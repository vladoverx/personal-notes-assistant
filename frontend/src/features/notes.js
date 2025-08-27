import * as api from '../services/api.js';
import { formatNoteType, formatDate } from '../utils/format.js';
import { applyTagColors } from '../utils/colors.js';

let state = { notes: [], currentNote: null, filters: { note_type: '', tag: '' } };
let searchDebounceTimer = null;
let latestSearchSeq = 0;
const SEARCH_DEBOUNCE_MS = 250;

export function initNotes() {
  const newNoteBtn = document.getElementById('new-note-btn');
  const noteForm = document.getElementById('note-form');
  const deleteNoteBtn = document.getElementById('delete-note');
  const searchInput = document.getElementById('search');
  const notesGrid = document.getElementById('notes-grid');
  const filterCategory = document.getElementById('filter-category');
  const filterTag = document.getElementById('filter-tag');

  newNoteBtn?.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); openNewNote(); });
  noteForm?.addEventListener('submit', handleSaveNote);
  document.getElementById('cancel-edit')?.addEventListener('click', closeNoteModal);
  deleteNoteBtn?.addEventListener('click', handleDeleteNote);
  searchInput?.addEventListener('input', handleSearchInput);
  filterCategory?.addEventListener('change', handleFilterChange);
  filterTag?.addEventListener('change', handleFilterChange);

  // Populate filters from API
  void loadFilters();

  // Event delegation for notes grid
  notesGrid?.addEventListener('click', (e) => {
    const tile = e.target.closest('.tile');
    if (tile && notesGrid.contains(tile)) {
      const id = tile.getAttribute('data-id');
      if (id) openNote(id);
    }
  });

  // Modal interactions
  const modalBackdrop = document.getElementById('note-modal-backdrop');
  const modalDialog = document.querySelector('.modal-dialog');
  modalBackdrop?.addEventListener('click', (e) => { if (e.target === modalBackdrop) closeNoteModal(); });
  modalDialog?.addEventListener('click', (e) => e.stopPropagation());
}

export async function loadNotes() {
  try {
    const list = await api.listNotes();
    if (Array.isArray(list)) {
      state.notes = list;
      // If filters or query are active, re-run filtered search; else render all
      if (hasActiveSearchOrFilters()) {
        scheduleSearch();
      } else {
        renderNotes();
      }
    }
  } catch {
    // ignore
  }
}

export function renderNotes(list = state.notes) {
  const notesGrid = document.getElementById('notes-grid');
  if (!list || list.length === 0) { notesGrid.innerHTML = '<div class="empty">No notes yet. Create your first note!</div>'; return; }
  notesGrid.innerHTML = list.map(note => `
    <div class="tile" data-id="${note.id}">
      <div class="tile-meta">
        <span class="chip">${formatNoteType(note.note_type) || 'Note'}</span>
        <small>${formatDate(note.created_at)}</small>
      </div>
      <h3 class="tile-title">${note.title || 'Untitled'}</h3>
      <p class="tile-body">${note.content ? note.content.substring(0, 100) + (note.content.length > 100 ? '...' : '') : 'No content'}</p>
      ${note.tags && note.tags.length > 0 ? `
        <div class="tile-tags">
          ${note.tags.slice(0, 3).map(tag => `<span class="tag-chip">${tag}</span>`).join('')}
          ${note.tags.length > 3 ? `<span class="tag-chip more">+${note.tags.length - 3}</span>` : ''}
        </div>` : ''}
    </div>`).join('');
  // Apply deterministic colors per tag
  try { applyTagColors(notesGrid); } catch {}
}

export function openNote(noteId) {
  const idStr = String(noteId);
  const note = state.notes.find(n => String(n.id) === idStr);
  if (note) {
    state.currentNote = note;
    const noteTitle = document.getElementById('note-title');
    const noteCategory = document.getElementById('note-category');
    const noteContent = document.getElementById('note-content');
    noteTitle.value = note.title || '';
    noteCategory.value = note.note_type || '';
    noteContent.value = note.content || '';
    document.getElementById('delete-note').classList.remove('hidden');
    openNoteModal();
    return;
  }

  // Fallback: fetch note by ID (e.g., when opened from chat sources)
  void (async () => {
    try {
      const fetched = await api.getNote(noteId);
      if (fetched) {
        // Merge into state if not present
        const exists = state.notes.some(n => String(n.id) === String(fetched.id));
        if (!exists) state.notes.unshift(fetched);
        state.currentNote = fetched;
        const noteTitle = document.getElementById('note-title');
        const noteCategory = document.getElementById('note-category');
        const noteContent = document.getElementById('note-content');
        noteTitle.value = fetched.title || '';
        noteCategory.value = fetched.note_type || '';
        noteContent.value = fetched.content || '';
        document.getElementById('delete-note').classList.remove('hidden');
        openNoteModal();
      }
    } catch {}
  })();
}

export function openNewNote() {
  state.currentNote = null; 
  const noteTitle = document.getElementById('note-title');
  const noteCategory = document.getElementById('note-category');
  const noteContent = document.getElementById('note-content');
  noteTitle.value = ''; noteCategory.value = ''; noteContent.value = '';
  document.getElementById('delete-note').classList.add('hidden');
  openNoteModal();
}

function openNoteModal() { document.getElementById('note-modal').classList.add('show'); document.body.classList.add('blurred'); }
function closeNoteModal() { document.getElementById('note-modal').classList.remove('show'); document.body.classList.remove('blurred'); state.currentNote = null; }

async function handleSaveNote(event) {
  event.preventDefault();
  const noteTitle = document.getElementById('note-title');
  const noteCategory = document.getElementById('note-category');
  const noteContent = document.getElementById('note-content');
  try {
    if (state.currentNote) {
      // Prepare partial update payload respecting backend schema (omit fields not changed)
      const updatePayload = {};
      const titleVal = (noteTitle.value || '').trim();
      const contentVal = (noteContent.value || '').trim();

      updatePayload.title = titleVal || null;
      updatePayload.content = contentVal || null;
      const categoryVal = noteCategory.value;
      if (categoryVal) updatePayload.note_type = categoryVal; // omit if empty to avoid unintended reset

      if (!updatePayload.title && !updatePayload.content) {
        alert('Please provide a title or content.');
        return;
      }
      await api.updateNote(state.currentNote.id, updatePayload);
    } else {
      // Create payload; default note_type to 'note', provide empty tags list per schema
      const titleVal = (noteTitle.value || '').trim();
      const contentVal = (noteContent.value || '').trim();
      if (!titleVal && !contentVal) { alert('Please provide a title or content.'); return; }
      const createPayload = {
        title: titleVal || null,
        content: contentVal || null,
        note_type: noteCategory.value || 'note',
        tags: [],
      };
      await api.createNote(createPayload);
    }
    closeNoteModal();
    await loadNotes();
  } catch (err) { alert(`Failed to save note: ${err?.message || 'Please try again'}`); }
}

async function handleDeleteNote() {
  if (!state.currentNote) return;
  if (!confirm('Are you sure you want to delete this note?')) return;
  try {
    await api.deleteNote(state.currentNote.id);
    closeNoteModal(); await loadNotes();
  } catch { alert('Failed to delete note. Please try again.'); }
}

function handleSearchInput(event) {
  const raw = event?.target?.value ?? '';
  const searchInput = document.getElementById('search');
  if (searchInput && searchInput.value !== raw) searchInput.value = raw;
  scheduleSearch();
}

function handleFilterChange() {
  const filterCategory = document.getElementById('filter-category');
  const filterTag = document.getElementById('filter-tag');
  state.filters.note_type = filterCategory?.value || '';
  state.filters.tag = filterTag?.value || '';
  scheduleSearch();
}

function hasActiveSearchOrFilters() {
  const query = (document.getElementById('search')?.value || '').trim();
  const { note_type, tag } = state.filters;
  return Boolean(query) || Boolean(note_type) || Boolean(tag);
}

function scheduleSearch() {
  const raw = document.getElementById('search')?.value || '';
  const query = raw.trim();
  const { note_type, tag } = state.filters;
  const notesGrid = document.getElementById('notes-grid');

  // If nothing to search or filter, show recent notes
  if (!query && !note_type && !tag) {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    renderNotes(state.notes);
    return;
  }

  const seq = ++latestSearchSeq;
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(async () => {
    try {
      const params = {
        query: query || null,
        note_type: note_type || null,
        tags: tag ? [tag] : null,
        limit: 50,
      };
      const results = await api.searchNotes(params);
      if (seq !== latestSearchSeq) return;
      if (!Array.isArray(results) || results.length === 0) {
        notesGrid.innerHTML = '<div class="empty">No notes found matching your search.</div>';
        return;
      }
      renderNotes(results);
    } catch {
      // Fallback: client-side filtering on cached notes
      const q = (query || '').toLowerCase();
      const filteredNotes = state.notes.filter(note => {
        const matchesQuery = !q || (
          (note.title && note.title.toLowerCase().includes(q)) ||
          (note.content && note.content.toLowerCase().includes(q))
        );
        const matchesType = !note_type || String(note.note_type) === String(note_type);
        const matchesTag = !tag || (Array.isArray(note.tags) && note.tags.includes(tag));
        return matchesQuery && matchesType && matchesTag;
      });
      if (filteredNotes.length === 0) { notesGrid.innerHTML = '<div class="empty">No notes found matching your search.</div>'; return; }
      renderNotes(filteredNotes);
    }
  }, SEARCH_DEBOUNCE_MS);
}

async function loadFilters() {
  const [types, taxonomy] = await Promise.allSettled([
    api.getNoteTypes(),
    api.getUserTaxonomy(),
  ]);

  const filterCategory = document.getElementById('filter-category');
  const filterTag = document.getElementById('filter-tag');

  if (filterCategory && types.status === 'fulfilled' && Array.isArray(types.value)) {
    const current = filterCategory.value || '';
    filterCategory.innerHTML = '<option value="">All categories</option>' +
      types.value.map(t => `<option value="${t}">${formatNoteType(t) || t}</option>`).join('');
    filterCategory.value = current;
  }

  if (filterTag && taxonomy.status === 'fulfilled' && taxonomy.value && Array.isArray(taxonomy.value.tag_vocab)) {
    const tags = taxonomy.value.tag_vocab;
    const current = filterTag.value || '';
    filterTag.innerHTML = '<option value="">All tags</option>' +
      tags.map(tag => `<option value="${tag}">${tag}</option>`).join('');
    filterTag.value = current;
  }
}


