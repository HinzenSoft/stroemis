"""Rauchtest für den Jahresbericht je Zweig (Phase 4 · Lieferung 1, Entwurf Abschnitt A und D):
python tests/test_material_bericht.py  oder  pytest tests/test_material_bericht.py

Fester Aufbau über zwei Jahre (die Uhr des Moduls wird für das Vorjahr verstellt, wie in test_material_erinnerung):
Statuszeilen genau nach status.STATUS; Berichtigung nach Durchgangsende zählt einmal; Aussonderung aus Prüfung zählt
nicht als Prüfung; kritischer Mangel; Sperren aus dem Journal (Meldung am gesperrten Artikel zählt nicht, Verlust eigene
Art, kein Pfadtext); Journaleintrag am 31.12. um 23:30 UTC im Folgejahr; Unterordner mit gesperrtem Artikel nach
Heimat; Untergliederung als Zeile; DEMO-Kennzeichnung; Haken „Prüfer nennen“; Rechte; Eingaben; PDF-Seiten und PDF/A;
CSV mit Formelschutz; Kappung im PDF; eine Sichtberechnung je Anfrage. Alle Namen, Hersteller, Prüfpunkte und Gründe
sind Platzhalter."""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _flach, _heute, festschreiben, freigeben, gliederung, jpeg, katalog_grund,  # noqa: E402
                           neuer_artikel, neues_konto, pdf_seiten, protokoll_zeile, pruef_formulare, punkte_von,
                           starten, umgebung)
from test_material_export import CSP_PDF, csv_lesen  # noqa: E402

ZONE = ZoneInfo("Europe/Berlin")
ST_VERA = "/home/harness/devtools/bin/st-vera"


# --- Hilfen --------------------------------------------------------------------------------------------------------

class Uhr(datetime):
    """Ersetzt services.datetime: heute() und jetzt() rechnen dann mit dieser Uhr (Muster aus test_material_erinnerung).
    db.now() (UTC-Zeitstempel der Zeilen) bleibt die echte Uhr – Zeitstempel des Vorjahrs setzt der Aufbau direkt."""
    jetzt = None

    @classmethod
    def now(cls, tz=None):
        return cls.jetzt.astimezone(tz) if tz else cls.jetzt


@contextmanager
def uhr(tag):
    from app.material import services
    alt = services.datetime
    Uhr.jetzt = datetime(tag.year, tag.month, tag.day, 9, 0, tzinfo=ZONE)
    services.datetime = Uhr
    try:
        yield
    finally:
        services.datetime = alt


def sql(tmp, befehl, args=()):
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    try:
        with conn:
            conn.execute(befehl, args)
    finally:
        conn.close()


def ordner_neu(c, name, parent, art="standort"):
    r = c.post("/api/material/ordner", json={"name": name, "kind": art, "parent_id": parent})
    assert r.status_code == 201, r.get_json()
    return r.json["ordner"]["id"]


def sperren(c, iid, grund, text=None):
    r = c.post(f"/api/material/artikel/{iid}/sperren", json={"grund": grund, **({"text": text} if text else {})})
    assert r.status_code == 200, r.get_json()


def pruefung(c, iid, ergebnis, durchgang_id=None, art=None, **d):
    """Eine Prüfung mit Ergebnis (Karabiner: Sollwerte vorbelegt). Liefert die Kennung."""
    r = starten(c, iid, **({"durchgang_id": durchgang_id} if durchgang_id else {}), **({"art": art} if art else {}))
    assert r.status_code in (200, 201), r.get_json()
    pid = r.json["pruefung"]["id"]
    r = festschreiben(c, pid, ergebnis=ergebnis, **d)
    assert r.status_code == 200, r.get_json()
    return pid


def bericht(c, fid, **args):
    r = c.get(f"/api/material/ordner/{fid}/bericht", query_string=args)
    assert r.status_code == 200, (r.status_code, r.get_json())
    assert "no-store" in r.headers["Cache-Control"], r.headers["Cache-Control"]
    return r.json["bericht"]


def journal_zahl(app):
    with app.app_context():
        from app import db
        return db.query("SELECT COUNT(*) AS n FROM mat_audit", one=True)["n"]


def pdf_text(c, url, pfad):
    r = c.get(url)
    assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data.startswith(b"%PDF"), r.status_code
    with open(pfad, "wb") as fh:
        fh.write(r.data)
    return r, pdf_seiten(pfad)


def aufbau(tmp):
    """Eine Gliederung „OG Berichtstadt“ mit Fahrzeug (darin Fach 1), Lager und der Untergliederung „OG Unterstadt“;
    ein DEMO-Produkt; Artikel über zwei Jahre (J-1 = Vorjahr, J = laufendes Jahr):
      alt       Fahrzeug; Eingangsprüfung in J-1, in J im Durchgang geprüft, danach (nach Durchgangsende) berichtigt
      grenze    Lager, angelegt 1.1. J-1 (Zeitstempel direkt gesetzt); zwei Journal-Sperren von Hand: 31.12. J-1
                22:30 UTC (zählt J-1) und 23:30 UTC (zählt J, Ortszeit 1.1.), mit fremdem Pfadtext im Journal
      fach_a    Fach 1; im Durchgang ausgenommen („nicht auffindbar“), nie geprüft
      krit      Fahrzeug; Eingangsprüfung mit kritischem Mangel → instandsetzen → gesperrt (aus Prüfung)
      aus       Fahrzeug; Eingangsprüfung mit „aussondern empfohlen“ → gesperrt (aus Prüfung), nach dem Durchgang vom
                Materialwart ausgesondert („irreparabel“; seit Schritt 28 – vorher sonderte die Prüfung selbst aus)
      unter     Fach 1; vom Prüfer gesperrt (Beschädigung), im Durchgang ausgenommen – Heimat bleibt das Fach
      verlust   Lager; Verlust gemeldet, vom Materialwart ausgesondert
      verloren  Lager; Verlust gemeldet (bleibt gesperrt/verloren)
      mangel_a  Lager; Mangel gemeldet von der Führungskraft (sperrt), zweite Meldung vom Materialwart (keine Sperre)
      frei      Lager; Eingangsprüfung, Sperre nach Sturz, Freiprüfung (außerplanmäßig) → einsatzbereit; Fälligkeit im
                Ausblick in drei Monaten
      ug_a      Untergliederung, neu
      demo_a    Lager, DEMO-Produkt, offener Entwurf
      gurt_a    Lager, textil, Lebensende in diesem Dezember (Ausblick)
      weg       Lager, gelöscht
    Dazu ein laufender Rückruf zum HMS-Produkt (alle Artikel), eine fremde Gliederung und ein externer Prüfer."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    pruef_formulare(k["katalog"], ids)
    from app.material.services import mangel
    mangel.HINTERGRUND = lambda f, *a: f(*a)          # keine Threads im Test; ohne Mailserver geht ohnehin nichts hinaus
    adm, w, p1, f = k["adm"], k["wart"], k["pruefer"], k["fuehrung"]
    h = _heute()
    J = h.year
    gid, system = gliederung(w, "OG Berichtstadt")
    fz = ordner_neu(w, "Fahrzeug GW", gid, "fahrzeug")
    fach = ordner_neu(w, "Fach 1", fz)
    lager = ordner_neu(w, "Lager", gid)
    ug = ordner_neu(adm, "OG Unterstadt", gid, "gliederung")
    r = k["katalog"].post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                          "model": "HMS Demo", "article_no": "HD-1",
                                                          "material_kind": "metall_hardware", "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    demo_pid = r.json["produkt"]["id"]
    sql(tmp, "UPDATE mat_product SET demo = 1 WHERE id = ?", (demo_pid,))
    a = {}
    # Vorjahr: Uhr des Moduls auf den 15.6. J-1.
    with uhr(date(J - 1, 6, 15)):
        a["alt"] = neuer_artikel(w, ids["hms"], fz, serial_no="=1+2")
        pid_alt0 = pruefung(p1, a["alt"]["id"], "einsatzbereit")
        a["grenze"] = neuer_artikel(w, ids["hms"], lager, serial_no="GRENZE-1")
    sql(tmp, "UPDATE mat_item SET created_at = ? WHERE id = ?", (f"{J - 1}-06-15T08:00:00+00:00", a["alt"]["id"]))
    sql(tmp, "UPDATE mat_item SET created_at = ? WHERE id = ?", (f"{J - 1}-01-01T00:00:00+00:00", a["grenze"]["id"]))
    for zeit, grund in ((f"{J - 1}-12-31T22:30:00+00:00", "Platzhalter Grenze früh"),
                        (f"{J - 1}-12-31T23:30:00+00:00", "Platzhalter Grenze spät")):
        sql(tmp, "INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, after_json, "
                 "created_at) VALUES ('item', ?, NULL, 'Platzhalter', 'gesperrt', ?, ?, ?)",
            (a["grenze"]["id"], json.dumps({"lock_state": "frei", "ordner": "FREMDPFAD / alt"}),
             json.dumps({"lock_state": "gesperrt", "lock_reason": grund, "ordner": "FREMDPFAD / Gesperrt",
                         "herkunft": "FREMDPFAD / Lager"}), zeit))
    # Laufendes Jahr.
    a["fach_a"] = neuer_artikel(w, ids["hms"], fach, serial_no="FACH-1")
    a["krit"] = neuer_artikel(w, ids["hms"], fz, serial_no="KRIT-1")
    a["aus"] = neuer_artikel(w, ids["hms"], fz, serial_no="AUS-1")
    a["unter"] = neuer_artikel(w, ids["hms"], fach, serial_no="UNTER-1")
    r = w.post("/api/material/durchgaenge", json={"folder_id": fz, "titel": "Jahresprüfung Fahrzeug"})
    assert r.status_code == 201, r.get_json()
    rid = r.json["durchgang"]["id"]
    pid_alt = pruefung(p1, a["alt"]["id"], "einsatzbereit", durchgang_id=rid)
    r = starten(p1, a["krit"]["id"], durchgang_id=rid)
    assert r.status_code == 201, r.get_json()
    pr = r.json["pruefung"]
    pk, url = punkte_von(pr), f"/api/material/pruefungen/{pr['id']}/punkte"
    r = p1.put(f"{url}/{pk['Testpunkt Verschluss']}", json={"wert": "nein", "notiz": "Platzhalter Mangel"})
    assert r.status_code == 200 and r.json["punkt"]["befund"] == "mangel", r.get_json()
    r = p1.post(f"{url}/{pk['Testpunkt Verschluss']}/foto", data={"file": (jpeg(), "m.jpg")}, headers=H,
                content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    assert festschreiben(p1, pr["id"], ergebnis="instandsetzen").status_code == 200
    pid_aus = pruefung(p1, a["aus"]["id"], "aussondern_empfohlen", durchgang_id=rid, grund="Platzhalter kaputt")
    r = w.post(f"/api/material/durchgaenge/{rid}/ausnehmen", json={"item_id": a["fach_a"]["id"], "grund": "nicht auffindbar"})
    assert r.status_code == 200, r.get_json()
    sperren(p1, a["unter"]["id"], "beschaedigung", "Platzhalter Riss")
    r = w.post(f"/api/material/durchgaenge/{rid}/ausnehmen", json={"item_id": a["unter"]["id"], "grund": "gesperrt – Platzhalter"})
    assert r.status_code == 200, r.get_json()
    assert w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
    # Berichtigung nach Durchgangsende (round_id leer): Das Original zählt nicht mehr, die Berichtigung einmal.
    r = p1.post(f"/api/material/pruefungen/{pid_alt}/berichtigen", json={"grund": "Platzhalter Bemerkung"})
    assert r.status_code == 201, r.get_json()
    ber = r.json["pruefung"]["id"]
    assert festschreiben(p1, ber, ergebnis="einsatzbereit", bemerkung="Platzhalter nachgetragen").status_code == 200
    a["verlust"] = neuer_artikel(w, ids["hms"], lager, serial_no="VERLUST-1")
    sperren(p1, a["verlust"]["id"], "verlust")
    r = w.post(f"/api/material/artikel/{a['aus']['id']}/aussondern", json={"grund": "irreparabel"})
    assert r.status_code == 200, r.get_json()
    r = w.post(f"/api/material/artikel/{a['verlust']['id']}/aussondern", json={"grund": "verlust", "bemerkung": "Platzhalter weg"})
    assert r.status_code == 200, r.get_json()
    a["verloren"] = neuer_artikel(w, ids["hms"], lager, serial_no="VERLOREN-1")
    sperren(p1, a["verloren"]["id"], "verlust")
    a["mangel_a"] = neuer_artikel(w, ids["hms"], lager, serial_no="MANGEL-1")
    r = f.post(f"/api/material/artikel/{a['mangel_a']['id']}/mangel", headers=H, json={"beschreibung": "Platzhalter Mangel eins"})
    assert r.status_code == 201, r.get_json()
    r = w.post(f"/api/material/artikel/{a['mangel_a']['id']}/mangel", headers=H, json={"beschreibung": "Platzhalter Mangel zwei"})
    assert r.status_code == 201, r.get_json()
    a["frei"] = neuer_artikel(w, ids["hms"], lager, serial_no="FREI-1")
    pruefung(p1, a["frei"]["id"], "einsatzbereit")
    sperren(p1, a["frei"]["id"], "sturz")
    pruefung(p1, a["frei"]["id"], "einsatzbereit", art="ausserplanmaessig")
    in_drei = (h.replace(day=1) + timedelta(days=95)).replace(day=1)            # der Monatserste in drei Monaten
    sql(tmp, "UPDATE mat_item SET next_due_on = ? WHERE id = ?", (in_drei.isoformat(), a["frei"]["id"]))
    a["ug_a"] = neuer_artikel(w, ids["hms"], ug, serial_no="UG-1")
    a["demo_a"] = neuer_artikel(w, demo_pid, lager, serial_no="DEMO-1")
    assert starten(p1, a["demo_a"]["id"]).status_code == 201
    a["gurt_a"] = neuer_artikel(w, ids["gurt"], lager, manufactured_on=f"{J - 10}-12")   # Lebensende 1.12. J
    weg = neuer_artikel(w, ids["hms"], lager, serial_no="WEG-1")
    assert w.delete(f"/api/material/artikel/{weg['id']}", headers=H).status_code == 200
    r = adm.post(f"/api/material/produkte/{ids['hms']}/rueckrufe", json={"title": "Platzhalter Rückruf", "mail": False,
                                                                          "url": "https://www.example.org/rueckruf"})
    assert r.status_code == 201, r.get_json()
    gfremd, _ = gliederung(adm, "OG Fremd", standard=False)
    ext, ext_id = neues_konto(app, "extern@example.org", mat_pruefer=True, urkundennummer="EXT-4711")
    freigeben(adm, gid, ext_id, "pruefen")
    o = {"gid": gid, "system": system, "fz": fz, "fach": fach, "lager": lager, "ug": ug, "rid": rid, "pid_alt0": pid_alt0,
         "pid_alt": pid_alt, "ber": ber, "pid_aus": pid_aus, "gfremd": gfremd, "ext": ext, "J": J, "in_drei": in_drei,
         "demo_pid": demo_pid}
    return app, k, o, a


# --- Zahlen -------------------------------------------------------------------------------------------------------

def test_zahlen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        f, J = k["fuehrung"], o["J"]
        from app.material.services import bericht as dienst
        from app.material.services import status as st
        b = bericht(f, o["gid"])                       # ohne jahr: das laufende, ohne pruefer
        kopf = b["kopf"]
        assert kopf["jahr"] == J and kopf["jahre"] == [J - 1, J] and kopf["pruefer_nennen"] is False, kopf
        assert kopf["ordner"] == "OG Berichtstadt" and kopf["gliederung"] == "OG Berichtstadt" and kopf["artikel"] == 13
        assert kopf["demo"] == 1 and b["dokument"]["demo"] and kopf["ersteller"] == "fuehrung" and kopf["empfaenger"] == "Gliederung intern"
        # Bestand zum Stichtag: Zeilen genau nach status.STATUS, dazu verloren und die Summe ohne ausgesonderte.
        assert [z["status"] for z in b["bestand"]["zeilen"]] == list(st.STATUS)
        assert b["bestand"]["zaehlung"] == {"einsatzbereit": 2, "bald_faellig": 0, "ueberfaellig": 0, "neu": 5, "gesperrt": 4,
                                            "lebensdauer": 0, "ausgesondert": 2}, b["bestand"]["zaehlung"]
        assert b["bestand"]["verloren"] == 1 and b["bestand"]["bestand"] == 11
        kat = {x["name"]: x for x in b["bestand"]["kategorien"]}
        assert kat == {"PSA gegen Absturz": {"name": "PSA gegen Absturz", "bestand": 11, "faellig": 5, "gesperrt": 4}}, kat
        # Aufschlüsselung nach Heimat: der gesperrte „unter“ zählt im Fahrzeug (Fach 1 liegt darunter), nicht in
        # „Gesperrt“; die Untergliederung ist eine Zeile mit Kennzeichen; Systemordner haben keine Zeile.
        u = {x["name"]: x for x in b["bestand"]["unterordner"]}
        assert list(u) == ["Fahrzeug GW", "Lager", "OG Unterstadt"], list(u)
        assert (u["Fahrzeug GW"]["bestand"], u["Fahrzeug GW"]["gesperrt"], u["Fahrzeug GW"]["ausgesondert"]) == (4, 2, 1)
        assert u["Fahrzeug GW"]["zaehlung"]["einsatzbereit"] == 1 and u["Fahrzeug GW"]["zaehlung"]["neu"] == 1
        assert (u["Lager"]["bestand"], u["Lager"]["gesperrt"], u["Lager"]["ausgesondert"], u["Lager"]["demo"]) == (6, 2, 1, False)
        assert u["OG Unterstadt"]["kennzeichen"] == "Gliederung" and u["OG Unterstadt"]["bestand"] == 1
        assert not any(x["kennzeichen"] for x in b["bestand"]["unterordner"] if x["name"] != "OG Unterstadt")
        # Bewegungen: Zugänge im Jahr (alt und grenze stammen aus J-1), gelöscht, Aussonderungen.
        assert b["bewegungen"] == {"zugaenge": 11, "geloescht": 1, "aussonderungen": 2}, b["bewegungen"]
        # Prüfungen: Berichtigung nach Durchgangsende zählt einmal; die Aussonderung aus der Prüfung nicht als Prüfung.
        p = b["pruefungen"]
        assert p["gesamt"] == 5 and p["entwuerfe"] == 1 and p["mit_mangel"] == 1 and p["kritisch"] == 1, p
        assert {x["art"]: x["n"] for x in p["arten"]} == {"eingang": 3, "periodisch": 1, "ausserplanmaessig": 1, "reparatur": 0}
        assert {x["ergebnis"]: x["n"] for x in p["ergebnisse"]} == {"einsatzbereit": 3, "instandsetzen": 1, "aussondern_empfohlen": 1}
        assert p["abdeckung"] == {"bestand": 11, "geprueft": 3, "nicht_geprueft": 8}, p["abdeckung"]
        nicht = {x["inventarnummer"]: x for x in p["nicht_geprueft"]}
        assert set(nicht) == {a[n]["inventory_no"] for n in ("grenze", "fach_a", "unter", "verloren", "mangel_a", "ug_a", "demo_a", "gurt_a")}
        assert nicht[a["demo_a"]["inventory_no"]]["demo"] and not nicht[a["ug_a"]["inventory_no"]]["demo"]
        assert nicht[a["grenze"]["inventory_no"]]["letzte"] == "noch nie"
        # Durchgang: Zahlen über round_id, Ausnahmen mit Grund, Sammelprotokoll-ID als Text, keine Namen.
        assert len(b["durchgaenge"]) == 1
        d = b["durchgaenge"][0]
        s = protokoll_zeile(app, rid=o["rid"])
        assert (d["titel"], d["stand"], d["gesamt"], d["erledigt"], d["ausgenommen"], d["nicht_geprueft"]) == \
            ("Jahresprüfung Fahrzeug", "abgeschlossen", 5, 3, 2, 0), d
        assert d["protokoll_id"] == s["protocol_id"] and "wart" not in json.dumps(d) and not d["demo"]
        assert {x["inventarnummer"]: x["grund"] for x in d["ausnahmen"]} == {a["fach_a"]["inventory_no"]: "nicht auffindbar",
                                                                              a["unter"]["inventory_no"]: "gesperrt – Platzhalter"}
        # Prüfer nur mit Haken.
        assert b["pruefer"] is None
        # Sperren aus dem Journal: die zweite Meldung am gesperrten Artikel zählt nicht; Verlust ist eine eigene Art; der
        # Eintrag vom 31.12. 23:30 UTC gehört zu diesem Jahr; Grund nur aus lock_reason, nie ein Pfadtext.
        sp = b["sperren"]
        assert sp["gesamt"] == 8 and sp["freigegeben"] == 1, sp
        assert {x["art"]: x["n"] for x in sp["arten"]} == {"pruefung": 2, "mangel": 1, "verlust": 2, "ohne_pruefung": 3}
        gruende = {(x["inventarnummer"], x["art"]): x["grund"] for x in sp["liste"]}
        assert gruende[(a["grenze"]["inventory_no"], "ohne_pruefung")] == "Platzhalter Grenze spät"
        assert gruende[(a["unter"]["inventory_no"], "ohne_pruefung")] == "Beschädigung: Platzhalter Riss"
        assert gruende[(a["mangel_a"]["inventory_no"], "mangel")].startswith("Mangel gemeldet am")
        assert "instandsetzen" in gruende[(a["krit"]["inventory_no"], "pruefung")]
        assert (a["verloren"]["inventory_no"], "verlust") in gruende and (a["verlust"]["inventory_no"], "verlust") in gruende
        assert "FREMDPFAD" not in json.dumps(b, ensure_ascii=False)
        # Aussonderungen mit Grundart aus dem Präfix; ohne Haken niemand „durch“.
        au = b["aussonderungen"]
        assert au["gesamt"] == 2 and {x["art"]: x["n"] for x in au["arten"]} == {"pruefung": 0, "lebensdauer": 0, "verlust": 1, "irreparabel": 1, "sonstiges": 0}
        assert all(x["durch"] == "" for x in au["liste"]) and {x["inventarnummer"] for x in au["liste"]} == {a["aus"]["inventory_no"], a["verlust"]["inventory_no"]}
        aus = protokoll_zeile(app, o["pid_aus"])
        assert any(x["protokoll_id"] and x["grund"] == "irreparabel" for x in au["liste"]), au["liste"]
        assert aus["kind"] == "eingang"                 # die Prüfung selbst; die Aussonderung ist die zweite Zeile
        # Mangelmeldungen über mangel.stand – zwei gemeldet, beide offen; keine Meldernamen.
        m = b["maengel"]
        assert (m["gemeldet"], m["offen"], m["freipruefung"], m["aussonderung"], m["offen_stichtag"]) == (2, 2, 0, 0, 2), m
        assert all(x["inventarnummer"] == a["mangel_a"]["inventory_no"] for x in m["offen_liste"])
        assert "fuehrung" not in json.dumps(m) and "wart" not in json.dumps(m)
        # Rückruf: laufend, betroffene Artikel im Zweig (ohne ausgesonderte, ohne das DEMO-Produkt), URL als Text.
        assert len(b["rueckrufe"]) == 1
        rr = b["rueckrufe"][0]
        assert (rr["titel"], rr["laeuft"], rr["betroffen"], rr["offen"], rr["url"]) == ("Platzhalter Rückruf", True, 9, 5,
                                                                                       "https://www.example.org/rueckruf"), rr
        assert {x["inventarnummer"] for x in rr["artikel"] if x["zustand"] == "offen"} == \
            {a[n]["inventory_no"] for n in ("alt", "grenze", "fach_a", "frei", "ug_a")}
        # Ausblick: zwölf Monate ab heute, nur Status nach Datum; Lebensende textil; die Zeile „jetzt“.
        ab = b["ausblick"]
        assert ab["jetzt"] == {"ueberfaellig": 0, "neu": 5, "gesperrt": 4} and len(ab["monate"]) == 12
        monate = {x["monat"]: x for x in ab["monate"]}
        assert monate[o["in_drei"].strftime("%Y-%m")]["faellig"] == 1 and sum(x["faellig"] for x in ab["monate"]) == 1
        assert monate[f"{J}-12"]["lebensende"] == 1 and sum(x["lebensende"] for x in ab["monate"]) == 1
        assert ab["monate"][0]["monat"] == _heute().strftime("%Y-%m")
        assert b["fuss"] == list(dienst.FUSS) and "kein Prüfnachweis" in b["fuss"][0]
        # Vorjahr: nur die Eingangsprüfung, zwei Zugänge, die Sperre von 22:30 UTC – der Bestand bleibt der von heute.
        v = bericht(f, o["gid"], jahr=J - 1)
        assert v["pruefungen"]["gesamt"] == 1 and v["pruefungen"]["abdeckung"]["geprueft"] == 1
        assert v["bewegungen"] == {"zugaenge": 2, "geloescht": 0, "aussonderungen": 0}, v["bewegungen"]
        assert v["sperren"]["gesamt"] == 1 and v["sperren"]["liste"][0]["grund"] == "Platzhalter Grenze früh"
        assert v["bestand"]["zaehlung"] == b["bestand"]["zaehlung"] and not v["durchgaenge"] and v["maengel"]["gemeldet"] == 0
        assert v["rueckrufe"] == []          # heute laufend, aber erst in J angelegt – nicht im Vorjahr (Ablaufprüfung V1)
        # Mit Haken: Prüferliste je (Name, Urkundennummer), Aussonderungen durch getrennt (Materialwart ohne Urkunde).
        bh = bericht(f, o["gid"], pruefer=1)
        assert bh["kopf"]["pruefer_nennen"] is True
        assert bh["pruefer"]["pruefer"] == [{"name": "pruefer", "urkunde": "1012-4711", "n": 5}], bh["pruefer"]
        assert bh["pruefer"]["aussonderungen_durch"] == [{"name": "wart", "n": 2}]
        assert {x["durch"] for x in bh["aussonderungen"]["liste"]} == {"wart"}
        # Die Zweigmenge gilt nach Heimat: Der Bericht über das Fahrzeug nimmt den gesperrten „unter“ und die
        # Aussonderung „aus“ mit, nicht das Lager.
        bf = bericht(f, o["fz"])
        assert bf["kopf"]["artikel"] == 5 and bf["bestand"]["zaehlung"]["gesperrt"] == 2 and bf["bestand"]["zaehlung"]["ausgesondert"] == 1
        assert [x["name"] for x in bf["bestand"]["unterordner"]] == ["Fahrzeug GW (direkt)", "Fach 1"], bf["bestand"]["unterordner"]
        assert bf["kopf"]["gliederung"] == "OG Berichtstadt" and bf["kopf"]["pfad"] == "OG Berichtstadt / Fahrzeug GW"
    print("Zahlen bestanden.")


# --- Rechte, Eingaben, Sichtberechnung -------------------------------------------------------------------------------

def test_rechte_und_eingaben():
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        f, w, ext, J = k["fuehrung"], k["wart"], o["ext"], o["J"]
        gid = o["gid"]
        wege = [f"/api/material/ordner/{gid}/bericht", f"/materialablage/ordner/{gid}/bericht",
                f"/materialablage/ordner/{gid}/bericht-{J}.pdf", f"/materialablage/ordner/{gid}/bericht-{J}-mit-pruefern.pdf",
                f"/materialablage/export/{gid}-pruefungen-{J}.csv", f"/materialablage/export/{gid}-pruefungen-{J}-mit-pruefern.csv"]
        # Führungskraft (lesen) und Materialwart (verwalten): alles 200; die Seite ist der Rahmen mit der Ansicht „bericht“.
        for c in (f, w, k["adm"], k["katalog"]):
            for url in wege:
                r = c.get(url)
                assert r.status_code == 200, (url, r.status_code)
                if url != wege[1]:                      # die Seite ist nur der Rahmen; Daten, PDF und CSV nie zwischenspeichern
                    assert "no-store" in r.headers["Cache-Control"], url
        r = f.get(f"/materialablage/ordner/{gid}/bericht")
        assert 'data-ansicht="bericht"' in r.get_data(as_text=True)
        # Externer Prüfer (nur pruefen): 403 – er sieht den Ordner, bekommt aber keinen Bericht (wie beim Export).
        r = ext.get(wege[0])
        assert r.status_code == 403 and "Prüffreigabe allein" in r.json["error"], r.get_json()
        for url in wege[1:]:
            assert ext.get(url).status_code == 403, url
        # Fremde Gliederung und Systemordner: 404 wie Unbekanntes; ohne Modulzugang 403; ohne Anmeldung 401 bzw. Anmeldung.
        for fid in (o["gfremd"], o["system"]["gesperrt"], 999999):
            assert w.get(f"/api/material/ordner/{fid}/bericht").status_code == 404, fid
            assert w.get(f"/materialablage/ordner/{fid}/bericht-{J}.pdf").status_code == 404, fid
            assert w.get(f"/materialablage/export/{fid}-pruefungen-{J}.csv").status_code == 404, fid
            assert w.get(f"/materialablage/ordner/{fid}/bericht").status_code == 404, fid
        assert k["adm"].get(f"/api/material/ordner/{o['system']['gesperrt']}/bericht").status_code == 404
        assert k["nutzer"].get(wege[0]).status_code == 403 and k["nutzer"].get(wege[2]).status_code == 403
        fremd = app.test_client()
        assert fremd.get(wege[0]).status_code == 401
        r = fremd.get(wege[2])
        assert r.status_code == 302 and "/login" in r.headers["Location"], r.headers.get("Location")
        # Eingaben: jahr als ganze Zahl 1990…2100, pruefer ja/nein.
        for jahr in ("abc", "1800", "2101", "-5", "2026.5"):
            r = f.get(wege[0], query_string={"jahr": jahr})
            assert r.status_code == 400 and "Jahr" in r.json["error"], (jahr, r.get_json())
        assert f.get(wege[0], query_string={"pruefer": "vielleicht"}).status_code == 400
        assert f.get(wege[0], query_string={"jahr": str(J - 1), "pruefer": "nein"}).status_code == 200
        assert f.get(f"/materialablage/ordner/{gid}/bericht-1800.pdf").status_code == 400
        assert f.get(f"/materialablage/export/{gid}-pruefungen-2101.csv").status_code == 400
        # Eine Sichtberechnung je Anfrage (Muster test_material_trennung.test_abfragezahl).
        abfragen = []
        alt = db_mod.get_db

        def mit_zaehler():
            conn = alt()
            conn.set_trace_callback(abfragen.append)
            return conn
        for url in (wege[0], wege[4]):
            del abfragen[:]
            db_mod.get_db = mit_zaehler
            try:
                r = f.get(url)
            finally:
                db_mod.get_db = alt
            assert r.status_code == 200 and abfragen, url
            freigaben = [q for q in abfragen if "mat_folder_grant" in q and "ORDER BY id" in q]
            assert len(freigaben) == 1, (url, freigaben)
            # Die rekursive Ordner-CTE läuft einmal (Zweigmenge), dazu einmal die Ordnerzeilen des Zweigs – nicht je Block.
            assert len([q for q in abfragen if "WITH RECURSIVE baum" in q]) <= 2, [q[:80] for q in abfragen if "RECURSIVE" in q]
        # Ordnername mit Markup: wörtlich im PDF-Text, keine Links aus Daten.
        gx, _ = gliederung(k["adm"], "OG <img src=x onerror=alert(1)>")
        r, seiten = pdf_text(k["adm"], f"/materialablage/ordner/{gx}/bericht-{J}.pdf", os.path.join(tmp, "x.pdf"))
        text = _flach(" ".join(seiten))
        assert "<img src=x onerror=alert(1)>" in text, text[:600]
        cd = r.headers["Content-Disposition"]
        assert cd.startswith("inline") and re.search(rf"Jahresbericht_OG _img src_x onerror_alert_1__{J}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}\.pdf", cd), cd
        # Protokollzeile ohne Namen: Ordner, Jahr, Konto, Haken.
        import logging
        aufgezeichnet = []
        h = logging.Handler()
        h.emit = lambda rec: aufgezeichnet.append(rec.getMessage())
        stufe = app.logger.level
        app.logger.setLevel(logging.INFO)
        app.logger.addHandler(h)
        try:
            assert f.get(wege[3]).status_code == 200
        finally:
            app.logger.removeHandler(h)
            app.logger.setLevel(stufe)
        zeile = [z for z in aufgezeichnet if z.startswith("Bericht Ordner")]
        assert zeile == [f"Bericht Ordner {gid} Jahr {J} Konto {k['fuehrung_id']} pruefer=1 (PDF)"], zeile
    print("Rechte und Eingaben bestanden.")


# --- PDF und CSV -----------------------------------------------------------------------------------------------------

def test_pdf_und_csv():
    from pypdf import PdfReader
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        f, J, gid = k["fuehrung"], o["J"], o["gid"]
        pfad = os.path.join(tmp, "bericht.pdf")
        vorher = set(os.listdir(os.path.join(tmp, "pdf"))) if os.path.isdir(os.path.join(tmp, "pdf")) else set()
        journal_vorher = journal_zahl(app)
        r, seiten = pdf_text(f, f"/materialablage/ordner/{gid}/bericht-{J}.pdf", pfad)
        cd = r.headers["Content-Disposition"]
        # DEMO enthalten: Präfix im Dateinamen, [DEMO] im Kopf, Zahl im Bericht; sonst Titel, Fuß, Blöcke.
        assert cd.startswith("inline") and re.search(rf"DEMO-Jahresbericht_OG Berichtstadt_{J}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}\.pdf", cd), cd
        assert r.headers["Content-Security-Policy"] == CSP_PDF and "no-store" in r.headers["Cache-Control"]
        text = _flach(" ".join(seiten))
        for wert in (f"[DEMO] Jahresbericht OG Berichtstadt {J}", "kein Prüfnachweis", "nicht festgeschrieben",
                     "Bestand zum Stichtag", "Bewegungen im Jahr", "Prüfabdeckung", "Prüfdurchgänge", "Jahresprüfung Fahrzeug",
                     "Sperren und Freiprüfungen", "Aussonderungen im Jahr", "Mangelmeldungen", "Rückrufe", "Platzhalter Rückruf",
                     "https://www.example.org/rueckruf", "Ausblick", "Enthält 1 DEMO-Artikel", "OG Unterstadt Gliederung",
                     "Platzhalter Grenze spät", "nicht auffindbar", "Gliederung intern", "fuehrung",
                     a["demo_a"]["inventory_no"], "Testwerk HMS Demo", "noch nie"):
            assert wert in text, (wert, text[:3000])
        assert all("kein Prüfnachweis" in _flach(s) and "Stand" in _flach(s) for s in seiten)
        # Ohne Haken: kein Personenname und keine Urkundennummer außer dem Ersteller (S2) – weder Prüfer noch
        # Materialwart (Aussonderung, Durchgang) noch Melder; kein Block „Prüfer im Jahr“; kein Pfadtext aus dem Journal.
        assert "1012-4711" not in text and not re.search(r"\bpruefer\b", text) and not re.search(r"\bwart\b", text), text
        assert "Prüfer im Jahr" not in text and "FREMDPFAD" not in text and "Platzhalter Grenze früh" not in text
        assert text.count("fuehrung") == 1, text.count("fuehrung")
        leser = PdfReader(pfad)
        assert leser.metadata.get("/Keywords", "").startswith("strömis-bericht"), leser.metadata
        xmp = leser.trailer["/Root"]["/Metadata"].get_object().get_data()
        assert b'pdfaid:part="3"' in xmp and b'pdfaid:conformance="B"' in xmp, xmp[:600]
        # Nicht festgeschrieben: keine Datei unter DATA_DIR/pdf, keine Journalzeile.
        nachher = set(os.listdir(os.path.join(tmp, "pdf"))) if os.path.isdir(os.path.join(tmp, "pdf")) else set()
        assert nachher == vorher
        assert journal_zahl(app) == journal_vorher
        # PDF/A-3b mit veraPDF (bin/st-vera), wenn es da ist.
        if os.path.exists(ST_VERA):
            lauf = subprocess.run([ST_VERA, pfad], capture_output=True, text=True, timeout=300)
            assert lauf.returncode == 0 and "PASS" in lauf.stdout, (lauf.returncode, lauf.stdout[-800:], lauf.stderr[-800:])
        # Mit Haken: Prüferliste und Aussonderer, eigener Dateiname.
        r, seiten = pdf_text(f, f"/materialablage/ordner/{gid}/bericht-{J}-mit-pruefern.pdf", pfad)
        assert re.search(rf"DEMO-Jahresbericht_OG Berichtstadt_{J}-mit-pruefern_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}\.pdf", r.headers["Content-Disposition"])
        text = _flach(" ".join(seiten))
        assert "Prüfer im Jahr" in text and re.search(r"\bpruefer\b", text) and "1012-4711" in text and "durch wart" in text, text[-2500:]
        # Vorjahr als PDF: ein anderes Jahr im Titel.
        r, seiten = pdf_text(f, f"/materialablage/ordner/{gid}/bericht-{J - 1}.pdf", pfad)
        assert f"OG Berichtstadt {J - 1}" in _flach(seiten[0])
        # CSV: Spalten laut bericht.CSV_SPALTEN, eine Zeile je Prüfung und Aussonderung des Jahres (berichtigte Originale
        # nicht), Formelschutz, kritischer Mangel, Berichtigung von, Prüfer nur mit Haken.
        from app.material.services import bericht as dienst
        r = f.get(f"/materialablage/export/{gid}-pruefungen-{J}.csv")
        assert r.status_code == 200 and r.mimetype == "text/csv", r.status_code
        cd = r.headers["Content-Disposition"]
        assert cd.startswith("attachment") and re.search(rf"Pruefungen_OG Berichtstadt_{J}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}\.csv", cd), cd
        kopf, zeilen = csv_lesen(r.data)
        assert kopf == list(dienst.CSV_SPALTEN), kopf
        assert len(zeilen) == 7 and sum(1 for z in zeilen if z["Art"] == "Aussonderungsprotokoll") == 2, [z["Art"] for z in zeilen]
        assert all(z["Prüfer"] == "" and z["Urkundennummer"] == "" for z in zeilen)
        ber = protokoll_zeile(app, o["ber"])
        orig = protokoll_zeile(app, o["pid_alt"])
        z_ber = [z for z in zeilen if z["Protokoll-ID"] == ber["protocol_id"]]
        assert len(z_ber) == 1 and z_ber[0]["Berichtigung von"] == orig["protocol_id"] and z_ber[0]["Seriennummer"] == "'=1+2", z_ber
        assert z_ber[0]["Bemerkung"] == "Platzhalter nachgetragen" and z_ber[0]["Prüfdurchgang"] == ""
        assert not any(z["Protokoll-ID"] == orig["protocol_id"] for z in zeilen)
        z_krit = [z for z in zeilen if z["Inventarnummer"] == a["krit"]["inventory_no"]][0]
        assert (z_krit["Ergebnis"], z_krit["Mängel"], z_krit["kritischer Mangel"], z_krit["Prüfdurchgang"]) == \
            ("instandsetzen", "1", "ja", "Jahresprüfung Fahrzeug"), z_krit
        assert z_krit["Ordner"] == "OG Berichtstadt / Fahrzeug GW" and z_krit["Gliederung"] == "OG Berichtstadt"
        assert z_krit["Kategorie"] == "PSA gegen Absturz / Karabiner" and z_krit["DEMO"] == "nein"
        z_aus = [z for z in zeilen if z["Art"] == "Aussonderungsprotokoll" and z["Inventarnummer"] == a["verlust"]["inventory_no"]][0]
        assert z_aus["Ergebnis"] == "ausgesondert", z_aus
        assert z_aus["Grund"] == "Verlust" and z_aus["Mängel"] == "" and z_aus["kritischer Mangel"] == "" and z_aus["Bemerkung"] == "Platzhalter weg"
        roh = r.data.decode("utf-8-sig")
        assert "1012-4711" not in roh and "pruefer" not in roh and ";wart;" not in roh
        # Mit Haken: beide Spalten gefüllt.
        r = f.get(f"/materialablage/export/{gid}-pruefungen-{J}-mit-pruefern.csv")
        assert re.search(rf"Pruefungen_OG Berichtstadt_{J}-mit-pruefern_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}\.csv", r.headers["Content-Disposition"])
        kopf, zeilen = csv_lesen(r.data)
        assert {(z["Prüfer"], z["Urkundennummer"]) for z in zeilen} == {("pruefer", "1012-4711"), ("wart", "")}, zeilen
        # Vorjahr: nur die Eingangsprüfung.
        kopf, zeilen = csv_lesen(f.get(f"/materialablage/export/{gid}-pruefungen-{J - 1}.csv").data)
        assert len(zeilen) == 1 and zeilen[0]["Prüfart"] == "Eingangsprüfung" and zeilen[0]["Datum"] == f"15.06.{J - 1}"
    print("PDF und CSV bestanden.")


# --- Kappung -------------------------------------------------------------------------------------------------------

def test_kappung():
    """Listen im PDF auf bericht.KAPPUNG Zeilen gekürzt – Seite (JSON) und CSV nicht."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w, J = k["wart"], _heute().year
        gid, _ = gliederung(w, "OG Viel")
        lager = ordner_neu(w, "Lager", gid)
        from app.material.services import bericht as dienst
        n = dienst.KAPPUNG + 100
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            with conn:
                conn.executemany(
                    "INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, qr_token, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    [(ids["hms"], lager, f"K-{i:04d}", f"M-9{i:06d}", f"tok{i:08d}x", f"{J}-01-02T00:00:00+00:00",
                      f"{J}-01-02T00:00:00+00:00") for i in range(n)])
        finally:
            conn.close()
        b = bericht(w, gid)
        assert len(b["pruefungen"]["nicht_geprueft"]) == n and "gekappt" not in b["pruefungen"]
        pfad = os.path.join(tmp, "viel.pdf")
        r, seiten = pdf_text(w, f"/materialablage/ordner/{gid}/bericht-{J}.pdf", pfad)
        text = _flach(" ".join(seiten))
        assert "und 100 weitere Artikel" in text and f"höchstens {dienst.KAPPUNG} Zeilen je Liste" in text, text[-600:]
        assert text.count("M-9") == dienst.KAPPUNG, text.count("M-9")

        # Gesamtgrenze und Rückrufe (Sicherheitsprüfung B3): 30 laufende Rückrufe über alle 600 Artikel. Je Rückruf
        # höchstens KAPPUNG_RUECKRUF Inventarnummern, alle Listen zusammen höchstens KAPPUNG_GESAMT; die Zahlen bleiben
        # vollständig, die Seite (JSON) kürzt nicht. Laufzeit: früher ≈ 20 s und 63 Seiten bei 23 Rückrufen.
        rueckrufe = 30
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            with conn:
                conn.executemany("INSERT INTO mat_recall (product_id, title, created_at) VALUES (?,?,?)",
                                 [(ids["hms"], f"Platzhalter-Rückruf {i:02d}", f"{J}-01-03T00:00:00+00:00")
                                  for i in range(rueckrufe)])
        finally:
            conn.close()
        b = bericht(w, gid)
        assert len(b["rueckrufe"]) == rueckrufe and all(len(r["artikel"]) == n and r["betroffen"] == n
                                                         for r in b["rueckrufe"]), [r["betroffen"] for r in b["rueckrufe"]]
        import time
        t0 = time.monotonic()
        r, seiten = pdf_text(w, f"/materialablage/ordner/{gid}/bericht-{J}.pdf", pfad)
        dauer = time.monotonic() - t0
        text = _flach(" ".join(seiten))
        assert text.count("M-9") <= dienst.KAPPUNG_GESAMT, text.count("M-9")
        assert text.count("M-9") == dienst.KAPPUNG_GESAMT, text.count("M-9")   # 500 + 20 Rückrufe × 50
        assert text.count("siehe Berichtsseite") >= rueckrufe, text.count("siehe Berichtsseite")
        assert f"{n} Artikel – Liste siehe Berichtsseite" in text, text[-800:]   # Rückrufe nach erschöpfter Grenze
        assert len(seiten) <= 60 and dauer < 60, (len(seiten), dauer)
        print(f"PDF mit {rueckrufe} Rückrufen: {len(seiten)} Seiten, {dauer:.1f} s")
    print("Kappung bestanden.")


def test_rueckruf_ausblick_kategorien():
    """Ablaufprüfung V1, V3, V4: Ein laufender Rückruf, der erst nach dem Jahr angelegt wurde, steht nicht im Bericht des
    Jahres; ein Rückruf zu einem Produkt, das im Zweig nur ausgesonderte Artikel hat, und eine Kategorie nur mit
    Ausgesonderten fehlen; im Ausblick zählt eine überfällige Fälligkeit nur unter „jetzt“, nicht im laufenden Monat."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        w, heute = k["wart"], _heute()
        J = heute.year
        gid, _ = gliederung(w, "OG Ausblick")
        lager = ordner_neu(w, "Lager", gid)
        a = neuer_artikel(w, ids["hms"], lager, serial_no="AB-0001")
        # Rückruf angelegt im laufenden Jahr: steht im Bericht J, nicht im Bericht J-1.
        sql(tmp, "INSERT INTO mat_recall (product_id, title, created_at) VALUES (?,?,?)",
            (ids["hms"], "Platzhalter-Rückruf", f"{J}-02-01T00:00:00+00:00"))
        assert [r["titel"] for r in bericht(w, gid, jahr=J)["rueckrufe"]] == ["Platzhalter-Rückruf"]
        assert bericht(w, gid, jahr=J - 1)["rueckrufe"] == []
        # Überfällig seit dem Monatsersten bzw. seit 40 Tagen: nur „jetzt“, kein Monat zählt sie.
        for tage in (max(1, heute.day - 1), 40):
            faellig = (heute - timedelta(days=tage)).isoformat()
            sql(tmp, "UPDATE mat_item SET next_due_on = ?, last_inspected_on = ? WHERE id = ?",
                (faellig, (heute - timedelta(days=400)).isoformat(), a["id"]))
            aus = bericht(w, gid)["ausblick"]
            assert aus["jetzt"]["ueberfaellig"] == 1 and sum(m["faellig"] for m in aus["monate"]) == 0, (tage, aus)
        # Fällig später im laufenden Monat (oder im nächsten): genau einmal in den Monaten.
        spaeter = heute + timedelta(days=3)
        sql(tmp, "UPDATE mat_item SET next_due_on = ? WHERE id = ?", (spaeter.isoformat(), a["id"]))
        aus = bericht(w, gid)["ausblick"]
        assert sum(m["faellig"] for m in aus["monate"]) == 1 and aus["jetzt"]["ueberfaellig"] == 0, aus
        # Nur Ausgesonderte: Rückruf und Kategorie verschwinden.
        sql(tmp, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (a["id"],))
        b = bericht(w, gid)
        assert b["rueckrufe"] == [], b["rueckrufe"]
        kats = {x["name"]: x for x in b["bestand"]["kategorien"]}
        assert kats == {} and b["bestand"]["zaehlung"]["ausgesondert"] == 1, kats
    print("Rückrufe, Ausblick und Kategorien bestanden.")


def test_oberflaeche():
    """Statisch (Browserprüfung P4-L1): Tab-Titel schon beim ersten Laden; erster Aufruf gescheitert → Meldung mit
    Jahr-Auswahl (nicht nur eine rote Zeile); Sprungmarken mit festen ids; Rückruf-Artikel aufklappbar; Datumsfehler
    unterscheidet Format und ungültigen Tag, das Feld trägt aria-invalid. Fehlerseite unter /materialablage führt zur
    Material-Übersicht."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    anfang = js.index("  async function bericht() {")
    block = js[anfang:js.index("  /* --- Artikel ---", anfang)]
    geruest = block[block.index("    function geruest(b) {"):block.index("    function geruestFehler(e) {")]
    assert "titelSetzen(k);" in geruest
    assert "if (!ziel) { geruestFehler(e); return; }" in block and "if (!ziel) throw e;" not in block
    fehler = block[block.index("    function geruestFehler(e) {"):block.index("    // Daten holen;")]
    assert 'id="be-jahr"' in fehler and 'role="alert">${esc(e.message)}' in fehler and "laden(false)" in fehler
    for sid in ("be-bestand", "be-pruefungen", "be-rueckrufe", "be-ausblick"):
        assert f'id="{sid}"' in block and f'["{sid}", ' in block, sid
    assert '<details class="mat-auf mat-be-rr"><summary>Betroffene Artikel anzeigen' in block
    datum = js[js.index("  function datumWert(feld, name) {"):js.index("  // Beim Tippen die Trenner setzen")]
    assert 'feld.setAttribute("aria-invalid", "true")' in datum and "gibt es nicht." in datum
    assert "bitte als TT.MM.JJJJ angeben" in datum and 'feld.removeAttribute("aria-invalid")' in datum
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        r = k["wart"].get("/materialablage/ordner/999999/bericht")
        text = r.get_data(as_text=True)
        assert r.status_code == 404 and '<a href="/materialablage">Zur Übersicht der Materialablage</a>' in text and "Zur Strömipedia" not in text, text[-500:]
        r = k["wart"].get("/materialablage/gibt-es-nicht")
        assert r.status_code == 404 and "Zur Übersicht der Materialablage" in r.get_data(as_text=True)
    print("Oberfläche bestanden.")


if __name__ == "__main__":
    test_zahlen()
    test_rechte_und_eingaben()
    test_pdf_und_csv()
    test_kappung()
    test_rueckruf_ausblick_kategorien()
    test_oberflaeche()
    print("Alle Berichtstests bestanden.")
