'use strict';

const $ = (id) => document.getElementById(id);
let currentEmail = '';

function setMessage(text, kind = 'error') {
  const el = $('auth-msg');
  el.textContent = text || '';
  el.className = 'message' + (text ? ' ' + kind : '');
}

async function post(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Da ist etwas schiefgelaufen.');
  return data;
}

$('step-email').addEventListener('submit', async (event) => {
  event.preventDefault();
  setMessage('');
  const button = $('request-btn');
  button.disabled = true;
  button.textContent = 'Sende Code…';
  try {
    const data = await post('/api/auth/request-code', { email: $('email-input').value });
    currentEmail = data.email;
    $('step-email').hidden = true;
    $('step-code').hidden = false;
    $('code-hint').textContent =
      data.delivery === 'smtp'
        ? `Wir haben einen 6-stelligen Code an ${currentEmail} geschickt.`
        : 'Es ist kein Mailserver konfiguriert – der Code steht im Server-Log ' +
          '(docker compose logs kalorien-tagebuch).';
    $('code-input').focus();
  } catch (err) {
    setMessage(err.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Code anfordern';
  }
});

$('step-code').addEventListener('submit', async (event) => {
  event.preventDefault();
  setMessage('');
  const button = $('verify-btn');
  button.disabled = true;
  button.textContent = 'Prüfe…';
  try {
    await post('/api/auth/verify', { email: currentEmail, code: $('code-input').value });
    window.location.href = '/';
  } catch (err) {
    setMessage(err.message);
    button.disabled = false;
    button.textContent = 'Anmelden';
  }
});

$('back-btn').addEventListener('click', () => {
  $('step-code').hidden = true;
  $('step-email').hidden = false;
  $('code-input').value = '';
  setMessage('');
  $('email-input').focus();
});

$('code-input').addEventListener('input', (event) => {
  event.target.value = event.target.value.replace(/\D/g, '').slice(0, 6);
});
