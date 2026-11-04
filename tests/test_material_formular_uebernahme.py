"""Prüfformular eines anderen Produkts übernehmen (Schritt 35, Wunsch vom 04.11.2026):
python tests/test_material_formular_uebernahme.py  oder  pytest tests/test_material_formular_uebernahme.py

Produkt B verweist auf Produkt A (mat_product.formular_von): Für B gilt immer das aktive spezifische Formular von A, mit
jeder neuen Version dort; fällt es weg, gilt das generische der Kategorie. Geprüft: Auflösung, Ketten, Selbstverweis,
DEMO-Mischung (Dienst und Trigger), Länge, Rechte, Journal, eigenes Formular von B, Löschen der Quelle, Prüfung und
Protokoll an einem Artikel von B, Katalog-Export/-Import (mit und ohne Quelle, null löst), Migration 34 → 35 und die
Oberfläche statisch. Nachbesserung nach der Sicherheitsprüfung vom 04.11.2026 (Schritt 36): Quelle mit benutzter
Formularversion (Befund 2), Rennen Aktivieren ↔ Übernehmen (Befund 3), DEMO-Regel über die Kategorie (Befund 4, Hinweis 1)
und Migration 35 → 36. Alle Namen, Hersteller und Prüfpunkte hier sind erfundene Platzhalter."""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (H, abschluss, anmelden, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pdf_seiten, protokoll_zeile, starten, umgebung)
from test_material_katalog import exportieren, importieren, katalogjson, umschreiben  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "/api/material"


def trigger_36():
    """Die Trigger aus Schritt 36 – die drei aus Schritt 35 unter demselben Namen und die neuen."""
    from app.material import models
    return [x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.TRIGGER_36]


def formular(kp, ziel, titel, punkte, aktiv=True):
    r = kp.post(f"{API}/formulare", json=dict(ziel, titel=titel, punkte=punkte))
    assert r.status_code == 201, r.get_json()
    fid = r.json["formular"]["id"]
    if aktiv:
        assert kp.post(f"{API}/formulare/{fid}/aktivieren", json={}).status_code == 200
    return fid


def produkt_neu(kp, kategorie, modell, nr, **felder):
    r = kp.post(f"{API}/produkte", json=dict({"category_id": kategorie, "manufacturer": "Testwerk", "model": modell,
                                              "article_no": nr, "material_kind": "metall_hardware",
                                              "interval_months": 12}, **felder))
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


def lesen(kp, pid):
    r = kp.get(f"{API}/produkte/{pid}")
    assert r.status_code == 200, r.get_json()
    return r.json["produkt"]


def verknuepfen(kp, pid, quelle, **d):
    return kp.put(f"{API}/produkte/{pid}/formular-von", json=dict(d, quelle=quelle))


def aufbau(tmp):
    """Katalog aus katalog_grund mit generischem Formular für Karabiner, Produkt A (Karabiner) mit eigenem aktivem
    Formular, B und C (Karabiner) ohne."""
    app, k = umgebung(tmp)
    kp = k["katalog"]
    ids = katalog_grund(k["adm"])
    ids["generisch"] = formular(kp, {"kategorie_id": ids["karabiner"]}, "Karabiner generisch",
                                [{"text": "Platzhalter generisch", "art": "yesno", "soll": "ja"}])
    ids["a"] = produkt_neu(kp, ids["karabiner"], "Platzhalter A", "PA-1")
    ids["b"] = produkt_neu(kp, ids["karabiner"], "Platzhalter B", "PB-1")
    ids["c"] = produkt_neu(kp, ids["karabiner"], "Platzhalter C", "PC-1")
    ids["form_a"] = formular(kp, {"produkt_id": ids["a"]}, "Formular A",
                             [{"gruppe": "Gruppe", "text": "Platzhalter A1", "art": "yesno", "soll": "nein"},
                              {"text": "Platzhalter A2", "art": "yesno", "soll": "ja"}])
    return app, k, ids


def test_aufloesung_und_neue_version():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        b = lesen(kp, ids["b"])
        assert b["formular"]["id"] == ids["generisch"] and b["formular"]["art"] == "kategorie", b["formular"]
        assert b["formular_von"] is None and b["formular_genutzt_von"] == []

        r = verknuepfen(kp, ids["b"], ids["a"])
        assert r.status_code == 200 and r.json["geaendert"] is True, r.get_json()
        b = r.json["produkt"]
        assert b["formular"]["id"] == ids["form_a"] and b["formular"]["art"] == "uebernommen", b["formular"]
        assert b["formular"]["quelle"] == "übernommen von „Testwerk Platzhalter A“" and b["formular"]["punkte"] == 2
        assert b["formular"]["von"] == {"id": ids["a"], "name": "Testwerk Platzhalter A"}
        assert b["formular_von"]["id"] == ids["a"] and b["formular_von"]["aktiv"] is True
        assert b["formular_von"]["formular"] == {"id": ids["form_a"], "version": 1, "title": "Formular A"}
        # Noch einmal dasselbe: nichts ändert sich, kein zweiter Journaleintrag.
        assert verknuepfen(kp, ids["b"], ids["a"]).json["geaendert"] is False
        a = lesen(kp, ids["a"])
        assert [x["id"] for x in a["formular_genutzt_von"]] == [ids["b"]] and a["formular"]["art"] == "produkt"
        # Formularseite von A nennt die Nutzer.
        assert [x["name"] for x in kp.get(f"{API}/formulare/{ids['form_a']}").json["formular"]["genutzt_von"]] == [
            "Testwerk Platzhalter B"]
        assert kp.get(f"{API}/formulare/{ids['generisch']}").json["formular"]["genutzt_von"] == []

        # Neue Version an A gilt sofort auch für B.
        r = kp.post(f"{API}/formulare", json={"produkt_id": ids["a"], "vorlage_id": ids["form_a"]})
        neu = r.json["formular"]["id"]
        assert kp.put(f"{API}/formulare/{neu}", json={"punkte": [
            {"text": "Platzhalter A1 neu", "art": "yesno", "soll": "nein"}]}).status_code == 200
        assert lesen(kp, ids["b"])["formular"]["id"] == ids["form_a"]           # Entwurf gilt noch nicht
        assert kp.post(f"{API}/formulare/{neu}/aktivieren", json={}).status_code == 200
        b = lesen(kp, ids["b"])
        assert b["formular"]["id"] == neu and b["formular"]["version"] == 2 and b["formular"]["punkte"] == 1

        # Quelle inaktiv: B fällt auf das generische zurück, der Verweis bleibt, die Produktseite weiß es.
        assert kp.post(f"{API}/formulare/{neu}/deaktivieren", json={}).status_code == 200
        b = lesen(kp, ids["b"])
        assert b["formular"]["id"] == ids["generisch"] and b["formular"]["art"] == "kategorie"
        assert b["formular_von"]["id"] == ids["a"] and b["formular_von"]["aktiv"] is False
        assert b["formular_von"]["formular"] is None
        # Artikelseite und Prüfbeginn nutzen dieselbe Auflösung.
        with app.test_request_context():
            from app.material.services import katalog
            assert katalog.formular_fuer_produkt(ids["b"])["id"] == ids["generisch"]
        assert kp.post(f"{API}/formulare/{neu}/aktivieren", json={}).status_code == 200
        with app.test_request_context():
            f = katalog.formular_fuer_produkt(ids["b"])
            assert f["id"] == neu and f["art"] == "uebernommen" and f["uebernommen_von"]["id"] == ids["a"]

        # Lösen: wieder das generische; Journal am Produkt B mit Quelle.
        r = kp.delete(f"{API}/produkte/{ids['b']}/formular-von", headers=H)
        assert r.status_code == 200 and r.json["geaendert"] is True
        assert r.json["produkt"]["formular"]["id"] == ids["generisch"] and r.json["produkt"]["formular_von"] is None
        assert kp.delete(f"{API}/produkte/{ids['b']}/formular-von", headers=H).json["geaendert"] is False
        eintraege = [j for j in lesen(kp, ids["b"])["journal"] if j["entity"] == "product"]
        aktionen = [j["action"] for j in eintraege]
        assert aktionen.count("formular_uebernommen") == 1 and aktionen.count("formular_geloest") == 1, aktionen
        rein = next(j for j in eintraege if j["action"] == "formular_uebernommen")
        assert rein["nachher"] == {"formular_von": ids["a"], "produkt": "Testwerk Platzhalter A"}, rein
        raus = next(j for j in eintraege if j["action"] == "formular_geloest")
        assert raus["vorher"] == {"formular_von": ids["a"], "produkt": "Testwerk Platzhalter A"}, raus
        print("Auflösung, neue Version, Quelle inaktiv, Lösen bestanden.")


def test_regeln_ketten_selbst_demo_laenge_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        assert verknuepfen(kp, ids["b"], ids["a"]).status_code == 200
        # Selbstverweis, Kette (C → B, B verweist), Quelle ohne eigenes Formular, A (Quelle für B) verweist selbst.
        r = verknuepfen(kp, ids["c"], ids["c"])
        assert r.status_code == 409 and "sich selbst" in r.json["error"], r.get_json()
        r = verknuepfen(kp, ids["c"], ids["b"])
        assert r.status_code == 409 and "übernimmt selbst" in r.json["error"], r.get_json()
        r = verknuepfen(kp, ids["c"], ids["hms"])
        assert r.status_code == 409 and "kein eigenes aktives" in r.json["error"], r.get_json()
        formular(kp, {"produkt_id": ids["c"]}, "Formular C", [{"text": "Platzhalter C1", "art": "yesno", "soll": "ja"}])
        r = verknuepfen(kp, ids["a"], ids["c"])
        assert r.status_code == 409 and "übernehmen schon" in r.json["error"], r.get_json()
        assert verknuepfen(kp, ids["c"], 999999).status_code == 404

        # Eigenes aktives Formular an B: Übernehmen nur mit Deaktivieren; mit Verweis lässt sich keins aktivieren.
        assert kp.delete(f"{API}/produkte/{ids['b']}/formular-von", headers=H).status_code == 200
        eigen = formular(kp, {"produkt_id": ids["b"]}, "Formular B", [{"text": "Platzhalter B1", "art": "yesno",
                                                                       "soll": "ja"}])
        r = verknuepfen(kp, ids["b"], ids["a"])
        assert r.status_code == 409 and "deaktiviert werden" in r.json["error"], r.get_json()
        assert lesen(kp, ids["b"])["formular"]["id"] == eigen
        r = verknuepfen(kp, ids["b"], ids["a"], eigenes_deaktivieren=True)
        assert r.status_code == 200 and r.json["produkt"]["formular"]["id"] == ids["form_a"], r.get_json()
        f = kp.get(f"{API}/formulare/{eigen}").json["formular"]
        assert f["aktiv"] is False and f["journal"][0]["action"] == "deaktiviert", f["journal"][:1]
        assert "übernommen" in f["journal"][0]["nachher"]["grund"]
        r = kp.post(f"{API}/formulare/{eigen}/aktivieren", json={})
        assert r.status_code == 409 and "erst die Verknüpfung" in r.json["error"], r.get_json()
        # Anderes Produkt: Wechsel der Quelle in einem Schritt (Journal nennt die alte).
        r = verknuepfen(kp, ids["b"], ids["c"])
        assert r.status_code == 200 and r.json["produkt"]["formular_von"]["id"] == ids["c"]
        j = next(x for x in lesen(kp, ids["b"])["journal"] if x["action"] == "formular_uebernommen")
        assert j["vorher"]["formular_von"] == ids["a"] and j["nachher"]["formular_von"] == ids["c"], j

        # Länge: Formular mit „Länge (m)“ an einem Produkt einer Kategorie mit Länge – B (Karabiner) hat keine.
        r = k["adm"].post(f"{API}/kategorien", json={"name": "Seile (Test)", "default_material_kind": "textil",
                                                     "default_interval_months": 12, "items_have_length": True})
        seile = r.json["kategorie"]["id"]
        seil = produkt_neu(kp, seile, "Platzhalter Seil", "PS-1", material_kind="textil", lifetime_years=10)
        formular(kp, {"produkt_id": seil}, "Formular Seil", [{"text": "Platzhalter Länge", "art": "laenge"},
                                                             {"text": "Platzhalter S1", "art": "yesno", "soll": "nein"}])
        r = verknuepfen(kp, ids["b"], seil)
        assert r.status_code == 409 and "Länge (m)" in r.json["error"], r.get_json()
        seil2 = produkt_neu(kp, seile, "Platzhalter Seil 2", "PS-2", material_kind="textil", lifetime_years=10)
        assert verknuepfen(kp, seil2, seil).status_code == 200        # gleiche Kategorie mit Länge: geht

        # Kandidaten im Dialog: nur mit eigenem aktivem Formular, ohne Verweis, nicht B; Länge mit Grund.
        r = kp.get(f"{API}/produkte/{ids['b']}/formularquellen")
        assert r.status_code == 200, r.get_json()
        treffer = {p["id"]: p for p in r.json["produkte"]}
        assert set(treffer) == {ids["a"], ids["c"], seil}, treffer.keys()
        assert treffer[ids["a"]]["waehlbar"] and not treffer[ids["a"]]["andere_kategorie"]
        assert not treffer[seil]["waehlbar"] and "Länge" in treffer[seil]["grund"] and treffer[seil]["andere_kategorie"]
        r = kp.get(f"{API}/produkte/{ids['b']}/formularquellen?q=Seil")
        assert [p["id"] for p in r.json["produkte"]] == [seil] and r.json["gesamt"] == 1
        # Andere Kategorie ist erlaubt: Gurt Alpha (Gurte) übernimmt von C (Karabiner).
        assert verknuepfen(kp, ids["gurt"], ids["c"]).status_code == 200

        # DEMO nur mit DEMO: ein DEMO-Produkt mit eigenem Formular (über den Dienst).
        with app.test_request_context():
            from flask import g

            from app.material.services import Abgelehnt, katalog
            g.mat_akteur = "Test"
            demo = katalog.produkt_anlegen({"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                            "model": "Platzhalter DEMO", "article_no": "PD-1",
                                            "material_kind": "metall_hardware", "interval_months": 12}, demo=True)
            fid = katalog.formular_anlegen({"produkt_id": demo, "titel": "Formular DEMO", "punkte": [
                {"text": "Platzhalter D1", "art": "yesno", "soll": "ja"}]}, demo=True)
            katalog.formular_aktivieren(fid)
            for b_, q_ in ((ids["hms"], demo), (demo, ids["a"])):
                try:
                    katalog.formular_uebernehmen(b_, {"quelle": q_})
                    raise AssertionError("DEMO-Mischung angenommen")
                except Abgelehnt as exc:
                    assert "DEMO" in str(exc) and exc.code == 409
            ids_demo = [p["id"] for p in katalog.formular_quellen(demo)[0]]
            assert ids_demo == [] and demo not in [p["id"] for p in katalog.formular_quellen(ids["hms"])[0]]

        # Rechte: wie das spezifische Formular – nur die Material-Verwaltung.
        for wer in ("wart", "pruefer", "fuehrung", "nutzer"):
            c = k[wer]
            assert verknuepfen(c, ids["hms"], ids["a"]).status_code == 403, wer
            assert c.delete(f"{API}/produkte/{ids['b']}/formular-von", headers=H).status_code == 403, wer
            assert c.get(f"{API}/produkte/{ids['b']}/formularquellen").status_code == 403, wer
        assert lesen(k["wart"], ids["b"])["formular_von"]["id"] == ids["c"]      # lesen dürfen alle mit Katalog
        print("Ketten, Selbstverweis, eigenes Formular, Länge, DEMO, Rechte bestanden.")


def test_trigger_gegen_sql_von_hand():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        assert verknuepfen(k["katalog"], ids["b"], ids["a"]).status_code == 200
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("PRAGMA foreign_keys = ON")
        verboten = [f"UPDATE mat_product SET formular_von = id WHERE id = {ids['c']}",          # sich selbst
                    f"UPDATE mat_product SET formular_von = {ids['b']} WHERE id = {ids['c']}",   # Quelle verweist
                    f"UPDATE mat_product SET formular_von = {ids['c']} WHERE id = {ids['a']}",   # Quelle bekommt Verweis
                    f"UPDATE mat_product SET demo = 1 WHERE id = {ids['b']}",                    # Ziel wird DEMO
                    f"UPDATE mat_product SET demo = 1 WHERE id = {ids['a']}",                    # Quelle wird DEMO
                    f"UPDATE mat_product SET formular_von = 999999 WHERE id = {ids['c']}",       # gibt es nicht
                    "INSERT INTO mat_product (category_id, manufacturer, model, dedupe_key, material_kind, demo, "
                    f"formular_von, created_at, updated_at) VALUES ({ids['karabiner']}, 'X', 'Y', 'xy', "
                    f"'metall_hardware', 1, {ids['a']}, 'x', 'x')"]                              # DEMO auf echt
        for sql in verboten:
            try:
                conn.execute(sql)
                raise AssertionError("angenommen: " + sql)
            except sqlite3.IntegrityError as exc:
                # A hat ein eigenes aktives Formular – dort greift auch der Trigger aus Schritt 36 (Verweis oder eigenes).
                assert "keine Ketten" in str(exc) or (f"WHERE id = {ids['a']}" in sql and "kein eigenes aktives"
                                                      in str(exc)), (sql, exc)
        conn.execute(f"UPDATE mat_product SET formular_von = {ids['a']} WHERE id = {ids['c']}")  # erlaubt
        conn.execute(f"UPDATE mat_product SET formular_von = NULL WHERE id = {ids['c']}")
        conn.rollback()
        conn.close()
        print("Trigger bestanden.")


def test_quelle_loeschen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        assert verknuepfen(kp, ids["b"], ids["a"]).status_code == 200
        assert verknuepfen(kp, ids["c"], ids["a"]).status_code == 200
        assert [x["name"] for x in lesen(kp, ids["a"])["formular_genutzt_von"]] == ["Testwerk Platzhalter B",
                                                                                    "Testwerk Platzhalter C"]
        assert kp.delete(f"{API}/produkte/{ids['a']}", headers=H).status_code == 200
        for pid in (ids["b"], ids["c"]):
            p = lesen(kp, pid)
            assert p["formular_von"] is None and p["formular"]["id"] == ids["generisch"], p["formular"]
            j = next(x for x in p["journal"] if x["action"] == "formular_geloest")
            assert j["vorher"]["formular_von"] == ids["a"] and j["nachher"] == {"grund": "„Testwerk Platzhalter A“ gelöscht"}
        print("Löschen der Quelle bestanden.")


def test_pruefung_und_protokoll():
    """Eine Prüfung an einem Artikel von B nutzt das Formular von A; das Protokoll nennt A. Eine laufende Prüfung behält
    ihr Formular, auch wenn A eine neue Version bekommt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        assert verknuepfen(kp, ids["b"], ids["a"]).status_code == 200
        gid, _ = gliederung(w)
        a1 = neuer_artikel(w, ids["b"], gid)
        a2 = neuer_artikel(w, ids["b"], gid)
        artikel = w.get(f"{API}/artikel/{a1['id']}").json["artikel"]
        assert artikel["formular"]["id"] == ids["form_a"] and "übernommen von" in artikel["formular"]["quelle"]
        r = starten(p1, a1["id"])
        assert r.status_code in (200, 201), r.get_json()
        pr = r.json["pruefung"]
        assert pr["formular"]["id"] == ids["form_a"]
        assert [x["text"] for x in pr["punkte"]][:2] == ["Platzhalter A1", "Platzhalter A2"], pr["punkte"]
        laufend = starten(p1, a2["id"]).json["pruefung"]
        # Neue Version an A, während die zweite Prüfung läuft: sie behält Version 1.
        neu = kp.post(f"{API}/formulare", json={"produkt_id": ids["a"], "vorlage_id": ids["form_a"]}).json["formular"]["id"]
        assert kp.post(f"{API}/formulare/{neu}/aktivieren", json={}).status_code == 200
        assert p1.get(f"{API}/pruefungen/{laufend['id']}").json["pruefung"]["formular"]["id"] == ids["form_a"]
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        zeile = protokoll_zeile(app, pr["id"])
        text = " ".join(" ".join(pdf_seiten(os.path.join(tmp, zeile["pdf_path"]))).split())
        assert "„Formular A“, Version 1 (spezifisch für das Produkt „Testwerk Platzhalter A“)" in text, text[:3000]
        print("Prüfung und Protokoll bestanden.")


def test_export_import():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app_a, k, ids = aufbau(tmp_a)
        kp = k["katalog"]
        assert verknuepfen(kp, ids["b"], ids["a"]).status_code == 200
        roh = exportieren(kp)
        daten = katalogjson(roh)
        produkte = {p["modell"]: p for p in daten["produkte"]}
        a_uid = produkte["Platzhalter A"]["uid"]
        assert produkte["Platzhalter B"]["formular_von"] == {"uid": a_uid, "hersteller": "Testwerk",
                                                             "modell": "Platzhalter A", "artikelnummer": "PA-1"}
        assert "formular_von" not in produkte["Platzhalter A"] and "formular_von" not in produkte["Platzhalter C"]

        app_b = make_app(tmp_b)
        b = anmelden(app_b, "admin@example.org", "geheim123")
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert any("übernimmt das Prüfformular von „Testwerk Platzhalter A“" in z for z in ber["aenderungen"]), ber
        with app_b.app_context():
            from app import db
            pb = db.query("SELECT * FROM mat_product WHERE model = 'Platzhalter B'", one=True)
            pa = db.query("SELECT * FROM mat_product WHERE model = 'Platzhalter A'", one=True)
            assert pb["formular_von"] == pa["id"]
        p = lesen(b, pb["id"])
        assert p["formular"]["art"] == "uebernommen" and p["formular"]["title"] == "Formular A"
        # Noch einmal: unverändert, keine neue Zeile.
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and not any("Prüfformular" in z for z in ber["aenderungen"]), ber["aenderungen"]

        # null löst – vor den Formularen; ohne Schlüssel bleibt der Verweis.
        def ohne_schluessel(d):
            for x in d["produkte"]:
                x.pop("formular_von", None)
        assert importieren(b, umschreiben(roh, ohne_schluessel), False)["gespeichert"]
        assert lesen(b, pb["id"])["formular_von"]["id"] == pa["id"]

        def null(d):
            next(x for x in d["produkte"] if x["modell"] == "Platzhalter B")["formular_von"] = None
        ber = importieren(b, umschreiben(roh, null), False)
        assert ber["gespeichert"] and any("Übernahme des Prüfformulars gelöst" in z for z in ber["aenderungen"]), ber
        assert lesen(b, pb["id"])["formular_von"] is None

        # Quelle fehlt (weder hier noch in der Datei): Hinweis statt Fehler, der Rest wird gespeichert.
        def ohne_quelle(d):
            ziel = next(x for x in d["produkte"] if x["modell"] == "Platzhalter B")
            ziel["formular_von"] = {"uid": "0" * 32, "hersteller": "Testwerk", "modell": "Gibt es nicht",
                                    "artikelnummer": "X-0"}
        ber = importieren(b, umschreiben(roh, ohne_quelle), False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert any("Prüfformular nicht übernommen" in h and "gibt es weder" in h for h in ber["hinweise"]), ber["hinweise"]
        assert lesen(b, pb["id"])["formular_von"] is None

        # Eigenes aktives Formular hier: Der Verweis aus der Datei deaktiviert es (Änderungsliste sagt es).
        eigen = formular(b, {"produkt_id": pb["id"]}, "Formular B hier", [{"text": "Platzhalter B1", "art": "yesno",
                                                                            "soll": "ja"}])
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and any("eigenes Formular Version 1 deaktiviert" in z for z in ber["aenderungen"]), ber
        assert b.get(f"{API}/formulare/{eigen}").json["formular"]["aktiv"] is False
        # Formular der Datei für ein Produkt mit Verweis: angelegt, aber nicht aktiviert (Hinweis).

        def formular_fuer_b(d):
            d["formulare"].append({"produkt": {"uid": produkte["Platzhalter B"]["uid"]}, "titel": "Aus der Datei",
                                   "aktivieren": True, "punkte": [{"text": "Platzhalter Datei", "art": "yesno",
                                                                   "soll": "ja"}]})
        ber = importieren(b, umschreiben(roh, formular_fuer_b), False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert any("wird nicht aktiviert" in h for h in ber["hinweise"]), ber["hinweise"]
        assert lesen(b, pb["id"])["formular"]["art"] == "uebernommen"

        # Ein Katalog ohne das Feld (Stand vor Schritt 35) läuft wie bisher – Probelauf ohne Fehler.
        def alt(d):
            ohne_schluessel(d)
        ber = importieren(b, umschreiben(roh, alt), True)
        assert not ber["fehler"], ber
        # Quelle nicht im Export (sie liegt in einer DEMO-Kategorie, ohne eigenes Kennzeichen): Der Verweis fehlt, der
        # Bericht nennt das Produkt.
        with app_a.test_request_context():
            from flask import g

            from app import db
            from app.material.services import katalog, katalog_export
            g.mat_akteur = "Test"
            neu_kat = katalog.kategorie_anlegen({"name": "DEMO-Kategorie (Test)"}, demo=True)
            # Seit Schritt 36 lassen die Trigger diesen Stand nicht mehr zu (DEMO nur mit DEMO, auch über die Kategorie) –
            # hier ein Altbestand ohne sie.
            with db.transaction():
                for name in ("mat_product_formular_von", "mat_product_formular_quelle"):
                    db.execute(f"DROP TRIGGER {name}")
                db.execute("UPDATE mat_product SET category_id = ? WHERE id = ?", (neu_kat, ids["a"]))
            daten, _, bericht = katalog_export.sammeln(mit_dateien=False)
            assert bericht["verweis_ohne_quelle"] == ["Testwerk Platzhalter B"], bericht
            assert "formular_von" not in next(p for p in daten["produkte"] if p["modell"] == "Platzhalter B")
            assert "Quellprodukt nicht im Export" in katalog_export.bericht_text(bericht)
        print("Export und Import bestanden.")


def test_migration_34_35():
    """Frisch: Spalte, Index, Trigger. Vorversion 34 mit Altbestand (Kopie einer Datenbank ohne Spalte): Spalte kommt leer
    dazu, keine Zeile ändert sich. Zweiter Lauf: nichts geschieht, kein Fehler."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        from app.material import models
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert "formular_von" in models._spalten(conn, "mat_product")
        trigger = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
        assert {"mat_product_formular_von_neu", "mat_product_formular_von", "mat_product_formular_quelle"} <= trigger
        # Stand 34 nachstellen: Trigger (aus Schritt 35 und 36), Index und Spalte weg, Versionsvermerk 34.
        for name in trigger_36():
            conn.execute(f"DROP TRIGGER {name}")
        conn.execute("DROP INDEX idx_mat_product_formular_von")
        conn.execute("ALTER TABLE mat_product DROP COLUMN formular_von")
        conn.execute("UPDATE mat_meta SET wert = '34' WHERE schluessel = 'schema_version'")
        conn.commit()
        vorher = conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall()
        conn.close()
        make_app(tmp)                                       # Start: Schritt 35 bis zum Ende laufen
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == str(
            models.SCHEMA_VERSION)
        nachher = conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall()
        assert [r[:-1] for r in nachher] == vorher and all(r[-1] is None for r in nachher)
        assert conn.execute("PRAGMA foreign_key_check(mat_product)").fetchall() == []
        # Zweiter Lauf des Schritts (wiederholbar) und zweiter Start ändern nichts.
        models._schritt_35(conn)
        models._schritt_36(conn)
        conn.commit()
        assert conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall() == nachher
        conn.close()
        make_app(tmp)
        app2 = make_app(tmp)
        c = anmelden(app2, "admin@example.org", "geheim123")
        assert verknuepfen(c, ids["b"], ids["a"]).status_code == 200
        print("Migration 34 → 35 bestanden.")


# --- Nachbesserung nach der Sicherheitsprüfung vom 04.11.2026 (Schritt 36) -------------------------------------------------

BENUTZT = "Das Prüfformular dieses Produkts wurde schon für Prüfungen benutzt – es bleibt im Katalog."


def test_quelle_mit_benutzter_version():
    """Befund 2: Steckt das Formular der Quelle A in einer Prüfung (an einem Artikel von B), lässt sich A nicht löschen –
    Klartext statt „anderswo geändert“, und die Produktseite bietet es gar nicht erst an („loeschbar“ falsch). Schon ein
    Entwurf hält das Formular; nichts wird gelöst."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        assert verknuepfen(kp, ids["b"], ids["a"]).status_code == 200
        assert lesen(kp, ids["a"])["loeschbar"] is True                 # A selbst hat keine Artikel
        gid, _ = gliederung(w)
        art = neuer_artikel(w, ids["b"], gid)
        r = starten(p1, art["id"])
        assert r.status_code in (200, 201), r.get_json()
        pr = r.json["pruefung"]
        assert pr["formular"]["id"] == ids["form_a"]
        for schritt in ("entwurf", "festgeschrieben"):
            if schritt == "festgeschrieben":
                assert abschluss(p1, pr["id"], ergebnis="einsatzbereit").status_code == 200
            assert lesen(kp, ids["a"])["loeschbar"] is False, schritt
            r = kp.delete(f"{API}/produkte/{ids['a']}", headers=H)
            assert r.status_code == 409 and r.json["error"] == BENUTZT, (schritt, r.get_json())
            assert lesen(kp, ids["b"])["formular_von"]["id"] == ids["a"], schritt      # nichts gelöst
        # Gegenprobe: C (keine Artikel, Formular unbenutzt) bleibt löschbar; B hat Artikel – die bekannte Meldung.
        assert lesen(kp, ids["c"])["loeschbar"] is True
        r = kp.delete(f"{API}/produkte/{ids['b']}", headers=H)
        assert r.status_code == 409 and "Artikel" in r.json["error"], r.get_json()
        print("Quelle mit benutzter Formularversion bestanden.")


def test_rennen_aktivieren_uebernehmen():
    """Befund 3: Aktivieren eines eigenen Formulars von C gegen Übernehmen (C → A) – das Fenster wie in der Probe der
    Prüfung mit einer Pause nach dem Lesen von C geweitet. Danach nie Verweis und eigenes aktives Formular zugleich; der
    Trigger aus Schritt 36 fängt dasselbe gegen SQL von Hand."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        eigen = formular(kp, {"produkt_id": ids["c"]}, "Formular C", [{"text": "Platzhalter C1", "art": "yesno",
                                                                       "soll": "ja"}], aktiv=False)
        from app.material.services import katalog
        original = katalog.produkt
        lokal = threading.local()

        def langsam(pid):
            r = original(pid)
            if getattr(lokal, "warten", False):
                lokal.warten = False
                time.sleep(1.5)
            return r

        ergebnis = {}

        def aktivieren():
            lokal.warten = True
            c1 = anmelden(app, "katalog@example.org", "passwort1")
            ergebnis["aktivieren"] = c1.post(f"{API}/formulare/{eigen}/aktivieren", json={}).status_code

        katalog.produkt = langsam
        try:
            t = threading.Thread(target=aktivieren)
            t.start()
            time.sleep(0.5)
            r = verknuepfen(kp, ids["c"], ids["a"])
            ergebnis["uebernehmen"] = r.status_code
            t.join(30)
        finally:
            katalog.produkt = original
        assert ergebnis == {"aktivieren": 200, "uebernehmen": 409}, ergebnis
        assert "deaktiviert werden" in r.json["error"], r.get_json()
        pc = lesen(kp, ids["c"])
        assert pc["formular_von"] is None and pc["formular"]["id"] == eigen, pc["formular"]

        # SQL von Hand: aktivieren, einfügen bzw. verweisen, während das andere gilt.
        assert verknuepfen(kp, ids["c"], ids["a"], eigenes_deaktivieren=True).status_code == 200
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("PRAGMA foreign_keys = ON")
        for sql in (f"UPDATE mat_form SET active = 1 WHERE id = {eigen}",
                    "INSERT INTO mat_form (product_id, version, title, active, created_at, updated_at) "
                    f"VALUES ({ids['c']}, 9, 'Platzhalter', 1, 'x', 'x')",
                    f"UPDATE mat_form SET product_id = {ids['c']}, active = 1 WHERE id = {ids['form_a']}"):
            try:
                conn.execute(sql)
                raise AssertionError("angenommen: " + sql)
            except sqlite3.IntegrityError as exc:
                assert "kein eigenes aktives" in str(exc), (sql, exc)
        conn.rollback()
        conn.execute(f"UPDATE mat_product SET formular_von = NULL WHERE id = {ids['c']}")
        conn.execute(f"UPDATE mat_form SET active = 1 WHERE id = {eigen}")
        try:
            conn.execute(f"UPDATE mat_product SET formular_von = {ids['a']} WHERE id = {ids['c']}")
            raise AssertionError("Verweis neben eigenem aktivem Formular angenommen")
        except sqlite3.IntegrityError as exc:
            assert "kein eigenes aktives" in str(exc), exc
        conn.rollback()
        conn.close()
        print("Rennen Aktivieren/Übernehmen bestanden.")


def test_demo_regel_ueber_kategorie():
    """Befund 4, Hinweis 1: DEMO nach der Regel des Katalog-Exports – ein Produkt ohne Kennzeichen in einer Kategorie
    unter einer DEMO-Kategorie zählt als DEMO. Echt nur mit echt, DEMO nur mit DEMO: Dienst, Kandidaten im Dialog,
    Produkt in eine andere Kategorie, Kategorie umhängen (Klartext) und die Trigger gegen SQL von Hand."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp, adm = k["katalog"], k["adm"]
        with app.test_request_context():
            from app.material.services import katalog
            demo_wurzel = katalog.kategorie_anlegen({"name": "DEMO-Beispiel (Platzhalter)"}, demo=True)
        r = adm.post(f"{API}/kategorien", json={"name": "Karabiner (Platzhalter)", "parent_id": demo_wurzel,
                                                "default_material_kind": "metall_hardware"})
        assert r.status_code == 201, r.get_json()
        demo_kat = r.json["kategorie"]["id"]
        # So legt die Oberfläche Produkt und Formular in einer DEMO-Kategorie an: ohne eigenes Kennzeichen.
        d1 = produkt_neu(kp, demo_kat, "Platzhalter D1", "PD-11")
        d2 = produkt_neu(kp, demo_kat, "Platzhalter D2", "PD-12")
        formular(kp, {"produkt_id": d1}, "Formular D1", [{"text": "Platzhalter D", "art": "yesno", "soll": "ja"}])
        with app.app_context():
            from app import db
            from app.material.services import katalog
            assert db.query("SELECT demo FROM mat_product WHERE id = ?", (d1,), one=True)["demo"] == 0
            assert katalog.demo_kategorien() == {demo_wurzel, demo_kat}
            assert katalog.produkt_ist_demo(katalog.produkt(d1)) and not katalog.produkt_ist_demo(katalog.produkt(ids["b"]))
        for b_, q_ in ((ids["b"], d1), (d2, ids["a"])):
            r = verknuepfen(kp, b_, q_)
            assert r.status_code == 409 and "DEMO" in r.json["error"], r.get_json()
        quellen = lambda pid: {p["id"] for p in kp.get(f"{API}/produkte/{pid}/formularquellen").json["produkte"]}  # noqa: E731
        assert d1 not in quellen(ids["b"]) and ids["a"] in quellen(ids["b"])
        assert quellen(d2) == {d1}
        assert verknuepfen(kp, d2, d1).status_code == 200                  # DEMO mit DEMO (beide über die Kategorie)

        # Ein Produkt mit Verweis bzw. eine Quelle über die DEMO-Grenze verschieben: Klartext mit dem Namen des anderen.
        assert verknuepfen(kp, ids["b"], ids["a"]).status_code == 200
        for pid, anderes in ((ids["b"], "Platzhalter A"), (ids["a"], "Platzhalter B")):
            r = kp.put(f"{API}/produkte/{pid}", json={"category_id": demo_kat})
            assert r.status_code == 409 and "DEMO nur mit DEMO" in r.json["error"] and anderes in r.json["error"], \
                r.get_json()
        r = kp.put(f"{API}/produkte/{d2}", json={"category_id": ids["karabiner"]})
        assert r.status_code == 409 and "Platzhalter D1" in r.json["error"], r.get_json()
        assert kp.put(f"{API}/produkte/{ids['c']}", json={"category_id": demo_kat}).status_code == 200   # ohne Verweis
        assert kp.put(f"{API}/produkte/{ids['c']}", json={"category_id": ids["karabiner"]}).status_code == 200
        # Eine Kategorie über die DEMO-Grenze umhängen: Gurt Alpha (Gurte) übernimmt von A (Karabiner) – Gurte oder Karabiner
        # unter die DEMO-Kategorie: Klartext, nichts geändert. Wandern beide Seiten mit (B und A in Karabiner, D2 und D1)
        # oder hängt kein Verweis daran, geht es.
        assert verknuepfen(kp, ids["gurt"], ids["a"]).status_code == 200
        for kid in (ids["gurte"], ids["karabiner"]):
            r = kp.put(f"{API}/kategorien/{kid}", json={"parent_id": demo_wurzel})
            assert r.status_code == 409 and "DEMO nur mit DEMO" in r.json["error"], r.get_json()
        assert kp.delete(f"{API}/produkte/{ids['gurt']}/formular-von", headers=H).status_code == 200
        assert kp.put(f"{API}/kategorien/{ids['karabiner']}", json={"parent_id": demo_wurzel}).status_code == 200
        assert kp.put(f"{API}/kategorien/{ids['karabiner']}", json={"parent_id": ids["psa"]}).status_code == 200
        assert kp.put(f"{API}/kategorien/{demo_kat}", json={"parent_id": ids["psa"]}).status_code == 200
        assert kp.put(f"{API}/kategorien/{demo_kat}", json={"parent_id": demo_wurzel}).status_code == 200
        assert lesen(kp, ids["b"])["formular_von"]["id"] == ids["a"]
        assert verknuepfen(kp, ids["gurt"], ids["a"]).status_code == 200

        # SQL von Hand (mit Fremdschlüsseln): dieselben Wechsel scheitern an den Triggern aus Schritt 36.
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("PRAGMA foreign_keys = ON")
        for sql in (f"UPDATE mat_product SET category_id = {demo_kat} WHERE id = {ids['b']}",          # Ziel wird DEMO
                    f"UPDATE mat_product SET category_id = {demo_kat} WHERE id = {ids['a']}",          # Quelle wird DEMO
                    f"UPDATE mat_product SET formular_von = {d1} WHERE id = {ids['c']}",               # echt auf DEMO
                    f"UPDATE mat_category SET parent_id = {demo_wurzel} WHERE id = {ids['karabiner']}",
                    f"UPDATE mat_category SET parent_id = {demo_wurzel} WHERE id = {ids['gurte']}",
                    f"UPDATE mat_category SET demo = 1 WHERE id = {ids['gurte']}"):
            try:
                conn.execute(sql)
                raise AssertionError("angenommen: " + sql)
            except sqlite3.IntegrityError as exc:
                assert "DEMO nur von DEMO" in str(exc), (sql, exc)
        conn.execute(f"UPDATE mat_category SET demo = 1 WHERE id = {ids['psa']}")      # erlaubt: alle Seiten werden DEMO
        conn.rollback()
        conn.close()
        print("DEMO-Regel über die Kategorie bestanden.")


def test_migration_35_36():
    """Vorversion 35 mit Altbestand, den Schritt 36 ausschließt (Verweis zwischen DEMO-Kategorie und echt; Verweis neben
    eigenem aktivem Formular – nur über die Rennlücke bzw. vor der DEMO-Regel möglich): Der Start löst bzw. deaktiviert
    genau das, je eine Zeile im Startprotokoll, sonst ändert sich keine Zeile. Zweiter Lauf: nichts geschieht."""
    import logging
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = aufbau(tmp)
        kp = k["katalog"]
        from app.material import models
        with app.test_request_context():
            from app.material.services import katalog
            demo_kat = katalog.kategorie_anlegen({"name": "DEMO-Beispiel (Platzhalter)"}, demo=True)
        d = produkt_neu(kp, demo_kat, "Platzhalter D", "PD-21")
        eigen_c = formular(kp, {"produkt_id": ids["c"]}, "Formular C", [{"text": "Platzhalter C1", "art": "yesno",
                                                                         "soll": "ja"}], aktiv=False)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        # Stand 35 nachstellen: die Trigger in der Fassung von Schritt 35, Versionsvermerk 35; dann der Altbestand.
        for name in trigger_36():
            conn.execute(f"DROP TRIGGER {name}")
        models._schritt_35(conn)
        conn.execute("UPDATE mat_meta SET wert = '35' WHERE schluessel = 'schema_version'")
        conn.execute(f"UPDATE mat_product SET formular_von = {ids['a']} WHERE id = {d}")        # DEMO-Kategorie → echt
        conn.execute(f"UPDATE mat_product SET formular_von = {ids['a']} WHERE id = {ids['c']}")
        conn.execute(f"UPDATE mat_form SET active = 1 WHERE id = {eigen_c}")                    # Verweis und eigenes
        conn.execute(f"UPDATE mat_product SET formular_von = {ids['a']} WHERE id = {ids['b']}")  # in Ordnung
        conn.commit()
        produkte = conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall()
        formulare = conn.execute("SELECT * FROM mat_form ORDER BY id").fetchall()
        conn.close()
        meldungen = []

        class Sammler(logging.Handler):
            def emit(self, record):
                meldungen.append(record.getMessage())

        sammler = Sammler()
        logging.getLogger("app.material.models").addHandler(sammler)
        try:
            make_app(tmp)                                   # Start: Schritt 36 bis zum Ende laufen
        finally:
            logging.getLogger("app.material.models").removeHandler(sammler)
        conn = sqlite3.connect(pfad)
        from app.material import models as modelle
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == str(
            modelle.SCHEMA_VERSION)
        spalte = [r[1] for r in conn.execute("PRAGMA table_info(mat_product)")].index("formular_von")
        erwartet = [tuple(None if (r[0] == d and i == spalte) else v for i, v in enumerate(r)) for r in produkte]
        assert conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall() == erwartet
        aktiv = [r[1] for r in conn.execute("PRAGMA table_info(mat_form)")].index("active")
        erwartet = [tuple(0 if (r[0] == eigen_c and i == aktiv) else v for i, v in enumerate(r)) for r in formulare]
        assert conn.execute("SELECT * FROM mat_form ORDER BY id").fetchall() == erwartet
        schritt_36 = [m for m in meldungen if m.startswith("Schritt 36")]
        assert len(schritt_36) == 2 and "Platzhalter D" in schritt_36[0] and "Version 1" in schritt_36[1], meldungen
        trigger = {r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")}
        assert set(trigger_36()) <= set(trigger) and "category_id" in trigger["mat_product_formular_von"]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Zweiter Lauf des Schritts und zweiter Start ändern nichts.
        vorher = (conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall(),
                  conn.execute("SELECT * FROM mat_form ORDER BY id").fetchall())
        models._schritt_36(conn)
        conn.commit()
        assert (conn.execute("SELECT * FROM mat_product ORDER BY id").fetchall(),
                conn.execute("SELECT * FROM mat_form ORDER BY id").fetchall()) == vorher
        conn.close()
        app2 = make_app(tmp)
        c = anmelden(app2, "admin@example.org", "geheim123")
        assert lesen(c, ids["c"])["formular"]["art"] == "uebernommen"
        print("Migration 35 → 36 bestanden.")


def test_oberflaeche_statisch():
    with open(os.path.join(WURZEL, "app", "material", "static", "material.js"), encoding="utf-8") as fh:
        js = fh.read()
    produkt = js[js.index("  async function produkt() {"):js.index("  // Mehrere Dokumente auf einmal:")]
    # Ohne Verweis: „Spezifisches Formular bearbeiten“ und „Von anderem Produkt übernehmen“ im Menü „Bearbeiten“; mit
    # Verweis statt dessen „Anderes Produkt“ und „Verknüpfung lösen“.
    for stelle in ('text: "Spezifisches Formular bearbeiten"', 'text: "Von anderem Produkt übernehmen"',
                   'text: "Anderes Produkt"', 'text: "Verknüpfung lösen"', '"formular-uebernehmen": () => formularUebernehmen(p)',
                   '"formular-loesen": () => formularLoesen(p)', "Auch genutzt von"):
        assert stelle in produkt or stelle in js, stelle
    # Felder dürfen fehlen (Übungsantwort der Einführung kennt sie nicht).
    assert "(p.formular_genutzt_von || [])" in produkt and "eintraege: p.formular_von\n" in produkt
    assert "Das übernommene Formular von" in js
    # Formularseite der Quelle: derselbe Hinweis.
    editor = js[js.index("  async function formular() {"):]
    assert "${formularNutzerHinweis(f.genutzt_von)}" in editor[:editor.index("\n  }\n")]
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_aufloesung_und_neue_version()
    test_regeln_ketten_selbst_demo_laenge_rechte()
    test_trigger_gegen_sql_von_hand()
    test_quelle_loeschen()
    test_pruefung_und_protokoll()
    test_export_import()
    test_migration_34_35()
    test_quelle_mit_benutzter_version()
    test_rennen_aktivieren_uebernehmen()
    test_demo_regel_ueber_kategorie()
    test_migration_35_36()
    test_oberflaeche_statisch()
    print(json.dumps({"ok": True}))
