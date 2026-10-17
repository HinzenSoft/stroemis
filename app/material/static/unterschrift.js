/* Unterschrift zeichnen – gemeinsam für das Profil und die Seiten des Moduls Material.
   MatUnterschrift.zeichnen({titel, hinweis, bestehend, speichern}) öffnet einen eigenen Dialog mit dem
   Signatur-Pad (vendor/signature_pad) und liefert das Bild als data:-URL (PNG, durchsichtiger Grund) oder
   null bei Abbruch. Ein eigener <dialog>, nicht #dlg: Das Profil hat keinen, und im Modul liegt der Pad
   oft über einem schon offenen Dialog (Aussondern).
   Mit speichern (async, bekommt das Bild) bleibt der Dialog offen, bis der Server es angenommen hat –
   lehnt er ab („leer“), zeigt der Toast den Grund, und es lässt sich gleich weiterzeichnen. */
window.MatUnterschrift = (function () {
  "use strict";
  const esc = (s) => S.esc(s);
  let zaehler = 0;

  /* Die Fläche hat sich geändert (Telefon gedreht): das Gezeichnete so umrechnen, dass es ganz hineinpasst –
     gleichmäßig verkleinert (nie vergrößert, nie verzerrt) und im selben Abstand über der Linie. */
  function umrechnen(daten, alt, neu) {
    const s = Math.min(1, neu.b / alt.b, neu.linie / alt.linie);
    const mal = (v) => (typeof v === "number" ? v * s : v);
    return daten.map((g) => Object.assign({}, g, {
      minWidth: mal(g.minWidth), maxWidth: mal(g.maxWidth), dotSize: mal(g.dotSize),
      points: g.points.map((p) => Object.assign({}, p, { x: p.x * s, y: neu.linie + (p.y - alt.linie) * s })),
    }));
  }

  function zeichnen(opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      if (!window.SignaturePad) { S.toast("Das Unterschriftsfeld ließ sich nicht laden – bitte die Seite neu laden.", true); resolve(null); return; }
      const dlg = document.createElement("dialog");
      const tid = `us-titel-${++zaehler}`;
      dlg.className = "us-dlg";
      dlg.setAttribute("aria-labelledby", tid);
      dlg.innerHTML = `<div class="dlg-body"><h2 id="${tid}">${esc(opts.titel || "Unterschrift")}</h2>
        ${opts.hinweis ? `<p class="help us-hinweis">${esc(opts.hinweis)}</p>` : ""}
        <div class="us-flaeche">
          <canvas class="us-canvas" role="img" aria-label="Feld zum Unterschreiben – mit Finger, Stift oder Maus"></canvas>
          <span class="us-linie" aria-hidden="true"></span>
          <span class="us-platzhalter" aria-hidden="true">Hier unterschreiben</span></div>
        ${opts.bestehend ? `<p class="us-bisher small muted">Bisher: <img src="${esc(opts.bestehend)}" alt="bisherige Unterschrift"></p>` : ""}
        <div class="dlg-actions us-aktionen"><button type="button" class="btn secondary" data-us="leeren" disabled>Leeren</button>
          <button type="button" class="btn secondary" data-us="ab">Abbrechen</button>
          <button type="button" class="btn" data-us="ok" disabled>Übernehmen</button></div></div>`;
      document.body.appendChild(dlg);
      const canvas = dlg.querySelector("canvas");
      const linie = dlg.querySelector(".us-linie");
      const platz = dlg.querySelector(".us-platzhalter");
      const knopf = (k) => dlg.querySelector(`[data-us="${k}"]`);
      const pad = new window.SignaturePad(canvas, { penColor: "rgb(20, 30, 80)", minWidth: 0.9, maxWidth: 2.8, throttle: 12 });
      let ergebnis = null;
      let laeuft = false;

      const zustand = () => {
        const leer = pad.isEmpty();
        knopf("ok").disabled = leer || laeuft;
        knopf("leeren").disabled = leer || laeuft;
        knopf("ab").disabled = laeuft;
        platz.hidden = !leer;
      };
      /* Die Zeichenfläche hat so viele Pixel wie das Gerät (devicePixelRatio) – sonst wird der Strich auf dem
         Telefon unscharf und sitzt versetzt neben dem Finger. Ändert sich die Fläche (Telefon gedreht), bleibt
         Gezeichnetes erhalten und wird so umgerechnet, dass es ganz hineinpasst – sonst schnitte die schmalere
         Fläche das Ende der Unterschrift ab, und abgeschnitten käme sie ins Protokoll. */
      let alt = null;
      function anpassen() {
        const dpr = Math.max(window.devicePixelRatio || 1, 1);
        const b = canvas.offsetWidth, h = canvas.offsetHeight;
        if (!b || !h || (alt && alt.b === b && alt.h === h && alt.dpr === dpr)) return;
        // Die Linie liegt über der Fläche; ihre Höhe in der Fläche ist der Anker beim Umrechnen.
        const neu = { b, h, dpr, linie: Math.max(1, linie.getBoundingClientRect().bottom - canvas.getBoundingClientRect().top) };
        let daten = pad.toData();
        if (alt && daten.length && (alt.b !== b || alt.h !== h)) daten = umrechnen(daten, alt, neu);
        alt = neu;
        canvas.width = Math.round(b * dpr);
        canvas.height = Math.round(h * dpr);
        canvas.getContext("2d").scale(dpr, dpr);
        pad.clear();
        if (daten.length) pad.fromData(daten);
        zustand();
      }
      /* Die Berührung gehört ganz dem Pad: Endet ein Strich mit Schwung, wertete der Browser das sonst als Wischen
         (touch-action allein hält nur das Rollen auf), und das nächste Tippen – etwa auf „Übernehmen“ – ginge im
         Abbremsen dieses Wischens unter, ohne Klick. Die Zeiger-Ereignisse fürs Zeichnen kommen trotzdem an. */
      const schlucken = (e) => { if (e.cancelable) e.preventDefault(); };
      canvas.addEventListener("touchstart", schlucken, { passive: false });
      canvas.addEventListener("touchmove", schlucken, { passive: false });
      pad.addEventListener("beginStroke", () => { platz.hidden = true; });
      pad.addEventListener("endStroke", zustand);
      knopf("leeren").addEventListener("click", () => { pad.clear(); zustand(); });
      knopf("ab").addEventListener("click", () => dlg.close());
      knopf("ok").addEventListener("click", async () => {
        if (pad.isEmpty() || laeuft) return;
        const bild = pad.toDataURL("image/png");
        if (opts.speichern) {
          laeuft = true;
          zustand();
          knopf("ok").textContent = "Wird gespeichert …";
          try { await opts.speichern(bild); }
          catch (e) { S.toast(e.message, true); laeuft = false; knopf("ok").textContent = "Übernehmen"; zustand(); return; }
        }
        ergebnis = bild;
        dlg.close();
      });
      // Größe der Fläche beobachten (Drehen, Fenster, Schrift geladen); ohne ResizeObserver genügt „resize“.
      const beobachter = window.ResizeObserver ? new ResizeObserver(() => anpassen()) : null;
      window.addEventListener("resize", anpassen);
      // Escape schließt wie „Abbrechen“ – nur nicht, während das Bild schon unterwegs ist.
      dlg.addEventListener("cancel", (e) => { if (laeuft) e.preventDefault(); });
      dlg.addEventListener("close", () => {
        window.removeEventListener("resize", anpassen);
        if (beobachter) beobachter.disconnect();
        pad.off();
        dlg.remove();
        resolve(ergebnis);
      });
      dlg.showModal();
      anpassen();
      if (beobachter) beobachter.observe(canvas);
      zustand();
    });
  }

  return { zeichnen };
})();
