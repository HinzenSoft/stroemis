"""Bestandteil-Liste an normalen Produkten und Seriennummern der Bestandteile (Schritt 25, Wunsch vom 25.10.2026):
python tests/test_material_bestandteile.py  oder  pytest tests/test_material_bestandteile.py

  - Schema-Schritt 25: frisch, 24 → Ende mit Altbestand (auch Änderungsanträge), zweiter Lauf; Trigger der Liste (nur
    Text, seit Schritt 26 in dessen Fassung) und der Seriennummern der Bestandteile.
  - Katalog: Produkt mit Liste anlegen (in einem Zug, atomar), ersetzen und leeren, Fehler je Position, Journal,
    Variante, Löschen, Rechte.
  - Prüfung: Zeilen „… vorhanden“ in Einzelprüfung und Durchgang, „fehlt“ ist ein Mangel (Foto und Bemerkung), offener
    Entwurf behält seine Zeilen, Berichtigung kopiert, Protokoll-PDF.
  - Seriennummern der Bestandteile: beim Anlegen und bis zur ersten Prüfung direkt, danach in der Prüfung (alt → neu im
    Protokoll) oder per Änderungsantrag; Suche; Meine PSA; Lebenslauf; Liste ändern behält Nummern unveränderter
    Positionen.
  - Katalogdatei: Format-Beispiel, Bericht „bestandteillisten“, zweiter Lauf, Fehler, Export → Import, Vorlage.
Alle Namen, Nummern und Listen hier sind Platzhalter."""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, abschluss, festschreiben, gliederung, jpeg, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, pruef_formulare, punkte_von, starten, umgebung)
from test_material_antrag import ablehnen, beantragen, bestaetigen, journal, post  # noqa: E402
from test_material_set_rueckbau import _importieren, _schema, abgewiesen, roh  # noqa: E402
from test_material_trennung import bis_schritt, endversion, zeilen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTE = [{"bezeichnung": "Platzhalter Bestandteil A", "anzahl": 2}, {"bezeichnung": "Platzhalter Tasche", "anzahl": 1}]


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.get_json())
    return r.json


class T:
    pass


def aufbau(tmp):
    """Konten, Katalog (katalog_grund mit Formularen) und ein Produkt „Lieferumfang Alpha“ (Metall, Kategorie Karabiner –
    dort gilt das generische Formular) mit Bestandteil-Liste LISTE; Gliederung mit Lager, darin ein Artikel davon."""
    t = T()
    t.app, t.k = umgebung(tmp)
    t.ids = katalog_grund(t.k["adm"])
    pruef_formulare(t.k["katalog"], t.ids)
    t.w, t.p, t.mv, t.f, t.adm = t.k["wart"], t.k["pruefer"], t.k["katalog"], t.k["fuehrung"], t.k["adm"]
    t.produkt = ok(t.mv.post("/api/material/produkte", json={
        "category_id": t.ids["karabiner"], "manufacturer": "Testwerk", "model": "Lieferumfang Alpha", "article_no": "LA-1",
        "material_kind": "metall_hardware", "interval_months": 12, "bestandteile": LISTE}), 201)["produkt"]
    t.pid = t.produkt["id"]
    t.gid, t.system = gliederung(t.w)
    t.lager = ok(t.w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": t.gid}),
                 201)["ordner"]["id"]
    t.pos = {z["bezeichnung"]: z["id"] for z in t.produkt["bestandteile"]}
    return t


def nummern(t, **werte):
    """bestandteil_nummern aus {"A1": …, "A2": …, "T": …} (A: Bestandteil A, Stück 1/2; T: Tasche)."""
    a, tasche = t.pos["Platzhalter Bestandteil A"], t.pos["Platzhalter Tasche"]
    ziel = {"A1": (a, 1), "A2": (a, 2), "T": (tasche, 1)}
    return [{"bestandteil_id": ziel[k][0], "stueck": ziel[k][1], "seriennummer": v} for k, v in werte.items()]


def pruefung_von(c, iid):
    r = starten(c, iid)
    assert r.status_code in (200, 201), r.get_json()
    return r.json["pruefung"]


def zeile(pr, text):
    return next(x for x in pr["punkte"] if x["text"] == text)


# --- Schema-Schritt 25 --------------------------------------------------------------------------------------------------

def test_migration_25():
    """Frisch: Tabelle, Spalten, Trigger. 24 → Ende an einer Datenbank mit Bestand (Artikel, Prüfung,
    Änderungsanträge): keine Zeile ändert sich, die Kennungen und der AUTOINCREMENT-Stand der Anträge bleiben, das Schema
    gleicht dem frischen; zweiter Lauf und Schritt 25 für sich ändern nichts."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("table", "mat_item_component_serial") in schema_frisch
    for name in ("mat_component_neu", "mat_component_aendern", "mat_result_bestandteil", "mat_teilnummer_position",
                 "mat_teilnummer_neu", "mat_teilnummer_aendern", "mat_teilnummer_loeschen", "mat_teilnummer_antrag_neu"):
        assert ("trigger", name) in schema_frisch, name
    assert "'component_serial'" in schema_frisch[("table", "mat_item_change")]
    assert "COALESCE(component_id, 0)" in schema_frisch[("index", "ux_mat_item_change_offen")]
    # Schritt 23 bleibt, wie er ausgeliefert wurde.
    assert "'component_serial'" not in models.ANTRAG_TABELLE_23 and "component_id" not in models.ANTRAG_TABELLE_23

    with tempfile.TemporaryDirectory() as tmp, post():
        def bestand(tmp):
            from test_material_antrag import aufbau as antrag_aufbau
            t = antrag_aufbau(tmp)
            kid = ok(beantragen(t.w, t.k1, serial_no="AN-101"), 201)["antrag"]["id"]
            return t, kid
        t, kid = bis_schritt(24)(bestand, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "24"
        # bis_schritt hat Tabelle und Spalten aus Schritt 25 vorab angelegt (die Dienste lesen sie) – für den echten
        # Stand 24 wieder weg.
        conn.execute("DROP TABLE mat_item_component_serial")
        for spalte in ("component_serials", "component_id"):
            conn.execute(f"ALTER TABLE mat_inspection_result DROP COLUMN {spalte}")
        conn.commit()
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_item_component_serial'").fetchone()
        tabellen = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat_%' "
                                               "AND name NOT LIKE '%fts%' AND name <> 'mat_meta' ORDER BY name")]
        # Die Kopie der Stückliste je Set entfällt mit Schritt 26 (hier leer).
        vorher = {n: conn.execute(f"SELECT * FROM {n} ORDER BY rowid").fetchall() for n in tabellen
                  if n != "mat_item_set_slot"}
        seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'mat_item_change'").fetchone()[0]
        conn.close()
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        conn = roh(app)
        try:
            for n, alt in vorher.items():
                breite = len(alt[0]) if alt else 0
                assert [r[:breite] for r in conn.execute(f"SELECT * FROM {n} ORDER BY rowid").fetchall()] == alt, n
            assert conn.execute("SELECT component_id, stueck, component_label FROM mat_item_change").fetchall() == \
                [(None, None, "")] * len(vorher["mat_item_change"])
            assert conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'mat_item_change'").fetchone()[0] == seq
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            assert _schema(pfad) == schema_frisch, {k: (_schema(pfad).get(k), schema_frisch.get(k))
                                                    for k in set(_schema(pfad)) | set(schema_frisch)
                                                    if _schema(pfad).get(k) != schema_frisch.get(k)}
            assert models.migrieren(conn) == models.SCHEMA_VERSION
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_25(conn)
            assert conn.total_changes == n
            conn.rollback()
            assert _schema(pfad) == schema_frisch
        finally:
            conn.close()
        # Der offene Antrag aus Stand 24 lässt sich weiter bestätigen.
        ok(bestaetigen(t.w, kid))
        assert zeilen(app, "SELECT serial_no FROM mat_item WHERE id = ?", (t.k1,))[0]["serial_no"] == "AN-101"
    print("Migration 24 → 25 bestanden.")


def test_trigger_25():
    """Direkt in SQLite: Text-Position erlaubt, einzeln geführt nicht (Fassung von Schritt 26). Seriennummern
    nur an einer Position des Produkts des Artikels; nach der ersten Prüfung nur gedeckt (Antrag oder offene Prüfung),
    ein bestätigter Antrag wirkt einmal; mit der Position, nach einem Produktwechsel und beim Kürzen der Anzahl gehen
    sie; INSERT OR REPLACE über die Kennung nie."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        art = neuer_artikel(t.w, t.pid, t.lager, serial_no="BT-T-1")
        a = t.pos["Platzhalter Bestandteil A"]
        conn = roh(t.app)
        try:
            conn.execute("INSERT INTO mat_product_component (set_product_id, bezeichnung, anzahl) VALUES (?, 'Zusatz', 1)",
                         (t.ids["gurt"],))
            conn.rollback()
            abgewiesen(conn, "INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                             "einzeln) VALUES (?, ?, 'X', 1, 1)", (t.pid, t.ids["hms"]), "ist nur Text")
            abgewiesen(conn, "UPDATE mat_product_component SET einzeln = 1, component_product_id = ? WHERE id = ?",
                       (t.ids["hms"], a), "ist nur Text")
            ts = "2026-10-25T08:00:00+00:00"
            ein = "INSERT INTO mat_item_component_serial (item_id, component_id, stueck, serial_no, updated_at) VALUES (?,?,?,?,?)"
            abgewiesen(conn, ein, (art["id"], a, 3, "X", ts), "gehört zu einem Stück")          # Stück über der Anzahl
            andere = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="BT-T-2")
            abgewiesen(conn, ein, (andere["id"], a, 1, "X", ts), "gehört zu einem Stück")       # fremdes Produkt
            conn.execute(ein, (art["id"], a, 1, "VOR-1", ts))                                   # ungeprüft: direkt
            conn.execute(ein, (art["id"], a, 2, "VOR-2", ts))
            conn.commit()
        finally:
            conn.close()
        pr = pruefung_von(t.p, art["id"])
        ok(abschluss(t.p, pr["id"], ergebnis="einsatzbereit"))
        conn = roh(t.app)
        try:
            abgewiesen(conn, "UPDATE mat_item_component_serial SET serial_no = 'NEU' WHERE item_id = ?", (art["id"],),
                       "seit der ersten Prüfung fest")
            abgewiesen(conn, "DELETE FROM mat_item_component_serial WHERE item_id = ?", (art["id"],),
                       "seit der ersten Prüfung fest")
            abgewiesen(conn, ein, (art["id"], t.pos["Platzhalter Tasche"], 1, "NEU-T", ts), "seit der ersten Prüfung fest")
            sid = conn.execute("SELECT id FROM mat_item_component_serial WHERE item_id = ? AND stueck = 1",
                               (art["id"],)).fetchone()[0]
            abgewiesen(conn, "INSERT OR REPLACE INTO mat_item_component_serial (id, item_id, component_id, stueck, serial_no, "
                             "updated_at) VALUES (?,?,?,?,?,?)", (sid, art["id"], a, 1, "VOR-1", ts))
            abgewiesen(conn, "UPDATE mat_item_component_serial SET stueck = 2 WHERE id = ?", (sid,))
            # Ein bestätigter Antrag deckt genau seine Änderung – einmal (abgewiesen rollt zurück: jeweils committen).
            kid = conn.execute("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by_name, "
                               "created_at, component_id, stueck, component_label) VALUES (?, 'component_serial', 'VOR-1', "
                               "'NACH-1', 'Platzhalter', 'wart', ?, ?, 1, 'A')", (art["id"], ts, a)).lastrowid
            conn.commit()
            abgewiesen(conn, "UPDATE mat_item_component_serial SET serial_no = 'NACH-1' WHERE id = ?", (sid,))
            conn.execute("UPDATE mat_item_change SET status = 'bestaetigt', resolved_by_name = 'wart', resolved_at = ? "
                         "WHERE id = ?", (ts, kid))
            conn.commit()
            abgewiesen(conn, "UPDATE mat_item_component_serial SET serial_no = 'ANDERS' WHERE id = ?", (sid,))
            conn.execute("UPDATE mat_item_component_serial SET serial_no = 'NACH-1' WHERE id = ?", (sid,))
            assert conn.execute("SELECT applied_at FROM mat_item_change WHERE id = ?", (kid,)).fetchone()[0]
            conn.commit()
            abgewiesen(conn, "UPDATE mat_item_component_serial SET serial_no = 'VOR-1' WHERE id = ?", (sid,))
            # Mit der Position geht die Nummer (ON DELETE CASCADE).
            conn.execute("DELETE FROM mat_product_component WHERE id = ?", (a,))
            assert not conn.execute("SELECT 1 FROM mat_item_component_serial WHERE item_id = ?", (art["id"],)).fetchone()
            conn.rollback()
            # Gekürzte Anzahl: das Stück darüber gilt nicht mehr und darf weg.
            conn.execute("UPDATE mat_product_component SET anzahl = 1 WHERE id = ?", (a,))
            conn.execute("DELETE FROM mat_item_component_serial WHERE item_id = ? AND stueck = 2", (art["id"],))
            abgewiesen(conn, "DELETE FROM mat_item_component_serial WHERE item_id = ? AND stueck = 1", (art["id"],),
                       "seit der ersten Prüfung fest")
            assert conn.execute("SELECT COUNT(*) FROM mat_item_component_serial WHERE item_id = ?",
                                (art["id"],)).fetchone()[0] == 2
        finally:
            conn.close()
    print("Trigger 25 bestanden.")


# --- Katalog ------------------------------------------------------------------------------------------------------------

def test_katalog_liste():
    """Anlegen mit Liste in einem Zug; Fehler je Position (kein Produkt entsteht); ersetzen, leeren, Journal nur bei
    Änderung; Variante übernimmt bzw. ersetzt; Produktseite lesen alle mit Modulzugang; pflegen nur die
    Material-Verwaltung; Löschen nimmt die Liste mit."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        p = t.produkt
        assert "is_set" not in p and [(z["bezeichnung"], z["anzahl"]) for z in p["bestandteile"]] == \
            [("Platzhalter Bestandteil A", 2), ("Platzhalter Tasche", 1)]
        neu = {"category_id": t.ids["karabiner"], "manufacturer": "Testwerk", "material_kind": "metall_hardware",
               "interval_months": 12}
        vor = zeilen(t.app, "SELECT COUNT(*) AS n FROM mat_product")[0]["n"]
        for liste, text in (([{"bezeichnung": "X", "einzeln": True}], "Bestandteil-Liste ist nur Text"),
                            ([{"bezeichnung": "X", "produkt_id": t.ids["hms"]}], "Bestandteil-Liste ist nur Text"),
                            ([{"bezeichnung": "X", "austausch": "ja"}], "Bestandteil-Liste ist nur Text"),
                            ([{"bezeichnung": " "}], "Bitte eine Bezeichnung angeben."),
                            ([{"bezeichnung": "X"}, {"bezeichnung": " x "}], "„x“ steht schon in Position 1"),
                            ([{"bezeichnung": "X", "anzahl": 21}], "Anzahl"),
                            ([{"bezeichnung": "X", "anzahl": 0}], "Anzahl"),
                            ([{"bezeichnung": f"X{n}"} for n in range(31)], "Höchstens 30 Positionen"),
                            ("Tasche", "muss eine Liste sein")):
            r = t.mv.post("/api/material/produkte", json=dict(neu, model="Fehlt", article_no="F-1", bestandteile=liste))
            assert r.status_code == 400 and text in r.json["error"], (liste, r.get_json())
        assert zeilen(t.app, "SELECT COUNT(*) AS n FROM mat_product")[0]["n"] == vor
        r = t.mv.post("/api/material/produkte", json=dict(neu, model="Fehlt", article_no="F-1",
                                                          bestandteile=[{"bezeichnung": "X"}, {"bezeichnung": "Y",
                                                                                               "einzeln": True}]))
        assert r.json["error"].startswith("Position 2: "), r.get_json()
        # Ersetzen, gleich, leeren – Journal „bestandteile“ nur bei einer Änderung.
        url = f"/api/material/produkte/{t.pid}/bestandteile"
        assert ok(t.mv.put(url, json={"bestandteile": LISTE}))["geaendert"] is False
        neu_liste = [{"bezeichnung": "Platzhalter Tasche", "anzahl": 1}, {"bezeichnung": "Platzhalter Bestandteil A",
                                                                         "anzahl": 3}]
        r = ok(t.mv.put(url, json={"bestandteile": neu_liste}))
        assert r["geaendert"] is True and [z["bezeichnung"] for z in r["produkt"]["bestandteile"]] == \
            ["Platzhalter Tasche", "Platzhalter Bestandteil A"]
        # Gleiche Bezeichnung = dieselbe Position (an ihr hängen die Seriennummern der Artikel).
        assert {z["bezeichnung"]: z["id"] for z in r["produkt"]["bestandteile"]} == t.pos
        j = zeilen(t.app, "SELECT * FROM mat_audit WHERE entity = 'product' AND entity_id = ? AND action = 'bestandteile' "
                          "ORDER BY id", (t.pid,))
        assert len(j) == 2, j                                 # Anlegen und diese Änderung
        assert json.loads(j[-1]["after_json"])["bestandteile"][1] == {"bezeichnung": "Platzhalter Bestandteil A",
                                                                      "anzahl": 3}
        assert ok(t.mv.put(url, json={"bestandteile": []}))["produkt"]["bestandteile"] == []
        ok(t.mv.put(url, json={"bestandteile": LISTE}))
        # Rechte: pflegen nur die Material-Verwaltung, lesen jeder mit Modulzugang.
        for c in (t.w, t.p, t.f):
            assert c.put(url, json={"bestandteile": []}).status_code == 403
            assert c.post("/api/material/produkte", json=dict(neu, model="Z", article_no="Z-1",
                                                              bestandteile=LISTE)).status_code == 403
            assert len(ok(c.get(f"/api/material/produkte/{t.pid}"))["produkt"]["bestandteile"]) == 2
        assert t.k["nutzer"].get(f"/api/material/produkte/{t.pid}").status_code in (403, 404)
        # Variante: ohne „bestandteile“ die Liste des Vorbilds, mit – die bearbeitete.
        v1 = ok(t.mv.post(f"/api/material/produkte/{t.pid}/variante", json=dict(p, article_no="LA-2")), 201)["produkt"]
        assert "is_set" not in v1 and [z["bezeichnung"] for z in v1["bestandteile"]] == [x["bezeichnung"] for x in LISTE]
        v2 = ok(t.mv.post(f"/api/material/produkte/{t.pid}/variante",
                          json=dict(p, article_no="LA-3", bestandteile=[{"bezeichnung": "Nur eins"}])), 201)["produkt"]
        assert [z["bezeichnung"] for z in v2["bestandteile"]] == ["Nur eins"]
        v3 = ok(t.mv.post(f"/api/material/produkte/{t.pid}/variante", json=dict(p, article_no="LA-4", bestandteile=[])),
                201)["produkt"]
        assert v3["bestandteile"] == []
        # Löschen nimmt die Liste mit.
        ok(t.mv.delete(f"/api/material/produkte/{v1['id']}", headers=H))
        assert not zeilen(t.app, "SELECT 1 FROM mat_product_component WHERE set_product_id = ?", (v1["id"],))
        # „is_set“ (Set-Funktion bis Schritt 26) wird übergangen: ein Produkt mit Liste.
        r = ok(t.mv.post("/api/material/produkte", json=dict(neu, model="S", article_no="S-1", is_set=True,
                                                             bestandteile=[{"bezeichnung": "Tasche"}])), 201)
        assert "is_set" not in r["produkt"] and len(r["produkt"]["bestandteile"]) == 1
    print("Katalog Bestandteil-Liste bestanden.")


# --- Prüfung ------------------------------------------------------------------------------------------------------------

def test_pruefung_zeilen():
    """Je Position eine Ja/Nein-Zeile „… vorhanden“ hinter den Formularpunkten, „(2×)“ bei mehr als einem Stück;
    „nein“ ist ein Mangel mit Foto und Bemerkung (F1 a, nicht kritisch – „einsatzbereit“ bleibt wählbar); eine Liste,
    die sich während des Entwurfs ändert, ändert ihn nicht; Durchgang ebenso; Berichtigung kopiert; Protokoll-PDF."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        art = neuer_artikel(t.w, t.pid, t.lager, serial_no="BT-P-1")
        pr = pruefung_von(t.p, art["id"])
        texte = [(x["gruppe"], x["text"], x["bestandteil"]) for x in pr["punkte"]]
        assert texte[-2:] == [("Bestandteile", "Platzhalter Bestandteil A (2×) vorhanden", True),
                              ("Bestandteile", "Platzhalter Tasche vorhanden", True)], texte
        assert not any(b for _, _, b in texte[:-2])
        a = zeile(pr, "Platzhalter Bestandteil A (2×) vorhanden")
        assert (a["art"], a["soll"], a["wert"], a["befund"], a["pflicht"], a["kritisch"]) == \
            ("yesno", "ja", "ja", "ok", True, False)
        assert [n["stueck"] for n in a["nummern"]] == [1, 2]
        # Liste ändern: der offene Entwurf behält seine Zeilen.
        ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile", json={"bestandteile": LISTE + [{"bezeichnung": "Neu"}]}))
        assert len(pruefung_von(t.p, art["id"])["punkte"]) == len(pr["punkte"])
        url = f"/api/material/pruefungen/{pr['id']}/punkte/{a['id']}"
        assert ok(t.p.put(url, json={"wert": "nein"}))["punkt"]["befund"] == "mangel"
        r = abschluss(t.p, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Foto" in r.json["error"], r.get_json()
        ok(t.p.post(f"{url}/foto", headers=H, data={"file": (jpeg(), "a.jpg")}, content_type="multipart/form-data"))
        r = abschluss(t.p, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Bemerkung" in r.json["error"], r.get_json()
        ok(t.p.put(url, json={"notiz": "Platzhalter: ein Stück fehlt"}))
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        # Protokoll-PDF: Gruppe „Bestandteile“ mit der Zeile.
        from test_material import pdf_seiten
        x = zeilen(t.app, "SELECT pdf_path FROM mat_inspection WHERE id = ?", (pr["id"],))[0]
        text = " ".join(" ".join(pdf_seiten(os.path.join(tmp, x["pdf_path"]))).split())
        assert "Bestandteile" in text and "Platzhalter Bestandteil A (2×) vorhanden" in text, text[-800:]
        # Die nächste Prüfung hat die neue Liste.
        pr2 = pruefung_von(t.p, art["id"])
        assert [x["text"] for x in pr2["punkte"] if x["bestandteil"]][-1] == "Neu vorhanden"
        ok(t.p.delete(f"/api/material/pruefungen/{pr2['id']}", headers=H))
        # Berichtigung kopiert die Zeilen samt Position.
        b = ok(t.p.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter"}), 201)
        bp = ok(t.p.get(f"/api/material/pruefungen/{b['pruefung']['id']}"))["pruefung"]
        assert [x["text"] for x in bp["punkte"] if x["bestandteil"]] == [x["text"] for x in pr["punkte"] if x["bestandteil"]]
        # Durchgang: dieselben Zeilen.
        art2 = neuer_artikel(t.w, t.pid, t.lager, serial_no="BT-P-2")
        d = ok(t.w.post("/api/material/durchgaenge", json={"folder_id": t.lager, "titel": "Platzhalter-Durchgang"}), 201)
        pr3 = ok(starten(t.p, art2["id"], durchgang_id=d["durchgang"]["id"]), 201)["pruefung"]
        assert [x["text"] for x in pr3["punkte"] if x["bestandteil"]] == \
            ["Platzhalter Bestandteil A (2×) vorhanden", "Platzhalter Tasche vorhanden", "Neu vorhanden"]
        # Ein Artikel ohne Liste hat keine solche Zeile.
        hms = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="BT-P-3")
        assert not any(x["bestandteil"] for x in pruefung_von(t.p, hms["id"])["punkte"])
    print("Prüfzeilen bestanden.")


# --- Seriennummern der Bestandteile --------------------------------------------------------------------------------------

def test_seriennummern():
    """Beim Anlegen und bis zur ersten Prüfung direkt (Materialwart; Prüfer 403), danach 409; in der Prüfung trägt der
    Prüfer sie ein (übernommen beim Festschreiben, Protokoll alt → neu, Journal); per Antrag; Suche; Meine PSA;
    Lebenslauf; Liste ändern behält die Nummern unveränderter Positionen."""
    with tempfile.TemporaryDirectory() as tmp, post():
        t = aufbau(tmp)
        r = t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "BT-S-1",
                                                     "bestandteil_nummern": nummern(t, A1="TN-A1", T="")})
        a = ok(r, 201)["artikel"]
        assert [z["nummern"] for z in a["bestandteile"]] == [["TN-A1", ""], [""]]
        assert a["bestandteile_direkt"] is True and a["produkt"]["bestandteile"] == LISTE
        angelegt = journal(t.app, a["id"], "angelegt")[0]["nachher"]
        assert angelegt["bestandteil_nummern"] == [{"bestandteil": "Platzhalter Bestandteil A (Stück 1 von 2)",
                                                    "seriennummer": "TN-A1"}]
        # Fehler: fremde Position, Stück über der Anzahl, zu lang.
        for falsch, text in ((nummern(t, A1="X")[:0] + [{"bestandteil_id": 999999, "stueck": 1, "seriennummer": "X"}],
                              "nicht in der Bestandteil-Liste"),
                             ([{"bestandteil_id": t.pos["Platzhalter Tasche"], "stueck": 2, "seriennummer": "X"}], "Stück"),
                             (nummern(t, T="X" * 81), "zu lang")):
            r = t.w.put(f"/api/material/artikel/{a['id']}", json={"bestandteil_nummern": falsch})
            assert r.status_code == 400 and text in r.json["error"], r.get_json()
        # Bearbeiten vor der ersten Prüfung: Materialwart ja, Prüfer nein.
        assert t.p.put(f"/api/material/artikel/{a['id']}", json={"bestandteil_nummern": nummern(t, T="TN-T")}
                       ).status_code == 403
        a = ok(t.w.put(f"/api/material/artikel/{a['id']}", json={"bestandteil_nummern": nummern(t, A2="TN-A2", T="TN-T")}))[
            "artikel"]
        assert [z["nummern"] for z in a["bestandteile"]] == [["TN-A1", "TN-A2"], ["TN-T"]]
        assert journal(t.app, a["id"], "bestandteil_nummern")[-1]["nachher"]["bestandteil_nummern"][-1] == \
            {"bestandteil": "Platzhalter Tasche", "seriennummer": "TN-T"}
        # Suche über die Nummer eines Bestandteils.
        treffer = ok(t.w.get("/api/material/suche?q=TN-A2"))
        assert [x["id"] for x in treffer["treffer"]] == [a["id"]] and treffer["exakt_lokal"] is True, treffer
        assert [x["id"] for x in ok(t.w.get("/api/material/suche?q=n-a"))["treffer"]] == [a["id"]]
        # Prüfung: der Prüfer trägt eine neue Nummer ein und entfernt eine.
        pr = pruefung_von(t.p, a["id"])
        za = zeile(pr, "Platzhalter Bestandteil A (2×) vorhanden")
        assert [(n["alt"], n["neu"], n["wert"]) for n in za["nummern"]] == [("TN-A1", None, "TN-A1"),
                                                                            ("TN-A2", None, "TN-A2")]
        url = f"/api/material/pruefungen/{pr['id']}/punkte/{za['id']}"
        assert t.p.put(url, json={"seriennummern": ["nur eins"]}).status_code == 400
        x = ok(t.p.put(url, json={"seriennummern": ["TN-A1", "TN-A2-NEU"]}))["punkt"]
        assert [n["neu"] for n in x["nummern"]] == [None, "TN-A2-NEU"]
        zt = zeile(pr, "Platzhalter Tasche vorhanden")
        ok(t.p.put(f"/api/material/pruefungen/{pr['id']}/punkte/{zt['id']}", json={"seriennummern": [""]}))
        # Fremde Prüfzeile ohne Bestandteil nimmt keine Nummern.
        frei = next(x for x in pr["punkte"] if not x["bestandteil"])
        assert t.p.put(f"/api/material/pruefungen/{pr['id']}/punkte/{frei['id']}",
                       json={"seriennummern": ["X"]}).status_code == 400
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        a = ok(t.w.get(f"/api/material/artikel/{a['id']}"))["artikel"]
        assert [z["nummern"] for z in a["bestandteile"]] == [["TN-A1", "TN-A2-NEU"], [""]]
        assert a["bestandteile_direkt"] is False
        j = journal(t.app, a["id"], "bestandteil_nummern")[-1]
        assert j["nachher"]["pruefung"] == pr["id"] and j["vorher"]["bestandteil_nummern"] == [
            {"bestandteil": "Platzhalter Bestandteil A (Stück 2 von 2)", "seriennummer": "TN-A2"},
            {"bestandteil": "Platzhalter Tasche", "seriennummer": "TN-T"}], j
        from test_material import pdf_seiten
        x = zeilen(t.app, "SELECT pdf_path FROM mat_inspection WHERE id = ?", (pr["id"],))[0]
        text = " ".join(" ".join(pdf_seiten(os.path.join(tmp, x["pdf_path"]))).split())
        # pdftotext zieht ein am Bindestrich umbrochenes „TN-A2“ zu „TNA2“ zusammen – deshalb ohne Bindestriche verglichen.
        flach = text.replace("-", "")
        assert "Stück 2: Seriennummer TNA2 → TNA2NEU" in flach and "Seriennummer TNT → –" in flach, text[:2500]
        assert "Stück 1: Seriennummer TNA1" in flach
        # Danach direkt nicht mehr – 409; per Antrag ja.
        r = t.w.put(f"/api/material/artikel/{a['id']}", json={"bestandteil_nummern": nummern(t, T="TN-T2")})
        assert r.status_code == 409 and "Seit der ersten Prüfung" in r.json["error"], r.get_json()
        r = beantragen(t.w, a["id"], bestandteil_nummern=nummern(t, A1="TN-A1-B", T="TN-T2"))
        kid = ok(r, 201)["antrag"]["id"]
        x = ok(t.w.get(f"/api/material/artikel/{a['id']}"))["artikel"]["antraege"][0]
        assert [(y["feld_text"], y["alt_text"], y["neu_text"]) for y in x["aenderungen"]] == [
            ("Seriennummer Bestandteil „Platzhalter Bestandteil A (Stück 1 von 2)“", "TN-A1", "TN-A1-B"),
            ("Seriennummer Bestandteil „Platzhalter Tasche“", "(leer)", "TN-T2")], x
        ok(bestaetigen(t.w, kid))
        a = ok(t.w.get(f"/api/material/artikel/{a['id']}"))["artikel"]
        assert [z["nummern"] for z in a["bestandteile"]] == [["TN-A1-B", "TN-A2-NEU"], ["TN-T2"]]
        assert all(r["applied_at"] for r in zeilen(t.app, "SELECT applied_at FROM mat_item_change WHERE item_id = ?",
                                                   (a["id"],)))
        assert journal(t.app, a["id"], "antrag_bestaetigt")[-1]["nachher"]["bestandteil_nummern"][1] == \
            {"bestandteil": "Platzhalter Tasche", "seriennummer": "TN-T2"}
        # Meine PSA und Lebenslauf.
        ok(t.w.put(f"/api/material/artikel/{a['id']}/zuordnung", json={"user_id": t.k["fuehrung_id"]}))
        psa = ok(t.f.get("/api/material/meine-psa"))
        karte = next(k for k in psa["artikel"] if k["id"] == a["id"])
        assert [(b["bezeichnung"], b["anzahl"], b["nummern"]) for b in karte["bestandteile"]] == \
            [("Platzhalter Bestandteil A", 2, ["TN-A1-B", "TN-A2-NEU"]), ("Platzhalter Tasche", 1, ["TN-T2"])]
        with t.app.test_request_context():
            from flask import g
            from app import db
            from app.material.services import lebenslauf
            g.user = db.query("SELECT * FROM users WHERE id = ?", (t.k["wart_id"],), one=True)
            d = lebenslauf.daten(a["id"])
        assert d["bestandteile"] == [{"text": "2 × Platzhalter Bestandteil A",
                                      "nummern": "Stück 1: TN-A1-B, Stück 2: TN-A2-NEU"},
                                     {"text": "1 × Platzhalter Tasche", "nummern": "TN-T2"}], d["bestandteile"]
        # Liste ändern: Tasche fällt weg, Anzahl A sinkt auf 1 – Nummer von A1 bleibt, die anderen gehen ins Journal.
        ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile",
                    json={"bestandteile": [{"bezeichnung": "Platzhalter Bestandteil A", "anzahl": 1},
                                           {"bezeichnung": "Neu", "anzahl": 1}]}))
        a = ok(t.w.get(f"/api/material/artikel/{a['id']}"))["artikel"]
        assert [(z["bezeichnung"], z["nummern"]) for z in a["bestandteile"]] == [("Platzhalter Bestandteil A", ["TN-A1-B"]),
                                                                               ("Neu", [""])]
        j = journal(t.app, a["id"], "bestandteil_nummern")[-1]
        assert j["nachher"]["grund"] == "Bestandteil-Liste des Produkts geändert" and \
            {x["seriennummer"] for x in j["vorher"]["bestandteil_nummern"]} == {"TN-A2-NEU", "TN-T2"}, j
    print("Seriennummern der Bestandteile bestanden.")


# --- Katalogdatei ----------------------------------------------------------------------------------------------------------

def _datei(produkte):
    return {"format": "stroemis-material-katalog", "version": 2, "demo": False, "quelle": "Platzhalter",
            "kategorien": [{"name": "Platzhalter Kategorie", "materialart": "metall_hardware", "intervall_monate": 12}],
            "produkte": produkte}


def _p(**kw):
    return dict({"kategorie": ["Platzhalter Kategorie"], "hersteller": "Platzhalterwerk", "modell": "Lieferumfang Beta",
                 "artikelnummer": "LB-1", "materialart": "metall_hardware", "beschreibung": ""}, **kw)


def test_katalogdatei():
    """Format-Beispiel im Probelauf ohne Fehler, echter Lauf neu, zweiter Lauf unverändert, Änderung „geändert“;
    Fehlertexte; Liste aus Texten ist ein Hinweis; [] entfernt; Export → Import rund; die DEMO-Vorlage geht durch."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app = t.app
        mit_liste = _p(set=False, bestandteile=LISTE)
        b = _importieren(app, _datei([mit_liste]), trocken=True)
        assert not b["fehler"] and b["bestandteillisten"]["neu"] == 1, b
        b = _importieren(app, _datei([mit_liste]))
        assert not b["fehler"] and b["gespeichert"] and b["bestandteillisten"] == {"neu": 1, "geaendert": 0,
                                                                                    "unveraendert": 0}, b
        pid = zeilen(app, "SELECT id FROM mat_product WHERE model = 'Lieferumfang Beta'")[0]["id"]
        assert [(z["bezeichnung"], z["anzahl"], z["einzeln"]) for z in zeilen(
            app, "SELECT * FROM mat_product_component WHERE set_product_id = ? ORDER BY position", (pid,))] == \
            [("Platzhalter Bestandteil A", 2, 0), ("Platzhalter Tasche", 1, 0)]
        b = _importieren(app, _datei([mit_liste]))
        assert b["bestandteillisten"] == {"neu": 0, "geaendert": 0, "unveraendert": 1} and \
            b["produkte"]["unveraendert"] == 1, b
        # Ohne „set“ ebenso; nur die Liste ändert sich → das Produkt zählt als geändert.
        b = _importieren(app, _datei([_p(bestandteile=LISTE[:1])]))
        assert b["bestandteillisten"]["geaendert"] == 1 and b["produkte"]["geaendert"] == 1, b
        assert any("Bestandteil-Liste ersetzt (1 Position)" in x for x in b["aenderungen"]), b["aenderungen"]
        # Fehler je Position.
        for liste, text in (([{"bezeichnung": "X", "einzeln": True}], "Position 1: Eine Bestandteil-Liste ist nur Text"),
                            ([{"bezeichnung": "X", "produkt": {"hersteller": "Testwerk", "modell": "HMS Beta",
                                                               "artikelnummer": "HB-7"}}], "Bestandteil-Liste ist nur Text"),
                            ([{"bezeichnung": "X", "austausch": "nein"}], "Bestandteil-Liste ist nur Text"),
                            ([{"bezeichnung": "X"}, {"bezeichnung": "X"}], "Position 2: „X“ steht schon in Position 1"),
                            ([{"anzahl": 1}], "Position 1: Bitte eine Bezeichnung angeben.")):
            b = _importieren(app, _datei([_p(set=False, bestandteile=liste)]), trocken=True)
            assert any(text in f for f in b["fehler"]), (liste, b["fehler"])
        # Liste aus Texten: Hinweis, übergangen.
        b = _importieren(app, _datei([_p(bestandteile=["Tasche"])]), trocken=True)
        assert not b["fehler"] and any("Liste aus Texten" in h for h in b["hinweise"]), b
        # [] entfernt die Liste.
        b = _importieren(app, _datei([_p(bestandteile=[])]))
        assert b["bestandteillisten"]["geaendert"] == 1 and \
            not zeilen(app, "SELECT 1 FROM mat_product_component WHERE set_product_id = ?", (pid,))
        # Export → Import rund: die flache Liste ohne „set“.
        with app.test_request_context():
            from flask import g
            from app import db
            from app.material.services import katalog_export
            g.user = db.query("SELECT * FROM users WHERE id = ?", (t.k["katalog_id"],), one=True)
            daten, _, _ = katalog_export.sammeln(mit_dateien=False)
        e = next(x for x in daten["produkte"] if x["modell"] == "Lieferumfang Alpha")
        assert e["bestandteile"] == LISTE and "set" not in e, e
        with tempfile.TemporaryDirectory() as tmp2:
            app2 = make_app(tmp2)
            b = _importieren(app2, daten)
            assert not b["fehler"] and b["bestandteillisten"]["neu"] >= 1, b
        # Die DEMO-Vorlage geht im Probelauf ohne Fehler durch.
        with open(os.path.join(WURZEL, "docs", "material-katalog-bestandteile-vorlage.json"), encoding="utf-8") as fh:
            vorlage = json.load(fh)
        with tempfile.TemporaryDirectory() as tmp3:
            app3 = make_app(tmp3)
            b = _importieren(app3, vorlage, trocken=True)
            assert not b["fehler"] and b["bestandteillisten"]["neu"] == 1 and "stuecklisten" not in b, b
    print("Katalogdatei bestanden.")


# --- Oberfläche (statisch) -----------------------------------------------------------------------------------------------

# --- Nachbesserung nach den Prüfungen (25.10.2026; Proben der Prüfer Ablauf und Sicherheit) ------------------------------

def _art_nummern(t, iid):
    return [z["nummern"] for z in ok(t.w.get(f"/api/material/artikel/{iid}"))["artikel"]["bestandteile"]]


def _serien_von(t, pid, text):
    return zeile(ok(t.p.get(f"/api/material/pruefungen/{pid}"))["pruefung"], text)["nummern"]


def _setzen(t, pr, text, werte):
    return t.p.put(f"/api/material/pruefungen/{pr['id']}/punkte/{zeile(pr, text)['id']}", json={"seriennummern": werte})


TASCHE = "Platzhalter Tasche vorhanden"


def test_kennung_und_bezeichnung():
    """B1 (Prüfung Ablauf): Umbenennen schreibt die neue Position vor dem Löschen der alten (neue Kennung); kommt eine
    Kennung über zwei Änderungen doch wieder (Tasche weg, dann Beutel neu), übernimmt weder der offene Prüfentwurf noch
    der offene Antrag die Nummer der Tasche am Beutel – Prüfzeile 409 beim Eintragen, beim Festschreiben nicht übernommen
    (Protokoll ohne „neu“), Antrag passt nicht mehr und lässt sich nur ablehnen (TEIL_WEG vor STAND_ANDERS)."""
    with tempfile.TemporaryDirectory() as tmp, post():
        t = aufbau(tmp)
        tasche = t.pos["Platzhalter Tasche"]
        umbenannt = [LISTE[0], {"bezeichnung": "Platzhalter Beutel", "anzahl": 1}]
        # Offener Entwurf (R1) und offener Antrag (R2) an zwei Artikeln.
        a1 = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "R1"}),
                201)["artikel"]
        a2 = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "R2"}),
                201)["artikel"]
        pr0 = pruefung_von(t.p, a2["id"])
        ok(festschreiben(t.p, pr0["id"], ergebnis="einsatzbereit"))
        kid = ok(beantragen(t.w, a2["id"], bestandteil_nummern=nummern(t, T="AR-TASCHE")), 201)["antrag"]["id"]
        pr = pruefung_von(t.p, a1["id"])
        ok(_setzen(t, pr, TASCHE, ["NR-TASCHE"]))
        # Tasche weg, danach Beutel neu: Der Beutel bekommt die Kennung der Tasche wieder (höchste Kennung).
        ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile", json={"bestandteile": [LISTE[0]]}))
        p = ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile", json={"bestandteile": umbenannt}))["produkt"]
        assert {z["bezeichnung"]: z["id"] for z in p["bestandteile"]}["Platzhalter Beutel"] == tasche
        # Prüfung: Eintragen an der Zeile der Tasche 409, Festschreiben übernimmt nichts.
        r = _setzen(t, pr, TASCHE, ["NR-ANDERS"])
        assert r.status_code == 409 and "gibt es so nicht mehr" in r.json["error"], r.get_json()
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a1["id"]) == [["", ""], [""]]
        assert [n["neu"] for n in _serien_von(t, pr["id"], TASCHE)] == [None]
        # Antrag: passt nicht, Bestätigen 409 mit dem Satz zur Position, Ablehnen geht.
        x = ok(t.w.get(f"/api/material/artikel/{a2['id']}"))["artikel"]["antraege"][0]
        assert x["passt"] is False and [y["passt"] for y in x["aenderungen"]] == [False], x
        r = bestaetigen(t.w, kid)
        assert r.status_code == 409 and "diese Position gibt es so nicht mehr" in r.json["error"], r.get_json()
        assert _art_nummern(t, a2["id"]) == [["", ""], [""]]
        ok(ablehnen(t.w, kid, antwort="Platzhalter"))
        # Gegenprobe: Dieselbe Position mit anderer Schreibweise und höherer Anzahl passt weiter.
        a3 = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "R3"}),
                201)["artikel"]
        ok(festschreiben(t.p, pruefung_von(t.p, a3["id"])["id"], ergebnis="einsatzbereit"))
        t.pos = {z["bezeichnung"]: z["id"] for z in p["bestandteile"]}
        a_id = t.pos["Platzhalter Bestandteil A"]
        kid = ok(beantragen(t.w, a3["id"], bestandteil_nummern=[{"bestandteil_id": a_id, "stueck": 2,
                                                                  "seriennummer": "AR-A2"}]), 201)["antrag"]["id"]
        ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile",
                    json={"bestandteile": [{"bezeichnung": "platzhalter  BESTANDTEIL a", "anzahl": 3}, umbenannt[1]]}))
        ok(bestaetigen(t.w, kid))
        assert _art_nummern(t, a3["id"])[0] == ["", "AR-A2", ""]
        # Umbenennen in einem Zug: Die neue Position bekommt eine neue Kennung (erst einfügen, dann löschen).
        beutel = {z["bezeichnung"]: z["id"] for z in ok(t.mv.get(f"/api/material/produkte/{t.pid}"))["produkt"][
            "bestandteile"]}["Platzhalter Beutel"]
        p = ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile",
                        json={"bestandteile": [LISTE[0], {"bezeichnung": "Platzhalter Hülle"}]}))["produkt"]
        assert {z["bezeichnung"]: z["id"] for z in p["bestandteile"]}["Platzhalter Hülle"] > beutel
    print("Kennung und Bezeichnung bestanden.")


def test_berichtigung_wirksamer_wert():
    """B2 (Prüfung Ablauf) und S3 (Prüfung Sicherheit): Die Berichtigung vergleicht mit dem wirksamen Wert – setzt sie
    die Nummer des Originals zurück, geht das in den Artikel; hat ein Antrag sie nach dem Original geändert, nennt das
    Protokoll der Berichtigung diesen Stand als „alt“. Ein Stück, das sie nicht anfasst, bleibt wie im Original."""
    with tempfile.TemporaryDirectory() as tmp, post():
        t = aufbau(tmp)
        app = t.app

        def original(sn, vorher, eingetragen):
            a = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": sn,
                                                            "bestandteil_nummern": nummern(t, A1="A1-FEST", T=vorher)}),
                   201)["artikel"]
            pr = pruefung_von(t.p, a["id"])
            ok(_setzen(t, pr, TASCHE, [eingetragen]))
            ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
            return a, pr

        def berichtigen(pr, eingabe=None, a_eingabe=None):
            b = ok(t.p.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter"}),
                   201)["pruefung"]
            if eingabe is not None:
                ok(_setzen(t, b, TASCHE, [eingabe]))
            if a_eingabe is not None:
                ok(_setzen(t, b, "Platzhalter Bestandteil A (2×) vorhanden", a_eingabe))
            return b

        # Ablauf S1: Original ALT1 → NEU1, die Berichtigung trägt ALT1 ein (der Eintrag des Originals war falsch).
        a, pr = original("BER-1", "ALT1", "NEU1")
        b = berichtigen(pr, "ALT1")
        assert [n["artikel"] for n in zeile(ok(t.p.get(f"/api/material/pruefungen/{b['id']}"))["pruefung"],
                                            TASCHE)["nummern"]] == ["NEU1"]
        ok(festschreiben(t.p, b["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a["id"])[1] == ["ALT1"]
        assert [(n["alt"], n["neu"]) for n in _serien_von(t, b["id"], TASCHE)] == [("NEU1", "ALT1")]
        assert journal(app, a["id"], "bestandteil_nummern")[-1]["nachher"]["pruefung"] == b["id"]
        # Sicherheit probe10: Original A-T → P1, Antrag P1 → AN; Berichtigung D-NEU bzw. A-T.
        for sn, eingabe in (("BER-2", "D-NEU"), ("BER-3", "A-T")):
            a, pr = original(sn, "A-T", "P1")
            kid = ok(beantragen(t.w, a["id"], bestandteil_nummern=nummern(t, T="AN")), 201)["antrag"]["id"]
            ok(bestaetigen(t.w, kid))
            b = berichtigen(pr, eingabe)
            ok(festschreiben(t.p, b["id"], ergebnis="einsatzbereit"))
            assert _art_nummern(t, a["id"])[1] == [eingabe], sn
            assert [(n["alt"], n["neu"]) for n in _serien_von(t, b["id"], TASCHE)] == [("AN", eingabe)], sn
        # Unverändert gelassen (auch mitgeschickt): wie im Original, der Artikel behält den Stand nach dem Antrag.
        a, pr = original("BER-4", "A-T", "P1")
        kid = ok(beantragen(t.w, a["id"], bestandteil_nummern=nummern(t, T="AN")), 201)["antrag"]["id"]
        ok(bestaetigen(t.w, kid))
        b = berichtigen(pr, "P1", a_eingabe=["A1-FEST", ""])
        ok(festschreiben(t.p, b["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a["id"]) == [["A1-FEST", ""], ["AN"]]
        assert [(n["alt"], n["neu"]) for n in _serien_von(t, b["id"], TASCHE)] == [("A-T", "P1")]
        # Tippt der Prüfer zurück auf den Wert des Originals, gilt wieder dessen Eintrag.
        a, pr = original("BER-5", "A-T", "P1")
        b = berichtigen(pr, "X-ZWISCHEN")
        ok(_setzen(t, b, TASCHE, ["P1"]))
        ok(festschreiben(t.p, b["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a["id"])[1] == ["P1"]
        assert [(n["alt"], n["neu"]) for n in _serien_von(t, b["id"], TASCHE)] == [("A-T", "P1")]
    print("Berichtigung mit wirksamem Wert bestanden.")


def test_nicht_uebernommen_und_wettlauf():
    """B3 (Prüfung Ablauf): „n. z.“ mit eingetragener Nummer, gesunkene Anzahl und entfallene Position – das Protokoll
    hält kein „alt → neu“ fest, das am Artikel nicht geschah. B4: Ein Antrag, der die Nummer nach dem Eintrag des
    Prüfers ändert, wird nicht still überschrieben – 409 wie bei der Länge, danach gilt der Eintrag mit dem neuen „alt“."""
    with tempfile.TemporaryDirectory() as tmp, post():
        t = aufbau(tmp)
        # (a) n. z.
        a = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "NZ-1",
                                                        "bestandteil_nummern": nummern(t, T="ALT2")}), 201)["artikel"]
        pr = pruefung_von(t.p, a["id"])
        ok(_setzen(t, pr, TASCHE, ["NEU2"]))
        ok(t.p.put(f"/api/material/pruefungen/{pr['id']}/punkte/{zeile(pr, TASCHE)['id']}",
                   json={"befund": "nicht_zutreffend"}))
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a["id"])[1] == ["ALT2"]
        assert [(n["alt"], n["neu"]) for n in _serien_von(t, pr["id"], TASCHE)] == [("ALT2", None)]
        from test_material import pdf_seiten
        x = zeilen(t.app, "SELECT pdf_path FROM mat_inspection WHERE id = ?", (pr["id"],))[0]
        flach = " ".join(" ".join(pdf_seiten(os.path.join(tmp, x["pdf_path"]))).split()).replace("-", "")
        assert "NEU2" not in flach, flach[-600:]
        # (b) Anzahl sinkt und die Tasche fällt weg, während der Entwurf offen ist.
        a = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "NZ-2"}),
               201)["artikel"]
        pr = pruefung_von(t.p, a["id"])
        ok(_setzen(t, pr, "Platzhalter Bestandteil A (2×) vorhanden", ["N-A1", "N-A2"]))
        ok(_setzen(t, pr, TASCHE, ["N-T"]))
        ok(t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile",
                    json={"bestandteile": [{"bezeichnung": "Platzhalter Bestandteil A", "anzahl": 1}]}))
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a["id"]) == [["N-A1"]]
        assert [n["neu"] for n in _serien_von(t, pr["id"], "Platzhalter Bestandteil A (2×) vorhanden")] == ["N-A1", None]
        assert [n["neu"] for n in _serien_von(t, pr["id"], TASCHE)] == [None]
    with tempfile.TemporaryDirectory() as tmp, post():
        t = aufbau(tmp)
        # (c) Wettlauf R3: Eintrag PRUEFER, danach Antrag ALT → ANTRAG bestätigt.
        a = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "WL-1",
                                                        "bestandteil_nummern": nummern(t, T="ALT")}), 201)["artikel"]
        ok(festschreiben(t.p, pruefung_von(t.p, a["id"])["id"], ergebnis="einsatzbereit"))
        pr = pruefung_von(t.p, a["id"])
        ok(_setzen(t, pr, TASCHE, ["PRUEFER"]))
        kid = ok(beantragen(t.w, a["id"], bestandteil_nummern=nummern(t, T="ANTRAG")), 201)["antrag"]["id"]
        ok(bestaetigen(t.w, kid))
        r = festschreiben(t.p, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 409 and "während der Prüfung geändert" in r.json["error"] and \
            "Platzhalter Tasche: jetzt ANTRAG" in r.json["error"], r.get_json()
        assert _art_nummern(t, a["id"])[1] == ["ANTRAG"]
        assert [(n["alt"], n["wert"]) for n in _serien_von(t, pr["id"], TASCHE)] == [("ANTRAG", "PRUEFER")]
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        assert _art_nummern(t, a["id"])[1] == ["PRUEFER"]
        assert [(n["alt"], n["neu"]) for n in _serien_von(t, pr["id"], TASCHE)] == [("ANTRAG", "PRUEFER")]
        # Trägt der Prüfer erst nach dem Antrag ein (er sah den neuen Stand), kein Rückfragen.
        pr = pruefung_von(t.p, a["id"])
        kid = ok(beantragen(t.w, a["id"], bestandteil_nummern=nummern(t, T="ANTRAG-2")), 201)["antrag"]["id"]
        ok(bestaetigen(t.w, kid))
        ok(_setzen(t, pr, TASCHE, ["PRUEFER-2"]))
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        assert [(n["alt"], n["neu"]) for n in _serien_von(t, pr["id"], TASCHE)] == [("ANTRAG-2", "PRUEFER-2")]
    print("Nicht übernommen und Wettlauf bestanden.")


def test_steuerzeichen_und_mail():
    """S1 (Prüfung Sicherheit): Eine Eingabe nur aus Steuerzeichen ist leer – keine Nummer bzw. „Bitte eine Bezeichnung
    angeben“ statt 409 „anderswo geändert“; Antrag ohne Änderung 400; Prüfzeile und Abschließen laufen; die
    Katalogdatei nennt Produkt und Position. V1 (Prüfung Ablauf): Leerzeichen nach dem Doppelpunkt in der Antragsmail."""
    with tempfile.TemporaryDirectory() as tmp, post() as mails:
        t = aufbau(tmp)
        a = ok(t.w.post("/api/material/artikel", json={"product_id": t.pid, "folder_id": t.lager, "serial_no": "SZ-1",
                                                        "bestandteil_nummern": nummern(t, A1="\x01SN-1", T="\x01")}),
               201)["artikel"]
        assert _art_nummern(t, a["id"]) == [["SN-1", ""], [""]]
        ok(t.w.put(f"/api/material/artikel/{a['id']}", json={"bestandteil_nummern": nummern(t, A2="\x00\x01")}))
        r = t.mv.put(f"/api/material/produkte/{t.pid}/bestandteile", json={"bestandteile": [{"bezeichnung": "\x01"}]})
        assert r.status_code == 400 and "Position 1: Bitte eine Bezeichnung angeben" in r.json["error"], r.get_json()
        pr = pruefung_von(t.p, a["id"])
        ok(_setzen(t, pr, TASCHE, ["\x01"]))
        ok(festschreiben(t.p, pr["id"], ergebnis="einsatzbereit"))
        r = beantragen(t.p, a["id"], bestandteil_nummern=nummern(t, T="\x01"))
        assert r.status_code == 400 and "mindestens ein Feld" in r.json["error"], r.get_json()
        del mails[:]
        ok(beantragen(t.p, a["id"], bestandteil_nummern=nummern(t, T="MT-1")), 201)
        zeile_ = [x for x in mails[0][2].splitlines() if "Bestandteil" in x]
        assert zeile_ == ["Seriennummer Bestandteil „Platzhalter Tasche“: (leer) → MT-1"], zeile_
        b = _importieren(t.app, _datei([_p(bestandteile=[{"bezeichnung": "Gut"}, {"bezeichnung": "\x01"}])]), trocken=True)
        assert any("Lieferumfang Beta" in f and "Position 2: Bitte eine Bezeichnung angeben" in f for f in b["fehler"]), b
    print("Steuerzeichen und Mail bestanden.")


def _js():
    return open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8").read()


def test_oberflaeche_statisch():
    """Konstanten JS ↔ Python, Beschriftungen der neuen Journal-Aktionen in beiden, keine Piktogramme in den neuen
    Knöpfen."""
    from app.material.services import beschriftung, stueckliste
    js = _js()
    assert f'const BESTANDTEIL_GRUPPE = "{stueckliste.BESTANDTEIL_GRUPPE}";' in js
    for aktion in ("bestandteile", "bestandteil_nummern"):
        assert aktion in beschriftung.AKTION
        assert f'{aktion}: "{beschriftung.AKTION[aktion]}"' in js, aktion
    assert f'bestandteil_nummern: "{beschriftung.FELD["bestandteil_nummern"]}"' in js
    assert "Bestandteile bearbeiten" in js and "Seriennummern der Bestandteile" in js
    # Nachbesserung nach den Prüfungen (25.10.2026): Hinweis bei doppelter Nummer, Bemerkung mit Label vor dem Fieldset
    # der Nummern, Untermenü „Mehr“ auf der Produktseite, Kategorie über dem Hersteller.
    css = open(os.path.join(WURZEL, "app/material/static/material.css"), encoding="utf-8").read()
    assert "function doppeltePruefen(gruppe)" in js and "Diese Nummer steht schon an" in js
    assert js.index('class="mat-pnotiz-label"') < js.index("${nummern}</div>`;")
    assert '<fieldset class="mat-punkt-nummern">' in js
    assert '{ text: "Als Variante kopieren", satz: "Neues Produkt mit diesen Stammdaten.", attrs: \'data-act="variante"\' }' in js   # S.menue
    assert 'data-act="variante">Als Variante kopieren</button>' not in js
    assert "@container mat-seite (min-width: 900px) and (max-width: 979px)" in css and "mat-kat-zusatz" in js
    assert "btn ghost" not in js
    from app.material.services.teilnummern import stueck_text
    assert stueck_text("Teil (rot)", 1, 2) == "Teil (rot) – Stück 1 von 2" and stueck_text("Teil", 2, 2) == "Teil (Stück 2 von 2)"
    print("Oberfläche statisch bestanden.")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
