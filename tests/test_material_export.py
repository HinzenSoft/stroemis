"""Rauchtest für den Export des Moduls „Material“ (Lieferung 4):  python tests/test_material_export.py  oder
pytest tests/test_material_export.py

CSV je Ordner, ZIP aller Protokolle, Lebenslauf-PDF je Artikel – „lassen sich herunterladen“, mit dem richtigen
Inhalt und nur für die, die den Ordner lesen dürfen. Die Helfer kommen aus test_material.py; alle Namen, Hersteller
und Prüfpunkte sind erfunden und nur für den Test da."""
import csv
import hashlib
import io
import logging
import os
import re
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (_flach, _heute, festschreiben, gliederung, katalog_grund, neuer_artikel,  # noqa: E402
                           pdf_seiten, protokoll_zeile, pruef_formulare, starten, umgebung)

CSP_PDF = "default-src 'none'; object-src 'self'; img-src 'self' data:"


def aufbau(tmp):
    """Eine Gliederung mit Fahrzeug (darin ein Fach), Lager und fünf Artikeln:
      formel    im Fach, Seriennummer und Bemerkung wie Formeln; im Durchgang geprüft, danach berichtigt
      textil    im Fahrzeug, Monatsangaben, noch ohne Prüfung („neu“)
      gesperrt  im Fahrzeug geprüft, dann gesperrt – liegt in „Gesperrt“, Herkunft Fahrzeug
      lager     im Lager
      weg       im Fahrzeug, verloren gemeldet und ausgesondert – liegt in „Ausgesondert“, Herkunft Fahrzeug (Phase 2)"""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    pruef_formulare(k["katalog"], ids)
    w, p1 = k["wart"], k["pruefer"]
    gid, system = gliederung(w, "OG Übungsstadt")

    def ordner(name, parent, art="standort"):
        r = w.post("/api/material/ordner", json={"name": name, "kind": art, "parent_id": parent})
        assert r.status_code == 201, r.get_json()
        return r.json["ordner"]["id"]

    fz = ordner("Fahrzeug GW-Wasserrettung", gid, "fahrzeug")
    fach = ordner("Fach 1 – Gurte", fz)
    lager = ordner("Lager Süd", gid)
    a = {"formel": neuer_artikel(w, ids["hms"], fach, serial_no="=1+2", notes="@SUMME(A1:A2)\nzweite Zeile äöüß"),
         "textil": neuer_artikel(w, ids["gurt"], fz, manufactured_on="2021-03", purchased_on="2021-04",
                                 first_use_on="2021-05-17"),
         "gesperrt": neuer_artikel(w, ids["hms"], fz, serial_no="-7"),
         "lager": neuer_artikel(w, ids["hms"], lager),
         "weg": neuer_artikel(w, ids["hms"], fz, serial_no="WEG-1")}
    # Durchgang im Fach: eine Prüfung, dann das Sammelprotokoll.
    rid = w.post("/api/material/durchgaenge", json={"folder_id": fach, "titel": "Jahresprüfung Fach 1"}).json["durchgang"]["id"]
    pid = starten(p1, a["formel"]["id"], durchgang_id=rid).json["pruefung"]["id"]
    assert festschreiben(p1, pid, ergebnis="einsatzbereit").status_code == 200
    assert w.post(f"/api/material/durchgaenge/{rid}/abschliessen", json={}).status_code == 200
    # Berichtigung: Original und Berichtigung gehören beide in ZIP und Lebenslauf.
    r = p1.post(f"/api/material/pruefungen/{pid}/berichtigen", json={"grund": "Bemerkung vergessen"})
    assert r.status_code == 201, r.get_json()
    ber = r.json["pruefung"]["id"]
    assert festschreiben(p1, ber, ergebnis="einsatzbereit", bemerkung="Nachgetragen").status_code == 200
    # Geprüft, dann gesperrt: wandert nach „Gesperrt“, der Herkunftsordner bleibt das Fahrzeug.
    pid_g = starten(p1, a["gesperrt"]["id"]).json["pruefung"]["id"]
    assert festschreiben(p1, pid_g, ergebnis="einsatzbereit").status_code == 200
    r = p1.post(f"/api/material/artikel/{a['gesperrt']['id']}/sperren",
                json={"grund": "beschaedigung", "text": "Riss am Schnapper"})
    assert r.status_code == 200, r.get_json()
    # Verloren und ausgesondert: liegt danach in „Ausgesondert“ der Gliederung; seit Phase 2 bleibt die Herkunft
    # (Fahrzeug) – sie ist seine Heimat.
    assert p1.post(f"/api/material/artikel/{a['weg']['id']}/sperren", json={"grund": "verlust"}).status_code == 200
    r = w.post(f"/api/material/artikel/{a['weg']['id']}/aussondern", json={"grund": "verlust", "bemerkung": "Bei Übung weg"})
    assert r.status_code == 200, r.get_json()
    o = {"gid": gid, "gesperrt": system["gesperrt"], "ausgesondert": system["ausgesondert"], "fz": fz, "fach": fach,
         "lager": lager, "rid": rid, "pid": pid, "ber": ber, "pid_g": pid_g, "aus": r.json["aussonderung"]}
    return app, k, o, a


def csv_lesen(daten):
    """CSV aus dem Export: BOM, „;“, CRLF – als Liste von dicts (und die Kopfzeile)."""
    assert daten.startswith(b"\xef\xbb\xbf"), daten[:10]
    text = daten.decode("utf-8-sig")
    assert text.endswith("\r\n") and text.split("\r\n", 1)[0].count(";") > 3, text[:200]
    zeilen = list(csv.reader(io.StringIO(text, newline=""), delimiter=";"))
    kopf = zeilen[0]
    return kopf, [dict(zip(kopf, z)) for z in zeilen[1:]]


def _tag(d):
    return d.strftime("%d.%m.%Y")


# --- CSV je Ordner ------------------------------------------------------------------------------------------------

def test_csv():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        f = k["fuehrung"]
        from app.material.services import export
        r = f.get(f"/materialablage/export/{o['fz']}.csv")
        assert r.status_code == 200 and r.mimetype == "text/csv", (r.status_code, r.mimetype)
        heute = _heute()
        cd = r.headers["Content-Disposition"]
        assert cd.startswith("attachment") and re.search(rf"Artikel_Fahrzeug GW-Wasserrettung_{heute.isoformat()}_\d{{4}}\.csv", cd), cd
        assert "no-store" in r.headers["Cache-Control"], r.headers["Cache-Control"]
        kopf, zeilen = csv_lesen(r.data)
        assert kopf == list(export.ARTIKEL_SPALTEN), kopf
        # Im Fahrzeug und darunter – dazu der gesperrte und der ausgesonderte, die von hier stammen (ihre Heimat ist das
        # Fahrzeug); nicht das Lager. Reihenfolge wie im Baum: Fahrzeug, darin das Fach, dann „Gesperrt“ und
        # „Ausgesondert“ (Systemordner zuletzt).
        nummern = [z["Inventarnummer"] for z in zeilen]
        assert nummern == [a["textil"]["inventory_no"], a["formel"]["inventory_no"], a["gesperrt"]["inventory_no"],
                           a["weg"]["inventory_no"]], nummern
        z = {x["Inventarnummer"]: x for x in zeilen}
        # Der Status ist derselbe wie überall (status.status) und wie in der Artikelansicht.
        with app.app_context():
            from app.material.services import bestand
            from app.material.services import status as st
            for nr, x in z.items():
                iid = [v["id"] for v in a.values() if v["inventory_no"] == nr][0]
                assert x["Status"] == st.LABEL[st.status(bestand.artikel(iid))], (nr, x["Status"])
                assert x["Status"] == f.get(f"/api/material/artikel/{iid}").json["artikel"]["status_text"]
        g = z[a["gesperrt"]["inventory_no"]]
        assert g["Status"] == "gesperrt" and g["Sperrzustand"] == "gesperrt", g
        assert g["Sperr-/Aussonderungsgrund"] == "Beschädigung: Riss am Schnapper", g
        assert g["Ordner"] == "OG Übungsstadt / Gesperrt" and g["Gliederung"] == "OG Übungsstadt", g
        assert g["Herkunftsordner"] == "OG Übungsstadt / Fahrzeug GW-Wasserrettung", g
        assert g["Seriennummer"] == "'-7" and g["zuletzt geprüft"] == _tag(heute), g
        # Formel-Schutz: Was mit = + - @ beginnt, bekommt ein ' davor – auch in mehrzeiligen Bemerkungen.
        x = z[a["formel"]["inventory_no"]]
        assert x["Seriennummer"] == "'=1+2" and x["Bemerkung"] == "'@SUMME(A1:A2)\nzweite Zeile äöüß", x
        assert x["Ordner"] == "OG Übungsstadt / Fahrzeug GW-Wasserrettung / Fach 1 – Gurte", x
        assert x["Status"] == "einsatzbereit" and x["Prüfintervall wirksam (Monate)"] == "12", x
        assert x["Hersteller"] == "Testwerk" and x["Modell"] == "HMS Beta" and x["Artikelnummer"] == "HB-7", x
        assert x["Kategorie"] == "PSA gegen Absturz / Karabiner" and x["Materialart"] == "Metall", x
        naechste = f.get(f"/api/material/artikel/{a['formel']['id']}").json["artikel"]["next_due_on"]
        assert x["nächste Prüfung"] == "{2}.{1}.{0}".format(*naechste.split("-")), (x["nächste Prüfung"], naechste)
        # Monatsangaben als MM/JJJJ, Tage als TT.MM.JJJJ; das Lebensende nur bei textil.
        t = z[a["textil"]["inventory_no"]]
        assert (t["hergestellt"], t["gekauft"], t["Erstgebrauch"], t["Lebensende"]) == ("03/2021", "04/2021", "17.05.2021",
                                                                                        "01.03.2031"), t
        assert t["Status"] == "neu" and t["Materialart"] == "textil" and t["DEMO"] == "nein" and t["Sperrzustand"] == "frei"
        # Eine laufende Prüfung steht als „in Prüfung bei“.
        assert starten(k["pruefer"], a["textil"]["id"]).status_code == 201
        _, zeilen = csv_lesen(f.get(f"/materialablage/export/{o['fz']}.csv").data)
        assert {x["Inventarnummer"]: x["in Prüfung bei"] for x in zeilen}[a["textil"]["inventory_no"]] == "pruefer"
        # Die Gliederung: alle fünf, auch der ausgesonderte (in „Ausgesondert“) und das Lager; Umlaute im Dateinamen.
        r = f.get(f"/materialablage/export/{o['gid']}.csv")
        assert r.status_code == 200 and "filename*=UTF-8''Artikel_OG%20%C3%9Cbungsstadt_" in r.headers["Content-Disposition"]
        _, zeilen = csv_lesen(r.data)
        assert {x["Inventarnummer"] for x in zeilen} == {v["inventory_no"] for v in a.values()}
        w = {x["Inventarnummer"]: x for x in zeilen}[a["weg"]["inventory_no"]]
        assert w["Status"] == "ausgesondert" and w["Ordner"] == "OG Übungsstadt / Ausgesondert", w
        assert w["Herkunftsordner"] == "OG Übungsstadt / Fahrzeug GW-Wasserrettung", w
        assert w["Sperr-/Aussonderungsgrund"] == "Verlust", w
        # Ein leerer Ordner: nur die Kopfzeile.
        leer = k["wart"].post("/api/material/ordner", json={"name": "Leer", "kind": "set", "parent_id": o["lager"]}).json["ordner"]["id"]
        kopf, zeilen = csv_lesen(f.get(f"/materialablage/export/{leer}.csv").data)
        assert kopf == list(export.ARTIKEL_SPALTEN) and zeilen == []
        # Formel-Schutz und Dateiname auch einzeln.
        assert [export._zelle(v) for v in ("=A1", "+1", "-1", "@x", "\tx", "\rx", "a=b", "", None, 12)] == \
            ["'=A1", "'+1", "'-1", "'@x", "'\tx", "'\rx", "a=b", "", "", "12"]
        assert export.dateiname("OG › Wache/Süd 🚒") == "OG _ Wache_Süd _" and export.dateiname("...") == "Export"
    print("CSV-Exporttest bestanden.")


# --- ZIP aller Protokolle -------------------------------------------------------------------------------------------

class _Mitschrift(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.zeilen = []

    def emit(self, record):
        self.zeilen.append(record.getMessage())


def zip_lesen(daten):
    z = zipfile.ZipFile(io.BytesIO(daten))
    assert z.testzip() is None
    kopf, zeilen = csv_lesen(z.read("Verzeichnis.csv"))
    return z, kopf, {x["Protokoll-ID"]: x for x in zeilen}


def test_zip():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        f = k["fuehrung"]
        from app.material.services import export
        jahr = _heute().year
        p, b, g, s, aus = (protokoll_zeile(app, o["pid"]), protokoll_zeile(app, o["ber"]), protokoll_zeile(app, o["pid_g"]),
                           protokoll_zeile(app, rid=o["rid"]), protokoll_zeile(app, o["aus"]))
        r = f.get(f"/materialablage/export/{o['fz']}-protokolle.zip")
        assert r.status_code == 200 and r.mimetype == "application/zip", r.status_code
        assert re.search(rf"Protokolle_Fahrzeug GW-Wasserrettung_{_heute().isoformat()}_\d{{4}}\.zip", r.headers["Content-Disposition"])
        assert "no-store" in r.headers["Cache-Control"]
        z, kopf, verz = zip_lesen(r.data)
        assert kopf == list(export.VERZEICHNIS_SPALTEN), kopf
        # Einzelprotokolle (auch das berichtigte Original samt Berichtigung), das Sammelprotokoll des Fachs und seit
        # Phase 2 die Aussonderung: Der ausgesonderte Artikel gehört über seine Heimat weiter zum Fahrzeug.
        erwartet = {
            p["protocol_id"]: f"Protokolle/{jahr}/{p['protocol_id']}_{a['formel']['inventory_no']}.pdf",
            b["protocol_id"]: f"Protokolle/{jahr}/{b['protocol_id']}_{a['formel']['inventory_no']}.pdf",
            g["protocol_id"]: f"Protokolle/{jahr}/{g['protocol_id']}_{a['gesperrt']['inventory_no']}.pdf",
            aus["protocol_id"]: f"Protokolle/{jahr}/{aus['protocol_id']}_{a['weg']['inventory_no']}.pdf",
            s["protocol_id"]: f"Sammelprotokolle/{jahr}/{s['protocol_id']}.pdf"}
        assert set(verz) == set(erwartet), set(verz)
        assert sorted(z.namelist()) == sorted(["Verzeichnis.csv", *erwartet.values()]), z.namelist()
        assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
        for zeile in (p, b, g, s):
            v = verz[zeile["protocol_id"]]
            daten = z.read(erwartet[zeile["protocol_id"]])
            assert hashlib.sha256(daten).hexdigest() == zeile["file_sha256"] == v["SHA-256 der Datei"], zeile["protocol_id"]
            assert hashlib.sha256(daten[:zeile["pdf_hashed_bytes"]]).hexdigest() == v["SHA-256 der ersten N Bytes"]
            assert v["N (Bytes)"] == str(zeile["pdf_hashed_bytes"]) and v["Zustand"] == "unverändert", v
            assert v["Datei im ZIP"] == erwartet[zeile["protocol_id"]]
        assert verz[p["protocol_id"]]["berichtigt durch"] == b["protocol_id"]
        assert verz[b["protocol_id"]]["Berichtigung von"] == p["protocol_id"]
        assert verz[p["protocol_id"]]["Prüfdurchgang"] == "Jahresprüfung Fach 1"
        assert verz[p["protocol_id"]]["Prüfer"] == "pruefer" and verz[p["protocol_id"]]["Urkundennummer"] == "1012-4711"
        assert verz[p["protocol_id"]]["Seriennummer"] == "'=1+2"            # Formel-Schutz auch im Verzeichnis
        assert verz[s["protocol_id"]]["Art"] == "Sammelprotokoll" and verz[s["protocol_id"]]["Ergebnis"] == "abgeschlossen"
        # Die Gliederung: dieselben – alles darin gehört auch zu ihr.
        z, _, verz = zip_lesen(f.get(f"/materialablage/export/{o['gid']}-protokolle.zip").data)
        assert set(verz) == set(erwartet), set(verz)
        v = verz[aus["protocol_id"]]
        assert v["Art"] == "Aussonderungsprotokoll" and v["Grund"] == "Verlust" and v["Prüfer"] == "wart", v
        assert v["Ergebnis"] == "ausgesondert", v              # nicht das Etikett alter Prüfungen (Ablaufprüfung A1)
        assert hashlib.sha256(z.read(v["Datei im ZIP"])).hexdigest() == aus["file_sha256"]
        # Ein leerer Ordner: ein ZIP, in dem nur das Verzeichnis liegt.
        z, _, verz = zip_lesen(f.get(f"/materialablage/export/{o['lager']}-protokolle.zip").data)
        assert z.namelist() == ["Verzeichnis.csv"] and verz == {}

        # Eine nachträglich veränderte Datei und eine fehlende brechen den Export nicht ab: Sie stehen im Verzeichnis
        # als „verändert“ bzw. „fehlt“, kommen nicht ins ZIP, und das Protokoll der App nennt sie.
        pfad = os.path.join(tmp, g["pdf_path"])
        os.chmod(pfad, 0o644)
        with open(pfad, "r+b") as fh:
            fh.seek(100)
            x = fh.read(1)
            fh.seek(100)
            fh.write(bytes([x[0] ^ 1]))
        os.chmod(os.path.join(tmp, s["pdf_path"]), 0o644)
        os.remove(os.path.join(tmp, s["pdf_path"]))
        mitschrift = _Mitschrift()
        app.logger.addHandler(mitschrift)
        try:
            r = f.get(f"/materialablage/export/{o['fz']}-protokolle.zip")
        finally:
            app.logger.removeHandler(mitschrift)
        assert r.status_code == 200, r.status_code
        z, _, verz = zip_lesen(r.data)
        assert verz[g["protocol_id"]]["Zustand"] == "verändert" and verz[g["protocol_id"]]["Datei im ZIP"] == ""
        assert verz[s["protocol_id"]]["Zustand"] == "fehlt" and verz[s["protocol_id"]]["Datei im ZIP"] == ""
        assert verz[g["protocol_id"]]["SHA-256 der Datei"] == g["file_sha256"]           # der festgeschriebene Wert
        assert sorted(z.namelist()) == sorted(["Verzeichnis.csv", erwartet[p["protocol_id"]], erwartet[b["protocol_id"]],
                                               erwartet[aus["protocol_id"]]])
        assert any(g["pdf_path"] in m and "verändert" in m for m in mitschrift.zeilen), mitschrift.zeilen
        assert any(s["pdf_path"] in m and "fehlt" in m for m in mitschrift.zeilen), mitschrift.zeilen
        assert any("Protokoll-Export" in m for m in mitschrift.zeilen), mitschrift.zeilen
        # Obergrenze: zu groß ist 413 mit Klartext, als Seite.
        alt = export.ZIP_MAX_BYTES
        export.ZIP_MAX_BYTES = 1000
        try:
            r = f.get(f"/materialablage/export/{o['gid']}-protokolle.zip")
        finally:
            export.ZIP_MAX_BYTES = alt
        assert r.status_code == 413 and r.mimetype == "text/html" and "größer als" in r.get_data(as_text=True)
    print("ZIP-Exporttest bestanden.")


# --- Lebenslauf-PDF ----------------------------------------------------------------------------------------------

def _dateien(wurzel):
    return {os.path.join(d, n) for d, _, namen in os.walk(wurzel) for n in namen}


def _zahlen(app):
    with app.app_context():
        from app import db
        return {t: db.query(f"SELECT COUNT(*) AS n FROM {t}", one=True)["n"] for t in ("mat_inspection", "mat_audit", "mat_round")}


def test_lebenslauf():
    from pypdf import PdfReader
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        f = k["fuehrung"]
        p, b, s = protokoll_zeile(app, o["pid"]), protokoll_zeile(app, o["ber"]), protokoll_zeile(app, rid=o["rid"])
        vorher, zahlen = _dateien(os.path.join(tmp, "pdf")), _zahlen(app)
        r = f.get(f"/materialablage/artikel/{a['formel']['id']}/lebenslauf.pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf" and r.data.startswith(b"%PDF"), r.status_code
        cd = r.headers["Content-Disposition"]
        assert cd.startswith("inline") and re.search(
            rf"Lebenslauf_{a['formel']['inventory_no']}_{_heute().isoformat()}_\d{{4}}_L-{_heute().year}-\d{{6}}\.pdf", cd), cd
        assert "no-store" in r.headers["Cache-Control"] and r.headers["Content-Security-Policy"] == CSP_PDF
        # Kein Protokoll: keine neue Datei unter DATA_DIR/pdf, keine Zeile in mat_inspection, kein Journaleintrag (die Zeile
        # in mat_lebenslauf prüft test_material_lebenslauf_summe.py).
        assert _dateien(os.path.join(tmp, "pdf")) == vorher and _zahlen(app) == zahlen
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        seiten = pdf_seiten(pfad)
        text = _flach(" ".join(seiten))
        for wert in (a["formel"]["inventory_no"], p["protocol_id"], b["protocol_id"], s["protocol_id"], "Kennung L-",
                     "Lebenslauf", "Testwerk HMS Beta", "Jahresprüfung Fach 1", "Bemerkung vergessen", "Nachgetragen",
                     "Urkunde 1012-4711", "zweite Zeile äöüß", "angelegt", "geprüft"):
            assert wert in text, (wert, text[:1500])
        # Prüfsummen der Protokolldateien in voller Länge; älteste Prüfung zuerst, die Berichtigung dahinter.
        ohne_leer = text.replace(" ", "")
        assert p["file_sha256"] in ohne_leer and b["file_sha256"] in ohne_leer and s["file_sha256"] in ohne_leer
        assert text.index(f"Protokoll {p['protocol_id']}") < text.index(f"Protokoll {b['protocol_id']}"), text[:2000]
        # Kein Protokoll: keine Unterschrift, keine Protokoll-Kennung im Kopf, kein „festgeschrieben“ (Nachtrag des Nutzers
        # vom 27.10.2026); eigener Fuß mit Kennung und der Prüfsummen-Stempel auf jeder Seite (Schritt 31).
        assert "Unterschrift" not in text and "Prüfnachweis" not in text and "nicht festgeschrieben" not in text
        kennung = re.search(r"L-\d{4}-\d{6}", cd).group(0)
        assert all(f"Lebenslauf {a['formel']['inventory_no']} · {kennung} · Stand" in _flach(x)
                   and f"Lebenslauf {kennung} · SHA-256 (erste" in _flach(x) for x in seiten), seiten[0][-400:]
        leser = PdfReader(pfad)
        assert leser.metadata.get("/Keywords", "").startswith("strömis-lebenslauf"), leser.metadata
        assert "protokoll" not in leser.metadata.get("/Keywords", "")
        # PDF/A-3b wie die Protokolle (die Kennung steht in den XMP-Metadaten; geprüft mit veraPDF, siehe Notizen).
        xmp = leser.trailer["/Root"]["/Metadata"].get_object().get_data()
        assert b'pdfaid:part="3"' in xmp and b'pdfaid:conformance="B"' in xmp, xmp[:600]
        # Ausgesondert: Aussonderungsnachweis mit Protokoll und Grund; gesperrt: Sperrgrund und Herkunft.
        aus = protokoll_zeile(app, o["aus"])
        r = f.get(f"/materialablage/artikel/{a['weg']['id']}/lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "AUSGESONDERT" in text and aus["protocol_id"] in text and "Bei Übung weg" in text and "Verlust" in text, text[:1200]
        r = f.get(f"/materialablage/artikel/{a['gesperrt']['id']}/lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "GESPERRT" in text and "Riss am Schnapper" in text and "Fahrzeug GW-Wasserrettung" in text, text[:1200]
        # Ohne Prüfung: ein kurzer Lebenslauf mit Hinweis.
        r = f.get(f"/materialablage/artikel/{a['lager']['id']}/lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "noch keine abgeschlossene Prüfung" in text and "Eingangsprüfung ausstehend" in text, text[:1200]
        assert _dateien(os.path.join(tmp, "pdf")) == vorher and _zahlen(app) == zahlen
    print("Lebenslauftest bestanden.")


@contextmanager
def uhrzeit(stunde, minute):
    """Stellt jetzt() (services.datetime) auf heute, stunde:minute deutscher Zeit – für die Uhrzeit im Dateinamen.
    db.now() bleibt die echte Uhr."""
    from app.material import services
    tag = _heute()
    fest = datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=ZoneInfo("Europe/Berlin"))

    class Uhr(datetime):
        @classmethod
        def now(cls, tz=None):
            return fest.astimezone(tz) if tz else fest
    alt = services.datetime
    services.datetime = Uhr
    try:
        yield
    finally:
        services.datetime = alt


def test_lebenslauf_jeder_abruf_frisch():
    """Meldung vom 26.10.2026: Chrome auf Android zeigte einen alten Lebenslauf (gleiche Adresse, gleicher Tagesname).
    Jeder Abruf setzt neu – zwei Abrufe mit einer Änderung dazwischen liefern den neuen Stand unter anderem Namen
    (Datum und Uhrzeit, deutsche Zeit); der Zeitstempel ?stand=… vom Knopf ändert nichts; no-store bleibt. Die übrigen
    auf Abruf gesetzten Dateien tragen die Uhrzeit ebenso."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        w, iid, tag = k["wart"], a["lager"]["id"], _heute().isoformat()
        url = f"/materialablage/artikel/{iid}/lebenslauf.pdf"
        pfad = os.path.join(tmp, "lebenslauf.pdf")

        def abruf(adresse):
            r = w.get(adresse)
            assert r.status_code == 200 and r.mimetype == "application/pdf", r.status_code
            assert "no-store" in r.headers["Cache-Control"] and r.headers["Content-Security-Policy"] == CSP_PDF
            with open(pfad, "wb") as fh:
                fh.write(r.data)
            return r.headers["Content-Disposition"], _flach(" ".join(pdf_seiten(pfad)))
        with uhrzeit(15, 46):
            cd1, text1 = abruf(f"{url}?stand=1761486360000")
        assert w.put(f"/api/material/artikel/{iid}", json={"notes": "Platzhalter nach dem ersten Abruf"}).status_code == 200
        with uhrzeit(18, 18):
            cd2, text2 = abruf(f"{url}?stand=1761495480000")
            cd3, text3 = abruf(url)
        assert cd1.startswith("inline") and f"_{tag}_1546_L-" in cd1, cd1
        assert f"_{tag}_1818_L-" in cd2 and f"_{tag}_1818_L-" in cd3 and cd3 != cd2, (cd2, cd3)     # je Abruf eine Kennung
        assert "Platzhalter nach dem ersten Abruf" not in text1
        assert "Platzhalter nach dem ersten Abruf" in text2 and "Platzhalter nach dem ersten Abruf" in text3, text2[:1500]
        # Die übrigen Dateien auf Abruf: CSV und ZIP des Ordners mit Uhrzeit (Jahresbericht: test_material_bericht).
        with uhrzeit(7, 5):
            for adresse in (f"/materialablage/export/{o['fz']}.csv?stand=1", f"/materialablage/export/{o['fz']}-protokolle.zip"):
                r = w.get(adresse)
                assert r.status_code == 200 and f"_{tag}_0705." in r.headers["Content-Disposition"], r.headers
                assert "no-store" in r.headers["Cache-Control"]
        # Oberfläche: Die Knöpfe tragen data-frisch, beim Klick (nicht beim Zeichnen) kommt ?stand=<ms> dazu.
        js = w.get("/static/material/material.js").get_data(as_text=True)
        for knopf in ('/lebenslauf.pdf" target="_blank" rel="noopener" data-frisch', '/export/${d.id}.csv" data-frisch',
                      '/export/${d.id}-protokolle.zip" data-frisch', '${mit}.pdf" target="_blank" rel="noopener" data-frisch',
                      '${mit}.csv" data-frisch', '/nacharbeit.csv" data-frisch', '/katalog/export" download data-frisch'):
            assert knopf in js, knopf
        assert 'u.searchParams.set("stand", String(Date.now()))' in js
        assert 'for (const art of ["click", "auxclick", "contextmenu"]) document.addEventListener(art, frischeAdresse, true);' in js
    print("Lebenslauf frisch bestanden.")


# --- Rechte und Oberfläche -------------------------------------------------------------------------------------------

def test_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        gid, _ = gliederung(k["wart"])
        art = neuer_artikel(k["wart"], ids["hms"], gid)
        adressen = [f"/materialablage/export/{gid}.csv", f"/materialablage/export/{gid}-protokolle.zip",
                    f"/materialablage/artikel/{art['id']}/lebenslauf.pdf"]
        for url in adressen:
            # Anonym: zur Anmeldung, danach zurück hierher.
            r = app.test_client().get(url)
            assert r.status_code == 302 and "/login" in r.headers["Location"], (url, r.status_code)
            # Konto ohne Recht im Modul: 403 – auch für Kennungen, die es nicht gibt (verrät nichts).
            assert k["nutzer"].get(url).status_code == 403, url
            # Führungskraft (lesend), Prüfer, Materialwart, Material-Verwaltung: dürfen.
            for wer in ("fuehrung", "pruefer", "wart", "katalog", "adm"):
                assert k[wer].get(url).status_code == 200, (wer, url)
        for url in ("/materialablage/export/99999.csv", "/materialablage/export/99999-protokolle.zip",
                    "/materialablage/artikel/99999/lebenslauf.pdf"):
            assert k["nutzer"].get(url).status_code == 403, url
            r = k["fuehrung"].get(url)
            assert r.status_code == 404 and r.mimetype == "text/html", (url, r.status_code, r.mimetype)
        # Die Oberfläche bietet die drei Knöpfe an (Ordner: CSV und Protokolle, Artikel: Lebenslauf).
        js = k["fuehrung"].get("/static/material/material.js").get_data(as_text=True)
        assert "/materialablage/export/" in js and "-protokolle.zip" in js and "/lebenslauf.pdf" in js
    print("Rechtetest (Export) bestanden.")


def test_review_lieferung4():
    """Befunde aus dem Review: Das Datum einer Ausnahme im Durchgang steht in deutscher Zeit (nicht als UTC-Datum),
    und „die ältesten fehlen“ erscheint nur, wenn das Journal wirklich mehr Einträge hat, als der Lebenslauf aufnimmt."""
    import sqlite3
    from test_material import H, gliederung, katalog_grund, neuer_artikel, pdf_seiten, pruef_formulare, umgebung
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w = k["wart"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["hms"], gid)
        rid = w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Nachtschicht"}).json["durchgang"]["id"]
        r = w.post(f"/api/material/durchgaenge/{rid}/ausnehmen", json={"item_id": a["id"], "grund": "nicht auffindbar"}, headers=H)
        assert r.status_code == 200, r.get_json()
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        conn.execute("UPDATE mat_round_item SET excluded_at = '2026-01-15T23:30:00+00:00' WHERE round_id = ?", (rid,))
        conn.commit()
        conn.close()
        r = w.get(f"/materialablage/artikel/{a['id']}/lebenslauf.pdf")
        pfad = os.path.join(tmp, "ll.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = " ".join(" ".join(pdf_seiten(pfad)).split())
        assert "16.01.2026" in text and "15.01.2026" not in text, text[:1500]
        for bemerkung in ("erste", "zweite"):                     # Journal: angelegt plus zwei Änderungen
            assert w.put(f"/api/material/artikel/{a['id']}", json={"notes": bemerkung}).status_code == 200
        # Genau so viele Journaleinträge, wie der Lebenslauf aufnimmt: nichts fehlt.
        from app.material.services import lebenslauf
        with app.app_context():
            from app import db
            n = db.query("SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'item' AND entity_id = ?", (a["id"],), one=True)["n"]
            alt = lebenslauf.JOURNAL_MAX
            try:
                lebenslauf.JOURNAL_MAX = n
                d = lebenslauf.daten(a["id"])
                assert not d["ereignisse_gekuerzt"] and len(d["ereignisse"]) == n, (n, d["ereignisse_gekuerzt"])
                lebenslauf.JOURNAL_MAX = n - 1
                d = lebenslauf.daten(a["id"])
                assert d["ereignisse_gekuerzt"] and len(d["ereignisse"]) == n - 1, (n, d["ereignisse_gekuerzt"])
                assert d["ereignisse"][0]["aktion"] != "angelegt"      # der älteste („angelegt“) fällt weg
            finally:
                lebenslauf.JOURNAL_MAX = alt
    print("Review-Befunde Lieferung 4 (Export) bestanden.")


if __name__ == "__main__":
    test_csv()
    test_zip()
    test_lebenslauf()
    test_lebenslauf_jeder_abruf_frisch()
    test_rechte()
    test_review_lieferung4()
