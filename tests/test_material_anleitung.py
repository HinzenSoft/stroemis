"""Verweise auf die Anleitung in der Strömipedia (Wunsch vom 28.10.2026):  python tests/test_material_anleitung.py  oder
pytest …

Entscheidung des Nutzers „Nur wer lesen darf“: Links, Willkommen und Hinweis nur für Konten, die die Zielseite in der
Strömipedia lesen dürfen (mit deren Regeln). Gefunden wird über den Titel im Teilbaum unter „Materialablage“, der Anker
nur, wenn es die Überschrift gibt. Seiteninhalte sind Platzhalter; die Titel sind die des Artikels (THEMEN)."""
import html
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, neues_konto, umgebung  # noqa: E402
from test_module_uiux_u3 import Umgebung  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json(silent=True))
    return r.get_json()


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def verweise(c, pfad="/materialablage/pruefungen"):
    """Die Adressen, die die Seite dem Browser mitgibt (data-anleitung am <main>)."""
    seite = c.get(pfad)
    assert seite.status_code == 200, (pfad, seite.status_code)
    m = re.search(r'data-anleitung="([^"]*)"', seite.get_data(as_text=True))
    assert m, pfad
    return json.loads(html.unescape(m.group(1)))


def artikel(adm):
    """Der Teilbaum wie nach dem ZIP-Import: „Materialablage“ mit Unterseiten; „Bestand“ ohne die Überschrift
    „Artikelliste des Ordners“, „Rechtesystem“ lesebeschränkt, „Katalog“ fehlt. Dazu ein gleichnamiger Einzelartikel
    ohne Unterseiten, der nicht gemeint ist."""
    def seite(titel, inhalt, eltern=None):
        d = {"title": titel, "content": inhalt}
        if eltern:
            d["parent_id"] = eltern
        return ok(adm.post("/api/wiki/pages", json=d), 201)["page"]
    einzel = seite("Materialablage", "# Materialablage\n\nPlatzhalter ohne Unterseiten\n")
    wurzel = seite("Materialablage", "# Materialablage\n\nPlatzhalter\n")
    p = {"wurzel": wurzel, "einzel": einzel,
         "pruefung": seite("Prüfung", "# Prüfung\n\n## Prüfung starten\n\nPlatzhalter\n\n```\n## Speichern und Reservierung\n```\n",
                           wurzel["id"]),
         "bestand": seite("Bestand", "# Bestand\n\n## Nummern\n\nPlatzhalter\n", wurzel["id"]),
         "rechte": seite("Rechtesystem", "# Rechtesystem\n\n## Freigaben je Ordner\n", wurzel["id"])}
    p["import"] = seite("Bestandsimport", "# Bestandsimport\n\n## Wie Werte gelesen werden\n", p["bestand"]["id"])
    ok(adm.put(f"/api/wiki/pages/{p['rechte']['id']}/restrict", json={"read_restricted": True}))
    return p


# --- Kennungen der Überschriften ---------------------------------------------------------------------------------------

def test_kennungen_wie_buildtoc():
    from app.material.services.anleitung import kennungen
    k = kennungen("# Titel\n\n## Seite „Echtheit prüfen“\n\n### Größe & Maß\n\n## Status\n\n## Status\n\n"
                  "## [Verlinkt](/x) und **fett**\n\n## Bild ![alt](/b.png) davor\n\n## Toc\n\n## snake_case _kursiv_\n\n"
                  "```\n## Im Code\n```\n\n~~~\n## Auch im Code\n~~~\n\n###### Sechs\n\n## Schluss ##\n")
    assert k == {"titel", "seite-echtheit-pruefen", "groesse-mass", "status", "status-2", "verlinkt-und-fett",
                 "bild-davor", "toc-abschnitt", "snake-case-kursiv", "schluss"}, k
    assert kennungen("") == set()     # Codeblöcke und h6 zählen nicht (buildToc: h1–h5)


def test_themen_stehen_im_artikel():
    """Alle Anker der Tabelle gibt es im Artikel, wenn er neben dem Repository liegt (Arbeitsrechner); sonst nur die
    Form der Tabelle."""
    from app.material.services import anleitung
    for thema, (titel, anker) in anleitung.THEMEN.items():
        assert re.fullmatch(r"[a-z_]+", thema) and titel and (not anker or re.fullmatch(r"[a-z0-9-]+", anker)), thema
    quelle = "/home/harness/wiki-material/artikel"
    if not os.path.isdir(quelle):
        return
    seiten = {}
    for ordner, _, dateien in os.walk(quelle):
        for d in dateien:
            if d.endswith(".md"):
                with open(os.path.join(ordner, d), encoding="utf-8") as fh:
                    text = fh.read()
                seiten[text.splitlines()[0].lstrip("# ").strip()] = anleitung.kennungen(text)
    for thema, (titel, anker) in anleitung.THEMEN.items():
        assert titel in seiten, (thema, titel)
        assert not anker or anker in seiten[titel], (thema, titel, anker)


# --- Auflösung mit den Rechten der Strömipedia -------------------------------------------------------------------------

def test_aufloesung_mit_und_ohne_leserecht():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        leser, _ = neues_konto(app, "leser@example.org", "lesen", rechte={"material": 1, "wiki": 1})
        ohne, _ = neues_konto(app, "ohne@example.org", "lesen", rechte={"material": 1, "wiki": 0})
        # Ohne Artikel: nichts – kein Link, keine Meldung.
        assert verweise(leser) == {} and verweise(adm) == {}
        p = artikel(adm)
        v = verweise(leser)
        slug = {n: s["slug"] for n, s in p.items()}
        assert v["uebersicht"] == f"/stroemipedia/{slug['wurzel']}"          # die Wurzel mit Unterseiten
        assert v["pruefungen"] == f"/stroemipedia/{slug['pruefung']}"
        assert v["pruefung_neu"] == f"/stroemipedia/{slug['pruefung']}#pruefung-starten"
        # Die Überschrift steht nur im Codeblock: kein Anker, Link an den Anfang der Seite.
        assert v["offene_pruefungen"] == f"/stroemipedia/{slug['pruefung']}"
        assert v["ordner"] == f"/stroemipedia/{slug['bestand']}"              # Anker fehlt im Artikel
        assert v["nummern"] == f"/stroemipedia/{slug['bestand']}#nummern"
        assert v["import_spalten"] == f"/stroemipedia/{slug['import']}#wie-werte-gelesen-werden"   # zwei Ebenen tief
        assert "katalog" not in v and "produkt" not in v                        # Seite fehlt
        assert "freigaben" not in v                                             # lesebeschränkt
        assert "Rechtesystem" not in json.dumps(v, ensure_ascii=False)
        assert verweise(adm)["freigaben"] == f"/stroemipedia/{slug['rechte']}#freigaben-je-ordner"   # Wiki-Verwaltung
        # Ohne Stufe in der Strömipedia (Lesemodus): nur Öffentliches – erst nichts, dann der freigegebene Abschnitt.
        assert verweise(ohne) == {}
        ok(adm.put(f"/api/wiki/pages/{p['pruefung']['id']}/share", json={"is_public": True, "public_children": False}))
        v2 = verweise(ohne)
        assert v2["pruefung_neu"].endswith("#pruefung-starten") and "uebersicht" not in v2 and "ordner" not in v2
        ok(adm.put(f"/api/wiki/pages/{p['rechte']['id']}/restrict", json={"read_restricted": False}))
        ok(adm.put(f"/api/wiki/pages/{p['wurzel']['id']}/share", json={"is_public": True, "public_children": True}))
        v2 = verweise(ohne)
        assert v2["uebersicht"] and v2["ordner"] and v2["freigaben"] and "katalog" not in v2
        # Auf jeder Seite der Materialablage dasselbe, auch auf „Meine PSA“.
        v = verweise(leser)
        for pfad in ("/materialablage", "/materialablage/bestand", "/materialablage/katalog", "/materialablage/meine-psa"):
            assert verweise(leser, pfad) == v, pfad
        # Wurzel im Papierkorb: keine Links mehr (der Einzelartikel ohne Unterseiten zählt nur, wenn es keine andere gibt).
        ok(adm.delete(f"/api/wiki/pages/{p['wurzel']['id']}", headers=H))
        assert set(verweise(leser)) <= {"uebersicht"}
        assert verweise(leser).get("uebersicht", f"/stroemipedia/{slug['einzel']}") == f"/stroemipedia/{slug['einzel']}"


def test_echtheit_pruefen_nur_mit_leserecht():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        p = artikel(adm)
        nachweise = ok(adm.post("/api/wiki/pages", json={"title": "Nachweise und Protokolle", "parent_id": p["wurzel"]["id"],
                                                          "content": "# Nachweise\n\n## Seite „Echtheit prüfen“\n"}), 201)["page"]
        link = f'href="/stroemipedia/{nachweise["slug"]}#seite-echtheit-pruefen"'
        assert link in adm.get("/materialablage/pruefen").get_data(as_text=True)
        assert "Mehr dazu in der Strömipedia" not in app.test_client().get("/materialablage/pruefen").get_data(as_text=True)
        ohne, _ = neues_konto(app, "ohne@example.org", "lesen", rechte={"material": 1, "wiki": 0})
        assert "Mehr dazu in der Strömipedia" not in ohne.get("/materialablage/pruefen").get_data(as_text=True)


# --- Willkommen und Hinweis ----------------------------------------------------------------------------------------------

def willkommen(c):
    return c.get("/materialablage").get_data(as_text=True).count('id="mat-willkommen"')


def test_willkommen_genau_einmal_je_konto():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        leser, leser_id = neues_konto(app, "leser@example.org", "lesen", rechte={"material": 1, "wiki": 1})
        ohne, ohne_id = neues_konto(app, "ohne@example.org", "lesen", rechte={"material": 1, "wiki": 0})
        # Ohne Artikel: kein Willkommen – und nichts gemerkt.
        assert willkommen(leser) == 0
        p = artikel(adm)
        seite = leser.get("/materialablage").get_data(as_text=True)
        assert seite.count('id="mat-willkommen"') == 1
        for teil in ('<h2 id="mat-willkommen-titel">Willkommen in der Materialablage</h2>',
                     f'<a class="btn" id="mat-willkommen-los" href="/stroemipedia/{p["wurzel"]["slug"]}" target="_blank" '
                     'rel="noopener">Zur Anleitung</a>',
                     '<button class="btn secondary" type="button" id="mat-willkommen-spaeter">Später</button>'):
            assert teil in seite, teil
        # Danach nie wieder – auch nicht in einer neuen Sitzung; andere Seiten zeigen es nie.
        assert willkommen(leser) == 0
        assert 'id="mat-willkommen"' not in leser.get("/materialablage/pruefungen").get_data(as_text=True)
        leser.post("/api/auth/logout", json={})
        assert leser.post("/api/auth/login", json={"email": "leser@example.org", "password": "passwort1"}).status_code == 200
        assert willkommen(leser) == 0
        # Der Hinweis bleibt (dauerhaft): Die Übersicht bekommt die Adresse bei jedem Besuch.
        for _ in range(3):
            assert verweise(leser, "/materialablage")["uebersicht"] == f"/stroemipedia/{p['wurzel']['slug']}"
        # Ohne Leserecht: kein Willkommen, kein Merker – sobald das Konto lesen darf, kommt es einmal.
        assert willkommen(ohne) == 0 and willkommen(ohne) == 0
        from app import db
        with app.app_context():
            assert not db.query("SELECT 1 FROM mat_meta WHERE schluessel = ?", (f"willkommen:{ohne_id}",), one=True)
            assert db.query("SELECT 1 FROM mat_meta WHERE schluessel = ?", (f"willkommen:{leser_id}",), one=True)
        ok(adm.put(f"/api/admin/users/{ohne_id}", json={"rechte": {"material": 1, "wiki": 1}}))
        assert willkommen(ohne) == 1 and willkommen(ohne) == 0
        # Konto gelöscht: der Merker geht mit.
        ok(adm.delete(f"/api/admin/users/{leser_id}", headers=H))
        with app.app_context():
            assert not db.query("SELECT 1 FROM mat_meta WHERE schluessel = ?", (f"willkommen:{leser_id}",), one=True)


def test_willkommen_nach_dem_hinweis_entwicklungsserver():
    """Erste Anmeldung auf dev, erste Seite = Übersicht: beide Dialoge im HTML, material.js öffnet das Willkommen erst
    nach dem Schließen des dev-Hinweises (nie zwei übereinander)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        with Umgebung("stroemis-dev"):
            app, k = umgebung(tmp)
            adm = k["adm"]
            artikel(adm)
            leser, _ = neues_konto(app, "leser@example.org", "lesen", rechte={"material": 1, "wiki": 1})
            leser.post("/api/auth/logout", json={})
            assert leser.post("/api/auth/login", json={"email": "leser@example.org", "password": "passwort1"}).status_code == 200
            seite = leser.get("/materialablage").get_data(as_text=True)
            assert seite.count('id="dev-hinweis"') == 1 and seite.count('id="mat-willkommen"') == 1
    js = lesen("app/material/static/material.js")
    teil = js[js.index("(function willkommen() {"):js.index("})();", js.index("(function willkommen() {"))]
    assert 'const dev = document.getElementById("dev-hinweis");' in teil
    assert 'if (dev && dev.open) dev.addEventListener("close", zeigen, { once: true });' in teil
    assert "S.dialogVerlauf(dlg);" in teil and "los.focus();" in teil


def test_hinweis_und_links_in_der_oberflaeche():
    js = lesen("app/material/static/material.js")
    hinweis = js[js.index("function anleitungHinweis() {"):js.index("(function willkommen() {")]
    assert "Anleitung in der Strömipedia öffnen" in hinweis and 'class="btn secondary"' in hinweis
    assert "schliessen" not in hinweis.lower() and "data-act" not in hinweis          # nicht ausblendbar
    assert "${anleitungHinweis()}" in js
    # Kopf-Links und Infos fragen nur nach Themen, die es in der Tabelle gibt.
    from app.material.services.anleitung import THEMEN
    benutzt = set(re.findall(r'(?:mehrDazu|anleitungKopf|anleitungUrl)\("([a-z_]+)"\)', js))
    benutzt |= set(re.findall(r'mehrDazu\("([a-z_]+)"\)', lesen("app/material/static/freigaben.js")))
    benutzt |= {"ordner_system", "ordner", "uebersicht", "echtheit"}
    assert benutzt <= set(THEMEN), benutzt - set(THEMEN)
    assert set(THEMEN) <= benutzt, set(THEMEN) - benutzt
    css = lesen("app/material/static/material.css")
    regel = css[css.index(".notice.mat-anleitung-hinweis {"):css.index("}", css.index(".notice.mat-anleitung-hinweis {"))]
    assert "var(--wasser)" in regel and "--rot" not in regel


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            print("ok", name)
