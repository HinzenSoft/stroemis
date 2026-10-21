"""Änderungsanträge an festen Stammdaten (Modul Material, Entscheidungen des Nutzers vom 21.10.2026):
python tests/test_material_antrag.py

Seit der ersten abgeschlossenen Prüfung stehen Seriennummer und Herstelldatum fest (test_material_stammdaten.py). Neu:
  1. Bei Metall lässt sich ein fehlendes Herstelldatum direkt nachtragen (PUT, ohne Antrag) – bei textil und „sonstiges“
     nicht; ändern und entfernen bleibt gesperrt.
  2.+3. Jede andere Änderung – auch STR-Nummer → Herstellernummer – beantragen Materialwart oder Prüfer mit Begründung;
     die Material-Verwaltung (Plattform-Verwaltung eingeschlossen) bestätigt oder lehnt ab (Katalog → Meldungen →
     Änderungsanträge). Bestätigt steht die Änderung sofort am Artikel (Journal mit alt/neu, Antragsteller, Bestätiger,
     Begründung); der Trigger lässt genau diese Änderung einmal zu. Mails an die Material-Verwaltung (Rückfall PV) und
     an den Antragsteller; DEMO, dev-Sperre und ohne Mailserver ins Log.
Dazu Schritt 15 der Migration, Rückrufabgleich mit der neuen Nummer, Löschkonzept und die Oberfläche (statisch).
Echte Mails gehen nie hinaus (antrag.send_mail ist ersetzt). Alle Namen, Nummern und Texte sind Platzhalter."""
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, abschluss, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pruef_formulare, punkte_von, starten, umgebung)
from test_material_erinnerung import umwelt  # noqa: E402
from test_material_trennung import bis_schritt, endversion  # noqa: E402

# Eine KOPIE einer Datenbank auf Stand 7 für den Pfad 7 → 15 – nur, wenn angegeben; die Quelle bleibt unberührt.
KOPIE_STAND_7 = os.environ.get("MATERIAL_KOPIE_STAND_7") or ""
FEST = ("Seriennummer und Herstelldatum stehen seit der ersten Prüfung fest – sie sind Teil des Prüfnachweises. Eine "
        "Änderung beantragst du mit Begründung bei der Material-Verwaltung.")
NUR_MV = "Das macht die Material-Verwaltung (Stufe „Verwaltung“ im Modul Material)."
ANTRAG_FEST = "Ein Änderungsantrag lässt sich nur einmal entscheiden"
TRIGGER_NEU = {"mat_item_stammdaten_fest", "mat_item_antrag_angewendet", "mat_item_change_inhalt",
               "mat_item_change_antragsteller", "mat_item_change_entscheider", "mat_item_change_entschieden",
               "mat_item_change_angewendet", "mat_item_change_loeschen", "mat_item_change_ersetzen", "mat_item_change_neu"}


# --- Helfer ---------------------------------------------------------------------------------------------------------

class T:
    pass


def pruefen(c, iid, gurt=False):
    """Eine Prüfung „einsatzbereit“ – beim Gurt mit dem Messwert, den das spezifische Formular verlangt."""
    r = starten(c, iid)
    assert r.status_code in (200, 201), r.get_json()
    pr = r.json["pruefung"]
    if gurt:
        url = f"/api/material/pruefungen/{pr['id']}/punkte/{punkte_von(pr)['Testpunkt Messwert']}"
        assert c.put(url, json={"wert": "1"}).status_code == 200
    r = abschluss(c, pr["id"], ergebnis="einsatzbereit")
    assert r.status_code == 200, r.get_json()


def sql(app, befehl, args=()):
    with app.app_context():
        from app import db
        return db.execute(befehl, args)


def zeilen(app, abfrage, args=()):
    with app.app_context():
        from app import db
        return [dict(r) for r in db.query(abfrage, args)]


def item(app, iid):
    return zeilen(app, "SELECT * FROM mat_item WHERE id = ?", (iid,))[0]


def antraege(app, iid):
    return zeilen(app, "SELECT * FROM mat_item_change WHERE item_id = ? ORDER BY id", (iid,))


def journal(app, iid, aktion):
    import json
    out = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = ? ORDER BY id",
                 (iid, aktion))
    for j in out:
        j["vorher"] = json.loads(j["before_json"]) if j["before_json"] else None
        j["nachher"] = json.loads(j["after_json"]) if j["after_json"] else None
    return out


def beantragen(c, iid, **d):
    d.setdefault("begruendung", "Platzhalter: Etikett beim Prüfen anders abgelesen")
    return c.post(f"/api/material/artikel/{iid}/antrag", headers=H, json=d)


def bestaetigen(c, aid, **d):
    return c.post(f"/api/material/antraege/{aid}/bestaetigen", headers=H, json=d)


def ablehnen(c, aid, **d):
    return c.post(f"/api/material/antraege/{aid}/ablehnen", headers=H, json=d)


def lesen(c, iid):
    r = c.get(f"/api/material/artikel/{iid}")
    assert r.status_code == 200, r.get_json()
    return r.json["artikel"]


@contextmanager
def post():
    """Mails direkt statt im Hintergrund und nur in eine Liste; ein Mailserver gilt als eingerichtet."""
    from app.material.services import antrag
    liste = []
    alt = (antrag.HINTERGRUND, antrag.send_mail, antrag.MAILSERVER)
    antrag.HINTERGRUND = lambda f, *a: f(*a)
    antrag.send_mail = lambda an, betreff, inhalt: liste.append((an, betreff, inhalt)) or True
    antrag.MAILSERVER = lambda: True
    try:
        yield liste
    finally:
        antrag.HINTERGRUND, antrag.send_mail, antrag.MAILSERVER = alt


@contextmanager
def logzeilen(app):
    liste = []

    class Sammler(logging.Handler):
        def emit(self, rec):
            liste.append(rec.getMessage())
    h = Sammler(level=logging.WARNING)
    app.logger.addHandler(h)
    try:
        yield liste
    finally:
        app.logger.removeHandler(h)


def aufbau(tmp):
    """Gliederung A mit Lager: Karabiner k1 (SN AN-100, 03/2024), Karabiner k2 (STR-Nummer, ohne Herstelldatum), Gurt g1
    (textil, 01/2024), Sonderteil s1 („sonstiges“, ohne Herstelldatum) – alle geprüft –, Karabiner neu1 (ungeprüft).
    Dazu eine fremde Gliederung B mit Karabiner fb (SN AN-B1). Materialwart, Prüfer, Führungskraft, Material-Verwaltung
    (katalog), Plattform-Verwaltung (adm), Konto ohne Stufe (nutzer)."""
    t = T()
    t.app, t.k = umgebung(tmp)
    t.ids = katalog_grund(t.k["adm"])
    pruef_formulare(t.k["katalog"], t.ids)
    r = t.k["katalog"].post("/api/material/produkte", json={
        "category_id": t.ids["karabiner"], "manufacturer": "Testwerk", "model": "Sonderteil Gamma", "article_no": "SG-1",
        "material_kind": "sonstiges", "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    t.sonst = r.json["produkt"]["id"]
    t.w, t.p, t.f, t.mv, t.adm = t.k["wart"], t.k["pruefer"], t.k["fuehrung"], t.k["katalog"], t.k["adm"]
    t.gid, t.system = gliederung(t.w)
    t.lager = t.w.post("/api/material/ordner", json={"name": "Lager", "kind": "standort", "parent_id": t.gid}).json["ordner"]["id"]
    t.k1 = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-100", manufactured_on="2024-03", purchased_on="2024-05")["id"]
    t.k2 = neuer_artikel(t.w, t.ids["hms"], t.lager)["id"]
    t.g1 = neuer_artikel(t.w, t.ids["gurt"], t.lager, serial_no="AN-G1", manufactured_on="2024-01")["id"]
    t.s1 = neuer_artikel(t.w, t.sonst, t.lager, serial_no="AN-S1")["id"]
    t.neu1 = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-NEU")["id"]
    for iid in (t.k1, t.k2, t.s1):
        pruefen(t.p, iid)
    pruefen(t.p, t.g1, gurt=True)
    t.str_nr = item(t.app, t.k2)["serial_no"]
    assert t.str_nr.startswith("STR-")
    t.gid_b, _ = gliederung(t.adm, "OG Nachbarort", standard=False)
    lager_b = t.adm.post("/api/material/ordner", json={"name": "Lager B", "kind": "standort",
                                                       "parent_id": t.gid_b}).json["ordner"]["id"]
    t.fb = neuer_artikel(t.adm, t.ids["hms"], lager_b, serial_no="AN-B1", manufactured_on="2024-01")["id"]
    return t


# --- 1. Herstelldatum nachtragen (Metall direkt) ---------------------------------------------------------------------

def test_nachtragen():
    """Metall, fest, ohne Herstelldatum: PUT trägt es nach (200, Journal „geändert“); danach ändern oder entfernen 409.
    „sonstiges“ ohne Herstelldatum und textil (leer gemacht vor der Prüfung): 409. Seriennummer bleibt fest, auch im
    selben PUT. Ein Antrag fürs Nachtragen bei Metall: 409 mit Hinweis."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a = lesen(t.w, t.k2)
        assert a["stammdaten_fest"] and a["herstellung_nachtragbar"] and a["darf_antrag"], a
        assert lesen(t.w, t.k1)["herstellung_nachtragbar"] is False and lesen(t.w, t.s1)["herstellung_nachtragbar"] is False
        r = beantragen(t.w, t.k2, manufactured_on="2023-11")
        assert r.status_code == 409 and "direkt" in r.json["error"], r.get_json()
        # Zusammen mit einer anderen Seriennummer: 409, nichts geändert.
        r = t.w.put(f"/api/material/artikel/{t.k2}", json={"serial_no": "AN-200", "manufactured_on": "2023-11"})
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        assert item(t.app, t.k2)["manufactured_on"] is None
        # Nachtragen mit dem Stand aus dem Dialog (der schickt keine Seriennummer).
        r = t.w.put(f"/api/material/artikel/{t.k2}", json={"stand": a["stand"], "manufactured_on": "2023-11",
                                                           "notes": "nachgetragen"})
        assert r.status_code == 200 and r.json["artikel"]["manufactured_on"] == "2023-11", r.get_json()
        assert r.json["artikel"]["herstellung_nachtragbar"] is False
        j = journal(t.app, t.k2, "geaendert")[-1]
        assert j["vorher"]["manufactured_on"] is None and j["nachher"]["manufactured_on"] == "2023-11", j
        for wert in ("2023-10", "2023-11-05", "", None):
            r = t.w.put(f"/api/material/artikel/{t.k2}", json={"manufactured_on": wert})
            assert r.status_code == 409 and r.json["error"] == FEST, (wert, r.get_json())
        assert item(t.app, t.k2)["manufactured_on"] == "2023-11"
        # „sonstiges“: kein direktes Nachtragen – aber per Antrag.
        r = t.w.put(f"/api/material/artikel/{t.s1}", json={"manufactured_on": "2023-11"})
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        assert beantragen(t.w, t.s1, manufactured_on="2023-11").status_code == 201
        # textil: vor der Prüfung ohne Herstelldatum (Altbestand), danach kein direktes Nachtragen.
        g2 = neuer_artikel(t.w, t.ids["gurt"], t.lager, serial_no="AN-G2", manufactured_on="2024-02")["id"]
        sql(t.app, "UPDATE mat_item SET manufactured_on = NULL, retire_by = NULL WHERE id = ?", (g2,))
        pruefen(t.p, g2, gurt=True)
        r = t.w.put(f"/api/material/artikel/{g2}", json={"manufactured_on": "2024-02"})
        assert r.status_code == 409, r.get_json()
        assert lesen(t.w, g2)["herstellung_nachtragbar"] is False
        # Nachtragen ist Sache des Materialwarts: Prüfer und Führungskraft dürfen nicht bearbeiten.
        assert t.p.put(f"/api/material/artikel/{t.k1}", json={"notes": "x"}).status_code == 403
    print("Nachtragen bestanden.")


# --- 2. Rechte ---------------------------------------------------------------------------------------------------------

def test_rechte():
    """Beantragen: Materialwart und Prüfer (201), Führungskraft (nur lesen) 403, ohne Stufe 403, fremde Gliederung 404 wie
    unbekannt, ungeprüft und ausgesondert 409. Liste: Material-Verwaltung alle, Materialwart/Prüfer die eigenen,
    Führungskraft leer, ohne Stufe 403. Entscheiden nur Material- und Plattform-Verwaltung (sonst 403), unbekannt 404."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.w, t.k1, serial_no="AN-101")
        assert r.status_code == 201 and len(r.json["antraege"]) == 1, r.get_json()
        a_w = r.json["antraege"][0]
        assert (a_w["feld"], a_w["alt"], a_w["neu"], a_w["status"], a_w["eigen"]) == ("serial_no", "AN-100", "AN-101",
                                                                                      "offen", True), a_w
        assert r.json["artikel"]["antraege"][0]["id"] == a_w["id"]
        r = beantragen(t.p, t.g1, manufactured_on="2023-12")
        assert r.status_code == 201, r.get_json()
        a_p = r.json["antraege"][0]["id"]
        r = beantragen(t.f, t.k1, manufactured_on="2024-02")
        assert r.status_code == 403, r.get_json()
        r = beantragen(t.k["nutzer"], t.k1, manufactured_on="2024-02")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        fremd, unbekannt = beantragen(t.w, t.fb, serial_no="AN-B2"), beantragen(t.w, 999999, serial_no="AN-B2")
        assert fremd.status_code == unbekannt.status_code == 404 and fremd.get_json() == unbekannt.get_json()
        assert t.app.test_client().post(f"/api/material/artikel/{t.k1}/antrag", headers=H, json={}).status_code == 401
        r = beantragen(t.w, t.neu1, serial_no="AN-NEU2")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()
        assert lesen(t.w, t.neu1)["darf_antrag"] is False
        # Ausgesondert: kein Antrag mehr.
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (t.s1,))
        r = beantragen(t.w, t.s1, serial_no="AN-S2")
        assert r.status_code == 409 and "ausgesondert" in r.json["error"], r.get_json()
        assert lesen(t.w, t.s1)["darf_antrag"] is False
        # Liste und Zahlen.
        d = t.mv.get("/api/material/antraege").json
        assert d["alle"] and d["bearbeiten"] and d["filter"] == "offen" and d["offen"] == 2, d
        assert {x["id"] for x in d["antraege"]} == {a_w["id"], a_p}
        assert d["antraege"][0]["artikel"]["inventory_no"] and d["antraege"][0]["artikel"]["gliederung"] == "OG Musterstadt"
        d = t.w.get("/api/material/antraege").json
        assert not d["alle"] and not d["bearbeiten"] and [x["id"] for x in d["antraege"]] == [a_w["id"]], d
        assert d["filter"] == "alle" and d["meldungen_offen"] is None
        assert [x["id"] for x in t.p.get("/api/material/antraege").json["antraege"]] == [a_p]
        assert t.f.get("/api/material/antraege").json["antraege"] == []
        assert t.k["nutzer"].get("/api/material/antraege").status_code == 403
        assert t.adm.get("/api/material/antraege").json["offen"] == 2
        # Entscheiden: nur Material- und Plattform-Verwaltung.
        for c in (t.w, t.p, t.f):
            for f in (bestaetigen, ablehnen):
                r = f(c, a_w["id"], antwort="x")
                assert r.status_code == 403 and r.json["error"] == NUR_MV, r.get_json()
        assert bestaetigen(t.k["nutzer"], a_w["id"]).status_code == 403
        assert bestaetigen(t.mv, 999999).status_code == 404 and ablehnen(t.mv, 999999, antwort="x").status_code == 404
        assert bestaetigen(t.mv, a_w["id"]).status_code == 200
        assert ablehnen(t.adm, a_p, antwort="Platzhalter: Datum stimmt").status_code == 200
        assert item(t.app, t.k1)["serial_no"] == "AN-101" and item(t.app, t.g1)["manufactured_on"] == "2024-01"
        # Erledigte: „erledigt“ zeigt beide, „offen“ keinen mehr.
        d = t.mv.get("/api/material/antraege?status=erledigt").json
        assert {x["status"] for x in d["antraege"]} == {"bestaetigt", "abgelehnt"} and d["offen"] == 0, d
        assert t.mv.get("/api/material/antraege").json["antraege"] == []
    print("Rechte bestanden.")


# --- 3. Prüfen beim Antrag ---------------------------------------------------------------------------------------------

def test_eingaben():
    """Begründung Pflicht, etwas muss beantragt sein; Seriennummer nicht dieselbe, nicht STR-…, je Produkt eindeutig
    (sichtbar: 409 mit Inventarnummer; fremd: 409 ohne, protokolliert); Herstelldatum Format, nicht in der Zukunft,
    nicht nach dem Kauf, bei textil nicht entfernen; ein offener Antrag je Feld (409), das andere Feld geht; beide Felder
    in einem Antrag: zwei Zeilen, zwei Journaleinträge."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        k1 = item(t.app, t.k1)
        faelle = [
            ({"serial_no": "AN-101", "begruendung": ""}, 400, "Begründung"),
            ({"serial_no": "AN-101", "begruendung": "   "}, 400, "Begründung"),
            ({}, 400, "Bitte eine neue Seriennummer"),
            ({"serial_no": "  "}, 400, "Bitte eine neue Seriennummer"),
            ({"serial_no": "AN-100"}, 400, "dieselbe"),
            ({"serial_no": "STR-000123"}, 400, "STR-"),
            ({"serial_no": "x" * 81}, 400, "zu lang"),
            ({"serial_no": "AN-NEU"}, 409, k1["inventory_no"][:2]),               # gibt es bei neu1 (sichtbar)
            ({"manufactured_on": "2024-03"}, 400, "dasselbe"),
            ({"manufactured_on": "03/2024"}, 400, "Monat (JJJJ-MM)"),
            ({"manufactured_on": "2099-01"}, 400, "Zukunft"),
            ({"manufactured_on": "2024-06"}, 400, "Kaufdatum"),
            ({"manufactured_on": "2024-02", "herstellung_entfernen": True}, 400, "nicht beides"),
            ({"serial_no": "AN-101", "begruendung": "x" * 1001}, 400, "zu lang"),
        ]
        for d, code, text in faelle:
            r = beantragen(t.w, t.k1, **d)
            assert r.status_code == code and text in r.json["error"], (d, r.status_code, r.get_json())
        r = beantragen(t.w, t.k1, serial_no="AN-NEU")
        assert "M-" in r.json["error"], r.get_json()
        # Fremde Dublette: dieselbe Nummer bei demselben Produkt in B – 409 ohne Inventarnummer, protokolliert.
        r = beantragen(t.w, t.k1, serial_no="an-b1")
        assert r.status_code == 409 and "Bereich, den du nicht siehst" in r.json["error"], r.get_json()
        assert zeilen(t.app, "SELECT art FROM mat_global_search ORDER BY id DESC LIMIT 1")[0]["art"] == "dublette"
        r = beantragen(t.w, t.g1, herstellung_entfernen=True)
        assert r.status_code == 400 and "textilem Material" in r.json["error"], r.get_json()
        assert antraege(t.app, t.k1) == [] and antraege(t.app, t.g1) == []
        # Beide Felder auf einmal: zwei Zeilen mit derselben Begründung, zwei Journaleinträge.
        r = beantragen(t.w, t.k1, serial_no="AN-101", manufactured_on="2024-02", begruendung="Platzhalter beide")
        assert r.status_code == 201 and [x["feld"] for x in r.json["antraege"]] == ["serial_no", "manufactured_on"]
        z = antraege(t.app, t.k1)
        assert [(x["field"], x["old_value"], x["new_value"], x["reason"], x["created_by_name"]) for x in z] == [
            ("serial_no", "AN-100", "AN-101", "Platzhalter beide", "wart"),
            ("manufactured_on", "2024-03", "2024-02", "Platzhalter beide", "wart")], z
        j = journal(t.app, t.k1, "antrag_gestellt")
        assert [(x["vorher"], x["nachher"]["antrag"]) for x in j] == [({"serial_no": "AN-100"}, z[0]["id"]),
                                                                       ({"manufactured_on": "2024-03"}, z[1]["id"])], j
        assert j[0]["user_name"] == "wart" and j[0]["nachher"]["begruendung"] == "Platzhalter beide"
        # Je Feld ein offener Antrag – auch für einen anderen Antragsteller.
        r = beantragen(t.p, t.k1, serial_no="AN-102")
        assert r.status_code == 409 and "läuft schon ein Antrag" in r.json["error"], r.get_json()
        r = beantragen(t.p, t.k1, manufactured_on="2024-01")
        assert r.status_code == 409, r.get_json()
        # Entfernen bei Metall: als Antrag möglich (Zeile mit neuem Wert NULL).
        r = beantragen(t.w, t.fb, herstellung_entfernen=True)
        assert r.status_code == 404
        r = beantragen(t.adm, t.fb, herstellung_entfernen=True)
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()
        assert item(t.app, t.k1)["serial_no"] == "AN-100"
    print("Eingaben bestanden.")


# --- 4. Bestätigen und ablehnen ----------------------------------------------------------------------------------------

def test_entscheiden():
    """STR → Herstellernummer bestätigt: Nummer am Artikel, serial_generated 0, applied_at, Journal mit alt/neu,
    Antragsteller, Bestätiger, Begründung; zweites Entscheiden 409. Textil: Lebensende rechnet neu. Eindeutigkeit beim
    Bestätigen (anderer Antrag hat die Nummer inzwischen bekommen) 409; Stand geändert 409; ausgesondert nur ablehnen.
    Ablehnen nur mit Begründung, Artikel unverändert, Journal. Danach ist ein neuer Antrag fürs Feld möglich. Die
    Material-Verwaltung bestätigt ihren eigenen Antrag."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.w, t.k2, serial_no="HN-777", begruendung="Platzhalter: Herstellernummer gefunden")
        aid = r.json["antraege"][0]["id"]
        r = bestaetigen(t.mv, aid, antwort="Platzhalter Anmerkung")
        assert r.status_code == 200 and r.json["antrag"]["status"] == "bestaetigt", r.get_json()
        z = item(t.app, t.k2)
        assert (z["serial_no"], z["serial_generated"]) == ("HN-777", 0), z
        a = antraege(t.app, t.k2)[0]
        assert a["applied_at"] and a["resolved_by_name"] == "katalog" and a["answer"] == "Platzhalter Anmerkung", a
        j = journal(t.app, t.k2, "antrag_bestaetigt")
        assert len(j) == 1 and j[0]["user_name"] == "katalog", j
        assert j[0]["vorher"] == {"serial_no": t.str_nr, "serial_generated": True}, j
        assert j[0]["nachher"] == {"serial_no": "HN-777", "serial_generated": False, "antrag": aid, "beantragt_von": "wart",
                                   "begruendung": "Platzhalter: Herstellernummer gefunden",
                                   "anmerkung": "Platzhalter Anmerkung"}, j
        for f in (bestaetigen, ablehnen):
            r = f(t.mv, aid, antwort="noch einmal")
            assert r.status_code == 409 and "schon entschieden" in r.json["error"], r.get_json()
        a = lesen(t.w, t.k2)
        assert a["antraege"] == [] and a["serial_no"] == "HN-777"
        assert any(e["action"] == "antrag_bestaetigt" for e in a["journal"])
        # Festgeschriebene Protokolle bleiben, wie sie sind: Prüfsumme der Datei unverändert und gültig.
        x = zeilen(t.app, "SELECT id FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL", (t.k2,))[0]
        assert t.w.get(f"/material/pruefung/{x['id']}/pdf").status_code == 200

        # Textil: neues Herstelldatum → Lebensende neu (10 Jahre).
        aid = beantragen(t.p, t.g1, manufactured_on="2023-07").json["antraege"][0]["id"]
        assert item(t.app, t.g1)["retire_by"] == "2034-01-01"
        assert bestaetigen(t.mv, aid).status_code == 200
        z = item(t.app, t.g1)
        assert (z["manufactured_on"], z["retire_by"]) == ("2023-07", "2033-07-01"), z
        j = journal(t.app, t.g1, "antrag_bestaetigt")[0]
        assert j["vorher"] == {"manufactured_on": "2024-01", "retire_by": "2034-01-01"}, j
        assert "anmerkung" not in j["nachher"] and j["nachher"]["beantragt_von"] == "pruefer"

        # Eindeutigkeit beim Bestätigen: zwei Anträge auf dieselbe neue Nummer – der zweite scheitert erst jetzt.
        a1 = beantragen(t.w, t.k1, serial_no="HN-900").json["antraege"][0]["id"]
        k3 = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-300")["id"]
        pruefen(t.p, k3)
        a2 = beantragen(t.w, k3, serial_no="hn-900").json["antraege"][0]["id"]
        assert bestaetigen(t.mv, a1).status_code == 200
        r = bestaetigen(t.mv, a2)
        assert r.status_code == 409 and "gibt es bei diesem Produkt schon" in r.json["error"], r.get_json()
        assert antraege(t.app, k3)[0]["status"] == "offen" and item(t.app, k3)["serial_no"] == "AN-300"
        d = {x["id"]: x for x in t.mv.get("/api/material/antraege").json["antraege"]}
        assert d[a2]["passt"] is True
        # Ablehnen: Begründung Pflicht, Artikel unverändert, Journal.
        assert ablehnen(t.mv, a2).status_code == 400 and ablehnen(t.mv, a2, antwort=" ").status_code == 400
        r = ablehnen(t.mv, a2, antwort="Platzhalter: Nummer vergeben")
        assert r.status_code == 200 and r.json["antrag"]["status"] == "abgelehnt", r.get_json()
        assert item(t.app, k3)["serial_no"] == "AN-300" and antraege(t.app, k3)[0]["applied_at"] is None
        j = journal(t.app, k3, "antrag_abgelehnt")
        assert j[0]["nachher"] == {"antrag": a2, "feld": "Seriennummer", "ablehnung": "Platzhalter: Nummer vergeben"}, j
        # Danach ist ein neuer Antrag fürs selbe Feld möglich.
        assert beantragen(t.w, k3, serial_no="HN-901").status_code == 201

        # Stand geändert (an Dienst und Trigger vorbei nachgestellt): bestätigen 409, ablehnen geht.
        a3 = beantragen(t.w, t.s1, serial_no="AN-S9").json["antraege"][0]["id"]
        _ohne_trigger(t.app, "UPDATE mat_item SET serial_no = 'AN-S8' WHERE id = ?", (t.s1,))
        assert t.mv.get("/api/material/antraege").json["antraege"][-1]["passt"] is False
        r = bestaetigen(t.mv, a3)
        assert r.status_code == 409 and "nicht mehr den Wert" in r.json["error"], r.get_json()
        assert ablehnen(t.mv, a3, antwort="Platzhalter: Stand geändert").status_code == 200
        # Ausgesondert nach dem Antrag: nur noch ablehnen.
        a4 = beantragen(t.w, t.s1, manufactured_on="2022-05").json["antraege"][0]["id"]
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (t.s1,))
        r = bestaetigen(t.mv, a4)
        assert r.status_code == 409 and "nur noch ablehnen" in r.json["error"], r.get_json()
        assert ablehnen(t.mv, a4, antwort="Platzhalter: ausgesondert").status_code == 200

        # Die Material-Verwaltung beantragt (sie verwaltet alles) und bestätigt selbst – mit Journal.
        r = beantragen(t.mv, t.fb, serial_no="AN-B9")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"]
        aid = beantragen(t.mv, t.k1, manufactured_on="2024-01").json["antraege"][0]["id"]
        lst = t.mv.get("/api/material/antraege").json["antraege"]
        assert [x["eigen"] for x in lst if x["id"] == aid] == [True]
        assert bestaetigen(t.mv, aid).status_code == 200
        j = journal(t.app, t.k1, "antrag_bestaetigt")[-1]
        assert j["user_name"] == "katalog" and j["nachher"]["beantragt_von"] == "katalog", j
        assert item(t.app, t.k1)["manufactured_on"] == "2024-01"
    print("Entscheiden bestanden.")


def _ohne_trigger(app, befehl, args):
    """Einen Wert an Dienst und Trigger vorbei ändern (nur für Tests): Trigger weg, ändern, Trigger wieder an."""
    from app.material import models
    pfad = os.path.join(app.config["DATA_DIR"], "stroemis.db")
    conn = sqlite3.connect(pfad)
    try:
        conn.execute("DROP TRIGGER mat_item_stammdaten_fest")
        conn.execute(befehl, args)
        conn.execute(models.TRIGGER_15_ARTIKEL[0])
        conn.commit()
    finally:
        conn.close()


# --- 5. Trigger ----------------------------------------------------------------------------------------------------------

def test_trigger():
    """An der Schnittstelle vorbei: Eine Änderung nach der ersten Prüfung geht nur mit einem bestätigten, nicht
    angewendeten Antrag mit genau diesem alten und neuen Wert – und nur einmal; Nachtragen bei Metall geht, bei
    „sonstiges“ nicht. Anträge: nur offen einfügen, Inhalt fest, einmal entscheiden, nicht löschen, nicht ersetzen,
    applied_at einmal und nur nach der Bestätigung, Kontokennung nur auf NULL; höchstens ein offener je Feld."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        wart = t.k["wart_id"]

        def geht_nicht(befehl, args=(), text="seit der ersten Prüfung fest"):
            try:
                conn.execute(befehl, args)
            except sqlite3.IntegrityError as e:
                assert text in str(e), (befehl, e)
                return
            raise AssertionError(befehl)

        def neu(iid, feld, alt, wert):
            cur = conn.execute("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, "
                               "created_by_name, created_at) VALUES (?,?,?,?,'Platzhalter',?,'wart','2026-10-21T08:00:00+00:00')",
                               (iid, feld, alt, wert, wart))
            return cur.lastrowid

        def entscheiden(aid, status="bestaetigt", antwort=""):
            conn.execute("UPDATE mat_item_change SET status = ?, answer = ?, resolved_by = ?, resolved_by_name = 'katalog', "
                         "resolved_at = '2026-10-21T09:00:00+00:00' WHERE id = ?", (status, antwort, t.k["katalog_id"], aid))

        try:
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-T1' WHERE id = ?", (t.k1,))
            # Offener Antrag reicht nicht.
            aid = neu(t.k1, "serial_no", "AN-100", "AN-T1")
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-T1' WHERE id = ?", (t.k1,))
            # Nur offen einfügbar, nur einer je Feld.
            geht_nicht("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, status, created_by_name, "
                       "created_at, resolved_at, resolved_by_name) VALUES (?, 'manufactured_on', NULL, '2024-01', 'x', "
                       "'bestaetigt', 'x', 'x', 'x', 'x')", (t.k1,), ANTRAG_FEST)
            try:
                neu(t.k1, "serial_no", "AN-100", "AN-T2")
                raise AssertionError("zweiter offener Antrag")
            except sqlite3.IntegrityError as e:
                assert "UNIQUE" in str(e), e
            entscheiden(aid)
            # Bestätigt: nur genau dieser Wert …
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-T9' WHERE id = ?", (t.k1,))
            geht_nicht("UPDATE mat_item SET serial_no = 'an-t1' WHERE id = ?", (t.k1,))
            # … und nicht zusammen mit einer ungedeckten Änderung des anderen Feldes.
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-T1', manufactured_on = '2024-01' WHERE id = ?", (t.k1,))
            conn.execute("UPDATE mat_item SET serial_no = 'AN-T1' WHERE id = ?", (t.k1,))
            assert conn.execute("SELECT applied_at FROM mat_item_change WHERE id = ?", (aid,)).fetchone()[0]
            # Verbraucht: zurück geht es nicht, noch einmal anwenden auch nicht.
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-100' WHERE id = ?", (t.k1,))
            geht_nicht("UPDATE mat_item_change SET applied_at = NULL WHERE id = ?", (aid,), ANTRAG_FEST)
            geht_nicht("UPDATE mat_item_change SET applied_at = 'x' WHERE id = ?", (aid,), ANTRAG_FEST)
            # Falscher alter Wert deckt nichts.
            aid2 = neu(t.k1, "manufactured_on", "2024-02", "2024-01")
            entscheiden(aid2)
            geht_nicht("UPDATE mat_item SET manufactured_on = '2024-01' WHERE id = ?", (t.k1,))
            # applied_at nicht in derselben Anweisung wie die Entscheidung, nicht an einem offenen Antrag.
            aid3 = neu(t.s1, "serial_no", "AN-S1", "AN-S5")
            geht_nicht("UPDATE mat_item_change SET applied_at = 'x' WHERE id = ?", (aid3,), ANTRAG_FEST)
            geht_nicht("UPDATE mat_item_change SET status = 'bestaetigt', resolved_at = 'x', applied_at = 'x' WHERE id = ?",
                       (aid3,), ANTRAG_FEST)
            # Inhalt fest, einmal entscheiden, nicht löschen, nicht ersetzen.
            for befehl in ("UPDATE mat_item_change SET reason = 'anders' WHERE id = ?",
                           "UPDATE mat_item_change SET new_value = 'AN-S6' WHERE id = ?",
                           "UPDATE mat_item_change SET created_by_name = 'jemand' WHERE id = ?",
                           "DELETE FROM mat_item_change WHERE id = ?"):
                geht_nicht(befehl, (aid3,), ANTRAG_FEST)
            for befehl in ("UPDATE mat_item_change SET status = 'abgelehnt', answer = 'x' WHERE id = ?",
                           "UPDATE mat_item_change SET answer = 'anders' WHERE id = ?",
                           "UPDATE mat_item_change SET resolved_by_name = 'jemand' WHERE id = ?",
                           f"UPDATE mat_item_change SET resolved_by = {wart} WHERE id = ?",
                           "DELETE FROM mat_item_change WHERE id = ?"):
                geht_nicht(befehl, (aid,), ANTRAG_FEST)
            geht_nicht("INSERT OR REPLACE INTO mat_item_change (id, item_id, field, old_value, new_value, reason, "
                       "created_by_name, created_at) VALUES (?, ?, 'serial_no', 'AN-T1', 'AN-T7', 'x', 'x', 'x')",
                       (aid, t.k1), ANTRAG_FEST)
            # Kontokennungen nur auf NULL.
            geht_nicht("UPDATE mat_item_change SET created_by = ? WHERE id = ?", (t.k["pruefer_id"], aid3), ANTRAG_FEST)
            conn.execute("UPDATE mat_item_change SET created_by = NULL, resolved_by = NULL WHERE id = ?", (aid,))
            # Ablehnen braucht eine Begründung (CHECK).
            try:
                entscheiden(aid3, "abgelehnt", "")
                raise AssertionError("abgelehnt ohne Begründung")
            except sqlite3.IntegrityError as e:
                assert "CHECK" in str(e), e
            # Nachtragen: Metall ja (einmal), „sonstiges“ nein; Entfernen bei Metall nur mit Antrag.
            conn.execute("UPDATE mat_item SET manufactured_on = '2023-10' WHERE id = ?", (t.k2,))
            geht_nicht("UPDATE mat_item SET manufactured_on = '2023-09' WHERE id = ?", (t.k2,))
            geht_nicht("UPDATE mat_item SET manufactured_on = NULL WHERE id = ?", (t.k2,))
            geht_nicht("UPDATE mat_item SET manufactured_on = '2023-10' WHERE id = ?", (t.s1,))
            aid4 = neu(t.k2, "manufactured_on", "2023-10", None)
            entscheiden(aid4)
            conn.execute("UPDATE mat_item SET manufactured_on = NULL WHERE id = ?", (t.k2,))
            # Ungeprüft: frei wie bisher.
            conn.execute("UPDATE mat_item SET serial_no = 'AN-NEU9', manufactured_on = NULL WHERE id = ?", (t.neu1,))
            conn.commit()
        finally:
            conn.close()
        assert (item(t.app, t.k1)["serial_no"], item(t.app, t.k2)["manufactured_on"]) == ("AN-T1", None)
    print("Trigger bestanden.")


# --- 6. Mails ------------------------------------------------------------------------------------------------------------

def test_mails():
    """Neuer Antrag: an die Material-Verwaltung (nicht an den Antragsteller), mit Inventarnummer, alt → neu,
    Begründung, Link; ohne Material-Verwaltung an die Plattform-Verwaltung. Entscheidung: an den Antragsteller (bestätigt
    mit Anmerkung, abgelehnt mit Begründung), nicht bei eigener Entscheidung. Umgebungssperre, ohne Mailserver, DEMO:
    nichts verschickt, je Mail ein Logeintrag, mail false."""
    with post() as liste, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.w, t.s1, serial_no="HN-1", manufactured_on="2023-01", begruendung="Platzhalter Mailtext")
        assert r.status_code == 201 and r.json["mail"] is True, r.get_json()
        assert [m[0] for m in liste] == ["katalog@example.org"], liste
        an, betreff, text = liste[0]
        inv = item(t.app, t.s1)["inventory_no"]
        assert betreff == f"strömis.de – Änderungsantrag: {inv} (Seriennummer, Herstellung)", betreff
        for teil in (f"{inv} – Testwerk Sonderteil Gamma", "Gliederung:   OG Musterstadt", "Seriennummer: AN-S1 → HN-1",
                     "Herstellung:  (leer) → 01/2023", "Platzhalter Mailtext", "wart beantragt",
                     "https://strömis.de/material/katalog/meldungen?bereich=antraege"):
            assert teil in text, (teil, text)
        a_sn, a_hd = [x["id"] for x in r.json["antraege"]]
        liste.clear()
        assert bestaetigen(t.mv, a_sn, antwort="Platzhalter Anmerkung").status_code == 200
        assert ablehnen(t.mv, a_hd, antwort="Platzhalter Ablehnung").status_code == 200
        assert [m[0] for m in liste] == ["wart@example.org"] * 2, liste
        assert "Änderungsantrag bestätigt" in liste[0][1] and "Platzhalter Anmerkung" in liste[0][2]
        assert "Seriennummer: AN-S1 → HN-1" in liste[0][2] and "Protokolle nennen weiter den alten Wert" in liste[0][2]
        assert "Änderungsantrag abgelehnt" in liste[1][1] and "Platzhalter Ablehnung" in liste[1][2]
        assert f"https://strömis.de/material/artikel/{t.s1}" in liste[1][2]
        # Die Material-Verwaltung beantragt selbst: keine Mail an sich; entscheidet selbst: keine Mail.
        liste.clear()
        r = beantragen(t.mv, t.k1, serial_no="AN-111")
        assert r.json["mail"] is False and liste == [], (r.get_json(), liste)
        assert bestaetigen(t.mv, r.json["antraege"][0]["id"]).status_code == 200 and liste == []
        # Ohne Material-Verwaltung: an die Plattform-Verwaltung.
        sql(t.app, "UPDATE users SET recht_material = 1 WHERE id = ?", (t.k["katalog_id"],))
        r = beantragen(t.w, t.s1, serial_no="AN-S2")
        assert [m[0] for m in liste] == ["admin@example.org"], liste
        sql(t.app, "UPDATE users SET recht_material = 2 WHERE id = ?", (t.k["katalog_id"],))
        # Still: Umgebungssperre und ohne Mailserver.
        from app.material.services import antrag
        for umg, grund in (({"MATERIAL_ERINNERUNGEN_SPERRE": "1"}, "Umgebungssperre"),
                           ({"STROEMIS_NAME": "stroemis-dev"}, "Umgebungssperre"), ({}, "kein Mailserver")):
            liste.clear()
            alt = antrag.MAILSERVER
            if not umg:
                antrag.MAILSERVER = lambda: False
            try:
                with umwelt(**umg), logzeilen(t.app) as log:
                    r = beantragen(t.w, t.g1, manufactured_on="2023-06", begruendung="Platzhalter still")
                    assert r.status_code == 201 and r.json["mail"] is False, r.get_json()
                    aid = r.json["antraege"][0]["id"]
                    assert ablehnen(t.mv, aid, antwort="Platzhalter still zurück").status_code == 200
            finally:
                antrag.MAILSERVER = alt
            assert liste == [], liste
            still = [z for z in log if f"Mail nicht verschickt ({grund})" in z]
            assert len(still) == 2 and "katalog@example.org" in still[0] and "Platzhalter still" in still[0], log
            assert "wart@example.org" in still[1] and "Platzhalter still zurück" in still[1], log
        # DEMO-Artikel: nur ins Log, mit [DEMO].
        g2, _ = gliederung(t.adm, "DEMO-OG Platzhalter", standard=False)
        sql(t.app, "UPDATE mat_folder SET demo = 1 WHERE id = ?", (g2,))
        d1 = neuer_artikel(t.adm, t.ids["hms"], g2, serial_no="DEMO-A1", manufactured_on="2024-01")["id"]
        sql(t.app, "INSERT INTO mat_inspection (item_id, kind, inspector_name, inspected_on, result, created_at, "
                   "updated_at, completed_at) VALUES (?, 'eingang', 'DEMO-Prüfer', '2026-10-01', 'einsatzbereit', "
                   "'2026-10-01T08:00:00+00:00', '2026-10-01T08:00:00+00:00', '2026-10-01T08:00:00+00:00')", (d1,))
        liste.clear()
        with logzeilen(t.app) as log:
            r = beantragen(t.adm, d1, serial_no="DEMO-A2")
            assert r.status_code == 201 and r.json["mail"] is False, r.get_json()
        assert liste == [] and any("DEMO-Artikel" in z and "[DEMO]" in z for z in log), log
    print("Mails bestanden.")


# --- 7. Artikel, Zahlen, Rückruf, Löschkonzept -------------------------------------------------------------------------

def test_artikel_und_zahlen():
    """Artikel: offene Anträge mit Inhalt für Materialwart und Prüfer, für die Führungskraft nur Feld und Zeitpunkt;
    darf_antrag. Zahlen für die Blase (/meldungen) und die Übersicht (/start) nur für die Material-Verwaltung. Seite
    „Meldungen“ mit bereich=antraege. Rückruf trifft die neue Seriennummer, nicht mehr die alte."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        aid = beantragen(t.w, t.k2, serial_no="HN-555", begruendung="Platzhalter sichtbar").json["antraege"][0]["id"]
        for c, inhalt in ((t.w, True), (t.p, True), (t.mv, True), (t.f, False)):
            a = lesen(c, t.k2)
            x = a["antraege"][0]
            assert (x["id"], x["feld"], x["inhalt"]) == (aid, "serial_no", inhalt), x
            assert (x["begruendung"], x["antragsteller"]) == (("Platzhalter sichtbar", "wart") if inhalt else (None, None))
            assert a["darf_antrag"] is inhalt, (c, a["darf_antrag"])
        assert t.mv.get("/api/material/meldungen?status=offen").json["antraege_offen"] == 1
        assert t.w.get("/api/material/meldungen?status=offen").json["antraege_offen"] is None
        assert t.mv.get("/api/material/start").json["antraege_offen"] == 1
        assert t.w.get("/api/material/start").json["antraege_offen"] is None
        assert t.mv.get("/api/material/antraege").json["meldungen_offen"] == 0
        import html as html_mod
        for adresse, soll in (("?bereich=antraege", "antraege"), ("?bereich=x", "produkte"), ("", "produkte")):
            seite = html_mod.unescape(t.w.get(f"/material/katalog/meldungen{adresse}").get_data(as_text=True))
            assert f'"bereich": "{soll}"' in seite, (adresse, seite[:1500])
        # Rückruf mit der neuen Nummer – vor der Bestätigung trifft er nicht, danach schon; die alte trifft nicht mehr.
        assert bestaetigen(t.mv, aid).status_code == 200
        r = t.mv.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", headers=H,
                      json={"title": "Platzhalter-Rückruf", "serials": f"HN-555\n{t.str_nr}", "mail": False})
        assert r.status_code == 201, r.get_json()
        assert r.json["betroffen"] == 1 and r.json["nicht_gefunden"] == [t.str_nr], r.get_json()
        assert [x["title"] for x in lesen(t.w, t.k2)["rueckrufe"]] == ["Platzhalter-Rückruf"]
    print("Artikel und Zahlen bestanden.")


def test_loeschkonzept():
    """Kontolöschen: material-folgen nennt die Anträge (gestellt oder entschieden); nach dem Löschen bleiben Namen, die
    Kennungen sind NULL, Journal mit Namen und Inhalten unverändert."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = beantragen(t.p, t.k1, serial_no="AN-150").json["antraege"][0]["id"]
        beantragen(t.p, t.g1, manufactured_on="2023-08")
        assert bestaetigen(t.mv, a1).status_code == 200
        f = t.adm.get(f"/api/admin/users/{t.k['pruefer_id']}/material-folgen").json
        assert f["antraege"] == 2, f
        assert t.adm.get(f"/api/admin/users/{t.k['katalog_id']}/material-folgen").json["antraege"] == 1
        assert t.adm.get(f"/api/admin/users/{t.k['fuehrung_id']}/material-folgen").json["antraege"] == 0
        journal_sql = "SELECT id, entity, entity_id, user_name, action, before_json, after_json FROM mat_audit ORDER BY id"
        vorher = zeilen(t.app, journal_sql)
        assert t.adm.delete(f"/api/admin/users/{t.k['pruefer_id']}", headers=H).status_code == 200
        assert t.adm.delete(f"/api/admin/users/{t.k['katalog_id']}", headers=H).status_code == 200
        z = zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")
        assert [(x["created_by"], x["created_by_name"], x["resolved_by"], x["resolved_by_name"]) for x in z] == [
            (None, "pruefer", None, "katalog"), (None, "pruefer", None, "")], z
        nachher = zeilen(t.app, journal_sql)
        assert nachher[:len(vorher)] == vorher             # Namen und Inhalte bleiben (die Kontokennung geht auf NULL)
    print("Löschkonzept bestanden.")


# --- 8. Migration 15 ------------------------------------------------------------------------------------------------------

def _schema(pfad):
    conn = sqlite3.connect(pfad)
    try:
        version = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0]
        trigger = {r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")}
        tabellen = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        return version, trigger, tabellen
    finally:
        conn.close()


def _zahlen(pfad):
    conn = sqlite3.connect(pfad)
    try:
        return {n: conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for (n,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat%' AND name NOT LIKE '%fts%'")}
    finally:
        conn.close()


def test_migration_15():
    """Frisch: Version 15, Tabelle, alle Trigger, der Artikeltrigger in der neuen Fassung. 14 → 15 (Tabelle und Trigger
    entfernt, Trigger aus Schritt 14 wieder angelegt): Daten unverändert, Trigger ersetzt, wirkt; zweiter Lauf ohne
    Änderung. 7 → 15 an einer Kopie (wenn angegeben): Zahlen wie 7 → 14, die Tabelle leer."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger, tabellen = _schema(pfad)
        assert version == "15" == endversion() and "mat_item_change" in tabellen, (version, tabellen)
        assert TRIGGER_NEU <= set(trigger) and "mat_item_change" in trigger["mat_item_stammdaten_fest"], trigger
        # Stand 14 nachstellen.
        conn = sqlite3.connect(pfad)
        conn.execute("DROP TABLE mat_item_change")
        for n in TRIGGER_NEU:
            conn.execute(f"DROP TRIGGER IF EXISTS {n}")
        for befehl in models.TRIGGER_14:
            conn.execute(befehl)
        conn.execute("UPDATE mat_meta SET wert = '14' WHERE schluessel = 'schema_version'")
        conn.commit()
        conn.close()
        assert "mat_item_change" not in _schema(pfad)[1]["mat_item_stammdaten_fest"]
        vorher = _zahlen(pfad)
        make_app(tmp)
        version, trigger, tabellen = _schema(pfad)
        assert version == "15" and TRIGGER_NEU <= set(trigger), (version, trigger)
        assert "mat_item_change" in trigger["mat_item_stammdaten_fest"]
        nachher = _zahlen(pfad)
        assert nachher.pop("mat_item_change") == 0 and nachher == vorher
        conn = sqlite3.connect(pfad)
        assert models.migrieren(conn) == models.SCHEMA_VERSION == 15
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_15(conn)
        assert conn.total_changes == n and _schema_in(conn) == trigger
        conn.rollback()
        conn.close()
    if KOPIE_STAND_7 and os.path.exists(KOPIE_STAND_7):
        with tempfile.TemporaryDirectory() as tmp14, tempfile.TemporaryDirectory() as tmp15:
            for d in (tmp14, tmp15):
                shutil.copyfile(KOPIE_STAND_7, os.path.join(d, "stroemis.db"))
            bis_schritt(14)(make_app, tmp14)
            make_app(tmp15)
            v14, t14, _ = _schema(os.path.join(tmp14, "stroemis.db"))
            v15, t15, tab15 = _schema(os.path.join(tmp15, "stroemis.db"))
            assert (v14, v15) == ("14", "15") and set(t15) == set(t14) | TRIGGER_NEU, (v14, v15)
            z14, z15 = _zahlen(os.path.join(tmp14, "stroemis.db")), _zahlen(os.path.join(tmp15, "stroemis.db"))
            assert z15.pop("mat_item_change") == 0 and z15 == z14, (z14, z15)
            # Auf den echten Daten: ein geprüfter Artikel bleibt fest.
            conn = sqlite3.connect(os.path.join(tmp15, "stroemis.db"))
            try:
                geprueft = conn.execute("SELECT item_id FROM mat_inspection WHERE completed_at IS NOT NULL LIMIT 1").fetchone()
                if geprueft:
                    try:
                        conn.execute("UPDATE mat_item SET serial_no = serial_no || '-x' WHERE id = ?", geprueft)
                        raise AssertionError("Trigger fehlt")
                    except sqlite3.IntegrityError:
                        pass
            finally:
                conn.close()
        print("Migration 7 → 15 aus der Kopie bestanden.")
    else:
        print("Migration 7 → 15 übersprungen (MATERIAL_KOPIE_STAND_7 nicht gesetzt).")
    print("Migration 15 bestanden.")


def _schema_in(conn):
    return {r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")}


# --- 9. Oberfläche (statisch) ----------------------------------------------------------------------------------------

def test_oberflaeche_statisch():
    """material.js: Dialog „Bearbeiten“ mit Nachtragen (Metall) und grauem „Änderung beantragen …“, offener Antrag als
    Hinweis; Antragsdialog mit Begründung und EINEM roten Knopf „Antrag senden“; Artikelseite für Prüfer ohne
    Verwalterrecht; Meldungen mit dem Bereich „Änderungsanträge“, Karten nur mit grauen Knöpfen, Rückfrage „Bestätigen“
    als roter Hauptknopf, „Ablehnen“ endgültig (rot umrandet); Blase zählt beides. Keine btn ghost. admin.js nennt die
    Anträge beim Löschen; CSS für Marke und Bereichswahl."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    admin = open(os.path.join(wurzel, "app/static/js/admin.js"), encoding="utf-8").read()
    dlg = js[js.index("function artikelDialog(a)"):js.index("/* --- Änderungsanträge")]
    assert "const nachtragen = fest && !!a.herstellung_nachtragbar;" in dlg
    assert 'datumFeld("ad-herst", null, "monat")' in dlg and "Nur Nachtragen möglich" in dlg
    assert ('<button class="btn secondary small" type="button" id="ad-antrag">Änderung beantragen …</button>' in dlg
            and "antragMoeglich(a)" in dlg and "antragOffenText(x)" in dlg)
    assert "} else if (nachtragen) {" in dlg and "if (nach) daten.manufactured_on = nach;" in dlg
    block = js[js.index("/* --- Änderungsanträge"):js.index("/* --- Artikel anlegen")]
    antrag_dlg = block[block.index("function antragDialog(a)"):]
    assert antrag_dlg.count('class="btn"') == 1 and '<button class="btn" id="aa-ok" type="button">Antrag senden</button>' in antrag_dlg
    assert 'id="aa-grund"' in antrag_dlg and "Begründung (Pflicht)" in antrag_dlg and "/antrag`" in antrag_dlg
    assert "wartet auf die Material-Verwaltung" in block
    seite = js[js.index("async function artikel()"):js.index("function artikelDialog(a)")]
    assert "antragMoeglich(a) && !darfPflegen" in seite and 'data-act="antrag">Änderung beantragen …</button>' in seite
    m = js[js.index("async function meldungen()"):js.index("function zuordnenDialog(m, danach)")]
    assert ">Änderungsanträge${zahl(nAntraege)}</button>" in m and "async function antraegeZeichnen()" in m
    karte = m[m.index("function antragKarte(x, bearbeiten)"):m.index("function antragBestaetigenDialog")]
    assert 'class="btn secondary small" data-act="bestaetigen"' in karte and 'data-act="antrag-ablehnen"' in karte
    assert 'class="btn"' not in karte and "btn danger" not in karte
    best = m[m.index("function antragBestaetigenDialog"):m.index("function antragAblehnenDialog")]
    assert best.count('class="btn"') == 1 and '<button class="btn" id="ba-ok" type="button">Bestätigen</button>' in best
    abl = m[m.index("function antragAblehnenDialog"):]
    assert '<button class="btn danger" id="aa-ablehnen" type="button">Ablehnen</button>' in abl and 'class="btn"' not in abl
    assert "btn ghost" not in js
    zaehlen = js[js.index("async function meldungenZaehlen(el)"):]
    assert "(d.offen || 0) + (d.antraege_offen || 0)" in zaehlen[:800]
    assert "d.antraege_offen ? `<p class=\"notice\"><a href=\"/material/katalog/meldungen?bereich=antraege\">" in js
    for x in ("antrag_gestellt:", "antrag_bestaetigt:", "antrag_abgelehnt:", "beantragt_von:", "ablehnung:"):
        assert x in js, x
    assert '"Änderungsantrag behält", "Änderungsanträge behalten"' in admin
    for x in (".mat-mstatus.m-bestaetigt", ".mat-meldung.m-bestaetigt", ".mat-bereiche {", ".mat-antrag-offen"):
        assert x in css, x
    from app.material.services import beschriftung
    assert beschriftung.AKTION["antrag_bestaetigt"] == "Änderung bestätigt (Antrag)" and beschriftung.FELD["antrag"]
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_nachtragen()
    test_rechte()
    test_eingaben()
    test_entscheiden()
    test_trigger()
    test_mails()
    test_artikel_und_zahlen()
    test_loeschkonzept()
    test_migration_15()
    test_oberflaeche_statisch()
