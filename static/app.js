'use strict';

const fmtKcal = (n) => Math.round(n).toLocaleString('de-DE') + ' kcal';
const fmtNum = (n) => Math.round(n).toLocaleString('de-DE');
const weekdayShort = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { weekday: 'short' });
const dateLong = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
// Bewusst nicht toISOString(): das rechnet auf UTC um und verschiebt das Datum
// in unserer Zeitzone um einen Tag nach hinten.
const isoLocal = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-` +
  `${String(date.getDate()).padStart(2, '0')}`;

const $ = (id) => document.getElementById(id);

const state = {
  me: null,
  range: 7,
  end: null,          // Enddatum des angezeigten Zeitraums (null = heute)
  today: null,
  summary: null,
  selectedDay: null,
  editingId: null,
};

// --------------------------------------------------------------------------
// API
// --------------------------------------------------------------------------

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body ? { 'Content-Type': 'application/json' } : {},
    ...options,
  });
  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Nicht angemeldet.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Da ist etwas schiefgelaufen.');
  return data;
}

function setMessage(el, text, kind = 'error') {
  el.textContent = text || '';
  el.className = 'message' + (text ? ' ' + kind : '');
}

// --------------------------------------------------------------------------
// Eintrag hinzufügen
// --------------------------------------------------------------------------

async function addEntry(payload, buttonEl) {
  setMessage($('error-msg'), '');
  const label = buttonEl ? buttonEl.textContent : null;
  if (buttonEl) {
    buttonEl.disabled = true;
    buttonEl.textContent = payload.kcal == null ? 'Schätze…' : 'Speichere…';
  }
  try {
    await api('/api/entries', { method: 'POST', body: JSON.stringify(payload) });
    $('food-input').value = '';
    await refreshAll();
  } catch (err) {
    setMessage($('error-msg'), err.message);
  } finally {
    if (buttonEl) {
      buttonEl.disabled = false;
      buttonEl.textContent = label;
    }
  }
}

function handleAdd() {
  const desc = $('food-input').value.trim();
  if (!desc) {
    setMessage($('error-msg'), 'Bitte gib ein, was du gegessen oder getrunken hast.');
    return;
  }
  addEntry({ desc }, $('add-btn'));
}

// --------------------------------------------------------------------------
// Heutige Einträge
// --------------------------------------------------------------------------

async function loadToday() {
  const data = await api('/api/entries');
  state.today = data;
  renderToday();
}

function renderToday() {
  const list = $('today-list');
  const entries = state.today ? state.today.entries : [];
  list.textContent = '';

  const totalKcal = entries.reduce((sum, e) => sum + e.kcal, 0);
  const totalProtein = entries.reduce((sum, e) => sum + (e.protein || 0), 0);
  $('today-total').textContent = fmtKcal(totalKcal);
  renderGoalProgress(totalKcal, totalProtein);

  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'Noch nichts eingetragen heute.';
    list.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    list.appendChild(
      state.editingId === entry.id ? buildEditForm(entry) : buildEntryRow(entry)
    );
  });
}

function buildEntryRow(entry) {
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
  edit.textContent = '✎';
  edit.addEventListener('click', () => {
    state.editingId = entry.id;
    renderToday();
  });

  const del = document.createElement('button');
  del.className = 'icon-btn danger';
  del.title = 'Eintrag löschen';
  del.setAttribute('aria-label', 'Eintrag löschen');
  del.textContent = '×';
  del.addEventListener('click', async () => {
    del.disabled = true;
    try {
      await api('/api/entries/' + entry.id, { method: 'DELETE' });
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

function buildEditForm(entry) {
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
    { key: 'kcal', label: 'kcal', value: Math.round(entry.kcal), step: 'any', min: '0' },
    {
      key: 'protein', label: 'Eiweiß (g)',
      value: entry.protein == null ? '' : Math.round(entry.protein), step: 'any', min: '0',
    },
  ];
  const inputs = {};
  fields.forEach((field) => {
    const wrap = document.createElement('div');
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = field.label;
    const input = document.createElement('input');
    input.type = 'number';
    input.value = field.value;
    input.step = field.step;
    input.min = field.min;
    input.inputMode = 'numeric';
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
    renderToday();
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
          kcal: inputs.kcal.value,
          protein: inputs.protein.value === '' ? null : inputs.protein.value,
          time: timeInput.value,
        }),
      });
      state.editingId = null;
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
  bar.hidden = false;
  bar.classList.toggle('over', totalKcal >= goal);
  bar.firstElementChild.style.width = share + '%';
  const remaining = goal - totalKcal;
  if (remaining > 0) {
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
// Favoriten / Schnell-Eintrag
// --------------------------------------------------------------------------

async function loadFavorites() {
  const items = await api('/api/favorites');
  const container = $('favorites');
  container.textContent = '';
  items.forEach((item) => {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.title = 'Ohne neue Schätzung direkt übernehmen';
    chip.append(document.createTextNode(item.desc));
    const kcal = document.createElement('span');
    kcal.className = 'chip-kcal';
    kcal.textContent = fmtNum(item.kcal);
    chip.appendChild(kcal);
    chip.addEventListener('click', () =>
      addEntry(
        { desc: item.desc, kcal: item.kcal, protein: item.protein },
        chip
      )
    );
    container.appendChild(chip);
  });
}

// --------------------------------------------------------------------------
// Verlaufsdiagramm
// --------------------------------------------------------------------------

async function loadSummary() {
  const params = new URLSearchParams({ days: String(state.range) });
  if (state.end) params.set('end', state.end);
  state.summary = await api('/api/summary?' + params.toString());
  renderSummary();
}

function renderSummary() {
  const data = state.summary;
  const chart = $('week-chart');
  chart.textContent = '';

  const logged = data.series.filter((d) => d.entries > 0);
  const average = logged.length
    ? logged.reduce((sum, d) => sum + d.total, 0) / logged.length
    : 0;
  $('avg-label').textContent = `Ø erfasste Tage (${state.range})`;
  $('week-avg').textContent = fmtKcal(average);

  $('chart-title').textContent = state.end
    ? `${state.range} Tage bis ${dateLong(data.end)}`
    : `Letzte ${state.range} Tage`;
  $('chart-next').disabled = !state.end;

  const goal = data.kcal_goal || 0;
  const maxValue = Math.max(...data.series.map((d) => d.total), goal, 1);
  const chartHeight = 110;
  // Bei vielen Tagen frisst der Abstand die Balkenbreite auf – auf dem Handy
  // bleiben sonst 5 px übrig, die man nicht treffen kann. Zahlen über den
  // Balken und jedes Datum würden sich dort ebenfalls überlappen.
  const dense = data.series.length > 14;
  chart.style.gap = dense ? '2px' : '6px';
  const labelEvery = dense ? 5 : 1;

  if (goal) {
    const line = document.createElement('div');
    line.className = 'goal-line';
    line.style.bottom = 16 + (goal / maxValue) * chartHeight + 'px';
    const tag = document.createElement('span');
    tag.textContent = 'Ziel ' + fmtNum(goal);
    line.appendChild(tag);
    chart.appendChild(line);
  }

  data.series.forEach((day, index) => {
    const isToday = day.date === data.today;
    const fromEnd = data.series.length - 1 - index;
    const showLabel = fromEnd % labelEvery === 0;
    const col = document.createElement('button');
    col.type = 'button';
    col.className = 'week-col' + (state.selectedDay === day.date ? ' selected' : '');
    col.title = `${dateLong(day.date)}: ${fmtKcal(day.total)}`;
    col.setAttribute('aria-label', col.title);

    const total = document.createElement('span');
    total.className = 'week-total';
    total.textContent = !dense && day.total ? fmtNum(day.total) : '';

    const bar = document.createElement('div');
    bar.className = 'week-bar';
    if (goal && day.total >= goal) bar.classList.add('reached');
    if (isToday) bar.classList.add('today');
    bar.style.height = Math.max(4, Math.round((day.total / maxValue) * chartHeight)) + 'px';

    const label = document.createElement('span');
    label.className = 'week-label' + (isToday ? ' today' : '');
    if (showLabel) {
      label.textContent = dense
        ? new Date(day.date + 'T00:00:00').getDate()
        : weekdayShort(day.date);
    }

    col.append(total, bar, label);
    col.addEventListener('click', () => selectDay(day.date));
    chart.appendChild(col);
  });

  const emptyDays = data.series.length - logged.length;
  $('chart-note').textContent = emptyDays
    ? `Tippe auf einen Balken für die Details. ${emptyDays} Tag${emptyDays === 1 ? '' : 'e'} ohne Einträge.`
    : 'Tippe auf einen Balken, um den Tag zu sehen.';

  if (state.selectedDay) renderDayDetail();
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
  box.hidden = false;
  $('day-detail-date').textContent = dateLong(state.selectedDay);
  if (reload || !state.dayCache || state.dayCache.date !== state.selectedDay) {
    $('day-detail-list').textContent = 'Lade…';
    try {
      state.dayCache = await api(
        '/api/entries?date=' + encodeURIComponent(state.selectedDay)
      );
    } catch (err) {
      $('day-detail-list').textContent = err.message;
      return;
    }
  }
  const entries = state.dayCache.entries;
  const total = entries.reduce((sum, e) => sum + e.kcal, 0);
  $('day-detail-total').textContent = fmtKcal(total);
  const list = $('day-detail-list');
  list.textContent = '';
  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'An diesem Tag wurde nichts eingetragen.';
    list.appendChild(empty);
    return;
  }
  entries.forEach((entry) => {
    const row = document.createElement('div');
    row.className = 'day-detail-item';
    const left = document.createElement('span');
    left.textContent = `${entry.time} · ${entry.desc}`;
    const right = document.createElement('span');
    right.textContent = fmtNum(entry.kcal) + ' kcal';
    row.append(left, right);
    list.appendChild(row);
  });
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

async function saveWeight() {
  const input = $('weight-input');
  const value = input.value.trim();
  if (!value) {
    setMessage($('weight-msg'), 'Bitte gib dein Gewicht in kg ein.');
    return;
  }
  $('weight-btn').disabled = true;
  try {
    await api('/api/weights', { method: 'POST', body: JSON.stringify({ kg: value }) });
    input.value = '';
    setMessage($('weight-msg'), 'Gewicht gespeichert.', 'ok');
    await loadWeights();
    loadCoach();
  } catch (err) {
    setMessage($('weight-msg'), err.message);
  } finally {
    $('weight-btn').disabled = false;
  }
}

// --------------------------------------------------------------------------
// KI-Einschätzung
// --------------------------------------------------------------------------

async function loadCoach(refresh = false) {
  const box = $('coach');
  const refreshBtn = $('coach-refresh');
  box.hidden = false;
  refreshBtn.disabled = true;
  if (refresh) $('coach-stamp').textContent = 'Wird ausgewertet…';
  try {
    const data = refresh
      ? await api('/api/coach/refresh', { method: 'POST' })
      : await api('/api/coach');
    box.className = 'coach ' + (data.status || '');
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
    $('coach-stamp').textContent = data.cached ? 'Gespeicherte Einschätzung' : 'Frisch ausgewertet';
    refreshBtn.hidden = data.status === 'no_goal' || data.status === 'no_data';
  } catch (err) {
    box.className = 'coach';
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

function openSettings() {
  $('goal-input').value = state.me.kcal_goal ? Math.round(state.me.kcal_goal) : '';
  $('protein-goal-input').value = state.me.protein_goal ? Math.round(state.me.protein_goal) : '';
  $('name-input').value = state.me.display_name || '';
  setMessage($('settings-msg'), '');
  $('settings-modal').hidden = false;
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
          kcal_goal: $('goal-input').value.trim() || null,
          protein_goal: $('protein-goal-input').value.trim() || null,
          display_name: $('name-input').value.trim(),
        }),
      })
    );
    $('settings-modal').hidden = true;
    await refreshAll();
  } catch (err) {
    setMessage($('settings-msg'), err.message);
  } finally {
    btn.disabled = false;
  }
}

// --------------------------------------------------------------------------
// Start
// --------------------------------------------------------------------------

async function refreshAll() {
  state.dayCache = null;
  await Promise.all([loadToday(), loadSummary(), loadFavorites(), loadWeights()]);
  loadCoach();
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

$('add-btn').addEventListener('click', handleAdd);
$('food-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleAdd();
});
$('weight-btn').addEventListener('click', saveWeight);
$('weight-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') saveWeight();
});
$('coach-refresh').addEventListener('click', () => loadCoach(true));
$('chart-prev').addEventListener('click', () => shiftRange(-1));
$('chart-next').addEventListener('click', () => shiftRange(1));
document.querySelectorAll('[data-range]').forEach((btn) => {
  btn.addEventListener('click', () => setRange(Number(btn.dataset.range)));
});
$('settings-btn').addEventListener('click', openSettings);
$('settings-close').addEventListener('click', () => ($('settings-modal').hidden = true));
$('settings-cancel').addEventListener('click', () => ($('settings-modal').hidden = true));
$('settings-save').addEventListener('click', saveSettings);
$('settings-modal').addEventListener('click', (e) => {
  if (e.target === $('settings-modal')) $('settings-modal').hidden = true;
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') $('settings-modal').hidden = true;
});
$('logout-btn').addEventListener('click', async () => {
  await fetch('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
});

(async function start() {
  try {
    await loadMe();
    document.querySelector('[data-range="7"]').classList.add('active');
    await refreshAll();
  } catch (err) {
    setMessage($('error-msg'), err.message);
  }
})();
