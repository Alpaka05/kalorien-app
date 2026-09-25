'use strict';

/* Farbschema: hell, dunkel, OLED-Schwarz oder nach Systemeinstellung.
 *
 * Diese Datei wird im <head> geladen und blockiert absichtlich das erste
 * Zeichnen. Liefe sie erst am Seitenende, sähe man im Dunkelmodus für einen
 * Moment die helle Seite aufblitzen.
 *
 * Die Auswahl liegt im localStorage und nicht im Konto: Sie muss vor dem
 * ersten Zeichnen bekannt sein, /api/me antwortet aber erst danach – und auf
 * der Login-Seite gibt es noch gar kein Konto, das man fragen könnte. Dafür
 * gilt sie pro Gerät, was hier ohnehin passt: Handy abends dunkel, Rechner
 * tagsüber hell.
 */
(function () {
  const KEY = 'kcal-theme';
  const CHOICES = ['system', 'light', 'dark', 'oled'];
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  function stored() {
    // localStorage kann werfen (privater Modus, blockierte Cookies). Dann
    // bleibt es bei der Systemeinstellung, statt dass die Seite leer bleibt.
    try {
      const value = localStorage.getItem(KEY);
      if (CHOICES.includes(value)) return value;
    } catch (err) {
      /* ignorieren */
    }
    return 'system';
  }

  /* Dark Reader & Co. stehen still, solange die Seite selbst dunkel ist.
   *
   * Ohne dieses Signal legt die Erweiterung ihre Umkehrung über unser eigenes
   * Dunkel und macht daraus ein ausgewaschenes Grau. Umgekehrt wird die Sperre
   * im Hellmodus wieder entfernt: Wer alle Seiten per Erweiterung abdunkelt,
   * soll das hier weiter tun können, ohne dass wir uns dazwischendrängen.
   */
  function lockExtensions(active) {
    const existing = document.querySelector('meta[name="darkreader-lock"]');
    if (active && !existing) {
      const meta = document.createElement('meta');
      meta.name = 'darkreader-lock';
      document.head.appendChild(meta);
    } else if (!active && existing) {
      existing.remove();
    }
  }

  /* Farbe der Browserleiste (iOS Safari, Chrome auf Android). Ohne das bleibt
   * oben ein heller Streifen über der dunklen Seite stehen.
   *
   * Die Werte sind Kopien von --bg aus styles.css. Eine
   * prefers-color-scheme-Variante von <meta name="theme-color"> hilft hier
   * nicht: sie würde die ausdrückliche Wahl in den Einstellungen übergehen.
   */
  const BAR_COLOR = { light: '#FAF8F3', dark: '#191817', oled: '#000000' };

  function paintBrowserBar(key) {
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = BAR_COLOR[key];
  }

  function apply() {
    const choice = stored();
    // Aufgelöst wird hier, nicht im CSS: `data-theme` steht damit immer auf
    // "light" oder "dark". Das CSS braucht so nur einen Dunkel-Block, und
    // Erweiterungen sehen einen eindeutigen Zustand statt einer Mischung aus
    // Attribut und Media Query.
    //
    // OLED ist kein drittes Theme, sondern der Dunkelmodus mit schwarzem
    // Grund: data-theme bleibt "dark", damit jede Dunkel-Regel im CSS (etwa
    // der Pfeil der Auswahlfelder) weiter greift, und data-oled legt nur die
    // Flächenfarben darüber.
    const oled = choice === 'oled';
    const theme = choice === 'system' ? (media.matches ? 'dark' : 'light')
      : oled ? 'dark' : choice;
    const root = document.documentElement;
    root.dataset.theme = theme;
    if (oled) root.dataset.oled = '';
    else delete root.dataset.oled;
    // color-scheme mitziehen, damit Scrollbalken, Formularelemente und der
    // von Chrome erzwungene Dunkelmodus dasselbe annehmen wie die Seite.
    root.style.colorScheme = theme;
    paintBrowserBar(oled ? 'oled' : theme);
    lockExtensions(theme === 'dark');
  }

  // Systemwechsel (z. B. automatisch bei Sonnenuntergang) sofort mitnehmen.
  if (media.addEventListener) {
    media.addEventListener('change', apply);
  } else if (media.addListener) {
    media.addListener(apply); // Safari < 14
  }

  window.Theme = {
    get: stored,
    set(choice) {
      if (!CHOICES.includes(choice)) return;
      try {
        localStorage.setItem(KEY, choice);
      } catch (err) {
        /* ignorieren – dann gilt die Wahl nur für diese Sitzung */
      }
      apply();
    },
  };

  apply();
})();
