"""Globale Seriennummernsuche und QR-Steckbrief (Phase 2 · Lieferung 1, Abschnitt 3):
python tests/test_material_globalsuche.py  oder  pytest tests/test_material_globalsuche.py

Die Tests aus dem Bauentwurf 8.3 für Paket C: Eingaben (Bestätigung, Länge, vergebene Nummern, die Verwaltung),
genau die Felder des Steckbriefs (keine Kennung, Pfad der Heimat ohne Systemordner, persönlicher Ordner verdeckt),
höchstens 10 Treffer mit „mehr“, die gemeinsame Bremse von Suche, QR-Steckbrief und Dublette, das Protokoll mit seiner
Frist (beim Schreiben, beim Neustart, beim Lesen) nur für die Verwaltung, der QR-Steckbrief erst nach Bestätigung, dazu
mit Paket A1R das Angebot in GET /suche, die Seite /m/<token> eines fremden Artikels und die fremde Dublette beim
Anlegen. Seit den Entscheidungen vom 18.10.2026 außerdem: das Sperrwort im Steckbrief (test_sperrwort), das Angebot zu
jeder tauglichen Anfrage außer für die Verwaltung (test_angebot) und nur fremde Treffer, auch bei derselben
Seriennummer im eigenen Bereich (test_nur_fremde), auch für ein Konto, das nur einen Ordner einer Gliederung sieht
(test_teilfreigabe), und das Angebot auch nach der Weiterleitung zu einem eindeutigen eigenen Treffer
(test_eindeutiger_treffer). Alle Namen, Hersteller und Nummern hier sind erfunden und nur für
den Test da."""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, freigeben, jpeg, make_app, neuer_artikel, neues_konto  # noqa: E402
from test_material_trennung import sql, zeilen, zwei_gliederungen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

SUCHE = "/api/material/globalsuche"
QR = "/api/material/globalsuche/qr"
PROTOKOLL = "/api/material/globalsuche/protokoll"
GEHEIM = ("Bemerkung geheim Test", "Sperrgrund geheim Test", "Spind Erika Test", "Fach Oben Test")


def global_suchen(c, q, **mehr):
    return c.post(SUCHE, json=dict({"q": q, "bestaetigt": True}, **mehr), headers=H)


def steckbrief_holen(c, token, **mehr):
    return c.post(QR, json=dict({"token": token, "bestaetigt": True}, **mehr), headers=H)


def token_von(a):
    return a["qr_adresse"].rsplit("/", 1)[1]


def protokoll(app):
    return zeilen(app, "SELECT * FROM mat_global_search ORDER BY id")


def versuche(app, uid):
    """Wie oft das Konto in der laufenden Viertelstunde durch die Bremse ging."""
    return zeilen(app, "SELECT COUNT(*) AS n FROM login_attempts WHERE scope = ?", (f"mat-global:{uid}",))[0]["n"]


def vor_tagen(tage):
    return (datetime.now(timezone.utc) - timedelta(days=tage)).replace(microsecond=0).isoformat()


def alte_zeile(app, tage, anfrage="TEST-ALT-0001"):
    sql(app, "INSERT INTO mat_global_search (user_id, user_name, art, anfrage, treffer, item_ids, created_at) "
             "VALUES (NULL, 'Testkonto alt', 'suche', ?, 0, '[]', ?)", (anfrage, vor_tagen(tage)))


def aufbau(tmp):
    """Zwei Gliederungen (zwei_gliederungen) und in B Artikel in allen Lagen, die der Steckbrief kennen muss: im
    Fahrzeug, unter einem persönlichen Ordner, gesperrt und verloren (mit Herkunft), ausgesondert ohne Herkunft und
    direkt in einer verschachtelten Gliederung. Das Produkt „HMS Beta“ hat ein Bild, der Gurt keins. Jeder Artikel in B
    trägt eine Bemerkung, die nie hinausgehen darf."""
    t = zwei_gliederungen(tmp)
    w = t.wart_b
    r = t.k["katalog"].post(f"/api/material/produkte/{t.ids['hms']}/bild", data={"file": (jpeg(), "hms.jpg")}, headers=H,
                            content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    t.fahrzeug_b = ordner_neu(w, t.lager_b, "Fahrzeug NS", "fahrzeug")
    t.spind_b = ordner_neu(w, t.fahrzeug_b, "Spind Erika Test", "persoenlich")
    t.fach_b = ordner_neu(w, t.spind_b, "Fach Oben Test", "sonstiges")
    r = w.post("/api/material/ordner", json={"name": "Ortsgruppe Teil Test", "kind": "gliederung", "parent_id": t.b})
    assert r.status_code == 201, r.get_json()
    t.teil_b = r.json["ordner"]["id"]
    t.gurt_b = neuer_artikel(w, t.ids["gurt"], t.fahrzeug_b, serial_no="TEST-G-0001", manufactured_on="2020-03")
    t.pers_b = neuer_artikel(w, t.ids["hms"], t.fach_b, serial_no="TEST-G-0002")
    t.gesp_b = neuer_artikel(w, t.ids["hms"], t.lager_b, serial_no="TEST-G-0003")
    t.aus_b = neuer_artikel(w, t.ids["hms"], t.lager_b, serial_no="TEST-G-0004")
    t.verl_b = neuer_artikel(w, t.ids["hms"], t.fahrzeug_b, serial_no="TEST-G-0005")
    t.teil_art_b = neuer_artikel(w, t.ids["hms"], t.teil_b, serial_no="TEST-G-0006")
    # Sperrzustände direkt in der Tabelle – so, wie Sperre, Verlustmeldung und eine Aussonderung aus Phase 1 sie
    # hinterlassen (Ausgesonderte aus Phase 1 haben keine Herkunft).
    sql(t.app, "UPDATE mat_item SET lock_state = 'gesperrt', lock_reason = ?, folder_id = ?, origin_folder_id = ? "
               "WHERE id = ?", (GEHEIM[1], t.sys_b["gesperrt"], t.lager_b, t.gesp_b["id"]))
    sql(t.app, "UPDATE mat_item SET lock_state = 'verloren', lock_reason = ?, folder_id = ?, origin_folder_id = ? "
               "WHERE id = ?", (GEHEIM[1], t.sys_b["gesperrt"], t.fahrzeug_b, t.verl_b["id"]))
    sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert', lock_reason = ?, folder_id = ?, origin_folder_id = NULL "
               "WHERE id = ?", (GEHEIM[1], t.sys_b["ausgesondert"], t.aus_b["id"]))
    t.alle_b = [t.art_b, t.gurt_b, t.pers_b, t.gesp_b, t.aus_b, t.verl_b, t.teil_art_b]
    for x in t.alle_b:
        sql(t.app, "UPDATE mat_item SET notes = ? WHERE id = ?", (GEHEIM[0], x["id"]))
    return t


def nichts_geheimes(t, r, *weitere):
    """Die Antwort nennt weder Kennungen noch Links, Status, Prüfungen, Bemerkungen oder verdeckte Ordner."""
    text = r.get_data(as_text=True)
    for wort in GEHEIM + weitere + ('"id"', "/material/artikel/", "/m/", "Prüferin Nachbarstadt", "1012-9001",
                                    "Testdurchgang", '"status', "einsatzbereit", "faellig", "next_due", "notes"):
        assert wort not in text, (wort, text)
    for x in getattr(t, "alle_b", [t.art_b]):
        assert token_von(x) not in text, text


# --- Eingaben ---------------------------------------------------------------------------------------------------

def test_eingaben():
    """Ohne Bestätigung, zu kurz oder zu lang, vergebene Nummern: 400. Die Plattform-Verwaltung sieht alles: 409. Nichts
    davon zählt in der Bremse oder steht im Protokoll. Eine Seriennummer aus dem eigenen Bereich hält die Suche nicht
    mehr auf (Entscheidung vom 18.10.2026) – sie läuft, zählt und findet nur Fremdes. Ohne Anmeldung 401, ohne
    Modulzugang 403."""
    from app.material.services import globalsuche
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        w, uid = t.wart_a, t.k["wart_id"]
        for d in ({"q": "TEST-B-0001"}, {"q": "TEST-B-0001", "bestaetigt": "true"},
                  {"q": "TEST-B-0001", "bestaetigt": 1}, {"q": "TEST-B-0001", "bestaetigt": False}, {}):
            r = w.post(SUCHE, json=d, headers=H)
            assert r.status_code == 400 and r.json["error"] == globalsuche.BESTAETIGEN, (d, r.get_json())
        for q in ("ABC", "  A  B ", "x" * 81, "", None, 12345678, ["TEST-B-0001"]):
            r = global_suchen(w, q)
            assert r.status_code == 400 and r.json["error"] == globalsuche.ZU_KURZ, (q, r.get_json())
        assert global_suchen(w, "x" * 80).status_code == 200            # 80 Zeichen gehen noch
        for q in ("M-000001", "m-000001", "M-TEST1", "STR-000001", "str-12345", " STR-000001 "):
            r = global_suchen(w, q)
            assert r.status_code == 400 and r.json["error"] == globalsuche.NUR_HERSTELLER, (q, r.get_json())
        assert versuche(t.app, uid) == 1 and len(protokoll(t.app)) == 1           # nur die Suche mit 80 Zeichen
        # Im eigenen Bereich – auch klein geschrieben und mit Leerraum: Die Suche läuft und zeigt nur Fremdes (hier
        # nichts); sie zählt in der Bremse und steht im Protokoll.
        for q in ("TEST-A-0001", "test-a-0001", "  TEST-A-0001 "):
            r = global_suchen(w, q)
            assert r.status_code == 200 and r.json["treffer"] == [] and r.json["mehr"] is False, (q, r.get_json())
        assert versuche(t.app, uid) == 4
        assert [(z["anfrage"], z["treffer"]) for z in protokoll(t.app)][1:] == [
            ("TEST-A-0001", 0), ("test-a-0001", 0), ("TEST-A-0001", 0)]
        # Die Plattform-Verwaltung sieht alles – für sie gibt es nichts Fremdes: 409, nicht gezählt, nicht protokolliert.
        # Eine unbrauchbare Anfrage bleibt auch bei ihr beim eigenen Fehler (400).
        adm_id = zeilen(t.app, "SELECT id FROM users WHERE email = 'admin@example.org'")[0]["id"]
        for q in ("TEST-B-0001", "TEST-A-0001", "TEST-NIRGENDS-0815"):
            r = global_suchen(t.adm, q)
            assert r.status_code == 409 and r.json["error"] == globalsuche.SIEHT_ALLES, (q, r.get_json())
        assert global_suchen(t.adm, "STR-000001").json["error"] == globalsuche.NUR_HERSTELLER
        assert t.adm.post(SUCHE, json={"q": "TEST-B-0001"}, headers=H).json["error"] == globalsuche.BESTAETIGEN
        assert versuche(t.app, adm_id) == 0 and len(protokoll(t.app)) == 4
        # Leerraum in der Mitte zählt einfach, Steuerzeichen als Leerraum – so steht die Anfrage im Protokoll.
        assert global_suchen(w, "TEST \t  NIRGENDS\x00 0815").status_code == 200
        assert protokoll(t.app)[-1]["anfrage"] == "TEST NIRGENDS 0815"
        # Ohne Anmeldung 401, ohne Modulzugang 403 mit dem Grund.
        assert t.app.test_client().post(SUCHE, json={"q": "TEST-B-0001", "bestaetigt": True}, headers=H).status_code == 401
        r = global_suchen(t.k["nutzer"], "TEST-B-0001")
        assert r.status_code == 403 and "nicht freigeschaltet" in r.json["error"], r.get_json()
        # GET gibt es nicht – die Suche ändert das Protokoll.
        assert w.get(f"{SUCHE}?q=TEST-B-0001").status_code == 405
    print("Eingaben bestanden.")


# --- Der Steckbrief ---------------------------------------------------------------------------------------------

def test_steckbrief():
    """Ein fremder Treffer hat genau die Schlüssel aus FELDER – keine Kennung, kein Link, kein Prüfstatus, keine
    Prüfdaten; den Sperrzustand nur als ein Wort. Die Zugehörigkeit kommt aus der Heimat: Gesperrte und Verlorene unter
    ihrem Herkunftsordner, Ausgesonderte ohne Herkunft nur bei der Gliederung, ein persönlicher Ordner nur als
    „persönlicher Ordner“, eine verschachtelte Gliederung mit eigenem Namen. Suchen darf jeder mit Modulzugang, auch
    ohne Bestand; wer B sieht, findet dort nichts Fremdes, und die Verwaltung sieht alles und bekommt deshalb 409."""
    from app.material.services import globalsuche
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        w = t.wart_a
        gurt = t.wart_b.get(f"/api/material/artikel/{t.gurt_b['id']}").json["artikel"]
        assert gurt["retire_by"], gurt

        def einer(q):
            r = global_suchen(w, q)
            assert r.status_code == 200, (q, r.get_json())
            assert set(r.json) == {"treffer", "mehr", "hinweis"} and r.json["mehr"] is False, r.json
            assert r.json["hinweis"] == globalsuche.HINWEIS and len(r.json["treffer"]) == 1, r.json
            x = r.json["treffer"][0]
            assert set(x) == globalsuche.FELDER, set(x) ^ globalsuche.FELDER
            nichts_geheimes(t, r)
            return x, r

        x, r = einer("test-g-0001")                         # ohne Rücksicht auf Groß/klein
        assert x == {"inventory_no": t.gurt_b["inventory_no"], "serial_no": "TEST-G-0001", "hersteller": "Testwerk",
                     "modell": "Gurt Alpha", "artikelnummer": "GA-100", "norm": "", "materialart": "textil",
                     "kategorie": "PSA gegen Absturz / Gurte", "vorschau": None, "hergestellt": "2020-03",
                     "lebensende": gurt["retire_by"], "gliederung": "OG Nachbarstadt",
                     "ordner": "Lager Nachbarstadt / Fahrzeug NS", "sperre": None, "demo": False}, x
        x, r = einer("TEST-B-0001")
        assert x["inventory_no"] == t.art_b["inventory_no"] and x["ordner"] == "Lager Nachbarstadt", x
        assert x["materialart"] == "Metall" and x["lebensende"] is None and x["hergestellt"] is None, x
        assert x["sperre"] is None, x
        assert x["kategorie"] == "PSA gegen Absturz / Karabiner" and x["modell"] == "HMS Beta", x
        # Das Produktbild ist Katalog und ohnehin global – als Vorschau, die jeder mit Modulzugang laden darf.
        assert re.fullmatch(r"/media/material/thumb/[0-9a-f]+\.jpg", x["vorschau"]), x
        assert w.get(x["vorschau"]).status_code == 200
        x, r = einer("TEST-G-0002")
        assert x["ordner"] == "Lager Nachbarstadt / Fahrzeug NS / persönlicher Ordner", x
        # Gesperrt, verloren und ausgesondert: genau ein Wort – der Systemordner steht nicht im Pfad, der Grund nirgends.
        x, r = einer("TEST-G-0003")                         # gesperrt, Herkunft Lager
        assert x["ordner"] == "Lager Nachbarstadt" and x["sperre"] == "gesperrt", x
        nichts_geheimes(t, r, "Gesperrt")
        x, r = einer("TEST-G-0005")                         # verloren, Herkunft Fahrzeug
        assert x["ordner"] == "Lager Nachbarstadt / Fahrzeug NS" and x["sperre"] == "verloren gemeldet", x
        nichts_geheimes(t, r, "Gesperrt")
        x, r = einer("TEST-G-0004")                         # ausgesondert ohne Herkunft (Filter NULL: fremd)
        assert x["ordner"] == "" and x["gliederung"] == "OG Nachbarstadt" and x["sperre"] == "ausgesondert", x
        nichts_geheimes(t, r, "Ausgesondert")
        x, r = einer("TEST-G-0006")
        assert x["gliederung"] == "Ortsgruppe Teil Test" and x["ordner"] == "", x
        # Jede Suche steht im Protokoll – Normalform, Treffer, Kennungen.
        p = protokoll(t.app)
        assert [(z["art"], z["anfrage"], z["treffer"], json.loads(z["item_ids"]), z["user_id"], z["user_name"])
                for z in p] == [("suche", q, 1, [i], t.k["wart_id"], "wart") for q, i in (
                    ("test-g-0001", t.gurt_b["id"]), ("TEST-B-0001", t.art_b["id"]), ("TEST-G-0002", t.pers_b["id"]),
                    ("TEST-G-0003", t.gesp_b["id"]), ("TEST-G-0005", t.verl_b["id"]), ("TEST-G-0004", t.aus_b["id"]),
                    ("TEST-G-0006", t.teil_art_b["id"]))], p
        # Eine Seriennummer, die es nirgends gibt: 200 ohne Treffer – und trotzdem im Protokoll.
        r = global_suchen(w, "TEST-NIRGENDS-0815")
        assert r.status_code == 200 and r.json == {"treffer": [], "mehr": False, "hinweis": globalsuche.HINWEIS}, r.json
        assert protokoll(t.app)[-1]["treffer"] == 0
        # Suchen darf jeder mit Modulzugang: ein Katalogpfleger ohne Bestand, ein Prüfer mit Häkchen ohne Freigabe.
        kp, _ = neues_konto(t.app, "katalog2@example.org", name="Katalogpflege Test", mat_katalog=True)
        assert kp.get("/api/material/start").json["darf"]["lesen"] is False
        assert global_suchen(kp, "TEST-B-0001").json["treffer"][0]["inventory_no"] == t.art_b["inventory_no"]
        pr, _ = neues_konto(t.app, "pruefer3@example.org", name="Prüfer Test", mat_pruefer=True, urkundennummer="1012-0003")
        assert global_suchen(pr, "TEST-B-0001").status_code == 200
        # Wer B sieht – auch nur zum Prüfen –, findet den Artikel mit der normalen Suche; die globale zeigt nur Fremdes
        # (hier nichts). Die Verwaltung sieht alles: 409.
        for c in (t.wart_b, t.pruefer_b):
            r = global_suchen(c, "TEST-B-0001")
            assert r.status_code == 200 and r.json["treffer"] == [], r.get_json()
        r = global_suchen(t.adm, "TEST-B-0001")
        assert r.status_code == 409 and r.json["error"] == globalsuche.SIEHT_ALLES, r.get_json()
        # Vom System vergebene Seriennummern findet die globale Suche nie (die Anfrage käme ohnehin nicht durch).
        sql(t.app, "UPDATE mat_item SET serial_generated = 1 WHERE id = ?", (t.art_b["id"],))
        assert global_suchen(w, "TEST-B-0001").json["treffer"] == []
    print("Steckbrief bestanden.")


def test_zehn_und_mehr():
    """Dieselbe Seriennummer an elf Artikeln (verschiedene Produkte): höchstens zehn Treffer, nach Kennung, und „mehr“ –
    eine Gesamtzahl gibt es nicht. Mit genau zehn ist „mehr“ falsch."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        ids = []
        for n in range(11):
            r = t.k["katalog"].post("/api/material/produkte", json={
                "category_id": t.ids["karabiner"], "manufacturer": "Testwerk", "model": f"Testkarabiner {n + 1:02d}",
                "material_kind": "metall_hardware", "interval_months": 12})
            assert r.status_code == 201, r.get_json()
            ids.append(neuer_artikel(t.wart_b, r.json["produkt"]["id"], t.lager_b, serial_no="TEST-ELF-0001")["id"])
            if n == 9:
                r = global_suchen(t.wart_a, "TEST-ELF-0001")
                assert len(r.json["treffer"]) == 10 and r.json["mehr"] is False, r.json
        r = global_suchen(t.wart_a, "test-elf-0001")
        assert r.status_code == 200 and len(r.json["treffer"]) == 10 and r.json["mehr"] is True, r.json
        assert "gesamt" not in r.json and "11" not in json.dumps([x["modell"] for x in r.json["treffer"]])
        assert [x["modell"] for x in r.json["treffer"]] == [f"Testkarabiner {n:02d}" for n in range(1, 11)]
        z = protokoll(t.app)[-1]
        assert z["treffer"] == 10 and json.loads(z["item_ids"]) == ids[:10], z
    print("Zehn und mehr bestanden.")


# --- Bremse -----------------------------------------------------------------------------------------------------

def test_bremse():
    """Zehn Blicke über den eigenen Bereich je Viertelstunde und Konto – Suche, QR-Steckbrief und Dublette zusammen.
    Die elfte Suche und der elfte Steckbrief: 429, ohne Protokollzeile. Ein anderes Konto ist frei; nach der
    Viertelstunde geht es wieder. Unbrauchbare Anfragen antworten auch an der Grenze wie sonst (400)."""
    from flask import g

    from app.material.services import globalprotokoll, globalsuche
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        f, uid = t.k["fuehrung"], t.k["fuehrung_id"]
        token_b = token_von(t.art_b)
        for _ in range(6):
            assert global_suchen(f, "TEST-B-0001").status_code == 200
        for _ in range(2):
            assert steckbrief_holen(f, token_b).status_code == 200
        # Zwei fremde Dubletten – die Dublettenprüfung beim Anlegen geht durch dieselbe Bremse (routes._fremde_dublette).
        with t.app.test_request_context():
            from app import db
            g.user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
            for _ in range(2):
                globalprotokoll.bremse(uid)
        assert versuche(t.app, uid) == 10
        zeilen_vorher = len(protokoll(t.app))
        r = global_suchen(f, "TEST-B-0001")
        assert r.status_code == 429 and r.json["error"] == globalprotokoll.ZU_VIELE, r.get_json()
        r = steckbrief_holen(f, token_b)
        assert r.status_code == 429 and r.json["error"] == globalprotokoll.ZU_VIELE, r.get_json()
        assert len(protokoll(t.app)) == zeilen_vorher == 8
        # Was ohnehin scheitert, bleibt beim eigenen Fehler; ein eigener Artikel per QR führt weiter wie sonst. Eine
        # eigene Seriennummer geht seit dem 18.10.2026 durch die Bremse wie jede andere.
        r = f.post(SUCHE, json={"q": "TEST-B-0001"}, headers=H)
        assert r.status_code == 400 and r.json["error"] == globalsuche.BESTAETIGEN
        assert global_suchen(f, "ABC").status_code == 400
        assert global_suchen(f, "TEST-A-0001").status_code == 429
        assert global_suchen(t.adm, "TEST-B-0001").status_code == 409
        assert steckbrief_holen(f, token_von(t.art_a)).json == {"weiter": f"/material/artikel/{t.art_a['id']}"}
        # Je Konto gezählt.
        assert global_suchen(t.wart_a, "TEST-B-0001").status_code == 200
        # Nach der Viertelstunde geht es wieder.
        sql(t.app, "UPDATE login_attempts SET created_at = ? WHERE scope = ?",
            ((datetime.now(timezone.utc) - timedelta(minutes=16)).replace(microsecond=0).isoformat(), f"mat-global:{uid}"))
        assert global_suchen(f, "TEST-B-0001").status_code == 200
    print("Bremse bestanden.")


# --- Protokoll --------------------------------------------------------------------------------------------------

def test_protokoll():
    """Das Protokoll liest nur die Plattform-Verwaltung: neueste zuerst, je Zeile Zeit, Name, Art, Anfrage, Treffer und
    die Gliederungen der Treffer, seitenweise. Was älter als zwölf Monate ist, fällt heraus – beim Schreiben einer neuen
    Zeile, beim Neustart der Anwendung und beim Lesen."""
    from app.material.routes_global import NUR_VERWALTUNG
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        assert global_suchen(t.wart_a, "TEST-B-0001").status_code == 200
        assert steckbrief_holen(t.k["fuehrung"], token_von(t.art_b)).status_code == 200
        assert global_suchen(t.wart_a, "TEST-NIRGENDS-0815").status_code == 200
        r = t.adm.get(PROTOKOLL)
        assert r.status_code == 200 and (r.json["gesamt"], r.json["seite"], r.json["pro_seite"]) == (3, 1, 50), r.json
        e = r.json["eintraege"]
        assert [(x["name"], x["art"], x["anfrage"], x["treffer"], x["gliederungen"]) for x in e] == [
            ("wart", "suche", "TEST-NIRGENDS-0815", 0, []),
            ("fuehrung", "qr", t.art_b["inventory_no"], 1, ["OG Nachbarstadt"]),
            ("wart", "suche", "TEST-B-0001", 1, ["OG Nachbarstadt"])], e
        assert all(set(x) == {"id", "zeit", "name", "art", "anfrage", "treffer", "gliederungen"} for x in e), e
        assert datetime.fromisoformat(e[0]["zeit"]) >= datetime.fromisoformat(e[-1]["zeit"])
        # Nur die Verwaltung – Materialwarte (auch der Gliederung der Treffer), Führungskraft, Katalogpfleger und Prüfer
        # nicht; ohne Modulzugang ebenso 403, ohne Anmeldung 401.
        for c in (t.wart_a, t.wart_b, t.k["fuehrung"], t.k["katalog"], t.k["pruefer"], t.pruefer_b, t.k["nutzer"]):
            r = c.get(PROTOKOLL)
            assert r.status_code == 403 and r.json["error"] == NUR_VERWALTUNG, r.get_json()
        assert t.app.test_client().get(PROTOKOLL).status_code == 401
        # Seiten: Unsinn 400, hinter dem Ende leer.
        for s in ("abc", "0", "-1", "1.5"):
            assert t.adm.get(PROTOKOLL, query_string={"seite": s}).status_code == 400, s
        r = t.adm.get(PROTOKOLL, query_string={"seite": 2})
        assert r.status_code == 200 and r.json["eintraege"] == [] and r.json["gesamt"] == 3, r.json
        # Zwölf Monate: beim Lesen …
        alte_zeile(t.app, 366)
        alte_zeile(t.app, 300, "TEST-JUENGER-0001")
        r = t.adm.get(PROTOKOLL)
        assert [x["anfrage"] for x in r.json["eintraege"]][-1] == "TEST-JUENGER-0001" and r.json["gesamt"] == 4, r.json
        assert {z["anfrage"] for z in protokoll(t.app)} == {"TEST-B-0001", t.art_b["inventory_no"], "TEST-NIRGENDS-0815",
                                                             "TEST-JUENGER-0001"}
        # … beim Schreiben einer neuen Zeile (Suche wie QR) …
        alte_zeile(t.app, 400)
        assert global_suchen(t.wart_a, "TEST-B-0001").status_code == 200
        assert "TEST-ALT-0001" not in {z["anfrage"] for z in protokoll(t.app)}
        alte_zeile(t.app, 400)
        assert steckbrief_holen(t.wart_a, token_von(t.art_b)).status_code == 200
        assert "TEST-ALT-0001" not in {z["anfrage"] for z in protokoll(t.app)}
        # … und beim Neustart der Anwendung.
        alte_zeile(t.app, 366)
        make_app(tmp)
        anfragen = [z["anfrage"] for z in protokoll(t.app)]
        assert "TEST-ALT-0001" not in anfragen and "TEST-JUENGER-0001" in anfragen and len(anfragen) == 6, anfragen
        # Seitenweise: 50 je Seite.
        for n in range(50):
            alte_zeile(t.app, 1, f"TEST-SEITE-{n:04d}")
        r1, r2 = t.adm.get(PROTOKOLL).json, t.adm.get(PROTOKOLL, query_string={"seite": 2}).json
        assert len(r1["eintraege"]) == 50 and len(r2["eintraege"]) == 6 and r1["gesamt"] == r2["gesamt"] == 56
        assert not {x["id"] for x in r1["eintraege"]} & {x["id"] for x in r2["eintraege"]}
        # Angezeigt wird es als zugeklappter Abschnitt in der Nutzerverwaltung.
        html = t.adm.get("/admin").get_data(as_text=True)
        assert 'id="mat-globalsuche"' in html and "Globale Suchen (Modul Material)" in html, html[-800:]
        assert "js/admin_globalsuche.js" in html
    print("Protokoll bestanden.")


# --- QR-Steckbrief ----------------------------------------------------------------------------------------------

def test_qr_steckbrief():
    """POST /globalsuche/qr: erst nach Bestätigung (sonst 400, ohne Bremse und Protokoll); unbekanntes Token 404 wie
    „gibt es nicht“; ein fremder Artikel gibt denselben Steckbrief wie die Suche (Zeile „qr“ mit der Inventarnummer);
    ein eigener führt zum Artikel – ohne Bremse und Protokoll."""
    from app.material.services import globalsuche
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        w, uid = t.wart_a, t.k["wart_id"]
        token_b = token_von(t.art_b)
        for d in ({"token": token_b}, {"token": token_b, "bestaetigt": "ja"}, {"token": token_b, "bestaetigt": False}, {}):
            r = w.post(QR, json=d, headers=H)
            assert r.status_code == 400 and r.json["error"] == globalsuche.BESTAETIGEN_QR, (d, r.get_json())
        assert versuche(t.app, uid) == 0 and protokoll(t.app) == []
        unbekannt = steckbrief_holen(w, "GibtEsNicht-0000")
        assert unbekannt.status_code == 404 and unbekannt.json == {"error": "Artikel nicht gefunden."}, unbekannt.get_json()
        for token in ("", None, 123, ["x"]):
            r = steckbrief_holen(w, token)
            assert (r.status_code, r.get_json()) == (404, unbekannt.get_json()), (token, r.get_json())
        r = steckbrief_holen(w, token_b)
        assert r.status_code == 200 and set(r.json) == {"treffer", "mehr", "hinweis"}, r.get_json()
        assert r.json["mehr"] is False and r.json["hinweis"] == globalsuche.HINWEIS and len(r.json["treffer"]) == 1
        x = r.json["treffer"][0]
        assert set(x) == globalsuche.FELDER and x == global_suchen(t.k["fuehrung"], "TEST-B-0001").json["treffer"][0], x
        nichts_geheimes(t, r)
        r = steckbrief_holen(w, token_von(t.pers_b))
        assert r.json["treffer"][0]["ordner"] == "Lager Nachbarstadt / Fahrzeug NS / persönlicher Ordner", r.json
        nichts_geheimes(t, r)
        r = steckbrief_holen(w, token_von(t.gesp_b))
        assert r.json["treffer"][0]["ordner"] == "Lager Nachbarstadt" and r.json["treffer"][0]["sperre"] == "gesperrt"
        nichts_geheimes(t, r, "Gesperrt")
        p = [z for z in protokoll(t.app) if z["user_id"] == uid]
        assert [(z["art"], z["anfrage"], z["treffer"], json.loads(z["item_ids"])) for z in p] == [
            ("qr", t.art_b["inventory_no"], 1, [t.art_b["id"]]), ("qr", t.pers_b["inventory_no"], 1, [t.pers_b["id"]]),
            ("qr", t.gesp_b["inventory_no"], 1, [t.gesp_b["id"]])], p
        # Eigener Artikel (auch gesperrt, über die Heimat): weiter zum Artikel, nichts gezählt, nichts protokolliert.
        vorher = (versuche(t.app, uid), len(protokoll(t.app)))
        assert steckbrief_holen(w, token_von(t.art_a)).json == {"weiter": f"/material/artikel/{t.art_a['id']}"}
        assert steckbrief_holen(t.wart_b, token_von(t.gesp_b)).json == {"weiter": f"/material/artikel/{t.gesp_b['id']}"}
        assert (versuche(t.app, uid), len(protokoll(t.app))) == vorher
        # Ohne Anmeldung 401, ohne Modulzugang 403.
        assert t.app.test_client().post(QR, json={"token": token_b, "bestaetigt": True}, headers=H).status_code == 401
        assert steckbrief_holen(t.k["nutzer"], token_b).status_code == 403
    print("QR-Steckbrief bestanden.")


# --- Entscheidungen vom 18.10.2026 -------------------------------------------------------------------------------

def test_sperrwort():
    """Entscheidung 1: Der Steckbrief trägt immer „sperre“ – genau ein Wort („gesperrt“, „verloren gemeldet“,
    „ausgesondert“) oder null bei frei, ohne Grund und Datum; in der Suche wie im QR-Steckbrief. Auch ein Sperrgrund,
    der einen Rückruf nennt, geht nicht hinaus."""
    from app.material.services import globalsuche
    assert not hasattr(globalsuche, "STECKBRIEF_MIT_SPERRE")
    assert "sperre" in globalsuche.FELDER and len(globalsuche.FELDER) == 15
    assert set(globalsuche.SPERRE.values()) == {"gesperrt", "verloren gemeldet", "ausgesondert"}
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        sql(t.app, "UPDATE mat_item SET lock_reason = 'Rückruf Testwerk geheim' WHERE id = ?", (t.verl_b["id"],))
        for q, sperre in (("TEST-G-0003", "gesperrt"), ("TEST-G-0005", "verloren gemeldet"),
                          ("TEST-G-0004", "ausgesondert"), ("TEST-B-0001", None), ("TEST-G-0001", None)):
            r = global_suchen(t.wart_a, q)
            x = r.json["treffer"][0]
            assert set(x) == globalsuche.FELDER and x["sperre"] == sperre, (q, x)
            text = r.get_data(as_text=True)
            for wort in (GEHEIM[1], "Rückruf", "lock_", "Gesperrt", "Ausgesondert"):
                assert wort not in text, (q, wort, text)
        for a, sperre in ((t.aus_b, "ausgesondert"), (t.verl_b, "verloren gemeldet"), (t.gesp_b, "gesperrt"),
                          (t.art_b, None)):
            r = steckbrief_holen(t.wart_a, token_von(a))
            x = r.json["treffer"][0]
            assert set(x) == globalsuche.FELDER and x["sperre"] == sperre, x
            assert "Rückruf" not in r.get_data(as_text=True) and GEHEIM[1] not in r.get_data(as_text=True)
    # Angebot, Rückfrage und QR-Ansicht beschreiben den Inhalt wie das Ergebnis (Prüfung der Nachbesserung): alle drei
    # Sperrwörter in der Rückfrage, kein „Nur Stammdaten und Zugehörigkeit“ ohne den Sperrzustand.
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    glob, suche = (open(os.path.join(wurzel, f"app/material/static/{d}.js"), encoding="utf-8").read()
                   for d in ("global", "suche"))
    erklaerung = "".join(re.findall(r'"([^"]*)"', re.search(r"const ERKLAERUNG = (.*?);\n", glob, re.S).group(1)))
    assert "gesperrt, verloren gemeldet oder ausgesondert" in erklaerung, erklaerung
    for js in (glob, suche):
        assert "Nur Stammdaten und Zugehörigkeit" not in js and "Nur Stammdaten, Zugehörigkeit und Sperrzustand" in js
    print("Sperrwort bestanden.")


def test_angebot():
    """Entscheidung 2: Angeboten wird die globale Suche zu jeder tauglichen Anfrage (4–80 Zeichen, keine vergebene
    Nummer) – unabhängig von lokalen Treffern, auch wenn ein eigener Artikel genau diese Nummer hat. Nur wer alles
    sieht (Plattform-Verwaltung), bekommt kein Angebot; ein Konto ganz ohne Bestand (Katalogpfleger) schon. Die
    Schalter der Lieferung sind fort."""
    from flask import g

    from app.material.services import globalsuche
    for name in ("ANGEBOT", "ANGEBOTE", "IM_BEREICH", "exakt_sichtbar"):
        assert not hasattr(globalsuche, name), name
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        _, kp_id = neues_konto(t.app, "katalog2@example.org", name="Katalogpflege Test", mat_katalog=True)
        adm_id = zeilen(t.app, "SELECT id FROM users WHERE email = 'admin@example.org'")[0]["id"]
        fragen = ("TEST-A-0001", " test-a-0001 ", "TEST-B-0001", "TEST-A-000", "TEST", "ABC", "x" * 81, "STR-000001",
                  "M-000001")
        tauglich = [True] * 5 + [False] * 4

        def als(uid):
            with t.app.test_request_context():
                from app import db
                g.user = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
                return [globalsuche.angebot(q) for q in fragen], globalsuche.sieht_alles()
        assert als(t.k["wart_id"]) == (tauglich, False)          # eigene, fremde und Teilnummern
        assert als(kp_id) == (tauglich, False)                   # ohne Bestand (artikel_filter „0“)
        assert als(adm_id) == ([False] * len(fragen), True)      # sieht alles
    print("Angebot bestanden.")


def test_nur_fremde():
    """Entscheidung 2: Dieselbe Seriennummer in A (sichtbar) und B (fremd) – die globale Suche von A liefert nur die
    Artikel aus B und protokolliert nur deren Kennungen; aus Sicht von B ist es umgekehrt. Die Bedingung steht in der
    Abfrage: Elf eigene Artikel mit kleineren Kennungen verdrängen die fremden nicht aus den zehn Treffern, und „mehr“
    zählt nur Fremde. Bestätigung, Bremse und Protokoll wie sonst; wer beide Gliederungen sieht, findet global
    nichts mehr."""
    from app.material.services import globalsuche
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        produkte = []
        for n in range(13):
            r = t.k["katalog"].post("/api/material/produkte", json={
                "category_id": t.ids["karabiner"], "manufacturer": "Testwerk", "model": f"Testkarabiner {n + 1:02d}",
                "material_kind": "metall_hardware", "interval_months": 12})
            assert r.status_code == 201, r.get_json()
            produkte.append(r.json["produkt"]["id"])
        # Erst elf in A (kleinere Kennungen), dann zwei in B – alle mit derselben Seriennummer, je ein anderes Produkt.
        eigen = [neuer_artikel(t.wart_a, produkte[n], t.lager_a, serial_no="TEST-BEIDE-0001")["id"] for n in range(11)]
        fremd = [neuer_artikel(t.wart_b, produkte[n], t.lager_b, serial_no="TEST-BEIDE-0001")["id"] for n in (11, 12)]
        # Die lokale Suche von A findet die eigenen und bietet die globale trotzdem an.
        s = t.wart_a.get("/api/material/suche", query_string={"q": "TEST-BEIDE-0001"}).json
        assert s["gesamt"] == 11 and s["exakt_lokal"] is True and s["global_angebot"] is True, s
        vorher = len(protokoll(t.app))
        r = global_suchen(t.wart_a, "test-beide-0001")
        assert r.status_code == 200 and r.json["mehr"] is False, r.get_json()
        assert [(x["modell"], x["gliederung"]) for x in r.json["treffer"]] == [
            ("Testkarabiner 12", "OG Nachbarstadt"), ("Testkarabiner 13", "OG Nachbarstadt")], r.json
        nichts_geheimes(t, r)
        p = protokoll(t.app)
        assert len(p) == vorher + 1 and (p[-1]["art"], p[-1]["anfrage"], p[-1]["treffer"]) == (
            "suche", "test-beide-0001", 2) and json.loads(p[-1]["item_ids"]) == fremd, p[-1]
        assert versuche(t.app, t.k["wart_id"]) == 1
        # Aus Sicht von B sind die elf aus A fremd: zehn Treffer (die kleinsten Kennungen) und „mehr“.
        r = global_suchen(t.wart_b, "TEST-BEIDE-0001")
        assert len(r.json["treffer"]) == 10 and r.json["mehr"] is True, r.json
        assert {x["gliederung"] for x in r.json["treffer"]} == {"OG Musterstadt"}
        assert json.loads(protokoll(t.app)[-1]["item_ids"]) == eigen[:10]
        # Genau zehn fremde: „mehr“ ist falsch – die eigenen zwei in B zählen nicht mit.
        sql(t.app, "UPDATE mat_item SET serial_no = 'TEST-ANDERS-0001' WHERE id = ?", (eigen[-1],))
        r = global_suchen(t.wart_b, "TEST-BEIDE-0001")
        assert len(r.json["treffer"]) == 10 and r.json["mehr"] is False, r.json
        # Ohne Bestätigung nichts – nicht gezählt, nicht protokolliert.
        n = len(protokoll(t.app))
        r = t.wart_a.post(SUCHE, json={"q": "TEST-BEIDE-0001"}, headers=H)
        assert r.status_code == 400 and r.json["error"] == globalsuche.BESTAETIGEN
        assert len(protokoll(t.app)) == n and versuche(t.app, t.k["wart_id"]) == 1
        # Wer beide Gliederungen sieht, findet global nichts mehr – die normale Suche hat alle.
        freigeben(t.adm, t.b, t.k["wart_id"], "lesen")
        r = global_suchen(t.wart_a, "TEST-BEIDE-0001")
        assert r.status_code == 200 and r.json["treffer"] == [] and r.json["mehr"] is False, r.json
        assert json.loads(protokoll(t.app)[-1]["item_ids"]) == [] and protokoll(t.app)[-1]["treffer"] == 0
        assert t.wart_a.get("/api/material/suche", query_string={"q": "TEST-BEIDE-0001"}).json["gesamt"] == 12
    print("Nur fremde Treffer bestanden.")


def test_teilfreigabe():
    """Prüfung der Nachbesserung: Ein externer Prüfer mit Freigabe nur am Lager von A findet global auch einen Artikel
    aus dem Fahrzeug von A – derselben Gliederung, aber außerhalb seiner Freigabe – mit „OG Musterstadt“ als
    Zugehörigkeit. „Andere Gliederungen“ stimmte also nicht: Angebot, Trennlinie, Rückfrage und leeres Ergebnis
    sprechen von „außerhalb deines Bereichs“, der Hinweis von der Freigabe am Ordner statt „in der Gliederung“."""
    from app.material.services import globalsuche
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        fahrzeug_a = ordner_neu(t.wart_a, t.a, "Fahrzeug Musterstadt", "fahrzeug")
        im_lager = neuer_artikel(t.wart_a, t.ids["hms"], t.lager_a, serial_no="TEST-TEIL-0001")
        im_fahrzeug = neuer_artikel(t.wart_a, t.ids["gurt"], fahrzeug_a, serial_no="TEST-TEIL-0001",
                                    manufactured_on="2024-01")
        extern, extern_id = neues_konto(t.app, "extern@example.org", name="Prüfer extern Test", mat_pruefer=True,
                                        urkundennummer="1012-9002")
        freigeben(t.adm, t.lager_a, extern_id, "pruefen")
        # Lokal sieht er nur den aus dem Lager – und bekommt das Angebot.
        s = extern.get("/api/material/suche", query_string={"q": "TEST-TEIL-0001"}).json
        assert [x["id"] for x in s["treffer"]] == [im_lager["id"]] and s["exakt_lokal"] is True, s
        assert s["global_angebot"] is True, s
        # Global der aus dem Fahrzeug: dieselbe Gliederung, außerhalb seiner Freigabe.
        r = global_suchen(extern, "TEST-TEIL-0001")
        assert r.status_code == 200 and r.json["mehr"] is False, r.get_json()
        assert [(x["inventory_no"], x["gliederung"], x["ordner"]) for x in r.json["treffer"]] == [
            (im_fahrzeug["inventory_no"], "OG Musterstadt", "Fahrzeug Musterstadt")], r.json
        assert json.loads(protokoll(t.app)[-1]["item_ids"]) == [im_fahrzeug["id"]]
        assert r.json["hinweis"] == globalsuche.HINWEIS and "in der Gliederung" not in globalsuche.HINWEIS
        assert "Ordner" in globalsuche.HINWEIS
        # Der Materialwart von A sieht beide – global findet er nichts.
        assert global_suchen(t.wart_a, "TEST-TEIL-0001").json["treffer"] == []
    # Die Texte der Oberfläche: nirgends „aus/in anderen Gliederungen“ als Überschrift, Knopf oder leeres Ergebnis.
    for datei in ("global", "suche"):
        js = open(os.path.join(wurzel, f"app/material/static/{datei}.js"), encoding="utf-8").read()
        assert "Außerhalb deines Bereichs" in js, datei
        for alt in ("Aus anderen Gliederungen", "In anderen Gliederungen", "Suche in anderen Gliederungen",
                    "Artikel anderer Gliederungen"):
            assert alt not in js, (datei, alt)
    print("Teilfreigabe bestanden.")


def seiten_daten(r):
    """DATEN einer Modulseite (data-daten im HTML)."""
    html = r.get_data(as_text=True)
    return json.loads(re.search(r'data-daten="([^"]*)"', html).group(1).replace("&#34;", '"').replace("&quot;", '"'))


def test_eindeutiger_treffer():
    """Prüfung der Nachbesserung, Entscheidung 2 („immer angeboten“): Ein eindeutiger eigener Treffer öffnet den
    Artikel weiter direkt – taugt die Anfrage für die globale Suche, nimmt die Weiterleitung sie mit (?q=), und die
    Artikelseite bekommt sie als „suche“, für das Angebot unter dem Kopf. Auch bei einem Teiltreffer. Ohne q bei
    Inventarnummern, zu kurzen Anfragen und für die Plattform-Verwaltung; das Laden zählt nicht in der Bremse und
    steht nicht im Protokoll; ein fremder Artikel bleibt 404, auch mit q."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        w, a = t.wart_a, t.art_a
        for q in ("TEST-A-0001", "test-a-0001", "TEST-A-000"):
            r = w.get("/material/suche", query_string={"q": q})
            assert r.status_code == 302, (q, r.status_code)
            assert r.headers["Location"].endswith(f"/material/artikel/{a['id']}?q={q}"), r.headers["Location"]
            r = w.get(f"/material/artikel/{a['id']}", query_string={"q": q})
            assert r.status_code == 200 and seiten_daten(r) == {"id": a["id"], "suche": q}, seiten_daten(r)
        # Inventarnummern taugen nicht für die globale Suche: Weiterleitung ohne q.
        r = w.get("/material/suche", query_string={"q": a["inventory_no"]})
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/material/artikel/{a['id']}"), r.headers
        # Was nicht taugt, übergeht die Artikelseite.
        for q in (a["inventory_no"], "STR-000001", "ABC", "x" * 81, ""):
            assert seiten_daten(w.get(f"/material/artikel/{a['id']}", query_string={"q": q})) == {"id": a["id"]}, q
        # Die Plattform-Verwaltung sieht alles: kein Angebot, also auch kein q.
        r = t.adm.get("/material/suche", query_string={"q": "TEST-B-0001"})
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/material/artikel/{t.art_b['id']}"), r.headers
        r = t.adm.get(f"/material/artikel/{t.art_b['id']}", query_string={"q": "TEST-B-0001"})
        assert seiten_daten(r) == {"id": t.art_b["id"]}
        # Fremdes bleibt fremd – auch mit q.
        r = w.get(f"/material/artikel/{t.art_b['id']}", query_string={"q": "TEST-B-0001"})
        assert r.status_code == 404 and "TEST-B-0001" not in r.get_data(as_text=True)
        assert protokoll(t.app) == [] and versuche(t.app, t.k["wart_id"]) == 0
    print("Eindeutiger Treffer bestanden.")


# --- Erst mit Paket A1R -----------------------------------------------------------------------------------------

def test_angebot_ueber_suche():
    """GET /suche liefert exakt_lokal und global_angebot (A1R, über globalsuche.angebot): Angebot bei fremder und bei
    eigener Seriennummer, auch neben Teiltreffern – exakt_lokal sagt, ob ein eigener Artikel genau diese Nummer hat.
    Der Katalogpfleger ohne Bestand bekommt das Angebot (und keinen Treffer), die Plattform-Verwaltung nie."""
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        w = t.wart_a
        r = w.get("/api/material/suche", query_string={"q": "TEST-B-0001"})
        assert r.status_code == 200 and r.json["treffer"] == [] and r.json["exakt_lokal"] is False, r.get_json()
        assert r.json["global_angebot"] is True, r.json
        r = w.get("/api/material/suche", query_string={"q": "test-a-0001"})
        assert r.json["gesamt"] == 1 and r.json["exakt_lokal"] is True and r.json["global_angebot"] is True, r.json
        r = w.get("/api/material/suche", query_string={"q": "TEST-A-000"})               # Teiltreffer, kein exakter
        assert r.json["gesamt"] >= 1 and r.json["exakt_lokal"] is False and r.json["global_angebot"] is True, r.json
        for q in ("ABC", "M-000001", "STR-000001"):
            assert w.get("/api/material/suche", query_string={"q": q}).json["global_angebot"] is False, q
        kp, _ = neues_konto(t.app, "katalog2@example.org", name="Katalogpflege Test", mat_katalog=True)
        r = kp.get("/api/material/suche", query_string={"q": "TEST-B-0001"})
        assert r.status_code == 200 and r.json["treffer"] == [] and r.json["global_angebot"] is True, r.get_json()
        for q in ("TEST-A-0001", "TEST-B-0001", "TEST-NIRGENDS-0815"):
            r = t.adm.get("/api/material/suche", query_string={"q": q})
            assert r.status_code == 200 and r.json["global_angebot"] is False, (q, r.json)
        assert t.adm.get("/api/material/suche", query_string={"q": "TEST-B-0001"}).json["gesamt"] == 1
        assert protokoll(t.app) == []                     # die lokale Suche protokolliert nichts
    print("Angebot über /suche bestanden.")


def test_qr_seite_fremd():
    """/m/<token> eines fremden Artikels (A1R): die Seite „fremd“ ohne Artikeldaten im HTML – nur das Token für den
    Knopf –, kein Protokoll beim Laden; der Steckbrief erst nach Bestätigung. Ein eigener Artikel: Weiterleitung."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        w = t.wart_a
        token_b = token_von(t.art_b)
        r = w.get(f"/m/{token_b}")
        assert r.status_code == 200, r.status_code
        html = r.get_data(as_text=True)
        assert 'data-ansicht="fremd"' in html, html[-600:]
        daten = json.loads(re.search(r'data-daten="([^"]*)"', html).group(1).replace("&#34;", '"').replace("&quot;", '"'))
        assert daten == {"token": token_b}, daten
        for wort in (t.art_b["inventory_no"], "TEST-B-0001", "OG Nachbarstadt", "Lager Nachbarstadt", "HMS Beta",
                     "mat-banner") + GEHEIM:
            assert wort not in html, wort
        assert protokoll(t.app) == []
        assert steckbrief_holen(w, token_b).json["treffer"][0]["inventory_no"] == t.art_b["inventory_no"]
        assert [z["art"] for z in protokoll(t.app)] == ["qr"]
        r = w.get(f"/m/{token_von(t.art_a)}")
        assert r.status_code == 302 and r.headers["Location"].endswith(f"/material/artikel/{t.art_a['id']}"), r.headers
    print("QR-Seite fremd bestanden.")


def test_bremse_mit_dublette():
    """Die fremde Dublette beim Anlegen (A1R, 3.7) zählt in derselben Bremse und steht im Protokoll (Art „dublette“):
    neun Suchen und eine Dublette, dann ist die elfte Suche 429 – ebenso die nächste Dublette."""
    from app.material.services import globalprotokoll
    with tempfile.TemporaryDirectory() as tmp:
        t = zwei_gliederungen(tmp)
        w = t.wart_a
        for _ in range(9):
            assert global_suchen(w, "TEST-B-0001").status_code == 200
        r = w.post("/api/material/artikel", json={"product_id": t.ids["hms"], "folder_id": t.lager_a,
                                                  "serial_no": "TEST-B-0001"}, headers=H)
        assert r.status_code == 409 and t.art_b["inventory_no"] not in r.json["error"], r.get_json()
        assert "Nachbarstadt" not in r.json["error"], r.get_json()
        assert [z["art"] for z in protokoll(t.app)][-1] == "dublette"
        r = global_suchen(w, "TEST-B-0001")
        assert r.status_code == 429 and r.json["error"] == globalprotokoll.ZU_VIELE, r.get_json()
        r = w.post("/api/material/artikel", json={"product_id": t.ids["hms"], "folder_id": t.lager_a,
                                                  "serial_no": "TEST-B-0001"}, headers=H)
        assert r.status_code == 429, r.get_json()
        assert len(protokoll(t.app)) == 10
    print("Bremse mit Dublette bestanden.")


if __name__ == "__main__":
    for test in (test_eingaben, test_steckbrief, test_zehn_und_mehr, test_bremse, test_protokoll, test_qr_steckbrief,
                 test_sperrwort, test_angebot, test_nur_fremde, test_teilfreigabe, test_eindeutiger_treffer,
                 test_angebot_ueber_suche, test_qr_seite_fremd, test_bremse_mit_dublette):
        test()
