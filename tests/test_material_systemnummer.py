"""Seriennummer durch die Systemnummer ersetzen; Seriennummern im Bestandsimport ab 3 Zeichen (Wunsch vom 08.11.2026):
python tests/test_material_systemnummer.py

„Durch Systemnummer ersetzen“ gibt einem Artikel statt der Herstellernummer die STR-Nummer, die er beim Anlegen ohne
Herstellernummer bekommen hätte (STR- mit der Zahl seiner Inventarnummer, serial_generated 1). Bis zur ersten Prüfung
direkt im Dialog „Bearbeiten“ (Materialwart, Journal mit alter und neuer Nummer), danach nur per Änderungsantrag – die
Nummer steht im Antrag und wird erst mit der Bestätigung die Seriennummer; Rückruf-Hinweise, „vormals …“ und Trigger wie
bei jeder Seriennummernänderung. Dazu die Grenze von 3 Zeichen im Bestandsimport und in der globalen Suche.
Echte Mails gehen nie hinaus (post ersetzt den Versand). Alle Namen, Nummern und Texte sind Platzhalter."""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, neuer_artikel  # noqa: E402
from test_material_antrag import (ANTRAG_FEST, FEST, ablehnen, antraege, aufbau, beantragen, bestaetigen,  # noqa: E402
                                  item, journal, lesen, post, sql, zeilen)

SCHON = "schon eine Seriennummer vom System"
ODER = "nicht beides"


def systemnummer(app, iid):
    """Die erwartete Systemnummer: STR- mit der Zahl der Inventarnummer."""
    return "STR-" + item(app, iid)["inventory_no"][2:]


def bearbeiten(c, iid, **d):
    return c.put(f"/api/material/artikel/{iid}", json=d)


# --- 1. Direkt im Dialog „Bearbeiten“ (vor der ersten Prüfung) -----------------------------------------------------

def test_direkt():
    """Materialwart: AN-NEU → STR-<Inventarnummer>, serial_generated 1, Journal „geaendert“ mit alter und neuer Nummer;
    die Artikelansicht nennt die Systemnummer nur, solange er keine hat. Zweites Mal 409, zugleich eine andere Nummer
    400, kein Ja/Nein 400. Prüfer 403, Führungskraft 403, nach der ersten Prüfung 409 (nur per Antrag). Eine echte
    Herstellernummer ersetzt sie wieder; die Nummer bekommt nie ein anderer Artikel – liegt sie (per SQL) schon bei
    einem anderen Artikel desselben Produkts, 409."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sn = systemnummer(t.app, t.neu1)
        a = lesen(t.w, t.neu1)
        assert a["systemnummer"] == sn and not a["serial_generated"] and not a["stammdaten_fest"], a
        assert lesen(t.w, t.k2)["systemnummer"] is None            # hat schon eine vom System
        for c, code in ((t.p, 403), (t.f, 403)):
            r = bearbeiten(c, t.neu1, systemnummer=True)
            assert r.status_code == code, (code, r.get_json())
        r = bearbeiten(t.w, t.neu1, systemnummer=True, serial_no="AN-ANDERS")
        assert r.status_code == 400 and ODER in r.json["error"], r.get_json()
        r = bearbeiten(t.w, t.neu1, systemnummer="vielleicht")
        assert r.status_code == 400 and "ja oder nein" in r.json["error"], r.get_json()
        assert item(t.app, t.neu1)["serial_no"] == "AN-NEU"
        # Nach der ersten Prüfung nur per Antrag.
        r = bearbeiten(t.w, t.k1, systemnummer=True)
        assert r.status_code == 409 and r.json["error"] == FEST, r.get_json()
        # Gleiche Nummer wie bisher mitgeschickt (der Dialog leert das Feld, ein älterer schickt sie mit): geht.
        r = bearbeiten(t.w, t.neu1, systemnummer=True, serial_no="an-neu", stand=a["stand"])
        assert r.status_code == 200, r.get_json()
        z = item(t.app, t.neu1)
        assert (z["serial_no"], z["serial_generated"]) == (sn, 1), z
        j = journal(t.app, t.neu1, "geaendert")[-1]
        assert j["vorher"] == {"serial_no": "AN-NEU", "serial_generated": False}, j
        assert j["nachher"] == {"serial_no": sn, "serial_generated": True}, j
        neu = r.json["artikel"]
        assert neu["systemnummer"] is None and neu["serial_generated"] is True and neu["serial_no"] == sn
        r = bearbeiten(t.w, t.neu1, systemnummer=True)
        assert r.status_code == 409 and SCHON in r.json["error"], r.get_json()
        # Wieder eine Herstellernummer: die Systemnummer ist frei – aber nur für diesen Artikel.
        assert bearbeiten(t.w, t.neu1, serial_no="AN-NEU-2").status_code == 200
        assert (item(t.app, t.neu1)["serial_no"], item(t.app, t.neu1)["serial_generated"]) == ("AN-NEU-2", 0)
        andere = neuer_artikel(t.w, t.ids["hms"], t.lager)
        assert andere["serial_no"] != sn and andere["serial_no"] == systemnummer(t.app, andere["id"])
        assert lesen(t.w, t.neu1)["systemnummer"] == sn
        # Nie doppelt: Trägt (an der Schnittstelle vorbei) ein anderer Artikel desselben Produkts die Nummer, 409.
        x = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="AN-X1")["id"]
        sql(t.app, "UPDATE mat_item SET serial_no = ? WHERE id = ?", (systemnummer(t.app, x), t.neu1))
        r = bearbeiten(t.w, x, systemnummer=True)
        assert r.status_code == 409 and "gibt es bei diesem Produkt schon" in r.json["error"], r.get_json()
        assert item(t.app, x)["serial_no"] == "AN-X1"
        # Eine getippte STR-Nummer bleibt gesperrt, auch die eigene.
        r = bearbeiten(t.w, x, serial_no=systemnummer(t.app, x))
        assert r.status_code == 400 and "STR-" in r.json["error"], r.get_json()
    print("Direkt bestanden.")


# --- 2. Per Änderungsantrag (nach der ersten Prüfung) --------------------------------------------------------------

def test_antrag():
    """Prüfer beantragt „systemnummer“ an k1 (AN-100): die Zeile nennt alt AN-100 und neu STR-<Inventarnummer> (Text
    „… (vom System)“), der Artikel bleibt bis zur Bestätigung, wie er ist; Journal „antrag_gestellt“ mit beiden
    Nummern. Bestätigt: Nummer und serial_generated 1, applied_at, Journal „antrag_bestaetigt“. Danach (und an k2 mit
    STR-Nummer) 409. Abgelehnt: nichts ändert sich. Zugleich eine andere Nummer 400, eine getippte STR-Nummer 400,
    Führungskraft 403."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sn = systemnummer(t.app, t.k1)
        assert lesen(t.w, t.k1)["systemnummer"] == sn
        for d, code, text in (({"systemnummer": True, "serial_no": "AN-ANDERS"}, 400, ODER),
                              ({"serial_no": sn}, 400, "STR-"),
                              ({"systemnummer": "vielleicht"}, 400, "ja oder nein")):
            r = beantragen(t.p, t.k1, **d)
            assert r.status_code == code and text in r.json["error"], (d, r.get_json())
        assert beantragen(t.f, t.k1, systemnummer=True).status_code == 403
        r = beantragen(t.p, t.k2, systemnummer=True)
        assert r.status_code == 409 and SCHON in r.json["error"], r.get_json()
        r = beantragen(t.p, t.k1, systemnummer=True, serial_no="AN-100", begruendung="Platzhalter: Etikett unleserlich")
        assert r.status_code == 201, r.get_json()
        x = r.json["antrag"]
        aid = x["id"]
        assert [(y["feld"], y["alt"], y["neu"], y["neu_text"]) for y in x["aenderungen"]] == [
            ("serial_no", "AN-100", sn, f"{sn} (vom System)")], x
        assert (item(t.app, t.k1)["serial_no"], item(t.app, t.k1)["serial_generated"]) == ("AN-100", 0)
        j = journal(t.app, t.k1, "antrag_gestellt")[-1]
        assert j["vorher"] == {"serial_no": "AN-100", "serial_generated": False}, j
        assert {k: j["nachher"][k] for k in ("serial_no", "serial_generated", "antrag")} == {
            "serial_no": sn, "serial_generated": True, "antrag": aid}, j
        r = bestaetigen(t.w, aid)
        assert r.status_code == 200, r.get_json()
        z = item(t.app, t.k1)
        assert (z["serial_no"], z["serial_generated"]) == (sn, 1), z
        assert all(a["applied_at"] and a["status"] == "bestaetigt" for a in antraege(t.app, t.k1))
        j = journal(t.app, t.k1, "antrag_bestaetigt")[-1]
        assert j["vorher"] == {"serial_no": "AN-100", "serial_generated": False}, j
        assert j["nachher"] == {"serial_no": sn, "serial_generated": True, "antrag": aid, "beantragt_von": "pruefer",
                                "begruendung": "Platzhalter: Etikett unleserlich"}, j
        assert lesen(t.w, t.k1)["systemnummer"] is None
        r = beantragen(t.p, t.k1, systemnummer=True)
        assert r.status_code == 409 and SCHON in r.json["error"], r.get_json()
        # Wieder eine Herstellernummer per Antrag: serial_generated 0 (wie bisher).
        aid2 = beantragen(t.p, t.k1, serial_no="AN-100-B").json["antrag"]["id"]
        assert bestaetigen(t.w, aid2).status_code == 200
        assert (item(t.app, t.k1)["serial_no"], item(t.app, t.k1)["serial_generated"]) == ("AN-100-B", 0)
        # Abgelehnt: nichts ändert sich.
        aid3 = beantragen(t.w, t.s1, systemnummer=True).json["antrag"]["id"]
        assert ablehnen(t.w, aid3, antwort="Platzhalter: Nummer ist lesbar").status_code == 200
        assert (item(t.app, t.s1)["serial_no"], item(t.app, t.s1)["serial_generated"]) == ("AN-S1", 0)
        assert lesen(t.w, t.s1)["systemnummer"] == systemnummer(t.app, t.s1)
    print("Antrag bestanden.")


def test_bestaetigen_eindeutig():
    """Liegt die Nummer beim Bestätigen (an der Schnittstelle vorbei) schon bei einem anderen Artikel desselben
    Produkts, 409 – der Antrag bleibt offen und lässt sich ablehnen; der Artikel bleibt, wie er ist."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sn = systemnummer(t.app, t.k1)
        aid = beantragen(t.w, t.k1, systemnummer=True).json["antrag"]["id"]
        sql(t.app, "UPDATE mat_item SET serial_no = ? WHERE id = ?", (sn, t.neu1))       # ungeprüft, kein Trigger
        r = bestaetigen(t.w, aid)
        assert r.status_code == 409 and "gibt es bei diesem Produkt schon" in r.json["error"], r.get_json()
        assert item(t.app, t.k1)["serial_no"] == "AN-100" and antraege(t.app, t.k1)[0]["status"] == "offen"
        assert ablehnen(t.w, aid, antwort="Platzhalter").status_code == 200
    print("Bestätigen eindeutig bestanden.")


# --- 3. Trigger -------------------------------------------------------------------------------------------------------

def test_trigger():
    """An der Schnittstelle vorbei: Nach der ersten Prüfung geht die Systemnummer nicht ohne bestätigten Antrag in den
    Artikel, auch nicht mit offenem; der bestätigte Antrag wirkt genau einmal, sein Inhalt bleibt fest."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sn = systemnummer(t.app, t.k1)
        # Ohne offene Transaktion (autocommit) – zwischendurch schreibt die Schnittstelle.
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"), isolation_level=None)

        def geht_nicht(befehl, args=(), text="seit seiner ersten Prüfung fest"):
            try:
                conn.execute(befehl, args)
            except sqlite3.IntegrityError as e:
                assert text in str(e), (befehl, e)
                return
            raise AssertionError(befehl)
        try:
            geht_nicht("UPDATE mat_item SET serial_no = ?, serial_generated = 1 WHERE id = ?", (sn, t.k1))
            aid = beantragen(t.w, t.k1, systemnummer=True).json["antrag"]["id"]
            geht_nicht("UPDATE mat_item SET serial_no = ?, serial_generated = 1 WHERE id = ?", (sn, t.k1))
            geht_nicht("UPDATE mat_item_change SET new_value = 'STR-999999' WHERE id = ?", (aid,), ANTRAG_FEST)
            assert bestaetigen(t.w, aid).status_code == 200
            # Einmal angewendet: zurück und wieder hin geht nicht.
            geht_nicht("UPDATE mat_item SET serial_no = 'AN-100', serial_generated = 0 WHERE id = ?", (t.k1,))
            geht_nicht("UPDATE mat_item_change SET new_value = 'AN-100' WHERE id = ?", (aid,), ANTRAG_FEST)
            geht_nicht("DELETE FROM mat_item_change WHERE id = ?", (aid,), ANTRAG_FEST)
        finally:
            conn.close()
        assert item(t.app, t.k1)["serial_no"] == sn
    print("Trigger bestanden.")


# --- 4. Folgen: Rückruf und „vormals …“ ---------------------------------------------------------------------------------

def test_rueckruf_und_vormals():
    """Ein laufender Rückruf mit AN-100 in seiner Liste trifft k1 nach der Systemnummer nicht mehr: Antrag (Karte) unter
    „nicht_mehr“, Journal der Bestätigung „rueckruf_nicht_mehr“. Das Einzelprotokoll der Prüfung vor dem Antrag nennt
    weiter AN-100 – „vormals AN-100 (Änderungsantrag Nr. …)“ für ein späteres Sammelprotokoll (protokoll._vormals)."""
    with post(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sn = systemnummer(t.app, t.k1)
        r = t.mv.post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe", headers=H,
                      json={"title": "Platzhalter-Rückruf", "serials": "AN-100\nAN-999", "mail": False})
        assert r.status_code == 201, r.get_json()
        rid = r.json["rueckruf"]["id"]
        aid = beantragen(t.p, t.k1, systemnummer=True).json["antrag"]["id"]
        karte = [x for x in t.w.get("/api/material/antraege").json["antraege"] if x["id"] == aid][0]
        assert karte["rueckruf"] == {"nicht_mehr": [{"id": rid, "title": "Platzhalter-Rückruf"}], "neu": [],
                                     "wieder_offen": []}, karte["rueckruf"]
        assert bestaetigen(t.w, aid).status_code == 200
        j = journal(t.app, t.k1, "antrag_bestaetigt")[-1]["nachher"]
        assert j["rueckruf_nicht_mehr"] == [f"Platzhalter-Rückruf (Nr. {rid})"], j
        assert [x["title"] for x in lesen(t.w, t.k1)["rueckrufe"]] == []
        pruefung = zeilen(t.app, "SELECT id FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL",
                          (t.k1,))[0]["id"]
        from app.material.services import protokoll
        with t.app.app_context():
            assert protokoll._vormals(t.k1, pruefung, sn) == ("AN-100", aid)
    print("Rückruf und „vormals“ bestanden.")


# --- 5. Import und globale Suche ab 3 Zeichen ----------------------------------------------------------------------------

def test_import_drei_zeichen():
    """Bestandsimport: „A1B“ (3 Zeichen) ist übernehmbar und wird angelegt, „17“ (2) bleibt „von Hand anlegen“ mit dem
    Satz „weniger als 3 Zeichen“. Globale Suche: „ABC“ geht (200, im Protokoll), „AB“ ist zu kurz."""
    from test_material_globalsuche import global_suchen, protokoll as such_protokoll
    from test_material_import import KOPF, aufbau as import_aufbau, codes, csv_bytes, nach_nr, ok, probelauf, uebernehmen
    with tempfile.TemporaryDirectory() as tmp:
        t = import_aufbau(tmp)
        daten = csv_bytes([KOPF, ["Testwerk", "HMS Beta", "A1B"], ["Testwerk", "HMS Beta", "17"]])
        z = nach_nr(ok(probelauf(t.w, t.lager, daten)))
        assert z[2]["status"] == "uebernehmbar" and z[2]["seriennummer"] == "A1B", z[2]
        assert codes(z[3]) == ["serie_von_hand"] and "weniger als 3 Zeichen" in z[3]["gruende"][0]["text"], z[3]
        z = nach_nr(ok(uebernehmen(t.w, t.lager, daten), 201))
        assert zeilen(t.app, "SELECT serial_generated FROM mat_item WHERE id = ? AND serial_no = 'A1B'",
                      (z[2]["artikel"]["id"],)) == [{"serial_generated": 0}]
        from app.material.services import globalsuche
        assert globalsuche.MIN_ZEICHEN == 3 and "Mindestens 3 und" in globalsuche.ZU_KURZ
        vorher = len(such_protokoll(t.app))
        r = global_suchen(t.w, "ABC")
        assert r.status_code == 200 and r.json["treffer"] == [], r.get_json()
        assert len(such_protokoll(t.app)) == vorher + 1
        r = global_suchen(t.w, "AB")
        assert r.status_code == 400 and r.json["error"] == globalsuche.ZU_KURZ, r.get_json()
    print("Import ab 3 Zeichen bestanden.")


if __name__ == "__main__":
    test_direkt()
    test_antrag()
    test_bestaetigen_eindeutig()
    test_trigger()
    test_rueckruf_und_vormals()
    test_import_drei_zeichen()
