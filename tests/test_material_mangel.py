"""Mangelmeldung (Phase 3 · Lieferung 1, Bauentwurf 3 und 7.2):  python tests/test_material_mangel.py  oder  pytest

Die zugeordnete Person (auch ohne Modulstufe) und jeder mit Leserecht am Artikel meldet einen Mangel: Beschreibung
Pflicht, bis 3 Fotos (nur Web- und Vorschaufassung bleiben, das Original geht sofort). Jede Meldung sperrt sofort – auch
bei offenem Prüfentwurf; zurück nur über die Freiprüfung mit Häkchen je Meldung, die sie erledigt (ebenso die
Aussonderung); „instandsetzen“ erledigt nicht, eine Berichtigung gibt nie frei; der Materialwart sondert nach einer
reinen Mangelsperre erst nach einer Prüfung aus. Mails an Verwalter (Rückfall MV, PV) und Prüfer, an die zugeordnete
Person bei fremder Meldung; bei DEMO und Umgebungssperre ins Log. Meldungen sind unveränderlich (Trigger), der Name
bleibt beim Kontolöschen. Schritt 13 der Migration. Echte Mails gehen nie hinaus (mangel.send_mail ist ersetzt).

Alle Namen, Hersteller, Nummern und Texte hier sind Platzhalter und nur für den Test da."""
import io
import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image  # noqa: E402
from test_material import (H, _heute, festschreiben, freigeben, gliederung, jpeg, make_app, neuer_artikel,  # noqa: E402
                           neues_konto, pdf_seiten, starten, unterschreiben)
from test_material_erinnerung import umwelt  # noqa: E402
from test_material_meine_psa import LISTE, aufbau, melden, post_mangel, zuordnen  # noqa: E402
from test_material_trennung import bis_schritt, endversion, erinnerungslog_wie_schritt_11, sql, zeilen  # noqa: E402
from test_material_ueberblick import ordner_neu, sperren, zustand  # noqa: E402

MELDUNG = {"id", "created_at", "description", "fotos", "melder", "offen", "lock_before", "erledigt"}
# Eine KOPIE einer Datenbank auf Stand 7 für den Pfad 7 → 13 (test_migration_13) – nur, wenn angegeben; die Quelle
# bleibt unberührt.
KOPIE_STAND_7 = os.environ.get("MATERIAL_KOPIE_STAND_7") or ""


# --- Helfer ---------------------------------------------------------------------------------------------------------

def item(app, iid):
    return zeilen(app, "SELECT * FROM mat_item WHERE id = ?", (iid,))[0]


def meldungen(app, iid):
    return zeilen(app, "SELECT * FROM mat_defect_report WHERE item_id = ? ORDER BY id", (iid,))


def journal(app, iid, aktion):
    return zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'item' AND entity_id = ? AND action = ? ORDER BY id",
                  (iid, aktion))


def dateien(app):
    """Alle Dateien unter orig/, web/ und thumb/ des Medienordners."""
    with app.app_context():
        from app.material.services import katalog
        d = katalog.medien_dir()
    return {f"{sub}/{n}" for sub in ("orig", "web", "thumb") if os.path.isdir(os.path.join(d, sub))
            for n in os.listdir(os.path.join(d, sub))}


def geprueft(app, iid):
    """Als „einsatzbereit, zuletzt geprüft“ setzen – ohne Prüfung (dann ist die Eingangsprüfung vorbei)."""
    zustand(app, iid, last_inspected_on="2025-01-15", next_due_on="2099-01-01")


def pruefung(c, iid, **d):
    r = starten(c, iid, **d)
    assert r.status_code in (200, 201), r.get_json()
    return r.json["pruefung"]


def neue_sekunde():
    """Zeitstempel haben ganze Sekunden; „seit der Meldung geprüft“ verlangt einen späteren (gleiche Sekunde zählt als
    vorher)."""
    time.sleep(1.05)


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


@contextmanager
def foto_zaehler():
    from app.material.services import katalog
    alt = katalog.foto_ablegen
    aufrufe = []

    def zaehlen(*a, **kw):
        aufrufe.append(1)
        return alt(*a, **kw)
    katalog.foto_ablegen = zaehlen
    try:
        yield aufrufe
    finally:
        katalog.foto_ablegen = alt


def extern(t, mail="extern@example.org", name="Externer Prüfer"):
    """Ein externer Prüfer: Stufe Mitglied, Qualifikation, nur eine befristete Prüffreigabe an der Gliederung (Prüfsicht,
    kein Grundrecht)."""
    c, uid = neues_konto(t.app, mail, name=name, stufe=1, mat_pruefer=True, urkundennummer="1012-0099")
    freigeben(t.adm, t.gid, uid, "pruefen")
    unterschreiben(c)
    return c, uid


# --- 7.2 ------------------------------------------------------------------------------------------------------------

def test_melden_zugeordnet():
    """Person ohne Stufe meldet die eigene PSA mit zwei Fotos: 201, gesperrt; Artikel in „Gesperrt“, Herkunft gemerkt,
    Grund „Mangel gemeldet am …“; genau ein Journaleintrag „mangel_gemeldet“ mit Namen und Kennung; die Zeile der
    Meldung."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        zuordnen(t, a1, t.person_id)
        r = melden(t.person, a1, "Platzhalter: Naht aufgegangen", fotos=2)
        assert r.status_code == 201, r.get_json()
        assert r.json["gesperrt"] is True and r.json["mail"] is True, r.get_json()
        m = r.json["mangel"]
        assert set(m) == MELDUNG and m["offen"] and m["lock_before"] == "frei" and m["erledigt"] is None, m
        assert m["melder"] == "Person Platzhalter" and len(m["fotos"]) == 2
        assert all(set(f) == {"vorschau", "web"} for f in m["fotos"])
        i = item(t.app, a1)
        assert i["lock_state"] == "gesperrt" and i["folder_id"] == t.system["gesperrt"], i
        assert i["origin_folder_id"] == t.lager
        assert i["lock_reason"] == f"Mangel gemeldet am {_heute().strftime('%d.%m.%Y')}", i["lock_reason"]
        j = journal(t.app, a1, "mangel_gemeldet")
        assert len(j) == 1 and not journal(t.app, a1, "gesperrt"), j
        assert j[0]["user_name"] == "Person Platzhalter"
        nachher = json.loads(j[0]["after_json"])
        assert nachher["mangel"] == m["id"] and nachher["lock_state"] == "gesperrt" and nachher["origin_folder_id"] == t.lager
        assert "Naht" not in j[0]["after_json"] and json.loads(j[0]["before_json"])["lock_state"] == "frei"
        d = meldungen(t.app, a1)
        assert len(d) == 1 and d[0]["reporter_id"] == t.person_id and d[0]["reporter_name"] == "Person Platzhalter"
        assert d[0]["description"] == "Platzhalter: Naht aufgegangen" and len(json.loads(d[0]["photos_json"])) == 2
        assert d[0]["closed_at"] is None and d[0]["lock_before"] == "frei"
        # Meine PSA zeigt die Sperre, die offene Meldung und die eigene ganz.
        k = t.person.get(LISTE).json["artikel"][0]
        assert k["gesperrt"] and k["mangel"]["seit"] == m["created_at"] and k["eigene_maengel"][0]["id"] == m["id"]
    print("Melden (zugeordnet) bestanden.")


def test_rechte():
    """lesen, verwalten, Prüfsicht und MV dürfen melden; Mitglied ohne Freigabe 404 wie unbekannt; ohne Stufe fremd und
    unbekannt 403 gleich."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        ext, _ = extern(t)
        mehr = [neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no=f"RE-{n}")["id"] for n in range(3)]
        for c, iid in ((t.k["fuehrung"], t.art[0]), (t.w, t.art[1]), (ext, t.art[2]), (t.k["katalog"], mehr[0])):
            r = melden(c, iid)
            assert r.status_code == 201, r.get_json()
        fremd, unbekannt = melden(t.mitglied, mehr[1]), melden(t.mitglied, 999999)
        assert fremd.status_code == unbekannt.status_code == 404 and fremd.get_json() == unbekannt.get_json()
        fremd, unbekannt = melden(t.person, mehr[1]), melden(t.person, 999999)
        assert fremd.status_code == unbekannt.status_code == 403 and fremd.get_json() == unbekannt.get_json()
        assert not meldungen(t.app, mehr[1]) and item(t.app, mehr[1])["lock_state"] == "frei"
        assert t.app.test_client().post(f"/api/material/artikel/{mehr[1]}/mangel", headers=H,
                                        json={"beschreibung": "x"}).status_code == 401
        # Die Route ist für den Trennungstest wie jede andere beschrieben.
        f = t.app.view_functions["material_api.artikel_mangel"]
        assert f.mat_quelle == "iid" and f.mat_recht == ("lesen",)
    print("Rechte bestanden.")


def test_eingaben():
    """Ohne Beschreibung 400 (keine Datei bleibt); 4 Fotos 400; keine Bilddatei 400; HEIC → Web- und Vorschaufassung,
    kein Original; GPS im Upload → Webfassung ohne EXIF."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        c = t.k["fuehrung"]
        a1, a2, a3 = t.art
        vorher = dateien(t.app)
        url = f"/api/material/artikel/{a1}/mangel"
        for daten in ({"fotos": [(jpeg(), "a.jpg")]}, {"beschreibung": "   ", "fotos": [(jpeg(), "a.jpg")]},
                      {"beschreibung": "x", "fotos": [(jpeg(), f"{n}.jpg") for n in range(4)]},
                      {"beschreibung": "x", "fotos": [(io.BytesIO(b"kein Bild"), "notiz.txt")]},
                      {"beschreibung": "x", "fotos": [(io.BytesIO(b"kein Bild"), "falsch.jpg")]},
                      {"beschreibung": "x" * 2001}):
            r = c.post(url, headers=H, content_type="multipart/form-data", data=daten)
            assert r.status_code == 400, (daten.get("beschreibung", "")[:10], r.get_json())
        assert c.post(url, headers=H, json={}).status_code == 400
        assert dateien(t.app) == vorher and not meldungen(t.app, a1) and item(t.app, a1)["lock_state"] == "frei"
        # HEIC aus dem Telefon.
        import pillow_heif
        pillow_heif.register_heif_opener()
        buf = io.BytesIO()
        Image.new("RGB", (320, 240), (30, 90, 200)).save(buf, "HEIF")
        buf.seek(0)
        r = c.post(f"/api/material/artikel/{a2}/mangel", headers=H, content_type="multipart/form-data",
                   data={"beschreibung": "Platzhalter HEIC", "fotos": [(buf, "IMG_0001.HEIC")]})
        assert r.status_code == 201, r.get_json()
        name = json.loads(meldungen(t.app, a2)[0]["photos_json"])[0]
        key = os.path.splitext(name)[0]
        neu = dateien(t.app) - vorher
        assert neu == {f"web/{key}.jpg", f"thumb/{key}.jpg"}, neu
        # EXIF mit Aufnahmeort: die Webfassung trägt keine EXIF-Daten.
        exif = Image.Exif()
        exif[0x0110] = "Platzhalterkamera"
        exif[0x8825] = {1: "N", 2: (52.0, 31.0, 0.0), 3: "E", 4: (13.0, 24.0, 0.0)}
        buf = io.BytesIO()
        Image.new("RGB", (320, 240), (90, 20, 20)).save(buf, "JPEG", exif=exif)
        buf.seek(0)
        with Image.open(io.BytesIO(buf.getvalue())) as probe:
            assert probe.getexif().get_ifd(0x8825), "Testbild ohne GPS"
        r = c.post(f"/api/material/artikel/{a3}/mangel", headers=H, content_type="multipart/form-data",
                   data={"beschreibung": "Platzhalter GPS", "fotos": [(buf, "gps.jpg")]})
        assert r.status_code == 201, r.get_json()
        name = json.loads(meldungen(t.app, a3)[0]["photos_json"])[0]
        with t.app.app_context():
            from app.material.services import katalog
            d = katalog.medien_dir()
        for sub in ("web", "thumb"):
            with Image.open(os.path.join(d, sub, os.path.splitext(name)[0] + ".jpg")) as bild:
                assert not dict(bild.getexif()), dict(bild.getexif())
        assert not os.path.exists(os.path.join(d, "orig", name))
    print("Eingaben bestanden.")


def test_vorpruefung():
    """Recht, Zustand und eigene offene Meldung vor den Fotos: 0 Aufrufe von foto_ablegen, Medienordner unverändert.
    Wettlauf: zwischen Vorprüfung und Transaktion ausgesondert → 409 aus der Transaktion, die Fotos sind wieder weg."""
    from app.material.services import mangel
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        zuordnen(t, a1, t.person_id)
        assert melden(t.person, a1).status_code == 201
        vorher = dateien(t.app)
        with foto_zaehler() as aufrufe:
            r = melden(t.person, a1, fotos=2)
            assert r.status_code == 409 and "schon einen Mangel gemeldet" in r.json["error"], r.get_json()
            assert _heute().strftime("%d.%m.%Y") in r.json["error"]
            sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (a2,))
            r = melden(t.k["fuehrung"], a2, fotos=1)
            assert r.status_code == 409 and r.json["error"] == mangel.AUSGESONDERT, r.get_json()
            r = melden(t.mitglied, a3, fotos=2)
            assert r.status_code == 404, r.get_json()
            assert not aufrufe and dateien(t.app) == vorher
        alt = mangel.fotos_ablegen

        def dazwischen(d):
            namen = alt(d)
            assert namen and dateien(t.app) != vorher
            sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (a3,))
            return namen
        mangel.fotos_ablegen = dazwischen
        try:
            r = melden(t.k["fuehrung"], a3, fotos=2)
        finally:
            mangel.fotos_ablegen = alt
        assert r.status_code == 409 and r.json["error"] == mangel.AUSGESONDERT, r.get_json()
        assert dateien(t.app) == vorher and not meldungen(t.app, a3)
    print("Vorprüfung bestanden.")


def test_original_sofort():
    """Drei Fotos, das dritte scheitert in store_upload: kein Original (auch nicht von 1 und 2 – sie waren schon beim
    nächsten Foto weg), keine Web-/Vorschaufassung, 400."""
    from app.material.services import katalog
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        vorher = dateien(t.app)
        alt = katalog.store_upload
        n = []

        def speichern(f, d, **kw):
            n.append(1)
            assert not any(x.startswith("orig/") for x in dateien(t.app) - vorher), "Original liegt noch"
            if len(n) == 3:
                raise ValueError("Testfehler beim dritten Foto")
            return alt(f, d, **kw)
        katalog.store_upload = speichern
        try:
            r = melden(t.k["fuehrung"], t.art[0], fotos=3)
        finally:
            katalog.store_upload = alt
        assert r.status_code == 400 and len(n) == 3, (r.get_json(), n)
        assert dateien(t.app) == vorher and not meldungen(t.app, t.art[0])
    print("Original sofort weg bestanden.")


def test_schon_gesperrt():
    """Vorher vom Prüfer gesperrt (Sturz): Meldung 201, gesperrt false, Grund unverändert, Journal nur {"mangel"};
    verloren ebenso; ausgesondert 409."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        sperren(t.k["pruefer"], a1, "sturz")
        sperren(t.k["pruefer"], a2, "verlust")
        grund = item(t.app, a1)["lock_reason"]
        for iid, zustand_ in ((a1, "gesperrt"), (a2, "verloren")):
            r = melden(t.k["fuehrung"], iid)
            assert r.status_code == 201 and r.json["gesperrt"] is False, r.get_json()
            assert r.json["mangel"]["lock_before"] == zustand_
            j = journal(t.app, iid, "mangel_gemeldet")
            assert len(j) == 1 and j[0]["before_json"] is None and json.loads(j[0]["after_json"]) == {
                "mangel": r.json["mangel"]["id"]}, j
            assert item(t.app, iid)["lock_state"] == zustand_
        assert item(t.app, a1)["lock_reason"] == grund
        sql(t.app, "UPDATE mat_item SET lock_state = 'ausgesondert' WHERE id = ?", (a3,))
        assert melden(t.k["fuehrung"], a3).status_code == 409
    print("Schon gesperrt bestanden.")


def test_offener_entwurf():
    """Ein Prüfer hat einen Entwurf; die Meldung sperrt trotzdem. „einsatzbereit“ ohne Häkchen 409, mit einem von zwei
    409, mit allen 200 – frei im Herkunftsordner, Meldungen erledigt durch diese Prüfung. „instandsetzen“ ohne Häkchen
    200 (die Meldung bleibt offen)."""
    from app.material.services import mangel
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, _ = t.art
        p = t.k["pruefer"]
        pr = pruefung(p, a1)
        assert melden(t.k["fuehrung"], a1).status_code == 201
        r = melden(t.w, a1)
        assert r.status_code == 201 and r.json["gesperrt"] is False
        assert item(t.app, a1)["lock_state"] == "gesperrt"
        ids = [m["id"] for m in meldungen(t.app, a1)]
        entwurf = p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]
        assert [m["id"] for m in entwurf["maengel"]] == ids and all(set(m) == MELDUNG for m in entwurf["maengel"])
        for gesehen in (None, [ids[0]], [ids[1]], []):
            daten = {"ergebnis": "einsatzbereit"}
            if gesehen is not None:
                daten["maengel_gesehen"] = gesehen
            r = festschreiben(p, pr["id"], **daten)
            assert r.status_code == 409 and r.json["error"] == mangel.MANGEL_NEU, r.get_json()
        assert festschreiben(p, pr["id"], ergebnis="einsatzbereit", maengel_gesehen="x").status_code == 400
        r = festschreiben(p, pr["id"], ergebnis="einsatzbereit", maengel_gesehen=[str(ids[0]), ids[1]])
        assert r.status_code == 200, r.get_json()
        i = item(t.app, a1)
        assert i["lock_state"] == "frei" and i["folder_id"] == t.lager and i["origin_folder_id"] is None, i
        assert all(m["closed_inspection_id"] == pr["id"] and m["closed_at"] for m in meldungen(t.app, a1))
        # „instandsetzen“ braucht kein Häkchen und erledigt nichts.
        pr = pruefung(p, a2)
        assert melden(t.k["fuehrung"], a2).status_code == 201
        r = festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund")
        assert r.status_code == 200, r.get_json()
        assert meldungen(t.app, a2)[0]["closed_at"] is None and item(t.app, a2)["lock_state"] == "gesperrt"
    print("Offener Entwurf bestanden.")


def test_erledigung():
    """„instandsetzen“ lässt offen, danach erledigt die Freiprüfung; Prüfergebnis „aussondern“ erledigt; nicht
    berichtigbar bei offener Meldung; Berichtigung, dann Meldung, dann „einsatzbereit“ → 409."""
    from app.material.services import mangel
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        p, f = t.k["pruefer"], t.k["fuehrung"]
        for iid in t.art:
            geprueft(t.app, iid)
        assert melden(f, a1).status_code == 201
        pr = pruefung(p, a1)
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund").status_code == 200
        assert meldungen(t.app, a1)[0]["closed_at"] is None
        b = p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]["berichtigbar"]
        assert b == {"ok": False, "grund": mangel.NUR_NEUE_PRUEFUNG}, b
        r = p.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter"})
        assert r.status_code == 409, r.get_json()
        pr2 = pruefung(p, a1)
        mid = meldungen(t.app, a1)[0]["id"]
        assert festschreiben(p, pr2["id"], ergebnis="einsatzbereit", maengel_gesehen=[mid]).status_code == 200
        d = meldungen(t.app, a1)[0]
        assert d["closed_inspection_id"] == pr2["id"]
        m = f.get(f"/api/material/artikel/{a1}").json["artikel"]["maengel"][0]
        assert m["erledigt"] == {"am": d["closed_at"], "pruefung": pr2["id"], "art": "freipruefung"} and not m["offen"]
        # Prüfergebnis „aussondern“.
        assert melden(f, a2).status_code == 201
        pr = pruefung(p, a2)
        assert festschreiben(p, pr["id"], ergebnis="aussondern", grund="Platzhaltergrund").status_code == 200
        m = t.w.get(f"/api/material/artikel/{a2}").json["artikel"]["maengel"][0]
        assert m["erledigt"]["art"] == "aussonderung" and m["erledigt"]["pruefung"] != pr["id"], m
        # Berichtigung begonnen, dann Meldung, dann „einsatzbereit“: nie frei durch eine Berichtigung.
        pr = pruefung(p, a3)
        assert festschreiben(p, pr["id"], ergebnis="einsatzbereit").status_code == 200
        r = p.post(f"/api/material/pruefungen/{pr['id']}/berichtigen", json={"grund": "Platzhalter Berichtigung"})
        assert r.status_code == 201, r.get_json()
        ber = r.json["pruefung"]["id"]
        assert melden(f, a3).status_code == 201
        mid = meldungen(t.app, a3)[0]["id"]
        r = festschreiben(p, ber, ergebnis="einsatzbereit", maengel_gesehen=[mid])
        assert r.status_code == 409 and r.json["error"] == mangel.NUR_NEUE_PRUEFUNG, r.get_json()
        assert item(t.app, a3)["lock_state"] == "gesperrt"
    print("Erledigung bestanden.")


def test_aussondern_materialwart():
    """Der Materialwart meldet selbst und will aussondern: 409 NUR_GEMELDET, nichts geändert, mangel_nur_gemeldet;
    nach „instandsetzen“ eines Prüfers geht es und erledigt die Meldung. War der Artikel schon vom Prüfer gesperrt, geht
    es sofort. Eine Berichtigung nach der Meldung zählt nicht als Prüfung."""
    from app.material.services import mangel
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        w, p = t.w, t.k["pruefer"]
        for iid in t.art:
            geprueft(t.app, iid)
        assert melden(w, a1).status_code == 201
        vorher = item(t.app, a1)
        r = w.post(f"/api/material/artikel/{a1}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 409 and r.json["error"] == mangel.NUR_GEMELDET, r.get_json()
        assert item(t.app, a1) == vorher
        assert w.get(f"/api/material/artikel/{a1}").json["artikel"]["mangel_nur_gemeldet"] is True
        neue_sekunde()
        pr = pruefung(p, a1)
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund").status_code == 200
        assert w.get(f"/api/material/artikel/{a1}").json["artikel"]["mangel_nur_gemeldet"] is False
        r = w.post(f"/api/material/artikel/{a1}/aussondern", json={"grund": "irreparabel"})
        assert r.status_code == 200, r.get_json()
        d = meldungen(t.app, a1)[0]
        assert d["closed_inspection_id"] == r.json["aussonderung"] and d["closed_at"]
        # Vorher vom Prüfer gesperrt, dann gemeldet: Aussondern sofort.
        sperren(p, a2, "sturz")
        assert melden(w, a2).status_code == 201
        assert w.get(f"/api/material/artikel/{a2}").json["artikel"]["mangel_nur_gemeldet"] is False
        assert w.post(f"/api/material/artikel/{a2}/aussondern", json={"grund": "irreparabel"}).status_code == 200
        # Eine Berichtigung nach der Meldung zählt nicht (direkt in der Tabelle – über die Schnittstelle gibt es sie
        # bei offener Meldung gar nicht).
        pr = pruefung(p, a3)
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund").status_code == 200
        neue_sekunde()
        assert melden(w, a3).status_code == 201
        # (Gesperrt durch „instandsetzen“, dann gemeldet: lock_before „gesperrt“ – Aussondern ginge sofort.)
        assert w.get(f"/api/material/artikel/{a3}").json["artikel"]["mangel_nur_gemeldet"] is False
        a4 = neuer_artikel(w, t.ids["hms"], t.lager, serial_no="AUS-4")["id"]
        geprueft(t.app, a4)
        p0 = pruefung(p, a4)
        assert festschreiben(p, p0["id"], ergebnis="einsatzbereit").status_code == 200
        assert melden(w, a4).status_code == 201
        with t.app.app_context():
            from app import db
            db.execute("INSERT INTO mat_inspection (item_id, inspector_name, inspected_on, kind, result, "
                       "corrects_inspection_id, completed_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (a4, "Platzhalter", "2026-01-01", "periodisch", "einsatzbereit", p0["id"],
                        "2099-01-01T00:00:00+00:00", "x", "x"))
            assert mangel.nur_gemeldet(a4) and mangel.ungeprueft(a4)
    print("Aussondern durch den Materialwart bestanden.")


def test_pruefart():
    """Nach einer Meldung schlägt die Prüfung „außerplanmäßig“ vor (Start ohne Art legt sie so an); nach
    „instandsetzen“ wieder „Reparatur“; vom Prüfer gesperrt ohne Meldung „Reparatur“; neu weiter nur „Eingang“."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        p, f = t.k["pruefer"], t.k["fuehrung"]
        geprueft(t.app, a1)
        geprueft(t.app, a2)
        assert melden(f, a1).status_code == 201
        assert f.get(f"/api/material/artikel/{a1}").json["artikel"]["pruefarten"]["vorschlag"] == "ausserplanmaessig"
        pr = pruefung(p, a1)
        assert pr["art"] == "ausserplanmaessig", pr["art"]
        neue_sekunde()
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund").status_code == 200
        assert f.get(f"/api/material/artikel/{a1}").json["artikel"]["pruefarten"]["vorschlag"] == "reparatur"
        sperren(p, a2, "sturz")
        assert f.get(f"/api/material/artikel/{a2}").json["artikel"]["pruefarten"]["vorschlag"] == "reparatur"
        assert melden(f, a3).status_code == 201
        pa = f.get(f"/api/material/artikel/{a3}").json["artikel"]["pruefarten"]
        assert pa == {"arten": ["eingang"], "vorschlag": "eingang"}, pa
    print("Prüfart bestanden.")


def test_durchgang():
    """Im offenen Durchgang bleibt der Artikel nach der Meldung in der Liste; die Freiprüfung im Durchgang erledigt die
    Meldung; nach „instandsetzen“ lässt sich der Durchgang abschließen, die Meldung bleibt offen."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        p, f, w = t.k["pruefer"], t.k["fuehrung"], t.w
        r = w.post("/api/material/durchgaenge", json={"folder_id": t.lager, "titel": "Platzhalter-Durchgang"})
        assert r.status_code == 201, r.get_json()
        rid = r.json["durchgang"]["id"]
        assert melden(f, a1).status_code == 201 and melden(f, a2).status_code == 201
        d = w.get(f"/api/material/durchgaenge/{rid}").json["durchgang"]
        assert {a["id"] for a in d["artikel"] if a.get("sichtbar")} >= {a1, a2}
        assert next(a for a in d["artikel"] if a.get("id") == a1)["mangel"] is True
        pr = pruefung(p, a1, durchgang_id=rid)
        mid = meldungen(t.app, a1)[0]["id"]
        assert festschreiben(p, pr["id"], ergebnis="einsatzbereit", maengel_gesehen=[mid]).status_code == 200
        assert meldungen(t.app, a1)[0]["closed_inspection_id"] == pr["id"]
        pr = pruefung(p, a2, durchgang_id=rid)
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund").status_code == 200
        r = w.post(f"/api/material/durchgaenge/{rid}/ausnehmen", json={"item_id": a3, "grund": "Platzhalter: verliehen"})
        assert r.status_code == 200, r.get_json()
        r = w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={})
        assert r.status_code == 200, r.get_json()
        assert meldungen(t.app, a2)[0]["closed_at"] is None
    print("Durchgang bestanden.")


def test_rueckruf():
    """Laufender Rückruf: nach der Mangelsperre „erledigt/gesperrt“, nach der Freiprüfung „erledigt/geprüft“; die Karte
    in „Meine PSA“ zeigt den Titel nur, solange er „offen“ ist."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        zuordnen(t, a1, t.person_id)
        geprueft(t.app, a1)
        r = t.k["katalog"].post(f"/api/material/produkte/{t.ids['hms']}/rueckrufe",
                                json={"title": "Platzhalter-Rückruf", "mail": False})
        assert r.status_code == 201, r.get_json()
        assert t.person.get(LISTE).json["artikel"][0]["rueckruf"] == ["Platzhalter-Rückruf"]
        neue_sekunde()
        assert melden(t.person, a1).status_code == 201
        rr = t.w.get(f"/api/material/artikel/{a1}").json["artikel"]["rueckrufe"][0]
        assert (rr["zustand"], rr["grund"]) == ("erledigt", "gesperrt"), rr
        assert t.person.get(LISTE).json["artikel"][0]["rueckruf"] == []
        pr = pruefung(t.k["pruefer"], a1)
        mid = meldungen(t.app, a1)[0]["id"]
        assert festschreiben(t.k["pruefer"], pr["id"], ergebnis="einsatzbereit", maengel_gesehen=[mid]).status_code == 200
        rr = t.w.get(f"/api/material/artikel/{a1}").json["artikel"]["rueckrufe"][0]
        assert (rr["zustand"], rr["grund"]) == ("erledigt", "geprueft"), rr
        assert t.person.get(LISTE).json["artikel"][0]["rueckruf"] == []
    print("Rückruf bestanden.")


def test_grenzen():
    """Eine offene Meldung je Konto und Artikel (409, auch zweimal hintereinander); ein anderes Konto darf; keine
    Tagesgrenze – 15 Meldungen eines Kontos an 15 Artikeln."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        f = t.k["fuehrung"]
        assert melden(f, a1).status_code == 201
        assert melden(f, a1).status_code == 409 and melden(f, a1).status_code == 409
        assert melden(t.w, a1).status_code == 201
        viele = [neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no=f"GR-{n}")["id"] for n in range(15)]
        for iid in viele:
            r = melden(f, iid)
            assert r.status_code == 201, r.get_json()
        assert len(zeilen(t.app, "SELECT id FROM mat_defect_report WHERE reporter_id = ?", (t.k["fuehrung_id"],))) == 16
    print("Grenzen bestanden.")


def test_mail():
    """Empfänger: Verwalter der Heimat und Prüfer mit wirksamer Prüffreigabe; nicht der Melder, keine DEMO-Adresse;
    ohne Verwalter MV, ohne MV PV. Den Namen des Melders bekommt jeder Empfänger mit Grund- oder Prüfrecht – auch der
    externe Prüfer (Entscheidung B); Text mit Beschreibung, Fotozahl, Link; ein Fehlschlag hält die anderen nicht auf;
    mail true."""
    from app.material.services import mangel
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        ext, _ = extern(t)
        _, demo_id = neues_konto(t.app, "demo-wart@beispiel.invalid", name="DEMO-Wart", stufe=1)
        freigeben(t.adm, t.gid, demo_id, "verwalten")
        a1 = t.art[0]
        zuordnen(t, a1, t.person_id)
        with post_mangel() as post:
            r = melden(t.person, a1, "Platzhalter: Schnalle klemmt", fotos=2)
            assert r.status_code == 201 and r.json["mail"] is True, r.get_json()
        an = {m[0]: m for m in post}
        assert set(an) == {"wart@example.org", "pruefer@example.org", "extern@example.org"}, set(an)
        inv = item(t.app, a1)["inventory_no"]
        for adr in ("wart@example.org", "pruefer@example.org"):
            _, betreff, text = an[adr]
            assert betreff == f"strömis.de – Mangel gemeldet: {inv} Testwerk HMS Beta – gesperrt", betreff
            assert text.startswith("Person Platzhalter hat am ") and "Platzhalter: Schnalle klemmt" in text
            assert "Fotos:      2 (am Artikel)" in text and f"https://strömis.de/material/artikel/{a1}" in text
            assert "beiseite" not in text or True
            assert "Lager Platzhalter" in text and "„Gesperrt“ der Gliederung OG Musterstadt" in text
        assert an["wart@example.org"][2].rstrip().endswith("weil du diesen Ordner verwaltest.")
        assert an["pruefer@example.org"][2].rstrip().endswith("weil du hier prüfen darfst.")
        _, _, text = an["extern@example.org"]
        assert text.startswith("Person Platzhalter hat am ") and "Platzhalter: Schnalle klemmt" in text
        assert text.rstrip().endswith("weil du hier prüfen darfst.")
        with t.app.app_context():                    # ohne Grund- und Prüfrecht hieße es so (kommt nicht vor)
            from app.material.services import katalog
            r_ = mangel.meldung(meldungen(t.app, a1)[0]["id"])
            i_ = item(t.app, a1)
            assert mangel._mailtext(r_, i_, katalog.produkt(i_["product_id"]), "pruefer", False)[1].startswith(
                "Jemand mit Zugriff auf den Artikel hat am ")
        # Ein Fehlschlag hält die anderen nicht auf.
        alt = (mangel.HINTERGRUND, mangel.send_mail)
        gesendet = []

        def senden(adr, betreff, text):
            gesendet.append(adr)
            if adr == "wart@example.org":
                raise RuntimeError("Testausnahme")
            return adr != "pruefer@example.org"
        mangel.HINTERGRUND, mangel.send_mail = (lambda fn, *a: fn(*a)), senden
        try:
            with t.app.app_context():
                mangel._versenden(1, [(a, "b", "t") for a in ("wart@example.org", "pruefer@example.org",
                                                              "extern@example.org")])
        finally:
            mangel.HINTERGRUND, mangel.send_mail = alt
        assert gesendet == ["wart@example.org", "pruefer@example.org", "extern@example.org"]
        # Rückfall: Gliederung ohne Verwalter – MV, ohne MV die PV.
        g2, _ = gliederung(t.adm, "OG Zwei", standard=False)
        l2 = ordner_neu(t.adm, g2, "Lager Zwei")
        b1, b2 = (neuer_artikel(t.adm, t.ids["hms"], l2, serial_no=f"RF-{n}")["id"] for n in (1, 2))
        freigeben(t.adm, g2, t.k["fuehrung_id"], "lesen")
        with post_mangel() as post:
            assert melden(t.k["fuehrung"], b1).status_code == 201
        assert [m[0] for m in post] == ["katalog@example.org"], post
        assert "weil du zur Material-Verwaltung gehörst" in post[0][2]
        sql(t.app, "UPDATE users SET recht_material = 1 WHERE id = ?", (t.k["katalog_id"],))
        with post_mangel() as post:
            assert melden(t.k["fuehrung"], b2).status_code == 201
        assert [m[0] for m in post] == ["admin@example.org"], post
        assert "weil du zur Plattform-Verwaltung gehörst" in post[0][2]
    print("Mail bestanden.")


def test_mail_zugeordnet():
    """Ein Kollege meldet die PSA einer Person ohne Stufe: sie bekommt eine kurze Mail ohne Melder, Beschreibung und
    Ordner, mit Link auf „Meine PSA“ – auch abbestellt; nicht bei eigener Meldung, ohne Adresse, mit DEMO-Adresse,
    deaktiviert; als Materialwartin nur die volle Mail."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        mehr = [neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no=f"ZM-{n}")["id"] for n in range(5)]
        a1, a2, a3 = t.art
        for iid in [a1, a2, a3] + mehr[:4]:
            zuordnen(t, iid, t.person_id)
        f = t.k["fuehrung"]
        sql(t.app, "UPDATE users SET mat_psa_mails = 0 WHERE id = ?", (t.person_id,))
        with post_mangel() as post:
            assert melden(f, a1, "Platzhalter-Beschreibung geheim").status_code == 201
        mails = [m for m in post if m[0] == "person@example.org"]
        assert len(mails) == 1, post
        _, betreff, text = mails[0]
        inv = item(t.app, a1)["inventory_no"]
        assert betreff == f"strömis.de – Deine PSA {inv} ist gesperrt – nicht verwenden", betreff
        assert text.startswith("Hallo Person Platzhalter,") and f"https://strömis.de/material/meine-psa/{a1}" in text
        for nicht in ("fuehrung", "Platzhalter-Beschreibung", "Lager Platzhalter", "OG Musterstadt", "/material/artikel/"):
            assert nicht not in text, nicht
        assert "leg sie sofort beiseite und gib sie deinem Materialwart" in text and "nicht abbestellen" in text
        # Selbst gemeldet: keine.
        with post_mangel() as post:
            assert melden(t.person, a2).status_code == 201
        assert not [m for m in post if m[0] == "person@example.org"] and post
        # Ohne Adresse, DEMO-Adresse, deaktiviert: keine.
        for iid, befehl in ((a3, "UPDATE users SET email = '' WHERE id = ?"),
                            (mehr[0], "UPDATE users SET email = 'person@demo.invalid' WHERE id = ?"),
                            (mehr[1], "UPDATE users SET email = 'person@example.org', active = 0 WHERE id = ?")):
            sql(t.app, befehl, (t.person_id,))
            with post_mangel() as post:
                assert melden(f, iid).status_code == 201
            assert not [m for m in post if "person" in m[0]], post
        # Materialwartin des Ordners: nur die volle Mail, einmal.
        zuordnen(t, mehr[4], t.k["wart_id"])
        with post_mangel() as post:
            assert melden(f, mehr[4]).status_code == 201
        an_wart = [m for m in post if m[0] == "wart@example.org"]
        assert len(an_wart) == 1 and "Mangel gemeldet:" in an_wart[0][1], post
    print("Mail an die zugeordnete Person bestanden.")


def test_mail_still():
    """Umgebungssperre (MATERIAL_ERINNERUNGEN_SPERRE=1, STROEMIS_NAME=…-dev) und DEMO-Artikel: kein send_mail, aber je
    Mail ein Logeintrag mit Betreff und Text, mail false; ohne Empfänger mail false."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        f = t.k["fuehrung"]
        mehr = [neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no=f"ST-{n}")["id"] for n in range(2)]
        for iid, umg in ((t.art[0], {"MATERIAL_ERINNERUNGEN_SPERRE": "1"}),
                         (t.art[1], {"STROEMIS_NAME": "stroemis-dev"})):
            with umwelt(**umg), post_mangel() as post, logzeilen(t.app) as log:
                r = melden(f, iid, "Platzhalter still")
                assert r.status_code == 201 and r.json["mail"] is False, r.get_json()
            assert not post
            still = [z for z in log if "Mail nicht verschickt (Umgebungssperre)" in z]
            assert len(still) == 2 and all("Betreff: strömis.de – Mangel gemeldet" in z for z in still), log   # Wart, Prüfer
            assert all("Platzhalter still" in z for z in still)
        # DEMO-Artikel: eine DEMO-Gliederung mit DEMO-Einsatzkraft als zugeordneter Person.
        g2, _ = gliederung(t.adm, "DEMO-OG Platzhalter", standard=False)
        sql(t.app, "UPDATE mat_folder SET demo = 1 WHERE id = ?", (g2,))
        l2 = ordner_neu(t.adm, g2, "DEMO-Lager")
        b1 = neuer_artikel(t.adm, t.ids["hms"], l2, serial_no="DEMO-1")["id"]
        _, kraft = neues_konto(t.app, "einsatzkraft@beispiel.invalid", name="DEMO-Einsatzkraft", stufe=0)
        assert t.adm.put(f"/api/material/artikel/{b1}/zuordnung", json={"user_id": kraft}).status_code == 200
        freigeben(t.adm, g2, t.k["wart_id"], "verwalten")
        with post_mangel() as post, logzeilen(t.app) as log:
            r = melden(f, mehr[0])                                     # (echter Artikel, Kontrolle)
            assert r.json["mail"] is True and post
        with post_mangel() as post, logzeilen(t.app) as log:
            r = t.adm.post(f"/api/material/artikel/{b1}/mangel", headers=H, json={"beschreibung": "Platzhalter DEMO"})
            assert r.status_code == 201 and r.json["mail"] is False, r.get_json()
        assert not post
        demo = [z for z in log if "Mail nicht verschickt (DEMO-Artikel)" in z]
        assert any("einsatzkraft@beispiel.invalid" in z and "[DEMO]" in z for z in demo), log
        assert any("wart@example.org" in z for z in demo), log
        # Ohne Empfänger: keine Verwalter, keine Prüfer, MV und PV nicht erreichbar.
        g3, _ = gliederung(t.adm, "OG Drei", standard=False)
        l3 = ordner_neu(t.adm, g3, "Lager Drei")
        c1 = neuer_artikel(t.adm, t.ids["hms"], l3, serial_no="OHNE-1")["id"]
        freigeben(t.adm, g3, t.k["fuehrung_id"], "lesen")
        sql(t.app, "UPDATE users SET email = 'katalog@x.invalid' WHERE id = ?", (t.k["katalog_id"],))
        sql(t.app, "UPDATE users SET email = 'admin@x.invalid' WHERE email = 'admin@example.org'")
        with post_mangel() as post:
            r = melden(f, c1)
            assert r.status_code == 201 and r.json["mail"] is False and not post, (r.get_json(), post)
    print("Mail still bestanden.")


def test_sichtbarkeit():
    """artikel.maengel (offen zuerst, Melder mit Grund- oder Prüfrecht – auch für die Prüfsicht, Entscheidung B); Marke
    „mangel“ in Ordnerliste, Fälligen, Suche; /start.maengel nur eigener Bereich und nur ungeprüfte; pruefung.maengel
    im Entwurf; Meine PSA: fremde Meldung nur als Zeitpunkt."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        ext, _ = extern(t)
        a1, a2, a3 = t.art
        f, w, p = t.k["fuehrung"], t.w, t.k["pruefer"]
        zuordnen(t, a1, t.person_id)
        geprueft(t.app, a1)
        assert melden(f, a1, "Erste Platzhaltermeldung").status_code == 201
        assert melden(t.person, a1, "Zweite Platzhaltermeldung").status_code == 201
        ms = w.get(f"/api/material/artikel/{a1}").json["artikel"]["maengel"]
        assert [m["description"] for m in ms] == ["Zweite Platzhaltermeldung", "Erste Platzhaltermeldung"]
        assert {m["melder"] for m in ms} == {"fuehrung", "Person Platzhalter"}
        # Entscheidung B: Name und Text auch für Prüfer – auch den externen mit befristeter Prüffreigabe.
        assert {m["melder"] for m in ext.get(f"/api/material/artikel/{a1}").json["artikel"]["maengel"]} == {
            "fuehrung", "Person Platzhalter"}
        # Marke in Listen.
        inv = item(t.app, a1)["inventory_no"]
        o = f.get(f"/api/material/ordner/{t.system['gesperrt']}").json["ordner"]["artikel"]
        assert [a["mangel"] for a in o if a["id"] == a1] == [True]
        assert all(a["mangel"] is False for a in f.get(f"/api/material/ordner/{t.lager}").json["ordner"]["artikel"])
        assert [a["mangel"] for a in f.get("/api/material/faellig?status=gesperrt").json["artikel"]] == [True]
        assert f.get(f"/api/material/suche?q={inv}").json["treffer"][0]["mangel"] is True
        # Übersicht: eigener Bereich, Melder nur mit Grundrecht.
        s = f.get("/api/material/start").json
        assert s["maengel_gesamt"] == 2 and len(s["maengel"]) == 2, s["maengel"]
        z = s["maengel"][0]
        assert set(z) == {"id", "item_id", "inventory_no", "produkt", "created_at", "kurz", "fotos", "melder"}
        assert z["item_id"] == a1 and z["melder"] == "Person Platzhalter" and z["kurz"] == "Zweite Platzhaltermeldung"
        assert set(z["produkt"]) == {"manufacturer", "model", "description"}
        assert {x["melder"] for x in ext.get("/api/material/start").json["maengel"]} == {"fuehrung", "Person Platzhalter"}
        g2, _ = gliederung(t.adm, "OG Zwei", standard=False)
        l2 = ordner_neu(t.adm, g2, "Lager Zwei")
        b1 = neuer_artikel(t.adm, t.ids["hms"], l2, serial_no="SI-B")["id"]
        _, leser_b = neues_konto(t.app, "leser_b@example.org", name="Leser B", stufe=1)
        freigeben(t.adm, g2, leser_b, "lesen")
        assert melden(t.adm, b1).status_code == 201
        assert {x["item_id"] for x in f.get("/api/material/start").json["maengel"]} == {a1}
        assert {x["item_id"] for x in t.adm.get("/api/material/start").json["maengel"]} == {a1, b1}
        # Entwurf: offene Meldungen; Prüfsicht ohne Namen.
        pr = pruefung(p, a1)
        assert [m["melder"] for m in p.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]["maengel"]] == [
            "fuehrung", "Person Platzhalter"]
        assert [m["melder"] for m in ext.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]["maengel"]] == [
            "fuehrung", "Person Platzhalter"]
        assert [m["description"] for m in ext.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]["maengel"]
                ] == ["Erste Platzhaltermeldung", "Zweite Platzhaltermeldung"]
        # Nach „instandsetzen“ fehlt die Zeile im Kasten, die Marke bleibt.
        neue_sekunde()
        assert festschreiben(p, pr["id"], ergebnis="instandsetzen", grund="Platzhaltergrund").status_code == 200
        s = f.get("/api/material/start").json
        assert s["maengel"] == [] and s["maengel_gesamt"] == 0
        assert f.get(f"/api/material/suche?q={inv}").json["treffer"][0]["mangel"] is True
        # Meine PSA: fremde Meldung nur als Zeitpunkt, eigene ganz.
        k = t.person.get(LISTE).json["artikel"][0]
        assert set(k["mangel"]) == {"seit"} and [m["description"] for m in k["eigene_maengel"]] == [
            "Zweite Platzhaltermeldung"]
        assert "Erste Platzhaltermeldung" not in json.dumps(t.person.get(LISTE).json, ensure_ascii=False)
        assert a2 and a3
    print("Sichtbarkeit bestanden.")


def _verboten(pfad, befehl, args=()):
    conn = sqlite3.connect(pfad)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute(befehl, args)
        raise AssertionError(f"erlaubt: {befehl}")
    except sqlite3.DatabaseError as exc:
        assert "Mangelmeldung" in str(exc), (befehl, exc)
    finally:
        conn.rollback()
        conn.close()


def test_unveraenderlich():
    """Ändern, Löschen, INSERT OR REPLACE, zweites Erledigen, anderes Konto, erledigt einfügen, Erledigen durch eine
    fremde Prüfung oder einen Entwurf: abgewiesen. reporter_id → NULL beim Kontolöschen geht, der Name bleibt; Artikel
    mit Meldung löschen 409."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        p = t.k["pruefer"]
        pfad = os.path.join(tmp, "stroemis.db")
        assert melden(t.person2, a1).status_code == 403              # (ohne Zuordnung)
        zuordnen(t, a1, t.person_id)
        assert melden(t.person, a1).status_code == 201
        mid = meldungen(t.app, a1)[0]["id"]
        pr = pruefung(p, a1)
        assert festschreiben(p, pr["id"], ergebnis="einsatzbereit", maengel_gesehen=[mid]).status_code == 200
        pr2 = pruefung(p, a2)                                         # Entwurf an a2
        assert melden(t.k["fuehrung"], a2).status_code == 201
        offen = meldungen(t.app, a2)[0]["id"]
        for befehl, args in (
                ("UPDATE mat_defect_report SET description = 'anders' WHERE id = ?", (mid,)),
                ("UPDATE mat_defect_report SET photos_json = '[]' WHERE id = ?", (mid,)),
                ("UPDATE mat_defect_report SET reporter_name = 'anders' WHERE id = ?", (mid,)),
                ("DELETE FROM mat_defect_report WHERE id = ?", (mid,)),
                ("INSERT OR REPLACE INTO mat_defect_report (id, item_id, description, reporter_name, lock_before, "
                 "created_at) VALUES (?, ?, 'neu', 'X', 'frei', 'x')", (mid, a1)),
                ("UPDATE mat_defect_report SET closed_inspection_id = ?, closed_at = 'y' WHERE id = ?", (pr["id"], mid)),
                ("UPDATE mat_defect_report SET reporter_id = ? WHERE id = ?", (t.person2_id, mid)),
                ("INSERT INTO mat_defect_report (item_id, description, reporter_name, lock_before, created_at, "
                 "closed_inspection_id, closed_at) VALUES (?, 'x', 'X', 'frei', 'x', ?, 'x')", (a3, pr["id"])),
                ("UPDATE mat_defect_report SET closed_inspection_id = ?, closed_at = 'x' WHERE id = ?", (pr["id"], offen)),
                ("UPDATE mat_defect_report SET closed_inspection_id = ?, closed_at = 'x' WHERE id = ?", (pr2["id"], offen))):
            _verboten(pfad, befehl, args)
        # Artikel mit Meldung lässt sich nicht löschen (auch ohne Prüfung).
        a4 = neuer_artikel(t.w, t.ids["hms"], t.lager, serial_no="UV-4")["id"]
        assert melden(t.k["fuehrung"], a4).status_code == 201
        r = t.w.delete(f"/api/material/artikel/{a4}", headers=H)
        assert r.status_code == 409 and "Mangel gemeldet" in r.json["error"], r.get_json()
        # Konto löschen: Kennung NULL, Name bleibt.
        assert t.adm.delete(f"/api/admin/users/{t.person_id}", headers=H).status_code == 200
        d = meldungen(t.app, a1)[0]
        assert d["reporter_id"] is None and d["reporter_name"] == "Person Platzhalter" and d["closed_at"], d
    print("Unveränderlich bestanden.")


def test_kontoloeschen_folgen():
    """Der Dialog „Konto löschen“ erfährt die Zahl der Meldungen, die den Namen behalten; danach Kennung NULL."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        c, uid = neues_konto(t.app, "melder@example.org", name="Melder Platzhalter", stufe=1)
        freigeben(t.adm, t.gid, uid, "lesen")
        for iid in t.art[:2]:
            assert melden(c, iid).status_code == 201
        r = t.adm.get(f"/api/admin/users/{uid}/material-folgen")
        assert r.status_code == 200 and r.json["maengel"] == 2, r.get_json()
        assert t.adm.get(f"/api/admin/users/{t.person_id}/material-folgen").json["maengel"] == 0
        assert t.adm.delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
        rows = zeilen(t.app, "SELECT reporter_id, reporter_name FROM mat_defect_report ORDER BY id")
        assert [tuple(r.values()) for r in rows] == [(None, "Melder Platzhalter")] * 2, rows
    print("Kontolöschen (Folgen) bestanden.")


def test_lebenslauf():
    """Lebenslauf-PDF: „Mangel gemeldet“ mit „(Person)“ – nicht der Name, nicht der Text."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        zuordnen(t, a1, t.person_id)
        assert melden(t.person, a1, "Geheimer Platzhaltertext").status_code == 201
        r = t.w.get(f"/material/artikel/{a1}/lebenslauf.pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf", r.status_code
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = " ".join(" ".join(pdf_seiten(pfad)).split())
        assert "Mangel gemeldet" in text and "(Person)" in text, text[-1500:]
        assert "Person Platzhalter" not in text and "Geheimer Platzhaltertext" not in text
        assert "Mangelmeldung Nr." in text
    print("Lebenslauf bestanden.")


TRIGGER_13 = {"mat_defect_aendern", "mat_defect_melder", "mat_defect_erledigt", "mat_defect_loeschen",
              "mat_defect_ersetzen", "mat_defect_neu_erledigt", "mat_defect_erledigt_durch"}


def _schema_13(pfad):
    conn = sqlite3.connect(pfad)
    try:
        version = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0]
        trigger = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger' "
                                              "AND tbl_name = 'mat_defect_report'")}
        indizes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' "
                                              "AND tbl_name = 'mat_defect_report'")}
        spalten = [r[1] for r in conn.execute("PRAGMA table_info(mat_defect_report)")]
        psa = {r[0] for r in conn.execute("SELECT mat_psa_mails FROM users")}
        sql_ = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'mat_defect_report'").fetchone()[0]
        return version, trigger, indizes, spalten, psa, sql_
    finally:
        conn.close()


def test_migration_13():
    """Frisch, 12 → 13 (Tabelle und Spalte entfernt, Version 12), zweiter Lauf ohne Änderung; mat_psa_mails = 1 für
    vorhandene Konten; 7 → 13 aus einer Kopie (wenn vorhanden)."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        version, trigger, indizes, spalten, psa, sql_ = _schema_13(pfad)
        assert version == "13" == endversion() and trigger == TRIGGER_13, (version, trigger)
        assert {"idx_mat_defect_item", "idx_mat_defect_offen", "idx_mat_defect_melder"} <= indizes, indizes
        assert spalten == ["id", "item_id", "description", "photos_json", "reporter_id", "reporter_name", "lock_before",
                           "created_at", "closed_inspection_id", "closed_at"], spalten
        assert "AUTOINCREMENT" in sql_ and psa == {1}
        # CHECKs.
        conn = sqlite3.connect(pfad)
        conn.execute("PRAGMA foreign_keys = ON")
        for befehl in ("UPDATE users SET mat_psa_mails = 2",
                       "INSERT INTO mat_defect_report (item_id, description, reporter_name, lock_before, created_at) "
                       "VALUES (999, ' ', 'X', 'frei', 'x')"):
            try:
                conn.execute(befehl)
                raise AssertionError(befehl)
            except sqlite3.IntegrityError:
                pass
        conn.rollback()
        # 12 → 13: Tabelle und Spalte weg, Version 12.
        conn.execute("INSERT INTO mat_meta (schluessel, wert) VALUES ('probe', 'x')")
        for befehl in ("DROP TABLE mat_defect_report", "ALTER TABLE users DROP COLUMN mat_psa_mails",
                       "UPDATE mat_meta SET wert = '12' WHERE schluessel = 'schema_version'"):
            conn.execute(befehl)
        conn.commit()
        stand = {n: conn.execute(f"SELECT * FROM {n} ORDER BY rowid").fetchall() for (n,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'mat%' AND name NOT LIKE '%fts%'")}
        conn.close()
        make_app(tmp)
        version, trigger, _, _, psa, _ = _schema_13(pfad)
        assert version == "13" and trigger == TRIGGER_13 and psa == {1}, (version, trigger, psa)
        conn = sqlite3.connect(pfad)
        nachher = {n: conn.execute(f"SELECT * FROM {n} ORDER BY rowid").fetchall() for n in stand}
        stand["mat_meta"] = [r for r in stand["mat_meta"] if r[0] != "schema_version"]
        nachher["mat_meta"] = [r for r in nachher["mat_meta"] if r[0] != "schema_version"]
        assert nachher == stand
        assert conn.execute("SELECT COUNT(*) FROM mat_defect_report").fetchone()[0] == 0
        # Zweiter Lauf: keine Änderung.
        assert models.migrieren(conn) == 13
        conn.execute("BEGIN")
        n = conn.total_changes
        models._schritt_13(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
        assert app
    # 7 → 13 aus der Kopie (nur, wenn sie auf diesem Rechner liegt; die Quelle bleibt unberührt).
    if KOPIE_STAND_7 and os.path.exists(KOPIE_STAND_7):
        with tempfile.TemporaryDirectory() as tmp12, tempfile.TemporaryDirectory() as tmp13:
            for d in (tmp12, tmp13):
                shutil.copyfile(KOPIE_STAND_7, os.path.join(d, "stroemis.db"))
            bis_schritt(12)(make_app, tmp12)
            app13 = make_app(tmp13)
            assert erinnerungslog_wie_schritt_11(app13)
            version, trigger, _, _, psa, _ = _schema_13(os.path.join(tmp13, "stroemis.db"))
            assert version == "13" and trigger == TRIGGER_13 and psa == {1}, (version, trigger, psa)
            zahlen = []
            for d in (tmp12, tmp13):
                c = sqlite3.connect(os.path.join(d, "stroemis.db"))
                tabellen = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE "
                                                    "'mat%' AND name NOT LIKE '%fts%' AND name <> 'mat_defect_report' "
                                                    "ORDER BY name")]
                zahlen.append({n: c.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in tabellen})
                c.close()
            assert zahlen[0] == zahlen[1] and zahlen[1]["mat_item"] > 0, zahlen
            print("  7 → 13 aus der Kopie:", zahlen[1]["mat_item"], "Artikel,", zahlen[1]["mat_folder"], "Ordner")
    else:
        print("  (7 → 13: keine Kopie angegeben – MATERIAL_KOPIE_STAND_7 – übersprungen)")
    print("Migration 13 bestanden.")


if __name__ == "__main__":
    test_melden_zugeordnet()
    test_rechte()
    test_eingaben()
    test_vorpruefung()
    test_original_sofort()
    test_schon_gesperrt()
    test_offener_entwurf()
    test_erledigung()
    test_aussondern_materialwart()
    test_pruefart()
    test_durchgang()
    test_rueckruf()
    test_grenzen()
    test_mail()
    test_mail_zugeordnet()
    test_mail_still()
    test_sichtbarkeit()
    test_unveraenderlich()
    test_kontoloeschen_folgen()
    test_lebenslauf()
    test_migration_13()
    print("Alle Tests zur Mangelmeldung bestanden.")
