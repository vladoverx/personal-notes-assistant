import { initAuth, validateToken } from '../features/auth.js';
import { initNotes, loadNotes, openNote, renderNotes } from '../features/notes.js';
import { getAuthToken } from '../services/api.js';

let currentPage = 'auth';

export function initApp() {
  document.addEventListener('DOMContentLoaded', () => {
    wireTabs();
    initAuth({
      onAuthSuccess: () => { showApp(); loadNotes(); },
      onSignOut: () => { showAuthPage(); clearChatUI(); notifyChatSignedOut(); }
    });
    initNotes();
    // Global unauthorized handler from API layer
    window.addEventListener('auth-unauthorized', () => {
      showAuthPage();
      clearChatUI();
      notifyChatSignedOut();
    });
    // Cross-feature: open note from chat source link
    window.addEventListener('open-note', (e) => {
      const id = e?.detail?.id;
      if (id) { void (async () => { await switchPage('notes'); openNote(id); })(); }
    });
    // Initial auth validation
    if (hasToken()) {
      validateToken().catch(() => { showAuthPage(); });
    } else {
      showAuthPage();
    }
  });
}

function wireTabs() {
  const tabNotes = document.getElementById('tab-notes');
  const tabChat = document.getElementById('tab-chat');
  tabNotes?.addEventListener('click', () => switchPage('notes'));
  tabChat?.addEventListener('click', () => switchPage('chat'));
}

function hasToken() { return !!getAuthToken(); }

export function showAuthPage() {
  const authPage = document.getElementById('auth-page');
  const appContent = document.getElementById('app-content');
  authPage.classList.remove('hidden');
  appContent.classList.add('hidden');
  document.body.classList.remove('chat-page');
  currentPage = 'auth';
}

export function showApp() {
  const authPage = document.getElementById('auth-page');
  const appContent = document.getElementById('app-content');
  authPage.classList.add('hidden');
  appContent.classList.remove('hidden');
  switchPage('notes');
}

export async function switchPage(page) {
  currentPage = page;
  const tabNotes = document.getElementById('tab-notes');
  const tabChat = document.getElementById('tab-chat');
  const notesPage = document.getElementById('notes-page');
  const chatPage = document.getElementById('chat-page');

  tabNotes?.classList.remove('primary');
  tabChat?.classList.remove('primary');
  notesPage.classList.add('hidden');
  chatPage.classList.add('hidden');

  if (page === 'notes') {
    notesPage.classList.remove('hidden');
    tabNotes?.classList.add('primary');
    document.body.classList.remove('chat-page');
    loadNotes();
  } else {
    chatPage.classList.remove('hidden');
    tabChat?.classList.add('primary');
    document.body.classList.add('chat-page');
    // Lazy-load chat controller for performance
    const { initChatController, applyChatCenteringState, showChatWelcome } = await import('../features/chat-controller.js');
    initChatController();
    applyChatCenteringState();
    showChatWelcome();
  }
}

function clearChatUI() {
  const chatLog = document.getElementById('chat-log');
  const chatEmpty = document.getElementById('chat-empty');
  if (chatLog) chatLog.innerHTML = '';
  if (chatEmpty) chatEmpty.style.display = 'block';
}

function notifyChatSignedOut() {
  try {
    const evt = new Event('app-signed-out');
    window.dispatchEvent(evt);
  } catch {
    try { sessionStorage.setItem('resetChat', '1'); } catch {}
  }
}


