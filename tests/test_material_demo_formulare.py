"""DEMO-Skript: Platzhalter-Formulare für echte Kategorien (Wunsch des Nutzers vom 25.10.2026).

scripts/material_demo.py --demo legt zum Schluss an jeder echten Kategorie ohne wirksames aktives Formular ein
DEMO-Platzhalter-Formular an – so hoch im Baum wie möglich, mit DEMO-Kennzeichen, aktiviert, nur auf dev/localhost.
Geprüft: der DEMO-Bestand bleibt genau wie ohne den Schritt (Artikel, Prüfungen, Durchgänge, der Helm „neu“ und ohne
Formular), echte Formulare (aktiv wie inaktiv) bleiben unberührt, ein Artikel eines echten Produkts lässt sich prüfen,
der Katalog-Export enthält keines der Platzhalter-Formulare, ein zweiter Lauf legt nichts an, die Sperre über BASE_URL.
Alle Kategorien, Produkte und Prüfpunkte hier sind Platzhalter.
"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import make_app  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = "https://dev.strömis.de"
TITEL = "DEMO-Prüfformular (Platzhalter) – "


def _punkt(text):
    return {"gruppe": "", "text": text, "art": "yesno", "soll": "ja"}


# Ein kleiner „echter“ Katalog (ohne Kennzeichen demo) – nur Platzhalter. A: ohne Formular, A1 mit Artikellänge;
# B: mit aktivem echtem Formular; C: nur mit inaktivem echtem Formular, darunter C1.
KATALOG = {
    "format": "stroemis-material-katalog", "version": 1,
    "kategorien": [
        {"name": "Test-Kategorie A", "unterkategorien": [
            {"name": "Test-Kategorie A1", "materialart": "sonstiges", "intervall_monate": 12, "artikel_laenge": True},
            {"name": "Test-Kategorie A2", "materialart": "sonstiges", "intervall_monate": 12}]},
        {"name": "Test-Kategorie B", "unterkategorien": [
            {"name": "Test-Kategorie B1", "materialart": "sonstiges", "intervall_monate": 12}]},
        {"name": "Test-Kategorie C", "unterkategorien": [
            {"name": "Test-Kategorie C1", "materialart": "sonstiges", "intervall_monate": 12}]},
    ],
    "produkte": [
        {"kategorie": ["Test-Kategorie A", "Test-Kategorie A1"], "hersteller": "Test-Hersteller", "modell": "Test-Seil",
         "artikelnummer": "T-1", "materialart": "sonstiges", "beschreibung": ""},
    ],
    "formulare": [
        {"kategorie": ["Test-Kategorie B"], "titel": "Test-Formular B", "punkte": [_punkt("Test-Punkt B")]},
        {"kategorie": ["Test-Kategorie C"], "titel": "Test-Formular C", "aktivieren": False,
         "punkte": [_punkt("Test-Punkt C")]},
    ],
}


def demo_laufen(adresse):
    """Das Skript wie von der Kommandozeile mit BASE_URL adresse – die Ausgabe."""
    spec = importlib.util.spec_from_file_location("material_demo_formulare", os.path.join(REPO, "scripts",
                                                                                          "material_demo.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    puffer, argv, alt = io.StringIO(), sys.argv, os.environ.get("BASE_URL")
    sys.argv, os.environ["BASE_URL"] = ["material_demo.py", "--demo"], adresse
    try:
        with contextlib.redirect_stdout(puffer):
            modul.main()
    finally:
        sys.argv, os.environ["BASE_URL"] = argv, alt
    return puffer.getvalue()


def aufbauen(tmp):
    app = make_app(tmp)
    with app.app_context():
        from app.material.services import importer
        bericht = importer.importieren(KATALOG, quelle="Test")
        assert not bericht["fehler"], bericht["fehler"]
    return app


def demo_stand(app):
    """Der DEMO-Bestand ohne Zeitstempel und Kennungen: Artikel, Prüfungen, Durchgänge, DEMO-Formulare an DEMO-Zielen."""
    from app import db
    with app.app_context():
        artikel = [tuple(r.values()) for r in db.query(
            "SELECT p.model, i.serial_no, f.name AS ordner, i.lock_state, i.next_due_on, i.retire_by FROM mat_item i "
            "JOIN mat_product p ON p.id = i.product_id JOIN mat_folder f ON f.id = i.folder_id ORDER BY i.id")]
        pruefungen = [tuple(r.values()) for r in db.query(
            "SELECT p.model, i.serial_no, x.kind, x.result, x.inspected_on, x.form_version, x.locked_at IS NOT NULL "
            "FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id JOIN mat_product p ON p.id = i.product_id "
            "ORDER BY x.id")]
        durchgaenge = db.query("SELECT COUNT(*) AS n FROM mat_round", one=True)["n"]
        formulare = [tuple(r.values()) for r in db.query(
            "SELECT title, version, active FROM mat_form WHERE title NOT LIKE ? ORDER BY id", (TITEL + "%",))]
    return artikel, pruefungen, durchgaenge, formulare


def test_demo_formulare():
    from app import db
    with tempfile.TemporaryDirectory() as ohne, tempfile.TemporaryDirectory() as mit:
        # Gesperrt (BASE_URL der Produktion): kein Platzhalter-Formular, sonst alles wie bisher.
        app_ohne = aufbauen(ohne)
        aus = demo_laufen("https://strömis.de")
        assert "Platzhalter-Formulare: keine angelegt" in aus, aus
        with app_ohne.app_context():
            assert not db.query("SELECT 1 FROM mat_form WHERE title LIKE ?", (TITEL + "%",))

        app = aufbauen(mit)
        aus = demo_laufen(DEV)
        assert "Platzhalter-Formulare: 2 DEMO-Formulare" in aus, aus
        # Der DEMO-Bestand ist genau derselbe wie ohne den Schritt.
        assert demo_stand(app) == demo_stand(app_ohne)
        with app.app_context():
            from flask import g

            from app.material.services import bestand, katalog, katalog_export, pruefung, status
            helm = db.query("SELECT id FROM mat_product WHERE model = 'DEMO Helm'", one=True)["id"]
            assert katalog.formular_fuer_produkt(helm) is None
            helme = db.query("SELECT * FROM mat_item WHERE product_id = ?", (helm,))
            assert helme and all(status.status(i) == "neu" for i in helme), [status.status(i) for i in helme]
            neu = {r["name"]: r for r in db.query(
                "SELECT c.name, f.id, f.active, f.demo, f.version FROM mat_form f JOIN mat_category c ON "
                "c.id = f.category_id WHERE f.title LIKE ?", (TITEL + "%",))}
            # A an der Oberkategorie (reicht für A1 und A2), C1 unter dem inaktiven echten Formular von C; B hat ein echtes.
            assert set(neu) == {"Test-Kategorie A", "Test-Kategorie C1"}, neu
            assert all(f["active"] == 1 and f["demo"] == 1 for f in neu.values())
            arten = [p["editor"] for p in katalog.punkte(neu["Test-Kategorie A"]["id"])]
            assert arten == ["yesno", "text", "number", "laenge"], arten
            assert [p["editor"] for p in katalog.punkte(neu["Test-Kategorie C1"]["id"])] == ["yesno", "text", "number"]
            # Echte Formulare unberührt: B aktiv, C inaktiv.
            echt = {r["title"]: r["active"] for r in db.query("SELECT title, active FROM mat_form WHERE demo = 0")}
            assert echt == {"Test-Formular B": 1, "Test-Formular C": 0}, echt
            # Jede echte Kategorie hat ein wirksames Formular – bis auf C selbst: Dort bleibt das inaktive echte
            # Formular allein (ein aktives DEMO-Formular verdrängte es im Export), das Skript nennt sie.
            assert "Test-Kategorie C (" in aus, aus
            for k in db.query("SELECT id FROM mat_category WHERE demo = 0 AND name <> 'Test-Kategorie C'"):
                assert any(db.query("SELECT 1 FROM mat_form WHERE category_id = ? AND active = 1", (x["id"],))
                           for x in katalog.kategorie_pfad(k["id"])), k

            # Eine Prüfung an einem Artikel eines echten Produkts lässt sich starten.
            g.mat_akteur = "Test"
            gl = bestand.ordner_anlegen({"name": "Test-Gliederung", "kind": "gliederung"})
            seil = db.query("SELECT id FROM mat_product WHERE model = 'Test-Seil'", one=True)["id"]
            iid = bestand.artikel_anlegen({"product_id": seil, "folder_id": gl, "length_m": 50})
            pid, angelegt = pruefung.starten(iid, {"id": None, "name": "Test-Prüfer", "urkunde": "T-1",
                                                   "login": "Test"})
            assert angelegt
            x = db.query("SELECT form_id FROM mat_inspection WHERE id = ?", (pid,), one=True)
            assert x["form_id"] == neu["Test-Kategorie A"]["id"]
            laenge = db.query("SELECT finding, value FROM mat_inspection_result WHERE inspection_id = ? AND "
                              "editor = 'laenge'", (pid,), one=True)
            assert laenge["finding"] == "ok", dict(laenge)

            # Der Katalog-Export enthält keines der Platzhalter-Formulare – die echten (auch das inaktive) schon.
            daten, _, _ = katalog_export.sammeln(mit_dateien=False)
            titel = [f["titel"] for f in daten["formulare"]]
            assert not [t for t in titel if "DEMO" in t], titel
            assert sorted(titel) == ["Test-Formular B", "Test-Formular C"], titel
            anzahl = db.query("SELECT COUNT(*) AS n FROM mat_form", one=True)["n"]

        # Zweiter Lauf: nichts dazu.
        aus = demo_laufen(DEV)
        assert "nichts angelegt" in aus, aus
        with make_app(mit).app_context():
            assert db.query("SELECT COUNT(*) AS n FROM mat_form", one=True)["n"] == anzahl
    print("DEMO-Skript: Platzhalter-Formulare bestanden.")


if __name__ == "__main__":
    test_demo_formulare()
