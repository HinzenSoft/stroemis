"""Katalog-Export (Lieferung 4): Kategorien, Produkte mit Bild und Dokumenten und die Prüfformulare dieser Instanz
als ZIP im Format 3 des Katalogimports (importer.py; bis Schritt 37 Format 2) – so kommt der in dev gepflegte Katalog in
die Produktion.

    flask --app "app:create_app()" material export-catalog katalog.zip
    GET /api/material/katalog/export

Bestand, Artikel, Prüfungen, Meldungen und Rückrufe bleiben draußen – sie gehören zur Instanz, nicht zum Katalog.
Ebenso alles, was DEMO ist: Kategorien mit DEMO-Kennzeichen samt ihrem ganzen Teilbaum, Produkte mit Kennzeichen
oder in einer DEMO-Kategorie, Formulare im Pool einer DEMO-Kategorie, Dokumente an DEMO-Zielen. Über die Oberfläche in
einer DEMO-Kategorie Angelegtes trägt selbst kein Kennzeichen – es fällt mit dem Teilbaum heraus, und der Bericht zählt
es eigens. Ein Prüfformular mit DEMO-Kennzeichen in einer echten Kategorie (die Platzhalter der Skripte) kommt mit, wenn
es aktiv ist (Entscheidung vom 04.11.2026, katalog-transfer) – der Import nimmt „DEMO“ vorn aus dem Titel und übernimmt
nie ein Kennzeichen; der Bericht nennt es.

Aufbau des Archivs:
  katalog.json                          Format 3 (CHANGELOG-Material.md, „Katalogdatei (Format 3)“)
  dateien/bilder/<sha256>.<endung>      Originale der Produktbilder, unverändert (mit ihren Metadaten)
  dateien/dokumente/<sha256>.<endung>   aktuelle Herstellerdokumente (nicht zurückgezogen, nicht abgelöst); ihre
                                        früheren Versionen nur als Kennung („vorgaenger“ in katalog.json)
  bericht.txt                           was drin ist und was nicht – zum Lesen, der Import übergeht ihn

Prüfformulare (Format 3, Formular-Pool): je Formular des Pools mit aktiver Version genau diese – mit uid, Heimat
(„kategorie“, „kategorie_uid“), Titel, Prüfpunkten und den Zuweisungen („standard_fuer“: Kategorien, „zugewiesen“:
Produkte, beide nur, soweit sie mitkommen). Ohne aktive Version kommt ein Formular nicht mit (E1), ältere Versionen nie –
ihre Nummern sind je Instanz eigene. Kein Journal und nichts Journalähnliches: keine Konten, Namen, Bearbeitungszeiten.
Je Prüfpunkt seit Schritt 39 auch „untergruppe“ (leer = keine); eine ältere Datei ohne das Feld liest der Import als leer.

Eine Datei, die der Import nicht annähme (größer als seine Grenze, importer.BILD_MAX_IMPORT bzw. DOK_MAX_BYTES), bleibt
draußen und steht im Bericht unter „zu_gross“ – sonst stünde der ganze Import.

Bestandteil-Liste (Schritt 25): als „bestandteile“: [{bezeichnung, anzahl}]; ohne Liste fehlt der Schlüssel. „set“
schreibt der Export nie (die Set-Funktion ist seit Schritt 26 zurückgebaut).

„formular_von“ (Schritt 35/36) schreibt der Export seit dem Formular-Pool nicht mehr – das ist jetzt eine Zuweisung.
"""
import hashlib
import json
import os
import zipfile
from datetime import datetime

from flask import current_app

from ... import db
from ...images import ALLOWED_EXT
from . import ZONE, Abgelehnt, importer, katalog, stueckliste

EXPORT_MAX_BYTES = importer.ZIP_MAX_BYTES
# Bilder und Dokumente gehen ungepackt ins Archiv: Sie packen sich kaum, und so bleibt jeder Eintrag weit unter der
# Grenze, die der Import für das Packverhältnis setzt.
_UNGEPACKT = zipfile.ZIP_STORED


def _summe(pfad):
    summe = hashlib.sha256()
    with open(pfad, "rb") as fh:
        for stueck in iter(lambda: fh.read(1024 * 1024), b""):
            summe.update(stueck)
    return summe.hexdigest()


def _punkt(p):
    return {"gruppe": p["group_name"], "untergruppe": p["untergruppe"], "text": p["label"], "art": p["editor"],
            "pflicht": bool(p["mandatory"]), "soll": p["expected_value"]}


def sammeln(mit_dateien=True):
    """Der Katalog dieser Instanz ohne DEMO: (daten, dateien, bericht). daten wird katalog.json, dateien ist
    {Pfad im Archiv: Datei hier}, bericht zählt, was drin ist und was ausgelassen wurde. Ohne mit_dateien (Vorschau)
    werden die Produktbilder nicht gelesen – ihre Verweise fehlen dann, Zahlen und Größe stimmen."""
    medien = os.path.realpath(katalog.medien_dir())
    kats = db.query("SELECT * FROM mat_category ORDER BY position, name COLLATE NOCASE, id")
    # Kategorien, die nicht mitkommen: jede mit DEMO-Kennzeichen samt ihrem ganzen Teilbaum (die DEMO-Regel des Katalogs,
    # katalog.demo_kategorien – dieselbe für die Übung der Einführung und „Prüfformular übernehmen“).
    raus = katalog.demo_kategorien()
    nach_id = {k["id"]: k for k in kats}
    kinder = {}
    for k in kats:
        kinder.setdefault(k["parent_id"], []).append(k)
    bericht = {"erstellt": datetime.now(ZONE).isoformat(timespec="seconds"), "quelle": current_app.config["BASE_URL"],
               "enthalten": {"kategorien": 0, "produkte": 0, "bilder": 0, "formulare": 0, "dokumente": 0},
               "ausgelassen": {"kategorien": 0, "produkte": 0, "formulare": 0, "dokumente": 0, "ohne_kennzeichen": 0,
                               "namen": []},
               "ohne_aktive": 0, "fehlende_dateien": [], "zu_gross": [], "formular_liste": [], "groesse": 0,
               "grenze": EXPORT_MAX_BYTES}
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
                 "position": k["position"], "artikel_laenge": bool(k["items_have_length"])}
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
        if katalog.produkt_ist_demo(p, raus):
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
        flach = stueckliste.kurzliste(p["id"])
        if flach:
            e["bestandteile"] = [{"bezeichnung": z["bezeichnung"], "anzahl": z["anzahl"]} for z in flach]
        produkte.append(e)
    bericht["enthalten"]["produkte"] = len(produkte)

    # Prüfformulare: je Formular des Pools mit aktiver Version (E1) und Heimat im Export.
    kat_angabe = {k["id"]: {"kategorie": pfad(k["id"]), "kategorie_uid": k["uid"]} for k in reihe}
    prod_angabe = {p["id"]: {"uid": p["uid"], "hersteller": p["manufacturer"], "modell": p["model"],
                             "artikelnummer": p["article_no"]} for p in exportiert}
    zuweisungen = {}
    for z in db.query("SELECT * FROM mat_formular_zuweisung ORDER BY id"):
        zuweisungen.setdefault(z["formular_id"], []).append(z)
    formular_liste = []
    for r in db.query("SELECT f.*, v.id AS version_id, v.title, v.demo AS version_demo FROM mat_formular f "
                      "LEFT JOIN mat_form v ON v.formular_id = f.id AND v.active = 1 ORDER BY f.id"):
        if r["category_id"] in raus:
            raus_n["formulare"] += 1
            raus_n["ohne_kennzeichen"] += 0 if r["demo"] else 1
            continue
        if not r["version_id"]:
            bericht["ohne_aktive"] += 1
            continue
        if r["category_id"] not in kat_angabe:
            continue                                # Heimat ohne Pfad (sollte es nicht geben)
        liste = zuweisungen.get(r["id"], [])
        punkte = [_punkt(x) for x in katalog.punkte(r["version_id"])]
        formular_liste.append(dict(kat_angabe[r["category_id"]], uid=r["uid"], titel=r["title"], punkte=punkte,
                                   standard_fuer=[kat_angabe[z["category_id"]] for z in liste
                                                  if z["category_id"] in kat_angabe],
                                   zugewiesen=[prod_angabe[z["product_id"]] for z in liste
                                               if z["product_id"] in prod_angabe]))
        bericht["formular_liste"].append({
            "titel": r["title"], "heimat": " / ".join(pfad(r["category_id"])), "demo": bool(r["version_demo"]),
            "platzhalter": any("platzhalter" in (p["text"] or "").casefold() for p in punkte),
            "standard_fuer": len(formular_liste[-1]["standard_fuer"]), "zugewiesen": len(formular_liste[-1]["zugewiesen"])})
    bericht["enthalten"]["formulare"] = len(formular_liste)
    raus_n["namen"] = raus_n["namen"][:50]

    daten = {"format": importer.FORMAT, "version": 3, "quelle": bericht["quelle"], "erstellt": bericht["erstellt"],
             "kategorien": kategorien, "produkte": produkte, "formulare": formular_liste}
    return daten, dateien, bericht


def bericht_text(b):
    """bericht.txt im Archiv: für Menschen, nicht für den Import."""
    e, a = b["enthalten"], b["ausgelassen"]
    zeilen = ["Katalog-Export – Materialablage", f"Quelle:   {b['quelle']}", f"Erstellt: {b['erstellt']}",
              f"Format:   {importer.FORMAT}, Version 3", "",
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
    if b["formular_liste"]:
        zeilen += ["", "Prüfformulare im Export (je die aktive Version – der Import macht sie aktiv, ohne DEMO):"]
        for f in b["formular_liste"]:
            marken = [m for m, ja in (("auf dieser Instanz DEMO", f["demo"]), ("Platzhalter", f["platzhalter"])) if ja]
            wo = [w for w in (f"Standard für {f['standard_fuer']} Kategorie{'n' if f['standard_fuer'] != 1 else ''}"
                              if f["standard_fuer"] else "",
                              f"{f['zugewiesen']} Produkt{'en' if f['zugewiesen'] != 1 else ''} zugewiesen"
                              if f["zugewiesen"] else "") if w]
            zeilen.append(f"  „{f['titel']}“ – {f['heimat']}{' – ' + ', '.join(wo) if wo else ''}"
                          f"{' [' + ', '.join(marken) + ']' if marken else ''}")
    if b["ohne_aktive"]:
        zeilen += ["", f"Nicht im Export: {b['ohne_aktive']} Prüfformulare ohne aktive Version."]
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
