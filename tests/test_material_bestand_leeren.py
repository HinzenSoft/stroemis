"""Nur den Bestand der Materialablage auf dev leeren (flask material dev-bestand-leeren, Wunsch vom 08.11.2026):
python tests/test_material_bestand_leeren.py  oder  pytest …

Ein Bestand mit jeder Art Inhalt (Gliederung, Artikel, Prüfung mit Befund- und Anhangfoto, Ordnerfoto, Mangel mit Foto,
Lebenslauf, Durchgang, Bestandsimport, Produktmeldung mit Ordner und Foto, Rückruf) und ein kleiner Beispielbestand aus
scripts/material_beispielbestand.py: Danach sind die Tabellen des Bestands leer, Katalog, Formulare (samt Pool,
Zuweisungen und den DEMO-Formularen), Rückrufe, Meldungen (bis auf den Ordner), Katalog- und Kontojournal, Konten (bis
auf die DEMO-Konten des Skripts), die übrigen Module, Einstellungen, Zähler und das ganze Schema samt Triggern
unverändert; die Medien des Bestands liegen Datei für Datei in der Sicherung, die des Katalogs am Platz; die Trigger
sperren wieder. Danach startet die App, und der Beispielbestand lässt sich erneut anlegen. Sperren: Produktion, ohne
Schalter, laufender Katalogimport, nicht eingeordnete Tabelle; Scheitern von Sicherung, Verschieben und Löschen und
SIGTERM lassen alles, wie es war.
Alle Namen und Nummern hier sind Platzhalter."""
import errno
import os
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, jpeg, katalog_grund, make_app, neuer_artikel, neues_konto, starten,  # noqa: E402
                           umgebung)
from test_material_beispielbestand import laufen as beispiel_laufen  # noqa: E402
from test_material_dev_zuruecksetzen import (DEV, KIND, bestand_aufbauen, dateien, rechte,  # noqa: E402
                                             umwelt)
from test_material_import import ok  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEFEHL = "dev-bestand-leeren"
SCHALTER = "--ja-bestand-loeschen"


def aufrufen(app, *schalter):
    r = app.test_cli_runner().invoke(args=["material", BEFEHL, *schalter])
    if r.exception and not isinstance(r.exception, SystemExit):
        raise r.exception
    return r.output, r.exit_code


def sicherungen(app):
    return sorted(n for n in os.listdir(app.config["DATA_DIR"]) if n.startswith("sicherung-"))


def datenbank(db_pfad):
    """Jede Zeile jeder Tabelle (ohne Schattentabellen des Volltexts), das ganze Schema und sqlite_sequence."""
    conn = sqlite3.connect(db_pfad)
    try:
        namen = sorted(r[1] for r in conn.execute("PRAGMA main.table_list")
                       if r[2] == "table" and not r[1].startswith("sqlite_"))
        out = {t: conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in namen}
        out["#schema"] = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
        out["#sequenz"] = conn.execute("SELECT * FROM sqlite_sequence ORDER BY name").fetchall()
        out["#spalten"] = {t: [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')] for t in namen}
        out["#volltext"] = conn.execute("SELECT COUNT(*) FROM mat_item_fts").fetchone()[0]
        return out
    finally:
        conn.close()


def stand(app):
    return {"db": datenbank(app.config["DB_PATH"]),
            "dateien": dateien(app.config["DATA_DIR"], ohne=("stroemis.db", os.path.join("katalog-import", "sperre")))}


def bestand_voll(tmp):
    """bestand_aufbauen (Katalog mit Bild und Dokument, Gliederung, Artikel, Lebenslauf, Durchgang, Bestandsimport,
    Beispielbestand mit 8 Artikeln, Wiki, Spot, Lehrgang) und dazu: Ordnerfoto, Befundfoto, Prüfanhang, Mangelfoto,
    Produktmeldung mit Ordner und Foto, Rückruf, „Zuletzt besucht“ mit Artikel und Album, ein fremdes Konto mit
    @example.invalid und ein Probelauf-Verzeichnis des Katalogimports."""
    app, k = bestand_aufbauen(tmp)
    w, p = k["wart"], k["pruefer"]
    with app.app_context():
        from app import db
        gid = db.query("SELECT id FROM mat_folder WHERE parent_id IS NULL AND demo = 0", one=True)["id"]
        hms = db.query("SELECT id FROM mat_product WHERE model = 'HMS Beta' AND manufacturer = 'Testwerk'", one=True)["id"]
    lager = ordner_neu(w, gid, "Lager Foto Platzhalter")
    ok(w.post(f"/api/material/ordner/{lager}/foto", data={"file": (jpeg(), "lager.jpg")}, headers=H,
              content_type="multipart/form-data"))
    a = neuer_artikel(w, hms, lager, serial_no="PH-FOTO-1")
    pr = ok(starten(p, a["id"]), 201)["pruefung"]
    ok(p.post(f"/api/material/pruefungen/{pr['id']}/punkte/{pr['punkte'][0]['id']}/foto", headers=H,
              content_type="multipart/form-data", data={"file": (jpeg(), "befund.jpg")}))
    ok(p.post(f"/api/material/pruefungen/{pr['id']}/anhaenge", headers=H, content_type="multipart/form-data",
              data={"file": [(jpeg(), "scan.jpg")], "art": "foto", "titel": "Platzhalter-Scan"}), 201)
    ok(k["fuehrung"].post(f"/api/material/artikel/{a['id']}/mangel", headers=H, content_type="multipart/form-data",
                          data={"beschreibung": "Platzhalter-Mangel", "fotos": [(jpeg(), "m.jpg")]}), 201)
    ok(w.post("/api/material/meldungen", headers=H, content_type="multipart/form-data",
              data={"manufacturer": "Meldewerk", "model": "Platzhalter", "folder_id": str(lager),
                    "fotos": (jpeg(), "etikett.jpg")}), 201)
    ok(k["katalog"].post(f"/api/material/produkte/{hms}/rueckrufe", headers=H,
                         json={"title": "Platzhalter-Rückruf", "serials": "", "mail": False}), 201)
    # Eine globale Suche (Protokoll in mat_global_search) – der Materialwart sucht eine Seriennummer außerhalb seines Bereichs.
    ok(w.post("/api/material/globalsuche", json={"q": "DEMO-NS-4711", "bestaetigt": True}))
    neues_konto(app, "andere@example.invalid", stufe=0)
    with app.app_context():
        from app import db, start
        uid = db.query("SELECT id FROM users WHERE email = 'admin@example.org'", one=True)["id"]
        db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?)",
                   (start.ZIELE.format(uid=uid), f'[["material", {a["id"]}, "2026-11-08 10:00:00"], '
                                                 '["karte", 1, "2026-11-08 09:00:00"]]'))
    return app, k


def test_einordnung():
    """Jede Tabelle des frischen Schemas und jede Entität des Journals (beschriftung.ENTITAET) ist eingeordnet – ein
    neuer Schemaschritt muss hier entscheiden, ob seine Tabelle zum Bestand gehört."""
    from app.material.services import bestand_leeren as bl
    from app.material.services.beschriftung import ENTITAET
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        conn = sqlite3.connect(app.config["DB_PATH"])
        try:
            assert bl.einordnen(conn) == [], bl.einordnen(conn)
            alle = {r[1] for r in conn.execute("PRAGMA main.table_list") if r[1].startswith("mat_") and r[2] != "shadow"}
        finally:
            conn.close()
        bekannt = set(bl.BESTAND) | set(bl.VOLLTEXT_BESTAND) | set(bl.BLEIBT) | set(bl.TEILWEISE)
        assert alle == bekannt, (alle - bekannt, bekannt - alle)
        assert len(set(bl.BESTAND) | set(bl.BLEIBT)) == len(bl.BESTAND) + len(bl.BLEIBT)
        assert set(ENTITAET) == set(bl.JOURNAL_BESTAND) | set(bl.JOURNAL_BLEIBT), set(ENTITAET)
    for mail in ("demo-wart-a@example.invalid", "demo-mv@example.invalid", "demo-einsatzkraft-01@example.invalid",
                 "demo-einsatzkraft-42@example.invalid", "demo-pruefer-2@example.invalid"):
        assert bl.DEMO_KONTEN.fullmatch(mail), mail
    for mail in ("demo-wart-c@example.invalid", "demo-mv@example.org", "x-demo-mv@example.invalid", "demo@example.invalid",
                 "demo-einsatzkraft-1@example.invalid", "demo-mv@example.invalid.de"):
        assert not bl.DEMO_KONTEN.fullmatch(mail), mail
    print("Einordnung bestanden.")


def test_sperren():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        from test_material import gliederung
        gid, _ = gliederung(k["adm"])
        neuer_artikel(k["wart"], ids["hms"], ordner_neu(k["wart"], gid, "Lager Platzhalter"), serial_no="PH-1")
        vorher = stand(app)
        faelle = [
            ({"STROEMIS_NAME": None, "BASE_URL": DEV["BASE_URL"]}, "STROEMIS_NAME ist „nicht gesetzt“"),
            ({"STROEMIS_NAME": "stroemis", "BASE_URL": DEV["BASE_URL"]}, "STROEMIS_NAME ist „stroemis“"),
            ({"STROEMIS_NAME": "stroemis-dev", "BASE_URL": "https://strömis.de"}, "BASE_URL in der Umgebung ist"),
            ({"STROEMIS_NAME": "stroemis-dev", "BASE_URL": "https://www.xn--strmis-yxa.de/"}, "frei ist nur"),
        ]
        for werte, text in faelle:
            for schalter in ((SCHALTER,), ("--trocken",), ("--trocken", SCHALTER), ()):
                with umwelt(app, **werte):
                    aus, code = aufrufen(app, *schalter)
                assert code == 2 and text in aus and "nichts geändert" in aus, (werte, schalter, code, aus)
        with umwelt(app, **DEV):
            aus, code = aufrufen(app)
        assert code == 2 and f"Ohne {SCHALTER}" in aus and "--trocken" in aus, (code, aus)
        # Der Schalter von dev-zuruecksetzen gilt hier nicht.
        r = app.test_cli_runner().invoke(args=["material", BEFEHL, "--ja-alles-loeschen"])
        assert r.exit_code == 2 and "No such option" in r.output, r.output
        for schalter in (("--trocken",), ("--trocken", SCHALTER)):
            with umwelt(app, **DEV):
                aus, code = aufrufen(app, *schalter)
            assert code == 0 and aus.startswith("Probelauf – nichts geändert."), (code, aus)
            assert "mat_item " in aus and "Sicherung nach:" in aus and "sicherung-bestand-" in aus, aus
            assert "Bleibt: Katalog" in aus and "Zähler" in aus, aus
        # BASE_URL der Anwendung zeigt auf die Produktion.
        with app.app_context():
            from app import db
            db.execute("INSERT INTO einstellungen (schluessel, wert, geaendert_am) VALUES ('BASE_URL', "
                       "'https://strömis.de', ?)", (db.now(),))
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, SCHALTER)
        assert code == 2 and "BASE_URL der Anwendung" in aus, (code, aus)
        with app.app_context():
            from app import db, einstellungen
            db.execute("DELETE FROM einstellungen WHERE schluessel = 'BASE_URL'")
            einstellungen.anwenden()
        assert stand(app) == vorher and not sicherungen(app)
        # Eine Tabelle des Moduls, die niemand eingeordnet hat: Probelauf und Lauf brechen ab (1), nichts geändert.
        with app.app_context():
            from app import db
            db.execute("CREATE TABLE mat_platzhalter_neu (id INTEGER PRIMARY KEY)")
        vorher = stand(app)
        for schalter in (("--trocken",), (SCHALTER,)):
            with umwelt(app, **DEV):
                aus, code = aufrufen(app, *schalter)
            assert code == 1 and "mat_platzhalter_neu" in aus and "nichts geändert" in aus, (schalter, code, aus)
        assert stand(app) == vorher and not sicherungen(app)
    print("Sperren bestanden.")


def _ohne(zeilen, spalten, weg):
    """Zeilen ohne die Spalten in weg (Vergleich der Produktmeldungen ohne folder_id)."""
    idx = [i for i, s in enumerate(spalten) if s not in weg]
    return [tuple(z[i] for i in idx) for z in zeilen]


def test_leeren():
    from app.material.services import bestand_leeren as bl
    with tempfile.TemporaryDirectory() as tmp:
        app, k = bestand_voll(tmp)
        db_pfad = app.config["DB_PATH"]
        vorher = stand(app)
        v = vorher["db"]
        for t in ("mat_item", "mat_inspection", "mat_inspection_result", "mat_inspection_attachment", "mat_round",
                  "mat_import", "mat_import_row", "mat_folder_grant", "mat_lebenslauf", "mat_defect_report",
                  "mat_item_change", "mat_round_setprotokoll", "mat_global_search"):
            assert v[t], t
        for t in ("mat_formular", "mat_form", "mat_formular_zuweisung", "mat_recall", "mat_product_request",
                  "mat_product_document"):
            assert v[t], t
        sp = v["#spalten"]
        demo = {z[sp["users"].index("email")]: z[0] for z in v["users"]
                if re.fullmatch(r"demo-.*@example\.invalid", z[sp["users"].index("email")])}
        assert "demo-mv@example.invalid" in demo and "demo-einsatzkraft-01@example.invalid" in demo, demo
        # Die Medien: Fotos des Bestands (Ordner, Befund, Mangel), Anhang, Protokolle; dazu die des Katalogs.
        conn = sqlite3.connect(db_pfad)
        bestand_keys = {os.path.splitext(n)[0] for n, in conn.execute(
            "SELECT photo FROM mat_folder WHERE photo <> '' UNION SELECT photo FROM mat_inspection_result "
            "WHERE photo <> ''")}
        bestand_keys |= {os.path.splitext(n)[0] for (j,) in conn.execute("SELECT photos_json FROM mat_defect_report")
                         for n in __import__("json").loads(j)}
        katalog_keys = {os.path.splitext(n)[0] for n, in conn.execute("SELECT image FROM mat_product WHERE image <> ''")}
        katalog_keys |= {os.path.splitext(n)[0] for (j,) in conn.execute("SELECT photos_json FROM mat_product_request")
                         for n in __import__("json").loads(j)}
        conn.close()
        assert len(bestand_keys) >= 3 and katalog_keys and not bestand_keys & katalog_keys

        def wandert(rel):
            teile = rel.split(os.sep)
            if teile[0] == "pdf":
                return teile[1] != "lebenslauf"
            if teile[:2] != ["media", "material"]:
                return False
            return teile[2] == "anhang" or (teile[2] in bl.FOTO_ARTEN and os.path.splitext(teile[3])[0] in bestand_keys)
        bewegt = {p: s for p, s in vorher["dateien"].items() if wandert(p)}
        assert any(p.startswith("pdf" + os.sep + "20") for p in bewegt) and any("anhang" in p for p in bewegt)
        assert any(p.startswith(os.path.join("pdf", "lebenslauf")) for p in vorher["dateien"]), "Zählerdatei fehlt"

        with umwelt(app, **DEV):
            aus, code = aufrufen(app, "--trocken")
        assert code == 0 and "demo-wart-a@example.invalid (DEMO-Materialwart Flussland)" in aus, aus
        assert "andere@example.invalid (andere) – nicht aus dem Beispielbestand" in aus, aus
        assert stand(app) == vorher
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, SCHALTER)
        assert code == 0, (code, aus)
        assert aus.startswith("Bestand der Materialablage geleert. Sicherung:") and "docker compose restart" in aus, aus
        assert "DEMO-Konten des Beispielbestands gelöscht" in aus and "demo-mv@example.invalid" in aus, aus
        assert f"{len(bewegt)} Dateien" in aus or "Dateien" in aus, aus
        (ordner,) = sicherungen(app)
        assert ordner.startswith("sicherung-bestand-")
        sicherung = os.path.join(tmp, ordner)
        nachher = stand(app)
        n = nachher["db"]
        # Bestand leer, Volltext leer.
        assert {t: len(n[t]) for t in bl.BESTAND if n[t]} == {} and n["#volltext"] == 0
        # Schema samt Triggern Zeichen für Zeichen wie vorher, Zähler (sqlite_sequence) unverändert.
        assert n["#schema"] == v["#schema"] and n["#sequenz"] == v["#sequenz"]
        # Katalog und Formulare unverändert; Produktmeldungen nur ohne Ordner.
        for t in bl.BLEIBT:
            if t in n and t != "mat_product_request":
                assert n[t] == v[t], t
        weg = ("folder_id",)
        assert _ohne(n["mat_product_request"], sp["mat_product_request"], weg) == _ohne(
            v["mat_product_request"], sp["mat_product_request"], weg)
        assert all(z[sp["mat_product_request"].index("folder_id")] is None for z in n["mat_product_request"])
        # Journal: nur Katalog und Konten – ohne die Einträge an gelöschten DEMO-Konten.
        a = sp["mat_audit"]
        erwartet = [z for z in v["mat_audit"] if z[a.index("entity")] not in bl.JOURNAL_BESTAND
                    and not (z[a.index("entity")] == "user" and z[a.index("entity_id")] in demo.values())]
        assert n["mat_audit"] == erwartet and erwartet
        # mat_meta: ohne Merker des Beispielbestands, Zähler bleiben, „Zuletzt besucht“ ohne Artikel.
        meta_v, meta_n = dict(v["mat_meta"]), dict(n["mat_meta"])
        assert "beispielbestand_gross" in meta_v and "beispielbestand_gross" not in meta_n
        assert meta_n["inventar_zaehler"] == meta_v["inventar_zaehler"] and int(meta_n["inventar_zaehler"]) > 0
        assert [s for s in meta_v if s.startswith("lebenslauf_zaehler_")] and all(
            meta_n[s] == meta_v[s] for s in meta_v if s.startswith("lebenslauf_zaehler_"))
        ziele = [s for s in meta_n if s.startswith("start:ziele:")]
        assert ziele and all('"material"' not in meta_n[s] for s in ziele) and any('"karte"' in meta_n[s] for s in ziele)
        assert {s: w for s, w in meta_n.items() if not s.startswith("start:ziele:")} == {
            s: w for s, w in meta_v.items() if s not in bl.MERKER and not s.startswith("start:ziele:")
            and not any(s.endswith(f":{u}") for u in demo.values())}
        # Konten: nur die DEMO-Konten des Skripts weg; alle übrigen Zeilen außerhalb des Moduls unverändert.
        e = sp["users"].index("email")
        assert [z for z in n["users"]] == [z for z in v["users"] if z[e] not in demo]
        assert any(z[e] == "andere@example.invalid" for z in n["users"])
        for t in v:
            if not t.startswith(("mat_", "#")) and t != "users":
                assert n[t] == v[t], t
        # Dateien: was wandert, liegt Datei für Datei in der Sicherung; alles andere (Katalog, Wiki, Spots,
        # Zählerdateien) unverändert am Platz.
        assert {p: s for p, s in nachher["dateien"].items() if not p.startswith(ordner)} == {
            p: s for p, s in vorher["dateien"].items() if p not in bewegt}
        assert dateien(sicherung, ohne=("stroemis.db", "LIESMICH.txt")) == bewegt
        kopie = os.path.join(sicherung, "stroemis.db")
        assert datenbank(kopie) == v
        c = sqlite3.connect(kopie)
        assert c.execute("PRAGMA foreign_key_check").fetchall() == [] and c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        c.close()
        assert rechte(sicherung) == 0o700 and rechte(kopie) == 0o600 and rechte(os.path.join(sicherung, "LIESMICH.txt")) \
            == 0o600
        with open(os.path.join(sicherung, "LIESMICH.txt"), encoding="utf-8") as fh:
            liesmich = fh.read()
        assert f"cp data/{ordner}/stroemis.db data/stroemis.db" in liesmich and "cp -a" in liesmich, liesmich
        assert "LAUF UNVOLLSTÄNDIG" not in liesmich and "BITTE LÖSCHEN" in liesmich and f"rm -rf data/{ordner}" in aus
        # Integrität und Fremdschlüssel; die Unveränderlichkeit greift wieder.
        conn = sqlite3.connect(db_pfad)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            for sql in ("DELETE FROM mat_audit", "UPDATE mat_audit SET action = 'x'"):
                try:
                    conn.execute(sql)
                    raise AssertionError(sql)
                except sqlite3.IntegrityError as exc:
                    assert "unveränderlich" in str(exc), exc
        finally:
            conn.close()

        # Neustart, Modul benutzbar; der Beispielbestand lässt sich erneut anlegen – neue Inventarnummern.
        app2 = make_app(tmp)
        c = app2.test_client()
        ok(c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}))
        assert ok(c.get("/api/material/start"))
        assert c.get(f"/api/material/meldungen/{v['mat_product_request'][0][0]}").status_code == 200
        aus2, code = beispiel_laufen("--beispielbestand", "--artikel", "8")
        assert code == 0 and "festgeschrieben mit Protokoll" in aus2, (code, aus2)
        neu = datenbank(db_pfad)
        assert len(neu["mat_formular"]) == len(v["mat_formular"]) and neu["mat_form"] == v["mat_form"]
        alt_nr = {z[sp["mat_item"].index("inventory_no")] for z in v["mat_item"]}
        neu_nr = {z[sp["mat_item"].index("inventory_no")] for z in neu["mat_item"]}
        assert neu_nr and not neu_nr & alt_nr and min(neu_nr) > max(alt_nr), (min(neu_nr), max(alt_nr))
        pfade = [z[sp["mat_inspection"].index("pdf_path")] for z in neu["mat_inspection"]]
        assert all(os.path.isfile(os.path.join(tmp, p)) for p in pfade if p)
        # Ein zweiter Lauf geht ebenso und nennt die ältere Sicherung.
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, SCHALTER)
        assert code == 0 and ordner in aus.split("Ältere Sicherungen", 1)[1], (code, aus)
        assert {t for t in bl.BESTAND if datenbank(db_pfad)[t]} == set()
    print("Leeren bestanden.")


def test_scheitern():
    """Sicherung, Verschieben oder Löschen scheitern: nichts geändert, keine Sicherung bleibt liegen."""
    from app.material.services import bestand_leeren as bl
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        from test_material import gliederung
        gid, _ = gliederung(k["adm"])
        lager = ordner_neu(k["wart"], gid, "Lager Platzhalter")
        ok(k["wart"].post(f"/api/material/ordner/{lager}/foto", data={"file": (jpeg(), "lager.jpg")}, headers=H,
                          content_type="multipart/form-data"))
        neuer_artikel(k["wart"], ids["hms"], lager, serial_no="PH-1")
        os.makedirs(os.path.join(tmp, "pdf", "2026"))
        with open(os.path.join(tmp, "pdf", "2026", "P-platzhalter.pdf"), "wb") as fh:
            fh.write(PDF)
        vorher = stand(app)
        echt_rename, echt_fsync, echt_loeschen = os.rename, os.fsync, bl._loeschen
        pdf = os.path.join(tmp, "pdf", "2026")

        def fsync_kaputt(_fd):
            raise OSError(errno.EIO, "Platzhalter: Schreibfehler")

        def rename_kaputt(quelle, ziel):
            if quelle == pdf:
                raise OSError(errno.EXDEV, "Platzhalter: anderes Dateisystem")
            return echt_rename(quelle, ziel)

        def loeschen_kaputt(conn, b):
            echt_loeschen(conn, b)
            raise sqlite3.DatabaseError("Platzhalter: Löschen gescheitert")

        def trigger_fehlt(conn, b):
            echt_loeschen(conn, b)
            conn.execute("DROP TRIGGER mat_inspection_unloeschbar")

        for name, ziel, ersatz, text in (
                ("fsync", os, fsync_kaputt, "Die Sicherung der Datenbank ist gescheitert"),
                ("rename", os, rename_kaputt, "nichts geändert: Datenbank unverändert, Medien zurück"),
                ("_loeschen", bl, loeschen_kaputt, "Löschen gescheitert"),
                ("_loeschen", bl, trigger_fehlt, "Schema oder Trigger nach dem Leeren anders")):
            alt = getattr(ziel, name)
            setattr(ziel, name, ersatz)
            try:
                with umwelt(app, **DEV):
                    aus, code = aufrufen(app, SCHALTER)
            finally:
                setattr(ziel, name, alt)
            assert code == 1 and text in aus and "FEHLER" in aus, (name, code, aus)
            assert stand(app) == vorher, name
            assert not sicherungen(app), (name, sicherungen(app))
        assert (os.rename, os.fsync, bl._loeschen) == (echt_rename, echt_fsync, echt_loeschen)
    print("Scheitern bestanden.")


def test_katalogimport():
    """Läuft ein Katalogimport, bricht der Befehl ab und ändert nichts; --trocken warnt. Die Aufträge des Katalogimports
    bleiben danach (der Katalog bleibt ja)."""
    from test_material_importauftrag import hoch, katalog_zip

    from test_material import import_abwarten
    from app.material.services import importauftrag
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        probe = import_abwarten(k["katalog"], hoch(k["katalog"], katalog_zip(1, mit_dateien=False)))
        assert probe["uebernehmbar"], probe
        vorher = stand(app)
        with app.app_context():
            sperre = importauftrag._sperre_nehmen()
        try:
            with umwelt(app, **DEV):
                aus, code = aufrufen(app, "--trocken")
                assert code == 0 and "ACHTUNG Gerade läuft ein Katalogimport" in aus, aus
                aus, code = aufrufen(app, SCHALTER)
            assert code == 1 and "Gerade läuft ein Katalogimport" in aus and "nichts geändert" in aus, (code, aus)
        finally:
            sperre.close()
        assert stand(app) == vorher and not sicherungen(app)
        with umwelt(app, **DEV):
            aus, code = aufrufen(app, SCHALTER)
        assert code == 0, (code, aus)
        assert k["katalog"].get(f"/api/material/katalog/import/{probe['id']}").status_code == 200
    print("Katalogimport bestanden.")


def test_abbruch_per_signal():
    """SIGTERM mitten im Lauf (Medien schon verschoben, in _loeschen angehalten): Rückweg – Exit 1, alles wie vorher."""
    import select
    import signal
    import subprocess
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        from test_material import gliederung
        gid, _ = gliederung(k["adm"])
        lager = ordner_neu(k["wart"], gid, "Lager Platzhalter")
        ok(k["wart"].post(f"/api/material/ordner/{lager}/foto", data={"file": (jpeg(), "lager.jpg")}, headers=H,
                          content_type="multipart/form-data"))
        neuer_artikel(k["wart"], ids["hms"], lager, serial_no="PH-1")
        make_app(tmp)
        vorher = stand(app)
        kind = (KIND.replace("zuruecksetzen as z", "bestand_leeren as z").replace("z._leeren", "z._loeschen")
                .replace("def halt(conn):", "def halt(conn, b):").replace("echt(conn)", "echt(conn, b)")
                .replace("dev-zuruecksetzen", BEFEHL).replace("--ja-alles-loeschen", SCHALTER))
        assert "bestand_leeren" in kind and BEFEHL in kind and "echt(conn, b)" in kind
        env = dict(os.environ, DATA_DIR=tmp, **DEV)
        p = subprocess.Popen([sys.executable, "-S", "-c", kind], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             env=env, cwd=REPO)
        try:
            bereit, _, _ = select.select([p.stdout], [], [], 120)
            assert bereit and p.stdout.readline().strip() == b"BEREIT", "Kind meldet sich nicht"
            p.send_signal(signal.SIGTERM)
            aus, _ = p.communicate(timeout=60)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=30)
        aus = aus.decode("utf-8", "replace")
        assert p.returncode == 1 and "Signal SIGTERM" in aus and "nichts geändert" in aus, (p.returncode, aus)
        assert stand(app) == vorher and not sicherungen(app)
    print("Abbruch per Signal bestanden.")


if __name__ == "__main__":
    test_einordnung()
    test_sperren()
    test_scheitern()
    test_katalogimport()
    test_abbruch_per_signal()
    test_leeren()
