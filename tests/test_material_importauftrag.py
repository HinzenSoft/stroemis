"""Katalogimport im Hintergrund (Wunsch des Nutzers, 24.10.2026):  python tests/test_material_importauftrag.py

POST …/katalog/import antwortet 202 mit einem Auftrag, ein Thread führt den Import aus, GET …/import/<kennung> zeigt
Zustand, Phase und am Ende den Bericht; „Übernehmen“ startet den echten Lauf mit der Datei des Probelaufs. Geprüft:
Ablauf bis „fertig“, Bericht wie beim synchronen Lauf (Probelauf und echter Lauf, Journal mit demselben Konto),
Übernehmen ohne neuen Upload, höchstens ein Import gleichzeitig (409), Auftrag eines beendeten Prozesses (echt per
SIGKILL beim Ablegen und mitten in der Schreibtransaktion) → „abgebrochen“, Sperre frei, nichts halb geschrieben und
keine abgelegte Datei übrig; Rechte, Aufräumen, Fehlerfälle, Fortschritt, Kommandozeile unverändert.
Nachbesserung nach der Sicherheitsprüfung (24.10.2026): Konto gelöscht → Name weg, ein neues Konto mit derselben
Kennung kann nicht übernehmen; zu wenig Platz → 507; ein neuer Auftrag löscht die Dateien älterer Probeläufe; ein
abgebrochenes Übernehmen (echt per SIGKILL) lässt sich wiederholen, eines nach dem Commit nicht; die Meldung nach einem
unerwarteten Fehler sagt, ob schon gespeichert war. Alle Namen, Hersteller und Angaben hier sind Platzhalter nur für den
Test."""
import io
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import H, PDF, anmelden, import_abwarten, jpeg, make_app, umgebung  # noqa: E402

URL = "/api/material/katalog/import"


def hoch(c, inhalt, name="katalog.zip", trocken=True, url=URL):
    return c.post(url, data={"file": (io.BytesIO(inhalt), name), "trocken": "1" if trocken else "0"}, headers=H,
                  content_type="multipart/form-data")


def katalog_zip(n=2, mit_dateien=True, farbe=0):
    """Ein Katalog (Format 2) mit n Platzhalter-Produkten, je mit Bild und Dokument."""
    from PIL import Image
    eintraege, produkte = {}, []
    for i in range(n):
        p = {"uid": f"{i + 1:032x}", "kategorie": ["Platzhalterkategorie"], "hersteller": "Platzhalterwerk",
             "modell": f"Probe {i + 1}", "artikelnummer": f"PH-{i + 1}", "materialart": "metall_hardware",
             "intervall_monate": 12}
        if mit_dateien:
            buf = io.BytesIO()
            Image.new("RGB", (40 + i, 30), (10 * i + farbe, 80, 160)).save(buf, "JPEG")
            eintraege[f"dateien/bilder/b{i}.jpg"] = buf.getvalue()
            eintraege[f"dateien/dokumente/d{i}.pdf"] = PDF + f"% {i} {farbe}\n".encode()
            p["bild"] = f"dateien/bilder/b{i}.jpg"
            p["dokumente"] = [{"art": "datenblatt", "titel": f"Blatt {i + 1}", "datei": f"dateien/dokumente/d{i}.pdf"}]
        produkte.append(p)
    daten = {"format": "stroemis-material-katalog", "version": 2,
             "kategorien": [{"uid": "f" * 32, "name": "Platzhalterkategorie"}], "produkte": produkte}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("katalog.json", json.dumps(daten))
        for name, inhalt in eintraege.items():
            z.writestr(name, inhalt)
    return buf.getvalue()


def ordner(tmp):
    return os.path.join(tmp, "katalog-import")


def dateien_im_auftragsordner(tmp):
    try:
        return sorted(n for n in os.listdir(ordner(tmp)) if n != "sperre")
    except FileNotFoundError:
        return []


def mediendateien(tmp):
    """Alle Dateien unter media/material (Bilder in orig/web/thumb, Dokumente in dok)."""
    wurzel = os.path.join(tmp, "media", "material")
    out = set()
    for d, _, namen in os.walk(wurzel):
        for n in namen:
            out.add(os.path.relpath(os.path.join(d, n), wurzel))
    return out


def zahl(app, sql, args=()):
    from app import db
    with app.app_context():
        return db.query(sql, args, one=True)["n"]


def zustand_schreiben(tmp, z):
    with open(os.path.join(ordner(tmp), z["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(z, fh)


def lesen(c, kennung):
    r = c.get(f"{URL}/{kennung}")
    assert r.status_code == 200, r.get_json()
    return r.json["auftrag"]


# --- 1. Ablauf, Bericht wie synchron, Übernehmen ohne neuen Upload --------------------------------------------------

def test_ablauf_und_bericht():
    from flask import g

    from app import db
    from app.material.services import importer
    roh = katalog_zip(3)
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        # A: synchron wie die Kommandozeile (mit angemeldetem Konto im Kontext) – B: über die Schnittstelle.
        app_a = make_app(tmp_a)
        anmelden(app_a, "admin@example.org", "geheim123")
        with app_a.test_request_context():
            g.user = db.query("SELECT * FROM users WHERE email = ?", ("admin@example.org",), one=True)
            sync_probe = json.loads(json.dumps(importer.datei_importieren(io.BytesIO(roh), trocken=True,
                                                                          quelle="katalog.zip")))
            sync_echt = json.loads(json.dumps(importer.datei_importieren(io.BytesIO(roh), trocken=False,
                                                                         quelle="katalog.zip")))
        app = make_app(tmp_b)
        c = anmelden(app, "admin@example.org", "geheim123")
        r = hoch(c, roh)
        assert r.status_code == 202, r.get_json()
        a = r.json["auftrag"]
        assert a["zustand"] in ("wartet", "laeuft", "fertig") and a["trocken"] and a["quelle"] == "katalog.zip", a
        assert len(a["id"]) == 32 and a["eigener"] and a["groesse"] == len(roh) and "von_id" not in a, a
        probe = import_abwarten(c, r)
        assert probe["zustand"] == "fertig" and probe["phase"] == "probe" and probe["beendet"], probe
        assert probe["bericht"] == sync_probe, (probe["bericht"], sync_probe)
        # Die Datei des Probelaufs liegt für „Übernehmen“ bereit (eine Stunde) – Ordner 0700, Dateien 0600.
        assert probe["uebernehmbar"] and probe["datei_bis"], probe
        assert os.stat(ordner(tmp_b)).st_mode & 0o777 == 0o700
        for n in dateien_im_auftragsordner(tmp_b) + ["sperre"]:
            assert os.stat(os.path.join(ordner(tmp_b), n)).st_mode & 0o777 == 0o600, n
        assert f"{probe['id']}.datei" in dateien_im_auftragsordner(tmp_b)
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 0 and not mediendateien(tmp_b)

        # Übernehmen: ohne Datei in der Anfrage; die Datei wandert zum neuen Auftrag und ist danach weg.
        r = c.post(f"{URL}/{probe['id']}/uebernehmen", headers=H)
        assert r.status_code == 202, r.get_json()
        echt = import_abwarten(c, r)
        assert echt["zustand"] == "fertig" and not echt["trocken"] and echt["aus"] == probe["id"], echt
        assert echt["bericht"] == sync_echt, (echt["bericht"], sync_echt)
        assert echt["bericht"]["gespeichert"] and echt["bericht"]["produkte"]["neu"] == 3
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 3
        assert dateien_im_auftragsordner(tmp_b) == sorted(f"{k}.{e}" for k in (probe["id"], echt["id"])
                                                          for e in ("bericht.json", "json")), dateien_im_auftragsordner(tmp_b)
        alt = lesen(c, probe["id"])
        assert alt["uebernommen_in"] == echt["id"] and not alt["uebernehmbar"] and alt["bericht"] == sync_probe, alt
        assert c.post(f"{URL}/{probe['id']}/uebernehmen", headers=H).status_code == 409
        # Journal wie beim synchronen Lauf: dasselbe Konto mit Namen und Kennung.
        with app_a.app_context():
            namen_a = {(x["user_name"], x["user_id"]) for x in db.query("SELECT user_name, user_id FROM mat_audit")}
        with app.app_context():
            namen_b = {(x["user_name"], x["user_id"]) for x in db.query("SELECT user_name, user_id FROM mat_audit")}
        assert namen_a == namen_b and len(namen_b) == 1 and None not in next(iter(namen_b)), (namen_a, namen_b)
        # Die Katalogseite zeigt den letzten Auftrag (ohne Bericht).
        r = c.get(f"{URL}/aktuell")
        assert r.status_code == 200 and r.json["auftrag"]["id"] == echt["id"] and "bericht" not in r.json["auftrag"]
    print("Ablauf und Bericht bestanden.")


def test_probelauf_ohne_aenderung_und_frist():
    from app.material.services import importauftrag
    roh = katalog_zip(1, mit_dateien=False)
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        import_abwarten(c, hoch(c, roh, trocken=False))
        # Nichts zu übernehmen: Die Datei bleibt nicht liegen, „Übernehmen“ gibt es nicht.
        a = import_abwarten(c, hoch(c, roh))
        assert a["zustand"] == "fertig" and not a["uebernehmbar"] and not a["bericht"]["aenderungen"], a
        assert f"{a['id']}.datei" not in dateien_im_auftragsordner(tmp)
        assert c.post(f"{URL}/{a['id']}/uebernehmen", headers=H).status_code == 409
        # Ein Probelauf mit Änderungen, dessen Frist abgelaufen ist: 409 und die Datei wird aufgeräumt.
        roh2 = katalog_zip(2, mit_dateien=False)
        a = import_abwarten(c, hoch(c, roh2))
        assert a["uebernehmbar"], a
        pfad = os.path.join(ordner(tmp), a["id"] + ".json")
        with open(pfad, encoding="utf-8") as fh:
            z = json.load(fh)
        z["datei_bis"] = "2026-01-01T00:00:00+00:00"
        zustand_schreiben(tmp, z)
        r = c.post(f"{URL}/{a['id']}/uebernehmen", headers=H)
        assert r.status_code == 409 and "Stunde" in r.json["error"], r.get_json()
        with app.app_context():
            importauftrag.aufraeumen()
        assert f"{a['id']}.datei" not in dateien_im_auftragsordner(tmp)
    print("Probelauf ohne Änderung und Frist bestanden.")


# --- 2. Höchstens ein Import gleichzeitig ---------------------------------------------------------------------------

def test_zweiter_import_409():
    from app.material.services import importauftrag, importer
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        c, kp = k["adm"], k["katalog"]
        los, drin = threading.Event(), threading.Event()
        echt = importer.importieren

        def haengt(*a, **kw):
            drin.set()
            assert los.wait(60)
            return echt(*a, **kw)

        warten_alt, importer.importieren, importauftrag.SPERRE_WARTEN = importauftrag.SPERRE_WARTEN, haengt, 0.3
        try:
            erster = hoch(c, katalog_zip(2))
            assert erster.status_code == 202 and drin.wait(30), erster.get_json()
            kennung = erster.json["auftrag"]["id"]
            a = lesen(c, kennung)
            assert a["zustand"] == "laeuft" and a["phase"] == "pruefen" and a["n"] is None, a
            # Ein zweiter Start – auch von einem anderen Konto der Material-Verwaltung – bekommt 409 mit dem laufenden.
            for wer in (c, kp):
                r = hoch(wer, katalog_zip(1))
                assert r.status_code == 409 and r.json["auftrag"]["id"] == kennung, r.get_json()
                assert "läuft schon" in r.json["error"], r.get_json()
            # Den laufenden sieht auch das andere Konto, „eigener“ nur der Starter.
            assert lesen(kp, kennung)["eigener"] is False and lesen(c, kennung)["eigener"] is True
            assert kp.get(f"{URL}/aktuell").json["auftrag"]["zustand"] == "laeuft"
            # Die hochgeladene Datei des zweiten Versuchs blieb nicht liegen.
            assert [n for n in dateien_im_auftragsordner(tmp) if n.endswith(".datei")] == [f"{kennung}.datei"]
        finally:
            los.set()
            importer.importieren = echt
        a = import_abwarten(c, erster)
        assert a["zustand"] == "fertig", a
        importauftrag.SPERRE_WARTEN = warten_alt
        # Danach geht der nächste.
        assert import_abwarten(kp, hoch(kp, katalog_zip(1)))["zustand"] == "fertig"
    print("Zweiter Import (409) bestanden.")


# --- 3. Prozess weg: abgebrochen, Sperre frei, nichts halb geschrieben -----------------------------------------------

KIND = r"""
import io, os, sys, time
sys.path.insert(0, {tests!r})
from test_material import H, anmelden, make_app
from app.material.services import importer
app = make_app({tmp!r})
c = anmelden(app, "admin@example.org", "geheim123")
wo, marke = {wo!r}, {marke!r}
if wo == "ablegen":
    echt, n = importer._ablegen, [0]
    def haken(archiv, eintrag):
        n[0] += 1
        if n[0] == 3:
            open(marke, "w").close()
            time.sleep(600)
        return echt(archiv, eintrag)
    importer._ablegen = haken
else:
    echt = importer._formulare
    def haken(liste, lauf):
        if not lauf.planen:
            open(marke, "w").close()
            time.sleep(600)
        return echt(liste, lauf)
    importer._formulare = haken
with open({zip!r}, "rb") as fh:
    roh = fh.read()
r = c.post("/api/material/katalog/import", data={{"file": (io.BytesIO(roh), "katalog.zip"),
           "trocken": "1" if wo == "uebernehmen" else "0"}}, headers=H, content_type="multipart/form-data")
assert r.status_code == 202, r.get_json()
if wo == "uebernehmen":
    from app.material.services import importauftrag
    assert importauftrag.warten(r.json["auftrag"]["id"], 120)
    print(r.json["auftrag"]["id"], flush=True)
    r = c.post("/api/material/katalog/import/" + r.json["auftrag"]["id"] + "/uebernehmen", headers=H)
    assert r.status_code == 202, r.get_json()
print(r.json["auftrag"]["id"], flush=True)
time.sleep(600)
"""


def _kind_toeten(tmp, wo):
    """Einen Arbeitsprozess nachstellen, der mitten im Import endet (Neustart, Deploy): ein eigener Prozess startet den
    Import über die Schnittstelle, hält an der Stelle wo an und wird mit SIGKILL beendet – ohne jedes Aufräumen.
    „ablegen“: vor der dritten von vier Dateien (zwei liegen und stehen im Protokoll); „schreiben“: mitten in der
    Transaktion des zweiten Durchgangs, nach Kategorien und Produkten (alle vier Dateien liegen); „uebernehmen“ wie
    „schreiben“, aber als „Übernehmen“ nach einem Probelauf. Liefert die Kennung des Laufs – bei „uebernehmen“
    (Probelauf, Lauf)."""
    zip_pfad, marke = os.path.join(tmp, "probe.zip"), os.path.join(tmp, "marke")
    with open(zip_pfad, "wb") as fh:
        fh.write(katalog_zip(2))
    skript = KIND.format(tests=os.path.dirname(os.path.abspath(__file__)), tmp=tmp, wo=wo, marke=marke, zip=zip_pfad)
    protokoll = open(os.path.join(tmp, "kind.log"), "wb")
    kind = subprocess.Popen([sys.executable, "-S", "-c", skript], stdout=subprocess.PIPE, stderr=protokoll,
                            env=dict(os.environ))
    try:
        probe = ""
        if wo == "uebernehmen":
            bereit = select.select([kind.stdout], [], [], 120)[0]
            probe = kind.stdout.readline().decode().strip() if bereit else ""
        bereit = select.select([kind.stdout], [], [], 90)[0]
        kennung = kind.stdout.readline().decode().strip() if bereit else ""
        ende = time.monotonic() + 60
        while not os.path.exists(marke) and time.monotonic() < ende and kind.poll() is None:
            time.sleep(0.05)
        if not (os.path.exists(marke) and len(kennung) == 32):
            with open(os.path.join(tmp, "kind.log"), "rb") as fh:
                raise AssertionError((wo, kennung, kind.poll(), fh.read()[-3000:]))
    finally:
        os.kill(kind.pid, signal.SIGKILL)
        kind.wait(10)
        kind.stdout.close()
        protokoll.close()
    os.remove(zip_pfad)
    os.remove(os.path.join(tmp, "kind.log"))
    return (probe, kennung) if wo == "uebernehmen" else kennung


def test_prozess_weg():
    from app.material.services import importauftrag
    for wo in ("ablegen", "schreiben"):
        with tempfile.TemporaryDirectory() as tmp:
            app = make_app(tmp)
            c = anmelden(app, "admin@example.org", "geheim123")
            vorher = (zahl(app, "SELECT COUNT(*) AS n FROM mat_product"), zahl(app, "SELECT COUNT(*) AS n FROM mat_audit"))
            kennung = _kind_toeten(tmp, wo)
            # Die Dateien lagen schon (2 beim Ablegen, alle 4 vor dem Schreiben), das Protokoll nennt sie.
            assert len([m for m in mediendateien(tmp) if m.startswith("orig/") or m.startswith("dok/")]) == (
                2 if wo == "ablegen" else 4), mediendateien(tmp)
            with open(os.path.join(ordner(tmp), kennung + ".abgelegt"), encoding="utf-8") as fh:
                assert len(fh.read().splitlines()) == (2 if wo == "ablegen" else 4)
            # Gleich danach ist das Lebenszeichen noch frisch: weiter „laeuft“, und ein Start wartet (409).
            alt, importauftrag.TOT_NACH, importauftrag.SPERRE_WARTEN = (importauftrag.TOT_NACH,
                                                                         importauftrag.SPERRE_WARTEN), 4, 0.2
            try:
                a = lesen(c, kennung)
                assert a["zustand"] == "laeuft" and a["phase"] == ("ablegen" if wo == "ablegen" else "schreiben"), a
                assert hoch(c, katalog_zip(1)).status_code == 409
                time.sleep(4.5)
                a = lesen(c, kennung)
            finally:
                importauftrag.TOT_NACH, importauftrag.SPERRE_WARTEN = alt
            assert a["zustand"] == "abgebrochen" and "unterbrochen" in a["fehler"] and a["beendet"], a
            assert "bevor er gespeichert hatte" in a["fehler"] and "neuer Probelauf" in a["fehler"], a
            assert not a["uebernehmbar"], a
            assert "/" not in a["fehler"] and a["bericht"] is None, a
            # Nichts halb geschrieben, keine abgelegte Datei übrig, die hochgeladene Datei weg, Sperre frei.
            assert (zahl(app, "SELECT COUNT(*) AS n FROM mat_product"),
                    zahl(app, "SELECT COUNT(*) AS n FROM mat_audit")) == vorher, wo
            assert not [m for m in mediendateien(tmp) if "/" in m], (wo, mediendateien(tmp))
            assert dateien_im_auftragsordner(tmp) == [f"{kennung}.json"], dateien_im_auftragsordner(tmp)
            neu = import_abwarten(c, hoch(c, katalog_zip(2), trocken=False))
            assert neu["zustand"] == "fertig" and neu["bericht"]["produkte"]["neu"] == 2, neu
            assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 2
        print(f"Prozess weg ({wo}) bestanden.")


def test_abgelegt_aufraeumen_behaelt_genanntes():
    """Ein abgebrochener Lauf, der noch committet hatte: Was die Datenbank nennt, bleibt; der Rest geht."""
    from app import db
    from app.material.services import importauftrag
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        import_abwarten(c, hoch(c, katalog_zip(1), trocken=False))
        with app.app_context():
            genannt = db.query("SELECT image FROM mat_product", one=True)["image"]
            doknamen = [x["file_path"] for x in db.query("SELECT file_path FROM mat_product_document")]
        from werkzeug.datastructures import FileStorage

        from app.material.services import katalog
        with app.test_request_context():
            frei = katalog.foto_ablegen(FileStorage(jpeg(), filename="x.jpg"), vorschau_ganz=True)
            frei_dok = katalog._datei_ablegen(FileStorage(io.BytesIO(PDF + b"% frei\n"), filename="x.pdf"))[0]
        kennung = "e" * 32
        zustand_schreiben(tmp, {"id": kennung, "zustand": "laeuft", "trocken": False, "quelle": "k.zip",
                                "gestartet": "2026-01-01T00:00:00+00:00", "lebenszeichen": "2026-01-01T00:00:00+00:00",
                                "von_id": 1, "von": "Platzhalter"})
        with open(os.path.join(ordner(tmp), kennung + ".abgelegt"), "w", encoding="utf-8") as fh:
            for zeile in (["bild", genannt], ["bild", frei], ["dokument", doknamen[0]], ["dokument", frei_dok],
                          ["bild", "../../stroemis.db"], ["bild", "kaputt"]):
                fh.write(json.dumps(zeile) + "\n")
            fh.write('["bild", "halb')
        with open(os.path.join(ordner(tmp), kennung + ".datei"), "wb") as fh:
            fh.write(b"PK")
        a = lesen(c, kennung)
        assert a["zustand"] == "abgebrochen", a
        m = mediendateien(tmp)
        assert f"orig/{genannt}" in m and f"dok/{doknamen[0]}" in m, m
        assert f"orig/{frei}" not in m and not any(frei.split(".")[0] in x for x in m) and f"dok/{frei_dok}" not in m, m
        assert os.path.exists(os.path.join(tmp, "stroemis.db"))
        assert f"{kennung}.datei" not in dateien_im_auftragsordner(tmp)
        assert f"{kennung}.abgelegt" not in dateien_im_auftragsordner(tmp)
        with app.app_context():
            importauftrag.aufraeumen()
    print("Aufräumen abgelegter Dateien bestanden.")


# --- 4. Rechte ------------------------------------------------------------------------------------------------------

def test_rechte():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        a = import_abwarten(k["katalog"], hoch(k["katalog"], katalog_zip(1, mit_dateien=False)))
        kennung = a["id"]
        for rolle in ("fuehrung", "wart", "pruefer", "nutzer"):
            c = k[rolle]
            assert hoch(c, katalog_zip(1)).status_code == 403, rolle
            assert c.get(f"{URL}/{kennung}").status_code == 403, rolle
            assert c.get(f"{URL}/aktuell").status_code == 403, rolle
            assert c.post(f"{URL}/{kennung}/uebernehmen", headers=H).status_code == 403, rolle
        anonym = app.test_client()
        assert anonym.get(f"{URL}/{kennung}").status_code == 401
        assert anonym.post(f"{URL}/{kennung}/uebernehmen", headers=H).status_code == 401
        # Ohne X-Requested-With kein Übernehmen (CSRF).
        assert k["katalog"].post(f"{URL}/{kennung}/uebernehmen").status_code == 403
        # Fremde oder erfundene Kennung: 404 – auch nichts, was nach einem Pfad aussieht.
        for falsch in ("0" * 32, "A" * 32, "abc", kennung[:-1] + "g", "..%2Fsperre", "sperre"):
            assert k["katalog"].get(f"{URL}/{falsch}").status_code == 404, falsch
            assert k["katalog"].post(f"{URL}/{falsch}/uebernehmen", headers=H).status_code == 404, falsch
        # Ein anderes Konto der Material-Verwaltung sieht den Auftrag, übernehmen darf nur, wer ihn gestartet hat.
        b = lesen(k["adm"], kennung)
        assert b["eigener"] is False and b["uebernehmbar"] is False and b["von"] == "katalog", b
        r = k["adm"].post(f"{URL}/{kennung}/uebernehmen", headers=H)
        assert r.status_code == 403 and "gestartet" in r.json["error"], r.get_json()
        assert lesen(k["katalog"], kennung)["uebernehmbar"] is True
        # Im Zustand steht vom Konto nur der pseudonyme Kontoverweis (users.mat_ref) – kein Name, keine users.id –,
        # im Bericht keine Person.
        with open(os.path.join(ordner(tmp), kennung + ".json"), encoding="utf-8") as fh:
            roh = fh.read()
        z = json.loads(roh)
        assert "@" not in roh and "von" not in z and "von_id" not in z, z
        assert z["von_ref"] == zahl(app, "SELECT mat_ref AS n FROM users WHERE id = ?", (k["katalog_id"],)), z
        with open(os.path.join(ordner(tmp), kennung + ".bericht.json"), encoding="utf-8") as fh:
            roh = fh.read()
        assert "@" not in roh and '"von' not in roh
    print("Rechte bestanden.")


# --- 5. Fehlerfälle -------------------------------------------------------------------------------------------------

def test_fehlerfaelle():
    from app.material.services import importauftrag, importer
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        # Kaputte Datei: Auftrag „fehlgeschlagen“, der Bericht nennt den Grund; die Datei ist weg.
        for roh, name, teil in ((b"PK\x03\x04kaputt", "k.zip", "beschädigt"), (b"{kein json", "k.json", "JSON")):
            a = import_abwarten(c, hoch(c, roh, name, trocken=False))
            assert a["zustand"] == "fehlgeschlagen" and teil in a["bericht"]["fehler"][0], a
            assert not a["bericht"]["gespeichert"] and not a["uebernehmbar"], a
        # Fehler im Katalog (Prüfregel): ebenfalls „fehlgeschlagen“ mit dem Bericht wie bisher.
        daten = {"format": "stroemis-material-katalog", "version": 2,
                 "produkte": [{"hersteller": "Platzhalterwerk", "modell": "Ohne Kategorie"}]}
        a = import_abwarten(c, hoch(c, json.dumps(daten).encode(), "k.json"))
        assert a["zustand"] == "fehlgeschlagen" and a["bericht"]["fehler"] and a["bericht"]["trocken"], a
        # Unerwarteter Fehler im Import: „fehlgeschlagen“, Text ohne Pfad, nichts gespeichert, Sperre frei.
        echt = importer.importieren

        def kaputt(*a, **kw):
            raise RuntimeError(f"Testfehler in {tmp}/geheim")

        importer.importieren = kaputt
        try:
            a = import_abwarten(c, hoch(c, katalog_zip(1), trocken=False))
        finally:
            importer.importieren = echt
        assert a["zustand"] == "fehlgeschlagen" and "unerwarteten Fehler" in a["fehler"], a
        assert tmp not in json.dumps(a) and "Testfehler" not in json.dumps(a), a
        assert a["bericht"]["fehler"] == [a["fehler"]] and not a["bericht"]["gespeichert"], a
        assert "Gespeichert wurde nichts" in a["fehler"], a
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 0
        # Unerwarteter Fehler NACH dem Commit: Die Meldung sagt nicht „nichts gespeichert“.
        echt_abschluss = importer._abschluss

        def nach_commit(lauf, basis):
            if lauf.bericht.get("gespeichert"):
                raise RuntimeError("Testfehler nach dem Commit")
            return echt_abschluss(lauf, basis)

        importer._abschluss = nach_commit
        try:
            a = import_abwarten(c, hoch(c, katalog_zip(1, farbe=90), trocken=False))
        finally:
            importer._abschluss = echt_abschluss
        assert a["zustand"] == "fehlgeschlagen" and "schon geschrieben" in a["fehler"], a
        assert "Gespeichert wurde nichts" not in a["fehler"], a
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 1
        assert not [n for n in dateien_im_auftragsordner(tmp) if n.endswith((".datei", ".abgelegt"))]
        assert import_abwarten(c, hoch(c, katalog_zip(1), trocken=False))["zustand"] == "fertig"
        # Ohne Datei weiter 400 (vor dem Speichern); kaputte Sperr- und Zustandsdateien stören nicht.
        assert c.post(URL, data={"trocken": "1"}, headers=H, content_type="multipart/form-data").status_code == 400
        with open(os.path.join(ordner(tmp), "sperre"), "w", encoding="utf-8") as fh:
            fh.write("{kaputt")
        kaputt_id = "d" * 32
        with open(os.path.join(ordner(tmp), kaputt_id + ".json"), "w", encoding="utf-8") as fh:
            fh.write('{"id": "' + kaputt_id + '", "zustand": "irgendwas"')
        assert c.get(f"{URL}/{kaputt_id}").status_code == 404
        assert c.get(f"{URL}/aktuell").status_code == 200
        assert import_abwarten(c, hoch(c, katalog_zip(1)))["zustand"] == "fertig"
        # Der unlesbare Zustand verschwindet nach einer Stunde.
        os.utime(os.path.join(ordner(tmp), kaputt_id + ".json"), (time.time() - 7200, time.time() - 7200))
        with app.app_context():
            importauftrag.aufraeumen()
        assert f"{kaputt_id}.json" not in dateien_im_auftragsordner(tmp)
    print("Fehlerfälle bestanden.")


# --- 6. Aufräumen ---------------------------------------------------------------------------------------------------

def test_aufraeumen():
    from app.material.services import importauftrag
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        a = import_abwarten(c, hoch(c, katalog_zip(1, mit_dateien=False), trocken=False))
        assert dateien_im_auftragsordner(tmp) == [f"{a['id']}.bericht.json", f"{a['id']}.json"]
        # Hinweis auf der Katalogseite einen Tag lang, danach nicht mehr; nach 7 Tagen sind Zustand und Bericht weg.
        pfad = os.path.join(ordner(tmp), a["id"] + ".json")
        with open(pfad, encoding="utf-8") as fh:
            z = json.load(fh)
        z["beendet"] = "2026-01-01T00:00:00+00:00"
        zustand_schreiben(tmp, z)
        assert c.get(f"{URL}/aktuell").json["auftrag"] is None
        assert dateien_im_auftragsordner(tmp) == []
        # Waisen: eine Datei ohne Zustand (Start, der vor dem Zustand endete), eine liegengebliebene Zwischendatei.
        for n in ("c" * 32 + ".datei", "c" * 32 + ".json.1234abcd.neu", "fremd.txt"):
            with open(os.path.join(ordner(tmp), n), "wb") as fh:
                fh.write(b"x")
        os.utime(os.path.join(ordner(tmp), "c" * 32 + ".json.1234abcd.neu"), (time.time() - 120, time.time() - 120))
        with app.app_context():
            importauftrag.aufraeumen()
        assert dateien_im_auftragsordner(tmp) == ["fremd.txt"], dateien_im_auftragsordner(tmp)
        os.remove(os.path.join(ordner(tmp), "fremd.txt"))
        # Der Tageslauf räumt mit auf.
        from app.material import tageslauf
        from app.material.services import erinnerung
        alt = erinnerung.tageslauf_versuchen
        erinnerung.tageslauf_versuchen = lambda: None
        try:
            with open(os.path.join(ordner(tmp), "b" * 32 + ".datei"), "wb") as fh:
                fh.write(b"x")
            tageslauf._einmal(app)
        finally:
            erinnerung.tageslauf_versuchen = alt
        assert dateien_im_auftragsordner(tmp) == []
    print("Aufräumen bestanden.")


# --- 7. Fortschritt im Importer und Kommandozeile ----------------------------------------------------------------

def test_fortschritt_und_kommandozeile():
    from flask import g

    from app import db
    from app.material.services import importer
    roh = katalog_zip(2)
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        anmelden(app, "admin@example.org", "geheim123")
        meldungen = []
        with app.test_request_context():
            g.user = None
            ohne = importer.datei_importieren(io.BytesIO(roh), trocken=True, quelle="k.zip")
            mit = importer.datei_importieren(io.BytesIO(roh), trocken=True, quelle="k.zip",
                                             fortschritt=lambda *a, **kw: meldungen.append((a, kw)))
            assert ohne == mit
            assert [m[0][0] for m in meldungen] == ["pruefen"] * 5 + ["probe"], meldungen
            assert meldungen[1][0][1:] == (0, 4) and meldungen[4][0][1:] == (3, 4), meldungen
            meldungen.clear()
            echt = importer.datei_importieren(io.BytesIO(roh), trocken=False, quelle="k.zip",
                                              fortschritt=lambda *a, **kw: meldungen.append((a, kw)))
            assert echt["gespeichert"], echt
            phasen = [m[0][0] for m in meldungen]
            assert phasen == ["pruefen"] * 5 + ["probe"] + ["ablegen"] * 8 + ["schreiben", "gespeichert"], phasen
            abgelegt = [m[1]["abgelegt"] for m in meldungen if m[1].get("abgelegt")]
            assert sorted(a[0] for a in abgelegt) == ["bild", "bild", "dokument", "dokument"], abgelegt
            assert db.query("SELECT COUNT(*) AS n FROM mat_product", one=True)["n"] == 2
        # Die Kommandozeile bleibt synchron und legt keinen Auftrag an.
        pfad = os.path.join(tmp, "cli.zip")
        with open(pfad, "wb") as fh:
            fh.write(katalog_zip(3, farbe=50))
        r = app.test_cli_runner().invoke(args=["material", "import-catalog", pfad, "--trocken"])
        assert r.exit_code == 0 and "Trockenlauf – nichts gespeichert." in r.output, r.output
        r = app.test_cli_runner().invoke(args=["material", "import-catalog", pfad])
        assert r.exit_code == 0 and "Gespeichert." in r.output, r.output
        assert dateien_im_auftragsordner(tmp) == []
    print("Fortschritt und Kommandozeile bestanden.")


# --- 8. Nachbesserung nach der Sicherheitsprüfung (24.10.2026) ----------------------------------------------------

def test_konto_geloescht():
    """Befund 1: Der Zustand nennt das Konto nur über users.mat_ref. Nach dem Löschen steht „(gelöschtes Konto)“ da, und
    ein neues Konto, dem SQLite dieselbe Kennung gibt, kann den Probelauf nicht übernehmen."""
    from test_material import neues_konto

    from app.material.services import importauftrag
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        c1, uid = neues_konto(app, "starter@example.org", rechte={"material": 2})
        a = import_abwarten(c1, hoch(c1, katalog_zip(1, mit_dateien=False)))
        assert a["uebernehmbar"] and a["eigener"] and a["von"] == "starter", a
        assert lesen(k["adm"], a["id"])["von"] == "starter"
        assert k["adm"].delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
        c2, uid2 = neues_konto(app, "nachfolger@example.org", rechte={"material": 2})
        assert uid2 == uid, (uid, uid2)               # ohne AUTOINCREMENT vergibt SQLite die Kennung neu
        b = lesen(c2, a["id"])
        assert b["von"] == "(gelöschtes Konto)" and not b["eigener"] and not b["uebernehmbar"], b
        assert c2.get(f"{URL}/aktuell").json["auftrag"]["von"] == "(gelöschtes Konto)"
        r = c2.post(f"{URL}/{a['id']}/uebernehmen", headers=H)
        assert r.status_code == 403 and "gestartet" in r.json["error"], r.get_json()
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 0
        with open(os.path.join(ordner(tmp), a["id"] + ".json"), encoding="utf-8") as fh:
            assert "starter" not in fh.read()
        # Ein Zustand der ersten Fassung (Name und users.id): Beim Aufräumen verschwinden beide Felder, übernehmen
        # lässt er sich nicht.
        alt_id = "a" * 32
        zustand_schreiben(tmp, {"id": alt_id, "zustand": "fertig", "trocken": True, "quelle": "k.zip",
                                "gestartet": "2026-10-24T06:00:00+00:00", "beendet": "2099-01-01T00:00:00+00:00",
                                "von_id": uid2, "von": "Platzhalter Alt", "datei_bis": "2099-01-01T00:00:00+00:00"})
        with open(os.path.join(ordner(tmp), alt_id + ".datei"), "wb") as fh:
            fh.write(b"PK")
        assert c2.post(f"{URL}/{alt_id}/uebernehmen", headers=H).status_code == 403
        with app.app_context():
            importauftrag.aufraeumen()
        with open(os.path.join(ordner(tmp), alt_id + ".json"), encoding="utf-8") as fh:
            z = json.load(fh)
        assert "von" not in z and "von_id" not in z and z["zustand"] == "fertig", z
        assert lesen(c2, alt_id)["von"] is None
    print("Konto gelöscht bestanden.")


def test_plattenplatz():
    """Befund 2: zu wenig Platz → 507 ohne Pfad, nichts liegen geblieben; ein neuer Auftrag löscht die Dateien
    älterer Probeläufe."""
    import shutil
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        p1 = import_abwarten(c, hoch(c, katalog_zip(1, mit_dateien=False)))
        p2 = import_abwarten(c, hoch(c, katalog_zip(2, mit_dateien=False)))
        # Der zweite Probelauf hat die Datei des ersten gelöscht – dessen „Übernehmen“ ist überholt.
        assert f"{p1['id']}.datei" not in dateien_im_auftragsordner(tmp) and p2["uebernehmbar"], p2
        assert not lesen(c, p1["id"])["uebernehmbar"]
        r = c.post(f"{URL}/{p1['id']}/uebernehmen", headers=H)
        assert r.status_code == 409 and "nächsten Import" in r.json["error"], r.get_json()

        from app.material.services import importauftrag
        echt = shutil.disk_usage
        shutil.disk_usage = lambda pfad: echt(pfad)._replace(free=importauftrag.RESERVE + 10)
        try:
            # Übernehmen: 507, der Probelauf bleibt übernehmbar.
            r = c.post(f"{URL}/{p2['id']}/uebernehmen", headers=H)
            assert r.status_code == 507 and "zu wenig Platz" in r.json["error"], r.get_json()
            assert tmp not in r.json["error"] and "/" not in r.json["error"], r.get_json()
            assert lesen(c, p2["id"])["uebernehmbar"]
            # Neuer Upload: 507, keine Datei liegen geblieben (die des älteren Probelaufs ist weg).
            r = hoch(c, katalog_zip(3, mit_dateien=False))
            assert r.status_code == 507 and "Katalogdatei" in r.json["error"] and tmp not in r.json["error"], r.get_json()
            assert not [n for n in dateien_im_auftragsordner(tmp) if n.endswith(".datei")], dateien_im_auftragsordner(tmp)
        finally:
            shutil.disk_usage = echt
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 0
        # Mit Platz geht es wieder; die Sperre ist frei.
        assert import_abwarten(c, hoch(c, katalog_zip(1, mit_dateien=False)))["zustand"] == "fertig"
    print("Plattenplatz bestanden.")


def test_uebernehmen_abgebrochen():
    """Ein „Übernehmen“, dessen Prozess mitten in der Schreibtransaktion endet (SIGKILL): Der Probelauf bekommt seine
    Datei zurück, „Übernehmen“ geht noch einmal (auch über die Kennung des abgebrochenen Laufs). Endet er erst nach dem
    Commit (Vermerk „gespeichert“), nicht – und die Meldung sagt, dass die Datenbank geschrieben war."""
    from app.material.services import importauftrag
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = anmelden(app, "admin@example.org", "geheim123")
        probe, kennung = _kind_toeten(tmp, "uebernehmen")
        alt, importauftrag.TOT_NACH = importauftrag.TOT_NACH, 0
        try:
            a = lesen(c, kennung)
        finally:
            importauftrag.TOT_NACH = alt
        assert a["zustand"] == "abgebrochen" and a["aus"] == probe and a["uebernehmbar"] and a["datei_bis"], a
        assert "noch einmal" in a["fehler"] and "bevor er gespeichert hatte" in a["fehler"], a
        p = lesen(c, probe)
        assert p["uebernehmbar"] and p["uebernommen_in"] is None, p
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 0
        assert not [m for m in mediendateien(tmp) if "/" in m], mediendateien(tmp)
        assert sorted(n for n in dateien_im_auftragsordner(tmp) if n.endswith(".datei")) == [f"{probe}.datei"]
        r = c.post(f"{URL}/{kennung}/uebernehmen", headers=H)
        assert r.status_code == 202, r.get_json()
        echt = import_abwarten(c, r)
        assert echt["zustand"] == "fertig" and echt["aus"] == probe and echt["bericht"]["gespeichert"], echt
        assert zahl(app, "SELECT COUNT(*) AS n FROM mat_product") == 2
        assert lesen(c, probe)["uebernommen_in"] == echt["id"] and not lesen(c, kennung)["uebernehmbar"]

        # Nach dem Commit abgebrochen (nachgestellt): keine zweite Runde, die Meldung nennt es.
        p2 = import_abwarten(c, hoch(c, katalog_zip(3)))
        assert p2["uebernehmbar"], p2
        with open(os.path.join(ordner(tmp), p2["id"] + ".json"), encoding="utf-8") as fh:
            z2 = json.load(fh)
        neu = "b" * 32
        os.replace(os.path.join(ordner(tmp), p2["id"] + ".datei"), os.path.join(ordner(tmp), neu + ".datei"))
        z2.update(uebernommen_in=neu, datei_bis=None)
        zustand_schreiben(tmp, z2)
        zustand_schreiben(tmp, {"id": neu, "zustand": "laeuft", "trocken": False, "quelle": "katalog.zip",
                                "gestartet": "2026-01-01T00:00:00+00:00", "lebenszeichen": "2026-01-01T00:00:00+00:00",
                                "von_ref": z2["von_ref"], "aus": p2["id"], "phase": "schreiben", "gespeichert": True})
        a = lesen(c, neu)
        assert a["zustand"] == "abgebrochen" and not a["uebernehmbar"] and "schon geschrieben" in a["fehler"], a
        assert not lesen(c, p2["id"])["uebernehmbar"]
        assert not [n for n in dateien_im_auftragsordner(tmp) if n.endswith(".datei")], dateien_im_auftragsordner(tmp)
        r = c.post(f"{URL}/{neu}/uebernehmen", headers=H)
        assert r.status_code == 409 and "schon übernommen" in r.json["error"], r.get_json()
    print("Abgebrochenes Übernehmen bestanden.")


# --- 9. Oberfläche (statisch) -------------------------------------------------------------------------------------

def test_oberflaeche_statisch():
    pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "material", "static",
                        "material.js")
    with open(pfad, encoding="utf-8") as fh:
        js = fh.read()
    assert "katalog/import/aktuell" in js and "/uebernehmen`" in js and "upload.onprogress" in js
    assert "btn ghost" not in js
    # Nachbesserung: vor dem Hochladen nachfragen, nach 100 % „Datei wird abgelegt …“, Zahlen im Balken als Zahl.
    assert "xhr.upload.onload" in js and "Datei wird abgelegt …" in js and "Number(m)" in js
    print("Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_ablauf_und_bericht()
    test_probelauf_ohne_aenderung_und_frist()
    test_zweiter_import_409()
    test_prozess_weg()
    test_abgelegt_aufraeumen_behaelt_genanntes()
    test_rechte()
    test_fehlerfaelle()
    test_aufraeumen()
    test_fortschritt_und_kommandozeile()
    test_konto_geloescht()
    test_plattenplatz()
    test_uebernehmen_abgebrochen()
    test_oberflaeche_statisch()
    print("Alle Tests zum Katalogimport im Hintergrund bestanden.")
