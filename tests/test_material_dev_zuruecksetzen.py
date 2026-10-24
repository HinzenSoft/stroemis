"""Modul Material auf dev zurücksetzen (flask material dev-zuruecksetzen, Wunsch vom 23.10.2026):
python tests/test_material_dev_zuruecksetzen.py  oder  pytest …

Sperren: ohne dev-Kennung (STROEMIS_NAME auf „-dev“), mit BASE_URL der Produktion (Umgebung oder Anwendung) oder ohne
--ja-alles-loeschen lehnt der Befehl mit 2 ab und ändert nichts; --trocken zeigt nur. Der volle Lauf auf einem Bestand
mit Katalog samt Bild und Dokument, Gliederung, Artikeln, Durchgang, Bestandsimport und dem DEMO-Bestand aus
scripts/material_demo.py (festgeschriebene Prüfungen mit Protokollen, Set, DEMO-Konten): danach sind alle mat_-Tabellen
leer, Schema und mat_meta gleichen einer neuen Installation (Version 21), die Sicherung enthält die alte Datenbank Zeile
für Zeile und die verschobenen Medien Datei für Datei, und Konten, Wiki, Spots, Prüfungen-Modul und Einstellungen sind
byteidentisch – auch die Modulstufe 2 ohne Plattform-Verwaltung, die Migration Schritt 10 neu rechnen würde. Ein
zweiter Lauf auf dem leeren Modul geht, die App startet danach, und material_demo.py --demo läuft wieder. Scheitert
die Sicherung, das Verschieben oder das Anlegen, bleibt alles, wie es war. Läuft ein Katalogimport im Hintergrund,
bricht der Befehl ab, ohne etwas zu ändern; danach sind dessen Aufträge unter DATA_DIR/katalog-import weg
(Nachbesserung nach der Sicherheitsprüfung vom 24.10.2026).
Alle Namen und Nummern hier sind Platzhalter."""
import contextlib
import errno
import hashlib
import io
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, gliederung, jpeg, katalog_grund, make_app, neuer_artikel,  # noqa: E402
                           pruef_formulare, umgebung)
from test_material_import import csv_bytes, ok, uebernehmen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = {"STROEMIS_NAME": "stroemis-dev", "BASE_URL": "https://dev.strömis.de"}
MODUL = "(tbl_name LIKE 'mat\\_%' ESCAPE '\\' OR name LIKE 'mat\\_%' ESCAPE '\\')"
MEDIEN = (os.path.join("media", "material"), "pdf")


@contextlib.contextmanager
def umwelt(app=None, **werte):
    """Umgebungsvariablen (None entfernt) und – mit app – BASE_URL der Anwendung für die Dauer des Blocks."""
    alt = {k: os.environ.get(k) for k in werte}
    alt_cfg = app.config.get("BASE_URL") if app else None
    try:
        for k, v in werte.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if app and werte.get("BASE_URL"):
            app.config["BASE_URL"] = werte["BASE_URL"]
        yield
    finally:
        for k, v in alt.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if app:
            app.config["BASE_URL"] = alt_cfg


def aufrufen(app, *schalter):
    """Der Befehl wie auf der Kommandozeile – (Ausgabe samt Fehlerausgabe, Rückgabewert)."""
    r = app.test_cli_runner().invoke(args=["material", "dev-zuruecksetzen", *schalter])
    if r.exception and not isinstance(r.exception, SystemExit):
        raise r.exception
    return r.output, r.exit_code


def sha(pfad):
    with open(pfad, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def dateien(wurzel, ohne=()):
    """{relativer Pfad: SHA-256} aller Dateien unter wurzel – ohne die Pfade, die mit einem aus ohne beginnen."""
    out = {}
    for w, _, namen in os.walk(wurzel):
        for n in namen:
            rel = os.path.relpath(os.path.join(w, n), wurzel)
            if not rel.startswith(ohne):
                out[rel] = sha(os.path.join(w, n))
    return out


def tabellen(conn, modul):
    """Die Tabellen des Moduls (modul=True) oder alle übrigen – ohne Volltext-Schattentabellen und sqlite_*."""
    return sorted(r[1] for r in conn.execute("PRAGMA main.table_list")
                  if r[2] == "table" and not r[1].startswith("sqlite_") and r[1].startswith("mat_") == modul)


def inhalt(db_pfad, modul):
    """Jede Zeile jeder Tabelle (des Moduls oder der übrigen) und – für die übrigen – ihr Schema samt sqlite_sequence."""
    conn = sqlite3.connect(db_pfad)
    try:
        out = {t: conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tabellen(conn, modul)}
        if not modul:
            out["#schema"] = conn.execute(f"SELECT type, name, tbl_name, sql FROM sqlite_master WHERE NOT {MODUL} "
                                          "ORDER BY type, name").fetchall()
            out["#sequenz"] = conn.execute("SELECT * FROM sqlite_sequence WHERE name NOT LIKE 'mat\\_%' ESCAPE '\\' "
                                           "ORDER BY name").fetchall()
        return out
    finally:
        conn.close()


def schema_modul(db_pfad):
    conn = sqlite3.connect(db_pfad)
    try:
        return (sorted(conn.execute(f"SELECT type, name, tbl_name, sql FROM sqlite_master WHERE {MODUL}").fetchall()),
                conn.execute("SELECT * FROM mat_meta ORDER BY schluessel").fetchall())
    finally:
        conn.close()


def stand(app):
    """Alles: jede Zeile der ganzen Datenbank und jede Datei im Datenordner außer der Datenbank selbst und der (leeren)
    Sperrdatei des Katalogimports – die legt der Befehl an, um während des Laufs jeden Import fernzuhalten."""
    db = app.config["DB_PATH"]
    return {"modul": inhalt(db, True), "aussen": inhalt(db, False),
            "dateien": dateien(app.config["DATA_DIR"], ohne=("stroemis.db", os.path.join("katalog-import", "sperre")))}


def rechte(pfad):
    return os.stat(pfad).st_mode & 0o777


def sicherungen(app):
    return sorted(n for n in os.listdir(app.config["DATA_DIR"]) if n.startswith("sicherung-material-"))


def demo_laufen(*schalter):
    """scripts/material_demo.py wie von der Kommandozeile (DATA_DIR hat make_app gesetzt) – (Ausgabe, Rückgabewert)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("material_demo_test", os.path.join(REPO, "scripts", "material_demo.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    puffer, code, argv = io.StringIO(), 0, sys.argv
    sys.argv = ["material_demo.py", *schalter]
    try:
        with contextlib.redirect_stdout(puffer):
            modul.main()
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.argv = argv
    return puffer.getvalue(), code


def bestand_aufbauen(tmp):
    """Ein Bestand, der jede Art Modulinhalt hat, und daneben Konten, Wiki, Spots und Prüfungen-Modul."""
    app, k = umgebung(tmp)
    adm, kp, w = k["adm"], k["katalog"], k["wart"]
    ids = katalog_grund(adm)
    pruef_formulare(kp, ids)
    ok(kp.post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")}, headers=H,
               content_type="multipart/form-data"))
    ok(kp.post(f"/api/material/produkte/{ids['hms']}/dokumente", headers=H, content_type="multipart/form-data",
               data={"file": (io.BytesIO(PDF + b"%platzhalter"), "anleitung.pdf"), "kind": "gebrauchsanleitung",
                     "title": "Anleitung (Platzhalter)", "valid_from": "2024-01-01"}), 201)
    gid, _ = gliederung(adm)
    lager = ordner_neu(w, gid, "Lager Platzhalter")
    for n in range(1, 3):
        neuer_artikel(w, ids["hms"], lager, serial_no=f"PH-000{n}")
    ok(w.post("/api/material/durchgaenge", json={"folder_id": gid, "titel": "Platzhalter-Durchgang"}), 201)
    kopf = ["Hersteller", "Modell", "Seriennummer"]
    ok(uebernehmen(w, lager, csv_bytes([kopf, ["Testwerk", "HMS Beta", "PH-IMP-1"], ["Testwerk", "Unbekannt", "PH-IMP-2"]])),
       201)
    aus, code = demo_laufen("--demo", "--konten")
    assert code == 0 and "festgeschrieben" in aus and "DEMO-Set mit 2 Teilen" in aus, (code, aus)
    # Daneben: Wiki-Seite (mit Datei), Spot mit Bild, Lehrgang im Prüfungen-Modul.
    ok(adm.post("/api/wiki/pages", json={"title": "Platzhalter-Seite", "content": "Platzhaltertext"}), 201)
    ok(adm.post("/api/wiki/files", data={"file": (jpeg(), "wiki.jpg")}, headers=H, content_type="multipart/form-data"))
    album = ok(adm.post("/api/albums", json={"title": "Platzhalter-Spot", "category": "wasser"}), 201)["album"]["id"]
    ok(adm.post(f"/api/albums/{album}/photos", data={"files": [(jpeg(), "spot.jpg")]}, headers=H,
                content_type="multipart/form-data"), 201)
    ok(adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Platzhalter-Lehrgang"}), 201)
    return app, k


def test_sperren():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        gid, _ = gliederung(k["adm"])
        neuer_artikel(k["wart"], ids["hms"], ordner_neu(k["wart"], gid, "Lager Platzhalter"), serial_no="PH-1")
        vorher = stand(app)
        faelle = [
            ({"STROEMIS_NAME": None, "BASE_URL": DEV["BASE_URL"]}, "STROEMIS_NAME ist „nicht gesetzt“"),
            ({"STROEMIS_NAME": "stroemis", "BASE_URL": DEV["BASE_URL"]}, "STROEMIS_NAME ist „stroemis“"),
            ({"STROEMIS_NAME": "stroemis-dev-alt", "BASE_URL": DEV["BASE_URL"]}, "nicht die Entwicklung"),
            ({"STROEMIS_NAME": "stroemis-dev", "BASE_URL": "https://strömis.de"}, "BASE_URL in der Umgebung ist"),
            ({"STROEMIS_NAME": "stroemis-dev", "BASE_URL": "https://www.xn--strmis-yxa.de/"}, "frei ist nur"),
        ]
        for werte, text in faelle:
            for schalter in (("--ja-alles-loeschen",), ("--trocken",), ("--trocken", "--ja-alles-loeschen"), ()):
                with umwelt(app, **werte):
                    aus, code = aufrufen(app, *schalter)
                assert code == 2 and text in aus and "nichts geändert" in aus, (werte, schalter, code, aus)
        # dev, aber ohne Schalter: abgelehnt.
        with umwelt(app, **DEV):
            aus, code = aufrufen(app)
        assert code == 2 and "Ohne --ja-alles-loeschen" in aus and "--trocken" in aus, (code, aus)
        # --trocken zeigt, ändert nichts – auch zusammen mit dem Schalter.
        for schalter in (("--trocken",), ("--trocken", "--ja-alles-loeschen")):
            with umwelt(app, **DEV):
                aus, code = aufrufen(app, *schalter)
            assert code == 0 and aus.startswith("Probelauf – nichts geändert."), (code, aus)
            assert "mat_item " in aus and "Sicherung nach:" in aus and "sicherung-material-" in aus, aus
            assert "media/material" in aus and "pdf" in aus and "Version 21" in aus and "Bleibt: Konten" in aus, aus
        # BASE_URL der Anwendung (Verwaltung → Einstellungen) zeigt auf die Produktion, die Umgebung auf dev.
        with app.app_context():
            from app import db
            db.execute("INSERT INTO einstellungen (schluessel, wert, geaendert_am) VALUES ('BASE_URL', "
                       "'https://strömis.de', ?)", (db.now(),))
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--ja-alles-loeschen")
        assert code == 2 and "BASE_URL der Anwendung" in aus, (code, aus)
        with app.app_context():
            from app import db
            db.execute("DELETE FROM einstellungen WHERE schluessel = 'BASE_URL'")
            from app import einstellungen
            einstellungen.anwenden()                 # der übernommene Wert geht zurück (wie bei der nächsten Anfrage)
        assert stand(app) == vorher and not sicherungen(app)
    print("Sperren bestanden.")


def test_zuruecksetzen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = bestand_aufbauen(tmp)
        db_pfad = app.config["DB_PATH"]
        vorher = stand(app)
        medien_vorher = {rel: dateien(os.path.join(tmp, rel)) for rel in MEDIEN}
        modul = vorher["modul"]
        for t in ("mat_item", "mat_inspection", "mat_round", "mat_import", "mat_import_row", "mat_audit",
                  "mat_item_set_slot", "mat_product_document", "mat_folder_grant"):
            assert modul[t], t
        assert any(r for r in modul["mat_inspection"]) and medien_vorher["pdf"] and medien_vorher[MEDIEN[0]]
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--ja-alles-loeschen")
        assert code == 0, (code, aus)
        assert "Modul Material zurückgesetzt. Sicherung:" in aus and "docker compose restart" in aus, aus
        assert "demo-wart-a@example.invalid (DEMO-Materialwart A)" in aus and "Nutzerverwaltung" in aus, aus
        (ordner,) = sicherungen(app)
        sicherung = os.path.join(tmp, ordner)
        nachher = stand(app)
        # Alle mat_-Tabellen leer bis auf mat_meta; Schema und mat_meta wie bei einer neuen Installation.
        assert {t: z for t, z in nachher["modul"].items() if z and t != "mat_meta"} == {}, nachher["modul"]
        with tempfile.TemporaryDirectory() as frisch:
            neu = make_app(frisch)
            assert schema_modul(db_pfad) == schema_modul(neu.config["DB_PATH"])
        assert dict(nachher["modul"]["mat_meta"])["schema_version"] == "21"
        # Außerhalb des Moduls byteidentisch: jede Zeile, jedes Schema-Objekt, jede Datei (Konten, Wiki, Spots,
        # Prüfungen, Einstellungen – auch die Modulstufe 2 der Material-Verwaltung ohne Plattform-Verwaltung).
        assert nachher["aussen"] == vorher["aussen"]
        with app.app_context():
            from app import db
            assert db.query("SELECT recht_material FROM users WHERE email = 'demo-mv@example.invalid'",
                            one=True)["recht_material"] == 2
        assert {p: s for p, s in nachher["dateien"].items() if not p.startswith(ordner)} == {
            p: s for p, s in vorher["dateien"].items() if not p.startswith(MEDIEN)}
        # Sicherung: die alte Datenbank Zeile für Zeile (gewöhnliches Journal, quick_check), die Medien verschoben.
        kopie = os.path.join(sicherung, "stroemis.db")
        assert inhalt(kopie, True) == vorher["modul"] and inhalt(kopie, False) == vorher["aussen"]
        c = sqlite3.connect(kopie)
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete" and c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        c.close()
        for rel in MEDIEN:
            assert dateien(os.path.join(sicherung, rel)) == medien_vorher[rel], rel
            assert not dateien(os.path.join(tmp, rel)), rel
        with open(os.path.join(sicherung, "LIESMICH.txt"), encoding="utf-8") as fh:
            liesmich = fh.read()
        assert f"cp data/{ordner}/stroemis.db data/stroemis.db" in liesmich and f"mv data/{ordner}/pdf data/pdf" in liesmich
        assert f"mv data/{ordner}/media/material data/media/material" in liesmich and "docker compose up -d" in liesmich
        assert "LAUF UNVOLLSTÄNDIG" not in liesmich and "BITTE LÖSCHEN" in liesmich and "Passwort-Hash" in liesmich
        assert f"rm -rf data/{ordner}" in liesmich and f"rm -rf data/{ordner}" in aus and "Passwort-Hash" in aus
        # Personendaten: Ordner 0700, Kopie und LIESMICH 0600 (Befund 3 der Sicherheitsprüfung).
        assert rechte(sicherung) == 0o700 and rechte(kopie) == 0o600, (oct(rechte(sicherung)), oct(rechte(kopie)))
        assert rechte(os.path.join(sicherung, "LIESMICH.txt")) == 0o600 and rechte(os.path.join(sicherung, "media")) == 0o700
        assert "Ältere Sicherungen" not in aus

        # Zweiter Lauf auf dem leeren Modul: geht, eigene Sicherung.
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--ja-alles-loeschen")
        assert code == 0 and "Geleert:" in aus, (code, aus)
        assert len(sicherungen(app)) == 2 and stand(app)["aussen"] == vorher["aussen"]
        # Der Bericht nennt die ältere Sicherung zum Löschen, der Probelauf beide.
        alt = aus.split("Ältere Sicherungen", 1)[1]
        assert ordner in alt and sicherungen(app)[1] not in alt, aus
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--trocken")
        assert code == 0 and all(n in aus.split("Ältere Sicherungen", 1)[1] for n in sicherungen(app)), aus
        # Die App startet danach, das Modul ist leer und benutzbar, und die Demodaten laufen wieder.
        app2 = make_app(tmp)
        c = app2.test_client()
        ok(c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}))
        assert ok(c.get("/api/material/start"))
        aus, code = demo_laufen("--demo", "--konten")
        assert code == 0 and "festgeschrieben" in aus and "DEMO-Set mit 2 Teilen" in aus, (code, aus)
        assert "Konto demo-wart-a@example.invalid ist schon da" in aus, aus
        with app2.app_context():
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM mat_inspection WHERE pdf_path IS NOT NULL", one=True)["n"] > 0
            pfade = {r["pdf_path"] for r in db.query("SELECT pdf_path FROM mat_inspection WHERE pdf_path IS NOT NULL")}
        assert all(os.path.isfile(os.path.join(tmp, p)) for p in pfade), pfade
    print("Zurücksetzen bestanden.")


def test_scheitern():
    """Sicherung, Verschieben oder Anlegen scheitern: nichts geändert, keine Sicherung bleibt liegen."""
    from app.material.services import zuruecksetzen as z
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        ok(k["katalog"].post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")},
                             headers=H, content_type="multipart/form-data"))
        gid, _ = gliederung(k["adm"])
        neuer_artikel(k["wart"], ids["hms"], ordner_neu(k["wart"], gid, "Lager Platzhalter"), serial_no="PH-1")
        os.makedirs(os.path.join(tmp, "pdf", "2026"))
        with open(os.path.join(tmp, "pdf", "2026", "P-platzhalter.pdf"), "wb") as fh:
            fh.write(PDF)
        vorher = stand(app)
        pdf = os.path.join(tmp, "pdf")
        echt_rename, echt_fsync, echt_anlegen = os.rename, os.fsync, z._anlegen

        def fsync_kaputt(_fd):
            raise OSError(errno.EIO, "Platzhalter: Schreibfehler")

        def rename_kaputt(quelle, ziel):
            if quelle == pdf:
                raise OSError(errno.EXDEV, "Platzhalter: anderes Dateisystem")
            return echt_rename(quelle, ziel)

        def anlegen_kaputt(conn, vorlage):
            echt_anlegen(conn, vorlage)
            raise sqlite3.DatabaseError("Platzhalter: Anlegen gescheitert")

        for name, ziel, ersatz, text in (
                ("fsync", os, fsync_kaputt, "Die Sicherung der Datenbank ist gescheitert"),
                ("rename", os, rename_kaputt, "nichts geändert: Datenbank unverändert, Medien zurück"),
                ("_anlegen", z, anlegen_kaputt, "Anlegen gescheitert")):
            alt = getattr(ziel, name)
            setattr(ziel, name, ersatz)
            try:
                with umwelt(app, **DEV):
                    aus, code = aufrufen(app, "--ja-alles-loeschen")
            finally:
                setattr(ziel, name, alt)
            assert code == 1 and text in aus and "FEHLER" in aus, (name, code, aus)
            assert stand(app) == vorher, name
            assert not sicherungen(app), (name, sicherungen(app))
        assert (os.rename, os.fsync, z._anlegen) == (echt_rename, echt_fsync, echt_anlegen)
    print("Scheitern bestanden.")


# --- Nachbesserung nach der Sicherheitsprüfung (23.10.2026) ------------------------------------------------------

def test_sperre_schreibweisen():
    """Befund 1: BASE_URL als Positivliste – bereinigt (Leerraum, Schema, NFKC/NFD, ideographischer Punkt, IDNA, groß/
    klein), frei nur „dev.…“, localhost und 127.0.0.1. Die Fälle aus der Probe sperre.py der Prüfung, je einmal in der
    Umgebung (Anwendung auf dev) und in der Anwendung (Umgebung auf dev); dazu sperrgrund() und der Probelauf."""
    import unicodedata
    from app.material.services import zuruecksetzen as z
    nfd = unicodedata.normalize("NFD", "https://strömis.de")
    gesperrt = ["https://strömis.de", "HTTPS://STRÖMIS.DE/", "https://strömis.de:443/x", "https://xn--strmis-yxa.de",
                "https://XN--STRMIS-YXA.DE", "https://strömis.de.", "https://www.strömis.de", "https://user:pw@strömis.de",
                "strömis.de", "//strömis.de", " https://strömis.de", "https://strömis.de ", nfd, "https://strömis。de",
                "https://STRÖMIS.de", "https://strömis.de\t", "https://wiki.strömis.de", "", None, "https://[::1]",
                "http://strömis.de:abc", "https://[", "https://dev", "https://devströmis.de", "https://ｓｔｒöｍｉｓ．ｄｅ",
                "   "]
    frei = ["https://dev.strömis.de", "dev.strömis.de", " https://dev.strömis.de\n", unicodedata.normalize(
        "NFD", "https://dev.strömis.de"), "https://dev.strömis。de", "HTTPS://DEV.XN--STRMIS-YXA.DE/", "https://ｄｅｖ．strömis.de",
        "http://localhost:8080", "http://127.0.0.1:8080", "https://dev.strömis.de."]
    for a in gesperrt:
        assert not z.adresse_frei(a), (a, z.host(a))
    for a in frei:
        assert z.adresse_frei(a), (a, z.host(a))
    assert z.host(nfd) == z.host("https://strömis。de") == z.host("strömis.de ") == "xn--strmis-yxa.de"
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        vorher = stand(app)
        for a in gesperrt + frei:
            for wo in ("umgebung", "anwendung"):
                env = dict(DEV) if wo == "anwendung" else {"STROEMIS_NAME": DEV["STROEMIS_NAME"], "BASE_URL": a}
                alt_env = {k: os.environ.get(k) for k in env}
                os.environ.update({k: v for k, v in env.items() if v is not None})
                if env["BASE_URL"] is None:
                    os.environ.pop("BASE_URL", None)
                app.config["BASE_URL"] = a if wo == "anwendung" else DEV["BASE_URL"]
                try:
                    with app.app_context():
                        grund = z.sperrgrund()
                    aus, code = aufrufen(app, "--trocken")
                finally:
                    for k, v in alt_env.items():
                        if v is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = v
                ist_frei = a in frei
                assert (grund is None) == ist_frei and code == (0 if ist_frei else 2), (a, wo, grund, code, aus)
                if not ist_frei:
                    teil = "BASE_URL in der Umgebung" if wo == "umgebung" else "BASE_URL der Anwendung"
                    assert teil in grund and ("fehlt" in grund or "ist „" in grund), (a, wo, grund)
        assert stand(app) == vorher and not sicherungen(app)
    print("Sperre Schreibweisen bestanden.")


KIND = r"""
import os, sys, time
from app import create_app
app = create_app()
from app.material.services import zuruecksetzen as z
echt = z._leeren
def halt(conn):
    os.write(1, b"BEREIT\n")
    time.sleep(120)
    return echt(conn)
z._leeren = halt
r = app.test_cli_runner().invoke(args=["material", "dev-zuruecksetzen", "--ja-alles-loeschen"])
sys.stdout.write(r.output)
sys.stdout.flush()
sys.exit(r.exit_code)
"""


def _kind_abbrechen(tmp, signum):
    """Den Befehl in einem eigenen Prozess starten, ihn nach dem Verschieben der Medien (in _leeren) anhalten und ihm
    signum schicken – wie docker compose restart/stop oder ein Deploy während des Laufs (Probe kill.py der Prüfung).
    Liefert (Rückgabewert, Ausgabe)."""
    import select
    import subprocess
    env = dict(os.environ, DATA_DIR=tmp, **DEV)
    kind = subprocess.Popen([sys.executable, "-S", "-c", KIND], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=env, cwd=REPO)
    try:
        bereit, _, _ = select.select([kind.stdout], [], [], 120)
        assert bereit and kind.stdout.readline().strip() == b"BEREIT", "Kind meldet sich nicht"
        kind.send_signal(signum)
        aus, _ = kind.communicate(timeout=60)
    finally:
        if kind.poll() is None:
            kind.kill()
            kind.wait(timeout=30)
    return kind.returncode, aus.decode("utf-8", "replace")


def test_abbruch_per_signal():
    """Befund 2: SIGTERM und SIGHUP mitten im Lauf (Medien schon verschoben) führen in den Rückweg – Exit 1, Datenbank und
    Medien wie vorher, keine Sicherung bleibt liegen, die Signal-Handler sind danach die alten. SIGKILL lässt sich nicht
    abfangen: Die Datenbank bleibt unverändert (SQLite verwirft den offenen Umbau), die Medien liegen in der Sicherung,
    und deren LIESMICH.txt (vor dem ersten Verschieben geschrieben) bringt sie mit ihren mv-Zeilen zurück."""
    import signal
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        ok(k["katalog"].post(f"/api/material/produkte/{ids['gurt']}/bild", data={"file": (jpeg(), "gurt.jpg")},
                             headers=H, content_type="multipart/form-data"))
        gid, _ = gliederung(k["adm"])
        neuer_artikel(k["wart"], ids["hms"], ordner_neu(k["wart"], gid, "Lager Platzhalter"), serial_no="PH-1")
        os.makedirs(os.path.join(tmp, "pdf", "2026"))
        with open(os.path.join(tmp, "pdf", "2026", "P-platzhalter.pdf"), "wb") as fh:
            fh.write(PDF)
        make_app(tmp)                    # die Startschritte legen die Datei ohne Zeile nach pdf/verwaist – wie im Kind
        vorher = stand(app)
        for signum in (signal.SIGTERM, signal.SIGHUP):
            code, aus = _kind_abbrechen(tmp, signum)
            name = signal.Signals(signum).name
            assert code == 1 and f"Signal {name}" in aus and "nichts geändert" in aus, (name, code, aus)
            jetzt = stand(app)
            assert jetzt == vorher and not sicherungen(app), (name, sicherungen(app), {
                (t, x): (vorher[t].get(x), jetzt[t].get(x))
                for t in vorher for x in set(vorher[t]) | set(jetzt[t]) if vorher[t].get(x) != jetzt[t].get(x)})
        # Die Handler sind nach einem Lauf wieder die alten (hier im Testprozess, ohne Signal).
        alt = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP))
        from app.material.services import zuruecksetzen as z
        with z._signale_abfangen():
            assert signal.getsignal(signal.SIGTERM) not in alt
        assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)) == alt
        # SIGKILL: halber Zustand, aber mit Anleitung.
        code, _ = _kind_abbrechen(tmp, signal.SIGKILL)
        assert code == -signal.SIGKILL, code
        (ordner,) = sicherungen(app)
        sicherung = os.path.join(tmp, ordner)
        nachher = stand(app)
        assert nachher["modul"] == vorher["modul"] and nachher["aussen"] == vorher["aussen"]
        assert all(not os.path.exists(os.path.join(tmp, rel)) for rel in MEDIEN)
        with open(os.path.join(sicherung, "LIESMICH.txt"), encoding="utf-8") as fh:
            liesmich = fh.read()
        assert "LAUF UNVOLLSTÄNDIG" in liesmich and "BITTE LÖSCHEN" in liesmich, liesmich
        zeilen = [z_.split()[:3] for z_ in liesmich.splitlines() if z_.strip().startswith("mv ")]
        assert len(zeilen) == 2 and "cp data/" not in liesmich, liesmich
        for _, quelle, ziel in zeilen:                   # der Rückweg aus LIESMICH.txt, data/ = tmp
            os.rename(os.path.join(tmp, quelle[len("data/"):]), os.path.join(tmp, ziel[len("data/"):]))
        for rest in ("stroemis.db", "LIESMICH.txt"):
            os.remove(os.path.join(sicherung, rest))
        os.rmdir(os.path.join(sicherung, "media"))
        os.rmdir(sicherung)
        assert stand(app) == vorher
    print("Abbruch per Signal bestanden.")


def test_katalogimport():
    """Läuft ein Katalogimport (Sperre gehalten oder frisches Lebenszeichen), bricht der Befehl ab und ändert nichts;
    --trocken warnt. Danach leert er DATA_DIR/katalog-import bis auf die Sperrdatei."""
    import json
    import shutil

    from test_material_importauftrag import hoch, katalog_zip

    from test_material import import_abwarten
    from app.material.services import importauftrag
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        probe = import_abwarten(k["katalog"], hoch(k["katalog"], katalog_zip(1, mit_dateien=False)))
        assert probe["uebernehmbar"], probe
        ordner = os.path.join(tmp, "katalog-import")
        vorher = stand(app)
        with app.app_context():
            sperre = importauftrag._sperre_nehmen()
        try:
            with umwelt(app, **DEV):
                aus, code = aufrufen(app, "--trocken")
                assert code == 0 and "ACHTUNG Gerade läuft ein Katalogimport" in aus and "katalog-import" in aus, aus
                aus, code = aufrufen(app, "--ja-alles-loeschen")
            assert code == 1 and "Gerade läuft ein Katalogimport" in aus and "nichts geändert" in aus, (code, aus)
        finally:
            sperre.close()
        # Ohne Sperre, aber mit frischem Lebenszeichen (Prozess eben erst weg): ebenso.
        frisch = "c" * 32
        with app.app_context():
            jetzt = importauftrag.db.now()
        with open(os.path.join(ordner, frisch + ".json"), "w", encoding="utf-8") as fh:
            json.dump({"id": frisch, "zustand": "laeuft", "trocken": True, "quelle": "k.zip", "gestartet": jetzt,
                       "lebenszeichen": jetzt}, fh)
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--ja-alles-loeschen")
        assert code == 1 and "Gerade läuft ein Katalogimport" in aus, (code, aus)
        os.remove(os.path.join(ordner, frisch + ".json"))
        assert stand(app) == vorher and not sicherungen(app)
        # Kein Import: Zurücksetzen geht und leert die Aufträge.
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--ja-alles-loeschen")
        assert code == 0 and "Dateien geleert (Aufträge des Katalogimports)" in aus, (code, aus)
        assert os.listdir(ordner) == ["sperre"], os.listdir(ordner)
        assert k["katalog"].get(f"/api/material/katalog/import/{probe['id']}").status_code == 404
        for name in sicherungen(app):
            shutil.rmtree(os.path.join(tmp, name))
    print("Katalogimport bestanden.")


if __name__ == "__main__":
    test_sperren()
    test_sperre_schreibweisen()
    test_scheitern()
    test_abbruch_per_signal()
    test_zuruecksetzen()
    test_katalogimport()
