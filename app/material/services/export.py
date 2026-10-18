"""Export eines Ordners (Lieferung 4; Konzept: „Export – CSV je Ordner, ZIP aller Protokolle, Lebenslauf-PDF je
Artikel – Datenhoheit und Umzugsfähigkeit“). Das Lebenslauf-PDF steht in lebenslauf.py.

Welche Artikel zu einem Ordner gehören, ist für CSV und ZIP dasselbe (menge()): alle, deren Heimat (bestand.heimat)
im Ordner oder darunter liegt – wie beim Eröffnen eines Prüfdurchgangs. Gesperrte, verlorene und seit Phase 2 auch
ausgesonderte zählen also bei ihrem Herkunftsordner, auch wenn sie in „Gesperrt“ oder „Ausgesondert“ liegen;
Ausgesonderte ohne Herkunft (vor Schritt 8 ausgesondert, Herkunftsordner gelöscht) gehören zur Gliederung. Protokolle
wandern mit dem Artikel: Im ZIP stehen die Protokolle der Artikel, die heute zum Ordner gehören, dazu die
Sammelprotokolle der Durchgänge, die für den Ordner oder einen seiner Unterordner eröffnet wurden. Exportieren darf nur,
wer das Grundrecht am Ordner hat (routes_export) – damit sieht er alles, was dazu gehört, auch die Spalte
„Zugeordnet an“.

CSV: Trennzeichen „;“, UTF-8 mit BOM, Zeilenende CRLF – so öffnet Excel die Datei mit Umlauten richtig. Datumswerte
deutsch (TT.MM.JJJJ, Monatsangaben MM/JJJJ). Ein Wert, der mit = + - @ Tabulator oder Wagenrücklauf beginnt, bekommt
ein ' vorangestellt; sonst nähme eine Tabellenkalkulation ihn als Formel (Formel-Injektion über Seriennummer,
Bemerkung, Sperrgrund oder Ordnernamen).

ZIP: Jede Protokolldatei geht durch protokoll.datei() – hinein kommt nur, was noch genau die festgeschriebene Datei
ist. Fehlt eine oder ist sie verändert, bricht der Export nicht ab: Ihre Zeile in Verzeichnis.csv sagt „fehlt“ bzw.
„verändert“, das Protokoll der App nennt die Datei. Gepackt wird ohne Kompression (PDFs sind schon komprimiert) in
eine temporäre Datei unter TMP_DIR – wie beim Wiki-Export – und höchstens ZIP_MAX_BYTES."""
import csv
import io
import os
import re
import tempfile
import zipfile
from datetime import datetime

from flask import current_app

from ... import db
from ..models import ERGEBNISSE, MATERIALARTEN
from . import ZONE, Abgelehnt, bestand, heute, protokoll
from . import status as st
from .faelligkeit import im_unterbaum
from .interval import wirksam
from .protokoll import PRUEFART_TEXT, datum_text, zeit_text

# Mehr packt der ZIP-Export nicht ein – wie EXPORT_MAX_BYTES im Wiki.
ZIP_MAX_BYTES = 2 * 1024 ** 3
FORMEL_ANFANG = ("=", "+", "-", "@", "\t", "\r")
SPERRZUSTAND = {"frei": "frei", "gesperrt": "gesperrt", "verloren": "verloren", "ausgesondert": "ausgesondert"}

ARTIKEL_SPALTEN = (
    "Inventarnummer", "Seriennummer", "Seriennummer vom System", "Hersteller", "Modell", "Artikelnummer", "Kategorie",
    "Norm", "Materialart", "Ordner", "Gliederung", "Status", "Sperrzustand", "Sperr-/Aussonderungsgrund",
    "Herkunftsordner", "zuletzt geprüft", "nächste Prüfung", "Prüfintervall wirksam (Monate)", "hergestellt",
    "gekauft", "Erstgebrauch", "Lebensende", "Bemerkung", "in Prüfung bei", "Zugeordnet an", "DEMO")
VERZEICHNIS_SPALTEN = (
    "Protokoll-ID", "Art", "Prüfart", "Datum", "festgeschrieben", "Inventarnummer", "Seriennummer", "Produkt",
    "Prüfdurchgang", "Prüfer", "Urkundennummer", "Ergebnis", "Grund", "Datei im ZIP", "SHA-256 der Datei",
    "SHA-256 der ersten N Bytes", "N (Bytes)", "Zustand", "berichtigt durch", "Berichtigung von", "DEMO")

# Mit dem offenen Entwurf (höchstens einer je Artikel) für „in Prüfung bei“ und der zugeordneten Person (Name, immer
# der aktuelle Stand); die Spalten des Produkts, die das wirksame Intervall braucht, unter eigenem Namen (i.* hat selbst
# ein interval_months).
ARTIKEL_SQL = ("SELECT i.*, p.manufacturer, p.model, p.article_no, p.norm, p.material_kind, p.category_id, "
               f"p.interval_months AS p_int, {bestand.demo_sql('i', 'p')} AS artikel_demo, "
               "e.inspector_name AS entwurf_pruefer, "
               "zu.name AS zugeordnet_name FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
               "LEFT JOIN mat_inspection e ON e.item_id = i.id AND e.completed_at IS NULL "
               "LEFT JOIN users zu ON zu.id = i.assigned_user_id ")
# Ohne signature_png: Die Unterschrift steckt schon im Protokoll, und tausend Kopien bräuchte hier niemand.
PRUEFUNG_SQL = ("SELECT x.id, x.item_id, x.round_id, x.protocol_id, x.inspector_name, x.inspector_certificate, "
                "x.inspected_on, x.kind, x.result, x.reason, x.corrects_inspection_id, x.completed_at, x.locked_at, "
                "x.pdf_path, x.pdf_sha256, x.pdf_hashed_bytes, x.file_sha256, i.inventory_no, i.serial_no, "
                f"p.manufacturer, p.model, {bestand.demo_sql('i', 'p')} AS artikel_demo, r.title AS durchgang "
                "FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id JOIN mat_product p ON p.id = i.product_id "
                "LEFT JOIN mat_round r ON r.id = x.round_id ")


def dateiname(text):
    """Teil eines Dateinamens aus Ordnername oder Nummer – ohne Pfadtrenner und Sonderzeichen (wie _export_name im
    Wiki). Umlaute bleiben; send_file(download_name=…) schreibt sie RFC-5987-kodiert in die Kopfzeile."""
    name = re.sub(r"[^\w .\-]+", "_", text or "", flags=re.UNICODE).strip(" .") or "Export"
    return name[:120]


def _zelle(wert):
    """Ein CSV-Wert als Text; was eine Tabellenkalkulation als Formel läse, mit vorangestelltem '."""
    if wert is None:
        return ""
    s = str(wert)
    return "'" + s if s.startswith(FORMEL_ANFANG) else s


def csv_bytes(kopf, zeilen):
    """Zeilen als CSV für Excel: „;“, CRLF, UTF-8 mit BOM, jeder Wert durch _zelle()."""
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    schreiber.writerow(kopf)
    for z in zeilen:
        schreiber.writerow([_zelle(w) for w in z])
    return puffer.getvalue().encode("utf-8-sig")


def menge(fid):
    """SQL-Bedingung (über i = mat_item) und Parameter: die Artikel, die zum Ordner fid gehören (siehe oben) – dieselbe
    Regel wie durchgang.eroeffnen, dort ohne Ausgesonderte."""
    return bestand.heimat_im_zweig(fid)


def _ketten(alle):
    """{Kennung: [Zeilen von der Wurzel bis hierher]} für eine Tabelle mit parent_id, ohne weitere Abfrage. Ein
    Zyklus (den es nicht geben darf) bricht ab, statt endlos zu laufen."""
    out = {}
    for start in alle:
        kette, x, gesehen = [], start, set()
        while x in alle and x not in gesehen:
            gesehen.add(x)
            kette.insert(0, alle[x])
            x = alle[x]["parent_id"]
        out[start] = kette
    return out


def _ordnerbaum():
    """Alle Ordner auf einmal: je Kennung Pfad, Gliederung und Platz in der Baumreihenfolge (wie in der Oberfläche,
    Systemordner zuletzt) – eine Abfrage statt einer je Zeile und Ebene (bestand.pfad)."""
    alle = {o["id"]: o for o in db.query("SELECT id, parent_id, name, kind, system_kind, position FROM mat_folder")}
    out = {}
    for fid, kette in _ketten(alle).items():
        gl = next((o for o in reversed(kette) if o["kind"] == "gliederung" and not o["system_kind"]), None)
        out[fid] = {"pfad": " / ".join(o["name"] for o in kette), "gliederung": gl["name"] if gl else "",
                    "reihe": [(o["system_kind"] is not None, o["position"], o["name"].casefold(), o["id"]) for o in kette]}
    return out


def _kategoriepfade():
    alle = {k["id"]: k for k in db.query("SELECT id, parent_id, name FROM mat_category")}
    return {kid: " / ".join(k["name"] for k in kette) for kid, kette in _ketten(alle).items()}


# --- CSV je Ordner ----------------------------------------------------------------------------------------------

def artikel_csv(fid):
    """(CSV als bytes, Dateiname): die Artikel des Ordners fid samt Unterordnern, in Baumreihenfolge, je Ordner nach
    Inventarnummer. Status wie überall aus status.status() – abgeleitet, nie gespeichert."""
    o = bestand.ordner(fid)
    bedingung, args = menge(fid)
    rows = db.query(ARTIKEL_SQL + f"WHERE {bedingung}", args)
    baum, kategorien = _ordnerbaum(), _kategoriepfade()
    ohne = {"pfad": "", "gliederung": "", "reihe": []}
    rows.sort(key=lambda r: (baum.get(r["folder_id"], ohne)["reihe"], r["inventory_no"]))
    stichtag, schwelle = heute(), st.schwelle_tage()
    intervalle = {}
    zeilen = []
    for r in rows:
        s = st.status(r, stichtag, schwelle)
        intervall = None
        if r["lock_state"] != "ausgesondert":
            # Gesperrte liegen in „Gesperrt“; ihr Intervall kommt aus der Heimat (wie bei der Freiprüfung).
            heimat = bestand.heimat(r)
            schluessel = (r["product_id"], heimat, r["interval_months"])
            if schluessel not in intervalle:
                intervalle[schluessel] = wirksam({"interval_months": r["p_int"], "category_id": r["category_id"]},
                                                 heimat, r["interval_months"])["monate"]
            intervall = intervalle[schluessel]
        ordner = baum.get(r["folder_id"], ohne)
        zeilen.append([
            r["inventory_no"], r["serial_no"], "ja" if r["serial_generated"] else "nein", r["manufacturer"], r["model"],
            r["article_no"], kategorien.get(r["category_id"], ""), r["norm"],
            MATERIALARTEN.get(r["material_kind"], r["material_kind"]), ordner["pfad"], ordner["gliederung"], st.LABEL[s],
            SPERRZUSTAND.get(r["lock_state"], r["lock_state"]), r["lock_reason"],
            baum.get(r["origin_folder_id"], ohne)["pfad"] if r["origin_folder_id"] else "",
            datum_text(r["last_inspected_on"]), datum_text(r["next_due_on"]), intervall,
            datum_text(r["manufactured_on"]), datum_text(r["purchased_on"]), datum_text(r["first_use_on"]),
            datum_text(r["retire_by"]) if r["material_kind"] == "textil" else "", r["notes"], r["entwurf_pruefer"],
            ((r["zugeordnet_name"] or "").strip() or "(ohne Namen)") if r["assigned_user_id"] else "",
            "ja" if r["artikel_demo"] else "nein"])
    return csv_bytes(ARTIKEL_SPALTEN, zeilen), f"Artikel_{dateiname(o['name'])}_{stichtag.isoformat()}.csv"


# --- ZIP aller Protokolle -----------------------------------------------------------------------------------------

def _datei_pruefen(row):
    """(Pfad oder None, Zustand) einer Protokolldatei – über protokoll.datei(), also gegen die Prüfsumme."""
    if not row.get("locked_at") or not row.get("pdf_path"):
        return None, "ohne Protokoll"
    try:
        return protokoll.datei(row), "unverändert"
    except Abgelehnt as exc:
        return None, "verändert" if exc.code == 409 else "fehlt"


def _im_zip(ordner, row, inventarnummer=None):
    """Protokolle/<Jahr>/P-2026-000123_M-000042.pdf – das Jahr ist das des Festschreibens, wie unter DATA_DIR/pdf."""
    return f"{ordner}/{row['protocol_id'].split('-')[1]}/{protokoll.dateiname(row, inventarnummer)}"


def _groesse_text(n):
    return f"{n // 1024 ** 3} GB" if n >= 1024 ** 3 else f"{max(1, n // 1024 ** 2)} MB"


def protokolle_zip(fid):
    """(offene temporäre Datei mit dem ZIP, Dateiname, Zahlen): alle festgeschriebenen Prüf- und
    Aussonderungsprotokolle der Artikel des Ordners – auch berichtigte Originale samt ihrer Berichtigung –, die
    Sammelprotokolle der Durchgänge im Zweig und Verzeichnis.csv mit einer Zeile je Vorgang. Abgeschlossene Vorgänge
    ohne Protokoll (vor Lieferung 3) stehen im Verzeichnis als „ohne Protokoll“. Ein leerer Ordner ergibt ein ZIP, in
    dem nur das Verzeichnis (mit Kopfzeile) liegt."""
    o = bestand.ordner(fid)
    bedingung, args = menge(fid)
    pruefungen = db.query(PRUEFUNG_SQL + f"WHERE x.completed_at IS NOT NULL AND {bedingung} ORDER BY x.inspected_on, x.id",
                          args)
    zweig, zargs = im_unterbaum(fid)
    runden = db.query(
        "SELECT r.id, r.folder_id, r.title, r.closed_on, r.closed_by_name, r.aborted, r.protocol_id, r.locked_at, "
        "r.pdf_path, r.pdf_sha256, r.pdf_hashed_bytes, r.file_sha256, "
        f"{bestand.demo_ordner_sql('r.folder_id')} AS ordner_demo "
        "FROM mat_round r JOIN mat_folder o ON o.id = r.folder_id "
        f"WHERE r.closed_on IS NOT NULL AND {zweig.replace('i.folder_id IN', 'r.folder_id IN', 1)} "
        "ORDER BY r.closed_on, r.id", zargs)
    protokoll_von = {x["id"]: x["protocol_id"] or "(ohne Protokoll)" for x in pruefungen}
    berichtigt_durch = {x["corrects_inspection_id"]: protokoll_von[x["id"]] for x in pruefungen if x["corrects_inspection_id"]}
    zeilen, dateien, gesamt = [], [], 0
    zaehler = {"unverändert": 0, "fehlt": 0, "verändert": 0, "ohne Protokoll": 0}

    def aufnehmen(row, ordner, inventarnummer=None):
        nonlocal gesamt
        pfad, zustand = _datei_pruefen(row)
        zaehler[zustand] += 1
        if not pfad:
            return "", zustand
        gesamt += os.path.getsize(pfad)
        if gesamt > ZIP_MAX_BYTES:
            raise Abgelehnt(f"Der Export wäre größer als {_groesse_text(ZIP_MAX_BYTES)}. Bitte die Unterordner "
                            "einzeln exportieren.", 413)
        name = _im_zip(ordner, row, inventarnummer)
        dateien.append((pfad, name))
        return name, zustand

    for x in pruefungen:
        name, zustand = aufnehmen(x, "Protokolle", x["inventory_no"])
        zeilen.append([
            x["protocol_id"], "Aussonderungsprotokoll" if x["kind"] == "aussonderung" else "Prüfprotokoll",
            PRUEFART_TEXT.get(x["kind"], x["kind"]), datum_text(x["inspected_on"]), zeit_text(x["locked_at"]),
            x["inventory_no"], x["serial_no"], f"{x['manufacturer']} {x['model']}".strip(), x["durchgang"],
            x["inspector_name"], x["inspector_certificate"], ERGEBNISSE.get(x["result"], x["result"]), x["reason"], name,
            x["file_sha256"], x["pdf_sha256"], x["pdf_hashed_bytes"], zustand, berichtigt_durch.get(x["id"], ""),
            protokoll_von.get(x["corrects_inspection_id"], "(ohne Protokoll)") if x["corrects_inspection_id"] else "",
            "ja" if x["artikel_demo"] else "nein"])
    for r in runden:
        name, zustand = aufnehmen(r, "Sammelprotokolle")
        zeilen.append([
            r["protocol_id"], "Sammelprotokoll", "", datum_text(r["closed_on"]), zeit_text(r["locked_at"]), "", "", "",
            r["title"], r["closed_by_name"], "", "abgebrochen" if r["aborted"] else "abgeschlossen", "", name,
            r["file_sha256"], r["pdf_sha256"], r["pdf_hashed_bytes"], zustand, "", "", "ja" if r["ordner_demo"] else "nein"])
    if zaehler["fehlt"] or zaehler["verändert"]:
        # Welche Dateien, steht schon im Protokoll der App (protokoll.datei); hier die Zusammenfassung des Exports.
        current_app.logger.warning("Protokoll-Export Ordner %s: %d Protokolldateien fehlen, %d sind verändert – im "
                                   "Verzeichnis vermerkt", fid, zaehler["fehlt"], zaehler["verändert"])
    buf = tempfile.TemporaryFile(dir=current_app.config["TMP_DIR"])
    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            info = zipfile.ZipInfo("Verzeichnis.csv", date_time=datetime.now(ZONE).timetuple()[:6])
            z.writestr(info, csv_bytes(VERZEICHNIS_SPALTEN, zeilen))
            for pfad, name in dateien:
                z.write(pfad, name)
    except BaseException:
        buf.close()
        raise
    buf.seek(0)
    return buf, f"Protokolle_{dateiname(o['name'])}_{heute().isoformat()}.zip", zaehler
