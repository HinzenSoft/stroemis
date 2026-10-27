"""Nachbesserung vor dem Merge (26.10.2026, Teil A):  python tests/test_material_vor_merge.py  oder pytest

R1: Ein Artikel kommt per bestätigtem Änderungsantrag (Seriennummer oder Produkt) in einen laufenden Rückruf – als
Prüfung zum Rückruf zählt nur eine nach dem Antrag (Banner, Marke, Übersicht, Lebenslauf). Rückruf ohne Mailserver sagt
ehrlich, dass keine Mail hinausging (still). DEMO-Konten zählen nicht als Material-Verwaltung. „Bald fällig ab … Tagen“
nur 0–365; gespeichert = angezeigt = wirksam. Schritt 30: Kennungen und Kontoverweise festgeschriebener Nachweise auch
gegen SQL von Hand („SET rowid“, INSERT OR REPLACE ins Journal, mit und ohne recursive_triggers/Fremdschlüssel); frisch,
29 → 30 mit Altbestand, zweiter Lauf. Alles Platzhalter."""
import os
import re
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (make_app, mails_abfangen, mails_zurueck, neuer_artikel, neues_konto,  # noqa: E402
                           pdf_seiten, umgebung)
from test_material_a4_n5 import _geprueft, aufbau  # noqa: E402
from test_material_produktwechsel import produkt_neu  # noqa: E402

API = "/api/material"


def _rueckruf_am_artikel(c, iid):
    return [(r["title"], r["zustand"], r["grund"]) for r in c.get(f"{API}/artikel/{iid}").json["artikel"]["rueckrufe"]]


def _antrag_bestaetigt(t, iid, **wuensche):
    r = t.p.post(f"{API}/artikel/{iid}/antrag", json=dict(wuensche, begruendung="Platzhalter Tippfehler"))
    assert r.status_code == 201, r.get_json()
    r = t.w.post(f"{API}/antraege/{r.json['antrag']['id']}/bestaetigen", json={})
    assert r.status_code == 200, r.get_json()


def _lebenslauf(t, tmp, iid):
    r = t.w.get(f"/materialablage/artikel/{iid}/lebenslauf.pdf")
    assert r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code
    pfad = os.path.join(tmp, f"ll_{iid}.pdf")
    with open(pfad, "wb") as fh:
        fh.write(r.data)
    return " ".join(" ".join(pdf_seiten(pfad)).split())


def test_r1_rueckruf_nach_antrag():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        mit = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="R1-ALT")["id"]          # Prüfung zwischen Rückruf und Antrag
        ohne = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="R1-KONTROLLE")["id"]   # keine Prüfung dazwischen
        rolle = produkt_neu(t.mv, category_id=t.ids["karabiner"], model="Rolle Platzhalter", article_no="RP-1",
                            material_kind="metall_hardware", interval_months=12)
        anders = neuer_artikel(t.w, rolle, t.ga, serial_no="R1-NEU3")["id"]             # kommt per Produktwechsel hinein
        for iid in (mit, ohne, anders):
            _geprueft(t, iid)
        time.sleep(1.1)                                      # gleiche Sekunde zählt als „vorher“
        r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                      json={"title": "Rückruf Platzhalter", "description": "Platzhalter",
                            "serials": "R1-NEU\nR1-NEU2\nR1-NEU3", "mail": False})
        assert r.status_code == 201, r.get_json()
        time.sleep(1.1)
        _geprueft(t, mit)                                    # damals nicht betroffen – kein Hinweis in der Prüfung
        _geprueft(t, anders)
        time.sleep(1.1)
        _antrag_bestaetigt(t, mit, serial_no="R1-NEU")
        _antrag_bestaetigt(t, ohne, serial_no="R1-NEU2")
        _antrag_bestaetigt(t, anders, product_id=t.ids["hms"])
        for iid in (mit, ohne, anders):
            assert _rueckruf_am_artikel(t.w, iid) == [("Rückruf Platzhalter", "offen", None)], (iid, _rueckruf_am_artikel(t.w, iid))
        # Marke in der Ordnerliste, Zahlen der Übersicht und der Produktseite, Lebenslauf.
        marke = {a["id"]: a["rueckruf"] for a in t.w.get(f"{API}/ordner/{t.ga}").json["ordner"]["artikel"]}
        assert marke[mit] == marke[ohne] == marke[anders] == "Rückruf Platzhalter", marke
        uebersicht = [(x["title"], x["betroffen"], x["offen"]) for x in t.w.get(f"{API}/start").json["rueckrufe"]]
        assert uebersicht == [("Rückruf Platzhalter", 3, 3)], uebersicht
        text = _lebenslauf(t, tmp, mit)
        assert "für diesen Artikel offen" in text and "nach dem Rückruf geprüft" not in text, text[:3000]
        # Erst eine Prüfung nach dem Antrag erledigt den Rückruf für den Artikel.
        time.sleep(1.1)
        _geprueft(t, mit)
        assert _rueckruf_am_artikel(t.w, mit) == [("Rückruf Platzhalter", "erledigt", "geprueft")]
        assert _rueckruf_am_artikel(t.w, ohne) == [("Rückruf Platzhalter", "offen", None)]
        uebersicht = [(x["title"], x["betroffen"], x["offen"]) for x in t.w.get(f"{API}/start").json["rueckrufe"]]
        assert uebersicht == [("Rückruf Platzhalter", 3, 2)], uebersicht
        assert "erledigt – nach dem Rückruf geprüft" in _lebenslauf(t, tmp, mit)
        # Ein abgelehnter Antrag verschiebt nichts: Die Prüfung nach dem Rückruf zählt weiter.
        r = t.p.post(f"{API}/artikel/{mit}/antrag", json={"serial_no": "R1-ANDERS", "begruendung": "Platzhalter"})
        assert r.status_code == 201, r.get_json()
        r = t.w.post(f"{API}/antraege/{r.json['antrag']['id']}/ablehnen", json={"antwort": "Platzhalter"})
        assert r.status_code == 200, r.get_json()
        assert _rueckruf_am_artikel(t.w, mit) == [("Rückruf Platzhalter", "erledigt", "geprueft")]
    print("R1 bestanden.")


def test_rueckruf_ohne_mailserver():
    """Verbesserung 1: Ohne Mailserver (bzw. unter der Umgebungssperre) sagt die Antwort „still“ – die Zählung bleibt."""
    from app.material.services import erinnerung, mailprotokoll, rueckruf
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a = neuer_artikel(t.w, t.ids["hms"], t.ga, serial_no="STILL-1")["id"]
        _geprueft(t, a)
        alt = mails_abfangen(rueckruf)
        try:
            mailprotokoll.MAILSERVER = lambda: False                  # wie der lokale Server ohne SMTP_HOST
            r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                          json={"title": "Still Platzhalter", "serials": "STILL-1", "mail": True})
            assert r.status_code == 201 and r.json["mail"] is True and r.json["still"] == "kein Mailserver", r.get_json()
            assert r.json["empfaenger"] > 0
            x = [y for y in t.mv.get(f"{API}/produkte/{t.ids['hms']}").json["produkt"]["rueckrufe"]
                 if y["title"] == "Still Platzhalter"][0]
            assert x["still"] == "kein Mailserver" and x["mail_failed"] == x["mail_count"] + x["mail_failed"] > 0, x
            r = t.w.get(f"{API}/produkte/{t.ids['hms']}").json["produkt"]["rueckrufe"]
            assert [y["still"] for y in r if y["title"] == "Still Platzhalter"] == ["kein Mailserver"]
            mailprotokoll.MAILSERVER = lambda: True
            gesperrt = erinnerung.gesperrt
            erinnerung.gesperrt = lambda: True
            try:
                r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                              json={"title": "Sperre Platzhalter", "serials": "STILL-1", "mail": True})
                assert r.status_code == 201 and r.json["still"] == "Umgebungssperre", r.get_json()
            finally:
                erinnerung.gesperrt = gesperrt
            r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                          json={"title": "Laut Platzhalter", "serials": "STILL-1", "mail": True})
            assert r.status_code == 201 and r.json["still"] is None, r.get_json()
            r = t.mv.post(f"{API}/produkte/{t.ids['hms']}/rueckrufe",
                          json={"title": "Ohne Platzhalter", "serials": "STILL-1", "mail": False})
            assert r.status_code == 201 and r.json["mail"] is False and r.json["still"] is None, r.get_json()
        finally:
            mails_zurueck(alt)
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "app/material/static/material.js"), encoding="utf-8").read()
    assert ': r.still ? `Es ging keine Mail hinaus – ${rrStill(r.still)}.`' in js
    assert "if (r.still && r.mail_failed === n)" in js and "if (r.still) return `Mail an" in js
    assert '"kein Mailserver": "kein Mailserver eingerichtet", Umgebungssperre:' in js
    print("Rückruf ohne Mailserver bestanden.")


def test_demo_konto_keine_material_verwaltung():
    """Verbesserung 2: Ein DEMO-Konto mit Stufe Verwaltung verschluckt den Rückfall auf die Plattform-Verwaltung nicht."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        from test_material import _KONTEN, _konten, anmelden
        _KONTEN.pop(app, None)
        _konten(app)["adm"] = anmelden(app, "admin@example.org", "geheim123")
        _, demo_id = neues_konto(app, "demo-mv@example.invalid", rechte={"material": 2})
        from app import db
        from app.material.services import rechte
        with app.app_context():
            adm_id = db.query("SELECT id FROM users WHERE email = 'admin@example.org'", one=True)["id"]
            assert [u["id"] for u in rechte.material_verwaltung_konten()] == [adm_id]
        _, echt_id = neues_konto(app, "mv@example.org", rechte={"material": 2})
        with app.app_context():
            assert [u["id"] for u in rechte.material_verwaltung_konten()] == [echt_id]
            assert demo_id != echt_id
    print("DEMO-Konto der Material-Verwaltung bestanden.")


def test_bald_faellig_bereich():
    """Befund 2 (übrige Module): Werte außerhalb 0–365 lehnt die Leitstelle mit 400 ab; was gespeichert ist, wird
    angezeigt und gilt – auch in einem Arbeitsprozess, der vorher einen anderen Wert hatte."""
    from app import db, einstellungen
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        url = "/api/admin/einstellungen"

        def feld(d):
            return [f for f in d["felder"] if f["schluessel"] == "MATERIAL_BALD_FAELLIG_TAGE"][0]
        for roh in ("-5", "366", "1000", "abc", "1.5"):
            r = adm.put(url, json={"werte": {"MATERIAL_BALD_FAELLIG_TAGE": roh}})
            assert r.status_code == 400, (roh, r.get_json())
            assert "zwischen 0 und 365" in r.json["error"] or "braucht eine Zahl" in r.json["error"], r.json
        assert feld(adm.get(url).json)["quelle"] != "gespeichert"
        assert w.get(f"{API}/start").json["schwelle_tage"] == 30
        for roh, zahl in (("365", 365), ("0", 0), (" 045 ", 45)):
            r = adm.put(url, json={"werte": {"MATERIAL_BALD_FAELLIG_TAGE": roh}})
            assert r.status_code == 200, r.get_json()
            f = feld(r.json)
            assert (f["wert"], f["quelle"], f["bereich"]) == (str(zahl), "gespeichert", [0, 365]), f
            assert w.get(f"{API}/start").json["schwelle_tage"] == zahl
        # Ein unbrauchbarer Wert aus der Zeit vor der Prüfung (von Hand in der Datenbank): nicht angezeigt, nicht
        # wirksam – in jedem Arbeitsprozess der Grundstand, nicht der zuletzt geltende Wert (hier 45).
        with app.app_context():
            db.execute("UPDATE einstellungen SET wert = '-5' WHERE schluessel = 'MATERIAL_BALD_FAELLIG_TAGE'")
        f = feld(adm.get(url).json)
        assert (f["wert"], f["quelle"]) == ("30", "vorgabe"), f
        assert w.get(f"{API}/start").json["schwelle_tage"] == 30
        with app.app_context():
            assert einstellungen.NACH_SCHLUESSEL["MATERIAL_BALD_FAELLIG_TAGE"].wert("1000") is None
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app/static/js/admin.js"),
              encoding="utf-8").read()
    assert re.search(r'const bereich = f\.bereich \? ` min="\$\{Number\(f\.bereich\[0\]\)\}"', js)
    print("„Bald fällig“ 0–365 bestanden.")


def _versuch(pfad, sql, args=(), fk=True, rekursiv=True):
    """Eine Anweisung an einer eigenen Verbindung, immer zurückgerollt: None, wenn sie durchging (und etwas änderte),
    sonst die Meldung der Datenbank."""
    c = sqlite3.connect(pfad, isolation_level=None)
    c.execute(f"PRAGMA foreign_keys = {'ON' if fk else 'OFF'}")
    c.execute(f"PRAGMA recursive_triggers = {'ON' if rekursiv else 'OFF'}")
    c.execute("BEGIN")
    try:
        c.execute(sql, args)
        return None if c.execute("SELECT changes()").fetchone()[0] else "nichts geändert"
    except sqlite3.Error as exc:
        return str(exc)
    finally:
        c.execute("ROLLBACK")
        c.close()


def test_schritt_30_trigger():
    """Befund 1 der Sicherheitsprüfung vor dem Merge: jede Änderung der Kennung festgeschriebener Nachweise (auch über
    rowid), Kontoverweise nur auf NULL, kein INSERT OR REPLACE im Journal – mit der Verbindung der App und mit der
    Vorgabe des sqlite3-Werkzeugs. Was die App selbst tut (Konto löschen setzt Verweise auf NULL), geht weiter."""
    from test_material_mailprotokoll import einfuegen
    from test_material_setprotokolle import _haupt
    from test_material import H, festschreiben, jpeg, starten
    with tempfile.TemporaryDirectory() as tmp:
        t = _haupt(tmp)                                      # abgeschlossener Durchgang mit Prüfungen und Set-Protokollen
        pr = starten(t.p, t.d1["id"]).json["pruefung"]
        r = t.p.post(f"{API}/pruefungen/{pr['id']}/anhaenge", headers=H, content_type="multipart/form-data",
                     data={"file": [(jpeg(), "scan.jpg")], "art": "foto", "titel": "Platzhalter-Scan"})
        assert r.status_code in (200, 201), r.get_json()
        assert festschreiben(t.p, pr["id"], ergebnis="einsatzbereit").status_code == 200
        r = t.w.post(f"{API}/artikel/{t.a1['id']}/mangel", headers=H, json={"beschreibung": "Platzhalter-Mangel"})
        assert r.status_code in (200, 201), r.get_json()
        einfuegen(t.app, "k-platzhalter")
        r = t.p.post(f"{API}/artikel/{t.a2['id']}/antrag", json={"serial_no": "SP-NEU", "begruendung": "Platzhalter"})
        assert r.status_code == 201, r.get_json()
        pfad = os.path.join(tmp, "stroemis.db")
        c = sqlite3.connect(pfad)
        eins = lambda sql: c.execute(sql).fetchone()[0]                                        # noqa: E731
        fest = eins("SELECT id FROM mat_inspection WHERE locked_at IS NOT NULL AND id IN "
                    "(SELECT inspection_id FROM mat_inspection_attachment) ORDER BY id LIMIT 1")
        letzte = eins("SELECT MAX(id) FROM mat_inspection WHERE completed_at IS NOT NULL")
        geprueft = eins("SELECT item_id FROM mat_inspection WHERE completed_at IS NOT NULL ORDER BY id LIMIT 1")
        anderes = eins("SELECT MAX(id) FROM users")
        assert eins(f"SELECT COUNT(*) FROM mat_round WHERE id = {t.rid} AND closed_on IS NOT NULL") == 1
        assert eins("SELECT COUNT(*) FROM mat_round_setprotokoll") > 0 and eins("SELECT COUNT(*) FROM mat_defect_report")
        assert eins(f"SELECT COUNT(*) FROM mat_round_item WHERE round_id = {t.rid} AND excluded_by IS NOT NULL")
        c.close()
        neu = "rowid + 900000"
        kennung = [
            f"UPDATE mat_inspection SET id = 900000 WHERE id = {letzte}",
            f"UPDATE mat_inspection SET rowid = {neu} WHERE id = {fest}",
            "UPDATE mat_audit SET id = 900000 WHERE id = (SELECT MIN(id) FROM mat_audit)",
            f"UPDATE mat_audit SET rowid = {neu} WHERE id = (SELECT MIN(id) FROM mat_audit)",
            f"UPDATE mat_inspection_attachment SET rowid = {neu} WHERE inspection_id = {fest}",
            f"UPDATE mat_inspection_attachment SET id = 900000 WHERE inspection_id = {fest}",
            f"UPDATE mat_inspection_result SET rowid = {neu} WHERE inspection_id = {fest}",
            f"UPDATE mat_defect_report SET rowid = {neu}",
            f"UPDATE mat_round SET rowid = {neu} WHERE id = {t.rid}",
            f"UPDATE mat_round_item SET rowid = {neu} WHERE round_id = {t.rid}",
            f"UPDATE mat_round_setprotokoll SET rowid = {neu}",
            f"UPDATE mat_item_change SET rowid = {neu}",
            f"UPDATE mat_mail_fehler SET rowid = {neu}",
            f"UPDATE mat_item SET rowid = {neu} WHERE id = {geprueft}",
            f"UPDATE mat_product SET rowid = {neu} WHERE id = {t.ids['hms']}",
            # Kontoverweise und Prüfpunkt: nur auf NULL
            f"UPDATE mat_audit SET user_id = {anderes} WHERE id = (SELECT MIN(id) FROM mat_audit WHERE user_id IS NOT NULL "
            f"AND user_id <> {anderes})",
            f"UPDATE mat_round SET opened_by = {anderes} WHERE id = {t.rid}",
            f"UPDATE mat_round SET closed_by = {anderes} WHERE id = {t.rid}",
            f"UPDATE mat_inspection_attachment SET uploaded_by = {anderes} WHERE inspection_id = {fest}",
            f"UPDATE mat_inspection_result SET checklist_item_id = (SELECT MAX(id) FROM mat_checklist_item) "
            f"WHERE inspection_id = {fest} AND checklist_item_id IS NOT (SELECT MAX(id) FROM mat_checklist_item)",
            # Journal ersetzen (ohne recursive_triggers griffe der Lösch-Trigger nicht)
            "INSERT OR REPLACE INTO mat_audit (id, entity, entity_id, user_id, user_name, action, before_json, after_json, "
            "created_at) SELECT id, entity, entity_id, user_id, 'Ersetzt', 'ersetzt', NULL, NULL, created_at FROM mat_audit "
            "WHERE id = (SELECT MIN(id) FROM mat_audit)",
        ]
        kennung.append(f"UPDATE mat_round_item SET excluded_by = {anderes} WHERE round_id = {t.rid} "
                       "AND excluded_by IS NOT NULL")
        for fk, rek in ((True, True), (False, False), (True, False), (False, True)):
            for sql in kennung:
                fehler = _versuch(pfad, sql, fk=fk, rekursiv=rek)
                assert fehler and fehler != "nichts geändert", (fk, rek, sql, fehler)
        # Was erlaubt bleibt: Kontoverweise auf NULL (Konto gelöscht), eine Zeile ohne Änderung der Kennung.
        for sql in ("UPDATE mat_audit SET user_id = NULL WHERE user_id IS NOT NULL",
                    f"UPDATE mat_round SET opened_by = NULL, closed_by = NULL WHERE id = {t.rid}",
                    f"UPDATE mat_inspection_attachment SET uploaded_by = NULL WHERE inspection_id = {fest}",
                    f"UPDATE mat_inspection_result SET checklist_item_id = NULL WHERE inspection_id = {fest}",
                    f"UPDATE mat_round_item SET excluded_by = NULL WHERE round_id = {t.rid} AND excluded_by IS NOT NULL",
                    "UPDATE mat_mail_fehler SET erledigt_at = '2026-10-26T12:00:00+00:00', erledigt_von_name = 'Test'",
                    f"UPDATE mat_item SET notes = 'Platzhalter' WHERE id = {geprueft}"):
            assert _versuch(pfad, sql) is None, sql
        # Die App löscht ein Konto mit Journal, Anhang, Durchgang und Prüfungen (Verweise werden NULL).
        pid = t.k["pruefer_id"]
        r = t.adm.delete(f"/api/admin/users/{pid}", headers=H)
        assert r.status_code == 200, r.get_json()
        c = sqlite3.connect(pfad)
        assert c.execute("SELECT COUNT(*) FROM mat_audit WHERE user_id = ?", (pid,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM mat_inspection_attachment WHERE uploaded_by = ?", (pid,)).fetchone()[0] == 0
        c.close()
    print("Schritt 30 (Trigger) bestanden.")


def _zeilen_je_tabelle(pfad, ohne_leere=()):
    """Zeilen je mat_-Tabelle; Tabellen aus ohne_leere fehlen, wenn sie leer sind (seit Schritt 31: mat_lebenslauf, die
    ein Stand 29 noch nicht hat)."""
    c = sqlite3.connect(pfad)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat_%' AND name NOT LIKE "
                          "'%fts%' AND name <> 'mat_meta' ORDER BY name"):
        out[t] = c.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
        if t in ohne_leere and not out[t]:
            del out[t]
    c.close()
    return out


def test_schritt_30_migration():
    """Frisch und 29 → 30 (mit Altbestand: abgeschlossener Durchgang, Set-Protokolle, Journal) ergeben dasselbe Schema;
    Schritt 30 ändert keine Zeile; ein zweiter Lauf ändert nichts."""
    from test_material_set_rueckbau import _schema, _unterschied
    from test_material_setprotokolle import _haupt
    from test_material_trennung import bis_schritt, endversion, zeilen
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("trigger", "mat_audit_zeile") in schema_frisch and ("trigger", "mat_round_konto") in schema_frisch
    with tempfile.TemporaryDirectory() as tmp:
        bis_schritt(29)(_haupt, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "29"
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_audit_zeile'").fetchone()
        conn.close()
        vorher = _zeilen_je_tabelle(pfad)
        assert vorher["mat_round_setprotokoll"] and vorher["mat_audit"] and vorher["mat_inspection"]
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        schema = _schema(pfad)
        assert schema == schema_frisch, _unterschied(schema, schema_frisch)
        assert _zeilen_je_tabelle(pfad, ("mat_lebenslauf",)) == vorher
        conn = sqlite3.connect(pfad)
        n = conn.total_changes
        for sql in models.SCHRITT_30:
            conn.execute(sql)
        assert conn.total_changes == n
        conn.close()
        make_app(tmp)                                        # zweiter Start: nichts ändert sich
        assert _schema(pfad) == schema_frisch and _zeilen_je_tabelle(pfad, ("mat_lebenslauf",)) == vorher
    print("Schritt 30 (Migration) bestanden.")


def _lies(rel):
    return open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel), encoding="utf-8").read()


def _coarse_bloecke(css):
    """Inhalt aller @media (pointer: coarse)-Blöcke (Klammern gezählt)."""
    out = []
    for m in re.finditer(r"@media \(pointer: coarse\)\s*\{", css):
        i, tiefe = m.end(), 1
        while tiefe:
            tiefe += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return "\n".join(out)


def test_oberflaeche_statisch():
    """B1 Jahresbericht als Karte bis 760 px, B2 Fokus zentral in dialog()/confirm(), B3 Tippflächen und B4 Toast nur
    unter pointer: coarse (Messungen im Browser: Bericht der Nachbesserung)."""
    js = _lies("app/material/static/material.js")
    css = _lies("app/material/static/material.css")
    app_css = _lies("app/static/css/app.css")
    fg_css = _lies("app/material/static/freigaben.css")
    # B1: beide breiten Tabellen tragen die Klasse, die Containerabfrage macht sie bis 760 px zur Karte.
    assert '"mat-bericht-ordner mat-bericht-breit")' in js and '"mat-bericht-breit") : leer("Im Jahr kein Prüfdurchgang' in js
    assert "@container mat-seite (max-width: 760px) {\n  #mat-inhalt table.list.mat-bericht-breit," in css
    # B2: dialog/confirm sind eigene Hüllen, die den Auslöser merken; der alte Einzelfall ist weg.
    assert "const { esc, api, toast } = S;" in js and "function dialog(html, onOpen) {" in js
    assert "if (dlgEl && !dlgEl.open && !dlgZiel) dlgZiel = fokusZiel();" in js
    assert "return S.confirm(text, okLabel, neinLabel, opt).then((ja) => {" in js
    assert 'dlg.addEventListener("close", () => { if (knopf.isConnected) knopf.focus(); }, { once: true });' not in js
    # B3/B4: nur unter pointer: coarse; die Notiz-Regel steht hinter der Grundregel (gleiche Spezifität).
    assert ".mf-notiz > summary { padding: 11px 0; }" in _coarse_bloecke(fg_css)
    assert fg_css.index("@media (pointer: coarse) { .mf-notiz > summary") > fg_css.index(".mf-notiz > summary { cursor")
    assert ".mat-pruefen-form .btn { min-height: 44px; }" in _coarse_bloecke(css)
    touch = _coarse_bloecke(app_css)
    assert ".us-aktionen .btn { min-height: 44px; }" in touch
    assert "#toast, #toast[popover] { bottom: auto; top: calc(var(--topbar) + 12px" in touch
    assert "#toast[popover].bei-dialog { left: var(--toast-x, 50%); bottom: auto;" in app_css     # Dialog geht vor
    # Nachtrag 1: kein grauer GESPERRT-Banner, wenn eine offene Mangelmeldung sperrt und ihr roter Banner steht.
    assert 'const sperreDurchMangel = /^Mangel gemeldet am /.test(a.lock_reason || "") && offeneMaengel.length > 0;' in js
    # Seit dem Nachtrag V7 (Runde 3) auch nicht, wenn der Sperrgrund als Zeile im Mangel-Banner steht (sperreImMangel).
    assert '${a.status === "gesperrt" && !sperreDurchMangel && !sperreImMangel ? `<p class="mat-banner s-gesperrt">GESPERRT' in js
    assert 'offeneMaengel.map((m, i) => mangelBanner(m, sperreImMangel && i === 0 ? sperrText || "" : null)).join("")' in js
    # Nachtrag 2: der Sperr-Banner ist rot wie der Mangel-Banner; Marke, Kachel und Zahl bleiben.
    assert ".mat-banner.s-gesperrt { background: var(--rot); }" in css
    assert ".s-gesperrt.mat-status { background: var(--mat-gesperrt); }" in css
    assert ".mat-zahl.s-gesperrt { background: var(--mat-gesperrt); }" in css
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_r1_rueckruf_nach_antrag()
    test_rueckruf_ohne_mailserver()
    test_demo_konto_keine_material_verwaltung()
    test_bald_faellig_bereich()
    test_schritt_30_trigger()
    test_schritt_30_migration()
    test_oberflaeche_statisch()
    print("Alle Tests der Nachbesserung vor dem Merge bestanden.")
