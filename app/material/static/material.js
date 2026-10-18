/* Modul Material – Oberfläche aller Ansichten: Übersicht, fällige Prüfungen, Bestand (Ordnerbaum mit
   Systemordnern und Mehrfachauswahl), Artikel mit Lebenslauf (Prüfungen und Journal), Artikel anlegen,
   Prüfung (Formular fürs Telefon), Prüfdurchgang, Katalog mit Produkten, Dokumenten und Prüfformularen,
   Suche nach Nummern; links die Ordnerleiste.
   Welche Ansicht gemeint ist, sagt data-ansicht am <main>; was das Konto darf, data-darf. Ausgeblendet
   wird nur, was ohnehin scheitern würde – der Server prüft jede Aktion selbst. */
(function () {
  const { esc, api, toast, dialog, confirm } = S;
  const root = document.getElementById("mat");
  if (!root) return;
  const ANSICHT = root.dataset.ansicht || "dashboard";
  const DATEN = JSON.parse(root.dataset.daten || "{}");
  const DARF = JSON.parse(root.dataset.darf || "{}");
  const inhalt = document.getElementById("mat-inhalt");
  const API = "/api/material";
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  /* --- Großansicht für Fotos -------------------------------------------------------------------------
     Ein Klick auf ein Foto (Mangelfoto, Produktbild, Meldungsfoto) zeigt es groß über der Seite statt in einem neuen
     Tab; mit Strg/⌘ oder der mittleren Maustaste öffnet der Link wie gewohnt einen Tab. Gezeigt wird die Webfassung
     (gedreht, auch bei HEIC vom iPhone), „Original“ führt zur hochgeladenen Datei. Stehen mehrere Fotos zusammen
     (data-gruppe, etwa alle Fotos einer Prüfung), blättern Pfeiltasten und Pfeilknöpfe. */
  const bildLink = (web, original, titel, gruppe, bildHtml) => `<a class="mat-bildlink" href="${esc(original || web)}"
    target="_blank" rel="noopener" data-web="${esc(web)}" data-titel="${esc(titel || "")}"${gruppe ? ` data-gruppe="${esc(gruppe)}"` : ""}
    aria-label="${esc(titel ? `Foto groß zeigen: ${titel}` : "Foto groß zeigen")}">${bildHtml}</a>`;

  function bildZeigen(link) {
    const gruppe = link.dataset.gruppe;
    const liste = gruppe ? $$(`a.mat-bildlink[data-gruppe="${CSS.escape(gruppe)}"]`) : [link];
    let i = Math.max(0, liste.indexOf(link));
    const vorher = document.activeElement;
    const box = document.createElement("div");
    box.className = "md-lightbox mat-lightbox";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Foto");
    box.innerHTML = `<button type="button" class="md-lightbox-close" aria-label="Schließen">×</button>
      ${liste.length > 1 ? `<button type="button" class="mat-lb-pfeil zurueck" aria-label="Vorheriges Foto">‹</button>
        <button type="button" class="mat-lb-pfeil weiter" aria-label="Nächstes Foto">›</button>` : ""}
      <figure><img alt=""><figcaption><span class="mat-lb-titel"></span>
        <a class="mat-lb-original" target="_blank" rel="noopener">Original</a><span class="mat-lb-zahl"></span></figcaption></figure>`;
    const img = $("img", box);
    const zeige = () => {
      const l = liste[i];
      img.src = l.dataset.web || l.href;
      img.alt = l.dataset.titel || "Foto";
      $(".mat-lb-titel", box).textContent = l.dataset.titel || "";
      $(".mat-lb-original", box).href = l.href;
      $(".mat-lb-zahl", box).textContent = liste.length > 1 ? `${i + 1} von ${liste.length}` : "";
    };
    const blaettern = (d) => { i = (i + d + liste.length) % liste.length; zeige(); };
    const taste = (e) => {
      if (e.key === "Escape") { e.preventDefault(); schliessen(); }
      else if (e.key === "ArrowRight" && liste.length > 1) blaettern(1);
      else if (e.key === "ArrowLeft" && liste.length > 1) blaettern(-1);
    };
    function schliessen() {
      box.remove();
      document.removeEventListener("keydown", taste);
      if (vorher && vorher.focus) vorher.focus({ preventScroll: true });
    }
    box.addEventListener("click", (e) => {
      const pfeil = e.target.closest(".mat-lb-pfeil");
      if (pfeil) { blaettern(pfeil.classList.contains("zurueck") ? -1 : 1); return; }
      if (e.target === img || e.target.closest("figcaption")) return;     // „Original“ öffnet seinen Tab
      schliessen();
    });
    document.addEventListener("keydown", taste);
    document.body.appendChild(box);
    zeige();
    $(".md-lightbox-close", box).focus();
  }
  document.addEventListener("click", (e) => {
    const l = e.target.closest("a.mat-bildlink");
    if (!l || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    bildZeigen(l);
  });

  const STATUS = { einsatzbereit: "einsatzbereit", bald_faellig: "bald fällig", ueberfaellig: "überfällig", neu: "neu",
                   gesperrt: "gesperrt", lebensdauer: "Lebensdauer erreicht", ausgesondert: "ausgesondert" };
  const PRUEFART = { eingang: "Eingangsprüfung", periodisch: "periodische Prüfung", ausserplanmaessig: "außerplanmäßige Prüfung",
                     reparatur: "Prüfung nach Reparatur", aussonderung: "Aussonderung" };
  const PRUEFART_KURZ = { eingang: "Eingangsprüfung", periodisch: "periodisch", ausserplanmaessig: "außerplanmäßig",
                          reparatur: "Reparatur", aussonderung: "Aussonderung" };
  const ERGEBNIS = { einsatzbereit: "einsatzbereit", instandsetzen: "instandsetzen", aussondern: "aussondern" };
  const BEFUND = { ok: "in Ordnung", mangel: "Mangel", nicht_zutreffend: "nicht zutreffend" };
  const ANHANGART = { externes_pruefformular: "externes Prüfformular", pruefbericht: "Prüfbericht", foto: "Foto", sonstiges: "Sonstiges" };
  const SPERRGRUND = { sturz: "Sturzbelastung", beschaedigung: "Beschädigung", verlust: "Verlust", rueckruf: "Rückruf" };
  const AUSSONDERUNGSGRUND = { lebensdauer: "Lebensdauer erreicht", verlust: "Verlust", irreparabel: "irreparabel" };
  const MATERIALART = { textil: "textil", metall_hardware: "Metall", sonstiges: "sonstiges" };
  const ORDNERART = { gliederung: "Gliederung", standort: "Standort", fahrzeug: "Fahrzeug", set: "Set",
                      persoenlich: "persönlich", sonstiges: "sonstiges" };
  const DOKART = { produktbild: "Produktbild", konformitaetserklaerung: "Konformitätserklärung",
                   gebrauchsanleitung: "Gebrauchsanleitung", pruefanweisung: "Prüfanweisung", pflegehinweis: "Pflegehinweis",
                   datenblatt: "Datenblatt", sonstiges: "Sonstiges" };
  const EDITOR = { yesno: "Ja/Nein", text: "Text", date: "Datum", number: "Zahl", photo: "Foto", signature: "Unterschrift" };
  // Feldnamen für das Journal – was nicht hier steht, erscheint mit seinem technischen Namen.
  const FELD = {
    manufacturer: "Hersteller", model: "Modell", article_no: "Artikelnummer", norm: "Norm", material_kind: "Materialart",
    interval_months: "Prüfintervall (Monate)", lifetime_years: "Lebensdauer (Jahre)", lifetime_source: "Fundstelle Lebensdauer",
    description: "Beschreibung", category_id: "Kategorie", image: "Bild", serial_no: "Seriennummer",
    serial_generated: "Seriennummer vom System", inventory_no: "Inventarnummer", manufactured_on: "Herstellung",
    purchased_on: "Kauf", first_use_on: "Erstgebrauch", retire_by: "Lebensende", next_due_on: "Nächste Prüfung",
    notes: "Bemerkung", folder_id: "Ordner", ordner: "Ordner", product_id: "Produkt", name: "Name", kind: "Art",
    parent_id: "Oberordner", pfad: "Ablage", photo: "Foto", title: "Titel", version: "Version", valid_from: "Gültig ab",
    withdrawn_on: "Zurückgezogen ab", active: "Aktiv", punkte: "Prüfpunkte", default_material_kind: "Materialart (Vorgabe)",
    default_interval_months: "Prüfintervall (Vorgabe)", default_lifetime_years: "Lebensdauer (Vorgabe)",
    recht_material: "Stufe Material", mat_pruefer: "Prüfer", mat_katalog: "Katalogpfleger", urkundennummer: "Urkundennummer",
    system_kind: "Systemordner", url: "Adresse", file_path: "Datei", sha256: "SHA-256", size: "Größe",
    lock_state: "Sperrzustand", lock_reason: "Grund der Sperre", origin_folder_id: "Herkunftsordner", herkunft: "Herkunftsordner",
    last_inspected_on: "Zuletzt geprüft", pruefung: "Prüfung", ergebnis: "Ergebnis", art: "Art", grund: "Grund", datum: "Datum",
    aussonderung: "Aussonderung",
    pruefer: "Prüfer", result: "Ergebnis", inspected_on: "Prüftag", reason: "Grund", maengel: "Mängel", item_id: "Artikel Nr.",
    round_id: "Durchgang Nr.", form_id: "Formular Nr.", form_version: "Formularversion", inspector_name: "Prüfer",
    begonnen: "begonnen", seiten: "Seiten", dateien: "Dateien", basis: "aus Prüfung", erledigt: "erledigt", ausgenommen: "ausgenommen",
    links: "Links", fotos: "Fotos", note: "Bemerkung", answer: "Antwort", status: "Status",
    von: "Kopie von Produkt Nr.", kopie_von: "Kopie von Dokument Nr.", dokumente: "Dokumente übernommen",
    protocol_id: "Protokoll-ID", pdf_sha256: "Prüfsumme", pdf_hashed_bytes: "Bytes", file_sha256: "Prüfsumme der Datei",
    anhaenge_angefuegt: "Anhänge angefügt", login: "Anmeldung", berichtigung: "Berichtigung", berichtigt: "berichtigt",
    unterschrift: "Unterschrift", nicht_geprueft: "nicht geprüft", uid: "Katalogkennung",
    rueckruf: "Rückruf Nr.", serials: "Seriennummern", mail: "Mail an Materialwarte und Prüfer", close_note: "Vermerk",
  };
  const AKTION = { angelegt: "angelegt", geaendert: "geändert", geloescht: "gelöscht", verschoben: "verschoben",
                   bild: "Bild geändert", foto: "Foto geändert", neue_version: "neue Version", zurueckgezogen: "zurückgezogen",
                   aktiviert: "aktiviert", deaktiviert: "deaktiviert", lebensende: "Lebensende nachgezogen", rollen: "Rollen",
                   begonnen: "Prüfung begonnen", abgeschlossen: "Prüfung abgeschlossen", verworfen: "Prüfung verworfen",
                   reservierung_freigegeben: "Reservierung freigegeben", geprueft: "geprüft", freigeprueft: "freigeprüft",
                   gesperrt: "gesperrt", ausgesondert: "ausgesondert", anhang: "Anhang", anhang_entfernt: "Anhang entfernt",
                   eroeffnet: "Durchgang eröffnet", ausgenommen: "ausgenommen", einbezogen: "wieder einbezogen",
                   geschlossen: "Durchgang abgeschlossen", faelligkeit: "Fälligkeit vorgezogen", umbenannt: "umbenannt",
                   eingepflegt: "eingepflegt", abgelehnt: "abgelehnt", variante: "als Variante angelegt",
                   festgeschrieben: "festgeschrieben", berichtigt: "berichtigt", berichtigung_begonnen: "Berichtigung begonnen",
                   unterschrift: "Unterschrift geändert", urkundennummer: "Urkundennummer geändert",
                   abgebrochen: "Durchgang abgebrochen", rueckruf: "Rückruf angelegt", rueckruf_beendet: "Rückruf beendet" };
  const ENTITAET = { item: "Artikel", product: "Produkt", document: "Dokument", form: "Formular", folder: "Ordner",
                     category: "Kategorie", user: "Konto", inspection: "Prüfung", round: "Durchgang", request: "Produktmeldung" };

  /* Warum hier nicht geprüft werden kann (DARF.pruefen ist false) – als HTML. Das Häkchen „Prüfer“ setzt die
     Verwaltung in der Nutzerverwaltung, die Urkundennummer trägt der Prüfer selbst im Profil ein. Wer das Häkchen
     schon hat, dem fehlt nur die Nummer: Er bekommt den Weg dorthin als Link. */
  const URKUNDE_IM_PROFIL = 'Du bist als Prüfer eingetragen, aber deine Urkundennummer fehlt noch – trage sie im '
    + '<a href="/profil#unterschrift">Profil unter „Urkundennummer und Unterschrift“</a> ein, dann kannst du prüfen.';
  const pruefHinweis = () => DARF.pruefer_haekchen ? URKUNDE_IM_PROFIL
    : "Prüfen dürfen nur Prüfer mit Urkundennummer: Das Häkchen „Prüfer“ setzt die Verwaltung in der Nutzerverwaltung, "
      + "die Urkundennummer trägt der Prüfer selbst in seinem Profil ein.";

  // „2026-12-04“ → „04.12.2026“, „2026-12“ → „12/2026“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const fmtTag = (d) => {
    const s = String(d || "");
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}.${m[2]}.${m[1]}`;
    m = s.match(/^(\d{4})-(\d{2})$/);
    return m ? `${m[2]}/${m[1]}` : s;
  };
  const fmtZeit = (iso) => S.fmtDate(iso, true);

  /* Datumsfelder auf Deutsch: Textfelder statt der Datumsfelder des Browsers – die zeigen das Format seiner
     Sprache (in einem englischen Browser mm/dd/yyyy). Monat: MM/JJJJ, Tag: TT.MM.JJJJ; gespeichert wird ISO. */
  const datumAnzeige = (iso, art) => {
    const m = String(iso || "").match(/^(\d{4})-(\d{2})(?:-(\d{2}))?$/);
    if (!m) return "";
    return art === "monat" || !m[3] ? `${m[2]}/${m[1]}` : `${m[3]}.${m[2]}.${m[1]}`;
  };
  const datumFeld = (id, iso, art) => `<input type="text" id="${id}" class="mat-datum" data-art="${art}" inputmode="numeric" autocomplete="off"
    maxlength="${art === "monat" ? 7 : 10}" placeholder="${art === "monat" ? "MM/JJJJ" : "TT.MM.JJJJ"}" value="${esc(datumAnzeige(iso, art))}">`;
  // ISO ('YYYY-MM' bzw. 'YYYY-MM-DD'), "" für leer – oder ein Fehler mit Hinweis aufs Format.
  function datumWert(feld, name) {
    const s = feld.value.trim();
    if (!s) return "";
    if (feld.dataset.art === "monat") {
      const m = s.match(/^(\d{1,2})[/.](\d{4})$/);
      if (m && +m[1] >= 1 && +m[1] <= 12) return `${m[2]}-${m[1].padStart(2, "0")}`;
      throw new Error(`„${name}“: bitte als MM/JJJJ angeben, z. B. 03/2024.`);
    }
    const m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m) {
      const d = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
      if (d.getUTCFullYear() === +m[3] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[1]) {
        return `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
      }
    }
    throw new Error(`„${name}“: bitte als TT.MM.JJJJ angeben, z. B. 17.03.2024.`);
  }
  // Beim Tippen die Trenner setzen („032024“ → „03/2024“, „17032024“ → „17.03.2024“), beim Verlassen vereinheitlichen.
  document.addEventListener("input", (e) => {
    const f = e.target;
    if (!f.classList || !f.classList.contains("mat-datum") || e.inputType !== "insertText") return;
    if (/[/.][/.]$/.test(f.value)) { f.value = f.value.slice(0, -1); return; }    // Trenner selbst getippt – steht schon da
    if (f.dataset.art === "monat" ? /^\d{2}$/.test(f.value) : /^\d{2}$|^\d{1,2}\.\d{2}$/.test(f.value)) {
      f.value += f.dataset.art === "monat" ? "/" : ".";
    }
  });
  document.addEventListener("change", (e) => {
    const f = e.target;
    if (!f.classList || !f.classList.contains("mat-datum")) return;
    try { f.value = datumAnzeige(datumWert(f, ""), f.dataset.art); f.classList.remove("ungueltig"); }
    catch (err) { f.classList.add("ungueltig"); }
  }, true);
  const plural = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;
  const statusMarke = (s, gross) => `<span class="mat-status s-${esc(s)}${gross ? " gross" : ""}">${esc(STATUS[s] || s)}</span>`;
  const demoMarke = (x) => (x ? '<span class="mat-demo" title="DEMO – nicht für echte Prüfungen">DEMO</span>' : "");
  const leer = (text) => `<p class="mat-leer">${esc(text)}</p>`;
  const produktName = (p) => `${p.manufacturer || ""} ${p.model || ""}`.trim();
  const fokus = (el) => { if (el && !window.matchMedia("(pointer: coarse)").matches) el.focus(); };
  const EIN = "\u00a0\u00a0\u00a0";          // Einrückung je Ebene in Auswahllisten
  const groesse = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round((b || 0) / 1024))} kB`);

  /* --- Gerüst -------------------------------------------------------------------------------- */
  const NAV = { dashboard: "dashboard", pruefungen: "pruefungen", bestand: "bestand", ordner: "bestand", artikel: "bestand",
                artikel_neu: "bestand", katalog: "katalog", produkt: "katalog", formular: "katalog", meldungen: "katalog", suche: "",
                pruefung: "pruefungen", pruefung_neu: "pruefungen", durchgang: "pruefungen" };
  $$(".mat-nav a").forEach((a) => a.classList.toggle("aktiv", a.dataset.nav === NAV[ANSICHT]));
  if (ANSICHT === "suche" && DATEN.q) $(".mat-suche input").value = DATEN.q;
  if (!DARF.lesen) $$('.mat-nav a:not([data-nav="katalog"]), .mat-suche').forEach((el) => el.remove());

  // Klicks auf [data-act] gehen an die Aktionen der gerade gezeichneten Ansicht.
  let aktionen = {};
  inhalt.addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    if (!b || !inhalt.contains(b) || !aktionen[b.dataset.act]) return;
    if (b.tagName === "A" || b.tagName === "BUTTON") e.preventDefault();
    aktionen[b.dataset.act](b, e);
  });

  // Ein Textfeld so hoch wie sein Inhalt – lange Prüfanweisungen bleiben ganz lesbar. Ändert sich die Breite
  // (Fenster, Telefon gedreht), rechnen alle sichtbaren neu.
  function textHoehe(ta) {
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight + ta.offsetHeight - ta.clientHeight}px`;
  }
  let hoeheLos = null;
  window.addEventListener("resize", () => { clearTimeout(hoeheLos); hoeheLos = setTimeout(() => $$("textarea.fp-text").forEach(textHoehe), 150); });

  /* --- Leiste links --------------------------------------------------------------------------------
     Wo Ansicht und Bildschirm Platz haben, steht links ein Baum: im Bestand der Ordnerbaum, im Katalog
     (Katalog, Produkt, Formular, Meldungen) der Kategorienbaum. Die eigene Ebene ist markiert, der Weg dorthin
     aufgeklappt, alles einen Klick entfernt. Unter 1200 px ist die Leiste eine Schublade hinter
     „☰ Ordner“ bzw. „☰ Kategorien“ (wie im Wiki). Nicht auf der Seite „Bestand“: dort ist der Ordnerbaum
     selbst der Inhalt. Auf- und Zuklappen merkt sich der Browser, je Baum getrennt. */
  const KATALOG_ANSICHTEN = new Set(["katalog", "produkt", "formular", "meldungen"]);
  const MIT_LEISTE = new Set(["dashboard", "pruefungen", "ordner", "artikel", "artikel_neu", "suche", "pruefung",
                              "pruefung_neu", "durchgang", "katalog", "produkt", "formular", "meldungen"]);
  const LEISTE_KATALOG = KATALOG_ANSICHTEN.has(ANSICHT);
  const leiste = document.getElementById("mat-side");
  const leisteAuf = document.getElementById("mat-side-auf");
  const KLAPP = LEISTE_KATALOG ? "mat-kategorie-klapp" : "mat-ordner-klapp";
  let leisteDaten = null;              // Ordner oder Kategorien
  let leisteAktiv = null;              // markierter Ordner bzw. markierte Kategorie
  let katalogWahl = null;              // setzt der Katalog: Kategorie wählen, ohne die Seite neu zu laden
  const klappLesen = () => { try { return JSON.parse(localStorage.getItem(KLAPP) || "{}") || {}; } catch (e) { return {}; } };
  const klappMerken = (z) => { try { localStorage.setItem(KLAPP, JSON.stringify(z)); } catch (e) { /* privat: dann eben nicht */ } };

  function leisteZeichnen() {
    if (!leisteDaten) return;
    const ziel = $("#mat-baumnav");
    if (!leisteDaten.length) { ziel.innerHTML = leer(LEISTE_KATALOG ? "Noch keine Kategorien." : "Noch keine Ordner."); return; }
    const kinder = baumKinder(leisteDaten);
    const nachId = {};
    leisteDaten.forEach((o) => { nachId[o.id] = o; });
    const weg = new Set();
    for (let x = leisteAktiv; x && nachId[x] && !weg.has(x); x = nachId[x].parent_id) weg.add(x);
    const klapp = klappLesen();
    // Kategorien zählen die Produkte ihrer Unterkategorien mit – wie die Liste, die ein Klick öffnet.
    const summe = (id) => (nachId[id].produkte || 0) + (kinder[id] || []).reduce((n, c) => n + summe(c.id), 0);
    const zeile = (o, hat, auf) => {
      const aktiv = o.id === leisteAktiv;
      const knopf = `<button class="tg" type="button" data-klapp="${o.id}" aria-label="${auf ? "zuklappen" : "aufklappen"}" ${hat ? "" : 'tabindex="-1"'}></button>`;
      const markiert = `class="${aktiv ? "active" : ""}" ${aktiv ? 'aria-current="page"' : ""}`;
      if (LEISTE_KATALOG) {
        return `${knopf}<a href="/material/katalog?kategorie=${o.id}" data-kat="${o.id}" ${markiert} title="${esc(o.name)}${o.norm ? ` · ${esc(o.norm)}` : ""}">${esc(o.name)}</a>
          <span class="mat-side-anzahl" title="Produkte (mit Unterkategorien)">${summe(o.id)}</span>`;
      }
      const z = o.zaehlung || {};
      const rot = (z.ueberfaellig || 0) + (z.lebensdauer || 0);
      const zahl = o.system_kind ? `<span class="mat-side-anzahl">${Object.values(z).reduce((a, b) => a + b, 0)}</span>`
        : `${rot ? `<span class="mat-zahl s-ueberfaellig" title="überfällig oder Lebensdauer erreicht">${rot}</span>` : ""}${z.neu ? `<span class="mat-zahl s-neu" title="neu – Eingangsprüfung offen">${z.neu}</span>` : ""}`;
      return `${knopf}<a href="/material/ordner/${o.id}" ${markiert} title="${esc(o.name)}">${o.system_kind ? "🔒 " : ""}${esc(o.name)}</a>${zahl}`;
    };
    const zweig = (pid, tiefe) => (kinder[pid] || []).map((o) => {
      const hat = !!kinder[o.id];
      const auf = hat && (weg.has(o.id) || (o.id in klapp ? klapp[o.id] : tiefe === 0));
      return `<li class="${hat ? (auf ? "" : "collapsed") : "leaf"}${o.system_kind ? " system" : ""}">
        <div class="row">${zeile(o, hat, auf)}</div>${hat ? `<ul>${zweig(o.id, tiefe + 1)}</ul>` : ""}</li>`;
    }).join("");
    const alle = LEISTE_KATALOG ? `<li class="leaf"><div class="row"><button class="tg" type="button" tabindex="-1" aria-hidden="true"></button>
      <a href="/material/katalog" data-kat="" class="${ANSICHT === "katalog" && !leisteAktiv ? "active" : ""}">alle Kategorien</a></div></li>` : "";
    ziel.innerHTML = `<ul class="tree mat-tree">${alle}${zweig(0, 0)}</ul>`;
  }

  async function leisteLaden() {
    if (!leiste || !MIT_LEISTE.has(ANSICHT) || !(DARF.lesen || (LEISTE_KATALOG && DARF.katalog))) return;
    document.getElementById("mat-shell").classList.add("mit-leiste");
    leiste.hidden = false;
    if (LEISTE_KATALOG) {
      const kopf = $(".mat-side-kopf a", leiste);
      kopf.textContent = "Kategorien";
      kopf.href = "/material/katalog";
      leiste.setAttribute("aria-label", "Kategorien");
      if (leisteAuf) leisteAuf.textContent = "☰ Kategorien";
    }
    try { leisteDaten = LEISTE_KATALOG ? await kategorienLaden() : (await api(`${API}/ordner`)).ordner; }
    catch (e) { $("#mat-baumnav").innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    leisteZeichnen();
  }
  // Jede Ansicht meldet hier ihren Ordner (Ordner, Artikel, Prüfung, Durchgang) bzw. ihre Kategorie (Katalog,
  // Produkt, Formular) – die Leiste markiert ihn.
  function leisteMarkieren(id) { leisteAktiv = id || null; leisteZeichnen(); }
  const schublade = window.matchMedia("(max-width: 1199px)");
  // Als Schublade ist die geschlossene Leiste nur aus dem Bild geschoben – „inert“ nimmt sie auch aus der
  // Tab-Reihenfolge und dem Vorlesen. Neben dem Inhalt (breiter Bildschirm) ist sie immer bedienbar.
  function leisteInert() { if (leiste) leiste.inert = schublade.matches && !leiste.classList.contains("open"); }
  function leisteZu(fokusZurueck) {
    if (!leiste) return;
    const war = leiste.classList.contains("open");
    leiste.classList.remove("open");
    if (leisteAuf) leisteAuf.setAttribute("aria-expanded", "false");
    leisteInert();
    if (war && fokusZurueck && leisteAuf) leisteAuf.focus();
  }
  if (leiste) {
    leiste.addEventListener("click", (e) => {
      // Im Katalog wechselt eine Kategorie ohne Neuladen – Suche und Sortierung bleiben stehen.
      const kat = e.target.closest("a[data-kat]");
      if (kat && katalogWahl && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
        e.preventDefault();
        katalogWahl(kat.dataset.kat ? +kat.dataset.kat : null);
        leisteZu();
        return;
      }
      const b = e.target.closest("[data-klapp]");
      if (!b) return;
      const li = b.closest("li");
      if (li.classList.contains("leaf")) return;
      const auf = li.classList.contains("collapsed");
      li.classList.toggle("collapsed", !auf);
      b.setAttribute("aria-label", auf ? "zuklappen" : "aufklappen");
      const klapp = klappLesen();
      klapp[b.dataset.klapp] = auf;
      klappMerken(klapp);
    });
    $("#mat-side-zu").addEventListener("click", () => leisteZu(true));
    if (leisteAuf) leisteAuf.addEventListener("click", () => {
      const auf = !leiste.classList.contains("open");
      leiste.classList.toggle("open", auf);
      leisteAuf.setAttribute("aria-expanded", String(auf));
      leisteInert();
      if (auf) { const a = $("a.active", leiste) || $("a", leiste); if (a) a.focus({ preventScroll: true }); }
    });
    // Tippen neben die offene Schublade oder Escape schließt sie.
    document.addEventListener("click", (e) => {
      if (leiste.classList.contains("open") && !leiste.contains(e.target) && !(leisteAuf && leisteAuf.contains(e.target))) leisteZu();
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") leisteZu(true); });
    schublade.addEventListener("change", leisteInert);
    leisteInert();
  }

  async function zeigen(fn) {
    try { await fn(); }
    catch (e) {
      inhalt.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  }

  function seitenleiste(gesamt, seite, proSeite) {
    const seiten = Math.max(1, Math.ceil(gesamt / proSeite));
    if (seiten <= 1) return "";
    return `<div class="mat-seiten"><button class="btn secondary small" data-act="seite" data-seite="${seite - 1}" ${seite <= 1 ? "disabled" : ""}>‹ zurück</button>
      <span>Seite ${seite} von ${seiten} · ${gesamt} Einträge</span>
      <button class="btn secondary small" data-act="seite" data-seite="${seite + 1}" ${seite >= seiten ? "disabled" : ""}>weiter ›</button></div>`;
  }

  /* --- Journal (Vorher/Nachher je Feld) ----------------------------------------------------- */
  function wert(v, feld) {
    if (v === null || v === undefined || v === "") return '<span class="muted">–</span>';
    if (Array.isArray(v)) return v.length ? `<ul class="mat-wertliste">${v.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "–";
    if (typeof v === "boolean" || ((feld === "serial_generated" || feld === "active" || feld === "mat_pruefer" || feld === "mat_katalog") && (v === 0 || v === 1))) return v ? "ja" : "nein";
    if (feld === "material_kind" || feld === "default_material_kind") return esc(MATERIALART[v] || v);
    if (feld === "kind" || feld === "art") return esc(PRUEFART_KURZ[v] || ORDNERART[v] || ANHANGART[v] || v);
    if (feld === "result" || feld === "ergebnis") return esc(ERGEBNIS[v] || v);
    if (["pruefung", "aussonderung", "basis", "berichtigung", "berichtigt"].includes(feld) && Number.isInteger(v)) return `<a href="/material/pruefung/${v}">Nr. ${v}</a>`;
    if (/sha256$/.test(feld)) return `<span class="mat-hash">${esc(v)}</span>`;
    if (feld === "lock_state") return esc({ frei: "frei", gesperrt: "gesperrt", verloren: "verloren (gesperrt)", ausgesondert: "ausgesondert" }[v] || v);
    if (/_on$|^valid_from$|^retire_by$|^datum$|^begonnen$/.test(feld)) return esc(fmtTag(v));
    if (typeof v === "object") return esc(JSON.stringify(v));
    return esc(v);
  }
  function journalHtml(eintraege, mitEntitaet) {
    if (!eintraege || !eintraege.length) return leer("Noch keine Einträge.");
    return `<ol class="mat-journal">${eintraege.map((j) => {
      const alle = Object.assign({}, j.vorher || {}, j.nachher || {});
      const felder = j.action === "angelegt" || j.action === "geloescht"
        ? [] : Object.keys(alle).filter((f) => !(f === "folder_id" && "ordner" in alle) && !(f === "origin_folder_id" && "herkunft" in alle)
                                       && !(f === "parent_id" && "pfad" in alle));
      const zeilen = felder.map((f) => `<tr><th>${esc(FELD[f] || f)}</th><td>${wert((j.vorher || {})[f], f)}</td><td>${wert((j.nachher || {})[f], f)}</td></tr>`).join("");
      return `<li><div class="mat-j-kopf"><span class="mat-j-zeit">${esc(fmtZeit(j.created_at))}</span>
        <strong>${mitEntitaet ? esc(ENTITAET[j.entity] || j.entity) + " " : ""}${esc(AKTION[j.action] || j.action)}</strong>
        <span class="muted">von ${esc(j.user_name || "–")}</span></div>
        ${zeilen ? `<table class="mat-diff"><thead><tr><th>Feld</th><th>vorher</th><th>nachher</th></tr></thead><tbody>${zeilen}</tbody></table>` : ""}</li>`;
    }).join("")}</ol>`;
  }

  /* --- Unterschrift und Protokoll ------------------------------------------------------------------
     Festschreiben (Prüfung) und Aussondern brauchen die eigene Unterschrift aus dem Profil. Fehlt sie, öffnet
     sich zuerst das Signatur-Pad (unterschrift.js); gespeichert wird sie im Profil und gilt sofort. */
  let eigenesBildMerk = null;
  // Jedes Mal frisch vom Server: Der Dialog soll genau die Unterschrift zeigen, die ins Protokoll kommt – auch wenn
  // sie inzwischen in einem anderen Fenster ersetzt wurde.
  async function eigenesBild() {
    if (DARF.unterschrift) {
      eigenesBildMerk = (await api(`${API}/unterschrift`)).unterschrift;
      // Inzwischen im Profil entfernt (anderes Fenster)? Dann gilt sie als fehlend – Festschreiben fragt neu.
      if (!eigenesBildMerk) DARF.unterschrift = false;
    }
    return eigenesBildMerk;
  }
  async function eigeneUnterschrift(hinweis) {
    if (DARF.unterschrift) return true;
    const bild = await MatUnterschrift.zeichnen({ titel: "Deine Unterschrift", hinweis,
      speichern: async (b) => { eigenesBildMerk = (await api(`${API}/unterschrift`, { method: "PUT", body: { bild: b } })).unterschrift; } });
    if (!bild) return false;
    DARF.unterschrift = true;
    toast("Unterschrift in deinem Profil gespeichert");
    return true;
  }
  // Der Server lehnt ab, weil die Unterschrift inzwischen fehlt (in einem anderen Fenster entfernt)?
  const unterschriftWeg = (e) => { if (e.status === 403 && /Unterschrift/.test(e.message)) { DARF.unterschrift = false; eigenesBildMerk = null; } };
  // Ohne Zwischenablage ist der Text markiert; am Telefon gibt es kein Strg+C, dort kopiert das Menü der Markierung.
  const kopierText = () => (window.matchMedia("(pointer: coarse)").matches ? "jetzt kopieren" : "mit Strg+C kopieren");
  // Prüfsumme gekürzt; der volle Wert steht im title, ein Klick kopiert ihn (Aktion „summe“).
  const summeKnopf = (h) => `<button type="button" class="mat-summe mat-hash" data-act="summe" data-wert="${esc(h)}" title="${esc(h)} – Klick kopiert">${esc(h.slice(0, 16))}…</button>`;
  async function summeKopieren(b) {
    try { await navigator.clipboard.writeText(b.dataset.wert); toast("Prüfsumme kopiert"); }
    catch (e) {
      // Ohne Zwischenablage: die ganze Summe zeigen und markieren.
      b.textContent = b.dataset.wert;
      const r = document.createRange(); r.selectNodeContents(b);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      toast(`Prüfsumme markiert – ${kopierText()}`);
    }
  }

  /* --- Ordnerbaum ----------------------------------------------------------------------------- */
  function baumKinder(liste) {
    const kinder = {};
    liste.forEach((o) => { (kinder[o.parent_id || 0] = kinder[o.parent_id || 0] || []).push(o); });
    Object.values(kinder).forEach((l) => l.sort((a, b) => (a.system_kind ? 1 : 0) - (b.system_kind ? 1 : 0) || a.position - b.position || a.name.localeCompare(b.name, "de")));
    return kinder;
  }
  function zahlen(z) {
    if (!z) return "";
    const teile = [];
    if (z.ueberfaellig) teile.push(`<span class="mat-zahl s-ueberfaellig" title="überfällig">${z.ueberfaellig}</span>`);
    if (z.neu) teile.push(`<span class="mat-zahl s-neu" title="neu – Eingangsprüfung offen">${z.neu}</span>`);
    if (z.lebensdauer) teile.push(`<span class="mat-zahl s-lebensdauer" title="Lebensdauer erreicht">${z.lebensdauer}</span>`);
    if (z.gesperrt) teile.push(`<span class="mat-zahl s-gesperrt" title="gesperrt">${z.gesperrt}</span>`);
    if (z.bald_faellig) teile.push(`<span class="mat-zahl s-bald_faellig" title="bald fällig">${z.bald_faellig}</span>`);
    return teile.join("");
  }
  function baumHtml(liste, start) {
    const kinder = baumKinder(liste);
    const zweig = (pid) => (kinder[pid] || []).map((o) => `<li class="${o.system_kind ? "system" : ""}">
        <a href="/material/ordner/${o.id}">${o.system_kind ? "🔒 " : ""}${esc(o.name)}</a>
        ${o.system_kind ? "" : `<span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span>`}${demoMarke(o.demo)}
        <span class="mat-baum-zahl">${o.system_kind ? (o.zaehlung ? Object.values(o.zaehlung).reduce((a, b) => a + b, 0) : 0) : o.bestand}</span>${o.system_kind ? "" : zahlen(o.zaehlung)}
        ${kinder[o.id] ? `<ul>${zweig(o.id)}</ul>` : ""}</li>`).join("");
    return `<ul class="mat-baum">${zweig(start || 0)}</ul>`;
  }

  function unterordnerHtml(liste) {
    return `<ul class="mat-unterordner">${liste.map((o) => `<li class="${o.system_kind ? "system" : ""}">
        <a href="/material/ordner/${o.id}">${o.system_kind ? "🔒 " : ""}${esc(o.name)}</a>
        ${o.system_kind ? "" : `<span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span>`}${demoMarke(o.demo)}
        <span class="mat-baum-zahl">${o.system_kind ? Object.values(o.zaehlung || {}).reduce((a, b) => a + b, 0) : o.bestand}</span>${o.system_kind ? "" : zahlen(o.zaehlung)}</li>`).join("")}</ul>`;
  }

  /* Ordnerwahl im Dialog: Systemordner und (beim Verschieben eines Ordners) dessen eigener Zweig
     sind nicht wählbar. */
  async function ordnerWaehlen(titel, opts) {
    opts = opts || {};
    const liste = (await api(`${API}/ordner`)).ordner;
    const kinder = baumKinder(liste);
    const gesperrt = new Set();
    if (opts.ohneZweig) {
      const weg = [opts.ohneZweig];
      while (weg.length) { const x = weg.pop(); gesperrt.add(x); (kinder[x] || []).forEach((k) => weg.push(k.id)); }
    }
    const zweig = (pid) => (kinder[pid] || []).filter((o) => !o.system_kind).map((o) => `<li>
        <label class="inline"><input type="radio" name="ziel" value="${o.id}" ${gesperrt.has(o.id) ? "disabled" : ""}>
        ${esc(o.name)} <span class="mat-art">${esc(ORDNERART[o.kind])}</span></label>
        ${kinder[o.id] ? `<ul>${zweig(o.id)}</ul>` : ""}</li>`).join("");
    return new Promise((resolve) => {
      let gewaehlt = null;
      const dlg = dialog(`<h2>${esc(titel)}</h2>
        ${opts.obersteEbene ? '<label class="inline"><input type="radio" name="ziel" value="0"> oberste Ebene (nur für Gliederungen)</label>' : ""}
        <div class="mat-wahl">${liste.length ? `<ul class="mat-baum">${zweig(0)}</ul>` : leer("Noch keine Ordner.")}</div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="ow-ok" type="button">Übernehmen</button></div>`, (d, body) => {
        $("#ow-ok", body).onclick = () => {
          const r = $('input[name="ziel"]:checked', body);
          if (!r) { toast("Bitte einen Ordner wählen.", true); return; }
          gewaehlt = +r.value;
          d.close();
        };
      });
      dlg.addEventListener("close", () => resolve(gewaehlt), { once: true });
    });
  }

  /* --- Übersicht ------------------------------------------------------------------------------ */
  async function dashboard() {
    const d = await api(`${API}/start`);
    const z = d.zaehlung;
    const kachel = (s, titel) => `<a class="mat-kachel s-${s}" href="/material/pruefungen?status=${s}"><strong>${z[s] || 0}</strong><span>${esc(titel)}</span></a>`;
    inhalt.innerHTML = `<div class="page-head"><h1>Material</h1>
        <div class="btn-row">${DARF.verwalten ? '<a class="btn secondary" href="/material/bestand">Bestand pflegen</a><a class="btn secondary" href="/material/artikel/neu">+ Artikel</a>' : ""}</div></div>
      ${rueckrufKasten(d.rueckrufe)}
      ${d.meldungen_offen ? `<p class="notice"><a href="/material/katalog/meldungen"><strong>${plural(d.meldungen_offen, "offene Produktmeldung", "offene Produktmeldungen")}</strong></a>
        – Materialwarte warten darauf, Artikel davon anzulegen.</p>` : ""}
      <div class="mat-kacheln">
        <div class="mat-kachel gesamt"><strong>${d.bestand}</strong><span>Artikel im Bestand</span></div>
        ${kachel("ueberfaellig", "überfällig")}${kachel("neu", "neu (Eingangsprüfung)")}${kachel("bald_faellig", `bald fällig (${d.schwelle_tage} Tage)`)}
        ${kachel("gesperrt", "gesperrt")}${kachel("lebensdauer", "Lebensdauer erreicht")}${kachel("einsatzbereit", "einsatzbereit")}
      </div>
      <div id="mat-runden"></div>
      <section class="section"><h2>Fälligkeiten je Ordner</h2>
        ${d.ordner_uebersicht.length ? ordnerUebersichtHtml(d.ordner_uebersicht)
          : leer(DARF.verwalten ? "Noch keine Gliederung – lege unter „Bestand“ die erste an." : "Noch keine Gliederung angelegt.")}
      </section>
      <section class="section"><h2>Als Nächstes zu prüfen</h2>
        ${d.naechste.length ? artikelTabelle(d.naechste, { pfad: true }) + (d.faellig_gesamt > d.naechste.length ? `<p><a href="/material/pruefungen">Alle ${d.faellig_gesamt} anzeigen →</a></p>` : "")
          : leer("Nichts fällig.")}
      </section>`;
    ordnerUebersichtKlappen($("#mat-ue"));
    rundenKasten($("#mat-runden"), true);
  }

  /* Fälligkeiten je Ordner: Gliederungen mit ihren Ordnern eingerückt, die Zahlen für den ganzen Zweig – dieselben wie in
     der Ordnerleiste (/start, ordner_uebersicht). Die Systemordner sind keine eigenen Zeilen: Gesperrte und ausgesonderte
     Artikel liegen in ihrer Gliederung und zählen dort. Jede Zahl führt zur Liste genau dieser Artikel (Prüfungen, nach
     Ordner und Status gefiltert), die nächste Fälligkeit zu allem Fälligen im Ordner, der Name zum Ordner. Ein großer Baum
     (mehr als UE_GROSS Zeilen) beginnt mit zugeklappten Ordnern ab der zweiten Ebene unter der Gliederung. Unter 860 px
     wird jede Zeile zur Karte; leere Zahlen entfallen dort. */
  const UE_SPALTEN = [["ueberfaellig", "überfällig", "überfällig"], ["neu", "neu", "neu (Eingangsprüfung offen)"],
                      ["bald_faellig", "bald fällig", "bald fällig"], ["gesperrt", "gesperrt", "gesperrt"],
                      ["lebensdauer", "Lebensdauer erreicht", "Lebensdauer erreicht"]];
  const UE_GROSS = 30;
  function ordnerUebersichtHtml(zeilen) {
    const nachId = {};
    zeilen.forEach((o) => { nachId[o.id] = o; });
    const zu = new Set(zeilen.length > UE_GROSS ? zeilen.filter((o) => o.tiefe >= 1 && o.unterordner).map((o) => o.id) : []);
    const vorfahren = (o) => { const weg = []; for (let p = nachId[o.parent_id]; p; p = nachId[p.parent_id]) weg.push(p.id); return weg; };
    const zeile = (o) => {
      const weg = vorfahren(o);
      const knopf = o.unterordner
        ? `<button type="button" class="mat-ue-klapp" data-ue-klapp="${o.id}" aria-expanded="${!zu.has(o.id)}" aria-label="Unterordner von ${esc(o.name)}"></button>`
        : '<span class="mat-ue-klapp" aria-hidden="true"></span>';
      const zahlen = UE_SPALTEN.map(([s, kurz, lang]) => {
        const n = o.zaehlung[s] || 0;
        return `<td data-l="${esc(lang)}" class="mat-ue-zahl${n ? "" : " mat-ue-null"}">${n ? `<a class="mat-zahl s-${s}" href="/material/pruefungen?ordner=${o.id}&status=${s}" title="${esc(`${lang} – ${o.name}`)}">${n}</a>` : '<span class="muted">–</span>'}</td>`;
      }).join("");
      return `<tr data-weg="${weg.join(" ")}" class="${o.tiefe ? "" : "mat-ue-oben"}" style="--tiefe:${Math.min(o.tiefe, 8)}" ${weg.some((x) => zu.has(x)) ? "hidden" : ""}>
        <td data-l="Ordner" class="mat-ue-name">${knopf}<a href="/material/ordner/${o.id}">${esc(o.name)}</a>${o.tiefe && o.kind !== "gliederung" ? "" : ` <span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span>`}${demoMarke(o.demo)}</td>
        <td data-l="Bestand" class="mat-ue-zahl">${o.bestand}</td>${zahlen}
        <td data-l="nächste Fälligkeit" class="mat-ue-tag${o.naechste ? "" : " mat-ue-null"}">${o.naechste ? `<a class="t-${esc(o.naechste_status)}" href="/material/pruefungen?ordner=${o.id}" title="Alles Fällige in ${esc(o.name)}">${esc(fmtTag(o.naechste))}</a>` : '<span class="muted">–</span>'}</td></tr>`;
    };
    return `<p class="help">Die Zahlen gelten für den ganzen Zweig. Gesperrte und ausgesonderte Artikel liegen in ihrer Gliederung und zählen dort.
        Nächste Fälligkeit: das früheste Prüfdatum im Zweig – ohne neue (Eingangsprüfung), gesperrte und Artikel am Lebensende, die ihre eigenen Spalten haben.</p>
      <table class="list mat-tabelle mat-ue" id="mat-ue"><thead><tr><th>Ordner</th><th class="mat-ue-zahl">Bestand</th>
        ${UE_SPALTEN.map(([s, kurz, lang]) => `<th class="mat-ue-zahl" title="${esc(lang)}">${esc(kurz)}</th>`).join("")}<th>nächste Fälligkeit</th></tr></thead>
      <tbody>${zeilen.map(zeile).join("")}</tbody></table>`;
  }
  // Auf- und Zuklappen: Eine Zeile ist verborgen, solange einer ihrer Oberordner zugeklappt ist.
  function ordnerUebersichtKlappen(tabelle) {
    if (!tabelle) return;
    tabelle.addEventListener("click", (e) => {
      const b = e.target.closest("[data-ue-klapp]");
      if (!b) return;
      b.setAttribute("aria-expanded", String(b.getAttribute("aria-expanded") !== "true"));
      const zu = new Set($$('[data-ue-klapp][aria-expanded="false"]', tabelle).map((x) => x.dataset.ueKlapp));
      $$("tbody tr", tabelle).forEach((tr) => { tr.hidden = tr.dataset.weg.split(" ").some((x) => x && zu.has(x)); });
    });
  }

  /* Laufende Prüfdurchgänge als Kasten (Übersicht) bzw. Liste mit abgeschlossenen (Prüfungen). */
  async function rundenKasten(ziel, nurOffen) {
    if (!ziel) return;
    try {
      const liste = (await api(`${API}/durchgaenge${nurOffen ? "?offen=1" : ""}`)).durchgaenge;
      if (nurOffen && !liste.length) { ziel.innerHTML = ""; return; }
      ziel.innerHTML = `<section class="section"><h2>${nurOffen ? "Laufende Prüfdurchgänge" : "Prüfdurchgänge"}</h2>
        ${liste.length ? `<ul class="mat-runden">${liste.map((r) => `<li><a href="/material/durchgang/${r.id}"><strong>${esc(r.titel)}</strong></a>
          <span class="muted">${esc(r.ordner)} · eröffnet ${esc(fmtTag(r.eroeffnet_am))}${r.offen ? "" : ` · ${r.abgebrochen ? "abgebrochen" : "abgeschlossen"} ${esc(fmtTag(r.geschlossen_am))}`}</span>
          ${fortschritt(r.zaehlung)}${r.protokoll ? ` <a class="mat-pdf" href="${esc(r.protokoll.url)}" target="_blank" rel="noopener" title="Sammelprotokoll ${esc(r.protokoll.id)} öffnen">PDF</a>` : ""}</li>`).join("")}</ul>` : leer("Noch kein Prüfdurchgang.")}</section>`;
    } catch (e) { ziel.innerHTML = ""; }
  }
  function fortschritt(z) {
    const fertig = z.erledigt + z.ausgenommen;
    const proz = z.gesamt ? Math.round((100 * fertig) / z.gesamt) : 0;
    return `<span class="mat-fortschritt" title="${fertig} von ${z.gesamt} erledigt oder ausgenommen"><span style="width:${proz}%"></span></span>
      <span class="small">${fertig}/${z.gesamt}${z.in_pruefung ? ` · ${z.in_pruefung} in Prüfung` : ""}</span>`;
  }

  /* Artikelliste als Tabelle; mit auswahl:true bekommt jede Zeile ein Häkchen (Mehrfachauswahl). */
  /* Sortierbare Spaltenköpfe. Sortiert wird auf dem Server (die Listen kommen seitenweise); ein Klick sortiert
     aufsteigend, der nächste auf dieselbe Spalte absteigend. sort = { feld, richtung } oder null. */
  function sortKopf(titel, feld, sort) {
    if (!sort) return `<th>${esc(titel)}</th>`;
    const an = sort.feld === feld;
    const zustand = an ? (sort.richtung === "ab" ? "descending" : "ascending") : "none";
    return `<th aria-sort="${zustand}"><button type="button" class="mat-sort${an ? " an" : ""}" data-act="sortieren" data-feld="${feld}"
      title="nach ${esc(titel)} sortieren">${esc(titel)}<span class="mat-sort-pfeil" aria-hidden="true">${an ? (sort.richtung === "ab" ? "▼" : "▲") : "↕"}</span></button></th>`;
  }
  const sortWeiter = (sort, feld) => (sort.feld === feld ? { feld, richtung: sort.richtung === "auf" ? "ab" : "auf" } : { feld, richtung: "auf" });
  const sortParameter = (q, sort) => { if (sort && sort.feld) { q.set("sort", sort.feld); q.set("richtung", sort.richtung); } return q; };
  // Ein Produkt in Listen: Hersteller in eigener Spalte, hier Bild, Modell und Artikelnummer.
  const produktZelle = (a) => `${a.vorschau ? `<img class="mat-mini" src="${esc(a.vorschau)}" alt="" loading="lazy">` : ""}${esc(a.model || "")}${a.article_no ? ` <span class="muted">${esc(a.article_no)}</span>` : ""}${demoMarke(a.demo)}`;

  function artikelTabelle(liste, opts) {
    opts = opts || {};
    const s = opts.sort || null;
    return `<table class="list mat-tabelle mat-artikel">
      <thead><tr>${opts.auswahl ? '<th class="mat-wahlspalte"><input type="checkbox" id="mat-alle" aria-label="alle auswählen"></th>' : ""}
        ${sortKopf("Inventar-Nr.", "inventar", s)}${sortKopf("Hersteller", "hersteller", s)}${sortKopf("Produkt", "produkt", s)}${sortKopf("Seriennummer", "serie", s)}
        ${opts.pfad ? "<th>Ablage</th>" : ""}${sortKopf("Nächste Prüfung", "faellig", s)}${sortKopf("Status", "status", s)}${opts.pruefen ? "<th></th>" : ""}</tr></thead>
      <tbody>${liste.map((a) => `<tr data-id="${a.id}">
        ${opts.auswahl ? `<td class="mat-wahlspalte"><input type="checkbox" class="mat-wahl-art" value="${a.id}" ${a.lock_state !== "frei" ? 'disabled title="Gesperrte und ausgesonderte Artikel bleiben in ihrem Systemordner."' : ""} aria-label="${esc(a.inventory_no)} auswählen"></td>` : ""}
        <td data-l="Inventar-Nr."><a class="mat-inv" href="/material/artikel/${a.id}"><strong>${esc(a.inventory_no)}</strong></a></td>
        <td data-l="Hersteller">${esc(a.manufacturer || "")}</td>
        <td data-l="Produkt">${produktZelle(a)}</td>
        <td data-l="Seriennummer">${esc(a.serial_no)}${a.serial_generated ? ' <span class="muted" title="vom System vergeben">(System)</span>' : ""}</td>
        ${opts.pfad ? `<td data-l="Ablage">${esc(a.pfad || "")}</td>` : ""}
        <td data-l="Nächste Prüfung">${a.status === "neu" ? '<span class="muted">Eingangsprüfung</span>' : a.lock_state !== "frei" ? '<span class="muted">–</span>' : a.next_due_on ? esc(fmtTag(a.next_due_on)) : '<span class="muted">–</span>'}</td>
        <td data-l="Status">${statusMarke(a.status)}${a.rueckruf ? ` <span class="mat-rr-marke" title="Rückruf: ${esc(a.rueckruf)}">Rückruf</span>` : ""}${a.entwurf ? `<div class="small muted">in Prüfung bei ${esc(a.entwurf.pruefer || "?")}</div>` : ""}</td>
        ${opts.pruefen ? `<td class="tabelle-aktionen">${pruefKnopf(a)}</td>` : ""}</tr>`).join("")}</tbody></table>`;
  }
  // „Prüfen“ in Listen: für Prüfer, solange niemand anderes den Artikel reserviert hat.
  function pruefKnopf(a, durchgangId) {
    if (!DARF.pruefen || a.lock_state === "ausgesondert") return "";
    if (a.entwurf && a.entwurf.pruefer_id !== DARF.uid) return "";
    const q = durchgangId ? `?durchgang=${durchgangId}` : "";
    return a.entwurf ? `<a class="btn secondary small" href="/material/pruefung/${a.entwurf.id}">Weiter prüfen</a>`
      : `<a class="btn secondary small" href="/material/artikel/${a.id}/pruefung/neu${q}">Prüfen</a>`;
  }

  /* --- Fällige Prüfungen ------------------------------------------------------------------------ */
  async function pruefungen() {
    const params = new URLSearchParams(location.search);
    // Alles Fällige – wie bestand.FAELLIG auf dem Server (überfällig, Lebensdauer erreicht, neu, bald fällig).
    const FAELLIG = "ueberfaellig,lebensdauer,neu,bald_faellig";
    let filter = params.get("status") || FAELLIG;
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    const FILTER = [[FAELLIG, "alles Fällige"], ["ueberfaellig", "überfällig"], ["lebensdauer", "Lebensdauer erreicht"],
                    ["neu", "neu (Eingangsprüfung)"], ["bald_faellig", "bald fällig"], ["gesperrt", "gesperrt"],
                    ["einsatzbereit", "einsatzbereit"]];
    if (DATEN.ordner) leisteMarkieren(DATEN.ordner);
    async function liste() {
      const q = sortParameter(new URLSearchParams({ status: filter, seite, pro_seite: 50 }), sort);
      if (DATEN.ordner) q.set("ordner", DATEN.ordner);
      const d = await api(`${API}/faellig?${q}`);
      // Aus der Übersicht kommt die Liste nach Ordner gefiltert – samt Unterordnern; „alle Ordner“ hebt das auf.
      const ordnerZeile = d.ordner ? `<p class="mat-pr-ordner">Nur <a href="/material/ordner/${d.ordner.id}">${esc(d.ordner.pfad.map((o) => o.name).join(" / "))}</a> mit Unterordnern
        · <a href="/material/pruefungen?status=${encodeURIComponent(filter)}">alle Ordner</a></p>` : "";
      $("#pr-liste").innerHTML = `${ordnerZeile}<p class="help">Überfällig, Lebensdauer erreicht (die Prüfung endet mit „aussondern“), neu (die Eingangsprüfung steht aus) oder in den nächsten ${d.schwelle_tage} Tagen fällig. Prüfen lässt sich jeder Artikel aber jederzeit – auch aus seiner Ansicht.</p>
        <div class="c-tabs mat-filter">${FILTER.map(([f, t]) => `<button type="button" data-act="filter" data-f="${f}" class="${f === filter ? "sel" : ""}">${esc(t)}</button>`).join("")}</div>
        ${d.artikel.length ? artikelTabelle(d.artikel, { pfad: true, pruefen: DARF.pruefen, sort }) : leer("Keine Artikel in dieser Auswahl.")}
        ${seitenleiste(d.gesamt, seite, 50)}`;
    }
    async function offene() {
      const liste = (await api(`${API}/entwuerfe`)).entwuerfe;
      $("#pr-offen").innerHTML = liste.length ? `<section class="section"><h2>Offene Prüfungen</h2>
        <p class="help">Eine offene Prüfung reserviert ihren Artikel: Nur ihr Prüfer arbeitet daran weiter. Liegt eine liegen, gibt der Materialwart sie frei.</p>
        <table class="list mat-tabelle"><thead><tr><th>Artikel</th><th>Prüfung</th><th>Prüfer</th><th>begonnen</th><th></th></tr></thead><tbody>
        ${liste.map((x) => `<tr><td data-l="Artikel"><a href="/material/artikel/${x.item_id}"><strong>${esc(x.artikel.inventory_no)}</strong></a> ${esc(produktName(x.artikel))} <div class="small muted">${esc(x.artikel.pfad)}</div></td>
          <td data-l="Prüfung">${esc(PRUEFART_KURZ[x.art] || x.art)}</td><td data-l="Prüfer">${esc(x.pruefer)}${x.eigen ? ' <span class="badge">du</span>' : ""}</td>
          <td data-l="begonnen">${esc(fmtZeit(x.begonnen_am))}</td>
          <td class="tabelle-aktionen">${x.eigen && DARF.pruefen ? `<a class="btn secondary small" href="/material/pruefung/${x.id}">Weiter prüfen</a>` : `<a class="btn secondary small" href="/material/pruefung/${x.id}">Ansehen</a>`}
            ${!x.eigen && DARF.verwalten ? `<button class="btn secondary small" data-act="freigeben" data-id="${x.id}" data-wer="${esc(x.pruefer)}">Freigeben</button>` : ""}</td></tr>`).join("")}
        </tbody></table></section>` : "";
    }
    async function zeichnen() {
      inhalt.innerHTML = `<div class="page-head"><h1>Prüfungen</h1>
          <div class="btn-row"><a class="btn secondary" href="/material/pruefen" title="Ist ein PDF-Protokoll unverändert?">Protokoll prüfen</a>
            ${DARF.verwalten || DARF.pruefen ? '<button class="btn secondary" data-act="runde">+ Prüfdurchgang</button>' : ""}</div></div>
        ${!DARF.pruefen ? `<p class="notice">${pruefHinweis()}</p>` : ""}
        <div id="pr-runden"></div><div id="pr-offen"></div>
        <section class="section"><h2>Zu prüfen</h2><div id="pr-liste"><p class="help">Wird geladen …</p></div></section>`;
      await Promise.all([zeigenIn(liste, "#pr-liste"), zeigenIn(offene, "#pr-offen"), rundenKasten($("#pr-runden"), false)]);
    }
    aktionen = {
      filter: (b) => { filter = b.dataset.f; seite = 1; history.replaceState(null, "", `?${DATEN.ordner ? `ordner=${DATEN.ordner}&` : ""}status=${filter}`); zeigenIn(liste, "#pr-liste"); },
      seite: (b) => { seite = +b.dataset.seite; zeigenIn(liste, "#pr-liste"); },
      sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); seite = 1; zeigenIn(liste, "#pr-liste"); },
      freigeben: (b) => reservierungFreigeben(+b.dataset.id, b.dataset.wer, () => Promise.all([zeigenIn(offene, "#pr-offen"), zeigenIn(liste, "#pr-liste")])),
      runde: () => rundeDialog(DATEN.ordner || null),
    };
    await zeichnen();
  }

  // Wie zeigen(), aber nur für einen Teil der Seite.
  async function zeigenIn(fn, sel) {
    try { await fn(); } catch (e) { const el = $(sel); if (el) el.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  }

  async function reservierungFreigeben(pid, wer, danach) {
    if (!(await confirm(`Die offene Prüfung von ${wer} verwerfen und den Artikel freigeben? Ihre Befunde, Fotos und Anhänge gehen dabei verloren.`, "Freigeben"))) return;
    try { await api(`${API}/pruefungen/${pid}`, { method: "DELETE" }); toast("Reservierung freigegeben"); await danach(); }
    catch (e) { toast(e.message, true); }
  }

  async function rundeDialog(ordnerId) {
    const liste = (await api(`${API}/ordner`)).ordner.filter((o) => !o.system_kind);
    if (!liste.length) { toast("Zuerst unter „Bestand“ eine Gliederung anlegen.", true); return; }
    const kinder = baumKinder(liste);
    const optionen = (pid, tiefe) => (kinder[pid] || []).map((o) => `<option value="${o.id}" ${o.id === ordnerId ? "selected" : ""}>${EIN.repeat(tiefe)}${esc(o.name)} (${o.bestand})</option>${optionen(o.id, tiefe + 1)}`).join("");
    dialog(`<h2>Prüfdurchgang eröffnen</h2>
      <p class="help">Alle Artikel im gewählten Ordner und darunter (ohne ausgesonderte) kommen auf eine gemeinsame Liste. Mehrere Prüfer arbeiten sie gleichzeitig ab; wer einen Artikel öffnet, reserviert ihn.</p>
      <label for="rd-titel">Titel</label><input type="text" id="rd-titel" maxlength="160" value="Jahresprüfung ${new Date().getFullYear()}">
      <label for="rd-ordner">Ordner</label><select id="rd-ordner">${optionen(0, 0)}</select>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="rd-ok" type="button">Eröffnen</button></div>`,
    (dlg, body) => {
      fokus($("#rd-titel", body));
      $("#rd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge`, { method: "POST", body: { titel: $("#rd-titel", body).value, folder_id: +$("#rd-ordner", body).value } });
          location.href = `/material/durchgang/${r.durchgang.id}`;
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Bestand ------------------------------------------------------------------------------------ */
  async function bestand() {
    const d = await api(`${API}/ordner`);
    inhalt.innerHTML = `<div class="page-head"><h1>Bestand</h1>
        <div class="btn-row">${DARF.verwalten ? '<button class="btn secondary" data-act="gliederung">+ Gliederung</button>' : ""}</div></div>
      <p class="help">Oben stehen die Gliederungen, darunter frei verschachtelt Standorte, Fahrzeuge, Sets. Jede Gliederung hat die
        Systemordner „Gesperrt“ und „Ausgesondert“ – dorthin kommen Artikel nur durch eine Sperre oder Aussonderung.
        Die Zahl hinter einem Ordner ist sein Bestand; farbig: überfällig, Lebensdauer erreicht, gesperrt, bald fällig.</p>
      ${d.ordner.length ? baumHtml(d.ordner) : leer("Noch kein Ordner angelegt.")}`;
    aktionen = { gliederung: () => ordnerDialog({ kind: "gliederung" }, null) };
  }

  /* --- Foto im Dialog (Ordnerfoto, Produktbild – Lieferung 5) ------------------------------------------------
     Statt des nackten Dateifelds („Datei auswählen / Keine ausgewählt“, 21 px hoch) ein Knopf „📷 Foto wählen …“ –
     ohne capture: Am Telefon bietet das System Kamera ODER Galerie an, am Rechner öffnet er den Dateidialog, und das
     Foto lässt sich auch in den Dialog ziehen. Links die Vorschau: das bisherige Foto, das neu gewählte (schon vor dem
     Speichern) oder ein leerer Rahmen, daneben Dateiname und Größe. „entfernen“ ist ein Knopf und wirkt wie die
     Auswahl erst beim Speichern; „Doch behalten“ nimmt es zurück. Angenommen wird, was auch der Server annimmt. */
  const FOTO_ENDUNGEN = [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"];   // images.ALLOWED_EXT
  const FOTO_MAX_BYTES = 30 * 1024 * 1024;                                                         // katalog.BILD_MAX_BYTES
  // id: das Dateifeld; titel: Überschrift; wort: „Foto“ oder „Bild“; bisher: Vorschau des bisherigen (oder leer).
  const fotoFeld = (id, titel, wort, bisher, hinweis) => `<div class="mat-feldkopf" id="${id}-kopf">${esc(titel)}</div>
      <div class="mat-bildwahl" id="${id}-feld" role="group" aria-labelledby="${id}-kopf" data-wort="${esc(wort)}" data-bisher="${esc(bisher || "")}">
        <div class="mat-bildwahl-bild"></div>
        <div class="mat-bildwahl-steuer">
          <div class="btn-row"><label class="btn secondary mat-bildwahl-knopf"><span aria-hidden="true">📷</span> ${esc(wort)} wählen …<input type="file" id="${id}"
              accept="image/*" class="mat-datei" aria-describedby="${id}-name ${id}-hilfe"></label>
            <button type="button" class="btn secondary mat-bildwahl-weg" hidden></button></div>
          <div class="mat-bildwahl-name" id="${id}-name" aria-live="polite"></div>
          <div class="help" id="${id}-hilfe">${esc(hinweis)}<span class="mat-nur-maus"> Die Datei lässt sich auch hierher ziehen.</span></div>
        </div></div>`;
  // Liefert die Auswahl als { datei: File | null, entfernen: bool } – gelesen erst beim Speichern.
  function fotoFeldVerdrahten(dlg, body, id) {
    const feld = $(`#${id}-feld`, body);
    const eingabe = $(`#${id}`, body);
    const { wort, bisher } = feld.dataset;
    const wahl = { datei: null, entfernen: false };
    let url = null;
    function zeichnen() {
      if (url) { URL.revokeObjectURL(url); url = null; }
      const f = wahl.datei;
      const bild = $(".mat-bildwahl-bild", feld);
      const weg = $(".mat-bildwahl-weg", feld);
      if (f) url = URL.createObjectURL(f);
      bild.classList.toggle("weg", !f && wahl.entfernen);
      bild.innerHTML = f ? `<img src="${esc(url)}" alt="Vorschau: ${esc(f.name)}">`
        : bisher ? `<img src="${esc(bisher)}" alt="Bisheriges ${esc(wort)}${wahl.entfernen ? " – wird entfernt" : ""}">`
        : `<span class="mat-bildwahl-leer">kein ${esc(wort)}</span>`;
      // HEIC zeigt außer Safari kaum ein Browser an – hochgeladen und umgewandelt wird es trotzdem. (Ein schon ersetztes
      // Bild, dessen Adresse eben freigegeben wurde, meldet sich hier nicht mehr.)
      const img = $("img", bild);
      if (f) img.onerror = () => { if (img.isConnected) bild.innerHTML = '<span class="mat-bildwahl-leer">Vorschau nach dem Speichern</span>'; };
      $(".mat-bildwahl-name", feld).innerHTML = f
        ? `<strong>${esc(f.name)}</strong> · ${esc(groesse(f.size))} – ${bisher ? `ersetzt beim Speichern das bisherige ${esc(wort)}` : "wird beim Speichern hochgeladen"}`
        : wahl.entfernen ? `Das ${esc(wort)} wird beim Speichern entfernt.` : "";
      weg.hidden = !f && !bisher;
      weg.textContent = f ? "Auswahl entfernen" : wahl.entfernen ? "Doch behalten" : `${wort} entfernen`;
    }
    function nehmen(f) {
      if (!f) return;
      const endung = (f.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
      if (!FOTO_ENDUNGEN.includes(endung)) { toast(`„${f.name}“ ist kein Foto (JPEG, PNG, WebP, HEIC oder TIFF).`, true); return; }
      if (f.size > FOTO_MAX_BYTES) { toast(`„${f.name}“ ist größer als ${FOTO_MAX_BYTES / 1048576} MB.`, true); return; }
      wahl.datei = f;
      wahl.entfernen = false;
      zeichnen();
    }
    // Den Wert gleich leeren: So löst dieselbe Datei nach „Auswahl entfernen“ wieder ein change aus.
    eingabe.addEventListener("change", () => { nehmen(eingabe.files[0]); eingabe.value = ""; });
    $(".mat-bildwahl-weg", feld).addEventListener("click", (ev) => {
      if (wahl.datei) wahl.datei = null;
      else wahl.entfernen = !wahl.entfernen;
      zeichnen();
      if (ev.currentTarget.hidden) eingabe.focus();
    });
    // Ablegen per Ziehen: überall im Dialog (sonst öffnete der Browser die Datei und der Dialog wäre weg). #dlg-body
    // bleibt über alle Dialoge bestehen – die Handler gelten nur, solange dieser offen ist. Gezogener Text bleibt Text.
    const aus = new AbortController();
    dlg.addEventListener("close", () => { aus.abort(); if (url) URL.revokeObjectURL(url); }, { once: true });
    const dateien = (ev) => ev.dataTransfer && Array.from(ev.dataTransfer.types || []).includes("Files");
    body.addEventListener("dragover", (ev) => { if (!dateien(ev)) return; ev.preventDefault(); feld.classList.add("ueber"); }, { signal: aus.signal });
    body.addEventListener("dragleave", (ev) => { if (!body.contains(ev.relatedTarget)) feld.classList.remove("ueber"); }, { signal: aus.signal });
    body.addEventListener("drop", (ev) => {
      if (!dateien(ev)) return;
      ev.preventDefault();
      feld.classList.remove("ueber");
      nehmen(ev.dataTransfer.files[0]);
    }, { signal: aus.signal });
    zeichnen();
    return wahl;
  }

  /* Datei hinter einem Knopf (Dokument, Fotos zur Meldung): daneben, was gewählt ist, und „Auswahl entfernen“. Das
     Dateifeld behält die Dateien – gelesen wird wie bisher input.files. */
  const dateiKnopf = (id, text, accept, mehrere) => `<div class="mat-dateiwahl"><label class="btn secondary mat-bildwahl-knopf">${text}<input type="file"
      id="${id}" accept="${esc(accept)}" class="mat-datei"${mehrere ? " multiple" : ""} aria-describedby="${id}-name"></label>
      <span class="mat-dateiwahl-name" id="${id}-name" aria-live="polite"></span>
      <button type="button" class="btn secondary mat-dateiwahl-weg" hidden>Auswahl entfernen</button></div>`;
  function dateiKnopfVerdrahten(body, id) {
    const eingabe = $(`#${id}`, body);
    const name = $(`#${id}-name`, body);
    const weg = $(".mat-dateiwahl-weg", eingabe.closest(".mat-dateiwahl"));
    const zeichnen = () => {
      const liste = Array.from(eingabe.files);
      name.textContent = !liste.length ? (eingabe.multiple ? "keine Dateien gewählt" : "keine Datei gewählt")
        : liste.map((f) => `${f.name} (${groesse(f.size)})`).join(", ");
      name.classList.toggle("gewaehlt", !!liste.length);
      weg.hidden = !liste.length;
    };
    eingabe.addEventListener("change", zeichnen);
    weg.addEventListener("click", () => { eingabe.value = ""; zeichnen(); eingabe.focus(); });
    zeichnen();
  }

  /* Bildschirmtastatur: Bei Nummern (Serien-, Artikelnummer, Norm, Versionsstand) groß schreiben, nichts
     „korrigieren“, keine Rechtschreibprüfung und keine Vorschläge aus früheren Eingaben – sonst macht iOS aus „ab12 c“
     gern „Ab12 C“ oder ein Wort. Namen (Hersteller, Modell) und Suchen: nur nichts korrigieren; Adressen: Tastatur
     für Adressen, klein. */
  const TASTATUR_NUMMER = 'autocapitalize="characters" autocorrect="off" spellcheck="false" autocomplete="off"';
  const TASTATUR_NAME = 'autocorrect="off" spellcheck="false"';
  const TASTATUR_SUCHE = 'autocorrect="off" spellcheck="false" enterkeyhint="search"';
  const TASTATUR_ADRESSE = 'inputmode="url" autocapitalize="off" autocorrect="off" spellcheck="false" autocomplete="off"';

  /* Hinweise, die nur im title stehen, sieht ohne Maus niemand. Dort zeigt ein Tipp auf ein nicht bedienbares Element
     mit title – farbige Zahlen in Baum und Schublade, Marken wie „kritisch“ oder „DEMO“, gekürzte Prüfsummen – den
     Text als Meldung. Ein gesperrtes Auswahlkästchen nimmt keinen Tipp an (material.css lässt ihn zur Zelle durch);
     die Zelle sagt, warum es gesperrt ist. */
  const OHNE_HOVER = window.matchMedia("(hover: none)");
  document.addEventListener("click", (e) => {
    if (!OHNE_HOVER.matches || e.defaultPrevented || !(e.target instanceof Element)) return;
    const zelle = e.target.closest("td.mat-wahlspalte");
    const gesperrt = zelle && $("input:disabled[title]", zelle);
    if (gesperrt) { toast(gesperrt.title); return; }
    const t = e.target.closest("[title]");
    if (!t || !t.title || !t.closest("#mat, #mat-side, #dlg") || t.closest("a, button, input, select, textarea, label, summary, [data-act]")) return;
    toast(t.title);
  });

  function ordnerDialog(o, parentId) {
    const neu = !o.id;
    const oben = neu && !parentId;
    dialog(`<h2>${neu ? (oben ? "Gliederung anlegen" : "Ordner anlegen") : "Ordner bearbeiten"}</h2>
      <label for="od-name">Name</label><input type="text" id="od-name" value="${esc(o.name || "")}" maxlength="120">
      <div class="field-row">
        <div><label for="od-kind">Art</label><select id="od-kind" ${oben || o.kind === "gliederung" ? "disabled" : ""}>
          ${Object.entries(ORDNERART).map(([k, t]) => `<option value="${k}" ${(o.kind || "standort") === k ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
          ${o.kind === "gliederung" && !neu ? '<div class="help">Eine Gliederung bleibt eine Gliederung.</div>' : ""}</div>
        <div><label for="od-int">Prüfintervall (Monate)</label><input type="number" id="od-int" min="1" max="120" value="${o.interval_months || ""}" placeholder="vom Produkt">
          <div class="help">Nur zum Verschärfen: Gilt die Herstellervorgabe kürzer, gilt sie.</div></div>
      </div>
      <label for="od-desc">Beschreibung</label><textarea id="od-desc" rows="3" maxlength="2000">${esc(o.description || "")}</textarea>
      ${fotoFeld("od-foto", "Foto", "Foto", o.foto ? o.vorschau || o.foto : "", "JPEG, PNG, WebP oder HEIC vom Telefon; Web- und Vorschaufassung entstehen beim Hochladen.")}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="od-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
    (dlg, body) => {
      fokus($("#od-name", body));
      const fotoWahl = fotoFeldVerdrahten(dlg, body, "od-foto");
      // Erst die Angaben, dann das Foto. Scheitert nur das Foto, kennt der Dialog den Ordner schon: Ein zweiter Klick
      // speichert die Angaben erneut und lädt das Foto nach, statt den Ordner doppelt anzulegen (wie beim Produktbild).
      let oid = o.id || null;
      $("#od-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        knopf.disabled = true;
        const daten = { name: $("#od-name", body).value, kind: oben ? "gliederung" : $("#od-kind", body).value,
                        interval_months: $("#od-int", body).value || null, description: $("#od-desc", body).value };
        if (!neu && o.kind === "gliederung") daten.kind = "gliederung";
        const foto = fotoWahl.datei;
        try {
          const r = oid ? await api(`${API}/ordner/${oid}`, { method: "PUT", body: daten })
                        : await api(`${API}/ordner`, { method: "POST", body: Object.assign(daten, { parent_id: parentId || null }) });
          oid = r.ordner.id;
          if (foto) {
            const fd = new FormData();
            fd.append("file", foto);
            await api(`${API}/ordner/${oid}/foto`, { method: "POST", body: fd });
          } else if (fotoWahl.entfernen) {
            await api(`${API}/ordner/${oid}/foto`, { method: "DELETE" });
          }
          dlg.close();
          location.href = `/material/ordner/${oid}`;
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  async function ordner() {
    const id = DATEN.id;
    let filter = "";
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    async function zeichnen() {
      const q = sortParameter(new URLSearchParams({ seite, pro_seite: 200 }), sort);
      if (filter) q.set("status", filter);
      const d = (await api(`${API}/ordner/${id}?${q}`)).ordner;
      leisteMarkieren(d.id);
      const system = !!d.system_kind;
      const darfPflegen = DARF.verwalten && !system;
      const z = d.zaehlung || {};
      const bc = d.pfad.map((p, i) => i === d.pfad.length - 1 ? `<span>${esc(p.name)}</span>` : `<a href="/material/ordner/${p.id}">${esc(p.name)}</a>`).join(" / ");
      inhalt.innerHTML = `<div class="mat-pfad"><a href="/material/bestand">Bestand</a> / ${bc}</div>
        <div class="page-head"><h1>${system ? "🔒 " : ""}${esc(d.name)} ${system ? "" : `<span class="mat-art">${esc(ORDNERART[d.kind])}</span>`}${demoMarke(d.demo)}</h1>
          <div class="btn-row">${darfPflegen ? `<button class="btn secondary small" data-act="unterordner">+ Unterordner</button>
            <a class="btn secondary small" href="/material/artikel/neu?ordner=${d.id}">+ Artikel</a>
            <button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>
            <button class="btn secondary small" data-act="verschieben">Verschieben</button><button class="btn secondary small" data-act="loeschen">Löschen</button>` : ""}
            ${DARF.lesen ? exportMenue(d) : ""}</div></div>
        ${system ? `<p class="notice">${d.system_kind === "gesperrt" ? "Hierher verschiebt eine Sperre die Artikel der Gliederung. Zurück in ihren Herkunftsordner bringt sie nur eine Freiprüfung." : "Ausgesonderte Artikel bleiben hier mit ihrem vollen Lebenslauf sichtbar, zählen aber nirgends mehr als Bestand und lassen sich nicht zurückholen."}</p>` : ""}
        ${d.foto || d.description || d.interval_months ? `<div class="mat-ordnerkopf">${d.foto ? bildLink(d.foto, d.original, `Ordnerfoto ${d.name}`, null, `<img class="mat-ordnerfoto" src="${esc(d.vorschau)}" alt="">`) : ""}
          <div>${d.description ? `<p class="mat-text">${esc(d.description)}</p>` : ""}
          ${d.interval_months ? `<p class="small">Prüfintervall hier: höchstens ${d.interval_months} Monate.</p>` : ""}</div></div>` : ""}
        ${d.unterordner.length ? `<section class="section"><h2>Unterordner</h2>${unterordnerHtml(d.unterordner)}</section>` : ""}
        <section class="section"><h2>Artikel in diesem Ordner</h2>
          <div class="c-tabs mat-filter">${["", "ueberfaellig", "neu", "bald_faellig", "gesperrt", "lebensdauer", "einsatzbereit"].map((s) => `<button type="button" data-act="filter" data-f="${s}" class="${s === filter ? "sel" : ""}">${s ? esc(STATUS[s]) : "alle"}${s && d.direkt && d.direkt[s] ? ` (${d.direkt[s]})` : ""}</button>`).join("")}</div>
          ${d.artikel.length ? artikelTabelle(d.artikel, { auswahl: darfPflegen, pruefen: DARF.pruefen && d.system_kind !== "ausgesondert", sort }) : leer(filter ? "Keine Artikel mit diesem Status." : "Hier liegen keine Artikel.")}
          ${seitenleiste(d.artikel_gesamt, seite, d.pro_seite)}
          ${darfPflegen ? '<div class="mat-sammel" id="mat-sammel" hidden><span id="mat-sammel-n"></span><button class="btn secondary small" data-act="sammel-verschieben">Verschieben nach …</button></div>' : ""}
        </section>
        <p class="small mat-zweigbestand">${system ? plural(Object.values(z).reduce((a, b) => a + b, 0), "Artikel", "Artikel") : `Bestand im ganzen Zweig: <strong>${d.bestand}</strong> ${zahlen(z)}`}</p>
        <details class="section mat-auf"><summary>Journal des Ordners</summary>${journalHtml(d.journal)}</details>`;
      const sammel = () => {
        const n = $$(".mat-wahl-art:checked", inhalt).length;
        const leiste = $("#mat-sammel");
        if (!leiste) return;
        leiste.hidden = !n;
        $("#mat-sammel-n").textContent = `${plural(n, "Artikel", "Artikel")} ausgewählt`;
      };
      $$(".mat-wahl-art", inhalt).forEach((c) => c.addEventListener("change", sammel));
      const alle = $("#mat-alle", inhalt);
      if (alle) alle.addEventListener("change", () => { $$(".mat-wahl-art:not(:disabled)", inhalt).forEach((c) => { c.checked = alle.checked; }); sammel(); });
      aktionen = {
        filter: (b) => { filter = b.dataset.f; seite = 1; zeigen(zeichnen); },
        seite: (b) => { seite = +b.dataset.seite; zeigen(zeichnen); },
        sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); seite = 1; zeigen(zeichnen); },
        unterordner: () => ordnerDialog({ kind: "standort" }, d.id),
        runde: () => rundeDialog(d.id),
        bearbeiten: () => ordnerDialog(d, d.parent_id),
        verschieben: async () => {
          const ziel = await ordnerWaehlen("Ordner verschieben nach …", { ohneZweig: d.id, obersteEbene: d.kind === "gliederung" });
          if (ziel === null) return;
          try { await api(`${API}/ordner/${d.id}/verschieben`, { method: "POST", body: { parent_id: ziel || null } }); toast("Verschoben"); zeigen(zeichnen); }
          catch (e) { toast(e.message, true); }
        },
        loeschen: async () => {
          if (!(await confirm(`Ordner „${d.name}“ löschen? Das geht nur, solange er leer ist.`, "Löschen"))) return;
          try { await api(`${API}/ordner/${d.id}`, { method: "DELETE" }); location.href = d.parent_id ? `/material/ordner/${d.parent_id}` : "/material/bestand"; }
          catch (e) { toast(e.message, true); }
        },
        "sammel-verschieben": async () => {
          const ids = $$(".mat-wahl-art:checked", inhalt).map((c) => +c.value);
          if (!ids.length) return;
          const ziel = await ordnerWaehlen(`${plural(ids.length, "Artikel", "Artikel")} verschieben nach …`);
          if (!ziel) return;
          try { const r = await api(`${API}/artikel/verschieben`, { method: "POST", body: { ids, folder_id: ziel } }); toast(`${plural(r.verschoben, "Artikel", "Artikel")} verschoben`); zeigen(zeichnen); }
          catch (e) { toast(e.message, true); }
        },
      };
    }
    await zeichnen();
  }

  /* --- Produktsuche mit allen Treffern (Artikel anlegen, Meldung zuordnen) ------------------------------
     Alle Treffer in einer scrollbaren Liste unter dem Suchfeld, je 50 vom Server; rückt das Ende der Liste ins Bild,
     kommen die nächsten. Eine Antwort zu einer älteren Eingabe zählt nicht mehr (Zähler je Liste). */
  function trefferLeeren(ziel) {
    ziel._lauf = (ziel._lauf || 0) + 1;
    ziel.innerHTML = "";
    ziel.onscroll = null;
  }
  function produktTreffer(ziel, q, waehlen, leerHtml) {
    trefferLeeren(ziel);
    const lauf = ziel._lauf;
    const liste = [];
    let gesamt = 0;
    let seite = 0;
    let laedt = false;
    ziel.scrollTop = 0;
    const zeile = (p, i) => `<button type="button" class="mat-treffer-zeile" data-i="${i}">
      ${p.vorschau ? `<img class="mat-mini" src="${esc(p.vorschau)}" alt="">` : ""}<strong>${esc(produktName(p))}</strong> <span class="muted">${esc(p.article_no || "")} · ${esc(p.category_name || "")}</span>${demoMarke(p.demo)}</button>`;
    async function mehr() {
      if (laedt || (seite && liste.length >= gesamt)) return;
      laedt = true;
      try {
        const d = await api(`${API}/produkte?q=${encodeURIComponent(q)}&pro_seite=50&seite=${seite + 1}`);
        if (lauf !== ziel._lauf) return;
        seite += 1;
        gesamt = d.gesamt;
        const start = liste.length;
        liste.push(...d.produkte);
        if (!liste.length) { ziel.innerHTML = leerHtml; return; }
        const fuss = $(".mat-treffer-fuss", ziel);
        if (fuss) fuss.remove();
        ziel.insertAdjacentHTML("beforeend", d.produkte.map((p, i) => zeile(p, start + i)).join("")
          + `<p class="help mat-treffer-fuss">${liste.length < gesamt ? `${liste.length} von ${gesamt} Treffern – weiter scrollen …` : plural(gesamt, "Treffer", "Treffer")}</p>`);
      } catch (e) {
        if (lauf === ziel._lauf) ziel.innerHTML = `<p class="error">${esc(e.message)}</p>`;
        return;
      } finally { laedt = false; }
      // Füllt eine Seite den Kasten nicht (große Bildschirme), gleich die nächste holen.
      if (lauf === ziel._lauf && liste.length < gesamt && ziel.scrollHeight <= ziel.clientHeight + 60) mehr();
    }
    ziel.onscroll = () => { if (ziel.scrollTop + ziel.clientHeight >= ziel.scrollHeight - 160) mehr(); };
    ziel.onclick = (e) => { const b = e.target.closest(".mat-treffer-zeile"); if (b && liste[+b.dataset.i]) waehlen(liste[+b.dataset.i]); };
    mehr();
  }

  /* --- Export (Lieferung 4) ----------------------------------------------------------------------------
     Ordner: Artikelliste als CSV und alle Protokolle als ZIP; Artikel: Lebenslauf als PDF. Gewöhnliche Links,
     kein fetch – der Server prüft das Leserecht selbst und zeigt einen Fehler als Seite. Ein Download lässt die
     Seite stehen; damit niemand doppelt klickt, während das ZIP entsteht, sagt ein Hinweis, dass es kommt. */
  // Export eines Ordners als Untermenü im Ordnerkopf: Knopf „Export“, darunter die beiden Downloads mit einem Satz,
  // was drinsteckt. <details> öffnet und schließt ohne eigenes Skript (auch per Tastatur und Touch).
  const exportMenue = (d) => `<details class="mat-menue">
      <summary class="btn secondary small" aria-haspopup="true">Export</summary>
      <div class="mat-menue-liste">
        <a href="/material/export/${d.id}.csv" data-export="Die Artikelliste wird heruntergeladen …"><strong>Artikelliste (CSV)</strong>
          <span>Alle Artikel hier und darunter, auch die von hier gesperrten (ausgesonderte bei ihrer Gliederung), mit Status, Fälligkeiten und Stammdaten – für Excel.</span></a>
        <a href="/material/export/${d.id}-protokolle.zip" data-export="Die Protokolle werden zusammengestellt – bei vielen dauert das einen Moment …"><strong>Protokolle (ZIP)</strong>
          <span>Die Protokolle dieser Artikel und die Sammelprotokolle der Durchgänge hier, mit Verzeichnis und Prüfsummen.</span></a>
      </div></details>`;
  const LEBENSLAUF_TEXT = "Stammdaten, alle Prüfungen in zeitlicher Reihenfolge, Prüfdurchgänge und Ereignisse als PDF – zum Weitergeben oder als Aussonderungsnachweis. Stand jetzt, nicht festgeschrieben.";
  const lebenslaufKnopf = (a) => `<a class="btn secondary small" href="/material/artikel/${a.id}/lebenslauf.pdf" target="_blank" rel="noopener"
    title="${LEBENSLAUF_TEXT}">Lebenslauf (PDF)</a>`;
  document.addEventListener("click", (e) => {
    const l = e.target.closest("a[data-export]");
    if (!l || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    toast(l.dataset.export);
  });
  // Untermenüs (details.mat-menue): ein Klick daneben, auf einen Eintrag oder Escape schließt. Beim Öffnen steht die
  // Liste rechtsbündig unter dem Knopf – ragte sie dabei aus dem Bild (am Telefon steht der Knopf irgendwo in der
  // umgebrochenen Knopfzeile), rückt sie so weit, dass sie mit 8 px Abstand ganz hineinpasst.
  document.addEventListener("click", (e) => {
    $$("details.mat-menue[open]").forEach((m) => {
      if (!m.contains(e.target) || e.target.closest(".mat-menue-liste a")) m.open = false;
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    $$("details.mat-menue[open]").forEach((m) => { m.open = false; $("summary", m).focus(); });
  });
  document.addEventListener("toggle", (e) => {
    const m = e.target;
    if (!(m instanceof HTMLDetailsElement) || !m.classList.contains("mat-menue") || !m.open) return;
    const liste = $(".mat-menue-liste", m);
    const knopf = m.getBoundingClientRect();
    const breite = liste.offsetWidth;
    const rand = document.documentElement.clientWidth;
    const links = Math.max(8, Math.min(knopf.right - breite, rand - 8 - breite));
    liste.style.right = "auto";
    liste.style.left = `${Math.round(links - knopf.left)}px`;
  }, true);

  /* --- Artikel --------------------------------------------------------------------------------------- */
  async function artikel() {
    const a = (await api(`${API}/artikel/${DATEN.id}`)).artikel;
    leisteMarkieren(a.folder_id);
    const p = a.produkt;
    const frei = a.lock_state === "frei";
    const darfPflegen = DARF.verwalten && a.lock_state !== "ausgesondert";
    const aus = a.lock_state === "ausgesondert";
    const gesperrt = a.lock_state === "gesperrt" || a.lock_state === "verloren";
    const eigenerEntwurf = a.entwurf && a.entwurf.pruefer_id === DARF.uid;
    const fremderEntwurf = a.entwurf && !eigenerEntwurf;
    const iv = a.intervall || {};
    const ld = a.lebensdauer;
    let ldText = '<span class="muted">keine festgeschriebene Lebensdauer</span>';
    if (ld && ld.festgeschrieben) {
      ldText = ld.rest_tage > 0 ? `${esc(fmtTag(ld.ende))} <span class="muted">(noch ${plural(ld.rest_tage, "Tag", "Tage")}; ${ld.vorgezogen ? "von Hand vorgezogen" : `${ld.jahre} Jahre ab Herstellung`})</span>`
        : `<strong class="mat-warn">erreicht am ${esc(fmtTag(ld.ende))}</strong>`;
    } else if (ld) {
      ldText = `Herstellerangabe ${ld.jahre} Jahre${ld.quelle ? ` (${esc(ld.quelle)})` : ""} <span class="muted">– bei „${esc(MATERIALART[p.material_kind])}“ kein festgeschriebenes Lebensende</span>`;
    }
    const ivText = iv.monate ? `${iv.monate} Monate <span class="muted">(${esc(iv.quelle || "")}${iv.organisation && iv.organisation[0] && iv.hersteller && iv.hersteller[0] && iv.organisation[0] > iv.hersteller[0] ? ` – ${esc(iv.organisation[1])} wollte ${iv.organisation[0]}, die Herstellervorgabe ist kürzer` : ""})</span>` : '<span class="mat-warn">kein Intervall</span>';
    const bc = a.pfad.map((o) => `<a href="/material/ordner/${o.id}">${esc(o.name)}</a>`).join(" / ");
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    inhalt.innerHTML = `${p.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen. Dieses Produkt stammt aus den Demodaten.</p>' : ""}
      ${a.status === "ausgesondert" ? `<p class="mat-banner s-ausgesondert">AUSGESONDERT – dieser Artikel ist außer Dienst und darf nicht mehr verwendet werden.</p>` : ""}
      ${a.status === "gesperrt" ? `<p class="mat-banner s-gesperrt">GESPERRT${a.lock_reason ? ` – ${esc(a.lock_reason)}` : ""}. Nicht verwenden, bis eine Freiprüfung ihn freigibt.</p>` : ""}
      ${a.status === "lebensdauer" ? `<p class="mat-banner s-lebensdauer">LEBENSDAUER ERREICHT – aussondern.</p>` : ""}
      ${a.status === "neu" ? '<p class="mat-banner s-neu">NEU – die Eingangsprüfung steht aus. Bis dahin nicht einsetzen.</p>' : ""}
      ${rueckrufBanner(a)}
      <div class="mat-pfad">${bc}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? bildLink(p.bild, p.original, `Produktbild ${produktName(p)}`, null, `<img class="mat-produktbild" src="${esc(p.bild)}" alt="Produktbild ${esc(produktName(p))}">`) : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel">
          <h1>${esc(a.inventory_no)} ${statusMarke(a.status, true)}</h1>
          <p class="mat-produktzeile"><a href="/material/katalog/produkt/${p.id}">${esc(produktName(p))}</a>${p.article_no ? ` · Art.-Nr. ${esc(p.article_no)}` : ""}</p>
          <p>Seriennummer <strong>${esc(a.serial_no)}</strong>${a.serial_generated ? ' <span class="badge grey">vom System vergeben</span><span class="help mat-sn-hinweis">Der Hersteller vergibt keine Seriennummer – diese Nummer bitte dauerhaft am Artikel anbringen.</span>' : ""}</p>
          <div class="btn-row mat-pruefknoepfe">${!aus && DARF.pruefen && !fremderEntwurf ? `<button class="btn" data-act="pruefen">${eigenerEntwurf ? "Prüfung fortsetzen" : a.status === "neu" ? "Eingangsprüfung starten" : "Prüfung starten"}</button>` : ""}
            ${frei && DARF.pruefen && !a.entwurf ? '<button class="btn secondary small" data-act="sperren">Sperren</button>' : ""}
            ${gesperrt && DARF.verwalten && !a.entwurf ? '<button class="btn secondary small" data-act="aussondern">Aussondern</button>' : ""}</div>
          ${a.entwurf ? `<p class="small">In Prüfung bei <strong>${esc(a.entwurf.pruefer)}</strong> seit ${esc(fmtZeit(a.entwurf.seit))}
            ${fremderEntwurf ? ` · <a href="/material/pruefung/${a.entwurf.id}">ansehen</a>` : ""}
            ${fremderEntwurf && DARF.verwalten ? ' · <button class="lnk" type="button" data-act="freigeben">Reservierung freigeben</button>' : ""}</p>` : ""}
          ${aus || DARF.pruefen ? "" : DARF.pruefer_haekchen ? `<p class="notice small">${URKUNDE_IM_PROFIL}</p>`
            : '<p class="small muted">Prüfen dürfen Prüfer mit Urkundennummer (Häkchen „Prüfer“ in der Nutzerverwaltung, Urkundennummer im eigenen Profil).</p>'}
          ${a.durchgang ? `<p class="small">Steht im Prüfdurchgang <a href="/material/durchgang/${a.durchgang.id}">${esc(a.durchgang.titel)}</a>.</p>` : ""}
          <div class="btn-row">${darfPflegen ? `<button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>${frei ? '<button class="btn secondary small" data-act="verschieben">Verschieben</button>' : ""}${a.darf_loeschen ? '<button class="btn secondary small" data-act="loeschen">Löschen</button>' : ""}` : ""}${DARF.lesen ? lebenslaufKnopf(a) : ""}</div>
          ${DARF.lesen ? `<p class="help mat-nur-touch">Lebenslauf (PDF): ${LEBENSLAUF_TEXT}</p>` : ""}
        </div>
      </div>
      <div class="mat-spalten">
        <section class="section"><h2>Stammdaten</h2><dl class="mat-daten">
          ${zeile("Produkt", `${esc(produktName(p))}${p.norm ? ` · ${esc(p.norm)}` : ""}`)}
          ${zeile("Materialart", esc(MATERIALART[p.material_kind] || p.material_kind))}
          ${zeile("Gliederung", a.gliederung ? `<a href="/material/ordner/${a.gliederung.id}">${esc(a.gliederung.name)}</a>` : "–")}
          ${zeile("Herstellung", a.manufactured_on ? esc(fmtTag(a.manufactured_on)) : '<span class="muted">–</span>')}
          ${zeile("Kauf", a.purchased_on ? esc(fmtTag(a.purchased_on)) : '<span class="muted">–</span>')}
          ${zeile("Erstgebrauch", a.first_use_on ? esc(fmtTag(a.first_use_on)) : '<span class="muted">–</span>')}
          ${zeile("Lebensende", ldText)}
          ${zeile("Nächste Prüfung", aus ? '<span class="muted">–</span>' : gesperrt ? '<span class="muted">setzt die Freiprüfung</span>' : a.status === "neu" ? '<strong>Eingangsprüfung ausstehend</strong>' : a.next_due_on ? `<strong>${esc(fmtTag(a.next_due_on))}</strong>` : '<span class="mat-warn">keine</span>')}
          ${zeile("Zuletzt geprüft", a.last_inspected_on ? esc(fmtTag(a.last_inspected_on)) : '<span class="muted">noch nie</span>')}
          ${zeile("Prüfintervall", ivText)}
          ${zeile("Prüfformular", a.formular ? `${esc(a.formular.title || "ohne Titel")} · Version ${a.formular.version} <span class="muted">(${esc(a.formular.quelle)}, ${plural(a.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span>` : '<span class="mat-warn">kein aktives Prüfformular – im Katalog anlegen</span>')}
          ${a.notes ? zeile("Bemerkung", `<span class="mat-text">${esc(a.notes)}</span>`) : ""}
        </dl></section>
        <section class="section"><h2>QR-Code und NFC</h2>
          <p class="help">Diese Adresse öffnet nach der Anmeldung diesen Artikel. Kopiere sie und schreibe sie auf einen NFC- oder RFID-Tag oder drucke sie mit einem beliebigen Etikettenprogramm als QR-Code – die Kamera-App des Telefons öffnet sie.</p>
          <div class="mat-qr"><input type="text" readonly value="${esc(a.qr_adresse)}" id="mat-qr" aria-label="Adresse für QR, NFC und RFID">
          <button class="btn secondary small" data-act="qr-kopieren">Kopieren</button></div>
          <h2>Herstellerdokumente</h2>
          ${a.dokumente.length ? dokListe(a.dokumente, true) : leer("Am Produkt und seiner Kategorie sind keine Dokumente hinterlegt.")}
        </section>
      </div>
      <section class="section"><h2>Prüfungen</h2>${pruefListe(a.pruefungen)}</section>
      <section class="section"><h2>Journal</h2><p class="help">Änderungen am Artikel und an seinem Produkt, neueste zuerst.</p>${journalHtml(a.journal, true)}</section>`;
    aktionen = {
      "qr-kopieren": async () => {
        const feld = $("#mat-qr");
        try { await navigator.clipboard.writeText(feld.value); toast("Adresse kopiert"); }
        catch (e) { feld.select(); document.execCommand && document.execCommand("copy"); toast(`Adresse markiert – ${kopierText()}`); }
      },
      bearbeiten: () => artikelDialog(a),
      pruefen: () => { location.href = eigenerEntwurf ? `/material/pruefung/${a.entwurf.id}` : `/material/artikel/${a.id}/pruefung/neu`; },
      sperren: () => sperrDialog(a),
      "rr-sperren": (b) => sperrDialog(a, { grund: "rueckruf", text: ((a.rueckrufe || []).find((r) => r.id === +b.dataset.id) || {}).title }),
      aussondern: () => aussonderDialog(a),
      freigeben: () => reservierungFreigeben(a.entwurf.id, a.entwurf.pruefer, () => zeigen(artikel)),
      verschieben: async () => {
        const ziel = await ordnerWaehlen("Artikel verschieben nach …");
        if (!ziel) return;
        try { await api(`${API}/artikel/verschieben`, { method: "POST", body: { ids: [a.id], folder_id: ziel } }); toast("Verschoben"); zeigen(artikel); }
        catch (e) { toast(e.message, true); }
      },
      loeschen: async () => {
        if (!(await confirm(`Artikel ${a.inventory_no} löschen? Das ist nur für falsch angelegte Artikel ohne Prüfung gedacht; die Inventarnummer wird nicht wieder vergeben.`, "Löschen"))) return;
        try { await api(`${API}/artikel/${a.id}`, { method: "DELETE" }); location.href = `/material/ordner/${a.folder_id}`; }
        catch (e) { toast(e.message, true); }
      },
    };
  }

  /* Prüfungen eines Artikels, neueste zuerst – der Prüfteil des Lebenslaufs. Je festgeschriebenem Eintrag das
     Protokoll (PDF im neuen Tab); ein durch eine Berichtigung ersetztes Original steht grau mit „berichtigt“. */
  function pruefListe(liste) {
    if (!liste || !liste.length) return leer("Noch keine Prüfung.");
    return `<table class="list mat-tabelle mat-pruefliste"><thead><tr><th>Datum</th><th>Art</th><th>Ergebnis</th><th>Prüfer</th><th>Nächste Prüfung</th><th>Protokoll</th></tr></thead><tbody>
      ${liste.map((x) => {
        const ersetzt = x.berichtigt_durch && !x.berichtigt_durch.entwurf;
        return `<tr class="${x.entwurf ? "mat-entwurf" : ersetzt ? "mat-alt" : ""}"><td data-l="Datum"><a href="/material/pruefung/${x.id}">${x.entwurf ? "Entwurf" : esc(fmtTag(x.datum))}</a></td>
        <td data-l="Art">${esc(PRUEFART_KURZ[x.art] || x.art)}${x.berichtigt ? ' <span class="mat-marke-ber">Berichtigung</span>' : ""}${ersetzt ? ` <span class="badge grey" title="berichtigt durch ${esc(x.berichtigt_durch.protokoll_id || "eine spätere Prüfung")}">berichtigt</span>` : ""}</td>
        <td data-l="Ergebnis">${x.entwurf ? '<span class="muted">in Prüfung</span>' : ergebnisMarke(x.ergebnis)}${x.grund ? `<div class="small muted">${esc(x.grund)}</div>` : ""}</td>
        <td data-l="Prüfer">${esc(x.pruefer || "")}${x.urkunde ? ` <span class="muted small">(${esc(x.urkunde)})</span>` : ""}</td>
        <td data-l="Nächste Prüfung">${x.naechste ? esc(fmtTag(x.naechste)) : '<span class="muted">–</span>'}</td>
        <td data-l="Protokoll">${x.protokoll ? `<a class="mat-pdf" href="${esc(x.protokoll.url)}" target="_blank" rel="noopener" title="Protokoll ${esc(x.protokoll.id)} öffnen (PDF)">PDF</a> <span class="muted small mat-hash">${esc(x.protokoll.id)}</span>` : '<span class="muted">–</span>'}</td></tr>`;
      }).join("")}</tbody></table>`;
  }
  const ergebnisMarke = (e) => (e ? `<span class="mat-ergebnis-marke e-${esc(e)}">${esc(ERGEBNIS[e] || e)}</span>` : "");

  // vorgabe: { grund, text } – etwa aus dem Rückruf-Banner (Grund „Rückruf“, Titel des Rückrufs).
  function sperrDialog(a, vorgabe) {
    vorgabe = vorgabe || {};
    dialog(`<h2>${esc(a.inventory_no)} sperren</h2>
      <p class="help">Sperren ohne Prüfung – nach Sturzbelastung, Beschädigung, bei Verlust oder bei einem Rückruf des Herstellers. Der Artikel wandert nach „Gesperrt“ seiner Gliederung; zurück bringt ihn nur eine Freiprüfung mit „einsatzbereit“.</p>
      <label for="sd-grund">Grund</label><select id="sd-grund">${Object.entries(SPERRGRUND).map(([k, v]) => `<option value="${k}"${k === vorgabe.grund ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
      <label for="sd-text">Was ist passiert?</label><input type="text" id="sd-text" maxlength="300" placeholder="z. B. Sturz in die Rettungskette, Schnitt am Band" value="${esc(vorgabe.text || "")}">
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="sd-ok" type="button">Sperren</button></div>`,
    (dlg, body) => {
      $("#sd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try { await api(`${API}/artikel/${a.id}/sperren`, { method: "POST", body: { grund: $("#sd-grund", body).value, text: $("#sd-text", body).value } }); dlg.close(); toast("Gesperrt"); zeigen(artikel); }
        catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* Aussonderung durch den Materialwart: wird mit seiner Unterschrift festgeschrieben (Aussonderungsprotokoll).
     Fehlt sie, unterschreibt er im Dialog – vorab mit „Unterschreiben“ oder spätestens beim Aussondern. */
  function aussonderDialog(a) {
    const heute = new Date();
    const tag = `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, "0")}-${String(heute.getDate()).padStart(2, "0")}`;
    const HINWEIS = "Die Aussonderung wird mit deiner Unterschrift festgeschrieben. Sie wird in deinem Profil gespeichert und als Kopie ins Aussonderungsprotokoll übernommen.";
    dialog(`<h2>${esc(a.inventory_no)} aussondern</h2>
      <p class="help">Die Aussonderung ist endgültig: Der Artikel wandert nach „Ausgesondert“, bleibt dort mit seinem Lebenslauf sichtbar und zählt nirgends mehr als Bestand.</p>
      <div class="field-row"><div><label for="au-grund">Grund</label><select id="au-grund">${Object.entries(AUSSONDERUNGSGRUND).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
        <div><label for="au-datum">Datum</label><input type="date" id="au-datum" value="${tag}" max="${tag}"></div></div>
      <label for="au-bem">Bemerkung</label><textarea id="au-bem" rows="3" maxlength="2000"></textarea>
      <p class="help">Die Aussonderung wird mit deiner Unterschrift festgeschrieben (Aussonderungsprotokoll).</p>
      <div id="au-us"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="au-ok" type="button">Aussondern</button></div>`,
    (dlg, body) => {
      async function usZeigen() {
        const ziel = $("#au-us", body);
        if (!DARF.unterschrift) {
          ziel.innerHTML = `<div class="mat-us-fehlt"><span>Dir fehlt noch eine Unterschrift. Ohne sie lässt sich nicht aussondern.</span>
            <button type="button" class="btn secondary small" id="au-us-knopf">Unterschreiben</button></div>`;
          $("#au-us-knopf", body).onclick = async () => { if (await eigeneUnterschrift(HINWEIS)) usZeigen(); };
          return;
        }
        let bild = null;
        try { bild = await eigenesBild(); } catch (e) { /* dann ohne Bild */ }
        if (!DARF.unterschrift) { usZeigen(); return; }      // im Profil inzwischen entfernt
        ziel.innerHTML = bild ? `<div class="mat-fs-unterschrift"><img src="${esc(bild)}" alt="Deine Unterschrift"><span class="small muted">Deine Unterschrift aus dem Profil</span></div>` : "";
      }
      usZeigen();
      $("#au-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const hatte = DARF.unterschrift;
        if (!(await eigeneUnterschrift(HINWEIS))) return;
        if (!hatte) usZeigen();
        knopf.disabled = true;
        knopf.textContent = "Wird festgeschrieben …";
        try {
          const r = await api(`${API}/artikel/${a.id}/aussondern`, { method: "POST", body: { grund: $("#au-grund", body).value, datum: $("#au-datum", body).value, bemerkung: $("#au-bem", body).value } });
          let prot = null;
          try { prot = (await api(`${API}/pruefungen/${r.aussonderung}`)).pruefung.protokoll; } catch (e) { /* Link genügt */ }
          toast(prot ? `Ausgesondert – Protokoll ${prot.id}` : "Ausgesondert");
          // Im selben Dialog weiter: zur Aussonderung mit ihrem Protokoll; darunter steht der Artikel schon neu.
          dialog(`<h2>${esc(a.inventory_no)} ausgesondert</h2>
            <p>Das Aussonderungsprotokoll ${prot ? `<strong class="mat-hash">${esc(prot.id)}</strong> ` : ""}ist mit deiner Unterschrift festgeschrieben.</p>
            <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button>
              ${prot ? `<a class="btn secondary" href="${esc(prot.url)}" target="_blank" rel="noopener">Protokoll (PDF)</a>` : ""}
              <a class="btn" href="/material/pruefung/${r.aussonderung}" id="au-weiter">Zur Aussonderung</a></div>`,
          // Der Knopf, auf dem der Fokus lag, ist mit dem alten Inhalt weg – sonst fiele er an den Seitenanfang.
          (d2, b2) => $("#au-weiter", b2).focus());
          zeigen(artikel);
        } catch (e) { unterschriftWeg(e); toast(e.message, true); knopf.disabled = false; knopf.textContent = "Aussondern"; if (!DARF.unterschrift) usZeigen(); }
      };
    });
  }

  function artikelDialog(a) {
    const textil = a.produkt.material_kind === "textil";
    dialog(`<h2>Artikel ${esc(a.inventory_no)} bearbeiten</h2>
      <label for="ad-sn">Seriennummer des Herstellers</label><input type="text" id="ad-sn" ${TASTATUR_NUMMER} value="${a.serial_generated ? "" : esc(a.serial_no)}" placeholder="${a.serial_generated ? esc(a.serial_no) + " (vom System)" : ""}" maxlength="80">
      <div class="help">Leer lassen behält die Nummer. Eine echte Herstellernummer ersetzt die vom System vergebene.</div>
      <div class="field-row"><div><label for="ad-herst">Herstellung (Monat${textil ? ", Pflicht" : ""})</label>${datumFeld("ad-herst", a.manufactured_on, "monat")}</div>
        <div><label for="ad-kauf">Kauf (Monat)</label>${datumFeld("ad-kauf", a.purchased_on, "monat")}</div></div>
      <div class="field-row"><div><label for="ad-erst">Erstgebrauch (Monat)</label>${datumFeld("ad-erst", a.first_use_on, "monat")}</div>
        <div><label for="ad-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="ad-int" min="1" max="120" value="${a.interval_months || ""}" placeholder="vom Produkt/Ordner"></div></div>
      <div class="field-row"><div ${a.status === "neu" ? "hidden" : ""}><label for="ad-due">Nächste Prüfung</label>${datumFeld("ad-due", a.next_due_on, "tag")}
          <div class="help">Nur vorziehen – später setzt sie eine Prüfung.</div></div>
        ${textil ? `<div><label for="ad-ende">Lebensende</label>${datumFeld("ad-ende", a.retire_by, "tag")}<div class="help">Nur vorziehen. Leer lassen behält das Lebensende.</div></div>` : "<div></div>"}</div>
      <label for="ad-notes">Bemerkung</label><textarea id="ad-notes" rows="3" maxlength="4000">${esc(a.notes || "")}</textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ad-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
      $("#ad-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        // Ein Tagesdatum (aus der Zeit vor den Monatsfeldern) bleibt erhalten, wenn der Monat derselbe ist.
        const behalten = (neu, alt) => (neu && alt && alt.slice(0, 7) === neu ? alt : neu || null);
        let daten;
        try {
          daten = { stand: a.stand, serial_no: $("#ad-sn", body).value,
                    manufactured_on: behalten(datumWert($("#ad-herst", body), "Herstellung"), a.manufactured_on),
                    purchased_on: behalten(datumWert($("#ad-kauf", body), "Kauf"), a.purchased_on),
                    first_use_on: behalten(datumWert($("#ad-erst", body), "Erstgebrauch"), a.first_use_on),
                    interval_months: $("#ad-int", body).value || null,
                    next_due_on: datumWert($("#ad-due", body), "Nächste Prüfung") || null, notes: $("#ad-notes", body).value };
          if (textil) daten.retire_by = datumWert($("#ad-ende", body), "Lebensende") || null;
        } catch (e) { toast(e.message, true); return; }
        knopf.disabled = true;
        try { await api(`${API}/artikel/${a.id}`, { method: "PUT", body: daten }); dlg.close(); toast("Gespeichert"); zeigen(artikel); }
        catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Artikel anlegen ---------------------------------------------------------------------------- */
  async function artikelNeu() {
    if (!DARF.verwalten) { inhalt.innerHTML = '<p class="error">Artikel legen nur Materialwarte an.</p>'; return; }
    const ordnerListe = (await api(`${API}/ordner`)).ordner;
    const wahl = ordnerListe.filter((o) => !o.system_kind);
    if (!wahl.length) { inhalt.innerHTML = `<h1>Artikel anlegen</h1>${leer("Zuerst unter „Bestand“ eine Gliederung anlegen.")}`; return; }
    leisteMarkieren(DATEN.ordner);
    const kinder = baumKinder(wahl);
    const optionen = (pid, tiefe) => (kinder[pid] || []).map((o) => `<option value="${o.id}" ${o.id === DATEN.ordner ? "selected" : ""}>${EIN.repeat(tiefe)}${esc(o.name)}</option>${optionen(o.id, tiefe + 1)}`).join("");
    let produkt = null;
    inhalt.innerHTML = `<div class="page-head"><h1>Artikel anlegen</h1></div>
      <div class="mat-formular">
        <label for="an-q">Produkt aus dem Katalog</label>
        <div class="mat-produktwahl"><input type="search" id="an-q" placeholder="Hersteller, Modell, Artikelnummer …" autocomplete="off" ${TASTATUR_SUCHE}>
          <div id="an-treffer" class="mat-treffer"></div></div>
        <div id="an-produkt" class="mat-gewaehlt" hidden></div>
        <p class="help">Fehlt das Produkt im Katalog? <button type="button" class="lnk" data-act="melden">Fehlendes Produkt melden</button>
          – ein Produktkatalogpfleger nimmt es auf, du bekommst Bescheid.</p>
        <label for="an-ordner">Ordner</label><select id="an-ordner">${optionen(0, 0)}</select>
        <label for="an-sn">Seriennummer des Herstellers</label><input type="text" id="an-sn" maxlength="80" placeholder="leer lassen, wenn der Hersteller keine vergibt" ${TASTATUR_NUMMER}>
        <div class="help">Ohne Herstellernummer vergibt das System eine eindeutige (STR-…), die dann am Artikel angebracht wird. Die Inventarnummer vergibt immer das System.</div>
        <div class="field-row"><div><label for="an-herst">Herstellung (Monat)</label>${datumFeld("an-herst", "", "monat")}</div>
          <div><label for="an-kauf">Kauf (Monat)</label>${datumFeld("an-kauf", "", "monat")}</div></div>
        <div class="field-row"><div><label for="an-erst">Erstgebrauch (Monat)</label>${datumFeld("an-erst", "", "monat")}</div>
          <div><label for="an-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="an-int" min="1" max="120" placeholder="vom Produkt/Ordner"></div></div>
        <div class="field-row"><div id="an-ende-feld" hidden><label for="an-ende">Lebensende</label>${datumFeld("an-ende", "", "tag")}<div class="help" id="an-ende-hilfe"></div></div>
          <div><p class="help" id="an-due-hilfe"></p></div></div>
        <p class="notice">Neu angelegte Artikel stehen auf <strong>neu</strong>, bis ein Prüfer die Eingangsprüfung gemacht hat – erst sie gibt sie frei und setzt die erste Fälligkeit.</p>
        <label for="an-notes">Bemerkung</label><textarea id="an-notes" rows="2" maxlength="4000"></textarea>
        <div class="btn-row mat-knoepfe"><button class="btn" data-act="anlegen">Anlegen</button>
          <button class="btn secondary" data-act="anlegen-weiter" title="Produkt und Ordner bleiben für den nächsten Artikel stehen">Anlegen und nächsten</button></div>
        <p class="help mat-nur-touch">„Anlegen und nächsten“: Produkt und Ordner bleiben für den nächsten Artikel stehen.</p>
      </div>
      <div id="an-meldungen"></div>`;
    let vorschlagLos = null;
    async function vorschlag() {
      if (!produkt) return;
      const q = new URLSearchParams({ product_id: produkt.id, folder_id: $("#an-ordner").value });
      for (const [k, sel] of [["manufactured_on", "#an-herst"], ["purchased_on", "#an-kauf"], ["first_use_on", "#an-erst"]]) {
        try { const w = datumWert($(sel), ""); if (w) q.set(k, w); } catch (e) { /* noch unvollständig getippt */ }
      }
      if ($("#an-int").value) q.set("interval_months", $("#an-int").value);
      try {
        const v = (await api(`${API}/artikel/vorschlag?${q}`)).vorschlag;
        $("#an-due-hilfe").textContent = v.intervall.monate ? `Prüfintervall ${v.intervall.monate} Monate (${v.intervall.quelle}).` : "Kein Prüfintervall – am Produkt oder in der Kategorie eintragen.";
        const textil = v.material_kind === "textil";
        $("#an-ende-feld").hidden = !textil;
        if (textil) {
          const ende = $("#an-ende");
          if (!ende.dataset.selbst) ende.value = datumAnzeige(v.retire_by, "tag");
          $("#an-ende-hilfe").textContent = v.retire_by ? `${v.lifetime_years} Jahre ab Herstellung; nur vorziehen.` : "Herstellung angeben – bei textilem Material Pflicht.";
        }
      } catch (e) { /* Eingaben unvollständig – der Vorschlag kommt, sobald sie es nicht mehr sind */ }
    }
    const spaeter = () => { clearTimeout(vorschlagLos); vorschlagLos = setTimeout(vorschlag, 250); };
    ["#an-ordner", "#an-herst", "#an-kauf", "#an-erst", "#an-int"].forEach((s) => $(s).addEventListener("change", spaeter));
    $("#an-ende").addEventListener("input", (e) => { e.target.dataset.selbst = "1"; });
    function waehlen(p) {
      produkt = p;
      $("#an-produkt").hidden = false;
      $("#an-produkt").innerHTML = `${p.vorschau ? `<img class="mat-mini" src="${esc(p.vorschau)}" alt="">` : ""}<strong>${esc(produktName(p))}</strong> ${p.article_no ? `<span class="muted">${esc(p.article_no)}</span>` : ""} ${demoMarke(p.demo)}
        <span class="mat-art">${esc(MATERIALART[p.material_kind])}</span> <button class="lnk" type="button" id="an-anders">anderes Produkt</button>`;
      trefferLeeren($("#an-treffer"));
      $("#an-q").value = "";
      $("#an-anders").onclick = () => { produkt = null; $("#an-produkt").hidden = true; fokus($("#an-q")); };
      $("#an-ende").dataset.selbst = "";
      vorschlag();
    }
    let suchLos = null;
    $("#an-q").addEventListener("input", () => {
      clearTimeout(suchLos);
      suchLos = setTimeout(async () => {
        const q = $("#an-q").value.trim();
        if (!q) { trefferLeeren($("#an-treffer")); return; }
        produktTreffer($("#an-treffer"), q, waehlen,
          '<p class="help">Kein Produkt gefunden. <button type="button" class="lnk" data-act="melden">Als fehlendes Produkt melden</button></p>');
      }, 200);
    });
    if (DATEN.produkt) {
      try { waehlen((await api(`${API}/produkte/${DATEN.produkt}`)).produkt); } catch (e) { /* Produkt gibt es nicht mehr */ }
    }
    async function anlegen(weiter) {
      if (!produkt) { toast("Bitte zuerst ein Produkt wählen.", true); return; }
      let daten;
      try {
        daten = { product_id: produkt.id, folder_id: +$("#an-ordner").value, serial_no: $("#an-sn").value,
                  manufactured_on: datumWert($("#an-herst"), "Herstellung") || null, purchased_on: datumWert($("#an-kauf"), "Kauf") || null,
                  first_use_on: datumWert($("#an-erst"), "Erstgebrauch") || null, interval_months: $("#an-int").value || null,
                  notes: $("#an-notes").value };
        if (!$("#an-ende-feld").hidden) daten.retire_by = datumWert($("#an-ende"), "Lebensende") || null;
      } catch (e) { toast(e.message, true); return; }
      try {
        const r = await api(`${API}/artikel`, { method: "POST", body: daten });
        if (!weiter) { location.href = `/material/artikel/${r.artikel.id}`; return; }
        toast(`${r.artikel.inventory_no} angelegt (Seriennummer ${r.artikel.serial_no})`);
        $("#an-sn").value = ""; $("#an-notes").value = "";
        fokus($("#an-sn"));
      } catch (e) { toast(e.message, true); }
    }
    // Die eigenen Meldungen unter dem Formular: Ist eine eingepflegt, wählt ein Klick ihr Produkt.
    async function meldungenZeigen() {
      const ziel = $("#an-meldungen");
      try {
        const liste = (await api(`${API}/meldungen?eigene=1&status=alle`)).meldungen.slice(0, 10);
        ziel.innerHTML = liste.length ? `<section class="section"><h2>Deine Produktmeldungen</h2><ul class="mat-meldeliste">
          ${liste.map((m) => `<li>${meldestatusMarke(m.status)} <strong>${esc(meldungName(m))}</strong>${m.article_no ? ` <span class="muted">${esc(m.article_no)}</span>` : ""}
            <span class="muted small">gemeldet am ${esc(fmtTag(m.created_at))}</span>
            ${m.status === "eingepflegt" && m.produkt ? `<button type="button" class="btn secondary small" data-act="meldung-waehlen" data-pid="${m.produkt.id}">Artikel davon anlegen</button>` : ""}
            ${m.status === "abgelehnt" ? `<div class="small">Abgelehnt: <span class="mat-text">${esc(m.answer)}</span></div>` : ""}</li>`).join("")}</ul>
          <p class="small"><a href="/material/katalog/meldungen">Alle deine Meldungen →</a></p></section>` : "";
      } catch (e) { ziel.innerHTML = ""; }
    }
    aktionen = {
      anlegen: () => anlegen(false), "anlegen-weiter": () => anlegen(true),
      // Vorbelegt aus der Suche: „Hersteller Modell …“ – die meisten tippen den Hersteller zuerst.
      melden: () => {
        const q = $("#an-q").value.trim();
        const teile = q.split(/\s+/).filter(Boolean);
        meldungDialog({ manufacturer: teile.length > 1 ? teile[0] : "", model: teile.length > 1 ? teile.slice(1).join(" ") : q,
                        folder_id: +$("#an-ordner").value || null }, meldungenZeigen);
      },
      "meldung-waehlen": async (b) => {
        try { waehlen((await api(`${API}/produkte/${b.dataset.pid}`)).produkt); window.scrollTo({ top: 0, behavior: "smooth" }); }
        catch (e) { toast(e.message, true); }
      },
    };
    fokus($("#an-q"));
    meldungenZeigen();
  }

  /* --- Katalog ------------------------------------------------------------------------------------- */
  let kategorienCache = null;
  async function kategorienLaden(neu) {
    if (!kategorienCache || neu) kategorienCache = (await api(`${API}/kategorien`)).kategorien;
    return kategorienCache;
  }
  function kategorieOptionen(liste, gewaehlt, ohne) {
    const kinder = {};
    liste.forEach((k) => { (kinder[k.parent_id || 0] = kinder[k.parent_id || 0] || []).push(k); });
    const zweig = (pid, tiefe) => (kinder[pid] || []).filter((k) => k.id !== ohne).map((k) => `<option value="${k.id}" ${k.id === gewaehlt ? "selected" : ""}>${EIN.repeat(tiefe)}${esc(k.name)}</option>${zweig(k.id, tiefe + 1)}`).join("");
    return zweig(0, 0);
  }

  async function katalog() {
    let kategorie = DATEN.kategorie || null;
    let q = "";
    let sort = { feld: null, richtung: "auf" };
    const kats = await kategorienLaden();
    // Endlos: Die erste Seite kommt sofort, jede weitere, sobald das Ende der Liste ins Bild rückt. Jede neue
    // Suche, Sortierung oder Kategorie beginnt einen neuen Lauf; was vom alten noch unterwegs ist, fällt weg.
    const PRO_SEITE = 50;
    let lauf = 0;
    let beobachter = null;
    let nachladen = null;
    const produktZeile = (x) => `<tr><td data-l="Hersteller">${esc(x.manufacturer || "")}</td>
          <td data-l="Produkt">${x.vorschau ? `<img class="mat-mini" src="${esc(x.vorschau)}" alt="" loading="lazy">` : ""}<a href="/material/katalog/produkt/${x.id}"><strong>${esc(x.model || "")}</strong></a>${x.article_no ? ` <span class="muted">${esc(x.article_no)}</span>` : ""}${demoMarke(x.demo)}</td>
          <td data-l="Kategorie">${esc(x.category_name || "")}</td><td data-l="Materialart">${esc(MATERIALART[x.material_kind])}</td>
          <td data-l="Intervall">${x.intervall.monate ? `${x.intervall.monate} Mon.` : "–"}</td>
          <td data-l="Lebensdauer">${x.lifetime_years ? `${x.lifetime_years} J.` : "–"}</td><td data-l="Bestand">${x.bestand}</td></tr>`;
    async function liste() {
      const meinLauf = ++lauf;
      if (beobachter) { beobachter.disconnect(); beobachter = null; }
      const holen = (seite) => {
        const p = sortParameter(new URLSearchParams({ q, seite, pro_seite: PRO_SEITE }), sort);
        if (kategorie) p.set("kategorie", kategorie);
        return api(`${API}/produkte?${p}`);
      };
      const d = await holen(1);
      if (meinLauf !== lauf) return;
      const s = sort;
      const ziel = $("#kat-liste");
      ziel.innerHTML = d.produkte.length ? `<table class="list mat-tabelle"><thead><tr>${sortKopf("Hersteller", "hersteller", s)}${sortKopf("Produkt", "produkt", s)}${sortKopf("Kategorie", "kategorie", s)}${sortKopf("Materialart", "materialart", s)}${sortKopf("Intervall", "intervall", s)}${sortKopf("Lebensdauer", "lebensdauer", s)}${sortKopf("Bestand", "bestand", s)}</tr></thead>
        <tbody>${d.produkte.map(produktZeile).join("")}</tbody></table><p class="help mat-endlos" id="kat-mehr"></p>`
        : leer(q || kategorie ? "Kein Produkt in dieser Auswahl." : "Der Katalog ist noch leer.");
      // War die Liste schon unter der Suchzeile weggescrollt, beginnt die neue Auswahl direkt unter ihr.
      const such = $(".mat-suchzeile");
      if (such && ziel.getBoundingClientRect().top < such.getBoundingClientRect().bottom) {
        window.scrollBy(0, ziel.getBoundingClientRect().top - such.getBoundingClientRect().bottom);
      }
      if (!d.produkte.length) return;
      const mehr = $("#kat-mehr");
      let seite = 1;
      let geladen = d.produkte.length;
      let gesamt = d.gesamt;
      let laedt = false;
      const stand = () => { mehr.textContent = geladen < gesamt ? `${geladen} von ${gesamt} – weitere kommen beim Scrollen` : plural(gesamt, "Produkt", "Produkte"); };
      stand();
      if (geladen >= gesamt) return;
      beobachter = new IntersectionObserver(async (eintraege) => {
        if (laedt || !eintraege.some((e) => e.isIntersecting)) return;
        laedt = true;
        let n;
        try { n = await holen(seite + 1); }
        catch (e) {
          laedt = false;
          if (meinLauf !== lauf || !beobachter) return;
          beobachter.unobserve(mehr);
          mehr.innerHTML = `${esc(e.message)} <button type="button" class="lnk" data-act="kat-mehr">Noch einmal versuchen</button>`;
          return;
        }
        laedt = false;
        if (meinLauf !== lauf || !beobachter) return;
        seite += 1;
        $("tbody", ziel).insertAdjacentHTML("beforeend", n.produkte.map(produktZeile).join(""));
        geladen += n.produkte.length;
        gesamt = n.produkte.length ? n.gesamt : geladen;       // leer: inzwischen sind es weniger geworden
        stand();
        if (geladen >= gesamt) { beobachter.disconnect(); beobachter = null; return; }
        // Steht das Ende nach dem Anhängen noch im Bild (großer Bildschirm), gleich die nächste Seite.
        beobachter.unobserve(mehr);
        beobachter.observe(mehr);
      }, { rootMargin: "0px 0px 600px 0px" });
      beobachter.observe(mehr);
      nachladen = () => { if (beobachter) { stand(); beobachter.observe(mehr); } };
    }
    function zeichnen() {
      const k = kats.find((x) => x.id === kategorie);
      const pfad = [];
      for (let x = k; x; x = kats.find((y) => y.id === x.parent_id)) pfad.unshift(x);
      leisteMarkieren(kategorie);
      // Produkte samt Unterkategorien – dieselbe Zahl wie in der Leiste und wie die Liste darunter.
      const summe = (id) => (kats.find((x) => x.id === id).produkte || 0) + kats.filter((x) => x.parent_id === id).reduce((n, c) => n + summe(c.id), 0);
      const angaben = k ? [k.norm ? esc(k.norm) : "", k.default_material_kind ? `Materialart ${esc(MATERIALART[k.default_material_kind])}` : "",
        k.default_interval_months ? `Prüfintervall ${k.default_interval_months} Monate` : "", plural(summe(k.id), "Produkt", "Produkte")].filter(Boolean).join(" · ") : "";
      // Zum aktiven generischen Formular führt bei Katalogpflegern der Knopf „Generisches Formular“, sonst der Verweis in der Angabenzeile.
      inhalt.innerHTML = `<div class="page-head"><h1>Katalog</h1>
          <div class="btn-row">${DARF.katalog ? '<button class="btn secondary" data-act="kat-export">Katalog exportieren</button><button class="btn secondary" data-act="kat-import">Katalog importieren</button>' : ""}
            ${DARF.lesen || DARF.katalog ? `<a class="btn secondary mat-mit-zahl" href="/material/katalog/meldungen">Meldungen<span class="mat-meldezahl" id="kat-meldungen" hidden></span></a>` : ""}
            ${DARF.katalog ? '<button class="btn secondary" data-act="kat-neu">+ Kategorie</button><button class="btn secondary" data-act="produkt-neu">+ Produkt</button>' : ""}</div></div>
        ${k ? `<div class="mat-katkopf">
            <div class="mat-pfad"><a href="/material/katalog" data-act="kategorie" data-id="">alle Kategorien</a>${pfad.slice(0, -1).map((x) => ` / <a href="/material/katalog?kategorie=${x.id}" data-act="kategorie" data-id="${x.id}">${esc(x.name)}</a>`).join("")}</div>
            <h2>${esc(k.name)} ${demoMarke(k.demo)}</h2>
            <p class="small">${angaben}${!k.aktives_formular ? ' · <span class="muted">kein aktives generisches Prüfformular</span>'
              : DARF.katalog ? "" : ` · <a href="/material/katalog/formular/${k.aktives_formular}">generisches Prüfformular</a>`}</p>
            ${DARF.katalog ? `<div class="btn-row"><button class="btn secondary small" data-act="kat-bearbeiten">Kategorie bearbeiten</button>
              <button class="btn secondary small" data-act="kat-formular">Generisches Formular</button><button class="btn secondary small" data-act="kat-loeschen">Löschen</button></div>` : ""}
            <div class="mat-katdoks"><h3 class="mat-unter">Dokumente für alle Produkte dieser Kategorie</h3>
              <p class="help">Pflegehinweise, allgemeine Anleitungen … – sie gelten für jedes Produkt hier und in den Unterkategorien und stehen dort bei den Herstellerdokumenten.</p>
              <div id="kat-doks"><p class="help">Wird geladen …</p></div>
              ${DARF.katalog ? '<button class="btn secondary small" data-act="dok-neu">+ Dokument</button>' : ""}</div></div>`
          : (kats.length ? "" : leer(DARF.katalog ? "Noch keine Kategorien – mit „+ Kategorie“ anlegen." : "Noch keine Kategorien."))}
        <div class="mat-suchzeile"><input type="search" id="kat-q" placeholder="Produkte suchen: Hersteller, Modell, Artikelnummer, Norm" value="${esc(q)}" autocomplete="off" ${TASTATUR_SUCHE}></div>
        <div id="kat-liste"></div>`;
      let los = null;
      $("#kat-q").addEventListener("input", (e) => { clearTimeout(los); los = setTimeout(() => { q = e.target.value.trim(); zeigen(liste); }, 250); });
      zeigen(liste);
      if (k) zeigenIn(katDoks, "#kat-doks");
      if (DARF.katalog) meldungenZaehlen($("#kat-meldungen"));
    }
    let katDocs = [];
    async function katDoks() {
      katDocs = (await api(`${API}/kategorien/${kategorie}/dokumente`)).dokumente;
      const ziel = $("#kat-doks");
      if (ziel) ziel.innerHTML = katDocs.length ? dokTabelle(katDocs, DARF.katalog) : leer("Noch keine Dokumente an dieser Kategorie.");
    }
    aktionen = {
      kategorie: (b) => katalogWahl(b.dataset.id ? +b.dataset.id : null),
      "kat-mehr": () => { if (nachladen) nachladen(); },
      sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); zeigen(liste); },
      "kat-neu": () => kategorieDialog({ parent_id: kategorie }),
      "kat-bearbeiten": () => kategorieDialog(kats.find((x) => x.id === kategorie)),
      "kat-loeschen": async () => {
        const k = kats.find((x) => x.id === kategorie);
        if (!(await confirm(`Kategorie „${k.name}“ löschen? Das geht nur ohne Unterkategorien und Produkte.`, "Löschen"))) return;
        try { await api(`${API}/kategorien/${k.id}`, { method: "DELETE" }); location.href = "/material/katalog"; } catch (e) { toast(e.message, true); }
      },
      "kat-formular": () => formularFuer({ kategorie_id: kategorie }),
      "produkt-neu": () => produktDialog({ category_id: kategorie }),
      "kat-export": () => katalogExportDialog(),
      "kat-import": () => katalogImportDialog(),
      ...dokAktionen(() => katDocs, () => `${API}/kategorien/${kategorie}/dokumente`, () => zeigenIn(katDoks, "#kat-doks")),
    };
    katalogWahl = (id) => {
      kategorie = id;
      history.replaceState(null, "", kategorie ? `?kategorie=${kategorie}` : location.pathname);
      zeichnen();
    };
    zeichnen();
  }

  /* --- Katalogaustausch (Lieferung 4): Export als ZIP, Import mit Probelauf ----------------------------------
     Export: Der Dialog zeigt erst, was mitkommt und was nicht (DEMO, fehlende Dateien), dann lädt der Knopf das ZIP.
     Import: Datei wählen → Probelauf (der Server schreibt nichts, auch keine Datei) → Bericht → „Übernehmen“ führt
     denselben Import echt aus und zeigt dessen Bericht. Gelöscht wird beim Import nie etwas. */
  const AUSTAUSCH_ARTEN = [["kategorien", "Kategorien"], ["produkte", "Produkte"], ["formulare", "Formulare"],
                           ["bilder", "Bilder"], ["dokumente", "Dokumente"]];
  const austauschListe = (titel, zeilen, art) => (zeilen && zeilen.length ? `<div class="mat-austausch-liste ${art || ""}">
    <strong>${esc(titel)}</strong><ul>${zeilen.map((z) => `<li>${esc(z)}</li>`).join("")}</ul></div>` : "");

  async function katalogExportDialog() {
    let v;
    try { v = (await api(`${API}/katalog/export/vorschau`)).export; } catch (e) { toast(e.message, true); return; }
    const e = v.enthalten, a = v.ausgelassen;
    const zeile = (t, n, raus) => `<tr><th scope="row">${t}</th><td>${n}</td><td>${raus === null ? "–" : raus}</td></tr>`;
    dialog(`<h2>Katalog exportieren</h2>
      <p>Kategorien, Produkte mit Bild und Dokumenten und die Prüfformulare als ZIP – zum Import in einer anderen Instanz,
        etwa von dev in die Produktion. Bestand, Artikel und Prüfungen kommen nie mit, DEMO-Einträge auch nicht.</p>
      <table class="mat-austausch"><thead><tr><th></th><th>im Export</th><th>ausgelassen (DEMO)</th></tr></thead><tbody>
        ${zeile("Kategorien", e.kategorien, a.kategorien)}${zeile("Produkte", e.produkte, a.produkte)}
        ${zeile("davon mit Bild", e.bilder, null)}${zeile("Formulare", e.formulare, a.formulare)}${zeile("Dokumente", e.dokumente, a.dokumente)}
      </tbody></table>
      ${a.ohne_kennzeichen ? `<p class="help">${plural(a.ohne_kennzeichen, "Eintrag", "Einträge")} ohne eigenes DEMO-Kennzeichen fallen mit heraus: Sie stehen in einer DEMO-Kategorie bzw. gehören zu einem DEMO-Ziel.</p>` : ""}
      ${a.namen.length ? `<details class="mat-auf"><summary>DEMO-Einträge (oberste Ebene)</summary><ul class="mat-austausch-aenderungen">${a.namen.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></details>` : ""}
      ${austauschListe("Nicht im Export, weil die Datei hier fehlt", v.fehlende_dateien, "warnung")}
      ${austauschListe("Nicht im Export, weil der Import die Datei nicht annähme (zu groß)", v.zu_gross, "warnung")}
      ${v.ohne_punkte ? `<p class="help">${plural(v.ohne_punkte, "Formularentwurf", "Formularentwürfe")} ohne Prüfpunkte (und ohne aktives Formular) bleibt draußen.</p>` : ""}
      ${v.groesse ? `<p class="help">Dateien zusammen etwa ${esc(groesse(v.groesse))}.${e.bilder ? " Die Produktbilder gehen als Original mit – samt ihren Metadaten." : ""}</p>` : ""}
      ${v.groesse > v.grenze ? `<p class="error">Der Export wäre größer als ${esc(groesse(v.grenze))} – so groß wird er nicht gebaut.</p>` : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        ${v.groesse > v.grenze ? "" : `<a class="btn" id="ke-los" href="${API}/katalog/export" download>Herunterladen</a>`}</div>`,
    (dlg, body) => {
      // Der Download läuft am Dialog vorbei; geschlossen wird, sobald der Browser die Anfrage abgeschickt hat.
      const los = $("#ke-los", body);
      if (los) los.addEventListener("click", () => setTimeout(() => { if (dlg.open) dlg.close(); }, 400));
    });
  }

  function importBerichtHtml(b) {
    const arten = b.version === 2 ? AUSTAUSCH_ARTEN : AUSTAUSCH_ARTEN.slice(0, 3);
    const zeile = ([k, t]) => {
      const z = b[k] || {};
      const geaendert = k === "formulare" ? "–" : (z.geaendert || 0) + (z.neue_version || 0);
      return `<tr><th scope="row">${t}</th><td>${z.neu || 0}</td><td>${geaendert}</td><td>${z.unveraendert || 0}</td></tr>`;
    };
    const stand = b.gespeichert ? '<p class="mat-austausch-stand ok">Übernommen.</p>'
      : b.fehler.length ? '<p class="mat-austausch-stand bad">Nicht übernommen – erst die Fehler beheben.</p>'
        : b.trocken ? '<p class="mat-austausch-stand">Probelauf – noch nichts gespeichert.</p>'
          : '<p class="mat-austausch-stand bad">Nicht gespeichert.</p>';
    const h = b.herkunft || {};
    const nichts = !b.fehler.length && !b.aenderungen.length && !b.hinweise.length;
    return `${stand}
      ${h.quelle || h.erstellt ? `<p class="help">Export von ${esc(h.quelle || "?")}${h.erstellt ? `, erstellt ${esc(fmtZeit(h.erstellt))}` : ""}.</p>` : ""}
      <table class="mat-austausch"><thead><tr><th></th><th>neu</th><th>geändert</th><th>unverändert</th></tr></thead>
        <tbody>${arten.map(zeile).join("")}</tbody></table>
      ${b.version === 2 ? '<p class="help">Eine geänderte Prüfliste wird eine neue Formularversion (zählt als neu); eine neue Dokumentversion zählt als geändert.</p>' : ""}
      ${austauschListe("Fehler", b.fehler, "fehler")}
      ${austauschListe("Achtung – betrifft vorhandene Artikel", b.warnungen, "warnung")}
      ${austauschListe("Hinweis", b.hinweise, "")}
      ${b.aenderungen.length ? `<details class="mat-auf"${b.aenderungen.length <= 12 ? " open" : ""}><summary>Im Einzelnen (${b.aenderungen.length})</summary>
        <ul class="mat-austausch-aenderungen">${b.aenderungen.map((z) => `<li>${esc(z)}</li>`).join("")}</ul></details>` : ""}
      ${nichts && !b.gespeichert ? '<p class="mat-leer">Nichts zu übernehmen – der Katalog hier entspricht schon der Datei.</p>' : ""}`;
  }

  function katalogImportDialog() {
    let datei = null;
    dialog(`<h2>Katalog importieren</h2>
      <p>Ein Katalog-Export (ZIP) oder eine Katalogdatei (JSON). Zuerst läuft ein Probelauf: Er zeigt, was neu ist und was
        sich ändert, und speichert nichts. Übernommen wird erst mit „Übernehmen“. Gelöscht wird beim Import nie etwas.</p>
      <div class="mat-ablage" id="ki-ablage">
        <p><strong>Datei hierher ziehen</strong> oder <label class="btn secondary small">Datei wählen<input type="file" id="ki-datei" class="mat-datei" accept=".zip,.json,application/zip,application/json"></label></p>
        <p class="help" id="ki-name">ZIP oder JSON, bis 2 GB.</p>
      </div>
      <div id="ki-bericht" class="mat-austausch-bericht" aria-live="polite"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button>
        <button class="btn" id="ki-ok" type="button" hidden>Übernehmen</button></div>`,
    (dlg, body) => {
      const bericht = $("#ki-bericht", body);
      const ok = $("#ki-ok", body);
      let laeuft = false;
      async function senden(trocken) {
        const fd = new FormData();
        fd.append("file", datei);
        fd.append("trocken", trocken ? "1" : "0");
        return (await api(`${API}/katalog/import`, { method: "POST", body: fd })).bericht;
      }
      async function probelauf(f) {
        if (!f || laeuft) return;
        if (!/\.(zip|json)$/i.test(f.name)) { toast(`„${f.name}“: bitte ein Katalog-Export (ZIP) oder eine JSON-Datei.`, true); return; }
        datei = f;
        laeuft = true;
        ok.hidden = true;
        $("#ki-name", body).textContent = `${f.name} · ${groesse(f.size)}`;
        bericht.innerHTML = '<p class="help">Probelauf läuft …</p>';
        try {
          const b = await senden(true);
          bericht.innerHTML = importBerichtHtml(b);
          ok.hidden = Boolean(b.fehler.length) || !(b.aenderungen.length || b.hinweise.length);
        } catch (e) { bericht.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
        laeuft = false;
      }
      $("#ki-datei", body).addEventListener("change", (ev) => { probelauf(ev.target.files[0]); ev.target.value = ""; });
      const ablage = $("#ki-ablage", body);
      // Abgelegt wird überall im Dialog – nie soll der Browser die Datei stattdessen selbst öffnen. #dlg-body bleibt
      // über alle Dialoge bestehen: Die Handler gelten nur, solange dieser Dialog offen ist.
      const weg = new AbortController();
      dlg.addEventListener("close", () => weg.abort(), { once: true });
      body.addEventListener("dragover", (ev) => { ev.preventDefault(); ablage.classList.add("ueber"); }, { signal: weg.signal });
      body.addEventListener("dragleave", (ev) => { if (!body.contains(ev.relatedTarget)) ablage.classList.remove("ueber"); }, { signal: weg.signal });
      body.addEventListener("drop", (ev) => {
        ev.preventDefault();
        ablage.classList.remove("ueber");
        if (ev.dataTransfer && ev.dataTransfer.files.length) probelauf(ev.dataTransfer.files[0]);
      }, { signal: weg.signal });
      ok.onclick = async () => {
        if (!datei || laeuft) return;
        laeuft = true;
        ok.disabled = true;
        ok.textContent = "Wird übernommen …";
        try {
          const b = await senden(false);
          bericht.innerHTML = importBerichtHtml(b);
          ok.hidden = true;
          if (b.gespeichert) {
            toast("Katalog übernommen");
            // Leiste und Liste zeigen den neuen Stand, sobald der Bericht gelesen und der Dialog zu ist.
            dlg.addEventListener("close", () => location.reload(), { once: true });
          }
        } catch (e) { toast(e.message, true); }
        ok.disabled = false;
        ok.textContent = "Übernehmen";
        laeuft = false;
      };
    });
  }

  async function formularFuer(ziel) {
    // Das aktive (oder neueste) Formular des Ziels öffnen – oder ein neues anlegen.
    const q = ziel.kategorie_id ? `kategorie=${ziel.kategorie_id}` : `produkt=${ziel.produkt_id}`;
    try {
      const liste = (await api(`${API}/formulare?${q}`)).formulare;
      const f = liste.find((x) => x.aktiv) || liste[0];
      if (f) { location.href = `/material/katalog/formular/${f.id}`; return; }
      const r = await api(`${API}/formulare`, { method: "POST", body: ziel });
      location.href = `/material/katalog/formular/${r.formular.id}`;
    } catch (e) { toast(e.message, true); }
  }

  async function kategorieDialog(k) {
    const kats = await kategorienLaden();
    const neu = !k.id;
    dialog(`<h2>${neu ? "Kategorie anlegen" : "Kategorie bearbeiten"}</h2>
      <label for="kd-name">Name</label><input type="text" id="kd-name" value="${esc(k.name || "")}" maxlength="120">
      <label for="kd-parent">Oberkategorie</label><select id="kd-parent"><option value="">– oberste Ebene –</option>${kategorieOptionen(kats, k.parent_id, k.id)}</select>
      <label for="kd-norm">Norm</label><input type="text" id="kd-norm" value="${esc(k.norm || "")}" maxlength="200" placeholder="z. B. EN 361" ${TASTATUR_NUMMER}>
      <div class="field-row"><div><label for="kd-art">Materialart (Vorgabe für Produkte)</label><select id="kd-art"><option value="">–</option>
          ${Object.entries(MATERIALART).map(([w, t]) => `<option value="${w}" ${k.default_material_kind === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
        <div><label for="kd-int">Prüfintervall (Monate, Vorgabe)</label><input type="number" id="kd-int" min="1" max="120" value="${k.default_interval_months || ""}"></div></div>
      <label for="kd-ld">Lebensdauer (Jahre, Vorschlag – nur textil)</label><input type="number" id="kd-ld" min="1" max="50" value="${k.default_lifetime_years || ""}">
      <div class="help">Nur ein Vorschlag beim Anlegen eines Produkts: Die Lebensdauer steht am Produkt, aus der Anleitung des Herstellers.</div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="kd-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
    (dlg, body) => {
      const art = $("#kd-art", body), ld = $("#kd-ld", body);
      const pruefen = () => { ld.disabled = art.value !== "textil"; if (ld.disabled) ld.value = ""; };
      art.addEventListener("change", pruefen); pruefen();
      fokus($("#kd-name", body));
      $("#kd-ok", body).onclick = async () => {
        const daten = { name: $("#kd-name", body).value, parent_id: $("#kd-parent", body).value ? +$("#kd-parent", body).value : null,
                        norm: $("#kd-norm", body).value, default_material_kind: art.value || null,
                        default_interval_months: $("#kd-int", body).value || null, default_lifetime_years: ld.value || null };
        try {
          const r = neu ? await api(`${API}/kategorien`, { method: "POST", body: daten }) : await api(`${API}/kategorien/${k.id}`, { method: "PUT", body: daten });
          dlg.close(); location.href = `/material/katalog?kategorie=${r.kategorie.id}`;
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  // Eine Artikelnummer gibt es im Katalog nur einmal. Schon beim Tippen sagen, wem sie gehört – der Server
  // prüft beim Speichern ohnehin. ausser: das Produkt, das gerade bearbeitet wird.
  function artikelnummerPruefen(feld, hilfe, ausser) {
    let los = null;
    const pruefen = async () => {
      const nr = feld.value.trim();
      if (!nr) { hilfe.innerHTML = ""; return; }
      try {
        const p = (await api(`${API}/produkte/artikelnummer?${new URLSearchParams({ nr, ausser: ausser || "" })}`)).produkt;
        if (feld.value.trim() !== nr) return;          // inzwischen weitergetippt
        hilfe.innerHTML = p ? `<span class="mat-warn">Schon vergeben: <a href="/material/katalog/produkt/${p.id}" target="_blank" rel="noopener">${esc(p.name)}</a>${p.article_no ? ` (${esc(p.article_no)})` : ""}</span>` : "";
      } catch (e) { hilfe.innerHTML = ""; }
    };
    feld.addEventListener("input", () => { clearTimeout(los); los = setTimeout(pruefen, 300); });
    if (feld.value.trim()) pruefen();
  }

  async function produktDialog(p) {
    const kats = await kategorienLaden();
    const neu = !p.id;
    const kat = (id) => kats.find((k) => k.id === +id) || {};
    // Als Variante: die aktuellen Dokumente des Vorbilds (neueste Version, nicht zurückgezogen) zur Auswahl.
    const vorbildDoks = p.variante_von ? p.variante_von.dokumente.filter((d) => !d.abgeloest_durch && (!d.withdrawn_on || d.withdrawn_on > isoHeute(0))) : [];
    dialog(`<h2>${p.variante_von ? `Variante von „${esc(produktName(p.variante_von))}“` : p.meldung ? "Produkt aus Meldung anlegen" : neu ? "Produkt anlegen" : "Produkt bearbeiten"}</h2>
      ${p.variante_von ? '<p class="help">Die Stammdaten sind übernommen – bitte die neue Artikelnummer eintragen und anpassen, was sich unterscheidet.</p>' : ""}
      ${p.meldung ? meldeKasten(p.meldung) : ""}
      <label for="pd-kat">Kategorie</label><select id="pd-kat"><option value="">– bitte wählen –</option>${kategorieOptionen(kats, p.category_id)}</select>
      <div class="field-row"><div><label for="pd-her">Hersteller</label><input type="text" id="pd-her" value="${esc(p.manufacturer || "")}" maxlength="120" ${TASTATUR_NAME}></div>
        <div><label for="pd-mod">Modell</label><input type="text" id="pd-mod" value="${esc(p.model || "")}" maxlength="160" ${TASTATUR_NAME}></div></div>
      <div class="field-row"><div><label for="pd-art">Artikelnummer des Herstellers</label><input type="text" id="pd-art" value="${esc(p.article_no || "")}" maxlength="80" ${TASTATUR_NUMMER}><div class="help" id="pd-art-hilfe"></div></div>
        <div><label for="pd-norm">Norm</label><input type="text" id="pd-norm" value="${esc(p.norm || "")}" maxlength="200" ${TASTATUR_NUMMER}></div></div>
      <div class="field-row"><div><label for="pd-mk">Materialart</label><select id="pd-mk">${Object.entries(MATERIALART).map(([w, t]) => `<option value="${w}" ${p.material_kind === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
        <div><label for="pd-int">Prüfintervall (Monate)</label><input type="number" id="pd-int" min="1" max="120" value="${p.interval_months || ""}"><div class="help" id="pd-int-hilfe"></div></div></div>
      <div class="field-row"><div><label for="pd-ld">Lebensdauer (Jahre)</label><input type="number" id="pd-ld" min="1" max="50" value="${p.lifetime_years || ""}"><div class="help" id="pd-ld-hilfe"></div></div>
        <div><label for="pd-lq">Fundstelle der Lebensdauer</label><input type="text" id="pd-lq" value="${esc(p.lifetime_source || "")}" maxlength="300" placeholder="z. B. Gebrauchsanleitung, Kap. 9"></div></div>
      <label for="pd-desc">Beschreibung</label><textarea id="pd-desc" rows="3" maxlength="4000">${esc(p.description || "")}</textarea>
      ${fotoFeld("pd-bild", "Produktbild", "Bild", p.bild ? p.vorschau || p.bild : "", "JPEG, PNG, WebP oder HEIC vom Telefon.")}
      ${p.variante_von ? `<fieldset class="mat-variante-doks"><legend>Dokumente übernehmen</legend>
        ${vorbildDoks.length ? vorbildDoks.map((d) => `<label class="inline"><input type="checkbox" class="pd-dok" value="${d.id}" checked> ${esc(d.title)}
          <span class="muted small">${esc(DOKART[d.kind] || d.kind)}${d.version ? `, ${esc(d.version)}` : ""}${d.datei ? "" : " · Link"}</span></label>`).join("") : '<p class="help">Das Produkt hat keine aktuellen Dokumente.</p>'}
        <p class="help">Das Produktbild wird nie übernommen. Dokumente der Kategorie gelten ohnehin für alle Produkte darin.</p></fieldset>` : ""}
      ${p.meldung ? '<label for="pd-antwort">Anmerkung für den Melder (optional, steht in seiner Mail)</label><textarea id="pd-antwort" rows="2" maxlength="1000"></textarea>' : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="pd-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
    (dlg, body) => {
      const katSel = $("#pd-kat", body), mk = $("#pd-mk", body), ld = $("#pd-ld", body);
      const hilfen = () => {
        const k = kat(katSel.value);
        $("#pd-int-hilfe", body).textContent = k.default_interval_months ? `leer = ${k.default_interval_months} Monate aus der Kategorie` : "Pflicht, die Kategorie hat keine Vorgabe";
        const textil = mk.value === "textil";
        ld.disabled = mk.value === "metall_hardware";
        if (ld.disabled) ld.value = "";
        $("#pd-ld-hilfe", body).textContent = textil ? "Pflicht bei textil – Herstellerangabe" + (k.default_lifetime_years ? ` (Vorschlag der Kategorie: ${k.default_lifetime_years})` : "")
          : mk.value === "sonstiges" ? "nur mit Herstellerangabe (Fundstelle)" : "Metall hat keine festgeschriebene Lebensdauer";
      };
      katSel.addEventListener("change", () => {
        const k = kat(katSel.value);
        if (neu && k.default_material_kind) mk.value = k.default_material_kind;
        if (neu && !$("#pd-norm", body).value && k.norm) $("#pd-norm", body).value = k.norm;
        hilfen();
      });
      mk.addEventListener("change", hilfen);
      // Neu in einer Kategorie: deren Vorgaben übernehmen – nicht bei einer Variante, die hat ihre eigenen.
      if (neu && p.category_id && !p.variante_von) katSel.dispatchEvent(new Event("change"));
      hilfen();
      artikelnummerPruefen($("#pd-art", body), $("#pd-art-hilfe", body), p.id);
      const bildWahl = fotoFeldVerdrahten(dlg, body, "pd-bild");
      // Erst die Angaben, dann das Bild. Scheitert nur das Bild, kennt der Dialog das Produkt schon: Ein zweiter
      // Klick speichert die Angaben erneut und lädt das Bild nach, statt das Produkt doppelt anzulegen.
      let pid = p.id || null;
      $("#pd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const daten = { category_id: katSel.value ? +katSel.value : null, manufacturer: $("#pd-her", body).value, model: $("#pd-mod", body).value,
                        article_no: $("#pd-art", body).value, norm: $("#pd-norm", body).value, material_kind: mk.value,
                        interval_months: $("#pd-int", body).value || null, lifetime_years: ld.value || null,
                        lifetime_source: $("#pd-lq", body).value, description: $("#pd-desc", body).value };
        const bild = bildWahl.datei;
        if (p.variante_von && !pid && !daten.article_no.trim()) { toast("Eine Variante braucht eine eigene Artikelnummer.", true); fokus($("#pd-art", body)); return; }
        knopf.disabled = true;
        try {
          // Aus einer Meldung: Produkt anlegen und Meldung erledigen in einem Zug (der Melder bekommt Bescheid).
          const r = pid ? await api(`${API}/produkte/${pid}`, { method: "PUT", body: daten })
            : p.meldung ? await api(`${API}/meldungen/${p.meldung.id}/produkt`, { method: "POST", body: Object.assign(daten, { antwort: $("#pd-antwort", body).value }) })
            : p.variante_von ? await api(`${API}/produkte/${p.variante_von.id}/variante`, { method: "POST", body: Object.assign(daten, { dokumente: $$(".pd-dok:checked", body).map((c) => +c.value) }) })
            : await api(`${API}/produkte`, { method: "POST", body: daten });
          pid = r.produkt.id;
          if (bild) {
            const fd = new FormData();
            fd.append("file", bild);
            await api(`${API}/produkte/${pid}/bild`, { method: "POST", body: fd });
          } else if (bildWahl.entfernen) {
            await api(`${API}/produkte/${pid}/bild`, { method: "DELETE" });
          }
          dlg.close(); location.href = `/material/katalog/produkt/${pid}`;
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Dokumente: am Produkt oder an einer Kategorie (gelten dann für alle Produkte darin) ------------ */
  function dokZeile(d, k) {
    return `<tr class="${d.gilt ? "" : "mat-alt"}"><td data-l="Dokument"><a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
        <div class="small muted">${esc(DOKART[d.kind] || d.kind)}${d.datei ? ` · ${esc(groesse(d.size))}` : " · Link"}</div></td>
      <td data-l="Version">${esc(d.version || "–")}</td><td data-l="Gültig ab">${esc(fmtTag(d.valid_from))}</td>
      <td data-l="Stand">${d.gilt ? '<span class="mat-status s-einsatzbereit">gilt</span>' : d.withdrawn_on ? `zurückgezogen ${esc(fmtTag(d.withdrawn_on))}` : d.abgeloest_durch ? "abgelöst" : "noch nicht gültig"}
        ${d.sha256 ? `<div class="small muted mat-hash" title="SHA-256 ${esc(d.sha256)}">${esc(d.sha256.slice(0, 12))}…</div>` : ""}</td>
      <td>${k ? `<div class="btn-row"><button class="btn secondary small" data-act="dok-name" data-id="${d.id}">Umbenennen</button>${!d.abgeloest_durch && !d.withdrawn_on ? `<button class="btn secondary small" data-act="dok-version" data-id="${d.id}">Neue Version</button><button class="btn secondary small" data-act="dok-zurueck" data-id="${d.id}">Zurückziehen</button>` : ""}</div>` : ""}</td></tr>`;
  }
  // Herstellerdokumente als Liste: erst die des Produkts, dann unter einer kleinen Zwischenzeile die seiner
  // Kategorien (Artikel: herkunft; Prüfung: kategorie, der Name vom Prüftag). verlinkt: Titel als Link.
  function dokListe(docs, verlinkt) {
    const kat = (d) => (d.herkunft ? d.herkunft.name : d.kategorie);
    const eintrag = (d) => `<li>${verlinkt ? `<a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>` : esc(d.title)}
      <span class="muted${verlinkt ? "" : " small"}">${esc(DOKART[d.kind] || d.kind)}${d.version ? `, ${esc(d.version)}` : ""}</span></li>`;
    const eigene = docs.filter((d) => !kat(d));
    return `${eigene.length ? `<ul class="mat-doks">${eigene.map(eintrag).join("")}</ul>` : ""}
      ${katGruppen(docs.filter((d) => kat(d))).map((g) => `${katKopf(g.name, verlinkt ? g.id : null)}<ul class="mat-doks">${g.docs.map(eintrag).join("")}</ul>`).join("")}`;
  }
  // Kategoriedokumente je Kategorie (ein Produkt erbt auch von Oberkategorien) – in der Reihenfolge des Pfads.
  // Artikel und Produkt kennen die Kategorie (herkunft), eine Prüfung nur ihren Namen vom Prüftag (kategorie).
  function katGruppen(docs) {
    const gruppen = [];
    docs.forEach((d) => {
      const schluessel = d.herkunft ? `id${d.herkunft.id}` : `name${d.kategorie}`;
      let g = gruppen.find((x) => x.schluessel === schluessel);
      if (!g) gruppen.push((g = { schluessel, id: d.herkunft ? d.herkunft.id : null, name: d.herkunft ? d.herkunft.name : d.kategorie, docs: [] }));
      g.docs.push(d);
    });
    return gruppen;
  }
  const katKopf = (name, id) => `<h3 class="mat-unter">Dokumente <span class="mat-unter-zusatz">für die Kategorie
    ${id ? `<a href="/material/katalog?kategorie=${id}">${esc(name)}</a>` : esc(name)}</span></h3>`;
  const dokTabelle = (docs, k) => `<table class="list mat-tabelle"><thead><tr><th>Dokument</th><th>Version</th><th>Gültig ab</th><th>Stand</th><th></th></tr></thead><tbody>${docs.map((d) => dokZeile(d, k)).join("")}</tbody></table>`;

  // Umbenennen, neue Version, zurückziehen – für Produkt- und Kategoriedokumente gleich; danach neu zeichnen.
  function dokAktionen(docs, neuUrl, danach) {
    return {
      "dok-neu": () => dokumenteDialog(typeof neuUrl === "function" ? neuUrl() : neuUrl, danach),
      "dok-version": (b) => dokumentDialog(`${API}/dokumente/${b.dataset.id}/version`, docs().find((d) => d.id === +b.dataset.id), danach),
      "dok-zurueck": async (b) => {
        const d = docs().find((x) => x.id === +b.dataset.id);
        if (!(await confirm(`„${d.title}“ ab heute zurückziehen? Es bleibt in der Liste und in alten Protokollen sichtbar.`, "Zurückziehen"))) return;
        try { await api(`${API}/dokumente/${d.id}/zurueckziehen`, { method: "POST", body: {} }); toast("Zurückgezogen"); await danach(); } catch (e) { toast(e.message, true); }
      },
      "dok-name": (b) => {
        const d = docs().find((x) => x.id === +b.dataset.id);
        dialog(`<h2>Dokument umbenennen</h2>
          <p class="help">Nur der Name ändert sich – Datei, Version und Prüfsumme bleiben. Alte Protokolle zeigen den Namen vom Prüftag.</p>
          <label for="dn-titel">Name</label><input type="text" id="dn-titel" maxlength="200" value="${esc(d.title)}">
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="dn-ok" type="button">Speichern</button></div>`,
        (dlg, body) => {
          const feld = $("#dn-titel", body);
          fokus(feld);
          if (feld.select && !window.matchMedia("(pointer: coarse)").matches) feld.select();
          const speichern = async (ev) => {
            if (ev) ev.preventDefault();
            const knopf = $("#dn-ok", body);
            knopf.disabled = true;
            try { await api(`${API}/dokumente/${d.id}`, { method: "PUT", body: { title: feld.value } }); dlg.close(); toast("Umbenannt"); await danach(); }
            catch (e) { toast(e.message, true); knopf.disabled = false; }
          };
          $("#dn-ok", body).onclick = () => speichern();
          feld.addEventListener("keydown", (e) => { if (e.key === "Enter") speichern(e); });
        });
      },
    };
  }

  /* --- Produkt ------------------------------------------------------------------------------------- */
  async function produkt() {
    const p = (await api(`${API}/produkte/${DATEN.id}`)).produkt;
    leisteMarkieren(p.category_id);
    const k = DARF.katalog;
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    const formulare = p.formulare || [];
    inhalt.innerHTML = `${p.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen.</p>' : ""}
      <div class="mat-pfad"><a href="/material/katalog">Katalog</a> / ${p.kategorie_pfad.map((x) => `<a href="/material/katalog?kategorie=${x.id}">${esc(x.name)}</a>`).join(" / ")}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? bildLink(p.bild, p.original, `Produktbild ${produktName(p)}`, null, `<img class="mat-produktbild" src="${esc(p.bild)}" alt="">`) : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel"><h1>${esc(produktName(p))} ${demoMarke(p.demo)}</h1>
          ${DARF.verwalten ? `<div class="btn-row"><a class="btn secondary small" href="/material/artikel/neu?produkt=${p.id}">+ Artikel dieses Produkts</a></div>` : ""}
          ${k ? `<div class="btn-row"><button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>${p.artikel_gesamt ? "" : '<button class="btn secondary small" data-act="loeschen">Löschen</button>'}</div>
          <div class="btn-row"><button class="btn secondary small" data-act="variante">Als Variante kopieren</button><button class="btn secondary small" data-act="rr-neu">Rückruf anlegen</button></div>` : ""}</div>
      </div>
      ${rueckrufAbschnitt(p)}
      <div class="mat-spalten">
        <section class="section"><h2>Stammdaten</h2><dl class="mat-daten">
          ${zeile("Artikelnummer", p.article_no ? esc(p.article_no) : '<span class="muted">–</span>')}
          ${zeile("Materialart", esc(MATERIALART[p.material_kind] || p.material_kind))}
          ${zeile("Norm", p.norm ? esc(p.norm) : '<span class="muted">–</span>')}
          ${zeile("Prüfintervall", p.intervall.monate ? `${p.intervall.monate} Monate <span class="muted">(${esc(p.intervall.quelle)})</span>` : '<span class="mat-warn">keins</span>')}
          ${zeile("Lebensdauer", p.lifetime_years ? `${p.lifetime_years} Jahre${p.lifetime_source ? ` <span class="muted">(${esc(p.lifetime_source)})</span>` : ""}${p.material_kind === "textil" ? "" : ' <span class="muted">– nicht festgeschrieben</span>'}` : '<span class="muted">keine</span>')}
          ${zeile("Bestand", `${plural(p.bestand, "Artikel", "Artikel")}${p.artikel_gesamt > p.bestand ? ` <span class="muted">(+${p.artikel_gesamt - p.bestand} ausgesondert)</span>` : ""}`)}
          ${p.description ? zeile("Beschreibung", `<span class="mat-text">${esc(p.description)}</span>`) : ""}
        </dl></section>
        <section class="section"><h2>Prüfformular</h2>
          ${p.formular ? `<p>Geprüft wird nach <a href="/material/katalog/formular/${p.formular.id}"><strong>${esc(p.formular.title || "Formular")}</strong> · Version ${p.formular.version}</a> <span class="muted">(${esc(p.formular.quelle)}, ${plural(p.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span>.</p>` : '<p class="mat-warn">Für dieses Produkt gilt kein aktives Prüfformular – weder ein spezifisches noch ein generisches der Kategorie.</p>'}
          ${formulare.length ? `<p class="small">Spezifische Versionen: ${formulare.map((f) => `<a href="/material/katalog/formular/${f.id}">v${f.version}${f.aktiv ? " (aktiv)" : ""}</a>`).join(", ")}</p>` : ""}
          ${k ? '<button class="btn secondary small" data-act="formular">Spezifisches Formular bearbeiten</button>' : ""}
          <p class="help">Ein aktives spezifisches Formular ersetzt das generische der Kategorie.</p>
        </section>
      </div>
      <section class="section"><h2>Herstellerdokumente</h2>
        <p class="help">Gelten für alle Artikel dieses Produkts. Ein Protokoll verweist auf die Version, die am Prüftag galt.</p>
        ${p.dokumente.length ? dokTabelle(p.dokumente, k) : leer("Noch keine Dokumente am Produkt.")}
        ${k ? '<button class="btn secondary small" data-act="dok-neu">+ Dokument</button>' : ""}
        ${katGruppen(p.kategorie_dokumente).map((g) => `${katKopf(g.name, g.id)}
          <ul class="mat-doks">${g.docs.map((d) => `<li><a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
            <span class="muted small">${esc(DOKART[d.kind] || d.kind)}${d.version ? `, ${esc(d.version)}` : ""}</span></li>`).join("")}</ul>`).join("")}
        ${p.kategorie_dokumente.length ? '<p class="help">Kategoriedokumente hängen an der Kategorie und gelten für alle Produkte darin.</p>' : ""}
      </section>
      <section class="section"><h2>Journal</h2>${journalHtml(p.journal, true)}</section>`;
    aktionen = {
      bearbeiten: () => produktDialog(p),
      // Stammdaten vorbelegt, Artikelnummer leer (eine neue ist Pflicht), kein Bild.
      variante: () => produktDialog(Object.assign({}, p, { id: null, article_no: "", bild: null, vorschau: null, original: null, variante_von: p })),
      loeschen: async () => {
        if (!(await confirm(`Produkt „${produktName(p)}“ aus dem Katalog löschen?`, "Löschen"))) return;
        try { await api(`${API}/produkte/${p.id}`, { method: "DELETE" }); location.href = "/material/katalog"; } catch (e) { toast(e.message, true); }
      },
      formular: () => formularFuer({ produkt_id: p.id }),
      "rr-neu": () => rueckrufDialog(p),
      "rr-beenden": (b) => rueckrufBeenden(p.rueckrufe.find((r) => r.id === +b.dataset.id)),
      ...dokAktionen(() => p.dokumente, `${API}/produkte/${p.id}/dokumente`, () => zeigen(produkt)),
    };
  }

  // Mehrere Dokumente auf einmal: Dateien per Knopf (Mehrfachauswahl) oder hineinziehen, dazu Links; je Eintrag
  // Titel, Art und Versionsstand. Jede Datei geht einzeln an den Server – was scheitert, bleibt mit Grund stehen.
  const DOK_ENDUNGEN = [".pdf", ".jpg", ".jpeg", ".png", ".webp"];
  const DOK_MAX_BYTES = 50 * 1024 * 1024;
  // Die Art aus dem Dateinamen raten – nur, wo es eindeutig ist; sonst wählt man sie selbst.
  function dokArtRaten(name, bild) {
    const n = name.toLowerCase();
    if (/konformit|declaration.?of.?conformity|(^|[^a-z])doc([^a-z]|$)/.test(n)) return "konformitaetserklaerung";
    if (/pr(ü|ue)f|inspection|checklist/.test(n)) return "pruefanweisung";
    if (/pflege|wartung|reinigung|care|maintenance|cleaning/.test(n)) return "pflegehinweis";
    if (/datenblatt|data.?sheet|technical|technisch|specification|spezifikation/.test(n)) return "datenblatt";
    if (/anleitung|gebrauch|bedienung|manual|instruction|notice|user.?guide/.test(n)) return "gebrauchsanleitung";
    return bild ? "produktbild" : "";
  }
  function dokumenteDialog(url, danach) {
    const eintraege = [];
    dialog(`<h2>Dokumente hinzufügen</h2>
      <div class="mat-ablage" id="dm-ablage">
        <p><strong>Dateien hierher ziehen</strong> oder <label class="btn secondary small">Dateien wählen<input type="file" id="dm-dateien" class="mat-datei" accept="application/pdf,image/jpeg,image/png,image/webp" multiple></label></p>
        <p class="help">PDF oder Bild, bis 50 MB je Datei – gern mehrere auf einmal.</p>
      </div>
      <div id="dm-liste" class="mat-dokliste"></div>
      <p><button type="button" class="lnk" id="dm-link">+ Link beim Hersteller hinzufügen</button></p>
      <label for="dm-ab">Gültig ab (für alle)</label><input type="date" id="dm-ab">
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="dm-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
      const liste = $("#dm-liste", body);
      const artWahl = (w) => `<option value="">– Art wählen –</option>${Object.entries(DOKART).map(([k, t]) => `<option value="${k}" ${k === w ? "selected" : ""}>${esc(t)}</option>`).join("")}`;
      // Was getippt wurde, vor jedem Neuzeichnen übernehmen.
      const merken = () => $$(".mat-dokzeile", liste).forEach((z) => {
        const e = eintraege[+z.dataset.i];
        e.titel = $(".dm-titel", z).value; e.art = $(".dm-art", z).value; e.version = $(".dm-ver", z).value;
        if (!e.datei) e.url = $(".dm-url", z).value.trim();
      });
      function zeichnen() {
        liste.innerHTML = eintraege.map((e, i) => `<div class="mat-dokzeile${e.fehler ? " fehler" : ""}" data-i="${i}">
            <div class="mat-dokzeile-name">${e.datei ? `${esc(e.datei.name)} <span class="muted small">${esc(groesse(e.datei.size))}</span>` : "Link"}</div>
            ${e.datei ? "" : `<input type="text" class="dm-url" maxlength="500" placeholder="https://…" value="${esc(e.url || "")}" aria-label="Adresse" ${TASTATUR_ADRESSE}>`}
            <input type="text" class="dm-titel" maxlength="200" value="${esc(e.titel)}" placeholder="${e.datei ? "Titel" : "Titel (leer = Adresse)"}" aria-label="Titel">
            <select class="dm-art" aria-label="Art">${artWahl(e.art)}</select>
            <input type="text" class="dm-ver" maxlength="40" value="${esc(e.version)}" placeholder="Version" aria-label="Versionsstand" ${TASTATUR_NUMMER}>
            <button type="button" class="lnk dm-weg" title="Entfernen" aria-label="Entfernen">✕</button>
            ${e.fehler ? `<div class="dm-status">${esc(e.fehler)}</div>` : ""}</div>`).join("");
        $$(".dm-weg", liste).forEach((b) => { b.onclick = () => { merken(); eintraege.splice(+b.closest(".mat-dokzeile").dataset.i, 1); zeichnen(); }; });
      }
      function hinzufuegen(dateien) {
        merken();
        for (const f of dateien) {
          const endung = (f.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
          if (!DOK_ENDUNGEN.includes(endung)) { toast(`„${f.name}“: nur PDF oder Bild (JPEG, PNG, WebP).`, true); continue; }
          if (f.size > DOK_MAX_BYTES) { toast(`„${f.name}“ ist größer als 50 MB.`, true); continue; }
          if (eintraege.some((e) => e.datei && e.datei.name === f.name && e.datei.size === f.size)) continue;
          eintraege.push({ datei: f, titel: f.name.replace(/\.[^.]+$/, "").replace(/_+/g, " ").trim(), art: dokArtRaten(f.name, endung !== ".pdf"), version: "" });
        }
        zeichnen();
      }
      $("#dm-dateien", body).addEventListener("change", (ev) => { hinzufuegen(Array.from(ev.target.files)); ev.target.value = ""; });
      const ablage = $("#dm-ablage", body);
      // Abgelegt wird überall im Dialog – nie soll der Browser die Datei stattdessen selbst öffnen. #dlg-body bleibt
      // über alle Dialoge bestehen: Die Handler gelten nur, solange dieser Dialog offen ist.
      const weg = new AbortController();
      dlg.addEventListener("close", () => weg.abort(), { once: true });
      body.addEventListener("dragover", (ev) => { ev.preventDefault(); ablage.classList.add("ueber"); }, { signal: weg.signal });
      body.addEventListener("dragleave", (ev) => { if (!body.contains(ev.relatedTarget)) ablage.classList.remove("ueber"); }, { signal: weg.signal });
      body.addEventListener("drop", (ev) => {
        ev.preventDefault();
        ablage.classList.remove("ueber");
        if (ev.dataTransfer && ev.dataTransfer.files.length) hinzufuegen(Array.from(ev.dataTransfer.files));
      }, { signal: weg.signal });
      $("#dm-link", body).onclick = () => { merken(); eintraege.push({ datei: null, url: "", titel: "", art: "", version: "" }); zeichnen(); fokus($(".mat-dokzeile:last-child .dm-url", liste)); };
      $("#dm-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        merken();
        if (!eintraege.length) { toast("Bitte zuerst Dateien wählen oder hineinziehen.", true); return; }
        eintraege.forEach((e) => {
          e.fehler = !e.art ? "Bitte die Art wählen." : !e.datei && !/^https?:\/\/\S+/.test(e.url || "") ? "Bitte eine Adresse mit https:// angeben." : "";
        });
        if (eintraege.some((e) => e.fehler)) { zeichnen(); toast("Bitte die markierten Einträge ergänzen.", true); return; }
        const ab = $("#dm-ab", body).value;
        knopf.disabled = true;
        let gespeichert = 0;
        for (const [i, e] of eintraege.entries()) {
          knopf.textContent = `Speichere ${i + 1} von ${eintraege.length} …`;
          try {
            if (e.datei) {
              const fd = new FormData();
              Object.entries({ kind: e.art, title: e.titel, version: e.version, valid_from: ab }).forEach(([k, w]) => fd.append(k, w));
              fd.append("file", e.datei);
              await api(url, { method: "POST", body: fd });
            } else {
              await api(url, { method: "POST", body: { kind: e.art, title: e.titel, version: e.version, valid_from: ab || null, url: e.url } });
            }
            e.fertig = true;
            gespeichert += 1;
          } catch (err) { e.fehler = err.message; }
        }
        knopf.textContent = "Speichern";
        knopf.disabled = false;
        const rest = eintraege.filter((e) => !e.fertig);
        eintraege.splice(0, eintraege.length, ...rest);
        if (gespeichert && danach) await danach();
        if (!rest.length) { dlg.close(); toast(plural(gespeichert, "Dokument gespeichert", "Dokumente gespeichert")); return; }
        zeichnen();
        toast(`${gespeichert} gespeichert, ${rest.length} nicht – der Grund steht am Eintrag.`, true);
      };
      zeichnen();
    });
  }

  function dokumentDialog(url, alt, danach) {
    dialog(`<h2>${alt ? `Neue Version von „${esc(alt.title)}“` : "Dokument hinzufügen"}</h2>
      ${alt ? "" : `<label for="dd-kind">Art</label><select id="dd-kind">${Object.entries(DOKART).map(([w, t]) => `<option value="${w}">${esc(t)}</option>`).join("")}</select>`}
      <label for="dd-title">Titel</label><input type="text" id="dd-title" value="${esc(alt ? alt.title : "")}" maxlength="200" placeholder="leer = Dateiname">
      <div class="field-row"><div><label for="dd-ver">Versionsstand</label><input type="text" id="dd-ver" maxlength="40" placeholder="z. B. 03/2024" ${TASTATUR_NUMMER}></div>
        <div><label for="dd-ab">Gültig ab</label><input type="date" id="dd-ab"></div></div>
      <div class="mat-feldkopf">Datei (PDF oder Bild)</div>${dateiKnopf("dd-datei", "Datei wählen …", "application/pdf,image/jpeg,image/png,image/webp", false)}
      <label for="dd-url">… oder Adresse beim Hersteller</label><input type="text" id="dd-url" maxlength="500" placeholder="https://…" ${TASTATUR_ADRESSE}>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="dd-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
      dateiKnopfVerdrahten(body, "dd-datei");
      $("#dd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const datei = $("#dd-datei", body).files[0];
        const felder = { title: $("#dd-title", body).value, version: $("#dd-ver", body).value, valid_from: $("#dd-ab", body).value };
        if (!alt) felder.kind = $("#dd-kind", body).value;
        knopf.disabled = true;
        try {
          if (datei) {
            const fd = new FormData();
            Object.entries(felder).forEach(([k, v]) => fd.append(k, v));
            fd.append("file", datei);
            await api(url, { method: "POST", body: fd });
          } else {
            await api(url, { method: "POST", body: Object.assign(felder, { url: $("#dd-url", body).value, valid_from: felder.valid_from || null }) });
          }
          dlg.close(); toast("Dokument gespeichert"); await (danach ? danach() : zeigen(produkt));
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Prüfformular ---------------------------------------------------------------------------------- */
  async function formular() {
    const d = await api(`${API}/formulare/${DATEN.id}`);
    const f = d.formular;
    leisteMarkieren(f.ziel.art === "kategorie" ? f.ziel.id : f.ziel.kategorie_id);
    const bearbeitbar = DARF.katalog && f.aenderbar;
    let punkte = f.punkte.map((p) => Object.assign({}, p));
    const zielText = f.ziel.art === "kategorie" ? `Kategorie ${f.ziel.pfad.map((x) => x.name).join(" / ")} (generisch)` : `Produkt ${f.ziel.name} (spezifisch)`;
    const zielLink = f.ziel.art === "kategorie" ? `/material/katalog?kategorie=${f.ziel.id}` : `/material/katalog/produkt/${f.ziel.id}`;
    function punktZeile(p, i) {
      if (!bearbeitbar) {
        return `<tr><td data-l="Gruppe">${esc(p.gruppe || "")}</td><td data-l="Prüfpunkt">${esc(p.text)}</td><td data-l="Art">${esc(EDITOR[p.art])}</td>
          <td data-l="Soll">${esc(p.soll || "–")}</td><td>${p.pflicht ? "Pflicht" : "optional"}${p.kritisch ? ' · <strong class="mat-warn">kritisch</strong>' : ""}</td></tr>`;
      }
      return `<tr data-i="${i}"><td data-l="Gruppe"><input type="text" class="fp-gruppe" value="${esc(p.gruppe || "")}" maxlength="80"></td>
        <td data-l="Prüfpunkt"><textarea class="fp-text" rows="1" maxlength="1000" aria-label="Prüfpunkt">${esc(p.text || "")}</textarea></td>
        <td data-l="Art"><select class="fp-art">${Object.entries(EDITOR).map(([w, t]) => `<option value="${w}" ${p.art === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></td>
        <td data-l="Soll">${p.art === "yesno" ? `<select class="fp-soll"><option value="">–</option><option value="ja" ${p.soll === "ja" ? "selected" : ""}>ja</option><option value="nein" ${p.soll === "nein" ? "selected" : ""}>nein</option></select>`
          : p.art === "text" || p.art === "number" ? `<input type="text" class="fp-soll" value="${esc(p.soll || "")}" maxlength="60" placeholder="optional">` : '<span class="muted">–</span>'}</td>
        <td><label class="inline"><input type="checkbox" class="fp-pflicht" ${p.pflicht ? "checked" : ""}> Pflicht</label>
          <label class="inline"><input type="checkbox" class="fp-kritisch" ${p.kritisch ? "checked" : ""} ${p.art === "yesno" ? "" : "disabled"}> kritisch</label>
          <div class="btn-row"><button class="btn secondary small" data-act="hoch" data-i="${i}" aria-label="nach oben">↑</button><button class="btn secondary small" data-act="runter" data-i="${i}" aria-label="nach unten">↓</button><button class="btn secondary small" data-act="weg" data-i="${i}" aria-label="entfernen">✕</button></div></td></tr>`;
    }
    function einsammeln() {
      if (!bearbeitbar) return;
      $$("#fp-tabelle tbody tr", inhalt).forEach((tr) => {
        const p = punkte[+tr.dataset.i];
        p.gruppe = $(".fp-gruppe", tr).value; p.text = $(".fp-text", tr).value; p.art = $(".fp-art", tr).value;
        const soll = $(".fp-soll", tr); p.soll = soll ? soll.value : "";
        p.pflicht = $(".fp-pflicht", tr).checked; p.kritisch = $(".fp-kritisch", tr).checked && p.art === "yesno";
      });
    }
    function zeichnen() {
      inhalt.innerHTML = `${f.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen.</p>' : ""}
        <div class="mat-pfad"><a href="/material/katalog">Katalog</a> / <a href="${zielLink}">${esc(zielText)}</a></div>
        <div class="page-head"><h1>${esc(f.titel || "Prüfformular")} <span class="badge grey">Version ${f.version}</span> ${f.aktiv ? '<span class="mat-status s-einsatzbereit">aktiv</span>' : '<span class="badge grey">inaktiv</span>'} ${demoMarke(f.demo)}</h1>
          <div class="btn-row">${DARF.katalog ? `${f.aktiv ? '<button class="btn secondary small" data-act="deaktivieren">Deaktivieren</button>' : '<button class="btn secondary small" data-act="aktivieren">Aktivieren</button>'}
            <button class="btn secondary small" data-act="neue-version">Neue Version</button>${!f.aktiv && !f.benutzt ? '<button class="btn secondary small" data-act="loeschen">Löschen</button>' : ""}` : ""}</div></div>
        <p class="help">${esc(zielText)}. ${f.gueltig_ab ? `Gültig ab ${esc(fmtTag(f.gueltig_ab))}.` : "Noch nie aktiviert."}
          ${f.benutzt ? " Diese Version wurde schon für Prüfungen benutzt und bleibt unverändert – Änderungen gehen über eine neue Version." : ""}
          Bei der Prüfung ist jeder Befund mit „in Ordnung“ vorbelegt, Ja/Nein-Punkte mit ihrem Sollwert; bei Text und Zahl ist das Soll ein Hinweis für den Prüfer. Ein kritischer Punkt mit Mangel schließt „einsatzbereit“ aus.</p>
        ${bearbeitbar ? `<label for="fp-titel">Titel</label><input type="text" id="fp-titel" value="${esc(f.titel || "")}" maxlength="160">` : ""}
        <table class="list mat-tabelle mat-formtabelle" id="fp-tabelle">
          <colgroup><col style="width:13%"><col style="width:48%"><col style="width:12%"><col style="width:11%"><col style="width:16%"></colgroup><thead><tr><th>Gruppe</th><th>Prüfpunkt</th><th>Art</th><th>Soll</th><th></th></tr></thead>
          <tbody>${punkte.map(punktZeile).join("")}</tbody></table>
        ${!punkte.length ? leer("Noch keine Prüfpunkte.") : ""}
        ${bearbeitbar ? '<div class="btn-row mat-knoepfe"><button class="btn secondary" data-act="punkt-neu">+ Prüfpunkt</button><button class="btn" data-act="speichern">Speichern</button></div>' : ""}
        <section class="section"><h2>Versionen</h2><ul class="mat-versionen">${f.versionen.map((v) => `<li>${v.id === f.id ? `<strong>Version ${v.version}</strong>` : `<a href="/material/katalog/formular/${v.id}">Version ${v.version}</a>`}
          ${v.aktiv ? '<span class="mat-status s-einsatzbereit">aktiv</span>' : ""}${v.benutzt ? ' <span class="badge grey">benutzt</span>' : ""} <span class="muted">${esc(v.titel || "")} · ${plural(v.punkte_anzahl, "Prüfpunkt", "Prüfpunkte")}</span></li>`).join("")}</ul></section>
        <details class="section mat-auf"><summary>Journal</summary>${journalHtml(f.journal)}</details>`;
      $$(".fp-art", inhalt).forEach((s) => s.addEventListener("change", () => { einsammeln(); zeichnen(); }));
      $$(".fp-text", inhalt).forEach((ta) => {
        textHoehe(ta);
        ta.addEventListener("input", () => textHoehe(ta));
        // Ein Prüfpunkt ist eine Zeile Text, die nur umbricht – Enter fügt keinen Absatz ein.
        ta.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });
      });
    }
    async function speichern() {
      einsammeln();
      try {
        await api(`${API}/formulare/${f.id}`, { method: "PUT", body: { titel: $("#fp-titel").value, punkte } });
        toast("Formular gespeichert"); zeigen(formular);
      } catch (e) { toast(e.message, true); }
    }
    aktionen = {
      "punkt-neu": () => { einsammeln(); punkte.push({ gruppe: punkte.length ? punkte[punkte.length - 1].gruppe : "", text: "", art: "yesno", soll: "nein", pflicht: true, kritisch: false }); zeichnen(); fokus($$(".fp-text", inhalt).pop()); },
      hoch: (b) => { einsammeln(); const i = +b.dataset.i; if (i > 0) { [punkte[i - 1], punkte[i]] = [punkte[i], punkte[i - 1]]; zeichnen(); } },
      runter: (b) => { einsammeln(); const i = +b.dataset.i; if (i < punkte.length - 1) { [punkte[i + 1], punkte[i]] = [punkte[i], punkte[i + 1]]; zeichnen(); } },
      weg: (b) => { einsammeln(); punkte.splice(+b.dataset.i, 1); zeichnen(); },
      speichern,
      aktivieren: async () => { try { if (bearbeitbar) { einsammeln(); await api(`${API}/formulare/${f.id}`, { method: "PUT", body: { titel: $("#fp-titel").value, punkte } }); } await api(`${API}/formulare/${f.id}/aktivieren`, { method: "POST", body: {} }); toast("Aktiviert"); zeigen(formular); } catch (e) { toast(e.message, true); } },
      deaktivieren: async () => { try { await api(`${API}/formulare/${f.id}/deaktivieren`, { method: "POST", body: {} }); toast("Deaktiviert"); zeigen(formular); } catch (e) { toast(e.message, true); } },
      "neue-version": async () => {
        const ziel = f.kategorie_id ? { kategorie_id: f.kategorie_id } : { produkt_id: f.produkt_id };
        try { const r = await api(`${API}/formulare`, { method: "POST", body: Object.assign(ziel, { vorlage_id: f.id }) }); location.href = `/material/katalog/formular/${r.formular.id}`; }
        catch (e) { toast(e.message, true); }
      },
      loeschen: async () => {
        if (!(await confirm(`Version ${f.version} löschen?`, "Löschen"))) return;
        try { await api(`${API}/formulare/${f.id}`, { method: "DELETE" }); location.href = zielLink; } catch (e) { toast(e.message, true); }
      },
    };
    zeichnen();
  }

  /* --- Suche -------------------------------------------------------------------------------------------- */
  async function suche() {
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    async function zeichnen() {
      const q = DATEN.q || "";
      if (!q) { inhalt.innerHTML = `<h1>Suche</h1>${leer("Serien-, Inventar- oder Herstellernummer oben eingeben – auch Teile davon.")}`; return; }
      const p = sortParameter(new URLSearchParams({ q, seite, pro_seite: 50 }), sort);
      const d = await api(`${API}/suche?${p}`);
      inhalt.innerHTML = `<div class="page-head"><h1>Suche „${esc(q)}“</h1></div>
        ${d.treffer.length ? artikelTabelle(d.treffer, { pfad: true, sort }) : leer("Kein Artikel gefunden.")}${seitenleiste(d.gesamt, seite, 50)}`;
    }
    aktionen = {
      seite: (b) => { seite = +b.dataset.seite; zeigen(zeichnen); },
      sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); seite = 1; zeigen(zeichnen); },
    };
    await zeichnen();
  }

  /* --- Prüfung starten ---------------------------------------------------------------------------- */
  function artikelPfad(a) {
    return `<div class="mat-pfad">${(a.pfad || []).map((o) => `<a href="/material/ordner/${o.id}">${esc(o.name)}</a>`).join(" / ")}
      / <a href="/material/artikel/${a.id}">${esc(a.inventory_no)}</a></div>`;
  }
  function lebensdauerHinweis(ld) {
    if (!ld) return "";
    return ld.erreicht ? `<p class="mat-banner s-lebensdauer">LEBENSENDE ERREICHT am ${esc(fmtTag(ld.ende))} – „einsatzbereit“ ist nicht mehr wählbar.</p>`
      : `<p class="notice">Textil: Lebensende ${esc(fmtTag(ld.ende))} – noch ${plural(ld.rest_tage, "Tag", "Tage")}.</p>`;
  }

  async function pruefungNeu() {
    const a = (await api(`${API}/artikel/${DATEN.id}`)).artikel;
    leisteMarkieren(a.folder_id);
    if (a.entwurf && a.entwurf.pruefer_id === DARF.uid && DARF.pruefen) { location.replace(`/material/pruefung/${a.entwurf.id}`); return; }
    const p = a.produkt;
    const pa = a.pruefarten || { arten: [], vorschlag: null };
    let hinweis = "";                     // HTML – nur der Hinweis zum Prüferwerden enthält einen Link
    if (a.lock_state === "ausgesondert") hinweis = "Ein ausgesonderter Artikel wird nicht mehr geprüft.";
    else if (!DARF.pruefen) hinweis = pruefHinweis();
    else if (a.entwurf) hinweis = esc(`In Prüfung bei ${a.entwurf.pruefer} seit ${fmtZeit(a.entwurf.seit)}.${DARF.verwalten ? " Eine liegen gebliebene Reservierung gibst du in der Artikelansicht frei." : " Eine liegen gebliebene Reservierung gibt der Materialwart frei."}`);
    else if (!a.formular) hinweis = "Für dieses Produkt gibt es kein aktives Prüfformular – weder am Produkt noch in seiner Kategorie. Der Produktkatalogpfleger legt es im Katalog an.";
    const ld = a.lebensdauer && a.lebensdauer.festgeschrieben ? { ende: a.lebensdauer.ende, rest_tage: a.lebensdauer.rest_tage, erreicht: a.lebensdauer.rest_tage <= 0 } : null;
    inhalt.innerHTML = `${p.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen. Dieses Produkt stammt aus den Demodaten.</p>' : ""}
      ${artikelPfad(a)}
      <div class="page-head"><h1>Prüfung ${esc(a.inventory_no)} ${statusMarke(a.status, true)}</h1></div>
      <div class="mat-formular">
        <p class="mat-produktzeile"><strong>${esc(produktName(p))}</strong>${p.article_no ? ` · Art.-Nr. ${esc(p.article_no)}` : ""} · Seriennummer ${esc(a.serial_no)}</p>
        ${a.lock_state !== "frei" && a.lock_state !== "ausgesondert" ? `<p class="mat-banner s-gesperrt">GESPERRT${a.lock_reason ? ` – ${esc(a.lock_reason)}` : ""}. Mit „einsatzbereit“ ist diese Prüfung die Freiprüfung.</p>` : ""}
        ${rueckrufHinweis((a.rueckrufe || []).filter((r) => r.zustand !== "erledigt").map((r) => r.title), a.id)}
        ${lebensdauerHinweis(ld)}
        ${a.formular ? `<p>Formular: ${esc(a.formular.title || "ohne Titel")} · Version ${a.formular.version} <span class="muted">(${esc(a.formular.quelle)}, ${plural(a.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span></p>` : ""}
        ${a.durchgang ? `<p>Im Prüfdurchgang <a href="/material/durchgang/${a.durchgang.id}">${esc(a.durchgang.titel)}</a> – die Prüfung zählt dort.</p>` : ""}
        ${hinweis ? `<p class="notice">${hinweis}</p><p><a class="btn secondary" href="/material/artikel/${a.id}">Zum Artikel</a></p>` : `
          <fieldset class="mat-arten"><legend>Art der Prüfung</legend>
            ${pa.arten.map((x) => `<label class="mat-art-wahl"><input type="radio" name="art" value="${x}" ${x === pa.vorschlag ? "checked" : ""}> ${esc(PRUEFART[x] || x)}</label>`).join("")}
            ${pa.arten.length === 1 && pa.arten[0] === "eingang" ? '<p class="help">Die erste Prüfung eines Artikels ist die Eingangsprüfung. Erst sie gibt ihn frei; bis dahin steht er auf „neu“.</p>' : ""}
          </fieldset>
          <div class="btn-row mat-knoepfe"><button class="btn" data-act="beginnen">Prüfung beginnen</button><a class="btn secondary" href="/material/artikel/${a.id}">Abbrechen</a></div>
          <p class="help">Mit dem Beginn reservierst du den Artikel: Andere sehen „in Prüfung bei dir“, bis du abschließt oder verwirfst. Jede Eingabe wird sofort gespeichert – du kannst jederzeit unterbrechen.</p>`}
      </div>`;
    aktionen = {
      beginnen: async (b) => {
        b.disabled = true;
        const wahl = $('input[name="art"]:checked');
        const body = { art: wahl ? wahl.value : null };
        if (DATEN.durchgang) body.durchgang_id = DATEN.durchgang;
        try { const r = await api(`${API}/artikel/${a.id}/pruefungen`, { method: "POST", body }); location.href = `/material/pruefung/${r.pruefung.id}`; }
        catch (e) { toast(e.message, true); b.disabled = false; }
      },
    };
  }

  /* --- Prüfung (Entwurf und abgeschlossen) --------------------------------------------------------
     Fürs Telefon am Material gebaut: je Prüfpunkt große Umschalter, ein Kamera-Knopf, die Bemerkung nur
     bei Bedarf; unten eine feste Leiste mit Ergebnis und Abschluss. Jede Eingabe geht sofort an den
     Server – der Entwurf ist immer gespeichert. Prüfen und Anzeigen übernimmt der Server; hier wird nur
     vorab gezeigt, was er sagen würde (kritischer Mangel, fehlendes Foto). */
  const befundMarke = (b) => (b ? `<span class="mat-befund b-${esc(b)}">${esc(BEFUND[b] || b)}</span>` : '<span class="muted">–</span>');
  const isoHeute = (plusTage) => {
    const d = new Date(); d.setDate(d.getDate() + (plusTage || 0));
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  async function pruefungAnsicht() {
    let pr = (await api(`${API}/pruefungen/${DATEN.id}`)).pruefung;
    let ergebnis = null;
    let seiten = [];                 // Dateien für den nächsten Anhang (Scan: eine Seite je Foto)
    let hochladen = false;           // ein Anhang ist unterwegs – der Knopf bleibt so lange gesperrt
    let gebunden = false;
    // Was gerade gespeichert wird. Ein Wert wird beim Verlassen des Feldes gespeichert – tippt jemand danach
    // sofort auf „Abschließen“, wartet der Abschluss, bis der Wert angekommen ist.
    let laufend = Promise.resolve();
    // Die Kette selbst schluckt Fehler (gemeldet hat sie der Aufrufer schon) – sonst stünde jeder abgelehnte Wert
    // zusätzlich als „Uncaught (in promise)“ in der Konsole.
    const merken = (p) => { laufend = laufend.then(() => p, () => p).catch(() => {}); return p; };
    const bearbeitbar = () => pr.entwurf && pr.eigen && DARF.pruefen;
    const punkt = (rid) => pr.punkte.find((x) => x.id === rid);

    // Berichtigen darf nur, wer die Prüfung gemacht hat; ob es gerade geht, sagt der Server (berichtigbar). Eine
    // Aussonderung (auch „aussondern“ als Ergebnis) ist nie berichtigbar – dort gibt es den Knopf gar nicht.
    const darfBerichtigen = () => !pr.entwurf && pr.eigen && DARF.pruefen && pr.berichtigbar && pr.art !== "aussonderung"
      && pr.ergebnis !== "aussondern";

    function kopf() {
      const a = pr.artikel;
      const knoepfe = [];
      if (pr.entwurf && !pr.eigen && DARF.verwalten) knoepfe.push('<button class="btn secondary small" data-act="freigeben">Reservierung freigeben</button>');
      if (darfBerichtigen()) {
        knoepfe.push(pr.berichtigbar.ok ? '<button class="btn secondary small" data-act="berichtigen">Berichtigen</button>'
          : `<button class="btn secondary small" type="button" disabled title="${esc(pr.berichtigbar.grund)}">Berichtigen</button>`);
      }
      return `${pr.produkt.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen. Dieses Produkt stammt aus den Demodaten.</p>' : ""}
        <div class="mat-pfad">${a.pfad.map((o) => `<a href="/material/ordner/${o.id}">${esc(o.name)}</a>`).join(" / ")} / <a href="/material/artikel/${a.id}">${esc(a.inventory_no)}</a></div>
        <div class="page-head"><h1>${esc(PRUEFART[pr.art] || pr.art)} <span class="mat-h1-zusatz">${esc(a.inventory_no)}</span> ${pr.entwurf ? '<span class="badge">Entwurf</span>' : ergebnisMarke(pr.ergebnis)}</h1>
          ${knoepfe.length ? `<div class="btn-row">${knoepfe.join("")}</div>` : ""}</div>
        ${berichtigungHinweis()}
        <p class="mat-produktzeile"><strong>${esc(pr.produkt.name)}</strong>${pr.produkt.article_no ? ` · Art.-Nr. ${esc(pr.produkt.article_no)}` : ""} · Seriennummer ${esc(a.serial_no)} ${statusMarke(a.status)}</p>
        <p class="small muted">${pr.formular ? `Formular ${esc(pr.formular.titel || "ohne Titel")}, Version ${pr.formular.version} · ` : ""}${pr.art === "aussonderung" ? "Ausgeführt von" : "Prüfer"} ${esc(pr.pruefer || "–")}${pr.urkunde ? ` (Urkundennummer ${esc(pr.urkunde)})` : ""}
          · ${pr.entwurf && !pr.berichtigt ? `begonnen ${esc(fmtZeit(pr.begonnen_am))}` : `Prüftag ${esc(fmtTag(pr.datum))}`}
          ${pr.durchgang ? ` · Durchgang <a href="/material/durchgang/${pr.durchgang.id}">${esc(pr.durchgang.titel)}</a>` : ""}</p>`;
    }

    /* Berichtigung: Die Berichtigung verweist auf ihr Original, das Original auf seine Berichtigung. */
    function berichtigungHinweis() {
      const b = pr.berichtigt;
      const original = (x) => (x.protokoll_id
        ? `von <a href="/material/pruefung/${x.id}">Protokoll ${esc(x.protokoll_id)}</a> vom ${esc(fmtTag(x.datum))}`
        : `<a href="/material/pruefung/${x.id}">der Prüfung vom ${esc(fmtTag(x.datum))}</a> (ohne Protokoll)`);
      let html = "";
      if (b && pr.entwurf) {
        html += `<div class="mat-ber"><strong>Berichtigung</strong> ${original(b)} – Grund: ${esc(pr.grund_berichtigung || "–")}.
          Der Prüftag bleibt der ${esc(fmtTag(pr.datum))}, die Art der Prüfung steht fest. Erst mit dem Festschreiben ersetzt die Berichtigung das Original.</div>`;
      } else if (b) {
        html += `<div class="mat-ber"><strong>Berichtigung</strong> ${original(b)}. Grund: ${esc(pr.grund_berichtigung || "–")}</div>`;
      }
      const d = pr.berichtigt_durch;
      if (d && d.entwurf) {
        html += `<div class="mat-ber"><strong>Berichtigung in Arbeit</strong> bei ${esc(d.pruefer || "–")} – <a href="/material/pruefung/${d.id}">Entwurf ansehen</a>. Bis sie festgeschrieben ist, gilt diese Prüfung.</div>`;
      } else if (d) {
        html += `<div class="mat-ber ersetzt"><strong>Berichtigt</strong> durch <a href="/material/pruefung/${d.id}">${d.protokoll_id ? `Protokoll ${esc(d.protokoll_id)}` : "eine spätere Prüfung"}</a> – maßgeblich ist die Berichtigung. Diese Prüfung bleibt${pr.protokoll ? " mit ihrem Protokoll" : ""} unverändert erhalten.</div>`;
      }
      return html;
    }

    function punktHtml(x) {
      const mangel = x.befund === "mangel";
      const nz = x.befund === "nicht_zutreffend";
      let steuer;
      if (x.art === "yesno") {
        steuer = `<div class="mat-wahl3" role="group" aria-label="Befund zu ${esc(x.text)}">
          ${["ja", "nein"].map((w) => `<button type="button" data-act="pwert" data-rid="${x.id}" data-wert="${w}" class="${w === x.soll ? "soll" : "abw"}" aria-pressed="${!nz && x.wert === w}">${w === "ja" ? "Ja" : "Nein"}</button>`).join("")}
          <button type="button" data-act="pbefund" data-rid="${x.id}" data-befund="nicht_zutreffend" aria-pressed="${nz}">n. z.</button></div>`;
      } else if (x.art === "signature") {
        // Unterschriftsfeld: gezeichnet im Pad (unterschrift.js); „n. z.“ nimmt es heraus. Kein Foto.
        steuer = `<div class="mat-us-feld">
          ${x.unterschrift ? `<img class="mat-us-bild" src="${esc(x.unterschrift)}" alt="Unterschrift: ${esc(x.text)}">` : ""}
          <div class="btn-row">${nz ? "" : `<button type="button" class="btn secondary small" data-act="punterschrift" data-rid="${x.id}">${x.unterschrift ? "Neu unterschreiben" : "Unterschreiben"}</button>`}
            ${x.unterschrift ? `<button type="button" class="btn secondary small" data-act="punterschrift-weg" data-rid="${x.id}">Entfernen</button>` : ""}
            <button type="button" class="btn secondary small mat-nz-knopf" data-act="pbefund" data-rid="${x.id}" data-befund="nicht_zutreffend" aria-pressed="${nz}" title="nicht zutreffend">n. z.</button></div></div>`;
      } else {
        const feld = x.art === "photo" ? ""
          : x.art === "date" ? `<input type="date" class="mat-pwert" data-rid="${x.id}" value="${esc(x.wert || "")}" aria-label="${esc(x.text)}">`
          : x.art === "number" ? `<input type="text" inputmode="decimal" class="mat-pwert" data-rid="${x.id}" value="${esc(x.wert || "")}" placeholder="${x.soll ? `Soll ${esc(x.soll)}` : "Wert"}" aria-label="${esc(x.text)}">`
          : `<textarea class="mat-pwert" data-rid="${x.id}" rows="2" maxlength="1000" aria-label="${esc(x.text)}" placeholder="${esc(x.soll || "")}">${esc(x.wert || "")}</textarea>`;
        steuer = `${feld}<div class="mat-wahl3" role="group" aria-label="Befund zu ${esc(x.text)}">
          ${[["ok", "in Ordnung", "soll"], ["mangel", "Mangel", "abw"], ["nicht_zutreffend", "n. z.", ""]].map(([b, t, k]) => `<button type="button" data-act="pbefund" data-rid="${x.id}" data-befund="${b}" class="${k}" aria-pressed="${x.befund === b}">${t}</button>`).join("")}</div>`;
      }
      const fotoPflicht = mangel || (x.art === "photo" && x.pflicht && !nz);
      const foto = x.art === "signature" ? "" : `<div class="mat-punkt-foto">
          ${x.foto ? bildLink(x.foto.web, x.foto.original, x.text, "punkte", `<img src="${esc(x.foto.vorschau)}" alt="Foto zu ${esc(x.text)}">`) : ""}
          <label class="btn secondary small mat-kamera">📷 ${x.foto ? "neues Foto" : "Foto"}<input type="file" accept="image/*" capture="environment" data-foto="${x.id}" class="mat-datei" aria-label="Foto zu ${esc(x.text)}"></label>
          ${x.foto ? `<button type="button" class="lnk small" data-act="pfoto-weg" data-rid="${x.id}">Foto entfernen</button>` : ""}
          ${fotoPflicht && !x.foto ? '<span class="mat-pflicht">Foto ist Pflicht</span>' : ""}</div>`;
      const notiz = mangel || x.notiz;
      return `<div class="mat-punkt${mangel ? " mangel" : ""}${nz ? " nz" : ""}" id="pp-${x.id}">
        <div class="mat-punkt-kopf"><span class="mat-punkt-text">${esc(x.text)}</span>
          ${x.kritisch ? '<span class="mat-kritisch" title="Ein Mangel hier schließt „einsatzbereit“ aus">kritisch</span>' : ""}
          ${x.art === "yesno" && x.soll ? `<span class="muted small">Soll ${esc(x.soll)}</span>` : ""}${x.pflicht ? "" : '<span class="muted small">optional</span>'}</div>
        <div class="mat-punkt-zeile">${steuer}${foto}
          ${notiz ? "" : `<button type="button" class="lnk small" data-act="pnotiz-auf" data-rid="${x.id}">+ Bemerkung</button>`}</div>
        <textarea class="mat-pnotiz" data-rid="${x.id}" rows="2" maxlength="1000" placeholder="${mangel ? "Pflicht bei Mangel: Was ist wo zu sehen?" : "Bemerkung"}" ${notiz ? "" : "hidden"}${mangel ? ' aria-required="true"' : ""}>${esc(x.notiz || "")}</textarea>
        ${mangel && !(x.notiz || "").trim() ? '<span class="mat-pflicht mat-pflicht-notiz">Bemerkung ist Pflicht</span>' : ""}</div>`;
    }

    function punkteHtml() {
      if (!pr.punkte.length) return "";
      let gruppe = null;
      let html = "";
      pr.punkte.forEach((x) => {
        if (x.gruppe !== gruppe) { gruppe = x.gruppe; html += gruppe ? `<h3 class="mat-gruppe">${esc(gruppe)}</h3>` : ""; }
        html += punktHtml(x);
      });
      return `<section class="section mat-punkte"><h2>Prüfpunkte</h2>
        <p class="help">Vorbelegt mit dem Sollwert – ändere nur, was abweicht. Ein Mangel braucht ein Foto, ein kritischer schließt „einsatzbereit“ aus.</p>${html}</section>`;
    }

    function anhaengeListe() {
      if (!pr.anhaenge.length) return leer("Keine Anhänge.");
      return `<ul class="mat-anhaenge">${pr.anhaenge.map((x) => `<li><a href="${esc(x.datei)}" target="_blank" rel="noopener">${esc(x.titel)}</a>
        <span class="muted small">${esc(x.art_text)} · ${plural(x.seiten || 0, "Seite", "Seiten")} · SHA-256 <span class="mat-hash" title="${esc(x.sha256)}">${esc(x.sha256.slice(0, 12))}…</span>${x.im_protokoll ? " · ans Protokoll" : ""}</span>
        ${bearbeitbar() ? `<button type="button" class="lnk small" data-act="anhang-weg" data-id="${x.id}">entfernen</button>` : ""}</li>`).join("")}</ul>`;
    }

    function anhaengeHtml() {
      const neu = bearbeitbar() ? `<div class="mat-anhang-neu">
          <div class="field-row"><div><label for="ah-art">Art</label><select id="ah-art">${Object.entries(ANHANGART).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
            <div><label for="ah-titel">Titel</label><input type="text" id="ah-titel" maxlength="160" placeholder="z. B. Prüfkarte des Herstellers"></div></div>
          <div class="btn-row"><label class="btn secondary small">📷 Seite fotografieren<input type="file" accept="image/*" capture="environment" id="ah-kamera" class="mat-datei"></label>
            <label class="btn secondary small">Dateien wählen<input type="file" accept="application/pdf,image/*" multiple id="ah-dateien" class="mat-datei"></label></div>
          <ol class="mat-scan" id="ah-seiten"></ol>
          <label class="inline"><input type="checkbox" id="ah-protokoll" checked> hinten ans Protokoll hängen</label>
          <div class="btn-row"><button type="button" class="btn secondary small" data-act="anhang-hoch" id="ah-hoch" disabled>Als ein PDF anhängen</button></div></div>` : "";
      return `<section class="section"><h2>Anhänge</h2>
        ${bearbeitbar() ? '<p class="help">Externe Prüfkarte, Bericht eines Prüfdienstes … als PDF oder Foto. Mehrere Fotos (eine je Seite) und PDFs werden in der Reihenfolge der Liste ein PDF.</p>' : ""}
        <div id="ah-liste">${anhaengeListe()}</div>${neu}</section>`;
    }

    function seitenZeichnen() {
      const ol = $("#ah-seiten");
      if (!ol) return;
      ol.innerHTML = seiten.map((f, i) => `<li>${esc(f.name)} <span class="muted small">${groesse(f.size)}</span>
        <button type="button" class="lnk small" data-act="seite-weg" data-i="${i}">entfernen</button></li>`).join("");
      $("#ah-hoch").disabled = !seiten.length || hochladen;
      $("#ah-hoch").textContent = hochladen ? "Wird hochgeladen …" : seiten.length > 1 ? `${seiten.length} Dateien als ein PDF anhängen` : "Als PDF anhängen";
    }

    function offeneHinweise() {
      const offen = pr.punkte.filter((x) => x.pflicht && x.befund !== "nicht_zutreffend"
        && (x.art === "photo" ? !x.foto : x.art === "signature" ? !x.unterschrift : x.art === "yesno" ? !x.wert : !(x.wert || "").trim()));
      const ohneFoto = pr.punkte.filter((x) => x.befund === "mangel" && !x.foto);
      const ohneNotiz = pr.punkte.filter((x) => x.befund === "mangel" && !(x.notiz || "").trim());
      const kritisch = pr.punkte.filter((x) => x.befund === "mangel" && x.kritisch);
      const ldErreicht = pr.lebensdauer && pr.lebensdauer.erreicht;
      return { offen, ohneFoto, ohneNotiz, kritisch, einsatzSperre: kritisch.length || ldErreicht, maengel: pr.punkte.filter((x) => x.befund === "mangel") };
    }

    function abschlussHtml() {
      return `<div class="mat-abschluss" id="pr-abschluss" role="region" aria-label="Ergebnis und Abschluss">
        <div class="mat-ergebnis" role="group" aria-label="Ergebnis">
          ${Object.keys(ERGEBNIS).map((e) => `<button type="button" data-act="ergebnis" data-e="${e}" class="e-${e}" aria-pressed="false">${esc(ERGEBNIS[e])}</button>`).join("")}</div>
        <div class="mat-abschluss-zeile">
          <label class="mat-due" id="pr-due-feld" hidden>Nächste Prüfung <input type="date" id="pr-due" value="${esc(pr.vorschlag_naechste || "")}" max="${esc(pr.vorschlag_naechste || "")}" min="${isoHeute(1)}"></label>
          <input type="text" id="pr-grund" maxlength="300" placeholder="Grund" aria-label="Grund" value="${esc(pr.grund || "")}" hidden>
          <button type="button" class="btn" data-act="festschreiben" id="pr-ok" disabled>Festschreiben</button></div>
        <div class="mat-abschluss-hinweis" id="pr-hinweis" aria-live="polite"></div></div>`;
    }

    function abschlussAktualisieren() {
      const h = offeneHinweise();
      if (ergebnis === "einsatzbereit" && h.einsatzSperre) ergebnis = null;
      $$("#pr-abschluss [data-act=ergebnis]").forEach((b) => {
        b.setAttribute("aria-pressed", String(b.dataset.e === ergebnis));
        if (b.dataset.e === "einsatzbereit") {
          b.disabled = !!h.einsatzSperre;
          b.title = h.einsatzSperre ? (pr.einsatzbereit_gesperrt.concat(h.kritisch.length ? ["kritischer Mangel"] : [])).join("; ") : "";
        }
      });
      $("#pr-due-feld").hidden = ergebnis !== "einsatzbereit";
      $("#pr-grund").hidden = !ergebnis || ergebnis === "einsatzbereit";
      $("#pr-grund").placeholder = h.maengel.length ? "Grund (freiwillig – die Mängel stehen oben)" : "Grund (Pflicht ohne Mangel)";
      $("#pr-ok").disabled = !ergebnis;
      const teile = [];
      if (h.offen.length) teile.push(`${plural(h.offen.length, "Pflichtpunkt", "Pflichtpunkte")} ohne Befund`);
      if (h.ohneFoto.length) teile.push(`${plural(h.ohneFoto.length, "Mangel", "Mängel")} ohne Foto`);
      if (h.ohneNotiz.length) teile.push(`${plural(h.ohneNotiz.length, "Mangel", "Mängel")} ohne Bemerkung`);
      if (h.kritisch.length) teile.push("kritischer Mangel – nicht einsatzbereit");
      else if (pr.lebensdauer && pr.lebensdauer.erreicht) teile.push("Lebensende erreicht – nicht einsatzbereit");
      if (pr.freipruefung && ergebnis === "einsatzbereit") teile.push("Freiprüfung: Der Artikel kehrt in seinen Herkunftsordner zurück");
      if (ergebnis === "instandsetzen" && !pr.freipruefung) teile.push("„instandsetzen“ sperrt den Artikel");
      if (ergebnis === "aussondern") teile.push("„aussondern“ ist endgültig");
      if (!DARF.unterschrift) teile.push("Deine Unterschrift fehlt noch – „Festschreiben“ fragt danach");
      $("#pr-hinweis").textContent = teile.join(" · ");
      $("#pr-hinweis").classList.toggle("warn", !!(h.offen.length || h.ohneFoto.length || h.ohneNotiz.length || h.kritisch.length));
    }

    function leseHtml() {
      const zeilen = pr.punkte.map((x) => `<tr class="${x.befund === "mangel" ? "mat-mangelzeile" : ""}">
          <td data-l="Prüfpunkt">${x.gruppe ? `<span class="muted small">${esc(x.gruppe)}</span><br>` : ""}${esc(x.text)}</td>
          <td class="mat-krit-spalte">${x.kritisch ? '<span class="mat-kritisch">kritisch</span>' : ""}</td>
          <td data-l="Befund">${x.art === "signature" && !x.unterschrift && x.befund !== "nicht_zutreffend" ? '<span class="muted">nicht unterschrieben</span>' : befundMarke(x.befund)}</td><td data-l="Wert">${x.art === "signature" && x.unterschrift ? `<img class="mat-us-mini" src="${esc(x.unterschrift)}" alt="Unterschrift">`
            : x.wert ? esc(x.wert) : '<span class="muted">–</span>'}${x.art === "yesno" && x.soll ? ` <span class="muted small mat-soll">(Soll ${esc(x.soll)})</span>` : ""}</td>
          <td data-l="Bemerkung">${x.notiz ? `<span class="mat-text">${esc(x.notiz)}</span>` : ""}</td>
          <td data-l="Foto">${x.foto ? bildLink(x.foto.web, x.foto.original, `${x.text}${x.notiz ? ` – ${x.notiz}` : ""}`, "befunde", `<img class="mat-mini" src="${esc(x.foto.vorschau)}" alt="Foto">`) : ""}</td></tr>`).join("");
      const ergebnisBox = pr.entwurf ? `<p class="notice">Diese Prüfung ist noch offen – in Prüfung bei ${esc(pr.pruefer)} seit ${esc(fmtZeit(pr.begonnen_am))}. Was hier steht, ist der aktuelle Stand des Entwurfs.</p>`
        : `<div class="mat-spalten"><section class="section"><h2>Ergebnis</h2><dl class="mat-daten">
          <dt>Ergebnis</dt><dd>${ergebnisMarke(pr.ergebnis)}</dd>
          <dt>Prüftag</dt><dd>${esc(fmtTag(pr.datum))}</dd>
          ${pr.naechste ? `<dt>Nächste Prüfung</dt><dd><strong>${esc(fmtTag(pr.naechste))}</strong></dd>` : ""}
          ${pr.grund ? `<dt>Grund</dt><dd>${esc(pr.grund)}</dd>` : ""}
          ${pr.bemerkung ? `<dt>Bemerkung</dt><dd class="mat-text">${esc(pr.bemerkung)}</dd>` : ""}
          <dt>${pr.art === "aussonderung" ? "Ausgeführt von" : "Prüfer"}</dt><dd>${esc(pr.pruefer || "–")}${pr.urkunde ? ` · Urkundennummer ${esc(pr.urkunde)}` : ""}</dd>
          ${pr.basis_id ? `<dt>Grundlage</dt><dd><a href="/material/pruefung/${pr.basis_id}">Prüfung vom Tag der Aussonderung</a></dd>` : ""}
          <dt>Abgeschlossen</dt><dd>${esc(fmtZeit(pr.abgeschlossen_am))}</dd></dl></section>${protokollHtml()}</div>`;
      return `${ergebnisBox}
        ${pr.punkte.length ? `<section class="section"><h2>Befunde</h2><table class="list mat-tabelle mat-befunde"><thead><tr><th>Prüfpunkt</th><th class="mat-krit-spalte"><span class="mat-vorlesen">kritisch</span></th><th>Befund</th><th>Wert</th><th>Bemerkung</th><th>Foto</th></tr></thead><tbody>${zeilen}</tbody></table></section>` : ""}
        ${pr.art !== "aussonderung" ? anhaengeHtml() : ""}
        ${pr.dokumente.length ? `<section class="section"><h2>Herstellerdokumente am Prüftag</h2>${dokListe(pr.dokumente, false)}</section>` : ""}`;
    }

    /* Mit dem Ergebnis „aussondern“ entsteht zusätzlich eine Aussonderung mit eigenem Protokoll (A-…). Die
       Prüfung kennt sie nicht – der Lebenslauf schon: Dort verweist sie mit basis_id auf diese Prüfung. */
    let aussonderung = null;
    async function aussonderungLaden() {
      aussonderung = null;
      if (pr.entwurf || pr.ergebnis !== "aussondern" || pr.art === "aussonderung") return;
      try {
        const liste = (await api(`${API}/artikel/${pr.item_id}`)).artikel.pruefungen || [];
        aussonderung = liste.find((x) => x.art === "aussonderung" && x.basis_id === pr.id) || null;
      } catch (e) { /* dann ohne Verweis */ }
    }
    function aussonderungHtml() {
      const a = aussonderung;
      if (!a) return "";
      return `<dt>Aussonderung</dt><dd><a href="/material/pruefung/${a.id}">${a.protokoll ? `Protokoll ${esc(a.protokoll.id)}` : "Aussonderung ansehen"}</a>
        ${a.protokoll ? ` · <a class="mat-pdf" href="${esc(a.protokoll.url)}" target="_blank" rel="noopener" title="Aussonderungsprotokoll ${esc(a.protokoll.id)} öffnen">PDF</a>` : ""}</dd>`;
    }

    /* Das festgeschriebene Protokoll: ID, PDF, wann und mit welcher Anmeldung, Prüfsumme, Unterschrift. */
    function protokollHtml() {
      const p = pr.protokoll;
      const nein = darfBerichtigen() && !pr.berichtigbar.ok && !pr.berichtigt_durch
        ? `<p class="small muted">Berichtigen geht nicht: ${esc(pr.berichtigbar.grund)}</p>` : "";
      if (!p) return `<section class="section mat-protokoll"><h2>Protokoll</h2><p class="muted">Vor Einführung des Festschreibens abgeschlossen – ohne Protokoll.</p>${nein}</section>`;
      return `<section class="section mat-protokoll"><h2>Protokoll</h2>
        <div class="mat-protokoll-kopf"><span class="mat-protokoll-id mat-hash">${esc(p.id)}</span>
          <a class="btn secondary small" href="${esc(p.url)}" target="_blank" rel="noopener">Protokoll (PDF)</a></div>
        <dl class="mat-daten">
          <dt>Festgeschrieben</dt><dd>${esc(fmtZeit(p.festgeschrieben))}${p.anmeldung ? ` von ${esc(p.anmeldung)}` : ""}</dd>
          <dt>Prüfsumme</dt><dd><span class="small muted">SHA-256 (erste ${esc(p.bytes)} Bytes)</span><br>${summeKnopf(p.sha256)}</dd>
          ${pr.unterschrift ? `<dt>Unterschrift</dt><dd><img class="mat-us-bild" src="${esc(pr.unterschrift)}" alt="Unterschrift von ${esc(pr.pruefer || "")}"></dd>` : ""}
          ${aussonderungHtml()}
        </dl>
        <p class="help">Die Prüfsumme steht im Fuß jeder Seite des PDFs. Ob eine Datei unverändert ist, zeigt <a href="/material/pruefen">Protokoll prüfen</a>.</p>${nein}</section>`;
    }

    function bearbeitenHtml() {
      return `${pr.freipruefung ? `<p class="mat-banner s-gesperrt">GESPERRT – mit „einsatzbereit“ ist diese Prüfung die Freiprüfung.</p>` : ""}
        ${rueckrufHinweis(pr.artikel.rueckruf ? [pr.artikel.rueckruf] : [], pr.artikel.id, Boolean(pr.berichtigt))}
        ${lebensdauerHinweis(pr.lebensdauer)}
        ${punkteHtml()}
        <section class="section"><h2>Zur Prüfung</h2>
          ${pr.berichtigt ? `<label for="pr-art">Art der Prüfung</label><select id="pr-art" disabled><option>${esc(PRUEFART[pr.art] || pr.art)}</option></select>
            <p class="help">Bei einer Berichtigung steht die Art fest – wie im Original.</p>`
            : pr.arten && pr.arten.length > 1 ? `<label for="pr-art">Art der Prüfung</label><select id="pr-art">${pr.arten.map((x) => `<option value="${x}" ${x === pr.art ? "selected" : ""}>${esc(PRUEFART[x] || x)}</option>`).join("")}</select>` : ""}
          <label for="pr-bem">Bemerkung</label>
          <p class="help" id="pr-bem-hilfe">Mängel, die du während der Prüfung festgestellt und durch eine eigene Maßnahme gleich behoben hast, sind hier zu dokumentieren – jeweils mit der Maßnahme. Was sich nicht während der Prüfung beheben ließ, gehört als Mangel an den Prüfpunkt.</p>
          <textarea id="pr-bem" rows="3" maxlength="4000" aria-describedby="pr-bem-hilfe" placeholder="z. B. Schnapper schwergängig – gereinigt und geschmiert">${esc(pr.bemerkung || "")}</textarea></section>
        ${anhaengeHtml()}
        <p class="help">Alles ist gespeichert – du kannst die Prüfung jederzeit unterbrechen und später fortsetzen.
          <button type="button" class="lnk" data-act="verwerfen">${pr.berichtigt ? "Berichtigung verwerfen" : "Entwurf verwerfen"}</button></p>
        ${abschlussHtml()}`;
    }

    function zeichnen() {
      leisteMarkieren(pr.artikel.folder_id);
      const ohneNummer = pr.entwurf && pr.eigen && !DARF.pruefen && DARF.pruefer_haekchen ? `<p class="notice">${URKUNDE_IM_PROFIL}</p>` : "";
      inhalt.innerHTML = `<div class="mat-pruefung${bearbeitbar() ? " mat-mit-leiste" : ""}">${kopf()}${ohneNummer}${bearbeitbar() ? bearbeitenHtml() : leseHtml()}</div>`;
      if (bearbeitbar()) { binden(); abschlussAktualisieren(); seitenZeichnen(); }
    }

    /* Die Karte neu zeichnen – ohne dem, der gerade darin tippt, etwas wegzunehmen: Was im fokussierten Feld
       steht, aber noch nicht gespeichert ist, bleibt stehen (es wird beim Verlassen gespeichert), eine
       geöffnete Bemerkung bleibt offen, und der Fokus kehrt auf dasselbe Element zurück – sonst schlösse
       sich am Telefon die Tastatur mitten im Satz und die Tastaturbedienung fiele an den Seitenanfang. */
    function punktErsetzen(neu) {
      pr.punkte = pr.punkte.map((x) => (x.id === neu.id ? neu : x));
      const el = $(`#pp-${neu.id}`);
      if (!el) { abschlussAktualisieren(); return; }
      const aktiv = el.contains(document.activeElement) ? document.activeElement : null;
      let fokusSel = null;
      if (aktiv) {
        if (aktiv.classList.contains("mat-pnotiz")) fokusSel = ".mat-pnotiz";
        else if (aktiv.classList.contains("mat-pwert")) fokusSel = ".mat-pwert";
        else if (aktiv.matches("input[data-foto]")) fokusSel = "input[data-foto]";
        else if (aktiv.dataset.act) fokusSel = `[data-act="${aktiv.dataset.act}"]${aktiv.dataset.wert ? `[data-wert="${aktiv.dataset.wert}"]` : ""}${aktiv.dataset.befund ? `[data-befund="${aktiv.dataset.befund}"]` : ""}`;
      }
      const tippen = aktiv && (fokusSel === ".mat-pnotiz" || fokusSel === ".mat-pwert") ? { wert: aktiv.value, von: aktiv.selectionStart, bis: aktiv.selectionEnd } : null;
      const notizAlt = $(".mat-pnotiz", el);
      const notizOffen = notizAlt && !notizAlt.hidden;
      el.outerHTML = punktHtml(neu);
      const karte = $(`#pp-${neu.id}`);
      const notiz = $(".mat-pnotiz", karte);
      if (notiz && notizOffen && notiz.hidden) { notiz.hidden = false; const plus = $('[data-act="pnotiz-auf"]', karte); if (plus) plus.remove(); }
      if (fokusSel && !$(fokusSel, karte)) {
        // Den Knopf gibt es nicht mehr (z. B. „Entfernen“ nach dem Entfernen): Fokus auf den ersten der Karte.
        const ersatz = $("button[data-act]", karte);
        if (ersatz) ersatz.focus({ preventScroll: true });
      } else if (fokusSel) {
        const ziel = $(fokusSel, karte);
        if (ziel) {
          if (tippen) { ziel.value = tippen.wert; }
          ziel.focus({ preventScroll: true });
          if (tippen && ziel.setSelectionRange) { try { ziel.setSelectionRange(tippen.von, tippen.bis); } catch (e) { /* Datumsfeld */ } }
          // Gesetzter Text löst beim Verlassen kein „change“ aus – ungespeichert Gerettetes speichert der Blur.
          const feld = fokusSel === ".mat-pnotiz" ? "notiz" : "wert";
          if (tippen && tippen.wert !== (neu[feld] || "")) {
            ziel.addEventListener("blur", () => { if (ziel.isConnected && ziel.value !== (punkt(neu.id)[feld] || "")) punktSetzen(neu.id, { [feld]: ziel.value }); }, { once: true });
          }
        }
      }
      abschlussAktualisieren();
    }

    async function punktSetzen(rid, body) {
      try { punktErsetzen((await merken(api(`${API}/pruefungen/${pr.id}/punkte/${rid}`, { method: "PUT", body }))).punkt); }
      catch (e) { toast(e.message, true); }
    }

    function binden() {
      if (gebunden) return;
      gebunden = true;
      inhalt.addEventListener("change", async (e) => {
        if (!bearbeitbar()) return;
        const el = e.target;
        if (el.matches(".mat-pwert")) { await punktSetzen(+el.dataset.rid, { wert: el.value }); return; }
        if (el.matches(".mat-pnotiz")) { await punktSetzen(+el.dataset.rid, { notiz: el.value }); return; }
        if (el.matches("input[data-foto]")) {
          const f = el.files[0];
          if (!f) return;
          const fd = new FormData(); fd.append("file", f);
          const karte = el.closest(".mat-punkt");
          if (karte) karte.classList.add("laedt");
          try { punktErsetzen((await merken(api(`${API}/pruefungen/${pr.id}/punkte/${el.dataset.foto}/foto`, { method: "POST", body: fd }))).punkt); toast("Foto gespeichert"); }
          catch (err) { toast(err.message, true); if (karte) karte.classList.remove("laedt"); }
          return;
        }
        if (el.id === "pr-bem" || el.id === "pr-art") {
          try {
            pr = (await api(`${API}/pruefungen/${pr.id}`, { method: "PUT", body: el.id === "pr-bem" ? { bemerkung: el.value } : { art: el.value } })).pruefung;
            if (el.id === "pr-art") { $("h1", inhalt).firstChild.textContent = `${PRUEFART[pr.art] || pr.art} `; toast("Prüfart geändert"); }
          } catch (err) { toast(err.message, true); }
          return;
        }
        if (el.id === "ah-kamera" || el.id === "ah-dateien") {
          seiten = seiten.concat(Array.from(el.files));
          el.value = "";
          seitenZeichnen();
        }
      });
    }

    const HINWEIS_FEST = "Zum Festschreiben brauchst du deine Unterschrift. Sie wird in deinem Profil gespeichert und als Kopie in jedes Protokoll übernommen, das du festschreibst – ändern kannst du sie dort jederzeit.";
    const HINWEIS_WEG = "Deine Unterschrift ist nicht mehr in deinem Profil hinterlegt – vielleicht in einem anderen Fenster entfernt. Zum Festschreiben unterschreibe bitte neu; sie wird wieder im Profil gespeichert und als Kopie ins Protokoll übernommen.";
    const usZeile = (bild) => (!DARF.unterschrift ? '<span class="small muted">fehlt – „Festschreiben“ fragt danach</span>'
      : `${bild ? `<img class="mat-us-bild" src="${esc(bild)}" alt="Deine Unterschrift">` : ""}<span class="small muted">aus deinem Profil – sie kommt als Kopie ins Protokoll</span>`);

    /* Vor dem Festschreiben: alles auf einen Blick, mit der Unterschrift, die ins Protokoll kommt. Der Knopf im
       Dialog schreibt fest; scheitert es, bleibt der Dialog offen und der Toast sagt warum. Fehlt die Unterschrift
       inzwischen (im Profil entfernt), fragt der Pad gleich danach – vor dem Dialog oder nach dem 403. */
    async function festschreibDialog(daten) {
      let bild = null;
      try { bild = await eigenesBild(); } catch (e) { /* dann ohne Bild */ }
      if (!DARF.unterschrift) {
        if (!(await eigeneUnterschrift(HINWEIS_WEG))) { abschlussAktualisieren(); return; }
        bild = eigenesBildMerk;
        abschlussAktualisieren();
      }
      const a = pr.artikel;
      const maengel = offeneHinweise().maengel.length;
      dialog(`<h2>Prüfung festschreiben</h2>
        <dl class="mat-daten mat-fs-daten">
          <dt>Artikel</dt><dd><strong>${esc(a.inventory_no)}</strong> · ${esc(pr.produkt.name)}</dd>
          <dt>Prüfung</dt><dd>${esc(PRUEFART[pr.art] || pr.art)} am ${esc(fmtTag(pr.prueftag || isoHeute()))}</dd>
          <dt>Ergebnis</dt><dd>${ergebnisMarke(daten.ergebnis)}${maengel ? ` <span class="small">mit ${plural(maengel, "Mangel", "Mängeln")}</span>` : ""}</dd>
          ${daten.ergebnis === "einsatzbereit" ? `<dt>Nächste Prüfung</dt><dd><strong>${esc(fmtTag(daten.next_due_on || pr.vorschlag_naechste))}</strong></dd>` : ""}
          ${daten.grund ? `<dt>Grund</dt><dd>${esc(daten.grund)}</dd>` : ""}
          <dt>Prüfer</dt><dd>${esc(pr.pruefer || "–")}${pr.urkunde ? ` · Urkundennummer ${esc(pr.urkunde)}` : ""}</dd>
          <dt>Unterschrift</dt><dd id="fs-us">${usZeile(bild)}</dd>
        </dl>
        ${daten.ergebnis === "aussondern" ? `<p class="mat-fs-warnung"><strong>„aussondern“ ist endgültig.</strong> Der Artikel wandert nach „Ausgesondert“ und zählt nicht mehr als Bestand; dazu entsteht ein Aussonderungsprotokoll.</p>` : ""}
        ${pr.berichtigt ? `<p>Diese Berichtigung ersetzt ${pr.berichtigt.protokoll_id ? `Protokoll ${esc(pr.berichtigt.protokoll_id)}` : "die ursprüngliche Prüfung"}; das Original bleibt unverändert erhalten.</p>` : ""}
        <p class="help">Danach ist die Prüfung unveränderlich; eine Korrektur geht nur als Berichtigung. Das Protokoll entsteht mit Prüfsumme.</p>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn${daten.ergebnis === "aussondern" ? " danger" : ""}" id="fs-ok" type="button">Festschreiben</button></div>`,
      (dlg, body) => {
        const knopf = $("#fs-ok", body);
        fokus(knopf);
        let erneut = false;          // nach einem 403 wegen fehlender Unterschrift genau einmal von selbst weiter
        async function festschreiben() {
          if (!DARF.unterschrift) {
            if (!(await eigeneUnterschrift(HINWEIS_WEG))) return;          // abgebrochen: der Dialog bleibt offen
            $("#fs-us", body).innerHTML = usZeile(eigenesBildMerk);
            abschlussAktualisieren();
          }
          knopf.disabled = true;
          knopf.textContent = "Wird festgeschrieben …";
          try {
            pr = (await api(`${API}/pruefungen/${pr.id}/festschreiben`, { method: "POST", body: daten })).pruefung;
            await aussonderungLaden();
            dlg.close();
            toast((pr.protokoll ? `Festgeschrieben – Protokoll ${pr.protokoll.id}` : "Festgeschrieben")
              + (aussonderung && aussonderung.protokoll ? `, Aussonderungsprotokoll ${aussonderung.protokoll.id}` : ""));
            window.scrollTo(0, 0);
            zeichnen();
          } catch (e) {
            unterschriftWeg(e);
            knopf.disabled = false;
            knopf.textContent = "Festschreiben";
            if (!DARF.unterschrift) {
              $("#fs-us", body).innerHTML = usZeile(null);
              abschlussAktualisieren();
              if (!erneut) { erneut = true; await festschreiben(); return; }
            }
            toast(e.message, true);
          }
        }
        knopf.onclick = festschreiben;
      });
    }

    aktionen = {
      pwert: (b) => punktSetzen(+b.dataset.rid, { wert: b.dataset.wert }),
      punterschrift: async (b) => {
        const x = punkt(+b.dataset.rid);
        const bild = await MatUnterschrift.zeichnen({ titel: x.text, bestehend: x.unterschrift,
          hinweis: "Hier unterschreibt, wen der Prüfpunkt nennt – mit Finger, Stift oder Maus. Die Unterschrift kommt mit der Prüfung ins Protokoll.",
          speichern: async (bild) => { punktErsetzen((await merken(api(`${API}/pruefungen/${pr.id}/punkte/${x.id}`, { method: "PUT", body: { unterschrift: bild } }))).punkt); } });
        // Die Karte ist neu gezeichnet, der Knopf von vorher weg: der Fokus geht auf „Neu unterschreiben“.
        const neu = bild && $(`#pp-${x.id} [data-act="punterschrift"]`);
        if (neu) neu.focus({ preventScroll: true });
      },
      "punterschrift-weg": async (b) => {
        if (!(await confirm("Diese Unterschrift entfernen?", "Entfernen"))) return;
        punktSetzen(+b.dataset.rid, { unterschrift: null });
      },
      pbefund: async (b) => {
        const x = punkt(+b.dataset.rid);
        // Noch einmal auf „n. z.“ tippen nimmt es zurück: wieder der Sollwert.
        const befund = b.dataset.befund === "nicht_zutreffend" && x.befund === "nicht_zutreffend" ? "ok" : b.dataset.befund;
        // „n. z.“ nimmt einem Unterschriftsfeld die Unterschrift – wie „Entfernen“ erst nachfragen.
        if (befund === "nicht_zutreffend" && x.art === "signature" && x.unterschrift
          && !(await confirm(`„${x.text}“ als nicht zutreffend markieren? Die Unterschrift darin wird dabei entfernt.`, "Unterschrift entfernen"))) return;
        punktSetzen(x.id, { befund });
      },
      "pnotiz-auf": (b) => { const k = $(`#pp-${b.dataset.rid}`); const ta = $(".mat-pnotiz", k); ta.hidden = false; b.remove(); ta.focus(); },
      "pfoto-weg": async (b) => {
        try { punktErsetzen((await api(`${API}/pruefungen/${pr.id}/punkte/${b.dataset.rid}/foto`, { method: "DELETE" })).punkt); }
        catch (e) { toast(e.message, true); }
      },
      "seite-weg": (b) => { seiten.splice(+b.dataset.i, 1); seitenZeichnen(); },
      "anhang-hoch": async () => {
        if (!seiten.length || hochladen) return;
        // Genau diese Dateien gehen hoch; was währenddessen dazukommt, bleibt für den nächsten Anhang stehen.
        const teil = seiten.slice();
        const fd = new FormData();
        teil.forEach((f) => fd.append("file", f));
        fd.append("art", $("#ah-art").value);
        fd.append("titel", $("#ah-titel").value);
        fd.append("im_protokoll", $("#ah-protokoll").checked ? "ja" : "nein");
        hochladen = true;
        seitenZeichnen();
        try {
          const r = await merken(api(`${API}/pruefungen/${pr.id}/anhaenge`, { method: "POST", body: fd }));
          pr.anhaenge.push(r.anhang);
          seiten = seiten.filter((f) => !teil.includes(f));
          $("#ah-titel").value = "";
          $("#ah-liste").innerHTML = anhaengeListe();
          toast(`Angehängt (${plural(r.anhang.seiten, "Seite", "Seiten")})`);
        } catch (e) { toast(e.message, true); }
        hochladen = false;
        seitenZeichnen();
      },
      "anhang-weg": async (b) => {
        if (!(await confirm("Diesen Anhang entfernen?", "Entfernen"))) return;
        try {
          await api(`${API}/pruefungen/${pr.id}/anhaenge/${b.dataset.id}`, { method: "DELETE" });
          pr.anhaenge = pr.anhaenge.filter((x) => x.id !== +b.dataset.id);
          $("#ah-liste").innerHTML = anhaengeListe();
        } catch (e) { toast(e.message, true); }
      },
      ergebnis: (b) => { if (b.disabled) return; ergebnis = ergebnis === b.dataset.e ? null : b.dataset.e; abschlussAktualisieren(); if (ergebnis && ergebnis !== "einsatzbereit") fokus($("#pr-grund")); },
      festschreiben: async (b) => {
        if (!ergebnis) return;
        // Was der Server sicher ablehnt, gleich hier sagen – bevor nach der Unterschrift gefragt wird. Vorher abwarten,
        // was gerade gespeichert wird: Eine eben getippte Bemerkung kommt beim Verlassen des Feldes an.
        await laufend.catch(() => {});
        const h = offeneHinweise();
        const grund = ergebnis === "einsatzbereit" ? "" : $("#pr-grund").value.trim();
        if (h.offen.length) { toast("Noch ohne Befund: " + h.offen.slice(0, 5).map((x) => x.text).join("; "), true); return; }
        if (h.ohneFoto.length) { toast("Jeder Mangel braucht ein Foto – es fehlt bei: " + h.ohneFoto.slice(0, 5).map((x) => x.text).join("; "), true); return; }
        if (h.ohneNotiz.length) {
          toast("Jeder Mangel braucht eine Bemerkung – sie fehlt bei: " + h.ohneNotiz.slice(0, 5).map((x) => x.text).join("; "), true);
          fokus($(`#pp-${h.ohneNotiz[0].id} .mat-pnotiz`)); return;
        }
        if (ergebnis !== "einsatzbereit" && !h.maengel.length && !grund) { toast(`Ohne Mangel braucht „${ERGEBNIS[ergebnis]}“ einen Grund.`, true); fokus($("#pr-grund")); return; }
        b.disabled = true;
        try {
          if (!(await eigeneUnterschrift(HINWEIS_FEST))) return;
          abschlussAktualisieren();
          await laufend.catch(() => {});
          const daten = { ergebnis, grund, bemerkung: $("#pr-bem").value };
          if (ergebnis === "einsatzbereit") daten.next_due_on = $("#pr-due").value || null;
          await festschreibDialog(daten);
        } finally { if (b.isConnected) b.disabled = !ergebnis; }
      },
      berichtigen: () => {
        dialog(`<h2>Prüfung berichtigen</h2>
          <p>Die Berichtigung ist ein neuer Entwurf mit allen Befunden, Fotos und Anhängen dieser Prüfung und demselben Prüftag (${esc(fmtTag(pr.datum))}).
            Darin änderst du, was falsch war, und schreibst ihn wie jede Prüfung fest – erst dann gilt er am Artikel.</p>
          <p class="help">Das Original bleibt unverändert${pr.protokoll ? ` mit Protokoll ${esc(pr.protokoll.id)}` : ""} erhalten und zeigt danach „berichtigt durch …“.</p>
          <label for="bg-grund">Grund der Berichtigung</label><input type="text" id="bg-grund" maxlength="300" placeholder="z. B. Messwert falsch übertragen">
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="bg-ok" type="button">Berichtigung beginnen</button></div>`,
        (dlg, body) => {
          const feld = $("#bg-grund", body);
          fokus(feld);
          feld.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#bg-ok", body).click(); } });
          $("#bg-ok", body).onclick = async (ev) => {
            const grund = feld.value.trim();
            if (!grund) { toast("Bitte den Grund der Berichtigung angeben.", true); feld.focus(); return; }
            const knopf = ev.currentTarget;
            knopf.disabled = true;
            try { const r = await api(`${API}/pruefungen/${pr.id}/berichtigen`, { method: "POST", body: { grund } }); location.href = `/material/pruefung/${r.pruefung.id}`; }
            catch (e) {
              if (e.status === 409) {
                // Inzwischen nicht mehr berichtigbar (etwa anderswo schon begonnen): neu laden – dann steht oben,
                // was los ist, mit dem Weg zum Entwurf, und der Knopf sagt, warum er gesperrt ist.
                dlg.close();
                try { pr = (await api(`${API}/pruefungen/${pr.id}`)).pruefung; zeichnen(); } catch (err) { /* bleibt so */ }
                toast(e.message, true);
                return;
              }
              toast(e.message, true); knopf.disabled = false;
            }
          };
        });
      },
      summe: summeKopieren,
      verwerfen: async () => {
        const b = pr.berichtigt;
        const frage = b ? `Die Berichtigung verwerfen? Was du darin geändert hast, geht verloren. Das Original${b.protokoll_id ? ` (Protokoll ${b.protokoll_id})` : ""} bleibt unverändert gültig.`
          : "Den Entwurf verwerfen? Befunde, Fotos und Anhänge dieser Prüfung gehen verloren, der Artikel ist wieder frei.";
        if (!(await confirm(frage, "Verwerfen"))) return;
        // Eine verworfene Berichtigung führt zurück zum Original, das weiter gilt.
        try { await api(`${API}/pruefungen/${pr.id}`, { method: "DELETE" }); location.href = b ? `/material/pruefung/${b.id}` : `/material/artikel/${pr.item_id}`; }
        catch (e) { toast(e.message, true); }
      },
      freigeben: () => reservierungFreigeben(pr.id, pr.pruefer, async () => { location.href = `/material/artikel/${pr.item_id}`; }),
    };
    await aussonderungLaden();
    zeichnen();
  }

  /* --- Prüfdurchgang ---------------------------------------------------------------------------------- */
  async function durchgangAnsicht() {
    let filter = "";
    let d = null;
    let sort = { feld: null, richtung: "auf" };
    // Der Durchgang kommt als Ganzes – hier sortiert der Browser selbst.
    const ZUSTAND_REIHE = { in_pruefung: 0, offen: 1, nicht_geprueft: 1, ausgenommen: 2, erledigt: 3 };
    const STATUS_RANG = { ueberfaellig: 0, lebensdauer: 1, neu: 2, gesperrt: 3, bald_faellig: 4, einsatzbereit: 5, ausgesondert: 6 };
    const SORTWERT = {
      inventar: (a) => a.inventory_no, hersteller: (a) => (a.manufacturer || "").toLowerCase(), produkt: (a) => (a.model || "").toLowerCase(),
      ablage: (a) => (a.pfad || "").toLowerCase(), stand: (a) => ZUSTAND_REIHE[a.zustand], status: (a) => STATUS_RANG[a.status],
    };
    function sortiert(liste) {
      if (!sort.feld) return liste;
      const wert = SORTWERT[sort.feld];
      const r = sort.richtung === "ab" ? -1 : 1;
      return liste.slice().sort((x, y) => {
        const a = wert(x), b = wert(y);
        return (a < b ? -1 : a > b ? 1 : 0) * r || x.inventory_no.localeCompare(y.inventory_no);
      });
    }
    async function laden() { d = (await api(`${API}/durchgaenge/${DATEN.id}`)).durchgang; }
    function zeile(a) {
      const darf = d.offen && (DARF.verwalten || DARF.pruefen);
      let zustand;
      let knopf = "";
      if (a.zustand === "erledigt") {
        zustand = `${ergebnisMarke(a.pruefung.ergebnis)} <a class="small" href="/material/pruefung/${a.pruefung.id}">${esc(fmtTag(a.pruefung.datum))}, ${esc(a.pruefung.pruefer)}</a>`;
      } else if (a.zustand === "ausgenommen") {
        zustand = `<span class="badge grey">ausgenommen</span> <span class="small">${esc(a.ausnahme.grund)}</span> <span class="muted small">(${esc(a.ausnahme.von || "")})</span>`;
        if (darf && a.lock_state !== "ausgesondert") knopf = `<button type="button" class="btn secondary small" data-act="einbeziehen" data-id="${a.id}">Einbeziehen</button>`;
      } else if (a.zustand === "nicht_geprueft") {
        zustand = '<span class="badge grey">nicht geprüft</span>';
      } else if (a.zustand === "in_pruefung") {
        zustand = `<span class="badge">in Prüfung</span> <span class="small">bei ${esc(a.entwurf.pruefer)} seit ${esc(fmtZeit(a.entwurf.seit))}</span>`;
        if (a.entwurf.eigen && DARF.pruefen) knopf = `<a class="btn secondary small" href="/material/pruefung/${a.entwurf.id}">Weiter prüfen</a>`;
        else if (DARF.verwalten && d.offen) knopf = `<button type="button" class="btn secondary small" data-act="freigeben" data-id="${a.entwurf.id}" data-wer="${esc(a.entwurf.pruefer)}">Freigeben</button>`;
      } else {
        zustand = '<span class="muted">offen</span>';
        if (d.offen && DARF.pruefen && a.lock_state !== "ausgesondert") knopf = `<a class="btn secondary small" href="/material/artikel/${a.id}/pruefung/neu?durchgang=${d.id}">Prüfen</a>`;
        if (darf) knopf += `<button type="button" class="btn secondary small" data-act="ausnehmen" data-id="${a.id}" data-nr="${esc(a.inventory_no)}">Ausnehmen</button>`;
      }
      return `<tr class="z-${a.zustand}"><td data-l="Inventar-Nr."><a class="mat-inv" href="/material/artikel/${a.id}"><strong>${esc(a.inventory_no)}</strong></a></td>
        <td data-l="Hersteller">${esc(a.manufacturer || "")}</td>
        <td data-l="Produkt">${produktZelle(a)}<div class="small muted">SN ${esc(a.serial_no)}</div></td>
        <td data-l="Ablage">${esc(a.pfad)}</td><td data-l="Stand">${zustand}</td><td data-l="Status">${statusMarke(a.status)}</td>
        <td class="tabelle-aktionen">${knopf}</td></tr>`;
    }
    function zeichnen() {
      leisteMarkieren(d.folder_id);
      const z = d.zaehlung;
      const darf = DARF.verwalten || DARF.pruefen;
      const liste = sortiert(d.artikel.filter((a) => !filter || a.zustand === filter));
      const s = sort;
      // Laufend: offen, in Prüfung, erledigt, ausgenommen. Vorbei: erledigt, ausgenommen – nach einem Abbruch
      // dazu „nicht geprüft“.
      const zustaende = d.offen ? [["", "alle"], ["offen", "offen"], ["in_pruefung", "in Prüfung"], ["erledigt", "erledigt"], ["ausgenommen", "ausgenommen"]]
        : [["", "alle"], ["erledigt", "erledigt"], ["ausgenommen", "ausgenommen"]].concat(z.nicht_geprueft ? [["nicht_geprueft", "nicht geprüft"]] : []);
      inhalt.innerHTML = `<div class="mat-pfad"><a href="/material/pruefungen">Prüfungen</a> / Prüfdurchgang</div>
        <div class="page-head"><h1>${esc(d.titel)} ${d.offen ? '<span class="badge">offen</span>' : `<span class="badge grey">${d.abgebrochen ? "abgebrochen" : "abgeschlossen"}</span>`}</h1>
          <div class="btn-row">${d.offen && darf ? `<button class="btn secondary" data-act="abbrechen">Durchgang abbrechen</button>
            <button class="btn" data-act="schliessen" ${d.abschliessbar ? "" : "disabled"}>Durchgang abschließen</button>` : ""}
            ${!d.offen && d.protokoll ? `<a class="btn secondary" href="${esc(d.protokoll.url)}" target="_blank" rel="noopener">Sammelprotokoll (PDF)</a>` : ""}</div></div>
        <p>Ordner <a href="/material/ordner/${d.folder_id}">${esc(d.ordner)}</a> · eröffnet ${esc(fmtTag(d.eroeffnet_am))} von ${esc(d.eroeffnet_von || "–")}
          ${d.offen ? "" : ` · ${d.abgebrochen ? "abgebrochen" : "abgeschlossen"} ${esc(fmtTag(d.geschlossen_am))} von ${esc(d.geschlossen_von || "–")}`}</p>
        ${d.protokoll ? `<p class="mat-protokoll-zeile">Sammelprotokoll <strong class="mat-hash">${esc(d.protokoll.id)}</strong> · festgeschrieben ${esc(fmtZeit(d.protokoll.festgeschrieben))}
          · SHA-256 (erste ${esc(d.protokoll.bytes)} Bytes) ${summeKnopf(d.protokoll.sha256)} · <a href="/material/pruefen">Protokoll prüfen</a></p>`
          : d.offen ? "" : '<p class="small muted">Vor Einführung des Festschreibens geschlossen – ohne Sammelprotokoll.</p>'}
        <div class="mat-kacheln mat-rundenzahlen">${zustaende.map(([k, t]) => `<div class="mat-kachel z-${k || "gesamt"}"><strong>${z[k || "gesamt"]}</strong><span>${k ? t : "Artikel"}</span></div>`).join("")}</div>
        <p>${fortschritt(z)}</p>
        ${d.offen ? `<p class="help">Jeder öffnet seinen Artikel mit „Prüfen“ und reserviert ihn damit – die anderen sehen „in Prüfung bei …“. Abschließen geht, sobald jeder Artikel geprüft oder mit Grund ausgenommen ist. Beim Abschließen entsteht das Sammelprotokoll mit allen Prüfern.</p>` : ""}
        <div class="c-tabs mat-filter">${zustaende.map(([f, t]) => `<button type="button" data-act="filter" data-f="${f}" class="${f === filter ? "sel" : ""}">${esc(t)}${f ? ` (${z[f]})` : ""}</button>`).join("")}</div>
        ${liste.length ? `<table class="list mat-tabelle mat-runde"><thead><tr>${sortKopf("Inventar-Nr.", "inventar", s)}${sortKopf("Hersteller", "hersteller", s)}${sortKopf("Produkt", "produkt", s)}${sortKopf("Ablage", "ablage", s)}${sortKopf("Stand", "stand", s)}${sortKopf("Status", "status", s)}<th></th></tr></thead><tbody>${liste.map(zeile).join("")}</tbody></table>` : leer("Keine Artikel in dieser Auswahl.")}
        ${d.pruefer.length ? `<section class="section"><h2>Prüfer in diesem Durchgang</h2><ul>${d.pruefer.map((x) => `<li>${esc(x.name)}${x.urkunde ? ` · Urkundennummer ${esc(x.urkunde)}` : ""} – ${plural(x.anzahl, "Prüfung", "Prüfungen")}</li>`).join("")}</ul></section>` : ""}`;
    }
    async function neu() { await laden(); zeichnen(); }
    aktionen = {
      filter: (b) => { filter = b.dataset.f; zeichnen(); },
      sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); zeichnen(); },
      summe: summeKopieren,
      freigeben: (b) => reservierungFreigeben(+b.dataset.id, b.dataset.wer, neu),
      einbeziehen: async (b) => {
        try { await api(`${API}/durchgaenge/${d.id}/einbeziehen`, { method: "POST", body: { item_id: +b.dataset.id } }); await neu(); }
        catch (e) { toast(e.message, true); }
      },
      ausnehmen: (b) => {
        dialog(`<h2>${esc(b.dataset.nr)} ausnehmen</h2>
          <p class="help">Ein ausgenommener Artikel wird in diesem Durchgang nicht geprüft. Der Grund steht später im Sammelprotokoll.</p>
          <label for="dn-grund">Grund</label><input type="text" id="dn-grund" maxlength="200" list="dn-vorschlaege" placeholder="z. B. nicht auffindbar">
          <datalist id="dn-vorschlaege"><option value="nicht auffindbar"><option value="beim Hersteller in Reparatur"><option value="kürzlich geprüft"></datalist>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="dn-ok" type="button">Ausnehmen</button></div>`,
        (dlg, body) => {
          fokus($("#dn-grund", body));
          $("#dn-ok", body).onclick = async (ev) => {
            const knopf = ev.currentTarget;
            knopf.disabled = true;
            try { await api(`${API}/durchgaenge/${d.id}/ausnehmen`, { method: "POST", body: { item_id: +b.dataset.id, grund: $("#dn-grund", body).value } }); dlg.close(); await neu(); }
            catch (e) { toast(e.message, true); knopf.disabled = false; }
          };
        });
      },
      schliessen: async (b) => {
        if (!(await confirm(`Den Durchgang „${d.titel}“ abschließen? Danach lässt sich darin nichts mehr prüfen oder ausnehmen. Das Sammelprotokoll mit allen Prüfern wird festgeschrieben.`, "Abschließen"))) return;
        b.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge/${d.id}/abschliessen`, { method: "POST", body: {} });
          toast(r.durchgang && r.durchgang.protokoll ? `Durchgang abgeschlossen – Sammelprotokoll ${r.durchgang.protokoll.id}` : "Durchgang abgeschlossen");
          await neu();
        } catch (e) { toast(e.message, true); b.disabled = false; }
      },
      abbrechen: async (b) => {
        const z = d.zaehlung;
        const weiter = z.in_pruefung ? " Offene Prüfungen darin laufen als einzelne Prüfungen weiter." : "";
        const text = z.erledigt
          ? `Den Durchgang „${d.titel}“ abbrechen? Er endet ohne Abschluss: ${z.erledigt} geprüft, ${z.ausgenommen} ausgenommen, ${z.offen + z.in_pruefung} nicht geprüft. Was geprüft ist, bleibt dokumentiert – das Sammelprotokoll wird mit diesem Stand festgeschrieben.`
          : `Den Durchgang „${d.titel}“ abbrechen? Darin ist noch nichts geprüft – er wird ganz entfernt.`;
        if (!(await confirm(text + weiter, "Durchgang abbrechen"))) return;
        b.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge/${d.id}/abbrechen`, { method: "POST", body: {} });
          if (!r.durchgang) { location.href = "/material/pruefungen"; return; }
          filter = "";
          toast(r.durchgang.protokoll ? `Durchgang abgebrochen – Sammelprotokoll ${r.durchgang.protokoll.id}` : "Durchgang abgebrochen"); await neu();
        } catch (e) { toast(e.message, true); b.disabled = false; }
      },
    };
    await neu();
  }

  /* --- Produktmeldungen ------------------------------------------------------------------------------
     Wer Artikel anlegt, meldet Produkte, die im Katalog fehlen (Links, Fotos, Bemerkung). Katalogpfleger
     legen sie an (Produktdialog mit den Angaben der Meldung), ordnen ein vorhandenes zu oder lehnen mit
     Begründung ab; der Melder bekommt jeweils eine Mail. */
  const MELDESTATUS = { offen: "offen", eingepflegt: "eingepflegt", abgelehnt: "abgelehnt" };
  const meldestatusMarke = (s) => `<span class="mat-mstatus m-${esc(s)}">${esc(MELDESTATUS[s] || s)}</span>`;
  const meldungName = (m) => `${m.manufacturer} ${m.model}`;
  const kurzLink = (u) => u.replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "");

  function meldeDetails(m) {
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    const daten = [m.article_no ? zeile("Artikelnummer", esc(m.article_no)) : "", m.norm ? zeile("Norm", esc(m.norm)) : "",
      m.kategorie ? zeile("Kategorie (Vorschlag)", esc(m.kategorie.pfad)) : "",
      m.links.length ? zeile("Links", m.links.map((l) => `<a href="${esc(l)}" target="_blank" rel="noopener noreferrer">${esc(kurzLink(l))}</a>`).join("<br>")) : "",
      m.note ? zeile("Bemerkung", `<span class="mat-text">${esc(m.note)}</span>`) : ""].join("");
    return `${daten ? `<dl class="mat-daten mat-meldung-daten">${daten}</dl>` : ""}
      ${m.fotos.length ? `<div class="mat-meldung-fotos">${m.fotos.map((f) => bildLink(f.web, f.original, `Foto zur Meldung ${m.manufacturer || ""} ${m.model || ""}`.trim(), `meldung-${m.id}`, `<img src="${esc(f.vorschau)}" alt="Foto zur Meldung" loading="lazy">`)).join("")}</div>` : ""}`;
  }
  // Im Produktdialog: was der Melder wusste – zum Nachschlagen, während die Felder schon vorbelegt sind.
  const meldeKasten = (m) => `<div class="mat-meldekasten"><p class="small">Gemeldet von ${esc(m.created_by_name || "–")} am ${esc(fmtTag(m.created_at))}${m.ordner ? ` für ${esc(m.ordner.pfad)}` : ""}</p>${meldeDetails(m)}</div>`;

  // bearbeiten: Katalogpfleger in der Liste aller Meldungen – nur sie bekommen die Knöpfe zum Abarbeiten.
  function meldeKarte(m, bearbeiten) {
    const wer = (name) => (name ? ` von ${esc(name)}` : "");
    const knoepfe = [];
    if (bearbeiten && m.status === "offen") {
      knoepfe.push(`<button type="button" class="btn secondary small" data-act="anlegen" data-id="${m.id}">Produkt anlegen</button>`,
                   `<button type="button" class="btn secondary small" data-act="zuordnen" data-id="${m.id}">Vorhandenes zuordnen</button>`,
                   `<button type="button" class="btn secondary small" data-act="ablehnen" data-id="${m.id}">Ablehnen</button>`);
    }
    if (m.eigen && DARF.verwalten && m.status === "eingepflegt" && m.produkt) {
      knoepfe.push(`<a class="btn secondary small" href="/material/artikel/neu?produkt=${m.produkt.id}${m.ordner ? `&ordner=${m.ordner.id}` : ""}">Artikel davon anlegen</a>`);
    }
    // Eigene Meldungen löscht der Melder selbst – offen oder erledigt.
    if (m.eigen) knoepfe.push(`<button type="button" class="btn secondary small" data-act="loeschen" data-id="${m.id}">Löschen</button>`);
    return `<article class="mat-meldung m-${esc(m.status)}">
      <div class="mat-meldung-kopf"><h2>${esc(meldungName(m))}</h2>${meldestatusMarke(m.status)}</div>
      <p class="muted small">gemeldet${wer(m.created_by_name)} am ${esc(fmtTag(m.created_at))}${m.ordner ? ` · für ${esc(m.ordner.pfad)}` : ""}</p>
      ${meldeDetails(m)}
      ${m.treffer ? `<p class="notice">Steht inzwischen im Katalog: <a href="/material/katalog/produkt/${m.treffer.id}">${esc(produktName(m.treffer))}</a>${m.treffer.article_no ? ` <span class="muted">${esc(m.treffer.article_no)}</span>` : ""}
        ${bearbeiten ? `<button type="button" class="btn secondary small" data-act="treffer" data-id="${m.id}">Zuordnen</button>` : ""}</p>` : ""}
      ${m.status === "eingepflegt" ? `<p class="mat-meldung-ergebnis">Eingepflegt${wer(m.resolved_by_name)} am ${esc(fmtTag(m.resolved_at))}:
        ${m.produkt ? `<a href="/material/katalog/produkt/${m.produkt.id}">${esc(produktName(m.produkt))}</a>` : '<span class="muted">Produkt inzwischen gelöscht</span>'}
        ${m.answer ? `<br><span class="mat-text">${esc(m.answer)}</span>` : ""}</p>` : ""}
      ${m.status === "abgelehnt" ? `<p class="mat-meldung-ergebnis">Abgelehnt${wer(m.resolved_by_name)} am ${esc(fmtTag(m.resolved_at))}: <span class="mat-text">${esc(m.answer)}</span></p>` : ""}
      ${knoepfe.length ? `<div class="btn-row">${knoepfe.join("")}</div>` : ""}
    </article>`;
  }

  async function meldungen() {
    let filter = DATEN.status || null;
    let eigene = null;            // null: was der Server für die Rolle vorsieht; Materialwarte schalten zwischen „1“ und „0“
    leisteMarkieren(null);
    async function zeichnen() {
      const q = new URLSearchParams();
      if (filter) q.set("status", filter);
      if (eigene) q.set("eigene", eigene);
      const d = await api(`${API}/meldungen${String(q) ? `?${q}` : ""}`);
      filter = d.filter;
      const liste = d.meldungen;
      const meldung = (b) => liste.find((m) => m.id === +b.dataset.id);
      // Lesende (Führungskraft, Materialwart in „alle“) sehen dieselben Karten ohne Knöpfe zum Abarbeiten.
      const hilfe = d.bearbeiten ? "Materialwarte melden hier Produkte, die ihnen beim Anlegen von Artikeln im Katalog fehlen. „Produkt anlegen“ übernimmt ihre Angaben in den Produktdialog. Der Melder bekommt eine Mail, sobald das Produkt im Katalog ist – oder deine Begründung, wenn du ablehnst."
        : d.alle ? "Materialwarte melden hier Produkte, die ihnen beim Anlegen von Artikeln im Katalog fehlen; die Katalogpfleger nehmen sie auf oder lehnen sie mit Begründung ab."
          : "Produkte, die du beim Anlegen von Artikeln als fehlend gemeldet hast. Du bekommst eine Mail, sobald ein Katalogpfleger sie bearbeitet hat.";
      inhalt.innerHTML = `<div class="page-head"><h1>${d.alle ? "Produktmeldungen" : "Deine Produktmeldungen"}</h1>
          <div class="btn-row"><a class="btn secondary" href="/material/katalog">Katalog</a>${DARF.verwalten ? '<a class="btn secondary" href="/material/artikel/neu">+ Artikel</a>' : ""}</div></div>
        <p class="help">${hilfe}${DARF.verwalten && !DARF.katalog ? ` <button type="button" class="lnk" data-act="eigene">${d.alle ? "Nur deine zeigen" : "Alle Meldungen zeigen"}</button>` : ""}</p>
        <div class="c-tabs mat-filter" role="group" aria-label="Status">${[["offen", "offen"], ["erledigt", "erledigt"], ["alle", "alle"]].map(([w, t]) => `<button type="button" class="${w === filter ? "sel" : ""}" data-act="filter" data-f="${w}" aria-pressed="${w === filter}">${t}${w === "offen" && d.offen ? ` (${d.offen})` : ""}</button>`).join("")}</div>
        ${liste.length ? liste.map((m) => meldeKarte(m, d.bearbeiten)).join("") : leer(filter === "offen" ? "Keine offenen Meldungen." : "Keine Meldungen.")}`;
      aktionen = {
        filter: (b) => {
          filter = b.dataset.f;
          try { history.replaceState(null, "", `/material/katalog/meldungen?status=${filter}`); } catch (e) { /* nur die Adresszeile */ }
          zeigen(zeichnen);
        },
        eigene: () => { eigene = d.alle ? "1" : "0"; filter = null; zeigen(zeichnen); },
        anlegen: (b) => {
          const m = meldung(b);
          produktDialog({ meldung: m, manufacturer: m.manufacturer, model: m.model, article_no: m.article_no, norm: m.norm,
                          category_id: m.kategorie ? m.kategorie.id : null });
        },
        zuordnen: (b) => zuordnenDialog(meldung(b), zeichnen),
        ablehnen: (b) => ablehnenDialog(meldung(b), zeichnen),
        treffer: async (b) => {
          const m = meldung(b);
          if (!(await confirm(`„${meldungName(m)}“ dem Produkt „${produktName(m.treffer)}“ zuordnen? Der Melder bekommt Bescheid.`, "Zuordnen"))) return;
          try {
            await api(`${API}/meldungen/${m.id}/zuordnen`, { method: "POST", body: { product_id: m.treffer.id } });
            toast("Zugeordnet – der Melder bekommt Bescheid."); await zeichnen();
          } catch (e) { toast(e.message, true); }
        },
        loeschen: async (b) => {
          const m = meldung(b);
          const folge = m.status === "offen" ? " Sie verschwindet damit auch bei den Katalogpflegern."
            : m.status === "eingepflegt" ? " Das Produkt bleibt im Katalog." : "";
          if (!(await confirm(`Deine Meldung „${meldungName(m)}“ löschen?${folge}`, "Löschen"))) return;
          try { await api(`${API}/meldungen/${m.id}`, { method: "DELETE" }); toast("Meldung gelöscht"); await zeichnen(); }
          catch (e) { toast(e.message, true); }
        },
      };
    }
    await zeichnen();
  }

  function zuordnenDialog(m, danach) {
    dialog(`<h2>Vorhandenem Produkt zuordnen</h2>
      <p class="help">Für „${esc(meldungName(m))}“ – wenn das Produkt schon im Katalog steht, etwa anders geschrieben oder mit anderer Artikelnummer.</p>
      <label for="zu-q">Produkt suchen</label>
      <div class="mat-produktwahl"><input type="search" id="zu-q" autocomplete="off" ${TASTATUR_SUCHE} value="${esc(m.manufacturer)}"><div id="zu-treffer" class="mat-treffer"></div></div>
      <div id="zu-gewaehlt" class="mat-gewaehlt" hidden></div>
      <label for="zu-antwort">Anmerkung für den Melder (optional, steht in seiner Mail)</label><textarea id="zu-antwort" rows="2" maxlength="1000"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="zu-ok" type="button" disabled>Zuordnen</button></div>`,
    (dlg, body) => {
      let gewaehlt = null;
      let los = null;
      async function suchen() {
        const q = $("#zu-q", body).value.trim();
        if (!q) { trefferLeeren($("#zu-treffer", body)); return; }
        produktTreffer($("#zu-treffer", body), q, (p) => {
          gewaehlt = p;
          $("#zu-gewaehlt", body).hidden = false;
          $("#zu-gewaehlt", body).innerHTML = `<strong>${esc(produktName(gewaehlt))}</strong> <span class="muted">${esc(gewaehlt.article_no || "")}</span>`;
          trefferLeeren($("#zu-treffer", body));
          $("#zu-ok", body).disabled = false;
        }, '<p class="help">Kein Produkt gefunden.</p>');
      }
      $("#zu-q", body).addEventListener("input", () => { clearTimeout(los); los = setTimeout(suchen, 200); });
      suchen();
      $("#zu-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          await api(`${API}/meldungen/${m.id}/zuordnen`, { method: "POST", body: { product_id: gewaehlt.id, antwort: $("#zu-antwort", body).value } });
          dlg.close(); toast("Zugeordnet – der Melder bekommt Bescheid."); await danach();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  function ablehnenDialog(m, danach) {
    dialog(`<h2>Meldung ablehnen</h2>
      <p>„${esc(meldungName(m))}“, gemeldet von ${esc(m.created_by_name || "–")}</p>
      <label for="ab-antwort">Begründung (bekommt der Melder per Mail)</label>
      <textarea id="ab-antwort" rows="3" maxlength="1000" placeholder="z. B. gehört nicht ins Modul, steht unter anderem Namen im Katalog"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="ab-ok" type="button">Ablehnen</button></div>`,
    (dlg, body) => {
      fokus($("#ab-antwort", body));
      $("#ab-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          await api(`${API}/meldungen/${m.id}/ablehnen`, { method: "POST", body: { antwort: $("#ab-antwort", body).value } });
          dlg.close(); toast("Abgelehnt – der Melder bekommt die Begründung."); await danach();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  async function meldungenZaehlen(el) {
    if (!el) return;
    try {
      const n = (await api(`${API}/meldungen?status=offen`)).offen || 0;
      el.textContent = n > 99 ? "99+" : n;
      el.title = plural(n, "offene Meldung", "offene Meldungen");
      el.hidden = !n;
    } catch (e) { /* der Zähler ist Beiwerk */ }
  }

  // Ein Produkt melden, das beim Anlegen eines Artikels im Katalog fehlt. v: Vorbelegung (aus der Suche) und Ordner.
  async function meldungDialog(v, danach) {
    const kats = await kategorienLaden();
    dialog(`<h2>Fehlendes Produkt melden</h2>
      <p class="help">Ein Produktkatalogpfleger nimmt es in den Katalog auf. Du bekommst eine Mail, sobald du Artikel davon anlegen kannst.</p>
      <div class="field-row"><div><label for="me-her">Hersteller</label><input type="text" id="me-her" maxlength="120" value="${esc(v.manufacturer || "")}" ${TASTATUR_NAME}></div>
        <div><label for="me-mod">Modell</label><input type="text" id="me-mod" maxlength="160" value="${esc(v.model || "")}" ${TASTATUR_NAME}></div></div>
      <div class="field-row"><div><label for="me-art">Artikelnummer des Herstellers</label><input type="text" id="me-art" maxlength="80" ${TASTATUR_NUMMER}><div class="help" id="me-art-hilfe"></div></div>
        <div><label for="me-norm">Norm</label><input type="text" id="me-norm" maxlength="200" placeholder="z. B. EN 362" ${TASTATUR_NUMMER}></div></div>
      <label for="me-kat">Kategorie</label><select id="me-kat"><option value="">– weiß ich nicht –</option>${kategorieOptionen(kats, null)}</select>
      <label for="me-links">Links</label><textarea id="me-links" rows="3" ${TASTATUR_ADRESSE} placeholder="https://… – je Zeile eine Adresse: Herstellerseite, Gebrauchsanleitung, Händler"></textarea>
      <div class="mat-feldkopf">Fotos (bis zu 3)</div>${dateiKnopf("me-fotos", '<span aria-hidden="true">📷</span> Fotos wählen …', "image/*", true)}
      <div class="help">Etikett oder Typenschild – darauf stehen meist Hersteller, Modell, Norm und Herstelldatum.</div>
      <label for="me-note">Bemerkung</label><textarea id="me-note" rows="3" maxlength="2000" placeholder="Was hilft beim Einpflegen? z. B. Größe, Farbe, wo gekauft"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="me-ok" type="button">Melden</button></div>`,
    (dlg, body) => {
      fokus($("#me-her", body));
      artikelnummerPruefen($("#me-art", body), $("#me-art-hilfe", body), null);
      dateiKnopfVerdrahten(body, "me-fotos");
      $("#me-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const fotos = Array.from($("#me-fotos", body).files);
        if (fotos.length > 3) { toast("Höchstens 3 Fotos.", true); return; }
        const fd = new FormData();
        const felder = { manufacturer: $("#me-her", body).value, model: $("#me-mod", body).value, article_no: $("#me-art", body).value,
                         norm: $("#me-norm", body).value, category_id: $("#me-kat", body).value, folder_id: v.folder_id || "",
                         links: $("#me-links", body).value, note: $("#me-note", body).value };
        Object.entries(felder).forEach(([k, w]) => fd.append(k, w));
        fotos.forEach((f) => fd.append("fotos", f));
        knopf.disabled = true;
        try {
          await api(`${API}/meldungen`, { method: "POST", body: fd });
          dlg.close();
          toast("Gemeldet – du bekommst eine Mail, sobald das Produkt im Katalog ist.");
          if (danach) await danach();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Rückrufe (Lieferung 4) ---------------------------------------------------------------------------
     Ein Katalogpfleger legt am Produkt einen Rückruf an; er steht am Produkt (laufende oben, beendete eingeklappt),
     als Banner an jedem betroffenen Artikel und als Kasten auf der Übersicht. Gesperrt wird nichts automatisch:
     Prüfer sperren mit dem Grund „Rückruf“ (Knopf im Banner). Je Artikel ist ein Rückruf „offen“ oder „erledigt“
     (gesperrt oder nach dem Rückruf geprüft) – das rechnet der Server, nie die Oberfläche. */
  const RR_GRUND = { gesperrt: "gesperrt", geprueft: "nach dem Rückruf geprüft", ausgesondert: "ausgesondert" };
  const rrZustand = (z, grund) => `<span class="mat-rr-zustand ${z === "erledigt" ? "erledigt" : "offen"}">${z === "erledigt" ? `erledigt${RR_GRUND[grund] ? ` – ${esc(RR_GRUND[grund])}` : ""}` : "offen"}</span>`;
  const rrLink = (url, text) => (url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text || kurzLink(url))}</a>` : "");

  // Kasten auf der Übersicht: laufende Rückrufe, die Artikel im Bestand betreffen – wo noch etwas offen ist, zuerst.
  function rueckrufKasten(liste) {
    if (!liste || !liste.length) return "";
    return `<section class="section mat-rr-kasten" aria-label="Rückrufe"><h2>Rückrufe</h2><ul class="mat-rr-liste">${liste.map((r) => `<li>
        <span class="mat-rr-marke">Rückruf</span>
        <span class="mat-rr-was"><a href="/material/katalog/produkt/${r.produkt.id}"><strong>${esc(produktName(r.produkt))}</strong></a> – ${esc(r.title)}</span>
        <span class="small">${plural(r.betroffen, "Artikel", "Artikel")} betroffen · ${r.offen ? `<strong class="mat-warn">${r.offen} offen</strong>` : "alle erledigt"}</span></li>`).join("")}</ul></section>`;
  }

  // Hinweis in der Prüfung: Für den Artikel läuft ein Rückruf, der für ihn noch offen ist. Beschreibung und Empfehlung
  // stehen am Artikel; eine Prüfung nach dem Rückruf erledigt ihn für den Artikel.
  function rueckrufHinweis(titel, artikelId, berichtigung) {
    return titel.length ? `<div class="mat-banner mat-rr-banner" role="note"><p class="mat-rr-titel">RÜCKRUF: ${titel.map(esc).join(" · ")}</p>
      <p class="mat-rr-zeile">Was der Hersteller empfiehlt, steht am <a href="/material/artikel/${artikelId}">Artikel</a>. ${berichtigung
        ? "Eine Berichtigung erledigt den Rückruf nicht – dafür braucht es eine neue Prüfung oder eine Sperre."
        : "Mit dem Abschluss dieser Prüfung gilt der Rückruf für den Artikel als erledigt."}</p></div>` : "";
  }

  // Banner am Artikel – je laufendem Rückruf, der ihn betrifft. Prüfer sperren von hier mit dem Grund „Rückruf“.
  function rueckrufBanner(a) {
    return (a.rueckrufe || []).map((r) => {
      const offen = r.zustand !== "erledigt";
      const sperren = offen && DARF.pruefen && a.lock_state === "frei" && !a.entwurf;
      return `<div class="mat-banner mat-rr-banner${offen ? "" : " erledigt"}" role="note">
        <p class="mat-rr-titel">RÜCKRUF: ${esc(r.title)}</p>
        ${r.description ? `<p class="mat-text mat-rr-text">${esc(r.description)}</p>` : ""}
        <p class="mat-rr-zeile">${r.url ? `${rrLink(r.url, "Meldung des Herstellers")} · ` : ""}seit ${esc(S.fmtDate(r.created_at))} · ${r.alle ? "alle Artikel des Produkts" : "betrifft diese Seriennummer"}
          · für diesen Artikel ${rrZustand(r.zustand, r.grund)}${offen ? " – noch nicht gesperrt und seit dem Rückruf nicht geprüft" : ""}</p>
        ${sperren ? `<div class="btn-row"><button class="btn small" type="button" data-act="rr-sperren" data-id="${r.id}">Sperren (Rückruf)</button></div>` : ""}
        ${offen && !DARF.pruefen ? '<p class="mat-rr-zeile">Sperren dürfen Prüfer (Grund „Rückruf“); eine Prüfung nach dem Rückruf erledigt ihn ebenso.</p>' : ""}
      </div>`;
    }).join("");
  }

  // Wie es um die Mail steht: verschickt (mit Fehlschlägen), läuft noch, nicht bestätigt oder keine.
  function rrMailText(r) {
    if (r.mailed_at) {
      const n = r.mail_count + r.mail_failed;
      if (!n) return "Mail: keine Empfänger gefunden.";
      return `Mail an ${plural(n, "Empfänger", "Empfänger")} verschickt am ${esc(fmtZeit(r.mailed_at))}${r.mail_failed ? ` – ${r.mail_failed} davon ${r.mail_failed === 1 ? "ging" : "gingen"} nicht hinaus` : ""}.`;
    }
    if (!r.mail_count) return "Keine Mail verschickt.";
    const alt = Date.now() - Date.parse(r.created_at) > (r.unbestaetigt_minuten || 10) * 60000;
    return alt ? `Mail an ${plural(r.mail_count, "Empfänger", "Empfänger")}: Versand nicht bestätigt.`
      : `Mail an ${plural(r.mail_count, "Empfänger", "Empfänger")} wird verschickt …`;
  }

  function rueckrufKarte(r) {
    const serien = r.serien || [];
    const serienText = serien.length > 20
      ? `${serien.slice(0, 20).map(esc).join(", ")} <details class="mat-rr-serien"><summary>alle ${serien.length} zeigen</summary><p class="mat-text">${esc(serien.join("\n"))}</p></details>`
      : serien.map(esc).join(", ");
    const artikel = r.artikel || [];
    return `<article class="mat-rr-karte${r.aktiv ? "" : " beendet"}">
      <div class="mat-rr-kopf"><span class="mat-rr-marke">${r.aktiv ? "Rückruf" : "beendet"}</span><h3>${esc(r.title)}</h3></div>
      <p class="small muted">angelegt von ${esc(r.created_by_name || "–")} am ${esc(S.fmtDate(r.created_at))}${r.aktiv ? "" : ` · beendet von ${esc(r.closed_by_name || "–")} am ${esc(S.fmtDate(r.closed_at))}`}</p>
      ${r.description ? `<p class="mat-text">${esc(r.description)}</p>` : ""}
      ${r.url ? `<p>${rrLink(r.url, `Meldung des Herstellers: ${kurzLink(r.url)}`)}</p>` : ""}
      <p><strong>Betroffen:</strong> ${r.alle ? "alle Artikel dieses Produkts" : `${serien.length === 1 ? "Seriennummer" : "Seriennummern"} ${serienText}`}</p>
      ${r.aktiv ? `<p>${plural(r.betroffen, "Artikel", "Artikel")} im Bestand betroffen${r.betroffen ? ` · ${r.offen ? `<strong class="mat-warn">${r.offen} offen</strong>` : "alle erledigt"}` : ""}</p>
        ${artikel.length ? `<table class="list mat-tabelle mat-rr-artikel"><thead><tr><th>Inventar-Nr.</th><th>Seriennummer</th><th>Ablage</th><th>Zustand</th></tr></thead><tbody>
          ${artikel.map((x) => `<tr><td data-l="Inventar-Nr."><a class="mat-inv" href="/material/artikel/${x.id}"><strong>${esc(x.inventory_no)}</strong></a></td>
            <td data-l="Seriennummer">${esc(x.serial_no)}${x.serial_generated ? ' <span class="muted">(System)</span>' : ""}</td>
            <td data-l="Ablage">${esc(x.pfad || "")}</td><td data-l="Zustand">${rrZustand(x.zustand, x.grund)}</td></tr>`).join("")}</tbody></table>` : ""}
        ${(r.nicht_gefunden || []).length ? `<p class="small">Ohne Artikel im Bestand: ${r.nicht_gefunden.map(esc).join(", ")}</p>` : ""}` : ""}
      ${!r.aktiv && r.close_note ? `<p><strong>Vermerk:</strong> <span class="mat-text">${esc(r.close_note)}</span></p>` : ""}
      <p class="small muted">${rrMailText(r)}</p>
      ${r.aktiv && DARF.katalog ? `<div class="btn-row"><button class="btn secondary small" type="button" data-act="rr-beenden" data-id="${r.id}">Rückruf beenden</button></div>` : ""}
    </article>`;
  }

  // Abschnitt am Produkt: laufende Rückrufe offen, beendete eingeklappt darunter.
  function rueckrufAbschnitt(p) {
    const liste = p.rueckrufe || [];
    if (!liste.length) return "";
    const aktiv = liste.filter((r) => r.aktiv);
    const beendet = liste.filter((r) => !r.aktiv);
    return `<section class="section mat-rr-abschnitt"><h2>Rückrufe</h2>
      ${aktiv.map(rueckrufKarte).join("")}
      ${beendet.length ? `<details class="mat-rr-beendet"><summary>${plural(beendet.length, "beendeter Rückruf", "beendete Rückrufe")}</summary>${beendet.map(rueckrufKarte).join("")}</details>` : ""}
    </section>`;
  }

  function rueckrufDialog(p) {
    dialog(`<h2>Rückruf anlegen</h2>
      <p class="help">Für „${esc(produktName(p))}“. Der Hinweis steht danach am Produkt, an jedem betroffenen Artikel und auf der Übersicht. Gesperrt wird nichts automatisch – das tun Prüfer mit dem Grund „Rückruf“.</p>
      <label for="rr-titel">Titel</label><input type="text" id="rr-titel" maxlength="200" placeholder="kurz, wie in der Meldung des Herstellers">
      <label for="rr-text">Was ist betroffen, was ist zu tun?</label><textarea id="rr-text" rows="5" maxlength="4000" placeholder="Beschreibung und Empfehlung des Herstellers"></textarea>
      <label for="rr-url">Link zur Meldung des Herstellers</label><input type="text" id="rr-url" maxlength="500" placeholder="https://…" ${TASTATUR_ADRESSE}>
      <label for="rr-serien">Betroffene Seriennummern</label><textarea id="rr-serien" rows="4" ${TASTATUR_NUMMER} placeholder="eine je Zeile – leer lassen, wenn alle Artikel des Produkts betroffen sind"></textarea>
      <div class="help">Groß/klein und Leerzeichen am Rand spielen keine Rolle.</div>
      <label class="inline"><input type="checkbox" id="rr-mail" checked> Mail an Materialwarte und Prüfer</label>
      <div class="help">An alle Materialwarte und an die Prüfer, die einen betroffenen Artikel schon geprüft haben.</div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="rr-ok" type="button">Rückruf anlegen</button></div>`,
    (dlg, body) => {
      fokus($("#rr-titel", body));
      $("#rr-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          const r = await api(`${API}/produkte/${p.id}/rueckrufe`, { method: "POST", body: {
            title: $("#rr-titel", body).value, description: $("#rr-text", body).value, url: $("#rr-url", body).value,
            serials: $("#rr-serien", body).value, mail: $("#rr-mail", body).checked } });
          rueckrufErgebnis(r);
          zeigen(produkt);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  // Rückmeldung nach dem Anlegen: betroffene Artikel, Mail, Seriennummern ohne Artikel im Bestand.
  function rueckrufErgebnis(r) {
    const nf = r.nicht_gefunden || [];
    dialog(`<h2>Rückruf angelegt</h2>
      <p><strong>${plural(r.betroffen, "Artikel", "Artikel")}</strong> im Bestand betroffen${r.betroffen && r.offen < r.betroffen ? `, davon ${r.offen} offen` : ""}.</p>
      <p>${!r.mail ? "Keine Mail verschickt." : r.empfaenger ? `Mail an ${plural(r.empfaenger, "Empfänger", "Empfänger")} wird verschickt.` : "Für die Mail gab es keine Empfänger."}</p>
      ${nf.length ? `<p class="notice">Zu ${nf.length === 1 ? "dieser Seriennummer" : "diesen Seriennummern"} gibt es keinen Artikel im Bestand: ${nf.map(esc).join(", ")}</p>` : ""}
      <div class="dlg-actions"><button class="btn" data-close type="button" id="rr-fertig">OK</button></div>`,
    (d2, b2) => $("#rr-fertig", b2).focus());
  }

  function rueckrufBeenden(r) {
    if (!r) return;
    dialog(`<h2>Rückruf beenden</h2>
      <p>„${esc(r.title)}“</p>
      <p class="help">Danach steht kein Hinweis mehr an den Artikeln und auf der Übersicht; am Produkt bleibt der Rückruf mit deinem Vermerk sichtbar.${r.offen ? ` <strong>${plural(r.offen, "Artikel ist", "Artikel sind")} noch offen.</strong>` : ""}</p>
      <label for="rr-vermerk">Vermerk</label><textarea id="rr-vermerk" rows="3" maxlength="1000" placeholder="z. B. alle betroffenen Artikel geprüft"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="rr-beenden-ok" type="button">Beenden</button></div>`,
    (dlg, body) => {
      fokus($("#rr-vermerk", body));
      $("#rr-beenden-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          await api(`${API}/rueckrufe/${r.id}/beenden`, { method: "POST", body: { vermerk: $("#rr-vermerk", body).value } });
          dlg.close(); toast("Rückruf beendet"); zeigen(produkt);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  const ANSICHTEN = { dashboard, pruefungen, bestand, ordner, artikel, artikel_neu: artikelNeu, katalog, produkt, formular, suche,
                      meldungen, pruefung_neu: pruefungNeu, pruefung: pruefungAnsicht, durchgang: durchgangAnsicht };
  leisteLaden();
  zeigen(ANSICHTEN[ANSICHT] || dashboard);
})();
