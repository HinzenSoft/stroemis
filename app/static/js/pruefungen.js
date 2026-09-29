/* Prüfungen – Lehrgangsliste, Lehrgang mit Reitern (Teilnehmende, Leistungen, Bewertung, Mängel),
   Bewertungsdialog mit Stoppuhr und Medien, Mängelübersicht samt Druckansicht, Import aus Excel/ISC.
   Zwei Stufen von Rechten: Prüfende bewerten, haken ab und kommentieren; die Lehrgangsleitung
   (darf_leiten vom Server) pflegt Stammdaten, Profilbilder, Leistungen und das Lehrgangsergebnis –
   ist das vermerkt, sind die Daten der Person eingefroren.
   Alles läuft auf einer Seite; welche Ansicht gemeint ist, sagt data-ansicht am <main>. */
(function () {
  const { esc, api, toast, dialog, fmtDate } = S;
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
    nutzer: null,            // Nutzerliste für die Auswahl der Referierenden, einmal geladen
    kataloge: null,          // Kataloge (Kurzform mit Anzahl), einmal geladen – Auswahl beim Anlegen
    katalog: null,           // Katalogdetail der geöffneten Katalogseite
    liste: [], jahre: [],    // Lehrgangsliste und die darin vorkommenden Jahre
    reiter: "teilnehmer",
    bewAnsicht: null, bewLeistung: null, bewTn: null,
    mf: { teilnehmer: "", leistung: "", nur_offen: true },   // Filter der Mängelübersicht
    medienGruppen: {}, medienZaehler: 0,                      // Medienlisten für den Leuchtkasten
    dlgAufraeumen: null,     // räumt Stoppuhr-Timer und Objekt-URLs des Bewertungsdialogs weg
    lb: null,                // {medien, i, onDelete} des offenen Leuchtkastens
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
  const md = (text) => {
    if (!window.MD || !text) return `<p>${esc(text || "")}</p>`;
    const t = document.createElement("div");
    t.innerHTML = MD.render(text);
    t.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
    return t.innerHTML;
  };
  const groesseText = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(b / 1024))} kB`);
  const isVideo = (f) => /^video\//.test(f.type) || /\.(mp4|m4v|mov|webm)$/i.test(f.name || "");
  const plural = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;
  // Ein Kommentar in einer Matrixzelle: ein Satz reicht, der Rest steht im Dialog.
  const kuerzen = (text, n) => { const t = String(text || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t; };

  /* --- Rechte in der Oberfläche ------------------------------------------------------------
     Der Server entscheidet (403), die Oberfläche blendet nur aus, was ohnehin scheitern würde:
     Prüfende bewerten, haken ab und kommentieren; Stammdaten, Leistungen, Löschen und das
     Lehrgangsergebnis gehören der Lehrgangsleitung und der Administration (darf_leiten). */
  const darfLeiten = () => !!(state.lehrgang && state.lehrgang.darf_leiten);
  const istAdmin = () => !!(window.STROEMIS && STROEMIS.user && STROEMIS.user.role === "admin");
  // Derselbe Text wie im Server (409) – damit die Oberfläche nicht anders erklärt als die Antwort.
  const EINGEFROREN = "Für diese Person ist das Lehrgangsergebnis vermerkt – die Prüfungsdaten sind eingefroren. Die Lehrgangsleitung kann das Ergebnis aufheben.";

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
      <div class="lb-side"><button class="close" id="lb-close" aria-label="Schließen">×</button>
        <h2>${esc(tnName(tn))}</h2>
        <div class="lb-meta">${esc(tn.gliederung || "")}${tn.geburtsdatum ? `${tn.gliederung ? "<br>" : ""}geb. ${esc(fmtTag(tn.geburtsdatum))}` : ""}</div>
        ${ergebnisMarkeHtml(tn)}</div>`;
    $("#lb-close").onclick = () => lb.close();
    if (!lb.open) lb.showModal();
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
  /* Spalte „Lehrgang“: Die Leitung sieht 👍/👎 (der gesetzte ist hervorgehoben), alle anderen
     nur die Marke. Darunter klein, wer das Ergebnis wann vermerkt hat. */
  function ergebnisHtml(tn) {
    if (!darfLeiten()) return `<div class="erg-block">${ergebnisMarkeHtml(tn, { leer: true })}${ergebnisVonHtml(tn)}</div>`;
    const knopf = (erg, sym, titel, kl) => `<button type="button" class="erg-knopf ${kl}${tn.ergebnis === erg ? " sel" : ""}" data-act="tn-ergebnis" data-tid="${tn.id}" data-erg="${erg}"
        aria-pressed="${tn.ergebnis === erg}" aria-label="${titel}" title="${titel}${tn.ergebnis === erg ? " – antippen zum Aufheben" : ""}">${sym}</button>`;
    return `<div class="erg-block"><div class="erg-knoepfe">${knopf("bestanden", "👍", "Lehrgang bestanden", "ja")}${knopf("nicht_bestanden", "👎", "Lehrgang nicht bestanden", "nein")}</div>${ergebnisVonHtml(tn)}</div>`;
  }
  /* Spalte „Kommentar“: die Zelle selbst öffnet den Dialog; gekürzt auf rund 60 Zeichen. */
  function kommentarZelleHtml(tn, opts = {}) {
    const t = tn.kommentar || "";
    const leerText = tn.eingefroren ? "–" : "+ Kommentar";
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

  function fortschrittHtml(lg) {
    const ges = lg.zellen_gesamt || 0, ab = lg.zellen_abgenommen || 0;
    const pct = ges ? Math.round((ab / ges) * 100) : 0;
    const offen = lg.offene_maengel || 0;
    return `<div class="fortschritt"><span>${ab}/${ges} Leistungen abgenommen</span>
      <div class="balken"><span class="${ges && ab === ges ? "voll" : ""}" style="width:${pct}%"></span></div>
      ${offen ? `<span class="maengel">${plural(offen, "offener Mangel", "offene Mängel")}</span>` : '<span class="muted">keine offenen Mängel</span>'}
      ${lg.voraussetzungen_offen ? `<span class="maengel"> · ${lg.voraussetzungen_offen} TN mit offenen Voraussetzungen</span>` : ""}</div>`;
  }

  /* Medienkacheln. Die Liste wird unter einem Schlüssel gemerkt, damit der Leuchtkasten beim
     Antippen weiß, worin er blättern soll. loeschbar hängt ein ✕ an jede Kachel. */
  function medienGridHtml(medien, opts = {}) {
    if (!medien || !medien.length) return "";
    const key = "mg" + (++state.medienZaehler);
    state.medienGruppen[key] = { medien, onDelete: opts.onDelete || null };
    return `<div class="medien-grid${opts.klein ? " klein" : ""}">${medien.map((m, i) => `
      <div class="medium-huelle"><button type="button" class="medium" data-mg="${key}" data-i="${i}" title="${esc(m.original_name || "")}">
        <img src="${esc(m.thumb)}" alt="${esc(m.original_name || "")}" loading="lazy">${m.kind === "video" ? '<span class="play" aria-hidden="true">▶</span>' : ""}</button>
        ${opts.loeschbar ? `<button type="button" class="medium-weg" data-mg="${key}" data-i="${i}" aria-label="Medium löschen" title="Medium löschen">×</button>` : ""}</div>`).join("")}</div>`;
  }

  /* --- Leuchtkasten (Bild/Video groß) ---------------------------------------------------- */
  const lb = $("#lightbox"), lbBody = $("#lb-body");

  function openLightbox(gruppe, i) {
    state.lb = { medien: gruppe.medien, i, onDelete: gruppe.onDelete };
    renderLightbox();
    if (!lb.open) lb.showModal();
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
      <div class="lb-side"><button class="close" id="lb-close" aria-label="Schließen">×</button>
        <h2>${m.kind === "video" ? "Video" : "Bild"} ${i + 1} von ${medien.length}</h2>
        <div class="lb-meta"><strong>${esc(m.original_name || "")}</strong>
          hochgeladen von ${esc(m.hochgeladen_von_name || "")} am ${esc(fmtDate(m.hochgeladen_am, true))}
          ${m.width ? `<br>${m.width} × ${m.height} px` : ""}</div>
        <div class="btn-row"><a class="btn secondary small" href="${esc(m.orig)}" target="_blank" rel="noopener">Original öffnen</a>
          ${onDelete ? '<button class="btn danger small" id="lb-del" type="button">Löschen</button>' : ""}</div>
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
      el.innerHTML = `<span aria-hidden="true">⏱</span><span>Stoppuhr läuft: ${esc(su.tn_name)} – ${esc(su.leistung)}</span>
        <span class="zeit" id="su-banner-zeit"></span>
        <button type="button" class="btn small" data-act="su-oeffnen">Öffnen</button>`;
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

  /* --- Nutzerliste für die Auswahl der Referierenden ----------------------------------------- */
  async function nutzerLaden() {
    if (state.nutzer) return state.nutzer;
    try { state.nutzer = (await api(`${API}/nutzer`)).nutzer || []; }
    catch (e) { toast("Die Nutzerliste ließ sich nicht laden: " + e.message, true); state.nutzer = []; }
    return state.nutzer;
  }

  /* ==========================================================================================
     Lehrgang anlegen / bearbeiten
     ========================================================================================== */
  function ausbilderZeileHtml(a, nutzer) {
    a = a || {};
    const bekannt = a.user_id != null && nutzer.some((n) => n.id === a.user_id);
    const extern = !!a.name && !bekannt;
    return `<div class="ausb-zeile">
      <div class="ausb-wer">
        <select class="ausb-user${extern ? " hidden" : ""}" aria-label="Referierende:n aus den Nutzern wählen">
          <option value="">– Nutzer wählen –</option>
          ${nutzer.map((n) => `<option value="${n.id}" ${bekannt && n.id === a.user_id ? "selected" : ""}>${esc(n.name)}${n.gliederung ? ` (${esc(n.gliederung)})` : ""}</option>`).join("")}
        </select>
        <input type="text" class="ausb-name${extern ? "" : " hidden"}" placeholder="Name (extern)" value="${extern ? esc(a.name) : ""}" aria-label="Name der externen Person">
        <label class="inline"><input type="checkbox" class="ausb-extern" ${extern ? "checked" : ""}> extern (Freitext)</label>
      </div>
      <input type="text" class="ausb-funktion" list="ausb-funktionen" placeholder="Funktion (optional)" value="${esc(a.funktion || "")}" aria-label="Funktion">
      <label class="inline ausb-leit" title="Lehrgangsleitung: darf den Lehrgang bearbeiten, Prüfungen löschen und das Lehrgangsergebnis vermerken"><input type="checkbox" class="ausb-leitung" ${a.ist_leitung ? "checked" : ""}> Leitung</label>
      <button type="button" class="btn ghost" data-weg aria-label="Zeile entfernen" title="Zeile entfernen">✕</button>
    </div>`;
  }

  function ausbilderLesen(body) {
    const liste = [];
    $$(".ausb-zeile", body).forEach((z) => {
      const extern = $(".ausb-extern", z).checked;
      const funktion = $(".ausb-funktion", z).value.trim();
      const ist_leitung = $(".ausb-leitung", z).checked;
      if (extern) {
        const name = $(".ausb-name", z).value.trim();
        if (name) liste.push({ user_id: null, name, funktion, ist_leitung });
      } else {
        const sel = $(".ausb-user", z);
        // Der Name kommt aus der Nutzerliste, nicht aus dem Optionstext – dort hängt die Gliederung dran.
        const n = sel.value ? (state.nutzer || []).find((x) => x.id === +sel.value) : null;
        if (n) liste.push({ user_id: n.id, name: n.name, funktion, ist_leitung });
      }
    });
    return liste;
  }

  async function lehrgangDialog(lg, nachher) {
    const nutzer = await nutzerLaden();
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
      <label>Lehrgangsleitung und Referierende</label>
      <div class="help">Mehrere Personen können Lehrgangsleitung sein – dafür den Haken „Leitung“ setzen. Die Leitung darf den Lehrgang
        bearbeiten, Stammdaten pflegen, Prüfungen löschen und das Lehrgangsergebnis vermerken; alle anderen prüfen und haken ab.
        Rechte bekommt nur, wer über sein Nutzerkonto gewählt ist – ein externer Freitext-Eintrag erscheint nur in der Anzeige.</div>
      <div class="ausb-liste" id="ausb-liste">${(lg.ausbilder || []).map((a) => ausbilderZeileHtml(a, nutzer)).join("")}</div>
      <datalist id="ausb-funktionen"><option value="Referierende:r"><option value="Seiltechnik"><option value="Wasser"><option value="Helfer:in"></datalist>
      <div class="btn-row"><button type="button" class="btn secondary small" id="ausb-plus-leitung">+ Lehrgangsleitung</button>
        <button type="button" class="btn secondary small" id="ausb-plus">+ Referierende:r</button></div>
      <div class="feld-kopf"><label for="lg-besch">Beschreibung / Bemerkungen</label>${diktatKnopf("lg-besch")}</div>
      <textarea id="lg-besch" placeholder="Ablauf, Treffpunkt, Besonderheiten …">${esc(lg.beschreibung)}</textarea>
      ${neu && kataloge.length ? `<label for="lg-katalog">Prüfungsleistungen aus Katalog übernehmen (optional)</label>
      <select id="lg-katalog"><option value="">– Keine Vorlage, leer beginnen –</option>
        ${kataloge.map((k) => `<option value="${k.id}">${esc(k.titel)} (${plural(k.leistungen_anzahl, "Leistung", "Leistungen")})</option>`).join("")}</select>
      <div class="help">Die Leistungen werden einmalig in diesen Lehrgang kopiert – eine spätere Änderung am Katalog wirkt sich nicht mehr
        aus. Weitere Leistungen lassen sich jederzeit einzeln ergänzen, auch während der Lehrgang schon läuft.</div>` : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="lg-save" type="button">${neu ? "Lehrgang anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        const liste = $("#ausb-liste", body);
        // Ein neuer Lehrgang beginnt mit der anlegenden Person als Leitung – der Server trüge sie ohnehin
        // ein; so sieht man es gleich und kann weitere Leitungen daneben setzen.
        if (!liste.children.length) liste.insertAdjacentHTML("beforeend", ausbilderZeileHtml({ user_id: (STROEMIS.user || {}).id, ist_leitung: true }, nutzer));
        $("#ausb-plus-leitung", body).onclick = () => liste.insertAdjacentHTML("beforeend", ausbilderZeileHtml({ ist_leitung: true }, nutzer));
        $("#ausb-plus", body).onclick = () => liste.insertAdjacentHTML("beforeend", ausbilderZeileHtml({ funktion: "Referierende:r" }, nutzer));
        liste.addEventListener("click", (e) => { const b = e.target.closest("[data-weg]"); if (b) b.closest(".ausb-zeile").remove(); });
        liste.addEventListener("change", (e) => {
          if (!e.target.classList.contains("ausb-extern")) return;
          const z = e.target.closest(".ausb-zeile");
          $(".ausb-user", z).classList.toggle("hidden", e.target.checked);
          $(".ausb-name", z).classList.toggle("hidden", !e.target.checked);
          if (e.target.checked) $(".ausb-name", z).focus();
        });
        if (neu) fokus($("#lg-titel", body));
        $("#lg-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const d = {
            titel: $("#lg-titel", body).value.trim(), nummer: $("#lg-nummer", body).value.trim(), ort: $("#lg-ort", body).value.trim(),
            datum_von: $("#lg-von", body).value || null, datum_bis: $("#lg-bis", body).value || null,
            status: $("#lg-status", body).value, beschreibung: $("#lg-besch", body).value, ausbilder: ausbilderLesen(body),
          };
          if (neu && $("#lg-katalog", body)) d.katalog_id = $("#lg-katalog", body).value ? +$("#lg-katalog", body).value : null;
          if (!d.titel) { $("#lg-titel", body).focus(); return toast("Bitte einen Titel angeben.", true); }
          if (d.datum_von && d.datum_bis && d.datum_bis < d.datum_von) { $("#lg-bis", body).focus(); return toast("Das Enddatum liegt vor dem Anfang.", true); }
          knopf.disabled = true;
          try {
            const r = neu ? await api(`${API}/lehrgaenge`, { method: "POST", body: d })
                          : await api(`${API}/lehrgaenge/${lg.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Lehrgang angelegt" : "Gespeichert");
            if (nachher) await nachher(r.lehrgang);
          } catch (e) { toast(e.message, true); }
          finally { knopf.disabled = false; }
        };
      });
  }

  /* Kopieren: Leistungen und Voraussetzungs-Definitionen wandern mit, Teilnehmende und
     Ergebnisse nicht. Titel und Datum fragt der Dialog ab – ein Lehrgang ohne Datum wäre in der
     Liste nicht zu finden. */
  function kopierenDialog(lg) {
    dialogOeffnen(`<h2>Lehrgang kopieren</h2>
      <p class="help">Übernommen werden Titel, Ort, Referierende, Beschreibung, Voraussetzungen und alle
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
          if (d.datum_von && d.datum_bis && d.datum_bis < d.datum_von) return toast("Das Enddatum liegt vor dem Anfang.", true);
          knopf.disabled = true;
          try {
            const r = await api(`${API}/lehrgaenge/${lg.id}/kopieren`, { method: "POST", body: d });
            meldungMerken(`Kopie „${r.lehrgang.titel}“ angelegt`);
            location.href = `/pruefungen/${r.lehrgang.id}#leistungen`;
          } catch (e) { knopf.disabled = false; toast(e.message, true); }
        };
      });
  }

  async function lehrgangLoeschen(lg) {
    const text = `Lehrgang „${lg.titel}“ endgültig löschen? Alle Teilnehmenden, Voraussetzungen, Bewertungen und Medien werden gelöscht.`;
    if (!(await S.confirm(text, "Endgültig löschen"))) return;
    try {
      await api(`${API}/lehrgaenge/${lg.id}`, { method: "DELETE" });
      if (ANSICHT === "liste") { toast("Lehrgang gelöscht"); await listeLaden(); }
      else { meldungMerken("Lehrgang gelöscht"); location.href = "/pruefungen"; }
    } catch (e) { toast(e.message, true); }
  }

  /* ==========================================================================================
     Lehrgangsliste
     ========================================================================================== */
  function renderListe() {
    root.innerHTML = `
      <div class="page-head"><h1>Prüfungen</h1>
        <div class="btn-row"><button class="btn secondary" data-act="lg-import">Import</button>
          <a class="btn secondary" href="/pruefungen/kataloge">Kataloge</a>
          <button class="btn" data-act="lg-neu">+ Lehrgang anlegen</button></div></div>
      <div class="su-banner hidden" id="su-banner"></div>
      <div class="filter">
        <input type="search" id="lg-suche" placeholder="Titel, Ort oder Nummer suchen …" aria-label="Lehrgänge durchsuchen" autocomplete="off">
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
      ziel.innerHTML = `<div class="leer"><strong>${q || jahr ? "Kein Lehrgang passt zur Suche." : "Noch keine Lehrgänge"}</strong>
        ${q || jahr ? "" : "Lege einen Lehrgang an oder importiere eine Excel-Teilnehmerliste."}</div>`;
      return;
    }
    ziel.innerHTML = `<table class="list" id="lg-tabelle">
      <colgroup><col style="width:30%"><col style="width:16%"><col style="width:10%"><col style="width:6%"><col style="width:18%"><col style="width:20%"></colgroup>
      <thead><tr><th>Lehrgang</th><th>Datum</th><th>Status</th><th>TN</th><th>Fortschritt</th><th></th></tr></thead>
      <tbody>${state.liste.map((lg) => `<tr data-id="${lg.id}">
        <td data-l="Lehrgang"><a class="titel" href="/pruefungen/${lg.id}">${esc(lg.titel)}</a>
          ${lg.nummer ? `<div class="nummer">Nr. ${esc(lg.nummer)}</div>` : ""}${lg.ort ? `<div class="small muted">${esc(lg.ort)}</div>` : ""}</td>
        <td data-l="Datum">${esc(spanne(lg.datum_von, lg.datum_bis)) || '<span class="muted">–</span>'}</td>
        <td data-l="Status">${statusMarke(lg.status)}</td>
        <td data-l="TN">${lg.tn_anzahl}</td>
        <td data-l="Fortschritt">${fortschrittHtml(lg)}</td>
        <td class="btn-row">
          <a class="btn small" href="/pruefungen/${lg.id}">Öffnen</a>
          ${lg.darf_leiten ? `<button class="btn ghost small" data-act="lg-edit" data-id="${lg.id}">Bearbeiten</button>
          <button class="btn ghost small" data-act="lg-kopie" data-id="${lg.id}">Kopieren</button>
          <button class="btn ghost small" data-act="lg-del" data-id="${lg.id}">Löschen</button>` : ""}
        </td></tr>`).join("")}</tbody></table>`;
  }

  /* ==========================================================================================
     Kataloge: Vorlagen für Prüfungsleistungen, unabhängig von einem Lehrgang. Lesen darf jede:r
     Prüfer:in (Auswahl beim Anlegen eines Lehrgangs); anlegen, ändern und löschen nur die
     Administration – anders als beim Lehrgang gibt es keine Leitung, die dafür geradestünde.
     ========================================================================================== */
  async function katalogeLaden(neu) {
    if (state.kataloge && !neu) return state.kataloge;
    try { state.kataloge = (await api(`${API}/kataloge`)).kataloge || []; }
    catch (e) { toast("Die Kataloge ließen sich nicht laden: " + e.message, true); state.kataloge = []; }
    return state.kataloge;
  }

  async function renderKataloge() {
    root.innerHTML = `<a class="zurueck" href="/pruefungen">← Alle Lehrgänge</a>
      <div class="page-head"><h1>Prüfungsleistungskataloge</h1>
        ${istAdmin() ? '<div class="btn-row"><button class="btn" data-act="kat-neu">+ Katalog anlegen</button></div>' : ""}</div>
      <p class="help">Ein Katalog ist eine Vorlage: Seine Prüfungsleistungen lassen sich beim Anlegen eines Lehrgangs
        einmalig übernehmen. Spätere Änderungen am Katalog wirken sich nicht mehr auf schon angelegte Lehrgänge aus.</p>
      <div id="kat-liste"><p class="help">Wird geladen …</p></div>`;
    const ziel = $("#kat-liste");
    const kataloge = await katalogeLaden(true);
    if (!ziel) return;
    if (!kataloge.length) {
      ziel.innerHTML = `<div class="leer"><strong>Noch keine Kataloge</strong>${istAdmin()
        ? "Lege einen an, um Prüfungsleistungen als Vorlage bereitzustellen." : "Die Administration legt sie an."}</div>`;
      return;
    }
    ziel.innerHTML = `<table class="list">
      <colgroup><col style="width:32%"><col style="width:38%"><col style="width:10%"><col style="width:20%"></colgroup>
      <thead><tr><th>Katalog</th><th>Beschreibung</th><th>Leistungen</th><th></th></tr></thead>
      <tbody>${kataloge.map((k) => `<tr data-id="${k.id}">
        <td data-l="Katalog"><a class="titel" href="/pruefungen/kataloge/${k.id}">${esc(k.titel)}</a></td>
        <td data-l="Beschreibung">${k.beschreibung ? esc(kuerzen(k.beschreibung, 140)) : '<span class="muted">–</span>'}</td>
        <td data-l="Leistungen">${k.leistungen_anzahl}</td>
        <td class="btn-row">
          <a class="btn small" href="/pruefungen/kataloge/${k.id}">Öffnen</a>
          ${istAdmin() ? `<button class="btn ghost small" data-act="kat-edit" data-id="${k.id}">Bearbeiten</button>
          <button class="btn ghost small" data-act="kat-del" data-id="${k.id}">Löschen</button>` : ""}
        </td></tr>`).join("")}</tbody></table>`;
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
          if (!titel) { $("#kat-titel", body).focus(); return toast("Bitte einen Titel angeben.", true); }
          const d = { titel, beschreibung: $("#kat-besch", body).value };
          knopf.disabled = true;
          try {
            const r = neu ? await api(`${API}/kataloge`, { method: "POST", body: d })
                          : await api(`${API}/kataloge/${k.id}`, { method: "PUT", body: d });
            dlg.close();
            state.kataloge = null;   // Titel/Beschreibung geändert – Auswahlliste neu laden.
            if (neu) { toast("Katalog angelegt"); location.href = `/pruefungen/kataloge/${r.katalog.id}`; return; }
            toast("Gespeichert");
            if (ANSICHT === "kataloge") await renderKataloge();
            else { state.katalog = r.katalog; renderKatalogSeite(); }
          } catch (e) { toast(e.message, true); }
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
      if (ANSICHT === "katalog") location.href = "/pruefungen/kataloge"; else await renderKataloge();
    } catch (e) { toast(e.message, true); }
  }

  async function loadKatalogDetail() {
    const d = await api(`${API}/kataloge/${KATALOG_ID}`);
    state.katalog = d.katalog;
  }

  function renderKatalogSeite() {
    const k = state.katalog;
    if (!k) return;
    const admin = istAdmin();
    const ls = k.leistungen || [];
    root.innerHTML = `<a class="zurueck" href="/pruefungen/kataloge">← Alle Kataloge</a>
      <div class="page-head"><h1>${esc(k.titel)}</h1>
        ${admin ? `<div class="btn-row"><button class="btn secondary small" data-act="kat-edit" data-id="${k.id}">Bearbeiten</button>
        <button class="btn ghost small" data-act="kat-del" data-id="${k.id}">Löschen</button></div>` : ""}</div>
      ${k.beschreibung ? `<details class="beschreibung-kopf"><summary>Beschreibung</summary><div class="md">${esc(k.beschreibung).replace(/\n/g, "<br>")}</div></details>` : ""}
      <div class="reiter-kopf"><h2>Prüfungsleistungen</h2>
        ${admin ? '<div class="btn-row"><button class="btn small" data-act="kl-neu">+ Prüfungsleistung</button></div>' : ""}</div>
      ${!ls.length ? '<div class="leer"><strong>Noch keine Prüfungsleistungen</strong>Sie werden beim Anlegen eines Lehrgangs mit diesem Katalog als Vorlage in den Lehrgang kopiert.</div>'
        : ls.map((l, i) => leistungKarteHtml(l, i, ls.length, admin, "kl")).join("")}`;
  }

  function katalogLeistungDialog(kid, l) {
    l = l || {};
    const neu = !l.id;
    dialogOeffnen(`<h2>${neu ? "Prüfungsleistung anlegen" : "Prüfungsleistung bearbeiten"}</h2>
      <label for="kl-bez">Bezeichnung</label>
      <input type="text" id="kl-bez" value="${esc(l.bezeichnung)}" placeholder="z. B. Wurfsackwurf auf Ziel, Aufbau Flaschenzug 3:1" required>
      <label for="kl-zeit">Zeitansatz (mm:ss oder 300 für 3:00) – leer lassen, wenn es keine Sollzeit gibt</label>
      <input type="text" id="kl-zeit" class="zeitfeld" inputmode="numeric" placeholder="mm:ss" autocomplete="off"
             value="${l.zeitansatz_sekunden != null ? fmtZeit(l.zeitansatz_sekunden) : ""}">
      <div class="help">Mit Zeitansatz zeigt der Bewertungsdialog später eine Stoppuhr mit Sollzeit. Über das Bestehen entscheidet sie nicht.</div>
      <label>Beschreibung – Ablauf und Kriterien</label>
      <div id="kl-editor"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="kl-save" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        const holen = mdEditorEinrichten(dlg, body, "#kl-editor", l.beschreibung_md, "kl-md");
        if (neu) fokus($("#kl-bez", body));
        $("#kl-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const bez = $("#kl-bez", body).value.trim();
          if (!bez) { $("#kl-bez", body).focus(); return toast("Bitte eine Bezeichnung angeben.", true); }
          const z = zeitLesen($("#kl-zeit", body).value);
          if (!z.ok) { $("#kl-zeit", body).focus(); return toast("Zeitansatz bitte als mm:ss angeben, z. B. 03:00 – oder nur Ziffern: 300.", true); }
          const d = { bezeichnung: bez, beschreibung_md: holen(), zeitansatz_sekunden: z.wert };
          knopf.disabled = true;
          try {
            if (neu) await api(`${API}/kataloge/${kid}/leistungen`, { method: "POST", body: d });
            else await api(`${API}/katalog-leistungen/${l.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Prüfungsleistung angelegt" : "Gespeichert");
            await loadKatalogDetail(); renderKatalogSeite();
          } catch (e) { toast(e.message, true); }
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
    } catch (e) { [ls[i], ls[j]] = [ls[j], ls[i]]; toast(e.message, true); }
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

  function renderLehrgangSeite() {
    const lg = state.lehrgang;
    if (!lg) return;
    // Kopf: erst die Leitung(en), dann die übrigen Referierenden – jeweils mit Funktion in Klammern.
    // Bei einer Leitung ist die Funktion „Lehrgangsleitung“ (etwa aus der ISC-Liste) nur eine Wiederholung – weg damit.
    const person = (a) => {
      const f = a.ist_leitung && /^(lehrgangs)?leitung$/i.test((a.funktion || "").trim()) ? "" : a.funktion;
      return `${esc(a.name)}${f ? ` <span class="muted">(${esc(f)})</span>` : ""}`;
    };
    const leitungen = (lg.ausbilder || []).filter((a) => a.ist_leitung).map(person).join(", ");
    const referierende = (lg.ausbilder || []).filter((a) => !a.ist_leitung).map(person).join(", ");
    const ausb = [leitungen ? `<span class="muted">Leitung:</span> ${leitungen}` : "",
                  referierende ? `<span class="muted">Referierende:</span> ${referierende}` : ""].filter(Boolean).join(" · ");
    // Kopfknöpfe nur für die Leitung; „Bearbeiten“ steht ganz rechts. Kopieren geht über die Liste.
    const best = lg.ergebnis_bestanden || 0, nicht = lg.ergebnis_nicht_bestanden || 0;
    // Rollstand der Matrizen und offene Beschreibungen überleben das Neuzeichnen – sonst sprang die
    // Matrix nach jedem Speichern auf dem Tablet zurück in die erste Spalte.
    const rollstaende = $$(".table-scroll", root).map((el) => el.scrollLeft);
    const aufgeklappt = $$("details", root).map((d) => d.open);
    root.innerHTML = `
      <a class="zurueck" href="/pruefungen">← Alle Lehrgänge</a>
      <div class="page-head"><h1>${esc(lg.titel)}</h1>
        ${lg.darf_leiten ? `<div class="btn-row">
          <button class="btn secondary small" data-act="lg-import-in" data-id="${lg.id}">Import</button>
          <button class="btn secondary small" data-act="lg-edit" data-id="${lg.id}">Bearbeiten</button>
        </div>` : ""}</div>
      <div class="kopf-meta">${statusMarke(lg.status)}${lg.nummer ? `<span>Nr. ${esc(lg.nummer)}</span>` : ""}
        ${lg.datum_von || lg.datum_bis ? `<span>${esc(spanne(lg.datum_von, lg.datum_bis))}</span>` : ""}${lg.ort ? `<span>${esc(lg.ort)}</span>` : ""}
        <span>${plural(lg.tn_anzahl, "Teilnehmende:r", "Teilnehmende")}</span>
        ${best || nicht ? `<span class="erg-zaehler" title="Vermerkte Lehrgangsergebnisse"><b class="ja">${best} bestanden</b> · <b class="nein">${nicht} nicht bestanden</b></span>` : ""}</div>
      ${ausb ? `<p class="ausbilder-zeile">${ausb}</p>` : ""}
      ${lg.beschreibung ? `<details class="beschreibung-kopf"><summary>Beschreibung</summary><div class="md">${esc(lg.beschreibung).replace(/\n/g, "<br>")}</div></details>` : ""}
      ${fortschrittHtml(lg)}
      <div class="c-tabs reiter" role="tablist">
        <button type="button" role="tab" data-reiter="teilnehmer">Teilnehmende <span class="z">(${lg.tn_anzahl})</span></button>
        <button type="button" role="tab" data-reiter="leistungen">Leistungen <span class="z">(${lg.leistungen_anzahl})</span></button>
        <button type="button" role="tab" data-reiter="bewertung">Bewertung</button>
        <button type="button" role="tab" data-reiter="maengel">Mängel${lg.offene_maengel ? ` <span class="badge rot">${lg.offene_maengel}</span>` : ""}</button>
      </div>
      <div class="su-banner hidden" id="su-banner"></div>
      <div id="reiter-inhalt"></div>`;
    renderReiter();
    bannerZeichnen();
    $$(".table-scroll", root).forEach((el, i) => { if (rollstaende[i]) el.scrollLeft = rollstaende[i]; });
    $$("details", root).forEach((d, i) => { if (aufgeklappt[i]) d.open = true; });
  }

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
    const kopf = `<div class="reiter-kopf"><h2>Teilnehmende</h2>
      ${leitung ? `<div class="btn-row"><button class="btn secondary small" data-act="vor-verwalten">Voraussetzungen verwalten</button>
        <button class="btn small" data-act="tn-neu">+ Teilnehmende:r</button></div>` : ""}</div>`;
    if (!tns.length) {
      return kopf + `<div class="leer"><strong>Noch keine Teilnehmenden</strong>${leitung ? "Lege sie an oder importiere die Excel-Teilnehmerliste – daraus kommen auch die Voraussetzungen." : "Die Lehrgangsleitung legt sie an oder importiert die Excel-Teilnehmerliste."}</div>`;
    }
    const hinweis = vor.length ? "" : `<p class="help">Noch keine Voraussetzungen angelegt${leitung ? " – über „Voraussetzungen verwalten“ oder den Import." : "."}</p>`;
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
            <button type="button" class="vk-stempel ${st ? (st.erfuellt ? "ja" : "nein") : ""}" data-act="vk-verlauf" data-tid="${tn.id}" data-vid="${v.id}" ${st ? "" : "disabled"} title="Verlauf anzeigen">${st ? stempelHtml(st) : ""}</button>
          </div></td>`;
        }).join("")}
      </tr>`).join("")}</tbody></table></div>`;
    // Telefon: Karten je TN mit großen Kästen.
    const karten = `<div class="tn-mobil">${tns.map((tn) => `<div class="tn-karte ${tn.voraussetzungen_offen ? "offen" : ""}${tn.eingefroren ? " gesperrt" : ""}">
      <div class="tn-kopf">${tnKopfHtml(tn, leitung ? `<button type="button" class="linkbtn" data-act="tn-edit" data-tid="${tn.id}">${esc(tnName(tn))}</button>` : null)}
        ${tn.voraussetzungen_offen ? `<span class="badge rot">${tn.voraussetzungen_offen} offen</span>` : (vor.length ? '<span class="badge gruen">alle erfüllt</span>' : "")}${ergebnisMarkeHtml(tn)}</div>
      ${tn.gliederung || tn.geburtsdatum ? `<div class="small muted">${esc(tn.gliederung || "")}${tn.geburtsdatum ? `${tn.gliederung ? " · " : ""}geb. ${esc(fmtTag(tn.geburtsdatum))}` : ""}</div>` : ""}
      ${vor.map((v) => {
        const st = tn.voraussetzungen[String(v.id)];
        const id = `vk-${tn.id}-${v.id}`;
        return `<div class="vk-zeile">
          <input type="checkbox" id="${id}" data-vk data-tid="${tn.id}" data-vid="${v.id}" ${st && st.erfuellt ? "checked" : ""} ${tn.eingefroren ? "disabled" : ""}>
          <label class="vk-text" for="${id}">${esc(v.bezeichnung)}${st ? `<small class="${st.erfuellt ? "ja" : "nein"}">${stempelHtml(st)}</small>` : ""}</label>
          <button type="button" class="vk-verlauf" data-act="vk-verlauf" data-tid="${tn.id}" data-vid="${v.id}" ${st ? "" : "disabled"} aria-label="Verlauf anzeigen" title="Verlauf">🕓</button>
        </div>`;
      }).join("")}
    </div>`).join("")}</div>`;
    return kopf + hinweis + tabelle + karten;
  }

  /* Häkchen setzen oder nehmen: Der Server antwortet mit wer/wann – das kommt sofort unter den
     Kasten, ohne den ganzen Lehrgang neu zu laden. Geht es schief, springt der Kasten zurück. */
  async function voraussetzungSetzen(cb) {
    const tid = +cb.dataset.tid, vid = +cb.dataset.vid, erfuellt = cb.checked;
    cb.disabled = true;
    try {
      const r = await api(`${API}/teilnehmer/${tid}/voraussetzungen/${vid}`, { method: "PUT", body: { erfuellt } });
      const tn = (state.lehrgang.teilnehmer || []).find((t) => t.id === tid);
      if (tn) {
        tn.voraussetzungen[String(vid)] = r.status;
        tn.voraussetzungen_offen = (state.lehrgang.voraussetzungen || []).filter((v) => !(tn.voraussetzungen[String(v.id)] || {}).erfuellt).length;
        state.lehrgang.voraussetzungen_offen = state.lehrgang.teilnehmer.filter((t) => t.voraussetzungen_offen > 0).length;
      }
      renderLehrgangSeite();
    } catch (e) {
      cb.checked = !erfuellt;
      cb.disabled = false;
      toast(e.message, true);
    }
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
        : '<p class="muted">Noch keine Einträge.</p>'}
      <div class="dlg-actions"><button class="btn" data-close type="button">Schließen</button></div>`);
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
    dialogOeffnen(`<h2>${neu ? "Teilnehmende:n anlegen" : esc(tnName(tn))}</h2>
      <div class="tn-bild-zeile">
        ${tnBildHtml(tn, "gross")}
        <div class="pb-text">
          <p class="help">${neu ? "Ein Profilbild lässt sich hinzufügen, sobald die Person angelegt ist." : "Quadratisch zugeschnitten, 256 Pixel. Es erscheint vor dem Namen in Listen und Matrix."}</p>
          <div class="btn-row"><button type="button" class="btn secondary small" id="tn-pb-waehlen" ${neu ? "disabled" : ""}>Bild wählen …</button>
            <button type="button" class="btn ghost small${bildAdresse(tn) ? "" : " hidden"}" id="tn-pb-weg">Entfernen</button></div>
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
      <div class="dlg-actions">${neu ? "" : '<button class="btn danger" id="tn-del" type="button" style="margin-right:auto">Löschen</button>'}
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
          if (!d.name) { $("#tn-name", body).focus(); return toast("Bitte den Nachnamen angeben.", true); }
          knopf.disabled = true;
          try {
            if (neu) await api(`${API}/lehrgaenge/${LEHRGANG_ID}/teilnehmer`, { method: "POST", body: d });
            else await api(`${API}/teilnehmer/${tn.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Teilnehmende:r angelegt" : "Gespeichert");
            await loadDetail(); renderLehrgangSeite();
          } catch (e) { toast(e.message, true); }
          finally { knopf.disabled = false; }
        };
        const del = $("#tn-del", body);
        if (del) del.onclick = async () => {
          if (!(await S.confirm(`${tnName(tn)} aus dem Lehrgang löschen? Alle Bewertungen und Medien dieser Person werden mit gelöscht.`))) return;
          try {
            await api(`${API}/teilnehmer/${tn.id}`, { method: "DELETE" });
            dlg.close();
            toast("Teilnehmende:r gelöscht");
            await loadDetail(); renderLehrgangSeite();
          } catch (e) { toast(e.message, true); }
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
        <p class="help">Jede:r Teilnehmende bekommt für jede Voraussetzung einen Kasten zum Abhaken. Umbenennen: Text ändern und das Feld verlassen.</p>
        <div class="vor-wrap">${vor.length ? `<ul class="vor-liste">${vor.map((v, i) => `<li data-vid="${v.id}">
          <input type="text" value="${esc(v.bezeichnung)}" data-bez aria-label="Bezeichnung">
          <button type="button" class="btn ghost" data-hoch ${i === 0 ? "disabled" : ""} aria-label="nach oben" title="nach oben">↑</button>
          <button type="button" class="btn ghost" data-runter ${i === vor.length - 1 ? "disabled" : ""} aria-label="nach unten" title="nach unten">↓</button>
          <button type="button" class="btn ghost" data-del aria-label="löschen" title="löschen">🗑</button></li>`).join("")}</ul>`
          : '<p class="muted">Noch keine Voraussetzungen.</p>'}</div>
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
            } catch (e) { toast(e.message, true); }
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
              } catch (e) { inp.value = alt; toast(e.message, true); }
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
            } catch (err) { toast(err.message, true); }
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
      <div class="titel">${esc(l.bezeichnung)} ${l.zeitansatz_sekunden != null ? `<span class="badge grey" title="Zeitansatz (Sollzeit)">⏱ ${fmtZeit(l.zeitansatz_sekunden)}</span>` : ""}</div>
      ${editierbar ? `<div class="btn-row">
        <span class="pfeile"><button class="btn ghost small" data-act="${praefix}-hoch" data-lid="${l.id}" ${i === 0 ? "disabled" : ""} aria-label="nach oben" title="nach oben">↑</button>
          <button class="btn ghost small" data-act="${praefix}-runter" data-lid="${l.id}" ${i === gesamt - 1 ? "disabled" : ""} aria-label="nach unten" title="nach unten">↓</button></span>
        <button class="btn ghost small" data-act="${praefix}-edit" data-lid="${l.id}">Bearbeiten</button>
        <button class="btn ghost small" data-act="${praefix}-del" data-lid="${l.id}">Löschen</button></div>` : '<div class="btn-row"></div>'}
      ${l.beschreibung_md ? `<div class="md-vorschau">${md(l.beschreibung_md)}</div>` : '<div class="md-vorschau muted">Keine Beschreibung.</div>'}
    </div>`;
  }

  function leistungenHtml(lg) {
    const ls = lg.leistungen || [];
    const leitung = darfLeiten();
    const kopf = `<div class="reiter-kopf"><h2>Prüfungsleistungen</h2>
      ${leitung ? '<div class="btn-row"><button class="btn small" data-act="pl-neu">+ Prüfungsleistung</button></div>' : ""}</div>`;
    if (!ls.length) return kopf + '<div class="leer"><strong>Noch keine Prüfungsleistungen</strong>Jede:r Teilnehmende bekommt für jede Leistung ein Bewertungsfeld in der Matrix.</div>';
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
    } catch (e) { [ls[i], ls[j]] = [ls[j], ls[i]]; toast(e.message, true); }
  }

  /* Dialog mit Toast UI für die Beschreibung. Bleibt der Editor aus (Datei nicht geladen),
     gibt es ein einfaches Markdown-Feld – die Leistung lässt sich trotzdem anlegen. */
  /* Toast-UI-Editor in ein Element einhängen (Markdown-Textarea als Rückfall, falls die
     Bibliothek fehlt) und beim Schließen des Dialogs wieder abbauen. Gemeinsam für Leistungen im
     Lehrgang und im Katalog – dieselbe Beschreibung, derselbe Editor. Liefert eine Funktion, die
     den aktuellen Markdown-Text ausliest. */
  function mdEditorEinrichten(dlg, body, elSelektor, wert, fallbackId) {
    const el = $(elSelektor, body);
    let ed = null, fallback = null;
    if (window.toastui && toastui.Editor) {
      const opts = {
        el, initialEditType: "wysiwyg", hideModeSwitch: true, height: "260px",
        initialValue: wert || "", language: "de-DE", usageStatistics: false,
        placeholder: "Wie läuft die Prüfung ab, was wird bewertet?",
        toolbarItems: [["heading", "bold", "italic"], ["ul", "ol", "link"]],
      };
      try { ed = new toastui.Editor(opts); }
      catch (e) { delete opts.language; try { ed = new toastui.Editor(opts); } catch (e2) { ed = null; } }
    }
    if (!ed) {
      el.innerHTML = `<textarea class="pl-fallback" id="${fallbackId}" placeholder="Beschreibung (Markdown)">${esc(wert)}</textarea>`;
      fallback = $("#" + fallbackId, el);
    }
    const aufraeumen = () => { try { if (ed) ed.destroy(); } catch (e) { /* schon weg */ } ed = null; };
    state.dlgAufraeumen = aufraeumen;
    dlg.addEventListener("close", () => { if (state.dlgAufraeumen === aufraeumen) { aufraeumen(); state.dlgAufraeumen = null; } }, { once: true });
    return () => { try { return ed ? ed.getMarkdown() : fallback.value; } catch (e) { return fallback ? fallback.value : ""; } };
  }

  function leistungDialog(l) {
    l = l || {};
    const neu = !l.id;
    dialogOeffnen(`<h2>${neu ? "Prüfungsleistung anlegen" : "Prüfungsleistung bearbeiten"}</h2>
      <label for="pl-bez">Bezeichnung</label>
      <input type="text" id="pl-bez" value="${esc(l.bezeichnung)}" placeholder="z. B. Wurfsackwurf auf Ziel, Aufbau Flaschenzug 3:1" required>
      <label for="pl-zeit">Zeitansatz (mm:ss oder 300 für 3:00) – leer lassen, wenn es keine Sollzeit gibt</label>
      <input type="text" id="pl-zeit" class="zeitfeld" inputmode="numeric" placeholder="mm:ss" autocomplete="off"
             value="${l.zeitansatz_sekunden != null ? fmtZeit(l.zeitansatz_sekunden) : ""}">
      <div class="help">Mit Zeitansatz zeigt der Bewertungsdialog eine Stoppuhr mit Sollzeit. Über das Bestehen entscheidet sie nicht.</div>
      <label>Beschreibung – Ablauf und Kriterien</label>
      <div id="pl-editor"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="pl-save" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
      (dlg, body) => {
        const holen = mdEditorEinrichten(dlg, body, "#pl-editor", l.beschreibung_md, "pl-md");
        if (neu) fokus($("#pl-bez", body));
        $("#pl-save", body).onclick = async (ev) => {
          const knopf = ev.currentTarget;
          if (knopf.disabled) return;
          const bez = $("#pl-bez", body).value.trim();
          if (!bez) { $("#pl-bez", body).focus(); return toast("Bitte eine Bezeichnung angeben.", true); }
          const z = zeitLesen($("#pl-zeit", body).value);
          if (!z.ok) { $("#pl-zeit", body).focus(); return toast("Zeitansatz bitte als mm:ss angeben, z. B. 03:00 – oder nur Ziffern: 300.", true); }
          const d = { bezeichnung: bez, beschreibung_md: holen(), zeitansatz_sekunden: z.wert };
          knopf.disabled = true;
          try {
            if (neu) await api(`${API}/lehrgaenge/${LEHRGANG_ID}/leistungen`, { method: "POST", body: d });
            else await api(`${API}/leistungen/${l.id}`, { method: "PUT", body: d });
            dlg.close();
            toast(neu ? "Prüfungsleistung angelegt" : "Gespeichert");
            await loadDetail(); renderLehrgangSeite();
          } catch (e) { toast(e.message, true); }
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
    return `${auf}
      <span class="sym" aria-hidden="true">${def.sym}</span>
      <span class="txt">${def.txt}${def.np ? '<span class="badge np">NP</span>' : ""}${anhang}</span>
      ${opts.ohneSub ? "" : `<span class="sub">${sub}</span>`}${alsSpan ? "</span>" : "</button>"}`;
  }

  function bewertungHtml(lg) {
    const tns = lg.teilnehmer || [], ls = lg.leistungen || [];
    const a = bewAnsichtLesen();
    const kopf = `<div class="reiter-kopf"><h2>Bewertung</h2></div>`;
    if (!tns.length || !ls.length) {
      return kopf + `<div class="leer"><strong>${!tns.length ? "Noch keine Teilnehmenden" : "Noch keine Prüfungsleistungen"}</strong>
        ${!tns.length ? "Teilnehmende anlegen oder importieren – dann erscheint hier die Matrix." : "Im Reiter „Leistungen“ die Prüfungsleistungen anlegen."}</div>`;
    }
    if (state.bewLeistung == null || !ls.some((l) => l.id === state.bewLeistung)) state.bewLeistung = ls[0].id;
    if (state.bewTn == null || !tns.some((t) => t.id === state.bewTn)) state.bewTn = tns[0].id;
    const umschalter = `<div class="bew-umschalter">
      <div class="c-tabs" role="tablist">
        <button type="button" role="tab" data-act="bew-ansicht" data-a="matrix" class="${a === "matrix" ? "sel" : ""}">Matrix</button>
        <button type="button" role="tab" data-act="bew-ansicht" data-a="leistung" class="${a === "leistung" ? "sel" : ""}">je Leistung</button>
        <button type="button" role="tab" data-act="bew-ansicht" data-a="tn" class="${a === "tn" ? "sel" : ""}">je TN</button>
      </div>
      ${a === "leistung" ? `<select id="bew-sel-leistung" aria-label="Prüfungsleistung">${ls.map((l) => `<option value="${l.id}" ${l.id === state.bewLeistung ? "selected" : ""}>${esc(l.bezeichnung)}${l.zeitansatz_sekunden != null ? ` (⏱ ${fmtZeit(l.zeitansatz_sekunden)})` : ""}</option>`).join("")}</select>` : ""}
      ${a === "tn" ? `<select id="bew-sel-tn" aria-label="Teilnehmende:r">${tns.map((t) => `<option value="${t.id}" ${t.id === state.bewTn ? "selected" : ""}>${esc(tnName(t))}${t.gliederung ? ` (${esc(t.gliederung)})` : ""}</option>`).join("")}</select>
        <button type="button" class="btn secondary small" data-act="bew-tn-druck" title="Alle Leistungen dieser Person mit Kommentaren und Bildern drucken oder als PDF speichern">🖨 Druckansicht</button>` : ""}
    </div>`;
    let inhalt = "";
    if (a === "matrix") {
      // Nur die Leistungen: Der freie Kommentar und das Lehrgangsergebnis stehen in der Ansicht
      // „je TN“ – in der Matrix machten die beiden Spalten die Tabelle am Gewässer nur breiter.
      // Das Schloss und die Dämpfung eingefrorener Personen bleiben.
      inhalt = `<div class="table-scroll"><table class="bew-matrix">
        <thead><tr><th class="tn-kopf">Teilnehmende:r</th>${ls.map((l) => `<th title="${esc(l.bezeichnung)}">${esc(l.bezeichnung)}${l.zeitansatz_sekunden != null ? `<br><span class="muted">⏱ ${fmtZeit(l.zeitansatz_sekunden)}</span>` : ""}</th>`).join("")}</tr></thead>
        <tbody>${tns.map((tn) => `<tr class="${tn.eingefroren ? "gesperrt" : ""}">
          <td>${tnKopfHtml(tn)}<span class="tn-sub">${esc(tn.gliederung || "")}</span>
            ${tn.voraussetzungen_offen ? `<span class="badge rot" title="Voraussetzungen nicht vollständig">${tn.voraussetzungen_offen} Vorauss. offen</span>` : ""}</td>
          ${ls.map((l) => `<td>${zelleHtml(tn, l)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    } else if (a === "leistung") {
      const l = ls.find((x) => x.id === state.bewLeistung);
      inhalt = `${l.beschreibung_md ? `<details class="beschreibung-kopf"><summary>Prüfungsbeschreibung</summary><div class="md">${md(l.beschreibung_md)}</div></details>` : ""}
        <ul class="zellen-liste">${tns.map((tn) => `<li><button type="button" class="zelle-zeile ${tn.voraussetzungen_offen ? "offen-vor" : ""}${tn.eingefroren ? " gesperrt" : ""}" data-act="zelle" data-tid="${tn.id}" data-lid="${l.id}">
          <span class="name">${tnKopfHtml(tn)}${ergebnisMarkeHtml(tn)}<small>${esc(tn.gliederung || "")}${tn.voraussetzungen_offen ? `${tn.gliederung ? " · " : ""}${tn.voraussetzungen_offen} Voraussetzungen offen` : ""}</small></span>
          ${zelleHtml(tn, l, { tag: "span" })}
        </button></li>`).join("")}</ul>`;
    } else {
      const tn = tns.find((x) => x.id === state.bewTn);
      // Kopf über der Liste: Bild und Name, der freie Kommentar und (für die Leitung) das Ergebnis.
      const block = `<div class="tn-block${tn.eingefroren ? " gesperrt" : ""}">
        <div class="tn-block-kopf"><span class="tn-kopfzeile">${tnBildHtml(tn, "gross")}${schlossHtml(tn)}<span class="tn-name">${esc(tnName(tn))}</span></span>${tn.gliederung ? `<span class="muted tn-gliederung">${esc(tn.gliederung)}</span>` : ""}</div>
        ${tn.eingefroren ? `<p class="notice small">${esc(EINGEFROREN)}</p>` : ""}
        <div class="tn-block-felder">
          <div><span class="feldname">Kommentar</span>${kommentarZelleHtml(tn, { laenge: 200 })}</div>
          <div><span class="feldname">Lehrgang</span>${ergebnisHtml(tn)}</div>
        </div></div>`;
      inhalt = `${block}${tn.voraussetzungen_offen ? `<p class="notice">${tn.voraussetzungen_offen} Voraussetzungen sind noch nicht erfüllt.</p>` : ""}
        <ul class="zellen-liste">${ls.map((l) => {
          // Zu jeder Leistung: gebrauchte Zeit (neben der Sollzeit) und der Kommentar des letzten
          // Versuchs – das ist die Ansicht fürs Feedbackgespräch mit der Person.
          const z = tn.leistungen[String(l.id)];
          const zeit = z && z.letzte_zeit_sekunden != null
            ? `<small class="zeile-zeit">⏱ ${fmtZeit(z.letzte_zeit_sekunden)}${l.zeitansatz_sekunden != null ? ` von ${fmtZeit(l.zeitansatz_sekunden)}${z.letzte_zeit_sekunden > l.zeitansatz_sekunden ? " – über Sollzeit" : ""}` : ""}</small>`
            : (l.zeitansatz_sekunden != null ? `<small>Sollzeit ${fmtZeit(l.zeitansatz_sekunden)}</small>` : "");
          const komm = z && z.letzter_kommentar ? `<small class="zeile-komm">${esc(kuerzen(z.letzter_kommentar, 220))}</small>` : "";
          return `<li><button type="button" class="zelle-zeile${tn.eingefroren ? " gesperrt" : ""}" data-act="zelle" data-tid="${tn.id}" data-lid="${l.id}">
          <span class="name">${esc(l.bezeichnung)}${zeit}${komm}</span>
          ${zelleHtml(tn, l, { tag: "span" })}
        </button></li>`; }).join("")}</ul>`;
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
          } catch (e) { toast(e.message, true); }
          finally { knopf.disabled = false; }
        };
      });
  }

  /* Lehrgangsergebnis 👍/👎 (nur Leitung). Ein Klick auf das gesetzte Ergebnis hebt es auf –
     erst dann lassen sich wieder Prüfungen erfassen. */
  async function ergebnisSetzen(tid, erg, knopf) {
    const tn = tnAusState(tid);
    if (!tn) return;
    const aufheben = tn.ergebnis === erg;
    const text = aufheben ? "Ergebnis aufheben? Danach lassen sich wieder Prüfungen erfassen."
      : `${tnName(tn)}: Lehrgang als „${ERGEBNIS[erg][0]}“ vermerken? Bewertungen, Häkchen und Kommentar dieser Person sind danach eingefroren, bis das Ergebnis aufgehoben wird.`;
    if (!(await S.confirm(text, aufheben ? "Aufheben" : "Vermerken"))) return;
    if (knopf) knopf.disabled = true;
    try {
      const r = await api(`${API}/teilnehmer/${tid}/ergebnis`, { method: "PUT", body: { ergebnis: aufheben ? null : erg } });
      tnUebernehmen(r.teilnehmer);
      toast(aufheben ? "Ergebnis aufgehoben" : `Vermerkt: ${ERGEBNIS[erg][0]}`);
      // Der Kopf zeigt die Zähler, die Matrix Schloss und Dämpfung – die ganze Seite neu.
      await loadDetail().catch(() => {});
      renderLehrgangSeite();
    } catch (e) { if (knopf) knopf.disabled = false; toast(e.message, true); }
  }

  function bewertungBinden() {
    const sl = $("#bew-sel-leistung"); if (sl) sl.onchange = () => { state.bewLeistung = +sl.value; renderReiter(); };
    const st = $("#bew-sel-tn"); if (st) st.onchange = () => { state.bewTn = +st.value; renderReiter(); };
  }

  /* ==========================================================================================
     Bewertungsdialog
     ========================================================================================== */
  function versuchKarteHtml(v, istLetzter, opts = {}) {
    const bearbeitet = v.bearbeitet_am ? ` · <span title="Ursprünglicher Stand im Verlauf">bearbeitet von ${esc(v.bearbeitet_von_name)} am ${esc(fmtDate(v.bearbeitet_am, true))}</span>` : "";
    return `<div class="versuch-karte ${v.ergebnis}" data-vid="${v.id}">
      <div class="vk-kopf"><span>${versuchTitel(v)}</span>
        <span class="erg ${v.ergebnis}">${v.ergebnis === "bestanden" ? "👍 bestanden" : "👎 mangelhaft"}</span>
        ${v.zeit_sekunden != null ? `<span class="zeit">⏱ ${fmtZeit(v.zeit_sekunden)}${opts.soll != null ? ` <span class="muted">(Soll ${fmtZeit(opts.soll)})</span>` : ""}</span>` : ""}</div>
      ${v.kommentar ? `<div class="kommentar">${esc(v.kommentar)}</div>` : ""}
      ${medienGridHtml(v.medien, { loeschbar: !!opts.onMedienWeg, onDelete: opts.onMedienWeg })}
      <div class="abnahme">abgenommen von ${esc(v.geprueft_von_name)} am ${esc(fmtDate(v.geprueft_am, true))}${bearbeitet}</div>
      ${v.verlauf && v.verlauf.length ? `<details class="staende"><summary>Frühere Stände (${v.verlauf.length})</summary><ul>${v.verlauf.map((s) => `<li>
        ${s.ergebnis === "bestanden" ? "👍 bestanden" : "👎 mangelhaft"}${s.zeit_sekunden != null ? ` · ${fmtZeit(s.zeit_sekunden)}` : ""}${s.kommentar ? ` · „${esc(s.kommentar)}“` : ""}
        <span class="muted">– von ${esc(s.von_name)}, galt ${esc(fmtDate(s.stand_ab, true))} bis ${esc(fmtDate(s.ersetzt_am, true))}</span></li>`).join("")}</ul></details>` : ""}
      ${opts.knoepfe ? `<div class="btn-row">
        <button type="button" class="btn secondary small" data-v-edit="${v.id}">Bearbeiten</button>
        ${istLetzter ? `<button type="button" class="btn secondary small" data-v-medien="${v.id}">📷 Medien hinzufügen</button>
          ${darfLeiten() ? `<button type="button" class="btn danger small" data-v-del="${v.id}">Versuch löschen</button>` : ""}` : ""}
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
        <div class="su-knoepfe"><button type="button" class="btn" data-su="start">▶ Start</button>
          <button type="button" class="btn secondary" data-su="stopp" disabled>■ Stopp</button>
          <button type="button" class="btn ghost" data-su="reset">Zurücksetzen</button></div>
        <div class="su-hinweis"></div></div>` : ""}
      <label for="bw-zeit">Zeit (mm:ss oder 230 für 2:30)</label>
      <div class="zeit-zeile"><input type="text" id="bw-zeit" class="zeitfeld" inputmode="numeric" placeholder="mm:ss" autocomplete="off"
             value="${v.zeit_sekunden != null ? fmtZeit(v.zeit_sekunden) : ""}">
        <span class="help">${l.zeitansatz_sekunden != null ? "„Stopp“ trägt die gemessene Zeit ein – sie lässt sich hier korrigieren." : "Ohne Zeitansatz, aber die Zeit darf trotzdem notiert werden."}</span></div>
      <label>Bewertung</label>
      <div class="bew-wahl" id="bw-wahl">
        <button type="button" data-erg="bestanden" class="${v.ergebnis === "bestanden" ? "sel" : ""}" aria-pressed="${v.ergebnis === "bestanden"}"><span class="sym" aria-hidden="true">👍</span> bestanden</button>
        <button type="button" data-erg="mangelhaft" class="${v.ergebnis === "mangelhaft" ? "sel" : ""}" aria-pressed="${v.ergebnis === "mangelhaft"}"><span class="sym" aria-hidden="true">👎</span> mangelhaft</button>
      </div>
      <div class="feld-kopf"><label for="bw-komm" id="bw-komm-label">${v.ergebnis === "mangelhaft" ? "Kommentar (Pflicht bei mangelhaft)" : "Kommentar"}</label>${diktatKnopf("bw-komm")}</div>
      <textarea id="bw-komm" placeholder="Was war gut, was hat gefehlt? Bei mangelhaft: die Fehler für das Feedbackgespräch.">${esc(v.kommentar)}</textarea>
      ${diktatHinweis()}
      <label>Medien</label>
      <button type="button" class="btn secondary medien-knopf" id="bw-medien-knopf">📷 Foto/Video aufnehmen oder wählen</button>
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
      if (wahl) { wahl.scrollIntoView({ behavior: "smooth", block: "center" }); const b = wahl.querySelector("button"); if (b) b.focus({ preventScroll: true }); }
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
          } catch (e) { b.disabled = false; toast(e.message, true); }
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
        pflichtZeigen();
      });
      komm.addEventListener("input", () => { if (komm.value.trim()) komm.classList.remove("fehler"); });
      zeitfeld.addEventListener("input", () => zeitfeld.classList.remove("fehler"));

      // Medien auswählen: Vorschau, Größe, einzeln entfernbar. Die Dateien liegen im Speicher,
      // bis die Bewertung gespeichert ist – erst dann gibt es einen Versuch, zu dem sie gehören.
      let dateien = [];
      const liste = $("#bw-medien-liste", form), inp = $("#bw-dateien", form);
      const listeZeichnen = () => {
        liste.innerHTML = dateien.map((f, i) => {
          let vorschau = '<span class="video-icon" aria-hidden="true">🎬</span>';
          if (!isVideo(f)) { const u = URL.createObjectURL(f); urls.push(u); vorschau = `<img src="${u}" alt="">`; }
          return `<li>${vorschau}<span class="name">${esc(f.name)}<small>${groesseText(f.size)}${isVideo(f) ? " · Video" : ""}</small></span>
            <button type="button" class="btn ghost small" data-weg="${i}" aria-label="Entfernen" title="Entfernen">✕</button></li>`;
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
        if (!erg) { wahl.scrollIntoView({ block: "center" }); return toast("Bitte 👍 bestanden oder 👎 mangelhaft wählen.", true); }
        // Läuft die Stoppuhr noch und ist das Zeitfeld leer, gilt die gemessene Zeit – wer
        // direkt speichert, hat das Stoppen nur übersprungen, nicht die Messung verworfen.
        const laufend = suLesen();
        if (laufend && laufend.tid === tid && laufend.lid === lid && !zeitfeld.value.trim()) {
          zeitfeld.value = fmtZeit(Math.round((Date.now() - laufend.start) / 1000));
        }
        const z = zeitLesen(zeitfeld.value);
        if (!z.ok) { zeitfeld.classList.add("fehler"); zeitfeld.focus(); return toast("Zeit bitte als mm:ss angeben, z. B. 02:30 – oder nur Ziffern: 230.", true); }
        const kommentar = komm.value.trim();
        // Pflichtkommentar schon hier – der Server prüft es ebenfalls (siehe catch unten).
        if (erg === "mangelhaft" && !kommentar) { komm.classList.add("fehler"); komm.focus(); return toast("Bei „mangelhaft“ ist ein Kommentar Pflicht.", true); }
        knopf.disabled = true;
        try {
          let versuch;
          if (modus.art === "edit") {
            versuch = (await api(`${API}/versuche/${modus.versuch.id}`, { method: "PUT", body: { ergebnis: erg, zeit_sekunden: z.wert, kommentar } })).versuch;
          } else {
            versuch = (await api(`${API}/teilnehmer/${tid}/leistungen/${lid}/versuche`,
              { method: "POST", body: { ergebnis: erg, zeit_sekunden: z.wert, kommentar, nachpruefung: modus.art === "np" } })).versuch;
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
          if (/Kommentar/i.test(e.message)) { komm.classList.add("fehler"); komm.focus(); }
          toast(e.message, true);
        } finally { knopf.disabled = false; }
      };
      if (modus.art === "np" || modus.art === "edit") $("#bw-form-titel", form).scrollIntoView({ block: "start" });
    }, ["pruef-dlg"]);
  }

  /* --- Reiter Mängel / Feedback ------------------------------------------------------------ */
  function maengelHtml(lg) {
    const tns = lg.teilnehmer || [], ls = lg.leistungen || [];
    return `<div class="reiter-kopf"><h2>Mängel / Feedback</h2></div>
      <div class="maengel-filter">
        <div><label for="mf-tn">Teilnehmende:r</label><select id="mf-tn"><option value="">Alle</option>${tns.map((t) => `<option value="${t.id}" ${String(t.id) === String(state.mf.teilnehmer) ? "selected" : ""}>${esc(tnName(t))}</option>`).join("")}</select></div>
        <div><label for="mf-l">Prüfungsleistung</label><select id="mf-l"><option value="">Alle</option>${ls.map((l) => `<option value="${l.id}" ${String(l.id) === String(state.mf.leistung) ? "selected" : ""}>${esc(l.bezeichnung)}</option>`).join("")}</select></div>
        <label class="inline"><input type="checkbox" id="mf-offen" ${state.mf.nur_offen ? "checked" : ""}> nur offene Mängel</label>
        <div class="btn-row knoepfe"><button class="btn secondary small" data-act="m-druck">Druckansicht</button>
          <button class="btn secondary small" data-act="m-alle" id="mf-alle" ${state.mf.teilnehmer ? "" : "disabled"} title="Alle Bewertungen der gewählten Person, auch die bestandenen">Alle Bewertungen</button></div>
      </div>
      <div id="maengel-liste"><p class="help">Wird geladen …</p></div>`;
  }

  function maengelBinden() {
    const tn = $("#mf-tn"), l = $("#mf-l"), offen = $("#mf-offen");
    const neu = () => { state.mf = { teilnehmer: tn.value, leistung: l.value, nur_offen: offen.checked }; $("#mf-alle").disabled = !tn.value; maengelLaden(); };
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
        ${v.zeit_sekunden != null || m.leistung.zeitansatz_sekunden != null ? `<span class="zeit">⏱ ${v.zeit_sekunden != null ? fmtZeit(v.zeit_sekunden) : "–"}${m.leistung.zeitansatz_sekunden != null ? ` (Soll ${fmtZeit(m.leistung.zeitansatz_sekunden)})` : ""}</span>` : ""}
        <span class="${npKlasse}">${npText}</span></div>
      ${v.kommentar ? `<div class="kommentar">${esc(v.kommentar)}</div>` : '<div class="kommentar muted">Kein Kommentar.</div>'}
      ${medienGridHtml(v.medien, { klein: !!opts.druck })}
      <div class="abnahme">abgenommen von ${esc(v.geprueft_von_name)} am ${esc(fmtDate(v.geprueft_am, true))}${bearbeitet}</div>
      ${opts.druck ? "" : `<div class="btn-row">
        ${m.nachpruefung_status === "offen" ? `<button class="btn small" data-act="m-np" data-tid="${m.teilnehmer.id}" data-lid="${m.leistung.id}">Nachprüfung durchführen</button>` : ""}
        <button class="btn ghost small" data-act="zelle" data-tid="${m.teilnehmer.id}" data-lid="${m.leistung.id}">Alle Versuche</button></div>`}
    </div>`;
  }

  function maengelGruppenHtml(maengel, opts = {}) {
    if (!maengel.length) return `<div class="leer"><strong>Keine Mängel${opts.nurOffen ? " offen" : ""}</strong>${opts.nurOffen ? "Alles, was mangelhaft war, wurde nachgeprüft – oder es gab nichts zu beanstanden." : "Zu dieser Auswahl gibt es keine mangelhaften Bewertungen."}</div>`;
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
          ${v.zeit_sekunden != null ? `<span class="zeit">⏱ ${fmtZeit(v.zeit_sekunden)}${soll(v.leistung_id) != null ? ` <span class="muted">(Soll ${fmtZeit(soll(v.leistung_id))})</span>` : ""}</span>` : ""}</div>
        ${v.kommentar ? `<div class="kommentar">${esc(v.kommentar)}</div>` : ""}
        ${medienGridHtml(v.medien)}
        <div class="abnahme">abgenommen von ${esc(v.geprueft_von_name)} am ${esc(fmtDate(v.geprueft_am, true))}${v.bearbeitet_am ? ` · bearbeitet von ${esc(v.bearbeitet_von_name)} am ${esc(fmtDate(v.bearbeitet_am, true))}` : ""}</div>
      </div>`).join("") : '<p class="muted">Noch keine Bewertungen.</p>'}`;
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
      <div class="dlg-actions"><button class="btn" data-close type="button">Schließen</button></div>`,
      undefined, ["pruef-dlg"]);
  }

  /* --- Druckansicht --------------------------------------------------------------------------- */
  // Welche Druckansicht gemeint ist, sagt ?ansicht= in der Adresse – „tn“ für eine Person mit
  // allen ihren Leistungen, sonst (auch ohne den Parameter, für alte Verweise) die Mängelübersicht.
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
    const filter = [tn ? `Teilnehmende:r: ${tnName(tn)}` : "alle Teilnehmenden", l ? `Leistung: ${l.bezeichnung}` : "alle Leistungen", mf.nur_offen ? "nur offene Mängel" : "alle mangelhaften Bewertungen"];
    root.innerHTML = `<div class="druck-kopf"><h1>Mängelübersicht – ${esc(lg.titel)}</h1>
        <button class="btn no-print" id="druck-los" type="button">🖨 Drucken</button>
        <div class="druck-filter">${esc([spanne(lg.datum_von, lg.datum_bis), lg.ort, lg.nummer ? `Nr. ${lg.nummer}` : ""].filter(Boolean).join(" · "))}<br>${esc(filter.join(" · "))} · Stand ${esc(fmtDate(new Date().toISOString(), true))}</div></div>
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
    root.innerHTML = `<div class="druck-kopf"><h1>Prüfungsleistungen – ${esc(tnName(tn))}</h1>
        <button class="btn no-print" id="druck-los" type="button">🖨 Drucken</button>
        <div class="druck-filter">${esc([lg.titel, spanne(lg.datum_von, lg.datum_bis), lg.ort].filter(Boolean).join(" · "))}<br>
          ${esc(tn.gliederung || "")}${tn.gliederung ? " · " : ""}${plural(versuche.length, "Bewertung", "Bewertungen")}${tn.ergebnis ? ` · Lehrgang ${ERGEBNIS[tn.ergebnis][0]}` : ""} · Stand ${esc(fmtDate(new Date().toISOString(), true))}</div></div>
      <div class="tn-block-kopf">${tnBildHtml(tn, "gross")}${schlossHtml(tn)}<span class="tn-name">${esc(tnName(tn))}</span>${tn.gliederung ? `<span class="muted tn-gliederung">${esc(tn.gliederung)}</span>` : ""}</div>
      ${bewertungenListeHtml(tn, versuche, soll)}`;
    $("#druck-los").onclick = () => window.print();
  }

  /* ==========================================================================================
     Excel-Import: Datei → Vorschau → Zuordnung korrigieren → Übernehmen
     ========================================================================================== */
  const ZUORDNUNG = [["vorname", "Vorname"], ["name", "Nachname"], ["geburtsdatum", "Geburtsdatum"], ["gliederung", "Gliederung"],
    ["email", "E-Mail"], ["rolle", "Rolle"], ["bemerkung", "Bemerkung"], ["extra", "Weitere Angabe"], ["voraussetzung", "Voraussetzung"], ["ignorieren", "Ignorieren"]];

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

    const schrittDatei = () => {
      dialogOeffnen(`<h2>Import</h2>
        <p class="help">${lehrgang ? `Teilnehmende und Voraussetzungen in „${esc(lehrgang.titel)}“ übernehmen. Bestehende Teilnehmende (gleicher Name, ggf. Geburtsdatum) werden aktualisiert, nicht doppelt angelegt.`
          : "Aus einer Excel-Teilnehmerliste (.xlsx) wird ein neuer Lehrgang mit Teilnehmenden und Voraussetzungen angelegt. Vorher gibt es eine Vorschau."}</p>
        <p class="help import-isc">Die Stammdaten der Teilnehmenden lassen sich aus dem ISC übernehmen: Dort unter
          <strong>Dokumente → Checkliste Voraussetzungen (Excel)</strong> die Option <strong>„Allgemeine Lehrgangsinformationen mit ausgeben“</strong>
          wählen und die erzeugte Excel-Datei hier hochladen.</p>
        <div class="import-schritt import-datei">
          <label for="imp-datei">Datei (.xlsx)</label>
          <input type="file" id="imp-datei" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet">
          ${datei ? `<div class="help">Gewählt: ${esc(datei.name)}</div>` : ""}
          <div class="help">Kopfzeilen über der Tabelle, verbundene Zellen und Leerzeilen am Ende sind kein Problem. Spalten mit „ja/nein“ oder Daten werden als Voraussetzungen erkannt.</div>
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
        <h3>Spalten und Zuordnung</h3>
        <p class="help">Die Zuordnung wurde aus den Spaltentiteln erkannt und lässt sich hier korrigieren – die Vorschau rechnet dann neu.</p>
        <table class="import-spalten"><thead><tr><th>Spalte</th><th>Beispiele</th><th>Zuordnung</th></tr></thead>
          <tbody>${(v.spalten || []).map((s) => `<tr>
            <td class="titel">${esc(s.titel) || '<span class="muted">(ohne Titel)</span>'}</td>
            <td class="beispiele">${esc((s.beispiele || []).join(", "))}</td>
            <td><select data-spalte="${s.index}" aria-label="Zuordnung für ${esc(s.titel)}">${ZUORDNUNG.map(([k, t]) => `<option value="${k}" ${s.zuordnung === k ? "selected" : ""}>${t}</option>`).join("")}</select></td>
          </tr>`).join("")}</tbody></table>
        <div class="import-zahlen">
          <span><b>${tn.length}</b> Teilnehmende erkannt${vorhanden ? ` <span class="muted">(davon ${vorhanden} bereits vorhanden → werden aktualisiert)</span>` : ""}</span>
          <span><b>${(v.ausbilder || []).length}</b> Referierende erkannt</span>
          <span><b>${vor.length}</b> Voraussetzungen${vorAlt ? ` <span class="muted">(${vorAlt} schon vorhanden)</span>` : ""}</span>
        </div>
        ${(v.warnungen || []).length ? `<div class="notice import-warnungen"><strong>Hinweise</strong><ul>${v.warnungen.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : ""}
        ${tn.length ? `<h3>Vorschau (${Math.min(8, tn.length)} von ${tn.length})</h3>
          <div class="table-scroll"><table class="import-vorschau"><thead><tr><th>Name</th><th>Vorname</th><th>Geburtsdatum</th><th>Gliederung</th><th>Voraussetzungen erfüllt</th></tr></thead>
          <tbody>${tn.slice(0, 8).map((t) => `<tr class="${t.vorhanden ? "vorhanden" : ""}"><td>${esc(t.name)}${t.vorhanden ? ' <span class="badge grey">vorhanden</span>' : ""}</td><td>${esc(t.vorname)}</td>
            <td>${esc(fmtTag(t.geburtsdatum))}</td><td>${esc(t.gliederung)}</td><td>${Object.values(t.voraussetzungen || {}).filter(Boolean).length} / ${vor.length}</td></tr>`).join("")}</tbody></table></div>` : ""}
        ${(v.ausbilder || []).length ? `<p class="help">Referierende: ${v.ausbilder.map((a) => `${esc(a.name)}${a.funktion ? ` (${esc(a.funktion)})` : ""}`).join(", ")}</p>` : ""}
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
              const meldung = `Import: ${r.angelegt} angelegt, ${r.aktualisiert} aktualisiert, ${r.voraussetzungen_neu} neue Voraussetzungen, ${r.ausbilder_neu} neue Referierende`
                + ((r.warnungen || []).length ? ` – ${plural(r.warnungen.length, "Hinweis", "Hinweise")}` : "");
              if (!lehrgang) {
                const diff = {};
                Object.entries(felder).forEach(([k, val]) => { if ((val || "") !== (lg[k] || "")) diff[k] = val; });
                if (Object.keys(diff).length) {
                  try { await api(`${API}/lehrgaenge/${lg.id}`, { method: "PUT", body: diff }); } catch (e) { toast(e.message, true); }
                }
                meldungMerken(meldung);
                location.href = `/pruefungen/${lg.id}#teilnehmer`;
                return;
              }
              dlg.close();
              toast(meldung);
              await loadDetail(); renderLehrgangSeite();
            } catch (e) { knopf.disabled = false; toast(e.message, true); }
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
    if (tab) { location.hash = "#" + tab.dataset.reiter; return; }
    const b = e.target.closest("[data-act]");
    if (!b) return;
    const act = b.dataset.act, id = +b.dataset.id, tid = +b.dataset.tid, lid = +b.dataset.lid;
    const lgAus = (x) => (ANSICHT === "liste" ? state.liste.find((l) => l.id === x) : state.lehrgang);
    try {
      switch (act) {
        case "lg-neu": return lehrgangDialog(null, (lg) => { location.href = `/pruefungen/${lg.id}#leistungen`; });
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
          location.href = `/pruefungen/${su.lehrgang}#bewertung`;
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
        case "bew-tn-druck": window.open(`/pruefungen/${LEHRGANG_ID}/druck?ansicht=tn&teilnehmer=${state.bewTn}`, "_blank", "noopener"); return;
        case "zelle": return bewertungsDialog(tid, lid);
        case "m-np": return bewertungsDialog(tid, lid, { nachpruefung: true });
        case "m-alle": return state.mf.teilnehmer ? alleBewertungenDialog(+state.mf.teilnehmer) : toast("Bitte zuerst eine Person wählen.", true);
        case "m-druck": window.open(`/pruefungen/${LEHRGANG_ID}/druck?${maengelQuery(state.mf)}`, "_blank", "noopener"); return;
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
        root.innerHTML = `<a class="zurueck" href="/pruefungen/kataloge">← Alle Kataloge</a><p class="notice">${esc(e.status === 404 ? "Diesen Katalog gibt es nicht (mehr)." : "Der Katalog ließ sich nicht laden: " + e.message)}</p>`;
        return;
      }
      return renderKatalogSeite();
    }
    if (!LEHRGANG_ID) { root.innerHTML = '<p class="notice">Kein Lehrgang angegeben.</p>'; return; }
    if (ANSICHT === "druck") return renderDruck();
    state.reiter = reiterAusHash();
    try { await loadDetail(); }
    catch (e) {
      root.innerHTML = `<a class="zurueck" href="/pruefungen">← Alle Lehrgänge</a><p class="notice">${esc(e.status === 404 ? "Diesen Lehrgang gibt es nicht (mehr)." : "Der Lehrgang ließ sich nicht laden: " + e.message)}</p>`;
      return;
    }
    renderLehrgangSeite();
  }
  start().catch((e) => toast(e.message, true));
})();
