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

  /* Striche umrechnen: x mal s, y im s-fachen Abstand zur Linie (von.linie → nach.linie). Die Strichstärke bleibt die
     des Stifts – sonst wäre ein Strich, der auf der kleinen Fläche dazukam, nach dem Aufklappen fast doppelt so dick. */
  function umrechnen(daten, s, von, nach) {
    return daten.map((g) => Object.assign({}, g, {
      points: g.points.map((p) => Object.assign({}, p, { x: p.x * s, y: nach.linie + (p.y - von.linie) * s })),
    }));
  }

  /* Wie groß die Unterschrift auf einer Fläche stehen kann: in Originalgröße, wenn sie hineinpasst, sonst gleichmäßig
     so weit verkleinert, dass sie ganz hineinpasst (nie vergrößert, nie verzerrt) – im selben Abstand über der Linie. */
  function massstab(daten, linie, flaeche) {
    const rand = 4;                  // halbe Strichstärke und etwas Luft
    let rechts = 0, oben = 0, unten = 0;
    daten.forEach((g) => g.points.forEach((p) => {
      rechts = Math.max(rechts, p.x);
      oben = Math.max(oben, linie - p.y);
      unten = Math.max(unten, p.y - linie);
    }));
    let s = 1;
    if (rechts + rand > flaeche.b) s = Math.min(s, (flaeche.b - rand) / Math.max(rechts, 1));
    if (oben + rand > flaeche.linie) s = Math.min(s, (flaeche.linie - rand) / Math.max(oben, 1));
    if (unten + rand > flaeche.h - flaeche.linie) s = Math.min(s, (flaeche.h - flaeche.linie - rand) / Math.max(unten, 1));
    return Math.max(s, 0.05);
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
         Telefon unscharf und sitzt versetzt neben dem Finger. Ändert sich die Fläche (Telefon gedreht, Faltgerät
         auf- oder zugeklappt), bleibt Gezeichnetes erhalten und wird so umgerechnet, dass es ganz hineinpasst –
         sonst schnitte die schmalere Fläche das Ende der Unterschrift ab, und abgeschnitten käme sie ins Protokoll.
         Gerechnet wird immer von der Bezugsfassung aus (die Striche in der Größe, in der sie gezeichnet wurden),
         nicht von der zuletzt gezeigten: Sonst schrumpfte die Unterschrift bei jedem Zu- und Aufklappen weiter und
         wüchse auf der großen Fläche nie zurück. */
      let flaeche = null;            // wie die Fläche gerade ist: b, h, dpr, linie – und s, der Maßstab des Gezeigten
      let bezug = null;              // { daten, linie }: die Striche in Originalgröße, y bezogen auf diese Linie
      function anpassen() {
        const dpr = Math.max(window.devicePixelRatio || 1, 1);
        const b = canvas.offsetWidth, h = canvas.offsetHeight;
        if (!b || !h || (flaeche && flaeche.b === b && flaeche.h === h && flaeche.dpr === dpr)) return;
        // Die Linie liegt über der Fläche; ihre Höhe in der Fläche ist der Anker beim Umrechnen.
        const neu = { b, h, dpr, linie: Math.max(1, linie.getBoundingClientRect().bottom - canvas.getBoundingClientRect().top), s: 1 };
        if (bezug && bezug.daten.length) neu.s = massstab(bezug.daten, bezug.linie, neu);
        flaeche = neu;
        canvas.width = Math.round(b * dpr);
        canvas.height = Math.round(h * dpr);
        canvas.getContext("2d").scale(dpr, dpr);
        pad.clear();
        if (bezug && bezug.daten.length) pad.fromData(umrechnen(bezug.daten, neu.s, bezug, neu));
        zustand();
      }
      // Nach jedem Strich: alles, was auf der Fläche steht, zurück in die Bezugsgröße – ein Strich auf der
      // verkleinerten Fläche wächst beim Aufklappen mit dem Rest.
      function bezugMerken() {
        const daten = pad.toData();
        if (!flaeche || !daten.length) { bezug = null; return; }
        const linieBezug = bezug ? bezug.linie : flaeche.linie;
        bezug = { linie: linieBezug, daten: umrechnen(daten, 1 / flaeche.s, flaeche, { linie: linieBezug }) };
      }
      /* Die Berührung gehört ganz dem Pad: Endet ein Strich mit Schwung, wertete der Browser das sonst als Wischen
         (touch-action allein hält nur das Rollen auf), und das nächste Tippen – etwa auf „Übernehmen“ – ginge im
         Abbremsen dieses Wischens unter, ohne Klick. Die Zeiger-Ereignisse fürs Zeichnen kommen trotzdem an. */
      const schlucken = (e) => { if (e.cancelable) e.preventDefault(); };
      canvas.addEventListener("touchstart", schlucken, { passive: false });
      canvas.addEventListener("touchmove", schlucken, { passive: false });
      pad.addEventListener("beginStroke", () => { platz.hidden = true; });
      pad.addEventListener("endStroke", () => { bezugMerken(); zustand(); });
      knopf("leeren").addEventListener("click", () => { pad.clear(); bezug = null; zustand(); });
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
      /* Fokus beim Öffnen: showModal() nähme das erste Bedienelement – „Leeren“ ist ausgegraut, also „Abbrechen“ (Reste
         vor dem finalen Test, 5). Am Rechner bekommt ihn die Zeichenfläche (tabindex -1: nicht in der Tab-Reihenfolge, die
         Vorlesehilfe sagt, wozu sie da ist; Tab führt weiter zu den Knöpfen), am Touchgerät der Titel wie in jedem Dialog
         (S.dialog in common.js) – so springt nichts an und nichts wird markiert, bevor der Finger zeichnet. */
      const start = window.matchMedia("(pointer: coarse)").matches ? dlg.querySelector("h2") : canvas;
      start.tabIndex = -1;
      start.autofocus = true;
      dlg.showModal();
      anpassen();
      if (beobachter) beobachter.observe(canvas);
      zustand();
    });
  }

  return { zeichnen };
})();
