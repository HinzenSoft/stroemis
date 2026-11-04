"""Formular-Pool im Katalogaustausch (Format 3, Schritt 38) mit den Entscheidungen aus planung/katalog-transfer:
python tests/test_material_formular_transfer.py  oder  pytest tests/test_material_formular_transfer.py

  - Export (E1): je Formular des Pools mit aktiver Version genau diese – auch mit DEMO-Kennzeichen und Platzhalter –,
    mit uid, Heimat, Standard für, zugewiesen an; ohne aktive Version und im Pool einer DEMO-Kategorie nichts. Kein
    Journal und nichts Journalähnliches (Konten, Namen, E-Mail, Bearbeitungszeiten) in katalog.json und bericht.txt; der
    Bericht nennt die Formulare und welche hier DEMO bzw. Platzhalter sind.
  - Import: übernimmt nie ein DEMO-Kennzeichen (auch nicht „demo“: true der Datei), nimmt „DEMO“ vorn aus Titeln, macht
    das Formular aktiv; zweiter Import ändert nichts; Abgleich über die uid, sonst über den Titel in derselben Heimat
    (E3, die uid wird übernommen); abweichende Punkte oder Titel → neue Version; die Datei ist für Zuweisungen
    maßgeblich (E2) – was nur Formulare und Ziele hier betrifft, bleibt; eine laufende Prüfung behält ihre Version.
  - Frischer Stand: Rundlauf in eine leere Instanz – für jedes Produkt dasselbe Formular (Titel und Prüfpunkte).
  - Alte Dateien (Format 1/2): Formulare mit „kategorie“ werden Standard, mit „produkt“ zugewiesen, „aktivieren“: false
    nur Version, „formular_von“ wird Zuweisung an das Formular der Quelle; leerer Titel → „Prüfformular <Ziel>“.
Alle Namen, Hersteller und Prüfpunkte sind Platzhalter."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (anmelden, formular_neu, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           starten, umgebung)
from test_material_katalog import exportieren, importieren, katalogjson, umschreiben  # noqa: E402

API = "/api/material"
JA = [{"text": "Platzhalter Ja", "art": "yesno", "soll": "ja"}]


def pool_neu(c, kategorie, titel, punkte=JA, aktivieren=True):
    r = c.post(f"{API}/formular-pool", json={"kategorie_id": kategorie, "titel": titel, "punkte": punkte})
    assert r.status_code == 201, r.get_json()
    if aktivieren:
        assert c.post(f"{API}/formulare/{r.json['formular']['id']}/aktivieren", json={}).status_code == 200
    return r.json["formular"]["formular_id"], r.json["formular"]["id"]


def zuweisen(c, pf, kategorien=(), produkte=()):
    r = c.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": list(kategorien), "produkte": list(produkte)})
    assert r.status_code == 200, r.get_json()


def produkt_neu(c, kategorie, modell, nr):
    r = c.post(f"{API}/produkte", json={"category_id": kategorie, "manufacturer": "Testwerk", "model": modell,
                                        "article_no": nr, "material_kind": "metall_hardware", "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


def geltend(c):
    """Je Produkt (Modell) das geltende Formular als (Titel, Art, Prüfpunkte)."""
    out = {}
    for p in c.get(f"{API}/produkte?pro_seite=200").json["produkte"]:
        f = c.get(f"{API}/produkte/{p['id']}").json["produkt"]["formular"]
        punkte = [x["text"] for x in c.get(f"{API}/formulare/{f['id']}").json["formular"]["punkte"]] if f else None
        out[p["model"]] = (f["title"], f["art"], punkte) if f else None
    return out


def quelle(tmp):
    """Instanz A (dev): Gurte mit Standard „Gurtprüfung“, dem Gurt zugewiesen (Z3); Karabiner mit einem aktiven
    DEMO-Platzhalter als Standard, HMS ausdrücklich zugewiesen; ein Entwurf ohne aktive Version; eine DEMO-Kategorie mit
    eigenem Formular."""
    app, k = umgebung(tmp)
    kp = k["katalog"]
    ids = katalog_grund(k["adm"])
    ids["f1"], ids["f1v"] = pool_neu(kp, ids["gurte"], "Gurtprüfung", [
        {"gruppe": "Platzhalter Gruppe", "text": "Platzhalter Gurt", "art": "yesno", "soll": "nein"},
        {"text": "Platzhalter Bemerkung", "art": "text", "pflicht": False}])
    zuweisen(kp, ids["f1"], kategorien=[ids["gurte"]], produkte=[ids["gurt"]])
    with app.test_request_context():
        from flask import g

        from app.material.services import katalog
        g.mat_akteur = "Test"
        pf, vid = katalog.pool_anlegen({"kategorie_id": ids["karabiner"], "titel": "DEMO – Platzhalter Karabiner",
                                        "punkte": [{"text": "DEMO Ja/Nein-Punkt (Platzhalter)", "art": "yesno",
                                                    "soll": "ja"}]}, demo=True)
        katalog.formular_aktivieren(vid)
        ids["f2"], ids["f2v"] = pf, vid
        demo = katalog.kategorie_anlegen({"name": "DEMO Bereich"}, demo=True)
        pd, vd = katalog.pool_anlegen({"kategorie_id": demo, "titel": "Nur DEMO", "punkte": JA})
        katalog.formular_aktivieren(vd)
        katalog.zuweisung_setzen(pd, {"kategorien": [demo]})
    zuweisen(kp, ids["f2"], kategorien=[ids["karabiner"]], produkte=[ids["hms"]])
    ids["f3"], _ = pool_neu(kp, ids["karabiner"], "Entwurf Karabiner", aktivieren=False)
    return app, k, ids


def test_export():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids = quelle(tmp)
        kp = k["katalog"]
        roh = exportieren(kp)
        daten = katalogjson(roh)
        assert daten["version"] == 3
        f = {x["titel"]: x for x in daten["formulare"]}
        assert set(f) == {"Gurtprüfung", "DEMO – Platzhalter Karabiner"}, set(f)            # E1, DEMO-Kategorie draußen
        assert f["Gurtprüfung"]["kategorie"] == ["PSA gegen Absturz", "Gurte"] and len(f["Gurtprüfung"]["uid"]) == 32
        assert [x["kategorie"] for x in f["Gurtprüfung"]["standard_fuer"]] == [["PSA gegen Absturz", "Gurte"]]
        assert [x["modell"] for x in f["Gurtprüfung"]["zugewiesen"]] == ["Gurt Alpha"]
        assert [x["modell"] for x in f["DEMO – Platzhalter Karabiner"]["zugewiesen"]] == ["HMS Beta"]
        assert set(f["Gurtprüfung"]) == {"uid", "kategorie", "kategorie_uid", "titel", "punkte", "standard_fuer",
                                         "zugewiesen"}
        # Kein Journal, keine Konten, keine Zeiten der Bearbeitung – weder in katalog.json noch im Bericht.
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(roh)) as z:
            bericht = z.read("bericht.txt").decode()
        for text in (json.dumps(daten, ensure_ascii=False), bericht):
            for wort in ("@example", "created", "updated", "user", "journal", "audit", "angelegt_von", "Migration",
                         "Katalogimport (", "Admin"):
                assert wort not in text, (wort, text[:2000])
        assert "„Gurtprüfung“ – PSA gegen Absturz / Gurte – Standard für 1 Kategorie, 1 Produkt zugewiesen" in bericht, bericht
        assert "„DEMO – Platzhalter Karabiner“" in bericht and "[auf dieser Instanz DEMO, Platzhalter]" in bericht, bericht
        assert "Nicht im Export: 1 Prüfformulare ohne aktive Version." in bericht, bericht
    print("Export bestanden.")


def test_import_und_rundlauf():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app_a, k, ids = quelle(tmp_a)
        kp = k["katalog"]
        roh = exportieren(kp)
        app_b, kb = umgebung(tmp_b)
        b = kb["katalog"]
        # Frischer Stand: leere Instanz. Probelauf schreibt nichts, der echte Lauf alles.
        ber = importieren(b, roh, True)
        assert not ber["fehler"] and not ber["gespeichert"] and ber["formulare"]["neu"] == 2, ber
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["formulare"] == {"neu": 2, "unveraendert": 0} and ber["zuweisungen"]["neu"] == 4, ber
        # Gleiches Formular je Produkt (Titel, Art, Prüfpunkte) – nur ohne „DEMO“ vorn im Titel.
        from app.material.services.importer import ohne_demo
        a_stand, b_stand = geltend(kp), geltend(b)
        assert b_stand == {m: (ohne_demo(v[0]), v[1], v[2]) if v else None for m, v in a_stand.items()}, (a_stand,
                                                                                                         b_stand)
        with app_b.app_context():
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM mat_form WHERE demo = 1", one=True)["n"] == 0
            assert db.query("SELECT COUNT(*) AS n FROM mat_formular WHERE demo = 1", one=True)["n"] == 0
            assert db.query("SELECT COUNT(*) AS n FROM mat_category WHERE demo = 1", one=True)["n"] == 0
            assert sorted(r["title"] for r in db.query("SELECT title FROM mat_form WHERE active = 1")) == [
                "Gurtprüfung", "Platzhalter Karabiner"]
            uids_b = {r["uid"] for r in db.query("SELECT uid FROM mat_formular")}
        with app_a.app_context():
            from app import db
            assert uids_b == {r["uid"] for r in db.query("SELECT uid FROM mat_formular WHERE id IN (?, ?)",
                                                         (ids["f1"], ids["f2"]))}
        # Zweiter Import: nichts.
        ber = importieren(b, roh, False)
        assert ber["formulare"] == {"neu": 0, "unveraendert": 2} and ber["zuweisungen"] == {
            "neu": 0, "geloest": 0, "unveraendert": 4}, ber
        assert not ber["aenderungen"], ber["aenderungen"]

        # E2: Die Datei ist maßgeblich. In B: (a) ein eigenes Formular für HMS, (b) „Gurtprüfung“ zusätzlich an ein Produkt
        # nur hier, (c) ein eigenes Formular an einem eigenen Produkt, (d) ein anderer Standard für Gurte.
        bk = {x["name"]: x["id"] for x in b.get(f"{API}/kategorien").json["kategorien"]}
        bp = {x["model"]: x["id"] for x in b.get(f"{API}/produkte?pro_seite=200").json["produkte"]}
        nur_b = produkt_neu(b, bk["Gurte"], "Nur hier", "NH-1")
        nur_b2 = produkt_neu(b, bk["Karabiner"], "Nur hier 2", "NH-2")
        fb, _ = pool_neu(b, bk["Karabiner"], "Eigen Karabiner")
        zuweisen(b, fb, produkte=[bp["HMS Beta"], nur_b2])                          # (a) und (c)
        f1_b = next(f["id"] for x in b.get(f"{API}/formular-pool").json["kategorien"] for f in x["formulare"]
                    if f["titel"] == "Gurtprüfung")
        zuweisen(b, f1_b, kategorien=[bk["Gurte"]], produkte=[bp["Gurt Alpha"], nur_b])   # (b)
        fb3, _ = pool_neu(b, bk["Gurte"], "Eigen Gurte")
        zuweisen(b, fb3, kategorien=[bk["Gurte"]])                                  # (d)
        ber = importieren(b, roh, False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["zuweisungen"]["geloest"] == 1 and ber["zuweisungen"]["neu"] == 2, ber    # (b) gelöst, (a)+(d) zurück
        jetzt = geltend(b)
        assert jetzt["HMS Beta"][0] == "Platzhalter Karabiner" and jetzt["Nur hier 2"][0] == "Eigen Karabiner"
        assert jetzt["Nur hier"] == ("Gurtprüfung", "standard", jetzt["Nur hier"][2])        # über den Standard
        with app_b.app_context():
            from app import db
            assert not db.query("SELECT 1 FROM mat_formular_zuweisung WHERE product_id = ?", (nur_b,))
        assert any("nicht mehr zugewiesen" in z for z in ber["aenderungen"]), ber["aenderungen"]

        # Eine laufende Prüfung in B behält ihre Version; neuer Titel in A → neue Version in B (gleiches Formular, E3).
        gid, _ = gliederung(kb["wart"])
        art = neuer_artikel(kb["wart"], bp["Gurt Alpha"], gid, manufactured_on="2025-01")
        pr = starten(kb["pruefer"], art["id"])
        assert pr.status_code in (200, 201), pr.get_json()
        alt_v = pr.json["pruefung"]["formular"]["id"]
        r = kp.post(f"{API}/formulare", json={"formular_id": ids["f1"], "vorlage_id": ids["f1v"],
                                              "titel": "Gurtprüfung (neu)"})
        assert r.status_code == 201 and kp.post(f"{API}/formulare/{r.json['formular']['id']}/aktivieren",
                                                json={}).status_code == 200
        ber = importieren(b, exportieren(kp), False)
        assert ber["formulare"] == {"neu": 1, "unveraendert": 1}, ber
        assert geltend(b)["Gurt Alpha"][0] == "Gurtprüfung (neu)"
        assert kb["pruefer"].get(f"{API}/pruefungen/{pr.json['pruefung']['id']}").json["pruefung"]["formular"]["id"] == alt_v
        with app_b.app_context():
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM mat_formular", one=True)["n"] == 4      # 2 aus A, 2 nur hier
    print("Import und Rundlauf bestanden.")


def test_titelabgleich_und_demo_der_datei():
    """E3 ohne uid: ein gleichnamiges Formular in derselben Heimat übernimmt die uid der Datei (Journal); ein Feld
    „demo“ der Datei zählt nicht; „DEMO-“ und „DEMO “ vorn fallen weg."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        ids = katalog_grund(c)
        pf, _ = pool_neu(c, ids["gurte"], "Gurtprüfung", JA)
        datei = {"format": "stroemis-material-katalog", "version": 3, "demo": True,
                 "kategorien": [{"name": "PSA gegen Absturz", "unterkategorien": [{"name": "Gurte"}]}],
                 "formulare": [{"uid": "a" * 32, "kategorie": ["PSA gegen Absturz", "Gurte"], "titel": "DEMO-Gurtprüfung",
                                "punkte": JA, "standard_fuer": [{"kategorie": ["PSA gegen Absturz", "Gurte"]}]},
                               {"uid": "b" * 32, "kategorie": ["PSA gegen Absturz", "Karabiner"],
                                "titel": "DEMO Karabiner neu", "demo": True, "punkte": JA}]}
        ber = importieren(c, json.dumps(datei).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"], ber
        assert ber["formulare"] == {"neu": 1, "unveraendert": 1}, ber
        with app.app_context():
            from app import db
            rows = {r["uid"]: r for r in db.query("SELECT * FROM mat_formular")}
            assert rows["a" * 32]["id"] == pf and rows["a" * 32]["demo"] == 0
            assert rows["b" * 32]["demo"] == 0
            assert {r["title"] for r in db.query("SELECT title FROM mat_form")} == {"Gurtprüfung", "Karabiner neu"}
            assert db.query("SELECT COUNT(*) AS n FROM mat_category WHERE demo = 1", one=True)["n"] == 0
            assert db.query("SELECT 1 FROM mat_audit WHERE entity = 'formular' AND entity_id = ? AND action = 'geaendert' "
                            "AND after_json LIKE ?", (pf, f'%{"a" * 32}%'))
        assert c.get(f"{API}/produkte/{ids['gurt']}").json["produkt"]["formular"]["title"] == "Gurtprüfung"
    print("Titelabgleich und DEMO der Datei bestanden.")


def test_alte_formate():
    """Format 1/2: „kategorie“ → Standard, „produkt“ → zugewiesen (Heimat: die Kategorie des Produkts), „aktivieren“:
    false nur als Version, „formular_von“ → Zuweisung an das Formular der Quelle, leerer Titel → „Prüfformular <Ziel>“."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        ids = katalog_grund(c)
        hms2 = produkt_neu(c, ids["karabiner"], "HMS Zwei", "HZ-2")
        produkt = {"hersteller": "Testwerk", "modell": "HMS Beta", "artikelnummer": "HB-7"}
        datei = {"format": "stroemis-material-katalog", "version": 2,
                 "produkte": [{"kategorie": ["PSA gegen Absturz", "Karabiner"], "hersteller": "Testwerk",
                               "modell": "HMS Zwei", "artikelnummer": "HZ-2", "materialart": "metall_hardware",
                               "intervall_monate": 12, "formular_von": produkt}],
                 "formulare": [{"kategorie": ["PSA gegen Absturz", "Gurte"], "titel": "", "punkte": JA},
                               {"produkt": produkt, "titel": "Spezifisch HMS", "punkte": JA},
                               {"kategorie": ["PSA gegen Absturz", "Karabiner"], "titel": "Nur Entwurf",
                                "aktivieren": False, "punkte": JA}]}
        ber = importieren(c, json.dumps(datei).encode(), False, "katalog.json")
        assert ber["gespeichert"] and not ber["fehler"], ber
        gurt = c.get(f"{API}/produkte/{ids['gurt']}").json["produkt"]["formular"]
        assert gurt["title"] == "Prüfformular Gurte" and gurt["art"] == "standard", gurt
        hms = c.get(f"{API}/produkte/{ids['hms']}").json["produkt"]["formular"]
        assert hms["title"] == "Spezifisch HMS" and hms["art"] == "zugewiesen", hms
        assert hms["formular"]["heimat"]["id"] == ids["karabiner"]
        zwei = c.get(f"{API}/produkte/{hms2}").json["produkt"]["formular"]
        assert zwei["id"] == hms["id"] and zwei["art"] == "zugewiesen", zwei
        pool = {f["titel"]: f for x in c.get(f"{API}/formular-pool").json["kategorien"] for f in x["formulare"]}
        assert pool["Nur Entwurf"]["aktive_version"] is None and not pool["Nur Entwurf"]["zugewiesen"]
        # Noch einmal: unverändert.
        ber = importieren(c, json.dumps(datei).encode(), False, "katalog.json")
        assert ber["formulare"] == {"neu": 0, "unveraendert": 3} and not ber["aenderungen"], ber
        # Quelle ohne Formular hier: Hinweis, kein Fehler.
        datei["produkte"][0]["formular_von"] = {"hersteller": "Testwerk", "modell": "Gurt Alpha", "artikelnummer": "GA-100"}
        ber = importieren(c, json.dumps(datei).encode(), False, "katalog.json")
        assert ber["gespeichert"] and any("kein zugewiesenes Prüfformular" in h for h in ber["hinweise"]), ber
    print("Alte Formate bestanden.")


if __name__ == "__main__":
    test_export()
    test_import_und_rundlauf()
    test_titelabgleich_und_demo_der_datei()
    test_alte_formate()
    print(json.dumps({"ok": True}))
