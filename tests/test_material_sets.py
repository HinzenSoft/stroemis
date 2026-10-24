"""Sets mit Komponenten (Phase 4 · Lieferung 2, Paket K1):  python tests/test_material_sets.py  oder  pytest

Schema-Schritt 21 (frisch, 20 → 21, zweiter Lauf, Fremdschlüssel, Trigger), Katalog (Stückliste, „Set“,
Grenzen, Löschen, Variante, Katalogdatei Format 2 hin und zurück), Bestand (Set anlegen, Set-Block, Listen nur mit der
Set-Zeile, Set-Status gegen status.status(), Weichen der Einzelwege als Tabelle „Route × {Set-Artikel, Teil, freier
Artikel}“, set_stimmig mit Teil-Kennung < Set-Kennung bei Ordner verschieben, Artikel verschieben, Ordner löschen und
Konto löschen), Trennung je Gliederung, Meine PSA, Steckbrief, Bestandsimport und das DEMO-Skript.

Alle Hersteller, Modelle, Nummern und Stücklisten hier sind erfunden und nur für den Test da."""
import contextlib
import importlib.util
import io
import logging
import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, festschreiben, gliederung, katalog_grund, make_app,  # noqa: E402
                           mails_abfangen, mails_zurueck, neuer_artikel, neues_konto, starten, umgebung)
from test_material_import import csv_bytes, nach_nr, ok, probelauf  # noqa: E402
from test_material_trennung import bis_schritt, endversion, sql, zeilen, zwei_gliederungen  # noqa: E402
from test_material_ueberblick import ohne_post, ordner_neu, zustand  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- Aufbau -------------------------------------------------------------------------------------------------------------

def set_katalog(mv, ids):
    """Zum Katalog aus katalog_grund: „Rolle Gamma“ (Metall, Karabiner) und das Set-Produkt „Testset Alpha“ (textil, in
    „Gurte“ – dort gilt das generische Formular) mit Stückliste: zwei einzeln geführte HMS Beta, eine Rolle Gamma
    (Austausch ja), eine Tasche (nur Text). Liefert (Set-Produkt, Rolle, Stückliste als JSON)."""
    rolle = ok(mv.post("/api/material/produkte", json={
        "category_id": ids["karabiner"], "manufacturer": "Testwerk", "model": "Rolle Gamma", "article_no": "RG-1",
        "material_kind": "metall_hardware", "interval_months": 12}), 201)["produkt"]["id"]
    # Set anlegen (Wunsch vom 24.10.2026): Produkt und Stückliste in einer Anfrage.
    p = ok(mv.post("/api/material/produkte", json={
        "category_id": ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Alpha", "article_no": "TS-1",
        "material_kind": "textil", "lifetime_years": 10, "is_set": True, "bestandteile": [
            {"produkt_id": ids["hms"], "bezeichnung": "Verbindungselement", "anzahl": 2, "einzeln": True},
            {"produkt_id": rolle, "anzahl": 1, "einzeln": True, "austausch": "ja"},
            {"bezeichnung": "Tasche", "anzahl": 1, "einzeln": False}]}), 201)["produkt"]
    assert p["is_set"] is True and len(p["bestandteile"]) == 3, p
    return p["id"], rolle, p["bestandteile"]


def teile_fuer(stueckliste, serien=()):
    """„teile“ für POST /artikel: je einzeln geführter Position so viele, wie die Stückliste nennt – mit den Seriennummern
    der Reihe nach (leer: STR-Nummer)."""
    serien = iter(serien)
    return [{"bestandteil_id": b["id"], "serial_no": next(serien, "")}
            for b in stueckliste if b["einzeln"] for _ in range(b["anzahl"])]


def set_neu(c, set_p, ordner, stueckliste, serie, teil_serien=(), **felder):
    r = c.post("/api/material/artikel", json=dict({"product_id": set_p, "folder_id": ordner, "serial_no": serie,
                                                    "manufactured_on": f"{_heute().year - 1}-03",
                                                    "teile": teile_fuer(stueckliste, teil_serien)}, **felder))
    assert r.status_code == 201, r.get_json()
    return r.json


def set_aufbau(tmp):
    """zwei_gliederungen (A mit lager_a, B mit lager_b) und der Set-Katalog; in lager_a ein Set S (Teile HMS, HMS, Rolle)
    und ein freier Artikel F; in lager_b ein Set SB. Mails der Produktmeldungen verwirft der Aufrufer (ohne_post)."""
    t = zwei_gliederungen(tmp)
    set_p, rolle, liste = set_katalog(t.k["katalog"], t.ids)
    s = set_neu(t.wart_a, set_p, t.lager_a, liste, "SET-A-1", ("SET-A-K1", "SET-A-K2", "SET-A-R1"))
    sb = set_neu(t.wart_b, set_p, t.lager_b, liste, "SET-B-1", ("SET-B-K1", "SET-B-K2", "SET-B-R1"))
    f = neuer_artikel(t.wart_a, t.ids["hms"], t.lager_a, serial_no="FREI-A-1")
    return SimpleNamespace(**vars(t), set_p=set_p, rolle=rolle, liste=liste, s=s["artikel"], hinweise=s["hinweise"],
                           sb=sb["artikel"], f=f, teile=[x["id"] for x in s["artikel"]["set"]["teile"]],
                           teile_b=[x["id"] for x in sb["artikel"]["set"]["teile"]])


def stimmig(app):
    with app.app_context():
        from app.material.services import sets
        return sets.unstimmige() == []


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


# --- Schema-Schritt 21 --------------------------------------------------------------------------------------------------

def test_migration_21():
    """Frisch: Stand 21 mit allen Tabellen, Spalten, Indizes und Triggern. 20 → 21 an einer Datenbank mit Bestand
    (Kategorie, Produkt, Gliederung, Artikel, abgeschlossene Prüfung – direkt in SQLite, denn die Dienste schreiben seit
    Schritt 21 dessen Spalten): die Spalten kommen mit ihren Vorgaben dazu, keine Zeile ändert sich, kein Fremdschlüssel
    bricht, das Schema gleicht danach dem frischen; zweiter Lauf und Schritt 21 für sich ändern nichts; die Fest-Trigger
    aus Schritt 6 kennen set_lauf_id; die CHECKs greifen."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    for name in ("mat_product_component", "mat_item_set_slot", "mat_set_lauf", "mat_set_protokoll_zeile"):
        assert ("table", name) in schema_frisch, name
    for name in ("mat_item_teil_neu", "mat_item_teil_setzen", "mat_item_set_produkt", "mat_product_set_umschalten",
                 "mat_component_neu", "mat_slot_neu", "mat_slot_aendern", "mat_slot_loeschen", "mat_set_lauf_neu",
                 "mat_set_lauf_beendet", "mat_inspection_in_set_lauf", "mat_set_zeile_neu", "mat_set_zeile_aendern"):
        assert ("trigger", name) in schema_frisch, name
    assert "set_lauf_id" in schema_frisch[("trigger", "mat_inspection_festgeschrieben")]
    assert "set_lauf_id" in schema_frisch[("trigger", "mat_inspection_abgeschlossen")]
    # Keine Kreuzzeilen-Trigger auf Lage, Sperre und Zuordnung (S1, A8).
    for (art, name), text in schema_frisch.items():
        if art == "trigger" and "ON mat_item" in text:
            kopf = text.split(" WHEN ")[0]
            assert not any(f"OF {s}" in kopf or f", {s}" in kopf for s in ("folder_id", "origin_folder_id", "lock_state",
                                                                            "assigned_user_id")), (name, kopf)

    with tempfile.TemporaryDirectory() as tmp:
        bis_schritt(20, nachruesten=False)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        conn.execute("PRAGMA foreign_keys = ON")
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "20"
        assert "is_set" not in _spalten(conn, "mat_product") and "parent_item_id" not in _spalten(conn, "mat_item")
        assert "set_lauf_id" not in _spalten(conn, "mat_inspection")
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_product_component'").fetchone()
        ts = "2026-10-01T08:00:00+00:00"
        with conn:
            conn.execute("INSERT INTO mat_category (id, name, default_material_kind, default_interval_months, created_at, "
                         "updated_at) VALUES (1, 'Migrationstest', 'metall_hardware', 12, ?, ?)", (ts, ts))
            conn.execute("INSERT INTO mat_product (id, category_id, manufacturer, model, article_no, dedupe_key, "
                         "material_kind, created_at, updated_at) VALUES (1, 1, 'Testwerk', 'Mig', 'M-1', "
                         "'testwerk|mig|m1', 'metall_hardware', ?, ?)", (ts, ts))
            conn.execute("INSERT INTO mat_folder (id, name, kind, created_at, updated_at) VALUES (1, 'OG Mig', "
                         "'gliederung', ?, ?)", (ts, ts))
            conn.execute("INSERT INTO mat_item (id, product_id, folder_id, serial_no, inventory_no, qr_token, created_at, "
                         "updated_at, last_inspected_on, next_due_on) VALUES (1, 1, 1, 'MIG-21', 'M-900001', 'tokenmig21', "
                         "?, ?, '2026-10-01', '2027-10-01')", (ts, ts))
            conn.execute("INSERT INTO mat_inspection (item_id, inspected_on, kind, result, completed_at, created_at, "
                         "updated_at) VALUES (1, '2026-10-01', 'periodisch', 'einsatzbereit', ?, ?, ?)", (ts, ts, ts))
        vorher = {t: conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in
                  ("mat_item", "mat_product", "mat_inspection", "mat_audit", "mat_folder")}
        conn.close()

        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        conn = roh(app)
        try:
            # Die alten Spalten unverändert, die neuen mit ihren Vorgaben.
            for t, alt in vorher.items():
                n = len(alt[0]) if alt else 0
                assert [r[:n] for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()] == alt, t
            assert conn.execute("SELECT is_set FROM mat_product").fetchall() == [(0,)]
            assert conn.execute("SELECT parent_item_id, lock_cause, set_lock_origin, set_pruefen FROM mat_item").fetchall() \
                == [(None, None, None, 0)]
            assert conn.execute("SELECT set_lauf_id FROM mat_inspection").fetchall() == [(None,)]
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            schema = _schema(pfad)
            assert schema == schema_frisch, {k: (schema.get(k), schema_frisch.get(k)) for k in set(schema) | set(schema_frisch)
                                             if schema.get(k) != schema_frisch.get(k)}
            # Fest-Trigger mit set_lauf_id (S4): an der abgeschlossenen Prüfung abgewiesen (hier greift zuerst der
            # Lauf-Trigger – den Fest-Trigger allein zeigt test_trigger_21 mit NULL).
            abgewiesen(conn, "UPDATE mat_inspection SET set_lauf_id = 1")
            # CHECKs der neuen Spalten.
            for befehl in ("UPDATE mat_product SET is_set = 2", "UPDATE mat_item SET lock_cause = 'x'",
                           "UPDATE mat_item SET set_lock_origin = 'x'", "UPDATE mat_item SET set_pruefen = 3"):
                abgewiesen(conn, befehl)
            # Zweiter Lauf und Schritt 21 für sich: keine Zeile ändert sich.
            assert models.migrieren(conn) == models.SCHEMA_VERSION
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_21(conn)
            assert conn.total_changes == n
            conn.rollback()
            assert _schema(pfad) == schema_frisch
        finally:
            conn.close()
    print("Migration 20 → 21 bestanden.")


def test_trigger_21():
    """Die Einzeilen-Trigger aus Schritt 21, direkt in SQLite (mit den Pragmas der App): Teil nur über NULL, nur an einem
    Set-Artikel, nur mit Produkt laut Kopie der Stückliste, kein Set als Teil, nicht ausgesondert; Produkt fest an Teil und
    Set und von/zu einem Set-Produkt; „Set“ nur ohne Artikel und nicht für Bestandteile; Stückliste nur an Sets
    und ohne Sets; Kopie unveränderlich (auch gegen REPLACE); Set-Prüflauf; Prüfungen im Lauf; Teiletabelle des
    Set-Protokolls wie mat_inspection_result."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, s, f = t.app, t.s["id"], t.f["id"]
        k1, k2, r1 = t.teile
        frei2 = neuer_artikel(t.wart_a, t.ids["hms"], t.lager_a, serial_no="FREI-A-2")["id"]
        gurt = neuer_artikel(t.wart_a, t.ids["gurt"], t.lager_a, serial_no="GURT-A-1",
                             manufactured_on=f"{_heute().year - 1}-01")["id"]
        conn = roh(app)
        try:
            # parent_item_id: X → Y verboten, Selbstverweis, an einen Nicht-Set-Artikel, Set als Teil, Produkt nicht in
            # der Kopie, ausgesondert.
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (t.sb["id"], k1), "Teil")
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = id WHERE id = ?", (f,), "Teil")
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (f, frei2), "Teil")
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (s, t.sb["id"]), "Teil")
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (s, gurt), "Teil")
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (k1, frei2), "Teil")
            conn.execute("UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (frei2,))
            abgewiesen(conn, "UPDATE mat_item SET parent_item_id = ?, lock_state = 'ausgesondert' WHERE id = ?",
                       (s, frei2), "Teil")
            # NULL → Set geht (so setzt K2 ein Teil ein), NULL zurück auch (entnehmen).
            conn.execute("UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (s, f))
            conn.execute("UPDATE mat_item SET parent_item_id = NULL WHERE id = ?", (f,))
            conn.rollback()
            # Ein neues Teil per INSERT nur nach denselben Regeln.
            abgewiesen(conn, "INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, qr_token, parent_item_id, "
                       "created_at, updated_at) VALUES (?, ?, 'X-1', 'M-999991', 'tok-x-1', ?, 'x', 'x')",
                       (t.ids["gurt"], t.lager_a, s), "Teil")
            # Produkt fest an Teil und Set, von/zu Set-Produkt.
            abgewiesen(conn, "UPDATE mat_item SET product_id = ? WHERE id = ?", (t.rolle, k1), "Produkt")
            abgewiesen(conn, "UPDATE mat_item SET product_id = ? WHERE id = ?", (t.ids["gurt"], s), "Produkt")
            abgewiesen(conn, "UPDATE mat_item SET product_id = ? WHERE id = ?", (t.set_p, f), "Produkt")
            # „Set“: nicht mit Artikeln, nicht für einen Bestandteil, nicht aus bei vorhandener Stückliste.
            abgewiesen(conn, "UPDATE mat_product SET is_set = 0 WHERE id = ?", (t.set_p,), "Set")
            leer = conn.execute("INSERT INTO mat_product (category_id, manufacturer, model, dedupe_key, material_kind, "
                                "interval_months, created_at, updated_at) VALUES (?, 'Testwerk', 'Leer', 'testwerk|leer|', "
                                "'metall_hardware', 12, 'x', 'x')", (t.ids["karabiner"],)).lastrowid
            conn.commit()
            abgewiesen(conn, "UPDATE mat_product SET is_set = 1 WHERE id = ?", (t.ids["hms"],), "Set")
            conn.execute("UPDATE mat_product SET is_set = 1 WHERE id = ?", (leer,))
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                       "einzeln) VALUES (?, ?, 'Set im Set', 1, 1)", (t.set_p, leer), "kein Set")
            conn.execute("UPDATE mat_product SET is_set = 0 WHERE id = ?", (leer,))
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                       "einzeln) VALUES (?, ?, 'an Nicht-Set', 1, 1)", (t.ids["hms"], leer), "kein Set")
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, bezeichnung, anzahl, einzeln) "
                       "VALUES (?, 'einzeln ohne Produkt', 1, 1)", (t.set_p,))
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                       "einzeln) VALUES (?, ?, 'Text mit Produkt', 1, 0)", (t.set_p, leer))
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, bezeichnung, anzahl, einzeln) "
                       "VALUES (?, 'zu viele', 21, 0)", (t.set_p,))
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, bezeichnung, anzahl, einzeln, austausch) "
                       "VALUES (?, 'Austausch', 1, 0, 'vielleicht')", (t.set_p,))
            # Bestandteil-Produkt löschen: RESTRICT (der Dienst antwortet vorher 409).
            abgewiesen(conn, "DELETE FROM mat_product WHERE id = ?", (t.rolle,))
            # Kopie der Stückliste: nie ändern, nicht per REPLACE (als Ganzes ersetzen seit Schritt 22 – siehe
            # test_material_sets_uebertragen.test_schritt_22).
            slot = conn.execute("SELECT * FROM mat_item_set_slot WHERE set_item_id = ? ORDER BY id LIMIT 1", (s,)).fetchone()
            abgewiesen(conn, "UPDATE mat_item_set_slot SET anzahl = 3 WHERE id = ?", (slot[0],), "unveränderlich")
            abgewiesen(conn, "INSERT OR REPLACE INTO mat_item_set_slot (id, set_item_id, position, bezeichnung, anzahl, "
                       "einzeln, austausch) VALUES (?, ?, 0, 'Ersatz', 1, 0, 'ja')", (slot[0], s), "als Ganzes")
            # Set-Prüflauf: nur an einem Set-Artikel, nur offen, höchstens einer offen je Set.
            abgewiesen(conn, "INSERT INTO mat_set_lauf (set_item_id, opened_at) VALUES (?, 'x')", (f,), "Set-Prüflauf")
            abgewiesen(conn, "INSERT INTO mat_set_lauf (set_item_id, opened_at, state, closed_at) VALUES (?, 'x', "
                       "'abgeschlossen', 'x')", (s,), "Set-Prüflauf")
            lauf = conn.execute("INSERT INTO mat_set_lauf (set_item_id, opened_at) VALUES (?, 'x')", (s,)).lastrowid
            conn.commit()
            abgewiesen(conn, "INSERT INTO mat_set_lauf (set_item_id, opened_at) VALUES (?, 'y')", (s,))
            abgewiesen(conn, "UPDATE mat_set_lauf SET set_item_id = ? WHERE id = ?", (t.sb["id"], lauf), "Set-Prüflauf")
            # Prüfungen im Lauf: nur Set-Artikel und Teile dieses Sets.
            abgewiesen(conn, "INSERT INTO mat_inspection (item_id, inspected_on, kind, set_lauf_id, created_at, updated_at) "
                       "VALUES (?, '2026-10-01', 'periodisch', ?, 'x', 'x')", (f, lauf), "Set-Prüflauf")
            px = conn.execute("INSERT INTO mat_inspection (item_id, inspected_on, kind, set_lauf_id, created_at, updated_at) "
                              "VALUES (?, '2026-10-01', 'periodisch', ?, 'x', 'x')", (k1, lauf)).lastrowid
            # Teiletabelle: am offenen Entwurf ja, danach nichts mehr.
            zeile = conn.execute("INSERT INTO mat_set_protokoll_zeile (inspection_id, position, art, bezeichnung) "
                                 "VALUES (?, 1, 'teil', 'Verbindungselement')", (px,)).lastrowid
            conn.commit()
            abgewiesen(conn, "INSERT INTO mat_set_protokoll_zeile (inspection_id, position, art) VALUES (?, 2, 'x')", (px,))
            conn.execute("UPDATE mat_inspection SET result = 'einsatzbereit', completed_at = 'x' WHERE id = ?", (px,))
            conn.execute("UPDATE mat_set_lauf SET state = 'abgeschlossen', closed_at = 'x' WHERE id = ?", (lauf,))
            conn.commit()
            for befehl, args in (("UPDATE mat_set_protokoll_zeile SET ergebnis = 'aussondern' WHERE id = ?", (zeile,)),
                                 ("DELETE FROM mat_set_protokoll_zeile WHERE id = ?", (zeile,)),
                                 ("INSERT INTO mat_set_protokoll_zeile (inspection_id, position, art) VALUES (?, 3, 'teil')",
                                  (px,)),
                                 ("INSERT OR REPLACE INTO mat_set_protokoll_zeile (id, inspection_id, position, art) "
                                  "VALUES (?, ?, 1, 'teil')", (zeile, px))):
                abgewiesen(conn, befehl, args, "abgeschlossene Prüfung")
            abgewiesen(conn, "UPDATE mat_inspection SET set_lauf_id = NULL WHERE id = ?", (px,), "abgeschlossene Prüfung")
            abgewiesen(conn, "UPDATE mat_set_lauf SET state = 'offen', closed_at = NULL WHERE id = ?", (lauf,), "Set-Prüflauf")
            abgewiesen(conn, "DELETE FROM mat_set_lauf WHERE id = ?", (lauf,), "Set-Prüflauf")
            abgewiesen(conn, "INSERT INTO mat_inspection (item_id, inspected_on, kind, set_lauf_id, created_at, updated_at) "
                       "VALUES (?, '2026-10-01', 'periodisch', ?, 'x', 'x')", (k2, lauf), "Set-Prüflauf")
            assert r1
        finally:
            conn.close()
    print("Trigger aus Schritt 21 bestanden.")


# --- Katalog ------------------------------------------------------------------------------------------------------------

def test_katalog_stueckliste():
    """Stückliste über die Schnittstelle: nur Katalog (403 sonst), nur an Sets (409), Regeln und Grenzen (400), DEMO-
    Bestandteil in echtem Set, Journal „stueckliste“, „Bestandteil von“, Löschen eines Bestandteils 409, „Set“
    umschalten (mit Artikeln 409, Bestandteil 409, ausschalten nimmt die Stückliste mit), Variante mit Stückliste."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        mv = k["katalog"]
        ids = katalog_grund(k["adm"])
        set_p, rolle, liste = set_katalog(mv, ids)
        assert [(b["bezeichnung"], b["anzahl"], b["einzeln"], b["austausch"], (b["produkt"] or {}).get("id"))
                for b in liste] == [("Verbindungselement", 2, True, "nicht_belegt", ids["hms"]),
                                    ("Testwerk Rolle Gamma", 1, True, "ja", rolle), ("Tasche", 1, False, "nicht_belegt", None)]
        url = f"/api/material/produkte/{set_p}/bestandteile"
        assert k["wart"].put(url, json={"bestandteile": []}).status_code == 403
        assert k["fuehrung"].put(url, json={"bestandteile": []}).status_code == 403
        r = mv.put(f"/api/material/produkte/{ids['hms']}/bestandteile", json={"bestandteile": []})
        assert r.status_code == 409 and "Set" in r.json["error"], r.get_json()

        def falsch(eintraege, text, code=400):
            r = mv.put(url, json={"bestandteile": eintraege})
            assert r.status_code == code and text in r.json["error"], (eintraege, r.status_code, r.get_json())
        falsch([{"bezeichnung": "ohne Produkt", "einzeln": True}], "Katalogprodukt")
        falsch([{"produkt_id": rolle, "einzeln": False}], "nur Text")
        falsch([{"produkt_id": set_p, "einzeln": True}], "selbst eins")
        falsch([{"bezeichnung": "", "einzeln": False}], "Bezeichnung")
        falsch([{"bezeichnung": "x" * 121, "einzeln": False}], "zu lang")
        falsch([{"bezeichnung": "zwei\nZeilen" + "x" * 120, "einzeln": False}], "zu lang")
        falsch([{"bezeichnung": "Tasche", "anzahl": 21}], "zwischen 1 und 20")
        falsch([{"bezeichnung": "Tasche", "anzahl": 0}], "zwischen 1 und 20")
        falsch([{"bezeichnung": "Tasche", "austausch": "vielleicht"}], "Austausch")
        falsch([{"bezeichnung": f"Teil {n}"} for n in range(31)], "30 Positionen")
        falsch([{"produkt_id": ids["hms"], "einzeln": True, "anzahl": 20}, {"produkt_id": rolle, "einzeln": True,
                                                                            "anzahl": 20},
                {"produkt_id": ids["hms"], "einzeln": True, "anzahl": 11}], "50 einzeln")
        falsch([{"produkt_id": 999999, "einzeln": True}], "nicht gefunden", 404)
        falsch("keine Liste", "Liste")
        # DEMO-Bestandteil in einem echten Set: abgelehnt (der Export nennt Altfälle, test_format_2).
        with app.app_context():
            from app.material.services import katalog
            demo = katalog.produkt_anlegen({"category_id": ids["karabiner"], "manufacturer": "DEMO-Testwerk",
                                            "model": "DEMO Teil", "material_kind": "metall_hardware",
                                            "interval_months": 12}, demo=True)
        falsch([{"produkt_id": demo, "einzeln": True}], "DEMO-Produkt")
        # Unverändert: geaendert false, kein Journaleintrag.
        nochmal = [{"produkt_id": (b["produkt"] or {}).get("id"), "bezeichnung": b["bezeichnung"], "anzahl": b["anzahl"],
                    "einzeln": b["einzeln"], "austausch": b["austausch"]} for b in liste]
        r = ok(mv.put(url, json={"bestandteile": nochmal}))
        assert r["geaendert"] is False
        journal = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'product' AND entity_id = ? AND action = 'stueckliste'",
                         (set_p,))
        assert len(journal) == 1 and '"bezeichnung": "Tasche"' in journal[0]["after_json"], journal
        # Lesen: is_set in Listen, voll mit Stückliste, „Bestandteil von“, Grenzen; löschbar nur, wer nirgends Bestandteil ist.
        p = ok(k["fuehrung"].get(f"/api/material/produkte/{set_p}"))["produkt"]
        assert p["is_set"] and len(p["bestandteile"]) == 3 and "set_umschaltbar" not in p, p
        # sets_aelter nur für die Material-Verwaltung (S7).
        assert "sets_aelter" not in p and ok(mv.get(f"/api/material/produkte/{set_p}"))["produkt"]["sets_aelter"] == 0
        assert p["stueckliste_grenzen"] == {"positionen": 30, "anzahl": 20, "teile": 50, "bezeichnung": 120}
        h = ok(k["fuehrung"].get(f"/api/material/produkte/{ids['hms']}"))["produkt"]
        assert h["bestandteil_von"] == [{"id": set_p, "name": "Testwerk Testset Alpha"}] and h["loeschbar"] is False, h
        assert "sets_aelter" not in ok(mv.get(f"/api/material/produkte/{ids['hms']}"))["produkt"]
        assert {x["id"]: x["is_set"] for x in ok(mv.get("/api/material/produkte?q=Testwerk"))["produkte"]}[set_p] is True
        r = mv.delete(f"/api/material/produkte/{rolle}", headers=H)
        assert r.status_code == 409 and "Bestandteil von „Testwerk Testset Alpha“" in r.json["error"], r.get_json()
        # Umstellen Produkt ↔ Set nur über die Katalogdatei (Entscheidung S2): ein abweichendes is_set 409, gleiches 200.
        r = mv.put(f"/api/material/produkte/{rolle}", json={"is_set": True})
        assert r.status_code == 409 and "legt das Anlegen fest" in r.json["error"], r.get_json()
        r = mv.put(f"/api/material/produkte/{set_p}", json={"is_set": False})
        assert r.status_code == 409 and "Katalogdatei" in r.json["error"], r.get_json()
        assert ok(mv.put(f"/api/material/produkte/{set_p}", json={"is_set": True}))["produkt"]["is_set"]
        assert ok(mv.put(f"/api/material/produkte/{rolle}", json={"is_set": False}))["produkt"]["is_set"] is False
        # Variante folgt dem Vorbild: die eines Sets ist ein Set – ohne „bestandteile“ mit der Stückliste des Vorbilds
        # („stueckliste“ zählt nicht mehr) …
        r = ok(mv.post(f"/api/material/produkte/{set_p}/variante", json={
            "category_id": ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Alpha | Pro", "article_no": "TS-2",
            "material_kind": "textil", "lifetime_years": 10, "stueckliste": False}), 201)["produkt"]
        assert r["is_set"] and [(b["bezeichnung"], b["anzahl"]) for b in r["bestandteile"]] == [
            ("Verbindungselement", 2), ("Testwerk Rolle Gamma", 1), ("Tasche", 1)], r
        # … mit „bestandteile“ mit dieser Liste (Regeln wie beim Anlegen, S3) …
        r = mv.post(f"/api/material/produkte/{set_p}/variante", json={
            "category_id": ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Alpha | Ohne", "article_no": "TS-3",
            "material_kind": "textil", "lifetime_years": 10, "bestandteile": [{"bezeichnung": "Tasche"}]})
        assert r.status_code == 400 and "einzeln geführtes Teil" in r.json["error"], r.get_json()
        assert not zeilen(app, "SELECT 1 FROM mat_product WHERE article_no = 'TS-3'")
        variante = ok(mv.post(f"/api/material/produkte/{set_p}/variante", json={
            "category_id": ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Alpha | Ohne", "article_no": "TS-3",
            "material_kind": "textil", "lifetime_years": 10, "is_set": False,
            "bestandteile": [{"produkt_id": rolle, "einzeln": True, "anzahl": 2}]}), 201)["produkt"]
        assert variante["is_set"] and [(b["bezeichnung"], b["anzahl"]) for b in variante["bestandteile"]] == [
            ("Testwerk Rolle Gamma", 2)], variante
        # … die eines Produkts ein Produkt (eine Stückliste dazu 400).
        r = mv.post(f"/api/material/produkte/{ids['hms']}/variante", json={
            "category_id": ids["karabiner"], "manufacturer": "Testwerk", "model": "HMS Beta | X", "article_no": "HB-8",
            "material_kind": "metall_hardware", "interval_months": 12, "bestandteile": [{"produkt_id": rolle, "einzeln": True}]})
        assert r.status_code == 400 and "Variante eines Sets" in r.json["error"], r.get_json()
        assert not ok(mv.post(f"/api/material/produkte/{ids['hms']}/variante", json={
            "category_id": ids["karabiner"], "manufacturer": "Testwerk", "model": "HMS Beta | X", "article_no": "HB-8",
            "material_kind": "metall_hardware", "interval_months": 12, "is_set": True}), 201)["produkt"]["is_set"]
        # Mit Artikeln lässt sich nichts umstellen (409) – an einem einfachen Produkt nicht.
        gid, _ = gliederung(k["adm"])
        lager = ordner_neu(k["wart"], gid, "Lager")
        neuer_artikel(k["wart"], rolle, lager, serial_no="RG-ART-1")
        r = mv.put(f"/api/material/produkte/{rolle}", json={"is_set": True})
        assert r.status_code == 409 and "Artikel" in r.json["error"], r.get_json()
        # Die Stückliste eines Sets ersetzen: nie ohne einzeln geführtes Teil (S3), auch nicht leer.
        falsch([{"bezeichnung": "Tasche"}], "mindestens ein einzeln geführtes Teil")
        falsch([], "mindestens ein einzeln geführtes Teil")
        # Produkt löschen: ein Set ohne Artikel geht samt Stückliste (Journal nennt die Zahl).
        ok(mv.put(url, json={"bestandteile": [{"produkt_id": ids["hms"], "einzeln": True}]}))
        for v in zeilen(app, "SELECT id FROM mat_product WHERE article_no IN ('TS-2', 'TS-3')"):
            ok(mv.delete(f"/api/material/produkte/{v['id']}", headers=H))
        ok(mv.delete(f"/api/material/produkte/{set_p}", headers=H))
        assert not zeilen(app, "SELECT 1 FROM mat_product_component WHERE set_product_id = ?", (set_p,))
        assert '"bestandteile": 1' in zeilen(app, "SELECT before_json FROM mat_audit WHERE entity = 'product' "
                                                  "AND entity_id = ? AND action = 'geloescht'", (set_p,))[0]["before_json"]
    print("Stückliste im Katalog bestanden.")


def _importieren(app, daten, trocken=False):
    with app.app_context():
        from app.material.services import importer
        return importer.importieren(daten, trocken=trocken, quelle="Test")


def test_format_2():
    """Katalogdatei hin und zurück: Der Export schreibt „set“ und „bestandteile“ (Verweise mit uid); der Import in eine
    leere Instanz legt Set und Stückliste an – auch wenn das Set vor seinen Bestandteilen steht (zweiter Durchgang) –,
    ein zweiter Import ändert nichts. Fehler: Umschalten an einem Produkt mit Artikeln, unbekannter Bestandteil, „set“:
    false mit Bestandteilen, Bestandteile ohne Set; eine Textliste ist ein Hinweis; ein DEMO-Bestandteil in einem
    echten Set fehlt im Export samt „bestandteile“ und steht im Bericht."""
    with tempfile.TemporaryDirectory() as quelle, tempfile.TemporaryDirectory() as ziel:
        app, k = umgebung(quelle)
        ids = katalog_grund(k["adm"])
        set_p, rolle, _ = set_katalog(k["katalog"], ids)
        with app.app_context():
            from app.material.services import katalog_export
            daten, _, bericht = katalog_export.sammeln(mit_dateien=False)
        produkte = {p["modell"]: p for p in daten["produkte"]}
        s = produkte["Testset Alpha"]
        assert s["set"] is True and "set" not in produkte["HMS Beta"] and bericht["set_verstoesse"] == []
        assert [(b["bezeichnung"], b["anzahl"], b["einzeln"], b["austausch"], (b.get("produkt") or {}).get("modell"))
                for b in s["bestandteile"]] == [("Verbindungselement", 2, True, "nicht_belegt", "HMS Beta"),
                                                ("Testwerk Rolle Gamma", 1, True, "ja", "Rolle Gamma"),
                                                ("Tasche", 1, False, "nicht_belegt", None)]
        assert s["bestandteile"][0]["produkt"]["uid"] == produkte["HMS Beta"]["uid"]

        app2 = make_app(ziel)
        # Das Set vor seinen Bestandteilen – der zweite Durchgang löst die Verweise erst nach allen Produkten auf.
        daten["produkte"].sort(key=lambda p: p["modell"] != "Testset Alpha")
        b = _importieren(app2, daten)
        assert b["gespeichert"] and not b["fehler"] and b["stuecklisten"] == {"neu": 1, "geaendert": 0, "unveraendert": 0}, b
        p2 = zeilen(app2, "SELECT * FROM mat_product WHERE model = 'Testset Alpha'")[0]
        assert p2["is_set"] == 1 and p2["uid"] == s["uid"]
        assert [(z["bezeichnung"], z["anzahl"], z["einzeln"], z["austausch"], z["model"]) for z in zeilen(
            app2, "SELECT c.*, p.model FROM mat_product_component c LEFT JOIN mat_product p ON p.id = c.component_product_id "
                  "WHERE c.set_product_id = ? ORDER BY c.position", (p2["id"],))] == [
            ("Verbindungselement", 2, 1, "nicht_belegt", "HMS Beta"), ("Testwerk Rolle Gamma", 1, 1, "ja", "Rolle Gamma"),
            ("Tasche", 1, 0, "nicht_belegt", None)]
        assert any("Stückliste ersetzt (3 Positionen)" in z for z in b["aenderungen"]), b["aenderungen"]
        b = _importieren(app2, daten)
        assert b["gespeichert"] and b["stuecklisten"] == {"neu": 0, "geaendert": 0, "unveraendert": 1}, b
        # Ersetzen als Ganzes: eine Position weniger – ersetzt, mit Journal.
        kurz = dict(s, bestandteile=s["bestandteile"][:2])
        b = _importieren(app2, dict(daten, produkte=[p if p["modell"] != "Testset Alpha" else kurz for p in daten["produkte"]]))
        assert b["gespeichert"] and b["stuecklisten"]["geaendert"] == 1, b
        assert zeilen(app2, "SELECT COUNT(*) AS n FROM mat_product_component WHERE set_product_id = ?",
                      (p2["id"],))[0]["n"] == 2
        assert zeilen(app2, "SELECT user_name FROM mat_audit WHERE entity = 'product' AND entity_id = ? AND action = "
                            "'stueckliste' ORDER BY id DESC LIMIT 1", (p2["id"],))[0]["user_name"] == "Katalogimport (Test)"

        def fehler(produkte_neu, text):
            b = _importieren(app2, dict(daten, produkte=produkte_neu))
            assert not b["gespeichert"] and any(text in f for f in b["fehler"]), (text, b["fehler"])

        hms = produkte["HMS Beta"]
        fehler([dict(hms, set=True)], "Stückliste von")             # Bestandteil wird kein Set
        fehler([dict(s, set=False)], "nur ein Set hat Bestandteile")
        fehler([dict(hms, bestandteile=[{"bezeichnung": "Tasche"}])], "„set“: true fehlt")
        fehler([dict(s, bestandteile=[{"produkt": {"hersteller": "Nirgendwerk", "modell": "Phantom"}, "einzeln": True}])],
               "„Nirgendwerk | Phantom | –“ (Hersteller | Modell | Artikelnummer) gibt es weder im Katalog noch in der Datei")
        fehler([dict(s, bestandteile=[{"bezeichnung": "Tasche", "anzahl": 99}])], "zwischen 1 und 20")
        fehler([dict(s, bestandteile="Tasche")], "Liste")
        # Umschalten an einem Produkt mit Artikeln: Fehler dieses Produkts.
        with app2.app_context():
            from app import db
            from app.material.services import bestand
            with db.transaction():
                g = bestand.ordner_anlegen({"name": "OG Ziel", "kind": "gliederung"})
                rolle2 = db.query("SELECT id FROM mat_product WHERE model = 'Rolle Gamma'", one=True)["id"]
                bestand.artikel_anlegen({"product_id": rolle2, "folder_id": g, "serial_no": "RG-Z-1"})
        fehler([dict(s, bestandteile=[]), dict(produkte["Rolle Gamma"], set=True)], "schon 1 Artikel")
        # Textliste (Recherche-Manifest): Hinweis, übergangen.
        b = _importieren(app2, dict(daten, produkte=[dict(s, bestandteile=["Tasche", "Seilsatz"])]))
        assert b["gespeichert"] and any("Liste aus Texten" in h for h in b["hinweise"]), b
        # Die Vorlage für Sets (docs/material-katalog-set-vorlage.json) geht im Probelauf ohne Fehler durch – auch mit dem
        # Set vor seinem Bestandteil.
        import json
        with open(os.path.join(REPO, "docs", "material-katalog-set-vorlage.json"), encoding="utf-8") as fh:
            vorlage = json.load(fh)
        b = _importieren(app2, vorlage, trocken=True)
        assert not b["fehler"] and b["stuecklisten"]["neu"] == 1 and b["produkte"]["neu"] == 2, b
        # Probelauf schreibt nichts.
        b = _importieren(app2, dict(daten, produkte=[dict(s, bestandteile=[])]), trocken=True)
        assert not b["gespeichert"] and zeilen(app2, "SELECT COUNT(*) AS n FROM mat_product_component WHERE "
                                                      "set_product_id = ?", (p2["id"],))[0]["n"] == 2

        # DEMO-Bestandteil in einem echten Set (Altfall, an der Regel vorbei direkt eingetragen): kein „bestandteile“.
        with app.app_context():
            from app import db
            from app.material.services import katalog, katalog_export
            demo = katalog.produkt_anlegen({"category_id": ids["karabiner"], "manufacturer": "DEMO-Testwerk",
                                            "model": "DEMO Teil", "material_kind": "metall_hardware",
                                            "interval_months": 12}, demo=True)
            db.execute("INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                       "einzeln, position) VALUES (?, ?, 'DEMO Teil', 1, 1, 9)", (set_p, demo))
            daten, _, bericht = katalog_export.sammeln(mit_dateien=False)
            text = katalog_export.bericht_text(bericht)
        s = {p["modell"]: p for p in daten["produkte"]}["Testset Alpha"]
        assert s["set"] is True and "bestandteile" not in s, s
        assert len(bericht["set_verstoesse"]) == 1 and "DEMO Teil" in bericht["set_verstoesse"][0], bericht
        assert "DEMO-Bestandteil" in text
    print("Katalogdatei Format 2 mit Stücklisten bestanden.")


# --- Bestand ------------------------------------------------------------------------------------------------------------

def test_set_anlegen():
    """POST /artikel mit Set-Produkt: ohne „teile“ 400, falsche Zahl je Position 400, fremde Position 400, doppelte
    Seriennummern 400, Regeln des Teils mit Position im Text, ohne Stückliste 409, „teile“ an einem anderen Produkt 400.
    Sonst eine Transaktion: Set, Kopie der Stückliste, Teile (Produkt aus der Stückliste, Ordner des Sets, eigene
    Inventarnummer und QR), Journal „set_angelegt“ mit der Teileliste, Hinweis „STR-Nummer am Teil anbringen“. Eine
    fremde Dublette an einem Teil rollt alles zurück. Spätere Änderungen der Stückliste lassen das Set, wie es ist."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w = t.app, t.wart_a
        set_p, rolle, liste = set_katalog(t.k["katalog"], t.ids)
        basis = {"product_id": set_p, "folder_id": t.lager_a, "serial_no": "SET-N-1",
                 "manufactured_on": f"{_heute().year - 1}-03"}

        def falsch(d, text, code=400):
            vorher = zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"]
            r = w.post("/api/material/artikel", json=dict(basis, **d))
            assert r.status_code == code and text in r.json["error"], (d, r.status_code, r.get_json())
            assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"] == vorher
        falsch({}, "mit seinen Teilen")
        falsch({"teile": "x"}, "Liste")
        falsch({"teile": teile_fuer(liste)[:2]}, "genau 1 Teil")
        falsch({"teile": teile_fuer(liste) + teile_fuer(liste)[:1]}, "genau 2 Teile")
        tasche = next(b for b in liste if not b["einzeln"])
        falsch({"teile": teile_fuer(liste) + [{"bestandteil_id": tasche["id"]}]}, "nicht als einzeln geführter")
        falsch({"teile": teile_fuer(liste, ("DOPPELT-1", "doppelt-1"))}, "zweimal")
        falsch({"teile": [dict(x, serial_no="STR-000123") if n == 0 else x for n, x in enumerate(teile_fuer(liste))]},
               "Teil „Verbindungselement“ 1 von 2 (Seriennummer „STR-000123“): Seriennummern der Form")
        r = w.post("/api/material/artikel", json={"product_id": t.ids["hms"], "folder_id": t.lager_a, "teile": []})
        assert r.status_code == 400 and "nur beim Anlegen eines Sets" in r.json["error"], r.get_json()
        # Ein Set ohne Stückliste gibt es nur noch aus der Zeit vor „Set anlegen“ (Altbestand – direkt in SQLite).
        leer = ok(t.k["katalog"].post("/api/material/produkte", json={
            "category_id": t.ids["gurte"], "manufacturer": "Testwerk", "model": "Leerset", "article_no": "LS-1",
            "material_kind": "textil", "lifetime_years": 10}), 201)["produkt"]["id"]
        conn = roh(app)
        conn.execute("UPDATE mat_product SET is_set = 1 WHERE id = ?", (leer,))
        conn.commit()
        conn.close()
        falsch({"product_id": leer, "teile": []}, "keine Stückliste", 409)
        # Ein „product_id“ im Teil zählt nicht: Das Produkt kommt aus der Stückliste.
        teile = [dict(x, product_id=t.ids["gurt"]) for x in teile_fuer(liste, ("SET-N-K1", "", "SET-N-R1"))]
        r = ok(w.post("/api/material/artikel", json=dict(basis, teile=teile)), 201)
        a = r["artikel"]
        assert a["ist_set"] and a["teil_von"] is None and a["set"]["teile_anzahl"] == 3, a["set"]
        assert len(r["hinweise"]) == 1 and r["hinweise"][0].startswith("STR-Nummer am Teil anbringen"), r["hinweise"]
        teile = zeilen(app, "SELECT * FROM mat_item WHERE parent_item_id = ? ORDER BY id", (a["id"],))
        assert [x["product_id"] for x in teile] == [t.ids["hms"], t.ids["hms"], rolle]
        assert {x["folder_id"] for x in teile} == {t.lager_a} and len({x["qr_token"] for x in teile}) == 3
        assert [x["inventory_no"] for x in teile] == sorted(x["inventory_no"] for x in teile) > [a["inventory_no"]]
        assert teile[1]["serial_generated"] == 1 and teile[1]["serial_no"].startswith("STR-")
        assert [(b["bezeichnung"], b.get("vorhanden"), b.get("fehlt")) for b in a["set"]["bestandteile"]] == [
            ("Verbindungselement", 2, 0), ("Testwerk Rolle Gamma", 1, 0), ("Tasche", None, None)]
        assert a["set"]["vollstaendig"] is True and a["set"]["fehlend"] == []
        assert [x["bestandteil"] for x in a["set"]["teile"]] == ["Verbindungselement", "Verbindungselement",
                                                                 "Testwerk Rolle Gamma"]
        assert a["set"]["status"] == "neu" and a["set"]["eigen"]["status"] == "neu"
        j = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? ORDER BY id", (a["id"],))
        assert [x["action"] for x in j] == ["angelegt", "set_angelegt"], j
        assert '"bestandteil": "Verbindungselement"' in j[1]["after_json"] and '"Tasche"' in j[1]["after_json"]
        tj = zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'angelegt'",
                    (teile[0]["id"],))[0]["after_json"]
        assert f'"set": {a["id"]}' in tj and f'"set_inventar": "{a["inventory_no"]}"' in tj, tj
        # Am Teil: „teil_von“, kein Set-Block; ein ungeprüftes Teil lässt sich einzeln löschen (K2 – sperrt das Set).
        x = ok(w.get(f"/api/material/artikel/{teile[0]['id']}"))["artikel"]
        assert x["set"] is None and not x["ist_set"] and x["darf_loeschen"] is True
        assert x["teil_von"] == {"id": a["id"], "inventory_no": a["inventory_no"], "produkt": "Testwerk Testset Alpha",
                                 "status": "neu", "status_text": "neu", "bestandteil": "Verbindungselement",
                                 "teile_anzahl": 3, "austausch": "nicht_belegt"}, x["teil_von"]
        assert a["darf_loeschen"] is True
        # Kopie der Stückliste: eine spätere Änderung färbt das Set nicht um (erst „Stückliste übertragen“).
        r = ok(t.k["katalog"].put(f"/api/material/produkte/{set_p}/bestandteile", json={"bestandteile": [
            {"produkt_id": rolle, "einzeln": True}, {"bezeichnung": "Tasche"}]}))
        assert r["produkt"]["sets_aelter"] == 1, r["produkt"]["sets_aelter"]
        a2 = ok(w.get(f"/api/material/artikel/{a['id']}"))["artikel"]
        assert len(a2["set"]["bestandteile"]) == 3 and a2["set"]["vollstaendig"]
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_item_set_slot WHERE set_item_id = ?", (a["id"],))[0]["n"] == 3
        ok(t.k["katalog"].put(f"/api/material/produkte/{set_p}/bestandteile", json={"bestandteile": [
            {"produkt_id": t.ids["hms"], "bezeichnung": "Verbindungselement", "anzahl": 2, "einzeln": True},
            {"produkt_id": rolle, "anzahl": 1, "einzeln": True, "austausch": "ja"},
            {"bezeichnung": "Tasche", "anzahl": 1, "einzeln": False}]}))
        liste = ok(t.k["katalog"].get(f"/api/material/produkte/{set_p}"))["produkt"]["bestandteile"]
        # Vorschlag für den Dialog: die Stückliste mit Produktangaben.
        v = ok(w.get(f"/api/material/artikel/vorschlag?product_id={set_p}&folder_id={t.lager_a}"))["vorschlag"]
        assert [b["anzahl"] for b in v["set"]["bestandteile"]] == [2, 1, 1] and v["set"]["teil_felder"] == [
            "serial_no", "manufactured_on", "purchased_on", "first_use_on", "length_m"], v["set"]
        assert ok(w.get(f"/api/material/artikel/vorschlag?product_id={t.ids['hms']}"))["vorschlag"]["set"] is None
        # Fremde Dublette an einem Teil (Seriennummer gibt es in B): alles zurück, protokolliert ohne Merkmale aus B.
        vorher = zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"]
        r = w.post("/api/material/artikel", json=dict(basis, serial_no="SET-N-3",
                                                      teile=teile_fuer(liste, ("SET-N3-K1", "TEST-B-0001", "SET-N3-R1"))))
        assert r.status_code == 409 and "Bereich, den du nicht siehst" in r.json["error"], r.get_json()
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"] == vorher
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_global_search WHERE art = 'dublette'")[0]["n"] == 1
        # Set löschen: nur ganz und ungeprüft – Teile und Kopie gehen mit, Journal je Teil.
        ok(w.delete(f"/api/material/artikel/{a['id']}", headers=H))
        assert not zeilen(app, "SELECT 1 FROM mat_item WHERE id = ? OR parent_item_id = ?", (a["id"], a["id"]))
        assert not zeilen(app, "SELECT 1 FROM mat_item_set_slot WHERE set_item_id = ?", (a["id"],))
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'item' AND action = 'geloescht' AND "
                           "after_json LIKE '%mit dem Set gelöscht%'")[0]["n"] == 3
        assert stimmig(app)
    print("Set anlegen bestanden.")


def test_set_rang():
    """SET_RANG folgt der Rangfolge von status.status(): Für jedes Paar von Zuständen hat ein Artikel, der beide Bedingungen
    erfüllt, den Status, der in SET_RANG weiter vorn steht (Kritik S29, A18)."""
    from datetime import date, timedelta
    from app.material.services import status as st
    h = date(2026, 10, 23)
    bedingung = {
        "ausgesondert": {"lock_state": "ausgesondert"}, "gesperrt": {"lock_state": "gesperrt"},
        "lebensdauer": {"retire_by": h.isoformat()}, "neu": {"last_inspected_on": None},
        "ueberfaellig": {"next_due_on": (h - timedelta(days=1)).isoformat()},
        "bald_faellig": {"next_due_on": (h + timedelta(days=5)).isoformat()}, "einsatzbereit": {}}
    basis = {"lock_state": "frei", "retire_by": None, "last_inspected_on": "2026-01-01",
             "next_due_on": (h + timedelta(days=200)).isoformat()}
    assert set(st.SET_RANG) == set(st.STATUS)
    for a in st.SET_RANG:
        assert st.status(dict(basis, **bedingung[a]), h, 30) == a, a
        for b in st.SET_RANG:
            if a == b or set(bedingung[a]) & set(bedingung[b]):
                continue                          # dieselbe Spalte – nicht beides zugleich
            beide = {**basis, **bedingung[a], **bedingung[b]}
            erwartet = st.schlechtester([a, b])
            assert st.status(beide, h, 30) == erwartet, (a, b, st.status(beide, h, 30))
    print("Rangfolge des Set-Status bestanden.")


def test_listen_und_status():
    """Ordnerliste, Fällige und Suche zeigen die Set-Zeile mit Set-Status, Set-Fälligkeit und „set“ (Teile nicht
    einzeln); Filter und Sortierung nach den Set-Werten; Kopf „davon m Sets mit k Teilen“; Seiten zählen die Set-Zeile
    einmal. Der Set-Status aus SQL (gruppen_status_sql) gleicht dem aus Python (sets.werte) in jeder Lage; die Suche
    findet ein Teil mit „teil_von“. Zählungen im Baum bleiben je Artikel."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, s = t.app, t.wart_a, t.s["id"]
        h = _heute()
        k1, k2, r1 = t.teile
        # Set-Artikel geprüft, Teile noch nicht: Set „neu“, eigen „einsatzbereit“.
        zustand(app, s, last_inspected_on=h.isoformat(), next_due_on=(h.replace(year=h.year + 1)).isoformat())
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}"))["ordner"]
        ids = [x["id"] for x in o["artikel"]]
        assert s in ids and not set(t.teile) & set(ids) and o["artikel_gesamt"] == len(ids) == 3, ids   # art_a, S, F
        z = next(x for x in o["artikel"] if x["id"] == s)
        assert z["status"] == "neu" and z["set"]["eigen"]["status"] == "einsatzbereit" and z["set"]["teile"] == 3, z
        assert o["sets"] == {"anzahl": 1, "teile": 3}
        assert s in [x["id"] for x in ok(w.get(f"/api/material/ordner/{t.lager_a}?status=neu"))["ordner"]["artikel"]]
        assert s not in [x["id"] for x in ok(w.get(f"/api/material/ordner/{t.lager_a}?status=einsatzbereit"))["ordner"]["artikel"]]
        seite = ok(w.get(f"/api/material/ordner/{t.lager_a}?pro_seite=1&seite=2&sort=inventar"))["ordner"]
        assert seite["artikel_gesamt"] == 3 and len(seite["artikel"]) == 1
        # Baum zählt je Artikel (Teile zählen mit, Entwurf F).
        lager = next(x for x in ok(w.get("/api/material/ordner"))["ordner"] if x["id"] == t.lager_a)
        assert lager["bestand"] == 6, lager
        # Alle geprüft; ein Teil überfällig: Set überfällig mit dem Teil als Auslöser.
        for iid in t.teile:
            zustand(app, iid, last_inspected_on=h.isoformat(), next_due_on=(h.replace(year=h.year + 1)).isoformat())
        zustand(app, k2, next_due_on=(h.replace(year=h.year - 1)).isoformat())
        f = ok(w.get("/api/material/faellig"))
        zeile = next(x for x in f["artikel"] if x["id"] == s)
        assert zeile["status"] == "ueberfaellig" and zeile["next_due_on"] == h.replace(year=h.year - 1).isoformat()
        assert zeile["set"]["faellig_durch"]["id"] == k2 and not set(t.teile) & {x["id"] for x in f["artikel"]}
        assert f["sets"] == {"anzahl": 1, "teile": 3}, f["sets"]
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert a["set"]["status"] == "ueberfaellig" and a["set"]["faellig_durch"] == {
            "id": k2, "inventory_no": a["set"]["teile"][1]["inventory_no"], "set_artikel": False}
        assert a["status"] == "einsatzbereit"              # der Set-Artikel selbst; die Set-Werte stehen in „set“
        # Sortierung nach Status über die Set-Werte: das überfällige Set vor dem einsatzbereiten Artikel.
        zustand(app, t.f["id"], last_inspected_on=h.isoformat(), next_due_on=(h.replace(year=h.year + 1)).isoformat())
        reihe = [x["id"] for x in ok(w.get(f"/api/material/ordner/{t.lager_a}?sort=status"))["ordner"]["artikel"]]
        assert reihe.index(s) < reihe.index(t.f["id"]), reihe
        # Lebensende am Set-Artikel (textil) bestimmt das Set-Lebensende.
        assert a["set"]["retire_by"] == a["retire_by"] and a["set"]["lebensende_durch"]["set_artikel"] is True
        # Suche: das Teil mit „teil_von“, das Set als Set-Zeile.
        s_t = ok(w.get("/api/material/suche?q=SET-A-K1"))["treffer"]
        assert [x["id"] for x in s_t] == [k1] and s_t[0]["teil_von"]["id"] == s, s_t
        s_s = ok(w.get("/api/material/suche?q=SET-A-1"))["treffer"]
        assert s_s[0]["id"] == s and s_s[0]["set"]["teile"] == 3 and s_s[0]["status"] == "ueberfaellig"
        # SQL gegen Python in vielen Lagen.
        lagen = [dict(), dict(lock_state="gesperrt"), dict(retire_by=h.isoformat()), dict(last_inspected_on=None),
                 dict(next_due_on=(h.replace(year=h.year - 1)).isoformat())]
        for x in lagen:
            for wer in (s, k1):
                alt = zeilen(app, "SELECT lock_state, retire_by, last_inspected_on, next_due_on FROM mat_item WHERE id = ?",
                             (wer,))[0]
                sql(app, f"UPDATE mat_item SET {', '.join(f'{c} = ?' for c in x) or 'id = id'} WHERE id = ?",
                    (*x.values(), wer))
                with app.test_request_context():
                    from flask import g
                    from app import db
                    from app.material.services import sets
                    from app.material.services import status as st
                    g.user = db.query("SELECT * FROM users WHERE id = ?", (t.k["wart_id"],), one=True)
                    sz = db.query("SELECT * FROM mat_item WHERE id = ?", (s,), one=True)
                    py = sets.werte(sz, sets.teile(s))["status"]
                    sq = db.query(f"SELECT {sets.gruppen_status_sql('i')} AS s FROM mat_item i WHERE i.id = :id",
                                  dict(st.parameter(), id=s), one=True)["s"]
                    assert py == sq, (x, wer, py, sq)
                sql(app, "UPDATE mat_item SET lock_state = ?, retire_by = ?, last_inspected_on = ?, next_due_on = ? "
                         "WHERE id = ?", (alt["lock_state"], alt["retire_by"], alt["last_inspected_on"], alt["next_due_on"],
                                          wer))
        assert stimmig(app)
    print("Listen und Set-Status bestanden.")


def test_routen_tabelle():
    """Route × {Set-Artikel, Teil, freier Artikel} mit dem erwarteten Status (Weichen im Dienst, S9). Set verschieben und
    zuordnen nehmen die Teile mit (Journal je Teil mit dem Set); Sperren und Mangelmeldung gehen an Set-Artikel und Teil
    (Sperr-Kaskade, K2 – auch an einem schon mitgesperrten Teil); Aussondern am Teil nur über „Teil entnehmen“, am Set
    nicht nach einer ungeprüften Meldung. Nach jeder Anfrage liegen alle Sets stimmig."""
    from app.material.services import mangel
    alt = mails_abfangen(mangel, lambda an, betreff, inhalt: True)
    try:
        with ohne_post(), tempfile.TemporaryDirectory() as tmp:
            t = set_aufbau(tmp)
            app, w, p = t.app, t.wart_a, t.k["pruefer"]
            s, f = t.s["id"], t.f["id"]
            k1 = t.teile[0]
            fach = ordner_neu(w, t.lager_a, "Fach Musterstadt")
            person = t.k["fuehrung_id"]
            faelle = [
                ("verschieben", lambda x: w.post("/api/material/artikel/verschieben", json={"ids": [x], "folder_id": fach}),
                 200, 409, 200),
                ("zuordnung", lambda x: w.put(f"/api/material/artikel/{x}/zuordnung", json={"user_id": person}),
                 200, 409, 200),
                ("sammelzuordnung", lambda x: w.post("/api/material/artikel/zuordnen", json={"ids": [x], "user_id": None}),
                 200, 409, 200),
                ("produktwechsel", lambda x: w.put(f"/api/material/artikel/{x}", json={"product_id": t.rolle}),
                 409, 409, 200),
                # Am Set ist es dasselbe Produkt – nichts ändert sich (200); Teil und freier Artikel: 409 (A7b).
                ("zu Set-Produkt", lambda x: w.put(f"/api/material/artikel/{x}", json={"product_id": t.set_p}),
                 200, 409, 409),
                # K2: Das Set sperrt ganz; das Teil ist danach mitgesperrt und nimmt trotzdem eine eigene Sperre an.
                ("sperren", lambda x: p.post(f"/api/material/artikel/{x}/sperren", json={"grund": "sturz"}),
                 200, 200, 200),
                ("mangel", lambda x: w.post(f"/api/material/artikel/{x}/mangel", json={"beschreibung": "Testmangel"}),
                 201, 201, 201),
                # Der freie Artikel ist hier vom Prüfer gesperrt (Zeile „sperren“) – der Materialwart sondert aus. Am Set
                # steht seit eben eine ungeprüfte Meldung (409), am Teil geht es nur über „Teil entnehmen“.
                ("aussondern", lambda x: w.post(f"/api/material/artikel/{x}/aussondern", json={"grund": "irreparabel"}),
                 409, 409, 200),
            ]
            for name, anfrage, soll_set, soll_teil, soll_frei in faelle:
                for wer, soll in ((s, soll_set), (k1, soll_teil), (f, soll_frei)):
                    r = anfrage(wer)
                    assert r.status_code == soll, (name, wer, r.status_code, r.get_json())
                    if wer == k1 and soll == 409:
                        assert "Teil des Sets" in r.json["error"], (name, r.get_json())
                    assert stimmig(app), name
                    if name == "verschieben" and soll == 200:
                        ziel = zeilen(app, "SELECT folder_id FROM mat_item WHERE id = ? OR parent_item_id = ?", (wer, wer))
                        assert {x["folder_id"] for x in ziel} == {fach}, ziel
                        ok(w.post("/api/material/artikel/verschieben", json={"ids": [wer], "folder_id": t.lager_a}))
                    if name == "zuordnung" and wer == s:
                        assert {x["assigned_user_id"] for x in zeilen(
                            app, "SELECT assigned_user_id FROM mat_item WHERE id = ? OR parent_item_id = ?", (s, s))} == {person}
            # Journal am Teil: verschoben und zugeordnet mit dem Set.
            j = zeilen(app, "SELECT action, after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? ORDER BY id",
                       (k1,))
            assert [x["action"] for x in j][:5] == ["angelegt", "verschoben", "verschoben", "zugeordnet",
                                                    "zuordnung_geloest"], j
            assert all(f'"set": {s}' in x["after_json"] for x in j[1:5]), j
            # K2: mit dem Set gesperrt (System), dann eigene Sperre und Meldung am Teil.
            assert [x["action"] for x in j][5:] == ["set_gesperrt", "gesperrt", "mangel_gemeldet"], j
            # Prüfung am Teil im gesperrten Set: einsatzbereit nimmt nur den eigenen Grund, instandsetzen setzt ihn.
            pr = ok(starten(p, k1), 201)["pruefung"]
            assert festschreiben(p, pr["id"], ergebnis="einsatzbereit",
                                 maengel_gesehen=[m["id"] for m in pr["maengel"]]).status_code == 200
            assert zeilen(app, "SELECT lock_state, lock_cause FROM mat_item WHERE id = ?", (k1,)) == [
                {"lock_state": "gesperrt", "lock_cause": "set"}]
            pid = ok(starten(p, t.teile[1]), 201)["pruefung"]["id"]
            assert festschreiben(p, pid, ergebnis="instandsetzen", grund="Testgrund").status_code == 200
            assert zeilen(app, "SELECT lock_cause FROM mat_item WHERE id = ?", (t.teile[1],))[0]["lock_cause"] == "eigen"
            assert stimmig(app)
            # Löschen: ein geprüftes Teil 409 wie jeder geprüfte Artikel, Set mit einer Prüfung an einem Teil 409.
            r = w.delete(f"/api/material/artikel/{k1}", headers=H)
            assert r.status_code == 409 and "Prüfungen" in r.json["error"], r.get_json()
            r = w.delete(f"/api/material/artikel/{s}", headers=H)
            assert r.status_code == 409 and "aussondern statt löschen" in r.json["error"], r.get_json()
            # Kontrolle: Aussondern und Löschen freier Artikel gehen wie bisher.
            frei2 = neuer_artikel(w, t.ids["hms"], t.lager_a, serial_no="FREI-A-9")["id"]
            ok(p.post(f"/api/material/artikel/{frei2}/sperren", json={"grund": "sturz"}))
            assert w.post(f"/api/material/artikel/{frei2}/aussondern", json={"grund": "irreparabel"}).status_code == 200
            weg = neuer_artikel(w, t.ids["hms"], t.lager_a)["id"]
            assert w.delete(f"/api/material/artikel/{weg}", headers=H).status_code == 200
            assert stimmig(app)
    finally:
        mails_zurueck(alt)
    print("Routentabelle Set/Teil/frei bestanden.")


def test_stimmig_teil_vor_set():
    """set_stimmig, wenn ein Teil die kleinere Kennung hat als sein Set (eingesetzter Altartikel – Kennungen werden
    wiedervergeben; S1 mit Probe P-D): Ordner über eine Gliederungsgrenze verschieben (_systemordner_nachziehen, einzeln
    nach Kennung), Artikel verschieben, Ordner löschen (Herkunft der Ausgesonderten → NULL über den Fremdschlüssel) und
    Konto löschen (Zuordnung in einer Anweisung) gehen durch und lassen die Sets stimmig. Eine Abweichung rollt eine
    Set-Transaktion zurück (500) und steht beim Start im Log."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, adm = t.app, t.wart_a, t.adm

        def mit_altteil(ordner, serie):
            """Ein Set, dessen eines Teil ein vorher angelegter Artikel ist (kleinere Kennung) – direkt eingesetzt, wie es
            eine spätere Lieferung („vorhandenen Artikel einsetzen“) tut."""
            alt = neuer_artikel(w, t.ids["hms"], ordner, serial_no=serie + "-ALT")["id"]
            neu = set_neu(w, t.set_p, ordner, t.liste, serie, (serie + "-K1", serie + "-K2", serie + "-R1"))["artikel"]
            sql(app, "UPDATE mat_item SET parent_item_id = ? WHERE id = ?", (neu["id"], alt))
            assert alt < neu["id"]
            return neu["id"], alt

        # 1. Gesperrtes Set (direkt gesetzt – die Kaskade kommt mit K2) mit Altteil; Lager über die Gliederungsgrenze.
        halle = ordner_neu(w, t.a, "Halle Musterstadt")
        s1, alt1 = mit_altteil(halle, "SET-P1")
        sql(app, "UPDATE mat_item SET lock_state = 'gesperrt', origin_folder_id = ?, folder_id = ? "
                 "WHERE id = ? OR parent_item_id = ?", (halle, t.sys_a["gesperrt"], s1, s1))
        assert stimmig(app)
        ok(adm.post(f"/api/material/ordner/{halle}/verschieben", json={"parent_id": t.b}))
        lage = zeilen(app, "SELECT DISTINCT folder_id, origin_folder_id FROM mat_item WHERE id = ? OR parent_item_id = ?",
                      (s1, s1))
        assert lage == [{"folder_id": t.sys_b["gesperrt"], "origin_folder_id": halle}], lage
        assert stimmig(app)
        # 2. Artikel verschieben: freies Set mit Altteil.
        s2, alt2 = mit_altteil(t.lager_a, "SET-P2")
        fach = ordner_neu(w, t.lager_a, "Fach P2")
        ok(w.post("/api/material/artikel/verschieben", json={"ids": [s2], "folder_id": fach}))
        assert {x["folder_id"] for x in zeilen(app, "SELECT folder_id FROM mat_item WHERE id = ? OR parent_item_id = ?",
                                               (s2, s2))} == {fach}
        assert stimmig(app)
        # 3. Ordner löschen: ausgesondertes Set mit Altteil, Herkunft im gelöschten Ordner.
        weg = ordner_neu(w, t.a, "Weg Musterstadt")
        s3, alt3 = mit_altteil(weg, "SET-P3")
        sql(app, "UPDATE mat_item SET lock_state = 'ausgesondert', origin_folder_id = ?, folder_id = ? "
                 "WHERE id = ? OR parent_item_id = ?", (weg, t.sys_a["ausgesondert"], s3, s3))
        ok(w.delete(f"/api/material/ordner/{weg}", headers=H))
        assert {x["origin_folder_id"] for x in zeilen(
            app, "SELECT origin_folder_id FROM mat_item WHERE id = ? OR parent_item_id = ?", (s3, s3))} == {None}
        assert stimmig(app)
        # 4. Konto löschen: Set mit Altteil der Person zugeordnet.
        _, person = neues_konto(app, "person_p4@example.org", name="Person P4")
        s4, alt4 = mit_altteil(t.lager_a, "SET-P4")
        sql(app, "UPDATE mat_item SET assigned_user_id = ? WHERE id = ? OR parent_item_id = ?", (person, s4, s4))
        assert stimmig(app)
        assert adm.delete(f"/api/admin/users/{person}", headers=H).status_code == 200
        assert {x["assigned_user_id"] for x in zeilen(
            app, "SELECT assigned_user_id FROM mat_item WHERE id = ? OR parent_item_id = ?", (s4, s4))} == {None}
        assert stimmig(app)
        # 5. Abweichung (direkt gesetzt): die nächste Set-Transaktion rollt zurück, der Start meldet das Set im Log.
        sql(app, "UPDATE mat_item SET folder_id = ? WHERE id = ?", (fach, alt4))
        assert not stimmig(app)
        r = w.put(f"/api/material/artikel/{s4}/zuordnung", json={"user_id": t.k["fuehrung_id"]})
        assert r.status_code == 500 and "nicht mehr gleich" in r.json["error"], r.get_json()
        assert zeilen(app, "SELECT assigned_user_id FROM mat_item WHERE id = ?", (s4,))[0]["assigned_user_id"] is None
        puffer = io.StringIO()
        handler = logging.StreamHandler(puffer)
        logger = logging.getLogger("app.material.services.sets")
        logger.addHandler(handler)
        try:
            make_app(tmp)
        finally:
            logger.removeHandler(handler)
        assert "Sets nicht stimmig" in puffer.getvalue() and str(s4) in puffer.getvalue(), puffer.getvalue()
    print("set_stimmig mit Teil vor Set bestanden.")


def test_trennung():
    """Fremde Sets und Teile antworten wie Unbekanntes (404) – lesen, verschieben, zuordnen, Sammelzuordnung –, die Suche
    findet sie nicht, „teil_von“ und der Set-Block nennen nichts Fremdes; der Steckbrief eines fremden Teils sagt nur
    „teil_eines_sets“. Eine Position einer fremden Stückliste beim Anlegen ist 400 (keine Bestandsangabe)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w = t.wart_a
        unbekannt = w.get("/api/material/artikel/999999")
        for x in [t.sb["id"]] + t.teile_b:
            r = w.get(f"/api/material/artikel/{x}")
            assert r.status_code == 404 and r.get_json() == unbekannt.get_json()
            r = w.post("/api/material/artikel/verschieben", json={"ids": [x], "folder_id": t.lager_a})
            assert r.status_code == 404, r.get_json()
            assert w.put(f"/api/material/artikel/{x}/zuordnung", json={"user_id": None}).status_code == 404
            assert w.post("/api/material/artikel/zuordnen", json={"ids": [x], "user_id": None}).status_code == 404
        assert ok(w.get("/api/material/suche?q=SET-B-K1"))["gesamt"] == 0
        assert ok(w.get("/api/material/suche?q=SET-B-1"))["gesamt"] == 0
        text = w.get(f"/api/material/artikel/{t.s['id']}").get_data(as_text=True) + \
            w.get(f"/api/material/ordner/{t.lager_a}").get_data(as_text=True)
        assert "SET-B-" not in text and "Nachbarstadt" not in text
        # Steckbrief (globale Suche) eines fremden Teils: nur das Kennzeichen.
        r = ok(w.post("/api/material/globalsuche", json={"q": "SET-B-K1", "bestaetigt": True}))
        assert len(r["treffer"]) == 1 and r["treffer"][0]["teil_eines_sets"] is True, r
        r = ok(w.post("/api/material/globalsuche", json={"q": "SET-B-1", "bestaetigt": True}))
        assert r["treffer"][0]["teil_eines_sets"] is False and "SET-B-K1" not in str(r)
        # Wart B sieht sein Set mit Teilen.
        b = ok(t.wart_b.get(f"/api/material/artikel/{t.sb['id']}"))["artikel"]
        assert [x["id"] for x in b["set"]["teile"]] == t.teile_b
    print("Trennung je Gliederung bei Sets bestanden.")


def test_meine_psa_und_import():
    """Meine PSA: ein zugeordnetes Set ist eine Karte mit Set-Status und den Teilen als Karten (gleiche Schlüssel,
    „teil_eines_sets“), die Zahl zählt je Set; Bestandsimport: eine Zeile mit Set-Produkt geht in die Nacharbeit, die
    Produktwahl der Nacharbeit nimmt kein Set-Produkt."""
    from test_material_meine_psa import KARTE
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w = t.app, t.wart_a
        person, person_id = neues_konto(app, "psa_set@example.org", name="PSA Set", stufe=0)
        ok(w.put(f"/api/material/artikel/{t.s['id']}/zuordnung", json={"user_id": person_id}))
        ok(w.put(f"/api/material/artikel/{t.f['id']}/zuordnung", json={"user_id": person_id}))
        r = ok(person.get("/api/material/meine-psa"))
        assert r["gesamt"] == 2 and len(r["artikel"]) == 2, r
        karte = next(k for k in r["artikel"] if k["id"] == t.s["id"])
        assert set(karte) == KARTE and karte["teil_eines_sets"] is False and len(karte["teile"]) == 3
        assert all(set(x) == KARTE and x["teil_eines_sets"] is True and x["teile"] == [] for x in karte["teile"])
        assert next(k for k in r["artikel"] if k["id"] == t.f["id"])["teile"] == []
        with app.test_request_context():
            from app import db
            from app.material.services import psa
            u = db.query("SELECT * FROM users WHERE id = ?", (person_id,), one=True)
            assert psa.anzahl(person_id) == 2 and psa.kurz(u)["anzahl"] == 2
        # Zugeordnete eines Ordners: das Set zählt einmal.
        z = ok(w.get(f"/api/material/ordner/{t.a}/zugeordnete"))["zugeordnete"]
        assert [x["anzahl"] for x in z if x["id"] == person_id] == [2], z
        # Bestandsimport: Set-Produkt → Nacharbeit mit Grund, Produktwahl abgelehnt.
        daten = csv_bytes([["Hersteller", "Modell", "Artikelnummer", "Seriennummer", "Herstellung"],
                           ["Testwerk", "Testset Alpha", "TS-1", "SET-IMP-1", f"{_heute().year - 1}-01"]])
        b = ok(probelauf(w, t.lager_a, daten))
        zeile = nach_nr(b)[2]
        assert zeile["status"] == "nacharbeit" and any("Sets legt der Import nicht an" in g["text"] for g in zeile["gruende"]), zeile
        r = ok(w.post(f"/api/material/ordner/{t.lager_a}/import", headers=H, content_type="multipart/form-data",
                      data={"file": (io.BytesIO(daten), "liste.csv")}), 201)
        zeile_id = zeilen(app, "SELECT id FROM mat_import_row WHERE status = 'offen'")[0]["id"]
        assert r["import"]["angelegt"] == 0
        r = w.post(f"/api/material/ordner/{t.lager_a}/nacharbeit/produkt", json={"zeilen": [zeile_id],
                                                                                "product_id": t.set_p})
        assert r.status_code == 400 and "Sets legt der Import nicht an" in r.json["error"], r.get_json()
    print("Meine PSA und Bestandsimport bei Sets bestanden.")


def test_demo_set():
    """scripts/material_demo.py --demo legt ein DEMO-Set-Produkt mit Stückliste aus DEMO-Bestandteilen und einen
    DEMO-Set-Artikel mit seinen Teilen an – alles DEMO; ein zweiter Lauf legt nichts dazu."""
    def laufen():
        spec = importlib.util.spec_from_file_location("material_demo_sets", os.path.join(REPO, "scripts", "material_demo.py"))
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        alt, sys.argv = sys.argv, ["material_demo.py", "--demo"]
        puffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(puffer):
                modul.main()
        finally:
            sys.argv = alt
        return puffer.getvalue()
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        aus = laufen()
        assert "DEMO-Set mit 2 Teilen" in aus, aus
        app = make_app(tmp)
        p = zeilen(app, "SELECT * FROM mat_product WHERE model = 'DEMO Verbindungsmittel-Set'")[0]
        assert p["is_set"] == 1 and p["demo"] == 1
        komp = zeilen(app, "SELECT c.*, p.demo FROM mat_product_component c LEFT JOIN mat_product p "
                           "ON p.id = c.component_product_id WHERE c.set_product_id = ? ORDER BY c.position", (p["id"],))
        assert [(c["anzahl"], c["einzeln"], c["demo"]) for c in komp] == [(2, 1, 1), (1, 0, None)]
        s = zeilen(app, "SELECT * FROM mat_item WHERE product_id = ?", (p["id"],))
        assert len(s) == 1 and s[0]["serial_no"] == "DEMO-SET-1"
        teile = zeilen(app, "SELECT serial_no FROM mat_item WHERE parent_item_id = ? ORDER BY id", (s[0]["id"],))
        assert [x["serial_no"] for x in teile] == ["DEMO-SET-K1", "DEMO-SET-K2"]
        with app.app_context():
            from app.material.services import bestand
            assert bestand.ist_demo(s[0]["id"])
        vorher = zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"]
        assert "DEMO-Set ist schon da" in laufen()
        assert zeilen(make_app(tmp), "SELECT COUNT(*) AS n FROM mat_item")[0]["n"] == vorher
    print("DEMO-Set bestanden.")


if __name__ == "__main__":
    test_migration_21()
    test_trigger_21()
    test_katalog_stueckliste()
    test_format_2()
    test_set_anlegen()
    test_set_rang()
    test_listen_und_status()
    test_routen_tabelle()
    test_stimmig_teil_vor_set()
    test_trennung()
    test_meine_psa_und_import()
    test_demo_set()
