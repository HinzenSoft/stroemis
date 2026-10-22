"""Herstellerdokumente einmal je Inhalt (Modul Material, Schritt 18, Entscheidung des Nutzers vom 22.10.2026):
python tests/test_material_dokumente.py

Eine Dokumentdatei heißt nach ihrem Inhalt (<SHA-256><Endung> unter media/material/dok) und gehört allen Dokumenten mit
diesem Inhalt; entfernt wird sie erst, wenn kein Dokument sie mehr nennt. Geprüft werden Hochladen (zwei Produkte, eine
Datei), Variante, Löschen von Produkt und Kategorie, die Regel „ein Dokument aus einem festgeschriebenen Protokoll
bleibt“, neue Versionen, der Katalogimport (eine Datei für drei Produkte, Probelauf, Rollback nach spätem Fehler) und die
Zusammenführung des Altbestands beim Start (Schritt 18: Dubletten, falsche Prüfsummen, fehlende Datei, zweiter Lauf,
Medien nicht erreichbar, Kommandozeile). Nach der Sicherheitsprüfung vom 22.10.2026 dazu: der Wettlauf „letztes Produkt
löschen“ gegen „denselben Inhalt ablegen“ (Hochladen, Import, Variante – Befund 1) und das Aufräumen des Ordners
(Dateien ohne Zeile nach einem Abbruch nach dem Commit, alte Zwischendateien – Befunde 2 und 3). Alle Inhalte sind
Platzhalter."""
import hashlib
import io
import json
import logging
import os
import secrets
import shutil
import sqlite3
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, PDF, abschluss, anmelden, gliederung, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, pruef_formulare, starten, umgebung)
from test_material_trennung import bis_schritt, endversion  # noqa: E402

# Eine KOPIE einer Datenbank auf Stand 7 für den Pfad 7 → 18 – nur, wenn angegeben; die Quelle bleibt unberührt.
KOPIE_STAND_7 = os.environ.get("MATERIAL_KOPIE_STAND_7") or ""

PDF_A = PDF + b"%inhalt-a"
PDF_B = PDF + b"%inhalt-b"
PDF_C = PDF + b"%inhalt-c"


def sha(daten):
    return hashlib.sha256(daten).hexdigest()


def hoch(c, url, inhalt, name, **felder):
    return c.post(url, data=dict(felder, file=(io.BytesIO(inhalt), name)), headers=H, content_type="multipart/form-data")


def dok_ordner(tmp):
    return os.path.join(tmp, "media", "material", "dok")


def dateien(tmp):
    """Die Dokumentdateien auf der Platte – ohne Zwischendateien (die dürfen nach keinem Aufruf übrig sein)."""
    try:
        namen = sorted(os.listdir(dok_ordner(tmp)))
    except FileNotFoundError:
        return set()
    assert not [n for n in namen if n.startswith(".")], namen
    return set(namen)


def zeilen(app, abfrage, args=()):
    with app.app_context():
        from app import db
        return [dict(r) for r in db.query(abfrage, args)]


def dokument_anlegen(c, pid, inhalt, name="anleitung.pdf", **felder):
    r = hoch(c, f"/api/material/produkte/{pid}/dokumente", inhalt, name,
             **dict({"kind": "gebrauchsanleitung", "valid_from": "2024-01-01"}, **felder))
    assert r.status_code == 201, r.get_json()
    return r.json["dokument_id"], next(d for d in r.json["dokumente"] if d["id"] == r.json["dokument_id"])


# --- 1. Eine Datei für alle Dokumente gleichen Inhalts -----------------------------------------------------------------

def test_gemeinsame_datei():
    """Dasselbe PDF an zwei Produkten: zwei Zeilen, eine Datei mit Inhaltsnamen. Eine Variante nennt dieselbe Datei
    (keine Kopie mehr). Löschen eines Produkts lässt die Datei stehen, solange ein anderes sie nennt; mit der letzten
    Zeile verschwindet sie. Ein zweites Hochladen desselben Inhalts lässt keine Zwischendatei zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        kp = k["katalog"]
        ids = katalog_grund(k["adm"])
        name_a = sha(PDF_A) + ".pdf"
        d1, j1 = dokument_anlegen(kp, ids["gurt"], PDF_A)
        assert j1["datei"] == f"/media/material/dok/{name_a}" and j1["sha256"] == sha(PDF_A) and j1["size"] == len(PDF_A)
        assert dateien(tmp) == {name_a}
        d2, j2 = dokument_anlegen(kp, ids["hms"], PDF_A, name="Anleitung Kopie.PDF", kind="datenblatt")
        assert j2["datei"] == j1["datei"] and d2 != d1
        assert dateien(tmp) == {name_a}
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_product_document WHERE file_path = ?", (name_a,))[0]["n"] == 2
        # Ein zweiter Inhalt: zweite Datei.
        d3, j3 = dokument_anlegen(kp, ids["gurt"], PDF_B, name="konf.pdf", kind="konformitaetserklaerung")
        assert dateien(tmp) == {name_a, sha(PDF_B) + ".pdf"}
        # Variante mit Dokumenten: dieselbe Datei, keine Kopie.
        r = kp.post(f"/api/material/produkte/{ids['gurt']}/variante",
                    json={"category_id": ids["gurte"], "manufacturer": "Testwerk", "model": "Gurt Alpha", "article_no": "GA-101",
                          "material_kind": "textil", "lifetime_years": 10, "description": "Variante", "dokumente": [d1, d3]})
        assert r.status_code == 201, r.get_json()
        variante = r.json["produkt"]["id"]
        assert dateien(tmp) == {name_a, sha(PDF_B) + ".pdf"}
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_product_document WHERE file_path = ?", (name_a,))[0]["n"] == 3
        # Auslieferung unter dem neuen Namen – mit Zugang zum Modul.
        gliederung(k["adm"], "OG Zugang")
        assert k["fuehrung"].get(j1["datei"]).status_code == 200
        assert k["fuehrung"].get("/media/material/dok/" + "0" * 64 + ".pdf").status_code == 404
        # Produkt hms weg: seine Zeile weg, die Datei bleibt (Gurt und Variante nennen sie).
        assert kp.delete(f"/api/material/produkte/{ids['hms']}", headers=H).status_code == 200
        assert dateien(tmp) == {name_a, sha(PDF_B) + ".pdf"}
        assert kp.delete(f"/api/material/produkte/{variante}", headers=H).status_code == 200
        assert dateien(tmp) == {name_a, sha(PDF_B) + ".pdf"}
        # Mit dem letzten Produkt verschwinden beide Dateien.
        assert kp.delete(f"/api/material/produkte/{ids['gurt']}", headers=H).status_code == 200
        assert dateien(tmp) == set()
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_product_document")[0]["n"] == 0
        # Ein Dokument, dessen Datenbankzeile scheitert, lässt eine schon vorhandene Datei stehen: Hochladen an ein
        # Produkt, das es nicht mehr gibt (404 nach der Prüfung des Ziels – vor dem Ablegen), und an ein
        # vorhandenes mit einem Inhalt, der schon da ist.
        dokument_anlegen(kp, _neues_produkt(kp, ids), PDF_C)
        assert dateien(tmp) == {sha(PDF_C) + ".pdf"}
        r = hoch(kp, "/api/material/produkte/999999/dokumente", PDF_C, "x.pdf", kind="datenblatt")
        assert r.status_code == 404
        assert dateien(tmp) == {sha(PDF_C) + ".pdf"}
    print("Gemeinsame-Datei-Test bestanden.")


def _neues_produkt(kp, ids, nr="NP-1"):
    r = kp.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                "model": f"Neu {nr}", "article_no": nr, "material_kind": "metall_hardware",
                                                "interval_months": 12})
    assert r.status_code == 201, r.get_json()
    return r.json["produkt"]["id"]


# --- 2. Neue Version und die Protokollregel --------------------------------------------------------------------------

def test_version_und_protokoll():
    """Eine neue Version an Produkt A lässt die alte Datei liegen – auch Produkt B nennt sie. Ein Dokument, das ein
    festgeschriebenes Protokoll nennt, verliert seine Zeile nicht (Kategorie nicht löschbar, 409) und damit auch nicht
    seine Datei; ein anderes Produkt mit derselben Datei darf trotzdem weg, die Datei bleibt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        ids = katalog_grund(k["adm"])
        pruef_formulare(kp, ids)
        name_a, name_b, name_c = (sha(x) + ".pdf" for x in (PDF_A, PDF_B, PDF_C))
        d1, _ = dokument_anlegen(kp, ids["gurt"], PDF_A)
        dokument_anlegen(kp, ids["hms"], PDF_A)
        r = hoch(kp, f"/api/material/dokumente/{d1}/version", PDF_B, "anleitung-2.pdf", version="2", valid_from="2025-01-01")
        assert r.status_code == 201, r.get_json()
        assert dateien(tmp) == {name_a, name_b}
        # hms weg: name_a bleibt (die alte Version am Gurt nennt sie), name_b auch.
        assert kp.delete(f"/api/material/produkte/{ids['hms']}", headers=H).status_code == 200
        assert dateien(tmp) == {name_a, name_b}

        # Protokollregel: Pflegehinweis (Datei C) an einer eigenen Kategorie ohne Formular; ihr Produkt hat ein
        # spezifisches Formular und wird geprüft – das Protokoll nennt das geerbte Dokument. Ein zweites Produkt (Gurt)
        # hat dieselbe Datei als Datenblatt.
        r = kp.post("/api/material/kategorien", json={"name": "Pflegekategorie", "parent_id": ids["psa"],
                                                     "default_material_kind": "metall_hardware"})
        assert r.status_code == 201, r.get_json()
        pflege = r.json["kategorie"]["id"]
        r = hoch(kp, f"/api/material/kategorien/{pflege}/dokumente", PDF_C, "pflege.pdf", kind="pflegehinweis",
                 title="Pflegehinweis", valid_from="2024-01-01")
        assert r.status_code == 201, r.get_json()
        kdok = r.json["dokument_id"]
        dokument_anlegen(kp, ids["gurt"], PDF_C, name="blatt.pdf", kind="datenblatt")
        assert dateien(tmp) == {name_a, name_b, name_c}
        hms2 = _neues_produkt(kp, dict(ids, karabiner=pflege), "HB-8")
        r = kp.post("/api/material/formulare", json={"produkt_id": hms2, "titel": "Spezifisch", "punkte": [
            {"text": "Testpunkt Verschluss", "art": "yesno", "soll": "ja"}]})
        assert r.status_code == 201, r.get_json()
        assert kp.post(f"/api/material/formulare/{r.json['formular']['id']}/aktivieren", json={}).status_code == 200
        gid, _ = gliederung(w)
        a = neuer_artikel(w, hms2, gid, serial_no="K-1")
        r = starten(p1, a["id"])
        assert r.status_code in (200, 201), r.get_json()
        pr = r.json["pruefung"]
        assert abschluss(p1, pr["id"], ergebnis="einsatzbereit").status_code == 200
        fest = p1.get(f"/api/material/pruefungen/{pr['id']}").json["pruefung"]
        assert kdok in [d["id"] for d in fest["dokumente"]], fest["dokumente"]     # das Protokoll nennt das Dokument
        # Das Produkt aus der Kategorie ziehen – dann hätte sie keine Produkte mehr und wäre löschbar, wenn nicht das
        # Protokoll wäre.
        r = kp.put(f"/api/material/produkte/{hms2}", json={"category_id": ids["karabiner"]})
        assert r.status_code == 200, r.get_json()
        r = kp.delete(f"/api/material/kategorien/{pflege}", headers=H)
        assert r.status_code == 409 and "Prüfprotokollen" in r.json["error"], r.get_json()
        assert dateien(tmp) == {name_a, name_b, name_c}
        # Der Gurt mit dem Datenblatt gleicher Datei darf weg – die Datei bleibt beim Pflegehinweis.
        assert kp.delete(f"/api/material/produkte/{ids['gurt']}", headers=H).status_code == 200
        assert dateien(tmp) == {name_c}
        assert zeilen(app, "SELECT id FROM mat_product_document WHERE file_path = ?", (name_c,)) == [{"id": kdok}]
        assert k["fuehrung"].get(f"/media/material/dok/{name_c}").status_code == 200
    print("Versions- und Protokolltest bestanden.")


# --- 3. Katalogimport ------------------------------------------------------------------------------------------------

def _zip(produkte, dateien_im_archiv, formulare=None):
    buf = io.BytesIO()
    daten = {"format": "stroemis-material-katalog", "version": 2,
             "kategorien": [{"uid": "b" * 32, "name": "Importkategorie", "materialart": "metall_hardware",
                             "intervall_monate": 12}],
             "produkte": produkte}
    if formulare is not None:
        daten["formulare"] = formulare
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("katalog.json", json.dumps(daten))
        for name, inhalt in dateien_im_archiv.items():
            z.writestr(name, inhalt)
    return buf.getvalue()


def _produkt(n, datei):
    return {"uid": f"{n:032x}", "kategorie": ["Importkategorie"], "hersteller": "Importwerk", "modell": f"Modell {n}",
            "artikelnummer": f"IW-{n}", "materialart": "metall_hardware", "intervall_monate": 12,
            "dokumente": [{"art": "gebrauchsanleitung", "titel": "Anleitung", "datei": datei}]}


def test_import():
    """Format 2: ein PDF für drei Produkte → eine Datei, drei Zeilen; ein Verweis auf einen Inhalt, der hier schon liegt,
    legt nichts Neues ab. Der Probelauf lässt keine Datei zurück. Ein später Fehler im zweiten Durchgang (Rollback) lässt
    keine neue Datei zurück und keine vorhandene verschwinden – auch nicht die, deren Inhalt der Import noch einmal
    brachte."""
    from app.material.services import importer
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        kp = k["katalog"]
        ids = katalog_grund(k["adm"])
        name_a, name_b, name_c = (sha(x) + ".pdf" for x in (PDF_A, PDF_B, PDF_C))
        dokument_anlegen(kp, ids["gurt"], PDF_A)                       # vorhanden vor dem Import
        assert dateien(tmp) == {name_a}
        pfad_b, pfad_a = f"dateien/dokumente/{name_b}", f"dateien/dokumente/{name_a}"
        roh = _zip([_produkt(1, pfad_b), _produkt(2, pfad_b), _produkt(3, pfad_b), _produkt(4, pfad_a)],
                   {pfad_b: PDF_B, pfad_a: PDF_A})

        def importieren(roh, trocken):
            r = hoch(kp, "/api/material/katalog/import", roh, "katalog.zip", trocken="1" if trocken else "0")
            assert r.status_code == 200, r.get_json()
            return r.json["bericht"]

        ber = importieren(roh, True)
        assert ber["trocken"] and not ber["fehler"] and ber["dokumente"]["neu"] == 4, ber
        assert dateien(tmp) == {name_a}
        ber = importieren(roh, False)
        assert ber["gespeichert"] and not ber["fehler"] and ber["dokumente"]["neu"] == 4, ber
        assert dateien(tmp) == {name_a, name_b}
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_product_document WHERE file_path = ?", (name_b,))[0]["n"] == 3
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_product_document WHERE file_path = ?", (name_a,))[0]["n"] == 2
        # Noch einmal derselbe Import: nichts Neues, keine Datei mehr.
        ber = importieren(roh, False)
        assert not ber["fehler"] and ber["dokumente"]["neu"] == 0, ber
        assert dateien(tmp) == {name_a, name_b}

        # Rollback: Drei weitere Produkte mit Datei C und eines mit Datei A (liegt schon da); im zweiten Durchgang
        # (nicht beim Planen) scheitert der Formularteil. Danach: keine Datei C, A und B unverändert, Zeilen wie vorher.
        vorher = zeilen(app, "SELECT id, product_id, file_path FROM mat_product_document ORDER BY id")
        pfad_c = f"dateien/dokumente/{name_c}"
        roh2 = _zip([_produkt(5, pfad_c), _produkt(6, pfad_c), _produkt(7, pfad_c), _produkt(8, pfad_a)],
                    {pfad_c: PDF_C, pfad_a: PDF_A})
        echt = importer._formulare

        def kaputt(liste, lauf):
            if not lauf.planen:
                raise RuntimeError("Testfehler nach dem Ablegen")
            return echt(liste, lauf)

        importer._formulare = kaputt
        try:
            with app.test_request_context():
                try:
                    importer.datei_importieren(io.BytesIO(roh2), trocken=False, quelle="test")
                    raise AssertionError("Der Testfehler kam nicht durch")
                except RuntimeError as exc:
                    assert "Testfehler" in str(exc)
        finally:
            importer._formulare = echt
        assert dateien(tmp) == {name_a, name_b}
        assert zeilen(app, "SELECT id, product_id, file_path FROM mat_product_document ORDER BY id") == vorher
        # Ohne den Fehler geht derselbe Import durch – C kommt genau einmal dazu.
        ber = importieren(roh2, False)
        assert ber["gespeichert"] and ber["dokumente"]["neu"] == 4, ber
        assert dateien(tmp) == {name_a, name_b, name_c}
    print("Importtest bestanden.")


# --- 4. Schritt 18: Altbestand zusammenführen -------------------------------------------------------------------------

class _Log(logging.Handler):
    def __init__(self):
        super().__init__()
        self.zeilen = []

    def emit(self, record):
        self.zeilen.append((record.levelno, record.getMessage()))


def _altbestand(tmp, app, pid):
    """Dateien und Zeilen, wie sie bis Schritt 17 entstanden: Zufallsnamen, Prüfsumme leer, falsch oder richtig."""
    ordner = dok_ordner(tmp)
    os.makedirs(ordner, exist_ok=True)
    namen = [secrets.token_hex(10) + ".pdf" for _ in range(5)]
    for n in namen[:3]:
        with open(os.path.join(ordner, n), "wb") as fh:
            fh.write(PDF_A)
    with open(os.path.join(ordner, namen[3]), "wb") as fh:
        fh.write(PDF_B)
    # namen[4]: Zeile ohne Datei.
    with app.app_context():
        from app import db
        for n, s, g in ((namen[0], "", 0), (namen[1], "f" * 64, 1), (namen[2], sha(PDF_A), len(PDF_A)),
                        (namen[3], sha(PDF_A), len(PDF_B)), (namen[4], "", 0)):
            db.execute("INSERT INTO mat_product_document (product_id, kind, title, file_path, mime, size, sha256, valid_from, "
                       "uploaded_at) VALUES (?, 'gebrauchsanleitung', ?, ?, 'application/pdf', ?, ?, '2024-01-01', 'x')",
                       (pid, "Alt " + n[:4], n, g, s))
        db.execute("INSERT INTO mat_product_document (product_id, kind, title, url, valid_from, uploaded_at) "
                   "VALUES (?, 'datenblatt', 'Link', 'https://hersteller.example/x', '2024-01-01', 'x')", (pid,))
        db.execute("DELETE FROM mat_meta WHERE schluessel = 'dok_inhalt'")     # wie eine Datenbank vor Schritt 18
    return namen


def _meta(tmp, schluessel):
    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
    try:
        r = conn.execute("SELECT wert FROM mat_meta WHERE schluessel = ?", (schluessel,)).fetchone()
        return r[0] if r else None
    finally:
        conn.close()


def test_migration_18():
    """17 → 18 auf einem Datenordner mit Altbestand: drei Kopien eines PDF unter Zufallsnamen (Prüfsumme leer, falsch,
    richtig), ein zweites PDF mit falscher Prüfsumme, eine Zeile ohne Datei. Danach: eine Datei je Inhalt, alle Zeilen
    umgeschrieben (Prüfsumme und Größe aus der Datei), die Zeile ohne Datei unverändert und im Log; zweiter Lauf ohne
    Änderung. Medien beim Start nicht erreichbar: nichts geändert, Kennzeichen bleibt offen, der nächste Start holt es
    nach; Kommandozeile mit --probe und echt."""
    from app.material.services import dokablage
    log = _Log()
    logging.getLogger("app.material.services.dokablage").addHandler(log)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app17 = bis_schritt(17)(make_app, tmp)
            adm = anmelden(app17, "admin@example.org", "geheim123")
            ids = katalog_grund(adm)
            namen = _altbestand(tmp, app17, ids["gurt"])
            assert _meta(tmp, "schema_version") == "17" and _meta(tmp, "dok_inhalt") is None
            assert dateien(tmp) == set(namen[:4])
            name_a, name_b = sha(PDF_A) + ".pdf", sha(PDF_B) + ".pdf"

            app = make_app(tmp)
            assert _meta(tmp, "schema_version") == endversion() and _meta(tmp, "dok_inhalt") == "1"
            assert dateien(tmp) == {name_a, name_b}
            docs = zeilen(app, "SELECT title, file_path, sha256, size, url FROM mat_product_document ORDER BY id")
            assert [(d["file_path"], d["sha256"], d["size"]) for d in docs[:3]] == [(name_a, sha(PDF_A), len(PDF_A))] * 3, docs
            assert (docs[3]["file_path"], docs[3]["sha256"], docs[3]["size"]) == (name_b, sha(PDF_B), len(PDF_B)), docs
            assert (docs[4]["file_path"], docs[4]["sha256"], docs[4]["size"]) == (namen[4], "", 0), docs
            assert docs[5]["url"] and docs[5]["file_path"] is None
            warnungen = [m for lvl, m in log.zeilen if lvl >= logging.WARNING]
            assert any(namen[4] in m and "fehlt" in m for m in warnungen), log.zeilen
            assert any("Schritt 18" in m and "4 Dateien → 2" in m for lvl, m in log.zeilen if lvl == logging.INFO), log.zeilen
            index = zeilen(app, "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_mat_document_file'")
            assert index, "Index aus Schritt 18 fehlt"
            # Zweiter Lauf: nichts zu tun – weder beim Start noch von Hand.
            log.zeilen.clear()
            make_app(tmp)
            assert dateien(tmp) == {name_a, name_b} and not log.zeilen, log.zeilen
            assert zeilen(app, "SELECT title, file_path, sha256, size, url FROM mat_product_document ORDER BY id") == docs
            conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
            try:
                b = dokablage.zusammenfuehren(conn, dok_ordner(tmp))
                assert (b["umbenannt"], b["zusammengefuehrt"], b["berichtigt"], b["umgeschrieben"]) == (0, 0, 0, 0), b
                assert [f["name"] for f in b["fehlend"]] == [namen[4]] and b["dateien_vorher"] == b["dateien_nachher"] == 2
                b = dokablage.zusammenfuehren(conn, dok_ordner(tmp), nur_wenn_offen=True)
                assert b["erledigt"]
            finally:
                conn.close()
            # Die neuen Dateien werden ausgeliefert und mit derselben Prüfsumme exportiert.
            kp = anmelden(app, "admin@example.org", "geheim123")
            assert kp.get(f"/media/material/dok/{name_a}").status_code == 200
            r = kp.get("/api/material/katalog/export")
            with zipfile.ZipFile(io.BytesIO(r.get_data())) as z:
                assert f"dateien/dokumente/{name_a}" in z.namelist() and f"dateien/dokumente/{name_b}" in z.namelist()
            print("Migration 17 → 18 bestanden.")

        # Medien beim Start nicht erreichbar: nichts Destruktives, Kennzeichen bleibt „0“, Warnung; später nachgeholt.
        with tempfile.TemporaryDirectory() as tmp:
            app17 = bis_schritt(17)(make_app, tmp)
            adm = anmelden(app17, "admin@example.org", "geheim123")
            ids = katalog_grund(adm)
            namen = _altbestand(tmp, app17, ids["gurt"])
            beiseite = os.path.join(tmp, "dok-beiseite")
            os.rename(dok_ordner(tmp), beiseite)
            log.zeilen.clear()
            app = make_app(tmp)
            assert _meta(tmp, "schema_version") == endversion() and _meta(tmp, "dok_inhalt") == "0"
            assert any("nicht erreichbar" in m for lvl, m in log.zeilen if lvl == logging.WARNING), log.zeilen
            assert not os.path.exists(dok_ordner(tmp))
            docs = zeilen(app, "SELECT file_path FROM mat_product_document WHERE file_path IS NOT NULL ORDER BY id")
            assert [d["file_path"] for d in docs] == namen
            # Kommandozeile ohne Medien: Bericht und Exit 2, nichts angelegt.
            r = app.test_cli_runner().invoke(args=["material", "dok-zusammenfuehren", "--probe"])
            assert r.exit_code == 2 and "nicht erreichbar" in r.output, r.output
            assert not os.path.exists(dok_ordner(tmp))
            os.rename(beiseite, dok_ordner(tmp))
            # --probe: rechnet, ändert nichts.
            r = app.test_cli_runner().invoke(args=["material", "dok-zusammenfuehren", "--probe"])
            assert r.exit_code == 1 and "Probelauf" in r.output and "Dateien vorher: 4" in r.output, r.output
            assert "Dateien nachher: 2" in r.output and "Umbenannt: 2, Dubletten zusammengeführt: 2" in r.output, r.output
            assert "ACHTUNG Datei fehlt: " + namen[4] in r.output, r.output
            assert dateien(tmp) == set(namen[:4]) and _meta(tmp, "dok_inhalt") == "0"
            # Echt: zusammengeführt, Kennzeichen gesetzt; der nächste Start tut nichts mehr.
            r = app.test_cli_runner().invoke(args=["material", "dok-zusammenfuehren"])
            assert r.exit_code == 1 and "Zusammengeführt." in r.output and "Zeilen umgeschrieben: 4" in r.output, r.output
            assert dateien(tmp) == {sha(PDF_A) + ".pdf", sha(PDF_B) + ".pdf"} and _meta(tmp, "dok_inhalt") == "1"
            log.zeilen.clear()
            make_app(tmp)
            assert not log.zeilen, log.zeilen
            print("Migration 18 ohne erreichbare Medien bestanden.")

        if KOPIE_STAND_7:
            with tempfile.TemporaryDirectory() as tmp:
                shutil.copyfile(KOPIE_STAND_7, os.path.join(tmp, "stroemis.db"))
                log.zeilen.clear()
                make_app(tmp)
                assert _meta(tmp, "schema_version") == endversion()
                mit_datei = zeilen(make_app(tmp), "SELECT COUNT(*) AS n FROM mat_product_document WHERE file_path IS NOT NULL")
                # Die Kopie bringt keine Medien mit: Mit Dokumentdateien bleibt das Kennzeichen offen (Warnung), ohne ist
                # es gesetzt.
                assert _meta(tmp, "dok_inhalt") == ("0" if mit_datei[0]["n"] else "1"), (mit_datei, log.zeilen)
            print("Migration 7 → 18 aus der Kopie bestanden.")
        else:
            print("Migration 7 → 18 übersprungen (MATERIAL_KOPIE_STAND_7 nicht gesetzt).")
    finally:
        logging.getLogger("app.material.services.dokablage").removeHandler(log)
    print("Migration 18 bestanden.")


# --- 5. Wettlauf Löschen gegen Ablegen (Befund 1 der Prüfung vom 22.10.2026) ------------------------------------------

def _import_zip(name_y, inhalt):
    daten = {"format": "stroemis-material-katalog", "version": 2,
             "kategorien": [{"uid": "b" * 32, "name": "Importkategorie", "materialart": "metall_hardware",
                             "intervall_monate": 12}],
             "produkte": [{"uid": f"{n:032x}", "kategorie": ["Importkategorie"], "hersteller": "Importwerk",
                           "modell": f"Modell {n}", "artikelnummer": f"IW-{n}", "materialart": "metall_hardware",
                           "intervall_monate": 12,
                           "dokumente": [{"art": "gebrauchsanleitung", "titel": "Anleitung",
                                          "datei": f"dateien/dokumente/{name_y}"}]} for n in (1, 2)]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("katalog.json", json.dumps(daten))
        z.writestr(f"dateien/dokumente/{name_y}", inhalt)
    return buf.getvalue()


def test_wettlauf_loeschen_ablegen():
    """Produkt Gurt hat Datei F. Während jemand denselben Inhalt an ein anderes Produkt bringt – Datei geschrieben,
    Zeile noch nicht –, löscht ein anderer Arbeitsprozess das letzte Produkt mit F (_datei_freigeben). Nachher muss
    jede Zeile mit file_path ihre Datei haben. Der „andere Prozess“ ist ein Haken an der Stelle außerhalb der
    Schreibsperre: beim Hochladen nach _datei_schreiben (die Zwischendatei liegt, eingeordnet wird erst in der
    Transaktion), beim Import nach dem Ablegen der Dateien vor dem zweiten Durchgang (dort legt _Lauf.ablegen unter
    der Sperre aus dem Archiv nach). Variante: Fehlt die Datei des Quelldokuments beim Kopieren, 409 und kein neues
    Produkt (_datei_sichern) – vorher wäre eine Zeile ohne Datei entstanden."""
    from app.material.services import importer, katalog
    pdf_x, pdf_y = PDF + b"%wettlauf-x", PDF + b"%wettlauf-y"
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        kp = k["katalog"]
        ids = katalog_grund(k["adm"])
        name_x = sha(pdf_x) + ".pdf"
        dokument_anlegen(kp, ids["gurt"], pdf_x)
        echt = katalog._datei_schreiben
        zustand = {"n": 0}

        def haken(file_storage):
            out = echt(file_storage)
            zustand["n"] += 1
            if zustand["n"] == 1:
                katalog.produkt_loeschen(ids["gurt"])          # „gleichzeitig“: der andere Arbeitsprozess
                assert not os.path.isfile(os.path.join(dok_ordner(tmp), name_x)), "Freigeben hat F nicht entfernt"
            return out

        katalog._datei_schreiben = haken
        try:
            did, _ = dokument_anlegen(kp, ids["hms"], pdf_x)
        finally:
            katalog._datei_schreiben = echt
        z = zeilen(app, "SELECT id FROM mat_product_document WHERE file_path = ?", (name_x,))
        assert [r["id"] for r in z] == [did] and dateien(tmp) == {name_x}, (z, dateien(tmp))
        assert kp.get(f"/media/material/dok/{name_x}").status_code == 200
        print("Wettlauf Hochladen gegen Löschen bestanden.")

        # Import: Inhalt Y liegt schon (Produkt HMS); die Lieferung nennt ihn für zwei Produkte. Nach dem Ablegen
        # (zweiter Aufruf – eine Ablage je Fundstelle) löscht jemand HMS, die Datei ist weg; der zweite Durchgang
        # legt sie nach.
        name_y = sha(pdf_y) + ".pdf"
        dokument_anlegen(kp, ids["hms"], pdf_y)
        echt = importer._ablegen
        zustand = {"n": 0}

        def haken_import(archiv, eintrag):
            out = echt(archiv, eintrag)
            zustand["n"] += 1
            if zustand["n"] == 2:
                katalog.produkt_loeschen(ids["hms"])
                assert not os.path.isfile(os.path.join(dok_ordner(tmp), name_y))
            return out

        importer._ablegen = haken_import
        try:
            r = hoch(kp, "/api/material/katalog/import", _import_zip(name_y, pdf_y), "katalog.zip", trocken="0")
        finally:
            importer._ablegen = echt
        b = r.json["bericht"]
        assert r.status_code == 200 and b["gespeichert"] and not b["fehler"], b
        assert b["dokumente"] == {"neu": 2, "neue_version": 0, "unveraendert": 0}, b
        z = zeilen(app, "SELECT id FROM mat_product_document WHERE file_path = ?", (name_y,))
        # Mit HMS ging auch sein Dokument X (das letzte mit dieser Datei) – richtig so; Y hat der Import nachgelegt.
        assert len(z) == 2 and zustand["n"] == 3 and dateien(tmp) == {name_y}, (z, zustand, dateien(tmp))
        print("Wettlauf Import gegen Löschen bestanden.")

        # Variante: Produkt IW-1 hat die Zeile mit Y; die Datei ist weg (wie nach einem Freigeben zwischen dem Lesen
        # der Dokumente und der Transaktion, oder ein Altbestand ohne Datei) → 409, kein neues Produkt.
        iw1 = zeilen(app, "SELECT id FROM mat_product WHERE article_no = 'IW-1'")[0]["id"]
        dok = zeilen(app, "SELECT id FROM mat_product_document WHERE product_id = ?", (iw1,))[0]["id"]
        os.rename(os.path.join(dok_ordner(tmp), name_y), os.path.join(tmp, "beiseite.pdf"))
        r = kp.post(f"/api/material/produkte/{iw1}/variante", json={
            "category_id": ids["karabiner"], "manufacturer": "Importwerk", "model": "Modell 1", "article_no": "IW-1V",
            "material_kind": "metall_hardware", "interval_months": 12, "dokumente": [dok]}, headers=H)
        assert r.status_code == 409 and "liegt nicht mehr" in r.json["error"], r.get_json()
        assert not zeilen(app, "SELECT id FROM mat_product WHERE article_no = 'IW-1V'")
        os.rename(os.path.join(tmp, "beiseite.pdf"), os.path.join(dok_ordner(tmp), name_y))
        r = kp.post(f"/api/material/produkte/{iw1}/variante", json={
            "category_id": ids["karabiner"], "manufacturer": "Importwerk", "model": "Modell 1", "article_no": "IW-1V",
            "material_kind": "metall_hardware", "interval_months": 12, "dokumente": [dok]}, headers=H)
        assert r.status_code == 201, r.get_json()
        assert len(zeilen(app, "SELECT id FROM mat_product_document WHERE file_path = ?", (name_y,))) == 3
        # Am Ende: jede Zeile mit Datei hat ihre Datei, keine Zwischendatei.
        for d in zeilen(app, "SELECT file_path FROM mat_product_document WHERE file_path IS NOT NULL"):
            assert os.path.isfile(os.path.join(dok_ordner(tmp), d["file_path"])), d
        assert dateien(tmp) == {name_y}
    print("Wettlauf-Test bestanden.")


# --- 6. Aufräumen: Dateien ohne Zeile, alte Zwischendateien (Befunde 2 und 3) -------------------------------------------

def _alt_machen(pfad, tage):
    alt = os.path.getmtime(pfad) - tage * 86400
    os.utime(pfad, (alt, alt))


def test_aufraeumen():
    """Nach der Zusammenführung bricht der Prozess zwischen Commit und Entfernen der alten Namen ab (nachgestellt:
    die alten Namen liegen wieder als Dubletten da). Dazu eine fremde Datei ohne Zeile, eine alte und eine junge
    Zwischendatei vom Hochladen und ein alter Kopierrest. Der nächste Start (Kennzeichen schon „1“) entfernt die
    Dubletten und die alten Zwischendateien, lässt die fremde Datei und die junge Zwischendatei liegen und sagt es im
    Log; die Kommandozeile zählt es im Bericht (--probe rechnet nur). Der Kopier-Rückfall in _verweisen lässt keine
    Zwischendatei zurück."""
    from app.material.services import dokablage
    log = _Log()
    logging.getLogger("app.material.services.dokablage").addHandler(log)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            app17 = bis_schritt(17)(make_app, tmp)
            adm = anmelden(app17, "admin@example.org", "geheim123")
            ids = katalog_grund(adm)
            namen = _altbestand(tmp, app17, ids["gurt"])
            ordner = dok_ordner(tmp)
            app = make_app(tmp)
            name_a, name_b = sha(PDF_A) + ".pdf", sha(PDF_B) + ".pdf"
            assert _meta(tmp, "dok_inhalt") == "1" and dateien(tmp) == {name_a, name_b}
            # Abbruch nach dem Commit: die alten Namen liegen noch (harte Verweise wie vor dem Entfernen).
            for n in namen[:3]:
                os.link(os.path.join(ordner, name_a), os.path.join(ordner, n))
            os.link(os.path.join(ordner, name_b), os.path.join(ordner, namen[3]))
            fremd = os.path.join(ordner, "fremd.pdf")              # kein Inhalt einer Zeile – bleibt
            with open(fremd, "wb") as fh:
                fh.write(PDF_C)
            reste = {".neu-" + "a" * 20 + ".pdf": 2, "." + name_a + ".teil": 3, ".neu-" + "b" * 20 + ".pdf": 0}
            for n, tage in reste.items():
                with open(os.path.join(ordner, n), "wb") as fh:
                    fh.write(b"%PDF-rest")
                _alt_machen(os.path.join(ordner, n), tage)
            log.zeilen.clear()
            make_app(tmp)
            rest = sorted(os.listdir(ordner))
            assert rest == sorted([".neu-" + "b" * 20 + ".pdf", name_a, name_b, "fremd.pdf"]), rest
            info = [m for lvl, m in log.zeilen if lvl == logging.INFO]
            warn = [m for lvl, m in log.zeilen if lvl == logging.WARNING]
            assert any("4 Dateien ohne Zeile entfernt" in m and "2 Zwischendateien" in m for m in info), log.zeilen
            assert any("1 Dateien ohne Zeile" in m and "bleiben liegen" in m for m in warn), log.zeilen
            assert not any("Schritt 18" in m for m in info), "die Zusammenführung selbst darf nicht noch einmal laufen"
            # Noch ein Start: nichts mehr zu melden außer der fremden Datei.
            log.zeilen.clear()
            make_app(tmp)
            assert [lvl for lvl, m in log.zeilen] == [logging.WARNING] and "1 Dateien ohne Zeile" in log.zeilen[0][1]
            # Kommandozeile: dieselbe Lage noch einmal hergestellt, --probe zählt, echt räumt.
            os.link(os.path.join(ordner, name_a), os.path.join(ordner, namen[0]))
            with open(os.path.join(ordner, ".neu-" + "c" * 20 + ".pdf"), "wb") as fh:
                fh.write(b"%PDF-rest")
            _alt_machen(os.path.join(ordner, ".neu-" + "c" * 20 + ".pdf"), 2)
            r = app.test_cli_runner().invoke(args=["material", "dok-zusammenfuehren", "--probe"])
            assert r.exit_code == 1 and "Dateien vorher: 4 (" in r.output, r.output   # Zwischendateien zählen nicht
            assert "Dateien ohne Zeile: 1 (0.0 MB) – bleiben liegen; zu entfernen, weil der Inhalt unter seinem " \
                   "Inhaltsnamen liegt: 1" in r.output and "Zwischendateien älter als ein Tag zu entfernen: 1" in r.output, r.output
            assert "Dateien nachher: 3 (" in r.output, r.output
            assert os.path.isfile(os.path.join(ordner, namen[0]))
            r = app.test_cli_runner().invoke(args=["material", "dok-zusammenfuehren"])
            assert r.exit_code == 1 and "entfernt, weil der Inhalt unter seinem Inhaltsnamen liegt: 1" in r.output, r.output
            assert "Zwischendateien älter als ein Tag entfernt: 1" in r.output and "Dateien nachher: 3 (" in r.output, r.output
            assert sorted(os.listdir(ordner)) == sorted([".neu-" + "b" * 20 + ".pdf", name_a, name_b, "fremd.pdf"])
            # Kopier-Rückfall ohne harte Verweise: Zwischendatei mit Punkt davor, nachher weg.
            echt = os.link

            def kein_link(*a, **kw):
                raise OSError("keine harten Verweise (Probe)")

            os.link = kein_link
            try:
                dokablage._verweisen(os.path.join(ordner, name_a), os.path.join(ordner, "kopie.pdf"))
            finally:
                os.link = echt
            with open(os.path.join(ordner, "kopie.pdf"), "rb") as fh:
                assert fh.read() == PDF_A
            assert not [n for n in os.listdir(ordner) if n.endswith(".teil")]
            os.remove(os.path.join(ordner, "kopie.pdf"))
    finally:
        logging.getLogger("app.material.services.dokablage").removeHandler(log)
    print("Aufräumen-Test bestanden.")


if __name__ == "__main__":
    test_gemeinsame_datei()
    test_version_und_protokoll()
    test_import()
    test_migration_18()
    test_wettlauf_loeschen_ablegen()
    test_aufraeumen()
    print("Alle Dokumenttests bestanden.")
