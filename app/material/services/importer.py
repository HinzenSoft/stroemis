"""Katalogimport aus einer JSON-Datei – der Weg, auf dem die Ergebnisse aus Phase 0 (Produkte,
Intervalle, Lebensdauern, Prüfformulare der Sachkundigen) ins System kommen.

    flask --app "app:create_app()" material import-catalog katalog.json [--trocken]

Der Import läuft durch dieselben Regeln wie die Oberfläche (katalog.py) und ist ganz oder gar nicht:
Findet er auch nur einen Fehler, wird nichts gespeichert, und der Bericht nennt jeden Fehler mit
seiner Stelle in der Datei. Er ist wiederholbar: Vorhandene Kategorien (gleicher Name an gleicher
Stelle) und Produkte (gleiche Dublette Hersteller + Modell + Artikelnummer) werden abgeglichen statt
doppelt angelegt; ein Formular, dessen Prüfpunkte sich nicht geändert haben, bleibt bei seiner
Version. Das Format steht in CHANGELOG-Material.md.
"""
from flask import g

from ... import db
from . import Abgelehnt, katalog, text

FORMAT = "stroemis-material-katalog"


class _Rueckgaengig(Exception):
    pass


def _name(wert, was="Name", n=120):
    """Ein Name, vereinheitlicht wie beim Speichern (Leerraum zusammengezogen, Steuerzeichen raus) –
    sonst fände ein zweiter Lauf „PSA  gegen Absturz“ nicht wieder, was der erste gespeichert hat."""
    return text({"wert": wert}, "wert", was, n)


def _pfad(wert):
    """Kategoriepfad: Liste von Namen oder ein Text mit „ / “ dazwischen."""
    if isinstance(wert, str):
        teile = [_name(t) for t in wert.split(" / ")]
    elif isinstance(wert, list) and all(isinstance(t, str) for t in wert):
        teile = [_name(t) for t in wert]
    else:
        raise Abgelehnt("„kategorie“ muss ein Pfad sein (Liste von Namen oder „Ober / Unter“).")
    if not teile or not all(teile):
        raise Abgelehnt("Der Kategoriepfad ist leer.")
    return teile


def _kategorie_finden(pfad):
    parent = None
    for name in pfad:
        k = db.query("SELECT * FROM mat_category WHERE COALESCE(parent_id, 0) = ? AND name = ? COLLATE NOCASE",
                     (parent or 0, name), one=True)
        if not k:
            raise Abgelehnt(f"Kategorie „{' / '.join(pfad)}“ gibt es nicht (weder im Katalog noch in der Datei).")
        parent = k["id"]
    return parent


_KATEGORIE_ABBILDUNG = {"norm": "norm", "materialart": "default_material_kind",
                        "intervall_monate": "default_interval_months", "lebensdauer_jahre": "default_lifetime_years",
                        "position": "position"}
_PRODUKT_ABBILDUNG = {"hersteller": "manufacturer", "modell": "model", "artikelnummer": "article_no", "norm": "norm",
                      "materialart": "material_kind", "intervall_monate": "interval_months",
                      "lebensdauer_jahre": "lifetime_years", "lebensdauer_quelle": "lifetime_source",
                      "beschreibung": "description"}


def _abbilden(eintrag, abbildung):
    return {ziel: eintrag[quelle] for quelle, ziel in abbildung.items() if quelle in eintrag}


def _kategorien(liste, parent, stelle, bericht, demo):
    if not isinstance(liste, list):
        raise Abgelehnt(f"{stelle}: „kategorien“ muss eine Liste sein.")
    for n, e in enumerate(liste):
        ort = f"{stelle}[{n}]"
        try:
            if not isinstance(e, dict):
                raise Abgelehnt("Eintrag ist kein Objekt.")
            name = _name(e.get("name")) if isinstance(e.get("name"), str) else ""
            if not name:
                raise Abgelehnt("„name“ fehlt.")
            d = dict(_abbilden(e, _KATEGORIE_ABBILDUNG), name=name, parent_id=parent)
            vorhanden = db.query("SELECT * FROM mat_category WHERE COALESCE(parent_id, 0) = ? AND name = ? COLLATE NOCASE",
                                 (parent or 0, name), one=True)
            if vorhanden:
                kid = vorhanden["id"]
                vorher = katalog.kategorie_werte({}, vorhanden)
                nachher = katalog.kategorie_werte(d, vorhanden)
                if vorher != nachher:
                    katalog.kategorie_aendern(kid, d)
                    bericht["kategorien"]["geaendert"] += 1
                else:
                    bericht["kategorien"]["unveraendert"] += 1
            else:
                kid = katalog.kategorie_anlegen(d, demo=demo)
                bericht["kategorien"]["neu"] += 1
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort} ({e.get('name') if isinstance(e, dict) else '?'}): {exc}")
            continue
        if e.get("unterkategorien"):
            _kategorien(e["unterkategorien"], kid, f"{ort}.unterkategorien", bericht, demo)


def _produkt_key(e):
    if not isinstance(e, dict):
        raise Abgelehnt("Produktangabe ist kein Objekt.")
    teile = [e.get(k) if isinstance(e.get(k), str) else "" for k in ("hersteller", "modell", "artikelnummer")]
    return katalog.dedupe_key(*teile)


def _produkte(liste, bericht, demo):
    if not isinstance(liste, list):
        raise Abgelehnt("„produkte“ muss eine Liste sein.")
    for n, e in enumerate(liste):
        ort = f"produkte[{n}]"
        try:
            if not isinstance(e, dict):
                raise Abgelehnt("Eintrag ist kein Objekt.")
            d = _abbilden(e, _PRODUKT_ABBILDUNG)
            d["category_id"] = _kategorie_finden(_pfad(e.get("kategorie")))
            vorhanden = db.query("SELECT * FROM mat_product WHERE dedupe_key = ?", (_produkt_key(e),), one=True)
            if vorhanden:
                if katalog.produkt_werte(d, vorhanden) != katalog.produkt_werte({}, vorhanden):
                    katalog.produkt_aendern(vorhanden["id"], d)
                    bericht["produkte"]["geaendert"] += 1
                else:
                    bericht["produkte"]["unveraendert"] += 1
            else:
                katalog.produkt_anlegen(d, demo=demo)
                bericht["produkte"]["neu"] += 1
        except Abgelehnt as exc:
            name = f"{e.get('hersteller', '?')} {e.get('modell', '?')}" if isinstance(e, dict) else "?"
            bericht["fehler"].append(f"{ort} ({name}): {exc}")


def _formulare(liste, bericht, demo):
    if not isinstance(liste, list):
        raise Abgelehnt("„formulare“ muss eine Liste sein.")
    for n, e in enumerate(liste):
        ort = f"formulare[{n}]"
        try:
            if not isinstance(e, dict):
                raise Abgelehnt("Eintrag ist kein Objekt.")
            if ("kategorie" in e) == ("produkt" in e):
                raise Abgelehnt("Ein Formular gehört entweder zu einer „kategorie“ oder zu einem „produkt“.")
            if "kategorie" in e:
                ziel = {"kategorie_id": _kategorie_finden(_pfad(e["kategorie"]))}
                spalte, wert = "category_id", ziel["kategorie_id"]
            else:
                p = db.query("SELECT id FROM mat_product WHERE dedupe_key = ?", (_produkt_key(e["produkt"]),), one=True)
                if not p:
                    raise Abgelehnt("Das Produkt gibt es weder im Katalog noch in der Datei.")
                ziel = {"produkt_id": p["id"]}
                spalte, wert = "product_id", p["id"]
            punkte = katalog.punkte_pruefen(e.get("punkte"))
            if not punkte:
                raise Abgelehnt("Ein Formular braucht mindestens einen Prüfpunkt.")
            titel = _name(e.get("titel"), "Titel", 160) if isinstance(e.get("titel"), str) else ""
            aktivieren = e.get("aktivieren", True) is not False
            letzte = db.query(f"SELECT * FROM mat_form WHERE {spalte} = ? ORDER BY version DESC LIMIT 1", (wert,), one=True)
            gleich = False
            if letzte:
                alt = [{k: p[k] for k in ("group_name", "label", "editor", "mandatory", "expected_value", "is_critical")}
                       for p in katalog.punkte(letzte["id"])]
                neu = [{k: p[k] for k in ("group_name", "label", "editor", "mandatory", "expected_value", "is_critical")}
                       for p in punkte]
                gleich = alt == neu and letzte["title"] == titel
            if gleich:
                fid = letzte["id"]
                bericht["formulare"]["unveraendert"] += 1
            else:
                fid = katalog.formular_anlegen(dict(ziel, titel=titel, punkte=e.get("punkte")), demo=demo)
                bericht["formulare"]["neu"] += 1
            if aktivieren and not katalog.formular(fid)["active"]:
                katalog.formular_aktivieren(fid)
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort}: {exc}")


def importieren(daten, trocken=False, quelle="Datei"):
    """Den Katalog aus einem geladenen JSON-Objekt übernehmen. Liefert einen Bericht; bei Fehlern
    oder im Trockenlauf ist danach nichts gespeichert."""
    bericht = {"kategorien": {"neu": 0, "geaendert": 0, "unveraendert": 0},
               "produkte": {"neu": 0, "geaendert": 0, "unveraendert": 0},
               "formulare": {"neu": 0, "unveraendert": 0}, "fehler": [], "gespeichert": False}
    if not isinstance(daten, dict) or daten.get("format") != FORMAT:
        bericht["fehler"].append(f"Das ist keine Katalogdatei (\"format\": \"{FORMAT}\" fehlt).")
        return bericht
    if daten.get("version") != 1:
        bericht["fehler"].append("Unbekannte Formatversion – erwartet wird \"version\": 1.")
        return bericht
    demo = daten.get("demo") is True
    g.mat_akteur = f"Katalogimport ({quelle})"
    try:
        with db.transaction(sofort=True):
            try:
                _kategorien(daten.get("kategorien") or [], None, "kategorien", bericht, demo)
                _produkte(daten.get("produkte") or [], bericht, demo)
                _formulare(daten.get("formulare") or [], bericht, demo)
            except Abgelehnt as exc:
                bericht["fehler"].append(str(exc))
            if bericht["fehler"] or trocken:
                raise _Rueckgaengig()
        bericht["gespeichert"] = True
    except _Rueckgaengig:
        pass
    finally:
        g.pop("mat_akteur", None)
    return bericht
