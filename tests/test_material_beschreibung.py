"""Rauchtest für die Produktbeschreibung als Zusatz hinter dem Namen (Nachbesserung vom 18.10.2026):
python tests/test_material_beschreibung.py  oder  pytest tests/test_material_beschreibung.py

Die Beschreibung eines Produkts ist ein kurzer Zusatz – etwa die Verschlussart – und steht überall als „Modell |
Beschreibung“ vor der Artikelnummer. Über die Oberfläche höchstens 80 Zeichen in einer Zeile: länger ist ein Fehler mit
Klartext, nie eine stille Kürzung, auch nicht für eine ältere Beschreibung. Der Katalogimport (Format 1 und 2, also auch
der Austausch dev → Produktion) übernimmt ältere, längere unverändert. Die Anzeige folgt einer Regel (katalog.zusatz und
katalog.produktname hier, produktZusatz in material.js), die Produktsuche findet auch über die Beschreibung.
Alle Namen, Nummern und Texte hier sind erfunden und nur für den Test da."""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (H, _flach, anmelden, festschreiben, gliederung, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, pdf_seiten, protokoll_zeile, pruef_formulare, starten, umgebung)
from test_material_export import csv_lesen  # noqa: E402
from test_material_katalog import exportieren, importieren  # noqa: E402

# Eine ältere Beschreibung von vor der Grenze: lang und mehrzeilig – ein Platzhalter, kein echter Inhalt.
LANG = ("Platzhalter für eine ältere, lange Beschreibung aus der Zeit vor der Grenze von achtzig Zeichen, mit "
        "mehreren Sätzen.\nZweite Zeile des Platzhalters.")
FELDER = ("category_id", "manufacturer", "model", "article_no", "norm", "material_kind", "interval_months",
          "lifetime_years", "lifetime_source", "description")


def _db(app, sql, args=(), one=True):
    with app.app_context():
        from app import db
        return db.query(sql, args, one=one)


def test_laenge_beim_speichern():
    """Anlegen, Bearbeiten, Variante und Produkt aus einer Meldung: höchstens 80 Zeichen, eine Zeile. Eine ältere,
    lange Beschreibung bleibt bei einer Änderung, die sie nicht nennt; schickt der Dialog sie unverändert mit, ist das
    ein Fehler (der Dialog sagt vorher „Bitte kürzen“) – gespeichert wird nichts davon."""
    from app.material.services import meldung
    alt = (meldung.HINTERGRUND, meldung.send_mail)
    meldung.HINTERGRUND = lambda f, *a: f(*a)
    meldung.send_mail = lambda an, betreff, inhalt: True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k = umgebung(tmp)
            ids = katalog_grund(k["adm"])
            kp = k["katalog"]
            basis = {"category_id": ids["karabiner"], "manufacturer": "Testwerk", "material_kind": "metall_hardware",
                     "interval_months": 12}
            zahl = _db(app, "SELECT COUNT(*) AS n FROM mat_product")["n"]
            r = kp.post("/api/material/produkte", json=dict(basis, model="Karabiner Zeta", article_no="KZ-1",
                                                            description="x" * 81))
            assert r.status_code == 400, r.get_json()
            assert "kurzer Zusatz" in r.json["error"] and "höchstens 80 Zeichen, hier sind es 81" in r.json["error"], r.json
            assert _db(app, "SELECT COUNT(*) AS n FROM mat_product")["n"] == zahl
            # Genau 80 gehen; Zeilenumbrüche und doppelter Leerraum werden zu einem Leerzeichen (das Feld ist einzeilig).
            r = kp.post("/api/material/produkte", json=dict(basis, model="Karabiner Zeta", article_no="KZ-1",
                                                            description="y" * 80))
            assert r.status_code == 201 and r.json["produkt"]["description"] == "y" * 80, r.get_json()
            r = kp.post("/api/material/produkte", json=dict(basis, model="Karabiner Eta", article_no="KE-1",
                                                            description="  Screwlock\n\t Alu  "))
            assert r.status_code == 201 and r.json["produkt"]["description"] == "Screwlock Alu", r.get_json()
            pid = r.json["produkt"]["id"]
            url = f"/api/material/produkte/{pid}"

            # Eine ältere, lange Beschreibung (von vor der Grenze – hier direkt in die Datenbank geschrieben).
            with app.app_context():
                from app import db
                db.execute("UPDATE mat_product SET description = ? WHERE id = ?", (LANG, pid))
            # Eine Änderung, die sie nicht nennt, lässt sie stehen.
            r = kp.put(url, json={"interval_months": 6})
            assert r.status_code == 200 and r.json["produkt"]["description"] == LANG, r.get_json()
            # Der Dialog schickt alle Felder – mit der unveränderten alten Beschreibung ist das ein Fehler, nichts
            # geändert (auch das Intervall nicht).
            p = kp.get(url).json["produkt"]
            dialog = {f: p[f] for f in FELDER}
            dialog["interval_months"] = 3
            r = kp.put(url, json=dialog)
            assert r.status_code == 400 and f"hier sind es {len(' '.join(LANG.split()))}" in r.json["error"], r.get_json()
            p = kp.get(url).json["produkt"]
            assert p["description"] == LANG and p["interval_months"] == 6, p
            # Gekürzt geht es.
            dialog["description"] = "Screwlock"
            r = kp.put(url, json=dialog)
            assert r.status_code == 200, r.get_json()
            assert r.json["produkt"]["description"] == "Screwlock" and r.json["produkt"]["interval_months"] == 3

            # Variante: dieselbe Grenze.
            r = kp.post(f"{url}/variante", json=dict(dialog, article_no="KE-2", description="z" * 81))
            assert r.status_code == 400 and "höchstens 80" in r.json["error"], r.get_json()
            r = kp.post(f"{url}/variante", json=dict(dialog, article_no="KE-2", description="Twistlock"))
            assert r.status_code == 201 and r.json["produkt"]["description"] == "Twistlock", r.get_json()

            # Produkt aus einer Meldung: ebenso – die Meldung bleibt offen, bis es klappt.
            gliederung(k["wart"])            # melden darf, wer irgendwo verwaltet
            r = k["wart"].post("/api/material/meldungen", json={"manufacturer": "Meldewerk", "model": "Karabiner Theta"},
                               headers=H)
            assert r.status_code == 201, r.get_json()
            mid = r.json["meldung"]["id"]
            d = dict(basis, manufacturer="Meldewerk", model="Karabiner Theta", description="w" * 81)
            r = kp.post(f"/api/material/meldungen/{mid}/produkt", json=d)
            assert r.status_code == 400 and "höchstens 80" in r.json["error"], r.get_json()
            assert kp.get(f"/api/material/meldungen/{mid}").json["meldung"]["status"] == "offen"
            d["description"] = "Ball-Lock"
            r = kp.post(f"/api/material/meldungen/{mid}/produkt", json=d)
            assert r.status_code == 201 and r.json["produkt"]["description"] == "Ball-Lock", r.get_json()
    finally:
        meldung.HINTERGRUND, meldung.send_mail = alt
    print("Länge beim Speichern bestanden.")


def test_import_lange_beschreibung():
    """Der Katalogimport scheitert nicht an einer langen, mehrzeiligen Beschreibung: Er übernimmt sie unverändert und
    sagt es im Bericht (ein Hinweis, kein Fehler); ein zweiter Lauf ändert nichts und meldet nichts. Der Austausch
    dev → Produktion (Katalog-Export als ZIP, Probelauf und Import in eine zweite Instanz) trägt sie ebenso unverändert."""
    katalog = {"format": "stroemis-material-katalog", "version": 1,
               "kategorien": [{"name": "Testkategorie", "materialart": "metall_hardware", "intervall_monate": 12}],
               "produkte": [{"kategorie": ["Testkategorie"], "hersteller": "Testwerk", "modell": "Karabiner Lang",
                             "artikelnummer": "KL-1", "materialart": "metall_hardware", "beschreibung": LANG},
                            {"kategorie": ["Testkategorie"], "hersteller": "Testwerk", "modell": "Karabiner Kurz",
                             "artikelnummer": "KK-1", "materialart": "metall_hardware", "beschreibung": "Screwlock"}]}
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app = make_app(tmp_a)
        c = anmelden(app, "admin@example.org", "geheim123")
        ber = importieren(c, json.dumps(katalog).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"] and ber["produkte"]["neu"] == 2, ber
        lang = [h for h in ber["hinweise"] if "Beschreibung" in h]
        assert len(lang) == 1 and "Karabiner Lang" in lang[0] and f"{len(LANG)} Zeichen" in lang[0], ber["hinweise"]
        assert _db(app, "SELECT description FROM mat_product WHERE model = 'Karabiner Lang'")["description"] == LANG
        # Wiederholt: unverändert, kein Hinweis.
        ber = importieren(c, json.dumps(katalog).encode(), False, "katalog.json")
        assert ber["produkte"] == {"neu": 0, "geaendert": 0, "unveraendert": 2}, ber
        assert not [h for h in ber["hinweise"] if "Beschreibung" in h], ber["hinweise"]

        # Austausch in eine zweite Instanz (Format 2): erst der Probelauf, dann der echte Lauf.
        roh = exportieren(c)
        app_b = make_app(tmp_b)
        c_b = anmelden(app_b, "admin@example.org", "geheim123")
        ber = importieren(c_b, roh, True)
        assert not ber["fehler"] and not ber["gespeichert"] and ber["produkte"]["neu"] == 2, ber
        ber = importieren(c_b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"] and ber["version"] == 2, ber
        assert any("Karabiner Lang" in h for h in ber["hinweise"]), ber["hinweise"]
        zeilen = {r["model"]: r["description"] for r in _db(app_b, "SELECT model, description FROM mat_product",
                                                            one=False)}
        assert zeilen == {"Karabiner Lang": LANG, "Karabiner Kurz": "Screwlock"}, zeilen
        # Zurück nach A: nichts zu tun.
        ber = importieren(c, exportieren(c_b), False)
        assert ber["produkte"]["geaendert"] == 0 and not ber["fehler"], ber
    print("Import mit langer Beschreibung bestanden.")


def test_bericht_und_journal_mit_zusatz():
    """Prüfung der Nachbesserung: Importbericht und Journal nennen ein Produkt wie überall „Hersteller Modell |
    Beschreibung“ – zwei Varianten, die nur die Beschreibung trennt, sind im Bericht zu unterscheiden: neu (auch im
    Probelauf), geändert, als Ziel eines Formulars und in der Meldung „kein Prüfintervall mehr“; der Journaleintrag „als
    Variante angelegt“ nennt die Quelle mit ihrem Zusatz. Vorher stand zweimal „Produkt „Testwerk D Test“: neu“ da."""
    def katalog(zweite="Twistlock", intervall=12):
        return json.dumps({
            "format": "stroemis-material-katalog", "version": 1,
            "kategorien": [{"name": "Testkategorie", "materialart": "metall_hardware", "intervall_monate": intervall}],
            "produkte": [{"kategorie": ["Testkategorie"], "hersteller": "Testwerk", "modell": "D Test",
                          "artikelnummer": f"DT-{i}", "materialart": "metall_hardware", "beschreibung": b}
                         for i, b in ((1, "Screwlock"), (2, zweite))],
            "formulare": [{"produkt": {"hersteller": "Testwerk", "modell": "D Test", "artikelnummer": "DT-1"},
                           "titel": "Testformular", "punkte": [{"gruppe": "Testgruppe", "text": "Testpunkt (Platzhalter)",
                                                                "art": "yesno", "soll": "ja", "kritisch": True}]}],
        }).encode()

    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        for trocken in (True, False):
            ber = importieren(c, katalog(), trocken, "katalog.json")
            assert not ber["fehler"] and ber["produkte"]["neu"] == 2, ber
            z = ber["aenderungen"]
            assert "Produkt „Testwerk D Test | Screwlock“: neu" in z and "Produkt „Testwerk D Test | Twistlock“: neu" in z, z
            assert any(a.startswith("Formular „Testformular“ (Produkt „Testwerk D Test | Screwlock“)") for a in z), z
        ber = importieren(c, katalog(zweite="Ball-Lock"), False, "katalog.json")
        assert ber["produkte"]["geaendert"] == 1, ber
        assert [a for a in ber["aenderungen"] if a.startswith("Produkt „Testwerk D Test | Ball-Lock“: geändert")], ber
        ber = importieren(c, katalog(zweite="Ball-Lock", intervall=None), True, "katalog.json")
        fehler = ber["fehler"]                             # Fehlerorte und die Meldung an der Kategorie
        assert [x[:43] for x in fehler[:2]] == ["produkte[0] (Testwerk D Test | Screwlock): ",
                                                "produkte[1] (Testwerk D Test | Ball-Lock): "], fehler
        assert ("kategorien[0] (Testkategorie): Danach hätten diese Produkte kein Prüfintervall mehr: Testwerk D Test | "
                "Screwlock, Testwerk D Test | Ball-Lock.") in fehler[2], fehler
        # Eine Variante über die Oberfläche: Der Journaleintrag nennt die Quelle mit ihrem Zusatz.
        pid = _db(app, "SELECT id FROM mat_product WHERE article_no = 'DT-1'")["id"]
        quelle = c.get(f"/api/material/produkte/{pid}").json["produkt"]
        stamm = {f: quelle[f] for f in FELDER}
        r = c.post(f"/api/material/produkte/{quelle['id']}/variante", headers=H,
                   json=dict(stamm, article_no="DT-3", description="Triact-Lock"))
        assert r.status_code == 201, r.get_json()
        journal = c.get(f"/api/material/produkte/{r.json['produkt']['id']}").json["produkt"]["journal"]
        eintrag = [e for e in journal if e["action"] == "variante"]
        assert len(eintrag) == 1 and eintrag[0]["nachher"]["name"] == "Testwerk D Test | Screwlock", journal
    print("Bericht und Journal mit Zusatz bestanden.")


def test_demo_ohne_beschreibung():
    """Prüfung der Nachbesserung: Die DEMO-Produkte haben keine Beschreibung – den Hinweis „DEMO – nicht für echte
    Prüfungen“ trägt die DEMO-Marke, als Zusatz hinter dem Namen stand er doppelt („DEMO Gurt A | DEMO – nicht für echte
    Prüfungen“). Ein neuer Lauf des DEMO-Skripts leert ihn auch in einem älteren DEMO-Katalog; die DEMO-Gliederung
    behält ihn als Beschreibung."""
    import contextlib
    import importlib.util
    import io
    from app.material.services import katalog
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def laufen(frueher=False):
        spec = importlib.util.spec_from_file_location("material_demo_beschreibung",
                                                      os.path.join(wurzel, "scripts", "material_demo.py"))
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        if frueher:                                    # der Stand vor der Nachbesserung
            for p in modul.KATALOG["produkte"]:
                p["beschreibung"] = modul.HINWEIS
        argv, sys.argv = sys.argv, ["material_demo.py", "--demo"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                modul.main()
        finally:
            sys.argv = argv
        return modul

    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        modul = laufen(frueher=True)
        sql = "SELECT manufacturer, model, description FROM mat_product WHERE demo = 1"
        assert {z["description"] for z in _db(app, sql, one=False)} == {modul.HINWEIS}
        laufen()
        zeilen = _db(app, sql, one=False)
        assert len(zeilen) == 5 and all(z["description"] == "" for z in zeilen), zeilen
        assert all(katalog.produktname(z) == f"{z['manufacturer']} {z['model']}" for z in zeilen), zeilen
        assert _db(app, "SELECT description FROM mat_folder WHERE name = ?", (modul.GLIEDERUNG,))["description"] \
            == modul.HINWEIS
    with tempfile.TemporaryDirectory() as tmp:                # ein frischer DEMO-Katalog ebenso
        app = make_app(tmp)
        laufen()
        assert {z["description"] for z in _db(app, "SELECT description FROM mat_product WHERE demo = 1", one=False)} \
            == {""}
    print("DEMO-Produkte ohne Beschreibung bestanden.")


def test_regel_produktname():
    """Die Regel für den Namen (katalog.zusatz, produktname – dieselbe wie produktZusatz in material.js): ohne
    Beschreibung nur der Name ohne Strich; mit „Modell | Beschreibung“; steht der Zusatz schon von Hand im Modellnamen,
    nicht doppelt; Leerraum und Zeilenumbrüche werden ein Leerzeichen; eine ältere, lange Beschreibung endet in einer
    Zeile nach höchstens 80 Zeichen am Wortende mit „…“."""
    from app.material.services import katalog
    assert katalog.BESCHREIBUNG_MAX == 80

    def name(modell, beschreibung):
        return katalog.produktname({"manufacturer": "Testwerk", "model": modell, "description": beschreibung})

    assert name("D Test", "") == name("D Test", None) == "Testwerk D Test"
    assert name("D Test", "Screwlock") == "Testwerk D Test | Screwlock"
    assert name("D Test | Screwlock", "") == "Testwerk D Test | Screwlock"            # von Hand im Modellnamen
    assert name("D Test | Screwlock", " screwlock ") == "Testwerk D Test | Screwlock"  # nicht doppelt
    assert name("D Test | Screwlock", "Twistlock") == "Testwerk D Test | Screwlock | Twistlock"
    assert name("D Test", "Screw\n  lock\tAlu") == "Testwerk D Test | Screw lock Alu"
    assert katalog.produktname({"manufacturer": "Testwerk", "model": "D Test", "description": "x"}, "Ball-Lock") \
        == "Testwerk D Test | Ball-Lock"                                                 # aus product_description
    z = katalog.zusatz("D Test", LANG)
    flach = " ".join(LANG.split())
    assert len(z) <= 80 and z.endswith("…") and "\n" not in z, z
    assert flach.startswith(z[:-1]) and flach[len(z) - 1] == " ", z                  # am Wortende abgeschnitten
    assert katalog.zusatz("D Test", "y" * 80) == "y" * 80 and katalog.zusatz("D Test", "y" * 81) == "y" * 79 + "…"
    print("Regel für den Produktnamen bestanden.")


def test_darstellung():
    """Wo der Server den Produktnamen liefert oder druckt, steht der Zusatz dabei: Artikellisten (Ordner, Suche,
    offene Prüfungen) tragen die Beschreibung des Produkts, die Prüfung Name und Felder, das neue Prüfprotokoll und der
    Lebenslauf (PDF) „Hersteller Modell | Beschreibung“, die CSV eine eigene Spalte „Beschreibung“ hinter „Modell“ (voll, ungekürzt),
    der Hinweis zur vergebenen Artikelnummer den Namen."""
    from app.material.services import export
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        assert kp.put(f"/api/material/produkte/{ids['hms']}", json={"description": "Twistlock"}).status_code == 200
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        g = neuer_artikel(w, ids["gurt"], gid, manufactured_on="2025-01")
        liste = {x["id"]: x for x in w.get(f"/api/material/ordner/{gid}").json["ordner"]["artikel"]}
        assert liste[a["id"]]["description"] == "Twistlock" and liste[g["id"]]["description"] == "", liste
        t = w.get("/api/material/suche", query_string={"q": a["inventory_no"]}).json["treffer"]
        assert t[0]["id"] == a["id"] and t[0]["description"] == "Twistlock" and t[0]["model"] == "HMS Beta", t
        pr = starten(p1, a["id"]).json["pruefung"]
        assert pr["produkt"]["name"] == "Testwerk HMS Beta | Twistlock", pr["produkt"]
        assert (pr["produkt"]["model"], pr["produkt"]["description"]) == ("HMS Beta", "Twistlock"), pr["produkt"]
        offen = p1.get("/api/material/entwuerfe").json["entwuerfe"]
        assert offen[0]["artikel"]["description"] == "Twistlock", offen
        r = festschreiben(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, pr["id"])["pdf_path"]))))
        assert "Testwerk HMS Beta | Twistlock" in text, text[:600]
        # Der Lebenslauf (PDF, Stand jetzt) ebenso.
        r = w.get(f"/material/artikel/{a['id']}/lebenslauf.pdf")
        assert r.status_code == 200, r.status_code
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        assert "Testwerk HMS Beta | Twistlock" in _flach(" ".join(pdf_seiten(pfad)))
        # CSV: eigene Spalte hinter „Modell“; das Modell allein.
        r = w.get(f"/material/export/{gid}.csv")
        assert r.status_code == 200, r.status_code
        kopf, zeilen = csv_lesen(r.data)
        assert kopf == list(export.ARTIKEL_SPALTEN) and kopf[kopf.index("Modell") + 1] == "Beschreibung", kopf
        z = {x["Inventarnummer"]: x for x in zeilen}
        assert z[a["inventory_no"]]["Modell"] == "HMS Beta" and z[a["inventory_no"]]["Beschreibung"] == "Twistlock", z
        assert z[g["inventory_no"]]["Beschreibung"] == "", z
        r = kp.get("/api/material/produkte/artikelnummer", query_string={"nr": "HB-7"})
        assert r.json["produkt"]["name"] == "Testwerk HMS Beta | Twistlock", r.get_json()
    print("Darstellung (Server, PDF, CSV) bestanden.")


def test_suche_ueber_beschreibung():
    """Die Produktsuche (Katalog, Artikel anlegen, Meldung zuordnen) findet auch über die Beschreibung – ganze und
    halbe Wörter, kurze (LIKE) wie lange (Trigrammindex), auch gemischt mit dem Modell; mit und ohne Volltextindex."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp, w = k["katalog"], k["wart"]
        r = kp.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                    "model": "D Classic", "article_no": "DC-1",
                                                    "material_kind": "metall_hardware", "interval_months": 12,
                                                    "description": "Screwlock"})
        assert r.status_code == 201, r.get_json()
        dc = r.json["produkt"]["id"]

        def treffer(c, q):
            r = c.get("/api/material/produkte", query_string={"q": q})
            assert r.status_code == 200, r.get_json()
            return [p["id"] for p in r.json["produkte"]]

        volltext = _db(app, "SELECT wert FROM mat_meta WHERE schluessel = 'volltext'")
        stufen = ["1", "0"] if volltext and volltext["wert"] == "1" else ["0"]
        for stufe in stufen:
            with app.app_context():
                from app import db
                db.execute("UPDATE mat_meta SET wert = ? WHERE schluessel = 'volltext'", (stufe,))
            for q in ("Screwlock", "screwl", "Classic Screwlock", "Testwerk crew", "D Screwlock DC-1"):
                assert treffer(kp, q) == [dc], (stufe, q, treffer(kp, q))
            assert dc in treffer(kp, "sc"), stufe
            assert treffer(kp, "Twistlock") == [] and treffer(kp, "Classic Twistlock") == [], stufe
            # Artikel anlegen (Materialwart) nutzt dieselbe Suche.
            assert treffer(w, "Screwlock") == [dc], stufe
    print("Suche über die Beschreibung bestanden.")


def test_oberflaeche_statisch():
    """material.js: eine Regel für den Produktnamen (produktZusatz mit den Ausgaben produktName und produktHtml, für
    suche.js und global.js als window.MatProdukt) mit derselben Grenze wie der Server; das Feld im Produktdialog ist
    einzeilig wie die anderen, mit Höchstlänge, Hilfetext und dem Hinweis für ältere lange Beschreibungen. Listen, Seiten,
    Vorschläge und Steckbrief nehmen die Regel – keine eigene Verkettung von Hersteller und Modell mehr."""
    from app.material.services import katalog
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def lesen(rel):
        with open(os.path.join(wurzel, rel), encoding="utf-8") as fh:
            return fh.read()

    js, suche, glob = (lesen(f"app/material/static/{d}.js") for d in ("material", "suche", "global"))
    assert f"const BESCHREIBUNG_MAX = {katalog.BESCHREIBUNG_MAX};" in js
    assert "window.MatProdukt = { name: produktName, html: produktHtml, zusatz: produktZusatz" in js
    # Strich und Zusatz bleiben zusammen (Prüfung der Nachbesserung): Ein Wortverbinder (U+2060) verbietet den Umbruch
    # zwischen „|“ und dem geschützten Leerzeichen – sonst stand es am Anfang der nächsten Zeile, im Link unterstrichen.
    assert '>|&#x2060;&nbsp;${esc(z.text)}</span>` : name;' in js and ">|&nbsp;" not in js
    # Die Regel steht vor „if (!root) return;“ – suche.js und global.js finden sie auf jeder Modulseite.
    assert js.index("window.MatProdukt =") < js.index("if (!root) return;")
    # Der Dialog: ein einzeiliges Feld wie die anderen, Höchstlänge, Hilfetext, Hinweis mit dem bisherigen Text.
    feld = re.search(r'<input type="text" id="pd-desc"[^>]*>', js)
    assert feld and 'maxlength="${BESCHREIBUNG_MAX}"' in feld.group(0), feld
    assert '<textarea id="pd-desc"' not in js
    for haken in ("Kurzer Zusatz hinter dem Namen, z. B. die Verschlussart.", 'id="pd-desc-alt"', "Bitte kürzen:",
                  "if (laenge > BESCHREIBUNG_MAX)"):
        assert haken in js, haken
    # Listen und Seiten: der Zusatz im selben Link bzw. derselben Hervorhebung wie das Modell.
    for stelle in ('<strong>${produktHtml(x, true)}</strong></a>', "${produktHtml(a, true)}${a.article_no",
                   '<h1>${produktHtml(p)} ${demoMarke(p.demo)}</h1>', "<strong>${produktHtml(pr.produkt)}</strong>",
                   '<strong>${produktHtml(p)}</strong> <span class="muted">${esc(p.article_no || "")} · '):
        assert stelle in js, stelle
    for alt in ("esc(x.model", "esc(a.model", "esc(pr.produkt.name)", "const produktName = (p) =>"):
        assert alt not in js, alt
    # Vorschläge und Steckbrief.
    assert "window.MatProdukt.html(a)" in suche and "a.model" not in suche
    assert ("window.MatProdukt.html({ manufacturer: t.hersteller, model: t.modell, description: t.beschreibung })"
            in glob)
    seite = lesen("app/material/templates/material/seite.html")
    assert seite.index("material.js") < seite.index("suche.js") < seite.index("global.js")
    # „Art.-Nr. …“ und „Seriennummer …“ hinter dem Produkt als ein Stück (Gesamtprüfung: mit dem Zusatz brach die Zeile
    # sonst als „Art.-“ / „Nr. …“ oder „DEMO-K-“ / „1“) – an allen fünf Stellen über MatProdukt.artNr, keine eigene
    # Verkettung mehr; was breiter ist als die Zeile, bricht darin um (inline-block mit max-width).
    for datei in (js, suche, glob):
        assert "· Art.-Nr. ${" not in datei
    assert js.count("${artNrHtml(") == 3 and js.count('${nummerHtml("Seriennummer", a.serial_no)}') == 2
    assert "window.MatProdukt.artNr(a.article_no, markiert(a.article_no, q))" in suche
    assert "window.MatProdukt.artNr(t.artikelnummer)" in glob
    assert ".mat-ganz { display: inline-block; max-width: 100%; }" in lesen("app/material/static/material.css")
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_laenge_beim_speichern()
    test_import_lange_beschreibung()
    test_bericht_und_journal_mit_zusatz()
    test_demo_ohne_beschreibung()
    test_regel_produktname()
    test_darstellung()
    test_suche_ueber_beschreibung()
    test_oberflaeche_statisch()
