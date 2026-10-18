"""Trennung je Gliederung – Freigaben je Ordner (Phase 2 · Lieferung 1):  python tests/test_material_trennung.py
oder  pytest tests/test_material_trennung.py

Die Kerntests des Rechtekerns nach dem Bauentwurf 8.2: Migration 7 → 8 (Nr. 1), Ablauf einer Freigabe mit dem
deutschen Kalendertag (Nr. 12), Prüfen nur mit Prüffreigabe – auch für Verwalter und Verwaltung (Nr. 13), Abfragezahl
der Materialstufe (Nr. 14) –, dazu Einheitstests für die Sicht (Vererbung, Pfad-Knoten, teilweise sichtbare
Systemordner, Prüffreigabe ohne Qualifikation, Heimat im Filter, mehrere Freigaben und ihr Ende) und für
requires_folder (404 für Fremdes wie für Unbekanntes, 403 nur bei sichtbarem Gegenstand, Kennungen als „7“ und 7.0,
Formular und JSON).

Paket A1R ergänzt die Durchsetzung in Diensten und Inhalten (8.2/2–11): nichts aus B in irgendeiner Antwort an A
(Pfad und Inhalt der Anfrage, tabellengetrieben gegen url_map), Vererbung und Heimat, Verschieben und Durchgänge, eine
Heimat beim Gliederungswechsel, kein Abziehen, Produktjournal, Dubletten, Prüfsicht. Was erst mit einem anderen Paket
grün werden kann, steht in WARTET_AUF.

Weitere Pakete hängen ihre Tests unten an (vor dem Block __main__) und bauen mit zwei_gliederungen() bzw.
trennung_aufbau() auf: zwei Gliederungen nebeneinander, jede mit eigenem Verwalter. Alle Namen, Hersteller und Nummern
hier sind erfunden und nur für den Test da."""
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _flach, _heute, festschreiben, freigeben, gliederung, jpeg, katalog_grund,  # noqa: E402
                           make_app, neuer_artikel, neues_konto, pdf_seiten, protokoll_zeile, pruef_formulare, starten,
                           umgebung, unterschreiben, unterschrift_hinterlegen)
from test_material_ueberblick import (MEHRDEUTIG, MULTIPART, SCHREIBEN, _stand, _url, ohne_post,  # noqa: E402
                                      ordner_neu, sperren)


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


# --- Aufbau für 8.2/2–11: B mit allem, was durchsickern könnte --------------------------------------------------------

def _foto(c, url, name="test.jpg"):
    r = c.post(url, data={"file": (jpeg(), name)}, headers=H, content_type="multipart/form-data")
    assert r.status_code in (200, 201), (url, r.get_json())
    return r.json


def trennung_aufbau(tmp):
    """zwei_gliederungen und dazu in B: ein Ordnerfoto, die Prüfung der Prüferin im Durchgang – mit Befundfoto und
    Anhang festgeschrieben –, der abgeschlossene Durchgang mit Sammelprotokoll, ein gesperrter und ein ausgesonderter
    Artikel, eine Meldung mit Foto und eine Zuordnung an eine Person aus B (direkt in der Tabelle – die Route baut Paket
    D). In A ein abgeschlossener Durchgang mit festgeschriebener Prüfung (CSV und ZIP von A haben Inhalt), im Katalog
    ein Produktbild. Mails der Meldung verwirft der Aufrufer (ohne_post).

    Liefert (t, b): t aus zwei_gliederungen, b mit den Kennungen und Adressen aus B und b.merkmale – Zeichenketten, die in
    keiner Antwort an wart_a stehen dürfen (Inventar- und Seriennummern, Ordner- und Kontonamen, Protokoll-IDs,
    Dateinamen, Urkundennummer, Meldungstext)."""
    t = zwei_gliederungen(tmp)
    app, ids = t.app, t.ids
    b = SimpleNamespace()
    o = _foto(t.wart_b, f"/api/material/ordner/{t.lager_b}/foto", "lager.jpg")["ordner"]
    b.ordnerfoto = [o["foto"], o["vorschau"], o["original"]]
    pr = t.pruefer_b.get(f"/api/material/pruefungen/{t.entwurf_b}").json["pruefung"]
    b.punkt = pr["punkte"][0]["id"]
    f = _foto(t.pruefer_b, f"/api/material/pruefungen/{t.entwurf_b}/punkte/{b.punkt}/foto", "befund.jpg")["punkt"]["foto"]
    b.befundfoto = [f["web"], f["vorschau"], f["original"]]
    r = t.pruefer_b.post(f"/api/material/pruefungen/{t.entwurf_b}/anhaenge", headers=H, content_type="multipart/form-data",
                         data={"file": [(jpeg(), "scan.jpg")], "art": "foto", "titel": "Testscan", "im_protokoll": "nein"})
    assert r.status_code == 201, r.get_json()
    b.anhang_id, b.anhang = r.json["anhang"]["id"], r.json["anhang"]["datei"]
    unterschreiben(t.pruefer_b)
    r = festschreiben(t.pruefer_b, t.entwurf_b, ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()
    r = t.wart_b.post(f"/api/material/durchgaenge/{t.durchgang_b}/abschliessen", json={})
    assert r.status_code == 200, r.get_json()
    b.gesperrt = neuer_artikel(t.wart_b, ids["hms"], t.lager_b, serial_no="TEST-B-0002")
    sperren(t.pruefer_b, b.gesperrt["id"])
    b.weg = neuer_artikel(t.wart_b, ids["hms"], t.lager_b, serial_no="TEST-B-0003")
    sperren(t.pruefer_b, b.weg["id"])
    unterschrift_hinterlegen(app, t.wart_b_id)
    r = t.wart_b.post(f"/api/material/artikel/{b.weg['id']}/aussondern", json={"grund": "irreparabel"})
    assert r.status_code == 200, r.get_json()
    b.aussonderung = r.json["aussonderung"]
    r = t.wart_b.post("/api/material/meldungen", headers=H, content_type="multipart/form-data",
                      data={"manufacturer": "Meldewerk", "model": "Meldemodell Nachbarstadt", "note": "Notiz Nachbarstadt",
                            "folder_id": str(t.lager_b), "fotos": (jpeg(), "etikett.jpg")})
    assert r.status_code == 201, r.get_json()
    b.meldung = r.json["meldung"]["id"]
    m = r.json["meldung"]["fotos"][0]
    b.meldungsfoto = [m["web"], m["vorschau"], m["original"]]
    _, b.person_id = neues_konto(app, "person_b@example.org", name="Person Nachbarstadt")
    sql(app, "UPDATE mat_item SET assigned_user_id = ? WHERE id = ?", (b.person_id, t.art_b["id"]))
    r = t.wart_a.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang Musterstadt"})
    assert r.status_code == 201, r.get_json()
    b.durchgang_a = r.json["durchgang"]["id"]
    pid = starten(t.k["pruefer"], t.art_a["id"], durchgang_id=b.durchgang_a).json["pruefung"]["id"]
    assert festschreiben(t.k["pruefer"], pid, ergebnis="einsatzbereit").status_code == 200
    assert t.wart_a.post(f"/api/material/durchgaenge/{b.durchgang_a}/abschliessen", json={}).status_code == 200
    b.produktbild = _foto(t.k["katalog"], f"/api/material/produkte/{ids['hms']}/bild", "hms.jpg")["produkt"]["bild"]
    b.freigabe = zeilen(app, "SELECT id FROM mat_folder_grant WHERE user_id = ? AND folder_id = ?",
                        (t.wart_b_id, t.b))[0]["id"]
    b.artikel = [t.art_b["id"], b.gesperrt["id"], b.weg["id"]]
    artikel = {r["id"]: r for r in zeilen(app, "SELECT id, inventory_no, qr_token FROM mat_item")}
    b.token = artikel[t.art_b["id"]]["qr_token"]
    protokolle = [r["protocol_id"] for r in zeilen(
        app, "SELECT protocol_id FROM mat_inspection WHERE protocol_id IS NOT NULL AND item_id IN (?, ?, ?)", b.artikel)]
    protokolle.append(zeilen(app, "SELECT protocol_id FROM mat_round WHERE id = ?", (t.durchgang_b,))[0]["protocol_id"])
    assert len(protokolle) == 3 and all(protokolle), protokolle
    dateien = [os.path.splitext(u.rsplit("/", 1)[1])[0] for u in b.ordnerfoto + b.befundfoto + b.meldungsfoto + [b.anhang]]
    b.merkmale = {"Nachbarstadt", "TEST-B-", "1012-9001", "wart_b@", "pruefer_b@", "person_b@", *protokolle, *dateien,
                  *(artikel[i]["inventory_no"] for i in b.artikel)}
    b.ordner = {r["id"] for r in zeilen(app, "WITH RECURSIVE z(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f "
                                             "JOIN z ON f.parent_id = z.id) SELECT id FROM z", (t.b,))}
    return t, b


def _text(daten):
    return daten if isinstance(daten, str) else daten.decode("utf-8", "replace")


def ohne_merkmale(b, wo, daten):
    """Kein Merkmal aus B in dieser Antwort (Text, JSON, CSV)."""
    text = _text(daten)
    for m in b.merkmale:
        assert m not in text, (wo, m, text[max(0, text.find(m) - 200):text.find(m) + 200])


_PLATZHALTER = re.compile(r"<(?:[^<>:]+:)?(\w+)>")
# Platzhalter, die in einer Route einen Gegenstand aus dem Bestand meinen (bei pid, fid, rid zählt der Abschnitt davor,
# wie in test_material_ueberblick._url): Mit einer Kennung aus B antwortet die Route an wart_a wie für Unbekanntes.
BESTAND_PLATZHALTER = {"iid", "mid", "aid", "token", "gid", ("pruefungen", "pid"), ("pruefung", "pid"),
                       ("punkte", "rid"), ("ordner", "fid"), ("export", "fid"), ("durchgaenge", "rid"),
                       ("durchgang", "rid")}
# Was erst ein anderes Paket filtert (Bauentwurf 9.1) – geprüft in test_nichts_aus_b_paket_d.
LESEN_ANDERES_PAKET = {"material_api.meldung_lesen": "D"}


def _platzhalter(regel):
    out, teile = [], regel.rule.split("/")
    for n, teil in enumerate(teile):
        for name in _PLATZHALTER.findall(teil):
            out.append(name if name not in MEHRDEUTIG else (teile[n - 1], name))
    return out


# --- 8.2/2: Nutzer A sieht Gliederung B nirgends ----------------------------------------------------------------------

def test_nichts_aus_b():
    """Für jede Route der Material-Blueprints mit Kennungen aus B: lesen 404 wie für Unbekanntes (die Seite „fremd“ nach
    einem QR-Scan ohne Artikeldaten), schreiben 404 oder 403 – nie 2xx, danach ist in keiner Tabelle etwas anders. In
    keiner Antwort an wart_a steht ein Merkmal aus B: Listen, Suche, Zählungen, Katalog (Spalte Bestand), Produktseite,
    Durchgänge, CSV und ZIP von A, die Seiten. Medien aus B antworten 404, das Produktbild 200."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t, b = trennung_aufbau(tmp)
        app, w, ids = t.app, t.wart_a, t.ids
        form = zeilen(app, "SELECT id FROM mat_form ORDER BY id LIMIT 1")[0]["id"]
        kennungen = {"iid": t.art_b["id"], "mid": b.meldung, "aid": b.anhang_id, "token": b.token, "gid": b.freigabe,
                     "kid": ids["karabiner"], "did": 999999, "ruid": 999999, "filename": "material.js",
                     "art": "web", "dateiname": "x.jpg",
                     ("produkte", "pid"): ids["hms"], ("produkt", "pid"): ids["hms"],
                     ("pruefungen", "pid"): t.entwurf_b, ("pruefung", "pid"): t.entwurf_b, ("punkte", "rid"): b.punkt,
                     ("ordner", "fid"): t.lager_b, ("export", "fid"): t.lager_b, ("formulare", "fid"): form,
                     ("formular", "fid"): form, ("durchgaenge", "rid"): t.durchgang_b, ("durchgang", "rid"): t.durchgang_b}
        regeln = [r for r in app.url_map.iter_rules() if r.endpoint.split(".")[0] in ("material", "material_api")
                  and r.endpoint != "material.medien"]
        vorher = _stand(app)
        gelesen = geschrieben = 0
        for regel in regeln:
            fremd = any(p in BESTAND_PLATZHALTER for p in _platzhalter(regel))
            url = _url(regel, kennungen)
            if "GET" in regel.methods and regel.endpoint not in LESEN_ANDERES_PAKET:
                r = w.get(url)
                assert r.status_code < 500, (url, r.status_code)
                if fremd:
                    soll = 200 if regel.endpoint == "material.qr_ziel" else 404
                    assert r.status_code == soll, (url, r.status_code, r.data[:300])
                ohne_merkmale(b, url, r.data)
                gelesen += 1
            for methode in sorted(regel.methods & SCHREIBEN):
                if not fremd:
                    continue                    # Kennungen im Inhalt: test_felder_im_inhalt
                if regel.endpoint in MULTIPART:
                    r = w.open(url, method=methode, headers=H, content_type="multipart/form-data",
                               data={"file": (jpeg(), "x.jpg"), "titel": "x"})
                else:
                    r = w.open(url, method=methode, headers=H, json={})
                assert r.status_code in (403, 404), (methode, url, r.status_code, r.get_json(silent=True))
                ohne_merkmale(b, f"{methode} {url}", r.data)
                geschrieben += 1
        assert gelesen >= 40 and geschrieben >= 25, (gelesen, geschrieben)          # Stand Phase 2 · L1: 47 und 29
        assert _stand(app) == vorher, "Mit Kennungen aus B hat sich etwas geändert."

        # Listen, Suche, Zählungen, Katalog: nur A.
        inventar_b = zeilen(app, "SELECT inventory_no FROM mat_item WHERE id = ?", (t.art_b["id"],))[0]["inventory_no"]
        for url in ("/api/material/start", "/api/material/ordner", "/api/material/suche?q=TEST-B-0001",
                    f"/api/material/suche?q={inventar_b}", "/api/material/suche?q=TEST", "/api/material/faellig",
                    "/api/material/faellig?status=gesperrt", "/api/material/faellig?status=ausgesondert",
                    "/api/material/entwuerfe", "/api/material/durchgaenge", "/api/material/rueckrufe",
                    "/api/material/produkte?q=HMS", f"/api/material/produkte/{ids['hms']}", "/api/material/meldungen",
                    f"/api/material/ordner/{t.a}", f"/api/material/ordner/{t.lager_a}", f"/api/material/ordner/{t.sys_a['gesperrt']}",
                    f"/api/material/artikel/{t.art_a['id']}", f"/api/material/durchgaenge/{b.durchgang_a}",
                    f"/material/export/{t.a}.csv", f"/material/export/{t.lager_a}.csv", "/material", "/material/bestand"):
            r = w.get(url)
            assert r.status_code == 200, (url, r.status_code)
            ohne_merkmale(b, url, r.data)
        assert not {o["id"] for o in w.get("/api/material/ordner").json["ordner"]} & b.ordner
        # Gegenprobe: An B gehen diese Merkmale sehr wohl – die Prüfung oben sucht nach dem Richtigen.
        text_b = "".join(t.wart_b.get(u).get_data(as_text=True) for u in (
            "/api/material/ordner", f"/api/material/ordner/{t.lager_b}", f"/api/material/artikel/{t.art_b['id']}",
            f"/api/material/durchgaenge/{t.durchgang_b}"))
        assert "Nachbarstadt" in text_b and "TEST-B-" in text_b and inventar_b in text_b and "1012-9001" in text_b
        s = w.get("/api/material/suche?q=TEST-B-0001").json
        assert s["gesamt"] == 0 and s["treffer"] == [] and s["eindeutig"] is None and s["exakt_lokal"] is False, s
        assert s["global_angebot"] is True, s
        assert w.get(f"/api/material/suche?q={inventar_b}").json["gesamt"] == 0
        assert w.get("/api/material/start").json["bestand"] == 1
        p = w.get(f"/api/material/produkte/{ids['hms']}").json["produkt"]
        assert (p["bestand"], p["artikel_gesamt"], p["loeschbar"]) == (1, 1, False), p
        assert [x["bestand"] for x in w.get("/api/material/produkte?q=HMS").json["produkte"]] == [1]
        assert t.wart_b.get(f"/api/material/produkte/{ids['hms']}").json["produkt"]["bestand"] == 2   # art_b, gesperrt
        # Das ZIP von A: Verzeichnis und Dateinamen ohne B.
        r = w.get(f"/material/export/{t.a}-protokolle.zip")
        assert r.status_code == 200, r.status_code
        z = zipfile.ZipFile(io.BytesIO(r.data))
        ohne_merkmale(b, "ZIP von A", "\n".join(z.namelist()) + _text(z.read("Verzeichnis.csv")))
        assert len(z.namelist()) == 3                          # Verzeichnis, die Prüfung und das Sammelprotokoll von A
        # Die Suchseite leitet nicht zu Fremdem weiter; die Artikelseite aus B ist 404 ohne Banner; der QR-Scan zeigt
        # nur „fremd“.
        assert w.get("/material/suche?q=TEST-B-0001").status_code == 200
        r = w.get(f"/material/artikel/{b.gesperrt['id']}")
        assert r.status_code == 404 and "mat-banner" not in r.get_data(as_text=True)
        ohne_merkmale(b, "Artikelseite B", r.data)
        r = w.get(f"/m/{b.token}")
        assert r.status_code == 200 and 'data-ansicht="fremd"' in r.get_data(as_text=True), r.status_code
        ohne_merkmale(b, "QR fremd", r.data)
        assert "mat-banner" not in r.get_data(as_text=True)
        r = t.wart_b.get(f"/m/{b.token}")
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/material/artikel/{t.art_b['id']}")

        # Medien je Datei: aus B 404 (für B selbst 200), das Produktbild für alle mit Modulzugang.
        for url in b.ordnerfoto + b.befundfoto + b.meldungsfoto + [b.anhang]:
            assert w.get(url).status_code == 404, url
        for url in b.ordnerfoto:
            assert t.wart_b.get(url).status_code == 200, url
        for url in b.befundfoto + [b.anhang]:
            assert t.pruefer_b.get(url).status_code == 200, url
        assert t.wart_b.get(b.meldungsfoto[0]).status_code == 200                    # der Melder
        assert t.k["katalog"].get(b.meldungsfoto[0]).status_code == 200              # die Katalogpflege
        assert w.get(b.produktbild).status_code == 200 and t.k["fuehrung"].get(b.produktbild).status_code == 200
        assert w.get("/media/material/web/gibtesnicht.jpg").status_code == 404
        assert w.get("/media/material/heimlich/x.jpg").status_code == 404
        assert t.k["nutzer"].get(b.produktbild).status_code == 403
    print("Nichts aus B bestanden.")


# --- 8.2/3: Kennungen im Inhalt der Anfrage ---------------------------------------------------------------------------

# Felder im Inhalt einer Anfrage, die einen Gegenstand meinen: (Methode, Regel, Feld, Format). Gegen url_map
# abgeglichen – eine Route, deren requires_folder-Quelle ein Feld der Anfrage ist (json:, form:, eingabe:), braucht hier
# eine Zeile. Dazu die Felder der Pakete B und D, die ihren Bezug im Dienst lesen: ids beim Zuordnen und user_id bei
# Zuordnung und Freigabe. Ein Konto aus B ist dort ausdrücklich erlaubt (1.6 Nr. 2, 6.1) – für user_id zählt, dass
# deaktiviert, ohne Namen und nicht vorhanden gleich antworten (1.6 Nr. 12).
FELDER_IM_INHALT = (
    ("POST", "/api/material/artikel/<int:iid>/pruefungen", "durchgang_id", "json"),
    ("POST", "/api/material/durchgaenge/<int:rid>/ausnehmen", "item_id", "json"),
    ("POST", "/api/material/durchgaenge/<int:rid>/einbeziehen", "item_id", "json"),
    ("POST", "/api/material/meldungen", "folder_id", "multipart"),
    ("POST", "/api/material/meldungen", "folder_id", "json"),
    ("POST", "/api/material/durchgaenge", "folder_id", "json"),
    ("POST", "/api/material/artikel", "folder_id", "json"),
    ("POST", "/api/material/artikel/verschieben", "folder_id", "json"),
    ("POST", "/api/material/ordner", "parent_id", "json"),
    ("POST", "/api/material/ordner/<int:fid>/verschieben", "parent_id", "json"),
    ("POST", "/api/material/artikel/verschieben", "ids", "json"),
    ("POST", "/api/material/artikel/zuordnen", "ids", "json"),
    ("PUT", "/api/material/artikel/<int:iid>/zuordnung", "user_id", "json"),
    ("POST", "/api/material/artikel/zuordnen", "user_id", "json"),
    ("POST", "/api/material/ordner/<int:fid>/freigaben", "user_id", "json"),
)


def test_felder_im_inhalt():
    """Jedes Feld × {A (Kontrolle: Erfolg), B, B als Text „7“, B als 7.0, nicht vorhanden}: Die B-Formen sind nie 2xx
    und antworten mit Status und Text genau wie dieselbe Form von „nicht vorhanden“. Für user_id stehen ein
    deaktiviertes Konto und eines ohne Namen an der Stelle von B; die Kontrolle ist ein Konto aus B. Die Tabelle deckt
    jede Route ab, deren Bezug aus dem Inhalt kommt."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w, p, ids = t.app, t.wart_a, t.k["pruefer"], t.ids
        a2, a3, a4 = (neuer_artikel(w, ids["hms"], t.lager_a)["id"] for _ in range(3))
        halle = ordner_neu(w, t.a, "Halle Musterstadt")
        neuer_artikel(w, ids["hms"], halle)
        fach = ordner_neu(w, t.lager_a, "Fach Musterstadt")
        r = w.post("/api/material/durchgaenge", json={"folder_id": t.lager_a, "titel": "Testdurchgang Musterstadt"})
        assert r.status_code == 201, r.get_json()
        r_a = r.json["durchgang"]["id"]
        nummer = iter(range(1, 10000))

        def melden(fid, multipart):
            felder = {"manufacturer": "Meldewerk", "model": f"Testmodell {next(nummer)}", "folder_id": fid}
            if multipart:
                felder = {k_: str(v) for k_, v in felder.items()}
                felder["fotos"] = (jpeg(), "etikett.jpg")
                return w.post("/api/material/meldungen", headers=H, content_type="multipart/form-data", data=felder)
            return w.post("/api/material/meldungen", headers=H, json=felder)

        # In dieser Reihenfolge: Die Kontrollen ändern den Bestand (Ausnehmen vor Einbeziehen, Verschieben zuletzt).
        faelle = [
            (FELDER_IM_INHALT[0], lambda v: p.post(f"/api/material/artikel/{t.art_a['id']}/pruefungen",
                                                   json={"durchgang_id": v}), r_a, 201, t.durchgang_b),
            (FELDER_IM_INHALT[1], lambda v: w.post(f"/api/material/durchgaenge/{r_a}/ausnehmen",
                                                   json={"item_id": v, "grund": "Testgrund"}), a2, 200, t.art_b["id"]),
            (FELDER_IM_INHALT[2], lambda v: w.post(f"/api/material/durchgaenge/{r_a}/einbeziehen", json={"item_id": v}),
             a2, 200, t.art_b["id"]),
            (FELDER_IM_INHALT[3], lambda v: melden(v, True), t.lager_a, 201, t.lager_b),
            (FELDER_IM_INHALT[4], lambda v: melden(v, False), t.lager_a, 201, t.lager_b),
            (FELDER_IM_INHALT[5], lambda v: w.post("/api/material/durchgaenge", json={"folder_id": v, "titel": "Test"}),
             halle, 201, t.lager_b),
            (FELDER_IM_INHALT[6], lambda v: w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": v}),
             t.lager_a, 201, t.lager_b),
            (FELDER_IM_INHALT[7], lambda v: w.post("/api/material/artikel/verschieben", json={"ids": [a3], "folder_id": v}),
             fach, 200, t.lager_b),
            (FELDER_IM_INHALT[8], lambda v: w.post("/api/material/ordner", json={"name": f"Testordner {next(nummer)}",
                                                                                "parent_id": v}), t.lager_a, 201, t.lager_b),
            (FELDER_IM_INHALT[9], lambda v: w.post(f"/api/material/ordner/{fach}/verschieben", json={"parent_id": v}),
             halle, 200, t.lager_b),
            (FELDER_IM_INHALT[10], lambda v: w.post("/api/material/artikel/verschieben", json={"ids": [v], "folder_id": halle}),
             a4, 200, t.art_b["id"]),
            (FELDER_IM_INHALT[11], lambda v: w.post("/api/material/artikel/zuordnen",
                                                    json={"ids": [v], "user_id": t.k["fuehrung_id"]}),
             a2, 200, t.art_b["id"]),
        ]
        # user_id: an der Stelle von B ein deaktiviertes Konto und eines ohne Namen; die Kontrolle ist ein Konto aus B.
        _, inaktiv_id = neues_konto(app, "inaktiv_a@example.org", name="Inaktiv Musterstadt")
        _, namenlos_id = neues_konto(app, "namenlos_a@example.org", name="Namenlos Musterstadt")
        sql(app, "UPDATE users SET active = 0 WHERE id = ?", (inaktiv_id,))
        sql(app, "UPDATE users SET name = '' WHERE id = ?", (namenlos_id,))
        faelle_konto = [
            (FELDER_IM_INHALT[12], lambda v: w.put(f"/api/material/artikel/{a2}/zuordnung", json={"user_id": v}),
             t.pruefer_b_id, 200),
            (FELDER_IM_INHALT[13], lambda v: w.post("/api/material/artikel/zuordnen", json={"ids": [a2], "user_id": v}),
             t.wart_b_id, 200),
            (FELDER_IM_INHALT[14], lambda v: w.post(f"/api/material/ordner/{t.lager_a}/freigaben",
                                                    json={"user_id": v, "grundrecht": "lesen"}), t.pruefer_b_id, 201),
        ]
        assert [f[0] for f in faelle] + [f[0] for f in faelle_konto] == list(FELDER_IM_INHALT)

        def formen(v, multipart):
            # Im Formular ist alles Text – 7.0 kommt dort als „7.0“ an.
            return [v, str(v), str(float(v)) if multipart else float(v)]
        for zeile, anfrage, a_wert, soll, b_wert in faelle:
            multipart = zeile[3] == "multipart"
            for fremd, unbekannt in zip(formen(b_wert, multipart), formen(999999, multipart)):
                r, u = anfrage(fremd), anfrage(unbekannt)
                assert not 200 <= r.status_code < 300, (zeile, fremd, r.status_code, r.get_json())
                assert u.status_code in (400, 404), (zeile, unbekannt, u.status_code, u.get_json())
                assert (r.status_code, r.get_json()) == (u.status_code, u.get_json()), (zeile, fremd, r.get_json(),
                                                                                        u.get_json())
            r = anfrage(a_wert)
            assert r.status_code == soll, (zeile, a_wert, r.status_code, r.get_json())
        for zeile, anfrage, b_konto, soll in faelle_konto:
            for konto in (inaktiv_id, namenlos_id):
                for gesperrt, unbekannt in zip(formen(konto, False), formen(999999, False)):
                    r, u = anfrage(gesperrt), anfrage(unbekannt)
                    assert not 200 <= r.status_code < 300, (zeile, gesperrt, r.status_code, r.get_json())
                    assert u.status_code == 404, (zeile, unbekannt, u.status_code, u.get_json())
                    assert (r.status_code, r.get_json()) == (u.status_code, u.get_json()), (zeile, gesperrt, r.get_json(),
                                                                                            u.get_json())
            r = anfrage(b_konto)
            assert r.status_code == soll, (zeile, b_konto, r.status_code, r.get_json())
        assert zeilen(app, "SELECT assigned_user_id FROM mat_item WHERE id = ?", (a2,))[0]["assigned_user_id"] == t.wart_b_id
        assert zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission = 'lesen'",
                      (t.lager_a, t.pruefer_b_id))
        assert not zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE user_id IN (?, ?)", (inaktiv_id, namenlos_id))
        # Die Prüfung der Kontrolle hängt am Durchgang aus A; an B ging nichts.
        assert zeilen(app, "SELECT round_id FROM mat_inspection WHERE item_id = ? AND completed_at IS NULL",
                      (t.art_a["id"],))[0]["round_id"] == r_a
        assert zeilen(app, "SELECT folder_id FROM mat_item WHERE id = ?", (t.art_b["id"],))[0]["folder_id"] == t.lager_b

        # Abgleich mit url_map: jede Quelle aus dem Inhalt hat ihre Zeile – und jede Zeile ihre Route.
        tabelle = {(m, regel, feld) for m, regel, feld, _ in FELDER_IM_INHALT}
        routen = {(m, r.rule) for r in app.url_map.iter_rules() for m in r.methods}
        assert all((m, regel) in routen for m, regel, _ in tabelle), tabelle - {x for x in tabelle if x[:2] in routen}
        fehlt = []
        for regel in app.url_map.iter_rules():
            if regel.endpoint.split(".")[0] not in ("material", "material_api"):
                continue
            art, _, feld = (getattr(app.view_functions[regel.endpoint], "mat_quelle", "") or "").partition(":")
            if art in ("json", "form", "eingabe"):
                fehlt += [(m, regel.rule, feld) for m in sorted(regel.methods - {"HEAD", "OPTIONS"})
                          if (m, regel.rule, feld) not in tabelle]
        assert not fehlt, f"Feld im Inhalt ohne Zeile in FELDER_IM_INHALT: {fehlt}"
    print("Felder im Inhalt bestanden.")


# --- 8.2/4: Vererbung und Heimat ---------------------------------------------------------------------------------------

def test_vererbung_und_heimat():
    """Freigabe an der Gliederung gilt bis in den Unter-Unterordner. Nur am Fahrzeug: Gliederung und Lager sind
    Pfad-Knoten (ohne Zahlen, GET 404), Geschwister fehlen. Der gesperrte Fahrzeug-Artikel ist sichtbar und
    aussonderbar, danach bleiben Artikel und Aussonderungsprotokoll lesbar. „Gesperrt“ und „Ausgesondert“ sind
    teilweise sichtbar (nur die eigenen), die Übersicht hat die Zeile „Gesperrt (deine Artikel)“."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gid, sys_a = gliederung(adm)
        lager = ordner_neu(adm, gid, "Lager")
        fahrzeug = ordner_neu(adm, lager, "Fahrzeug Eins", "fahrzeug")
        satz = ordner_neu(adm, fahrzeug, "Satz Eins", "set")
        halle = ordner_neu(adm, gid, "Halle")
        leser, leser_id = neues_konto(app, "leser@example.org", name="Leser Test")
        freigeben(adm, gid, leser_id, "lesen")
        fahrer, fahrer_id = neues_konto(app, "fahrer@example.org", name="Fahrer Test")
        freigeben(adm, fahrzeug, fahrer_id, "verwalten")
        unterschrift_hinterlegen(app, fahrer_id)
        assert leser.get(f"/api/material/ordner/{satz}").status_code == 200
        x = neuer_artikel(fahrer, ids["hms"], satz, serial_no="TEST-HEIMAT-1")["id"]
        neuer_artikel(adm, ids["hms"], fahrzeug, serial_no="TEST-HEIMAT-2")
        h = neuer_artikel(adm, ids["hms"], halle, serial_no="TEST-HEIMAT-3")["id"]
        sperren(k["pruefer"], x)
        sperren(k["pruefer"], h)

        knoten = {o["id"]: o for o in fahrer.get("/api/material/ordner").json["ordner"]}
        assert set(knoten) == {gid, lager, fahrzeug, satz, sys_a["gesperrt"], sys_a["ausgesondert"]}, knoten
        for pfad in (gid, lager):
            assert knoten[pfad] == {"id": pfad, "parent_id": knoten[pfad]["parent_id"], "name": knoten[pfad]["name"],
                                    "kind": knoten[pfad]["kind"], "system_kind": None, "nur_pfad": True}, knoten[pfad]
        assert knoten[fahrzeug]["darf"] == {"lesen": True, "grund": True, "pruefen": False, "verwalten": True}
        assert knoten[fahrzeug]["bestand"] == 1 and knoten[satz]["bestand"] == 0       # x liegt in „Gesperrt“
        g = knoten[sys_a["gesperrt"]]
        assert g["teilweise"] and g["bestand"] == 1 and g["zaehlung"]["gesperrt"] == 1, g
        assert g["darf"] == {"lesen": False, "grund": False, "pruefen": False, "verwalten": False}
        unbekannt = fahrer.get("/api/material/ordner/999999")
        for fid in (gid, lager, halle):
            gleich_wie_unbekannt(fahrer.get(f"/api/material/ordner/{fid}"), unbekannt)
        gleich_wie_unbekannt(fahrer.get(f"/api/material/artikel/{h}"), fahrer.get("/api/material/artikel/999999"))
        assert fahrer.get(f"/material/ordner/{gid}").status_code == 404
        assert fahrer.get(f"/material/ordner/{sys_a['gesperrt']}").status_code == 200
        inhalt = fahrer.get(f"/api/material/ordner/{sys_a['gesperrt']}").json["ordner"]
        assert [a["id"] for a in inhalt["artikel"]] == [x] and inhalt["artikel_gesamt"] == 1 and inhalt["journal"] is None
        assert {a["id"] for a in k["wart"].get(f"/api/material/ordner/{sys_a['gesperrt']}").json["ordner"]["artikel"]} == {x, h}
        # Übersicht: Pfad-Knoten ohne Zahlen, die eigenen Gesperrten als eigene Zeile unter der Gliederung.
        zeilen_ = fahrer.get("/api/material/start").json["ordner_uebersicht"]
        assert [z["id"] for z in zeilen_] == [gid, lager, fahrzeug, satz, sys_a["gesperrt"]], zeilen_
        assert zeilen_[0]["nur_pfad"] and "bestand" not in zeilen_[0] and "zaehlung" not in zeilen_[1]
        zeile = zeilen_[-1]
        assert zeile["name"] == "Gesperrt (deine Artikel)" and zeile["tiefe"] == 1 and zeile["zaehlung"]["gesperrt"] == 1
        assert zeile["parent_id"] == gid and zeile["teilweise"], zeile
        assert "Gesperrt (deine Artikel)" not in k["wart"].get("/api/material/start").get_data(as_text=True)
        # Aussondern durch den Verwalter des Fahrzeugs; Artikel und Protokoll bleiben lesbar.
        a = fahrer.get(f"/api/material/artikel/{x}").json["artikel"]
        assert a["darf"]["verwalten"] and a["status"] == "gesperrt", a
        r = fahrer.post(f"/api/material/artikel/{x}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 200, r.get_json()
        aid = r.json["aussonderung"]
        a = fahrer.get(f"/api/material/artikel/{x}").json["artikel"]
        assert a["status"] == "ausgesondert" and a["folder_id"] == sys_a["ausgesondert"] and a["origin_folder_id"] == satz
        assert fahrer.get(f"/api/material/pruefungen/{aid}").status_code == 200
        r = fahrer.get(f"/material/pruefung/{aid}/pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf", r.status_code
        assert fahrer.get(f"/material/artikel/{x}").status_code == 200
        inhalt = fahrer.get(f"/api/material/ordner/{sys_a['ausgesondert']}").json["ordner"]
        assert [a["id"] for a in inhalt["artikel"]] == [x], inhalt["artikel"]
    print("Vererbung und Heimat bestanden.")


# --- 8.2/5: Verschieben und Durchgänge (Kritik 1) ----------------------------------------------------------------------

def test_verschieben_und_durchgaenge():
    """Ein offener Durchgang in A, X wird nach B verschoben: In A ist X „verschoben am …“ ausgenommen (A schließt ab),
    B eröffnet ohne Konflikt einen eigenen, die Prüfung aus B hängt an Bs Durchgang, und As Sammelprotokoll nennt weder
    Pfad noch Prüferin aus B. Einbeziehen in A: 409; Bs Prüfung mit As durchgang_id: 404 wie unbekannt. Ebenso innerhalb
    einer Gliederung – ein offener Entwurf verliert dabei seinen Durchgang."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, k, w, ids = t.app, t.k, t.wart_a, t.ids
        x = t.art_a["id"]
        y = neuer_artikel(w, ids["hms"], t.a, serial_no="TEST-A-0002")["id"]
        r = w.post("/api/material/durchgaenge", json={"folder_id": t.a, "titel": "Testdurchgang Musterstadt"})
        assert r.status_code == 201 and r.json["durchgang"]["zaehlung"]["gesamt"] == 2, r.get_json()
        r_a = r.json["durchgang"]["id"]
        pid = starten(k["pruefer"], y, durchgang_id=r_a).json["pruefung"]["id"]
        assert festschreiben(k["pruefer"], pid, ergebnis="einsatzbereit").status_code == 200
        halle_b = ordner_neu(t.wart_b, t.b, "Halle Nachbarstadt")
        r = t.adm.post("/api/material/artikel/verschieben", json={"ids": [x], "folder_id": halle_b})
        assert r.status_code == 200, r.get_json()
        # In A: ausgenommen mit Grund, ohne Link (A sieht X nicht mehr), Pfad nicht aus B.
        d = w.get(f"/api/material/durchgaenge/{r_a}").json["durchgang"]
        zeile = next(a for a in d["artikel"] if not a["sichtbar"])
        assert zeile["zustand"] == "ausgenommen" and zeile["ausnahme"]["von"] == "System", zeile
        assert zeile["ausnahme"]["grund"] == f"verschoben am {_heute().strftime('%d.%m.%Y')} – nicht mehr im Bereich des Durchgangs"
        assert zeile["pfad"] == "(aus dem Bereich des Durchgangs verschoben)" and "id" not in zeile, zeile
        assert d["zaehlung"]["ausgenommen"] == 1 and d["abschliessbar"], d["zaehlung"]
        assert "Nachbarstadt" not in json.dumps(d, ensure_ascii=False)
        r = w.post(f"/api/material/durchgaenge/{r_a}/einbeziehen", json={"item_id": x})
        assert r.status_code == 409 and "nicht mehr im Bereich" in r.json["error"], r.get_json()
        # B: eigener Durchgang ohne Konflikt; As Durchgang taugt dort nicht (404 wie unbekannt); die Prüfung hängt an B.
        r = t.wart_b.post("/api/material/durchgaenge", json={"folder_id": halle_b, "titel": "Testdurchgang Halle"})
        assert r.status_code == 201, r.get_json()
        r_b = r.json["durchgang"]["id"]
        gleich_wie_unbekannt(starten(t.pruefer_b, x, durchgang_id=r_a), starten(t.pruefer_b, x, durchgang_id=999999))
        r = starten(t.pruefer_b, x)
        assert r.status_code == 201 and r.json["pruefung"]["round_id"] == r_b, r.get_json()
        assert r.json["pruefung"]["durchgang"] == {"id": r_b, "titel": "Testdurchgang Halle",
                                                   "ordner": "OG Nachbarstadt / Halle Nachbarstadt", "sichtbar": True}
        unterschreiben(t.pruefer_b)
        assert festschreiben(t.pruefer_b, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
        # A schließt ab; das Sammelprotokoll nennt nichts aus B.
        r = w.post(f"/api/material/durchgaenge/{r_a}/abschliessen", json={})
        assert r.status_code == 200, r.get_json()
        text = _flach(" ".join(pdf_seiten(os.path.join(tmp, protokoll_zeile(app, rid=r_a)["pdf_path"]))))
        for fremd in ("Nachbarstadt", "1012-9001", "Prüferin"):
            assert fremd not in text, (fremd, text[:2000])
        assert "aus dem Bereich des Durchgangs verschoben" in text, text[:2000]
        assert "pruefer" in text and "1012-4711" in text

        # Innerhalb einer Gliederung: vom Lager ins Fahrzeug – ein offener Entwurf verliert seinen Durchgang.
        lager2 = ordner_neu(w, t.a, "Lager Zwei")
        fahrzeug = ordner_neu(w, t.a, "Fahrzeug Eins", "fahrzeug")
        z = neuer_artikel(w, ids["hms"], lager2, serial_no="TEST-A-0003")["id"]
        neuer_artikel(w, ids["hms"], lager2, serial_no="TEST-A-0004")
        r = w.post("/api/material/durchgaenge", json={"folder_id": lager2, "titel": "Testdurchgang Lager Zwei"})
        assert r.status_code == 201, r.get_json()
        r_l = r.json["durchgang"]["id"]
        entwurf = starten(k["pruefer"], z, durchgang_id=r_l).json["pruefung"]["id"]
        assert w.post("/api/material/artikel/verschieben", json={"ids": [z], "folder_id": fahrzeug}).status_code == 200
        d = w.get(f"/api/material/durchgaenge/{r_l}").json["durchgang"]
        zeile = next(a for a in d["artikel"] if a.get("id") == z)
        assert zeile["sichtbar"] and zeile["zustand"] == "ausgenommen" and zeile["ausnahme"]["grund"].startswith("verschoben am")
        assert zeile["pfad"] == "(aus dem Bereich des Durchgangs verschoben)", zeile
        pr = k["pruefer"].get(f"/api/material/pruefungen/{entwurf}").json["pruefung"]
        assert pr["round_id"] is None and pr["durchgang"] is None and pr["entwurf"], pr
        assert zeilen(app, "SELECT 1 FROM mat_audit WHERE entity = 'inspection' AND entity_id = ? AND action = 'geaendert'",
                      (entwurf,))
        r = w.post(f"/api/material/durchgaenge/{r_l}/einbeziehen", json={"item_id": z})
        assert r.status_code == 409 and "nicht mehr im Bereich" in r.json["error"], r.get_json()
        # Zurück ins Lager: dann lässt er sich wieder einbeziehen – aber nicht, solange er anderswo offen steht.
        assert w.post("/api/material/artikel/verschieben", json={"ids": [z], "folder_id": lager2}).status_code == 200
        r = w.post("/api/material/durchgaenge", json={"folder_id": t.a, "titel": "Testdurchgang Gliederung"})
        assert r.status_code == 409 and "Testdurchgang Lager Zwei" in r.json["error"], r.get_json()
        assert w.post(f"/api/material/durchgaenge/{r_l}/einbeziehen", json={"item_id": z}).status_code == 200
        pr = k["pruefer"].get(f"/api/material/pruefungen/{entwurf}").json["pruefung"]
        assert pr["round_id"] == r_l, pr                       # der offene Entwurf zählt wieder hier
    print("Verschieben und Durchgänge bestanden.")


# --- 8.2/6: Eine Heimat (Kritik 2) -------------------------------------------------------------------------------------

def test_eine_heimat():
    """G verwaltet „Lager“ mit einem gesperrten und einem ausgesonderten Artikel; die Verwaltung verschiebt das Lager
    nach H. Beide wandern in die Systemordner von H (Journal mit Grund); G sieht sie nicht mehr, prüft sie nicht frei,
    exportiert sie nicht und nimmt sie in keinen neuen Durchgang."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, k, w, ids = t.app, t.k, t.wart_a, t.ids
        y = neuer_artikel(w, ids["hms"], t.lager_a, serial_no="TEST-A-0010")["id"]
        sperren(k["pruefer"], y)
        z = neuer_artikel(w, ids["hms"], t.lager_a, serial_no="TEST-A-0011")["id"]
        sperren(k["pruefer"], z)
        assert w.post(f"/api/material/artikel/{z}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        bleibt = neuer_artikel(w, ids["hms"], t.a, serial_no="TEST-A-0012")["id"]
        inventar = {r["id"]: r["inventory_no"] for r in zeilen(app, "SELECT id, inventory_no FROM mat_item")}
        assert inventar[y] in w.get(f"/material/export/{t.a}.csv").get_data(as_text=True)
        r = t.adm.post(f"/api/material/ordner/{t.lager_a}/verschieben", json={"parent_id": t.b})
        assert r.status_code == 200, r.get_json()
        lage = {r["id"]: r["folder_id"] for r in zeilen(app, "SELECT id, folder_id FROM mat_item WHERE id IN (?, ?)", (y, z))}
        assert lage == {y: t.sys_b["gesperrt"], z: t.sys_b["ausgesondert"]}, lage
        for iid, ziel in ((y, t.sys_b["gesperrt"]), (z, t.sys_b["ausgesondert"])):
            e = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'verschoben' "
                            "ORDER BY id DESC LIMIT 1", (iid,))[0]
            nachher = json.loads(e["after_json"])
            assert nachher["folder_id"] == ziel and nachher["grund"] == "Ordner in andere Gliederung verschoben", nachher
        # G: nicht mehr zu sehen, nicht freizuprüfen, nicht im Export, nicht im neuen Durchgang.
        for iid in (y, z):
            gleich_wie_unbekannt(w.get(f"/api/material/artikel/{iid}"), w.get("/api/material/artikel/999999"))
        gleich_wie_unbekannt(starten(k["pruefer"], y), starten(k["pruefer"], 999999))
        csv_a = w.get(f"/material/export/{t.a}.csv").get_data(as_text=True)
        assert inventar[y] not in csv_a and inventar[z] not in csv_a and inventar[bleibt] in csv_a
        r = w.post("/api/material/durchgaenge", json={"folder_id": t.a, "titel": "Testdurchgang Musterstadt"})
        assert r.status_code == 201 and r.json["durchgang"]["zaehlung"]["gesamt"] == 1, r.get_json()
        assert {a["id"] for a in w.get(f"/api/material/durchgaenge/{r.json['durchgang']['id']}").json["durchgang"]["artikel"]} \
            == {bleibt}
        # H sieht beide in seinen Systemordnern – und sie gehören zum verschobenen Lager.
        assert {a["id"] for a in t.wart_b.get(f"/api/material/ordner/{t.sys_b['gesperrt']}").json["ordner"]["artikel"]} == {y}
        assert t.wart_b.get(f"/api/material/artikel/{z}").json["artikel"]["origin_folder_id"] == t.lager_a
        csv_lager = t.wart_b.get(f"/material/export/{t.lager_a}.csv").get_data(as_text=True)
        assert inventar[y] in csv_lager and inventar[z] in csv_lager
    print("Eine Heimat bestanden.")


# --- 8.2/7: Kein Abziehen (Kritik 3) -----------------------------------------------------------------------------------

def test_kein_abziehen():
    """Wer G/Lager und H verwaltet, aber nicht G, zieht weder Artikel noch Ordner von G nach H ab (403). Ein Ziel in
    einer Gliederung, die er nicht sieht: 404 wie unbekannt. Mit Verwalten an G und H geht beides."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, adm = t.app, t.adm
        gast, gast_id = neues_konto(app, "gast@example.org", name="Gast Verwalter")
        freigeben(adm, t.lager_a, gast_id, "verwalten")
        freigeben(adm, t.b, gast_id, "verwalten")
        fach = ordner_neu(t.wart_a, t.lager_a, "Fach Eins")
        c, _ = gliederung(adm, "OG Drittstadt", standard=False)
        r = gast.post("/api/material/artikel/verschieben", json={"ids": [t.art_a["id"]], "folder_id": t.b})
        assert r.status_code == 403 and "beide Gliederungen" in r.json["error"], r.get_json()
        r = gast.post(f"/api/material/ordner/{fach}/verschieben", json={"parent_id": t.b})
        assert r.status_code == 403 and "beide Gliederungen" in r.json["error"], r.get_json()
        r = gast.post(f"/api/material/ordner/{t.lager_a}/verschieben", json={"parent_id": t.b})
        assert r.status_code == 403, r.get_json()                       # den Oberordner (G) verwaltet er nicht
        # Innerhalb seines Lagers und innerhalb von H darf er.
        assert gast.post("/api/material/artikel/verschieben", json={"ids": [t.art_a["id"]], "folder_id": fach}).status_code == 200
        gleich_wie_unbekannt(gast.post("/api/material/artikel/verschieben", json={"ids": [t.art_a["id"]], "folder_id": c}),
                             gast.post("/api/material/artikel/verschieben", json={"ids": [t.art_a["id"]],
                                                                                  "folder_id": 999999}))
        gleich_wie_unbekannt(gast.post(f"/api/material/ordner/{fach}/verschieben", json={"parent_id": c}),
                             gast.post(f"/api/material/ordner/{fach}/verschieben", json={"parent_id": 999999}))
        assert zeilen(app, "SELECT folder_id FROM mat_item WHERE id = ?", (t.art_a["id"],))[0]["folder_id"] == fach
        # Mit Verwalten an G und H: beides.
        freigeben(adm, t.a, gast_id, "verwalten")
        r = gast.post("/api/material/artikel/verschieben", json={"ids": [t.art_a["id"]], "folder_id": t.b})
        assert r.status_code == 200, r.get_json()
        r = gast.post(f"/api/material/ordner/{fach}/verschieben", json={"parent_id": t.b})
        assert r.status_code == 200, r.get_json()
        # Auf die oberste Ebene und von dort weg nur die Verwaltung.
        r = gast.post(f"/api/material/ordner/{t.b}/verschieben", json={"parent_id": t.a})
        assert r.status_code == 403, r.get_json()
    print("Kein Abziehen bestanden.")


# --- 8.2/8: Produktjournal (Kritik 6) ----------------------------------------------------------------------------------

def test_produktjournal():
    """Eine Meldung aus B mit Bemerkung und Link wird zum Produkt, das A nutzt. Produkt und A-Artikel zeigen wart_a
    weder Melder noch Bemerkung, Link oder Ordner aus B; die Katalogpflege und der Melder sehen den Eintrag."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        ids, w = t.ids, t.wart_a
        r = t.wart_b.post("/api/material/meldungen", headers=H, json={
            "manufacturer": "Meldewerk", "model": "Seilklemme Test", "note": "Bemerkung Nachbarstadt",
            "links": ["https://example.org/nachbarstadt"], "folder_id": t.lager_b})
        assert r.status_code == 201, r.get_json()
        mid = r.json["meldung"]["id"]
        r = t.k["katalog"].post(f"/api/material/meldungen/{mid}/produkt", json={
            "category_id": ids["karabiner"], "manufacturer": "Meldewerk", "model": "Seilklemme Test", "article_no": "MW-1",
            "material_kind": "metall_hardware", "interval_months": 12, "antwort": "Eingepflegt."})
        assert r.status_code == 201, r.get_json()
        pid = r.json["produkt"]["id"]
        a = neuer_artikel(w, pid, t.lager_a)

        def eintraege(c, url, schluessel):
            r = c.get(url)
            assert r.status_code == 200, (url, r.get_json())
            return r.get_data(as_text=True), r.json[schluessel]["journal"]
        for url, schluessel in ((f"/api/material/produkte/{pid}", "produkt"), (f"/api/material/artikel/{a['id']}", "artikel")):
            text, journal_ = eintraege(w, url, schluessel)
            for fremd in ("Wart Nachbarstadt", "Bemerkung Nachbarstadt", "example.org/nachbarstadt", "Nachbarstadt"):
                assert fremd not in text, (url, fremd)
            assert not [e for e in journal_ if e["entity"] == "request"], journal_
            for e in journal_:
                for teil in (e["vorher"] or {}, e["nachher"] or {}):
                    assert teil.get("folder_id") != t.lager_b, e
        for c in (t.k["katalog"], t.wart_b):
            _, journal_ = eintraege(c, f"/api/material/produkte/{pid}", "produkt")
            assert {e["action"] for e in journal_ if e["entity"] == "request"} == {"angelegt", "eingepflegt"}, journal_
        # Im Artikeljournal stehen Meldungen nie – auch nicht für den Melder.
        b_artikel = neuer_artikel(t.wart_b, pid, t.lager_b)
        _, journal_ = eintraege(t.wart_b, f"/api/material/artikel/{b_artikel['id']}", "artikel")
        assert not [e for e in journal_ if e["entity"] == "request"]
    print("Produktjournal bestanden.")


# --- 8.2/10: Dublette (Kritik 8) ---------------------------------------------------------------------------------------

def test_dublette():
    """Eine Seriennummer, die es bei diesem Produkt nur in B gibt: 409 ohne Inventarnummer und Gliederung, eine Zeile
    „dublette“ im Protokoll; die elfte in einer Viertelstunde: 429. Eine sichtbare Dublette: 409 mit Inventarnummer,
    ohne Protokoll. Ebenso beim Ändern der Seriennummer."""
    from app.material.services import globalprotokoll
    from app.material.services.bestand import FremdeDublette
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w, ids = t.app, t.wart_a, t.ids
        inventar_b = zeilen(app, "SELECT inventory_no FROM mat_item WHERE id = ?", (t.art_b["id"],))[0]["inventory_no"]

        def anlegen(serie):
            return w.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": t.lager_a, "serial_no": serie})

        def protokoll():
            return zeilen(app, "SELECT * FROM mat_global_search WHERE art = 'dublette' ORDER BY id")
        r = anlegen("TEST-B-0001")
        assert r.status_code == 409 and r.json["error"] == FremdeDublette.TEXT, r.get_json()
        assert inventar_b not in r.json["error"] and "Nachbarstadt" not in r.json["error"]
        z = protokoll()
        assert [(x["user_id"], x["user_name"], x["anfrage"], x["treffer"], json.loads(x["item_ids"])) for x in z] == \
            [(t.k["wart_id"], "wart", "TEST-B-0001", 1, [t.art_b["id"]])], z
        assert not zeilen(app, "SELECT 1 FROM mat_item WHERE serial_no = 'TEST-B-0001' AND id <> ?", (t.art_b["id"],))
        # Sichtbare Dublette: wie bisher mit Inventarnummer, ohne Protokoll und ohne Bremse.
        eigen = neuer_artikel(w, ids["hms"], t.lager_a, serial_no="TEST-A-0005")
        r = anlegen("test-a-0005")
        assert r.status_code == 409 and eigen["inventory_no"] in r.json["error"], r.get_json()
        assert len(protokoll()) == 1
        # Ändern auf eine fremde Seriennummer: ebenso.
        r = w.put(f"/api/material/artikel/{t.art_a['id']}", json={"serial_no": "TEST-B-0001"})
        assert r.status_code == 409 and r.json["error"] == FremdeDublette.TEXT, r.get_json()
        assert len(protokoll()) == 2
        assert zeilen(app, "SELECT serial_no FROM mat_item WHERE id = ?", (t.art_a["id"],))[0]["serial_no"] == "TEST-A-0001"
        # Bremse: zusammen höchstens zehn in der Viertelstunde, die elfte 429 – ohne Zeile.
        for _ in range(globalprotokoll.GRENZE - 2):
            assert anlegen("TEST-B-0001").status_code == 409
        r = anlegen("TEST-B-0001")
        assert r.status_code == 429 and r.json["error"] == globalprotokoll.ZU_VIELE, r.get_json()
        assert len(protokoll()) == globalprotokoll.GRENZE
        # Die Verwaltung sieht B – für sie ist es eine sichtbare Dublette.
        r = t.adm.post("/api/material/artikel", json={"product_id": ids["hms"], "folder_id": t.lager_a,
                                                      "serial_no": "TEST-B-0001"})
        assert r.status_code == 409 and inventar_b in r.json["error"], r.get_json()
    print("Dublette bestanden.")


# --- 8.2/11: Prüfsicht (Kritik 11) -------------------------------------------------------------------------------------

def test_pruefsicht():
    """Ein externer Prüfer mit nur einer Prüffreigabe am Lager: Artikel und Prüfungen ja; CSV, ZIP und Lebenslauf nicht
    (403 am Lager, 404 an der Gliederung, die er nicht sieht); zugeordnete Person und Journal null, der Filter
    „zugeordnet“ findet nichts. Ohne Urkundennummer wirkt die Prüffreigabe nicht mehr: alles 404; ohne Häkchen auch
    kein Modulzugang: 403."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, w, adm = t.app, t.wart_a, t.adm
        ext, ext_id = neues_konto(app, "extern@example.org", name="Externer Prüfer", mat_pruefer=True,
                                  urkundennummer="1012-8001")
        freigeben(adm, t.lager_a, ext_id, "pruefen")
        _, person_id = neues_konto(app, "person_a@example.org", name="Person Musterstadt")
        sql(app, "UPDATE mat_item SET assigned_user_id = ? WHERE id = ?", (person_id, t.art_a["id"]))
        iid = t.art_a["id"]
        a = ext.get(f"/api/material/artikel/{iid}").json["artikel"]
        assert a["darf"] == {"lesen": True, "grund": False, "pruefen": True, "verwalten": False}, a["darf"]
        assert a["zugeordnet"] is None and a["journal"] is None and "Person Musterstadt" not in json.dumps(a), a
        a = w.get(f"/api/material/artikel/{iid}").json["artikel"]
        assert a["zugeordnet"] == {"id": person_id, "name": "Person Musterstadt", "gliederung": "", "aktiv": True}, a
        assert a["journal"], a
        o = ext.get(f"/api/material/ordner/{t.lager_a}").json["ordner"]
        assert o["journal"] is None and [x["zugeordnet_name"] for x in o["artikel"]] == [None], o
        assert [x["zugeordnet_name"] for x in w.get(f"/api/material/ordner/{t.lager_a}").json["ordner"]["artikel"]] == \
            ["Person Musterstadt"]
        assert ext.get(f"/api/material/ordner/{t.lager_a}?zugeordnet={person_id}").json["ordner"]["artikel_gesamt"] == 0
        assert w.get(f"/api/material/ordner/{t.lager_a}?zugeordnet={person_id}").json["ordner"]["artikel_gesamt"] == 1
        assert ext.get(f"/api/material/faellig?zugeordnet={person_id}").json["gesamt"] == 0
        assert w.get(f"/api/material/faellig?zugeordnet={person_id}").json["gesamt"] == 1
        assert w.get("/api/material/faellig?zugeordnet=abc").status_code == 400
        r = starten(ext, iid)
        assert r.status_code == 201, r.get_json()
        pid = r.json["pruefung"]["id"]
        assert r.json["pruefung"]["darf"]["pruefen"] and r.json["pruefung"]["artikel"]["zugeordnet_name"] is None
        assert ext.get(f"/api/material/artikel/{iid}/pruefungen").status_code == 200
        assert ext.get(f"/api/material/pruefungen/{pid}").status_code == 200
        for url in (f"/material/export/{t.lager_a}.csv", f"/material/export/{t.lager_a}-protokolle.zip",
                    f"/material/artikel/{iid}/lebenslauf.pdf"):
            assert ext.get(url).status_code == 403, url
        for url in (f"/material/export/{t.a}.csv", f"/material/export/{t.a}-protokolle.zip"):
            assert ext.get(url).status_code == 404, url
        # Ohne Urkundennummer (Häkchen bleibt, also Modulzugang): Die Prüffreigabe wirkt nicht – alles wie unbekannt.
        assert adm.put(f"/api/admin/users/{ext_id}", json={"urkundennummer": ""}).status_code == 200
        for pfad in (f"artikel/{iid}", f"pruefungen/{pid}", f"ordner/{t.lager_a}", f"artikel/{iid}/pruefungen"):
            gleich_wie_unbekannt(ext.get(f"/api/material/{pfad}"), ext.get(f"/api/material/{pfad.split('/')[0]}/999999"
                                                                           + ("/pruefungen" if pfad.endswith("pruefungen")
                                                                              and pfad.startswith("artikel") else "")))
        assert ext.get(f"/material/export/{t.lager_a}.csv").status_code == 404
        assert ext.get(f"/material/artikel/{iid}").status_code == 404
        # Ohne Häkchen: kein Modulzugang – 403 vor jeder Frage nach dem Gegenstand.
        assert adm.put(f"/api/admin/users/{ext_id}", json={"mat_pruefer": False}).status_code == 200
        r = ext.get(f"/api/material/artikel/{iid}")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        assert ext.get("/api/material/artikel/999999").status_code == 403
    print("Prüfsicht bestanden.")


# --- Journal, Pseudonyme, Prüfseite und Seiten --------------------------------------------------------------------------

def test_journal_und_seiten():
    """Was sonst zur Trennung gehört: Ordner löschen schreibt je Freigabe „freigabe_entfernt“ (Kontoverweis, kein Name)
    und hält nur noch wegen Gesperrter an; Aussondern löst die Zuordnung (Journal mit Grund, Kontoverweis); das Journal
    liest den Verweis als Namen, der Lebenslauf schreibt „(Person)“; die Prüfseite verlinkt nur, was das Konto sieht;
    „Artikel anlegen“ nur für Verwalter; Seiten ohne Modulzugang nennen den Grund; Prüfer stehen nie mit E-Mail da."""
    import html as html_mod
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        app, k, w, ids, adm = t.app, t.k, t.wart_a, t.ids, t.adm

        def refs():
            return {u["id"]: u["mat_ref"] for u in zeilen(app, "SELECT id, mat_ref FROM users")}
        # Ordner löschen: Gesperrte halten ihn, Ausgesonderte nicht; die Freigaben gehen mit Journal.
        fach = ordner_neu(w, t.lager_a, "Fach Eins")
        _, gast_id = neues_konto(app, "gast@example.org", name="Gast Fach")
        bis = (_heute() + timedelta(days=30)).isoformat()
        grant = freigeben(adm, fach, gast_id, "lesen", bis=bis)
        x = neuer_artikel(w, ids["hms"], fach, serial_no="TEST-A-0020")["id"]
        sperren(k["pruefer"], x)
        r = w.delete(f"/api/material/ordner/{fach}", headers=H)
        assert r.status_code == 409 and "kehren" in r.json["error"], r.get_json()
        assert w.post(f"/api/material/artikel/{x}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        r = w.delete(f"/api/material/ordner/{fach}", headers=H)
        assert r.status_code == 200, r.get_json()
        e = zeilen(app, "SELECT * FROM mat_audit WHERE action = 'freigabe_entfernt'")
        assert len(e) == 1 and e[0]["entity"] == "folder" and e[0]["entity_id"] == fach and e[0]["user_name"] == "wart", e
        assert json.loads(e[0]["before_json"]) == {"freigabe": grant, "konto": {"ref": refs()[gast_id]}, "recht": "lesen",
                                                   "bis": bis}, e
        assert json.loads(e[0]["after_json"]) == {"grund": "Ordner gelöscht"} and "Gast" not in e[0]["before_json"]
        assert not zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE folder_id = ?", (fach,))
        # Der Ausgesonderte hat seine Herkunft verloren und gehört jetzt zur Gliederung – weiter sichtbar.
        a = w.get(f"/api/material/artikel/{x}").json["artikel"]
        assert a["origin_folder_id"] is None and a["folder_id"] == t.sys_a["ausgesondert"], a
        # Aussondern löst die Zuordnung – im Journal nur der Kontoverweis.
        y = neuer_artikel(w, ids["hms"], t.lager_a, serial_no="TEST-A-0021")["id"]
        _, person_id = neues_konto(app, "person_a@example.org", name="Person Musterstadt")
        sql(app, "UPDATE mat_item SET assigned_user_id = ? WHERE id = ?", (person_id, y))
        sperren(k["pruefer"], y)
        assert w.post(f"/api/material/artikel/{y}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        assert zeilen(app, "SELECT assigned_user_id FROM mat_item WHERE id = ?", (y,))[0]["assigned_user_id"] is None
        e = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = 'zuordnung_geloest'",
                   (y,))
        assert len(e) == 1 and e[0]["before_json"] is None, e
        assert json.loads(e[0]["after_json"]) == {"konto": {"ref": refs()[person_id]}, "grund": "ausgesondert"}, e
        # Die Kennung als eigene Zahl – als Teilstück des zufälligen Hex-Verweises käme sie sonst gelegentlich vor.
        assert "Person" not in e[0]["after_json"] and not re.search(rf"(?<![0-9a-f]){person_id}(?![0-9a-f])",
                                                                   e[0]["after_json"]), e
        # Gelesen wird der Verweis als Name – ohne den Verweis selbst; im Lebenslauf steht „(Person)“.
        a = w.get(f"/api/material/artikel/{y}").json["artikel"]
        eintrag = next(j for j in a["journal"] if j["action"] == "zuordnung_geloest")
        assert eintrag["nachher"] == {"konto": {"name": "Person Musterstadt"}, "grund": "ausgesondert"}, eintrag
        assert refs()[person_id] not in json.dumps(a)
        r = w.get(f"/material/artikel/{y}/lebenslauf.pdf")
        assert r.status_code == 200, r.status_code
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "Person: (Person)" in text and "Person Musterstadt" not in text, text[-1500:]      # „Zuordnung geändert“
        from app.material.services import beschriftung
        assert beschriftung.wert_text({"name": "Person Musterstadt"}, "konto") == "(Person)"
        assert beschriftung.wert_text("pruefen", "recht") == "prüfen" and beschriftung.wert_text(None, "bis") == "unbefristet"
        assert beschriftung.AKTION["freigabe_entfernt"] == "Freigabe entfernt"

        # Prüfseite: der Link nur für den, der die Prüfung sehen darf.
        pid_b = starten(t.pruefer_b, neuer_artikel(t.wart_b, ids["hms"], t.lager_b)["id"]).json["pruefung"]["id"]
        unterschreiben(t.pruefer_b)
        assert festschreiben(t.pruefer_b, pid_b, ergebnis="einsatzbereit").status_code == 200
        with open(os.path.join(tmp, protokoll_zeile(app, pid_b)["pdf_path"]), "rb") as fh:
            original = fh.read()

        def pruefen(c):
            r = c.post("/api/material/pruefen", data={"datei": (io.BytesIO(original), "protokoll.pdf")}, headers=H,
                       content_type="multipart/form-data")
            assert r.status_code == 200, r.get_json()
            return r.json
        assert pruefen(w)["ergebnis"] == "unveraendert" and "link" not in pruefen(w)
        assert pruefen(t.wart_b)["link"] == f"/material/pruefung/{pid_b}"
        assert w.get(f"/material/pruefung/{pid_b}/pdf").status_code == 404
        assert w.get(f"/material/pruefung/{pid_b}").status_code == 404

        # „Artikel anlegen“: nur wer irgendwo verwaltet; den Ordner aus der Adresse nur, wenn er ihn verwaltet.
        r = k["fuehrung"].get("/material/artikel/neu")
        assert r.status_code == 403 and "Materialwarte" in r.get_data(as_text=True)

        def daten(r):
            assert r.status_code == 200, r.status_code
            return json.loads(html_mod.unescape(re.search(r'data-daten="([^"]*)"', r.get_data(as_text=True)).group(1)))
        assert daten(w.get(f"/material/artikel/neu?ordner={t.lager_b}"))["ordner"] is None
        assert daten(w.get(f"/material/artikel/neu?ordner={t.lager_a}"))["ordner"] == t.lager_a
        # Ohne Modulzugang: 403 mit dem Grund, auf jeder Seite.
        token = zeilen(app, "SELECT qr_token FROM mat_item WHERE id = ?", (t.art_a["id"],))[0]["qr_token"]
        for url in ("/material", f"/m/{token}", f"/material/artikel/{t.art_a['id']}", f"/material/export/{t.a}.csv"):
            r = k["nutzer"].get(url)
            assert r.status_code == 403 and "nicht freigeschaltet" in r.get_data(as_text=True), url
        # Prüfer stehen mit Namen da, nie mit der E-Mail.
        from app.material.services import pruefung
        with app.test_request_context():
            u = {"id": 1, "name": "  ", "email": "ohne@example.org", "urkundennummer": "", "mat_pruefer": 0,
                 "signature_png": None}
            assert pruefung.pruefer_aus(u)["name"] == "(Konto ohne Namen)"
    print("Journal und Seiten bestanden.")


# --- Tests, die erst mit einem anderen Paket grün werden ----------------------------------------------------------------

def test_nichts_aus_b_paket_d():
    """8.2/2, Teil von Paket D: die Meldung aus B (lesen 404 wie unbekannt, in keiner Liste), ein Rückruf über alle
    Artikel des Produkts (Übersicht, Produktseite, Rückrufliste und -antwort, Artikel) und die Rückrufmail an wart_a –
    nirgends ein Merkmal aus B."""
    from app.material.services import rueckruf
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t, b = trennung_aufbau(tmp)
        w, ids = t.wart_a, t.ids
        gleich_wie_unbekannt(w.get(f"/api/material/meldungen/{b.meldung}"), w.get("/api/material/meldungen/999999"))
        for url in ("/api/material/meldungen", "/api/material/meldungen?eigene=0", "/api/material/meldungen?eigene=1"):
            r = w.get(url)
            assert r.status_code == 200 and b.meldung not in [m["id"] for m in r.json["meldungen"]], (url, r.get_json())
            ohne_merkmale(b, url, r.data)
        post = []
        alt = (rueckruf.HINTERGRUND, rueckruf.send_mail)
        rueckruf.HINTERGRUND = lambda f, *a: f(*a)
        rueckruf.send_mail = lambda an, betreff, inhalt: post.append((an, betreff, inhalt)) or True
        try:
            r = t.adm.post(f"/api/material/produkte/{ids['hms']}/rueckrufe", json={"title": "Testrückruf", "mail": True})
            assert r.status_code == 201, r.get_json()
        finally:
            rueckruf.HINTERGRUND, rueckruf.send_mail = alt
        ruid = r.json["rueckruf"]["id"]
        for url in ("/api/material/rueckrufe", "/api/material/start", f"/api/material/produkte/{ids['hms']}",
                    f"/api/material/produkte/{ids['hms']}/rueckrufe", f"/api/material/artikel/{t.art_a['id']}",
                    f"/material/katalog/produkt/{ids['hms']}"):
            r = w.get(url)
            assert r.status_code == 200, (url, r.status_code)
            ohne_merkmale(b, url, r.data)
        inventar_a = zeilen(t.app, "SELECT inventory_no FROM mat_item WHERE id = ?", (t.art_a["id"],))[0]["inventory_no"]
        an_a = [m for m in post if m[0] == "wart@example.org"]
        assert len(an_a) == 1 and inventar_a in an_a[0][2], post
        ohne_merkmale(b, "Rückrufmail an wart_a", an_a[0][1] + an_a[0][2])
        r = w.post(f"/api/material/rueckrufe/{ruid}/beenden", json={"vermerk": "Test"})
        assert r.status_code == 403
    print("Nichts aus B (Paket D) bestanden.")


def test_rueckruf_antwort():
    """8.2/9 (Paket D): Ein Katalogpfleger ohne Bestand legt einen Rückruf mit mail=false und Seriennummern aus B an und
    beendet ihn – die Antworten nennen weder nicht gefundene Nummern noch Empfänger, betroffen ist 0. Die Verwaltung
    bekommt die vollen Zahlen."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        kp, _ = neues_konto(t.app, "katalog_ohne@example.org", name="Katalog ohne Bestand", mat_katalog=True)
        daten = {"title": "Testrückruf", "serials": "TEST-B-0001\nTEST-X-0404", "mail": False}
        r = kp.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", json=daten)
        assert r.status_code == 201, r.get_json()
        j = r.get_json()
        assert "nicht_gefunden" not in j and "empfaenger" not in j and j["betroffen"] == 0, j
        assert "nicht_gefunden" not in j["rueckruf"] and not j["rueckruf"].get("artikel"), j["rueckruf"]
        r = kp.post(f"/api/material/rueckrufe/{j['rueckruf']['id']}/beenden", json={"vermerk": "Testvermerk"})
        assert r.status_code == 200, r.get_json()
        assert "nicht_gefunden" not in r.get_data(as_text=True) and "empfaenger" not in r.get_data(as_text=True)
        r = t.adm.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", json=daten)
        assert r.status_code == 201 and r.json["betroffen"] == 1 and r.json["nicht_gefunden"] == ["TEST-X-0404"], r.get_json()
        assert "empfaenger" in r.json
    print("Rückruf-Antwort bestanden.")


def test_pruefsicht_zugeordnete():
    """8.2/11 (Paket D): „Zugeordnete eines Ordners“ nur mit Grundrecht – der externe Prüfer bekommt 403."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        ext, ext_id = neues_konto(t.app, "extern@example.org", name="Externer Prüfer", mat_pruefer=True,
                                  urkundennummer="1012-8001")
        freigeben(t.adm, t.lager_a, ext_id, "pruefen")
        assert ext.get(f"/api/material/ordner/{t.lager_a}/zugeordnete").status_code == 403
        assert t.wart_a.get(f"/api/material/ordner/{t.lager_a}/zugeordnete").status_code == 200
        gleich_wie_unbekannt(t.wart_a.get(f"/api/material/ordner/{t.lager_b}/zugeordnete"),
                             t.wart_a.get("/api/material/ordner/999999/zugeordnete"))
    print("Prüfsicht: Zugeordnete bestanden.")


# Was erst nach dem Zusammenführen mit einem anderen Paket grün sein kann (Bauentwurf 9.3): Name → Paket. Der Block
# __main__ führt diese Tests aus und meldet ein Scheitern nur; die Integration leert die Tabelle.
WARTET_AUF = {"test_nichts_aus_b_paket_d": "D", "test_rueckruf_antwort": "D", "test_pruefsicht_zugeordnete": "D"}


if __name__ == "__main__":
    test_migration_7_8()
    test_sicht()
    test_requires_folder()
    test_ablauf()
    test_pruefen_nur_mit_prueffreigabe()
    test_abfragezahl()
    test_unterbau()
    test_nichts_aus_b()
    test_felder_im_inhalt()
    test_vererbung_und_heimat()
    test_verschieben_und_durchgaenge()
    test_eine_heimat()
    test_kein_abziehen()
    test_produktjournal()
    test_dublette()
    test_pruefsicht()
    test_journal_und_seiten()
    for name, paket in WARTET_AUF.items():
        try:
            globals()[name]()
        except Exception as exc:                 # wartet auf das andere Paket – meldet, scheitert aber nicht
            print(f"{name}: wartet auf Paket {paket} ({type(exc).__name__}: {str(exc)[:200]})")
