export function formatNoteType(noteType) {
  const map = {
    'note': 'Note',
    'task': 'Task',
    'event': 'Event',
    'recipe': 'Recipe',
    'vocabulary': 'Vocabulary',
  };
  return map[noteType] || noteType;
}

export function formatDate(dateString) {
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const absMs = Math.abs(diffMs);
  const minutes = Math.round(diffMs / (1000 * 60));
  const hours = Math.round(diffMs / (1000 * 60 * 60));
  const days = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (absMs < 60 * 1000) return rtf.format(0, 'minute');
  if (absMs < 60 * 60 * 1000) return rtf.format(minutes, 'minute');
  if (absMs < 24 * 60 * 60 * 1000) return rtf.format(hours, 'hour');
  if (absMs < 7 * 24 * 60 * 60 * 1000) return rtf.format(days, 'day');
  return date.toLocaleDateString();
}

export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}


