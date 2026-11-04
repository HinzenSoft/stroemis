"""Absätze im Prüfpunkt (Wunsch des Nutzers vom 04.11.2026: „Möglichkeit, Absätze in den Prüfpunkt einzufügen“):
python tests/test_material_pruefpunkt_absatz.py  oder  pytest

1. katalog.punkt_text: Zeilenumbrüche bleiben („\\r\\n“ und „\\r“ werden „\\n“), je Zeile Steuerzeichen und mehrfache
   Leerzeichen zu einem, kein Rand; mehr als eine Leerzeile wird eine, Leerzeilen am Rand fallen weg; ein einzeiliger
   Text kommt genau so heraus wie vorher (services.text mit einzeilig=True); 1000 Zeichen bleiben die Grenze.
2. Ablauf über die Schnittstelle: Formular mit Absätzen anlegen und speichern → GET liefert sie; „Neue Version“ übernimmt
   sie; Katalog-Export (katalog.json) und Import in eine zweite Anlage rund; die Prüfung kopiert sie; Meldungen nennen
   den Punkt in einer Zeile; das Prüfprotokoll-PDF zeigt die Absätze als eigene Zeilen und HTML im Punkttext als Text.
Die Anzeige im Browser (Editor, Nur-Lese-Ansicht, Prüfung, HTML bleibt Text) prüft tests/test_material_formular_editor.py.
Alle Inhalte sind Platzhalter."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (_heute, abschluss, gliederung, katalog_grund, neuer_artikel, pdf_layout_seiten,  # noqa: E402
                           starten, umgebung)
from test_material_katalog import exportieren, importieren, katalogjson  # noqa: E402

ABSATZ = "Platzhalter Absatz eins\r\nPlatzhalter Zeile zwei  \n\n\n\n  Platzhalter   Absatz drei\n"
ABSATZ_NORM = "Platzhalter Absatz eins\nPlatzhalter Zeile zwei\n\nPlatzhalter Absatz drei"
HTML = "<img src=x onerror=alert(1)>\n<b>Platzhalter fett</b>"
MESSUNG = "Platzhalter Messung\nmit zweiter Zeile"


def test_punkt_text():
    with tempfile.TemporaryDirectory() as tmp:
        from test_material import make_app
        app = make_app(tmp)
        with app.app_context():
            from app.material.services import Abgelehnt, text
            from app.material.services.katalog import punkt_text
            assert punkt_text(ABSATZ, 1) == ABSATZ_NORM
            assert punkt_text("\n\n  A \n\n", 1) == "A"
            assert punkt_text("A\r\rB", 1) == "A\n\nB"
            assert punkt_text("A\tB\x01C", 1) == "A B C"
            assert punkt_text(HTML, 1) == HTML
            # Einzeilig wie vorher.
            for t in ("a  b", "  x\ty ", "a\x01b", "a   b", "a b", "Prüfpunkt (z. B. „x“)"):
                assert punkt_text(t, 1) == text({"text": t}, "text", "x", 1000, pflicht=True), t
            for leer in ("", "  \n\n \r\n", None, "\x01"):
                try:
                    punkt_text(leer, 3)
                    raise AssertionError(repr(leer))
                except Abgelehnt as e:
                    assert "Text von Prüfpunkt 3" in str(e)
            assert punkt_text("x" * 1000, 1) == "x" * 1000
            try:
                punkt_text("x" * 1001, 1)
                raise AssertionError("zu lang")
            except Abgelehnt as e:
                assert "höchstens 1000" in str(e)
            # Zeilen zählen nur einmal: 500 + „\r\n“ + 499 sind 1000 Zeichen.
            assert len(punkt_text("a" * 500 + "\r\n" + "b" * 499, 1)) == 1000
    print("punkt_text bestanden.")


def test_ablauf():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        app, k = umgebung(tmp_a)
        ids = katalog_grund(k["adm"])
        kp, w, p1 = k["katalog"], k["wart"], k["pruefer"]
        r = kp.post("/api/material/formular-pool", json={"kategorie_id": ids["gurte"], "titel": "Platzhalter Absatz", "punkte": [
            {"gruppe": "Platzhalter Gruppe", "text": ABSATZ, "art": "yesno", "soll": "nein"},
            {"gruppe": "Platzhalter Gruppe", "text": HTML, "art": "yesno", "soll": "ja"},
            {"text": "Platzhalter  einzeilig", "art": "text", "pflicht": False},
            {"text": MESSUNG, "art": "text"}]})
        assert r.status_code == 201, r.get_json()
        fid, pf = r.json["formular"]["id"], r.json["formular"]["formular_id"]
        erwartet = [ABSATZ_NORM, HTML, "Platzhalter einzeilig", MESSUNG]
        assert [p["text"] for p in r.json["formular"]["punkte"]] == erwartet
        # Speichern (PUT) wie der Editor: Absätze bleiben, Windows-Umbrüche werden „\n“.
        punkte = r.json["formular"]["punkte"]
        punkte[3]["text"] = MESSUNG.replace("\n", "\r\n")
        r = kp.put(f"/api/material/formulare/{fid}", json={"titel": "Platzhalter Absatz", "punkte": punkte})
        assert r.status_code == 200, r.get_json()
        assert [p["text"] for p in kp.get(f"/api/material/formulare/{fid}").json["formular"]["punkte"]] == erwartet
        # Neue Version übernimmt die Punkte unverändert.
        r = kp.post("/api/material/formulare", json={"formular_id": pf, "vorlage_id": fid})
        assert r.status_code == 201 and [p["text"] for p in r.json["formular"]["punkte"]] == erwartet
        assert kp.post(f"/api/material/formulare/{fid}/aktivieren", json={}).status_code == 200
        assert kp.put(f"/api/material/formular-pool/{pf}/zuweisung", json={"produkte": [ids["gurt"]]}).status_code == 200

        # Katalog-Export (Format 3) und Import in eine zweite Anlage: rund.
        roh = exportieren(kp)
        formulare = katalogjson(roh)["formulare"]
        texte = [p["text"] for f in formulare for p in f["punkte"]]
        assert all(t in texte for t in erwartet), texte
        app_b, kb = umgebung(tmp_b)
        ber = importieren(kb["katalog"], roh, False)
        assert ber["gespeichert"], ber
        with app_b.app_context():
            from app import db
            labels = [z["label"] for z in db.query("SELECT label FROM mat_checklist_item ORDER BY form_id, position")]
        assert all(t in labels for t in erwartet), labels

        # Prüfung: kopiert die Absätze; die Meldung nennt den Punkt in einer Zeile; das PDF zeigt eigene Zeilen.
        gid, _ = gliederung(w)
        a = neuer_artikel(w, ids["gurt"], gid, manufactured_on=f"{_heute().year - 1}-01")
        r = starten(p1, a["id"])
        assert r.status_code == 201, r.get_json()
        pr = r.json["pruefung"]
        assert [x["text"] for x in pr["punkte"]] == erwartet
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 400 and "Noch ohne Befund: Platzhalter Messung mit zweiter Zeile" in r.json["error"], r.get_json()
        assert "\n" not in r.json["error"]
        messung = next(x for x in pr["punkte"] if x["text"] == MESSUNG)
        r = p1.put(f"/api/material/pruefungen/{pr['id']}/punkte/{messung['id']}", json={"wert": "Platzhalter Wert"})
        assert r.status_code == 200, r.get_json()
        r = abschluss(p1, pr["id"], ergebnis="einsatzbereit")
        assert r.status_code == 200, r.get_json()
        r = w.get(f"/materialablage/pruefung/{pr['id']}/pdf")
        assert r.status_code == 200 and r.mimetype == "application/pdf"
        pfad = os.path.join(tmp_a, "protokoll.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.get_data())
        zeilen = [z.strip() for z in "\n".join(pdf_layout_seiten(pfad)).splitlines()]
        def zeile_mit(t):
            return next((i for i, z in enumerate(zeilen) if t in z), None)
        eins, zwei, drei = (zeile_mit(t) for t in ("Platzhalter Absatz eins", "Platzhalter Zeile zwei", "Platzhalter Absatz drei"))
        assert None not in (eins, zwei, drei) and eins < zwei < drei, (eins, zwei, drei)
        assert "Platzhalter Zeile zwei" not in zeilen[eins] and drei - zwei >= 2, zeilen[eins:drei + 1]   # Leerzeile dazwischen
        assert zeile_mit("<img src=x onerror=alert(1)>") is not None and zeile_mit("<b>Platzhalter fett</b>") is not None
        assert zeile_mit("<img") < zeile_mit("<b>Platzhalter fett</b>")
    print("Ablauf bestanden.")


if __name__ == "__main__":
    test_punkt_text()
    test_ablauf()
