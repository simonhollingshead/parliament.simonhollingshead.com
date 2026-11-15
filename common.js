export const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
export const isoDateFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' });
export const headerDateFormatter = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'Europe/London',
});

export const PARTY_ABBREVIATIONS = {
  'Labour': 'LAB',
  'Labour (Co-op)': 'LAB',
  'Conservative': 'CON',
  'Liberal Democrat': 'LD',
  'Crossbench': 'XB',
  'Green Party': 'GRN',
  'Democratic Unionist Party': 'DUP',
  'Non-affiliated': 'NA',
  'Independent': 'IND',
  'Plaid Cymru': 'PC',
  'Bishops': 'BSH',
  'Alliance': 'ALL',
  'Ulster Unionist Party': 'UUP',
  'Scottish National Party': 'SNP',
  'Reform UK': 'REF',
  'The City Remembrancer': 'CTY',
  'Sharpe Pritchard LLP': 'A:SP',
  'Broadfield Law UK LLP': 'A:BL',
};

export function parseDate(dateStr) {
  if (typeof dateStr !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null;
  const dateObj = new Date(`${dateStr}T12:00:00Z`);
  return !Number.isNaN(dateObj.getTime()) && isoDateFormatter.format(dateObj) === dateStr ? dateObj : null;
}

export function parseHexColour(rawHex) {
  let hex = rawHex?.replace(/^#/, '').trim() || '';
  if (/^[0-9a-f]{3}$/i.test(hex)) {
    hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
  }
  return /^[0-9a-f]{6}$/i.test(hex) ? hex : null;
}

export function getContrastTextColour(hex) {
  const toLinear = offset => {
    const c = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const luminance = 0.2126 * toLinear(0) + 0.7152 * toLinear(2) + 0.0722 * toLinear(4);
  return luminance > 0.34 ? '#000000' : '#ffffff';
}

export function createPartyChip(entries, fallbackLabel = null) {
  const seen = new Set();
  const chip = document.createElement('span');
  chip.className = 'chip chip-party';

  for (const entry of entries || []) {
    if (!entry?.party) continue;
    const shortParty = PARTY_ABBREVIATIONS[entry.party];
    const label = shortParty || entry.party;
    if (seen.has(label)) continue;
    seen.add(label);

    const span = document.createElement('span');
    span.textContent = label;
    const hex = shortParty ? parseHexColour(entry.partyColour) : null;
    if (hex) {
      span.className = 'party-seg';
      span.style.backgroundColor = `#${hex}`;
      span.style.color = getContrastTextColour(hex);
    } else {
      span.className = 'party-seg party-seg-unknown';
    }
    chip.appendChild(span);
  }

  if (seen.size === 0) {
    if (!fallbackLabel) return null;
    const fallback = document.createElement('span');
    fallback.className = 'party-seg party-seg-unknown';
    fallback.textContent = fallbackLabel;
    chip.appendChild(fallback);
  }

  return chip;
}

export function createHouseChip(house, leadHouse = null) {
  const chip = document.createElement('span');
  if (house === 'Commons') {
    chip.className = 'chip chip-house-commons';
    chip.textContent = 'HC';
  } else if (house === 'Lords') {
    chip.className = 'chip chip-house-lords';
    chip.textContent = 'HL';
  } else if (house === 'Joint' && (leadHouse === 'Commons' || leadHouse === 'Lords')) {
    chip.className = `chip chip-house-joint-${leadHouse.toLowerCase()}`;
    chip.textContent = 'JT';
  } else {
    chip.className = 'chip chip-unknown';
    chip.textContent = [house, leadHouse].filter(Boolean).join('/') || '?';
  }
  return chip;
}

export function createStatusElement(text, isError = false) {
  const p = document.createElement('p');
  p.className = isError ? 'region-status region-status-error' : 'region-status';
  p.textContent = text;
  return p;
}
