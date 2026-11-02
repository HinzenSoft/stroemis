/* Startseite über alle Module (Wunsch vom 02.11.2026; Server: app/start.py, Vorlage start.html).
   Holt alles aus GET /api/start – der Server liefert nur Module, Zahlen, Titel und Links, die das Konto sehen darf – und
   zeichnet: je Modul eine Kachel (Zeilen mit Zahl über 0, jede ein Link auf die passende Ansicht; sonst ein ruhiger Satz),
   darunter „Zuletzt besucht“ und „Neu und geändert“ über die Module und die obersten Abschnitte der Strömipedia als
   Karten. Danach merkt POST /api/start/besuch den Besuch – der Vergleichspunkt für „seit deinem letzten Besuch“.
   Alle Texte aus Eingaben (Titel, Namen) gehen durch esc. */
(function () {
  const { esc, api } = S;
  const ziel = document.getElementById("start-inhalt");
  if (!ziel) return;

  /* Die Wörter zu den Zeilen der Kacheln: [Einzahl, Mehrzahl] hinter der Zahl; dringend färbt die Zahl zusätzlich (das Wort
     sagt es schon). Arten wie in app/start.py. */
  const SEIT = " seit deinem letzten Besuch";
  const ZEILE = {
    seiten: ["Seite", "Seiten"],
    seiten_frei: ["freigegebene Seite", "freigegebene Seiten"],
    wiki_neu: ["neu oder geändert" + SEIT, "neu oder geändert" + SEIT],
    alben: ["Album", "Alben"],
    alben_neu: ["neues Album" + SEIT, "neue Alben" + SEIT],
    bilder_neu: ["neues Bild" + SEIT, "neue Bilder" + SEIT],
    laufend: ["laufender Lehrgang", "laufende Lehrgänge"],
    leistungen_offen: ["Leistung noch nicht abgenommen", "Leistungen noch nicht abgenommen"],
    lehrgang_maengel: ["offener Mangel", "offene Mängel"],
    ueberfaellig: ["überfällig", "überfällig"],
    neu: ["neu (Eingangsprüfung)", "neu (Eingangsprüfung)"],
    bald_faellig: ["bald fällig", "bald fällig"],
    maengel: ["gemeldeter Mangel", "gemeldete Mängel"],
    antraege: ["offener Änderungsantrag", "offene Änderungsanträge"],
    psa: ["Artikel dir zugeordnet", "Artikel dir zugeordnet"],
    psa_dringend: ["davon nicht einsatzbereit", "davon nicht einsatzbereit"],
    anfragen: ["offene Kontoanfrage", "offene Kontoanfragen"],
  };
  const DRINGEND = new Set(["ueberfaellig", "maengel", "lehrgang_maengel", "psa_dringend"]);

  function zeileHtml(z) {
    const w = ZEILE[z.art] || ["", ""];
    const wort = (z.zahl === 1 ? w[0] : w[1]) + (z.art === "bald_faellig" && z.tage != null ? ` (${Number(z.tage)} Tage)` : "");
    return `<li><a class="start-zeile${DRINGEND.has(z.art) ? " dringend" : ""}" href="${esc(z.href)}"><strong>${Number(z.zahl)}</strong>
      <span>${esc(wort)}</span></a></li>`;
  }

  function kachelHtml(k) {
    const id = `start-k-${esc(k.modul)}`;
    return `<section class="start-kachel" aria-labelledby="${id}"><h2 id="${id}"><a href="${esc(k.pfad)}">${esc(k.name)}</a></h2>
      ${k.zeilen.length ? `<ul class="start-zeilen">${k.zeilen.map(zeileHtml).join("")}</ul>` : `<p class="start-ruhig">${esc(k.ruhig)}</p>`}</section>`;
  }

  /* Zeitangabe der Listen: heute die Uhrzeit, gestern „gestern“, sonst Tag und Monat (Jahr nur, wenn es nicht dieses ist);
     die volle Angabe im title. */
  function wann(iso) {
    const d = new Date(iso);
    if (!iso || isNaN(d)) return "";
    const jetzt = new Date();
    const gestern = new Date(jetzt.getFullYear(), jetzt.getMonth(), jetzt.getDate() - 1);
    let text;
    if (d.toDateString() === jetzt.toDateString()) text = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    else if (d.toDateString() === gestern.toDateString()) text = "gestern";
    else text = d.toLocaleDateString("de-DE", d.getFullYear() === jetzt.getFullYear()
      ? { day: "2-digit", month: "2-digit" } : { day: "2-digit", month: "2-digit", year: "numeric" });
    return `<time datetime="${esc(iso)}" title="${esc(S.fmtDate(iso, true))}">${esc(text)}</time>`;
  }

  function listeHtml(titel, id, eintraege, leer) {
    const zeilen = eintraege.map((e) => `<li><a href="${esc(e.href)}"><span class="start-titel">${esc(e.titel)}${e.zusatz
      ? `<span class="start-zusatz"> · ${esc(e.zusatz)}</span>` : ""}</span>
      <span class="start-meta">${esc(e.modulname)} · ${e.neu ? "neu · " : ""}${wann(e.zeit)}</span></a></li>`).join("");
    return `<section class="section start-liste" aria-labelledby="${id}"><h2 id="${id}">${titel}</h2>
      ${eintraege.length ? `<ul>${zeilen}</ul>` : `<div class="leerzustand"><strong>${leer[0]}</strong>${leer[1]}</div>`}</section>`;
  }

  /* Karten der Strömipedia: dieselben wie auf der Übersicht der Strömipedia (.wiki-karten in app.css). */
  function wikiHtml(d) {
    if (!d.abschnitte) return "";
    const seite = (s) => `<a href="/stroemipedia/${esc(s.slug)}">${s.icon ? esc(s.icon) + " " : ""}${esc(s.title)}</a>`;
    const karten = d.abschnitte.map((a) => `<li class="wiki-karte"><h3>${seite(a)}</h3>
      <p class="wiki-karte-zahl">${esc(S.plural(a.seiten, "Seite", "Seiten"))}</p>
      ${a.unterseiten.length ? `<ul>${a.unterseiten.map((u) => `<li>${seite(u)}</li>`).join("")}</ul>` : ""}</li>`).join("");
    const leer = d.lesemodus ? ["Keine freigegebenen Seiten", "Derzeit sind keine Seiten für alle Angemeldeten freigegeben."]
      : ["Die Strömipedia ist noch leer", "Sobald jemand eine Seite anlegt, steht sie hier."];
    return `<section class="section start-wiki" aria-labelledby="start-wiki-titel">
      <div class="abschnittskopf"><h2 id="start-wiki-titel">Strömipedia</h2><a class="start-alle" href="/stroemipedia">alle<span class="nur-vorlesen"> Abschnitte</span> →</a></div>
      ${d.abschnitte.length ? `<ul class="wiki-karten">${karten}</ul>` : `<div class="leerzustand"><strong>${leer[0]}</strong>${leer[1]}</div>`}</section>`;
  }

  async function laden() {
    let d;
    try { d = await api("/api/start"); }
    catch (e) {
      ziel.innerHTML = `<p class="notice" role="alert">Die Startseite ließ sich nicht laden: ${esc(e.message)} Lade die Seite neu, um es noch einmal zu versuchen.</p>`;
      return;
    }
    ziel.innerHTML = `<div class="start-kacheln" data-anzahl="${d.kacheln.length}">${d.kacheln.map(kachelHtml).join("")}</div>
      <div class="start-listen">
        ${listeHtml("Zuletzt besucht", "start-zuletzt", d.zuletzt, ["Noch nichts besucht", "Was du öffnest, steht hier zum schnellen Wiederfinden."])}
        ${listeHtml("Neu und geändert", "start-neu", d.neu, ["Nichts Neues", "Hier steht, was zuletzt angelegt oder geändert wurde."])}
      </div>
      ${wikiHtml(d)}`;
    // Erst nach dem Zeichnen: Der Besuch zählt, wenn die Zahlen zu sehen waren. Scheitert es, bleibt der alte Punkt.
    try { await api("/api/start/besuch", { method: "POST", body: {} }); } catch (e) { /* beim nächsten Mal */ }
  }
  laden();
})();
