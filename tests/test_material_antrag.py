"""Änderungsanträge an Stammdaten (Modul Material, Entscheidungen des Nutzers vom 21.10.2026; seit dem 24.10.2026 an allen
Stammdaten, Freigabe durch die zuständigen Materialwarte – Entscheidungen E1–E8): python tests/test_material_antrag.py

Seit der ersten abgeschlossenen Prüfung stehen die Stammdaten fest (test_material_stammdaten.py). Jede Änderung –
auch STR-Nummer → Herstellernummer, auch ein leeres Herstelldatum nachtragen (E3) – beantragen Materialwart oder Prüfer
mit Begründung; die Materialwarte des Ordners (eigene Freigabe „verwalten“ an der Heimat oder darüber) bestätigen oder
lehnen ab, den eigenen Antrag eingeschlossen (E5); die Material-Verwaltung nur mit eigener Verwalterfreigabe (E6).
Bestätigt steht die Änderung sofort am Artikel (Journal mit alt/neu, Antragsteller, Bestätiger, Begründung); der Trigger
lässt genau diese Änderung einmal zu. Mails an die zuständigen Materialwarte (Rückfall Material-Verwaltung, dann
Plattform-Verwaltung) und an den Antragsteller; DEMO, dev-Sperre und ohne Mailserver ins Log.
Dazu die Schritte 15–17 der Migration, Rückrufabgleich mit der neuen Nummer, Löschkonzept und die Oberfläche (statisch).
Prüfung vom 21.10.2026 (Abschnitt 10): Leser sehen im Verlauf und im Lebenslauf weder Begründung noch Namen, Bescheid nur
an einen Antragsteller, der den Artikel noch liest, Schritt 16 (Trigger gegen Umwege an der Sperre vorbei), Hinweis auf
laufende Rückrufe, „vormals …“ im Sammelprotokoll.
Entscheidungen vom 21.10.2026 zur Prüfung (Abschnitt 11): Der Antragsteller zieht seinen offenen Antrag selbst zurück;
das Herstelldatum lässt sich nur noch ändern, nicht entfernen (auch nicht per Antrag); Schritt 17 mit Altbestand.
Sammelanträge, die neuen Felder, Zuständigkeit je Rolle und Schritt 23: test_material_antrag_zustaendig.py.
Echte Mails gehen nie hinaus (die Nahtstelle mailprotokoll.versand ist ersetzt). Alle Namen, Nummern und Texte sind Platzhalter."""
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, abschluss, gliederung, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pruef_formulare, punkte_von, starten, umgebung, mails_abfangen, mails_zurueck)
from test_material_erinnerung import umwelt  # noqa: E402
from test_material_trennung import bis_schritt, endversion  # noqa: E402

# Eine KOPIE einer Datenbank auf Stand 7 für den Pfad 7 → 15 – nur, wenn angegeben; die Quelle bleibt unberührt.
KOPIE_STAND_7 = os.environ.get("MATERIAL_KOPIE_STAND_7") or ""
FEST = ("Seit der ersten Prüfung stehen die Stammdaten fest – sie sind Teil des Prüfnachweises. Eine Änderung beantragst "
        "du mit Begründung; entscheiden die Materialwarte des Ordners.")
NUR_ZUSTAENDIG = "Entscheiden dürfen die Materialwarte dieses Ordners"
ANTRAG_FEST = "Ein Änderungsantrag lässt sich nur einmal entscheiden"
TRIGGER_NEU = {"mat_item_stammdaten_fest", "mat_item_antrag_angewendet", "mat_item_change_inhalt",
               "mat_item_change_antragsteller", "mat_item_change_entscheider", "mat_item_change_entschieden",
               "mat_item_change_angewendet", "mat_item_change_loeschen", "mat_item_change_ersetzen", "mat_item_change_neu"}
TRIGGER_16 = {"mat_item_ersetzen", "mat_item_kennung", "mat_item_geprueft_loeschen", "mat_item_produkt_fest",
              "mat_product_materialart_fest", "mat_product_ersetzen", "mat_product_kennung"}
TRIGGER_17 = {"mat_item_change_herstellung_leer", "mat_item_change_entfernen_bestaetigen", "mat_item_change_zurueckziehen"}
TRIGGER_19 = {"mat_mail_fehler_fest", "mat_mail_fehler_ordner"}
TRIGGER_23 = {"mat_item_change_gruppe"}


def trigger_21():
    """Die Trigger aus Schritt 21 (Sets) – zwei davon ersetzen gleichnamige aus Schritt 6."""
    from app.material import models
    return {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.TRIGGER_21}


def trigger_26():
    """Die Trigger seit Schritt 26 (Rückbau der Set-Funktion): (neu bzw. ersetzt, entfernt)."""
    from app.material import models
    neu = {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.TRIGGER_26}
    return neu, set(models.TRIGGER_WEG_26)


def trigger_27():
    """Die Trigger aus Schritt 27 (Set-Protokolle im Prüfdurchgang)."""
    from app.material import models
    return {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.TRIGGER_27}


def trigger_30():
    """Die Trigger aus Schritt 30 (Kennungen und Kontoverweise gegen SQL von Hand, Nachbesserung vor dem Merge)."""
    from app.material import models
    return {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.SCHRITT_30}


def trigger_31():
    """Die Trigger aus Schritt 31 (Verzeichnis ausgegebener Lebensläufe, unveränderlich)."""
    from app.material import models
    return {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.SCHRITT_31 if "CREATE TRIGGER" in x}


def trigger_32():
    """Die Trigger aus Schritt 32 (REPLACE ohne recursive_triggers): fünf ersetzen gleichnamige aus Schritt 30, zwei sind
    neu am Artikel."""
    from app.material import models
    return {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0]
            for x in models.TRIGGER_32_ZEILE + models.TRIGGER_32_ARTIKEL}


def trigger_25(nur_antrag=False):
    """Die Trigger aus Schritt 25 (Bestandteil-Liste, Seriennummern der Bestandteile) – zwei ersetzen gleichnamige aus
    Schritt 21. nur_antrag: nur die, die mat_item_change lesen (wer die Tabelle entfernt, entfernt sie mit)."""
    from app.material import models
    return {x.split("CREATE TRIGGER IF NOT EXISTS ", 1)[1].split()[0] for x in models.TRIGGER_25
            if not nur_antrag or "mat_item_change" in x}
HERST_BLEIBT = "nicht entfernen"


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
    alt = mails_abfangen(antrag, lambda an, betreff, inhalt: liste.append((an, betreff, inhalt)) or True)
    try:
        yield liste
    finally:
        mails_zurueck(alt)


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
    """GEÄNDERT am 24.10.2026 (Entscheidung E3): Ein leeres Herstelldatum trägt nach der ersten Prüfung niemand mehr
    direkt nach – auch bei Metall nicht (PUT 409); per Antrag geht es bei jeder Materialart. Seriennummer bleibt fest,
    auch im selben PUT. Bemerkung ändern Materialwart UND Prüfer direkt (E2), die Führungskraft nicht."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a = lesen(t.w, t.k2)
        assert a["stammdaten_fest"] and a["darf_antrag"] and "herstellung_nachtragbar" not in a, a
        for d in ({"serial_no": "AN-200", "manufactured_on": "2023-11"}, {"stand": a["stand"], "manufactured_on": "2023-11"}):
            r = t.w.put(f"/api/material/artikel/{t.k2}", json=d)
            assert r.status_code == 409 and r.json["error"] == FEST, (d, r.get_json())
        assert item(t.app, t.k2)["manufactured_on"] is None
        r = beantragen(t.w, t.k2, manufactured_on="2023-11")
        assert r.status_code == 201, r.get_json()
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        assert item(t.app, t.k2)["manufactured_on"] == "2023-11"
        for wert in ("2023-10", "2023-11-05", "", None):
            r = t.w.put(f"/api/material/artikel/{t.k2}", json={"manufactured_on": wert})
            assert r.status_code == 409 and r.json["error"] == FEST, (wert, r.get_json())
        # „sonstiges“ und textil: ebenso nur per Antrag.
        r = t.w.put(f"/api/material/artikel/{t.s1}", json={"manufactured_on": "2023-11"})
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        assert beantragen(t.w, t.s1, manufactured_on="2023-11").status_code == 201
        g2 = neuer_artikel(t.w, t.ids["gurt"], t.lager, serial_no="AN-G2", manufactured_on="2024-02")["id"]
        sql(t.app, "UPDATE mat_item SET manufactured_on = NULL, retire_by = NULL WHERE id = ?", (g2,))
        pruefen(t.p, g2, gurt=True)
        r = t.w.put(f"/api/material/artikel/{g2}", json={"manufactured_on": "2024-02"})
        assert r.status_code == 409, r.get_json()
        # Bemerkung: Prüfer direkt (E2), Führungskraft nicht.
        assert t.p.put(f"/api/material/artikel/{t.k1}", json={"notes": "x"}).status_code == 200
        assert t.f.put(f"/api/material/artikel/{t.k1}", json={"notes": "y"}).status_code == 403
    print("Nachtragen bestanden.")


# --- 2. Rechte ---------------------------------------------------------------------------------------------------------

def test_rechte():
    """Beantragen: Materialwart und Prüfer (201), Führungskraft (nur lesen) 403, ohne Stufe 403, fremde Gliederung 404 wie
    unbekannt, ungeprüft und ausgesondert 409. Liste: der Materialwart die eigenen und die, die er entscheidet, der Prüfer
    die eigenen, Führungskraft und Material-Verwaltung (ohne eigene Verwalterfreigabe) keine, ohne Stufe 403. Entscheiden
    nur die Materialwarte des Ordners – auch den eigenen Antrag (E5); sonst 403, unbekannt 404."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.w, t.k1, serial_no="AN-101")
        assert r.status_code == 201 and len(r.json["antrag"]["aenderungen"]) == 1, r.get_json()
        a_w = r.json["antrag"]
        x = a_w["aenderungen"][0]
        assert (x["feld"], x["alt"], x["neu"], a_w["status"], a_w["eigen"]) == ("serial_no", "AN-100", "AN-101", "offen",
                                                                              True), a_w
        assert r.json["artikel"]["antraege"][0]["id"] == a_w["id"]
        r = beantragen(t.p, t.g1, manufactured_on="2023-12")
        assert r.status_code == 201, r.get_json()
        a_p = r.json["antrag"]["id"]
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
        d = t.w.get("/api/material/antraege").json
        assert d["filter"] == "offen" and d["zu_entscheiden"] == 2 and {x["id"] for x in d["antraege"]} == {a_w["id"], a_p}
        assert d["antraege"][0]["artikel"]["inventory_no"] and d["antraege"][0]["artikel"]["gliederung"] == "OG Musterstadt"
        assert all(x["entscheiden"] for x in d["antraege"])
        d = t.p.get("/api/material/antraege").json
        assert [x["id"] for x in d["antraege"]] == [a_p] and d["zu_entscheiden"] == 0 and not d["antraege"][0]["entscheiden"]
        for c in (t.f, t.mv, t.adm):
            d = c.get("/api/material/antraege").json
            assert d["antraege"] == [] and d["zu_entscheiden"] == 0, d
        assert t.k["nutzer"].get("/api/material/antraege").status_code == 403
        # Entscheiden: nur der Materialwart des Ordners.
        for c in (t.p, t.f, t.mv, t.adm):
            for f in (bestaetigen, ablehnen):
                r = f(c, a_w["id"], antwort="x")
                assert r.status_code == 403 and NUR_ZUSTAENDIG in r.json["error"], r.get_json()
        assert bestaetigen(t.k["nutzer"], a_w["id"]).status_code == 403
        assert bestaetigen(t.w, 999999).status_code == 404 and ablehnen(t.w, 999999, antwort="x").status_code == 404
        assert bestaetigen(t.w, a_w["id"]).status_code == 200
        assert ablehnen(t.w, a_p, antwort="Platzhalter: Datum stimmt").status_code == 200
        assert item(t.app, t.k1)["serial_no"] == "AN-101" and item(t.app, t.g1)["manufactured_on"] == "2024-01"
        # Erledigte: „erledigt“ zeigt beide, „offen“ keinen mehr.
        d = t.w.get("/api/material/antraege?status=erledigt").json
        assert {x["status"] for x in d["antraege"]} == {"bestaetigt", "abgelehnt"} and d["zu_entscheiden"] == 0, d
        assert t.w.get("/api/material/antraege").json["antraege"] == []
        assert [x["status"] for x in t.p.get("/api/material/antraege?status=alle").json["antraege"]] == ["abgelehnt"]
    print("Rechte bestanden.")


# --- 3. Prüfen beim Antrag ---------------------------------------------------------------------------------------------

def test_eingaben():
    """Begründung Pflicht, etwas muss sich ändern; Seriennummer nicht STR-…, je Produkt eindeutig (sichtbar: 409 mit
    Inventarnummer; fremd: 409 ohne, protokolliert); Herstelldatum Format, nicht in der Zukunft, nicht nach dem Kauf,
    nicht entfernen; ein offener Antrag je Artikel (409, auch für ein anderes Feld); beide Felder in einem Antrag: ein
    Sammelantrag (Kopf und Folgezeile), ein Journaleintrag."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        k1 = item(t.app, t.k1)
        faelle = [
            ({"serial_no": "AN-101", "begruendung": ""}, 400, "Begründung"),
            ({"serial_no": "AN-101", "begruendung": "   "}, 400, "Begründung"),
            ({}, 400, "mindestens ein Feld"),
            ({"serial_no": "  "}, 400, "mindestens ein Feld"),
            ({"serial_no": "AN-100"}, 400, "mindestens ein Feld"),
            ({"serial_no": "STR-000123"}, 400, "STR-"),
            ({"serial_no": "x" * 81}, 400, "zu lang"),
            ({"serial_no": "AN-NEU"}, 409, k1["inventory_no"][:2]),               # gibt es bei neu1 (sichtbar)
            ({"manufactured_on": "2024-03"}, 400, "mindestens ein Feld"),
            ({"manufactured_on": "03/2024"}, 400, "Monat (JJJJ-MM)"),
            ({"manufactured_on": "2099-01"}, 400, "Zukunft"),
            ({"manufactured_on": "2024-06"}, 400, "Kaufdatum"),
            ({"manufactured_on": "2024-02", "herstellung_entfernen": True}, 400, HERST_BLEIBT),
            ({"herstellung_entfernen": True}, 400, HERST_BLEIBT),
            ({"manufactured_on": ""}, 400, HERST_BLEIBT),
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
        assert r.status_code == 400 and HERST_BLEIBT in r.json["error"], r.get_json()
        assert antraege(t.app, t.k1) == [] and antraege(t.app, t.g1) == []
        # Beide Felder auf einmal: ein Sammelantrag – Kopf und Folgezeile mit derselben Begründung, ein Journaleintrag.
        r = beantragen(t.w, t.k1, serial_no="AN-101", manufactured_on="2024-02", begruendung="Platzhalter beide")
        assert r.status_code == 201 and [x["feld"] for x in r.json["antrag"]["aenderungen"]] == ["serial_no",
                                                                                                "manufactured_on"]
        z = antraege(t.app, t.k1)
        assert [(x["field"], x["old_value"], x["new_value"], x["reason"], x["created_by_name"], x["group_id"]) for x in z] == [
            ("serial_no", "AN-100", "AN-101", "Platzhalter beide", "wart", None),
            ("manufactured_on", "2024-03", "2024-02", "Platzhalter beide", "wart", z[0]["id"])], z
        j = journal(t.app, t.k1, "antrag_gestellt")
        assert len(j) == 1 and j[0]["vorher"] == {"serial_no": "AN-100", "manufactured_on": "2024-03"}, j
        assert j[0]["nachher"]["antrag"] == z[0]["id"] and j[0]["user_name"] == "wart"
        assert j[0]["nachher"]["begruendung"] == "Platzhalter beide"
        # Ein offener Antrag je Artikel – auch für ein anderes Feld und einen anderen Antragsteller.
        for d in ({"serial_no": "AN-102"}, {"purchased_on": "2024-06"}):
            r = beantragen(t.p, t.k1, **d)
            assert r.status_code == 409 and "läuft schon ein Änderungsantrag" in r.json["error"], r.get_json()
        r = beantragen(t.w, t.fb, herstellung_entfernen=True)
        assert r.status_code == 404
        r = beantragen(t.adm, t.fb, serial_no="AN-B9")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"], r.get_json()
        assert item(t.app, t.k1)["serial_no"] == "AN-100"
    print("Eingaben bestanden.")


# --- 4. Bestätigen und ablehnen ----------------------------------------------------------------------------------------

def test_entscheiden():
    """STR → Herstellernummer bestätigt (vom Materialwart des Ordners): Nummer am Artikel, serial_generated 0, applied_at,
    Journal mit alt/neu, Antragsteller, Bestätiger, Begründung; zweites Entscheiden 409. Textil: Lebensende rechnet neu.
    Eindeutigkeit beim Bestätigen (anderer Antrag hat die Nummer inzwischen bekommen) 409; Stand geändert 409;
    ausgesondert nur ablehnen. Ablehnen nur mit Begründung, Artikel unverändert, Journal. Danach ist ein neuer Antrag
    möglich. Die Material-Verwaltung beantragt (sie verwaltet alles) – entscheiden darf sie ohne eigene
    Verwalterfreigabe nicht, der Materialwart schon."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.p, t.k2, serial_no="HN-777", begruendung="Platzhalter: Herstellernummer gefunden")
        aid = r.json["antrag"]["id"]
        r = bestaetigen(t.w, aid, antwort="Platzhalter Anmerkung")
        assert r.status_code == 200 and r.json["antrag"]["status"] == "bestaetigt", r.get_json()
        z = item(t.app, t.k2)
        assert (z["serial_no"], z["serial_generated"]) == ("HN-777", 0), z
        a = antraege(t.app, t.k2)[0]
        assert a["applied_at"] and a["resolved_by_name"] == "wart" and a["answer"] == "Platzhalter Anmerkung", a
        j = journal(t.app, t.k2, "antrag_bestaetigt")
        assert len(j) == 1 and j[0]["user_name"] == "wart", j
        assert j[0]["vorher"] == {"serial_no": t.str_nr, "serial_generated": True}, j
        assert j[0]["nachher"] == {"serial_no": "HN-777", "serial_generated": False, "antrag": aid, "beantragt_von": "pruefer",
                                   "begruendung": "Platzhalter: Herstellernummer gefunden",
                                   "anmerkung": "Platzhalter Anmerkung"}, j
        for f in (bestaetigen, ablehnen):
            r = f(t.w, aid, antwort="noch einmal")
            assert r.status_code == 409 and "schon entschieden" in r.json["error"], r.get_json()
        a = lesen(t.w, t.k2)
        assert a["antraege"] == [] and a["serial_no"] == "HN-777"
        assert any(e["action"] == "antrag_bestaetigt" for e in a["journal"])
        # Festgeschriebene Protokolle bleiben, wie sie sind: Prüfsumme der Datei unverändert und gültig.
        x = zeilen(t.app, "SELECT id FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL", (t.k2,))[0]
        assert t.w.get(f"/materialablage/pruefung/{x['id']}/pdf").status_code == 200

        # Textil: neues Herstelldatum → Lebensende neu (10 Jahre).
        aid = beantragen(t.p, t.g1, manufactured_on="2023-07").json["antrag"]["id"]
        assert item(t.app, t.g1)["retire_by"] == "2034-01-01"
        assert bestaetigen(t.w, aid).status_code == 200
        z = item(t.app, t.g1)
        assert (z["manufactured_on"], z["retire_by"]) == ("2023-07", "2033-07-01"), z
        j = journal(t.app, t.g1, "antrag_bestaetigt")[0]
        assert j["vorher"] == {"manufactured_on": "2024-01", "retire_by": "2034-01-01"}, j
        assert "anmerkung" not in j["nachher"] and j["nachher"]["beantragt_von"] == "pruefer"

        # Eindeutigkeit beim Bestätigen: zwei Anträge auf dieselbe neue Nummer – der zweite scheitert erst jetzt.
        a1 = beantragen(t.p, t.k1, serial_no="HN-900").json["antrag"]["id"]
        k3 = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-300")["id"]
        pruefen(t.p, k3)
        a2 = beantragen(t.p, k3, serial_no="hn-900").json["antrag"]["id"]
        assert bestaetigen(t.w, a1).status_code == 200
        r = bestaetigen(t.w, a2)
        assert r.status_code == 409 and "gibt es bei diesem Produkt schon" in r.json["error"], r.get_json()
        assert antraege(t.app, k3)[0]["status"] == "offen" and item(t.app, k3)["serial_no"] == "AN-300"
        d = {x["id"]: x for x in t.w.get("/api/material/antraege").json["antraege"]}
        assert d[a2]["passt"] is True
        # Ablehnen: Begründung Pflicht, Artikel unverändert, Journal.
        assert ablehnen(t.w, a2).status_code == 400 and ablehnen(t.w, a2, antwort=" ").status_code == 400
        r = ablehnen(t.w, a2, antwort="Platzhalter: Nummer vergeben")
        assert r.status_code == 200 and r.json["antrag"]["status"] == "abgelehnt", r.get_json()
        assert item(t.app, k3)["serial_no"] == "AN-300" and antraege(t.app, k3)[0]["applied_at"] is None
        j = journal(t.app, k3, "antrag_abgelehnt")
        assert j[0]["nachher"] == {"antrag": a2, "feld": "Seriennummer", "ablehnung": "Platzhalter: Nummer vergeben"}, j
        # Danach ist ein neuer Antrag möglich.
        assert beantragen(t.w, k3, serial_no="HN-901").status_code == 201

        # Stand geändert (an Dienst und Trigger vorbei nachgestellt): bestätigen 409, ablehnen geht.
        a3 = beantragen(t.p, t.s1, serial_no="AN-S9").json["antrag"]["id"]
        _ohne_trigger(t.app, "UPDATE mat_item SET serial_no = 'AN-S8' WHERE id = ?", (t.s1,))
        assert [x["passt"] for x in t.w.get("/api/material/antraege").json["antraege"] if x["id"] == a3] == [False]
        r = bestaetigen(t.w, a3)
        assert r.status_code == 409 and "nicht mehr den Wert" in r.json["error"], r.get_json()
        assert ablehnen(t.w, a3, antwort="Platzhalter: Stand geändert").status_code == 200
        # Ausgesondert nach dem Antrag: nur noch ablehnen.
        a4 = beantragen(t.p, t.s1, manufactured_on="2022-05").json["antrag"]["id"]
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (t.s1,))
        r = bestaetigen(t.w, a4)
        assert r.status_code == 409 and "nur noch ablehnen" in r.json["error"], r.get_json()
        assert ablehnen(t.w, a4, antwort="Platzhalter: ausgesondert").status_code == 200

        # Die Material-Verwaltung beantragt (sie verwaltet alles), entscheiden darf sie ohne eigene Verwalterfreigabe nicht.
        r = beantragen(t.mv, t.fb, serial_no="AN-B9")
        assert r.status_code == 409 and "noch nicht geprüft" in r.json["error"]
        aid = beantragen(t.mv, t.k1, manufactured_on="2024-01").json["antrag"]["id"]
        assert t.mv.get("/api/material/antraege").json["antraege"][0]["eigen"] is True
        assert bestaetigen(t.mv, aid).status_code == 403
        assert bestaetigen(t.w, aid).status_code == 200
        j = journal(t.app, t.k1, "antrag_bestaetigt")[-1]
        assert j["user_name"] == "wart" and j["nachher"]["beantragt_von"] == "katalog", j
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
        conn.execute(models.TRIGGER_23_ARTIKEL[0])
        conn.commit()
    finally:
        conn.close()


# --- 5. Trigger ----------------------------------------------------------------------------------------------------------

def test_trigger():
    """An der Schnittstelle vorbei: Eine Änderung nach der ersten Prüfung geht nur mit einem bestätigten, nicht
    angewendeten Antrag mit genau diesem alten und neuen Wert – und nur einmal; seit Schritt 23 auch kein Nachtragen bei
    Metall mehr. Anträge: nur offen einfügen, Inhalt fest, einmal entscheiden, nicht löschen, nicht ersetzen, applied_at
    einmal und nur nach der Bestätigung, Kontokennung nur auf NULL; höchstens ein offener je Artikel."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        wart = t.k["wart_id"]

        def geht_nicht(befehl, args=(), text="seit seiner ersten Prüfung fest"):
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
            conn.execute("UPDATE mat_item_change SET status = ?, answer = ?, resolved_by = ?, resolved_by_name = 'wart', "
                         "resolved_at = '2026-10-21T09:00:00+00:00' WHERE id = ?", (status, antwort, wart, aid))

        try:
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-T1' WHERE id = ?", (t.k1,))
            # Offener Antrag reicht nicht.
            aid = neu(t.k1, "serial_no", "AN-100", "AN-T1")
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-T1' WHERE id = ?", (t.k1,))
            # Nur offen einfügbar; je Artikel nur ein offener.
            geht_nicht("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, status, created_by_name, "
                       "created_at, resolved_at, resolved_by_name) VALUES (?, 'manufactured_on', '2024-01', '2023-01', 'x', "
                       "'bestaetigt', 'x', 'x', 'x', 'x')", (t.g1,), ANTRAG_FEST)
            try:
                neu(t.k1, "serial_no", "AN-100", "AN-T2")
                raise AssertionError("zweiter offener Antrag")
            except sqlite3.IntegrityError as e:
                assert "höchstens ein offener" in str(e) or "UNIQUE" in str(e), e
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
                           "UPDATE mat_item_change SET group_id = 1 WHERE id = ?",
                           "DELETE FROM mat_item_change WHERE id = ?"):
                geht_nicht(befehl, (aid3,), ANTRAG_FEST)
            for befehl in ("UPDATE mat_item_change SET status = 'abgelehnt', answer = 'x' WHERE id = ?",
                           "UPDATE mat_item_change SET answer = 'anders' WHERE id = ?",
                           "UPDATE mat_item_change SET resolved_by_name = 'jemand' WHERE id = ?",
                           f"UPDATE mat_item_change SET resolved_by = {t.k['pruefer_id']} WHERE id = ?",
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
            # Nachtragen: seit Schritt 23 bei keiner Materialart ohne Antrag (E3); entfernen gar nicht – auch kein Antrag
            # darauf (Schritt 17).
            geht_nicht("UPDATE mat_item SET manufactured_on = '2023-10' WHERE id = ?", (t.k2,))
            geht_nicht("UPDATE mat_item SET manufactured_on = '2023-10' WHERE id = ?", (t.s1,))
            for leer in (None, "", "  "):
                geht_nicht("INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, "
                           "created_by_name, created_at) VALUES (?, 'manufactured_on', '2023-10', ?, 'x', ?, 'wart', 'x')",
                           (t.k2, leer, wart), HERST_BLEIBT)
            aid4 = neu(t.k2, "manufactured_on", None, "2023-10")
            entscheiden(aid4)
            conn.execute("UPDATE mat_item SET manufactured_on = '2023-10' WHERE id = ?", (t.k2,))
            geht_nicht("UPDATE mat_item SET manufactured_on = NULL WHERE id = ?", (t.k2,))
            # Ungeprüft: frei wie bisher.
            conn.execute("UPDATE mat_item SET serial_no = 'AN-NEU9', manufactured_on = NULL, purchased_on = '2024-01', "
                         "interval_months = 6 WHERE id = ?", (t.neu1,))
            conn.commit()
        finally:
            conn.close()
        assert (item(t.app, t.k1)["serial_no"], item(t.app, t.k2)["manufactured_on"]) == ("AN-T1", "2023-10")
    print("Trigger bestanden.")


# --- 6. Mails ------------------------------------------------------------------------------------------------------------

def test_mails():
    """Neuer Antrag: an die zuständigen Materialwarte (nicht an den Antragsteller), mit Inventarnummer, alt → neu,
    Begründung, Link auf die Liste im Bestand; ohne jedes zuständige Konto an die Material-Verwaltung, ohne sie an die
    Plattform-Verwaltung. Entscheidung: an den Antragsteller (bestätigt mit Anmerkung, abgelehnt mit Begründung), nicht
    bei eigener Entscheidung. Umgebungssperre, ohne Mailserver, DEMO: nichts verschickt, je Mail ein Logeintrag, mail
    false."""
    with post() as liste, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        r = beantragen(t.p, t.s1, serial_no="HN-1", manufactured_on="2023-01", begruendung="Platzhalter Mailtext")
        assert r.status_code == 201 and r.json["mail"] is True, r.get_json()
        assert [m[0] for m in liste] == ["wart@example.org"], liste
        an, betreff, text = liste[0]
        inv = item(t.app, t.s1)["inventory_no"]
        assert betreff == f"strömis.de – Änderungsantrag: {inv} (Seriennummer, Herstellung)", betreff
        for teil in (f"{inv} – Testwerk Sonderteil Gamma", "Gliederung:    OG Musterstadt", "Seriennummer:  AN-S1 → HN-1",
                     "Herstellung:   (leer) → 01/2023", "Platzhalter Mailtext", "pruefer beantragt",
                     "https://strömis.de/materialablage/bestand/antraege", "weil du den Ordner „OG Musterstadt / Lager“ verwaltest"):
            assert teil in text, (teil, text)
        kid = r.json["antrag"]["id"]
        liste.clear()
        assert bestaetigen(t.w, kid, antwort="Platzhalter Anmerkung").status_code == 200
        assert [m[0] for m in liste] == ["pruefer@example.org"], liste
        assert "Änderungsantrag bestätigt" in liste[0][1] and "Platzhalter Anmerkung" in liste[0][2]
        assert "Seriennummer:  AN-S1 → HN-1" in liste[0][2] and "Protokolle nennen weiter den alten Wert" in liste[0][2]
        kid2 = beantragen(t.p, t.s1, first_use_on="2024-01").json["antrag"]["id"]
        liste.clear()
        assert ablehnen(t.w, kid2, antwort="Platzhalter Ablehnung").status_code == 200
        assert [m[0] for m in liste] == ["pruefer@example.org"], liste
        assert "Änderungsantrag abgelehnt" in liste[0][1] and "Platzhalter Ablehnung" in liste[0][2]
        assert f"https://strömis.de/materialablage/artikel/{t.s1}" in liste[0][2]
        # Der Materialwart beantragt selbst: keine Mail an sich (er ist der einzige zuständige) und entscheidet selbst.
        liste.clear()
        r = beantragen(t.w, t.k1, serial_no="AN-111")
        assert r.json["mail"] is False and liste == [], (r.get_json(), liste)
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200 and liste == []
        # Die Material-Verwaltung beantragt: Mail an den Materialwart, Bescheid an sie.
        r = beantragen(t.mv, t.k1, serial_no="AN-112")
        assert [m[0] for m in liste] == ["wart@example.org"], liste
        liste.clear()
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        assert [m[0] for m in liste] == ["katalog@example.org"] and "Änderungsantrag bestätigt" in liste[0][1], liste
        # Ohne zuständiges Konto (die Verwalterfreigabe ist weg): an die Material-Verwaltung, ohne sie an die
        # Plattform-Verwaltung.
        sql(t.app, "UPDATE mat_folder_grant SET permission = 'lesen' WHERE user_id = ? AND permission = 'verwalten'",
            (t.k["wart_id"],))
        liste.clear()
        r = beantragen(t.p, t.s1, purchased_on="2024-02")
        assert [m[0] for m in liste] == ["katalog@example.org"] and "Freigabe „verwalten“ gibst" in liste[0][2], liste
        assert zurueckziehen(t.p, r.json["antrag"]["id"]).status_code == 200
        sql(t.app, "UPDATE users SET recht_material = 1 WHERE id = ?", (t.k["katalog_id"],))
        liste.clear()
        r = beantragen(t.p, t.s1, purchased_on="2024-02")
        assert [m[0] for m in liste] == ["admin@example.org"], liste
        assert zurueckziehen(t.p, r.json["antrag"]["id"]).status_code == 200
        sql(t.app, "UPDATE users SET recht_material = 2 WHERE id = ?", (t.k["katalog_id"],))
        sql(t.app, "UPDATE mat_folder_grant SET permission = 'verwalten' WHERE user_id = ? AND permission = 'lesen'",
            (t.k["wart_id"],))
        # Still: Umgebungssperre und ohne Mailserver.
        from app.material.services import mailprotokoll
        for umg, grund in (({"MATERIAL_ERINNERUNGEN_SPERRE": "1"}, "Umgebungssperre"),
                           ({"STROEMIS_NAME": "stroemis-dev"}, "Umgebungssperre"), ({}, "kein Mailserver")):
            liste.clear()
            alt = mailprotokoll.MAILSERVER
            if not umg:
                mailprotokoll.MAILSERVER = lambda: False
            try:
                with umwelt(**umg), logzeilen(t.app) as log:
                    r = beantragen(t.p, t.g1, manufactured_on="2023-06", begruendung="Platzhalter still")
                    assert r.status_code == 201 and r.json["mail"] is False, r.get_json()
                    assert ablehnen(t.w, r.json["antrag"]["id"], antwort="Platzhalter still zurück").status_code == 200
            finally:
                mailprotokoll.MAILSERVER = alt
            assert liste == [], liste
            still = [z for z in log if f"Mail nicht verschickt ({grund})" in z]
            assert len(still) == 2 and "wart@example.org" in still[0] and "Platzhalter still" in still[0], log
            assert "pruefer@example.org" in still[1] and "Platzhalter still zurück" in still[1], log
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
    """Artikel: offene Anträge mit Inhalt für Materialwart, Prüfer und Material-Verwaltung, für die Führungskraft nur
    Felder und Zeitpunkt; darf_antrag nur ohne offenen Antrag. Zahlen für die Blase (/antraege) und die Übersicht (/start)
    für jeden, der entscheiden darf; die Produktmeldungen zählen sie nicht mehr. Alte Adresse leitet weiter. Rückruf trifft
    die neue Seriennummer, nicht mehr die alte."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        aid = beantragen(t.p, t.k2, serial_no="HN-555", begruendung="Platzhalter sichtbar").json["antrag"]["id"]
        for c, inhalt in ((t.w, True), (t.p, True), (t.mv, True), (t.f, False)):
            a = lesen(c, t.k2)
            x = a["antraege"][0]
            assert (x["id"], x["aenderungen"][0]["feld"], x["inhalt"]) == (aid, "serial_no", inhalt), x
            assert (x["begruendung"], x["antragsteller"]) == (("Platzhalter sichtbar", "pruefer") if inhalt else (None, None))
            assert a["darf_antrag"] is False and a["antrag_offen"] is True, (c, a["darf_antrag"])
        assert lesen(t.w, t.k1)["darf_antrag"] is True and lesen(t.f, t.k1)["darf_antrag"] is False
        assert "antraege_offen" not in t.mv.get("/api/material/meldungen?status=offen").json
        assert t.w.get("/api/material/start").json["antraege_offen"] == 1
        for c in (t.mv, t.p, t.f):
            assert c.get("/api/material/start").json["antraege_offen"] == 0
        assert t.w.get("/api/material/antraege").json["zu_entscheiden"] == 1
        r = t.w.get("/materialablage/katalog/meldungen?bereich=antraege")
        assert r.status_code == 302 and r.headers["Location"].endswith("/materialablage/bestand/antraege")
        import html as html_mod
        seite = html_mod.unescape(t.w.get("/materialablage/katalog/meldungen").get_data(as_text=True))
        assert '"bereich"' not in seite and "meldungen" in seite
        # Rückruf mit der neuen Nummer – vor der Bestätigung trifft er nicht, danach schon; die alte trifft nicht mehr.
        assert bestaetigen(t.w, aid).status_code == 200
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
        a1 = beantragen(t.p, t.k1, serial_no="AN-150").json["antrag"]["id"]
        beantragen(t.p, t.g1, manufactured_on="2023-08")
        assert bestaetigen(t.w, a1).status_code == 200
        f = t.adm.get(f"/api/admin/users/{t.k['pruefer_id']}/material-folgen").json
        assert f["antraege"] == 2, f
        assert t.adm.get(f"/api/admin/users/{t.k['wart_id']}/material-folgen").json["antraege"] == 1
        assert t.adm.get(f"/api/admin/users/{t.k['fuehrung_id']}/material-folgen").json["antraege"] == 0
        journal_sql = "SELECT id, entity, entity_id, user_name, action, before_json, after_json FROM mat_audit ORDER BY id"
        vorher = zeilen(t.app, journal_sql)
        assert t.adm.delete(f"/api/admin/users/{t.k['pruefer_id']}", headers=H).status_code == 200
        z = zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")
        assert [(x["created_by"], x["created_by_name"], x["resolved_by"], x["resolved_by_name"]) for x in z] == [
            (None, "pruefer", t.k["wart_id"], "wart"), (None, "pruefer", None, "")], z
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
    """Zeilen je mat_-Tabelle – ohne mat_item_set_slot (entfällt mit Schritt 26), mat_round_setprotokoll (kommt mit
    Schritt 27), mat_antrag_ohne_verwalter (kommt mit Schritt 29) und mat_lebenslauf (kommt mit Schritt 31); in den
    Altständen hier alle leer."""
    conn = sqlite3.connect(pfad)
    try:
        return {n: conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for (n,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat%' AND name NOT LIKE '%fts%' "
            "AND name NOT IN ('mat_item_set_slot', 'mat_round_setprotokoll', 'mat_antrag_ohne_verwalter', "
            "'mat_lebenslauf')")}
    finally:
        conn.close()


def test_migration_15():
    """Frisch: Version 15 (heute die Endversion), Tabelle, alle Trigger, der Artikeltrigger in der neuen Fassung. 14 →
    Ende (Tabelle und Trigger entfernt, Trigger aus Schritt 14 wieder angelegt): Daten unverändert, Trigger ersetzt,
    wirkt; zweiter Lauf ohne Änderung. 7 → 15 an einer Kopie (wenn angegeben): Zahlen wie 7 → 14, die Tabelle leer."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger, tabellen = _schema(pfad)
        assert version == endversion() and "mat_item_change" in tabellen, (version, tabellen)
        assert TRIGGER_NEU <= set(trigger) and "mat_item_change" in trigger["mat_item_stammdaten_fest"], trigger
        # Stand 14 nachstellen – samt den Triggern späterer Schritte, die mat_item_change lesen (Schritt 23).
        conn = sqlite3.connect(pfad)
        conn.execute("DROP TABLE mat_item_change")
        for n in TRIGGER_NEU | TRIGGER_23 | {"mat_item_produkt_fest"} | trigger_25(nur_antrag=True):
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
        assert version == endversion() and TRIGGER_NEU <= set(trigger), (version, trigger)
        assert "mat_item_change" in trigger["mat_item_stammdaten_fest"]
        nachher = _zahlen(pfad)
        assert nachher.pop("mat_item_change") == 0 and nachher == vorher
        conn = sqlite3.connect(pfad)
        assert models.migrieren(conn) == models.SCHEMA_VERSION >= 15
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_15(conn)
        models._schritt_16(conn)
        models._schritt_17(conn)
        models._schritt_23(conn)                   # ersetzt die Artikeltrigger wieder durch die Fassung aus 23
        models._schritt_24(conn)                   # und die zwei des Lebensendes durch die aus 24
        models._schritt_25(conn)                   # und die Antragstrigger durch die aus 25 (Seriennummern der Bestandteile)
        models._schritt_26(conn)                   # und die Stücklisten-Trigger durch die aus 26 (nur Text)
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
            assert v14 == "14" and v15 == endversion() and TRIGGER_NEU | TRIGGER_16 | TRIGGER_17 | TRIGGER_23 <= set(t15)
            z14, z15 = _zahlen(os.path.join(tmp14, "stroemis.db")), _zahlen(os.path.join(tmp15, "stroemis.db"))
            assert z15.pop("mat_item_change") == 0, (z14, z15)
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
        print("Migration 7 → Ende aus der Kopie bestanden.")
    else:
        print("Migration 7 → 15 übersprungen (MATERIAL_KOPIE_STAND_7 nicht gesetzt).")
    print("Migration 15 bestanden.")


def _schema_in(conn):
    return {r[0]: r[1] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")}


# --- 9. Oberfläche (statisch) ----------------------------------------------------------------------------------------

def test_oberflaeche_statisch():
    """material.js: Dialog „Bearbeiten“ mit schreibgeschütztem Block und grauem „Änderung beantragen“, offener Antrag als
    Hinweis; Antragsdialog mit Begründung und EINEM roten Knopf „Antrag senden“; Artikelseite: „Bearbeiten“ auch für
    Prüfer, „Änderung beantragen“ ohne Hilfetext darunter; Liste „Änderungsanträge“ mit Karten nur mit grauen
    Knöpfen, Rückfrage „Bestätigen“ als roter Hauptknopf, „Ablehnen“ endgültig (rot umrandet); Blase am Knopf im
    Bestand. Keine btn ghost. admin.js nennt die Anträge beim Löschen; CSS für Marke und Liste."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    admin = open(os.path.join(wurzel, "app/static/js/admin.js"), encoding="utf-8").read()
    dlg = js[js.index("function artikelDialog(a)"):js.index("/* --- Änderungsanträge")]
    assert "const gesperrt = fest || nurDirekt;" in dlg and "const nurDirekt = !(a.darf || {}).verwalten;" in dlg
    assert ('<button class="btn secondary small" type="button" id="ad-antrag">Änderung beantragen</button>' in dlg
            and "antragMoeglich(a)" in dlg and "offen.map(antragOffenHtml)" in dlg)
    assert dlg.count('class="btn"') == 1 and '<button class="btn" id="ad-ok" type="button">Speichern</button>' in dlg
    block = js[js.index("/* --- Änderungsanträge"):js.index("/* --- Artikel anlegen")]
    antrag_dlg = block[block.index("function antragDialog(a)"):]
    assert antrag_dlg.count('class="btn"') == 1 and '<button class="btn" id="aa-ok" type="button">Antrag senden</button>' in antrag_dlg
    assert 'id="aa-grund"' in antrag_dlg and "Begründung (Pflicht)" in antrag_dlg and "/antrag`" in antrag_dlg
    assert "wartet auf einen Materialwart des Ordners" in block and "Material-Verwaltung bestätigt" not in block
    seite = js[js.index("async function artikel()"):js.index("function artikelDialog(a)")]
    assert "const darfDirekt = Boolean(darf.verwalten || darf.pruefen)" in seite
    # Seit dem 27.10.2026 rechts neben der Überschrift „Stammdaten“ (Nachtrag 5), nicht mehr am Ende des Blocks; seit
    # UI/UX D5 im gemeinsamen Abschnittskopf (.abschnittskopf statt .mat-kastenkopf).
    assert ("<div class=\"abschnittskopf\"><h2>Stammdaten</h2>${antragMoeglich(a) ? '<button class=\"btn secondary small\" "
            "type=\"button\" data-act=\"antrag\">Änderung beantragen</button>' : \"\"}</div>") in seite
    karte = js[js.index("function antragKarte(x)"):js.index("function antragBestaetigenDialog")]
    assert 'class="btn secondary small" data-act="bestaetigen"' in karte and 'data-act="antrag-ablehnen"' in karte
    assert 'class="btn"' not in karte and "btn danger" not in karte and "x.entscheiden && geht" in karte
    best = js[js.index("function antragBestaetigenDialog"):js.index("function antragAblehnenDialog")]
    assert best.count('class="btn"') == 1 and '<button class="btn" id="ba-ok" type="button">Bestätigen</button>' in best
    abl = js[js.index("function antragAblehnenDialog"):js.index("function zuordnenDialog")]
    assert '<button class="btn danger" id="aa-ablehnen" type="button">Ablehnen</button>' in abl and 'class="btn"' not in abl
    assert "btn ghost" not in js
    zaehlen = js[js.index("async function antraegeZaehlen(el)"):]
    assert "zu_entscheiden" in zaehlen[:600] and '"99+"' in zaehlen[:600]
    assert "d.antraege_offen ? `<p class=\"notice\"><a href=\"/materialablage/bestand/antraege\">" in js
    for x in ("antrag_gestellt:", "antrag_bestaetigt:", "antrag_abgelehnt:", "beantragt_von:", "ablehnung:"):
        assert x in js, x
    assert '"Änderungsantrag behält", "Änderungsanträge behalten"' in admin
    for x in (".mat-mstatus.m-bestaetigt", ".mat-meldung.m-bestaetigt", ".mat-antrag-aenderungen", ".mat-antrag-offen"):
        assert x in css, x
    from app.material.services import beschriftung
    assert beschriftung.AKTION["antrag_bestaetigt"] == "Änderung bestätigt (Antrag)" and beschriftung.FELD["antrag"]
    print("Oberfläche (statisch) bestanden.")


# --- 10. Prüfung vom 21.10.2026 ----------------------------------------------------------------------------------------

def _pdf_text(data):
    import io
    from pypdf import PdfReader
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


def test_leser_ohne_inhalt():
    """Befund 1: Wer den Artikel nur liest (Führungskraft), sieht in Verlauf und Lebenslauf bei „Änderung beantragt“,
    „… bestätigt“ und „… abgelehnt“ weder Begründung, Antragsteller, Anmerkung noch Ablehnungsgrund, als Handelnden
    „(Person)“ – wie die Antragsansicht (inhalt false). Feld, alter und neuer Wert bleiben. Materialwart und Prüfer sehen
    alles."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        aid = beantragen(t.p, t.k1, serial_no="AN-L1", begruendung="Platzhalter Begründung L").json["antrag"]["id"]
        assert bestaetigen(t.w, aid, antwort="Platzhalter Anmerkung L").status_code == 200
        aid = beantragen(t.p, t.s1, serial_no="AN-L2", begruendung="Platzhalter Begründung M").json["antrag"]["id"]
        assert ablehnen(t.w, aid, antwort="Platzhalter Ablehnung M").status_code == 200
        geheim = ("Platzhalter Begründung", "Platzhalter Anmerkung", "Platzhalter Ablehnung")
        for iid in (t.k1, t.s1):
            f = lesen(t.f, iid)
            assert f["antraege"] == [] and not f["darf_antrag"]
            eintraege = [e for e in f["journal"] if e["action"].startswith("antrag_")]
            assert len(eintraege) == 2, eintraege
            for e in eintraege:
                assert e["user_name"] == "(Person)", e
                assert not {"begruendung", "beantragt_von", "anmerkung", "ablehnung"} & set(e["nachher"]), e
                assert not any(g in str(e) for g in geheim), e
            # Wer beantragen darf, sieht alles.
            for c in (t.w, t.p):
                voll = [e for e in lesen(c, iid)["journal"] if e["action"].startswith("antrag_")]
                assert {e["user_name"] for e in voll} == {"pruefer", "wart"}, voll
                assert any("begruendung" in e["nachher"] for e in voll)
        f = [e for e in lesen(t.f, t.k1)["journal"] if e["action"] == "antrag_bestaetigt"][0]
        assert (f["vorher"], f["nachher"]) == ({"serial_no": "AN-100"}, {"serial_no": "AN-L1", "antrag": f["nachher"]["antrag"]}), f
        abgelehnt = [e for e in lesen(t.f, t.s1)["journal"] if e["action"] == "antrag_abgelehnt"][0]
        assert abgelehnt["nachher"] == {"antrag": aid, "feld": "Seriennummer"}, abgelehnt
        # Lebenslauf: für die Führungskraft ohne, für den Materialwart mit Begründung und Namen.
        r = t.f.get(f"/materialablage/artikel/{t.k1}/lebenslauf.pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
        text = _pdf_text(r.data)
        assert "AN-L1" in text, text
        assert not any(g in text for g in geheim) and "beantragt von" not in text, text
        text = _pdf_text(t.w.get(f"/materialablage/artikel/{t.k1}/lebenslauf.pdf").data)
        assert "Platzhalter Begründung L" in text and "Platzhalter Anmerkung L" in text and "beantragt von" in text
        text = _pdf_text(t.f.get(f"/materialablage/artikel/{t.s1}/lebenslauf.pdf").data)
        assert "Platzhalter Ablehnung M" not in text
    print("Leser ohne Inhalt bestanden.")


def test_bescheid_nur_mit_recht():
    """Befund 2: Den Bescheid bekommt der Antragsteller nur, solange er den Artikel liest (Grund- oder Prüfrecht) – nach
    abgelaufener befristeter Prüffreigabe oder nach dem Verschieben in eine fremde Gliederung gar keinen; liest er ihn
    noch, wie bisher. Entscheiden die Materialwarte des Ordners, in dem der Artikel gerade liegt."""
    from datetime import date, timedelta
    from test_material import freigeben, neues_konto
    with post() as liste, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        ext, ext_id = neues_konto(t.app, "extern@example.org", None, mat_pruefer=True, urkundennummer="1012-9999")
        freigeben(t.adm, t.lager, ext_id, "pruefen", bis=(date.today() + timedelta(days=30)).isoformat())
        r = beantragen(ext, t.k1, serial_no="AN-EXT1")
        assert r.status_code == 201, r.get_json()
        aid = r.json["antrag"]["id"]
        # Mit Recht: Bescheid wie bisher.
        liste.clear()
        assert ablehnen(t.w, aid, antwort="Platzhalter Grund 1").status_code == 200
        assert [m[0] for m in liste] == ["extern@example.org"], liste
        aid = beantragen(ext, t.k1, serial_no="AN-EXT2").json["antrag"]["id"]
        sql(t.app, "UPDATE mat_folder_grant SET valid_until = ? WHERE user_id = ?",
            ((date.today() - timedelta(days=1)).isoformat(), ext_id))
        assert ext.get(f"/api/material/artikel/{t.k1}").status_code == 404
        liste.clear()
        with logzeilen(t.app):
            assert ablehnen(t.w, aid, antwort="Platzhalter Grund 2").status_code == 200
        assert liste == [], liste
        # Materialwart beantragt, der Artikel wandert in eine fremde Gliederung: Dort entscheidet deren Materialwart (hier
        # die Material-Verwaltung mit eigener Verwalterfreigabe an B); keine Mail mit deren Namen an den Antragsteller.
        freigeben(t.adm, t.gid_b, t.k["katalog_id"], "verwalten")
        aid = beantragen(t.w, t.s1, serial_no="AN-S1B").json["antrag"]["id"]
        lager_b = zeilen(t.app, "SELECT id FROM mat_folder WHERE name = 'Lager B'")[0]["id"]
        r = t.adm.post("/api/material/artikel/verschieben", headers=H, json={"ids": [t.s1], "folder_id": lager_b})
        assert r.status_code == 200, r.get_json()
        assert t.w.get(f"/api/material/artikel/{t.s1}").status_code == 404
        assert bestaetigen(t.w, aid).status_code == 404                     # liest ihn nicht mehr
        liste.clear()
        assert bestaetigen(t.mv, aid).status_code == 200
        assert liste == [] and item(t.app, t.s1)["serial_no"] == "AN-S1B", liste
        # Zurück im eigenen Bereich: wieder mit Bescheid.
        r = t.adm.post("/api/material/artikel/verschieben", headers=H, json={"ids": [t.s1], "folder_id": t.lager})
        assert r.status_code == 200, r.get_json()
        aid = beantragen(t.mv, t.s1, serial_no="AN-S1C").json["antrag"]["id"]
        liste.clear()
        assert bestaetigen(t.w, aid).status_code == 200
        assert [m[0] for m in liste] == ["katalog@example.org"] and "OG Musterstadt" in liste[0][2], liste
    print("Bescheid nur mit Recht bestanden.")


def test_trigger_16():
    """Befund 3: An der Schnittstelle vorbei lässt sich ein geprüfter Artikel weder per INSERT OR REPLACE ersetzen (mit
    und ohne Fremdschlüssel), noch umnummerieren, löschen oder auf ein anderes Produkt umhängen; die Materialart eines
    Produkts mit geprüften Artikeln bleibt, Produkte lassen sich nicht ersetzen. Ungeprüftes und derselbe Wert gehen;
    die App arbeitet wie bisher (Bearbeiten, Löschen eines ungeprüften Artikels, Anlegen)."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        # Ein Produkt nur mit einem ungeprüften Artikel – seine Materialart sperrt erst der Dienst, nicht die Datenbank.
        r = t.mv.post("/api/material/produkte", json={"category_id": t.ids["karabiner"], "manufacturer": "Testwerk",
                                                      "model": "Sonderteil Delta", "article_no": "SD-1",
                                                      "material_kind": "metall_hardware", "interval_months": 12})
        assert r.status_code == 201, r.get_json()
        ungeprueft = r.json["produkt"]["id"]
        neuer_artikel(t.w, ungeprueft, t.lager, serial_no="AN-D1")

        def geht_nicht(conn, befehl, args, text):
            try:
                conn.execute(befehl, args)
            except sqlite3.IntegrityError as e:
                assert text in str(e), (befehl, e)
                return
            raise AssertionError(befehl)

        def zeile(conn, tabelle, kennung):
            spalten = [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
            return spalten, dict(zip(spalten, conn.execute(f"SELECT * FROM {tabelle} WHERE id = ?", (kennung,)).fetchone()))

        for fk in (1, 0):
            conn = sqlite3.connect(pfad)
            conn.execute(f"PRAGMA foreign_keys = {fk}")
            try:
                spalten, alt = zeile(conn, "mat_item", t.k1)
                neu = dict(alt, serial_no="AN-REPLACE", manufactured_on="2001-01")
                for art in ("INSERT OR REPLACE", "REPLACE", "INSERT"):
                    geht_nicht(conn, f"{art} INTO mat_item ({','.join(spalten)}) VALUES ({','.join('?' * len(spalten))})",
                               [neu[s] for s in spalten], "nicht ersetzen")
                geht_nicht(conn, "UPDATE mat_item SET id = 99999 WHERE id = ?", (t.k1,), "Kennung nicht ändern")
                geht_nicht(conn, "DELETE FROM mat_item WHERE id = ?", (t.k1,), "aussondern statt löschen")
                geht_nicht(conn, "UPDATE mat_item SET product_id = ? WHERE id = ?", (t.ids["gurt"], t.k1), "Produkt eines")
                geht_nicht(conn, "UPDATE mat_item SET product_id = ? WHERE id = ?", (t.ids["hms"], t.s1), "Produkt eines")
                geht_nicht(conn, "UPDATE mat_product SET material_kind = 'metall_hardware' WHERE id = ?", (t.sonst,),
                           "Materialart")
                pspalten, palt = zeile(conn, "mat_product", t.sonst)
                geht_nicht(conn, f"INSERT OR REPLACE INTO mat_product ({','.join(pspalten)}) VALUES "
                           f"({','.join('?' * len(pspalten))})", [dict(palt, material_kind="metall_hardware")[s]
                                                                  for s in pspalten], "nicht ersetzen")
                geht_nicht(conn, "UPDATE mat_product SET id = 99999 WHERE id = ?", (t.sonst,), "Kennung nicht ändern")
                # Erlaubt: derselbe Wert, ein ungeprüfter Artikel, ein Produkt ohne geprüfte Artikel.
                conn.execute("UPDATE mat_item SET product_id = product_id, notes = 'Platzhalter' WHERE id = ?", (t.k1,))
                conn.execute("UPDATE mat_item SET product_id = ? WHERE id = ?", (t.ids["gurt"], t.neu1))
                conn.execute("UPDATE mat_product SET material_kind = 'sonstiges' WHERE id = ?", (ungeprueft,))
                conn.execute("UPDATE mat_product SET material_kind = material_kind WHERE id = ?", (t.sonst,))
            finally:
                conn.rollback()
                conn.close()
        assert (item(t.app, t.k1)["serial_no"], item(t.app, t.s1)["product_id"]) == ("AN-100", t.sonst)
        # Die App wie bisher: bearbeiten (schreibt product_id neu), Produktwechsel vor der Prüfung, löschen, anlegen.
        r = t.w.put(f"/api/material/artikel/{t.k1}", headers=H, json={"notes": "Platzhalter Bemerkung"})
        assert r.status_code == 200, r.get_json()
        r = t.w.put(f"/api/material/artikel/{t.k1}", headers=H, json={"product_id": t.ids["gurt"]})
        # Seit dem Feintuning (L2b Nr. 29): eigener Satz – das Produkt steht im Prüfprotokoll.
        assert r.status_code == 409 and "steht seit der ersten Prüfung fest" in r.json["error"], r.get_json()
        neu = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-T16")["id"]
        r = t.w.put(f"/api/material/artikel/{neu}", headers=H, json={"product_id": t.sonst})
        assert r.status_code == 200 and item(t.app, neu)["product_id"] == t.sonst, r.get_json()
        assert t.w.delete(f"/api/material/artikel/{neu}", headers=H).status_code == 200
        assert not zeilen(t.app, "SELECT id FROM mat_item WHERE id = ?", (neu,))
        r = t.mv.put(f"/api/material/produkte/{t.sonst}", headers=H, json={"material_kind": "metall_hardware"})
        assert r.status_code == 409 and "Materialart" in r.json["error"], r.get_json()
    print("Trigger 16 bestanden.")


def test_migration_16():
    """Schritt 16: frisch Version 16 mit allen Triggern; 15 → 16 (neue Trigger entfernt, mat_item_stammdaten_fest in der
    Fassung aus 15): Daten unverändert, Trigger da und ersetzt, zweiter Lauf ohne Änderung. 7 → 16 an einer Kopie (wenn angegeben): Zahlen wie 7 → 15, Trigger greifen an einem
    geprüften Artikel der Kopie."""
    from app.material import models
    bis16 = bis_schritt(16)                       # seit Schritt 17 läuft eine frische Datenbank weiter – hier bis 16
    with tempfile.TemporaryDirectory() as tmp:
        bis16(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger, _ = _schema(pfad)
        assert version == "16" and TRIGGER_16 <= set(trigger), (version, trigger)
        assert "c.old_value IS NOT NULL" in trigger["mat_item_stammdaten_fest"]
        conn = sqlite3.connect(pfad)
        for n in TRIGGER_16 | {"mat_item_stammdaten_fest"}:
            conn.execute(f"DROP TRIGGER {n}")
        conn.execute(models.TRIGGER_15_ARTIKEL[0])          # die Fassung aus Schritt 15
        conn.execute("UPDATE mat_meta SET wert = '15' WHERE schluessel = 'schema_version'")
        conn.commit()
        conn.close()
        vorher = _zahlen(pfad)
        bis16(make_app, tmp)
        version, trigger2, _ = _schema(pfad)
        assert version == "16" and trigger2 == trigger and _zahlen(pfad) == vorher
        conn = sqlite3.connect(pfad)
        assert bis16(models.migrieren, conn) == 16
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_16(conn)
        assert conn.total_changes == n and _schema_in(conn) == trigger
        conn.rollback()
        conn.close()
    if KOPIE_STAND_7 and os.path.exists(KOPIE_STAND_7):
        with tempfile.TemporaryDirectory() as tmp15, tempfile.TemporaryDirectory() as tmp16:
            for d in (tmp15, tmp16):
                shutil.copyfile(KOPIE_STAND_7, os.path.join(d, "stroemis.db"))
            bis_schritt(15)(make_app, tmp15)
            bis16(make_app, tmp16)
            v15, t15, _ = _schema(os.path.join(tmp15, "stroemis.db"))
            v16, t16, _ = _schema(os.path.join(tmp16, "stroemis.db"))
            assert (v15, v16) == ("15", "16") and set(t16) == set(t15) | TRIGGER_16, (v15, v16)
            assert _zahlen(os.path.join(tmp15, "stroemis.db")) == _zahlen(os.path.join(tmp16, "stroemis.db"))
            conn = sqlite3.connect(os.path.join(tmp16, "stroemis.db"))
            conn.execute("PRAGMA foreign_keys = 0")
            try:
                geprueft = conn.execute("SELECT item_id FROM mat_inspection WHERE completed_at IS NOT NULL LIMIT 1").fetchone()
                if geprueft:
                    for befehl in ("DELETE FROM mat_item WHERE id = ?", "UPDATE mat_item SET id = -5 WHERE id = ?",
                                   "UPDATE mat_item SET product_id = -5 WHERE id = ?"):
                        try:
                            conn.execute(befehl, geprueft)
                            raise AssertionError(f"Trigger fehlt: {befehl}")
                        except sqlite3.IntegrityError:
                            pass
            finally:
                conn.rollback()
                conn.close()
        print("Migration 7 → 16 aus der Kopie bestanden.")
    else:
        print("Migration 7 → 16 übersprungen (MATERIAL_KOPIE_STAND_7 nicht gesetzt).")
    print("Migration 16 bestanden.")


def test_rueckruf_hinweis():
    """Befund 4: Trifft ein laufender Rückruf den Artikel über seine Seriennummer, nennen Antrag (Liste, Artikel) ihn
    unter „rueckruf.nicht_mehr“, ein Rückruf, der erst die neue Nummer träfe, unter „neu“; einer für alle Artikel des
    Produkts gar nicht. Beim Bestätigen vermerkt das Journal beide; danach trägt der Antrag keinen Hinweis mehr."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        rueckrufe = {}
        for titel, serien in (("Platzhalter-Rückruf alt", "AN-100\nAN-999"), ("Platzhalter-Rückruf neu", "AN-100-K"),
                              ("Platzhalter-Rückruf alle", "")):
            r = t.mv.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", headers=H,
                          json={"title": titel, "serials": serien, "mail": False})
            assert r.status_code == 201, r.get_json()
            rueckrufe[titel] = r.json["rueckruf"]["id"]
        vorher = {x["title"]: x["alle"] for x in lesen(t.w, t.k1)["rueckrufe"]}
        assert vorher == {"Platzhalter-Rückruf alt": False, "Platzhalter-Rückruf alle": True}, vorher
        aid = beantragen(t.p, t.k1, serial_no="AN-100-K").json["antrag"]["id"]
        erwartet = {"nicht_mehr": [{"id": rueckrufe["Platzhalter-Rückruf alt"], "title": "Platzhalter-Rückruf alt"}],
                    "neu": [{"id": rueckrufe["Platzhalter-Rückruf neu"], "title": "Platzhalter-Rückruf neu"}],
                    "wieder_offen": []}
        karte = [x for x in t.w.get("/api/material/antraege").json["antraege"] if x["id"] == aid][0]
        assert karte["rueckruf"] == erwartet, karte["rueckruf"]
        assert lesen(t.w, t.k1)["antraege"][0]["rueckruf"] == erwartet
        # Herstelldatum und ein Artikel ohne passende Rückrufe: leer.
        a2 = beantragen(t.p, t.s1, serial_no="AN-S1X").json["antrag"]["id"]
        x = [y for y in t.w.get("/api/material/antraege").json["antraege"] if y["id"] == a2][0]
        assert x["rueckruf"] == {"nicht_mehr": [], "neu": [], "wieder_offen": []}, x
        assert bestaetigen(t.w, aid).status_code == 200
        j = journal(t.app, t.k1, "antrag_bestaetigt")[-1]["nachher"]
        assert j["rueckruf_nicht_mehr"] == [f"Platzhalter-Rückruf alt (Nr. {rueckrufe['Platzhalter-Rückruf alt']})"], j
        assert j["rueckruf_neu"] == [f"Platzhalter-Rückruf neu (Nr. {rueckrufe['Platzhalter-Rückruf neu']})"], j
        nachher = sorted(x["title"] for x in lesen(t.w, t.k1)["rueckrufe"])
        assert nachher == ["Platzhalter-Rückruf alle", "Platzhalter-Rückruf neu"], nachher
        erledigt = [y for y in t.w.get("/api/material/antraege?status=alle").json["antraege"] if y["id"] == aid][0]
        assert erledigt["rueckruf"] is None
        # Ohne Rückruf an der Nummer: kein Vermerk.
        assert bestaetigen(t.w, a2).status_code == 200
        j = journal(t.app, t.s1, "antrag_bestaetigt")[-1]["nachher"]
        assert "rueckruf_nicht_mehr" not in j and "rueckruf_neu" not in j, j
        from app.material.services import beschriftung
        assert beschriftung.FELD["rueckruf_nicht_mehr"] == "Rückruf trifft ihn nicht mehr"
    print("Rückruf-Hinweis bestanden.")


def test_sammelprotokoll_vormals():
    """Befund 6: Hat ein bestätigter Antrag die Seriennummer nach dem Einzelprotokoll ersetzt, nennt die Zeile des
    Sammelprotokolls „vormals <alte Nummer> (Änderungsantrag Nr. …)“ – nicht bei einer Änderung vor der Prüfung im
    Durchgang und nicht bei unverändertem Artikel; beim Produkt ebenso „vormals <Produkt> …“ (seit dem 24.10.2026).
    Einzelprotokoll und ein schon festgeschriebenes Sammelprotokoll bleiben Byte für Byte, wie sie sind."""
    import hashlib
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        hms2 = t.mv.post("/api/material/produkte", json={"category_id": t.ids["karabiner"], "manufacturer": "Testwerk",
                                                         "model": "HMS Epsilon", "article_no": "HE-1",
                                                         "material_kind": "metall_hardware", "interval_months": 12}).json["produkt"]["id"]
        kiste = t.w.post("/api/material/ordner", json={"name": "Kiste", "kind": "standort", "parent_id": t.gid}).json["ordner"]["id"]
        a = neuer_artikel(t.w, t.ids["hms"], kiste, serial_no="AN-ALT-1", manufactured_on="2024-01")["id"]
        b = neuer_artikel(t.w, t.ids["hms"], kiste, serial_no="AN-ALT-2", manufactured_on="2024-01")["id"]
        c = neuer_artikel(t.w, t.ids["hms"], kiste, serial_no="AN-ALT-3", manufactured_on="2024-01")["id"]
        # b: vor dem Durchgang geprüft und umbenannt – sein Protokoll im Durchgang nennt schon die neue Nummer.
        pruefen(t.p, b)
        ab = beantragen(t.p, b, serial_no="AN-NEU-2").json["antrag"]["id"]
        assert bestaetigen(t.w, ab).status_code == 200
        rid = t.p.post("/api/material/durchgaenge", json={"folder_id": kiste, "titel": "Platzhalter-Durchgang"}).json["durchgang"]["id"]
        for iid in (a, b, c):
            pruefen(t.p, iid)
        pa = zeilen(t.app, "SELECT id FROM mat_inspection WHERE item_id = ? AND round_id = ?", (a, rid))[0]["id"]
        pdf1 = t.w.get(f"/materialablage/pruefung/{pa}/pdf").data
        aa = beantragen(t.p, a, serial_no="AN-NEU-1", product_id=hms2).json["antrag"]["id"]
        assert bestaetigen(t.w, aa).status_code == 200
        assert t.w.get(f"/materialablage/pruefung/{pa}/pdf").data == pdf1 and "AN-ALT-1" in _pdf_text(pdf1)
        assert t.p.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
        r = t.w.get(f"/materialablage/durchgang/{rid}/sammelprotokoll")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
        text = " ".join(_pdf_text(r.data).split())
        assert "AN-NEU-1" in text and f"vormals AN-ALT-1 (Änderungsantrag Nr. {aa})" in text, text
        assert f"vormals Testwerk HMS Beta (Änderungsantrag Nr. {aa})" in text and "HMS Epsilon" in text, text
        assert "AN-NEU-2" in text and "vormals AN-ALT-2" not in text and "AN-ALT-3" in text
        assert text.count("vormals") == 2, text
        # Festgeschrieben: Ein späterer Antrag ändert das Sammelprotokoll nicht mehr.
        summe = hashlib.sha256(r.data).hexdigest()
        a3 = beantragen(t.p, c, serial_no="AN-NEU-3").json["antrag"]["id"]
        assert bestaetigen(t.w, a3).status_code == 200
        r = t.w.get(f"/materialablage/durchgang/{rid}/sammelprotokoll")
        assert hashlib.sha256(r.data).hexdigest() == summe and "vormals AN-ALT-3" not in _pdf_text(r.data)
        from app.material.services import protokoll
        with t.app.app_context():
            assert protokoll._vormals(c, zeilen(t.app, "SELECT id FROM mat_inspection WHERE item_id = ? AND round_id = ?",
                                                (c, rid))[0]["id"], "AN-NEU-3") == ("AN-ALT-3", a3)
        ziel = os.environ.get("SAMMELPROTOKOLL_ABLAGE")       # für bin/st-vera (PDF/A) – nur, wenn angegeben
        if ziel:
            with open(ziel, "wb") as fh:
                fh.write(r.data)
    print("Sammelprotokoll „vormals“ bestanden.")


def test_nachtragen_nach_entfernen():
    """Befund 5, entschieden am 21.10.2026; seit dem 24.10.2026 (E3) für alle: Ein leeres Herstelldatum trägt nach der
    ersten Prüfung niemand direkt nach – auch die Altfälle (Stand 16, _altbestand_16: per Antrag entfernt) nicht; PUT 409,
    ein Antrag auf einen neuen Wert geht und wird bestätigt. Der Trigger hält dasselbe an der Schnittstelle vorbei; ein
    Artikel ohne je ein Herstelldatum ebenso."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = _altbestand_16(tmp)
        make_app(tmp)                                                  # 16 → Ende
        assert item(t.app, t.k1)["manufactured_on"] is None
        a = lesen(t.w, t.k1)
        assert a["stammdaten_fest"] and "herstellung_nachtragbar" not in a
        for iid in (t.k1, t.k2):
            r = t.w.put(f"/api/material/artikel/{iid}", headers=H, json={"manufactured_on": "2010-01"})
            assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
            assert item(t.app, iid)["manufactured_on"] is None
        # An der Schnittstelle vorbei: ebenso abgewiesen.
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            for iid in (t.k1, t.k2):
                try:
                    conn.execute("UPDATE mat_item SET manufactured_on = '2010-01' WHERE id = ?", (iid,))
                    raise AssertionError("Trigger lässt Nachtragen zu")
                except sqlite3.IntegrityError as e:
                    assert "seit seiner ersten Prüfung fest" in str(e), e
        finally:
            conn.rollback()
            conn.close()
        # Per Antrag geht es.
        r = beantragen(t.w, t.k1, manufactured_on="2023-06", begruendung="Platzhalter Etikett gefunden")
        assert r.status_code == 201, r.get_json()
        assert bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        assert item(t.app, t.k1)["manufactured_on"] == "2023-06"
    print("Nachtragen nach Entfernen bestanden.")


def test_oberflaeche_pruefung():
    """Oberfläche zu Befund 4: Antragsdialog nennt einen laufenden Rückruf mit Seriennummernliste, Karte und Rückfrage
    „Bestätigen“ nennen x.rueckruf; Journal-Beschriftungen für die beiden neuen Felder. Knopfregel unverändert."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    block = js[js.index("/* --- Änderungsanträge"):js.index("/* --- Artikel anlegen")]
    assert "const antragRueckruf = (x) =>" in block and "nach der Änderung ${raus.length > 1" in block
    antrag_dlg = block[block.index("function antragDialog(a)"):]
    assert "(a.rueckrufe || []).filter((r) => !r.alle)" in antrag_dlg and "betroffen – nach einer Änderung der Seriennummer" in antrag_dlg
    assert antrag_dlg.count('class="btn"') == 1
    karte = js[js.index("function antragKarte(x)"):js.index("function antragBestaetigenDialog")]
    assert "${offen ? antragRueckruf(x) : \"\"}" in karte and 'class="btn"' not in karte
    best = js[js.index("function antragBestaetigenDialog"):js.index("function antragAblehnenDialog")]
    assert "${antragRueckruf(x)}" in best and best.count('class="btn"') == 1
    assert 'rueckruf_nicht_mehr: "Rückruf trifft ihn nicht mehr", rueckruf_neu: "Rückruf trifft ihn jetzt"' in js
    tpl = open(os.path.join(wurzel, "app/material/templates/material/pdf/sammelprotokoll.html"), encoding="utf-8").read()
    assert "{% if a.seriennummer_vormals %}" in tpl and "{% if a.produkt_vormals %}" in tpl
    print("Oberfläche (Prüfung) bestanden.")


# --- 11. Entscheidungen vom 21.10.2026 zur Prüfung: zurückziehen, Herstelldatum nicht entfernen, Schritt 17 ------------

def zurueckziehen(c, aid):
    return c.post(f"/api/material/antraege/{aid}/zurueckziehen", headers=H, json={})


def _altbestand_16(tmp):
    """Ein Stand 16 mit Anträgen, wie es ihn auf dev geben kann: aufbau unter Schemaversion 16, dazu Karabiner k3
    (AN-300, 05/2023, geprüft). k1 (Metall) hat sein Herstelldatum per bestätigtem Antrag verloren (bis Schritt 16
    möglich), k3 hat einen offenen Antrag aufs Entfernen, k2 einen offenen auf eine Herstellernummer. Die Antragszeilen
    entstehen per SQL so, wie die Dienste von damals sie schrieben – die Trigger aus Schritt 16 sind dabei aktiv."""
    def bau():
        t = aufbau(tmp)
        t.k3 = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-300", manufactured_on="2023-05")["id"]
        pruefen(t.p, t.k3)
        return t
    t = bis_schritt(16)(bau)
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    try:
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "16"

        def neu(iid, feld, alt, wert):
            return conn.execute(
                "INSERT INTO mat_item_change (item_id, field, old_value, new_value, reason, created_by, created_by_name, "
                "created_at) VALUES (?,?,?,?,'Platzhalter alt',?,'wart','2026-10-21T08:00:00+00:00')",
                (iid, feld, alt, wert, t.k["wart_id"])).lastrowid
        t.a_weg = neu(t.k1, "manufactured_on", "2024-03", None)
        conn.execute("UPDATE mat_item_change SET status = 'bestaetigt', resolved_by = ?, resolved_by_name = 'katalog', "
                     "resolved_at = '2026-10-21T09:00:00+00:00' WHERE id = ?", (t.k["katalog_id"], t.a_weg))
        conn.execute("UPDATE mat_item SET manufactured_on = NULL WHERE id = ?", (t.k1,))
        assert conn.execute("SELECT applied_at FROM mat_item_change WHERE id = ?", (t.a_weg,)).fetchone()[0]
        t.a_offen = neu(t.k3, "manufactured_on", "2023-05", None)
        t.a_sn = neu(t.k2, "serial_no", t.str_nr, "HN-ALT")
        conn.commit()
    finally:
        conn.close()
    return t


def test_zurueckziehen():
    """GEÄNDERT am 21.10.2026: Den offenen Antrag zieht der Antragsteller selbst zurück – nur seinen eigenen (sonst 404,
    auch für Materialwart und Material-Verwaltung), nur offen (sonst 409), nur solange er den Artikel liest (sonst 404).
    Stand „zurückgezogen“ mit ihm als Handelndem, keine Antwort, keine Mail; Journal „Änderungsantrag zurückgezogen“ (für
    Leser ohne Namen), auch im Lebenslauf; danach weder bestätigen noch ablehnen; die Zahl der zu entscheidenden sinkt,
    unter „erledigt“ steht er; neu beantragen geht. Der Trigger lässt das Zurückziehen nur dem Antragsteller."""
    with post() as liste, tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        aid = beantragen(t.p, t.k1, serial_no="AN-150").json["antrag"]["id"]
        aid2 = beantragen(t.w, t.g1, manufactured_on="2023-12").json["antrag"]["id"]
        assert t.w.get("/api/material/antraege").json["zu_entscheiden"] == 2
        mails = len(liste)
        for c in (t.w, t.mv, t.adm, t.f):
            r = zurueckziehen(c, aid)
            assert r.status_code == 404 and r.json["error"] == "Änderungsantrag nicht gefunden.", r.get_json()
        assert zurueckziehen(t.k["nutzer"], aid).status_code in (403, 404)
        assert zurueckziehen(t.p, 999999).status_code == 404
        assert antraege(t.app, t.k1)[0]["status"] == "offen"
        r = zurueckziehen(t.p, aid)
        assert r.status_code == 200 and (r.json["antrag"]["status"], r.json["antrag"]["status_text"]) == (
            "zurueckgezogen", "zurückgezogen"), r.get_json()
        z = antraege(t.app, t.k1)[0]
        assert (z["status"], z["resolved_by"], z["resolved_by_name"], z["answer"], z["applied_at"]) == (
            "zurueckgezogen", t.k["pruefer_id"], "pruefer", "", None) and z["resolved_at"], z
        assert item(t.app, t.k1)["serial_no"] == "AN-100" and len(liste) == mails
        j = journal(t.app, t.k1, "antrag_zurueckgezogen")
        assert len(j) == 1 and j[0]["user_name"] == "pruefer" and j[0]["vorher"] is None, j
        assert j[0]["nachher"] == {"antrag": aid, "feld": "Seriennummer"}, j
        # Endzustand: kein zweites Mal, weder bestätigen noch ablehnen.
        r = zurueckziehen(t.p, aid)
        assert r.status_code == 409 and "schon entschieden" in r.json["error"], r.get_json()
        for f in (bestaetigen, ablehnen):
            assert f(t.w, aid, antwort="Platzhalter").status_code == 409
        # Zähler, Listen, Artikel.
        d = t.w.get("/api/material/antraege").json
        assert d["zu_entscheiden"] == 1 and [x["id"] for x in d["antraege"]] == [aid2]
        erl = t.w.get("/api/material/antraege?status=erledigt").json["antraege"]
        assert [(x["id"], x["status"]) for x in erl] == [(aid, "zurueckgezogen")], erl
        assert [(x["id"], x["status"]) for x in t.p.get("/api/material/antraege?status=alle").json["antraege"]] == [
            (aid, "zurueckgezogen")]
        assert lesen(t.p, t.k1)["antraege"] == [] and [(x["id"], x["eigen"]) for x in lesen(t.p, t.g1)["antraege"]] == [
            (aid2, False)]
        assert [(x["id"], x["eigen"]) for x in lesen(t.w, t.g1)["antraege"]] == [(aid2, True)]
        assert beantragen(t.p, t.k1, serial_no="AN-151").status_code == 201
        # Leser: ohne Namen; Lebenslauf nennt den Eintrag.
        e = [x for x in lesen(t.f, t.k1)["journal"] if x["action"] == "antrag_zurueckgezogen"]
        assert len(e) == 1 and e[0]["user_name"] == "(Person)", e
        text = _pdf_text(t.w.get(f"/materialablage/artikel/{t.k1}/lebenslauf.pdf").data)
        assert "Änderungsantrag zurückgezogen" in " ".join(text.split()), text
        # Materialwart und Material-Verwaltung ziehen ihre eigenen zurück.
        assert zurueckziehen(t.w, aid2).status_code == 200
        aid3 = beantragen(t.mv, t.g1, manufactured_on="2023-12").json["antrag"]["id"]
        assert zurueckziehen(t.mv, aid3).status_code == 200 and item(t.app, t.g1)["manufactured_on"] == "2024-01"
        # Wer den Artikel nicht mehr liest (in eine fremde Gliederung verschoben): 404 – wie in seiner Liste.
        aid4 = beantragen(t.p, t.s1, serial_no="AN-S7").json["antrag"]["id"]
        heimat = item(t.app, t.s1)["folder_id"]
        sql(t.app, "UPDATE mat_item SET folder_id = ? WHERE id = ?", (item(t.app, t.fb)["folder_id"], t.s1))
        assert zurueckziehen(t.p, aid4).status_code == 404
        sql(t.app, "UPDATE mat_item SET folder_id = ? WHERE id = ?", (heimat, t.s1))
        assert zurueckziehen(t.p, aid4).status_code == 200
        # Trigger: zurückziehen nur mit der Kennung des Antragstellers, ohne Antwort; Kontolöschen danach geht.
        aid5 = beantragen(t.p, t.s1, serial_no="AN-S8").json["antrag"]["id"]
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            for wer, antwort in ((t.k["wart_id"], ""), (None, ""), (t.k["pruefer_id"], "Platzhalter")):
                try:
                    conn.execute("UPDATE mat_item_change SET status = 'zurueckgezogen', resolved_by = ?, answer = ?, "
                                 "resolved_by_name = 'x', resolved_at = 'x' WHERE id = ?", (wer, antwort, aid5))
                    raise AssertionError((wer, antwort))
                except sqlite3.IntegrityError as e:
                    assert "nur der Antragsteller" in str(e), e
            conn.execute("UPDATE mat_item_change SET created_by = NULL, resolved_by = NULL WHERE id = ?", (aid,))
            try:
                conn.execute("UPDATE mat_item_change SET status = 'offen', resolved_at = NULL WHERE id = ?", (aid,))
                raise AssertionError("wieder offen")
            except sqlite3.IntegrityError as e:
                assert ANTRAG_FEST in str(e), e
            conn.commit()
        finally:
            conn.close()
    print("Zurückziehen bestanden.")


def test_herstellung_nicht_entfernen():
    """GEÄNDERT am 21.10.2026: Das Herstelldatum lässt sich nach der ersten Prüfung nicht entfernen, auch nicht per Antrag
    – bei jeder Materialart; ändern per Antrag geht weiter. Der Dienst weist herstellung_entfernen und ein leeres Datum
    ab (beim Bearbeiten und im Antrag), die Datenbank einen Antrag mit leerem neuem Herstelldatum und das Leeren des
    Feldes. Vor der ersten Prüfung bleibt das Feld frei (entfernen geht); danach nachtragen nur per Antrag (E3)."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        for iid in (t.k1, t.g1):
            r = beantragen(t.w, iid, herstellung_entfernen=True)
            assert r.status_code == 400 and r.json["error"].startswith("Das Herstelldatum lässt sich nicht entfernen"), (
                r.get_json())
            r = t.w.put(f"/api/material/artikel/{iid}", headers=H, json={"manufactured_on": None})
            assert r.status_code in (400, 409), r.get_json()
            assert item(t.app, iid)["manufactured_on"] is not None
        assert antraege(t.app, t.k1) == [] and antraege(t.app, t.g1) == []
        r = beantragen(t.w, t.k1, manufactured_on="")
        assert r.status_code == 400 and HERST_BLEIBT in r.json["error"], r.get_json()
        # Ändern geht.
        r = beantragen(t.p, t.k1, manufactured_on="2024-01")
        assert r.status_code == 201 and bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        assert item(t.app, t.k1)["manufactured_on"] == "2024-01"
        # Vor der ersten Prüfung frei: entfernen; danach nachtragen nur per Antrag.
        r = t.w.put(f"/api/material/artikel/{t.neu1}", headers=H, json={"manufactured_on": "2024-04"})
        assert r.status_code == 200, r.get_json()
        r = t.w.put(f"/api/material/artikel/{t.neu1}", headers=H, json={"manufactured_on": None})
        assert r.status_code == 200 and item(t.app, t.neu1)["manufactured_on"] is None, r.get_json()
        pruefen(t.p, t.neu1)
        r = t.w.put(f"/api/material/artikel/{t.neu1}", headers=H, json={"manufactured_on": "2024-04"})
        assert r.status_code == 409 and item(t.app, t.neu1)["manufactured_on"] is None, r.get_json()
        r = beantragen(t.w, t.neu1, manufactured_on="2024-04")
        assert r.status_code == 201 and bestaetigen(t.w, r.json["antrag"]["id"]).status_code == 200
        assert item(t.app, t.neu1)["manufactured_on"] == "2024-04"
    print("Herstelldatum nicht entfernen bestanden.")


def test_migration_17():
    """Schritt 17: frisch (heute die Endversion), CHECK mit „zurückgezogen“, alle Trigger. 16 → Ende an einem Stand 16 mit
    Anträgen (_altbestand_16): alle Zeilen und Kennungen gleich, AUTOINCREMENT-Stand gleich (die nächste Kennung liegt
    darüber), Zahlen aller Tabellen gleich, Trigger = Stand 16 + die der späteren Schritte, mat_item_stammdaten_fest
    ersetzt; zweiter Lauf ohne Änderung. Danach: der alte offene Antrag aufs Entfernen lässt sich nicht bestätigen
    (Dienst 409, Trigger), nur ablehnen oder zurückziehen; der offene auf die Herstellernummer wird bestätigt. 7 → Ende an
    einer Kopie (wenn angegeben): Tabelle leer und umgebaut, Trigger greifen."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger, _ = _schema(pfad)
        assert version == endversion() and TRIGGER_17 | TRIGGER_NEU | TRIGGER_16 | TRIGGER_23 <= set(trigger), trigger
        assert "'zurueckgezogen'" in _tabelle_sql(pfad)
        assert "NEW.manufactured_on IS NOT OLD.manufactured_on AND NEW.manufactured_on IS NULL" in trigger["mat_item_stammdaten_fest"]
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = _altbestand_16(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        v16, t16, _ = _schema(pfad)
        assert v16 == "16" and "'zurueckgezogen'" not in _tabelle_sql(pfad)
        alt = zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")
        seq = zeilen(t.app, "SELECT seq FROM sqlite_sequence WHERE name = 'mat_item_change'")
        vorher = _zahlen(pfad)
        make_app(tmp)
        v17, t17, _ = _schema(pfad)
        # Schritt 18: keine Trigger; 19: die zwei des Mailfehler-Protokolls; 21: die der Sets; 23: die Gruppe; 25: die der
        # Seriennummern der Bestandteile.
        # 26: die Wächter des Rückbaus statt der entfallenen Set-Trigger; 30: Kennungen und Kontoverweise; 31: Lebensläufe.
        neu_26, weg_26 = trigger_26()
        erwartet = (set(t16) | TRIGGER_17 | TRIGGER_19 | trigger_21() | TRIGGER_23 | trigger_25() | neu_26 | trigger_27()
                    | trigger_30() | trigger_31() | trigger_32()) - weg_26
        assert v17 == endversion() and set(t17) == erwartet, set(t17) ^ erwartet
        assert t17["mat_item_stammdaten_fest"] != t16["mat_item_stammdaten_fest"]
        assert t17["mat_item_antrag_angewendet"] != t16["mat_item_antrag_angewendet"]          # seit Schritt 23 alle Felder
        assert "'zurueckgezogen'" in _tabelle_sql(pfad) and "'purchased_on'" in _tabelle_sql(pfad)
        # Seit Schritt 25 dazu component_id, stueck und component_label (leer) – die alten Spalten unverändert.
        assert [{k: r[k] for k in alt[0]} for r in zeilen(t.app, "SELECT * FROM mat_item_change ORDER BY id")] == alt \
            and len(alt) == 3
        assert zeilen(t.app, "SELECT seq FROM sqlite_sequence WHERE name = 'mat_item_change'") == seq
        # Schritt 19 legt mat_mail_fehler (leer) an – sonst keine Zeile anders.
        assert _zahlen(pfad) == dict(vorher, mat_mail_fehler=0)
        indizes = {r["name"] for r in zeilen(t.app, "SELECT name FROM sqlite_master WHERE type = 'index' "
                                                    "AND tbl_name = 'mat_item_change' AND sql IS NOT NULL")}
        assert indizes == {"ux_mat_item_change_offen", "idx_mat_item_change_item", "idx_mat_item_change_status",
                           "idx_mat_item_change_antragsteller", "idx_mat_item_change_entscheider",
                           "idx_mat_item_change_gruppe"}, indizes
        conn = sqlite3.connect(pfad)
        assert models.migrieren(conn) == models.SCHEMA_VERSION
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_17(conn)
        models._schritt_23(conn)
        models._schritt_24(conn)
        models._schritt_25(conn)
        models._schritt_26(conn)
        assert conn.total_changes == n and _schema_in(conn) == t17
        conn.rollback()
        # Der alte offene Antrag aufs Entfernen: auch an der Schnittstelle vorbei nicht zu bestätigen.
        try:
            conn.execute("UPDATE mat_item_change SET status = 'bestaetigt', resolved_by_name = 'x', resolved_at = 'x' "
                         "WHERE id = ?", (t.a_offen,))
            raise AssertionError("Entfernen bestätigt")
        except sqlite3.IntegrityError as e:
            assert HERST_BLEIBT in str(e), e
        finally:
            conn.rollback()
            conn.close()
        lst = {x["id"]: x for x in t.w.get("/api/material/antraege").json["antraege"]}
        assert (lst[t.a_offen]["entfernen"], lst[t.a_offen]["aenderungen"][0]["neu"], lst[t.a_sn]["entfernen"]) == (
            True, None, False)
        r = bestaetigen(t.w, t.a_offen)
        assert r.status_code == 409 and "nur noch ablehnen" in r.json["error"], r.get_json()
        assert item(t.app, t.k3)["manufactured_on"] == "2023-05"
        assert zurueckziehen(t.w, t.a_offen).status_code == 200
        assert bestaetigen(t.w, t.a_sn).status_code == 200 and item(t.app, t.k2)["serial_no"] == "HN-ALT"
        neu = beantragen(t.p, t.k3, serial_no="AN-301").json["antrag"]["id"]
        assert neu > max(x["id"] for x in alt)
    if KOPIE_STAND_7 and os.path.exists(KOPIE_STAND_7):
        with tempfile.TemporaryDirectory() as tmp17:
            shutil.copyfile(KOPIE_STAND_7, os.path.join(tmp17, "stroemis.db"))
            make_app(tmp17)
            v17, t17, _ = _schema(os.path.join(tmp17, "stroemis.db"))
            assert v17 == endversion() and TRIGGER_17 | TRIGGER_23 <= set(t17), v17
            assert _zahlen(os.path.join(tmp17, "stroemis.db"))["mat_item_change"] == 0
            assert "'zurueckgezogen'" in _tabelle_sql(os.path.join(tmp17, "stroemis.db"))
            conn = sqlite3.connect(os.path.join(tmp17, "stroemis.db"))
            try:
                geprueft = conn.execute("SELECT i.id FROM mat_item i JOIN mat_inspection x ON x.item_id = i.id "
                                        "WHERE x.completed_at IS NOT NULL AND i.manufactured_on IS NOT NULL LIMIT 1").fetchone()
                if geprueft:
                    try:
                        conn.execute("UPDATE mat_item SET manufactured_on = NULL WHERE id = ?", geprueft)
                        raise AssertionError("Trigger fehlt")
                    except sqlite3.IntegrityError:
                        pass
            finally:
                conn.rollback()
                conn.close()
        print("Migration 7 → Ende aus der Kopie bestanden.")
    else:
        print("Migration 7 → 17 übersprungen (MATERIAL_KOPIE_STAND_7 nicht gesetzt).")
    print("Migration 17 bestanden.")


def _tabelle_sql(pfad):
    conn = sqlite3.connect(pfad)
    try:
        return conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'mat_item_change'").fetchone()[0]
    finally:
        conn.close()


def test_oberflaeche_17():
    """Oberfläche zu den Entscheidungen vom 21.10.2026 zur Prüfung: Antragsdialog ohne „Herstelldatum entfernen“; offener
    eigener Antrag mit grauem „Antrag zurückziehen“ (Artikelseite und Dialog „Bearbeiten“) und Rückfrage; in der Liste
    „Zurückziehen“ grau auf der eigenen offenen Karte, „zurückgezogen“ als Marke und Ergebnis; ein alter Antrag aufs
    Entfernen nur noch ablehnen. Knopfregel unverändert; Journal-Beschriftung; CSS für die Marke."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    block = js[js.index("/* --- Änderungsanträge"):js.index("/* --- Artikel anlegen")]
    antrag_dlg = block[block.index("function antragDialog(a)"):]
    assert "aa-entfernen" not in js and "herstellung_entfernen" not in js and "Herstelldatum entfernen" not in js
    assert antrag_dlg.count('class="btn"') == 1
    hinweis = block[block.index("const antragOffenHtml"):block.index("function antragDialog(a)")]
    assert ('${x.eigen ? `<button class="btn secondary small" type="button" data-act="antrag-zurueck" '
            'data-id="${x.id}">Antrag zurückziehen</button>` : ""}' in hinweis)
    assert "await confirm(" in hinweis and '"Zurückziehen"' in hinweis and "/zurueckziehen`" in hinweis
    seite = js[js.index("async function artikel()"):js.index("function artikelDialog(a)")]
    assert '"antrag-zurueck": (b) => antragZurueckziehen(' in seite
    # Die offenen Anträge stehen als eigener Abschnitt am Anfang der rechten Spalte (Kasten .mat-spalte), vor „QR-Code und
    # NFC“, nicht unter den Stammdaten; der Knopf „Änderung beantragen“ bleibt links bei den Stammdaten (22.10.2026).
    spalten = seite[seite.index('<div class="mat-spalten">'):seite.index('<section class="section"><h2>Prüfungen</h2>')]
    links, rechts = spalten.split('<div class="mat-spalte">')
    assert "antragOffenHtml" not in links and 'data-act="antrag">Änderung beantragen<' in links
    abschnitt = ('`<section class="section mat-antraege-offen"><h2>Offene Änderungsanträge</h2>'
                 '${a.antraege.map(antragOffenHtml).join("")}</section>`')
    assert "(a.antraege || []).length ? " + abschnitt in rechts
    assert rechts.index("Offene Änderungsanträge") < rechts.index("<h2>QR-Code und NFC${infoKnopf(") < rechts.index("<h2>Herstellerdokumente</h2>")
    assert "order:" not in css[css.index(".mat-spalten {"):css.index(".mat-daten {")] and ".mat-spalte { min-width: 0; }" in css
    dlg = js[js.index("function artikelDialog(a)"):js.index("/* --- Änderungsanträge")]
    assert "querySelectorAll('[data-act=\"antrag-zurueck\"]')" in dlg and "dlg.close(); return zeigen(artikel);" in dlg
    karte = js[js.index("function antragKarte(x)"):js.index("function antragBestaetigenDialog")]
    assert 'x.eigen ? `<button type="button" class="btn secondary small" data-act="antrag-zurueck"' in karte
    assert "!x.entfernen" in karte and "Vom Antragsteller zurückgezogen am" in karte
    assert 'class="btn"' not in karte and "btn danger" not in karte
    seite_a = js[js.index("async function antraegeSeite()"):js.index("function antragKarte(x)")]
    assert '"antrag-zurueck": (b) => antragZurueckziehen(antrag(b), zeichnen)' in seite_a
    assert 'zurueckgezogen: "zurückgezogen" }' in js and 'antrag_zurueckgezogen: "Änderungsantrag zurückgezogen"' in js
    for x in (".mat-mstatus.m-zurueckgezogen", ".mat-meldung.m-zurueckgezogen", ".mat-antrag-offen .btn-row"):
        assert x in css, x
    from app.material.services import beschriftung
    assert beschriftung.AKTION["antrag_zurueckgezogen"] == "Änderungsantrag zurückgezogen"
    print("Oberfläche (17) bestanden.")


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
    test_leser_ohne_inhalt()
    test_bescheid_nur_mit_recht()
    test_trigger_16()
    test_migration_16()
    test_rueckruf_hinweis()
    test_sammelprotokoll_vormals()
    test_nachtragen_nach_entfernen()
    test_oberflaeche_pruefung()
    test_zurueckziehen()
    test_herstellung_nicht_entfernen()
    test_migration_17()
    test_oberflaeche_17()
