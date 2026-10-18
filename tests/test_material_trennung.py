"""Trennung je Gliederung – Freigaben je Ordner (Phase 2 · Lieferung 1):  python tests/test_material_trennung.py
oder  pytest tests/test_material_trennung.py

Die Kerntests des Rechtekerns nach dem Bauentwurf 8.2: Migration 7 → 8 (Nr. 1), Ablauf einer Freigabe mit dem
deutschen Kalendertag (Nr. 12), Prüfen nur mit Prüffreigabe – auch für Verwalter und Verwaltung (Nr. 13), Abfragezahl
der Materialstufe (Nr. 14) –, dazu Einheitstests für die Sicht (Vererbung, Pfad-Knoten, teilweise sichtbare
Systemordner, Prüffreigabe ohne Qualifikation, Heimat im Filter, mehrere Freigaben und ihr Ende) und für
requires_folder (404 für Fremdes wie für Unbekanntes, 403 nur bei sichtbarem Gegenstand, Kennungen als „7“ und 7.0,
Formular und JSON).

Weitere Pakete hängen ihre Tests unten an (vor dem Block __main__) und bauen mit zwei_gliederungen() auf: zwei
Gliederungen nebeneinander, jede mit eigenem Verwalter. Alle Namen, Hersteller und Nummern hier sind erfunden und nur
für den Test da."""
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, freigeben, gliederung, jpeg, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           neues_konto, pruef_formulare, starten, umgebung)
from test_material_ueberblick import ohne_post, ordner_neu  # noqa: E402


# --- Aufbau (für alle Tests dieser Datei und die, die dazukommen) ------------------------------------------------

def zwei_gliederungen(tmp):
    """Zwei Gliederungen nebeneinander. A („OG Musterstadt“) mit den Konten aus umgebung und ihren Standardfreigaben
    (wart verwaltet, fuehrung und katalog lesen, pruefer liest und prüft); B („OG Nachbarstadt“) mit eigenem Verwalter
    wart_b und eigener Prüferin pruefer_b – niemand aus A hat dort eine Freigabe. Je Gliederung ein Lager mit einem
    Karabiner (aktives Formular); in B dazu ein Prüfdurchgang über das Lager und ein Entwurf der Prüferin darin.

    Liefert ein SimpleNamespace: app, k (Konten aus umgebung), adm, ids (Katalog), a/b (Gliederungen), sys_a/sys_b
    (Systemordner), lager_a/lager_b, art_a/art_b (Artikel als JSON), wart_a (= k["wart"]), wart_b, wart_b_id,
    pruefer_b, pruefer_b_id, durchgang_b, entwurf_b."""
    app, k = umgebung(tmp)
    adm = k["adm"]
    ids = katalog_grund(adm)
    pruef_formulare(k["katalog"], ids)
    a, sys_a = gliederung(adm, "OG Musterstadt")
    b, sys_b = gliederung(adm, "OG Nachbarstadt", standard=False)
    wart_b, wart_b_id = neues_konto(app, "wart_b@example.org", name="Wart Nachbarstadt")
    pruefer_b, pruefer_b_id = neues_konto(app, "pruefer_b@example.org", name="Prüferin Nachbarstadt", mat_pruefer=True,
                                          urkundennummer="1012-9001")
    freigeben(adm, b, wart_b_id, "verwalten")
    freigeben(adm, b, pruefer_b_id, "lesen")
    freigeben(adm, b, pruefer_b_id, "pruefen")
    lager_a = ordner_neu(k["wart"], a, "Lager Musterstadt")
    lager_b = ordner_neu(wart_b, b, "Lager Nachbarstadt")
    art_a = neuer_artikel(k["wart"], ids["hms"], lager_a, serial_no="TEST-A-0001")
    art_b = neuer_artikel(wart_b, ids["hms"], lager_b, serial_no="TEST-B-0001")
    r = wart_b.post("/api/material/durchgaenge", json={"folder_id": lager_b, "titel": "Testdurchgang Nachbarstadt"})
    assert r.status_code == 201, r.get_json()
    durchgang_b = r.json["durchgang"]["id"]
    r = starten(pruefer_b, art_b["id"], durchgang_id=durchgang_b)
    assert r.status_code == 201, r.get_json()
    return SimpleNamespace(app=app, k=k, adm=adm, ids=ids, a=a, sys_a=sys_a, b=b, sys_b=sys_b, lager_a=lager_a,
                           lager_b=lager_b, art_a=art_a, art_b=art_b, wart_a=k["wart"], wart_b=wart_b,
                           wart_b_id=wart_b_id, pruefer_b=pruefer_b, pruefer_b_id=pruefer_b_id,
                           durchgang_b=durchgang_b, entwurf_b=r.json["pruefung"]["id"])


def sql(app, befehl, args=()):
    """Direkt in die Datenbank schreiben (Altfälle, Ablauf) – mit Commit."""
    with app.app_context():
        from app import db
        db.execute(befehl, args)


def zeilen(app, abfrage, args=()):
    with app.app_context():
        from app import db
        return db.query(abfrage, args)


def sicht_von(app, uid):
    """Die Sicht eines Kontos – in einem eigenen Anwendungskontext, also frisch gerechnet."""
    with app.app_context():
        from app import db
        from app.material.services import rechte
        return rechte.sicht(db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True))


def gleich_wie_unbekannt(r, unbekannt):
    """Fremdes antwortet wie Unbekanntes: gleicher Status, gleicher Text."""
    assert r.status_code == unbekannt.status_code == 404, (r.status_code, r.get_json(), unbekannt.get_json())
    assert r.get_json() == unbekannt.get_json(), (r.get_json(), unbekannt.get_json())


# --- 8.2/1: Migration 7 → 8 -------------------------------------------------------------------------------------

def test_migration_7_8():
    """Eine Datenbank auf Stand 7 (Phase 1): Stufen und Häkchen werden Freigaben an den vorhandenen Gliederungen – je
    eingefügter Zeile ein Journaleintrag –, jedes Konto bekommt ein mat_ref, die Altfälle werden bereinigt; die Spalten
    aus Phase 1 bleiben, und ein zweiter Start ändert nichts."""
    from app.material.services.interval import plus_monate
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gl1, sys1 = gliederung(adm, "OG Eins", standard=False)
        gl2, sys2 = gliederung(adm, "OG Zwei", standard=False)
        lager1, lager2 = ordner_neu(adm, gl1, "Lager Eins"), ordner_neu(adm, gl2, "Lager Zwei")
        y = neuer_artikel(adm, ids["hms"], lager1, serial_no="MIG-0002")["id"]   # im Durchgang, in Phase 1 nach GL2
        z = neuer_artikel(adm, ids["hms"], lager1, serial_no="MIG-0003")["id"]   # bleibt im Zweig
        rid = adm.post("/api/material/durchgaenge", json={"folder_id": lager1, "titel": "Testdurchgang"}).json["durchgang"]["id"]
        x = neuer_artikel(adm, ids["hms"], lager1, serial_no="MIG-0001")["id"]   # gesperrt, Herkunft in GL2
        freigeben(adm, gl1, k["pruefer_id"], "pruefen")
        entwurf = starten(k["pruefer"], y, durchgang_id=rid).json["pruefung"]["id"]
        konten = {n: neues_konto(app, f"{n}@example.org")[1] for n in ("stufe1", "stufe2", "ohne_urkunde", "katalogpflege",
                                                                         "pv")}
        # So hat Phase 1 die Konten hinterlassen (Prüfer und Katalogpfleger hob die Nutzerverwaltung auf Stufe 1).
        sql(app, "UPDATE users SET recht_material = 0, mat_pruefer = 0, mat_katalog = 0, urkundennummer = '' "
                 "WHERE id NOT IN (SELECT id FROM users WHERE recht_verwaltung = 2)")
        sql(app, "UPDATE users SET mat_pruefer = 0 WHERE recht_verwaltung = 2")
        for uid, spalten in ((konten["stufe1"], "recht_material = 1"),
                             (konten["stufe2"], "recht_material = 2, mat_pruefer = 1, urkundennummer = '1012-0001'"),
                             (konten["ohne_urkunde"], "recht_material = 1, mat_pruefer = 1"),
                             (konten["katalogpflege"], "recht_material = 1, mat_katalog = 1"),
                             (konten["pv"], "recht_verwaltung = 2, recht_material = 2, mat_pruefer = 1, "
                                            "urkundennummer = '1012-0002'")):
            sql(app, f"UPDATE users SET {spalten} WHERE id = ?", (uid,))
        # Altfälle: ein Gesperrter im „Gesperrt“ von GL1 mit Herkunft in GL2; eine offene Durchgangszeile außerhalb des
        # Zweigs (in Phase 1 verschoben, ohne dass der Durchgang davon wusste).
        sql(app, "UPDATE mat_item SET lock_state = 'gesperrt', lock_reason = 'Testsperre', folder_id = ?, "
                 "origin_folder_id = ? WHERE id = ?", (sys1["gesperrt"], lager2, x))
        sql(app, "UPDATE mat_item SET folder_id = ? WHERE id = ?", (lager2, y))
        # Stand 7: keine Freigaben, keine Kontoverweise, Schemaversion 7.
        sql(app, "DELETE FROM mat_folder_grant")
        sql(app, "UPDATE users SET mat_ref = NULL")
        sql(app, "UPDATE mat_meta SET wert = '7' WHERE schluessel = 'schema_version'")
        stufen_vorher = zeilen(app, "SELECT id, recht_material, mat_pruefer, mat_katalog FROM users ORDER BY id")
        journal_vorher = zeilen(app, "SELECT MAX(id) AS m FROM mat_audit")[0]["m"]

        app = make_app(tmp)                                    # Neustart: Schritt 8 läuft
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == "8"
        h = _heute()
        bis = min(f"{h.year + 1}-12-31", plus_monate(h, 24).isoformat())
        if h.year == 2026:
            assert bis == "2027-12-31"
        erwartet = set()
        for g in (gl1, gl2):
            erwartet |= {(g, konten["stufe1"], "lesen", None, "aus Phase 1: Stufe Mitglied"),
                         (g, konten["stufe2"], "verwalten", None, "aus Phase 1: Stufe Verwaltung"),
                         (g, konten["stufe2"], "pruefen", bis, "aus Phase 1: Häkchen Prüfer"),
                         (g, konten["ohne_urkunde"], "lesen", None, "aus Phase 1: Stufe Mitglied"),
                         (g, konten["ohne_urkunde"], "pruefen", bis, "aus Phase 1: Häkchen Prüfer"),
                         (g, konten["katalogpflege"], "lesen", None, "aus Phase 1: Stufe Mitglied"),
                         (g, konten["pv"], "pruefen", bis, "aus Phase 1: Häkchen Prüfer")}
        freigaben = zeilen(app, "SELECT * FROM mat_folder_grant ORDER BY id")
        assert {(f["folder_id"], f["user_id"], f["permission"], f["valid_until"], f["note"]) for f in freigaben} == erwartet
        assert all(f["granted_by"] is None for f in freigaben)
        # Je Zeile ein Journaleintrag am Ordner – mit Kontoverweis, ohne Notiz und ohne Namen.
        refs = {u["id"]: u["mat_ref"] for u in zeilen(app, "SELECT id, mat_ref FROM users")}
        assert all(re.fullmatch(r"[0-9a-f]{32}", r or "") for r in refs.values()), refs
        assert len(set(refs.values())) == len(refs)
        eintraege = zeilen(app, "SELECT * FROM mat_audit WHERE id > ? AND action = 'freigabe_erteilt' ORDER BY id",
                           (journal_vorher,))
        assert len(eintraege) == len(freigaben) == 14
        nach_id = {f["id"]: f for f in freigaben}
        for e in eintraege:
            d = json.loads(e["after_json"])
            f = nach_id[d["freigabe"]]
            assert e["entity"] == "folder" and e["entity_id"] == f["folder_id"] and e["user_name"] == "Migration Schritt 8"
            assert d == {"freigabe": f["id"], "konto": {"ref": refs[f["user_id"]]}, "recht": f["permission"],
                         "bis": f["valid_until"]}, d
        # Bereinigung: Der Gesperrte liegt jetzt in „Gesperrt“ von GL2; die Zeile außerhalb des Zweigs ist ausgenommen,
        # der Entwurf dazu hängt an keinem Durchgang mehr; was im Zweig liegt, bleibt offen.
        assert zeilen(app, "SELECT folder_id FROM mat_item WHERE id = ?", (x,))[0]["folder_id"] == sys2["gesperrt"]
        verschoben = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'verschoben'",
                            (x,))
        assert len(verschoben) == 1 and json.loads(verschoben[0]["after_json"])["grund"] == "Bereinigung Schritt 8"
        ri = {r["item_id"]: r for r in zeilen(app, "SELECT * FROM mat_round_item WHERE round_id = ?", (rid,))}
        assert ri[y]["excluded_reason"] == "verschoben (Bereinigung Schritt 8)" and ri[y]["excluded_by_name"] == "System"
        assert ri[z]["excluded_reason"] is None
        assert zeilen(app, "SELECT round_id FROM mat_inspection WHERE id = ?", (entwurf,))[0]["round_id"] is None
        assert zeilen(app, "SELECT 1 FROM mat_audit WHERE entity = 'round' AND entity_id = ? AND action = 'ausgenommen' "
                           "AND user_name = 'Migration Schritt 8'", (rid,))
        # Die Spalten aus Phase 1 bleiben, wie sie waren (Rückweg).
        assert zeilen(app, "SELECT id, recht_material, mat_pruefer, mat_katalog FROM users ORDER BY id") == stufen_vorher

        # Ein zweiter Start ändert nichts – und Schritt 8 selbst ist wiederholbar.
        def stand():
            return {t: zeilen(app, f"SELECT * FROM {t} ORDER BY rowid")
                    for t in ("mat_folder_grant", "mat_audit", "mat_item", "mat_round_item", "mat_inspection")} | {
                "users": zeilen(app, "SELECT id, mat_ref, recht_material FROM users ORDER BY id")}
        vorher = stand()
        app = make_app(tmp)
        assert stand() == vorher
        from app.material import models
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_8(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
    print("Migration 7 → 8 bestanden.")


# --- Sicht: Vererbung, Pfad-Knoten, Systemordner, Heimat ----------------------------------------------------------

def test_sicht():
    """Die Sicht eines Kontos: Freigaben gelten nach unten; über einem Anker liegen nur Pfad-Knoten; die Systemordner
    einer unsichtbaren Gliederung sind teilweise sichtbar; eine Prüffreigabe ohne Qualifikation wirkt gar nicht;
    artikel_filter zählt über die Heimat; mehrere Freigaben vereinigen sich, ihr Ende ist das späteste."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        ids = katalog_grund(adm)
        a, sys_a = gliederung(adm, "OG Musterstadt", standard=False)
        b, _ = gliederung(adm, "OG Nachbarstadt", standard=False)
        lager = ordner_neu(adm, a, "Lager")
        fahrzeug = ordner_neu(adm, lager, "Fahrzeug Eins", "fahrzeug")
        satz = ordner_neu(adm, fahrzeug, "Satz Eins", "set")
        halle = ordner_neu(adm, a, "Halle")
        nord = ordner_neu(adm, a, "Ortsgruppe Nord", "gliederung")
        lager_b = ordner_neu(adm, b, "Lager Nachbarstadt")
        sys_nord = {r["system_kind"]: r["id"] for r in zeilen(app, "SELECT id, system_kind FROM mat_folder WHERE "
                                                                   "parent_id = ? AND system_kind IS NOT NULL", (nord,))}

        def konto(name, **felder):
            return neues_konto(app, f"{name}@example.org", **felder)
        leser, leser_id = konto("leser")
        fahrer, fahrer_id = konto("fahrer")
        _, unq_id = konto("unqualifiziert", mat_pruefer=True)                 # Häkchen, aber keine Urkundennummer
        qual, qual_id = konto("qualifiziert", mat_pruefer=True, urkundennummer="1012-7001")
        _, mehr_id = konto("mehrfach")
        freigeben(adm, a, leser_id, "lesen")
        freigeben(adm, fahrzeug, fahrer_id, "lesen")
        freigeben(adm, lager, unq_id, "pruefen")
        freigeben(adm, lager, qual_id, "pruefen")
        h = _heute()
        d1, d2 = (h + timedelta(days=10)).isoformat(), (h + timedelta(days=40)).isoformat()
        freigeben(adm, a, mehr_id, "lesen", bis=d1)
        freigeben(adm, lager, mehr_id, "verwalten", bis=d2)
        freigeben(adm, fahrzeug, mehr_id, "lesen")

        # Vererbung: an der Gliederung → alles darunter, auch verschachtelte Gliederungen und Systemordner; nicht B.
        s = sicht_von(app, leser_id)
        unter_a = {r["id"] for r in zeilen(app, "WITH RECURSIVE t(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f "
                                                "JOIN t ON f.parent_id = t.id) SELECT id FROM t", (a,))}
        assert s.lesbar == s.grund == unter_a and {satz, nord, sys_nord["gesperrt"], sys_a["ausgesondert"]} <= s.lesbar
        assert not s.verwaltbar and not s.pruefbar and not s.pfad_knoten and not s.teil_system
        assert s.darf("lesen", satz) and s.darf("grund", satz) and not s.darf("lesen", lager_b) and not s.darf("lesen", b)
        assert not s.darf("verwalten", satz) and not s.darf("lesen", None) and s.irgendwo("lesen")
        assert s.ende("lesen", satz) is None

        # Nur am Fahrzeug: Lager und Gliederung sind Pfad-Knoten, ihre Systemordner teilweise sichtbar, Geschwister weg.
        s = sicht_von(app, fahrer_id)
        assert s.lesbar == {fahrzeug, satz}
        assert s.pfad_knoten == {lager, a}
        assert s.teil_system == {sys_a["gesperrt"], sys_a["ausgesondert"]}
        assert not ({halle, nord, b} & (s.lesbar | s.pfad_knoten | s.teil_system))
        assert s.sichtbar(sys_a["gesperrt"]) and not s.darf("lesen", sys_a["gesperrt"]) and not s.sichtbar(lager)
        assert fahrer.get(f"/api/material/ordner/{satz}").status_code == 200
        assert fahrer.get(f"/api/material/ordner/{sys_a['gesperrt']}").status_code == 200    # nur teilweise
        unbekannt = fahrer.get("/api/material/ordner/999999")
        for fid in (a, lager, halle, nord, b):
            gleich_wie_unbekannt(fahrer.get(f"/api/material/ordner/{fid}"), unbekannt)
        assert fahrer.put(f"/api/material/ordner/{sys_a['gesperrt']}", json={"name": "x"}).status_code == 403

        # Prüffreigabe ohne Qualifikation: wirkungslos, auch nicht als Leserecht. Mit Qualifikation: nur die Prüfsicht.
        s = sicht_von(app, unq_id)
        assert not s.lesbar and not s.pruefbar and not s.pfad_knoten and not s.qualifiziert
        assert [f.permission for f in s.freigaben] == ["pruefen"]           # die Zeile gilt, sie wirkt nur nicht
        s = sicht_von(app, qual_id)
        assert s.qualifiziert and s.pruefbar == s.lesbar == {lager, fahrzeug, satz} and not s.grund
        assert s.darf("pruefen", satz) and s.darf("lesen", satz) and not s.darf("grund", satz)
        assert s.pfad_knoten == {a} and s.teil_system == {sys_a["gesperrt"], sys_a["ausgesondert"]}
        assert s.ende("pruefen", satz) == (h + timedelta(days=365)).isoformat()

        # Mehrere Freigaben: vereinigt; das Ende ist das späteste deckende (unbefristet schlägt alles).
        s = sicht_von(app, mehr_id)
        assert s.lesbar == unter_a and s.verwaltbar == {lager, fahrzeug, satz}
        assert s.ende("lesen", halle) == d1
        assert s.ende("lesen", lager) == d2                                  # verwalten zählt als lesen
        assert s.ende("verwalten", satz) == d2
        assert s.ende("lesen", satz) is None and s.ende("grund", fahrzeug) is None
        try:
            s.ende("verwalten", halle)
            raise AssertionError("ende ohne Recht")
        except Exception as exc:
            assert getattr(exc, "code", None) == 403, exc
        # Abgelaufen zählt nicht – der letzte Tag schon.
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ? AND folder_id = ?",
            ((h - timedelta(days=1)).isoformat(), mehr_id, a))
        s = sicht_von(app, mehr_id)
        assert halle not in s.lesbar and lager in s.lesbar and s.pfad_knoten == {a}
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ? AND folder_id = ?", (h.isoformat(), mehr_id, a))
        assert halle in sicht_von(app, mehr_id).lesbar

        # Heimat im Filter: Gesperrte und Ausgesonderte zählen bei ihrem Herkunftsordner, ohne Herkunft bei der
        # Gliederung (Systemordner).
        frei = neuer_artikel(adm, ids["hms"], satz)["id"]
        halle_frei = neuer_artikel(adm, ids["hms"], halle)["id"]
        gesperrt = neuer_artikel(adm, ids["hms"], satz)["id"]
        gesperrt_halle = neuer_artikel(adm, ids["hms"], halle)["id"]
        weg_ohne = neuer_artikel(adm, ids["hms"], halle)["id"]
        weg_mit = neuer_artikel(adm, ids["hms"], fahrzeug)["id"]
        for iid, art, ziel in ((gesperrt, "gesperrt", sys_a["gesperrt"]), (gesperrt_halle, "gesperrt", sys_a["gesperrt"]),
                               (weg_mit, "ausgesondert", sys_a["ausgesondert"])):
            sql(app, "UPDATE mat_item SET lock_state = ?, origin_folder_id = folder_id, folder_id = ? WHERE id = ?",
                (art, ziel, iid))
        sql(app, "UPDATE mat_item SET lock_state = 'ausgesondert', origin_folder_id = NULL, folder_id = ? WHERE id = ?",
            (sys_a["ausgesondert"], weg_ohne))
        with app.app_context():
            from app import db
            from app.material.services import bestand, rechte

            def sichtbar(uid, recht="lesen"):
                u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
                rechte.sicht_verwerfen()
                return {r["id"] for r in db.query(f"SELECT i.id FROM mat_item i WHERE {rechte.artikel_filter('i', recht, u)}")}
            assert sichtbar(fahrer_id) == {frei, gesperrt, weg_mit}
            assert sichtbar(leser_id) == {frei, halle_frei, gesperrt, gesperrt_halle, weg_ohne, weg_mit}
            assert sichtbar(qual_id, "pruefen") == {frei, gesperrt, weg_mit} and sichtbar(qual_id, "grund") == set()
            assert sichtbar(unq_id) == set()
            adm_row = db.query("SELECT * FROM users WHERE email = 'admin@example.org'", one=True)
            assert rechte.artikel_filter("i", user=adm_row) == "1" and rechte.ordner_filter("r.folder_id", user=adm_row) == "1"
            assert rechte.artikel_filter("i", "pruefen", adm_row) == "0"             # die Verwaltung prüft nicht von selbst
            for iid in (frei, gesperrt, weg_ohne):
                i = bestand.artikel(iid)
                assert bestand.heimat(i) == db.query(f"SELECT {bestand.heimat_sql('x')} AS h FROM mat_item x WHERE x.id = ?",
                                                     (iid,), one=True)["h"]
            assert bestand.heimat(bestand.artikel(gesperrt)) == satz and bestand.heimat(bestand.artikel(weg_ohne)) == sys_a["ausgesondert"]
            u = db.query("SELECT * FROM users WHERE id = ?", (fahrer_id,), one=True)
            rechte.sicht_verwerfen()
            assert rechte.ordner_filter("f.id", user=u) == \
                f"f.id IN (SELECT value FROM json_each('{json.dumps(sorted([fahrzeug, satz]))}'))"
            assert {r["id"] for r in db.query(f"SELECT f.id FROM mat_folder f WHERE {rechte.ordner_filter('f.id', user=u)}")} == {fahrzeug, satz}
        # Über die Schnittstelle: der gesperrte Artikel aus dem Fahrzeug ja (Heimat), der aus der Halle nicht.
        assert fahrer.get(f"/api/material/artikel/{gesperrt}").status_code == 200
        gleich_wie_unbekannt(fahrer.get(f"/api/material/artikel/{gesperrt_halle}"), fahrer.get("/api/material/artikel/999999"))
        assert qual.get(f"/api/material/artikel/{gesperrt}").status_code == 200
    print("Sicht bestanden.")


# --- requires_folder: 404 für Fremdes, 403 nur bei Sichtbarem, Kennungen aus der Anfrage ----------------------------

def test_requires_folder():
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, k, w = t.app, t.k, t.wart_a
        # Ohne Anmeldung 401, ohne Modulzugang 403 – vor der Frage, ob es den Gegenstand gibt.
        assert app.test_client().get(f"/api/material/ordner/{t.b}").status_code == 401
        r = k["nutzer"].get(f"/api/material/ordner/{t.b}")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        assert k["nutzer"].get("/api/material/ordner/999999").status_code == 403
        # Pfad: Ordner, Artikel, Prüfung, Durchgang aus B antworten wie Unbekanntes.
        for pfad, fremd in (("ordner", t.lager_b), ("artikel", t.art_b["id"]), ("pruefungen", t.entwurf_b),
                            ("durchgaenge", t.durchgang_b), ("artikel", f"{t.art_b['id']}/pruefungen")):
            gleich_wie_unbekannt(w.get(f"/api/material/{pfad}/{fremd}"),
                                 w.get(f"/api/material/{pfad}/{'999999/pruefungen' if '/' in str(fremd) else 999999}"))
        gleich_wie_unbekannt(w.put(f"/api/material/artikel/{t.art_b['id']}", json={"notes": "x"}),
                             w.put("/api/material/artikel/999999", json={"notes": "x"}))
        gleich_wie_unbekannt(w.post(f"/api/material/durchgaenge/{t.durchgang_b}/abschliessen", json={}),
                             w.post("/api/material/durchgaenge/999999/abschliessen", json={}))
        # Sichtbar, aber ohne das Recht: 403 mit Klartext.
        r = k["fuehrung"].put(f"/api/material/ordner/{t.lager_a}", json={"name": "x"})
        assert r.status_code == 403 and "Materialwarte" in r.json["error"], r.get_json()
        r = k["fuehrung"].post(f"/api/material/artikel/{t.art_a['id']}/pruefungen", json={})
        assert r.status_code == 403 and "Prüfer" in r.json["error"], r.get_json()

        # Kennungen im Inhalt (JSON): A als Zahl, Text und 7.0 → angelegt; B in jeder Form → wie „nicht vorhanden“.
        def anlegen(folder_id):
            return w.post("/api/material/artikel", json={"product_id": t.ids["hms"], "folder_id": folder_id})
        for form in (t.lager_a, str(t.lager_a), float(t.lager_a)):
            assert anlegen(form).status_code == 201, form
        unbekannt = anlegen(999999)
        for form in (t.lager_b, str(t.lager_b), float(t.lager_b), t.b, t.sys_b["gesperrt"]):
            gleich_wie_unbekannt(anlegen(form), unbekannt)
        for unsinn in ("abc", True, 7.5, [t.lager_a], {"id": t.lager_a}, "7 8"):
            r = anlegen(unsinn)
            assert r.status_code == 400 and "Ordner" in r.json["error"], (unsinn, r.get_json())
        # Leere Quelle: global → nur die Verwaltung (Gliederung auf oberster Ebene), sonst 403.
        r = w.post("/api/material/artikel", json={"product_id": t.ids["hms"]})
        assert r.status_code == 403, r.get_json()
        r = w.post("/api/material/ordner", json={"name": "OG Eigen", "kind": "gliederung"})
        assert r.status_code == 403 and "Plattform-Verwaltung" in r.json["error"], r.get_json()
        gleich_wie_unbekannt(w.post("/api/material/ordner", json={"name": "Darin", "parent_id": str(t.lager_b)}),
                             w.post("/api/material/ordner", json={"name": "Darin", "parent_id": 999999}))
        assert w.post("/api/material/ordner", json={"name": "Darin", "parent_id": t.lager_a}).status_code == 201
        # Adresse (arg:): Vorschlag mit fremdem Ordner wie unbekannt, ohne Ordner genügt der Modulzugang.
        gleich_wie_unbekannt(w.get(f"/api/material/artikel/vorschlag?product_id={t.ids['hms']}&folder_id={t.lager_b}"),
                             w.get(f"/api/material/artikel/vorschlag?product_id={t.ids['hms']}&folder_id=999999"))
        assert k["katalog"].get(f"/api/material/artikel/vorschlag?product_id={t.ids['hms']}").status_code == 200

        # eingabe: liest wie routes._eingabe – Formular bei Dateien (Meldung mit Foto), sonst JSON.
        def melden(c, folder_id=None, formular=False, modell="Testmodell"):
            felder = {"manufacturer": "Meldewerk", "model": modell}
            if folder_id is not None:
                felder["folder_id"] = folder_id
            if formular:
                felder = {k_: str(v) for k_, v in felder.items()}
                felder["fotos"] = (jpeg(), "etikett.jpg")
                return c.post("/api/material/meldungen", headers=H, content_type="multipart/form-data", data=felder)
            return c.post("/api/material/meldungen", headers=H, json=felder)
        assert melden(w, t.lager_a, modell="Testmodell Eins").status_code == 201
        assert melden(w, t.lager_a, formular=True, modell="Testmodell Zwei").status_code == 201
        gleich_wie_unbekannt(melden(w, t.lager_b, formular=True), melden(w, 999999, formular=True))
        gleich_wie_unbekannt(melden(w, float(t.lager_b)), melden(w, 999999))
        # Leer heißt hier „irgendwo verwalten“: der Materialwart ja, die Führungskraft nicht.
        assert melden(w, modell="Testmodell Drei").status_code == 201
        r = melden(k["fuehrung"], modell="Testmodell Vier")
        assert r.status_code == 403 and "Materialwarte" in r.json["error"], r.get_json()

        # Direkt: _bezug löst auf (Heimat bei Artikeln), requires_folder prüft seine Angaben beim Anlegen.
        from app.material.services import rechte
        with app.test_request_context(method="POST", json={"folder_id": str(t.lager_a)}):
            assert rechte._bezug("json:folder_id", {}).ordner_id == t.lager_a
            assert rechte._bezug("eingabe:folder_id", {}).ordner_id == t.lager_a
            assert rechte._bezug("form:folder_id", {}).ordner_id is None
        with app.test_request_context(method="POST", content_type="multipart/form-data",
                                      data={"folder_id": str(t.lager_a), "fotos": (io.BytesIO(b"x"), "x.jpg")}):
            assert rechte._bezug("eingabe:folder_id", {}).ordner_id == t.lager_a
            assert rechte._bezug("json:folder_id", {}).ordner_id is None
        with app.test_request_context(f"/?folder_id={t.lager_a}"):
            assert rechte._bezug("arg:folder_id", {}).ordner_id == t.lager_a
        with app.test_request_context(method="POST", json={"folder_id": "abc"}):
            try:
                rechte._bezug("json:folder_id", {})
                raise AssertionError("Unsinn angenommen")
            except rechte.Abgelehnt as exc:
                assert exc.code == 400
        sql(app, "UPDATE mat_item SET lock_state = 'gesperrt', origin_folder_id = folder_id, folder_id = ? WHERE id = ?",
            (t.sys_a["gesperrt"], t.art_a["id"]))
        with app.app_context():
            b = rechte._bezug("iid", {"iid": t.art_a["id"]})
            assert (b.art, b.ordner_id, b.artikel["id"]) == ("artikel", t.lager_a, t.art_a["id"])
        for falsch in (lambda: rechte.requires_folder("lesen", None), lambda: rechte.requires_folder("lesen", "json:"),
                       lambda: rechte.requires_folder("schauen", "fid"), lambda: rechte.requires_folder("lesen", "fid", "nie")):
            try:
                falsch()
                raise AssertionError("falsche Angabe angenommen")
            except ValueError:
                pass
    print("requires_folder bestanden.")


# --- 8.2/12: Ablauf ---------------------------------------------------------------------------------------------

def test_ablauf():
    """Eine Freigabe gilt bis einschließlich zu ihrem letzten Tag, gemessen am deutschen Kalendertag. Danach: 404 ohne
    anderes Recht, 403 mit Lesefreigabe; der Entwurf bleibt, der Materialwart gibt ihn frei. Wer nur noch abgelaufene
    Freigaben hat, liest, wann und bei wem."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(adm)
        a = neuer_artikel(w, ids["hms"], gid)["id"]
        h = _heute()
        ext, ext_id = neues_konto(app, "extern@example.org", name="Externer Prüfer", mat_pruefer=True,
                                  urkundennummer="1012-8001")
        freigeben(adm, gid, ext_id, "pruefen", bis=h)                           # der letzte Tag ist heute
        r = starten(ext, a)
        assert r.status_code == 201, r.get_json()
        pid = r.json["pruefung"]["id"]
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ?", ((h - timedelta(days=1)).isoformat(), ext_id))
        gleich_wie_unbekannt(ext.put(f"/api/material/pruefungen/{pid}", json={}), ext.put("/api/material/pruefungen/999999",
                                                                                          json={}))
        gleich_wie_unbekannt(ext.get(f"/api/material/artikel/{a}"), ext.get("/api/material/artikel/999999"))
        freigeben(adm, gid, ext_id, "lesen")
        r = ext.put(f"/api/material/pruefungen/{pid}", json={})
        assert r.status_code == 403 and "Prüffreigabe" in r.json["error"], r.get_json()
        assert ext.get(f"/api/material/pruefungen/{pid}").status_code == 200
        # Der Entwurf bleibt – der Materialwart gibt die Reservierung frei.
        assert zeilen(app, "SELECT 1 FROM mat_inspection WHERE id = ? AND completed_at IS NULL", (pid,))
        assert w.delete(f"/api/material/pruefungen/{pid}", headers=H).status_code == 200

        # Stichtag in deutscher Zeit: gueltig() fragt services.heute(), heute() die Uhr in Europe/Berlin.
        from app.material import services
        from app.material.services import rechte

        class Uhr(datetime):
            jetzt = None

            @classmethod
            def now(cls, tz=None):
                return cls.jetzt.astimezone(tz) if tz else cls.jetzt
        alt = services.datetime
        services.datetime = Uhr
        try:
            utc = timezone.utc
            for jetzt, letzter_tag, gilt in (
                    (datetime(2026, 12, 14, 22, 59, tzinfo=utc), "2026-12-14", True),    # 23:59 Uhr MEZ
                    (datetime(2026, 12, 14, 23, 0, tzinfo=utc), "2026-12-14", False),    # 0:00 Uhr MEZ des Folgetags
                    (datetime(2026, 10, 17, 21, 59, tzinfo=utc), "2026-10-17", True),    # 23:59 Uhr MESZ
                    (datetime(2026, 10, 17, 22, 30, tzinfo=utc), "2026-10-17", False),   # 0:30 Uhr MESZ – UTC noch am Vortag
                    (datetime(2026, 10, 17, 22, 30, tzinfo=utc), "2026-10-18", True)):
                Uhr.jetzt = jetzt
                assert rechte.gueltig(letzter_tag) is gilt, (jetzt, letzter_tag)
            assert rechte.gueltig(None) and rechte.gueltig("2026-01-01", tag=date(2026, 1, 1))
            assert not rechte.gueltig("2026-01-01", tag="2026-01-02")
        finally:
            services.datetime = alt

        # Nur noch eine abgelaufene Freigabe: kein Modulzugang – der Text nennt Ordner, Datum und wer verlängert.
        gestern = h - timedelta(days=1)
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ?", (gestern.isoformat(), k["fuehrung_id"]))
        r = k["fuehrung"].get("/api/material/start")
        assert r.status_code == 403, r.get_json()
        assert r.json["error"] == (f"Deine Freigabe für „OG Musterstadt“ ist am {gestern.strftime('%d.%m.%Y')} abgelaufen. "
                                   "Verlängern kann sie: wart."), r.get_json()
        assert k["fuehrung"].get("/api/me").json["user"]["rechte"]["material"] == 0
        assert k["fuehrung"].get("/material").status_code == 403
        # Länger als ein Jahr her: der allgemeine Hinweis.
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ?",
            ((h - timedelta(days=400)).isoformat(), k["fuehrung_id"]))
        assert "Materialwart deiner Gliederung" in k["fuehrung"].get("/api/material/start").json["error"]
    print("Ablauf bestanden.")


# --- 8.2/13: Verwalter und Verwaltung prüfen nur mit Prüffreigabe --------------------------------------------------

def test_pruefen_nur_mit_prueffreigabe():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(adm)
        a1, a2 = (neuer_artikel(w, ids["hms"], gid)["id"] for _ in range(2))
        # Materialwart mit Häkchen und Urkunde, aber nur verwalten: kein Prüfen – mit Hinweis, wo es die Freigabe gibt.
        assert adm.put(f"/api/admin/users/{k['wart_id']}", json={"mat_pruefer": True, "urkundennummer": "1012-6001"}).status_code == 200
        assert w.get("/api/material/start").json["darf"]["qualifiziert"]
        r = starten(w, a1)
        assert r.status_code == 403 and "Prüffreigabe" in r.json["error"] and "Freigaben" in r.json["error"], r.get_json()
        r = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Test"})
        assert r.status_code == 201, r.get_json()                            # eröffnen darf er als Verwalter
        freigeben(adm, gid, k["wart_id"], "pruefen")
        assert starten(w, a1).status_code == 201
        # Die Verwaltung genauso: Häkchen und Urkunde, ohne Prüffreigabe 403, mit 201.
        adm_id = adm.get("/api/me").json["user"]["id"]
        assert adm.put(f"/api/admin/users/{adm_id}", json={"mat_pruefer": True, "urkundennummer": "1012-6002"}).status_code == 200
        d = adm.get("/api/material/start").json["darf"]
        assert d["alles"] and d["qualifiziert"] and not d["pruefen"], d
        r = starten(adm, a2)
        assert r.status_code == 403 and "Prüffreigabe" in r.json["error"], r.get_json()
        freigeben(adm, gid, adm_id, "pruefen")
        assert adm.get("/api/material/start").json["darf"]["pruefen"]
        assert starten(adm, a2).status_code == 201
    print("Prüfen nur mit Prüffreigabe bestanden.")


# --- 8.2/14: Abfragezahl ----------------------------------------------------------------------------------------

def test_abfragezahl():
    """Die Materialstufe fragt jede Seite der Plattform (Kopfleiste) – höchstens zwei Abfragen, ohne Ordnerbaum, auch
    bei 300 Ordnern. Im Modul selbst rechnet eine Anfrage die Sicht genau einmal."""
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        gid, _ = gliederung(k["adm"])
        with app.app_context():
            from app import db
            with db.transaction():
                for n in range(300):
                    db.execute("INSERT INTO mat_folder (parent_id, name, kind, created_at, updated_at) VALUES (?,?,?,?,?)",
                               (gid, f"Testordner {n:03d}", "standort", db.now(), db.now()))
        abfragen = []
        alt = db_mod.get_db

        def mit_zaehler():
            conn = alt()
            conn.set_trace_callback(abfragen.append)
            return conn

        def zaehlen(c, url):
            del abfragen[:]
            db_mod.get_db = mit_zaehler
            try:
                r = c.get(url)
            finally:
                db_mod.get_db = alt
            assert r.status_code == 200 and abfragen, (url, r.status_code)
            return ([q for q in abfragen if "mat_folder_grant" in q],
                    [q for q in abfragen if re.search(r"FROM mat_folder\b(?!_)", q)])
        freigaben, baum = zaehlen(k["fuehrung"], "/wiki")
        assert 1 <= len(freigaben) <= 2 and not baum, (freigaben, baum)
        assert 'href="/material"' in k["fuehrung"].get("/wiki").get_data(as_text=True)
        freigaben, baum = zaehlen(k["wart"], "/wiki")
        assert len(freigaben) <= 2 and not baum, (freigaben, baum)
        # Im Modul: eine Abfrage der eigenen Freigaben für die Sicht, eine für den Baum – trotz Decorator, darf_alles und
        # Zählung in derselben Anfrage.
        freigaben, baum = zaehlen(k["fuehrung"], f"/api/material/ordner/{gid}")
        assert len([q for q in freigaben if "ORDER BY id" in q]) == 1, freigaben
        assert len([q for q in baum if "SELECT id, parent_id, kind, system_kind FROM mat_folder" in q]) == 1, baum
    print("Abfragezahl bestanden.")


# --- Gemeinsamer Unterbau: Kontoverweis, wählbare Konten, Verwalter, Suchprotokoll, Angebot der globalen Suche -------

def test_unterbau():
    """Was die Pakete B, C und D vom Rechtekern übernehmen: journal.konto_ref/konto_name (ohne E-Mail),
    rechte.waehlbares_konto (eine Antwort für inaktiv, ohne Namen, nicht vorhanden), verwalter_von, darf_meldung,
    globalprotokoll (Bremse, Protokoll, Frist) und globalsuche.angebot."""
    from flask import g
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        gid, _ = gliederung(adm)
        lager = ordner_neu(k["wart"], gid, "Lager")
        _, gast_id = neues_konto(app, "gast@example.org", name="Gast Verwalter")
        freigeben(adm, lager, gast_id, "verwalten", bis=_heute() + timedelta(days=30))
        _, weg_id = neues_konto(app, "inaktiv@example.org")
        adm.put(f"/api/admin/users/{weg_id}", json={"active": False})
        _, leer_id = neues_konto(app, "ohne_namen@example.org", name="")
        from app.material.services import globalprotokoll, globalsuche, journal, rechte
        with app.test_request_context():
            from app import db
            # Kontoverweis: entsteht beim ersten Gebrauch, bleibt gleich, führt zum Namen – nie zur E-Mail.
            sql_ref = "SELECT mat_ref FROM users WHERE id = ?"
            db.execute("UPDATE users SET mat_ref = NULL WHERE id = ?", (gast_id,))
            ref = journal.konto_ref(gast_id)
            assert re.fullmatch(r"[0-9a-f]{32}", ref["ref"]) and journal.konto_ref(gast_id) == ref
            assert db.query(sql_ref, (gast_id,), one=True)["mat_ref"] == ref["ref"]
            assert journal.konto_name(ref["ref"]) == "Gast Verwalter"
            assert journal.konto_name(journal.konto_ref(leer_id)["ref"]) == "(ohne Namen)"
            assert journal.konto_name("0" * 32) == journal.konto_name(None) == "(gelöschtes Konto)"
            assert journal.konto_ref(999999) == {"ref": None}
            # Handelnde ohne Namen stehen nicht mit der E-Mail im Journal.
            g.user = db.query("SELECT * FROM users WHERE id = ?", (leer_id,), one=True)
            journal.eintragen("folder", gid, "geaendert", None, {"name": "Test"})
            e = db.query("SELECT user_name FROM mat_audit ORDER BY id DESC LIMIT 1", one=True)
            assert e["user_name"] == "(Konto ohne Namen)"
            from app.material.services import akteur
            assert akteur() == (leer_id, "(Konto ohne Namen)")
            # Lesen ohne bestimmte Aktionen.
            assert any(x["action"] == "geaendert" for x in journal.lesen([("folder", gid)]))
            assert not any(x["action"] == "geaendert" for x in journal.lesen([("folder", gid)], ohne=("geaendert",)))
            # Wählbare Konten: aktiv und mit Namen – sonst dieselbe 404.
            assert rechte.waehlbares_konto(str(gast_id))["id"] == gast_id
            antworten = set()
            for uid in (weg_id, leer_id, 999999):
                try:
                    rechte.waehlbares_konto(uid)
                    raise AssertionError(uid)
                except rechte.Abgelehnt as exc:
                    antworten.add((exc.code, str(exc)))
            assert antworten == {(404, "Konto nicht gefunden.")}, antworten
            # Verwalter eines Ordners: an ihm oder darüber, aktiv, ohne die Verwaltung – mit wirksamem Ende.
            v = {x["name"]: x["ende"] for x in rechte.verwalter_von(lager)}
            assert v == {"wart": None, "Gast Verwalter": (_heute() + timedelta(days=30)).isoformat()}, v
            assert [x["name"] for x in rechte.verwalter_von(gid)] == ["wart"]
            # Meldungen sieht der Melder, wer den Ordner sehen darf, Katalogpfleger und die Verwaltung.
            fuehrung = db.query("SELECT * FROM users WHERE id = ?", (k["fuehrung_id"],), one=True)
            nutzer = db.query("SELECT * FROM users WHERE id = ?", (k["nutzer_id"],), one=True)
            assert rechte.darf_meldung({"created_by": None, "folder_id": lager}, fuehrung)
            assert not rechte.darf_meldung({"created_by": None, "folder_id": None}, fuehrung)
            assert rechte.darf_meldung({"created_by": k["nutzer_id"], "folder_id": None}, nutzer)
            assert not rechte.darf_meldung({"created_by": None, "folder_id": lager}, nutzer)
            # Suchprotokoll: zehn in der Viertelstunde, die elfte 429; Zeilen mit Name, älter als ein Jahr fliegen raus.
            g.user = fuehrung
            for _ in range(globalprotokoll.GRENZE):
                globalprotokoll.bremse(fuehrung["id"])
            try:
                globalprotokoll.bremse(fuehrung["id"])
                raise AssertionError("Bremse greift nicht")
            except rechte.Abgelehnt as exc:
                assert exc.code == 429 and str(exc) == globalprotokoll.ZU_VIELE
            globalprotokoll.bremse(k["wart_id"])                                 # je Konto gezählt
            zid = globalprotokoll.eintragen("suche", "TEST-0815", [])
            db.execute("INSERT INTO mat_global_search (user_id, user_name, art, anfrage, treffer, created_at) "
                       "VALUES (NULL, 'Alt', 'qr', 'M-000001', 0, '2020-01-01T00:00:00+00:00')")
            liste = globalprotokoll.liste()
            assert [(x["id"], x["name"], x["art"], x["anfrage"], x["treffer"]) for x in liste["eintraege"]] == \
                [(zid, "fuehrung", "suche", "TEST-0815", 0)] and liste["gesamt"] == 1, liste
            db.execute("INSERT INTO mat_global_search (user_id, user_name, art, anfrage, treffer, created_at) "
                       "VALUES (NULL, 'Alt', 'qr', 'M-000001', 0, '2020-01-01T00:00:00+00:00')")
        make_app(tmp)                                                             # Neustart räumt auf
        assert zeilen(app, "SELECT user_name FROM mat_global_search") == [{"user_name": "fuehrung"}]
        # Angebot der globalen Suche: 4–80 Zeichen, keine vergebene Nummer, kein exakter Treffer im eigenen Bereich.
        assert globalsuche.normalform("  AB  12 \n 34 ") == "AB 12 34"
        assert globalsuche.angebot("AB-1234", 3, False) and not globalsuche.angebot("AB-1234", 3, True)
        for q in ("AB1", "x" * 81, "STR-000123", "m-000123", "M-12345"):
            assert not globalsuche.angebot(q, 0, False), q
        alt = globalsuche.ANGEBOT
        try:
            globalsuche.ANGEBOT = "ohne_treffer"
            assert globalsuche.angebot("AB-1234", 0, False) and not globalsuche.angebot("AB-1234", 2, False)
        finally:
            globalsuche.ANGEBOT = alt
        assert alt in globalsuche.ANGEBOTE and globalsuche.STECKBRIEF_MIT_SPERRE is False
        assert len(globalsuche.FELDER) == 14 and "inventory_no" in globalsuche.FELDER and "id" not in globalsuche.FELDER
    print("Unterbau bestanden.")


if __name__ == "__main__":
    test_migration_7_8()
    test_sicht()
    test_requires_folder()
    test_ablauf()
    test_pruefen_nur_mit_prueffreigabe()
    test_abfragezahl()
    test_unterbau()
