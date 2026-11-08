"""Untergruppen in Prüfformularen (Schritt 39, Wunsch vom 04.11.2026; Bauauftrag planung/untergruppen/auftrag.md):
python tests/test_material_untergruppen.py  oder  pytest tests/test_material_untergruppen.py

Entscheidungen: eine Ebene (Gruppe › Untergruppe › Prüfpunkte); gemischt erlaubt – Punkte ohne Untergruppe stehen am
Anfang der Gruppe, danach die Untergruppen; Prüfung und Prüfprotokoll zeigen die Untergruppe als kleinere
Zwischenüberschrift, die Punkte darunter eingezogen; der Editor wie Gruppen eine Stufe tiefer.
1. Dienst: Normalisierung wie „gruppe“ (eine Zeile, 80 Zeichen, fehlt = leer), Reihenfolge-Regel (in jedem Gruppenblock
   erst ohne Untergruppe, dann die Untergruppen als zusammenhängende Blöcke in der Reihenfolge ihres ersten Punkts;
   getrennte Gruppenblöcke bleiben getrennt; ohne Untergruppen unverändert), Journal.
2. Schnittstelle: PUT …/formulare/<id> mit „untergruppe“ je Punkt, GET geordnet, neue Version und Kopie übernehmen sie,
   Katalog-Export (Format 3, Feld „untergruppe“) und Import in eine zweite Anlage rund, zweiter Import ändert nichts, eine
   geänderte Untergruppe gibt eine neue Version, eine ältere Datei ohne das Feld kommt mit leerer Untergruppe herein.
3. Prüfung: die Befundzeilen tragen eine Kopie; Berichtigung kopiert sie; PDF mit Zwischenzeile und eingezogenen
   Punkten; ein festgeschriebenes Protokoll bleibt unverändert (Datei, Prüfsumme, Befundzeilen), wenn das Formular
   später andere Untergruppen bekommt; die Kopie in einer abgeschlossenen Prüfung ist per SQL unveränderlich.
4. Migration 38 → 39: frisch; Altbestand von Stand 38 (Formulare mit Gruppen, festgeschriebene Prüfung mit PDF) – Spalten
   mit '' dazu, sonst nichts verändert, Trigger da, Protokoll unverändert; zweiter Lauf ändert nichts.
5. Browser (1280 Maus, 360 Touch): Untergruppe anlegen, umbenennen, Punkte hinein und heraus ziehen, Untergruppe
   innerhalb einer Gruppe und in eine andere ziehen, entfernen (Rückfrage mit Anzahl), „+ Prüfpunkt“ je Untergruppe,
   „Nach oben/unten“ und „In Gruppe verschieben“ über Untergruppen, Pflicht eines Namens beim (seit 06.11.2026
   automatischen) Speichern – am Feld, ohne den Fokus zu nehmen –, Speichern in der Datenbank, Getipptes bleibt bei jedem Neuzeichnen, Nur-Lese-Ansicht und Prüfungsansicht mit Zwischenüberschrift;
   Tippflächen am Finger gemessen (≥ 44 px, Tipp auf die Mitte trifft), kein waagerechter Bildlauf, keine
   Konsolenfehler. Ohne Chromium „übersprungen“ mit rc 0.
Alle Inhalte sind Platzhalter."""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import (_heute, abschluss, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pdf_layout_seiten, starten, umgebung)
from test_material_katalog import exportieren, importieren, katalogjson, umschreiben  # noqa: E402

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GA, GB = "Platzhalter Gruppe A", "Platzhalter Gruppe B"
UK, UN = "Platzhalter UG Körper", "Platzhalter UG Nase"
# Ungeordnet geschickt: K1 vor D1, K2 nach N1 – der Server ordnet (Entscheidung 2).
UNGEORDNET = [
    {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K1", "art": "yesno", "soll": "ja"},
    {"gruppe": GA, "text": "Platzhalter D1", "art": "yesno", "soll": "ja"},
    {"gruppe": GA, "untergruppe": "  Platzhalter UG\tNase ", "text": "Platzhalter N1", "art": "text", "pflicht": False},
    {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K2", "art": "yesno", "soll": "nein"},
    {"gruppe": GA, "untergruppe": "", "text": "Platzhalter D2", "art": "number"},
    {"gruppe": GB, "text": "Platzhalter B1", "art": "yesno", "soll": "ja"},
]
GEORDNET = [(GA, "", "Platzhalter D1"), (GA, "", "Platzhalter D2"), (GA, UK, "Platzhalter K1"), (GA, UK, "Platzhalter K2"),
            (GA, UN, "Platzhalter N1"), (GB, "", "Platzhalter B1")]


def ordnung(punkte):
    return [(p["gruppe"], p["untergruppe"], p["text"]) for p in punkte]


def pool_neu(c, kategorie, titel, punkte, aktivieren=True):
    r = c.post(f"{API}/formular-pool", json={"kategorie_id": kategorie, "titel": titel, "punkte": punkte})
    assert r.status_code == 201, r.get_json()
    f = r.json["formular"]
    if aktivieren:
        assert c.post(f"{API}/formulare/{f['id']}/aktivieren", json={}).status_code == 200
    return f["formular_id"], f["id"]


# --- 1. Dienst -----------------------------------------------------------------------------------------------------

def test_dienst():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        with app.app_context():
            from app.material.services import Abgelehnt
            from app.material.services.katalog import punkte_pruefen
            out = punkte_pruefen(UNGEORDNET)
            assert [(p["group_name"], p["untergruppe"], p["label"]) for p in out] == GEORDNET, out
            assert [p["position"] for p in out] == [1, 2, 3, 4, 5, 6]
            # Ohne Untergruppen (und ohne das Feld): genau wie vorher, getrennte Gruppenblöcke bleiben getrennt.
            alt = [{"gruppe": "G1", "text": "a", "art": "text"}, {"gruppe": "G2", "text": "b", "art": "text"},
                   {"gruppe": "G1", "text": "c", "art": "text"}, {"text": "d", "art": "text"}]
            out = punkte_pruefen(alt)
            assert [(p["group_name"], p["untergruppe"], p["label"], p["position"]) for p in out] == [
                ("G1", "", "a", 1), ("G2", "", "b", 2), ("G1", "", "c", 3), ("", "", "d", 4)]
            # Untergruppen in getrennten Blöcken gleicher Gruppe werden nicht zusammengezogen.
            out = punkte_pruefen([{"gruppe": "G1", "untergruppe": "U", "text": "a", "art": "text"},
                                  {"gruppe": "G2", "text": "b", "art": "text"},
                                  {"gruppe": "G1", "text": "c", "art": "text"},
                                  {"gruppe": "G1", "untergruppe": "U", "text": "d", "art": "text"}])
            assert [(p["group_name"], p["untergruppe"], p["label"]) for p in out] == [
                ("G1", "U", "a"), ("G2", "", "b"), ("G1", "", "c"), ("G1", "U", "d")]
            # Eine Untergruppe ohne Gruppe (Block ohne Namen) geht auch.
            out = punkte_pruefen([{"untergruppe": "U", "text": "a", "art": "text"}, {"text": "b", "art": "text"}])
            assert [(p["group_name"], p["untergruppe"], p["label"]) for p in out] == [("", "", "b"), ("", "U", "a")]
            # Wie „gruppe“: 80 Zeichen, Text, Steuerzeichen raus.
            assert punkte_pruefen([{"untergruppe": "x" * 80, "text": "a", "art": "text"}])[0]["untergruppe"] == "x" * 80
            assert punkte_pruefen([{"untergruppe": "a\x01\nb", "text": "a", "art": "text"}])[0]["untergruppe"] == "a b"
            assert punkte_pruefen([{"untergruppe": None, "text": "a", "art": "text"}])[0]["untergruppe"] == ""
            for falsch, satz in (("x" * 81, "Untergruppe von Prüfpunkt 2“ ist zu lang"), (7, "Untergruppe von Prüfpunkt 2“ muss Text sein"),
                                 (["U"], "muss Text sein")):
                try:
                    punkte_pruefen([{"text": "a", "art": "text"}, {"untergruppe": falsch, "text": "b", "art": "text"}])
                    raise AssertionError(falsch)
                except Abgelehnt as exc:
                    assert satz in str(exc), exc
    print("Dienst bestanden.")


# --- 2. Schnittstelle, Versionen, Export und Import -----------------------------------------------------------------

def test_schnittstelle_und_transfer():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app, k = umgebung(tmp_a)
        ids = katalog_grund(k["adm"])
        kp = k["katalog"]
        pf, fid = pool_neu(kp, ids["gurte"], "Platzhalter Untergruppen", [{"text": "Platzhalter", "art": "text"}], False)
        r = kp.put(f"{API}/formulare/{fid}", json={"punkte": UNGEORDNET})
        assert r.status_code == 200, r.get_json()
        f = kp.get(f"{API}/formulare/{fid}").json["formular"]
        assert ordnung(f["punkte"]) == GEORDNET and [p["position"] for p in f["punkte"]] == [1, 2, 3, 4, 5, 6]
        with app.app_context():
            from app import db
            zeilen = db.query("SELECT group_name, untergruppe, label FROM mat_checklist_item WHERE form_id = ? "
                              "ORDER BY position", (fid,))
            assert [tuple(z.values()) if isinstance(z, dict) else tuple(z) for z in zeilen] == GEORDNET
            journal = db.query("SELECT after_json FROM mat_audit WHERE entity = 'form' AND entity_id = ? ORDER BY id DESC "
                               "LIMIT 1", (fid,), one=True)
        punkte_journal = json.loads(journal["after_json"])["punkte"]
        assert punkte_journal[2].startswith(f"{GA} › {UK}: Platzhalter K1 [yesno"), punkte_journal
        assert punkte_journal[0].startswith(f"{GA}: Platzhalter D1"), punkte_journal
        # Ohne Gruppe, mit Untergruppe: nur die Untergruppe vorn. Seit dem automatischen Speichern (06.11.2026) schreibt
        # dieselbe Person binnen zehn Minuten keinen zweiten Eintrag – der Rest kommt beim nächsten Schritt an der Version
        # (hier direkt über katalog.journal_nachziehen) in ihrem Namen dazu.
        r = kp.put(f"{API}/formulare/{fid}", json={"punkte": UNGEORDNET + [{"untergruppe": "U", "text": "x", "art": "text"}]})
        assert r.status_code == 200
        with app.app_context():
            from app import db
            from app.material.services import katalog
            zahl = db.query("SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'form' AND entity_id = ?", (fid,), one=True)["n"]
            with db.transaction():
                assert katalog.journal_nachziehen(fid)
            j = db.query("SELECT after_json FROM mat_audit WHERE entity = 'form' AND entity_id = ? ORDER BY id DESC LIMIT 1",
                         (fid,), one=True)
            assert db.query("SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'form' AND entity_id = ?", (fid,), one=True)["n"] == zahl + 1
        assert json.loads(j["after_json"])["punkte"][-1].startswith("U: x ["), j
        assert kp.put(f"{API}/formulare/{fid}", json={"punkte": UNGEORDNET}).status_code == 200
        # Zu lang: Fehler mit Stelle.
        r = kp.put(f"{API}/formulare/{fid}", json={"punkte": [{"untergruppe": "y" * 81, "text": "a", "art": "text"}]})
        assert r.status_code == 400 and "Untergruppe von Prüfpunkt 1" in r.json["error"], r.get_json()
        # Neue Version und Kopie übernehmen die Untergruppen.
        assert kp.post(f"{API}/formulare/{fid}/aktivieren", json={}).status_code == 200
        r = kp.post(f"{API}/formulare", json={"formular_id": pf, "vorlage_id": fid})
        assert r.status_code == 201 and ordnung(r.json["formular"]["punkte"]) == GEORDNET, r.get_json()
        r = kp.post(f"{API}/formular-pool", json={"kategorie_id": ids["gurte"], "titel": "Platzhalter Kopie", "vorlage_id": fid})
        assert r.status_code == 201 and ordnung(r.json["formular"]["punkte"]) == GEORDNET, r.get_json()
        assert kp.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": [], "produkte": [ids["gurt"]]}).status_code == 200

        # Export (Format 3): „untergruppe“ je Punkt.
        roh = exportieren(kp)
        daten = katalogjson(roh)
        assert daten["version"] == 3
        eintrag = next(x for x in daten["formulare"] if x["titel"] == "Platzhalter Untergruppen")
        assert [(p["gruppe"], p["untergruppe"], p["text"]) for p in eintrag["punkte"]] == GEORDNET
        # Import in eine zweite Anlage: rund; ein zweiter Import ändert nichts.
        app_b, kb = umgebung(tmp_b)
        ber = importieren(kb["katalog"], roh, False)
        assert ber["gespeichert"] and not ber["fehler"], ber

        def formular_b(titel="Platzhalter Untergruppen"):
            with app_b.app_context():
                from app import db
                return db.query("SELECT f.id, f.version FROM mat_form f WHERE f.title = ? AND f.active = 1", (titel,), one=True)
        fb = formular_b()
        assert ordnung(kb["katalog"].get(f"{API}/formulare/{fb['id']}").json["formular"]["punkte"]) == GEORDNET
        ber = importieren(kb["katalog"], roh, False)
        assert ber["gespeichert"] and ber["formulare"]["neu"] == 0, ber
        assert formular_b()["id"] == fb["id"]
        # Eine andere Untergruppe in der Datei: neue Version.
        def umbenennen(d):
            for e in d["formulare"]:
                for p in e["punkte"]:
                    if p["untergruppe"] == UN:
                        p["untergruppe"] = "Platzhalter UG Schnapper"
        ber = importieren(kb["katalog"], umschreiben(roh, umbenennen), False)
        assert ber["gespeichert"] and ber["formulare"]["neu"] == 1, ber
        neu = formular_b()
        assert neu["version"] == fb["version"] + 1
        assert ordnung(kb["katalog"].get(f"{API}/formulare/{neu['id']}").json["formular"]["punkte"])[4] == (
            GA, "Platzhalter UG Schnapper", "Platzhalter N1")
        # Eine ältere Datei ohne das Feld (wie vor Schritt 39): leere Untergruppe, die Gruppen bleiben.
        def ohne_feld(d):
            for e in d["formulare"]:
                e["titel"] = "Platzhalter alt"
                for p in e["punkte"]:
                    p.pop("untergruppe", None)
        ber = importieren(kb["katalog"], umschreiben(roh, ohne_feld), False)
        assert ber["gespeichert"] and not ber["fehler"], ber
        alt = formular_b("Platzhalter alt")
        punkte = kb["katalog"].get(f"{API}/formulare/{alt['id']}").json["formular"]["punkte"]
        assert {p["untergruppe"] for p in punkte} == {""} and [p["gruppe"] for p in punkte] == [g for g, _, _ in GEORDNET]
    print("Schnittstelle, Versionen, Export und Import bestanden.")


# --- 3. Prüfung, PDF, festgeschriebenes Protokoll --------------------------------------------------------------------

def _pdf_zeilen(c, pid, tmp, name):
    r = c.get(f"/materialablage/pruefung/{pid}/pdf")
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    pfad = os.path.join(tmp, name)
    with open(pfad, "wb") as fh:
        fh.write(r.get_data())
    return r.get_data(), "\n".join(pdf_layout_seiten(pfad)).splitlines()


def test_pruefung_und_protokoll():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        pf, fid = pool_neu(kp, ids["gurte"], "Platzhalter Prüfung", UNGEORDNET)
        assert kp.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": [ids["gurte"]], "produkte": []}).status_code == 200
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 1}-01")
        r = starten(p1, a["id"])
        assert r.status_code == 201, r.get_json()
        pr = r.json["pruefung"]
        assert ordnung(pr["punkte"]) == GEORDNET
        zahl = next(x for x in pr["punkte"] if x["text"] == "Platzhalter D2")
        assert p1.put(f"{API}/pruefungen/{pr['id']}/punkte/{zahl['id']}", json={"wert": "3"}).status_code == 200
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        # Die Ansicht der abgeschlossenen Prüfung liefert die Kopie weiter.
        assert ordnung(w.get(f"{API}/pruefungen/{pr['id']}").json["pruefung"]["punkte"]) == GEORDNET
        # PDF: Gruppe, darunter die Punkte ohne Untergruppe, dann die Untergruppe als Zwischenzeile mit ihren Punkten.
        roh, zeilen = _pdf_zeilen(w, pr["id"], tmp, "a.pdf")

        def stelle(t):
            treffer = [i for i, z in enumerate(zeilen) if t in z]
            assert treffer, (t, zeilen)
            return treffer[0]
        folge = [stelle(t) for t in (GA, "Platzhalter D1", "Platzhalter D2", UK, "Platzhalter K1", "Platzhalter K2", UN,
                                     "Platzhalter N1", GB, "Platzhalter B1")]
        assert folge == sorted(folge), folge
        # Zwischenzeile allein in ihrer Zeile (keine Nummer davor), Punkte darunter eingezogen.
        assert zeilen[stelle(UK)].strip() == UK and zeilen[stelle(UN)].strip() == UN
        spalte = lambda t: zeilen[stelle(t)].index(t)   # noqa: E731
        assert spalte("Platzhalter K1") > spalte("Platzhalter D1") and spalte("Platzhalter N1") > spalte("Platzhalter D2"), (
            zeilen[stelle("Platzhalter D1")], zeilen[stelle("Platzhalter K1")])
        with app.app_context():
            from app import db
            from app.material.services import protokoll
            gruppen, _f, _m = protokoll._befunde(pr["id"])
            a_punkte = gruppen[0]["punkte"]
            assert [(p["untergruppe"], p["untergruppe_neu"]) for p in a_punkte] == [
                ("", False), ("", False), (UK, True), (UK, False), (UN, True)]
            zeile = db.query("SELECT * FROM mat_inspection WHERE id = ?", (pr["id"],), one=True)
            befunde = db.query("SELECT * FROM mat_inspection_result WHERE inspection_id = ? ORDER BY id", (pr["id"],))
        assert zeile["locked_at"] and hashlib.sha256(roh).hexdigest() == zeile["file_sha256"]
        # Die Kopie in einer abgeschlossenen Prüfung ist unveränderlich (Trigger mat_result_untergruppe).
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            conn.execute("UPDATE mat_inspection_result SET untergruppe = 'x' WHERE inspection_id = ?", (pr["id"],))
            raise AssertionError("Untergruppe einer abgeschlossenen Prüfung geändert")
        except sqlite3.IntegrityError as exc:
            assert "unveränderlich" in str(exc), exc
        conn.close()

        # Das Formular bekommt andere Untergruppen (neue Version, aktiv) – das Protokoll bleibt, wie es war.
        r = kp.post(f"{API}/formulare", json={"formular_id": pf, "vorlage_id": fid})
        neu = r.json["formular"]
        punkte = [dict(p, untergruppe="Platzhalter UG neu" if p["untergruppe"] else "") for p in neu["punkte"]]
        assert kp.put(f"{API}/formulare/{neu['id']}", json={"punkte": punkte}).status_code == 200
        assert kp.post(f"{API}/formulare/{neu['id']}/aktivieren", json={}).status_code == 200
        roh2, _ = _pdf_zeilen(w, pr["id"], tmp, "b.pdf")
        assert roh2 == roh
        with app.app_context():
            from app import db
            assert db.query("SELECT * FROM mat_inspection_result WHERE inspection_id = ? ORDER BY id", (pr["id"],)) == befunde
            assert db.query("SELECT * FROM mat_inspection WHERE id = ?", (pr["id"],), one=True) == zeile

        # Berichtigung (die Prüfung von eben): Die neue Prüfung kopiert die Befundzeilen samt Untergruppe.
        r = p1.post(f"{API}/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter Grund"})
        assert r.status_code == 201, r.get_json()
        b = r.json["pruefung"]
        assert ordnung(b["punkte"]) == GEORDNET
        # Eine neue Prüfung nimmt die neue Version.
        a2 = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 1}-01")
        r = starten(p1, a2["id"])
        assert r.status_code == 201 and {x["untergruppe"] for x in r.json["pruefung"]["punkte"]} == {"", "Platzhalter UG neu"}
    print("Prüfung, PDF und festgeschriebenes Protokoll bestanden.")


# --- 4. Migration 38 → 39 ---------------------------------------------------------------------------------------------

def test_migration_frisch():
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        from app.material import models
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "39"
        for tabelle in ("mat_checklist_item", "mat_inspection_result"):
            spalte = [r for r in conn.execute(f"PRAGMA table_info({tabelle})") if r[1] == "untergruppe"]
            assert spalte and spalte[0][2] == "TEXT" and spalte[0][3] == 1 and spalte[0][4] == "''", (tabelle, spalte)
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = 'mat_result_untergruppe'").fetchone()
        schema = conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        models._schritt_39(conn)
        conn.commit()
        assert conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == schema
        conn.close()
    print("Migration frisch bestanden.")


def _auf_38(pfad):
    """Eine Datenbank von Stand 39 auf den von Stand 38 zurückbauen (für den Altbestand): Trigger und Spalten aus Schritt
    39 weg, Schemaversion 38. Die Untergruppen sind dort alle leer – so sähe derselbe Bestand unter Stand 38 aus."""
    from app.material import models
    conn = sqlite3.connect(pfad)
    for sql in models.TRIGGER_39:
        conn.execute(f"DROP TRIGGER IF EXISTS {models._trigger_name(sql)}")
    for tabelle, spalte, _art in models.SPALTEN_39:
        assert not conn.execute(f"SELECT 1 FROM {tabelle} WHERE {spalte} <> ''").fetchone()
        conn.execute(f"ALTER TABLE {tabelle} DROP COLUMN {spalte}")
    conn.execute("UPDATE mat_meta SET wert = '38' WHERE schluessel = 'schema_version'")
    conn.commit()
    conn.close()


def test_migration_38_39():
    if sqlite3.sqlite_version_info < (3, 35):
        print("Migration 38 → 39 übersprungen – SQLite ohne DROP COLUMN.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        # Altbestand: Formulare mit Gruppen (ohne Untergruppen), eine festgeschriebene Prüfung mit PDF.
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        alt = [dict(p, untergruppe="") for p in UNGEORDNET]
        pf, fid = pool_neu(kp, ids["gurte"], "Platzhalter Altbestand", alt)
        assert kp.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": [ids["gurte"]], "produkte": []}).status_code == 200
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 1}-01")
        pr = starten(p1, a["id"]).json["pruefung"]
        zahl = next(x for x in pr["punkte"] if x["text"] == "Platzhalter D2")
        assert p1.put(f"{API}/pruefungen/{pr['id']}/punkte/{zahl['id']}", json={"wert": "3"}).status_code == 200
        assert abschluss(p1, pr["id"], ergebnis="einsatzbereit").status_code == 200
        roh, _ = _pdf_zeilen(w, pr["id"], tmp, "vorher.pdf")
        pfad = os.path.join(tmp, "stroemis.db")
        _auf_38(pfad)
        conn = sqlite3.connect(pfad)
        tabellen = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat_%' "
                                               "ORDER BY name")]
        vorher = {t: conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabellen}
        spalten = {t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})")] for t in tabellen}
        trigger = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
        conn.close()
        assert "mat_result_untergruppe" not in trigger

        make_app(tmp)                                                             # Start: Schritt 39
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "39"
        for t in tabellen:
            nachher = conn.execute(f"SELECT {', '.join(spalten[t])} FROM {t} ORDER BY 1").fetchall()
            if t == "mat_meta":
                nachher = [z for z in nachher if z[0] != "schema_version"]
                vorher[t] = [z for z in vorher[t] if z[0] != "schema_version"]
            assert nachher == vorher[t], t
        for tabelle, spalte, _art in [("mat_checklist_item", "untergruppe", ""), ("mat_inspection_result", "untergruppe", "")]:
            assert conn.execute(f"SELECT COUNT(*) FROM {tabelle} WHERE {spalte} <> ''").fetchone()[0] == 0
            assert conn.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0] > 0
        neu_trigger = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
        assert neu_trigger == trigger | {"mat_result_untergruppe"}
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Zweiter Lauf des Schritts und zweiter Start ändern nichts.
        stand = [tuple(r) for t in tabellen for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")]
        schema = conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        from app.material import models
        models._schritt_39(conn)
        conn.commit()
        assert [tuple(r) for t in tabellen for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")] == stand
        assert conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == schema
        conn.close()
        app = make_app(tmp)
        # Das festgeschriebene Protokoll: dieselbe Datei; die Prüfung liest sich wie vorher (Untergruppen leer).
        from test_material import anmelden
        w2 = anmelden(app, "wart@example.org", "passwort1")
        roh2, _ = _pdf_zeilen(w2, pr["id"], tmp, "nachher.pdf")
        assert roh2 == roh
        punkte = w2.get(f"{API}/pruefungen/{pr['id']}").json["pruefung"]["punkte"]
        assert [(x["gruppe"], x["untergruppe"]) for x in punkte] == [(g, "") for g, _u, _t in GEORDNET], punkte
    print("Migration 38 → 39 bestanden.")


# --- 5. Browser ------------------------------------------------------------------------------------------------------

GROESSEN = ((1280, 900, False), (360, 740, True))
LANG_UG = ("Platzhalter-Untergruppe mit einem langen Namen, der in der Zwischenzeile ganz zu lesen ist" + "x" * 80)[:80]
# Je Gruppe: Name, Punkte ohne Untergruppe, [(Untergruppe, Punkte)], Hinweis „leer“ irgendwo im Block.
STRUKTUR = """JSON.stringify([...document.querySelectorAll('#fp-tabelle tbody')].map((tb) => {
  const text = (tr) => tr.querySelector('.fp-text').value;
  const direkt = [...tb.querySelectorAll('tr.fp-punkt:not([data-u])')].map(text);
  const unter = [...tb.querySelectorAll('tr.fp-ug-zeile')].map((k) => [k.querySelector('.fp-ug-name').value,
    [...tb.querySelectorAll(`tr.fp-punkt[data-u="${k.dataset.u}"]`)].map(text)]);
  return [(tb.querySelector('.fp-gruppenname') || {}).value, direkt, unter];
}))"""


def struktur(s):
    return json.loads(s.js(STRUKTUR))


def punkt(gi, pi, ui=None):
    return f'#fp-tabelle tr.fp-punkt[data-g="{gi}"][data-i="{pi}"]' + (":not([data-u])" if ui is None else f'[data-u="{ui}"]')


def ug_kopf(gi, ui):
    return f'#fp-tabelle tr.fp-ug-zeile[data-g="{gi}"][data-u="{ui}"]'


def browser_formular(u, kategorie):
    r = u.adm.post(f"{API}/formular-pool", json={"kategorie_id": kategorie, "titel": "Platzhalter Untergruppen", "punkte": [
        {"gruppe": GA, "text": "Platzhalter D1", "art": "yesno", "soll": "ja"},
        {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K1", "art": "yesno", "soll": "ja"},
        {"gruppe": GA, "untergruppe": UK, "text": "Platzhalter K2", "art": "text"},
        {"gruppe": GB, "text": "Platzhalter B1", "art": "yesno", "soll": "nein"},
        {"gruppe": GB, "text": "Platzhalter B2", "art": "yesno", "soll": "ja"}]})
    assert r.status_code == 201, r.get_json()
    return r.json["formular"]["id"]


def editor_ablauf(u, kategorie, breite, hoehe, touch):
    from test_material_formular_editor import gespeichert, klick, menue, oeffnen, tippen, tippflaechen, ziehen
    fid = browser_formular(u, kategorie)
    s = u.seite("matverwaltung", breite, hoehe, touch)
    try:
        oeffnen(s, fid)
        assert struktur(s) == [[GA, ["Platzhalter D1"], [[UK, ["Platzhalter K1", "Platzhalter K2"]]]],
                               [GB, ["Platzhalter B1", "Platzhalter B2"], []]], struktur(s)
        # Gruppe mit Untergruppe: „+ Prüfpunkt“ nach ihren eigenen Punkten, „+ Untergruppe“ in eigener Zeile am Ende;
        # ohne Untergruppe steht „+ Untergruppe“ neben „+ Prüfpunkt“.
        knoepfe = s.js("""[...document.querySelectorAll('#fp-tabelle tbody')].map((tb) => [...tb.querySelectorAll(':scope > tr')]
          .filter((tr) => tr.querySelector('[data-act=punkt-neu], [data-act=ug-neu]'))
          .map((tr) => [tr.className, [...tr.querySelectorAll('[data-act]')].map((b) => b.dataset.act + ':' + b.textContent.trim())]))""")
        assert knoepfe == [
            [["fp-fuss", ["punkt-neu:+ Prüfpunkt anlegen"]], ["fp-fuss fp-in-ug", ["punkt-neu:+ Prüfpunkt anlegen"]],
             ["fp-ug-neu", ["ug-neu:+ Untergruppe anlegen"]]],
            [["fp-fuss", ["punkt-neu:+ Prüfpunkt anlegen", "ug-neu:+ Untergruppe anlegen"]]]], knoepfe
        # Eingezogen: Text der Untergruppenpunkte rechts vom Text der übrigen, der Griff der Untergruppe rechts von dem eines
        # Punkts ohne Untergruppe (Tabelle: in der Spalte der Prüfpunkte; Karte: die ganze Zeile eingerückt).
        lagen = s.js(f"""(() => {{ const l = (sel) => document.querySelector(sel).getBoundingClientRect().left;
          return [l({json.dumps(punkt(0, 0) + ' .fp-text')}), l({json.dumps(punkt(0, 0, 0) + ' .fp-text')}),
                  l({json.dumps(punkt(0, 0) + ' .fp-griff')}), l({json.dumps(ug_kopf(0, 0) + ' .fp-griff')})]; }})()""")
        assert lagen[1] >= lagen[0] + 12 and lagen[3] >= lagen[2] + 12, lagen
        # Name der Untergruppe: Feld mit 80 Zeichen, Enter ohne Absatz; Getipptes bleibt bei jedem Neuzeichnen.
        assert s.js(f"document.querySelector({json.dumps(ug_kopf(0, 0) + ' .fp-ug-name')}).maxLength") == 80
        tippen(s, f"{ug_kopf(0, 0)} .fp-ug-name", " neu")
        tippen(s, f"{punkt(0, 1, 0)} .fp-text", " getippt")
        tippen(s, "#fp-titel", " getippt")

        # + Untergruppe in Gruppe B (leer, Fokus ins Namensfeld), Name tippen.
        klick(s, '#fp-tabelle [data-act="ug-neu"][data-g="1"]')
        if not touch:
            assert s.js(f"document.activeElement.matches({json.dumps(ug_kopf(1, 0) + ' .fp-ug-name')})")
        assert s.js("document.querySelector('#fp-tabelle tr.fp-leer[data-g=\"1\"][data-u=\"0\"]').textContent").strip() == (
            "Die Untergruppe ist leer – leer wird sie nicht gespeichert.")
        tippen(s, f"{ug_kopf(1, 0)} .fp-ug-name", UN)
        # Speichern mit einer leeren Untergruppe ohne Punkte geht (sie fällt weg) – hier noch nicht: erst Punkte hinein.
        # Punkt B2 in die neue Untergruppe ziehen (über die untere Hälfte ihres Kopfs → an ihren Anfang).
        ziehen(s, punkt(1, 1), ug_kopf(1, 0), anteil=0.8)
        st = struktur(s)
        assert st[1] == [GB, ["Platzhalter B1"], [[UN, ["Platzhalter B2"]]]], st
        assert st[0] == [GA, ["Platzhalter D1"], [[UK + " neu", ["Platzhalter K1", "Platzhalter K2 getippt"]]]], st
        # D1 in die Untergruppe von A ziehen (ans Ende: über deren „+ Prüfpunkt“) und K1 wieder heraus (obere Hälfte des
        # Untergruppenkopfs → ans Ende der Punkte ohne Untergruppe).
        ziehen(s, punkt(0, 0), '#fp-tabelle tr.fp-fuss[data-g="0"][data-u="0"]', anteil=0.5)
        assert struktur(s)[0] == [GA, [], [[UK + " neu", ["Platzhalter K1", "Platzhalter K2 getippt", "Platzhalter D1"]]]], struktur(s)
        ziehen(s, punkt(0, 0, 0), ug_kopf(0, 0), anteil=0.15)
        assert struktur(s)[0] == [GA, ["Platzhalter K1"], [[UK + " neu", ["Platzhalter K2 getippt", "Platzhalter D1"]]]], struktur(s)
        # Menü: „Nach unten“ vom letzten Punkt ohne Untergruppe → erster der Untergruppe; „Nach oben“ zurück.
        menue(s, punkt(0, 0), "punkt-runter")
        assert struktur(s)[0][1:] == [[], [[UK + " neu", ["Platzhalter K1", "Platzhalter K2 getippt", "Platzhalter D1"]]]], struktur(s)
        menue(s, punkt(0, 0, 0), "punkt-hoch")
        assert struktur(s)[0][1] == ["Platzhalter K1"], struktur(s)
        # „In Gruppe verschieben“ mit Untergruppen im Dialog: B1 in die Untergruppe „Körper neu“ der Gruppe A.
        menue(s, punkt(1, 0), "punkt-gruppe")
        assert s.warte("!!document.querySelector('#dlg[open] .fp-gruppenwahl')")
        wahl = s.js("[...document.querySelectorAll('#dlg[open] .fp-wahl')].map((l) => [l.querySelector('input').value, l.classList.contains('fp-wahl-ug'), l.querySelector('input').disabled])")
        assert wahl == [["0", False, False], ["0:0", True, False], ["1", False, True], ["1:0", True, False], ["neu", False, False]], wahl
        if touch:
            tippflaechen(s, "#dlg[open] .fp-wahl.fp-wahl-ug")
        klick(s, '#dlg[open] .fp-wahl:has(input[value="0:0"])')
        klick(s, "#fp-gruppe-ok")
        assert struktur(s)[0][2][0][1][-1] == "Platzhalter B1" and struktur(s)[1][1] == [], struktur(s)
        # Untergruppe ziehen: „Nase“ aus Gruppe B vor „Körper neu“ in Gruppe A (über dessen Kopf, obere Hälfte).
        ziehen(s, ug_kopf(1, 0), ug_kopf(0, 0), anteil=0.1)
        st = struktur(s)
        assert [x[0] for x in st[0][2]] == [UN, UK + " neu"] and st[1][2] == [], st
        assert st[0][2][0][1] == ["Platzhalter B2"], st
        assert not s.js("document.querySelector('.fp-einfuegemarke, #fp-tabelle .fp-zieht-block, #fp-tabelle.fp-ziehen')")
        # … innerhalb der Gruppe wieder ans Ende (über „+ Untergruppe“), Esc lässt alles stehen.
        vorher = struktur(s)
        ziehen(s, ug_kopf(0, 0), '#fp-tabelle tr.fp-ug-neu[data-g="0"]', anteil=0.3, esc=True)
        assert struktur(s) == vorher
        ziehen(s, ug_kopf(0, 0), '#fp-tabelle tr.fp-ug-neu[data-g="0"]', anteil=0.3)
        assert [x[0] for x in struktur(s)[0][2]] == [UK + " neu", UN], struktur(s)
        assert s.js("document.querySelector('#fp-titel').value") == "Platzhalter Untergruppen getippt"
        # + Prüfpunkt in der Untergruppe „Nase“ (am Ende), langer Name ganz sichtbar.
        klick(s, '#fp-tabelle tr.fp-fuss [data-act="punkt-neu"][data-g="0"][data-u="1"]')
        tippen(s, f"{punkt(0, 1, 1)} .fp-text", "Platzhalter N2")
        s.js(f"""(() => {{ const t = document.querySelector({json.dumps(ug_kopf(0, 1) + ' .fp-ug-name')}); t.value = '';
          t.dispatchEvent(new Event('input', {{ bubbles: true }})); }})()""")
        tippen(s, f"{ug_kopf(0, 1)} .fp-ug-name", LANG_UG)
        s.js(f"""(() => {{ const a = document.querySelector({json.dumps(punkt(0, 0) + ' .fp-art')}); a.value = 'text';
          a.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()""")
        s.b.warten(0.2)
        lang = s.js(f"""(() => {{ const t = document.querySelector({json.dumps(ug_kopf(0, 1) + ' .fp-ug-name')});
          return [t.value, t.scrollHeight - t.clientHeight, t.scrollWidth - t.clientWidth]; }})()""")
        assert lang[0] == LANG_UG and lang[1] <= 1 and lang[2] <= 1, lang
        # Leere Untergruppe mit Namen in Gruppe B, eine ohne Namen mit Punkt → das automatische Speichern verlangt den
        # Namen am Feld (der Fokus bleibt im Punkt, in dem getippt wird) und speichert bis dahin nicht.
        gespeichert(s)
        klick(s, '#fp-tabelle [data-act="ug-neu"][data-g="1"]')
        klick(s, '#fp-tabelle tr.fp-fuss [data-act="punkt-neu"][data-g="1"][data-u="0"]')
        tippen(s, f"{punkt(1, 0, 0)} .fp-text", "Platzhalter ohne Namen")
        assert s.warte("document.querySelector('#fp-stand').textContent === 'Nicht gespeichert – Untergruppe ohne Namen'")
        fehler = s.js(f"""(() => {{ const t = document.querySelector({json.dumps(ug_kopf(1, 0) + ' .fp-ug-name')});
          const p = document.getElementById(t.id + '-fehler'); return [t.getAttribute('aria-invalid'), p && p.textContent]; }})()""")
        assert fehler == ["true", "Eine Untergruppe mit Prüfpunkten braucht einen Namen."], fehler
        if not touch:
            assert s.js(f"document.activeElement.matches({json.dumps(punkt(1, 0, 0) + ' .fp-text')})")
        assert "Platzhalter ohne Namen" not in [z["label"] for z in u.sql("SELECT label FROM mat_checklist_item WHERE form_id = ?", (fid,))]
        # Untergruppe entfernen: mit Punkt nach Rückfrage samt Anzahl.
        klick(s, f'{ug_kopf(1, 0)} [data-act="ug-weg"]')
        assert s.warte("!!document.querySelector('dialog[open] #c-titel')")
        assert s.js("document.querySelector('dialog[open] #c-titel').textContent") == "Untergruppe 1 (ohne Namen) mit 1 Prüfpunkt entfernen?"
        assert s.js("document.querySelector('dialog[open] #c-ok').className") == "btn danger"
        klick(s, "dialog[open] #c-ok")
        assert struktur(s)[1] == [GB, [], []], struktur(s)
        # Tippflächen am Finger: Griff und Knopf am Untergruppenkopf, „+ Prüfpunkt“/„+ Untergruppe“ – gemessen.
        if touch:
            for sel in (f"{ug_kopf(0, 0)} .fp-griff", f'{ug_kopf(0, 0)} [data-act="ug-weg"]', "#fp-tabelle tr.fp-fuss.fp-in-ug .btn",
                        "#fp-tabelle tr.fp-ug-neu .btn", '#fp-tabelle tr.fp-fuss [data-act="ug-neu"]',
                        "#fp-tabelle tr.fp-in-ug .fp-griff", "#fp-tabelle tr.fp-in-ug .fp-menue summary"):
                tippflaechen(s, sel)
            assert s.js(f"getComputedStyle(document.querySelector({json.dumps(ug_kopf(0, 0) + ' .fp-griff')})).touchAction") == "none"
        assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        # Gespeichert von selbst: Reihenfolge, Gruppe und Untergruppe je Punkt in der Datenbank.
        gespeichert(s)
        zeilen = u.sql("SELECT group_name, untergruppe, label FROM mat_checklist_item WHERE form_id = ? ORDER BY position", (fid,))
        assert [(z["group_name"], z["untergruppe"], z["label"]) for z in zeilen] == [
            (GA, "", "Platzhalter K1"), (GA, UK + " neu", "Platzhalter K2 getippt"), (GA, UK + " neu", "Platzhalter D1"),
            (GA, UK + " neu", "Platzhalter B1"), (GA, LANG_UG, "Platzhalter B2"), (GA, LANG_UG, "Platzhalter N2")], zeilen
        assert u.sql("SELECT title FROM mat_form WHERE id = ?", (fid,))[0]["title"] == "Platzhalter Untergruppen getippt"
        assert struktur(s)[0][2][1][0] == LANG_UG
        s.sammeln()
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()

    # Nur lesen (Mitglied): Zwischenzeile der Untergruppe, Punkte eingezogen, ohne Griff und Felder.
    m = u.seite("mitglied", breite, hoehe, touch)
    try:
        oeffnen(m, fid)
        zeilen = m.js("""[...document.querySelectorAll('#fp-tabelle tbody tr')].map((tr) => [tr.className,
          (tr.querySelector('th') || tr.querySelector('.mat-mehrzeilig')).textContent.trim()])""")
        assert zeilen == [["fp-gruppenzeile", GA], ["", "Platzhalter K1"], ["fp-ug-zeile", UK + " neu"],
                          ["fp-in-ug", "Platzhalter K2 getippt"], ["fp-in-ug", "Platzhalter D1"], ["fp-in-ug", "Platzhalter B1"],
                          ["fp-ug-zeile", LANG_UG], ["fp-in-ug", "Platzhalter B2"], ["fp-in-ug", "Platzhalter N2"]], zeilen
        einzug = m.js("""(() => { const x = (sel) => { const e = document.querySelector(sel); const r = document.createRange();
          r.selectNodeContents(e); return r.getBoundingClientRect().left; };
          return [x('#fp-tabelle tbody tr:not([class]) .mat-mehrzeilig'), x('#fp-tabelle tr.fp-in-ug .mat-mehrzeilig'),
                  x('#fp-tabelle tr.fp-gruppenzeile th'), x('#fp-tabelle tr.fp-ug-zeile th'),
                  document.querySelector('#fp-tabelle tr.fp-gruppenzeile').getBoundingClientRect().left,
                  document.querySelector('#fp-tabelle tr.fp-ug-zeile').getBoundingClientRect().left]; })()""")
        # Zwischenzeile der Untergruppe: als Tabelle ihr Text eingezogen, als Karte die ganze Zeile.
        assert einzug[1] >= einzug[0] + 12 and max(einzug[3] - einzug[2], einzug[5] - einzug[4]) >= 12, einzug
        lang = m.js("(() => { const t = [...document.querySelectorAll('#fp-tabelle tr.fp-ug-zeile th')].pop(); return t.scrollWidth <= t.clientWidth; })()")
        assert lang, "langer Untergruppenname abgeschnitten"
        assert not m.js("document.querySelector('#fp-tabelle .fp-griff, #fp-tabelle textarea, [data-act=ug-neu]')")
        assert m.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        m.sammeln()
        assert not m.fehler, m.fehler
    finally:
        m.schliessen()
    return fid


def pruefung_ansicht(u, ids, fid):
    """Prüfungsansicht (offener Entwurf): Untergruppe als kleinere Zwischenüberschrift unter der Gruppe, Karten eingezogen."""
    from einfuehrung_browser import PASSWORT, mail
    from test_material import freigeben
    assert u.adm.post(f"{API}/formulare/{fid}/aktivieren", json={}).status_code == 200
    pf = u.sql("SELECT formular_id FROM mat_form WHERE id = ?", (fid,))[0]["formular_id"]
    assert u.adm.put(f"{API}/formular-pool/{pf}/zuweisung", json={"kategorien": [ids["gurte"]], "produkte": []}).status_code == 200
    gid = u.sql("SELECT id FROM mat_folder WHERE name = 'Übung Gliederung'")[0]["id"]
    freigeben(u.adm, gid, u.ids["pruefer"], "lesen")
    freigeben(u.adm, gid, u.ids["pruefer"], "pruefen")
    r = u.adm.post(f"{API}/artikel", json={"product_id": ids["gurt"], "folder_id": gid, "manufactured_on": "2025-01"})
    assert r.status_code == 201, r.get_json()
    p = u._anmelden(mail("pruefer"), PASSWORT)
    r = p.post(f"{API}/artikel/{r.json['artikel']['id']}/pruefungen", json={})
    assert r.status_code == 201, r.get_json()
    pid = r.json["pruefung"]["id"]
    for breite, hoehe, touch in GROESSEN:
        s = u.seite("pruefer", breite, hoehe, touch)
        try:
            s.oeffnen(f"/materialablage/pruefung/{pid}", warten=0.6)
            assert s.warte("!!document.querySelector('.mat-punkt-text')")
            folge = s.js("""[...document.querySelectorAll('.mat-punkte :is(h3.mat-gruppe, h4.mat-untergruppe, .mat-punkt-text)')]
              .map((e) => [e.tagName, e.textContent.trim()])""")
            assert folge[:4] == [["H3", GA], ["SPAN", "Platzhalter K1"], ["H4", UK + " neu"], ["SPAN", "Platzhalter K2 getippt"]], folge
            lagen = s.js("""(() => { const l = (sel) => document.querySelector(sel).getBoundingClientRect();
              const a = l('.mat-pliste > .mat-punkt'), b = l('.mat-in-ug > .mat-punkt'), g = l('h3.mat-gruppe'), h = l('h4.mat-untergruppe');
              const fs = (sel) => parseFloat(getComputedStyle(document.querySelector(sel)).fontSize);
              return [a.left, b.left, b.right <= document.documentElement.clientWidth, g.left, h.left, fs('h3.mat-gruppe'), fs('h4.mat-untergruppe')]; })()""")
            assert lagen[1] >= lagen[0] + 12 and lagen[2] and lagen[4] > lagen[3] and lagen[6] <= lagen[5], lagen
            assert s.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            s.sammeln()
            assert not s.fehler, s.fehler
        finally:
            s.schliessen()


def test_browser():
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    from test_material import katalog_grund as grund
    with Umgebung() as u:
        ids = grund(u.adm)
        fid = None
        for breite, hoehe, touch in GROESSEN:
            los = time.time()
            fid = editor_ablauf(u, ids["gurte"], breite, hoehe, touch)
            print(f"Editor mit Untergruppen {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({time.time() - los:.1f} s)")
        pruefung_ansicht(u, ids, fid)
        print("Prüfungsansicht mit Untergruppen: bestanden.")


def test_uebung():
    """Übung der Materialablage mit Katalog (keine neuen Schritte): Hat das Katalogformular Untergruppen, zeigen der
    Editor (Teil „Material-Verwaltung“) und die Prüfung (Teil „Prüfer“) sie; jede Übung kommt bis „Geschafft“, die
    Datenbank bleibt unverändert."""
    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    from test_einfuehrung_katalog import katalog_platzhalter
    from test_einfuehrung_material import durchlauf
    with Umgebung() as u:
        ids = katalog_platzhalter(u.app)
        with u.app.test_request_context():
            from flask import g
            from app.material.services import katalog
            g.mat_akteur = "Test"
            for fid in (ids["form_gurte"], ids["form_seil"]):
                punkte = [dict(katalog.punkt_json(p)) for p in katalog.punkte(fid)]
                for p in punkte[1:]:
                    p["untergruppe"] = "Platzhalter Untergruppe"
                katalog.formular_speichern(fid, {"punkte": punkte})
            from app import einfuehrung
            einfuehrung.katalog_vergessen()
            auswahl = einfuehrung.katalog_material()
            u.medien_frei = einfuehrung.katalog_bilder()
        assert {p["untergruppe"] for f in auswahl["formulare"][:2] for p in f["punkte"]} == {"", "Platzhalter Untergruppe"}
        for breite, hoehe, touch in GROESSEN:
            for teil, sel in (("verwaltung", "#fp-tabelle tr.fp-ug-zeile .fp-ug-name"), ("pruefer", "h4.mat-untergruppe")):
                gesehen = []

                def probe(seite, _z, sel=sel, gesehen=gesehen):
                    gesehen.append(seite.js(f"[...document.querySelectorAll({json.dumps(sel)})].map((e) => e.value || e.textContent)"))
                befunde, dauer = durchlauf(u, teil, breite, hoehe, touch, probe)
                assert not befunde, (teil, breite, befunde)
                assert any("Platzhalter Untergruppe" in x for x in gesehen), (teil, breite, gesehen)
                print(f"Übung material/{teil} mit Untergruppen {breite}×{hoehe}{' Touch' if touch else ''}: bestanden ({dauer:.1f} s)")


def test_statisch():
    """Beschriftungen, Knopfsprache und Touch-Regeln der Untergruppen."""
    with open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8") as fh:
        js = fh.read()
    with open(os.path.join(WURZEL, "app/material/static/material.css"), encoding="utf-8") as fh:
        css = fh.read()
    editor = js[js.index("  async function formular() {"):]
    editor = editor[:editor.index("\n  }\n")]
    assert '<span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Untergruppe<span class="k-anlegen"> anlegen</span></span>' in editor
    assert 'text: "Untergruppe entfernen"' in editor and 'placeholder="Name der Untergruppe"' in editor
    assert 'class="fp-ug-name" rows="1" maxlength="80"' in editor
    assert "btn ghost" not in editor and "btn danger" not in editor
    # Tippflächen nur unter (pointer: coarse).
    for regel in (".mat-formtabelle { --fp-ug-einzug: 52px; }", ".mat-formtabelle tr.fp-ug-neu .btn { min-height: 44px; }"):
        i = css.index(regel)
        assert css.rfind("@media (pointer: coarse) {", 0, i) > css.rfind("\n}\n", 0, i), regel
    # Prüfprotokoll: Zwischenzeile und Einzug.
    with open(os.path.join(WURZEL, "app/material/templates/material/pdf/pruefprotokoll.html"), encoding="utf-8") as fh:
        vorlage = fh.read()
    assert '<tr class="untergruppe"><td></td><td colspan="4">{{ p.untergruppe }}</td></tr>' in vorlage and "td.in-ug" in vorlage
    print("Statisch bestanden.")


if __name__ == "__main__":
    test_dienst()
    test_statisch()
    test_schnittstelle_und_transfer()
    test_pruefung_und_protokoll()
    test_migration_frisch()
    test_migration_38_39()
    test_browser()
    test_uebung()
