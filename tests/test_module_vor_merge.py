"""Nachbesserung vor dem Merge, Teil B – Strömipedia, Leitstelle, Riegenkarten, Anmeldung (26.10.2026):
python tests/test_module_vor_merge.py  oder  pytest tests/test_module_vor_merge.py

  F1  Rechte-Felder im Nutzerdialog breit genug für „Verwaltung“ (Raster mit Mindestbreite statt fünf Spalten).
  N1  Ein Klick auf einen Link im Text legt einen Verlaufseintrag an (wireLinks verdrahtet jeden Link einmal).
  N3  Esc schließt „Prüfungsleistung anlegen/bearbeiten“ auch aus dem Beschreibungs-Editor; Fokus auf „Bezeichnung“;
      lange Dialoge („Nutzer bearbeiten“) setzen den Fokus aufs erste Feld statt auf den rollenden Dialogkörper.
  N4  Emoji-Raster ist ein Tab-Stopp mit Pfeiltasten (Roving Tabindex).
  N5  Meldungen nennen die Wiki-Verwaltung, die Verwaltung der Riegenkarten bzw. die Plattform-Verwaltung statt
      „Redakteur“/„Administrator“/„Administration“; .env.example nennt die Leitstelle.
  N6  Schrägstrich am Ende der Startseiten (Weiterleitung: test_umbenennung), Seitentitel der Anmeldeseiten,
      „Seite nicht gefunden“ nur einmal, Kommentar-Aktionen brechen um.
Export → Import gleichnamiger Geschwister: test_wiki_import.test_rundweg_gleichnamige_geschwister.

Die Browserproben stehen im Bericht (Chromium, Firefox, WebKit); hier die Server-Seite und die Stellen im Code, an
denen die Lösungen hängen. Alle Namen und Seiten sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import H, make_app  # noqa: E402
from test_wiki_lesemodus import konto  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _anmelden(app):
    adm = app.test_client()
    assert adm.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
    return adm


def test_titel_der_anmeldeseiten():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = app.test_client()
        for pfad, titel in (("/login", "Anmelden"), ("/register", "Konto anfragen"),
                            ("/forgot", "Passwort vergessen"), ("/reset", "Neues Passwort setzen")):
            r = c.get(pfad)
            assert r.status_code == 200, (pfad, r.status_code)
            assert f"<title>{titel} – strömis.de</title>" in r.text, (pfad, re.findall(r"<title>.*?</title>", r.text))
        # Kontoanfrage: Hilfe und Rückmeldung nennen die Plattform-Verwaltung.
        r = c.get("/register")
        assert "Die Plattform-Verwaltung prüft deine Anfrage" in r.text and "Administrator" not in r.text
        r = c.post("/api/auth/register", json={"email": "neu@example.org", "password": "passwort1",
                                               "name": "Neu Platzhalter", "gliederung": "OG Platzhalter"})
        assert r.status_code == 201 and "an die Plattform-Verwaltung geschickt" in r.json["message"], r.json
        r = c.post("/api/auth/login", json={"email": "neu@example.org", "password": "passwort1"})
        assert r.status_code == 403 and r.json["error"] == ("Deine Kontoanfrage wartet noch auf die Freigabe durch die "
                                                           "Plattform-Verwaltung."), r.json
        # Kontoanfragen aus: die Seite und der Endpunkt sagen, an wen man sich wendet.
        adm = _anmelden(app)
        r = adm.put("/api/admin/einstellungen", json={"werte": {"ALLOW_REGISTRATION": False}})
        assert r.status_code == 200, r.json
        assert "Die Plattform-Verwaltung kann dein Konto anlegen." in c.get("/register").text
        r = c.post("/api/auth/register", json={"email": "neu2@example.org", "password": "passwort1", "name": "N",
                                               "gliederung": "OG"})
        assert r.status_code == 403 and r.json["error"] == ("Kontoanfragen sind deaktiviert. Bitte wende dich an die "
                                                           "Plattform-Verwaltung."), r.json
    print("Titel der Anmeldeseiten bestanden.")


def test_rollennamen_in_meldungen():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        adm = _anmelden(app)
        mitglied, _ = konto(app, adm, "mitglied@example.org", "Mitglied Platzhalter", {"wiki": 1, "pruefungen": 1})
        p = adm.post("/api/wiki/pages", json={"title": "Platzhalter", "content": "# Platzhalter\n"}).json["page"]
        r = mitglied.put(f"/api/wiki/pages/{p['id']}/share", json={"is_public": True})
        assert r.status_code == 403 and r.json["error"] == "Veröffentlichen darf nur die Wiki-Verwaltung.", r.json
        r = mitglied.delete(f"/api/wiki/pages/{p['id']}", headers=H)
        assert r.status_code == 403 and r.json["error"] == ("Nur der Ersteller oder die Wiki-Verwaltung kann diese "
                                                           "Seite löschen."), r.json
        r = mitglied.post("/api/pruefungen/kataloge", json={"titel": "Platzhalter"})
        assert r.status_code == 403 and r.json["error"] == "Kataloge pflegt nur die Verwaltung der Riegenkarten.", r.json
    # Keine sichtbare Meldung nennt noch die alten Rollen (Kommentare und Docstrings dürfen die Geschichte erzählen).
    alt = re.compile(r"Redakteur|Administrator|Administration|\bAdmin\b")
    for pfad in ("app/api_wiki.py", "app/api_pruefungen.py", "app/auth.py", "app/einstellungen.py"):
        for zeile in lies(pfad).splitlines():
            code = zeile.split("#", 1)[0]
            if re.search(r"(error=|Abgelehnt\(|hilfe=|_MSG|NUR_LEITUNG|^\s*\")", code) and alt.search(code):
                if '"""' not in code and "logger" not in code:
                    raise AssertionError(f"{pfad}: {zeile.strip()}")
    for pfad, alt_text in (("app/static/js/wiki.js", "die Administration und die oben"),
                           ("app/static/js/wiki.js", "nur Ersteller oder Admin<"),
                           ("app/static/js/pruefungen.js", "Die Administration legt sie an."),
                           ("app/templates/login.html", "Administrator")):
        assert alt_text not in lies(pfad), (pfad, alt_text)
    env = lies(".env.example")
    assert "Verwaltung → Einstellungen" not in env and env.count("Leitstelle → Einstellungen") == 2
    print("Rollennamen in Meldungen bestanden.")


def test_oberflaeche_statisch():
    css = lies("app/static/css/app.css")
    # F1: Raster mit Mindestbreite statt fünf Spalten von je rund 95 px.
    assert "grid-template-columns: repeat(auto-fill, minmax(min(100%, 8.5em), 1fr))" in css
    assert ".rechte-reihe { display: grid; grid-template-columns: repeat(5, 1fr)" not in css
    # N6: Kommentar-Aktionen brechen um.
    assert ".c-actions { display: flex; flex-wrap: wrap;" in css
    wiki = lies("app/static/js/wiki.js")
    # N1: jeder Link einmal verdrahtet.
    w = wiki[wiki.index("function wireLinks(root)"):]
    w = w[:w.index("\n  }\n")]
    assert "if (verdrahtet.has(a)) return;" in w and "verdrahtet.add(a);" in w
    assert "const verdrahtet = new WeakSet();" in wiki
    # N4: Emoji-Raster – ein Tab-Stopp, Pfeiltasten, Pos1/Ende.
    e = wiki[wiki.index("const emojiPicker = (body, initial) => {"):wiki.index("/* Bild wählen und hochladen")]
    assert 'tabindex="${i ? -1 : 0}"' in e and "ArrowDown: spalten()" in e and 'e.key === "Home"' in e
    assert 'grid.setAttribute("role", "group")' in e
    # N6: „Seite nicht gefunden“ nur einmal.
    s = wiki[wiki.index("async function show(slug)"):]
    s = s[:s.index("state.current = d.page;")]
    assert 'e.status === 404 ? "Diese Seite gibt es nicht (mehr)' in s
    # N3: Editor nimmt sich den Fokus nicht, Esc aus dem Editor schließt, Fokus auf „Bezeichnung“ auch beim Bearbeiten.
    pr = lies("app/static/js/pruefungen.js")
    m = pr[pr.index("function mdEditorEinrichten("):pr.index("function kriterienEntwurfEinrichten(")]
    assert "autofocus: false," in m
    assert 'e.key === "Escape" && e.defaultPrevented && dlg.open' in m and "dlg.close()" in m
    assert 'fokus($("#pl-bez", body));' in pr and 'fokus($("#kl-bez", body));' in pr
    assert 'if (neu) fokus($("#pl-bez"' not in pr
    # N3: Fokus nicht auf dem rollenden Dialogkörper.
    co = lies("app/static/js/common.js")
    d = co[co.index("function dialog(html, onOpen)"):co.index("function confirm(")]
    assert d.index("dlg.showModal()") < d.index("document.activeElement === body") < d.index("onOpen(dlg, body)")
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_titel_der_anmeldeseiten()
    test_rollennamen_in_meldungen()
    test_oberflaeche_statisch()
