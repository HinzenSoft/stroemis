/* Diktat – Spracheingabe für Textfelder über die Web Speech API des Browsers.
   Gedacht für draußen am Gewässer: Handschuhe, nasse Finger, eine Hand. Ein Knopf neben dem Feld
   startet die Erkennung; der erkannte Text landet hinter dem vorhandenen, die Zeile darunter zeigt,
   was der Browser gerade versteht. Die Erkennung selbst macht der Browser – Chrome und Safari
   schicken das Audio dafür je nach Gerät an Google bzw. Apple. Kann der Browser es auf dem Gerät
   (Chrome ab 139 mit Sprachpaket), wird das bevorzugt. Ohne Unterstützung (Firefox) erscheint kein
   Knopf; über die Einstellung SPRACHEINGABE lässt sich alles abschalten.
   Schnittstelle: Diktat.knopf(zielId) → HTML des Knopfs, Diktat.hinweis() → Hilfetext,
   Diktat.anbinden(container) → Klicks im Container übernehmen, Diktat.stopp() → Erkennung beenden. */
(function () {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const cfg = window.STROEMIS || {};
  const an = !!SR && cfg.spracheingabe !== false && window.isSecureContext;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const toast = (msg, fehler) => { if (window.S && S.toast) S.toast(msg, fehler); };
  let lokal = false;      // Erkennung auf dem Gerät möglich? Wird beim Laden gefragt, nicht beim Klick:
  let aktiv = null;       // { rec, feld, knopf, vorschau, basis, stoppt } der laufenden Erkennung

  function knopf(zielId, beschriftung) {
    if (!an) return "";
    return `<button type="button" class="btn secondary small diktat" data-diktat="${esc(zielId)}" aria-pressed="false"
      title="Diktieren – der Browser erkennt die Sprache, je nach Gerät über Google oder Apple.">
      <span class="diktat-punkt" aria-hidden="true"></span><span class="diktat-text">${esc(beschriftung || "Diktieren")}</span></button>`;
  }

  function hinweis() {
    if (!an) return "";
    return `<div class="help diktat-hinweis">Diktieren: Die Spracherkennung übernimmt der Browser – auf Android meist über Google,
      auf dem iPhone über Apple. Der Text lässt sich danach wie getippt ändern.</div>`;
  }

  /* Die Vorschauzeile direkt unter dem Feld – einmal angelegt, dann wiederverwendet. */
  function vorschauFuer(feld) {
    let v = feld.nextElementSibling;
    if (!v || !v.classList.contains("diktat-vorschau")) {
      v = document.createElement("div");
      v.className = "diktat-vorschau";
      v.setAttribute("aria-live", "polite");
      v.hidden = true;
      feld.insertAdjacentElement("afterend", v);
    }
    return v;
  }

  function zeichne(a, zustand) {   // "wartet" | "an" | "aus"
    a.knopf.classList.toggle("an", zustand !== "aus");
    a.knopf.setAttribute("aria-pressed", zustand !== "aus" ? "true" : "false");
    a.knopf.querySelector(".diktat-text").textContent = zustand === "an" ? "Stopp" : zustand === "wartet" ? "…" : "Diktieren";
    if (zustand === "aus") a.vorschau.hidden = true;
  }

  /* Alle Ergebnisse der Sitzung neu zusammensetzen statt anzuhängen: Android liefert endgültige
     Stücke gern doppelt, und so steht jedes Wort genau einmal hinter dem Ausgangstext. */
  function uebernehmen(a, ev) {
    let fertig = "", vorlaeufig = "";
    for (let i = 0; i < ev.results.length; i++) {
      const r = ev.results[i];
      if (r.isFinal) fertig += r[0].transcript + " "; else vorlaeufig += r[0].transcript;
    }
    fertig = fertig.trim();
    const neu = fertig ? (a.basis ? a.basis.replace(/\s+$/, "") + " " + fertig : fertig) : a.basis;
    if (a.feld.value !== neu) {
      a.feld.value = neu;
      a.feld.dispatchEvent(new Event("input", { bubbles: true }));
      a.feld.scrollTop = a.feld.scrollHeight;
    }
    a.vorschau.textContent = vorlaeufig.trim() ? "… " + vorlaeufig.trim() : "Sprich jetzt …";
    a.vorschau.hidden = false;
  }

  function beenden(a) {
    if (aktiv !== a) return;
    zeichne(a, "aus");
    aktiv = null;
  }

  function start(k) {
    const feld = document.getElementById(k.dataset.diktat);
    if (!feld || feld.readOnly || feld.disabled) return;
    stopp();
    const rec = new SR();
    rec.lang = "de-DE";
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    if (lokal) { try { rec.processLocally = true; } catch (e) { /* dann eben über den Anbieter */ } }
    const a = { rec, feld, knopf: k, vorschau: vorschauFuer(feld), basis: feld.value, stoppt: false };
    aktiv = a;
    zeichne(a, "wartet");
    rec.onstart = () => { if (aktiv === a && !a.stoppt) zeichne(a, "an"); };
    rec.onresult = (ev) => { if (aktiv === a) uebernehmen(a, ev); };
    rec.onerror = (ev) => {
      if (aktiv !== a) return;
      const art = ev.error;
      if (art === "not-allowed" || art === "service-not-allowed") toast("Das Mikrofon ist für diese Seite nicht freigegeben – bitte in den Browsereinstellungen erlauben.", true);
      else if (art === "network") toast("Die Spracherkennung braucht eine Netzverbindung.", true);
      else if (art === "language-not-supported") toast("Deutsch kennt die Spracherkennung dieses Browsers nicht.", true);
      else if (art === "audio-capture") toast("Kein Mikrofon gefunden.", true);
      else if (art !== "no-speech" && art !== "aborted") toast("Spracherkennung: " + art, true);
    };
    rec.onend = () => beenden(a);
    // Der Start muss unmittelbar auf den Klick folgen (Safari verlangt eine Nutzeraktion).
    try { rec.start(); }
    catch (e) { beenden(a); toast("Die Spracherkennung ließ sich nicht starten.", true); }
  }

  function stopp() {
    if (!aktiv || aktiv.stoppt) return;
    const a = aktiv;
    a.stoppt = true;
    zeichne(a, "wartet");
    try { a.rec.stop(); } catch (e) { beenden(a); }
    // Meldet der Browser das Ende nicht, räumt der Zeitgeber auf – der Knopf darf nicht hängen bleiben.
    setTimeout(() => beenden(a), 1500);
  }

  const angebunden = new WeakSet();
  function anbinden(container) {
    if (!an || !container || angebunden.has(container)) return;
    angebunden.add(container);
    container.addEventListener("click", (e) => {
      const k = e.target.closest("[data-diktat]");
      if (!k || !container.contains(k)) return;
      e.preventDefault();
      if (aktiv && aktiv.knopf === k) stopp(); else start(k);
    });
    const dlg = container.closest("dialog");
    if (dlg) dlg.addEventListener("close", stopp);
  }

  if (an) {
    // Vorab fragen, ob das Gerät selbst erkennen kann – beim Klick soll nichts mehr warten.
    if (typeof SR.available === "function") {
      try { Promise.resolve(SR.available({ langs: ["de-DE"], processLocally: true })).then((s) => { lokal = s === "available"; }, () => {}); }
      catch (e) { /* ältere Fassung der Schnittstelle */ }
    }
    document.addEventListener("visibilitychange", () => { if (document.hidden) stopp(); });
  }
  window.Diktat = { an, knopf, hinweis, anbinden, stopp };
})();
