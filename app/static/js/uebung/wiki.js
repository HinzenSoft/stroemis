/* Übungsdatei der Einführung: Strömipedia (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.2; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide, tests/test_einfuehrung_wiki.py läuft alle Teile durch).

   Übungsbestand: der Abschnitt „Übung: Start“ mit „Übung: Seite lesen“ (Überschriften für die Gliederung, ein Übungsbild,
   ein Kommentar von Übungsperson A; im Grundteil für das Konto zum Bearbeiten freigegeben), „Übung: Zweite Seite“ (zwei
   Fassungen im Verlauf; ab Redakteur vom Konto selbst angelegt) und „Übung: Vorlage“, dazu „Übung: Alte Seite“ im
   Papierkorb. Alle Texte sind Platzhalter über die Strömipedia selbst, Bilder nur aus /static/uebung/, Kennungen im
   Bereich 9100000xx, Adressen „uebung-…“. Die Antworten bilden die Form der Schnittstelle nach (app/api_wiki.py:
   page_json, Baum, Suche, Kommentare, Präsenz, Verlauf, Papierkorb) und rechnen die Rechte des geübten Teils so, wie der
   Server sie rechnete; was eine Antwort ändert, steht bis zum Ende des Ablaufs im Übungsbestand.

   Nicht in der Übung (Antwort „In der Übung nicht verfügbar.“): in den Papierkorb legen, endgültig löschen, duplizieren,
   verschieben, Lesebeschränkung, Ersteller ändern, Dateien hochladen und bearbeiten, Import. Den Export („Als Markdown
   herunterladen“, „Abschnitt als ZIP herunterladen“) holt die Seite per Seitenwechsel – den fängt unten ein Klick-Wächter
   ab und meldet dasselbe, statt die Übungsseite zu verlassen. */
(function () {
  const ST = window.STROEMIS || {};
  const ICH = (ST.user && ST.user.id) || 0;
  const ICH_NAME = (ST.user && ST.user.name) || "Du";
  const TEIL = () => (ST.einfuehrung && ST.einfuehrung.uebung) || "grund";
  const REDAKTION = () => TEIL() !== "grund";                 // Redakteur und Verwaltung legen Seiten an
  const VERWALTUNG = () => TEIL() === "verwaltung";
  const NICHT = { status: 403, error: "In der Übung nicht verfügbar." };
  const CONFLICT = "Die Seite wurde inzwischen von jemand anderem gespeichert. Bitte die Seite neu laden und die "
    + "Änderung noch einmal eintragen – der Verlauf zeigt die zwischenzeitliche Fassung.";

  // Kennungen des Übungsbestands (Bauvorlage 2.2: Strömipedia 9100000xx).
  const START = 910000001;
  const LESEN = 910000002;
  const ZWEITE = 910000003;
  const ALT = 910000004;
  const VORLAGE = 910000005;
  const KOMMENTAR_A = 910000011;
  const PERSON_A = 910000051;
  const PERSON_B = 910000052;
  const NEU = 910000061;                                      // erste Kennung für Neues aus der Übung
  const BILD = "/static/uebung/wiki/uebungsbild-7.jpg";
  const PERSONEN = [
    { id: PERSON_A, name: "Übungsperson A", email: "uebungsperson-a@example.invalid", gliederung: "Übung" },
    { id: PERSON_B, name: "Übungsperson B", email: "uebungsperson-b@example.invalid", gliederung: "Übung" },
  ];

  /* --- Übungsbestand ------------------------------------------------------------------------------------------------- */
  // Zeitpunkte wie db.now() (UTC, Sekunden), relativ zum Beginn des Ablaufs.
  const vor = (stunden) => new Date(Date.now() - stunden * 3600 * 1000).toISOString().replace(/\.\d{3}Z$/, "+00:00");
  const jetzt = () => vor(0);
  function seiteAnlegen(felder) {
    return Object.assign({ parent_id: null, position: 0, format: "markdown", is_public: 0, public_children: 0, version: 1,
                           icon: "", is_template: 0, read_restricted: 0, deleted_at: null, editors: [], alte_slugs: [] }, felder);
  }
  function bestand() {
    const eigen = TEIL() === "grund" ? PERSON_B : ICH;       // „Übung: Zweite Seite“ gehört ab Redakteur dem Konto
    const lesen = `# Übung: Seite lesen

Diese Seite gehört zur Übung. Sie zeigt, wie eine Seite der Strömipedia aufgebaut ist; alle Texte hier sind Platzhalter.

## Abschnitt eins

Überschriften wie diese stehen in der Gliederung der Seite.

## Abschnitt zwei

Platzhaltertext mit einem Übungsbild:

![Übungsbild](${BILD})

## Abschnitt drei

Platzhaltertext mit einem Verweis auf die [zweite Übungsseite](/stroemipedia/uebung-zweite-seite).
`;
    const seiten = [
      seiteAnlegen({ id: START, title: "Übung: Start", slug: "uebung-start", position: 0, created_by: PERSON_A,
        updated_by: PERSON_A, created_at: vor(72), updated_at: vor(72),
        content: "# Übung: Start\n\nDieser Abschnitt gehört zur Übung. Seine Unterseiten stehen im Seitenbaum darunter.\n" }),
      seiteAnlegen({ id: LESEN, title: "Übung: Seite lesen", slug: "uebung-seite-lesen", parent_id: START, position: 0,
        created_by: PERSON_A, updated_by: PERSON_A, created_at: vor(70), updated_at: vor(48), content: lesen,
        editors: TEIL() === "grund" ? [ICH] : [] }),
      seiteAnlegen({ id: ZWEITE, title: "Übung: Zweite Seite", slug: "uebung-zweite-seite", parent_id: START, position: 1,
        created_by: eigen, updated_by: eigen, created_at: vor(60), updated_at: vor(24), version: 2,
        content: "# Übung: Zweite Seite\n\nPlatzhaltertext der aktuellen Fassung. Die ältere Fassung steht im Verlauf.\n" }),
      seiteAnlegen({ id: VORLAGE, title: "Übung: Vorlage", slug: "uebung-vorlage", parent_id: START, position: 2,
        created_by: PERSON_A, updated_by: PERSON_A, created_at: vor(66), updated_at: vor(66), is_template: 1,
        content: "# Übung: Vorlage\n\n## Platzhalter-Abschnitt\n\nPlatzhaltertext einer Vorlage.\n" }),
      seiteAnlegen({ id: ALT, title: "Übung: Alte Seite", slug: "uebung-alte-seite", parent_id: START, position: 3,
        created_by: PERSON_A, updated_by: PERSON_A, created_at: vor(90), updated_at: vor(80), deleted_at: vor(20),
        content: "# Übung: Alte Seite\n\nPlatzhaltertext einer gelöschten Seite.\n" }),
    ];
    const fassung = (id, p, stunden, inhalt) => ({ id, page_id: p.id, title: p.title, content: inhalt || p.content,
      format: "markdown", user_id: p.created_by, created_at: vor(stunden), sitzung: "" });
    const [s, l, zw, v, a] = seiten;
    return {
      seiten,
      fassungen: [
        fassung(910000021, s, 72), fassung(910000022, l, 48),
        fassung(910000023, zw, 60, "# Übung: Zweite Seite\n\nÄltere Fassung: Platzhaltertext, wie er vorher dastand.\n"),
        fassung(910000024, zw, 24), fassung(910000025, v, 66), fassung(910000026, a, 80),
      ],
      kommentare: [{ id: KOMMENTAR_A, page_id: LESEN, parent_id: null, user_id: PERSON_A, quote: "", quote_before: "",
        quote_after: "", body: "Übung: ein Kommentar von Übungsperson A zur ganzen Seite.", resolved: 0, created_at: vor(30) }],
      gesehen: [{ page_id: LESEN, seen_at: vor(2) }],
      favoriten: [],
      beobachtet: [],
      naechste: NEU,
    };
  }

  /* --- Wie der Server rechnet (app/api_wiki.py) ---------------------------------------------------------------------- */
  const lebende = (z) => z.seiten.filter((p) => !p.deleted_at);
  const seite = (z, id) => lebende(z).find((p) => p.id === id) || null;
  // _get_page: Adresse oder frühere Adresse (umbenannte Seiten).
  function seiteNachAdresse(z, slug) {
    const s = String(slug || "");
    return lebende(z).find((p) => p.slug === s) || lebende(z).find((p) => (p.alte_slugs || []).includes(s)) || null;
  }
  const name = (uid) => (uid === ICH ? ICH_NAME : (PERSONEN.find((u) => u.id === uid) || {}).name || "unbekannt");
  function person(uid) {
    if (uid === ICH) return { id: ICH, name: ICH_NAME, email: "", gliederung: "" };
    const u = PERSONEN.find((x) => x.id === uid);
    return u ? Object.assign({}, u) : null;
  }
  function vorfahren(z, p) {
    const out = [];
    const gesehen = new Set();
    let cur = p && p.parent_id ? z.seiten.find((x) => x.id === p.parent_id) : null;
    while (cur && !gesehen.has(cur.id)) {
      out.push(cur);
      gesehen.add(cur.id);
      const eltern = cur.parent_id;
      cur = eltern ? z.seiten.find((x) => x.id === eltern) : null;
    }
    return out;
  }
  // is_public: die Seite selbst oder ein Vorfahr ist samt Unterseiten freigegeben.
  const oeffentlich = (z, p) => Boolean(p.is_public) || vorfahren(z, p).some((a) => a.is_public && a.public_children);
  // inherits_public: unter dieser Seite wäre eine neue Seite für alle Angemeldeten lesbar.
  function erbtFreigabe(z, pid) {
    const p = pid ? z.seiten.find((x) => x.id === pid) : null;
    return Boolean(p) && [p, ...vorfahren(z, p)].some((a) => a.is_public && a.public_children);
  }
  // can_edit: die Wiki-Verwaltung alles, ein Redakteur die eigenen, jeder, für den die Seite oder ein Vorfahr freigegeben ist.
  function darfBearbeiten(z, p) {
    if (VERWALTUNG() || (REDAKTION() && p.created_by === ICH)) return true;
    return [p, ...vorfahren(z, p)].some((a) => (a.editors || []).includes(ICH));
  }
  // can_delete (und can_share, can_restore): Ersteller ab Redakteur oder die Wiki-Verwaltung.
  const darfLoeschen = (p) => VERWALTUNG() || (REDAKTION() && p.created_by === ICH);
  const darfAnlegenUnter = (z, pid) => REDAKTION() && (VERWALTUNG() || !erbtFreigabe(z, pid));
  // Verweise wie sync_page_links: [Text](/stroemipedia/<slug>) – auf die heutige oder eine frühere Adresse.
  const VERWEIS_RE = /\]\(\/(?:stroemipedia|wiki)\/([^)\s#?]+)/g;
  const verweiseVon = (p) => [...String(p.content || "").matchAll(VERWEIS_RE)].map((m) => decodeURIComponent(m[1]));
  const namenVon = (p) => [p.slug, ...(p.alte_slugs || [])];
  const verweisenAuf = (z, p) => lebende(z).filter((q) => q.id !== p.id && verweiseVon(q).some((s) => namenVon(p).includes(s)));
  const kurz = (p) => ({ id: p.id, title: p.title, slug: p.slug, icon: p.icon });

  function seiteJson(z, p) {
    const out = {};
    for (const k of ["id", "title", "slug", "parent_id", "position", "created_by", "updated_by", "created_at", "updated_at",
                     "format", "is_public", "public_children", "version", "icon", "is_template", "read_restricted"]) out[k] = p[k];
    out.created_by_name = name(p.created_by);
    out.updated_by_name = name(p.updated_by);
    out.created_by_avatar = null;
    out.effective_public = oeffentlich(z, p);
    out.content = p.content;
    out.can_edit = darfBearbeiten(z, p);
    out.can_delete = darfLoeschen(p);
    out.can_share = darfLoeschen(p);
    out.can_publish = VERWALTUNG();
    out.can_create = darfAnlegenUnter(z, p.id);
    out.can_duplicate = darfAnlegenUnter(z, p.parent_id);
    if (out.can_share) out.editors = (p.editors || []).map(person).filter(Boolean);
    out.comment_count = z.kommentare.filter((c) => c.page_id === p.id && !c.resolved).length;
    out.favorite = z.favoriten.includes(p.id);
    out.watch = z.beobachtet.includes(p.id);
    out.backlink_count = verweisenAuf(z, p).length;
    return out;
  }
  // Baumzeilen wie tree() mit _baum_rechte.
  function baum(z) {
    return lebende(z).slice().sort((a, b) => a.position - b.position || a.title.localeCompare(b.title, "de")).map((p) => ({
      id: p.id, title: p.title, slug: p.slug, parent_id: p.parent_id, position: p.position, updated_at: p.updated_at,
      created_by: p.created_by, is_public: p.is_public, public_children: p.public_children, icon: p.icon,
      is_template: p.is_template, read_restricted: p.read_restricted, favorite: z.favoriten.includes(p.id) ? 1 : 0,
      can_edit: darfBearbeiten(z, p), can_delete: darfLoeschen(p), can_create: darfAnlegenUnter(z, p.id) }));
  }
  function slugify(titel) {
    const s = String(titel || "").trim().toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue")
      .replace(/ß/g, "ss").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return s || "seite";
  }
  // unique_slug: auch frühere Adressen anderer Seiten bleiben belegt.
  function freieAdresse(z, titel, ausser) {
    const basis = slugify(titel);
    for (let n = 1; ; n += 1) {
      const slug = n === 1 ? basis : `${basis}-${n}`;
      if (!z.seiten.some((p) => p.id !== ausser && (p.slug === slug || (p.alte_slugs || []).includes(slug)))) return slug;
    }
  }
  // Wie _revision: Zwischenstände derselben Bearbeitung (gleiches Kennzeichen „sitzung“) landen in derselben Fassung.
  function fassungSchreiben(z, p, sitzung) {
    const letzte = z.fassungen.filter((f) => f.page_id === p.id).sort((a, b) => b.id - a.id)[0];
    if (sitzung && letzte && letzte.sitzung === sitzung && letzte.user_id === ICH) {
      Object.assign(letzte, { title: p.title, content: p.content, created_at: p.updated_at });
      return;
    }
    z.fassungen.push({ id: z.naechste++, page_id: p.id, title: p.title, content: p.content, format: "markdown", user_id: ICH,
                       created_at: p.updated_at, sitzung: sitzung || "" });
  }
  // search(): jedes Wort in Titel oder Inhalt, Treffer im Titel zuerst, Ausschnitt um den ersten Treffer im Text.
  function suche(z, q) {
    const begriff = String(q || "").trim();
    if (begriff.length < 2) return { results: [] };
    const terms = begriff.split(/\s+/).filter(Boolean).slice(0, 6);
    const klein = (s) => String(s || "").toLowerCase();
    const imTitel = (p) => terms.filter((t) => klein(p.title).includes(klein(t))).length;
    const treffer = lebende(z).filter((p) => terms.every((t) => klein(p.title).includes(klein(t)) || klein(p.content).includes(klein(t))))
      .sort((a, b) => imTitel(b) - imTitel(a) || String(b.updated_at).localeCompare(String(a.updated_at)) || a.title.localeCompare(b.title, "de"));
    const results = treffer.map((p) => {
      const text = String(p.content || "").replace(/\s+/g, " ").trim();
      const stellen = terms.map((t) => klein(text).indexOf(klein(t))).filter((i) => i >= 0);
      let snippet = "";
      if (stellen.length) {
        const hit = Math.min(...stellen);
        const anfang = Math.max(0, hit - 60);
        snippet = (anfang ? "…" : "") + text.slice(anfang, hit + 140) + (text.length > hit + 140 ? "…" : "");
      } else if (text) snippet = text.slice(0, 160) + (text.length > 160 ? "…" : "");
      return { id: p.id, title: p.title, slug: p.slug, snippet, terms };
    });
    return { results: results.slice(0, 30), terms };
  }
  function kommentarJson(z, c) {
    const p = z.seiten.find((x) => x.id === c.page_id) || {};
    return Object.assign({}, c, { user_name: name(c.user_id),
      can_delete: VERWALTUNG() || c.user_id === ICH || (REDAKTION() && p.created_by === ICH),
      can_edit: VERWALTUNG() || c.user_id === ICH });
  }
  function teilbaum(z, id) {
    const out = [id];
    for (let i = 0; i < out.length; i += 1) z.seiten.filter((p) => p.parent_id === out[i]).forEach((p) => out.push(p.id));
    return out;
  }

  /* --- Antworten ------------------------------------------------------------------------------------------------------ */
  const ohneSeite = { status: 404, error: "Seite nicht gefunden" };
  const antworten = [
    ["GET", "/api/wiki/tree", (m, b, z) => ({ pages: baum(z) })],
    ["GET", "/api/wiki/recent", (m, b, z) => ({
      seen: z.gesehen.filter((g) => seite(z, g.page_id)).map((g) => Object.assign(kurz(seite(z, g.page_id)), { seen_at: g.seen_at })),
      changed: lebende(z).slice().sort((a, c) => String(c.updated_at).localeCompare(String(a.updated_at))).slice(0, 8)
        .map((p) => Object.assign(kurz(p), { updated_at: p.updated_at, updated_by_name: name(p.updated_by) })) })],
    ["GET", "/api/wiki/search", (m, b, z, url) => suche(z, url.searchParams.get("q"))],
    ["GET", "/api/wiki/templates", (m, b, z) => ({ pages: lebende(z).filter((p) => p.is_template).map(kurz) })],
    ["GET", "/api/wiki/bausteine", () => ({ bausteine: [] })],
    ["GET", "/api/wiki/users", () => ({ users: PERSONEN.map((u) => ({ id: u.id, name: u.name, gliederung: u.gliederung })) })],
    ["GET", "/api/wiki/favorites", (m, b, z) => ({ pages: z.favoriten.map((id) => seite(z, id)).filter(Boolean).map(kurz) })],

    // Seiten
    ["GET", /^\/api\/wiki\/pages\/([^/]+)$/, (m, b, z) => {
      const p = seiteNachAdresse(z, decodeURIComponent(m[1]));
      return p ? { page: seiteJson(z, p) } : ohneSeite;
    }],
    ["POST", "/api/wiki/pages", (m, b, z) => {
      const d = b || {};
      if (!REDAKTION()) return { status: 403, error: "Seiten anlegen dürfen Redakteure und die Wiki-Verwaltung." };
      const titel = String(d.title || "").trim();
      if (!titel) return { status: 400, error: "Bitte einen Titel angeben." };
      const eltern = d.parent_id ? seite(z, +d.parent_id) : null;
      if (d.parent_id && !eltern) return { status: 400, error: "Übergeordnete Seite nicht gefunden." };
      if (eltern && !darfAnlegenUnter(z, eltern.id)) {
        return { status: 403, error: "Dieser Abschnitt ist für alle Angemeldeten freigegeben. Seiten darin darf nur die Wiki-Verwaltung anlegen." };
      }
      const ts = jetzt();
      const p = seiteAnlegen({ id: z.naechste++, title: titel, slug: freieAdresse(z, titel, null), parent_id: eltern ? eltern.id : null,
        position: +d.position || 0, created_by: ICH, updated_by: ICH, created_at: ts, updated_at: ts, content: String(d.content || "") });
      z.seiten.push(p);
      fassungSchreiben(z, p, "");
      return { page: seiteJson(z, p) };
    }],
    ["PUT", /^\/api\/wiki\/pages\/(\d+)$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      const d = b || {};
      if (!p) return ohneSeite;
      if (!darfBearbeiten(z, p)) return { status: 403, error: "Diese Seite dürfen ihr Ersteller, freigegebene Nutzer und die Wiki-Verwaltung bearbeiten." };
      if (Number.isInteger(d.base_version) && ("content" in d || "title" in d) && d.base_version !== p.version) return { status: 409, error: CONFLICT };
      if ("parent_id" in d || "position" in d) return NICHT;          // verschieben gehört nicht zur Übung
      const vorher = { title: p.title, content: p.content };
      if ("title" in d) {
        const titel = String(d.title || "").trim();
        if (!titel) return { status: 400, error: "Der Titel darf nicht leer sein." };
        if (titel !== p.title) {
          const slug = freieAdresse(z, titel, p.id);
          if (slug !== p.slug) { p.alte_slugs = (p.alte_slugs || []).concat(p.slug); p.slug = slug; }
        }
        p.title = titel;
      }
      if ("content" in d) {
        const inhalt = String(d.content || "");
        if (!inhalt.trim() && String(vorher.content || "").trim() && !d.leeren) {
          return { status: 400, error: "Die Seite wäre danach leer. Das wird nicht von allein geschrieben – zum Leeren ausdrücklich bestätigen oder die Seite löschen." };
        }
        p.content = inhalt;
      }
      if (p.title !== vorher.title || p.content !== vorher.content) {
        p.version += 1;
        p.updated_by = ICH;
        p.updated_at = jetzt();
        fassungSchreiben(z, p, typeof d.sitzung === "string" ? d.sitzung : "");
      }
      return { page: seiteJson(z, p) };
    }],
    ["DELETE", /^\/api\/wiki\/pages\/\d+$/, () => NICHT],
    ["POST", /^\/api\/wiki\/pages\/\d+\/duplicate$/, () => NICHT],
    ["PUT", "/api/wiki/reorder", () => NICHT],
    ["POST", "/api/wiki/import", () => NICHT],
    ["PUT", /^\/api\/wiki\/pages\/\d+\/(restrict|creator)$/, () => NICHT],
    ["POST", /^\/api\/wiki\/files(\/zuschnitt|\/drehung)?$/, () => NICHT],
    ["GET", /^\/api\/wiki\/pages\/(\d+)\/backlinks$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      const raus = new Set(verweiseVon(p));
      return { pages: verweisenAuf(z, p).map((q) => Object.assign(kurz(q), { einbau: false })),
               outgoing: lebende(z).filter((q) => q.id !== p.id && namenVon(q).some((s) => raus.has(s))).map(kurz) };
    }],
    ["GET", /^\/api\/wiki\/pages\/(\d+)\/attachments$/, (m, b, z) => (seite(z, +m[1]) ? { files: [] } : ohneSeite)],
    ["GET", /^\/api\/wiki\/pages\/(\d+)\/contributors$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      const mit = [...new Set(z.fassungen.filter((f) => f.page_id === p.id && f.user_id !== p.created_by).map((f) => f.user_id))];
      const eintrag = (uid) => ({ id: uid, name: name(uid), avatar: null });
      return { owner: eintrag(p.created_by), contributors: mit.map(eintrag) };
    }],
    ["PUT", /^\/api\/wiki\/pages\/(\d+)\/favorite$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      z.favoriten = z.favoriten.filter((id) => id !== p.id).concat(b && b.favorite ? [p.id] : []);
      return { favorite: Boolean(b && b.favorite) };
    }],
    ["PUT", /^\/api\/wiki\/pages\/(\d+)\/watch$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      z.beobachtet = z.beobachtet.filter((id) => id !== p.id).concat(b && b.watch ? [p.id] : []);
      return { watch: Boolean(b && b.watch) };
    }],
    ["PUT", /^\/api\/wiki\/pages\/(\d+)\/(icon|options)$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      if (!darfBearbeiten(z, p)) return { status: 403, error: "Keine Berechtigung" };
      if (m[2] === "icon") p.icon = String((b && b.icon) || "").slice(0, 8);
      else if (b && "is_template" in b) p.is_template = b.is_template ? 1 : 0;
      return { page: seiteJson(z, p) };
    }],

    // Wer ist gerade an der Seite? In der Übung niemand sonst – das Konto bekommt den Schreibplatz, wenn es bearbeiten darf.
    ["POST", "/api/wiki/praesenz", (m, b, z) => {
      const d = b || {};
      if (d.weg) return { ok: true };
      const p = seite(z, +d.page_id);
      if (!p) return ohneSeite;
      const darf = darfBearbeiten(z, p);
      return { modus: d.modus === "schreiben" && darf ? "schreiben" : "lesen", version: p.version, darf_schreiben: darf,
               schreiber: null, andere: [] };
    }],

    // Kommentare
    ["GET", /^\/api\/wiki\/pages\/(\d+)\/comments$/, (m, b, z) => {
      if (!seite(z, +m[1])) return ohneSeite;
      return { comments: z.kommentare.filter((c) => c.page_id === +m[1]).sort((a, c) => a.id - c.id).map((c) => kommentarJson(z, c)) };
    }],
    ["POST", /^\/api\/wiki\/pages\/(\d+)\/comments$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      const d = b || {};
      if (!p) return ohneSeite;
      const text = String(d.body || "").trim();
      if (!text) return { status: 400, error: "Der Kommentar ist leer." };
      const eltern = d.parent_id ? z.kommentare.find((c) => c.id === +d.parent_id && c.page_id === p.id) : null;
      if (d.parent_id && !eltern) return { status: 400, error: "Kommentar nicht gefunden." };
      // Eine Antwort erbt die Fundstelle des Kommentars, an dem sie hängt.
      const c = { id: z.naechste++, page_id: p.id, parent_id: eltern ? eltern.id : null, user_id: ICH,
        quote: eltern ? eltern.quote : String(d.quote || "").trim().slice(0, 500),
        quote_before: eltern ? eltern.quote_before : String(d.quote_before || "").trim().slice(0, 120),
        quote_after: eltern ? eltern.quote_after : String(d.quote_after || "").trim().slice(0, 120),
        body: text.slice(0, 5000), resolved: 0, created_at: jetzt() };
      z.kommentare.push(c);
      return { comment: kommentarJson(z, c) };
    }],
    ["PUT", /^\/api\/wiki\/comments\/(\d+)$/, (m, b, z) => {
      const c = z.kommentare.find((x) => x.id === +m[1]);
      const d = b || {};
      if (!c) return { status: 404, error: "Kommentar nicht gefunden" };
      if (!kommentarJson(z, c).can_delete) return { status: 403, error: "Keine Berechtigung" };
      if ("resolved" in d) z.kommentare.filter((x) => x.id === c.id || x.parent_id === c.id).forEach((x) => { x.resolved = d.resolved ? 1 : 0; });
      if ("body" in d) {
        if (c.user_id !== ICH && !VERWALTUNG()) return { status: 403, error: "Nur der Verfasser kann seinen Kommentar ändern." };
        const text = String(d.body || "").trim();
        if (!text) return { status: 400, error: "Der Kommentar ist leer." };
        c.body = text.slice(0, 5000);
      }
      return { ok: true };
    }],
    ["DELETE", /^\/api\/wiki\/comments\/(\d+)$/, (m, b, z) => {
      const c = z.kommentare.find((x) => x.id === +m[1]);
      if (!c) return { status: 404, error: "Kommentar nicht gefunden" };
      if (!kommentarJson(z, c).can_delete) return { status: 403, error: "Keine Berechtigung" };
      z.kommentare = z.kommentare.filter((x) => x.id !== c.id && x.parent_id !== c.id);
      return { ok: true };
    }],

    // Teilen: Bearbeiter und Freigabe für alle Angemeldeten
    ["PUT", /^\/api\/wiki\/pages\/(\d+)\/editors$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      if (!darfLoeschen(p)) return { status: 403, error: "Nur der Ersteller oder die Wiki-Verwaltung kann Bearbeiter freigeben." };
      const ids = new Set(((b && b.user_ids) || []).map(Number).filter((id) => id !== p.created_by));
      p.editors = [...ids].filter((id) => PERSONEN.some((u) => u.id === id) || (p.editors || []).includes(id));
      return { editors: p.editors.map(person).filter(Boolean).sort((a, c) => a.name.localeCompare(c.name, "de")) };
    }],
    ["PUT", /^\/api\/wiki\/pages\/(\d+)\/share$/, (m, b, z) => {
      const p = seite(z, +m[1]);
      if (!p) return ohneSeite;
      if (!VERWALTUNG()) return { status: 403, error: "Veröffentlichen darf nur die Wiki-Verwaltung." };
      p.is_public = b && b.is_public ? 1 : 0;
      p.public_children = p.is_public && b.public_children ? 1 : 0;
      return { page: seiteJson(z, p) };
    }],

    // Verlauf
    ["GET", /^\/api\/wiki\/pages\/(\d+)\/revisions$/, (m, b, z) => {
      if (!z.seiten.some((p) => p.id === +m[1])) return ohneSeite;
      return { revisions: z.fassungen.filter((f) => f.page_id === +m[1]).sort((a, c) => c.id - a.id).map((f) => ({
        id: f.id, title: f.title, format: f.format, created_at: f.created_at, user_id: f.user_id, user_name: name(f.user_id),
        size: new TextEncoder().encode(f.content).length })) };
    }],
    ["GET", /^\/api\/wiki\/revisions\/(\d+)$/, (m, b, z) => {
      const f = z.fassungen.find((x) => x.id === +m[1]);
      if (!f) return { status: 404, error: "Version nicht gefunden" };
      return { revision: { id: f.id, page_id: f.page_id, title: f.title, content: f.content, format: f.format,
                           user_id: f.user_id, created_at: f.created_at } };
    }],
    ["POST", /^\/api\/wiki\/revisions\/(\d+)\/restore$/, (m, b, z) => {
      const f = z.fassungen.find((x) => x.id === +m[1]);
      if (!f) return { status: 404, error: "Version nicht gefunden" };
      const p = z.seiten.find((x) => x.id === f.page_id);
      if (!p) return ohneSeite;
      if (!darfBearbeiten(z, p)) return { status: 403, error: "Keine Berechtigung" };
      if (p.deleted_at) return { status: 409, error: "Diese Seite liegt im Papierkorb. Erst wiederherstellen, dann die Version zurückholen." };
      Object.assign(p, { title: f.title, content: f.content, updated_by: ICH, updated_at: jetzt() });
      p.version += 1;
      fassungSchreiben(z, p, "");
      return { page: seiteJson(z, p) };
    }],

    // Papierkorb
    ["GET", "/api/wiki/trash", (m, b, z) => {
      const geloescht = z.seiten.filter((p) => p.deleted_at);
      const oben = geloescht.filter((p) => !p.parent_id || !geloescht.some((x) => x.id === p.parent_id));
      return { pages: oben.sort((a, c) => String(c.deleted_at).localeCompare(String(a.deleted_at))).map((p) => ({
        id: p.id, title: p.title, slug: p.slug, icon: p.icon, deleted_at: p.deleted_at, parent_id: p.parent_id,
        created_by_name: name(p.created_by), children: geloescht.filter((x) => x.parent_id === p.id).length,
        can_restore: darfLoeschen(p) })) };
    }],
    ["POST", /^\/api\/wiki\/pages\/(\d+)\/restore$/, (m, b, z) => {
      const p = z.seiten.find((x) => x.id === +m[1] && x.deleted_at);
      if (!p) return { status: 404, error: "Diese Seite liegt nicht im Papierkorb." };
      if (!darfLoeschen(p)) return { status: 403, error: "Nur der Ersteller oder die Wiki-Verwaltung kann wiederherstellen." };
      // Liegt die frühere Elternseite noch im Papierkorb, kommt die Seite auf die oberste Ebene; mit ihr kommt zurück, was
      // im selben Zug gelöscht wurde.
      if (p.parent_id && !seite(z, p.parent_id)) p.parent_id = null;
      const ids = teilbaum(z, p.id);
      const zug = p.deleted_at;
      z.seiten.filter((x) => ids.includes(x.id) && x.deleted_at === zug).forEach((x) => { x.deleted_at = null; });
      return { page: seiteJson(z, p), restored: ids.length };
    }],
    ["DELETE", /^\/api\/wiki\/trash\/\d+$/, () => NICHT],
  ];

  /* --- Abläufe -------------------------------------------------------------------------------------------------------- */
  const $ = (sel) => document.querySelector(sel);
  const passt = (abfrage) => window.matchMedia(abfrage).matches;
  const schublade = () => passt("(max-width: 1023px)");             // Seitenbaum hinter „☰“, Suchzeile oben (app.css)
  const leiste = () => passt("(max-width: 599px)");                // Sprechblase als Leiste unten (einfuehrung.js)
  const gliederungImMenue = () => passt("(max-width: 1180px)");     // keine Gliederung, Kommentare unter dem Text (app.css)
  // Wie die Führung „sichtbar“ zählt (einfuehrung.js): mit Fläche, nicht unsichtbar, nicht in [hidden]/[inert].
  const sichtbar = (el) => Boolean(el && el.isConnected && el.getClientRects().length && getComputedStyle(el).visibility !== "hidden"
    && !el.closest("[hidden], [inert], .fuehrung-blase, .fuehrung-rahmen"));
  const finde = (sel) => [...document.querySelectorAll(sel)].find(sichtbar) || null;
  const offenerDialog = () => [...document.querySelectorAll("dialog[open]")].pop() || null;
  // Die Seite mit diesem Titel ist gezeichnet (Lesen, nicht der Editor) – Ziele davor gehörten noch zur vorigen Seite.
  const aufSeite = (titel) => {
    const h = $("#wiki-content h1.seitentitel");
    return Boolean(h) && !document.body.classList.contains("editing") && h.textContent.trim().startsWith(titel);
  };
  /* Ziele: Dass sie im Bild stehen, nicht unter einem Dialog liegen, der gerade zugeht, und nicht in der Schublade, die
     noch hereingleitet, wartet die Führung selbst ab (einfuehrung.js, beruhigen) – hier steht nur, wann ein Ziel zur
     richtigen Seite gehört. */
  const aufSeiteZiel = (titel, sel) => () => (aufSeite(titel) ? finde(sel) : null);
  // „Teilen“ steht als Knopf im Seitenkopf – am Telefon und in schmalen Köpfen am Finger im Menü „⋯“ (app.css, pageMenu).
  const teilenAlsKnopf = () => {
    const k = $("#pg-share");
    if (k && $("#pg-more")) return sichtbar(k);
    return !passt("(pointer: coarse) and (max-width: 640px)");
  };
  const EDITOR = ".toastui-editor-ww-container .ProseMirror";
  const MENUE = (a) => `.menue-schwebend button[data-a="${a}"]`;
  const SEITENTITEL = "#wiki-content h1.seitentitel";
  const neueSeite = () => {
    const h = $(SEITENTITEL);
    return h && !document.body.classList.contains("editing")
      && !/^Übung: (Start|Seite lesen|Zweite Seite|Vorlage)/.test(h.textContent.trim()) ? h : null;
  };
  const baumAuf = (text) => ({ wenn: schublade, ziel: "#wiki-menu", text, warten: { klick: "#wiki-menu" } });
  const teilenSchritte = (titel) => [
    { wenn: teilenAlsKnopf, ziel: aufSeiteZiel(titel, "#pg-share"), text: "Tippe auf „Teilen“.", warten: { klick: "#pg-share" } },
    { wenn: () => !teilenAlsKnopf(), ziel: aufSeiteZiel(titel, "#pg-more"), text: "„Teilen“ steckt hier im Menü „⋯“. Tippe darauf.",
      warten: { klick: "#pg-more" } },
    { wenn: () => !teilenAlsKnopf(), ziel: MENUE("share"), text: "Tippe auf „Teilen“.", warten: { klick: MENUE("share") } },
  ];

  const grund = [
    { titel: "Lesen", start: "/stroemipedia/uebung-start", schritte: [
      baumAuf("Tippe auf „☰“ für den Seitenbaum."),
      { ziel: '#tree li[data-id="910000002"] > .row > a', text: "Links steht der Seitenbaum. Öffne „Übung: Seite lesen“.",
        warten: { klick: '#tree li[data-id="910000002"] > .row > a' }, probe: { klick: '#tree li[data-id="910000002"] > .row > a' } },
      { wenn: () => !gliederungImMenue() && !document.body.classList.contains("toc-aus"),
        ziel: () => (aufSeite("Übung: Seite lesen") && $("#toc a") ? $("#toc") : null),
        text: "Die Gliederung springt zu den Abschnitten der Seite." },
      { wenn: () => !gliederungImMenue() && document.body.classList.contains("toc-aus"), ziel: null,
        text: "Die Gliederung springt zu den Abschnitten der Seite. Bei dir ist sie ausgeblendet – „☰“ oben rechts blendet sie ein." },
      { wenn: gliederungImMenue, ziel: aufSeiteZiel("Übung: Seite lesen", "#pg-more"),
        text: "Die Gliederung der Seite steckt hier im Menü „⋯“. Tippe darauf.", warten: { klick: "#pg-more" } },
      { wenn: gliederungImMenue, ziel: MENUE("toc"), text: "Tippe auf „Inhaltsverzeichnis“.", warten: { klick: MENUE("toc") } },
      { wenn: gliederungImMenue, ziel: "dialog[open] nav.toc",
        text: "Die Gliederung springt zu den Abschnitten der Seite. Tippe auf einen Abschnitt.",
        warten: { klick: "dialog[open] nav.toc a" }, probe: { klick: "dialog[open] nav.toc a" } },
    ] },
    { titel: "Suchen", start: "/stroemipedia/uebung-start", schritte: [
      { wenn: schublade, ziel: "#zeilen-suche", text: "Such nach „Zweite“.", warten: { wert: ["#zeilen-suche", /zweite/i] },
        probe: { tippen: ["#zeilen-suche", "Zweite"] } },
      { wenn: () => !schublade(), ziel: "#wiki-search", text: "Such nach „Zweite“.", warten: { wert: ["#wiki-search", /zweite/i] },
        probe: { tippen: ["#wiki-search", "Zweite"] } },
      { ziel: "#zeilen-treffer a, #search-results a", text: "Gesucht wird in Titel und Text aller Seiten. Öffne den ersten Treffer.",
        warten: { klick: "#zeilen-treffer a, #search-results a" }, probe: { klick: "#zeilen-treffer a, #search-results a" } },
      { ziel: aufSeiteZiel("Übung: Zweite Seite", SEITENTITEL),
        text: "Das ist die gefundene Seite. Am Telefon steht die Suche oben über jeder Seite." },
    ] },
    { titel: "Kommentieren", start: "/stroemipedia/uebung-seite-lesen", schritte: [
      { ziel: aufSeiteZiel("Übung: Seite lesen", "#pg-comment"),
        text: "Mit diesem Knopf kommentierst du die ganze Seite. Für eine bestimmte Stelle markierst du vorher Text im Artikel.",
        warten: { klick: "#pg-comment" } },
      { ziel: "#c-text", text: "Schreib einen Kommentar – Fragen und Hinweise an die Autoren gehören hierher.",
        warten: { wert: ["#c-text", /\S{3}/] }, probe: { tippen: ["#c-text", "Übung: ein Platzhalter-Kommentar"] } },
      { ziel: "#c-save", text: "Speichere den Kommentar.", warten: { anfrage: "POST /api/wiki/pages/910000002/comments" },
        probe: { klick: "#c-save" } },
      // Neben dem Text (ab 1181 px) steht der Kommentar in der Spur rechts; schmaler stehen die Kommentare unter dem Artikel.
      { wenn: () => !gliederungImMenue(), ziel: '#comments .comment[data-cid="910000061"]',
        text: "Dein Kommentar steht jetzt bei der Seite. In der Übung wurde nichts gespeichert." },
      { wenn: gliederungImMenue, ziel: null,
        text: "Dein Kommentar steht jetzt unten bei den Kommentaren der Seite. In der Übung wurde nichts gespeichert." },
    ] },
    { titel: "Bearbeiten", start: "/stroemipedia/uebung-seite-lesen", schritte: [
      { ziel: aufSeiteZiel("Übung: Seite lesen", "#pg-edit"),
        text: "Seiten, die für dich freigegeben sind, kannst du bearbeiten. Tippe auf „Bearbeiten“.", warten: { klick: "#pg-edit" } },
      { ziel: EDITOR, text: "Schreib einen Satz dazu.",
        warten: { wert: [EDITOR, /\S/] }, probe: { tippen: [EDITOR, "Übung: ein Satz. "] } },
      { ziel: "#ed-status", text: "Gespeichert wird von selbst – hier steht der Stand.",
        warten: { bedingung: () => /Gespeichert/.test(($("#ed-status") || {}).textContent || "") }, probe: { klick: "#ed-status" } },
      { ziel: "#ed-read", text: "Zurück zum Lesen.", warten: { klick: "#ed-read" } },
    ] },
  ];

  const redakteur = [
    { titel: "Seite anlegen", start: "/stroemipedia/uebung-start", schritte: [
      baumAuf("Tippe auf „☰“ – über dem Seitenbaum steht „Neue Seite“."),
      { ziel: aufSeiteZiel("Übung: Start", "#btn-new-page"),
        text: "Über „Neue Seite“ legst du eine Seite an – als Unterseite der Seite, die gerade offen ist.",
        warten: { klick: "#btn-new-page" }, probe: { klick: "#btn-new-page" } },
      { ziel: "#nv-los", text: "Leer beginnen oder den Inhalt einer Vorlage übernehmen. Lass „Leer“ gewählt und tippe auf „Weiter“.",
        warten: { klick: "#nv-los" } },
      // Am Telefon passt der leere Editor (480 px hoch) nicht über die Sprechblase – dort ohne Rahmen, der Editor steht oben.
      { wenn: () => !leiste(), ziel: EDITOR,
        text: "Die erste Zeile ist der Seitentitel. Ergänze ihn, etwa zu „Übung: Neue Seite“.",
        warten: { wert: [EDITOR, /\S/] }, probe: { tippen: [EDITOR, "Übung: "] } },
      { wenn: leiste, ziel: null, text: "Die erste Zeile im Editor ist der Seitentitel. Ergänze ihn, etwa zu „Übung: Neue Seite“.",
        warten: { wert: [EDITOR, /\S/] }, probe: { tippen: [EDITOR, "Übung: "] } },
      { ziel: "#ed-save", text: "Leg die Seite an. Danach speichert der Editor von selbst.", warten: { anfrage: "POST /api/wiki/pages" },
        probe: { klick: "#ed-save" } },
      { ziel: neueSeite, text: "Die neue Seite steht jetzt im Seitenbaum unter „Übung: Start“." },
    ] },
    { titel: "Bearbeiten erlauben", start: "/stroemipedia/uebung-zweite-seite", schritte: [
      { ziel: aufSeiteZiel("Übung: Zweite Seite", SEITENTITEL),
        text: "„Übung: Zweite Seite“ hast du angelegt. Deshalb legst du fest, wer sie außer dir bearbeiten darf." },
      ...teilenSchritte("Übung: Zweite Seite"),
      { ziel: "#sh-filter", text: "Such „Übungsperson“.", warten: { wert: ["#sh-filter", /übungsperson/i] },
        probe: { tippen: ["#sh-filter", "Übungsperson"] } },
      { ziel: '#sh-users label:has(input[value="910000051"])',
        text: "Hak „Übungsperson A“ an. Freigegebene bearbeiten die Seite und ihre Unterseiten.",
        warten: { klick: '#sh-users label:has(input[value="910000051"])' }, probe: { klick: '#sh-users label:has(input[value="910000051"])' } },
      { ziel: "#sh-save", text: "Speichere die Freigabe.", warten: { anfrage: "PUT /api/wiki/pages/910000003/editors" },
        probe: { klick: "#sh-save" } },
      { ziel: aufSeiteZiel("Übung: Zweite Seite", SEITENTITEL),
        text: "Übungsperson A darf die Seite jetzt bearbeiten. Zurücknehmen geht ebenso über „Teilen“." },
    ] },
    { titel: "Verlauf", start: "/stroemipedia/uebung-zweite-seite", schritte: [
      { ziel: aufSeiteZiel("Übung: Zweite Seite", "#pg-more"), text: "Im Menü „⋯“ steht der Verlauf der Seite. Tippe darauf.",
        warten: { klick: "#pg-more" } },
      { ziel: MENUE("history"), text: "Tippe auf „Verlauf“.", warten: { klick: MENUE("history") } },
      { ziel: ".rev-list [data-restore]", text: "Jede gespeicherte Fassung bleibt im Verlauf. Hol die ältere Fassung zurück.",
        warten: { klick: ".rev-list [data-restore]" }, probe: { klick: ".rev-list [data-restore]" } },
      { ziel: "dialog[open] #c-ok", text: "Die aktuelle Fassung bleibt dabei im Verlauf erhalten. Bestätige mit „Wiederherstellen“.",
        warten: { anfrage: /^POST \/api\/wiki\/revisions\/\d+\/restore$/ }, probe: { klick: "dialog[open] #c-ok" } },
      { ziel: () => (/Ältere Fassung/.test(($("#article") || {}).textContent || "") ? $("#article") : null),
        text: "Die Seite zeigt wieder die ältere Fassung." },
    ] },
  ];

  const verwaltung = [
    { titel: "Für alle Angemeldeten freigeben", start: "/stroemipedia/uebung-seite-lesen", schritte: [
      { ziel: aufSeiteZiel("Übung: Seite lesen", SEITENTITEL), text: "Als Wiki-Verwaltung gibst du Seiten für alle Angemeldeten frei." },
      ...teilenSchritte("Übung: Seite lesen"),
      { ziel: "label:has(> #sh-public)",
        text: "Freigegebene Seiten lesen auch Konten ohne Stufe in der Strömipedia. Hak „Diese Seite für alle Angemeldeten freigeben“ an.",
        warten: { klick: "label:has(> #sh-public)" }, probe: { klick: "label:has(> #sh-public)" } },
      { ziel: "#sh-save", text: "Speichere die Freigabe.", warten: { anfrage: "PUT /api/wiki/pages/910000002/share" },
        probe: { klick: "#sh-save" } },
      { ziel: aufSeiteZiel("Übung: Seite lesen", "#wiki-content .pubbadge"),
        text: "Die Marke zeigt: Diese Seite lesen jetzt alle Angemeldeten." },
    ] },
    { titel: "Papierkorb", start: "/stroemipedia/uebung-start", schritte: [
      baumAuf("Tippe auf „☰“ für den Seitenbaum."),
      { ziel: "#btn-baum-mehr", text: "Seltene Aktionen stehen im Menü „⋯“ über dem Seitenbaum. Tippe darauf.",
        warten: { klick: "#btn-baum-mehr" }, probe: { klick: "#btn-baum-mehr" } },
      { ziel: MENUE("trash"), text: "Tippe auf „Papierkorb“.", warten: { klick: MENUE("trash") } },
      { ziel: '.trash-list li[data-id="910000004"] [data-a="restore"]',
        text: "Gelöschte Seiten liegen hier, bis jemand sie wiederherstellt oder endgültig löscht. Hol „Übung: Alte Seite“ zurück.",
        warten: { anfrage: "POST /api/wiki/pages/910000004/restore" },
        probe: { klick: '.trash-list li[data-id="910000004"] [data-a="restore"]' } },
      // Erst der neu geöffnete, leere Papierkorb – nicht der, der gerade zugeht.
      { ziel: () => {
        const d = offenerDialog();
        return d && !d.querySelector(".trash-list") ? d.querySelector(".dlg-actions [data-close]") : null;
      }, text: "„Übung: Alte Seite“ steht wieder an ihrem alten Platz im Seitenbaum. Schließ den Papierkorb.",
        warten: { klick: "dialog[open] .dlg-actions [data-close]" } },
    ] },
  ];

  S.einfuehrung.modul("wiki", {
    bestand,
    antworten,
    // Eine Übungsdatei gibt es in der Strömipedia nicht (keine Anhänge im Übungsbestand); der Export (Seitenwechsel auf die
    // Datei) meldet in der Übung „In der Übung gibt es diese Datei nicht.“ (einfuehrung.js).
    dateien: [],
    teile: { grund: { ablaeufe: grund }, redakteur: { ablaeufe: redakteur }, verwaltung: { ablaeufe: verwaltung } },
  });
})();
