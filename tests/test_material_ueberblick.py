"""Rauchtest für das Modul „Material“, Lieferung 4 – Überblick:  python tests/test_material_ueberblick.py

Die Smoke-Tests aus dem Auftrag: Die Zählung je Ordner stimmt mit dem abgeleiteten Status überein; die
Führungskraft sieht alles und kann nichts ändern; /m/<token> öffnet den richtigen Artikel und zeigt
„ausgesondert“ prominent. Alle Namen, Hersteller und Prüfpunkte hier sind erfunden und nur für den Test da."""
import io
import os
import re
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, _heute, festschreiben, gliederung, jpeg, katalog_grund,  # noqa: E402
                           neuer_artikel, pruef_formulare, starten, umgebung)


def ordner_neu(c, parent_id, name, kind="standort"):
    r = c.post("/api/material/ordner", json={"name": name, "kind": kind, "parent_id": parent_id})
    assert r.status_code == 201, r.get_json()
    return r.json["ordner"]["id"]


def zustand(app, iid, **felder):
    """Letzte Prüfung und Fälligkeit direkt setzen – so entstehen die Zustände ohne eine Prüfung je Artikel."""
    with app.app_context():
        from app import db
        db.execute(f"UPDATE mat_item SET {', '.join(f'{k} = ?' for k in felder)} WHERE id = ?", (*felder.values(), iid))


def sperren(p, iid, grund="beschaedigung"):
    r = p.post(f"/api/material/artikel/{iid}/sperren", json={"grund": grund, "text": "Testsperre"})
    assert r.status_code == 200, r.get_json()
    return r.json["artikel"]


@contextmanager
def ohne_post():
    """Mails der Produktmeldungen nicht verschicken, sondern verwerfen (wie in test_material.test_produktmeldung)."""
    from app.material.services import meldung
    alt = (meldung.HINTERGRUND, meldung.send_mail)
    meldung.HINTERGRUND = lambda f, *a: f(*a)
    meldung.send_mail = lambda an, betreff, inhalt: True
    try:
        yield
    finally:
        meldung.HINTERGRUND, meldung.send_mail = alt


# --- 1. Zählung je Ordner ---------------------------------------------------------------------------------

def test_zaehlung_je_ordner():
    """Für jeden Ordner: Zahlen aus /ordner (Ordnerleiste) und /start (Übersicht) gegen eine Neuberechnung mit
    status.status je Artikel; Systemordner zählen bei ihrer Gliederung; jede Zahl führt zu genau so vielen Artikeln."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w, p1, f = k["wart"], k["pruefer"], k["fuehrung"]
        h = _heute()

        def tag(n):
            return (h + timedelta(days=n)).isoformat()

        # Gliederung → Lager → Fahrzeug → Satz (drei Ebenen), daneben eine Halle und eine Gliederung in der
        # Gliederung (mit eigenen Systemordnern); dazu eine zweite, leere Gliederung.
        gid, system = gliederung(w, "OG Prüfstadt")
        lager = ordner_neu(w, gid, "Lager")
        fahrzeug = ordner_neu(w, lager, "Fahrzeug Eins", "fahrzeug")
        satz = ordner_neu(w, fahrzeug, "Satz Eins", "set")
        halle = ordner_neu(w, gid, "Halle")
        nord = ordner_neu(w, gid, "Ortsgruppe Nord", "gliederung")
        leer_gid, _ = gliederung(w, "OG Leerstadt")

        # Artikel in allen Zuständen.
        neu = neuer_artikel(w, ids["hms"], satz)                                        # neu (Eingangsprüfung offen)
        bereit = neuer_artikel(w, ids["hms"], fahrzeug)
        zustand(app, bereit["id"], last_inspected_on=tag(-30), next_due_on=tag(200))     # einsatzbereit
        bald = neuer_artikel(w, ids["hms"], lager)
        zustand(app, bald["id"], last_inspected_on=tag(-300), next_due_on=tag(10))       # bald fällig
        ueber = neuer_artikel(w, ids["hms"], halle)
        zustand(app, ueber["id"], last_inspected_on=tag(-400), next_due_on=tag(-5))      # überfällig
        ohne_datum = neuer_artikel(w, ids["hms"], nord)
        zustand(app, ohne_datum["id"], last_inspected_on=tag(-400), next_due_on=None)    # überfällig, ohne Fälligkeit
        bereit_nord = neuer_artikel(w, ids["hms"], nord)
        zustand(app, bereit_nord["id"], last_inspected_on=tag(-20), next_due_on=tag(100))
        gesperrt = neuer_artikel(w, ids["hms"], satz)
        a = sperren(p1, gesperrt["id"])                                                   # gesperrt, Herkunft Satz
        assert a["folder_id"] == system["gesperrt"] and a["origin_folder_id"] == satz, a
        verloren = neuer_artikel(w, ids["hms"], nord)
        assert sperren(p1, verloren["id"], "verlust")["lock_state"] == "verloren"        # verloren → gesperrt
        alt = neuer_artikel(w, ids["gurt"], halle, manufactured_on=f"{h.year - 11}-01")
        assert alt["status"] == "lebensdauer", alt                                        # textil, Lebensende vorbei
        weg = neuer_artikel(w, ids["hms"], lager)
        sperren(p1, weg["id"])
        r = w.post(f"/api/material/artikel/{weg['id']}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 200 and r.json["artikel"]["folder_id"] == system["ausgesondert"], r.get_json()

        with app.app_context():
            from app import db
            from app.material.services import status as st
            artikel = db.query("SELECT * FROM mat_item")
            stati = {i["id"]: st.status(i) for i in artikel}
        assert set(stati.values()) == set(st.STATUS), Counter(stati.values())

        baum = {o["id"]: o for o in f.get("/api/material/ordner").json["ordner"]}

        def zweig(fid):
            out, offen = set(), [fid]
            while offen:
                x = offen.pop()
                out.add(x)
                offen.extend(o["id"] for o in baum.values() if o["parent_id"] == x)
            return out

        def zaehlen(ordner_ids):
            z = Counter(stati[i["id"]] for i in artikel if i["folder_id"] in ordner_ids)
            return {s: z.get(s, 0) for s in st.STATUS}

        def naechste(ordner_ids):
            tage = [i["next_due_on"] for i in artikel if i["folder_id"] in ordner_ids and i["next_due_on"]
                    and stati[i["id"]] in ("einsatzbereit", "bald_faellig", "ueberfaellig")]
            return min(tage) if tage else None

        # Ordnerleiste und Bestand (/ordner): direkt, ganzer Zweig, Bestand ohne ausgesonderte.
        for fid, o in baum.items():
            assert o["direkt"] == zaehlen({fid}), (o["name"], o["direkt"])
            assert o["zaehlung"] == zaehlen(zweig(fid)), (o["name"], o["zaehlung"], zaehlen(zweig(fid)))
            assert o["bestand"] == sum(n for s, n in o["zaehlung"].items() if s != "ausgesondert"), o["name"]

        # Übersicht (/start): eine Zeile je Ordner außer den Systemordnern, dieselben Zahlen.
        start = f.get("/api/material/start").json
        zeilen = start["ordner_uebersicht"]
        assert {z["id"] for z in zeilen} == {fid for fid, o in baum.items() if not o["system_kind"]}
        for z in zeilen:
            assert z["zaehlung"] == baum[z["id"]]["zaehlung"] and z["bestand"] == baum[z["id"]]["bestand"], z["name"]
            assert z["naechste"] == naechste(zweig(z["id"])), (z["name"], z["naechste"])
            assert z["unterordner"] == sum(1 for o in baum.values() if o["parent_id"] == z["id"] and not o["system_kind"])
        # Baumreihenfolge: Oberordner zuerst, jeder Zweig am Stück und eine Ebene tiefer eingerückt.
        for n, z in enumerate(zeilen):
            if z["parent_id"] is None:
                assert z["tiefe"] == 0, z
            else:
                eltern = [x for x in zeilen[:n] if x["id"] == z["parent_id"]]
                assert eltern and eltern[0]["tiefe"] + 1 == z["tiefe"], z
            ende = n + 1
            while ende < len(zeilen) and zeilen[ende]["tiefe"] > z["tiefe"]:
                ende += 1
            assert {x["id"] for x in zeilen[n + 1:ende]} == {x for x in zweig(z["id"]) - {z["id"]}
                                                            if not baum[x]["system_kind"]}, z["name"]
        zeile = {z["id"]: z for z in zeilen}

        # Von Hand nachgezählt: Gesperrte und ausgesonderte zählen bei ihrer Gliederung, nicht im Herkunftsordner;
        # die Gliederung in der Gliederung zählt im Oberordner mit – einmal.
        g = zeile[gid]["zaehlung"]
        assert g == {"einsatzbereit": 2, "bald_faellig": 1, "ueberfaellig": 2, "neu": 1, "gesperrt": 2, "lebensdauer": 1,
                     "ausgesondert": 1}, g
        assert zeile[gid]["bestand"] == 9 and zeile[gid]["naechste"] == tag(-5)
        assert zeile[gid]["naechste_status"] == "ueberfaellig"
        assert zeile[satz]["zaehlung"]["gesperrt"] == 0 and zeile[satz]["bestand"] == 1 and zeile[satz]["naechste"] is None
        assert zeile[lager]["bestand"] == 3 and zeile[lager]["zaehlung"]["ausgesondert"] == 0
        assert zeile[lager]["naechste"] == tag(10) and zeile[lager]["naechste_status"] == "bald_faellig"
        assert zeile[fahrzeug]["naechste"] == tag(200) and zeile[fahrzeug]["naechste_status"] == "einsatzbereit"
        assert zeile[halle]["zaehlung"]["lebensdauer"] == 1 and zeile[halle]["naechste"] == tag(-5)
        assert zeile[nord]["zaehlung"] == {"einsatzbereit": 1, "bald_faellig": 0, "ueberfaellig": 1, "neu": 0, "gesperrt": 1,
                                           "lebensdauer": 0, "ausgesondert": 0}, zeile[nord]
        assert zeile[nord]["tiefe"] == 1 and zeile[nord]["naechste"] == tag(100)     # ohne Datum zählt nicht mit
        assert zeile[leer_gid]["bestand"] == 0 and zeile[leer_gid]["naechste"] is None
        assert [zeile[x]["tiefe"] for x in (gid, lager, fahrzeug, satz, halle, nord, leer_gid)] == [0, 1, 2, 3, 1, 1, 0]

        # Gesamtzahl = Summe der obersten Zeilen (nichts doppelt) = Zählung über alle Artikel.
        oben = [z for z in zeilen if z["parent_id"] is None]
        assert sum(z["bestand"] for z in oben) == start["bestand"] == 9
        assert {s: sum(z["zaehlung"][s] for z in oben) for s in st.STATUS} == start["zaehlung"] == zaehlen(set(baum))
        # Die alte Liste der Gliederungen bleibt (auch die innere) – die Übersicht nutzt sie nicht mehr.
        assert {o["id"] for o in start["gliederungen"]} == {gid, nord, leer_gid}

        # Jede Zahl führt zu genau diesen Artikeln (Prüfungen, nach Ordner und Status gefiltert).
        for z in zeilen:
            for s in ("ueberfaellig", "neu", "bald_faellig", "gesperrt", "lebensdauer"):
                r = f.get("/api/material/faellig", query_string={"ordner": z["id"], "status": s, "pro_seite": 1})
                assert r.status_code == 200 and r.json["gesamt"] == z["zaehlung"][s], (z["name"], s, r.get_json())
            r = f.get("/api/material/faellig", query_string={"ordner": z["id"]})
            assert r.json["gesamt"] == sum(z["zaehlung"][s] for s in ("ueberfaellig", "lebensdauer", "neu", "bald_faellig"))
            assert r.json["ordner"]["id"] == z["id"] and r.json["ordner"]["pfad"][-1]["name"] == z["name"]
        # „Fällig“ umfasst Lebensdauer erreicht – wie das rote Abzeichen der Ordnerleiste; die erste Seite der Übersicht
        # stellt sie gleich hinter die überfälligen.
        assert start["faellig_gesamt"] == 2 + 1 + 1 + 1
        assert [x["status"] for x in start["naechste"]][:3] == ["ueberfaellig", "ueberfaellig", "lebensdauer"], start["naechste"]
    print("Zählung je Ordner bestanden.")


# --- 2. Führungskraft: sieht alles (in ihrer Gliederung), ändert nichts ------------------------------------------

SCHREIBEN = {"POST", "PUT", "PATCH", "DELETE"}
# Routen, die Dateien als Formular annehmen – sie bekommen eine Multipart-Anfrage wie aus dem Browser.
MULTIPART = {"material_api.produkt_bild", "material_api.ordner_foto", "material_api.dokument_neu",
             "material_api.dokument_version", "material_api.kategorie_dokument_neu", "material_api.punkt_foto",
             "material_api.anhang_neu", "material_api.meldung_anlegen", "material_api.pruefen"}
# Ausdrücklich erlaubt – mit Begründung und der Antwort, die die Führungskraft dort bekommt.
AUSNAHMEN_SCHREIBEN = {
    # Die Prüfseite ist für jeden, auch ohne Anmeldung; sie speichert nichts (ohne Datei: 400).
    ("POST", "material_api.pruefen"): 400,
    # Die eigene Unterschrift entfernen darf jeder – es sind seine Daten (hier ist keine da).
    ("DELETE", "material_api.unterschrift_entfernen"): 200,
    # Eine Meldung löscht nur ihr Melder; die des Materialwarts bleibt (403 aus dem Dienst, nicht aus der Rolle).
    ("DELETE", "material_api.meldung_loeschen"): 403,
}
# Ebenso nach dem Pfad (Phase 2, für die Routen der Pakete B, C, D): Die globale Suche und der QR-Steckbrief stehen
# jedem mit Modulzugang offen – ohne Bestätigung antworten sie 400 und schreiben nichts.
AUSNAHMEN_SCHREIBEN_PFAD = {
    ("POST", "/api/material/globalsuche"): 400,
    ("POST", "/api/material/globalsuche/qr"): 400,
}
# Lesen: was nicht 200 liefert, und warum.
AUSNAHMEN_LESEN = {
    "material.qr_ziel": 302,                       # /m/<token> leitet zum Artikel weiter
}
# Werkzeuge der Katalogpflege (Katalogaustausch, Lieferung 4) sind nur für Katalogpfleger; den Katalog selbst liest die
# Führungskraft über /kategorien und /produkte.
NUR_KATALOGPFLEGE = ("/api/material/katalog/",)
# Phase 2: Freigaben eines Ordners oder Kontos, die Nutzersuche und das Protokoll der globalen Suche liest nur, wer
# verwaltet (bzw. die Verwaltung) – die Führungskraft bekommt 403. „Meine Freigaben“ liest jeder Angemeldete.
NUR_VERWALTER_LESEN = re.compile(r"^/api/material/(ordner/<int:fid>/freigaben|freigaben|nutzer|globalsuche/protokoll)$")
# Abfrageparameter, ohne die eine Route nichts zu lesen hätte (400).
ABFRAGE = {
    "material_api.formulare": lambda e: {"produkt": e[("produkte", "pid")]},
    "material_api.artikel_vorschlag": lambda e: {"product_id": e[("produkte", "pid")], "folder_id": e[("ordner", "fid")]},
    "material_api.artikelnummer_pruefen": lambda e: {"nr": "GA-100"},
}
# pid, fid und rid heißen in verschiedenen Routen verschiedene Dinge (Produkt/Prüfung, Ordner/Formular,
# Durchgang/Prüfpunkt) – für sie entscheidet der Pfadabschnitt davor.
MEHRDEUTIG = {"pid", "fid", "rid"}
_PARAM = re.compile(r"<(?:[^<>:]+:)?(\w+)>")


def _url(regel, kennungen):
    """Pfad der Regel mit Kennungen aus der vorher aufgebauten Umgebung. Fehlt eine, scheitert der Test laut –
    eine neue Route braucht hier ihre Kennung."""
    teile = regel.rule.split("/")
    for n, teil in enumerate(teile):
        def ersetzen(m, davor=teile[n - 1]):
            name = m.group(1)
            if (davor, name) in kennungen:
                return str(kennungen[(davor, name)])
            if name in kennungen and name not in MEHRDEUTIG:
                return str(kennungen[name])
            raise AssertionError(f"Keine Kennung für <{name}> nach „{davor}“ in {regel.rule} ({regel.endpoint}) – "
                                 "bitte in test_fuehrungskraft_nur_lesen ergänzen.")
        teile[n] = _PARAM.sub(ersetzen, teil)
    return "/".join(teile)


def _stand(app):
    """Alle Zeilen der Modultabellen und die Unterschrift der Führungskraft – vorher und nachher gleich."""
    with app.app_context():
        from app import db
        tabellen = [r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat\\_%' "
                                                 "ESCAPE '\\' AND name NOT LIKE '%fts%' ORDER BY name")]
        out = {t: db.query(f"SELECT * FROM {t} ORDER BY rowid") for t in tabellen}
        out["users"] = db.query("SELECT id, recht_material, mat_pruefer, mat_katalog, urkundennummer, signature_png "
                                "FROM users ORDER BY id")
        return out


def test_fuehrungskraft_nur_lesen():
    """Alle schreibenden Routen der Material-Blueprints liefern der Führungskraft 403 (nicht von der CSRF-Wache),
    alle lesenden 200 – und am Ende hat sich in keiner Tabelle des Moduls etwas geändert."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        formulare = pruef_formulare(k["katalog"], ids)
        kp, w, p1, f = k["katalog"], k["wart"], k["pruefer"], k["fuehrung"]
        h = _heute()
        # Katalog: Produkt mit Bild und Herstellerdokument.
        r = kp.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        bild = r.json["produkt"]["bild"]
        r = kp.post(f"/api/material/produkte/{ids['gurt']}/dokumente", headers=H, content_type="multipart/form-data",
                    data={"kind": "gebrauchsanleitung", "file": (io.BytesIO(PDF), "anleitung.pdf")})
        assert r.status_code == 201, r.get_json()
        did = r.json["dokument_id"]
        # Bestand: Gliederung mit Lager, zwei Artikel.
        gid, _ = gliederung(w)
        lager = ordner_neu(w, gid, "Lager")
        a1 = neuer_artikel(w, ids["hms"], lager)
        a2 = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{h.year - 1}-01")
        # Ein Durchgang über das Lager mit einer festgeschriebenen Prüfung samt Anhang – abgeschlossen, mit Sammelprotokoll.
        rid = w.post("/api/material/durchgaenge", json={"folder_id": lager, "titel": "Jahresprüfung Test"}).json["durchgang"]["id"]
        fest = starten(p1, a1["id"], durchgang_id=rid).json["pruefung"]["id"]
        r = p1.post(f"/api/material/pruefungen/{fest}/anhaenge", headers=H, content_type="multipart/form-data",
                    data={"file": [(jpeg(), "foto.jpg")], "art": "foto", "titel": "Testfoto", "im_protokoll": "nein"})
        assert r.status_code == 201, r.get_json()
        aid = r.json["anhang"]["id"]
        assert festschreiben(p1, fest, ergebnis="einsatzbereit").status_code == 200
        assert w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
        # Ein Entwurf des Prüfers (reserviert den zweiten Artikel) mit seinen Prüfpunkten.
        pr = starten(p1, a2["id"]).json["pruefung"]
        entwurf, punkt = pr["id"], pr["punkte"][0]["id"]
        # Eine Meldung des Materialwarts und ein Rückruf am Produkt (direkt in die Tabelle aus Schemaschritt 7).
        r = w.post("/api/material/meldungen", json={"manufacturer": "Meldewerk", "model": "Gurt Omega"}, headers=H)
        assert r.status_code == 201, r.get_json()
        mid = r.json["meldung"]["id"]
        with app.app_context():
            from app import db
            ruid = db.execute("INSERT INTO mat_recall (product_id, title, created_at) VALUES (?, ?, ?)",
                              (ids["hms"], "Testrückruf", db.now()))
        token = a1["qr_adresse"].rsplit("/", 1)[1]
        with app.app_context():
            from app import db
            # Eine Freigabe (Phase 2) – die des Materialwarts an der Gliederung, nicht die eigene der Führungskraft.
            freigabe = db.query("SELECT id FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission = "
                                "'verwalten'", (gid, k["wart_id"]), one=True)["id"]
        kennungen = {
            "kid": ids["gurte"], "did": did, "iid": a1["id"], "mid": mid, "aid": aid, "ruid": ruid, "token": token,
            "gid": freigabe,
            "art": "web", "dateiname": bild.rsplit("/", 1)[1], "filename": "material.js",
            ("produkte", "pid"): ids["gurt"], ("produkt", "pid"): ids["gurt"],
            ("pruefungen", "pid"): entwurf, ("pruefung", "pid"): fest, ("punkte", "rid"): punkt,
            ("ordner", "fid"): gid, ("formulare", "fid"): formulare["spezifisch"], ("formular", "fid"): formulare["spezifisch"],
            ("durchgaenge", "rid"): rid, ("durchgang", "rid"): rid,
            ("export", "fid"): gid,                         # CSV und Protokoll-ZIP je Ordner
        }

        darf = f.get("/api/material/start").json["darf"]
        assert darf["lesen"] and not (darf["verwalten"] or darf["pruefen"] or darf["katalog"]), darf
        regeln = [r for r in app.url_map.iter_rules() if r.endpoint.split(".")[0] in ("material", "material_api")]
        vorher = _stand(app)

        # a) Schreiben: 403 – mit der Meldung der Rechteprüfung, nicht der CSRF-Wache (X-Requested-With, JSON).
        geprueft = 0
        for regel in regeln:
            for methode in sorted(regel.methods & SCHREIBEN):
                url = _url(regel, kennungen)
                if regel.endpoint in MULTIPART:
                    r = f.open(url, method=methode, headers=H, content_type="multipart/form-data",
                               data={"file": (jpeg(), "x.jpg"), "titel": "x"})
                else:
                    r = f.open(url, method=methode, headers=H, json={})
                fehler = (r.get_json(silent=True) or {}).get("error", "")
                soll = AUSNAHMEN_SCHREIBEN.get((methode, regel.endpoint),
                                               AUSNAHMEN_SCHREIBEN_PFAD.get((methode, regel.rule), 403))
                assert r.status_code == soll, (methode, url, r.status_code, fehler)
                if r.status_code == 403:
                    assert fehler and "X-Requested-With" not in fehler and "fremder Seite" not in fehler, (methode, url, fehler)
                geprueft += 1
        assert geprueft >= 56, geprueft                    # so viele waren es in Lieferung 4
        # Auch die eigene Unterschrift hinterlegen darf sie nicht – sie schreibt nichts fest und sondert nichts aus.
        r = f.put("/api/material/unterschrift", json={"bild": "data:image/png;base64,AAAA"})
        assert r.status_code == 403 and "Materialwarte und Prüfer" in r.json["error"], r.get_json()
        # Eine Urkundennummer eintragen auch nicht – das geht nur mit dem Häkchen „Prüfer“ (Lieferung 5).
        assert any(x.rule == "/api/material/urkundennummer" and "PUT" in x.methods for x in regeln)
        r = f.put("/api/material/urkundennummer", json={"urkundennummer": "1012-0001"})
        assert r.status_code == 403 and "Häkchen" in r.json["error"], r.get_json()
        assert _stand(app) == vorher, "Die Führungskraft hat etwas verändert."

        # b) Lesen: jede Seite und jede Schnittstelle des Moduls.
        gelesen = 0
        for regel in regeln:
            if "GET" not in regel.methods:
                continue
            url = _url(regel, kennungen)
            r = f.get(url, query_string=ABFRAGE[regel.endpoint](kennungen) if regel.endpoint in ABFRAGE else None)
            soll = (403 if url.startswith(NUR_KATALOGPFLEGE) or NUR_VERWALTER_LESEN.match(regel.rule)
                    else AUSNAHMEN_LESEN.get(regel.endpoint, 200))
            assert r.status_code == soll, (url, r.status_code, r.get_json(silent=True) or r.data[:200])
            gelesen += 1
        assert gelesen >= 42, gelesen                      # so viele waren es in Lieferung 4
        r = f.get(f"/m/{token}")
        assert r.headers["Location"].endswith(f"/material/artikel/{a1['id']}"), r.headers["Location"]
        # Die Produktmeldungen liest sie – alle, aber ohne Knöpfe zum Abarbeiten.
        r = f.get("/api/material/meldungen")
        assert r.json["alle"] and not r.json["bearbeiten"] and [m["id"] for m in r.json["meldungen"]] == [mid], r.get_json()
        assert f.get(f"/api/material/meldungen/{mid}").json["meldung"]["model"] == "Gurt Omega"
        # Fremde Entwürfe, festgeschriebene Protokolle und Sammelprotokolle sieht sie auch.
        assert f.get(f"/api/material/pruefungen/{entwurf}").json["pruefung"]["entwurf"]
        assert f.get(f"/material/pruefung/{fest}/pdf").mimetype == "application/pdf"
        assert f.get(f"/material/durchgang/{rid}/sammelprotokoll").mimetype == "application/pdf"
        assert _stand(app) == vorher
    print("Führungskraft nur lesend bestanden.")


# --- 3. QR-Ziel eines ausgesonderten Artikels ------------------------------------------------------------------

def test_qr_ausgesondert():
    """/m/<token> führt zum richtigen Artikel; ist er ausgesondert (oder gesperrt, am Lebensende), steht das schon
    im HTML der Seite – vor material.js – und die Schnittstelle meldet den Status."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w, p1, f = k["wart"], k["pruefer"], k["fuehrung"]
        h = _heute()
        gid, system = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        b = neuer_artikel(w, ids["hms"], gid)
        alt = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{h.year - 11}-01")

        def token(x):
            return x["qr_adresse"].rsplit("/", 1)[1]

        def seite_ueber_qr(x):
            r = f.get(f"/m/{token(x)}")
            assert r.status_code == 302 and urlparse(r.headers["Location"]).path == f"/material/artikel/{x['id']}", r.headers
            r = f.get(r.headers["Location"])
            assert r.status_code == 200
            return r.get_data(as_text=True)

        # Im Dienst: kein Hinweis.
        assert "mat-banner" not in seite_ueber_qr(b)
        # Gesperrt: Hinweis mit Grund; Lebensdauer erreicht: ebenso.
        sperren(p1, a["id"])
        html = seite_ueber_qr(a)
        assert 'class="mat-banner s-gesperrt"' in html and f"– {a['inventory_no']} nicht verwenden" in html, html[-900:]
        assert "Beschädigung: Testsperre" in html
        assert 'class="mat-banner s-lebensdauer"' in seite_ueber_qr(alt)
        # Ausgesondert: Weiterleitung zum richtigen Artikel, der Hinweis prominent in #mat-inhalt (material.js ersetzt
        # ihn beim Zeichnen durch die Ansicht mit eigenem Banner), die Schnittstelle meldet „ausgesondert“.
        r = w.post(f"/api/material/artikel/{a['id']}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 200, r.get_json()
        html = seite_ueber_qr(a)
        assert re.search(r'<div id="mat-inhalt"><p class="mat-banner s-ausgesondert" role="alert">AUSGESONDERT – '
                         + re.escape(a["inventory_no"]) + " ist außer Dienst und darf nicht mehr verwendet werden.</p>", html), \
            html[-900:]
        x = f.get(f"/api/material/artikel/{a['id']}").json["artikel"]
        assert x["status"] == "ausgesondert" and x["folder_id"] == system["ausgesondert"], x
        assert "mat-banner" not in seite_ueber_qr(b)
        # Unbekanntes Token: 404. Ohne Anmeldung: zur Anmeldung, danach zurück zum Token. Ohne Zugang: 403, kein Hinweis.
        assert f.get("/m/GibtEsNicht-0000").status_code == 404
        r = app.test_client().get(f"/m/{token(a)}")
        ziel = urlparse(r.headers["Location"])
        assert r.status_code == 302 and ziel.path == "/login" and parse_qs(ziel.query)["next"] == [f"/m/{token(a)}"], r.headers
        assert k["nutzer"].get(f"/m/{token(a)}").status_code == 403
        r = k["nutzer"].get(f"/material/artikel/{a['id']}")
        assert r.status_code == 403 and "AUSGESONDERT" not in r.get_data(as_text=True)
        r = app.test_client().get(f"/material/artikel/{a['id']}")
        assert r.status_code == 302 and "AUSGESONDERT" not in r.get_data(as_text=True)
    print("QR-Ziel ausgesondert bestanden.")


if __name__ == "__main__":
    test_zaehlung_je_ordner()
    test_fuehrungskraft_nur_lesen()
    test_qr_ausgesondert()
