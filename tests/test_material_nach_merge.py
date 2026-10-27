"""Liste nach dem Merge, Teil A (27.10.2026):  python tests/test_material_nach_merge.py  oder pytest

1 Lebenslauf-Kennung nach dem Zurückspielen einer Sicherung nie doppelt (Zählerdatei unter DATA_DIR/pdf/lebenslauf),
2 HEAD auf lebenslauf.pdf nur mit Kopfzeilen (keine Kennung, kein Eintrag), 3 Abrufbremse je Konto (429 mit Klartext),
5/6 Prüfseite „Protokoll oder Lebenslauf prüfen“ ohne doppelte Fehlermeldung, 15 Schritt 32 (REPLACE ohne
recursive_triggers verdrängt keine Prüfung, keinen Durchgang und keinen geprüften Artikel – frisch, 31 → 32 mit
Altbestand, zweiter Lauf), 18 Rückruf „für alle Artikel“ nach einem bestätigten Antrag wieder offen (Antrag sagt es,
Journal vermerkt es), 19 Rückruf-Text „keine Mail hinaus“ nach dem Stand beim Versand. Alles Platzhalter."""
import os
import re
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, festschreiben, jpeg, mails_abfangen, mails_zurueck, make_app, neuer_artikel,  # noqa: E402
                           starten)
from test_material_a4_n5 import _geprueft  # noqa: E402
from test_material_a4_n5 import aufbau as aufbau_a4  # noqa: E402
from test_material_export import aufbau  # noqa: E402
from test_material_lebenslauf_summe import _abruf, _zeilen  # noqa: E402
from test_material_vor_merge import _versuch, _zeilen_je_tabelle  # noqa: E402

API = "/api/material"
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(rel):
    with open(os.path.join(WURZEL, rel), encoding="utf-8") as fh:
        return fh.read()


def _zaehlerdateien(app):
    ordner = os.path.join(app.config["DATA_DIR"], "pdf", "lebenslauf")
    return sorted(os.listdir(ordner)) if os.path.isdir(ordner) else []


def test_kennung_nach_zurueckspielen():
    """Abruf → Sicherung → zwei Abrufe → Sicherung zurück (Datenbank ersetzt, pdf/ nur ergänzt, wie README
    „Zurückspielen“) → der nächste Abruf bekommt eine neue Nummer, keine schon ausgegebene. Ohne Zählerdatei gäbe es die
    Kennung ein zweites Mal (Gegenprobe)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        w, iid = k["wart"], a["lager"]["id"]
        _, k1 = _abruf(w, iid)
        jahr = k1.split("-")[1]
        assert k1 == f"L-{jahr}-000001" and _zaehlerdateien(app) == [k1]
        pfad = os.path.join(tmp, "stroemis.db")
        sicherung = os.path.join(tmp, "sicherung.db")
        quelle = sqlite3.connect(pfad)
        ziel = sqlite3.connect(sicherung)
        quelle.backup(ziel)
        quelle.close()
        ziel.close()
        _, k2 = _abruf(w, iid)
        _, k3 = _abruf(w, a["formel"]["id"])
        assert (k2, k3) == (f"L-{jahr}-000002", f"L-{jahr}-000003") and _zaehlerdateien(app) == [k3]

        def zurueckspielen():
            quelle = sqlite3.connect(sicherung)
            ziel = sqlite3.connect(pfad)
            quelle.backup(ziel)
            quelle.close()
            ziel.close()
        zurueckspielen()
        # rsync ~/data.bak/pdf/ data/pdf/ ergänzt: Die Zählerdatei aus der Sicherung liegt danach neben der neueren.
        open(os.path.join(tmp, "pdf", "lebenslauf", k1), "w").close()
        assert [z["kennung"] for z in _zeilen(app)] == [k1]
        _, k4 = _abruf(w, iid)
        assert k4 == f"L-{jahr}-000004", k4
        assert _zaehlerdateien(app) == [k4]
        # Gegenprobe: ohne Zählerdatei vergäbe die zurückgespielte Datenbank 000002 noch einmal.
        zurueckspielen()
        os.remove(os.path.join(tmp, "pdf", "lebenslauf", k4))
        _, k5 = _abruf(w, iid)
        assert k5 == f"L-{jahr}-000002", k5
        # Je Jahr eine Datei; ein anderes Jahr lässt die Datei dieses Jahres stehen.
        with app.app_context():
            from app.material.services import lebenslauf
            assert lebenslauf.kennung_vergeben("2031-06-01T10:00:00+00:00") == "L-2031-000001"
        assert _zaehlerdateien(app) == sorted([k5, "L-2031-000001"])
        # Ist die Ablage nicht beschreibbar, geht der Abruf trotzdem (Warnung im Log).
        os.chmod(os.path.join(tmp, "pdf", "lebenslauf"), 0o500)
        try:
            _, k6 = _abruf(w, iid)
            assert k6 == f"L-{jahr}-000003", k6
        finally:
            os.chmod(os.path.join(tmp, "pdf", "lebenslauf"), 0o700)
    readme = " ".join(lies("README.md").split())
    assert "pdf/lebenslauf/" in readme and "Kennung eines ausgegebenen Lebenslaufs wird nicht noch einmal vergeben" in readme
    print("Kennung nach dem Zurückspielen bestanden.")


def test_head_und_bremse():
    """HEAD: nach der Rechteprüfung nur Kopfzeilen (keine Kennung, keine Zeile, kein Zähler); ohne Recht wie GET.
    Bremse je Konto: über der Grenze 429 mit Klartext und Retry-After, keine Zeile; ein anderes Konto ruft weiter ab."""
    from app.material import routes_export
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        w, iid = k["wart"], a["lager"]["id"]
        r = w.head(f"/materialablage/artikel/{iid}/lebenslauf.pdf?stand=1")
        assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data == b"", (r.status_code, r.data[:20])
        assert "no-store" in r.headers["Cache-Control"] and "Content-Disposition" not in r.headers, dict(r.headers)
        assert "L-" not in str(r.headers) and _zeilen(app) == [] and _zaehlerdateien(app) == []
        with app.app_context():
            from app import db
            assert not db.query("SELECT 1 FROM mat_meta WHERE schluessel LIKE 'lebenslauf_zaehler_%'")
        assert k["nutzer"].head(f"/materialablage/artikel/{iid}/lebenslauf.pdf").status_code == 403
        assert w.head("/materialablage/artikel/999999/lebenslauf.pdf").status_code == 404
        # Bremse (Grenze für den Test auf 2 gesenkt).
        alt = routes_export.LEBENSLAUF_JE_VIERTELSTUNDE
        routes_export.LEBENSLAUF_JE_VIERTELSTUNDE = 2
        try:
            _abruf(w, iid)
            _abruf(w, iid)
            r = w.get(f"/materialablage/artikel/{iid}/lebenslauf.pdf")
            assert r.status_code == 429 and r.headers["Retry-After"] == "900", r.status_code
            assert "sehr viele Lebensläufe abgerufen" in r.text and "Viertelstunde" in r.text, r.text[:500]
            assert len(_zeilen(app)) == 2
            # HEAD zählt nicht und wird nicht gebremst; ein anderes Konto ruft weiter ab.
            assert w.head(f"/materialablage/artikel/{iid}/lebenslauf.pdf").status_code == 200
            _abruf(k["fuehrung"], iid)
            assert len(_zeilen(app)) == 3
            # Abgewiesenes (fremd, ohne Recht) zählt nicht: Die Führungskraft hat einen Abruf frei.
            assert k["nutzer"].get(f"/materialablage/artikel/{iid}/lebenslauf.pdf").status_code == 403
            _abruf(k["fuehrung"], iid)
            assert k["fuehrung"].get(f"/materialablage/artikel/{iid}/lebenslauf.pdf").status_code == 429
        finally:
            routes_export.LEBENSLAUF_JE_VIERTELSTUNDE = alt
    print("HEAD und Bremse bestanden.")


def test_pruefseite_texte():
    """Titel, Überschrift und Links „Protokoll oder Lebenslauf prüfen“; Hinweis auf Lebensläufe ohne Kennung; die
    Fehlermeldung steht nur im Ergebniskasten (kein Toast dazu)."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        r = app.test_client().get("/materialablage/pruefen")
        assert r.status_code == 200
        assert "<title>Protokoll oder Lebenslauf prüfen – strömis.de</title>" in r.text
        assert "<h1>Protokoll oder Lebenslauf prüfen</h1>" in r.text
        text = " ".join(r.text.split())
        assert "bevor sie eine Kennung (L-…) bekamen, tragen keine Prüfsumme – sie werden hier nicht erkannt." in text
    js = lies("app/material/static/pruefen.js")
    assert "toast" not in js and '<strong>Nicht geprüft</strong>' in js
    mjs = lies("app/material/static/material.js")
    assert ">Protokoll oder Lebenslauf prüfen</a>" in mjs and ">Protokoll prüfen</a>" not in mjs
    print("Prüfseite bestanden.")


def _bestand_mit_offenem(tmp):
    """Abgeschlossener Durchgang mit Prüfungen (test_material_setprotokolle._haupt), dazu ein offener Prüfentwurf mit
    Anhang an einem nie geprüften Artikel, ein offener Durchgang und ein geprüfter Artikel."""
    from test_material_setprotokolle import _haupt, durchgang
    t = _haupt(tmp)
    t.neu = neuer_artikel(t.w, t.ids["hms"], t.a, serial_no="NM-OFFEN")
    for iid in (t.d1["id"], t.neu["id"]):                    # festgeschrieben mit Anhang, dann ein Entwurf mit Anhang
        pr = starten(t.p, iid).json["pruefung"]
        r = t.p.post(f"{API}/pruefungen/{pr['id']}/anhaenge", headers=H, content_type="multipart/form-data",
                     data={"file": [(jpeg(), "scan.jpg")], "art": "foto", "titel": "Platzhalter-Scan"})
        assert r.status_code in (200, 201), r.get_json()
        if iid == t.d1["id"]:
            assert festschreiben(t.p, pr["id"], ergebnis="einsatzbereit").status_code == 200
    t.entwurf = pr["id"]
    t.offen_rid = durchgang(t, t.c, "Offener Platzhalter-Durchgang")
    return t


def test_schritt_32_trigger():
    """Befund 1 der Sicherheitsprüfung vor dem Merge: REPLACE über eine offene Zeile bzw. über einen anderen eindeutigen
    Schlüssel des Artikels – abgewiesen mit der Verbindung der App und mit der Vorgabe des sqlite3-Werkzeugs (ohne
    recursive_triggers und Fremdschlüssel). Was die App tut, geht weiter."""
    with tempfile.TemporaryDirectory() as tmp:
        t = _bestand_mit_offenem(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        c = sqlite3.connect(pfad)
        eins = lambda sql: c.execute(sql).fetchone()[0]                                        # noqa: E731
        fest = eins("SELECT MIN(id) FROM mat_inspection WHERE completed_at IS NOT NULL")
        fest_befund = eins(f"SELECT MIN(id) FROM mat_inspection_result WHERE inspection_id = {fest}")
        entwurf_befund = eins(f"SELECT MIN(id) FROM mat_inspection_result WHERE inspection_id = {t.entwurf}")
        fest_anhang = eins("SELECT MIN(a.id) FROM mat_inspection_attachment a JOIN mat_inspection x "
                           "ON x.id = a.inspection_id WHERE x.completed_at IS NOT NULL")
        entwurf_anhang = eins(f"SELECT MIN(id) FROM mat_inspection_attachment WHERE inspection_id = {t.entwurf}")
        zu_zeile = eins(f"SELECT MIN(rowid) FROM mat_round_item WHERE round_id = {t.rid}")
        offen_zeile = eins(f"SELECT MIN(rowid) FROM mat_round_item WHERE round_id = {t.offen_rid}")
        geprueft = t.a1["id"]
        inv, qr, serie = c.execute(f"SELECT inventory_no, qr_token, serial_no FROM mat_item WHERE id = {geprueft}").fetchone()
        assert eins(f"SELECT COUNT(*) FROM mat_inspection WHERE item_id = {geprueft} AND completed_at IS NOT NULL")
        assert eins(f"SELECT completed_at IS NULL FROM mat_inspection WHERE id = {t.entwurf}") == 1
        assert None not in (fest_befund, entwurf_befund, fest_anhang, entwurf_anhang, zu_zeile, offen_zeile)
        c.close()
        neu, prod = t.neu["id"], t.ids["hms"]
        spalten = "product_id, folder_id, serial_no, inventory_no, qr_token, created_at, updated_at"
        verboten = [
            f"UPDATE OR REPLACE mat_inspection SET id = {fest} WHERE id = {t.entwurf}",
            f"UPDATE mat_inspection SET id = 900000 WHERE id = {t.entwurf}",
            f"UPDATE mat_inspection SET rowid = rowid + 900000 WHERE id = {t.entwurf}",
            f"UPDATE OR REPLACE mat_inspection_result SET id = {fest_befund} WHERE id = {entwurf_befund}",
            f"UPDATE OR REPLACE mat_inspection_attachment SET id = {fest_anhang} WHERE id = {entwurf_anhang}",
            f"UPDATE OR REPLACE mat_round SET id = {t.rid} WHERE id = {t.offen_rid}",
            f"UPDATE mat_round SET rowid = rowid + 900000 WHERE id = {t.offen_rid}",
            f"UPDATE OR REPLACE mat_round_item SET rowid = {zu_zeile} WHERE rowid = {offen_zeile}",
            f"UPDATE OR REPLACE mat_item SET inventory_no = '{inv}' WHERE id = {neu}",
            f"UPDATE OR REPLACE mat_item SET qr_token = '{qr}' WHERE id = {neu}",
            f"UPDATE OR REPLACE mat_item SET serial_no = lower('{serie}') WHERE id = {neu}",
            f"INSERT OR REPLACE INTO mat_item ({spalten}) SELECT product_id, folder_id, serial_no, 'M-999999', 'qr-neu', "
            f"created_at, updated_at FROM mat_item WHERE id = {geprueft}",
            f"INSERT OR REPLACE INTO mat_item ({spalten}) SELECT product_id, folder_id, 'NM-ANDERS', inventory_no, "
            f"'qr-neu', created_at, updated_at FROM mat_item WHERE id = {geprueft}",
            f"REPLACE INTO mat_item ({spalten}) SELECT {prod}, folder_id, 'NM-ANDERS', 'M-999999', qr_token, created_at, "
            f"updated_at FROM mat_item WHERE id = {geprueft}",
        ]
        for fk, rek in ((True, True), (False, False), (True, False), (False, True)):
            for sql in verboten:
                fehler = _versuch(pfad, sql, fk=fk, rekursiv=rek)
                assert fehler and fehler != "nichts geändert", (fk, rek, sql, fehler)
        # Erlaubt bleibt: Inhalte offener Zeilen, ein ungeprüfter Artikel mit eigenem Schlüssel, Notizen am geprüften.
        for sql in (f"UPDATE mat_inspection SET remarks = 'Platzhalter' WHERE id = {t.entwurf}",
                    f"UPDATE mat_round SET title = 'Platzhalter neu' WHERE id = {t.offen_rid}",
                    f"UPDATE mat_item SET serial_no = 'NM-OFFEN-2' WHERE id = {neu}",
                    f"UPDATE mat_item SET notes = 'Platzhalter' WHERE id = {geprueft}",
                    f"INSERT INTO mat_item ({spalten}) SELECT product_id, folder_id, 'NM-FREI', 'M-999998', 'qr-frei', "
                    f"created_at, updated_at FROM mat_item WHERE id = {geprueft}"):
            assert _versuch(pfad, sql, fk=False, rekursiv=False) is None, sql
            assert _versuch(pfad, sql) is None, sql
        # Die App arbeitet weiter: Entwurf festschreiben, offenen Durchgang abbrechen, Artikel ändern.
        r = festschreiben(t.p, t.entwurf, ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        assert t.w.put(f"{API}/artikel/{neu}", json={"notes": "Platzhalter-Notiz"}).status_code == 200
        r = t.w.post(f"{API}/durchgaenge/{t.offen_rid}/abbrechen", json={"grund": "Platzhalter"})
        assert r.status_code == 200, r.get_json()
    print("Schritt 32 (Trigger) bestanden.")


def test_schritt_32_migration():
    """Frisch und 31 → 32 (Altbestand mit Prüfungen, Durchgängen, Rückruf und Lebenslauf) ergeben dasselbe Schema;
    Schritt 32 ändert keine Zeile (nur die neue, leere Spalte mail_still); ein zweiter Lauf ändert nichts."""
    from test_material_set_rueckbau import _schema, _unterschied
    from test_material_trennung import bis_schritt, endversion, zeilen
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("trigger", "mat_item_schluessel_neu") in schema_frisch and ("trigger", "mat_item_schluessel_aendern") in schema_frisch

    def altbestand(tmp):
        t = _bestand_mit_offenem(tmp)
        r = t.k["katalog"].post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                                json={"title": "Platzhalter-Rückruf", "mail": False})
        assert r.status_code == 201, r.get_json()
        _abruf(t.w, t.a1["id"])
        return t
    with tempfile.TemporaryDirectory() as tmp:
        t = bis_schritt(31)(altbestand, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "31"
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_item_schluessel_neu'").fetchone()
        alt_trigger = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'mat_inspection_zeile'").fetchone()[0]
        assert "completed_at" in alt_trigger
        conn.close()
        vorher = _zeilen_je_tabelle(pfad)
        assert vorher["mat_recall"] and vorher["mat_lebenslauf"] and vorher["mat_inspection"] and vorher["mat_round_item"]
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion() and int(endversion()) >= 32
        schema = _schema(pfad)
        assert schema == schema_frisch, _unterschied(schema, schema_frisch)
        nachher = _zeilen_je_tabelle(pfad)
        rest = dict(nachher)
        assert [z[:-1] for z in rest.pop("mat_recall")] == vorher.pop("mat_recall")
        assert rest == vorher
        assert [z["mail_still"] for z in zeilen(app, "SELECT mail_still FROM mat_recall")] == [None]
        conn = sqlite3.connect(pfad)
        from app.material import models
        conn.execute("BEGIN")
        models._schritt_32(conn)                             # Schritt 32 noch einmal: nichts ändert sich
        conn.commit()
        conn.close()
        assert _schema(pfad) == schema_frisch and _zeilen_je_tabelle(pfad) == nachher
        make_app(tmp)                                        # zweiter Start: nichts ändert sich
        assert _schema(pfad) == schema_frisch
        # Danach geht alles wie zuvor: Abruf, Prüfung.
        _, kennung = _abruf(t.w, t.a1["id"])
        assert kennung.endswith("-000002"), kennung
        r = festschreiben(t.p, t.entwurf, ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
    print("Schritt 32 (Migration) bestanden.")


def test_rueckruf_wieder_offen():
    """Rückruf für alle Artikel, Artikel danach geprüft (erledigt). Ein Antrag nur auf die Seriennummer (Tippfehler):
    Karte und Rückfrage sagen, dass der Rückruf danach wieder offen ist; nach dem Bestätigen ist er offen und das
    Journal vermerkt es. Ein Artikel mit offenem Rückruf und ein gesperrter bekommen den Satz nicht."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau_a4(tmp)
        a = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="TIPPFEHLR")["id"]
        b = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="OFFEN-1")["id"]
        for iid in (a, b):
            _geprueft(t, iid)
        time.sleep(1.1)
        r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe", json={"title": "Platzhalter alle", "mail": False})
        assert r.status_code == 201, r.get_json()
        time.sleep(1.1)
        _geprueft(t, a)
        zustand = lambda iid: [(x["title"], x["zustand"]) for x in t.w.get(f"{API}/artikel/{iid}").json["artikel"]["rueckrufe"]]  # noqa: E731
        assert zustand(a) == [("Platzhalter alle", "erledigt")] and zustand(b) == [("Platzhalter alle", "offen")]
        time.sleep(1.1)
        antraege = {}
        for iid, neu in ((a, "TIPPFEHLER"), (b, "OFFEN-2")):
            r = t.p.post(f"{API}/artikel/{iid}/antrag", json={"serial_no": neu, "begruendung": "Platzhalter Tippfehler"})
            assert r.status_code == 201, r.get_json()
            antraege[iid] = r.json["antrag"]["id"]
        liste = {x["item_id"]: x for x in t.w.get(f"{API}/antraege").json["antraege"]}
        assert liste[a]["rueckruf"]["wieder_offen"] == [{"id": 1, "title": "Platzhalter alle"}], liste[a]["rueckruf"]
        assert liste[a]["rueckruf"]["nicht_mehr"] == liste[a]["rueckruf"]["neu"] == []
        assert liste[b]["rueckruf"]["wieder_offen"] == [], liste[b]["rueckruf"]
        for iid in (a, b):
            r = t.w.post(f"{API}/antraege/{antraege[iid]}/bestaetigen", json={})
            assert r.status_code == 200, r.get_json()
        assert zustand(a) == [("Platzhalter alle", "offen")] and zustand(b) == [("Platzhalter alle", "offen")]
        j = [e for e in t.w.get(f"{API}/artikel/{a}").json["artikel"]["journal"] if e["action"] == "antrag_bestaetigt"]
        assert j[0]["nachher"]["rueckruf_wieder_offen"] == ["Platzhalter alle (Nr. 1)"], j[0]["nachher"]
        j = [e for e in t.w.get(f"{API}/artikel/{b}").json["artikel"]["journal"] if e["action"] == "antrag_bestaetigt"]
        assert "rueckruf_wieder_offen" not in j[0]["nachher"], j[0]["nachher"]
        # Gesperrt bleibt erledigt – kein Satz.
        c = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="GESPERRT-1")["id"]
        _geprueft(t, c)
        assert t.p.post(f"{API}/artikel/{c}/sperren", json={"grund": "rueckruf", "text": "Platzhalter"}).status_code == 200
        r = t.p.post(f"{API}/artikel/{c}/antrag", json={"serial_no": "GESPERRT-2", "begruendung": "Platzhalter"})
        assert r.status_code == 201, r.get_json()
        liste = {x["item_id"]: x for x in t.w.get(f"{API}/antraege").json["antraege"]}
        assert liste[c]["rueckruf"]["wieder_offen"] == [], liste[c]["rueckruf"]
    from app.material.services.beschriftung import FELD
    js = lies("app/material/static/material.js")
    assert FELD["rueckruf_wieder_offen"] == "Rückruf wieder offen (erneut prüfen)"
    assert 'rueckruf_wieder_offen: "Rückruf wieder offen (erneut prüfen)"' in js
    assert "gilt\"} danach wieder als offen – der Artikel muss erneut geprüft werden." in js
    print("Rückruf wieder offen bestanden.")


def test_rueckruf_still_beim_versand():
    """„still“ ist der Stand beim Anlegen: ohne Mailserver angelegt, später mit Mailserver gelesen – weiter „kein
    Mailserver“; mit Mailserver angelegt, später ohne gelesen – kein „still“."""
    from app.material.services import mailprotokoll, rueckruf
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau_a4(tmp)
        a = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="STILL-1")["id"]
        _geprueft(t, a)
        alt = mails_abfangen(rueckruf)
        server = mailprotokoll.MAILSERVER
        try:
            mailprotokoll.MAILSERVER = lambda: False
            r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                          json={"title": "Ohne Server Platzhalter", "serials": "STILL-1", "mail": True})
            assert r.status_code == 201 and r.json["still"] == "kein Mailserver", r.get_json()
            mailprotokoll.MAILSERVER = lambda: True
            r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                          json={"title": "Mit Server Platzhalter", "serials": "STILL-1", "mail": True})
            assert r.status_code == 201 and r.json["still"] is None, r.get_json()
            for konto, server_heute in ((t.mv, True), (t.w, True), (t.mv, False), (t.w, False)):
                mailprotokoll.MAILSERVER = (lambda: True) if server_heute else (lambda: False)
                x = {y["title"]: y["still"] for y in konto.get(f"{API}/produkte/{t.ids['hms']}").json["produkt"]["rueckrufe"]}
                assert x == {"Ohne Server Platzhalter": "kein Mailserver", "Mit Server Platzhalter": None}, (server_heute, x)
        finally:
            mailprotokoll.MAILSERVER = server
            mails_zurueck(alt)
        with t.app.app_context():
            from app import db
            assert [z["mail_still"] for z in db.query("SELECT mail_still FROM mat_recall ORDER BY id")] == ["kein Mailserver", None]
    print("Rückruf „still“ beim Versand bestanden.")


def test_oberflaeche_statisch():
    """7 Journal am Telefon als Karten, 8 Mangeltext im Banner höchstens 100ch, 11 Reiter bei 344 px, 14 Verbesserungen
    der Browserberichte (Artikelseite „Mehr“, „Löschen“ der Produktseite im Menü, abgeschlossene Durchgänge zugeklappt,
    Grund am ausgegrauten „Durchgang abschließen“, Inventarnummer ohne Umbruch, Katalogimport lesbar, Meine PSA am
    Finger, Kontrast auf Rot-hell, Tokens, Begriffe)."""
    js, css = lies("app/material/static/material.js"), lies("app/material/static/material.css")
    # 7
    assert 'data-l="vorher">${seite(j.vorher, f)}</td><td data-l="nachher"' in js
    karte = css[css.index("@container mat-seite (max-width: 600px) {\n  .mat-diff,"):]
    karte = karte[:karte.index("\n}\n")]
    for regel in (".mat-diff, .mat-diff tbody, .mat-diff tr, .mat-diff th, .mat-diff td { display: block; }",
                  ".mat-diff thead { display: none; }", '.mat-diff td[data-l]::before { content: attr(data-l) ": ";',
                  ".mat-diff td.mat-j-vorher.leer { display: none; }", "overflow-wrap: break-word;"):
        assert regel in karte, regel
    # 8 und 11
    assert ".mat-mangel-banner p { margin: 0 0 6px; overflow-wrap: anywhere; max-width: 100ch; }" in css
    assert ".mat-mangel-liste p { margin: 2px 0; overflow-wrap: anywhere; max-width: 100ch; }" in css
    assert "@media (max-width: 350px) { .mat-nav.enger .mat-reiter > a { padding-left: 4px; padding-right: 4px; } }" in css
    # 14: Artikelseite – Verschieben, Lebenslauf, Löschen im Menü „Mehr“, kein Erklärabsatz zwischen den Knopfreihen
    assert "function artikelMehr(a, eintraege) {" in js and '<p class="help mat-nur-touch">Lebenslauf (PDF)' not in js
    assert 'darfPflegen && frei ? "verschieben" : "", darf.grund ? "lebenslauf" : "", darfPflegen && a.darf_loeschen ? "loeschen" : ""' in js
    assert "Prüfen dürfen Prüfer mit Urkundennummer und Prüffreigabe (Häkchen" not in js
    produkt = js[js.index("const produktMenue = "):js.index("] });", js.index("const produktMenue = "))]
    assert 'p.loeschbar && { text: "Löschen", satz: "Nur ohne Artikel dieses Produkts.", attrs: \'data-act="loeschen"\' }' in produkt   # S.menue
    assert """${p.loeschbar ? '<button class="btn secondary small" data-act="loeschen">Löschen</button>' : ""}${produktMenue}""" not in js
    # Prüfungen: laufende oben; die abgeschlossenen seit dem 27.10.2026 auf eigener Seite (Menü „Prüfdurchgänge“,
    # test_material_dg_archiv); ausgegrautes „Durchgang abschließen“ mit Grund
    assert 'rundenKasten($("#pr-runden"), true)' in js and "mat-runden-alt" not in js
    assert "'disabled aria-describedby=\"dg-abschluss\"'" in js and '<p class="help" id="dg-abschluss">' in js
    # Inventarnummer ohne Umbruch, Begriffe, Katalogimport lesbar
    assert '<h1><span class="mat-inv">${esc(a.inventory_no)}</span>' in js
    assert '<h1>Prüfung <span class="mat-inv">${esc(a.inventory_no)}</span>' in js
    assert "<h2>Prüfdurchgang anlegen</h2>" in js and ">Eröffnen</button>" not in js
    assert '(oben ? "Gliederung anlegen" : "Unterordner anlegen")' in js
    assert "function fundstelleLesbar(z) {" in js and "orte.length >= 3 && orte.every(Boolean)" in js
    # Meine PSA am Finger, Kontrast auf Rot-hell, Tokens statt freier Schatten
    touch = css[css.index("/* --- Liste nach dem Merge, Teil A"):]
    assert ".mat-psa-doks .mat-doks > li > a, .mat-psa-titel h2 > a, .mat-psa-knoepfe > a" in touch
    assert "display: inline-flex; align-items: center; min-height: 44px; }" in touch
    # Kontrast auf Rot-hell seit UI/UX A5 als app-weite Regel in app.css („Text auf hellen Flächen“, test_module_uiux_u1b).
    app_css = lies("app/static/css/app.css")
    assert ":is(.muted, .help, .sub, small) { color: var(--anthrazit); }" in app_css
    assert ":is(a:not(.btn), .lnk) { color: var(--rot-auf-flaeche); }" in app_css
    assert "rgba(0, 0, 0, .16)" not in css and "rgba(0, 0, 0, .18)" not in css and "font-size: .85rem" not in css
    print("Oberfläche (statisch) bestanden.")


def test_importherkunft_gekuerzt():
    """Die Herkunft einer Katalogdatei (quelle) höchstens 200 Zeichen – am Wortende mit „…“, nicht mitten im Wort."""
    from app.material.services.importer import _gekuerzt
    assert _gekuerzt("kurz", 200) == "kurz"
    lang = "Karabiner, Selbstsicherungen, Verbindungsmittel " * 10
    k = _gekuerzt(lang, 200)
    assert len(k) <= 200 and k.endswith("\u00a0…") and k[:-2] == lang[:len(k) - 2] and lang[len(k) - 2] == " ", k
    assert _gekuerzt("x" * 300, 200) == "x" * 198 + "\u00a0…"
    print("Importherkunft bestanden.")


if __name__ == "__main__":
    test_kennung_nach_zurueckspielen()
    test_head_und_bremse()
    test_pruefseite_texte()
    test_schritt_32_trigger()
    test_schritt_32_migration()
    test_rueckruf_wieder_offen()
    test_rueckruf_still_beim_versand()
    test_oberflaeche_statisch()
    test_importherkunft_gekuerzt()
