/* Riegenkarten (Modul pruefungen) – Lehrgangsliste, Lehrgang mit Reitern (Teilnehmende, Leistungen, Bewertung, Mängel),
   Bewertungsdialog mit Stoppuhr und Medien, Mängelübersicht samt Druckansicht, Import aus Excel/ISC.
   Zwei Stufen von Rechten: Prüfende bewerten, haken ab und kommentieren; die Lehrgangsleitung
   (darf_leiten vom Server) pflegt Stammdaten, Profilbilder, Leistungen und das Lehrgangsergebnis –
   ist das vermerkt, sind die Daten der Person eingefroren.
   Alles läuft auf einer Seite; welche Ansicht gemeint ist, sagt data-ansicht am <main>. */
(function () {
  const { esc, api, toast, dialog, fmtDate, info } = S;
  /* Anleitung in der Strömipedia (Nachtrag vom 01.11.2026, app/anleitung.py, S.anleitung in common.js): „Anleitung“
     hinter der Überschrift der Lehrgangsliste, eines Lehrgangs und eines Katalogs, „Mehr dazu in der Strömipedia“ am Ende
     der Infos („i“). Ohne Leserecht an der Seite gibt es keinen Link. */
  const { mehrDazu, kopf: anleitungKopf } = S.anleitung;
  const root = document.getElementById("pruef");
  if (!root) return;
  const ANSICHT = root.dataset.ansicht || "liste";
  const LEHRGANG_ID = root.dataset.lehrgang ? +root.dataset.lehrgang : null;
  const KATALOG_ID = root.dataset.katalog ? +root.dataset.katalog : null;
  const API = "/api/pruefungen";
  const SU_KEY = "pruef:stoppuhr";
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const schmal = () => window.matchMedia("(max-width: 760px)").matches;
  // Fokus beim Öffnen nur mit Maus/Tastatur: Auf dem Telefon ginge sofort die Tastatur auf und
  // verdeckte die untere Hälfte des Dialogs, bevor man ihn gelesen hat.
  const fokus = (el) => { if (el && !window.matchMedia("(pointer: coarse)").matches) el.focus(); };

  const state = {
    lehrgang: null,          // LehrgangDetail der geöffneten Seite
    kataloge: null,          // Kataloge (Kurzform mit Anzahl), einmal geladen – Auswahl beim Anlegen
    katalog: null,           // Katalogdetail der geöffneten Katalogseite
    liste: [], jahre: [],    // Lehrgangsliste und die darin vorkommenden Jahre
    reiter: "teilnehmer",
    bewAnsicht: null, bewLeistung: null, bewTn: null,
    mf: { teilnehmer: "", leistung: "", nur_offen: true },   // Filter der Mängelübersicht
    medienGruppen: {}, medienZaehler: 0,                      // Medienlisten für den Leuchtkasten
    dlgAufraeumen: null,     // räumt Stoppuhr-Timer und Objekt-URLs des Bewertungsdialogs weg
    lb: null,                // {medien, i, onDelete} des offenen Leuchtkastens
    vorKlapp: {},            // Karte „Voraussetzungen“ je Person auf-/zugeklappt (tid → bool), solange die Seite offen ist
    kopfOffen: null,         // Angaben zum Lehrgang am Telefon/bei wenig Höhe aufgeklappt (null: Vorgabe zu)
  };

  /* --- Kleine Helfer --------------------------------------------------------------------- */
  // Sekunden → „mm:ss“. Über 99 Minuten wird die Minutenzahl einfach länger – das kommt bei
  // Prüfungsleistungen nicht vor, soll aber nichts Falsches zeigen.
  const fmtZeit = (sek) => {
    if (sek == null || isNaN(sek)) return "";
    const s = Math.max(0, Math.round(sek));
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  };
  // Millisekunden → „mm:ss.z“ für die laufende Stoppuhr (abgeschnitten, nicht gerundet – sonst
  // springt die Anzeige kurz auf die nächste Sekunde, bevor sie erreicht ist).
  const fmtZeitGenau = (ms) => {
    const zehntel = Math.max(0, Math.floor(ms / 100));
    return `${fmtZeit(Math.floor(zehntel / 10))}.${zehntel % 10}`;
  };
  /* Eingabe im Zeitfeld: „2:30“, „02:30“, „150“ (Sekunden) oder leer. Alles andere ist ein
     Tippfehler und soll nicht stillschweigend zu 0 werden. */
  function zeitLesen(text) {
    const t = String(text || "").trim();
    if (!t) return { ok: true, wert: null };
    const m = t.match(/^(\d{1,3}):([0-5]?\d)(?:[.,]\d+)?$/);
    if (m) return { ok: true, wert: (+m[1]) * 60 + (+m[2]) };
    if (/^\d+$/.test(t)) {
      // Die Zifferntastatur des Telefons (inputmode=numeric) hat keinen Doppelpunkt: „230“ und
      // „0230“ heißen 2:30, ein- und zweistellig sind Sekunden („45“).
      if (t.length >= 3) {
        const sek = +t.slice(-2), min = +t.slice(0, -2);
        return sek > 59 ? { ok: false } : { ok: true, wert: min * 60 + sek };
      }
      return { ok: true, wert: +t };
    }
    return { ok: false };
  }
  // „2026-12-04“ → „04.12.2026“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const fmtTag = (d) => {
    const m = String(d || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}.${m[2]}.${m[1]}` : (d || "");
  };
  const spanne = (von, bis) => (von && bis && von !== bis ? `${fmtTag(von)} – ${fmtTag(bis)}` : fmtTag(von || bis));
  const tnName = (tn) => `${tn.vorname || ""} ${tn.name || ""}`.trim() || "–";
  // „Maria Müller“ → „M. Müller“ – die Kurzform unter den Häkchen und in den Zellen.
  const kurzName = (name) => {
    const t = String(name || "").trim().split(/\s+/).filter(Boolean);
    return t.length >= 2 ? `${t[0][0]}. ${t.slice(1).join(" ")}` : (t[0] || "");
  };
  const STATUS = { geplant: ["geplant", "grey"], laufend: ["laufend", "blau"], abgeschlossen: ["abgeschlossen", "gruen"] };
  const statusMarke = (s) => { const [t, c] = STATUS[s] || STATUS.geplant; return `<span class="badge ${c}">${t}</span>`; };
  const ZELLE = {
    offen: { sym: "–", txt: "offen" },
    bestanden: { sym: "👍", txt: "bestanden" },
    mangelhaft: { sym: "👎", txt: "mangelhaft" },
    nachpruefung_bestanden: { sym: "👍", txt: "bestanden", np: true },
    nachpruefung_mangelhaft: { sym: "👎", txt: "mangelhaft", np: true },
  };
  // Der erste Versuch heißt „Versuch 1“, alles danach sind Nachprüfungen (so legt es der Server an).
  const versuchTitel = (v) => (v.ist_nachpruefung ? `Nachprüfung ${Math.max(1, v.versuch_nr - 1)}` : `Versuch ${v.versuch_nr}`);
  // Gerenderte Beschreibungen tragen keine id-Attribute: Ein <div id="bw-wahl"> im Text stünde
  // im Dialog vor dem Formular und würde von querySelector statt des echten Feldes gefunden.
  // Überschriften der Beschreibung stehen in einer Karte oder einem Dialog unter deren eigenen Überschriften: drei
  // Stufen tiefer (H1 → H4, ab H3 → H6), leere fallen weg (Gerätetest B11 – „# Ablauf“ war eine zweite H1 der Seite).
  const md = (text) => {
    if (!window.MD || !text) return `<p>${esc(text || "")}</p>`;
    const t = document.createElement("div");
    t.innerHTML = MD.render(text);
    t.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
    t.querySelectorAll("h1, h2, h3, h4, h5, h6").forEach((h) => {
      if (!h.textContent.trim() && !h.querySelector("img")) { h.remove(); return; }
      const tiefer = document.createElement(`h${Math.min(6, +h.tagName[1] + 3)}`);
      [...h.attributes].forEach((a) => tiefer.setAttribute(a.name, a.value));
      tiefer.innerHTML = h.innerHTML;
      h.replaceWith(tiefer);
    });
    return t.innerHTML;
  };
  /* Ohne Netz (Gerätetest W1): Ein Schreibvorgang, der scheitert, nimmt die Anzeige zurück und sagt es so – keine
     Warteschlange, wie bei der App ohne Netz (nur ein Hinweis). Der Status 0 kommt von S.api („keine Antwort“). */
  const NICHT_GESPEICHERT = "Nicht gespeichert – keine Verbindung.";
  const schreibFehler = (e) => (e && e.status === 0 ? Object.assign(new Error(NICHT_GESPEICHERT), { status: 0 }) : e);
  const groesseText = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(b / 1024))} kB`);
  const isVideo = (f) => /^video\//.test(f.type) || /\.(mp4|m4v|mov|webm)$/i.test(f.name || "");
  const plural = S.plural;              // „1 Bild“, „3 Bilder“ – app-weit in common.js (UI/UX vor dem Merge, A11)
  // Ein Kommentar in einer Matrixzelle: ein Satz reicht, der Rest steht im Dialog.
  const kuerzen = (text, n) => { const t = String(text || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t; };

  /* --- Rechte in der Oberfläche ------------------------------------------------------------
     Der Server entscheidet (403), die Oberfläche blendet nur aus, was ohnehin scheitern würde:
     Prüfende bewerten, haken ab und kommentieren; Stammdaten, Leistungen, Löschen und das
     Lehrgangsergebnis gehören der Lehrgangsleitung und der Administration (darf_leiten). Seit der Stufe Redakteur
     (01.11.2026): Lehrgänge anlegen, importieren als neuer Lehrgang und Kataloge ab Redakteur (darfAnlegen), kopieren
     nach darf_kopieren, einen Katalog bearbeiten nach darf_bearbeiten – ein Mitglied sieht nur die Lehrgänge, in denen
     es als Ausbilder steht (der Server liefert keine anderen). */
  const darfLeiten = () => !!(state.lehrgang && state.lehrgang.darf_leiten);
  const darfAnlegen = () => S.stufe("pruefungen") >= S.STUFE.redakteur;
  /* Knopfsprache (designsprache.md, nach_merge_liste Punkt 13): Seltene Zeilenaktionen stehen im Zeilenmenü „Mehr“
     (details.zeilenmenue wie in der Leitstelle, schließt über common.js), Verschieben als Textknöpfe statt ↑/↓. Die
     Einträge sind <button data-act …> – derselbe Klickverteiler wie vorher die einzelnen Knöpfe. */
  // Seit dem gemeinsamen Menübaustein (UI/UX vor dem Merge, A3): S.menue – bleibt ein Eintrag, steht er als Knopf da.
  // Einträge: [Text, Attribut-HTML]. Reihenfolge mit ↑/↓ und Entfernen mit ✕ wie in der Materialablage (D3).
  const zeilenMenue = (eintraege) => S.menue({ art: "zeilenmenue", eintraege: eintraege.filter(Boolean).map(([text, attrs]) => ({ text, attrs })) });
  const sortierKnoepfe = (i, n, hoch, runter) => S.reihenfolgeKnoepfe(i, n, hoch, runter);
  // Derselbe Text wie im Server (409) – damit die Oberfläche nicht anders erklärt als die Antwort.
  const EINGEFROREN = "Für diese Person ist das Lehrgangsergebnis vermerkt – die Prüfungsdaten sind eingefroren. Die Lehrgangsleitung kann das Ergebnis aufheben.";
  /* Erklärungen hinter einem „i“ (S.info, designsprache „Info-Symbol „i““): Zeitansatz und Kriterienliste stehen im
     Katalog und im Lehrgang; das Schloss eingefrorener Personen erklärt ein „i“ an der Überschrift der Liste (je Zeile
     bleibt das title für die Maus). */
  const ZEITANSATZ_INFO = "Mit Zeitansatz zeigt der Bewertungsdialog eine Stoppuhr mit Sollzeit. Über das Bestehen entscheidet sie nicht.";
  const KRITERIEN_INFO = "Zusätzlich zur Beschreibung: einzeln abhakbare Punkte.";
  // Wortgleich mit api_pruefungen.KRITERIEN_EINGEFROREN.
  const KRITERIEN_EINGEFROREN = "Zu dieser Leistung gibt es Bewertungen von Personen mit vermerktem Lehrgangsergebnis – deren Prüfungsdaten sind eingefroren, deshalb lassen sich die Kriterien nicht mehr anlegen, ändern, umsortieren oder löschen. Die Lehrgangsleitung kann das Ergebnis aufheben.";
  // Der ganze Leistungsdialog (Kleinigkeiten 02.11.2026): Bezeichnung, Zeitansatz und Beschreibung sperrt der Server mit
  // derselben Bedingung wie die Kriterien (api_pruefungen.update_leistung, _LEISTUNG_BETROFFEN) – änderbar bleibt nichts.
  const LEISTUNG_EINGEFROREN = "Zu dieser Leistung gibt es Bewertungen von Personen mit vermerktem Lehrgangsergebnis – deren Prüfungsdaten sind eingefroren, deshalb lassen sich Bezeichnung, Zeitansatz, Beschreibung und Kriterien nicht mehr ändern. Die Lehrgangsleitung kann das Ergebnis aufheben.";
  const eingefrorenInfo = (tns) => (tns.some((t) => t.eingefroren) ? info("eingefroren", `Eingefroren (Schloss am Namen): ${esc(EINGEFROREN)}${mehrDazu("eingefroren")}`) : "");

  /* --- Teilnehmende: Bild, Schloss, Ergebnis ------------------------------------------------ */
  // Ein Eintrag der Mängelliste kennt nur id/name/vorname – Bild, Kommentar und Ergebnis kommen
  // aus dem geladenen Lehrgang.
  const tnAusState = (tid) => ((state.lehrgang && state.lehrgang.teilnehmer) || []).find((t) => t.id === tid) || null;
  const tnVoll = (tn) => Object.assign({}, tnAusState(tn.id) || {}, tn);
  const initialen = (tn) => `${(tn.vorname || "")[0] || ""}${(tn.name || "")[0] || ""}`.toUpperCase() || "?";
  // Die Adresse kommt vom Server und zeigt stets nach /media/pruefung/avatar/ – alles andere
  // wird nicht eingebunden.
  const bildAdresse = (tn) => { const a = String((tn && tn.bild) || ""); return a.startsWith("/media/pruefung/avatar/") ? a : ""; };
  /* Der runde Kreis vor dem Namen: Profilbild oder Initialen (28 px; im TN-Dialog groß). */
  function tnBildHtml(tn, klasse) {
    const a = bildAdresse(tn);
    // Ein echtes Bild lässt sich antippen und groß ansehen (Leuchtkasten); Initialen nicht.
    const klick = a ? ` klick" data-act="tn-bild" data-tid="${tn.id}" role="button" tabindex="0" title="Profilbild vergrößern` : `" aria-hidden="true`;
    return `<span class="tn-bild${a ? " mit" : ""}${klasse ? ` ${klasse}` : ""}${klick}">${a ? `<img src="${esc(a)}" alt="${esc(tnName(tn))}" loading="lazy">` : esc(initialen(tn))}</span>`;
  }

  /* Profilbild groß: im Leuchtkasten, der über jedem offenen Dialog liegt – so bleibt ein
     gerade geöffneter Bewertungsdialog samt Eingaben darunter stehen. */
  function bildDialog(tid) {
    const tn = tnAusState(tid);
    const a = tn ? bildAdresse(tn) : "";
    if (!a) return;
    state.lb = null;
    lbBody.innerHTML = `<div class="lb-img lb-profil"><img src="${esc(a)}" alt="${esc(tnName(tn))}"></div>
      <div class="lb-side">${S.schliessenKnopf('id="lb-close"', "close")}
        <h2>${esc(tnName(tn))}</h2>
        <div class="lb-meta">${esc(tn.gliederung || "")}${tn.geburtsdatum ? `${tn.gliederung ? "<br>" : ""}geb. ${esc(fmtTag(tn.geburtsdatum))}` : ""}</div>
        ${ergebnisMarkeHtml(tn)}</div>`;
    $("#lb-close").onclick = () => lb.close();
    if (!lb.open) { lb.showModal(); S.dialogVerlauf(lb); }
  }
  // Bilder in Dialogen liegen außerhalb der Seite (#pruef) – dort fängt der Seiten-Delegierer nicht.
  document.addEventListener("click", (e) => {
    const b = e.target.closest('[data-act="tn-bild"]');
    if (b && !root.contains(b)) { e.preventDefault(); bildDialog(+b.dataset.tid); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const b = e.target.closest && e.target.closest('[data-act="tn-bild"]');
    if (b) { e.preventDefault(); bildDialog(+b.dataset.tid); }
  });
  const schlossHtml = (tn) => (tn.eingefroren ? `<span class="schloss" role="img" aria-label="eingefroren" title="${esc(EINGEFROREN)}">🔒</span>` : "");
  /* Bild, ggf. Schloss und Name als eine Zeile. nameHtml erlaubt einen Knopf statt des Textes. */
  function tnKopfHtml(tn, nameHtml) {
    return `<span class="tn-kopfzeile">${tnBildHtml(tn)}${schlossHtml(tn)}${nameHtml != null ? nameHtml : `<span class="tn-name">${esc(tnName(tn))}</span>`}</span>`;
  }
  const ERGEBNIS = { bestanden: ["bestanden", "gruen"], nicht_bestanden: ["nicht bestanden", "rot"] };
  function ergebnisMarkeHtml(tn, opts = {}) {
    const e = ERGEBNIS[tn.ergebnis];
    if (!e) return opts.leer ? '<span class="muted erg-leer">–</span>' : "";
    return `<span class="badge ${e[1]} erg-marke" title="Lehrgang ${e[0]}">${e[0]}</span>`;
  }
  const ergebnisVonHtml = (tn) => (tn.ergebnis ? `<span class="erg-von">von ${esc(kurzName(tn.ergebnis_von_name))} am ${esc(fmtDate(tn.ergebnis_am, true))}</span>` : "");
  /* Spalte „Lehrgang“: Die Leitung sieht „👍 bestanden“/„👎 nicht bestanden“ (der gesetzte ist hervorgehoben), alle
     anderen nur die Marke. Darunter klein, wer das Ergebnis wann vermerkt hat. Das Zeichen steht wie in der großen
     Bewertungswahl immer mit dem Wort (UI/UX vor dem Merge D14 – vorher nur 👍/👎). */
  function ergebnisHtml(tn) {
    if (!darfLeiten()) return `<div class="erg-block">${ergebnisMarkeHtml(tn, { leer: true })}${ergebnisVonHtml(tn)}</div>`;
    const knopf = (erg, sym, wort, kl) => `<button type="button" class="erg-knopf ${kl}${tn.ergebnis === erg ? " sel" : ""}" data-act="tn-ergebnis" data-tid="${tn.id}" data-erg="${erg}"
        aria-pressed="${tn.ergebnis === erg}" aria-label="Lehrgang ${wort}" title="Lehrgang ${wort}${tn.ergebnis === erg ? " – antippen zum Aufheben" : ""}"><span class="sym" aria-hidden="true">${sym}</span> ${wort}</button>`;
    return `<div class="erg-block"><div class="erg-knoepfe">${knopf("bestanden", "👍", "bestanden", "ja")}${knopf("nicht_bestanden", "👎", "nicht bestanden", "nein")}</div>${ergebnisVonHtml(tn)}</div>`;
  }
  /* Spalte „Kommentar“: die Zelle selbst öffnet den Dialog; gekürzt auf rund 60 Zeichen. */
  function kommentarZelleHtml(tn, opts = {}) {
    const t = tn.kommentar || "";
    const leerText = tn.eingefroren ? "–" : '<span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Kommentar<span class="k-anlegen"> anlegen</span></span>';
    return `<button type="button" class="komm-zelle${t ? "" : " leer"}${tn.eingefroren ? " gesperrt" : ""}" data-act="tn-kommentar" data-tid="${tn.id}"
      title="${esc(t || (tn.eingefroren ? "Kommentar (eingefroren)" : "Kommentar hinzufügen"))}">${t ? esc(kuerzen(t, opts.laenge || 60)) : leerText}</button>`;
  }

  /* Eine Meldung, die einen Seitenwechsel überleben soll (z. B. „Import: 12 angelegt“ vor dem
     Sprung zum neuen Lehrgang). */
  const meldungMerken = (text) => { try { sessionStorage.setItem("pruef:meldung", text); } catch (e) { /* egal */ } };
  const meldungZeigen = () => {
    try {
      const t = sessionStorage.getItem("pruef:meldung");
      if (t) { sessionStorage.removeItem("pruef:meldung"); toast(t); }
    } catch (e) { /* egal */ }
  };

  /* opts.ohneHinweise: nur Zahl und Balken – in der Lehrgangsliste stehen offene Mängel und Voraussetzungen unter dem
     Titel (lgHinweisHtml), die schmale Spalte quetschte sie auf drei Zeilen (Gerätetest F2). */
  function fortschrittHtml(lg, opts = {}) {
    const ges = lg.zellen_gesamt || 0, ab = lg.zellen_abgenommen || 0;
    const pct = ges ? Math.round((ab / ges) * 100) : 0;
    const offen = lg.offene_maengel || 0;
    return `<div class="fortschritt"><span>${ab}/${ges} Leistungen abgenommen</span>
      <div class="balken"><span class="${ges && ab === ges ? "voll" : ""}" style="width:${pct}%"></span></div>
      ${opts.ohneHinweise ? "" : `${offen ? `<span class="maengel">${plural(offen, "offener Mangel", "offene Mängel")}</span>` : '<span class="muted">keine offenen Mängel</span>'}
      ${lg.voraussetzungen_offen ? `<span class="maengel"> · ${lg.voraussetzungen_offen} Teilnehmende mit offenen Voraussetzungen</span>` : ""}`}</div>`;
  }
  const lgHinweisHtml = (lg) => {
    const t = [lg.offene_maengel ? plural(lg.offene_maengel, "offener Mangel", "offene Mängel") : "",
      lg.voraussetzungen_offen ? `${lg.voraussetzungen_offen} Teilnehmende mit offenen Voraussetzungen` : ""].filter(Boolean);
    return t.length ? `<div class="lg-hinweis">${t.join(" · ")}</div>` : "";
  };

  /* Medienkacheln. Die Liste wird unter einem Schlüssel gemerkt, damit der Leuchtkasten beim
     Antippen weiß, worin er blättern soll. loeschbar hängt ein ✕ an jede Kachel. */
  function medienGridHtml(medien, opts = {}) {
    if (!medien || !medien.length) return "";
    const key = "mg" + (++state.medienZaehler);
    state.medienGruppen[key] = { medien, onDelete: opts.onDelete || null };
    return `<div class="medien-grid${opts.klein ? " klein" : ""}">${medien.map((m, i) => `
      <div class="medium-huelle"><button type="button" class="medium" data-mg="${key}" data-i="${i}" title="${esc(m.original_name || "")}">
        <img src="${esc(m.thumb)}" alt="${esc(m.original_name || "")}" loading="lazy">${m.kind === "video" ? '<span class="play" aria-hidden="true">▶</span>' : ""}</button>
        ${opts.loeschbar ? S.entfernenKnopf(`data-mg="${key}" data-i="${i}"`, "Medium löschen", "medium-weg") : ""}</div>`).join("")}</div>`;
  }

  /* --- Leuchtkasten (Bild/Video groß) ---------------------------------------------------- */
  const lb = $("#lightbox"), lbBody = $("#lb-body");

  function openLightbox(gruppe, i) {
    state.lb = { medien: gruppe.medien, i, onDelete: gruppe.onDelete };
    renderLightbox();
    if (!lb.open) { lb.showModal(); S.dialogVerlauf(lb); }
  }

  function renderLightbox() {
    const { medien, i, onDelete } = state.lb;
    const m = medien[i];
    if (!m) return lb.close();
    lbBody.innerHTML = `
      <div class="lb-img">
        ${m.kind === "video"
          ? `<video controls playsinline preload="metadata" poster="${esc(m.web)}" src="${esc(m.orig)}"></video>`
          : `<img src="${esc(m.web)}" alt="${esc(m.original_name || "")}">`}
        ${medien.length > 1 ? '<button class="lb-nav prev" id="lb-prev" aria-label="Vorheriges">‹</button><button class="lb-nav next" id="lb-next" aria-label="Nächstes">›</button>' : ""}
      </div>
      <div class="lb-side">${S.schliessenKnopf('id="lb-close"', "close")}
        <h2>${m.kind === "video" ? "Video" : "Bild"} ${i + 1} von ${medien.length}</h2>
        <div class="lb-meta"><strong>${esc(m.original_name || "")}</strong>
          hochgeladen von ${esc(m.hochgeladen_von_name || "")} am ${esc(fmtDate(m.hochgeladen_am, true))}
          ${m.width ? `<br>${m.width} × ${m.height} px` : ""}</div>
        <div class="btn-row"><a class="btn secondary small" href="${esc(m.orig)}" target="_blank" rel="noopener">Original öffnen</a>
          ${onDelete ? '<button class="btn secondary small" id="lb-del" type="button">Löschen</button>' : ""}</div>
      </div>`;
    lb.tabIndex = -1;
    lb.focus();
    $("#lb-close").onclick = () => lb.close();
    const prev = $("#lb-prev"), next = $("#lb-next");
    if (prev) prev.onclick = () => { state.lb.i = (i - 1 + medien.length) % medien.length; renderLightbox(); };
    if (next) next.onclick = () => { state.lb.i = (i + 1) % medien.length; renderLightbox(); };
    const del = $("#lb-del");
    if (del) del.onclick = async () => {
      if (!(await S.confirm(`„${m.original_name || "Medium"}“ endgültig löschen?`))) return;
      try {
        await api(`${API}/medien/${m.id}`, { method: "DELETE" });
        toast("Medium gelöscht");
        lb.close();
        onDelete(m);
      } catch (e) { toast(e.message, true); }
    };
    // Wischen blättert – Pfeiltasten gibt es auf dem Telefon nicht.
    const flaeche = lbBody.querySelector(".lb-img");
    let x0 = null;
    flaeche.addEventListener("touchstart", (e) => { if (e.target.tagName === "VIDEO") return; x0 = e.touches[0].clientX; }, { passive: true });
    flaeche.addEventListener("touchend", (e) => {
      if (x0 == null) return;
      const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) < 50) return;
      const ziel = $(dx < 0 ? "#lb-next" : "#lb-prev"); if (ziel) ziel.click();
    }, { passive: true });
  }
  lb.addEventListener("keydown", (e) => {
    if (e.target && e.target.tagName === "VIDEO") return;
    if (e.key === "ArrowLeft") { const b = $("#lb-prev"); if (b) b.click(); }
    if (e.key === "ArrowRight") { const b = $("#lb-next"); if (b) b.click(); }
  });
  lb.addEventListener("click", (e) => { if (e.target === lb) lb.close(); });
  // Ein abspielendes Video liefe sonst unsichtbar weiter.
  lb.addEventListener("close", () => { lbBody.innerHTML = ""; });

  // Kacheln überall (Seite, Dialog): eine Stelle, die den Leuchtkasten öffnet oder ein Medium löscht.
  document.addEventListener("click", async (e) => {
    const weg = e.target.closest(".medium-weg[data-mg]");
    if (weg) {
      const g = state.medienGruppen[weg.dataset.mg];
      const m = g && g.medien[+weg.dataset.i];
      if (!m || !g.onDelete) return;
      if (!(await S.confirm(`„${m.original_name || "Medium"}“ endgültig löschen?`))) return;
      try { await api(`${API}/medien/${m.id}`, { method: "DELETE" }); toast("Medium gelöscht"); g.onDelete(m); }
      catch (err) { toast(err.message, true); }
      return;
    }
    const k = e.target.closest(".medium[data-mg]");
    if (!k) return;
    const g = state.medienGruppen[k.dataset.mg];
    if (g) openLightbox(g, +k.dataset.i);
  });

  /* --- Stoppuhr: Speicher --------------------------------------------------------------------
     Gespeichert wird der Startzeitpunkt, nicht ein Zähler: Die Anzeige rechnet Date.now() - start.
     So überlebt die Messung ein Neuladen, eine Bildschirmsperre oder einen versehentlich
     geschlossenen Dialog – und ein Reiter im Hintergrund, dessen Timer der Browser drosselt,
     zeigt danach trotzdem die richtige Zeit. */
  function suLesen() {
    try {
      const d = JSON.parse(localStorage.getItem(SU_KEY) || "null");
      return d && typeof d.start === "number" && d.tid && d.lid ? d : null;
    } catch (e) { return null; }
  }
  function suSchreiben(d) { try { localStorage.setItem(SU_KEY, JSON.stringify(d)); } catch (e) { toast("Die Stoppuhr lässt sich in diesem Browser nicht speichern.", true); } }
  function suLoeschen() { try { localStorage.removeItem(SU_KEY); } catch (e) { /* egal */ } }

  /* Das Banner „Stoppuhr läuft“ steht oben auf der Seite, egal auf welchem Reiter man ist –
     wer den Dialog zugemacht hat, findet die Messung hier wieder. */
  function bannerZeichnen() {
    const el = $("#su-banner");
    if (!el) return;
    const su = suLesen();
    el.classList.toggle("hidden", !su);
    if (!su) { el.innerHTML = ""; return; }
    if (!el.dataset.fuer || el.dataset.fuer !== `${su.tid}:${su.lid}:${su.start}`) {
      el.dataset.fuer = `${su.tid}:${su.lid}:${su.start}`;
      el.innerHTML = `<span>Stoppuhr läuft: ${esc(su.tn_name)} – ${esc(su.leistung)}</span>
        <span class="zeit" id="su-banner-zeit"></span>
        <button type="button" class="btn secondary small" data-act="su-oeffnen">Öffnen</button>`;
    }
    const z = $("#su-banner-zeit", el);
    if (z) z.textContent = fmtZeit(Math.floor((Date.now() - su.start) / 1000));
  }
  setInterval(bannerZeichnen, 1000);
  window.addEventListener("storage", (e) => { if (e.key === SU_KEY) bannerZeichnen(); });

  /* Alle Dialoge dieser Seite gehen hierüber: Erst wird weggeräumt, was der vorige Dialog
     hinterlassen hat (Stoppuhr-Timer, Objekt-URLs, ein Toast-UI-Editor, Zusatzklassen wie
     „wide“ oder „pruef-dlg“), dann kommt der neue Inhalt. Das hängt bewusst nicht allein am
     close-Ereignis des Dialogs: In einem verborgenen Reiter liefert der Browser es verspätet
     oder gar nicht, und der nächste Dialog trüge dann Breite und Timer des vorigen. */
  // Diktat (Spracheingabe, diktat.js): Knopf neben einem Textfeld und der Hinweis dazu – leer, wenn
  // der Browser keine Spracherkennung hat oder die Einstellung sie abschaltet.
  const diktatKnopf = (id) => (window.Diktat ? Diktat.knopf(id) : "");
  const diktatHinweis = () => (window.Diktat ? Diktat.hinweis() : "");

  function dialogOeffnen(html, onOpen, klassen) {
    if (state.dlgAufraeumen) { const f = state.dlgAufraeumen; state.dlgAufraeumen = null; try { f(); } catch (e) { /* schon weg */ } }
    if (window.Diktat) Diktat.stopp();
    const el = $("#dlg");
    el.className = "";
    if (klassen) el.classList.add(...klassen);
    const dlg = dialog(html, onOpen);
    if (window.Diktat) Diktat.anbinden($("#dlg-body"));
    return dlg;
  }

  /* ==========================================================================================
     Lehrgang anlegen / bearbeiten
     ========================================================================================== */
  /* Ausbilder sind Konten mit Stufe in den Riegenkarten (Wunsch des Nutzers vom 01.11.2026) – einen freien Namen gibt es
     nicht mehr. Je Zeile sucht man die Person über Name oder vollständige E-Mail-Adresse (GET /nutzer?q=, ab 2 Zeichen;
     der Server liefert nur passende Konten, eine Adresse nur als Ganzes – zweite Durchsicht vor dem Merge), Funktion und „Leitung“ bleiben je Ausbilder. Ein schon eingetragenes Konto ohne Zugriff
     bleibt stehen und ist markiert (OHNE_ZUGRIFF); neu wählen lässt es sich nicht. Eine andere Person: Zeile entfernen
     (✕) und eine neue anlegen. */
  const OHNE_ZUGRIFF = {
    stufe: "ohne Zugriff – Stufe in der Leitstelle vergeben",
    deaktiviert: "ohne Zugriff – Konto deaktiviert",
    konto: "ohne Zugriff – kein Konto",
  };
  const KEIN_KONTO = "Bitte eine Person aus der Trefferliste wählen – Ausbilder gibt es nur mit Konto.";
  // Name als Einheit (name-einheit), Gliederung grau dahinter.
  const kontoHtml = (a) => `<span class="name-einheit"><strong>${esc(a.name)}</strong></span>${a.gliederung ? ` <span class="small muted">${esc(a.gliederung)}</span>` : ""}`;

  function ausbilderPersonHtml(a) {
    if (a && a.user_id != null) {
      return `<div class="ausb-gewaehlt" tabindex="-1">${kontoHtml(a)}</div>
        ${a.zugriff === false ? `<p class="help ausb-ohne">${esc(OHNE_ZUGRIFF[a.ohne_zugriff] || OHNE_ZUGRIFF.stufe)}</p>` : ""}`;
    }
    return `<input type="search" class="ausb-suche" placeholder="Name oder E-Mail" autocomplete="off" enterkeyhint="search"
        aria-label="Person suchen – Name oder vollständige E-Mail-Adresse, ab 2 Zeichen">
      <ul class="ausb-treffer" aria-label="Gefundene Konten" hidden></ul>`;
  }

  function ausbilderZeileHtml(a) {
    a = a || {};
    const konto = a.user_id != null;
    return `<div class="ausb-zeile feld-gruppe"${konto ? ` data-uid="${a.user_id}"` : ""}>
      <div class="ausb-wer">${ausbilderPersonHtml(konto ? a : null)}</div>
      <input type="text" class="ausb-funktion" list="ausb-funktionen" placeholder="Funktion (optional)" value="${esc(a.funktion || "")}" aria-label="Funktion">
      <label class="inline ausb-leit"><input type="checkbox" class="ausb-leitung" ${a.ist_leitung ? "checked" : ""}> Leitung</label>
      ${S.entfernenKnopf("data-weg", "Zeile entfernen")}
    </div>`;
  }

  /* Die Zeilen des Dialogs als Liste für den Server – dazu je Eintrag die Zeile (Fehler des Servers nennen die Nummer
     in dieser Liste). Eine leere Zeile zählt nicht; eine angefangene Suche ohne gewählte Person ist ein Fehler am Feld. */
  function ausbilderLesen(body) {
    const liste = [], zeilen = [];
    let fehlt = null;
    $$(".ausb-zeile", body).forEach((z) => {
      const funktion = $(".ausb-funktion", z).value.trim();
      const ist_leitung = $(".ausb-leitung", z).checked;
      if (z.dataset.uid) {
        liste.push({ user_id: +z.dataset.uid, funktion, ist_leitung });
        zeilen.push(z);
      } else if (!fehlt && ($(".ausb-suche", z).value.trim() || funktion)) {
        fehlt = $(".ausb-suche", z);
      }
    });
    return { liste, zeilen, fehlt };
  }

  /* Suche in einer Zeile: verzögert (250 ms), die jüngste Eingabe gewinnt; Konten, die schon in einer anderen Zeile
     stehen, fehlen in den Treffern. Enter nimmt den einzigen Treffer. */
  function ausbilderSucheVerdrahten(liste) {
    let suchzeit = null, suchlauf = 0;
    const gewaehlt = () => new Set($$(".ausb-zeile[data-uid]", liste).map((z) => +z.dataset.uid));
    const waehlen = (z, k) => {
      z.dataset.uid = String(k.id);
      $(".ausb-wer", z).innerHTML = ausbilderPersonHtml({ user_id: k.id, name: k.name, gliederung: k.gliederung });
      $(".ausb-funktion", z).focus();          // weiter mit der Funktion der gewählten Person
    };
    async function suchen(feld) {
      const z = feld.closest(".ausb-zeile");
      const treffer = $(".ausb-treffer", z);
      const q = feld.value.trim();
      if (q.length < 2) { treffer.hidden = true; return; }
      const lauf = ++suchlauf;
      let r;
      try { r = await api(`${API}/nutzer?q=${encodeURIComponent(q)}`); }
      catch (e) { if (lauf === suchlauf) { treffer.innerHTML = `<li class="ausb-treffer-leer">${esc(e.message)}</li>`; treffer.hidden = false; } return; }
      if (lauf !== suchlauf || !feld.isConnected) return;
      const schon = gewaehlt();
      const konten = (r.nutzer || []).filter((k) => !schon.has(k.id));
      treffer.innerHTML = konten.length
        ? konten.map((k) => `<li><button type="button" class="ausb-konto" data-id="${k.id}">${kontoHtml(k)}</button></li>`).join("")
          + (r.mehr ? '<li class="ausb-treffer-leer">Mehr als 20 – bitte genauer.</li>' : "")
        : `<li class="ausb-treffer-leer">${(r.nutzer || []).length ? "Schon eingetragen."
          : q.includes("@") ? "Niemand gefunden – eine E-Mail-Adresse zählt nur vollständig; oder such nach dem Namen."
            : "Niemand gefunden – Ausbilder brauchen ein Konto mit Stufe in den Riegenkarten (die vergibt die Plattform-Verwaltung)."}</li>`;
      treffer.hidden = false;
      $$("button.ausb-konto", treffer).forEach((b) => b.addEventListener("click", () => waehlen(z, konten.find((k) => k.id === +b.dataset.id))));
    }
    liste.addEventListener("input", (e) => {
      if (!e.target.classList.contains("ausb-suche")) return;
      clearTimeout(suchzeit);
      suchzeit = setTimeout(() => suchen(e.target), 250);
    });
    liste.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || !e.target.classList.contains("ausb-suche")) return;
      e.preventDefault();
      const knoepfe = $$("button.ausb-konto", e.target.closest(".ausb-zeile"));
      if (knoepfe.length === 1) knoepfe[0].click();
      else if (knoepfe.length) knoepfe[0].focus();
    });
    liste.addEventListener("click", (e) => { const b = e.target.closest("[data-weg]"); if (b) b.closest(".ausb-zeile").remove(); });
  }

  async function lehrgangDialog(lg, nachher) {
    lg = lg || {};
    const neu = !lg.id;
    // Die Katalogauswahl gibt es nur beim Anlegen: Sie kopiert einmalig Leistungen hinein, ein
    // schon laufender Lehrgang hat längst eigene (siehe kataloge-Abschnitt weiter unten).
    const kataloge = neu ? await katalogeLaden() : [];
    dialogOeffnen(`<h2>${neu ? "Lehrgang anlegen" : "Lehrgang bearbeiten"}</h2>
      <label for="lg-titel">Titel / Lehrgangsbezeichnung</label>
      <input type="text" id="lg-titel" value="${esc(lg.titel)}" placeholder="z. B. Strömungsretter 1 (SR1)" required>
      <div class="field-row">
        <div><label for="lg-nummer">Lehrgangsnummer</label><input type="text" id="lg-nummer" value="${esc(lg.nummer)}" placeholder="z. B. 2026-0008"></div>
        <div><label for="lg-ort">Ort</label><input type="text" id="lg-ort" value="${esc(lg.ort)}"></div>
        <div><label for="lg-von">Datum von</label><input type="date" id="lg-von" value="${esc(lg.datum_von || "")}"></div>
        <div><label for="lg-bis">Datum bis</label><input type="date" id="lg-bis" value="${esc(lg.datum_bis || "")}"></div>
      </div>
      <label for="lg-status">Status</label>
      <select id="lg-status">
        ${Object.keys(STATUS).map((s) => `<option value="${s}" ${(lg.status || "geplant") === s ? "selected" : ""}>${STATUS[s][0]}</option>`).join("")}
      </select>
      <label>Lehrgangsleitung und Referierende${info("Lehrgangsleitung und Referierende", `Mehrere Personen können Lehrgangsleitung sein – dafür den Haken „Leitung“ setzen. Die Leitung darf den Lehrgang
        bearbeiten, Stammdaten pflegen, Prüfungen löschen und das Lehrgangsergebnis vermerken; alle anderen prüfen und haken ab.${mehrDazu("ausbilder")}`)}</label>
      <p class="help">Ausbilder ist nur, wer ein Konto mit Stufe in den Riegenkarten hat – suche die Person über Namen oder vollständige E-Mail-Adresse.</p>
      <div class="ausb-liste" id="ausb-liste">${(lg.ausbilder || []).map((a) => ausbilderZeileHtml(a)).join("")}</div>
      <datalist id="ausb-funktionen"><option value="Referierende:r"><option value="Seiltechnik"><option value="Wasser"><option value="Helfer:in"></datalist>
      <div class="btn-row"><button type="button" class="btn secondary small" id="ausb-plus"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Person<span class="k-anlegen"> anlegen</span></span></button></div>
      <div class="feld-kopf"><label for="lg-besch">Beschreibung / Bemerkungen</label>${diktatKnopf("lg-besch")}</div>
      <textarea id="lg-besch" placeholder="Ablauf, Treffpunkt, Besonderheiten …">${esc(lg.beschreibung)}</textarea>
      ${neu && kataloge.length ? `<label for="lg-katalog">Prüfungsleistungen aus Katalog übernehmen (optional)${info("Prüfungsleistungen aus Katalog", `Die Leistungen werden einmalig in diesen Lehrgang kopiert – eine spätere Änderung am Katalog wirkt sich nicht mehr
        aus. Weitere Leistungen lassen sich jederzeit einzeln ergänzen, auch während der Lehrgang schon läuft.${mehrDazu("katalog_vorlage")}`)}</label>
      <select id="lg-katalog"><option value="">– Keine Vorlage, leer beginnen –</option>
        ${kataloge.map((k) => `<option value="${k.id}">${esc(k.titel)} (${plural(k.leistungen_anzahl, "Leistung", "Leistungen")})</option>`).join("")}</select>` : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="lg-save" type="button">${neu ? "Lehrgang anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        const liste = $("#ausb-liste", body);
        // Ein neuer Lehrgang beginnt mit der anlegenden Person als Leitung – der Server trüge sie ohnehin
        // ein; so sieht man es gleich und kann weitere Leitungen daneben setzen.
        const ich = STROEMIS.user || {};
        if (!liste.children.length && ich.id) liste.insertAdjacentHTML("beforeend", ausbilderZeileHtml({ user_id: ich.id, name: ich.name || ich.email, ist_leitung: true }));
        // Eine leere Zeile für beides: Die Funktion ist frei, der Haken „Leitung“ steht jeder Person offen.
        $("#ausb-plus", body).onclick = () => {
          liste.insertAdjacentHTML("beforeend", ausbilderZeileHtml({}));
          $(".ausb-zeile:last-child .ausb-suche", liste).focus();
        };
        ausbilderSucheVerdrahten(liste);
        if (neu) fokus($("#lg-titel", body));
        $("#lg-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const d = {
            titel: $("#lg-titel", body).value.trim(), nummer: $("#lg-nummer", body).value.trim(), ort: $("#lg-ort", body).value.trim(),
            datum_von: $("#lg-von", body).value || null, datum_bis: $("#lg-bis", body).value || null,
            status: $("#lg-status", body).value, beschreibung: $("#lg-besch", body).value,
          };
          const ausb = ausbilderLesen(body);
          d.ausbilder = ausb.liste;
          if (neu && $("#lg-katalog", body)) d.katalog_id = $("#lg-katalog", body).value ? +$("#lg-katalog", body).value : null;
          if (!d.titel) return S.feldFehler($("#lg-titel", body), "Bitte einen Titel angeben.");
          if (d.datum_von && d.datum_bis && d.datum_bis < d.datum_von) return S.feldFehler($("#lg-bis", body), "Das Enddatum liegt vor dem Anfang.");
          if (ausb.fehlt) return S.feldFehler(ausb.fehlt, KEIN_KONTO);
          knopf.disabled = true;
          try {
            const r = neu ? await api(`${API}/lehrgaenge`, { method: "POST", body: d })
                          : await api(`${API}/lehrgaenge/${lg.id}`, { method: "PUT", body: d });
            dlg.close();
            // Neu: „Lehrgang angelegt“ meldet erst die Seite des neuen Lehrgangs (nachher springt dorthin).
            if (!neu) toast("Gespeichert");
            if (nachher) await nachher(r.lehrgang);
          } catch (e) {
            // Nennt der Server eine Ausbilderzeile (kein Konto, keine Stufe), steht die Meldung an ihr.
            const z = e.daten && Number.isInteger(e.daten.zeile) ? ausb.zeilen[e.daten.zeile] : null;
            const feld = z && ($(".ausb-gewaehlt", z) || $(".ausb-suche", z));
            if (feld) { knopf.disabled = false; S.feldFehler(feld, e.message); } else S.fehlschlag(knopf, e, body);
          }
          finally { knopf.disabled = false; }
        };
      });
  }

  /* Kopieren: Leistungen und Voraussetzungs-Definitionen wandern mit, Teilnehmende und
     Ergebnisse nicht. Titel und Datum fragt der Dialog ab – ein Lehrgang ohne Datum wäre in der
     Liste nicht zu finden. */
  function kopierenDialog(lg) {
    dialogOeffnen(`<h2>Lehrgang kopieren</h2>
      <p class="help">Übernommen werden Titel, Ort, Referierende mit Riegenkarten-Stufe, Beschreibung, Voraussetzungen und alle
        Prüfungsleistungen. Teilnehmende, Häkchen, Bewertungen und Medien bleiben beim Original.</p>
      <label for="kp-titel">Titel des neuen Lehrgangs</label>
      <input type="text" id="kp-titel" value="${esc(lg.titel)} (Kopie)">
      <div class="field-row">
        <div><label for="kp-von">Datum von</label><input type="date" id="kp-von"></div>
        <div><label for="kp-bis">Datum bis</label><input type="date" id="kp-bis"></div>
      </div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="kp-go" type="button">Kopie anlegen</button></div>`,
      (dlg, body) => {
        $("#kp-go", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const d = { titel: $("#kp-titel", body).value.trim(), datum_von: $("#kp-von", body).value || null, datum_bis: $("#kp-bis", body).value || null };
          if (d.datum_von && d.datum_bis && d.datum_bis < d.datum_von) return S.feldFehler($("#kp-bis", body), "Das Enddatum liegt vor dem Anfang.");
          knopf.disabled = true;
          try {
            const r = await api(`${API}/lehrgaenge/${lg.id}/kopieren`, { method: "POST", body: d });
            // Ausbilder ohne passendes Konto (keine Stufe, deaktiviert) kommen nicht mit (Rechte-Befund B3) – der Satz nennt sie.
            const nicht = r.ausbilder_nicht_uebernommen || [];
            meldungMerken(`Kopie „${r.lehrgang.titel}“ angelegt`
              + (nicht.length ? `. ${NICHT_UEBERNOMMEN}${nicht.map((a) => a.name).join(", ")}` : ""));
            location.href = `/riegenkarten/${r.lehrgang.id}#leistungen`;
          } catch (e) { S.fehlschlag(knopf, e, body); }
        };
      });
  }

  async function lehrgangLoeschen(lg) {
    const text = `Lehrgang „${lg.titel}“ endgültig löschen? Alle Teilnehmenden, Voraussetzungen, Bewertungen und Medien werden gelöscht.`;
    if (!(await S.confirm(text, "Endgültig löschen"))) return;
    try {
      await api(`${API}/lehrgaenge/${lg.id}`, { method: "DELETE" });
      if (ANSICHT === "liste") { toast("Lehrgang gelöscht"); await listeLaden(); }
      else { meldungMerken("Lehrgang gelöscht"); location.href = "/riegenkarten"; }
    } catch (e) { toast(e.message, true); }
  }

  /* ==========================================================================================
     Lehrgangsliste
     ========================================================================================== */
  function renderListe() {
    S.titel([], "pruefungen");
    root.innerHTML = `
      <div class="page-head"><h1>Riegenkarten</h1>${anleitungKopf("uebersicht")}
        ${darfAnlegen() ? `<div class="btn-row"><button class="btn secondary" data-act="lg-import">Import</button>
          <a class="btn secondary" href="/riegenkarten/kataloge">Kataloge</a>
          <button class="btn" data-act="lg-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Lehrgang<span class="k-anlegen"> anlegen</span></span></button></div>` : ""}</div>
      <div class="su-banner hidden" id="su-banner"></div>
      <div class="filter">
        <input type="search" id="lg-suche" placeholder="Titel, Ort oder Nummer" aria-label="Lehrgänge durchsuchen" autocomplete="off">
        <select id="lg-jahr" aria-label="Jahr"><option value="">Alle Jahre</option></select>
      </div>
      <div id="lg-liste"><p class="help">Wird geladen …</p></div>`;
    let timer;
    $("#lg-suche").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(listeLaden, 250); });
    $("#lg-jahr").addEventListener("change", () => listeLaden());
    listeLaden(true);
    bannerZeichnen();
  }

  async function listeLaden(erstmal) {
    const q = ($("#lg-suche") || {}).value || "", jahr = ($("#lg-jahr") || {}).value || "";
    const ziel = $("#lg-liste");
    if (!ziel) return;
    let d;
    try { d = await api(`${API}/lehrgaenge?q=${encodeURIComponent(q.trim())}&jahr=${encodeURIComponent(jahr)}`); }
    catch (e) { ziel.innerHTML = `<p class="notice">Die Lehrgänge ließen sich nicht laden: ${esc(e.message)}</p>`; return; }
    state.liste = d.lehrgaenge || [];
    // Die Jahresauswahl kommt aus der ungefilterten Liste – sonst schrumpfte sie nach dem ersten
    // Filtern auf das gewählte Jahr und ließe sich nicht mehr zurückstellen.
    if (erstmal === true || !state.jahre.length) {
      state.jahre = [...new Set(state.liste.map((l) => (l.datum_von || "").slice(0, 4)).filter((j) => /^\d{4}$/.test(j)))].sort().reverse();
      const sel = $("#lg-jahr");
      sel.innerHTML = '<option value="">Alle Jahre</option>' + state.jahre.map((j) => `<option value="${j}">${j}</option>`).join("");
      sel.value = jahr;
    }
    if (!state.liste.length) {
      ziel.innerHTML = `<div class="leerzustand"><strong>${q || jahr ? "Kein Lehrgang passt zur Suche." : "Noch keine Lehrgänge"}</strong>
        ${q || jahr ? "" : darfAnlegen() ? "Lege einen Lehrgang an oder importiere eine Excel-Teilnehmerliste."
          : "Hier stehen die Lehrgänge, in denen du als Ausbilder eingetragen bist."}</div>`;
      return;
    }
    // Die Statusspalte hat eine feste Breite für „abgeschlossen“ in einer Zeile (Gerätetest F2: bei 883 px 84 px breit,
    // die Marke brach zu „abgeschlo/ssen“). Ab 760 px Inhalt ist die Liste eine Tabelle (Teil X, F1): „Teilnehmende“ mit
    // weicher Trennstelle und 13 % breit, sonst lief der Kopf bei 800 px über seine Spalte.
    ziel.innerHTML = `<table class="list" id="lg-tabelle">
      <colgroup><col style="width:28%"><col style="width:15%"><col class="lg-status-spalte"><col style="width:13%"><col style="width:18%"><col style="width:16%"></colgroup>
      <thead><tr><th>Lehrgang</th><th>Datum</th><th>Status</th><th>Teil&shy;nehmende</th><th>Fortschritt</th><th></th></tr></thead>
      <tbody>${state.liste.map((lg) => `<tr data-id="${lg.id}">
        <td data-l="Lehrgang"><a class="titel" href="/riegenkarten/${lg.id}">${esc(lg.titel)}</a>
          ${lg.nummer ? `<div class="nummer">Nr. ${esc(lg.nummer)}</div>` : ""}${lg.ort ? `<div class="small muted">${esc(lg.ort)}</div>` : ""}${lgHinweisHtml(lg)}</td>
        <td data-l="Datum">${esc(spanne(lg.datum_von, lg.datum_bis)) || '<span class="muted">–</span>'}</td>
        <td data-l="Status">${statusMarke(lg.status)}</td>
        <td data-l="Teilnehmende">${lg.tn_anzahl}</td>
        <td data-l="Fortschritt">${fortschrittHtml(lg, { ohneHinweise: true })}</td>
        <td class="tabelle-aktionen"><div class="btn-row">
          <a class="btn secondary small" href="/riegenkarten/${lg.id}">Öffnen</a>
          ${lg.darf_leiten ? zeilenMenue([["Bearbeiten", `data-act="lg-edit" data-id="${lg.id}"`],
            ...(lg.darf_kopieren ? [["Kopieren", `data-act="lg-kopie" data-id="${lg.id}"`]] : []),
            ["Löschen", `data-act="lg-del" data-id="${lg.id}"`]]) : ""}
        </div></td></tr>`).join("")}</tbody></table>`;
  }

  /* ==========================================================================================
     Kataloge: Vorlagen für Prüfungsleistungen, unabhängig von einem Lehrgang. Lesen und anlegen ab Redakteur (Auswahl
     beim Anlegen eines Lehrgangs); ändern und löschen ein Redakteur nur seine eigenen, die Verwaltung alle
     (darf_bearbeiten vom Server) – anders als beim Lehrgang gibt es keine Leitung, die dafür geradestünde.
     ========================================================================================== */
  async function katalogeLaden(neu) {
    if (state.kataloge && !neu) return state.kataloge;
    try { state.kataloge = (await api(`${API}/kataloge`)).kataloge || []; }
    catch (e) { toast("Die Kataloge ließen sich nicht laden: " + e.message, true); state.kataloge = []; }
    return state.kataloge;
  }

  async function renderKataloge() {
    S.titel("Prüfungsleistungskataloge", "pruefungen");
    root.innerHTML = `<a class="zurueck" href="/riegenkarten">← Alle Lehrgänge</a>
      <div class="page-head"><h1>Prüfungsleistungskataloge${info("Prüfungsleistungskataloge", `Ein Katalog ist eine Vorlage: Seine Prüfungsleistungen lassen sich beim Anlegen eines Lehrgangs
        einmalig übernehmen. Spätere Änderungen am Katalog wirken sich nicht mehr auf schon angelegte Lehrgänge aus.${mehrDazu("kataloge_info")}`)}</h1>
        ${darfAnlegen() ? '<div class="btn-row"><button class="btn" data-act="kat-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Katalog<span class="k-anlegen"> anlegen</span></span></button></div>' : ""}</div>
      <div id="kat-liste"><p class="help">Wird geladen …</p></div>`;
    const ziel = $("#kat-liste");
    const kataloge = await katalogeLaden(true);
    if (!ziel) return;
    if (!kataloge.length) {
      ziel.innerHTML = '<div class="leerzustand"><strong>Noch keine Kataloge</strong>Lege einen an, um Prüfungsleistungen als Vorlage bereitzustellen.</div>';
      return;
    }
    ziel.innerHTML = `<table class="list">
      <colgroup><col style="width:32%"><col style="width:38%"><col style="width:10%"><col style="width:20%"></colgroup>
      <thead><tr><th>Katalog</th><th>Beschreibung</th><th>Leistungen</th><th></th></tr></thead>
      <tbody>${kataloge.map((k) => `<tr data-id="${k.id}">
        <td data-l="Katalog"><a class="titel" href="/riegenkarten/kataloge/${k.id}">${esc(k.titel)}</a></td>
        <td data-l="Beschreibung">${k.beschreibung ? esc(kuerzen(k.beschreibung, 140)) : '<span class="muted">–</span>'}</td>
        <td data-l="Leistungen">${k.leistungen_anzahl}</td>
        <td class="tabelle-aktionen"><div class="btn-row">
          <a class="btn secondary small" href="/riegenkarten/kataloge/${k.id}">Öffnen</a>
          ${k.darf_bearbeiten ? zeilenMenue([["Bearbeiten", `data-act="kat-edit" data-id="${k.id}"`], ["Löschen", `data-act="kat-del" data-id="${k.id}"`]]) : ""}
        </div></td></tr>`).join("")}</tbody></table>`;
  }

  function katalogDialog(k) {
    k = k || {};
    const neu = !k.id;
    dialogOeffnen(`<h2>${neu ? "Katalog anlegen" : "Katalog bearbeiten"}</h2>
      <label for="kat-titel">Titel</label>
      <input type="text" id="kat-titel" value="${esc(k.titel)}" placeholder="z. B. Strömungsretter 1 (SR1)" required>
      <label for="kat-besch">Beschreibung (optional)</label>
      <textarea id="kat-besch" placeholder="Wofür ist dieser Katalog gedacht, welcher Lehrgangstyp?">${esc(k.beschreibung)}</textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="kat-save" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        if (neu) fokus($("#kat-titel", body));
        $("#kat-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const titel = $("#kat-titel", body).value.trim();
          if (!titel) return S.feldFehler($("#kat-titel", body), "Bitte einen Titel angeben.");
          const d = { titel, beschreibung: $("#kat-besch", body).value };
          knopf.disabled = true;
          try {
            const r = neu ? await api(`${API}/kataloge`, { method: "POST", body: d })
                          : await api(`${API}/kataloge/${k.id}`, { method: "PUT", body: d });
            dlg.close();
            state.kataloge = null;   // Titel/Beschreibung geändert – Auswahlliste neu laden.
            if (neu) { toast("Katalog angelegt"); location.href = `/riegenkarten/kataloge/${r.katalog.id}`; return; }
            toast("Gespeichert");
            if (ANSICHT === "kataloge") await renderKataloge();
            else { state.katalog = r.katalog; renderKatalogSeite(); }
          } catch (e) { S.fehlschlag(knopf, e, body); }
          finally { knopf.disabled = false; }
        };
      });
  }

  async function katalogLoeschen(k) {
    const text = `Katalog „${k.titel}“ löschen? Schon angelegte Lehrgänge behalten ihre Prüfungsleistungen – nur die Vorlage verschwindet.`;
    if (!(await S.confirm(text, "Endgültig löschen"))) return;
    try {
      await api(`${API}/kataloge/${k.id}`, { method: "DELETE" });
      state.kataloge = null;
      toast("Katalog gelöscht");
      if (ANSICHT === "katalog") location.href = "/riegenkarten/kataloge"; else await renderKataloge();
    } catch (e) { toast(e.message, true); }
  }

  async function loadKatalogDetail() {
    const d = await api(`${API}/kataloge/${KATALOG_ID}`);
    state.katalog = d.katalog;
  }

  function renderKatalogSeite() {
    const k = state.katalog;
    if (!k) return;
    const admin = !!k.darf_bearbeiten;      // eigener Katalog ab Redakteur, alle für die Verwaltung
    const ls = k.leistungen || [];
    S.titel(k.titel, "pruefungen");
    root.innerHTML = `<a class="zurueck" href="/riegenkarten/kataloge">← Alle Kataloge</a>
      <div class="page-head"><h1>${esc(k.titel)}</h1>${anleitungKopf("katalog")}
        ${admin ? `<div class="btn-row">${S.menue({ art: "zeilenmenue", klein: false, eintraege: [
          { text: "Bearbeiten", attrs: `data-act="kat-edit" data-id="${k.id}"` },
          { text: "Löschen", attrs: `data-act="kat-del" data-id="${k.id}"` }] })}</div>` : ""}</div>
      ${k.beschreibung ? `<details class="beschreibung-kopf"><summary>Beschreibung</summary><div class="md">${esc(k.beschreibung).replace(/\n/g, "<br>")}</div></details>` : ""}
      <div class="abschnittskopf"><h2>Prüfungsleistungen</h2>
        ${admin ? '<div class="btn-row"><button class="btn small" data-act="kl-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Prüfungsleistung<span class="k-anlegen"> anlegen</span></span></button></div>' : ""}</div>
      ${!ls.length ? '<div class="leerzustand"><strong>Noch keine Prüfungsleistungen</strong>Sie werden beim Anlegen eines Lehrgangs mit diesem Katalog als Vorlage in den Lehrgang kopiert.</div>'
        : ls.map((l, i) => leistungKarteHtml(l, i, ls.length, admin, "kl")).join("")}`;
  }

  function katalogLeistungDialog(kid, l) {
    l = l || {};
    const neu = !l.id;
    dialogOeffnen(`<h2>${neu ? "Prüfungsleistung anlegen" : "Prüfungsleistung bearbeiten"}</h2>
      <label for="kl-bez">Bezeichnung</label>
      <input type="text" id="kl-bez" value="${esc(l.bezeichnung)}" placeholder="z. B. Wurfsackwurf auf Ziel, Aufbau Flaschenzug 3:1" required>
      <label for="kl-zeit">Zeitansatz${info("Zeitansatz", ZEITANSATZ_INFO + mehrDazu("zeitansatz"))} (mm:ss oder 300 für 3:00) – leer lassen, wenn es keine Sollzeit gibt</label>
      <input type="text" id="kl-zeit" class="zeitfeld" inputmode="numeric" placeholder="mm:ss" autocomplete="off"
             value="${l.zeitansatz_sekunden != null ? fmtZeit(l.zeitansatz_sekunden) : ""}">
      <label>Beschreibung – Ablauf</label>
      <div id="kl-editor"></div>
      <label>Kriterienliste (optional)${info("Kriterienliste", `${KRITERIEN_INFO} Wird beim Anlegen eines Lehrgangs aus diesem Katalog
        als Vorlage in die neue Prüfungsleistung kopiert.${mehrDazu("kriterienliste")}`)}</label>
      ${neu ? '<div id="krit-wrap"></div>' : kriterienListeHtml(l)}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="kl-save" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        const holen = mdEditorEinrichten(dlg, body, "#kl-editor", l.beschreibung_md, "kl-md");
        fokus($("#kl-bez", body));
        // Neu: die Kriterien sind nur ein lokaler Entwurf, bis die Leistung selbst existiert.
        // Bestehend: jede Änderung persistiert sofort über die eigenen Kriterien-Endpunkte.
        const kritEntwurf = neu ? kriterienEntwurfEinrichten(body) : null;
        if (!neu) {
          const kritBinden = () => {
            const anlegen = async () => {
              const feld = $("#krit-neu-text", body);
              const bez = feld.value.trim();
              if (!bez) return feld.focus();
              try {
                await api(`${API}/katalog-leistungen/${l.id}/kriterien`, { method: "POST", body: { bezeichnung: bez } });
                await kritNachziehen();
                $("#krit-neu-text", body).focus();
                toast("Kriterium angelegt");
              } catch (e) { toast(schreibFehler(e).message, true); }
            };
            $("#krit-neu-go", body).onclick = anlegen;
            $("#krit-neu-text", body).addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); anlegen(); } });
            $$("[data-krit-bez]", body).forEach((inp) => {
              const li = inp.closest("li"), kritid = +li.dataset.kid;
              const alt = inp.value;
              inp.addEventListener("blur", async () => {
                const bez = inp.value.trim();
                if (!bez) { inp.value = alt; return; }
                if (bez === alt) return;
                try { await api(`${API}/katalog-kriterien/${kritid}`, { method: "PUT", body: { bezeichnung: bez } }); await kritNachziehen(); toast("Umbenannt"); }
                catch (e) { inp.value = alt; toast(e.message, true); }
              });
              inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
            });
            // Am je Zeichnung neuen Rahmen gebunden, nicht am dauerhaften Dialogkörper – sonst
            // häuften sich die Handler bei jedem Neuzeichnen (wie bei den Voraussetzungen).
            $("#krit-wrap", body).addEventListener("click", async (e) => {
              const b = e.target.closest("button[data-krit-hoch],button[data-krit-runter],button[data-krit-del]");
              if (!b) return;
              const li = b.closest("li"), kritid = +li.dataset.kid;
              const ks = l.kriterien || [];
              const i = ks.findIndex((x) => x.id === kritid);
              try {
                if (b.hasAttribute("data-krit-del")) {
                  if (!(await S.confirm(`Kriterium „${ks[i].bezeichnung}“ löschen?`))) return;
                  await api(`${API}/katalog-kriterien/${kritid}`, { method: "DELETE" });
                } else {
                  const j = b.hasAttribute("data-krit-hoch") ? i - 1 : i + 1;
                  if (j < 0 || j >= ks.length) return;
                  [ks[i], ks[j]] = [ks[j], ks[i]];
                  await api(`${API}/katalog-leistungen/${l.id}/kriterien/reihenfolge`, { method: "PUT", body: { ids: ks.map((x) => x.id) } });
                }
                await kritNachziehen();
                toast(b.hasAttribute("data-krit-del") ? "Kriterium gelöscht" : "Reihenfolge gespeichert");
              } catch (err) { toast(schreibFehler(err).message, true); }
            });
          };
          // Nach jeder Änderung: frischen Stand holen (auch für die Seite hinter dem Dialog – der
          // Kriterien-Zähler auf der Karte soll stimmen), dann nur den Rahmen neu zeichnen.
          const kritNachziehen = async () => {
            try {
              await loadKatalogDetail();
              const frisch = (state.katalog.leistungen || []).find((x) => x.id === l.id);
              if (frisch) l.kriterien = frisch.kriterien;
            } catch (e) { /* lokaler Stand bleibt, falls das Nachladen scheitert */ }
            $("#krit-wrap", body).outerHTML = kriterienListeHtml(l);
            kritBinden();
            renderKatalogSeite();
          };
          kritBinden();
        }
        $("#kl-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const bez = $("#kl-bez", body).value.trim();
          if (!bez) return S.feldFehler($("#kl-bez", body), "Bitte eine Bezeichnung angeben.");
          const z = zeitLesen($("#kl-zeit", body).value);
          if (!z.ok) return S.feldFehler($("#kl-zeit", body), "Zeitansatz bitte als mm:ss angeben, z. B. 03:00 – oder nur Ziffern: 300.");
          const d = { bezeichnung: bez, beschreibung_md: holen(), zeitansatz_sekunden: z.wert };
          if (neu) d.kriterien = kritEntwurf.werte();
          knopf.disabled = true;
          try {
            if (neu) await api(`${API}/kataloge/${kid}/leistungen`, { method: "POST", body: d });
            else await api(`${API}/katalog-leistungen/${l.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Prüfungsleistung angelegt" : "Gespeichert");
            await loadKatalogDetail(); renderKatalogSeite();
          } catch (e) { S.fehlschlag(knopf, e, body); }
          finally { knopf.disabled = false; }
        };
      }, ["wide"]);
  }

  async function katalogLeistungLoeschen(kid, l) {
    if (!(await S.confirm(`Prüfungsleistung „${l.bezeichnung}“ aus dem Katalog löschen?`))) return;
    try {
      await api(`${API}/katalog-leistungen/${l.id}`, { method: "DELETE" });
      toast("Prüfungsleistung gelöscht");
      await loadKatalogDetail(); renderKatalogSeite();
    } catch (e) { toast(e.message, true); }
  }

  async function katalogLeistungVerschieben(kid, lid, richtung) {
    const ls = state.katalog.leistungen;
    const i = ls.findIndex((x) => x.id === lid), j = i + richtung;
    if (i < 0 || j < 0 || j >= ls.length) return;
    [ls[i], ls[j]] = [ls[j], ls[i]];
    try {
      await api(`${API}/kataloge/${kid}/leistungen/reihenfolge`, { method: "PUT", body: { ids: ls.map((x) => x.id) } });
      renderKatalogSeite();
      toast("Reihenfolge gespeichert");     // still war das nicht zu sehen (Gerätetest FT4)
    } catch (e) { [ls[i], ls[j]] = [ls[j], ls[i]]; toast(schreibFehler(e).message, true); }
  }

  /* ==========================================================================================
     Lehrgangsseite mit Reitern
     ========================================================================================== */
  const REITER = ["teilnehmer", "leistungen", "bewertung", "maengel"];

  async function loadDetail() {
    const d = await api(`${API}/lehrgaenge/${LEHRGANG_ID}`);
    state.lehrgang = d.lehrgang;
    return d.lehrgang;
  }

  function reiterAusHash() {
    const h = (location.hash || "").replace("#", "");
    return REITER.includes(h) ? h : "teilnehmer";
  }

  /* Leitung(en) und übrige Referierende für Kopf und Druckansicht – mit den Namen ihrer Konten (name-einheit), Funktion
     in Klammern, „ohne Zugriff“ bei einem Konto, das den Lehrgang nicht sieht (keine Stufe, deaktiviert). Bei einer
     Leitung ist die Funktion „Lehrgangsleitung“ (etwa aus der ISC-Liste) nur eine Wiederholung – weg damit. */
  function ausbilderZeile(lg) {
    const person = (a) => {
      const f = a.ist_leitung && /^(lehrgangs)?leitung$/i.test((a.funktion || "").trim()) ? "" : a.funktion;
      return `<span class="name-einheit">${esc(a.name)}</span>${f ? ` <span class="muted">(${esc(f)})</span>` : ""}`
        + (a.zugriff === false ? ` <span class="badge grey" title="${esc(OHNE_ZUGRIFF[a.ohne_zugriff] || OHNE_ZUGRIFF.stufe)}">ohne Zugriff</span>` : "");
    };
    const leitungen = (lg.ausbilder || []).filter((a) => a.ist_leitung).map(person).join(", ");
    const referierende = (lg.ausbilder || []).filter((a) => !a.ist_leitung).map(person).join(", ");
    return [leitungen ? `<span class="muted">Leitung:</span> ${leitungen}` : "",
            referierende ? `<span class="muted">Referierende:</span> ${referierende}` : ""].filter(Boolean).join(" · ");
  }

  /* Kopf des Lehrgangs (Gerätetest B3/Q3): Bis zu den Reitern war fast eine Bildschirmhöhe zu rollen, im Querformat
     füllte der Kopf den ganzen ersten Bildschirm. Jetzt
     - kleben die Reiter unter der Kopfleiste (.reiter-kleben) – Wechsel zwischen Bewertung und Mängeln ohne Hochrollen;
     - stehen Status, Nummer, Datum, Ort, Leitung, Beschreibung und Fortschritt am Telefon (≤ 760 px) und bei weniger als
       600 px Höhe in der zugeklappten Zeile „Angaben zum Lehrgang“ (Status, Datum und Stand stehen auch zugeklappt
       darin); breit und hoch genug ist sie immer offen und ohne Zeile darüber;
     - stehen „Bearbeiten“ und „Import“ (nur die Leitung) im Menü „Mehr“ der Seite wie auf der Katalogseite. */
  const kompaktMq = window.matchMedia("(max-width: 760px), (max-height: 599px)");
  const kopfOffen = () => !kompaktMq.matches || state.kopfOffen === true;
  kompaktMq.addEventListener("change", () => { const d = $("details.lg-kopf", root); if (d) d.open = kopfOffen(); });
  /* Wie weit oben die Reiter kleben: unter der Kopfleiste, solange sie selbst klebt – rollt sie mit (wenig Höhe, offene
     Tastatur), ganz oben. Gemessen statt als feste Zahl, damit beides stimmt. */
  function reiterObenSetzen() {
    const k = document.querySelector("header.bauchbinde");
    const pos = k ? getComputedStyle(k).position : "";
    root.style.setProperty("--reiter-oben", `${pos === "sticky" || pos === "fixed" ? Math.round(k.getBoundingClientRect().height) : 0}px`);
  }
  if (ANSICHT === "lehrgang") {
    window.addEventListener("resize", reiterObenSetzen);
    if (window.visualViewport) window.visualViewport.addEventListener("resize", reiterObenSetzen);
    new MutationObserver(reiterObenSetzen).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  }

  function renderLehrgangSeite() {
    const lg = state.lehrgang;
    if (!lg) return;
    const ausb = ausbilderZeile(lg);
    const best = lg.ergebnis_bestanden || 0, nicht = lg.ergebnis_nicht_bestanden || 0;
    const ges = lg.zellen_gesamt || 0, ab = lg.zellen_abgenommen || 0;
    // Rollstand der Matrizen und offene Beschreibungen überleben das Neuzeichnen – sonst sprang die
    // Matrix nach jedem Speichern auf dem Tablet zurück in die erste Spalte. Die Angaben zum Lehrgang und die Karten
    // „Voraussetzungen“ merken sich ihren Zustand selbst (state.kopfOffen, state.vorKlapp).
    const rollstaende = $$(".table-scroll", root).map((el) => el.scrollLeft);
    const AUFKLAPPER = "details:not(.lg-kopf):not(.vor-klapp):not(.menue)";
    const aufgeklappt = $$(AUFKLAPPER, root).map((d) => d.open);
    S.titel(lg.titel, "pruefungen");                  // Reiter des Browsers (Browserprüfung vor dem Merge, V2)
    const datum = lg.datum_von || lg.datum_bis ? esc(spanne(lg.datum_von, lg.datum_bis)) : "";
    root.innerHTML = `
      <a class="zurueck" href="/riegenkarten">← Alle Lehrgänge</a>
      <div class="page-head"><h1>${esc(lg.titel)}</h1>${anleitungKopf("lehrgang")}
        ${lg.darf_leiten ? `<div class="btn-row">${S.menue({ klein: false, eintraege: [
          { text: "Bearbeiten", attrs: `data-act="lg-edit" data-id="${lg.id}"` },
          { text: "Import", attrs: `data-act="lg-import-in" data-id="${lg.id}"` }] })}</div>` : ""}</div>
      <details class="lg-kopf"${kopfOffen() ? " open" : ""}>
        <summary><span class="lg-kopf-titel">Angaben zum Lehrgang</span>
          <span class="lg-kopf-kurz">${statusMarke(lg.status)}${datum ? `<span>${datum}</span>` : ""}<span>${ab}/${ges} abgenommen</span></span></summary>
        <div class="kopf-meta">${statusMarke(lg.status)}${lg.nummer ? `<span>Nr. ${esc(lg.nummer)}</span>` : ""}
          ${datum ? `<span>${datum}</span>` : ""}${lg.ort ? `<span>${esc(lg.ort)}</span>` : ""}
          <span>${lg.tn_anzahl} Teilnehmende</span>
          ${best || nicht ? `<span class="erg-zaehler" title="Vermerkte Lehrgangsergebnisse"><b class="ja">${best} bestanden</b> · <b class="nein">${nicht} nicht bestanden</b></span>` : ""}</div>
        ${ausb ? `<p class="ausbilder-zeile">${ausb}</p>` : ""}
        ${lg.beschreibung ? `<details class="beschreibung-kopf"><summary>Beschreibung</summary><div class="md">${esc(lg.beschreibung).replace(/\n/g, "<br>")}</div></details>` : ""}
        ${fortschrittHtml(lg)}
      </details>
      <div class="reiter-kleben">
        <div class="su-banner hidden" id="su-banner"></div>
        <div class="c-tabs reiter reiter-linie" role="tablist">
          <button type="button" role="tab" data-reiter="teilnehmer">Teilnehmende<span class="reiter-zahl">${lg.tn_anzahl}</span></button>
          <button type="button" role="tab" data-reiter="leistungen">Leistungen<span class="reiter-zahl">${lg.leistungen_anzahl}</span></button>
          <button type="button" role="tab" data-reiter="bewertung">Bewertung</button>
          <button type="button" role="tab" data-reiter="maengel">Mängel${lg.offene_maengel ? `<span class="reiter-zahl offen" title="offene Mängel">${lg.offene_maengel}</span>` : ""}</button>
        </div>
      </div>
      <div id="reiter-inhalt"></div>`;
    reiterObenSetzen();
    renderReiter();
    bannerZeichnen();
    $$(".table-scroll", root).forEach((el, i) => { if (rollstaende[i]) el.scrollLeft = rollstaende[i]; });
    $$(AUFKLAPPER, root).forEach((d, i) => { if (aufgeklappt[i]) d.open = true; });
  }
  // Wer die Angaben oder eine Karte „Voraussetzungen“ auf- oder zuklappt, behält das beim Neuzeichnen (nach jedem Häkchen).
  root.addEventListener("toggle", (e) => {
    const d = e.target;
    if (!(d instanceof HTMLDetailsElement)) return;
    if (d.classList.contains("lg-kopf") && kompaktMq.matches) state.kopfOffen = d.open;
    else if (d.classList.contains("vor-klapp")) state.vorKlapp[+d.dataset.tid] = d.open;
  }, true);

  function renderReiter() {
    const lg = state.lehrgang;
    const ziel = $("#reiter-inhalt");
    if (!lg || !ziel) return;
    $$("[data-reiter]", root).forEach((b) => b.classList.toggle("sel", b.dataset.reiter === state.reiter));
    if (state.reiter === "teilnehmer") ziel.innerHTML = teilnehmerHtml(lg);
    else if (state.reiter === "leistungen") ziel.innerHTML = leistungenHtml(lg);
    else if (state.reiter === "bewertung") { ziel.innerHTML = bewertungHtml(lg); bewertungBinden(); }
    else if (state.reiter === "maengel") { ziel.innerHTML = maengelHtml(lg); maengelBinden(); maengelLaden(); }
  }

  /* --- Reiter Teilnehmende: Voraussetzungen abhaken -------------------------------------- */
  function stempelHtml(st) {
    if (!st) return "";
    const wer = kurzName(st.gesetzt_von_name), wann = fmtDate(st.gesetzt_am, true);
    const quelle = st.quelle === "import" ? " · importiert" : "";
    return `${st.erfuellt ? "✓" : "✗"} ${esc(wer)} · ${esc(wann)}${quelle}`;
  }

  function teilnehmerHtml(lg) {
    const vor = lg.voraussetzungen || [], tns = lg.teilnehmer || [];
    const leitung = darfLeiten();
    const kopf = `<div class="abschnittskopf"><h2>Teilnehmende${eingefrorenInfo(tns)}</h2>
      ${leitung ? `<div class="btn-row"><button class="btn secondary small" data-act="vor-verwalten">Voraussetzungen verwalten</button>
        <button class="btn small" data-act="tn-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Teilnehmende<span class="k-anlegen"> anlegen</span></span></button></div>` : ""}</div>`;
    // Hierher führt „Lehrgang anlegen“ (Gerätetest FT6) – der Leerzustand sagt, wie es weitergeht; der Import steht im Menü
    // „Mehr“ oben.
    if (!tns.length) {
      return kopf + `<div class="leerzustand"><strong>Noch niemand eingetragen</strong>${leitung ? "Lege Teilnehmende an oder importiere die Excel-Teilnehmerliste (oben unter „Mehr“ → „Import“) – daraus kommen auch die Voraussetzungen." : "Die Lehrgangsleitung legt sie an oder importiert die Excel-Teilnehmerliste."}</div>`;
    }
    const hinweis = vor.length ? "" : `<p class="leerzustand">Noch keine Voraussetzungen angelegt${leitung ? " – über „Voraussetzungen verwalten“ oder den Import." : "."}</p>`;
    // Der Name ist für die Leitung ein Knopf (Bearbeiten), für alle anderen nur Text.
    const nameHtml = (tn) => (leitung
      ? `<button type="button" class="linkbtn tn-name" data-act="tn-edit" data-tid="${tn.id}" title="Bearbeiten">${esc(tnName(tn))}</button>`
      : `<span class="tn-name">${esc(tnName(tn))}</span>`);
    // Desktop: Tabelle TN × Voraussetzungen, erste Spalte klebt.
    const tabelle = `<div class="table-scroll tn-desktop"><table class="tn-matrix">
      <thead><tr><th>Name</th>${vor.map((v) => `<th title="${esc(v.bezeichnung)}">${esc(v.bezeichnung)}</th>`).join("")}</tr></thead>
      <tbody>${tns.map((tn) => `<tr class="${tn.voraussetzungen_offen ? "offen" : ""}${tn.eingefroren ? " gesperrt" : ""}" data-tid="${tn.id}">
        <td>${tnKopfHtml(tn, nameHtml(tn))}
          <span class="tn-sub">${esc(tn.gliederung || "")}${tn.geburtsdatum ? `${tn.gliederung ? " · " : ""}geb. ${esc(fmtTag(tn.geburtsdatum))}` : ""}</span>
          ${tn.voraussetzungen_offen ? `<span class="badge rot">${tn.voraussetzungen_offen} offen</span>` : (vor.length ? '<span class="badge gruen">alle erfüllt</span>' : "")}${ergebnisMarkeHtml(tn)}</td>
        ${vor.map((v) => {
          const st = tn.voraussetzungen[String(v.id)];
          return `<td><div class="vk">
            <input type="checkbox" data-vk data-tid="${tn.id}" data-vid="${v.id}" ${st && st.erfuellt ? "checked" : ""} ${tn.eingefroren ? "disabled" : ""} aria-label="${esc(v.bezeichnung)} – ${esc(tnName(tn))}">
            <button type="button" class="vk-stempel vk-stand ${st ? (st.erfuellt ? "ja" : "nein") : ""}" data-act="vk-verlauf" data-tid="${tn.id}" data-vid="${v.id}" ${st ? "" : "disabled"} title="Verlauf anzeigen">${st ? stempelHtml(st) : ""}</button>
          </div></td>`;
        }).join("")}
      </tr>`).join("")}</tbody></table></div>`;
    /* Telefon: Karten je Person mit großen Kästen. „Voraussetzungen“ ist eine erkennbare Zeile zum Aufklappen (Pfeil,
       Rahmen, „4 von 6 erfüllt“) und bei offenen Voraussetzungen aufgeklappt – zugeklappt sah der Bereich leer aus
       (Gerätetest B2). Wer sie selbst auf- oder zuklappt oder darin abhakt, behält den Zustand (state.vorKlapp). */
    const vorAuf = (tn) => (state.vorKlapp[tn.id] != null ? state.vorKlapp[tn.id] : tn.voraussetzungen_offen > 0);
    const karten = `<div class="tn-mobil">${tns.map((tn) => `<div class="tn-karte ${tn.voraussetzungen_offen ? "offen" : ""}${tn.eingefroren ? " gesperrt" : ""}">
      <div class="tn-kopf">${tnKopfHtml(tn, leitung ? `<button type="button" class="linkbtn" data-act="tn-edit" data-tid="${tn.id}">${esc(tnName(tn))}</button>` : null)}
        ${tn.voraussetzungen_offen ? `<span class="badge rot">${tn.voraussetzungen_offen} offen</span>` : (vor.length ? '<span class="badge gruen">alle erfüllt</span>' : "")}${ergebnisMarkeHtml(tn)}</div>
      ${tn.gliederung || tn.geburtsdatum ? `<div class="small muted">${esc(tn.gliederung || "")}${tn.geburtsdatum ? `${tn.gliederung ? " · " : ""}geb. ${esc(fmtTag(tn.geburtsdatum))}` : ""}</div>` : ""}
      ${vor.length ? `<details class="vor-klapp" data-tid="${tn.id}"${vorAuf(tn) ? " open" : ""}>
        <summary><span class="vor-klapp-titel">Voraussetzungen</span>
          <span class="vor-klapp-zahl${tn.voraussetzungen_offen ? " offen" : ""}">${vor.length - (tn.voraussetzungen_offen || 0)} von ${vor.length} erfüllt</span></summary>
        ${vor.map((v) => {
          const st = tn.voraussetzungen[String(v.id)];
          const id = `vk-${tn.id}-${v.id}`;
          // „Verlauf“ erst, wenn es einen gibt – ausgegraut ohne Grund wirkte der Knopf kaputt (Gerätetest FT6).
          return `<div class="vk-zeile">
            <input type="checkbox" id="${id}" data-vk data-tid="${tn.id}" data-vid="${v.id}" ${st && st.erfuellt ? "checked" : ""} ${tn.eingefroren ? "disabled" : ""}>
            <label class="vk-text" for="${id}">${esc(v.bezeichnung)}<small class="vk-stand${st ? (st.erfuellt ? " ja" : " nein") : ""}">${st ? stempelHtml(st) : ""}</small></label>
            ${st ? `<button type="button" class="btn secondary small vk-verlauf" data-act="vk-verlauf" data-tid="${tn.id}" data-vid="${v.id}" aria-label="Verlauf anzeigen">Verlauf</button>` : ""}
          </div>`;
        }).join("")}
      </details>` : ""}
    </div>`).join("")}</div>`;
    return kopf + hinweis + tabelle + karten;
  }

  /* Häkchen setzen oder nehmen: Der Server antwortet mit wer/wann – das kommt sofort unter den
     Kasten, ohne den ganzen Lehrgang neu zu laden. Geht es schief, springt der Kasten zurück.
     Gerätetest W1/W2: Solange die Antwort fehlt (Funkloch – die Anfrage hängt, ohne zu scheitern), steht unter dem Kasten
     „Wird gespeichert …“, nach zehn Sekunden „Noch nicht gespeichert – keine Antwort“; vorher sah das Häkchen gespeichert
     aus. Scheitert die Anfrage, springt der Kasten zurück und die Meldung sagt „Nicht gespeichert – keine Verbindung.“.
     Gespeichert meldet es ein Toast (role="status", wie bei Bewertungen), und der Fokus bleibt auf dem Kasten. */
  async function voraussetzungSetzen(cb) {
    const tid = +cb.dataset.tid, vid = +cb.dataset.vid, erfuellt = cb.checked;
    const inKarte = !!cb.closest(".tn-mobil");
    const hatteFokus = document.activeElement === cb;
    if (inKarte) state.vorKlapp[tid] = true;      // die Karte bleibt offen, auch wenn danach nichts mehr offen ist
    const stand = cb.closest(".vk, .vk-zeile").querySelector(".vk-stand");
    const alt = stand ? { html: stand.innerHTML, klasse: stand.className } : null;
    const zeigen = (text) => { if (stand) { stand.textContent = text; stand.classList.remove("ja", "nein"); stand.classList.add("speichert"); } };
    zeigen("Wird gespeichert …");
    const langsam = setTimeout(() => zeigen("Noch nicht gespeichert – keine Antwort vom Server"), 10000);
    cb.disabled = true;
    try {
      const r = await api(`${API}/teilnehmer/${tid}/voraussetzungen/${vid}`, { method: "PUT", body: { erfuellt } });
      const tn = (state.lehrgang.teilnehmer || []).find((t) => t.id === tid);
      const v = (state.lehrgang.voraussetzungen || []).find((x) => x.id === vid);
      if (tn) {
        tn.voraussetzungen[String(vid)] = r.status;
        tn.voraussetzungen_offen = (state.lehrgang.voraussetzungen || []).filter((x) => !(tn.voraussetzungen[String(x.id)] || {}).erfuellt).length;
        state.lehrgang.voraussetzungen_offen = state.lehrgang.teilnehmer.filter((t) => t.voraussetzungen_offen > 0).length;
      }
      renderLehrgangSeite();
      toast(`Gespeichert – ${tn ? `${tnName(tn)}: ` : ""}„${v ? v.bezeichnung : "Voraussetzung"}“ ${erfuellt ? "erfüllt" : "nicht erfüllt"}`);
      const neu = $(`${inKarte ? ".tn-mobil" : ".tn-desktop"} input[data-vk][data-tid="${tid}"][data-vid="${vid}"]`, root);
      if (neu && hatteFokus) neu.focus({ preventScroll: true });
    } catch (e) {
      cb.checked = !erfuellt;
      if (stand && alt) { stand.innerHTML = alt.html; stand.className = alt.klasse; }
      S.fehlschlag(cb, schreibFehler(e));
    } finally { clearTimeout(langsam); }
  }

  async function verlaufDialog(tid, vid) {
    const lg = state.lehrgang;
    const tn = (lg.teilnehmer || []).find((t) => t.id === tid), v = (lg.voraussetzungen || []).find((x) => x.id === vid);
    let d;
    try { d = await api(`${API}/teilnehmer/${tid}/voraussetzungen/${vid}/verlauf`); } catch (e) { return toast(e.message, true); }
    dialogOeffnen(`<h2>Verlauf</h2>
      <p class="help">${esc(tn ? tnName(tn) : "")} · ${esc(v ? v.bezeichnung : "")}</p>
      ${d.verlauf.length ? `<ul class="verlauf-liste">${d.verlauf.map((e) => `<li><span class="${e.erfuellt ? "ja" : "nein"}">${e.erfuellt ? "✓ erfüllt" : "✗ nicht erfüllt"}</span>
        · ${esc(e.user_name)} · ${esc(fmtDate(e.zeit, true))} <span class="quelle">${e.quelle === "import" ? "(importiert)" : "(manuell)"}</span></li>`).join("")}</ul>`
        : '<p class="leerzustand">Noch keine Einträge.</p>'}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`);
  }

  /* Ein Foto vom Telefon hat schnell zehn Megabyte – für einen Kreis von 256 Pixeln. Der Browser
     rechnet es vorher herunter (wie beim Profilbild der Nutzer); geht das nicht (HEIC, den dieser
     Browser nicht kennt), wandert die Datei unverändert los und der Server verkleinert. */
  async function bildKleinRechnen(f) {
    if (!window.createImageBitmap || !window.HTMLCanvasElement) return f;
    try {
      const bild = await createImageBitmap(f, { imageOrientation: "from-image" });
      const faktor = 1024 / Math.max(bild.width, bild.height);
      if (faktor >= 1) { bild.close(); return f; }
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(bild.width * faktor));
      c.height = Math.max(1, Math.round(bild.height * faktor));
      c.getContext("2d").drawImage(bild, 0, 0, c.width, c.height);
      bild.close();
      const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
      return blob && blob.size < f.size ? new File([blob], "profilbild.jpg", { type: "image/jpeg" }) : f;
    } catch (e) { return f; }
  }

  /* Der Server antwortet auf Bild, Kommentar und Ergebnis mit dem ganzen TN – der ersetzt den
     alten Stand im geladenen Lehrgang, ohne dass alles neu geholt werden muss. */
  function tnUebernehmen(tnNeu) {
    const liste = (state.lehrgang && state.lehrgang.teilnehmer) || [];
    const i = liste.findIndex((t) => t.id === tnNeu.id);
    if (i >= 0) liste[i] = Object.assign(liste[i], tnNeu);
    if (state.lehrgang) {
      state.lehrgang.ergebnis_bestanden = liste.filter((t) => t.ergebnis === "bestanden").length;
      state.lehrgang.ergebnis_nicht_bestanden = liste.filter((t) => t.ergebnis === "nicht_bestanden").length;
    }
    return i >= 0 ? liste[i] : tnNeu;
  }

  function teilnehmerDialog(tn) {
    tn = tn || {};
    const neu = !tn.id;
    const extra = Object.entries(tn.extra || {});
    dialogOeffnen(`<h2>${neu ? "Teilnehmende anlegen" : esc(tnName(tn))}</h2>
      <div class="tn-bild-zeile">
        ${tnBildHtml(tn, "gross")}
        <div class="pb-text">
          <p class="help">${neu ? "Ein Profilbild lässt sich hinzufügen, sobald die Person angelegt ist." : "Quadratisch zugeschnitten, 256 Pixel. Es erscheint vor dem Namen in Listen und Matrix."}</p>
          <div class="btn-row"><button type="button" class="btn secondary small" id="tn-pb-waehlen" ${neu ? "disabled" : ""}>Bild wählen</button>
            <button type="button" class="btn secondary small${bildAdresse(tn) ? "" : " hidden"}" id="tn-pb-weg">Entfernen</button></div>
          <input type="file" id="tn-pb-datei" class="hidden" accept="image/*,.heic,.heif">
        </div>
      </div>
      <div class="field-row">
        <div><label for="tn-vorname">Vorname</label><input type="text" id="tn-vorname" value="${esc(tn.vorname)}" autocomplete="off"></div>
        <div><label for="tn-name">Nachname</label><input type="text" id="tn-name" value="${esc(tn.name)}" autocomplete="off" required></div>
        <div><label for="tn-geb">Geburtsdatum</label><input type="date" id="tn-geb" value="${esc(tn.geburtsdatum || "")}"></div>
        <div><label for="tn-gl">Gliederung</label><input type="text" id="tn-gl" value="${esc(tn.gliederung)}"></div>
      </div>
      <label for="tn-email">E-Mail</label><input type="email" id="tn-email" value="${esc(tn.email)}" autocomplete="off">
      <div class="feld-kopf"><label for="tn-bem">Bemerkung</label>${diktatKnopf("tn-bem")}</div><textarea id="tn-bem" style="min-height:60px">${esc(tn.bemerkung)}</textarea>
      ${extra.length ? `<label>Weitere Angaben aus dem Import</label><dl class="kv">${extra.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
      <div class="dlg-actions">${neu ? "" : '<button class="btn secondary dlg-neben" id="tn-del" type="button">Löschen</button>'}
        <button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="tn-save" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        if (neu) fokus($("#tn-vorname", body));
        // Profilbild: sofort hochladen bzw. entfernen – unabhängig vom „Speichern“ der Felder.
        const pbWaehlen = $("#tn-pb-waehlen", body), pbWeg = $("#tn-pb-weg", body), pbDatei = $("#tn-pb-datei", body);
        let pbLaeuft = false;
        const pbSperren = (an) => { pbLaeuft = an; pbWaehlen.disabled = an || neu; pbWeg.disabled = an; };
        const pbZeigen = (tnNeu) => {
          const kreis = $(".tn-bild", body);
          if (kreis) kreis.outerHTML = tnBildHtml(tnNeu, "gross");
          pbWeg.classList.toggle("hidden", !bildAdresse(tnNeu));
        };
        pbWaehlen.onclick = () => { if (!neu) pbDatei.click(); };
        pbDatei.onchange = async () => {
          const f = pbDatei.files && pbDatei.files[0];
          pbDatei.value = "";
          if (!f || pbLaeuft || neu) return;
          pbSperren(true);
          toast("Bild wird hochgeladen …");
          try {
            const fd = new FormData();
            fd.append("file", await bildKleinRechnen(f), f.name || "bild.jpg");
            const r = await api(`${API}/teilnehmer/${tn.id}/bild`, { method: "POST", body: fd });
            tn = tnUebernehmen(r.teilnehmer);
            pbZeigen(tn);
            renderLehrgangSeite();
            toast("Profilbild gespeichert");
          } catch (e) { toast(e.message, true); }
          finally { pbSperren(false); }
        };
        pbWeg.onclick = async () => {
          if (pbLaeuft || neu) return;
          if (!(await S.confirm("Profilbild entfernen? Danach werden wieder die Initialen gezeigt.", "Entfernen"))) return;
          pbSperren(true);
          try {
            const r = await api(`${API}/teilnehmer/${tn.id}/bild`, { method: "DELETE" });
            tn = tnUebernehmen(r.teilnehmer);
            pbZeigen(tn);
            renderLehrgangSeite();
            toast("Profilbild entfernt");
          } catch (e) { toast(e.message, true); }
          finally { pbSperren(false); }
        };
        $("#tn-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const d = {
            name: $("#tn-name", body).value.trim(), vorname: $("#tn-vorname", body).value.trim(),
            geburtsdatum: $("#tn-geb", body).value || null, gliederung: $("#tn-gl", body).value.trim(),
            email: $("#tn-email", body).value.trim(), bemerkung: $("#tn-bem", body).value,
          };
          if (!d.name) return S.feldFehler($("#tn-name", body), "Bitte den Nachnamen angeben.");
          knopf.disabled = true;
          try {
            if (neu) await api(`${API}/lehrgaenge/${LEHRGANG_ID}/teilnehmer`, { method: "POST", body: d });
            else await api(`${API}/teilnehmer/${tn.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Teilnehmende angelegt" : "Gespeichert");
            await loadDetail(); renderLehrgangSeite();
          } catch (e) { S.fehlschlag(knopf, e, body); }
          finally { knopf.disabled = false; }
        };
        const del = $("#tn-del", body);
        if (del) del.onclick = async () => {
          if (!(await S.confirm(`${tnName(tn)} aus dem Lehrgang löschen? Alle Bewertungen und Medien dieser Person werden mit gelöscht.`))) return;
          try {
            await api(`${API}/teilnehmer/${tn.id}`, { method: "DELETE" });
            dlg.close();
            toast("Teilnehmende gelöscht");
            await loadDetail(); renderLehrgangSeite();
          } catch (e) { S.fehlschlag(del, e); }
        };
      });
  }

  /* Voraussetzungen verwalten: umbenennen (Feld verlassen speichert), Reihenfolge per Pfeil,
     löschen, neue anhängen. Dialog und die Seite dahinter werden nach jeder Änderung neu
     gezeichnet – beim Schließen bleibt nichts mehr zu tun. */
  function voraussetzungenDialog() {
    const zeichne = () => {
      const vor = state.lehrgang.voraussetzungen || [];
      dialogOeffnen(`<h2>Voraussetzungen</h2>
        <p class="help">Alle Teilnehmenden bekommen für jede Voraussetzung einen Kasten zum Abhaken. Umbenennen: Text ändern und das Feld verlassen.</p>
        <div class="vor-wrap">${vor.length ? `<ul class="vor-liste">${vor.map((v, i) => `<li data-vid="${v.id}">
          <input type="text" value="${esc(v.bezeichnung)}" data-bez aria-label="Bezeichnung">
          ${sortierKnoepfe(i, vor.length, "data-hoch", "data-runter")}
          ${S.entfernenKnopf("data-del", `Voraussetzung „${v.bezeichnung}“ löschen`)}</li>`).join("")}</ul>`
          : '<p class="leerzustand">Noch keine Voraussetzungen.</p>'}</div>
        <div class="vor-neu"><input type="text" id="vor-neu-text" placeholder="Neue Voraussetzung, z. B. DRSA Silber (nicht älter als 2 Jahre)" aria-label="Neue Voraussetzung">
          <button type="button" class="btn" id="vor-neu-go">Hinzufügen</button></div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`,
        (dlg, body) => {
          const neu = async () => {
            const feld = $("#vor-neu-text", body);
            const bez = feld.value.trim();
            if (!bez) return feld.focus();
            try {
              const r = await api(`${API}/lehrgaenge/${LEHRGANG_ID}/voraussetzungen`, { method: "POST", body: { bezeichnung: bez } });
              state.lehrgang.voraussetzungen.push(r.voraussetzung);
              await nachziehen();
              $("#vor-neu-text").focus();
              toast("Voraussetzung angelegt");
            } catch (e) { toast(schreibFehler(e).message, true); }
          };
          $("#vor-neu-go", body).onclick = neu;
          $("#vor-neu-text", body).addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); neu(); } });
          $$("[data-bez]", body).forEach((inp) => {
            const li = inp.closest("li"), vid = +li.dataset.vid;
            const alt = inp.value;
            inp.addEventListener("blur", async () => {
              const bez = inp.value.trim();
              if (!bez) { inp.value = alt; return; }
              if (bez === alt) return;
              try {
                const r = await api(`${API}/voraussetzungen/${vid}`, { method: "PUT", body: { bezeichnung: bez } });
                const v = state.lehrgang.voraussetzungen.find((x) => x.id === vid);
                if (v) v.bezeichnung = r.voraussetzung.bezeichnung;
                renderLehrgangSeite();
                toast("Umbenannt");
              } catch (e) { inp.value = alt; toast(schreibFehler(e).message, true); }
            });
            inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
          });
          // Am je Zeichnung neuen Rahmen, nicht am dauerhaften Dialogkörper: Dort häuften sich die
          // Handler bei jedem Neuzeichnen, und ein Klick löschte oder verschob mehrfach.
          $(".vor-wrap", body).addEventListener("click", async (e) => {
            const b = e.target.closest("button[data-hoch],button[data-runter],button[data-del]");
            if (!b) return;
            const li = b.closest("li"), vid = +li.dataset.vid;
            const vor = state.lehrgang.voraussetzungen;
            const i = vor.findIndex((x) => x.id === vid);
            try {
              if (b.hasAttribute("data-del")) {
                const v = vor[i];
                if (!(await S.confirm(`Voraussetzung „${v.bezeichnung}“ löschen? Die Häkchen aller Teilnehmenden dazu gehen verloren.`))) return;
                await api(`${API}/voraussetzungen/${vid}`, { method: "DELETE" });
                vor.splice(i, 1);
              } else {
                const j = b.hasAttribute("data-hoch") ? i - 1 : i + 1;
                if (j < 0 || j >= vor.length) return;
                [vor[i], vor[j]] = [vor[j], vor[i]];
                await api(`${API}/lehrgaenge/${LEHRGANG_ID}/voraussetzungen/reihenfolge`, { method: "PUT", body: { ids: vor.map((x) => x.id) } });
              }
              await nachziehen();
              toast(b.hasAttribute("data-del") ? "Voraussetzung gelöscht" : "Reihenfolge gespeichert");
            } catch (err) { toast(schreibFehler(err).message, true); }
          });
        });
    };
    /* Nach Anlegen, Löschen oder Umsortieren den Lehrgang neu holen und die Seite hinter dem
       Dialog nachziehen (Spalten, Zähler „offen“ je TN) – sofort, nicht erst beim Schließen. */
    const nachziehen = async () => {
      try { await loadDetail(); renderLehrgangSeite(); } catch (e) { toast(e.message, true); }
      zeichne();
    };
    zeichne();
  }

  /* --- Reiter Leistungen ----------------------------------------------------------------- */
  /* Eine Prüfungsleistung als Karte – dieselbe Darstellung für die Leistungen eines Lehrgangs
     und die eines Katalogs (Vorlage). Nur die data-act-Namen unterscheiden sich (praefix "pl"
     bzw. "kl"), damit ein Klick nie im falschen Bereich landet. */
  function leistungKarteHtml(l, i, gesamt, editierbar, praefix) {
    return `<div class="leistung-karte" data-lid="${l.id}">
      <div class="titel">${esc(l.bezeichnung)} ${l.zeitansatz_sekunden != null ? `<span class="badge grey" title="Zeitansatz (Sollzeit)">Soll ${fmtZeit(l.zeitansatz_sekunden)}</span>` : ""}
        ${l.kriterien && l.kriterien.length ? `<span class="badge grey" title="Kriterienliste">${plural(l.kriterien.length, "Kriterium", "Kriterien")}</span>` : ""}</div>
      ${editierbar ? `<div class="btn-row">
        <button class="btn secondary small" data-act="${praefix}-edit" data-lid="${l.id}">Bearbeiten</button>
        ${gesamt > 1 ? sortierKnoepfe(i, gesamt, `data-act="${praefix}-hoch" data-lid="${l.id}"`, `data-act="${praefix}-runter" data-lid="${l.id}"`) : ""}
        ${zeilenMenue([["Löschen", `data-act="${praefix}-del" data-lid="${l.id}"`]])}</div>` : '<div class="btn-row"></div>'}
      ${l.beschreibung_md ? `<div class="md-vorschau">${md(l.beschreibung_md)}</div>` : '<div class="md-vorschau muted">Keine Beschreibung.</div>'}
    </div>`;
  }

  function leistungenHtml(lg) {
    const ls = lg.leistungen || [];
    const leitung = darfLeiten();
    const kopf = `<div class="abschnittskopf"><h2>Prüfungsleistungen</h2>
      ${leitung ? '<div class="btn-row"><button class="btn small" data-act="pl-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Prüfungsleistung<span class="k-anlegen"> anlegen</span></span></button></div>' : ""}</div>`;
    if (!ls.length) return kopf + '<div class="leerzustand"><strong>Noch keine Prüfungsleistungen</strong>Alle Teilnehmenden bekommen für jede Leistung ein Bewertungsfeld in der Matrix.</div>';
    return kopf + ls.map((l, i) => leistungKarteHtml(l, i, ls.length, leitung, "pl")).join("");
  }

  async function leistungVerschieben(lid, richtung) {
    const ls = state.lehrgang.leistungen;
    const i = ls.findIndex((x) => x.id === lid), j = i + richtung;
    if (i < 0 || j < 0 || j >= ls.length) return;
    [ls[i], ls[j]] = [ls[j], ls[i]];
    try {
      await api(`${API}/lehrgaenge/${LEHRGANG_ID}/leistungen/reihenfolge`, { method: "PUT", body: { ids: ls.map((x) => x.id) } });
      renderReiter();
      toast("Reihenfolge gespeichert");
    } catch (e) { [ls[i], ls[j]] = [ls[j], ls[i]]; toast(schreibFehler(e).message, true); }
  }

  /* Adresse (und Text) für einen Link – als eigenes <dialog>-Element wie S.confirm, nicht über
     dialogOeffnen: Das würde den #dlg-body überschreiben und den Leistungsdialog dahinter leeren,
     der gerade noch offen steht. */
  function linkEinfuegenDialog(vorschlagText, aufOk) {
    const dlg = document.createElement("dialog");
    dlg.innerHTML = `<div class="dlg-body"><h2>Link einfügen</h2>
      <label for="lk-text">Text</label>
      <input type="text" id="lk-text" value="${esc(vorschlagText || "")}">
      <label for="lk-url">Adresse</label>
      <input type="text" id="lk-url" placeholder="https://…" autocomplete="off">
      <div class="dlg-actions"><button class="btn secondary" id="lk-abbr" type="button">Abbrechen</button>
      <button class="btn" id="lk-ok" type="button">Einfügen</button></div></div>`;
    document.body.appendChild(dlg);
    dlg.querySelector("#lk-abbr").onclick = () => dlg.close();
    dlg.querySelector("#lk-ok").onclick = () => {
      const urlFeld = dlg.querySelector("#lk-url");
      const url = urlFeld.value.trim();
      if (!url) return S.feldFehler(urlFeld, "Bitte eine Adresse angeben.");
      const text = dlg.querySelector("#lk-text").value.trim() || url;
      dlg.close();
      aufOk({ url, text });
    };
    dlg.addEventListener("close", () => dlg.remove(), { once: true });
    dlg.showModal();
    S.dialogVerlauf(dlg);
    fokus(dlg.querySelector(vorschlagText ? "#lk-url" : "#lk-text"));
  }

  /* Schwebende Formatleiste statt fester Toolbar – dieselbe Idee wie im Wiki-Editor (siehe
     wiki.js, setupInlineTools/onSelection), hier auf die paar Werkzeuge zurechtgestutzt, die die
     Beschreibung einer Prüfungsleistung braucht: Überschrift/Text, Liste, fett, kursiv, Link.
     Beide teilen sich denselben Toast-UI-Editor und damit dessen öffentliche exec/Selection-API;
     das Wiki-Menü selbst (Callouts, Spalten, Bausteine, Tabellen …) bleibt dort, wo es hingehört.
     Liefert { bubble, onSelection } zum Abbauen beim Schließen des Dialogs. */
  function mdBubbleEinrichten(ed, root, dlg) {
    const bubble = document.createElement("div");
    bubble.className = "ed-bubble hidden";
    // <dialog> mit showModal() liegt im Top-Layer des Browsers – ein an document.body gehängtes
    // Element bliebe trotz z-index dahinter unsichtbar. Als Kind des Dialogs selbst kommt die
    // Leiste in dieselbe Ebene; "fixed" statt "absolute" macht ihre Position dabei unabhängig
    // davon, wo im Baum sie hängt (das Original im Wiki hängt an document.body, dort passend
    // mit "absolute" plus Bildlaufversatz – hier reicht die reine Fensterposition).
    bubble.style.position = "fixed";
    bubble.setAttribute("role", "toolbar");
    bubble.setAttribute("aria-label", "Textformat");
    bubble.innerHTML = `
      <select class="ed-style" title="Absatz umwandeln" aria-label="Absatz umwandeln">
        <option value="">Umwandeln in …</option>
        <option value="p">Text</option>
        <option value="h1">Überschrift 1</option>
        <option value="h2">Überschrift 2</option>
        <option value="h3">Überschrift 3</option>
        <option value="ul">Aufzählung</option>
        <option value="ol">Nummerierte Liste</option>
      </select>
      <span class="sep"></span>
      <button type="button" data-cmd="bold" title="Fett" aria-label="Fett"><b>B</b></button>
      <button type="button" data-cmd="italic" title="Kursiv" aria-label="Kursiv"><i>I</i></button>
      <span class="sep"></span>
      <button type="button" data-act="link" title="Link einfügen" aria-label="Link einfügen">
        <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.5 9.5l3-3M7.5 4.5l1-1a2.8 2.8 0 014 4l-1 1M8.5 11.5l-1 1a2.8 2.8 0 01-4-4l1-1"/></svg>
      </button>`;
    dlg.appendChild(bubble);
    // Der eigentliche ProseMirror-Inhalt liegt tiefer im Toast-UI-Aufbau – nur Auswahlen darin
    // (nicht irgendwo sonst auf der Seite) sollen die Leiste zeigen.
    const pm = () => root.querySelector(".toastui-editor-ww-container .ProseMirror");
    const hide = () => bubble.classList.add("hidden");
    // Kein Fokuswechsel beim Klick auf die Leiste selbst – sonst bräche die Auswahl ab, bevor
    // der Befehl sie liest. Nur das <select> braucht seinen eigenen Fokus, um sich zu öffnen.
    bubble.addEventListener("mousedown", (e) => { if (e.target.tagName !== "SELECT") e.preventDefault(); });
    bubble.querySelectorAll("[data-cmd]").forEach((b) => { b.onclick = () => ed.exec(b.dataset.cmd); });
    bubble.querySelector(".ed-style").onchange = (e) => {
      const v = e.target.value;
      e.target.value = "";
      if (!v) return;
      hide();
      if (/^h[1-3]$/.test(v)) ed.exec("heading", { level: +v[1] });
      else if (v === "p") ed.exec("heading", { level: 0 });
      else if (v === "ul") ed.exec("bulletList");
      else if (v === "ol") ed.exec("orderedList");
    };
    bubble.querySelector("[data-act=link]").onclick = () => {
      const text = ed.getSelectedText();
      let bereich = null;
      try { bereich = ed.getSelection(); } catch (e) { /* im Rückfall ohne Editor egal */ }
      hide();
      // Der Link-Dialog nimmt den Fokus – die Auswahl merken und vor dem Einfügen wiederherstellen.
      linkEinfuegenDialog(text, ({ url, text: label }) => {
        if (bereich) { try { ed.setSelection(bereich[0], bereich[1]); } catch (e) { /* egal */ } }
        ed.exec("addLink", { linkUrl: url, linkText: label });
      });
    };
    // Zeigt an, welche Auszeichnung an der Auswahl schon anliegt (wie im Wiki-Editor).
    function markActive() {
      const sel = document.getSelection();
      const node = sel && sel.anchorNode;
      const knoten = node && (node.nodeType === 1 ? node : node.parentElement);
      const map = { bold: "strong, b", italic: "em, i" };
      bubble.querySelectorAll("[data-cmd]").forEach((b) => {
        b.classList.toggle("on", !!(knoten && knoten.closest(map[b.dataset.cmd])));
      });
      bubble.querySelector(".ed-style").value = "";
    }
    const onSelection = () => {
      const el = pm();
      const sel = document.getSelection();
      if (!el || !sel || sel.isCollapsed || !sel.rangeCount || !el.contains(sel.anchorNode)) return hide();
      const r = sel.getRangeAt(0).getBoundingClientRect();
      if (!r.width && !r.height) return hide();
      bubble.classList.remove("hidden");
      markActive();
      const w = bubble.offsetWidth;
      bubble.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
      bubble.style.top = `${Math.max(8, r.top - bubble.offsetHeight - 8)}px`;
    };
    document.addEventListener("selectionchange", onSelection);
    return { bubble, onSelection };
  }

  /* Dialog mit Toast UI für die Beschreibung. Bleibt der Editor aus (Datei nicht geladen),
     gibt es ein einfaches Markdown-Feld – die Leistung lässt sich trotzdem anlegen. */
  /* Toast-UI-Editor in ein Element einhängen (Markdown-Textarea als Rückfall, falls die
     Bibliothek fehlt) und beim Schließen des Dialogs wieder abbauen. Gemeinsam für Leistungen im
     Lehrgang und im Katalog – dieselbe Beschreibung, derselbe Editor. Liefert eine Funktion, die
     den aktuellen Markdown-Text ausliest.
     Keine feste Toolbar (toolbarItems: []) – stattdessen wie im Wiki eine schwebende Leiste bei
     Textauswahl (mdBubbleEinrichten), damit die Beschreibung mehr Platz zum Schreiben behält und
     sich einheitlich zum übrigen Editor der Anwendung verhält. */
  function mdEditorEinrichten(dlg, body, elSelektor, wert, fallbackId) {
    const el = $(elSelektor, body);
    let ed = null, fallback = null, bubble = null, onSelection = null;
    if (window.toastui && toastui.Editor) {
      el.classList.add("md-editor");
      const opts = {
        el, initialEditType: "wysiwyg", hideModeSwitch: true, height: "260px",
        initialValue: wert || "", language: "de-DE", usageStatistics: false,
        placeholder: "Wie läuft die Prüfung ab, was wird bewertet?",
        toolbarItems: [],
        // Toast UI nimmt sich sonst beim Anlegen den Fokus: Er gehört aber aufs erste Feld (am Rechner „Bezeichnung“,
        // am Touchgerät der Titel – common.js), und die Bildschirmtastatur soll nicht von selbst aufgehen.
        autofocus: false,
        // Dieselbe Reinigung wie in der Leseansicht und im Wiki-Editor; Toast UI nutzt sie nur für
        // Vorschau und eigene HTML-Renderer, die Anzeige reinigt gespeicherten Text ohnehin erneut.
        sanitizer: MD.reinigen,
      };
      try { ed = new toastui.Editor(opts); }
      catch (e) { delete opts.language; try { ed = new toastui.Editor(opts); } catch (e2) { ed = null; } }
      if (ed) { const b = mdBubbleEinrichten(ed, el, dlg); bubble = b.bubble; onSelection = b.onSelection; }
      // ProseMirror verschluckt Esc (preventDefault für jede Esc-Taste) – der Dialog blieb offen, solange der Fokus in
      // der Beschreibung stand. Hier also selbst schließen, wie es Esc in jedem anderen Feld tut.
      el.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && e.defaultPrevented && dlg.open && !e.isComposing) dlg.close();
      });
    }
    if (!ed) {
      el.innerHTML = `<textarea class="pl-fallback" id="${fallbackId}" placeholder="Beschreibung (Markdown)">${esc(wert)}</textarea>`;
      fallback = $("#" + fallbackId, el);
    }
    const aufraeumen = () => {
      try { if (ed) ed.destroy(); } catch (e) { /* schon weg */ }
      if (onSelection) document.removeEventListener("selectionchange", onSelection);
      if (bubble) bubble.remove();
      ed = null;
    };
    state.dlgAufraeumen = aufraeumen;
    dlg.addEventListener("close", () => { if (state.dlgAufraeumen === aufraeumen) { aufraeumen(); state.dlgAufraeumen = null; } }, { once: true });
    return () => { try { return ed ? ed.getMarkdown() : fallback.value; } catch (e) { return fallback ? fallback.value : ""; } };
  }

  /* Ein rein lokaler Entwurf einer Kriterienliste, bevor die Leistung zum ersten Mal gespeichert
     wird (Lehrgang wie Katalog) – ohne eigene Kennung gibt es dafür noch keine Kriterien-Endpunkte.
     Dieselben Bausteine (#krit-wrap, .vor-liste) wie beim Bearbeiten einer bestehenden Leistung,
     aber rein im Speicher: Hinzufügen/Entfernen/Umsortieren zeichnet nur diesen Ausschnitt neu und
     schickt nichts zum Server. werte() liest zusätzlich die Feldinhalte, bevor neu gezeichnet oder
     gespeichert wird – sonst ginge eine gerade getippte, noch nicht verlassene Zeile verloren.
     Ruft am Ende einmal zeichnen() auf: Die Vorlage im Dialog-HTML enthält dafür nur ein leeres
     <div id="krit-wrap"></div> als Platzhalter. */
  function kriterienEntwurfEinrichten(body) {
    let liste = [];
    const lesen = () => { liste = $$("#krit-wrap [data-krit-entwurf]", body).map((i) => i.value); return liste; };
    const html = () => `<div id="krit-wrap">
      ${liste.length ? `<ul class="vor-liste">${liste.map((bez, i) => `<li>
        <input type="text" value="${esc(bez)}" data-krit-entwurf aria-label="Kriterium">
        ${sortierKnoepfe(i, liste.length, "data-krit-hoch", "data-krit-runter")}
        ${S.entfernenKnopf("data-krit-del", "Kriterium entfernen")}</li>`).join("")}</ul>`
        : '<p class="leerzustand">Noch keine Kriterien.</p>'}
      <div class="vor-neu"><input type="text" id="krit-neu-text" placeholder="Neues Kriterium, z. B. Wurfsack sicher gegriffen" aria-label="Neues Kriterium">
        <button type="button" class="btn secondary small" id="krit-neu-go"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Kriterium<span class="k-anlegen"> anlegen</span></span></button></div>
    </div>`;
    const zeichnen = () => { $("#krit-wrap", body).outerHTML = html(); binden(); };
    function binden() {
      const anlegen = () => {
        const feld = $("#krit-neu-text", body);
        const bez = feld.value.trim();
        if (!bez) return feld.focus();
        lesen(); liste.push(bez); zeichnen();
        $("#krit-neu-text", body).focus();
      };
      $("#krit-neu-go", body).onclick = anlegen;
      $("#krit-neu-text", body).addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); anlegen(); } });
      $("#krit-wrap", body).addEventListener("click", (e) => {
        const b = e.target.closest("button[data-krit-hoch],button[data-krit-runter],button[data-krit-del]");
        if (!b) return;
        const li = b.closest("li"), i = [...li.parentElement.children].indexOf(li);
        lesen();
        if (b.hasAttribute("data-krit-del")) liste.splice(i, 1);
        else {
          const j = b.hasAttribute("data-krit-hoch") ? i - 1 : i + 1;
          if (j < 0 || j >= liste.length) return;
          [liste[i], liste[j]] = [liste[j], liste[i]];
        }
        zeichnen();
      });
    }
    zeichnen();
    return { werte: lesen };
  }

  /* Die Kriterienliste einer BESTEHENDEN Leistung – ein eigener, per outerHTML ersetzbarer Rahmen,
     damit ein Antippen (anlegen/umbenennen/umsortieren/löschen) nur diesen Ausschnitt neu zeichnet
     und nicht den ganzen Dialog: Sonst gingen unfertig getippte Bezeichnung/Beschreibung verloren. */
  function kriterienListeHtml(l, ohneSatz) {
    const ks = l.kriterien || [];
    // Eingefrorene Bewertungen an der Leistung (kriterien_eingefroren vom Server, Entscheidung des Nutzers vom
    // 01.11.2026): die Kriterien nur zum Lesen, ein Satz statt „Kriterium anlegen“ – der Server lehnt mit 409 ab.
    // ohneSatz: Der Dialog war schon beim Öffnen eingefroren, den Grund nennt der Satz über der Knopfzeile.
    if (l.kriterien_eingefroren) {
      return `<div id="krit-wrap">
        ${ks.length ? `<ul class="vor-liste krit-fest">${ks.map((k) => `<li>${esc(k.bezeichnung)}</li>`).join("")}</ul>` : ""}
        ${ohneSatz ? (ks.length ? "" : '<p class="leerzustand">Keine Kriterien.</p>') : `<p class="help krit-gesperrt">${esc(KRITERIEN_EINGEFROREN)}</p>`}
      </div>`;
    }
    return `<div id="krit-wrap">
      ${ks.length ? `<ul class="vor-liste">${ks.map((k, i) => `<li data-kid="${k.id}">
        <input type="text" value="${esc(k.bezeichnung)}" data-krit-bez aria-label="Kriterium">
        ${sortierKnoepfe(i, ks.length, "data-krit-hoch", "data-krit-runter")}
        ${S.entfernenKnopf("data-krit-del", `Kriterium „${k.bezeichnung}“ löschen`)}</li>`).join("")}</ul>`
        : '<p class="leerzustand">Noch keine Kriterien.</p>'}
      <div class="vor-neu"><input type="text" id="krit-neu-text" placeholder="Neues Kriterium, z. B. Wurfsack sicher gegriffen" aria-label="Neues Kriterium">
        <button type="button" class="btn secondary small" id="krit-neu-go"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Kriterium<span class="k-anlegen"> anlegen</span></span></button></div>
    </div>`;
  }

  /* Eingefroren (kriterien_eingefroren schon beim Öffnen): Alles steht nur zum Lesen da, die Beschreibung als Text statt
     im Editor; „Speichern“ ist ausgegraut (aria-disabled, fokussierbar), der Grund steht als Satz über der Knopfzeile –
     vorher scheiterte „Speichern“ erst mit 409 (Kleinigkeiten 02.11.2026, Bitte bestätigen 3 der Modul-Nachträge). */
  function leistungDialog(l) {
    l = l || {};
    const neu = !l.id;
    const fest = !neu && !!l.kriterien_eingefroren;
    const nurLesen = fest ? " readonly" : "";
    dialogOeffnen(`<h2>${neu ? "Prüfungsleistung anlegen" : "Prüfungsleistung bearbeiten"}</h2>
      <label for="pl-bez">Bezeichnung</label>
      <input type="text" id="pl-bez" value="${esc(l.bezeichnung)}" placeholder="z. B. Wurfsackwurf auf Ziel, Aufbau Flaschenzug 3:1" required${nurLesen}>
      <label for="pl-zeit">Zeitansatz${info("Zeitansatz", ZEITANSATZ_INFO + mehrDazu("zeitansatz"))} (mm:ss oder 300 für 3:00) – leer lassen, wenn es keine Sollzeit gibt</label>
      <input type="text" id="pl-zeit" class="zeitfeld" inputmode="numeric" placeholder="mm:ss" autocomplete="off"
             value="${l.zeitansatz_sekunden != null ? fmtZeit(l.zeitansatz_sekunden) : ""}"${nurLesen}>
      <label>Beschreibung – Ablauf</label>
      ${fest ? `<div class="md pl-fest">${l.beschreibung_md ? md(l.beschreibung_md) : '<p class="leerzustand">Keine Beschreibung.</p>'}</div>`
        : '<div id="pl-editor"></div>'}
      <label>Kriterienliste (optional)${info("Kriterienliste", `${KRITERIEN_INFO} Im Bewertungsdialog lässt sich jeder Punkt antippen –
        nicht bewertet, ✅ erfüllt, ❌ nicht erfüllt.${mehrDazu("kriterienliste")}`)}</label>
      ${neu ? '<div id="krit-wrap"></div>' : kriterienListeHtml(l, fest)}
      ${fest ? `<p class="help knopfgrund" id="pl-grund" aria-live="polite">${esc(LEISTUNG_EINGEFROREN)}</p>` : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="pl-save" type="button"${fest ? ' aria-disabled="true" aria-describedby="pl-grund"' : ""}>${neu ? "Anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        const holen = fest ? () => l.beschreibung_md : mdEditorEinrichten(dlg, body, "#pl-editor", l.beschreibung_md, "pl-md");
        fokus($("#pl-bez", body));
        // Neu: die Kriterien sind nur ein lokaler Entwurf, bis die Leistung selbst existiert.
        // Bestehend: jede Änderung persistiert sofort über die eigenen Kriterien-Endpunkte.
        const kritEntwurf = neu ? kriterienEntwurfEinrichten(body) : null;
        if (!neu) {
          const kritBinden = () => {
            if (!$("#krit-neu-go", body)) return;          // eingefroren: nur zum Lesen
            // 409: Inzwischen ist an der Leistung ein Ergebnis vermerkt – der Rahmen zeigt danach den Satz.
            const gesperrt = (e) => { if (e && e.status === 409) kritNachziehen(); };
            const anlegen = async () => {
              const feld = $("#krit-neu-text", body);
              const bez = feld.value.trim();
              if (!bez) return feld.focus();
              try {
                await api(`${API}/leistungen/${l.id}/kriterien`, { method: "POST", body: { bezeichnung: bez } });
                await kritNachziehen();
                $("#krit-neu-text", body).focus();
                toast("Kriterium angelegt");
              } catch (e) { toast(schreibFehler(e).message, true); gesperrt(e); }
            };
            $("#krit-neu-go", body).onclick = anlegen;
            $("#krit-neu-text", body).addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); anlegen(); } });
            $$("[data-krit-bez]", body).forEach((inp) => {
              const li = inp.closest("li"), kid = +li.dataset.kid;
              const alt = inp.value;
              inp.addEventListener("blur", async () => {
                const bez = inp.value.trim();
                if (!bez) { inp.value = alt; return; }
                if (bez === alt) return;
                try { await api(`${API}/kriterien/${kid}`, { method: "PUT", body: { bezeichnung: bez } }); await kritNachziehen(); toast("Umbenannt"); }
                catch (e) { inp.value = alt; toast(e.message, true); gesperrt(e); }
              });
              inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
            });
            // Am je Zeichnung neuen Rahmen gebunden, nicht am dauerhaften Dialogkörper – sonst
            // häuften sich die Handler bei jedem Neuzeichnen (wie bei den Voraussetzungen).
            $("#krit-wrap", body).addEventListener("click", async (e) => {
              const b = e.target.closest("button[data-krit-hoch],button[data-krit-runter],button[data-krit-del]");
              if (!b) return;
              const li = b.closest("li"), kid = +li.dataset.kid;
              const ks = l.kriterien || [];
              const i = ks.findIndex((x) => x.id === kid);
              try {
                if (b.hasAttribute("data-krit-del")) {
                  if (!(await S.confirm(`Kriterium „${ks[i].bezeichnung}“ löschen? Schon erfasste Haken dazu gehen verloren.`))) return;
                  await api(`${API}/kriterien/${kid}`, { method: "DELETE" });
                } else {
                  const j = b.hasAttribute("data-krit-hoch") ? i - 1 : i + 1;
                  if (j < 0 || j >= ks.length) return;
                  [ks[i], ks[j]] = [ks[j], ks[i]];
                  await api(`${API}/leistungen/${l.id}/kriterien/reihenfolge`, { method: "PUT", body: { ids: ks.map((x) => x.id) } });
                }
                await kritNachziehen();
                toast(b.hasAttribute("data-krit-del") ? "Kriterium gelöscht" : "Reihenfolge gespeichert");
              } catch (err) { toast(schreibFehler(err).message, true); gesperrt(err); }
            });
          };
          // Nach jeder Änderung: frischen Stand holen (auch für die Seite hinter dem Dialog – der
          // Kriterien-Zähler auf der Karte soll stimmen), dann nur den Rahmen neu zeichnen.
          const kritNachziehen = async () => {
            try {
              await loadDetail();
              const frisch = (state.lehrgang.leistungen || []).find((x) => x.id === l.id);
              if (frisch) { l.kriterien = frisch.kriterien; l.kriterien_eingefroren = frisch.kriterien_eingefroren; }
            } catch (e) { /* lokaler Stand bleibt, falls das Nachladen scheitert */ }
            $("#krit-wrap", body).outerHTML = kriterienListeHtml(l);
            kritBinden();
            renderLehrgangSeite();
          };
          kritBinden();
        }
        $("#pl-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          // Ausgegraut: Ein Klick hebt nur den Grund hervor und lässt ihn erneut vorlesen (wie in der Materialablage).
          if (knopf.getAttribute("aria-disabled") === "true") {
            const grund = $("#pl-grund", body);
            grund.classList.add("betont");
            grund.textContent = "";
            setTimeout(() => { grund.textContent = LEISTUNG_EINGEFROREN; }, 50);
            return;
          }
          const bez = $("#pl-bez", body).value.trim();
          if (!bez) return S.feldFehler($("#pl-bez", body), "Bitte eine Bezeichnung angeben.");
          const z = zeitLesen($("#pl-zeit", body).value);
          if (!z.ok) return S.feldFehler($("#pl-zeit", body), "Zeitansatz bitte als mm:ss angeben, z. B. 03:00 – oder nur Ziffern: 300.");
          const d = { bezeichnung: bez, beschreibung_md: holen(), zeitansatz_sekunden: z.wert };
          if (neu) d.kriterien = kritEntwurf.werte();
          knopf.disabled = true;
          try {
            if (neu) await api(`${API}/lehrgaenge/${LEHRGANG_ID}/leistungen`, { method: "POST", body: d });
            else await api(`${API}/leistungen/${l.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Prüfungsleistung angelegt" : "Gespeichert");
            await loadDetail(); renderLehrgangSeite();
          } catch (e) { S.fehlschlag(knopf, e, body); }
          finally { knopf.disabled = false; }
        };
      }, ["wide"]);
  }

  async function leistungLoeschen(l) {
    const abgenommen = (state.lehrgang.teilnehmer || []).filter((tn) => tn.leistungen[String(l.id)]).length;
    const text = `Prüfungsleistung „${l.bezeichnung}“ löschen?` + (abgenommen
      ? ` Dazu gibt es schon ${plural(abgenommen, "Bewertung", "Bewertungen")} – sie werden samt Medien gelöscht.` : "");
    if (!(await S.confirm(text))) return;
    try {
      await api(`${API}/leistungen/${l.id}`, { method: "DELETE" });
      toast("Prüfungsleistung gelöscht");
      await loadDetail(); renderLehrgangSeite();
    } catch (e) { toast(e.message, true); }
  }

  /* --- Reiter Bewertung: Matrix, je Leistung, je TN ---------------------------------------- */
  const ANSICHT_KEY = () => `pruef:ansicht:${LEHRGANG_ID}`;
  function bewAnsichtLesen() {
    if (state.bewAnsicht) return state.bewAnsicht;
    let a = null;
    try { a = localStorage.getItem(ANSICHT_KEY()); } catch (e) { /* egal */ }
    // Am Gewässer ist „alle TN für Leistung X“ der häufigste Ablauf – auf dem Telefon die Vorgabe.
    // Eine am Tablet gewählte Matrix passt auf das Telefon nicht (klebende Namensspalte plus eine
    // Zelle sind schon breiter als der Bildschirm) – dort beginnt es wieder mit „je Leistung“.
    if (a === "matrix" && schmal()) a = "leistung";
    state.bewAnsicht = ["matrix", "leistung", "tn"].includes(a) ? a : (schmal() ? "leistung" : "matrix");
    return state.bewAnsicht;
  }
  function bewAnsichtSetzen(a) {
    state.bewAnsicht = a;
    try { localStorage.setItem(ANSICHT_KEY(), a); } catch (e) { /* egal */ }
  }

  /* Eine Zelle der Matrix: Symbol, Kurztext, darunter Prüfer und Zeit. In der Matrix ist sie
     selbst der Knopf; in den Listen „je Leistung“/„je TN“ liegt sie in einer Knopfzeile und
     wird deshalb als <span> gezeichnet – ein Knopf im Knopf ist kein gültiges HTML. */
  function zelleHtml(tn, l, opts = {}) {
    const z = tn.leistungen[String(l.id)];
    const status = z ? z.status : "offen";
    const def = ZELLE[status] || ZELLE.offen;
    const sub = z ? `${esc(kurzName(z.geprueft_von_name))} · ${esc(fmtDate(z.geprueft_am, true))}${z.letzte_zeit_sekunden != null ? ` · ${fmtZeit(z.letzte_zeit_sekunden)}` : ""}` : "";
    // Eingefrorene Zellen (Lehrgangsergebnis vermerkt) sind gedämpft und öffnen den Dialog nur lesend.
    const gesperrt = !!tn.eingefroren;
    const titel = z ? `${def.np ? "Nachprüfung " : ""}${def.txt} – geprüft von ${z.geprueft_von_name} am ${fmtDate(z.geprueft_am, true)}${z.versuche > 1 ? ` (${z.versuche} Versuche)` : ""}`
      : (gesperrt ? "Nicht abgenommen – eingefroren" : "Noch nicht abgenommen – antippen zum Bewerten");
    const alsSpan = opts.tag === "span";
    const klasse = `zelle st-${status}${gesperrt ? " gesperrt" : ""}`;
    const auf = alsSpan ? `<span class="${klasse}" title="${esc(titel)}">`
      : `<button type="button" class="${klasse}" data-act="zelle" data-tid="${tn.id}" data-lid="${l.id}" title="${esc(titel)}">`;
    // Büroklammer, wenn zu der Zelle Bilder oder Videos hinterlegt sind – mit Anzahl ab zwei.
    const anhang = z && z.medien_anzahl
      ? `<span class="anhang" role="img" aria-label="${z.medien_anzahl} ${z.medien_anzahl === 1 ? "Anhang" : "Anhänge"}" title="${z.medien_anzahl} ${z.medien_anzahl === 1 ? "Anhang" : "Anhänge"}">📎${z.medien_anzahl > 1 ? z.medien_anzahl : ""}</span>`
      : "";
    // Hat die Leistung eine Kriterienliste und gibt es schon einen Versuch: X/Y erfüllt als
    // schneller Indikator, ohne dafür die Zelle öffnen zu müssen. In "je TN" steht stattdessen
    // die volle Liste darunter (siehe bewertungHtml) – dort unterbleibt das Kürzel (opts.ohneKrit).
    const krit = z && !opts.ohneKrit && l.kriterien && l.kriterien.length
      ? `<span class="krit-stand" role="img" aria-label="${z.kriterien_erfuellt} von ${l.kriterien.length} Kriterien erfüllt" title="${z.kriterien_erfuellt} von ${l.kriterien.length} Kriterien erfüllt">Kriterien ${z.kriterien_erfuellt}/${l.kriterien.length}</span>`
      : "";
    return `${auf}
      <span class="sym" aria-hidden="true">${def.sym}</span>
      <span class="txt">${def.txt}${def.np ? '<span class="badge np">NP</span>' : ""}${anhang}${krit}</span>
      ${opts.ohneSub ? "" : `<span class="sub">${sub}</span>`}${alsSpan ? "</span>" : "</button>"}`;
  }

  function bewertungHtml(lg) {
    const tns = lg.teilnehmer || [], ls = lg.leistungen || [];
    const a = bewAnsichtLesen();
    const kopf = `<div class="abschnittskopf"><h2>Bewertung${eingefrorenInfo(tns)}</h2></div>`;
    if (!tns.length || !ls.length) {
      return kopf + `<div class="leerzustand"><strong>${!tns.length ? "Noch keine Teilnehmenden" : "Noch keine Prüfungsleistungen"}</strong>
        ${!tns.length ? "Teilnehmende anlegen oder importieren – dann erscheint hier die Matrix." : "Im Reiter „Leistungen“ die Prüfungsleistungen anlegen."}</div>`;
    }
    if (state.bewLeistung == null || !ls.some((l) => l.id === state.bewLeistung)) state.bewLeistung = ls[0].id;
    if (state.bewTn == null || !tns.some((t) => t.id === state.bewTn)) state.bewTn = tns[0].id;
    const umschalter = `<div class="bew-umschalter">
      <div class="c-tabs" role="tablist">
        <button type="button" role="tab" data-act="bew-ansicht" data-a="matrix" class="${a === "matrix" ? "sel" : ""}">Matrix</button>
        <button type="button" role="tab" data-act="bew-ansicht" data-a="leistung" class="${a === "leistung" ? "sel" : ""}">je Leistung</button>
        <button type="button" role="tab" data-act="bew-ansicht" data-a="tn" class="${a === "tn" ? "sel" : ""}">je Teilnehmende</button>
      </div>
      ${a === "leistung" ? `<select id="bew-sel-leistung" aria-label="Prüfungsleistung">${ls.map((l) => `<option value="${l.id}" ${l.id === state.bewLeistung ? "selected" : ""}>${esc(l.bezeichnung)}${l.zeitansatz_sekunden != null ? ` (Soll ${fmtZeit(l.zeitansatz_sekunden)})` : ""}</option>`).join("")}</select>` : ""}
      ${a === "tn" ? `<select id="bew-sel-tn" aria-label="Teilnehmende">${tns.map((t) => `<option value="${t.id}" ${t.id === state.bewTn ? "selected" : ""}>${esc(tnName(t))}${t.gliederung ? ` (${esc(t.gliederung)})` : ""}</option>`).join("")}</select>
        <button type="button" class="btn secondary small" data-act="bew-tn-druck" title="Alle Leistungen dieser Person mit Kommentaren und Bildern drucken oder als PDF speichern">Druckansicht</button>` : ""}
    </div>`;
    let inhalt;
    if (a === "matrix") {
      // Nur die Leistungen: Der freie Kommentar und das Lehrgangsergebnis stehen in der Ansicht
      // „je TN“ – in der Matrix machten die beiden Spalten die Tabelle am Gewässer nur breiter.
      // Das Schloss und die Dämpfung eingefrorener Personen bleiben.
      inhalt = `<div class="table-scroll"><table class="bew-matrix">
        <thead><tr><th class="tn-kopf">Teilnehmende</th>${ls.map((l) => `<th title="${esc(l.bezeichnung)}">${esc(l.bezeichnung)}${l.zeitansatz_sekunden != null ? `<br><span class="muted">Soll ${fmtZeit(l.zeitansatz_sekunden)}</span>` : ""}</th>`).join("")}</tr></thead>
        <tbody>${tns.map((tn) => `<tr class="${tn.eingefroren ? "gesperrt" : ""}">
          <td>${tnKopfHtml(tn, `<button type="button" class="linkbtn" data-act="bew-zu-tn" data-tid="${tn.id}" title="Ansicht „je Teilnehmende“ für ${esc(tnName(tn))} öffnen">${esc(tnName(tn))}</button>`)}<span class="tn-sub">${esc(tn.gliederung || "")}</span>
            ${tn.voraussetzungen_offen ? `<span class="badge rot" title="Voraussetzungen nicht vollständig">${tn.voraussetzungen_offen} Vorauss. offen</span>` : ""}</td>
          ${ls.map((l) => `<td>${zelleHtml(tn, l)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    } else if (a === "leistung") {
      const l = ls.find((x) => x.id === state.bewLeistung);
      inhalt = `${l.beschreibung_md ? `<details class="beschreibung-kopf"><summary>Prüfungsbeschreibung</summary><div class="md">${md(l.beschreibung_md)}</div></details>` : ""}
        <ul class="zellen-liste">${tns.map((tn) => `<li><button type="button" class="zelle-zeile ${tn.voraussetzungen_offen ? "offen-vor" : ""}${tn.eingefroren ? " gesperrt" : ""}" data-act="zelle" data-tid="${tn.id}" data-lid="${l.id}">
          <span class="name">${tnKopfHtml(tn)}${ergebnisMarkeHtml(tn)}<small>${esc(tn.gliederung || "")}${tn.voraussetzungen_offen ? `${tn.gliederung ? " · " : ""}${S.plural(tn.voraussetzungen_offen, "Voraussetzung", "Voraussetzungen")} offen` : ""}</small></span>
          ${zelleHtml(tn, l, { tag: "span" })}
        </button></li>`).join("")}</ul>`;
    } else {
      const tn = tns.find((x) => x.id === state.bewTn);
      // Kopf über der Liste: Bild und Name, der freie Kommentar und (für die Leitung) das Ergebnis.
      const block = `<div class="tn-block${tn.eingefroren ? " gesperrt" : ""}">
        <div class="tn-block-kopf">${tnBildHtml(tn, "gross")}<div class="tn-block-text"><span class="tn-name-zeile">${schlossHtml(tn)}<span class="tn-name">${esc(tnName(tn))}</span></span>${tn.gliederung ? `<span class="muted tn-gliederung">${esc(tn.gliederung)}</span>` : ""}</div></div>
        ${tn.eingefroren ? `<p class="notice small">${esc(EINGEFROREN)}</p>` : ""}
        <div class="tn-block-felder">
          <div><span class="feldname">Kommentar</span>${kommentarZelleHtml(tn, { laenge: 200 })}</div>
          <div><span class="feldname">Lehrgang</span>${ergebnisHtml(tn)}</div>
        </div></div>`;
      inhalt = `${block}${tn.voraussetzungen_offen ? `<p class="notice">${tn.voraussetzungen_offen === 1 ? "1 Voraussetzung ist" : `${tn.voraussetzungen_offen} Voraussetzungen sind`} noch nicht erfüllt.</p>` : ""}
        <ul class="zellen-liste">${ls.map((l) => {
          // Zu jeder Leistung: gebrauchte Zeit (neben der Sollzeit) und der Kommentar des letzten
          // Versuchs – das ist die Ansicht fürs Feedbackgespräch mit der Person.
          const z = tn.leistungen[String(l.id)];
          const status = z ? z.status : "offen";
          const zeit = z && z.letzte_zeit_sekunden != null
            ? `<small class="zeile-zeit">Zeit ${fmtZeit(z.letzte_zeit_sekunden)}${l.zeitansatz_sekunden != null ? ` von ${fmtZeit(l.zeitansatz_sekunden)}${z.letzte_zeit_sekunden > l.zeitansatz_sekunden ? " – über Sollzeit" : ""}` : ""}</small>`
            : (l.zeitansatz_sekunden != null ? `<small>Sollzeit ${fmtZeit(l.zeitansatz_sekunden)}</small>` : "");
          const komm = z && z.letzter_kommentar ? `<small class="zeile-komm">${esc(kuerzen(z.letzter_kommentar, 220))}</small>` : "";
          // Volle Kriterienliste statt nur des X/Y-Kürzels: In dieser Ansicht steht ohnehin nur
          // eine Person mit reichlich Platz je Zeile – wie in der Druckansicht "je TN" schon.
          // Als eigenes <li> nach dem Knopf, nicht darin: ein <ul> gehört nicht in ein <button>.
          const krit = kriterienErgebnisHtml(l.id, z && z.kriterien_stand);
          // Der Titel färbt sich mit dem Ergebnis – grün bestanden, rot mangelhaft, sonst unverändert.
          return `<li><button type="button" class="zelle-zeile${tn.eingefroren ? " gesperrt" : ""}" data-act="zelle" data-tid="${tn.id}" data-lid="${l.id}">
          <span class="name"><span class="leist-titel st-${status}">${esc(l.bezeichnung)}</span>${zeit}${komm}</span>
          ${zelleHtml(tn, l, { tag: "span", ohneKrit: true })}
        </button>${krit}</li>`; }).join("")}</ul>`;
    }
    return kopf + umschalter + inhalt;
  }

  /* Freier Kommentar zu einer Person (alle Prüfenden). Bei eingefrorenen Daten nur lesbar. */
  function kommentarDialog(tid) {
    const tn = tnAusState(tid);
    if (!tn) return;
    const nurLesen = !!tn.eingefroren;
    dialogOeffnen(`<h2>Kommentar</h2>
      <p class="help dlg-tn">${tnKopfHtml(tn)}${tn.gliederung ? `<span class="muted">· ${esc(tn.gliederung)}</span>` : ""}</p>
      ${nurLesen ? `<p class="notice">${esc(EINGEFROREN)}</p>` : ""}
      <div class="feld-kopf"><label for="tn-komm">Freier Kommentar${nurLesen ? "" : " – Eindruck, Stärken, Hinweise für das Abschlussgespräch"}</label>${nurLesen ? "" : diktatKnopf("tn-komm")}</div>
      <textarea id="tn-komm" maxlength="5000" ${nurLesen ? "readonly" : ""} placeholder="${nurLesen ? "Kein Kommentar." : "Zum Beispiel: sehr sicher im Wasser, braucht bei der Seiltechnik noch Routine."}">${esc(tn.kommentar)}</textarea>
      ${nurLesen ? "" : '<div class="help">Sichtbar für alle Prüfenden dieses Lehrgangs. Höchstens 5000 Zeichen.</div>'}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">${nurLesen ? "Schließen" : "Abbrechen"}</button>
        ${nurLesen ? "" : '<button class="btn" id="tn-komm-save" type="button">Speichern</button>'}</div>`,
      (dlg, body) => {
        const feld = $("#tn-komm", body);
        if (nurLesen) return;
        fokus(feld);
        $("#tn-komm-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          knopf.disabled = true;
          try {
            const r = await api(`${API}/teilnehmer/${tid}/kommentar`, { method: "PUT", body: { kommentar: feld.value } });
            tnUebernehmen(r.teilnehmer);
            dlg.close();
            toast("Kommentar gespeichert");
            renderReiter();
          } catch (e) { S.fehlschlag(knopf, schreibFehler(e)); }
          finally { knopf.disabled = false; }
        };
      });
  }

  /* Lehrgangsergebnis bestanden/nicht bestanden (nur Leitung). Ein Klick auf das gesetzte Ergebnis hebt es auf –
     erst dann lassen sich wieder Prüfungen erfassen. */
  async function ergebnisSetzen(tid, erg, knopf) {
    const tn = tnAusState(tid);
    if (!tn) return;
    const aufheben = tn.ergebnis === erg;
    const text = aufheben ? "Ergebnis aufheben? Danach lassen sich wieder Prüfungen erfassen."
      : `${tnName(tn)}: Lehrgang als „${ERGEBNIS[erg][0]}“ vermerken? Bewertungen, Häkchen und Kommentar dieser Person sind danach eingefroren, bis das Ergebnis aufgehoben wird.`;
    // Nichts geht verloren – Aufheben macht es rückgängig: die gewöhnliche Rückfrage, nicht die für Endgültiges (A4).
    if (!(await S.confirm(text, aufheben ? "Aufheben" : "Vermerken", "", { endgueltig: false }))) return;
    if (knopf) knopf.disabled = true;
    try {
      const r = await api(`${API}/teilnehmer/${tid}/ergebnis`, { method: "PUT", body: { ergebnis: aufheben ? null : erg } });
      tnUebernehmen(r.teilnehmer);
      toast(aufheben ? "Ergebnis aufgehoben" : `Vermerkt: ${ERGEBNIS[erg][0]}`);
      // Der Kopf zeigt die Zähler, die Matrix Schloss und Dämpfung – die ganze Seite neu.
      await loadDetail().catch(() => {});
      renderLehrgangSeite();
    } catch (e) { S.fehlschlag(knopf, schreibFehler(e)); }
  }

  function bewertungBinden() {
    const sl = $("#bew-sel-leistung"); if (sl) sl.onchange = () => { state.bewLeistung = +sl.value; renderReiter(); };
    const st = $("#bew-sel-tn"); if (st) st.onchange = () => { state.bewTn = +st.value; renderReiter(); };
  }

  /* ==========================================================================================
     Bewertungsdialog
     ========================================================================================== */
  // Drei Zustände je Kriterium: nicht bewertet → erfüllt → nicht erfüllt → nicht bewertet.
  const KRIT_SYM = { leer: "⬜", ja: "✅", nein: "❌" };
  // Der Zustand steht im Namen des Knopfs – aria-pressed kennt nur zwei, „nicht erfüllt“ klang wie „nicht bewertet“
  // (Gerätetest W4); ein Wechsel wird zusätzlich angesagt (#bw-krit-ansage).
  const KRIT_TEXT = { leer: "nicht bewertet", ja: "erfüllt", nein: "nicht erfüllt" };
  const KRIT_ZYKLUS = { leer: "ja", ja: "nein", nein: "leer" };
  // Die Kriteriendefinitionen einer Leistung (Text, Reihenfolge) stehen an ihr selbst, nicht am
  // Versuch – wie beim Zeitansatz (soll()) zeigt eine spätere Umbenennung sich rückwirkend überall.
  const kriterienDefs = (lid) => {
    const l = (state.lehrgang.leistungen || []).find((x) => x.id === lid);
    return (l && l.kriterien) || [];
  };
  /* Nur die Kriterien, die bei DIESEM Versuch tatsächlich angekreuzt wurden – für Lese-Ansichten
     (Bisherige Versuche, Alle Bewertungen, Mängel, Druck). Nicht bewertete bleiben unerwähnt. */
  function kriterienErgebnisHtml(lid, stand) {
    if (!stand) return "";
    const eintraege = kriterienDefs(lid).filter((k) => stand[String(k.id)] !== undefined);
    if (!eintraege.length) return "";
    return `<ul class="kriterien-ergebnis">${eintraege.map((k) => {
      const ok = stand[String(k.id)];
      return `<li class="${ok ? "ja" : "nein"}">${ok ? "✅" : "❌"} ${esc(k.bezeichnung)}</li>`;
    }).join("")}</ul>`;
  }

  function versuchKarteHtml(v, istLetzter, opts = {}) {
    const bearbeitet = v.bearbeitet_am ? ` · <span title="Ursprünglicher Stand im Verlauf">bearbeitet von ${esc(v.bearbeitet_von_name)} am ${esc(fmtDate(v.bearbeitet_am, true))}</span>` : "";
    return `<div class="versuch-karte ${v.ergebnis}" data-vid="${v.id}">
      <div class="vk-kopf"><span>${versuchTitel(v)}</span>
        <span class="erg ${v.ergebnis}">${v.ergebnis === "bestanden" ? "👍 bestanden" : "👎 mangelhaft"}</span>
        ${v.zeit_sekunden != null ? `<span class="zeit">Zeit ${fmtZeit(v.zeit_sekunden)}${opts.soll != null ? ` <span class="muted">(Soll ${fmtZeit(opts.soll)})</span>` : ""}</span>` : ""}</div>
      ${v.kommentar ? `<div class="kommentar">${esc(v.kommentar)}</div>` : ""}
      ${kriterienErgebnisHtml(v.leistung_id, v.kriterien)}
      ${medienGridHtml(v.medien, { loeschbar: !!opts.onMedienWeg, onDelete: opts.onMedienWeg })}
      <div class="abnahme">abgenommen von ${esc(v.geprueft_von_name)} am ${esc(fmtDate(v.geprueft_am, true))}${bearbeitet}</div>
      ${v.verlauf && v.verlauf.length ? `<details class="staende"><summary>Frühere Stände (${v.verlauf.length})</summary><ul>${v.verlauf.map((s) => `<li>
        ${s.ergebnis === "bestanden" ? "👍 bestanden" : "👎 mangelhaft"}${s.zeit_sekunden != null ? ` · ${fmtZeit(s.zeit_sekunden)}` : ""}${s.kommentar ? ` · „${esc(s.kommentar)}“` : ""}
        <span class="muted">– von ${esc(s.von_name)}, galt ${esc(fmtDate(s.stand_ab, true))} bis ${esc(fmtDate(s.ersetzt_am, true))}</span></li>`).join("")}</ul></details>` : ""}
      ${opts.knoepfe ? `<div class="btn-row">
        <button type="button" class="btn secondary small" data-v-edit="${v.id}">Bearbeiten</button>
        ${istLetzter ? `<button type="button" class="btn secondary small" data-v-medien="${v.id}">Medien hinzufügen</button>
          ${darfLeiten() ? `<button type="button" class="btn secondary small" data-v-del="${v.id}">Versuch löschen</button>` : ""}` : ""}
        <input type="file" class="hidden" data-v-datei="${v.id}" accept="image/*,video/*,.heic,.heif,.mp4,.mov,.m4v,.webm" multiple>
      </div><div class="up-stand hidden"><span class="up-text small muted"></span><progress max="100" value="0"></progress></div>` : ""}
    </div>`;
  }

  function formularHtml(modus, l) {
    const v = modus.versuch || {};
    const titel = modus.art === "edit" ? `${versuchTitel(v)} bearbeiten` : modus.art === "np" ? "Nachprüfung durchführen" : "Neue Bewertung";
    return `<h3 id="bw-form-titel">${titel}</h3>
      ${l.zeitansatz_sekunden != null ? `<div class="stoppuhr">
        <div class="su-zeile"><span class="su-anzeige" aria-live="off">00:00.0</span><span class="su-soll">Soll ${fmtZeit(l.zeitansatz_sekunden)}</span></div>
        <div class="su-knoepfe"><button type="button" class="btn secondary" data-su="start">Start</button>
          <button type="button" class="btn secondary" data-su="stopp" disabled>Stopp</button>
          <button type="button" class="btn secondary" data-su="reset">Zurücksetzen</button></div>
        <div class="su-hinweis"></div></div>` : ""}
      <label for="bw-zeit">Zeit (mm:ss oder 230 für 2:30)</label>
      <div class="zeit-zeile"><input type="text" id="bw-zeit" class="zeitfeld" inputmode="numeric" placeholder="mm:ss" autocomplete="off"
             value="${v.zeit_sekunden != null ? fmtZeit(v.zeit_sekunden) : ""}">
        <span class="help">${l.zeitansatz_sekunden != null ? "„Stopp“ trägt die gemessene Zeit ein – sie lässt sich hier korrigieren." : "Ohne Zeitansatz, aber die Zeit darf trotzdem notiert werden."}</span></div>
      ${l.kriterien && l.kriterien.length ? `<label>Kriterien</label>
      <div class="kriterien-liste" id="bw-kriterien">${l.kriterien.map((k) => {
        const stand = v.kriterien || {};
        const z = stand[String(k.id)] === true ? "ja" : stand[String(k.id)] === false ? "nein" : "leer";
        return `<button type="button" class="krit-zeile ${z}" data-kid="${k.id}" data-stand="${z}" aria-label="${esc(k.bezeichnung)}: ${KRIT_TEXT[z]}">
          <span class="krit-sym" aria-hidden="true">${KRIT_SYM[z]}</span><span class="krit-text">${esc(k.bezeichnung)}</span></button>`;
      }).join("")}</div>
      <span class="nur-vorlesen" id="bw-krit-ansage" aria-live="polite"></span>
      <div class="help">Antippen wechselt zwischen nicht bewertet, ✅ erfüllt und ❌ nicht erfüllt.</div>` : ""}
      <label id="bw-wahl-label">Bewertung</label>
      <div class="bew-wahl" id="bw-wahl" role="group" aria-labelledby="bw-wahl-label" tabindex="-1">
        <button type="button" data-erg="bestanden" class="${v.ergebnis === "bestanden" ? "sel" : ""}" aria-pressed="${v.ergebnis === "bestanden"}"><span class="sym" aria-hidden="true">👍</span> bestanden</button>
        <button type="button" data-erg="mangelhaft" class="${v.ergebnis === "mangelhaft" ? "sel" : ""}" aria-pressed="${v.ergebnis === "mangelhaft"}"><span class="sym" aria-hidden="true">👎</span> mangelhaft</button>
      </div>
      <div class="feld-kopf"><label for="bw-komm" id="bw-komm-label">${v.ergebnis === "mangelhaft" ? "Kommentar (Pflicht bei mangelhaft)" : "Kommentar"}</label>${diktatKnopf("bw-komm")}</div>
      <textarea id="bw-komm" placeholder="Was war gut, was hat gefehlt? Bei mangelhaft: die Fehler für das Feedbackgespräch.">${esc(v.kommentar)}</textarea>
      ${diktatHinweis()}
      <label>Medien</label>
      <button type="button" class="btn secondary medien-knopf" id="bw-medien-knopf">Foto/Video aufnehmen oder wählen</button>
      <input type="file" id="bw-dateien" class="hidden" accept="image/*,video/*,.heic,.heif,.mp4,.mov,.m4v,.webm" multiple>
      <ul class="medien-wahl" id="bw-medien-liste"></ul>
      <div class="help">Bilder (auch HEIC) und Videos bis ${STROEMIS.maxUploadMb >= 1024 ? `${(STROEMIS.maxUploadMb / 1024).toFixed(STROEMIS.maxUploadMb % 1024 ? 1 : 0).replace(".", ",")} GB` : `${STROEMIS.maxUploadMb} MB`} je Hochladevorgang.</div>
      <div class="up-stand hidden" id="bw-up"><span class="up-text small muted"></span><progress max="100" value="0"></progress></div>
      <div class="dlg-actions"><button class="btn secondary" id="bw-abbruch" type="button">Abbrechen</button>
        <button class="btn" id="bw-save" type="button">${modus.art === "edit" ? "Änderung speichern" : "Bewertung speichern"}</button></div>`;
  }

  /* Standbild aus einem Video ziehen (Canvas) – wie posterFor in map.js: Der Server nimmt es als
     Vorschaubild, wenn ffmpeg fehlt oder das Format nicht lesen kann. */
  function posterFor(file) {
    return new Promise((resolve) => {
      const v = document.createElement("video");
      const url = URL.createObjectURL(file);
      let done = false;
      const finish = (blob) => { if (done) return; done = true; URL.revokeObjectURL(url); resolve(blob); };
      v.muted = true; v.playsInline = true; v.preload = "auto";
      v.onloadeddata = () => { try { v.currentTime = Math.min(1, (v.duration || 2) / 2); } catch (e) { finish(null); } };
      v.onseeked = () => {
        try {
          const c = document.createElement("canvas");
          const scale = Math.min(1, 1600 / Math.max(v.videoWidth, 1));
          c.width = Math.round(v.videoWidth * scale); c.height = Math.round(v.videoHeight * scale);
          c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
          c.toBlob((b) => finish(b), "image/jpeg", 0.85);
        } catch (e) { finish(null); }
      };
      v.onerror = () => finish(null);
      setTimeout(() => finish(null), 10000);
      v.src = url;
    });
  }

  /* Medien zu einem Versuch hochladen – XHR statt fetch, weil nur XHR den Fortschritt meldet.
     standEl: die Zeile mit Text und Balken, die dabei sichtbar wird. Liefert {medien, errors}. */
  async function medienHochladen(versuchId, files, standEl) {
    const text = standEl ? standEl.querySelector(".up-text") : null, prog = standEl ? standEl.querySelector("progress") : null;
    if (standEl) standEl.classList.remove("hidden");
    const videos = files.filter(isVideo).length;
    const posters = [];
    let n = 0;
    for (const f of files) {
      if (isVideo(f)) {
        if (text) text.textContent = `Vorschaubild ${++n} von ${videos} wird erzeugt …`;
        posters.push(await posterFor(f));
      } else posters.push(null);
    }
    if (text) text.textContent = `${plural(files.length, "Datei wird", "Dateien werden")} hochgeladen …`;
    const fd = new FormData();
    files.forEach((f, i) => { fd.append("files", f); fd.append("posters", posters[i] || new Blob(), posters[i] ? "poster.jpg" : ""); });
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API}/versuche/${versuchId}/medien`);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && prog) prog.value = Math.round((e.loaded / e.total) * 100); };
      xhr.onload = () => {
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch (e) { /* leer */ }
        if (xhr.status === 401) { location.href = "/login?next=" + encodeURIComponent(location.pathname); return; }
        if (xhr.status >= 400) reject(new Error(d.error || `Hochladen fehlgeschlagen (Fehler ${xhr.status})`));
        else resolve({ medien: d.medien || [], errors: d.errors || [] });
      };
      xhr.onerror = () => reject(new Error("Hochladen fehlgeschlagen – Verbindung unterbrochen."));
      xhr.send(fd);
    });
  }

  /* Stoppuhr im Formular. Gibt eine Aufräumfunktion zurück (Timer weg). */
  function stoppuhrEinrichten(body, l, tn, tid, lid) {
    const box = $(".stoppuhr", body);
    if (!box) return () => {};
    const anzeige = $(".su-anzeige", box), hinweis = $(".su-hinweis", box);
    const bStart = $('[data-su="start"]', box), bStopp = $('[data-su="stopp"]', box), bReset = $('[data-su="reset"]', box);
    const zeitfeld = $("#bw-zeit", body);
    const soll = l.zeitansatz_sekunden;
    let timer = null;
    // Ob der Dialog schon einmal offen gesehen wurde. S.dialog ruft onOpen VOR showModal auf –
    // beim Wiederaufnehmen einer laufenden Stoppuhr (nach Neuladen, über das Banner) kam der
    // erste Tick also, während der Dialog noch zu war, und hielt die Uhr sofort wieder an: Die
    // Anzeige stand auf 00:00, „Stopp“ war gesperrt, und die gemessene Zeit kam nie ins Feld.
    let warOffen = false;
    const zeichne = (ms) => { anzeige.textContent = fmtZeitGenau(ms); box.classList.toggle("ueber", soll != null && ms > soll * 1000); };
    const halt = () => { clearInterval(timer); timer = null; box.classList.remove("laeuft"); bStart.disabled = false; bStopp.disabled = true; };
    const tick = () => {
      // Dialog inzwischen zu (Escape, Backdrop) – der Timer darf nicht ins Leere weiterlaufen.
      // Erst ein Dialog, der offen war und wieder zu ist, zählt als geschlossen.
      if (!document.contains(box)) { halt(); return; }
      if ($("#dlg").open) warOffen = true;
      else if (warOffen) { halt(); return; }
      const su = suLesen();
      if (!su || su.tid !== tid || su.lid !== lid) { halt(); zustand(); return; }   // anderswo zurückgesetzt
      zeichne(Date.now() - su.start);
    };
    const laufen = () => { clearInterval(timer); timer = setInterval(tick, 100); box.classList.add("laeuft"); bStart.disabled = true; bStopp.disabled = false; tick(); };
    const zustand = () => {
      const su = suLesen();
      if (su && su.tid === tid && su.lid === lid) { hinweis.textContent = ""; laufen(); }
      else if (su) { halt(); bStart.disabled = true; hinweis.textContent = `Es läuft schon eine Stoppuhr für ${su.tn_name} – ${su.leistung}. Erst dort stoppen oder zurücksetzen.`; }
      else { halt(); hinweis.textContent = ""; }
      bannerZeichnen();
    };
    bStart.onclick = () => {
      if (suLesen()) return zustand();
      suSchreiben({ tid, lid, lehrgang: LEHRGANG_ID, start: Date.now(), tn_name: tnName(tn), leistung: l.bezeichnung });
      zustand();
    };
    bStopp.onclick = () => {
      const su = suLesen();
      if (!su || su.tid !== tid || su.lid !== lid) return zustand();
      const ms = Date.now() - su.start;
      suLoeschen();
      halt();
      zeichne(ms);
      zeitfeld.value = fmtZeit(Math.round(ms / 1000));
      zeitfeld.classList.remove("fehler");
      bannerZeichnen();
      // Direkt weiter zur Bewertung: die beiden großen Knöpfe in die Mitte holen.
      const wahl = $("#bw-wahl", body);
      if (wahl) { S.rollen(wahl, { block: "center" }); const b = wahl.querySelector("button"); if (b) b.focus({ preventScroll: true }); }
    };
    bReset.onclick = () => {
      const su = suLesen();
      if (su && (su.tid !== tid || su.lid !== lid)) return;   // fremde Stoppuhr: nur dort zurücksetzen
      suLoeschen(); halt(); zeichne(0); zustand();
    };
    zustand();
    if (!timer) zeichne(0);
    // Ein Reiter, der wieder in den Vordergrund kommt, holt die Anzeige sofort nach.
    const sichtbar = () => { if (document.visibilityState === "visible") tick(); };
    document.addEventListener("visibilitychange", sichtbar);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", sichtbar); };
  }

  async function bewertungsDialog(tid, lid, opts = {}) {
    let d;
    try { d = await api(`${API}/teilnehmer/${tid}/leistungen/${lid}/versuche`); }
    catch (e) { return toast(e.message, true); }
    const versuche = d.versuche || [], tn = tnVoll(d.teilnehmer), l = d.leistung;
    const letzter = versuche.length ? versuche[versuche.length - 1] : null;
    // Eingefroren (Lehrgangsergebnis vermerkt): alles ansehen, nichts ändern – kein Formular,
    // keine Medien- und Löschknöpfe. Der Server würde ohnehin mit 409 antworten.
    const gesperrt = !!tn.eingefroren;
    const su = suLesen();
    const suHier = !!(su && su.tid === tid && su.lid === lid) && !opts.uebersicht && !gesperrt;
    // Welches Formular? Kein Versuch → neue Bewertung. Letzter mangelhaft → Nachprüfung auf
    // Knopfdruck (oder sofort, wenn dafür schon eine Stoppuhr läuft). Letzter bestanden → nur Bearbeiten.
    let modus = null;
    if (gesperrt) modus = null;
    else if (opts.edit) modus = { art: "edit", versuch: versuche.find((v) => v.id === opts.edit) || letzter };
    else if (!letzter) modus = { art: "neu" };
    else if (letzter.ergebnis === "mangelhaft" && (opts.nachpruefung || suHier)) modus = { art: "np" };
    // Läuft für eine bestandene Zelle eine Stoppuhr (im Bearbeiten-Formular gestartet), muss sie
    // wieder erreichbar sein – die Übersicht hat keine Uhr.
    else if (suHier) modus = { art: "edit", versuch: letzter };
    const npMoeglich = !gesperrt && !!(letzter && letzter.ergebnis === "mangelhaft" && !modus);

    const neuZeichnen = async (o) => { await loadDetail().catch(() => {}); renderLehrgangSeite(); bewertungsDialog(tid, lid, o || {}); };
    const onMedienWeg = gesperrt ? null : () => neuZeichnen();

    const html = `<div class="dlg-kopf"><h2 class="dlg-tn">${tnKopfHtml(tn)}</h2><p class="leistung">${esc(l.bezeichnung)}${l.zeitansatz_sekunden != null ? ` · Sollzeit ${fmtZeit(l.zeitansatz_sekunden)}` : ""}${tn.gliederung ? ` · ${esc(tn.gliederung)}` : ""}${tn.ergebnis ? ` · Lehrgang ${ERGEBNIS[tn.ergebnis][0]}` : ""}</p></div>
      ${gesperrt ? `<p class="notice">${esc(EINGEFROREN)}</p>` : ""}
      ${l.beschreibung_md ? `<details class="beschreibung"><summary>Prüfungsbeschreibung</summary><div class="md">${md(l.beschreibung_md)}</div></details>` : ""}
      ${versuche.length ? `<h3>Bisherige Versuche</h3>${versuche.map((v) => versuchKarteHtml(v, v === letzter, { soll: l.zeitansatz_sekunden, knoepfe: !gesperrt, onMedienWeg })).join("")}` : ""}
      <div class="abschluss">
      ${modus ? formularHtml(modus, l)
        : gesperrt ? `<p class="help">${versuche.length ? "Die Bewertungen sind eingefroren." : "Diese Leistung wurde nicht abgenommen; neue Bewertungen sind eingefroren."}</p>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`
        : npMoeglich ? `<p class="help">Die letzte Bewertung ist mangelhaft. Eine Nachprüfung ist ein eigener, zusätzlicher Versuch – die Erstprüfung bleibt erhalten.</p>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button><button class="btn" id="bw-np" type="button">Nachprüfung durchführen</button></div>`
        : `<p class="help">Bestanden. Über „Bearbeiten“ lässt sich die Bewertung ändern – der bisherige Stand bleibt im Verlauf.</p>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`}
      </div>`;

    dialogOeffnen(html, (dlg, body) => {
      const urls = [];
      let suWeg = () => {};
      const aufraeumen = () => { suWeg(); urls.forEach((u) => URL.revokeObjectURL(u)); };
      state.dlgAufraeumen = aufraeumen;
      dlg.addEventListener("close", () => { if (state.dlgAufraeumen === aufraeumen) { aufraeumen(); state.dlgAufraeumen = null; } }, { once: true });

      // Knöpfe an den bisherigen Versuchen
      $$("[data-v-edit]", body).forEach((b) => b.onclick = () => bewertungsDialog(tid, lid, { edit: +b.dataset.vEdit }));
      $$("[data-v-del]", body).forEach((b) => b.onclick = async () => {
        const v = versuche.find((x) => x.id === +b.dataset.vDel);
        if (!(await S.confirm(`${versuchTitel(v)} löschen? Kommentar und Medien dieses Versuchs gehen verloren.`))) return;
        try { await api(`${API}/versuche/${v.id}`, { method: "DELETE" }); toast("Versuch gelöscht"); neuZeichnen(); }
        catch (e) { toast(e.message, true); }
      });
      $$("[data-v-medien]", body).forEach((b) => {
        const inp = $(`[data-v-datei="${b.dataset.vMedien}"]`, body);
        b.onclick = () => { inp.value = ""; inp.click(); };
        inp.onchange = async () => {
          const files = Array.from(inp.files || []);
          if (!files.length) return;
          const karte = b.closest(".versuch-karte");
          b.disabled = true;
          try {
            const r = await medienHochladen(+b.dataset.vMedien, files, $(".up-stand", karte));
            if (r.errors.length) toast(r.errors.join(" "), true);
            else toast(`${plural(r.medien.length, "Datei", "Dateien")} hochgeladen`);
            neuZeichnen();
          } catch (e) { S.fehlschlag(b, e); }
        };
      });
      const np = $("#bw-np", body);
      if (np) np.onclick = () => bewertungsDialog(tid, lid, { nachpruefung: true });
      if (!modus) return;

      // --- Formular ---
      suWeg = stoppuhrEinrichten(body, l, tn, tid, lid);
      // Die Felder liegen im Abschluss-Block – dort suchen, nicht im ganzen Dialog, in dem davor
      // gerenderter Text steht.
      const form = $(".abschluss", body) || body;
      const wahl = $("#bw-wahl", form), komm = $("#bw-komm", form), kommLabel = $("#bw-komm-label", form), zeitfeld = $("#bw-zeit", form);
      const gewaehlt = () => { const s = wahl.querySelector(".sel"); return s ? s.dataset.erg : null; };
      const pflichtZeigen = () => { kommLabel.textContent = gewaehlt() === "mangelhaft" ? "Kommentar (Pflicht bei mangelhaft)" : "Kommentar"; if (gewaehlt() !== "mangelhaft") komm.classList.remove("fehler"); };
      $$("button", wahl).forEach((b) => b.onclick = () => {
        $$("button", wahl).forEach((x) => { x.classList.toggle("sel", x === b); x.setAttribute("aria-pressed", String(x === b)); });
        S.feldOk(wahl);
        pflichtZeigen();
      });
      komm.addEventListener("input", () => { if (komm.value.trim()) komm.classList.remove("fehler"); });
      zeitfeld.addEventListener("input", () => zeitfeld.classList.remove("fehler"));
      // Kriterien: ein Tipp wechselt nicht bewertet → erfüllt → nicht erfüllt → nicht bewertet.
      const kritListe = $("#bw-kriterien", form);
      if (kritListe) kritListe.addEventListener("click", (e) => {
        const btn = e.target.closest(".krit-zeile");
        if (!btn) return;
        const naechster = KRIT_ZYKLUS[btn.dataset.stand];
        btn.dataset.stand = naechster;
        btn.className = `krit-zeile ${naechster}`;
        btn.querySelector(".krit-sym").textContent = KRIT_SYM[naechster];
        const name = `${btn.querySelector(".krit-text").textContent}: ${KRIT_TEXT[naechster]}`;
        btn.setAttribute("aria-label", name);
        $("#bw-krit-ansage", form).textContent = name;
      });

      // Medien auswählen: Vorschau, Größe, einzeln entfernbar. Die Dateien liegen im Speicher,
      // bis die Bewertung gespeichert ist – erst dann gibt es einen Versuch, zu dem sie gehören.
      let dateien = [];
      const liste = $("#bw-medien-liste", form), inp = $("#bw-dateien", form);
      const listeZeichnen = () => {
        liste.innerHTML = dateien.map((f, i) => {
          let vorschau = '<span class="video-icon" aria-hidden="true">🎬</span>';
          if (!isVideo(f)) { const u = URL.createObjectURL(f); urls.push(u); vorschau = `<img src="${u}" alt="">`; }
          return `<li>${vorschau}<span class="name">${esc(f.name)}<small>${groesseText(f.size)}${isVideo(f) ? " · Video" : ""}</small></span>
            ${S.entfernenKnopf(`data-weg="${i}"`, `${f.name} entfernen`)}</li>`;
        }).join("");
        $$("[data-weg]", liste).forEach((b) => b.onclick = () => { dateien.splice(+b.dataset.weg, 1); listeZeichnen(); });
      };
      $("#bw-medien-knopf", form).onclick = () => { inp.value = ""; inp.click(); };
      inp.onchange = () => { dateien = dateien.concat(Array.from(inp.files || [])); listeZeichnen(); };

      $("#bw-abbruch", form).onclick = () => { if (modus.art === "neu") dlg.close(); else bewertungsDialog(tid, lid, { uebersicht: true }); };
      $("#bw-save", form).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        const erg = gewaehlt();
        // Fehler an der Stelle (S.feldFehler), nicht als Toast (Gerätetest FT7, designsprache „Fehler am Feld“).
        if (!erg) { wahl.scrollIntoView({ block: "center" }); return S.feldFehler(wahl, "Bitte „bestanden“ oder „mangelhaft“ wählen."); }
        // Läuft die Stoppuhr noch und ist das Zeitfeld leer, gilt die gemessene Zeit – wer
        // direkt speichert, hat das Stoppen nur übersprungen, nicht die Messung verworfen.
        const laufend = suLesen();
        if (laufend && laufend.tid === tid && laufend.lid === lid && !zeitfeld.value.trim()) {
          zeitfeld.value = fmtZeit(Math.round((Date.now() - laufend.start) / 1000));
        }
        const z = zeitLesen(zeitfeld.value);
        if (!z.ok) { zeitfeld.classList.add("fehler"); return S.feldFehler(zeitfeld, "Zeit bitte als mm:ss angeben, z. B. 02:30 – oder nur Ziffern: 230."); }
        const kommentar = komm.value.trim();
        // Pflichtkommentar schon hier – der Server prüft es ebenfalls (siehe catch unten).
        if (erg === "mangelhaft" && !kommentar) { komm.classList.add("fehler"); return S.feldFehler(komm, "Bei „mangelhaft“ ist ein Kommentar Pflicht."); }
        // Kriterien-Stand aus den Knöpfen lesen – ohne Kriterienliste liefert das ein leeres Objekt,
        // was der Server als „nichts zu ändern“ versteht.
        const kriterien = {};
        $$(".krit-zeile", form).forEach((btn) => {
          if (btn.dataset.stand === "ja") kriterien[btn.dataset.kid] = true;
          else if (btn.dataset.stand === "nein") kriterien[btn.dataset.kid] = false;
        });
        knopf.disabled = true;
        try {
          let versuch;
          if (modus.art === "edit") {
            versuch = (await api(`${API}/versuche/${modus.versuch.id}`, { method: "PUT", body: { ergebnis: erg, zeit_sekunden: z.wert, kommentar, kriterien } })).versuch;
          } else {
            versuch = (await api(`${API}/teilnehmer/${tid}/leistungen/${lid}/versuche`,
              { method: "POST", body: { ergebnis: erg, zeit_sekunden: z.wert, kommentar, nachpruefung: modus.art === "np", kriterien } })).versuch;
          }
          if (dateien.length) {
            try {
              const r = await medienHochladen(versuch.id, dateien, $("#bw-up", form));
              if (r.errors.length) toast(r.errors.join(" "), true);
            } catch (e) { toast(e.message, true); }
          }
          // Eine für diese Zelle noch laufende Stoppuhr ist mit dem Speichern erledigt.
          const s = suLesen();
          if (s && s.tid === tid && s.lid === lid) suLoeschen();
          const wer = modus.art === "edit" ? `bearbeitet von ${versuch.bearbeitet_von_name || versuch.geprueft_von_name} am ${fmtDate(versuch.bearbeitet_am || versuch.geprueft_am, true)}`
                                            : `abgenommen von ${versuch.geprueft_von_name} am ${fmtDate(versuch.geprueft_am, true)}`;
          toast(`Gespeichert – ${wer}`);
          await loadDetail().catch(() => {});
          renderLehrgangSeite();
          if (modus.art === "edit") bewertungsDialog(tid, lid);
          else dlg.close();
        } catch (e) {
          // Ohne Netz bleibt alles Eingegebene im Dialog stehen – „Nicht gespeichert – keine Verbindung.“ (W1).
          if (/Kommentar/i.test(e.message)) { komm.classList.add("fehler"); S.feldFehler(komm, e.message); }
          else S.fehlschlag(knopf, schreibFehler(e));
        } finally { knopf.disabled = false; }
      };
      if (modus.art === "np" || modus.art === "edit") $("#bw-form-titel", form).scrollIntoView({ block: "start" });
    }, ["pruef-dlg"]);
  }

  /* --- Reiter Mängel / Feedback ------------------------------------------------------------ */
  function maengelHtml(lg) {
    const tns = lg.teilnehmer || [], ls = lg.leistungen || [];
    return `<div class="abschnittskopf"><h2>Mängel / Feedback</h2></div>
      <div class="maengel-filter">
        <div><label for="mf-tn">Teilnehmende</label><select id="mf-tn"><option value="">Alle</option>${tns.map((t) => `<option value="${t.id}" ${String(t.id) === String(state.mf.teilnehmer) ? "selected" : ""}>${esc(tnName(t))}</option>`).join("")}</select></div>
        <div><label for="mf-l">Prüfungsleistung</label><select id="mf-l"><option value="">Alle</option>${ls.map((l) => `<option value="${l.id}" ${String(l.id) === String(state.mf.leistung) ? "selected" : ""}>${esc(l.bezeichnung)}</option>`).join("")}</select></div>
        <label class="inline"><input type="checkbox" id="mf-offen" ${state.mf.nur_offen ? "checked" : ""}> nur offene Mängel</label>
        <div class="btn-row knoepfe"><button class="btn secondary small" data-act="m-druck">Druckansicht</button>
          ${tns.length ? '<button class="btn secondary small" data-act="m-alle" id="mf-alle" title="Alle Bewertungen der gewählten Person, auch die bestandenen">Alle Bewertungen</button>' : ""}</div>
      </div>
      <div id="maengel-liste"><p class="help">Wird geladen …</p></div>`;
  }

  function maengelBinden() {
    const tn = $("#mf-tn"), l = $("#mf-l"), offen = $("#mf-offen");
    // „Alle Bewertungen“ bleibt bedienbar – ohne gewählte Person sagt ein Hinweis, was fehlt (wirkte ausgegraut
    // ohne Grund, Browserprüfung vor dem Merge, Verbesserung 8); seit dem Gerätetest (FT6) als Fehler an der Auswahl
    // „Teilnehmende“. Ohne Teilnehmende gibt es den Knopf nicht – es gäbe niemanden zu wählen.
    const neu = () => { state.mf = { teilnehmer: tn.value, leistung: l.value, nur_offen: offen.checked }; maengelLaden(); };
    tn.onchange = neu; l.onchange = neu; offen.onchange = neu;
  }

  const NP_STATUS = {
    offen: ["Nachprüfung offen", "badge"],
    bestanden: ["Nachprüfung bestanden", "badge gruen"],
    erneut_mangelhaft: ["erneut mangelhaft", "badge rot"],
  };

  function mangelKarteHtml(m, opts = {}) {
    const v = m.versuch;
    const [npText, npKlasse] = NP_STATUS[m.nachpruefung_status] || NP_STATUS.offen;
    const bearbeitet = v.bearbeitet_am ? ` · bearbeitet von ${esc(v.bearbeitet_von_name)} am ${esc(fmtDate(v.bearbeitet_am, true))}` : "";
    return `<div class="mangel-karte ${m.nachpruefung_status === "bestanden" ? "gut" : ""}">
      <div class="mk-kopf"><span class="leistung">${esc(m.leistung.bezeichnung)}</span><span class="muted">${versuchTitel(v)}</span>
        ${v.zeit_sekunden != null || m.leistung.zeitansatz_sekunden != null ? `<span class="zeit">Zeit ${v.zeit_sekunden != null ? fmtZeit(v.zeit_sekunden) : "–"}${m.leistung.zeitansatz_sekunden != null ? ` (Soll ${fmtZeit(m.leistung.zeitansatz_sekunden)})` : ""}</span>` : ""}
        <span class="${npKlasse}">${npText}</span></div>
      ${v.kommentar ? `<div class="kommentar">${esc(v.kommentar)}</div>` : '<div class="kommentar muted">Kein Kommentar.</div>'}
      ${kriterienErgebnisHtml(v.leistung_id, v.kriterien)}
      ${medienGridHtml(v.medien, { klein: !!opts.druck })}
      <div class="abnahme">abgenommen von ${esc(v.geprueft_von_name)} am ${esc(fmtDate(v.geprueft_am, true))}${bearbeitet}</div>
      ${opts.druck ? "" : `<div class="btn-row">
        ${m.nachpruefung_status === "offen" ? `<button class="btn secondary small" data-act="m-np" data-tid="${m.teilnehmer.id}" data-lid="${m.leistung.id}">Nachprüfung durchführen</button>` : ""}
        <button class="btn secondary small" data-act="zelle" data-tid="${m.teilnehmer.id}" data-lid="${m.leistung.id}">Alle Versuche</button></div>`}
    </div>`;
  }

  function maengelGruppenHtml(maengel, opts = {}) {
    if (!maengel.length) return `<div class="leerzustand"><strong>Keine Mängel${opts.nurOffen ? " offen" : ""}</strong>${opts.nurOffen ? "Alles, was mangelhaft war, wurde nachgeprüft – oder es gab nichts zu beanstanden." : "Zu dieser Auswahl gibt es keine mangelhaften Bewertungen."}</div>`;
    const gruppen = [];
    for (const m of maengel) {
      let g = gruppen.find((x) => x.tn.id === m.teilnehmer.id);
      if (!g) { g = { tn: m.teilnehmer, eintraege: [] }; gruppen.push(g); }
      g.eintraege.push(m);
    }
    return gruppen.map((g) => `<section class="tn-gruppe">
      <h3>${tnKopfHtml(tnVoll(g.tn))}${g.tn.gliederung ? ` <span class="muted">· ${esc(g.tn.gliederung)}</span>` : ""}${ergebnisMarkeHtml(tnVoll(g.tn))} <span class="badge grey">${g.eintraege.length}</span></h3>
      ${g.eintraege.map((m) => mangelKarteHtml(m, opts)).join("")}</section>`).join("");
  }

  function maengelQuery(mf) {
    const p = new URLSearchParams();
    if (mf.teilnehmer) p.set("teilnehmer", mf.teilnehmer);
    if (mf.leistung) p.set("leistung", mf.leistung);
    if (mf.nur_offen) p.set("nur_offen", "1");
    return p.toString();
  }

  async function maengelLaden() {
    const ziel = $("#maengel-liste");
    if (!ziel) return;
    try {
      const d = await api(`${API}/lehrgaenge/${LEHRGANG_ID}/maengel?${maengelQuery(state.mf)}`);
      if (!$("#maengel-liste")) return;
      $("#maengel-liste").innerHTML = maengelGruppenHtml(d.maengel || [], { nurOffen: state.mf.nur_offen });
    } catch (e) { ziel.innerHTML = `<p class="notice">Die Mängel ließen sich nicht laden: ${esc(e.message)}</p>`; }
  }

  /* Freier Kommentar und je Versuch eine Karte mit Zeit, Kommentar und Medien – der gemeinsame
     Rumpf von „Alle Bewertungen“ (Dialog) und der Druckansicht „je TN“, damit beide bei jeder
     Änderung gleich bleiben. soll(lid) liefert den Zeitansatz der Leistung oder null. */
  function bewertungenListeHtml(tn, versuche, soll) {
    return `${tn.kommentar ? `<div class="versuch-karte"><div class="vk-kopf">Kommentar</div><div class="kommentar">${esc(tn.kommentar)}</div></div>` : ""}
      ${versuche.length ? versuche.map((v) => `<div class="versuch-karte ${v.ergebnis}">
        <div class="vk-kopf"><span>${esc(v.leistung_bezeichnung)}</span><span class="muted">${versuchTitel(v)}</span>
          <span class="erg ${v.ergebnis}">${v.ergebnis === "bestanden" ? "👍 bestanden" : "👎 mangelhaft"}</span>
          ${v.zeit_sekunden != null ? `<span class="zeit">Zeit ${fmtZeit(v.zeit_sekunden)}${soll(v.leistung_id) != null ? ` <span class="muted">(Soll ${fmtZeit(soll(v.leistung_id))})</span>` : ""}</span>` : ""}</div>
        ${v.kommentar ? `<div class="kommentar">${esc(v.kommentar)}</div>` : ""}
        ${kriterienErgebnisHtml(v.leistung_id, v.kriterien)}
        ${medienGridHtml(v.medien)}
        <div class="abnahme">abgenommen von ${esc(v.geprueft_von_name)} am ${esc(fmtDate(v.geprueft_am, true))}${v.bearbeitet_am ? ` · bearbeitet von ${esc(v.bearbeitet_von_name)} am ${esc(fmtDate(v.bearbeitet_am, true))}` : ""}</div>
      </div>`).join("") : '<p class="leerzustand">Noch keine Bewertungen.</p>'}`;
  }

  /* Alle Bewertungen einer Person – auch die bestandenen mit ihren Kommentaren, für das Gespräch. */
  async function alleBewertungenDialog(tid) {
    let d;
    try { d = await api(`${API}/teilnehmer/${tid}/versuche`); } catch (e) { return toast(e.message, true); }
    const tn = tnVoll(d.teilnehmer), versuche = d.versuche || [];
    const soll = (lid) => { const l = (state.lehrgang.leistungen || []).find((x) => x.id === lid); return l ? l.zeitansatz_sekunden : null; };
    dialogOeffnen(`<h2 class="dlg-tn">${tnKopfHtml(tn)}</h2>
      <p class="help">${esc(tn.gliederung || "")}${tn.gliederung ? " · " : ""}${plural(versuche.length, "Bewertung", "Bewertungen")}${tn.ergebnis ? ` · Lehrgang ${ERGEBNIS[tn.ergebnis][0]}` : ""}</p>
      ${bewertungenListeHtml(tn, versuche, soll)}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`,
      undefined, ["pruef-dlg"]);
  }

  /* --- Druckansicht --------------------------------------------------------------------------- */
  // Welche Druckansicht gemeint ist, sagt ?ansicht= in der Adresse – „tn“ für eine Person mit
  // allen ihren Leistungen, sonst (auch ohne den Parameter, für alte Verweise) die Mängelübersicht.
  // Wer den Lehrgang leitet und prüft, steht auch auf dem Ausdruck – mit den Namen der Konten.
  const druckAusbilder = (lg) => { const z = ausbilderZeile(lg); return z ? `<div class="druck-filter ausbilder-zeile">${z}</div>` : ""; };

  async function renderDruck() {
    const p = new URLSearchParams(location.search);
    if (p.get("ansicht") === "tn") return renderDruckTn(+p.get("teilnehmer"));
    const mf = { teilnehmer: p.get("teilnehmer") || "", leistung: p.get("leistung") || "", nur_offen: p.get("nur_offen") === "1" };
    let lg, d;
    try {
      lg = await loadDetail();
      d = await api(`${API}/lehrgaenge/${LEHRGANG_ID}/maengel?${maengelQuery(mf)}`);
    } catch (e) { root.innerHTML = `<p class="notice">${esc(e.message)}</p>`; return; }
    const tn = mf.teilnehmer ? (d.teilnehmer || []).find((t) => String(t.id) === mf.teilnehmer) : null;
    const l = mf.leistung ? (d.leistungen || []).find((x) => String(x.id) === mf.leistung) : null;
    const filter = [tn ? `Teilnehmende: ${tnName(tn)}` : "alle Teilnehmenden", l ? `Leistung: ${l.bezeichnung}` : "alle Leistungen", mf.nur_offen ? "nur offene Mängel" : "alle mangelhaften Bewertungen"];
    S.titel(`Mängelübersicht ${lg.titel}`, "pruefungen");
    root.innerHTML = `<div class="druck-kopf"><h1>Mängelübersicht – ${esc(lg.titel)}</h1>
        <button class="btn no-print" id="druck-los" type="button">Drucken</button>
        <div class="druck-filter">${esc([spanne(lg.datum_von, lg.datum_bis), lg.ort, lg.nummer ? `Nr. ${lg.nummer}` : ""].filter(Boolean).join(" · "))}<br>${esc(filter.join(" · "))} · Stand ${esc(fmtDate(new Date().toISOString(), true))}</div>
        ${druckAusbilder(lg)}</div>
      ${maengelGruppenHtml(d.maengel || [], { druck: true, nurOffen: mf.nur_offen })}`;
    $("#druck-los").onclick = () => window.print();
  }

  /* Druckansicht „je TN“: Profilbild, Kommentar und jede Leistung mit Zeit, Kommentar und Bildern –
     alles, was auf dem Bildschirm unter „je TN“ und im Dialog „Alle Bewertungen“ steht, hier als
     eigene, druckbare Seite (auch als PDF speicherbar). tid kommt aus der Adresse; ist sie leer
     oder ungültig, bricht es mit einer Meldung statt mit einer falschen Person ab. */
  async function renderDruckTn(tid) {
    if (!tid) { root.innerHTML = '<p class="notice">Keine Person angegeben.</p>'; return; }
    let lg, d;
    try {
      lg = await loadDetail();
      d = await api(`${API}/teilnehmer/${tid}/versuche`);
    } catch (e) {
      root.innerHTML = `<p class="notice">${esc(e.status === 404 ? "Diese Person gibt es in diesem Lehrgang nicht (mehr)." : "Die Bewertungen ließen sich nicht laden: " + e.message)}</p>`;
      return;
    }
    const tn = tnVoll(d.teilnehmer), versuche = d.versuche || [];
    const soll = (lid) => { const l = (lg.leistungen || []).find((x) => x.id === lid); return l ? l.zeitansatz_sekunden : null; };
    // Kein Name im Reiter: Der Titel landet im Browserverlauf, auch auf gemeinsam genutzten Geräten (nach_merge_liste
    // Punkt 17) – er nennt Ansicht und Lehrgang, die Person steht nur auf der Seite.
    S.titel(["Prüfungsleistungen", lg.titel], "pruefungen");
    root.innerHTML = `<div class="druck-kopf"><h1>Prüfungsleistungen – ${esc(tnName(tn))}</h1>
        <button class="btn no-print" id="druck-los" type="button">Drucken</button>
        <div class="druck-filter">${esc([lg.titel, spanne(lg.datum_von, lg.datum_bis), lg.ort].filter(Boolean).join(" · "))}<br>
          ${esc(tn.gliederung || "")}${tn.gliederung ? " · " : ""}${plural(versuche.length, "Bewertung", "Bewertungen")}${tn.ergebnis ? ` · Lehrgang ${ERGEBNIS[tn.ergebnis][0]}` : ""} · Stand ${esc(fmtDate(new Date().toISOString(), true))}</div>
        ${druckAusbilder(lg)}</div>
      <div class="tn-block-kopf">${tnBildHtml(tn, "gross")}<div class="tn-block-text"><span class="tn-name-zeile">${schlossHtml(tn)}<span class="tn-name">${esc(tnName(tn))}</span></span>${tn.gliederung ? `<span class="muted tn-gliederung">${esc(tn.gliederung)}</span>` : ""}</div></div>
      ${bewertungenListeHtml(tn, versuche, soll)}`;
    $("#druck-los").onclick = () => window.print();
  }

  /* ==========================================================================================
     Excel-Import: Datei → Vorschau → Zuordnung korrigieren → Übernehmen
     ========================================================================================== */
  const ZUORDNUNG = [["vorname", "Vorname"], ["name", "Nachname"], ["geburtsdatum", "Geburtsdatum"], ["gliederung", "Gliederung"],
    ["email", "E-Mail"], ["rolle", "Rolle"], ["bemerkung", "Bemerkung"], ["extra", "Weitere Angabe"], ["voraussetzung", "Voraussetzung"], ["ignorieren", "Ignorieren"]];

  /* Referierende aus der Datei: Übernommen wird nur, wer einem Konto mit Stufe zugeordnet ist (der Server: zuerst die
     E-Mail-Adresse, sonst ein eindeutiger Name); die übrigen stehen als eigene Liste da – derselbe Satz wie im Server. */
  const NICHT_UEBERNOMMEN = "Nicht übernommen – kein Konto mit Riegenkarten-Stufe: ";
  function importAusbilderHtml(v) {
    const mit = (v.ausbilder || []).filter((a) => a.konto), nicht = v.ausbilder_nicht_uebernommen || [];
    const funktion = (a) => (a.funktion ? ` <span class="muted">(${esc(a.funktion)})</span>` : "");
    return (mit.length ? `<p class="help">Referierende: ${mit.map((a) => `<span class="name-einheit">${esc(a.konto.name)}</span>${funktion(a)}${a.konto.eingetragen ? ' <span class="muted">– schon eingetragen</span>' : ""}`).join(", ")}</p>` : "")
      + (nicht.length ? `<div class="notice import-nicht"><strong>${esc(NICHT_UEBERNOMMEN.replace(/: $/, ""))}</strong>
          <ul>${nicht.map((a) => `<li><span class="name-einheit">${esc(a.name)}</span>${funktion(a)}</li>`).join("")}</ul>
          <p class="help">Wer prüfen soll, braucht ein Konto mit Stufe in den Riegenkarten – danach erneut importieren oder im Lehrgang unter „Bearbeiten“ eintragen.</p></div>` : "");
  }

  /* lehrgang: der Lehrgang, in den importiert wird – oder null für einen neuen aus der Datei.
     Zustandslos gegenüber dem Server: Vorschau und Übernahme schicken die Datei jeweils mit. */
  function importDialog(lehrgang) {
    let datei = null, zuordnung = null, vorschau = null;
    let eigene = {};      // vom Nutzer geänderte Lehrgangsfelder – überleben ein Neuzeichnen der Vorschau
    const felderLesen = (body) => {
      if (lehrgang || !$("#imp-titel", body)) return;
      eigene = { titel: $("#imp-titel", body).value, nummer: $("#imp-nummer", body).value, ort: $("#imp-ort", body).value,
                 datum_von: $("#imp-von", body).value, datum_bis: $("#imp-bis", body).value };
    };

    // Die Anleitung für den ISC steht als Satz da – man braucht sie zum Handeln, sie gehört nicht hinter ein „i“ (UI/UX vor
    // dem Merge C8).
    const schrittDatei = () => {
      dialogOeffnen(`<h2>Import</h2>
        <p class="help">${lehrgang ? `Teilnehmende und Voraussetzungen in „${esc(lehrgang.titel)}“ übernehmen. Bestehende Teilnehmende (gleicher Name, ggf. Geburtsdatum) werden aktualisiert, nicht doppelt angelegt.`
          : "Aus einer Excel-Teilnehmerliste (.xlsx) wird ein neuer Lehrgang mit Teilnehmenden und Voraussetzungen angelegt. Vorher gibt es eine Vorschau."}</p>
        <p class="help import-isc">Aus dem ISC: unter <strong>Dokumente → Checkliste Voraussetzungen (Excel)</strong> die Option
          <strong>„Allgemeine Lehrgangsinformationen mit ausgeben“</strong> wählen und die erzeugte Excel-Datei hier hochladen.</p>
        <div class="import-schritt import-datei">
          <label for="imp-datei">Datei (.xlsx)${info("Datei", `Kopfzeilen über der Tabelle, verbundene Zellen und Leerzeilen am Ende sind kein Problem. Spalten mit „ja/nein“ oder Daten werden als Voraussetzungen erkannt.${mehrDazu("import_datei")}`)}</label>
          <input type="file" id="imp-datei" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet">
          ${datei ? `<div class="help">Gewählt: ${esc(datei.name)}</div>` : ""}
        </div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
          <button class="btn" id="imp-weiter" type="button" ${datei ? "" : "disabled"}>Vorschau</button></div>`,
        (dlg, body) => {
          const inp = $("#imp-datei", body), weiter = $("#imp-weiter", body);
          inp.onchange = () => { datei = inp.files && inp.files[0] ? inp.files[0] : null; weiter.disabled = !datei; if (datei) vorschauLaden(); };
          weiter.onclick = () => { if (datei) vorschauLaden(); };
        }, ["wide", "import-dlg"]);
    };

    const vorschauLaden = async () => {
      const body = $("#dlg-body");
      body.innerHTML = `<h2>Import</h2><div class="import-arbeit">Datei „${esc(datei.name)}“ wird gelesen …<progress></progress></div>`;
      const fd = new FormData();
      fd.append("file", datei, datei.name);
      if (lehrgang) fd.append("lehrgang_id", String(lehrgang.id));
      if (zuordnung) fd.append("zuordnung", JSON.stringify(zuordnung));
      try {
        vorschau = await api(`${API}/import/vorschau`, { method: "POST", body: fd });
        schrittVorschau();
      } catch (e) {
        toast(e.message, true);
        // Eine Zuordnung, mit der die Vorschau scheitert, wird nicht weitergetragen.
        vorschau = null;
        zuordnung = null;
        schrittDatei();
      }
    };

    const schrittVorschau = () => {
      const v = vorschau;
      const tn = v.teilnehmer || [], vorhanden = tn.filter((t) => t.vorhanden).length;
      const vor = v.voraussetzungen || [], vorAlt = vor.filter((x) => x.vorhanden).length;
      const lgd = Object.assign({}, v.lehrgang || {}, eigene);
      // Welche leeren Felder des bestehenden Lehrgangs die Datei füllen würde.
      const fuellt = lehrgang ? [["titel", "Titel"], ["nummer", "Nummer"], ["datum_von", "Datum von"], ["datum_bis", "Datum bis"], ["ort", "Ort"]]
        .filter(([k]) => !lehrgang[k] && lgd[k]).map(([k, t]) => `${t}: ${k.startsWith("datum") ? fmtTag(lgd[k]) : lgd[k]}`) : [];
      dialogOeffnen(`<h2>Import – Vorschau</h2>
        <p class="help">Datei „${esc(datei.name)}“ · Kopfzeile in Zeile ${v.kopfzeile}. <button type="button" class="linkbtn" id="imp-andere">Andere Datei wählen</button></p>
        ${lehrgang ? `<div class="import-fuellen">${fuellt.length ? `<div class="notice">Aus der Datei werden diese leeren Lehrgangsfelder gefüllt: ${esc(fuellt.join(" · "))}</div>` : ""}</div>`
          : `<div class="import-lehrgang"><h3>Lehrgang</h3>
            <label for="imp-titel">Titel</label><input type="text" id="imp-titel" value="${esc(lgd.titel || "")}" placeholder="${esc(datei.name.replace(/\.xlsx$/i, ""))}">
            <div class="field-row">
              <div><label for="imp-nummer">Nummer</label><input type="text" id="imp-nummer" value="${esc(lgd.nummer || "")}"></div>
              <div><label for="imp-ort">Ort</label><input type="text" id="imp-ort" value="${esc(lgd.ort || "")}"></div>
              <div><label for="imp-von">Datum von</label><input type="date" id="imp-von" value="${esc(lgd.datum_von || "")}"></div>
              <div><label for="imp-bis">Datum bis</label><input type="date" id="imp-bis" value="${esc(lgd.datum_bis || "")}"></div>
            </div></div>`}
        <h3 class="abgesetzt">Spalten und Zuordnung</h3>
        <p class="help">Die Zuordnung wurde aus den Spaltentiteln erkannt und lässt sich hier korrigieren – die Vorschau rechnet dann neu.</p>
        <table class="import-spalten"><thead><tr><th>Spalte</th><th>Beispiele</th><th>Zuordnung</th></tr></thead>
          <tbody>${(v.spalten || []).map((s) => `<tr>
            <td class="titel">${esc(s.titel) || '<span class="muted">(ohne Titel)</span>'}</td>
            <td class="beispiele">${esc((s.beispiele || []).join(", "))}</td>
            <td><select data-spalte="${s.index}" aria-label="Zuordnung für ${esc(s.titel)}">${ZUORDNUNG.map(([k, t]) => `<option value="${k}" ${s.zuordnung === k ? "selected" : ""}>${t}</option>`).join("")}</select></td>
          </tr>`).join("")}</tbody></table>
        <div class="import-zahlen">
          <span><b>${tn.length}</b> Teilnehmende erkannt${vorhanden ? ` <span class="muted">(davon ${vorhanden} bereits vorhanden → werden aktualisiert)</span>` : ""}</span>
          <span><b>${(v.ausbilder || []).filter((a) => a.konto).length}</b> Referierende mit Konto</span>
          <span><b>${vor.length}</b> Voraussetzungen${vorAlt ? ` <span class="muted">(${vorAlt} schon vorhanden)</span>` : ""}</span>
        </div>
        ${(v.warnungen || []).length ? `<div class="notice import-warnungen"><strong>Hinweise</strong><ul>${v.warnungen.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : ""}
        ${tn.length ? `<h3>Vorschau (${Math.min(8, tn.length)} von ${tn.length})</h3>
          <div class="table-scroll"><table class="import-vorschau"><thead><tr><th>Name</th><th>Vorname</th><th>Geburtsdatum</th><th>Gliederung</th><th>Voraussetzungen erfüllt</th></tr></thead>
          <tbody>${tn.slice(0, 8).map((t) => `<tr class="${t.vorhanden ? "vorhanden" : ""}"><td>${esc(t.name)}${t.vorhanden ? ' <span class="badge grey">vorhanden</span>' : ""}</td><td>${esc(t.vorname)}</td>
            <td>${esc(fmtTag(t.geburtsdatum))}</td><td>${esc(t.gliederung)}</td><td>${Object.values(t.voraussetzungen || {}).filter(Boolean).length} / ${vor.length}</td></tr>`).join("")}</tbody></table></div>` : ""}
        ${importAusbilderHtml(v)}
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
          <button class="btn" id="imp-go" type="button" ${tn.length ? "" : "disabled"}>${lehrgang ? "In diesen Lehrgang übernehmen" : "Lehrgang anlegen und übernehmen"}</button></div>`,
        (dlg, body) => {
          $("#imp-andere", body).onclick = () => { zuordnung = null; felderLesen(body); schrittDatei(); };
          $$("select[data-spalte]", body).forEach((sel) => sel.onchange = () => {
            felderLesen(body);
            zuordnung = {};
            $$("select[data-spalte]", body).forEach((s) => { zuordnung[s.dataset.spalte] = s.value; });
            vorschauLaden();
          });
          $("#imp-go", body).onclick = async (ev) => {
            const knopf = ev.currentTarget;
            if (knopf.disabled) return;
            knopf.disabled = true;
            // Für einen neuen Lehrgang: Was der Nutzer in den Feldern geändert hat, kommt nach der
            // Übernahme per PUT hinterher – die Import-Route selbst nimmt nur die Datei.
            const felder = lehrgang ? null : {
              titel: $("#imp-titel", body).value.trim(), nummer: $("#imp-nummer", body).value.trim(), ort: $("#imp-ort", body).value.trim(),
              datum_von: $("#imp-von", body).value || null, datum_bis: $("#imp-bis", body).value || null,
            };
            const fd = new FormData();
            fd.append("file", datei, datei.name);
            if (lehrgang) fd.append("lehrgang_id", String(lehrgang.id));
            if (zuordnung) fd.append("zuordnung", JSON.stringify(zuordnung));
            try {
              const r = await api(`${API}/import`, { method: "POST", body: fd });
              const lg = r.lehrgang;
              const nicht = r.ausbilder_nicht_uebernommen || [];
              const meldung = `Import: ${r.angelegt} angelegt, ${r.aktualisiert} aktualisiert, ${r.voraussetzungen_neu} neue Voraussetzungen, ${r.ausbilder_neu} neue Referierende`
                + ((r.warnungen || []).length ? ` – ${plural(r.warnungen.length, "Hinweis", "Hinweise")}` : "")
                + (nicht.length ? `. ${NICHT_UEBERNOMMEN}${nicht.map((a) => a.name).join(", ")}` : "");
              if (!lehrgang) {
                const diff = {};
                Object.entries(felder).forEach(([k, val]) => { if ((val || "") !== (lg[k] || "")) diff[k] = val; });
                if (Object.keys(diff).length) {
                  try { await api(`${API}/lehrgaenge/${lg.id}`, { method: "PUT", body: diff }); } catch (e) { toast(e.message, true); }
                }
                meldungMerken(meldung);
                location.href = `/riegenkarten/${lg.id}#teilnehmer`;
                return;
              }
              dlg.close();
              toast(meldung);
              await loadDetail(); renderLehrgangSeite();
            } catch (e) { S.fehlschlag(knopf, e, body); }
          };
        }, ["wide", "import-dlg"]);
    };

    schrittDatei();
  }

  /* ==========================================================================================
     Klicks auf der Seite – eine Stelle für alle Knöpfe außerhalb der Dialoge
     ========================================================================================== */
  root.addEventListener("click", async (e) => {
    const tab = e.target.closest("[data-reiter]");
    if (tab) {
      // Der Reiter steht in der Adresse (Neuladen bleibt auf ihm), aber ohne eigenen Verlaufseintrag – wie Leitstelle und
      // Album (UI/UX vor dem Merge C6): Zurück verlässt den Lehrgang, statt durch die Reiter zu blättern.
      history.replaceState(history.state, "", "#" + tab.dataset.reiter);
      if (state.reiter !== tab.dataset.reiter) {
        // Kleben die Reiter schon (weit gerollt), beginnt der neue Reiter direkt unter ihnen statt irgendwo in seiner Mitte.
        const leiste = $(".reiter-kleben", root);
        const klebt = leiste && window.scrollY > 0 && leiste.getBoundingClientRect().top <= parseFloat(getComputedStyle(leiste).top) + 1;
        state.reiter = tab.dataset.reiter;
        renderReiter();
        const unterLeiste = parseFloat(getComputedStyle(leiste).top) + leiste.offsetHeight + 8;
        if (klebt) window.scrollTo({ top: Math.max(0, window.scrollY + $("#reiter-inhalt").getBoundingClientRect().top - unterLeiste) });
      }
      return;
    }
    const b = e.target.closest("[data-act]");
    if (!b) return;
    const act = b.dataset.act, id = +b.dataset.id, tid = +b.dataset.tid, lid = +b.dataset.lid;
    const lgAus = (x) => (ANSICHT === "liste" ? state.liste.find((l) => l.id === x) : state.lehrgang);
    try {
      switch (act) {
        // Ein neuer Lehrgang öffnet bei den Teilnehmenden – dort geht es weiter (Gerätetest FT6); die Meldung
        // „Lehrgang angelegt“ überlebt den Seitenwechsel.
        case "lg-neu": return lehrgangDialog(null, (lg) => { meldungMerken("Lehrgang angelegt"); location.href = `/riegenkarten/${lg.id}#teilnehmer`; });
        case "lg-import": return importDialog(null);
        case "lg-edit": {
          // In der Liste fehlen Referierende und Beschreibung – dafür das Detail holen.
          const lg = ANSICHT === "liste" ? (await api(`${API}/lehrgaenge/${id}`)).lehrgang : state.lehrgang;
          return lehrgangDialog(lg, async () => { if (ANSICHT === "liste") await listeLaden(); else { await loadDetail(); renderLehrgangSeite(); } });
        }
        case "lg-kopie": return kopierenDialog(lgAus(id));
        case "lg-import-in": {
          const lg = ANSICHT === "liste" ? (await api(`${API}/lehrgaenge/${id}`)).lehrgang : state.lehrgang;
          return importDialog(lg);
        }
        case "lg-del": return lehrgangLoeschen(lgAus(id));
        case "kat-neu": return katalogDialog(null);
        case "kat-edit": return katalogDialog(ANSICHT === "kataloge" ? state.kataloge.find((k) => k.id === id) : state.katalog);
        case "kat-del": return katalogLoeschen(ANSICHT === "kataloge" ? state.kataloge.find((k) => k.id === id) : state.katalog);
        case "kl-neu": return katalogLeistungDialog(KATALOG_ID, null);
        case "kl-edit": return katalogLeistungDialog(KATALOG_ID, (state.katalog.leistungen || []).find((l) => l.id === lid));
        case "kl-del": return katalogLeistungLoeschen(KATALOG_ID, (state.katalog.leistungen || []).find((l) => l.id === lid));
        case "kl-hoch": return katalogLeistungVerschieben(KATALOG_ID, lid, -1);
        case "kl-runter": return katalogLeistungVerschieben(KATALOG_ID, lid, 1);
        case "tn-kommentar": return kommentarDialog(tid);
        case "tn-bild": return bildDialog(tid);
        case "tn-ergebnis": return ergebnisSetzen(tid, b.dataset.erg, b);
        case "su-oeffnen": {
          const su = suLesen();
          if (!su) return bannerZeichnen();
          if (ANSICHT === "lehrgang" && su.lehrgang === LEHRGANG_ID) return bewertungsDialog(su.tid, su.lid);
          location.href = `/riegenkarten/${su.lehrgang}#bewertung`;
          return;
        }
        case "tn-neu": return teilnehmerDialog(null);
        case "tn-edit": return teilnehmerDialog((state.lehrgang.teilnehmer || []).find((t) => t.id === tid));
        case "vor-verwalten": return voraussetzungenDialog();
        case "vk-verlauf": return verlaufDialog(tid, +b.dataset.vid);
        case "pl-neu": return leistungDialog(null);
        case "pl-edit": return leistungDialog((state.lehrgang.leistungen || []).find((l) => l.id === lid));
        case "pl-del": return leistungLoeschen((state.lehrgang.leistungen || []).find((l) => l.id === lid));
        case "pl-hoch": return leistungVerschieben(lid, -1);
        case "pl-runter": return leistungVerschieben(lid, 1);
        case "bew-ansicht": bewAnsichtSetzen(b.dataset.a); return renderReiter();
        // Name in der Matrix: direkt zu „je TN“ für genau diese Person wechseln, statt erst über
        // den Reiter und dann die Auswahl zu müssen.
        case "bew-zu-tn": state.bewTn = tid; bewAnsichtSetzen("tn"); return renderReiter();
        case "bew-tn-druck": window.open(`/riegenkarten/${LEHRGANG_ID}/druck?ansicht=tn&teilnehmer=${state.bewTn}`, "_blank", "noopener"); return;
        case "zelle": return bewertungsDialog(tid, lid);
        case "m-np": return bewertungsDialog(tid, lid, { nachpruefung: true });
        // Ohne gewählte Person steht der Hinweis an der Auswahl (Fehler am Feld statt Toast, Gerätetest FT6).
        case "m-alle": return state.mf.teilnehmer ? alleBewertungenDialog(+state.mf.teilnehmer) : S.feldFehler($("#mf-tn"), "Bitte zuerst eine Person wählen.");
        case "m-druck": window.open(`/riegenkarten/${LEHRGANG_ID}/druck?${maengelQuery(state.mf)}`, "_blank", "noopener"); return;
        default: return;
      }
    } catch (err) { toast(err.message, true); }
  });

  // Häkchen der Voraussetzungen (Tabelle und Karten)
  root.addEventListener("change", (e) => {
    const cb = e.target.closest("input[data-vk]");
    if (cb) voraussetzungSetzen(cb);
  });

  window.addEventListener("hashchange", () => {
    if (ANSICHT !== "lehrgang") return;
    const r = reiterAusHash();
    if (r !== state.reiter) { state.reiter = r; renderReiter(); }
  });

  /* --- Start -------------------------------------------------------------------------------- */
  async function start() {
    meldungZeigen();
    if (ANSICHT === "liste") return renderListe();
    if (ANSICHT === "kataloge") return renderKataloge();
    if (ANSICHT === "katalog") {
      if (!KATALOG_ID) { root.innerHTML = '<p class="notice">Kein Katalog angegeben.</p>'; return; }
      try { await loadKatalogDetail(); }
      catch (e) {
        root.innerHTML = `<a class="zurueck" href="/riegenkarten/kataloge">← Alle Kataloge</a><p class="notice">${esc(e.status === 404 ? "Diesen Katalog gibt es nicht (mehr)." : "Der Katalog ließ sich nicht laden: " + e.message)}</p>`;
        return;
      }
      return renderKatalogSeite();
    }
    if (!LEHRGANG_ID) { root.innerHTML = '<p class="notice">Kein Lehrgang angegeben.</p>'; return; }
    if (ANSICHT === "druck") return renderDruck();
    state.reiter = reiterAusHash();
    try { await loadDetail(); }
    catch (e) {
      root.innerHTML = `<a class="zurueck" href="/riegenkarten">← Alle Lehrgänge</a><p class="notice">${esc(e.status === 404 ? "Diesen Lehrgang gibt es nicht (mehr)." : "Der Lehrgang ließ sich nicht laden: " + e.message)}</p>`;
      return;
    }
    renderLehrgangSeite();
  }
  start().catch((e) => toast(e.message, true));
})();
