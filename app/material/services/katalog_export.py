"""Katalog-Export (Lieferung 4): Kategorien, Produkte mit Bild und Dokumenten und die Prüfformulare dieser Instanz
als ZIP im Format 2 des Katalogimports (importer.py) – so kommt der in dev gepflegte Katalog in die Produktion.

    flask --app "app:create_app()" material export-catalog katalog.zip
    GET /api/material/katalog/export

Bestand, Artikel, Prüfungen, Meldungen und Rückrufe bleiben draußen – sie gehören zur Instanz, nicht zum Katalog.
Ebenso alles, was DEMO ist: Kategorien mit DEMO-Kennzeichen samt ihrem ganzen Teilbaum, Produkte mit Kennzeichen
oder in einer DEMO-Kategorie, Formulare mit Kennzeichen oder an einem DEMO-Ziel, Dokumente an DEMO-Zielen. Über die
Oberfläche in einer DEMO-Kategorie Angelegtes trägt selbst kein Kennzeichen – es fällt mit dem Teilbaum heraus,
und der Bericht zählt es eigens.

Aufbau des Archivs:
  katalog.json                          Format 2 (CHANGELOG-Material.md, „Katalogdatei (Format 2)“)
  dateien/bilder/<sha256>.<endung>      Originale der Produktbilder, unverändert (mit ihren Metadaten)
  dateien/dokumente/<sha256>.<endung>   aktuelle Herstellerdokumente (nicht zurückgezogen, nicht abgelöst); ihre
                                        früheren Versionen nur als Kennung („vorgaenger“ in katalog.json)
  bericht.txt                           was drin ist und was nicht – zum Lesen, der Import übergeht ihn

Je Ziel kommt ein Formular mit: das aktive („aktivieren“: true), ohne aktives die neueste Version mit Prüfpunkten
(„aktivieren“: false). Ältere Versionen nicht – ihre Nummern sind ohnehin je Instanz eigene.

Eine Datei, die der Import nicht annähme (größer als seine Grenze, importer.BILD_MAX_IMPORT bzw. DOK_MAX_BYTES), bleibt
draußen und steht im Bericht unter „zu_gross“ – sonst stünde der ganze Import.
"""
import hashlib
import json
import os
import zipfile
from datetime import datetime

from flask import current_app

from ... import db
from ...images import ALLOWED_EXT
from . import ZONE, Abgelehnt, importer, katalog

EXPORT_MAX_BYTES = importer.ZIP_MAX_BYTES
# Bilder und Dokumente gehen ungepackt ins Archiv: Sie packen sich kaum, und so bleibt jeder Eintrag weit unter der
# Grenze, die der Import für das Packverhältnis setzt.
_UNGEPACKT = zipfile.ZIP_STORED


def _ausgeschlossen(kats):
    """Kennungen der Kategorien, die nicht mitkommen: jede mit DEMO-Kennzeichen samt ihrem ganzen Teilbaum."""
    kinder = {}
    for k in kats:
        kinder.setdefault(k["parent_id"], []).append(k["id"])
    raus, stapel = set(), [k["id"] for k in kats if k["demo"]]
    while stapel:
        kid = stapel.pop()
        if kid not in raus:
            raus.add(kid)
            stapel.extend(kinder.get(kid, []))
    return raus


def _summe(pfad):
    summe = hashlib.sha256()
    with open(pfad, "rb") as fh:
        for stueck in iter(lambda: fh.read(1024 * 1024), b""):
            summe.update(stueck)
    return summe.hexdigest()


def _punkt(p):
    return {"gruppe": p["group_name"], "text": p["label"], "art": p["editor"], "pflicht": bool(p["mandatory"]),
            "soll": p["expected_value"], "kritisch": bool(p["is_critical"])}


def sammeln(mit_dateien=True):
    """Der Katalog dieser Instanz ohne DEMO: (daten, dateien, bericht). daten wird katalog.json, dateien ist
    {Pfad im Archiv: Datei hier}, bericht zählt, was drin ist und was ausgelassen wurde. Ohne mit_dateien (Vorschau)
    werden die Produktbilder nicht gelesen – ihre Verweise fehlen dann, Zahlen und Größe stimmen."""
    medien = os.path.realpath(katalog.medien_dir())
    kats = db.query("SELECT * FROM mat_category ORDER BY position, name COLLATE NOCASE, id")
    raus = _ausgeschlossen(kats)
    nach_id = {k["id"]: k for k in kats}
    kinder = {}
    for k in kats:
        kinder.setdefault(k["parent_id"], []).append(k)
    bericht = {"erstellt": datetime.now(ZONE).isoformat(timespec="seconds"), "quelle": current_app.config["BASE_URL"],
               "enthalten": {"kategorien": 0, "produkte": 0, "bilder": 0, "formulare": 0, "dokumente": 0},
               "ausgelassen": {"kategorien": 0, "produkte": 0, "formulare": 0, "dokumente": 0, "ohne_kennzeichen": 0,
                               "namen": []},
               "ohne_punkte": 0, "fehlende_dateien": [], "zu_gross": [], "groesse": 0, "grenze": EXPORT_MAX_BYTES}
    raus_n = bericht["ausgelassen"]
    dateien = {}
    # Alle Dokumente für die Versionsketten („vorgaenger“): je Version, welche sie ersetzt, und woran sie zu erkennen ist.
    alle_dokumente = {d["id"]: d for d in db.query(
        "SELECT id, replaces_id, file_path, url, version, sha256 FROM mat_product_document")}

    def pfad(kid):
        teile, gesehen = [], set()
        while kid and kid not in gesehen:
            gesehen.add(kid)
            teile.insert(0, nach_id[kid]["name"])
            kid = nach_id[kid]["parent_id"]
        return teile

    def datei(unter, quelle_dir, name, was, grenze, sha=None):
        """Eine Datei unter media/material in den Export aufnehmen – nur, wenn sie wirklich dort liegt und der Import
        sie annimmt (höchstens grenze Bytes). Liefert den Pfad im Archiv oder None; was (etwa „Produktbild von …“)
        steht dann im Bericht unter fehlende_dateien bzw. zu_gross."""
        quelle = os.path.join(medien, quelle_dir, name or "")
        echt = os.path.realpath(quelle)
        if not name or os.path.commonpath([medien, echt]) != medien or not os.path.isfile(echt):
            bericht["fehlende_dateien"].append(was)
            return None
        groesse = os.path.getsize(echt)
        if groesse > grenze:
            bericht["zu_gross"].append(f"{was}: {groesse / (1024 * 1024):.1f} MB – der Import nimmt höchstens "
                                       f"{grenze // (1024 * 1024)} MB")
            return None
        if not mit_dateien and not sha:
            schluessel = f"{unter}:{name}"            # Vorschau: Platzhalter, nur für Zahl und Größe
        else:
            schluessel = f"dateien/{unter}/{sha or _summe(echt)}{os.path.splitext(name)[1].lower()}"
        if schluessel not in dateien:
            dateien[schluessel] = echt
            bericht["groesse"] += groesse
        return schluessel

    def dok_summe(d):
        """SHA-256 der Datei eines Dokuments: gespeichert, sonst (ältere Einträge) aus der Datei – None ohne Datei."""
        if len(d["sha256"] or "") == 64:
            return d["sha256"]
        echt = os.path.realpath(os.path.join(medien, "dok", d["file_path"] or ""))
        if not mit_dateien or not d["file_path"] or os.path.commonpath([medien, echt]) != medien \
                or not os.path.isfile(echt):
            return None
        return _summe(echt)

    def vorgaenger(d):
        """Die früheren Versionen von d, neueste zuerst, als Kennung: SHA-256 der Datei bzw. Link und Versionsstand.
        Daran findet der Import die Kette auch dann, wenn am Ziel mehrere Dokumente gleich heißen."""
        out, gesehen, vid = [], {d["id"]}, d["replaces_id"]
        while vid in alle_dokumente and vid not in gesehen:
            gesehen.add(vid)
            v = alle_dokumente[vid]
            if v["url"]:
                out.append({"url": v["url"], "version": v["version"] or ""})
            else:
                summe = dok_summe(v)
                if summe:
                    out.append({"sha256": summe})
            vid = v["replaces_id"]
        return out

    def dokumente(spalte, ziel, zielname):
        out = []
        for d in reversed(importer.aktuelle_dokumente(spalte, ziel)):
            e = {"art": d["kind"], "titel": d["title"], "version": d["version"], "gueltig_ab": d["valid_from"]}
            if d["url"]:
                e["url"] = d["url"]
            else:
                sha = d["sha256"] if len(d["sha256"] or "") == 64 else None
                e["datei"] = datei("dokumente", "dok", d["file_path"], f"Dokument „{d['title']}“ an „{zielname}“",
                                   katalog.DOK_MAX_BYTES, sha)
                if not e["datei"]:
                    continue
            frueher = vorgaenger(d)
            if frueher:
                e["vorgaenger"] = frueher
            out.append(e)
        bericht["enthalten"]["dokumente"] += len(out)
        return out

    def ausgelassene_dokumente(spalte, ziel):
        raus_n["dokumente"] += len(importer.aktuelle_dokumente(spalte, ziel))

    # Kategorien als Baum, in der Reihenfolge der Oberfläche.
    reihe = []                                   # exportierte Kategorien in Baumreihenfolge – für die Formulare

    def baum(parent):
        out = []
        for k in kinder.get(parent, []):
            if k["id"] in raus:
                continue
            reihe.append(k)
            e = {"uid": k["uid"], "name": k["name"], "norm": k["norm"], "materialart": k["default_material_kind"],
                 "intervall_monate": k["default_interval_months"], "lebensdauer_jahre": k["default_lifetime_years"],
                 "position": k["position"]}
            docs = dokumente("category_id", k["id"], " / ".join(pfad(k["id"])))
            if docs:
                e["dokumente"] = docs
            unter = baum(k["id"])
            if unter:
                e["unterkategorien"] = unter
            out.append(e)
        return out

    kategorien = baum(None)
    bericht["enthalten"]["kategorien"] = len(reihe)
    for k in kats:
        if k["id"] in raus:
            raus_n["kategorien"] += 1
            raus_n["ohne_kennzeichen"] += 0 if k["demo"] else 1
            if k["demo"] and k["parent_id"] not in raus:
                raus_n["namen"].append(" / ".join(pfad(k["id"])))
            ausgelassene_dokumente("category_id", k["id"])

    produkte, exportiert = [], []
    for p in db.query("SELECT * FROM mat_product ORDER BY manufacturer COLLATE NOCASE, model COLLATE NOCASE, id"):
        name = katalog.produktname(p)
        if p["demo"] or p["category_id"] in raus:
            raus_n["produkte"] += 1
            raus_n["ohne_kennzeichen"] += 0 if p["demo"] else 1
            if p["demo"] and p["category_id"] not in raus:
                raus_n["namen"].append(name)
            ausgelassene_dokumente("product_id", p["id"])
            continue
        exportiert.append(p)
        e = {"uid": p["uid"], "kategorie": pfad(p["category_id"]), "kategorie_uid": nach_id[p["category_id"]]["uid"],
             "hersteller": p["manufacturer"], "modell": p["model"], "artikelnummer": p["article_no"], "norm": p["norm"],
             "materialart": p["material_kind"], "intervall_monate": p["interval_months"],
             "lebensdauer_jahre": p["lifetime_years"], "lebensdauer_quelle": p["lifetime_source"],
             "beschreibung": p["description"]}
        if p["image"]:
            was = f"Produktbild von „{name}“"
            if os.path.splitext(p["image"])[1].lower() in ALLOWED_EXT:
                bild = datei("bilder", "orig", p["image"], was, importer.BILD_MAX_IMPORT)
            else:
                bild = None
                bericht["fehlende_dateien"].append(was)
            if bild:
                if mit_dateien:
                    e["bild"] = bild
                bericht["enthalten"]["bilder"] += 1
        docs = dokumente("product_id", p["id"], name)
        if docs:
            e["dokumente"] = docs
        produkte.append(e)
    bericht["enthalten"]["produkte"] = len(produkte)

    # Je Ziel ein Formular: das aktive, sonst die neueste Version mit Prüfpunkten.
    formulare = {}
    for f in db.query("SELECT f.*, (SELECT COUNT(*) FROM mat_checklist_item c WHERE c.form_id = f.id) AS punkte_n "
                      "FROM mat_form f ORDER BY f.version DESC"):
        formulare.setdefault(("k", f["category_id"]) if f["category_id"] else ("p", f["product_id"]), []).append(f)

    def wahl(ziel):
        liste = formulare.get(ziel) or []
        aktiv = next((f for f in liste if f["active"]), None)
        if aktiv:
            return aktiv, True
        return next((f for f in liste if f["punkte_n"]), None), False

    formular_liste = []
    ziele = [(("k", k["id"]), {"kategorie": pfad(k["id"]), "kategorie_uid": k["uid"]}) for k in reihe]
    ziele += [(("p", p["id"]), {"produkt": {"uid": p["uid"], "hersteller": p["manufacturer"], "modell": p["model"],
                                            "artikelnummer": p["article_no"]}}) for p in exportiert]
    for ziel, angabe in ziele:
        f, aktivieren = wahl(ziel)
        if not f:
            bericht["ohne_punkte"] += 1 if formulare.get(ziel) else 0
            continue
        if f["demo"]:
            raus_n["formulare"] += 1
            continue
        formular_liste.append(dict(angabe, titel=f["title"], aktivieren=aktivieren,
                                   punkte=[_punkt(x) for x in katalog.punkte(f["id"])]))
    exportierte_ziele = {z for z, _ in ziele}
    for ziel in formulare:
        if ziel not in exportierte_ziele:          # Formulare an DEMO-Kategorien und -Produkten
            raus_n["formulare"] += 1
            raus_n["ohne_kennzeichen"] += 0 if all(f["demo"] for f in formulare[ziel]) else 1
    bericht["enthalten"]["formulare"] = len(formular_liste)
    raus_n["namen"] = raus_n["namen"][:50]

    daten = {"format": importer.FORMAT, "version": 2, "quelle": bericht["quelle"], "erstellt": bericht["erstellt"],
             "kategorien": kategorien, "produkte": produkte, "formulare": formular_liste}
    return daten, dateien, bericht


def bericht_text(b):
    """bericht.txt im Archiv: für Menschen, nicht für den Import."""
    e, a = b["enthalten"], b["ausgelassen"]
    zeilen = ["Katalog-Export – Modul Material", f"Quelle:   {b['quelle']}", f"Erstellt: {b['erstellt']}",
              f"Format:   {importer.FORMAT}, Version 2", "",
              "Im Export:",
              f"  Kategorien  {e['kategorien']}", f"  Produkte    {e['produkte']} (davon {e['bilder']} mit Bild)",
              f"  Formulare   {e['formulare']}", f"  Dokumente   {e['dokumente']}", "",
              "Ausgelassen (DEMO):",
              f"  Kategorien  {a['kategorien']}", f"  Produkte    {a['produkte']}", f"  Formulare   {a['formulare']}",
              f"  Dokumente   {a['dokumente']}"]
    if a["ohne_kennzeichen"]:
        zeilen.append(f"  davon {a['ohne_kennzeichen']} ohne eigenes DEMO-Kennzeichen – sie stehen in einer DEMO-Kategorie "
                      "bzw. gehören zu einem DEMO-Ziel.")
    if a["namen"]:
        zeilen += ["", "DEMO-Kategorien und -Produkte (oberste Ebene):"] + [f"  {n}" for n in a["namen"]]
    if b["ohne_punkte"]:
        zeilen += ["", f"Nicht im Export: {b['ohne_punkte']} Formularentwürfe ohne Prüfpunkte (ohne aktives Formular)."]
    if b["fehlende_dateien"]:
        zeilen += ["", "Nicht im Export, weil die Datei hier fehlt:"] + [f"  {x}" for x in b["fehlende_dateien"]]
    if b["zu_gross"]:
        zeilen += ["", "Nicht im Export, weil der Import die Datei nicht annähme:"] + [f"  {x}" for x in b["zu_gross"]]
    zeilen += ["", "Bestand, Artikel, Prüfungen, Meldungen und Rückrufe sind nie Teil des Katalog-Exports.",
               "Importieren: Katalog → „Katalog importieren“ oder flask material import-catalog <datei.zip>.", ""]
    return "\n".join(zeilen)


def zip_bauen(fh):
    """Den Export als ZIP in den Binärstrom fh schreiben (eine Datei unter TMP_DIR, nicht der Arbeitsspeicher).
    Liefert den Bericht; ist er größer als EXPORT_MAX_BYTES, Abgelehnt (413)."""
    daten, dateien, bericht = sammeln()
    if bericht["groesse"] > EXPORT_MAX_BYTES:
        raise Abgelehnt(f"Der Export wäre größer als {EXPORT_MAX_BYTES // 1024 ** 3} GB.", 413)
    try:
        with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("katalog.json", json.dumps(daten, ensure_ascii=False, indent=1))
            for ziel, quelle in sorted(dateien.items()):
                z.write(quelle, ziel, compress_type=_UNGEPACKT)
            z.writestr("bericht.txt", bericht_text(bericht))
    except OSError as exc:
        current_app.logger.warning("Katalog-Export: Datei nicht lesbar: %s", exc)
        raise Abgelehnt("Eine Datei des Katalogs ließ sich nicht lesen. Bitte erneut versuchen.", 500)
    return bericht
