"""UI/UX vor dem Merge, Teil U3 „übrige Module“ (27.10.2026, Auftrag planung/material-phase4/auftrag_uiux_bau.md):
python tests/test_module_uiux_u3.py  oder  pytest tests/test_module_uiux_u3.py

  C10 Hinweis „Entwicklungsserver“ nach jeder Anmeldung – nur auf dev, genau einmal, nicht ohne Anmeldung (Flask-Client).
  C1  Anmeldeseiten: Formular am Telefon zuerst.   C5  Texte (Leitstelle, Ankerplätze, Plattform-Verwaltung, 403-Weg …).
  C2/C3/C7/C8/C9/C12 Strömipedia und Ankerplätze, C4 Einstellungen, C6 Reiterverlauf, C11 Duo, A10-RK, D13–D15.
Das Verhalten im Browser (Lage, Tippflächen, Falz, Tastatur) ist gemessen (bericht_uiux_bau_u3.md); hier steht, dass die
Stellen im Code hängen und die Server-Seite stimmt. Alle Konten und Inhalte sind Platzhalter, es geht keine Mail hinaus."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_CSS, PCSS = "app/static/css/app.css", "app/static/css/pruefungen.css"
WIKI, MAP, RK, ADM, COMMON = ("app/static/js/wiki.js", "app/static/js/map.js", "app/static/js/pruefungen.js",
                              "app/static/js/admin.js", "app/static/js/common.js")


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


class Umgebung:
    """STROEMIS_NAME für die Dauer eines Blocks setzen (oder entfernen) – danach wie vorher."""

    def __init__(self, wert):
        self.wert, self.alt = wert, os.environ.get("STROEMIS_NAME")

    def __enter__(self):
        if self.wert is None:
            os.environ.pop("STROEMIS_NAME", None)
        else:
            os.environ["STROEMIS_NAME"] = self.wert

    def __exit__(self, *a):
        if self.alt is None:
            os.environ.pop("STROEMIS_NAME", None)
        else:
            os.environ["STROEMIS_NAME"] = self.alt


def _app(tmp):
    os.environ.pop("SMTP_HOST", None)            # nie eine echte Mail
    app = make_app(tmp)
    from app import auth
    auth.send_mail = lambda *a, **k: None
    return app


def _anmelden(c, mail="admin@example.org", pw="geheim123"):
    r = c.post("/api/auth/login", json={"email": mail, "password": pw})
    assert r.status_code == 200, r.get_json()


def _konto(app, adm, mail, name, rechte):
    c = app.test_client()
    c.post("/api/auth/register", json={"email": mail, "password": "passwort1", "name": name, "gliederung": "OG Platzhalter"})
    uid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == mail][0]["id"]
    assert adm.post(f"/api/admin/users/{uid}/approve", json={}).status_code == 200
    assert adm.put(f"/api/admin/users/{uid}", json={"rechte": rechte}).status_code == 200
    _anmelden(c, mail, "passwort1")
    return c, uid


def test_c10_hinweis_entwicklungsserver():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = _app(tmp)
        with Umgebung("stroemis-dev"):
            c = app.test_client()
            # Nicht angemeldet: weder auf der Anmeldeseite noch öffentlich.
            assert 'id="dev-hinweis"' not in c.get("/login").get_data(as_text=True)
            _anmelden(c)
            # Eine API-Antwort holt den Merker nicht ab – erst die erste Seite mit Kopfleiste, egal welches Modul.
            assert c.get("/api/me").status_code == 200
            erste = c.get("/riegenkarten").get_data(as_text=True)
            assert erste.count('id="dev-hinweis"') == 1
            for teil in ('<h2 id="dev-hinweis-titel">Entwicklungsserver</h2>', "Du bist auf dem Entwicklungsserver von strömis.de.",
                         "Daten können sich jederzeit ändern, verschwinden oder neu auftauchen.",
                         "Es kann und wird zu Fehlern und Problemen kommen.",
                         '<a href="mailto:bugs@stroemis.de?subject=str%C3%B6mis.de%20dev%3A%20">bugs@stroemis.de</a>',
                         '<button class="btn" type="button" id="dev-hinweis-ok">Verstanden</button>'):
                assert teil in erste, teil
            # Zweiter Seitenaufruf: nicht mehr.
            for pfad in ("/riegenkarten", "/leitstelle", "/profil"):
                assert 'id="dev-hinweis"' not in c.get(pfad).get_data(as_text=True), pfad
            # Abmelden und wieder anmelden: wieder genau einmal.
            c.post("/api/auth/logout", json={})
            _anmelden(c)
            assert 'id="dev-hinweis"' in c.get("/profil").get_data(as_text=True)
            assert 'id="dev-hinweis"' not in c.get("/profil").get_data(as_text=True)
            # Neues Passwort per Link beginnt ebenfalls eine Sitzung.
            from app import auth, db
            with app.app_context():
                u = db.query("SELECT * FROM users WHERE email = 'admin@example.org'", one=True)
                token = auth.make_reset_token(u)
            c2 = app.test_client()
            assert c2.post("/api/auth/reset", json={"token": token, "password": "geheim1234"}).status_code == 200
            assert 'id="dev-hinweis"' in c2.get("/profil").get_data(as_text=True)
            # Öffentliche Strömipedia ohne Konto: nie.
            assert 'id="dev-hinweis"' not in app.test_client().get("/oeffentlich/").get_data(as_text=True)
        # Ohne „-dev“ (lokal, Produktion): nie – auch nicht direkt nach der Anmeldung.
        for wert in (None, "stroemis", "stroemis-dev-alt"):
            with Umgebung(wert):
                c = app.test_client()
                _anmelden(c, pw="geheim1234")
                assert 'id="dev-hinweis"' not in c.get("/profil").get_data(as_text=True), wert
    # Erstes Konto über die Kontoanfrage (ohne ADMIN_EMAIL): auch dieser Weg beginnt eine Sitzung mit Hinweis.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        alt = {k: os.environ.pop(k, None) for k in ("ADMIN_EMAIL", "ADMIN_PASSWORD")}
        try:
            os.environ.update({"DATA_DIR": tmp, "COOKIE_SECURE": "false", "BASE_URL": "http://localhost"})
            os.environ.pop("SMTP_HOST", None)
            from app import create_app
            app = create_app()
            app.config["TESTING"] = True
            with Umgebung("stroemis-dev"):
                c = app.test_client()
                r = c.post("/api/auth/register", json={"email": "erst@example.org", "password": "passwort1",
                                                       "name": "Erstes Konto", "gliederung": "OG Platzhalter"})
                assert r.status_code == 201 and r.json["pending"] is False, r.get_json()
                assert 'id="dev-hinweis"' in c.get("/profil").get_data(as_text=True)
        finally:
            for k, v in alt.items():
                if v is not None:
                    os.environ[k] = v
    # Statisch: alle Wege, die eine Sitzung beginnen, laufen durch sitzung_beginnen; die Seite öffnet ihn als Dialog.
    a = lies("app/auth.py")
    assert a.count("sitzung_beginnen(") == 4             # Definition + Anmelden, erstes Konto, neues Passwort
    assert 'if module.dev_umgebung():\n        session["dev_hinweis"] = 1' in a
    assert 'return (os.environ.get("STROEMIS_NAME") or "").strip().endswith("-dev")' in lies("app/module.py")
    co = lies(COMMON)
    teil = co[co.index("(function devHinweis() {"):]
    assert "dlg.showModal();\n    dialogVerlauf(dlg);\n    ok.focus();" in teil
    assert "{% if user and dev_hinweis_einmal() %}" in lies("app/templates/base.html")
    print("C10 Hinweis „Entwicklungsserver“ bestanden.")


def test_c1_c5_anmeldung_und_texte():
    css = lies(APP_CSS)
    assert "  .login-form { order: -1; padding: 20px 22px 28px; }" in css
    assert "@media (max-height: 500px) {\n  .login-form { padding-top: 14px;" in css
    login = lies("app/templates/login.html")
    # „Passwort vergessen“: der Spam-Satz steht nur noch in der Antwort; Kontoanfrage: Spam-Satz unter dem Formular.
    vergessen = login[login.index("{% elif mode == 'forgot' %}"):login.index("{% else %}", login.index("{% elif mode == 'forgot' %}"))]
    assert "Spam" not in re.sub(r"\{#.*?#\}", "", vergessen, flags=re.S)
    reg = login[login.index("{% elif mode == 'register' %}"):login.index("{% elif mode == 'forgot' %}")]
    assert reg.index('<form id="f-register">') < reg.index('id="reg-spam"')
    assert 'const spam = document.getElementById("reg-spam");' in lies("app/static/js/auth.js")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = _app(tmp)
        adm = app.test_client()
        _anmelden(adm)
        # Startkonto heißt nach der Rolle (nur Neuanlage).
        assert adm.get("/api/me").json["user"]["name"] == "Plattform-Verwaltung"
        # Leitstelle: Überschrift „Leitstelle“, kein „Nutzerverwaltung“ mehr; Einstellungsgruppe „Ankerplätze“.
        leit = adm.get("/leitstelle").get_data(as_text=True)
        assert "<h1>Leitstelle</h1>" in leit and "Nutzerverwaltung" not in leit.replace("vorher „Nutzerverwaltung“", "")
        gruppen = adm.get("/api/admin/einstellungen").json["gruppen"]
        assert "Ankerplätze" in gruppen and "Karte" not in gruppen, gruppen
        # Probemail nennt die Leitstelle (ohne Mailserver wird nichts verschickt, der Text steht im Code).
        assert "in der Leitstelle von {cfg['SITE_NAME']}" in lies("app/api_admin.py")
        # 403: der Weg führt in den eigenen Bereich.
        matv, _ = _konto(app, adm, "matv@example.org", "Material Platzhalter", {"material": 2, "wiki": 0})
        r = matv.get("/ankerplaetze")
        assert r.status_code == 403 and '<a href="/materialablage">Zur Materialablage</a>' in r.get_data(as_text=True)
        mitglied, _ = _konto(app, adm, "mit@example.org", "Mitglied Platzhalter", {"wiki": 1, "material": 0})
        r = mitglied.get("/leitstelle")
        assert r.status_code == 403 and '<a href="/">Zur Strömipedia</a>' in r.get_data(as_text=True)
        keiner, _ = _konto(app, adm, "keiner@example.org", "Ohne Platzhalter", {"wiki": 0, "material": 0})
        r = keiner.get("/riegenkarten")
        assert r.status_code == 403 and '<a href="/stroemipedia">Zur Strömipedia</a>' in r.get_data(as_text=True)
    for pfad, alt in (("app/material/services/rechte.py", "„Prüfer“ in der Nutzerverwaltung"),
                      ("app/material/services/wikiverweis.py", "(Nutzerverwaltung)."),
                      ("app/material/services/zuruecksetzen.py", "über die Nutzerverwaltung löschen"),
                      (ADM, '"Nutzerverwaltung"')):
        assert alt not in lies(pfad), (pfad, alt)
    pub = lies("app/static/js/public.js")
    assert 'const titel = lesemodus ? "Öffentliche Seiten" : "Öffentliche Strömipedia";' in pub
    assert 'placeholder="Titel, Ort oder Nummer"' in lies(RK)
    print("C1/C5 Anmeldung und Texte bestanden.")


def test_c4_c8_einstellungen_und_info():
    adm, html = lies(ADM), lies("app/templates/admin.html")
    # Gegliedert (zugeklappte Gruppen), Schlüsselnamen nicht mehr vorn, keine .env in der Oberfläche.
    assert '<details class="accordion einst-gruppe" data-gruppe=' in adm and "einst-name" not in adm
    assert "title=\"${S.esc(`${titel} (${f.schluessel})`)}\"" in adm
    assert ".env" not in adm[adm.index("const QUELLE = {"):adm.index("function uebernehmen(d)")]
    assert "form.noValidate = true;" in adm
    assert "Was du hier speicherst, gilt sofort und vor der Grundeinstellung auf dem Server." in html
    assert ".env" not in re.sub(r"\{#.*?#\}", "", html, flags=re.S)
    ein = lies("app/einstellungen.py")
    for alt in ("nicht in der Datei \"\n               \".env", "so verlangt es DMARC", '"STARTTLS verwenden"', '"Karte", '):
        assert alt not in ein, alt
    # Info-Grenzfälle: Datenschutzsatz und ISC-Anleitung sichtbar, kein „i“ mehr.
    wiki = lies(WIKI)
    assert '<h3 class="abgesetzt">Lesen einschränken</h3>\n      <p class="help">Normalerweise darf jeder Angemeldete' in wiki
    assert 'info("Lesen einschränken"' not in wiki
    rk = lies(RK)
    assert '<p class="help import-isc">Aus dem ISC: unter <strong>Dokumente → Checkliste Voraussetzungen (Excel)</strong>' in rk
    assert 'info("ISC"' not in rk
    css = lies(APP_CSS)
    assert "main.leitstelle #users tr { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); column-gap: 12px; }" in css
    assert "main.leitstelle #users td[data-l]:empty { display: none; }" in css
    print("C4/C8 Einstellungen und Info bestanden.")


def test_stroemipedia_c2_c3_c9_c12_d13_d14_d15():
    wiki, css = lies(WIKI), lies(APP_CSS)
    # C2: gewählte Callout-Art als Auswahlzustand, kein roter Knopf; „Neue Seite“ grau bei anderer Hauptaktion.
    assert 'class="btn ${k === kind ? "" : "secondary"}"' not in wiki
    assert '`<button type="button" class="btn secondary" data-k="${k}" aria-pressed="${k === kind}">' in wiki
    assert wiki.count("calloutWahl(") == 2 and wiki.count("calloutWahlBinden(") == 2
    assert '.callout-art .btn[aria-pressed="true"]::before { content: "✓"; }' in css
    assert 'neueSeiteKnopf.classList.toggle("secondary",\n    document.body.classList.contains("editing") || !!content.querySelector("#h-new"));' in wiki
    # C3: Seitensymbol mit Namen, außerhalb der Überschrift.
    assert ('<div class="seitentitel-zeile"><button class="page-icon" id="pg-icon" type="button" title="Symbol der Seite ändern"\n'
            '        aria-label="Symbol der Seite ändern">') in wiki
    assert '<h1 class="seitentitel"><button' not in wiki
    # C9: Kommentarmarken per Tastatur.
    teil = wiki[wiki.index("const zumKommentar = (m, fokus) => {"):wiki.index("function findText(")]
    assert "m.tabIndex = 0;" in teil and 'm.setAttribute("role", "button");' in teil and "`Kommentar zu „" in teil
    assert 'if (e.key !== "Enter" && e.key !== " ") return;' in teil and "el.focus({ preventScroll: true });" in teil
    # C12: Baumknöpfe mit Bezug und aria-expanded; Schreibfläche der neuen Seite.
    assert '`aria-label="${esc(p.title)} ${collapsed ? "aufklappen" : "zuklappen"}" aria-expanded="${!collapsed}"`' in wiki
    assert 'aria-label="Unterseite zu ${esc(p.title)} anlegen"' in wiki and 'aria-label="Weitere Aktionen zu ${esc(p.title)}"' in wiki
    assert 'aria-label="Auf- oder zuklappen"' not in wiki
    assert "st.doc.childCount !== 1 || !st.schema.nodes.paragraph" in wiki
    assert ".ProseMirror:not(:has(> :not(h1:first-child, .autorzeile)))::after {" in css
    # D13: Schublade unter 1024 px (keine 800/801-Schwelle mehr).
    assert "@media (max-width: 1023px) {\n  /* minmax(0, 1fr) statt 1fr" in css
    assert "800px" not in css and "801px" not in css
    # D14: „öffentlich“ ohne Emoji.  D15: Emoji-Raster der Callout-Dialoge erst auf Wunsch.
    assert '>öffentlich</span>' in wiki and "🌐 öffentlich</span>" not in wiki
    assert wiki.count("{ spaeter: true }") == 2 and "Emoji-Auswahl zeigen" in wiki
    lese = lies("app/static/js/public.js")
    assert '<div class="wiki-head"><nav class="krumen" aria-label="Pfad"><span class="krume" aria-current="page">${titel}</span>' not in lese
    print("Strömipedia bestanden.")


def test_ankerplaetze_c2_c3_c7_c9():
    m, css, idx = lies(MAP), lies(APP_CSS), lies("app/templates/index.html")
    assert "yellow" not in m and ".btn.yellow" not in css
    assert 'a.setAttribute("aria-label", "Meinen Standort anzeigen");' in m
    assert 'id="a-delete"' not in m and '<button class="btn secondary dlg-neben" id="al-del" type="button">Album löschen</button>' in m
    assert "async function albumLoeschen(a, dlg) {" in m
    teil = m[m.index("const view = `"):m.index("const form = `")]
    assert "S.menue({" in teil and 'attrs: \'id="lb-del"\'' in teil and "lb-aktionen-weg" not in teil
    assert idx.index('<div class="map-tools">') < idx.index('<div id="map"></div>')
    print("Ankerplätze bestanden.")


def test_riegenkarten_a10_c6_c7_c11_d13_d14_d15():
    rk, pcss, css = lies(RK), lies(PCSS), lies(APP_CSS)
    assert ".pruef { max-width: 1600px; }\n.pruef.druck { max-width: none; }" in pcss
    assert ".pruef[data-ansicht=liste], .pruef[data-ansicht=kataloge], .pruef[data-ansicht=katalog] { max-width: 1280px; }" in pcss
    # C6: Reiterwechsel ersetzt den Verlaufseintrag.
    assert 'history.replaceState(history.state, "", "#" + tab.dataset.reiter);' in rk
    assert 'location.hash = "#" + tab.dataset.reiter' not in rk
    # C7: Katalogdetail „Bearbeiten“/„Löschen“ im Menü wie die Liste.
    teil = rk[rk.index("function renderKatalogSeite() {"):rk.index("function katalogLeistungDialog(")]
    assert 'S.menue({ art: "zeilenmenue", klein: false, eintraege: [' in teil and 'class="btn secondary small" data-act="kat-del"' not in teil
    # D15: Kopfknöpfe des Lehrgangs normal groß.
    assert 'class="btn secondary small" data-act="lg-edit"' not in rk and 'class="btn secondary" data-act="lg-edit"' in rk
    # D14: Knöpfe mit Wort, Marken ohne ⏱/📋, kein Emoji in Toast und „i“.
    assert "⏱" not in rk and "📋" not in rk
    assert '<span class="sym" aria-hidden="true">${sym}</span> ${wort}</button>' in rk
    assert 'knopf("nicht_bestanden", "👎", "nicht bestanden", "nein")' in rk
    assert 'toast("Bitte „bestanden“ oder „mangelhaft“ wählen.", true)' in rk
    assert "`🔒 eingefroren" not in rk
    # D13: Listen nach der Inhaltsbreite; C11: Duo – Inhalt in der rechten Hälfte.
    assert "main.leitstelle, main.pruef { container: liste / inline-size; }" in css
    assert "@container liste (max-width: 820px) {" in css and "@container liste (max-width: 720px) {" in pcss
    duo = css[css.index("/* C11: Doppelbildschirm"):]
    assert "main.page.breit.leitstelle, main.pruef[data-ansicht], main.page.profil-seite {" in duo
    assert "max-width: env(viewport-segment-width 1 0); margin-left: env(viewport-segment-left 1 0);" in duo
    print("Riegenkarten bestanden.")


if __name__ == "__main__":
    test_c10_hinweis_entwicklungsserver()
    test_c1_c5_anmeldung_und_texte()
    test_c4_c8_einstellungen_und_info()
    test_stroemipedia_c2_c3_c9_c12_d13_d14_d15()
    test_ankerplaetze_c2_c3_c7_c9()
    test_riegenkarten_a10_c6_c7_c11_d13_d14_d15()
