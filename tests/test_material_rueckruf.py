"""Tests zu den Rückrufen im Modul „Material“ (Lieferung 4):  python tests/test_material_rueckruf.py

Die Material-Verwaltung legt am Produkt einen Rückruf an. Der Hinweis steht am Produkt, an den betroffenen Artikeln und
auf der Übersicht. Gesperrt wird nicht automatisch – Prüfer sperren mit dem Grund „Rückruf“.

Seit Phase 2 (Bauentwurf 2.6) zeigen Liste und Zahlen jedem nur seinen Bereich; eine Mail geht je betroffenem Artikel
an die Verwalter seiner Heimat und an die Prüfer, die ihn geprüft haben und dort heute prüfen dürfen (ohne Verwalter:
die Material-Verwaltung, gibt es keine, die Plattform-Verwaltung), jeder bekommt nur die Artikel, die er sieht.
Empfängerzahl und nicht gefundene Seriennummern erfährt nur die Material-Verwaltung. Alle Namen, Hersteller, Titel und Seriennummern hier sind erfunden
und nur für den Test da."""
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, abschluss, anmelden, freigeben, gliederung, katalog_grund,  # noqa: E402
                           neuer_artikel, neues_konto, pruef_formulare, starten, umgebung, unterschreiben,
                           zweiter_pruefer, mails_abfangen, mails_zurueck)
from test_material_ueberblick import ordner_neu  # noqa: E402

RR = "/api/material/produkte/{}/rueckrufe"


def post_abfangen(scheitert=()):
    """Mails direkt statt im Hintergrund und nur in eine Liste – an Adressen aus „scheitert“ geht nichts hinaus."""
    from app.material.services import rueckruf
    post = []
    alt = mails_abfangen(rueckruf, lambda an, betreff, inhalt: post.append((an, betreff, inhalt)) or an not in scheitert)
    return post, alt


def post_zurueck(alt):
    mails_zurueck(alt)


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
    """Ein Konto mit Namen – ohne Angabe mit Stufe Mitglied im Modul Material (wie neue Konten)."""
    felder = dict(felder, rechte=dict({"material": 1}, **felder.get("rechte", {})))
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
            # Anlegen nur die Material-Verwaltung – nicht Materialwart, Führungskraft, Prüfer, Nutzer.
            for c in (k["wart"], k["fuehrung"], k["pruefer"], k["nutzer"]):
                r = anlegen(c, hms)
                assert r.status_code == 403, r.get_json()
            assert app.test_client().post(RR.format(hms), json={"title": "x"}, headers=H).status_code == 401
            r = anlegen(k["katalog"], hms, title="Rückruf der Material-Verwaltung", mail=False)
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
            # Beenden: ebenso nur die Material-Verwaltung – und nur mit Vermerk.
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
            # Ohne „mail“ gilt ja; mit mail=false geht nichts hinaus. Die Zahl der Empfänger und nicht gefundene
            # Seriennummern erfährt die Material-Verwaltung (sie sieht alle Bestände) – mit und ohne Plattform-Verwaltung.
            assert post == []
            for c in (kp, k["adm"]):
                r = anlegen(c, hms)
                assert r.status_code == 201 and r.json["mail"] is True and r.json["empfaenger"] > 0 and post, r.get_json()
                assert r.json["nicht_gefunden"] == [] and "benachrichtigt" not in r.json, r.get_json()
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
            assert p1.post(f"/api/material/artikel/{weg}/sperren", json={"grund": "verlust"}).status_code == 200
            assert w.post(f"/api/material/artikel/{weg}/aussondern", json={"grund": "irreparabel"}).status_code == 200
            # Ein Artikel eines anderen Produkts ist nie betroffen.
            gurt = neuer_artikel(w, ids["gurt"], lager, serial_no="RR-1", manufactured_on="2024-01")["id"]

            # Ohne Seriennummern: alle Artikel des Produkts im Bestand.
            r = anlegen(kp, hms, title="Alle Karabiner HMS Beta", description="Testbeschreibung: nicht verwenden.",
                        url="https://example.org/rr-alle", mail=False)
            assert r.status_code == 201, r.get_json()
            alle = r.json
            # Die Material-Verwaltung bekommt die Zahlen über alles und die Zahl der Empfänger.
            assert (alle["betroffen"], alle["offen"], alle["mail"], alle["empfaenger"]) == (3, 3, False, 0), alle
            assert alle["rueckruf"]["alle"] and alle["rueckruf"]["mail"] is False and not alle["rueckruf"]["mail_count"]
            assert "mail_count" not in f.get(RR.format(hms)).json["rueckrufe"][0]           # andere nur „mail“
            assert {a["id"] for a in alle["rueckruf"]["artikel"]} == set(art.values())
            # Mit Seriennummern: Vergleich ohne Groß/klein und ohne Leerraum außen; unbekannte kommen als Hinweis zurück –
            # an die Material-Verwaltung (für alle anderen hieße „nicht gefunden“ auch „nicht in fremden Gliederungen“).
            r = anlegen(k["adm"], hms, title="Nur zwei Seriennummern", serials=" rr-1 \nRR-2\nXY-9\nrr-4", mail=False)
            assert r.status_code == 201, r.get_json()
            teil = r.json
            assert teil["betroffen"] == 2 and teil["offen"] == 2 and teil["empfaenger"] == 0, teil
            assert teil["nicht_gefunden"] == ["XY-9", "rr-4"], teil["nicht_gefunden"]       # RR-4 ist ausgesondert
            assert {a["serial_no"] for a in teil["rueckruf"]["artikel"]} == {"RR-1", "rr-2"}
            assert teil["rueckruf"]["nicht_gefunden"] == ["XY-9", "rr-4"]
            x = f.get(RR.format(hms)).json["rueckrufe"][0]
            assert x["title"] == "Nur zwei Seriennummern" and "nicht_gefunden" not in x and x["betroffen"] == 2, x
            assert kp.get(RR.format(hms)).json["rueckrufe"][0]["nicht_gefunden"] == ["XY-9", "rr-4"]

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
            assert s[1]["produkt"] == {"id": hms, "manufacturer": "Testwerk", "model": "HMS Beta", "description": "",
                                       "article_no": "HB-7"}
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
    """Empfänger je betroffenem Artikel (Phase 2, Bauentwurf 2.6): die Verwalter seiner Heimat und die Prüfer, die ihn
    geprüft haben und dort heute prüfen dürfen; hat er keinen Verwalter, die Material-Verwaltung (gibt es keine, die
    Plattform-Verwaltung). Jeder Empfänger
    bekommt eine Mail mit genau den betroffenen Artikeln, die er sehen darf – aus einer fremden Gliederung steht darin
    nichts, auch keine Zahl."""
    post, alt = post_abfangen(scheitert={"wart2@example.org"})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            adm, w, kp = k["adm"], k["wart"], k["katalog"]
            hms = ids["hms"]
            gid = zeile(tmp, "SELECT parent_id FROM mat_folder WHERE id = ?", (lager,))["parent_id"]
            # Verwalter der Gliederung: wart (aus aufbau), wart2 (an ihn scheitert die Mail), wart3 (danach deaktiviert);
            # wart_fz verwaltet nur ein Fahrzeug, in dem kein betroffener Artikel liegt.
            _, wart2 = konto(app, adm, "wart2@example.org")
            _, wart3 = konto(app, adm, "wart3@example.org")
            _, wart_fz = konto(app, adm, "wart_fz@example.org")
            fahrzeug = ordner_neu(adm, gid, "Testfahrzeug", "fahrzeug")
            for uid in (wart2, wart3):
                freigeben(adm, gid, uid, "verwalten")
            freigeben(adm, fahrzeug, wart_fz, "verwalten")
            # Prüfer: pruefer (lesen und prüfen an der Gliederung), p2 prüft nur ein anderes Produkt; p3 bis p6 prüfen nur
            # im Lager – p4 verliert danach die Urkundennummer, p5 wird deaktiviert, p6s Prüffreigabe läuft ab.
            p2 = zweiter_pruefer(app, adm)
            p = {}
            for n in (3, 4, 5, 6):
                p[n] = konto(app, adm, f"pruefer{n}@example.org", mat_pruefer=True, urkundennummer=f"1012-471{n}")
                freigeben(adm, lager, p[n][1], "pruefen")
                unterschreiben(p[n][0])
            anderes = produkt_anlegen(kp, ids, "HMS Gamma", "HG-1")
            fremd = neuer_artikel(w, anderes, lager, serial_no="RR-1")["id"]
            pruefen(k["pruefer"], art["RR-1"])                                     # betroffen (beide Rückrufe)
            pruefen(p2, fremd)                                                     # anderes Produkt
            pruefen(p[3][0], art["RR-3"])                                          # nur im Rückruf „alle“ betroffen
            for n in (4, 5, 6):
                pruefen(p[n][0], art["rr-2"])                                      # betroffen – danach ohne P(A)
            # Eine zweite Gliederung mit eigenem Verwalter und eigener Prüferin; eine dritte ganz ohne Verwalter.
            ns, _ = gliederung(adm, "OG Nachbarstadt", standard=False)
            _, wart_ns = konto(app, adm, "wart_ns@example.org")
            freigeben(adm, ns, wart_ns, "verwalten")
            pruefer_ns, pruefer_ns_id = konto(app, adm, "pruefer_ns@example.org", mat_pruefer=True,
                                              urkundennummer="1012-4719")
            freigeben(adm, ns, pruefer_ns_id, "pruefen")
            unterschreiben(pruefer_ns)
            ns_art = neuer_artikel(adm, hms, ordner_neu(adm, ns, "Lager Nachbarstadt"), serial_no="RR-NS")["id"]
            pruefen(pruefer_ns, ns_art)
            ow, _ = gliederung(adm, "OG Ohnewart", standard=False)
            ow_art = neuer_artikel(adm, hms, ordner_neu(adm, ow, "Lager Ohnewart"), serial_no="RR-OW")["id"]
            assert adm.put(f"/api/admin/users/{wart3}", json={"active": False}).status_code == 200
            assert adm.put(f"/api/admin/users/{p[5][1]}", json={"active": False}).status_code == 200
            schreiben(tmp, "UPDATE users SET urkundennummer = ' - ' WHERE id = ?", (p[4][1],))
            schreiben(tmp, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ? AND permission = 'pruefen'",
                      ((_heute() - timedelta(days=1)).isoformat(), p[6][1]))
            inv = {r["id"]: r["inventory_no"] for r in [zeile(tmp, "SELECT id, inventory_no FROM mat_item WHERE id = ?",
                                                             (i,)) for i in (*art.values(), ns_art, ow_art)]}

            def mails():
                return {an: inhalt for an, _, inhalt in post}

            r = anlegen(adm, hms, title="Schnapper prüfen", description="Testbeschreibung des Herstellers.",
                        url="https://example.org/rr-1", serials="RR-1\nrr-2\nRR-NS")
            assert r.status_code == 201, r.get_json()
            ruid = r.json["rueckruf"]["id"]
            an = mails()
            assert sorted(an) == ["pruefer@example.org", "pruefer_ns@example.org", "wart2@example.org",
                                  "wart@example.org", "wart_ns@example.org"], sorted(an)
            assert r.json["empfaenger"] == 5 and r.json["betroffen"] == 3, r.get_json()
            betreff = post[0][1]
            assert betreff == "Rückruf: Testwerk HMS Beta – Schnapper prüfen", betreff
            # Musterstadt: die beiden eigenen Artikel, nichts aus der Nachbarstadt – auch nicht in der Zahl.
            for adr in ("wart@example.org", "wart2@example.org", "pruefer@example.org"):
                inhalt = an[adr]
                for teil in ("Testbeschreibung des Herstellers.", "https://example.org/rr-1", "  RR-1\n", "  rr-2\n",
                             "Dein Bereich: 2 betroffene Artikel", "Grund „Rückruf“", inv[art["RR-1"]], inv[art["rr-2"]],
                             f"https://strömis.de/material/katalog/produkt/{hms}", "https://strömis.de/material\n",
                             "OG Musterstadt / Lager"):
                    assert teil in inhalt, (adr, teil, inhalt)
                assert inv[ns_art] not in inhalt and "Nachbarstadt" not in inhalt, (adr, inhalt)
            # Nachbarstadt: nur ihr Artikel.
            for adr in ("wart_ns@example.org", "pruefer_ns@example.org"):
                inhalt = an[adr]
                assert "Dein Bereich: 1 betroffener Artikel" in inhalt and inv[ns_art] in inhalt, (adr, inhalt)
                assert "OG Nachbarstadt / Lager Nachbarstadt" in inhalt, inhalt
                assert "Musterstadt" not in inhalt and inv[art["RR-1"]] not in inhalt and inv[art["rr-2"]] not in inhalt
            # Ergebnis gespeichert: vier angenommen, eine gescheitert (wart2) – sehen kann das nur die Verwaltung.
            z = zeile(tmp, "SELECT mailed_at, mail_count, mail_failed FROM mat_recall WHERE id = ?", (ruid,))
            assert z["mailed_at"] and (z["mail_count"], z["mail_failed"]) == (4, 1), z
            x = adm.get(RR.format(hms)).json["rueckrufe"][0]
            assert (x["mail_count"], x["mail_failed"]) == (4, 1) and x["mailed_at"] == z["mailed_at"] and x["mail"], x
            x = k["fuehrung"].get(RR.format(hms)).json["rueckrufe"][0]
            assert x["mail"] is True and not {"mailed_at", "mail_count", "mail_failed", "nicht_gefunden"} & set(x), x
            assert (x["betroffen"], x["offen"]) == (2, 2), x

            # Ohne Seriennummern ist auch RR-3 betroffen – und damit p3 (er sieht nur das Lager) – und RR-OW: Ohne
            # Verwalter geht er an die Material-Verwaltung (katalog, ohne Plattform-Verwaltung), die alles sieht – nicht an
            # die Plattform-Verwaltung, solange es eine Material-Verwaltung gibt.
            del post[:]
            r = anlegen(adm, hms, title="Alle HMS Beta")
            an = mails()
            assert sorted(an) == ["katalog@example.org", "pruefer3@example.org", "pruefer@example.org",
                                  "pruefer_ns@example.org", "wart2@example.org", "wart@example.org",
                                  "wart_ns@example.org"], sorted(an)
            assert "alle Artikel dieses Produkts" in an["wart@example.org"]
            assert "Dein Bereich: 3 betroffene Artikel" in an["wart@example.org"]
            assert "Dein Bereich: 3 betroffene Artikel" in an["pruefer3@example.org"]
            assert "Dein Bereich: 5 betroffene Artikel" in an["katalog@example.org"] and inv[ow_art] in an["katalog@example.org"]
            assert inv[ow_art] not in an["wart@example.org"] and inv[ow_art] not in an["wart_ns@example.org"]
            # Die Material-Verwaltung ohne Plattform-Verwaltung bekommt beim Anlegen die vollen Zahlen.
            del post[:]
            r = anlegen(kp, hms, title="Von der Material-Verwaltung", serials="RR-1\nRR-NS")
            assert r.status_code == 201 and (r.json["betroffen"], r.json["empfaenger"]) == (2, 5), r.get_json()
            assert r.json["nicht_gefunden"] == [] and "benachrichtigt" not in r.json, r.get_json()
            assert sorted(mails()) == ["pruefer@example.org", "pruefer_ns@example.org", "wart2@example.org",
                                       "wart@example.org", "wart_ns@example.org"], post
            # Nur in der Nachbarstadt betroffen: Die Mail geht an deren Verwalter und Prüferin.
            del post[:]
            r = anlegen(kp, hms, title="Nur Nachbarstadt", serials="RR-NS")
            assert (r.json["betroffen"], r.json["offen"], r.json["empfaenger"]) == (1, 1, 2), r.get_json()
            assert sorted(mails()) == ["pruefer_ns@example.org", "wart_ns@example.org"], post

            # Solange der Versand läuft: mail_count ist die Zahl der Empfänger, mailed_at noch leer („wird verschickt“).
            from app.material.services import rueckruf
            wartend = []
            rueckruf.HINTERGRUND = lambda fn, *a: wartend.append((fn, a))
            r = anlegen(adm, hms, title="Versand läuft", serials="RR-1")
            x = r.json["rueckruf"]
            assert r.json["empfaenger"] == 3 and x["mailed_at"] is None and (x["mail_count"], x["mail_failed"]) == (3, 0), x
            rueckruf.HINTERGRUND = lambda fn, *a: fn(*a)
            with app.app_context():
                for fn, a in wartend:
                    fn(*a)
            x = adm.get(RR.format(hms)).json["rueckrufe"][0]
            assert x["title"] == "Versand läuft" and x["mailed_at"] and (x["mail_count"], x["mail_failed"]) == (2, 1), x
            # Hat der Artikel keinen Verwalter mehr, bekommt die Material-Verwaltung die Mail (der Prüfer weiter).
            schreiben(tmp, "DELETE FROM mat_folder_grant WHERE folder_id = ? AND permission = 'verwalten'", (gid,))
            del post[:]
            r = anlegen(adm, hms, title="Ohne Materialwart", serials="RR-1")
            assert sorted(mails()) == ["katalog@example.org", "pruefer@example.org"], post
            # Gibt es keine Material-Verwaltung außer der Plattform-Verwaltung, bekommt diese sie.
            schreiben(tmp, "UPDATE users SET recht_material = 1 WHERE email = 'katalog@example.org'")
            del post[:]
            r = anlegen(adm, hms, title="Ohne Materialwart, ohne Material-Verwaltung", serials="RR-1")
            assert sorted(mails()) == ["admin@example.org", "pruefer@example.org"], post
            schreiben(tmp, "UPDATE users SET recht_material = 2 WHERE email = 'katalog@example.org'")
            # Ohne Empfänger (Produkt ohne Artikel im Bestand) ist der Versand gleich fertig.
            del post[:]
            leer = produkt_anlegen(kp, ids, "HMS Leer", "HL-2")
            r = anlegen(adm, leer, title="Niemand da")
            assert r.status_code == 201 and r.json["empfaenger"] == 0 and post == [], r.get_json()
            x = r.json["rueckruf"]
            assert x["mailed_at"] and x["mail_count"] == 0 and x["mail_failed"] == 0 and x["mail"] is True, x
            # Ohne Material-Verwaltung, Plattform-Verwaltung und Verwalter erreicht die Mail niemanden – auch das ist
            # schnell fertig. Im Dienst gerufen: Über die Schnittstelle legt nur die Material-Verwaltung an, und die
            # bekäme die Mail.
            schreiben(tmp, "UPDATE users SET recht_verwaltung = 0, recht_material = 1 WHERE email IN "
                           "('admin@example.org', 'katalog@example.org')")
            del post[:]
            from flask import g
            with app.test_request_context():
                from app import db
                g.user = db.query("SELECT * FROM users WHERE email = 'katalog@example.org'", one=True)
                ruid, info = rueckruf.anlegen(hms, {"title": "Niemand erreichbar", "serials": "rr-2"}, g.user)
            assert post == [] and info["benachrichtigt"] is False, info
            z = zeile(tmp, "SELECT mailed_at, mail_count, mail_failed FROM mat_recall WHERE id = ?", (ruid,))
            assert z["mailed_at"] and (z["mail_count"], z["mail_failed"]) == (0, 0), z
    finally:
        post_zurueck(alt)
    print("Rückrufe: Mail-Empfänger bestanden.")


def test_mail_im_hintergrund():
    """Mit dem echten Hintergrund-Thread: Er schreibt das Ergebnis in seinem eigenen App-Kontext."""
    import threading
    from app.material.services import mailprotokoll
    alt = (mailprotokoll.versand, mailprotokoll.MAILSERVER)
    post = []
    mailprotokoll.versand = lambda an, betreff, inhalt: post.append((an, threading.current_thread().name)) or (True, "")
    mailprotokoll.MAILSERVER = lambda: True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, system, lager, art = aufbau(tmp)
            r = anlegen(k["katalog"], ids["hms"], title="Im Hintergrund")
            assert r.status_code == 201 and r.json["empfaenger"] == 1, r.get_json()
            ruid = r.json["rueckruf"]["id"]
            for _ in range(100):
                z = zeile(tmp, "SELECT mailed_at, mail_count, mail_failed FROM mat_recall WHERE id = ?", (ruid,))
                if z["mailed_at"]:
                    break
                time.sleep(0.05)
            # Der Verwalter der Gliederung – die Material-Verwaltung nicht: Die Artikel haben einen Verwalter.
            assert z["mailed_at"] and (z["mail_count"], z["mail_failed"]) == (1, 0), z
            assert post == [("wart@example.org", "mail")], post
    finally:
        mailprotokoll.versand, mailprotokoll.MAILSERVER = alt
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


def test_lebenslauf_und_pruefung():
    """Der Lebenslauf eines betroffenen Artikels nennt seine Rückrufe (laufende mit Zustand, beendete mit Vermerk),
    die Prüfung eines betroffenen Artikels zeigt den laufenden Rückruf – und ihr Abschluss erledigt ihn."""
    from test_material import pdf_seiten
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, _, _, art = aufbau(tmp)
            kp, p1 = k["katalog"], k["pruefer"]
            r = anlegen(kp, ids["hms"], title="Schnapper klemmt", serials="RR-1", description="Nicht mehr verwenden.",
                        url="https://hersteller.example/rr")
            assert r.status_code == 201, r.get_json()
            r = anlegen(kp, ids["hms"], title="Etikett fehlerhaft")
            assert r.status_code == 201, r.get_json()
            alt_id = r.json["rueckruf"]["id"]
            assert kp.post(f"/api/material/rueckrufe/{alt_id}/beenden", json={"vermerk": "Hersteller hat zurückgezogen"},
                           headers=H).status_code == 200

            def lebenslauf(iid):
                r = p1.get(f"/material/artikel/{iid}/lebenslauf.pdf")
                assert r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code
                pfad = os.path.join(tmp, f"ll_{iid}.pdf")
                with open(pfad, "wb") as fh:
                    fh.write(r.data)
                return " ".join(" ".join(pdf_seiten(pfad)).split())

            text = lebenslauf(art["RR-1"])
            for wert in ("Rückrufe", "Schnapper klemmt", "betrifft diese Seriennummer", "Nicht mehr verwenden.",
                         "für diesen Artikel offen", "Etikett fehlerhaft", "alle Artikel des Produkts", "beendet am",
                         "Hersteller hat zurückgezogen"):
                assert wert in text, (wert, text[:2000])
            text = lebenslauf(art["rr-2"])
            assert "Etikett fehlerhaft" in text and "Schnapper klemmt" not in text, text[:2000]
            # Die Prüfung zeigt den laufenden Rückruf; nach dem Abschluss ist er für den Artikel erledigt.
            r = starten(p1, art["RR-1"])
            assert r.status_code in (200, 201) and r.json["pruefung"]["artikel"]["rueckruf"] == "Schnapper klemmt", r.get_json()
            time.sleep(1.1)                          # gleiche Sekunde zählt als „vorher“
            assert abschluss(p1, r.json["pruefung"]["id"], ergebnis="einsatzbereit").status_code == 200
            assert "erledigt – nach dem Rückruf geprüft" in lebenslauf(art["RR-1"])
    finally:
        post_zurueck(alt)
    print("Rückrufe: Lebenslauf und Prüfung bestanden.")


def test_review_lieferung4():
    """Befunde aus dem Review: Seriennummern mit innerem Leerraum (auch geschützten Leerzeichen) treffen den Artikel,
    ein Zeilentrenner im Titel landet nicht im Betreff, mehrere offene Rückrufe stehen alle in der Prüfung."""
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, _, lager, art = aufbau(tmp)
            kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
            # Am Artikel zieht die Speicherung Leerraum zusammen („AB  12“ → „AB 12“); der Rückruf vergleicht genauso.
            ab = neuer_artikel(w, ids["hms"], lager, serial_no="AB  12")["id"]
            r = anlegen(k["adm"], ids["hms"], title="Leerraum", serials="ab  12\nRR\u00a01X", mail=False)
            assert r.status_code == 201 and r.json["betroffen"] == 1 and r.json["nicht_gefunden"] == ["RR\u00a01X"], r.get_json()
            assert [x["title"] for x in w.get(f"/api/material/artikel/{ab}").json["artikel"]["rueckrufe"]] == ["Leerraum"]
            # Ein Zeilentrenner (U+2028) im Titel: Der Betreff bleibt eine Zeile, die Mail geht hinaus.
            post.clear()
            r = anlegen(kp, ids["hms"], title="Schnapper\u2028prüfen", serials="RR-3")
            assert r.status_code == 201, r.get_json()
            assert post and all(len(b.splitlines()) == 1 and "\u2028" not in b for _, b, _ in post), post
            assert "Schnapper prüfen" in post[0][1], post[0][1]
            # Zwei offene Rückrufe an RR-3 („alle“ gibt es noch nicht – „Leerraum“ betrifft nur AB 12): beide in der Prüfung.
            assert anlegen(kp, ids["hms"], title="Für alle", mail=False).status_code == 201
            pr = starten(p1, art["RR-3"]).json["pruefung"]
            assert pr["artikel"]["rueckruf"] == "Schnapper\u2028prüfen · Für alle", pr["artikel"]
    finally:
        post_zurueck(alt)
    print("Rückrufe: Review-Befunde Lieferung 4 bestanden.")


# --- Phase 2: jeder Bereich für sich (Bauentwurf 2.6, Kritik 7) ----------------------------------------------------------

def zwei_bereiche(tmp):
    """aufbau und dazu eine zweite Gliederung „OG Nachbarstadt“ mit eigenem Verwalter und zwei Karabinern (TEST-NS-…) –
    niemand aus aufbau hat dort eine Freigabe."""
    app, k, ids, system, lager, art = aufbau(tmp)
    ns, _ = gliederung(k["adm"], "OG Nachbarstadt", standard=False)
    wart_ns, wart_ns_id = neues_konto(app, "wart_ns@example.org", name="Wart Nachbarstadt")
    freigeben(k["adm"], ns, wart_ns_id, "verwalten")
    lager_ns = ordner_neu(wart_ns, ns, "Lager Nachbarstadt")
    ns_art = {s: neuer_artikel(wart_ns, ids["hms"], lager_ns, serial_no=s)["id"] for s in ("TEST-NS-1", "TEST-NS-2")}
    return app, k, ids, lager, art, wart_ns, ns_art


def test_anlegen_nur_material_verwaltung():
    """Einen Rückruf legt nur die Material-Verwaltung an – und die sieht alle Bestände: Sie bekommt die vollen Zahlen
    (betroffen, nicht gefundene Nummern, Empfänger). Wer nur einen Teil sieht – ein Mitglied ohne Bestand, ein
    Materialwart –, kann keinen anlegen (403), ein Rückruf taugt also nicht als Abfrage fremder Bestände. Den
    „Katalogpfleger ohne Bestand“ gibt es seit Schritt 10 nicht mehr."""
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, lager, art, wart_ns, ns_art = zwei_bereiche(tmp)
            mg, _ = neues_konto(app, "mitglied_ohne@example.org", name="Mitglied ohne Bestand")
            daten = {"title": "Testrückruf", "serials": "TEST-NS-1\nTEST-X-0404", "mail": False}
            for c in (mg, k["wart"]):
                r = c.post(RR.format(ids["hms"]), json=daten)
                assert r.status_code == 403 and "Material-Verwaltung" in r.json["error"], r.get_json()
            assert zeile(tmp, "SELECT COUNT(*) AS n FROM mat_recall")["n"] == 0
            kp = k["katalog"]
            r = kp.post(RR.format(ids["hms"]), json=daten)
            assert r.status_code == 201, r.get_json()
            j = r.get_json()
            assert (j["betroffen"], j["nicht_gefunden"], j["empfaenger"], j["mail"]) == (1, ["TEST-X-0404"], 0, False), j
            assert j["rueckruf"]["nicht_gefunden"] == ["TEST-X-0404"] and "mail_count" in j["rueckruf"], j["rueckruf"]
            # Lesen dürfen alle mit Zugang – das Mitglied ohne Bestand sieht den Rückruf, aber keine Zahl über fremde.
            x = mg.get(RR.format(ids["hms"])).json["rueckrufe"][0]
            assert x["betroffen"] == 0 and not x["artikel"] and "nicht_gefunden" not in x and "mail_count" not in x, x
            r = kp.post(f"/api/material/rueckrufe/{j['rueckruf']['id']}/beenden", json={"vermerk": "Testvermerk"})
            assert r.status_code == 200, r.get_json()
            # Mit Mail: Der Verwalter der Nachbarstadt wird benachrichtigt, die Material-Verwaltung erfährt die Zahl.
            r = kp.post(RR.format(ids["hms"]), json=dict(daten, mail=True))
            assert (r.json["betroffen"], r.json["empfaenger"]) == (1, 1), r.get_json()
            assert [an for an, _, _ in post] == ["wart_ns@example.org"], post
    finally:
        post_zurueck(alt)
    print("Rückrufe: anlegen nur die Material-Verwaltung bestanden.")


def test_listen_je_bereich():
    """Übersicht (/start), Rückrufliste, Produkt und Rückrufe am Produkt zählen und zeigen je Konto nur den eigenen
    Bereich: der Materialwart von Musterstadt seine drei Karabiner, der der Nachbarstadt seine zwei, die Verwaltung alle
    fünf. Wer keinen betroffenen Artikel sieht, hat auf der Übersicht keinen Kasten – in der Liste steht der Rückruf
    trotzdem (der Katalog ist global)."""
    post, alt = post_abfangen()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app, k, ids, lager, art, wart_ns, ns_art = zwei_bereiche(tmp)
            hms, w = ids["hms"], k["wart"]

            def inventar(iid):
                return zeile(tmp, "SELECT inventory_no FROM mat_item WHERE id = ?", (iid,))["inventory_no"]
            # Die Material-Verwaltung legt an und sieht alle Bestände – ihre Zahlen zählen alles.
            r = anlegen(k["katalog"], hms, title="Alle Karabiner", mail=False)
            assert r.status_code == 201 and r.json["betroffen"] == 5, r.get_json()
            r = anlegen(k["katalog"], hms, title="Nur Nachbarstadt", serials="TEST-NS-2", mail=False)
            assert r.status_code == 201 and r.json["betroffen"] == 1, r.get_json()
            for c, eigene, fremde in ((w, set(art.values()), set(ns_art.values())),
                                      (wart_ns, set(ns_art.values()), set(art.values()))):
                start = c.get("/api/material/start").json["rueckrufe"]
                liste = {x["title"]: x for x in c.get("/api/material/rueckrufe").json["rueckrufe"]}
                rr = {x["title"]: x for x in c.get(RR.format(hms)).json["rueckrufe"]}
                produkt = {x["title"]: x for x in c.get(f"/api/material/produkte/{hms}").json["produkt"]["rueckrufe"]}
                assert set(liste) == set(rr) == set(produkt) == {"Alle Karabiner", "Nur Nachbarstadt"}, liste
                for quelle in (liste, rr, produkt):
                    assert quelle["Alle Karabiner"]["betroffen"] == len(eigene), quelle
                for quelle in (rr, produkt):
                    ids_ = {a["id"] for x in quelle.values() for a in x["artikel"]}
                    assert ids_ <= eigene and not ids_ & fremde, (quelle, eigene)
                    assert {a["id"] for a in quelle["Alle Karabiner"]["artikel"]} == eigene
                if c is w:
                    assert [x["title"] for x in start] == ["Alle Karabiner"], start
                    assert liste["Nur Nachbarstadt"]["betroffen"] == 0
                else:
                    assert [x["title"] for x in start] == ["Nur Nachbarstadt", "Alle Karabiner"], start
                    assert (liste["Nur Nachbarstadt"]["betroffen"], liste["Nur Nachbarstadt"]["offen"]) == (1, 1)
                # Inventarnummern fremder Artikel stehen nirgends (die Seriennummern des Rückrufs selbst schon – sie
                # gehören zur Meldung des Herstellers, nicht zum Bestand).
                text = "".join(c.get(u).get_data(as_text=True) for u in ("/api/material/rueckrufe", RR.format(hms)))
                text += json.dumps([start, c.get(f"/api/material/produkte/{hms}").json["produkt"]["rueckrufe"]])
                for i in fremde:
                    assert inventar(i) not in text, (i, text)
                for i in eigene:
                    assert inventar(i) in text, i
            # Die Verwaltung: alles.
            liste = {x["title"]: x for x in k["adm"].get("/api/material/rueckrufe").json["rueckrufe"]}
            assert (liste["Alle Karabiner"]["betroffen"], liste["Nur Nachbarstadt"]["betroffen"]) == (5, 1), liste
            # Die Marke „Rückruf“ in der Ordnerliste und das Banner am eigenen Artikel bleiben.
            zeilen = {x["id"]: x["rueckruf"] for x in w.get(f"/api/material/ordner/{lager}").json["ordner"]["artikel"]}
            assert zeilen[art["RR-1"]] == "Alle Karabiner", zeilen
            a = w.get(f"/api/material/artikel/{art['RR-1']}").json["artikel"]
            assert [x["title"] for x in a["rueckrufe"]] == ["Alle Karabiner"], a["rueckrufe"]
    finally:
        post_zurueck(alt)
    print("Rückrufe: Listen je Bereich bestanden.")


if __name__ == "__main__":
    test_rechte_und_eingaben()
    test_betroffene_und_hinweise()
    test_mail_empfaenger()
    test_mail_im_hintergrund()
    test_sperre_und_zustand()
    test_beenden_und_loeschen()
    test_lebenslauf_und_pruefung()
    test_review_lieferung4()
    test_anlegen_nur_material_verwaltung()
    test_listen_je_bereich()
