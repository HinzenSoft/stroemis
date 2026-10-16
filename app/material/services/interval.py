"""Prüfintervall, nächste Fälligkeit und Lebensende – eine Stelle für alle Rechnungen.

Rangfolge des Prüfintervalls (Vorschlag zum offenen Punkt aus dem Konzept):

  Herstellerseite    Produkt, sonst die nächste Kategorie mit Vorgabe (Kategorie → Oberkategorie …)
  Organisation       Artikel, sonst der nächste Ordner mit Vorgabe (Ordner → … → Gliederung)

Innerhalb jeder Seite überschreibt die genauere Ebene die gröbere – das ist die Vererbung aus dem
Konzept. Zwischen beiden Seiten gilt das KÜRZERE Intervall: Die Herstellerangabe ist eine Obergrenze,
die eine Gliederung verschärfen, aber nicht verlängern kann. Ein Fahrzeugordner mit 6 Monaten macht
aus einem 12-Monats-Produkt also 6; ein Ordner mit 24 Monaten ändert an einem 12-Monats-Produkt nichts.
Am Artikel selbst wird ein Wert über der Herstellerseite gar nicht erst angenommen (bestand.py).
"""
import calendar
from datetime import date

from ... import db
from . import erster_tag, heute


def plus_monate(d, monate):
    """Datum + n Monate; der Tag wird auf das Monatsende gekürzt (31.01. + 1 → 28./29.02.)."""
    gesamt = d.month - 1 + monate
    jahr, monat = d.year + gesamt // 12, gesamt % 12 + 1
    return date(jahr, monat, min(d.day, calendar.monthrange(jahr, monat)[1]))


def plus_jahre(d, jahre):
    return plus_monate(d, 12 * jahre)


def _kategorie_kette(kategorie_id):
    kette, gesehen = [], set()
    while kategorie_id and kategorie_id not in gesehen:
        gesehen.add(kategorie_id)
        k = db.query("SELECT id, parent_id, name, default_interval_months FROM mat_category WHERE id = ?",
                     (kategorie_id,), one=True)
        if not k:
            break
        kette.append(k)
        kategorie_id = k["parent_id"]
    return kette


def _ordner_kette(ordner_id):
    kette, gesehen = [], set()
    while ordner_id and ordner_id not in gesehen:
        gesehen.add(ordner_id)
        o = db.query("SELECT id, parent_id, name, kind, interval_months FROM mat_folder WHERE id = ?",
                     (ordner_id,), one=True)
        if not o:
            break
        kette.append(o)
        ordner_id = o["parent_id"]
    return kette


def herstellerseite(produkt):
    """(Monate, Quelle) aus Produkt oder Kategorie-Kette – oder (None, None)."""
    if produkt.get("interval_months"):
        return produkt["interval_months"], "Produkt"
    for k in _kategorie_kette(produkt.get("category_id")):
        if k["default_interval_months"]:
            return k["default_interval_months"], f"Kategorie „{k['name']}“"
    return None, None


def organisationsseite(ordner_id, artikel_monate=None):
    """(Monate, Quelle) aus Artikel oder Ordner-Kette – oder (None, None)."""
    if artikel_monate:
        return artikel_monate, "Artikel"
    for o in _ordner_kette(ordner_id):
        if o["interval_months"]:
            art = "Gliederung" if o["kind"] == "gliederung" else "Ordner"
            return o["interval_months"], f"{art} „{o['name']}“"
    return None, None


def wirksam(produkt, ordner_id, artikel_monate=None):
    """Das geltende Intervall samt Herkunft:
    {"monate", "quelle", "hersteller": [m, q], "organisation": [m, q]}. monate None = keins bekannt."""
    hm, hq = herstellerseite(produkt)
    om, oq = organisationsseite(ordner_id, artikel_monate)
    kandidaten = [(m, q) for m, q in ((hm, hq), (om, oq)) if m]
    if not kandidaten:
        monate, quelle = None, None
    else:
        monate, quelle = min(kandidaten, key=lambda x: x[0])
        if hm and om and om > hm:
            quelle = hq                       # Organisation wollte länger – die Herstellerseite gilt
    return {"monate": monate, "quelle": quelle, "hersteller": [hm, hq], "organisation": [om, oq]}


def lebensende(herstellung, lebensdauer_jahre):
    """retire_by = Herstelldatum + Lebensdauer. Bei einer Monatsangabe zählt der Monatserste."""
    if not herstellung or not lebensdauer_jahre:
        return None
    return plus_jahre(erster_tag(herstellung), lebensdauer_jahre).isoformat()


def faelligkeit_vorschlag(monate, erstgebrauch=None, kauf=None, stichtag=None):
    """Erste Fälligkeit eines neuen Artikels: Beginn der Nutzung (Erstgebrauch, sonst Kauf, sonst
    heute) plus Intervall. Liegt der Beginn lange zurück, ist der Artikel sofort überfällig – richtig
    so: Ein Gurt aus dem Altbestand ohne Prüfnachweis gehört zuerst geprüft."""
    if not monate:
        return None
    beginn = erstgebrauch or kauf
    basis = date.fromisoformat(beginn) if beginn else (stichtag or heute())
    return plus_monate(basis, monate).isoformat()


def spaetestens(monate, stichtag=None):
    """Die späteste Fälligkeit, die sich ohne Prüfung setzen lässt: heute plus ein Intervall."""
    if not monate:
        return None
    return plus_monate(stichtag or heute(), monate).isoformat()
