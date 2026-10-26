"""Rückbau der Set-Funktion (Schritt 26, Wunsch vom 25.10.2026):  python tests/test_material_set_rueckbau.py  oder  pytest

Schema: frisch = migriert (20 → Ende), 25 → 26 an einer Datenbank mit Set-Altbestand aus SQL (Set-Produkt mit einzeln
geführter und Text-Position, Set-Artikel mit Kopie der Stückliste, drei Teile – frei, mitgesperrt, ausgesondert –,
abgeschlossener Set-Lauf mit Teiletabelle und festgeschriebenem Protokoll, offener Set-Lauf in einem Durchgang mit
offenem Entwurf, Set-Meldung), zweiter Lauf, Trigger aus Schritt 26. Schnittstelle: entfallene Routen, „is_set“ und
„teile“ übergangen, Bestandteil-Liste nur Text, Katalogdatei mit „set“: true als Fehler, Export ohne „set“, Vorlage,
Meldung nur Produkt, CSV ohne Set-Spalten, alte Set-Spalte im Bestandsimport ignoriert, Rechte am Reiter „Bestandteile“.
Statisch: kein Bezug mehr auf die Set-Strukturen außerhalb der erlaubten Dateien.

Alle Hersteller, Modelle und Nummern hier sind erfunden und nur für den Test da."""
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, festschreiben, make_app, neuer_artikel, starten, umgebung,  # noqa: E402
                           katalog_grund, pruef_formulare, gliederung)
from test_material_import import csv_bytes, probelauf  # noqa: E402
from test_material_trennung import bis_schritt, endversion, sql, zeilen, zwei_gliederungen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JETZT = "2026-10-01T08:00:00+00:00"


def roh(app):
    """Eine rohe Verbindung zur Datenbank der App mit ihren Pragmas (Fremdschlüssel, rekursive Trigger)."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA recursive_triggers = ON")
    return conn


def abgewiesen(conn, befehl, args=(), text=None):
    try:
        conn.execute(befehl, args)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        assert text is None or text in str(exc), (befehl, exc)
        return str(exc)
    conn.rollback()
    raise AssertionError(f"nicht abgewiesen: {befehl} {args}")


def _schema(pfad):
    conn = sqlite3.connect(pfad)
    try:
        return {(r[0], r[1]): " ".join((r[2] or "").split()) for r in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'")}
    finally:
        conn.close()


def _spalten(conn, tabelle):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]


def _unterschied(a, b):
    return {k: (a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)}


# --- Schema -------------------------------------------------------------------------------------------------------------

def test_migration_frisch_und_ab_20():
    """Frisch: keine Kopie der Stückliste mehr (mat_item_set_slot), die eingefrorenen Nachweis-Tabellen bleiben, die
    Wächter aus Schritt 26 stehen, die entfallenen Trigger nicht. 20 → Ende an einer Datenbank mit Bestand (direkt in
    SQLite): Spalten mit ihren Vorgaben, keine Zeile ändert sich, kein Fremdschlüssel bricht, das Schema gleicht dem
    frischen; ein zweiter Lauf und Schritt 26 für sich ändern nichts."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("table", "mat_item_set_slot") not in schema_frisch
    for name in ("mat_product_component", "mat_set_lauf", "mat_set_protokoll_zeile", "mat_item_component_serial"):
        assert ("table", name) in schema_frisch, name
    for name in ("mat_product_kein_set", "mat_product_kein_set_aendern", "mat_item_kein_teil", "mat_item_kein_teil_aendern",
                 "mat_component_neu", "mat_component_aendern", "mat_set_lauf_neu", "mat_inspection_in_set_lauf",
                 "mat_inspection_set_lauf_wechsel", "mat_set_lauf_beendet", "mat_set_zeile_aendern",
                 "mat_teilnummer_position"):
        assert ("trigger", name) in schema_frisch, name
    for name in models.TRIGGER_WEG_26:
        assert ("trigger", name) not in schema_frisch, name
    assert ("index", "idx_mat_item_parent") not in schema_frisch
    assert ("index", "idx_mat_component_teil") not in schema_frisch
    assert "Bestandteil-Liste ist nur Text" in schema_frisch[("trigger", "mat_component_neu")]
    assert "set_lauf_id" in schema_frisch[("trigger", "mat_inspection_festgeschrieben")]

    with tempfile.TemporaryDirectory() as tmp:
        bis_schritt(20, nachruesten=False)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        conn.execute("PRAGMA foreign_keys = ON")
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "20"
        with conn:
            conn.execute("INSERT INTO mat_category (id, name, default_material_kind, default_interval_months, created_at, "
                         "updated_at) VALUES (1, 'Migrationstest', 'metall_hardware', 12, ?, ?)", (JETZT, JETZT))
            conn.execute("INSERT INTO mat_product (id, category_id, manufacturer, model, article_no, dedupe_key, "
                         "material_kind, created_at, updated_at) VALUES (1, 1, 'Testwerk', 'Mig', 'M-1', "
                         "'testwerk|mig|m1', 'metall_hardware', ?, ?)", (JETZT, JETZT))
            conn.execute("INSERT INTO mat_folder (id, name, kind, created_at, updated_at) VALUES (1, 'OG Mig', "
                         "'gliederung', ?, ?)", (JETZT, JETZT))
            conn.execute("INSERT INTO mat_item (id, product_id, folder_id, serial_no, inventory_no, qr_token, created_at, "
                         "updated_at, last_inspected_on, next_due_on) VALUES (1, 1, 1, 'MIG-26', 'M-900001', 'tokenmig26', "
                         "?, ?, '2026-10-01', '2027-10-01')", (JETZT, JETZT))
            conn.execute("INSERT INTO mat_inspection (item_id, inspected_on, kind, result, completed_at, created_at, "
                         "updated_at) VALUES (1, '2026-10-01', 'periodisch', 'einsatzbereit', ?, ?, ?)", (JETZT, JETZT, JETZT))
        vorher = {t: conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in
                  ("mat_item", "mat_product", "mat_inspection", "mat_folder")}
        conn.close()

        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        conn = roh(app)
        try:
            for t, alt in vorher.items():
                n = len(alt[0]) if alt else 0
                assert [r[:n] for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()] == alt, t
            assert conn.execute("SELECT is_set FROM mat_product").fetchall() == [(0,)]
            assert conn.execute("SELECT parent_item_id, lock_cause, set_lock_origin, set_pruefen FROM mat_item").fetchall() \
                == [(None, None, None, 0)]
            # Schritt 26 schreibt bei leerem Altbestand kein Journal.
            assert conn.execute("SELECT COUNT(*) FROM mat_audit WHERE user_name = 'Migration Schritt 26'").fetchone()[0] == 0
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            schema = _schema(pfad)
            assert schema == schema_frisch, _unterschied(schema, schema_frisch)
            assert models.migrieren(conn) == models.SCHEMA_VERSION
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_26(conn)
            models._schritt_26(conn)
            assert conn.total_changes == n
            conn.rollback()
            assert _schema(pfad) == schema_frisch
        finally:
            conn.close()
    print("Migration frisch und 20 → Ende bestanden.")


def _altbestand_25(tmp):
    """Auf Stand 25 (die Dienste schreiben keine Set-Spalten mehr – den Altbestand legt SQL an, so wie die Set-Funktion
    ihn hinterließ; die Trigger aus 21/22/25 laufen mit):
      Set-Produkt „Altset“ (Gurte) mit „Karabiner“ (2, einzeln, HMS Beta) und „Tasche“ (Text, Austausch ja);
      Set-Artikel S in lager_a mit Kopie der Stückliste; Teile K1 (frei, set_pruefen), K2 (mitgesperrt in „Gesperrt“),
      K3 (ausgesondert); ein abgeschlossener Set-Lauf L1 mit festgeschriebener Prüfung des Set-Artikels und einer Zeile
      der Teiletabelle; ein offener Set-Lauf L2 aus einem Durchgang D über lager_a mit offenem Entwurf an K1; eine
      Set-Meldung."""
    t = zwei_gliederungen(tmp)
    app, wart, pruefer = t.app, t.wart_a, t.k["pruefer"]
    r = t.k["katalog"].post("/api/material/produkte", json={
        "category_id": t.ids["gurte"], "manufacturer": "Testwerk", "model": "Altset", "article_no": "AS-1",
        "material_kind": "textil", "lifetime_years": 10, "bestandteile": [{"bezeichnung": "Tasche", "anzahl": 1}]})
    assert r.status_code == 201, r.get_json()
    set_p = r.json["produkt"]["id"]
    sql(app, "UPDATE mat_product SET is_set = 1 WHERE id = ?", (set_p,))
    sql(app, "UPDATE mat_product_component SET austausch = 'ja', position = 2 WHERE set_product_id = ?", (set_p,))
    sql(app, "INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, einzeln, "
             "austausch, position) VALUES (?, ?, 'Karabiner', 2, 1, 'nicht_belegt', 1)", (set_p, t.ids["hms"]))
    s = neuer_artikel(wart, set_p, t.lager_a, serial_no="ALT-SET-1", manufactured_on=f"{_heute().year - 1}-03")["id"]
    sql(app, "INSERT INTO mat_item_set_slot (set_item_id, position, product_id, bezeichnung, anzahl, einzeln, austausch) "
             "VALUES (?, 1, ?, 'Karabiner', 2, 1, 'nicht_belegt')", (s, t.ids["hms"]))
    sql(app, "INSERT INTO mat_item_set_slot (set_item_id, position, product_id, bezeichnung, anzahl, einzeln, austausch) "
             "VALUES (?, 2, NULL, 'Tasche', 1, 0, 'ja')", (s,))
    k1, k2, k3 = (neuer_artikel(wart, t.ids["hms"], t.lager_a, serial_no=f"ALT-K{n}")["id"] for n in (1, 2, 3))
    for k in (k1, k2, k3):
        sql(app, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (s, k))
    sql(app, "UPDATE mat_item SET set_pruefen = 1 WHERE id = ?", (k1,))
    sql(app, "UPDATE mat_item SET lock_state = 'gesperrt', lock_cause = 'set', lock_reason = 'mit dem Set gesperrt (Test)', "
             "origin_folder_id = folder_id, folder_id = ? WHERE id = ?", (t.sys_a["gesperrt"], k2))
    sql(app, "UPDATE mat_item SET lock_state = 'ausgesondert', lock_reason = 'Test', origin_folder_id = folder_id, "
             "folder_id = ? WHERE id = ?", (t.sys_a["ausgesondert"], k3))
    sql(app, "UPDATE mat_item SET set_lock_origin = NULL, lock_cause = NULL WHERE id = ?", (s,))
    # L1: abgeschlossener Set-Lauf mit festgeschriebener Prüfung des Set-Artikels und Teiletabelle.
    sql(app, "INSERT INTO mat_set_lauf (set_item_id, opened_at, opened_by_name) VALUES (?, ?, 'Test')", (s, JETZT))
    l1 = zeilen(app, "SELECT MAX(id) AS id FROM mat_set_lauf")[0]["id"]
    r = starten(pruefer, s)
    assert r.status_code == 201, r.get_json()
    p1 = r.json["pruefung"]["id"]
    sql(app, "UPDATE mat_inspection SET set_lauf_id = ? WHERE id = ?", (l1, p1))
    sql(app, "INSERT INTO mat_set_protokoll_zeile (inspection_id, position, art, bezeichnung, inventarnummer, ergebnis) "
             "VALUES (?, 1, 'teil', 'Karabiner', 'M-000002', 'einsatzbereit')", (p1,))
    r = festschreiben(pruefer, p1, ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()
    sql(app, "UPDATE mat_set_lauf SET state = 'abgeschlossen', closed_at = ?, set_inspection_id = ? WHERE id = ?",
        (JETZT, p1, l1))
    # L2: offener Set-Lauf aus einem Durchgang, mit offenem Entwurf an K1.
    r = wart.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Altdurchgang"})
    assert r.status_code == 201, r.get_json()
    d = r.json["durchgang"]["id"]
    sql(app, "INSERT INTO mat_set_lauf (set_item_id, round_id, opened_at, opened_by_name) VALUES (?, ?, ?, 'Test')",
        (s, d, JETZT))
    l2 = zeilen(app, "SELECT MAX(id) AS id FROM mat_set_lauf")[0]["id"]
    r = starten(pruefer, k1, durchgang_id=d)
    assert r.status_code == 201, r.get_json()
    p2 = r.json["pruefung"]["id"]
    sql(app, "UPDATE mat_inspection SET set_lauf_id = ? WHERE id = ?", (l2, p2))
    sql(app, "INSERT INTO mat_product_request (manufacturer, model, dedupe_key, is_set, set_teile, created_at) VALUES "
             "('Testwerk', 'Gemeldetes Set', 'testwerk|gemeldetesset|', 1, ?, ?)", ("Karabiner, 2 Stück\nTasche", JETZT))
    return SimpleNamespace(**vars(t), set_p=set_p, s=s, k1=k1, k2=k2, k3=k3, l1=l1, l2=l2, p1=p1, p2=p2, d=d)


def test_migration_25_26_altbestand():
    """25 → 26 an einer Datenbank mit Set-Altbestand: Teile ohne Set im selben Ordner, Sperren und Ordner unverändert,
    Sperrursachen leer; das Set-Produkt ein Produkt nur mit der Text-Position (Austausch „nicht belegt“); die Kopie der
    Stückliste weg; der offene Lauf abgebrochen und vom Durchgang gelöst, sein Entwurf ein normaler Entwurf; der
    abgeschlossene Lauf, seine Teiletabelle und die Protokolldatei unverändert (Prüfseite „unverändert“); Journal je
    geänderter Zeile; die Set-Meldung behält ihre Teile; das Schema gleicht dem frischen; ein zweiter Lauf ändert nichts;
    die App arbeitet mit dem Altbestand (Artikel, Produkt, Prüfung zu Ende, Meldung)."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = bis_schritt(25)(_altbestand_25, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "25"
        lage = {r[0]: r[1:] for r in conn.execute("SELECT id, folder_id, origin_folder_id, lock_state, lock_reason, "
                                                   "assigned_user_id FROM mat_item")}
        teiletabelle = conn.execute("SELECT * FROM mat_set_protokoll_zeile").fetchall()
        l1 = conn.execute("SELECT * FROM mat_set_lauf WHERE id = ?", (t.l1,)).fetchone()
        p1 = conn.execute("SELECT protocol_id, pdf_path, file_sha256 FROM mat_inspection WHERE id = ?", (t.p1,)).fetchone()
        conn.close()
        with open(os.path.join(tmp, p1[1]), "rb") as fh:
            original = fh.read()
        assert hashlib.sha256(original).hexdigest() == p1[2]

        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        conn = roh(app)
        try:
            # Teile: ohne Set, gleiche Lage, Sperre und Zuordnung; keine Sperrursache, kein set_pruefen.
            assert conn.execute("SELECT COUNT(*) FROM mat_item WHERE parent_item_id IS NOT NULL OR lock_cause IS NOT NULL "
                                "OR set_lock_origin IS NOT NULL OR set_pruefen <> 0").fetchone()[0] == 0
            assert {r[0]: r[1:] for r in conn.execute("SELECT id, folder_id, origin_folder_id, lock_state, lock_reason, "
                                                       "assigned_user_id FROM mat_item")} == lage
            assert conn.execute("SELECT lock_state FROM mat_item WHERE id = ?", (t.k2,)).fetchone()[0] == "gesperrt"
            # Produkt: kein Set, nur die Text-Position.
            assert conn.execute("SELECT is_set FROM mat_product WHERE id = ?", (t.set_p,)).fetchone()[0] == 0
            assert conn.execute("SELECT bezeichnung, anzahl, einzeln, component_product_id, austausch FROM "
                                "mat_product_component WHERE set_product_id = ?", (t.set_p,)).fetchall() == \
                [("Tasche", 1, 0, None, "nicht_belegt")]
            assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_item_set_slot'").fetchone()
            # Läufe: L2 abgebrochen und gelöst, sein Entwurf ohne Lauf; L1 und die Teiletabelle unverändert.
            assert conn.execute("SELECT state, round_id, closed_at IS NOT NULL FROM mat_set_lauf WHERE id = ?",
                                (t.l2,)).fetchone() == ("abgebrochen", None, 1)
            assert conn.execute("SELECT set_lauf_id, completed_at, round_id FROM mat_inspection WHERE id = ?",
                                (t.p2,)).fetchone() == (None, None, t.d)
            assert conn.execute("SELECT * FROM mat_set_lauf WHERE id = ?", (t.l1,)).fetchone() == l1
            assert conn.execute("SELECT * FROM mat_set_protokoll_zeile").fetchall() == teiletabelle
            assert conn.execute("SELECT set_lauf_id FROM mat_inspection WHERE id = ?", (t.p1,)).fetchone()[0] == t.l1
            # Journal (Akteur „Migration Schritt 26“) je geänderter Zeile.
            j = conn.execute("SELECT entity, entity_id, action, after_json FROM mat_audit WHERE user_name = "
                             "'Migration Schritt 26' ORDER BY id").fetchall()
            aktionen = sorted((e, i, a) for e, i, a, _ in j)
            assert aktionen == sorted([("item", t.s, "set_lauf_abgebrochen"), ("item", t.k1, "aus_set_geloest"),
                                       ("item", t.k2, "aus_set_geloest"), ("item", t.k3, "aus_set_geloest"),
                                       ("item", t.s, "set_rueckbau"), ("product", t.set_p, "bestandteile"),
                                       ("product", t.set_p, "geaendert")]), aktionen
            rueckbau = next(json.loads(x) for e, i, a, x in j if a == "set_rueckbau")
            assert len(rueckbau["teile"]) == 3 and "Schritt 26" in rueckbau["grund"], rueckbau
            liste = next(json.loads(x) for e, i, a, x in j if a == "bestandteile")
            assert liste["bestandteile"] == [{"bezeichnung": "Tasche", "anzahl": 1}], liste
            assert conn.execute("SELECT is_set, set_teile FROM mat_product_request WHERE model = 'Gemeldetes Set'"
                                ).fetchone() == (1, "Karabiner, 2 Stück\nTasche")
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            schema = _schema(pfad)
            assert schema == schema_frisch, _unterschied(schema, schema_frisch)
            # Zweiter Lauf: nichts ändert sich.
            assert models.migrieren(conn) == models.SCHEMA_VERSION
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_26(conn)
            assert conn.total_changes == n
            conn.rollback()
        finally:
            conn.close()
        # Die Protokolldatei: unverändert auf der Platte und auf der Prüfseite.
        with open(os.path.join(tmp, p1[1]), "rb") as fh:
            assert fh.read() == original
        anon = app.test_client()
        r = anon.post("/api/material/pruefen", data={"datei": (io.BytesIO(original), "protokoll.pdf")}, headers=H,
                      content_type="multipart/form-data")
        assert r.status_code == 200 and r.json["ergebnis"] == "unveraendert" and r.json["protokoll_id"] == p1[0], r.json
        # Die App mit dem Altbestand: Artikel und Produkt lesen, den Entwurf zu Ende prüfen, die Meldung lesen.
        wart, pruefer, mv = t.wart_a, t.k["pruefer"], t.k["katalog"]
        for iid in (t.s, t.k1, t.k2, t.k3):
            r = wart.get(f"/api/material/artikel/{iid}")
            assert r.status_code == 200, r.get_json()
            assert not {"set", "teil_von", "ist_set", "lock_cause"} & set(r.json["artikel"]), iid
        p = mv.get(f"/api/material/produkte/{t.set_p}").json["produkt"]
        assert "is_set" not in p and p["bestandteile"] == [{"id": p["bestandteile"][0]["id"], "position": 2,
                                                            "bezeichnung": "Tasche", "anzahl": 1}], p
        r = festschreiben(pruefer, t.p2, ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        m = mv.get("/api/material/meldungen?status=alle").json["meldungen"]
        alt = next(x for x in m if x["model"] == "Gemeldetes Set")
        assert alt["set_teile"] == "Karabiner, 2 Stück\nTasche" and "is_set" not in alt, alt
        # Der Gesperrte bleibt gesperrt, bis ein Prüfer frei prüft (Entwurf 3.6 Nr. 2).
        r = starten(pruefer, t.k2)
        assert r.status_code == 201 and r.json["pruefung"]["freipruefung"] is True, r.get_json()
    print("Migration 25 → 26 mit Altbestand bestanden.")


def test_trigger_26():
    """Die Wächter aus Schritt 26 direkt in SQLite: kein Set-Produkt, kein Teil, kein Set-Prüflauf, keine Prüfung in
    einem, Bestandteile nur als Text; Seriennummern der Bestandteile (Schritt 25) weiter möglich."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(k["wart"])
        r = k["katalog"].post("/api/material/produkte", json={
            "category_id": ids["karabiner"], "manufacturer": "Testwerk", "model": "Mit Liste", "article_no": "ML-1",
            "material_kind": "metall_hardware", "interval_months": 12,
            "bestandteile": [{"bezeichnung": "Beutel", "anzahl": 2}]})
        assert r.status_code == 201, r.get_json()
        pl = r.json["produkt"]
        a = neuer_artikel(k["wart"], ids["hms"], gid)["id"]
        b = neuer_artikel(k["wart"], pl["id"], gid)["id"]
        entwurf = starten(k["pruefer"], a).json["pruefung"]["id"]
        conn = roh(app)
        try:
            text = "Sets gibt es nicht mehr"
            abgewiesen(conn, "INSERT INTO mat_product (category_id, manufacturer, model, dedupe_key, material_kind, is_set, "
                       "created_at, updated_at) VALUES (?, 'Testwerk', 'S', 'testwerk|s|', 'metall_hardware', 1, 'x', 'x')",
                       (ids["karabiner"],), text)
            abgewiesen(conn, "UPDATE mat_product SET is_set = 1 WHERE id = ?", (ids["hms"],), text)
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (b, a), text)
            abgewiesen(conn, "INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, qr_token, parent_item_id, "
                       "created_at, updated_at) VALUES (?, ?, 'X-1', 'M-999991', 'tok-x-1', ?, 'x', 'x')",
                       (ids["hms"], gid, a), text)
            abgewiesen(conn, "INSERT INTO mat_set_lauf (set_item_id, opened_at) VALUES (?, 'x')", (a,), "Set-Prüfungen")
            abgewiesen(conn, "INSERT INTO mat_inspection (item_id, inspected_on, kind, set_lauf_id, created_at, updated_at) "
                       "VALUES (?, '2026-10-01', 'periodisch', 1, 'x', 'x')", (b,), "Set-Prüfungen")
            abgewiesen(conn, "UPDATE mat_inspection SET set_lauf_id = 1 WHERE id = ?", (entwurf,), "Set-Prüfungen")
            nur_text = "nur Text"
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                       "einzeln) VALUES (?, ?, 'Teil', 1, 1)", (pl["id"], ids["hms"]), nur_text)
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, bezeichnung, anzahl, austausch) "
                       "VALUES (?, 'Tasche', 1, 'ja')", (pl["id"],), nur_text)
            abgewiesen(conn, "UPDATE mat_product_component SET austausch = 'nein' WHERE set_product_id = ?", (pl["id"],),
                       nur_text)
            conn.execute("INSERT INTO mat_product_component (set_product_id, bezeichnung, anzahl, position) "
                         "VALUES (?, 'Riemen', 1, 5)", (pl["id"],))
            conn.rollback()
            pos = pl["bestandteile"][0]["id"]
            conn.execute("INSERT INTO mat_item_component_serial (item_id, component_id, stueck, serial_no, updated_at) "
                         "VALUES (?, ?, 1, 'B-1', 'x')", (b, pos))
            conn.commit()
        finally:
            conn.close()
    print("Trigger aus Schritt 26 bestanden.")


# --- Schnittstelle ------------------------------------------------------------------------------------------------------

def _importieren(app, daten, trocken=False):
    with app.app_context():
        from app.material.services import importer
        return importer.importieren(daten, trocken=trocken, quelle="Test")


def test_schnittstelle():
    """Entfallene Routen 404; POST /produkte mit „is_set“ legt ein Produkt an, Positionen mit „einzeln“, Produkt oder
    Austausch 400; POST /artikel mit „teile“ legt einen Artikel an; Meldung ohne Wahl Set; Katalogdatei: „set“: true ist
    ein Fehler dieses Produkts, „set“: false geht, Bericht ohne „stuecklisten“; die Vorlage geht fehlerfrei durch; der
    Export schreibt nie „set“; die Artikel-CSV hat keine Set-Spalten, der Bestandsimport ignoriert eine alte."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        mv, wart = k["katalog"], k["wart"]
        ids = katalog_grund(k["adm"])
        gid, _ = gliederung(wart)
        a = neuer_artikel(wart, ids["hms"], gid)["id"]
        for methode, url in (("get", f"/materialablage/artikel/{a}/set-pruefung"), ("get", f"/api/material/artikel/{a}/set-lauf"),
                             ("post", f"/api/material/artikel/{a}/set-lauf"), ("post", f"/api/material/artikel/{a}/aufloesen"),
                             ("post", f"/api/material/artikel/{a}/teil-entnehmen"),
                             ("get", f"/api/material/produkte/{ids['hms']}/stueckliste-uebertragen"),
                             ("post", f"/api/material/produkte/{ids['hms']}/stueckliste-uebertragen")):
            assert getattr(mv, methode)(url, json={}).status_code == 404, url
        r = mv.post("/api/material/produkte", json={
            "category_id": ids["karabiner"], "manufacturer": "Testwerk", "model": "Kein Set", "article_no": "KS-1",
            "material_kind": "metall_hardware", "interval_months": 12, "is_set": True,
            "bestandteile": [{"bezeichnung": "Tasche", "anzahl": 1}]})
        assert r.status_code == 201, r.get_json()
        assert "is_set" not in r.json["produkt"] and len(r.json["produkt"]["bestandteile"]) == 1
        assert zeilen(app, "SELECT is_set FROM mat_product WHERE id = ?", (r.json["produkt"]["id"],))[0]["is_set"] == 0
        for falsch in ({"bezeichnung": "Karabiner", "anzahl": 2, "einzeln": True, "produkt_id": ids["hms"]},
                       {"bezeichnung": "Karabiner", "produkt_id": ids["hms"]}, {"bezeichnung": "Tasche", "austausch": "ja"}):
            r = mv.put(f"/api/material/produkte/{ids['hms']}/bestandteile", json={"bestandteile": [falsch]})
            assert r.status_code == 400 and r.json["error"].startswith("Position 1: "), (falsch, r.get_json())
        r = wart.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": gid, "serial_no": "T-1",
                                                     "teile": [{"bestandteil_id": 1}]})
        assert r.status_code == 201 and "hinweise" not in r.json, r.get_json()
        # Meldung: nur Produkt – „is_set“ und „set_teile“ werden übergangen.
        r = wart.post("/api/material/meldungen", json={"manufacturer": "Testwerk", "model": "Neu gemeldet",
                                                       "folder_id": gid, "is_set": True, "set_teile": "x"})
        assert r.status_code == 201 and r.json["meldung"]["set_teile"] == "" and "is_set" not in r.json["meldung"], r.json
        assert zeilen(app, "SELECT is_set, set_teile FROM mat_product_request WHERE model = 'Neu gemeldet'")[0] == \
            {"is_set": 0, "set_teile": ""}
        # Katalogdatei.
        kopf = {"format": "stroemis-material-katalog", "version": 1,
                "kategorien": [{"name": "Rückbau", "materialart": "metall_hardware", "intervall_monate": 12}]}
        b = _importieren(app, dict(kopf, produkte=[
            {"kategorie": ["Rückbau"], "hersteller": "Testwerk", "modell": "Altset", "artikelnummer": "R-1", "set": True,
             "materialart": "metall_hardware", "bestandteile": [{"bezeichnung": "Tasche", "anzahl": 1}]},
            {"kategorie": ["Rückbau"], "hersteller": "Testwerk", "modell": "Normal", "artikelnummer": "R-2", "set": False,
             "materialart": "metall_hardware", "bestandteile": [{"bezeichnung": "Tasche", "anzahl": 1}]}]), trocken=True)
        assert len(b["fehler"]) == 1 and b["fehler"][0].startswith("produkte[0] (") and "Sets gibt es nicht mehr" in \
            b["fehler"][0] and "Ordner der Art „Set“" in b["fehler"][0], b["fehler"]
        assert "stuecklisten" not in b
        b = _importieren(app, dict(kopf, produkte=[
            {"kategorie": ["Rückbau"], "hersteller": "Testwerk", "modell": "Normal", "artikelnummer": "R-2", "set": False,
             "materialart": "metall_hardware", "bestandteile": [{"bezeichnung": "Tasche", "anzahl": 1}]}]))
        assert not b["fehler"] and b["bestandteillisten"]["neu"] == 1, b
        with open(os.path.join(REPO, "docs", "material-katalog-bestandteile-vorlage.json"), encoding="utf-8") as fh:
            vorlage = json.load(fh)
        assert not any("set" in p for p in vorlage["produkte"])
        b = _importieren(app, vorlage, trocken=True)
        assert not b["fehler"], b["fehler"]
        assert not os.path.exists(os.path.join(REPO, "docs", "material-katalog-set-vorlage.json"))
        with app.app_context():
            from app.material.services import katalog_export
            daten, _, bericht = katalog_export.sammeln()
        assert all("set" not in p for p in daten["produkte"]) and "set_verstoesse" not in bericht
        assert any(p.get("bestandteile") == [{"bezeichnung": "Tasche", "anzahl": 1}] for p in daten["produkte"])
        # Artikel-CSV ohne Set-Spalten; eine Spalte „Set (Inventarnummer)“ aus einem älteren Export ignoriert der
        # Bestandsimport.
        r = wart.get(f"/materialablage/export/{gid}.csv")
        assert r.status_code == 200, r.status_code
        kopfzeile = r.data.decode("utf-8-sig").splitlines()[0]
        assert "Set" not in kopfzeile, kopfzeile
        p = probelauf(wart, gid, csv_bytes([["Hersteller", "Modell", "Seriennummer", "Set (Inventarnummer)"],
                                            ["Testwerk", "HMS Beta", "CSV-1", "M-000001"]])).json
        spalte = next(s for s in p["spalten"] if s["titel"] == "Set (Inventarnummer)")
        assert spalte["zuordnung"] == "ignorieren", spalte
    print("Schnittstelle nach dem Rückbau bestanden.")


def test_rechte_bestandteile():
    """Reiter „Bestandteile“: PUT …/bestandteile und POST /produkte mit Liste nur für die Material-Verwaltung (sonst 403);
    lesen jeder mit Modulzugang."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        gliederung(k["wart"])
        url = f"/api/material/produkte/{ids['hms']}/bestandteile"
        liste = {"bestandteile": [{"bezeichnung": "Beutel", "anzahl": 1}]}
        for rolle in ("wart", "fuehrung", "pruefer", "nutzer"):
            assert k[rolle].put(url, json=liste).status_code == 403, rolle
            assert k[rolle].post("/api/material/produkte", json=dict(liste, category_id=ids["karabiner"],
                                 manufacturer="X", model="Y", material_kind="metall_hardware")).status_code == 403, rolle
        r = k["katalog"].put(url, json=liste)
        assert r.status_code == 200 and r.json["geaendert"] is True, r.get_json()
        for rolle in ("wart", "fuehrung", "pruefer"):
            p = k[rolle].get(f"/api/material/produkte/{ids['hms']}").json["produkt"]
            assert [x["bezeichnung"] for x in p["bestandteile"]] == ["Beutel"], rolle
        assert k["nutzer"].get(f"/api/material/produkte/{ids['hms']}").status_code == 403
    print("Rechte am Reiter „Bestandteile“ bestanden.")


# --- Statisch -----------------------------------------------------------------------------------------------------------

# Außerhalb dieser Dateien darf nichts mehr die Set-Strukturen lesen oder schreiben: das Schema (Schritte 21/22/26), die
# Lesetexte des Journals, dieser Test und die älteren Migrationstests, die den Stand vor Schritt 26 nachstellen.
ERLAUBT = {"app/material/models.py", "app/material/services/beschriftung.py", "tests/test_material_set_rueckbau.py",
           "tests/test_material_trennung.py"}
SET_BEGRIFFE = re.compile(r"parent_item_id|lock_cause|set_lock_origin|set_pruefen|\bis_set\b|set_lauf_id|mat_item_set_slot|"
                          r"mat_set_lauf|mat_set_protokoll_zeile|\b(?:sets|setlauf|setaustausch|setkopie)\.")


def test_kein_set_rest():
    """Kein Bezug mehr auf die Set-Strukturen in app/ und scripts/ (außer ERLAUBT; Docstrings und Kommentare zählen mit –
    nur Hinweise auf „is_set“ als übergangener Schlüssel sind erlaubt) und keiner auf die Set-Module in tests/; keine
    Set-Module; material.js ohne die Wege der Set-Funktion."""
    for name in ("sets", "setlauf", "setaustausch", "setkopie"):
        assert not os.path.exists(os.path.join(REPO, "app", "material", "services", f"{name}.py")), name
    assert not os.path.exists(os.path.join(REPO, "app", "material", "routes_sets.py"))
    funde = []
    for wurzel in ("app", "scripts"):
        for ordner, _, dateien in os.walk(os.path.join(REPO, wurzel)):
            for datei in dateien:
                if not datei.endswith((".py", ".html")):
                    continue
                pfad = os.path.relpath(os.path.join(ordner, datei), REPO)
                if pfad in ERLAUBT:
                    continue
                with open(os.path.join(REPO, pfad), encoding="utf-8") as fh:
                    for n, zeile in enumerate(fh, start=1):
                        z = zeile.replace("„is_set“", "")
                        if SET_BEGRIFFE.search(z):
                            funde.append(f"{pfad}:{n}: {zeile.strip()[:100]}")
    # Tests prüfen die Abwesenheit der Schlüssel („"is_set" not in …“) – dort zählen nur Bezüge auf die Set-Module.
    for ordner, _, dateien in os.walk(os.path.join(REPO, "tests")):
        for datei in dateien:
            pfad = os.path.relpath(os.path.join(ordner, datei), REPO)
            if datei.endswith(".py") and pfad not in ERLAUBT:
                with open(os.path.join(REPO, pfad), encoding="utf-8") as fh:
                    for n, zeile in enumerate(fh, start=1):
                        if re.search(r"\b(?:sets|setlauf|setaustausch|setkopie)\.|test_material_sets", zeile):
                            funde.append(f"{pfad}:{n}: {zeile.strip()[:100]}")
    assert not funde, "\n".join(funde)
    with open(os.path.join(REPO, "app", "material", "static", "material.js"), encoding="utf-8") as fh:
        js = fh.read()
    # Die Lesetexte des Journals (FELD, AKTION, SET_WERTE) behalten die Wörter der Set-Funktion für den Altbestand.
    js = re.sub(r"\n  const (?:FELD|AKTION|SET_WERTE) = \{.*?\n  \};", "", js, flags=re.S)
    for wort in ("Set anlegen", "Set prüfen", "set_lauf", "teil_von", "is_set", "Set-Ordner", "stueckliste-uebertragen",
                 "/set-lauf", "teil-entnehmen", "aufloesen"):
        assert wort not in js, wort
    from app.material.models import ORDNERARTEN
    assert ORDNERARTEN["set"] == "Set"
    print("Kein Set-Rest bestanden.")


if __name__ == "__main__":
    test_migration_frisch_und_ab_20()
    test_migration_25_26_altbestand()
    test_trigger_26()
    test_schnittstelle()
    test_rechte_bestandteile()
    test_kein_set_rest()
    print("Alle Tests des Set-Rückbaus bestanden.")
