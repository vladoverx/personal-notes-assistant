import * as api from '../services/api.js';
import { renderAssistantMarkdown, preloadMarkdownDeps, createStreamingMarkdownRenderer } from '../utils/markdown.js';
import { escapeHtml, formatNoteType, formatDate } from '../utils/format.js';
import { scrollChatToBottom } from '../utils/dom.js';
import { toolStartText, toolDoneText } from '../utils/chat.js';

let lastResponseId = null;
let chatEventSource = null;
let chatHasStarted = false;
let statusBubbleEl = null;
const toolChipByCallId = new Map();
let initialized = false;
let streamingMessageRef = null; // { containerEl, textEl, buffer }

// Cache for note metadata to avoid repeated fetches
const noteMetaCache = new Map(); // id -> { title, content, note_type, created_at, updated_at, tags }
let tooltipEl = null; // Singleton tooltip element
let currentPreviewAnchor = null; // Track the anchor that owns the current tooltip

export function initChatController() {
  if (initialized) return;
  initialized = true;
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');

  // Warm up markdown libraries in the background to reduce first-render jank
  try { preloadMarkdownDeps(); } catch {}

  chatForm?.addEventListener('submit', handleChatSubmit);

  // Submit chat on Enter, allow Shift+Enter for newline
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey && !e.isComposing) {
      e.preventDefault();
      if (typeof chatForm?.requestSubmit === 'function') {
        chatForm.requestSubmit();
      } else {
        chatForm?.submit();
      }
    }
  });

  // Allow app to reset chat state on sign-out
  window.addEventListener('app-signed-out', resetChatState);

  // Close any open stream when navigating away to prevent leaks
  window.addEventListener('beforeunload', () => {
    try { if (chatEventSource) chatEventSource.close(); } catch {}
  });

  // If app requested chat reset before module loaded, honor it now
  try {
    if (sessionStorage.getItem('resetChat') === '1') {
      resetChatState();
      sessionStorage.removeItem('resetChat');
    }
  } catch {}
}

export function applyChatCenteringState() {
  const chatPage = document.getElementById('chat-page');
  const chatLog = document.getElementById('chat-log');
  if (!chatHasStarted && chatLog?.children.length === 0) chatPage.classList.add('centered'); else chatPage.classList.remove('centered');
  // Show hint before first interaction
  const hint = document.getElementById('chat-hint');
  if (hint) hint.classList.toggle('hidden', chatHasStarted);
}

export function showChatWelcome() {
  const chatLog = document.getElementById('chat-log');
  const chatEmpty = document.getElementById('chat-empty');
  if (chatLog && chatLog.children.length === 0) chatEmpty.style.display = 'block'; else chatEmpty.style.display = 'none';
}

async function handleChatSubmit(event) {
  event.preventDefault();
  const chatPage = document.getElementById('chat-page');
  const chatInput = document.getElementById('chat-input');
  const chatEmpty = document.getElementById('chat-empty');
  const chatHint = document.getElementById('chat-hint');
  const chatLog = document.getElementById('chat-log');
  const message = chatInput.value.trim();
  if (!message) return;
  chatEmpty.style.display = 'none';
  if (!chatHasStarted) {
    chatHasStarted = true;
    chatPage.classList.remove('centered');
    if (chatHint) chatHint.classList.add('hidden');
  }
  addChatMessage('user', message);
  chatInput.value = '';
  showStatusBubble('Thinking…');
  try {
    if (chatEventSource) { chatEventSource.close(); chatEventSource = null; }
    // Ensure token is fresh before opening a long-lived SSE connection
    await api.ensureSessionFresh();
    chatEventSource = api.streamChat({ message, previousResponseId: lastResponseId });
    chatEventSource.addEventListener('tool_call', (e) => {
      hideStatusBubble();
      try {
        const data = JSON.parse(e.data);
        const friendly = toolStartText(data.name || 'tool');
        upsertToolChip(data.call_id, friendly, 'pending');
      } catch { upsertToolChip(undefined, 'Working…', 'pending'); }
    });
    chatEventSource.addEventListener('tool_result', (e) => {
      try {
        const data = JSON.parse(e.data);
        const friendly = toolDoneText(data.name || 'tool');
        upsertToolChip(data.call_id, friendly, 'done');
        // Between tool calls and the final response, show thinking
        showStatusBubble('Thinking…');
      } catch { /* ignore */ }
    });
    // Final streamed response handling
    chatEventSource.addEventListener('final_start', () => {
      // Ensure thinking bubble is visible until first token arrives
      showStatusBubble('Thinking…');
      // Prepare a streaming assistant message container
      const chatLog = document.getElementById('chat-log');
      const messageDiv = document.createElement('div');
      messageDiv.className = 'message assistant-message';
      const contentDiv = document.createElement('div');
      contentDiv.className = 'message-content';
      const textDiv = document.createElement('div');
      textDiv.className = 'message-text';
      contentDiv.appendChild(textDiv);
      messageDiv.appendChild(contentDiv);
      chatLog.appendChild(messageDiv);
      const renderer = createStreamingMarkdownRenderer(textDiv);
      streamingMessageRef = { containerEl: messageDiv, textEl: textDiv, renderer };
      scrollChatToBottom();
    });
    chatEventSource.addEventListener('final_delta', (e) => {
      try {
        const data = JSON.parse(e.data);
        const delta = typeof data.delta === 'string' ? data.delta : '';
        if (!streamingMessageRef) return;
        streamingMessageRef.renderer.append(delta);
        // Hide thinking once we start receiving tokens
        hideStatusBubble();
        scrollChatToBottom();
      } catch { /* ignore */ }
    });
    chatEventSource.addEventListener('final_done', (e) => {
      try {
        const data = JSON.parse(e.data);
        hideStatusBubble();
        if (streamingMessageRef) {
          // Ensure the last chunk is rendered
          // Renderer already throttles via rAF; force a final render by setting full text
          const finalText = streamingMessageRef.renderer.getBuffer();
          streamingMessageRef.renderer.setFullText(finalText);
          // Append sources, if any
          const sources = Array.isArray(data.sources) ? data.sources : [];
          if (sources.length > 0) {
            const sourcesHtml = `\n<div class="message-sources">\n  <div class="sources-label">Sources</div>\n  <div class="sources-list">\n    ${sources.map(id => { const label = typeof id === 'string' ? id.slice(0, 8) : String(id); return `<a href="#" class="source-link" data-id="${id}">\n      <span class="source-icon">📝</span>\n      <span class="source-text">${label}</span>\n    </a>`; }).join('')}\n  </div>\n</div>`;
            const wrapper = document.createElement('div');
            wrapper.innerHTML = sourcesHtml;
            streamingMessageRef.containerEl.querySelector('.message-content')?.appendChild(wrapper.firstElementChild);
            // Wire up source link clicks
            const sourcesContainer = streamingMessageRef.containerEl.querySelector('.sources-list');
            if (sourcesContainer) {
              sourcesContainer.addEventListener('click', (evt) => {
                const link = evt.target.closest('.source-link');
                if (!link) return;
                evt.preventDefault();
                const id = link.getAttribute('data-id');
                if (id) {
                  const openEvent = new CustomEvent('open-note', { detail: { id } });
                  window.dispatchEvent(openEvent);
                }
              });
              // Enhance with title fetching and previews
              enhanceSourceLinks(sourcesContainer);
            }
          }
          streamingMessageRef = null;
        }
        lastResponseId = data.response_id || null;
      } catch { /* ignore */ }
      chatEventSource && chatEventSource.close(); chatEventSource = null;
    });
    chatEventSource.addEventListener('final', (e) => {
      try {
        const data = JSON.parse(e.data);
        hideStatusBubble();
        addChatMessage('assistant', data.response, Array.isArray(data.sources) ? data.sources : []);
        lastResponseId = data.response_id || null;
      } catch {}
      chatEventSource && chatEventSource.close(); chatEventSource = null;
    });
    chatEventSource.addEventListener('error', (e) => {
      hideStatusBubble();
      // Remove any half-built streaming message
      try {
        if (streamingMessageRef) {
          streamingMessageRef.containerEl.remove();
          streamingMessageRef = null;
        }
      } catch {}
      let friendly = 'We could not complete that request. Please try again.';
      try {
        const data = JSON.parse(e.data || '{}');
        const serverMsg = typeof data.message === 'string' ? data.message : '';
        // Map known OpenAI error codes to user-friendly messages (docs: responses/object#error, error codes guide)
        const code = data?.error?.code || data?.code;
        if (code === 'rate_limit_exceeded' || code === 'rate_limit') friendly = 'Rate limit reached. Please wait a moment and try again.';
        else if (code === 'insufficient_quota') friendly = 'Quota exceeded. Try again later.';
        else if (code === 'unsupported_value' || serverMsg.includes('must be verified')) friendly = 'The model could not be streamed. Please try again.';
        else if (serverMsg) friendly = serverMsg;
      } catch {}
      addChatMessage('assistant', friendly);
      chatEventSource && chatEventSource.close(); chatEventSource = null;
    });
  } catch {
    hideStatusBubble(); addChatMessage('assistant', 'Sorry, I encountered an error. Please try again.');
  }
}

function addChatMessage(sender, text, sources = []) {
  const chatLog = document.getElementById('chat-log');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}-message`;
  const renderedText = sender === 'assistant' ? renderAssistantMarkdown(text) : escapeHtml(text);
  const sourcesHtml = (sender === 'assistant' && Array.isArray(sources) && sources.length > 0)
    ? `\n<div class="message-sources">\n  <div class="sources-label">Sources</div>\n  <div class="sources-list">\n    ${sources.map(id => { const label = typeof id === 'string' ? id.slice(0, 8) : String(id); return `<a href="#" class="source-link" data-id="${id}">\n      <span class="source-icon">📝</span>\n      <span class="source-text">${label}</span>\n    </a>`; }).join('')}\n  </div>\n</div>` : '';
  messageDiv.innerHTML = `
    <div class="message-content">
      <div class="message-text">${renderedText}</div>
      ${sourcesHtml}
    </div>`;
  chatLog.appendChild(messageDiv); scrollChatToBottom();

  // Delegate clicks on sources
  const sourcesContainer = messageDiv.querySelector('.sources-list');
  if (sourcesContainer) {
    sourcesContainer.addEventListener('click', (e) => {
      const link = e.target.closest('.source-link');
      if (!link) return;
      e.preventDefault();
      const id = link.getAttribute('data-id');
      if (id) {
        const openEvent = new CustomEvent('open-note', { detail: { id } });
        window.dispatchEvent(openEvent);
      }
    });
    // Enhance with title fetching and previews
    enhanceSourceLinks(sourcesContainer);
  }
}

function upsertToolChip(callId, text, state) {
  const chatLog = document.getElementById('chat-log');
  let ref = callId ? toolChipByCallId.get(callId) : null;
  if (!ref) {
    const row = document.createElement('div');
    row.className = 'tool-event';
    const chip = document.createElement('span');
    chip.className = `tool-chip ${state === 'done' ? 'done' : 'pending'}`;
    chip.textContent = text;
    row.appendChild(chip);
    chatLog.appendChild(row);
    scrollChatToBottom();
    if (callId) toolChipByCallId.set(callId, chip);
    return;
  }
  ref.textContent = text;
  ref.classList.toggle('pending', state !== 'done');
  ref.classList.toggle('done', state === 'done');
}

function showStatusBubble(text = 'Thinking…') {
  hideStatusBubble();
  const chatLog = document.getElementById('chat-log');
  statusBubbleEl = document.createElement('div');
  statusBubbleEl.className = 'status-bubble';
  statusBubbleEl.textContent = text;
  chatLog.appendChild(statusBubbleEl);
  scrollChatToBottom();
}

function hideStatusBubble() {
  if (statusBubbleEl) { statusBubbleEl.remove(); statusBubbleEl = null; }
}

function resetChatState() {
  lastResponseId = null;
  chatHasStarted = false;
  if (chatEventSource) { try { chatEventSource.close(); } catch {} chatEventSource = null; }
  toolChipByCallId.clear();
  // Reveal the hint again on reset
  const hint = document.getElementById('chat-hint');
  if (hint) hint.classList.remove('hidden');
}

// ----- Sources enhancement (titles + hover preview tooltip) -----

function enhanceSourceLinks(containerEl) {
  if (!containerEl) return;
  // Prefetch titles lazily and attach tooltip behaviors
  const links = containerEl.querySelectorAll('.source-link');
  links.forEach((link) => {
    const id = link.getAttribute('data-id');
    if (!id) return;
    // Replace label with title asynchronously
    updateSourceLabel(link, id);
  });

  // Event delegation for previews (mouse and keyboard)
  containerEl.addEventListener('mouseover', (evt) => {
    const link = evt.target.closest('.source-link');
    if (!link || !containerEl.contains(link)) return;
    const id = link.getAttribute('data-id');
    if (!id) return;
    showNotePreview(link, id);
  });
  containerEl.addEventListener('mouseout', (evt) => {
    const link = evt.target.closest('.source-link');
    // Hide only if leaving the link entirely
    const related = evt.relatedTarget;
    if (!link || (related && link.contains(related))) return;
    hideNotePreview();
  });
  containerEl.addEventListener('focusin', (evt) => {
    const link = evt.target.closest('.source-link');
    if (!link) return;
    const id = link.getAttribute('data-id');
    if (!id) return;
    showNotePreview(link, id);
  });
  containerEl.addEventListener('focusout', (evt) => {
    const link = evt.target.closest('.source-link');
    if (!link) return;
    hideNotePreview();
  });
  // Hide on container pointer leave and on click (navigate)
  containerEl.addEventListener('pointerleave', hideNotePreview);
  containerEl.addEventListener('click', hideNotePreview, { capture: true });

  // Global safety nets
  window.addEventListener('scroll', hideNotePreview, { passive: true });
  window.addEventListener('resize', hideNotePreview, { passive: true });
  document.addEventListener('pointerdown', hideNotePreview, { capture: true });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideNotePreview(); });
}

async function updateSourceLabel(linkEl, id) {
  try {
    const data = await getNoteMeta(id);
    const title = (data?.title && data.title.trim()) ? data.title.trim() : 'Untitled';
    const truncated = truncate(title, 42);
    const textEl = linkEl.querySelector('.source-text');
    if (textEl) textEl.textContent = truncated;
    linkEl.setAttribute('title', title);
  } catch {
    // leave default id-slice label
  }
}

async function showNotePreview(anchorEl, id) {
  const data = await getNoteMeta(id).catch(() => null);
  if (!data) return;
  ensureTooltip();
  // Build preview content
  const title = (data.title && data.title.trim()) ? data.title.trim() : 'Untitled';
  const snippet = (data.content || '').trim().slice(0, 180);
  const meta = `${formatNoteType(data.note_type)} · ${formatDate(data.created_at)}`;
  tooltipEl.innerHTML = `
    <div class="tooltip-title">${escapeHtml(truncate(title, 80))}</div>
    <div class="tooltip-meta">${escapeHtml(meta)}</div>
    ${snippet ? `<div class="tooltip-body">${escapeHtml(snippet)}${data.content && data.content.length > 180 ? '…' : ''}</div>` : ''}
  `;
  positionTooltip(anchorEl, tooltipEl);
  tooltipEl.setAttribute('aria-hidden', 'false');
  // Clear inline display so CSS can control visibility
  tooltipEl.style.display = '';
  if (currentPreviewAnchor && currentPreviewAnchor !== anchorEl) {
    try { currentPreviewAnchor.removeAttribute('aria-describedby'); } catch {}
  }
  anchorEl.setAttribute('aria-describedby', 'note-preview-tooltip');
  currentPreviewAnchor = anchorEl;
}

function hideNotePreview() {
  if (!tooltipEl) return;
  tooltipEl.setAttribute('aria-hidden', 'true');
  // Ensure hidden regardless of inline styles used during measurement
  tooltipEl.style.display = 'none';
  if (currentPreviewAnchor) {
    try { currentPreviewAnchor.removeAttribute('aria-describedby'); } catch {}
    currentPreviewAnchor = null;
  }
}

function ensureTooltip() {
  if (tooltipEl) return;
  tooltipEl = document.createElement('div');
  tooltipEl.id = 'note-preview-tooltip';
  tooltipEl.className = 'note-preview-tooltip';
  tooltipEl.setAttribute('role', 'tooltip');
  tooltipEl.setAttribute('aria-hidden', 'true');
  document.body.appendChild(tooltipEl);
}

function positionTooltip(anchorEl, tipEl) {
  const rect = anchorEl.getBoundingClientRect();
  const scrollX = window.scrollX || window.pageXOffset;
  const scrollY = window.scrollY || window.pageYOffset;
  const gap = 8;
  const maxWidth = Math.min(360, Math.max(240, Math.floor(window.innerWidth * 0.8)));
  tipEl.style.maxWidth = `${maxWidth}px`;
  tipEl.style.visibility = 'hidden';
  tipEl.style.left = '0px';
  tipEl.style.top = '0px';
  // Temporarily show to measure without relying on attribute CSS
  tipEl.style.display = 'block';
  const tRect = tipEl.getBoundingClientRect();
  // Prefer above; if not enough space, place below
  const aboveTop = rect.top + scrollY - tRect.height - gap;
  const belowTop = rect.bottom + scrollY + gap;
  const fitsAbove = rect.top >= tRect.height + gap;
  const top = fitsAbove ? aboveTop : belowTop;
  let left = rect.left + scrollX;
  const overflowRight = left + tRect.width - (scrollX + window.innerWidth);
  if (overflowRight > 0) left -= overflowRight + 8;
  if (left < scrollX + 8) left = scrollX + 8;
  tipEl.style.left = `${Math.round(left)}px`;
  tipEl.style.top = `${Math.round(top)}px`;
  tipEl.style.visibility = 'visible';
  // Let CSS control visibility afterwards
  tipEl.setAttribute('aria-hidden', 'false');
}

async function getNoteMeta(id) {
  if (noteMetaCache.has(id)) return noteMetaCache.get(id);
  const data = await api.getNote(id);
  noteMetaCache.set(id, data);
  return data;
}

function truncate(text, maxLen) {
  if (typeof text !== 'string') return '';
  return text.length > maxLen ? `${text.slice(0, maxLen - 1)}…` : text;
}


