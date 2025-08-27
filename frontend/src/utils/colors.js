// Utilities for generating stable colors from strings (tags)
// Based on hashing the tag to a hue and using CSS custom properties for styling.


function hashString(input) {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return hash >>> 0;
}

export function stringToHue(value) {
  const normalized = String(value || '').toLowerCase().trim();
  const hash = hashString(normalized);
  return hash % 360;
}

export function applyTagColors(root = document) {
  const container = root instanceof Element ? root : document;
  const chips = container.querySelectorAll('.tag-chip:not(.more)');
  chips.forEach((chip) => {
    const label = (chip.textContent || '').trim();
    if (!label) return;
    const hue = stringToHue(label);
    chip.style.setProperty('--tag-h', String(hue));
  });
}
