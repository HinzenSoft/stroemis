"""Seitenumbrüche in den PDF-Protokollen (Wunsch des Nutzers vom 27.10.2026, „Umbrüche in Protokollen vermeiden“, mit
Nachtrag):  python tests/test_material_pdf_umbruch.py  oder pytest

Gesetzt wird mit pdf.rendern aus Platzhalterdaten (wie die Dienste sie liefern), geprüft am echten PDF mit
pdftotext -layout:
- Sammelprotokoll mit 20 bis 40 Artikeln, so dass das Verzeichnis der Einzelprotokolle an verschiedenen Stellen der
  Seite beginnt: Überschrift nie mit weniger als vier Zeilen, am Ende nie weniger als drei Zeilen allein, ein kurzes
  Verzeichnis (bis 20 Zeilen) ungeteilt; die Artikelliste endet nie mit ein oder zwei Zeilen.
- Prüfprotokoll: Der Abschluss (Ergebnis, Herstellerdokumente, Unterschrift) beginnt auf einer neuen Seite und steht
  zusammen; Art, Version und Datum der Herstellerdokumente brechen nicht mitten im Wort oder Datum um.
- Prüfprotokoll mit sehr langen Bemerkungen: Jede Seite mit Befunden trägt den Tabellenkopf, die Überschrift steht nie
  allein (Zeilen mit viel Text bleiben aus den Ketten heraus).

Alle Namen, Nummern und Texte hier sind Platzhalter."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import make_app, pdf_layout_seiten  # noqa: E402

SHA = "0123456789abcdef" * 4


def _dokument(art, pid):
    return {"titel": art, "protokoll_id": pid, "festgeschrieben": "27.10.2026, 08:00 Uhr", "demo": False,
            "plattform": "beispiel.invalid", "pruefseite": "https://beispiel.invalid/pruefen", "art": art}


def _sammel(n):
    artikel = [{"nr": i, "inventarnummer": f"M-{i:06d}", "seriennummer": f"SN-PLATZHALTER-{i:04d}",
                "produkt_name": "Platzhalter-Produkt", "produkt_zusatz": "Platzhalter-Beschreibung",
                "ordner": "Platzhalter-Gliederung › Platzhalter-Lager", "zustand": "erledigt",
                "ergebnis": "einsatzbereit", "ergebnis_text": "einsatzbereit", "datum": "24.10.2026",
                "pruefer": "Platzhalter-Prüfer", "urkunde": "0000-0000", "protokoll_id": f"P-2026-9{i:05d}",
                "datei_sha256": SHA, "zwischen": [], "im_set": False}
               for i in range(1, n + 1)]
    return {"dokument": _dokument("Sammelprotokoll", "S-2026-900001"),
            "durchgang": {"titel": "Platzhalter-Durchgang", "ordner": "Platzhalter-Gliederung › Platzhalter-Lager",
                          "gliederung": "Platzhalter-Gliederung", "eroeffnet": "01.10.2026 von Platzhalter",
                          "abgeschlossen": "27.10.2026, 08:00 Uhr von Platzhalter", "abgebrochen": False},
            "set_info": None, "zaehlung": [{"text": "Artikel im Durchgang", "anzahl": n}, {"text": "geprüft", "anzahl": n}],
            "pruefer": [{"name": "Platzhalter-Prüfer", "urkunde": "0000-0000", "anzahl": n, "unterschrift": None}],
            "artikel": artikel, "ohne_protokoll": 0, "set_protokolle": []}


def _punkt(nr, notiz=""):
    return {"nr": nr, "text": f"Platzhalter-Prüfpunkt {nr}", "kritisch": False, "soll": "Ja", "befund": "ok",
            "befund_text": "in Ordnung", "wert": "Ja", "nummern": [], "foto_nr": None, "notiz": notiz, "unterschrift": None}


def _pruef(punkte, dokumente=()):
    return {"dokument": _dokument("Prüfprotokoll", "P-2026-900001"),
            "artikel": {"produkt_name": "Platzhalter-Produkt", "produkt_zusatz": "", "kategorie": "Platzhalter-Kategorie",
                        "seriennummer": "SN-PLATZHALTER", "seriennummer_vergeben": False, "inventarnummer": "M-000001",
                        "hersteller": "Platzhalter-Hersteller", "gliederung": "Platzhalter-Gliederung",
                        "ordner": "Platzhalter-Lager", "bild": None, "qr_svg": None},
            "pruefung": {"art": "Regelprüfung", "datum": "27.10.2026", "pruefer": "Platzhalter-Prüfer",
                         "urkunde": "0000-0000", "login": "pruefer@example.org", "formular": "Platzhalter-Formular",
                         "durchgang": "", "grund": "", "ergebnis": "einsatzbereit", "ergebnis_text": "einsatzbereit",
                         "naechste": "27.10.2027", "lebensdauer": "", "bemerkung": "Platzhalter-Bemerkung", "folge": "",
                         "berichtigt": None},
            "gruppen": [{"name": "Platzhalter-Gruppe", "punkte": punkte}], "maengel": 0, "fotos": [],
            "dokumente": list(dokumente), "anhaenge": [], "anhaenge_angefuegt": 0,
            "unterschrift": {"bild": None, "name": "Platzhalter-Prüfer", "urkunde": "0000-0000",
                             "login": "pruefer@example.org", "zeit": "27.10.2026, 08:00 Uhr"}}


def _seiten(app, tmp, vorlage, daten, name):
    from app.material.services import pdf
    with app.app_context():
        inhalt = pdf.rendern(vorlage, daten)
    pfad = os.path.join(tmp, name + ".pdf")
    with open(pfad, "wb") as f:
        f.write(inhalt)
    return pdf_layout_seiten(pfad)


def _zaehlen(seite, muster):
    return sum(1 for z in seite.splitlines() if re.match(muster, z))


def test_sammelprotokoll_verzeichnis_und_artikelliste():
    """Das Verzeichnis beginnt an verschiedenen Stellen der Seite – nie mit weniger als vier Zeilen unter der
    Überschrift, nie mit weniger als drei Zeilen allein am Ende; kurz (bis 20) ungeteilt."""
    verz = r"^\s*P-2026-9\d{5}\s"                  # Zeile des Verzeichnisses: beginnt mit der Protokoll-ID
    art = r"^\s*\d+\s+M-\d{6}\s"                     # Zeile der Artikelliste: Nr. und Inventarnummer
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        for n in (6, 12, 18, 20, 22, 26, 30, 34, 38):
            seiten = _seiten(app, tmp, "sammelprotokoll", _sammel(n), f"sammel-{n}")
            mit_v = [i for i, s in enumerate(seiten) if _zaehlen(s, verz)]
            kopf = [i for i, s in enumerate(seiten) if "Verzeichnis der Einzelprotokolle" in s]
            assert len(kopf) == 1 and kopf[0] == mit_v[0], (n, kopf, mit_v)
            je_seite = [_zaehlen(seiten[i], verz) for i in mit_v]
            assert sum(je_seite) == n, (n, je_seite)
            if n <= 20:
                assert len(mit_v) == 1, ("kurzes Verzeichnis geteilt", n, je_seite)
            assert je_seite[0] >= min(4, n), ("Anfang", n, je_seite)
            assert len(je_seite) == 1 or je_seite[-1] >= 3, ("Ende", n, je_seite)
            a_seite = [_zaehlen(s, art) for s in seiten if _zaehlen(s, art)]
            assert sum(a_seite) == n, (n, a_seite)
            assert len(a_seite) == 1 or a_seite[-1] >= 3, ("Ende der Artikelliste", n, a_seite)
    print("Sammelprotokoll: Umbrüche im Verzeichnis und in der Artikelliste bestanden.")


def test_pruefprotokoll_abschluss_auf_neuer_seite():
    """Ergebnis, Bemerkung, Herstellerdokumente und Unterschrift ab einer neuen Seite und zusammen; die Spalten der
    Herstellerdokumente zerhacken weder Art noch Version noch Datum."""
    dokumente = [{"titel": f"Platzhalter-Dokument {i}", "art": "Konformitätserklärung",
                  "version": "ausgestellt 20.01.2025 (Musterort)", "gueltig_ab": "20.01.2025", "sha256": SHA,
                  "herkunft": "Produkt"} for i in (1, 2)]
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        for n in (3, 30):
            seiten = _seiten(app, tmp, "pruefprotokoll", _pruef([_punkt(i) for i in range(1, n + 1)], dokumente),
                             f"pruef-{n}")
            ergebnis = [i for i, s in enumerate(seiten) if re.search(r"^\s*Ergebnis\s*$", s, re.M)]
            assert len(ergebnis) == 1 and ergebnis[0] >= 1, (n, ergebnis)
            seite = seiten[ergebnis[0]]
            # Die Seite beginnt mit dem Abschluss: keine Befundzeile davor, Überschrift als erste Zeile nach dem Kopf.
            assert not re.search(r"Platzhalter-Prüfpunkt", seite), (n, seite[:400])
            zeilen = [z.strip() for z in seite.splitlines() if z.strip()]
            assert zeilen[1] == "Ergebnis", (n, zeilen[:3])
            for teil in ("Platzhalter-Bemerkung", "Herstellerdokumente am Prüftag", "Unterschrift", "Platzhalter-Dokument 2"):
                assert teil in seite, (n, teil)
            assert re.search(r"Konformitätserklärung\s+20\.01\.2025", seite), seite
            assert "ausgestellt 20.01.2025" in seite, seite
            for zerhackt in ("ausge-", "Konformitäts-", "20.01.20 ", "Konformitätser-"):
                assert zerhackt not in seite, (n, zerhackt)
    print("Prüfprotokoll: Abschluss auf neuer Seite bestanden.")


def test_pruefprotokoll_lange_bemerkungen_mit_kopf():
    """Befunde mit sehr langen Bemerkungen (unter der Grenze für umbrechende Zeilen): Jede Seite mit Befunden trägt den
    Tabellenkopf, die Überschrift „Befunde“ steht mit mindestens einem Prüfpunkt auf ihrer Seite."""
    notiz = "Platzhalter-Bemerkung mit langem Text. " * 25        # rund 1000 Zeichen je Zeile
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        seiten = _seiten(app, tmp, "pruefprotokoll", _pruef([_punkt(i, notiz) for i in range(1, 9)]), "pruef-lang")
        mit_punkt = [i for i, s in enumerate(seiten) if "Platzhalter-Prüfpunkt" in s]
        assert len(mit_punkt) >= 2, mit_punkt
        for i in mit_punkt:
            assert re.search(r"Prüfpunkt\s+kritisch\s+Soll\s+Befund", seiten[i]), ("Tabellenkopf fehlt", i)
        kopf = [i for i, s in enumerate(seiten) if re.search(r"^\s*Befunde\s*$", s, re.M)]
        assert len(kopf) == 1 and kopf[0] in mit_punkt, (kopf, mit_punkt)
    print("Prüfprotokoll: lange Bemerkungen mit Tabellenkopf bestanden.")


if __name__ == "__main__":
    test_sammelprotokoll_verzeichnis_und_artikelliste()
    test_pruefprotokoll_abschluss_auf_neuer_seite()
    test_pruefprotokoll_lange_bemerkungen_mit_kopf()
