"""Formular-Pool – Nachbesserung nach der Sicherheitsprüfung vom 04.11.2026 (planung/formular-pool/pruefung_sicherheit.md):
python tests/test_material_formular_sicherheit.py  oder  pytest tests/test_material_formular_sicherheit.py

  - Befund 1: Eine alte Katalogdatei (Format 1/2) schreibt kein geteiltes Formular um. Ein „produkt“-Eintrag nimmt nur
    ein Formular, das allein diesem Produkt gilt (und den Produkten, die es laut derselben Datei übernehmen), ein
    „kategorie“-Eintrag nur eines, das allein Standard dieser Kategorie ist; sonst kommt ein neues in den Pool. Fälle 1–5
    der Probe probe_import_alt.py; ein zweiter Import ändert nichts. Die Berichtszeile nennt, wofür das Formular gilt.
  - Befund 2: PUT …/formular-pool/<id>/zuweisung mit kaputtem Rumpf (kein Objekt, kaputtes JSON, ein Schlüssel fehlt,
    keine Liste, keine Kennungen) → 400 mit Klartext, die Zuweisungen bleiben.
  - Hinweise: Format 3 nennt über den Titel zugeordnete Formulare mit ihren bisherigen Zuweisungen; „formulare“: [] warnt,
    welche Zuweisungen gelöst werden; „DEMO“ vorn fällt in jeder Schreibweise weg; mat_formular lässt sich nicht per
    INSERT OR REPLACE ersetzen und seine Kennung nicht ändern.
Alle Namen, Hersteller und Prüfpunkte sind Platzhalter."""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import H, anmelden, katalog_grund, make_app  # noqa: E402
from test_material_katalog import importieren  # noqa: E402

API = "/api/material"
FORMAT = "stroemis-material-katalog"


def punkt(text):
    return [{"text": text, "art": "yesno", "soll": "ja"}]


def pool_neu(c, kategorie, titel, punkte):
    r = c.post(f"{API}/formular-pool", json={"kategorie_id": kategorie, "titel": titel, "punkte": punkte})
    assert r.status_code == 201, r.get_json()
    assert c.post(f"{API}/formulare/{r.json['formular']['id']}/aktivieren", json={}).status_code == 200
    return r.json["formular"]["formular_id"]


def zuweisen(c, pf, kategorien=(), produkte=()):
    r = c.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": list(kategorien), "produkte": list(produkte)})
    assert r.status_code == 200, r.get_json()


def produkt_neu(c, kategorie, modell, nr):
    r = c.post(f"{API}/produkte", json={"category_id": kategorie, "manufacturer": "Testwerk", "model": modell,
                                        "article_no": nr, "material_kind": "metall_hardware", "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


def geltend(c, pid):
    """(Titel, Art, Prüfpunkte, Formular) des Formulars, das für das Produkt gilt – oder None."""
    f = c.get(f"{API}/produkte/{pid}").json["produkt"]["formular"]
    if not f:
        return None
    punkte = [x["text"] for x in c.get(f"{API}/formulare/{f['id']}").json["formular"]["punkte"]]
    return f["title"], f["art"], punkte, f["formular"]["id"]


def aufbau(tmp):
    """Karabiner mit dem Standard „Karabinerprüfung“ (Punkt „Standardpunkt“), Produkte P1–P3 und HMS Beta."""
    app = make_app(tmp)
    c = anmelden(app, "admin@example.org", "geheim123")
    ids = katalog_grund(c)
    for n in (1, 2, 3):
        ids[f"p{n}"] = produkt_neu(c, ids["karabiner"], f"Platzhalter P{n}", f"P{n}")
    ids["s"] = pool_neu(c, ids["karabiner"], "Karabinerprüfung", punkt("Standardpunkt"))
    zuweisen(c, ids["s"], kategorien=[ids["karabiner"]])
    return app, c, ids


def datei(formular, version=2, **mehr):
    return json.dumps(dict({"format": FORMAT, "version": version, "kategorien": [], "produkte": [],
                            "formulare": [formular]}, **mehr)).encode()


def fuer_produkt(n, titel, punkte, **mehr):
    return datei(dict({"produkt": {"hersteller": "Testwerk", "modell": f"Platzhalter P{n}", "artikelnummer": f"P{n}"},
                       "titel": titel, "punkte": punkte}, **mehr))


def fuer_kategorie(titel, punkte):
    return datei({"kategorie": ["PSA gegen Absturz", "Karabiner"], "titel": titel, "punkte": punkte})


def stand(c, ids):
    return {n: geltend(c, ids[n]) for n in ("p1", "p2", "p3", "hms")}


def versionen(app, pf):
    with app.app_context():
        from app import db
        return db.query("SELECT COUNT(*) AS n FROM mat_form WHERE formular_id = ?", (pf,), one=True)["n"]


def zweimal(c, roh):
    """Import und gleich noch einmal: Der zweite ändert nichts. Liefert den Bericht des ersten."""
    ber = importieren(c, roh, False, "katalog.json")
    assert ber["gespeichert"] and not ber["fehler"], ber
    nochmal = importieren(c, roh, False, "katalog.json")
    assert nochmal["gespeichert"] and not nochmal["fehler"], nochmal
    assert nochmal["formulare"]["neu"] == 0 and not nochmal["aenderungen"], nochmal
    assert nochmal["zuweisungen"]["neu"] == 0 and nochmal["zuweisungen"]["geloest"] == 0, nochmal
    return ber


def test_fall_1_gleicher_titel_wie_der_standard():
    """Der Titel des spezifischen Formulars gleicht dem Standard: P1 bekommt ein neues, der Standard bleibt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        vorher = stand(c, ids)
        ber = zweimal(c, fuer_produkt(1, "Karabinerprüfung", punkt("Nur für P1")))
        nachher = stand(c, ids)
        for n in ("p2", "p3", "hms"):
            assert nachher[n] == vorher[n] == ("Karabinerprüfung", "standard", ["Standardpunkt"], ids["s"]), nachher
        assert nachher["p1"][:3] == ("Karabinerprüfung", "zugewiesen", ["Nur für P1"]) and nachher["p1"][3] != ids["s"]
        assert versionen(app, ids["s"]) == 1
        assert any("gilt nicht nur für Produkt „Testwerk Platzhalter P1“ (Standard für „PSA gegen Absturz / Karabiner“)"
                   in h and "bleibt unverändert" in h for h in ber["hinweise"]), ber["hinweise"]
        assert "Formular „Karabinerprüfung“ (Produkt „Testwerk Platzhalter P1“): neue Version 1, aktiv – neu im Pool" in \
            ber["aenderungen"], ber["aenderungen"]
    print("Fall 1 bestanden.")


def test_fall_2_und_3_produkt_hat_den_standard_ausdruecklich():
    """P3 hat den Standard ausdrücklich zugewiesen (Z3): Das spezifische Formular kommt neu in den Pool – auch als
    Entwurf („aktivieren“: false) landet es nicht im Standard."""
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        zuweisen(c, ids["s"], kategorien=[ids["karabiner"]], produkte=[ids["p3"]])
        vorher = stand(c, ids)
        zweimal(c, fuer_produkt(3, "Spezial P3", punkt("Nur für P3"), aktivieren=False))
        assert stand(c, ids) == vorher and versionen(app, ids["s"]) == 1
        ber = zweimal(c, fuer_produkt(3, "Spezial P3", punkt("Nur für P3")))
        nachher = stand(c, ids)
        for n in ("p1", "p2", "hms"):
            assert nachher[n] == vorher[n], nachher
        assert nachher["p3"][:3] == ("Spezial P3", "zugewiesen", ["Nur für P3"]) and nachher["p3"][3] != ids["s"]
        assert versionen(app, ids["s"]) == 1
        # Der Entwurf aus dem ersten Import ist das Formular, das jetzt gilt (über den Titel, es galt für nichts).
        assert ber["formulare"] == {"neu": 0, "unveraendert": 1}, ber
        assert any("Version 1 aktiviert – bisher nirgends zugewiesen" in z for z in ber["aenderungen"]), ber["aenderungen"]
    print("Fall 2 und 3 bestanden.")


def test_fall_4_eigenes_formular():
    """Ein Formular, das nur diesem Produkt gilt, bekommt die neue Version (wie bisher); der Bericht sagt, wofür es gilt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        eigen = pool_neu(c, ids["karabiner"], "Eigen P1", punkt("Eigen"))
        zuweisen(c, eigen, produkte=[ids["p1"]])
        vorher = stand(c, ids)
        ber = zweimal(c, fuer_produkt(1, "Eigen P1", punkt("Eigen neu")))
        nachher = stand(c, ids)
        assert nachher["p1"] == ("Eigen P1", "zugewiesen", ["Eigen neu"], eigen), nachher
        assert all(nachher[n] == vorher[n] for n in ("p2", "p3", "hms")), nachher
        assert ("Formular „Eigen P1“ (Produkt „Testwerk Platzhalter P1“): neue Version 2, aktiv – gilt bisher: "
                "zugewiesen an „Testwerk Platzhalter P1“") in ber["aenderungen"], ber["aenderungen"]
    print("Fall 4 bestanden.")


def test_fall_5_kategorie_mit_titel_eines_eigenen_formulars():
    """Ein „kategorie“-Eintrag mit dem Titel des eigenen Formulars von P1 schreibt es nicht um, sondern den Standard der
    Kategorie (er gilt nur ihr); trägt der Standard auch eine Zuweisung an ein Produkt, kommt ein neuer Standard."""
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        eigen = pool_neu(c, ids["karabiner"], "Sichtprüfung", punkt("Nur P1 eigen"))
        zuweisen(c, eigen, produkte=[ids["p1"]])
        ber = zweimal(c, fuer_kategorie("Sichtprüfung", punkt("Generisch neu")))
        nachher = stand(c, ids)
        assert nachher["p1"] == ("Sichtprüfung", "zugewiesen", ["Nur P1 eigen"], eigen), nachher
        for n in ("p2", "p3", "hms"):
            assert nachher[n] == ("Sichtprüfung", "standard", ["Generisch neu"], ids["s"]), nachher
        assert versionen(app, eigen) == 1
        assert ("Formular „Sichtprüfung“ (Kategorie „PSA gegen Absturz / Karabiner“): neue Version 2, aktiv – gilt "
                "bisher: Standard für „PSA gegen Absturz / Karabiner“") in ber["aenderungen"], ber["aenderungen"]
        # Der Standard gilt zusätzlich ausdrücklich für P2 (Z3): Er bleibt, die Kategorie bekommt einen neuen.
        zuweisen(c, ids["s"], kategorien=[ids["karabiner"]], produkte=[ids["p2"]])
        ber = zweimal(c, fuer_kategorie("Sichtprüfung", punkt("Generisch neuer")))
        nachher = stand(c, ids)
        assert nachher["p2"] == ("Sichtprüfung", "zugewiesen", ["Generisch neu"], ids["s"]), nachher
        assert nachher["p3"][:3] == ("Sichtprüfung", "standard", ["Generisch neuer"]) and nachher["p3"][3] not in (
            ids["s"], eigen), nachher
        assert nachher["p1"][3] == eigen and versionen(app, ids["s"]) == 2
        assert any("gilt nicht nur für Kategorie" in h for h in ber["hinweise"]), ber["hinweise"]
    print("Fall 5 bestanden.")


def test_zuweisung_kaputter_rumpf():
    """Befund 2: 400 statt alle Zuweisungen zu lösen."""
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        zuweisen(c, ids["s"], kategorien=[ids["karabiner"]], produkte=[ids["p3"]])
        url = f"{API}/formular-pool/{ids['s']}/zuweisung"

        def zuweisungen():
            with app.app_context():
                from app import db
                return [(r["category_id"], r["product_id"]) for r in db.query(
                    "SELECT category_id, product_id FROM mat_formular_zuweisung ORDER BY id")]
        vorher = zuweisungen()
        assert vorher == [(ids["karabiner"], None), (None, ids["p3"])], vorher
        for rumpf in ([1, 2], [], None, "x", {}, {"produkte": [ids["p3"]]}, {"kategorien": [ids["karabiner"]]},
                      {"kategorien": ids["karabiner"], "produkte": []}, {"kategorien": [], "produkte": None},
                      {"kategorien": [], "produkte": ["abc"]}, {"kategorien": [True], "produkte": []}):
            r = c.put(url, data=json.dumps(rumpf), headers=dict(H, **{"Content-Type": "application/json"}))
            assert r.status_code == 400, (rumpf, r.status_code, r.get_json())
            assert r.json["error"], r.json
            assert zuweisungen() == vorher, rumpf
        r = c.put(url, json={"produkte": []})
        assert r.json["error"].startswith("Bitte „kategorien“ und „produkte“ als Listen"), r.json
        r = c.put(url, data="kaputt{", headers=dict(H, **{"Content-Type": "application/json"}))
        assert r.status_code == 400 and zuweisungen() == vorher, (r.status_code, r.get_json())
        # Leere Listen sind eine vollständige Menge: alles gelöst.
        r = c.put(url, json={"kategorien": [], "produkte": []})
        assert r.status_code == 200 and r.json["geaendert"] == 2 and zuweisungen() == [], r.get_json()
    print("Zuweisung mit kaputtem Rumpf bestanden.")


def test_format_3_hinweise():
    """Hinweis 1: über den Titel zugeordnet – mit bisherigen Zuweisungen und in der Zahl am Ende. Hinweis 2: eine Datei ohne
    Formulare warnt, welche Zuweisungen sie löst."""
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        eigen = pool_neu(c, ids["karabiner"], "Sichtprüfung", punkt("Nur P1 eigen"))
        zuweisen(c, eigen, produkte=[ids["p1"]])
        kategorien = [{"name": "PSA gegen Absturz", "unterkategorien": [{"name": "Karabiner"}]}]
        roh = datei({"uid": "c" * 32, "kategorie": ["PSA gegen Absturz", "Karabiner"], "titel": "Sichtprüfung",
                     "punkte": punkt("Generisch neu"), "standard_fuer": [{"kategorie": ["PSA gegen Absturz", "Karabiner"]}],
                     "zugewiesen": []}, version=3, kategorien=kategorien)
        ber = importieren(c, roh, True, "katalog.json")
        assert not ber["fehler"], ber
        assert any("über den Titel dem Prüfformular hier im Pool von „PSA gegen Absturz / Karabiner“ zugeordnet – es "
                   "übernimmt die Katalogkennung der Datei; bisher zugewiesen an „Testwerk Platzhalter P1“." in h
                   for h in ber["hinweise"]), ber["hinweise"]
        assert any(h.startswith("1 Prüfformular gab es hier schon") for h in ber["hinweise"]), ber["hinweise"]
        # „formulare“: [] – die Datei ist maßgeblich (E2): Standard der Karabiner wird gelöst, das sagt eine Warnung.
        roh = json.dumps({"format": FORMAT, "version": 3, "kategorien": kategorien, "produkte": [],
                          "formulare": []}).encode()
        ber = importieren(c, roh, True, "katalog.json")
        assert not ber["fehler"] and ber["zuweisungen"]["geloest"] == 1, ber
        assert ber["warnungen"] == [
            "Die Datei enthält keine Prüfformulare. Weil sie maßgeblich ist, löst der Import 1 Zuweisung an ihre "
            "Kategorien und Produkte: „Karabinerprüfung“ an Kategorie „PSA gegen Absturz / Karabiner“. Diese Produkte "
            "fallen auf den Standard darüber zurück oder sind danach nicht prüfbar."], ber["warnungen"]
        assert geltend(c, ids["p2"])[3] == ids["s"]                                       # Probelauf: nichts gespeichert
        # Mit Formularen in der Datei keine solche Warnung.
        roh = datei({"uid": "c" * 32, "kategorie": ["PSA gegen Absturz", "Karabiner"], "titel": "Anders",
                     "punkte": punkt("Anders"), "standard_fuer": [], "zugewiesen": []}, version=3, kategorien=kategorien)
        ber = importieren(c, roh, True, "katalog.json")
        assert not ber["fehler"] and ber["zuweisungen"]["geloest"] == 1 and not ber["warnungen"], ber
    print("Hinweise Format 3 bestanden.")


def test_demo_vorn_und_trigger():
    """Hinweis 4: „DEMO“ vorn in jeder Schreibweise; Hinweis 3: mat_formular nicht ersetzen, Kennung nicht ändern."""
    from app.material.services.importer import ohne_demo
    for roh, titel in (("DEMO – Gurt", "Gurt"), ("demo - klein", "klein"), ("Demo – Karabiner", "Karabiner"),
                       ("DEMO-Gurt", "Gurt"), ("dEmO Seil", "Seil"), ("Demonstration Seil", "Demonstration Seil"),
                       ("Gurt DEMO", "Gurt DEMO")):
        assert ohne_demo(roh) == titel, (roh, ohne_demo(roh))
    with tempfile.TemporaryDirectory() as tmp:
        app, c, ids = aufbau(tmp)
        with app.app_context():
            from app import db
            conn = db.get_db()
            vorher = conn.execute("SELECT * FROM mat_formular").fetchall()
            for fk in (0, 1):
                conn.execute(f"PRAGMA foreign_keys = {fk}")
                for sql, args in (
                        ("INSERT OR REPLACE INTO mat_formular (id, category_id, created_at, updated_at) "
                         "VALUES (?, ?, 'x', 'x')", (ids["s"], ids["gurte"])),
                        ("REPLACE INTO mat_formular (id, category_id, created_at, updated_at) VALUES (?, ?, 'x', 'x')",
                         (ids["s"], ids["karabiner"])),
                        ("UPDATE mat_formular SET id = 999 WHERE id = ?", (ids["s"],))):
                    try:
                        conn.execute(sql, args)
                        raise AssertionError(sql)
                    except sqlite3.IntegrityError as exc:
                        assert "Prüfformulare lassen sich nicht ersetzen" in str(exc), exc
                    conn.rollback()
            assert conn.execute("SELECT * FROM mat_formular").fetchall() == vorher
            assert conn.execute("SELECT COUNT(*) FROM mat_formular_zuweisung").fetchone()[0] == 1
        # Die App legt weiter Formulare an.
        pool_neu(c, ids["gurte"], "Neu nach Trigger", punkt("Platzhalter"))
    print("DEMO vorn und Trigger bestanden.")


if __name__ == "__main__":
    test_fall_1_gleicher_titel_wie_der_standard()
    test_fall_2_und_3_produkt_hat_den_standard_ausdruecklich()
    test_fall_4_eigenes_formular()
    test_fall_5_kategorie_mit_titel_eines_eigenen_formulars()
    test_zuweisung_kaputter_rumpf()
    test_format_3_hinweise()
    test_demo_vorn_und_trigger()
    print(json.dumps({"ok": True}))
