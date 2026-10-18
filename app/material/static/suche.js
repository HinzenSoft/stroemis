/* Vorschläge im Suchfeld des Moduls Material (Kopfzeile jeder Modulseite): Schon bei Teileingaben – ab zwei Zeichen –
   erscheinen unter dem Feld bis zu acht Artikel als Steckbrief: Produktfoto, Inventarnummer, Produkt, Seriennummer,
   Status und Ablage, der getippte Teil der Nummern hervorgehoben. Grundlage ist dieselbe Suche wie die Trefferseite
   (/api/material/suche: Serien-, Inventar-, Herstellernummer, auch Teile davon).

   Bedienung wie ein Kombinationsfeld (ARIA combobox/listbox): Pfeiltasten wählen, Enter öffnet den gewählten Artikel –
   ohne Wahl geht Enter wie bisher zur Trefferseite (ein eindeutiger Treffer öffnet dort direkt, mit dem Angebot der
   globalen Suche unter dem Kopf) –, Escape schließt.
   Mit Maus oder Finger öffnet ein Tipp den Artikel; „Alle Treffer“ führt zur Trefferseite. Ohne JavaScript bleibt das
   Feld ein gewöhnliches Suchformular.

   Phase 2 (Entscheidung vom 18.10.2026): Taugt die Anfrage für die globale Suche (global_angebot der Suche – nicht für
   die Material-Verwaltung, die ohnehin alles sieht), steht unter den eigenen Vorschlägen und „Alle Treffer“ – auch
   neben einem eigenen Artikel mit genau dieser Nummer – das Angebot, außerhalb des eigenen Bereichs zu suchen (nicht
   „in anderen Gliederungen“: Wer nur einen Teil einer Gliederung sieht, findet auch deren übrige Ordner). Enter oder
   Tipp darauf fragt nach (MatGlobal.bestaetigen, global.js). Danach bleiben die eigenen Vorschläge stehen; statt des
   Angebots folgen die Trennzeile „Außerhalb deines Bereichs“ und die fremden Steckbriefe – gestrichelt umrandet, die
   Gliederung oben, ohne Link (aria-disabled, mit den Pfeiltasten trotzdem wählbar zum Vorlesen). Eine globale Antwort
   kommt nie in den Zwischenspeicher: Sie gilt nur, solange die Anfrage unverändert im Feld steht. */
(function () {
  "use strict";
  const form = document.querySelector("form.mat-suche");
  const feld = form && form.querySelector('input[name="q"]');
  if (!feld) return;
  const esc = window.S.esc;
  const MIN = 2;
  const ANZAHL = 8;
  const STATUS = { einsatzbereit: "einsatzbereit", bald_faellig: "bald fällig", ueberfaellig: "überfällig", neu: "neu",
                   gesperrt: "gesperrt", lebensdauer: "Lebensdauer erreicht", ausgesondert: "ausgesondert" };

  const liste = document.createElement("ul");
  liste.className = "mat-vorschlaege";
  liste.id = "mat-vorschlaege";
  liste.setAttribute("role", "listbox");
  liste.setAttribute("aria-label", "Vorschläge");
  liste.hidden = true;
  form.appendChild(liste);
  feld.setAttribute("role", "combobox");
  feld.setAttribute("aria-autocomplete", "list");
  feld.setAttribute("aria-controls", liste.id);
  feld.setAttribute("aria-expanded", "false");

  const zwischen = new Map();          // Anfrage → Antwort, solange die Seite steht
  let laufend = null;                  // AbortController der letzten Anfrage – eine ältere Antwort zählt nicht mehr
  let warten = 0;
  let aktiv = -1;
  let optionen = [];
  let global = null;                   // { q, html } – der fremde Teil zu q (Ergebnis oder Meldung), bis weitergetippt wird

  // Der getippte Teil in einer Nummer hervorgehoben – ohne Rücksicht auf Groß/klein, nur an der ersten Stelle.
  function markiert(wert, q) {
    const text = String(wert || "");
    const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
    if (i < 0) return esc(text);
    return `${esc(text.slice(0, i))}<mark>${esc(text.slice(i, i + q.length))}</mark>${esc(text.slice(i + q.length))}`;
  }

  // Die Artikelnummer des Herstellers nur, wenn sie der Treffer ist – sonst kürzte sie die Produktzeile unnötig.
  const trifft = (wert, q) => Boolean(wert) && String(wert).toLowerCase().includes(q.toLowerCase());

  function karte(a, q, i) {
    const produkt = `${a.manufacturer || ""} ${a.model || ""}`.trim();
    return `<li role="option" id="mv-${i}" aria-selected="false" data-href="/material/artikel/${a.id}">
      <a href="/material/artikel/${a.id}" tabindex="-1">
        ${a.vorschau ? `<img class="mv-bild" src="${esc(a.vorschau)}" alt="" loading="lazy">` : '<span class="mv-bild leer" aria-hidden="true"></span>'}
        <span class="mv-text">
          <span class="mv-kopf"><strong class="mv-inv">${markiert(a.inventory_no, q)}</strong>
            <span class="mat-status s-${esc(a.status)}">${esc(STATUS[a.status] || a.status)}</span>${a.rueckruf ? ' <span class="mat-rr-marke">Rückruf</span>' : ""}${a.demo ? ' <span class="mat-demo">DEMO</span>' : ""}</span>
          <span class="mv-produkt">${esc(produkt || "–")}${trifft(a.article_no, q) ? ` · Art.-Nr. ${markiert(a.article_no, q)}` : ""}</span>
          <span class="mv-zeile">Seriennummer ${markiert(a.serial_no, q)}${a.pfad ? ` · ${esc(a.pfad)}` : ""}</span>
        </span></a></li>`;
  }

  // Das Angebot der globalen Suche als eigene Zeile unter den eigenen Vorschlägen – ein Knopf statt eines Links: Er
  // führt nirgendwohin, er fragt nach. Eine übliche Seriennummer bricht nicht am Bindestrich um (mg-ganz, global.css),
  // eine sehr lange schon. exakt: ein eigener Artikel hat genau diese Nummer.
  function angebotZeile(q, i, exakt) {
    return `<li role="option" id="mv-${i}" aria-selected="false" class="mv-global" data-global="1">
      <button type="button" tabindex="-1"><strong>Außerhalb deines Bereichs nach der Seriennummer „<span${q.length <= 30 ? ' class="mg-ganz"' : ""}>${esc(q)}</span>“ suchen</strong>
        <span class="mv-zeile">${exakt ? "Zeigt nur Artikel außerhalb deines Bereichs" : "Nur Stammdaten, Zugehörigkeit und Sperrzustand"} – die Suche wird protokolliert.</span></button></li>`;
  }

  // Erst die eigenen Vorschläge und „Alle Treffer“, darunter das Angebot – oder nach der Suche die fremden Treffer.
  function zeigen(d, q) {
    const treffer = (d.treffer || []).slice(0, ANZAHL);
    let html = treffer.map((a, i) => karte(a, q, i)).join("");
    if (treffer.length) {
      html += `<li role="option" id="mv-${treffer.length}" aria-selected="false" class="mv-alle" data-alle="1">
      <a href="/material/suche?q=${encodeURIComponent(q)}" tabindex="-1">${d.gesamt > treffer.length ? `Alle ${d.gesamt} Treffer anzeigen` : "Als Trefferliste anzeigen"}</a></li>`;
    } else {
      html = `<li class="mv-leer" role="presentation">Kein Artikel in deinem Bereich mit „${esc(q)}“ in Serien-, Inventar- oder Herstellernummer.</li>`;
    }
    if (global && global.q === q) html += global.html;
    else if (d.global_angebot && window.MatGlobal) html += angebotZeile(q, treffer.length ? treffer.length + 1 : 0, d.exakt_lokal);
    listeZeigen(html);
  }

  function listeZeigen(html) {
    liste.innerHTML = html;
    optionen = Array.from(liste.querySelectorAll('[role="option"]'));
    aktiv = -1;
    feld.removeAttribute("aria-activedescendant");
    liste.hidden = false;
    feld.setAttribute("aria-expanded", "true");
    hoeheBegrenzen();
  }

  /* Die Liste endet über der Tastatur: höchstens bis zum unteren Rand des sichtbaren Ausschnitts (visualViewport – auf
     dem iPhone schrumpft nur er, nicht das Fenster), mindestens aber so hoch wie zwei Steckbriefe. Vorher galten 70 %
     der Fensterhöhe, und „Alle Treffer“ lag am Telefon hinter der Tastatur. */
  function hoeheBegrenzen() {
    if (liste.hidden) return;
    const vv = window.visualViewport;
    const unten = vv ? vv.offsetTop + vv.height : window.innerHeight;
    const frei = unten - liste.getBoundingClientRect().top - 8;
    liste.style.maxHeight = `${Math.round(Math.max(130, Math.min(540, frei)))}px`;
  }
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", hoeheBegrenzen);
    window.visualViewport.addEventListener("scroll", hoeheBegrenzen);
  }
  window.addEventListener("resize", hoeheBegrenzen);
  window.addEventListener("scroll", hoeheBegrenzen, { passive: true });   // Android rollt das Feld nach dem Öffnen der Tastatur ins Bild

  function schliessen() {
    if (laufend) laufend.abort();
    clearTimeout(warten);
    liste.hidden = true;
    feld.setAttribute("aria-expanded", "false");
    feld.removeAttribute("aria-activedescendant");
    aktiv = -1;
  }

  function waehlen(i) {
    if (!optionen.length) return;
    aktiv = (i + optionen.length) % optionen.length;
    optionen.forEach((o, n) => o.setAttribute("aria-selected", n === aktiv ? "true" : "false"));
    feld.setAttribute("aria-activedescendant", optionen[aktiv].id);
    optionen[aktiv].scrollIntoView({ block: "nearest" });
  }

  /* --- Globale Suche (global.js) --- */
  const meldungZeile = (text) => `<li class="mv-leer" role="presentation">${esc(text)}</li>`;

  // Der fremde Teil unter den eigenen Vorschlägen: die Trennzeile, dann Steckbriefe ohne Link – wählbar zum Vorlesen,
  // aber nicht zu öffnen (aria-disabled); darunter der Hinweis.
  const TRENNER = '<li class="mv-trenner" role="presentation">Außerhalb deines Bereichs</li>';
  function globalHtml(d, q) {
    if (!d.treffer.length) return TRENNER + meldungZeile(`Außerhalb deines Bereichs hat kein Artikel die Seriennummer „${q}“.`);
    return TRENNER + d.treffer.map((t, i) => `<li role="option" id="mv-g${i}" aria-selected="false" aria-disabled="true"
        class="mv-steckbrief">${window.MatGlobal.karte(t)}</li>`).join("")
      + (d.mehr ? meldungZeile(`Weitere Artikel haben diese Seriennummer – gezeigt werden die ersten ${d.treffer.length}.`) : "")
      + meldungZeile(d.hinweis || "");
  }

  /* Die Liste zu q neu: die eigenen Vorschläge aus dem Zwischenspeicher, darunter der fremde Teil. Gerollt wird nur so
     weit, dass die Trennzeile und die Zeile danach (erste Karte oder Meldung) ganz zu sehen sind – höchstens, bis die
     Trennzeile oben steht. Passt das ohne Rollen, bleibt die Liste, wo sie ist, und die eigenen Vorschläge bleiben im
     Blick (Prüfung der Nachbesserung: vorher sprang sie immer bis zur Trennzeile und schnitt die eigenen ab). */
  function mitFremden(q) {
    if (zwischen.has(q)) zeigen(zwischen.get(q), q);
    else listeZeigen(global.html);
    const t = liste.querySelector(".mv-trenner");
    if (!t) return;
    const oben = liste.getBoundingClientRect().top + liste.clientTop;     // Innenkante, ohne Rahmen
    const fehlt = (t.nextElementSibling || t).getBoundingClientRect().bottom - (oben + liste.clientHeight);
    const bisTrenner = t.getBoundingClientRect().top - oben;            // weiter nie: die Trennzeile bleibt oben
    if (fehlt > 0 && bisTrenner > 0) liste.scrollTop += Math.min(fehlt, bisTrenner);
  }

  async function globalSuchen(q) {
    const G = window.MatGlobal;
    if (!G || !q) return;
    const ja = await G.bestaetigen(q);
    feld.focus({ preventScroll: true });
    if (!ja || feld.value.trim() !== q) return;
    global = { q, html: TRENNER + meldungZeile("Suche außerhalb deines Bereichs …") };
    mitFremden(q);
    let html;
    try {
      html = globalHtml(await G.suchen(q), q);
    } catch (e) {
      html = TRENNER + meldungZeile(e.message);   // zu viele Suchen, keine Verbindung … – bis weitergetippt wird
    }
    if (!global || global.q !== q) return;    // inzwischen weitergetippt: gilt nicht mehr
    global.html = html;
    if (feld.value.trim() === q) mitFremden(q);
  }

  async function laden() {
    const q = feld.value.trim();
    if (q.length < MIN) { schliessen(); return; }
    if (global && global.q === q && !zwischen.has(q)) { listeZeigen(global.html); return; }
    if (zwischen.has(q)) { zeigen(zwischen.get(q), q); return; }
    if (laufend) laufend.abort();
    laufend = new AbortController();
    try {
      const r = await fetch(`/api/material/suche?${new URLSearchParams({ q, pro_seite: ANZAHL })}`,
                            { signal: laufend.signal, headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" });
      if (!r.ok) { schliessen(); return; }                // ohne Leserecht o. Ä.: einfach keine Vorschläge
      const d = await r.json();
      zwischen.set(q, d);
      if (feld.value.trim() === q && document.activeElement === feld) zeigen(d, q);   // zeigen hängt den fremden Teil an
    } catch (e) {
      if (e.name !== "AbortError") schliessen();
    }
  }

  feld.addEventListener("input", () => { global = null; clearTimeout(warten); warten = setTimeout(laden, 180); });
  feld.addEventListener("focus", () => { if (feld.value.trim().length >= MIN) laden(); });
  feld.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (liste.hidden) { laden(); return; }
      e.preventDefault();
      waehlen(aktiv + (e.key === "ArrowDown" ? 1 : -1));
    } else if (e.key === "Enter" && !liste.hidden && aktiv >= 0) {
      e.preventDefault();
      const o = optionen[aktiv];
      if (o.dataset.global) globalSuchen(feld.value.trim());
      else if (o.querySelector("a")) location.href = o.querySelector("a").href;   // ein Steckbrief öffnet nichts
    } else if (e.key === "Escape" && !liste.hidden) {
      e.preventDefault();
      schliessen();
    }
  });
  // Ein Tipp in die Liste nimmt dem Feld nicht den Fokus – sonst schlösse sie, bevor der Klick ankommt.
  liste.addEventListener("pointerdown", (e) => e.preventDefault());
  liste.addEventListener("click", (e) => {
    if (e.target.closest("[data-global]")) { globalSuchen(feld.value.trim()); return; }
    const a = e.target.closest("a");
    if (a && !(e.ctrlKey || e.metaKey || e.shiftKey || e.button)) schliessen();
  });
  feld.addEventListener("blur", () => setTimeout(() => { if (document.activeElement !== feld) schliessen(); }, 120));
  // Ein Klick in einem Dialog (die Rückfrage der globalen Suche) schließt die Liste nicht – sie zeigt gleich das Ergebnis.
  document.addEventListener("click", (e) => { if (!form.contains(e.target) && !e.target.closest("dialog")) schliessen(); });
  form.addEventListener("submit", () => schliessen());
})();
