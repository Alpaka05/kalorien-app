'use strict';

const fmtKcal = (n) => Math.round(n).toLocaleString('de-DE') + ' kcal';
const fmtNum = (n) => Math.round(n).toLocaleString('de-DE');
const weekdayShort = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { weekday: 'short' });
// Gewicht immer mit einer Nachkommastelle, damit 68 und 68,5 untereinander
// gleich breit sind.
const fmtKg = (kg) =>
  kg.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
// Veränderung mit Vorzeichen; echtes Minus statt Bindestrich.
const fmtKgDelta = (delta) => {
  const rounded = Math.round(delta * 10) / 10;
  return (rounded > 0 ? '+' : rounded < 0 ? '−' : '±') + fmtKg(Math.abs(rounded));
};
const dateLong = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
const dateShort = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', {
    day: 'numeric', month: 'long',
  });
// Bewusst nicht toISOString(): das rechnet auf UTC um und verschiebt das Datum
// in unserer Zeitzone um einen Tag nach hinten.
const isoLocal = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-` +
  `${String(date.getDate()).padStart(2, '0')}`;

const $ = (id) => document.getElementById(id);

// Zielrichtung des Kontos. "lose" dreht die Bewertung um: das Tagesziel ist
// dann eine Obergrenze statt einer Untergrenze. Der Standard "gain" gilt auch,
// solange /api/me noch nicht geantwortet hat, damit nichts kurz falsch
// eingefärbt aufblitzt.
const losingWeight = () => (state.me && state.me.goal_direction) === 'lose';

// --------------------------------------------------------------------------
// Symbole
//
// Gezeichnet, nicht getippt: vorher standen hier Schriftzeichen (\u270e, \u00d7),
// die je nach Gerät in einer fremden Strichstärke und Ausrichtung erscheinen.
// Alle Pfade teilen dieselbe Strichstärke 1.75 wie der Pfeil der Auswahlfelder.
// --------------------------------------------------------------------------

const ICON = {
  pencil: '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="M14.5 7.5l2 2"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V4.5h6V7"/><path d="M6 7l1 12.5h10L18 7"/><path d="M10 11v5M14 11v5"/>',
  check: '<path d="M4.5 12.5l5 5 10-11"/>',
  down: '<path d="M12 5v13"/><path d="M6 12.5l6 6 6-6"/>',
  up: '<path d="M12 19V6"/><path d="M6 11.5l6-6 6 6"/>',
  dash: '<path d="M5 12h14"/>',
  alert: '<path d="M12 4.5 2.5 20h19L12 4.5Z"/><path d="M12 10v4.5"/><path d="M12 17.6v.4"/>',
};

function icon(name, size = 16) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.75');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = ICON[name] || '';
  return svg;
}

// Statussymbol der Einschätzung. Die Farbe kommt aus dem CSS über die
// Status-Klasse am Panel, die Form muss die Aussage allein tragen.
const COACH_ICON = {
  on_track: 'check',
  above_goal: 'up',
  slightly_behind: 'down',
  behind: 'down',
  no_data: 'dash',
  no_goal: 'dash',
};

function setCoachIcon(name) {
  const wrap = $('coach-icon');
  wrap.textContent = '';
  wrap.appendChild(icon(name, 18));
}

const state = {
  me: null,
  range: 7,
  metric: 'kcal',     // Was das Diagramm zeigt: kcal, protein oder weight
  end: null,          // Enddatum des angezeigten Zeitraums (null = heute)
  today: null,
  summary: null,
  selectedDay: null,
  editingId: null,
  undo: null,         // Zuletzt gelöschter Eintrag von heute: { entry, index }
  presets: null,      // Schnellwahl aus /api/presets
  weights: null,      // Messungen aus /api/weights, neueste zuerst
  calendar: null,     // Tagessummen des letzten Jahres aus /api/calendar
  photo: null,        // Angehängtes Foto als verkleinerte JPEG-data:-URL
  backfill: null,     // Tag, für den gerade nachgetragen wird (JJJJ-MM-TT)
};

// --------------------------------------------------------------------------
// API
// --------------------------------------------------------------------------

// Fehler, bei denen die App selbst gar nicht geantwortet hat: das Netz war
// weg, oder der Proxy davor (Cloudflare, Nginx) hat die Anfrage mit einer
// eigenen HTML-Seite beendet – etwa weil der Container gerade neu startet oder
// die Antwort zu lange gedauert hat. Solche Fehler lohnen einen zweiten
// Versuch; eine JSON-Fehlermeldung der App dagegen nicht.
class GatewayError extends Error {}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: options.body ? { 'Content-Type': 'application/json' } : {},
      ...options,
    });
  } catch (err) {
    throw new GatewayError('Keine Verbindung zum Server. Bitte nochmal versuchen.');
  }
  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Nicht angemeldet.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (data && data.error) throw new Error(data.error);
    // Keine JSON-Antwort heißt: nicht von der App. Den Statuscode nennen,
    // damit sich die Ursache im Log des Proxys wiederfinden lässt.
    const status = response.status;
    const timeout = status === 504 || status === 524;
    throw new GatewayError(
      (timeout
        ? 'Der Server hat nicht rechtzeitig geantwortet'
        : 'Der Server war gerade nicht erreichbar') +
        ` (HTTP ${status}). Bitte nochmal versuchen.`
    );
  }
  return data || {};
}

function setMessage(el, text, kind = 'error') {
  el.textContent = text || '';
  el.className = 'message' + (text ? ' ' + kind : '');
}

// --------------------------------------------------------------------------
// Eintrag hinzufügen
// --------------------------------------------------------------------------

// keepLabel: Chips tragen ihre kcal-Zahl in einem eigenen Element. Ein
// Textwechsel würde die Auszeichnung zerstören (und den Chip beim Zurücksetzen
// auf eine Zeile Text eindampfen), deshalb zeigen sie das Warten nur über den
// gesperrten Zustand.
// onSaved läuft direkt nach dem Speichern, noch bei gesperrtem Knopf. Das
// Eingabefeld leert nur handleAdd darüber – ein Chip soll keinen Text löschen,
// der gerade getippt wird.
async function addEntry(payload, buttonEl, keepLabel = false, onSaved = null) {
  setMessage($('error-msg'), '');
  state.undo = null;
  const label = buttonEl && !keepLabel ? buttonEl.textContent : null;
  if (buttonEl) {
    buttonEl.disabled = true;
    if (!keepLabel) {
      buttonEl.textContent = payload.kcal == null ? 'Schätze…' : 'Speichere…';
    }
  }
  // Beim Nachtragen gilt der Tag für alles, was hier ankommt – Eingabefeld,
  // Foto und Schnellwahl. Die Uhrzeit ist optional, leer nimmt der Server die
  // jetzige.
  const backfill = state.backfill;
  if (backfill) {
    payload = { ...payload, date: backfill };
    if ($('backfill-time').value) payload.time = $('backfill-time').value;
  }
  try {
    await api('/api/entries', { method: 'POST', body: JSON.stringify(payload) });
    if (onSaved) onSaved();
    // Den Tag aufklappen, damit der neue Eintrag sofort zu sehen ist.
    if (backfill && state.metric !== 'weight') state.selectedDay = backfill;
    await refreshAll();
    if (backfill) setMessage($('error-msg'), 'Nachgetragen für ' + dateLong(backfill) + '.', 'ok');
  } catch (err) {
    setMessage($('error-msg'), err.message);
  } finally {
    if (buttonEl) {
      buttonEl.disabled = false;
      if (!keepLabel) buttonEl.textContent = label;
    }
  }
}

async function handleAdd() {
  // Solange eine Schätzung läuft, ist der Knopf gesperrt – Enter im Feld
  // kommt aber an ihm vorbei. Ohne diese Abfrage speichert ein zweites Enter
  // während der Schätzung denselben Eintrag doppelt (und kostet einen
  // zweiten KI-Aufruf).
  if ($('add-btn').disabled) return;
  const input = $('food-input');
  const desc = input.value.trim();
  const photo = state.photo;
  if (!desc && !photo) {
    setMessage($('error-msg'), 'Bitte gib ein, was du gegessen oder getrunken hast.');
    return;
  }
  const payload = photo ? { desc, image: photo } : { desc };
  setPhotoBusy(!!photo);
  // Nur leeren, wenn dort noch der gespeicherte Text steht – wer während der
  // Schätzung schon weitertippt, verliert sonst das Neue. Schlägt die
  // Schätzung fehl, bleibt das Foto für einen zweiten Versuch hängen.
  await addEntry(payload, $('add-btn'), false, () => {
    if (input.value.trim() === desc) input.value = '';
    if (state.photo === photo) clearPhoto();
  });
  setPhotoBusy(false);
  // Während der Schätzung kann das Nachtragen begonnen oder beendet worden
  // sein; addEntry stellt die Beschriftung von vorher wieder her.
  syncAddLabel();
}

// --------------------------------------------------------------------------
// Nachtragen
// --------------------------------------------------------------------------

function syncAddLabel() {
  const btn = $('add-btn');
  if (!btn.disabled) btn.textContent = state.backfill ? 'Nachtragen' : 'Hinzufügen';
}

function startBackfill(date) {
  const changed = state.backfill !== date;
  state.backfill = date;
  $('backfill-date').textContent = dateLong(date);
  if (changed) $('backfill-time').value = '';
  $('backfill-bar').hidden = false;
  setMessage($('error-msg'), '');
  syncAddLabel();
  if (state.selectedDay) renderDayDetail();
  // Auf dem Handy liegt das Eingabefeld weit über dem Diagramm.
  $('backfill-bar').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  $('food-input').focus({ preventScroll: true });
}

function closeBackfill() {
  state.backfill = null;
  $('backfill-bar').hidden = true;
  setMessage($('error-msg'), '');
  syncAddLabel();
  if (state.selectedDay) renderDayDetail();
}

// --------------------------------------------------------------------------
// Foto anhängen
// --------------------------------------------------------------------------

// Lange Kante in Pixeln. Mehr bringt der KI nichts (Claude rechnet größere
// Bilder selbst auf etwa diese Größe herunter), und ein Handyfoto schrumpft
// so von mehreren MB auf ein paar hundert KB.
const PHOTO_MAX_EDGE = 1568;

// Liest das Bild über ein <img>: das dreht es nach seinen EXIF-Angaben richtig
// herum und kann in Safari auch HEIC. Das Ergebnis ist immer JPEG.
function shrinkPhoto(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(1, PHOTO_MAX_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      const ctx = canvas.getContext('2d');
      // Durchsichtige PNGs bekämen in JPEG sonst einen schwarzen Grund.
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Das Foto konnte nicht geöffnet werden.'));
    };
    img.src = url;
  });
}

async function attachPhoto(file) {
  if (!file || !file.type.startsWith('image/') || $('add-btn').disabled) return;
  setMessage($('error-msg'), '');
  try {
    state.photo = await shrinkPhoto(file);
  } catch (err) {
    setMessage($('error-msg'), err.message);
    return;
  }
  $('photo-thumb').src = state.photo;
  $('photo-attach').hidden = false;
  $('photo-btn').classList.add('on');
  $('food-input').placeholder = 'Optional: z. B. ohne Soße, halbe Portion';
  $('food-input').focus({ preventScroll: true });
}

function clearPhoto() {
  state.photo = null;
  $('photo-attach').hidden = true;
  $('photo-thumb').removeAttribute('src');
  $('photo-btn').classList.remove('on');
  $('food-input').placeholder = 'z. B. 2 Scheiben Toast mit Butter';
}

function setPhotoBusy(busy) {
  $('photo-attach').classList.toggle('busy', busy);
  $('photo-title').textContent = busy ? 'Schaue mir das Foto an…' : 'Foto angehängt';
  $('photo-hint').textContent = busy
    ? 'Dauert meist ein paar Sekunden.'
    : 'Schreib dazu, was man nicht sieht – oder füg es gleich hinzu.';
  $('photo-remove').disabled = busy;
  $('photo-btn').disabled = busy;
}

function firstImage(list) {
  return Array.from(list || []).find((f) => f.type && f.type.startsWith('image/'));
}

// --------------------------------------------------------------------------
// Heutige Einträge
// --------------------------------------------------------------------------

async function loadToday() {
  const data = await api('/api/entries');
  state.today = data;
  renderToday();
}

function renderTodayHint() {
  const data = state.today;
  const hint = $('today-hint');
  if (!data) return;
  // Nach Mitternacht bei verschobenem Tagesbeginn ist "Heute" nicht der
  // Kalendertag – ohne diesen Hinweis wirkt das wie ein Fehler.
  if (data.calendar_date && data.date !== data.calendar_date) {
    hint.textContent = ' · noch ' + dateShort(data.date);
    hint.title = `Ein neuer Tag beginnt bei dir um ${String(data.day_start_hour).padStart(2, '0')}:00.`;
  } else {
    hint.textContent = '';
    hint.removeAttribute('title');
  }
}

function renderToday() {
  const list = $('today-list');
  const entries = state.today ? state.today.entries : [];
  list.textContent = '';

  const totalKcal = entries.reduce((sum, e) => sum + e.kcal, 0);
  const totalProtein = entries.reduce((sum, e) => sum + (e.protein || 0), 0);
  $('today-total').textContent = fmtKcal(totalKcal);
  renderGoalProgress(totalKcal, totalProtein);
  renderTodayHint();

  // Ein Eintrag von gestern, der nach dem Tageswechsel noch in state.undo
  // steht, gehört nicht in die heutige Liste.
  const undo = state.undo && state.today && state.undo.entry.date === state.today.date
    ? state.undo
    : null;

  if (!entries.length && !undo) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'Noch nichts eingetragen heute.';
    list.appendChild(empty);
    return;
  }

  const rows = entries.map((entry) =>
    state.editingId === entry.id ? buildEditForm(entry) : buildEntryRow(entry)
  );
  if (undo) rows.splice(Math.min(undo.index, rows.length), 0, buildUndoRow(undo.entry));
  rows.forEach((row) => list.appendChild(row));
}

// Steht an der Stelle des gelöschten Eintrags, bis etwas anderes eingetragen,
// geändert oder gelöscht wird. Zurückgeholt wird mit den gespeicherten Werten,
// also ohne neue Schätzung.
function buildUndoRow(entry) {
  const row = document.createElement('div');
  row.className = 'entry-row undo-row';
  row.setAttribute('role', 'status');

  const text = document.createElement('p');
  text.className = 'undo-text';
  text.textContent = 'Gelöscht: ' + entry.desc;

  const btn = document.createElement('button');
  btn.className = 'link';
  btn.textContent = 'Rückgängig';
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      await api('/api/entries', {
        method: 'POST',
        body: JSON.stringify({
          desc: entry.desc, kcal: entry.kcal, protein: entry.protein,
          date: entry.date, time: entry.time,
        }),
      });
      state.undo = null;
      await refreshAll();
    } catch (err) {
      setMessage($('error-msg'), err.message);
      btn.disabled = false;
    }
  });

  row.append(text, btn);
  return row;
}

// Zeile und Formular stehen in der heutigen Liste und in der Karte eines
// vergangenen Tages. rerender zeichnet die Liste neu, in der sie stehen,
// entries ist diese Liste (für die Stelle der Rückgängig-Zeile).
function buildEntryRow(entry, rerender = renderToday, entries = null) {
  const row = document.createElement('div');
  row.className = 'entry-row';

  const left = document.createElement('div');
  const desc = document.createElement('p');
  desc.className = 'entry-desc';
  desc.textContent = entry.desc;
  const time = document.createElement('p');
  time.className = 'entry-time';
  time.textContent = entry.time;
  left.append(desc, time);

  const right = document.createElement('div');
  right.className = 'entry-right';
  const kcal = document.createElement('span');
  kcal.className = 'entry-kcal';
  kcal.textContent = fmtNum(entry.kcal) + ' kcal';
  right.appendChild(kcal);
  if (entry.protein != null) {
    const protein = document.createElement('span');
    protein.className = 'entry-protein';
    protein.textContent = fmtNum(entry.protein) + ' g E';
    right.appendChild(protein);
  }

  const edit = document.createElement('button');
  edit.className = 'icon-btn';
  edit.title = 'Eintrag bearbeiten';
  edit.setAttribute('aria-label', 'Eintrag bearbeiten');
  edit.appendChild(icon('pencil'));
  edit.addEventListener('click', () => {
    state.editingId = entry.id;
    rerender();
  });

  const del = document.createElement('button');
  del.className = 'icon-btn danger';
  del.title = 'Eintrag löschen';
  del.setAttribute('aria-label', 'Eintrag löschen');
  del.appendChild(icon('trash'));
  del.addEventListener('click', async () => {
    del.disabled = true;
    try {
      await api('/api/entries/' + entry.id, { method: 'DELETE' });
      // Der Mülleimer liegt direkt neben dem Stift und fragt nicht nach –
      // deshalb lässt sich das Löschen an derselben Stelle zurücknehmen.
      const list = entries || (state.today ? state.today.entries : []);
      const index = list.findIndex((e) => e.id === entry.id);
      state.undo = { entry, index: Math.max(0, index) };
      await refreshAll();
    } catch (err) {
      setMessage($('error-msg'), err.message);
      del.disabled = false;
    }
  });

  right.append(edit, del);
  row.append(left, right);
  return row;
}

function buildEditForm(entry, rerender = renderToday) {
  const form = document.createElement('form');
  form.className = 'edit-form';
  // Die Prüfung macht der Server (mit verständlichen Meldungen). Ohne das
  // würde der Browser das Absenden bei einem Wert, der nicht zum step passt,
  // stillschweigend verweigern – der Klick auf Speichern bliebe wirkungslos.
  form.noValidate = true;

  const descInput = document.createElement('input');
  descInput.type = 'text';
  descInput.value = entry.desc;
  descInput.maxLength = 500;

  const grid = document.createElement('div');
  grid.className = 'edit-grid';
  const fields = [
    { key: 'kcal', label: 'kcal', value: Math.round(entry.kcal) },
    {
      key: 'protein', label: 'Eiweiß (g)',
      value: entry.protein == null ? '' : Math.round(entry.protein),
    },
  ];
  const inputs = {};
  fields.forEach((field) => {
    const wrap = document.createElement('div');
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = field.label;
    const input = document.createElement('input');
    // type="text" statt "number": Safari verwirft bei type="number" eine
    // Eingabe mit Komma intern, das Feld zeigt sie noch, der Wert ist leer –
    // beim Eiweiß hätte das den Wert stillschweigend gelöscht.
    input.type = 'text';
    input.value = field.value;
    input.inputMode = 'decimal';
    input.autocomplete = 'off';
    input.maxLength = 7;
    wrap.append(label, input);
    grid.appendChild(wrap);
    inputs[field.key] = input;
  });
  const timeWrap = document.createElement('div');
  const timeLabel = document.createElement('label');
  timeLabel.className = 'field-label';
  timeLabel.textContent = 'Uhrzeit';
  const timeInput = document.createElement('input');
  timeInput.type = 'time';
  timeInput.value = entry.time;
  timeWrap.append(timeLabel, timeInput);
  grid.appendChild(timeWrap);
  // Verschiebt den Eintrag auf einen anderen Tag, etwa wenn das Abendessen
  // von gestern erst heute eingetragen wurde.
  const dateWrap = document.createElement('div');
  const dateLabel = document.createElement('label');
  dateLabel.className = 'field-label';
  dateLabel.textContent = 'Tag';
  const dateInput = document.createElement('input');
  dateInput.type = 'date';
  dateInput.value = entry.date;
  if (state.today) dateInput.max = state.today.date;
  dateWrap.append(dateLabel, dateInput);
  grid.appendChild(dateWrap);

  const actions = document.createElement('div');
  actions.className = 'edit-actions';
  const save = document.createElement('button');
  save.type = 'submit';
  save.className = 'small';
  save.textContent = 'Speichern';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'ghost small';
  cancel.textContent = 'Abbrechen';
  cancel.addEventListener('click', () => {
    state.editingId = null;
    rerender();
  });
  actions.append(save, cancel);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    save.disabled = true;
    try {
      await api('/api/entries/' + entry.id, {
        method: 'PATCH',
        body: JSON.stringify({
          desc: descInput.value.trim(),
          kcal: normalizeNumber(inputs.kcal.value),
          protein: normalizeNumber(inputs.protein.value) || null,
          time: timeInput.value,
          date: dateInput.value || undefined,
        }),
      });
      state.editingId = null;
      state.undo = null;
      await refreshAll();
    } catch (err) {
      setMessage($('error-msg'), err.message);
      save.disabled = false;
    }
  });

  form.append(descInput, grid, actions);
  return form;
}

function renderGoalProgress(totalKcal, totalProtein) {
  const goal = state.me && state.me.kcal_goal;
  const bar = $('today-bar');
  const note = $('today-note');
  if (!goal) {
    bar.hidden = true;
    note.className = 'card-note';
    note.textContent = 'Kein Tagesziel gesetzt';
    return;
  }
  const share = Math.min(100, Math.round((totalKcal / goal) * 100));
  const losing = losingWeight();
  bar.hidden = false;
  // Beim Zunehmen wechselt der Balken die Farbe, sobald das Ziel erreicht ist;
  // beim Abnehmen erst, wenn es überschritten wurde – dort ist genau auf dem
  // Ziel noch kein Fehltritt.
  bar.classList.toggle('over', losing ? totalKcal > goal : totalKcal >= goal);
  bar.firstElementChild.style.width = share + '%';
  const remaining = goal - totalKcal;
  if (losing) {
    if (remaining >= 0) {
      // Bewusst ohne "good": unter der Obergrenze zu liegen ist am Morgen noch
      // keine Leistung, das ist erst am Ende des Tages eine Aussage.
      note.className = 'card-note';
      note.textContent = `noch ${fmtKcal(remaining)} von ${fmtNum(goal)} übrig`;
    } else {
      note.className = 'card-note warn';
      note.textContent = `${fmtKcal(-remaining)} über dem Ziel`;
    }
  } else if (remaining > 0) {
    note.className = 'card-note';
    note.textContent = `noch ${fmtKcal(remaining)} bis ${fmtNum(goal)}`;
  } else {
    note.className = 'card-note good';
    note.textContent = `Ziel erreicht (+${fmtKcal(-remaining)})`;
  }

  const proteinGoal = state.me.protein_goal;
  const proteinNote = $('protein-note');
  if (proteinGoal) {
    proteinNote.className =
      'card-note' + (totalProtein >= proteinGoal ? ' good' : '');
    proteinNote.textContent =
      `Eiweiß heute: ${fmtNum(totalProtein)} / ${fmtNum(proteinGoal)} g`;
  } else if (totalProtein > 0) {
    proteinNote.className = 'card-note';
    proteinNote.textContent = `Eiweiß heute: ${fmtNum(totalProtein)} g`;
  } else {
    proteinNote.textContent = '';
  }
}

// --------------------------------------------------------------------------
// Schnellwahl aus den eigenen Einträgen
//
// Was in den letzten Wochen mehrfach eingetragen wurde, steht hier als Knopf,
// das Häufigste vorne. Die Werte stammen vom jüngsten Eintrag des Gerichts
// und werden direkt gespeichert – ohne KI-Schätzung, also ohne API-Aufruf.
// --------------------------------------------------------------------------

// Längere Beschreibungen passen nicht auf einen Knopf; der volle Text steht
// im title und landet unverändert im Tagebuch.
const PRESET_LABEL_MAX = 26;

function presetLabel(desc) {
  if (desc.length <= PRESET_LABEL_MAX) return desc;
  const cut = desc.slice(0, PRESET_LABEL_MAX);
  const space = cut.lastIndexOf(' ');
  return (space > 10 ? cut.slice(0, space) : cut).replace(/[\s,;:–-]+$/, '') + '…';
}

// Ausgeschaltet gibt es keine Anfrage: die Chips würden ohnehin nicht gezeigt.
const presetsEnabled = () => !state.me || state.me.show_presets !== false;

async function loadPresets() {
  if (!presetsEnabled()) {
    state.presets = null;
    renderPresets();
    return;
  }
  const data = await api('/api/presets');
  state.presets = data;
  renderPresets();
}

// So viele Knöpfe stehen immer da, der Rest liegt hinter dem Aufklapper. Zwei
// Zeilen sind der Kompromiss: die üblichen Gerichte sind einen Griff entfernt,
// ohne dass die Liste die Tageszahlen nach unten schiebt.
const PRESETS_COLLAPSED = 6;
const PRESETS_KEY = 'kcal-presets-open';

// Die Wahl gehört zum Gerät, nicht zum Konto – und localStorage kann werfen
// (privater Modus, blockierte Cookies), dann bleibt es beim eingeklappten
// Zustand statt dass die Chips ganz fehlen.
function presetsOpen(value) {
  try {
    if (value === undefined) return localStorage.getItem(PRESETS_KEY) === '1';
    localStorage.setItem(PRESETS_KEY, value ? '1' : '0');
  } catch (err) {
    /* ignorieren */
  }
  return Boolean(value);
}

function buildPresetChip(preset) {
  const chip = document.createElement('button');
  chip.className = 'chip';
  const protein = preset.protein == null ? '' : `, ${fmtNum(preset.protein)} g Eiweiß`;
  chip.title = `${preset.desc} · ${fmtKcal(preset.kcal)}${protein}`
    + ` · ${preset.count}× eingetragen – wird ohne neue Schätzung eingetragen`;
  chip.append(document.createTextNode(presetLabel(preset.desc)));
  const kcal = document.createElement('span');
  kcal.className = 'chip-kcal';
  kcal.textContent = fmtNum(preset.kcal);
  chip.appendChild(kcal);
  chip.addEventListener('click', () =>
    addEntry(
      { desc: preset.desc, kcal: preset.kcal, protein: preset.protein },
      chip,
      true
    )
  );
  return chip;
}

function renderPresets() {
  const container = $('presets');
  container.textContent = '';
  container.hidden = !presetsEnabled();
  if (!state.presets || container.hidden) return;
  const presets = state.presets.presets;
  if (!presets.length) {
    // Ohne Hinweis sähe die leere Stelle wie ein Ladefehler aus.
    const hint = document.createElement('p');
    hint.className = 'chips-empty';
    hint.textContent =
      `Hier erscheinen deine häufigsten Einträge, sobald du etwas ` +
      `${state.presets.min_count}-mal eingetragen hast.`;
    container.appendChild(hint);
    return;
  }
  const open = presetsOpen();
  const shown = open ? presets : presets.slice(0, PRESETS_COLLAPSED);
  shown.forEach((preset) => container.appendChild(buildPresetChip(preset)));

  const hidden = presets.length - PRESETS_COLLAPSED;
  if (hidden <= 0) return;
  const toggle = document.createElement('button');
  toggle.className = 'chip chip-toggle';
  toggle.textContent = open ? 'weniger' : `+${hidden} mehr`;
  toggle.setAttribute('aria-expanded', String(open));
  toggle.addEventListener('click', () => {
    presetsOpen(!open);
    renderPresets();
  });
  container.appendChild(toggle);
}

// --------------------------------------------------------------------------
// Verlaufsdiagramm
// --------------------------------------------------------------------------

let summaryRequest = 0;

async function loadSummary() {
  const params = new URLSearchParams({ days: String(state.range) });
  if (state.end) params.set('end', state.end);
  // Antworten können in anderer Reihenfolge zurückkommen als die Anfragen
  // gestellt wurden. Ohne diese Prüfung landen die Balken eines Zeitraums
  // unter der Überschrift und dem Durchschnitt eines anderen.
  const ticket = ++summaryRequest;
  const data = await api('/api/summary?' + params.toString());
  if (ticket !== summaryRequest) return;
  state.summary = data;
  renderSummary();
}

function renderSummary() {
  const data = state.summary;
  const chart = $('week-chart');
  chart.textContent = '';
  chart.classList.toggle('weight', state.metric === 'weight');

  // Die Kachel zeigt immer die Kalorien, egal welches Diagramm gewählt ist.
  // Der laufende Tag zählt nicht mit: morgens um zehn würde er den Schnitt
  // mit einem halben Tag nach unten ziehen.
  const withToday = data.series.some((d) => d.date === data.today);
  const logged = data.series.filter((d) => d.entries > 0 && d.date !== data.today);
  const average = logged.length
    ? logged.reduce((sum, d) => sum + d.total, 0) / logged.length
    : 0;
  $('avg-label').textContent = withToday
    ? 'Ø erfasste Tage, ohne heute'
    : `Ø erfasste Tage (${state.range})`;
  $('week-avg').textContent = fmtKcal(average);

  $('chart-title').textContent = state.end
    ? `${state.range} Tage bis ${dateLong(data.end)}`
    : `Letzte ${state.range} Tage`;
  $('chart-next').disabled = !state.end;

  // Die Höhe kommt aus dem CSS (.week-chart: 140px, auf dem Desktop füllt es
  // die freie Fensterhöhe, mindestens 220px),
  // davon gehen .week-total (12) + 2x gap (10) + .week-label (15) ab. Ist der
  // Wert größer, staucht Flexbox die hohen Balken auf dieselbe Höhe. 140 gilt,
  // solange das Diagramm ausgeblendet ist und keine eigene Höhe hat.
  const fullHeight = chart.clientHeight || 140;
  const chartHeight = fullHeight - 37;
  const barBaseline = 20; // Abstand Balkenunterkante zum Diagrammboden
  // Ob Zahlen und Datumsangaben Platz haben, hängt nicht an der Anzahl der
  // Tage, sondern an der Breite pro Spalte: 14 Tage sind auf dem Handy zu eng
  // (18 px Spalte gegen 27 px Zahl), auf dem Desktop reichlich. Deshalb hier
  // ausrechnen statt eine feste Grenze zu raten.
  const columns = data.series.length;
  // clientWidth statt getBoundingClientRect: auf großen Bildschirmen ist die
  // Seite per CSS-zoom vergrößert, und getBoundingClientRect liefert dann die
  // vergrößerte Breite – die Spalten würden doppelt skaliert.
  const chartWidth = chart.clientWidth || 335;
  const widthPerColumn = (gap) => (chartWidth - (columns - 1) * gap) / columns;
  const dense = widthPerColumn(6) < 28; // Platz für die Zahl über dem Balken?
  const gap = dense ? 2 : 6;
  chart.style.gap = gap + 'px';
  const perColumn = widthPerColumn(gap);
  // Kleinster Abstand, bei dem die Datumsangaben nicht zusammenlaufen.
  const labelEvery = [1, 2, 5].find((n) => n * perColumn >= 20) || 5;

  const geo = {
    chart, fullHeight, chartHeight, barBaseline, chartWidth, dense, gap, perColumn,
    // Tagesbeschriftung unter der Spalte, für Balken und Punkte gleich.
    label(day, index) {
      const label = document.createElement('span');
      label.className = 'week-label' + (day.date === data.today ? ' today' : '');
      const fromEnd = data.series.length - 1 - index;
      if (fromEnd % labelEvery === 0) {
        label.textContent = dense
          ? new Date(day.date + 'T00:00:00').getDate()
          : weekdayShort(day.date);
      }
      return label;
    },
  };

  if (state.metric === 'weight') renderWeightChart(data, geo);
  else renderBarChart(data, geo, state.metric === 'protein');

  if (state.selectedDay) renderDayDetail();
  // Der gewählte Tag ist auch im Kalender markiert.
  renderCalendar();
}

// Kalorien und Eiweiß: dieselben Balken, nur Wert, Ziel und Einheit wechseln.
function renderBarChart(data, geo, protein) {
  const { chart, chartHeight, barBaseline, dense, gap, perColumn } = geo;

  // Jeder Tag bringt Ziel und Zielrichtung mit, die an ihm galten. Eine
  // Änderung wirkt so erst ab dem Tag, an dem sie gemacht wurde, und färbt
  // ältere Balken nicht nachträglich um.
  const value = (day) => (protein ? day.protein : day.total);
  const dayGoal = (day) => (protein ? day.protein_goal : day.kcal_goal) || 0;
  // Das Eiweißziel ist immer eine Untergrenze, auch auf einem Konto, das
  // abnehmen will – die Zielrichtung gilt nur für die Kalorien.
  const dayLosing = (day) => !protein && day.goal_direction === 'lose';
  const goalText = (segment) => protein
    ? `Ziel ${fmtNum(segment.goal)} g`
    : (segment.losing ? 'Grenze ' : 'Ziel ') + fmtNum(segment.goal);
  const maxValue = Math.max(...data.series.map((d) => Math.max(value(d), dayGoal(d))), 1);

  // Aufeinanderfolgende Tage mit demselben Ziel und derselben Richtung teilen
  // sich ein Stück der Ziellinie. Ohne Änderung im Zeitraum ist das eine
  // durchgehende Linie.
  const segments = [];
  data.series.forEach((day, index) => {
    const last = segments[segments.length - 1];
    if (last && last.goal === dayGoal(day) && last.losing === dayLosing(day)) last.to = index;
    else segments.push({ goal: dayGoal(day), losing: dayLosing(day), from: index, to: index });
  });
  const current = segments[segments.length - 1];
  const legend = $('chart-goal');
  if (current && current.goal) {
    legend.hidden = false;
    legend.textContent = goalText(current);
  } else {
    // Ohne Eiweißziel sagt die Legende, warum kein Balken grün wird. Bei den
    // Kalorien gibt es immer ein Ziel, bis auf ganz neue Konten.
    legend.hidden = !protein;
    legend.textContent = protein ? 'kein Eiweißziel' : '';
  }

  segments.forEach((segment, index) => {
    if (!segment.goal) return;
    const line = document.createElement('div');
    line.className = 'goal-line';
    // Gleiche Grundlinie und gleicher Maßstab wie die Balken, sonst markiert
    // die Linie einen anderen Wert als den, der daneben steht.
    line.style.bottom = barBaseline + (segment.goal / maxValue) * chartHeight + 'px';
    if (segments.length > 1) {
      const span = segment.to - segment.from + 1;
      line.style.left = segment.from * (perColumn + gap) + 'px';
      line.style.right = 'auto';
      line.style.width = span * perColumn + (span - 1) * gap + 'px';
    }
    // Das letzte Stück (das aktuellste Ziel im Zeitraum) steht als Legende
    // unter dem Diagramm, wo es keine Tageszahl verdecken kann. Ältere Stücke
    // nur auf der Linie und nur, wenn sie breit genug sind.
    const width = (segment.to - segment.from + 1) * (perColumn + gap);
    if (index < segments.length - 1 && width >= 70) {
      const tag = document.createElement('span');
      tag.textContent = goalText(segment);
      line.appendChild(tag);
    }
    chart.appendChild(line);
  });

  data.series.forEach((day, index) => {
    const amount = value(day);
    const col = document.createElement('button');
    col.type = 'button';
    col.className = 'week-col' + (state.selectedDay === day.date ? ' selected' : '');
    col.title = `${dateLong(day.date)}: ` +
      (protein ? `${fmtNum(amount)} g Eiweiß` : fmtKcal(amount));
    col.setAttribute('aria-label', col.title);

    const total = document.createElement('span');
    total.className = 'week-total';
    total.textContent = !dense && amount ? fmtNum(amount) : '';

    const bar = document.createElement('div');
    bar.className = 'week-bar';
    const goal = dayGoal(day);
    if (goal && dayLosing(day)) {
      // Ohne Einträge ist ein Tag nicht "unter der Grenze geblieben", sondern
      // unbekannt – der bliebe sonst grün, obwohl nichts erfasst wurde.
      if (day.entries > 0) bar.classList.add(amount > goal ? 'over' : 'reached');
    } else if (goal && amount >= goal) {
      bar.classList.add('reached');
    }
    bar.style.height = Math.max(4, Math.round((amount / maxValue) * chartHeight)) + 'px';

    col.append(total, bar, geo.label(day, index));
    col.addEventListener('click', () => selectDay(day.date));
    chart.appendChild(col);
  });

  const emptyDays = data.series.length - data.series.filter((d) => d.entries > 0).length;
  $('chart-note').textContent = emptyDays
    ? `Tippe auf einen Balken für die Details. ${emptyDays} Tag${emptyDays === 1 ? '' : 'e'} ohne Einträge.`
    : 'Tippe auf einen Balken, um den Tag zu sehen.';
}

// Gewicht: eine Linie durch die Messungen, ein Punkt pro gewogenem Tag. Kein
// Ziel, also auch kein Grün – die Farbe bleibt dem erreichten Ziel vorbehalten.
function renderWeightChart(data, geo) {
  const { chart, fullHeight, chartHeight, barBaseline, chartWidth, dense, gap, perColumn } = geo;
  const measured = data.series.filter((d) => d.kg != null);

  // Die Skala beginnt nicht bei null (dann wäre jede Linie flach), umfasst
  // aber mindestens 2 kg: sonst sähe eine Schwankung um 100 g aus wie ein
  // Absturz. Die Grenzen liegen auf halben Kilogramm.
  let lo = 0;
  let hi = 2;
  if (measured.length) {
    const values = measured.map((d) => d.kg);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(2, Math.ceil((max - min + 0.4) * 2) / 2);
    lo = Math.floor(((min + max) / 2 - span / 2) * 2) / 2;
    hi = Math.max(lo + span, Math.ceil((max + 0.2) * 2) / 2);
  }
  const offset = (kg) => barBaseline + ((kg - lo) / (hi - lo)) * chartHeight;

  // Hilfslinien bei ganzen Kilogramm, bei großer Spanne bei jedem zweiten.
  const step = hi - lo > 6 ? 2 : 1;
  if (measured.length) {
    for (let kg = Math.ceil(lo / step) * step; kg <= hi; kg += step) {
      const line = document.createElement('div');
      line.className = 'weight-grid';
      line.style.bottom = offset(kg) + 'px';
      const tag = document.createElement('span');
      tag.textContent = `${kg} kg`;
      line.appendChild(tag);
      chart.appendChild(line);
    }
  }

  if (measured.length > 1) {
    const x = (index) => index * (perColumn + gap) + perColumn / 2;
    const points = [];
    data.series.forEach((day, index) => {
      if (day.kg == null) return;
      const y = fullHeight - offset(day.kg);
      points.push(`${points.length ? 'L' : 'M'}${x(index).toFixed(1)} ${y.toFixed(1)}`);
    });
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'weight-line');
    svg.setAttribute('width', String(chartWidth));
    svg.setAttribute('height', String(fullHeight));
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', points.join(' '));
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-width', '1.75');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(path);
    chart.appendChild(svg);
  }

  const lastMeasured = measured.length ? measured[measured.length - 1].date : null;
  data.series.forEach((day, index) => {
    const selected = state.selectedDay === day.date;
    const col = document.createElement('button');
    col.type = 'button';
    col.className = 'week-col' + (selected ? ' selected' : '') + (day.kg == null ? ' no-dot' : '');
    col.title = `${dateLong(day.date)}: ` +
      (day.kg == null ? 'kein Gewicht eingetragen' : `${fmtKg(day.kg)} kg`);
    col.setAttribute('aria-label', col.title);

    if (day.kg != null) {
      const bottom = offset(day.kg);
      const dot = document.createElement('span');
      dot.className = 'weight-dot';
      dot.style.bottom = bottom + 'px';
      // Bei engen Spalten liefen die Zahlen ineinander: dann nur die letzte
      // Messung und der ausgewählte Tag.
      const text = document.createElement('span');
      text.className = 'weight-value';
      // Die Zahl ist breiter als eine schmale Spalte. Mittig über dem Punkt
      // stünde sie am ersten und letzten Tag über den Diagrammrand hinaus,
      // dort schließt sie deshalb bündig mit der Spalte ab.
      if (perColumn < 44 && index === 0) text.classList.add('at-start');
      if (perColumn < 44 && index === data.series.length - 1) text.classList.add('at-end');
      text.style.bottom = bottom + 8 + 'px';
      text.textContent = !dense || selected || day.date === lastMeasured ? fmtKg(day.kg) : '';
      col.append(dot, text);
    }
    col.append(geo.label(day, index));
    col.addEventListener('click', () => selectDay(day.date));
    chart.appendChild(col);
  });

  const missing = data.series.length - measured.length;
  $('chart-note').textContent = !measured.length
    ? 'In diesem Zeitraum wurde kein Gewicht eingetragen.'
    : 'Tippe auf einen Tag für den Wert.' +
      (missing ? ` ${missing} Tag${missing === 1 ? '' : 'e'} ohne Messung.` : '');
  const legend = $('chart-goal');
  legend.hidden = measured.length < 2;
  legend.textContent = legend.hidden
    ? ''
    : `${fmtKgDelta(measured[measured.length - 1].kg - measured[0].kg)} kg im Zeitraum`;
}

async function selectDay(date) {
  if (state.selectedDay === date) {
    state.selectedDay = null;
    $('day-detail').hidden = true;
    renderSummary();
    return;
  }
  state.selectedDay = date;
  renderSummary();
  await renderDayDetail(true);
}

async function renderDayDetail(reload = false) {
  const box = $('day-detail');
  if (!state.selectedDay) {
    box.hidden = true;
    return;
  }
  const wanted = state.selectedDay;
  box.hidden = false;
  $('day-detail-date').textContent = dateLong(wanted);
  // Nachtragen nur für vergangene Tage: heute geht das über das Eingabefeld
  // ohnehin, und für einen Tag, der schon nachgetragen wird, braucht es den
  // Link nicht noch einmal.
  const past = !!state.summary && wanted < state.summary.today;
  $('day-detail-add').hidden =
    state.metric === 'weight' || !past || state.backfill === wanted;
  if (state.metric === 'weight') {
    renderWeightDetail(wanted);
    return;
  }
  if (reload || !state.dayCache || state.dayCache.date !== wanted) {
    $('day-detail-list').textContent = 'Lade…';
    let loaded;
    try {
      loaded = await api('/api/entries?date=' + encodeURIComponent(wanted));
    } catch (err) {
      if (state.selectedDay === wanted) $('day-detail-list').textContent = err.message;
      return;
    }
    // Während des Ladens kann ein anderer Tag angeklickt worden sein – dessen
    // Anzeige darf nicht mit diesen Daten überschrieben werden.
    if (state.selectedDay !== wanted) return;
    state.dayCache = loaded;
  }
  // Dieselbe Liste für Kalorien und Eiweiß, nur die rechte Spalte wechselt.
  const protein = state.metric === 'protein';
  const entries = state.dayCache.entries;
  const total = entries.reduce((sum, e) => sum + ((protein ? e.protein : e.kcal) || 0), 0);
  $('day-detail-total').textContent = protein ? `${fmtNum(total)} g Eiweiß` : fmtKcal(total);
  const list = $('day-detail-list');
  list.textContent = '';
  const undo = state.undo && state.undo.entry.date === wanted ? state.undo : null;
  if (!entries.length && !undo) {
    list.appendChild(detailEmpty('An diesem Tag wurde nichts eingetragen.'));
    return;
  }
  // Vergangene Tage lassen sich wie heute bearbeiten und löschen – wer
  // nachträgt, muss sich auch vertippen dürfen. Heute steht schon in der
  // Liste daneben, dort bleibt es bei der knappen Übersicht.
  if (past) {
    const rerender = () => renderDayDetail();
    const rows = entries.map((entry) =>
      state.editingId === entry.id
        ? buildEditForm(entry, rerender)
        : buildEntryRow(entry, rerender, entries)
    );
    if (undo) rows.splice(Math.min(undo.index, rows.length), 0, buildUndoRow(undo.entry));
    rows.forEach((row) => list.appendChild(row));
    return;
  }
  entries.forEach((entry) => {
    let right = fmtNum(entry.kcal) + ' kcal';
    if (protein) right = entry.protein == null ? '–' : fmtNum(entry.protein) + ' g';
    list.appendChild(detailRow(`${entry.time} · ${entry.desc}`, right));
  });
}

// Gewicht braucht keine Anfrage: der Wert steht schon in der Zusammenfassung,
// die vorige Messung in der Gewichtsliste – auch wenn sie vor dem Zeitraum liegt.
function renderWeightDetail(date) {
  const day = state.summary && state.summary.series.find((d) => d.date === date);
  const kg = day ? day.kg : null;
  $('day-detail-total').textContent = kg == null ? '' : `${fmtKg(kg)} kg`;
  const list = $('day-detail-list');
  list.textContent = '';
  if (kg == null) {
    list.appendChild(detailEmpty('An diesem Tag wurde kein Gewicht eingetragen.'));
    return;
  }
  const previous = (state.weights || []).find((w) => w.date < date);
  if (!previous) {
    list.appendChild(detailEmpty('Deine erste Messung.'));
    return;
  }
  list.append(
    detailRow(`Vorige Messung · ${dateLong(previous.date)}`, `${fmtKg(previous.kg)} kg`),
    detailRow('Veränderung', `${fmtKgDelta(kg - previous.kg)} kg`)
  );
}

function detailRow(leftText, rightText) {
  const row = document.createElement('div');
  row.className = 'day-detail-item';
  const left = document.createElement('span');
  left.textContent = leftText;
  const right = document.createElement('span');
  right.textContent = rightText;
  row.append(left, right);
  return row;
}

function detailEmpty(text) {
  const empty = document.createElement('div');
  empty.className = 'empty-state';
  empty.textContent = text;
  return empty;
}

// --------------------------------------------------------------------------
// Kalender
// --------------------------------------------------------------------------

// Mindestgröße einer Zelle und Abstand in px. Daraus ergibt sich, wie viele
// Wochen in die Breite passen: auf dem Handy etwa ein halbes Jahr, in der
// schmalen Desktop-Spalte etwas weniger, höchstens das ganze geladene Jahr.
const CAL_CELL = 13;
const CAL_GAP = 3;
const CAL_LABEL = 22;

async function loadCalendar() {
  state.calendar = await api('/api/calendar');
  renderCalendar();
}

// Stufe eines Tages. Beim Zunehmen wird es mit der Nähe zum Ziel grüner, voll
// grün erst am Ziel. Beim Abnehmen gibt es keine Abstufung: unter der Grenze
// ist erreicht, darüber bernsteinfarben – wie die Balken im Diagramm. Ohne
// Ziel zeigt die Zelle nur, dass etwas erfasst wurde.
function calLevel(day) {
  if (!day || !day.entries) return '';
  const goal = day.kcal_goal;
  if (!goal) return 'l2';
  if (day.goal_direction === 'lose') return day.total > goal ? 'over' : 'reached';
  const share = day.total / goal;
  if (share >= 1) return 'reached';
  return share >= 0.75 ? 'l3' : share >= 0.5 ? 'l2' : 'l1';
}

function renderCalendar() {
  const data = state.calendar;
  const grid = $('cal-grid');
  const width = grid.clientWidth;
  if (!data || !width) return;
  const weeks = Math.max(8, Math.min(53,
    Math.floor((width - CAL_LABEL + CAL_GAP) / (CAL_CELL + CAL_GAP))));
  grid.style.setProperty('--weeks', String(weeks));
  const byDate = new Map(data.days.map((d) => [d.date, d]));

  // Montag oben, die letzte Spalte ist die laufende Woche.
  const today = new Date(data.today + 'T00:00:00');
  const start = new Date(today);
  start.setDate(start.getDate() - ((today.getDay() + 6) % 7) - (weeks - 1) * 7);

  const cells = [];
  const place = (el, column, row) => {
    el.style.gridColumn = String(column);
    el.style.gridRow = String(row);
    cells.push(el);
  };
  ['Mo', '', 'Mi', '', 'Fr', '', ''].forEach((text, index) => {
    if (!text) return;
    const label = document.createElement('span');
    label.className = 'cal-wd';
    label.textContent = text;
    place(label, 1, index + 2);
  });

  const monthLabel = (date, week) => {
    const month = document.createElement('span');
    month.className = 'cal-month';
    month.textContent = date.toLocaleDateString('de-DE', { month: 'short' }).replace('.', '');
    place(month, week + 2, 1);
  };
  let firstMonthWeek = null;
  for (let week = 0; week < weeks; week += 1) {
    for (let weekday = 0; weekday < 7; weekday += 1) {
      const date = new Date(start);
      date.setDate(start.getDate() + week * 7 + weekday);
      if (date > today) break;
      // Monatsname über der Woche, in der der Monat beginnt.
      if (date.getDate() === 1) {
        monthLabel(date, week);
        if (firstMonthWeek === null) firstMonthWeek = week;
      }
      const iso = isoLocal(date);
      const day = byDate.get(iso);
      const cell = document.createElement('button');
      cell.type = 'button';
      cell.className = ['cal-cell', calLevel(day),
        iso === data.today ? 'today' : '',
        iso === state.selectedDay ? 'selected' : ''].filter(Boolean).join(' ');
      cell.title = `${dateLong(iso)}: ` + (day
        ? fmtKcal(day.total) + (day.kcal_goal ? ` von ${fmtNum(day.kcal_goal)}` : '')
        : 'nichts eingetragen');
      cell.setAttribute('aria-label', cell.title);
      cell.addEventListener('click', async () => {
        await selectDay(iso);
        // Auf dem Handy steht die Tageskarte über dem Kalender.
        if (!$('day-detail').hidden) {
          $('day-detail').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
      });
      place(cell, week + 2, weekday + 2);
    }
  }
  // Die erste Spalte bekommt ihren angefangenen Monat nur, wenn der nächste
  // Name nicht gleich danach folgt – sonst stünden beide übereinander.
  if (firstMonthWeek === null || firstMonthWeek >= 3) monthLabel(start, 0);
  grid.replaceChildren(...cells);

  // Serie: Tage in Folge mit Einträgen bis heute. Ist heute noch leer, zählt
  // die Serie bis gestern – der Tag ist ja noch nicht vorbei.
  let streak = 0;
  const cursor = new Date(today);
  if (!byDate.has(data.today)) cursor.setDate(cursor.getDate() - 1);
  while (byDate.has(isoLocal(cursor))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  $('cal-streak').textContent = streak > 1 ? `${streak} Tage in Folge erfasst` : '';

  const recent = [];
  for (let i = 0; i < 30; i += 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);
    recent.push(byDate.get(isoLocal(date)));
  }
  const logged = recent.filter(Boolean).length;
  const reached = recent.filter((d) => calLevel(d) === 'reached').length;
  $('cal-stats').textContent =
    `Letzte 30 Tage: ${logged} erfasst` + (reached ? `, ${reached} im Ziel` : '');

  renderCalendarLegend();
}

function renderCalendarLegend() {
  const legend = $('cal-legend');
  const parts = losingWeight()
    ? [['', 'nichts'], ['reached', 'im Ziel'], ['over', 'drüber']]
    : [[null, 'wenig'], [''], ['l1'], ['l2'], ['l3'], ['reached'], [null, 'Ziel']];
  legend.replaceChildren(...parts.flatMap(([level, text]) => {
    const out = [];
    if (level !== null) {
      const swatch = document.createElement('span');
      swatch.className = 'cal-swatch' + (level ? ' ' + level : '');
      out.push(swatch);
    }
    if (text) {
      const label = document.createElement('span');
      label.textContent = text;
      out.push(label);
    }
    return out;
  }));
}

function shiftRange(direction) {
  const base = new Date((state.end || state.summary.today) + 'T00:00:00');
  base.setDate(base.getDate() + direction * state.range);
  const todayDate = new Date(state.summary.today + 'T00:00:00');
  state.end = base >= todayDate ? null : isoLocal(base);
  state.selectedDay = null;
  $('day-detail').hidden = true;
  loadSummary().catch((err) => setMessage($('error-msg'), err.message));
}

// --------------------------------------------------------------------------
// Gewicht
// --------------------------------------------------------------------------

async function loadWeights() {
  const data = await api('/api/weights');
  state.weights = data.entries;
  const trend = $('weight-trend');
  if (!data.latest) {
    trend.textContent = 'Noch kein Gewicht erfasst';
    return;
  }
  let text = `${data.latest.kg.toLocaleString('de-DE')} kg am ${dateLong(data.latest.date)}`;
  if (data.trend) {
    const sign = data.trend.delta > 0 ? '+' : '';
    text += ` · ${sign}${data.trend.delta.toLocaleString('de-DE')} kg seit ${dateLong(data.trend.from_date)}`;
  }
  trend.textContent = text;
}

// Deutsche Eingabe mit Komma in das Format bringen, das die API erwartet.
const normalizeNumber = (raw) => String(raw ?? '').trim().replace(',', '.');

async function saveWeight() {
  const input = $('weight-input');
  const value = normalizeNumber(input.value);
  if (!value) {
    setMessage($('weight-msg'), 'Bitte gib dein Gewicht in kg ein.');
    return;
  }
  $('weight-btn').disabled = true;
  try {
    await api('/api/weights', { method: 'POST', body: JSON.stringify({ kg: value }) });
    input.value = '';
    setMessage($('weight-msg'), 'Gewicht gespeichert.', 'ok');
    // Die Zusammenfassung trägt das Gewicht pro Tag für das Diagramm.
    await Promise.all([loadWeights(), loadSummary()]);
  } catch (err) {
    setMessage($('weight-msg'), err.message);
  } finally {
    $('weight-btn').disabled = false;
  }
}

// --------------------------------------------------------------------------
// KI-Einschätzung
// --------------------------------------------------------------------------

async function fetchCoach(refresh) {
  const call = () =>
    refresh ? api('/api/coach/refresh', { method: 'POST' }) : api('/api/coach');
  try {
    return await call();
  } catch (err) {
    if (!(err instanceof GatewayError)) throw err;
    // Einmal still wiederholen: meist war nur der Container kurz weg oder die
    // Verbindung gestört, und die Einschätzung kommt beim zweiten Mal.
    await new Promise((resolve) => setTimeout(resolve, 2000));
    return call();
  }
}

// Ein- und Ausklappen der Einschätzung. Die Wahl gehört zum Gerät, wie die des
// Diagramms. Die Klasse sitzt an .dash-today statt an der Karte: loadCoach
// setzt deren className bei jeder Auswertung neu, und auf dem Desktop ordnet
// das Raster beim Einklappen auch die Kacheln daneben um.
const COACH_COLLAPSED_KEY = 'kcal-coach-collapsed';

function setCoachCollapsed(collapsed, remember = true) {
  document.querySelector('.dash-today').classList.toggle('coach-collapsed', collapsed);
  $('coach-toggle').setAttribute('aria-expanded', String(!collapsed));
  if (!remember) return;
  try {
    if (collapsed) localStorage.setItem(COACH_COLLAPSED_KEY, '1');
    else localStorage.removeItem(COACH_COLLAPSED_KEY);
  } catch (err) {
    /* ignorieren */
  }
}

function storedCoachCollapsed() {
  try {
    return localStorage.getItem(COACH_COLLAPSED_KEY) === '1';
  } catch (err) {
    return false;
  }
}

async function loadCoach(refresh = false) {
  const box = $('coach');
  const refreshBtn = $('coach-refresh');
  // Beim ersten Laden ist die Karte sonst einige Sekunden lang leer.
  if (!$('coach-headline').textContent) $('coach-headline').textContent = 'Wird ausgewertet…';
  box.hidden = false;
  refreshBtn.disabled = true;
  if (refresh) $('coach-stamp').textContent = 'Wird ausgewertet…';
  try {
    const data = await fetchCoach(refresh);
    // Die Statuswerte beschreiben die Lage zum Ziel, nicht deren Bewertung.
    // Welche Lage gut ist, entscheidet die Richtung – deshalb steht sie als
    // eigene Klasse daneben und das CSS dreht die Farben.
    box.className =
      'coach ' + (losingWeight() ? 'lose ' : '') + (data.status || '');
    setCoachIcon(COACH_ICON[data.status] || 'dash');
    $('coach-headline').textContent = data.headline || '';
    $('coach-message').textContent = data.message || '';
    const tips = $('coach-tips');
    tips.textContent = '';
    tips.hidden = !(data.tips && data.tips.length);
    (data.tips || []).forEach((tip) => {
      const li = document.createElement('li');
      li.textContent = tip;
      tips.appendChild(li);
    });
    // stale: Gemini war nicht erreichbar, der Server hat stattdessen die
    // letzte gespeicherte Einschätzung geschickt. Sie kennt die neuesten
    // Einträge noch nicht – das muss dabeistehen.
    $('coach-stamp').textContent = data.stale
      ? 'Ältere Einschätzung – ' + (data.notice || 'Aktualisierung gerade nicht möglich.')
      : data.cached ? 'Gespeicherte Einschätzung' : 'Frisch ausgewertet';
    refreshBtn.hidden = data.status === 'no_goal' || data.status === 'no_data';
  } catch (err) {
    box.className = 'coach error';
    setCoachIcon('alert');
    $('coach-headline').textContent = 'Einschätzung nicht möglich';
    $('coach-message').textContent = err.message;
    $('coach-stamp').textContent = '';
    $('coach-tips').hidden = true;
    refreshBtn.hidden = false;
  } finally {
    refreshBtn.disabled = false;
  }
}

// --------------------------------------------------------------------------
// Einstellungen
// --------------------------------------------------------------------------

async function loadMe() {
  state.me = await api('/api/me');
  $('settings-account').textContent = 'Angemeldet als ' + state.me.email;
}

function fillDayStartOptions() {
  const select = $('day-start-input');
  if (select.options.length) return;
  for (let hour = 0; hour <= 11; hour++) {
    const option = document.createElement('option');
    option.value = String(hour);
    option.textContent =
      String(hour).padStart(2, '0') + ':00' + (hour === 0 ? ' (Mitternacht)' : '');
    select.appendChild(option);
  }
}

// Der Hinweis unter dem Tagesziel erklärt, in welche Richtung das Ziel vom
// Verbrauch abweichen soll. Er hängt an der Auswahl darüber und ändert sich
// deshalb sofort mit, nicht erst nach dem Speichern.
function renderGoalHint() {
  $('goal-hint').textContent =
    $('goal-direction-input').value === 'lose'
      ? 'Zum Abnehmen liegt das Ziel unter deinem Verbrauch – typisch sind 300–500 kcal Defizit pro Tag.'
      : 'Zum Zunehmen liegt das Ziel über deinem Verbrauch – typisch sind 300–500 kcal Überschuss pro Tag.';
}

function fillSettings() {
  fillDayStartOptions();
  $('goal-direction-input').value = state.me.goal_direction || 'gain';
  renderGoalHint();
  $('goal-input').value = state.me.kcal_goal ? Math.round(state.me.kcal_goal) : '';
  $('protein-goal-input').value = state.me.protein_goal ? Math.round(state.me.protein_goal) : '';
  $('day-start-input').value = String(state.me.day_start_hour || 0);
  $('name-input').value = state.me.display_name || '';
  $('presets-input').value = presetsEnabled() ? 'on' : 'off';
  $('theme-input').value = Theme.get();
  fillAiModelOptions();
  setMessage($('settings-msg'), '');
}

// Die Einstellungen sind eine eigene Ansicht, die die Hauptansicht ersetzt,
// kein Dialog darüber. Das Öffnen legt einen Verlaufseintrag an: so führen die
// Zurück-Geste des Handys und die Zurück-Taste des Browsers zur Hauptansicht
// zurück, statt die App zu verlassen.
const SETTINGS_STATE = 'settings';
const inSettingsHistory = () => (history.state && history.state.view) === SETTINGS_STATE;
let mainScrollY = 0;

function showSettingsView(show) {
  if (show === !$('settings-view').hidden) return;
  // Den Fokus nur mitnehmen, wenn er in der Ansicht lag, die gleich verschwindet –
  // sonst landet er nach Tastaturbedienung im Nichts. Nach einem Tippen oder
  // Klick bleibt er, wo er ist.
  const leaving = show ? $('main-view') : $('settings-view');
  const hadFocus = leaving.contains(document.activeElement);
  // Die Hauptansicht soll dort weitergehen, wo sie verlassen wurde, die
  // Einstellungen beginnen immer oben.
  if (show) mainScrollY = window.scrollY;
  $('main-view').hidden = show;
  $('settings-view').hidden = !show;
  window.scrollTo(0, show ? 0 : mainScrollY);
  if (hadFocus) (show ? $('settings-back') : $('settings-btn')).focus({ preventScroll: true });
}

function openSettings() {
  fillSettings();
  history.pushState({ view: SETTINGS_STATE }, '');
  showSettingsView(true);
}

// Erst umschalten, dann den eigenen Verlaufseintrag zurücknehmen. history.back()
// wirkt erst mit dem popstate, bis dahin meldet history.state noch die
// Einstellungen. Ein zweiter Aufruf in dieser Lücke – etwa Zurück-Pfeil während
// des Speicherns, danach schließt das Speichern selbst – ginge sonst einen
// Schritt weiter zurück, aus der App heraus. Deshalb zählt die sichtbare Ansicht.
function closeSettings() {
  if ($('settings-view').hidden) return;
  showSettingsView(false);
  if (inSettingsHistory()) history.back();
}

// Nur Admin-Konten bekommen die Modellliste von /api/me. Für alle anderen
// bleibt das Feld verborgen – und der Server lehnt eine Wahl ohnehin ab.
function fillAiModelOptions() {
  const field = $('ai-model-field');
  const select = $('ai-model-input');
  field.hidden = !state.me.is_admin;
  if (!state.me.is_admin) return;
  select.textContent = '';
  (state.me.ai_models || []).forEach((model) => {
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = model.label + (model.available ? '' : ' – ANTHROPIC_API_KEY fehlt');
    option.disabled = !model.available;
    select.appendChild(option);
  });
  select.value = state.me.ai_model || 'gemini';
}

async function saveSettings() {
  const btn = $('settings-save');
  btn.disabled = true;
  try {
    state.me = Object.assign(
      state.me,
      await api('/api/me', {
        method: 'PATCH',
        body: JSON.stringify({
          goal_direction: $('goal-direction-input').value,
          kcal_goal: $('goal-input').value.trim() || null,
          protein_goal: $('protein-goal-input').value.trim() || null,
          day_start_hour: $('day-start-input').value,
          display_name: $('name-input').value.trim(),
          show_presets: $('presets-input').value === 'on',
          ...(state.me.is_admin ? { ai_model: $('ai-model-input').value } : {}),
        }),
      })
    );
  } catch (err) {
    setMessage($('settings-msg'), err.message);
    btn.disabled = false;
    return;
  }
  // Erst zur Hauptansicht zurück, wenn das Speichern geklappt hat – eine
  // Fehlermeldung in der verlassenen Ansicht würde niemand sehen. Fehler beim
  // Neuladen danach gehören in die Hauptanzeige.
  closeSettings();
  const moved = state.me.moved_entries || 0;
  try {
    await refreshAll();
    // Ziel, Richtung oder Modell können sich geändert haben – dann rechnet
    // der Server neu, sonst kommt die gespeicherte Einschätzung zurück.
    loadCoach();
  } catch (err) {
    setMessage($('error-msg'), err.message);
  } finally {
    btn.disabled = false;
  }
  if (moved) {
    setMessage(
      $('error-msg'),
      `${moved} ${moved === 1 ? 'Eintrag wurde' : 'Einträge wurden'} auf den neuen Tagesbeginn umgebucht.`,
      'ok'
    );
  }
}

// --------------------------------------------------------------------------
// Start
// --------------------------------------------------------------------------

async function refreshAll() {
  state.dayCache = null;
  // Die Schnellwahl hängt an den Einträgen: ein neuer oder korrigierter
  // Eintrag kann einen Knopf hinzufügen oder dessen Werte ändern.
  await Promise.all([loadToday(), loadSummary(), loadWeights(), loadPresets(), loadCalendar()]);
}

function setRange(days) {
  state.range = days;
  state.end = null;
  state.selectedDay = null;
  $('day-detail').hidden = true;
  document.querySelectorAll('[data-range]').forEach((btn) => {
    btn.classList.toggle('active', Number(btn.dataset.range) === days);
  });
  loadSummary().catch((err) => setMessage($('error-msg'), err.message));
}

// Die Wahl gehört zum Gerät, nicht zum Konto – wie das Farbschema. Kann
// localStorage nicht gelesen werden, startet das Diagramm bei den Kalorien.
const METRIC_KEY = 'kcal-chart-metric';
const METRICS = ['kcal', 'protein', 'weight'];

function storedMetric() {
  // Auf dem Desktop beginnt die Seite immer mit den Kalorien: dort ist das
  // Diagramm die größte Fläche und soll beim Öffnen den Tagesstand zeigen,
  // nicht das zuletzt angesehene Gewicht. Auf dem Handy bleibt die gemerkte
  // Wahl. Die Grenze ist dieselbe wie im CSS für das Desktop-Layout.
  if (window.matchMedia('(min-width: 960px)').matches) return 'kcal';
  try {
    const value = localStorage.getItem(METRIC_KEY);
    return METRICS.includes(value) ? value : 'kcal';
  } catch (err) {
    return 'kcal';
  }
}

// Zeitraum und ausgewählter Tag bleiben stehen: so lässt sich derselbe Tag
// in allen drei Diagrammen ansehen. Die Daten sind schon geladen.
function setMetric(metric) {
  state.metric = metric;
  try {
    localStorage.setItem(METRIC_KEY, metric);
  } catch (err) {
    /* ignorieren */
  }
  document.querySelectorAll('[data-metric]').forEach((btn) => {
    btn.setAttribute('aria-pressed', String(btn.dataset.metric === metric));
  });
  if (state.summary) renderSummary();
}

// Balkenhöhen und ob Zahlen und Datumsangaben über die Balken passen, hängen
// an der Größe des Diagramms (siehe renderSummary). Die ändert sich mit der
// Fenstergröße und springt auf dem Desktop zwischen den Spaltenlayouts, also
// neu zeichnen, sobald sie sich ändert. Breite 0 heißt: Hauptansicht
// ausgeblendet. Ohne ResizeObserver (sehr alte Browser) bleibt es beim
// Zeichnen nach dem Laden – ein Fehler hier würde die ganze App anhalten.
let chartSize = '';
if ('ResizeObserver' in window) {
  new ResizeObserver(([entry]) => {
    const { width, height } = entry.contentRect;
    const size = Math.round(width) + 'x' + Math.round(height);
    if (!width || size === chartSize) return;
    chartSize = size;
    if (state.summary) renderSummary();
  }).observe($('week-chart'));
}

// Der Kalender zeigt so viele Wochen, wie in die Breite passen.
let calendarWidth = 0;
if ('ResizeObserver' in window) {
  new ResizeObserver(([entry]) => {
    const width = Math.round(entry.contentRect.width);
    if (!width || width === calendarWidth) return;
    calendarWidth = width;
    renderCalendar();
  }).observe($('cal-grid'));
}

$('add-btn').addEventListener('click', handleAdd);
$('day-detail-add').addEventListener('click', () => startBackfill(state.selectedDay));
$('backfill-close').addEventListener('click', closeBackfill);
$('photo-btn').addEventListener('click', () => $('photo-input').click());
$('photo-input').addEventListener('change', (e) => {
  attachPhoto(e.target.files[0]);
  // Sonst löst dieselbe Datei beim nächsten Mal kein change mehr aus.
  e.target.value = '';
});
$('photo-remove').addEventListener('click', () => {
  clearPhoto();
  $('food-input').focus({ preventScroll: true });
});
// Desktop: Bild aus der Zwischenablage einfügen oder auf das Feld ziehen.
$('food-input').addEventListener('paste', (e) => {
  const file = firstImage(e.clipboardData && e.clipboardData.files);
  if (!file) return;
  e.preventDefault();
  attachPhoto(file);
});
const foodField = document.querySelector('.food-field');
foodField.addEventListener('dragover', (e) => {
  if (!Array.from(e.dataTransfer.types).includes('Files')) return;
  e.preventDefault();
  foodField.classList.add('dragging');
});
foodField.addEventListener('dragleave', () => foodField.classList.remove('dragging'));
foodField.addEventListener('drop', (e) => {
  foodField.classList.remove('dragging');
  const file = firstImage(e.dataTransfer.files);
  if (!file) return;
  e.preventDefault();
  attachPhoto(file);
});
$('food-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleAdd();
  if (e.key === 'Escape' && state.backfill) closeBackfill();
});
$('weight-btn').addEventListener('click', saveWeight);
$('weight-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') saveWeight();
});
$('coach-refresh').addEventListener('click', () => loadCoach(true));
$('coach-toggle').addEventListener('click', () => {
  setCoachCollapsed(!document.querySelector('.dash-today').classList.contains('coach-collapsed'));
});
setCoachCollapsed(storedCoachCollapsed(), false);
$('chart-prev').addEventListener('click', () => shiftRange(-1));
$('chart-next').addEventListener('click', () => shiftRange(1));
document.querySelectorAll('[data-range]').forEach((btn) => {
  btn.addEventListener('click', () => setRange(Number(btn.dataset.range)));
});
document.querySelectorAll('[data-metric]').forEach((btn) => {
  btn.addEventListener('click', () => setMetric(btn.dataset.metric));
});
$('settings-btn').addEventListener('click', openSettings);
$('settings-back').addEventListener('click', closeSettings);
$('settings-cancel').addEventListener('click', closeSettings);
$('settings-save').addEventListener('click', saveSettings);
$('goal-direction-input').addEventListener('change', renderGoalHint);
// Das Farbschema liegt im localStorage, nicht im Konto: es wirkt sofort und
// gehoert deshalb nicht in die PATCH-Nutzlast von "Speichern".
$('theme-input').addEventListener('change', (e) => Theme.set(e.target.value));
// Zurück-Geste, Zurück- und Vorwärts-Taste des Browsers. Die Felder werden nur
// beim Wechsel in die Einstellungen neu befüllt, damit ungespeicherte Eingaben
// nicht überschrieben werden.
window.addEventListener('popstate', () => {
  const show = inSettingsHistory();
  if (show && $('settings-view').hidden) fillSettings();
  showSettingsView(show);
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('settings-view').hidden) closeSettings();
});
$('logout-btn').addEventListener('click', async () => {
  await fetch('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
});

(async function start() {
  try {
    await loadMe();
    // Neu geladen, während die Einstellungen offen waren: der Verlaufseintrag
    // überlebt das Neuladen, also auch die Ansicht.
    if (inSettingsHistory()) {
      fillSettings();
      showSettingsView(true);
    }
    document.querySelector('[data-range="7"]').classList.add('active');
    setMetric(storedMetric());
    await refreshAll();
    // Nur hier und auf "Neu einschätzen": die Einschätzung bewertet die
    // abgeschlossenen Tage und ändert sich durch neue Einträge nicht.
    loadCoach();
  } catch (err) {
    setMessage($('error-msg'), err.message);
  }
})();
