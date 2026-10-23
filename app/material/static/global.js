/* Globale Seriennummernsuche und QR-Steckbrief fremder Artikel (Phase 2 · Lieferung 1, Paket C): Angebot unter der
   eigenen Trefferliste, Bestätigung („wird mit deinem Namen protokolliert“), Steckbrief-Karte ohne Link und die
   Ansicht „fremd“ nach einem QR-Scan. Stellt window.MatGlobal bereit – anbieten(element, q, optionen), bestaetigen(q),
   suchen(q), karte(treffer) und fremd(inhalt, daten); material.js und suche.js rufen sie auf.

   Nach den Entscheidungen vom 18.10.2026: Angeboten wird die Suche zu jeder Anfrage, die dafür taugt (global_angebot
   der lokalen Suche), auch neben eigenen Treffern; sie findet nur Artikel außerhalb des eigenen Bereichs – in anderen
   Gliederungen, bei einer Freigabe nur an einem Teil der Gliederung auch in deren übrigen Ordnern. Darum heißt es
   überall „außerhalb deines Bereichs“, nicht „andere Gliederungen“; zu welcher Gliederung ein Treffer gehört, sagt
   seine Karte. Die Treffer stehen unter der eigenen Liste – ab der Trennlinie „Außerhalb deines Bereichs“, jede Karte
   gestrichelt umrandet und mit ihrer Gliederung als Marke ganz oben. Ein Treffer zeigt nur Stammdaten, Zugehörigkeit
   und ein Sperrwort (gesperrt, verloren gemeldet, ausgesondert) – es gibt nichts weiter zu sehen, also auch keinen
   Link. Gesucht wird erst nach der Bestätigung; der Server protokolliert jede Suche und jeden Steckbrief mit Namen. */
window.MatGlobal = (function () {
  "use strict";
  const { esc, api, dialog } = window.S;
  const API = "/api/material/globalsuche";
  const ERKLAERUNG = "Die Suche geht über alle Artikel außerhalb deines Bereichs – in anderen Gliederungen und in "
    + "Ordnern, für die du keine Freigabe hast – und wird mit deinem Namen protokolliert. "
    + "Treffer zeigen nur Stammdaten, Zugehörigkeit und ob der Artikel gesperrt, verloren gemeldet oder ausgesondert "
    + "ist – keine Prüfungen, Protokolle, Fotos oder Bemerkungen.";
  // Das Sperrwort als Marke in den Farben des Moduls: anthrazit gesperrt (auch verloren gemeldet), grau ausgesondert.
  const SPERRE = { gesperrt: "s-gesperrt", "verloren gemeldet": "s-gesperrt", ausgesondert: "s-ausgesondert" };

  // „2026-12-04“ → „04.12.2026“, „2026-12“ → „12/2026“ – wie in material.js, ohne Date-Objekt (keine Zeitzone).
  const fmtTag = (d) => {
    const s = String(d || "");
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}.${m[2]}.${m[1]}`;
    m = s.match(/^(\d{4})-(\d{2})$/);
    return m ? `${m[2]}/${m[1]}` : s;
  };
  // Eine übliche Seriennummer (bis 30 Zeichen) bricht im Knopftext nicht am Bindestrich um (mg-ganz), eine sehr lange schon.
  const nummer = (q) => `„<span${q.length <= 30 ? ' class="mg-ganz"' : ""}>${esc(q)}</span>“`;

  /* Rückfrage vor der Suche – ein eigener Dialog statt S.confirm: „Suchen“ ist kein Löschen, also der rote
     Hauptknopf, nicht der Knopf für Endgültiges. Abbrechen steht vorn und hat mit der Maus den Fokus. */
  function bestaetigen(q) {
    return new Promise((resolve) => {
      let ja = false;
      const dlg = dialog(`<h2>Außerhalb deines Bereichs suchen</h2>
        <p>Seriennummer <strong class="mg-nummer">${esc(q)}</strong></p>
        <p>${esc(ERKLAERUNG)}</p>
        <div class="dlg-actions"><button class="btn secondary" type="button" data-close>Abbrechen</button>
          <button class="btn" type="button" id="mg-ok">Suchen</button></div>`,
      (d, body) => {
        body.querySelector("#mg-ok").addEventListener("click", () => { ja = true; d.close(); });
      });
      dlg.addEventListener("close", () => resolve(ja), { once: true });
    });
  }

  function suchen(q) {
    return api(API, { method: "POST", body: { q, bestaetigt: true } });
  }

  /* Der Steckbrief eines fremden Artikels: gestrichelt umrandet, ganz oben die Gliederung als Marke, dann
     Inventarnummer mit Sperrwort, Produkt, Seriennummer, Kategorie, Norm, Herstellung, Lebensende und „Gehört zu …“
     mit dem Ordner; ein Teil eines Hersteller-Sets sagt das (teil_eines_sets – ohne Angaben zum Set, Entwurf H). Alles aus der Antwort wird maskiert – auch Ordnernamen fremder Gliederungen sind fremde Eingaben. */
  function karte(t) {
    // „Hersteller Modell“ und dahinter grau die Beschreibung wie überall im Modul (window.MatProdukt aus material.js),
    // maskiert.
    const p = { manufacturer: t.hersteller, model: t.modell, description: t.beschreibung };
    const name = window.MatProdukt.nameHtml(p);
    const angaben = [["Seriennummer", t.serial_no], ["Kategorie", t.kategorie], ["Norm", t.norm],
                     ["Material", t.materialart], ["Herstellung", t.hergestellt && fmtTag(t.hergestellt)],
                     ["Lebensende", t.lebensende && fmtTag(t.lebensende)]].filter(([, wert]) => wert);
    const sperre = t.sperre ? ` <span class="mat-status ${SPERRE[t.sperre] || "s-gesperrt"}">${esc(t.sperre)}</span>` : "";
    return `<article class="mg-karte">
      ${t.vorschau ? `<img class="mg-bild" src="${esc(t.vorschau)}" alt="" loading="lazy">` : '<span class="mg-bild leer" aria-hidden="true"></span>'}
      <div class="mg-text">
        <p class="mg-gl"><span class="mg-gl-marke"><span class="mat-vorlesen">Gliederung </span>${esc(t.gliederung || "ohne Gliederung")}</span></p>
        <p class="mg-kopf"><strong class="mg-inv">${esc(t.inventory_no)}</strong>${sperre}${t.demo ? ' <span class="mat-demo">DEMO</span>' : ""}</p>
        <p class="mg-produkt">${name || "–"}${window.MatProdukt.zusatzHtml(p)}${window.MatProdukt.artNr(t.artikelnummer)}</p>
        <dl class="mg-daten">${angaben.map(([k, w]) => `<div><dt>${esc(k)}</dt><dd>${esc(w)}</dd></div>`).join("")}</dl>
        <p class="mg-gehoert">Gehört zu <strong>${esc(t.gliederung || "–")}</strong>${t.ordner ? ` · ${esc(t.ordner)}` : ""}</p>
        ${t.teil_eines_sets ? '<p class="mg-set">Teil eines Hersteller-Sets</p>' : ""}
      </div></article>`;
  }

  // Die Karten mit Hinweis – auf der Trefferseite unter der Trennlinie, in der Ansicht „fremd“ allein.
  function ergebnis(d, q) {
    if (!d.treffer.length) {
      return `<p class="mat-leer">Außerhalb deines Bereichs hat kein Artikel die Seriennummer „${esc(q)}“.</p>`;
    }
    return `<div class="mg-karten">${d.treffer.map(karte).join("")}</div>
      ${d.mehr ? `<p class="help">Weitere Artikel haben diese Seriennummer – gezeigt werden die ersten ${d.treffer.length}.</p>` : ""}
      <p class="help mg-hinweis">${esc(d.hinweis || "")}</p>`;
  }

  // Trefferseite: die fremden Treffer unter der eigenen Liste, ab der Trennlinie mit Überschrift.
  function abschnitt(d, q) {
    return `<section class="mg-fremde" aria-labelledby="mg-fremde-titel">
      <h2 class="mg-trenner" id="mg-fremde-titel" tabindex="-1">Außerhalb deines Bereichs</h2>${ergebnis(d, q)}</section>`;
  }

  /* Trefferseite: unter der eigenen Liste das Angebot, auch außerhalb des eigenen Bereichs zu suchen – ein grauer
     Knopf, die Hauptsache der Seite bleibt die eigene Liste. Nach der Suche steht an seiner Stelle das Ergebnis.
     Der Hilfetext nennt kurz, was die Rückfrage (ERKLAERUNG) ausführlich sagt – mit dem Sperrzustand, den das Ergebnis
     zeigt; ebenso die Angebotszeile in den Vorschlägen (suche.js).
     optionen.exakt: ein eigener Artikel hat genau diese Seriennummer (dann sagt der Text, dass nur die anderen kommen);
     optionen.ergebnis: das Ergebnis einer früheren Suche zu q – Blättern und Sortieren der eigenen Liste zeichnen die
     Seite neu, ohne noch einmal zu suchen; optionen.gefunden(d) bekommt das Ergebnis. */
  function anbieten(element, q, optionen) {
    const o = optionen || {};
    if (!element || !q) return;
    element.setAttribute("aria-live", "polite");
    if (o.ergebnis) { element.innerHTML = abschnitt(o.ergebnis, q); return; }
    element.innerHTML = `<section class="mg-angebot" aria-label="Suche außerhalb deines Bereichs">
      ${o.exakt ? "<p>Diese Seriennummer gibt es auch in deinem Bereich (oben) – die Suche zeigt nur Artikel außerhalb davon.</p>" : ""}
      <button class="btn secondary" type="button" data-mg="suchen"><span>Außerhalb deines Bereichs nach der Seriennummer ${nummer(q)} suchen</span></button>
      <p class="help">Nur Stammdaten, Zugehörigkeit und Sperrzustand – die Suche wird mit deinem Namen protokolliert.</p>
      <div class="mg-ergebnis"></div></section>`;
    const knopf = element.querySelector('[data-mg="suchen"]');
    const aus = element.querySelector(".mg-ergebnis");
    knopf.addEventListener("click", async () => {
      if (!(await bestaetigen(q))) return;
      knopf.disabled = true;
      aus.innerHTML = '<p class="help">Suche außerhalb deines Bereichs …</p>';
      try {
        const d = await suchen(q);
        if (o.gefunden) o.gefunden(d);
        element.innerHTML = abschnitt(d, q);
        element.querySelector(".mg-trenner").focus();      // der Knopf ist weg – der Fokus geht zum Ergebnis
      } catch (e) {
        aus.innerHTML = `<p class="notice">${esc(e.message)}</p>`;
        knopf.disabled = false;
      }
    });
  }

  /* Ansicht „fremd“ (/m/<token> eines Artikels außerhalb des eigenen Bereichs): erst nichts über den Artikel, nur der
     Knopf. Der Steckbrief kommt nach dem Klick – der Knopf sagt, dass das protokolliert wird. Liegt der Artikel
     inzwischen im eigenen Bereich, geht es zu ihm. */
  function fremd(inhalt, daten) {
    const token = (daten && daten.token) || "";
    inhalt.innerHTML = `<div class="page-head"><h1>Artikel aus einem anderen Bereich</h1></div>
      <div class="mg-fremd">
        <p>Dieser Artikel gehört nicht zu deinem Bereich.</p>
        <p class="help">Der Steckbrief zeigt Stammdaten, Zugehörigkeit und ob der Artikel gesperrt, verloren gemeldet oder
          ausgesondert ist – keine Prüfungen, Protokolle, Fotos oder Bemerkungen. Wer ihn öffnet, steht mit Namen im
          Protokoll der Plattform-Verwaltung.</p>
        <p class="help">Schaden entdeckt? Sag dem Materialwart der Gliederung Bescheid.</p>
        <div class="btn-row"><button class="btn" type="button" data-mg="steckbrief">Steckbrief anzeigen (wird protokolliert)</button></div>
        <div class="mg-ergebnis" aria-live="polite"></div>
      </div>`;
    const knopf = inhalt.querySelector('[data-mg="steckbrief"]');
    const aus = inhalt.querySelector(".mg-ergebnis");
    knopf.addEventListener("click", async () => {
      knopf.disabled = true;
      try {
        const d = await api(`${API}/qr`, { method: "POST", body: { token, bestaetigt: true } });
        if (d.weiter) { location.replace(d.weiter); return; }
        aus.innerHTML = ergebnis(d, "");
        knopf.closest(".btn-row").remove();
      } catch (e) {
        aus.innerHTML = `<p class="notice">${esc(e.message)}</p>`;
        knopf.disabled = false;
      }
    });
  }

  return { anbieten, bestaetigen, suchen, karte, fremd };
})();
