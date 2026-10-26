"""Nachbesserung vor dem Merge (26.10.2026, Teil A):  python tests/test_material_vor_merge.py  oder pytest

R1: Ein Artikel kommt per bestätigtem Änderungsantrag (Seriennummer oder Produkt) in einen laufenden Rückruf – als
Prüfung zum Rückruf zählt nur eine nach dem Antrag (Banner, Marke, Übersicht, Lebenslauf). Rückruf ohne Mailserver sagt
ehrlich, dass keine Mail hinausging (still). DEMO-Konten zählen nicht als Material-Verwaltung. „Bald fällig ab … Tagen“
nur 0–365; gespeichert = angezeigt = wirksam. Alles Platzhalter."""
import os
import re
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


if __name__ == "__main__":
    test_r1_rueckruf_nach_antrag()
    test_rueckruf_ohne_mailserver()
    test_demo_konto_keine_material_verwaltung()
    test_bald_faellig_bereich()
    print("Alle Tests der Nachbesserung vor dem Merge bestanden.")
