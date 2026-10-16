/* Modul Material – Oberfläche aller Ansichten: Übersicht, fällige Prüfungen, Bestand (Ordnerbaum mit
   Systemordnern und Mehrfachauswahl), Artikel mit Lebenslauf-Journal, Artikel anlegen, Katalog mit
   Produkten, Dokumenten und Prüfformularen, Suche nach Nummern.
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

  const STATUS = { einsatzbereit: "einsatzbereit", bald_faellig: "bald fällig", ueberfaellig: "überfällig",
                   gesperrt: "gesperrt", lebensdauer: "Lebensdauer erreicht", ausgesondert: "ausgesondert" };
  const STATUS_REIHE = ["ueberfaellig", "lebensdauer", "gesperrt", "bald_faellig", "einsatzbereit", "ausgesondert"];
  const MATERIALART = { textil: "textil", metall_hardware: "Metall/Hardware", sonstiges: "sonstiges" };
  const ORDNERART = { gliederung: "Gliederung", standort: "Standort", fahrzeug: "Fahrzeug", set: "Set",
                      persoenlich: "persönlich", sonstiges: "sonstiges" };
  const DOKART = { produktbild: "Produktbild", konformitaetserklaerung: "Konformitätserklärung",
                   gebrauchsanleitung: "Gebrauchsanleitung", pruefanweisung: "Prüfanweisung", datenblatt: "Datenblatt",
                   sonstiges: "Sonstiges" };
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
  };
  const AKTION = { angelegt: "angelegt", geaendert: "geändert", geloescht: "gelöscht", verschoben: "verschoben",
                   bild: "Bild geändert", foto: "Foto geändert", neue_version: "neue Version", zurueckgezogen: "zurückgezogen",
                   aktiviert: "aktiviert", deaktiviert: "deaktiviert", lebensende: "Lebensende nachgezogen", rollen: "Rollen" };
  const ENTITAET = { item: "Artikel", product: "Produkt", document: "Dokument", form: "Formular", folder: "Ordner",
                     category: "Kategorie", user: "Konto", inspection: "Prüfung", round: "Durchgang" };

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
                artikel_neu: "bestand", katalog: "katalog", produkt: "katalog", formular: "katalog", suche: "" };
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
    if (/_on$|^valid_from$|^retire_by$/.test(feld)) return esc(fmtTag(v));
    if (typeof v === "object") return esc(JSON.stringify(v));
    return esc(v);
  }
  function journalHtml(eintraege, mitEntitaet) {
    if (!eintraege || !eintraege.length) return leer("Noch keine Einträge.");
    return `<ol class="mat-journal">${eintraege.map((j) => {
      const felder = j.action === "angelegt" || j.action === "geloescht"
        ? [] : Object.keys(Object.assign({}, j.vorher || {}, j.nachher || {}));
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
      <div class="mat-kacheln">
        <div class="mat-kachel gesamt"><strong>${d.bestand}</strong><span>Artikel im Bestand</span></div>
        ${kachel("ueberfaellig", "überfällig")}${kachel("bald_faellig", `bald fällig (${d.schwelle_tage} Tage)`)}
        ${kachel("gesperrt", "gesperrt")}${kachel("lebensdauer", "Lebensdauer erreicht")}${kachel("einsatzbereit", "einsatzbereit")}
      </div>
      <section class="section"><h2>Gliederungen</h2>
        ${gl.length ? `<table class="list mat-tabelle"><thead><tr><th>Gliederung</th><th>Bestand</th><th>überfällig</th><th>bald fällig</th><th>gesperrt</th><th>Lebensdauer</th></tr></thead><tbody>
          ${gl.map((o) => `<tr><td data-l="Gliederung"><a href="/material/ordner/${o.id}">${esc(o.name)}</a>${demoMarke(o.demo)}</td>
            <td data-l="Bestand">${o.bestand}</td><td data-l="überfällig">${o.zaehlung.ueberfaellig || "–"}</td>
            <td data-l="bald fällig">${o.zaehlung.bald_faellig || "–"}</td><td data-l="gesperrt">${o.zaehlung.gesperrt || "–"}</td>
            <td data-l="Lebensdauer">${o.zaehlung.lebensdauer || "–"}</td></tr>`).join("")}</tbody></table>`
          : leer(DARF.verwalten ? "Noch keine Gliederung – lege unter „Bestand“ die erste an." : "Noch keine Gliederung angelegt.")}
      </section>
      <section class="section"><h2>Als Nächstes zu prüfen</h2>
        ${d.naechste.length ? artikelTabelle(d.naechste, { pfad: true }) + (d.faellig_gesamt > d.naechste.length ? `<p><a href="/material/pruefungen">Alle ${d.faellig_gesamt} anzeigen →</a></p>` : "")
          : leer("Nichts fällig.")}
      </section>`;
  }

  /* Artikelliste als Tabelle; mit auswahl:true bekommt jede Zeile ein Häkchen (Mehrfachauswahl). */
  function artikelTabelle(liste, opts) {
    opts = opts || {};
    return `<table class="list mat-tabelle mat-artikel">
      <thead><tr>${opts.auswahl ? '<th class="mat-wahlspalte"><input type="checkbox" id="mat-alle" aria-label="alle auswählen"></th>' : ""}
        <th>Inventar-Nr.</th><th>Produkt</th><th>Seriennummer</th>${opts.pfad ? "<th>Ablage</th>" : ""}<th>Nächste Prüfung</th><th>Status</th></tr></thead>
      <tbody>${liste.map((a) => `<tr data-id="${a.id}">
        ${opts.auswahl ? `<td class="mat-wahlspalte"><input type="checkbox" class="mat-wahl-art" value="${a.id}" ${a.lock_state !== "frei" ? 'disabled title="Gesperrte und ausgesonderte Artikel bleiben in ihrem Systemordner."' : ""} aria-label="${esc(a.inventory_no)} auswählen"></td>` : ""}
        <td data-l="Inventar-Nr."><a href="/material/artikel/${a.id}"><strong>${esc(a.inventory_no)}</strong></a></td>
        <td data-l="Produkt">${a.vorschau ? `<img class="mat-mini" src="${esc(a.vorschau)}" alt="" loading="lazy">` : ""}${esc(produktName(a))}${a.article_no ? ` <span class="muted">${esc(a.article_no)}</span>` : ""}${demoMarke(a.demo)}</td>
        <td data-l="Seriennummer">${esc(a.serial_no)}${a.serial_generated ? ' <span class="muted" title="vom System vergeben">(System)</span>' : ""}</td>
        ${opts.pfad ? `<td data-l="Ablage">${esc(a.pfad || "")}</td>` : ""}
        <td data-l="Nächste Prüfung">${a.next_due_on ? esc(fmtTag(a.next_due_on)) : '<span class="muted">–</span>'}</td>
        <td data-l="Status">${statusMarke(a.status)}</td></tr>`).join("")}</tbody></table>`;
  }

  /* --- Fällige Prüfungen ------------------------------------------------------------------------ */
  async function pruefungen() {
    const params = new URLSearchParams(location.search);
    let filter = params.get("status") || "ueberfaellig,bald_faellig";
    let seite = 1;
    const FILTER = [["ueberfaellig,bald_faellig", "fällig und überfällig"], ["ueberfaellig", "überfällig"],
                    ["bald_faellig", "bald fällig"], ["lebensdauer", "Lebensdauer erreicht"], ["gesperrt", "gesperrt"]];
    async function zeichnen() {
      const q = new URLSearchParams({ status: filter, seite, pro_seite: 50 });
      if (DATEN.ordner) q.set("ordner", DATEN.ordner);
      const d = await api(`${API}/faellig?${q}`);
      inhalt.innerHTML = `<div class="page-head"><h1>Prüfungen</h1></div>
        <p class="help">Was in den nächsten ${d.schwelle_tage} Tagen fällig wird oder schon überfällig ist. Prüfen lässt sich ab Lieferung 2 direkt aus dieser Liste.</p>
        <div class="c-tabs mat-filter">${FILTER.map(([f, t]) => `<button type="button" data-act="filter" data-f="${f}" class="${f === filter ? "sel" : ""}">${esc(t)}</button>`).join("")}</div>
        ${d.artikel.length ? artikelTabelle(d.artikel, { pfad: true }) : leer("Keine Artikel in dieser Auswahl.")}
        ${seitenleiste(d.gesamt, seite, 50)}`;
    }
    aktionen = {
      filter: (b) => { filter = b.dataset.f; seite = 1; history.replaceState(null, "", `?status=${filter}`); zeigen(zeichnen); },
      seite: (b) => { seite = +b.dataset.seite; zeigen(zeichnen); },
    };
    await zeichnen();
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
    async function zeichnen() {
      const q = new URLSearchParams({ seite, pro_seite: 200 });
      if (filter) q.set("status", filter);
      const d = (await api(`${API}/ordner/${id}?${q}`)).ordner;
      const system = !!d.system_kind;
      const darfPflegen = DARF.verwalten && !system;
      const z = d.zaehlung || {};
      const bc = d.pfad.map((p, i) => i === d.pfad.length - 1 ? `<span>${esc(p.name)}</span>` : `<a href="/material/ordner/${p.id}">${esc(p.name)}</a>`).join(" / ");
      inhalt.innerHTML = `<div class="mat-pfad"><a href="/material/bestand">Bestand</a> / ${bc}</div>
        <div class="page-head"><h1>${system ? "🔒 " : ""}${esc(d.name)} ${system ? "" : `<span class="mat-art">${esc(ORDNERART[d.kind])}</span>`}${demoMarke(d.demo)}</h1>
          <div class="btn-row">${darfPflegen ? `<button class="btn secondary small" data-act="unterordner">+ Unterordner</button>
            <a class="btn small" href="/material/artikel/neu?ordner=${d.id}">+ Artikel</a>
            <button class="btn ghost small" data-act="bearbeiten">Bearbeiten</button><button class="btn ghost small" data-act="foto">Foto</button>
            <button class="btn ghost small" data-act="verschieben">Verschieben</button><button class="btn ghost small" data-act="loeschen">Löschen</button>` : ""}</div></div>
        ${system ? `<p class="notice">${d.system_kind === "gesperrt" ? "Hierher verschiebt eine Sperre die Artikel der Gliederung. Zurück in ihren Herkunftsordner bringt sie nur eine Freiprüfung." : "Ausgesonderte Artikel bleiben hier mit ihrem vollen Lebenslauf sichtbar, zählen aber nirgends mehr als Bestand und lassen sich nicht zurückholen."}</p>` : ""}
        <div class="mat-ordnerkopf">${d.foto ? `<img class="mat-ordnerfoto" src="${esc(d.vorschau)}" alt="">` : ""}
          <div>${d.description ? `<p class="mat-text">${esc(d.description)}</p>` : ""}
          ${d.interval_months ? `<p class="small">Prüfintervall hier: höchstens ${d.interval_months} Monate.</p>` : ""}
          <p class="small">${system ? plural(Object.values(z).reduce((a, b) => a + b, 0), "Artikel", "Artikel") : `Bestand im ganzen Zweig: <strong>${d.bestand}</strong> ${zahlen(z)}`}</p></div></div>
        ${d.unterordner.length ? `<section class="section"><h2>Unterordner</h2>${unterordnerHtml(d.unterordner)}</section>` : ""}
        <section class="section"><h2>Artikel in diesem Ordner</h2>
          <div class="c-tabs mat-filter">${["", "ueberfaellig", "bald_faellig", "gesperrt", "lebensdauer", "einsatzbereit"].map((s) => `<button type="button" data-act="filter" data-f="${s}" class="${s === filter ? "sel" : ""}">${s ? esc(STATUS[s]) : "alle"}${s && d.direkt && d.direkt[s] ? ` (${d.direkt[s]})` : ""}</button>`).join("")}</div>
          ${d.artikel.length ? artikelTabelle(d.artikel, { auswahl: darfPflegen }) : leer(filter ? "Keine Artikel mit diesem Status." : "Hier liegen keine Artikel.")}
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
        unterordner: () => ordnerDialog({ kind: "standort" }, d.id),
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
        ev.currentTarget.disabled = true;
        try { await api(url, { method: "POST", body: fd }); dlg.close(); toast("Foto gespeichert"); await danach(); }
        catch (e) { toast(e.message, true); ev.currentTarget.disabled = false; }
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
    const p = a.produkt;
    const frei = a.lock_state === "frei";
    const darfPflegen = DARF.verwalten && a.lock_state !== "ausgesondert";
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
      <div class="mat-pfad">${bc}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? `<a href="${esc(p.original || p.bild)}" target="_blank" rel="noopener"><img class="mat-produktbild" src="${esc(p.bild)}" alt="Produktbild ${esc(produktName(p))}"></a>` : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel">
          <h1>${esc(a.inventory_no)} ${statusMarke(a.status, true)}</h1>
          <p class="mat-produktzeile"><a href="/material/katalog/produkt/${p.id}">${esc(produktName(p))}</a>${p.article_no ? ` · Art.-Nr. ${esc(p.article_no)}` : ""}</p>
          <p>Seriennummer <strong>${esc(a.serial_no)}</strong>${a.serial_generated ? ' <span class="badge grey" title="Der Hersteller vergibt keine Seriennummer – diese Nummer bitte dauerhaft am Artikel anbringen.">vom System vergeben</span>' : ""}</p>
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
          ${zeile("Nächste Prüfung", a.next_due_on ? `<strong>${esc(fmtTag(a.next_due_on))}</strong>` : '<span class="mat-warn">keine</span>')}
          ${zeile("Prüfintervall", ivText)}
          ${zeile("Prüfformular", a.formular ? `${esc(a.formular.title || "ohne Titel")} · Version ${a.formular.version} <span class="muted">(${esc(a.formular.quelle)}, ${plural(a.formular.punkte, "Prüfpunkt", "Prüfpunkte")})</span>` : '<span class="mat-warn">kein aktives Prüfformular – im Katalog anlegen</span>')}
          ${a.notes ? zeile("Bemerkung", `<span class="mat-text">${esc(a.notes)}</span>`) : ""}
        </dl></section>
        <section class="section"><h2>QR-Etikett</h2>
          <p class="help">Diese Adresse steht im QR-Code; derselbe Link lässt sich auf einen NFC- oder RFID-Tag schreiben. Die Kamera-App öffnet damit nach der Anmeldung diesen Artikel. Etikettenbögen kommen mit Lieferung 4.</p>
          <div class="mat-qr"><input type="text" readonly value="${esc(a.qr_adresse)}" id="mat-qr" aria-label="Adresse für QR, NFC und RFID">
          <button class="btn secondary small" data-act="qr-kopieren">Kopieren</button></div>
          <h2>Herstellerdokumente</h2>
          ${a.dokumente.length ? `<ul class="mat-doks">${a.dokumente.map((d) => `<li><a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a> <span class="muted">${esc(DOKART[d.kind] || d.kind)}${d.version ? `, ${esc(d.version)}` : ""}</span></li>`).join("")}</ul>` : leer("Am Produkt sind keine Dokumente hinterlegt.")}
        </section>
      </div>
      <section class="section"><h2>Prüfungen</h2>${leer("Noch keine Prüfungen. Prüfen, Sperren und Aussondern kommen mit Lieferung 2.")}</section>
      <section class="section"><h2>Journal</h2><p class="help">Änderungen am Artikel und an seinem Produkt, neueste zuerst.</p>${journalHtml(a.journal, true)}</section>`;
    aktionen = {
      "qr-kopieren": async () => {
        const feld = $("#mat-qr");
        try { await navigator.clipboard.writeText(feld.value); toast("Adresse kopiert"); }
        catch (e) { feld.select(); document.execCommand && document.execCommand("copy"); toast("Adresse markiert – mit Strg+C kopieren"); }
      },
      bearbeiten: () => artikelDialog(a),
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

  function artikelDialog(a) {
    const textil = a.produkt.material_kind === "textil";
    dialog(`<h2>Artikel ${esc(a.inventory_no)} bearbeiten</h2>
      <label for="ad-sn">Seriennummer des Herstellers</label><input type="text" id="ad-sn" value="${a.serial_generated ? "" : esc(a.serial_no)}" placeholder="${a.serial_generated ? esc(a.serial_no) + " (vom System)" : ""}" maxlength="80">
      <div class="help">Leer lassen behält die Nummer. Eine echte Herstellernummer ersetzt die vom System vergebene.</div>
      <div class="field-row"><div><label for="ad-herst">Herstellung (Monat${textil ? ", Pflicht" : ""})</label><input type="month" id="ad-herst" value="${esc((a.manufactured_on || "").slice(0, 7))}"></div>
        <div><label for="ad-kauf">Kauf</label><input type="date" id="ad-kauf" value="${esc(a.purchased_on || "")}"></div></div>
      <div class="field-row"><div><label for="ad-erst">Erstgebrauch</label><input type="date" id="ad-erst" value="${esc(a.first_use_on || "")}"></div>
        <div><label for="ad-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="ad-int" min="1" max="120" value="${a.interval_months || ""}" placeholder="vom Produkt/Ordner"></div></div>
      <div class="field-row"><div><label for="ad-due">Nächste Prüfung</label><input type="date" id="ad-due" value="${esc(a.next_due_on || "")}" max="${esc(a.next_due_on || "")}">
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
        const daten = { serial_no: $("#ad-sn", body).value, purchased_on: $("#ad-kauf", body).value || null,
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
    const kinder = baumKinder(wahl);
    const optionen = (pid, tiefe) => (kinder[pid] || []).map((o) => `<option value="${o.id}" ${o.id === DATEN.ordner ? "selected" : ""}>${EIN.repeat(tiefe)}${esc(o.name)}</option>${optionen(o.id, tiefe + 1)}`).join("");
    let produkt = null;
    inhalt.innerHTML = `<div class="page-head"><h1>Artikel anlegen</h1></div>
      <div class="mat-formular">
        <label for="an-q">Produkt aus dem Katalog</label>
        <div class="mat-produktwahl"><input type="search" id="an-q" placeholder="Hersteller, Modell, Artikelnummer …" autocomplete="off">
          <div id="an-treffer" class="mat-treffer"></div></div>
        <div id="an-produkt" class="mat-gewaehlt" hidden></div>
        <p class="help">Fehlt das Produkt, legt es ein Produktkatalogpfleger im Katalog an.</p>
        <label for="an-ordner">Ordner</label><select id="an-ordner">${optionen(0, 0)}</select>
        <label for="an-sn">Seriennummer des Herstellers</label><input type="text" id="an-sn" maxlength="80" placeholder="leer lassen, wenn der Hersteller keine vergibt">
        <div class="help">Ohne Herstellernummer vergibt das System eine eindeutige (STR-…), die dann am Artikel angebracht wird. Die Inventarnummer vergibt immer das System.</div>
        <div class="field-row"><div><label for="an-herst">Herstellung (Monat)</label><input type="month" id="an-herst"></div>
          <div><label for="an-kauf">Kauf</label><input type="date" id="an-kauf"></div></div>
        <div class="field-row"><div><label for="an-erst">Erstgebrauch</label><input type="date" id="an-erst"></div>
          <div><label for="an-int">Prüfintervall am Artikel (Monate)</label><input type="number" id="an-int" min="1" max="120" placeholder="vom Produkt/Ordner"></div></div>
        <div class="field-row"><div><label for="an-due">Nächste Prüfung</label><input type="date" id="an-due"><div class="help" id="an-due-hilfe"></div></div>
          <div id="an-ende-feld" hidden><label for="an-ende">Lebensende</label><input type="date" id="an-ende"><div class="help" id="an-ende-hilfe"></div></div></div>
        <label for="an-notes">Bemerkung</label><textarea id="an-notes" rows="2" maxlength="4000"></textarea>
        <div class="btn-row mat-knoepfe"><button class="btn" data-act="anlegen">Anlegen</button>
          <button class="btn secondary" data-act="anlegen-weiter" title="Produkt und Ordner bleiben für den nächsten Artikel stehen">Anlegen und nächsten</button></div>
      </div>`;
    let vorschlagLos = null;
    async function vorschlag() {
      if (!produkt) return;
      const q = new URLSearchParams({ product_id: produkt.id, folder_id: $("#an-ordner").value });
      for (const [k, sel] of [["manufactured_on", "#an-herst"], ["purchased_on", "#an-kauf"], ["first_use_on", "#an-erst"], ["interval_months", "#an-int"]]) {
        if ($(sel).value) q.set(k, $(sel).value);
      }
      try {
        const v = (await api(`${API}/artikel/vorschlag?${q}`)).vorschlag;
        const due = $("#an-due");
        if (!due.dataset.selbst) due.value = v.next_due_on || "";
        due.max = v.spaetestens || "";
        $("#an-due-hilfe").textContent = v.intervall.monate ? `Intervall ${v.intervall.monate} Monate (${v.intervall.quelle}); ohne Prüfung spätestens ${fmtTag(v.spaetestens)}.` : "";
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
    $("#an-due").addEventListener("input", (e) => { e.target.dataset.selbst = "1"; });
    $("#an-ende").addEventListener("input", (e) => { e.target.dataset.selbst = "1"; });
    function waehlen(p) {
      produkt = p;
      $("#an-produkt").hidden = false;
      $("#an-produkt").innerHTML = `${p.vorschau ? `<img class="mat-mini" src="${esc(p.vorschau)}" alt="">` : ""}<strong>${esc(produktName(p))}</strong> ${p.article_no ? `<span class="muted">${esc(p.article_no)}</span>` : ""} ${demoMarke(p.demo)}
        <span class="mat-art">${esc(MATERIALART[p.material_kind])}</span> <button class="lnk" type="button" id="an-anders">anderes Produkt</button>`;
      $("#an-treffer").innerHTML = "";
      $("#an-q").value = "";
      $("#an-anders").onclick = () => { produkt = null; $("#an-produkt").hidden = true; fokus($("#an-q")); };
      $("#an-due").dataset.selbst = ""; $("#an-ende").dataset.selbst = "";
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
          : '<p class="help">Kein Produkt gefunden.</p>';
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
                      next_due_on: $("#an-due").value || null, notes: $("#an-notes").value };
      if (!$("#an-ende-feld").hidden) daten.retire_by = $("#an-ende").value || null;
      try {
        const r = await api(`${API}/artikel`, { method: "POST", body: daten });
        if (!weiter) { location.href = `/material/artikel/${r.artikel.id}`; return; }
        toast(`${r.artikel.inventory_no} angelegt (Seriennummer ${r.artikel.serial_no})`);
        $("#an-sn").value = ""; $("#an-notes").value = "";
        fokus($("#an-sn"));
      } catch (e) { toast(e.message, true); }
    }
    aktionen = { anlegen: () => anlegen(false), "anlegen-weiter": () => anlegen(true) };
    fokus($("#an-q"));
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
    let seite = 1;
    const kats = await kategorienLaden();
    function katBaum() {
      const kinder = {};
      kats.forEach((k) => { (kinder[k.parent_id || 0] = kinder[k.parent_id || 0] || []).push(k); });
      const zweig = (pid) => (kinder[pid] || []).map((k) => `<li><a href="#" data-act="kategorie" data-id="${k.id}" class="${k.id === kategorie ? "aktiv" : ""}">${esc(k.name)}</a>
          ${k.norm ? `<span class="muted small">${esc(k.norm)}</span>` : ""}${demoMarke(k.demo)}
          ${k.aktives_formular ? `<a class="mat-formmarke" href="/material/katalog/formular/${k.aktives_formular}" title="aktives generisches Prüfformular">Formular</a>` : ""}
          ${kinder[k.id] ? `<ul>${zweig(k.id)}</ul>` : ""}</li>`).join("");
      return `<ul class="mat-baum mat-katbaum"><li><a href="#" data-act="kategorie" data-id="" class="${kategorie ? "" : "aktiv"}">alle Kategorien</a></li>${zweig(0)}</ul>`;
    }
    async function liste() {
      const p = new URLSearchParams({ q, seite, pro_seite: 25 });
      if (kategorie) p.set("kategorie", kategorie);
      const d = await api(`${API}/produkte?${p}`);
      $("#kat-liste").innerHTML = d.produkte.length ? `<table class="list mat-tabelle"><thead><tr><th>Produkt</th><th>Kategorie</th><th>Materialart</th><th>Intervall</th><th>Lebensdauer</th><th>Bestand</th></tr></thead><tbody>
        ${d.produkte.map((x) => `<tr><td data-l="Produkt">${x.vorschau ? `<img class="mat-mini" src="${esc(x.vorschau)}" alt="" loading="lazy">` : ""}<a href="/material/katalog/produkt/${x.id}"><strong>${esc(produktName(x))}</strong></a>${x.article_no ? ` <span class="muted">${esc(x.article_no)}</span>` : ""}${demoMarke(x.demo)}</td>
          <td data-l="Kategorie">${esc(x.category_name || "")}</td><td data-l="Materialart">${esc(MATERIALART[x.material_kind])}</td>
          <td data-l="Intervall">${x.intervall.monate ? `${x.intervall.monate} Mon.` : "–"}</td>
          <td data-l="Lebensdauer">${x.lifetime_years ? `${x.lifetime_years} J.` : "–"}</td><td data-l="Bestand">${x.bestand}</td></tr>`).join("")}</tbody></table>${seitenleiste(d.gesamt, seite, 25)}`
        : leer(q || kategorie ? "Kein Produkt in dieser Auswahl." : "Der Katalog ist noch leer.");
    }
    function zeichnen() {
      const k = kats.find((x) => x.id === kategorie);
      inhalt.innerHTML = `<div class="page-head"><h1>Katalog</h1>
          <div class="btn-row">${DARF.katalog ? '<button class="btn secondary" data-act="kat-neu">+ Kategorie</button><button class="btn" data-act="produkt-neu">+ Produkt</button>' : ""}</div></div>
        <div class="mat-katalog">
          <aside><h2>Kategorien</h2>${kats.length ? katBaum() : leer("Noch keine Kategorien.")}
            ${k && DARF.katalog ? `<div class="btn-row mat-katknoepfe"><button class="btn ghost small" data-act="kat-bearbeiten">Kategorie bearbeiten</button>
              <button class="btn ghost small" data-act="kat-formular">Generisches Formular</button><button class="btn ghost small" data-act="kat-loeschen">Löschen</button></div>` : ""}
            ${k && !DARF.katalog && k.aktives_formular ? `<p><a href="/material/katalog/formular/${k.aktives_formular}">Generisches Formular ansehen</a></p>` : ""}</aside>
          <div><input type="search" id="kat-q" placeholder="Produkte suchen: Hersteller, Modell, Artikelnummer, Norm" value="${esc(q)}" autocomplete="off">
            <div id="kat-liste"></div></div>
        </div>`;
      let los = null;
      $("#kat-q").addEventListener("input", (e) => { clearTimeout(los); los = setTimeout(() => { q = e.target.value.trim(); seite = 1; zeigen(liste); }, 250); });
      zeigen(liste);
    }
    aktionen = {
      kategorie: (b) => { kategorie = b.dataset.id ? +b.dataset.id : null; seite = 1; history.replaceState(null, "", kategorie ? `?kategorie=${kategorie}` : location.pathname); zeichnen(); },
      seite: (b) => { seite = +b.dataset.seite; zeigen(liste); },
      "kat-neu": () => kategorieDialog({ parent_id: kategorie }),
      "kat-bearbeiten": () => kategorieDialog(kats.find((x) => x.id === kategorie)),
      "kat-loeschen": async () => {
        const k = kats.find((x) => x.id === kategorie);
        if (!(await confirm(`Kategorie „${k.name}“ löschen? Das geht nur ohne Unterkategorien und Produkte.`, "Löschen"))) return;
        try { await api(`${API}/kategorien/${k.id}`, { method: "DELETE" }); location.href = "/material/katalog"; } catch (e) { toast(e.message, true); }
      },
      "kat-formular": () => formularFuer({ kategorie_id: kategorie }),
      "produkt-neu": () => produktDialog({ category_id: kategorie }),
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
    dialog(`<h2>${neu ? "Produkt anlegen" : "Produkt bearbeiten"}</h2>
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
          : mk.value === "sonstiges" ? "nur mit Herstellerangabe (Fundstelle)" : "Metall/Hardware hat keine festgeschriebene Lebensdauer";
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
      $("#pd-ok", body).onclick = async () => {
        const daten = { category_id: katSel.value ? +katSel.value : null, manufacturer: $("#pd-her", body).value, model: $("#pd-mod", body).value,
                        article_no: $("#pd-art", body).value, norm: $("#pd-norm", body).value, material_kind: mk.value,
                        interval_months: $("#pd-int", body).value || null, lifetime_years: ld.value || null,
                        lifetime_source: $("#pd-lq", body).value, description: $("#pd-desc", body).value };
        try {
          const r = neu ? await api(`${API}/produkte`, { method: "POST", body: daten }) : await api(`${API}/produkte/${p.id}`, { method: "PUT", body: daten });
          dlg.close(); location.href = `/material/katalog/produkt/${r.produkt.id}`;
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  /* --- Produkt ------------------------------------------------------------------------------------- */
  async function produkt() {
    const p = (await api(`${API}/produkte/${DATEN.id}`)).produkt;
    const k = DARF.katalog;
    const zeile = (t, w) => `<dt>${esc(t)}</dt><dd>${w}</dd>`;
    const dokZeile = (d) => `<tr class="${d.gilt ? "" : "mat-alt"}"><td data-l="Dokument"><a href="${esc(d.datei || d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
        <div class="small muted">${esc(DOKART[d.kind] || d.kind)}${d.datei ? ` · ${esc(groesse(d.size))}` : " · Link"}</div></td>
      <td data-l="Version">${esc(d.version || "–")}</td><td data-l="Gültig ab">${esc(fmtTag(d.valid_from))}</td>
      <td data-l="Stand">${d.gilt ? '<span class="mat-status s-einsatzbereit">gilt</span>' : d.withdrawn_on ? `zurückgezogen ${esc(fmtTag(d.withdrawn_on))}` : d.abgeloest_durch ? "abgelöst" : "noch nicht gültig"}
        ${d.sha256 ? `<div class="small muted mat-hash" title="SHA-256 ${esc(d.sha256)}">${esc(d.sha256.slice(0, 12))}…</div>` : ""}</td>
      <td>${k && !d.abgeloest_durch && !d.withdrawn_on ? `<div class="btn-row"><button class="btn ghost small" data-act="dok-version" data-id="${d.id}">Neue Version</button><button class="btn ghost small" data-act="dok-zurueck" data-id="${d.id}">Zurückziehen</button></div>` : ""}</td></tr>`;
    const formulare = p.formulare || [];
    inhalt.innerHTML = `${p.demo ? '<p class="mat-demo-banner">DEMO – nicht für echte Prüfungen.</p>' : ""}
      <div class="mat-pfad"><a href="/material/katalog">Katalog</a> / ${p.kategorie_pfad.map((x) => `<a href="/material/katalog?kategorie=${x.id}">${esc(x.name)}</a>`).join(" / ")}</div>
      <div class="mat-artikelkopf">
        ${p.bild ? `<a href="${esc(p.original || p.bild)}" target="_blank" rel="noopener"><img class="mat-produktbild" src="${esc(p.bild)}" alt=""></a>` : '<div class="mat-produktbild leer" aria-hidden="true">kein Produktbild</div>'}
        <div class="mat-artikeltitel"><h1>${esc(produktName(p))} ${demoMarke(p.demo)}</h1>
          <p class="mat-produktzeile">${p.article_no ? `Art.-Nr. ${esc(p.article_no)} · ` : ""}${esc(MATERIALART[p.material_kind])}${p.norm ? ` · ${esc(p.norm)}` : ""}</p>
          <div class="btn-row">${k ? `<button class="btn secondary small" data-act="bearbeiten">Bearbeiten</button><button class="btn ghost small" data-act="bild">Produktbild</button>${p.artikel_gesamt ? "" : '<button class="btn ghost small" data-act="loeschen">Löschen</button>'}` : ""}
            ${DARF.verwalten ? `<a class="btn small" href="/material/artikel/neu?produkt=${p.id}">+ Artikel dieses Produkts</a>` : ""}</div></div>
      </div>
      <div class="mat-spalten">
        <section class="section"><h2>Stammdaten</h2><dl class="mat-daten">
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
        ${p.dokumente.length ? `<table class="list mat-tabelle"><thead><tr><th>Dokument</th><th>Version</th><th>Gültig ab</th><th>Stand</th><th></th></tr></thead><tbody>${p.dokumente.map(dokZeile).join("")}</tbody></table>` : leer("Noch keine Dokumente.")}
        ${k ? '<button class="btn secondary small" data-act="dok-neu">+ Dokument</button>' : ""}
      </section>
      <section class="section"><h2>Journal</h2>${journalHtml(p.journal, true)}</section>`;
    aktionen = {
      bearbeiten: () => produktDialog(p),
      bild: () => fotoDialog(`${API}/produkte/${p.id}/bild`, !!p.bild, produkt),
      loeschen: async () => {
        if (!(await confirm(`Produkt „${produktName(p)}“ aus dem Katalog löschen?`, "Löschen"))) return;
        try { await api(`${API}/produkte/${p.id}`, { method: "DELETE" }); location.href = "/material/katalog"; } catch (e) { toast(e.message, true); }
      },
      formular: () => formularFuer({ produkt_id: p.id }),
      "dok-neu": () => dokumentDialog(`${API}/produkte/${p.id}/dokumente`, null),
      "dok-version": (b) => dokumentDialog(`${API}/dokumente/${b.dataset.id}/version`, p.dokumente.find((d) => d.id === +b.dataset.id)),
      "dok-zurueck": async (b) => {
        const d = p.dokumente.find((x) => x.id === +b.dataset.id);
        if (!(await confirm(`„${d.title}“ ab heute zurückziehen? Es bleibt in der Liste und in alten Protokollen sichtbar.`, "Zurückziehen"))) return;
        try { await api(`${API}/dokumente/${d.id}/zurueckziehen`, { method: "POST", body: {} }); toast("Zurückgezogen"); zeigen(produkt); } catch (e) { toast(e.message, true); }
      },
    };
  }

  function dokumentDialog(url, alt) {
    dialog(`<h2>${alt ? `Neue Version von „${esc(alt.title)}“` : "Herstellerdokument hinzufügen"}</h2>
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
          dlg.close(); toast("Dokument gespeichert"); zeigen(produkt);
        } catch (e) { toast(e.message, true); knopf.disabled = false; }
      };
    });
  }

  /* --- Prüfformular ---------------------------------------------------------------------------------- */
  async function formular() {
    const d = await api(`${API}/formulare/${DATEN.id}`);
    const f = d.formular;
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
        <td data-l="Prüfpunkt"><input type="text" class="fp-text" value="${esc(p.text || "")}" maxlength="300"></td>
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
          Alle Prüfpunkte werden bei der Prüfung mit ihrem Sollwert vorbelegt; ein kritischer Punkt mit Mangel schließt „einsatzbereit“ aus.</p>
        ${bearbeitbar ? `<label for="fp-titel">Titel</label><input type="text" id="fp-titel" value="${esc(f.titel || "")}" maxlength="160">` : ""}
        <table class="list mat-tabelle mat-formtabelle" id="fp-tabelle">
          <colgroup><col style="width:16%"><col style="width:38%"><col style="width:13%"><col style="width:12%"><col style="width:21%"></colgroup><thead><tr><th>Gruppe</th><th>Prüfpunkt</th><th>Art</th><th>Soll</th><th></th></tr></thead>
          <tbody>${punkte.map(punktZeile).join("")}</tbody></table>
        ${!punkte.length ? leer("Noch keine Prüfpunkte.") : ""}
        ${bearbeitbar ? '<div class="btn-row mat-knoepfe"><button class="btn secondary" data-act="punkt-neu">+ Prüfpunkt</button><button class="btn" data-act="speichern">Speichern</button></div>' : ""}
        <section class="section"><h2>Versionen</h2><ul class="mat-versionen">${f.versionen.map((v) => `<li>${v.id === f.id ? `<strong>Version ${v.version}</strong>` : `<a href="/material/katalog/formular/${v.id}">Version ${v.version}</a>`}
          ${v.aktiv ? '<span class="mat-status s-einsatzbereit">aktiv</span>' : ""}${v.benutzt ? ' <span class="badge grey">benutzt</span>' : ""} <span class="muted">${esc(v.titel || "")} · ${plural(v.punkte_anzahl, "Prüfpunkt", "Prüfpunkte")}</span></li>`).join("")}</ul></section>
        <details class="section mat-auf"><summary>Journal</summary>${journalHtml(f.journal)}</details>`;
      $$(".fp-art", inhalt).forEach((s) => s.addEventListener("change", () => { einsammeln(); zeichnen(); }));
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
    async function zeichnen() {
      const q = DATEN.q || "";
      if (!q) { inhalt.innerHTML = `<h1>Suche</h1>${leer("Serien-, Inventar- oder Herstellernummer oben eingeben – auch Teile davon.")}`; return; }
      const d = await api(`${API}/suche?q=${encodeURIComponent(q)}&seite=${seite}&pro_seite=50`);
      inhalt.innerHTML = `<div class="page-head"><h1>Suche „${esc(q)}“</h1></div>
        ${d.treffer.length ? artikelTabelle(d.treffer, { pfad: true }) : leer("Kein Artikel gefunden.")}${seitenleiste(d.gesamt, seite, 50)}`;
    }
    aktionen = { seite: (b) => { seite = +b.dataset.seite; zeigen(zeichnen); } };
    await zeichnen();
  }

  const ANSICHTEN = { dashboard, pruefungen, bestand, ordner, artikel, artikel_neu: artikelNeu, katalog, produkt, formular, suche };
  zeigen(ANSICHTEN[ANSICHT] || dashboard);
})();
