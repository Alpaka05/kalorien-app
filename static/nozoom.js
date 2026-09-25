'use strict';

/* Zoomen per Geste abschalten – ausdrücklich so gewünscht.
 *
 * Die App ist fürs Handy gebaut und hat überall mindestens 16px Schrift in
 * Feldern. Ein versehentliches Aufziehen mit zwei Fingern ließ die Seite
 * seitlich überstehen, und man musste jedes Mal von Hand zurückzoomen.
 *
 * Drei Schichten, weil kein Browser alle Wege gleich behandelt:
 *  - <meta name="viewport" … user-scalable=no> reicht für Chrome auf Android,
 *    wird von iOS Safari aber seit iOS 10 ignoriert.
 *  - touch-action: pan-x pan-y in styles.css lässt nur Scrollen zu und
 *    unterbindet damit auch das Doppeltippen zum Zoomen.
 *  - Für iOS bleibt nur, die Geste selbst abzufangen: Safari meldet sie als
 *    gesturestart/gesturechange; zusätzlich jede Bewegung mit mehr als einem
 *    Finger.
 */
(function () {
  const block = (e) => e.preventDefault();
  document.addEventListener('gesturestart', block, { passive: false });
  document.addEventListener('gesturechange', block, { passive: false });
  document.addEventListener(
    'touchmove',
    (e) => {
      if (e.touches.length > 1) e.preventDefault();
    },
    { passive: false }
  );
})();
