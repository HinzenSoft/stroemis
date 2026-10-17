/* Vorschläge im Suchfeld des Moduls Material (Kopfzeile jeder Modulseite): Schon bei Teileingaben – ab zwei Zeichen –
   erscheinen unter dem Feld bis zu acht Artikel als Steckbrief: Produktfoto, Inventarnummer, Produkt, Seriennummer,
   Status und Ablage, der getippte Teil der Nummern hervorgehoben. Grundlage ist dieselbe Suche wie die Trefferseite
   (/api/material/suche: Serien-, Inventar-, Herstellernummer, auch Teile davon).

   Bedienung wie ein Kombinationsfeld (ARIA combobox/listbox): Pfeiltasten wählen, Enter öffnet den gewählten Artikel –
   ohne Wahl geht Enter wie bisher zur Trefferseite (ein eindeutiger Treffer öffnet dort direkt) –, Escape schließt.
   Mit Maus oder Finger öffnet ein Tipp den Artikel; „Alle Treffer“ führt zur Trefferseite. Ohne JavaScript bleibt das
   Feld ein gewöhnliches Suchformular. */
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

  function zeigen(d, q) {
    const treffer = (d.treffer || []).slice(0, ANZAHL);
    let html = treffer.map((a, i) => karte(a, q, i)).join("");
    if (!treffer.length) html = `<li class="mv-leer" role="presentation">Kein Artikel mit „${esc(q)}“ in Serien-, Inventar- oder Herstellernummer.</li>`;
    else html += `<li role="option" id="mv-${treffer.length}" aria-selected="false" class="mv-alle" data-alle="1">
      <a href="/material/suche?q=${encodeURIComponent(q)}" tabindex="-1">${d.gesamt > treffer.length ? `Alle ${d.gesamt} Treffer anzeigen` : "Als Trefferliste anzeigen"}</a></li>`;
    liste.innerHTML = html;
    optionen = Array.from(liste.querySelectorAll('[role="option"]'));
    aktiv = -1;
    feld.removeAttribute("aria-activedescendant");
    liste.hidden = false;
    feld.setAttribute("aria-expanded", "true");
  }

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

  async function laden() {
    const q = feld.value.trim();
    if (q.length < MIN) { schliessen(); return; }
    if (zwischen.has(q)) { zeigen(zwischen.get(q), q); return; }
    if (laufend) laufend.abort();
    laufend = new AbortController();
    try {
      const r = await fetch(`/api/material/suche?${new URLSearchParams({ q, pro_seite: ANZAHL })}`,
                            { signal: laufend.signal, headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" });
      if (!r.ok) { schliessen(); return; }                // ohne Leserecht o. Ä.: einfach keine Vorschläge
      const d = await r.json();
      zwischen.set(q, d);
      if (feld.value.trim() === q && document.activeElement === feld) zeigen(d, q);
    } catch (e) {
      if (e.name !== "AbortError") schliessen();
    }
  }

  feld.addEventListener("input", () => { clearTimeout(warten); warten = setTimeout(laden, 180); });
  feld.addEventListener("focus", () => { if (feld.value.trim().length >= MIN) laden(); });
  feld.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (liste.hidden) { laden(); return; }
      e.preventDefault();
      waehlen(aktiv + (e.key === "ArrowDown" ? 1 : -1));
    } else if (e.key === "Enter" && !liste.hidden && aktiv >= 0) {
      e.preventDefault();
      location.href = optionen[aktiv].querySelector("a").href;
    } else if (e.key === "Escape" && !liste.hidden) {
      e.preventDefault();
      schliessen();
    }
  });
  // Ein Tipp in die Liste nimmt dem Feld nicht den Fokus – sonst schlösse sie, bevor der Klick ankommt.
  liste.addEventListener("pointerdown", (e) => e.preventDefault());
  liste.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (a && !(e.ctrlKey || e.metaKey || e.shiftKey || e.button)) schliessen();
  });
  feld.addEventListener("blur", () => setTimeout(() => { if (document.activeElement !== feld) schliessen(); }, 120));
  document.addEventListener("click", (e) => { if (!form.contains(e.target)) schliessen(); });
  form.addEventListener("submit", () => schliessen());
})();
