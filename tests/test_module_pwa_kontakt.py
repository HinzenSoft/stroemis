"""PWA (installierbar) und Kontaktadressen (01.11.2026, Auftrag planung/material-phase4/auftrag_pwa_kontakt.md):
python tests/test_module_pwa_kontakt.py  oder  pytest tests/test_module_pwa_kontakt.py

  1. Manifest /manifest.webmanifest: Inhalt, Content-Type, Symbole (Dateien, Größen), dev-Fassung mit eigenem Namen.
  2. Service Worker /sw.js: Content-Type, Versionsstempel, nur die Hinweisseite im Speicher, Bereiche, die er nicht anfasst.
  3. Hinweisseite /offline: ohne Mittel von außen, Tokens wie app.css.
  4. Einstellungen „Kontaktadresse“ und „Adresse für Fehlermeldungen“: Gruppe, Vorgaben, Prüfung, leer = entfällt, .env.
  5. Fuß auf allen Vorlagen (angemeldet, Anmeldung, Fehlerseiten, öffentliche Strömipedia, Ersatz-Fehlerseite).
  6. Hinweis „Entwicklungsserver“ mit der Fehleradresse aus der Einstellung.
  7. Bestandsimport: Satz mit der Kontaktadresse; Profil: Abschnitt „App“; CSS (Druck, Karte, Touch).
Das Verhalten im Browser (Installierbarkeit, offline, Standalone, Tippflächen) ist gemessen (bericht_pwakontakt.md).
Alle Konten und Inhalte sind Platzhalter, es geht keine Mail hinaus."""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


class Umgebung:
    """Umgebungsvariablen für die Dauer eines Blocks setzen (None entfernt) – danach wie vorher."""

    def __init__(self, **werte):
        self.werte = werte
        self.alt = {k: os.environ.get(k) for k in werte}

    def __enter__(self):
        for k, v in self.werte.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *a):
        for k, v in self.alt.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _app(tmp):
    os.environ.pop("SMTP_HOST", None)            # nie eine echte Mail
    app = make_app(tmp)
    from app import auth
    auth.send_mail = lambda *a, **k: None
    return app


def _anmelden(c, mail="admin@example.org", pw="geheim123"):
    r = c.post("/api/auth/login", json={"email": mail, "password": pw})
    assert r.status_code == 200, r.get_json()


def _fuss(html):
    m = re.search(r'<footer class="seitenfuss">(.*?)</footer>', html, re.S)
    return m.group(1) if m else None


STANDARD = ('<span class="fuss-teil">Fragen: <a href="mailto:verwalter@stroemis.de">verwalter@stroemis.de</a></span>'
            '<span class="fuss-punkt" aria-hidden="true">·</span>'
            '<span class="fuss-teil">Fehler: <a href="mailto:bugs@stroemis.de">bugs@stroemis.de</a></span>')


# --- 1. Manifest ------------------------------------------------------------------------------------------------------

def test_manifest():
    from PIL import Image
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, Umgebung(STROEMIS_NAME=None):
        app = _app(tmp)
        c = app.test_client()
        r = c.get("/manifest.webmanifest")
        assert r.status_code == 200 and r.content_type == "application/manifest+json"
        m = json.loads(r.get_data(as_text=True))
        assert (m["name"], m["short_name"], m["start_url"], m["scope"], m["display"], m["id"]) == \
            ("strömis.de", "strömis.de", "/", "/", "standalone", "/")
        css = lies("app/static/css/app.css")
        assert m["theme_color"] == "#e30613" and "--rot: #e30613;" in css
        assert m["background_color"] == "#ffffff" and "--weiss: #ffffff;" in css
        zwecke = {(i["sizes"], i["purpose"]) for i in m["icons"]}
        assert zwecke == {("192x192", "any"), ("512x512", "any"), ("192x192", "maskable"), ("512x512", "maskable")}
        for i in m["icons"] + [s["icons"][0] for s in m["shortcuts"]]:
            assert c.get(i["src"]).status_code == 200, i["src"]
            with Image.open(os.path.join(WURZEL, "app", i["src"].lstrip("/"))) as bild:
                assert "%dx%d" % bild.size == i["sizes"], i
                assert bild.mode == "RGB"               # ohne Durchsicht: das Rot reicht bis an den Rand
        # Kurzbefehle zu allen fünf Modulen unter ihren neuen Adressen.
        assert [(s["name"], s["url"]) for s in m["shortcuts"]] == [
            ("Strömipedia", "/"), ("Ankerplätze", "/ankerplaetze"), ("Riegenkarten", "/riegenkarten"),
            ("Materialablage", "/materialablage"), ("Leitstelle", "/leitstelle")]
        # Ohne Anmeldung, ohne Datenbank (ist_statisch), nach jedem Deploy sofort neu.
        assert r.headers["Cache-Control"] == "no-cache"
        from app import einstellungen
        assert einstellungen.ist_statisch("/manifest.webmanifest") and einstellungen.ist_statisch("/sw.js")
        assert not einstellungen.ist_statisch("/offline")
        # Seiten verweisen darauf, dazu das iOS-Symbol und die Angaben für den Startbildschirm.
        seite = c.get("/login").get_data(as_text=True)
        for teil in ('<link rel="manifest" href="/manifest.webmanifest">',
                     '<link rel="apple-touch-icon" href="/static/img/pwa/apple-touch-icon.png">',
                     '<meta name="mobile-web-app-capable" content="yes">',
                     '<meta name="apple-mobile-web-app-capable" content="yes">',
                     '<meta name="apple-mobile-web-app-title" content="strömis.de">',
                     '<meta name="apple-mobile-web-app-status-bar-style" content="default">'):
            assert teil in seite, teil
        # Öffentliche Strömipedia: kein Manifest (wiki.strömis.de leitet alles nach /oeffentlich/), aber das iOS-Symbol.
        oeff = c.get("/oeffentlich/").get_data(as_text=True)
        assert 'rel="manifest"' not in oeff and 'rel="apple-touch-icon"' in oeff
    # dev: eigener Name und Symbole mit Marke.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, Umgebung(STROEMIS_NAME="stroemis-dev"):
        app = _app(tmp)
        c = app.test_client()
        m = c.get("/manifest.webmanifest").get_json(force=True)
        assert m["name"] == m["short_name"] == "strömis.de dev"
        assert all(i["src"].endswith("-dev.png") for i in m["icons"])
        for i in m["icons"]:
            assert c.get(i["src"]).status_code == 200, i["src"]
        seite = c.get("/login").get_data(as_text=True)
        assert '<link rel="apple-touch-icon" href="/static/img/pwa/apple-touch-icon-dev.png">' in seite
        assert '<meta name="apple-mobile-web-app-title" content="strömis.de dev">' in seite
    # Erzeugung dokumentiert und wiederholbar.
    skript = lies("scripts/pwa_symbole.py")
    assert 'QUELLE = os.path.join(WURZEL, "app", "static", "img", "maskottchen.png")' in skript
    assert "ROT = (0xE3, 0x06, 0x13)" in skript
    print("Manifest bestanden.")


# --- 2. Service Worker ------------------------------------------------------------------------------------------------

def test_service_worker():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = _app(tmp)
        c = app.test_client()
        r = c.get("/sw.js")
        assert r.status_code == 200 and r.headers["Content-Type"] == "text/javascript; charset=utf-8"
        assert r.headers["Cache-Control"] == "no-cache"
        text = r.get_data(as_text=True)
        stand = app.config["PWA_STAND"]
        assert re.fullmatch(r"[0-9a-f]{16}", stand)
        assert f'const STAND = "{stand}";' in text and 'const STAND = "entwicklung";' not in text
        # Der Stand hängt an Worker, Hinweisseite und Zeichen – ein anderer Inhalt gibt einen anderen Stand.
        from app import pwa
        assert pwa.stand(app) == stand
        quelle = lies("app/static/js/sw.js")
        assert quelle.count(pwa.STAND_ZEILE) == 1
        # Zwischengespeichert wird nur die Hinweisseite: ein add, kein put, kein zweiter Speicher.
        assert quelle.count("c.add(") == 1 and ".put(" not in quelle and "addAll" not in quelle
        assert 'const OFFLINE = "/offline";' in quelle
        assert 'c.add(new Request(OFFLINE, { cache: "reload", credentials: "omit" }))' in quelle
        # Nicht angefasst: alles außer Seiten per GET, /api, /media, /static, QR-Adressen, Dateien und Protokolle.
        for teil in ('if (req.mode !== "navigate" || req.method !== "GET") return false;',
                     r"if (/^\/(api|media|static|m)\//.test(p)) return false;",
                     r'if (/\.[A-Za-z0-9]{1,8}$/.test(p.slice(p.lastIndexOf("/") + 1))) return false;',
                     r"if (/\/(pdf|sammelprotokoll)$/.test(p)) return false;"):
            assert teil in quelle, teil
        # Nur ein ausbleibendes Netz ersetzt die Seite; Antworten des Servers (auch Fehlerseiten) gehen durch.
        assert "e.respondWith(fetch(e.request).catch(async () => {" in quelle
        # Ablösen beim Deploy: alter Speicher weg, neuer Worker übernimmt.
        assert "self.skipWaiting()" in quelle and "clients.claim()" in quelle
        assert "n.startsWith(SPEICHER) && n !== SPEICHER + STAND" in quelle
        # Angemeldet wird er in common.js – nur im sicheren Kontext, Fehler lassen alles wie bisher.
        co = lies("app/static/js/common.js")
        assert 'if ("serviceWorker" in navigator && window.isSecureContext) {' in co
        assert 'navigator.serviceWorker.register("/sw.js")' in co
        # Am Ursprung ausgeliefert: kein Service-Worker-Allowed nötig; die CSP lässt Manifest und Worker zu (default-src).
        assert "Service-Worker-Allowed" not in r.headers
        csp = c.get("/login").headers["Content-Security-Policy"]
        assert csp.startswith("default-src 'self';") and "worker-src" not in csp and "manifest-src" not in csp
        assert "script-src 'self'" in csp
    print("Service Worker bestanden.")


# --- 3. Hinweisseite --------------------------------------------------------------------------------------------------

def test_offline_seite():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, Umgebung(STROEMIS_NAME=None):
        app = _app(tmp)
        r = app.test_client().get("/offline")
        assert r.status_code == 200 and r.headers["Cache-Control"] == "no-cache"
        html = r.get_data(as_text=True)
        assert "<h1>Keine Verbindung</h1>" in html
        assert "<p>strömis.de braucht das Netz. Versuch es gleich noch einmal.</p>" in html
        assert '<a class="btn" href="">Erneut versuchen</a>' in html
        # Keine Mittel von außen: kein Skript, kein Stylesheet, Bilder nur als data:-Adresse.
        assert "<script" not in html and html.count("<link") == 1
        assert re.search(r'<link rel="icon" href="data:image/svg\+xml;base64,[A-Za-z0-9+/=]+" type="image/svg\+xml">', html)
        assert re.findall(r'src="([^"]*)"', html) and all(s.startswith("data:image/") for s in re.findall(r'src="([^"]*)"', html))
        assert "url(" not in html
        # Tokens mit denselben Werten wie app.css.
        css = lies("app/static/css/app.css")
        wurzel = css[css.index(":root {"):css.index("}", css.index(":root {"))]
        stil = html[html.index(":root {"):html.index("}", html.index(":root {"))]
        tokens = re.findall(r"(--[a-z-]+):\s*([^;]+);", stil)
        assert len(tokens) >= 10
        for name, wert in tokens:
            assert f"{name}: {wert};" in wurzel, (name, wert)
    print("Hinweisseite bestanden.")


# --- 4. Einstellungen -------------------------------------------------------------------------------------------------

def test_einstellungen_kontaktadressen():
    from app import einstellungen
    k, f = einstellungen.NACH_SCHLUESSEL["KONTAKT_EMAIL"], einstellungen.NACH_SCHLUESSEL["FEHLER_EMAIL"]
    assert (k.gruppe, k.titel, k.art) == ("Seite", "Kontaktadresse", "email")
    assert (f.gruppe, f.titel, f.art) == ("Seite", "Adresse für Fehlermeldungen", "email")
    for gut in ("verwalter@stroemis.de", "bugs@strömis.de", " a.b-c+d@sub.example.org "):
        assert k.wert(gut) == gut.strip(), gut
    assert k.wert("") == "" and k.wert("   ") == ""
    for schlecht in ("verwalter", "a@b", "a@b.c", "a b@c.de", "a@b.de?subject=x", "<a@b.de>", "a@b.de, c@d.de",
                     'a"@b.de', "a@b@c.de", "a@b.de#x", "x" * 250 + "@b.de"):
        assert k.wert(schlecht) is None, schlecht
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = _app(tmp)
        assert app.config["KONTAKT_EMAIL"] == "verwalter@stroemis.de" and app.config["FEHLER_EMAIL"] == "bugs@stroemis.de"
        adm = app.test_client()
        _anmelden(adm)
        felder = {x["schluessel"]: x for x in adm.get("/api/admin/einstellungen").json["felder"]}
        assert felder["KONTAKT_EMAIL"]["wert"] == "verwalter@stroemis.de" and felder["KONTAKT_EMAIL"]["quelle"] == "vorgabe"
        assert felder["FEHLER_EMAIL"]["wert"] == "bugs@stroemis.de"
        # Ungültig: 400 mit Satz, der das Feld nennt (admin.js öffnet damit die Gruppe).
        r = adm.put("/api/admin/einstellungen", json={"werte": {"KONTAKT_EMAIL": "keine adresse"}})
        assert r.status_code == 400
        assert r.json["error"] == "„Kontaktadresse“ braucht eine gültige E-Mail-Adresse (oder bleibt leer)."
        # Gültig: gilt sofort im Fuß und für die Materialablage.
        assert adm.put("/api/admin/einstellungen", json={"werte": {"KONTAKT_EMAIL": "fragen@strömis.de"}}).status_code == 200
        html = adm.get("/profil").get_data(as_text=True)
        assert 'Fragen: <a href="mailto:fragen@str%C3%B6mis.de">fragen@strömis.de</a>' in _fuss(html)
        assert 'kontakt: "fragen@strömis.de" };' in html
        # Leer: die Angabe entfällt (auch der Punkt); beide leer: kein Fuß.
        adm.put("/api/admin/einstellungen", json={"werte": {"KONTAKT_EMAIL": ""}})
        fuss = _fuss(adm.get("/profil").get_data(as_text=True))
        assert "Fragen:" not in fuss and "fuss-punkt" not in fuss and "Fehler: " in fuss
        adm.put("/api/admin/einstellungen", json={"werte": {"FEHLER_EMAIL": ""}})
        html = adm.get("/profil").get_data(as_text=True)
        assert _fuss(html) is None and "seitenfuss" not in html and 'kontakt: "" };' in html
        # Zurücksetzen: wieder die Vorgabe.
        for schluessel in ("KONTAKT_EMAIL", "FEHLER_EMAIL"):
            assert adm.delete(f"/api/admin/einstellungen/{schluessel}",
                              headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 200
        assert _fuss(adm.get("/profil").get_data(as_text=True)) == STANDARD
    # .env: gesetzt gilt, leer heißt „keine Angabe“, unbrauchbar → Vorgabe.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
            Umgebung(KONTAKT_EMAIL="ov@example.org", FEHLER_EMAIL="kaputt"):
        app = _app(tmp)
        assert app.config["KONTAKT_EMAIL"] == "ov@example.org" and app.config["FEHLER_EMAIL"] == "bugs@stroemis.de"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, Umgebung(KONTAKT_EMAIL="", FEHLER_EMAIL=None):
        app = _app(tmp)
        assert app.config["KONTAKT_EMAIL"] == ""
    # Leitstelle: Eingabefeld vom Typ E-Mail.
    assert 'f.art === "email" ? "email" : "text"' in lies("app/static/js/admin.js")
    print("Einstellungen bestanden.")


# --- 5. Fuß auf allen Vorlagen ----------------------------------------------------------------------------------------

def test_fuss_auf_allen_seiten():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = _app(tmp)
        anon = app.test_client()
        for pfad in ("/login", "/register", "/forgot", "/reset", "/oeffentlich/", "/oeffentlich/irgendwas", "/offline-gibt-es-nicht",
                     "/materialablage/pruefen"):
            r = anon.get(pfad)
            html = r.get_data(as_text=True)
            if pfad == "/offline-gibt-es-nicht":
                assert r.status_code == 404
            assert _fuss(html) == STANDARD, pfad
            assert html.count('class="seitenfuss"') == 1, pfad
        adm = app.test_client()
        _anmelden(adm)
        for pfad in ("/", "/stroemipedia", "/ankerplaetze", "/riegenkarten", "/leitstelle", "/profil", "/materialablage",
                     "/materialablage/bestand", "/materialablage/katalog", "/seite-gibt-es-nicht"):
            r = adm.get(pfad)
            html = r.get_data(as_text=True)
            assert _fuss(html) == STANDARD, (pfad, r.status_code)
        # 403-Seite eines Kontos ohne Modul ebenfalls.
        anon.post("/api/auth/register", json={"email": "ohne@example.org", "password": "passwort1", "name": "Ohne Modul",
                                              "gliederung": "OG Platzhalter"})
        uid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "ohne@example.org"][0]["id"]
        adm.post(f"/api/admin/users/{uid}/approve", json={})
        adm.put(f"/api/admin/users/{uid}", json={"rechte": {"wiki": 0, "karte": 0, "pruefungen": 0, "material": 0,
                                                           "verwaltung": 0}})
        c = app.test_client()
        _anmelden(c, "ohne@example.org", "passwort1")
        r = c.get("/leitstelle")
        assert r.status_code == 403 and _fuss(r.get_data(as_text=True)) == STANDARD
        # Ersatz-Fehlerseite (wenn schon das Zeichnen scheitert): der Fuß ohne Vorlage.
        import app as paket
        alt = paket.render_template

        def kaputt(*a, **k):
            raise RuntimeError("Platzhalter")
        paket.render_template = kaputt
        try:
            with app.test_request_context("/x"):
                text, code = paket.fehlerseite(500, "Platzhalter")
        finally:
            paket.render_template = alt
        assert code == 500
        assert ('<footer><p><small>Fragen: <a href="mailto:verwalter@stroemis.de">verwalter@stroemis.de</a> · '
                'Fehler: <a href="mailto:bugs@stroemis.de">bugs@stroemis.de</a></small></p></footer>') in text
    # Vorlagen: base.html und public.html binden den Fuß ein, alle Seiten erben von base.html.
    assert lies("app/templates/base.html").count('{% include "_fuss.html" %}') == 1
    assert lies("app/templates/public.html").count('{% include "_fuss.html" %}') == 1
    for v in ("admin", "error", "index", "login", "profil", "pruefungen", "wiki", "wiki_lesemodus"):
        assert lies(f"app/templates/{v}.html").startswith('{% extends "base.html" %}'), v
    for v in ("pruefen", "seite"):
        assert lies(f"app/material/templates/material/{v}.html").startswith('{% extends "base.html" %}'), v
    print("Fuß bestanden.")


def test_fuss_css_und_karte():
    css = lies("app/static/css/app.css")
    teil = css[css.index("/* --- Fuß jeder Seite"):css.index("/* Kommentar-Reiter */")]
    assert "color: var(--grau); font-size: var(--fs-klein);" in teil
    assert "main.map-shell ~ .seitenfuss { display: none; }" in teil
    assert "@media print { .seitenfuss { display: none !important; } }" in teil
    assert "@media (pointer: coarse) {\n  .seitenfuss { padding-top: 2px;" in teil
    assert "  .seitenfuss a { display: inline-flex; align-items: center; min-height: 44px; }\n}" in teil
    # Nie fest oder klebend.
    assert "position: fixed" not in teil and "position: sticky" not in teil
    # Karte: der Fuß wandert ans Ende des Panels.
    mp = lies("app/static/js/map.js")
    assert ('const fuss = document.querySelector("body > .seitenfuss");\n'
            '    if (fuss) { const kopie = fuss.cloneNode(true); kopie.classList.add("im-panel"); panelBody.append(kopie); }') in mp
    print("Fuß-CSS bestanden.")


# --- 6. Hinweis „Entwicklungsserver“ ----------------------------------------------------------------------------------

def test_dev_hinweis_aus_einstellung():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, Umgebung(STROEMIS_NAME="stroemis-dev"):
        app = _app(tmp)
        adm = app.test_client()
        _anmelden(adm)
        html = adm.get("/profil").get_data(as_text=True)
        assert '<a href="mailto:bugs@stroemis.de?subject=str%C3%B6mis.de%20dev%3A%20">bugs@stroemis.de</a>' in html
        assert adm.put("/api/admin/einstellungen", json={"werte": {"FEHLER_EMAIL": "fehler@example.org"}}).status_code == 200
        adm.post("/api/auth/logout", json={})
        _anmelden(adm)
        html = adm.get("/profil").get_data(as_text=True)
        assert 'id="dev-hinweis"' in html
        assert ('<a href="mailto:fehler@example.org?subject=str%C3%B6mis.de%20dev%3A%20">fehler@example.org</a> '
                'schicken.</p>') in html
        assert "bugs@stroemis.de" not in html
        # Leer: der Satz entfällt, der Hinweis bleibt.
        adm.put("/api/admin/einstellungen", json={"werte": {"FEHLER_EMAIL": ""}})
        adm.post("/api/auth/logout", json={})
        _anmelden(adm)
        html = adm.get("/profil").get_data(as_text=True)
        assert 'id="dev-hinweis"' in html and "Fehler und Verbesserungsvorschläge" not in html
    assert "bugs@stroemis.de" not in lies("app/templates/base.html")
    print("dev-Hinweis bestanden.")


# --- 7. Bestandsimport, Profil ----------------------------------------------------------------------------------------

def test_bestandsimport_satz_und_profil():
    mj = lies("app/material/static/material.js")
    assert "      ${importKontakt()}\n      <section class=\"section mat-import\" id=\"bi-neu\"" in mj
    teil = mj[mj.index("function importKontakt() {"):mj.index("async function bestandsimport() {")]
    assert 'const adresse = (window.STROEMIS && STROEMIS.kontakt) || "";' in teil
    assert 'if (!adresse) return "";' in teil
    assert "Übernimmst du einen bestehenden Bestand? Stimm dich vorher mit der\n      Plattform-Verwaltung ab:" in teil
    assert '<span class="kurz">Übernahme abstimmen:</span> <a href="${esc(href)}">${esc(adresse)}</a>' in teil
    assert "info" not in teil.lower().replace("infoknopf", "")       # kein „i“: sichtbarer Satz
    mc = lies("app/material/static/material.css")
    assert ".mat-import-kontakt .kurz { display: none; }\n@container mat-seite (max-width: 600px) {" in mc
    # Profil: Abschnitt „App“, zunächst verborgen; common.js schaltet Knopf oder iOS-Anleitung.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = _app(tmp)
        adm = app.test_client()
        _anmelden(adm)
        html = adm.get("/profil").get_data(as_text=True)
        assert '<section class="section hidden" id="app-installieren" aria-labelledby="app-titel">' in html
        assert '<button class="btn secondary hidden" type="button" id="app-installieren-knopf">App installieren</button>' in html
        assert "in Safari „Teilen“ antippen, dann „Zum Home-Bildschirm“." in html
    co = lies("app/static/js/common.js")
    assert 'window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); angebot = e; zeigen(); });' in co
    assert 'window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true' in co
    print("Bestandsimport und Profil bestanden.")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
