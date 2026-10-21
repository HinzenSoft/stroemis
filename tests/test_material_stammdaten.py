"""Tests zu „Seriennummer und Herstelldatum stehen seit der ersten Prüfung fest“ (Modul Material, Nachbesserung vom
21.10.2026):  python tests/test_material_stammdaten.py

Sobald ein Artikel eine abgeschlossene Prüfung hat (completed_at gesetzt – ein Entwurf zählt nicht), lehnt
PUT /api/material/artikel/<id> eine Änderung von Seriennummer oder Herstelldatum mit 409 ab; dieselben Werte im selben
PUT stören nicht. Das gilt auch für eine vom System vergebene STR-Nummer. Der Trigger mat_item_stammdaten_fest
(Schritt 14) fängt, was am Dienst vorbeiginge. Der Dialog „Artikel … bearbeiten“ zeigt beide Felder oben nebeneinander,
bei festen Werten schreibgeschützt. Alle Nummern und Namen hier sind erfunden und nur für den Test da."""
import os
import re
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (abschluss, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pruef_formulare, starten, umgebung)
from test_material_trennung import bis_schritt, endversion  # noqa: E402

# Eine KOPIE einer Datenbank auf Stand 7 für den Pfad 7 → 14 – nur, wenn angegeben; die Quelle bleibt unberührt.
KOPIE_STAND_7 = os.environ.get("MATERIAL_KOPIE_STAND_7") or ""
FEST = "Seriennummer und Herstelldatum stehen seit der ersten Prüfung fest – sie sind Teil des Prüfnachweises."
TRIGGER = "mat_item_stammdaten_fest"


def aufbau(tmp):
    """Umgebung mit Katalog, Formularen, einer Gliederung mit Lager und zwei Karabinern (HMS Beta): einer mit
    Herstellernummer, einer mit vom System vergebener STR-Nummer."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    pruef_formulare(k["katalog"], ids)
    w = k["wart"]
    gid, _ = gliederung(w)
    lager = w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
    eigen = neuer_artikel(w, ids["hms"], lager, serial_no="SD-100a", manufactured_on="2024-03")
    system = neuer_artikel(w, ids["hms"], lager, manufactured_on="2024-03")
    assert system["serial_no"].startswith("STR-"), system
    return app, k, eigen["id"], system["id"]


def lesen(c, iid):
    r = c.get(f"/api/material/artikel/{iid}")
    assert r.status_code == 200, r.get_json()
    return r.json["artikel"]


def aendern(c, iid, **d):
    return c.put(f"/api/material/artikel/{iid}", json=d)


def db_zeile(tmp, iid):
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    conn.row_factory = sqlite3.Row
    try:
        return dict(conn.execute("SELECT * FROM mat_item WHERE id = ?", (iid,)).fetchone())
    finally:
        conn.close()


def test_dienst():
    """Vor der Prüfung und mit Entwurf frei änderbar; nach der ersten abgeschlossenen Prüfung 409 bei jeder echten
    Änderung, 200 bei denselben Werten (auch Groß/klein, leere Seriennummer, weggelassene Felder)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, eigen, system = aufbau(tmp)
        w, p = k["wart"], k["pruefer"]
        a = lesen(w, eigen)
        assert a["stammdaten_fest"] is False, a
        # Vor der ersten Prüfung: beides änderbar.
        r = aendern(w, eigen, serial_no="SD-100", manufactured_on="2024-02")
        assert r.status_code == 200, r.get_json()
        assert (r.json["artikel"]["serial_no"], r.json["artikel"]["manufactured_on"]) == ("SD-100", "2024-02")
        # Ein offener Entwurf zählt nicht.
        r = starten(p, eigen)
        assert r.status_code in (200, 201), r.get_json()
        pid = r.json["pruefung"]["id"]
        assert lesen(w, eigen)["stammdaten_fest"] is False
        r = aendern(w, eigen, serial_no="SD-101", manufactured_on="2024-01")
        assert r.status_code == 200, r.get_json()
        # Abgeschlossen: ab jetzt fest.
        r = abschluss(p, pid, ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        a = lesen(w, eigen)
        assert a["stammdaten_fest"] is True and a["serial_no"] == "SD-101" and a["manufactured_on"] == "2024-01", a
        vorher = db_zeile(tmp, eigen)
        for d in ({"serial_no": "SD-999"}, {"manufactured_on": "2023-12"}, {"manufactured_on": "2024-01-15"},
                  {"manufactured_on": ""}, {"manufactured_on": None},
                  {"serial_no": "SD-999", "manufactured_on": "2024-01"}):
            r = aendern(w, eigen, **d)
            assert r.status_code == 409 and r.json["error"] == FEST, (d, r.status_code, r.get_json())
        assert db_zeile(tmp, eigen) == vorher
        # Dieselben Werte stören nicht – auch nicht in anderer Schreibweise; gespeichert bleibt die bisherige.
        for d in ({"serial_no": "SD-101", "manufactured_on": "2024-01", "notes": "Bemerkung 1"},
                  {"serial_no": "sd-101", "notes": "Bemerkung 2"},
                  {"serial_no": "", "notes": "Bemerkung 3"},
                  {"serial_no": " SD-101 ", "manufactured_on": " 2024-01 ", "notes": "Bemerkung 4"},
                  {"notes": "Bemerkung 5"}):                        # so schickt es der Dialog bei festen Werten
            r = aendern(w, eigen, **d)
            assert r.status_code == 200, (d, r.get_json())
            z = db_zeile(tmp, eigen)
            assert (z["serial_no"], z["manufactured_on"], z["notes"]) == ("SD-101", "2024-01", d["notes"]), z
        # Mit dem Stand aus dem Dialog (stand) wie in der Oberfläche.
        a = lesen(w, eigen)
        r = aendern(w, eigen, stand=a["stand"], purchased_on="2024-04", notes="")
        assert r.status_code == 200 and r.json["artikel"]["purchased_on"] == "2024-04", r.get_json()

        # Vom System vergebene STR-Nummer: vor der Prüfung ersetzt eine Herstellernummer sie …
        r = aendern(w, system, serial_no="SD-200")
        assert r.status_code == 200 and r.json["artikel"]["serial_generated"] is False, r.get_json()
        # … ein anderer Artikel bleibt bei seiner STR-Nummer, wird geprüft, und danach ist auch sie fest.
        anderer = neuer_artikel(w, a["product_id"], a["folder_id"], manufactured_on="2024-03")
        str_nr = anderer["serial_no"]
        r = starten(p, anderer["id"])
        assert abschluss(p, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        r = aendern(w, anderer["id"], serial_no="SD-300")
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        for d in ({"serial_no": ""}, {"serial_no": str_nr}, {"serial_no": str_nr.lower()}):
            r = aendern(w, anderer["id"], notes="ok", **d)
            assert r.status_code == 200, (d, r.get_json())
            z = db_zeile(tmp, anderer["id"])
            assert (z["serial_no"], z["serial_generated"]) == (str_nr, 1), z
        assert lesen(w, anderer["id"])["stammdaten_fest"] is True
        assert app
    print("Dienst bestanden.")


def test_trigger():
    """Der Trigger fängt eine Änderung an der Datenbank vorbei – nur nach einer abgeschlossenen Prüfung, nur bei einem
    anderen Wert. Über die Schnittstelle käme er als 409 an (Fehlerbehandler für Integritätsfehler)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, eigen, system = aufbau(tmp)
        p = k["pruefer"]
        r = starten(p, eigen)
        pid = r.json["pruefung"]["id"]
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            # Entwurf: noch frei.
            conn.execute("UPDATE mat_item SET serial_no = 'SD-Entwurf', manufactured_on = '2024-02' WHERE id = ?",
                         (eigen,))
            conn.execute("UPDATE mat_item SET serial_no = 'SD-100a', manufactured_on = '2024-03' WHERE id = ?", (eigen,))
            conn.commit()
        finally:
            conn.close()
        assert abschluss(p, pid, ergebnis="einsatzbereit").status_code == 200
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            for befehl in ("UPDATE mat_item SET serial_no = 'SD-anders' WHERE id = ?",
                           "UPDATE mat_item SET serial_no = 'sd-100A' WHERE id = ?",          # auch Groß/klein
                           "UPDATE mat_item SET manufactured_on = '2024-03-01' WHERE id = ?",
                           "UPDATE mat_item SET manufactured_on = NULL WHERE id = ?"):
                try:
                    conn.execute(befehl, (eigen,))
                    raise AssertionError(befehl)
                except sqlite3.IntegrityError as e:
                    assert "seit der ersten Prüfung fest" in str(e), e
            # Derselbe Wert und andere Spalten gehen durch; der ungeprüfte Artikel bleibt frei.
            conn.execute("UPDATE mat_item SET serial_no = serial_no, manufactured_on = manufactured_on, notes = 'x' "
                         "WHERE id = ?", (eigen,))
            conn.execute("UPDATE mat_item SET serial_no = 'SD-frei', manufactured_on = NULL WHERE id = ?", (system,))
            conn.commit()
        finally:
            conn.close()
        assert (db_zeile(tmp, eigen)["serial_no"], db_zeile(tmp, system)["serial_no"]) == ("SD-100a", "SD-frei")
        assert app
    print("Trigger bestanden.")


def _schema(pfad):
    conn = sqlite3.connect(pfad)
    try:
        version = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0]
        trigger = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger' "
                                              "AND tbl_name = 'mat_item'")}
        return version, trigger
    finally:
        conn.close()


def _tabellen(pfad):
    conn = sqlite3.connect(pfad)
    try:
        return {n: conn.execute(f"SELECT * FROM {n} ORDER BY rowid").fetchall() for (n,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat%' AND name NOT LIKE '%fts%'")}
    finally:
        conn.close()


def test_migration_14():
    """Frisch, 13 → 14 (Trigger entfernt, Version 13; Daten unverändert), zweiter Lauf ohne Änderung; 7 → 14 aus einer
    Kopie (wenn angegeben)."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger = _schema(pfad)
        assert version == "14" == endversion() and TRIGGER in trigger, (version, trigger)
        conn = sqlite3.connect(pfad)
        conn.execute("INSERT INTO mat_meta (schluessel, wert) VALUES ('probe', 'x')")
        conn.execute(f"DROP TRIGGER {TRIGGER}")
        conn.execute("UPDATE mat_meta SET wert = '13' WHERE schluessel = 'schema_version'")
        conn.commit()
        conn.close()
        stand = _tabellen(pfad)
        make_app(tmp)
        version, trigger = _schema(pfad)
        assert version == "14" and TRIGGER in trigger, (version, trigger)
        nachher = _tabellen(pfad)
        for t in (stand, nachher):
            t["mat_meta"] = [r for r in t["mat_meta"] if r[0] != "schema_version"]
        assert nachher == stand
        conn = sqlite3.connect(pfad)
        assert models.migrieren(conn) == models.SCHEMA_VERSION == 14
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_14(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
        assert app
    if KOPIE_STAND_7 and os.path.exists(KOPIE_STAND_7):
        with tempfile.TemporaryDirectory() as tmp13, tempfile.TemporaryDirectory() as tmp14:
            for d in (tmp13, tmp14):
                shutil.copyfile(KOPIE_STAND_7, os.path.join(d, "stroemis.db"))
            bis_schritt(13)(make_app, tmp13)
            make_app(tmp14)
            v13, t13 = _schema(os.path.join(tmp13, "stroemis.db"))
            v14, t14 = _schema(os.path.join(tmp14, "stroemis.db"))
            assert (v13, v14) == ("13", "14") and TRIGGER not in t13 and t14 == t13 | {TRIGGER}, (v13, v14, t13, t14)
            vorher, nachher = _tabellen(os.path.join(tmp13, "stroemis.db")), _tabellen(os.path.join(tmp14, "stroemis.db"))
            for t in (vorher, nachher):
                t["mat_meta"] = [r for r in t["mat_meta"] if r[0] != "schema_version"]
            # Nur Zahlen vergleichen: Migrationsläufe schreiben Zeitstempel (Journal „Migration Schritt …“).
            assert {n: len(z) for n, z in vorher.items()} == {n: len(z) for n, z in nachher.items()}
            assert len(nachher["mat_item"]) > 0
            # Auf den echten Daten: Ein geprüfter Artikel ist fest, ein ungeprüfter (falls es einen gibt) nicht.
            conn = sqlite3.connect(os.path.join(tmp14, "stroemis.db"))
            try:
                geprueft = conn.execute("SELECT item_id FROM mat_inspection WHERE completed_at IS NOT NULL "
                                        "LIMIT 1").fetchone()
                if geprueft:
                    try:
                        conn.execute("UPDATE mat_item SET serial_no = serial_no || '-x' WHERE id = ?", geprueft)
                        raise AssertionError("Trigger fehlt")
                    except sqlite3.IntegrityError:
                        pass
            finally:
                conn.close()
        print("Migration 7 → 14 aus der Kopie bestanden.")
    else:
        print("Migration 7 → 14 übersprungen (MATERIAL_KOPIE_STAND_7 nicht gesetzt).")
    print("Migration 14 bestanden.")


def test_oberflaeche_statisch():
    """material.js: Seriennummer und Herstellung oben nebeneinander im Dialog „Artikel … bearbeiten“ (vor Kauf,
    Erstgebrauch, Intervall), bei stammdaten_fest schreibgeschützt mit Hinweis und nicht im PUT; das Anlegen bleibt, wie
    es war. material.css: die Zeile bleibt auch schmal (unter 480 px) zweispaltig."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    start = js.index("function artikelDialog(a)")
    dlg = js[start:js.index("/* --- Artikel anlegen", start)]
    assert "const fest = !!a.stammdaten_fest;" in dlg
    # Ganz oben: die erste Feldzeile nach der Überschrift trägt Seriennummer und Herstellung.
    kopf = dlg[dlg.index("bearbeiten</h2>"):]
    assert re.match(r'bearbeiten</h2>\s*<div class="field-row mat-stammzeile\$\{fest \? " mat-fest" : ""\}"><div>\$\{sn\}'
                    r'</div><div>\$\{herst\}</div></div>', kopf), kopf[:300]
    zeilen = {z: dlg.index(z) for z in ("const sn = fest", "const herst = fest")}
    sn = dlg[zeilen["const sn = fest"]:zeilen["const herst = fest"]]
    herst = dlg[zeilen["const herst = fest"]:dlg.index("dialog(`")]
    # Fest: schreibgeschützt mit sichtbarem Wert; offen: wie bisher mit dem Hinweis zur STR-Nummer.
    assert re.search(r'\? `<label for="ad-sn">Seriennummer[^`]*</label><input type="text" id="ad-sn" readonly '
                     r'value="\$\{esc\(a\.serial_no\)\}">`', sn), sn
    assert re.search(r'\? `<label for="ad-herst">Herstellung \(Monat\)</label><input type="text" id="ad-herst" '
                     r'class="mat-datum" readonly value="\$\{esc\(datumAnzeige\(a\.manufactured_on, "monat"\)\)\}"', herst), herst
    assert 'datumFeld("ad-herst", a.manufactured_on, "monat")' in herst and "TASTATUR_NUMMER" in sn
    assert "Seit der ersten Prüfung fest – Teil des Prüfnachweises." in dlg
    assert "Leer lassen behält die Nummer. Eine echte Herstellernummer ersetzt die vom System vergebene." in dlg
    # Der PUT schickt Seriennummer und Herstellung nur, solange sie nicht fest sind.
    daten = dlg[dlg.index("daten = { stand: a.stand"):dlg.index("} catch (e) { toast(e.message, true); return; }")]
    assert "serial_no" not in daten.split("if (!fest) {")[0] and "manufactured_on" not in daten.split("if (!fest) {")[0]
    assert re.search(r"if \(!fest\) \{\s*daten\.serial_no = \$\(\"#ad-sn\", body\)\.value;\s*"
                     r"daten\.manufactured_on = behalten\(", daten), daten
    # Reihenfolge im Dialog: Seriennummer/Herstellung, dann Kauf, Erstgebrauch, Intervall, Fälligkeit, Lebensende, Bemerkung.
    folge = [kopf.index(x) for x in ("mat-stammzeile", '"ad-kauf"', '"ad-erst"', 'id="ad-int"', '"ad-due"', '"ad-ende"',
                                     'id="ad-notes"')]
    assert folge == sorted(folge), folge
    # Anlegen unverändert: eigenes Formular, Seriennummer über die volle Breite, Herstellung neben Kauf.
    neu = js[js.index("async function artikelNeu()"):]
    assert '<label for="an-sn">Seriennummer des Herstellers</label><input type="text" id="an-sn"' in neu
    assert re.search(r'<div class="field-row"><div><label for="an-herst">Herstellung \(Monat\)</label>\$\{datumFeld\("an-herst"'
                     r'[^\n]*\n\s*<div><label for="an-kauf">', neu)
    assert "mat-stammzeile" not in neu[:neu.index("async function anlegen(")]
    # CSS: zweispaltig auch unter 480 px (überschreibt die Regel aus app.css), feste Felder grau hinterlegt.
    assert ".field-row.mat-stammzeile { align-items: end; }" in css
    assert ("@media (max-width: 480px) { .field-row.mat-stammzeile { grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); } }"
            in css)
    assert ".mat-fest input[readonly] {" in css
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_dienst()
    test_trigger()
    test_migration_14()
    test_oberflaeche_statisch()
