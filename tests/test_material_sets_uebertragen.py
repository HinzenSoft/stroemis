"""Sets anlegen und Stückliste übertragen (Wunsch des Nutzers, 24.10.2026):  python tests/test_material_sets_uebertragen.py

A – „Set anlegen“: Produkt und Stückliste atomar in einer Anfrage, Pflicht mindestens ein einzeln geführtes Teil (S3),
is_set nur mit Liste, Katalogimport mit derselben Regel. S8 – Set melden: Art und Teile an der Meldung, Set aus der
Meldung atomar und erledigt (Mail), Zuordnen eines Sets, Rechte. B – „Stückliste übertragen“: Schritt 22 (Trigger,
Spalten, Migration 21 → 22 mit Altbestand und zweitem Lauf), Vorschau (Gruppen, Wirkung, Ausschlüsse, ausgesonderte
gezählt, 403 für Materialwarte), je Änderungsart der Endzustand (nur Angaben – frei; Teil fehlt – gesperrt, einsetzen,
Set prüfen → frei; Teil übrig – Freigabe blockiert, entnehmen, Set prüfen → frei), veralteter Stand 409, Fehler im
zweiten Set rollt alles zurück, Jahresbericht zählt die Sperre einmal, Gliederungstrennung (Produktjournal ohne Nummern,
Lebenslauf ohne fremde Sets), alte Teiletabellen unverändert.

Alle Hersteller, Modelle, Nummern und Stücklisten hier sind erfunden und nur für den Test da."""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import _heute, make_app, mails_abfangen, mails_zurueck  # noqa: E402
from test_material_import import ok  # noqa: E402
from test_material_sets import _schema, _spalten, abgewiesen, roh, set_aufbau, stimmig  # noqa: E402
from test_material_sets_pruefung import eingangsgeprueft, lage, lauf_auf, set_pruefen  # noqa: E402
from test_material_trennung import bis_schritt, endversion, sql, zeilen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402


def _liste(t, **aenderung):
    """Die Stückliste aus set_aufbau als Anfrage – mit Änderungen je Position (Index → dict oder None zum Weglassen)."""
    basis = [{"produkt_id": t.ids["hms"], "bezeichnung": "Verbindungselement", "anzahl": 2, "einzeln": True},
             {"produkt_id": t.rolle, "anzahl": 1, "einzeln": True, "austausch": "ja"},
             {"bezeichnung": "Tasche", "anzahl": 1, "einzeln": False}]
    out = []
    for i, x in enumerate(basis):
        neu = aenderung.get(f"p{i}", {})
        if neu is None:
            continue
        out.append(dict(x, **neu))
    return out + aenderung.get("dazu", [])


def stueckliste_setzen(t, liste):
    return ok(t.k["katalog"].put(f"/api/material/produkte/{t.set_p}/bestandteile", json={"bestandteile": liste}))


def vorschau(t, c=None):
    return ok((c or t.k["katalog"]).get(f"/api/material/produkte/{t.set_p}/stueckliste-uebertragen"))


def uebertragen(t, v, ids, code=200):
    r = t.k["katalog"].post(f"/api/material/produkte/{t.set_p}/stueckliste-uebertragen",
                            json={"stand": v["stand"], "set_ids": ids})
    assert r.status_code == code, (r.status_code, r.get_json())
    return r.get_json()


def kopie(app, sid):
    return [(r["position"], r["product_id"], r["bezeichnung"], r["anzahl"], r["einzeln"], r["austausch"]) for r in
            zeilen(app, "SELECT * FROM mat_item_set_slot WHERE set_item_id = ? ORDER BY position, id", (sid,))]


def set_in(v, sid):
    return next(x for g in v["gruppen"] for x in g["sets"] if x["id"] == sid)


# --- A: Set anlegen -----------------------------------------------------------------------------------------------------

def test_set_anlegen_atomar():
    """POST /produkte mit is_set und bestandteile: Produkt und Stückliste in einem Zug; ein Fehler an Position 2 → 400,
    kein Produkt; is_set ohne oder mit leerer Liste 400, eine Liste ohne is_set 400; ohne einzeln geführtes Teil 400.
    sets_aelter sieht nur die Material-Verwaltung. Katalogimport: ein Set ohne einzeln geführte Position ist ein Fehler
    dieses Produkts – mit Liste und ohne Liste an einem neuen Set."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, mv = t.app, t.k["katalog"]
        basis = {"category_id": t.ids["gurte"], "manufacturer": "Testwerk", "model": "Testset Neu", "article_no": "TN-1",
                 "material_kind": "textil", "lifetime_years": 10}

        def falsch(d, text, code=400):
            r = mv.post("/api/material/produkte", json=dict(basis, **d))
            assert r.status_code == code and text in r.json["error"], (d, r.status_code, r.get_json())
            assert not zeilen(app, "SELECT 1 FROM mat_product WHERE article_no = 'TN-1'")
        falsch({"is_set": True, "bestandteile": [{"produkt_id": t.ids["hms"], "einzeln": True},
                                                 {"bezeichnung": "", "einzeln": False}]}, "Position 2: ")
        falsch({"is_set": True}, "mit seiner Stückliste")
        falsch({"is_set": True, "bestandteile": []}, "mit seiner Stückliste")
        falsch({"bestandteile": [{"produkt_id": t.ids["hms"], "einzeln": True}]}, "nur mit „is_set“")
        falsch({"is_set": True, "bestandteile": [{"bezeichnung": "Tasche"}]}, "mindestens ein einzeln geführtes Teil")
        assert t.wart_a.post("/api/material/produkte", json=dict(basis, is_set=True, bestandteile=_liste(t))).status_code \
            == 403
        p = ok(mv.post("/api/material/produkte", json=dict(basis, is_set=True, bestandteile=_liste(t))), 201)["produkt"]
        assert p["is_set"] and [b["anzahl"] for b in p["bestandteile"]] == [2, 1, 1] and p["sets_aelter"] == 0
        j = zeilen(app, "SELECT action FROM mat_audit WHERE entity = 'product' AND entity_id = ? ORDER BY id", (p["id"],))
        assert [x["action"] for x in j] == ["angelegt", "stueckliste"], j
        # Ein normales Produkt: is_set false oder fehlt.
        assert not ok(mv.post("/api/material/produkte", json=dict(basis, article_no="TN-2", is_set=False)),
                      201)["produkt"]["is_set"]
        # sets_aelter nur für die Material-Verwaltung.
        assert "sets_aelter" not in ok(t.wart_a.get(f"/api/material/produkte/{t.set_p}"))["produkt"]
        assert "sets_aelter" not in ok(t.k["fuehrung"].get(f"/api/material/produkte/{t.set_p}"))["produkt"]
        assert ok(mv.get(f"/api/material/produkte/{t.set_p}"))["produkt"]["sets_aelter"] == 0
        # Katalogimport: dieselbe Regel (S3).
        with app.app_context():
            from app.material.services import importer, katalog_export
            daten, _, _ = katalog_export.sammeln(mit_dateien=False)
            vorbild = {k: v for k, v in next(x for x in daten["produkte"] if x["modell"] == "Testset Alpha").items()
                       if k not in ("uid", "bild", "dokumente")}
            neu = [dict(vorbild, modell="Importset Ohne", artikelnummer="IO-1",
                        bestandteile=[{"bezeichnung": "Beutel", "anzahl": 1, "einzeln": False}]),
                   dict({k: v for k, v in vorbild.items() if k != "bestandteile"}, modell="Importset Leer",
                        artikelnummer="IL-1")]
            b = importer.importieren(dict(daten, produkte=daten["produkte"] + neu), trocken=True, quelle="Test")
        fehler = " | ".join(b["fehler"])
        assert "Importset Ohne" in fehler and "Importset Leer" in fehler and fehler.count("einzeln geführtes Teil") == 2, \
            b["fehler"]
        assert not zeilen(app, "SELECT 1 FROM mat_product WHERE article_no IN ('IO-1', 'IL-1')")
    print("Set anlegen (atomar, Pflicht, Import) bestanden.")


# --- S8: Set melden -----------------------------------------------------------------------------------------------------

def test_set_melden():
    """Meldung mit Art „Set“: Teile Pflicht, gespeichert, im Journal und in der Mail an die Verwaltung; eine
    Produktmeldung wie bisher. Set aus der Meldung: atomar mit Erledigen (ein Fehler in der Stückliste lässt Meldung und
    Katalog, wie sie waren), Mail an den Melder nennt das Set; is_set ohne Liste 400; nur die Material-Verwaltung.
    Zuordnen geht auch mit einem Set-Produkt."""
    from app.material.services import meldung
    gesendet = []

    def abfangen(an, betreff, inhalt):
        gesendet.append((an, betreff, inhalt))
        return True
    alt = mails_abfangen(meldung, abfangen)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            t = set_aufbau(tmp)
            app, mv, w = t.app, t.k["katalog"], t.wart_a
            r = w.post("/api/material/meldungen", json={"manufacturer": "Testwerk", "model": "Kombi Gamma",
                                                        "is_set": True, "folder_id": t.lager_a})
            assert r.status_code == 400 and "Teile des Sets" in r.json["error"], r.get_json()
            teile = "Testwerk Sitzgurt Gamma, 1\nTestwerk Brustgurt Gamma, 1"
            m = ok(w.post("/api/material/meldungen", json={"manufacturer": "Testwerk", "model": "Kombi Gamma",
                                                           "is_set": True, "set_teile": teile,
                                                           "folder_id": t.lager_a}), 201)["meldung"]
            assert m["is_set"] is True and m["set_teile"] == teile, m
            j = json.loads(zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'request' AND entity_id = ?",
                                  (m["id"],))[0]["after_json"])
            assert j["is_set"] is True and j["set_teile"] == teile, j
            an_verwaltung = [x for x in gesendet if "Set-Meldung: Testwerk Kombi Gamma" in x[1]]
            assert an_verwaltung and "hat ein Set gemeldet" in an_verwaltung[0][2] and "Teile des Sets:" in \
                an_verwaltung[0][2] and "Brustgurt Gamma" in an_verwaltung[0][2], an_verwaltung
            # Eine Produktmeldung bleibt, wie sie war (Teile zählen nicht).
            p = ok(w.post("/api/material/meldungen", json={"manufacturer": "Testwerk", "model": "Einzel Delta",
                                                           "set_teile": "zählt nicht", "folder_id": t.lager_a}),
                   201)["meldung"]
            assert p["is_set"] is False and p["set_teile"] == "", p
            assert '"is_set"' not in zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'request' "
                                                 "AND entity_id = ?", (p["id"],))[0]["after_json"]
            basis = {"category_id": t.ids["gurte"], "manufacturer": "Testwerk", "model": "Kombi Gamma", "article_no": "KG-1",
                     "material_kind": "textil", "lifetime_years": 10, "antwort": "Testantwort"}
            url = f"/api/material/meldungen/{m['id']}/produkt"
            # Rechte: nur die Material-Verwaltung.
            assert w.post(url, json=dict(basis, is_set=True, bestandteile=_liste(t))).status_code == 403
            # is_set ohne Liste: 400 – ein Set entsteht nur mit Stückliste.
            r = mv.post(url, json=dict(basis, is_set=True))
            assert r.status_code == 400 and "Stückliste" in r.json["error"], r.get_json()
            # Fehler in der Stückliste: nichts angelegt, Meldung offen.
            r = mv.post(url, json=dict(basis, is_set=True, bestandteile=[{"bezeichnung": "Beutel"}]))
            assert r.status_code == 400 and "einzeln geführtes Teil" in r.json["error"], r.get_json()
            assert not zeilen(app, "SELECT 1 FROM mat_product WHERE article_no = 'KG-1'")
            assert zeilen(app, "SELECT status FROM mat_product_request WHERE id = ?", (m["id"],))[0]["status"] == "offen"
            gesendet.clear()
            r = ok(mv.post(url, json=dict(basis, is_set=True, bestandteile=_liste(t))), 201)
            assert r["produkt"]["is_set"] and len(r["produkt"]["bestandteile"]) == 3, r["produkt"]
            assert r["meldung"]["status"] == "eingepflegt" and r["meldung"]["produkt"]["id"] == r["produkt"]["id"]
            an_melder = [x for x in gesendet if x[0] == "wart@example.org"]
            assert an_melder and "das von dir gemeldete Set ist jetzt im Katalog" in an_melder[0][2] and \
                "Testantwort" in an_melder[0][2], gesendet
            # Zuordnen eines vorhandenen Sets (Set-Produkt) an eine zweite Set-Meldung.
            m2 = ok(w.post("/api/material/meldungen", json={"manufacturer": "Testwerk", "model": "Testset Alpha neu",
                                                            "is_set": True, "set_teile": "zwei Karabiner, eine Rolle"}),
                    201)["meldung"]
            r = ok(mv.post(f"/api/material/meldungen/{m2['id']}/zuordnen", json={"product_id": t.set_p}))
            assert r["meldung"]["status"] == "eingepflegt" and r["meldung"]["produkt"]["is_set"], r["meldung"]
    finally:
        mails_zurueck(alt)
    print("Set melden und Set aus Meldung bestanden.")


# --- B: Schritt 22 ------------------------------------------------------------------------------------------------------

def test_schritt_22():
    """Trigger aus Schritt 22 direkt in SQLite: UPDATE nie, REPLACE nie; löschen und einfügen am freien Set geht, an
    einem Nicht-Set und an einem Teil nie, an einem ausgesonderten Set und bei offener Set-Prüfung nie; ein Set löschen
    nimmt die Kopie mit (ON DELETE CASCADE)."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, s, f = t.app, t.s["id"], t.f["id"]
        k1 = t.teile[0]
        conn = roh(app)
        einfuegen = ("INSERT INTO mat_item_set_slot (set_item_id, position, bezeichnung, anzahl, einzeln, austausch) "
                     "VALUES (?, 9, 'Nachschub', 1, 0, 'ja')")
        try:
            slot = conn.execute("SELECT id FROM mat_item_set_slot WHERE set_item_id = ? ORDER BY id", (s,)).fetchone()[0]
            abgewiesen(conn, "UPDATE mat_item_set_slot SET anzahl = 3 WHERE id = ?", (slot,), "unveränderlich")
            abgewiesen(conn, "INSERT OR REPLACE INTO mat_item_set_slot (id, set_item_id, position, bezeichnung, anzahl, "
                       "einzeln, austausch) VALUES (?, ?, 0, 'Ersatz', 1, 0, 'ja')", (slot, s), "als Ganzes")
            abgewiesen(conn, einfuegen, (f,), "als Ganzes")
            abgewiesen(conn, einfuegen, (k1,), "als Ganzes")
            # Am freien Set: als Ganzes ersetzen geht.
            conn.execute("DELETE FROM mat_item_set_slot WHERE set_item_id = ?", (s,))
            conn.execute(einfuegen, (s,))
            conn.rollback()
            # Set löschen: die Kopie geht mit.
            conn.execute("DELETE FROM mat_item WHERE parent_item_id = ?", (s,))
            conn.execute("DELETE FROM mat_item WHERE id = ?", (s,))
            assert not conn.execute("SELECT 1 FROM mat_item_set_slot WHERE set_item_id = ?", (s,)).fetchone()
            conn.rollback()
            # Offene Set-Prüfung: weder löschen noch einfügen.
            lauf = conn.execute("INSERT INTO mat_set_lauf (set_item_id, opened_at) VALUES (?, 'x')", (s,)).lastrowid
            conn.commit()
            abgewiesen(conn, "DELETE FROM mat_item_set_slot WHERE set_item_id = ?", (s,), "Set-Prüfung")
            abgewiesen(conn, einfuegen, (s,), "Set-Prüfung")
            conn.execute("DELETE FROM mat_set_lauf WHERE id = ?", (lauf,))
            conn.commit()
            # Ausgesondert: ebenso.
            conn.execute("UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ? OR parent_item_id = ?", (s, s))
            conn.commit()
            abgewiesen(conn, "DELETE FROM mat_item_set_slot WHERE set_item_id = ?", (s,), "ausgesonderten")
            abgewiesen(conn, einfuegen, (s,), "ausgesonderten")
        finally:
            conn.close()
        assert stimmig(app)
    print("Trigger aus Schritt 22 bestanden.")


def test_migration_22():
    """21 → 22 an einer Datenbank mit Altbestand (Set mit Teilen, Produktmeldung): die beiden Trigger neu, die Spalten
    an mat_product_request mit ihren Vorgaben, keine Zeile ändert sich, das Schema gleicht dem frischen; zweiter Lauf und
    Schritt 22 für sich ändern nichts."""
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert "ausgesondert" in schema_frisch[("trigger", "mat_slot_neu")]
    assert "mat_set_lauf" in schema_frisch[("trigger", "mat_slot_loeschen")]
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = bis_schritt(21, nachruesten=False)(set_aufbau, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "21"
        assert "is_set" not in _spalten(conn, "mat_product_request")
        assert "unveränderlich" in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'mat_slot_neu'").fetchone()[0]
        with conn:
            conn.execute("INSERT INTO mat_product_request (manufacturer, model, dedupe_key, created_at) VALUES "
                         "('Testwerk', 'Alt', 'testwerk|alt|', '2026-10-01T08:00:00+00:00')")
        vorher = {x: conn.execute(f"SELECT * FROM {x} ORDER BY rowid").fetchall() for x in
                  ("mat_item", "mat_product", "mat_item_set_slot", "mat_product_request", "mat_audit", "mat_set_lauf")}
        conn.close()
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        conn = roh(app)
        try:
            for x, alt in vorher.items():
                n = len(alt[0]) if alt else 0
                assert [r[:n] for r in conn.execute(f"SELECT * FROM {x} ORDER BY rowid").fetchall()] == alt, x
            assert conn.execute("SELECT is_set, set_teile FROM mat_product_request").fetchall() == [(0, "")]
            abgewiesen(conn, "UPDATE mat_product_request SET is_set = 2")
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            schema = _schema(pfad)
            assert schema == schema_frisch, {k: (schema.get(k), schema_frisch.get(k)) for k in set(schema) | set(schema_frisch)
                                             if schema.get(k) != schema_frisch.get(k)}
            assert models.migrieren(conn) == models.SCHEMA_VERSION
            conn.execute("BEGIN")
            n = conn.total_changes
            models._schritt_22(conn)
            models._schritt_22(conn)
            assert conn.total_changes == n
            conn.rollback()
            assert _schema(pfad) == schema_frisch
        finally:
            conn.close()
        # Der Altbestand lässt sich übertragen (Code 22 auf Daten von 21).
        stueckliste_setzen(t, _liste(t, p2={"bezeichnung": "Packsack"}))
        v = vorschau(t)
        assert v["uebertragbar"] == 2, v
    print("Migration 21 → 22 bestanden.")


# --- B: Vorschau und Übertragen -----------------------------------------------------------------------------------------

def test_vorschau():
    """Vorschau: Gruppen nach bisheriger Kopie mit Vergleich, je Set Wirkung; offene Set-Prüfung nicht übertragbar (mit
    Grund), ausgesonderte und gleiche nur gezählt; 409 ohne Stückliste mit einzeln geführtem Teil und an einem
    Nicht-Set; 403 für Materialwart, Führungskraft und Prüfer."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, mv = t.app, t.k["katalog"]
        v = vorschau(t)
        assert v["gruppen"] == [] and v["gleich"] == 2 and v["uebertragbar"] == 0, v
        for c in (t.wart_a, t.k["fuehrung"], t.k["pruefer"]):
            assert c.get(f"/api/material/produkte/{t.set_p}/stueckliste-uebertragen").status_code == 403
            assert c.post(f"/api/material/produkte/{t.set_p}/stueckliste-uebertragen", json={}).status_code == 403
        r = mv.get(f"/api/material/produkte/{t.ids['hms']}/stueckliste-uebertragen")
        assert r.status_code == 409, r.get_json()
        # Anzahl erhöht, Rolle entfernt, Tasche umbenannt.
        p = stueckliste_setzen(t, _liste(t, p0={"anzahl": 3}, p1=None, p2={"bezeichnung": "Packsack"}))["produkt"]
        assert p["sets_aelter"] == 2, p["sets_aelter"]
        lauf_auf(t.pruefer_b, t.sb["id"])
        v = vorschau(t)
        assert len(v["gruppen"]) == 1 and v["uebertragbar"] == 1 and v["sperrt"] == 1, v
        vg = {z["wirkung"] for z in v["gruppen"][0]["vergleich"]}
        assert vg == {"Anzahl 2 → 3", "entfällt", "Bezeichnung, Reihenfolge"}, v["gruppen"][0]["vergleich"]
        s = set_in(v, t.s["id"])
        assert s["uebertragbar"] and s["sperrt"] and "„Verbindungselement“ fehlt 1×" in s["wirkung"] and \
            "steht nicht mehr in der Stückliste" in s["wirkung"], s
        assert s["ordner"].endswith("Lager Musterstadt") and s["manufactured_on"], s
        sb = set_in(v, t.sb["id"])
        assert not sb["uebertragbar"] and "Set-Prüfung läuft" in sb["grund"], sb
        # Nicht übertragbares gewählt: 409, nichts geschrieben.
        alt = kopie(app, t.s["id"])
        uebertragen(t, v, [t.s["id"], t.sb["id"]], 409)
        assert kopie(app, t.s["id"]) == alt
        # Ausgesondert: nur gezählt.
        sql(app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ? OR parent_item_id = ?", (t.s["id"], t.s["id"]))
        v = vorschau(t)
        assert v["ausgesondert"] == 1 and v["uebertragbar"] == 0, v
        assert ok(mv.get(f"/api/material/produkte/{t.set_p}"))["produkt"]["sets_aelter"] == 1
    print("Vorschau „Stückliste übertragen“ bestanden.")


def test_nur_angaben():
    """Bezeichnung, Austausch, Reihenfolge und Bestandteile ohne eigenen Artikel (S6): Die Kopie ist danach die neue, das
    Set bleibt frei; Journal am Set mit vorher/nachher, kein Eintrag am Produkt mit Nummern. Eine gesperrte zieht ihre
    Gründe nach. Danach fragt die nächste Set-Prüfung die Bestandteile nach der neuen Kopie ab."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, s = t.app, t.s["id"]
        eingangsgeprueft(t)
        stueckliste_setzen(t, _liste(t, p1={"austausch": "nicht_belegt"}, p2={"bezeichnung": "Packsack", "anzahl": 2},
                                     dazu=[{"bezeichnung": "Seilsatz"}]))
        v = vorschau(t)
        assert set_in(v, s)["wirkung"] == "bleibt frei – nur Angaben" and not set_in(v, s)["sperrt"], set_in(v, s)
        r = uebertragen(t, v, [s, t.sb["id"]])
        assert r["uebertragen"] == 2 and r["gesperrt"] == 0 and r["produkt"]["sets_aelter"] == 0, r
        assert [x[2] for x in kopie(app, s)] == ["Verbindungselement", "Testwerk Rolle Gamma", "Packsack", "Seilsatz"]
        assert lage(app, s)[s][2] == "frei"
        j = zeilen(app, "SELECT user_name, before_json, after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                        "AND action = 'stueckliste_uebertragen'", (s,))
        assert len(j) == 1 and j[0]["user_name"] == "katalog" and "Tasche" in j[0]["before_json"] and \
            "Seilsatz" in j[0]["after_json"], j
        assert not zeilen(app, "SELECT 1 FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'gesperrt'",
                          (s,))
        # Gliederungstrennung: das Produktjournal nennt keine Inventarnummer.
        pj = " ".join(str(dict(x)) for x in zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'product' AND entity_id = ?",
                                                    (t.set_p,)))
        assert t.s["inventory_no"] not in pj and t.sb["inventory_no"] not in pj
        # Nächste Set-Prüfung: Ja/Nein-Zeilen nach der neuen Kopie.
        lauf_auf(t.k["pruefer"], s)
        from test_material import starten
        pr = starten(t.k["pruefer"], s).json["pruefung"]
        texte = [b["checklist_text"] for b in zeilen(app, "SELECT checklist_text FROM mat_inspection_result "
                                                          "WHERE inspection_id = ? AND checklist_item_id IS NULL", (pr["id"],))]
        assert texte == ["Packsack (2×) vorhanden", "Seilsatz vorhanden"], texte
    print("Übertragen – nur Angaben bestanden.")


def test_teil_fehlt_und_uebrig():
    """Anzahl erhöht → gesperrt („fehlt“), Teil einsetzen, Set prüfen → frei. Position entfernt → das Teil bleibt im Set,
    Set gesperrt, Freigabe blockiert („steht nicht mehr in der Stückliste“), Journal am Teil; Teil entnehmen, Set
    prüfen → frei. Jahresbericht: die Sperre aus dem Übertragen zählt einmal als „set“. Ein schon gesperrtes Set bleibt
    gesperrt, die Gründe ziehen nach. Lebenslauf des Sets in A nennt keine Nummern aus B; alte Teiletabellen bleiben."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, w, p = t.app, t.wart_a, t.k["pruefer"]
        s, k1, _, r1 = t.s["id"], *t.teile
        eingangsgeprueft(t)
        tabelle = zeilen(app, "SELECT * FROM mat_set_protokoll_zeile ORDER BY id")
        jahr = _heute().year

        def sperren_bericht():
            return ok(w.get(f"/api/material/ordner/{t.a}/bericht?jahr={jahr}"))["bericht"]["sperren"]
        b0 = sperren_bericht()
        # SB vorher gesperrt (Prüfer-Sperre am Teil in B).
        ok(t.pruefer_b.post(f"/api/material/artikel/{t.teile_b[0]}/sperren", json={"grund": "sturz", "text": "Teststurz"}))
        stueckliste_setzen(t, _liste(t, p0={"anzahl": 3}))
        v = vorschau(t)
        assert set_in(v, t.sb["id"])["wirkung"].startswith("bleibt gesperrt bis zur Set-Prüfung"), set_in(v, t.sb["id"])
        r = uebertragen(t, v, [s, t.sb["id"]])
        assert r["gesperrt"] == 2, r
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert a["lock_state"] == "gesperrt" and "„Verbindungselement“ fehlt" in a["lock_reason"], a["lock_reason"]
        assert [g["art"] for g in a["set"]["sperrgruende"]] == ["unvollstaendig", "set_pruefung"], a["set"]["sperrgruende"]
        assert lage(app, s)[k1][2] == "gesperrt" and stimmig(app)
        e = zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'gesperrt'",
                   (s,))
        assert len(e) == 1 and '"set_grund": "stueckliste"' in e[0]["after_json"], e
        b1 = sperren_bericht()
        assert b1["gesamt"] == b0["gesamt"] + 1 and {x["art"]: x["n"] for x in b1["arten"]}["set"] == 1, (b0, b1)
        sb = ok(t.wart_b.get(f"/api/material/artikel/{t.sb['id']}"))["artikel"]
        assert "Teststurz" in sb["lock_reason"] and "fehlt" in sb["lock_reason"], sb["lock_reason"]
        # Teil einsetzen, Set prüfen → frei.
        n = ok(w.post(f"/api/material/artikel/{s}/teil-einsetzen", json={"serial_no": "SET-A-K3", "bestaetigt": True}),
               201)
        neu = n["teil"]["id"]
        pr = set_pruefen(p, s, [neu])
        assert pr["set_protokoll"]["gesamt"] == "einsatzbereit", pr["set_protokoll"]
        assert lage(app, s)[s][2] == "frei"
        # Position entfernt: Rolle bleibt im Set, Set gesperrt.
        stueckliste_setzen(t, _liste(t, p0={"anzahl": 3}, p1=None))
        r = uebertragen(t, vorschau(t), [s])
        assert r["gesperrt"] == 1
        assert zeilen(app, "SELECT parent_item_id FROM mat_item WHERE id = ?", (r1,))[0]["parent_item_id"] == s
        a = ok(w.get(f"/api/material/artikel/{s}"))["artikel"]
        assert "nicht mehr in der Stückliste" in a["lock_reason"], a["lock_reason"]
        ue = [g for g in a["set"]["sperrgruende"] if g["art"] == "ueberzaehlig"]
        assert len(ue) == 1 and ue[0]["artikel"]["id"] == r1 and "erst „Teil entnehmen“" in ue[0]["text"], ue
        tj = zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                         "AND action = 'nicht_in_stueckliste'", (r1,))
        assert len(tj) == 1 and '"bestandteil": "Testwerk Rolle Gamma"' in tj[0]["after_json"], tj
        pr = set_pruefen(p, s, [])
        assert pr["set_protokoll"]["gesamt"] == "gesperrt" and any(
            "steht nicht mehr in der Stückliste" in g for g in pr["set_protokoll"]["gruende"]), pr["set_protokoll"]
        ok(w.post(f"/api/material/artikel/{s}/teil-entnehmen", json={"teil_id": r1}))
        pr = set_pruefen(p, s, [])
        assert pr["set_protokoll"]["gesamt"] == "einsatzbereit", pr["set_protokoll"]
        assert lage(app, s)[s][2] == "frei" and stimmig(app)
        # Alte Teiletabellen unverändert, Lebenslauf des Sets ohne Nummern aus B.
        assert zeilen(app, f"SELECT * FROM mat_set_protokoll_zeile WHERE id <= {tabelle[-1]['id']} ORDER BY id") == tabelle
        lj = " ".join(x["after_json"] or "" for x in zeilen(app, "SELECT after_json FROM mat_audit WHERE entity = 'item' "
                                                                 "AND entity_id = ?", (s,)))
        assert t.sb["inventory_no"] not in lj and all(
            x["inventory_no"] not in lj for x in zeilen(app, "SELECT inventory_no FROM mat_item WHERE parent_item_id = ?",
                                                        (t.sb["id"],)))
        assert w.get(f"/material/artikel/{s}/lebenslauf.pdf").status_code == 200
    print("Übertragen – Teil fehlt und Teil übrig bestanden.")


def test_stand_und_rollback():
    """Veralteter Stand → 409, nichts geschrieben; ein Fehler im zweiten Set rollt das erste zurück; leere Auswahl 400."""
    from app.material.services import Abgelehnt, setkopie
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        app, s, sb = t.app, t.s["id"], t.sb["id"]
        stueckliste_setzen(t, _liste(t, p2={"bezeichnung": "Packsack"}))
        v = vorschau(t)
        uebertragen(t, v, [], 400)
        stueckliste_setzen(t, _liste(t, p2={"bezeichnung": "Beutel"}))
        alt = (kopie(app, s), kopie(app, sb))
        r = uebertragen(t, v, [s, sb], 409)
        assert "Inzwischen geändert" in r["error"] and (kopie(app, s), kopie(app, sb)) == alt
        v = vorschau(t)
        echt = setkopie._uebertragen_an
        aufrufe = []

        def zweiter_scheitert(*a):
            aufrufe.append(a[0]["id"])
            if len(aufrufe) == 2:
                raise Abgelehnt("Testfehler im zweiten Set", 409)
            return echt(*a)
        setkopie._uebertragen_an = zweiter_scheitert
        try:
            r = uebertragen(t, v, [s, sb], 409)
        finally:
            setkopie._uebertragen_an = echt
        assert aufrufe == [s, sb] and (kopie(app, s), kopie(app, sb)) == alt, aufrufe
        assert not zeilen(app, "SELECT 1 FROM mat_audit WHERE action = 'stueckliste_uebertragen'")
        r = uebertragen(t, v, [sb])
        assert r["uebertragen"] == 1 and kopie(app, s) == alt[0] and kopie(app, sb) != alt[1]
        assert ok(t.k["katalog"].get(f"/api/material/produkte/{t.set_p}"))["produkt"]["sets_aelter"] == 1
    print("Stand und Rückrollen bestanden.")


if __name__ == "__main__":
    test_set_anlegen_atomar()
    test_set_melden()
    test_schritt_22()
    test_migration_22()
    test_vorschau()
    test_nur_angaben()
    test_teil_fehlt_und_uebrig()
    test_stand_und_rollback()
    print("Alle Tests bestanden.")
