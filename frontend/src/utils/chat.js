export function toolStartText(name) {
  switch (name) {
    case 'search_notes': return 'Searching for the notes';
    case 'create_note': return 'Creating a new note';
    case 'update_note': return 'Updating the note';
    case 'delete_note': return 'Deleting the note';
    default: return 'Working…';
  }
}

export function toolDoneText(name) {
  switch (name) {
    case 'search_notes': return 'Search completed';
    case 'create_note': return 'Note created';
    case 'update_note': return 'Update completed';
    case 'delete_note': return 'Deletion completed';
    default: return 'Done';
  }
}


