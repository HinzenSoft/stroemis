/* Übungsdatei der Einführung: Ankerplätze (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.3; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide; Durchläufe in tests/test_einfuehrung_karte.py).

   Übungsbestand: drei Alben „Übungsalbum A“ (Seiltechnik), „Übungsalbum B“ (Gewässer), „Übungsalbum C“ (Sonstiges) mit je
   zwei bis drei Übungsbildern, versetzt um den Kartenmittelpunkt (STROEMIS.mapCenter) – keine echten Orte. Ansprechpartner
   „Übungsperson A“ (example.invalid). Die Adresssuche findet immer den „Übungsort“ am Kartenmittelpunkt. Bilder nur unter
   /static/uebung/karte/ (Vorschau, Großansicht und Original) – erzeugt mit scripts/uebungsdateien.py. Kennungen im
   Bereich 920000001–920000099: Alben ab 920000001, Bilder ab 920000011, Übungsperson A 920000090.

   Die Antworten bilden die Form von app/api_albums.py nach (/api/map, /api/albums, /api/albums/<id>, Hochladen,
   /api/photos/<id>, /api/geocode). Nicht in der Übung (Bauvorlage 3.3): Album löschen, Alben zusammenlegen, Deckblatt,
   Ziehen und Ablegen (Einwurf), dazu Bild löschen – die Schicht antwortet darauf „In der Übung nicht verfügbar.“

   Im Teil „Redakteur“ gehört Übungsalbum A dem Konto selbst (ein Redakteur bearbeitet nur eigene Alben, can_edit wie
   api_albums.can_edit); B und C gehören Übungsperson A. */
(function () {
  const PERSON = 920000090;                                   // Übungsperson A, Besitzerin der übrigen Alben
  const ALBUM_A = 920000001;
  const BILD = (n) => `/static/uebung/karte/uebungsbild-${n}.jpg`;
  const BILDNAME = /^uebungsbild-([1-8])\.jpg$/;              // die Übungsbilder dieses Ordners
  const HOCHLADEBILD = 8;                                     // „Übungsbild nehmen“ und jede eigene Datei
  const KATEGORIEN = ["seil", "wasser", "sonstiges"];
  const ich = () => (window.STROEMIS && STROEMIS.user) || { id: 0, name: "" };
  const jetzt = () => new Date().toISOString().replace(/\.\d+Z$/, "+00:00");

  /* --- Wie der Server rechnet (api_albums.py) -------------------------------------------------------------------- */
  // can_edit: Verwaltung alle Alben, Redakteur die eigenen. In der Übung trägt S.stufe die Stufe des Teils.
  const darfAlbum = (ownerId) => S.stufe("karte") >= S.STUFE.verwaltung
    || (S.stufe("karte") >= S.STUFE.redakteur && ownerId === ich().id);
  const albumVon = (z, id) => z.alben.find((a) => a.id === id) || null;
  const darfBild = (z, p) => darfAlbum(p.owner_id) || darfAlbum((albumVon(z, p.album_id) || {}).owner_id);
  const bilderVon = (z, id) => z.bilder.filter((p) => p.album_id === id).sort((x, y) => x.sort - y.sort || x.id - y.id);
  const mittel = (werte) => (werte.length ? werte.reduce((n, x) => n + x, 0) / werte.length : null);

  function bildJson(p) {
    const out = {};
    for (const k of ["id", "album_id", "owner_id", "original_name", "width", "height", "lat", "lon", "altitude", "geo_source",
      "taken_at", "title", "note", "height_m", "details", "sort", "created_at", "kind"]) out[k] = p[k];
    out.thumb = BILD(p.bild);
    out.web = BILD(p.bild);
    out.orig = BILD(p.bild);
    return out;
  }
  function albumJson(z, a) {
    const bilder = bilderVon(z, a.id);
    const mit = bilder.filter((p) => p.lat != null);
    const person = z.personen[a.owner_id] || {};
    return Object.assign({}, a, { owner_name: person.name || "", owner_gliederung: person.gliederung || "",
      photos: bilder.map(bildJson), photo_count: bilder.length, unlocated_count: bilder.length - mit.length,
      lat: mittel(mit.map((p) => p.lat)), lon: mittel(mit.map((p) => p.lon)) });
  }
  // _clean_album: Felder als getrimmter Text, unbekannte Art → „sonstiges“, Titel Pflicht.
  const FELDER = ["title", "category", "description", "contact_name", "contact_org", "contact_phone", "contact_email", "contact_notes"];
  function albumFelder(d, neu) {
    const vals = {};
    for (const f of FELDER) {
      if (neu || (d && f in d)) vals[f] = d && d[f] != null ? String(d[f]).trim() : "";
    }
    if ("category" in vals && !KATEGORIEN.includes(vals.category)) vals.category = "sonstiges";
    if (neu && !vals.title) return { status: 400, error: "Bitte einen Titel für das Album angeben." };
    if ("title" in vals && !vals.title) return { status: 400, error: "Der Titel darf nicht leer sein." };
    return vals;
  }
  // Neue Kennungen bleiben im Bereich des Moduls: Alben bis 920000009, Bilder bis 920000089.
  function neueKennung(z, art) {
    if (z.naechste[art] > (art === "album" ? 920000009 : 920000089)) return null;
    z.naechste[art] += 1;
    return z.naechste[art] - 1;
  }

  /* --- Übungsbestand ---------------------------------------------------------------------------------------------- */
  function bestand() {
    const [lat, lon] = String(STROEMIS.mapCenter).split(",").map(Number);
    const am = jetzt();
    const besitzerA = S.stufe("karte") >= S.STUFE.redakteur ? ich().id : PERSON;   // Teil „Redakteur“: eigenes Album
    const album = (id, title, category, description, owner) => ({
      id, title, category, description, contact_name: "Übungsperson A", contact_org: "Übung", contact_phone: "",
      contact_email: "uebungsperson-a@example.invalid", contact_notes: "Übung: Platzhalter für Hinweise zur Kontaktaufnahme.",
      owner_id: owner, created_at: am, updated_at: am, cover_photo_id: null });
    // Bilder mit Geotag (geo_source „exif“) einige hundert Meter um den Kartenmittelpunkt – nur ein Versatz, kein Ort.
    const bild = (id, albumId, n, owner, sort, dLat, dLon) => ({
      id, album_id: albumId, owner_id: owner, bild: n, original_name: `uebungsbild-${n}.jpg`, width: 800, height: 600,
      lat: lat + dLat, lon: lon + dLon, altitude: null, geo_source: "exif", taken_at: null, title: "", note: "",
      height_m: null, details: "", sort, created_at: am, kind: "image" });
    return {
      personen: { [PERSON]: { name: "Übungsperson A", gliederung: "Übung" }, [ich().id]: { name: ich().name, gliederung: "" } },
      alben: [
        album(ALBUM_A, "Übungsalbum A", "seil", "Übung: Platzhalter für die Beschreibung eines Übungsobjekts.", besitzerA),
        album(920000002, "Übungsalbum B", "wasser", "Übung: Platzhalter für die Beschreibung eines Übungsgewässers.", PERSON),
        album(920000003, "Übungsalbum C", "sonstiges", "Übung: Platzhalter für die Beschreibung.", PERSON),
      ],
      bilder: [
        bild(920000011, ALBUM_A, 1, besitzerA, 1, 0.0040, -0.0060),
        bild(920000012, ALBUM_A, 2, besitzerA, 2, 0.0042, -0.0057),
        bild(920000013, ALBUM_A, 3, besitzerA, 3, 0.0038, -0.0055),
        bild(920000014, 920000002, 4, PERSON, 1, -0.0035, 0.0050),
        bild(920000015, 920000002, 5, PERSON, 2, -0.0033, 0.0054),
        bild(920000016, 920000003, 6, PERSON, 1, 0.0060, 0.0070),
        bild(920000017, 920000003, 7, PERSON, 2, 0.0062, 0.0067),
      ],
      naechste: { album: 920000004, bild: 920000020 },
      mitte: [lat, lon],
    };
  }

  /* --- Antworten -------------------------------------------------------------------------------------------------- */
  const antworten = [
    // Karte: alle Bilder mit Position (map_data).
    ["GET", /^\/api\/map$/, (m, body, z) => ({ photos: z.bilder.filter((p) => p.lat != null && p.lon != null).map((p) => {
      const a = albumVon(z, p.album_id) || {};
      return { id: p.id, album_id: p.album_id, lat: p.lat, lon: p.lon, title: p.title, album_title: a.title,
               category: a.category, kind: p.kind, cover: a.cover_photo_id === p.id, thumb: BILD(p.bild) };
    }) })],
    // Liste der Alben (list_albums): zuletzt geändert zuerst; Deckblatt, sonst das erste Bild.
    ["GET", /^\/api\/albums$/, (m, body, z) => ({ albums: z.alben.slice()
      .sort((x, y) => String(y.updated_at).localeCompare(String(x.updated_at)) || y.id - x.id)
      .map((a) => {
        const bilder = bilderVon(z, a.id);
        const deckblatt = bilder.find((p) => p.id === a.cover_photo_id) || bilder[0];
        const mit = bilder.filter((p) => p.lat != null);
        return Object.assign({}, a, { owner_name: (z.personen[a.owner_id] || {}).name || "", photo_count: bilder.length,
          unlocated_count: bilder.length - mit.length, lat: mittel(mit.map((p) => p.lat)), lon: mittel(mit.map((p) => p.lon)),
          cover: deckblatt ? BILD(deckblatt.bild) : null });
      }) })],
    ["POST", /^\/api\/albums$/, (m, body, z) => {
      if (S.stufe("karte") < S.STUFE.redakteur) return { status: 403, error: "Alben anlegen dürfen Redakteure und die Verwaltung der Ankerplätze." };
      const vals = albumFelder(body, true);
      if (vals.status) return vals;
      const id = neueKennung(z, "album");
      if (!id) return { status: 400, error: "In der Übung lassen sich keine weiteren Alben anlegen." };
      const am = jetzt();
      const a = Object.assign({ id, owner_id: ich().id, created_at: am, updated_at: am, cover_photo_id: null }, vals);
      z.alben.push(a);
      return { album: albumJson(z, a) };
    }],
    ["GET", /^\/api\/albums\/(\d+)$/, (m, body, z) => {
      const a = albumVon(z, +m[1]);
      if (!a) return { status: 404, error: "Album nicht gefunden" };
      return { album: Object.assign(albumJson(z, a), { can_edit: darfAlbum(a.owner_id) }) };
    }],
    ["PUT", /^\/api\/albums\/(\d+)$/, (m, body, z) => {
      const a = albumVon(z, +m[1]);
      if (!a) return { status: 404, error: "Album nicht gefunden" };
      if (!darfAlbum(a.owner_id)) return { status: 403, error: "Keine Berechtigung" };
      const vals = albumFelder(body, false);
      if (vals.status) return vals;
      Object.assign(a, vals, { updated_at: jetzt() });
      return { album: Object.assign(albumJson(z, a), { can_edit: true }) };
    }],
    // Hochladen (upload_photos): Die Dateien bleiben im Browser; jedes Bild zeigt ein Übungsbild und hat keinen Geotag –
    // so kommen die Rückfrage „ohne Geotag“ und das Platzieren auf der Karte.
    ["POST", /^\/api\/albums\/(\d+)\/photos$/, (m, body, z) => {
      const a = albumVon(z, +m[1]);
      if (!a) return { status: 404, error: "Album nicht gefunden" };
      if (!darfAlbum(a.owner_id)) return { status: 403, error: "Keine Berechtigung" };
      const dateien = body instanceof FormData ? body.getAll("files").filter((f) => f instanceof Blob) : [];
      if (!dateien.length) return { status: 400, error: "Keine Dateien empfangen." };
      const am = jetzt();
      let sort = bilderVon(z, a.id).reduce((n, p) => Math.max(n, p.sort), 0) + 1;
      const neu = [];
      const errors = [];
      for (const f of dateien) {
        const id = neueKennung(z, "bild");
        if (!id) { errors.push("In der Übung lassen sich keine weiteren Bilder hochladen."); break; }
        const name = String(f.name || "");
        const treffer = BILDNAME.exec(name);
        const p = { id, album_id: a.id, owner_id: ich().id, bild: treffer ? +treffer[1] : HOCHLADEBILD, original_name: name,
          width: 800, height: 600, lat: null, lon: null, altitude: null, geo_source: null, taken_at: null, title: "", note: "",
          height_m: null, details: "", sort: sort++, created_at: am, kind: "image" };
        z.bilder.push(p);
        neu.push(bildJson(p));
      }
      a.updated_at = am;
      return { photos: neu, unlocated: neu.filter((p) => p.lat == null).map((p) => p.id), errors };
    }],
    ["GET", /^\/api\/photos\/(\d+)$/, (m, body, z) => {
      const p = z.bilder.find((x) => x.id === +m[1]);
      if (!p) return { status: 404, error: "Bild nicht gefunden" };
      return { photo: Object.assign(bildJson(p), { can_edit: darfBild(z, p) }) };
    }],
    // Bild ändern (update_photo): Texte, Zahlen, Position – „manuell“ nur, wenn sie sich wirklich ändert.
    ["PUT", /^\/api\/photos\/(\d+)$/, (m, body, z) => {
      const p = z.bilder.find((x) => x.id === +m[1]);
      if (!p) return { status: 404, error: "Bild nicht gefunden" };
      if (!darfBild(z, p)) return { status: 403, error: "Keine Berechtigung" };
      const d = body && typeof body === "object" ? body : {};
      const vals = {};
      for (const f of ["title", "note", "details", "taken_at"]) {
        if (!(f in d)) continue;
        if (d[f] != null && typeof d[f] !== "string") return { status: 400, error: `„${f}“ muss Text sein.` };
        vals[f] = (d[f] || "").trim();
      }
      if (vals.taken_at && Number.isNaN(Date.parse(vals.taken_at))) return { status: 400, error: "„Aufnahmezeit“ muss ein Zeitpunkt sein." };
      for (const f of ["height_m", "altitude"]) {
        if (!(f in d)) continue;
        if (d[f] == null || d[f] === "") { vals[f] = null; continue; }
        const n = Number(String(d[f]).replace(",", "."));
        if (!Number.isFinite(n)) return { status: 400, error: `„${d[f]}“ ist keine gültige Zahl.` };
        vals[f] = n;
      }
      if ("lat" in d || "lon" in d) {
        const leer = (v) => v == null || v === "";
        if (leer(d.lat) && leer(d.lon)) Object.assign(vals, { lat: null, lon: null, geo_source: null });
        else {
          const lat = Number(d.lat), lon = Number(d.lon);
          if (leer(d.lat) || leer(d.lon) || !Number.isFinite(lat) || !Number.isFinite(lon)) return { status: 400, error: "Ungültige Koordinaten." };
          if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return { status: 400, error: "Koordinaten außerhalb des gültigen Bereichs." };
          if (lat !== p.lat || lon !== p.lon) Object.assign(vals, { lat, lon, geo_source: "manual" });
        }
      }
      Object.assign(p, vals);
      const a = albumVon(z, p.album_id);
      if (a && Object.keys(vals).length) a.updated_at = jetzt();
      return { photo: Object.assign(bildJson(p), { can_edit: true }) };
    }],
    // Adresssuche: ein Treffer „Übungsort“ am Kartenmittelpunkt – es geht keine Anfrage an einen Kartendienst.
    ["GET", /^\/api\/geocode$/, (m, body, z, url) => ((url.searchParams.get("q") || "").trim().length < 3 ? { results: [] }
      : { results: [{ name: "Übungsort", lat: z.mitte[0], lon: z.mitte[1] }] })],
  ];

  /* --- Abläufe ---------------------------------------------------------------------------------------------------- */
  /* Ziele sind einfache Selektoren: Die Führung wartet, bis die Seitenleiste nicht mehr gleitet (am Telefon eine
     Schublade von unten), und holt das Ziel sofort über die Leiste der Führung (einfuehrung.js, beruhigen/insBild). */
  const BILD_PUT = /^PUT \/api\/photos\/\d+$/;

  S.einfuehrung.modul("karte", {
    bestand,
    antworten,
    // „herunterladen“ (Original) in der Großansicht öffnet das Übungsbild selbst.
    dateien: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => [new RegExp(`^/static/uebung/karte/uebungsbild-${n}\\.jpg$`), BILD(n)]),
    teile: {
      grund: { ablaeufe: [
        { titel: "Karte und Album", start: "/ankerplaetze", schritte: [
          { ziel: "#map", text: "Auf der Karte stehen die Ankerplätze mit ihren Bildern." },
          { ziel: "#btn-albums", text: "Tippe auf „Alben“ – die Liste zeigt alle Alben.", warten: { klick: "#btn-albums" } },
          { ziel: `.album-wahl[data-id="${ALBUM_A}"]`, text: "Öffne Übungsalbum A.",
            warten: { klick: `.album-wahl[data-id="${ALBUM_A}"]` } },
          { ziel: '.photo-grid button[data-i="0"]', text: "Tippe auf ein Bild, um es groß zu sehen.",
            warten: { klick: ".photo-grid button" }, probe: { klick: '.photo-grid button[data-i="0"]' } },
          { ziel: "#lb-next", text: "Blättern geht mit den Pfeilen oder durch Wischen.", warten: { klick: "#lb-next" } },
          { ziel: "#lb-close", text: "Schließ die Großansicht – das Album bleibt offen.", warten: { klick: "#lb-close" } },
        ] },
        { titel: "Suchen und filtern", start: "/ankerplaetze", schritte: [
          { ziel: "#alben-suche", text: "Such nach „Übung“ – gesucht wird in Titel, Beschreibung und Gliederung der Alben.",
            warten: { wert: ["#alben-suche", /\S{3}/] }, probe: { tippen: ["#alben-suche", "Übung"] } },
          { ziel: '.chip[data-cat="wasser"]', text: "Die Knöpfe filtern nach Art. Tippe auf „Gewässer“.",
            warten: { klick: '.chip[data-cat="wasser"]' } },
          { ziel: "#panel.open #al-liste",
            text: "Jetzt stehen nur noch die Alben da, die zu Suche und Art passen. „Alle“ hebt den Filter wieder auf." },
        ] },
      ] },
      redakteur: { ablaeufe: [
        { titel: "Album anlegen", start: "/ankerplaetze", schritte: [
          { ziel: "#btn-new-album", text: "Als Redakteur legst du eigene Alben an. Tippe auf „Album anlegen“.",
            warten: { klick: "#btn-new-album" } },
          { ziel: "#al-title", text: "Gib dem Album einen Titel, hier „Übungsalbum D“.",
            warten: { wert: ["#al-title", /\S{3}/] }, probe: { tippen: ["#al-title", "Übungsalbum D"] } },
          { ziel: "#al-cat", text: "Wähle die Art: Übungsobjekt Seiltechnik, Übungsgewässer oder Sonstiges." },
          { ziel: "label:has(> #al-upload)", text: "Nimm den Haken heraus – Bilder lädst du im nächsten Ablauf hoch.",
            warten: { bedingung: () => !(document.querySelector("#al-upload") || {}).checked }, probe: { klick: "label:has(> #al-upload)" } },
          { ziel: "#al-save", text: "Leg das Album an.", warten: { anfrage: "POST /api/albums" }, probe: { klick: "#al-save" } },
          { ziel: "#panel.open #panel-body > p.help",
            text: "Das Album ist angelegt. Auf die Karte kommt es mit dem ersten Bild, das eine Position hat." },
        ] },
        // Ohne Anker: Die Seite lädt neu und zeigt die Karte ohne offenes Album – der Weg über „Alben“ zu Übungsalbum A
        // gehört zum Ablauf (weiter wie fortgesetzt).
        { titel: "Bilder hochladen", start: "/ankerplaetze", schritte: [
          { ziel: "#btn-albums", text: "Öffne die Liste der Alben.", warten: { klick: "#btn-albums" } },
          { ziel: `.album-wahl[data-id="${ALBUM_A}"]`,
            text: "Öffne Übungsalbum A. Es gehört dir – Bilder hochladen darfst du nur in eigenen Alben.",
            warten: { klick: `.album-wahl[data-id="${ALBUM_A}"]` } },
          { ziel: "#a-upload", text: "Tippe auf „Bilder / Videos hochladen“ – oder nimm hier ein Übungsbild.",
            datei: { input: "#file-input", bild: BILD(HOCHLADEBILD) },
            warten: { anfrage: `POST /api/albums/${ALBUM_A}/photos` }, probe: { datei: true } },
          { ziel: "#loc-start", text: "Das Bild hat keinen Geotag. Platzier es jetzt auf der Karte.",
            warten: { klick: "#loc-start" } },
          { ziel: "#loc-q", text: "Such den Ort: Gib „Übungsort“ ein.",
            warten: { wert: ["#loc-q", /\S{3}/] }, probe: { tippen: ["#loc-q", "Übungsort"] } },
          { ziel: "#loc-form button[type=submit]", text: "Tippe auf „Suchen“.", warten: { anfrage: "GET /api/geocode" },
            probe: { klick: "#loc-form button[type=submit]" } },
          { ziel: "#loc-treffer button", text: "Wähle den Treffer – die Karte fährt dorthin.", warten: { klick: "#loc-treffer button" } },
          { ziel: "#map", text: "Tippe jetzt auf die Karte, an die Stelle, an der das Bild entstanden ist.",
            // Die Probe tippt auf eine freie Stelle der Karte – in ihrer Mitte liegt am Telefon das Positionsbanner.
            warten: { da: "#loc-ok" }, probe: { klick: "#map", frei: true } },
          { ziel: "#loc-ok", text: "Speichere die Position.", warten: { anfrage: BILD_PUT }, probe: { klick: "#loc-ok" } },
          { ziel: "#panel.open .photo-grid", text: "Das Bild liegt jetzt mit Position im Album und auf der Karte." },
        ] },
        // Die Seite lädt zu Beginn jedes Ablaufs neu; map.js öffnet Übungsalbum A über den Anker.
        { titel: "Bild beschreiben", start: `/ankerplaetze#album=${ALBUM_A}`, schritte: [
          { ziel: '.photo-grid button[data-i="0"]', text: "Öffne das erste Bild.",
            warten: { klick: '.photo-grid button[data-i="0"]' } },
          { ziel: "#lb-edit", text: "Tippe auf „Bearbeiten“.", warten: { klick: "#lb-edit" } },
          { ziel: "#p-title", text: "Gib dem Bild einen Titel, hier „Übung: Ansicht“.",
            warten: { wert: ["#p-title", /\S{3}/] }, probe: { tippen: ["#p-title", "Übung: Ansicht"] } },
          { ziel: "#p-save", text: "Speichere – Titel, Notiz und weitere Infos stehen dann in der Großansicht.",
            warten: { anfrage: BILD_PUT }, probe: { klick: "#p-save" } },
        ] },
      ] },
    },
  });
})();
