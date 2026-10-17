"""Tests zu den Rückrufen im Modul „Material“ (Lieferung 4):  python tests/test_material_rueckruf.py

Ein Katalogpfleger legt am Produkt einen Rückruf an. Der Hinweis steht am Produkt, an den betroffenen Artikeln und
auf der Übersicht; eine Mail geht an alle Materialwarte und an die Prüfer betroffener Artikel. Gesperrt wird nicht
automatisch – Prüfer sperren mit dem Grund „Rückruf“. Alle Namen, Hersteller, Titel und Seriennummern hier sind
erfunden und nur für den Test da."""
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, abschluss, anmelden, gliederung, katalog_grund, neuer_artikel,  # noqa: E402
                           pruef_formulare, starten, umgebung, unterschreiben, zweiter_pruefer)

RR = "/api/material/produkte/{}/rueckrufe"


def post_abfangen(scheitert=()):
    """Mails direkt statt im Hintergrund und nur in eine Liste – an Adressen aus „scheitert“ geht nichts hinaus."""
    from app.material.services import rueckruf
    post = []
    alt = (rueckruf.HINTERGRUND, rueckruf.send_mail)
    rueckruf.HINTERGRUND = lambda f, *a: f(*a)
    rueckruf.send_mail = lambda an, betreff, inhalt: post.append((an, betreff, inhalt)) or an not in scheitert
    return post, alt


def post_zurueck(alt):
    from app.material.services import rueckruf
    rueckruf.HINTERGRUND, rueckruf.send_mail = alt


def aufbau(tmp):
    """Umgebung mit Katalog, Formularen, einer Gliederung mit Lager und drei Karabinern (HMS Beta)."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    pruef_formulare(k["katalog"], ids)
    w = k["wart"]
    gid, system = gliederung(w)
    lager = w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": gid}).json["ordner"]["id"]
    art = {s: neuer_artikel(w, ids["hms"], lager, serial_no=s)["id"] for s in ("RR-1", "rr-2", "RR-3")}
    return app, k, ids, system, lager, art


def produkt_anlegen(kp, ids, modell, artikelnummer):
    """Ein weiteres erfundenes Metallprodukt in der Kategorie Karabiner (generisches Formular)."""
    r = kp.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk", "model": modell,
                                                "article_no": artikelnummer, "material_kind": "metall_hardware",
                                                "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


def pruefen(c, iid):
    """Eine Prüfung mit dem Ergebnis „einsatzbereit“ (Karabiner: die Sollwerte sind vorbelegt)."""
    r = starten(c, iid)
    assert r.status_code in (200, 201), r.get_json()
    r = abschluss(c, r.json["pruefung"]["id"], ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()
    return r.json["pruefung"]["id"]


def konto(app, adm, mail, **felder):
    r = adm.post("/api/admin/users", json=dict({"email": mail, "password": "passwort1", "name": mail.split("@")[0]}, **felder))
    assert r.status_code == 201, (mail, r.get_json())
    return anmelden(app, mail, "passwort1"), r.json["user"]["id"]


def anlegen(c, pid, **d):
    return c.post(RR.format(pid), json=dict({"title": "Testrückruf"}, **d))


def zeile(tmp, sql, args=()):
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    conn.row_factory = sqlite3.Row
    try:
        r = conn.execute(sql, args).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def schreiben(tmp, sql, args=()):
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    try:
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


# --- Rechte und Eingaben ------------------------------------------------------------------------------------

def test_rechte_und_eingaben():
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            hms = ids["hms"]
            # Anlegen nur Katalogpfleger und Verwaltung – nicht Materialwart, Führungskraft, Prüfer, Nutzer.
            for c in (k["wart"], k["fuehrung"], k["pruefer"], k["nutzer"]):
                r = anlegen(c, hms)
                assert r.status_code == 403, r.get_json()
            assert app.test_client().post(RR.format(hms), json={"title": "x"}, headers=H).status_code == 401
            r = anlegen(k["katalog"], hms, title="Rückruf vom Katalogpfleger", mail=False)
            assert r.status_code == 201, r.get_json()
            ruid = r.json["rueckruf"]["id"]
            assert r.json["rueckruf"]["created_by_name"] == "katalog" and r.json["rueckruf"]["aktiv"]
            assert anlegen(k["adm"], hms, title="Rückruf der Verwaltung", mail=False).status_code == 201
            # Lesen: alle mit Zugang zum Modul; ein Konto ohne Modulrecht nicht, ohne Anmeldung niemand.
            for c in (k["fuehrung"], k["wart"], k["pruefer"], k["katalog"], k["adm"]):
                assert c.get(RR.format(hms)).status_code == 200
                assert c.get("/api/material/rueckrufe").status_code == 200
                assert len(c.get(f"/api/material/produkte/{hms}").json["produkt"]["rueckrufe"]) == 2
            assert k["nutzer"].get(RR.format(hms)).status_code == 403
            assert k["nutzer"].get("/api/material/rueckrufe").status_code == 403
            assert app.test_client().get(RR.format(hms)).status_code == 401
            assert k["fuehrung"].get(RR.format(99999)).status_code == 404
            # Beenden: ebenso nur Katalogpfleger und Verwaltung – und nur mit Vermerk.
            url = f"/api/material/rueckrufe/{ruid}/beenden"
            for c in (k["wart"], k["fuehrung"], k["pruefer"], k["nutzer"]):
                assert c.post(url, json={"vermerk": "x"}).status_code == 403
            r = k["katalog"].post(url, json={"vermerk": "  "})
            assert r.status_code == 400 and "Vermerk" in r.json["error"], r.get_json()
            r = k["katalog"].post(url, json={"vermerk": "Hersteller hat Entwarnung gegeben"})
            assert r.status_code == 200 and not r.json["rueckruf"]["aktiv"], r.get_json()
            assert r.json["rueckruf"]["close_note"] == "Hersteller hat Entwarnung gegeben"
            assert r.json["rueckruf"]["closed_by_name"] == "katalog"
            r = k["adm"].post(url, json={"vermerk": "noch einmal"})
            assert r.status_code == 409 and "schon beendet" in r.json["error"], r.get_json()
            assert k["adm"].post("/api/material/rueckrufe/99999/beenden", json={"vermerk": "x"}).status_code == 404

            # Eingaben: Titel Pflicht, Link nur http(s), Seriennummern als Text, Mail ja/nein, Produkt muss es geben.
            kp = k["katalog"]
            for falsch, teil in (({"title": " "}, "Titel"), ({"title": "x" * 201}, "Titel"),
                                 ({"url": "javascript:alert(1)"}, "http"), ({"url": "ftp://example.org/x"}, "http"),
                                 ({"url": "https://example.org/" + "x" * 500}, "zu lang"),
                                 ({"description": "x" * 4001}, "Beschreibung"), ({"serials": ["RR-1", 3]}, "Text"),
                                 ({"serials": "A" * 81}, "zu lang"), ({"serials": 17}, "Text"),
                                 ({"mail": "vielleicht"}, "ja oder nein")):
                r = anlegen(kp, hms, **falsch)
                assert r.status_code == 400 and teil in r.json["error"], (falsch, r.get_json())
            assert anlegen(kp, 99999).status_code == 404
            # „www.…“ bekommt https://; Leerzeilen, Leerraum und doppelte Seriennummern (Groß/klein) fallen weg.
            r = anlegen(kp, hms, url="www.example.org/rueckruf", serials=" RR-1 \n\nrr-1\nRR-2\n", mail=False,
                        description="Zeile eins\nZeile zwei")
            assert r.status_code == 201, r.get_json()
            x = r.json["rueckruf"]
            assert x["url"] == "https://www.example.org/rueckruf" and x["serien"] == ["RR-1", "RR-2"], x
            assert x["description"] == "Zeile eins\nZeile zwei" and not x["alle"]
            # Ohne „mail“ gilt ja; mit mail=false geht nichts hinaus.
            assert post == []
            r = anlegen(kp, hms)
            assert r.status_code == 201 and r.json["mail"] is True and r.json["empfaenger"] > 0 and post, r.get_json()
    finally:
        post_zurueck(alt)
    print("Rückrufe: Rechte und Eingaben bestanden.")


# --- Betroffene Artikel, Banner, Übersicht --------------------------------------------------------------------

def test_betroffene_und_hinweise():
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            w, p1, kp, f = k["wart"], k["pruefer"], k["katalog"], k["fuehrung"]
            hms = ids["hms"]
            # Ein ausgesonderter Artikel ist außer Dienst und nie betroffen.
            weg = neuer_artikel(w, hms, lager, serial_no="RR-4")["id"]
            assert p1.post(f"/api/material/artikel/{weg}/sperren", json={"grund": "beschaedigung"}).status_code == 200
            assert w.post(f"/api/material/artikel/{weg}/aussondern", json={"grund": "irreparabel"}).status_code == 200
            # Ein Artikel eines anderen Produkts ist nie betroffen.
            gurt = neuer_artikel(w, ids["gurt"], lager, serial_no="RR-1", manufactured_on="2024-01")["id"]

            # Ohne Seriennummern: alle Artikel des Produkts im Bestand.
            r = anlegen(kp, hms, title="Alle Karabiner HMS Beta", description="Testbeschreibung: nicht verwenden.",
                        url="https://example.org/rr-alle", mail=False)
            assert r.status_code == 201, r.get_json()
            alle = r.json
            assert (alle["betroffen"], alle["offen"], alle["nicht_gefunden"], alle["empfaenger"]) == (3, 3, [], 0), alle
            assert alle["rueckruf"]["alle"] and alle["rueckruf"]["mailed_at"] is None and alle["rueckruf"]["mail_count"] == 0
            assert {a["id"] for a in alle["rueckruf"]["artikel"]} == set(art.values())
            # Mit Seriennummern: Vergleich ohne Groß/klein und ohne Leerraum außen; unbekannte kommen als Hinweis zurück.
            r = anlegen(kp, hms, title="Nur zwei Seriennummern", serials=" rr-1 \nRR-2\nXY-9\nrr-4", mail=False)
            assert r.status_code == 201, r.get_json()
            teil = r.json
            assert teil["betroffen"] == 2 and teil["offen"] == 2, teil
            assert teil["nicht_gefunden"] == ["XY-9", "rr-4"], teil["nicht_gefunden"]       # RR-4 ist ausgesondert
            assert {a["serial_no"] for a in teil["rueckruf"]["artikel"]} == {"RR-1", "rr-2"}
            assert teil["rueckruf"]["nicht_gefunden"] == ["XY-9", "rr-4"]

            # Banner-Daten am Artikel: die laufenden Rückrufe, die ihn betreffen – für alle mit Lesezugang.
            a1 = f.get(f"/api/material/artikel/{art['RR-1']}").json["artikel"]
            assert [x["title"] for x in a1["rueckrufe"]] == ["Nur zwei Seriennummern", "Alle Karabiner HMS Beta"], a1["rueckrufe"]
            x = a1["rueckrufe"][1]
            assert x["zustand"] == "offen" and x["grund"] is None and x["alle"], x
            assert x["description"] == "Testbeschreibung: nicht verwenden." and x["url"] == "https://example.org/rr-alle"
            a3 = f.get(f"/api/material/artikel/{art['RR-3']}").json["artikel"]
            assert [x["title"] for x in a3["rueckrufe"]] == ["Alle Karabiner HMS Beta"], a3["rueckrufe"]
            assert f.get(f"/api/material/artikel/{gurt}").json["artikel"]["rueckrufe"] == []
            assert f.get(f"/api/material/artikel/{weg}").json["artikel"]["rueckrufe"] == []
            assert k["nutzer"].get(f"/api/material/artikel/{art['RR-1']}").status_code == 403

            # Produkt: laufende Rückrufe mit ihren Artikeln (neueste zuerst).
            p = f.get(f"/api/material/produkte/{hms}").json["produkt"]
            assert [x["title"] for x in p["rueckrufe"]] == ["Nur zwei Seriennummern", "Alle Karabiner HMS Beta"]
            assert all(x["aktiv"] and x["artikel"] for x in p["rueckrufe"])
            assert p["rueckrufe"][1]["artikel"][0]["pfad"] == "OG Musterstadt / Lager", p["rueckrufe"][1]["artikel"][0]
            assert f.get(f"/api/material/produkte/{ids['gurt']}").json["produkt"]["rueckrufe"] == []

            # Übersicht (/start): laufende Rückrufe mit Produkt und Zahlen – nur, was Artikel im Bestand betrifft.
            leer = produkt_anlegen(kp, ids, "HMS Leer", "HL-1")
            r = anlegen(kp, leer, title="Ohne Bestand", mail=False)
            assert r.status_code == 201 and r.json["betroffen"] == 0, r.get_json()
            s = f.get("/api/material/start").json["rueckrufe"]
            assert [x["title"] for x in s] == ["Nur zwei Seriennummern", "Alle Karabiner HMS Beta"], s
            assert s[1]["produkt"] == {"id": hms, "manufacturer": "Testwerk", "model": "HMS Beta", "article_no": "HB-7"}
            assert (s[1]["betroffen"], s[1]["offen"]) == (3, 3) and (s[0]["betroffen"], s[0]["offen"]) == (2, 2)
            # GET /rueckrufe zeigt alle laufenden, auch ohne Bestand.
            liste = f.get("/api/material/rueckrufe").json["rueckrufe"]
            assert {x["title"] for x in liste} == {"Nur zwei Seriennummern", "Alle Karabiner HMS Beta", "Ohne Bestand"}
            # Artikellisten tragen die Marke „Rückruf“ (Titel des offenen Rückrufs), solange er offen ist.
            zeilen = {x["id"]: x for x in w.get(f"/api/material/ordner/{lager}").json["ordner"]["artikel"]}
            assert zeilen[art["RR-3"]]["rueckruf"] == "Alle Karabiner HMS Beta", zeilen[art["RR-3"]]
            assert zeilen[art["RR-1"]]["rueckruf"] and zeilen[gurt]["rueckruf"] is None
            # Das Journal des Produkts (und damit jedes Artikels) führt den Rückruf.
            j = [e for e in p["journal"] if e["action"] == "rueckruf"]
            assert len(j) == 2 and j[0]["entity"] == "product" and j[0]["nachher"]["serials"] == ["rr-1", "RR-2", "XY-9", "rr-4"], j
            assert j[1]["nachher"]["serials"] == "alle" and j[1]["nachher"]["mail"] is False
            assert any(e["action"] == "rueckruf" for e in a1["journal"])
            assert post == []
    finally:
        post_zurueck(alt)
    print("Rückrufe: betroffene Artikel, Banner und Übersicht bestanden.")


# --- Mail ---------------------------------------------------------------------------------------------------

def test_mail_empfaenger():
    post, alt = post_abfangen(scheitert={"wart2@example.org"})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            adm, w, kp = k["adm"], k["wart"], k["katalog"]
            hms = ids["hms"]
            # Konten: ein zweiter Materialwart, ein inaktiver Materialwart, Prüfer mit verschiedenen Prüfungen.
            konto(app, adm, "wart2@example.org", rechte={"material": 2})
            _, wart3 = konto(app, adm, "wart3@example.org", rechte={"material": 2})
            p2 = zweiter_pruefer(app, adm)                                        # prüft nur ein anderes Produkt
            p3, _ = konto(app, adm, "pruefer3@example.org", mat_pruefer=True, urkundennummer="1012-4713")
            p4, p4_id = konto(app, adm, "pruefer4@example.org", mat_pruefer=True, urkundennummer="1012-4714")
            p5, p5_id = konto(app, adm, "pruefer5@example.org", mat_pruefer=True, urkundennummer="1012-4715")
            for c in (p3, p4, p5):
                unterschreiben(c)
            anderes = produkt_anlegen(kp, ids, "HMS Gamma", "HG-1")
            fremd = neuer_artikel(w, anderes, lager, serial_no="RR-1")["id"]
            pruefen(k["pruefer"], art["RR-1"])                                     # betroffen (beide Rückrufe)
            pruefen(p2, fremd)                                                     # anderes Produkt
            pruefen(p3, art["RR-3"])                                               # nur im Rückruf „alle“ betroffen
            pruefen(p4, art["rr-2"])                                               # betroffen – Urkunde danach ungültig
            pruefen(p5, art["rr-2"])                                               # betroffen – Konto danach inaktiv
            # Das Startkonto (admin@) ist mit Stufe 2 im Modul Material auch Materialwart.
            # Der Prüfer ist zugleich Materialwart (bekommt die Mail nur einmal); wart3 und pruefer5 sind inaktiv,
            # pruefer4 hat keine gültige Urkundennummer mehr (das prüft nur Python, nicht SQL).
            assert adm.put(f"/api/admin/users/{k['pruefer_id']}", json={"rechte": {"material": 2}}).status_code == 200
            assert adm.put(f"/api/admin/users/{wart3}", json={"active": False}).status_code == 200
            assert adm.put(f"/api/admin/users/{p5_id}", json={"active": False}).status_code == 200
            schreiben(tmp, "UPDATE users SET urkundennummer = ' - ' WHERE id = ?", (p4_id,))

            r = anlegen(kp, hms, title="Schnapper prüfen", description="Testbeschreibung des Herstellers.",
                        url="https://example.org/rr-1", serials="RR-1\nrr-2")
            assert r.status_code == 201, r.get_json()
            ruid = r.json["rueckruf"]["id"]
            an = [x[0] for x in post]
            assert sorted(an) == ["admin@example.org", "pruefer@example.org", "wart2@example.org", "wart@example.org"], an
            assert r.json["empfaenger"] == 4
            betreff, inhalt = post[0][1], post[0][2]
            assert betreff == "Rückruf: Testwerk HMS Beta – Schnapper prüfen", betreff
            for teil in ("Testbeschreibung des Herstellers.", "https://example.org/rr-1", "  RR-1\n", "  rr-2\n",
                         "Im Bestand:   2 betroffene Artikel", "Grund „Rückruf“",
                         f"https://strömis.de/material/katalog/produkt/{hms}", "https://strömis.de/material\n",
                         "OG Musterstadt / Lager"):
                assert teil in inhalt, (teil, inhalt)
            # Ergebnis gespeichert: drei angenommen, eine gescheitert (wart2).
            z = zeile(tmp, "SELECT mailed_at, mail_count, mail_failed FROM mat_recall WHERE id = ?", (ruid,))
            assert z["mailed_at"] and (z["mail_count"], z["mail_failed"]) == (3, 1), z
            x = k["fuehrung"].get(RR.format(hms)).json["rueckrufe"][0]
            assert (x["mail_count"], x["mail_failed"]) == (3, 1) and x["mailed_at"] == z["mailed_at"], x

            # Ohne Seriennummern ist auch RR-3 betroffen – und damit pruefer3.
            del post[:]
            r = anlegen(kp, hms, title="Alle HMS Beta")
            assert sorted(x[0] for x in post) == ["admin@example.org", "pruefer3@example.org", "pruefer@example.org",
                                                  "wart2@example.org", "wart@example.org"], post
            assert "alle Artikel dieses Produkts" in post[0][2] and "Im Bestand:   3 betroffene Artikel" in post[0][2]
            # Solange der Versand läuft: mail_count ist die Zahl der Empfänger, mailed_at noch leer („wird verschickt“).
            from app.material.services import rueckruf
            wartend = []
            rueckruf.HINTERGRUND = lambda fn, *a: wartend.append((fn, a))
            r = anlegen(kp, hms, title="Versand läuft", serials="RR-1")
            x = r.json["rueckruf"]
            assert r.json["empfaenger"] == 4 and x["mailed_at"] is None and (x["mail_count"], x["mail_failed"]) == (4, 0), x
            rueckruf.HINTERGRUND = lambda fn, *a: fn(*a)
            with app.app_context():
                for fn, a in wartend:
                    fn(*a)
            x = k["fuehrung"].get(RR.format(hms)).json["rueckrufe"][0]
            assert x["title"] == "Versand läuft" and x["mailed_at"] and (x["mail_count"], x["mail_failed"]) == (3, 1), x
            # Gibt es keinen Materialwart, bekommt die Verwaltung die Mail.
            schreiben(tmp, "UPDATE users SET recht_material = 1 WHERE recht_material = 2")
            del post[:]
            r = anlegen(kp, hms, title="Ohne Materialwart", serials="RR-1")
            assert sorted(x[0] for x in post) == ["admin@example.org", "pruefer@example.org"], post
            # Ohne Empfänger (Produkt ohne geprüfte Artikel, keine Verwaltung erreichbar) ist der Versand gleich fertig.
            schreiben(tmp, "UPDATE users SET recht_verwaltung = 1 WHERE email = 'admin@example.org'")
            del post[:]
            leer = produkt_anlegen(kp, ids, "HMS Leer", "HL-2")
            r = anlegen(kp, leer, title="Niemand da")
            assert r.status_code == 201 and r.json["empfaenger"] == 0 and post == [], r.get_json()
            x = r.json["rueckruf"]
            assert x["mailed_at"] and x["mail_count"] == 0 and x["mail_failed"] == 0, x
    finally:
        post_zurueck(alt)
    print("Rückrufe: Mail-Empfänger bestanden.")


def test_mail_im_hintergrund():
    """Mit dem echten Hintergrund-Thread: Er schreibt das Ergebnis in seinem eigenen App-Kontext."""
    import threading
    from app.material.services import rueckruf
    alt = rueckruf.send_mail
    post = []
    rueckruf.send_mail = lambda an, betreff, inhalt: post.append((an, threading.current_thread().name)) or True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            r = anlegen(k["katalog"], ids["hms"], title="Im Hintergrund")
            assert r.status_code == 201 and r.json["empfaenger"] == 2, r.get_json()     # admin@ und wart@
            ruid = r.json["rueckruf"]["id"]
            for _ in range(100):
                z = zeile(tmp, "SELECT mailed_at, mail_count, mail_failed FROM mat_recall WHERE id = ?", (ruid,))
                if z["mailed_at"]:
                    break
                time.sleep(0.05)
            assert z["mailed_at"] and (z["mail_count"], z["mail_failed"]) == (2, 0), z
            assert post == [("admin@example.org", "mail"), ("wart@example.org", "mail")], post
    finally:
        rueckruf.send_mail = alt
    print("Rückrufe: Mail im Hintergrund bestanden.")


# --- Sperre, Prüfung, Beenden, Löschen ------------------------------------------------------------------------

def test_sperre_und_zustand():
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            w, p1, kp, f = k["wart"], k["pruefer"], k["katalog"], k["fuehrung"]
            hms = ids["hms"]
            # Geprüft vor dem Rückruf: zählt nicht.
            vorher = pruefen(p1, art["rr-2"])
            pruefen(p1, art["RR-3"])
            r = anlegen(kp, hms, title="Gelenk prüfen", mail=False)
            ruid = r.json["rueckruf"]["id"]
            assert (r.json["betroffen"], r.json["offen"]) == (3, 3), r.get_json()
            # Gesperrt wird nicht automatisch.
            for iid in art.values():
                assert f.get(f"/api/material/artikel/{iid}").json["artikel"]["lock_state"] == "frei"

            # Sperren mit Grund „Rückruf“: nur Prüfer.
            url = f"/api/material/artikel/{art['RR-1']}/sperren"
            assert w.post(url, json={"grund": "rueckruf"}).status_code == 403
            assert kp.post(url, json={"grund": "rueckruf"}).status_code == 403
            r = p1.post(url, json={"grund": "rueckruf", "text": "Gelenk prüfen"})
            assert r.status_code == 200, r.get_json()
            a = r.json["artikel"]
            assert a["lock_state"] == "gesperrt" and a["status"] == "gesperrt" and a["folder_id"] == system["gesperrt"], a
            assert a["lock_reason"] == "Rückruf: Gelenk prüfen", a["lock_reason"]
            assert [(x["zustand"], x["grund"]) for x in a["rueckrufe"]] == [("erledigt", "gesperrt")], a["rueckrufe"]

            # Eine Prüfung nach dem Rückruf erledigt ihn; eine Berichtigung einer Prüfung von vorher nicht.
            time.sleep(1.1)                                  # Zeitstempel zählen in ganzen Sekunden
            pruefen(p1, art["RR-3"])
            r = p1.post(f"/api/material/pruefungen/{vorher}/berichtigen", json={"grund": "Tippfehler im Befund"})
            assert r.status_code == 201, r.get_json()
            assert abschluss(p1, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
            zust = {iid: f.get(f"/api/material/artikel/{iid}").json["artikel"]["rueckrufe"][0] for iid in art.values()}
            assert (zust[art["RR-3"]]["zustand"], zust[art["RR-3"]]["grund"]) == ("erledigt", "geprueft"), zust
            assert zust[art["rr-2"]]["zustand"] == "offen", zust
            x = f.get(RR.format(hms)).json["rueckrufe"][0]
            assert (x["betroffen"], x["offen"]) == (3, 1), x
            assert {a["id"]: a["zustand"] for a in x["artikel"]} == {art["RR-1"]: "erledigt", art["rr-2"]: "offen",
                                                                       art["RR-3"]: "erledigt"}
            s = f.get("/api/material/start").json["rueckrufe"]
            assert [(y["id"], y["betroffen"], y["offen"]) for y in s] == [(ruid, 3, 1)], s
            # Die Marke in Listen bleibt nur am offenen Artikel.
            zeilen = {y["id"]: y["rueckruf"] for y in w.get(f"/api/material/ordner/{lager}").json["ordner"]["artikel"]}
            assert zeilen == {art["rr-2"]: "Gelenk prüfen", art["RR-3"]: None}, zeilen
            # Ein offener Rückruf blockiert die Freiprüfung nicht – sie macht ihn für den Artikel erledigt.
            time.sleep(1.1)
            pruefen(p1, art["RR-1"])
            a = f.get(f"/api/material/artikel/{art['RR-1']}").json["artikel"]
            assert a["lock_state"] == "frei" and a["rueckrufe"][0]["zustand"] == "erledigt", a["rueckrufe"]
            assert a["rueckrufe"][0]["grund"] == "geprueft"
    finally:
        post_zurueck(alt)
    print("Rückrufe: Sperre und Zustand bestanden.")


def test_beenden_und_loeschen():
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            w, kp, f = k["wart"], k["katalog"], k["fuehrung"]
            hms = ids["hms"]
            ruid = anlegen(kp, hms, title="Wird beendet", mail=False).json["rueckruf"]["id"]
            assert f.get(f"/api/material/artikel/{art['RR-1']}").json["artikel"]["rueckrufe"]
            r = kp.post(f"/api/material/rueckrufe/{ruid}/beenden", json={"vermerk": "Alle Artikel geprüft\nTestvermerk"})
            assert r.status_code == 200, r.get_json()
            # Kein Banner, kein Kasten, keine Marke mehr – am Produkt bleibt er sichtbar, mit Vermerk.
            a = f.get(f"/api/material/artikel/{art['RR-1']}").json["artikel"]
            assert a["rueckrufe"] == [], a["rueckrufe"]
            assert f.get("/api/material/start").json["rueckrufe"] == []
            assert f.get("/api/material/rueckrufe").json["rueckrufe"] == []
            assert all(y["rueckruf"] is None for y in w.get(f"/api/material/ordner/{lager}").json["ordner"]["artikel"])
            p = f.get(f"/api/material/produkte/{hms}").json["produkt"]
            assert len(p["rueckrufe"]) == 1 and not p["rueckrufe"][0]["aktiv"], p["rueckrufe"]
            assert p["rueckrufe"][0]["close_note"] == "Alle Artikel geprüft\nTestvermerk"
            assert "artikel" not in p["rueckrufe"][0]
            aktionen = [e["action"] for e in p["journal"]]
            assert aktionen[:2] == ["rueckruf_beendet", "rueckruf"], aktionen
            assert [e["action"] for e in a["journal"] if e["entity"] == "product"][:2] == ["rueckruf_beendet", "rueckruf"]
            # Ein neuer Rückruf steht wieder oben, der beendete darunter.
            anlegen(kp, hms, title="Neuer Rückruf", mail=False)
            assert [(x["title"], x["aktiv"]) for x in f.get(RR.format(hms)).json["rueckrufe"]] == [
                ("Neuer Rückruf", True), ("Wird beendet", False)]

            # Ein Produkt ohne Artikel lässt sich mitsamt seinen Rückrufen löschen.
            leer = produkt_anlegen(kp, ids, "HMS Weg", "HW-1")
            r1 = anlegen(kp, leer, title="Weg damit", mail=False).json["rueckruf"]["id"]
            r2 = anlegen(kp, leer, title="Auch weg", mail=False).json["rueckruf"]["id"]
            kp.post(f"/api/material/rueckrufe/{r2}/beenden", json={"vermerk": "erledigt"})
            r = kp.delete(f"/api/material/produkte/{leer}", headers=H)
            assert r.status_code == 200, r.get_json()
            assert zeile(tmp, "SELECT COUNT(*) AS n FROM mat_recall WHERE id IN (?, ?)", (r1, r2))["n"] == 0
            assert f.get(RR.format(leer)).status_code == 404
            assert kp.post(f"/api/material/rueckrufe/{r1}/beenden", json={"vermerk": "x"}).status_code == 404
            # Ein Produkt mit Artikeln bleibt (wie bisher) – samt Rückrufen.
            assert kp.delete(f"/api/material/produkte/{hms}", headers=H).status_code == 409
            assert len(f.get(RR.format(hms)).json["rueckrufe"]) == 2
    finally:
        post_zurueck(alt)
    print("Rückrufe: Beenden und Löschen bestanden.")


if __name__ == "__main__":
    test_rechte_und_eingaben()
    test_betroffene_und_hinweise()
    test_mail_empfaenger()
    test_mail_im_hintergrund()
    test_sperre_und_zustand()
    test_beenden_und_loeschen()
