/* Modul Material – Oberfläche aller Ansichten: Übersicht, fällige Prüfungen, Bestand (Ordnerbaum mit
   Systemordnern und Mehrfachauswahl), Artikel mit Lebenslauf (Prüfungen und Journal), Artikel anlegen,
   Prüfung (Formular fürs Telefon), Prüfdurchgang, Katalog mit Produkten, Dokumenten und Prüfformularen,
   Suche nach Nummern; links die Ordnerleiste. Seit Phase 3 dazu „Meine PSA“ (auch ohne Modulzugang, dann ohne
   Modulnavigation und Ordnerleiste) und die Mangelmeldung.
   Welche Ansicht gemeint ist, sagt data-ansicht am <main>. Was das Konto darf, gilt seit Phase 2 je Ordner (Freigaben):
   Knöpfe an einem Ordner, Artikel, einer Prüfung oder einem Durchgang fragen dessen Feld „darf“ (lesen, grund,
   pruefen, verwalten); data-darf sagt nur, was das Konto irgendwo darf – für Reiter und die Knöpfe der Übersicht.
   Ausgeblendet wird nur, was ohnehin scheitern würde – der Server prüft jede Aktion selbst. */
(function () {
  const { esc, api, toast } = S;

  /* --- Fokus zurück nach Esc oder „Abbrechen“ (Browserprüfung vor dem Merge, B2) ----------------------------------
     Wer einen Dialog öffnet, landet nach dem Schließen wieder dort, wo er war: auf dem Knopf, der ihn öffnete – aus
     einem Untermenü (details.mat-menue) auf dessen Menüknopf. Gemerkt wird der zuletzt angeklickte Knopf außerhalb
     von Dialogen; so gilt es auch für Dialoge, die erst nach einem Laden öffnen (Ordner verschieben, Löschen,
     Katalog exportieren, Als Variante kopieren). Zurückgegeben wird der Fokus nur, wenn er sonst verloren wäre (auf
     der Seite oder im geschlossenen Dialog) und kein anderer Dialog offen ist. Folgedialoge im selben #dlg (Ergebnis
     nach dem Anlegen) erben das Ziel des ersten; hat die Ansicht neu gezeichnet, nimmt er den neuen Knopf gleichen
     Texts. */
  let letzterKlick = null;
  document.addEventListener("click", (e) => {
    const el = e.target.closest && e.target.closest("button, a[href], summary, [data-act]");
    if (el && !el.closest("dialog")) letzterKlick = { el, zeit: Date.now() };
  }, true);
  function fokusZiel() {
    const k = letzterKlick && Date.now() - letzterKlick.zeit < 30000 && letzterKlick.el.isConnected ? letzterKlick.el : null;
    const aktiv = document.activeElement;
    const el = k || (aktiv && aktiv !== document.body ? aktiv : null);
    if (!el || el.closest("dialog")) return null;
    const menue = el.closest("details.mat-menue");
    return menue ? menue.querySelector("summary") : el;
  }
  function fokusZurueckgeben(ziel) {
    const jetzt = document.activeElement;
    if (!ziel || document.querySelector("dialog[open]")) return;
    if (jetzt && jetzt !== document.body && !jetzt.closest("dialog")) return;
    // Hat die Ansicht inzwischen neu gezeichnet (nach dem Speichern), steht dort ein neuer Knopf mit demselben Text.
    const text = ziel.textContent.trim();
    const el = ziel.isConnected ? ziel : [...document.querySelectorAll(ziel.tagName)]
      .find((x) => x.textContent.trim() === text && x.getClientRects().length && !x.closest("dialog"));
    if (el) el.focus();
  }
  let dlgZiel = null;
  const dlgEl = document.getElementById("dlg");
  if (dlgEl) {
    dlgEl.addEventListener("close", () => {
      if (dlgEl.open) return;                    // gleich wieder offen (Folgedialog): Ziel bleibt für dessen Ende
      const ziel = dlgZiel;
      dlgZiel = null;
      fokusZurueckgeben(ziel);
    });
  }
  function dialog(html, onOpen) {
    if (dlgEl && !dlgEl.open && !dlgZiel) dlgZiel = fokusZiel();
    return S.dialog(html, onOpen);
  }
  function confirm(text, okLabel, neinLabel) {
    const ziel = document.querySelector("dialog[open]") ? null : fokusZiel();
    return S.confirm(text, okLabel, neinLabel).then((ja) => {
      setTimeout(() => fokusZurueckgeben(ziel), 0);
      return ja;
    });
  }

  /* --- Produktname mit Beschreibung (Nachbesserungen vom 18.10.2026) ---------------------------------------------
     Die Beschreibung eines Produkts ist ein kurzer Zusatz hinter dem Namen, etwa die Verschlussart eines Karabiners.
     Sichtbar heißt sie seit dem Wunsch vom 18.10.2026 „Bemerkung“ (Produktdialog, Produktseite, Platzhalter der
     Produktsuche, Journal am Produkt – feldName); description und die Namen hier im Code bleiben. Wo ein Produkt
     genannt wird, steht sie direkt hinter dem Modell und vor der Artikelnummer, ohne Strich und grau wie die
     Artikelnummer in der Katalogliste: „D Classic Screwlock K496B“ – der Name hervorgehoben bzw. verlinkt, der Zusatz
     außerhalb davon (class="muted mat-zusatz", nie fett, nie unterstrichen). Eine Regel für alle Stellen (modellTeile,
     produktZusatz), dieselbe wie katalog.produkt_teile auf dem Server (PDF, CSV, Mails): Ohne Beschreibung nur der
     Name. Steht der Zusatz schon von Hand im Modellnamen („D Classic | Screwlock“), gilt der Teil vor dem Strich als
     Name und der Teil dahinter als Zusatz – angezeigt wie eine Beschreibung, der Katalog bleibt, wie er ist; dieselbe
     Angabe in beiden kommt nicht doppelt, zwei verschiedene stehen mit Komma („Screwlock, Aluminium“). Eine ältere,
     längere Beschreibung (bis dahin war das Feld mehrzeilig) steht in einer Zeile, nach BESCHREIBUNG_MAX Zeichen mit
     „…“ gekürzt; den vollen Text zeigt der title.
     Ausgaben: produktName als Text, Name und Zusatz durch ein Leerzeichen getrennt (Rückfragen, Dialogtitel, alt);
     nameHtml (der Name, maskiert – kommt in den Link oder in <strong>) und dahinter zusatzHtml (der graue Zusatz mit
     führendem Leerzeichen, oder nichts) für Seiten und Listen – auch für suche.js und global.js (window.MatProdukt). */
  const BESCHREIBUNG_MAX = 80;
  // Der Modellname, zerlegt an „|“: vorn der Name, dahinter ein Zusatz von Hand (leere Teile fallen weg).
  function modellTeile(model) {
    const teile = String(model || "").split("|").map((t) => t.replace(/\s+/g, " ").trim());
    const extra = teile.slice(1).filter(Boolean);
    return { name: teile[0] || extra.shift() || "", extra };
  }
  // Der Zusatz hinter dem Namen als { text, voll } oder null; voll nur, wenn eine ältere, lange Beschreibung
  // gekürzt ist (für den title).
  function produktZusatz(p) {
    const { extra } = modellTeile(p && p.model);
    let z = String((p && p.description) || "").replace(/\s+/g, " ").trim();
    if (extra.some((t) => t.toLowerCase() === z.toLowerCase())) z = "";
    let k = z;
    if (z.length > BESCHREIBUNG_MAX) {
      k = z.slice(0, BESCHREIBUNG_MAX - 1);
      if (k.indexOf(" ", BESCHREIBUNG_MAX >> 1) >= 0) k = k.slice(0, k.lastIndexOf(" "));   // am Wortende, wo es geht
      k = `${k.replace(/[\s,;:–-]+$/, "")}…`;
    }
    const text = [...extra, k].filter(Boolean).join(", ");
    return text ? { text, voll: k === z ? "" : [...extra, z].join(", ") } : null;
  }
  // ohneHersteller: ab dem Modell – in Listen mit eigener Herstellerspalte.
  const nameText = (p, ohneHersteller) =>
    `${ohneHersteller ? "" : `${p.manufacturer || ""} `}${modellTeile(p.model).name}`.trim();
  const produktName = (p, ohneHersteller) => {
    const z = produktZusatz(p);
    return `${nameText(p, ohneHersteller)}${z ? ` ${z.text}` : ""}`.trim();
  };
  /* Kurze Wörter mit Bindestrich („GS-S“, „HB-7“) brechen nicht am Strich um („GS-“ / „S“), sondern rutschen ganz in die
     nächste Zeile (mat-wort, material.css). Lange behalten ihre Umbruchstelle – sonst ragten sie aus einer schmalen
     Spalte (Geräte-Prüfung vom 21.10.2026). */
  const WORT_MAX = 16;
  const nameHtml = (p, ohneHersteller) => nameText(p, ohneHersteller).split(" ")
    .map((w) => (w.includes("-") && w.length <= WORT_MAX ? `<span class="mat-wort">${esc(w)}</span>` : esc(w))).join(" ");
  const zusatzHtml = (p) => {
    const z = produktZusatz(p);
    return z ? ` <span class="muted mat-zusatz"${z.voll ? ` title="${esc(z.voll)}"` : ""}>${esc(z.text)}</span>` : "";
  };
  /* Nummern im Fließtext hinter dem Produkt – „ · Art.-Nr. DEMO-K-1“, „Seriennummer DEMO-K-0815“ – stehen als ein
     Stück (mat-ganz, material.css): Passt es nicht mehr in die Zeile, rutscht es ganz in die nächste, statt an einem
     Bindestrich zu brechen („Art.-“ / „Nr. …“). Nur was breiter ist als eine ganze Zeile, bricht darin um. html: die
     Nummer schon maskiert, etwa mit markiertem Suchtext (suche.js); sonst wird nr maskiert. */
  const nummerHtml = (label, nr, html) => `<span class="mat-ganz">${label} ${html === undefined ? esc(nr) : html}</span>`;
  // Der Trennpunkt gehört zum Stück – sonst blieb er beim Umbruch allein am Zeilenende stehen (Meine PSA am Telefon).
  const artNrHtml = (nr, html) => (nr ? ` ${nummerHtml("· Art.-Nr.", nr, html)}` : "");
  // Die Artikelnummer allein, leise hinter dem Namen (Listen, Treffer, Meldungen): ebenfalls als ein Stück – „GS-S“
  // brach sonst in der engen Tabelle am Strich um (Geräte-Prüfung vom 22.10.2026).
  const artNrKurz = (nr) => (nr ? ` <span class="muted mat-ganz">${esc(nr)}</span>` : "");
  window.MatProdukt = { name: produktName, nameHtml, zusatzHtml, zusatz: produktZusatz, max: BESCHREIBUNG_MAX,
                        artNr: artNrHtml, nummer: nummerHtml };

  const root = document.getElementById("mat");
  if (!root) return;
  const ANSICHT = root.dataset.ansicht || "dashboard";
  const DATEN = JSON.parse(root.dataset.daten || "{}");
  const DARF = JSON.parse(root.dataset.darf || "{}");
  const inhalt = document.getElementById("mat-inhalt");
  const API = "/api/material";
  /* Seitentitel je Ansicht (Browserprüfung vor dem Merge, V2): vorn das Gezeigte – Artikelnummer, Ordner, Produkt,
     Kategorie –, dann „Materialablage“ (S.titel); seite.html setzt bis dahin ein festes Wort je Ansicht. Ohne
     Modulzugang (nur „Meine PSA“, ohne Modulnavigation) ohne den Modulnamen – das Konto kennt das Modul nicht. */
  const OHNE_MODUL = !document.querySelector(".mat-nav");
  const seitenTitel = (...teile) => S.titel(teile, OHNE_MODUL ? "" : "material");
  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  /* --- Großansicht für Fotos -------------------------------------------------------------------------
     Ein Klick auf ein Foto (Mangelfoto, Produktbild, Meldungsfoto) zeigt es groß über der Seite statt in einem neuen
     Tab; mit Strg/⌘ oder der mittleren Maustaste öffnet der Link wie gewohnt einen Tab. Gezeigt wird die Webfassung
     (gedreht, auch bei HEIC vom iPhone), „Original“ führt zur hochgeladenen Datei. Stehen mehrere Fotos zusammen
     (data-gruppe, etwa alle Fotos einer Prüfung), blättern Pfeiltasten und Pfeilknöpfe – mit dem Finger auch
     Wischen nach links oder rechts; Wischen nach unten schließt.
     Die Großansicht ist ein modaler <dialog>: Der Fokus bleibt darin (Tab landete sonst auf der Kopfleiste dahinter),
     die Seite dahinter ist inert und rollt nicht mit (am Touchgerät html.mat-lb-offen und touch-action: none, mit der
     Maus ein wheel-Handler) – nach dem Schließen steht man an derselben Stelle des Prüfformulars. Solange er offen
     ist, sperrt html:has(dialog[open]) (app.css) auch das Ziehen zum Neuladen.
     Mit der Tastatur öffnet Enter das Foto wie jeden Link, die Leertaste wie bei einem Knopf auch; Esc schließt. */
  const bildLink = (web, original, titel, gruppe, bildHtml, label) => `<a class="mat-bildlink" href="${esc(original || web)}"
    target="_blank" rel="noopener" data-web="${esc(web)}" data-titel="${esc(titel || "")}"${gruppe ? ` data-gruppe="${esc(gruppe)}"` : ""}
    aria-label="${esc(label || (titel ? `Foto groß zeigen: ${titel}` : "Foto groß zeigen"))}">${bildHtml}</a>`;

  function bildZeigen(link) {
    const gruppe = link.dataset.gruppe;
    const liste = gruppe ? $$(`a.mat-bildlink[data-gruppe="${CSS.escape(gruppe)}"]`) : [link];
    let i = Math.max(0, liste.indexOf(link));
    const vorher = document.activeElement;
    const stelle = window.scrollY;
    const box = document.createElement("dialog");
    box.className = "mat-lightbox";
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
    const schliessen = () => { if (box.open) box.close(); };
    box.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" && liste.length > 1) { e.preventDefault(); blaettern(1); }
      else if (e.key === "ArrowLeft" && liste.length > 1) { e.preventDefault(); blaettern(-1); }
    });
    // Escape schließt den Dialog von selbst; aufgeräumt wird in jedem Fall hier.
    box.addEventListener("close", () => {
      box.remove();
      document.documentElement.classList.remove("mat-lb-offen");
      if (vorher && vorher.focus) vorher.focus({ preventScroll: true });
      if (Math.abs(window.scrollY - stelle) > 1) window.scrollTo(0, stelle);
    });
    // Wischen mit Finger oder Stift: waagerecht blättert, nach unten schließt. Die Maus klickt wie bisher.
    let start = null;
    let gewischt = false;
    box.addEventListener("pointerdown", (e) => {
      gewischt = false;
      start = e.pointerType !== "mouse" && e.isPrimary ? { x: e.clientX, y: e.clientY } : null;
    });
    box.addEventListener("pointercancel", () => { start = null; });
    // Jede Bewegung im Dialog gehört der Wischgeste (touch-action: none). Chromium nahm einen Wisch trotzdem als Schwung
    // (Fling), und der erste Tipp danach – auf ✕ oder einen Pfeil – hielt nur diesen an, statt zu schließen oder zu
    // blättern. Wer touchmove absagt, lässt keinen Schwung entstehen; touchstart bleibt frei, sonst käme kein Klick an.
    box.addEventListener("touchmove", (e) => { if (e.cancelable) e.preventDefault(); }, { passive: false });
    // Mit der Maus rollt das Rad die Seite dahinter nicht – die Rollsperre (html.mat-lb-offen) gilt nur am Touchgerät,
    // sonst stünde statt des Rollbalkens ein weißer Streifen da.
    box.addEventListener("wheel", (e) => { if (!e.ctrlKey) e.preventDefault(); }, { passive: false });   // Strg+Rad zoomt weiter
    box.addEventListener("pointerup", (e) => {
      if (!start || !e.isPrimary) return;
      const dx = e.clientX - start.x, dy = e.clientY - start.y;
      start = null;
      if (liste.length > 1 && Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy)) { gewischt = true; blaettern(dx < 0 ? 1 : -1); }
      else if (dy > 90 && dy > 1.5 * Math.abs(dx)) { gewischt = true; schliessen(); }
    });
    box.addEventListener("click", (e) => {
      if (gewischt) { gewischt = false; return; }                          // das Ende einer Wischgeste ist kein Tippen
      const pfeil = e.target.closest(".mat-lb-pfeil");
      if (pfeil) { blaettern(pfeil.classList.contains("zurueck") ? -1 : 1); return; }
      if (e.target === img || e.target.closest("figcaption")) return;     // „Original“ öffnet seinen Tab
      schliessen();
    });
    document.body.appendChild(box);
    zeige();
    document.documentElement.classList.add("mat-lb-offen");
    box.showModal();
    $(".md-lightbox-close", box).focus();
  }
  document.addEventListener("click", (e) => {
    const l = e.target.closest("a.mat-bildlink");
    if (!l || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    bildZeigen(l);
  });
  // Leertaste auf einem Foto: Das Drücken rollte sonst die Seite; geöffnet wird erst beim Loslassen, wie bei einem
  // Knopf – dann steht der Fokus schon auf „Schließen“, wenn nichts mehr von der Taste nachkommt.
  const leertasteAufFoto = (e) => e.key === " " && !e.ctrlKey && !e.metaKey && !e.altKey && e.target instanceof Element
    && e.target.matches("a.mat-bildlink");
  document.addEventListener("keydown", (e) => { if (leertasteAufFoto(e)) e.preventDefault(); });
  document.addEventListener("keyup", (e) => { if (leertasteAufFoto(e)) { e.preventDefault(); bildZeigen(e.target); } });

  const STATUS = { einsatzbereit: "einsatzbereit", bald_faellig: "bald fällig", ueberfaellig: "überfällig", neu: "neu",
                   gesperrt: "gesperrt", lebensdauer: "Lebensdauer erreicht", ausgesondert: "ausgesondert" };
  const PRUEFART = { eingang: "Eingangsprüfung", periodisch: "periodische Prüfung", ausserplanmaessig: "außerplanmäßige Prüfung",
                     reparatur: "Prüfung nach Reparatur", aussonderung: "Aussonderung" };
  const PRUEFART_KURZ = { eingang: "Eingangsprüfung", periodisch: "periodisch", ausserplanmaessig: "außerplanmäßig",
                          reparatur: "Reparatur", aussonderung: "Aussonderung" };
  // Wie models.ERGEBNISSE: „aussondern“ nur an Aussonderungen und Prüfungen vor Schritt 28; wählbar sind die drei ersten.
  const ERGEBNIS = { einsatzbereit: "einsatzbereit", instandsetzen: "instandsetzen", aussondern_empfohlen: "aussondern empfohlen", aussondern: "aussondern (ausgesondert)" };
  const WAEHLBAR = ["einsatzbereit", "instandsetzen", "aussondern_empfohlen"];
  const BEFUND = { ok: "in Ordnung", mangel: "Mangel", nicht_zutreffend: "nicht zutreffend" };
  const ANHANGART = { externes_pruefformular: "externes Prüfformular", pruefbericht: "Prüfbericht", foto: "Foto", sonstiges: "Sonstiges" };
  const SPERRGRUND = { sturz: "Sturzbelastung", beschaedigung: "Beschädigung", verlust: "Verlust", rueckruf: "Rückruf" };
  const AUSSONDERUNGSGRUND = { lebensdauer: "Lebensdauer erreicht", verlust: "Verlust", irreparabel: "irreparabel" };
  const MATERIALART = { textil: "textil", metall_hardware: "Metall", sonstiges: "sonstiges" };
  // „Set“: ein Ordner, in dem ein Satz Material zusammen liegt (seit Schritt 26 wieder so benannt) – wie models.ORDNERARTEN.
  const ORDNERART = { gliederung: "Gliederung", standort: "Standort", fahrzeug: "Fahrzeug", set: "Set",
                      persoenlich: "persönlich", sonstiges: "sonstiges" };
  const DOKART = { produktbild: "Produktbild", konformitaetserklaerung: "Konformitätserklärung",
                   gebrauchsanleitung: "Gebrauchsanleitung", pruefanweisung: "Prüfanweisung", pflegehinweis: "Pflegehinweis",
                   datenblatt: "Datenblatt", sonstiges: "Sonstiges" };
  const EDITOR = { yesno: "Ja/Nein", text: "Text", date: "Datum", number: "Zahl", photo: "Foto", signature: "Unterschrift", laenge: "Länge (m)" };
  // Artikellänge (Schritt 20): 57.5 → „57,5 m“ (eine Nachkommastelle, deutsches Komma); ohne Einheit fürs Eingabefeld.
  const laengeText = (m, einheit = true) => (m === null || m === undefined || m === "" ? "" : `${Number(m).toFixed(1).replace(".", ",")}${einheit ? " m" : ""}`);
  /* Altbestand vor Schritt 26 (Rückbau der Set-Funktion): die Wörter für Werte der früheren Set-Felder im Journal wie
     beschriftung.SET_WERTE und die Gruppe der Ja/Nein-Zeilen „… vorhanden“ an Prüfungen früherer Set-Artikel wie
     stueckliste.SET_GRUPPE – nur zum Lesen alter Einträge und Prüfungen. */
  const SET_WERTE = {
    lock_cause: { eigen: "eigener Grund", set: "mit dem Set" },
    verbleib: { aussondern: "mit aussondern", weiterfuehren: "entnommen und weitergeführt" },
    gesamtergebnis: { einsatzbereit: "einsatzbereit", gesperrt: "nicht einsatzbereit – Set gesperrt", ausgesondert: "Set ausgesondert" },
    set_grund: { unvollstaendig: "unvollständig", tausch: "Teil getauscht oder eingesetzt", ausgesondert: "Set ausgesondert",
                 bestandteil: "Bestandteil ersetzt – Set prüfen", stueckliste: "Stückliste übertragen" },
    austausch: { ja: "ja", nein: "nein", nicht_belegt: "nicht belegt" },
  };
  const SET_GRUPPE = "Bestandteile des Sets";
  // Die Gruppe der Zeilen „… vorhanden“ einer Bestandteil-Liste (Schritt 25) – wie stueckliste.BESTANDTEIL_GRUPPE.
  const BESTANDTEIL_GRUPPE = "Bestandteile";
  // Eine Zeile „… vorhanden“ (Bestandteil-Liste, bei alten Prüfungen auch eines früheren Set-Artikels): der Server sagt
  // es (bestandteil) – ein Formular darf selbst eine Gruppe „Bestandteile“ haben.
  const istBestandteil = (x) => (x.bestandteil !== undefined ? Boolean(x.bestandteil)
    : x.gruppe === SET_GRUPPE || x.gruppe === BESTANDTEIL_GRUPPE);
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
    recht_material: "Stufe Materialablage", mat_pruefer: "Prüfer", mat_katalog: "Katalogpfleger", urkundennummer: "Urkundennummer",
    system_kind: "Systemordner", url: "Adresse", file_path: "Datei", sha256: "SHA-256", size: "Größe",
    lock_state: "Sperrzustand", lock_reason: "Grund der Sperre", origin_folder_id: "Herkunftsordner", herkunft: "Herkunftsordner",
    last_inspected_on: "Zuletzt geprüft", pruefung: "Prüfung", ergebnis: "Ergebnis", art: "Art", grund: "Grund", datum: "Datum",
    aussonderung: "Aussonderung",
    pruefer: "Prüfer", result: "Ergebnis", inspected_on: "Prüftag", reason: "Grund", maengel: "Mängel", item_id: "Artikel Nr.",
    round_id: "Durchgang Nr.", form_id: "Formular Nr.", form_version: "Formularversion", inspector_name: "Prüfer",
    begonnen: "begonnen", seiten: "Seiten", dateien: "Dateien", basis: "aus Prüfung", empfehlung: "empfohlen in Prüfung", erledigt: "erledigt", ausgenommen: "ausgenommen",
    links: "Links", fotos: "Fotos", note: "Bemerkung", answer: "Antwort", status: "Status",
    von: "Kopie von Produkt Nr.", kopie_von: "Kopie von Dokument Nr.", dokumente: "Dokumente übernommen",
    protocol_id: "Protokoll-ID", pdf_sha256: "Prüfsumme", pdf_hashed_bytes: "Bytes", file_sha256: "Prüfsumme der Datei",
    anhaenge_angefuegt: "Anhänge angefügt", login: "Anmeldung", berichtigung: "Berichtigung", berichtigt: "berichtigt",
    unterschrift: "Unterschrift", nicht_geprueft: "nicht geprüft", uid: "Katalogkennung",
    rueckruf: "Rückruf Nr.", serials: "Seriennummern", mail: "Mail an Materialwarte und Prüfer", close_note: "Vermerk",
    // Phase 2: Freigaben je Ordner und Personenzuordnung – dieselben Wörter wie in beschriftung.py
    freigabe: "Freigabe Nr.", konto: "Person", recht: "Recht", bis: "bis", notiz_geaendert: "Notiz geändert",
    // Phase 2 · Lieferung 2: Erinnerungen
    reminders_off: "Erinnerungsmails aus",
    // Phase 2 · Lieferung 3: Bestandsimport und Prüfanleitung aus dem Wiki
    bestandsimport: "Bestandsimport Nr.", datei: "Datei", zeile: "Zeile", zeilen: "Zeilen",
    artikel_angelegt: "Artikel angelegt", schon_im_bestand: "schon im Bestand", nacharbeit: "Nacharbeit (Zeilen)",
    ersetzt: "neu eingelesen (Zeilen)", aus_nacharbeit: "aus der Nacharbeit",
    liste_inventarnummer: "bisherige Inventarnummer", liste_zuletzt_geprueft: "zuletzt geprüft laut Liste",
    liste_naechste_pruefung: "nächste Prüfung laut Liste", seite: "Seite der Strömipedia Nr.",
    // Phase 3 · Lieferung 1: Mangelmeldung
    mangel: "Mangelmeldung Nr.", mangelbeschreibung: "Mangelbeschreibung",
    // Änderungsanträge an festen Stammdaten (Entscheidungen vom 21.10.2026)
    antrag: "Änderungsantrag Nr.", begruendung: "Begründung", beantragt_von: "beantragt von", anmerkung: "Anmerkung",
    ablehnung: "Begründung der Ablehnung", feld: "Feld",
    rueckruf_nicht_mehr: "Rückruf trifft ihn nicht mehr", rueckruf_neu: "Rückruf trifft ihn jetzt",
    rueckruf_wieder_offen: "Rückruf wieder offen (erneut prüfen)",
    // Artikellänge (Schritt 20)
    length_m: "Länge (m)", items_have_length: "Artikel haben eine Länge",
    // Änderungsanträge an alle Stammdaten (Schritt 23): das von Hand vorgezogene Lebensende
    retire_by_manual: "Lebensende (von Hand vorgezogen)",
    // Altbestand vor Schritt 26 (Rückbau der Set-Funktion): Felder der früheren Sets, nur zum Lesen alter Einträge.
    // Sets (Schritt 21)
    is_set: "Set", bestandteile: "Bestandteile", teile: "Teile", set: "Set Nr.", set_inventar: "Set",
    // Sets anlegen und Stückliste übertragen (Schritt 22, Wunsch vom 24.10.2026); Set-Meldung (S8)
    fehlt: "fehlt", nicht_in_stueckliste: "nicht mehr in der Stückliste", set_teile: "Teile des Sets",
    stueckliste: "Stückliste übernommen",
    // Sperren, Set prüfen und Austausch im Set (Schritt 21, Paket K2)
    lock_cause: "Sperrursache", teil: "Teil", verbleib: "Verbleib", gesamtergebnis: "Gesamtergebnis",
    freigegeben: "freigegeben", gruende: "Gründe", lauf: "Set-Prüfung Nr.", set_lauf_id: "Set-Prüfung Nr.",
    set_grund: "Anlass der Set-Sperre", bestandteil: "Bestandteil", bestaetigt: "Austausch bestätigt",
    ersetzt_teil: "ersetzt Teil", austausch: "Austausch laut Hersteller möglich", hinweis: "Hinweis",
    geprueft: "abgeschlossene Prüfungen",
    // Sets, Teil 2 (L2b): vorhandenen Artikel einsetzen, „Bestandteil ersetzt“
    vorhanden: "vorhandener Artikel", bemerkung: "Bemerkung",
    // „position“: Nummer der Position in der Stückliste; „slot“ schrieb nur der Stand vor der Nachbesserung (B1).
    position: "Position", slot: "Kennung der Position",
    // Produkt am Artikel ändern (Feintuning, L2b Nr. 29): der lesbare Name neben der Kennung
    produkt: "Produkt",
    // Bestandteil-Liste an normalen Produkten und Seriennummern der Bestandteile (Schritt 25)
    bestandteil_nummern: "Seriennummern der Bestandteile",
    // Set-Protokolle im Prüfdurchgang (Schritt 27)
    set_protokolle: "Set-Protokolle",
  };
  // Die Beschriftung eines Feldes in einem Journaleintrag – wie beschriftung.feld_name: „description“ ist am Produkt der
  // kurze Zusatz hinter dem Namen und heißt dort seit dem Wunsch vom 18.10.2026 „Bemerkung“; an Ordnern und in den
  // Einträgen eines Rückrufs (auch sie stehen am Produkt) bleibt es die Beschreibung.
  const feldName = (f, j) => (f === "description" && j.entity === "product" && !/^rueckruf/.test(j.action || "")
    ? "Bemerkung" : FELD[f] || f);
  const AKTION = { angelegt: "angelegt", geaendert: "geändert", geloescht: "gelöscht", verschoben: "verschoben",
                   bild: "Bild geändert", foto: "Foto geändert", neue_version: "neue Version", zurueckgezogen: "zurückgezogen",
                   aktiviert: "aktiviert", deaktiviert: "deaktiviert", lebensende: "Lebensende nachgezogen", rollen: "Rollen",
                   begonnen: "Prüfung begonnen", abgeschlossen: "Prüfung abgeschlossen", verworfen: "Prüfung verworfen",
                   reservierung_freigegeben: "Reservierung aufgehoben", geprueft: "geprüft", freigeprueft: "freigeprüft",
                   gesperrt: "gesperrt", ausgesondert: "ausgesondert", anhang: "Anhang", anhang_entfernt: "Anhang entfernt",
                   eroeffnet: "Durchgang eröffnet", ausgenommen: "ausgenommen", einbezogen: "wieder einbezogen",
                   geschlossen: "Durchgang abgeschlossen", faelligkeit: "Fälligkeit vorgezogen", umbenannt: "umbenannt",
                   eingepflegt: "eingepflegt", abgelehnt: "abgelehnt", variante: "als Variante angelegt",
                   festgeschrieben: "festgeschrieben", berichtigt: "berichtigt", berichtigung_begonnen: "Berichtigung begonnen",
                   unterschrift: "Unterschrift geändert", urkundennummer: "Urkundennummer geändert",
                   abgebrochen: "Durchgang abgebrochen", rueckruf: "Rückruf angelegt", rueckruf_beendet: "Rückruf beendet",
                   freigabe_erteilt: "Freigabe erteilt", freigabe_geaendert: "Freigabe geändert",
                   freigabe_entzogen: "Freigabe entzogen", freigabe_entfernt: "Freigabe entfernt",
                   freigabe_abgelaufen: "Freigabe abgelaufen",
                   zugeordnet: "Zuordnung geändert", zuordnung_geloest: "Zuordnung geändert",
                   bestandsimport: "Bestandsimport", nacharbeit_uebernommen: "Nacharbeit übernommen",
                   nacharbeit_verworfen: "Nacharbeit verworfen", wiki: "Prüfanleitung (Strömipedia) geändert",
                   mangel_gemeldet: "Mangel gemeldet", antrag_gestellt: "Änderung beantragt",
                   antrag_bestaetigt: "Änderung bestätigt (Antrag)", antrag_abgelehnt: "Änderungsantrag abgelehnt",
                   antrag_zurueckgezogen: "Änderungsantrag zurückgezogen", laenge_geaendert: "Länge geändert",
                   // Altbestand vor Schritt 26 (Rückbau der Set-Funktion): Aktionen der früheren Sets, nur zum Lesen.
                   set_angelegt: "Set mit Teilen angelegt", stueckliste: "Stückliste geändert",
                   set_gesperrt: "mit dem Set gesperrt", set_frei: "mit dem Set freigegeben", teil_gesperrt: "Teil gesperrt",
                   teil_entnommen: "Teil entnommen", teil_eingesetzt: "Teil eingesetzt", teil_geloescht: "Teil gelöscht",
                   entnommen: "aus dem Set entnommen", set_lauf_eroeffnet: "Set-Prüfung begonnen",
                   set_lauf_abgebrochen: "Set-Prüfung abgebrochen", set_geprueft: "Set geprüft",
                   set_lauf_geaendert: "Set-Prüfung aus dem Durchgang gelöst",
                   eingesetzt: "in ein Set eingesetzt", aus_set_geloest: "aus dem Set gelöst (Set aufgelöst)",
                   bestandteil_ersetzt: "Bestandteil ersetzt", produkt_geaendert: "Produkt geändert",
                   stueckliste_uebertragen: "Stückliste übertragen", nicht_in_stueckliste: "steht nicht mehr in der Stückliste des Sets",
                   anzahl_verringert: "Anzahl in der Stückliste des Sets verringert – ein Stück zu entnehmen",
                   set_rueckbau: "Set aufgelöst – die Teile sind eigene Artikel (Schritt 26)",
                   // Schritt 25: Bestandteil-Liste eines Produkts und Seriennummern der Bestandteile am Artikel
                   bestandteile: "Bestandteile geändert", bestandteil_nummern: "Seriennummern der Bestandteile geändert" };
  const RECHT = { lesen: "lesen", pruefen: "prüfen", verwalten: "verwalten" };
  const ENTITAET = { item: "Artikel", product: "Produkt", document: "Dokument", form: "Formular", folder: "Ordner",
                     category: "Kategorie", user: "Konto", inspection: "Prüfung", round: "Durchgang", request: "Produktmeldung" };

  /* Warum hier nicht geprüft werden kann – als HTML. obj: der Ordner, Artikel oder die Prüfung (mit „darf“); ohne obj
     gilt die Frage für das ganze Konto (Seite „Prüfungen“). Prüfen braucht seit Phase 2 dreierlei: das Häkchen
     „Prüfer“ (setzt die Plattform-Verwaltung in der Leitstelle), die Urkundennummer (trägt der Prüfer selbst im Profil ein)
     und eine Prüffreigabe für den Ordner (vergibt dessen Materialwart). Wer das Häkchen schon hat, dem fehlt vielleicht
     nur die Nummer: Er bekommt den Weg dorthin als Link. Wer qualifiziert ist, dem fehlt die Prüffreigabe. */
  const URKUNDE_IM_PROFIL = 'Du bist als Prüfer eingetragen, aber deine Urkundennummer fehlt noch – trage sie im '
    + '<a href="/profil#unterschrift">Profil unter „Urkundennummer und Unterschrift“</a> ein, dann kannst du prüfen.';
  const KEINE_PRUEFFREIGABE = "Für diesen Ordner hast du keine Prüffreigabe – die vergibt der Materialwart unter Ordner → Bearbeiten → Freigaben.";
  const pruefHinweis = (obj) => (DARF.qualifiziert
    ? (obj ? KEINE_PRUEFFREIGABE : "Du hast noch keine gültige Prüffreigabe – die vergibt der Materialwart eines Ordners unter Ordner → Bearbeiten → Freigaben.")
    : DARF.pruefer_haekchen ? URKUNDE_IM_PROFIL
      : "Prüfen dürfen nur Prüfer mit Urkundennummer und Prüffreigabe: Das Häkchen „Prüfer“ setzt die Plattform-Verwaltung "
        + "in der Leitstelle, die Urkundennummer trägt der Prüfer selbst in seinem Profil ein, die Prüffreigabe für einen "
        + "Ordner vergibt dessen Materialwart.");

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
  // grenzen: {min, max} als ISO-Tag (nur „tag“) – datumWert lehnt Tage davor bzw. danach am Feld ab (Nachbesserung P4-L2b,
  // Browser B3: „max“ gibt es an einem Textfeld nicht).
  const datumFeld = (id, iso, art, grenzen) => `<input type="text" id="${id}" class="mat-datum" data-art="${art}" inputmode="numeric" autocomplete="off"
    maxlength="${art === "monat" ? 7 : 10}" placeholder="${art === "monat" ? "MM/JJJJ" : "TT.MM.JJJJ"}" value="${esc(datumAnzeige(iso, art))}"${grenzen && grenzen.min ? ` data-min="${esc(grenzen.min)}"` : ""}${grenzen && grenzen.max ? ` data-max="${esc(grenzen.max)}"` : ""}>`;
  // ISO ('YYYY-MM' bzw. 'YYYY-MM-DD'), "" für leer – oder ein Fehler: Hinweis aufs Format, wenn es nicht passt; „gibt es
  // nicht“, wenn das Format stimmt, der Tag aber nicht (31.02.). Das Feld trägt aria-invalid und die Klasse „ungueltig“
  // (Browserprüfung P4-L1, V7) – Vorleser sagen damit am Feld, dass es nicht stimmt.
  function datumWert(feld, name) {
    const falsch = (text) => {
      feld.setAttribute("aria-invalid", "true");
      feld.classList.add("ungueltig");
      return new Error(`„${name}“: ${text}`);
    };
    const s = feld.value.trim();
    feld.removeAttribute("aria-invalid");
    if (!s) return "";
    if (feld.dataset.art === "monat") {
      const m = s.match(/^(\d{1,2})[/.](\d{4})$/);
      if (!m) throw falsch("bitte als MM/JJJJ angeben, z. B. 03/2024.");
      if (+m[1] >= 1 && +m[1] <= 12) return `${m[2]}-${m[1].padStart(2, "0")}`;
      throw falsch(`${s} gibt es nicht – der Monat liegt zwischen 01 und 12.`);
    }
    const m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (!m) throw falsch("bitte als TT.MM.JJJJ angeben, z. B. 17.03.2024.");
    const d = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
    if (d.getUTCFullYear() === +m[3] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[1]) {
      const iso = `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
      if (feld.dataset.max && iso > feld.dataset.max) throw falsch(`spätestens ${feld.dataset.max === isoHeute(0) ? "heute, " : ""}${fmtTag(feld.dataset.max)}.`);
      if (feld.dataset.min && iso < feld.dataset.min) throw falsch(`frühestens ${fmtTag(feld.dataset.min)}.`);
      return iso;
    }
    throw falsch(`den ${s} gibt es nicht.`);
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
  /* Ein Name oder eine Anmeldung (E-Mail) hinter „von“, „bei“ oder in einem Personenfeld als Einheit (Nachtrag 2 vom
     27.10.2026): rutscht als Ganzes in die nächste Zeile statt nach „demo-“ oder „@“ zu brechen – nur ein Name, der
     länger ist als die ganze Zeile, bricht in sich (material.css, .mat-name). Der Text bleibt unverändert kopierbar. */
  const person = (n) => `<span class="mat-name">${esc(n)}</span>`;
  /* Info zu einem Begriff: das gekringelte „i“ hinter dem Begriff statt eines Erklärsatzes darunter – seit 27.10.2026
     app-weit in common.js (S.info, Verhalten und Aussehen dort bzw. in app.css, .info). */
  const infoKnopf = S.info;
  const PRUEFSUMME_INFO = 'Die Prüfsumme steht im Fuß jeder Seite des PDFs. Ob eine Datei unverändert ist, zeigt die <a href="/materialablage/pruefen">Prüfseite</a>.';
  const statusMarke = (s, gross) => `<span class="mat-status s-${esc(s)}${gross ? " gross" : ""}">${esc(STATUS[s] || s)}</span>`;
  const demoMarke = (x) => (x ? '<span class="mat-demo" title="DEMO – nicht für echte Prüfungen">DEMO</span>' : "");
  // Das Schloss vor „Gesperrt“ und „Ausgesondert“: grau wie die Klapp-Dreiecke daneben und ohne Leerzeichen, das im
  // Link mit unterstrichen würde – den Abstand hält der Rand (mat-schloss, material.css).
  const schloss = (o) => (o.system_kind ? '<span class="mat-schloss" aria-hidden="true">🔒</span>' : "");
  // Banner an Artikel und Prüfung: DEMO ist ein Artikel eines DEMO-Produkts oder mit Heimat in einem DEMO-Ordner
  // (bestand.demo_sql) – auch ein echtes Katalogprodukt im Beispielbestand.
  const DEMO_ARTIKEL = "DEMO – nicht für echte Prüfungen. Dieser Artikel gehört zu den Demodaten.";
  const leer = (text) => `<p class="leerzustand">${esc(text)}</p>`;
  // Produktfoto in der Produktwahl (Artikel anlegen: gewähltes Produkt und Treffer der Produktsuche): die Vorschau,
  // antippbar – sie öffnet die Webfassung groß (bildZeigen), dort führt „Original“ zur hochgeladenen Datei. Die Lupe
  // unten rechts zeigt auch am Telefon, wo es keinen Mauszeiger gibt, dass es größer geht. Ohne Bild: nichts.
  const LUPE_KLEIN = `<svg viewBox="0 0 24 24" width="12" height="12" focusable="false"><circle cx="10.5" cy="10.5" r="6.5"
    fill="none" stroke="currentColor" stroke-width="2.8"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"/></svg>`;
  const produktFoto = (p) => (p.bild && p.vorschau ? bildLink(p.bild, p.original, `Produktbild ${produktName(p)}`, null,
    `<span class="mat-produktfoto"><img class="mat-mini" src="${esc(p.vorschau)}" alt=""><span class="mat-lupe-marke" aria-hidden="true">${LUPE_KLEIN}</span></span>`,
    `Produktfoto groß anzeigen: ${produktName(p)}`) : "");
  const fokus = (el) => { if (el && !window.matchMedia("(pointer: coarse)").matches) el.focus(); };
  const EIN = "\u00a0\u00a0\u00a0";          // Einrückung je Ebene in Auswahllisten
  const groesse = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round((b || 0) / 1024))} kB`);

  /* --- Bausteine der anderen Pakete (Phase 2) --------------------------------------------------------------------
     freigaben.js (window.MatFreigaben) und global.js (window.MatGlobal) stehen in seite.html hinter dieser Datei. Ihre
     Objekte gibt es erst, wenn die Seite ganz gelesen ist – wer sie beim Zeichnen braucht, wartet darauf (baustein).
     Fehlt einer, bleibt die Stelle leer. */
  const seiteGelesen = new Promise((fertig) => {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => fertig(), { once: true });
    else fertig();
  });
  const baustein = async (name) => { await seiteGelesen; return window[name] || null; };

  /* --- Ordnerbaum, wie ihn das Konto sieht (Phase 2) ------------------------------------------------------------
     Einmal je Seite geladen und geteilt (Leiste, Ordnerwahl, Pfade); wer den Baum ändert, lädt ihn neu
     (ordnerBaum(true)). Er enthält nur, was das Konto sieht, und darüber Pfad-Knoten („nur_pfad“): Oberordner ohne
     eigene Freigabe, nur der Weg zu den eigenen – grau, ohne Zahl, ohne Link (der Server antwortet dort 404). */
  const OHNE_FREIGABE = "Hier hast du keine Freigabe – der Ordner steht nur als Weg zu deinen da.";
  let baumLauf = null;
  let baumIndex = {};
  function ordnerBaum(neu) {
    if (!baumLauf || neu) {
      const lauf = api(`${API}/ordner`).then((d) => {
        if (lauf === baumLauf) { baumIndex = {}; d.ordner.forEach((o) => { baumIndex[o.id] = o; }); }
        return d.ordner;
      });
      baumLauf = lauf;
      lauf.catch(() => { if (baumLauf === lauf) baumLauf = null; });
    }
    return baumLauf;
  }
  // Ein Ordner, den das Konto öffnen kann – kein Pfad-Knoten. Solange der Baum fehlt: ja (der Server entscheidet).
  const offenbar = (id) => !(baumIndex[id] && baumIndex[id].nur_pfad);
  const pfadKnoten = (name) => `<span class="mat-pfadknoten" title="${esc(OHNE_FREIGABE)}">${esc(name)}</span>`;
  // Ein Glied eines Pfads ({id, name}): verlinkt – oder grau, wenn es nur ein Pfad-Knoten ist.
  const pfadGlied = (o) => (offenbar(o.id) ? `<a href="/materialablage/ordner/${o.id}">${esc(o.name)}</a>` : pfadKnoten(o.name));
  /* Brotkrumen (.mat-pfad) aus fertigen Gliedern (HTML): Der Schrägstrich hängt am folgenden Glied – am Telefon blieb er
     sonst allein am Ende der Zeile stehen, und das letzte Glied („Gurte“) stand mit seiner Wortbreite allein darunter
     (Browserprüfung vor dem Merge, B-1; material.css). Auch das erste Glied steht in einem .mat-pfad-glied: Am Telefon
     bleiben die Brotkrumen eine Zeile, ein langes Glied endet mit „…“ (Reste vor dem finalen Test, 2). Ab vier Gliedern
     stehen dort nur das erste und das letzte, dazwischen der Knopf „…“ (.mat-pfad-luecke) – er zeigt den ganzen Pfad. */
  function pfadHtml(glieder) {
    const html = glieder.filter(Boolean).map((g, i) => `<span class="mat-pfad-glied">${i ? "/ " : ""}${g}</span>`);
    if (html.length > 3) html.splice(1, 0, '<span class="mat-pfad-glied mat-pfad-luecke">/ <button type="button" class="mat-pfad-mehr" aria-label="Ganzen Pfad zeigen">…</button></span>');
    return html.join(" ");
  }
  // Die nächste Gliederung über einem Ordner (oder er selbst) – wie bestand.gliederung_von auf dem Server.
  function gliederungVon(id) {
    const gesehen = new Set();
    for (let o = baumIndex[id]; o && !gesehen.has(o.id); o = baumIndex[o.parent_id]) {
      gesehen.add(o.id);
      if (o.kind === "gliederung" && !o.system_kind) return o;
    }
    return null;
  }
  // Verwaltet das Konto diesen Ordner? Ohne Ordner (oberste Ebene) nur die Material-Verwaltung.
  const verwaltet = (o) => (o ? Boolean(o.darf && o.darf.verwalten) : Boolean(DARF.alles));
  /* Wechselt ein Verschieben die Gliederung? quelle: Heimat des Artikels bzw. alter Oberordner. Über Gliederungsgrenzen
     verschiebt nur, wer beide Gliederungen verwaltet (Bauentwurf 1.7 Nr. 2) – die Ordnerwahl bietet andere Ziele gar
     nicht erst an. */
  function wechsel(quelle, ziel) {
    const a = gliederungVon(quelle), b = gliederungVon(ziel);
    return (a ? a.id : null) !== (b ? b.id : null);
  }
  const wechselErlaubt = (quelle, ziel) => !wechsel(quelle, ziel)
    || (verwaltet(gliederungVon(quelle)) && verwaltet(gliederungVon(ziel)));

  /* --- Gerüst -------------------------------------------------------------------------------- */
  const NAV = { dashboard: "dashboard", pruefungen: "pruefungen", bestand: "bestand", ordner: "bestand", artikel: "bestand",
                artikel_neu: "bestand", katalog: "katalog", produkt: "katalog", formular: "katalog", meldungen: "katalog", suche: "",
                pruefung: "pruefungen", pruefung_neu: "pruefungen", durchgang: "pruefungen", durchgaenge: "pruefungen",
                bestandsimport: "bestand", bericht: "bestand", antraege: "bestand" };
  $$(".mat-nav a").forEach((a) => a.classList.toggle("aktiv", a.dataset.nav === NAV[ANSICHT]));
  if (ANSICHT === "suche" && DATEN.q) $(".mat-suche input").value = DATEN.q;
  // Ohne Freigabe im Bestand (Mitglied ohne Freigabe, Prüfer ohne Prüffreigabe) fallen nur „Prüfungen“ und „Bestand“ weg. Die
  // Nummernsuche bleibt: Über sie erreicht jeder mit Zugang die globale Seriennummernsuche.
  if (!DARF.lesen) $$('.mat-nav a[data-nav="pruefungen"], .mat-nav a[data-nav="bestand"]').forEach((el) => el.remove());

  /* Modulnavigation (Lieferung 5): Passen „☰ Ordner“, die Reiter und das Suchfeld nicht in eine Zeile, stand die
     Navigation am Telefon in drei Zeilen – über 200 px, bevor nach einem QR-Scan die Inventarnummer kam. Dann wird sie
     einzeilig (.eng): Die Reiter rollen seitlich (der Rand blendet aus, solange dort noch einer steht, der aktive
     wird ins Bild gerollt), die Nummernsuche wartet hinter der Lupe und öffnet als eigene Zeile darunter – auch auf der
     Übersicht und im Bestand (Entscheidung des Nutzers, Nachtrag V4 vor dem Merge: „am Telefon zu, hinter der Lupe“;
     bis dahin stand sie dort gleich offen). Offen steht sie nur, wenn sie schon einen Begriff trägt – auf der
     Trefferseite sähe man sonst nicht, wonach gesucht wurde. Am Rechner (eine Zeile) steht das Feld immer da. Reicht der
     Platz auch so nicht, zeigt „☰“ nur noch das Zeichen, und die Reiter bekommen eine eigene Zeile (.enger, material.css). */
  const matNav = $(".mat-nav");
  const reiter = $(".mat-reiter");
  const lupe = $("#mat-lupe");
  const sucheForm = $(".mat-nav .mat-suche");
  if (matNav && sucheForm && $("input", sucheForm).value) matNav.classList.add("suche-offen");
  function rollHinweis() {
    if (!reiter) return;
    const rest = reiter.scrollWidth - reiter.clientWidth - reiter.scrollLeft;
    reiter.classList.toggle("rollt-links", reiter.scrollLeft > 2);
    reiter.classList.toggle("rollt-rechts", rest > 2);
  }
  // Eine Zeile, wenn kein sichtbares Element unterhalb des ersten beginnt – auch kein Reiter: Im Katalog am Telefon
  // stehen nur noch die Reiter in der Navigation (ohne Nummernsuche, „☰“ in der Suchzeile), die sonst umbrächen.
  function einzeilig() {
    const kinder = [...matNav.children].flatMap((el) => (el === reiter ? [...reiter.children] : [el])).filter((el) => el.offsetParent);
    if (kinder.length < 2) return true;
    const erstes = kinder[0].getBoundingClientRect();
    return kinder.every((el) => el.getBoundingClientRect().top < erstes.bottom - 4);
  }
  let navBreite = -1;
  function navAnordnen() {
    if (!matNav || !reiter) return;
    navBreite = matNav.clientWidth;
    matNav.classList.remove("eng", "enger");
    if (lupe) lupe.hidden = true;
    if (!einzeilig()) {
      matNav.classList.add("eng");
      if (lupe) lupe.hidden = false;
      if (reiter.scrollWidth > reiter.clientWidth + 1) matNav.classList.add("enger");
    }
    if (lupe) lupe.setAttribute("aria-expanded", String(matNav.classList.contains("suche-offen")));
    const aktiv = $("a.aktiv", reiter);
    if (aktiv && reiter.scrollWidth > reiter.clientWidth) {
      const r = reiter.getBoundingClientRect();
      const a = aktiv.getBoundingClientRect();
      if (a.right > r.right - 24) reiter.scrollLeft += a.right - r.right + 32;
      else if (a.left < r.left + 24) reiter.scrollLeft -= r.left - a.left + 32;
    }
    rollHinweis();
  }
  if (matNav && reiter) {
    reiter.addEventListener("scroll", rollHinweis, { passive: true });
    if (lupe) lupe.addEventListener("click", () => {
      const auf = !matNav.classList.contains("suche-offen");
      matNav.classList.toggle("suche-offen", auf);
      lupe.setAttribute("aria-expanded", String(auf));
      if (auf) $("input", sucheForm).focus();          // getippt, um zu suchen: hier darf die Tastatur kommen
    });
    // Escape im Feld (ohne offene Vorschläge – die schließt suche.js zuerst) klappt die Suche wieder ein.
    if (sucheForm) sucheForm.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || !matNav.classList.contains("eng") || !lupe) return;
      matNav.classList.remove("suche-offen");
      lupe.setAttribute("aria-expanded", "false");
      lupe.focus();
    });
    const breiteGeaendert = () => { if (matNav.clientWidth !== navBreite) navAnordnen(); };
    if (window.ResizeObserver) new ResizeObserver(breiteGeaendert).observe(matNav);
    else window.addEventListener("resize", breiteGeaendert);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(navAnordnen);
  }

  // Klicks auf [data-act] gehen an die Aktionen der gerade gezeichneten Ansicht. Was aus dem Wiki eingeblendet ist
  // (Prüfanleitung, .mat-anleitung), löst nie eine Aktion aus – auch dann nicht, wenn dort ein Element data-act trüge:
  // Die Reinigung nimmt es weg und der Schatten schirmt ab, das hier ist der dritte Riegel (Bauentwurf L3 3.5.2 Nr. 7).
  let aktionen = {};
  inhalt.addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    if (!b || !inhalt.contains(b) || !aktionen[b.dataset.act]) return;
    if (b.closest(".mat-anleitung")) return;
    if (b.tagName === "A" || b.tagName === "BUTTON") e.preventDefault();
    // Den Fokus nach Esc oder „Abbrechen“ gibt dialog() oben zurück (auf den Menüknopf, wenn der Eintrag in einem
    // details.mat-menue stand) – auch wenn der Dialog erst nach einem Laden öffnet (B5 P4-L2, B2 vor dem Merge).
    aktionen[b.dataset.act](b, e);
  });
  // „…“ in gekürzten Brotkrumen (pfadHtml): den ganzen Pfad zeigen, der Fokus geht auf das erste Glied, das dazukam.
  inhalt.addEventListener("click", (e) => {
    const k = e.target.closest(".mat-pfad-mehr");
    if (!k || !inhalt.contains(k)) return;
    const pfad = k.closest(".mat-pfad");
    pfad.classList.add("offen");
    const ziel = pfad.querySelector(".mat-pfad-luecke ~ .mat-pfad-glied a");
    if (ziel) ziel.focus();
  });
  // „Sortieren nach“ über den Karten (kartenKopf): dieselbe Aktion wie ein Klick auf den Spaltenkopf.
  inhalt.addEventListener("change", (e) => {
    if (e.target.closest(".mat-anleitung")) return;
    const s = e.target.closest("select[data-sortwahl]");
    if (s && aktionen.sortieren) aktionen.sortieren({ dataset: { feld: s.value } }, e);
    // Filter „Zugeordnet an …“ im Ordner.
    const p = e.target.closest("select[data-personwahl]");
    if (p && aktionen.person) aktionen.person(p, e);
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
     aufgeklappt, alles einen Klick entfernt. Unter 1024 px ist die Leiste eine Schublade hinter
     „☰ Ordner“ bzw. „☰ Kategorien“ (wie im Wiki), auf einem Doppelbildschirm füllt sie die linke Hälfte. Nicht auf
     der Seite „Bestand“: dort ist der Ordnerbaum selbst der Inhalt. Auf- und Zuklappen merkt sich der Browser, je Baum getrennt. */
  const KATALOG_ANSICHTEN = new Set(["katalog", "produkt", "formular", "meldungen"]);
  const MIT_LEISTE = new Set(["dashboard", "pruefungen", "ordner", "artikel", "artikel_neu", "suche", "pruefung",
                              "pruefung_neu", "durchgang", "durchgaenge", "katalog", "produkt", "formular", "meldungen", "bestandsimport", "bericht",
                              "antraege"]);
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
        return `${knopf}<a href="/materialablage/katalog?kategorie=${o.id}" data-kat="${o.id}" ${markiert} title="${esc(o.name)}${o.norm ? ` · ${esc(o.norm)}` : ""}">${esc(o.name)}</a>
          <span class="mat-side-anzahl" title="Produkte (mit Unterkategorien)">${summe(o.id)}</span>`;
      }
      // Pfad-Knoten: nur der Name, grau, ohne Zahl und ohne Link.
      if (o.nur_pfad) return `${knopf}<span class="mat-pfadknoten" title="${esc(OHNE_FREIGABE)}">${esc(o.name)}</span>`;
      const z = o.zaehlung || {};
      const rot = (z.ueberfaellig || 0) + (z.lebensdauer || 0);
      const zahl = o.system_kind ? `<span class="mat-side-anzahl">${Object.values(z).reduce((a, b) => a + b, 0)}</span>`
        : `${rot ? `<span class="mat-zahl s-ueberfaellig" title="überfällig oder Lebensdauer erreicht">${rot}</span>` : ""}${z.neu ? `<span class="mat-zahl s-neu" title="neu – Eingangsprüfung offen">${z.neu}</span>` : ""}`;
      return `${knopf}<a href="/materialablage/ordner/${o.id}" ${markiert} title="${esc(o.name)}${o.teilweise ? " – nur deine Artikel" : ""}">${schloss(o)}${esc(o.name)}</a>${zahl}`;
    };
    const zweig = (pid, tiefe) => (kinder[pid] || []).map((o) => {
      const hat = !!kinder[o.id];
      const auf = hat && (weg.has(o.id) || (o.id in klapp ? klapp[o.id] : tiefe === 0));
      return `<li class="${hat ? (auf ? "" : "collapsed") : "leaf"}${o.system_kind ? " system" : ""}">
        <div class="row">${zeile(o, hat, auf)}</div>${hat ? `<ul>${zweig(o.id, tiefe + 1)}</ul>` : ""}</li>`;
    }).join("");
    const alle = LEISTE_KATALOG ? `<li class="leaf"><div class="row"><button class="tg" type="button" tabindex="-1" aria-hidden="true"></button>
      <a href="/materialablage/katalog" data-kat="" class="${ANSICHT === "katalog" && !leisteAktiv ? "active" : ""}">alle Kategorien</a></div></li>` : "";
    ziel.innerHTML = `<ul class="tree mat-tree">${alle}${zweig(0, 0)}</ul>`;
  }

  async function leisteLaden() {
    if (!leiste || !MIT_LEISTE.has(ANSICHT) || !(DARF.lesen || LEISTE_KATALOG)) return;
    document.getElementById("mat-shell").classList.add("mit-leiste");
    navAnordnen();                     // „☰ Ordner“ steht jetzt in der Zeile
    leiste.hidden = false;
    if (LEISTE_KATALOG) {
      const kopf = $(".mat-side-kopf a", leiste);
      kopf.textContent = "Kategorien";
      kopf.href = "/materialablage/katalog";
      leiste.setAttribute("aria-label", "Kategorien");
      $("#mat-side-zu").setAttribute("aria-label", "Kategorien schließen");
      if (leisteAuf) $(".mat-side-auf-text", leisteAuf).textContent = " Kategorien";
    }
    try { leisteDaten = LEISTE_KATALOG ? await kategorienLaden() : await ordnerBaum(); }
    catch (e) { $("#mat-baumnav").innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    leisteZeichnen();
  }
  // Jede Ansicht meldet hier ihren Ordner (Ordner, Artikel, Prüfung, Durchgang) bzw. ihre Kategorie (Katalog,
  // Produkt, Formular) – die Leiste markiert ihn.
  function leisteMarkieren(id) { leisteAktiv = id || null; leisteZeichnen(); }
  // Schublade unter 1024 px (Tablet quer hat die Leiste daneben, Lieferung 5) – außer auf einem Doppelbildschirm mit
  // zwei Hälften nebeneinander: Dort steht sie fest in der linken (material.css, Abschnitt Geräte: shell).
  const schublade = window.matchMedia("(max-width: 1023px)");
  const zweiHaelften = window.matchMedia("(horizontal-viewport-segments: 2)");
  const alsSchublade = () => schublade.matches && !zweiHaelften.matches;
  /* Im Katalog wandert „☰ Kategorien“, solange die Leiste eine Schublade ist, links in die Suchzeile über der
     Produktliste (Wunsch vom 26.10.2026): Die klebt beim Scrollen oben, die Modulnavigation rollt weg – wer weit
     unten war, kam sonst nicht mehr an die Kategorien. Derselbe Knopf, kein zweiter (Handler, aria-expanded und die
     Fokus-Rückkehr bleiben); dort nur „☰“, der Name „Kategorien“ bleibt zum Vorlesen (material.css). Breiter (Leiste
     daneben) kehrt er in die Navigation zurück. Der Katalog ruft das nach jedem Zeichnen der Suchzeile. */
  const knopfInSuchzeile = () => Boolean(leisteAuf && leisteAuf.closest(".mat-suchzeile"));
  function leisteKnopfSetzen() {
    if (!leisteAuf || !matNav || !leiste) return;
    const zeile = ANSICHT === "katalog" && alsSchublade() ? $(".mat-suchzeile", inhalt) : null;
    const ziel = zeile || matNav;
    if (leisteAuf.parentNode !== ziel) {
      const fokus = document.activeElement === leisteAuf;
      ziel.prepend(leisteAuf);
      if (fokus) leisteAuf.focus({ preventScroll: true });
    }
    navAnordnen();                     // ohne den Knopf hat die Navigation mehr Platz
  }
  // Als Schublade ist die geschlossene Leiste nur aus dem Bild geschoben – „inert“ nimmt sie auch aus der
  // Tab-Reihenfolge und dem Vorlesen. Neben dem Inhalt (breiter Bildschirm) ist sie immer bedienbar.
  function leisteInert() { if (leiste) leiste.inert = alsSchublade() && !leiste.classList.contains("open"); }
  let leisteAufVon = null;             // der Knopf, der die Schublade geöffnet hat: „☰ Ordner“ oder „Filter (n)“
  function leisteZu(fokusZurueck) {
    if (!leiste) return;
    const war = leiste.classList.contains("open");
    leiste.classList.remove("open");
    if (leisteAuf) leisteAuf.setAttribute("aria-expanded", "false");
    leisteInert();
    const zurueck = leisteAufVon && leisteAufVon.isConnected ? leisteAufVon : leisteAuf;
    leisteAufVon = null;
    if (war && fokusZurueck && zurueck) zurueck.focus();
  }
  // Die Schublade öffnen – von „☰ Ordner“ (Fokus auf den markierten Ordner) oder von „Filter (n)“ über der Liste
  // (Wunsch vom 25.10.2026, F4: dieselbe Schublade, gerollt zu den Filtern, Fokus auf deren Titel).
  function leisteOeffnen(von, ziel) {
    leiste.classList.add("open");
    if (leisteAuf) leisteAuf.setAttribute("aria-expanded", "true");
    leisteInert();
    leisteAufVon = von || leisteAuf;
    if (ziel) { ziel.scrollIntoView({ block: "start" }); ziel.focus({ preventScroll: true }); return; }
    const a = $("a.active", leiste) || $("a", leiste);
    if (a) a.focus({ preventScroll: true });
  }
  /* Wischen nach links schließt die Schublade – auf der Leiste wie auf der Abdunklung daneben. Die Leiste folgt dabei
     dem Finger; reicht der Weg nicht (ein Viertel ihrer Breite, höchstens 80 px), springt sie zurück. Wer senkrecht
     wischt, rollt wie bisher den Baum. */
  function leisteWischen() {
    let zug = null;
    document.addEventListener("touchstart", (e) => {
      zug = leiste.classList.contains("open") && e.touches.length === 1
        ? { x: e.touches[0].clientX, y: e.touches[0].clientY, richtung: null, dx: 0 } : null;
    }, { passive: true });
    document.addEventListener("touchmove", (e) => {
      if (!zug) return;
      const dx = e.touches[0].clientX - zug.x;
      const dy = e.touches[0].clientY - zug.y;
      if (!zug.richtung && Math.abs(dx) + Math.abs(dy) > 10) zug.richtung = Math.abs(dx) > Math.abs(dy) ? "quer" : "hoch";
      if (zug.richtung !== "quer") return;
      zug.dx = Math.min(0, dx);
      leiste.style.transition = "none";
      leiste.style.transform = `translateX(${zug.dx}px)`;
    }, { passive: true });
    const ende = () => {
      if (!zug) return;
      const weit = zug.richtung === "quer" && zug.dx < -Math.min(80, leiste.offsetWidth / 4);
      zug = null;
      leiste.style.transition = "";
      leiste.style.transform = "";
      if (weit) leisteZu(knopfInSuchzeile());           // der Knopf klebt im Bild – Fokus zurück, ohne zu rollen
    };
    document.addEventListener("touchend", ende);
    document.addEventListener("touchcancel", ende);
  }
  if (leiste) {
    leiste.addEventListener("click", (e) => {
      // Das Filtermenü unter dem Baum (nur die Ordneransicht füllt es) wirkt wie Knöpfe im Inhalt: an die Aktionen der
      // Ansicht.
      const fb = e.target.closest("#mat-side-filter [data-act]");
      if (fb && aktionen[fb.dataset.act]) {
        e.preventDefault();
        aktionen[fb.dataset.act](fb, e);
        return;
      }
      // Im Katalog wechselt eine Kategorie ohne Neuladen – Suche und Sortierung bleiben stehen.
      const kat = e.target.closest("a[data-kat]");
      if (kat && katalogWahl && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
        e.preventDefault();
        katalogWahl(kat.dataset.kat ? +kat.dataset.kat : null, alsSchublade());
        leisteZu(knopfInSuchzeile());
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
    leiste.addEventListener("change", (e) => {
      const p = e.target.closest("#mat-side-filter select[data-personwahl]");
      if (p && aktionen.person) aktionen.person(p, e);
    });
    $("#mat-side-zu").addEventListener("click", () => leisteZu(true));
    if (leisteAuf) leisteAuf.addEventListener("click", () => {
      if (leiste.classList.contains("open")) leisteZu();
      else leisteOeffnen(leisteAuf);
    });
    // Tippen neben die offene Schublade oder Escape schließt sie (nicht der Knopf, der sie eben geöffnet hat).
    document.addEventListener("click", (e) => {
      if (leiste.classList.contains("open") && !leiste.contains(e.target) && !(leisteAuf && leisteAuf.contains(e.target))
          && !e.target.closest("[data-leiste-auf]")) leisteZu();
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") leisteZu(true); });
    // Wechselt die Darstellung (Tablet gedreht, Fold auf- oder zugeklappt), schließt eine offene Schublade – sonst
    // stand sie beim Zurückwechseln samt Abdunklung wieder offen da.
    const umschalten = () => { leisteZu(); leisteInert(); leisteKnopfSetzen(); };
    // Beim Verlassen der Seite zu: Zurück aus dem Verlauf (bfcache) stand sie sonst samt Abdunklung offen da – im Katalog
    // wie im Bestand (Browserprüfung vor dem Merge, V3).
    window.addEventListener("pagehide", () => leisteZu());
    schublade.addEventListener("change", umschalten);
    zweiHaelften.addEventListener("change", umschalten);
    leisteWischen();
    leisteInert();
  }

  async function zeigen(fn) {
    try { await fn(); }
    catch (e) {
      // Fremdes oder nicht (mehr) Erlaubtes (404, 403): die Meldung des Servers im Klartext und ein Weg zurück.
      inhalt.innerHTML = e.status === 403 || e.status === 404
        ? `<p class="notice">${esc(e.message)}</p><p><a class="btn secondary" href="/materialablage">Zur Übersicht</a></p>`
        : `<p class="error">${esc(e.message)}</p>`;
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
  // da: der Eintrag hat dieses Feld auf dieser Seite (vorher/nachher) – ein leeres „bis“ heißt dann „unbefristet“.
  /* Ein Listeneintrag im Journal: Text bleibt Text. Objekte erscheinen als Satz statt als „[object Object]“: die
     Positionen einer Bestandteil-Liste ({bezeichnung, anzahl}), die Seriennummern der Bestandteile ({bestandteil,
     seriennummer}) und – Altbestand vor Schritt 26 – die Teile früherer Sets ({inventory_no, serial_no, bestandteil},
     „vorhanden“: eingesetzter vorhandener Artikel) und Stücklisten-Positionen mit „einzeln“ und „austausch“. */
  function listenWert(x) {
    if (!x || typeof x !== "object") return x;
    if (x.inventory_no) return `${x.inventory_no}${x.serial_no ? ` (SN ${x.serial_no})` : ""}${x.bestandteil ? ` – ${x.bestandteil}` : ""}${x.vorhanden ? ", vorhandener Artikel" : ""}`;
    // Seriennummer eines Bestandteils (Schritt 25) – wie beschriftung._listen_wert.
    if (x.seriennummer !== undefined && x.bestandteil !== undefined) return `${x.bestandteil}: ${x.seriennummer || "–"}`;
    if (x.bezeichnung !== undefined) {
      return `${x.anzahl || 1} × ${x.bezeichnung}${x.einzeln ? ", einzeln geführt" : ""}${x.austausch ? `, Austausch: ${SET_WERTE.austausch[x.austausch] || x.austausch}` : ""}`;
    }
    return JSON.stringify(x);
  }
  function wert(v, feld, da) {
    if (feld === "konto") return v && v.name ? esc(v.name) : '<span class="muted">–</span>';    // Kontoverweis, beim Lesen aufgelöst
    if (feld === "bis" && da && (v === null || v === undefined || v === "")) return "unbefristet";
    if (v === null || v === undefined || v === "") return '<span class="muted">–</span>';
    if (feld === "recht") return esc(RECHT[v] || v);
    if (Array.isArray(v)) return v.length ? `<ul class="mat-wertliste">${v.map((x) => `<li>${esc(listenWert(x))}</li>`).join("")}</ul>` : "–";
    if (typeof v === "boolean" || ((feld === "serial_generated" || feld === "active" || feld === "mat_pruefer" || feld === "mat_katalog" || feld === "reminders_off" || feld === "aus_nacharbeit" || feld === "items_have_length") && (v === 0 || v === 1))) return v ? "ja" : "nein";
    if (feld === "length_m" && typeof v === "number") return esc(laengeText(v));
    if (feld === "material_kind" || feld === "default_material_kind") return esc(MATERIALART[v] || v);
    if (feld === "kind" || feld === "art") return esc(PRUEFART_KURZ[v] || ORDNERART[v] || ANHANGART[v] || v);
    if (feld === "result" || feld === "ergebnis") return esc(ERGEBNIS[v] || v);
    if (["pruefung", "aussonderung", "basis", "empfehlung", "berichtigung", "berichtigt"].includes(feld) && Number.isInteger(v)) return `<a href="/materialablage/pruefung/${v}">Nr. ${v}</a>`;
    if (/sha256$/.test(feld)) return `<span class="mat-hash">${esc(v)}</span>`;
    if (feld === "lock_state") return esc({ frei: "frei", gesperrt: "gesperrt", verloren: "verloren (gesperrt)", ausgesondert: "ausgesondert" }[v] || v);
    if (SET_WERTE[feld] && typeof v === "string") return esc(SET_WERTE[feld][v] || v);
    // Stufe in der Materialablage mit Zahl – Einträge vor Schritt 10 meinten die Stufen aus Phase 1 (wie beschriftung.py).
    if (feld === "recht_material" && Number.isInteger(v)) return esc(`${["kein Zugriff", "Mitglied", "Verwaltung"][v] || "?"} (${v})`);
    if (/_on$|^valid_from$|^retire_by(_manual)?$|^datum$|^begonnen$|^bis$/.test(feld)) return esc(fmtTag(v));
    if (typeof v === "object") return esc(JSON.stringify(v));
    return esc(v);
  }
  function journalHtml(eintraege, mitEntitaet) {
    if (!eintraege || !eintraege.length) return leer("Noch keine Einträge.");
    return `<ol class="mat-journal">${eintraege.map((j) => {
      const alle = Object.assign({}, j.vorher || {}, j.nachher || {});
      const felder = j.action === "angelegt" || j.action === "geloescht"
        ? [] : Object.keys(alle).filter((f) => !(f === "folder_id" && "ordner" in alle) && !(f === "origin_folder_id" && "herkunft" in alle)
                                       && !(f === "parent_id" && "pfad" in alle) && !(f === "product_id" && "produkt" in alle));
      const seite = (x, f) => wert((x || {})[f], f, Boolean(x) && f in x);
      // Schmal (mat-seite bis 600 px) wird jede Zeile zur Karte: Feld, darunter „vorher: …“ und „nachher: …“ über die
      // ganze Breite (data-l, material.css) – eine lange Mangelbeschreibung stand sonst in einer 125 px schmalen Zelle
      // (Liste nach dem Merge, 7). Hat ein Feld kein „vorher“ (neu dazugekommen), entfällt die Zeile dort; hat der ganze
      // Eintrag keins, auch die Beschriftung „nachher:“.
      const ohneVorher = !j.vorher || !Object.keys(j.vorher).length;
      const zeilen = felder.map((f) => `<tr><th>${esc(feldName(f, j))}</th><td class="mat-j-vorher${j.vorher && f in j.vorher ? "" : " leer"}" data-l="vorher">${seite(j.vorher, f)}</td><td data-l="nachher"${f === "mangelbeschreibung" ? ' class="mat-j-text"' : ""}>${seite(j.nachher, f)}</td></tr>`).join("");
      return `<li><div class="mat-j-kopf"><span class="mat-j-zeit">${esc(fmtZeit(j.created_at))}</span>
        <strong>${mitEntitaet ? esc(ENTITAET[j.entity] || j.entity) + " " : ""}${esc(AKTION[j.action] || j.action)}</strong>
        <span class="muted">von ${person(j.user_name || "–")}</span></div>
        ${zeilen ? `<table class="mat-diff${ohneVorher ? " ohne-vorher" : ""}"><thead><tr><th>Feld</th><th>vorher</th><th>nachher</th></tr></thead><tbody>${zeilen}</tbody></table>` : ""}</li>`;
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
  const summeKnopf = (h) => `<button type="button" class="mat-summe mat-hash" data-act="summe" data-wert="${esc(h)}" title="${esc(h)} – Klick kopiert"><span class="mat-summe-text">${esc(h.slice(0, 16))}…</span></button>`;
  async function summeKopieren(b) {
    try { await navigator.clipboard.writeText(b.dataset.wert); toast("Prüfsumme kopiert"); }
    catch (e) {
      // Ohne Zwischenablage: die ganze Summe zeigen und markieren.
      (b.querySelector(".mat-summe-text") || b).textContent = b.dataset.wert;
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
  // Legende zu zahlen(): jeder Zähler mit seinem Wort statt der Zahl – die Farbe ist nicht das einzige Merkmal, und die
  // Reihenfolge ist dieselbe wie hinter den Ordnern.
  // Seit 27.10.2026 steht sie mit der Erklärung des Bestands im „i“ an der Überschrift (BESTAND_INFO).
  const ZAEHLER_LEGENDE = `<span class="mat-legende">Hinter einem Ordner steht sein <span class="mat-baum-zahl">Bestand</span>,
      dahinter, wie viele davon <span class="mat-zahl s-ueberfaellig">überfällig</span> <span class="mat-zahl s-neu">neu</span>
      (Eingangsprüfung offen) <span class="mat-zahl s-lebensdauer">Lebensdauer erreicht</span>
      <span class="mat-zahl s-gesperrt">gesperrt</span> <span class="mat-zahl s-bald_faellig">bald fällig</span> sind –
      in dieser Reihenfolge, nur was vorkommt.</span>`;
  const BESTAND_INFO = "Oben stehen die Gliederungen, darunter frei verschachtelt Standorte, Fahrzeuge, Sets. Jede Gliederung hat die "
    + "Systemordner „Gesperrt“ und „Ausgesondert“ – dorthin kommen Artikel nur durch eine Sperre oder Aussonderung.";
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
  // Ein Knoten in Baum und Unterordnerliste: Pfad-Knoten grau ohne Zahl und Link; ein teilweise sichtbarer Systemordner
  // („Gesperrt“ einer Gliederung, die das Konto nicht sieht) sagt, dass er nur die eigenen Artikel zeigt.
  function knotenHtml(o) {
    if (o.nur_pfad) {
      return `${pfadKnoten(o.name)} ${o.system_kind ? "" : `<span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span>`}`;
    }
    return `<a href="/materialablage/ordner/${o.id}">${schloss(o)}${esc(o.name)}</a>
        ${o.system_kind ? "" : `<span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span>`}${o.teilweise ? ' <span class="small muted">nur deine Artikel</span>' : ""}${demoMarke(o.demo)}
        <span class="mat-baum-zahl">${o.system_kind ? Object.values(o.zaehlung || {}).reduce((a, b) => a + b, 0) : o.bestand}</span>${o.system_kind ? "" : zahlen(o.zaehlung)}`;
  }
  const knotenKlasse = (o) => (o.nur_pfad ? "pfad" : o.system_kind ? "system" : "");
  function baumHtml(liste, start) {
    const kinder = baumKinder(liste);
    const zweig = (pid) => (kinder[pid] || []).map((o) => `<li class="${knotenKlasse(o)}">${knotenHtml(o)}
        ${kinder[o.id] ? `<ul>${zweig(o.id)}</ul>` : ""}</li>`).join("");
    return `<ul class="mat-baum">${zweig(start || 0)}</ul>`;
  }

  function unterordnerHtml(liste) {
    return `<ul class="mat-unterordner">${liste.map((o) => `<li class="${knotenKlasse(o)}">${knotenHtml(o)}</li>`).join("")}</ul>`;
  }

  // Welche Knoten eines Auswahlbaums dastehen: die wählbaren (wahl) und alle, unter denen ein wählbarer liegt – als Weg.
  function auswahlBaum(kinder, wahl) {
    const da = new Set();
    const besuch = (pid) => (kinder[pid] || []).reduce((jemand, o) => {
      const hier = besuch(o.id) || wahl.has(o.id);
      if (hier) da.add(o.id);
      return jemand || hier;
    }, false);
    besuch(0);
    return da;
  }
  // <option>s einer Ordnerauswahl (Artikel anlegen, Prüfdurchgang): wählbar nur, was waehlbar(o) erlaubt; der Weg
  // dorthin steht deaktiviert da, Zweige ohne wählbaren Ordner entfallen. Liefert { html, anzahl }.
  function ordnerOptionen(liste, waehlbar, gewaehlt, mitBestand) {
    const ohneSystem = liste.filter((o) => !o.system_kind);
    const kinder = baumKinder(ohneSystem);
    const wahl = new Set(ohneSystem.filter((o) => !o.nur_pfad && waehlbar(o)).map((o) => o.id));
    const da = auswahlBaum(kinder, wahl);
    const zweig = (pid, tiefe) => (kinder[pid] || []).filter((o) => da.has(o.id)).map((o) => `<option value="${o.id}"${wahl.has(o.id)
      ? (o.id === gewaehlt ? " selected" : "") : " disabled"}>${EIN.repeat(tiefe)}${esc(o.name)}${mitBestand && wahl.has(o.id) ? ` (${o.bestand})` : ""}</option>${zweig(o.id, tiefe + 1)}`).join("");
    return { html: zweig(0, 0), anzahl: wahl.size };
  }

  /* Ordnerwahl im Dialog (verschieben nach …): wählbar sind nur Ordner, die das Konto verwaltet (opts.waehlbar), und mit
     opts.quelle nur Ziele, deren Gliederung es wechseln darf – über eine Gliederungsgrenze nur, wer beide verwaltet.
     Systemordner und (beim Verschieben eines Ordners) dessen eigener Zweig sind nie wählbar. Was nicht wählbar ist,
     aber zu wählbaren Ordnern führt, steht grau als Weg da; Zweige ohne wählbaren Ordner entfallen. opts.hinweis:
     HTML über dem Baum; opts.wechselHinweis: HTML, das erscheint, sobald ein Ziel in einer anderen Gliederung gewählt
     ist. Liefert die Kennung (0 = oberste Ebene) oder null. */
  async function ordnerWaehlen(titel, opts) {
    opts = opts || {};
    const liste = await ordnerBaum(true);
    const ohneSystem = liste.filter((o) => !o.system_kind);
    const kinder = baumKinder(ohneSystem);
    const gesperrt = new Set();
    if (opts.ohneZweig) {
      const weg = [opts.ohneZweig];
      while (weg.length) { const x = weg.pop(); gesperrt.add(x); (kinder[x] || []).forEach((k) => weg.push(k.id)); }
    }
    const mitQuelle = "quelle" in opts;
    let grenze = false;                  // ein verwalteter Ordner fiel nur wegen der Gliederungsgrenze weg
    const wahl = new Set(ohneSystem.filter((o) => {
      if (o.nur_pfad || gesperrt.has(o.id) || !(opts.waehlbar || verwaltet)(o)) return false;
      if (mitQuelle && !wechselErlaubt(opts.quelle, o.id)) { grenze = true; return false; }
      return true;
    }).map((o) => o.id));
    const oben = opts.obersteEbene && DARF.alles;
    const da = auswahlBaum(kinder, wahl);
    const zweig = (pid) => (kinder[pid] || []).filter((o) => da.has(o.id)).map((o) => {
      const unten = zweig(o.id);
      return `<li><label class="inline${wahl.has(o.id) ? "" : " mat-wahl-weg"}"><input type="radio" name="ziel" value="${o.id}" ${wahl.has(o.id) ? "" : "disabled"}>
        <span class="mat-wahl-name">${esc(o.name)}</span> <span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span></label>
        ${unten ? `<ul>${unten}</ul>` : ""}</li>`;
    }).join("");
    return new Promise((resolve) => {
      let gewaehlt = null;
      const dlg = dialog(`<h2>${esc(titel)}</h2>
        ${opts.hinweis ? `<p class="help">${opts.hinweis}</p>` : ""}
        ${oben ? '<label class="inline"><input type="radio" name="ziel" value="0"> oberste Ebene (nur für Gliederungen)</label>' : ""}
        <div class="mat-wahl">${wahl.size ? `<ul class="mat-baum">${zweig(0)}</ul>` : leer("Kein Ordner, den du hierfür verwaltest.")}</div>
        ${grenze ? '<p class="help">Ordner anderer Gliederungen stehen nur zur Wahl, wenn du beide Gliederungen verwaltest.</p>' : ""}
        <div id="ow-wechsel" class="notice" hidden>${opts.wechselHinweis || ""}</div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="ow-ok" type="button" ${wahl.size || oben ? "" : "disabled"}>Übernehmen</button></div>`, (d, body) => {
        // Liegt das gewählte Ziel in einer anderen Gliederung, sagt der Dialog vorher, was dann mitwandert.
        body.addEventListener("change", (e) => {
          if (e.target.name !== "ziel" || !opts.wechselHinweis || !mitQuelle) return;
          $("#ow-wechsel", body).hidden = !wechsel(opts.quelle, +e.target.value || null);
        });
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
  /* Ohne Freigabe im Bestand (Mitglied ohne Freigabe, Prüfer ohne Prüffreigabe, abgelaufene Freigaben) zeigt die Übersicht keine
     Zahlen – es wären nur Nullen –, sondern „Meine Freigaben“ (wer sie vergibt) und den Weg zu Katalog und Suche. */
  async function dashboard() {
    const d = await api(`${API}/start`);
    const z = d.zaehlung;
    // Nullen tragen „null“ und stehen hinten – in jeder Breite und schon im Dokument, damit Tab- und Vorlesereihenfolge
    // der sichtbaren entsprechen (vorher schob CSS order sie nur am Telefon ans Ende; Geräte-Prüfung vom 22.10.2026).
    // Am Telefon werden sie dazu zu einer Zeile (material.css, Übersicht).
    const kachel = ([s, titel]) => `<a class="mat-kachel s-${s}${z[s] ? "" : " null"}" href="/materialablage/pruefungen?status=${s}"><strong>${z[s] || 0}</strong><span>${esc(titel)}</span></a>`;
    const kacheln = [["ueberfaellig", "überfällig"], ["neu", "neu (Eingangs\u00adprüfung)"], ["bald_faellig", `bald fällig (${d.schwelle_tage} Tage)`],
      ["gesperrt", "gesperrt"], ["lebensdauer", "Lebensdauer erreicht"], ["einsatzbereit", "einsatzbereit"]];
    const bestandTeil = DARF.lesen ? `<div class="mat-kachelrahmen"><div class="mat-kacheln mat-statuskacheln">
        <div class="mat-kachel gesamt"><strong>${d.bestand}</strong><span>Artikel im Bestand</span></div>
        ${[...kacheln.filter(([s]) => z[s]), ...kacheln.filter(([s]) => !z[s])].map(kachel).join("")}
      </div></div>
      <div id="mat-runden"></div>
      <div class="mat-nebeneinander"><section class="section"><h2>Fälligkeiten je Ordner${d.ordner_uebersicht.length ? infoKnopf("Fälligkeiten je Ordner", ordnerUebersichtInfo(d.ordner_uebersicht)) : ""}</h2>
        ${d.ordner_uebersicht.length ? ordnerUebersichtHtml(d.ordner_uebersicht)
          : leer(DARF.gliederung_anlegen ? "Noch keine Gliederung – lege unter „Bestand“ die erste an." : "Noch keine Gliederung angelegt.")}
      </section>
      <section class="section"><h2>Als Nächstes zu prüfen</h2>
        ${d.naechste.length ? artikelTabelle(d.naechste, { pfad: true }) + (d.faellig_gesamt > d.naechste.length ? `<p><a href="/materialablage/pruefungen">Alle ${d.faellig_gesamt} anzeigen →</a></p>` : "")
          : leer("Nichts fällig.")}
      </section></div>`
      : `<p class="help">Im <a href="/materialablage/katalog">Katalog</a> stehen alle Produkte mit Prüfformularen und Herstellerdokumenten.
          Die Nummernsuche oben findet eine Herstellerseriennummer auf Wunsch auch außerhalb deines Bereichs – das wird mit deinem Namen protokolliert.</p>`;
    // Ohne Knöpfe im Kopf (Wunsch vom 20.10.2026): Bestand und „Artikel anlegen“ erreicht man über den Reiter „Bestand“.
    seitenTitel("Übersicht");
    inhalt.innerHTML = `<div class="page-head"><h1>Materialablage</h1></div>
      ${mangelKasten(d.maengel, d.maengel_gesamt)}
      ${rueckrufKasten(d.rueckrufe)}
      ${d.meldungen_offen ? `<p class="notice"><a href="/materialablage/katalog/meldungen"><strong>${plural(d.meldungen_offen, "offene Produktmeldung", "offene Produktmeldungen")}</strong></a>
        – Materialwarte warten darauf, Artikel davon anzulegen.</p>` : ""}
      ${d.antraege_offen ? `<p class="notice"><a href="/materialablage/bestand/antraege"><strong>${plural(d.antraege_offen, "offener Änderungsantrag", "offene Änderungsanträge")}</strong></a>
        – Stammdaten nach der ersten Prüfung in Ordnern, die du verwaltest; bestätigen oder ablehnen.</p>` : ""}
      ${empfohlenHinweis(d.aussonderung_empfohlen)}
      ${nacharbeitHinweis(d.nacharbeit)}
      ${erinnerungHinweise(d.erinnerungen)}
      <div id="mat-freigaben-hinweis"></div>
      ${bestandTeil}
      ${psaKasten(d.meine_psa)}
      ${erinnerungZeile(d.erinnerungen)}
      ${mailKasten(d.mailfehler)}`;
    aktionen = { probelauf: () => probelaufDialog(), "mail-erledigt": mailErledigt, "mail-alle": mailAlleErledigt,
                 "mail-mehr": () => mailMehrLaden() };
    if (DARF.lesen) {
      ordnerUebersichtKlappen($("#mat-ue"));
      rundenKasten($("#mat-runden"));
    }
    // „Meine Freigaben“ (freigaben.js): eigene Freigaben, gelb, was bald abläuft – ohne Freigabe, wer sie vergibt.
    const f = await baustein("MatFreigaben");
    const el = $("#mat-freigaben-hinweis");
    if (f && el) f.hinweis(el);
  }

  /* Erinnerungsmails (nur Material- und Plattform-Verwaltung; /start liefert sonst erinnerungen: null). Unten auf der
     Übersicht eine Zeile mit dem Stand – an/aus/gesperrt, der letzte Lauf – und dem Textlink „Probelauf ansehen“; was
     Handeln verlangt (Lauf steht, kein Mailserver, Fehlschläge, Fehler), steht zusätzlich oben gelb. Die Zeitpunkte
     kommen als UTC und werden in deutscher Zeit gezeigt, der Tag des Laufs ist schon der deutsche. Darunter seit
     Phase 4 · L1 der Kasten „Mailversand“ (mailKasten) mit den gescheiterten Modul-Mails. */
  const ZONE = "Europe/Berlin";
  const tagBerlin = (versatz) => new Intl.DateTimeFormat("sv-SE", { timeZone: ZONE })
    .format(new Date(Date.now() + (versatz || 0) * 86400000));
  const uhrBerlin = (iso) => (iso ? new Date(iso).toLocaleTimeString("de-DE", { timeZone: ZONE, hour: "2-digit", minute: "2-digit" }) : "");
  const tagKurz = (tag) => fmtTag(tag).slice(0, 6);
  // „heute 06:02“, „gestern 06:02“, „am 17.10. 06:02“
  function laufWann(l) {
    const tag = l.tag === tagBerlin() ? "heute" : l.tag === tagBerlin(-1) ? "gestern" : `am ${tagKurz(l.tag)}`;
    return `${tag}${l.beginn ? ` ${uhrBerlin(l.beginn)}` : ""}`;
  }
  // „4 Mails, 1 fehlgeschlagen“ – an wen, steht seit Phase 4 · L1 im Kasten „Mailversand“ (mailKasten), nicht mehr hier.
  function laufErgebnis(l) {
    return `${plural(l.mails || 0, "Mail", "Mails")}${l.fehlgeschlagen ? `, ${l.fehlgeschlagen} fehlgeschlagen` : ""}`;
  }
  const versandAktiv = (e) => e.versand && !e.gesperrt;

  function erinnerungZeile(e) {
    if (!e) return "";
    const l = e.letzter;
    const zustand = e.gesperrt ? "in dieser Umgebung gesperrt"
      : !e.versand ? "aus – einschalten unter Leitstelle → Einstellungen (Plattform-Verwaltung)"
        : e.smtp ? "an" : "an, aber kein Mailserver eingerichtet";
    const lauf = l ? ` · letzter Lauf ${laufWann(l)} – ${laufErgebnis(l)}` : versandAktiv(e) ? " · noch kein Lauf" : "";
    return `<p class="help mat-erinnerungen" id="mat-erinnerungen">Erinnerungsmails: ${zustand}${lauf}${e.laeuft ? " · ein Lauf ist gerade im Gange" : ""}
      · <button type="button" class="lnk" data-act="probelauf">Probelauf ansehen</button></p>`;
  }

  function erinnerungHinweise(e) {
    if (!e) return "";
    const l = e.letzter;
    const p = e.pflege;
    const hinweise = [];
    if (e.veraltet && l) hinweise.push(`Erinnerungsmails: Letzter Lauf am ${esc(tagKurz(l.tag))} – heute ist noch keiner gelaufen.`);
    if (e.pflege_veraltet) {
      hinweise.push(p && p.tag ? `Der tägliche Lauf (Journal, Aufräumen) ist seit dem ${esc(tagKurz(p.tag))} nicht gelaufen.`
        : "Der tägliche Lauf (Journal, Aufräumen) ist noch nie gelaufen.");
    }
    if (versandAktiv(e) && !e.smtp) hinweise.push("Erinnerungsmails sind an, aber kein Mailserver eingerichtet – es geht nichts hinaus.");
    if (l && l.fehlgeschlagen && versandAktiv(e)) {
      hinweise.push(l.fehlgeschlagen === 1 ? "1 Erinnerungsmail ist gescheitert – sie geht morgen erneut; an wen, steht unter „Mailversand“."
        : `${l.fehlgeschlagen} Erinnerungsmails sind gescheitert – sie gehen morgen erneut; an wen, steht unter „Mailversand“.`);
    }
    if (l && l.fehler) hinweise.push(`Beim letzten Lauf der Erinnerungsmails ist ein Fehler aufgetreten: ${esc(l.fehler)}`);
    if (p && p.fehler) hinweise.push(`Beim letzten täglichen Lauf (Journal, Aufräumen) ist ein Fehler aufgetreten: ${esc(p.fehler)}`);
    if (l && l.fehlerhaft) hinweise.push(`Beim letzten Lauf ${l.fehlerhaft === 1 ? "konnte 1 Artikel bzw. 1 Freigabe" : `konnten ${l.fehlerhaft} Artikel bzw. Freigaben`} nicht gelesen werden – siehe Server-Log.`);
    if (l && l.vermerk_fehler) hinweise.push(`${plural(l.vermerk_fehler, "verschickte Erinnerungsmail konnte", "verschickte Erinnerungsmails konnten")} nicht vermerkt werden – was darin stand, kommt morgen noch einmal. Siehe Server-Log.`);
    return hinweise.map((h) => `<p class="notice">${h} <a href="#mat-erinnerungen">Einzelheiten unten</a></p>`).join("");
  }

  /* Probelauf: wer beim nächsten echten Lauf welche Mail bekäme – heute, oder morgen, wenn heute schon verschickt wurde.
     Betreff und Text kommen fertig vom Server; nichts wird verschickt oder vermerkt. Das Kästchen „DEMO-Bestand
     einbeziehen (nur Ansicht)“ erscheint nur, wenn DEMO ausgelassen wurde oder schon einbezogen ist (auf dev ist alles
     DEMO); Umschalten lädt den Dialog neu. Mails mit DEMO tragen die Marke – sie gehen nie hinaus. Bekommt jemand die
     Mail (auch) als Inhaber einer ablaufenden Freigabe, nennt die Zeile „n eigene Freigaben“ (Abschnitt „Deine
     Freigaben“); eine Mail nur dafür nennt keine leeren Zahlen. Ebenso „n PSA“ für den Abschnitt „Deine PSA“ (Phase 3 ·
     L1: Artikel, die der Person zugeordnet sind) – „PSA“ bleibt auch in der Mehrzahl. */
  const DEMO_NIE = "DEMO – geht nie hinaus";
  const mailZahlen = (m) => [m.artikel || (!m.eigene && !m.psa) ? plural(m.artikel, "Artikel", "Artikel") : "",
    m.freigaben || (!m.eigene && !m.psa) ? plural(m.freigaben, "Freigabe", "Freigaben") : "",
    m.eigene ? plural(m.eigene, "eigene Freigabe", "eigene Freigaben") : "",
    m.psa ? `${m.psa} PSA` : ""].filter(Boolean).join(", ");
  async function probelaufDialog(demo, kaestchen) {
    let p;
    try { p = await api(`${API}/erinnerungen/probelauf${demo ? "?demo=1" : ""}`); } catch (e) { toast(e.message, true); return false; }
    // Beim Umschalten: Wurde der Dialog inzwischen geschlossen (oder steht ein anderer darin), nicht wieder öffnen.
    if (kaestchen && !(kaestchen.isConnected && $("#dlg").open)) return false;
    const wann = p.stichtag === tagBerlin() ? "Heute" : p.morgen ? "Morgen" : `Am ${fmtTag(p.stichtag)}`;
    const l = p.letzter;
    const zahlText = (a, f) => [a ? plural(a, "Artikel", "Artikel") : "", f ? plural(f, "Freigabe", "Freigaben") : ""].filter(Boolean).join(", ");
    const mails = p.mails.map((m) => `<details class="mat-probemail"><summary>${esc(m.name)}${m.gliederung ? ` (${esc(m.gliederung)})` : ""}
        – ${mailZahlen(m)}${m.demo ? `<span class="mat-demo" title="${DEMO_NIE}">DEMO</span>` : ""}</summary>
        ${m.demo ? `<p class="small"><strong>${DEMO_NIE}</strong> – nur zur Ansicht.</p>` : ""}
        <p class="small"><strong>Betreff:</strong> ${esc(m.betreff)}</p><pre class="mat-mailtext">${esc(m.text)}</pre></details>`).join("");
    const ohne = p.ohne_empfaenger.length ? `<p class="small"><strong>Ohne Empfänger:</strong> ${p.ohne_empfaenger.map((o) => `${esc(o.ordner)} (${zahlText(o.artikel, o.freigaben)})`).join("; ")}
        – niemand mit Adresse und Modulzugang verwaltet dort, auch keine Material- oder Plattform-Verwaltung.</p>` : "";
    const aus = p.ausgelassen.ordner_aus || [];
    const demoAus = [p.ausgelassen.demo ? `${p.ausgelassen.demo} DEMO-Artikel` : "",
      p.ausgelassen.demo_freigaben ? plural(p.ausgelassen.demo_freigaben, "DEMO-Freigabe", "DEMO-Freigaben") : ""].filter(Boolean);
    const ausTeile = [aus.length ? `Erinnerungen aus in ${aus.map((o) => `<a href="/materialablage/ordner/${o.id}">${esc(o.pfad)}</a> (${plural(o.artikel, "Artikel", "Artikel")})`).join(", ")}` : "", ...demoAus].filter(Boolean);
    const ausgelassen = ausTeile.length ? `<p class="small"><strong>Ausgelassen:</strong> ${ausTeile.join("; ")}</p>` : "";
    // Nur, wenn es DEMO gibt (oder es schon einbezogen ist) – in der Produktion ohne DEMO-Bestand bleibt der Dialog, wie er war.
    const demoFeld = p.demo || demoAus.length ? `<p class="mat-probelauf-demo"><label class="inline"><input type="checkbox" id="pl-demo" ${p.demo ? "checked" : ""}>
        DEMO-Bestand einbeziehen (nur Ansicht)</label></p>
      ${p.demo ? `<p class="notice small">DEMO-Bestand einbezogen – nur zur Ansicht. Mails mit DEMO gehen nie hinaus; der echte Lauf lässt DEMO weiter aus.</p>` : ""}` : "";
    const dlg = dialog(`<h2>Probelauf Erinnerungsmails</h2>
      ${l ? `<p class="small">${esc(laufWann(l).replace(/^\w/, (c) => c.toUpperCase()))} verschickt: ${laufErgebnis(l)}.</p>` : ""}
      ${p.gesperrt ? '<p class="notice small">Erinnerungsmails sind in dieser Umgebung gesperrt – so gingen sie hinaus, wenn sie an wären.</p>'
        : !p.versand ? '<p class="notice small">Erinnerungsmails sind aus – so gingen sie hinaus, wenn sie an wären.</p>'
        : !p.smtp ? '<p class="notice small">Kein Mailserver eingerichtet – so gingen sie hinaus, wenn einer eingerichtet wäre.</p>' : ""}
      <p class="help">Nichts wird verschickt oder vermerkt. Gerechnet mit den Rechten und Ordnern von jetzt.</p>
      ${demoFeld}
      ${p.fehlerhaft ? `<p class="notice small">${p.fehlerhaft === 1 ? "1 Artikel bzw. 1 Freigabe konnte" : `${p.fehlerhaft} Artikel bzw. Freigaben konnten`} nicht gelesen werden – siehe Server-Log.</p>` : ""}
      <h3>${wann} ab 6 Uhr gingen hinaus:</h3>
      ${mails || leer(`${wann} stünde nichts an.`)}
      ${ohne}${ausgelassen}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`);
    // #dlg dient allen Dialogen der Seite – die Breite gilt nur, solange der Probelauf offen ist.
    if (!dlg.classList.contains("mat-probelauf")) {
      dlg.classList.add("mat-probelauf");
      dlg.addEventListener("close", () => dlg.classList.remove("mat-probelauf"), { once: true });
    }
    const feld = $("#pl-demo", dlg);
    if (feld) {
      feld.addEventListener("change", async () => {
        feld.disabled = true;
        const neu = feld.checked;
        if (await probelaufDialog(neu, feld)) {
          const f = $("#pl-demo", dlg);
          if (f) f.focus();                        // der Fokus bleibt am Kästchen, auch nach dem Neuladen
        } else { feld.checked = !neu; feld.disabled = false; }
      });
    }
    return true;
  }

  /* Kasten „Mailversand“ (Phase 4 · L1): die gescheiterten Modul-Mails aus /start (mailfehler – null heißt kein Kasten;
     mailprotokoll.uebersicht), je nach Sicht: Material- und Plattform-Verwaltung alles, wer einen Ordner verwaltet, die
     Zeilen dieses Zweigs. Die letzten 20 offenen als Tabelle mit vier Spalten (Mail: Zeit, Art, Bezug als Link ins Modul
     – vom Server aus Kennungen gebaut –, darunter klein der Betreff; Empfänger mit Rolle – nie eine Adresse; Fehler als
     deutscher Text, darunter klein die gereinigte Antwort des Mailservers; „Erledigt“), bis 800 px Inhaltsbreite als
     Karte mit drei bis vier Zeilen. „Weitere anzeigen“ lädt alle offenen der Sicht nach (GET …/mailfehler, höchstens
     200). Je Zeile „Erledigt“ (grau, POST …/erledigt – die Zeile verschwindet, der Fokus geht zur nächsten Zeile bzw.
     zur Überschrift, 404 als Meldung), „Alle erledigt“ im Untermenü des Kastens mit Rückfrage (POST …/alle-erledigt,
     Antwort mit Zahl; der Fokus geht auf die Meldung im Kasten). Fehlt der Mailserver, steht für die Verwaltung eine
     Dauerzeile. Kein „Erneut senden“: Mailtexte werden nicht gespeichert – Erinnerungen holt der nächste Lauf nach. */
  const MAIL_KLASSE = { empfaenger_abgewiesen: "Empfänger abgewiesen", verbindung: "keine Verbindung zum Mailserver",
                        anmeldung: "Anmeldung am Mailserver abgelehnt", abgelehnt: "vom Mailserver abgelehnt",
                        ausnahme: "Fehler beim Versand", sonstiges: "sonstiger Fehler" };
  const MAIL_ROLLE = { verwalter: "Materialwart", pruefer: "Prüfer", zugeordnet: "zugeordnete Person", inhaber: "Inhaber der Freigabe",
                       verwaltung: "Material-Verwaltung", antragsteller: "Antragsteller", melder: "Melder" };
  function mailZeile(z) {
    const b = z.bezug || {};
    const bezug = b.pfad ? `<a href="${esc(b.pfad)}">${esc(b.text || "öffnen")}</a>` : esc(b.text || "");
    return `<tr data-mail="${Number(z.id)}">
      <td class="mat-mail-was"><span class="mat-mail-zeit">${esc(fmtZeit(z.created_at))}</span> · <strong>${esc(z.art_text)}</strong>${bezug ? ` · ${bezug}` : ""}
        ${z.betreff ? `<div class="mat-mail-betreff">${esc(z.betreff)}</div>` : ""}</td>
      <td class="mat-mail-an" data-l="An">${esc(z.empfaenger)} <span class="muted">(${esc(MAIL_ROLLE[z.rolle] || z.rolle)})</span></td>
      <td class="mat-mail-fehler">${esc(MAIL_KLASSE[z.klasse] || z.klasse)}${z.meldung ? `<div class="mat-mail-meldung">${esc(z.meldung)}</div>` : ""}</td>
      <td class="tabelle-aktionen"><button type="button" class="btn secondary small" data-act="mail-erledigt" data-id="${Number(z.id)}">Erledigt</button></td></tr>`;
  }
  // „… und n weitere“ mit „Weitere anzeigen“ – oder nichts, wenn alle offenen Zeilen dastehen.
  function mailMehr(offen, gezeigt) {
    if (offen <= gezeigt) return "";
    return `<p class="small mat-mail-mehr" id="mat-mail-mehr">… und ${offen - gezeigt} weitere.
      <button type="button" class="btn secondary small" data-act="mail-mehr">Weitere anzeigen</button></p>`;
  }
  function mailKasten(m) {
    if (!m) return "";
    const tabelle = m.zeilen.length ? `<table class="list mat-tabelle mat-mail" id="mat-mail-tabelle"><thead><tr><th>Mail</th>
        <th>Empfänger</th><th>Fehler</th><th></th></tr></thead><tbody>${m.zeilen.map(mailZeile).join("")}</tbody></table>
      ${mailMehr(m.offen, m.zeilen.length)}` : "";
    return `<section class="section mat-mail-kasten" id="mat-mail" aria-labelledby="mat-mail-titel" data-offen="${Number(m.offen)}"><div class="abschnittskopf"><h2 id="mat-mail-titel" tabindex="-1">Mailversand</h2>
        ${m.zeilen.length ? `<details class="mat-menue"><summary class="btn secondary small" aria-haspopup="true">Mehr</summary><div class="mat-menue-liste">
          <a href="#mat-mail" role="button" data-act="mail-alle"><strong>Alle erledigt</strong><span>Alle offenen Zeilen abhaken – auch die nicht angezeigten (mit Rückfrage).</span></a></div></details>` : ""}</div>
      ${m.kein_mailserver ? '<p class="notice">Kein Mailserver eingerichtet – keine Modul-Mail geht hinaus (Erinnerungen, Mängel, Anträge, Produktmeldungen, Rückrufe).</p>' : ""}
      ${m.zeilen.length ? `<p class="help mat-mail-hilfe">Diese Mails hat der Mailserver nicht angenommen. Erinnerungen holt der nächste Lauf nach; alles andere sagst du den Betroffenen selbst – ein erneuter Versand ist nicht möglich.</p>${tabelle}` : ""}
    </section>`;
  }
  // Die Zahl der offenen Zeilen steht am Kasten (data-offen) – „Erledigt“ zählt herunter, „… und n weitere“ folgt.
  function mailOffen(kasten, n) {
    kasten.dataset.offen = String(n);
    const tbody = $("#mat-mail-tabelle tbody", kasten);
    const gezeigt = tbody ? tbody.rows.length : 0;
    const alt = $("#mat-mail-mehr", kasten);
    if (alt) alt.remove();
    const tabelle = $("#mat-mail-tabelle", kasten);
    if (tabelle) tabelle.insertAdjacentHTML("afterend", mailMehr(n, gezeigt));
  }
  // „Erledigt“ an einer Zeile: abhaken, Zeile weg, Fokus auf „Erledigt“ der nächsten (sonst der vorigen) Zeile; war es
  // die letzte, bleibt der Kasten mit einer Meldung stehen und die Überschrift bekommt den Fokus (sonst fiele er an den
  // Seitenanfang). 404 (fremd oder inzwischen weg) steht als Meldung.
  async function mailErledigt(b) {
    b.disabled = true;
    try {
      await api(`${API}/mailfehler/${Number(b.dataset.id)}/erledigt`, { method: "POST", body: {} });
      const kasten = $("#mat-mail");
      const tr = b.closest("tr");
      const nachbar = tr.nextElementSibling || tr.previousElementSibling;
      tr.remove();
      const offen = Math.max(0, Number(kasten.dataset.offen || 1) - 1);
      if (!nachbar && !offen) {
        mailKastenLeeren("Alle Zeilen sind erledigt.");
        $("#mat-mail-titel").focus();
      } else if (!nachbar) {
        mailOffen(kasten, offen);
        mailMehrLaden(kasten);
      } else {
        mailOffen(kasten, offen);
        $('[data-act="mail-erledigt"]', nachbar).focus();
      }
      toast("Erledigt");
    } catch (e) { toast(e.message, true); b.disabled = false; }
  }
  // „Weitere anzeigen“: alle offenen Zeilen der Sicht (höchstens 200, neueste zuerst) statt der 20.
  async function mailMehrLaden(kasten) {
    kasten = kasten && kasten.dataset ? kasten : $("#mat-mail");
    try {
      const r = await api(`${API}/mailfehler`);
      const tbody = $("#mat-mail-tabelle tbody", kasten);
      const vorher = tbody.rows.length;
      if (!r.zeilen.length) {
        mailKastenLeeren("Alle Zeilen sind erledigt.");
        $("#mat-mail-titel").focus();
        return;
      }
      tbody.innerHTML = r.zeilen.map(mailZeile).join("");
      mailOffen(kasten, r.offen);
      const mehr = $("#mat-mail-mehr", kasten);
      if (mehr) mehr.innerHTML = `Es stehen die neuesten ${r.zeilen.length} von ${r.offen} offenen Zeilen da – die übrigen erscheinen, sobald du welche abhakst.`;
      // Der Fokus geht auf die erste neu dazugekommene Zeile (beim Nachladen nach der letzten abgehakten: die erste).
      $('[data-act="mail-erledigt"]', tbody.rows[Math.min(vorher, tbody.rows.length - 1)]).focus();
    } catch (e) { toast(e.message, true); }
  }
  // „Alle erledigt“ mit Rückfrage (die Zeilen sind danach nirgends mehr zu sehen); danach steht die Meldung im Kasten
  // und hat den Fokus.
  function mailAlleErledigt() {
    const kasten = $("#mat-mail");
    const menue = $("details.mat-menue", kasten);
    if (menue) menue.open = false;
    const n = Number(kasten.dataset.offen || 0);
    dialog(`<h2>Alle erledigt?</h2>
      <p>${n === 1 ? "1 Zeile" : `${n} Zeilen`} als erledigt markieren? Sie verschwinden aus dem Kasten und lassen sich nicht wieder zeigen – auch die, die hier nicht angezeigt sind.</p>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="mf-alle-ok" type="button">Alle erledigt</button></div>`,
    (dlg, body) => {
      $("#mf-alle-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          const r = await api(`${API}/mailfehler/alle-erledigt`, { method: "POST", body: {} });
          dlg.close();
          mailKastenLeeren(r.anzahl === 1 ? "1 Zeile erledigt." : `${r.anzahl} Zeilen erledigt.`);
          $("#mat-mail-stand").focus();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }
  // Der Kasten ohne offene Zeilen: Überschrift, die Dauerzeile ohne Mailserver (falls da) und die Meldung.
  function mailKastenLeeren(meldung) {
    const kasten = $("#mat-mail");
    if (!kasten) return;
    $$("table, p.help, #mat-mail-mehr, details.mat-menue, #mat-mail-stand", kasten).forEach((el) => el.remove());
    kasten.dataset.offen = "0";
    kasten.insertAdjacentHTML("beforeend", `<p class="help" id="mat-mail-stand" tabindex="-1">${esc(meldung)}</p>`);
  }

  /* Fälligkeiten je Ordner: Gliederungen mit ihren Ordnern eingerückt, die Zahlen für den ganzen Zweig – dieselben wie in
     der Ordnerleiste (/start, ordner_uebersicht). Die Systemordner sind keine eigenen Zeilen: Gesperrte und ausgesonderte
     Artikel liegen in ihrer Gliederung und zählen dort. Jede Zahl führt zur Liste genau dieser Artikel (Prüfungen, nach
     Ordner und Status gefiltert), die nächste Fälligkeit zu allem Fälligen im Ordner, der Name zum Ordner. Ein großer Baum
     (mehr als UE_GROSS Zeilen) beginnt mit zugeklappten Ordnern ab der zweiten Ebene unter der Gliederung. Bis 600 px
     Inhaltsbreite wird jede Zeile zur Karte; leere Zahlen entfallen dort. */
  // Kurztitel mit weichen Trennstellen (\u00ad): Am Rechner stehen die Köpfe einzeilig, in der engen Tabelle (601–820 px
  // Inhaltsbreite) dürfen sie dort umbrechen – so bleibt Platz für die Ordnernamen.
  const UE_SPALTEN = [["ueberfaellig", "über\u00adfällig", "überfällig"], ["neu", "neu", "neu (Eingangsprüfung offen)"],
                      ["bald_faellig", "bald fällig", "bald fällig"], ["gesperrt", "ge\u00adsperrt", "gesperrt"],
                      ["lebensdauer", "Lebens\u00addauer erreicht", "Lebensdauer erreicht"]];
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
      // Pfad-Knoten (Oberordner ohne eigene Freigabe): nur der Name, grau – keine Zahlen, kein Link.
      if (o.nur_pfad) {
        return `<tr data-weg="${weg.join(" ")}" class="mat-ue-pfad${o.tiefe ? "" : " mat-ue-oben"}" style="--tiefe:${Math.min(o.tiefe, 8)}" ${weg.some((x) => zu.has(x)) ? "hidden" : ""}>
          <td data-l="Ordner" class="mat-ue-name">${knopf}${pfadKnoten(o.name)}${o.kind === "gliederung" ? ` <span class="mat-art">${esc(ORDNERART[o.kind])}</span>` : ""}</td>
          ${'<td class="mat-ue-zahl mat-ue-null"></td>'.repeat(UE_SPALTEN.length + 1)}<td class="mat-ue-tag mat-ue-null"></td></tr>`;
      }
      // Die Karte (bis 600 px Inhaltsbreite) beschriftet mit dem Kurztitel – „neu“ statt „neu (Eingangsprüfung offen)“ spart eine Zeile.
      const zahlen = UE_SPALTEN.map(([s, kurz, lang]) => {
        const n = o.zaehlung[s] || 0;
        return `<td data-l="${esc(kurz.replace(/\u00ad/g, ""))}" class="mat-ue-zahl${n ? "" : " mat-ue-null"}">${n ? `<a class="mat-zahl s-${s}" href="/materialablage/pruefungen?ordner=${o.id}&status=${s}" title="${esc(`${lang} – ${o.name}`)}">${n}</a>` : '<span class="muted">–</span>'}</td>`;
      }).join("");
      return `<tr data-weg="${weg.join(" ")}" class="${o.tiefe ? "" : "mat-ue-oben"}" style="--tiefe:${Math.min(o.tiefe, 8)}" ${weg.some((x) => zu.has(x)) ? "hidden" : ""}>
        <td data-l="Ordner" class="mat-ue-name">${knopf}<a href="/materialablage/ordner/${o.id}">${schloss(o)}${esc(o.name)}</a>${o.system_kind || (o.tiefe && o.kind !== "gliederung") ? "" : ` <span class="mat-art">${esc(ORDNERART[o.kind] || o.kind)}</span>`}${demoMarke(o.demo)}</td>
        <td data-l="Bestand" class="mat-ue-zahl">${o.bestand}</td>${zahlen}
        <td data-l="nächste Fälligkeit" class="mat-ue-tag${o.naechste ? "" : " mat-ue-null"}">${o.naechste ? `<a class="t-${esc(o.naechste_status)}" href="/materialablage/pruefungen?ordner=${o.id}" title="Alles Fällige in ${esc(o.name)}">${esc(fmtTag(o.naechste))}</a>` : '<span class="muted">–</span>'}</td></tr>`;
    };
    // Die Erklärung steht seit 27.10.2026 im „i“ an der Überschrift (ordnerUebersichtInfo) – vorher als Absatz unter der
    // Tabelle, damit beide Tabellen nebeneinander auf gleicher Höhe beginnen (Wunsch vom 22.10.2026); das bleibt so.
    return `<table class="list mat-tabelle mat-ue" id="mat-ue"><thead><tr><th>Ordner</th><th class="mat-ue-zahl">Bestand</th>
        ${UE_SPALTEN.map(([s, kurz, lang]) => `<th class="mat-ue-zahl" title="${esc(lang)}">${esc(kurz)}</th>`).join("")}<th>nächste Fälligkeit</th></tr></thead>
      <tbody>${zeilen.map(zeile).join("")}</tbody></table>`;
  }
  const ordnerUebersichtInfo = (zeilen) => `Die Zahlen gelten für den ganzen Zweig. Gesperrte und ausgesonderte Artikel liegen in ihrer Gliederung und zählen dort.
    Nächste Fälligkeit: das früheste Prüfdatum im Zweig – ohne neue (Eingangsprüfung), gesperrte und Artikel am Lebensende, die ihre eigenen Spalten haben.
    ${zeilen.some((o) => o.nur_pfad) ? "Grau: übergeordnete Ordner, in denen du keine Freigabe hast – nur der Weg zu deinen." : ""}
    ${zeilen.some((o) => o.teilweise) ? "„Gesperrt (deine Artikel)“: deine gesperrten Artikel in einer Gliederung, die du sonst nicht siehst." : ""}`;
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

  /* Set-Protokolle eines Durchgangs (Schritt 27): je Set der Pfad (Link nur, wenn das Konto den Ordner sieht), Zahl der
     Artikel, Protokoll-ID und „PDF“ – als Liste wie die Durchgänge, am Telefon untereinander. */
  function setProtokolleHtml(liste) {
    return `<ul class="mat-runden mat-setprotokolle">${liste.map((t) => `<li>${t.ordner_sichtbar ? `<a href="/materialablage/ordner/${t.folder_id}"><strong>${esc(t.ordner)}</strong></a>` : `<strong>${esc(t.ordner)}</strong>`}
      <span class="muted">${plural(t.artikel, "Artikel", "Artikel")} · <span class="mat-hash">${esc(t.protokoll.id)}</span></span>
      <a class="mat-pdf" href="${esc(t.protokoll.url)}" target="_blank" rel="noopener" aria-label="Set-Protokoll ${esc(t.protokoll.id)} (PDF)" title="Set-Protokoll ${esc(t.protokoll.id)} öffnen">PDF</a></li>`).join("")}</ul>`;
  }
  /* Ordnerseite eines Sets: seine Set-Protokolle und die Sammelprotokolle der Durchgänge, die für ihn eröffnet wurden –
     der Durchgang als Link nur, wenn das Konto ihn sieht. Die Überschrift nennt, was darin steht. */
  const protokollArt = (x) => (x.art === "set" ? "Set-Protokoll" : "Sammelprotokoll");
  function sammelprotokolleTitel(liste) {
    const arten = new Set(liste.map(protokollArt));
    return arten.size > 1 ? "Set- und Sammelprotokolle" : arten.has("Set-Protokoll") ? "Set-Protokolle" : "Sammelprotokolle";
  }
  function sammelprotokolleHtml(liste) {
    return `<ul class="mat-runden mat-setprotokolle">${liste.map((x) => `<li>${x.durchgang.sichtbar ? `<a href="/materialablage/durchgang/${x.durchgang.id}"><strong>${esc(x.durchgang.titel)}</strong></a>` : `<strong>${esc(x.durchgang.titel)}</strong>`}
      <span class="muted">${protokollArt(x)} · ${esc(fmtTag(x.geschlossen_am))} · <span class="mat-hash">${esc(x.protokoll.id)}</span></span>
      <a class="mat-pdf" href="${esc(x.protokoll.url)}" target="_blank" rel="noopener" aria-label="${protokollArt(x)} ${esc(x.protokoll.id)} (PDF)" title="${protokollArt(x)} ${esc(x.protokoll.id)} öffnen">PDF</a></li>`).join("")}</ul>`;
  }

  /* Laufende Prüfdurchgänge: auf der Übersicht nur, wenn einer läuft; auf „Prüfungen“ immer (mitLeer) – dort ohne die
     abgeschlossenen und abgebrochenen. Die standen bis zum Wunsch vom 27.10.2026 zugeklappt darunter und wuchsen jedes
     Jahr; jetzt haben sie eine eigene Seite (Menü „Prüfdurchgänge“ → „Abgeschlossene Prüfdurchgänge“, durchgaengeArchiv). */
  const rundenZeilen = (l) => `<ul class="mat-runden">${l.map((r) => `<li><a href="/materialablage/durchgang/${r.id}"><strong>${esc(r.titel)}</strong></a>
          <span class="muted">${esc(r.ordner)} · eröffnet ${esc(fmtTag(r.eroeffnet_am))}</span>
          ${fortschritt(r.zaehlung)}</li>`).join("")}</ul>`;
  async function rundenKasten(ziel, mitLeer) {
    if (!ziel) return;
    try {
      const liste = (await api(`${API}/durchgaenge?offen=1`)).durchgaenge;
      if (!liste.length && !mitLeer) { ziel.innerHTML = ""; return; }
      ziel.innerHTML = `<section class="section"><h2>Laufende Prüfdurchgänge</h2>
        ${liste.length ? rundenZeilen(liste) : leer("Gerade läuft kein Prüfdurchgang.")}</section>`;
    } catch (e) { ziel.innerHTML = ""; }
  }
  /* Sammelprotokoll eines beendeten Durchgangs als „PDF“ (Prüfungen, abgeschlossene Prüfdurchgänge). */
  const sammelPdf = (r) => (r.protokoll ? `<a class="mat-pdf" href="${esc(r.protokoll.url)}" target="_blank" rel="noopener" aria-label="Sammelprotokoll ${esc(r.protokoll.id)} (PDF)" title="Sammelprotokoll ${esc(r.protokoll.id)} öffnen">PDF</a>` : "");
  function fortschritt(z) {
    const fertig = z.erledigt + z.ausgenommen;
    const proz = z.gesamt ? Math.round((100 * fertig) / z.gesamt) : 0;
    return `<span class="mat-fortschritt" title="${fertig} von ${z.gesamt} erledigt oder ausgenommen"><span style="width:${proz}%"></span></span>
      <span class="small">${fertig}/${z.gesamt}${z.in_pruefung ? ` · ${z.in_pruefung} in Prüfung` : ""}</span>`;
  }

  /* Artikelliste als Tabelle; mit auswahl:true bekommt jede Zeile ein Häkchen (Mehrfachauswahl). */
  /* Sortierbare Spaltenköpfe. Sortiert wird auf dem Server (die Listen kommen seitenweise); ein Klick sortiert
     aufsteigend, der nächste auf dieselbe Spalte absteigend. sort = { feld, richtung } oder null. */
  function sortKnopf(titel, feld, sort) {
    if (!sort) return esc(titel);
    const an = sort.feld === feld;
    return `<button type="button" class="mat-sort${an ? " an" : ""}" data-act="sortieren" data-feld="${feld}"
      title="nach ${esc(titel)} sortieren">${esc(titel)}<span class="mat-sort-pfeil" aria-hidden="true">${an ? (sort.richtung === "ab" ? "▼" : "▲") : "↕"}</span></button>`;
  }
  /* mehr (Lieferung 5): klasse am <th>; vor/nach: Köpfe zusammengelegter Spalten, die nur die enge Tabelle (601–820 px
     Inhaltsbreite) zeigt – ihre eigene Spalte (mat-schmal-weg, mat-eng-weg) entfällt dort, der Inhalt steht klein in
     dieser Zelle. */
  function sortKopf(titel, feld, sort, mehr) {
    mehr = mehr || {};
    const an = sort && sort.feld === feld;
    const zustand = !sort ? "" : ` aria-sort="${an ? (sort.richtung === "ab" ? "descending" : "ascending") : "none"}"`;
    return `<th${zustand}${mehr.klasse ? ` class="${mehr.klasse}"` : ""}>${mehr.vor || ""}${sortKnopf(titel, feld, sort)}${mehr.nach || ""}</th>`;
  }
  // Ein Kopf einer zusammengelegten Spalte im Kopf der Nachbarspalte (enge Tabelle); art: "schmal" oder "eng".
  const kopfZusatz = (titel, feld, sort, art) => `<span class="mat-${art}-zusatz mat-kopf-zusatz">${sort ? sortKnopf(titel, feld, sort) : esc(titel)}</span>`;
  /* Über den Karten (bis 600 px Inhaltsbreite) fehlt der Tabellenkopf – und mit ihm Sortierung und „alle auswählen“. Die Zeile hier
     holt beides zurück: „Sortieren nach“ mit denselben Spalten (felder: [[Titel, feld], …]), daneben die Richtung, und
     bei Mehrfachauswahl das Kästchen für alle. Breiter ist sie unsichtbar (material.css). */
  function kartenKopf(felder, sort, auswahl) {
    if (!sort && !auswahl) return "";
    const richtung = sort && sort.feld ? `<button type="button" class="btn secondary small mat-sortrichtung" data-act="sortieren" data-feld="${esc(sort.feld)}"
      aria-label="Reihenfolge umkehren">${sort.richtung === "ab" ? "▼ absteigend" : "▲ aufsteigend"}</button>` : "";
    return `<div class="mat-kartenkopf">
      ${auswahl ? '<label class="mat-wahl-feld mat-alle-feld"><input type="checkbox" class="mat-alle" aria-label="alle auswählen"><span>alle auswählen</span></label>' : ""}
      ${sort ? `<div class="mat-sortwahl"><label for="mat-sortwahl">Sortieren nach</label>
        <select id="mat-sortwahl" data-sortwahl><option value="">Vorgabe</option>${felder.map(([t, f]) => `<option value="${f}" ${sort.feld === f ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>${richtung}</div>` : ""}
    </div>`;
  }
  const ARTIKEL_SORT = [["Inventar-Nr.", "inventar"], ["Hersteller", "hersteller"], ["Produkt", "produkt"], ["Seriennummer", "serie"],
                        ["Nächste Prüfung", "faellig"], ["Status", "status"]];
  // Mit Spalte „Kategorie“ (nur die Artikelliste des Ordners, Wunsch vom 25.10.2026, F3) steht sie vorn.
  const ARTIKEL_SORT_KAT = [["Kategorie", "kategorie"]].concat(ARTIKEL_SORT);
  const sortWeiter = (sort, feld) => (sort.feld === feld ? { feld, richtung: sort.richtung === "auf" ? "ab" : "auf" } : { feld, richtung: "auf" });
  const sortParameter = (q, sort) => { if (sort && sort.feld) { q.set("sort", sort.feld); q.set("richtung", sort.richtung); } return q; };
  // Ein Produkt in Listen: Hersteller in eigener Spalte, hier Bild, Modell mit Beschreibung und Artikelnummer.
  // Die Länge eines Artikels (Schritt 20) steht grau hinter dem Produkt – nur, wo eine hinterlegt ist. Der Name ist ein
  // roter Link auf den Artikel und hebt sich so von Bemerkung, Artikelnummer und Länge ab (Wunsch des Nutzers,
  // 23.10.2026); für die Tastatur reicht der Link der Inventar-Nr. – daher tabindex -1. Ohne Sicht (fremde Zeile im
  // Durchgang) bleibt der Name Text.
  const produktZelle = (a, link = true) => `${a.vorschau ? `<img class="mat-mini" src="${esc(a.vorschau)}" alt="" loading="lazy">` : ""}${link ? `<a class="mat-produktname" href="/materialablage/artikel/${a.id}" tabindex="-1">${nameHtml(a, true)}</a>${zusatzHtml(a)}${artNrKurz(a.article_no)}` : `${nameHtml(a, true)}${zusatzHtml(a)}${artNrKurz(a.article_no)}`}${a.length_m ? ` <span class="muted small mat-laenge">${esc(laengeText(a.length_m))}</span>` : ""}${demoMarke(a.demo)}`;

  /* Drei Gestalten je nach Breite des Inhalts (material.css, „Lieferung 5 – Geräte: listen“): ab 821 px alle Spalten;
     601–820 px eine engere Tabelle – Seriennummer unter der Inventar-Nr., Hersteller über dem Produkt, nächste Prüfung
     unter dem Status; bis 600 px je Artikel eine Karte, ebenso zusammengefasst, unten Häkchen und „Prüfen“.
     opts.kategorie (Ordnerliste, Wunsch vom 25.10.2026): erste Spalte „Kategorie“ – eng und als Karte klein grau über
     Hersteller und Produkt; mit Kategorie bis 899 px eng, zwischen 900 und 979 px klein über dem Hersteller
     (material.css, .mat-kat-zusatz). */
  function artikelTabelle(liste, opts) {
    opts = opts || {};
    const s = opts.sort || null;
    // Weiche Trennstellen in den längsten Wörtern der Liste: Zwischen 821 und 900 px Inhaltsbreite (Fold aufgeklappt,
    // Tablet neben der Leiste) ragte die volle Tabelle sonst um wenige Pixel über den Rand (zweite Nachbesserung).
    const naechste = (a) => (a.status === "neu" ? "Eingangs\u00adprüfung" : a.lock_state !== "frei" || !a.next_due_on ? "" : fmtTag(a.next_due_on));
    const gesperrte = opts.auswahl && liste.some((a) => a.lock_state !== "frei");
    const kat = Boolean(opts.kategorie);
    return `${kartenKopf(kat ? ARTIKEL_SORT_KAT : ARTIKEL_SORT, s, opts.auswahl)}<table class="list mat-tabelle mat-karten mat-artikel${kat ? " mat-mit-kategorie" : ""}">
      <thead><tr>${opts.auswahl ? '<th class="mat-wahlspalte"><label class="mat-wahl-feld"><input type="checkbox" id="mat-alle" class="mat-alle" aria-label="alle auswählen"></label></th>' : ""}
        ${kat ? sortKopf("Kategorie", "kategorie", s, { klasse: "mat-schmal-weg mat-kategorie" }) : ""}${sortKopf("Inventar-Nr.", "inventar", s, { nach: kopfZusatz("Seriennummer", "serie", s, "schmal") })}${sortKopf("Hersteller", "hersteller", s, { klasse: "mat-schmal-weg", vor: kat ? kopfZusatz("Kategorie", "kategorie", s, "kat") : "" })}${sortKopf("Produkt", "produkt", s, { vor: `${kat ? kopfZusatz("Kategorie", "kategorie", s, "schmal") : ""}${kopfZusatz("Hersteller", "hersteller", s, "schmal")}`, nach: opts.person ? kopfZusatz("Person", "", null, "eng") : "" })}${sortKopf("Serien\u00adnummer", "serie", s, { klasse: "mat-schmal-weg" })}
        ${opts.person ? '<th class="mat-eng-weg">Person</th>' : ""}${opts.pfad ? "<th>Ablage</th>" : ""}${sortKopf("Nächste Prüfung", "faellig", s, { klasse: "mat-schmal-weg" })}${sortKopf("Status", "status", s, { nach: kopfZusatz("Nächste Prüfung", "faellig", s, "schmal") })}${opts.pruefen ? "<th></th>" : ""}</tr></thead>
      <tbody>${liste.map((a) => `<tr data-id="${a.id}">
        ${opts.auswahl ? `<td class="mat-wahlspalte mat-k-wahl">${wahlFeld(a)}</td>` : ""}
        ${kat ? `<td data-l="Kategorie" class="mat-schmal-weg mat-kategorie">${a.kategorie ? esc(a.kategorie.name) : ""}</td>` : ""}
        <td data-l="Inventar-Nr." class="mat-k-titel"><a class="mat-inv" href="/materialablage/artikel/${a.id}"><strong>${esc(a.inventory_no)}</strong></a>
          <div class="mat-schmal-zusatz small muted">SN ${esc(a.serial_no)}${a.serial_generated ? " (System)" : ""}</div></td>
        <td data-l="Hersteller" class="mat-schmal-weg">${kat && a.kategorie ? `<div class="mat-kat-zusatz small muted">${esc(a.kategorie.name)}</div>` : ""}${esc(a.manufacturer || "")}</td>
        <td data-l="Produkt" class="mat-k-ohne">${kat && a.kategorie ? `<div class="mat-schmal-zusatz small muted">${esc(a.kategorie.name)}</div>` : ""}${a.manufacturer ? `<div class="mat-schmal-zusatz small muted">${esc(a.manufacturer)}</div>` : ""}${produktZelle(a)}${opts.person && a.zugeordnet_name ? `<div class="mat-eng-zusatz small muted">${esc(a.zugeordnet_name)}</div>` : ""}</td>
        <td data-l="Seriennummer" class="mat-schmal-weg">${esc(a.serial_no)}${a.serial_generated ? ' <span class="muted" title="vom System vergeben">(System)</span>' : ""}</td>
        ${opts.person ? `<td data-l="Person" class="mat-eng-weg mat-k-halb">${a.zugeordnet_name ? person(a.zugeordnet_name) : ""}</td>` : ""}
        ${opts.pfad ? `<td data-l="Ablage">${esc(a.pfad || "")}</td>` : ""}
        <td data-l="Nächste Prüfung" class="mat-schmal-weg">${naechste(a) && a.status !== "neu" ? esc(naechste(a)) : `<span class="muted">${esc(naechste(a) || "–")}</span>`}</td>
        <td data-l="Status" class="mat-k-marke">${statusMarke(a.status)}${empfohlenMarke(a.aussonderung_empfohlen)}${a.rueckruf ? ` <span class="mat-rr-marke" title="Rückruf: ${esc(a.rueckruf)}">Rückruf</span>` : ""}${mangelMarke(a.mangel)}${a.entwurf ? `<div class="small muted">in Prüfung bei ${esc(a.entwurf.pruefer || "?")}</div>` : ""}${naechste(a) ? `<div class="mat-schmal-zusatz small${a.status === "neu" ? " muted" : ""}">${a.status === "neu" ? "" : "fällig "}${esc(naechste(a))}</div>` : ""}</td>
        ${opts.pruefen ? `<td class="tabelle-aktionen">${pruefKnopf(a)}</td>` : ""}</tr>`).join("")}</tbody></table>
      ${gesperrte ? '<p class="help mat-wahl-hinweis">Graue Kästchen: Gesperrte und ausgesonderte Artikel bleiben in ihrem Systemordner und lassen sich nicht verschieben.</p>' : ""}`;
  }
  /* Häkchen der Mehrfachauswahl mit Beschriftung: In der Tabelle füllt das Label die Zelle (am Finger ein großes
     Ziel), in der Karte steht „auswählen“ daneben – bei gesperrten Artikeln stattdessen, warum es nicht geht (ein title
     erscheint ohne Maus nie). */
  function wahlFeld(a) {
    const frei = a.lock_state === "frei";
    const grund = a.lock_state === "ausgesondert" ? "ausgesondert" : "gesperrt";
    return `<label class="mat-wahl-feld"><input type="checkbox" class="mat-wahl-art" value="${a.id}"${a.zugeordnet_name ? ' data-person="1"' : ""} ${frei ? "" : 'disabled title="Gesperrte und ausgesonderte Artikel bleiben in ihrem Systemordner."'} aria-label="${esc(a.inventory_no)} auswählen">
      <span class="mat-wahl-text">${frei ? "auswählen" : `${grund} – bleibt im Systemordner`}</span></label>`;
  }
  // „Prüfen“ in Listen: mit Prüffreigabe für den Artikel, solange niemand anderes ihn reserviert hat.
  function pruefKnopf(a, durchgangId) {
    if (!(a.darf && a.darf.pruefen) || a.lock_state === "ausgesondert") return "";
    const q = durchgangId ? `?durchgang=${durchgangId}` : "";
    if (a.entwurf && a.entwurf.pruefer_id !== DARF.uid) return "";
    return a.entwurf ? `<a class="btn secondary small" href="/materialablage/pruefung/${a.entwurf.id}">Weiter prüfen</a>`
      : `<a class="btn secondary small" href="/materialablage/artikel/${a.id}/pruefung/neu${q}">Prüfen</a>`;
  }

  /* --- Fällige Prüfungen ------------------------------------------------------------------------ */
  async function pruefungen() {
    const params = new URLSearchParams(location.search);
    // Alles Fällige – wie bestand.FAELLIG auf dem Server (überfällig, Lebensdauer erreicht, neu, bald fällig).
    const FAELLIG = "ueberfaellig,lebensdauer,neu,bald_faellig";
    let filter = params.get("status") || FAELLIG;
    // Aus dem Ordner mit dem Filter „Zugeordnet an …“: nur Artikel dieser Person (der Server wendet ihn nur an, wo das
    // Grundrecht gilt).
    let zugeordnet = params.get("zugeordnet") || "";
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    const FILTER = [[FAELLIG, "alles Fällige"], ["ueberfaellig", "überfällig"], ["lebensdauer", "Lebensdauer erreicht"],
                    ["neu", "neu (Eingangsprüfung)"], ["bald_faellig", "bald fällig"], ["gesperrt", "gesperrt"],
                    ["einsatzbereit", "einsatzbereit"]];
    if (DATEN.ordner) leisteMarkieren(DATEN.ordner);
    async function liste() {
      const q = sortParameter(new URLSearchParams({ status: filter, seite, pro_seite: 50 }), sort);
      if (DATEN.ordner) q.set("ordner", DATEN.ordner);
      if (zugeordnet) q.set("zugeordnet", zugeordnet);
      const d = await api(`${API}/faellig?${q}`);
      const zuInfo = $("#pr-zu-info");
      if (zuInfo) zuInfo.innerHTML = infoKnopf("Zu prüfen", `Überfällig, Lebensdauer erreicht (die Prüfung endet mit „aussondern empfohlen“ oder „instandsetzen“), neu (die Eingangsprüfung steht aus) oder in den nächsten ${esc(String(d.schwelle_tage))} Tagen fällig. Prüfen lässt sich jeder Artikel aber jederzeit – auch aus seiner Ansicht.`);
      // Aus der Übersicht kommt die Liste nach Ordner gefiltert – samt Unterordnern; „alle Ordner“ hebt das auf.
      const ordnerZeile = d.ordner ? `<p class="mat-pr-ordner">Nur <a href="/materialablage/ordner/${d.ordner.id}">${esc(d.ordner.pfad.map((o) => o.name).join(" / "))}</a> mit Unterordnern
        · <a href="${adresse({ ordner: null })}">alle Ordner</a></p>` : "";
      const name = (d.artikel.find((a) => a.zugeordnet_name) || {}).zugeordnet_name;
      const personZeile = zugeordnet ? `<p class="mat-pr-ordner">Nur Artikel, die ${name ? esc(name) : "einer Person"} zugeordnet sind
        · <a href="${adresse({ zugeordnet: null })}">alle Personen</a></p>` : "";
      $("#pr-liste").innerHTML = `${ordnerZeile}${personZeile}
        <div class="c-tabs mat-filter">${FILTER.map(([f, t]) => `<button type="button" data-act="filter" data-f="${f}" class="${f === filter ? "sel" : ""}">${esc(t)}</button>`).join("")}</div>
        ${d.artikel.length ? artikelTabelle(d.artikel, { pfad: true, pruefen: d.artikel.some((a) => a.darf && a.darf.pruefen), sort }) : leer("Keine Artikel in dieser Auswahl.")}
        ${seitenleiste(d.gesamt, seite, 50)}`;
    }
    async function offene() {
      const liste = (await api(`${API}/entwuerfe`)).entwuerfe;
      $("#pr-offen").innerHTML = liste.length ? `<section class="section"><h2>Offene Prüfungen${infoKnopf("Offene Prüfungen", "Eine offene Prüfung reserviert ihren Artikel: Nur ihr Prüfer arbeitet daran weiter. Bleibt eine Prüfung liegen, hebt der Materialwart die Reservierung auf.")}</h2>
        <table class="list mat-tabelle mat-karten"><thead><tr><th>Artikel</th><th>Prüfung</th><th>Prüfer</th><th>begonnen</th><th></th></tr></thead><tbody>
        ${liste.map((x) => `<tr><td data-l="Artikel" class="mat-k-titel"><a href="/materialablage/artikel/${x.item_id}"><strong>${esc(x.artikel.inventory_no)}</strong></a> ${nameHtml(x.artikel)}${zusatzHtml(x.artikel)} <div class="small muted">${esc(x.artikel.pfad)}</div></td>
          <td data-l="Prüfung" class="mat-k-halb">${esc(PRUEFART_KURZ[x.art] || x.art)}</td><td data-l="Prüfer" class="mat-k-halb">${person(x.pruefer)}${x.eigen ? ' <span class="badge">du</span>' : ""}</td>
          <td data-l="begonnen">${esc(fmtZeit(x.begonnen_am))}</td>
          <td class="tabelle-aktionen">${x.eigen && x.artikel.darf && x.artikel.darf.pruefen ? `<a class="btn secondary small" href="/materialablage/pruefung/${x.id}">Weiter prüfen</a>` : `<a class="btn secondary small" href="/materialablage/pruefung/${x.id}">Ansehen</a>`}
            ${!x.eigen && x.artikel.darf && x.artikel.darf.verwalten ? `<button class="btn secondary small" data-act="freigeben" data-id="${x.id}" data-wer="${esc(x.pruefer)}">Reservierung aufheben</button>` : ""}</td></tr>`).join("")}
        </tbody></table></section>` : "";
    }
    /* „Prüfdurchgänge“ (Wunsch vom 27.10.2026) statt des Knopfs „Prüfdurchgang anlegen“: ein Untermenü mit „Prüfdurchgang
       anlegen“ (wer irgendwo verwaltet oder prüft – wie bisher der Knopf) und „Abgeschlossene Prüfdurchgänge“ (jeder
       mit Sicht; aus der Übersicht mit dem Ordner der Liste als Filter). */
    const rundenMenue = () => `<details class="mat-menue">
        <summary class="btn secondary" aria-haspopup="true">Prüfdurchgänge</summary>
        <div class="mat-menue-liste">
          ${DARF.verwalten || DARF.pruefen ? `<a href="#" role="button" data-act="runde"><strong>Prüfdurchgang anlegen</strong>
            <span>Alle Artikel eines Ordners auf eine gemeinsame Liste – mehrere Prüfer arbeiten sie gleichzeitig ab.</span></a>` : ""}
          <a href="/materialablage/durchgaenge${DATEN.ordner ? `?ordner=${Number(DATEN.ordner)}` : ""}"><strong>Abgeschlossene Prüfdurchgänge</strong>
            <span>Auch abgebrochene, nach Jahr des Abschlusses und Ordner – mit Sammelprotokoll.</span></a>
        </div></details>`;
    async function zeichnen() {
      seitenTitel("Prüfungen");
      inhalt.innerHTML = `<div class="page-head"><h1>Prüfungen</h1>
          <div class="btn-row"><a class="btn secondary" href="/materialablage/pruefen" title="Ist ein Protokoll oder Lebenslauf (PDF) unverändert?">Protokoll oder Lebenslauf prüfen</a>
            ${rundenMenue()}</div></div>
        ${!DARF.pruefen ? `<p class="notice">${pruefHinweis()}</p>` : ""}
        <div id="pr-runden"></div><div id="pr-offen"></div>
        <section class="section"><h2>Zu prüfen<span id="pr-zu-info"></span></h2><div id="pr-liste"><p class="help">Wird geladen …</p></div></section>`;
      await Promise.all([zeigenIn(liste, "#pr-liste"), zeigenIn(offene, "#pr-offen"), rundenKasten($("#pr-runden"), true)]);
    }
    // Die Adresse dieser Liste mit Ordner, Person und Filter – was in aendern null ist, fällt weg.
    function adresse(aendern) {
      const p = new URLSearchParams();
      const werte = Object.assign({ ordner: DATEN.ordner || null, zugeordnet: zugeordnet || null, status: filter }, aendern || {});
      Object.entries(werte).forEach(([k, w]) => { if (w !== null && w !== "") p.set(k, w); });
      return `/materialablage/pruefungen?${p}`;
    }
    aktionen = {
      filter: (b) => { filter = b.dataset.f; seite = 1; history.replaceState(null, "", adresse()); zeigenIn(liste, "#pr-liste"); },
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
    if (!(await confirm(`Die offene Prüfung von ${wer} verwerfen und die Reservierung aufheben? Ihre Befunde, Fotos und Anhänge gehen dabei verloren.`, "Reservierung aufheben"))) return;
    try { await api(`${API}/pruefungen/${pid}`, { method: "DELETE" }); toast("Reservierung aufgehoben"); await danach(); }
    catch (e) { toast(e.message, true); }
  }

  // Einen Durchgang eröffnet, wer den Ordner verwaltet oder dort prüfen darf – nur solche Ordner stehen zur Wahl.
  async function rundeDialog(ordnerId) {
    const liste = await ordnerBaum(true);
    const wahl = ordnerOptionen(liste, (o) => Boolean(o.darf && (o.darf.verwalten || o.darf.pruefen)), ordnerId, true);
    if (!wahl.anzahl) {
      toast(liste.some((o) => !o.system_kind) ? "Einen Prüfdurchgang eröffnet, wer den Ordner verwaltet oder dort eine Prüffreigabe hat."
        : "Zuerst unter „Bestand“ eine Gliederung anlegen.", true);
      return;
    }
    // Knopf und Dialog sagen dasselbe: „Prüfdurchgang anlegen“ (Browserprüfung vor dem Merge, Verbesserung 8).
    dialog(`<h2>Prüfdurchgang anlegen</h2>
      <p class="help">Alle Artikel im gewählten Ordner und darunter (ohne ausgesonderte) kommen auf eine gemeinsame Liste. Mehrere Prüfer arbeiten sie gleichzeitig ab; wer einen Artikel öffnet, reserviert ihn.</p>
      <label for="rd-titel">Titel</label><input type="text" id="rd-titel" maxlength="160" value="Jahresprüfung ${new Date().getFullYear()}">
      <label for="rd-ordner">Ordner</label><select id="rd-ordner">${wahl.html}</select>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="rd-ok" type="button">Prüfdurchgang anlegen</button></div>`,
    (dlg, body) => {
      fokus($("#rd-titel", body));
      $("#rd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge`, { method: "POST", body: { titel: $("#rd-titel", body).value, folder_id: +$("#rd-ordner", body).value } });
          location.href = `/materialablage/durchgang/${r.durchgang.id}`;
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Abgeschlossene Prüfdurchgänge (Wunsch vom 27.10.2026) ------------------------------------------------------
     Seite /materialablage/durchgaenge (Ansicht „durchgaenge“) aus dem Menü „Prüfdurchgänge“ auf „Prüfungen“: beendete
     Durchgänge (auch abgebrochene) je Jahr des Abschlusses, neueste zuerst. Je Jahr ein Abschnitt zum Aufklappen mit der
     Anzahl in der Überschrift; offen steht nur das neueste. Ein Jahr kommt erst beim Aufklappen vom Server
     (GET /durchgaenge?abgeschlossen=1&jahr=…, je DG_PRO_SEITE, darunter „Weitere anzeigen“) – bei vielen Durchgängen wird
     nie alles geladen. Filter: Ordner (sein Zweig; zur Wahl die sichtbaren Ordner ohne Systemordner, der Server prüft die
     Sicht) und Wörter im Titel; sie stehen in der Adresse (?ordner=&q=). Aufgeklappte Jahre, Nachgeladenes und die
     Scrollhöhe stehen im Eintrag des Verlaufs – zurück von einem Durchgang an dieselbe Stelle (wie im Katalog). Je
     Durchgang eine Zeile wie bisher auf „Prüfungen“: Titel (Link), Ordner, eröffnet, abgeschlossen, Stand, PDF; am
     Telefon als Karte (Container „mat-seite“). */
  const DG_PRO_SEITE = 50;
  async function durchgaengeArchiv() {
    const adresse = new URLSearchParams(location.search);
    let ordner = /^\d{1,12}$/.test(adresse.get("ordner") || "") ? +adresse.get("ordner") : null;
    let q = (adresse.get("q") || "").trim().slice(0, 200);
    const gemerkt = history.state && history.state.durchgaenge;
    let wiederher = gemerkt && gemerkt.ordner === ordner && gemerkt.q === q ? gemerkt : null;
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    let jahre = [];                      // [{jahr, anzahl}] unter den gewählten Filtern
    let stand = {};                      // je Jahr: { zeilen, seite, offen, fehler }
    let lauf = 0;
    const merken = () => {
      try {
        const geladen = {};
        Object.entries(stand).forEach(([j, x]) => { geladen[j] = x.zeilen.length; });
        history.replaceState(Object.assign({}, history.state, { durchgaenge: { ordner, q, geladen, y: Math.round(window.scrollY),
          offen: Object.keys(stand).filter((j) => stand[j].offen).map(Number) } }), "");
      } catch (e) { /* ohne Verlauf eben ohne Rückweg an die Stelle */ }
    };
    window.addEventListener("pagehide", merken);
    inhalt.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("a[href]")) merken(); }, true);
    const holen = (jahr, seite) => {
      const p = new URLSearchParams({ abgeschlossen: "1", seite: String(seite), pro_seite: String(DG_PRO_SEITE) });
      if (jahr) p.set("jahr", String(jahr));
      if (ordner) p.set("ordner", String(ordner));
      if (q) p.set("q", q);
      return api(`${API}/durchgaenge?${p}`);
    };
    const zeile = (r) => `<tr><td data-l="Prüfdurchgang" class="mat-k-titel"><a href="/materialablage/durchgang/${r.id}"><strong>${esc(r.titel)}</strong></a>${r.abgebrochen ? ' <span class="badge grey">abgebrochen</span>' : ""}</td>
        <td data-l="Ordner">${esc(r.ordner)}</td>
        <td data-l="eröffnet" class="mat-k-halb">${esc(fmtTag(r.eroeffnet_am))}</td>
        <td data-l="${r.abgebrochen ? "abgebrochen" : "abgeschlossen"}" class="mat-k-halb">${esc(fmtTag(r.geschlossen_am))}</td>
        <td data-l="Stand" class="mat-dg-stand">${fortschritt(r.zaehlung)}</td>
        <td class="tabelle-aktionen">${sammelPdf(r)}</td></tr>`;
    function listeHtml(j) {
      const x = stand[j.jahr];
      if (!x) return '<p class="help">Wird geladen …</p>';
      if (x.fehler) return `<p class="notice" role="alert">${esc(x.fehler)}</p>`;
      if (!x.zeilen.length) return leer("In diesem Jahr keine abgeschlossenen Prüfdurchgänge (mehr).");
      const rest = j.anzahl - x.zeilen.length;
      return `<table class="list mat-tabelle mat-karten mat-dg-tabelle"><thead><tr><th>Prüfdurchgang</th><th>Ordner</th><th>eröffnet</th><th>abgeschlossen</th><th>Stand</th><th></th></tr></thead>
        <tbody>${x.zeilen.map(zeile).join("")}</tbody></table>
        ${rest > 0 ? `<p class="mat-dg-mehr"><button type="button" class="btn secondary small" data-act="dg-mehr" data-jahr="${j.jahr}">Weitere anzeigen (${rest})</button></p>` : ""}`;
    }
    // Die Überschrift ist zugleich der Klappknopf (summary) – die Zahl sagt, wie viele darin stehen, auch zugeklappt.
    const jahrHtml = (j) => `<section class="section mat-dg-jahr"><details class="mat-dg-klapp" data-jahr="${j.jahr}"${stand[j.jahr] && stand[j.jahr].offen ? " open" : ""}>
        <summary><h2>${j.jahr} <span class="mat-dg-anzahl">· ${plural(j.anzahl, "Prüfdurchgang", "Prüfdurchgänge")}</span></h2></summary>
        <div class="mat-dg-liste" id="dg-liste-${j.jahr}">${listeHtml(j)}</div></details></section>`;
    function leerText() {
      const was = ordner && q ? "In diesem Ordner keine abgeschlossenen Prüfdurchgänge mit diesen Wörtern im Titel."
        : ordner ? "In diesem Ordner (mit Unterordnern) keine abgeschlossenen Prüfdurchgänge."
          : q ? "Keine abgeschlossenen Prüfdurchgänge mit diesen Wörtern im Titel." : "Noch keine abgeschlossenen Prüfdurchgänge.";
      return leer(was);
    }
    function jahreZeichnen() {
      $("#dg-jahre").innerHTML = jahre.length ? jahre.map(jahrHtml).join("") : leerText();
    }
    function jahrZeichnen(jahr) {
      const j = jahre.find((x) => x.jahr === jahr);
      const ziel = $(`#dg-liste-${jahr}`);
      if (j && ziel) ziel.innerHTML = listeHtml(j);
    }
    // Ein Jahr (weiter) laden, bis mindestens bis Zeilen da sind (höchstens 20 Seiten) – beim Aufklappen eine Seite.
    async function jahrLaden(jahr, bis) {
      const x = stand[jahr] || (stand[jahr] = { zeilen: [], seite: 0, offen: true });
      const meinLauf = lauf;
      try {
        do {
          const d = await holen(jahr, x.seite + 1);
          if (meinLauf !== lauf) return;
          x.seite += 1;
          x.zeilen = x.zeilen.concat(d.durchgaenge);
          const j = jahre.find((y) => y.jahr === jahr);
          if (j) j.anzahl = d.gesamt;
          if (!d.durchgaenge.length) break;
        } while (x.zeilen.length < Math.min(bis || 0, DG_PRO_SEITE * 20));
        x.fehler = null;
      } catch (e) { if (meinLauf === lauf) x.fehler = e.message; }
    }
    // Neu laden (Filter geändert oder erster Aufruf): Jahre und das neueste Jahr in einem Abruf.
    async function laden() {
      const meinLauf = ++lauf;
      let d;
      try { d = await holen(null, 1); }
      catch (e) {
        if (meinLauf === lauf) $("#dg-jahre").innerHTML = `<p class="notice" role="alert">${esc(e.message)}</p>`;
        return;
      }
      if (meinLauf !== lauf) return;
      jahre = d.jahre;
      stand = {};
      if (d.jahr && d.gesamt) stand[d.jahr] = { zeilen: d.durchgaenge, seite: 1, offen: true };
      const zurueck = wiederher;
      wiederher = null;
      if (zurueck) {
        // Zurück von einem Durchgang: dieselben Jahre auf (auch ein zugeklapptes neuestes), so viel wie vorher geladen.
        const auf = new Set(zurueck.offen || []);
        if (d.jahr && stand[d.jahr] && !auf.has(d.jahr)) stand[d.jahr].offen = false;
        for (const j of jahre) {
          if (!auf.has(j.jahr)) continue;
          if (!stand[j.jahr]) stand[j.jahr] = { zeilen: [], seite: 0, offen: true };
          const bis = (zurueck.geladen || {})[j.jahr] || 0;
          if (stand[j.jahr].zeilen.length < Math.min(bis, j.anzahl) || !stand[j.jahr].seite) await jahrLaden(j.jahr, bis);
          if (meinLauf !== lauf) return;
        }
      }
      jahreZeichnen();
      if (zurueck) window.scrollTo(0, zurueck.y || 0);
    }
    // Filter in die Adresse – ohne neuen Eintrag im Verlauf (wie die Filter auf „Prüfungen“).
    function adresseSetzen() {
      const p = new URLSearchParams();
      if (ordner) p.set("ordner", String(ordner));
      if (q) p.set("q", q);
      try { history.replaceState(history.state, "", `/materialablage/durchgaenge${String(p) ? `?${p}` : ""}`); } catch (e) { /* nur die Adresszeile */ }
    }

    seitenTitel("Abgeschlossene Prüfdurchgänge");
    const baum = await ordnerBaum().catch(() => []);
    const wahl = ordnerOptionen(baum, () => true, ordner, false);
    inhalt.innerHTML = `<div class="mat-pfad">${pfadHtml(['<a href="/materialablage/pruefungen">Prüfungen</a>', "<span>Abgeschlossene Prüfdurchgänge</span>"])}</div>
      <div class="page-head"><h1>Abgeschlossene Prüfdurchgänge</h1></div>
      <form class="mat-dg-filter" id="dg-filter" role="search" aria-label="Abgeschlossene Prüfdurchgänge filtern">
        <label for="dg-ordner">Ordner <select id="dg-ordner"><option value="">alle Ordner</option>${wahl.html}</select></label>
        <label for="dg-q">Im Titel <input type="search" id="dg-q" maxlength="200" value="${esc(q)}" autocomplete="off" enterkeyhint="search"></label>
      </form>
      <div id="dg-jahre"><p class="help">Wird geladen …</p></div>`;
    const feldOrdner = $("#dg-ordner");
    const feldQ = $("#dg-q");
    let warten = null;
    feldOrdner.addEventListener("change", () => { ordner = feldOrdner.value ? +feldOrdner.value : null; adresseSetzen(); laden(); });
    const suchen = () => {
      clearTimeout(warten);
      const neu = feldQ.value.trim().slice(0, 200);
      if (neu === q) return;
      q = neu;
      adresseSetzen();
      laden();
    };
    feldQ.addEventListener("input", () => { clearTimeout(warten); warten = setTimeout(suchen, 350); });
    $("#dg-filter").addEventListener("submit", (e) => { e.preventDefault(); suchen(); });
    // Ein Jahr aufklappen lädt es (beim ersten Mal); zuklappen merkt sich nur den Zustand. „toggle“ steigt nicht auf.
    inhalt.addEventListener("toggle", async (e) => {
      const k = e.target;
      if (!(k instanceof HTMLDetailsElement) || !k.classList.contains("mat-dg-klapp")) return;
      const jahr = +k.dataset.jahr;
      if (!k.open) { if (stand[jahr]) stand[jahr].offen = false; return; }
      if (stand[jahr] && !stand[jahr].fehler) { stand[jahr].offen = true; return; }
      delete stand[jahr];
      jahrZeichnen(jahr);
      await jahrLaden(jahr, 0);
      jahrZeichnen(jahr);
    }, true);
    aktionen = {
      "dg-mehr": async (b) => {
        const jahr = +b.dataset.jahr;
        const x = stand[jahr];
        if (!x || b.disabled) return;
        b.disabled = true;
        const vorher = x.zeilen.length;
        await jahrLaden(jahr, vorher + 1);
        jahrZeichnen(jahr);
        // Der Fokus geht auf die erste neue Zeile – der Knopf ist weg oder rückt nach unten.
        const neu = $$(`#dg-liste-${jahr} tbody tr`)[vorher];
        const link = neu && $("a", neu);
        if (link) link.focus();
      },
    };
    await laden();
  }

  /* --- Bestand ------------------------------------------------------------------------------------ */
  async function bestand() {
    const liste = await ordnerBaum();
    seitenTitel("Bestand");
    const info = `${BESTAND_INFO}${liste.some((o) => o.nur_pfad) ? " Grau: übergeordnete Ordner, in denen du keine Freigabe hast – nur der Weg zu deinen." : ""}
      <span class="info-absatz">${ZAEHLER_LEGENDE}</span>`;
    inhalt.innerHTML = `<div class="page-head"><h1>Bestand${infoKnopf("Bestand", info)}</h1>
        <div class="btn-row">${DARF.gliederung_anlegen ? '<button class="btn secondary" data-act="gliederung"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Gliederung<span class="k-anlegen"> anlegen</span></span></button>' : ""}
          ${DARF.verwalten || DARF.pruefen ? '<a class="btn secondary mat-mit-zahl" href="/materialablage/bestand/antraege">Änderungsanträge<span class="mat-meldezahl" id="bst-antraege" hidden></span></a>' : ""}</div></div>
      ${liste.length ? baumHtml(liste) : leer(DARF.lesen ? "Noch kein Ordner angelegt." : "Du hast noch keine Freigabe im Bestand – der Materialwart deiner Gliederung vergibt sie.")}`;
    aktionen = { gliederung: () => ordnerDialog({ kind: "gliederung" }, null) };
    antraegeZaehlen($("#bst-antraege"));
  }

  /* --- Foto im Dialog (Ordnerfoto, Produktbild – Lieferung 5) ------------------------------------------------
     Statt des nackten Dateifelds („Datei auswählen / Keine ausgewählt“, 21 px hoch) ein Knopf „Foto wählen“ –
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
          <div class="btn-row"><label class="btn secondary mat-bildwahl-knopf">${esc(wort)} wählen<input type="file" id="${id}"
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
    // Steht das Feld in einem gerade verborgenen Reiter („Ordner bearbeiten“ im Reiter „Freigaben“), nimmt es nichts.
    const aus = new AbortController();
    dlg.addEventListener("close", () => { aus.abort(); if (url) URL.revokeObjectURL(url); }, { once: true });
    const dateien = (ev) => ev.dataTransfer && Array.from(ev.dataTransfer.types || []).includes("Files");
    const sichtbar = () => !feld.closest("[hidden]");
    body.addEventListener("dragover", (ev) => { if (!dateien(ev)) return; ev.preventDefault(); if (sichtbar()) feld.classList.add("ueber"); }, { signal: aus.signal });
    body.addEventListener("dragleave", (ev) => { if (!body.contains(ev.relatedTarget)) feld.classList.remove("ueber"); }, { signal: aus.signal });
    body.addEventListener("drop", (ev) => {
      if (!dateien(ev)) return;
      ev.preventDefault();
      feld.classList.remove("ueber");
      if (!sichtbar()) { toast(`Das ${wort} des Ordners bitte im Reiter „Ordner“ ablegen.`, true); return; }
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
  // Im Telefon passte der volle Platzhalter nicht ins Feld (abgeschnitten) – dort ein kürzerer, der volle als Beschriftung.
  const KAT_SUCHE = "Produkte suchen: Hersteller, Modell, Bemerkung, Artikelnummer, Norm";
  // Welcher Platzhalter passt, entscheidet die Fensterbreite – auch nach dem Drehen des Geräts, nicht nur beim Zeichnen.
  const KAT_SCHMAL = matchMedia("(max-width: 640px)");
  const katPlatzhalter = () => (KAT_SCHMAL.matches ? "Hersteller, Modell, Art.-Nr., Norm" : KAT_SUCHE);
  KAT_SCHMAL.addEventListener("change", () => { const feld = document.getElementById("kat-q"); if (feld) feld.placeholder = katPlatzhalter(); });
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

  /* „Ordner anlegen“ und „Ordner bearbeiten“. Beim Bearbeiten hat der Dialog zwei Reiter: „Ordner“ (Name, Art,
     Intervall, Beschreibung, Foto – rote Hauptaktion „Speichern“) und „Freigaben“ (freigaben.js, MatFreigaben.inhalt –
     rote Hauptaktion „Freigabe erteilen“ im Reiter). Einen eigenen Knopf „Freigaben“ im Ordnerkopf gibt es nicht mehr.
     Den Reiter gibt es überall, wo es „Bearbeiten“ gibt, und nur dort: Beides verlangt verwalten am Ordner (PUT und
     GET …/freigaben, requires_folder("verwalten")), an Systemordnern gibt es keins von beiden – wer Freigaben vergeben
     darf, darf den Ordner also immer auch bearbeiten. Beide Reiter stehen die ganze Zeit im Dialog, beim Wechsel geht
     nichts verloren; Ändern, Entziehen und Verlängern öffnen eigene Dialoge darüber. Nur wer den Dialog aus dem Reiter
     „Freigaben“ heraus verlässt („Schließen“, Esc, „Dort öffnen“), während im Reiter „Ordner“ noch Ungespeichertes
     steht, wird vorher gefragt. optionen: reiter („freigaben“ öffnet dort), vorlage (an MatFreigaben.inhalt, auch
     „verlaengern“), nachFreigaben (nach dem Schließen, wenn sich an den Freigaben etwas geändert hat). */
  function ordnerDialog(o, parentId, optionen) {
    const opt = optionen || {};
    const neu = !o.id;
    const oben = neu && !parentId;
    // Einen vorhandenen Ordner zur Gliederung machen heißt: alles darin wechselt die Gliederung. Das darf nur, wer die
    // bisherige Gliederung verwaltet (1.7 Nr. 2, wie beim Verschieben) – sonst fehlt die Art in der Auswahl. Solange
    // der Baum fehlt, entscheidet der Server.
    const umwandeln = neu || o.kind === "gliederung" || !Object.keys(baumIndex).length || verwaltet(gliederungVon(parentId));
    const arten = Object.entries(ORDNERART).filter(([k]) => k !== "gliederung" || umwandeln);
    const F = window.MatFreigaben;
    const mitFreigaben = !neu && !o.system_kind && verwaltet(o) && !!F;
    // „Erinnerungsmails aus“ nur an einem vorhandenen Ordner (kein Systemordner). Das Kästchen zeigt den eigenen Wert;
    // ist es ohnehin aus, weil ein Oberordner abschaltet, sagt der Hinweis, wo.
    const mitErinnerung = !neu && !o.system_kind;
    const geerbt = mitErinnerung && o.erinnerungen && o.erinnerungen.geerbt_von;
    const erinnerungFeld = mitErinnerung ? `<label class="inline"><input type="checkbox" id="od-erinnerung" ${o.reminders_off ? "checked" : ""}> Erinnerungsmails aus</label>
      <div class="help">Für diesen Ordner und alle Unterordner bekommt niemand eine Sammelmail zu Fälligkeit und Lebensende –
        auch nicht die Verwalter der Ordner darüber und die Material-Verwaltung. Ablaufende Freigaben melden sich weiter, ebenso
        „Deine PSA“ an die Personen, denen hier etwas zugeordnet ist (abbestellen kann das jede selbst im Profil).</div>
      ${geerbt ? `<div class="help">Ohnehin aus – geerbt von „${esc(geerbt.pfad)}“.</div>` : ""}` : "";
    const formular = `<label for="od-name">Name</label><input type="text" id="od-name" value="${esc(o.name || "")}" maxlength="120">
      <div class="field-row">
        <div><label for="od-kind">Art</label><select id="od-kind" ${oben || o.kind === "gliederung" ? "disabled" : ""}>
          ${arten.map(([k, t]) => `<option value="${k}" ${(o.kind || "standort") === k ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
          ${o.kind === "gliederung" && !neu ? '<div class="help">Eine Gliederung bleibt eine Gliederung.</div>' : ""}</div>
        <div><label for="od-int">Prüfintervall (Monate)${infoKnopf("Prüfintervall", "Nur zum Verschärfen: Gilt die Herstellervorgabe kürzer, gilt sie.")}</label><input type="number" id="od-int" min="1" max="120" value="${o.interval_months || ""}" placeholder="vom Produkt"></div>
      </div>
      ${erinnerungFeld}
      <label for="od-desc">Beschreibung</label><textarea id="od-desc" rows="3" maxlength="2000">${esc(o.description || "")}</textarea>
      ${fotoFeld("od-foto", "Foto", "Foto", o.foto ? o.vorschau || o.foto : "", "JPEG, PNG, WebP oder HEIC vom Telefon; Web- und Vorschaufassung entstehen beim Hochladen.")}`;
    // Die Knopfzeile bleibt letztes Kind des Dialogs – so klebt sie am Telefon unten (app.css). Mit Reitern zeigt sie,
    // was zum gewählten gehört (data-fuer): „Abbrechen“ und „Speichern“ bzw. „Schließen“.
    // Neu unter einem Ordner heißt der Knopf „Unterordner anlegen“ – der Dialog ebenso (Verbesserung 8).
    const titel = neu ? (oben ? "Gliederung anlegen" : "Unterordner anlegen") : "Ordner bearbeiten";
    dialog(mitFreigaben ? `<h2 id="od-titel">${titel}</h2>
      <div class="c-tabs reiter-linie mat-reiter" role="tablist" aria-labelledby="od-titel">
        <button type="button" role="tab" id="od-reiter-ordner" aria-controls="od-teil-ordner" data-reiter="ordner">Ordner</button>
        <button type="button" role="tab" id="od-reiter-freigaben" aria-controls="od-teil-freigaben" data-reiter="freigaben">Freigaben</button></div>
      <div class="mat-reiter-teil" role="tabpanel" id="od-teil-ordner" aria-labelledby="od-reiter-ordner">${formular}</div>
      <div class="mat-reiter-teil" role="tabpanel" id="od-teil-freigaben" aria-labelledby="od-reiter-freigaben" hidden></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button" data-fuer="ordner">Abbrechen</button>
        <button class="btn" id="od-ok" type="button" data-fuer="ordner">Speichern</button>
        <button class="btn secondary" id="od-schliessen" type="button" data-fuer="freigaben" hidden>Schließen</button></div>`
      : `<h2>${titel}</h2>${formular}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="od-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
    (dlg, body) => {
      const fotoWahl = fotoFeldVerdrahten(dlg, body, "od-foto");
      if (mitFreigaben) reiterVerdrahten(dlg, body, o, fotoWahl, opt);
      else fokus($("#od-name", body));
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
        if (mitErinnerung) daten.reminders_off = $("#od-erinnerung", body).checked;
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
          // Eine neue Gliederung braucht als Erstes ihren Materialwart: „Ordner bearbeiten“ öffnet dort im Reiter
          // „Freigaben“ mit dieser Vorlage.
          location.href = `/materialablage/ordner/${oid}${oben ? "?freigaben=materialwart" : ""}`;
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* Die Reiter von „Ordner bearbeiten“ (role tablist/tab/tabpanel; ← und → wechseln, Pos1 und Ende springen). Den
     Reiter „Freigaben“ füllt MatFreigaben.inhalt beim ersten Zeigen – wer nur den Namen ändert, lädt keine Freigaben. */
  function reiterVerdrahten(dlg, body, o, fotoWahl, opt) {
    const reiter = $$('[role="tab"]', body);
    const teilFreigaben = $("#od-teil-freigaben", body);
    let aktiv = null;
    let geladen = false;
    let geaendert = false;
    // Ungespeichert im Reiter „Ordner“: ein Feld anders als beim Öffnen oder ein Foto gewählt bzw. zum Entfernen vorgemerkt.
    const felder = () => JSON.stringify(["od-name", "od-kind", "od-int", "od-desc"].map((id) => $(`#${id}`, body).value)
      .concat($("#od-erinnerung", body) ? [$("#od-erinnerung", body).checked] : []));
    const anfang = felder();
    const ungespeichert = () => felder() !== anfang || !!fotoWahl.datei || fotoWahl.entfernen;
    async function verlassenOk() {
      if (!ungespeichert()) return true;
      if (await confirm("Im Reiter „Ordner“ stehen noch ungespeicherte Änderungen. Verwerfen?", "Verwerfen")) return true;
      zeigenReiter("ordner", true);
      return false;
    }
    function zeigenReiter(name, fokusReiter, fokusInhalt) {
      aktiv = name;
      reiter.forEach((t) => {
        const an = t.dataset.reiter === name;
        t.setAttribute("aria-selected", String(an));
        t.tabIndex = an ? 0 : -1;
        t.classList.toggle("sel", an);
        if (an && fokusReiter) t.focus();
      });
      $("#od-teil-ordner", body).hidden = name !== "ordner";
      teilFreigaben.hidden = name !== "freigaben";
      $$("[data-fuer]", body).forEach((b) => { b.hidden = b.dataset.fuer !== name; });
      if (name === "freigaben" && !geladen) {
        geladen = true;
        window.MatFreigaben.inhalt(teilFreigaben, o, {
          vorlage: opt.vorlage, fokus: !!fokusInhalt,
          geaendert: () => { geaendert = true; },
          // „Dort öffnen“ (geerbte Zeile): zum Oberordner, dort gleich in diesen Reiter.
          dort: async (id) => { if (await verlassenOk()) location.href = `/materialablage/ordner/${id}?freigaben`; },
        });
      } else if (name === "ordner" && fokusInhalt) {
        fokus($("#od-name", body));
      }
    }
    reiter.forEach((t) => t.addEventListener("click", () => zeigenReiter(t.dataset.reiter)));
    $('[role="tablist"]', body).addEventListener("keydown", (e) => {
      const i = reiter.findIndex((t) => t.dataset.reiter === aktiv);
      const ziel = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: reiter.length - 1 }[e.key];
      if (ziel === undefined) return;
      e.preventDefault();
      zeigenReiter(reiter[(ziel + reiter.length) % reiter.length].dataset.reiter, true);
    });
    $("#od-schliessen", body).addEventListener("click", async () => { if (await verlassenOk()) dlg.close(); });
    // Esc im Reiter „Freigaben“ fragt wie „Schließen“ (im Reiter „Ordner“ verwirft Esc wie „Abbrechen“).
    const abbruch = (e) => {
      if (aktiv !== "freigaben" || !ungespeichert()) return;
      e.preventDefault();
      verlassenOk().then((ok) => { if (ok) dlg.close(); });
    };
    dlg.addEventListener("cancel", abbruch);
    // #dlg dient allen Dialogen der Seite: Breite und Esc-Rückfrage gelten nur, solange dieser offen ist. Hat sich an
    // den Freigaben etwas geändert, zeichnet die Ordneransicht danach neu (eigene Rechte, Ablaufhinweis).
    dlg.classList.add("mat-ordner-reiter");
    dlg.addEventListener("close", () => {
      dlg.classList.remove("mat-ordner-reiter");
      dlg.removeEventListener("cancel", abbruch);
      if (geaendert && opt.nachFreigaben) opt.nachFreigaben();
    }, { once: true });
    // Direkt in „Freigaben“: showModal hat den Fokus schon aufs erste Bedienelement gesetzt – den Reiter „Ordner“.
    // Er geht auf den gewählten Reiter, bis MatFreigaben.inhalt geladen hat und ihn in den Inhalt setzt.
    const start = opt.reiter === "freigaben" ? "freigaben" : "ordner";
    zeigenReiter(start, start === "freigaben", true);
  }

  // Hinweise der Verschieben-Dialoge (Bauentwurf 1.7): was mit Freigaben, Systemordnern und Durchgängen geschieht.
  const ORDNER_VERSCHIEBEN = "Freigaben an diesem Ordner wandern mit; was vom alten Oberordner geerbt war, gilt hier nicht mehr, was am neuen Ort gilt, kommt dazu.";
  const ORDNER_WECHSEL = "Gesperrte und ausgesonderte Artikel aus diesem Ordner wandern in die Systemordner der neuen Gliederung; offene Durchgänge der alten Gliederung nehmen die Artikel mit Grund aus.";
  const GLIEDERUNG_WECHSEL = "Die Gliederung behält ihre Systemordner; offene Durchgänge der alten Gliederung nehmen ihre Artikel mit Grund aus.";
  const ARTIKEL_VERSCHIEBEN = "Am neuen Ort gelten die Freigaben des Zielordners. Steht ein Artikel in einem offenen Prüfdurchgang, dessen Bereich er verlässt, nimmt ihn der Durchgang mit Grund aus.";
  const ARTIKEL_WECHSEL = "Das Ziel liegt in einer anderen Gliederung: Wer nur dort eine Freigabe hat, wo der Artikel jetzt liegt, sieht ihn danach nicht mehr.";
  // Nach einem Verschieben: Die Leiste zeigt den neuen Baum (der Inhalt lädt ohnehin neu).
  function leisteNeu() {
    ordnerBaum(true).then((l) => { if (leisteDaten && !LEISTE_KATALOG) { leisteDaten = l; leisteZeichnen(); } }).catch(() => {});
  }

  async function ordner() {
    const id = DATEN.id;
    let filter = "";
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    let person = "";                 // Filter „Zugeordnet an“: Kennung des Kontos
    let personen = null;             // Konten mit Zuordnungen im Zweig – nur mit Grundrecht geholt
    let kategorie = "";              // Filter „Kategorie“ (Wunsch vom 25.10.2026): Kennung der Kategorie
    let kategorieName = "";          //   … und ihr Name, falls sie nach einer Änderung nicht mehr in der Liste steht
    let kategorienZuletzt = [];      //   … und die zuletzt vollständige Liste (Name und Platz bei 0 Treffern)
    let nachFilter = null;           // nach einer Wahl im Filtermenü: wohin der Fokus geht (Selektor) bzw. "liste"
    let grund = false;               // Grundrecht am Ordner – bekannt nach dem ersten Zeichnen
    let kopfEl = null;               // Ablaufhinweis der Freigaben: einmal geholt, bei jedem Zeichnen wieder eingesetzt
    // Die Personen für den Filter (nur mit Grundrecht). Hat die gewählte inzwischen keine Zuordnung mehr, gilt er nicht.
    async function personenHolen() {
      try { personen = (await api(`${API}/ordner/${id}/zugeordnete`)).zugeordnete; } catch (e) { personen = []; }
      if (person && !personen.some((p) => String(p.id) === person)) person = "";
    }
    // ?freigaben=<vorlage> (nach „Gliederung anlegen“ mit „materialwart“; „verlaengern“; leer aus „Dort öffnen“ und der
    // Nutzerverwaltung): „Ordner bearbeiten“ einmal im Reiter „Freigaben“ öffnen und den Wert aus der Adresse nehmen –
    // sonst ginge der Dialog bei jedem Neuladen wieder auf.
    const adresse = new URLSearchParams(location.search);
    // ?status=… (Link der Übersicht „Aussonderung empfohlen“, A4): der Statusfilter gleich gesetzt.
    const vorgabeStatus = adresse.get("status");
    if (vorgabeStatus && (vorgabeStatus === EMPFOHLEN || Object.prototype.hasOwnProperty.call(STATUS, vorgabeStatus))) filter = vorgabeStatus;
    let vorlage = adresse.get("freigaben");
    if (vorlage !== null) {
      adresse.delete("freigaben");
      try { history.replaceState(null, "", location.pathname + (String(adresse) ? `?${adresse}` : "")); } catch (e) { /* nur die Adresszeile */ }
    }
    // „Ordner bearbeiten“ für den zuletzt gezeichneten Ordner. Haben sich darin Freigaben geändert, gilt der Ordner nach
    // dem Schließen neu: eigene Rechte, Ablaufhinweis (Rückruf statt einer Kennzeichnung am gemeinsamen #dlg).
    let jetzt = null;
    const nachFreigaben = () => { kopfEl = null; zeigen(zeichnen); };
    const bearbeiten = (opt) => { if (jetzt) ordnerDialog(jetzt, jetzt.parent_id, Object.assign({ nachFreigaben }, opt)); };
    const freigabenOeffnen = (v) => bearbeiten({ reiter: "freigaben", vorlage: v || undefined });
    async function zeichnen() {
      if (grund && personen === null) await personenHolen();
      const q = sortParameter(new URLSearchParams({ seite, pro_seite: 200 }), sort);
      if (filter) q.set("status", filter);
      if (person) q.set("zugeordnet", person);
      if (kategorie) q.set("kategorie", kategorie);
      const [antwort] = await Promise.all([api(`${API}/ordner/${id}?${q}`), ordnerBaum().catch(() => null)]);
      const d = antwort.ordner;
      const darf = d.darf || {};
      jetzt = d;
      grund = Boolean(darf.grund);
      if (grund && personen === null) await personenHolen();
      leisteMarkieren(d.id);
      const system = !!d.system_kind;
      const darfPflegen = Boolean(darf.verwalten) && !system;
      // Verschieben und Löschen: wer den Ordner darüber verwaltet – eine Gliederung auf oberster Ebene nur die Verwaltung.
      const darfOben = darfPflegen && verwaltet(d.parent_id ? baumIndex[d.parent_id] : null);
      const z = d.zaehlung || {};
      const bc = d.pfad.map((p, i) => (i === d.pfad.length - 1 ? `<span>${esc(p.name)}</span>` : pfadGlied(p)));
      const pruefbar = d.system_kind !== "ausgesondert" && d.artikel.some((a) => a.darf && a.darf.pruefen);
      // Filter „Zugeordnet an …“ (Bauentwurf 6.4) – nur mit Grundrecht und nur, wenn im Zweig jemandem etwas zugeordnet ist.
      // Seit dem 25.10.2026 im Filtermenü der Seitenleiste.
      const personWahl = grund && personen && personen.length ? `<label for="mat-personwahl">Zugeordnet an</label><select class="mat-personwahl" id="mat-personwahl" data-personwahl><option value="">alle</option>${personen.map((p) => `<option value="${p.id}" ${String(p.id) === person ? "selected" : ""}>${esc(p.name)}${p.aktiv ? "" : " (deaktiviert)"}</option>`).join("")}</select>` : "";
      // „Erinnerungsmails aus“ (selbst oder von einem Oberordner geerbt) sieht, wer den Ordner pflegt – dort schaltet man es.
      const erinnerungAus = darfPflegen && d.erinnerungen && d.erinnerungen.aus;
      const geerbtVon = erinnerungAus && !d.erinnerungen.eigen ? d.erinnerungen.geerbt_von : null;
      // Liegt hier selbst nichts (die Zahlen zählen nur, was das Konto sieht), entfallen die Filter, und der leere Ordner
      // sagt, wie viele Artikel in den Unterordnern liegen – mit dem Weg zum Fälligen im Zweig (Geräte-Prüfung vom
      // 21.10.2026). Ist ein Filter gesetzt, bleibt die Zeile – sonst ließe er sich nicht zurücknehmen.
      const summe = (x) => Object.values(x || {}).reduce((a, b) => a + b, 0);
      const direktAlle = summe(d.direkt);
      const unten = Math.max(0, summe(z) - direktAlle);
      const faelligZweig = (z.ueberfaellig || 0) + (z.neu || 0) + (z.bald_faellig || 0) + (z.lebensdauer || 0);
      const leerHtml = filter || kategorie || person ? leer("Keine Artikel mit diesen Filtern.")
          : !unten ? leer("Hier liegen keine Artikel.")
            : `<p class="leerzustand">${unten === 1 ? "Hier liegen keine Artikel direkt – 1 liegt in einem Unterordner."
              : `Hier liegen keine Artikel direkt – ${unten} liegen in Unterordnern.`}${faelligZweig
              ? ` <a href="/materialablage/pruefungen?ordner=${d.id}">Fällige Artikel im ganzen Zweig →</a>` : ""}</p>`;
      /* Filtermenü in der Seitenleiste unter dem Baum (Wunsch vom 25.10.2026): Status, Kategorie und „Zugeordnet an“,
         untereinander verknüpft (alle zugleich). Die Zahlen je Gruppe zählen mit den übrigen Filtern (Server). Über
         der Liste steht nur ein Satz, was gefiltert ist, mit „Filter zurücksetzen“; unter 1024 px davor „Filter (n)“,
         der die Schublade bei den Filtern öffnet (F4). Liegt hier gar nichts und ist nichts gefiltert, entfällt es. */
      const zeigeFilter = Boolean(direktAlle || filter || person || kategorie);
      const kats = (d.kategorien || []).slice();
      if (kategorie && !kats.some((k) => String(k.id) === kategorie)) {
        // Ohne Treffer (etwa mit einem Status dazu) fehlt die gewählte Kategorie in der Antwort – sie bleibt mit Namen und
        // Platz der letzten Liste stehen, mit 0 (Prüfung Browser, Verbesserung 6).
        const i = kategorienZuletzt.findIndex((k) => String(k.id) === kategorie);
        const vorgaenger = new Set(i >= 0 ? kategorienZuletzt.slice(0, i).map((k) => k.id) : []);
        let platz = 0;
        kats.forEach((k, j) => { if (vorgaenger.has(k.id)) platz = j + 1; });
        kats.splice(i >= 0 ? platz : kats.length, 0, Object.assign({}, i >= 0 ? kategorienZuletzt[i]
          : { id: +kategorie, name: kategorieName || "gewählte Kategorie", pfad: kategorieName }, { n: 0 }));
      } else kategorienZuletzt = kats;
      const doppelt = new Set(kats.filter((k, i) => kats.findIndex((x) => x.name.toLowerCase() === k.name.toLowerCase()) !== i).map((k) => k.name.toLowerCase()));
      const katText = (k) => (doppelt.has(k.name.toLowerCase()) ? k.pfad : k.name);
      const wahlKnopf = (act, attr, wert, an, text, n, title) => `<li><button type="button" class="mat-filterwahl${an ? " active" : ""}" data-act="${act}" ${attr}="${esc(wert)}" aria-pressed="${an}"${title ? ` title="${esc(title)}"` : ""}><span>${text}</span><span class="mat-side-anzahl">${n}</span></button></li>`;
      const statusZahl = (st) => (st === EMPFOHLEN ? d.empfohlen || 0 : st ? (d.direkt && d.direkt[st]) || 0 : summe(d.direkt));
      // „Aussonderung empfohlen“ (A4) nur, wo es so einen Artikel gibt (oder der Filter gesetzt ist) – meist in „Gesperrt“.
      const statusListe = ["", "ueberfaellig", "neu", "bald_faellig", "gesperrt", "lebensdauer", "einsatzbereit"]
        .concat(d.empfohlen || filter === EMPFOHLEN ? [EMPFOHLEN] : []);
      const filterMenue = `<div class="mat-filtergruppe" role="group" aria-labelledby="mat-fg-status"><h3 id="mat-fg-status">Status</h3>
          <ul class="mat-filterliste">${statusListe.map((st) => wahlKnopf("filter", "data-f", st, st === filter, st ? esc(statusName(st)) : "alle", statusZahl(st))).join("")}</ul></div>
        ${kats.length ? `<div class="mat-filtergruppe" role="group" aria-labelledby="mat-fg-kat"><h3 id="mat-fg-kat">Kategorie</h3>
          <ul class="mat-filterliste">${wahlKnopf("kategorie", "data-k", "", !kategorie, "alle", kats.reduce((n, k) => n + k.n, 0))}${kats.map((k) => wahlKnopf("kategorie", "data-k", String(k.id), String(k.id) === kategorie, esc(katText(k)), k.n, k.pfad)).join("")}</ul></div>` : ""}
        ${personWahl ? `<div class="mat-filtergruppe mat-filter-person">${personWahl}</div>` : ""}`;
      const personName = person && personen ? ((personen.find((p) => String(p.id) === person) || {}).name || "") : "";
      const katAktiv = kategorie ? kats.find((k) => String(k.id) === kategorie) : null;
      const gefiltert = [filter ? `Status „${esc(statusName(filter))}“` : "", katAktiv ? `Kategorie „${esc(katText(katAktiv))}“` : "",
        person ? `zugeordnet an „${esc(personName)}“` : ""].filter(Boolean);
      const filterKopf = `<div class="mat-filterkopf"><button type="button" class="btn secondary small mat-filter-auf" data-act="filter-auf" data-leiste-auf
          aria-controls="mat-side">${gefiltert.length ? `Filter (${gefiltert.length})` : "Filter"}</button>
        ${gefiltert.length ? `<p class="small mat-gefiltert" tabindex="-1">Gefiltert: ${gefiltert.join(" · ")} – <button type="button" class="lnk" data-act="filter-weg">Filter zurücksetzen</button></p>` : ""}</div>`;
      const filterBox = $("#mat-side-filter");
      if (filterBox) {
        filterBox.hidden = !zeigeFilter;
        $("#mat-filter-inhalt", filterBox).innerHTML = zeigeFilter ? filterMenue : "";
      }
      const systemText = d.system_kind === "gesperrt"
        ? "Hierher verschiebt eine Sperre die Artikel der Gliederung. Zurück in ihren Herkunftsordner bringt sie nur eine Freiprüfung."
        : "Ausgesonderte Artikel bleiben hier mit ihrem vollen Lebenslauf sichtbar, zählen aber nirgends mehr als Bestand und lassen sich nicht zurückholen.";
      seitenTitel(d.name);
      inhalt.innerHTML = `<div class="mat-pfad">${pfadHtml(['<a href="/materialablage/bestand">Bestand</a>', ...bc])}</div>
        <div class="page-head"><h1>${schloss(d)}${esc(d.name)} ${system ? "" : `<span class="mat-art">${esc(ORDNERART[d.kind])}</span>`}${demoMarke(d.demo)}</h1>
          <div class="btn-row">${darfPflegen ? `<button class="btn secondary small" data-act="unterordner"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Unterordner<span class="k-anlegen"> anlegen</span></span></button>
            <a class="btn secondary small" href="/materialablage/artikel/neu?ordner=${d.id}"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Artikel<span class="k-anlegen"> anlegen</span></span></a>
            ${darfOben ? bearbeitenMenue : '<button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>'}` : ""}
            ${darf.grund ? exportMenue(d, darfPflegen) : ""}</div></div>
        ${darfPflegen ? '<div id="mat-freigaben-kopf"></div>' : ""}
        ${darfPflegen && d.nacharbeit ? `<p class="notice small">Aus einem Bestandsimport ${d.nacharbeit === 1 ? "wartet 1 Zeile" : `warten ${d.nacharbeit} Zeilen`} auf Nacharbeit.
          <a href="/materialablage/ordner/${d.id}/import#bi-nacharbeit">Nacharbeit öffnen</a></p>` : ""}
        ${system ? `<p class="notice">${systemText}${d.teilweise ? " Du siehst hier nur deine Artikel – die Gliederung selbst gehört nicht zu deinem Bereich." : ""}</p>` : ""}
        ${d.foto || d.description || d.interval_months || erinnerungAus ? `<div class="mat-ordnerkopf">${d.foto ? bildLink(d.foto, d.original, `Ordnerfoto ${d.name}`, null, `<img class="mat-ordnerfoto" src="${esc(d.vorschau)}" alt="">`) : ""}
          <div>${d.description ? `<p class="mat-text">${esc(d.description)}</p>` : ""}
          ${d.interval_months ? `<p class="small">Prüfintervall hier: höchstens ${d.interval_months} Monate.</p>` : ""}
          ${erinnerungAus ? `<p class="small">Erinnerungsmails aus${geerbtVon ? ` – geerbt von ${geerbtVon.sichtbar ? `<a href="/materialablage/ordner/${geerbtVon.id}">${esc(geerbtVon.pfad)}</a>` : esc(geerbtVon.pfad)}` : ""}</p>` : ""}</div></div>` : ""}
        ${d.unterordner.length ? `<section class="section"><h2>Unterordner</h2>${unterordnerHtml(d.unterordner)}</section>` : ""}
        <section class="section"><h2 id="mat-artikel-titel" tabindex="-1">Artikel in diesem Ordner</h2>
          ${zeigeFilter ? filterKopf : ""}
          ${d.artikel.length ? artikelTabelle(d.artikel, { auswahl: darfPflegen, pruefen: pruefbar, person: darf.grund, sort, kategorie: true }) : leerHtml}
          ${person ? `<p class="small"><a href="/materialablage/pruefungen?ordner=${d.id}&zugeordnet=${encodeURIComponent(person)}">Fällige Artikel dieser Person im ganzen Zweig →</a></p>` : ""}
          ${seitenleiste(d.artikel_gesamt, seite, d.pro_seite)}
          ${darfPflegen ? `<div class="mat-sammel" id="mat-sammel" hidden><span id="mat-sammel-n"></span><div class="btn-row">
            <button class="btn secondary small" data-act="sammel-verschieben">Verschieben</button>
            <button class="btn secondary small" data-act="sammel-zuordnen">Zuordnen</button>
            <button class="btn secondary small" data-act="sammel-loesen" hidden>Zuordnung lösen</button></div></div>` : ""}
        </section>
        ${(d.sammelprotokolle || []).length ? `<section class="section"><h2>${sammelprotokolleTitel(d.sammelprotokolle)}</h2>${sammelprotokolleHtml(d.sammelprotokolle)}</section>` : ""}
        <p class="small mat-zweigbestand">${system ? plural(Object.values(z).reduce((a, b) => a + b, 0), "Artikel", "Artikel") : `Bestand im ganzen Zweig: <strong>${d.bestand}</strong> ${zahlen(z)}`}</p>
        ${darf.grund ? `<details class="section mat-auf"><summary>Journal des Ordners</summary>${journalHtml(d.journal)}</details>` : ""}`;
      if (darfPflegen) {
        // Der Ablaufhinweis bleibt im Ordnerkopf – ein Hinweis, kein Menü; „Verlängern“ führt in den Reiter.
        if (!kopfEl) {
          kopfEl = document.createElement("div");
          kopfEl.id = "mat-freigaben-kopf";
          const el = kopfEl;
          baustein("MatFreigaben").then((f) => { if (f) f.kopfhinweis(el, d, () => freigabenOeffnen("verlaengern")); });
        }
        $("#mat-freigaben-kopf").replaceWith(kopfEl);
        if (vorlage !== null) {
          const v = vorlage;
          vorlage = null;
          baustein("MatFreigaben").then((f) => { if (f) freigabenOeffnen(v); });
        }
      }
      // „alle auswählen“ gibt es zweimal – im Tabellenkopf und über den Karten (schmale Bildschirme); beide zeigen
      // denselben Stand, halb gesetzt, solange nur ein Teil angehakt ist.
      const waehlbar = $$(".mat-wahl-art:not(:disabled)", inhalt);
      const alleK = $$(".mat-alle", inhalt);
      const sammel = () => {
        const gewaehlt = $$(".mat-wahl-art:checked", inhalt);
        const n = gewaehlt.length;
        alleK.forEach((x) => { x.checked = !!waehlbar.length && n === waehlbar.length; x.indeterminate = n > 0 && n < waehlbar.length; });
        const leiste = $("#mat-sammel");
        if (!leiste) return;
        leiste.hidden = !n;
        $("#mat-sammel-n").textContent = `${plural(n, "Artikel", "Artikel")} ausgewählt`;
        // „Zuordnung lösen“ nur, wenn unter den gewählten einer jemandem zugeordnet ist.
        $('[data-act="sammel-loesen"]', leiste).hidden = !gewaehlt.some((c) => c.dataset.person);
      };
      if (nachFilter) {
        // Nach einer Wahl: in der Schublade zum Satz „Gefiltert …“ bzw. zur Liste, in der festen Leiste zurück auf die Wahl.
        const ziel = nachFilter === "liste" ? $(".mat-gefiltert", inhalt) || $("#mat-artikel-titel", inhalt) : $(nachFilter);
        nachFilter = null;
        if (ziel) ziel.focus();
      }
      $$(".mat-wahl-art", inhalt).forEach((c) => c.addEventListener("change", sammel));
      alleK.forEach((alle) => alle.addEventListener("change", () => { waehlbar.forEach((c) => { c.checked = alle.checked; }); sammel(); }));
      const gewaehlteIds = () => $$(".mat-wahl-art:checked", inhalt).map((c) => +c.value);

      // Eine Wahl im Filtermenü: erste Seite, Schublade zu (der Fokus geht danach auf den Satz über der Liste).
      const gewaehlt = (sel) => {
        seite = 1;
        if (alsSchublade() && leiste && leiste.classList.contains("open")) { leisteZu(); nachFilter = "liste"; } else nachFilter = sel;
        zeigen(zeichnen);
      };
      aktionen = {
        filter: (b) => { filter = b.dataset.f; gewaehlt(`[data-act="filter"][data-f="${filter}"]`); },
        kategorie: (b) => {
          kategorie = b.dataset.k;
          kategorieName = kategorie ? b.title || $("span", b).textContent : "";
          gewaehlt(`[data-act="kategorie"][data-k="${kategorie}"]`);
        },
        "filter-weg": () => { filter = ""; kategorie = ""; person = ""; seite = 1; nachFilter = "#mat-artikel-titel"; zeigen(zeichnen); },
        "filter-auf": (b) => { if (leiste && filterBox) leisteOeffnen(b, $("#mat-filter-titel", filterBox)); },
        seite: (b) => { seite = +b.dataset.seite; zeigen(zeichnen); },
        sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); seite = 1; zeigen(zeichnen); },
        person: (s) => { person = s.value; gewaehlt("#mat-personwahl"); },
        unterordner: () => ordnerDialog({ kind: "standort" }, d.id),
        runde: () => rundeDialog(d.id),
        bearbeiten: () => bearbeiten(),
        verschieben: async () => {
          const gl = d.kind === "gliederung";
          const ziel = await ordnerWaehlen("Ordner verschieben nach …", { ohneZweig: d.id, obersteEbene: gl, quelle: d.parent_id || null,
                                                                          hinweis: ORDNER_VERSCHIEBEN, wechselHinweis: gl ? GLIEDERUNG_WECHSEL : ORDNER_WECHSEL });
          if (ziel === null) return;
          try { await api(`${API}/ordner/${d.id}/verschieben`, { method: "POST", body: { parent_id: ziel || null } }); toast("Verschoben"); leisteNeu(); zeigen(zeichnen); }
          catch (e) { toast(e.message, true); }
        },
        loeschen: async () => {
          if (!(await confirm(`Ordner „${d.name}“ endgültig löschen? Danach ist er weg. Das geht nur bei einem leeren Ordner – ohne Unterordner und Artikel, ohne Prüfdurchgänge und Set-Protokolle, ohne offene Nacharbeit und ohne gesperrte Artikel, die hierher zurückkehren.`, "Löschen"))) return;
          try { await api(`${API}/ordner/${d.id}`, { method: "DELETE" }); location.href = d.parent_id && offenbar(d.parent_id) ? `/materialablage/ordner/${d.parent_id}` : "/materialablage/bestand"; }
          catch (e) { toast(e.message, true); }
        },
        "sammel-verschieben": async () => {
          const ids = gewaehlteIds();
          if (!ids.length) return;
          const ziel = await ordnerWaehlen(`${plural(ids.length, "Artikel", "Artikel")} verschieben nach …`,
                                           { quelle: d.id, hinweis: ARTIKEL_VERSCHIEBEN, wechselHinweis: ARTIKEL_WECHSEL });
          if (!ziel) return;
          try { const r = await api(`${API}/artikel/verschieben`, { method: "POST", body: { ids, folder_id: ziel } }); toast(`${plural(r.verschoben, "Artikel", "Artikel")} verschoben`); leisteNeu(); zeigen(zeichnen); }
          catch (e) { toast(e.message, true); }
        },
        "sammel-zuordnen": async () => {
          const ids = gewaehlteIds();
          if (!ids.length) return;
          const p = await personWaehlen(`${plural(ids.length, "Artikel", "Artikel")} zuordnen`);
          if (!p) return;
          try {
            const r = await api(`${API}/artikel/zuordnen`, { method: "POST", body: { ids, user_id: p.id } });
            toast(`${plural(r.geaendert, "Artikel", "Artikel")} zugeordnet an ${p.name}`);
            personen = null;
            zeigen(zeichnen);
          } catch (e) { toast(e.message, true); }
        },
        "sammel-loesen": async () => {
          const ids = gewaehlteIds();
          if (!ids.length) return;
          try {
            const r = await api(`${API}/artikel/zuordnen`, { method: "POST", body: { ids, user_id: null } });
            toast(`Zuordnung gelöst – ${plural(r.geaendert, "Artikel", "Artikel")}`);
            personen = null;
            zeigen(zeichnen);
          } catch (e) { toast(e.message, true); }
        },
      };
    }
    await zeichnen();
  }

  /* --- Produktsuche mit allen Treffern (Artikel anlegen, Meldung zuordnen) ------------------------------
     Alle Treffer in einer scrollbaren Liste unter dem Suchfeld, je 50 vom Server; rückt das Ende der Liste ins Bild,
     kommen die nächsten. Eine Antwort zu einer älteren Eingabe zählt nicht mehr (Zähler je Liste).
     Je Treffer zwei getrennte Flächen nebeneinander: das Foto (öffnet es groß, wählt nichts) und der Knopf mit dem
     Namen (wählt das Produkt) – ein Link in einem Knopf wäre kein gültiges HTML, und der Tipp gehörte beiden.
     Die Treffer kommen nach Kategorie sortiert; vor jeder neuen Kategorie steht eine Trennlinie mit ihrem Namen
     (auch über die Seitengrenze hinweg), der Name steht deshalb nicht mehr in jeder Zeile (Wunsch vom 24.10.2026). */
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
    let kategorie = null;
    ziel.scrollTop = 0;
    const zeile = (p, i) => `<div class="mat-treffer-produkt">${produktFoto(p)}<button type="button" class="mat-treffer-wahl" data-i="${i}">
      <strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${p.article_no ? ` <span class="muted"><span class="mat-ganz">${esc(p.article_no)}</span></span>` : ""}${demoMarke(p.demo)}</button></div>`;
    const mitKopf = (p, i) => {
      const k = p.category_name || "";
      const kopf = k !== kategorie ? `<div class="mat-treffer-kat">${esc(k || "ohne Kategorie")}</div>` : "";
      kategorie = k;
      return kopf + zeile(p, i);
    };
    async function mehr() {
      if (laedt || (seite && liste.length >= gesamt)) return;
      laedt = true;
      try {
        const d = await api(`${API}/produkte?q=${encodeURIComponent(q)}&sort=kategorie&pro_seite=50&seite=${seite + 1}`);
        if (lauf !== ziel._lauf) return;
        seite += 1;
        gesamt = d.gesamt;
        const start = liste.length;
        liste.push(...d.produkte);
        if (!liste.length) { ziel.innerHTML = leerHtml; return; }
        const fuss = $(".mat-treffer-fuss", ziel);
        if (fuss) fuss.remove();
        ziel.insertAdjacentHTML("beforeend", d.produkte.map((p, i) => mitKopf(p, start + i)).join("")
          + `<p class="help mat-treffer-fuss">${liste.length < gesamt ? `${liste.length} von ${gesamt} Treffern – weiter scrollen …` : plural(gesamt, "Treffer", "Treffer")}</p>`);
      } catch (e) {
        if (lauf === ziel._lauf) ziel.innerHTML = `<p class="error">${esc(e.message)}</p>`;
        return;
      } finally { laedt = false; }
      // Füllt eine Seite den Kasten nicht (große Bildschirme), gleich die nächste holen.
      if (lauf === ziel._lauf && liste.length < gesamt && ziel.scrollHeight <= ziel.clientHeight + 60) mehr();
    }
    ziel.onscroll = () => { if (ziel.scrollTop + ziel.clientHeight >= ziel.scrollHeight - 160) mehr(); };
    ziel.onclick = (e) => { const b = e.target.closest(".mat-treffer-wahl"); if (b && liste[+b.dataset.i]) waehlen(liste[+b.dataset.i]); };
    mehr();
  }

  /* --- Export (Lieferung 4) ----------------------------------------------------------------------------
     Ordner: Artikelliste als CSV und alle Protokolle als ZIP; Artikel: Lebenslauf als PDF. Gewöhnliche Links,
     kein fetch – der Server prüft das Leserecht selbst und zeigt einen Fehler als Seite. Ein Download lässt die
     Seite stehen; damit niemand doppelt klickt, während das ZIP entsteht, sagt ein Hinweis, dass es kommt. */
  // Export eines Ordners als Untermenü im Ordnerkopf: Knopf „Export“, darunter die beiden Downloads mit einem Satz,
  // was drinsteckt. <details> öffnet und schließt ohne eigenes Skript (auch per Tastatur und Touch). Wer den Ordner
  // pflegt (verwalten, kein Systemordner – importieren), findet hier seit Phase 2 · L3 auch den Bestandsimport: Das
  // Menü heißt dann „Export / Import“ und hat unter einem Strich „Bestandsliste importieren“ und, solange etwas
  // offen ist, „Nacharbeit (n offen)“ – seltene Funktionen gehören ins Untermenü, kein neuer Knopf in der Kopfzeile.
  // Seit Phase 4 · L1 steht hier auch „Jahresbericht exportieren“ (Ansicht bericht) – nicht an Systemordnern: Ein Bericht
  // über „Gesperrt“ oder „Ausgesondert“ wäre nach der Heimat-Logik leer, der Server antwortet dort 404.
  const exportMenue = (d, importieren) => `<details class="mat-menue">
      <summary class="btn secondary small" aria-haspopup="true">${importieren ? "Export / Import" : "Export"}</summary>
      <div class="mat-menue-liste">
        <a href="/materialablage/export/${d.id}.csv" data-frisch data-export="Die Artikelliste wird heruntergeladen …"><strong>Artikelliste exportieren (CSV)</strong>
          <span>Alle Artikel hier und darunter, auch die von hier gesperrten und ausgesonderten, mit Status, Fälligkeiten und Stammdaten – für Excel.</span></a>
        <a href="/materialablage/export/${d.id}-protokolle.zip" data-frisch data-export="Die Protokolle werden zusammengestellt – bei vielen dauert das einen Moment …"><strong>Protokolle exportieren (ZIP)</strong>
          <span>Die Protokolle dieser Artikel, die Sammelprotokolle der Durchgänge und die Set-Protokolle der Sets hier, mit Verzeichnis und Prüfsummen.</span></a>
        ${d.system_kind ? "" : `<a href="/materialablage/ordner/${d.id}/bericht"><strong>Jahresbericht exportieren</strong>
          <span>Bestand, Prüfungen, Sperren, Aussonderungen, Mängel und Rückrufe dieses Zweigs für ein Kalenderjahr – als Seite, PDF und Prüfungsliste (CSV).</span></a>`}
        ${importieren ? `<hr class="mat-menue-trenner">
        <a href="/materialablage/ordner/${d.id}/import"><strong>Bestandsliste importieren</strong>
          <span>Eine Liste aus Excel oder CSV in diesen Ordner übernehmen: erst ein Probelauf, dann übernehmen; was nicht passt, kommt in die Nacharbeit.</span></a>
        ${d.nacharbeit ? `<a href="/materialablage/ordner/${d.id}/import#bi-nacharbeit"><strong>Nacharbeit (${d.nacharbeit} offen)</strong>
          <span>Zeilen aus Bestandsimporten, die noch ein Produkt, eine Angabe oder eine Entscheidung brauchen.</span></a>` : ""}` : ""}
      </div></details>`;
  // Katalog-Export und -Import im Kopf des Katalogs: wie „Export / Import“ im Ordnerkopf ein Untermenü statt zweier
  // Knöpfe (Wunsch vom 20.10.2026). Die Einträge öffnen die Dialoge über data-act; ohne Skript führen sie zum Katalog.
  const katalogMenue = `<details class="mat-menue">
      <summary class="btn secondary" aria-haspopup="true">Export / Import</summary>
      <div class="mat-menue-liste">
        <a href="/materialablage/katalog" role="button" data-act="kat-export"><strong>Katalog exportieren</strong>
          <span>Kategorien, Produkte und Prüfformulare samt Bildern und Herstellerdokumenten als ZIP – zum Sichern oder für eine andere Installation. Bestand, Prüfungen und DEMO bleiben draußen.</span></a>
        <a href="/materialablage/katalog" role="button" data-act="kat-import"><strong>Katalog importieren</strong>
          <span>Eine Katalogdatei (ZIP oder JSON) übernehmen: erst ein Probelauf, dann übernehmen. Gelöscht wird dabei nichts.</span></a>
      </div></details>`;
  // „Bearbeiten“ im Kategoriekopf des Katalogs: wie im Ordnerkopf steht „Löschen“ im Untermenü statt als eigener Knopf
  // (Browserprüfung vor dem Merge, V1 – am Telefon schob die Knopfreihe samt Dokumenten die Produktliste weit hinunter).
  const kategorieMenue = `<details class="mat-menue">
      <summary class="btn secondary small" aria-haspopup="true">Bearbeiten</summary>
      <div class="mat-menue-liste">
        <a href="#" role="button" data-act="kat-bearbeiten"><strong>Kategorie bearbeiten</strong>
          <span>Name, Oberkategorie, Norm und die Vorgaben für Materialart, Prüfintervall, Lebensdauer und Länge.</span></a>
        <a href="#" role="button" data-act="kat-loeschen"><strong>Löschen</strong>
          <span>Geht nur ohne Unterkategorien und Produkte; vorher wird nachgefragt.</span></a>
      </div></details>`;
  // „Bearbeiten“ im Ordnerkopf: Verschieben und Löschen stehen im Untermenü statt als eigene Knöpfe (Wunsch vom
  // 20.10.2026). Wer den Ordner nur bearbeiten, aber nicht verschieben oder löschen darf, behält den einfachen Knopf.
  const bearbeitenMenue = `<details class="mat-menue">
      <summary class="btn secondary small" aria-haspopup="true">Bearbeiten</summary>
      <div class="mat-menue-liste">
        <a href="#" role="button" data-act="bearbeiten"><strong>Ordner bearbeiten</strong>
          <span>Name, Art, Prüfintervall, Beschreibung, Foto, Erinnerungsmails und Freigaben.</span></a>
        <a href="#" role="button" data-act="verschieben"><strong>Verschieben</strong>
          <span>Den Ordner samt Unterordnern und Artikeln an eine andere Stelle im Bestand hängen.</span></a>
        <a href="#" role="button" data-act="loeschen"><strong>Löschen</strong>
          <span>Geht nur bei einem leeren Ordner – ohne Unterordner und Artikel, ohne Prüfdurchgänge und Set-Protokolle, ohne offene Nacharbeit eines Bestandsimports und ohne gesperrte Artikel, die hierher zurückkehren; vorher wird nachgefragt.</span></a>
      </div></details>`;
  const LEBENSLAUF_TEXT = "Stammdaten, alle Prüfungen in zeitlicher Reihenfolge, Prüfdurchgänge und Ereignisse als PDF – zum Weitergeben oder als Aussonderungsnachweis. Stand jetzt, mit Kennung und Prüfsumme – prüfbar auf der Prüfseite.";
  const lebenslaufKnopf = (a) => `<a class="btn secondary small" href="/materialablage/artikel/${a.id}/lebenslauf.pdf" target="_blank" rel="noopener" data-frisch
    title="${LEBENSLAUF_TEXT}">Lebenslauf (PDF)</a>`;
  /* Artikelseite: neben „Bearbeiten“ die selteneren Funktionen im Menü „Mehr“ – Verschieben, Lebenslauf, Löschen –, je mit
     dem Satz, was sie tun (vorher bis zu vier gleichrangige Knöpfe und unter Touch ein Erklärabsatz zum Lebenslauf
     zwischen den Knopfreihen; Browserprüfung vor dem Merge, Verbesserung 5). Bleibt nur eine Funktion, steht sie als
     Knopf da. */
  function artikelMehr(a, eintraege) {
    const knopf = { verschieben: '<button class="btn secondary small" data-act="verschieben">Verschieben</button>',
                    lebenslauf: lebenslaufKnopf(a), loeschen: '<button class="btn secondary small" data-act="loeschen">Löschen</button>' };
    const zeile = {
      verschieben: `<a href="#" role="button" data-act="verschieben"><strong>Verschieben</strong>
        <span>In einen anderen Ordner legen – auch in eine andere Gliederung, wenn du dort verwaltest.</span></a>`,
      lebenslauf: `<a href="/materialablage/artikel/${a.id}/lebenslauf.pdf" target="_blank" rel="noopener" data-frisch><strong>Lebenslauf (PDF)</strong>
        <span>${LEBENSLAUF_TEXT}</span></a>`,
      loeschen: `<a href="#" role="button" data-act="loeschen"><strong>Löschen</strong>
        <span>Nur für falsch angelegte Artikel ohne Prüfung; vorher wird nachgefragt.</span></a>`,
    };
    if (eintraege.length < 2) return eintraege.map((e) => knopf[e]).join("");
    return `<details class="mat-menue"><summary class="btn secondary small" aria-haspopup="true">Mehr</summary>
      <div class="mat-menue-liste">${eintraege.map((e) => zeile[e]).join("")}</div></details>`;
  }
  // Auf Abruf gesetzte Dateien (Lebenslauf, Jahresbericht, Exporte, Nacharbeit, Katalog – data-frisch): Beim Antippen
  // bekommt die Adresse einen Zeitstempel (?stand=…, der Server übergeht ihn). Chrome auf Android legt PDFs als Download
  // ab und öffnete beim nächsten Tippen auf dieselbe Adresse die schon vorhandene Datei mit altem Stand (Meldung vom
  // 26.10.2026). Gesetzt beim Klick, nicht beim Zeichnen – die Seite kann seit Stunden offen sein; auch beim Klick mit
  // der mittleren Taste und vor dem Kontextmenü („Link in neuem Tab öffnen“, „Link herunterladen“).
  const frischeAdresse = (e) => {
    const l = e.target.closest && e.target.closest("a[data-frisch]");
    if (!l) return;
    const u = new URL(l.getAttribute("href"), location.href);
    u.searchParams.set("stand", String(Date.now()));
    l.setAttribute("href", u.pathname + u.search + u.hash);
  };
  for (const art of ["click", "auxclick", "contextmenu"]) document.addEventListener(art, frischeAdresse, true);
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
  function menueAusrichten(m) {
    const liste = $(".mat-menue-liste", m);
    const knopf = m.getBoundingClientRect();
    const breite = liste.offsetWidth;
    // Grenzen: das Fenster – auf einem Doppelbildschirm die Hälfte, in der der Knopf steht (sonst lag die Liste
    // halb unter dem Scharnier).
    let anfang = 0;
    let ende = document.documentElement.clientWidth;
    const haelften = window.viewport && window.viewport.segments;
    if (haelften && haelften.length > 1) {
      const h = Array.from(haelften).find((s) => knopf.left >= s.x - 1 && knopf.left < s.x + s.width);
      if (h) { anfang = h.x; ende = Math.min(ende, h.x + h.width); }
    }
    const links = Math.max(anfang + 8, Math.min(knopf.right - breite, ende - 8 - breite));
    liste.style.right = "auto";
    liste.style.left = `${Math.round(links - knopf.left)}px`;
  }
  document.addEventListener("toggle", (e) => {
    const m = e.target;
    if (!(m instanceof HTMLDetailsElement) || !m.classList.contains("mat-menue") || !m.open) return;
    menueAusrichten(m);
  }, true);
  // Ändert sich die Fensterbreite, während ein Menü offen ist (Fold auf- oder zugeklappt, Tablet gedreht), rückt es mit –
  // vorher behielt es die Lage vom Öffnen und ragte nach dem Zuklappen 31 px links aus dem Bild.
  window.addEventListener("resize", () => $$("details.mat-menue[open]").forEach(menueAusrichten));

  /* --- Jahresbericht je Zweig (Phase 4 · Lieferung 1) --------------------------------------------------------------
     Seite /materialablage/ordner/<fid>/bericht (Ansicht „bericht“, DATEN = {id}); die Daten kommen fertig formatiert von
     GET /api/material/ordner/<fid>/bericht?jahr=&pruefer= (services/bericht.daten) – dieselben Blöcke in derselben
     Reihenfolge wie im PDF (Entwurf A4): Kopf, Bestand zum Stichtag, Bewegungen, Prüfungen mit Prüfabdeckung,
     Prüfdurchgänge, Prüfer (nur mit Haken), Sperren und Freiprüfungen, Aussonderungen, Mangelmeldungen, Rückrufe, Ausblick,
     Fußsätze. Jahr-Auswahl (kopf.jahre) und Haken „Prüfer nennen“ laden die Daten neu und stehen in der Adresse
     (?jahr=&pruefer=1); „PDF“ und „Prüfungen (CSV)“ (grau) führen auf die Dateirouten – mit Haken auf die Fassung
     „-mit-pruefern“, deren Dateiname sagt, dass Namen darin stehen. Ohne Haken enthält keine Ausgabe einen
     Personennamen außer dem Ersteller. Zahlentabellen wie im PDF, Listen als Modullisten (am Telefon Karten über die
     Containerabfrage mat-seite); jede Zelle über esc(), keine DOM-ids aus Daten. DEMO: Zahl im Kopf, Marke je Zeile.
     Die Seite zeigt Listen ganz (eine lange Liste „nicht geprüft“ und die betroffenen Artikel eines Rückrufs
     aufklappbar); das PDF kürzt sie auf BERICHT_KAPPUNG Zeilen – darunter steht dann ein Hinweis. Unter dem Kopf
     Sprungmarken zu den Blöcken. 403, 404 und 400 (Jahr außerhalb 1990…2100) kommen als Meldung – auch beim ersten
     Laden mit Jahr-Auswahl (geruestFehler), damit man ein anderes Jahr wählen kann. Der Tab-Titel nennt Zweig und Jahr. */
  const BERICHT_KAPPUNG = 500;
  // Datenschutz bleibt sichtbar („Ohne Haken nennt keine Ausgabe einen Prüfer.“), die Einzelheiten stehen im „i“.
  const PRUEFER_NENNEN_INFO = "Mit Haken nennen die Seite, das PDF und die CSV die Prüfer mit Urkundennummer und wer ausgesondert hat.";
  async function bericht() {
    const fid = Number(DATEN.id);
    const adresse = new URLSearchParams(location.search);
    let jahr = /^\d{4}$/.test(adresse.get("jahr") || "") ? +adresse.get("jahr") : null;
    let pruefer = adresse.get("pruefer") === "1";
    leisteMarkieren(fid);
    const zahlen = (zeilen) => `<table class="mat-zahlen"><tbody>${zeilen.map(([n, text]) => `<tr><td class="mat-zahl-wert">${esc(String(n))}</td><td class="mat-zahl-text">${text}</td></tr>`).join("")}</tbody></table>`;
    const paar = (a, b) => `<div class="mat-paar"><div>${a}</div><div>${b}</div></div>`;
    const mono = (t) => `<span class="mat-hash">${esc(t)}</span>`;
    const kappung = (n, was) => (n > BERICHT_KAPPUNG ? `<p class="small muted">Im PDF stehen nur die ersten ${BERICHT_KAPPUNG} ${was} dieser Liste.</p>` : "");
    const liste = (koepfe, zeilen, klasse) => `<table class="list mat-tabelle${klasse ? ` ${klasse}` : ""}"><thead><tr>${koepfe.map((k) => `<th${k[1] ? ` class="${k[1]}"` : ""}>${esc(k[0])}</th>`).join("")}</tr></thead><tbody>${zeilen.join("")}</tbody></table>`;
    const td = (l, inhalt, klasse) => `<td data-l="${esc(l)}"${klasse ? ` class="${klasse}"` : ""}>${inhalt}</td>`;
    // Sprungmarken zu den Blöcken (feste ids, nichts aus Daten); „Prüfer“ nur mit Haken.
    const BLOECKE = [["be-bestand", "Bestand"], ["be-bewegungen", "Bewegungen"], ["be-pruefungen", "Prüfungen"],
                     ["be-durchgaenge", "Durchgänge"], ["be-pruefer", "Prüfer"], ["be-sperren", "Sperren"],
                     ["be-aussonderungen", "Aussonderungen"], ["be-maengel", "Mängel"], ["be-rueckrufe", "Rückrufe"],
                     ["be-ausblick", "Ausblick"]];
    const NICHT_GEPRUEFT_OFFEN = 25;          // so viele „nicht geprüft“ stehen aufgeklappt, mehr zugeklappt
    const titelSetzen = (k) => seitenTitel(`Jahresbericht ${k.ordner} ${k.jahr}`);

    function inhaltHtml(b) {
      const k = b.kopf;
      const bst = b.bestand;
      const pr = b.pruefungen;
      const sp = b.sperren;
      const au = b.aussonderungen;
      const ma = b.maengel;
      const ab = b.ausblick;
      const kopf = `<dl class="mat-daten mat-bericht-daten">
          <dt>Zweig</dt><dd>${esc(k.pfad)}</dd>${k.gliederung && k.gliederung !== k.ordner ? `<dt>Gliederung</dt><dd>${esc(k.gliederung)}</dd>` : ""}
          <dt>Stichtag der Bestandszahlen</dt><dd>${esc(k.stichtag)}</dd>
          <dt>Erstellt von</dt><dd>${esc(k.ersteller)} am ${esc(k.erstellt_am)}</dd>
          <dt>Empfänger</dt><dd>${esc(k.empfaenger)}</dd>
          <dt>Artikel im Zweig (Sicht)</dt><dd>${esc(String(k.artikel))}${k.demo ? ` – davon ${k.demo} DEMO ${demoMarke(true)}` : ""}</dd>
          <dt>Prüfer genannt</dt><dd>${k.pruefer_nennen ? "ja" : "nein"}</dd></dl>
        ${k.demo ? `<p class="notice small">Enthält ${k.demo} DEMO-Artikel – gekennzeichnet mit der Marke DEMO; nicht für echte Nachweise.</p>` : ""}`;
      const bestand = `<section class="section" id="be-bestand"><h2>Bestand zum Stichtag ${esc(k.stichtag)}</h2>
        ${paar(zahlen([...bst.zeilen.map((z) => [z.n, `${statusMarke(z.status)}${z.status === "ausgesondert" ? ' <span class="muted">(gesamt, seit je)</span>' : ""}`]),
          [bst.verloren, "davon verloren gemeldet"], [bst.bestand, "<strong>Bestand gesamt</strong> (ohne ausgesonderte)"]]),
        `<h3>Je Kategorie (oberste Ebene)</h3>${bst.kategorien.length ? zahlen(bst.kategorien.map((x) => [x.bestand, `${esc(x.name)} <span class="muted">– fällig ${x.faellig}, gesperrt ${x.gesperrt}</span>`])) : leer("Keine Artikel.")}`)}
        ${bst.unterordner.length ? `<h3>Je Unterordner (nach Heimat)</h3>${liste([["Ordner"], ["Bestand", "mat-be-zahl"], ["einsatzbereit", "mat-be-zahl"], ["bald fällig", "mat-be-zahl"], ["überfällig", "mat-be-zahl"], ["neu", "mat-be-zahl"], ["gesperrt", "mat-be-zahl"], ["Lebensdauer", "mat-be-zahl"], ["ausgesondert", "mat-be-zahl"]],
          bst.unterordner.map((u) => `<tr>${td("Ordner", `${esc(u.name)}${u.kennzeichen ? ` <span class="mat-art">${esc(u.kennzeichen)}</span>` : ""}${demoMarke(u.demo)}`, "mat-k-titel")}${td("Bestand", String(u.bestand), "mat-be-zahl")}${["einsatzbereit", "bald_faellig", "ueberfaellig", "neu", "gesperrt", "lebensdauer", "ausgesondert"].map((st) => td(STATUS[st] || st, String(u.zaehlung[st] || 0), `mat-be-zahl${u.zaehlung[st] ? "" : " mat-be-null"}`)).join("")}</tr>`), "mat-bericht-ordner mat-bericht-breit")}` : ""}
        </section>`;
      const bewegungen = `<section class="section" id="be-bewegungen"><h2>Bewegungen im Jahr ${esc(String(k.jahr))}</h2>
        ${zahlen([[b.bewegungen.zugaenge, "Zugänge (angelegt oder importiert)"], [b.bewegungen.aussonderungen, "Aussonderungen"], [b.bewegungen.geloescht, "gelöscht (falsch angelegt, ohne Prüfung)"]])}</section>`;
      const pruefungen = `<section class="section" id="be-pruefungen"><h2>Prüfungen im Jahr ${esc(String(k.jahr))}</h2>
        ${paar(zahlen([[pr.gesamt, "<strong>Prüfungen gesamt</strong> (ohne Aussonderungen)"], ...pr.arten.map((a) => [a.n, esc(a.text)]), [pr.entwuerfe, "offene Entwürfe (nicht abgeschlossen)"]]),
          zahlen([...pr.ergebnisse.map((e) => [e.n, `Ergebnis „${esc(e.text)}“`]), [pr.mit_mangel, "mit Mangel"], [pr.kritisch, "mit kritischem Mangel"]]))}
        <h3>Prüfabdeckung</h3>
        ${zahlen([[pr.abdeckung.bestand, "Artikel im Bestand (ohne ausgesonderte)"], [pr.abdeckung.geprueft, "davon im Jahr mit abgeschlossener Prüfung"], [pr.abdeckung.nicht_geprueft, "im Jahr nicht geprüft"]])}
        ${pr.nicht_geprueft.length ? `<details class="mat-auf"${pr.nicht_geprueft.length <= NICHT_GEPRUEFT_OFFEN ? " open" : ""}><summary>Im Jahr nicht geprüft (${pr.nicht_geprueft.length})</summary>${liste([["Inventarnummer"], ["Produkt"], ["letzte Prüfung"]],
          pr.nicht_geprueft.map((x) => `<tr>${td("Inventarnummer", `${mono(x.inventarnummer)}${demoMarke(x.demo)}`)}${td("Produkt", esc(x.produkt))}${td("letzte Prüfung", esc(x.letzte))}</tr>`))}${kappung(pr.nicht_geprueft.length, "Artikel")}</details>` : ""}
        </section>`;
      const durchgaenge = `<section class="section" id="be-durchgaenge"><h2>Prüfdurchgänge</h2>
        ${b.durchgaenge.length ? liste([["Durchgang"], ["Zeitraum"], ["Stand"], ["Artikel", "mat-be-zahl"], ["erledigt", "mat-be-zahl"], ["ausgenommen", "mat-be-zahl"], ["nicht geprüft", "mat-be-zahl"]],
          b.durchgaenge.map((r) => `<tr>${td("Durchgang", `<strong>${esc(r.titel)}</strong>${demoMarke(r.demo)}${r.ausnahmen.length ? `<div class="small muted">Ausnahmen: ${r.ausnahmen.map((a) => `${mono(a.inventarnummer)} (${esc(a.grund)})`).join("; ")}</div>` : ""}`)}
            ${td("Zeitraum", esc(r.zeitraum))}${td("Stand", `${esc(r.stand)}${r.protokoll_id ? ` · ${mono(r.protokoll_id)}` : ""}`)}
            ${td("Artikel", String(r.gesamt), "mat-be-zahl")}${td("erledigt", String(r.erledigt), "mat-be-zahl")}${td("ausgenommen", String(r.ausgenommen), "mat-be-zahl")}
            ${td("nicht geprüft", r.stand === "offen" ? `${r.offen} offen` : String(r.nicht_geprueft), "mat-be-zahl")}</tr>`), "mat-bericht-breit") : leer("Im Jahr kein Prüfdurchgang im Zweig.")}</section>`;
      const pruefer = b.pruefer ? `<section class="section" id="be-pruefer"><h2>Prüfer im Jahr ${esc(String(k.jahr))}</h2>
        ${b.pruefer.pruefer.length ? liste([["Prüfer"], ["Urkundennummer"], ["Prüfungen", "mat-be-zahl"]],
          b.pruefer.pruefer.map((x) => `<tr>${td("Prüfer", esc(x.name))}${td("Urkundennummer", mono(x.urkunde || ""))}${td("Prüfungen", String(x.n), "mat-be-zahl")}</tr>`)) : leer("Keine Prüfungen.")}
        ${b.pruefer.aussonderungen_durch.length ? `<h3>Aussonderungen durch</h3>${liste([["Name"], ["Aussonderungen", "mat-be-zahl"]],
          b.pruefer.aussonderungen_durch.map((x) => `<tr>${td("Name", esc(x.name))}${td("Aussonderungen", String(x.n), "mat-be-zahl")}</tr>`))}` : ""}</section>` : "";
      const sperren = `<section class="section" id="be-sperren"><h2>Sperren und Freiprüfungen im Jahr ${esc(String(k.jahr))}</h2>
        ${zahlen([[sp.gesamt, "<strong>Sperren gesamt</strong>"], ...sp.arten.map((a) => [a.n, esc(a.text)]), [sp.freigegeben, "wieder freigegeben (Freiprüfung)"]])}
        ${sp.liste.length ? `${liste([["Datum"], ["Inventarnummer"], ["Art"], ["Grund"]],
          sp.liste.map((x) => `<tr>${td("Datum", esc(x.datum))}${td("Inventarnummer", `${mono(x.inventarnummer)}${demoMarke(x.demo)}`)}${td("Art", esc(x.art_text))}${td("Grund", esc(x.grund))}</tr>`))}${kappung(sp.liste.length, "Sperren")}` : ""}</section>`;
      const aussonderungen = `<section class="section" id="be-aussonderungen"><h2>Aussonderungen im Jahr ${esc(String(k.jahr))}</h2>
        ${zahlen([[au.gesamt, "<strong>Aussonderungen gesamt</strong>"], ...au.arten.map((a) => [a.n, esc(a.text)])])}
        ${au.liste.length ? `${liste([["Datum"], ["Inventarnummer"], ["Produkt"], ["Grund"]],
          au.liste.map((x) => `<tr>${td("Datum", esc(x.datum))}${td("Inventarnummer", `${mono(x.inventarnummer)}${demoMarke(x.demo)}`)}${td("Produkt", `${esc(x.produkt)}`)}${td("Grund", `${esc(x.grund)}${x.durch ? ` · durch ${esc(x.durch)}` : ""}${x.protokoll_id ? ` · ${mono(x.protokoll_id)}` : ""}`)}</tr>`))}${kappung(au.liste.length, "Aussonderungen")}` : ""}</section>`;
      const maengel = `<section class="section" id="be-maengel"><h2>Mangelmeldungen</h2>
        ${zahlen([[ma.gemeldet, `<strong>gemeldet im Jahr ${esc(String(k.jahr))}</strong>`], [ma.offen, "davon heute offen"], [ma.freipruefung, "erledigt durch Freiprüfung"], [ma.aussonderung, "erledigt durch Aussonderung"], [ma.offen_stichtag, "offene Meldungen zum Stichtag (alle Jahre)"]])}
        ${ma.offen_liste.length ? `${liste([["Inventarnummer"], ["gemeldet am"]],
          ma.offen_liste.map((x) => `<tr>${td("Inventarnummer", `${mono(x.inventarnummer)}${demoMarke(x.demo)}`)}${td("gemeldet am", esc(x.gemeldet))}</tr>`))}${kappung(ma.offen_liste.length, "Meldungen")}` : ""}</section>`;
      const rueckrufe = `<section class="section" id="be-rueckrufe"><h2>Rückrufe${infoKnopf("Rückrufe", "Rückrufe, die im Jahr angelegt oder beendet wurden oder heute laufen – zu Produkten mit Artikeln im Zweig.")}</h2>
        ${b.rueckrufe.length ? `${liste([["Angelegt · beendet"], ["Rückruf"], ["betroffen", "mat-be-zahl"], ["offen", "mat-be-zahl"]],
          b.rueckrufe.map((r) => `<tr>${td("Angelegt · beendet", `${esc(r.angelegt)}<br>${r.beendet ? `beendet ${esc(r.beendet)}` : "läuft"}`)}
            ${td("Rückruf", `<strong>${esc(r.titel)}</strong> – ${esc(r.produkt)} <span class="muted">(${r.alle ? "alle Artikel des Produkts" : "nach Seriennummern"})</span>${r.url ? `<div class="small">Meldung des Herstellers: ${mono(r.url)}</div>` : ""}${r.artikel.length ? `<details class="mat-auf mat-be-rr"><summary>Betroffene Artikel anzeigen (${r.artikel.length})</summary><ul class="mat-be-rr-liste">${[...r.artikel].sort((x, y) => (x.zustand !== "offen") - (y.zustand !== "offen")).map((a) => `<li>${mono(a.inventarnummer)} <span class="muted">${esc(a.zustand)}</span>${demoMarke(a.demo)}</li>`).join("")}</ul></details>` : ""}`)}
            ${td("betroffen", String(r.betroffen), "mat-be-zahl")}${td("offen", String(r.offen), "mat-be-zahl")}</tr>`))}` : leer("Kein Rückruf betrifft Artikel im Zweig.")}</section>`;
      const ausblick = `<section class="section" id="be-ausblick"><h2>Ausblick – zwölf Monate ab ${esc(k.stichtag)}</h2>
        <p class="help">Jetzt: ${ab.jetzt.ueberfaellig} überfällig, ${ab.jetzt.neu} neu (Eingangsprüfung ausstehend), ${ab.jetzt.gesperrt} gesperrt.</p>
        ${liste([["Monat"], ["fällig", "mat-be-zahl"], ["Lebensende (textil)", "mat-be-zahl"]],
          ab.monate.map((m) => `<tr>${td("Monat", esc(m.text), "mat-k-titel")}${td("fällig", String(m.faellig), `mat-be-zahl${m.faellig ? "" : " mat-be-null"}`)}${td("Lebensende (textil)", String(m.lebensende), `mat-be-zahl${m.lebensende ? "" : " mat-be-null"}`)}</tr>`), "mat-bericht-monate")}</section>`;
      const fuss = `<ul class="small muted mat-bericht-fuss">${b.fuss.map((satz) => `<li>${esc(satz)}</li>`).join("")}</ul>`;
      const sprung = `<nav class="mat-bericht-sprung" aria-label="Blöcke des Berichts"><ul>${BLOECKE.filter(([id]) => id !== "be-pruefer" || b.pruefer)
        .map(([id, text]) => `<li><a href="#${id}">${esc(text)}</a></li>`).join("")}</ul></nav>`;
      return kopf + sprung + bestand + bewegungen + pruefungen + durchgaenge + pruefer + sperren + aussonderungen + maengel + rueckrufe + ausblick + fuss;
    }

    function dateien(b) {
      const k = b.kopf;
      const mit = k.pruefer_nennen ? "-mit-pruefern" : "";
      return `<a class="btn secondary small" href="/materialablage/ordner/${fid}/bericht-${Number(k.jahr)}${mit}.pdf" target="_blank" rel="noopener" data-frisch
          data-export="Das PDF wird erzeugt – bei vielen Artikeln dauert das einige Sekunden …" title="Dieser Bericht als PDF/A – Listen gekürzt (${BERICHT_KAPPUNG} Zeilen je Liste, 1 500 insgesamt, 50 Artikel je Rückruf). Stand jetzt, nicht festgeschrieben.">PDF</a>
        <a class="btn secondary small" href="/materialablage/export/${fid}-pruefungen-${Number(k.jahr)}${mit}.csv" data-frisch data-export="Die Prüfungsliste wird heruntergeladen …"
          title="Alle Prüfungen und Aussonderungen des Jahres im Zweig als CSV für Excel${k.pruefer_nennen ? " – mit Prüfer und Urkundennummer" : " – ohne Prüfernamen"}.">Prüfungen (CSV)</a>`;
    }

    function geruest(b) {
      const k = b.kopf;
      const jahre = k.jahre.includes(k.jahr) ? k.jahre : [...k.jahre, k.jahr].sort();
      inhalt.innerHTML = `<div class="mat-pfad">${pfadHtml(['<a href="/materialablage/bestand">Bestand</a>', `<a href="/materialablage/ordner/${fid}">${esc(k.pfad)}</a>`])}</div>
        <div class="page-head"><h1>Jahresbericht ${esc(k.ordner)} <span id="be-titel-jahr">${esc(String(k.jahr))}</span>${demoMarke(k.demo)}</h1>
          <div class="btn-row" id="be-dateien">${dateien(b)}</div></div>
        <div class="mat-bericht-wahl">
          <label for="be-jahr">Kalenderjahr${infoKnopf("Kalenderjahr", "Bestandszahlen gelten zum Stichtag heute, Ereignisse für das Kalenderjahr.")} <select id="be-jahr">${jahre.map((j) => `<option value="${Number(j)}"${j === k.jahr ? " selected" : ""}>${Number(j)}</option>`).join("")}</select></label>
          <label class="inline" for="be-pruefer"><input type="checkbox" id="be-pruefer"${k.pruefer_nennen ? " checked" : ""}> Prüfer nennen${infoKnopf("Prüfer nennen", PRUEFER_NENNEN_INFO)}</label>
          <span class="help">Ohne Haken nennt keine Ausgabe einen Prüfer.</span></div>
        <div id="be-inhalt">${inhaltHtml(b)}</div>`;
      $("#be-jahr").addEventListener("change", (e) => { jahr = +e.target.value; laden(true); });
      $("#be-pruefer").addEventListener("change", (e) => { pruefer = e.target.checked; laden(true); });
      titelSetzen(k);
    }

    // Erster Aufruf gescheitert (400 Jahr außerhalb, 403, 404): Meldung mit Jahr-Auswahl (die letzten 15 Jahre) und dem
    // Weg zurück – ein anderes Jahr lädt den Bericht neu.
    function geruestFehler(e) {
      const dieses = new Date().getFullYear();
      const jahre = Array.from({ length: 15 }, (_, i) => dieses - i);
      const gewaehlt = jahre.includes(jahr) ? jahr : dieses;
      inhalt.innerHTML = `<div class="mat-pfad">${pfadHtml(['<a href="/materialablage">Materialablage</a>', '<a href="/materialablage/bestand">Bestand</a>'])}</div>
        <div class="page-head"><h1>Jahresbericht</h1></div>
        <div class="mat-bericht-wahl">
          <label for="be-jahr">Kalenderjahr <select id="be-jahr">${jahre.map((j) => `<option value="${j}"${j === gewaehlt ? " selected" : ""}>${j}</option>`).join("")}</select></label></div>
        <div id="be-inhalt"><p class="notice" role="alert">${esc(e.message)}</p></div>`;
      $("#be-jahr").addEventListener("change", (ev) => { jahr = +ev.target.value; laden(false); });
      seitenTitel("Jahresbericht");
    }

    // Daten holen; nachladen: nur der Inhalt wird ersetzt, Auswahl und Knöpfe bleiben (mit neuer Jahreszahl).
    async function laden(nachladen) {
      const q = new URLSearchParams();
      if (jahr) q.set("jahr", String(jahr));
      if (pruefer) q.set("pruefer", "1");
      const ziel = nachladen ? $("#be-inhalt") : null;
      if (ziel) ziel.innerHTML = '<p class="help">Wird geladen …</p>';
      let b;
      try { b = (await api(`${API}/ordner/${fid}/bericht?${q}`)).bericht; }
      catch (e) {
        if (!ziel) { geruestFehler(e); return; }
        ziel.innerHTML = `<p class="notice" role="alert">${esc(e.message)}</p>`;
        return;
      }
      try { history.replaceState(null, "", location.pathname + (String(q) ? `?${q}` : "")); } catch (e) { /* nur die Adresszeile */ }
      if (!ziel) { geruest(b); return; }
      ziel.innerHTML = inhaltHtml(b);
      $("#be-dateien").innerHTML = dateien(b);
      $("#be-titel-jahr").textContent = String(b.kopf.jahr);
      titelSetzen(b.kopf);
    }
    await laden(false);
  }

  /* --- Artikel --------------------------------------------------------------------------------------- */
  /* Angeboten wird die globale Suche immer (Entscheidung vom 18.10.2026) – auch, wenn die Suche einen eindeutigen
     eigenen Treffer gleich hier geöffnet hat (DATEN.suche, nur wenn die Anfrage dafür taugt). Dann steht das Angebot
     unter dem Kopf des Artikels; exakt, wenn er genau diese Seriennummer hat (Leerraum und Groß/klein wie auf dem
     Server egal). Das Ergebnis bleibt, wenn die Seite nach einer Aktion neu gezeichnet wird – gesucht wird einmal. */
  let artikelFremde = null;
  const nummerNormal = (s) => String(s || "").split(/\s+/).filter(Boolean).join(" ").toLowerCase();

  async function artikel() {
    const [antwort] = await Promise.all([api(`${API}/artikel/${DATEN.id}`), ordnerBaum().catch(() => null)]);
    const a = antwort.artikel;
    const darf = a.darf || {};           // was das Konto an diesem Artikel (seiner Heimat) darf
    leisteMarkieren(a.folder_id);
    const p = a.produkt;
    const frei = a.lock_state === "frei";
    const darfPflegen = Boolean(darf.verwalten) && a.lock_state !== "ausgesondert";
    // „Bearbeiten“ auch für Prüfer (Wunsch vom 24.10.2026, E2): Bemerkung, Länge und nächste Prüfung direkt.
    const darfDirekt = Boolean(darf.verwalten || darf.pruefen) && a.lock_state !== "ausgesondert";
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
    const bc = pfadHtml(a.pfad.map(pfadGlied));
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    // Personenzuordnung (Bauentwurf 6.4): sehen nur mit Grundrecht, zuordnen, ändern und lösen, wer den Artikel verwaltet.
    // Einem ausgesonderten Artikel ordnet niemand mehr jemanden zu; eine alte Zuordnung lässt sich noch lösen.
    const zu = a.zugeordnet;
    const zuKnoepfe = darf.verwalten && (!aus || zu) ? `<div class="btn-row mat-zuordnung">${aus ? "" : `<button class="btn secondary small" type="button" data-act="zuordnen">${zu ? "Ändern" : "Zuordnen"}</button>`}${zu ? '<button class="btn secondary small" type="button" data-act="zuordnung-loesen">Lösen</button>' : ""}</div>` : "";
    // Gemeldete Mängel (Phase 3 · L1): offene als Banner oben, erledigte eingeklappt unter „Prüfungen“. Melden darf jeder
    // mit Leserecht, außer am ausgesonderten Artikel. „Aussondern“ des Materialwarts ist ausgegraut, solange es der Server
    // nicht erlaubt (a.aussondern, Schritt 28: erst nach einer Prüfung mit „instandsetzen“ oder „aussondern empfohlen“,
    // ohne Prüfung nur bei Verlust) – der Grund steht darunter.
    const maengel = a.maengel || [];
    const darfMelden = !aus && Boolean(darf.lesen);
    // Eigene offene Meldung: Knopf ausgegraut mit Hilfezeile wie in „Meine PSA“ – kein Dialog, der erst 409 bringt.
    // Wer den Artikel selbst verwaltet, bekommt den Satz „an den Materialwart“ nicht.
    const schonGemeldet = darfMelden && a.mangel_eigen_offen;
    const sperrKnopf = frei && darf.pruefen && !a.entwurf;
    const aussonderKnopf = gesperrt && darf.verwalten && !a.entwurf;
    // Designsprache: keine Erklärzeilen unter Knöpfen – was ein Knopf gerade nicht kann (ausgegraut, mit
    // aria-describedby) oder warum er fehlt, steht als Satz über seiner Knopfzeile (Nutzer, 25.10.2026).
    const aussondernNein = aussonderKnopf && a.aussondern && !a.aussondern.ok ? a.aussondern.grund : "";
    const empf = a.aussonderung_empfohlen;
    // Hat die Empfehlung selbst gesperrt, steht ihr Grund nur im Hinweis darunter – der Banner sagt nur „Aussonderung
    // empfohlen“ (Browserprüfung vom 25.10.2026: dreimal derselbe Grund).
    const sperrText = empf && /aussondern empfohlen/.test(a.lock_reason || "") ? "Aussonderung empfohlen" : a.lock_reason;
    // Kommt die Sperre von einer offenen Mangelmeldung (Sperrgrund „Mangel gemeldet am …“, mangel.melden) und steht deren
    // roter Banner, sagt der graue GESPERRT-Banner dasselbe noch einmal – er entfällt (Nutzer, 26.10.2026). Bei jedem
    // anderen Sperrgrund bleibt er; die Marke „gesperrt“ im Kopf bleibt immer.
    const offeneMaengel = maengel.filter((m) => m.offen);
    const sperreDurchMangel = /^Mangel gemeldet am /.test(a.lock_reason || "") && offeneMaengel.length > 0;
    // Gesperrt aus einem anderen Grund (Prüfung, Verlust …) UND eine offene Mangelmeldung: Statt zweier gleich großer roter
    // Kästen steht nur der Mangel-Banner, der Sperrgrund als Zeile darin – im ersten, wenn es mehrere gibt (Entscheidung
    // des Nutzers, Nachtrag V7 vor dem Merge: „zusammenlegen“).
    const sperreImMangel = a.status === "gesperrt" && !sperreDurchMangel && offeneMaengel.length > 0;
    const zuordnung = darf.grund ? zeile("Zugeordnet an", `${zu ? `${esc(zu.name)}${zu.gliederung ? ` <span class="muted">· ${esc(zu.gliederung)}</span>` : ""}${zu.aktiv ? "" : ' <span class="muted">(deaktiviert)</span>'}`
      : '<span class="muted">–</span>'}${zuKnoepfe}`) : "";
    seitenTitel(a.inventory_no);
    inhalt.innerHTML = `${quittungHtml()}${a.demo ? `<p class="mat-demo-banner">${DEMO_ARTIKEL}</p>` : ""}
      ${a.status === "ausgesondert" ? `<p class="mat-banner s-ausgesondert">AUSGESONDERT – dieser Artikel ist außer Dienst und darf nicht mehr verwendet werden.</p>` : ""}
      ${a.status === "gesperrt" && !sperreDurchMangel && !sperreImMangel ? `<p class="mat-banner s-gesperrt">GESPERRT${sperrText ? ` – ${esc(sperrText)}` : ""}. Nicht verwenden, bis eine Freiprüfung ihn freigibt.</p>` : ""}
      ${empf ? `<p class="notice mat-empfehlung"><strong>Aussonderung empfohlen</strong> – ${person(empf.pruefer || "Prüfer")} am ${esc(fmtTag(empf.datum))} (<a href="/materialablage/pruefung/${Number(empf.pruefung)}">${empf.protokoll_id ? `Protokoll ${esc(empf.protokoll_id)}` : "Prüfung ansehen"}</a>)${empf.grund ? `: ${esc(empf.grund)}` : ""}. Aussondern kann der Materialwart.</p>` : ""}
      ${offeneMaengel.map((m, i) => mangelBanner(m, sperreImMangel && i === 0 ? sperrText || "" : null)).join("")}
      ${a.status === "lebensdauer" ? `<p class="mat-banner s-lebensdauer">LEBENSDAUER ERREICHT – nicht mehr verwenden, prüfen lassen und aussondern.</p>` : ""}
      ${a.status === "neu" ? '<p class="mat-banner s-neu">NEU – die Eingangsprüfung steht aus. Bis dahin nicht einsetzen.</p>' : ""}
      ${rueckrufBanner(a)}
      <div class="mat-pfad">${bc}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? bildLink(p.bild, p.original, `Produktbild ${produktName(p)}`, null, `<img class="mat-produktbild" src="${esc(p.bild)}" alt="Produktbild ${esc(produktName(p))}">`) : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel">
          <h1><span class="mat-inv">${esc(a.inventory_no)}</span> ${statusMarke(a.status, true)}${empfohlenMarke(empf)}</h1>
          <p class="mat-produktzeile"><a href="/materialablage/katalog/produkt/${p.id}">${nameHtml(p)}</a>${zusatzHtml(p)}${artNrHtml(p.article_no)}</p>
          <p>Seriennummer <strong>${esc(a.serial_no)}</strong>${a.serial_generated ? ' <span class="badge grey">vom System vergeben</span><span class="help mat-sn-hinweis">Der Hersteller vergibt keine Seriennummer – diese Nummer bitte dauerhaft am Artikel anbringen.</span>' : ""}</p>
          ${aus || darf.pruefen ? "" : DARF.qualifiziert || DARF.pruefer_haekchen ? `<p class="notice small">${pruefHinweis(a)}</p>` : ""}
          ${schonGemeldet ? `<p class="help mat-schon-gemeldet" id="mat-schon-gemeldet">Du hast am ${esc(S.fmtDate(a.mangel_eigen_offen))} schon gemeldet – ein Prüfer sieht es sich an.${darf.verwalten ? "" : " Ergänzungen bitte direkt an den Materialwart."}</p>` : ""}
          ${aussondernNein ? `<p class="help mat-aussondern-hilfe" id="mat-aussondern-hilfe">${esc(aussondernNein)}</p>` : ""}
          <div class="btn-row mat-pruefknoepfe">${!aus && darf.pruefen && !fremderEntwurf ? `<button class="btn" data-act="pruefen">${eigenerEntwurf ? "Prüfung fortsetzen" : a.status === "neu" ? "Eingangsprüfung starten" : "Prüfung starten"}</button>` : ""}
            ${sperrKnopf ? '<button class="btn secondary small" data-act="sperren">Sperren</button>' : ""}
            ${darfMelden ? `<button class="btn secondary small" type="button"${schonGemeldet ? ' disabled aria-describedby="mat-schon-gemeldet"' : ' data-act="mangel"'}>Mangel melden</button>` : ""}
            ${aussonderKnopf ? `<button class="btn secondary small" type="button"${aussondernNein ? ' disabled aria-describedby="mat-aussondern-hilfe"' : ' data-act="aussondern"'}>Aussondern</button>` : ""}</div>
          ${a.entwurf ? `<p class="small">In Prüfung bei <strong>${person(a.entwurf.pruefer)}</strong> seit ${esc(fmtZeit(a.entwurf.seit))}
            ${fremderEntwurf ? ` <span class="mat-nowrap">· <a href="/materialablage/pruefung/${a.entwurf.id}">ansehen</a></span>` : ""}
            ${fremderEntwurf && darf.verwalten ? ' <span class="mat-nowrap">· <button class="lnk" type="button" data-act="freigeben">Reservierung aufheben</button></span>' : ""}</p>` : ""}
          ${a.durchgang ? `<p class="small">Steht im Prüfdurchgang ${a.durchgang.sichtbar ? `<a href="/materialablage/durchgang/${a.durchgang.id}">${esc(a.durchgang.titel)}</a>` : `„${esc(a.durchgang.titel)}“`}.</p>` : ""}
          <div class="btn-row">${darfDirekt ? '<button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>' : ""}${artikelMehr(a, [
            darfPflegen && frei ? "verschieben" : "", darf.grund ? "lebenslauf" : "", darfPflegen && a.darf_loeschen ? "loeschen" : ""].filter(Boolean))}</div>
        </div>
      </div>
      ${DATEN.suche ? '<div id="mat-global-angebot"></div>' : ""}
      <div class="mat-spalten">
        <section class="section"><div class="abschnittskopf"><h2>Stammdaten</h2>${antragMoeglich(a) ? '<button class="btn secondary small" type="button" data-act="antrag">Änderung beantragen</button>' : ""}</div>
          <dl class="mat-daten">
          ${zeile("Produkt", `${nameHtml(p)}${zusatzHtml(p)}`)}
          ${zeile("Norm", p.norm ? esc(p.norm) : '<span class="muted">–</span>')}
          ${(a.bestandteile || []).length ? zeile("Bestandteile", bestandteilZeilen(a.bestandteile, true)) : ""}
          ${zeile("Materialart", esc(MATERIALART[p.material_kind] || p.material_kind))}
          ${zeile("Gliederung", a.gliederung ? pfadGlied(a.gliederung) : "–")}
          ${zuordnung}
          ${zeile("Herstellung", a.manufactured_on ? esc(fmtTag(a.manufactured_on)) : '<span class="muted">–</span>')}
          ${zeile("Kauf", a.purchased_on ? esc(fmtTag(a.purchased_on)) : '<span class="muted">–</span>')}
          ${zeile("Erstgebrauch", a.first_use_on ? esc(fmtTag(a.first_use_on)) : '<span class="muted">–</span>')}
          ${zeile("Lebensende", ldText)}
          ${a.laenge_moeglich || a.length_m ? zeile("Länge", a.length_m ? esc(laengeText(a.length_m)) : '<span class="muted">–</span>') : ""}
          ${zeile("Nächste Prüfung", aus ? '<span class="muted">–</span>' : gesperrt ? '<span class="muted">setzt die Freiprüfung</span>' : a.status === "neu" ? '<strong>Eingangsprüfung ausstehend</strong>' : a.next_due_on ? `<strong>${esc(fmtTag(a.next_due_on))}</strong>` : '<span class="mat-warn">keine</span>')}
          ${zeile("Zuletzt geprüft", a.last_inspected_on ? esc(fmtTag(a.last_inspected_on)) : '<span class="muted">noch nie</span>')}
          ${zeile("Prüfintervall", ivText)}
          ${zeile("Prüfformular", a.formular ? `${esc(a.formular.title || "ohne Titel")} · Version ${a.formular.version} <span class="muted">(${esc(a.formular.quelle)}, ${plural(a.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span>` : '<span class="mat-warn">kein aktives Prüfformular – im Katalog anlegen</span>')}
          ${a.notes ? zeile("Bemerkung", `<span class="mat-text">${esc(a.notes)}</span>`) : ""}
        </dl></section>
        <div class="mat-spalte">
        ${(a.antraege || []).length ? `<section class="section mat-antraege-offen"><h2>Offene Änderungsanträge</h2>${a.antraege.map(antragOffenHtml).join("")}</section>` : ""}
        <section class="section"><h2>QR-Code und NFC${infoKnopf("QR-Code und NFC", "Diese Adresse öffnet nach der Anmeldung diesen Artikel. Kopiere sie und schreibe sie auf einen NFC- oder RFID-Tag oder drucke sie mit einem beliebigen Etikettenprogramm als QR-Code – die Kamera-App des Telefons öffnet sie.")}</h2>
          <div class="mat-qr"><input type="text" readonly value="${esc(a.qr_adresse)}" id="mat-qr" aria-label="Adresse für QR, NFC und RFID">
          <button class="btn secondary small" data-act="qr-kopieren">Kopieren</button></div>
          <h2>Herstellerdokumente</h2>
          ${a.dokumente.length ? dokListe(a.dokumente, true) : leer("Am Produkt und seiner Kategorie sind keine Dokumente hinterlegt.")}
        </section>
        </div>
      </div>
      <section class="section"><h2>Prüfungen</h2>${pruefListe(a.pruefungen)}</section>
      ${mangelErledigt(maengel.filter((m) => !m.offen))}
      ${darf.grund ? `<section class="section"><h2>Journal${infoKnopf("Journal", "Änderungen am Artikel und an seinem Produkt, neueste zuerst.")}</h2>${journalHtml(a.journal, true)}</section>` : ""}`;
    aktionen = {
      "qr-kopieren": async () => {
        const feld = $("#mat-qr");
        try { await navigator.clipboard.writeText(feld.value); toast("Adresse kopiert"); }
        catch (e) { feld.select(); document.execCommand && document.execCommand("copy"); toast(`Adresse markiert – ${kopierText()}`); }
      },
      bearbeiten: () => artikelDialog(a),
      antrag: () => antragDialog(a),
      "antrag-zurueck": (b) => antragZurueckziehen((a.antraege || []).find((x) => x.id === +b.dataset.id), () => zeigen(artikel)),
      pruefen: () => { location.href = eigenerEntwurf ? `/materialablage/pruefung/${a.entwurf.id}` : `/materialablage/artikel/${a.id}/pruefung/neu`; },
      sperren: () => sperrDialog(a),
      mangel: () => mangelDialog(a, (r, q) => { quittung = q; return zeigen(artikel); }),
      "mangel-weiterlesen": (b) => mangelWeiterlesen(b),
      "rr-sperren": (b) => sperrDialog(a, { grund: "rueckruf", text: ((a.rueckrufe || []).find((r) => r.id === +b.dataset.id) || {}).title }),
      aussondern: () => aussonderDialog(a),
      freigeben: () => reservierungFreigeben(a.entwurf.id, a.entwurf.pruefer, () => zeigen(artikel)),
      verschieben: async () => {
        const ziel = await ordnerWaehlen("Artikel verschieben nach …", { quelle: a.folder_id, hinweis: ARTIKEL_VERSCHIEBEN, wechselHinweis: ARTIKEL_WECHSEL });
        if (!ziel) return;
        try { await api(`${API}/artikel/verschieben`, { method: "POST", body: { ids: [a.id], folder_id: ziel } }); toast("Verschoben"); leisteNeu(); zeigen(artikel); }
        catch (e) { toast(e.message, true); }
      },
      zuordnen: async () => {
        const wer = await personWaehlen(zu ? `${a.inventory_no}: Zuordnung ändern` : `${a.inventory_no} zuordnen`);
        if (!wer) return;
        try { await api(`${API}/artikel/${a.id}/zuordnung`, { method: "PUT", body: { user_id: wer.id } }); toast(`Zugeordnet an ${wer.name}`); zeigen(artikel); }
        catch (e) { toast(e.message, true); }
      },
      "zuordnung-loesen": async () => {
        try { await api(`${API}/artikel/${a.id}/zuordnung`, { method: "PUT", body: { user_id: null } }); toast("Zuordnung gelöst"); zeigen(artikel); }
        catch (e) { toast(e.message, true); }
      },
      loeschen: async () => {
        const frage = `Artikel ${a.inventory_no} löschen? Das ist nur für falsch angelegte Artikel ohne Prüfung gedacht; die Inventarnummer wird nicht wieder vergeben.`;
        if (!(await confirm(frage, "Löschen"))) return;
        try { await api(`${API}/artikel/${a.id}`, { method: "DELETE" }); location.href = `/materialablage/ordner/${a.folder_id}`; }
        catch (e) { toast(e.message, true); }
      },
    };
    if (DATEN.suche) {
      const g = await baustein("MatGlobal");
      const el = $("#mat-global-angebot");
      if (g && el) {
        g.anbieten(el, DATEN.suche, { exakt: nummerNormal(a.serial_no) === nummerNormal(DATEN.suche), ergebnis: artikelFremde,
                                      gefunden: (x) => { artikelFremde = x; } });
      }
    }
  }

  /* Personenzuordnung (Bauentwurf 6.4): Ein Artikel – meist PSA, die eine Person dauerhaft nutzt – wird einem Konto
     zugeordnet. Gesucht wird nach dem Namen (ab 3 Zeichen, GET /nutzer – ohne E-Mail, nur aktive Konten mit Namen).
     Liefert { id, name } oder null. */
  const ZUORDNUNG_HILFE = "Nur für PSA, die eine Person dauerhaft nutzt. Die Person sieht sie unter „Meine PSA“, bekommt "
    + "Erinnerungen per Mail und kann Mängel melden (das sperrt). Erscheint nicht in Protokollen.";
  function personWaehlen(titel) {
    return new Promise((resolve) => {
      let gewaehlt = null;
      let ja = false;
      let ergebnis = null;
      const dlg = dialog(`<h2>${esc(titel)}</h2>
        <p class="help">${esc(ZUORDNUNG_HILFE)}</p>
        <label for="zp-q">Person</label>
        <div class="mat-produktwahl"><input type="search" id="zp-q" placeholder="Name, mindestens 3 Zeichen" autocomplete="off" ${TASTATUR_NAME}>
          <div id="zp-treffer" class="mat-treffer" aria-live="polite"></div></div>
        <div id="zp-gewaehlt" class="mat-gewaehlt" hidden></div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
          <button class="btn" id="zp-ok" type="button" disabled>Zuordnen</button></div>`,
      (d, body) => {
        const feld = $("#zp-q", body);
        const treffer = $("#zp-treffer", body);
        let los = null;
        let lauf = 0;
        fokus(feld);
        async function suchen() {
          const q = feld.value.trim();
          const meinLauf = ++lauf;
          if (q.length < 3) { treffer.innerHTML = q ? '<p class="help">Mindestens 3 Zeichen des Namens.</p>' : ""; return; }
          let r;
          // Zuordnen geht an jedes aktive Konto mit Namen – wer PSA trägt, braucht keinen Zugang zum Modul.
          try { r = await api(`${API}/nutzer?q=${encodeURIComponent(q)}&zweck=zuordnung`); }
          catch (e) { if (meinLauf === lauf) treffer.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
          if (meinLauf !== lauf) return;
          ergebnis = r.nutzer;
          treffer.innerHTML = ergebnis.length ? ergebnis.map((u, i) => `<button type="button" class="mat-treffer-zeile" data-i="${i}">
              <strong>${esc(u.name)}</strong>${u.gliederung ? ` <span class="muted">${esc(u.gliederung)}</span>` : ""}</button>`).join("")
              + (r.mehr ? '<p class="help">Weitere Treffer – bitte genauer tippen.</p>' : "")
            : '<p class="help">Niemand gefunden – zuordnen lässt sich jedes aktive Konto mit Namen.</p>';
        }
        feld.addEventListener("input", () => { clearTimeout(los); los = setTimeout(suchen, 250); });
        treffer.addEventListener("click", (e) => {
          const b = e.target.closest(".mat-treffer-zeile");
          if (!b || !ergebnis) return;
          gewaehlt = ergebnis[+b.dataset.i];
          const anzeige = $("#zp-gewaehlt", body);
          anzeige.hidden = false;
          anzeige.innerHTML = `<strong>${esc(gewaehlt.name)}</strong>${gewaehlt.gliederung ? ` <span class="muted">${esc(gewaehlt.gliederung)}</span>` : ""}`;
          treffer.innerHTML = "";
          $("#zp-ok", body).disabled = false;
          fokus($("#zp-ok", body));
        });
        $("#zp-ok", body).onclick = () => { if (gewaehlt) { ja = true; d.close(); } };
      });
      dlg.addEventListener("close", () => resolve(ja ? { id: gewaehlt.id, name: gewaehlt.name } : null), { once: true });
    });
  }

  /* Prüfungen eines Artikels, neueste zuerst – der Prüfteil des Lebenslaufs. Je festgeschriebenem Eintrag das
     Protokoll (PDF im neuen Tab); ein durch eine Berichtigung ersetztes Original steht grau mit „berichtigt“. */
  function pruefListe(liste) {
    if (!liste || !liste.length) return leer("Noch keine Prüfung.");
    return `<table class="list mat-tabelle mat-karten mat-pruefliste"><thead><tr><th>Datum</th><th>Art</th><th>Ergebnis</th><th>Prüfer</th><th>Nächste Prüfung</th><th>Protokoll</th></tr></thead><tbody>
      ${liste.map((x) => {
        const ersetzt = x.berichtigt_durch && !x.berichtigt_durch.entwurf;
        return `<tr class="${x.entwurf ? "mat-entwurf" : ersetzt ? "mat-alt" : ""}"><td data-l="Datum" class="mat-k-titel"><a href="/materialablage/pruefung/${x.id}">${x.entwurf ? "Entwurf" : esc(fmtTag(x.datum))}</a></td>
        <td data-l="Art" class="mat-k-halb">${esc(PRUEFART_KURZ[x.art] || x.art)}${x.berichtigt ? ' <span class="mat-marke-ber">Berichtigung</span>' : ""}${ersetzt ? ` <span class="badge grey" title="berichtigt durch ${esc(x.berichtigt_durch.protokoll_id || "eine spätere Prüfung")}">berichtigt</span>` : ""}</td>
        <td data-l="Ergebnis" class="mat-k-marke">${x.entwurf ? '<span class="muted">in Prüfung</span>' : ergebnisMarke(x.ergebnis)}${x.grund ? `<div class="small muted">${esc(x.grund)}</div>` : ""}</td>
        <td data-l="Prüfer" class="mat-k-halb">${x.pruefer ? person(x.pruefer) : ""}${x.urkunde ? ` <span class="muted small">(${esc(x.urkunde)})</span>` : ""}</td>
        <td data-l="Nächste Prüfung">${x.naechste ? esc(fmtTag(x.naechste)) : '<span class="muted">–</span>'}</td>
        <td data-l="Protokoll" class="mat-k-ohne">${x.protokoll ? `<a class="mat-pdf" href="${esc(x.protokoll.url)}" target="_blank" rel="noopener" title="Protokoll ${esc(x.protokoll.id)} öffnen (PDF)">PDF</a> <span class="muted small mat-hash">${esc(x.protokoll.id)}</span>` : '<span class="muted">–</span>'}</td></tr>`;
      }).join("")}</tbody></table>`;
  }
  const ergebnisMarke = (e) => (e ? `<span class="mat-ergebnis-marke e-${esc(e)}">${esc(ERGEBNIS[e] || e)}</span>` : "");

  // vorgabe: { grund, text } – etwa aus dem Rückruf-Banner (Grund „Rückruf“, Titel des Rückrufs).
  // „Sperren“ ist die Hauptaktion des Dialogs (btn) – nicht btn danger: Eine
  // Freiprüfung hebt die Sperre wieder auf (Entscheidung vom 23.10.2026, L2b).
  function sperrDialog(a, vorgabe) {
    vorgabe = vorgabe || {};
    dialog(`<h2>${esc(a.inventory_no)} sperren</h2>
      <p class="help">Sperren ohne Prüfung – nach Sturzbelastung, Beschädigung, bei Verlust oder bei einem Rückruf des Herstellers. Der Artikel wandert nach „Gesperrt“ seiner Gliederung; zurück bringt ihn nur eine Freiprüfung mit „einsatzbereit“.</p>
      <label for="sd-grund">Grund</label><select id="sd-grund">${Object.entries(SPERRGRUND).map(([k, v]) => `<option value="${k}"${k === vorgabe.grund ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
      <label for="sd-text">Was ist passiert?</label><input type="text" id="sd-text" maxlength="300" placeholder="z. B. Sturz in die Rettungskette, Schnitt am Band" value="${esc(vorgabe.text || "")}">
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="sd-ok" type="button">Sperren</button></div>`,
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
    const tag = isoHeute(0);
    // Das Datum als deutsches Textfeld (TT.MM.JJJJ, C2 in P4-L1): spätestens heute, nicht vor der letzten Prüfung, dem
    // Herstelldatum und der Erfassung – der Server prüft dieselben Grenzen (409 mit Klartext).
    const herst = a.manufactured_on ? (a.manufactured_on.length === 7 ? `${a.manufactured_on}-01` : a.manufactured_on) : "";
    const grenzen = [[a.last_inspected_on, "letzte Prüfung"], [herst, "Herstellung"], [(a.created_at || "").slice(0, 10), "Erfassung"]].filter(([d]) => d);
    const fruehestens = grenzen.length ? grenzen.reduce((x, y) => (y[0] > x[0] ? y : x)) : null;
    const HINWEIS = "Die Aussonderung wird mit deiner Unterschrift festgeschrieben. Sie wird in deinem Profil gespeichert und als Kopie ins Aussonderungsprotokoll übernommen.";
    // Die Empfehlung des Prüfers (Schritt 28) steht im Dialog; der Grund ist vorbelegt: verloren → Verlust, Lebensende
    // erreicht → Lebensdauer, sonst irreparabel.
    const empf = a.aussonderung_empfohlen;
    const vorbelegt = a.lock_state === "verloren" ? "verlust" : a.retire_by && a.retire_by <= tag ? "lebensdauer" : "irreparabel";
    dialog(`<h2>${esc(a.inventory_no)} aussondern</h2>
      <p class="help">Die Aussonderung ist endgültig: Der Artikel wandert nach „Ausgesondert“, bleibt dort mit seinem Lebenslauf sichtbar und zählt nirgends mehr als Bestand.</p>
      ${empf ? `<p class="notice mat-empfehlung"><strong>Aussonderung empfohlen</strong> von ${person(empf.pruefer || "–")} am ${esc(fmtTag(empf.datum))}${empf.protokoll_id ? ` (Protokoll ${esc(empf.protokoll_id)})` : ""}${empf.grund ? `: ${esc(empf.grund)}` : ""}</p>` : ""}
      <div class="field-row"><div><label for="au-grund">Grund</label><select id="au-grund">${Object.entries(AUSSONDERUNGSGRUND).map(([k, v]) => `<option value="${k}"${k === vorbelegt ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
        <div><label for="au-datum">Datum</label>${datumFeld("au-datum", tag, "tag")}
          <div class="help">${fruehestens ? `Frühestens ${esc(fmtTag(fruehestens[0]))} (${esc(fruehestens[1])}), spätestens` : "Spätestens"} heute (${esc(fmtTag(tag))}).</div></div></div>
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
        // Erst das Datum (ein Tippfehler bricht ab), dann die Unterschrift.
        let datum;
        try { datum = datumWert($("#au-datum", body), "Datum"); }
        catch (e) { toast(e.message, true); $("#au-datum", body).focus(); return; }
        const hatte = DARF.unterschrift;
        if (!(await eigeneUnterschrift(HINWEIS))) return;
        if (!hatte) usZeigen();
        knopf.disabled = true;
        knopf.textContent = "Wird festgeschrieben …";
        try {
          const daten = { grund: $("#au-grund", body).value, datum, bemerkung: $("#au-bem", body).value };
          const r = await api(`${API}/artikel/${a.id}/aussondern`, { method: "POST", body: daten });
          let prot = null;
          try { prot = (await api(`${API}/pruefungen/${r.aussonderung}`)).pruefung.protokoll; } catch (e) { /* Link genügt */ }
          toast(`Ausgesondert${prot ? ` – Protokoll ${prot.id}` : ""}`);
          // Im selben Dialog weiter: zur Aussonderung mit ihrem Protokoll; darunter steht der Artikel schon neu.
          dialog(`<h2>${esc(a.inventory_no)} ausgesondert</h2>
            <p>Das Aussonderungsprotokoll ${prot ? `<strong class="mat-hash">${esc(prot.id)}</strong> ` : ""}ist mit deiner Unterschrift festgeschrieben.</p>
            <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button>
              ${prot ? `<a class="btn secondary" href="${esc(prot.url)}" target="_blank" rel="noopener">Protokoll (PDF)</a>` : ""}
              <a class="btn" href="/materialablage/pruefung/${r.aussonderung}" id="au-weiter">Zur Aussonderung</a></div>`,
          // Der Knopf, auf dem der Fokus lag, ist mit dem alten Inhalt weg – sonst fiele er an den Seitenanfang.
          (d2, b2) => $("#au-weiter", b2).focus());
          zeigen(artikel);
        } catch (e) { unterschriftWeg(e); toast(e.message, true); knopf.disabled = false; knopf.textContent = "Aussondern"; if (!DARF.unterschrift) usZeigen(); }
      };
    });
  }

  /* Produkt am Artikel ändern (Feintuning nach dem Kommentar-Dokument, L2b Nr. 29): „Bearbeiten“ hat ein Produktfeld,
     solange der Artikel keine abgeschlossene Prüfung hat (produkt_aenderbar). Mit offenem
     Entwurf steht es fest mit Satz (der Server antwortet sonst 409). Ein anderes Produkt wählt man wie beim Anlegen
     (produktTreffer); was der Wechsel nachzieht, sagt ein Hinweis vor dem Speichern. Die Länge fällt weg, wenn die
     Kategorie des neuen Produkts keine vorsieht – wie im Dienst (bestand.artikel_werte), das Journal nennt den alten
     Wert. Lebensende und Länge gehen dann nicht mit; der Server rechnet sie aus dem neuen Produkt. */
  const PRODUKT_ENTWURF = "Das Produkt lässt sich erst ändern, wenn die Prüfung festgeschrieben oder verworfen ist.";
  const produktGewaehltHtml = (p) => `<strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${artNrKurz(p.article_no)} ${demoMarke(p.demo)}
    <span class="mat-art">${esc(MATERIALART[p.material_kind] || "")}</span>`;
  // Was ein Wechsel von a.produkt auf p nachzieht – als Sätze für den Hinweis im Dialog.
  function produktFolgen(a, p) {
    const alt = a.produkt;
    const out = [];
    if (p.material_kind === "textil") out.push(`Das Lebensende rechnet neu aus Herstellung und Lebensdauer des neuen Produkts${p.lifetime_years ? ` (${p.lifetime_years} Jahre)` : ""}; die Herstellung ist Pflicht.`);
    else if (alt.material_kind === "textil") out.push("Das Lebensende fällt weg – es gibt es nur bei textilem Material.");
    if (a.length_m && !p.laenge_moeglich) out.push(`Die Länge (${laengeText(a.length_m)}) fällt weg – die Kategorie des neuen Produkts sieht keine vor.`);
    out.push("Wird das Prüfintervall kürzer, rückt die nächste Prüfung vor. Laufende Rückrufe gelten nach dem neuen Produkt.");
    return out;
  }

  // Seit der ersten Prüfung (stammdaten_fest) stehen die freigabepflichtigen Stammdaten fest (Wunsch vom 24.10.2026,
  // Entscheidung E1): Produkt, Seriennummer, Herstellung, Kauf, Erstgebrauch, Lebensende und Prüfintervall – oben
  // schreibgeschützt als Block, geändert wird über „Änderung beantragen“ (antragDialog). Direkt bleiben die nächste
  // Prüfung (vorziehen), die Länge und die Bemerkung – auch für Prüfer (E2), die sonst nichts bearbeiten (nurDirekt).
  /* Seriennummern der Bestandteile (Schritt 25): je Position der Bestandteil-Liste und Stück ein freiwilliges Feld –
     beim Anlegen, im Dialog „Bearbeiten“ (bis zur ersten Prüfung, Materialwart) und im Antrag. liste: [{id, bezeichnung,
     anzahl, nummern}]. Je zwei Felder in einer Reihe (Telefon: untereinander wie jede field-row). */
  // Wie teilnummern.stueck_text: endet die Bezeichnung mit einer Klammer, ohne zweite Klammer dahinter.
  const stueckText = (z, st) => (z.anzahl <= 1 ? z.bezeichnung
    : /\)\s*$/.test(z.bezeichnung) ? `${z.bezeichnung} – Stück ${st} von ${z.anzahl}` : `${z.bezeichnung} (Stück ${st} von ${z.anzahl})`);
  function teilnummernFelder(praefix, liste) {
    const felder = [];
    liste.forEach((z) => { for (let st = 1; st <= z.anzahl; st += 1) felder.push([z, st]); });
    const feld = ([z, st]) => `<div><label for="${praefix}-${z.id}-${st}">${esc(stueckText(z, st))}</label><input type="text" id="${praefix}-${z.id}-${st}" class="mat-teilnr" data-b="${z.id}" data-s="${st}" data-name="${esc(stueckText(z, st))}" maxlength="80" value="${esc((z.nummern || [])[st - 1] || "")}" ${TASTATUR_NUMMER}></div>`;
    const reihen = [];
    for (let i = 0; i < felder.length; i += 2) reihen.push(`<div class="field-row">${feld(felder[i])}${felder[i + 1] ? feld(felder[i + 1]) : "<div></div>"}</div>`);
    return reihen.join("");
  }
  const teilnummernSatz = (praefix, liste, hilfe) => `<fieldset class="mat-teilnr-satz" id="${praefix}"><legend>Seriennummern der Bestandteile</legend>
    ${teilnummernFelder(praefix, liste)}<div class="help">${esc(hilfe)}</div></fieldset>`;
  const teilnummernLesen = (el) => $$(".mat-teilnr", el).map((f) => ({ bestandteil_id: +f.dataset.b, stueck: +f.dataset.s, seriennummer: f.value.trim() }));
  /* Dieselbe Seriennummer an zwei Stück eines Artikels (auch in anderer Schreibung): nur ein Hinweis am zweiten Feld –
     gespeichert wird trotzdem, eindeutig müssen die Nummern der Bestandteile nicht sein (Prüfung Browser, Verbesserung
     2). Eine Gruppe ist ein Artikel: der Satz im Dialog (.mat-teilnr-satz) bzw. die Prüfpunkte (.mat-punkte); jedes Feld
     nennt sein Stück in data-name. Beim Zeichnen (doppelteZeigen) und bei jeder Eingabe. */
  const NUMMERFELD = ".mat-teilnr, .mat-pnummer";
  const nummerSchluessel = (v) => v.trim().replace(/\s+/g, " ").toLocaleLowerCase("de");
  function doppeltePruefen(gruppe) {
    const erste = new Map();
    $$(NUMMERFELD, gruppe).forEach((f) => {
      const k = nummerSchluessel(f.value);
      const vorher = k ? erste.get(k) : null;
      if (k && !vorher) erste.set(k, f);
      let h = document.getElementById(`${f.id}-doppelt`);
      if (!vorher) {
        if (h) { h.remove(); f.removeAttribute("aria-describedby"); }
        return;
      }
      if (!h) {
        h = document.createElement("div");
        h.className = "help mat-doppelt";
        h.id = `${f.id}-doppelt`;
        f.insertAdjacentElement("afterend", h);
        f.setAttribute("aria-describedby", h.id);
      }
      h.textContent = `Diese Nummer steht schon an „${vorher.dataset.name}“.`;
    });
  }
  const doppelteZeigen = (wurzel) => $$(".mat-teilnr-satz, .mat-punkte", wurzel).forEach(doppeltePruefen);
  document.addEventListener("input", (e) => {
    const gruppe = e.target.matches && e.target.matches(NUMMERFELD) ? e.target.closest(".mat-teilnr-satz, .mat-punkte") : null;
    if (gruppe) doppeltePruefen(gruppe);
  });

  function artikelDialog(a) {
    const textil = a.produkt.material_kind === "textil";
    const fest = !!a.stammdaten_fest;
    const nurDirekt = !(a.darf || {}).verwalten;
    const gesperrt = fest || nurDirekt;        // die freigabepflichtigen Felder nur lesen
    // Länge (Schritt 20): nur, wenn die Kategorie des Produkts eine vorsieht – oder der Artikel noch eine trägt.
    const mitLaenge = !!(a.laenge_moeglich || a.length_m);
    const offen = a.antraege || [];
    const lesefeld = (id, label, wert) => `<div><label for="${id}">${esc(label)}</label><input type="text" id="${id}" readonly value="${esc(wert)}" placeholder="–"></div>`;
    const festBlock = gesperrt ? `<div class="mat-fest mat-festblock">
        <div class="field-row"><div class="mat-festprodukt"><label for="ad-produkt-fest">Produkt</label><input type="text" id="ad-produkt-fest" readonly value="${esc(produktName(a.produkt))}"></div></div>
        <div class="field-row mat-stammzeile">${lesefeld("ad-sn", `Seriennummer${a.serial_generated ? " (vom System)" : ""}`, a.serial_no)}${lesefeld("ad-herst", "Herstellung (Monat)", datumAnzeige(a.manufactured_on, "monat"))}</div>
        <div class="field-row">${lesefeld("ad-kauf", "Kauf (Monat)", datumAnzeige(a.purchased_on, "monat"))}${lesefeld("ad-erst", "Erstgebrauch (Monat)", datumAnzeige(a.first_use_on, "monat"))}</div>
        <div class="field-row">${textil ? lesefeld("ad-ende", "Lebensende", datumAnzeige(a.retire_by, "tag")) : ""}${lesefeld("ad-int", "Prüfintervall am Artikel (Monate)", a.interval_months || "")}</div></div>
      <div class="help">${fest ? "Seit der ersten Prüfung fest – Teil des Prüfnachweises." : "Diese Stammdaten ändert der Materialwart."}</div>
      ${(a.bestandteile || []).length ? `<div class="mat-fest-teile"><p class="mat-bt-label">Seriennummern der Bestandteile</p>${bestandteilZeilen(a.bestandteile, true, "keine Nummer eingetragen")}</div>` : ""}
      ${fest ? `${offen.map(antragOffenHtml).join("")}
        ${antragMoeglich(a) ? '<div class="btn-row mat-antrag-knopf"><button class="btn secondary small" type="button" id="ad-antrag">Änderung beantragen</button></div>' : ""}` : ""}` : "";
    const sn = `<label for="ad-sn">Seriennummer des Herstellers</label><input type="text" id="ad-sn" ${TASTATUR_NUMMER} value="${a.serial_generated ? "" : esc(a.serial_no)}" placeholder="${a.serial_generated ? esc(a.serial_no) + " (vom System)" : ""}" maxlength="80">`;
    const herst = `<label for="ad-herst">Herstellung (Monat${textil ? ", Pflicht" : ""})</label>${datumFeld("ad-herst", a.manufactured_on, "monat")}`;
    const mitProdukt = !gesperrt && !!a.produkt_aenderbar;
    const produktFeldHtml = mitProdukt ? `<div class="mat-ad-produkt"><label for="ad-q">Produkt</label>
        <div id="ad-produkt" class="mat-gewaehlt">${produktGewaehltHtml(a.produkt)}${a.entwurf ? "" : ' <button class="lnk" type="button" id="ad-anders">anderes Produkt</button>'}</div>
        ${a.entwurf ? "" : `<div class="mat-produktwahl" id="ad-wahl" hidden><input type="search" id="ad-q" placeholder="Hersteller, Modell, Bemerkung, Artikelnummer …" autocomplete="off" ${TASTATUR_SUCHE}>
          <div id="ad-treffer" class="mat-treffer"></div></div>`}
        <div class="help" id="ad-produkt-hilfe">${a.entwurf ? esc(PRODUKT_ENTWURF) : "Bis zur ersten Prüfung änderbar – danach per Änderungsantrag."}</div>
        <p class="error" id="ad-produkt-fehler" hidden></p>
        <div class="notice small" id="ad-folgen" hidden></div></div>` : "";
    const faellig = `<div ${a.status === "neu" ? "hidden" : ""}><label for="ad-due">Nächste Prüfung</label>${datumFeld("ad-due", a.next_due_on, "tag")}
          <div class="help">Nur vorziehen – später setzt sie eine Prüfung.</div></div>`;
    dialog(`<h2>Artikel ${esc(a.inventory_no)} bearbeiten</h2>
      ${festBlock}
      ${produktFeldHtml}
      ${gesperrt ? "" : `<div class="field-row mat-stammzeile"><div>${sn}</div><div>${herst}</div></div>
      <div class="help">Seriennummer: Leer lassen behält die Nummer. Eine echte Herstellernummer ersetzt die vom System vergebene.</div>
      <div class="field-row"><div><label for="ad-kauf">Kauf (Monat)</label>${datumFeld("ad-kauf", a.purchased_on, "monat")}</div>
        <div><label for="ad-erst">Erstgebrauch (Monat)</label>${datumFeld("ad-erst", a.first_use_on, "monat")}</div></div>
      ${(a.bestandteile || []).length && a.bestandteile_direkt ? teilnummernSatz("ad-tn", a.bestandteile, "Freiwillig – leer lassen, wo es keine gibt. Nach der ersten Prüfung trägt sie der Prüfer in der Prüfung ein.") : ""}`}
      <div class="field-row">${gesperrt ? faellig + "<div></div>" : `<div><label for="ad-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="ad-int" min="1" max="120" value="${a.interval_months || ""}" placeholder="vom Produkt/Ordner"></div>
        ${faellig}`}</div>
      ${textil && !gesperrt ? `<div class="field-row" id="ad-ende-zeile"><div><label for="ad-ende">Lebensende</label>${datumFeld("ad-ende", a.retire_by, "tag")}<div class="help">Nur vorziehen. Leer lassen behält das Lebensende.</div></div><div></div></div>` : ""}
      ${mitLaenge || mitProdukt ? `<div class="field-row" id="ad-laenge-zeile"${mitLaenge ? "" : " hidden"}><div><label for="ad-laenge">Länge (m)</label><input type="text" id="ad-laenge" class="mat-laenge-feld" inputmode="decimal" autocomplete="off" maxlength="10" placeholder="z. B. 57,5" value="${esc(laengeText(a.length_m, false))}">
        <div class="help">Tatsächliche Länge in Metern, eine Nachkommastelle. Ein Prüfpunkt „Länge“ fragt sie bei jeder Prüfung ab.</div></div><div></div></div>` : ""}
      <label for="ad-notes">Bemerkung</label><textarea id="ad-notes" rows="3" maxlength="4000">${esc(a.notes || "")}</textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ad-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
      doppelteZeigen(body);
      // Ein anderes Produkt (null: es bleibt). Der Dialog zeigt es mit seinen Folgen; Lebensende und Länge folgen ihm.
      let neuesProdukt = null;
      const anders = $("#ad-anders", body);
      const produktFehler = (text) => {
        const el = $("#ad-produkt-fehler", body);
        el.textContent = text || "";
        el.hidden = !text;
      };
      function produktSetzen(p) {
        produktFehler("");
        neuesProdukt = p && p.id !== a.produkt.id ? p : null;
        const zeige = neuesProdukt || a.produkt;
        $("#ad-produkt", body).innerHTML = `${produktGewaehltHtml(zeige)} <button class="lnk" type="button" id="ad-anders">anderes Produkt</button>${neuesProdukt ? ' <button class="lnk" type="button" id="ad-zurueck">zurück zum bisherigen</button>' : ""}`;
        $("#ad-wahl", body).hidden = true;
        trefferLeeren($("#ad-treffer", body));
        $("#ad-q", body).value = "";
        $("#ad-anders", body).onclick = suchen;
        const zurueck = $("#ad-zurueck", body);
        if (zurueck) zurueck.onclick = () => { produktSetzen(null); fokus($("#ad-anders", body)); };
        const folgen = $("#ad-folgen", body);
        folgen.innerHTML = neuesProdukt ? `<p>Neues Produkt: ${esc(produktName(neuesProdukt))}. Beim Speichern:</p><ul>${produktFolgen(a, neuesProdukt).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
        folgen.hidden = !neuesProdukt;
        // Lebensende und Länge nach dem neuen Produkt: Das Lebensende rechnet der Server, die Länge nur, wo die Kategorie sie vorsieht.
        const ende = $("#ad-ende-zeile", body);
        if (ende) ende.hidden = Boolean(neuesProdukt);
        const laenge = (neuesProdukt || a.produkt).laenge_moeglich || (!neuesProdukt && a.length_m);
        $("#ad-laenge-zeile", body).hidden = !laenge;
        // Die Seriennummern der Bestandteile gehören zum bisherigen Produkt – mit einem anderen fallen sie weg.
        const tn = $("#ad-tn", body);
        if (tn) tn.hidden = Boolean(neuesProdukt);
        const herstLabel = $('label[for="ad-herst"]', body);
        if (herstLabel) herstLabel.textContent = `Herstellung (Monat${(neuesProdukt || a.produkt).material_kind === "textil" ? ", Pflicht" : ""})`;
      }
      function suchen() {
        $("#ad-wahl", body).hidden = false;
        produktFehler("");
        fokus($("#ad-q", body));
      }
      if (anders) {
        anders.onclick = suchen;
        let los = null;
        $("#ad-q", body).addEventListener("input", () => {
          clearTimeout(los);
          los = setTimeout(() => {
            const q = $("#ad-q", body).value.trim();
            if (!q) { trefferLeeren($("#ad-treffer", body)); return; }
            produktTreffer($("#ad-treffer", body), q, (p) => { produktSetzen(p); fokus($("#ad-anders", body)); }, '<p class="help">Kein Produkt gefunden.</p>');
          }, 200);
        });
      }
      const zumAntrag = $("#ad-antrag", body);
      if (zumAntrag) zumAntrag.onclick = () => antragDialog(a);
      // Den eigenen offenen Antrag zurückziehen: Rückfrage darüber, danach schließt der Dialog und die Seite zeichnet neu.
      body.querySelectorAll('[data-act="antrag-zurueck"]').forEach((b) => {
        b.onclick = () => antragZurueckziehen(offen.find((x) => x.id === +b.dataset.id), () => { dlg.close(); return zeigen(artikel); });
      });
      $("#ad-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        let daten;
        try {
          // Fest oder Prüfer: nur die direkten Felder – die übrigen schickt der Dialog gar nicht erst.
          daten = { stand: a.stand, next_due_on: datumWert($("#ad-due", body), "Nächste Prüfung") || null, notes: $("#ad-notes", body).value };
          if (!gesperrt) {
            Object.assign(daten, {
              purchased_on: datumBehalten(datumWert($("#ad-kauf", body), "Kauf"), a.purchased_on),
              first_use_on: datumBehalten(datumWert($("#ad-erst", body), "Erstgebrauch"), a.first_use_on),
              interval_months: $("#ad-int", body).value || null, serial_no: $("#ad-sn", body).value,
              manufactured_on: datumBehalten(datumWert($("#ad-herst", body), "Herstellung"), a.manufactured_on) });
            if (textil && !neuesProdukt) daten.retire_by = datumWert($("#ad-ende", body), "Lebensende") || null;
            if (neuesProdukt) daten.product_id = neuesProdukt.id;
            else if ($("#ad-tn", body)) daten.bestandteil_nummern = teilnummernLesen($("#ad-tn", body));
          }
          const laengeZeile = $("#ad-laenge-zeile", body);
          if (laengeZeile && !laengeZeile.hidden) daten.length_m = $("#ad-laenge", body).value.trim() || null;
        } catch (e) { toast(e.message, true); return; }
        knopf.disabled = true;
        try {
          await api(`${API}/artikel/${a.id}`, { method: "PUT", body: daten });
          dlg.close();
          toast(neuesProdukt ? `Gespeichert – Produkt jetzt ${produktName(neuesProdukt)}` : "Gespeichert");
          zeigen(artikel);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }
  // Ein Tagesdatum (aus der Zeit vor den Monatsfeldern) bleibt erhalten, wenn der Monat derselbe ist.
  const datumBehalten = (neu, alt) => (neu && alt && alt.slice(0, 7) === neu ? alt : neu || null);

  /* --- Änderungsanträge (Entscheidungen vom 21.10.2026; seit dem 24.10.2026 an allen Stammdaten) --------------------
     Seit der ersten Prüfung stehen die Stammdaten fest. Materialwart und Prüfer beantragen eine Änderung mit
     Begründung – alle Felder, die sich ändern sollen, in EINEM Antrag; die Materialwarte des Ordners bestätigen oder
     lehnen ab (Bestand → Änderungsanträge), den eigenen Antrag eingeschlossen. Ein offener Antrag je Artikel;
     festgeschriebene Protokolle behalten die alten Werte, Journal und Lebenslauf zeigen die Änderung. Den eigenen
     offenen Antrag zieht der Antragsteller selbst zurück. Die Werte kommen als Text vom Server (alt_text, neu_text). */
  const ANTRAG_STATUS = { offen: "offen", bestaetigt: "bestätigt", abgelehnt: "abgelehnt", zurueckgezogen: "zurückgezogen" };
  const antragAenderungen = (x, mitPasst) => `<ul class="mat-antrag-aenderungen">${(x.aenderungen || []).map((y) => `<li>${esc(y.feld_text)}: ${esc(y.alt_text)} → <strong>${esc(y.neu_text)}</strong>${mitPasst && !y.passt ? ' <span class="mat-warn">(am Artikel inzwischen anders)</span>' : ""}</li>`).join("")}</ul>`;
  // Kein offener Antrag, nach der ersten Prüfung, nicht ausgesondert, Materialwart oder Prüfer (darf_antrag vom Server).
  const antragMoeglich = (a) => Boolean(a.darf_antrag);
  // Laufende Rückrufe, aus denen der Artikel nach der Änderung fiele oder in die er käme (x.rueckruf, nur bei offenen
  // Anträgen – neue Seriennummer oder anderes Produkt) – auf der Karte und in der Rückfrage „Bestätigen“; das Journal
  // vermerkt es beim Bestätigen. Dazu Rückrufe, die ihn weiter treffen und durch eine Prüfung erledigt waren: Nach dem
  // Antrag zählt nur eine neue Prüfung (R1) – sie gelten wieder als offen (Liste nach dem Merge, 18).
  const antragRueckruf = (x) => {
    const f = x.rueckruf || {};
    const titel = (l) => l.map((r) => `„${esc(r.title)}“`).join(", ");
    const raus = f.nicht_mehr || [];
    const rein = f.neu || [];
    const wieder = f.wieder_offen || [];
    return (raus.length ? `<p class="notice small">Artikel ist von ${raus.length > 1 ? "den Rückrufen" : "Rückruf"} ${titel(raus)} betroffen – nach der Änderung ${raus.length > 1 ? "treffen sie" : "trifft der Rückruf"} ihn nicht mehr.</p>` : "")
      + (rein.length ? `<p class="notice small">Nach der Änderung trifft ihn ${rein.length > 1 ? "die laufenden Rückrufe" : "der laufende Rückruf"} ${titel(rein)}.</p>` : "")
      + (wieder.length ? `<p class="notice small">${wieder.length > 1 ? "Die Rückrufe" : "Der Rückruf"} ${titel(wieder)} ${wieder.length > 1 ? "gelten" : "gilt"} danach wieder als offen – der Artikel muss erneut geprüft werden.</p>` : "");
  };
  // Ein offener Antrag als Hinweis an Artikel und Dialog „Bearbeiten“: wer entscheiden darf, kommt mit „Entscheiden“ in
  // die Liste; der eigene trägt das graue „Antrag zurückziehen“. Auf der Artikelseite stehen die Anträge als Abschnitt
  // „Offene Änderungsanträge“ am Anfang der rechten Spalte (Wunsch vom 22.10.2026) – Lesefolge = DOM-Folge.
  const antragOffenHtml = (x) => `<div class="notice small mat-antrag-offen"><p>Änderung beantragt am ${esc(S.fmtDate(x.created_at))}${x.antragsteller ? ` von ${person(x.antragsteller)}` : ""} – wartet auf einen Materialwart des Ordners.</p>
    ${antragAenderungen(x)}${x.entscheiden || x.eigen ? `<div class="btn-row">${x.entscheiden ? '<a class="btn secondary small" href="/materialablage/bestand/antraege">Entscheiden</a>' : ""}${x.eigen ? `<button class="btn secondary small" type="button" data-act="antrag-zurueck" data-id="${x.id}">Antrag zurückziehen</button>` : ""}</div>` : ""}</div>`;
  // Rückfrage, dann zurückziehen (nur der Antragsteller, nur offen – der Server prüft es). Keine Mail.
  async function antragZurueckziehen(x, danach) {
    if (!x) return;
    if (!(await confirm(`Deinen Antrag (${x.felder_text}) zurückziehen? Niemand entscheidet dann mehr darüber; neu beantragen kannst du jederzeit.`, "Zurückziehen"))) return;
    try {
      await api(`${API}/antraege/${x.id}/zurueckziehen`, { method: "POST", body: {} });
      toast("Antrag zurückgezogen");
      await danach();
    } catch (e) { toast(e.message, true); }
  }

  // Der Antragsdialog: alle freigabepflichtigen Felder mit den heutigen Werten; geschickt wird nur, was sich ändert.
  // Produkt mit „anderes Produkt“ und seinen Folgen. Begründung Pflicht.
  function antragDialog(a) {
    const textil = a.produkt.material_kind === "textil";
    // Lebensende (Wunsch vom 25.10.2026): vorziehen oder ein vorgezogenes wieder nach hinten – höchstens bis zur
    // Rechnung aus Herstellung und Lebensdauer (genau die Rechnung: nicht mehr von Hand gesetzt).
    const berechnet = a.lebensdauer && a.lebensdauer.berechnet;
    const endeHilfe = berechnet ? `Vorziehen oder wieder nach hinten – höchstens bis ${esc(fmtTag(berechnet))} (Herstellung + ${a.lebensdauer.jahre} Jahre).` : "";
    const mitProdukt = !!a.produkt_beantragbar;
    // Ein laufender Rückruf mit Seriennummernliste trifft den Artikel über seine Nummer – mit einer neuen nicht mehr.
    const rueckrufe = (a.rueckrufe || []).filter((r) => !r.alle);
    dialog(`<h2>Änderung beantragen – ${esc(a.inventory_no)}</h2>
      <p class="help">Seit der ersten Prüfung stehen die Stammdaten fest. Ändere, was nicht stimmt – ein Materialwart des Ordners bestätigt oder lehnt ab, du bekommst Bescheid. Festgeschriebene Protokolle behalten die alten Angaben.</p>
      ${mitProdukt ? `<div class="mat-ad-produkt"><label for="aa-q">Produkt</label>
        <div id="aa-produkt" class="mat-gewaehlt">${produktGewaehltHtml(a.produkt)} <button class="lnk" type="button" id="aa-anders">anderes Produkt</button></div>
        <div class="mat-produktwahl" id="aa-wahl" hidden><input type="search" id="aa-q" placeholder="Hersteller, Modell, Bemerkung, Artikelnummer …" autocomplete="off" ${TASTATUR_SUCHE}>
          <div id="aa-treffer" class="mat-treffer"></div></div>
        <p class="error" id="aa-produkt-fehler" hidden></p>
        <div class="notice small" id="aa-folgen" hidden></div></div>`
        : `<p class="small">Produkt: <strong>${nameHtml(a.produkt)}</strong>${zusatzHtml(a.produkt)}</p>`}
      <div class="field-row mat-antragzeile"><div><label for="aa-sn">Seriennummer</label><input type="text" id="aa-sn" ${TASTATUR_NUMMER} maxlength="80" value="${esc(a.serial_no)}"></div>
        <div><label for="aa-herst">Herstellung (Monat)</label>${datumFeld("aa-herst", a.manufactured_on, "monat")}</div></div>
      <div class="field-row"><div><label for="aa-kauf">Kauf (Monat)</label>${datumFeld("aa-kauf", a.purchased_on, "monat")}</div>
        <div><label for="aa-erst">Erstgebrauch (Monat)</label>${datumFeld("aa-erst", a.first_use_on, "monat")}</div></div>
      <div class="field-row"><div id="aa-ende-feld"${textil ? "" : " hidden"}><label for="aa-ende">Lebensende</label>${datumFeld("aa-ende", a.retire_by, "tag")}${endeHilfe ? `<div class="help" id="aa-ende-hilfe">${endeHilfe}</div>` : ""}</div>
        <div><label for="aa-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="aa-int" min="1" max="120" value="${a.interval_months || ""}" placeholder="vom Produkt/Ordner"></div></div>
      ${(a.bestandteile || []).length ? teilnummernSatz("aa-tn", a.bestandteile, "Leer heißt: dieses Stück hat keine Nummer. Mit einem anderen Produkt beantragst du sie getrennt.") : ""}
      ${rueckrufe.length ? `<p class="notice small">Artikel ist von ${rueckrufe.length > 1 ? "den Rückrufen" : "Rückruf"} ${rueckrufe.map((r) => `„${esc(r.title)}“`).join(", ")} betroffen – nach einer Änderung der Seriennummer ${rueckrufe.length > 1 ? "treffen sie" : "trifft der Rückruf"} ihn nicht mehr (außer die neue Nummer steht ebenfalls in seiner Liste).</p>` : ""}
      <label for="aa-grund">Begründung (Pflicht)</label>
      <textarea id="aa-grund" rows="3" maxlength="1000" placeholder="z. B. Etikett beim Prüfen falsch abgelesen, Herstellernummer nachträglich gefunden"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="aa-ok" type="button">Antrag senden</button></div>`,
    (dlg, body) => {
      doppelteZeigen(body);
      let neuesProdukt = null;
      const fehler = (text) => { const el = $("#aa-produkt-fehler", body); el.textContent = text || ""; el.hidden = !text; };
      function produktSetzen(p) {
        fehler("");
        neuesProdukt = p && p.id !== a.produkt.id ? p : null;
        $("#aa-produkt", body).innerHTML = `${produktGewaehltHtml(neuesProdukt || a.produkt)} <button class="lnk" type="button" id="aa-anders">anderes Produkt</button>${neuesProdukt ? ' <button class="lnk" type="button" id="aa-zurueck">zurück zum bisherigen</button>' : ""}`;
        $("#aa-wahl", body).hidden = true;
        trefferLeeren($("#aa-treffer", body));
        $("#aa-q", body).value = "";
        $("#aa-anders", body).onclick = suchen;
        const zurueck = $("#aa-zurueck", body);
        if (zurueck) zurueck.onclick = () => { produktSetzen(null); fokus($("#aa-anders", body)); };
        const folgen = $("#aa-folgen", body);
        folgen.innerHTML = neuesProdukt ? `<p>Neues Produkt: ${esc(produktName(neuesProdukt))}. Nach der Bestätigung:</p><ul>${produktFolgen(a, neuesProdukt).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
        folgen.hidden = !neuesProdukt;
        // Das Lebensende rechnet nach dem neuen Produkt – ändern lässt es sich dann mit einem späteren Antrag; ebenso die
        // Seriennummern der Bestandteile (sie gehören zum bisherigen Produkt).
        $("#aa-ende-feld", body).hidden = !textil || Boolean(neuesProdukt);
        if ($("#aa-tn", body)) $("#aa-tn", body).hidden = Boolean(neuesProdukt);
      }
      function suchen() { $("#aa-wahl", body).hidden = false; fehler(""); fokus($("#aa-q", body)); }
      if (mitProdukt) {
        $("#aa-anders", body).onclick = suchen;
        let los = null;
        $("#aa-q", body).addEventListener("input", () => {
          clearTimeout(los);
          los = setTimeout(() => {
            const q = $("#aa-q", body).value.trim();
            if (!q) { trefferLeeren($("#aa-treffer", body)); return; }
            produktTreffer($("#aa-treffer", body), q, (p) => { produktSetzen(p); fokus($("#aa-anders", body)); }, '<p class="help">Kein Produkt gefunden.</p>');
          }, 200);
        });
      }
      $("#aa-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const daten = { begruendung: $("#aa-grund", body).value };
        const anders = (neu, alt) => (neu || null) !== (alt || null);
        try {
          const sn = $("#aa-sn", body).value.trim();
          if (sn !== a.serial_no) daten.serial_no = sn;
          for (const [id, feld, name] of [["aa-herst", "manufactured_on", "Herstellung"], ["aa-kauf", "purchased_on", "Kauf"],
            ["aa-erst", "first_use_on", "Erstgebrauch"]]) {
            const wert = datumBehalten(datumWert($(`#${id}`, body), name), a[feld]);
            if (anders(wert, a[feld])) daten[feld] = wert;
          }
          if (textil && !neuesProdukt) {
            const ende = datumWert($("#aa-ende", body), "Lebensende") || null;
            if (anders(ende, a.retire_by)) daten.retire_by = ende;
          }
          const iv = $("#aa-int", body).value;
          if ((iv ? +iv : null) !== (a.interval_months || null)) daten.interval_months = iv || null;
          if (neuesProdukt) daten.product_id = neuesProdukt.id;
          else if ($("#aa-tn", body)) {
            // Nur die geänderten Stück (der Server prüft ohnehin gegen den Artikel).
            const alt = {};
            (a.bestandteile || []).forEach((z) => (z.nummern || []).forEach((n, i) => { alt[`${z.id}-${i + 1}`] = n || ""; }));
            const geaendert = teilnummernLesen($("#aa-tn", body)).filter((x) => (alt[`${x.bestandteil_id}-${x.stueck}`] || "") !== x.seriennummer);
            if (geaendert.length) daten.bestandteil_nummern = geaendert;
          }
        } catch (e) { toast(e.message, true); return; }
        if (Object.keys(daten).length === 1) { toast("Bitte mindestens ein Feld ändern.", true); return; }
        if (!daten.begruendung.trim()) { toast("Bitte begründe die Änderung.", true); fokus($("#aa-grund", body)); return; }
        knopf.disabled = true;
        try {
          const r = await api(`${API}/artikel/${a.id}/antrag`, { method: "POST", body: daten });
          dlg.close();
          // Ohne zuständiges Konto ging die Mail an die Material-Verwaltung (Prüfung Ablauf, Befund 4).
          const ohne = r.antrag && r.antrag.ohne_zustaendige;
          toast(r.mail ? (ohne ? "Antrag gesendet – die Material-Verwaltung bekommt eine Mail." : "Antrag gesendet – die Materialwarte des Ordners bekommen eine Mail.")
            : ohne ? "Antrag gesendet – der Ordner hat zurzeit keinen Materialwart, der ihn entscheiden kann." : "Antrag gesendet – er wartet auf einen Materialwart des Ordners.");
          zeigen(artikel);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Artikel anlegen ---------------------------------------------------------------------------- */
  async function artikelNeu() {
    if (!DARF.verwalten) { inhalt.innerHTML = '<p class="error">Artikel legen nur Materialwarte an.</p>'; return; }
    // Wählbar sind nur Ordner, die das Konto verwaltet; der Weg dorthin steht grau dabei.
    const wahl = ordnerOptionen(await ordnerBaum(), verwaltet, DATEN.ordner);
    seitenTitel("Artikel anlegen");
    if (!wahl.anzahl) { inhalt.innerHTML = `<h1>Artikel anlegen</h1>${leer("Du verwaltest noch keinen Ordner – Artikel legt an, wer den Ordner verwaltet.")}`; return; }
    leisteMarkieren(DATEN.ordner);
    let produkt = null;
    inhalt.innerHTML = `<div class="page-head"><h1>Artikel anlegen${infoKnopf("Artikel anlegen", "Neu angelegte Artikel stehen auf <strong>neu</strong>, bis ein Prüfer die Eingangsprüfung gemacht hat – erst sie gibt sie frei und setzt die erste Fälligkeit.")}</h1></div>
      <div class="mat-formular">
        <label for="an-q">Produkt aus dem Katalog</label>
        <div class="mat-produktwahl"><input type="search" id="an-q" placeholder="Hersteller, Modell, Bemerkung, Artikelnummer …" autocomplete="off" ${TASTATUR_SUCHE}>
          <div id="an-treffer" class="mat-treffer"></div></div>
        <div id="an-produkt" class="mat-gewaehlt" hidden></div>
        <p class="help">Fehlt das Produkt im Katalog? <button type="button" class="lnk" data-act="melden">Fehlendes Produkt melden</button>
          – die Material-Verwaltung nimmt es auf, du bekommst Bescheid.</p>
        <label for="an-ordner">Ordner</label><select id="an-ordner">${wahl.html}</select>
        <label for="an-sn">Seriennummer des Herstellers${infoKnopf("Seriennummer des Herstellers", "Ohne Herstellernummer vergibt das System eine eindeutige (STR-…), die dann am Artikel angebracht wird. Die Inventarnummer vergibt immer das System.")}</label><input type="text" id="an-sn" maxlength="80" placeholder="leer lassen, wenn der Hersteller keine vergibt" ${TASTATUR_NUMMER}>
        <div class="field-row"><div><label for="an-herst">Herstellung (Monat)</label>${datumFeld("an-herst", "", "monat")}</div>
          <div><label for="an-kauf">Kauf (Monat)</label>${datumFeld("an-kauf", "", "monat")}</div></div>
        <div class="field-row"><div><label for="an-erst">Erstgebrauch (Monat)</label>${datumFeld("an-erst", "", "monat")}</div>
          <div><label for="an-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="an-int" min="1" max="120" placeholder="vom Produkt/Ordner"></div></div>
        <div class="field-row"><div id="an-ende-feld" hidden><label for="an-ende">Lebensende</label>${datumFeld("an-ende", "", "tag")}<div class="help" id="an-ende-hilfe"></div></div>
          <div><p class="help" id="an-due-hilfe"></p></div></div>
        <div class="field-row"><div id="an-laenge-feld" hidden><label for="an-laenge">Länge (m)</label><input type="text" id="an-laenge" class="mat-laenge-feld" inputmode="decimal" autocomplete="off" maxlength="10" placeholder="z. B. 57,5">
          <div class="help">Tatsächliche Länge in Metern, eine Nachkommastelle – ein Prüfpunkt „Länge“ fragt sie bei jeder Prüfung ab.</div></div><div></div></div>
        <div id="an-bestandteile" hidden></div>
        <label for="an-notes">Bemerkung</label><textarea id="an-notes" rows="2" maxlength="4000"></textarea>
        <div class="btn-row mat-knoepfe"><button class="btn" data-act="anlegen">Anlegen</button>
          <button class="btn secondary" data-act="anlegen-weiter" title="Produkt und Ordner bleiben für den nächsten Artikel stehen">Anlegen und nächsten</button></div>
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
        // Bestandteil-Liste des Produkts (Schritt 25): je Stück ein freiwilliges Feld „Seriennummer“.
        if (teilnrFuer !== produkt.id) {
          teilnrFuer = produkt.id;
          const el = $("#an-bestandteile");
          el.innerHTML = (v.bestandteile || []).length ? teilnummernSatz("an-tn", v.bestandteile, "Freiwillig – leer lassen, wo es keine gibt.") : "";
          doppelteZeigen(el);
          el.hidden = !(v.bestandteile || []).length;
        }
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
    let teilnrFuer = null;
    function bestandteileLeeren() {
      teilnrFuer = null;
      $("#an-bestandteile").hidden = true;
      $("#an-bestandteile").innerHTML = "";
    }
    $("#an-ende").addEventListener("input", (e) => { e.target.dataset.selbst = "1"; });
    function waehlen(p) {
      produkt = p;
      $("#an-produkt").hidden = false;
      $("#an-produkt").innerHTML = `${produktFoto(p)}<strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${artNrKurz(p.article_no)} ${demoMarke(p.demo)}
        <span class="mat-art">${esc(MATERIALART[p.material_kind])}</span> <button class="lnk" type="button" id="an-anders">anderes Produkt</button>`;
      trefferLeeren($("#an-treffer"));
      $("#an-q").value = "";
      $("#an-anders").onclick = () => { produkt = null; $("#an-produkt").hidden = true; bestandteileLeeren(); fokus($("#an-q")); };
      $("#an-ende").dataset.selbst = "";
      bestandteileLeeren();
      // Das Längenfeld nur bei Produkten, deren Kategorie eine Länge vorsieht (laenge_moeglich aus produkt_json).
      $("#an-laenge-feld").hidden = !p.laenge_moeglich;
      if (!p.laenge_moeglich) $("#an-laenge").value = "";
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
        if (!$("#an-laenge-feld").hidden) daten.length_m = $("#an-laenge").value.trim() || null;
        if (teilnrFuer === produkt.id && !$("#an-bestandteile").hidden) daten.bestandteil_nummern = teilnummernLesen($("#an-bestandteile"));
      } catch (e) { toast(e.message, true); return; }
      try {
        const r = await api(`${API}/artikel`, { method: "POST", body: daten });
        // Hinweise des Servers gehen nicht in einem Toast unter – ein Dialog, der mit „Zum Artikel“ bzw. „Nächsten
        // anlegen“ weiterführt.
        const weiterHier = () => {
          $("#an-sn").value = ""; $("#an-notes").value = "";
          $$("#an-bestandteile .mat-teilnr").forEach((f) => { f.value = ""; });
          fokus($("#an-sn"));
        };
        if ((r.hinweise || []).length) {
          dialog(`<h2>${esc(r.artikel.inventory_no)} angelegt</h2>
            <ul class="mat-an-hinweise">${r.hinweise.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>
            <div class="dlg-actions">${weiter ? '<button class="btn" type="button" data-close>Nächsten anlegen</button>'
              : `<a class="btn" href="/materialablage/artikel/${r.artikel.id}">Zum Artikel</a>`}</div>`,
          (dlg) => { if (weiter) dlg.addEventListener("close", weiterHier, { once: true }); else dlg.addEventListener("close", () => { location.href = `/materialablage/artikel/${r.artikel.id}`; }, { once: true }); });
          return;
        }
        if (!weiter) { location.href = `/materialablage/artikel/${r.artikel.id}`; return; }
        toast(`${r.artikel.inventory_no} angelegt (Seriennummer ${r.artikel.serial_no})`);
        weiterHier();
      } catch (e) { toast(e.message, true); }
    }
    // Die eigenen Meldungen unter dem Formular: Ist eine eingepflegt, wählt ein Klick ihr Produkt.
    async function meldungenZeigen() {
      const ziel = $("#an-meldungen");
      try {
        const liste = (await api(`${API}/meldungen?eigene=1&status=alle`)).meldungen.slice(0, 10);
        ziel.innerHTML = liste.length ? `<section class="section"><h2>Deine Produktmeldungen</h2><ul class="mat-meldeliste">
          ${liste.map((m) => `<li>${meldestatusMarke(m.status)} <strong>${esc(meldungName(m))}</strong>${artNrKurz(m.article_no)}
            <span class="muted small">gemeldet am ${esc(fmtTag(m.created_at))}</span>
            ${m.status === "eingepflegt" && m.produkt ? `<button type="button" class="btn secondary small" data-act="meldung-waehlen" data-pid="${m.produkt.id}">Artikel davon anlegen</button>` : ""}
            ${m.status === "abgelehnt" ? `<div class="small">Abgelehnt: <span class="mat-text">${esc(m.answer)}</span></div>` : ""}</li>`).join("")}</ul>
          <p class="small"><a href="/materialablage/katalog/meldungen">Alle deine Meldungen →</a></p></section>` : "";
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

  const KATALOG_SORT = [["Hersteller", "hersteller"], ["Produkt", "produkt"], ["Kategorie", "kategorie"], ["Materialart", "materialart"],
                        ["Intervall", "intervall"], ["Lebensdauer", "lebensdauer"], ["Bestand", "bestand"]];
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
    /* Zurück von einer Produktseite (Browserprüfung vor dem Merge, V3): Die Seite kam neu und stand oben, die Endlosliste
       wieder bei 50. Suche, Sortierung, wie viel nachgeladen war und die Scrollhöhe stehen deshalb im Eintrag des
       Verlaufs (history.state, gemerkt beim Verlassen) – nur für dieselbe Kategorie; ein neuer Aufruf hat keinen. Das
       Wiederherstellen übernimmt liste(), der Browser rollt nicht selbst dazwischen. */
    let geladenJetzt = 0;
    const gemerkt = history.state && history.state.katalog;
    let wiederher = gemerkt && (gemerkt.kategorie || null) === kategorie ? gemerkt : null;
    if (wiederher) { q = wiederher.q || ""; sort = wiederher.sort || sort; }
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    const merken = () => {
      try {
        history.replaceState(Object.assign({}, history.state, { katalog: { kategorie, q, sort, geladen: geladenJetzt, y: Math.round(window.scrollY) } }), "");
      } catch (e) { /* ohne Verlauf eben ohne Rückweg an die Stelle */ }
    };
    window.addEventListener("pagehide", merken);
    inhalt.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("a[href]")) merken(); }, true);
    // Enge Tabelle und Karte (Lieferung 5): der Hersteller klein über dem Produkt, die kurzen Angaben zu zweit.
    const produktZeile = (x) => `<tr><td data-l="Hersteller" class="mat-schmal-weg">${esc(x.manufacturer || "")}</td>
          <td data-l="Produkt" class="mat-k-titel">${x.manufacturer ? `<div class="mat-schmal-zusatz small muted">${esc(x.manufacturer)}</div>` : ""}${x.vorschau ? `<img class="mat-mini" src="${esc(x.vorschau)}" alt="" loading="lazy">` : ""}<a href="/materialablage/katalog/produkt/${x.id}"><strong>${nameHtml(x, true)}</strong></a>${zusatzHtml(x)}${artNrKurz(x.article_no)}${demoMarke(x.demo)}</td>
          <td data-l="Kategorie">${esc(x.category_name || "")}</td><td data-l="Materialart" class="mat-k-halb">${esc(MATERIALART[x.material_kind])}</td>
          <td data-l="Intervall" class="mat-k-halb">${x.intervall.monate ? `${x.intervall.monate} Mon.` : "–"}</td>
          <td data-l="Lebensdauer" class="mat-k-halb">${x.lifetime_years ? `${x.lifetime_years} J.` : "–"}</td><td data-l="Bestand" class="mat-k-halb">${x.bestand}</td></tr>`;
    async function liste(springen) {
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
      ziel.innerHTML = d.produkte.length ? `${kartenKopf(KATALOG_SORT, s)}<table class="list mat-tabelle mat-karten mat-katalogliste"><thead><tr>${sortKopf("Hersteller", "hersteller", s, { klasse: "mat-schmal-weg" })}${sortKopf("Produkt", "produkt", s, { vor: kopfZusatz("Hersteller", "hersteller", s, "schmal") })}${sortKopf("Kategorie", "kategorie", s)}${sortKopf("Materialart", "materialart", s)}${sortKopf("Intervall", "intervall", s)}${sortKopf("Lebensdauer", "lebensdauer", s)}${sortKopf("Bestand", "bestand", s)}</tr></thead>
        <tbody>${d.produkte.map(produktZeile).join("")}</tbody></table><p class="help mat-endlos" id="kat-mehr"></p>`
        : leer(q || kategorie ? "Kein Produkt in dieser Auswahl." : "Der Katalog ist noch leer.");
      const such = $(".mat-suchzeile");
      const zurueck = wiederher;
      wiederher = null;
      if (springen && such) {
        // Kategorie aus der Schublade gewählt (Telefon, Tablet hochkant): Die Suchzeile kommt unter die Kopfleiste, die
        // Liste direkt darunter – vorher sah man nur den Kopf der Kategorie (Browserprüfung vor dem Merge, V1).
        const oben = parseFloat(getComputedStyle(such).top) || 0;
        window.scrollTo(0, ziel.getBoundingClientRect().top + window.scrollY - such.offsetHeight - oben);
      } else if (!zurueck && such && ziel.getBoundingClientRect().top < such.getBoundingClientRect().bottom) {
        // War die Liste schon unter der Suchzeile weggescrollt, beginnt die neue Auswahl direkt unter ihr.
        window.scrollBy(0, ziel.getBoundingClientRect().top - such.getBoundingClientRect().bottom);
      }
      geladenJetzt = d.produkte.length;
      if (!d.produkte.length) { if (zurueck) window.scrollTo(0, zurueck.y || 0); return; }
      const mehr = $("#kat-mehr");
      let seite = 1;
      let geladen = d.produkte.length;
      let gesamt = d.gesamt;
      let laedt = false;
      const stand = () => { mehr.textContent = geladen < gesamt ? `${geladen} von ${gesamt} – weitere kommen beim Scrollen` : plural(gesamt, "Produkt", "Produkte"); };
      const anhaengen = (n) => {
        seite += 1;
        $("tbody", ziel).insertAdjacentHTML("beforeend", n.produkte.map(produktZeile).join(""));
        geladen += n.produkte.length;
        gesamt = n.produkte.length ? n.gesamt : geladen;       // leer: inzwischen sind es weniger geworden
        geladenJetzt = geladen;
      };
      // Zurück von einer Produktseite: so weit nachladen wie vorher (höchstens 20 Seiten), dann an die alte Stelle.
      if (zurueck) {
        try {
          while (geladen < Math.min(zurueck.geladen || 0, gesamt, PRO_SEITE * 20)) {
            const n = await holen(seite + 1);
            if (meinLauf !== lauf) return;
            anhaengen(n);
            if (!n.produkte.length) break;
          }
        } catch (e) { /* dann eben nur bis hierher – weiter unten lädt das Scrollen nach */ }
        window.scrollTo(0, zurueck.y || 0);
      }
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
        anhaengen(n);
        stand();
        if (geladen >= gesamt) { beobachter.disconnect(); beobachter = null; return; }
        // Steht das Ende nach dem Anhängen noch im Bild (großer Bildschirm), gleich die nächste Seite.
        beobachter.unobserve(mehr);
        beobachter.observe(mehr);
      }, { rootMargin: "0px 0px 600px 0px" });
      beobachter.observe(mehr);
      nachladen = () => { if (beobachter) { stand(); beobachter.observe(mehr); } };
    }
    function zeichnen(springen) {
      const k = kats.find((x) => x.id === kategorie);
      const pfad = [];
      for (let x = k; x; x = kats.find((y) => y.id === x.parent_id)) pfad.unshift(x);
      leisteMarkieren(kategorie);
      seitenTitel(k ? k.name : "", "Katalog");     // auch beim Wechsel der Kategorie ohne Neuladen
      // Produkte samt Unterkategorien – dieselbe Zahl wie in der Leiste und wie die Liste darunter.
      const summe = (id) => (kats.find((x) => x.id === id).produkte || 0) + kats.filter((x) => x.parent_id === id).reduce((n, c) => n + summe(c.id), 0);
      const angaben = k ? [k.norm ? esc(k.norm) : "", k.default_material_kind ? `Materialart ${esc(MATERIALART[k.default_material_kind])}` : "",
        k.default_interval_months ? `Prüfintervall ${k.default_interval_months} Monate` : "", k.laenge_wirksam ? "Artikel haben eine Länge" : "",
        plural(summe(k.id), "Produkt", "Produkte")].filter(Boolean).join(" · ") : "";
      // Zum aktiven generischen Formular führt bei der Material-Verwaltung der Knopf „Generisches Formular“, sonst der Verweis in der Angabenzeile.
      // Ohne eigenes gilt das der nächsten Oberkategorie mit einem (katalog.py prüft danach) – die Zeile nennt es mit Link: zur
      // Kategorie, wo der Knopf steht (Material-Verwaltung), sonst zum Formular (Feinschliff aus den Wiki-Fragen, K9).
      const geerbt = k && !k.aktives_formular ? pfad.slice(0, -1).reverse().find((x) => x.aktives_formular) : null;
      const formularZeile = !k ? "" : k.aktives_formular
        ? (DARF.katalog ? "" : ` · <a href="/materialablage/katalog/formular/${k.aktives_formular}">generisches Prüfformular</a>`)
        : !geerbt ? ' · <span class="muted">kein aktives generisches Prüfformular</span>'
          : ` · generisches Prüfformular von ${DARF.katalog
            ? `<a href="/materialablage/katalog?kategorie=${geerbt.id}" data-act="kategorie" data-id="${geerbt.id}">„${esc(geerbt.name)}“</a>`
            : `<a href="/materialablage/katalog/formular/${geerbt.aktives_formular}">„${esc(geerbt.name)}“</a>`}`;
      inhalt.innerHTML = `<div class="page-head"><h1>Katalog</h1>
          <div class="btn-row">${DARF.katalog ? '<button class="btn secondary" data-act="kat-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Kategorie<span class="k-anlegen"> anlegen</span></span></button><button class="btn secondary" data-act="produkt-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Produkt<span class="k-anlegen"> anlegen</span></span></button>' : ""}
            ${DARF.lesen || DARF.katalog ? `<a class="btn secondary mat-mit-zahl" href="/materialablage/katalog/meldungen">Produktmeldungen<span class="mat-meldezahl" id="kat-meldungen" hidden></span></a>` : ""}
            ${DARF.katalog ? katalogMenue : ""}</div></div>
        ${k ? `<div class="mat-katkopf">
            <div class="mat-pfad">${pfadHtml(['<a href="/materialablage/katalog" data-act="kategorie" data-id="">alle Kategorien</a>',
              ...pfad.slice(0, -1).map((x) => `<a href="/materialablage/katalog?kategorie=${x.id}" data-act="kategorie" data-id="${x.id}">${esc(x.name)}</a>`)])}</div>
            <h2>${esc(k.name)} ${demoMarke(k.demo)}</h2>
            <p class="small">${angaben}${formularZeile}</p>
            ${DARF.katalog ? `<div class="btn-row">${kategorieMenue}
              <button class="btn secondary small" data-act="kat-formular">Generisches Formular</button></div>` : ""}
            <details class="mat-katdoks mat-auf"${alsSchublade() ? "" : " open"}><summary>Dokumente für alle Produkte dieser Kategorie<span id="kat-doks-zahl"></span>${infoKnopf("Dokumente für alle Produkte dieser Kategorie", "Pflegehinweise, allgemeine Anleitungen … – sie gelten für jedes Produkt hier und in den Unterkategorien und stehen dort bei den Herstellerdokumenten.")}</summary>
              <div id="kat-doks"><p class="help">Wird geladen …</p></div>
              ${DARF.katalog ? '<button class="btn secondary small" data-act="dok-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Dokument<span class="k-anlegen"> anlegen</span></span></button>' : ""}</details></div>`
          : (kats.length ? "" : leer(DARF.katalog ? "Noch keine Kategorien – mit „Kategorie anlegen“." : "Noch keine Kategorien."))}
        ${DARF.katalog ? '<div id="kat-import-hinweis"></div>' : ""}
        <div class="mat-suchzeile"><input type="search" id="kat-q" placeholder="${katPlatzhalter()}"
          aria-label="${KAT_SUCHE}" title="${KAT_SUCHE}" value="${esc(q)}" autocomplete="off" ${TASTATUR_SUCHE}></div>
        <div id="kat-liste"></div>`;
      leisteKnopfSetzen();             // „☰ Kategorien“ in die neue Suchzeile (Telefon, Tablet hochkant)
      let los = null;
      $("#kat-q").addEventListener("input", (e) => { clearTimeout(los); los = setTimeout(() => { q = e.target.value.trim(); zeigen(liste); }, 250); });
      zeigen(() => liste(springen));
      if (k) zeigenIn(katDoks, "#kat-doks");
      if (DARF.katalog) { meldungenZaehlen($("#kat-meldungen")); importHinweis(); }
    }
    let katDocs = [];
    async function katDoks() {
      katDocs = (await api(`${API}/kategorien/${kategorie}/dokumente`)).dokumente;
      const ziel = $("#kat-doks");
      if (ziel) ziel.innerHTML = katDocs.length ? dokTabelle(katDocs, DARF.katalog) : leer("Noch keine Dokumente an dieser Kategorie.");
      const zahl = $("#kat-doks-zahl");
      if (zahl) zahl.textContent = ` (${katDocs.length})`;          // auch zugeklappt sieht man, ob es welche gibt
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
        try { await api(`${API}/kategorien/${k.id}`, { method: "DELETE" }); location.href = "/materialablage/katalog"; } catch (e) { toast(e.message, true); }
      },
      "kat-formular": () => formularFuer({ kategorie_id: kategorie }),
      "produkt-neu": () => produktDialog({ category_id: kategorie }),
      "kat-export": () => katalogExportDialog(),
      "kat-import": () => katalogImportDialog(),
      "kat-import-stand": (b) => katalogImportDialog(b.dataset.id),
      "kat-import-aus": (b) => {
        try { localStorage.setItem(IMPORT_AUSGEBLENDET, b.dataset.id); } catch (e) { /* privat: dann eben nicht */ }
        const ziel = $("#kat-import-hinweis");
        if (ziel) ziel.innerHTML = "";
      },
      ...dokAktionen(() => katDocs, () => `${API}/kategorien/${kategorie}/dokumente`, () => zeigenIn(katDoks, "#kat-doks")),
    };
    // springen: aus der Schublade gewählt – danach steht die Liste oben (liste).
    katalogWahl = (id, springen) => {
      kategorie = id;
      history.replaceState(null, "", kategorie ? `?kategorie=${kategorie}` : location.pathname);
      zeichnen(springen);
    };
    zeichnen();
  }

  /* --- Katalogaustausch (Lieferung 4): Export als ZIP, Import mit Probelauf ----------------------------------
     Export: Der Dialog zeigt erst, was mitkommt und was nicht (DEMO, fehlende Dateien), dann lädt der Knopf das ZIP.
     Import: Datei wählen → Probelauf (der Server schreibt nichts in den Katalog) → Bericht → „Übernehmen“ führt
     denselben Import echt aus und zeigt dessen Bericht – seit dem 24.10.2026 im Hintergrund (katalogImportDialog).
     Gelöscht wird beim Import nie etwas. */
  const AUSTAUSCH_ARTEN = [["kategorien", "Kategorien"], ["produkte", "Produkte"], ["formulare", "Formulare"],
                           ["bilder", "Bilder"], ["dokumente", "Dokumente"]];
  /* Fundstellen des Katalogimports lesbar (Browserprüfung vor dem Merge, Verbesserung 7): Der Server nennt sie wie in der
     Datei („produkte[0] (Name): „Materialart“ fehlt.“, gezählt ab 0) – hier „Produkt 1 „Name“: „Materialart“ fehlt.“.
     Der Bericht selbst bleibt, wie er ist (Werkzeuge der Katalogpflege lesen ihn). */
  const FUNDSTELLE = { kategorien: "Kategorie", unterkategorien: "Unterkategorie", produkte: "Produkt", dokumente: "Dokument",
                       formulare: "Formular" };
  function fundstelleLesbar(z) {
    const m = /^((?:kategorien|produkte|formulare)\[\d+\](?:\.(?:unterkategorien|dokumente)\[\d+\]|\.bild)*)(?: \((.*?)\))?: /.exec(z);
    if (!m) return z;
    const ort = m[1].split(".").map((t) => {
      const teil = /^(\w+)\[(\d+)\]$/.exec(t);
      return teil ? `${FUNDSTELLE[teil[1]]} ${Number(teil[2]) + 1}` : "Bild";
    }).join(" › ");
    return `${ort}${m[2] ? ` „${m[2]}“` : ""}: ${z.slice(m[0].length)}`;
  }
  /* Eine Liste des Importberichts. Fehler gleichen Wortlauts an vielen Stellen (etwa 18 Produkte ohne Materialart) stehen
     als eine Zeile mit ihren Fundstellen darunter. */
  const austauschListe = (titel, zeilen, art) => {
    if (!zeilen || !zeilen.length) return "";
    const gruppen = new Map();
    zeilen.map(fundstelleLesbar).forEach((z) => {
      const i = z.indexOf(": ");
      const satz = i > 0 ? z.slice(i + 2) : z;
      if (!gruppen.has(satz)) gruppen.set(satz, []);
      gruppen.get(satz).push(i > 0 ? z.slice(0, i) : "");
    });
    const li = [...gruppen].map(([satz, orte]) => (orte.length >= 3 && orte.every(Boolean)
      ? `<li>${esc(satz)} <span class="muted">(${orte.length}×)</span><ul>${orte.map((o) => `<li>${esc(o)}</li>`).join("")}</ul></li>`
      : orte.map((o) => `<li>${esc(o ? `${o}: ${satz}` : satz)}</li>`).join("")));
    return `<div class="mat-austausch-liste ${art || ""}"><strong>${esc(titel)}</strong><ul>${li.join("")}</ul></div>`;
  };

  async function katalogExportDialog() {
    let v;
    try { v = (await api(`${API}/katalog/export/vorschau`)).export; } catch (e) { toast(e.message, true); return; }
    const e = v.enthalten, a = v.ausgelassen;
    const zeile = (t, n, raus) => `<tr><th scope="row">${t}</th><td>${n}</td><td>${raus === null ? "–" : raus}</td></tr>`;
    dialog(`<h2>Katalog exportieren</h2>
      <p>Kategorien, Produkte mit Bild und Dokumenten und die Prüfformulare als ZIP – zum Sichern oder für eine
        andere Installation. Bestand, Artikel und Prüfungen kommen nie mit, DEMO-Einträge auch nicht.</p>
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
        ${v.groesse > v.grenze ? "" : `<a class="btn" id="ke-los" href="${API}/katalog/export" download data-frisch>Herunterladen</a>`}</div>`,
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
    // Bestandteil-Listen an Produkten (Schritt 25): neu (das Produkt hatte noch keine), ersetzt oder gleich geblieben.
    const bl = b.bestandteillisten || {};
    const flach = bl.neu || bl.geaendert || bl.unveraendert ? `<tr><th scope="row">Bestandteil-Listen</th><td>${bl.neu || 0}</td><td>${bl.geaendert || 0}</td><td>${bl.unveraendert || 0}</td></tr>` : "";
    return `${stand}
      ${h.quelle || h.erstellt ? `<p class="help">Export von ${esc(h.quelle || "?")}${h.erstellt ? `, erstellt ${esc(fmtZeit(h.erstellt))}.` : /…$/.test(h.quelle || "") ? "" : "."}</p>` : ""}
      <table class="mat-austausch"><thead><tr><th></th><th>neu</th><th>geändert${b.version === 2 ? infoKnopf("neu und geändert", "Eine geänderte Prüfliste wird eine neue Formularversion (zählt als neu); eine neue Dokumentversion zählt als geändert.") : ""}</th><th>unverändert</th></tr></thead>
        <tbody>${arten.map(zeile).join("")}${flach}</tbody></table>
      ${austauschListe("Fehler", b.fehler, "fehler")}
      ${austauschListe("Achtung – betrifft vorhandene Artikel", b.warnungen, "warnung")}
      ${austauschListe("Hinweis", b.hinweise, "")}
      ${b.aenderungen.length ? `<details class="mat-auf"${b.aenderungen.length <= 12 ? " open" : ""}><summary>Im Einzelnen (${b.aenderungen.length})</summary>
        <ul class="mat-austausch-aenderungen">${b.aenderungen.map((z) => `<li>${esc(z)}</li>`).join("")}</ul></details>` : ""}
      ${nichts && !b.gespeichert ? '<p class="leerzustand">Nichts zu übernehmen – der Katalog hier entspricht schon der Datei.</p>' : ""}`;
  }

  /* Katalogimport im Hintergrund (Wunsch des Nutzers, 24.10.2026): Die große Lieferung (über 1 GB) lief länger, als der
     Reverse-Proxy auf eine Antwort wartet (504). Jetzt lädt der Dialog die Datei hoch (mit Fortschritt), der Server
     antwortet sofort mit einem Auftrag, und der Dialog fragt alle 2,5 s nach Phase und Zahlen, am Ende nach dem Bericht.
     „Übernehmen“ startet den echten Lauf mit der Datei des Probelaufs – ohne neuen Upload (sie liegt eine Stunde
     bereit). Der Dialog darf zu: Der Import läuft weiter, die Katalogseite zeigt ihn als Hinweis (importHinweis). Wird
     der Dialog während des Hochladens geschlossen, bricht nur das Hochladen ab – auf dem Server ist dann nichts
     angekommen. Nachbesserung nach der Sicherheitsprüfung (24.10.2026): Vor dem Hochladen fragt der Dialog, ob schon ein
     Import läuft, und lädt dann gar nicht erst hoch. Ist die Datei ganz oben, legt der Server sie ab („Datei wird
     abgelegt …“) – wer jetzt schließt, bricht nichts mehr ab, der Probelauf startet trotzdem. */
  const IMPORT_OFFEN = new Set(["wartet", "laeuft"]);
  const IMPORT_PHASE = { pruefen: "Datei prüfen", probe: "Probedurchgang", ablegen: "Dateien ablegen",
                         schreiben: "Datenbank schreiben" };
  const tausend = (n) => Number(n || 0).toLocaleString("de-DE");
  function importStandText(a) {
    const was = a.trocken ? "Probelauf" : "Übernehmen";
    if (a.zustand === "wartet" || !a.phase) return `${was}: startet …`;
    return `${was}: ${IMPORT_PHASE[a.phase] || "läuft"}${a.m ? ` – ${tausend(a.n)} von ${tausend(a.m)}` : ""} …`;
  }
  function importBalken(n, m) {
    const max = Number(m) || 0;
    return max > 0 ? `<progress class="mat-import-balken" max="${max}" value="${Math.min(Number(n) || 0, max)}"></progress>`
      : '<progress class="mat-import-balken"></progress>';
  }
  function importHerkunft(a) {
    const teile = [`gestartet ${esc(fmtZeit(a.gestartet))}${a.von ? ` von ${person(a.von)}` : ""}`, esc(a.quelle || "")];
    if (a.beendet && !IMPORT_OFFEN.has(a.zustand)) teile.push(`beendet ${esc(fmtZeit(a.beendet))}`);
    if (a.uebernehmbar && a.datei_bis) teile.push(`Übernehmen bis ${esc(fmtZeit(a.datei_bis))}`);
    return `<p class="help mat-import-herkunft">${teile.filter(Boolean).join(" · ")}</p>`;
  }

  // Hochladen mit Fortschritt: fetch kennt keinen Upload-Fortschritt, deshalb XMLHttpRequest. Antwort 202 → Auftrag;
  // sonst ein Fehler mit status (0 = keine Verbindung, -1 = abgebrochen) und – bei 409 – dem laufenden Auftrag
  // (507: zu wenig Platz auf dem Server, die Meldung sagt es).
  function importHochladen(datei, beiFortschritt, merken, beiOben) {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append("file", datei);
      fd.append("trocken", "1");
      const xhr = new XMLHttpRequest();
      merken(xhr);
      xhr.open("POST", `${API}/katalog/import`);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.responseType = "json";
      // Ganz oben (alle Bytes gesendet) meldet beiOben – je nach Browser schon mit dem letzten Fortschritt oder erst mit
      // upload.onload; beiOben verträgt beides.
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        beiFortschritt(e.loaded, e.total);
        if (e.loaded >= e.total) beiOben();
      };
      xhr.upload.onload = () => beiOben();
      const fehler = (text, status, auftrag) => { const e = new Error(text); e.status = status; e.auftrag = auftrag; return e; };
      xhr.onload = () => {
        const d = xhr.response || {};
        if (xhr.status === 202) { resolve(d.auftrag); return; }
        if (xhr.status === 401) { location.href = "/login?next=" + encodeURIComponent(location.pathname); }
        reject(fehler(d.error || `Fehler ${xhr.status}`, xhr.status, d.auftrag));
      };
      xhr.onerror = () => reject(fehler("Keine Verbindung zum Server.", 0));
      xhr.onabort = () => reject(fehler("Hochladen abgebrochen – auf dem Server ist nichts angekommen.", -1));
      xhr.send(fd);
    });
  }

  function katalogImportDialog(kennung) {
    dialog(`<h2>Katalog importieren</h2>
      <p>Ein Katalog-Export (ZIP) oder eine Katalogdatei (JSON). Zuerst läuft ein Probelauf: Er zeigt, was neu ist und was
        sich ändert, und speichert nichts. Übernommen wird erst mit „Übernehmen“. Gelöscht wird beim Import nie etwas.
        Der Import läuft auf dem Server weiter, auch wenn du diesen Dialog schließt.</p>
      <div class="mat-ablage" id="ki-ablage">
        <p><strong>Datei hierher ziehen</strong> oder <label class="btn secondary small">Datei wählen<input type="file" id="ki-datei" class="mat-datei" accept=".zip,.json,application/zip,application/json"></label></p>
        <p class="help" id="ki-name">ZIP oder JSON, bis 2 GB.</p>
      </div>
      <div id="ki-stand" class="mat-import-stand" aria-live="polite"></div>
      <div id="ki-bericht" class="mat-austausch-bericht" aria-live="polite"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button>
        <button class="btn" id="ki-ok" type="button" hidden>Übernehmen</button></div>`,
    (dlg, body) => {
      const bericht = $("#ki-bericht", body);
      const stand = $("#ki-stand", body);
      const ok = $("#ki-ok", body);
      const ablage = $("#ki-ablage", body);
      let xhr = null;            // das laufende Hochladen
      let oben = false;          // die Datei ist ganz oben – der Server legt sie ab, Schließen bricht nichts mehr ab
      let aktuell = null;        // die Kennung, deren Stand der Dialog gerade zeigt
      let uhr = null;
      let gemeldet = false;      // „Katalog übernommen“ nur einmal
      const offen = () => dlg.open && body.contains(stand);
      const weg = new AbortController();
      dlg.addEventListener("close", () => {
        weg.abort();
        clearTimeout(uhr);
        aktuell = null;
        if (xhr && oben) toast("Die Datei ist hochgeladen – der Probelauf startet auf dem Server. Sein Stand steht oben auf der Katalogseite.");
        else if (xhr) { xhr.abort(); toast("Hochladen abgebrochen – es wurde nichts importiert.", true); }
        importHinweis();
      }, { once: true });

      function zeigen(a) {
        if (IMPORT_OFFEN.has(a.zustand)) {
          ablage.hidden = true;
          ok.hidden = true;
          stand.innerHTML = `<p><strong>${esc(importStandText(a))}</strong></p>${importBalken(a.n, a.m)}${importHerkunft(a)}`;
          bericht.innerHTML = "";
          return;
        }
        ablage.hidden = false;
        // Abgebrochen (Prozess weg) hat keinen Bericht, nur den Grund; sonst steht jeder Fehler im Bericht wie bisher.
        stand.innerHTML = `${a.bericht ? "" : `<p class="error">${esc(a.fehler || "Der Import ist ohne Bericht zu Ende gegangen.")}</p>`}${importHerkunft(a)}`;
        bericht.innerHTML = a.bericht ? importBerichtHtml(a.bericht) : "";
        ok.hidden = !a.uebernehmbar;
        ok.disabled = false;
        ok.textContent = "Übernehmen";
        if (!a.trocken && a.bericht && a.bericht.gespeichert && !gemeldet) {
          gemeldet = true;
          toast("Katalog übernommen");
          // Leiste und Liste zeigen den neuen Stand, sobald der Bericht gelesen und der Dialog zu ist.
          dlg.addEventListener("close", () => location.reload(), { once: true });
        }
      }

      // Den Stand eines Auftrags holen, bis er zu Ende ist. Ohne Verbindung (Neustart, Deploy) weiter versuchen.
      async function verfolgen(id, pause = 2500) {
        clearTimeout(uhr);
        aktuell = id;
        let a;
        try { a = (await api(`${API}/katalog/import/${encodeURIComponent(id)}`)).auftrag; } catch (e) {
          if (!offen() || aktuell !== id) return;
          if (e.status === 0 || e.status >= 500) {
            let p = $(".mat-import-netz", stand);
            if (!p) { p = document.createElement("p"); p.className = "help mat-import-netz"; stand.appendChild(p); }
            p.textContent = "Keine Verbindung zum Server – es wird weiter nachgefragt …";
            uhr = setTimeout(() => verfolgen(id, Math.min(pause * 2, 15000)), pause);
            return;
          }
          stand.innerHTML = `<p class="error">${esc(e.message)}</p>`;
          ablage.hidden = false;
          return;
        }
        if (!offen() || aktuell !== id) return;
        zeigen(a);
        if (IMPORT_OFFEN.has(a.zustand)) uhr = setTimeout(() => verfolgen(id), 2500);
      }

      async function probelauf(f) {
        if (!f || xhr || ablage.hidden) return;          // während des Hochladens oder eines Laufs nicht
        if (!/\.(zip|json)$/i.test(f.name)) { toast(`„${f.name}“: bitte ein Katalog-Export (ZIP) oder eine JSON-Datei.`, true); return; }
        clearTimeout(uhr);
        aktuell = null;
        ok.hidden = true;
        ablage.hidden = true;
        bericht.innerHTML = "";
        $("#ki-name", body).textContent = `${f.name} · ${groesse(f.size)}`;
        const belegt = (text, laufend) => {
          ablage.hidden = false;
          stand.innerHTML = `<p class="error">${esc(text)}</p>${laufend ? '<p><button type="button" class="lnk" id="ki-laufend">Stand des laufenden Imports ansehen</button></p>' : ""}`;
          const lnk = $("#ki-laufend", stand);
          if (lnk) lnk.onclick = () => verfolgen(laufend.id);
        };
        // Läuft schon einer, gar nicht erst hochladen – bei über 1 GB wären das sonst Minuten für eine 409.
        stand.innerHTML = "<p><strong>Prüfen, ob gerade ein Import läuft …</strong></p>";
        let laufend = null;
        try { laufend = (await api(`${API}/katalog/import/aktuell`)).auftrag; } catch (e) { /* dann entscheidet der Server (409) */ }
        if (!offen()) return;
        if (laufend && IMPORT_OFFEN.has(laufend.zustand)) {
          belegt(`Es läuft schon ein Katalogimport${laufend.von ? ` von ${laufend.von}` : ""}. Es kann immer nur einer laufen – bitte warten, bis er fertig ist.`, laufend);
          return;
        }
        stand.innerHTML = `<p><strong id="ki-was">Hochladen …</strong></p>${importBalken(0, 100)}<p class="help" id="ki-hoch">${esc(f.name)} · ${esc(groesse(f.size))}</p>`;
        let a;
        oben = false;
        try {
          a = await importHochladen(f, (n, m) => {
            const balken = $(".mat-import-balken", stand);
            if (balken && !oben) { balken.max = m; balken.value = n; }
            const t = $("#ki-hoch", stand);
            if (t && !oben) t.textContent = `${Math.floor((n / m) * 100)} % · ${groesse(n)} von ${groesse(m)}`;
          }, (x) => { xhr = x; }, () => {
            // Ganz oben: Bis zur Antwort kopiert der Server die Datei an ihren Platz – bei 1 GB einige Sekunden.
            if (oben) return;
            oben = true;
            const was = $("#ki-was", stand);
            if (was) was.textContent = "Datei wird abgelegt …";
            const balken = $(".mat-import-balken", stand);
            if (balken) balken.removeAttribute("value");
            const t = $("#ki-hoch", stand);
            if (t) t.textContent = `${f.name} · ${groesse(f.size)} hochgeladen`;
          });
        } catch (e) {
          xhr = null;
          if (!offen()) { if (oben) toast(e.message, true); return; }
          belegt(e.message, e.auftrag);
          return;
        }
        xhr = null;
        if (!offen()) { importHinweis(); return; }
        zeigen(a);
        verfolgen(a.id);
      }
      $("#ki-datei", body).addEventListener("change", (ev) => { probelauf(ev.target.files[0]); ev.target.value = ""; });
      // Abgelegt wird überall im Dialog – nie soll der Browser die Datei stattdessen selbst öffnen. #dlg-body bleibt
      // über alle Dialoge bestehen: Die Handler gelten nur, solange dieser Dialog offen ist.
      body.addEventListener("dragover", (ev) => { ev.preventDefault(); if (!ablage.hidden) ablage.classList.add("ueber"); }, { signal: weg.signal });
      body.addEventListener("dragleave", (ev) => { if (!body.contains(ev.relatedTarget)) ablage.classList.remove("ueber"); }, { signal: weg.signal });
      body.addEventListener("drop", (ev) => {
        ev.preventDefault();
        ablage.classList.remove("ueber");
        if (!ablage.hidden && ev.dataTransfer && ev.dataTransfer.files.length) probelauf(ev.dataTransfer.files[0]);
      }, { signal: weg.signal });
      ok.onclick = async () => {
        if (!aktuell || ok.disabled) return;
        ok.disabled = true;
        ok.textContent = "Wird gestartet …";
        try {
          const a = (await api(`${API}/katalog/import/${encodeURIComponent(aktuell)}/uebernehmen`, { method: "POST" })).auftrag;
          if (!offen()) return;
          zeigen(a);
          verfolgen(a.id);
        } catch (e) {
          toast(e.message, true);
          ok.disabled = false;
          ok.textContent = "Übernehmen";
        }
      };
      if (kennung) verfolgen(kennung);
    });
  }

  /* Hinweis oben auf der Katalogseite: ein laufender Import (mit Phase und Zahlen, alle 5 s neu) oder einer, der vor
     höchstens einem Tag zu Ende ging – mit „Stand ansehen“ bzw. „Bericht ansehen“ (öffnet den Dialog mit diesem
     Auftrag). Einen beendeten blendet „Ausblenden“ in diesem Browser aus. */
  const IMPORT_AUSGEBLENDET = "mat-katalogimport-ausgeblendet";
  let importHinweisUhr = null;
  async function importHinweis() {
    clearTimeout(importHinweisUhr);
    if (!$("#kat-import-hinweis")) return;
    let a;
    try { a = (await api(`${API}/katalog/import/aktuell`)).auftrag; } catch (e) { return; }
    const ziel = $("#kat-import-hinweis");      // die Seite kann inzwischen neu gezeichnet sein
    if (!ziel) return;
    let aus = "";
    try { aus = localStorage.getItem(IMPORT_AUSGEBLENDET) || ""; } catch (e) { /* privat: dann eben nicht */ }
    if (!a || (!IMPORT_OFFEN.has(a.zustand) && aus === a.id)) { ziel.innerHTML = ""; return; }
    let text;
    if (IMPORT_OFFEN.has(a.zustand)) text = `Katalogimport läuft – ${importStandText(a)}`;
    else if (a.zustand === "fertig") {
      text = a.trocken ? (a.uebernehmbar ? "Probelauf fertig – noch nicht übernommen." : "Probelauf fertig.")
        : "Katalogimport übernommen.";
    } else if (a.zustand === "abgebrochen") {
      text = `${a.trocken ? "Probelauf" : "Katalogimport"} abgebrochen${a.uebernehmbar ? " – Übernehmen geht noch einmal." : "."}`;
    } else if (a.fehler) text = `${a.trocken ? "Probelauf" : "Katalogimport"} mit Fehler beendet.`;
    else text = `${a.trocken ? "Probelauf" : "Katalogimport"} mit Fehlern beendet – nichts gespeichert.`;
    const laeuft = IMPORT_OFFEN.has(a.zustand);
    ziel.innerHTML = `<div class="mat-importhinweis${laeuft ? " laeuft" : a.zustand === "fertig" ? "" : " bad"}" role="status">
      <p><strong>${esc(text)}</strong> <span class="help">${a.von ? `${esc(a.von)} · ` : ""}${esc(a.quelle || "")} · ${esc(fmtZeit(laeuft ? a.gestartet : a.beendet))}</span></p>
      <p><button type="button" class="lnk" data-act="kat-import-stand" data-id="${esc(a.id)}">${laeuft || a.zustand === "abgebrochen" ? "Stand ansehen" : "Bericht ansehen"}</button>${laeuft ? "" : ` · <button type="button" class="lnk" data-act="kat-import-aus" data-id="${esc(a.id)}">Ausblenden</button>`}</p></div>`;
    if (laeuft) importHinweisUhr = setTimeout(importHinweis, 5000);
  }

  async function formularFuer(ziel) {
    // Das aktive (oder neueste) Formular des Ziels öffnen – oder ein neues anlegen.
    const q = ziel.kategorie_id ? `kategorie=${ziel.kategorie_id}` : `produkt=${ziel.produkt_id}`;
    try {
      const liste = (await api(`${API}/formulare?${q}`)).formulare;
      const f = liste.find((x) => x.aktiv) || liste[0];
      if (f) { location.href = `/materialablage/katalog/formular/${f.id}`; return; }
      const r = await api(`${API}/formulare`, { method: "POST", body: ziel });
      location.href = `/materialablage/katalog/formular/${r.formular.id}`;
    } catch (e) { toast(e.message, true); }
  }

  async function kategorieDialog(k) {
    const kats = await kategorienLaden();
    const neu = !k.id;
    // „Artikel haben eine Länge“ wirkt auf Unterkategorien: Setzt es schon eine Oberkategorie, sagt der Dialog das.
    const oben = kats.find((x) => x.id === k.parent_id);
    const geerbt = !!(oben && oben.laenge_wirksam);
    dialog(`<h2>${neu ? "Kategorie anlegen" : "Kategorie bearbeiten"}</h2>
      <label for="kd-name">Name</label><input type="text" id="kd-name" value="${esc(k.name || "")}" maxlength="120">
      <label for="kd-parent">Oberkategorie</label><select id="kd-parent"><option value="">– oberste Ebene –</option>${kategorieOptionen(kats, k.parent_id, k.id)}</select>
      <label for="kd-norm">Norm</label><input type="text" id="kd-norm" value="${esc(k.norm || "")}" maxlength="200" placeholder="z. B. EN 361" ${TASTATUR_NUMMER}>
      <div class="field-row"><div><label for="kd-art">Materialart (Vorgabe für Produkte)</label><select id="kd-art"><option value="">–</option>
          ${Object.entries(MATERIALART).map(([w, t]) => `<option value="${w}" ${k.default_material_kind === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
        <div><label for="kd-int">Prüfintervall (Monate, Vorgabe)</label><input type="number" id="kd-int" min="1" max="120" value="${k.default_interval_months || ""}"></div></div>
      <label for="kd-ld">Lebensdauer (Jahre, Vorschlag – nur textil)${infoKnopf("Lebensdauer", "Nur ein Vorschlag beim Anlegen eines Produkts: Die Lebensdauer steht am Produkt, aus der Anleitung des Herstellers.")}</label><input type="number" id="kd-ld" min="1" max="50" value="${k.default_lifetime_years || ""}">
      <label class="inline mat-kd-laenge"><input type="checkbox" id="kd-laenge" ${k.items_have_length ? "checked" : ""}> Artikel haben eine Länge${infoKnopf("Artikel haben eine Länge", "Seile und Meterware: Artikel dieser Kategorie und aller Unterkategorien bekommen ein Feld „Länge (m)“; ein Prüfpunkt „Länge“ fragt sie bei der Prüfung ab.")}</label>
      ${geerbt ? '<div class="help">Hier schon durch eine Oberkategorie gesetzt.</div>' : ""}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="kd-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`,
    (dlg, body) => {
      const art = $("#kd-art", body), ld = $("#kd-ld", body);
      const pruefen = () => { ld.disabled = art.value !== "textil"; if (ld.disabled) ld.value = ""; };
      art.addEventListener("change", pruefen); pruefen();
      fokus($("#kd-name", body));
      $("#kd-ok", body).onclick = async () => {
        const daten = { name: $("#kd-name", body).value, parent_id: $("#kd-parent", body).value ? +$("#kd-parent", body).value : null,
                        norm: $("#kd-norm", body).value, default_material_kind: art.value || null,
                        default_interval_months: $("#kd-int", body).value || null, default_lifetime_years: ld.value || null,
                        items_have_length: $("#kd-laenge", body).checked };
        try {
          const r = neu ? await api(`${API}/kategorien`, { method: "POST", body: daten }) : await api(`${API}/kategorien/${k.id}`, { method: "PUT", body: daten });
          dlg.close(); location.href = `/materialablage/katalog?kategorie=${r.kategorie.id}`;
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  // Eine Artikelnummer gibt es je Hersteller nur einmal (seit dem 22.10.2026 nicht mehr katalogweit – P53 ist bei
  // Petzl und bei Rock Exotica je ein anderes Produkt). Schon beim Tippen sagen, wem sie bei diesem Hersteller gehört –
  // der Server prüft beim Speichern ohnehin. herstellerFeld: das Herstellerfeld desselben Formulars (ein anderer
  // Hersteller dort nimmt den Hinweis weg); ausser: das Produkt, das gerade bearbeitet wird.
  function artikelnummerPruefen(feld, herstellerFeld, hilfe, ausser) {
    let los = null;
    const pruefen = async () => {
      const nr = feld.value.trim(), hersteller = herstellerFeld.value.trim();
      if (!nr) { hilfe.innerHTML = ""; return; }
      try {
        const p = (await api(`${API}/produkte/artikelnummer?${new URLSearchParams({ nr, hersteller, ausser: ausser || "" })}`)).produkt;
        if (feld.value.trim() !== nr || herstellerFeld.value.trim() !== hersteller) return;   // inzwischen weitergetippt
        // Der Name im Link, der Zusatz grau dahinter – wie überall im Modul, auch in dieser Warnzeile.
        hilfe.innerHTML = p ? `<span class="mat-warn">Schon vergeben: <a href="/materialablage/katalog/produkt/${p.id}" target="_blank" rel="noopener">${nameHtml(p)}</a>${zusatzHtml(p)}${p.article_no ? ` <span class="mat-ganz">(${esc(p.article_no)})</span>` : ""}</span>` : "";
      } catch (e) { hilfe.innerHTML = ""; }
    };
    const spaeter = () => { clearTimeout(los); los = setTimeout(pruefen, 300); };
    feld.addEventListener("input", spaeter);
    herstellerFeld.addEventListener("input", spaeter);
    if (feld.value.trim()) pruefen();
  }

  /* opt.danach (Phase 2 · L3, „Im Katalog anlegen“ aus der Nacharbeit): Nach dem Anlegen bleibt die Seite stehen und
     danach(produkt) ordnet das neue Produkt zu – sonst geht es wie bisher zur Produktseite. */
  async function produktDialog(p, opt) {
    opt = opt || {};
    const kats = await kategorienLaden();
    const neu = !p.id;
    const kat = (id) => kats.find((k) => k.id === +id) || {};
    // Als Variante: die aktuellen Dokumente des Vorbilds (neueste Version, nicht zurückgezogen) zur Auswahl.
    const vorbildDoks = p.variante_von ? p.variante_von.dokumente.filter((d) => !d.abgeloest_durch && (!d.withdrawn_on || d.withdrawn_on > isoHeute(0))) : [];
    /* Beschreibung (sichtbar „Bemerkung“): ein Feld wie die anderen – halb breit, der Hilfetext daneben –, eine Zeile,
       höchstens BESCHREIBUNG_MAX Zeichen (der Server prüft beim Speichern, katalog.beschreibung). Eine ältere, längere
       wird nie still gekürzt: Das Feld zeigt sie ganz (in einer Zeile – ein Textfeld verschluckte Zeilenumbrüche sonst
       ohne Leerzeichen), darunter der Hinweis mit dem bisherigen Text; gespeichert wird erst, wenn sie kürzer ist. */
    const beschreibung = String(p.description || "").replace(/\s+/g, " ").trim();
    const zuLang = beschreibung.length > BESCHREIBUNG_MAX;
    /* Zwei Reiter: „Produkt“ (die Felder) und „Bestandteile“ (die Bestandteil-Liste, Schritt 25 – nur Bezeichnung und
       Anzahl, stuecklisteEditor; leer erlaubt). Beim Wechsel geht nichts verloren. Neu angelegt (auch als Variante und
       aus einer Meldung) geht die Liste in derselben Anfrage mit – scheitert eine Position, entsteht nichts und die
       Position ist markiert; beim Bearbeiten erst das Produkt, dann die Liste als Ganzes (PUT …/bestandteile), wenn sie
       sich geändert hat. Nicht in der Nacharbeit (opt.danach). */
    const mitReiter = !opt.danach;
    const formular = `${p.variante_von ? `<p class="help">Die Stammdaten sind übernommen – bitte die neue Artikelnummer eintragen und anpassen, was sich unterscheidet.${(p.bestandteile || []).length ? " Die Bestandteile stehen im Reiter „Bestandteile“." : ""}</p>` : ""}
      ${p.meldung ? meldeKasten(p.meldung) : ""}
      <label for="pd-kat">Kategorie</label><select id="pd-kat"><option value="">– bitte wählen –</option>${kategorieOptionen(kats, p.category_id)}</select>
      <div class="field-row"><div><label for="pd-her">Hersteller</label><input type="text" id="pd-her" value="${esc(p.manufacturer || "")}" maxlength="120" ${TASTATUR_NAME}></div>
        <div><label for="pd-mod">Modell</label><input type="text" id="pd-mod" value="${esc(p.model || "")}" maxlength="160" ${TASTATUR_NAME}></div></div>
      <div class="field-row mat-feld-hilfe"><div><label for="pd-desc">Bemerkung</label><input type="text" id="pd-desc" value="${esc(beschreibung)}" maxlength="${BESCHREIBUNG_MAX}" ${TASTATUR_NAME} aria-describedby="pd-desc-hilfe${zuLang ? " pd-desc-alt" : ""}"></div>
        <div class="help" id="pd-desc-hilfe">Kurzer Zusatz hinter dem Namen, z. B. die Verschlussart.</div></div>
      ${zuLang ? `<div class="notice mat-beschr-alt" id="pd-desc-alt"><p><strong>Bitte kürzen:</strong> Die bisherige Bemerkung hat ${beschreibung.length} Zeichen, hinter den Namen passen höchstens ${BESCHREIBUNG_MAX}. Gespeichert wird erst, wenn sie kürzer ist – Ausführliches gehört in ein Dokument am Produkt. Bisher:</p>
        <p class="mat-text">${esc(p.description)}</p></div>` : ""}
      <div class="field-row"><div><label for="pd-art">Artikelnummer des Herstellers</label><input type="text" id="pd-art" value="${esc(p.article_no || "")}" maxlength="80" ${TASTATUR_NUMMER}><div class="help" id="pd-art-hilfe"></div></div>
        <div><label for="pd-norm">Norm</label><input type="text" id="pd-norm" value="${esc(p.norm || "")}" maxlength="200" ${TASTATUR_NUMMER}></div></div>
      <div class="field-row"><div><label for="pd-mk">Materialart</label><select id="pd-mk">${Object.entries(MATERIALART).map(([w, t]) => `<option value="${w}" ${p.material_kind === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
        <div><label for="pd-int">Prüfintervall (Monate)</label><input type="number" id="pd-int" min="1" max="120" value="${p.interval_months || ""}"><div class="help" id="pd-int-hilfe"></div></div></div>
      <div class="field-row"><div><label for="pd-ld">Lebensdauer (Jahre)</label><input type="number" id="pd-ld" min="1" max="50" value="${p.lifetime_years || ""}"><div class="help" id="pd-ld-hilfe"></div></div>
        <div><label for="pd-lq">Fundstelle der Lebensdauer</label><input type="text" id="pd-lq" value="${esc(p.lifetime_source || "")}" maxlength="300" placeholder="z. B. Gebrauchsanleitung, Kap. 9"></div></div>
      ${fotoFeld("pd-bild", "Produktbild", "Bild", p.bild ? p.vorschau || p.bild : "", "JPEG, PNG, WebP oder HEIC vom Telefon.")}
      ${p.variante_von ? `<fieldset class="mat-variante-doks"><legend>Dokumente übernehmen</legend>
        ${vorbildDoks.length ? vorbildDoks.map((d) => `<label class="inline"><input type="checkbox" class="pd-dok" value="${d.id}" checked> ${esc(d.title)}
          <span class="muted small">${esc(DOKART[d.kind] || d.kind)}${d.version ? `, ${esc(d.version)}` : ""}${d.datei ? "" : " · Link"}</span></label>`).join("") : '<p class="help">Das Produkt hat keine aktuellen Dokumente.</p>'}
        <p class="help">Das Produktbild wird nie übernommen. Dokumente der Kategorie gelten ohnehin für alle Produkte darin.</p></fieldset>` : ""}
      ${p.meldung ? '<label for="pd-antwort">Anmerkung für den Melder (optional, steht in seiner Mail)</label><textarea id="pd-antwort" rows="2" maxlength="1000"></textarea>' : ""}`;
    const titel = p.variante_von ? `Variante von „${esc(produktName(p.variante_von))}“`
      : p.meldung ? "Produkt aus Meldung anlegen" : neu ? "Produkt anlegen" : "Produkt bearbeiten";
    dialog(mitReiter ? `<h2 id="pd-titel">${titel}</h2>
      <div class="c-tabs reiter-linie mat-reiter" role="tablist" aria-labelledby="pd-titel">
        <button type="button" role="tab" id="pd-reiter-produkt" aria-controls="pd-teil-produkt" data-reiter="produkt">Produkt</button>
        <button type="button" role="tab" id="pd-reiter-bestandteile" aria-controls="pd-teil-bestandteile" data-reiter="bestandteile">Bestandteile</button></div>
      <div class="mat-reiter-teil" role="tabpanel" id="pd-teil-produkt" aria-labelledby="pd-reiter-produkt">${formular}</div>
      <div class="mat-reiter-teil" role="tabpanel" id="pd-teil-bestandteile" aria-labelledby="pd-reiter-bestandteile" hidden></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="pd-ok" type="button">${neu ? "Anlegen" : "Speichern"}</button></div>`
      : `<h2>${titel}</h2>${formular}
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
      artikelnummerPruefen($("#pd-art", body), $("#pd-her", body), $("#pd-art-hilfe", body), p.id);
      const bildWahl = fotoFeldVerdrahten(dlg, body, "pd-bild");
      // Die Bestandteil-Liste und die Reiter (Start „Produkt“, „Bestandteile bearbeiten“ öffnet „Bestandteile“); die
      // Variante übernimmt die Liste des Vorbilds zum Bearbeiten.
      const stueck = mitReiter ? stuecklisteEditor($("#pd-teil-bestandteile", body), p) : null;
      const reiterZeigen = mitReiter ? reiterSchalten(body, opt.reiter === "bestandteile" ? "bestandteile" : "produkt") : null;
      // Erst die Angaben (ein neues Produkt samt Bestandteil-Liste), dann das Bild. Scheitert nur das Bild, kennt der
      // Dialog das Produkt schon: Ein zweiter Klick speichert die Angaben erneut und lädt das Bild nach, statt das Produkt
      // doppelt anzulegen. Beim Bearbeiten geht die Liste nach dem Produkt an den Server; scheitert sie, bleibt der Dialog
      // im Reiter „Bestandteile“.
      let pid = p.id || null;
      $("#pd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const daten = { category_id: katSel.value ? +katSel.value : null, manufacturer: $("#pd-her", body).value, model: $("#pd-mod", body).value,
                        article_no: $("#pd-art", body).value, norm: $("#pd-norm", body).value, material_kind: mk.value,
                        interval_months: $("#pd-int", body).value || null, lifetime_years: ld.value || null,
                        lifetime_source: $("#pd-lq", body).value, description: $("#pd-desc", body).value };
        const bild = bildWahl.datei;
        if (p.variante_von && !pid && !daten.article_no.trim()) { toast("Eine Variante braucht eine eigene Artikelnummer.", true); fokus($("#pd-art", body)); return; }
        const laenge = daten.description.replace(/\s+/g, " ").trim().length;
        if (laenge > BESCHREIBUNG_MAX) { toast(`Die Bemerkung ist ein kurzer Zusatz hinter dem Namen – höchstens ${BESCHREIBUNG_MAX} Zeichen, hier sind es ${laenge}. Bitte kürzen.`, true); fokus($("#pd-desc", body)); return; }
        if (mitReiter) {
          const fehler = stueck.pruefen();
          if (fehler) { reiterZeigen("bestandteile"); toast(fehler, true); return; }
          // Neu (auch Variante und aus Meldung): Produkt und Bestandteil-Liste in einer Anfrage – die Liste nur, wenn sie
          // nicht leer ist (eine Variante schickt sie immer: leer heißt dort „ohne Liste“).
          if (!pid && (stueck.liste().length || p.variante_von)) daten.bestandteile = stueck.liste();
        }
        knopf.disabled = true;
        try {
          // Aus einer Meldung: Produkt anlegen und Meldung erledigen in einem Zug (der Melder bekommt Bescheid).
          let r;
          try {
            r = pid ? await api(`${API}/produkte/${pid}`, { method: "PUT", body: daten })
              : p.meldung ? await api(`${API}/meldungen/${p.meldung.id}/produkt`, { method: "POST", body: Object.assign(daten, { antwort: $("#pd-antwort", body).value }) })
              : p.variante_von ? await api(`${API}/produkte/${p.variante_von.id}/variante`, { method: "POST", body: Object.assign(daten, { dokumente: $$(".pd-dok:checked", body).map((c) => +c.value) }) })
              : await api(`${API}/produkte`, { method: "POST", body: daten });
          } catch (e) {
            // „Position n: …“ beim Anlegen: an die Position, in den Reiter „Bestandteile“.
            if (mitReiter && !pid && /^Position \d+: |Positionen je Liste/.test(e.message)) { stueck.fehlerZeigen(e.message); reiterZeigen("bestandteile"); }
            throw e;
          }
          pid = r.produkt.id;
          if (mitReiter && p.id && stueck.geaendert()) {
            try { r = await api(`${API}/produkte/${pid}/bestandteile`, { method: "PUT", body: { bestandteile: stueck.liste() } }); }
            catch (e) { stueck.fehlerZeigen(e.message); reiterZeigen("bestandteile"); throw e; }
          }
          if (mitReiter) stueck.gespeichert();
          if (bild) {
            const fd = new FormData();
            fd.append("file", bild);
            await api(`${API}/produkte/${pid}/bild`, { method: "POST", body: fd });
          } else if (bildWahl.entfernen) {
            await api(`${API}/produkte/${pid}/bild`, { method: "DELETE" });
          }
          dlg.close();
          if (opt.danach) await opt.danach(r.produkt);
          else location.href = `/materialablage/katalog/produkt/${pid}`;
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* Reiter in einem Dialog (role tablist/tab/tabpanel wie „Ordner bearbeiten“; ← und → wechseln, Pos1 und Ende
     springen). Die Teile tragen aria-labelledby auf ihren Reiter. Liefert zeigen(name, fokusReiter). */
  function reiterSchalten(body, start) {
    const reiter = $$('[role="tab"]', body);
    let aktiv = null;
    function zeigen(name, fokusReiter) {
      aktiv = name;
      reiter.forEach((t) => {
        const an = t.dataset.reiter === name;
        t.setAttribute("aria-selected", String(an));
        t.tabIndex = an ? 0 : -1;
        t.classList.toggle("sel", an);
        if (an && fokusReiter) t.focus();
        const teil = $(`#${t.getAttribute("aria-controls")}`, body);
        if (teil) teil.hidden = !an;
      });
    }
    reiter.forEach((t) => t.addEventListener("click", () => zeigen(t.dataset.reiter)));
    $('[role="tablist"]', body).addEventListener("keydown", (e) => {
      const i = reiter.findIndex((t) => t.dataset.reiter === aktiv);
      const ziel = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: reiter.length - 1 }[e.key];
      if (ziel === undefined) return;
      e.preventDefault();
      zeigen(reiter[(ziel + reiter.length) % reiter.length].dataset.reiter, true);
    });
    zeigen(start);
    return zeigen;
  }

  /* Der Reiter „Bestandteile“ (Schritt 25): die Bestandteil-Liste eines Produkts, Position für Position – nur
     Bezeichnung und Anzahl; leer erlaubt, gleiche Bezeichnung nur einmal. Reihenfolge = Position (↑ ↓), „Entfernen“
     nimmt sie heraus. Grenzen aus stueckliste_grenzen (an einem neuen Produkt gibt es die Antwort noch nicht – dann
     dieselben Zahlen wie in models.py). Fehler des Servers („Position n: …“) markieren die Position. Liefert liste(),
     pruefen() (Text oder ""), geaendert(), gespeichert(), fehlerZeigen(text). */
  const STUECK_GRENZEN = { positionen: 30, anzahl: 20, bezeichnung: 120 };
  const BESTANDTEILE_INFO = "Jede Prüfung fragt je Position ab, ob sie vorhanden ist; Seriennummern einzelner Stücke stehen am Artikel.";
  function stuecklisteEditor(teil, p) {
    const g = Object.assign({}, STUECK_GRENZEN, p.stueckliste_grenzen || {});
    const pos = (p.bestandteile || []).map((z) => ({ bezeichnung: z.bezeichnung, anzahl: z.anzahl }));
    const form = (x) => ({ bezeichnung: x.bezeichnung.trim(), anzahl: +x.anzahl || 1 });
    let anfang = JSON.stringify(pos.map(form));
    // Die Felder in pos übernehmen – vor jedem Neuzeichnen, damit Getipptes bleibt.
    function lesen() {
      $$(".mat-bt", teil).forEach((f) => {
        const x = pos[+f.dataset.i];
        x.bezeichnung = $(".bt-bez", f).value;
        x.anzahl = $(".bt-anzahl", f).value;
      });
    }
    function zaehler() {
      const z = $(".mat-bt-zaehler", teil);
      if (z) z.textContent = `${pos.length} von ${g.positionen} Positionen`;
      const info = $(".mat-bt-info", teil);
      if (info && !info.firstChild) info.innerHTML = infoKnopf("Positionen", BESTANDTEILE_INFO);
    }
    function zeichnen(fokusSel) {
      teil.innerHTML = `<div class="mat-bt-liste">${pos.map((x, i) => `<fieldset class="mat-bt" data-i="${i}"><legend>Position ${i + 1}</legend>
          <div class="mat-bt-kopf"><span></span>
            <div class="btn-row"><button class="btn secondary small" type="button" data-bt="hoch" data-i="${i}" aria-label="Position ${i + 1} nach oben" ${i ? "" : "disabled"}>↑</button><button class="btn secondary small" type="button" data-bt="runter" data-i="${i}" aria-label="Position ${i + 1} nach unten" ${i < pos.length - 1 ? "" : "disabled"}>↓</button><button class="btn secondary small" type="button" data-bt="weg" data-i="${i}" aria-label="Position ${i + 1} entfernen">Entfernen</button></div></div>
          <div class="field-row mat-bt-felder nur-text"><div><label for="bt-${i}-bez">Bezeichnung</label><input type="text" id="bt-${i}-bez" class="bt-bez" maxlength="${g.bezeichnung}" value="${esc(x.bezeichnung || "")}" ${TASTATUR_NAME}></div>
            <div><label for="bt-${i}-anzahl">Anzahl</label><input type="number" id="bt-${i}-anzahl" class="bt-anzahl" min="1" max="${g.anzahl}" value="${esc(String(x.anzahl || 1))}"></div></div>
          <p class="error mat-bt-fehler" hidden></p></fieldset>`).join("")}</div>
        ${pos.length ? "" : '<p class="leerzustand">Noch keine Bestandteile.</p>'}
        <div class="btn-row mat-bt-neu"><button class="btn secondary small" type="button" data-bt="neu" ${pos.length >= g.positionen ? "disabled" : ""}><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Bestandteil<span class="k-anlegen"> anlegen</span></span></button>
          <span class="help mat-bt-zaehler"></span><span class="mat-bt-info"></span></div>`;
      zaehler();
      if (fokusSel) fokus($(fokusSel, teil));
    }
    teil.addEventListener("click", (e) => {
      const b = e.target.closest("[data-bt]");
      if (!b || b.disabled) return;
      const i = +b.dataset.i;
      lesen();
      const art = b.dataset.bt;
      if (art === "neu") { pos.push({ bezeichnung: "", anzahl: 1 }); zeichnen(`#bt-${pos.length - 1}-bez`); }
      else if (art === "weg") { pos.splice(i, 1); zeichnen(); }
      else if (art === "hoch" && i > 0) { [pos[i - 1], pos[i]] = [pos[i], pos[i - 1]]; zeichnen(`[data-bt="hoch"][data-i="${i - 1}"]`); }
      else if (art === "runter" && i < pos.length - 1) { [pos[i + 1], pos[i]] = [pos[i], pos[i + 1]]; zeichnen(`[data-bt="runter"][data-i="${i + 1}"]`); }
    });
    teil.addEventListener("input", (e) => {
      const f = e.target;
      if (f.classList.contains("bt-anzahl")) { pos[+f.closest(".mat-bt").dataset.i].anzahl = f.value; zaehler(); }
    });
    zeichnen();
    function markieren(i, text) {
      const f = $(`.mat-bt[data-i="${i}"]`, teil);
      if (!f) return;
      f.classList.add("ungueltig");
      const el = $(".mat-bt-fehler", f);
      el.textContent = text;
      el.hidden = false;
      f.scrollIntoView({ block: "nearest" });
    }
    return {
      liste: () => { lesen(); return pos.map(form); },
      geaendert: () => { lesen(); return JSON.stringify(pos.map(form)) !== anfang; },
      gespeichert: () => { anfang = JSON.stringify(pos.map(form)); },
      // Was der Server sicher abwiese, gleich hier am Feld: ohne Bezeichnung, Anzahl, doppelte Bezeichnung.
      pruefen: () => {
        lesen();
        $$(".mat-bt", teil).forEach((f) => { f.classList.remove("ungueltig"); $(".mat-bt-fehler", f).hidden = true; });
        const schluessel = (b) => b.trim().replace(/\s+/g, " ").toLowerCase();
        for (let i = 0; i < pos.length; i += 1) {
          const x = pos[i];
          const n = +x.anzahl;
          const doppelt = x.bezeichnung.trim() ? pos.findIndex((y) => schluessel(y.bezeichnung) === schluessel(x.bezeichnung)) : i;
          const text = !x.bezeichnung.trim() ? "Bitte eine Bezeichnung angeben."
            : !Number.isInteger(n) || n < 1 || n > g.anzahl ? `Anzahl zwischen 1 und ${g.anzahl}.`
              : doppelt < i ? `„${x.bezeichnung.trim()}“ steht schon in Position ${doppelt + 1} – die Anzahl anpassen.` : "";
          if (text) { markieren(i, text); return `Position ${i + 1}: ${text}`; }
        }
        return "";
      },
      // „Position n: …“ vom Server an die Position, sonst nur die Meldung (der Aufrufer zeigt sie als Toast).
      fehlerZeigen: (text) => {
        const m = String(text || "").match(/^Position (\d+): (.*)$/);
        if (m) markieren(+m[1] - 1, m[2]);
      },
    };
  }

  /* --- Dokumente: am Produkt oder an einer Kategorie (gelten dann für alle Produkte darin) ------------ */
  function dokZeile(d, k) {
    return `<tr class="${d.gilt ? "" : "mat-alt"}"><td data-l="Dokument" class="mat-k-titel"><a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
        <div class="small muted">${esc(DOKART[d.kind] || d.kind)}${d.datei ? ` · ${esc(groesse(d.size))}` : " · Link"}</div></td>
      <td data-l="Version" class="mat-k-halb">${esc(d.version || "–")}</td><td data-l="Gültig ab" class="mat-k-halb">${esc(fmtTag(d.valid_from))}</td>
      <td data-l="Stand" class="mat-k-marke">${d.gilt ? '<span class="mat-status s-einsatzbereit">gilt</span>' : d.withdrawn_on ? `zurückgezogen ${esc(fmtTag(d.withdrawn_on))}` : d.abgeloest_durch ? "abgelöst" : "noch nicht gültig"}
        ${d.sha256 ? `<div class="small muted mat-hash" title="SHA-256 ${esc(d.sha256)}">${esc(d.sha256.slice(0, 12))}…</div>` : ""}</td>
      <td class="tabelle-aktionen">${k ? `<div class="btn-row"><button class="btn secondary small" data-act="dok-name" data-id="${d.id}">Umbenennen</button>${!d.abgeloest_durch && !d.withdrawn_on ? `<button class="btn secondary small" data-act="dok-version" data-id="${d.id}">Neue Version</button><button class="btn secondary small" data-act="dok-zurueck" data-id="${d.id}">Zurückziehen</button>` : ""}</div>` : ""}</td></tr>`;
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
    ${id ? `<a href="/materialablage/katalog?kategorie=${id}">${esc(name)}</a>` : esc(name)}</span></h3>`;
  const dokTabelle = (docs, k) => `<table class="list mat-tabelle mat-karten"><thead><tr><th>Dokument</th><th>Version</th><th>Gültig ab</th><th>Stand</th><th></th></tr></thead><tbody>${docs.map((d) => dokZeile(d, k)).join("")}</tbody></table>`;

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
  /* Die Bestandteil-Liste eines Produkts (Schritt 25) auf der Produktseite: „2 × Bezeichnung“ –
     nur, wenn es eine gibt (angelegt wird sie über „Bearbeiten“ → Reiter „Bestandteile“); mit Katalogrecht dazu
     „Bestandteile bearbeiten“. Auch Artikelseite und Meine PSA zeigen sie so (bestandteilZeilen). */
  // ohneText: was dasteht, wenn eine Position keine Nummer trägt (schreibgeschützter Block im Dialog „Bearbeiten“).
  const bestandteilZeilen = (liste, mitNummern, ohneText) => `<ul class="mat-bestandteile">${liste.map((z) => `<li>${z.anzahl} × ${esc(z.bezeichnung)}${mitNummern ? nummernHtml(z) || (ohneText ? ` <span class="muted small">– ${esc(ohneText)}</span>` : "") : ""}</li>`).join("")}</ul>`;
  // Seriennummern der Stück einer Position (Artikel, Meine PSA): „SN A1“ bzw. „Stück 2: A2“ – leere fallen weg.
  function nummernHtml(z) {
    const mit = (z.nummern || []).map((n, i) => [i + 1, n]).filter(([, n]) => n);
    if (!mit.length) return "";
    return ` <span class="muted small mat-teilnummern">${mit.map(([st, n]) => `${z.anzahl > 1 ? `Stück ${st}: ` : "SN "}<span class="mat-ganz">${esc(n)}</span>`).join(" · ")}</span>`;
  }
  function bestandteilListeHtml(p, k) {
    const liste = p.bestandteile || [];
    if (!liste.length) return "";
    return `<section class="section mat-bestandteil-liste"><div class="abschnittskopf"><h2>Bestandteile${infoKnopf("Bestandteile", BESTANDTEILE_INFO)}</h2>${k ? '<button class="btn secondary small" data-act="stueckliste">Bestandteile bearbeiten</button>' : ""}</div>
      ${bestandteilZeilen(liste)}</section>`;
  }

  async function produkt() {
    const p = (await api(`${API}/produkte/${DATEN.id}`)).produkt;
    leisteMarkieren(p.category_id);
    const k = DARF.katalog;
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    const formulare = p.formulare || [];
    // Die Bemerkung steht als Zusatz in der Überschrift; nur eine ältere, dort gekürzte zusätzlich ganz hier.
    const zusatz = produktZusatz(p);
    // Seltene Funktionen im Untermenü statt als weitere Knöpfe neben „Bearbeiten“ (Knopfregel; Prüfung Browser,
    // Verbesserung 4) – seit der Liste nach dem Merge auch „Löschen“ (selten und endgültig).
    const produktMenue = `<details class="mat-menue">
        <summary class="btn secondary small" aria-haspopup="true">Mehr</summary>
        <div class="mat-menue-liste">
          <a href="#" role="button" data-act="variante"><strong>Als Variante kopieren</strong>
            <span>Ein neues Produkt mit diesen Stammdaten anlegen, etwa eine andere Länge – mit eigener Artikelnummer.</span></a>
          <a href="#" role="button" data-act="rr-neu"><strong>Rückruf anlegen</strong>
            <span>Eine Rückrufaktion des Herstellers für alle Artikel dieses Produkts oder bestimmte Seriennummern.</span></a>
          ${p.loeschbar ? `<a href="#" role="button" data-act="loeschen"><strong>Löschen</strong>
            <span>Geht nur, solange es keinen Artikel dieses Produkts gibt; vorher wird nachgefragt.</span></a>` : ""}
        </div></details>`;
    seitenTitel(produktName(p));
    inhalt.innerHTML = `${p.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen.</p>' : ""}
      <div class="mat-pfad">${pfadHtml(['<a href="/materialablage/katalog">Katalog</a>', ...p.kategorie_pfad.map((x) => `<a href="/materialablage/katalog?kategorie=${x.id}">${esc(x.name)}</a>`)])}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? bildLink(p.bild, p.original, `Produktbild ${produktName(p)}`, null, `<img class="mat-produktbild" src="${esc(p.bild)}" alt="">`) : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel"><h1>${nameHtml(p)}${zusatzHtml(p)} ${demoMarke(p.demo)}</h1>
          ${DARF.verwalten ? `<div class="btn-row"><a class="btn secondary small" href="/materialablage/artikel/neu?produkt=${p.id}"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Artikel dieses Produkts<span class="k-anlegen"> anlegen</span></span></a></div>` : ""}
          ${k ? `<div class="btn-row"><button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button>${produktMenue}</div>` : ""}</div>
      </div>
      ${rueckrufAbschnitt(p)}
      <div class="mat-spalten">
        <section class="section"><h2>Stammdaten</h2><dl class="mat-daten">
          ${zeile("Artikelnummer", p.article_no ? `<span class="mat-ganz">${esc(p.article_no)}</span>` : '<span class="muted">–</span>')}
          ${zeile("Materialart", esc(MATERIALART[p.material_kind] || p.material_kind))}
          ${zeile("Norm", p.norm ? esc(p.norm) : '<span class="muted">–</span>')}
          ${zeile("Prüfintervall", p.intervall.monate ? `${p.intervall.monate} Monate <span class="muted">(${esc(p.intervall.quelle)})</span>` : '<span class="mat-warn">keins</span>')}
          ${zeile("Lebensdauer", p.lifetime_years ? `${p.lifetime_years} Jahre${p.lifetime_source ? ` <span class="muted">(${esc(p.lifetime_source)})</span>` : ""}${p.material_kind === "textil" ? "" : ' <span class="muted">– nicht festgeschrieben</span>'}` : '<span class="muted">keine</span>')}
          ${zeile("Bestand", `${plural(p.bestand, "Artikel", "Artikel")}${p.artikel_gesamt > p.bestand ? ` <span class="muted">(+${p.artikel_gesamt - p.bestand} ausgesondert)</span>` : ""}${DARF.alles ? "" : ' <span class="muted">in deinem Bereich</span>'}`)}
          ${zusatz && zusatz.voll ? zeile("Bemerkung", `<span class="mat-text">${esc(p.description)}</span>
            <div class="help">Länger als ${BESCHREIBUNG_MAX} Zeichen, in der Überschrift gekürzt – gedacht ist ein kurzer Zusatz hinter dem Namen.${k ? " Bitte unter „Bearbeiten“ kürzen." : ""}</div>`) : ""}
        </dl></section>
        <section class="section"><div class="abschnittskopf"><h2>Prüfformular${infoKnopf("Prüfformular", "Ein aktives spezifisches Formular ersetzt das generische der Kategorie.")}</h2>
          ${k ? '<button class="btn secondary small" data-act="formular">Spezifisches Formular bearbeiten</button>' : ""}</div>
          ${p.formular ? `<p>Geprüft wird nach <a href="/materialablage/katalog/formular/${p.formular.id}"><strong>${esc(p.formular.title || "Formular")}</strong> · Version ${p.formular.version}</a> <span class="muted">(${esc(p.formular.quelle)}, ${plural(p.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span>.</p>` : '<p class="mat-warn">Für dieses Produkt gilt kein aktives Prüfformular – weder ein spezifisches noch ein generisches der Kategorie.</p>'}
          ${formulare.length ? `<p class="small">Spezifische Versionen: ${formulare.map((f) => `<a href="/materialablage/katalog/formular/${f.id}">v${f.version}${f.aktiv ? " (aktiv)" : ""}</a>`).join(", ")}</p>` : ""}
        </section>
      </div>
      ${bestandteilListeHtml(p, k)}
      <section class="section"><div class="abschnittskopf"><h2>Herstellerdokumente${infoKnopf("Herstellerdokumente", `Gelten für alle Artikel dieses Produkts. Ein Protokoll verweist auf die Version, die am Prüftag galt.${p.kategorie_dokumente.length ? " Kategoriedokumente hängen an der Kategorie und gelten für alle Produkte darin." : ""}`)}</h2>
          ${k ? '<button class="btn secondary small" data-act="dok-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Dokument<span class="k-anlegen"> anlegen</span></span></button>' : ""}</div>
        ${p.dokumente.length ? dokTabelle(p.dokumente, k) : leer("Noch keine Dokumente am Produkt.")}
        ${katGruppen(p.kategorie_dokumente).map((g) => `${katKopf(g.name, g.id)}
          <ul class="mat-doks">${g.docs.map((d) => `<li><a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
            <span class="muted small">${esc(DOKART[d.kind] || d.kind)}${d.version ? `, ${esc(d.version)}` : ""}</span></li>`).join("")}</ul>`).join("")}
      </section>
      <section class="section"><h2>Journal</h2>${journalHtml(p.journal, true)}</section>`;
    aktionen = {
      bearbeiten: () => produktDialog(p),
      stueckliste: () => produktDialog(p, { reiter: "bestandteile" }),
      // Stammdaten vorbelegt, Artikelnummer leer (eine neue ist Pflicht), kein Bild.
      variante: () => produktDialog(Object.assign({}, p, { id: null, article_no: "", bild: null, vorschau: null, original: null, variante_von: p })),
      loeschen: async () => {
        if (!(await confirm(`Produkt „${produktName(p)}“ aus dem Katalog löschen?`, "Löschen"))) return;
        try { await api(`${API}/produkte/${p.id}`, { method: "DELETE" }); location.href = "/materialablage/katalog"; } catch (e) { toast(e.message, true); }
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
      <p><button type="button" class="lnk" id="dm-link"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Link beim Hersteller<span class="k-anlegen"> anlegen</span></span></button></p>
      <label for="dm-ab">Gültig ab (für alle)</label>${datumFeld("dm-ab", "", "tag")}
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
        let ab;
        try { ab = datumWert($("#dm-ab", body), "Gültig ab"); }
        catch (e) { toast(e.message, true); $("#dm-ab", body).focus(); return; }
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
        <div><label for="dd-ab">Gültig ab</label>${datumFeld("dd-ab", "", "tag")}</div></div>
      <div class="mat-feldkopf">Datei (PDF oder Bild)</div>${dateiKnopf("dd-datei", "Datei wählen", "application/pdf,image/jpeg,image/png,image/webp", false)}
      <label for="dd-url">… oder Adresse beim Hersteller</label><input type="text" id="dd-url" maxlength="500" placeholder="https://…" ${TASTATUR_ADRESSE}>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="dd-ok" type="button">Speichern</button></div>`,
    (dlg, body) => {
      dateiKnopfVerdrahten(body, "dd-datei");
      $("#dd-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const datei = $("#dd-datei", body).files[0];
        let ab;
        try { ab = datumWert($("#dd-ab", body), "Gültig ab"); }
        catch (e) { toast(e.message, true); $("#dd-ab", body).focus(); return; }
        const felder = { title: $("#dd-title", body).value, version: $("#dd-ver", body).value, valid_from: ab };
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
    const zielLink = f.ziel.art === "kategorie" ? `/materialablage/katalog?kategorie=${f.ziel.id}` : `/materialablage/katalog/produkt/${f.ziel.id}`;
    function punktZeile(p, i) {
      if (!bearbeitbar) {
        return `<tr><td data-l="Gruppe">${esc(p.gruppe || "")}</td><td data-l="Prüfpunkt">${esc(p.text)}</td><td data-l="Art">${esc(EDITOR[p.art])}</td>
          <td data-l="Soll">${esc(p.soll || "–")}</td><td>${p.pflicht ? "Pflicht" : "optional"}${p.kritisch ? ' · <strong class="mat-warn">kritisch</strong>' : ""}</td></tr>`;
      }
      return `<tr data-i="${i}"><td data-l="Gruppe"><input type="text" class="fp-gruppe" value="${esc(p.gruppe || "")}" maxlength="80"></td>
        <td data-l="Prüfpunkt"><textarea class="fp-text" rows="1" maxlength="1000" aria-label="Prüfpunkt">${esc(p.text || "")}</textarea></td>
        <td data-l="Art"><select class="fp-art">${Object.entries(EDITOR).map(([w, t]) => `<option value="${w}" ${p.art === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></td>
        <td data-l="Soll">${p.art === "yesno" ? `<select class="fp-soll"><option value="">–</option><option value="ja" ${p.soll === "ja" ? "selected" : ""}>ja</option><option value="nein" ${p.soll === "nein" ? "selected" : ""}>nein</option></select>`
          : p.art === "text" || p.art === "number" ? `<input type="text" class="fp-soll" value="${esc(p.soll || "")}" maxlength="60" placeholder="optional">`
            : p.art === "laenge" ? '<span class="muted" title="Das Soll ist die am Artikel hinterlegte Länge">Artikellänge</span>' : '<span class="muted">–</span>'}</td>
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
    /* Prüfanleitung aus dem Wiki (Phase 2 · L3): nur die Material-Verwaltung sieht die Zeile (formular.wiki kommt sonst
       null); „Ändern“ nur mit Stufe Mitglied im Wiki (wiki_aendern, Entscheidung vom 19.10.2026). Auch an benutzten
       Versionen – die Verknüpfung gehört nicht zum Prüfinhalt. */
    function wikiZeile() {
      if (!DARF.katalog) return "";
      const w = f.wiki;
      let anzeige = '<span class="muted">keine</span>';
      if (w && w.zustand === "ok") {
        anzeige = `${w.url ? `<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.titel)}</a>` : `<strong>${esc(w.titel)}</strong>`}
          ${w.reichweite ? `<span class="badge grey">${esc(REICHWEITE[w.reichweite] || w.reichweite)}</span>` : ""}`;
      } else if (w && w.zustand === "papierkorb") anzeige = "Die verknüpfte Seite liegt im Papierkorb der Strömipedia.";
      else if (w) anzeige = `Seite Nr. ${esc(w.seite)} – du darfst sie nicht lesen`;
      const warnung = w && w.zustand === "ok" ? REICHWEITE_HINWEIS[w.reichweite] : "";
      const info = `${f.benutzt && f.wiki_aendern ? "Die Verknüpfung gehört nicht zum Prüfinhalt und lässt sich auch an benutzten Versionen ändern. " : ""}${WIKI_PRUEFUNG_INFO} ${NEUE_KONTEN}`;
      return `<div class="mat-wikizeile" id="fp-wiki"><p><strong>Prüfanleitung in der Strömipedia${infoKnopf("Prüfanleitung in der Strömipedia", info)}:</strong> ${anzeige}
          ${f.wiki_aendern ? '<button type="button" class="lnk" data-act="wiki-waehlen">Ändern</button>' : ""}</p>
        ${warnung ? `<p class="small mat-warn-leise">${esc(warnung)}</p>` : ""}
        ${f.wiki_aendern ? "" : '<p class="help">Verknüpfen kann, wer in der Strömipedia mindestens Mitglied ist.</p>'}</div>`;
    }
    function zeichnen() {
      seitenTitel(f.titel || "Prüfformular");
      inhalt.innerHTML = `${f.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen.</p>' : ""}
        <div class="mat-pfad">${pfadHtml(['<a href="/materialablage/katalog">Katalog</a>', `<a href="${zielLink}">${esc(zielText)}</a>`])}</div>
        <div class="page-head"><h1>${esc(f.titel || "Prüfformular")} <span class="badge grey">Version ${f.version}</span> ${f.aktiv ? '<span class="mat-status s-einsatzbereit">aktiv</span>' : '<span class="badge grey">inaktiv</span>'} ${demoMarke(f.demo)}</h1>
          <div class="btn-row">${DARF.katalog ? `${f.aktiv ? '<button class="btn secondary small" data-act="deaktivieren">Deaktivieren</button>' : '<button class="btn secondary small" data-act="aktivieren">Aktivieren</button>'}
            <button class="btn secondary small" data-act="neue-version">Neue Version</button>${!f.aktiv && !f.benutzt ? '<button class="btn secondary small" data-act="loeschen">Löschen</button>' : ""}` : ""}</div></div>
        ${wikiZeile()}
        <p class="help">${esc(zielText)}. ${f.gueltig_ab ? `Gültig ab ${esc(fmtTag(f.gueltig_ab))}.` : "Noch nie aktiviert."}
          ${f.benutzt ? " Diese Version wurde schon für Prüfungen benutzt und bleibt unverändert – Änderungen gehen über eine neue Version." : ""}</p>
        ${bearbeitbar ? `<label for="fp-titel">Titel</label><input type="text" id="fp-titel" value="${esc(f.titel || "")}" maxlength="160">` : ""}
        <h2 class="mat-fp-punkte">Prüfpunkte${infoKnopf("Prüfpunkte", PRUEFPUNKTE_INFO)}</h2>
        <table class="list mat-tabelle mat-formtabelle" id="fp-tabelle">
          <colgroup><col style="width:13%"><col style="width:48%"><col style="width:12%"><col style="width:11%"><col style="width:16%"></colgroup><thead><tr><th>Gruppe</th><th>Prüfpunkt</th><th>Art</th><th>Soll</th><th></th></tr></thead>
          <tbody>${punkte.map(punktZeile).join("")}</tbody></table>
        ${!punkte.length ? leer("Noch keine Prüfpunkte.") : ""}
        ${bearbeitbar ? '<div class="btn-row mat-knoepfe"><button class="btn secondary" data-act="punkt-neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Prüfpunkt<span class="k-anlegen"> anlegen</span></span></button><button class="btn" data-act="speichern">Speichern</button></div>' : ""}
        <section class="section"><h2>Versionen</h2><ul class="mat-versionen">${f.versionen.map((v) => `<li>${v.id === f.id ? `<strong>Version ${v.version}</strong>` : `<a href="/materialablage/katalog/formular/${v.id}">Version ${v.version}</a>`}
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
        try { const r = await api(`${API}/formulare`, { method: "POST", body: Object.assign(ziel, { vorlage_id: f.id }) }); location.href = `/materialablage/katalog/formular/${r.formular.id}`; }
        catch (e) { toast(e.message, true); }
      },
      loeschen: async () => {
        if (!(await confirm(`Version ${f.version} löschen?`, "Löschen"))) return;
        try { await api(`${API}/formulare/${f.id}`, { method: "DELETE" }); location.href = zielLink; } catch (e) { toast(e.message, true); }
      },
      // Nur die Zeile neu – was in den Prüfpunkten getippt, aber noch nicht gespeichert ist, bleibt stehen.
      "wiki-waehlen": () => wikiWahl(f, (neu) => {
        f.wiki = neu.wiki;
        f.wiki_aendern = neu.wiki_aendern;
        const alt = $("#fp-wiki", inhalt);
        if (alt) alt.outerHTML = wikiZeile();
      }),
    };
    zeichnen();
  }

  /* --- Prüfanleitung aus dem Wiki: Seitenwahl am Formular (Phase 2 · L3, nur Material-Verwaltung mit Wiki-Stufe) ---
     Titelsuche über die Seiten, die dieses Konto im Wiki lesen darf (300 ms Ruhe; ohne Suchwort die zuletzt
     geänderten); je Treffer die Reichweite als graue Marke und, bei interner oder beschränkter Seite, wer sie nicht sieht.
     Gespeichert wird sofort (PUT …/formulare/<id>/wiki), danach zeichnet die Formularansicht ihre Zeile neu. */
  const REICHWEITE = { oeffentlich: "öffentlich", intern: "intern", beschraenkt: "beschränkt" };
  const PRUEFPUNKTE_INFO = "Bei der Prüfung ist jeder Befund mit „in Ordnung“ vorbelegt, Ja/Nein-Punkte mit ihrem Sollwert; bei Text und Zahl ist das Soll ein Hinweis für den Prüfer. "
    + "Ein kritischer Punkt mit Mangel schließt „einsatzbereit“ aus. Ein Punkt der Art „Länge (m)“ ist mit der Länge des Artikels vorbelegt; trägt der Prüfer eine andere ein, "
    + "übernimmt das Festschreiben sie in den Artikel (nur bei Kategorien mit „Artikel haben eine Länge“).";
  const WIKI_PRUEFUNG_INFO = "Hat die Seite eine Überschrift „Prüfung“, wird dieser Abschnitt in offenen Prüfungen eingeblendet, sonst nur verlinkt.";
  // Wer die Anleitung sieht, steht sichtbar und in einer Zeile; dass neue Konten keinen Zugang haben, sagt das „i“ (NEUE_KONTEN).
  const NEUE_KONTEN = "Neue Konten haben keine Stufe in der Strömipedia und sehen nur öffentliche Seiten.";
  const REICHWEITE_HINWEIS = { intern: "Prüfer ohne Zugang zur Strömipedia sehen nur, dass es eine Anleitung gibt.",
                               beschraenkt: "Nur für Freigegebene lesbar – die meisten Prüfer sehen sie nicht." };
  function wikiWahl(formular, danach) {
    const aktuell = formular.wiki ? formular.wiki.seite : null;
    dialog(`<h2>Prüfanleitung aus der Strömipedia</h2>
      <label for="ww-q">Seite suchen (Titel)${infoKnopf("Seite suchen", `${WIKI_PRUEFUNG_INFO} Jeder sieht nur, was er in der Strömipedia lesen darf. ${NEUE_KONTEN}`)}</label>
      <input type="search" id="ww-q" autocomplete="off" ${TASTATUR_SUCHE} placeholder="z. B. Karabiner">
      <p class="help" id="ww-lesemodus" hidden>Du siehst nur öffentliche Seiten.</p>
      <div class="mat-wikiwahl" id="ww-liste"></div>
      <p class="help" id="ww-stand" aria-live="polite">Wird geladen …</p>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        ${aktuell ? '<button class="btn secondary" id="ww-weg" type="button">Verknüpfung entfernen</button>' : ""}
        <button class="btn" id="ww-ok" type="button" disabled>Verknüpfen</button></div>`,
    (dlg, body) => {
      let gewaehlt = null;
      let los = null;
      let lauf = 0;
      const liste = $("#ww-liste", body);
      const stand = $("#ww-stand", body);
      const ok = $("#ww-ok", body);
      let seiten = [];
      function zeichnen() {
        liste.innerHTML = seiten.map((x, i) => `<button type="button" data-i="${i}" aria-pressed="${gewaehlt === x.id}">
          <span class="mat-wikiwahl-titel">${x.icon ? `<span aria-hidden="true">${esc(x.icon)}</span> ` : ""}${esc(x.titel)}</span>
          <span class="badge grey">${esc(REICHWEITE[x.reichweite] || x.reichweite)}</span>${x.id === aktuell ? ' <span class="small muted">verknüpft</span>' : ""}
          ${REICHWEITE_HINWEIS[x.reichweite] ? `<span class="small muted mat-wikiwahl-hinweis">${esc(REICHWEITE_HINWEIS[x.reichweite])}</span>` : ""}</button>`).join("");
      }
      async function suchen() {
        const meins = ++lauf;
        const q = $("#ww-q", body).value.trim();
        try {
          const d = await api(`${API}/wiki/seiten?${new URLSearchParams({ q })}`);
          if (meins !== lauf) return;
          seiten = d.seiten;
          $("#ww-lesemodus", body).hidden = !d.lesemodus;
          stand.textContent = !seiten.length ? (q ? "Keine Seite gefunden." : "Keine Seite, die du lesen darfst.")
            : q.length >= 2 ? plural(seiten.length, "Treffer", "Treffer") : "Zuletzt geänderte Seiten – oder oben nach dem Titel suchen.";
          zeichnen();
        } catch (e) { if (meins === lauf) { stand.textContent = e.message; seiten = []; zeichnen(); } }
      }
      $("#ww-q", body).addEventListener("input", () => { clearTimeout(los); los = setTimeout(suchen, 300); });
      liste.addEventListener("click", (ev) => {
        const b = ev.target.closest("button[data-i]");
        if (!b) return;
        gewaehlt = seiten[+b.dataset.i].id;
        ok.disabled = gewaehlt === aktuell;
        zeichnen();
        const neu = $(`button[data-i="${b.dataset.i}"]`, liste);      // neu gezeichnet – sonst stünde der Fokus auf <body>
        if (neu) neu.focus();
      });
      suchen();
      async function speichern(seite, knopf) {
        knopf.disabled = true;
        try {
          const r = await api(`${API}/formulare/${formular.id}/wiki`, { method: "PUT", body: { seite } });
          dlg.close();
          toast(seite ? "Prüfanleitung verknüpft" : "Verknüpfung entfernt");
          danach(r.formular);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      }
      ok.onclick = () => { if (gewaehlt) speichern(gewaehlt, ok); };
      const weg = $("#ww-weg", body);
      if (weg) weg.onclick = () => speichern(null, weg);
    });
  }

  /* --- Suche -------------------------------------------------------------------------------------------- */
  async function suche() {
    let seite = 1;
    let sort = { feld: null, richtung: "auf" };
    let fremde = null;            // Ergebnis der globalen Suche zu q – Blättern und Sortieren suchen nicht noch einmal
    async function zeichnen() {
      const q = DATEN.q || "";
      seitenTitel("Suche");
      if (!q) { inhalt.innerHTML = `<h1>Suche</h1>${leer("Serien-, Inventar- oder Herstellernummer oben eingeben – auch Teile davon.")}`; return; }
      const p = sortParameter(new URLSearchParams({ q, seite, pro_seite: 50 }), sort);
      const d = await api(`${API}/suche?${p}`);
      seitenTitel(`Suche „${q}“`);
      inhalt.innerHTML = `<div class="page-head"><h1>Suche „${esc(q)}“</h1></div>
        ${d.treffer.length ? artikelTabelle(d.treffer, { pfad: true, sort }) : leer("Kein Artikel in deinem Bereich gefunden.")}${seitenleiste(d.gesamt, seite, 50)}
        ${d.global_angebot ? '<div id="mat-global-angebot"></div>' : ""}`;
      // Unter der eigenen Liste das Angebot, auch außerhalb des eigenen Bereichs zu suchen (global.js – mit Rückfrage
      // und Protokoll); nach der Suche stehen dort die fremden Treffer, deutlich abgesetzt.
      if (d.global_angebot) {
        const g = await baustein("MatGlobal");
        const el = $("#mat-global-angebot");
        if (g && el) g.anbieten(el, q, { exakt: d.exakt_lokal, ergebnis: fremde, gefunden: (x) => { fremde = x; } });
      }
    }
    aktionen = {
      seite: (b) => { seite = +b.dataset.seite; zeigen(zeichnen); },
      sortieren: (b) => { sort = sortWeiter(sort, b.dataset.feld); seite = 1; zeigen(zeichnen); },
    };
    await zeichnen();
  }

  /* --- Prüfung starten ---------------------------------------------------------------------------- */
  function artikelPfad(a) {
    return `<div class="mat-pfad">${pfadHtml([...(a.pfad || []).map(pfadGlied), `<a href="/materialablage/artikel/${a.id}">${esc(a.inventory_no)}</a>`])}</div>`;
  }
  function lebensdauerHinweis(ld) {
    if (!ld) return "";
    return ld.erreicht ? `<p class="mat-banner s-lebensdauer">LEBENSENDE ERREICHT am ${esc(fmtTag(ld.ende))} – „einsatzbereit“ ist nicht mehr wählbar.</p>`
      : `<p class="notice">Textil: Lebensende ${esc(fmtTag(ld.ende))} – noch ${plural(ld.rest_tage, "Tag", "Tage")}.</p>`;
  }

  async function pruefungNeu() {
    const [antwort] = await Promise.all([api(`${API}/artikel/${DATEN.id}`), ordnerBaum().catch(() => null)]);
    const a = antwort.artikel;
    const darf = a.darf || {};
    leisteMarkieren(a.folder_id);
    if (a.entwurf && a.entwurf.pruefer_id === DARF.uid && darf.pruefen) { location.replace(`/materialablage/pruefung/${a.entwurf.id}`); return; }
    const p = a.produkt;
    const pa = a.pruefarten || { arten: [], vorschlag: null };
    let hinweis = "";                     // HTML – nur der Hinweis zum Prüferwerden enthält einen Link
    if (a.lock_state === "ausgesondert") hinweis = "Ein ausgesonderter Artikel wird nicht mehr geprüft.";
    else if (!darf.pruefen) hinweis = pruefHinweis(a);
    else if (a.entwurf) hinweis = esc(`In Prüfung bei ${a.entwurf.pruefer} seit ${fmtZeit(a.entwurf.seit)}.${darf.verwalten ? " Eine liegen gebliebene Reservierung hebst du in der Artikelansicht auf." : " Eine liegen gebliebene Reservierung hebt der Materialwart auf."}`);
    else if (!a.formular) hinweis = "Für dieses Produkt gibt es kein aktives Prüfformular – weder am Produkt noch in seiner Kategorie. Die Material-Verwaltung legt es im Katalog an.";
    const ld = a.lebensdauer && a.lebensdauer.festgeschrieben ? { ende: a.lebensdauer.ende, rest_tage: a.lebensdauer.rest_tage, erreicht: a.lebensdauer.rest_tage <= 0 } : null;
    seitenTitel(`Prüfung ${a.inventory_no}`);
    inhalt.innerHTML = `${a.demo ? `<p class="mat-demo-banner">${DEMO_ARTIKEL}</p>` : ""}
      ${artikelPfad(a)}
      <div class="page-head"><h1>Prüfung <span class="mat-inv">${esc(a.inventory_no)}</span> ${statusMarke(a.status, true)}</h1></div>
      <div class="mat-formular">
        <p class="mat-produktzeile"><strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${artNrHtml(p.article_no)} · ${nummerHtml("Seriennummer", a.serial_no)}</p>
        ${a.lock_state !== "frei" && a.lock_state !== "ausgesondert" ? `<p class="mat-banner s-gesperrt">GESPERRT${a.lock_reason ? ` – ${esc(a.lock_reason)}` : ""}. Mit „einsatzbereit“ ist diese Prüfung die Freiprüfung.</p>` : ""}
        ${mangelHinweis((a.maengel || []).filter((m) => m.offen))}
        ${rueckrufHinweis((a.rueckrufe || []).filter((r) => r.zustand !== "erledigt").map((r) => r.title), a.id)}
        ${lebensdauerHinweis(ld)}
        ${a.formular ? `<p>Formular: ${esc(a.formular.title || "ohne Titel")} · Version ${a.formular.version} <span class="muted">(${esc(a.formular.quelle)}, ${plural(a.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span></p>` : ""}
        ${a.durchgang ? `<p>Im Prüfdurchgang ${a.durchgang.sichtbar ? `<a href="/materialablage/durchgang/${a.durchgang.id}">${esc(a.durchgang.titel)}</a>` : `„${esc(a.durchgang.titel)}“`} – die Prüfung zählt dort.</p>` : ""}
        ${hinweis ? `<p class="notice">${hinweis}</p><p><a class="btn secondary" href="/materialablage/artikel/${a.id}">Zum Artikel</a></p>` : `
          <fieldset class="mat-arten"><legend>Art der Prüfung</legend>
            ${pa.arten.map((x) => `<label class="mat-art-wahl"><input type="radio" name="art" value="${x}" ${x === pa.vorschlag ? "checked" : ""}> ${esc(PRUEFART[x] || x)}${x === "eingang" && pa.arten.length === 1 ? infoKnopf("Eingangsprüfung", "Die erste Prüfung eines Artikels ist die Eingangsprüfung. Erst sie gibt ihn frei; bis dahin steht er auf „neu“.") : ""}</label>`).join("")}
          </fieldset>
          <p class="help" id="pa-folge">Mit dem Beginn reservierst du den Artikel: Andere sehen „in Prüfung bei dir“, bis du abschließt oder verwirfst. Jede Eingabe wird sofort gespeichert – du kannst jederzeit unterbrechen.</p>
          <div class="btn-row mat-knoepfe"><button class="btn" data-act="beginnen" aria-describedby="pa-folge">Prüfung beginnen</button><a class="btn secondary" href="/materialablage/artikel/${a.id}">Abbrechen</a></div>`}
      </div>`;
    aktionen = {
      beginnen: async (b) => {
        b.disabled = true;
        const wahl = $('input[name="art"]:checked');
        const body = { art: wahl ? wahl.value : null };
        if (DATEN.durchgang) body.durchgang_id = DATEN.durchgang;
        try { const r = await api(`${API}/artikel/${a.id}/pruefungen`, { method: "POST", body }); location.href = `/materialablage/pruefung/${r.pruefung.id}`; }
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

  /* --- Prüfanleitung aus dem Wiki in offenen Prüfungen (Phase 2 · Lieferung 3) ----------------------------------
     pruefung.anleitung: {titel, url, quelle} | {kein_zugang: true} | null (abgeschlossen, nichts verknüpft, Papierkorb).
     Im Kopf der Prüfung steht dann „Prüfanleitung aus der Strömipedia“ zum Aufklappen. Erst beim ersten Öffnen lädt die Seite
     marked, DOMPurify und markdown.js nach (gleiche Quelle, CSP „script-src 'self'“) und holt die Wiki-Seite über den
     Endpunkt des Wikis selbst (anleitung.quelle – mit dessen Rechten). Eingeblendet wird nur der Abschnitt „Prüfung“.
     Der Inhalt stammt aus einer Wiki-Seite, die andere ändern können als die, die verknüpft hat. Darum, in dieser Folge:
     1. gerendert wie im Wiki (MD.render, mit dessen Reinigung), 2. ein zweites Mal streng gereinigt (ANLEITUNG_REINIGUNG:
     keine ids, keine Namen, keine data-*, keine Formularelemente, keine Labels, keine Stile), 3. der Abschnitt
     ausgeschnitten (abschnittPruefung), 4. eingesetzt in einen geschlossenen Shadow-Root: document.querySelector,
     getElementById, $/$$, benannte Eigenschaften von window/document und die Klick-Delegation an #mat-inhalt reichen
     nicht hinein, die Stile der Prüfansicht nicht hinein und die des Abschnitts nicht hinaus. Dazu übergeht die
     Klick-Delegation alles in .mat-anleitung, und Festschreiben liest seine Felder nur aus dem eigenen Behälter.
     MD.enhance läuft nicht (es lüde eingebundene Seiten nach und vergäbe ids); eingebundene Bausteine stehen als
     Hinweis da, Inhaltsverzeichnis und Unterseiten-Liste entfallen, jeder Link öffnet einen neuen Tab. */
  const ANLEITUNG_REINIGUNG = {
    ADD_TAGS: ["video", "audio", "source"], ADD_ATTR: ["controls", "preload", "playsinline"],
    FORBID_TAGS: ["style", "form", "textarea", "select", "button", "dialog", "iframe", "input", "label", "output",
                  "data", "object", "embed", "base", "meta", "link"],
    FORBID_ATTR: ["style", "id", "name", "for", "form", "formaction", "target"],
    ALLOW_DATA_ATTR: false };
  const ANLEITUNG_KEIN_ZUGANG = "Zu diesem Formular gibt es eine Prüfanleitung in der Strömipedia, die du nicht lesen darfst.";
  const ANLEITUNG_OHNE_ABSCHNITT = "Die Seite hat keinen Abschnitt „Prüfung“ – bitte in der Strömipedia lesen.";
  const ANLEITUNG_ALT = "Diese Seite lässt sich hier nicht einblenden – bitte in der Strömipedia lesen.";
  const ANLEITUNG_FEHLER = "Die Anleitung ließ sich nicht laden.";
  const ANLEITUNG_EINBAU = "Eingebundener Abschnitt – nur in der Strömipedia sichtbar.";
  // Stile nur im Schatten: Bilder und Filme höchstens so breit wie der Kasten, breite Tabellen und Code rollen seitlich.
  // contain: paint – der Kasten ist Bezugsrahmen auch für position: fixed und schneidet ab: Klassen aus app.css, die im
  // Abschnitt stehen dürfen (etwa .md-lightbox, fix über dem ganzen Fenster), legen sich nicht über die Prüfansicht.
  const ANLEITUNG_STIL = `:host { display: block; contain: paint; }
    article.wiki-content { padding: 2px 2px 6px; overflow-wrap: anywhere; }
    article.wiki-content > :first-child { margin-top: 4px; }
    img, video { max-width: 100%; height: auto; }
    table { display: block; max-width: 100%; overflow-x: auto; }
    th, td { overflow-wrap: normal; min-width: 4em; }
    pre { max-width: 100%; overflow-x: auto; }
    .anleitung-einbau { color: var(--grau); font-size: var(--fs-klein); font-style: italic; }`;
  // Nur eigene Adressen („/stroemipedia/…“, „/api/…“) – was sonst käme, wird kein Link und keine Anfrage.
  const eigeneAdresse = (u) => (typeof u === "string" && /^\/(?![/\\])/.test(u) ? u : null);
  const skriptLaden = (src) => new Promise((fertig, fehler) => {
    const el = document.createElement("script");
    el.src = src;
    el.onload = () => fertig();
    el.onerror = () => fehler(new Error(`${src} ließ sich nicht laden.`));
    document.head.appendChild(el);
  });
  let markdownLauf = null;
  function markdownBereit() {
    if (window.MD && window.DOMPurify) return Promise.resolve();
    if (!markdownLauf) {
      markdownLauf = (async () => {
        if (!window.marked) await skriptLaden("/static/vendor/marked/marked.min.js");
        if (!window.DOMPurify) await skriptLaden("/static/vendor/dompurify/purify.min.js");
        if (!window.MD) await skriptLaden("/static/js/markdown.js");
      })();
      markdownLauf.catch(() => { markdownLauf = null; });
    }
    return markdownLauf;
  }
  /* Der Abschnitt „Prüfung“: die erste Überschrift h1–h5 der obersten Ebene (nicht in einem Kasten), deren Text ohne
     Rand und ohne abschließenden Doppelpunkt, Groß/klein egal „Prüfung“ lautet – und alles bis vor die nächste
     Überschrift gleicher oder höherer Ebene. html ist schon streng gereinigt; gelesen wird es in ein <template> (dort
     lädt nichts und läuft nichts). Liefert ein DocumentFragment oder null. */
  function abschnittPruefung(html) {
    const t = document.createElement("template");
    t.innerHTML = html;
    const knoten = Array.from(t.content.childNodes);
    const ebene = (n) => (n.nodeType === 1 && /^H[1-5]$/.test(n.tagName) ? +n.tagName[1] : 0);
    const text = (n) => n.textContent.normalize("NFC").trim().replace(/\s*:$/, "").toLocaleLowerCase("de");
    const start = knoten.findIndex((n) => ebene(n) && text(n) === "prüfung");
    if (start < 0) return null;
    const hoehe = ebene(knoten[start]);
    const teil = document.createDocumentFragment();
    for (let i = start; i < knoten.length; i++) {
      if (i > start && ebene(knoten[i]) && ebene(knoten[i]) <= hoehe) break;
      teil.appendChild(knoten[i]);
    }
    teil.querySelectorAll("a").forEach((a) => { a.setAttribute("target", "_blank"); a.setAttribute("rel", "noopener noreferrer"); });
    teil.querySelectorAll(".einbau").forEach((el) => {
      const p = document.createElement("p");
      p.className = "anleitung-einbau";
      p.textContent = ANLEITUNG_EINBAU;
      el.replaceWith(p);
    });
    teil.querySelectorAll(".md-marker").forEach((el) => el.remove());
    return teil;
  }
  function anleitungBauen(a) {
    if (a.kein_zugang) {
      const p = document.createElement("p");
      p.className = "small muted mat-anleitung-kein";
      p.textContent = ANLEITUNG_KEIN_ZUGANG;
      return p;
    }
    const url = eigeneAdresse(a.url);
    const d = document.createElement("details");
    d.className = "mat-anleitung";
    d.innerHTML = `<summary>Prüfanleitung aus der Strömipedia: <span class="mat-anleitung-titel">${esc(a.titel)}</span></summary>
      <div class="mat-anleitung-koerper"><p class="help mat-anleitung-stand" aria-live="polite">wird geladen …</p>
        ${url ? `<p class="small mat-anleitung-link"><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Ganze Seite in der Strömipedia öffnen ↗</a></p>` : ""}</div>`;
    let geladen = false;
    d.addEventListener("toggle", () => {
      if (!d.open || geladen) return;
      geladen = true;
      anleitungLaden(d, a);
    });
    return d;
  }
  async function anleitungLaden(d, a) {
    const stand = $(".mat-anleitung-stand", d);
    const sagen = (text) => { stand.textContent = text; stand.className = "small mat-anleitung-stand"; };
    let abschnitt;
    try {
      const quelle = eigeneAdresse(a.quelle);
      if (!quelle) throw new Error(ANLEITUNG_FEHLER);
      await markdownBereit();
      const seite = (await api(quelle)).page;
      if (!seite || seite.format !== "markdown") { sagen(ANLEITUNG_ALT); return; }
      abschnitt = abschnittPruefung(DOMPurify.sanitize(MD.render(seite.content || ""), ANLEITUNG_REINIGUNG));
    } catch (e) { sagen(ANLEITUNG_FEHLER); return; }
    if (!abschnitt) { sagen(ANLEITUNG_OHNE_ABSCHNITT); return; }
    const wirt = document.createElement("div");
    wirt.className = "mat-anleitung-inhalt";
    const schatten = wirt.attachShadow({ mode: "closed" });
    const css = document.createElement("link");
    css.rel = "stylesheet";
    const seitenCss = document.querySelector('link[rel="stylesheet"][href*="/css/app.css"]');
    css.href = seitenCss ? seitenCss.href : "/static/css/app.css";
    const stil = document.createElement("style");
    stil.textContent = ANLEITUNG_STIL;
    const artikel = document.createElement("article");
    artikel.className = "wiki-content";
    artikel.appendChild(abschnitt);
    schatten.append(css, stil, artikel);
    stand.replaceWith(wirt);
  }

  async function pruefungAnsicht() {
    let pr = (await Promise.all([api(`${API}/pruefungen/${DATEN.id}`), ordnerBaum().catch(() => null)]))[0].pruefung;
    let ergebnis = null;
    let seiten = [];                 // Dateien für den nächsten Anhang (Scan: eine Seite je Foto)
    let hochladen = false;           // ein Anhang ist unterwegs – der Knopf bleibt so lange gesperrt
    let gebunden = false;
    // Was gerade gespeichert wird. Tippt jemand nach einer Eingabe sofort auf „Festschreiben“, wartet der Abschluss,
    // bis alles angekommen ist (allesGesendet).
    let laufend = Promise.resolve();
    // Die Kette selbst schluckt Fehler (gemeldet hat sie der Aufrufer schon) – sonst stünde jeder abgelehnte Wert
    // zusätzlich als „Uncaught (in promise)“ in der Konsole.
    const merken = (p) => { laufend = laufend.then(() => p, () => p).catch(() => {}); return p; };
    // Was das Konto an dieser Prüfung darf, hängt am Artikel (seiner Heimat) – „darf“ kommt mit jeder Antwort neu.
    const darfHier = (r) => Boolean(pr.darf && pr.darf[r]);
    const bearbeitbar = () => pr.entwurf && pr.eigen && darfHier("pruefen");
    const punkt = (rid) => pr.punkte.find((x) => x.id === rid);
    /* Abschlussleiste und Bemerkung nur aus ihren eigenen Behältern – nie etwas Gleichnamiges aus der eingeblendeten
       Prüfanleitung (.mat-anleitung). Die Reinigung nimmt dort ids weg und der Schatten schirmt ab; das hier hält auch,
       wenn sich eins davon einmal ändert (Bauentwurf L3 3.5.2 Nr. 7). */
    const echt = (sel) => $$(sel, inhalt).find((el) => !el.closest(".mat-anleitung")) || null;
    const abschlussBox = () => echt("#pr-abschluss");
    const imAbschluss = (sel) => { const a = abschlussBox(); return a ? $(sel, a) : null; };
    const bemFeld = () => echt("#pr-bem");
    let anleitungEl = null;          // die Prüfanleitung: einmal gebaut, bei jedem Zeichnen wieder eingesetzt (bleibt offen)

    /* Getipptes speichern, während getippt wird: Wert und Bemerkung eines Prüfpunkts und die Bemerkung zur Prüfung
       gehen kurz nach dem letzten Tastendruck an den Server, nicht erst beim Verlassen des Feldes. Am Telefon
       verlässt man ein Feld oft gar nicht – Ziehen zum Neuladen, die Zurück-Geste oder ein Browser, der den Tab im
       Hintergrund verwirft, nahmen den Text sonst mit, obwohl darunter „Alles ist gespeichert“ stand.
       Je Feld ist höchstens eine Anfrage unterwegs; was währenddessen dazukommt, geht danach. So kommt beim Server nie
       ein älterer Stand nach einem neueren an, und derselbe Stand geht nicht zweimal. Die Anfragen tragen keepalive
       und kommen auch an, wenn die Seite gerade geht; wer die Seite verlässt oder wegschaltet, schickt Ausstehendes
       sofort. Bis der Server es bestätigt, liegt es außerdem in diesem Fenster (sessionStorage) und wird beim nächsten
       Laden nachgetragen – aber nur, wenn am Server noch der Stand von vorher steht. */
    const TIPP_MS = 800;
    const ABLAGE = `stroemis-mat-pruefung-${DATEN.id}`;      // „stroemis-“: Abmelden räumt es weg (common.js)
    const felder = new Map();        // "26:notiz", "26:wert", "bem" → { wert, bestaetigt, timer, unterwegs, laut, fehler }
    let ersetzt = false;             // punktErsetzen tauscht gerade eine Karte aus – deren Fokuswechsel ist kein Verlassen
    const schluessel = (el) => (el.id === "pr-bem" ? "bem" : `${el.dataset.rid}:${el.matches(".mat-pnotiz") ? "notiz" : "wert"}`);
    // Datumspunkte (mat-datum, C2 in P4-L1) zeigen TT.MM.JJJJ und speichern ISO: feldWert liefert den Wert für den
    // Server – oder null, wenn das Datum nicht lesbar ist (bleibt rot im Feld; laut: mit Toast); anzeige den Feldtext.
    function feldWert(el, laut) {
      if (!el.classList.contains("mat-datum")) return el.value;
      try { const w = datumWert(el, el.getAttribute("aria-label") || "Datum"); el.classList.remove("ungueltig"); return w; }
      catch (err) { el.classList.add("ungueltig"); if (laut) toast(err.message, true); return null; }
    }
    const anzeige = (el, wert) => (el.classList.contains("mat-datum") ? datumAnzeige(wert, "tag") : wert);
    const feldVon = (k) => (k === "bem" ? bemFeld()
      : $(`#pp-${k.split(":")[0]} ${k.endsWith(":notiz") ? ".mat-pnotiz" : ".mat-pwert"}`));
    function serverWert(k) {
      if (k === "bem") return pr.bemerkung || "";
      const [rid, feld] = k.split(":");
      const x = punkt(+rid);
      return (x && x[feld]) || "";
    }
    function eintrag(k) {
      let e = felder.get(k);
      if (!e) { e = { wert: serverWert(k), bestaetigt: serverWert(k), timer: null, unterwegs: null, laut: false, fehler: null }; felder.set(k, e); }
      return e;
    }
    const offen = (e) => Boolean(e.unterwegs) || e.wert !== e.bestaetigt;

    // Anfragen zu einem Prüfpunkt gehen nacheinander: Jede Antwort trägt den ganzen Punkt, und die Karte wird danach
    // gezeichnet. Liefen sie parallel – etwa die Bemerkung beim Verlassen des Feldes und gleich danach der Tipp auf
    // „n. z.“ –, konnte die ältere Antwort zuletzt ankommen und einen überholten Befund zeigen.
    const punktKetten = new Map();
    function punktAnfrage(rid, los) {
      const p = (punktKetten.get(+rid) || Promise.resolve()).then(los);
      punktKetten.set(+rid, p.catch(() => {}));
      return p;
    }

    function anfrage(k, wert) {
      if (k === "bem") return api(`${API}/pruefungen/${pr.id}`, { method: "PUT", body: { bemerkung: wert }, keepalive: true });
      const [rid, feld] = k.split(":");
      return punktAnfrage(rid, () => api(`${API}/pruefungen/${pr.id}/punkte/${rid}`, { method: "PUT", body: { [feld]: wert }, keepalive: true }));
    }

    function vormerken(k, wert) {
      const e = eintrag(k);
      e.wert = wert;
      clearTimeout(e.timer);
      e.timer = setTimeout(() => senden(k), TIPP_MS);
      ablegen();
      standZeigen();
    }

    // Den neuesten Stand eines Feldes schicken. laut: Fehler als Toast (beim Verlassen des Feldes, vor dem Festschreiben);
    // beim Tippen bleibt es still – eine halbe Zahl wie „-“ ist noch kein Fehler, und der Text bleibt ja im Feld.
    function senden(k, laut) {
      const e = eintrag(k);
      clearTimeout(e.timer);
      e.timer = null;
      if (laut) e.laut = true;
      if (e.unterwegs) return e.unterwegs;                 // danach geht der neueste Stand von selbst
      if (e.wert === e.bestaetigt) { e.laut = false; standZeigen(); return Promise.resolve(); }
      const wert = e.wert;
      const mitToast = e.laut;
      e.laut = false;
      let fehler = null;
      e.unterwegs = merken(anfrage(k, wert).then((antwort) => {
        e.bestaetigt = wert;
        e.fehler = null;
        uebernehmen(k, antwort);
      }, (err) => {
        fehler = err;
        e.fehler = err.message;
        if (mitToast) toast(err.message, true);
      }).then(() => {
        e.unterwegs = null;
        ablegen();
        standZeigen();
        // Inzwischen weitergetippt: den neuen Stand hinterher. Nach einem Fehler nur, wenn jemand darauf wartet.
        if (e.wert !== e.bestaetigt && (!fehler || e.laut)) return senden(k);
        return undefined;
      }));
      standZeigen();
      return e.unterwegs;
    }

    // Die Antwort übernehmen. Wer noch im Feld tippt, dem wird die Karte nicht unter den Fingern neu gezeichnet –
    // nur der Stand, der Hinweis „Bemerkung ist Pflicht“ und die Leiste folgen.
    function uebernehmen(k, antwort) {
      if (k === "bem") { pr.bemerkung = antwort.pruefung.bemerkung; return; }
      const neu = antwort.punkt;
      if (feldVon(k) === document.activeElement) {
        pr.punkte = pr.punkte.map((x) => (x.id === neu.id ? neu : x));
        const karte = $(`#pp-${neu.id}`);
        const hinweis = karte && $(".mat-pflicht-notiz", karte);
        const fehlt = neu.befund === "mangel" && !(neu.notiz || "").trim();
        if (karte && fehlt && !hinweis) $(".mat-pnotiz", karte).insertAdjacentHTML("afterend", '<span class="mat-pflicht mat-pflicht-notiz">Bemerkung ist Pflicht</span>');
        else if (hinweis && !fehlt) hinweis.remove();
        abschlussAktualisieren();
      } else {
        punktErsetzen(neu);
      }
    }

    // Alles Ausstehende jetzt schicken und abwarten – vor dem Festschreiben. Liefert die Felder, die danach noch
    // nicht gespeichert sind (kein Netz, oder der Server lehnt den Wert ab).
    async function allesGesendet() {
      await Promise.all(Array.from(felder.keys()).map((k) => senden(k, true)));
      await laufend.catch(() => {});
      return Array.from(felder.keys()).filter((k) => offen(felder.get(k)));
    }

    function ablegen() {
      const daten = {};
      felder.forEach((e, k) => { if (offen(e)) daten[k] = { wert: e.wert, basis: e.bestaetigt }; });
      try {
        if (Object.keys(daten).length) sessionStorage.setItem(ABLAGE, JSON.stringify(daten));
        else sessionStorage.removeItem(ABLAGE);
      } catch (err) { /* kein Speicher (privater Modus) – dann bleibt es beim Senden */ }
    }

    // Beim Laden: Was in diesem Fenster getippt, aber nicht bestätigt war, ins Feld zurück und noch einmal schicken.
    function nachtragen() {
      let alt;
      try { alt = JSON.parse(sessionStorage.getItem(ABLAGE) || "null"); } catch (err) { alt = null; }
      if (!alt || typeof alt !== "object") return;
      let n = 0;
      Object.entries(alt).forEach(([k, v]) => {
        const el = feldVon(k);
        if (!el || !v || typeof v.wert !== "string" || v.wert === v.basis || serverWert(k) !== v.basis) return;
        el.value = anzeige(el, v.wert);
        if (el.hidden) {
          el.hidden = false;
          const plus = $('[data-act="pnotiz-auf"]', el.closest(".mat-punkt"));
          if (plus) plus.remove();
        }
        eintrag(k).wert = v.wert;
        senden(k, true);
        n += 1;
      });
      ablegen();
      if (n) toast(`${plural(n, "Eingabe", "Eingaben")} aus diesem Fenster nachgetragen`);
    }

    function vergessen() {
      felder.forEach((e) => clearTimeout(e.timer));
      felder.clear();
      try { sessionStorage.removeItem(ABLAGE); sessionStorage.removeItem(ABSCHLUSS); } catch (err) { /* egal */ }
    }

    /* Ergebnis, Grund und „Nächste Prüfung“ der Abschlussleiste gehen erst mit dem Festschreiben an den Server. Bis dahin
       merkt sie sich dieses Fenster (sessionStorage wie oben) und setzt sie beim Laden wieder ein – Neuladen, die
       Zurück-Geste oder ein im Hintergrund verworfener Tab nahmen sie sonst mit, obwohl „Alles ist gespeichert“ dastand.
       Die Statuszeile sagt, dass sie nur hier liegen (standZeigen). */
    const ABSCHLUSS = `${ABLAGE}-abschluss`;
    // Ohne gewähltes Ergebnis gibt es nichts zu merken – Grund und Datum gehören zu ihm.
    // „Nächste Prüfung“ ist ein deutsches Textfeld (TT.MM.JJJJ, C2 in P4-L1); gemerkt und gesendet wird ISO. Ungültig
    // Getipptes zählt hier als leer – beim Festschreiben gibt es dafür den Toast (dueWert).
    function dueIso(due) {
      try { return datumWert(due, "Nächste Prüfung"); } catch (e) { return ""; }
    }
    function abschlussStand() {
      const grund = imAbschluss("#pr-grund"), due = imAbschluss("#pr-due");
      return { ergebnis, grund: grund ? grund.value : "", faellig: due ? dueIso(due) : "", leer: !ergebnis };
    }
    function abschlussMerken() {
      const d = abschlussStand();
      try {
        if (d.leer) sessionStorage.removeItem(ABSCHLUSS);
        else sessionStorage.setItem(ABSCHLUSS, JSON.stringify({ ergebnis: d.ergebnis, grund: d.grund, faellig: d.faellig }));
      } catch (err) { /* kein Speicher (privater Modus) – dann bleibt es bis zum Festschreiben im Fenster */ }
      standZeigen();
    }
    function abschlussZurueck() {
      let alt;
      try { alt = JSON.parse(sessionStorage.getItem(ABSCHLUSS) || "null"); } catch (err) { alt = null; }
      if (alt && typeof alt === "object") {
        if (WAEHLBAR.includes(alt.ergebnis)) ergebnis = alt.ergebnis;
        const grund = imAbschluss("#pr-grund"), due = imAbschluss("#pr-due");
        if (grund && typeof alt.grund === "string") grund.value = alt.grund.slice(0, 300);
        if (due && typeof alt.faellig === "string" && /^\d{4}-\d{2}-\d{2}$/.test(alt.faellig)
          && alt.faellig >= isoHeute(1) && (!pr.vorschlag_naechste || alt.faellig <= pr.vorschlag_naechste)) due.value = datumAnzeige(alt.faellig, "tag");
        abschlussAktualisieren();
      }
      abschlussMerken();             // was nicht mehr gilt (etwa „einsatzbereit“ nach einem kritischen Mangel), fällt weg
    }

    // „Alles ist gespeichert“ nur, wenn es stimmt.
    function standZeigen() {
      const el = $("#pr-stand");
      if (!el) return;
      let ausstehend = false;
      let fehler = null;
      felder.forEach((e) => { if (offen(e)) { ausstehend = true; if (e.fehler && !e.unterwegs) fehler = e.fehler; } });
      el.textContent = fehler ? `Noch nicht gespeichert (${fehler}). Was du getippt hast, bleibt in diesem Fenster und geht erneut, sobald du das Feld verlässt.`
        : ausstehend ? "Wird gespeichert …"
        : !abschlussStand().leer ? "Alles außer dem Ergebnis ist gespeichert – du kannst die Prüfung jederzeit unterbrechen und später fortsetzen. Das Ergebnis samt Grund bzw. nächster Prüfung merkt sich bis zum Festschreiben nur dieses Fenster."
        : "Alles ist gespeichert – du kannst die Prüfung jederzeit unterbrechen und später fortsetzen.";
      el.classList.toggle("mat-warn", Boolean(fehler));
    }

    /* Tastatur offen: Solange in einem Feld außerhalb der Abschlussleiste getippt wird, kleben Kopf- und
       Abschlussleiste nicht (.tippt, material.css). Quer neben der Tastatur blieb vom Feld sonst nichts zu sehen.
       „Offen“ heißt: Android verkleinert das Fenster (interactive-widget=resizes-content), iOS nur den sichtbaren
       Ausschnitt. Ein Rechner mit Maus bleibt, wie er ist. Die Leisten kommen erst einen Augenblick nach dem
       Verlassen des Feldes zurück – sonst landete der Tipp auf einen Umschalter womöglich auf der Leiste, die eben
       an dieser Stelle wieder erscheint. */
    const TIPPFELD = "textarea, input[type=text], input[type=search], input[type=number], input:not([type])";
    const grob = window.matchMedia("(pointer: coarse)");
    const hoechste = new Map();      // größte Fensterhöhe je Breite – deutlich weniger heißt: Tastatur
    let tipptAus = null;
    function tastaturOffen() {
      const vv = window.visualViewport;
      if (vv && vv.scale <= 1.01 && vv.height < window.innerHeight - 100) return true;            // iOS
      if (!grob.matches) return false;
      if (window.innerHeight < (hoechste.get(window.innerWidth) || 0) - 100) return true;         // Android
      // Gleich nach dem Drehen mit offener Tastatur gibt es für die neue Breite noch keinen Vergleich: dann am
      // Bildschirm in dieser Lage messen.
      const quer = screen.orientation ? /landscape/.test(screen.orientation.type) : window.innerWidth > window.innerHeight;
      return window.innerHeight < (quer ? Math.min(screen.width, screen.height) : Math.max(screen.width, screen.height)) * 0.6;
    }
    function tipptPruefen(spaeter) {
      const box = $(".mat-mit-leiste", inhalt);
      if (!box) return;
      hoechste.set(window.innerWidth, Math.max(hoechste.get(window.innerWidth) || 0, window.innerHeight));
      const ae = document.activeElement;
      const an = Boolean(ae && ae.matches && ae.matches(TIPPFELD) && box.contains(ae) && !ae.closest(".mat-abschluss") && tastaturOffen());
      clearTimeout(tipptAus);
      if (an) {
        box.classList.add("tippt");
        // Das Feld ins Bild holen, falls es (etwa nach dem Drehen mit offener Tastatur) außerhalb liegt.
        requestAnimationFrame(() => {
          if (document.activeElement !== ae) return;
          const r = ae.getBoundingClientRect();
          if (r.top < 0 || r.bottom > window.innerHeight) ae.scrollIntoView({ block: "nearest" });
        });
      } else if (!box.classList.contains("tippt")) {
        return;
      } else if (spaeter) {
        tipptAus = setTimeout(() => tipptPruefen(false), 300);
      } else {
        box.classList.remove("tippt");
      }
    }

    // Wie hoch die Abschlussleiste gerade ist: Danach richtet sich, wie weit ein fokussiertes Feld über ihr bleibt.
    const leisteBeobachter = window.ResizeObserver ? new ResizeObserver((eintraege) => {
      const h = eintraege[0] && eintraege[0].target.isConnected ? eintraege[0].target.offsetHeight : 0;
      document.documentElement.style.setProperty("--mat-leiste-h", `${h}px`);
    }) : null;

    // Berichtigen darf nur, wer die Prüfung gemacht hat; ob es gerade geht, sagt der Server (berichtigbar). Eine
    // Aussonderung (auch „aussondern“ als Ergebnis) ist nie berichtigbar – dort gibt es den Knopf gar nicht.
    const darfBerichtigen = () => !pr.entwurf && pr.eigen && darfHier("pruefen") && pr.berichtigbar && pr.art !== "aussonderung"
      && pr.ergebnis !== "aussondern";

    function kopf() {
      const a = pr.artikel;
      const knoepfe = [];
      if (pr.entwurf && !pr.eigen && darfHier("verwalten")) knoepfe.push('<button class="btn secondary small" data-act="freigeben">Reservierung aufheben</button>');
      if (darfBerichtigen()) {
        knoepfe.push(pr.berichtigbar.ok ? '<button class="btn secondary small" data-act="berichtigen">Berichtigen</button>'
          : `<button class="btn secondary small" type="button" disabled title="${esc(pr.berichtigbar.grund)}">Berichtigen</button>`);
      }
      return `${pr.artikel.demo ? `<p class="mat-demo-banner">${DEMO_ARTIKEL}</p>` : ""}
        <div class="mat-pfad">${pfadHtml([...a.pfad.map(pfadGlied), `<a href="/materialablage/artikel/${a.id}">${esc(a.inventory_no)}</a>`])}</div>
        <div class="page-head"><h1>${esc(PRUEFART[pr.art] || pr.art)} <span class="mat-h1-zusatz mat-inv">${esc(a.inventory_no)}</span> ${pr.entwurf ? '<span class="badge">Entwurf</span>' : ergebnisMarke(pr.ergebnis)}</h1>
          ${knoepfe.length ? `<div class="btn-row">${knoepfe.join("")}</div>` : ""}</div>
        ${berichtigungHinweis()}
        <p class="mat-produktzeile"><strong>${nameHtml(pr.produkt)}</strong>${zusatzHtml(pr.produkt)}${artNrHtml(pr.produkt.article_no)} · ${nummerHtml("Seriennummer", a.serial_no)} ${statusMarke(a.status)}</p>
        <p class="small muted">${pr.formular ? `Formular ${esc(pr.formular.titel || "ohne Titel")}, Version ${pr.formular.version} · ` : ""}${pr.art === "aussonderung" ? "Ausgeführt von" : "Prüfer"} ${person(pr.pruefer || "–")}${pr.urkunde ? ` (<span class="mat-ganz">Urkundennummer ${esc(pr.urkunde)}</span>)` : ""}
          · ${pr.entwurf && !pr.berichtigt ? `begonnen ${esc(fmtZeit(pr.begonnen_am))}` : `Prüftag ${esc(fmtTag(pr.datum))}`}
          ${pr.durchgang ? ` · Durchgang ${pr.durchgang.sichtbar ? `<a href="/materialablage/durchgang/${pr.durchgang.id}">${esc(pr.durchgang.titel)}</a>` : `„${esc(pr.durchgang.titel)}“`}` : ""}</p>
        ${pr.anleitung ? '<div class="mat-anleitung-platz"></div>' : ""}`;
    }
    // Die Prüfanleitung aus dem Wiki (nur offene Prüfungen, Phase 2 · L3) an ihren Platz im Kopf – dasselbe Element wie
    // beim letzten Zeichnen, damit eine aufgeklappte Anleitung offen und geladen bleibt.
    function anleitungEinsetzen() {
      const platz = $(".mat-anleitung-platz", inhalt);
      if (!platz) return;
      if (!anleitungEl) anleitungEl = anleitungBauen(pr.anleitung);
      platz.replaceWith(anleitungEl);
    }

    /* Berichtigung: Die Berichtigung verweist auf ihr Original, das Original auf seine Berichtigung. */
    function berichtigungHinweis() {
      const b = pr.berichtigt;
      const original = (x) => (x.protokoll_id
        ? `von <a href="/materialablage/pruefung/${x.id}">Protokoll ${esc(x.protokoll_id)}</a> vom ${esc(fmtTag(x.datum))}`
        : `<a href="/materialablage/pruefung/${x.id}">der Prüfung vom ${esc(fmtTag(x.datum))}</a> (ohne Protokoll)`);
      let html = "";
      if (b && pr.entwurf) {
        html += `<div class="mat-ber"><strong>Berichtigung</strong> ${original(b)} – Grund: ${esc(pr.grund_berichtigung || "–")}.
          Der Prüftag bleibt der ${esc(fmtTag(pr.datum))}, die Art der Prüfung steht fest. Erst mit dem Festschreiben ersetzt die Berichtigung das Original.</div>`;
      } else if (b) {
        html += `<div class="mat-ber"><strong>Berichtigung</strong> ${original(b)}. Grund: ${esc(pr.grund_berichtigung || "–")}</div>`;
      }
      const d = pr.berichtigt_durch;
      if (d && d.entwurf) {
        html += `<div class="mat-ber"><strong>Berichtigung in Arbeit</strong> bei ${person(d.pruefer || "–")} – <a href="/materialablage/pruefung/${d.id}">Entwurf ansehen</a>. Bis sie festgeschrieben ist, gilt diese Prüfung.</div>`;
      } else if (d) {
        html += `<div class="mat-ber ersetzt"><strong>Berichtigt</strong> durch <a href="/materialablage/pruefung/${d.id}">${d.protokoll_id ? `Protokoll ${esc(d.protokoll_id)}` : "eine spätere Prüfung"}</a> – maßgeblich ist die Berichtigung. Diese Prüfung bleibt${pr.protokoll ? " mit ihrem Protokoll" : ""} unverändert erhalten.</div>`;
      }
      return html;
    }

    // Seriennummern der Bestandteile an der Zeile „… vorhanden“ (Schritt 25), gelesen: „SN A1 → A2“ bzw. „Stück 2: …“.
    function nummernLesen(x) {
      const n = (x.nummern || []).filter((y) => y.alt || (y.neu !== null && y.neu !== undefined));
      if (!n.length) return "";
      return n.map((y) => `<div class="small muted mat-teilnummern">${x.nummern.length > 1 ? `Stück ${y.stueck}: ` : "SN "}${y.neu !== null && y.neu !== undefined && y.neu !== y.alt
        ? `${esc(y.alt || "–")} → ${esc(y.neu || "–")}` : esc(y.alt)}</div>`).join("");
    }

    function punktHtml(x) {
      const mangel = x.befund === "mangel";
      const nz = x.befund === "nicht_zutreffend";
      const laengeMoeglich = !!(pr.laenge && pr.laenge.moeglich);
      let steuer;
      if (x.art === "yesno") {
        // Bestandteil-Liste (Schritt 25; alte Prüfungen früherer Set-Artikel ebenso): „vorhanden“/„fehlt“ statt Ja/Nein –
        // gespeichert bleibt ja/nein.
        const wort = istBestandteil(x) ? { ja: "vorhanden", nein: "fehlt" } : { ja: "Ja", nein: "Nein" };
        steuer = `<div class="mat-wahl3" role="group" aria-label="Befund zu ${esc(x.text)}">
          ${["ja", "nein"].map((w) => `<button type="button" data-act="pwert" data-rid="${x.id}" data-wert="${w}" class="${w === x.soll ? "soll" : "abw"}" aria-pressed="${!nz && x.wert === w}">${wort[w]}</button>`).join("")}
          <button type="button" data-act="pbefund" data-rid="${x.id}" data-befund="nicht_zutreffend" aria-pressed="${nz}" title="nicht zutreffend">n. z.</button></div>`;
      } else if (x.art === "signature") {
        // Unterschriftsfeld: gezeichnet im Pad (unterschrift.js); „n. z.“ nimmt es heraus. Kein Foto.
        steuer = `<div class="mat-us-feld">
          ${x.unterschrift ? `<img class="mat-us-bild" src="${esc(x.unterschrift)}" alt="Unterschrift: ${esc(x.text)}">` : ""}
          <div class="btn-row">${nz ? "" : `<button type="button" class="btn secondary small" data-act="punterschrift" data-rid="${x.id}">${x.unterschrift ? "Neu unterschreiben" : "Unterschreiben"}</button>`}
            ${x.unterschrift ? `<button type="button" class="btn secondary small" data-act="punterschrift-weg" data-rid="${x.id}">Entfernen</button>` : ""}
            <button type="button" class="btn secondary small mat-nz-knopf" data-act="pbefund" data-rid="${x.id}" data-befund="nicht_zutreffend" aria-pressed="${nz}" title="nicht zutreffend">n. z.</button></div></div>`;
      } else {
        const feld = x.art === "photo" ? ""
          : x.art === "date" ? `<input type="text" class="mat-pwert mat-datum" data-art="tag" inputmode="numeric" autocomplete="off" maxlength="10" placeholder="TT.MM.JJJJ" data-rid="${x.id}" value="${esc(datumAnzeige(x.wert, "tag"))}" aria-label="${esc(x.text)}">`
          : x.art === "number" ? `<input type="text" inputmode="decimal" class="mat-pwert" data-rid="${x.id}" value="${esc(x.wert || "")}" placeholder="${x.soll ? `Soll ${esc(x.soll)}` : "Wert"}" aria-label="${esc(x.text)}">`
          // Längenpunkt (Schritt 20): vorbelegt mit der Artikellänge; ohne vorgesehene Länge (Kategorie) nur „n. z.“.
          : x.art === "laenge" ? (laengeMoeglich
            ? `<input type="text" inputmode="decimal" class="mat-pwert mat-laenge-feld" data-rid="${x.id}" value="${esc(x.wert || "")}" placeholder="Länge in m" autocomplete="off" maxlength="10" aria-label="${esc(x.text)}">`
            : `<p class="help mat-laenge-hinweis">Für Artikel dieser Kategorie ist keine Länge vorgesehen – der Punkt gilt als nicht zutreffend.</p>`)
          : `<textarea class="mat-pwert" data-rid="${x.id}" rows="2" maxlength="1000" aria-label="${esc(x.text)}" placeholder="${esc(x.soll || "")}">${esc(x.wert || "")}</textarea>`;
        steuer = `${feld}<div class="mat-wahl3" role="group" aria-label="Befund zu ${esc(x.text)}">
          ${[["ok", "in Ordnung", "soll"], ["mangel", "Mangel", "abw"], ["nicht_zutreffend", "n. z.", ""]]
            .filter(([b]) => x.art !== "laenge" || laengeMoeglich || b === "nicht_zutreffend").map(([b, t, k]) => `<button type="button" data-act="pbefund" data-rid="${x.id}" data-befund="${b}" class="${k}" aria-pressed="${x.befund === b}"${b === "nicht_zutreffend" ? ' title="nicht zutreffend"' : ""}>${t}</button>`).join("")}</div>`;
      }
      const fotoPflicht = mangel || (x.art === "photo" && x.pflicht && !nz);
      // Zwei Wege zum Foto: „Foto“ öffnet am Telefon gleich die Kamera (capture), „Galerie“ nimmt ein schon
      // gemachtes Foto (Kamera-App, ohne Netz aufgenommen, vom Kollegen). Am Rechner öffnen beide nur die
      // Dateiauswahl – dort steht allein der erste (material.css). „Foto entfernen“ fragt nach und steht abgesetzt.
      const foto = x.art === "signature" ? "" : `<div class="mat-punkt-foto">
          ${x.foto ? bildLink(x.foto.web, x.foto.original, x.text, "punkte", `<img src="${esc(x.foto.vorschau)}" alt="Foto zu ${esc(x.text)}">`) : ""}
          <label class="btn secondary small mat-kamera">${x.foto ? "neues Foto" : "Foto"}<input type="file" accept="image/*" capture="environment" data-foto="${x.id}" class="mat-datei" aria-label="Foto zu ${esc(x.text)}"></label>
          <label class="btn secondary small mat-galerie">Galerie<input type="file" accept="image/*" data-foto="${x.id}" class="mat-datei" aria-label="Foto zu ${esc(x.text)} aus der Galerie wählen"></label>
          ${x.foto ? `<button type="button" class="btn secondary small mat-foto-weg" data-act="pfoto-weg" data-rid="${x.id}">Foto entfernen</button>` : ""}
          ${fotoPflicht && !x.foto ? '<span class="mat-pflicht">Foto ist Pflicht</span>' : ""}</div>`;
      const notiz = mangel || x.notiz;
      // Seriennummern der Bestandteile (Schritt 25): je Stück ein Feld, vorbelegt mit der Nummer am Artikel – eine neue
      // oder fehlende trägt der Prüfer hier ein, übernommen wird sie beim Festschreiben (das Protokoll zeigt alt → neu).
      // Eigenes Fieldset unter der Bemerkung (Prüfung Browser, Verbesserung 1); in der Berichtigung dazu der Stand am
      // Artikel, wenn er vom Feld abweicht; dieselbe Nummer an zwei Stück nur als Hinweis (doppeltePruefen).
      const mehrere = (x.nummern || []).length > 1;
      const nummern = (x.nummern || []).length ? `<fieldset class="mat-punkt-nummern"><legend id="pn-${x.id}-titel">${mehrere ? "Seriennummern" : "Seriennummer"}</legend>${x.nummern.map((n) => `<div>${mehrere ? `<label for="pn-${x.id}-${n.stueck}">Stück ${n.stueck}</label>` : ""}
          <input type="text" class="mat-pnummer" id="pn-${x.id}-${n.stueck}" data-rid="${x.id}" data-name="${esc(x.text.replace(/ vorhanden$/, "") + (mehrere ? `, Stück ${n.stueck}` : ""))}" maxlength="80" autocomplete="off" value="${esc(n.wert || "")}" placeholder="keine" ${mehrere ? "" : `aria-labelledby="pn-${x.id}-titel" `}${TASTATUR_NUMMER}>
          ${n.neu !== null && n.neu !== undefined && n.neu !== n.alt ? `<div class="help">bisher ${esc(n.alt || "keine")}</div>` : ""}${n.artikel !== undefined && n.artikel !== n.wert ? `<div class="help">am Artikel heute ${esc(n.artikel || "keine")}</div>` : ""}</div>`).join("")}</fieldset>` : "";
      return `<div class="mat-punkt${mangel ? " mangel" : ""}${nz ? " nz" : ""}" id="pp-${x.id}">
        <div class="mat-punkt-kopf"><span class="mat-punkt-text">${esc(x.text)}</span>
          ${x.kritisch ? '<span class="mat-kritisch" title="Ein Mangel hier schließt „einsatzbereit“ aus">kritisch</span>' : ""}
          ${x.art === "yesno" && x.soll && !istBestandteil(x) ? `<span class="muted small">Soll ${esc(x.soll)}</span>` : ""}${x.art === "laenge" && laengeMoeglich ? `<span class="muted small">${x.soll ? `am Artikel ${esc(x.soll)} m` : "am Artikel keine Länge"}</span>` : ""}${x.pflicht ? "" : '<span class="muted small">optional</span>'}</div>
        <div class="mat-punkt-zeile">${steuer}${foto}
          ${notiz ? "" : `<button type="button" class="lnk small" data-act="pnotiz-auf" data-rid="${x.id}"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Bemerkung<span class="k-anlegen"> anlegen</span></span></button>`}</div>
        <label for="pnotiz-${x.id}" class="mat-pnotiz-label">${mangel ? "Bemerkung zum Mangel" : "Bemerkung"}</label>
        <textarea class="mat-pnotiz" id="pnotiz-${x.id}" data-rid="${x.id}" rows="2" maxlength="1000" placeholder="${mangel ? "Pflicht: Was ist wo zu sehen?" : ""}" ${notiz ? "" : "hidden"}${mangel ? ' aria-required="true"' : ""}>${esc(x.notiz || "")}</textarea>
        ${mangel && !(x.notiz || "").trim() ? '<span class="mat-pflicht mat-pflicht-notiz">Bemerkung ist Pflicht</span>' : ""}
        ${nummern}</div>`;
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
          <div class="btn-row"><label class="btn secondary small">Seite fotografieren<input type="file" accept="image/*" capture="environment" id="ah-kamera" class="mat-datei"></label>
            <label class="btn secondary small">Dateien wählen<input type="file" accept="application/pdf,image/*" multiple id="ah-dateien" class="mat-datei"></label></div>
          <ol class="mat-scan" id="ah-seiten"></ol>
          <label class="inline"><input type="checkbox" id="ah-protokoll" checked> hinten ans Protokoll hängen</label>
          <div class="btn-row"><button type="button" class="btn secondary small" data-act="anhang-hoch" id="ah-hoch" disabled>Als ein PDF anhängen</button></div></div>` : "";
      return `<section class="section"><h2>Anhänge${bearbeitbar() ? infoKnopf("Anhänge", "Externe Prüfkarte, Bericht eines Prüfdienstes … als PDF oder Foto. Mehrere Fotos (eine je Seite) und PDFs werden in der Reihenfolge der Liste ein PDF.") : ""}</h2>
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
      // Die Statuszeile steht über Ergebnis und „Festschreiben“, nicht darunter (Designsprache, Nutzer 25.10.2026).
      return `<div class="mat-abschluss" id="pr-abschluss" role="region" aria-label="Ergebnis und Abschluss">
        <div class="mat-abschluss-hinweis" id="pr-hinweis" aria-live="polite" data-act="hinweis-ganz"></div>
        <div class="mat-ergebnis" role="group" aria-label="Ergebnis" aria-describedby="pr-hinweis">
          ${WAEHLBAR.map((e) => `<button type="button" data-act="ergebnis" data-e="${e}" class="e-${e}" aria-pressed="false">${esc(ERGEBNIS[e])}</button>`).join("")}</div>
        <div class="mat-abschluss-zeile">
          <label class="mat-due" id="pr-due-feld" hidden>Nächste Prüfung ${datumFeld("pr-due", pr.vorschlag_naechste || "", "tag")}
            <span class="mat-due-hilfe">frühestens ${esc(fmtTag(isoHeute(1)))}${pr.vorschlag_naechste ? `, spätestens ${esc(fmtTag(pr.vorschlag_naechste))}` : ""}</span></label>
          <input type="text" id="pr-grund" maxlength="300" placeholder="Grund" aria-label="Grund" value="${esc(pr.grund || "")}" hidden>
          <button type="button" class="btn" data-act="festschreiben" id="pr-ok" aria-describedby="pr-hinweis" disabled>Festschreiben</button></div></div>`;
    }

    // In der einzeiligen Leiste (wenig Höhe, breite Touch-Geräte – material.css) ist das Feld für den Grund oft schmal: Passt
    // die Langform dort nicht hinein, steht nur „Grund“ darin und die Langform im title. Am Rechner bleibt sie.
    const EINZEILIG = window.matchMedia("(max-height: 500px) and (min-width: 561px), (pointer: coarse) and (min-width: 600px)");
    const textMass = document.createElement("canvas").getContext("2d");
    function grundPlatzhalter() {
      const g = imAbschluss("#pr-grund");
      if (!g) return;
      const lang = offeneHinweise().maengel.length ? "Grund (freiwillig – die Mängel stehen oben)" : "Grund (Pflicht ohne Mangel)";
      let kurz = false;
      if (EINZEILIG.matches && !g.hidden) {
        const s = getComputedStyle(g);
        textMass.font = `${s.fontSize} ${s.fontFamily}`;
        kurz = textMass.measureText(lang).width > g.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
      }
      g.placeholder = kurz ? "Grund" : lang;
      g.title = kurz ? lang : "";
    }
    function abschlussAktualisieren() {
      const h = offeneHinweise();
      if (ergebnis === "einsatzbereit" && h.einsatzSperre) { ergebnis = null; abschlussMerken(); }
      const box = abschlussBox();
      $$("[data-act=ergebnis]", box).forEach((b) => {
        b.setAttribute("aria-pressed", String(b.dataset.e === ergebnis));
        if (b.dataset.e === "einsatzbereit") {
          b.disabled = !!h.einsatzSperre;
          b.title = h.einsatzSperre ? (pr.einsatzbereit_gesperrt.concat(h.kritisch.length ? ["kritischer Mangel"] : [])).join("; ") : "";
        }
      });
      $("#pr-due-feld", box).hidden = ergebnis !== "einsatzbereit";
      $("#pr-grund", box).hidden = !ergebnis || ergebnis === "einsatzbereit";
      grundPlatzhalter();
      $("#pr-ok", box).disabled = !ergebnis;
      const teile = [];
      if (h.offen.length) teile.push(`${plural(h.offen.length, "Pflichtpunkt", "Pflichtpunkte")} ohne Befund`);
      if (h.ohneFoto.length) teile.push(`${plural(h.ohneFoto.length, "Mangel", "Mängel")} ohne Foto`);
      if (h.ohneNotiz.length) teile.push(`${plural(h.ohneNotiz.length, "Mangel", "Mängel")} ohne Bemerkung`);
      if (h.kritisch.length) teile.push("kritischer Mangel – nicht einsatzbereit");
      else if (pr.lebensdauer && pr.lebensdauer.erreicht) teile.push("Lebensende erreicht – nicht einsatzbereit");
      if (pr.freipruefung && ergebnis === "einsatzbereit") teile.push("Freiprüfung: Der Artikel kehrt in seinen Herkunftsordner zurück");
      if (ergebnis === "instandsetzen" && !pr.freipruefung) teile.push("„instandsetzen“ sperrt den Artikel");
      if (ergebnis === "aussondern_empfohlen") teile.push(pr.freipruefung ? "Der Artikel bleibt gesperrt – aussondern kann der Materialwart" : "„aussondern empfohlen“ sperrt den Artikel – aussondern kann der Materialwart");
      if (!DARF.unterschrift) teile.push("Deine Unterschrift fehlt noch – „Festschreiben“ fragt danach");
      $("#pr-hinweis", box).textContent = teile.join(" · ");
      $("#pr-hinweis", box).classList.toggle("warn", !!(h.offen.length || h.ohneFoto.length || h.ohneNotiz.length || h.kritisch.length));
    }

    function leseHtml() {
      const zeilen = pr.punkte.map((x) => `<tr class="${x.befund === "mangel" ? "mat-mangelzeile" : ""}">
          <td data-l="Prüfpunkt" class="mat-k-ohne">${x.gruppe ? `<span class="muted small">${esc(x.gruppe)}</span><br>` : ""}${esc(x.text)}</td>
          <td class="mat-krit-spalte mat-k-kurz">${x.kritisch ? '<span class="mat-kritisch">kritisch</span>' : ""}</td>
          <td data-l="Befund" class="mat-k-kurz mat-k-ohne">${x.art === "signature" && !x.unterschrift && x.befund !== "nicht_zutreffend" ? '<span class="muted">nicht unterschrieben</span>' : befundMarke(x.befund)}</td><td data-l="Wert" class="mat-k-kurz">${x.art === "signature" && x.unterschrift ? `<img class="mat-us-mini" src="${esc(x.unterschrift)}" alt="Unterschrift">`
            : x.art === "laenge" && x.wert ? `${esc(x.wert)} m${x.soll && x.soll !== x.wert ? ` <span class="muted small mat-soll">(vorher ${esc(x.soll)} m)</span>` : x.soll ? ' <span class="muted small mat-soll">(unverändert)</span>' : ""}`
            : istBestandteil(x) && x.art === "yesno" && x.wert ? esc(x.wert === "ja" ? "vorhanden" : "fehlt")
            : x.wert ? esc(x.wert) : '<span class="muted">–</span>'}${x.art === "yesno" && x.soll && !istBestandteil(x) ? ` <span class="muted small mat-soll">(Soll ${esc(x.soll)})</span>` : ""}${nummernLesen(x)}</td>
          <td data-l="Bemerkung">${x.notiz ? `<span class="mat-text">${esc(x.notiz)}</span>` : ""}</td>
          <td data-l="Foto">${x.foto ? bildLink(x.foto.web, x.foto.original, `${x.text}${x.notiz ? ` – ${x.notiz}` : ""}`, "befunde", `<img class="mat-mini" src="${esc(x.foto.vorschau)}" alt="Foto">`) : ""}</td></tr>`).join("");
      // Die Marke steht direkt unter der Überschrift „Ergebnis“ – nicht noch einmal als Zeile „Ergebnis“ (Reste, 4).
      const ergebnisBox = pr.entwurf ? `<p class="notice">Diese Prüfung ist noch offen – in Prüfung bei ${person(pr.pruefer)} seit ${esc(fmtZeit(pr.begonnen_am))}. Was hier steht, ist der aktuelle Stand des Entwurfs.</p>`
        : `<div class="mat-spalten"><section class="section"><h2>Ergebnis</h2><p class="mat-ergebnis-zeile">${ergebnisMarke(pr.ergebnis)}</p><dl class="mat-daten">
          <dt>Prüftag</dt><dd>${esc(fmtTag(pr.datum))}</dd>
          ${pr.naechste ? `<dt>Nächste Prüfung</dt><dd><strong>${esc(fmtTag(pr.naechste))}</strong></dd>` : ""}
          ${pr.grund ? `<dt>Grund</dt><dd>${esc(pr.grund)}</dd>` : ""}
          ${pr.bemerkung ? `<dt>Bemerkung</dt><dd class="mat-text">${esc(pr.bemerkung)}</dd>` : ""}
          <dt>${pr.art === "aussonderung" ? "Ausgeführt von" : "Prüfer"}</dt><dd>${person(pr.pruefer || "–")}${pr.urkunde ? ` · <span class="mat-ganz">Urkundennummer ${esc(pr.urkunde)}</span>` : ""}</dd>
          ${pr.basis_id ? `<dt>Grundlage</dt><dd><a href="/materialablage/pruefung/${pr.basis_id}">Prüfung vom Tag der Aussonderung</a></dd>` : ""}
          <dt>Abgeschlossen</dt><dd>${esc(fmtZeit(pr.abgeschlossen_am))}</dd></dl></section>${protokollHtml()}</div>`;
      return `${ergebnisBox}
        ${pr.punkte.length ? `<section class="section"><h2>Befunde${pr.punkte.some((x) => x.kritisch) ? infoKnopf("kritisch", "„kritisch“: Ein Mangel an diesem Prüfpunkt schließt „einsatzbereit“ aus.") : ""}</h2><table class="list mat-tabelle mat-karten mat-befunde"><thead><tr><th>Prüfpunkt</th><th class="mat-krit-spalte"><span class="mat-vorlesen">kritisch</span></th><th>Befund</th><th>Wert</th><th>Bemerkung</th><th>Foto</th></tr></thead><tbody>${zeilen}</tbody></table></section>` : ""}
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
      return `<dt>Aussonderung</dt><dd><a href="/materialablage/pruefung/${a.id}">${a.protokoll ? `Protokoll ${esc(a.protokoll.id)}` : "Aussonderung ansehen"}</a>
        ${a.protokoll ? ` · <a class="mat-pdf" href="${esc(a.protokoll.url)}" target="_blank" rel="noopener" title="Aussonderungsprotokoll ${esc(a.protokoll.id)} öffnen">PDF</a>` : ""}</dd>`;
    }

    /* Das festgeschriebene Protokoll: ID, PDF, wann und mit welcher Anmeldung, Prüfsumme, Unterschrift. */
    function protokollHtml() {
      const p = pr.protokoll;
      const nein = darfBerichtigen() && !pr.berichtigbar.ok && !pr.berichtigt_durch
        ? `<p class="small muted">Berichtigen geht nicht: ${esc(pr.berichtigbar.grund)}</p>` : "";
      if (!p) return `<section class="section mat-protokoll"><h2>Protokoll</h2><p class="muted">Vor Einführung des Festschreibens abgeschlossen – ohne Protokoll.</p>${nein}</section>`;
      // Die eine Abschnittsaktion („Protokoll (PDF)“) steht rechts neben der Überschrift (.abschnittskopf wie „Stammdaten“
      // → „Änderung beantragen“; Nutzer 27.10.2026), die Kennung allein als erste Zeile darunter.
      return `<section class="section mat-protokoll"><div class="abschnittskopf"><h2>Protokoll</h2>
          <a class="btn secondary small" href="${esc(p.url)}" target="_blank" rel="noopener">Protokoll (PDF)</a></div>
        <div class="mat-protokoll-kopf"><span class="mat-protokoll-id mat-hash">${esc(p.id)}</span></div>
        <dl class="mat-daten">
          <dt>Festgeschrieben</dt><dd>${esc(fmtZeit(p.festgeschrieben))}${p.anmeldung ? ` von ${person(p.anmeldung)}` : ""}</dd>
          <dt>Prüfsumme${infoKnopf("Prüfsumme", PRUEFSUMME_INFO)}</dt><dd><span class="small muted">SHA-256 (erste ${esc(p.bytes)} Bytes)</span><br>${summeKnopf(p.sha256)}</dd>
          ${pr.unterschrift ? `<dt>Unterschrift</dt><dd><img class="mat-us-bild" src="${esc(pr.unterschrift)}" alt="Unterschrift von ${esc(pr.pruefer || "")}"></dd>` : ""}
          ${aussonderungHtml()}
        </dl>${nein}</section>`;
    }

    function bearbeitenHtml() {
      return `${pr.freipruefung ? `<p class="mat-banner s-gesperrt">GESPERRT – mit „einsatzbereit“ ist diese Prüfung die Freiprüfung.</p>` : ""}
        ${mangelHinweis(pr.maengel, Boolean(pr.berichtigt))}
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
        <p class="help"><span id="pr-stand">Alles ist gespeichert – du kannst die Prüfung jederzeit unterbrechen und später fortsetzen.</span>
          <button type="button" class="lnk" data-act="verwerfen">${pr.berichtigt ? "Berichtigung verwerfen" : "Entwurf verwerfen"}</button></p>
        ${abschlussHtml()}`;
    }

    function zeichnen() {
      leisteMarkieren(pr.artikel.folder_id);
      // Der eigene Entwurf, aber prüfen geht gerade nicht (Urkundennummer fehlt, Prüffreigabe abgelaufen): warum.
      const ohneNummer = pr.entwurf && pr.eigen && !darfHier("pruefen") && (DARF.pruefer_haekchen || DARF.qualifiziert) ? `<p class="notice">${pruefHinweis(pr)}</p>` : "";
      seitenTitel(`${PRUEFART[pr.art] || pr.art} ${pr.artikel.inventory_no}`);
      inhalt.innerHTML = `<div class="mat-pruefung${bearbeitbar() ? " mat-mit-leiste" : ""}">${kopf()}${ohneNummer}${bearbeitbar() ? bearbeitenHtml() : leseHtml()}</div>`;
      anleitungEinsetzen();
      doppelteZeigen(inhalt);
      if (leisteBeobachter) leisteBeobachter.disconnect();
      if (bearbeitbar()) {
        binden(); abschlussAktualisieren(); abschlussZurueck(); seitenZeichnen(); tipptPruefen(false);
        if (leisteBeobachter) leisteBeobachter.observe(abschlussBox());
      } else {
        vergessen();
      }
    }

    /* Die Karte neu zeichnen – ohne dem, der gerade darin tippt, etwas wegzunehmen: Was im fokussierten Feld
       steht, aber noch nicht gespeichert ist, bleibt stehen (es geht beim Tippen ohnehin an den Server), eine
       geöffnete Bemerkung bleibt offen, und der Fokus kehrt auf dasselbe Element zurück – sonst schlösse
       sich am Telefon die Tastatur mitten im Satz und die Tastaturbedienung fiele an den Seitenanfang.
       Was in einem anderen Feld der Karte getippt, aber noch nicht bestätigt ist, bleibt ebenso stehen. */
    function punktErsetzen(neu) {
      pr.punkte = pr.punkte.map((x) => (x.id === neu.id ? neu : x));
      const el = $(`#pp-${neu.id}`);
      if (!el) { abschlussAktualisieren(); return; }
      const aktiv = el.contains(document.activeElement) ? document.activeElement : null;
      let fokusSel = null;
      if (aktiv) {
        if (aktiv.classList.contains("mat-pnotiz")) fokusSel = ".mat-pnotiz";
        else if (aktiv.classList.contains("mat-pwert")) fokusSel = ".mat-pwert";
        else if (aktiv.classList.contains("mat-pnummer")) fokusSel = `#${aktiv.id}`;
        else if (aktiv.matches("input[data-foto]")) fokusSel = aktiv.hasAttribute("capture") ? "input[data-foto][capture]" : "input[data-foto]:not([capture])";
        else if (aktiv.dataset.act) fokusSel = `[data-act="${aktiv.dataset.act}"]${aktiv.dataset.wert ? `[data-wert="${aktiv.dataset.wert}"]` : ""}${aktiv.dataset.befund ? `[data-befund="${aktiv.dataset.befund}"]` : ""}`;
      }
      const tippen = aktiv && (fokusSel === ".mat-pnotiz" || fokusSel === ".mat-pwert" || aktiv.classList.contains("mat-pnummer")) ? { wert: aktiv.value, von: aktiv.selectionStart, bis: aktiv.selectionEnd } : null;
      const notizAlt = $(".mat-pnotiz", el);
      const notizOffen = notizAlt && !notizAlt.hidden;
      ersetzt = true;
      try { el.outerHTML = punktHtml(neu); } finally { ersetzt = false; }
      const karte = $(`#pp-${neu.id}`);
      doppeltePruefen(karte.closest(".mat-punkte"));
      const notiz = $(".mat-pnotiz", karte);
      if (notiz && notizOffen && notiz.hidden) { notiz.hidden = false; const plus = $('[data-act="pnotiz-auf"]', karte); if (plus) plus.remove(); }
      // Noch nicht Bestätigtes aus einem anderen Feld der Karte (die Antwort einer anderen Anfrage kennt es nicht).
      ["wert", "notiz"].forEach((feld) => {
        const e = felder.get(`${neu.id}:${feld}`);
        const f = $(feld === "notiz" ? ".mat-pnotiz" : ".mat-pwert", karte);
        if (!e || !f || e.wert === e.bestaetigt || f.value === anzeige(f, e.wert) || (tippen && fokusSel === (feld === "notiz" ? ".mat-pnotiz" : ".mat-pwert"))) return;
        f.value = anzeige(f, e.wert);
        if (f.hidden) { f.hidden = false; const plus = $('[data-act="pnotiz-auf"]', karte); if (plus) plus.remove(); }
      });
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
          // Gesetzter Text löst beim Verlassen kein „change“ aus – Gerettetes speichert das Verlassen (focusout in binden).
        }
      }
      abschlussAktualisieren();
    }

    async function punktSetzen(rid, body) {
      try { punktErsetzen((await merken(punktAnfrage(rid, () => api(`${API}/pruefungen/${pr.id}/punkte/${rid}`, { method: "PUT", body })))).punkt); }
      catch (e) { toast(e.message, true); }
    }

    function binden() {
      if (gebunden) return;
      gebunden = true;
      const TEXT = ".mat-pwert, .mat-pnotiz, #pr-bem";
      // Beim Tippen vormerken (geht nach TIPP_MS), beim Verlassen sofort – Datumsfelder erst mit „change“ (halb getippt
      // ist noch kein Datum).
      inhalt.addEventListener("input", (e) => {
        if (bearbeitbar() && e.target.matches(TEXT) && !e.target.classList.contains("mat-datum")) vormerken(schluessel(e.target), e.target.value);
        if (bearbeitbar() && (e.target.id === "pr-grund" || e.target.id === "pr-due")) abschlussMerken();
      });
      window.addEventListener("resize", () => { if (bearbeitbar()) grundPlatzhalter(); });
      inhalt.addEventListener("focusout", (e) => {
        const el = e.target;
        setTimeout(() => tipptPruefen(true), 0);
        if (ersetzt || !bearbeitbar() || !el.matches || !el.matches(TEXT) || !el.isConnected) return;
        const k = schluessel(el);
        const wert = feldWert(el, false);          // ungültiges Datum: „change“ hat es schon gesagt
        if (wert === null) return;
        eintrag(k).wert = wert;
        senden(k, true);
      });
      inhalt.addEventListener("focusin", () => tipptPruefen(true));
      const groesse = () => tipptPruefen(false);
      window.addEventListener("resize", groesse);
      if (window.visualViewport) window.visualViewport.addEventListener("resize", groesse);
      // Wer die Seite verlässt oder wegschaltet: Ausstehendes sofort (die Anfrage trägt keepalive). Was gerade
      // unterwegs ist, kommt ebenso an; was danach noch fehlt, liegt im Fenster und wird beim nächsten Laden nachgetragen.
      const jetzt = () => felder.forEach((e, k) => { if (!e.unterwegs && e.wert !== e.bestaetigt) senden(k); });
      window.addEventListener("pagehide", jetzt);
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") jetzt(); });
      window.addEventListener("online", jetzt);
      inhalt.addEventListener("change", async (e) => {
        if (!bearbeitbar()) return;
        const el = e.target;
        // Seriennummern der Bestandteile: alle Stück der Zeile auf einmal, beim Verlassen des Feldes (Schritt 25).
        if (el.matches(".mat-pnummer")) {
          const karte = el.closest(".mat-punkt");
          await punktSetzen(el.dataset.rid, { seriennummern: $$(".mat-pnummer", karte).map((f) => f.value.trim()) });
          return;
        }
        if (el.matches(TEXT)) {
          const k = schluessel(el);
          const wert = feldWert(el, true);
          if (wert === null) return;
          eintrag(k).wert = wert;
          await senden(k, true);
          return;
        }
        if (el.matches("input[data-foto]")) {
          const f = el.files[0];
          if (!f) return;
          const fd = new FormData(); fd.append("file", f);
          const karte = el.closest(".mat-punkt");
          if (karte) karte.classList.add("laedt");
          try { punktErsetzen((await merken(punktAnfrage(el.dataset.foto, () => api(`${API}/pruefungen/${pr.id}/punkte/${el.dataset.foto}/foto`, { method: "POST", body: fd })))).punkt); toast("Foto gespeichert"); }
          catch (err) { toast(err.message, true); if (karte) karte.classList.remove("laedt"); }
          return;
        }
        if (el.id === "pr-art") {
          try {
            pr = (await api(`${API}/pruefungen/${pr.id}`, { method: "PUT", body: { art: el.value } })).pruefung;
            $("h1", inhalt).firstChild.textContent = `${PRUEFART[pr.art] || pr.art} `;
            toast("Prüfart geändert");
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
      /* Gemeldete Mängel (Phase 3 · L1): Mit „einsatzbereit“ hakt der Prüfer jede offene Meldung einzeln ab – erst dann ist
         „Festschreiben“ frei, und nur die abgehakten gehen als maengel_gesehen mit. Eine Berichtigung gibt bei offener
         Meldung ohnehin nicht frei (der Server sagt es); „instandsetzen“ und „aussondern empfohlen“ brauchen kein Häkchen. */
      const zuHaken = daten.ergebnis === "einsatzbereit" && !pr.berichtigt ? (pr.maengel || []) : [];
      delete daten.maengel_gesehen;
      dialog(`<h2>Prüfung festschreiben</h2>
        <dl class="mat-daten mat-fs-daten">
          <dt>Artikel</dt><dd><strong>${esc(a.inventory_no)}</strong> · ${nameHtml(pr.produkt)}${zusatzHtml(pr.produkt)}</dd>
          <dt>Prüfung</dt><dd>${esc(PRUEFART[pr.art] || pr.art)} am ${esc(fmtTag(pr.prueftag || isoHeute()))}</dd>
          <dt>Ergebnis</dt><dd>${ergebnisMarke(daten.ergebnis)}${maengel ? ` <span class="small">mit ${plural(maengel, "Mangel", "Mängeln")}</span>` : ""}</dd>
          ${daten.ergebnis === "einsatzbereit" ? `<dt>Nächste Prüfung</dt><dd><strong>${esc(fmtTag(daten.next_due_on || pr.vorschlag_naechste))}</strong></dd>` : ""}
          ${daten.grund ? `<dt>Grund</dt><dd>${esc(daten.grund)}</dd>` : ""}
          <dt>Prüfer</dt><dd>${person(pr.pruefer || "–")}${pr.urkunde ? ` · <span class="mat-ganz">Urkundennummer ${esc(pr.urkunde)}</span>` : ""}</dd>
          <dt>Unterschrift</dt><dd id="fs-us">${usZeile(bild)}</dd>
        </dl>
        ${zuHaken.length ? `<fieldset class="mat-fs-maengel"><legend>Gemeldete Mängel</legend>
          ${zuHaken.map((m) => `<div class="mat-fs-mangel"><label class="inline"><input type="checkbox" data-mangel="${Number(m.id)}">
            Gemeldeten Mangel vom ${esc(S.fmtDate(m.created_at))} geprüft</label>
            ${m.description ? `<p class="small mat-text">${esc(m.description.length > 300 ? `${m.description.slice(0, 299)}…` : m.description)}</p>` : ""}</div>`).join("")}
          <p class="help" id="fs-maengel-hilfe">Freigeben kannst du erst, wenn du jeden gemeldeten Mangel geprüft hast.</p></fieldset>` : ""}
        ${daten.ergebnis === "aussondern_empfohlen" ? "<p>Der Artikel wird gesperrt und wandert nach „Gesperrt“. Deine Empfehlung steht im Protokoll und am Artikel – aussondern kann danach der Materialwart.</p>" : ""}
        ${pr.berichtigt ? `<p>Diese Berichtigung ersetzt ${pr.berichtigt.protokoll_id ? `Protokoll ${esc(pr.berichtigt.protokoll_id)}` : "die ursprüngliche Prüfung"}; das Original bleibt unverändert erhalten.</p>` : ""}
        <p class="help">Danach ist die Prüfung unveränderlich; eine Korrektur geht nur als Berichtigung. Das Protokoll entsteht mit Prüfsumme.</p>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="fs-ok" type="button">Festschreiben</button></div>`,
      (dlg, body) => {
        const knopf = $("#fs-ok", body);
        const haken = $$("input[data-mangel]", body);
        const alleAbgehakt = () => haken.every((h) => h.checked);
        const knopfFrei = () => { knopf.disabled = !alleAbgehakt(); };
        haken.forEach((h) => h.addEventListener("change", knopfFrei));
        knopfFrei();
        fokus(haken.length ? haken[0] : knopf);
        let erneut = false;          // nach einem 403 wegen fehlender Unterschrift genau einmal von selbst weiter
        async function festschreiben() {
          if (!DARF.unterschrift) {
            if (!(await eigeneUnterschrift(HINWEIS_WEG))) return;          // abgebrochen: der Dialog bleibt offen
            $("#fs-us", body).innerHTML = usZeile(eigenesBildMerk);
            abschlussAktualisieren();
          }
          if (!alleAbgehakt()) { toast("Freigeben kannst du erst, wenn du jeden gemeldeten Mangel geprüft hast.", true); return; }
          if (haken.length) daten.maengel_gesehen = haken.filter((h) => h.checked).map((h) => +h.dataset.mangel);
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
            if (e.status === 409 && (e.message.startsWith(MANGEL_NEU_ANFANG) || e.message.startsWith(LAENGE_GEAENDERT_ANFANG))) {
              // Inzwischen ist ein Mangel gemeldet worden: neu laden – er erscheint oben und hier mit eigenem Häkchen.
              // Ebenso, wenn jemand die Länge am Artikel geändert hat: Der Längenpunkt zeigt danach die neue Länge
              // (ein eigener Messwert bleibt), der Prüfer bestätigt und schreibt erneut fest.
              dlg.close();
              try { pr = (await api(`${API}/pruefungen/${pr.id}`)).pruefung; zeichnen(); } catch (err) { /* bleibt so */ }
              toast(e.message, true);
              return;
            }
            knopf.disabled = false;
            knopfFrei();
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
          speichern: async (bild) => { punktErsetzen((await merken(punktAnfrage(x.id, () => api(`${API}/pruefungen/${pr.id}/punkte/${x.id}`, { method: "PUT", body: { unterschrift: bild } })))).punkt); } });
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
        // Wie beim Anhang und bei der Unterschrift erst nachfragen – beim Mangel ist das Foto der Beleg.
        const x = punkt(+b.dataset.rid);
        const frage = x && x.befund === "mangel" ? "Das Foto zu diesem Mangel entfernen? Ohne Foto lässt sich die Prüfung nicht festschreiben."
          : "Dieses Foto entfernen?";
        if (!(await confirm(frage, "Entfernen"))) return;
        try { punktErsetzen((await punktAnfrage(b.dataset.rid, () => api(`${API}/pruefungen/${pr.id}/punkte/${b.dataset.rid}/foto`, { method: "DELETE" }))).punkt); }
        catch (e) { toast(e.message, true); }
      },
      // Wenig Höhe: Der Hinweis in der Leiste steht in einer Zeile – antippen zeigt ihn ganz.
      "hinweis-ganz": (h) => { h.classList.toggle("ganz"); },
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
      ergebnis: (b) => {
        if (b.disabled) return;
        ergebnis = ergebnis === b.dataset.e ? null : b.dataset.e;
        abschlussAktualisieren(); abschlussMerken();
        if (ergebnis && ergebnis !== "einsatzbereit") fokus(imAbschluss("#pr-grund"));
      },
      festschreiben: async (b) => {
        if (!ergebnis) return;
        // Was der Server sicher ablehnt, gleich hier sagen – bevor nach der Unterschrift gefragt wird. Vorher alles
        // Getippte schicken und abwarten; was nicht ankam (kein Netz), hält das Festschreiben auf.
        const ungespeichert = await allesGesendet();
        if (ungespeichert.length) {
          const fehler = felder.get(ungespeichert[0]).fehler;
          toast(`Noch nicht gespeichert${fehler ? ` (${fehler})` : ""} – bitte prüfen und noch einmal festschreiben.`, true);
          fokus(feldVon(ungespeichert[0]));
          return;
        }
        const h = offeneHinweise();
        const grund = ergebnis === "einsatzbereit" ? "" : imAbschluss("#pr-grund").value.trim();
        if (h.offen.length) { toast("Noch ohne Befund: " + h.offen.slice(0, 5).map((x) => x.text).join("; "), true); return; }
        if (h.ohneFoto.length) { toast("Jeder Mangel braucht ein Foto – es fehlt bei: " + h.ohneFoto.slice(0, 5).map((x) => x.text).join("; "), true); return; }
        if (h.ohneNotiz.length) {
          toast("Jeder Mangel braucht eine Bemerkung – sie fehlt bei: " + h.ohneNotiz.slice(0, 5).map((x) => x.text).join("; "), true);
          fokus($(`#pp-${h.ohneNotiz[0].id} .mat-pnotiz`)); return;
        }
        if (ergebnis !== "einsatzbereit" && !h.maengel.length && !grund) { toast(`Ohne Mangel braucht „${ERGEBNIS[ergebnis]}“ einen Grund.`, true); fokus(imAbschluss("#pr-grund")); return; }
        // „Nächste Prüfung“: ein Tippfehler bricht ab (vorher wurde daraus still „spätestens“ – S20); die Grenzen
        // prüft der Server noch einmal.
        let due = null;
        if (ergebnis === "einsatzbereit") {
          try { due = datumWert(imAbschluss("#pr-due"), "Nächste Prüfung") || null; }
          catch (e) { toast(e.message, true); fokus(imAbschluss("#pr-due")); return; }
          if (due && (due < isoHeute(1) || (pr.vorschlag_naechste && due > pr.vorschlag_naechste))) {
            toast(`„Nächste Prüfung“: frühestens ${fmtTag(isoHeute(1))}${pr.vorschlag_naechste ? `, spätestens ${fmtTag(pr.vorschlag_naechste)}` : ""} – vorziehen geht, verschieben nicht.`, true);
            fokus(imAbschluss("#pr-due")); return;
          }
        }
        b.disabled = true;
        try {
          if (!(await eigeneUnterschrift(HINWEIS_FEST))) return;
          abschlussAktualisieren();
          await laufend.catch(() => {});
          const daten = { ergebnis, grund, bemerkung: bemFeld().value };
          if (ergebnis === "einsatzbereit") daten.next_due_on = due;
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
            try { const r = await api(`${API}/pruefungen/${pr.id}/berichtigen`, { method: "POST", body: { grund } }); location.href = `/materialablage/pruefung/${r.pruefung.id}`; }
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
        try { await api(`${API}/pruefungen/${pr.id}`, { method: "DELETE" }); vergessen(); location.href = b ? `/materialablage/pruefung/${b.id}` : `/materialablage/artikel/${pr.item_id}`; }
        catch (e) { toast(e.message, true); }
      },
      freigeben: () => reservierungFreigeben(pr.id, pr.pruefer, async () => { location.href = `/materialablage/artikel/${pr.item_id}`; }),
    };
    await aussonderungLaden();
    zeichnen();
    if (bearbeitbar()) nachtragen();
  }

  /* --- Prüfdurchgang ---------------------------------------------------------------------------------- */
  const DURCHGANG_SORT = [["Inventar-Nr.", "inventar"], ["Hersteller", "hersteller"], ["Produkt", "produkt"], ["Ablage", "ablage"],
                          ["Stand", "stand"], ["Status", "status"]];
  async function durchgangAnsicht() {
    let filter = "";
    let d = null;
    let sort = { feld: null, richtung: "auf" };
    // Der Durchgang kommt als Ganzes – hier sortiert der Browser selbst.
    const ZUSTAND_REIHE = { in_pruefung: 0, offen: 1, nicht_geprueft: 1, ausgenommen: 2, erledigt: 3 };
    const STATUS_RANG = { ueberfaellig: 0, lebensdauer: 1, neu: 2, gesperrt: 3, bald_faellig: 4, einsatzbereit: 5, ausgesondert: 6 };
    const SORTWERT = {
      inventar: (a) => a.inventory_no, hersteller: (a) => (a.manufacturer || "").toLowerCase(), produkt: (a) => (a.model || "").toLowerCase(),
      ablage: (a) => (a.pfad || "").toLowerCase(), stand: (a) => ZUSTAND_REIHE[a.zustand], status: (a) => STATUS_RANG[a.status] ?? 9,
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
    async function laden() { d = (await Promise.all([api(`${API}/durchgaenge/${DATEN.id}`), ordnerBaum().catch(() => null)]))[0].durchgang; }
    // Liegt ein freier Artikel noch im Zweig des Durchgangs? Wer ihn hinausverschoben hat, kann ihn nicht wieder
    // einbeziehen (Bauentwurf 1.7 Nr. 6) – der Knopf entfällt. Ohne geladenen Baum (oder bei gesperrten): ja.
    function imZweig(a) {
      if (a.lock_state !== "frei" || !baumIndex[a.folder_id]) return true;
      const gesehen = new Set();
      for (let o = baumIndex[a.folder_id]; o && !gesehen.has(o.id); o = baumIndex[o.parent_id]) {
        if (o.id === d.folder_id) return true;
        gesehen.add(o.id);
      }
      return false;
    }
    /* Eine Zeile je Artikel. Knöpfe nach dem, was das Konto am Durchgang (d.darf) und am Artikel (a.darf) darf. Einen
       Artikel, der aus dem Bereich des Durchgangs verschoben wurde und den das Konto nicht sieht („sichtbar“: false),
       zeigt die Liste ohne Link und ohne Knöpfe – mit Nummer, Produkt, Stand und dem Grund der Ausnahme. */
    function zeile(a) {
      const darf = d.offen && Boolean(d.darf && (d.darf.verwalten || d.darf.pruefen));
      const ad = a.darf || {};
      const sichtbar = a.sichtbar !== false;
      let zustand;
      let knopf = "";
      if (a.zustand === "erledigt") {
        const wann = `${esc(fmtTag(a.pruefung.datum))}, ${person(a.pruefung.pruefer)}`;
        zustand = `${ergebnisMarke(a.pruefung.ergebnis)} ${a.pruefung.id ? `<a class="small" href="/materialablage/pruefung/${a.pruefung.id}">${wann}</a>` : `<span class="small">${wann}</span>`}`;
      } else if (a.zustand === "ausgenommen") {
        zustand = `<span class="badge grey">ausgenommen</span> <span class="small">${esc(a.ausnahme.grund)}</span> <span class="muted small">(${esc(a.ausnahme.von || "")})</span>`;
        if (darf && sichtbar && a.lock_state !== "ausgesondert" && imZweig(a)) knopf = `<button type="button" class="btn secondary small" data-act="einbeziehen" data-id="${a.id}">Einbeziehen</button>`;
      } else if (a.zustand === "nicht_geprueft") {
        zustand = '<span class="badge grey">nicht geprüft</span>';
      } else if (a.zustand === "in_pruefung") {
        zustand = `<span class="badge">in Prüfung</span>${a.entwurf ? ` <span class="small">bei ${person(a.entwurf.pruefer)} seit ${esc(fmtZeit(a.entwurf.seit))}</span>` : ""}`;
        if (a.entwurf && a.entwurf.eigen && ad.pruefen) knopf = `<a class="btn secondary small" href="/materialablage/pruefung/${a.entwurf.id}">Weiter prüfen</a>`;
        else if (a.entwurf && ad.verwalten && d.offen) knopf = `<button type="button" class="btn secondary small" data-act="freigeben" data-id="${a.entwurf.id}" data-wer="${esc(a.entwurf.pruefer)}">Reservierung aufheben</button>`;
      } else {
        zustand = '<span class="muted">offen</span>';
        if (sichtbar && d.offen && ad.pruefen && a.lock_state !== "ausgesondert") {
          knopf = `<a class="btn secondary small" href="/materialablage/artikel/${a.id}/pruefung/neu?durchgang=${d.id}">Prüfen</a>`;
        }
        if (sichtbar && darf) knopf += `<button type="button" class="btn secondary small" data-act="ausnehmen" data-id="${a.id}" data-nr="${esc(a.inventory_no)}">Ausnehmen</button>`;
      }
      const nummer = sichtbar ? `<a class="mat-inv" href="/materialablage/artikel/${a.id}"><strong>${esc(a.inventory_no)}</strong></a>`
        : `<strong class="mat-inv">${esc(a.inventory_no)}</strong><div class="small muted">nicht in deinem Bereich</div>`;
      // Enge Tabelle: Hersteller und Ablage stehen klein beim Produkt; Karte: Inventar-Nr. und Status oben (Lieferung 5).
      return `<tr class="z-${a.zustand}${sichtbar ? "" : " mat-fremd"}"><td data-l="Inventar-Nr." class="mat-k-titel">${nummer}</td>
        <td data-l="Hersteller" class="mat-schmal-weg">${esc(a.manufacturer || "")}</td>
        <td data-l="Produkt" class="mat-k-ohne">${a.manufacturer ? `<div class="mat-schmal-zusatz small muted">${esc(a.manufacturer)}</div>` : ""}${produktZelle(a, sichtbar)}${a.serial_no ? `<div class="small muted">SN ${esc(a.serial_no)}</div>` : ""}
          <div class="mat-eng-zusatz small muted">${esc(a.pfad)}</div></td>
        <td data-l="Ablage" class="mat-eng-weg">${esc(a.pfad)}</td><td data-l="Stand">${zustand}</td><td data-l="Status" class="mat-k-marke">${a.status ? statusMarke(a.status) : '<span class="muted">–</span>'}${empfohlenMarke(a.aussonderung_empfohlen)}</td>
        <td class="tabelle-aktionen">${knopf}</td></tr>`;
    }
    function zeichnen() {
      leisteMarkieren(d.folder_id);
      const z = d.zaehlung;
      const darf = Boolean(d.darf && (d.darf.verwalten || d.darf.pruefen));
      // Ausgegrautes „Durchgang abschließen“: der Grund mit Zahl im Satz über der Liste, am Knopf per aria-describedby
      // (Browserprüfung vor dem Merge, Verbesserung 4).
      const rest = (z.offen || 0) + (z.in_pruefung || 0);
      const liste = sortiert(d.artikel.filter((a) => !filter || a.zustand === filter));
      const s = sort;
      // Laufend: offen, in Prüfung, erledigt, ausgenommen. Vorbei: erledigt, ausgenommen – nach einem Abbruch
      // dazu „nicht geprüft“.
      const zustaende = d.offen ? [["", "alle"], ["offen", "offen"], ["in_pruefung", "in Prüfung"], ["erledigt", "erledigt"], ["ausgenommen", "ausgenommen"]]
        : [["", "alle"], ["erledigt", "erledigt"], ["ausgenommen", "ausgenommen"]].concat(z.nicht_geprueft ? [["nicht_geprueft", "nicht geprüft"]] : []);
      seitenTitel(d.titel);
      // Ein beendeter Durchgang steht unter „Abgeschlossene Prüfdurchgänge“ – die Brotkrume führt dorthin zurück.
      inhalt.innerHTML = `<div class="mat-pfad">${pfadHtml(['<a href="/materialablage/pruefungen">Prüfungen</a>', d.offen ? "" : '<a href="/materialablage/durchgaenge">Abgeschlossene Prüfdurchgänge</a>', "<span>Prüfdurchgang</span>"])}</div>
        <div class="page-head"><h1>${esc(d.titel)} ${d.offen ? '<span class="badge">offen</span>' : `<span class="badge grey">${d.abgebrochen ? "abgebrochen" : "abgeschlossen"}</span>`}</h1>
          <div class="btn-row">${d.offen && darf ? `<button class="btn secondary" data-act="abbrechen">Durchgang abbrechen</button>
            <button class="btn" data-act="schliessen" ${d.abschliessbar ? "" : 'disabled aria-describedby="dg-abschluss"'}>Durchgang abschließen</button>` : ""}
            ${!d.offen && (d.set_protokolle || []).length ? `<a class="btn secondary" href="/materialablage/durchgang/${d.id}/protokolle.zip">Alle Protokolle (ZIP)</a>` : ""}</div></div>
        <p>Ordner <a href="/materialablage/ordner/${d.folder_id}">${esc(d.ordner)}</a> · eröffnet ${esc(fmtTag(d.eroeffnet_am))} von ${person(d.eroeffnet_von || "–")}
          ${d.offen ? "" : ` · ${d.abgebrochen ? "abgebrochen" : "abgeschlossen"} ${esc(fmtTag(d.geschlossen_am))} von ${person(d.geschlossen_von || "–")}`}</p>
        ${d.protokoll ? `<section class="section mat-protokoll"><div class="abschnittskopf"><h2>Sammelprotokoll</h2>
          ${d.offen ? "" : `<a class="btn secondary small" href="${esc(d.protokoll.url)}" target="_blank" rel="noopener" title="Sammelprotokoll ${esc(d.protokoll.id)} öffnen">Protokoll (PDF)</a>`}</div>
          <p class="mat-protokoll-zeile"><strong class="mat-hash">${esc(d.protokoll.id)}</strong> · festgeschrieben ${esc(fmtZeit(d.protokoll.festgeschrieben))}
          · Prüfsumme${infoKnopf("Prüfsumme", (d.set_protokolle || []).length ? 'Die Prüfsumme steht im Fuß jeder Seite des PDFs, ebenso in jedem Set-Protokoll. Ob eine Datei unverändert ist, zeigt die <a href="/materialablage/pruefen">Prüfseite</a>.' : PRUEFSUMME_INFO)}
          <span class="small muted">SHA-256 (erste ${esc(d.protokoll.bytes)} Bytes)</span> ${summeKnopf(d.protokoll.sha256)}</p></section>`
          : d.offen ? "" : '<p class="small muted">Vor Einführung des Festschreibens geschlossen – ohne Sammelprotokoll.</p>'}
        ${(d.set_protokolle || []).length ? `<section class="section"><h2>Set-Protokolle</h2>${setProtokolleHtml(d.set_protokolle)}</section>` : ""}
        <div class="mat-kachelrahmen"><div class="mat-kacheln mat-rundenzahlen">${zustaende.map(([k, t]) => `<div class="mat-kachel z-${k || "gesamt"}"><strong>${z[k || "gesamt"]}</strong><span>${k ? t : "Artikel"}</span></div>`).join("")}</div></div>
        <p>${fortschritt(z)}</p>
        ${d.offen ? `<p class="help" id="dg-abschluss">${d.abschliessbar || !rest ? "" : `<strong>Noch ${plural(rest, "Artikel", "Artikel")} offen oder in Prüfung.</strong> `}Jeder öffnet seinen Artikel mit „Prüfen“ und reserviert ihn damit – die anderen sehen „in Prüfung bei …“. Abschließen geht, sobald jeder Artikel geprüft oder mit Grund ausgenommen ist. Beim Abschließen entsteht das Sammelprotokoll mit allen Prüfern${d.set_ordner && d.set_ordner.anzahl ? ` – dazu für jedes Set mit geprüften Artikeln ein eigenes Set-Protokoll (hier bis zu ${d.set_ordner.anzahl}; Sets mit Geprüftem bisher: ${d.set_ordner.mit_pruefung})` : ""}.</p>` : ""}
        <div class="c-tabs mat-filter">${zustaende.map(([f, t]) => `<button type="button" data-act="filter" data-f="${f}" class="${f === filter ? "sel" : ""}">${esc(t)}${f ? ` (${z[f]})` : ""}</button>`).join("")}</div>
        ${liste.length ? `${kartenKopf(DURCHGANG_SORT, s)}<table class="list mat-tabelle mat-karten mat-runde"><thead><tr>${sortKopf("Inventar-Nr.", "inventar", s)}${sortKopf("Hersteller", "hersteller", s, { klasse: "mat-schmal-weg" })}${sortKopf("Produkt", "produkt", s, { vor: kopfZusatz("Hersteller", "hersteller", s, "schmal"), nach: kopfZusatz("Ablage", "ablage", s, "eng") })}${sortKopf("Ablage", "ablage", s, { klasse: "mat-eng-weg" })}${sortKopf("Stand", "stand", s)}${sortKopf("Status", "status", s)}<th></th></tr></thead><tbody>${liste.map(zeile).join("")}</tbody></table>` : leer("Keine Artikel in dieser Auswahl.")}
        ${d.pruefer.length ? `<section class="section"><h2>Prüfer in diesem Durchgang</h2><ul>${d.pruefer.map((x) => `<li>${person(x.name)}${x.urkunde ? ` · <span class="mat-ganz">Urkundennummer ${esc(x.urkunde)}</span>` : ""} – ${plural(x.anzahl, "Prüfung", "Prüfungen")}</li>`).join("")}</ul></section>` : ""}`;
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
        const sets = d.set_ordner ? d.set_ordner.mit_pruefung : 0;
        const fest = sets ? `Das Sammelprotokoll mit allen Prüfern und ${plural(sets, "Set-Protokoll", "Set-Protokolle")} werden festgeschrieben.` : "Das Sammelprotokoll mit allen Prüfern wird festgeschrieben.";
        if (!(await confirm(`Den Durchgang „${d.titel}“ abschließen? Danach lässt sich darin nichts mehr prüfen oder ausnehmen. ${fest}`, "Abschließen"))) return;
        b.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge/${d.id}/abschliessen`, { method: "POST", body: {} });
          const n = r.durchgang && r.durchgang.set_protokolle ? r.durchgang.set_protokolle.length : 0;
          toast(r.durchgang && r.durchgang.protokoll ? `Durchgang abgeschlossen – Sammelprotokoll ${r.durchgang.protokoll.id}${n ? ` und ${plural(n, "Set-Protokoll", "Set-Protokolle")}` : ""}` : "Durchgang abgeschlossen");
          await neu();
        } catch (e) { toast(e.message, true); b.disabled = false; }
      },
      abbrechen: async (b) => {
        const z = d.zaehlung;
        const weiter = z.in_pruefung ? " Offene Prüfungen darin laufen als einzelne Prüfungen weiter." : "";
        // Set-Protokolle entstehen nur beim Abschluss (F2 b) – das sagt die Rückfrage, sobald Sets im Durchgang sind.
        const sets = z.erledigt && d.set_ordner && d.set_ordner.anzahl ? " Set-Protokolle entstehen dabei keine – nur beim Abschließen." : "";
        const text = z.erledigt
          ? `Den Durchgang „${d.titel}“ abbrechen? Er endet ohne Abschluss: ${z.erledigt} geprüft, ${z.ausgenommen} ausgenommen, ${z.offen + z.in_pruefung} nicht geprüft. Was geprüft ist, bleibt dokumentiert – das Sammelprotokoll wird mit diesem Stand festgeschrieben.${sets}`
          : `Den Durchgang „${d.titel}“ abbrechen? Darin ist noch nichts geprüft – er wird ganz entfernt.`;
        if (!(await confirm(text + weiter, "Durchgang abbrechen", "Zurück"))) return;
        b.disabled = true;
        try {
          const r = await api(`${API}/durchgaenge/${d.id}/abbrechen`, { method: "POST", body: {} });
          if (!r.durchgang) { location.href = "/materialablage/pruefungen"; return; }
          filter = "";
          toast(r.durchgang.protokoll ? `Durchgang abgebrochen – Sammelprotokoll ${r.durchgang.protokoll.id}` : "Durchgang abgebrochen"); await neu();
        } catch (e) { toast(e.message, true); b.disabled = false; }
      },
    };
    await neu();
  }

  /* --- Produktmeldungen ------------------------------------------------------------------------------
     Wer Artikel anlegt, meldet Produkte, die im Katalog fehlen (Links, Fotos, Bemerkung). Die Material-Verwaltung
     legt sie an (Produktdialog mit den Angaben der Meldung), ordnen ein vorhandenes zu oder lehnen mit
     Begründung ab; der Melder bekommt jeweils eine Mail. */
  const MELDESTATUS = { offen: "offen", eingepflegt: "eingepflegt", abgelehnt: "abgelehnt" };
  const meldestatusMarke = (s) => `<span class="mat-mstatus m-${esc(s)}">${esc(MELDESTATUS[s] || s)}</span>`;
  const meldungName = (m) => `${m.manufacturer} ${m.model}`;
  const kurzLink = (u) => u.replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "");

  // notizTitel: Im Produktdialog („Produkt aus Meldung anlegen“) heißt die Bemerkung der Meldung „Bemerkung des
  // Melders“ – darunter steht das Feld „Bemerkung“ des Produkts (Wunsch vom 18.10.2026), zwei gleiche Wörter wären dort
  // nicht zu unterscheiden. In der Liste der Meldungen bleibt es „Bemerkung“ wie im Dialog „Fehlendes Produkt melden“.
  // Eine alte Set-Meldung (vor Schritt 26) nennt dazu schreibgeschützt die Teile, wie der Melder sie kannte.
  function meldeDetails(m, notizTitel = "Bemerkung") {
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    const daten = [m.set_teile ? zeile("Teile laut Meldung", `<span class="mat-text">${esc(m.set_teile)}</span>`) : "",
      m.article_no ? zeile("Artikelnummer", `<span class="mat-ganz">${esc(m.article_no)}</span>`) : "", m.norm ? zeile("Norm", esc(m.norm)) : "",
      m.kategorie ? zeile("Kategorie (Vorschlag)", esc(m.kategorie.pfad)) : "",
      m.links.length ? zeile("Links", m.links.map((l) => `<a href="${esc(l)}" target="_blank" rel="noopener noreferrer">${esc(kurzLink(l))}</a>`).join("<br>")) : "",
      m.note ? zeile(notizTitel, `<span class="mat-text">${esc(m.note)}</span>`) : ""].join("");
    return `${daten ? `<dl class="mat-daten mat-meldung-daten">${daten}</dl>` : ""}
      ${m.fotos.length ? `<div class="mat-meldung-fotos">${m.fotos.map((f) => bildLink(f.web, f.original, `Foto zur Meldung ${m.manufacturer || ""} ${m.model || ""}`.trim(), `meldung-${m.id}`, `<img src="${esc(f.vorschau)}" alt="Foto zur Meldung" loading="lazy">`)).join("")}</div>` : ""}`;
  }
  // Im Produktdialog: was der Melder wusste – zum Nachschlagen, während die Felder schon vorbelegt sind.
  // Für welchen Ordner gemeldet wurde: der Pfad, wenn das Konto den Ordner sieht – sonst nur die Gliederung (Phase 2).
  const meldeOrdner = (m) => (!m.ordner ? "" : m.ordner.pfad ? m.ordner.pfad : m.ordner.gliederung ? `Gliederung ${m.ordner.gliederung}` : "");
  const meldeKasten = (m) => `<div class="mat-meldekasten"><p class="small">Gemeldet von ${person(m.created_by_name || "–")} am ${esc(fmtTag(m.created_at))}${meldeOrdner(m) ? ` für ${esc(meldeOrdner(m))}` : ""}</p>${meldeDetails(m, "Bemerkung des Melders")}</div>`;

  // bearbeiten: die Material-Verwaltung in der Liste aller Meldungen – nur sie bekommt die Knöpfe zum Abarbeiten.
  function meldeKarte(m, bearbeiten) {
    const wer = (name) => (name ? ` von ${person(name)}` : "");
    const knoepfe = [];
    if (bearbeiten && m.status === "offen") {
      knoepfe.push(`<button type="button" class="btn secondary small" data-act="anlegen" data-id="${m.id}">Produkt anlegen</button>`,
                   `<button type="button" class="btn secondary small" data-act="zuordnen" data-id="${m.id}">Vorhandenes zuordnen</button>`,
                   `<button type="button" class="btn secondary small" data-act="ablehnen" data-id="${m.id}">Ablehnen</button>`);
    }
    if (m.eigen && DARF.verwalten && m.status === "eingepflegt" && m.produkt) {
      knoepfe.push(`<a class="btn secondary small" href="/materialablage/artikel/neu?produkt=${m.produkt.id}${m.ordner && m.ordner.id ? `&ordner=${m.ordner.id}` : ""}">Artikel davon anlegen</a>`);
    }
    // Eigene Meldungen löscht der Melder selbst – offen oder erledigt.
    if (m.eigen) knoepfe.push(`<button type="button" class="btn secondary small" data-act="loeschen" data-id="${m.id}">Löschen</button>`);
    return `<article class="mat-meldung m-${esc(m.status)}">
      <div class="mat-meldung-kopf"><h2>${esc(meldungName(m))}</h2>${meldestatusMarke(m.status)}</div>
      <p class="muted small">gemeldet${wer(m.created_by_name)} am ${esc(fmtTag(m.created_at))}${meldeOrdner(m) ? ` · für ${esc(meldeOrdner(m))}` : ""}</p>
      ${meldeDetails(m)}
      ${m.treffer ? `<p class="notice">Steht inzwischen im Katalog: <a href="/materialablage/katalog/produkt/${m.treffer.id}">${nameHtml(m.treffer)}</a>${zusatzHtml(m.treffer)}${artNrKurz(m.treffer.article_no)}
        ${bearbeiten ? `<button type="button" class="btn secondary small" data-act="treffer" data-id="${m.id}">Zuordnen</button>` : ""}</p>` : ""}
      ${m.status === "eingepflegt" ? `<p class="mat-meldung-ergebnis">Eingepflegt${wer(m.resolved_by_name)} am ${esc(fmtTag(m.resolved_at))}:
        ${m.produkt ? `<a href="/materialablage/katalog/produkt/${m.produkt.id}">${nameHtml(m.produkt)}</a>${zusatzHtml(m.produkt)}` : '<span class="muted">Produkt inzwischen gelöscht</span>'}
        ${m.answer ? `<br><span class="mat-text">${esc(m.answer)}</span>` : ""}</p>` : ""}
      ${m.status === "abgelehnt" ? `<p class="mat-meldung-ergebnis">Abgelehnt${wer(m.resolved_by_name)} am ${esc(fmtTag(m.resolved_at))}: <span class="mat-text">${esc(m.answer)}</span></p>` : ""}
      ${knoepfe.length ? `<div class="btn-row">${knoepfe.join("")}</div>` : ""}
    </article>`;
  }

  async function meldungen() {
    let filter = DATEN.status || null;
    let eigene = null;            // null: was der Server für die Rolle vorsieht; Materialwarte schalten zwischen „1“ und „0“
    // Nur noch Produktmeldungen (Wunsch vom 24.10.2026): Die Änderungsanträge haben ihre Seite im Bestand.
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
        : d.alle ? "Materialwarte melden hier Produkte, die ihnen beim Anlegen von Artikeln im Katalog fehlen; die Material-Verwaltung nimmt sie auf oder lehnt sie mit Begründung ab."
          : "Produkte, die du beim Anlegen von Artikeln als fehlend gemeldet hast. Du bekommst eine Mail, sobald die Material-Verwaltung sie bearbeitet hat.";
      seitenTitel(d.alle ? "Produktmeldungen" : "Deine Produktmeldungen");
      inhalt.innerHTML = `<div class="page-head"><h1>${d.alle ? "Produktmeldungen" : "Deine Produktmeldungen"}</h1>
          <div class="btn-row"><a class="btn secondary" href="/materialablage/katalog">Katalog</a>${DARF.verwalten ? '<a class="btn secondary" href="/materialablage/artikel/neu"><span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Artikel<span class="k-anlegen"> anlegen</span></span></a>' : ""}</div></div>
        <p class="help">${hilfe}${DARF.verwalten && !DARF.katalog ? ` <button type="button" class="lnk" data-act="eigene">${d.alle ? "Nur deine zeigen" : "Alle Meldungen zeigen"}</button>` : ""}</p>
        <div class="c-tabs mat-filter" role="group" aria-label="Status">${[["offen", "offen"], ["erledigt", "erledigt"], ["alle", "alle"]].map(([w, t]) => `<button type="button" class="${w === filter ? "sel" : ""}" data-act="filter" data-f="${w}" aria-pressed="${w === filter}">${t}${w === "offen" && d.offen ? ` (${d.offen})` : ""}</button>`).join("")}</div>
        ${liste.length ? liste.map((m) => meldeKarte(m, d.bearbeiten)).join("") : leer(filter === "offen" ? "Keine offenen Meldungen." : "Keine Meldungen.")}`;
      aktionen = {
        filter: (b) => {
          filter = b.dataset.f;
          try { history.replaceState(null, "", `/materialablage/katalog/meldungen?status=${filter}`); } catch (e) { /* nur die Adresszeile */ }
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
          const folge = m.status === "offen" ? " Sie verschwindet damit auch bei der Material-Verwaltung."
            : m.status === "eingepflegt" ? " Das Produkt bleibt im Katalog." : "";
          if (!(await confirm(`Deine Meldung „${meldungName(m)}“ löschen?${folge}`, "Löschen"))) return;
          try { await api(`${API}/meldungen/${m.id}`, { method: "DELETE" }); toast("Meldung gelöscht"); await zeichnen(); }
          catch (e) { toast(e.message, true); }
        },
      };
    }
    await zeichnen();
  }

  /* --- Änderungsanträge im Bestand (Wunsch vom 24.10.2026) ---------------------------------------------------------
     Die eigenen Anträge und die, die das Konto als Materialwart des Ordners entscheidet (eigene Freigabe „verwalten“
     dort oder darüber – die Material-Verwaltung nur mit so einer Freigabe). Je Sammelantrag eine Karte; graue Knöpfe
     „Bestätigen“ und „Ablehnen“ nur, wenn das Konto entscheiden darf, „Zurückziehen“ am eigenen offenen – der rote
     Hauptknopf steht erst in der Rückfrage (Knopfregel). */
  async function antraegeSeite() {
    let filter = DATEN.status || null;
    leisteMarkieren(null);
    async function zeichnen() {
      const d = await api(`${API}/antraege${filter ? `?status=${filter}` : ""}`);
      filter = d.filter;
      const liste = d.antraege;
      const antrag = (b) => liste.find((x) => x.id === +b.dataset.id);
      seitenTitel("Änderungsanträge");
      inhalt.innerHTML = `<div class="page-head"><h1>Änderungsanträge${infoKnopf("Änderungsanträge", "Seit der ersten Prüfung stehen die Stammdaten eines Artikels fest – Materialwarte und Prüfer beantragen hier Änderungen mit Begründung, die Materialwarte des Ordners bestätigen oder lehnen ab.")}</h1>
          <div class="btn-row"><a class="btn secondary" href="/materialablage/bestand">Bestand</a></div></div>
        <div class="c-tabs mat-filter" role="group" aria-label="Status">${[["offen", "offen"], ["erledigt", "erledigt"], ["alle", "alle"]].map(([w, t]) => `<button type="button" class="${w === filter ? "sel" : ""}" data-act="filter" data-f="${w}" aria-pressed="${w === filter}">${t}${w === "offen" && d.zu_entscheiden ? ` (${d.zu_entscheiden} zu entscheiden)` : ""}</button>`).join("")}</div>
        ${liste.length ? liste.map(antragKarte).join("") : leer(filter === "offen" ? "Keine offenen Änderungsanträge." : "Keine Änderungsanträge.")}`;
      aktionen = {
        filter: (b) => {
          filter = b.dataset.f;
          try { history.replaceState(null, "", `/materialablage/bestand/antraege?status=${filter}`); } catch (e) { /* nur die Adresszeile */ }
          zeigen(zeichnen);
        },
        bestaetigen: (b) => antragBestaetigenDialog(antrag(b), zeichnen),
        "antrag-ablehnen": (b) => antragAblehnenDialog(antrag(b), zeichnen),
        "antrag-zurueck": (b) => antragZurueckziehen(antrag(b), zeichnen),
      };
    }
    await zeichnen();
  }

  const antragMarke = (st) => `<span class="mat-mstatus m-${esc(st)}">${esc(ANTRAG_STATUS[st] || st)}</span>`;
  function antragKarte(x) {
    const art = x.artikel;
    const wer = (name) => (name ? ` von ${person(name)}` : "");
    const offen = x.status === "offen";
    // Bestätigen geht nur, solange der Artikel alle alten Werte trägt, nicht ausgesondert ist und der Antrag nicht das
    // Herstelldatum leeren will (gibt es seit dem 21.10.2026 nicht mehr – ältere offene nur noch ablehnen).
    const geht = x.passt && !x.entfernen && art.lock_state !== "ausgesondert";
    const nurAblehnen = art.lock_state === "ausgesondert" ? "Der Artikel ist inzwischen ausgesondert – der Antrag lässt sich nur noch ablehnen."
      : x.entfernen ? "Ein Herstelldatum lässt sich nicht mehr entfernen – der Antrag lässt sich nur noch ablehnen."
        : "Der Artikel trägt inzwischen nicht mehr alle alten Werte – der Antrag lässt sich nur noch ablehnen.";
    const knoepfe = [x.entscheiden && geht ? `<button type="button" class="btn secondary small" data-act="bestaetigen" data-id="${x.id}">Bestätigen</button>` : "",
      x.entscheiden ? `<button type="button" class="btn secondary small" data-act="antrag-ablehnen" data-id="${x.id}">Ablehnen</button>` : "",
      x.eigen ? `<button type="button" class="btn secondary small" data-act="antrag-zurueck" data-id="${x.id}">Zurückziehen</button>` : ""].join("");
    return `<article class="mat-meldung mat-antrag m-${esc(x.status)}">
      <div class="mat-meldung-kopf"><h2><a href="/materialablage/artikel/${art.id}">${esc(art.inventory_no)}</a> <span class="mat-antrag-produkt">${nameHtml(art.produkt)}${zusatzHtml(art.produkt)}</span></h2>${antragMarke(x.status)}${art.demo ? ' <span class="badge grey">DEMO</span>' : ""}</div>
      <p class="muted small">Antrag Nr. ${x.id} · beantragt${wer(x.antragsteller)} am ${esc(S.fmtDate(x.created_at))}${art.pfad || art.gliederung ? ` · ${esc(art.pfad || art.gliederung)}` : ""}${x.eigen && x.entscheiden ? " · dein eigener Antrag" : ""}</p>
      ${antragAenderungen(x, offen)}
      <dl class="mat-daten mat-meldung-daten"><dt>Begründung</dt><dd><span class="mat-text">${esc(x.begruendung || "")}</span></dd></dl>
      ${offen ? antragRueckruf(x) : ""}
      ${offen && !geht ? `<p class="notice small">${nurAblehnen}</p>` : ""}
      ${offen && x.ohne_zustaendige ? '<p class="notice small">Dieser Ordner hat zurzeit keinen Materialwart mit Freigabe „verwalten“ – die Material-Verwaltung kann sich die Freigabe dort geben und dann entscheiden.</p>' : ""}
      ${x.status === "bestaetigt" ? `<p class="mat-meldung-ergebnis">Bestätigt${wer(x.entschieden_von)} am ${esc(S.fmtDate(x.resolved_at))}${x.antwort ? `: <span class="mat-text">${esc(x.antwort)}</span>` : ""}</p>` : ""}
      ${x.status === "abgelehnt" ? `<p class="mat-meldung-ergebnis">Abgelehnt${wer(x.entschieden_von)} am ${esc(S.fmtDate(x.resolved_at))}: <span class="mat-text">${esc(x.antwort || "")}</span></p>` : ""}
      ${x.status === "zurueckgezogen" ? `<p class="mat-meldung-ergebnis">Vom Antragsteller zurückgezogen am ${esc(S.fmtDate(x.resolved_at))}.</p>` : ""}
      ${offen && knoepfe ? `<div class="btn-row">${knoepfe}</div>` : ""}
    </article>`;
  }

  function antragBestaetigenDialog(x, danach) {
    const art = x.artikel;
    const folgen = (x.aenderungen || []).some((y) => ["product_id", "manufactured_on", "interval_months"].includes(y.feld));
    dialog(`<h2>Änderung bestätigen</h2>
      <p>${esc(art.inventory_no)} – ${nameHtml(art.produkt)}${zusatzHtml(art.produkt)}</p>
      ${antragAenderungen(x)}
      <p class="small">Beantragt von ${person(x.antragsteller || "–")} am ${esc(S.fmtDate(x.created_at))}: <span class="mat-text">${esc(x.begruendung || "")}</span></p>
      ${antragRueckruf(x)}
      <p class="help">Alle Änderungen stehen danach sofort am Artikel; Journal und Lebenslauf zeigen sie mit beiden Namen. Festgeschriebene Protokolle behalten die alten Werte.${folgen ? " Lebensende, Länge und nächste Prüfung ziehen nach." : ""}</p>
      <label for="ba-antwort">Anmerkung für den Antragsteller (optional, steht in seiner Mail)</label><textarea id="ba-antwort" rows="2" maxlength="1000"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ba-ok" type="button">Bestätigen</button></div>`,
    (dlg, body) => {
      $("#ba-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        try {
          await api(`${API}/antraege/${x.id}/bestaetigen`, { method: "POST", body: { antwort: $("#ba-antwort", body).value } });
          dlg.close(); toast(x.eigen ? "Bestätigt – die Änderung steht am Artikel." : "Bestätigt – der Antragsteller bekommt Bescheid."); await danach();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  function antragAblehnenDialog(x, danach) {
    const art = x.artikel;
    dialog(`<h2>Antrag ablehnen</h2>
      <p>${esc(art.inventory_no)}, beantragt von ${person(x.antragsteller || "–")}:</p>
      ${antragAenderungen(x)}
      <label for="aa-antwort">Begründung (Pflicht, bekommt der Antragsteller per Mail)</label>
      <textarea id="aa-antwort" rows="3" maxlength="1000" placeholder="z. B. Nummer auf dem Etikett stimmt mit der gespeicherten überein"></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn danger" id="aa-ablehnen" type="button">Ablehnen</button></div>`,
    (dlg, body) => {
      fokus($("#aa-antwort", body));
      $("#aa-ablehnen", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (!$("#aa-antwort", body).value.trim()) { toast("Bitte begründe die Ablehnung.", true); return; }
        knopf.disabled = true;
        try {
          await api(`${API}/antraege/${x.id}/ablehnen`, { method: "POST", body: { antwort: $("#aa-antwort", body).value } });
          dlg.close(); toast(x.eigen ? "Abgelehnt." : "Abgelehnt – der Antragsteller bekommt die Begründung."); await danach();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
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
          $("#zu-gewaehlt", body).innerHTML = `<strong>${nameHtml(gewaehlt)}</strong>${zusatzHtml(gewaehlt)}${artNrKurz(gewaehlt.article_no)}`;
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
      <p>„${esc(meldungName(m))}“, gemeldet von ${person(m.created_by_name || "–")}</p>
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
      // Nur Produktmeldungen – die Änderungsanträge zählt ihr Knopf im Bestand (antraegeZaehlen, Wunsch vom 24.10.2026).
      const n = (await api(`${API}/meldungen?status=offen`)).offen || 0;
      el.textContent = n > 99 ? "99+" : n;
      el.title = n ? plural(n, "offene Produktmeldung", "offene Produktmeldungen") : "";
      el.hidden = !n;
    } catch (e) { /* der Zähler ist Beiwerk */ }
  }

  // Die Blase am Knopf „Änderungsanträge“ im Bestand: offene, die das Konto als Materialwart des Ordners entscheidet.
  async function antraegeZaehlen(el) {
    if (!el) return;
    try {
      const n = (await api(`${API}/antraege?nur_zahl=1`)).zu_entscheiden || 0;     // nur die Zahl, nicht die Liste
      el.textContent = n > 99 ? "99+" : n;
      el.title = n ? `${plural(n, "offener Änderungsantrag", "offene Änderungsanträge")} zu entscheiden` : "";
      el.hidden = !n;
    } catch (e) { /* der Zähler ist Beiwerk */ }
  }

  /* Ein Produkt melden, das beim Anlegen eines Artikels im Katalog fehlt (seit dem Rückbau der Set-Funktion, Schritt 26,
     wieder nur ein Produkt). v: Vorbelegung (aus der Suche) und Ordner. Aus der Nacharbeit eines Bestandsimports
     (Phase 2 · L3) kommen dazu v.url (…/nacharbeit/melden – der Zielordner steht in der Adresse, kein folder_id) und
     v.angabe (die Produktangabe der Liste); vorbelegt sind dann Hersteller, Modell und Artikelnummer aus der Liste und
     seit dem 25.10.2026 die Bemerkung (v.note: Satz zum Import und die Bemerkungen der Zeilen). v.norm und v.category_id
     belegen Norm und Kategorie vor, wenn ein Aufrufer sie kennt (die Nacharbeit kennt sie nicht, Entscheidung F2). */
  async function meldungDialog(v, danach) {
    const kats = await kategorienLaden();
    dialog(`<h2>Fehlendes Produkt melden</h2>
      <p class="help">Die Material-Verwaltung nimmt es in den Katalog auf. Du bekommst eine Mail, sobald du Artikel davon anlegen kannst.</p>
      <div class="field-row"><div><label for="me-her">Hersteller</label><input type="text" id="me-her" maxlength="120" value="${esc(v.manufacturer || "")}" ${TASTATUR_NAME}></div>
        <div><label for="me-mod">Modell</label><input type="text" id="me-mod" maxlength="160" value="${esc(v.model || "")}" ${TASTATUR_NAME}></div></div>
      <div class="field-row"><div><label for="me-art">Artikelnummer des Herstellers</label><input type="text" id="me-art" maxlength="80" value="${esc(v.article_no || "")}" ${TASTATUR_NUMMER}><div class="help" id="me-art-hilfe"></div></div>
        <div><label for="me-norm">Norm</label><input type="text" id="me-norm" maxlength="200" placeholder="z. B. EN 362" value="${esc(v.norm || "")}" ${TASTATUR_NUMMER}></div></div>
      <label for="me-kat">Kategorie</label><select id="me-kat"><option value="">– weiß ich nicht –</option>${kategorieOptionen(kats, v.category_id || null)}</select>
      <label for="me-links">Links</label><textarea id="me-links" rows="3" ${TASTATUR_ADRESSE} placeholder="https://… – je Zeile eine Adresse: Herstellerseite, Gebrauchsanleitung, Händler"></textarea>
      <div class="mat-feldkopf">Fotos (bis zu 3)</div>${dateiKnopf("me-fotos", 'Fotos wählen', "image/*", true)}
      <div class="help">Etikett oder Typenschild – darauf stehen meist Hersteller, Modell, Norm und Herstelldatum.</div>
      <label for="me-note">Bemerkung</label><textarea id="me-note" rows="3" maxlength="2000" placeholder="Was hilft beim Einpflegen? z. B. Größe, Farbe, wo gekauft">${esc(v.note || "")}</textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="me-ok" type="button">Melden</button></div>`,
    (dlg, body) => {
      fokus($("#me-her", body));
      artikelnummerPruefen($("#me-art", body), $("#me-her", body), $("#me-art-hilfe", body), null);
      dateiKnopfVerdrahten(body, "me-fotos");
      $("#me-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        const fotos = Array.from($("#me-fotos", body).files);
        if (fotos.length > 3) { toast("Höchstens 3 Fotos.", true); return; }
        const fd = new FormData();
        const felder = { manufacturer: $("#me-her", body).value, model: $("#me-mod", body).value, article_no: $("#me-art", body).value,
                         norm: $("#me-norm", body).value, category_id: $("#me-kat", body).value,
                         links: $("#me-links", body).value, note: $("#me-note", body).value };
        if (v.url) felder.angabe = v.angabe || "";
        else felder.folder_id = v.folder_id || "";
        Object.entries(felder).forEach(([k, w]) => fd.append(k, w));
        fotos.forEach((f) => fd.append("fotos", f));
        knopf.disabled = true;
        try {
          await api(v.url || `${API}/meldungen`, { method: "POST", body: fd });
          dlg.close();
          toast("Gemeldet – du bekommst eine Mail, sobald du Artikel davon anlegen kannst.");
          if (danach) await danach();
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Rückrufe (Lieferung 4) ---------------------------------------------------------------------------
     Die Material-Verwaltung legt am Produkt einen Rückruf an; er steht am Produkt (laufende oben, beendete eingeklappt),
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
        <span class="mat-rr-was"><a href="/materialablage/katalog/produkt/${r.produkt.id}"><strong>${nameHtml(r.produkt)}</strong></a>${zusatzHtml(r.produkt)} – ${esc(r.title)}</span>
        <span class="small">${plural(r.betroffen, "Artikel", "Artikel")} betroffen · ${r.offen ? `<strong class="mat-warn">${r.offen} offen</strong>` : "alle erledigt"}</span></li>`).join("")}</ul></section>`;
  }

  // Hinweis in der Prüfung: Für den Artikel läuft ein Rückruf, der für ihn noch offen ist. Beschreibung und Empfehlung
  // stehen am Artikel; eine Prüfung nach dem Rückruf erledigt ihn für den Artikel.
  function rueckrufHinweis(titel, artikelId, berichtigung) {
    return titel.length ? `<div class="mat-banner mat-rr-banner" role="note"><p class="mat-rr-titel">RÜCKRUF: ${titel.map(esc).join(" · ")}</p>
      <p class="mat-rr-zeile">Was der Hersteller empfiehlt, steht am <a href="/materialablage/artikel/${artikelId}">Artikel</a>. ${berichtigung
        ? "Eine Berichtigung erledigt den Rückruf nicht – dafür braucht es eine neue Prüfung oder eine Sperre."
        : "Mit dem Abschluss dieser Prüfung gilt der Rückruf für den Artikel als erledigt."}</p></div>` : "";
  }

  // Banner am Artikel – je laufendem Rückruf, der ihn betrifft. Prüfer sperren von hier mit dem Grund „Rückruf“.
  function rueckrufBanner(a) {
    return (a.rueckrufe || []).map((r) => {
      const offen = r.zustand !== "erledigt";
      const pruefen = Boolean(a.darf && a.darf.pruefen);
      const sperren = offen && pruefen && a.lock_state === "frei" && !a.entwurf;
      return `<div class="mat-banner mat-rr-banner${offen ? "" : " erledigt"}" role="note">
        <p class="mat-rr-titel">RÜCKRUF: ${esc(r.title)}</p>
        ${r.description ? `<p class="mat-text mat-rr-text">${esc(r.description)}</p>` : ""}
        <p class="mat-rr-zeile">${r.url ? `${rrLink(r.url, "Meldung des Herstellers")} · ` : ""}seit ${esc(S.fmtDate(r.created_at))} · ${r.alle ? "alle Artikel des Produkts" : "betrifft diese Seriennummer"}
          · für diesen Artikel ${rrZustand(r.zustand, r.grund)}${offen ? " – noch nicht gesperrt und nicht mit dem Rückruf geprüft" : ""}</p>
        ${sperren ? `<div class="btn-row"><button class="btn small" type="button" data-act="rr-sperren" data-id="${r.id}">Sperren (Rückruf)</button></div>` : ""}
        ${offen && !pruefen ? '<p class="mat-rr-zeile">Sperren dürfen Prüfer mit Prüffreigabe (Grund „Rückruf“); eine Prüfung nach dem Rückruf erledigt ihn ebenso.</p>' : ""}
      </div>`;
    }).join("");
  }

  // Warum keine Mail hinausgeht (mailprotokoll.still): ehrlich sagen statt „wird verschickt“ (Nachbesserung vor dem Merge).
  const RR_STILL = { "kein Mailserver": "kein Mailserver eingerichtet", Umgebungssperre: "in dieser Umgebung sind Mails gesperrt" };
  const rrStill = (grund) => esc(RR_STILL[grund] || grund);

  // Wie es um die Mail steht: verschickt (mit Fehlschlägen), läuft noch, nicht bestätigt oder keine. Wie viele Mails
  // hinausgingen, sieht nur die Material-Verwaltung (Phase 2) – sonst steht nur da, ob eine angefordert war („mail“).
  function rrMailText(r) {
    if (!("mail_count" in r)) {
      return !r.mail ? "Keine Mail verschickt." : r.still ? `Es ging keine Mail hinaus – ${rrStill(r.still)}.`
        : "Mail an die Verwalter und Prüfer der betroffenen Artikel.";
    }
    if (r.mailed_at) {
      const n = r.mail_count + r.mail_failed;
      if (!n) return "Mail: keine Empfänger gefunden.";
      if (r.still && r.mail_failed === n) return `Mail an ${plural(n, "Empfänger", "Empfänger")} am ${esc(fmtZeit(r.mailed_at))}: keine ging hinaus – ${rrStill(r.still)}.`;
      return `Mail an ${plural(n, "Empfänger", "Empfänger")} verschickt am ${esc(fmtZeit(r.mailed_at))}${r.mail_failed ? ` – ${r.mail_failed} davon ${r.mail_failed === 1 ? "ging" : "gingen"} nicht hinaus` : ""}.`;
    }
    if (!r.mail_count) return "Keine Mail verschickt.";
    if (r.still) return `Mail an ${plural(r.mail_count, "Empfänger", "Empfänger")}: keine geht hinaus – ${rrStill(r.still)}.`;
    const alt = Date.now() - Date.parse(r.created_at) > (r.unbestaetigt_minuten || 10) * 60000;
    return alt ? `Mail an ${plural(r.mail_count, "Empfänger", "Empfänger")}: Versand nicht bestätigt.`
      : `Mail an ${plural(r.mail_count, "Empfänger", "Empfänger")} wird verschickt …`;
  }

  /* Wer keinen Bestand sieht (Mitglied ohne Freigabe), bekäme bei jedem Rückruf „0 Artikel in deinem Bereich“ –
     das klänge, als träfe er nichts. Die Zahlen gehören den Bereichen (Bauentwurf 2.6), also steht dort, wer sie sieht. */
  const OHNE_BESTAND = () => !DARF.alles && !DARF.lesen;
  const RR_OHNE_BESTAND = "Wie viele Artikel betroffen sind, sehen die Materialwarte der Gliederungen.";

  function rueckrufKarte(r) {
    const serien = r.serien || [];
    const serienText = serien.length > 20
      ? `${serien.slice(0, 20).map(esc).join(", ")} <details class="mat-rr-serien"><summary>alle ${serien.length} zeigen</summary><p class="mat-text">${esc(serien.join("\n"))}</p></details>`
      : serien.map(esc).join(", ");
    const artikel = r.artikel || [];
    return `<article class="mat-rr-karte${r.aktiv ? "" : " beendet"}">
      <div class="mat-rr-kopf"><span class="mat-rr-marke">${r.aktiv ? "Rückruf" : "beendet"}</span><h3>${esc(r.title)}</h3></div>
      <p class="small muted">angelegt von ${person(r.created_by_name || "–")} am ${esc(S.fmtDate(r.created_at))}${r.aktiv ? "" : ` · beendet von ${person(r.closed_by_name || "–")} am ${esc(S.fmtDate(r.closed_at))}`}</p>
      ${r.description ? `<p class="mat-text">${esc(r.description)}</p>` : ""}
      ${r.url ? `<p>${rrLink(r.url, `Meldung des Herstellers: ${kurzLink(r.url)}`)}</p>` : ""}
      <p><strong>Betroffen:</strong> ${r.alle ? "alle Artikel dieses Produkts" : `${serien.length === 1 ? "Seriennummer" : "Seriennummern"} ${serienText}`}</p>
      ${r.aktiv ? `<p>${OHNE_BESTAND() ? RR_OHNE_BESTAND : `${plural(r.betroffen, "Artikel", "Artikel")} ${DARF.alles ? "im Bestand" : "in deinem Bereich"} betroffen${r.betroffen ? ` · ${r.offen ? `<strong class="mat-warn">${r.offen} offen</strong>` : "alle erledigt"}` : ""}`}</p>
        ${artikel.length ? `<table class="list mat-tabelle mat-karten mat-rr-artikel"><thead><tr><th>Inventar-Nr.</th><th>Seriennummer</th><th>Ablage</th><th>Zustand</th></tr></thead><tbody>
          ${artikel.map((x) => `<tr><td data-l="Inventar-Nr." class="mat-k-titel"><a class="mat-inv" href="/materialablage/artikel/${x.id}"><strong>${esc(x.inventory_no)}</strong></a></td>
            <td data-l="Seriennummer">${esc(x.serial_no)}${x.serial_generated ? ' <span class="muted">(System)</span>' : ""}</td>
            <td data-l="Ablage">${esc(x.pfad || "")}</td><td data-l="Zustand" class="mat-k-marke">${rrZustand(x.zustand, x.grund)}</td></tr>`).join("")}</tbody></table>` : ""}
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
      <label for="rr-serien">Betroffene Seriennummern${infoKnopf("Betroffene Seriennummern", "Groß/klein und Leerzeichen am Rand spielen keine Rolle.")}</label><textarea id="rr-serien" rows="4" ${TASTATUR_NUMMER} placeholder="eine je Zeile – leer lassen, wenn alle Artikel des Produkts betroffen sind"></textarea>
      <label class="inline"><input type="checkbox" id="rr-mail" checked> Mail an Materialwarte und Prüfer${infoKnopf("Mail an Materialwarte und Prüfer", "An die Verwalter der betroffenen Artikel und an die Prüfer, die einen davon schon geprüft haben – jeder bekommt nur die Artikel, die er sehen darf.")}</label>
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
          rueckrufErgebnis(r, Boolean($("#rr-serien", body).value.trim()));
          zeigen(produkt);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* Rückmeldung nach dem Anlegen: betroffene Artikel, Mail, Seriennummern ohne Artikel im Bestand. Die Material-Verwaltung
     bekommt die Zahlen über alles, die Zahl der Empfänger und die Seriennummern ohne Artikel; alle anderen nur die Zahlen
     ihres Bereichs und ob für ihre Artikel eine Mail hinausgeht („benachrichtigt“, Phase 2) – ohne eigenen Bestand
     statt der Zahl, wer sie sieht, und bei Seriennummern, dass Tippfehler niemand meldet. */
  function rueckrufErgebnis(r, mitSerien) {
    const nf = r.nicht_gefunden || [];
    const verwaltung = "empfaenger" in r;
    const zahl = !verwaltung && OHNE_BESTAND() ? RR_OHNE_BESTAND
      : `<strong>${plural(r.betroffen, "Artikel", "Artikel")}</strong> ${verwaltung ? "im Bestand" : "in deinem Bereich"} betroffen${r.betroffen && r.offen < r.betroffen ? `, davon ${r.offen} offen` : ""}.`;
    const mail = !r.mail ? "Keine Mail verschickt."
      : r.still ? `Es ging keine Mail hinaus – ${rrStill(r.still)}.`
      : verwaltung ? (r.empfaenger ? `Mail an ${plural(r.empfaenger, "Empfänger", "Empfänger")} wird verschickt.` : "Für die Mail gab es keine Empfänger.")
        : r.benachrichtigt ? "Die Verwalter und Prüfer deiner betroffenen Artikel bekommen eine Mail."
          : "Die Mail geht an die Verwalter und Prüfer der betroffenen Artikel – jeder bekommt nur seine.";
    dialog(`<h2>Rückruf angelegt</h2>
      <p>${zahl}</p>
      <p>${mail}</p>
      ${mitSerien && !verwaltung ? '<p class="help">Ob jede Seriennummer einen Artikel trifft, sieht nur die Material-Verwaltung – bitte die Nummern selbst genau prüfen.</p>' : ""}
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

  /* --- Bestandsimport (Phase 2 · Lieferung 3) ----------------------------------------------------------------------
     Seite /materialablage/ordner/<id>/import – nur mit „verwalten“ am Ordner, kein Systemordner (das prüft schon die
     Seitenroute). Oben „Neue Liste“: Datei wählen (oder hineinziehen), der Probelauf läuft sofort mit der automatischen
     Spaltenzuordnung. Ändert man eine Zuordnung, läuft er nach 600 ms Ruhe neu; eine laufende Anfrage bricht dabei ab
     (AbortController), nur die neueste Antwort zählt. Dann „Übernehmen: n Artikel anlegen, m Zeilen in die Nacharbeit“ –
     der eine rote Knopf der Seite; ist keine Spalte als Seriennummer zugeordnet, gibt ihn erst das Kästchen „Diese Liste
     hat keine Seriennummern …“ direkt darüber frei (Entscheidung vom 20.10.2026, jeder neue Probelauf nimmt es zurück);
     danach die Tabelle „angelegt“ mit den neuen Inventarnummern zum Beschriften.
     Darunter die Nacharbeit dieses Zielordners (über alle Importe hierher): Produkte je Angabe oder für ausgewählte
     Zeilen zuordnen, melden (Materialwart) bzw. im Katalog anlegen (Material-Verwaltung), erneut prüfen und übernehmen,
     verwerfen, als CSV herunterladen. Werte werden hier nicht bearbeitet – dafür ist die CSV mit „Nacharbeit-Nr.“ da.
     Alles, was aus der Datei kommt (Spaltentitel, Beispiele, Werte, Ordner, Gründe, Hinweise), ist reiner Text und geht
     nur über esc() in die Seite (Bauentwurf 4.9) – in der Nacharbeit sehen es auch andere Verwalter. */
  const IMPORT_MAX_BYTES = 5 * 1024 * 1024;                     // bestandsimport.MAX_BYTES
  const IMPORT_ZU_GROSS = "Die Datei ist größer als 5 MB – bitte nur die Liste speichern (ohne Bilder und weitere Blätter) oder als CSV.";
  const IMPORT_FEHLT = "Ordne mindestens Hersteller und Modell (oder Artikelnummer) zu.";        // bestandsimport.FEHLT_ZUORDNUNG
  const IMPORT_NICHTS = "Nichts zu übernehmen – alles steht schon im Bestand oder ist erledigt.";  // bestandsimport.NICHTS
  // Datenschutz bleibt sichtbar – kurz, eine Zeile; was man danach tun kann, steht im „i“ an „Spalten“.
  const IMPORT_PERSONEN = "Personen werden nicht übernommen.";
  const IMPORT_PERSONEN_INFO = "Artikel ordnest du nach dem Import im Ordner über „Zuordnen“ einer Person zu.";
  const IMPORT_NEUBESCHRIFTEN = "Alte Inventarnummern stehen in der Bemerkung und sind nicht suchbar – die Artikel bitte neu beschriften. Eine Liste dafür liefert „Export“ im Ordner.";
  const IMPORT_OHNE_SERIENSPALTE = "Keine Spalte ist als Seriennummer zugeordnet. Steht die Seriennummer doch in einer Spalte, ordne sie oben unter „Spalten“ zu – dann braucht es kein Häkchen.";
  const IMPORT_CSV_SATZ = "Korrigieren, speichern und hier als neue Liste hochladen – die Zeilen werden dabei erledigt. Die Spalte „Nacharbeit-Nr.“ bitte nicht ändern.";
  const IMPORT_SEITE = 100;                                      // Zeilen je Reiter, „weitere …“ zeigt die nächsten
  const PRODUKT_ART = { mehrdeutig: "mehrdeutig", vorschlag: "ähnlich", unbekannt: "nicht im Katalog" };
  const NA_STATUS = { uebernommen: "übernommen", im_bestand: "schon im Bestand", verworfen: "verworfen", ersetzt: "neu eingelesen" };
  const NA_GRUPPEN = [["", "alle"], ["produkt", "Produkt"], ["seriennummer", "Seriennummer"], ["daten", "Daten"], ["ordner", "Ordner"],
                      ["sonstige", "Sonstige"]];
  const KODIERUNG = { "utf-8": "UTF-8", "utf-8-sig": "UTF-8", "utf-16": "UTF-16", cp1252: "Windows-1252" };
  const TRENNER = { ";": "Semikolon", ",": "Komma", "\t": "Tabulator" };
  const REITER_VORHER = [["uebernehmbar", "übernehmbar"], ["im_bestand", "schon im Bestand"], ["nacharbeit", "Nacharbeit"], ["erledigt", "schon erledigt"]];
  const REITER_NACHHER = [["angelegt", "angelegt"], ["im_bestand", "schon im Bestand"], ["nacharbeit", "in die Nacharbeit"], ["erledigt", "schon erledigt"]];
  // Spaltenbuchstabe wie in Excel (0 → A, 26 → AA) – für Spalten ohne Titel.
  const spalteBuchstabe = (i) => { let t = ""; for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) t = String.fromCharCode(65 + ((n - 1) % 26)) + t; return t; };
  const gruendeHtml = (g) => (g && g.length ? `<ul class="mat-gruende">${g.map((x) => `<li data-code="${esc(x.code)}">${esc(x.text)}</li>`).join("")}</ul>` : "");
  const hinweiseHtml = (h) => (h && h.length ? `<ul class="mat-hinweise">${h.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "");
  const angabeAus = (w) => [w.hersteller, w.modell, w.artikelnummer].filter(Boolean).join(" ");
  const produktKurz = (p) => `${esc(p.name)}${artNrKurz(p.article_no)}${demoMarke(p.demo)}`;
  const importFehler = (e) => (e.status === 413 ? IMPORT_ZU_GROSS : e.message);
  // Ohne Seriennummernspalte (Entscheidung vom 20.10.2026): der Satz am Kästchen über „Übernehmen“. Die Zeilen der
  // Nacharbeit bekommen ihre STR-Nummer dort später ohne weitere Frage – darum zählen sie hier mit.
  function ohneSerieSatz(z) {
    const n = z.uebernehmbar, m = z.nacharbeit;
    const artikel = n === 1 ? "der Artikel bekommt" : `alle ${n} Artikel bekommen`;
    const zeilen = m === 1 ? "die Zeile der Nacharbeit" : `die ${m} Zeilen der Nacharbeit`;
    if (n && m) return `Diese Liste hat keine Seriennummern – ${artikel} eine Seriennummer vom System (STR-…), ${zeilen} später auch.`;
    if (n) return `Diese Liste hat keine Seriennummern – ${artikel} eine Seriennummer vom System (STR-…).`;
    return `Diese Liste hat keine Seriennummern – ${zeilen} ${m === 1 ? "bekommt" : "bekommen"} beim Übernehmen dort eine Seriennummer vom System (STR-…).`;
  }
  function faelligSaetze(f) {
    const out = [];
    if (!f) return out;
    const n = f.laut_liste_ueberfaellig, m = f.ohne_pruefdatum, k = f.lebensdauer_erreicht;
    if (n) out.push(n === 1 ? "1 Artikel ist laut Liste überfällig – er steht in der nächsten Erinnerung."
      : `${n} Artikel sind laut Liste überfällig – sie stehen in der nächsten Erinnerung.`);
    if (m) out.push(`${m} Artikel ohne Prüfdatum in der Liste – Eingangsprüfung sofort fällig.`);
    if (k) out.push(k === 1 ? "1 Artikel hat seine Lebensdauer erreicht – nach dem Import prüfen lassen („aussondern empfohlen“), danach sondert der Materialwart aus."
      : `${k} Artikel haben ihre Lebensdauer erreicht – nach dem Import prüfen lassen („aussondern empfohlen“), danach sondert der Materialwart aus.`);
    return out;
  }
  // Die angelegten Artikel zum Beschriften: Zeile, bisherige Nummer, Seriennummer (STR-… vom System), neue Inventarnummer.
  // Nummern und Daten (.mat-ungeteilt) brechen nicht mitten in der Zahl um.
  const angelegtTabelle = (liste, mitNr) => `<table class="list mat-tabelle mat-karten mat-angelegt">
      <thead><tr>${mitNr ? "<th>Nacharbeit-Nr.</th>" : ""}<th>Zeile</th><th>Neue Inventarnummer</th><th>Bisherige Nummer</th><th>Seriennummer</th><th>Fällig</th></tr></thead>
      <tbody>${liste.map((x) => `<tr>${mitNr ? `<td data-l="Nacharbeit-Nr." class="mat-k-halb mat-ungeteilt">${esc(x.id)}</td>` : ""}
        <td data-l="Zeile" class="mat-k-kurz mat-ungeteilt">${esc(x.nr)}</td>
        <td data-l="Neue Inventarnummer" class="mat-k-titel">${x.artikel ? `<a class="mat-inv" href="/materialablage/artikel/${esc(x.artikel.id)}"><strong>${esc(x.artikel.inventory_no)}</strong></a>` : "–"}</td>
        <td data-l="Bisherige Nummer" class="mat-k-halb">${x.bisherige_nummer ? esc(x.bisherige_nummer) : '<span class="muted">–</span>'}</td>
        <td data-l="Seriennummer" class="mat-k-halb">${esc(x.seriennummer || "–")}${/^STR-/.test(x.seriennummer || "") ? ' <span class="muted" title="vom System vergeben">(System)</span>' : ""}</td>
        <td data-l="Fällig" class="mat-k-halb mat-ungeteilt">${x.faellig ? esc(fmtTag(x.faellig)) : '<span class="muted">–</span>'}</td></tr>`).join("")}</tbody></table>`;
  // Wie S.api für ein Formular mit Datei, aber abbrechbar (signal): Beim Probelauf zählt nur die neueste Anfrage.
  async function importSenden(pfad, fd, signal) {
    let res;
    try {
      res = await fetch(pfad, { method: "POST", body: fd, signal, credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } });
    } catch (e) {
      if (e.name === "AbortError") throw e;
      const netz = new Error("Keine Verbindung zum Server.");
      netz.status = 0;
      throw netz;
    }
    if (res.status === 401) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname);
      throw new Error("Nicht angemeldet");
    }
    let daten = {};
    try { daten = await res.json(); } catch (e) { /* kein JSON (etwa ein 413 vom Proxy) */ }
    if (!res.ok) {
      const err = new Error(daten.error || `Fehler ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return daten;
  }
  // Übersicht: offene Nacharbeit je Zielordner, den das Konto verwaltet (/start, höchstens 20).
  /* Übersicht (A4): gesperrte Artikel mit Aussonderungsempfehlung, die das Konto aussondern darf – je „Gesperrt“-Ordner
     ein Link mit gesetztem Filter; bei mehreren Gliederungen mit deren Namen. Nichts bei 0. */
  function empfohlenHinweis(liste) {
    if (!liste || !liste.length) return "";
    const n = liste.reduce((s, x) => s + x.anzahl, 0);
    const link = (x, text) => `<a href="/materialablage/ordner/${Number(x.ordner_id)}?status=${EMPFOHLEN}">${text}</a>`;
    const text = `${n} Artikel mit Aussonderungsempfehlung`;
    return `<p class="notice mat-empfohlen-hinweis">${liste.length === 1 ? link(liste[0], `<strong>${text}</strong>`) : `<strong>${text}</strong>`}
      – gesperrt, ein Prüfer empfiehlt die Aussonderung; aussondern kannst du sie als Materialwart.${liste.length > 1 ? ` ${liste.map((x) => link(x, `${esc(x.gliederung)} (${Number(x.anzahl)})`)).join(" · ")}` : ""}</p>`;
  }
  const nacharbeitHinweis = (liste) => (liste && liste.length ? `<p class="notice">Nacharbeit aus Bestandsimporten:
      ${liste.map((x) => `<a href="/materialablage/ordner/${esc(x.ordner.id)}/import#bi-nacharbeit">${esc(x.ordner.pfad)}</a> (${esc(x.offen)})`).join(", ")}</p>` : "");

  async function bestandsimport() {
    const fid = DATEN.id;
    const [antwort] = await Promise.all([api(`${API}/ordner/${fid}?pro_seite=1`), ordnerBaum().catch(() => null)]);
    const o = antwort.ordner;
    leisteMarkieren(o.id);
    // „Neue Liste“
    let datei = null;            // die gewählte Datei
    let wahl = {};               // eigene Spaltenzuordnung {index: feld} – geht der Erkennung vor
    let bericht = null;          // der letzte Bericht (Probelauf, nach dem Übernehmen das Ergebnis)
    let fertig = false;          // bericht ist das Ergebnis des Übernehmens
    let lauf = null;             // AbortController des laufenden Probelaufs
    let ruhe = null;             // Zeitgeber nach einer geänderten Zuordnung
    let fehler = null;           // letzter Fehler des Probelaufs
    let reiter = null;           // Ergebnis-Reiter
    let bis = IMPORT_SEITE;      // so viele Zeilen zeigt der Reiter
    let spaltenAuf = null;       // Zuordnungstabelle auf/zu (null: nach Lage)
    let uebernimmt = false;
    let berichtFuer = "";        // die Zuordnung, zu der bericht gehört – weicht sie ab, gilt „Übernehmen“ nicht
    let ohneSerie = false;       // Häkchen „Diese Liste hat keine Seriennummern“ – gilt nur für den Bericht, unter dem es steht
    inhalt.innerHTML = `<div class="mat-pfad">${pfadHtml(['<a href="/materialablage/bestand">Bestand</a>', ...o.pfad.map(pfadGlied), "<span>Import</span>"])}</div>
      <div class="page-head"><h1>Bestandsliste importieren${infoKnopf("Bestandsliste importieren", "Importierte Artikel stehen auf „neu“, bis sie im System geprüft sind. Die Fälligkeit kommt aus „nächste Prüfung“ oder „zuletzt geprüft“ der Liste; ohne beides ist die Eingangsprüfung sofort fällig.")} ${demoMarke(o.demo)}</h1></div>
      <p class="help">Zielordner: <strong>${esc(o.pfad.map((x) => x.name).join(" / "))}</strong> – mit der Spalte „Ordner“ auch seine Unterordner.</p>
      <section class="section mat-import" id="bi-neu" aria-labelledby="bi-neu-titel"><h2 id="bi-neu-titel">Neue Liste</h2>
        <div class="mat-ablage" id="bi-ablage">
          <p><strong>Datei hierher ziehen</strong> oder <label class="btn secondary small mat-ablage-knopf">Datei wählen<input type="file" id="bi-datei" class="mat-datei"
            accept=".xlsx,.csv,.txt,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"></label></p>
          <p class="help" id="bi-name">Excel-Arbeitsmappe (.xlsx) oder CSV, höchstens 5 MB.</p></div>
        <details class="mat-auf mat-import-hilfe"><summary>Welche Listen passen?</summary>
          <p class="help">Excel-Arbeitsmappe (.xlsx) oder CSV, höchstens 5 MB und 2000 Zeilen. Eine Zeile je Artikel, oben eine Kopfzeile.
            Erkannt werden Spalten wie Hersteller, Modell, Artikelnummer, Seriennummer, Inventarnummer, Ordner, Herstelldatum, Kaufdatum,
            Erstgebrauch, zuletzt geprüft, nächste Prüfung, Prüfintervall, Anzahl und Bemerkung; Größe, Farbe und Standort kommen in die Bemerkung.
            Die Spalte „Ordner“ nennt einen vorhandenen Unterordner dieses Ordners (etwa „Fahrzeug 1 / Kiste A“).</p>
          <p class="help">Seriennummern bitte vor dem Speichern als Text formatieren – sonst schneidet Excel führende Nullen ab oder schreibt 1,23E+11.
            Datum als TT.MM.JJJJ oder MM/JJJJ. Personen (Ausgegeben an, Telefon …) werden nicht übernommen. Was schon im Bestand steht
            (Produkt und Seriennummer), erkennt der Import und überspringt es; Zeilen ohne Seriennummer bekommen eine Seriennummer vom System (STR-…).
            Hat die Liste gar keine Spalte mit Seriennummern, bestätigst du das vor dem Übernehmen mit einem Häkchen.</p></details>
        <div id="bi-stand" class="mat-import-stand" aria-live="polite"></div>
        <div id="bi-bericht" class="mat-import-bericht"></div>
      </section>
      <section class="section mat-nacharbeit" id="bi-nacharbeit"><h2>Nacharbeit</h2><p class="help">Wird geladen …</p></section>`;
    const standEl = $("#bi-stand"), berichtEl = $("#bi-bericht"), naBox = $("#bi-nacharbeit");

    function standZeichnen() {
      if (lauf || ruhe) { standEl.innerHTML = `<p class="help">${ruhe && !lauf ? "Zuordnung geändert – der Probelauf folgt gleich …" : "Probelauf läuft …"}</p>`; return; }
      if (!fehler) { standEl.innerHTML = ""; return; }
      const nochmal = fehler.status === 429 || fehler.status === 0;
      standEl.innerHTML = `<p class="error">${esc(importFehler(fehler))}${nochmal ? ' <button type="button" class="lnk" data-act="bi-wiederholen">Erneut versuchen</button>' : ""}</p>`;
    }
    function waehlen(f) {
      if (!f) return;
      clearTimeout(ruhe); ruhe = null;
      if (lauf) { lauf.abort(); lauf = null; }
      datei = null; wahl = {}; bericht = null; fertig = false; reiter = null; bis = IMPORT_SEITE; spaltenAuf = null; fehler = null; ohneSerie = false;
      $("#bi-name").textContent = `${f.name} · ${groesse(f.size)}`;
      if (f.size > IMPORT_MAX_BYTES) { fehler = { message: IMPORT_ZU_GROSS, status: 413 }; berichtZeichnen(); return; }
      datei = f;
      berichtZeichnen();              // der Bericht der vorigen Datei gilt nicht mehr
      probelauf();
    }
    function formular() {
      const fd = new FormData();
      fd.append("file", datei);
      if (Object.keys(wahl).length) fd.append("zuordnung", JSON.stringify(wahl));
      return fd;
    }
    const ersterReiter = (b) => {
      const liste = fertig ? REITER_NACHHER : REITER_VORHER;
      return (liste.find(([s]) => b.zahlen[s]) || liste[0])[0];
    };
    async function probelauf() {
      clearTimeout(ruhe); ruhe = null;
      if (!datei) return;
      if (lauf) lauf.abort();
      const meins = new AbortController();
      lauf = meins;
      fehler = null;
      standZeichnen();
      berichtEl.classList.add("laedt");
      const fuer = JSON.stringify(wahl);
      try {
        const b = await importSenden(`${API}/ordner/${fid}/import/probelauf`, formular(), meins.signal);
        if (lauf !== meins) return;
        bericht = b;
        berichtFuer = fuer;
        fertig = false;
        ohneSerie = false;         // ein neuer Probelauf (etwa nach geänderter Zuordnung) will ein neues Häkchen
        if (!reiter || !b.zahlen[reiter]) { reiter = ersterReiter(b); bis = IMPORT_SEITE; }
      } catch (e) {
        if (e.name === "AbortError" || lauf !== meins) return;
        fehler = e;
      } finally {
        if (lauf === meins) { lauf = null; berichtZeichnen(); }
      }
    }
    function dateiZeile(b) {
      const d = b.datei;
      const art = d.art === "xlsx" ? "Excel-Arbeitsmappe" : `CSV, ${esc(KODIERUNG[d.kodierung] || d.kodierung)}, getrennt durch ${esc(TRENNER[d.trennzeichen] || d.trennzeichen)}`;
      return `<p class="small mat-import-datei">${art} · Kopfzeile in Zeile ${esc(d.kopfzeile)} · ${plural(d.datenzeilen, "Datenzeile", "Datenzeilen")}${d.leerzeilen ? ` · ${plural(d.leerzeilen, "leere Zeile", "leere Zeilen")} übergangen` : ""}</p>`;
    }
    function spaltenHtml(b) {
      const fehlt = b.fehlt && b.fehlt.length;
      if (fertig) return "";
      if (b.nacharbeit_csv && !spaltenAuf && !fehlt) {
        return `<p class="mat-import-csv">Nacharbeits-CSV erkannt – Spalten zugeordnet. <button type="button" class="lnk" data-act="bi-spalten">Zuordnung ändern</button></p>`;
      }
      const auf = fehlt || spaltenAuf !== false;
      const zugeordnet = b.spalten.filter((x) => x.zuordnung !== "ignorieren").length;
      const optionen = (x) => b.felder.map((f) => `<option value="${esc(f.feld)}" ${f.feld === x.zuordnung ? "selected" : ""}>${esc(f.text)}</option>`).join("");
      const zeile = (x) => {
        const titel = x.titel || `Spalte ${spalteBuchstabe(x.index)}`;
        return `<tr class="${x.zuordnung === "ignorieren" ? "mat-alt" : ""}"><td data-l="Spalte" class="mat-k-titel"><strong>${esc(titel)}</strong></td>
          <td data-l="Beispiele" class="mat-k-ohne">${x.gesperrt ? "" : x.beispiele.length ? x.beispiele.map((w) => `<span class="mat-beispiel">${esc(w)}</span>`).join('<span class="muted"> · </span>') : '<span class="muted">–</span>'}</td>
          <td data-l="Feld" class="mat-k-ohne">${x.gesperrt ? '<span class="muted">Personenangaben – werden nicht übernommen</span>'
            : `<select data-spalte="${esc(x.index)}" aria-label="Feld für die Spalte ${esc(titel)}">${optionen(x)}</select>`}</td></tr>`;
      };
      return `<details class="mat-auf mat-import-spalten" ${auf ? "open" : ""}><summary>Spalten – ${zugeordnet} von ${b.spalten.length} zugeordnet${infoKnopf("Spalten", `Mehrere Spalten in der Bemerkung erscheinen als „Titel: Wert“.${b.spalten.some((x) => x.gesperrt) ? `<span class="info-absatz">${esc(IMPORT_PERSONEN_INFO)}</span>` : ""}`)}</summary>
          <table class="list mat-tabelle mat-karten mat-spaltenwahl"><thead><tr><th>Spalte in der Datei</th><th>Beispiele</th><th>Feld</th></tr></thead>
            <tbody>${b.spalten.map(zeile).join("")}</tbody></table>
          ${b.spalten.some((x) => x.gesperrt) ? `<p class="help">${esc(IMPORT_PERSONEN)}</p>` : ""}</details>
        ${fehlt ? `<p class="error">${esc(IMPORT_FEHLT)}</p>` : ""}`;
    }
    function zeilenHtml(b) {
      const liste = b.zeilen.filter((x) => x.status === reiter);
      if (!liste.length) return leer("Keine Zeilen.");
      const teil = liste.slice(0, bis);
      const weitere = liste.length > bis ? `<p><button type="button" class="btn secondary small" data-act="bi-weitere">weitere ${Math.min(IMPORT_SEITE, liste.length - bis)} von ${liste.length - bis}</button></p>` : "";
      if (reiter === "angelegt") return `${angelegtTabelle(teil)}${weitere}`;
      const produkt = (x) => (x.produkt ? produktKurz(x.produkt) : x.angabe_text ? `<span class="muted">${esc(x.angabe_text)}</span>` : '<span class="muted">ohne Produktangabe</span>');
      return `<table class="list mat-tabelle mat-karten mat-import-zeilen">
          <thead><tr><th>Zeile</th><th>Produkt</th><th>Seriennummer</th><th>Ordner</th><th>Fällig</th><th>Gründe und Hinweise</th></tr></thead>
          <tbody>${teil.map((x) => `<tr><td data-l="Zeile" class="mat-k-titel"><strong class="mat-ungeteilt">Zeile ${esc(x.nr)}</strong>${x.rueckruf ? ` <span class="mat-rr-marke" title="Rückruf: ${esc(x.rueckruf)}">Rückruf</span>` : ""}</td>
            <td data-l="Produkt" class="mat-k-ohne">${produkt(x)}${x.artikel ? `<div class="small">schon im Bestand: <a href="/materialablage/artikel/${esc(x.artikel.id)}">${esc(x.artikel.inventory_no)}</a></div>` : ""}</td>
            <td data-l="Seriennummer" class="mat-k-halb">${x.seriennummer ? esc(x.seriennummer) : `<span class="muted">${x.status === "erledigt" ? "–" : "ohne"}</span>`}</td>
            <td data-l="Ordner" class="mat-k-halb">${x.ordner ? esc(x.ordner) : '<span class="muted">–</span>'}</td>
            <td data-l="Fällig" class="mat-k-halb mat-ungeteilt">${x.faellig ? esc(fmtTag(x.faellig)) : '<span class="muted">–</span>'}</td>
            <td data-l="Gründe und Hinweise" class="mat-k-ohne">${gruendeHtml(x.gruende)}${hinweiseHtml(x.hinweise)}</td></tr>`).join("")}</tbody></table>${weitere}`;
    }
    // „Übernehmen“ gilt nur für den letzten Probelauf zur aktuellen Zuordnung – ohne Seriennummernspalte erst mit Häkchen.
    const uebernehmenGesperrt = () => uebernimmt || Boolean(lauf || ruhe) || JSON.stringify(wahl) !== berichtFuer
      || Boolean(bericht && bericht.ohne_seriennummern_bestaetigen && !ohneSerie);
    function knopfText(b) {
      const z = b.zahlen;
      const a = plural(z.uebernehmbar, "Artikel", "Artikel"), n = plural(z.nacharbeit, "Zeile", "Zeilen");
      if (z.uebernehmbar && z.nacharbeit) return `Übernehmen: ${a} anlegen, ${n} in die Nacharbeit`;
      if (z.uebernehmbar) return `Übernehmen: ${a} anlegen`;
      if (z.nacharbeit) return `${n} in die Nacharbeit übernehmen`;
      // Eine Nacharbeits-CSV, deren Zeilen inzwischen im Bestand stehen: Übernehmen erledigt die alten Zeilen.
      if (b.nacharbeit_csv && z.im_bestand) return "Übernehmen: Nacharbeit abgleichen (nichts anzulegen)";
      return "";
    }
    function ergebnisHtml(b) {
      const z = b.zahlen;
      const warn = b.warnungen.concat(b.ordner_unbekannt.map((u) => `Ordner „${u.wert}“ (${plural(u.zeilen, "Zeile", "Zeilen")}) gibt es unter „${o.name}“ nicht – bitte im Bestand anlegen und den Probelauf wiederholen, oder die Spalte als Bemerkung zuordnen.`));
      const fehlt = b.fehlt && b.fehlt.length;
      const imp = b.import;
      const stand = fertig && imp ? `<p class="mat-austausch-stand ok" tabindex="-1">Übernommen: ${plural(imp.angelegt, "Artikel", "Artikel")} angelegt${imp.nacharbeit ? `, ${plural(imp.nacharbeit, "Zeile", "Zeilen")} in die Nacharbeit` : ""}${imp.im_bestand ? `, ${plural(imp.im_bestand, "Zeile", "Zeilen")} schon im Bestand oder erledigt` : ""}${imp.ersetzt ? `, ${plural(imp.ersetzt, "Zeile", "Zeilen")} der Nacharbeit neu eingelesen` : ""}.</p>
        ${imp.angelegt ? `<p class="help">${esc(IMPORT_NEUBESCHRIFTEN)}</p>` : ""}` : "";
      const offen = !fertig && b.produkte_offen.length ? `<div class="mat-austausch-liste mat-import-produkte"><strong>Produkte, die der Katalog nicht sicher kennt</strong>
          <ul>${b.produkte_offen.map((p) => `<li>${esc(angabeAus(p) || "ohne Angabe")} – ${plural(p.zeilen, "Zeile", "Zeilen")} – ${esc(PRODUKT_ART[p.art] || p.art)}</li>`).join("")}</ul>
          <p class="help">Diese Zeilen kommen in die Nacharbeit. Dort ordnest du das Produkt zu – auch zeilenweise, etwa bei verschiedenen Größen – oder meldest es.</p></div>` : "";
      const reiterListe = (fertig ? REITER_NACHHER : REITER_VORHER).filter(([s]) => s !== "erledigt" || z.erledigt);
      // Dieselbe Datei ist eben in diesen Ordner übernommen worden (zehn Minuten gesperrt): kein Knopf, der sicher scheitert.
      const sperre = !fertig && b.sperre_bis ? uhrBerlin(b.sperre_bis) : "";      // wie die Uhrzeit in der Warnung
      const text = fehlt || sperre ? "" : knopfText(b);
      const knoepfe = fertig
        ? '<div class="btn-row mat-import-knoepfe"><button type="button" class="btn secondary" data-act="bi-neu">Weitere Liste importieren</button></div>'
        : `<p class="small mat-import-wieder"><button type="button" class="lnk" data-act="bi-wiederholen">Probelauf wiederholen</button>${Object.keys(wahl).length ? ' · <button type="button" class="lnk" data-act="bi-automatisch">Zuordnung wie erkannt</button>' : ""}</p>
          ${sperre ? `<p class="notice">Diese Datei ist eben in diesen Ordner übernommen worden – noch einmal übernehmen geht erst ab ${esc(sperre)} Uhr (dann „Probelauf wiederholen“). Was offen blieb, steht unten in der Nacharbeit.</p>` : ""}
          ${!fehlt && !sperre && !text && z.zeilen ? `<p class="leerzustand">${esc(IMPORT_NICHTS)}</p>` : ""}
          ${text && b.ohne_seriennummern_bestaetigen ? `<div class="notice mat-import-ohne-serie"><label class="inline"><input type="checkbox" id="bi-ohne-serie" aria-describedby="bi-ohne-serie-hilfe" ${ohneSerie ? "checked" : ""}><span>${esc(ohneSerieSatz(z))}</span></label>
            <p class="help" id="bi-ohne-serie-hilfe">${esc(IMPORT_OHNE_SERIENSPALTE)}</p></div>` : ""}
          ${!fehlt && z.nacharbeit ? `<p class="help">${esc(b.frist)}</p>` : ""}
          <div class="btn-row mat-import-knoepfe"><button type="button" class="btn secondary" data-act="bi-neu">Neu wählen</button>${text ? `<button type="button" class="btn" data-act="bi-uebernehmen" ${uebernehmenGesperrt() ? "disabled" : ""}>${esc(uebernimmt ? "Wird übernommen …" : text)}</button>` : ""}</div>`;
      return `${stand}${austauschListe("Bitte beachten", warn, "warnung")}${offen}
        ${fehlt ? "" : `${austauschListe("Fälligkeit", faelligSaetze(b.faelligkeit), "")}
        <div class="c-tabs mat-filter mat-import-reiter" role="group" aria-label="Zeilen nach Ergebnis">${reiterListe.map(([s, t]) => `<button type="button" data-act="bi-reiter" data-r="${s}" class="${s === reiter ? "sel" : ""}" aria-pressed="${s === reiter}">${esc(t)} ${z[s] || 0}</button>`).join("")}</div>
        ${zeilenHtml(b)}`}
        ${knoepfe}`;
    }
    function berichtZeichnen() {
      standZeichnen();
      berichtEl.classList.remove("laedt");
      // Wer gerade eine Zuordnung wählt, behält den Fokus auf derselben Spalte.
      const aktiv = berichtEl.contains(document.activeElement) && document.activeElement.dataset ? document.activeElement.dataset.spalte : undefined;
      if (!bericht) { berichtEl.innerHTML = ""; return; }
      berichtEl.innerHTML = `${dateiZeile(bericht)}${spaltenHtml(bericht)}${ergebnisHtml(bericht)}`;
      if (aktiv !== undefined) { const s = $(`select[data-spalte="${CSS.escape(aktiv)}"]`, berichtEl); if (s) s.focus({ preventScroll: true }); }
    }
    async function uebernehmen() {
      if (!datei || uebernehmenGesperrt() || (bericht && bericht.sperre_bis)) return;
      const fd = formular();
      if (bericht && bericht.ohne_seriennummern_bestaetigen) fd.append("ohne_seriennummern", "true");   // nur mit Häkchen hier
      uebernimmt = true;
      berichtZeichnen();
      try {
        const b = await importSenden(`${API}/ordner/${fid}/import`, fd);
        bericht = b;
        fertig = true;
        fehler = null;
        reiter = ersterReiter(b);
        bis = IMPORT_SEITE;
        const n = b.import ? b.import.angelegt : 0;
        toast(n ? `${plural(n, "Artikel", "Artikel")} angelegt` : "Übernommen – kein Artikel angelegt");
        leisteNeu();
        nacharbeitLaden();
      } catch (e) {
        toast(importFehler(e), true);
      } finally {
        uebernimmt = false;
        berichtZeichnen();
      }
      // Der Knopf ist neu gezeichnet worden – der Fokus geht auf das Ergebnis bzw. zurück auf den Knopf.
      const fokus = fertig ? $(".mat-austausch-stand", berichtEl) : $('[data-act="bi-uebernehmen"]', berichtEl);
      if (fokus) fokus.focus({ preventScroll: true });
      if (fertig) $("#bi-neu-titel").scrollIntoView({ block: "start" });
    }

    // Datei wählen oder in den Abschnitt ziehen; daneben Abgelegtes öffnet der Browser nie selbst (die Seite wäre weg).
    $("#bi-datei").addEventListener("change", (ev) => { const f = ev.target.files[0]; ev.target.value = ""; waehlen(f); });
    const ablage = $("#bi-ablage"), bereich = $("#bi-neu");
    bereich.addEventListener("dragover", (ev) => { ev.preventDefault(); ablage.classList.add("ueber"); });
    bereich.addEventListener("dragleave", (ev) => { if (!bereich.contains(ev.relatedTarget)) ablage.classList.remove("ueber"); });
    bereich.addEventListener("drop", (ev) => {
      ev.preventDefault();
      ablage.classList.remove("ueber");
      if (ev.dataTransfer && ev.dataTransfer.files.length) waehlen(ev.dataTransfer.files[0]);
    });
    inhalt.addEventListener("dragover", (ev) => ev.preventDefault());
    inhalt.addEventListener("drop", (ev) => ev.preventDefault());
    // Eine geänderte Zuordnung: Was gerade läuft, zählt nicht mehr; nach 600 ms Ruhe der neue Probelauf. Bis dahin ist
    // „Übernehmen“ gesperrt – seine Zahlen gehören zur alten Zuordnung.
    // Das Häkchen ohne Seriennummernspalte gibt den Knopf frei, ohne neu zu zeichnen (der Fokus bleibt am Kästchen); eine
    // geänderte Zuordnung nimmt es zurück.
    berichtEl.addEventListener("change", (ev) => {
      const k = $('[data-act="bi-uebernehmen"]', berichtEl);
      if (ev.target.id === "bi-ohne-serie") {
        ohneSerie = ev.target.checked;
        if (k) k.disabled = uebernehmenGesperrt();
        return;
      }
      const s = ev.target.closest("select[data-spalte]");
      if (!s) return;
      wahl[s.dataset.spalte] = s.value;
      if (lauf) { lauf.abort(); lauf = null; }
      clearTimeout(ruhe);
      ruhe = setTimeout(probelauf, 600);
      ohneSerie = false;
      const h = $("#bi-ohne-serie", berichtEl);
      if (h) h.checked = false;
      if (k) k.disabled = true;
      standZeichnen();
    });
    berichtEl.addEventListener("toggle", (ev) => { if (ev.target.classList && ev.target.classList.contains("mat-import-spalten")) spaltenAuf = ev.target.open; }, true);

    /* --- Nacharbeit dieses Zielordners --- */
    let na = null;               // Antwort von GET …/nacharbeit
    let naGruppe = "";           // Filter nach Grund
    let naZeilen = [];           // geladene offene Zeilen (Seite 1 … naSeite)
    let naSeite = 1;
    let naAlle = false;          // „alle n offenen“ gewählt – dann geht "alle" an den Server
    const naWahl = new Set();    // gewählte Nacharbeit-Nr.
    let naGeladen = false;
    async function nacharbeitLaden() {
      try {
        na = await api(`${API}/ordner/${fid}/nacharbeit?${new URLSearchParams({ gruppe: naGruppe || "alle", seite: 1 })}`);
      } catch (e) {
        naBox.innerHTML = `<h2>Nacharbeit</h2><p class="error">${esc(e.message)}</p>`;
        return;
      }
      naZeilen = na.zeilen;
      naSeite = na.seite;
      naWahl.clear();
      naAlle = false;
      nacharbeitZeichnen();
      if (!naGeladen && location.hash === "#bi-nacharbeit") naBox.scrollIntoView({ block: "start" });
      naGeladen = true;
    }
    async function naMehr(knopf) {
      knopf.disabled = true;
      try {
        const d = await api(`${API}/ordner/${fid}/nacharbeit?${new URLSearchParams({ gruppe: naGruppe || "alle", seite: naSeite + 1 })}`);
        naZeilen = naZeilen.concat(d.zeilen);
        naSeite = d.seite;
        na.seiten = d.seiten;
        nacharbeitZeichnen();
      } catch (e) { toast(e.message, true); knopf.disabled = false; }
    }
    const naAuswahl = () => (naAlle ? "alle" : Array.from(naWahl));
    const naAnzahl = () => (naAlle ? na.zahlen.offen : naWahl.size);
    function naGruppenHtml() {
      if (!na.gruppen.length) return "";
      return `<h3 class="mat-unter">Produkte zuordnen</h3><div class="mat-na-karten">${na.gruppen.map((g, i) => {
        const m = g.meldung;
        const meldung = !m ? "" : m.status === "offen" ? "Gemeldet – die Material-Verwaltung nimmt das Produkt auf."
          : m.status === "eingepflegt" ? `Eingepflegt: ${m.produkt ? produktKurz(m.produkt) : "–"} – „Übernehmen“ legt die Artikel an.`
            : `Abgelehnt${m.antwort ? `: ${esc(m.antwort)}` : ""}`;
        const knoepfe = [`<button type="button" class="btn secondary small" data-act="na-gruppe-zuordnen" data-i="${i}">Produkt zuordnen</button>`];
        // Ist schon ein Produkt zugeordnet (auch gerade erst im Katalog angelegt), braucht es kein Anlegen und Melden mehr –
        // „Produkt zuordnen“ ändert die Wahl.
        // Konten ohne Katalogrecht melden das fehlende Produkt (vorbelegt aus der Nacharbeit, Wunsch vom 25.10.2026).
        if (!g.produkt && DARF.katalog) knoepfe.push(`<button type="button" class="btn secondary small" data-act="na-anlegen" data-i="${i}">Im Katalog anlegen</button>`);
        else if (!g.produkt && (!m || m.status === "abgelehnt")) knoepfe.push(`<button type="button" class="btn secondary small" data-act="na-melden" data-i="${i}">Fehlendes Produkt melden</button>`);
        // Zugeordnet (ganz oder zeilenweise) oder die Meldung eingepflegt: direkt übernehmen, ohne Anhaken und ohne CSV.
        if (g.produkt || g.zugeordnet || (m && m.status === "eingepflegt")) knoepfe.push(`<button type="button" class="btn secondary small" data-act="na-uebernehmen" data-i="${i}">Übernehmen</button>`);
        const zeilenweise = !g.produkt && g.zugeordnet ? ` · zeilenweise zugeordnet: ${g.zugeordnet} von ${g.offen}` : "";
        return `<div class="mat-na-karte"><p class="mat-na-angabe"><strong>${esc(angabeAus(g) || "ohne Angabe")}</strong> <span class="mat-na-art">${esc(g.produkt ? "zugeordnet" : PRODUKT_ART[g.art] || g.art)}</span></p>
          <p class="small">${plural(g.offen, "Zeile", "Zeilen")}${g.produkt ? ` · zugeordnet: <strong>${produktKurz(g.produkt)}</strong>` : ""}${zeilenweise}</p>
          ${m ? `<p class="small">${meldestatusMarke(m.status)} ${meldung}</p>` : ""}
          <p class="help">${g.offen === 1 ? "Gilt für die Zeile dieser Angabe." : `Gilt für alle ${g.offen} Zeilen dieser Angabe. Sind es verschiedene Größen oder Varianten, die Zeilen unten auswählen und einzeln zuordnen.`}</p>
          <div class="btn-row">${knoepfe.join("")}</div></div>`;
      }).join("")}</div>`;
    }
    function naZeileHtml(z) {
      const w = z.werte || {};
      const angabe = angabeAus(w);
      const bem = w.bemerkung ? (w.bemerkung.length > 80 ? `${w.bemerkung.slice(0, 80)}…` : w.bemerkung) : "";
      return `<tr data-id="${esc(z.id)}">
        <td class="mat-wahlspalte mat-k-wahl"><label class="mat-wahl-feld"><input type="checkbox" class="mat-na-wahl" value="${esc(z.id)}" ${naAlle || naWahl.has(z.id) ? "checked" : ""}
          aria-label="Nacharbeit-Nr. ${esc(z.id)} auswählen"><span class="mat-wahl-text">auswählen</span></label></td>
        <td data-l="Nacharbeit-Nr." class="mat-k-titel"><strong>Nr. ${esc(z.id)}</strong><div class="small muted">${esc(z.import.datei)} · Zeile&nbsp;${esc(z.nr)}</div></td>
        <td data-l="Angaben" class="mat-k-ohne">${angabe ? `<strong>${esc(angabe)}</strong>` : '<span class="muted">ohne Produktangabe</span>'}
          ${z.produkt ? `<div class="small">zugeordnet: ${produktKurz(z.produkt)}</div>` : ""}
          <div class="small">${w.seriennummer ? `SN ${esc(w.seriennummer)}` : '<span class="muted">ohne Seriennummer</span>'}${w.ordner ? ` · Ordner ${esc(w.ordner)}` : ""}</div>
          ${bem ? `<div class="small muted mat-na-bem">${esc(bem)}</div>` : ""}</td>
        <td data-l="Gründe" class="mat-k-ohne">${gruendeHtml(z.gruende)}<div class="small muted">offen bis ${esc(fmtTag(z.offen_bis))}</div></td>
        <td data-l="Werte" class="mat-k-ohne"><details class="mat-na-werte"><summary>alle Werte</summary><dl class="mat-daten">${na.felder.filter((f) => w[f.feld]).map((f) => `<dt>${esc(f.text)}</dt><dd class="mat-text">${esc(w[f.feld])}</dd>`).join("")}</dl></details></td></tr>`;
    }
    function naErledigtHtml() {
      if (!na.erledigt.length) return "";
      return `<details class="mat-auf mat-na-erledigt"><summary>Zuletzt erledigt (${na.erledigt.length})</summary>
        <table class="list mat-tabelle mat-karten"><thead><tr><th>Nacharbeit-Nr.</th><th>Ergebnis</th><th>Grund</th><th>Wer, wann</th></tr></thead>
        <tbody>${na.erledigt.map((x) => `<tr><td data-l="Nacharbeit-Nr." class="mat-k-titel">Nr. ${esc(x.id)} <span class="small muted">Zeile ${esc(x.nr)}</span></td>
          <td data-l="Ergebnis" class="mat-k-marke">${esc(NA_STATUS[x.status] || x.status)}${x.artikel ? ` – <a href="/materialablage/artikel/${esc(x.artikel.id)}">${esc(x.artikel.inventory_no)}</a>` : ""}</td>
          <td data-l="Grund">${x.grund ? esc(x.grund) : '<span class="muted">–</span>'}</td>
          <td data-l="Wer, wann">${esc(x.von || "–")}, ${esc(fmtZeit(x.am))}</td></tr>`).join("")}</tbody></table></details>`;
    }
    function nacharbeitZeichnen() {
      const z = na.zahlen;
      const kopf = `<div class="mat-nacharbeit-kopf"><h2>Nacharbeit – ${z.offen} offen</h2>
        ${z.offen ? `<details class="mat-menue"><summary class="btn secondary small" aria-haspopup="true">Mehr</summary><div class="mat-menue-liste">
          <a href="/materialablage/ordner/${esc(fid)}/nacharbeit.csv" data-frisch data-export="Die Nacharbeit wird heruntergeladen …"><strong>Als CSV herunterladen</strong><span>${esc(IMPORT_CSV_SATZ)}</span></a></div></details>` : ""}</div>`;
      if (!z.offen) {
        naBox.innerHTML = `${kopf}${leer("Nichts offen – was ein Import nicht übernehmen konnte, steht hier.")}${naErledigtHtml()}`;
        return;
      }
      const filter = NA_GRUPPEN.filter(([g]) => !g || z[g] || g === naGruppe).map(([g, t]) => `<button type="button" data-act="na-filter" data-g="${g}" class="${g === naGruppe ? "sel" : ""}" aria-pressed="${g === naGruppe}">${esc(t)} (${g ? z[g] : z.offen})</button>`).join("");
      naBox.innerHTML = `${kopf}<p class="help">${esc(na.frist)} Werte lassen sich hier nicht bearbeiten: „Mehr → Als CSV herunterladen“, korrigieren und oben als neue Liste hochladen.</p>
        ${naGruppenHtml()}
        <h3 class="mat-unter">Offene Zeilen</h3>
        <div class="c-tabs mat-filter" role="group" aria-label="Offene Zeilen nach Grund">${filter}</div>
        <div class="mat-na-liste">
          ${naZeilen.length ? `<div class="mat-kartenkopf"><label class="mat-wahl-feld mat-alle-feld"><input type="checkbox" class="mat-na-alle"><span>alle auf dieser Seite auswählen</span></label></div>
          <table class="list mat-tabelle mat-karten mat-na-zeilen"><thead><tr><th class="mat-wahlspalte"><label class="mat-wahl-feld"><input type="checkbox" class="mat-na-alle" aria-label="alle auf dieser Seite auswählen"></label></th>
            <th>Nacharbeit-Nr.</th><th>Angaben</th><th>Gründe</th><th>Werte</th></tr></thead>
            <tbody>${naZeilen.map(naZeileHtml).join("")}</tbody></table>` : leer("Keine offenen Zeilen mit diesem Grund.")}
          ${naSeite < na.seiten ? '<p><button type="button" class="btn secondary small" data-act="na-weitere">weitere</button></p>' : ""}
          <div class="mat-sammel" id="na-sammel" hidden><span><span id="na-sammel-n"></span> <button type="button" class="lnk" data-act="na-alle-offen" hidden></button></span>
            <div class="btn-row"><button type="button" class="btn secondary small" data-act="na-zeilen-zuordnen">Produkt zuordnen</button>
              <button type="button" class="btn secondary small" data-act="na-pruefen">Erneut prüfen</button>
              <button type="button" class="btn secondary small" data-act="na-verwerfen">Verwerfen</button></div></div>
        </div>
        ${naErledigtHtml()}`;
      naSammel();
    }
    function naSammel() {
      const boxen = $$(".mat-na-wahl", naBox);
      const n = boxen.filter((c) => c.checked).length;
      $$(".mat-na-alle", naBox).forEach((x) => { x.checked = boxen.length > 0 && n === boxen.length; x.indeterminate = n > 0 && n < boxen.length; });
      const leiste = $("#na-sammel", naBox);
      if (!leiste) return;
      leiste.hidden = !n;
      $("#na-sammel-n", naBox).textContent = naAlle ? `alle ${na.zahlen.offen} offenen Zeilen ausgewählt` : `${plural(naWahl.size, "Zeile", "Zeilen")} ausgewählt`;
      const alle = $('[data-act="na-alle-offen"]', leiste);
      alle.hidden = naAlle || n < boxen.length || na.zahlen.offen <= naWahl.size;
      alle.textContent = `alle ${na.zahlen.offen} offenen auswählen${naGruppe ? " (alle Gründe)" : ""}`;
    }
    naBox.addEventListener("change", (ev) => {
      const c = ev.target;
      if (c.classList.contains("mat-na-wahl")) {
        if (naAlle) { naAlle = false; $$(".mat-na-wahl", naBox).forEach((x) => { if (x.checked) naWahl.add(+x.value); }); }
        if (c.checked) naWahl.add(+c.value); else naWahl.delete(+c.value);
        naSammel();
      } else if (c.classList.contains("mat-na-alle")) {
        naAlle = false;
        $$(".mat-na-wahl", naBox).forEach((x) => { x.checked = c.checked; if (c.checked) naWahl.add(+x.value); else naWahl.delete(+x.value); });
        naSammel();
      }
    });

    // Produkt zuordnen – für eine Angabe (Karte) oder für die ausgewählten Zeilen.
    function zuordnenDialogNa(titel, hilfe, vorschlaege, ziel, aktuell) {
      dialog(`<h2>${esc(titel)}</h2><p class="help">${esc(hilfe)}</p>
        ${vorschlaege.length ? `<div class="mat-feldkopf">Vorschläge</div><div class="mat-treffer mat-na-vorschlaege">${vorschlaege.map((p, i) => `<div class="mat-treffer-produkt">${p.vorschau ? `<img class="mat-mini" src="${esc(p.vorschau)}" alt="">` : ""}<button type="button" class="mat-treffer-wahl" data-v="${i}"><strong>${esc(p.name)}</strong>${artNrKurz(p.article_no)}${demoMarke(p.demo)}</button></div>`).join("")}</div>` : ""}
        <label for="nz-q">Produkt suchen</label>
        <div class="mat-produktwahl"><input type="search" id="nz-q" autocomplete="off" ${TASTATUR_SUCHE}><div id="nz-treffer" class="mat-treffer"></div></div>
        <div id="nz-gewaehlt" class="mat-gewaehlt" hidden></div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
          ${aktuell ? '<button class="btn secondary" id="nz-weg" type="button">Zuordnung entfernen</button>' : ""}
          <button class="btn" id="nz-ok" type="button" disabled>Zuordnen</button></div>`,
      (dlg, body) => {
        let gewaehlt = null;
        let los = null;
        const zeigeWahl = (id, html) => {
          gewaehlt = id;
          const el = $("#nz-gewaehlt", body);
          el.hidden = false;
          el.innerHTML = `<span>Gewählt: ${html}</span>`;
          $("#nz-ok", body).disabled = false;
        };
        const vor = $(".mat-na-vorschlaege", body);
        if (vor) vor.addEventListener("click", (ev) => { const b = ev.target.closest("[data-v]"); if (b) { const p = vorschlaege[+b.dataset.v]; zeigeWahl(p.id, produktKurz(p)); } });
        $("#nz-q", body).addEventListener("input", () => {
          clearTimeout(los);
          los = setTimeout(() => {
            const q = $("#nz-q", body).value.trim();
            if (!q) { trefferLeeren($("#nz-treffer", body)); return; }
            produktTreffer($("#nz-treffer", body), q, (p) => {
              zeigeWahl(p.id, `<strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${artNrKurz(p.article_no)}${demoMarke(p.demo)}`);
              trefferLeeren($("#nz-treffer", body));
              $("#nz-ok", body).focus();          // der gewählte Treffer ist weg – sonst landete der Fokus auf <body>
            },
              '<p class="help">Kein Produkt gefunden.</p>');
          }, 200);
        });
        async function setzen(pid, knopf) {
          knopf.disabled = true;
          try {
            const r = await api(`${API}/ordner/${fid}/nacharbeit/produkt`, { method: "POST", body: Object.assign({ product_id: pid }, ziel) });
            dlg.close();
            await nacharbeitLaden();
            // Nach dem Zuordnen gleich die Prüfung dieser Zeilen mit „k Artikel übernehmen“ (Wunsch vom 25.10.2026, F1).
            if (pid) nachpruefen(ziel, r.gesetzt);
            else toast(`Zuordnung entfernt – ${plural(r.gesetzt, "Zeile", "Zeilen")}`);
          } catch (e) { toast(e.message, true); knopf.disabled = false; }
        }
        $("#nz-ok", body).onclick = (ev) => { if (gewaehlt) setzen(gewaehlt, ev.currentTarget); };
        const weg = $("#nz-weg", body);
        if (weg) weg.onclick = () => setzen(null, weg);
      });
    }
    // Erneut prüfen: erst das Ergebnis (schreibt nichts), dann auf Wunsch übernehmen. ziel: {zeilen} (Vorgabe: die
    // Auswahl) oder {angabe} (die Karte – „Übernehmen“). zugeordnet: Zahl der eben zugeordneten Zeilen – dann kommt der
    // Dialog direkt aus „Zuordnen“ und sagt das im Titel.
    async function nachpruefen(ziel, zugeordnet) {
      if (!ziel) {
        const zeilen = naAuswahl();
        if (zeilen !== "alle" && !zeilen.length) return;
        ziel = { zeilen };
      }
      let r;
      try { r = await api(`${API}/ordner/${fid}/nacharbeit/pruefen`, { method: "POST", body: Object.assign({ uebernehmen: false }, ziel) }); }
      catch (e) { toast(e.message, true); return; }
      const z = r.zahlen;
      const offen = r.zeilen.filter((x) => x.status === "nacharbeit");
      const n = z.uebernehmbar, m = z.im_bestand;
      const label = n ? `${plural(n, "Artikel", "Artikel")} übernehmen` : m ? `${plural(m, "Zeile", "Zeilen")} als „schon im Bestand“ erledigen` : "";
      const titel = zugeordnet ? (label ? "Zugeordnet – übernehmen?" : "Zugeordnet") : ziel.angabe ? "Übernehmen" : "Erneut prüfen";
      dialog(`<h2>${titel}</h2>
        ${zugeordnet ? `<p>${plural(zugeordnet, "Zeile", "Zeilen")} zugeordnet.</p>` : ""}
        <p>${plural(z.zeilen, "Zeile", "Zeilen")} geprüft: <strong>${n} übernehmbar</strong>${m ? `, ${m} schon im Bestand` : ""}, ${z.nacharbeit} weiter offen.</p>
        ${austauschListe("Bitte beachten", r.hinweise.concat(faelligSaetze(r.faelligkeit)), "warnung")}
        ${offen.length ? `<details class="mat-auf" ${offen.length <= 10 ? "open" : ""}><summary>Weiter offen (${offen.length})</summary>
          <ul class="mat-na-offen">${offen.slice(0, 200).map((x) => `<li><strong>Nr. ${esc(x.id)}</strong> <span class="muted">(Zeile ${esc(x.nr)})</span>${gruendeHtml(x.gruende)}</li>`).join("")}</ul></details>` : ""}
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">${label ? "Abbrechen" : "Schließen"}</button>
          ${label ? `<button class="btn mat-knopf-umbruch" id="np-ok" type="button">${esc(label)}</button>` : ""}</div>`,
      (dlg, body) => {
        const ok = $("#np-ok", body);
        if (!ok) return;
        ok.onclick = async () => {
          ok.disabled = true;
          ok.textContent = "Wird übernommen …";
          let e;
          try { e = await api(`${API}/ordner/${fid}/nacharbeit/pruefen`, { method: "POST", body: Object.assign({}, ziel, { uebernehmen: true }) }); }
          catch (err) { toast(err.message, true); ok.disabled = false; ok.textContent = label; return; }
          const angelegt = e.zeilen.filter((x) => x.status === "angelegt");
          toast(angelegt.length ? `${plural(angelegt.length, "Artikel", "Artikel")} angelegt` : "Erledigt");
          dialog(`<h2>Übernommen</h2>
            <p>${plural(e.zahlen.angelegt, "Artikel", "Artikel")} angelegt${e.zahlen.im_bestand ? `, ${plural(e.zahlen.im_bestand, "Zeile", "Zeilen")} schon im Bestand` : ""}${e.zahlen.nacharbeit ? `, ${plural(e.zahlen.nacharbeit, "Zeile", "Zeilen")} weiter offen` : ""}.</p>
            ${austauschListe("Bitte beachten", e.hinweise, "warnung")}
            ${angelegt.length ? `<div class="mat-dlg-liste">${angelegtTabelle(angelegt, true)}</div><p class="help">${esc(IMPORT_NEUBESCHRIFTEN)}</p>` : ""}
            <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`);
          // #dlg dient allen Dialogen der Seite – die Breite gilt nur, solange dieses Ergebnis offen ist.
          if (angelegt.length && !dlg.classList.contains("mat-uebernommen")) {
            dlg.classList.add("mat-uebernommen");
            dlg.addEventListener("close", () => dlg.classList.remove("mat-uebernommen"), { once: true });
          }
          // Der Inhalt ist ersetzt – der Fokus geht auf den neuen Titel, nicht hinter den Dialog.
          const titel = $("h2", body);
          if (titel) { titel.tabIndex = -1; titel.focus(); }
          leisteNeu();
          nacharbeitLaden();
        };
      });
    }
    async function naVerwerfen() {
      const zeilen = naAuswahl();
      const n = naAnzahl();
      if (!n) return;
      if (!(await confirm(`${plural(n, "Zeile", "Zeilen")} verwerfen? Sie verschwinden aus der Nacharbeit; ihre Werte werden gelöscht.`, "Verwerfen"))) return;
      try {
        const r = await api(`${API}/ordner/${fid}/nacharbeit/verwerfen`, { method: "POST", body: { zeilen } });
        toast(`${plural(r.verworfen, "Zeile", "Zeilen")} verworfen`);
        nacharbeitLaden();
      } catch (e) { toast(e.message, true); }
    }

    aktionen = {
      "bi-reiter": (b) => { reiter = b.dataset.r; bis = IMPORT_SEITE; berichtZeichnen(); },
      "bi-weitere": () => { bis += IMPORT_SEITE; berichtZeichnen(); },
      "bi-spalten": () => { spaltenAuf = true; berichtZeichnen(); },
      "bi-wiederholen": () => probelauf(),
      "bi-automatisch": () => { wahl = {}; probelauf(); },
      "bi-uebernehmen": () => uebernehmen(),
      "bi-neu": () => {
        clearTimeout(ruhe); ruhe = null;
        if (lauf) { lauf.abort(); lauf = null; }
        datei = null; wahl = {}; bericht = null; fertig = false; fehler = null; reiter = null; spaltenAuf = null; ohneSerie = false;
        $("#bi-name").textContent = "Excel-Arbeitsmappe (.xlsx) oder CSV, höchstens 5 MB.";
        berichtZeichnen();
        $("#bi-datei").click();
      },
      "na-filter": (b) => { naGruppe = b.dataset.g; nacharbeitLaden(); },
      "na-weitere": (b) => naMehr(b),
      "na-alle-offen": () => {
        naAlle = true;
        $$(".mat-na-wahl", naBox).forEach((x) => { x.checked = true; naWahl.add(+x.value); });
        naSammel();
      },
      "na-gruppe-zuordnen": (b) => {
        const g = na.gruppen[+b.dataset.i];
        const ueber = !g.produkt && g.zugeordnet ? ` Das ersetzt die zeilenweise Zuordnung (${plural(g.zugeordnet, "Zeile", "Zeilen")}) – für verschiedene Größen oder Varianten die Zeilen unten einzeln zuordnen.` : "";
        zuordnenDialogNa(`Produkt zuordnen: ${angabeAus(g) || "ohne Angabe"}`,
          `Gilt für ${g.offen === 1 ? "die Zeile" : `alle ${g.offen} offenen Zeilen`} dieser Angabe.${ueber} Danach kannst du sie gleich übernehmen.`,
          g.vorschlaege || [], { angabe: g.angabe }, g.produkt || g.zugeordnet);
      },
      "na-zeilen-zuordnen": () => {
        const n = naAnzahl();
        if (!n) return;
        zuordnenDialogNa(`Produkt zuordnen: ${plural(n, "Zeile", "Zeilen")}`,
          "Etwa für eine Größe oder Variante. Danach kannst du sie gleich übernehmen.", [], { zeilen: naAuswahl() },
          naZeilen.some((x) => x.produkt && (naAlle || naWahl.has(x.id))));
      },
      "na-melden": (b) => {
        const g = na.gruppen[+b.dataset.i];
        meldungDialog({ manufacturer: g.hersteller, model: g.modell, article_no: g.artikelnummer, note: g.meldung_bemerkung,
                        angabe: g.angabe, url: `${API}/ordner/${fid}/nacharbeit/melden` }, () => nacharbeitLaden());
      },
      "na-anlegen": (b) => {
        const g = na.gruppen[+b.dataset.i];
        produktDialog({ manufacturer: g.hersteller, model: g.modell, article_no: g.artikelnummer }, {
          danach: async (p) => {
            const r = await api(`${API}/ordner/${fid}/nacharbeit/produkt`, { method: "POST", body: { angabe: g.angabe, product_id: p.id } });
            await nacharbeitLaden();
            nachpruefen({ angabe: g.angabe }, r.gesetzt);
          } });
      },
      "na-pruefen": () => nachpruefen(),
      "na-uebernehmen": (b) => nachpruefen({ angabe: na.gruppen[+b.dataset.i].angabe }),
      "na-verwerfen": () => naVerwerfen(),
    };
    await nacharbeitLaden();
  }

  /* --- Meine PSA und Mangelmeldung (Phase 3 · Lieferung 1) ------------------------------------------------------
     „Meine PSA“ (/materialablage/meine-psa[/<iid>]) zeigt jedem Konto mit Namen die Ausrüstung, die ihm zugeordnet ist – auch
     ohne Modulstufe; dann fehlen Modulnavigation und Ordnerleiste (seite.html, nur_psa), und diese Ansicht braucht
     keine von beiden. Je Artikel eine Karte mit genau dem, was die Schnittstelle liefert (psa.artikel_json). Den Mangel
     melden die zugeordnete Person und jeder mit Leserecht am Artikel – hier und auf der Artikelseite im selben Dialog.
     Jede Meldung sperrt sofort; die Texte sagen überall dasselbe: beiseitelegen und dem Materialwart geben. */
  const MANGEL_MAX_FOTOS = 3;                       // mangel.MAX_FOTOS
  const MANGEL_TEXT_MAX = 2000;                     // mangel.TEXT_MAX
  // Anfang von mangel.MANGEL_NEU: Eine Meldung kam während der Prüfung – die Prüfung wird neu geladen.
  const MANGEL_NEU_ANFANG = "Am Artikel ist ein gemeldeter Mangel offen, den du nicht als geprüft abgehakt hast";
  const LAENGE_GEAENDERT_ANFANG = "Die Länge am Artikel wurde während der Prüfung";
  const BEISEITE = "Leg ihn sofort beiseite (aus Fahrzeug oder Lager) und gib ihn deinem Materialwart.";
  const mangelMarke = (x) => (x ? ' <span class="mat-mangel-marke" title="Mangel gemeldet">Mangel</span>' : "");
  // Ein Prüfer hat die Aussonderung des gesperrten Artikels empfohlen (Schritt 28) – aussondern kann der Materialwart.
  // Als Statusfilter im Bestand (A4) heißt sie EMPFOHLEN (bestand.EMPFOHLEN).
  const EMPFOHLEN = "aussonderung_empfohlen";
  const statusName = (st) => (st === EMPFOHLEN ? "Aussonderung empfohlen" : STATUS[st] || st);
  const empfohlenMarke = (x) => (x ? ' <span class="mat-empfohlen-marke">Aussonderung empfohlen</span>' : "");
  const tagZeit = (iso) => fmtZeit(iso).replace(",", "");         // „20.10.2026 13:05“ in der Zeit des Browsers
  // Fotos einer Meldung: Vorschau, groß die Webfassung – ein Original gibt es nicht (F4), „Original“ zeigt dieselbe.
  const mangelFotos = (m, titel) => ((m.fotos || []).length ? `<div class="mat-mangel-fotos">${m.fotos.map((f, i) => bildLink(f.web, f.web,
    `${titel} – Foto ${i + 1}`, `mangel-${m.id}`, `<img class="mat-mini" src="${esc(f.vorschau)}" alt="">`,
    `Foto ${i + 1} zur Mangelmeldung groß zeigen`)).join("")}</div>` : "");

  // Nach dem Melden steht oben, was geschah – der Toast allein ist am Telefon schnell weg.
  let quittung = "";
  const quittungHtml = () => { const q = quittung; quittung = ""; return q ? `<p class="notice mat-mangel-quittung" role="status" tabindex="-1">${esc(q)}</p>` : ""; };
  function mangelQuittung(r) {
    const was = r.gesperrt ? "der Artikel ist gesperrt" : "der Artikel war schon gesperrt";
    // „unterwegs“: Die Mail geht im Hintergrund hinaus – ob der Mailserver sie annimmt, steht erst im Log.
    return r.mail ? `Gemeldet – ${was}. Die Mail an Materialwart und Prüfer ist unterwegs. Leg ihn beiseite und gib ihn deinem Materialwart.`
      : `Gemeldet – ${was}. Es ging keine Mail hinaus – sag deinem Materialwart Bescheid und gib ihm den Artikel.`;
  }

  /* Dialog „Mangel melden“ (Meine PSA und Artikelseite). a: {id, inventory_no}; danach(antwort, text) zeichnet neu.
     Fotos ohne capture: Das Telefon bietet Kamera oder Galerie an, am Rechner öffnet sich die Dateiauswahl. Jede Wahl
     hängt an die Liste an, die Eingabe wird danach geleert – so lassen sich drei Fotos nacheinander aufnehmen; mehr als
     drei nimmt die Liste nicht. „Auswahl entfernen“ leert sie. Rot gefüllt ist nur „Melden und sperren“ – die eine
     Hauptaktion (btn, nicht btn danger: Die Sperre hebt eine Freiprüfung wieder auf; Entscheidung vom 23.10.2026, L2b). */
  function mangelDialog(a, danach) {
    const fotos = [];
    dialog(`<h2>Mangel melden – ${esc(a.inventory_no)}</h2>
      <p class="mat-mangel-warnung"><strong>Mit dem Melden wird der Artikel sofort gesperrt.</strong> ${BEISEITE} Freigeben kann ihn nur ein Prüfer nach einer Prüfung.</p>
      <label for="mg-text">Was ist dir aufgefallen? <span class="mat-pflicht" aria-hidden="true">*</span></label>
      <textarea id="mg-text" rows="5" maxlength="${MANGEL_TEXT_MAX}" required aria-required="true" aria-describedby="mg-text-fehler mg-text-hilfe"
        placeholder="Was ist passiert, was siehst du – und wo liegt er jetzt?"></textarea>
      <p class="help" id="mg-text-hilfe">Mit Beschreibung und Fotos – Materialwarte und Prüfer bekommen eine Mail.</p>
      <p class="error mat-feld-fehler" id="mg-text-fehler" hidden></p>
      <div class="mat-feldkopf" id="mg-fotos-kopf">Fotos (bis zu ${MANGEL_MAX_FOTOS})</div>
      <div class="mat-mangel-fotowahl" role="group" aria-labelledby="mg-fotos-kopf">
        <div class="mat-dateiwahl"><label class="btn secondary mat-bildwahl-knopf">Foto hinzufügen<input type="file"
            id="mg-fotos" accept="image/*" multiple class="mat-datei" aria-describedby="mg-fotos-stand"></label>
          <span class="mat-dateiwahl-name" id="mg-fotos-stand" aria-live="polite"></span>
          <button type="button" class="btn secondary mat-dateiwahl-weg" id="mg-fotos-weg" hidden>Auswahl entfernen</button></div>
        <ol class="mat-fotoliste" id="mg-fotos-liste" hidden></ol>
      </div>
      <p class="help">Dein Name steht bei der Meldung.</p>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="mg-ok" type="button">Melden und sperren</button></div>`,
    (dlg, body) => {
      const text = $("#mg-text", body);
      const fehler = $("#mg-text-fehler", body);
      const eingabe = $("#mg-fotos", body);
      const weg = $("#mg-fotos-weg", body);
      fokus(text);
      function zeichnen() {
        const ol = $("#mg-fotos-liste", body);
        ol.innerHTML = fotos.map((f) => `<li><span class="mat-fotoliste-name">${esc(f.name)}</span> <span class="muted small">${esc(groesse(f.size))}</span></li>`).join("");
        ol.hidden = !fotos.length;
        $("#mg-fotos-stand", body).textContent = !fotos.length ? "keine Fotos gewählt"
          : fotos.length >= MANGEL_MAX_FOTOS ? `${MANGEL_MAX_FOTOS} von ${MANGEL_MAX_FOTOS} Fotos – mehr gehen nicht` : `${plural(fotos.length, "Foto", "Fotos")} gewählt`;
        weg.hidden = !fotos.length;
        $(".mat-bildwahl-knopf", body).classList.toggle("voll", fotos.length >= MANGEL_MAX_FOTOS);
        eingabe.disabled = fotos.length >= MANGEL_MAX_FOTOS;
      }
      eingabe.addEventListener("change", () => {
        let zuviel = false;
        Array.from(eingabe.files).forEach((f) => {
          const endung = (f.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
          if (!FOTO_ENDUNGEN.includes(endung)) { toast(`„${f.name}“ ist kein Foto (JPEG, PNG, WebP, HEIC oder TIFF).`, true); return; }
          if (f.size > FOTO_MAX_BYTES) { toast(`„${f.name}“ ist größer als ${FOTO_MAX_BYTES / 1048576} MB.`, true); return; }
          if (fotos.length >= MANGEL_MAX_FOTOS) { zuviel = true; return; }
          fotos.push(f);
        });
        if (zuviel) toast(`Höchstens ${MANGEL_MAX_FOTOS} Fotos.`, true);
        eingabe.value = "";                 // dieselbe Datei (oder das nächste Kamerafoto) löst wieder ein change aus
        zeichnen();
      });
      weg.addEventListener("click", () => { fotos.length = 0; zeichnen(); eingabe.focus(); });
      text.addEventListener("input", () => { if (text.value.trim()) { fehler.hidden = true; text.classList.remove("ungueltig"); text.removeAttribute("aria-invalid"); } });
      zeichnen();
      $("#mg-ok", body).onclick = async (ev) => {
        const knopf = ev.currentTarget;
        if (!text.value.trim()) {
          fehler.textContent = "Bitte beschreib, was dir aufgefallen ist.";
          fehler.hidden = false;
          text.classList.add("ungueltig");
          text.setAttribute("aria-invalid", "true");
          text.focus();
          return;
        }
        const fd = new FormData();
        fd.append("beschreibung", text.value);
        fotos.forEach((f) => fd.append("fotos", f));
        knopf.disabled = true;
        knopf.textContent = "Wird gemeldet …";
        try {
          const r = await api(`${API}/artikel/${a.id}/mangel`, { method: "POST", body: fd });
          dlg.close();
          const q = mangelQuittung(r);
          toast(q);
          if (danach) await danach(r, q);
          // Nach dem Neuzeichnen stünde der Fokus auf body – die Quittung oben bekommt ihn (Tastatur, Vorlesehilfe).
          const qEl = $(".mat-mangel-quittung");
          if (qEl) qEl.focus();
        } catch (e) {
          toast(e.status === 413 ? "Die Fotos sind zusammen zu groß – bitte weniger oder kleinere wählen." : e.message, true);
          knopf.disabled = false;
          knopf.textContent = "Melden und sperren";
        }
      };
    });
  }

  // Banner am Artikel: je offener Meldung ein roter Kasten (unter dem GESPERRT-Banner, wenn ein anderer Grund sperrt). Text, Fotos und Melder schickt der
  // Server nur Prüfern und Materialwarten des Artikels und dem Melder selbst (inhalt; Entscheidung vom 21.10.2026) – wer
  // nur liest, sieht den Zeitpunkt und den Satz MANGEL_VERBORGEN.
  const MANGEL_VERBORGEN = "Was gemeldet wurde, sehen nur Prüfer und Materialwart.";
  const mangelText = (m, klasse) => (m.inhalt ? `<p class="${klasse}">${esc(m.description)}</p>` : `<p class="${klasse} mat-mangel-verborgen">${MANGEL_VERBORGEN}</p>`);
  // Die erledigende Freiprüfung wurde später berichtigt und gibt nicht mehr frei – die Meldung ist wieder offen.
  const wiederOffen = (m) => (m.wieder_offen ? `<p class="mat-mangel-zeile mat-mangel-wieder"><a href="/materialablage/pruefung/${Number(m.wieder_offen.berichtigung)}">Freiprüfung später berichtigt</a> (jetzt: ${esc(ERGEBNIS[m.wieder_offen.ergebnis] || m.wieder_offen.ergebnis)}) – die Meldung ist wieder offen, die nächste Freiprüfung hakt sie ab.</p>` : "");

  /* Ein langer Mangeltext (ab MANGEL_LANG Zeichen) steht im Banner der Artikelseite eingeklappt: der Anfang bis zum
     letzten Wortende vor MANGEL_ANFANG Zeichen, „ …“, darunter „Weiterlesen“ – der Knopf zeigt den Rest an Ort und Stelle
     und klappt ihn mit „Weniger anzeigen“ wieder zu (Reste vor dem finalen Test, 1; Teil A, Bitte bestätigen 4: eine
     Beschreibung mit 1 852 Zeichen schob am Telefon den Artikel um mehrere Bildschirme nach unten). Bis dahin ist der Rest
     hidden, auch für Vorlesehilfen – der Knopf sagt mit aria-expanded, dass mehr kommt. Kürzere Texte wie bisher. */
  const MANGEL_LANG = 600, MANGEL_ANFANG = 400;
  function mangelTextKurz(m, klasse) {
    const t = m.inhalt ? String(m.description || "") : "";
    if (t.length < MANGEL_LANG) return mangelText(m, klasse);
    const leer = Math.max(t.lastIndexOf(" ", MANGEL_ANFANG), t.lastIndexOf("\n", MANGEL_ANFANG));
    let schnitt = leer > MANGEL_ANFANG / 2 ? leer : MANGEL_ANFANG;
    if (/[\uD800-\uDBFF]/.test(t[schnitt - 1])) schnitt -= 1;       // kein halbes Zeichen (Emoji) am Schnitt
    const id = `mangel-text-${Number(m.id)}`;
    return `<p class="${klasse}" id="${id}">${esc(t.slice(0, schnitt))}<span class="mat-mangel-punkte" aria-hidden="true"> …</span><span class="mat-mangel-rest" hidden>${esc(t.slice(schnitt))}</span></p>
      <p class="mat-mangel-mehr"><button type="button" class="btn secondary small" data-act="mangel-weiterlesen" aria-expanded="false" aria-controls="${id}">Weiterlesen</button></p>`;
  }
  function mangelWeiterlesen(b) {
    const text = document.getElementById(b.getAttribute("aria-controls"));
    if (!text) return;
    const auf = b.getAttribute("aria-expanded") !== "true";
    $(".mat-mangel-rest", text).hidden = !auf;
    $(".mat-mangel-punkte", text).hidden = auf;
    b.setAttribute("aria-expanded", String(auf));
    b.textContent = auf ? "Weniger anzeigen" : "Weiterlesen";
  }

  // sperre: Sperrgrund aus einem anderen Grund als dem Mangel (Text, auch leer) – dann steht er als Zeile darin; null: nichts.
  function mangelBanner(m, sperre) {
    return `<div class="mat-banner mat-mangel-banner" role="note">
      <p class="mat-mangel-titel">MANGEL GEMELDET am ${esc(tagZeit(m.created_at))}${m.melder ? ` · von ${person(m.melder)}` : ""}</p>
      ${sperre === null || sperre === undefined ? "" : `<p class="mat-mangel-sperre"><strong>Außerdem gesperrt</strong>${sperre ? `: ${esc(sperre)}` : ""}.</p>`}
      ${mangelTextKurz(m, "mat-text mat-mangel-text")}
      ${mangelFotos(m, `Mangel vom ${S.fmtDate(m.created_at)}`)}
      ${wiederOffen(m)}
      <p class="mat-mangel-zeile">Nicht verwenden – beiseitelegen und beim Materialwart abgeben. Freigeben kann ihn nur ein Prüfer mit einer Prüfung („einsatzbereit“).</p></div>`;
  }

  // Erledigte Meldungen am Artikel: eingeklappt unter „Prüfungen“ – wann, wer (wenn sichtbar), was, und wodurch erledigt.
  function mangelErledigt(liste) {
    if (!liste.length) return "";
    return `<section class="section"><h2>Gemeldete Mängel</h2><details class="mat-mangel-alt"><summary>${plural(liste.length, "erledigte Meldung", "erledigte Meldungen")}</summary>
      <ul class="mat-mangel-liste">${liste.map((m) => `<li><p class="small"><strong>${esc(tagZeit(m.created_at))}</strong>${m.melder ? ` · ${person(m.melder)}` : ""}
          · erledigt am ${esc(S.fmtDate(m.erledigt.am))} durch <a href="/materialablage/pruefung/${Number(m.erledigt.pruefung)}">${m.erledigt.art === "aussonderung" ? "Aussonderung" : "Freiprüfung"}</a></p>
        ${mangelText(m, "mat-text")}${mangelFotos(m, `Mangel vom ${S.fmtDate(m.created_at)}`)}</li>`).join("")}</ul></details></section>`;
  }

  // Hinweis in der Prüfung (Start und Entwurf): je offener Meldung, mit Text und Fotos.
  function mangelHinweis(liste, berichtigung) {
    return (liste || []).map((m) => `<div class="mat-banner mat-mangel-banner" role="note">
      <p class="mat-mangel-titel">GEMELDETER MANGEL vom ${esc(tagZeit(m.created_at))}${m.melder ? ` (von ${person(m.melder)})` : ""}</p>
      ${mangelText(m, "mat-text mat-mangel-text")}
      ${mangelFotos(m, `Mangel vom ${S.fmtDate(m.created_at)}`)}
      ${wiederOffen(m)}
      <p class="mat-mangel-zeile">${berichtigung ? "Eine Berichtigung gibt den Artikel nicht frei – dafür braucht es eine neue Prüfung."
        : "Mit „einsatzbereit“ hebst du die Sperre auf (Freiprüfung) und erledigst die Meldung."}</p></div>`).join("");
  }

  // Übersicht, oben: Meldungen, nach denen noch kein Prüfer geprüft hat (nach „instandsetzen“ fallen sie heraus). Wer
  // nur liest, sieht Artikel und Tag – Kurztext, Fotozahl und Melder fehlen dann (inhalt false).
  function mangelKasten(liste, gesamt) {
    if (!liste || !liste.length) return "";
    return `<section class="section mat-mangel-kasten" aria-label="Gemeldete Mängel"><h2>Gemeldete Mängel</h2>
      <p class="help">Gesperrt durch eine Meldung und seitdem von keinem Prüfer geprüft.</p>
      <ul class="mat-rr-liste">${liste.map((m) => `<li>
        <span class="mat-mangel-marke">Mangel</span>
        <span class="mat-rr-was"><a href="/materialablage/artikel/${Number(m.item_id)}"><strong>${esc(m.inventory_no)}</strong></a> · ${nameHtml(m.produkt)}${zusatzHtml(m.produkt)}</span>
        ${m.inhalt ? `<span class="mat-mangel-kurz">${esc(m.kurz)}</span>` : ""}
        <span class="small">gemeldet am ${esc(S.fmtDate(m.created_at))}${m.melder ? ` · ${person(m.melder)}` : ""}${m.fotos ? ` · ${plural(m.fotos, "Foto", "Fotos")}` : ""}</span></li>`).join("")}</ul>
      ${gesamt > liste.length ? `<p class="small"><a href="/materialablage/pruefungen?status=gesperrt">… und ${gesamt - liste.length} weitere</a></p>` : ""}</section>`;
  }

  // Übersicht, unten: die eigene PSA (für jeden mit Modulzugang und Zuordnung).
  const psaKasten = (k) => (k ? `<p class="notice mat-psa-kasten${k.dringend ? " dringend" : ""}">Dir ${k.anzahl === 1 ? "ist 1 Artikel" : `sind ${k.anzahl} Artikel`} zugeordnet${k.dringend
    ? ` – davon ${k.dringend} nicht einsatzbereit` : ""}. <a href="/materialablage/meine-psa">Meine PSA ansehen →</a></p>` : "");

  /* Eine Karte in „Meine PSA“. Banner oben (Mangel, Sperre, überfällig, Lebensdauer, neu, DEMO) – mit dem, was die
     Person tun soll; dann Bild, Nummern, Daten, Dokumente, Rückruf, die eigenen Meldungen und „Mangel melden“. */
  // Das Banner einer Karte – höchstens eins, das dringendste.
  function psaBanner(k) {
    if (k.mangel) return ["mat-mangel-banner", `Mangel gemeldet am ${S.fmtDate(k.mangel.seit)} – nicht verwenden. Bring sie deinem Materialwart; ein Prüfer muss sie ansehen.`];
    if (k.verloren) return ["s-gesperrt", "Als verloren gemeldet – taucht sie wieder auf: nicht verwenden, gib sie deinem Materialwart."];
    if (k.gesperrt) return ["s-gesperrt", "GESPERRT – nicht verwenden. Leg sie beiseite und gib sie deinem Materialwart."];
    if (k.status === "ueberfaellig") return ["mat-psa-ueberfaellig", "PRÜFUNG ÜBERFÄLLIG – nicht verwenden, bis sie geprüft ist. Gib sie deinem Materialwart."];
    if (k.status === "lebensdauer") return ["s-lebensdauer", "LEBENSDAUER ERREICHT – nicht mehr verwenden, gib sie deinem Materialwart."];
    if (k.status === "neu") return ["s-neu", "NEU – die Eingangsprüfung steht aus. Bis dahin nicht verwenden."];
    return null;
  }
  const psaNaechste = (k) => (k.gesperrt ? '<span class="muted">nach Freigabe durch einen Prüfer</span>'
    : k.status === "neu" ? "<strong>Eingangsprüfung ausstehend</strong>"
      : k.next_due_on ? `<strong${k.status === "ueberfaellig" ? ' class="mat-warn"' : ""}>${esc(fmtTag(k.next_due_on))}</strong>` : '<span class="muted">–</span>');
  function psaKarte(k, einzeln) {
    const p = k.produkt;
    const name = produktName(p);
    const banner = [psaBanner(k)].filter(Boolean);
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    const naechste = psaNaechste(k);
    const offen = k.eigene_maengel.some((m) => m.offen);
    // Inventarnummer nie am Bindestrich umbrechen („M-⏎000005“; Browserprüfung vor dem Merge, Verbesserung 10).
    const inv = einzeln ? `<span class="mat-inv">${esc(k.inventory_no)}</span>` : `<a class="mat-inv" href="/materialablage/meine-psa/${Number(k.id)}">${esc(k.inventory_no)}</a>`;
    return `<article class="mat-psa-karte s-${esc(k.status)}${k.mangel ? " mit-mangel" : ""}" aria-labelledby="psa-${Number(k.id)}">
      ${k.demo ? `<p class="mat-demo-banner">${DEMO_ARTIKEL}</p>` : ""}
      ${banner.map(([cls, t]) => `<p class="mat-banner ${cls}" role="note">${esc(t)}</p>`).join("")}
      <div class="mat-psa-kopf">
        ${p.bild && p.vorschau ? bildLink(p.bild, p.bild, `Produktbild ${name}`, null, `<img class="mat-psa-bild" src="${esc(p.vorschau)}" alt="">`, `Produktbild groß zeigen: ${name}`)
          : '<div class="mat-psa-bild leer" aria-hidden="true">kein Bild</div>'}
        <div class="mat-psa-titel">
          <h2 id="psa-${Number(k.id)}">${inv} ${statusMarke(k.status)}</h2>
          <p class="mat-produktzeile"><strong>${nameHtml(p)}</strong>${zusatzHtml(p)}${artNrHtml(p.article_no)}</p>
          <p class="small">${nummerHtml("Seriennummer", k.serial_no)}${k.serial_generated ? ' <span class="muted">(vom System)</span>' : ""}</p>
        </div>
      </div>
      <dl class="mat-daten mat-psa-daten">
        ${zeile("Nächste Prüfung", naechste)}
        ${k.retire_by ? zeile("Lebensende", `${k.status === "lebensdauer" ? '<strong class="mat-warn">' : ""}${esc(fmtTag(k.retire_by))}${k.status === "lebensdauer" ? "</strong>" : ""}`) : ""}
        ${k.length_m ? zeile("Länge", esc(laengeText(k.length_m))) : ""}
        ${(k.bestandteile || []).length ? zeile("Bestandteile", bestandteilZeilen(k.bestandteile, true)) : ""}
        ${zeile("Zuletzt geprüft", k.last_inspected_on ? esc(fmtTag(k.last_inspected_on)) : '<span class="muted">noch nie</span>')}
        ${k.gliederung ? zeile("Gliederung", esc(k.gliederung)) : ""}
        ${k.gesperrt && k.lock_reason ? zeile("Sperrgrund", esc(k.lock_reason)) : ""}
        ${k.notes ? zeile("Bemerkung", `<span class="mat-text">${esc(k.notes)}</span>`) : ""}
      </dl>
      ${k.rueckruf.map((t) => `<p class="mat-psa-rueckruf"><span class="mat-rr-marke">Rückruf</span> Rückruf des Herstellers: ${esc(t)} – bitte deinem Materialwart zeigen.</p>`).join("")}
      ${k.dokumente.length ? `<div class="mat-psa-doks"><h3 class="mat-unter">Dokumente</h3><ul class="mat-doks">${k.dokumente.map((d) => `<li>${d.datei || d.url
        ? `<a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>` : esc(d.title)} <span class="muted">${esc(DOKART[d.kind] || d.kind)}</span></li>`).join("")}</ul></div>` : ""}
      ${k.eigene_maengel.length ? `<details class="mat-psa-meldungen"><summary>Deine Meldungen (${k.eigene_maengel.length})</summary>
        <ul class="mat-mangel-liste">${k.eigene_maengel.map((m) => `<li><p class="small"><strong>${esc(tagZeit(m.created_at))}</strong>
            <span class="mat-rr-zustand ${m.offen ? "offen" : "erledigt"}">${m.offen ? "offen" : "erledigt"}</span></p>
          <p class="mat-text">${esc(m.description)}</p>${mangelFotos(m, `Deine Meldung vom ${S.fmtDate(m.created_at)}`)}</li>`).join("")}</ul></details>` : ""}
      ${offen ? `<p class="help" id="psa-schon-${Number(k.id)}">Du hast schon gemeldet – ein Prüfer sieht es sich an. Ergänzungen bitte direkt an den Materialwart.</p>` : ""}
      <div class="btn-row mat-psa-knoepfe">
        <button class="btn secondary" type="button" data-act="mangel" data-id="${Number(k.id)}"${offen ? ' disabled aria-describedby="psa-schon-' + Number(k.id) + '"' : ""}>Mangel melden</button>
        ${k.artikel_link ? `<a href="/materialablage/artikel/${Number(k.id)}">Zum Artikel</a>` : ""}</div>
    </article>`;
  }

  async function meinePsa() {
    const d = await api(`${API}/meine-psa`);
    const einzeln = Boolean(DATEN.id);
    const karten = einzeln ? d.artikel.filter((k) => k.id === DATEN.id) : d.artikel;
    const kopf = `${einzeln ? '<p class="mat-psa-zurueck"><a href="/materialablage/meine-psa">← Alle meine PSA</a></p>' : ""}
      <div class="page-head"><h1>Meine PSA</h1></div>
      <p class="help">Ausrüstung, die dir persönlich zugeordnet ist. Vor jedem Gebrauch ansehen; was dir auffällt, meldest du hier – und gibst sie deinem Materialwart.</p>`;
    const liste = karten.length ? `<div class="mat-psa-liste${einzeln ? " einzeln" : ""}">${karten.map((k) => psaKarte(k, einzeln)).join("")}</div>`
      : einzeln ? leer("Dieser Artikel ist dir nicht (mehr) zugeordnet – oder er steht nicht unter den ersten in deiner Liste.")
        : leer("Dir ist keine Ausrüstung zugeordnet. Das macht der Materialwart deiner Gliederung.");
    inhalt.innerHTML = `${quittungHtml()}${kopf}${liste}
      ${!einzeln && d.gesamt > d.artikel.length ? `<p class="notice">… und ${d.gesamt - d.artikel.length} weitere – frag deinen Materialwart.</p>` : ""}
      ${d.gesamt || !d.mails ? `<p class="help mat-psa-mails">Erinnerungen per Mail: ${d.mails ? "an" : "aus"} – <a href="/profil#psa">im Profil ändern</a></p>` : ""}`;
    aktionen = {
      mangel: (b) => {
        const k = d.artikel.find((x) => x.id === +b.dataset.id);
        if (!k || b.disabled) return;
        mangelDialog(k, (r, q) => { quittung = q; return zeigen(meinePsa); });
      },
    };
  }

  /* Nach einem QR-Scan an einem Artikel außerhalb des eigenen Bereichs (/m/<token>): Die Seite enthält nichts über ihn,
     den Steckbrief gibt es erst nach Bestätigung (global.js; DATEN ist genau {token}). */
  async function fremd() {
    const g = await baustein("MatGlobal");
    if (g) g.fremd(inhalt, DATEN);
    else inhalt.innerHTML = leer("Dieser Artikel gehört nicht zu deinem Bereich.");
  }

  const ANSICHTEN = { dashboard, pruefungen, bestand, ordner, artikel, artikel_neu: artikelNeu, katalog, produkt, formular, suche,
                      meldungen, pruefung_neu: pruefungNeu, pruefung: pruefungAnsicht, durchgang: durchgangAnsicht, durchgaenge: durchgaengeArchiv, fremd,
                      meine_psa: meinePsa, bestandsimport, bericht, antraege: antraegeSeite };
  leisteLaden();
  zeigen(ANSICHTEN[ANSICHT] || dashboard);
})();
