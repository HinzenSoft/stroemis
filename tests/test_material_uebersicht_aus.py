"""Gliederung aus „Fälligkeiten je Ordner“ ausblenden (Schritt 40, Wunsch vom 10.11.2026; Auftrag
planung/uebersicht-ausblenden):  python tests/test_material_uebersicht_aus.py

  1. Migration frisch, 39 → 40 mit Altbestand, zweiter Lauf.
  2. Schalter: nur an Gliederungen der obersten Ebene, Rechte wie beim Bearbeiten, Journal und Beschriftung.
  3. Übersicht: der ganze Zweig fehlt in der Tabelle, „ordner_ausgeblendet“ nennt die Gliederung (auch als Pfad-Knoten);
     Ordnerleiste und übrige Zahlen bleiben.
  4. Verschieben unter eine andere Gliederung setzt den Schalter zurück; Bearbeiten prüft und schreibt unter einer
     Schreibsperre, ein gleichzeitiges Verschieben kommt nicht dazwischen (Prüfung Ablauf R1, Befund 1).
  5. Oberfläche (statisch): Häkchen im Dialog, Zeile „Nicht gezeigt“, Info, Journal-Beschriftung.

Alle Namen sind Platzhalter."""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import gliederung, katalog_grund, make_app, neuer_artikel, umgebung, freigeben  # noqa: E402
from test_material_rueckruf import konto  # noqa: E402
from test_material_trennung import endversion, zeilen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _start(c):
    r = c.get(f"{API}/start")
    assert r.status_code == 200, r.get_json()
    return r.json


def _aus(c, fid, wert):
    return c.put(f"{API}/ordner/{fid}", json={"overview_off": wert})


def _journal(app, fid):
    return [(json.loads(z["before_json"] or "null"), json.loads(z["after_json"] or "null"))
            for z in zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'folder' AND entity_id = ? AND action = 'geaendert' "
                                 "ORDER BY id", (fid,))]


# --- 1. Migration ------------------------------------------------------------------------------------------------------

def test_migration_frisch():
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        from app.material import models
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == endversion()
        spalte = [r for r in conn.execute("PRAGMA table_info(mat_folder)") if r[1] == "overview_off"]
        assert spalte and spalte[0][2] == "INTEGER" and spalte[0][3] == 1 and spalte[0][4] == "0", spalte
        conn.execute("INSERT INTO mat_folder (name, kind, created_at, updated_at) VALUES ('Platzhalter', 'gliederung', "
                     "'2026-11-10', '2026-11-10')")
        assert conn.execute("SELECT overview_off FROM mat_folder").fetchone()[0] == 0
        try:
            conn.execute("UPDATE mat_folder SET overview_off = 2")
            raise AssertionError("CHECK fehlt")
        except sqlite3.IntegrityError:
            pass
        conn.rollback()
        schema = conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        models._schritt_40(conn)                                                    # zweiter Lauf ändert nichts
        conn.commit()
        assert conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == schema
        conn.close()
    print("Migration frisch bestanden.")


def test_migration_39_40():
    if sqlite3.sqlite_version_info < (3, 35):
        print("Migration 39 → 40 übersprungen – SQLite ohne DROP COLUMN.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        # Altbestand: zwei Gliederungen, Unterordner mit „Erinnerungsmails aus“, ein Artikel.
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w = k["wart"]
        gid, _ = gliederung(w, "OG Platzhalter")
        gliederung(w, "Platzhalter Zwei")
        lager = ordner_neu(w, gid, "Lager")
        assert w.put(f"{API}/ordner/{lager}", json={"reminders_off": True}).status_code == 200
        neuer_artikel(w, ids["hms"], lager)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        conn.execute("ALTER TABLE mat_folder DROP COLUMN overview_off")
        conn.execute("UPDATE mat_meta SET wert = '39' WHERE schluessel = 'schema_version'")
        conn.commit()
        tabellen = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat_%' "
                                               "ORDER BY name")]
        spalten = {t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})")] for t in tabellen}
        vorher = {t: conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabellen}
        conn.close()

        make_app(tmp)                                                               # Start: Schritt 40
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == endversion()
        for t in tabellen:
            nachher = conn.execute(f"SELECT {', '.join(spalten[t])} FROM {t} ORDER BY 1").fetchall()
            if t == "mat_meta":
                nachher = [z for z in nachher if z[0] != "schema_version"]
                vorher[t] = [z for z in vorher[t] if z[0] != "schema_version"]
            assert nachher == vorher[t], t
        assert conn.execute("SELECT COUNT(*), SUM(overview_off) FROM mat_folder").fetchone() == (len(vorher["mat_folder"]), 0)
        schema = conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
        conn.close()
        make_app(tmp)                                                               # zweiter Start: nichts zu tun
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == schema
        conn.close()
    print("Migration 39 → 40 bestanden.")


# --- 2. bis 4. Schalter, Übersicht, Verschieben -------------------------------------------------------------------------

def test_ausblenden():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        adm, w = k["adm"], k["wart"]
        echt, _ = gliederung(w, "OG Platzhalter")
        nord = ordner_neu(w, echt, "Ortsgruppe Nord", "gliederung")
        privat, system = gliederung(w, "Platzhalter Privat")
        lager = ordner_neu(w, privat, "Lager")
        regal = ordner_neu(w, lager, "Regal")
        neuer_artikel(w, ids["hms"], echt)
        neuer_artikel(w, ids["hms"], regal)
        neuer_artikel(w, ids["hms"], lager)

        vorher = _start(w)
        assert {privat, lager, regal} <= {z["id"] for z in vorher["ordner_uebersicht"]}
        assert vorher["ordner_ausgeblendet"] == []
        baum_vorher = w.get(f"{API}/ordner").json["ordner"]

        # Rechte und Eingaben: lesen 403, unter der obersten Ebene 400, Systemordner 409, Unsinn 400.
        assert _aus(k["fuehrung"], privat, True).status_code == 403
        for fid in (lager, nord):
            r = _aus(w, fid, True)
            assert r.status_code == 400 and "nur an Gliederungen der obersten Ebene" in r.json["error"], r.get_json()
        assert _aus(w, system["gesperrt"], True).status_code == 409
        r = _aus(w, privat, "vielleicht")
        assert r.status_code == 400 and "Nicht in „Fälligkeiten je Ordner“ zeigen" in r.json["error"], r.get_json()
        r = w.post(f"{API}/ordner", json={"name": "Keller", "kind": "standort", "parent_id": privat, "overview_off": True})
        assert r.status_code == 400, r.get_json()
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_folder WHERE overview_off = 1")[0]["n"] == 0

        # Ausblenden durch den Materialwart der Gliederung: Journal mit Beschriftung.
        r = _aus(w, privat, True)
        assert r.status_code == 200 and r.json["ordner"]["overview_off"] is True, r.get_json()
        assert w.get(f"{API}/ordner/{privat}").json["ordner"]["overview_off"] is True
        assert w.get(f"{API}/ordner/{lager}").json["ordner"]["overview_off"] is False
        assert _journal(app, privat)[-1] == ({"overview_off": 0}, {"overview_off": 1})
        with app.app_context():
            from app.material.services import beschriftung
            assert beschriftung.FELD["overview_off"] == "In „Fälligkeiten je Ordner“ ausgeblendet"
            assert beschriftung.wert_text(1, "overview_off") == "ja"

        # Übersicht ohne den Zweig, die Gliederung unter der Tabelle; alle übrigen Zahlen gleich.
        nachher = _start(w)
        assert [z["id"] for z in nachher["ordner_uebersicht"]] == [z["id"] for z in vorher["ordner_uebersicht"]
                                                                    if z["id"] not in (privat, lager, regal)]
        assert nachher["ordner_ausgeblendet"] == [{"id": privat, "name": "Platzhalter Privat", "nur_pfad": False}]
        for feld in ("zaehlung", "bestand", "naechste", "faellig_gesamt"):
            assert nachher[feld] == vorher[feld], feld
        assert [o["id"] for o in nachher["gliederungen"]] == [o["id"] for o in vorher["gliederungen"]]
        baum = w.get(f"{API}/ordner").json["ordner"]
        assert [{x: o.get(x) for x in ("id", "zaehlung", "bestand")} for o in baum] == \
               [{x: o.get(x) for x in ("id", "zaehlung", "bestand")} for o in baum_vorher]
        assert w.get(f"{API}/ordner/{privat}").status_code == 200

        # Wer nur „Lager“ sieht, hat die Gliederung als Pfad-Knoten: ebenfalls nicht in der Tabelle, ohne Link darunter.
        sub, sub_id = konto(app, adm, "lager@example.org")
        freigeben(adm, lager, sub_id, "lesen")
        d = _start(sub)
        assert d["ordner_uebersicht"] == [] and d["bestand"] == 2, d
        assert d["ordner_ausgeblendet"] == [{"id": privat, "name": "Platzhalter Privat", "nur_pfad": True}]

        # Wieder zeigen, wieder ausblenden; „null“ gilt wie „nein“.
        assert _aus(w, privat, None).status_code == 200
        assert privat in {z["id"] for z in _start(w)["ordner_uebersicht"]}
        assert _aus(w, privat, "ja").status_code == 200

        # Andere Felder ändern lässt den Schalter stehen.
        assert w.put(f"{API}/ordner/{privat}", json={"name": "Platzhalter Privat neu"}).status_code == 200
        assert w.get(f"{API}/ordner/{privat}").json["ordner"]["overview_off"] is True

        # Verschieben unter eine andere Gliederung setzt ihn zurück (mit Journal), zurück nach oben bleibt er aus.
        r = adm.post(f"{API}/ordner/{privat}/verschieben", json={"parent_id": echt})
        assert r.status_code == 200 and r.json["ordner"]["overview_off"] is False, r.get_json()
        assert _journal(app, privat)[-1] == ({"overview_off": 1}, {"overview_off": 0})
        d = _start(w)
        assert privat in {z["id"] for z in d["ordner_uebersicht"]} and d["ordner_ausgeblendet"] == []
        assert adm.post(f"{API}/ordner/{privat}/verschieben", json={"parent_id": None}).status_code == 200
        assert w.get(f"{API}/ordner/{privat}").json["ordner"]["overview_off"] is False

        # Eine neue Gliederung der obersten Ebene darf gleich ausgeblendet angelegt werden (nur die Verwaltung legt sie an).
        r = adm.post(f"{API}/ordner", json={"name": "Platzhalter Drei", "kind": "gliederung", "overview_off": True})
        assert r.status_code == 201 and r.json["ordner"]["overview_off"] is True, r.get_json()
        assert _start(adm)["ordner_ausgeblendet"] == [{"id": r.json["ordner"]["id"], "name": "Platzhalter Drei",
                                                       "nur_pfad": False}]
    print("Schalter, Übersicht und Verschieben bestanden.")


def test_wettlauf_bearbeiten_verschieben():
    """Prüfung Ablauf R1, Befund 1: Zwischen der Prüfung „nur oberste Ebene“ und dem UPDATE darf kein anderes Konto
    die Gliederung unter eine andere schieben – sonst stünde dort overview_off = 1 und jedes weitere Bearbeiten
    scheiterte. Einschub genau in diesem Fenster: ein Schreibversuch über eine zweite Verbindung findet die Sperre."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        katalog_grund(k["adm"])
        adm, w = k["adm"], k["wart"]
        echt, _ = gliederung(w, "OG Platzhalter")
        privat, _ = gliederung(w, "Platzhalter Privat")
        from app.material.services import bestand
        orig, erlebt = bestand._uebersicht_pruefen, []

        def einschub(werte, parent_id):
            orig(werte, parent_id)
            fremd = sqlite3.connect(os.path.join(tmp, "stroemis.db"), timeout=0)
            try:
                fremd.execute("UPDATE mat_folder SET parent_id = ? WHERE id = ?", (echt, privat))
                fremd.commit()
                erlebt.append("verschoben")
            except sqlite3.OperationalError as e:
                erlebt.append(str(e))
            finally:
                fremd.close()

        bestand._uebersicht_pruefen = einschub
        try:
            r = _aus(w, privat, True)
        finally:
            bestand._uebersicht_pruefen = orig
        assert r.status_code == 200, r.get_json()
        assert erlebt == ["database is locked"], erlebt
        assert [dict(z) for z in zeilen(app, "SELECT parent_id, overview_off FROM mat_folder WHERE id = ?", (privat,))] == \
               [{"parent_id": None, "overview_off": 1}]
        # Das Verschieben danach setzt zurück, Bearbeiten geht weiter.
        assert adm.post(f"{API}/ordner/{privat}/verschieben", json={"parent_id": echt}).status_code == 200
        r = w.put(f"{API}/ordner/{privat}", json={"name": "Platzhalter Privat neu"})
        assert r.status_code == 200 and r.json["ordner"]["overview_off"] is False, r.get_json()
    print("Wettlauf Bearbeiten gegen Verschieben bestanden.")


# --- 5. Oberfläche (statisch) -------------------------------------------------------------------------------------------

def test_oberflaeche_statisch():
    with open(os.path.join(WURZEL, "app", "material", "static", "material.js"), encoding="utf-8") as f:
        js = f.read()
    assert 'overview_off: "In „Fälligkeiten je Ordner“ ausgeblendet"' in js
    assert 'feld === "reminders_off" || feld === "overview_off"' in js
    # Das Häkchen nur an einer vorhandenen Gliederung der obersten Ebene, mit Hinweis; gesendet nur dort.
    assert 'const mitUebersicht = !neu && !o.system_kind && o.kind === "gliederung" && !o.parent_id;' in js
    assert 'id="od-uebersicht"' in js and "Nicht in „Fälligkeiten je Ordner“ zeigen</label>" in js
    assert 'if (mitUebersicht) daten.overview_off = $("#od-uebersicht", body).checked;' in js
    # Zeile „Nicht gezeigt“ unter der Tabelle und der Schalter im Info-Fenster.
    assert "const ausgeblendet = d.ordner_ausgeblendet || [];" in js and "${ordnerAusgeblendetHtml(ausgeblendet)}" in js
    assert "Nicht gezeigt: " in js and "Alle Gliederungen sind hier ausgeblendet." in js
    # Der Weg im Info-Fenster wie in der Oberfläche; das „i“ auch, wenn alle Gliederungen ausgeblendet sind (Browser R1).
    info = js.split("const ordnerUebersichtInfo", 1)[1].split("\n  //", 1)[0]
    assert "im Ordner „Bearbeiten“ → „Ordner bearbeiten“, Häkchen unter „Erinnerungsmails aus“" in info
    assert "Fälligkeiten je Ordner${d.ordner_uebersicht.length || ausgeblendet.length ? infoKnopf(" in js
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_migration_frisch()
    test_migration_39_40()
    test_ausblenden()
    test_wettlauf_bearbeiten_verschieben()
    test_oberflaeche_statisch()
    print("Alle Tests für „Gliederung ausblenden“ bestanden.")
