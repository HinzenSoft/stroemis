"""Die Funktion „kritisch“ der Prüfpunkte ist entfernt (Entscheidung des Nutzers vom 03.11.2026, „Funktion ganz
entfernen“):  python tests/test_material_ohne_kritisch.py  oder  pytest tests/test_material_ohne_kritisch.py

  - Formular-Editor: kein Häkchen und keine Marke „kritisch“, kein Satz „Ein kritischer Punkt mit Mangel …“; die
    Schnittstelle liefert Punkte ohne „kritisch“ und übergeht das Feld beim Speichern (auch an Text-Punkten und mit
    unbrauchbarem Wert – früher Fehler).
  - Prüfung: Mangel an einem Punkt, dessen Ergebniszeile noch is_critical = 1 trägt (wie aus einem Entwurf vor dem
    Umbau; am Formularpunkt gibt es die Spalte seit Schritt 37 nicht mehr) – „einsatzbereit“ ist nicht gesperrt und lässt sich über die Schnittstelle
    festschreiben; Befunde ohne „kritisch“; Prüfprotokoll (HTML und PDF-Text) und Lebenslauf ohne „kritisch“; das
    gespeicherte Protokoll bleibt beim Lesen von Prüfung, Lebenslauf und Jahresbericht Byte für Byte, wie es war.
  - Jahresbericht (Schnittstelle, PDF) und CSV-Prüfungsliste ohne „mit kritischem Mangel“ bzw. „kritischer Mangel“.
  - Katalog: Import einer Datei mit „kritisch“ geht ohne Fehler, der Wert wird nicht gespeichert (die Spalte
    is_critical gibt es seit Schritt 37 nicht mehr); ein erneuter Import derselben Datei legt keine neue Version an; der
    Export schreibt „kritisch“ nicht mehr.
  - Oberfläche statisch: Prüfung, Befunde, Jahresbericht und CSS ohne Marke, Spalte und „i“ „kritisch“; das
    Anleitungsthema „kritisch“ ist entfallen.
Alle Namen, Nummern und Prüfpunkte hier sind Platzhalter."""
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _flach, _heute, festschreiben, gliederung, jpeg, katalog_grund, make_app,  # noqa: E402
                           neuer_artikel, pdf_seiten, protokoll_zeile, pruef_formulare, punkte_von, starten, umgebung)
from test_material_export import csv_lesen  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "/api/material"


def lies(rel):
    with open(os.path.join(WURZEL, rel), encoding="utf-8") as fh:
        return fh.read()


def sql(app, befehl, args=()):
    with app.app_context():
        from app import db
        if befehl.lstrip().upper().startswith("SELECT"):
            return db.query(befehl, args)
        db.execute(befehl, args)                    # schreibt sofort (ohne umschließende Transaktion)


def test_formular_editor():
    """Formular-Editor und Schnittstelle der Formulare ohne „kritisch“."""
    js = lies("app/material/static/material.js")
    for alt in ("fp-kritisch", "> kritisch</label>", "p.kritisch", "kritisch: false", "Ein kritischer Punkt mit Mangel",
                '<strong class="mat-warn">kritisch</strong>'):
        assert alt not in js, alt
    assert 'pflicht: true });' in js                                   # neue Punkte ohne „kritisch“
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        kp = k["katalog"]
        r = kp.post(f"{API}/formulare", json={"kategorie_id": ids["gurte"], "titel": "Platzhalter-Formular", "punkte": [
            {"text": "Platzhalter Ja/Nein", "art": "yesno", "soll": "nein", "kritisch": True},
            {"text": "Platzhalter Text", "art": "text", "kritisch": True},
            {"text": "Platzhalter Zahl", "art": "number", "kritisch": "vielleicht"}]})
        assert r.status_code == 201, r.get_json()
        f = r.json["formular"]
        assert [p["text"] for p in f["punkte"]] == ["Platzhalter Ja/Nein", "Platzhalter Text", "Platzhalter Zahl"]
        assert all("kritisch" not in p for p in f["punkte"]), f["punkte"]
        assert sql(app, "SELECT COUNT(*) AS n FROM mat_checklist_item WHERE form_id = ?", (f["id"],))[0]["n"] == 3
        assert "is_critical" not in {s["name"] for s in sql(app, "SELECT name FROM pragma_table_info('mat_checklist_item')")}
        # Speichern (unbenutztes Formular) übergeht das Feld ebenso; das Journal nennt es nicht.
        r = kp.put(f"{API}/formulare/{f['id']}", json={"punkte": [
            {"text": "Platzhalter Ja/Nein", "art": "yesno", "soll": "ja", "kritisch": True}]})
        assert r.status_code == 200, r.get_json()
        assert all("kritisch" not in p for p in kp.get(f"{API}/formulare/{f['id']}").json["formular"]["punkte"])
        journal = sql(app, "SELECT before_json, after_json FROM mat_audit WHERE entity = 'form' AND entity_id = ?", (f["id"],))
        assert journal and not any("kritisch" in ((j["before_json"] or "") + (j["after_json"] or "")) for j in journal), journal
    print("Formular-Editor ohne „kritisch“ bestanden.")


def test_pruefung_einsatzbereit_trotz_alter_markierung():
    """Mangel an einem Punkt, dessen Ergebniszeile is_critical = 1 trägt (alter Entwurf): „einsatzbereit“ ist wählbar
    und wird festgeschrieben;
    weder Befunde noch Protokoll, Lebenslauf oder Jahresbericht nennen „kritisch“; das gespeicherte Protokoll bleibt."""
    from app.material.services import pdf
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 2}-01")
        pr = starten(p1, a["id"]).json["pruefung"]
        pk = punkte_von(pr)
        # Ein Entwurf von vor dem Umbau trüge die Markierung auch in der Ergebniszeile.
        sql(app, "UPDATE mat_inspection_result SET is_critical = 1 WHERE id = ?", (pk["Testpunkt Schnitt"],))
        assert sql(app, "SELECT is_critical FROM mat_inspection_result WHERE id = ?", (pk["Testpunkt Schnitt"],))[0]["is_critical"] == 1
        url = f"{API}/pruefungen/{pr['id']}/punkte"
        r = p1.put(f"{url}/{pk['Testpunkt Schnitt']}", json={"wert": "ja", "notiz": "Platzhalter Schnitt"})
        assert r.status_code == 200 and r.json["punkt"]["befund"] == "mangel" and "kritisch" not in r.json["punkt"]
        r = p1.post(f"{url}/{pk['Testpunkt Schnitt']}/foto", data={"file": (jpeg(), "m.jpg")}, headers=H,
                    content_type="multipart/form-data")
        assert r.status_code == 200, r.get_json()
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "3"}).status_code == 200
        d = p1.get(f"{API}/pruefungen/{pr['id']}").json["pruefung"]
        assert d["einsatzbereit_gesperrt"] == [] and all("kritisch" not in x for x in d["punkte"]), d
        gesetzt, original = [], pdf._setzen

        def mitschreiben(html):
            gesetzt.append(html)
            return original(html)

        pdf._setzen = mitschreiben
        try:
            r = festschreiben(p1, pr["id"], ergebnis="einsatzbereit")
        finally:
            pdf._setzen = original
        assert r.status_code == 200 and r.json["pruefung"]["ergebnis"] == "einsatzbereit", r.get_json()
        assert all("kritisch" not in x for x in r.json["pruefung"]["punkte"])
        artikel = w.get(f"{API}/artikel/{a['id']}").json["artikel"]
        assert artikel["lock_state"] == "frei" and artikel["status"] == "einsatzbereit", artikel
        # Protokoll: HTML ohne Spalte, Marke und Legende „kritisch“; PDF-Text ebenso, der Mangel steht da.
        html = [h for h in gesetzt if 'class="liste befunde' in h]
        assert len(html) == 1 and "kritisch" not in html[0].lower(), [h[:200] for h in html]
        zeile = protokoll_zeile(app, pr["id"])
        pfad = os.path.join(tmp, zeile["pdf_path"])
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "kritisch" not in text.lower() and "Platzhalter Schnitt" in text and "1 Mangel" in text, text[:2000]
        with open(pfad, "rb") as fh:
            vorher = fh.read()
        assert hashlib.sha256(vorher).hexdigest() == zeile["file_sha256"]
        # Lesen der Prüfung, des Lebenslaufs und des Jahresberichts rendert das Protokoll nicht neu.
        assert p1.get(f"{API}/pruefungen/{pr['id']}").status_code == 200
        r = w.get(f"/materialablage/artikel/{a['id']}/lebenslauf.pdf")
        assert r.status_code == 200 and r.data.startswith(b"%PDF"), r.status_code
        ll = os.path.join(tmp, "lebenslauf.pdf")
        with open(ll, "wb") as fh:
            fh.write(r.data)
        assert "kritisch" not in _flach(" ".join(pdf_seiten(ll))).lower()
        assert w.get(f"{API}/ordner/{gid}/bericht").status_code == 200
        r = w.get(f"/materialablage/pruefung/{pr['id']}/pdf")
        assert r.status_code == 200 and r.data == vorher
        with open(pfad, "rb") as fh:
            assert fh.read() == vorher
        assert protokoll_zeile(app, pr["id"])["file_sha256"] == zeile["file_sha256"]
    print("Prüfung: „einsatzbereit“ trotz alter Markierung bestanden.")


def test_jahresbericht_und_csv():
    """Jahresbericht (Schnittstelle, PDF) und CSV-Prüfungsliste ohne „kritisch“ – auch mit Mangel an einem Punkt, der die
    alte Markierung trägt."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        pruef_formulare(k["katalog"], ids)
        w, p1 = k["wart"], k["pruefer"]
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 2}-01")
        pr = starten(p1, a["id"]).json["pruefung"]
        pk = punkte_von(pr)
        sql(app, "UPDATE mat_inspection_result SET is_critical = 1 WHERE inspection_id = ?", (pr["id"],))
        url = f"{API}/pruefungen/{pr['id']}/punkte"
        assert p1.put(f"{url}/{pk['Testpunkt Schnitt']}", json={"wert": "ja", "notiz": "Platzhalter"}).status_code == 200
        assert p1.post(f"{url}/{pk['Testpunkt Schnitt']}/foto", data={"file": (jpeg(), "m.jpg")}, headers=H,
                       content_type="multipart/form-data").status_code == 200
        assert p1.put(f"{url}/{pk['Testpunkt Messwert']}", json={"wert": "3"}).status_code == 200
        assert festschreiben(p1, pr["id"], ergebnis="instandsetzen").status_code == 200
        jahr = int(protokoll_zeile(app, pr["id"])["inspected_on"][:4])
        r = w.get(f"{API}/ordner/{gid}/bericht", query_string={"jahr": jahr})
        assert r.status_code == 200, r.get_json()
        p = r.json["bericht"]["pruefungen"]
        assert p["gesamt"] == 1 and p["mit_mangel"] == 1 and "kritisch" not in p, p
        r = w.get(f"/materialablage/ordner/{gid}/bericht-{jahr}.pdf")
        assert r.status_code == 200 and r.data.startswith(b"%PDF"), r.status_code
        pfad = os.path.join(tmp, "bericht.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = _flach(" ".join(pdf_seiten(pfad)))
        assert "mit Mangel" in text and "kritisch" not in text.lower(), text[:1500]
        r = w.get(f"/materialablage/export/{gid}-pruefungen-{jahr}.csv")
        assert r.status_code == 200 and r.mimetype == "text/csv", r.status_code
        kopf, zeilen = csv_lesen(r.data)
        assert "Mängel" in kopf and not any("kritisch" in s for s in kopf), kopf
        assert len(zeilen) == 1 and zeilen[0]["Mängel"] == "1", zeilen
        assert "kritisch" not in r.data.decode("utf-8-sig").lower()
    print("Jahresbericht und CSV ohne „kritisch“ bestanden.")


DATEI = {
    "format": "stroemis-material-katalog", "version": 1,
    "kategorien": [{"name": "Platzhalterbaum", "unterkategorien": [
        {"name": "Platzhalter-Gurte", "materialart": "sonstiges", "intervall_monate": 12}]}],
    "produkte": [],
    "formulare": [{"kategorie": ["Platzhalterbaum", "Platzhalter-Gurte"], "titel": "Platzhalter-Formular", "punkte": [
        {"gruppe": "G", "text": "Platzhalter Ja/Nein", "art": "yesno", "soll": "nein", "kritisch": True},
        {"text": "Platzhalter Text", "art": "text", "pflicht": False, "kritisch": True},
        {"text": "Platzhalter Zahl", "art": "number", "pflicht": False, "kritisch": "vielleicht"}]}]}


def test_katalog_import_und_export():
    """Import mit „kritisch“ geht (Wert übergangen – die Spalte gibt es seit Schritt 37 nicht mehr), ein zweiter Lauf
    legt keine neue Version an; der Export schreibt „kritisch“ nicht."""
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        with app.app_context():
            from flask import g

            from app import db
            from app.material.services import importer, katalog_export
            g.mat_akteur = "Test"
            bericht = importer.importieren(DATEI, quelle="Test")
            assert not bericht["fehler"], bericht["fehler"]
            formulare = db.query("SELECT * FROM mat_form")
            assert len(formulare) == 1 and formulare[0]["active"], formulare
            fid = formulare[0]["id"]
            punkte = db.query("SELECT * FROM mat_checklist_item WHERE form_id = ? ORDER BY position", (fid,))
            assert [p["label"] for p in punkte] == ["Platzhalter Ja/Nein", "Platzhalter Text", "Platzhalter Zahl"]
            assert all("is_critical" not in p for p in punkte), punkte
            # Derselbe Import ist unverändert – keine neue Version nur wegen der Marke in der Datei.
            bericht = importer.importieren(DATEI, quelle="Test")
            assert not bericht["fehler"], bericht["fehler"]
            assert [f["id"] for f in db.query("SELECT id FROM mat_form")] == [fid]
            # Ohne „kritisch“ in der Datei ebenso.
            ohne = {**DATEI, "formulare": [{**DATEI["formulare"][0], "punkte": [
                {k: v for k, v in p.items() if k != "kritisch"} for p in DATEI["formulare"][0]["punkte"]]}]}
            assert not importer.importieren(ohne, quelle="Test")["fehler"]
            assert [f["id"] for f in db.query("SELECT id FROM mat_form")] == [fid]
            # Export: Punkte ohne „kritisch“.
            daten, _, _ = katalog_export.sammeln(mit_dateien=False)
            punkte = [p for f in daten["formulare"] for p in f["punkte"]]
            assert len(punkte) == 3 and all("kritisch" not in p for p in punkte), punkte
            assert set(punkte[0]) == {"gruppe", "text", "art", "pflicht", "soll"}, punkte[0]
            # Und zurück: der Export lässt sich wieder importieren, ohne neue Version.
            assert not importer.importieren(daten, quelle="Test")["fehler"]
            assert [f["id"] for f in db.query("SELECT id FROM mat_form")] == [fid]
    print("Katalogimport mit und Export ohne „kritisch“ bestanden.")


def test_oberflaeche_statisch():
    """Prüfung, Befunde, Jahresbericht, CSS, PDF-Vorlagen und Anleitungsthemen ohne „kritisch“."""
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    for alt in ("mat-kritisch", "mat-krit-spalte", "x.kritisch", "h.kritisch", "pr.kritisch", "mit kritischem Mangel",
                'infoKnopf("kritisch"', 'mehrDazu("kritisch")', "kritischer Mangel – nicht einsatzbereit",
                "ein kritischer schließt"):
        assert alt not in js, alt
    assert "mat-kritisch" not in css and "mat-krit-spalte" not in css
    assert "<h2>Befunde</h2>" in js and "Ein Mangel braucht ein Foto und eine Bemerkung." in js
    # Die Sperre von „einsatzbereit“ in der Oberfläche: nur noch das Lebensende (wie auf dem Server).
    assert "einsatzSperre: !!ldErreicht" in js
    protokoll = lies("app/material/templates/material/pdf/pruefprotokoll.html")
    assert "c-krit" not in protokoll and 'class="krit' not in protokoll and "p.kritisch" not in protokoll
    assert 'colspan="5"' in protokoll and 'colspan="6"' not in protokoll
    assert "kritisch" not in lies("app/material/templates/material/pdf/bericht.html")
    from app.material.services import anleitung, bericht
    assert "kritisch" not in anleitung.THEMEN and "pruefpunkte" in anleitung.THEMEN
    assert "kritischer Mangel" not in bericht.CSV_SPALTEN
    print("Oberfläche statisch bestanden.")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
