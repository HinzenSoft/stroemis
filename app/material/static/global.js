/* Globale Seriennummernsuche und QR-Steckbrief fremder Artikel (Phase 2 · Lieferung 1, Paket C): Angebot auf der
   Trefferseite, Bestätigung („wird mit deinem Namen protokolliert“), Steckbrief-Karte ohne Link und die Ansicht „fremd“
   nach einem QR-Scan. Stellt window.MatGlobal bereit – anbieten(element, q), bestaetigen(q), suchen(q), karte(treffer)
   und fremd(inhalt, daten); material.js und suche.js rufen sie auf.

   Ein Treffer zeigt nur Stammdaten und Zugehörigkeit (Gliederung und Ordner) – es gibt nichts weiter zu sehen, also
   auch keinen Link. Gesucht wird erst nach der Bestätigung; der Server bremst (zehn je Viertelstunde, Suche und
   Steckbrief zusammen) und protokolliert jede Suche mit Namen. */
window.MatGlobal = (function () {
  "use strict";
  const { esc, api, dialog } = window.S;
  const API = "/api/material/globalsuche";
  const ERKLAERUNG = "Die Suche geht über den Bestand aller Gliederungen und wird mit deinem Namen protokolliert. "
    + "Treffer zeigen nur Stammdaten und Zugehörigkeit – keine Prüfungen, Protokolle, Fotos oder Bemerkungen.";
  // Nur mit dem Schalter STECKBRIEF_MIT_SPERRE kommt „sperre“ mit – dann als Marke in den Farben des Moduls.
  const SPERRE = { gesperrt: "s-gesperrt", "verloren gemeldet": "s-gesperrt", ausgesondert: "s-ausgesondert" };

  // „2026-12-04“ → „04.12.2026“, „2026-12“ → „12/2026“ – wie in material.js, ohne Date-Objekt (keine Zeitzone).
  const fmtTag = (d) => {
    const s = String(d || "");
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}.${m[2]}.${m[1]}`;
    m = s.match(/^(\d{4})-(\d{2})$/);
    return m ? `${m[2]}/${m[1]}` : s;
  };

  /* Rückfrage vor der Suche – ein eigener Dialog statt S.confirm: „Global suchen“ ist kein Löschen, also der rote
     Hauptknopf, nicht der Knopf für Endgültiges. Abbrechen steht vorn und hat mit der Maus den Fokus. */
  function bestaetigen(q) {
    return new Promise((resolve) => {
      let ja = false;
      const dlg = dialog(`<h2>In allen Gliederungen suchen</h2>
        <p>Seriennummer <strong class="mg-nummer">${esc(q)}</strong></p>
        <p>${esc(ERKLAERUNG)}</p>
        <div class="dlg-actions"><button class="btn secondary" type="button" data-close>Abbrechen</button>
          <button class="btn" type="button" id="mg-ok">Global suchen</button></div>`,
      (d, body) => {
        body.querySelector("#mg-ok").addEventListener("click", () => { ja = true; d.close(); });
      });
      dlg.addEventListener("close", () => resolve(ja), { once: true });
    });
  }

  function suchen(q) {
    return api(API, { method: "POST", body: { q, bestaetigt: true } });
  }

  /* Der Steckbrief: Produktbild, Inventar- und Seriennummer, Produkt, Kategorie, Norm, Herstellung, Lebensende und
     „Gehört zu …“. Alles aus der Antwort wird maskiert – auch Ordnernamen fremder Gliederungen sind fremde Eingaben. */
  function karte(t) {
    const produkt = [t.hersteller, t.modell].filter(Boolean).join(" ");
    const angaben = [["Seriennummer", t.serial_no], ["Kategorie", t.kategorie], ["Norm", t.norm],
                     ["Material", t.materialart], ["Herstellung", t.hergestellt && fmtTag(t.hergestellt)],
                     ["Lebensende", t.lebensende && fmtTag(t.lebensende)]].filter(([, wert]) => wert);
    const sperre = t.sperre ? ` <span class="mat-status ${SPERRE[t.sperre] || "s-gesperrt"}">${esc(t.sperre)}</span>` : "";
    return `<article class="mg-karte">
      ${t.vorschau ? `<img class="mg-bild" src="${esc(t.vorschau)}" alt="" loading="lazy">` : '<span class="mg-bild leer" aria-hidden="true"></span>'}
      <div class="mg-text">
        <p class="mg-kopf"><strong class="mg-inv">${esc(t.inventory_no)}</strong>${sperre}${t.demo ? ' <span class="mat-demo">DEMO</span>' : ""}</p>
        <p class="mg-produkt">${esc(produkt || "–")}${t.artikelnummer ? ` · Art.-Nr. ${esc(t.artikelnummer)}` : ""}</p>
        <dl class="mg-daten">${angaben.map(([k, w]) => `<div><dt>${esc(k)}</dt><dd>${esc(w)}</dd></div>`).join("")}</dl>
        <p class="mg-gehoert">Gehört zu <strong>${esc(t.gliederung || "–")}</strong>${t.ordner ? ` · ${esc(t.ordner)}` : ""}</p>
      </div></article>`;
  }

  // Das Ergebnis als Abschnitt einer Seite (Trefferseite, Ansicht „fremd“).
  function ergebnis(d, q) {
    if (!d.treffer.length) {
      return `<p class="mat-leer">Auch in den anderen Gliederungen hat kein Artikel die Seriennummer „${esc(q)}“.</p>`;
    }
    return `<div class="mg-karten">${d.treffer.map(karte).join("")}</div>
      ${d.mehr ? `<p class="help">Weitere Artikel haben diese Seriennummer – gezeigt werden die ersten ${d.treffer.length}.</p>` : ""}
      <p class="help mg-hinweis">${esc(d.hinweis || "")}</p>`;
  }

  /* Trefferseite: Kein sichtbarer Artikel hat genau diese Seriennummer – das Angebot, global zu suchen. Ein grauer
     Knopf: Die Hauptsache der Seite bleibt die lokale Trefferliste. */
  function anbieten(element, q) {
    if (!element || !q) return;
    element.innerHTML = `<section class="mg-angebot" aria-label="Suche in allen Gliederungen">
      <p>Kein Artikel in deinem Bereich hat genau die Seriennummer „${esc(q)}“.</p>
      <button class="btn secondary" type="button" data-mg="suchen"><span>In allen Gliederungen nach der Seriennummer „<span${q.length <= 30 ? ' class="mg-ganz"' : ""}>${esc(q)}</span>“ suchen</span></button>
      <div class="mg-ergebnis" aria-live="polite"></div></section>`;
    const knopf = element.querySelector('[data-mg="suchen"]');
    const aus = element.querySelector(".mg-ergebnis");
    knopf.addEventListener("click", async () => {
      if (!(await bestaetigen(q))) return;
      knopf.disabled = true;
      aus.innerHTML = '<p class="help">Suche in allen Gliederungen …</p>';
      try {
        const d = await suchen(q);
        aus.innerHTML = `<h2 class="mg-titel">In allen Gliederungen</h2>${ergebnis(d, q)}`;
        knopf.remove();
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
        <p class="help">Der Steckbrief zeigt Stammdaten und Zugehörigkeit – keine Prüfungen, Protokolle, Fotos oder
          Bemerkungen. Wer ihn öffnet, steht mit Namen im Protokoll der Plattform-Verwaltung.</p>
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
