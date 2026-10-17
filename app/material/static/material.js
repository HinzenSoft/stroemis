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

  const STATUS = { einsatzbereit: "einsatzbereit", bald_faellig: "bald fällig", ueberfaellig: "überfällig", neu: "neu",
                   gesperrt: "gesperrt", lebensdauer: "Lebensdauer erreicht", ausgesondert: "ausgesondert" };
  const PRUEFART = { eingang: "Eingangsprüfung", periodisch: "periodische Prüfung", ausserplanmaessig: "außerplanmäßige Prüfung",
                     reparatur: "Prüfung nach Reparatur", aussonderung: "Aussonderung" };
  const PRUEFART_KURZ = { eingang: "Eingangsprüfung", periodisch: "periodisch", ausserplanmaessig: "außerplanmäßig",
                          reparatur: "Reparatur", aussonderung: "Aussonderung" };
  const ERGEBNIS = { einsatzbereit: "einsatzbereit", instandsetzen: "instandsetzen", aussondern: "aussondern" };
  const BEFUND = { ok: "in Ordnung", mangel: "Mangel", nicht_zutreffend: "nicht zutreffend" };
  const ANHANGART = { externes_pruefformular: "externes Prüfformular", pruefbericht: "Prüfbericht", foto: "Foto", sonstiges: "Sonstiges" };
  const SPERRGRUND = { sturz: "Sturzbelastung", beschaedigung: "Beschädigung", verlust: "Verlust" };
  const AUSSONDERUNGSGRUND = { lebensdauer: "Lebensdauer erreicht", verlust: "Verlust", irreparabel: "irreparabel" };
  const ZUSTAND = { offen: "offen", in_pruefung: "in Prüfung", erledigt: "erledigt", ausgenommen: "ausgenommen" };
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
  };
  const AKTION = { angelegt: "angelegt", geaendert: "geändert", geloescht: "gelöscht", verschoben: "verschoben",
                   bild: "Bild geändert", foto: "Foto geändert", neue_version: "neue Version", zurueckgezogen: "zurückgezogen",
                   aktiviert: "aktiviert", deaktiviert: "deaktiviert", lebensende: "Lebensende nachgezogen", rollen: "Rollen",
                   begonnen: "Prüfung begonnen", abgeschlossen: "Prüfung abgeschlossen", verworfen: "Prüfung verworfen",
                   reservierung_freigegeben: "Reservierung freigegeben", geprueft: "geprüft", freigeprueft: "freigeprüft",
                   gesperrt: "gesperrt", ausgesondert: "ausgesondert", anhang: "Anhang", anhang_entfernt: "Anhang entfernt",
                   eroeffnet: "Durchgang eröffnet", ausgenommen: "ausgenommen", einbezogen: "wieder einbezogen",
                   geschlossen: "Durchgang abgeschlossen", faelligkeit: "Fälligkeit vorgezogen", umbenannt: "umbenannt",
                   eingepflegt: "eingepflegt", abgelehnt: "abgelehnt" };
  const ENTITAET = { item: "Artikel", product: "Produkt", document: "Dokument", form: "Formular", folder: "Ordner",
                     category: "Kategorie", user: "Konto", inspection: "Prüfung", round: "Durchgang", request: "Produktmeldung" };

  // „2026-12-04“ → „04.12.2026“, „2026-12“ → „12/2026“ – ohne Date-Objekt, damit keine Zeitzone den Tag verschiebt.
  const fmtTag = (d) => {
    const s = String(d || "");
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}.${m[2]}.${m[1]}`;
    m = s.match(/^(\d{4})-(\d{2})$/);
    return m ? `${m[2]}/${m[1]}` : s;
  };
  const fmtZeit = (iso) => S.fmtDate(iso, true);
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
    if ((feld === "pruefung" || feld === "aussonderung" || feld === "basis") && Number.isInteger(v)) return `<a href="/material/pruefung/${v}">Nr. ${v}</a>`;
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
    const gl = d.gliederungen;
    inhalt.innerHTML = `<div class="page-head"><h1>Material</h1>
        <div class="btn-row">${DARF.verwalten ? '<a class="btn secondary" href="/material/bestand">Bestand pflegen</a><a class="btn" href="/material/artikel/neu">+ Artikel</a>' : ""}</div></div>
      ${d.meldungen_offen ? `<p class="notice"><a href="/material/katalog/meldungen"><strong>${plural(d.meldungen_offen, "offene Produktmeldung", "offene Produktmeldungen")}</strong></a>
        – Materialwarte warten darauf, Artikel davon anzulegen.</p>` : ""}
      <div class="mat-kacheln">
        <div class="mat-kachel gesamt"><strong>${d.bestand}</strong><span>Artikel im Bestand</span></div>
        ${kachel("ueberfaellig", "überfällig")}${kachel("neu", "neu (Eingangsprüfung)")}${kachel("bald_faellig", `bald fällig (${d.schwelle_tage} Tage)`)}
        ${kachel("gesperrt", "gesperrt")}${kachel("lebensdauer", "Lebensdauer erreicht")}${kachel("einsatzbereit", "einsatzbereit")}
      </div>
      <div id="mat-runden"></div>
      <section class="section"><h2>Gliederungen</h2>
        ${gl.length ? `<table class="list mat-tabelle"><thead><tr><th>Gliederung</th><th>Bestand</th><th>überfällig</th><th>neu</th><th>bald fällig</th><th>gesperrt</th><th>Lebensdauer</th></tr></thead><tbody>
          ${gl.map((o) => `<tr><td data-l="Gliederung"><a href="/material/ordner/${o.id}">${esc(o.name)}</a>${demoMarke(o.demo)}</td>
            <td data-l="Bestand">${o.bestand}</td><td data-l="überfällig">${o.zaehlung.ueberfaellig || "–"}</td><td data-l="neu">${o.zaehlung.neu || "–"}</td>
            <td data-l="bald fällig">${o.zaehlung.bald_faellig || "–"}</td><td data-l="gesperrt">${o.zaehlung.gesperrt || "–"}</td>
            <td data-l="Lebensdauer">${o.zaehlung.lebensdauer || "–"}</td></tr>`).join("")}</tbody></table>`
          : leer(DARF.verwalten ? "Noch keine Gliederung – lege unter „Bestand“ die erste an." : "Noch keine Gliederung angelegt.")}
      </section>
      <section class="section"><h2>Als Nächstes zu prüfen</h2>
        ${d.naechste.length ? artikelTabelle(d.naechste, { pfad: true }) + (d.faellig_gesamt > d.naechste.length ? `<p><a href="/material/pruefungen">Alle ${d.faellig_gesamt} anzeigen →</a></p>` : "")
          : leer("Nichts fällig.")}
      </section>`;
    rundenKasten($("#mat-runden"), true);
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
          ${fortschritt(r.zaehlung)}</li>`).join("")}</ul>` : leer("Noch kein Prüfdurchgang.")}</section>`;
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
        <td data-l="Status">${statusMarke(a.status)}${a.entwurf ? `<div class="small muted">in Prüfung bei ${esc(a.entwurf.pruefer || "?")}</div>` : ""}</td>
        ${opts.pruefen ? `<td class="tabelle-aktionen">${pruefKnopf(a)}</td>` : ""}</tr>`).join("")}</tbody></table>`;
  }
  // „Prüfen“ in Listen: für Prüfer, solange niemand anderes den Artikel reserviert hat.
  function pruefKnopf(a, durchgangId) {
    if (!DARF.pruefen || a.lock_state === "ausgesondert") return "";
    if (a.entwurf && a.entwurf.pruefer_id !== DARF.uid) return "";
    const q = durchgangId ? `?durchgang=${durchgangId}` : "";
    return a.entwurf ? `<a class="btn small" href="/material/pruefung/${a.entwurf.id}">Weiter prüfen</a>`
      : `<a class="btn secondary small" href="/material/artikel/${a.id}/pruefung/neu${q}">Prüfen</a>`;
  }

  /* --- Fällige Prüfungen ------------------------------------------------------------------------ */
  async function pruefungen() {
    const params = new URLSearchParams(location.search);
    let filter = params.get("status") || "ueberfaellig,neu,bald_faellig";
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    const FILTER = [["ueberfaellig,neu,bald_faellig", "fällig, überfällig und neu"], ["ueberfaellig", "überfällig"],
                    ["neu", "neu (Eingangsprüfung)"], ["bald_faellig", "bald fällig"], ["lebensdauer", "Lebensdauer erreicht"],
                    ["gesperrt", "gesperrt"]];
    async function liste() {
      const q = sortParameter(new URLSearchParams({ status: filter, seite, pro_seite: 50 }), sort);
      if (DATEN.ordner) q.set("ordner", DATEN.ordner);
      const d = await api(`${API}/faellig?${q}`);
      $("#pr-liste").innerHTML = `<p class="help">Überfällig, neu (die Eingangsprüfung steht aus) oder in den nächsten ${d.schwelle_tage} Tagen fällig. Prüfen lässt sich jeder Artikel aber jederzeit – auch aus seiner Ansicht.</p>
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
          <td class="tabelle-aktionen">${x.eigen && DARF.pruefen ? `<a class="btn small" href="/material/pruefung/${x.id}">Weiter prüfen</a>` : `<a class="btn ghost small" href="/material/pruefung/${x.id}">Ansehen</a>`}
            ${!x.eigen && DARF.verwalten ? `<button class="btn ghost small" data-act="freigeben" data-id="${x.id}" data-wer="${esc(x.pruefer)}">Freigeben</button>` : ""}</td></tr>`).join("")}
        </tbody></table></section>` : "";
    }
    async function zeichnen() {
      inhalt.innerHTML = `<div class="page-head"><h1>Prüfungen</h1>
          <div class="btn-row">${DARF.verwalten || DARF.pruefen ? '<button class="btn secondary" data-act="runde">+ Prüfdurchgang</button>' : ""}</div></div>
        ${!DARF.pruefen ? '<p class="notice">Prüfen dürfen nur Prüfer mit hinterlegter Urkundennummer (Nutzerverwaltung → Häkchen „Prüfer“).</p>' : ""}
        <div id="pr-runden"></div><div id="pr-offen"></div>
        <section class="section"><h2>Zu prüfen</h2><div id="pr-liste"><p class="help">Wird geladen …</p></div></section>`;
      await Promise.all([zeigenIn(liste, "#pr-liste"), zeigenIn(offene, "#pr-offen"), rundenKasten($("#pr-runden"), false)]);
    }
    aktionen = {
      filter: (b) => { filter = b.dataset.f; seite = 1; history.replaceState(null, "", `?status=${filter}`); zeigenIn(liste, "#pr-liste"); },
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
        <div class="btn-row">${DARF.verwalten ? '<button class="btn" data-act="gliederung">+ Gliederung</button>' : ""}</div></div>
      <p class="help">Oben stehen die Gliederungen, darunter frei verschachtelt Standorte, Fahrzeuge, Sets. Jede Gliederung hat die
        Systemordner „Gesperrt“ und „Ausgesondert“ – dorthin kommen Artikel nur durch eine Sperre oder Aussonderung.
        Die Zahl hinter einem Ordner ist sein Bestand; farbig: überfällig, Lebensdauer erreicht, gesperrt, bald fällig.</p>
      ${d.ordner.length ? baumHtml(d.ordner) : leer("Noch kein Ordner angelegt.")}`;
    aktionen = { gliederung: () => ordnerDialog({ kind: "gliederung" }, null) };
  }

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
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="od-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
    (dlg, body) => {
      fokus($("#od-name", body));
      $("#od-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (knopf.disabled) return;
        knopf.disabled = true;
        const daten = { name: $("#od-name", body).value, kind: oben ? "gliederung" : $("#od-kind", body).value,
                        interval_months: $("#od-int", body).value || null, description: $("#od-desc", body).value };
        if (!neu && o.kind === "gliederung") daten.kind = "gliederung";
        try {
          const r = neu ? await api(`${API}/ordner`, { method: "POST", body: Object.assign(daten, { parent_id: parentId || null }) })
                        : await api(`${API}/ordner/${o.id}`, { method: "PUT", body: daten });
          dlg.close();
          location.href = `/material/ordner/${r.ordner.id}`;
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
            <a class="btn small" href="/material/artikel/neu?ordner=${d.id}">+ Artikel</a>
            <button class="btn ghost small" data-act="bearbeiten">Bearbeiten</button><button class="btn ghost small" data-act="foto">Foto</button>
            <button class="btn ghost small" data-act="verschieben">Verschieben</button><button class="btn ghost small" data-act="loeschen">Löschen</button>` : ""}
            ${!system && (DARF.verwalten || DARF.pruefen) ? '<button class="btn ghost small" data-act="runde">+ Prüfdurchgang</button>' : ""}</div></div>
        ${system ? `<p class="notice">${d.system_kind === "gesperrt" ? "Hierher verschiebt eine Sperre die Artikel der Gliederung. Zurück in ihren Herkunftsordner bringt sie nur eine Freiprüfung." : "Ausgesonderte Artikel bleiben hier mit ihrem vollen Lebenslauf sichtbar, zählen aber nirgends mehr als Bestand und lassen sich nicht zurückholen."}</p>` : ""}
        <div class="mat-ordnerkopf">${d.foto ? `<img class="mat-ordnerfoto" src="${esc(d.vorschau)}" alt="">` : ""}
          <div>${d.description ? `<p class="mat-text">${esc(d.description)}</p>` : ""}
          ${d.interval_months ? `<p class="small">Prüfintervall hier: höchstens ${d.interval_months} Monate.</p>` : ""}
          <p class="small">${system ? plural(Object.values(z).reduce((a, b) => a + b, 0), "Artikel", "Artikel") : `Bestand im ganzen Zweig: <strong>${d.bestand}</strong> ${zahlen(z)}`}</p></div></div>
        ${d.unterordner.length ? `<section class="section"><h2>Unterordner</h2>${unterordnerHtml(d.unterordner)}</section>` : ""}
        <section class="section"><h2>Artikel in diesem Ordner</h2>
          <div class="c-tabs mat-filter">${["", "ueberfaellig", "neu", "bald_faellig", "gesperrt", "lebensdauer", "einsatzbereit"].map((s) => `<button type="button" data-act="filter" data-f="${s}" class="${s === filter ? "sel" : ""}">${s ? esc(STATUS[s]) : "alle"}${s && d.direkt && d.direkt[s] ? ` (${d.direkt[s]})` : ""}</button>`).join("")}</div>
          ${d.artikel.length ? artikelTabelle(d.artikel, { auswahl: darfPflegen, pruefen: DARF.pruefen && d.system_kind !== "ausgesondert", sort }) : leer(filter ? "Keine Artikel mit diesem Status." : "Hier liegen keine Artikel.")}
          ${seitenleiste(d.artikel_gesamt, seite, d.pro_seite)}
          ${darfPflegen ? '<div class="mat-sammel" id="mat-sammel" hidden><span id="mat-sammel-n"></span><button class="btn small" data-act="sammel-verschieben">Verschieben nach …</button></div>' : ""}
        </section>
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
        foto: () => fotoDialog(`${API}/ordner/${d.id}/foto`, !!d.foto, zeichnen),
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

  function fotoDialog(url, hatFoto, danach) {
    dialog(`<h2>Foto</h2><p class="help">JPEG, PNG, WebP oder HEIC vom Telefon; Web- und Vorschaufassung entstehen beim Hochladen.</p>
      <input type="file" id="fd-datei" accept="image/*">
      <div class="dlg-actions">${hatFoto ? '<button class="btn danger" id="fd-weg" type="button">Foto entfernen</button>' : ""}
        <button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="fd-ok" type="button">Hochladen</button></div>`,
    (dlg, body) => {
      $("#fd-ok", body).onclick = async (ev) => {
        const f = $("#fd-datei", body).files[0];
        if (!f) { toast("Bitte ein Foto wählen.", true); return; }
        const fd = new FormData(); fd.append("file", f);
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try { await api(url, { method: "POST", body: fd }); dlg.close(); toast("Foto gespeichert"); await danach(); }
        catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
      const weg = $("#fd-weg", body);
      if (weg) weg.onclick = async () => {
        try { await api(url, { method: "DELETE" }); dlg.close(); toast("Foto entfernt"); await danach(); } catch (e) { toast(e.message, true); }
      };
    });
  }

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
      <div class="mat-pfad">${bc}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? `<a href="${esc(p.original || p.bild)}" target="_blank" rel="noopener"><img class="mat-produktbild" src="${esc(p.bild)}" alt="Produktbild ${esc(produktName(p))}"></a>` : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel">
          <h1>${esc(a.inventory_no)} ${statusMarke(a.status, true)}</h1>
          <p class="mat-produktzeile"><a href="/material/katalog/produkt/${p.id}">${esc(produktName(p))}</a>${p.article_no ? ` · Art.-Nr. ${esc(p.article_no)}` : ""}</p>
          <p>Seriennummer <strong>${esc(a.serial_no)}</strong>${a.serial_generated ? ' <span class="badge grey" title="Der Hersteller vergibt keine Seriennummer – diese Nummer bitte dauerhaft am Artikel anbringen.">vom System vergeben</span>' : ""}</p>
          <div class="btn-row mat-pruefknoepfe">${!aus && DARF.pruefen && !fremderEntwurf ? `<button class="btn" data-act="pruefen">${eigenerEntwurf ? "Prüfung fortsetzen" : a.status === "neu" ? "Eingangsprüfung starten" : "Prüfung starten"}</button>` : ""}
            ${frei && DARF.pruefen && !a.entwurf ? '<button class="btn secondary small" data-act="sperren">Sperren</button>' : ""}
            ${gesperrt && DARF.verwalten && !a.entwurf ? '<button class="btn secondary small" data-act="aussondern">Aussondern</button>' : ""}</div>
          ${a.entwurf ? `<p class="small">In Prüfung bei <strong>${esc(a.entwurf.pruefer)}</strong> seit ${esc(fmtZeit(a.entwurf.seit))}
            ${fremderEntwurf ? ` · <a href="/material/pruefung/${a.entwurf.id}">ansehen</a>` : ""}
            ${fremderEntwurf && DARF.verwalten ? ' · <button class="lnk" type="button" data-act="freigeben">Reservierung freigeben</button>' : ""}</p>` : ""}
          ${!aus && !DARF.pruefen && (DARF.verwalten || DARF.lesen) ? '<p class="small muted">Prüfen dürfen Prüfer mit hinterlegter Urkundennummer.</p>' : ""}
          ${a.durchgang ? `<p class="small">Steht im Prüfdurchgang <a href="/material/durchgang/${a.durchgang.id}">${esc(a.durchgang.titel)}</a>.</p>` : ""}
          <div class="btn-row">${darfPflegen ? `<button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>${frei ? '<button class="btn ghost small" data-act="verschieben">Verschieben</button>' : ""}${a.darf_loeschen ? '<button class="btn ghost small" data-act="loeschen">Löschen</button>' : ""}` : ""}</div>
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
        <section class="section"><h2>QR-Etikett</h2>
          <p class="help">Diese Adresse steht im QR-Code; derselbe Link lässt sich auf einen NFC- oder RFID-Tag schreiben. Die Kamera-App öffnet damit nach der Anmeldung diesen Artikel. Etikettenbögen kommen mit Lieferung 4.</p>
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
        catch (e) { feld.select(); document.execCommand && document.execCommand("copy"); toast("Adresse markiert – mit Strg+C kopieren"); }
      },
      bearbeiten: () => artikelDialog(a),
      pruefen: () => { location.href = eigenerEntwurf ? `/material/pruefung/${a.entwurf.id}` : `/material/artikel/${a.id}/pruefung/neu`; },
      sperren: () => sperrDialog(a),
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

  /* Prüfungen eines Artikels, neueste zuerst – der Prüfteil des Lebenslaufs. */
  function pruefListe(liste) {
    if (!liste || !liste.length) return leer("Noch keine Prüfung.");
    return `<table class="list mat-tabelle mat-pruefliste"><thead><tr><th>Datum</th><th>Art</th><th>Ergebnis</th><th>Prüfer</th><th>Nächste Prüfung</th></tr></thead><tbody>
      ${liste.map((x) => `<tr class="${x.entwurf ? "mat-entwurf" : ""}"><td data-l="Datum"><a href="/material/pruefung/${x.id}">${x.entwurf ? "Entwurf" : esc(fmtTag(x.datum))}</a></td>
        <td data-l="Art">${esc(PRUEFART_KURZ[x.art] || x.art)}</td>
        <td data-l="Ergebnis">${x.entwurf ? '<span class="muted">in Prüfung</span>' : ergebnisMarke(x.ergebnis)}${x.grund ? `<div class="small muted">${esc(x.grund)}</div>` : ""}</td>
        <td data-l="Prüfer">${esc(x.pruefer || "")}${x.urkunde ? ` <span class="muted small">(${esc(x.urkunde)})</span>` : ""}</td>
        <td data-l="Nächste Prüfung">${x.naechste ? esc(fmtTag(x.naechste)) : '<span class="muted">–</span>'}</td></tr>`).join("")}</tbody></table>`;
  }
  const ergebnisMarke = (e) => (e ? `<span class="mat-ergebnis-marke e-${esc(e)}">${esc(ERGEBNIS[e] || e)}</span>` : "");

  function sperrDialog(a) {
    dialog(`<h2>${esc(a.inventory_no)} sperren</h2>
      <p class="help">Sperren ohne Prüfung – nach Sturzbelastung, Beschädigung oder bei Verlust. Der Artikel wandert nach „Gesperrt“ seiner Gliederung; zurück bringt ihn nur eine Freiprüfung mit „einsatzbereit“.</p>
      <label for="sd-grund">Grund</label><select id="sd-grund">${Object.entries(SPERRGRUND).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select>
      <label for="sd-text">Was ist passiert?</label><input type="text" id="sd-text" maxlength="300" placeholder="z. B. Sturz in die Rettungskette, Schnitt am Band">
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

  function aussonderDialog(a) {
    const heute = new Date();
    const tag = `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, "0")}-${String(heute.getDate()).padStart(2, "0")}`;
    dialog(`<h2>${esc(a.inventory_no)} aussondern</h2>
      <p class="help">Die Aussonderung ist endgültig: Der Artikel wandert nach „Ausgesondert“, bleibt dort mit seinem Lebenslauf sichtbar und zählt nirgends mehr als Bestand.</p>
      <div class="field-row"><div><label for="au-grund">Grund</label><select id="au-grund">${Object.entries(AUSSONDERUNGSGRUND).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
        <div><label for="au-datum">Datum</label><input type="date" id="au-datum" value="${tag}" max="${tag}"></div></div>
      <label for="au-bem">Bemerkung</label><textarea id="au-bem" rows="3" maxlength="2000"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="au-ok" type="button">Aussondern</button></div>`,
    (dlg, body) => {
      $("#au-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          await api(`${API}/artikel/${a.id}/aussondern`, { method: "POST", body: { grund: $("#au-grund", body).value, datum: $("#au-datum", body).value, bemerkung: $("#au-bem", body).value } });
          dlg.close(); toast("Ausgesondert"); zeigen(artikel);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  function artikelDialog(a) {
    const textil = a.produkt.material_kind === "textil";
    dialog(`<h2>Artikel ${esc(a.inventory_no)} bearbeiten</h2>
      <label for="ad-sn">Seriennummer des Herstellers</label><input type="text" id="ad-sn" value="${a.serial_generated ? "" : esc(a.serial_no)}" placeholder="${a.serial_generated ? esc(a.serial_no) + " (vom System)" : ""}" maxlength="80">
      <div class="help">Leer lassen behält die Nummer. Eine echte Herstellernummer ersetzt die vom System vergebene.</div>
      <div class="field-row"><div><label for="ad-herst">Herstellung (Monat${textil ? ", Pflicht" : ""})</label><input type="month" id="ad-herst" value="${esc((a.manufactured_on || "").slice(0, 7))}"></div>
        <div><label for="ad-kauf">Kauf</label><input type="date" id="ad-kauf" value="${esc(a.purchased_on || "")}"></div></div>
      <div class="field-row"><div><label for="ad-erst">Erstgebrauch</label><input type="date" id="ad-erst" value="${esc(a.first_use_on || "")}"></div>
        <div><label for="ad-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="ad-int" min="1" max="120" value="${a.interval_months || ""}" placeholder="vom Produkt/Ordner"></div></div>
      <div class="field-row"><div ${a.status === "neu" ? "hidden" : ""}><label for="ad-due">Nächste Prüfung</label><input type="date" id="ad-due" value="${esc(a.next_due_on || "")}" max="${esc(a.next_due_on || "")}">
          <div class="help">Nur vorziehen – später setzt sie eine Prüfung.</div></div>
        ${textil ? `<div><label for="ad-ende">Lebensende</label><input type="date" id="ad-ende" value="${esc(a.retire_by || "")}"><div class="help">Nur vorziehen. Leer lassen behält das Lebensende.</div></div>` : "<div></div>"}</div>
      <label for="ad-notes">Bemerkung</label><textarea id="ad-notes" rows="3" maxlength="4000">${esc(a.notes || "")}</textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ad-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
      $("#ad-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        const herst = $("#ad-herst", body).value;
        // Ein Tagesdatum bleibt erhalten, wenn der Monat derselbe ist – der Monatswähler kennt keinen Tag.
        const daten = { stand: a.stand, serial_no: $("#ad-sn", body).value, purchased_on: $("#ad-kauf", body).value || null,
                        manufactured_on: herst && a.manufactured_on && a.manufactured_on.slice(0, 7) === herst ? a.manufactured_on : (herst || null),
                        first_use_on: $("#ad-erst", body).value || null, interval_months: $("#ad-int", body).value || null,
                        next_due_on: $("#ad-due", body).value || null, notes: $("#ad-notes", body).value };
        if (textil) daten.retire_by = $("#ad-ende", body).value || null;
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
        <div class="mat-produktwahl"><input type="search" id="an-q" placeholder="Hersteller, Modell, Artikelnummer …" autocomplete="off">
          <div id="an-treffer" class="mat-treffer"></div></div>
        <div id="an-produkt" class="mat-gewaehlt" hidden></div>
        <p class="help">Fehlt das Produkt im Katalog? <button type="button" class="lnk" data-act="melden">Fehlendes Produkt melden</button>
          – ein Produktkatalogpfleger nimmt es auf, du bekommst Bescheid.</p>
        <label for="an-ordner">Ordner</label><select id="an-ordner">${optionen(0, 0)}</select>
        <label for="an-sn">Seriennummer des Herstellers</label><input type="text" id="an-sn" maxlength="80" placeholder="leer lassen, wenn der Hersteller keine vergibt">
        <div class="help">Ohne Herstellernummer vergibt das System eine eindeutige (STR-…), die dann am Artikel angebracht wird. Die Inventarnummer vergibt immer das System.</div>
        <div class="field-row"><div><label for="an-herst">Herstellung (Monat)</label><input type="month" id="an-herst"></div>
          <div><label for="an-kauf">Kauf</label><input type="date" id="an-kauf"></div></div>
        <div class="field-row"><div><label for="an-erst">Erstgebrauch</label><input type="date" id="an-erst"></div>
          <div><label for="an-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="an-int" min="1" max="120" placeholder="vom Produkt/Ordner"></div></div>
        <div class="field-row"><div id="an-ende-feld" hidden><label for="an-ende">Lebensende</label><input type="date" id="an-ende"><div class="help" id="an-ende-hilfe"></div></div>
          <div><p class="help" id="an-due-hilfe"></p></div></div>
        <p class="notice">Neu angelegte Artikel stehen auf <strong>neu</strong>, bis ein Prüfer die Eingangsprüfung gemacht hat – erst sie gibt sie frei und setzt die erste Fälligkeit.</p>
        <label for="an-notes">Bemerkung</label><textarea id="an-notes" rows="2" maxlength="4000"></textarea>
        <div class="btn-row mat-knoepfe"><button class="btn" data-act="anlegen">Anlegen</button>
          <button class="btn secondary" data-act="anlegen-weiter" title="Produkt und Ordner bleiben für den nächsten Artikel stehen">Anlegen und nächsten</button></div>
      </div>
      <div id="an-meldungen"></div>`;
    let vorschlagLos = null;
    async function vorschlag() {
      if (!produkt) return;
      const q = new URLSearchParams({ product_id: produkt.id, folder_id: $("#an-ordner").value });
      for (const [k, sel] of [["manufactured_on", "#an-herst"], ["purchased_on", "#an-kauf"], ["first_use_on", "#an-erst"], ["interval_months", "#an-int"]]) {
        if ($(sel).value) q.set(k, $(sel).value);
      }
      try {
        const v = (await api(`${API}/artikel/vorschlag?${q}`)).vorschlag;
        $("#an-due-hilfe").textContent = v.intervall.monate ? `Prüfintervall ${v.intervall.monate} Monate (${v.intervall.quelle}).` : "Kein Prüfintervall – am Produkt oder in der Kategorie eintragen.";
        const textil = v.material_kind === "textil";
        $("#an-ende-feld").hidden = !textil;
        if (textil) {
          const ende = $("#an-ende");
          if (!ende.dataset.selbst) ende.value = v.retire_by || "";
          ende.max = v.retire_by || "";
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
      $("#an-treffer").innerHTML = "";
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
        if (!q) { $("#an-treffer").innerHTML = ""; return; }
        const d = await api(`${API}/produkte?q=${encodeURIComponent(q)}&pro_seite=8`);
        $("#an-treffer").innerHTML = d.produkte.length ? d.produkte.map((p, i) => `<button type="button" class="mat-treffer-zeile" data-i="${i}">
            ${p.vorschau ? `<img class="mat-mini" src="${esc(p.vorschau)}" alt="">` : ""}<strong>${esc(produktName(p))}</strong> <span class="muted">${esc(p.article_no || "")} · ${esc(p.category_name || "")}</span>${demoMarke(p.demo)}</button>`).join("")
          + (d.gesamt > d.produkte.length ? `<p class="help">${d.gesamt} Treffer – genauer suchen.</p>` : "")
          : '<p class="help">Kein Produkt gefunden. <button type="button" class="lnk" data-act="melden">Als fehlendes Produkt melden</button></p>';
        $$(".mat-treffer-zeile", $("#an-treffer")).forEach((b) => { b.onclick = () => waehlen(d.produkte[+b.dataset.i]); });
      }, 200);
    });
    if (DATEN.produkt) {
      try { waehlen((await api(`${API}/produkte/${DATEN.produkt}`)).produkt); } catch (e) { /* Produkt gibt es nicht mehr */ }
    }
    async function anlegen(weiter) {
      if (!produkt) { toast("Bitte zuerst ein Produkt wählen.", true); return; }
      const daten = { product_id: produkt.id, folder_id: +$("#an-ordner").value, serial_no: $("#an-sn").value,
                      manufactured_on: $("#an-herst").value || null, purchased_on: $("#an-kauf").value || null,
                      first_use_on: $("#an-erst").value || null, interval_months: $("#an-int").value || null,
                      notes: $("#an-notes").value };
      if (!$("#an-ende-feld").hidden) daten.retire_by = $("#an-ende").value || null;
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
          <div class="btn-row">${DARF.katalog ? `<a class="btn secondary mat-mit-zahl" href="/material/katalog/meldungen">Meldungen<span class="mat-meldezahl" id="kat-meldungen" hidden></span></a>
            <button class="btn secondary" data-act="kat-neu">+ Kategorie</button><button class="btn" data-act="produkt-neu">+ Produkt</button>` : ""}</div></div>
        ${k ? `<div class="mat-katkopf">
            <div class="mat-pfad"><a href="/material/katalog" data-act="kategorie" data-id="">alle Kategorien</a>${pfad.slice(0, -1).map((x) => ` / <a href="/material/katalog?kategorie=${x.id}" data-act="kategorie" data-id="${x.id}">${esc(x.name)}</a>`).join("")}</div>
            <h2>${esc(k.name)} ${demoMarke(k.demo)}</h2>
            <p class="small">${angaben}${!k.aktives_formular ? ' · <span class="muted">kein aktives generisches Prüfformular</span>'
              : DARF.katalog ? "" : ` · <a href="/material/katalog/formular/${k.aktives_formular}">generisches Prüfformular</a>`}</p>
            ${DARF.katalog ? `<div class="btn-row"><button class="btn ghost small" data-act="kat-bearbeiten">Kategorie bearbeiten</button>
              <button class="btn ghost small" data-act="kat-formular">Generisches Formular</button><button class="btn ghost small" data-act="kat-loeschen">Löschen</button></div>` : ""}
            <div class="mat-katdoks"><h3 class="mat-unter">Dokumente für alle Produkte dieser Kategorie</h3>
              <p class="help">Pflegehinweise, allgemeine Anleitungen … – sie gelten für jedes Produkt hier und in den Unterkategorien und stehen dort bei den Herstellerdokumenten.</p>
              <div id="kat-doks"><p class="help">Wird geladen …</p></div>
              ${DARF.katalog ? '<button class="btn secondary small" data-act="dok-neu">+ Dokument</button>' : ""}</div></div>`
          : (kats.length ? "" : leer(DARF.katalog ? "Noch keine Kategorien – mit „+ Kategorie“ anlegen." : "Noch keine Kategorien."))}
        <div class="mat-suchzeile"><input type="search" id="kat-q" placeholder="Produkte suchen: Hersteller, Modell, Artikelnummer, Norm" value="${esc(q)}" autocomplete="off"></div>
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
      ...dokAktionen(() => katDocs, () => `${API}/kategorien/${kategorie}/dokumente`, () => zeigenIn(katDoks, "#kat-doks")),
    };
    katalogWahl = (id) => {
      kategorie = id;
      history.replaceState(null, "", kategorie ? `?kategorie=${kategorie}` : location.pathname);
      zeichnen();
    };
    zeichnen();
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
      <label for="kd-norm">Norm</label><input type="text" id="kd-norm" value="${esc(k.norm || "")}" maxlength="200" placeholder="z. B. EN 361">
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

  async function produktDialog(p) {
    const kats = await kategorienLaden();
    const neu = !p.id;
    const kat = (id) => kats.find((k) => k.id === +id) || {};
    dialog(`<h2>${p.meldung ? "Produkt aus Meldung anlegen" : neu ? "Produkt anlegen" : "Produkt bearbeiten"}</h2>
      ${p.meldung ? meldeKasten(p.meldung) : ""}
      <label for="pd-kat">Kategorie</label><select id="pd-kat"><option value="">– bitte wählen –</option>${kategorieOptionen(kats, p.category_id)}</select>
      <div class="field-row"><div><label for="pd-her">Hersteller</label><input type="text" id="pd-her" value="${esc(p.manufacturer || "")}" maxlength="120"></div>
        <div><label for="pd-mod">Modell</label><input type="text" id="pd-mod" value="${esc(p.model || "")}" maxlength="160"></div></div>
      <div class="field-row"><div><label for="pd-art">Artikelnummer des Herstellers</label><input type="text" id="pd-art" value="${esc(p.article_no || "")}" maxlength="80"></div>
        <div><label for="pd-norm">Norm</label><input type="text" id="pd-norm" value="${esc(p.norm || "")}" maxlength="200"></div></div>
      <div class="field-row"><div><label for="pd-mk">Materialart</label><select id="pd-mk">${Object.entries(MATERIALART).map(([w, t]) => `<option value="${w}" ${p.material_kind === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
        <div><label for="pd-int">Prüfintervall (Monate)</label><input type="number" id="pd-int" min="1" max="120" value="${p.interval_months || ""}"><div class="help" id="pd-int-hilfe"></div></div></div>
      <div class="field-row"><div><label for="pd-ld">Lebensdauer (Jahre)</label><input type="number" id="pd-ld" min="1" max="50" value="${p.lifetime_years || ""}"><div class="help" id="pd-ld-hilfe"></div></div>
        <div><label for="pd-lq">Fundstelle der Lebensdauer</label><input type="text" id="pd-lq" value="${esc(p.lifetime_source || "")}" maxlength="300" placeholder="z. B. Gebrauchsanleitung, Kap. 9"></div></div>
      <label for="pd-desc">Beschreibung</label><textarea id="pd-desc" rows="3" maxlength="4000">${esc(p.description || "")}</textarea>
      <label for="pd-bild">Produktbild</label>
      <div class="mat-bildfeld">${p.vorschau ? `<img src="${esc(p.vorschau)}" alt="Bisheriges Produktbild">` : ""}
        <div><input type="file" id="pd-bild" accept="image/*">
          ${p.bild ? '<label class="inline"><input type="checkbox" id="pd-bild-weg"> Bild entfernen</label>' : ""}
          <div class="help">${p.bild ? "Ein neues Bild ersetzt das bisherige. " : ""}JPEG, PNG, WebP oder HEIC vom Telefon.</div></div></div>
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
      if (neu && p.category_id) katSel.dispatchEvent(new Event("change"));
      hilfen();
      // Erst die Angaben, dann das Bild. Scheitert nur das Bild, kennt der Dialog das Produkt schon: Ein zweiter
      // Klick speichert die Angaben erneut und lädt das Bild nach, statt das Produkt doppelt anzulegen.
      let pid = p.id || null;
      $("#pd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const daten = { category_id: katSel.value ? +katSel.value : null, manufacturer: $("#pd-her", body).value, model: $("#pd-mod", body).value,
                        article_no: $("#pd-art", body).value, norm: $("#pd-norm", body).value, material_kind: mk.value,
                        interval_months: $("#pd-int", body).value || null, lifetime_years: ld.value || null,
                        lifetime_source: $("#pd-lq", body).value, description: $("#pd-desc", body).value };
        const bild = $("#pd-bild", body).files[0];
        const weg = $("#pd-bild-weg", body);
        knopf.disabled = true;
        try {
          // Aus einer Meldung: Produkt anlegen und Meldung erledigen in einem Zug (der Melder bekommt Bescheid).
          const r = pid ? await api(`${API}/produkte/${pid}`, { method: "PUT", body: daten })
            : p.meldung ? await api(`${API}/meldungen/${p.meldung.id}/produkt`, { method: "POST", body: Object.assign(daten, { antwort: $("#pd-antwort", body).value }) })
            : await api(`${API}/produkte`, { method: "POST", body: daten });
          pid = r.produkt.id;
          if (bild) {
            const fd = new FormData();
            fd.append("file", bild);
            await api(`${API}/produkte/${pid}/bild`, { method: "POST", body: fd });
          } else if (weg && weg.checked) {
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
      <td>${k ? `<div class="btn-row"><button class="btn ghost small" data-act="dok-name" data-id="${d.id}">Umbenennen</button>${!d.abgeloest_durch && !d.withdrawn_on ? `<button class="btn ghost small" data-act="dok-version" data-id="${d.id}">Neue Version</button><button class="btn ghost small" data-act="dok-zurueck" data-id="${d.id}">Zurückziehen</button>` : ""}</div>` : ""}</td></tr>`;
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
        ${p.bild ? `<a href="${esc(p.original || p.bild)}" target="_blank" rel="noopener"><img class="mat-produktbild" src="${esc(p.bild)}" alt=""></a>` : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel"><h1>${esc(produktName(p))} ${demoMarke(p.demo)}</h1>
          ${DARF.verwalten ? `<div class="btn-row"><a class="btn small" href="/material/artikel/neu?produkt=${p.id}">+ Artikel dieses Produkts</a></div>` : ""}
          ${k ? `<div class="btn-row"><button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>${p.artikel_gesamt ? "" : '<button class="btn secondary small" data-act="loeschen">Löschen</button>'}</div>` : ""}</div>
      </div>
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
      loeschen: async () => {
        if (!(await confirm(`Produkt „${produktName(p)}“ aus dem Katalog löschen?`, "Löschen"))) return;
        try { await api(`${API}/produkte/${p.id}`, { method: "DELETE" }); location.href = "/material/katalog"; } catch (e) { toast(e.message, true); }
      },
      formular: () => formularFuer({ produkt_id: p.id }),
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
            ${e.datei ? "" : `<input type="text" class="dm-url" maxlength="500" placeholder="https://…" value="${esc(e.url || "")}" aria-label="Adresse">`}
            <input type="text" class="dm-titel" maxlength="200" value="${esc(e.titel)}" placeholder="${e.datei ? "Titel" : "Titel (leer = Adresse)"}" aria-label="Titel">
            <select class="dm-art" aria-label="Art">${artWahl(e.art)}</select>
            <input type="text" class="dm-ver" maxlength="40" value="${esc(e.version)}" placeholder="Version" aria-label="Versionsstand">
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
      // Abgelegt wird überall im Dialog – nie soll der Browser die Datei stattdessen selbst öffnen.
      body.addEventListener("dragover", (ev) => { ev.preventDefault(); ablage.classList.add("ueber"); });
      body.addEventListener("dragleave", (ev) => { if (!body.contains(ev.relatedTarget)) ablage.classList.remove("ueber"); });
      body.addEventListener("drop", (ev) => {
        ev.preventDefault();
        ablage.classList.remove("ueber");
        if (ev.dataTransfer && ev.dataTransfer.files.length) hinzufuegen(Array.from(ev.dataTransfer.files));
      });
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
      <div class="field-row"><div><label for="dd-ver">Versionsstand</label><input type="text" id="dd-ver" maxlength="40" placeholder="z. B. 03/2024"></div>
        <div><label for="dd-ab">Gültig ab</label><input type="date" id="dd-ab"></div></div>
      <label for="dd-datei">Datei (PDF oder Bild)</label><input type="file" id="dd-datei" accept="application/pdf,image/jpeg,image/png,image/webp">
      <label for="dd-url">… oder Adresse beim Hersteller</label><input type="text" id="dd-url" maxlength="500" placeholder="https://…">
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="dd-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
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
          <div class="btn-row"><button class="btn ghost small" data-act="hoch" data-i="${i}" aria-label="nach oben">↑</button><button class="btn ghost small" data-act="runter" data-i="${i}" aria-label="nach unten">↓</button><button class="btn ghost small" data-act="weg" data-i="${i}" aria-label="entfernen">✕</button></div></td></tr>`;
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
          <div class="btn-row">${DARF.katalog ? `${f.aktiv ? '<button class="btn ghost small" data-act="deaktivieren">Deaktivieren</button>' : '<button class="btn small" data-act="aktivieren">Aktivieren</button>'}
            <button class="btn secondary small" data-act="neue-version">Neue Version</button>${!f.aktiv && !f.benutzt ? '<button class="btn ghost small" data-act="loeschen">Löschen</button>' : ""}` : ""}</div></div>
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
    let hinweis = "";
    if (a.lock_state === "ausgesondert") hinweis = "Ein ausgesonderter Artikel wird nicht mehr geprüft.";
    else if (!DARF.pruefen) hinweis = "Prüfen dürfen nur Prüfer mit hinterlegter Urkundennummer (Nutzerverwaltung → Häkchen „Prüfer“).";
    else if (a.entwurf) hinweis = `In Prüfung bei ${a.entwurf.pruefer} seit ${fmtZeit(a.entwurf.seit)}.${DARF.verwalten ? " Eine liegen gebliebene Reservierung gibst du in der Artikelansicht frei." : " Eine liegen gebliebene Reservierung gibt der Materialwart frei."}`;
    else if (!a.formular) hinweis = "Für dieses Produkt gibt es kein aktives Prüfformular – weder am Produkt noch in seiner Kategorie. Der Produktkatalogpfleger legt es im Katalog an.";
    const ld = a.lebensdauer && a.lebensdauer.festgeschrieben ? { ende: a.lebensdauer.ende, rest_tage: a.lebensdauer.rest_tage, erreicht: a.lebensdauer.rest_tage <= 0 } : null;
    inhalt.innerHTML = `${p.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen. Dieses Produkt stammt aus den Demodaten.</p>' : ""}
      ${artikelPfad(a)}
      <div class="page-head"><h1>Prüfung ${esc(a.inventory_no)} ${statusMarke(a.status, true)}</h1></div>
      <div class="mat-formular">
        <p class="mat-produktzeile"><strong>${esc(produktName(p))}</strong>${p.article_no ? ` · Art.-Nr. ${esc(p.article_no)}` : ""} · Seriennummer ${esc(a.serial_no)}</p>
        ${a.lock_state !== "frei" && a.lock_state !== "ausgesondert" ? `<p class="mat-banner s-gesperrt">GESPERRT${a.lock_reason ? ` – ${esc(a.lock_reason)}` : ""}. Mit „einsatzbereit“ ist diese Prüfung die Freiprüfung.</p>` : ""}
        ${lebensdauerHinweis(ld)}
        ${a.formular ? `<p>Formular: ${esc(a.formular.title || "ohne Titel")} · Version ${a.formular.version} <span class="muted">(${esc(a.formular.quelle)}, ${plural(a.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span></p>` : ""}
        ${a.durchgang ? `<p>Im Prüfdurchgang <a href="/material/durchgang/${a.durchgang.id}">${esc(a.durchgang.titel)}</a> – die Prüfung zählt dort.</p>` : ""}
        ${hinweis ? `<p class="notice">${esc(hinweis)}</p><p><a class="btn secondary" href="/material/artikel/${a.id}">Zum Artikel</a></p>` : `
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
    const merken = (p) => { laufend = laufend.then(() => p, () => p); return p; };
    const bearbeitbar = () => pr.entwurf && pr.eigen && DARF.pruefen;
    const punkt = (rid) => pr.punkte.find((x) => x.id === rid);

    function kopf() {
      const a = pr.artikel;
      return `${pr.produkt.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen. Dieses Produkt stammt aus den Demodaten.</p>' : ""}
        <div class="mat-pfad">${a.pfad.map((o) => `<a href="/material/ordner/${o.id}">${esc(o.name)}</a>`).join(" / ")} / <a href="/material/artikel/${a.id}">${esc(a.inventory_no)}</a></div>
        <div class="page-head"><h1>${esc(PRUEFART[pr.art] || pr.art)} <span class="mat-h1-zusatz">${esc(a.inventory_no)}</span> ${pr.entwurf ? '<span class="badge">Entwurf</span>' : ergebnisMarke(pr.ergebnis)}</h1>
          ${pr.entwurf && !pr.eigen && DARF.verwalten ? '<div class="btn-row"><button class="btn ghost small" data-act="freigeben">Reservierung freigeben</button></div>' : ""}</div>
        <p class="mat-produktzeile"><strong>${esc(pr.produkt.name)}</strong>${pr.produkt.article_no ? ` · Art.-Nr. ${esc(pr.produkt.article_no)}` : ""} · Seriennummer ${esc(a.serial_no)} ${statusMarke(a.status)}</p>
        <p class="small muted">${pr.formular ? `Formular ${esc(pr.formular.titel || "ohne Titel")}, Version ${pr.formular.version} · ` : ""}Prüfer ${esc(pr.pruefer || "–")}${pr.urkunde ? ` (Urkundennummer ${esc(pr.urkunde)})` : ""}
          · ${pr.entwurf ? `begonnen ${esc(fmtZeit(pr.begonnen_am))}` : `Prüftag ${esc(fmtTag(pr.datum))}`}
          ${pr.durchgang ? ` · Durchgang <a href="/material/durchgang/${pr.durchgang.id}">${esc(pr.durchgang.titel)}</a>` : ""}</p>`;
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
        steuer = '<p class="help">Unterschriftsfelder folgen mit Lieferung 3.</p>';
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
          ${x.foto ? `<a href="${esc(x.foto.web)}" target="_blank" rel="noopener"><img src="${esc(x.foto.vorschau)}" alt="Foto zu ${esc(x.text)}"></a>` : ""}
          <label class="btn ${fotoPflicht && !x.foto ? "" : "secondary"} small mat-kamera">📷 ${x.foto ? "neues Foto" : "Foto"}<input type="file" accept="image/*" capture="environment" data-foto="${x.id}" class="mat-datei" aria-label="Foto zu ${esc(x.text)}"></label>
          ${x.foto ? `<button type="button" class="lnk small" data-act="pfoto-weg" data-rid="${x.id}">Foto entfernen</button>` : ""}
          ${fotoPflicht && !x.foto ? '<span class="mat-pflicht">Foto ist Pflicht</span>' : ""}</div>`;
      const notiz = mangel || x.notiz;
      return `<div class="mat-punkt${mangel ? " mangel" : ""}${nz ? " nz" : ""}" id="pp-${x.id}">
        <div class="mat-punkt-kopf"><span class="mat-punkt-text">${esc(x.text)}</span>
          ${x.kritisch ? '<span class="mat-kritisch" title="Ein Mangel hier schließt „einsatzbereit“ aus">kritisch</span>' : ""}
          ${x.art === "yesno" && x.soll ? `<span class="muted small">Soll ${esc(x.soll)}</span>` : ""}${x.pflicht ? "" : '<span class="muted small">optional</span>'}</div>
        <div class="mat-punkt-zeile">${steuer}${foto}
          ${notiz ? "" : `<button type="button" class="lnk small" data-act="pnotiz-auf" data-rid="${x.id}">+ Bemerkung</button>`}</div>
        <textarea class="mat-pnotiz" data-rid="${x.id}" rows="2" maxlength="1000" placeholder="${mangel ? "Was ist wo zu sehen? (Mangel)" : "Bemerkung"}" ${notiz ? "" : "hidden"}>${esc(x.notiz || "")}</textarea></div>`;
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
          <label class="inline"><input type="checkbox" id="ah-protokoll" checked> hinten ans Protokoll hängen (PDF ab Lieferung 3)</label>
          <div class="btn-row"><button type="button" class="btn small" data-act="anhang-hoch" id="ah-hoch" disabled>Als ein PDF anhängen</button></div></div>` : "";
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
      const offen = pr.punkte.filter((x) => x.pflicht && x.art !== "signature" && x.befund !== "nicht_zutreffend"
        && (x.art === "photo" ? !x.foto : x.art === "yesno" ? !x.wert : !(x.wert || "").trim()));
      const ohneFoto = pr.punkte.filter((x) => x.befund === "mangel" && !x.foto);
      const kritisch = pr.punkte.filter((x) => x.befund === "mangel" && x.kritisch);
      const ldErreicht = pr.lebensdauer && pr.lebensdauer.erreicht;
      return { offen, ohneFoto, kritisch, einsatzSperre: kritisch.length || ldErreicht, maengel: pr.punkte.filter((x) => x.befund === "mangel") };
    }

    function abschlussHtml() {
      return `<div class="mat-abschluss" id="pr-abschluss" role="region" aria-label="Ergebnis und Abschluss">
        <div class="mat-ergebnis" role="group" aria-label="Ergebnis">
          ${Object.keys(ERGEBNIS).map((e) => `<button type="button" data-act="ergebnis" data-e="${e}" class="e-${e}" aria-pressed="false">${esc(ERGEBNIS[e])}</button>`).join("")}</div>
        <div class="mat-abschluss-zeile">
          <label class="mat-due" id="pr-due-feld" hidden>Nächste Prüfung <input type="date" id="pr-due" value="${esc(pr.vorschlag_naechste || "")}" max="${esc(pr.vorschlag_naechste || "")}" min="${isoHeute(1)}"></label>
          <input type="text" id="pr-grund" maxlength="300" placeholder="Grund" aria-label="Grund" value="${esc(pr.grund || "")}" hidden>
          <button type="button" class="btn" data-act="abschliessen" id="pr-ok" disabled>Abschließen</button></div>
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
      if (h.kritisch.length) teile.push("kritischer Mangel – nicht einsatzbereit");
      else if (pr.lebensdauer && pr.lebensdauer.erreicht) teile.push("Lebensende erreicht – nicht einsatzbereit");
      if (pr.freipruefung && ergebnis === "einsatzbereit") teile.push("Freiprüfung: Der Artikel kehrt in seinen Herkunftsordner zurück");
      if (ergebnis === "instandsetzen" && !pr.freipruefung) teile.push("„instandsetzen“ sperrt den Artikel");
      if (ergebnis === "aussondern") teile.push("„aussondern“ ist endgültig");
      $("#pr-hinweis").textContent = teile.join(" · ");
      $("#pr-hinweis").classList.toggle("warn", !!(h.offen.length || h.ohneFoto.length || h.kritisch.length));
    }

    function leseHtml() {
      const zeilen = pr.punkte.map((x) => `<tr class="${x.befund === "mangel" ? "mat-mangelzeile" : ""}">
          <td data-l="Prüfpunkt">${x.gruppe ? `<span class="muted small">${esc(x.gruppe)}</span><br>` : ""}${esc(x.text)}${x.kritisch ? ' <span class="mat-kritisch">kritisch</span>' : ""}</td>
          <td data-l="Befund">${befundMarke(x.befund)}</td><td data-l="Wert">${x.wert ? esc(x.wert) : '<span class="muted">–</span>'}${x.art === "yesno" && x.soll ? ` <span class="muted small">(Soll ${esc(x.soll)})</span>` : ""}</td>
          <td data-l="Bemerkung">${x.notiz ? `<span class="mat-text">${esc(x.notiz)}</span>` : ""}</td>
          <td data-l="Foto">${x.foto ? `<a href="${esc(x.foto.web)}" target="_blank" rel="noopener"><img class="mat-mini" src="${esc(x.foto.vorschau)}" alt="Foto"></a>` : ""}</td></tr>`).join("");
      const ergebnisBox = pr.entwurf ? `<p class="notice">Diese Prüfung ist noch offen – in Prüfung bei ${esc(pr.pruefer)} seit ${esc(fmtZeit(pr.begonnen_am))}. Was hier steht, ist der aktuelle Stand des Entwurfs.</p>`
        : `<section class="section"><h2>Ergebnis</h2><dl class="mat-daten">
          <dt>Ergebnis</dt><dd>${ergebnisMarke(pr.ergebnis)}</dd>
          <dt>Prüftag</dt><dd>${esc(fmtTag(pr.datum))}</dd>
          ${pr.naechste ? `<dt>Nächste Prüfung</dt><dd><strong>${esc(fmtTag(pr.naechste))}</strong></dd>` : ""}
          ${pr.grund ? `<dt>Grund</dt><dd>${esc(pr.grund)}</dd>` : ""}
          ${pr.bemerkung ? `<dt>Bemerkung</dt><dd class="mat-text">${esc(pr.bemerkung)}</dd>` : ""}
          <dt>${pr.art === "aussonderung" ? "Ausgeführt von" : "Prüfer"}</dt><dd>${esc(pr.pruefer || "–")}${pr.urkunde ? ` · Urkundennummer ${esc(pr.urkunde)}` : ""}</dd>
          ${pr.basis_id ? `<dt>Grundlage</dt><dd><a href="/material/pruefung/${pr.basis_id}">Prüfung vom Tag der Aussonderung</a></dd>` : ""}
          <dt>Abgeschlossen</dt><dd>${esc(fmtZeit(pr.abgeschlossen_am))}</dd></dl>
          <p class="help">Unterschrift, PDF-Protokoll mit Prüfsumme und Festschreiben folgen mit Lieferung 3.</p></section>`;
      return `${ergebnisBox}
        ${pr.punkte.length ? `<section class="section"><h2>Befunde</h2><table class="list mat-tabelle mat-befunde"><thead><tr><th>Prüfpunkt</th><th>Befund</th><th>Wert</th><th>Bemerkung</th><th>Foto</th></tr></thead><tbody>${zeilen}</tbody></table></section>` : ""}
        ${pr.art !== "aussonderung" ? anhaengeHtml() : ""}
        ${pr.dokumente.length ? `<section class="section"><h2>Herstellerdokumente am Prüftag</h2>${dokListe(pr.dokumente, false)}</section>` : ""}`;
    }

    function bearbeitenHtml() {
      return `${pr.freipruefung ? `<p class="mat-banner s-gesperrt">GESPERRT – mit „einsatzbereit“ ist diese Prüfung die Freiprüfung.</p>` : ""}
        ${lebensdauerHinweis(pr.lebensdauer)}
        ${punkteHtml()}
        <section class="section"><h2>Zur Prüfung</h2>
          ${pr.arten && pr.arten.length > 1 ? `<label for="pr-art">Art der Prüfung</label><select id="pr-art">${pr.arten.map((x) => `<option value="${x}" ${x === pr.art ? "selected" : ""}>${esc(PRUEFART[x] || x)}</option>`).join("")}</select>` : ""}
          <label for="pr-bem">Bemerkung</label>
          <p class="help" id="pr-bem-hilfe">Mängel, die du während der Prüfung festgestellt und durch eine eigene Maßnahme gleich behoben hast, sind hier zu dokumentieren – jeweils mit der Maßnahme. Was sich nicht während der Prüfung beheben ließ, gehört als Mangel an den Prüfpunkt.</p>
          <textarea id="pr-bem" rows="3" maxlength="4000" aria-describedby="pr-bem-hilfe" placeholder="z. B. Schnapper schwergängig – gereinigt und geschmiert">${esc(pr.bemerkung || "")}</textarea></section>
        ${anhaengeHtml()}
        <p class="help">Alles ist gespeichert – du kannst die Prüfung jederzeit unterbrechen und später fortsetzen.
          <button type="button" class="lnk" data-act="verwerfen">Entwurf verwerfen</button></p>
        ${abschlussHtml()}`;
    }

    function zeichnen() {
      leisteMarkieren(pr.artikel.folder_id);
      inhalt.innerHTML = `<div class="mat-pruefung${bearbeitbar() ? " mat-mit-leiste" : ""}">${kopf()}${bearbeitbar() ? bearbeitenHtml() : leseHtml()}</div>`;
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
      if (fokusSel) {
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

    aktionen = {
      pwert: (b) => punktSetzen(+b.dataset.rid, { wert: b.dataset.wert }),
      pbefund: (b) => {
        const x = punkt(+b.dataset.rid);
        // Noch einmal auf „n. z.“ tippen nimmt es zurück: wieder der Sollwert.
        const befund = b.dataset.befund === "nicht_zutreffend" && x.befund === "nicht_zutreffend" ? "ok" : b.dataset.befund;
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
      abschliessen: async (b) => {
        if (!ergebnis) return;
        if (ergebnis === "aussondern" && !(await confirm("Den Artikel endgültig aussondern? Er wandert nach „Ausgesondert“ und zählt nicht mehr als Bestand.", "Aussondern"))) return;
        b.disabled = true;
        await laufend.catch(() => {});
        const body = { ergebnis, grund: ergebnis === "einsatzbereit" ? "" : $("#pr-grund").value, bemerkung: $("#pr-bem").value };
        if (ergebnis === "einsatzbereit") body.next_due_on = $("#pr-due").value || null;
        try {
          pr = (await api(`${API}/pruefungen/${pr.id}/abschliessen`, { method: "POST", body })).pruefung;
          toast("Prüfung abgeschlossen");
          window.scrollTo(0, 0);
          zeichnen();
        } catch (e) { toast(e.message, true); b.disabled = false; }
      },
      verwerfen: async () => {
        if (!(await confirm("Den Entwurf verwerfen? Befunde, Fotos und Anhänge dieser Prüfung gehen verloren, der Artikel ist wieder frei.", "Verwerfen"))) return;
        try { await api(`${API}/pruefungen/${pr.id}`, { method: "DELETE" }); location.href = `/material/artikel/${pr.item_id}`; }
        catch (e) { toast(e.message, true); }
      },
      freigeben: () => reservierungFreigeben(pr.id, pr.pruefer, async () => { location.href = `/material/artikel/${pr.item_id}`; }),
    };
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
      let zustand = "";
      let knopf = "";
      if (a.zustand === "erledigt") {
        zustand = `${ergebnisMarke(a.pruefung.ergebnis)} <a class="small" href="/material/pruefung/${a.pruefung.id}">${esc(fmtTag(a.pruefung.datum))}, ${esc(a.pruefung.pruefer)}</a>`;
      } else if (a.zustand === "ausgenommen") {
        zustand = `<span class="badge grey">ausgenommen</span> <span class="small">${esc(a.ausnahme.grund)}</span> <span class="muted small">(${esc(a.ausnahme.von || "")})</span>`;
        if (darf && a.lock_state !== "ausgesondert") knopf = `<button type="button" class="btn ghost small" data-act="einbeziehen" data-id="${a.id}">Einbeziehen</button>`;
      } else if (a.zustand === "nicht_geprueft") {
        zustand = '<span class="badge grey">nicht geprüft</span>';
      } else if (a.zustand === "in_pruefung") {
        zustand = `<span class="badge">in Prüfung</span> <span class="small">bei ${esc(a.entwurf.pruefer)} seit ${esc(fmtZeit(a.entwurf.seit))}</span>`;
        if (a.entwurf.eigen && DARF.pruefen) knopf = `<a class="btn small" href="/material/pruefung/${a.entwurf.id}">Weiter prüfen</a>`;
        else if (DARF.verwalten && d.offen) knopf = `<button type="button" class="btn ghost small" data-act="freigeben" data-id="${a.entwurf.id}" data-wer="${esc(a.entwurf.pruefer)}">Freigeben</button>`;
      } else {
        zustand = '<span class="muted">offen</span>';
        if (d.offen && DARF.pruefen && a.lock_state !== "ausgesondert") knopf = `<a class="btn secondary small" href="/material/artikel/${a.id}/pruefung/neu?durchgang=${d.id}">Prüfen</a>`;
        if (darf) knopf += `<button type="button" class="btn ghost small" data-act="ausnehmen" data-id="${a.id}" data-nr="${esc(a.inventory_no)}">Ausnehmen</button>`;
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
            <button class="btn" data-act="schliessen" ${d.abschliessbar ? "" : "disabled"}>Durchgang abschließen</button>` : ""}</div></div>
        <p>Ordner <a href="/material/ordner/${d.folder_id}">${esc(d.ordner)}</a> · eröffnet ${esc(fmtTag(d.eroeffnet_am))} von ${esc(d.eroeffnet_von || "–")}
          ${d.offen ? "" : ` · ${d.abgebrochen ? "abgebrochen" : "abgeschlossen"} ${esc(fmtTag(d.geschlossen_am))} von ${esc(d.geschlossen_von || "–")}`}</p>
        <div class="mat-kacheln mat-rundenzahlen">${zustaende.map(([k, t]) => `<div class="mat-kachel z-${k || "gesamt"}"><strong>${z[k || "gesamt"]}</strong><span>${k ? t : "Artikel"}</span></div>`).join("")}</div>
        <p>${fortschritt(z)}</p>
        ${d.offen ? `<p class="help">Jeder öffnet seinen Artikel mit „Prüfen“ und reserviert ihn damit – die anderen sehen „in Prüfung bei …“. Abschließen geht, sobald jeder Artikel geprüft oder mit Grund ausgenommen ist. Das Sammelprotokoll mit allen Prüfern folgt mit Lieferung 3.</p>` : ""}
        <div class="c-tabs mat-filter">${zustaende.map(([f, t]) => `<button type="button" data-act="filter" data-f="${f}" class="${f === filter ? "sel" : ""}">${esc(t)}${f ? ` (${z[f]})` : ""}</button>`).join("")}</div>
        ${liste.length ? `<table class="list mat-tabelle mat-runde"><thead><tr>${sortKopf("Inventar-Nr.", "inventar", s)}${sortKopf("Hersteller", "hersteller", s)}${sortKopf("Produkt", "produkt", s)}${sortKopf("Ablage", "ablage", s)}${sortKopf("Stand", "stand", s)}${sortKopf("Status", "status", s)}<th></th></tr></thead><tbody>${liste.map(zeile).join("")}</tbody></table>` : leer("Keine Artikel in dieser Auswahl.")}
        ${d.pruefer.length ? `<section class="section"><h2>Prüfer in diesem Durchgang</h2><ul>${d.pruefer.map((x) => `<li>${esc(x.name)}${x.urkunde ? ` · Urkundennummer ${esc(x.urkunde)}` : ""} – ${plural(x.anzahl, "Prüfung", "Prüfungen")}</li>`).join("")}</ul></section>` : ""}`;
    }
    async function neu() { await laden(); zeichnen(); }
    aktionen = {
      filter: (b) => { filter = b.dataset.f; zeichnen(); },
      sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); zeichnen(); },
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
        if (!(await confirm(`Den Durchgang „${d.titel}“ abschließen? Danach lässt sich darin nichts mehr prüfen oder ausnehmen.`, "Abschließen"))) return;
        b.disabled = true;
        try { await api(`${API}/durchgaenge/${d.id}/abschliessen`, { method: "POST", body: {} }); toast("Durchgang abgeschlossen"); await neu(); }
        catch (e) { toast(e.message, true); b.disabled = false; }
      },
      abbrechen: async (b) => {
        const z = d.zaehlung;
        const weiter = z.in_pruefung ? " Offene Prüfungen darin laufen als einzelne Prüfungen weiter." : "";
        const text = z.erledigt
          ? `Den Durchgang „${d.titel}“ abbrechen? Er endet ohne Abschluss: ${z.erledigt} geprüft, ${z.ausgenommen} ausgenommen, ${z.offen + z.in_pruefung} nicht geprüft. Was geprüft ist, bleibt dokumentiert.`
          : `Den Durchgang „${d.titel}“ abbrechen? Darin ist noch nichts geprüft – er wird ganz entfernt.`;
        if (!(await confirm(text + weiter, "Durchgang abbrechen"))) return;
        b.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge/${d.id}/abbrechen`, { method: "POST", body: {} });
          if (!r.durchgang) { location.href = "/material/pruefungen"; return; }
          filter = "";
          toast("Durchgang abgebrochen"); await neu();
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
      ${m.fotos.length ? `<div class="mat-meldung-fotos">${m.fotos.map((f) => `<a href="${esc(f.original)}" target="_blank" rel="noopener"><img src="${esc(f.vorschau)}" alt="Foto zur Meldung" loading="lazy"></a>`).join("")}</div>` : ""}`;
  }
  // Im Produktdialog: was der Melder wusste – zum Nachschlagen, während die Felder schon vorbelegt sind.
  const meldeKasten = (m) => `<div class="mat-meldekasten"><p class="small">Gemeldet von ${esc(m.created_by_name || "–")} am ${esc(fmtTag(m.created_at))}${m.ordner ? ` für ${esc(m.ordner.pfad)}` : ""}</p>${meldeDetails(m)}</div>`;

  function meldeKarte(m, alle) {
    const wer = (name) => (name ? ` von ${esc(name)}` : "");
    const knoepfe = [];
    if (alle && m.status === "offen") {
      knoepfe.push(`<button type="button" class="btn small" data-act="anlegen" data-id="${m.id}">Produkt anlegen</button>`,
                   `<button type="button" class="btn secondary small" data-act="zuordnen" data-id="${m.id}">Vorhandenes zuordnen</button>`,
                   `<button type="button" class="btn secondary small" data-act="ablehnen" data-id="${m.id}">Ablehnen</button>`);
    }
    if (m.eigen && DARF.verwalten && m.status === "eingepflegt" && m.produkt) {
      knoepfe.push(`<a class="btn small" href="/material/artikel/neu?produkt=${m.produkt.id}${m.ordner ? `&ordner=${m.ordner.id}` : ""}">Artikel davon anlegen</a>`);
    }
    // Eigene Meldungen löscht der Melder selbst – offen oder erledigt.
    if (m.eigen) knoepfe.push(`<button type="button" class="btn secondary small" data-act="loeschen" data-id="${m.id}">Löschen</button>`);
    return `<article class="mat-meldung m-${esc(m.status)}">
      <div class="mat-meldung-kopf"><h2>${esc(meldungName(m))}</h2>${meldestatusMarke(m.status)}</div>
      <p class="muted small">gemeldet${wer(m.created_by_name)} am ${esc(fmtTag(m.created_at))}${m.ordner ? ` · für ${esc(m.ordner.pfad)}` : ""}</p>
      ${meldeDetails(m)}
      ${m.treffer ? `<p class="notice">Steht inzwischen im Katalog: <a href="/material/katalog/produkt/${m.treffer.id}">${esc(produktName(m.treffer))}</a>${m.treffer.article_no ? ` <span class="muted">${esc(m.treffer.article_no)}</span>` : ""}
        ${alle ? `<button type="button" class="btn small" data-act="treffer" data-id="${m.id}">Zuordnen</button>` : ""}</p>` : ""}
      ${m.status === "eingepflegt" ? `<p class="mat-meldung-ergebnis">Eingepflegt${wer(m.resolved_by_name)} am ${esc(fmtTag(m.resolved_at))}:
        ${m.produkt ? `<a href="/material/katalog/produkt/${m.produkt.id}">${esc(produktName(m.produkt))}</a>` : '<span class="muted">Produkt inzwischen gelöscht</span>'}
        ${m.answer ? `<br><span class="mat-text">${esc(m.answer)}</span>` : ""}</p>` : ""}
      ${m.status === "abgelehnt" ? `<p class="mat-meldung-ergebnis">Abgelehnt${wer(m.resolved_by_name)} am ${esc(fmtTag(m.resolved_at))}: <span class="mat-text">${esc(m.answer)}</span></p>` : ""}
      ${knoepfe.length ? `<div class="btn-row">${knoepfe.join("")}</div>` : ""}
    </article>`;
  }

  async function meldungen() {
    let filter = DATEN.status || null;
    leisteMarkieren(null);
    async function zeichnen() {
      const d = await api(`${API}/meldungen${filter ? `?status=${encodeURIComponent(filter)}` : ""}`);
      filter = d.filter;
      const liste = d.meldungen;
      const meldung = (b) => liste.find((m) => m.id === +b.dataset.id);
      inhalt.innerHTML = `<div class="page-head"><h1>${d.alle ? "Produktmeldungen" : "Deine Produktmeldungen"}</h1>
          <div class="btn-row"><a class="btn secondary" href="/material/katalog">Katalog</a>${DARF.verwalten ? '<a class="btn" href="/material/artikel/neu">+ Artikel</a>' : ""}</div></div>
        <p class="help">${d.alle ? "Materialwarte melden hier Produkte, die ihnen beim Anlegen von Artikeln im Katalog fehlen. „Produkt anlegen“ übernimmt ihre Angaben in den Produktdialog. Der Melder bekommt eine Mail, sobald das Produkt im Katalog ist – oder deine Begründung, wenn du ablehnst."
          : "Produkte, die du beim Anlegen von Artikeln als fehlend gemeldet hast. Du bekommst eine Mail, sobald ein Katalogpfleger sie bearbeitet hat."}</p>
        <div class="mat-filter" role="group" aria-label="Status">${[["offen", "offen"], ["erledigt", "erledigt"], ["alle", "alle"]].map(([w, t]) => `<button type="button" class="btn small${w === filter ? "" : " secondary"}" data-act="filter" data-f="${w}" aria-pressed="${w === filter}">${t}${w === "offen" && d.offen ? ` (${d.offen})` : ""}</button>`).join("")}</div>
        ${liste.length ? liste.map((m) => meldeKarte(m, d.alle)).join("") : leer(filter === "offen" ? "Keine offenen Meldungen." : "Keine Meldungen.")}`;
      aktionen = {
        filter: (b) => {
          filter = b.dataset.f;
          try { history.replaceState(null, "", `/material/katalog/meldungen?status=${filter}`); } catch (e) { /* nur die Adresszeile */ }
          zeigen(zeichnen);
        },
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
      <div class="mat-produktwahl"><input type="search" id="zu-q" autocomplete="off" value="${esc(m.manufacturer)}"><div id="zu-treffer" class="mat-treffer"></div></div>
      <div id="zu-gewaehlt" class="mat-gewaehlt" hidden></div>
      <label for="zu-antwort">Anmerkung für den Melder (optional, steht in seiner Mail)</label><textarea id="zu-antwort" rows="2" maxlength="1000"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="zu-ok" type="button" disabled>Zuordnen</button></div>`,
    (dlg, body) => {
      let gewaehlt = null;
      let los = null;
      async function suchen() {
        const q = $("#zu-q", body).value.trim();
        if (!q) { $("#zu-treffer", body).innerHTML = ""; return; }
        try {
          const d = await api(`${API}/produkte?q=${encodeURIComponent(q)}&pro_seite=8`);
          $("#zu-treffer", body).innerHTML = d.produkte.length ? d.produkte.map((p, i) => `<button type="button" class="mat-treffer-zeile" data-i="${i}">
              ${p.vorschau ? `<img class="mat-mini" src="${esc(p.vorschau)}" alt="">` : ""}<strong>${esc(produktName(p))}</strong> <span class="muted">${esc(p.article_no || "")} · ${esc(p.category_name || "")}</span></button>`).join("")
            : '<p class="help">Kein Produkt gefunden.</p>';
          $$(".mat-treffer-zeile", body).forEach((b) => {
            b.onclick = () => {
              gewaehlt = d.produkte[+b.dataset.i];
              $("#zu-gewaehlt", body).hidden = false;
              $("#zu-gewaehlt", body).innerHTML = `<strong>${esc(produktName(gewaehlt))}</strong> <span class="muted">${esc(gewaehlt.article_no || "")}</span>`;
              $("#zu-treffer", body).innerHTML = "";
              $("#zu-ok", body).disabled = false;
            };
          });
        } catch (e) { toast(e.message, true); }
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
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ab-ok" type="button">Ablehnen</button></div>`,
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
      <div class="field-row"><div><label for="me-her">Hersteller</label><input type="text" id="me-her" maxlength="120" value="${esc(v.manufacturer || "")}"></div>
        <div><label for="me-mod">Modell</label><input type="text" id="me-mod" maxlength="160" value="${esc(v.model || "")}"></div></div>
      <div class="field-row"><div><label for="me-art">Artikelnummer des Herstellers</label><input type="text" id="me-art" maxlength="80"></div>
        <div><label for="me-norm">Norm</label><input type="text" id="me-norm" maxlength="200" placeholder="z. B. EN 362"></div></div>
      <label for="me-kat">Kategorie</label><select id="me-kat"><option value="">– weiß ich nicht –</option>${kategorieOptionen(kats, null)}</select>
      <label for="me-links">Links</label><textarea id="me-links" rows="3" placeholder="https://… – je Zeile eine Adresse: Herstellerseite, Gebrauchsanleitung, Händler"></textarea>
      <label for="me-fotos">Fotos (bis zu 3)</label><input type="file" id="me-fotos" accept="image/*" multiple>
      <div class="help">Etikett oder Typenschild – darauf stehen meist Hersteller, Modell, Norm und Herstelldatum.</div>
      <label for="me-note">Bemerkung</label><textarea id="me-note" rows="3" maxlength="2000" placeholder="Was hilft beim Einpflegen? z. B. Größe, Farbe, wo gekauft"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="me-ok" type="button">Melden</button></div>`,
    (dlg, body) => {
      fokus($("#me-her", body));
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

  const ANSICHTEN = { dashboard, pruefungen, bestand, ordner, artikel, artikel_neu: artikelNeu, katalog, produkt, formular, suche,
                      meldungen, pruefung_neu: pruefungNeu, pruefung: pruefungAnsicht, durchgang: durchgangAnsicht };
  leisteLaden();
  zeigen(ANSICHTEN[ANSICHT] || dashboard);
})();
