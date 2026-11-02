"""Anleitungsverweise und Nachträge aus den Modul-Artikeln (01.11.2026):  python tests/test_module_anleitung.py  oder pytest …

Teil A: „Anleitung“ im Seitenkopf und „Mehr dazu in der Strömipedia“ in den vorhandenen „i“ von Strömipedia,
Ankerplätzen und Riegenkarten – dieselben Regeln wie in der Materialablage (app/anleitung.py: Titel unter der Wurzel,
Anker über die Kennung, nur wer lesen darf, fehlt die Seite, kein Link). Teil B: Vorlagen beim Anlegen, Leitung beim
Import, gesperrte Kriterien, Herkunft der Position. Teil C: die Fehler aus den Artikeln. Seiteninhalte sind Platzhalter;
die Titel und Überschriften sind die der Artikel (TABELLEN)."""
import html
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _konten, anmelden, make_app, neues_konto  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIKEL = {"wiki": "/home/harness/wiki-stroemipedia/artikel", "karte": "/home/harness/wiki-ankerplaetze/artikel",
           "pruefungen": "/home/harness/wiki-riegenkarten/artikel"}
JS = {"wiki": "app/static/js/wiki.js", "karte": "app/static/js/map.js", "pruefungen": "app/static/js/pruefungen.js"}


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json(silent=True))
    return r.get_json()


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def verweise(c, pfad):
    """Die Adressen, die die Seite dem Browser mitgibt (data-anleitung am Rahmen)."""
    seite = c.get(pfad)
    assert seite.status_code == 200, (pfad, seite.status_code)
    m = re.search(r'data-anleitung="([^"]*)"', seite.get_data(as_text=True))
    assert m, pfad
    return json.loads(html.unescape(m.group(1)))


def start(tmp):
    app = make_app(tmp)
    adm = anmelden(app, "admin@example.org", "geheim123")
    _konten(app)["adm"] = adm
    return app, adm


def freigeben(adm, s, unterseiten=True):
    ok(adm.put(f"/api/wiki/pages/{s['id']}/share", json={"is_public": True, "public_children": unterseiten}))


def seite(adm, titel, inhalt, eltern=None):
    d = {"title": titel, "content": inhalt}
    if eltern:
        d["parent_id"] = eltern
    return ok(adm.post("/api/wiki/pages", json=d), 201)["page"]


# --- Teil A: Tabellen und Artikel ----------------------------------------------------------------------------------------

def test_tabellen_stehen_in_den_artikeln():
    """Alle Titel und Anker der drei Tabellen gibt es in den Artikeln, wenn sie neben dem Repository liegen
    (Arbeitsrechner); sonst nur die Form der Tabellen. Die Materialablage prüft test_material_anleitung."""
    from app import anleitung
    assert set(anleitung.TABELLEN) == {"wiki", "karte", "pruefungen"}
    for modul, (wurzel, themen) in anleitung.TABELLEN.items():
        assert themen.get("uebersicht") == (wurzel, ""), modul
        for thema, (titel, anker) in themen.items():
            assert re.fullmatch(r"[a-z_]+", thema) and titel and (not anker or re.fullmatch(r"[a-z0-9-]+", anker)), thema
        if not os.path.isdir(ARTIKEL[modul]):
            continue
        seiten = {}
        for ordner, _, dateien in os.walk(ARTIKEL[modul]):
            for d in dateien:
                if d.endswith(".md"):
                    with open(os.path.join(ordner, d), encoding="utf-8") as fh:
                        text = fh.read()
                    seiten[text.splitlines()[0].lstrip("# ").strip()] = anleitung.kennungen(text)
        assert wurzel in seiten, (modul, wurzel)
        for thema, (titel, anker) in themen.items():
            assert titel in seiten, (modul, thema, titel)
            assert not anker or anker in seiten[titel], (modul, thema, titel, anker)


def test_oberflaeche_fragt_nur_nach_themen_der_tabelle():
    """Jedes Thema der Tabelle hat eine Stelle in der Oberfläche und umgekehrt (keine toten Einträge)."""
    from app import anleitung
    for modul, (_, themen) in anleitung.TABELLEN.items():
        js = lesen(JS[modul])
        benutzt = set(re.findall(r'(?:mehrDazu|anleitungKopf|anleitungUrl|S\.anleitung\.(?:kopf|mehrDazu|url))\("([a-z_]+)"', js))
        benutzt |= set(re.findall(r', (?:true|false), "([a-z_]+)"\);', js))                       # map.js openPanel
        benutzt |= {x for t in re.findall(r'mehrDazu\(isNew \? "([a-z_]+)" : "([a-z_]+)"\)', js) for x in t}
        assert benutzt <= set(themen), (modul, benutzt - set(themen))
        assert set(themen) <= benutzt, (modul, set(themen) - benutzt)
    # Die Materialablage behält ihre eigene Tabelle und ihr Willkommen; die Suche ist dieselbe.
    from app.material.services import anleitung as mat
    assert mat.WURZEL == "Materialablage" and "uebersicht" in mat.THEMEN and mat.kennungen is anleitung.kennungen
    assert "allgemein.aufloesen(WURZEL, THEMEN, user)" in lesen("app/material/services/anleitung.py")


def test_hilfen_in_common_und_kein_link_auf_die_offene_seite():
    common = lesen("app/static/js/common.js")
    teil = common[common.index("window.S.anleitung = (function () {"):]
    for stelle in ('document.querySelector("[data-anleitung]")', '`/stroemipedia/${ausser}`',
                   'target="_blank" rel="noopener">Mehr dazu in der Strömipedia</a></span>',
                   '<a class="lnk kopf-anleitung" href="${window.S.esc(u)}"${tab}>Anleitung<span class="nur-vorlesen"> in der Strömipedia</span></a>',
                   "return { url, mehrDazu, kopf };"):
        assert stelle in teil, stelle
    wiki = lesen(JS["wiki"])
    # Die Seite „Strömipedia“ liegt in der Strömipedia: Kein Link zeigt auf die Seite, die gerade offen ist.
    assert 'const offeneSeite = () => (state.editorNeu ? "" : (state.current && state.current.slug) || "");' in wiki
    assert 'const anleitungUrl = (thema) => S.anleitung.url(thema, { ausser: offeneSeite() });' in wiki
    assert 'const mehrDazu = (thema) => S.anleitung.mehrDazu(thema, { ausser: offeneSeite() });' in wiki
    assert '<h1>Strömipedia</h1>${S.anleitung.kopf("uebersicht", { neuerTab: false })}' in wiki       # in der Anwendung
    assert 'if (a === "anleitung") return navigate(slugAus(anleitungUrl("seite")));' in wiki
    css = lesen("app/static/css/app.css")
    assert ".kopf-anleitung { display: inline-block; flex: none; }" in css
    assert ":is(.page-head, .wiki-head) > .kopf-anleitung { margin-right: auto; }" in css


def test_aufloesung_je_modul_mit_den_rechten_der_stroemipedia():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, adm = start(tmp)
        red, _ = neues_konto(app, "red@example.org", rechte={"wiki": 2, "karte": 2, "pruefungen": 2})
        ohne, _ = neues_konto(app, "ohne@example.org", rechte={"wiki": 0, "karte": 1, "pruefungen": 1})
        # Ohne Artikel: nichts – kein Link, keine Meldung.
        assert verweise(red, "/stroemipedia") == {} and verweise(red, "/ankerplaetze") == {}
        assert verweise(red, "/riegenkarten") == {}
        w = seite(adm, "Strömipedia", "# Strömipedia\n\nPlatzhalter\n")
        lf = seite(adm, "Lesen und Finden", "# Lesen und Finden\n\n## Kopfzeile einer Seite\n\nPlatzhalter\n", w["id"])
        ed = seite(adm, "Der Editor", "# Der Editor\n\n## Auswahlleiste\n\n```\n## Synchronisierte Abschnitte\n```\n", w["id"])
        tf = seite(adm, "Teilen und Freigaben", "# Teilen und Freigaben\n\n## Bearbeiten erlauben\n", w["id"])
        ok(adm.put(f"/api/wiki/pages/{tf['id']}/restrict", json={"read_restricted": True}))
        a = seite(adm, "Ankerplätze", "# Ankerplätze\n\nPlatzhalter\n")
        alben = seite(adm, "Alben", "# Alben\n\n## Album anlegen\n\n## Album bearbeiten\n", a["id"])
        r = seite(adm, "Riegenkarten", "# Riegenkarten\n\nPlatzhalter\n")
        lg = seite(adm, "Lehrgänge", "# Lehrgänge\n\n## Die Lehrgangsseite\n", r["id"])
        # Gleichnamige Seite in einem anderen Artikel: zählt nicht (nur der Teilbaum unter der Wurzel).
        seite(adm, "Alben", "# Alben\n\n## Album in der Seitenleiste\n", r["id"])
        # Nicht freigegeben: keine Links – für niemanden (Entscheidung nach der Sicherheitsprüfung, 01.11.2026).
        for c in (red, adm, ohne):
            assert verweise(c, "/ankerplaetze") == {} and verweise(c, "/riegenkarten") == {}
        assert verweise(red, "/stroemipedia") == {} and verweise(adm, "/stroemipedia") == {}
        # Strömipedia einzeln freigegeben („Teilen und Freigaben“ bleibt lesebeschränkt), die beiden anderen samt Unterseiten.
        for s in (w, lf, ed):
            freigeben(adm, s, unterseiten=False)
        freigeben(adm, a)
        freigeben(adm, r)

        v = verweise(red, "/stroemipedia")
        assert v["uebersicht"] == f"/stroemipedia/{w['slug']}"
        assert v["seite"] == f"/stroemipedia/{lf['slug']}#kopfzeile-einer-seite"
        assert v["editor"] == f"/stroemipedia/{ed['slug']}"
        assert v["textfarbe"] == f"/stroemipedia/{ed['slug']}#auswahlleiste"
        assert v["abschnitt_einbinden"] == f"/stroemipedia/{ed['slug']}"        # Überschrift nur im Codeblock
        assert "bearbeiten_erlauben" not in v                                  # lesebeschränkt = nie freigegeben
        assert "papierkorb" not in v                                           # Seite fehlt
        assert verweise(adm, "/stroemipedia") == v                              # auch für die Wiki-Verwaltung
        assert verweise(red, f"/stroemipedia/{lf['slug']}") == v               # jede Seite der Strömipedia dasselbe

        k = verweise(red, "/ankerplaetze")
        assert k == {"uebersicht": f"/stroemipedia/{a['slug']}", "album": f"/stroemipedia/{alben['slug']}",
                     "album_neu": f"/stroemipedia/{alben['slug']}#album-anlegen",
                     "album_bearbeiten": f"/stroemipedia/{alben['slug']}#album-bearbeiten"}, k
        p = verweise(red, "/riegenkarten")
        assert p == {"uebersicht": f"/stroemipedia/{r['slug']}", "lehrgang": f"/stroemipedia/{lg['slug']}#die-lehrgangsseite",
                     "ausbilder": f"/stroemipedia/{lg['slug']}", "katalog_vorlage": f"/stroemipedia/{lg['slug']}"}, p
        assert verweise(red, "/riegenkarten/kataloge") == p
        # Ohne Stufe in der Strömipedia (Lesemodus): dasselbe – es zählen ohnehin nur freigegebene Seiten.
        assert verweise(ohne, "/ankerplaetze") == k and verweise(ohne, "/riegenkarten") == p
        # Eine nicht freigegebene Unterseite (Redakteur, eigene Wurzel nur selbst freigegeben) lenkt nicht um.
        freigeben(adm, a, unterseiten=False)
        assert verweise(red, "/ankerplaetze") == {"uebersicht": f"/stroemipedia/{a['slug']}"}
        freigeben(adm, a)
        # Wurzel im Papierkorb: keine Links mehr.
        ok(adm.delete(f"/api/wiki/pages/{a['id']}", headers=H))
        assert verweise(red, "/ankerplaetze") == {}


def test_materialablage_wie_vorher():
    """Die Materialablage findet ihren Artikel wie vorher – auch wenn daneben die Artikel der anderen Module liegen."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, adm = start(tmp)
        leser, _ = neues_konto(app, "leser@example.org", rechte={"material": 1, "wiki": 1})
        m = seite(adm, "Materialablage", "# Materialablage\n\nPlatzhalter\n")
        pr = seite(adm, "Prüfung", "# Prüfung\n\n## Prüfung starten\n", m["id"])
        seite(adm, "Strömipedia", "# Strömipedia\n")
        aussen = seite(adm, "Prüfung", "# Prüfung\n\n## Prüfung starten\n")      # gleichnamig, außerhalb
        assert verweise(leser, "/materialablage/pruefungen") == {}
        freigeben(adm, m)
        freigeben(adm, aussen)
        v = verweise(leser, "/materialablage/pruefungen")
        assert v["uebersicht"] == f"/stroemipedia/{m['slug']}"
        assert v["pruefung_neu"] == f"/stroemipedia/{pr['slug']}#pruefung-starten"
        assert set(v) == {"uebersicht", "pruefungen", "pruefung_neu", "pruefung", "offene_pruefungen", "eingangspruefung"}, v


# --- Teil B ----------------------------------------------------------------------------------------------------------------

def test_vorlagen_beim_anlegen():
    """B1: „Neue Seite“ bietet nur Vorlagen an, die das Konto lesen darf; der Inhalt wird kopiert, die neue Seite verweist
    auf dieselben Dateien wie die Vorlage (wie Duplizieren) und hängt sonst nicht an ihr."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, adm = start(tmp)
        red, _ = neues_konto(app, "red@example.org", rechte={"wiki": 2})
        assert ok(red.get("/api/wiki/templates"))["pages"] == []
        offen = seite(adm, "Vorlage Bericht", "# Vorlage Bericht\n\n## Ablauf\n\n![Bild](/media/wiki/demo-platzhalter.png)\n")
        geheim = seite(adm, "Vorlage intern", "# Vorlage intern\n\nPlatzhalter\n")
        for s in (offen, geheim):
            ok(adm.put(f"/api/wiki/pages/{s['id']}/options", json={"is_template": True}))
        ok(adm.put(f"/api/wiki/pages/{geheim['id']}/restrict", json={"read_restricted": True}))
        assert [p["slug"] for p in ok(red.get("/api/wiki/templates"))["pages"]] == [offen["slug"]]
        assert {p["slug"] for p in ok(adm.get("/api/wiki/templates"))["pages"]} == {offen["slug"], geheim["slug"]}
        # Was der Editor nach „Weiter“ anlegt: der Inhalt ohne Titelzeile unter „# Neue Seite“.
        v = ok(red.get(f"/api/wiki/pages/{offen['slug']}?leise=1"))["page"]
        inhalt = re.sub(r"^\s*#[ \t]+[^\n]*\n*", "", v["content"])
        neu = ok(red.post("/api/wiki/pages", json={"title": "Neue Seite", "content": f"# Neue Seite\n\n{inhalt}"}), 201)["page"]
        from app import db
        with app.app_context():
            assert db.query("SELECT file FROM wiki_page_files WHERE page_id = ?", (neu["id"],)) == [{"file": "demo-platzhalter.png"}]
        # Danach hängt nichts an der Vorlage: ändern und in den Papierkorb legen lässt die neue Seite unverändert.
        ok(adm.put(f"/api/wiki/pages/{offen['id']}", json={"title": "Vorlage Bericht", "content": "# Vorlage Bericht\n\nanders\n",
                                                          "base_version": v["version"]}))
        ok(adm.delete(f"/api/wiki/pages/{offen['id']}", headers=H))
        n = ok(red.get(f"/api/wiki/pages/{neu['slug']}"))["page"]
        assert "## Ablauf" in n["content"] and "anders" not in n["content"] and not n["is_template"]
    js = lesen(JS["wiki"])
    teil = js[js.index("  async function neueSeite(parentId) {"):js.index("  /* Papierkorb: wiederherstellen")]
    for stelle in ('api("/api/wiki/templates")', "if (!vorlagen.length) { if (leaveEditor()) openEditor({ parent_id: parentId }); return; }",
                   '<h2>Neue Seite</h2>', 'zeile("", "Leer", true)', '<button class="btn" id="nv-los" type="button">Weiter</button>',
                   '?leise=1`', "if (!v.is_template)", "if (!leaveEditor()) { los.disabled = false; return; }",
                   "openEditor({ parent_id: parentId, content: inhalt });"):
        assert stelle in teil, stelle
    assert 'if (a === "child") return neueSeite(page.id);' in js
    assert "neueSeite(state.current && state.current.can_create ? state.current.id : null);" in js


def test_import_als_neuer_lehrgang_macht_zur_leitung():
    """B2: Wer importiert, wird Leitung – auch mit Stufe Verwaltung (wie die vorbelegte Zeile im Dialog)."""
    from test_pruefungen import _import, _vorschau, _xlsx
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, adm = start(tmp)
        verw, verw_id = neues_konto(app, "verw@example.org", rechte={"pruefungen": 3})
        red, red_id = neues_konto(app, "red@example.org", rechte={"pruefungen": 2})
        for c, uid in ((verw, verw_id), (red, red_id)):
            v = _vorschau(c, _xlsx([["Vorname", "Nachname"], ["Ida", "Import"]]))
            assert v.status_code == 200, v.get_json()
            r = _import(c, _xlsx([["Vorname", "Nachname"], ["Ida", "Import"]]))
            assert r.status_code == 201, r.get_json()
            ausb = r.json["lehrgang"]["ausbilder"]
            assert [(a["user_id"], a["ist_leitung"]) for a in ausb] == [(uid, True)], ausb
        # Beim Anlegen über die Schnittstelle ohne Zeile bleibt es für die Verwaltung wie bisher (der Dialog belegt vor).
        lg = ok(verw.post("/api/pruefungen/lehrgaenge", json={"titel": "DEMO-Lehrgang"}), 201)["lehrgang"]
        assert lg["ausbilder"] == []


def test_kriterien_eingefrorener_leistungen_in_der_oberflaeche():
    """B3: Der Server sperrt (test_pruefungen); die Oberfläche zeigt die Kriterien nur zum Lesen und einen Satz statt
    „Kriterium anlegen“ – derselbe Satz wie die 409."""
    import app.api_pruefungen as ap
    js = lesen(JS["pruefungen"])
    assert f'const KRITERIEN_EINGEFROREN = "{ap.KRITERIEN_EINGEFROREN}";' in js
    teil = js[js.index("  function kriterienListeHtml(l) {"):js.index("  function leistungDialog(l) {")]
    gesperrt = teil[teil.index("if (l.kriterien_eingefroren) {"):teil.index("return `<div id=\"krit-wrap\">\n      ${ks.length")]
    assert '<p class="help krit-gesperrt">${esc(KRITERIEN_EINGEFROREN)}</p>' in gesperrt
    assert "krit-neu-go" not in gesperrt and "data-krit-bez" not in gesperrt and "data-krit-del" not in gesperrt
    assert 'if (!$("#krit-neu-go", body)) return;          // eingefroren: nur zum Lesen' in js
    assert "l.kriterien_eingefroren = frisch.kriterien_eingefroren;" in js


def test_bild_bearbeiten_behaelt_die_herkunft():
    """B4: „(manuell)“ nur, wenn die Position im Dialog geändert wurde."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, adm = start(tmp)
        aid = ok(adm.post("/api/albums", json={"title": "DEMO-Album", "category": "seil"}), 201)["album"]["id"]
        from app import db
        with app.app_context():
            pid = db.execute("INSERT INTO photos (album_id, owner_id, file, original_name, lat, lon, geo_source, created_at) "
                             "VALUES (?, 1, 'demo.jpg', 'demo.jpg', 51.5, 10.25, 'exif', ?)", (aid, db.now()))
        # Unverändert mitgeschickt (wie ein älteres Formular): Herkunft bleibt.
        ph = ok(adm.put(f"/api/photos/{pid}", json={"title": "DEMO-Titel", "lat": "51.5", "lon": "10.25"}))["photo"]
        assert (ph["title"], ph["geo_source"], ph["lat"], ph["lon"]) == ("DEMO-Titel", "exif", 51.5, 10.25), ph
        ph = ok(adm.put(f"/api/photos/{pid}", json={"note": "DEMO"}))["photo"]
        assert ph["geo_source"] == "exif"
        ph = ok(adm.put(f"/api/photos/{pid}", json={"lat": "51.6", "lon": "10.25"}))["photo"]
        assert (ph["geo_source"], ph["lat"]) == ("manual", 51.6), ph
        ph = ok(adm.put(f"/api/photos/{pid}", json={"lat": None, "lon": None}))["photo"]
        assert (ph["geo_source"], ph["lat"]) == (None, None), ph
    js = lesen(JS["karte"])
    assert 'if (lat !== String(p.lat ?? "") || lon !== String(p.lon ?? "")) {' in js


# --- Teil C ----------------------------------------------------------------------------------------------------------------

def test_neue_seite_ohne_fremde_kommentare():
    """C1: Der Editor einer neuen Seite zeigt keine Kommentare der zuvor geöffneten Seite – auch keine, die erst danach
    eintreffen."""
    js = lesen(JS["wiki"])
    teil = js[js.index("  function openEditor(p) {"):js.index("    const crumbs = isNew ? [] : ancestors(p);")]
    assert 'if (isNew) { state.comments = []; commentsEl.innerHTML = ""; }' in teil
    lade = js[js.index("  async function loadComments() {"):js.index("  /* Ein Kommentar samt Antworten")]
    assert "if (!state.current || state.current.id !== p.id || state.editorNeu) return;" in lade


def test_album_position_uebernehmen():
    """C4: Den Knopf gibt es nur mit einer echten Albumposition; nach dem Platzieren rechnet die Seite sie wie der Server
    nach; ohne Ziel geht nichts zum Server (lat/lon null hieße „Position entfernen“)."""
    js = lesen(JS["karte"])
    assert "letztePos" not in js
    assert "const albumPos = !!(state.album && state.album.lat != null && state.album.lon != null);" in js
    teil = js[js.index("  async function setLocation(p, lat, lon) {"):js.index("  /* --- Bild-Detail")]
    assert 'if (lat == null || lon == null) return toast("Keine Position zum Übernehmen – bitte auf die Karte tippen.", true);' in teil
    assert teil.index("albumPositionNachfuehren(p.id, lat, lon);") < teil.index('toast("Position gespeichert");')
    assert "a.lat = mit.length ? mit.reduce((n, x) => n + x.lat, 0) / mit.length : null;" in teil


def test_dialogtext_und_dateiauswahl_der_ankerplaetze():
    """C5: Wer ein Album sieht; C6: Die Dateiauswahl nimmt genau, was der Server annimmt."""
    js = lesen(JS["karte"])
    assert '<p class="help">Alle mit Zugang zu den Ankerplätzen können es sehen.</p>' in js
    assert "Alle angemeldeten Nutzer" not in js
    from app.images import ALLOWED_EXT, MEDIEN_ACCEPT, VIDEO_EXT, _MEDIENTYPEN
    teile = MEDIEN_ACCEPT.split(",")
    assert {t for t in teile if t.startswith(".")} == ALLOWED_EXT | VIDEO_EXT
    assert set(_MEDIENTYPEN) == ALLOWED_EXT | VIDEO_EXT
    assert not any(x in MEDIEN_ACCEPT for x in ("gif", "bmp", "avif", "image/*", "video/*"))
    assert 'accept="{{ accept }}"' in lesen("app/templates/index.html")
    assert "const ENDUNGEN = new Set(fileInput.accept.split" in js and "gif|" not in js
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, adm = start(tmp)
        seite_html = adm.get("/ankerplaetze").get_data(as_text=True)
        assert f'accept="{html.escape(MEDIEN_ACCEPT)}"' in seite_html


def test_css_der_riegenkarten():
    """C2: „mangelhaft Kriterien 2/3“ bleibt in der Zelle; C3: Abstand über „Spalten und Zuordnung“."""
    css = lesen("app/static/css/pruefungen.css")
    assert "/* Nachtrag 01.11.2026 (C2)" in css and ".zelle .txt > :is(.anhang, .krit-stand) { display: inline-block; }" in css
    assert '<h3 class="abgesetzt">Spalten und Zuordnung</h3>' in lesen(JS["pruefungen"])
    assert "h3.abgesetzt { margin-top: 18px; }" in lesen("app/static/css/app.css")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print("ok", name)
