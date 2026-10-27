"""Prüfsumme und Kennung für den Lebenslauf (Schritt 31, Wunsch vom 27.10.2026):  python tests/test_material_lebenslauf_summe.py
oder pytest

Jeder Abruf eines Lebenslaufs bekommt eine Kennung L-<jahr>-<nr> (fortlaufend je Jahr) und einen Prüfsummen-Stempel wie
ein Protokoll; mat_lebenslauf verzeichnet Kennung, Inventarnummer, Stand und Prüfsummen – kein Konto, keinen Inhalt,
keine Datei. Die Prüfseite erkennt ihn (unverändert, Stempel fehlt, angehängt, Inhalt verändert, fremde Datei, Kennung
mit falscher Summe) ohne Inventarnummer und ohne Personendaten. Trigger-Matrix wie Schritt 30, Migration frisch / 30 → 31
mit Altbestand / zweiter Lauf. Kein Hinweis „nicht festgeschrieben“ mehr (Nachtrag des Nutzers vom 27.10.2026). Alles
Platzhalter."""
import hashlib
import io
import os
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _flach, _heute, make_app, pdf_seiten  # noqa: E402
from test_material_export import aufbau  # noqa: E402
from test_material_vor_merge import _versuch, _zeilen_je_tabelle  # noqa: E402

KENNUNG = re.compile(r"L-(\d{4})-(\d{6})")


def _abruf(c, iid):
    r = c.get(f"/materialablage/artikel/{iid}/lebenslauf.pdf?stand=1")
    assert r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code
    kennung = KENNUNG.search(r.headers["Content-Disposition"]).group(0)
    return r.data, kennung


def _zeilen(app):
    with app.app_context():
        from app import db
        return [dict(z) for z in db.query("SELECT * FROM mat_lebenslauf ORDER BY id")]


def _pruefen(c, daten, name="lebenslauf.pdf"):
    r = c.post("/api/material/pruefen", data={"datei": (io.BytesIO(daten), name)}, headers=H,
               content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    return r.json


def test_abruf_und_verzeichnis():
    """Ein Abruf – genau eine Zeile mit den Prüfsummen der ausgelieferten Datei; zwei Abrufe – zwei Kennungen. Stempel,
    Kopf und Fuß auf jeder Seite, kein „nicht festgeschrieben“; die ersten N Bytes rechnen nach."""
    from pypdf import PdfReader
    from app.material.services import stempel
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        w, iid, inv = k["wart"], a["lager"]["id"], a["lager"]["inventory_no"]
        # Mehrere Seiten: Ereignisse im Journal.
        for n in range(45):
            assert w.put(f"/api/material/artikel/{iid}", json={"notes": f"Platzhalter-Notiz {n} " + "x" * 60}).status_code == 200
        assert _zeilen(app) == []
        daten, kennung = _abruf(w, iid)
        jahr = str(_heute().year)
        assert kennung == f"L-{jahr}-000001", kennung
        (z,) = _zeilen(app)
        assert set(z) == {"id", "kennung", "inventory_no", "stand", "pdf_sha256", "pdf_hashed_bytes", "file_sha256"}, z
        assert (z["kennung"], z["inventory_no"]) == (kennung, inv)
        assert z["file_sha256"] == hashlib.sha256(daten).hexdigest()
        n = z["pdf_hashed_bytes"]
        assert 0 < n < len(daten) and z["pdf_sha256"] == hashlib.sha256(daten[:n]).hexdigest()
        assert stempel.kennung_lesen(daten) == (kennung, n, z["pdf_sha256"])
        assert f"%Stroemis-Lebenslauf {kennung} N={n}".encode() in daten
        pfad = os.path.join(tmp, "ll.pdf")
        with open(pfad, "wb") as fh:
            fh.write(daten)
        seiten = pdf_seiten(pfad)
        assert len(seiten) >= 2, len(seiten)
        for s in map(_flach, seiten):
            assert f"Lebenslauf {inv} · {kennung} · Stand" in s, s[-500:]
            assert f"Lebenslauf {kennung} · SHA-256 (erste {n} Bytes): {z['pdf_sha256']}" in s.replace("- ", "-"), s[-500:]
            assert f"nachrechnen: head -c {n} datei.pdf | sha256sum" in s and "/materialablage/pruefen" in s, s[-500:]
            assert "nicht festgeschrieben" not in s and "Auszug" not in s, s[-500:]
        text = _flach(" ".join(seiten))
        assert f"Kennung {kennung}" in text and f"Dieser Lebenslauf ({kennung}, Stand" in text, text[:800]
        assert "und die genannten Protokolle lassen sich mit ihrer Prüfsumme prüfen" in text, text[-600:]
        leser = PdfReader(pfad)
        assert kennung in leser.metadata.get("/Keywords", ""), leser.metadata
        xmp = leser.trailer["/Root"]["/Metadata"].get_object().get_data()
        assert b'pdfaid:part="3"' in xmp and b'pdfaid:conformance="B"' in xmp
        # Zweiter Abruf: neue Kennung, neue Zeile, andere Datei (Stand und Kennung im Inhalt). Kein Konto in der Zeile.
        daten2, kennung2 = _abruf(k["fuehrung"], iid)
        assert kennung2 == f"L-{jahr}-000002" and daten2 != daten
        assert [z["kennung"] for z in _zeilen(app)] == [kennung, kennung2]
        # Ohne Zugang zum Modul: kein Lebenslauf, keine Zeile.
        assert k["nutzer"].get(f"/materialablage/artikel/{iid}/lebenslauf.pdf").status_code == 403
        assert len(_zeilen(app)) == 2
    print("Abruf und Verzeichnis bestanden.")


def test_kennung_je_jahr():
    """Fortlaufend je Jahr (deutsche Zeit); ein vergebener, nie verzeichneter Abruf hinterlässt eine Lücke; der Zähler
    folgt der höchsten verzeichneten Nummer, falls er fehlt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        with app.app_context():
            from app import db
            from app.material.services import lebenslauf
            assert lebenslauf.kennung_vergeben("2027-06-01T10:00:00+00:00") == "L-2027-000001"
            # 31.12. 23:30 UTC ist in Deutschland schon der 1.1.
            assert lebenslauf.kennung_vergeben("2027-12-31T23:30:00+00:00") == "L-2028-000001"
            assert lebenslauf.kennung_vergeben("2027-03-01T10:00:00+00:00") == "L-2027-000002"
        jahr = _heute().year
        _, k1 = _abruf(k["wart"], a["lager"]["id"])
        with app.app_context():
            assert lebenslauf.kennung_vergeben(db.now()) == f"L-{jahr}-000002"        # reserviert, nie verzeichnet
        _, k3 = _abruf(k["wart"], a["lager"]["id"])
        assert (k1, k3) == (f"L-{jahr}-000001", f"L-{jahr}-000003")
        with app.app_context():
            db.execute("DELETE FROM mat_meta WHERE schluessel = ?", (f"lebenslauf_zaehler_{jahr}",))
        _, k4 = _abruf(k["wart"], a["lager"]["id"])
        assert k4 == f"L-{jahr}-000004", k4
        with app.app_context():
            from app.material.services import pdf
            zeilen = lebenslauf.stempel_zeilen("L-2026-000001", 99_999_999, "0" * 64)
            assert all(len(z) + len("dev.") <= pdf.STEMPEL_ZEICHEN for z in zeilen), [len(z) for z in zeilen]
    print("Kennung je Jahr bestanden.")


def test_pruefseite():
    """Unverändert, Stempel fehlt, angehängt, Inhalt verändert, fremde Datei, Kennung mit falscher Summe – ohne
    Inventarnummer; den Link zum Artikel bekommt nur, wer ihn sehen darf."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        w, inv = k["wart"], a["lager"]["inventory_no"]
        daten, kennung = _abruf(w, a["lager"]["id"])
        (z,) = _zeilen(app)
        n = z["pdf_hashed_bytes"]
        anon = app.test_client()
        r = _pruefen(anon, daten)
        assert set(r) == {"ergebnis", "protokoll_id", "art", "hinweis", "stand"}, r
        assert (r["ergebnis"], r["protokoll_id"], r["art"]) == ("unveraendert", kennung, "Lebenslauf"), r
        assert re.fullmatch(r"\d\d\.\d\d\.\d{4}, \d\d:\d\d Uhr", r["stand"]) and "Byte für Byte der Lebenslauf" in r["hinweis"]
        assert inv not in str(r) and "Auszug" not in str(r) and "festgeschrieben" not in str(r)
        # Angemeldet mit Leserecht: Link zum Artikel; ohne Zugang zum Modul keiner.
        r = _pruefen(w, daten)
        assert r["link"] == f"/materialablage/artikel/{a['lager']['id']}", r
        assert "link" not in _pruefen(k["nutzer"], daten)
        # Stempel fehlt (nur die ersten N Bytes).
        r = _pruefen(anon, daten[:n])
        assert (r["ergebnis"], r["protokoll_id"]) == ("veraendert", kennung) and "Stempel fehlt" in r["hinweis"], r
        # Angehängt: der Lebenslauf selbst unverändert, danach etwas dazu.
        r = _pruefen(anon, daten + b"\n% angehaengt\n%%EOF\n")
        assert (r["ergebnis"], r["protokoll_id"]) == ("veraendert", kennung), r
        assert f"Die ersten {n} Bytes (der Lebenslauf selbst) sind unverändert" in r["hinweis"], r
        # Inhalt verändert: ein Byte innerhalb der ersten N Bytes.
        i = n // 2
        r = _pruefen(anon, daten[:i] + bytes([daten[i] ^ 1]) + daten[i + 1:])
        assert (r["ergebnis"], r["protokoll_id"]) == ("veraendert", kennung), r
        assert r["hinweis"] == "Der Inhalt des Lebenslaufs wurde verändert – die Prüfsumme stimmt nicht mehr.", r
        # Fremde Datei.
        r = _pruefen(anon, b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
        assert r["ergebnis"] == "unbekannt" and r["protokoll_id"] is None and "kein Lebenslauf" in r["hinweis"], r
        # Kennung mit falscher Summe bzw. falscher Länge, erfundene Kennung: verrät nichts.
        for kommentar in (f"%Stroemis-Lebenslauf {kennung} N={n} SHA-256={'0' * 64}",
                          f"%Stroemis-Lebenslauf {kennung} N={n + 1} SHA-256={z['pdf_sha256']}",
                          f"%Stroemis-Protokoll {kennung} N={n} SHA-256={'1' * 64}",
                          f"%Stroemis-Lebenslauf L-{_heute().year}-000999 N={n} SHA-256={z['pdf_sha256']}"):
            r = _pruefen(anon, b"%PDF-1.4\n% Platzhalter\n%%EOF\n" + kommentar.encode() + b"\n%%EOF\n")
            assert r["ergebnis"] == "unbekannt" and r["protokoll_id"] is None and "L-" not in str(r), (kommentar, r)
        # Ein Lebenslauf eines später gelöschten Artikels (ohne Prüfung) bleibt erkennbar – ohne Link.
        neu, kennung_neu = _abruf(w, a["textil"]["id"])
        assert w.delete(f"/api/material/artikel/{a['textil']['id']}", headers=H).status_code == 200
        r = _pruefen(w, neu)
        assert (r["ergebnis"], r["protokoll_id"]) == ("unveraendert", kennung_neu) and "link" not in r, r
        # Protokolle unverändert erkannt (Gegenprobe).
        with app.app_context():
            from app import db
            from app.material.services import protokoll
            p = db.query("SELECT protocol_id, pdf_path FROM mat_inspection WHERE id = ?", (o["pid"],), one=True)
            with open(protokoll.voller_pfad(p["pdf_path"]), "rb") as fh:
                pdf = fh.read()
        r = _pruefen(anon, pdf)
        assert (r["ergebnis"], r["protokoll_id"], r["art"]) == ("unveraendert", p["protocol_id"], "Prüfprotokoll"), r
        assert "stand" not in r and r["hinweis"] == "Die Datei ist Byte für Byte das festgeschriebene Protokoll."
    print("Prüfseite bestanden.")


def test_trigger():
    """Unveränderlich auch gegen SQL von Hand: kein UPDATE (auch über rowid), kein DELETE, kein INSERT OR REPLACE bzw.
    UPSERT über Kennung oder Zeile – mit und ohne recursive_triggers/Fremdschlüssel. Neue Zeilen gehen."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, o, a = aufbau(tmp)
        _abruf(k["wart"], a["lager"]["id"])
        _abruf(k["wart"], a["formel"]["id"])
        pfad = os.path.join(tmp, "stroemis.db")
        spalten = "kennung, inventory_no, stand, pdf_sha256, pdf_hashed_bytes, file_sha256"
        verboten = [
            "UPDATE mat_lebenslauf SET kennung = 'L-2026-999999' WHERE id = 1",
            "UPDATE mat_lebenslauf SET id = 900000 WHERE id = 1",
            "UPDATE mat_lebenslauf SET rowid = rowid + 900000",
            "UPDATE mat_lebenslauf SET stand = '2020-01-01T00:00:00+00:00'",
            "UPDATE mat_lebenslauf SET file_sha256 = pdf_sha256",
            "UPDATE mat_lebenslauf SET inventory_no = 'M-999999'",
            "DELETE FROM mat_lebenslauf",
            "DELETE FROM mat_lebenslauf WHERE id = 2",
            f"INSERT OR REPLACE INTO mat_lebenslauf ({spalten}) SELECT kennung, 'M-999999', stand, pdf_sha256, "
            "pdf_hashed_bytes, file_sha256 FROM mat_lebenslauf WHERE id = 1",
            f"REPLACE INTO mat_lebenslauf (id, {spalten}) SELECT id, 'L-2026-888888', 'M-999999', stand, pdf_sha256, "
            "pdf_hashed_bytes, file_sha256 FROM mat_lebenslauf WHERE id = 1",
            f"INSERT INTO mat_lebenslauf ({spalten}) SELECT kennung, inventory_no, '2020-01-01', pdf_sha256, "
            "pdf_hashed_bytes, file_sha256 FROM mat_lebenslauf WHERE id = 1 ON CONFLICT(kennung) DO UPDATE SET stand = "
            "excluded.stand",
            f"INSERT INTO mat_lebenslauf ({spalten}) VALUES ('P-2026-000001', 'M-1', '2026', 'a', 1, 'b')",
        ]
        for fk, rek in ((True, True), (False, False), (True, False), (False, True)):
            for sql in verboten:
                fehler = _versuch(pfad, sql, fk=fk, rekursiv=rek)
                assert fehler and fehler != "nichts geändert", (fk, rek, sql, fehler)
        assert _versuch(pfad, f"INSERT INTO mat_lebenslauf ({spalten}) VALUES ('L-2026-777777', 'M-1', '2026', 'a', 1, "
                              "'b')") is None
    print("Trigger bestanden.")


def test_migration():
    """Frisch und 30 → 31 (mit Altbestand: abgeschlossener Durchgang, Set-Protokolle, Journal) ergeben dasselbe Schema;
    Schritt 31 ändert keine Zeile; ein zweiter Lauf ändert nichts; danach geht der Abruf."""
    from test_material_set_rueckbau import _schema, _unterschied
    from test_material_setprotokolle import _haupt
    from test_material_trennung import bis_schritt, endversion, zeilen
    from app.material import models
    with tempfile.TemporaryDirectory() as frisch:
        make_app(frisch)
        schema_frisch = _schema(os.path.join(frisch, "stroemis.db"))
    assert ("table", "mat_lebenslauf") in schema_frisch and ("trigger", "mat_lebenslauf_aendern") in schema_frisch
    with tempfile.TemporaryDirectory() as tmp:
        t = bis_schritt(30)(_haupt, tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        assert conn.execute("SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'").fetchone()[0] == "30"
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'mat_lebenslauf'").fetchone()
        conn.close()
        vorher = _zeilen_je_tabelle(pfad)
        assert vorher["mat_round_setprotokoll"] and vorher["mat_audit"] and vorher["mat_inspection"]
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion() == "31"
        schema = _schema(pfad)
        assert schema == schema_frisch, _unterschied(schema, schema_frisch)
        nachher = _zeilen_je_tabelle(pfad)
        assert nachher.pop("mat_lebenslauf") == [] and nachher == vorher
        conn = sqlite3.connect(pfad)
        n = conn.total_changes
        for sql in models.SCHRITT_31:
            conn.execute(sql)
        assert conn.total_changes == n
        conn.close()
        make_app(tmp)                                        # zweiter Start: nichts ändert sich
        assert _schema(pfad) == schema_frisch
        _, kennung = _abruf(t.w, t.a1["id"])
        assert kennung.endswith("-000001")
    print("Schritt 31 (Migration) bestanden.")


if __name__ == "__main__":
    test_abruf_und_verzeichnis()
    test_kennung_je_jahr()
    test_pruefseite()
    test_trigger()
    test_migration()
