"""Der sichtbare Status eines Artikels – nie gespeichert, immer abgeleitet.

Eine Wahrheit über die Einsatzbereitschaft: status() für einen einzelnen Artikel, status_sql() für
Listen, Zählungen und Filter in der Datenbank. Beide folgen derselben Rangfolge; ein Test hält sie
gegeneinander (tests/test_material.py).

Rangfolge (das Schwerste gewinnt):
  ausgesondert        lock_state = ausgesondert
  gesperrt            lock_state = gesperrt oder verloren
  lebensdauer         retire_by liegt heute oder davor (nur textiles Material hat ein retire_by)
  neu                 noch keine abgeschlossene Prüfung (last_inspected_on fehlt): Die Eingangsprüfung
                      steht aus – vorher ist nichts einsatzbereit, auch nicht mit Fälligkeit in der Zukunft
  ueberfaellig        next_due_on liegt vor heute – oder fehlt
  bald_faellig        next_due_on liegt innerhalb der Schwelle (Einstellung, Vorgabe 30 Tage)
  einsatzbereit       sonst
"""
from datetime import date, timedelta

from flask import current_app, has_app_context

from . import heute as _heute

STATUS = ("einsatzbereit", "bald_faellig", "ueberfaellig", "neu", "gesperrt", "lebensdauer", "ausgesondert")
LABEL = {"einsatzbereit": "einsatzbereit", "bald_faellig": "bald fällig", "ueberfaellig": "überfällig",
         "neu": "neu", "gesperrt": "gesperrt", "lebensdauer": "Lebensdauer erreicht", "ausgesondert": "ausgesondert"}
# Was als Bestand zählt: alles, was nicht ausgesondert ist. Ein ausgesonderter Artikel bleibt mit
# seinem Lebenslauf sichtbar, taucht aber in keiner Bestandszahl mehr auf.
BESTAND = tuple(s for s in STATUS if s != "ausgesondert")
SCHWELLE_VORGABE = 30


def schwelle_tage():
    """„Bald fällig“ heißt: innerhalb so vieler Tage (Einstellung MATERIAL_BALD_FAELLIG_TAGE)."""
    if has_app_context():
        wert = current_app.config.get("MATERIAL_BALD_FAELLIG_TAGE")
        if wert is not None and wert != "":
            try:
                return max(0, int(wert))          # 0 heißt: erst am Fälligkeitstag „bald fällig“
            except (TypeError, ValueError):
                pass
    return SCHWELLE_VORGABE


def _iso(d):
    return d.isoformat() if isinstance(d, date) else d


def status(item, stichtag=None, schwelle=None):
    """Status eines Artikels (dict mit lock_state, last_inspected_on, next_due_on, retire_by)."""
    stichtag = stichtag or _heute()
    schwelle = schwelle_tage() if schwelle is None else schwelle
    h = _iso(stichtag)
    bald = _iso(stichtag + timedelta(days=schwelle))
    lock = item["lock_state"]
    if lock == "ausgesondert":
        return "ausgesondert"
    if lock in ("gesperrt", "verloren"):
        return "gesperrt"
    if item["retire_by"] and item["retire_by"] <= h:
        return "lebensdauer"
    if not item.get("last_inspected_on"):
        return "neu"
    if not item["next_due_on"] or item["next_due_on"] < h:
        return "ueberfaellig"
    if item["next_due_on"] <= bald:
        return "bald_faellig"
    return "einsatzbereit"


def status_sql(alias="i"):
    """Derselbe Status als SQL-Ausdruck. Braucht die benannten Parameter aus parameter()."""
    a = alias
    return (f"(CASE WHEN {a}.lock_state = 'ausgesondert' THEN 'ausgesondert' "
            f"WHEN {a}.lock_state IN ('gesperrt', 'verloren') THEN 'gesperrt' "
            f"WHEN {a}.retire_by IS NOT NULL AND {a}.retire_by <= :st_heute THEN 'lebensdauer' "
            f"WHEN {a}.last_inspected_on IS NULL THEN 'neu' "
            f"WHEN {a}.next_due_on IS NULL OR {a}.next_due_on < :st_heute THEN 'ueberfaellig' "
            f"WHEN {a}.next_due_on <= :st_bald THEN 'bald_faellig' "
            f"ELSE 'einsatzbereit' END)")


def parameter(stichtag=None, schwelle=None):
    stichtag = stichtag or _heute()
    schwelle = schwelle_tage() if schwelle is None else schwelle
    return {"st_heute": stichtag.isoformat(), "st_bald": (stichtag + timedelta(days=schwelle)).isoformat()}


def leere_zaehlung():
    return {s: 0 for s in STATUS}
