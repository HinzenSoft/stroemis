"""Beispielbestand (scripts/material_beispielbestand.py):  python tests/test_material_beispielbestand.py  oder  pytest …

Ein Testkatalog mit offensichtlichen Platzhaltern wie in den anderen Tests (echte Produkte ohne DEMO-Kennzeichen: ein
textiles mit Lebensdauer und spezifischem Formular, ein Metallprodukt mit generischem Formular, eines ohne Formular;
dazu ein Produktbild, ein Dokument und ein DEMO-Teil). Der Generator läuft mit kleiner Zahl: Der Katalog bleibt Zeile
für Zeile und Datei für Datei gleich – auch sein Export im Format 2 –, jeder Zustand kommt vor, jede abgeschlossene
Prüfung ist festgeschrieben und hat ihr Protokoll, und die DEMO-Kennzeichnung greift an Artikel, Liste, Protokoll,
Sammelprotokoll, Lebenslauf, CSV und Steckbrief – auch für echte Produkte, weil ihre Heimat ein DEMO-Ordner ist
(bestand.demo_sql). Ein zweiter Lauf legt nichts an, ohne Schalter endet das Skript mit 2, ohne echte Produkte mit 1;
ein abgebrochener Lauf (Strg-C oder SIGHUP) hinterlässt einen Teilbestand, den der nächste Lauf als unvollständig meldet
(Rückgabewert 1) statt „schon da“. Die Prüferin prüft dauerhaft, nur der externe Prüfer befristet.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, _flach, gliederung, jpeg, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pdf_seiten, pruef_formulare, starten, umgebung)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HINWEIS = "DEMO – nicht für echte Prüfungen"
KATALOG_TABELLEN = ("mat_category", "mat_product", "mat_product_document", "mat_form", "mat_checklist_item",
                    "mat_recall", "mat_product_request")
BESTAND_TABELLEN = ("mat_folder", "mat_item", "mat_inspection", "mat_inspection_result", "mat_round", "mat_round_item",
                    "mat_folder_grant", "mat_audit", "users")
GLIEDERUNGEN = ("DEMO-OG Auental", "DEMO-OG Bachheim", "DEMO-OG Flussstadt")
ARTIKEL = 36


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


def katalog_stand(app):
    """Alles, was zum Katalog gehört: jede Zeile jeder Katalogtabelle, der Export im Format 2 (katalog.json ohne
    Zeitstempel, Prüfsummen der Dateien im Archiv) und die Dateien hinter Produktbildern und Dokumenten."""
    with app.app_context():
        from app import db
        from app.material.services import katalog, katalog_export
        tabellen = {t: db.query(f"SELECT * FROM {t} ORDER BY id") for t in KATALOG_TABELLEN}
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
    """Ohne --beispielbestand (oder mit Unbekanntem): Hilfe, Rückgabewert 2; mit der Adresse der Produktion: 1. Beides
    legt nichts an."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        vorher = bestand_stand(app)
        for schalter in ((), ("--artikel", "10"), ("--beispielbestand", "--artikel", "null"), ("--beispiel",)):
            aus, code = laufen(*schalter)
            assert code == 2 and "Abgebrochen" in aus and "--beispielbestand" in aus, (schalter, aus[-300:])
            # Die Hilfe nennt, was danach im Katalog nicht mehr geht.
            assert "seine Materialart nicht mehr" in aus and "Formularversion" in aus, aus[:3000]
        # Mit der Adresse der Produktion legt das Skript nichts an – auch mit Schalter.
        for adresse in ("https://strömis.de", "https://www.xn--strmis-yxa.de/"):
            aus, code = laufen("--beispielbestand", adresse=adresse)
            assert code == 1 and "Adresse der Produktion" in aus, aus[-300:]
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

        t0 = time.time()
        aus, code = laufen("--beispielbestand", "--artikel", str(ARTIKEL))
        dauer = time.time() - t0
        assert code == 0, aus[-3000:]
        assert "Beispielbestand angelegt" in aus and "Kommt nicht vor" not in aus, aus[-3000:]
        assert not re.search(r"^Hinweise:", aus, re.M), aus[-2000:]          # nichts übersprungen
        # Der Bericht nennt die Folge für die Katalogpflege: Produkte mit Artikeln bleiben, ihre Materialart steht fest.
        assert "Jetzt mit Artikeln: 3 Produkte" in aus, aus[-2000:]
        r = k["katalog"].delete(f"/api/material/produkte/{ids['helm']}", headers=H)
        assert r.status_code == 409, r.get_json()

        # 1. Der Katalog bleibt unverändert – Zeilen, Export und Dateien.
        nachher = katalog_stand(app)
        for teil in ("export", "export_dateien", "dateien"):
            assert nachher[teil] == katalog_vorher[teil], teil
        for t in KATALOG_TABELLEN:
            assert nachher["tabellen"][t] == katalog_vorher["tabellen"][t], t

        with app.app_context():
            from app import db
            from app.material.services import bestand, export, globalsuche, lebenslauf
            from app.material.services import status as st
            gls = db.query(f"SELECT * FROM mat_folder WHERE parent_id IS NULL AND name IN ({','.join('?' * 3)})",
                           GLIEDERUNGEN)
            assert len(gls) == 3 and all(g["demo"] and g["kind"] == "gliederung" for g in gls), gls
            zweige = set()
            for g in gls:
                zweige |= bestand.unterbaum(g["id"])
            ordner = db.query(f"SELECT * FROM mat_folder WHERE id IN ({','.join(str(x) for x in zweige)})")
            assert all(o["demo"] for o in ordner)
            assert all(o["name"].startswith("DEMO-") or o["system_kind"] for o in ordner), [o["name"] for o in ordner]
            assert all(not o["interval_months"] for o in ordner)
            artikel = [i for i in db.query("SELECT * FROM mat_item") if bestand.heimat(i) in zweige]
            assert len(artikel) == ARTIKEL, len(artikel)

            # 2. Nur echte Produkte, alle davon; DEMO-Bestandsangaben.
            assert {i["product_id"] for i in artikel} == {ids["gurt"], ids["hms"], ids["helm"]}
            assert all(i["serial_no"].startswith("DEMO-") and i["notes"] == HINWEIS for i in artikel)
            assert not db.query("SELECT 1 FROM mat_item WHERE product_id = ?", (ids["demo"],))

            # 3. Jeder Zustand kommt vor – verloren gemeldet und beide Wege der Aussonderung eingeschlossen.
            zaehlung = Counter(st.status(i) for i in artikel)
            assert set(zaehlung) == set(st.STATUS), zaehlung
            assert any(i["lock_state"] == "verloren" for i in artikel)
            for i in artikel:
                if st.status(i) == "lebensdauer":
                    assert i["product_id"] == ids["gurt"] and i["retire_by"] <= bestand.heute().isoformat()
            iids = {i["id"] for i in artikel}
            pruefungen = [x for x in db.query("SELECT * FROM mat_inspection") if x["item_id"] in iids]
            aus_pruefung = [x for x in pruefungen if x["kind"] == "aussonderung" and x["basis_inspection_id"]]
            aus_wart = [x for x in pruefungen if x["kind"] == "aussonderung" and not x["basis_inspection_id"]]
            assert aus_pruefung and aus_wart, (aus_pruefung, aus_wart)
            # Ohne aktives Formular keine Prüfung: Helm Gamma bleibt „neu“.
            helme = [i for i in artikel if i["product_id"] == ids["helm"]]
            assert helme and all(st.status(i) == "neu" for i in helme)
            assert not any(x["item_id"] in {i["id"] for i in helme} for x in pruefungen)

            # 4. Prüfungen: zurückdatiert, festgeschrieben mit Protokoll; Prüfer sind DEMO-Konten mit DEMO-Urkunde.
            konten = {u["id"]: u for u in db.query("SELECT * FROM users WHERE email LIKE '%@example.invalid'")}
            assert len(konten) == 18 and all(u["name"].startswith("DEMO-") for u in konten.values())
            # Modulstufe Material: Mitglied – nur die zweite Einsatzkraft je Gliederung hat keinen Zugriff.
            assert all(u["recht_material"] == (0 if re.search(r"^demo-einsatzkraft-\w+-2@", u["email"]) else 1)
                       and u["recht_karte"] == 0 and u["recht_wiki"] == 0 and u["recht_verwaltung"] == 0
                       for u in konten.values()), {u["email"]: u["recht_material"] for u in konten.values()}
            fertig = [x for x in pruefungen if x["completed_at"]]
            assert len(fertig) > ARTIKEL and min(x["inspected_on"] for x in fertig) < bestand.heute().isoformat()
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
            # Der externe Prüfer hat seine Prüffreigabe erst seit heute: Er prüft nur heute, die Geschichte die Prüferin.
            extern = {uid for uid, u in konten.items() if u["email"].startswith("demo-extern-")}
            von_extern = [x for x in pruefungen if x["inspector_user_id"] in extern]
            heute = bestand.heute().isoformat()
            assert von_extern and all((x["inspected_on"] or heute) == heute for x in von_extern), \
                [(x["id"], x["inspected_on"]) for x in von_extern]
            entwuerfe = [x for x in pruefungen if not x["completed_at"]]
            assert entwuerfe and all(x["round_id"] for x in entwuerfe)
            befunde = db.query("SELECT r.* FROM mat_inspection_result r JOIN mat_inspection x ON x.id = r.inspection_id "
                               f"WHERE x.item_id IN ({','.join(str(i) for i in iids)})")
            maengel = [b for b in befunde if b["finding"] == "mangel"]
            assert maengel and all(b["photo"] and b["note"] == HINWEIS for b in maengel)
            assert all(b["note"] == HINWEIS for b in befunde if b["finding"] == "nicht_zutreffend")
            # Soll beachtet: Ja/Nein ohne Mangel steht auf dem Soll.
            assert all(b["value"] == b["expected_value"] for b in befunde if b["editor"] == "yesno" and b["finding"] == "ok")

            # 5. Durchgänge je Gliederung: einer abgeschlossen mit Sammelprotokoll, einer offen; Zuordnungen an DEMO-Personen.
            runden = [r for r in db.query("SELECT * FROM mat_round") if r["folder_id"] in zweige]
            zu = [r for r in runden if r["closed_on"]]
            assert len(zu) == 3 and len(runden) == 6 and all(r["protocol_id"] and r["pdf_path"] for r in zu)
            for r in runden:
                x = db.query("SELECT SUM(completed_at IS NOT NULL) AS fertig, SUM(completed_at IS NULL) AS entwurf, "
                             "(SELECT COUNT(*) FROM mat_round_item WHERE round_id = ? AND excluded_reason LIKE 'DEMO%') "
                             "AS aus FROM mat_inspection WHERE round_id = ?", (r["id"], r["id"]), one=True)
                assert x["fertig"], r                                           # geprüft – im offenen nur teilweise
                if not r["closed_on"]:
                    assert x["entwurf"] == 1 and x["aus"] == 1, (r, x)
                    assert db.query("SELECT COUNT(*) AS n FROM mat_round_item WHERE round_id = ?", (r["id"],),
                                    one=True)["n"] > x["fertig"] + 2, r          # der Rest ist offen
            zugeordnet = [i for i in artikel if i["assigned_user_id"]]
            assert zugeordnet and all(i["assigned_user_id"] in konten for i in zugeordnet)

            # 6. Journal unter „Beispielbestand“ (ausgenommen, was das System selbst einträgt).
            namen = {e["user_name"] for e in db.query("SELECT user_name FROM mat_audit WHERE created_at >= ? AND user_id "
                                                      "IS NULL", (min(x["created_at"] for x in pruefungen),))}
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
                                                   "parent_id": gls[0]["id"]})
        assert r.status_code == 201 and not r.json["ordner"]["demo"], r.get_json()
        neu = neuer_artikel(adm, ids["hms"], r.json["ordner"]["id"], serial_no="OBERFLAECHE-1")
        assert neu["demo"] is True, neu

        # 8. Konten: Freigaben „Beispielbestand“, der Materialwart sieht seine Gliederung, nicht die anderen.
        passwoerter = dict(re.findall(r"(\S+@example\.invalid)\s.*?Passwort: (\S+)", aus))
        assert len(passwoerter) == 18, aus[-3000:]
        from test_material import anmelden
        wart = anmelden(app, "demo-wart-au@example.invalid", passwoerter["demo-wart-au@example.invalid"])
        au = next(g for g in gls if g["name"] == "DEMO-OG Auental")
        bh = next(g for g in gls if g["name"] == "DEMO-OG Bachheim")
        assert wart.get(f"/api/material/ordner/{au['id']}").status_code == 200
        assert wart.get(f"/api/material/ordner/{bh['id']}").status_code == 404
        direkt = adm.get(f"/api/material/ordner/{au['id']}/freigaben").json["direkt"]
        assert {x["recht"] for x in direkt} == {"verwalten", "lesen", "pruefen"}, direkt
        assert {x["vergeben_von"] for x in direkt} == {"Beispielbestand"}, direkt
        # Befristet ist eine Prüffreigabe nur für Externe: die Prüferin dauerhaft (mit lesen dort), der externe Prüfer
        # 30 Tage im Lager.
        pruef = [x for x in direkt if x["recht"] == "pruefen"]
        assert [(x["konto"]["name"], x["bis"], x["grundrecht_dort"], x["wirkt"]) for x in pruef] == [
            ("DEMO-Prüferin Auental", None, True, True)], pruef
        with app.app_context():
            from app import db
            lager = db.query("SELECT id FROM mat_folder WHERE name = 'DEMO-Lager' AND parent_id = ?", (au["id"],),
                             one=True)["id"]
        extern = [x for x in adm.get(f"/api/material/ordner/{lager}/freigaben").json["direkt"]
                  if x["recht"] == "pruefen"]
        assert [(x["konto"]["name"], x["laeuft_ab_in_tagen"]) for x in extern] == [("DEMO-Prüfer extern Auental", 30)], \
            extern
        assert extern[0]["bis"] is not None and extern[0]["wirkt"], extern
        # Einsatzkraft 1 liest ihren persönlichen Ordner (mit zugeordneter Ausrüstung), sonst nichts; Einsatzkraft 2 hat
        # keinen Modulzugang und liest „nicht freigeschaltet“. Der Bericht sagt das an beiden Konten.
        with app.app_context():
            from app import db
            persoenlich = db.query("SELECT id FROM mat_folder WHERE name = 'DEMO-Einsatzkraft Auental 1'", one=True)["id"]
        eins = anmelden(app, "demo-einsatzkraft-au-1@example.invalid",
                        passwoerter["demo-einsatzkraft-au-1@example.invalid"])
        assert eins.get("/material").status_code == 200
        r = eins.get(f"/api/material/ordner/{persoenlich}")
        assert r.status_code == 200 and r.json["ordner"]["artikel"], r.get_json()
        assert all(a["zugeordnet_name"] == "DEMO-Einsatzkraft Auental 1" for a in r.json["ordner"]["artikel"]
                   if a["lock_state"] != "ausgesondert"), r.json["ordner"]["artikel"]
        assert eins.get(f"/api/material/ordner/{au['id']}").status_code == 404
        zwei = anmelden(app, "demo-einsatzkraft-au-2@example.invalid",
                        passwoerter["demo-einsatzkraft-au-2@example.invalid"])
        r = zwei.get("/material")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.get_data(as_text=True)
        assert re.search(r"demo-einsatzkraft-au-1@example\.invalid .*\(liest ihren persönlichen Ordner\)", aus)
        assert re.search(r"demo-einsatzkraft-au-2@example\.invalid .*\(ohne Modulzugang", aus)

        # 9. Ein zweiter Lauf legt nichts an.
        vorher = bestand_stand(app)
        zweit, code = laufen("--beispielbestand")
        assert code == 0 and "schon da" in zweit and "Passwort" not in zweit, zweit
        assert bestand_stand(app) == vorher
        assert katalog_stand(app) == nachher
    print(f"Beispielbestand bestanden ({ARTIKEL} Artikel in {dauer:.0f} s).")


def test_abgebrochener_lauf():
    """Abbruch mitten im Lauf (abgerissene Verbindung, SIGHUP – wie beim SSH-Abbruch während docker exec): Der Artikel in
    Arbeit rollt samt Protokolldateien zurück, die fertigen bleiben, der Hinweis erscheint, der Merker fehlt. Der nächste
    Lauf meldet „unvollständig“ mit Rückgabewert 1 und legt nichts an – vorher sagte er „schon da“ mit 0."""
    import signal
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        platzhalterkatalog(k)

        stand = {}

        def abreissen(modul):
            anlegen, pruefen = modul.Beispielbestand.artikel_anlegen, modul.Beispielbestand.pruefen

            def artikel_anlegen(self, plan):
                stand["nr"] = plan["nr"]
                return anlegen(self, plan)

            def pruefen_dann_abreissen(self, *a, **kw):
                ergebnis = pruefen(self, *a, **kw)      # ab dem dritten Artikel: Protokoll geschrieben, Transaktion
                if stand["nr"] >= 3:                    # noch offen – jetzt reißt die Verbindung ab
                    os.kill(os.getpid(), signal.SIGHUP)
                return ergebnis
            modul.Beispielbestand.artikel_anlegen = artikel_anlegen
            modul.Beispielbestand.pruefen = pruefen_dann_abreissen

        alt = signal.getsignal(signal.SIGHUP)
        aus, code = laufen("--beispielbestand", "--artikel", "6", anpassen=abreissen)
        assert code == "unterbrochen", (code, aus[-2000:])
        assert "Unterbrochen." in aus and "unvollständig" in aus and "zurückgesetzten dev-Datenbank" in aus, aus[-2000:]
        assert signal.getsignal(signal.SIGHUP) is alt                    # das Skript stellt die Signale zurück
        with app.app_context():
            from app import db
            assert not db.query("SELECT 1 FROM mat_meta WHERE schluessel = 'beispielbestand'")
            artikel = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE serial_no LIKE 'DEMO-%'", one=True)["n"]
            assert stand["nr"] >= 3 and artikel == stand["nr"] - 1, (stand, artikel)
            assert not db.query("SELECT 1 FROM mat_round")
            pfade = {r["pdf_path"] for r in db.query("SELECT pdf_path FROM mat_inspection WHERE pdf_path IS NOT NULL")}
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
    test_beispielbestand()
    test_abgebrochener_lauf()
