let markedModule = null;
let domPurifyModule = null;

export async function preloadMarkdownDeps() {
  if (!markedModule) {
    markedModule = await import('https://cdn.jsdelivr.net/npm/marked@12/+esm');
  }
  if (!domPurifyModule) {
    domPurifyModule = await import('https://cdn.jsdelivr.net/npm/dompurify@3.0.8/dist/purify.es.mjs');
  }
}

export function renderAssistantMarkdown(text) {
  if (!text) return '';
  const raw = String(text);
  if (!markedModule || !domPurifyModule) {
    // Fallback: escape only, to avoid unsafe HTML before deps load
    return raw
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br/>');
  }
  const html = markedModule.marked.parse(raw, { mangle: false, headerIds: false });
  return domPurifyModule.default.sanitize(html, { USE_PROFILES: { html: true } });
}

export function createStreamingMarkdownRenderer(targetEl) {
  let buffer = '';
  let needsFrame = false;

  const flush = () => {
    needsFrame = false;
    targetEl.innerHTML = renderAssistantMarkdown(buffer);
  };

  return {
    append(delta) {
      buffer += typeof delta === 'string' ? delta : '';
      if (!needsFrame) {
        needsFrame = true;
        requestAnimationFrame(flush);
      }
    },
    setFullText(text) {
      buffer = String(text || '');
      targetEl.innerHTML = renderAssistantMarkdown(buffer);
    },
    getBuffer() { return buffer; },
    clear() { buffer = ''; targetEl.innerHTML = ''; }
  };
}


