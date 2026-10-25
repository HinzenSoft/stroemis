"""Beispielbestand (scripts/material_beispielbestand.py):  python tests/test_material_beispielbestand.py  oder  pytest …

Ein Testkatalog mit offensichtlichen Platzhaltern wie in den anderen Tests (echte Produkte ohne DEMO-Kennzeichen: ein
textiles mit Lebensdauer und spezifischem Formular, ein Metallprodukt mit generischem Formular, eines ohne Formular;
dazu ein Produktbild, ein Dokument und ein DEMO-Teil). Der Generator läuft mit kleiner Zahl: Der Katalog bleibt Zeile
für Zeile und Datei für Datei gleich – auch sein Export im Format 2 – bis auf DEMO-Formulare an Kategorien ohne
wirksames Formular (nicht im Export); jeder Zustand kommt vor, die Geschichte reicht über zwei Jahre (Jahresdurchgänge,
Mängel mit Reparatur, Aussonderungen mit Nachkauf, Verschiebungen, Zuordnungen auch beendet, Änderungsanträge), jede
abgeschlossene Prüfung ist festgeschrieben und hat ihr Protokoll, und die DEMO-Kennzeichnung greift an Artikel, Liste,
Protokoll, Sammelprotokoll, Lebenslauf, CSV und Steckbrief – auch für echte Produkte, weil ihre Heimat ein DEMO-Ordner
ist (bestand.demo_sql). Ein zweiter Lauf legt nichts an, ohne Schalter endet das Skript mit 2, außerhalb von dev und
ohne echte Produkte mit 1; ein abgebrochener Lauf (Strg-C oder SIGHUP) hinterlässt einen Teilbestand, den der nächste
Lauf als unvollständig meldet (Rückgabewert 1) statt „schon da“. Die Prüfer prüfen dauerhaft, nur der externe befristet.
Die Formulare nach den Petzl-Prüfberichten (scripts/beispielbestand_petzl_punkte.json) prüft test_formulare.
Alle Namen und Nummern hier sind erfunden und nur für den Test da."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, _flach, gliederung, jpeg, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pdf_seiten, pruef_formulare, starten, umgebung)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HINWEIS = "DEMO – nicht für echte Prüfungen"
KATALOG_TABELLEN = ("mat_category", "mat_product", "mat_product_document", "mat_form", "mat_checklist_item",
                    "mat_recall", "mat_product_request")
BESTAND_TABELLEN = ("mat_folder", "mat_item", "mat_inspection", "mat_inspection_result", "mat_round", "mat_round_item",
                    "mat_folder_grant", "mat_audit", "users")
GLIEDERUNGEN = ("DEMO-Kreisverband Flussland", "DEMO-OG Nachbarstadt")
ARTIKEL = 50
PETZL = os.path.join(REPO, "scripts", "beispielbestand_petzl_punkte.json")


def laufen(*schalter, adresse="https://dev.strömis.de", anpassen=None):
    """Das Skript wie von der Kommandozeile – (Ausgabe, Rückgabewert). adresse: BASE_URL für den Lauf (make_app setzt die
    der Produktion, dort legt das Skript nichts an). anpassen(modul) darf das frisch geladene Skript vorher ändern; ein
    Lauf, der mit KeyboardInterrupt endet, liefert den Rückgabewert „unterbrochen“."""
    spec = importlib.util.spec_from_file_location("material_beispielbestand_test",
                                                  os.path.join(REPO, "scripts", "material_beispielbestand.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    if anpassen:
        anpassen(modul)
    puffer, code, alt = io.StringIO(), 0, os.environ.get("BASE_URL")
    os.environ["BASE_URL"] = adresse
    try:
        with contextlib.redirect_stdout(puffer):
            modul.main(list(schalter))
    except SystemExit as exc:
        code = exc.code
    except KeyboardInterrupt:
        code = "unterbrochen"
    finally:
        if alt is None:
            os.environ.pop("BASE_URL", None)
        else:
            os.environ["BASE_URL"] = alt
    return puffer.getvalue(), code


def sha(pfad):
    with open(pfad, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def katalog_stand(app, ohne_demo_formulare=False):
    """Alles, was zum Katalog gehört: jede Zeile jeder Katalogtabelle, der Export im Format 2 (katalog.json ohne
    Zeitstempel, Prüfsummen der Dateien im Archiv) und die Dateien hinter Produktbildern und Dokumenten.
    ohne_demo_formulare: die DEMO-Formulare des Beispielbestands samt Prüfpunkten nicht mitzählen."""
    with app.app_context():
        from app import db
        from app.material.services import katalog, katalog_export
        tabellen = {t: db.query(f"SELECT * FROM {t} ORDER BY id") for t in KATALOG_TABELLEN}
        if ohne_demo_formulare:
            demo = {f["id"] for f in tabellen["mat_form"] if f["demo"] and f["title"].startswith(
                ("DEMO-Prüfformular (Platzhalter) – ", "DEMO – Prüfformular nach Petzl-Prüfbericht"))}
            tabellen["mat_form"] = [f for f in tabellen["mat_form"] if f["id"] not in demo]
            tabellen["mat_checklist_item"] = [c for c in tabellen["mat_checklist_item"] if c["form_id"] not in demo]
        daten, dateien, _ = katalog_export.sammeln()
        daten.pop("erstellt")
        medien = katalog.medien_dir()
        files = {}
        for p in tabellen["mat_product"]:
            if p["image"]:
                stamm = os.path.splitext(p["image"])[0]
                for art, name in (("orig", p["image"]), ("web", stamm + ".jpg"), ("thumb", stamm + ".jpg")):
                    files[f"{art}/{name}"] = sha(os.path.join(medien, art, name))
        for d in tabellen["mat_product_document"]:
            if d["file_path"]:
                files[f"dok/{d['file_path']}"] = sha(os.path.join(medien, "dok", d["file_path"]))
        return {"tabellen": tabellen, "export": json.dumps(daten, ensure_ascii=False, sort_keys=True),
                "export_dateien": {k: sha(v) for k, v in dateien.items()}, "dateien": files}


def bestand_stand(app):
    with app.app_context():
        from app import db
        return {t: db.query(f"SELECT * FROM {t} ORDER BY rowid") for t in BESTAND_TABELLEN}


def platzhalterkatalog(k):
    """Echte Produkte (ohne DEMO-Kennzeichen, Platzhalter): Gurt Alpha (textil, 10 Jahre, spezifisches Formular mit
    Ja/Nein, Zahl ohne Soll und freiem Text), HMS Beta (Metall, generisches Formular), Helm Gamma (ohne Formular). Dazu
    ein Produktbild, ein Dokument als Datei und eins als Link, ein inaktiver Formularentwurf und ein DEMO-Teil."""
    kp = k["katalog"]
    ids = katalog_grund(k["adm"])
    ids["formulare"] = pruef_formulare(kp, ids)
    r = kp.post("/api/material/kategorien", json={"name": "Helme (Test)", "parent_id": ids["psa"],
                                                  "default_material_kind": "sonstiges", "default_interval_months": 12})
    assert r.status_code == 201, r.get_json()
    r = kp.post("/api/material/produkte", json={"category_id": r.json["kategorie"]["id"], "manufacturer": "Testwerk",
                                                "model": "Helm Gamma", "article_no": "HG-3", "material_kind": "sonstiges"})
    assert r.status_code == 201, r.get_json()
    ids["helm"] = r.json["produkt"]["id"]
    r = kp.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")}, headers=H,
                content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    r = kp.post(f"/api/material/produkte/{ids['hms']}/dokumente", headers=H, content_type="multipart/form-data",
                data={"file": (io.BytesIO(PDF + b"%test"), "anleitung.pdf"), "kind": "gebrauchsanleitung",
                      "title": "Anleitung HMS Beta (Test)", "valid_from": "2024-01-01"})
    assert r.status_code == 201, r.get_json()
    r = kp.post(f"/api/material/kategorien/{ids['gurte']}/dokumente",
                json={"kind": "pflegehinweis", "title": "Pflege (Test)", "url": "https://hersteller.example/pflege"})
    assert r.status_code == 201, r.get_json()
    r = kp.post("/api/material/formulare", json={"produkt_id": ids["hms"], "titel": "HMS Beta (Entwurf)", "punkte": [
        {"text": "Testpunkt Entwurf", "art": "yesno", "soll": "ja"}]})
    assert r.status_code == 201, r.get_json()
    demo = {"format": "stroemis-material-katalog", "version": 1, "demo": True,
            "kategorien": [{"name": "DEMO Testbaum", "materialart": "metall_hardware", "intervall_monate": 12}],
            "produkte": [{"kategorie": ["DEMO Testbaum"], "hersteller": "DEMO-Testwerk", "modell": "DEMO Teil",
                          "artikelnummer": "DEMO-T-1", "materialart": "metall_hardware"}],
            "formulare": [{"kategorie": ["DEMO Testbaum"], "titel": "DEMO-Formular",
                           "punkte": [{"text": "DEMO-Prüfpunkt", "art": "yesno", "soll": "ja"}]}]}
    with k["adm"].application.app_context():
        from flask import g

        from app.material.services import importer
        g.mat_akteur = "Test"
        assert not importer.importieren(demo, quelle="Test")["fehler"]
        from app import db
        ids["demo"] = db.query("SELECT id FROM mat_product WHERE demo = 1", one=True)["id"]
    return ids


def protokoll_text(app, rel):
    with app.app_context():
        from flask import current_app
        return _flach(" ".join(pdf_seiten(os.path.join(current_app.config["DATA_DIR"], rel))))


# --- Tests -------------------------------------------------------------------------------------------------------------

def test_ohne_schalter():
    """Ohne --beispielbestand (oder mit Unbekanntem): Hilfe, Rückgabewert 2; außerhalb von dev (Positivliste BASE_URL
    wie flask material dev-zuruecksetzen): 1. Beides legt nichts an."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        vorher = bestand_stand(app)
        for schalter in ((), ("--artikel", "10"), ("--beispielbestand", "--artikel", "null"), ("--beispiel",)):
            aus, code = laufen(*schalter)
            assert code == 2 and "Abgebrochen" in aus and "--beispielbestand" in aus, (schalter, aus[-300:])
            # Die Hilfe nennt, was danach im Katalog nicht mehr geht.
            assert "seine Materialart nicht mehr" in aus and "Formularversion" in aus, aus[:3000]
        # Außerhalb von dev (oder localhost) legt das Skript nichts an – auch mit Schalter.
        for adresse in ("https://strömis.de", "https://www.xn--strmis-yxa.de/", "https://beispiel.example", ""):
            aus, code = laufen("--beispielbestand", adresse=adresse)
            assert code == 1 and "gehört nur auf dev" in aus, (adresse, aus[-300:])
        assert bestand_stand(app) == vorher
    print("Ohne Schalter bestanden.")


def test_ohne_echte_produkte():
    """Nur DEMO-Produkte im Katalog: Abbruch mit Klartext (Rückgabewert 1) – kein Ordner, kein Konto."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        with app.app_context():
            from flask import g

            from app.material.services import importer
            g.mat_akteur = "Test"
            assert not importer.importieren({
                "format": "stroemis-material-katalog", "version": 1, "demo": True,
                "kategorien": [{"name": "DEMO Nur", "materialart": "metall_hardware", "intervall_monate": 12}],
                "produkte": [{"kategorie": ["DEMO Nur"], "hersteller": "DEMO-Testwerk", "modell": "DEMO Einzel",
                              "materialart": "metall_hardware"}]}, quelle="Test")["fehler"]
        vorher = bestand_stand(app)
        aus, code = laufen("--beispielbestand", "--artikel", "5")
        assert code == 1 and "keine echten Produkte" in aus, aus
        assert bestand_stand(app) == vorher
    print("Ohne echte Produkte bestanden.")


def test_demo_grenze_beim_verschieben():
    """Über die Grenze der Demodaten verschiebt niemand, auch nicht die Plattform-Verwaltung (409, bestand.DEMO_GRENZE) –
    in beide Richtungen, Artikel wie Ordner, auch ein Ordner ohne Kennzeichen in einer DEMO-Gliederung und eine Auswahl,
    in der nur einer die Grenze überschritte. Sonst wechselte „DEMO“ an Artikel, Lebenslauf, CSV und Verzeichnis, während
    die festgeschriebenen Protokolle blieben, wie sie sind. Innerhalb der Demodaten und im echten Bestand geht es weiter."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, ids = k["adm"], katalog_grund(k["adm"])
        echt_gl, _ = gliederung(adm, "OG Musterstadt")

        def ordner(name, oben, art="sonstiges"):
            r = adm.post("/api/material/ordner", json={"name": name, "kind": art, "parent_id": oben})
            assert r.status_code == 201, r.get_json()
            return r.json["ordner"]["id"]

        echt_lager = ordner("Lager (Test)", echt_gl, "standort")
        with app.app_context():
            from flask import g

            from app.material.services import bestand
            g.mat_akteur = "Test"
            demo_gl = bestand.ordner_anlegen({"name": "DEMO-OG Testau", "kind": "gliederung"}, demo=True)
            demo_lager = bestand.ordner_anlegen({"name": "DEMO-Lager", "kind": "standort", "parent_id": demo_gl},
                                                demo=True)
            demo_gl2 = bestand.ordner_anlegen({"name": "DEMO-OG Zweitau", "kind": "gliederung"}, demo=True)
        ober = ordner("Über die Oberfläche (Test)", demo_gl)           # ohne Kennzeichen, aber in einer DEMO-Gliederung
        ober_gl = ordner("Untergliederung (Test)", demo_gl, "gliederung")
        echt = neuer_artikel(adm, ids["hms"], echt_lager, serial_no="ECHT-G1")
        demo = neuer_artikel(adm, ids["hms"], demo_lager, serial_no="DEMO-G1")
        assert demo["demo"] is True and echt["demo"] is False

        def artikel(liste, ziel):
            return adm.post("/api/material/artikel/verschieben", json={"ids": liste, "folder_id": ziel}, headers=H)

        def verschieben(fid, ziel):
            return adm.post(f"/api/material/ordner/{fid}/verschieben", json={"parent_id": ziel}, headers=H)

        vorher = bestand_stand(app)
        for r in (artikel([echt["id"]], demo_lager), artikel([echt["id"]], ober), artikel([demo["id"]], echt_lager),
                  artikel([demo["id"]], echt_gl), artikel([demo["id"], echt["id"]], demo_gl2),
                  verschieben(demo_lager, echt_gl), verschieben(ober, echt_lager), verschieben(ober_gl, None),
                  verschieben(echt_lager, demo_gl), verschieben(echt_gl, demo_gl)):
            assert r.status_code == 409 and "Demodaten" in r.get_json()["error"], r.get_json()
        assert bestand_stand(app) == vorher
        assert adm.get(f"/api/material/artikel/{echt['id']}").json["artikel"]["demo"] is False
        assert adm.get(f"/api/material/artikel/{demo['id']}").json["artikel"]["demo"] is True

        # Innerhalb der Demodaten und im echten Bestand verschiebt es sich wie immer.
        assert artikel([demo["id"]], demo_gl2).status_code == 200
        assert artikel([demo["id"]], ober).status_code == 200
        assert artikel([echt["id"]], echt_gl).status_code == 200
        assert verschieben(ober, demo_gl2).status_code == 200
        assert verschieben(demo_lager, ober).status_code == 200
        assert verschieben(echt_lager, echt_gl).status_code == 200      # schon dort: ohne Wirkung, ohne Fehler
        assert adm.get(f"/api/material/artikel/{demo['id']}").json["artikel"]["demo"] is True
        assert adm.get(f"/api/material/artikel/{echt['id']}").json["artikel"]["demo"] is False
    print("Grenze der Demodaten beim Verschieben bestanden.")


def test_beispielbestand():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = platzhalterkatalog(k)
        # Ein echter Bestand daneben: eine Gliederung ohne DEMO mit einem geprüften Artikel – er bleibt ohne DEMO.
        echt_gl, _ = gliederung(k["adm"], "OG Musterstadt")
        echt = neuer_artikel(k["wart"], ids["hms"], echt_gl, serial_no="ECHT-1")["id"]
        r = starten(k["pruefer"], echt)
        assert r.status_code == 201, r.get_json()
        r = k["pruefer"].post(f"/api/material/pruefungen/{r.json['pruefung']['id']}/abschliessen",
                              json={"ergebnis": "einsatzbereit"})
        assert r.status_code == 200, r.get_json()
        katalog_vorher = katalog_stand(app)
        assert katalog_vorher["dateien"] and katalog_vorher["export_dateien"]
        with app.app_context():
            from app import db
            journal_vor = db.query("SELECT MAX(id) AS n FROM mat_audit", one=True)["n"]

        t0 = time.time()
        aus, code = laufen("--beispielbestand", "--artikel", str(ARTIKEL))
        dauer = time.time() - t0
        assert code == 0, aus[-3000:]
        assert "Beispielbestand angelegt" in aus and "Kommt nicht vor" not in aus, aus[-3000:]
        assert not re.search(r"^Hinweise", aus, re.M), aus[-3000:]          # nichts gescheitert
        # Der Bericht nennt die Folge für die Katalogpflege: Produkte mit Artikeln bleiben, ihre Materialart steht fest.
        assert "Jetzt mit Artikeln: 3 Produkte" in aus, aus[-2000:]
        r = k["katalog"].delete(f"/api/material/produkte/{ids['helm']}", headers=H)
        assert r.status_code == 409, r.get_json()

        # 1. Der Katalog bleibt unverändert – Zeilen, Export und Dateien – bis auf das DEMO-Platzhalter-Formular an der
        # Oberkategorie (sie hatte keins; der Helm erbt es), das der Export auslässt.
        nachher = katalog_stand(app, ohne_demo_formulare=True)
        for teil in ("export", "export_dateien", "dateien"):
            assert nachher[teil] == katalog_vorher[teil], teil
        for t in KATALOG_TABELLEN:
            assert nachher["tabellen"][t] == katalog_vorher["tabellen"][t], t

        with app.app_context():
            from app import db
            from app.material.services import bestand, export, globalsuche, katalog, lebenslauf
            from app.material.services import status as st
            demo_formulare = db.query("SELECT * FROM mat_form WHERE demo = 1 AND title LIKE 'DEMO-Prüfformular%'")
            assert [(f["title"], f["category_id"], f["active"]) for f in demo_formulare] == [
                ("DEMO-Prüfformular (Platzhalter) – PSA gegen Absturz", ids["psa"], 1)], demo_formulare
            assert katalog.formular_fuer_produkt(ids["helm"])["id"] == demo_formulare[0]["id"]
            gls = db.query(f"SELECT * FROM mat_folder WHERE parent_id IS NULL AND name IN ({','.join('?' * 2)})",
                           GLIEDERUNGEN)
            assert len(gls) == 2 and all(g["demo"] and g["kind"] == "gliederung" for g in gls), gls
            fl = next(g for g in gls if g["name"] == GLIEDERUNGEN[0])
            ns = next(g for g in gls if g["name"] == GLIEDERUNGEN[1])
            zweige = set()
            for g in gls:
                zweige |= bestand.unterbaum(g["id"])
            ordner = db.query(f"SELECT * FROM mat_folder WHERE id IN ({','.join(str(x) for x in zweige)})")
            assert all(o["demo"] for o in ordner)
            assert all(o["name"].startswith("DEMO-") or o["system_kind"] for o in ordner), [o["name"] for o in ordner]
            assert all(not o["interval_months"] for o in ordner)
            arten = Counter(o["kind"] for o in ordner)
            assert arten["fahrzeug"] == 6 and arten["set"] == 5 and arten["persoenlich"] >= 2, arten
            sets = {o["id"]: o for o in ordner if o["kind"] == "set"}
            assert any(o["parent_id"] in sets for o in sets.values())                      # ein Set im Set
            artikel = [i for i in db.query("SELECT * FROM mat_item") if bestand.heimat(i) in zweige]
            nachkauf = [i for i in artikel if re.search(r"-[EN]$", i["serial_no"])]
            assert len(artikel) - len(nachkauf) == ARTIKEL, (len(artikel), len(nachkauf))
            assert any(bestand.heimat(i) in bestand.unterbaum(ns["id"]) for i in artikel)
            assert db.query("SELECT 1 FROM mat_item WHERE serial_no = 'DEMO-NS-4711'", one=True)

            # 2. Nur echte Produkte, alle davon; DEMO-Bestandsangaben.
            assert {i["product_id"] for i in artikel} == {ids["gurt"], ids["hms"], ids["helm"]}
            assert all(i["serial_no"].startswith("DEMO-") and i["notes"] == HINWEIS for i in artikel)
            assert not db.query("SELECT 1 FROM mat_item WHERE product_id = ?", (ids["demo"],))

            # 3. Jeder Zustand kommt vor – verloren gemeldet und beide Wege der Aussonderung eingeschlossen.
            zaehlung = Counter(st.status(i) for i in artikel)
            assert set(zaehlung) == set(st.STATUS), zaehlung
            assert any(i["lock_state"] == "verloren" for i in artikel)
            assert any(i["lock_state"] == "gesperrt" for i in artikel)
            # Überfällig ist, was in diesem Jahr noch aussteht (MTW 2 seit gut einem Monat, das Zentrallager seit ein paar
            # Tagen) – nichts, dessen Prüfung über ein Jahr ausgeblieben wäre.
            spaet = [i["next_due_on"] for i in artikel if st.status(i) == "ueberfaellig"]
            assert spaet and min(spaet) >= (bestand.heute() - timedelta(days=60)).isoformat(), sorted(spaet)[:5]
            for i in artikel:
                if st.status(i) == "lebensdauer":
                    assert i["product_id"] == ids["gurt"] and i["retire_by"] <= bestand.heute().isoformat()
            iids = {i["id"] for i in artikel}
            pruefungen = [x for x in db.query("SELECT * FROM mat_inspection") if x["item_id"] in iids]
            aus_pruefung = [x for x in pruefungen if x["kind"] == "aussonderung" and x["basis_inspection_id"]]
            aus_wart = [x for x in pruefungen if x["kind"] == "aussonderung" and not x["basis_inspection_id"]]
            assert aus_pruefung and aus_wart, (aus_pruefung, aus_wart)

            # 4. Die Geschichte: über zwei Jahre, Prüftage und Journal mit ihrem damaligen Datum, Jahresdurchgänge in
            # mehreren Jahren, Reparaturen, Nachkäufe, Verschiebungen, beendete Zuordnungen, Änderungsanträge.
            heute = bestand.heute()
            fertig = [x for x in pruefungen if x["completed_at"]]
            assert len(fertig) > ARTIKEL
            assert min(x["inspected_on"] for x in fertig) < (heute - timedelta(days=600)).isoformat()
            assert all(x["created_at"][:10] <= x["inspected_on"] or x["inspected_on"] == heute.isoformat()
                       for x in fertig if x["kind"] != "aussonderung")
            arten_p = Counter(x["kind"] for x in fertig)
            assert arten_p["eingang"] and arten_p["periodisch"] and arten_p["reparatur"], arten_p
            runden = [r for r in db.query("SELECT * FROM mat_round") if r["folder_id"] in zweige]
            zu = [r for r in runden if r["closed_on"]]
            assert len({r["closed_on"][:4] for r in zu}) >= 2, [r["closed_on"] for r in zu]
            assert all(r["protocol_id"] and r["pdf_path"] for r in zu)
            assert len([r for r in runden if not r["closed_on"]]) == 1
            journal = Counter(e["action"] for e in db.query(
                f"SELECT action FROM mat_audit WHERE entity = 'item' AND entity_id IN ({','.join(map(str, iids))})"))
            assert journal["zugeordnet"] and journal["zuordnung_geloest"] and journal["verschoben"], journal
            assert journal["antrag_gestellt"], journal
            eintraege = db.query(f"SELECT created_at FROM mat_audit WHERE entity = 'item' AND entity_id IN "
                                 f"({','.join(map(str, iids))}) ORDER BY id")
            assert eintraege[0]["created_at"][:10] < (heute - timedelta(days=500)).isoformat()
            antraege = Counter(r["status"] for r in db.query(
                f"SELECT status FROM mat_item_change WHERE item_id IN ({','.join(map(str, iids))})"))
            assert antraege and set(antraege) <= {"offen", "bestaetigt", "abgelehnt", "zurueckgezogen"}, antraege

            # 5. Prüfungen: festgeschrieben mit Protokoll; Prüfer sind DEMO-Konten mit DEMO-Urkunde.
            konten = {u["id"]: u for u in db.query("SELECT * FROM users WHERE email LIKE '%@example.invalid'")}
            assert all(u["name"].startswith("DEMO-") for u in konten.values())
            mails = {u["email"] for u in konten.values()}
            for mail in ("demo-wart-a", "demo-wart-b", "demo-pruefer", "demo-pruefer-2", "demo-pruefer-ns", "demo-extern",
                         "demo-mitglied", "demo-mv", "demo-einsatzkraft-01", "demo-einsatzkraft-02"):
                assert f"{mail}@example.invalid" in mails, mail
            # Modulstufe Material: Mitglied, die Material-Verwaltung Verwaltung, die Einsatzkräfte ab der zweiten keinen.
            for u in konten.values():
                soll = 2 if u["email"].startswith("demo-mv@") else (
                    0 if re.match(r"demo-einsatzkraft-(?!01@)", u["email"]) else 1)
                assert u["recht_material"] == soll and u["recht_karte"] == 0 and u["recht_wiki"] == 0 \
                    and u["recht_verwaltung"] == 0, (u["email"], u["recht_material"])
            for x in fertig:
                kurz = (x["id"], x["kind"], x["result"], x["inspector_name"])
                assert x["locked_at"] and x["protocol_id"] and x["pdf_path"], kurz
                assert sha(os.path.join(tmp, x["pdf_path"])) == x["file_sha256"], kurz
                assert x["inspector_user_id"] in konten, kurz
                if x["kind"] == "aussonderung" and not x["basis_inspection_id"]:      # der Materialwart sondert aus
                    assert konten[x["inspector_user_id"]]["email"].startswith("demo-wart-"), kurz
                else:
                    assert x["inspector_certificate"].startswith("DEMO-"), kurz
                if x["kind"] != "aussonderung":
                    assert x["remarks"] == HINWEIS, kurz
            # Der externe Prüfer hat seine Prüffreigabe erst seit heute: Er prüft nur heute (ein Entwurf im Durchgang).
            extern = {uid for uid, u in konten.items() if u["email"].startswith("demo-extern@")}
            von_extern = [x for x in pruefungen if x["inspector_user_id"] in extern]
            assert von_extern and all(x["inspected_on"] == heute.isoformat() for x in von_extern), von_extern
            entwuerfe = [x for x in pruefungen if not x["completed_at"]]
            assert entwuerfe and all(x["round_id"] for x in entwuerfe)
            befunde = db.query("SELECT r.* FROM mat_inspection_result r JOIN mat_inspection x ON x.id = r.inspection_id "
                               f"WHERE x.item_id IN ({','.join(str(i) for i in iids)})")
            maengel = [b for b in befunde if b["finding"] == "mangel"]
            assert maengel and all(b["photo"] and b["note"] == HINWEIS for b in maengel)
            assert all(b["note"] == HINWEIS for b in befunde if b["finding"] == "nicht_zutreffend")
            # Soll beachtet: Ja/Nein ohne Mangel steht auf dem Soll; Textpunkte tragen den DEMO-Platzhalter.
            assert all(b["value"] == b["expected_value"] for b in befunde if b["editor"] == "yesno" and b["finding"] == "ok")
            assert all(b["value"] == HINWEIS for b in befunde if b["editor"] == "text")
            offen = next(r for r in runden if not r["closed_on"])
            x = db.query("SELECT SUM(completed_at IS NOT NULL) AS fertig, SUM(completed_at IS NULL) AS entwurf, "
                         "(SELECT COUNT(*) FROM mat_round_item WHERE round_id = ? AND excluded_reason LIKE 'DEMO%') "
                         "AS aus FROM mat_inspection WHERE round_id = ?", (offen["id"], offen["id"]), one=True)
            assert x["fertig"] and x["entwurf"] == 1 and x["aus"] >= 1, x
            assert db.query("SELECT COUNT(*) AS n FROM mat_round_item WHERE round_id = ?", (offen["id"],),
                            one=True)["n"] > x["fertig"] + 2, offen                  # der Rest ist offen
            zugeordnet = [i for i in artikel if i["assigned_user_id"]]
            assert zugeordnet and all(i["assigned_user_id"] in konten for i in zugeordnet)

            # 6. Journal ohne Konto nur unter „Beispielbestand“ (ausgenommen, was das System selbst einträgt).
            namen = {e["user_name"] for e in db.query("SELECT user_name FROM mat_audit WHERE id > ? AND user_id IS NULL",
                                                      (journal_vor,))}
            assert namen <= {"Beispielbestand", "System"}, namen

            # 7. DEMO-Kennzeichnung: jeder Artikel des Beispielbestands, der echte daneben nicht.
            assert all(bestand.ist_demo(i["id"]) for i in artikel) and not bestand.ist_demo(echt)
            ein = next(i for i in artikel if i["lock_state"] == "frei" and i["last_inspected_on"])
            assert lebenslauf.daten(ein["id"])["dokument"]["demo"] and not lebenslauf.daten(echt)["dokument"]["demo"]
            steckbrief = db.query(globalsuche._STECKBRIEF_SQL + "WHERE i.id IN (?, ?)", (ein["id"], echt))
            assert {s["id"]: globalsuche.steckbrief(s)["demo"] for s in steckbrief} == {ein["id"]: True, echt: False}
            for g in gls:
                zeilen = export.artikel_csv(g["id"])[0].decode("utf-8-sig").splitlines()
                assert zeilen[0].endswith(";DEMO") and all(z.endswith(";ja") for z in zeilen[1:]), zeilen[:3]
            assert export.artikel_csv(echt_gl)[0].decode("utf-8-sig").splitlines()[1].endswith(";nein")
            protokoll = next(x for x in fertig if x["item_id"] == ein["id"])
            echt_protokoll = db.query("SELECT pdf_path FROM mat_inspection WHERE item_id = ?", (echt,), one=True)
            lager = db.query("SELECT id FROM mat_folder WHERE name = 'DEMO-Zentrallager' AND parent_id = ?", (fl["id"],),
                             one=True)["id"]
            persoenlich = db.query("SELECT id FROM mat_folder WHERE name = 'DEMO-Einsatzkraft 01'", one=True)["id"]
            # Eine Einsatzkraft ohne Modulzugang, der Ausrüstung zugeordnet ist.
            ohne = db.query("SELECT u.email FROM users u WHERE u.email LIKE 'demo-einsatzkraft-%' AND u.recht_material = 0 "
                            "AND EXISTS (SELECT 1 FROM mat_item i WHERE i.assigned_user_id = u.id AND i.lock_state <> "
                            "'ausgesondert') ORDER BY u.email LIMIT 1", one=True)["email"]
        assert HINWEIS in protokoll_text(app, protokoll["pdf_path"])
        assert HINWEIS in protokoll_text(app, zu[0]["pdf_path"])
        assert "DEMO" not in protokoll_text(app, echt_protokoll["pdf_path"])
        adm = k["adm"]
        assert adm.get(f"/api/material/artikel/{ein['id']}").json["artikel"]["demo"] is True
        assert adm.get(f"/api/material/artikel/{echt}").json["artikel"]["demo"] is False
        liste = adm.get(f"/api/material/ordner/{ein['folder_id']}").json["ordner"]["artikel"]
        assert ein["id"] in {a["id"] for a in liste} and all(a["demo"] for a in liste)
        pruefung = adm.get(f"/api/material/pruefungen/{protokoll['id']}").json["pruefung"]
        assert pruefung["artikel"]["demo"] is True and pruefung["produkt"]["demo"] is False
        # Auch ein Ordner ohne Kennzeichen, den jemand über die Oberfläche in einer DEMO-Gliederung anlegt, ist DEMO.
        r = adm.post("/api/material/ordner", json={"name": "Neu über die Oberfläche", "kind": "sonstiges",
                                                   "parent_id": fl["id"]})
        assert r.status_code == 201 and not r.json["ordner"]["demo"], r.get_json()
        neu = neuer_artikel(adm, ids["hms"], r.json["ordner"]["id"], serial_no="OBERFLAECHE-1")
        assert neu["demo"] is True, neu

        # 8. Konten: Freigaben „Beispielbestand“, der Materialwart sieht seine Gliederung, nicht die andere.
        passwoerter = dict(re.findall(r"(\S+@example\.invalid)\s.*?Passwort: (\S+)", aus))
        assert len(passwoerter) == 9, aus[-3000:]                 # die Einsatzkräfte ab 02 mit gemeinsamem Passwort
        gemeinsam = re.search(r"demo-einsatzkraft-02 bis -\d+@example\.invalid: \d+ Einsatzkräfte .*Passwort wie oben: "
                              r"(\S+)", aus)
        assert gemeinsam and gemeinsam.group(1) == passwoerter["demo-einsatzkraft-01@example.invalid"], aus[-2000:]
        from test_material import anmelden
        wart = anmelden(app, "demo-wart-a@example.invalid", passwoerter["demo-wart-a@example.invalid"])
        assert wart.get(f"/api/material/ordner/{fl['id']}").status_code == 200
        assert wart.get(f"/api/material/ordner/{ns['id']}").status_code == 404
        # Die DEMO-Material-Verwaltung sieht beide Gliederungen, ohne Plattform-Verwaltung zu sein.
        mv = anmelden(app, "demo-mv@example.invalid", passwoerter["demo-mv@example.invalid"])
        assert mv.get(f"/api/material/ordner/{fl['id']}").status_code == 200
        assert mv.get(f"/api/material/ordner/{ns['id']}").status_code == 200
        direkt = adm.get(f"/api/material/ordner/{fl['id']}/freigaben").json["direkt"]
        assert {x["recht"] for x in direkt} == {"verwalten", "lesen", "pruefen"}, direkt
        assert {x["vergeben_von"] for x in direkt} == {"Beispielbestand"}, direkt
        # Befristet ist eine Prüffreigabe nur für Externe: die Prüfer dauerhaft (mit lesen dort), der externe Prüfer
        # 30 Tage im Zentrallager.
        pruef = sorted((x["konto"]["name"], x["bis"], x["grundrecht_dort"], x["wirkt"]) for x in direkt
                       if x["recht"] == "pruefen")
        assert pruef == [("DEMO-Prüfer", None, True, True), ("DEMO-Prüferin 2", None, True, True)], pruef
        extern = [x for x in adm.get(f"/api/material/ordner/{lager}/freigaben").json["direkt"]
                  if x["recht"] == "pruefen"]
        assert [(x["konto"]["name"], x["laeuft_ab_in_tagen"]) for x in extern] == [("DEMO-Prüfer extern", 30)], extern
        assert extern[0]["bis"] is not None and extern[0]["wirkt"], extern
        # Einsatzkraft 01 liest ihren persönlichen Ordner (mit zugeordneter Ausrüstung), sonst nichts; die übrigen haben
        # keinen Modulzugang und sehen „Meine PSA“. Der Bericht sagt das.
        eins = anmelden(app, "demo-einsatzkraft-01@example.invalid", passwoerter["demo-einsatzkraft-01@example.invalid"])
        assert eins.get("/material").status_code == 200
        r = eins.get(f"/api/material/ordner/{persoenlich}")
        assert r.status_code == 200 and r.json["ordner"]["artikel"], r.get_json()
        assert all(a["zugeordnet_name"] == "DEMO-Einsatzkraft 01" for a in r.json["ordner"]["artikel"]
                   if a["lock_state"] != "ausgesondert"), r.json["ordner"]["artikel"]
        assert eins.get(f"/api/material/ordner/{fl['id']}").status_code == 404
        zwei = anmelden(app, ohne, gemeinsam.group(1))
        # Ohne Modulzugang, aber mit zugeordneter PSA: „Material“ führt zu „Meine PSA“ (Phase 3 · L1), sonst 403.
        r = zwei.get("/material")
        assert r.status_code == 302 and r.headers["Location"].endswith("/material/meine-psa"), r.status_code
        assert zwei.get("/material/meine-psa").status_code == 200 and zwei.get("/api/material/meine-psa").json["artikel"]
        r = zwei.get("/material/bestand")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.get_data(as_text=True)
        assert re.search(r"demo-einsatzkraft-01@example\.invalid .*\(liest ihren persönlichen Ordner\)", aus)

        # 9. Ein zweiter Lauf legt nichts an.
        vorher, katalog_jetzt = bestand_stand(app), katalog_stand(app)
        zweit, code = laufen("--beispielbestand")
        assert code == 0 and "schon da" in zweit and "Passwort" not in zweit, zweit
        assert bestand_stand(app) == vorher
        assert katalog_stand(app) == katalog_jetzt
    print(f"Beispielbestand bestanden ({ARTIKEL} Artikel in {dauer:.0f} s).")


def test_formulare():
    """Formulare für echte Kategorien ohne wirksames Formular: nach dem Petzl-Prüfbericht, wo die Datei die Kategorie
    nach ihrem Namen kennt – genau ihre Punkte (Text wörtlich, Gruppe, Art, Pflicht, Soll, kritisch), DEMO-Kennzeichen,
    aktiv –, sonst ein Platzhalter an der obersten Kategorie ohne Formular. Echte Formulare (aktiv und inaktiv) bleiben,
    der Export enthält keins der DEMO-Formulare, ein zweiter Lauf legt nichts an; fehlt die Datei, gibt es nur
    Platzhalter. Kategorien und Produkte sind Platzhalter."""
    spec = importlib.util.spec_from_file_location("material_beispielbestand_formulare",
                                                  os.path.join(REPO, "scripts", "material_beispielbestand.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    vorlagen, fehlt = modul.petzl_vorlagen()
    assert not fehlt and {"Seilrollen", "Gurte", "Karabiner"} <= set(vorlagen), (fehlt, sorted(vorlagen))
    with open(PETZL, encoding="utf-8") as fh:
        roh = json.load(fh)
    katalogdatei = {
        "format": "stroemis-material-katalog", "version": 1,
        "kategorien": [
            {"name": "Testbaum", "unterkategorien": [
                {"name": "Seilrollen", "materialart": "metall_hardware", "intervall_monate": 12},
                {"name": "Gurte", "materialart": "sonstiges", "intervall_monate": 12},
                {"name": "Sonderbau (Test)", "materialart": "sonstiges", "intervall_monate": 12}]},
            {"name": "Karabiner", "materialart": "metall_hardware", "intervall_monate": 12}],
        "produkte": [{"kategorie": ["Testbaum", "Seilrollen"], "hersteller": "Testwerk", "modell": "Rolle Delta",
                      "artikelnummer": "RD-1", "materialart": "metall_hardware"}],
        "formulare": [
            {"kategorie": ["Testbaum", "Gurte"], "titel": "Gurte (Test, inaktiv)", "aktivieren": False,
             "punkte": [{"text": "Testpunkt Gurt", "art": "yesno", "soll": "ja"}]},
            {"kategorie": ["Karabiner"], "titel": "Karabiner (Test)",
             "punkte": [{"text": "Testpunkt Karabiner", "art": "yesno", "soll": "ja"}]}]}
    for mit_datei in (True, False):
        with tempfile.TemporaryDirectory() as tmp:
            app = make_app(tmp)
            with app.app_context():
                from flask import g

                from app import db
                from app.material.services import importer, katalog, katalog_export
                g.mat_akteur = "Test"
                assert not importer.importieren(katalogdatei, quelle="Test")["fehler"]
                kid = {k["name"]: k["id"] for k in db.query("SELECT id, name FROM mat_category")}
                echt_vorher = db.query("SELECT * FROM mat_form WHERE demo = 0 ORDER BY id")
                petzl, platzhalter, ohne = modul.formulare(vorlagen if mit_datei else {})
                assert petzl == (["Seilrollen"] if mit_datei else []), petzl
                assert platzhalter == ["Testbaum"] and ohne == [], (platzhalter, ohne)
                assert db.query("SELECT * FROM mat_form WHERE demo = 0 ORDER BY id") == echt_vorher
                neu = {f["category_id"]: f for f in db.query("SELECT * FROM mat_form WHERE demo = 1")}
                assert set(neu) == ({kid["Seilrollen"], kid["Testbaum"]} if mit_datei else {kid["Testbaum"]}), neu
                assert all(f["active"] for f in neu.values())
                if mit_datei:
                    f = neu[kid["Seilrollen"]]
                    v = roh["Seilrollen"]
                    assert f["title"] == f"DEMO – Prüfformular nach Petzl-Prüfbericht ({v['bezugsprodukt']}) – Seilrollen"
                    punkte = katalog.punkte(f["id"])
                    assert [(p["label"], p["group_name"], p["editor"], bool(p["mandatory"]), p["expected_value"],
                             bool(p["is_critical"])) for p in punkte] == [
                        (p["text"], p["gruppe"], p["art_app"], p["pflicht"], p["soll"], p["kritisch"])
                        for p in v["punkte"]], punkte
                    assert katalog.formular_fuer_produkt(
                        db.query("SELECT id FROM mat_product WHERE model = 'Rolle Delta'", one=True)["id"])["id"] == f["id"]
                platz = katalog.punkte(neu[kid["Testbaum"]]["id"])
                assert [p["editor"] for p in platz] == ["yesno", "text", "number"], platz
                # Der Export nimmt die echten Formulare mit (auch das inaktive), keines der DEMO-Formulare.
                daten, _, _ = katalog_export.sammeln(mit_dateien=False)
                assert sorted(x["titel"] for x in daten["formulare"]) == ["Gurte (Test, inaktiv)", "Karabiner (Test)"]
                # Zweiter Lauf: nichts dazu.
                anzahl = db.query("SELECT COUNT(*) AS n FROM mat_form", one=True)["n"]
                assert modul.formulare(vorlagen if mit_datei else {}) == ([], [], [])
                assert db.query("SELECT COUNT(*) AS n FROM mat_form", one=True)["n"] == anzahl
    # Jede Petzl-Vorlage lässt sich so anlegen (Titel, Gruppen und Texte in den Grenzen der App).
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        with app.app_context():
            from flask import g

            from app.material.services import katalog
            g.mat_akteur = "Test"
            for name, v in vorlagen.items():
                kid = katalog.kategorie_anlegen({"name": name})
                fid = katalog.formular_anlegen({"kategorie_id": kid, "titel": modul.petzl_titel(name, v),
                                                "punkte": modul.petzl_punkte(v)}, demo=True)
                assert len(katalog.punkte(fid)) == len(v["punkte"]), name
                assert len(modul.petzl_titel(name, v)) <= 160
    # Fehlt die Datei: nur Platzhalter, mit Grund.
    assert modul.petzl_vorlagen(os.path.join(REPO, "fehlt.json"))[0] == {}
    print("Formulare nach Petzl-Prüfbericht und Platzhalter bestanden.")


def test_abgebrochener_lauf():
    """Abbruch mitten im Lauf (abgerissene Verbindung, SIGHUP – wie beim SSH-Abbruch während docker exec): Der Vorgang in
    Arbeit rollt samt Protokolldateien zurück, die fertigen bleiben, der Hinweis erscheint, der Merker fehlt, die Uhr
    gilt wieder. Der nächste Lauf meldet „unvollständig“ mit Rückgabewert 1 und legt nichts an."""
    import signal
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        platzhalterkatalog(k)

        # Abbruch mitten in der ersten Gliederung: Ihre Transaktion rollt zurück, es gibt nichts – und der Hinweis
        # sagt das, statt von einem unvollständigen Bestand zu sprechen.
        from app.material.services import bestand
        anlegen = bestand.ordner_anlegen

        def ordner_anlegen(d, demo=False):
            fid = anlegen(d, demo)
            if d.get("parent_id"):
                os.kill(os.getpid(), signal.SIGHUP)
            return fid

        vorher = bestand_stand(app)
        bestand.ordner_anlegen = ordner_anlegen
        try:
            aus, code = laufen("--beispielbestand", "--artikel", "6")
        finally:
            bestand.ordner_anlegen = anlegen
        assert code == "unterbrochen" and "Unterbrochen. Nichts angelegt" in aus, (code, aus[-2000:])
        assert bestand_stand(app) == vorher

        stand = {"n": 0}
        from app.material.services import pruefung as pruefdienst
        abschliessen = pruefdienst.abschliessen

        def abreissen(*a, **kw):
            ergebnis = abschliessen(*a, **kw)       # ab der dritten Prüfung: Protokoll geschrieben, Transaktion noch
            stand["n"] += 1                         # offen – jetzt reißt die Verbindung ab
            if stand["n"] >= 3:
                os.kill(os.getpid(), signal.SIGHUP)
            return ergebnis

        alt = signal.getsignal(signal.SIGHUP)
        pruefdienst.abschliessen = abreissen
        try:
            aus, code = laufen("--beispielbestand", "--artikel", "6")
        finally:
            pruefdienst.abschliessen = abschliessen
        assert code == "unterbrochen", (code, aus[-2000:])
        assert "Unterbrochen." in aus and "unvollständig" in aus and "zurückgesetzten dev-Datenbank" in aus, aus[-2000:]
        assert signal.getsignal(signal.SIGHUP) is alt                    # das Skript stellt die Signale zurück
        with app.app_context():
            from app import db
            from app.material.services import ZONE, heute
            assert heute() == datetime.now(ZONE).date()                       # die echte Uhr gilt wieder
            assert not db.query("SELECT 1 FROM mat_meta WHERE schluessel = 'beispielbestand'")
            # Zwei Prüfungen sind fertig, die dritte rollte samt Protokoll zurück.
            assert db.query("SELECT COUNT(*) AS n FROM mat_inspection WHERE completed_at IS NOT NULL",
                            one=True)["n"] == 2
            pfade = {r["pdf_path"] for r in db.query("SELECT pdf_path FROM mat_inspection WHERE pdf_path IS NOT NULL "
                                                     "UNION SELECT pdf_path FROM mat_round WHERE pdf_path IS NOT NULL")}
        dateien = {os.path.relpath(os.path.join(w, f), tmp) for w, _, fs in os.walk(os.path.join(tmp, "pdf"))
                   for f in fs}
        assert dateien == pfade, dateien ^ pfade                         # keine verwaiste Protokolldatei
        vorher = bestand_stand(app)
        zweit, code = laufen("--beispielbestand")
        assert code == 1 and "unvollständig" in zweit and "schon da" not in zweit, (code, zweit)
        assert bestand_stand(app) == vorher
    print("Abgebrochener Lauf bestanden.")


if __name__ == "__main__":
    test_ohne_schalter()
    test_ohne_echte_produkte()
    test_demo_grenze_beim_verschieben()
    test_formulare()
    test_beispielbestand()
    test_abgebrochener_lauf()
