'use strict';

// Ziele: Übersicht, ein einzelnes Ziel, Anlegen und Bearbeiten, Konfetti.
//
// Nutzt aus app.js die Hilfen ($, api, icon, setMessage, dateLong,
// dateShort, isoLocal, weekdayShort) und den Router (openView, goBack,
// replaceView, switchTab). Der Router ruft showGoalsList, showGoalDetail und
// showGoalForm auf; loadHabits liefert außerdem die Zahl am Ziele-Tab.
//
// Im Code heißen Ziele "habits", damit sie nicht mit dem Kalorienziel
// verwechselt werden. Die Rechnung (Serie, Etappen, "geschafft") macht der
// Server, siehe habits.py – hier wird nur gezeigt.

const UNIT = { day: ['Tag', 'Tage'], week: ['Woche', 'Wochen'], month: ['Monat', 'Monate'] };
const UNIT_SHORT = { day: 'Tg.', week: 'Wo.', month: 'Mon.' };
const PER = { day: 'pro Tag', week: 'pro Woche', month: 'pro Monat' };
// Wie in habits.py: öfter als einmal am Tag geht bei Wochen und Monaten nicht.
const MAX_TARGET = { day: 10, week: 7, month: 31 };
const HABIT_ICONS = [
  'dumbbell', 'leaf', 'apple', 'book', 'drop', 'moon',
  'heart', 'bike', 'sun', 'glass', 'music', 'star',
];
const ICON_NAMES = {
  dumbbell: 'Hantel', leaf: 'Blatt', apple: 'Apfel', book: 'Buch', drop: 'Tropfen', moon: 'Mond',
  heart: 'Herz', bike: 'Fahrrad', sun: 'Sonne', glass: 'Glas', music: 'Musik', star: 'Stern',
};
const SUGGESTIONS = [
  { title: 'Ins Gym gehen', period: 'week', target: 3, icon: 'dumbbell' },
  { title: 'Etwas Gesundes essen', period: 'day', target: 1, icon: 'leaf' },
  { title: 'Obst essen', period: 'day', target: 2, icon: 'apple' },
  { title: 'Lesen', period: 'week', target: 4, icon: 'book' },
  { title: 'Spazieren gehen', period: 'week', target: 5, icon: 'sun' },
  { title: 'Kein Alkohol', period: 'day', target: 1, icon: 'glass' },
];

const goals = {
  habits: null,      // Liste aus /api/habits
  detail: null,      // offenes Ziel samt Verlauf (history)
  heatEnd: null,     // letzter angezeigter Tag im Verlauf, null = heute
  heatWeeks: 0,
  selectedDay: null, // Tag im Nachtragen-Feld
  form: { period: 'week', target: 3, icon: 'dumbbell' },
  editing: null,     // id beim Bearbeiten
  prefill: null,     // Vorschlag aus dem leeren Zustand
  fresh: null,       // Ziel, das gerade eingetragen wurde (siehe markFresh)
  flash: null,       // { habitId, text, until } – "Neuer Rekord" für kurze Zeit
  deleteArmed: false,
};

// --------------------------------------------------------------------------
// Kleine Helfer
// --------------------------------------------------------------------------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const unit = (period, n) => UNIT[period][n === 1 ? 0 : 1];
const freqText = (h) => `${h.target}× ${PER[h.period]}`;
const addDays = (iso, n) => {
  const d = new Date(iso + 'T00:00:00');
  d.setDate(d.getDate() + n);
  return isoLocal(d);
};
const mondayOf = (iso) => addDays(iso, -((new Date(iso + 'T00:00:00').getDay() + 6) % 7));
const wdShort = (iso) => weekdayShort(iso).replace('.', '');
const wdLong = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { weekday: 'long' });
const dayOfMonth = (iso) => Number(iso.slice(8, 10));
const monthLong = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { month: 'long' });
const monthShort = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { month: 'short' }).replace('.', '');
const fmtOne = (n) => n.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const canHover = () => window.matchMedia('(hover: hover)').matches;

// "heute", "diese Woche", "im Oktober"
function thisPeriod(h) {
  if (h.period === 'day') return 'heute';
  if (h.period === 'week') return 'diese Woche';
  return 'im ' + monthLong(h.current.start);
}

// Ende des laufenden Zeitraums, kurz: "bis So", "bis 31.10."
function untilShort(h) {
  const end = h.current.end;
  if (h.period === 'week') return 'bis ' + wdShort(end);
  if (h.period === 'month') return `bis ${dayOfMonth(end)}.${Number(end.slice(5, 7))}.`;
  return '';
}

// Ende des laufenden Zeitraums, ausgeschrieben: "bis Sonntag", "bis zum 31. Oktober"
function untilLong(h) {
  const end = h.current.end;
  if (h.period === 'week') return 'bis ' + wdLong(end);
  if (h.period === 'month') return 'bis zum ' + dateShort(end);
  return 'heute';
}

function replaceHabit(habit) {
  if (!goals.habits) return;
  const index = goals.habits.findIndex((h) => h.id === habit.id);
  if (index >= 0) goals.habits[index] = { ...goals.habits[index], ...habit };
  else goals.habits.push(habit);
}

function updateBadge() {
  const open = (goals.habits || []).filter((h) => h.period === 'day' && !h.current.met).length;
  const badge = $('goals-badge');
  badge.hidden = !open;
  badge.textContent = open ? String(open) : '';
  const tab = document.querySelector('#tabbar [data-tab="goals"]');
  tab.setAttribute('aria-label', open ? `Ziele, ${open} heute offen` : 'Ziele');
}

// --------------------------------------------------------------------------
// Übersicht
// --------------------------------------------------------------------------

let habitsRequest = 0;

async function loadHabits() {
  const request = ++habitsRequest;
  const data = await api('/api/habits');
  if (request !== habitsRequest) return;
  goals.habits = data.habits;
  updateBadge();
  if (!$('goals-view').hidden) renderGoalsList();
}

function showGoalsList() {
  setMessage($('goals-msg'), '');
  renderGoalsList();
  loadHabits().catch((err) => setMessage($('goals-msg'), err.message));
}

function renderGoalsList() {
  const list = $('habit-list');
  const habits = goals.habits;
  list.textContent = '';
  if (!habits) return;
  const daily = habits.filter((h) => h.period === 'day');
  $('goals-sub').textContent = daily.length
    ? `Heute ${daily.filter((h) => h.current.met).length} von ${daily.length} ` +
      (daily.length === 1 ? 'Tagesziel' : 'Tageszielen') + ' geschafft'
    : habits.length ? 'Trag ein, wenn du etwas geschafft hast.'
    : 'Was willst du regelmäßig schaffen? Nimm einen Vorschlag oder leg mit + ein eigenes Ziel an.';
  habits.forEach((h) => list.appendChild(buildHabitCard(h)));
  // Ohne Ziele stehen die Vorschläge als gestrichelte Kacheln dort, wo die
  // Karten erscheinen werden. Ein eigenes Ziel legt das Plus oben an.
  if (!habits.length) SUGGESTIONS.forEach((s) => list.appendChild(buildSuggestTile(s)));
}

// Öffnet das Formular schon ausgefüllt.
function buildSuggestTile(suggestion) {
  const tile = el('button', 'habit-suggest');
  tile.type = 'button';
  tile.setAttribute('aria-label', `${suggestion.title}, ${freqText(suggestion)} – als Ziel anlegen`);
  const icn = el('span', 'habit-icon');
  icn.appendChild(icon(suggestion.icon, 20));
  const text = el('span', 'habit-titles');
  text.appendChild(el('span', 'habit-name', suggestion.title));
  text.appendChild(el('span', 'habit-freq', freqText(suggestion)));
  const plus = el('span', 'habit-suggest-plus');
  plus.appendChild(icon('plus', 16));
  tile.append(icn, text, plus);
  tile.addEventListener('click', () => {
    goals.prefill = suggestion;
    openView('goal-form');
  });
  return tile;
}

function buildSeg(h, className) {
  const seg = el('div', className);
  const count = Math.min(h.current.count, h.target);
  if (h.target <= 12) {
    for (let i = 0; i < h.target; i++) seg.appendChild(el('i', i < count ? 'on' : ''));
  } else {
    seg.classList.add('solid');
    const fill = el('i', 'on');
    fill.style.width = (count / h.target) * 100 + '%';
    seg.appendChild(fill);
  }
  return seg;
}

function buildStreakRow(h) {
  const row = el('div', 'habit-streak' + (h.streak ? '' : ' none'));
  const flame = el('span', 'flame');
  flame.appendChild(icon('flame', 16));
  row.appendChild(flame);
  if (h.streak) {
    row.appendChild(el('span', 'habit-streak-num', String(h.streak)));
    row.appendChild(el('span', '', `${unit(h.period, h.streak)} in Folge`));
  } else {
    row.appendChild(el('span', '', h.best ? `Noch keine Serie · Rekord ${h.best}` : 'Noch keine Serie'));
  }
  // Die letzten Zeiträume als Kästchen, der laufende umrandet.
  const recent = el('span', 'habit-recent');
  recent.setAttribute('aria-hidden', 'true');
  h.recent.forEach((met) => recent.appendChild(el('i', met === null ? 'none' : met ? 'on' : '')));
  recent.appendChild(el('i', 'cur' + (h.current.met ? ' on' : '')));
  row.appendChild(recent);
  return row;
}

function buildHabitCard(h) {
  const card = el('article', 'habit-card');
  card.dataset.id = h.id;
  const top = el('div', 'habit-top');
  const open = el('button', 'habit-open');
  open.type = 'button';
  const icn = el('span', 'habit-icon');
  icn.appendChild(icon(h.icon, 20));
  const titles = el('span', 'habit-titles');
  titles.appendChild(el('span', 'habit-name', h.title));
  titles.appendChild(el('span', 'habit-freq', freqText(h)));
  open.append(icn, titles);
  open.addEventListener('click', () => openView('goal', h.id));

  const check = el('button', 'habit-check');
  check.type = 'button';
  const doneToday = !h.can_check_today;
  if (doneToday) {
    check.classList.add('done');
    check.append(iconFace('when-rest', 'check', 20), iconFace('when-hover', 'close', 20));
    check.setAttribute('aria-label', `${h.title}: heute eingetragen – wieder austragen`);
    check.title = 'Wieder austragen';
    armUncheck(check, h);
  } else {
    check.appendChild(icon('plus', 20));
    check.setAttribute('aria-label', `${h.title}: heute eintragen`);
    check.title = 'Heute eintragen';
    check.addEventListener('click', (e) => {
      e.stopPropagation();
      checkIn(h.id, null, check);
    });
  }
  top.append(open, check);
  card.appendChild(top);
  card.appendChild(buildSeg(h, 'habit-seg'));

  const meta = el('div', 'habit-meta');
  const left = el('span');
  if (h.current.met) {
    left.textContent = { day: 'Heute geschafft', week: 'Woche geschafft', month: 'Monat geschafft' }[h.period];
  } else if (h.target === 1) {
    const when = thisPeriod(h);
    left.textContent = when.charAt(0).toUpperCase() + when.slice(1) + ' noch offen';
  } else {
    left.appendChild(el('span', 'num', String(h.current.count)));
    left.appendChild(document.createTextNode(` von ${h.target} ${thisPeriod(h)}`));
  }
  meta.appendChild(left);
  if (!h.current.met) {
    const left = h.target - h.current.count;
    const text = h.target === 1 ? untilShort(h) : `noch ${left}×` + (untilShort(h) ? ' ' + untilShort(h) : '');
    if (text) meta.appendChild(el('span', h.risk ? 'warn' : '', text));
  } else if (h.period === 'day' && h.target > 1) {
    meta.appendChild(el('span', '', `${h.current.count} / ${h.target}`));
  }
  card.appendChild(meta);
  card.appendChild(buildStreakRow(h));
  // Die ganze Karte öffnet das Ziel – nur der runde Knopf trägt ein.
  card.addEventListener('click', (e) => {
    if (e.target.closest('button')) return;
    openView('goal', h.id);
  });
  return card;
}

// --------------------------------------------------------------------------
// Eintragen
// --------------------------------------------------------------------------

async function checkIn(habitId, date = null, buttonEl = null) {
  const msg = $('goal-view').hidden ? $('goals-msg') : $('goal-msg');
  setMessage(msg, '');
  if (buttonEl) buttonEl.disabled = true;
  let result;
  try {
    result = await api(`/api/habits/${habitId}/checkins`, {
      method: 'POST',
      body: JSON.stringify(date ? { date } : {}),
    });
  } catch (err) {
    setMessage(msg, err.message);
    if (buttonEl) buttonEl.disabled = false;
    return null;
  }
  replaceHabit(result.habit);
  updateBadge();
  if (result.record && !result.milestone) {
    goals.flash = {
      habitId,
      text: `Neuer Rekord: ${result.habit.streak} ${unit(result.habit.period, result.habit.streak)} in Folge.`,
      until: Date.now() + 10000,
    };
  }
  // Der Knopf unter dem Zeiger wird gleich zum Austragen-Knopf – erst rot
  // werden lassen, wenn die Maus ihn einmal verlassen hat.
  goals.fresh = habitId;
  if (!$('goal-view').hidden && goals.detail && goals.detail.id === habitId) {
    await loadGoalDetail(true);
  } else if (!$('goals-view').hidden) {
    renderGoalsList();
  }
  if (result.completed) celebrate(result.habit);
  return result;
}

async function undoCheckin(habitId, checkinId) {
  try {
    const result = await api(`/api/habits/${habitId}/checkins/${checkinId}`, { method: 'DELETE' });
    goals.flash = null;
    replaceHabit(result.habit);
    updateBadge();
    if (!$('goal-view').hidden) await loadGoalDetail(true);
    else renderGoalsList();
  } catch (err) {
    setMessage($('goal-view').hidden ? $('goals-msg') : $('goal-msg'), err.message);
  }
}

// Ein Symbol (oder Symbol und Text) für einen der beiden Zustände eines
// Knopfs: in Ruhe (when-rest) oder beim Überfahren (when-hover). Das CSS
// blendet jeweils einen aus.
function iconFace(className, name, size, text = null) {
  const face = el('span', className);
  face.appendChild(icon(name, size));
  if (text) face.appendChild(document.createTextNode(text));
  return face;
}

// Ein eingetragener Knopf trägt heute wieder aus. Mit Maus ist er beim
// Überfahren schon rot, ein Klick genügt. Auf dem Touchscreen gibt es kein
// Überfahren: der erste Tipp macht ihn rot, der zweite trägt aus – sonst
// wäre ein versehentlicher Tipp gleich ein gelöschter Eintrag.
function armUncheck(button, h) {
  const lastToday = () => h.today_checkins[h.today_checkins.length - 1];
  if (goals.fresh === h.id && canHover()) markFresh(button);
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    if (button.classList.contains('fresh')) return;
    if (canHover() || button.classList.contains('armed')) {
      button.disabled = true;
      undoCheckin(h.id, lastToday());
      return;
    }
    button.classList.add('armed');
    setTimeout(() => button.classList.remove('armed'), 3000);
  });
  button.addEventListener('blur', () => button.classList.remove('armed'));
}

// Direkt nach dem Eintragen steht der Zeiger noch über dem Knopf. Rot wird er
// erst, wenn die Maus ihn einmal verlassen hat; bis dahin tut ein Klick
// nichts, damit ein Doppelklick nicht gleich wieder austrägt.
function markFresh(button) {
  button.classList.add('fresh');
  button.addEventListener('mouseleave', () => {
    button.classList.remove('fresh');
    goals.fresh = null;
  }, { once: true });
}

// Ein Zeitraum ist gerade voll geworden. Die Flamme hüpft immer; Konfetti
// gibt es bei Wochen- und Monatszielen – bei Tageszielen käme es sonst
// jeden Tag und wäre bald nichts mehr wert.
function celebrate(habit) {
  if (!reduceMotion()) {
    const scope = !$('goal-view').hidden ? $('goal-view') : document.querySelector(`.habit-card[data-id="${habit.id}"]`);
    const flame = scope && scope.querySelector('.streak-flame, .habit-streak .flame');
    if (flame) {
      flame.classList.remove('pulse');
      void flame.offsetWidth;
      flame.classList.add('pulse');
    }
  }
  if (habit.period !== 'day') confetti();
}

// Konfetti vom unteren Bildschirmrand: ein <canvas> über der Seite, das sich
// nach gut zwei Sekunden selbst entfernt. Die Seite bleibt bedienbar.
function confetti() {
  if (reduceMotion()) return;
  const canvas = el('canvas', 'confetti');
  canvas.setAttribute('aria-hidden', 'true');
  document.body.appendChild(canvas);
  const dpr = window.devicePixelRatio || 1;
  const W = window.innerWidth;
  const H = window.innerHeight;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const css = getComputedStyle(document.documentElement);
  const colors = ['--ember', '--ember', '--accent', '--accent-dark', '--gold', '--ember-dark', '--gold']
    .map((name) => css.getPropertyValue(name).trim());
  // Auf großen Bildschirmen mehr Schnipsel und mehr Schwung, damit es nicht
  // nur am unteren Rand glimmt.
  const count = Math.round(Math.min(220, Math.max(110, W / 2.6)));
  const lift = Math.sqrt(H / 760);
  const parts = [];
  for (let i = 0; i < count; i++) {
    const x = W * (0.04 + Math.random() * 0.92);
    const kind = Math.random();
    parts.push({
      x, y: H + 6,
      vx: (Math.random() - 0.5) * 4.5 + (W / 2 - x) * 0.006,
      vy: -(11.5 + Math.random() * 10.5) * lift,
      g: (0.28 + Math.random() * 0.06) * lift,
      w: 5 + Math.random() * 4,
      h: 8 + Math.random() * 6,
      rot: Math.random() * 6.28,
      vr: (Math.random() - 0.5) * 0.3,
      ph: Math.random() * 6.28,
      vph: 0.1 + Math.random() * 0.14,
      color: colors[i % colors.length],
      shape: kind < 0.18 ? 'dot' : kind < 0.36 ? 'strip' : 'rect',
      delay: Math.random() < 0.65 ? 0 : 6 + Math.random() * 16,
      life: 0,
    });
  }
  let frame = 0;
  let last = performance.now();
  function tick(now) {
    // In Schritten von 60 Bildern pro Sekunde rechnen, damit 120-Hz-Displays
    // nicht doppelt so schnell sind.
    const step = Math.min(2, Math.max(0.5, (now - last) / 16.67));
    last = now;
    frame += step;
    ctx.clearRect(0, 0, W, H);
    let alive = 0;
    for (const p of parts) {
      if (frame < p.delay) { alive++; continue; }
      const drag = Math.pow(0.985, step);
      p.vx *= drag;
      p.vy = p.vy * drag + p.g * step;
      p.x += p.vx * step;
      p.y += p.vy * step;
      p.rot += p.vr * step;
      p.ph += p.vph * step;
      p.life += step;
      if (p.y > H + 30 && p.vy > 0) continue;
      const alpha = p.life > 110 ? 1 - (p.life - 110) / 30 : 1;
      if (alpha <= 0) continue;
      alive++;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.scale(1, Math.cos(p.ph));
      ctx.fillStyle = p.color;
      if (p.shape === 'dot') {
        ctx.beginPath();
        ctx.arc(0, 0, p.w * 0.42, 0, 6.283);
        ctx.fill();
      } else if (p.shape === 'strip') {
        ctx.fillRect(-1.25, -p.h * 0.75, 2.5, p.h * 1.5);
      } else {
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      }
      ctx.restore();
    }
    if (alive && frame < 260) requestAnimationFrame(tick);
    else canvas.remove();
  }
  requestAnimationFrame(tick);
}

// --------------------------------------------------------------------------
// Ein Ziel
// --------------------------------------------------------------------------

let detailRequest = 0;

function showGoalDetail(id) {
  setMessage($('goal-msg'), '');
  if (!goals.detail || goals.detail.id !== id) {
    goals.heatEnd = null;
    goals.selectedDay = null;
    $('heat-day').hidden = true;
    const cached = (goals.habits || []).find((h) => h.id === id);
    goals.detail = cached ? { ...cached, history: null } : null;
  }
  if (goals.detail) renderGoalDetail();
  else {
    $('goal-title').textContent = '';
    $('goal-sub').textContent = '';
    $('goal-streak').textContent = '';
    $('habit-heat').textContent = '';
    $('habit-stats').textContent = '';
  }
  goals.detailId = id;
  loadGoalDetail().catch(() => {});
}

// Wie viele Wochen der Verlauf zeigt, hängt an der Breite: Kästchen von
// etwa 12px plus 3px Abstand, zwischen 12 Wochen und einem Jahr.
function heatWeeksFor(width) {
  return Math.max(12, Math.min(53, Math.floor((width - 24) / 15)));
}

async function loadGoalDetail(keepDay = false) {
  const id = goals.detailId;
  const request = ++detailRequest;
  const weeks = heatWeeksFor($('habit-heat').clientWidth || 300);
  const today = (goals.detail && goals.detail.today) || isoLocal(new Date());
  const end = addDays(mondayOf(goals.heatEnd || today), 6);
  const start = addDays(end, -(weeks * 7 - 1));
  let data;
  try {
    data = await api(`/api/habits/${id}?from=${start}&to=${end}`);
  } catch (err) {
    if (request !== detailRequest) return;
    if (err.status === 404) {
      goals.detail = null;
      replaceView('goals');
      setMessage($('goals-msg'), 'Dieses Ziel gibt es nicht mehr.');
      return;
    }
    setMessage($('goal-msg'), err.message);
    throw err;
  }
  if (request !== detailRequest || id !== goals.detailId) return;
  goals.heatWeeks = weeks;
  goals.detail = data;
  replaceHabit(data);
  updateBadge();
  renderGoalDetail();
  if (goals.selectedDay && keepDay) selectHeatDay(goals.selectedDay);
}

function renderGoalDetail() {
  const h = goals.detail;
  $('goal-title').textContent = h.title;
  $('goal-sub').textContent = `${freqText(h)} · seit ${dateShort(h.start_date)}`;
  renderStreakCard(h);
  if (h.history) renderHeat(h);
  else {
    // Noch kein Verlauf geladen (anderes Ziel aus dem Zwischenstand): lieber
    // leer als der Verlauf des vorigen Ziels.
    $('habit-heat').textContent = '';
    $('heat-foot').textContent = '';
  }
  renderHabitStats(h);
}

function streakMessage(h) {
  const c = h.current;
  const left = h.target - c.count;
  const one = unit(h.period, 1);
  if (goals.flash && goals.flash.habitId === h.id && goals.flash.until > Date.now()) {
    return { text: goals.flash.text, kind: 'ember' };
  }
  if (h.milestone_hit) {
    return { text: `Meilenstein erreicht: ${h.streak} ${unit(h.period, h.streak)} in Folge.`, kind: 'ember' };
  }
  if (c.met) {
    const next = { day: 'morgen', week: 'nächste Woche', month: 'im ' + monthLong(addDays(c.end, 1)) }[h.period];
    const done = { day: 'Heute geschafft', week: 'Woche geschafft', month: `${monthLong(c.start)} geschafft` }[h.period];
    return { text: `${done} – ${next} geht es weiter.`, kind: '' };
  }
  if (h.risk === 'tight') {
    return {
      text: `Noch ${left}× ${untilLong(h)} – sonst endet die Serie von ${h.run_before} ${unit(h.period, h.run_before)}.`,
      kind: 'warn',
    };
  }
  if (h.risk === 'lost') {
    return {
      text: `${h.period === 'week' ? 'Diese Woche' : 'Diesen Monat'} reicht es nicht mehr – die Serie von ${h.run_before} ${unit(h.period, h.run_before)} endet ${h.period === 'week' ? 'am ' + wdLong(c.end) : 'mit dem Monat'}.`,
      kind: '',
    };
  }
  if (!h.streak) {
    return { text: `Noch ${left}× ${thisPeriod(h)}, dann beginnt deine Serie.`, kind: '' };
  }
  const next = h.streak + 1;
  return { text: `Noch ${left}× ${thisPeriod(h)}, dann sind es ${next} ${unit(h.period, next)}.`, kind: '' };
}

function pillLabel(h, checkin) {
  if (h.period === 'week') return wdShort(checkin.date);
  if (h.period === 'month') return dayOfMonth(checkin.date) + '.';
  return checkin.time || null;
}

function renderStreakCard(h) {
  const card = $('goal-streak');
  const previous = card.querySelector('.streak-num');
  const before = previous ? previous.textContent : null;
  card.textContent = '';

  // Flamme, Zahl, Rekord
  const top = el('div', 'streak-top');
  const flame = el('span', 'streak-flame' + (h.streak ? '' : ' cold'));
  flame.appendChild(icon('flame', 30));
  const numbers = el('div');
  const num = el('p', 'streak-num' + (h.streak ? '' : ' zero'), String(h.streak));
  if (before !== null && before !== String(h.streak) && !reduceMotion()) num.classList.add('rise');
  numbers.appendChild(num);
  numbers.appendChild(el('p', 'streak-unit', `${unit(h.period, h.streak)} in Folge`));
  const best = el('div', 'streak-best', 'Rekord');
  best.appendChild(el('b', '', `${h.best} ${UNIT_SHORT[h.period]}`));
  top.append(flame, numbers, best);
  card.appendChild(top);

  // Durchgehende Leiste bis zur nächsten Etappe; der laufende Zeitraum zählt
  // anteilig mit.
  const bar = h.bar;
  const share = Math.max(0, Math.min(1, (bar.value - bar.from) / Math.max(1, bar.to - bar.from)));
  const row = el('div', 'streak-row');
  const track = el('div', 'streak-bar');
  track.setAttribute('role', 'img');
  track.setAttribute('aria-label', h.milestone_hit
    ? `Meilenstein ${bar.to} erreicht`
    : `Auf dem Weg zum Meilenstein ${bar.to} ${unit(h.period, bar.to)}`);
  const fill = el('span');
  track.appendChild(fill);
  const flag = el('span', 'streak-flag' + (h.milestone_hit ? ' got' : ''));
  flag.appendChild(icon('flag', 13));
  flag.appendChild(el('span', '', String(bar.to)));
  flag.title = `Meilenstein: ${bar.to} ${unit(h.period, bar.to)} in Folge`;
  row.append(track, flag);
  card.appendChild(row);
  // Erst nach dem Einhängen setzen, damit die Breite animiert wächst.
  const oldShare = Number(card.dataset.share || 0);
  fill.style.width = (card.dataset.habit === String(h.id) ? oldShare : share) * 100 + '%';
  card.dataset.share = String(share);
  card.dataset.habit = String(h.id);
  requestAnimationFrame(() => { fill.style.width = share * 100 + '%'; });

  // Der laufende Zeitraum: je Einheit eine Pille, gefüllte tragen den Tag.
  const line = el('div', 'period-line');
  const label = { day: 'Heute', week: 'Diese Woche', month: monthLong(h.current.start) }[h.period];
  line.appendChild(el('span', 'period-label', label.charAt(0).toUpperCase() + label.slice(1)));
  if (h.target <= 7) {
    const pills = el('span', 'period-pills');
    for (let i = 0; i < h.target; i++) {
      const checkin = h.current.checkins[i];
      const pill = el('i', checkin ? 'on' : '');
      if (checkin) {
        const text = pillLabel(h, checkin);
        if (text) pill.textContent = text;
        else pill.appendChild(icon('check', 12));
      }
      pills.appendChild(pill);
    }
    line.appendChild(pills);
  } else {
    line.appendChild(buildSeg(h, 'habit-seg period-seg'));
  }
  line.appendChild(el('span', 'period-count', `${h.current.count} / ${h.target}`));
  card.appendChild(line);

  const msg = streakMessage(h);
  card.appendChild(el('p', 'streak-msg' + (msg.kind ? ' ' + msg.kind : ''), msg.text));

  // Eintragen
  if (h.can_check_today) {
    const btn = el('button', 'streak-checkin');
    const more = h.period === 'day' && h.today_count > 0;
    btn.appendChild(icon(more ? 'plus' : 'check', 18));
    btn.appendChild(document.createTextNode(more ? `Noch ${h.target - h.today_count}× eintragen` : 'Heute eintragen'));
    btn.addEventListener('click', () => checkIn(h.id, null, btn));
    card.appendChild(btn);
  } else {
    const done = el('button', 'streak-done');
    done.type = 'button';
    done.append(
      iconFace('when-rest', 'check', 18, h.period === 'day' ? 'Heute geschafft' : 'Heute eingetragen'),
      iconFace('when-hover', 'close', 18, 'Wieder austragen')
    );
    done.setAttribute('aria-label', 'Heute eingetragen – wieder austragen');
    armUncheck(done, h);
    card.appendChild(done);
  }
  const links = el('p', 'streak-links');
  const other = el('button', 'link', 'Anderen Tag nachtragen');
  other.addEventListener('click', () => {
    selectHeatDay(addDays(h.today, -1));
    $('heat-day').scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
    $('heat-day-input').focus({ preventScroll: true });
  });
  links.appendChild(other);
  card.appendChild(links);
}

// Verlauf im Stil des GitHub-Graphen: eine Spalte je Woche, Montag oben.
// Bei Wochenzielen zeigt ein Strich unter der Spalte, ob die Woche gereicht hat.
function renderHeat(h) {
  const grid = $('habit-heat');
  const hist = h.history;
  const weekly = h.period === 'week';
  const weeks = Math.round((new Date(hist.to + 'T00:00:00') - new Date(hist.from + 'T00:00:00')) / 864e5 / 7);
  grid.textContent = '';
  grid.style.setProperty('--weeks', weeks);
  grid.classList.toggle('weekly', weekly);
  grid.appendChild(el('span'));
  ['Mo', '', 'Mi', '', 'Fr', '', 'So'].forEach((d) => grid.appendChild(el('span', 'heat-wd', d)));
  if (weekly) grid.appendChild(el('span'));
  const limit = h.period === 'day' ? h.target : 1;
  let lastMonth = null;
  for (let w = 0; w < weeks; w++) {
    const monday = addDays(hist.from, w * 7);
    const month = new Date(addDays(monday, 3) + 'T00:00:00').getMonth();
    const nextMonth = new Date(addDays(monday, 10) + 'T00:00:00').getMonth();
    // Monatsname über der ersten Woche eines Monats – nicht ganz am Ende
    // (zu wenig Platz) und nicht über einer angeschnittenen ersten Spalte.
    const labelled = month !== lastMonth && w < weeks - 2 && !(w === 0 && nextMonth !== month);
    grid.appendChild(el('span', 'heat-month', labelled ? monthShort(addDays(monday, 3)) : ''));
    lastMonth = month;
    for (let d = 0; d < 7; d++) {
      const iso = addDays(monday, d);
      const n = hist.days[iso] || 0;
      const cell = el('button', 'heat-cell');
      cell.type = 'button';
      cell.dataset.date = iso;
      if (iso > h.today) {
        cell.classList.add('future');
        cell.disabled = true;
      } else if (n >= limit) cell.classList.add('on');
      else if (n > 0) cell.classList.add('part');
      else if (iso < h.start_date) cell.classList.add('before');
      if (iso === h.today) cell.classList.add('today');
      if (iso === goals.selectedDay) cell.classList.add('selected');
      cell.setAttribute('aria-label', `${dateLong(iso)}: ${n ? n + '× eingetragen' : 'nichts eingetragen'}`);
      cell.addEventListener('click', () => selectHeatDay(iso));
      grid.appendChild(cell);
    }
    if (weekly) {
      const met = hist.periods[monday];
      const current = monday === mondayOf(h.today);
      const done = current ? h.current.met : met;
      grid.appendChild(el('span', 'heat-week' + (done ? ' on' : '') + (current && !done ? ' open' : '')));
    }
  }
  $('heat-next').disabled = !goals.heatEnd || goals.heatEnd >= h.today;
  const foot = $('heat-foot');
  foot.textContent = '';
  foot.appendChild(el('span', 'heat-hint', 'Tippe auf einen Tag, um nachzutragen oder zu löschen.'));
  const legend = el('span', 'heat-legend');
  const key = (cls, text) => {
    const item = el('span', 'heat-key');
    item.appendChild(el('i', cls));
    item.appendChild(document.createTextNode(text));
    legend.appendChild(item);
  };
  if (h.period === 'day' && h.target > 1) {
    key('part', 'teilweise');
    key('', 'geschafft');
  } else key('', h.period === 'day' ? 'geschafft' : 'eingetragen');
  if (weekly) key('week', 'Woche geschafft');
  foot.appendChild(legend);
}

function shiftHeat(direction) {
  const h = goals.detail;
  if (!h) return;
  const end = goals.heatEnd || h.today;
  let next = addDays(end, direction * goals.heatWeeks * 7);
  if (next >= h.today) next = null;
  goals.heatEnd = next;
  loadGoalDetail(true).catch(() => {});
}

function renderHabitStats(h) {
  const box = $('habit-stats');
  box.textContent = '';
  const t = h.totals;
  const periodsSoFar = t.periods + (h.current.met ? 0 : 1);
  const tile = (value, label) => {
    const item = el('div', 'habit-stat');
    item.appendChild(el('p', 'habit-stat-value', value));
    item.appendChild(el('p', 'habit-stat-label', label));
    box.appendChild(item);
  };
  const done = t.periods ? Math.round((t.met / t.periods) * 100) : null;
  tile(done === null ? '–' : `${done} %`, `der ${UNIT[h.period][1]} geschafft`);
  tile(t.entries.toLocaleString('de-DE'), 'Einträge gesamt');
  tile(`${fmtOne(t.entries / Math.max(1, periodsSoFar))}×`, `pro ${UNIT[h.period][0]} im Schnitt`);
}

// Nachtragen oder Löschen an einem Tag.
async function selectHeatDay(iso) {
  const h = goals.detail;
  if (!h || !iso) return;
  if (iso > h.today) iso = h.today;
  goals.selectedDay = iso;
  $('heat-day').hidden = false;
  const input = $('heat-day-input');
  input.max = h.today;
  input.value = iso;
  setMessage($('heat-day-msg'), '');
  document.querySelectorAll('#habit-heat .heat-cell.selected').forEach((c) => c.classList.remove('selected'));
  const cell = document.querySelector(`#habit-heat .heat-cell[data-date="${iso}"]`);
  if (cell) cell.classList.add('selected');
  const list = $('heat-day-list');
  let data;
  try {
    data = await api(`/api/habits/${h.id}/checkins?date=${iso}`);
  } catch (err) {
    setMessage($('heat-day-msg'), err.message);
    return;
  }
  if (goals.selectedDay !== iso) return;
  list.textContent = '';
  data.checkins.forEach((c) => {
    const row = el('div', 'heat-day-item');
    row.appendChild(el('span', '', c.time ? `${c.time} Uhr` : 'nachgetragen'));
    const del = el('button', 'icon-btn danger');
    del.type = 'button';
    del.title = 'Eintrag löschen';
    del.setAttribute('aria-label', 'Eintrag löschen');
    del.appendChild(icon('trash'));
    del.addEventListener('click', () => undoCheckin(h.id, c.id).then(() => selectHeatDay(iso)));
    row.appendChild(del);
    list.appendChild(row);
  });
  if (!data.checkins.length) list.appendChild(el('p', 'heat-day-empty', `${dateLong(iso)}: nichts eingetragen.`));
  const limit = h.period === 'day' ? h.target : 1;
  const add = $('heat-day-add');
  add.disabled = data.checkins.length >= limit;
  add.textContent = add.disabled ? 'Eingetragen' : 'Eintragen';
}

async function addHeatDay() {
  const h = goals.detail;
  const iso = $('heat-day-input').value;
  if (!h || !iso) return;
  const result = await checkIn(h.id, iso, $('heat-day-add'));
  if (!result) {
    setMessage($('heat-day-msg'), $('goal-msg').textContent);
    setMessage($('goal-msg'), '');
    $('heat-day-add').disabled = false;
    return;
  }
  // Steht der Tag außerhalb des angezeigten Zeitraums, dorthin springen.
  if (iso < h.history.from || iso > h.history.to) {
    goals.heatEnd = iso;
    await loadGoalDetail(true);
  }
  selectHeatDay(iso);
}

// --------------------------------------------------------------------------
// Anlegen und Bearbeiten
// --------------------------------------------------------------------------

async function showGoalForm(id) {
  goals.editing = id;
  goals.deleteArmed = false;
  setMessage($('goal-form-msg'), '');
  let habit = null;
  if (id) {
    habit = (goals.habits || []).find((h) => h.id === id) || (goals.detail && goals.detail.id === id ? goals.detail : null);
    if (!habit) {
      try {
        habit = await api(`/api/habits/${id}`);
      } catch (err) {
        setMessage($('goal-form-msg'), err.message);
        return;
      }
    }
  }
  const source = habit || goals.prefill || { title: '', period: 'week', target: 3, icon: 'dumbbell' };
  goals.prefill = null;
  goals.form = { period: source.period, target: source.target, icon: source.icon };
  goals.original = habit ? { period: habit.period, target: habit.target } : null;
  $('goal-form-title').textContent = habit ? 'Ziel bearbeiten' : 'Neues Ziel';
  $('goal-save').textContent = habit ? 'Speichern' : 'Ziel anlegen';
  $('goal-name-input').value = source.title;
  $('goal-danger').hidden = !habit;
  resetDelete();
  renderSuggestionChips(!habit);
  renderIconGrid();
  renderFrequency();
}

function renderSuggestionChips(show) {
  const box = $('goal-suggest');
  box.textContent = '';
  box.hidden = !show;
  if (!show) return;
  SUGGESTIONS.forEach((s) => {
    const chip = el('button', 'chip', s.title);
    chip.type = 'button';
    chip.addEventListener('click', () => {
      $('goal-name-input').value = s.title;
      goals.form = { period: s.period, target: s.target, icon: s.icon };
      renderIconGrid();
      renderFrequency();
    });
    box.appendChild(chip);
  });
}

function renderIconGrid() {
  const grid = $('goal-icons');
  grid.textContent = '';
  HABIT_ICONS.forEach((name) => {
    const btn = el('button', 'icon-choice');
    btn.type = 'button';
    btn.setAttribute('role', 'radio');
    btn.setAttribute('aria-checked', String(goals.form.icon === name));
    btn.setAttribute('aria-label', ICON_NAMES[name]);
    btn.title = ICON_NAMES[name];
    btn.tabIndex = goals.form.icon === name ? 0 : -1;
    btn.appendChild(icon(name, 22));
    btn.addEventListener('click', () => {
      goals.form.icon = name;
      renderIconGrid();
      grid.querySelector('[aria-checked="true"]').focus({ preventScroll: true });
    });
    grid.appendChild(btn);
  });
}

function explainFrequency(period, n) {
  if (period === 'day') {
    return n === 1
      ? 'Ein Tag ist geschafft, wenn du einmal eingetragen hast. Deine Serie zählt die Tage am Stück.'
      : `Ein Tag ist geschafft, wenn du ${n}× eingetragen hast. Deine Serie zählt die geschafften Tage am Stück.`;
  }
  const days = n === 1 ? 'an einem Tag' : `an ${n} Tagen`;
  if (period === 'week') {
    return `Eine Woche (Montag bis Sonntag) ist geschafft, wenn du ${days} eingetragen hast – egal an welchen. Deine Serie zählt die geschafften Wochen am Stück.`;
  }
  return `Ein Monat ist geschafft, wenn du ${days} eingetragen hast. Deine Serie zählt die geschafften Monate am Stück.`;
}

function renderFrequency() {
  const { period, target } = goals.form;
  $('goal-target-value').textContent = String(target);
  $('goal-target-minus').disabled = target <= 1;
  $('goal-target-plus').disabled = target >= MAX_TARGET[period];
  document.querySelectorAll('[data-period]').forEach((btn) => {
    btn.setAttribute('aria-pressed', String(btn.dataset.period === period));
  });
  let text = explainFrequency(period, target);
  const o = goals.original;
  if (o && (o.period !== period || o.target !== target)) {
    text += ' Die Änderung gilt auch rückwirkend – Serie und Rekord werden neu berechnet.';
  }
  $('goal-explain').textContent = text;
}

function setFormPeriod(period) {
  goals.form.period = period;
  goals.form.target = Math.min(goals.form.target, MAX_TARGET[period]);
  renderFrequency();
}

function stepTarget(delta) {
  const { period, target } = goals.form;
  goals.form.target = Math.max(1, Math.min(MAX_TARGET[period], target + delta));
  renderFrequency();
}

async function saveGoal() {
  const btn = $('goal-save');
  const payload = { title: $('goal-name-input').value.trim(), ...goals.form };
  if (!payload.title) {
    setMessage($('goal-form-msg'), 'Bitte gib dem Ziel einen Namen.');
    $('goal-name-input').focus();
    return;
  }
  btn.disabled = true;
  try {
    if (goals.editing) {
      const habit = await api(`/api/habits/${goals.editing}`, { method: 'PATCH', body: JSON.stringify(payload) });
      replaceHabit(habit);
      if (goals.detail && goals.detail.id === habit.id) goals.detail = { ...goals.detail, ...habit };
      updateBadge();
      goBack();
    } else {
      const habit = await api('/api/habits', { method: 'POST', body: JSON.stringify(payload) });
      if (goals.habits) goals.habits.push(habit);
      updateBadge();
      // Das Formular durch das neue Ziel ersetzen: Zurück führt dann zur
      // Liste, nicht wieder ins Formular.
      replaceView('goal', habit.id);
    }
  } catch (err) {
    setMessage($('goal-form-msg'), err.message);
  } finally {
    btn.disabled = false;
  }
}

function resetDelete() {
  goals.deleteArmed = false;
  $('goal-delete').textContent = 'Ziel löschen';
  $('goal-delete-hint').textContent = 'Löscht das Ziel mit allen Einträgen.';
}

// Zwei Schritte statt eines Dialogs: der erste Tipp fragt nach, der zweite
// löscht. Nach ein paar Sekunden ohne zweiten Tipp ist die Frage wieder weg.
async function deleteGoal() {
  const id = goals.editing;
  if (!id) return;
  if (!goals.deleteArmed) {
    goals.deleteArmed = true;
    const habit = (goals.habits || []).find((h) => h.id === id);
    const entries = habit ? habit.totals.entries : 0;
    $('goal-delete').textContent = 'Wirklich löschen?';
    $('goal-delete-hint').textContent = entries
      ? `Löscht das Ziel mit ${entries === 1 ? 'einem Eintrag' : entries.toLocaleString('de-DE') + ' Einträgen'}. Das lässt sich nicht rückgängig machen.`
      : 'Das lässt sich nicht rückgängig machen.';
    setTimeout(() => { if (goals.deleteArmed && goals.editing === id) resetDelete(); }, 6000);
    return;
  }
  try {
    await api(`/api/habits/${id}`, { method: 'DELETE' });
  } catch (err) {
    setMessage($('goal-form-msg'), err.message);
    return;
  }
  goals.habits = (goals.habits || []).filter((h) => h.id !== id);
  goals.detail = null;
  updateBadge();
  switchTab('goals');
}

// --------------------------------------------------------------------------
// Ereignisse
// --------------------------------------------------------------------------

$('goal-new').addEventListener('click', () => openView('goal-form'));
$('goal-back').addEventListener('click', goBack);
$('goal-edit').addEventListener('click', () => { if (goals.detail) openView('goal-form', goals.detail.id); });
$('goal-form-back').addEventListener('click', goBack);
$('goal-cancel').addEventListener('click', goBack);
$('goal-save').addEventListener('click', saveGoal);
$('goal-name-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') saveGoal(); });
$('goal-delete').addEventListener('click', deleteGoal);
$('goal-target-minus').addEventListener('click', () => stepTarget(-1));
$('goal-target-plus').addEventListener('click', () => stepTarget(1));
document.querySelectorAll('[data-period]').forEach((btn) => {
  btn.addEventListener('click', () => setFormPeriod(btn.dataset.period));
});
// Pfeiltasten in der Symbolauswahl, wie bei einer Gruppe von Optionsfeldern.
$('goal-icons').addEventListener('keydown', (e) => {
  const step = { ArrowRight: 1, ArrowDown: 6, ArrowLeft: -1, ArrowUp: -6 }[e.key];
  if (!step) return;
  e.preventDefault();
  const index = HABIT_ICONS.indexOf(goals.form.icon);
  goals.form.icon = HABIT_ICONS[(index + step + HABIT_ICONS.length) % HABIT_ICONS.length];
  renderIconGrid();
  $('goal-icons').querySelector('[aria-checked="true"]').focus();
});
$('heat-prev').addEventListener('click', () => shiftHeat(-1));
$('heat-next').addEventListener('click', () => shiftHeat(1));
$('heat-day-add').addEventListener('click', addHeatDay);
$('heat-day-input').addEventListener('change', (e) => { if (e.target.value) selectHeatDay(e.target.value); });

// Der Verlauf passt seine Wochenzahl an die Breite an (Drehen des Handys,
// Fenstergröße am Desktop).
if ('ResizeObserver' in window) {
  let heatTimer = null;
  new ResizeObserver(([entry]) => {
    const width = entry.contentRect.width;
    if (!width || !goals.detail || $('goal-view').hidden) return;
    if (heatWeeksFor(width) === goals.heatWeeks) return;
    clearTimeout(heatTimer);
    heatTimer = setTimeout(() => loadGoalDetail(true).catch(() => {}), 200);
  }).observe($('habit-heat'));
}
