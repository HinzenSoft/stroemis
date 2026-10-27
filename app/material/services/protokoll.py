"""Protokolle als PDF: Prüfprotokoll, Aussonderungsprotokoll und Sammelprotokoll eines Prüfdurchgangs –
festgeschrieben und mit aufgedruckter Prüfsumme (Konzept „PDF-Prüfprotokoll“, Lieferung 3).

Ablauf beim Festschreiben, in der Schreibtransaktion des Vorgangs: Die Daten kommen aus der Datenbank, wie
sie in dieser Transaktion stehen; WeasyPrint rendert sie (pdf.py), angehängte PDFs kommen hinten dazu,
SHA-256 geht über diese N Bytes, und ein inkrementelles Update setzt den Stempel auf jede Seite
(stempel.py). Die Datei liegt danach unter DATA_DIR/pdf/<jahr>/<protokoll-id>.pdf – im Datenvolumen, damit
sie mit der Sicherung wandert –, schreibgeschützt und nie überschrieben. In der Datenbank stehen
pdf_sha256 (aufgedruckter Wert), pdf_hashed_bytes (N) und file_sha256 (die ganze Datei mit Stempel).

Protokoll-IDs: P-<jahr>-<nr> (Prüfung), A-<jahr>-<nr> (Aussonderung), S-<jahr>-<nr> (Sammelprotokoll), seit Schritt
27 T-<jahr>-<nr> (Set-Protokoll eines Set-Ordners im Durchgang); die Nummer ist die Kennung der Prüfung, des
Durchgangs bzw. der Zeile in mat_round_setprotokoll (AUTOINCREMENT, nie zweimal vergeben), das Jahr das des
Festschreibens. Die Lücken zwischen den Nummern sind verworfene Entwürfe, keine fehlenden Protokolle.

Scheitert die Transaktion nach dem Schreiben einer Datei, löscht dateien_sichern() sie wieder – sonst
lägen PDFs ohne Datenbankzeile herum.

Ein Durchgang schreibt seit der Prüfung vom 25.10.2026 zweistufig fest (durchgang_auswahl, t_nummern_reservieren,
durchgang_vorbereiten, durchgang_rendern, durchgang_festschreiben): Sammel- und Set-Protokolle entstehen OHNE Schreibsperre unter Zwischennamen; unter der kurzen
Schreibsperre rechnet durchgang_festschreiben ihre Daten noch einmal aus und übernimmt die Dateien nur, wenn sie genau
gleich sind – sonst verwirft der Aufrufer sie und beginnt neu. Mit vielen Sets hielt das Rendern unter der Sperre die
ganze Plattform länger fest, als andere Anfragen warten (15 s, app/db.py)."""
import hashlib
import io
import json
import os
import secrets
from contextlib import contextmanager
from datetime import date, datetime
from flask import current_app, g
from pypdf import PdfReader

from ... import db
from ..models import ANHANGARTEN, DOKUMENTARTEN, ERGEBNISSE, MATERIALARTEN
from . import ZONE, Abgelehnt, bestand, journal, katalog, laenge_text, qr, stempel
VORSATZ = {"pruefprotokoll": "P", "aussonderungsprotokoll": "A", "sammelprotokoll": "S", "setprotokoll": "T"}
TITEL = {"pruefprotokoll": "Prüfprotokoll", "aussonderungsprotokoll": "Aussonderungsprotokoll",
         "sammelprotokoll": "Sammelprotokoll", "setprotokoll": "Set-Protokoll"}
PRUEFART_TEXT = {"eingang": "Eingangsprüfung", "periodisch": "periodische Prüfung",
                 "ausserplanmaessig": "außerplanmäßige Prüfung", "reparatur": "Prüfung nach Reparatur",
                 "aussonderung": "Aussonderung"}
BEFUND_TEXT = {"ok": "in Ordnung", "mangel": "Mangel", "nicht_zutreffend": "nicht zutreffend"}
PRUEFSEITE = "/materialablage/pruefen"


# --- Formatierung ---------------------------------------------------------------------------------------

def ortszeit(iso):
    """UTC-Zeitstempel der Datenbank → deutsche Ortszeit (Sommer- und Winterzeit)."""
    return datetime.fromisoformat(iso).astimezone(ZONE)


def zeit_text(iso):
    return ortszeit(iso).strftime("%d.%m.%Y, %H:%M Uhr") if iso else ""


def datum_text(s):
    """'2026-10-17' → '17.10.2026', '2021-03' → '03/2021', leer bleibt leer."""
    if not s:
        return ""
    try:
        if len(s) == 7:
            jahr, monat = s.split("-")
            return f"{monat}/{jahr}"
        return date.fromisoformat(s[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return s


def _pfad_text(fid):
    return " › ".join(o["name"] for o in bestand.pfad(fid)) if fid else ""


def protokoll_id(art, nummer, ts):
    """P-/A-/S-<jahr>-<nr>; liegt unter dieser ID schon eine Datei (nach dem Zurückspielen einer Sicherung kann ein
    Entwurf wieder offen sein, dessen Protokoll schon ausgehändigt wurde – seine Datei liegt in pdf/verwaist/), bekommt
    das neue Protokoll eine Folgenummer: P-2026-000007-2. Eine ID bezeichnet so nie zwei verschiedene Dateien."""
    jahr = ortszeit(ts).year
    basis = f"{VORSATZ[art]}-{jahr}-{nummer:06d}"
    pid, folge = basis, 1
    while _id_belegt(pid, jahr):
        folge += 1
        pid = f"{basis}-{folge}"
    return pid


def _id_belegt(pid, jahr):
    import re
    if os.path.exists(os.path.join(ablage(), str(jahr), pid + ".pdf")):
        return True
    verwaist = os.path.join(ablage(), "verwaist")
    muster = re.compile(re.escape(pid) + r"-\d{14}\.pdf")
    return os.path.isdir(verwaist) and any(muster.fullmatch(n) for n in os.listdir(verwaist))


def pruefseite():
    """Die Adresse der Prüfseite zum Abdrucken (mit lesbarem Hostnamen)."""
    return qr.anzeige(qr.basis()) + PRUEFSEITE


def stempel_zeilen(n, summe, pid):
    return [stempel.stempel_text(n, summe),
            f"{pid} · nachrechnen: head -c {n} datei.pdf | sha256sum · prüfen: {pruefseite()}"]


# --- Ablage --------------------------------------------------------------------------------------------

def ablage():
    return os.path.join(current_app.config["DATA_DIR"], "pdf")


def voller_pfad(rel):
    """pdf_path (relativ zu DATA_DIR, „pdf/2026/P-2026-000123.pdf“) → Pfad im Dateisystem – nur innerhalb von
    DATA_DIR/pdf."""
    wurzel = os.path.realpath(ablage())
    pfad = os.path.realpath(os.path.join(current_app.config["DATA_DIR"], rel or ""))
    if not pfad.startswith(wurzel + os.sep):
        raise Abgelehnt("Ungültiger Protokollpfad.", 404)
    return pfad


@contextmanager
def dateien_sichern():
    """Rahmen um eine Schreibtransaktion, in der Protokolle entstehen. Scheitert sie (auch noch beim Commit),
    werden die neuen Dateien wieder gelöscht. Verschachtelt räumt der äußere Rahmen auf. Gehört AUSSEN um
    db.transaction: with protokoll.dateien_sichern(), db.transaction(sofort=True): …"""
    if g.get("mat_pdf_neu") is not None:
        yield
        return
    g.mat_pdf_neu = []
    try:
        yield
    except BaseException:
        for pfad in g.mat_pdf_neu:
            try:
                os.chmod(pfad, 0o644)
                os.remove(pfad)
            except OSError:
                pass
        raise
    finally:
        g.mat_pdf_neu = None


def verwaiste_beiseite(conn):
    """Beim Start: Protokolldateien, auf die keine Zeile verweist, nach pdf/verwaist/ verschieben (nicht löschen),
    und die Zähler der Kennungen über jede vorhandene Protokollnummer heben (_nummern_schuetzen).
    Das bleibt nur übrig, wenn ein Prozess zwischen dem Schreiben der Datei und dem Commit abbrach – etwa ein
    unterschriebenes Aussonderungsprotokoll zu einer Aussonderung, die es nie gab. Unter der Schreibsperre: Wer
    gerade festschreibt, hält sie, seine noch nicht bestätigte Datei kann hier also nicht dabei sein. Zwischendateien
    eines abgebrochenen zweistufigen Abschlusses (zwischendateien) löscht er, wenn sie älter als ZWISCHEN_ALT_S sind –
    jüngere können zu einem Abschluss gehören, der in einem anderen Arbeitsprozess gerade rendert."""
    import logging
    import re
    pfad = conn.execute("PRAGMA database_list").fetchone()[2]
    wurzel = os.path.join(os.path.dirname(pfad or ""), "pdf")
    if not pfad or not os.path.isdir(wurzel):
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        bekannt = {r[0] for r in conn.execute("SELECT pdf_path FROM mat_inspection WHERE pdf_path IS NOT NULL "
                                              "UNION SELECT pdf_path FROM mat_round WHERE pdf_path IS NOT NULL")}
        if _tabelle_da(conn, "mat_round_setprotokoll"):
            bekannt |= {r[0] for r in conn.execute("SELECT pdf_path FROM mat_round_setprotokoll")}
        _nummern_schuetzen(conn, wurzel)
        for jahr in sorted(os.listdir(wurzel)):
            if not re.fullmatch(r"\d{4}", jahr) or not os.path.isdir(os.path.join(wurzel, jahr)):
                continue
            for name in sorted(os.listdir(os.path.join(wurzel, jahr))):
                if name.startswith(".") and name.endswith(ZWISCHEN_ENDUNG):
                    zwischen = os.path.join(wurzel, jahr, name)
                    try:
                        if datetime.now().timestamp() - os.path.getmtime(zwischen) > ZWISCHEN_ALT_S:
                            os.remove(zwischen)
                    except OSError:
                        pass
                    continue
                if not name.endswith(".pdf") or f"pdf/{jahr}/{name}" in bekannt:
                    continue
                ziel = os.path.join(wurzel, "verwaist")
                os.makedirs(ziel, exist_ok=True)
                os.replace(os.path.join(wurzel, jahr, name),
                           os.path.join(ziel, f"{name[:-4]}-{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"))
                logging.getLogger(__name__).warning("Protokolldatei ohne Datenbankzeile beiseitegelegt: pdf/%s/%s",
                                                    jahr, name)
        conn.commit()
    finally:
        if conn.in_transaction:
            conn.rollback()


def _nummern_schuetzen(conn, wurzel):
    """Keine Protokoll-ID zweimal: Liegt eine Datei mit höherer Nummer vor, als die Datenbank kennt (etwa nach dem
    Zurückspielen einer Sicherung, nach der noch festgeschrieben wurde), rückt der Zähler (sqlite_sequence) über sie
    hinaus – sonst bekäme die nächste Prüfung die ID eines schon ausgehändigten Protokolls."""
    import re
    hoechste = {"mat_inspection": 0, "mat_round": 0, "mat_round_setprotokoll": 0}
    tabelle_je = {"S": "mat_round", "T": "mat_round_setprotokoll"}
    for ordner, _, namen in os.walk(wurzel):
        for name in namen:
            m = re.match(r"([PAST])-\d{4}-(\d+)", name)
            if m:
                tabelle = tabelle_je.get(m.group(1), "mat_inspection")
                hoechste[tabelle] = max(hoechste[tabelle], int(m.group(2)))
    for tabelle, nr in hoechste.items():
        if not nr or not _tabelle_da(conn, tabelle):
            continue
        zeile = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (tabelle,)).fetchone()
        if zeile is None:
            conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (tabelle, nr))
        elif zeile[0] < nr:
            conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (nr, tabelle))


def _tabelle_da(conn, name):
    """Gibt es die Tabelle? Der Start läuft auch an Datenbanken älterer Stände (Tests mit bis_schritt)."""
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone())


def _ablegen(rel, daten):
    neu = g.get("mat_pdf_neu")
    if neu is None:
        raise RuntimeError("Protokolle entstehen nur innerhalb von dateien_sichern().")
    pfad = voller_pfad(rel)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    try:
        fh = open(pfad, "xb")
    except FileExistsError:
        # protokoll_id() vergibt keine ID, unter der schon eine Datei liegt – das hier ist ein Programmfehler.
        raise RuntimeError(f"Protokolldatei {rel} gibt es schon.")
    neu.append(pfad)
    with fh:
        fh.write(daten)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(pfad, 0o444)


ZWISCHEN_ENDUNG = ".teil"
# Zwischendateien, die so alt sind, gehören zu keinem laufenden Abschluss mehr (Gunicorn bricht eine Anfrage nach
# einer Stunde ab) – verwaiste_beiseite löscht sie beim Start.
ZWISCHEN_ALT_S = 24 * 60 * 60


@contextmanager
def zwischendateien():
    """Rahmen um das zweistufige Festschreiben eines Durchgangs: Was _zwischen_ablegen vor der Schreibtransaktion
    ablegt, liegt unter einem Zwischennamen neben seinem Ziel („.<ID>.<zufall>.teil“ – kein .pdf, also weder für
    verwaiste_beiseite noch für den Nummernschutz eine Protokolldatei). Am Ende verschwinden alle Zwischennamen; was
    _zwischen_uebernehmen unter der Sperre verlinkt hat, bleibt unter seinem endgültigen Namen (scheitert die
    Transaktion, löscht dateien_sichern auch den)."""
    if g.get("mat_pdf_zwischen") is not None:
        raise RuntimeError("zwischendateien() ist schon offen.")
    g.mat_pdf_zwischen = {}
    try:
        yield
    finally:
        for pfad in g.mat_pdf_zwischen.values():
            try:
                os.remove(pfad)          # ohne chmod: Der Link teilt sich die Rechte mit der übernommenen Datei.
            except OSError:
                pass
        g.mat_pdf_zwischen = None


def _zwischen_ablegen(rel, daten):
    zwischen = g.get("mat_pdf_zwischen")
    if zwischen is None:
        raise RuntimeError("Vorab gerenderte Protokolle liegen nur innerhalb von zwischendateien().")
    ziel = voller_pfad(rel)
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    pfad = os.path.join(os.path.dirname(ziel),
                        f".{os.path.basename(ziel)[:-4]}.{secrets.token_hex(8)}{ZWISCHEN_ENDUNG}")
    with open(pfad, "xb") as fh:
        zwischen[rel] = pfad
        fh.write(daten)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(pfad, 0o444)


def _zwischen_uebernehmen(rel):
    """Unter der Schreibsperre: die vorab gerenderte Datei unter ihrem endgültigen Namen – als harter Link, der nie eine
    vorhandene Datei überschreibt; ohne harte Links (fremdes Dateisystem) als Kopie wie _ablegen."""
    neu = g.get("mat_pdf_neu")
    if neu is None:
        raise RuntimeError("Protokolle entstehen nur innerhalb von dateien_sichern().")
    quelle, ziel = g.mat_pdf_zwischen[rel], voller_pfad(rel)
    try:
        os.link(quelle, ziel)
    except FileExistsError:
        raise RuntimeError(f"Protokolldatei {rel} gibt es schon.")
    except OSError:
        with open(quelle, "rb") as fh:
            _ablegen(rel, fh.read())
        return
    neu.append(ziel)


def _rendern(art, pid, daten, anhaenge=()):
    """Rendern, Anhänge anfügen, Prüfsumme, Stempel → (Dateiinhalt, Felder für die Datenbank); abgelegt wird hier noch
    nichts. Scheitert das Erzeugen, bricht der ganze Vorgang ab (die Prüfung bleibt Entwurf) – mit einer Meldung statt
    eines Serverfehlers."""
    from . import pdf
    try:
        basis = pdf.rendern(art, daten)
        eigene = len(PdfReader(io.BytesIO(basis)).pages)
        if anhaenge:
            inhalte = []
            for pfad in anhaenge:
                with open(pfad, "rb") as fh:
                    inhalte.append(fh.read())
            basis = stempel.anhaengen(basis, inhalte)
        n, summe = len(basis), stempel.sha256(basis)
        fertig = stempel.stempeln(basis, pdf.stempelvorlage(stempel_zeilen(n, summe, pid)), pid, eigene)
    except Abgelehnt:
        raise
    except Exception:
        current_app.logger.exception("Protokoll %s ließ sich nicht erzeugen", pid)
        raise Abgelehnt(f"Das Protokoll {pid} ließ sich nicht erzeugen – nichts wurde festgeschrieben. Liegt es an einem "
                        "angehängten PDF, dieses bitte entfernen und neu als PDF speichern oder fotografieren.", 500)
    jahr = pid.split("-")[1]
    return fertig, {"pdf_path": f"pdf/{jahr}/{pid}.pdf", "pdf_sha256": summe, "pdf_hashed_bytes": n,
                    "file_sha256": stempel.sha256(fertig)}


def _erzeugen(art, pid, daten, anhaenge=()):
    """Rendern und ablegen – in der Schreibtransaktion des Vorgangs → Felder für die Datenbank."""
    fertig, felder = _rendern(art, pid, daten, anhaenge)
    _ablegen(felder["pdf_path"], fertig)
    return felder


# --- Bausteine der Protokolldaten ------------------------------------------------------------------------

def _dokument(art, pid, ts, demo):
    return {"art": art, "titel": TITEL[art], "protokoll_id": pid, "festgeschrieben": zeit_text(ts),
            "plattform": qr.anzeige(qr.basis()).split("://", 1)[-1], "pruefseite": pruefseite(), "demo": bool(demo)}


def _bild(name, art="web", max_kante=1200):
    from . import pdf
    if not name:
        return None
    pfad = os.path.join(katalog.medien_dir(), art, os.path.splitext(name)[0] + ".jpg")
    return pdf.bild_daten_uri(pfad, max_kante)


def _png(png):
    from . import pdf
    return pdf.png_daten_uri(png) if png else None


def _artikel(item, produkt, ordner_id):
    from . import pdf
    kategorie = " › ".join(k["name"] for k in katalog.kategorie_pfad(produkt["category_id"]))
    gliederung = bestand.gliederung_von(ordner_id) if ordner_id else None
    url = qr.adresse(item["qr_token"])
    # Der Name mit der Beschreibung als Zusatz dahinter, ohne Strich und grau wie in der Oberfläche (basis.html, Makro
    # produkt_mit_zusatz) – erst in Protokollen ab dem 18.10.2026; festgeschriebene bleiben, wie sie sind. Das Feld
    # „Modell“ darunter ist das Modell ohne Zusatz – auch ohne einen von Hand hinter „|“ im Modellnamen
    # (katalog.modell_teile), der steht wie eine Beschreibung grau hinter dem Namen.
    name, zusatz = katalog.produkt_teile(produkt)
    return {"produkt_name": name, "produkt_zusatz": zusatz,
            "hersteller": produkt["manufacturer"], "modell": katalog.modell_teile(produkt["model"])[0],
            "artikelnummer": produkt["article_no"] or "", "kategorie": kategorie,
            "norm": produkt["norm"] or "", "materialart": MATERIALARTEN.get(produkt["material_kind"], ""),
            "seriennummer": item["serial_no"], "seriennummer_vergeben": bool(item["serial_generated"]),
            "inventarnummer": item["inventory_no"], "hergestellt": datum_text(item["manufactured_on"]),
            "gekauft": datum_text(item["purchased_on"]), "erstgebrauch": datum_text(item["first_use_on"]),
            "lebensende": datum_text(item["retire_by"]) if produkt["material_kind"] == "textil" else "",
            "laenge": laenge_text(item.get("length_m")),
            "gliederung": gliederung["name"] if gliederung else "", "ordner": _pfad_text(ordner_id),
            "bild": _bild(produkt["image"], max_kante=700), "qr_svg": pdf.qr_svg(url), "qr_url": qr.anzeige(url)}


def _laenge_m(text):
    """„57,5“ aus der Ergebniszeile → „57,5 m“; leer bleibt leer."""
    return f"{text.strip()} m" if (text or "").strip() else ""


def _wert_text(r):
    if r["editor"] == "yesno":
        return {"ja": "Ja", "nein": "Nein"}.get(r["value"], r["value"] or "")
    if r["editor"] == "date":
        return datum_text(r["value"])
    if r["editor"] == "laenge":
        # Längenpunkt (Schritt 20): „57,5 m → 55,0 m“ bei einer Änderung, sonst „57,5 m (unverändert)“ – das Soll ist
        # die Artikellänge vor dem Festschreiben (pruefung._laenge_uebernehmen).
        soll, wert = _laenge_m(r["expected_value"]), _laenge_m(r["value"])
        if r["finding"] == "nicht_zutreffend" or not wert:
            return ""
        if soll and soll != wert:
            return f"{soll} → {wert}"
        return f"{wert} (unverändert)" if soll else wert
    return r["value"] or ""


def _soll_text(r):
    if r["editor"] == "yesno":
        return {"ja": "Ja", "nein": "Nein"}.get(r["expected_value"], r["expected_value"] or "")
    if r["editor"] == "laenge":
        return _laenge_m(r["expected_value"])
    return r["expected_value"] or ""


def _nummern_text(r):
    """Seriennummern der Bestandteile an einer Zeile „… vorhanden“ (Schritt 25): je Stück mit Nummer „Seriennummer A1“
    bzw. „Seriennummer A1 → A2“ (vom Prüfer geändert; „–“ für keine) – bei mehr als einem Stück mit „Stück n:“ davor."""
    roh = r.get("component_serials")
    if not r.get("component_id") or not roh:
        return []
    serien = json.loads(roh)
    out = []
    for n, x in enumerate(serien, start=1):
        alt, neu = x.get("alt") or "", x.get("neu")
        if neu is not None and neu != alt:
            t = f"{alt or '–'} → {neu or '–'}"
        elif alt:
            t = alt
        else:
            continue
        out.append((f"Stück {n}: " if len(serien) > 1 else "") + "Seriennummer " + t)
    return out


def _befunde(pid):
    gruppen, fotos, maengel = [], [], 0
    for nr, r in enumerate(db.query("SELECT * FROM mat_inspection_result WHERE inspection_id = ? ORDER BY position, id",
                                    (pid,)), start=1):
        foto_nr = None
        if r["photo"]:
            bild = _bild(r["photo"])
            if bild:
                foto_nr = len(fotos) + 1
                fotos.append({"nr": foto_nr, "punkt_nr": nr, "punkt": r["checklist_text"], "notiz": r["note"] or "",
                              "bild": bild})
        if r["finding"] == "mangel":
            maengel += 1
        punkt = {"nr": nr, "text": r["checklist_text"], "art": r["editor"], "soll": _soll_text(r),
                 "kritisch": bool(r["is_critical"]), "pflicht": bool(r["mandatory"]), "befund": r["finding"] or "ok",
                 "befund_text": ("nicht unterschrieben" if r["editor"] == "signature" and r["finding"] == "ok"
                                 and not r["signature_png"] else BEFUND_TEXT.get(r["finding"], "")),
                 "wert": _wert_text(r), "notiz": r["note"] or "",
                 "foto_nr": foto_nr, "unterschrift": _png(r["signature_png"]), "nummern": _nummern_text(r)}
        if not gruppen or gruppen[-1]["name"] != (r["group_name"] or ""):
            gruppen.append({"name": r["group_name"] or "", "punkte": []})
        gruppen[-1]["punkte"].append(punkt)
    return gruppen, fotos, maengel


def _formular_text(p):
    if not p["form_id"]:
        return ""
    f = db.query("SELECT title, category_id, product_id FROM mat_form WHERE id = ?", (p["form_id"],), one=True)
    if not f:
        return ""
    art = "spezifisch für das Produkt" if f["product_id"] else "generisch für die Kategorie"
    return f"„{f['title']}“, Version {p['form_version']} ({art})"


def _lebensdauer_text(item, produkt, tag):
    if produkt["material_kind"] != "textil" or not item["retire_by"]:
        return ""
    rest = (date.fromisoformat(item["retire_by"]) - date.fromisoformat(tag)).days
    if rest <= 0:
        return f"Lebensende erreicht am {datum_text(item['retire_by'])}"
    return f"Lebensende {datum_text(item['retire_by'])} (noch {rest} Tage)"


def _folge(p, item):
    if p["result"] == "instandsetzen":
        return ("Der Artikel ist gesperrt und liegt im Ordner „Gesperrt“ seiner Gliederung, bis eine Prüfung mit "
                "dem Ergebnis „einsatzbereit“ (Freiprüfung) ihn freigibt.")
    if p["result"] == "aussondern_empfohlen":
        return ("Der Prüfer empfiehlt, den Artikel auszusondern. Er ist gesperrt und liegt im Ordner „Gesperrt“ seiner "
                "Gliederung; aussondern kann der Materialwart (eigener Vorgang mit Aussonderungsprotokoll).")
    if p["result"] == "aussondern":
        # Nur die Aussonderung dieses Artikels (bis Schritt 26 trugen mit ausgesonderte Teile eines Sets dieselbe Grundlage).
        a = db.query("SELECT protocol_id FROM mat_inspection WHERE basis_inspection_id = ? AND kind = 'aussonderung' "
                     "AND item_id = ?", (p["id"], p["item_id"]), one=True)
        nr = f" – siehe Aussonderungsprotokoll {a['protocol_id']}" if a and a["protocol_id"] else ""
        return f"Der Artikel ist ausgesondert und zählt nicht mehr zum Bestand{nr}."
    return ""


def _anhaenge(pid):
    liste, pfade = [], []
    for nr, a in enumerate(db.query("SELECT * FROM mat_inspection_attachment WHERE inspection_id = ? ORDER BY id",
                                    (pid,)), start=1):
        liste.append({"nr": nr, "titel": a["title"], "art": ANHANGARTEN.get(a["kind"], a["kind"]), "seiten": a["pages"],
                      "sha256": a["sha256"], "angefuegt": bool(a["in_pdf"]),
                      "hochgeladen": f"{datum_text(a['uploaded_at'][:10])} von {a['uploaded_by_name']}"})
        if a["in_pdf"]:
            pfade.append(os.path.join(katalog.medien_dir(), "anhang", a["file_path"]))
    return liste, pfade


def _dokumente(p):
    out = []
    for x in json.loads(p["documents_json"] or "[]"):
        out.append({"titel": x.get("title") or "", "art": DOKUMENTARTEN.get(x.get("kind"), x.get("kind") or ""),
                    "version": x.get("version") or "", "gueltig_ab": datum_text(x.get("valid_from")),
                    "sha256": x.get("sha256") or "",
                    "herkunft": f"Kategorie „{x['kategorie']}“" if x.get("kategorie") else "Produkt"})
    return out


def _unterschrift(p, png, login, ts):
    return {"bild": _png(png), "name": p["inspector_name"], "urkunde": p["inspector_certificate"], "login": login,
            "zeit": zeit_text(ts)}


def _pruefprotokoll(p, pid, ts, png, login, ordner_id):
    item = bestand.artikel(p["item_id"])
    produkt = katalog.produkt(item["product_id"])
    gruppen, fotos, maengel = _befunde(p["id"])
    anhaenge, pfade = _anhaenge(p["id"])
    durchgang = db.query("SELECT title FROM mat_round WHERE id = ?", (p["round_id"],), one=True) if p["round_id"] else None
    berichtigt = None
    if p["corrects_inspection_id"]:
        alt = db.query("SELECT protocol_id, inspected_on FROM mat_inspection WHERE id = ?",
                       (p["corrects_inspection_id"],), one=True)
        berichtigt = {"protokoll_id": alt["protocol_id"] or "(ohne Protokoll)", "datum": datum_text(alt["inspected_on"]),
                      "grund": p["correction_reason"]}
    daten = {
        "dokument": _dokument("pruefprotokoll", pid, ts, bestand.ist_demo(item["id"])),
        "artikel": _artikel(item, produkt, ordner_id),
        "pruefung": {"art": PRUEFART_TEXT.get(p["kind"], p["kind"]), "datum": datum_text(p["inspected_on"]),
                     "pruefer": p["inspector_name"], "urkunde": p["inspector_certificate"], "login": login,
                     "formular": _formular_text(p), "durchgang": durchgang["title"] if durchgang else "",
                     "grund": p["reason"] or "", "ergebnis": p["result"], "ergebnis_text": ERGEBNISSE.get(p["result"], ""),
                     # Die EN-365-Karte nennt immer die nächste Prüfung – ohne Fälligkeit steht da, warum.
                     "naechste": datum_text(p["next_due_on"]) or {
                         "instandsetzen": "entfällt – Artikel gesperrt; vor dem nächsten Einsatz Freiprüfung nötig",
                         "aussondern_empfohlen": "entfällt – Artikel gesperrt, Aussonderung empfohlen",
                         "aussondern": "entfällt – Artikel ausgesondert"}.get(p["result"], ""),
                     "lebensdauer": _lebensdauer_text(item, produkt, p["inspected_on"]),
                     "bemerkung": p["remarks"] or "", "folge": _folge(p, item), "berichtigt": berichtigt},
        "gruppen": gruppen, "maengel": maengel, "fotos": fotos, "dokumente": _dokumente(p), "anhaenge": anhaenge,
        "anhaenge_angefuegt": len(pfade), "unterschrift": _unterschrift(p, png, login, ts),
    }
    return daten, pfade


def _aussonderungsprotokoll(p, pid, ts, png, login, ordner_id, sperre):
    item = bestand.artikel(p["item_id"])
    produkt = katalog.produkt(item["product_id"])
    basis = None
    if p["basis_inspection_id"]:
        b = db.query("SELECT * FROM mat_inspection WHERE id = ?", (p["basis_inspection_id"],), one=True)
        basis = {"protokoll_id": protokoll_id("pruefprotokoll", b["id"], ts), "datum": datum_text(b["inspected_on"]),
                 "art": PRUEFART_TEXT.get(b["kind"], b["kind"]), "pruefer": b["inspector_name"]}
    letzte = db.query("SELECT * FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL AND kind <> 'aussonderung' "
                      "AND id IS NOT ? ORDER BY inspected_on DESC, id DESC LIMIT 1",
                      (p["item_id"], p["basis_inspection_id"]), one=True)
    letzte_pruefung = None
    if letzte:
        letzte_pruefung = {"protokoll_id": letzte["protocol_id"] or "", "datum": datum_text(letzte["inspected_on"]),
                           "art": PRUEFART_TEXT.get(letzte["kind"], letzte["kind"]),
                           "ergebnis_text": ERGEBNISSE.get(letzte["result"], ""), "pruefer": letzte["inspector_name"]}
    daten = {
        "dokument": _dokument("aussonderungsprotokoll", pid, ts, bestand.ist_demo(item["id"])),
        "artikel": _artikel(item, produkt, ordner_id),
        "aussonderung": {"datum": datum_text(p["inspected_on"]), "grund": p["reason"], "bemerkung": p["remarks"] or "",
                         "person": p["inspector_name"], "rolle": "Prüfer" if p["basis_inspection_id"] else "Materialwart",
                         "urkunde": p["inspector_certificate"] or "", "login": login,
                         "ordner_jetzt": _pfad_text(item["folder_id"]), "basis": basis, "sperre": sperre or "",
                         "letzte_pruefung": letzte_pruefung},
        "unterschrift": _unterschrift(p, png, login, ts),
    }
    return daten


# --- Festschreiben ------------------------------------------------------------------------------------

def pruefung_festschreiben(pruefung_id, ts, unterschrift, login, ordner_id, sperre=""):
    """Prüfung oder Aussonderung festschreiben: Protokoll erzeugen und mit Unterschrift, Anmeldung, Zeitpunkt
    und Prüfsummen in die Zeile schreiben. In der Schreibtransaktion des Abschlusses und innerhalb von
    dateien_sichern(). ordner_id: der Ordner des Artikels vor dem Vorgang (Sperre und Aussonderung verschieben
    ihn); sperre: Sperrvermerk vor einer Aussonderung. Liefert die Protokoll-ID."""
    p = db.query("SELECT * FROM mat_inspection WHERE id = ?", (pruefung_id,), one=True)
    if not p or not p["completed_at"] or p["locked_at"]:
        raise RuntimeError("Festschreiben nur einmal und erst nach dem Abschluss.")
    if not unterschrift:
        raise Abgelehnt("Zum Festschreiben fehlt die Unterschrift.", 403)
    if p["kind"] == "aussonderung":
        art = "aussonderungsprotokoll"
        pid = protokoll_id(art, p["id"], ts)
        daten, pfade = _aussonderungsprotokoll(p, pid, ts, unterschrift, login, ordner_id, sperre), []
    else:
        art = "pruefprotokoll"
        pid = protokoll_id(art, p["id"], ts)
        daten, pfade = _pruefprotokoll(p, pid, ts, unterschrift, login, ordner_id)
    felder = _erzeugen(art, pid, daten, pfade)
    db.execute("UPDATE mat_inspection SET protocol_id = ?, signature_png = ?, locked_login = ?, locked_at = ?, "
               "pdf_path = ?, pdf_sha256 = ?, pdf_hashed_bytes = ?, file_sha256 = ?, updated_at = ? WHERE id = ?",
               (pid, unterschrift, login or "", ts, felder["pdf_path"], felder["pdf_sha256"], felder["pdf_hashed_bytes"],
                felder["file_sha256"], ts, p["id"]))
    journal.eintragen("inspection", p["id"], "festgeschrieben", None,
                      {"protocol_id": pid, "pdf_sha256": felder["pdf_sha256"],
                       "pdf_hashed_bytes": felder["pdf_hashed_bytes"], "file_sha256": felder["file_sha256"],
                       "anhaenge_angefuegt": len(pfade), "login": login or ""})
    return pid


def _vormals(item_id, pruefung_id, aktuell, feld="serial_no"):
    """Der Wert (Seriennummer bzw. Produktkennung), den das Einzelprotokoll der Prüfung nennt, wenn ein bestätigter
    Änderungsantrag ihn danach ersetzt hat: (alter Wert, Antrag Nr.) oder None. „Danach“ heißt: Der Journaleintrag der
    Bestätigung steht nach dem Festschreiben der Prüfung (Journal-Kennungen sind streng steigend – genauer als
    Zeitstempel in Sekunden). Ohne Festschreiben (Prüfungen vor den PDF-Protokollen) zählt jeder Antrag, Anträge gibt es
    erst seit Schritt 15. Die Antrag-Nr. ist die des Sammelantrags (Kopf, Schritt 23)."""
    ab = db.query("SELECT MAX(id) AS m FROM mat_audit WHERE entity = 'inspection' AND entity_id = ? "
                  "AND action = 'festgeschrieben'", (pruefung_id,), one=True)["m"] or 0
    c = db.query("SELECT COALESCE(c.group_id, c.id) AS nr, c.old_value FROM mat_item_change c JOIN mat_audit a "
                 "ON a.entity = 'item' AND a.entity_id = c.item_id AND a.action = 'antrag_bestaetigt' "
                 "AND json_extract(a.after_json, '$.antrag') = COALESCE(c.group_id, c.id) "
                 "WHERE c.item_id = ? AND c.field = ? AND c.applied_at IS NOT NULL AND a.id > ? "
                 "ORDER BY a.id LIMIT 1", (item_id, feld, ab), one=True)
    return (c["old_value"], c["nr"]) if c and c["old_value"] != str(aktuell) else None


def _eintraege(r):
    """Die Zeilen des Sammelprotokolls eines Durchgangs – einmal je Festschreiben, für das Sammelprotokoll und alle
    Set-Protokolle. Die Ordnerspalte zeigt die Heimat eines Artikels nur, wenn sie im Zweig des Durchgangs liegt –
    sonst „aus dem Bereich verschoben“, nie einen Pfad aus einem fremden Bereich (1.7 Nr. 7). Die Seriennummer ist die
    heutige; hat ein Änderungsantrag sie nach dem Einzelprotokoll ersetzt, steht die alte als „vormals …
    (Änderungsantrag Nr. …)“ dabei – sonst widersprächen sich beide Dokumente ohne Verweis (Prüfung vom 21.10.2026).
    Intern dazu (mit „_“): die Kette der Ordner von der Gliederung bis zur Heimat (None außerhalb des Zweigs), Artikel
    und Prüfung."""
    from . import durchgang
    zeilen = durchgang._zeilen(r["id"])
    zweig, pfade = bestand.unterbaum(r["folder_id"]), {}
    artikel = {a["id"]: a for a in db.query(bestand.ARTIKEL_LISTE_SQL + "WHERE i.id IN (SELECT item_id FROM mat_round_item "
                                                                         "WHERE round_id = ?)", (r["id"],))}
    pruefungen = {x["id"]: x for x in db.query(
        "SELECT id, protocol_id, file_sha256, corrects_inspection_id, inspected_on, inspector_name, inspector_certificate "
        "FROM mat_inspection WHERE round_id = ? AND completed_at IS NOT NULL", (r["id"],))}
    ketten, liste = {}, []
    for z in zeilen:
        a = artikel.get(z["item_id"])
        if not a:
            continue
        zustand = durchgang._zustand(z, geschlossen=True)
        x = pruefungen.get(z["pruefung_id"]) if z["pruefung_id"] else None
        ausnahme = ""
        if z["excluded_reason"]:
            ausnahme = f"{z['excluded_reason']} ({z['excluded_by_name']}, {ortszeit(z['excluded_at']).strftime('%d.%m.%Y') if z['excluded_at'] else ''})"
        name, zusatz = katalog.produkt_teile(a, a["product_description"])
        vormals = _vormals(a["id"], x["id"], a["serial_no"]) if x else None
        produkt_vormals = _vormals(a["id"], x["id"], a["product_id"], "product_id") if x else None
        if produkt_vormals:
            p_alt = db.query("SELECT * FROM mat_product WHERE id = ?", (int(produkt_vormals[0]),), one=True)
            produkt_vormals = (katalog.produktname(p_alt) if p_alt else f"Produkt Nr. {produkt_vormals[0]}",
                               produkt_vormals[1])
        heimat = bestand.heimat(a)
        if heimat in zweig and heimat not in ketten:
            ketten[heimat] = bestand.pfad(heimat)
        liste.append({"inventarnummer": a["inventory_no"], "seriennummer": a["serial_no"],
                      "seriennummer_vormals": (f"vormals {vormals[0]} (Änderungsantrag Nr. {vormals[1]})"
                                               if vormals else ""),
                      "produkt_vormals": (f"vormals {produkt_vormals[0]} (Änderungsantrag Nr. {produkt_vormals[1]})"
                                          if produkt_vormals else ""),
                      "produkt_name": name, "produkt_zusatz": zusatz,
                      "ordner": durchgang.ordnerspalte(zweig, a, pfade, _pfad_text),
                      "zustand": zustand, "ergebnis": (z["ergebnis"] or "") if x else "",
                      "ergebnis_text": ERGEBNISSE.get(z["ergebnis"], "") if x else "",
                      "datum": datum_text(x["inspected_on"]) if x else "", "pruefer": x["inspector_name"] if x else "",
                      "urkunde": x["inspector_certificate"] if x else "", "protokoll_id": (x["protocol_id"] or "") if x else "",
                      "datei_sha256": (x["file_sha256"] or "") if x else "",
                      "berichtigung": bool(x and x["corrects_inspection_id"]), "ausnahme": ausnahme,
                      "_kette": ketten.get(heimat) if heimat in zweig else None, "_item": a["id"]})
    return liste


def _unter(e, wurzel):
    """Die Ordner unterhalb von wurzel auf dem Weg zur Heimat der Zeile – None, wenn die Heimat nicht darunter liegt
    (oder den Zweig verlassen hat)."""
    kette = e["_kette"]
    if not kette:
        return None
    ids = [o["id"] for o in kette]
    return kette[ids.index(wurzel) + 1:] if wurzel in ids else None


def set_ordner_von(eintraege, wurzel):
    """Die Ordner der Art „Set“ unterhalb von wurzel, in denen Zeilen liegen: {Kennung: {ordner (Pfad), artikel (Zeilen
    darunter, auch in inneren Sets – F1 b), geprueft (davon erledigt)}}, in Baumreihenfolge."""
    out = {}
    for e in sorted(eintraege, key=lambda e: _ordnung(e, wurzel)):
        for o in _unter(e, wurzel) or ():
            if o["kind"] == "set" and not o["system_kind"]:
                s = out.setdefault(o["id"], {"ordner": _pfad_text(o["id"]), "artikel": 0, "geprueft": 0})
                s["artikel"] += 1
                s["geprueft"] += e["zustand"] == "erledigt"
    return out


def _ordnung(e, wurzel):
    """Sortierschlüssel der Artikelliste: der Weg unter wurzel als Folge von Ordnern (nicht als Text – „Rucksack 1-B“
    stünde sonst zwischen „Rucksack 1“ und „Rucksack 1 › Tasche“), auf jeder Ebene erst die Artikel direkt im Ordner,
    dann Unterordner, die kein Set sind, dann die Sets – so stehen die Artikel eines Sets sicher zusammen. Artikel, die
    den Bereich verlassen haben, stehen am Ende."""
    unter = _unter(e, wurzel)
    if unter is None:
        return ((2, "", 0),), e["inventarnummer"]
    return tuple((1 if o["kind"] == "set" else 0, o["name"].casefold(), o["id"]) for o in unter), e["inventarnummer"]


def _ist_set(o):
    return o["kind"] == "set" and not o["system_kind"]


def _zwischenzeilen(liste, unten, alle_sets, je_set, abgebrochen):
    """Die Zwischenzeilen der Artikelliste (Prüfung vom 25.10.2026): Verglichen wird die ganze Kette der Sets auf dem Weg
    jeder Zeile unterhalb von unten (Durchgangs- bzw. Set-Ordner), nicht nur das innerste Set. Beim Eintritt in Sets steht
    je Set eine Zeile, von außen nach innen – auch für ein Set ohne eigene Artikel, mit seinem Set-Protokoll; beim Rückweg
    in ein äußeres Set „(Fortsetzung)“; beim Verlassen aller Sets „Außerhalb von Sets · <gemeinsamer Ordner>“ – ist unten
    selbst ein Set (Set-Protokoll, Durchgang für ein Set), steht das Set als äußerste Ebene: „Set <Pfad> (Fortsetzung)“.
    „n Artikel“ zählt genau die Zeilen bis zur nächsten Zwischenzeile; hat das Set mehr (in inneren Sets, nach einer
    Fortsetzung), steht „im ganzen Set …“ dabei – so viele stehen in seinem Set-Protokoll. Setzt je Zeile zwischen
    (Liste der Texte, meist leer) und im_set (in einem Set unterhalb von unten)."""
    pfad_unten = bestand.pfad(unten)
    unten_set = bool(pfad_unten) and _ist_set(pfad_unten[-1])
    ueber_set = any(_ist_set(o) for o in pfad_unten[:-1])
    koepfe, vorher, gesehen = [], [], set()
    for i, e in enumerate(liste):
        kette = [o["id"] for o in _unter(e, unten) or () if _ist_set(o)]
        e["im_set"], e["zwischen"] = bool(kette), []
        gleich = 0
        while gleich < min(len(kette), len(vorher)) and kette[gleich] == vorher[gleich]:
            gleich += 1
        if kette[gleich:]:
            neu = [(fid, fid in gesehen) for fid in kette[gleich:]]
        elif len(kette) < len(vorher):
            neu = [(kette[-1] if kette else None, True)]
        else:
            neu = []
        for fid, fortsetzung in neu:
            koepfe.append((i, fid, fortsetzung))
            gesehen.add(fid)
        vorher = kette
    for n, (i, fid, fortsetzung) in enumerate(koepfe):
        # Die Zeilen bis zum nächsten Kopf gehören zum letzten Kopf an dieser Stelle; die davor (äußere Sets, in die
        # zugleich eingetreten wird) haben keine eigenen.
        bis = next((k[0] for k in koepfe[n + 1:]), len(liste))
        block = liste[i:bis]
        if fid is None:
            if unten_set:
                text = f"Set {_pfad_text(unten)} (Fortsetzung)"
            else:
                # Der Ordner, in dem alle diese Zeilen liegen (commonprefix vergleicht Listen Glied für Glied).
                gemeinsam = os.path.commonprefix([[o["id"] for o in e["_kette"]] for e in block if e["_kette"]])
                text = "Außerhalb innerer Sets" if ueber_set else "Außerhalb von Sets"
                if gemeinsam:
                    text += f" · {_pfad_text(gemeinsam[-1])}"
            text += f" · {len(block)} Artikel"
        else:
            s, t = alle_sets[fid], je_set.get(fid)
            text = f"Set {s['ordner']}"
            if fortsetzung:
                text += f" (Fortsetzung) · {len(block)} Artikel"
            else:
                if len(block) == s["artikel"]:
                    text += f" · {len(block)} Artikel"
                elif block:
                    text += f" · {len(block)} Artikel, im ganzen Set {s['artikel']}"
                else:
                    text += f" · im ganzen Set {s['artikel']} Artikel"
                if t:
                    text += f" · Set-Protokoll {t['protokoll_id']}"
                elif abgebrochen:
                    text += " · kein Set-Protokoll (Durchgang abgebrochen)"
                elif not s["geprueft"]:
                    text += " · kein Set-Protokoll (nichts geprüft)"
        liste[i]["zwischen"].append(text)


def _sammelprotokoll(r, pid, ts, eintraege=None, wurzel=None, haupt=None, je_set=None):
    """Daten des Sammelprotokolls (wurzel None) oder des Set-Protokolls eines Set-Ordners unterhalb des Durchgangsordners
    (wurzel: seine Kennung; haupt: {protokoll_id, ordner} des Sammelprotokolls) – eine Funktion, gefiltert nach den
    Artikeln darunter (Entscheidung F1 b: auch die innerer Sets). je_set: die Set-Protokolle des Durchgangs {Ordner:
    {protokoll_id, artikel, file_sha256, ordner}} – für die Zwischenzeilen der Sets in der Artikelliste und (nur im
    Sammelprotokoll) das Verzeichnis der Set-Protokolle. Nummerierung je Protokoll 1…n."""
    from . import durchgang
    if eintraege is None:
        eintraege = _eintraege(r)
    je_set = je_set or {}
    unten = wurzel or r["folder_id"]
    liste = [dict(e) for e in eintraege if wurzel is None or _unter(e, wurzel) is not None]
    liste.sort(key=lambda e: _ordnung(e, unten))
    zaehler = {"erledigt": 0, "ausgenommen": 0, "nicht_geprueft": 0, "einsatzbereit": 0, "instandsetzen": 0,
               "aussondern_empfohlen": 0, "aussondern": 0}
    ohne = 0
    for nr, e in enumerate(liste, start=1):
        e["nr"] = nr
        zaehler[e["zustand"]] = zaehler.get(e["zustand"], 0) + 1
        if e["zustand"] == "erledigt":
            if e["ergebnis"]:
                zaehler[e["ergebnis"]] += 1
            if not e["protokoll_id"]:
                ohne += 1
    _zwischenzeilen(liste, unten, set_ordner_von(eintraege, unten), je_set, r["aborted"])
    zaehlung = [{"text": "Artikel im Durchgang" if wurzel is None else "Artikel im Set", "anzahl": len(liste)},
                {"text": "geprüft", "anzahl": zaehler["erledigt"]},
                {"text": "davon einsatzbereit", "anzahl": zaehler["einsatzbereit"], "einzug": True},
                {"text": "davon instandsetzen", "anzahl": zaehler["instandsetzen"], "einzug": True},
                {"text": "davon aussondern empfohlen", "anzahl": zaehler["aussondern_empfohlen"], "einzug": True}]
    if zaehler["aussondern"]:                  # Prüfungen vor Schritt 28, die zugleich aussonderten
        zaehlung.append({"text": "davon ausgesondert", "anzahl": zaehler["aussondern"], "einzug": True})
    zaehlung.append({"text": "ausgenommen", "anzahl": zaehler["ausgenommen"]})
    if r["aborted"] or zaehler["nicht_geprueft"]:
        zaehlung.append({"text": "nicht geprüft", "anzahl": zaehler["nicht_geprueft"]})
    # Prüfer: wer im Durchgang geprüft hat – im Set-Protokoll nur an Artikeln dieses Sets; die Unterschrift ist die
    # letzte dieses Prüfers an einer solchen Prüfung.
    nur = "" if wurzel is None else " AND item_id IN (SELECT value FROM json_each(?))"
    args = (r["id"],) if wurzel is None else (r["id"], json.dumps([e["_item"] for e in liste]))
    pruefer = []
    for x in db.query("SELECT inspector_user_id AS uid, inspector_name AS name, inspector_certificate AS urkunde, "
                      "COUNT(*) AS anzahl FROM mat_inspection WHERE round_id = ? AND completed_at IS NOT NULL" + nur + " "
                      + durchgang.OHNE_BERICHTIGTE +
                      "GROUP BY inspector_user_id, inspector_name, inspector_certificate ORDER BY inspector_name", args):
        sig = db.query("SELECT signature_png FROM mat_inspection WHERE round_id = ? AND inspector_user_id IS ? AND "
                       "inspector_name = ? AND signature_png IS NOT NULL" + nur + " ORDER BY locked_at DESC LIMIT 1",
                       (r["id"], x["uid"], x["name"]) + args[1:], one=True)
        pruefer.append({"name": x["name"], "urkunde": x["urkunde"], "anzahl": x["anzahl"],
                        "unterschrift": _png(sig["signature_png"]) if sig else None})
    for e in liste:
        e.pop("_kette", None)
        e.pop("_item", None)
    gl = bestand.gliederung_von(r["folder_id"])
    art = "sammelprotokoll" if wurzel is None else "setprotokoll"
    return {
        "dokument": _dokument(art, pid, ts, bestand.ordner_ist_demo(unten)),
        "durchgang": {"titel": r["title"], "ordner": _pfad_text(unten), "gliederung": gl["name"] if gl else "",
                      "eroeffnet": f"{datum_text(r['opened_on'])} von {r['opened_by_name']}",
                      "abgeschlossen": f"{zeit_text(ts)} von {r['closed_by_name']}", "abgebrochen": bool(r["aborted"])},
        "set_info": ({"name": bestand.ordner(wurzel)["name"], "teil_von": haupt["protokoll_id"],
                 "durchgang_ordner": haupt["ordner"]} if wurzel is not None else None),
        "zaehlung": zaehlung, "pruefer": pruefer, "artikel": liste, "ohne_protokoll": ohne,
        "set_protokolle": [je_set[fid] for fid in sorted(je_set, key=lambda f: je_set[f]["kennung"])] if wurzel is None else [],
    }


class Veraendert(Exception):
    """Zwischen dem Rendern ohne Sperre und dem Festschreiben hat sich etwas geändert, das in den Protokollen stünde –
    der Aufrufer verwirft die vorab gerenderten Dateien und beginnt neu (durchgang._beenden)."""


def durchgang_auswahl(r):
    """Stufe 1a, ohne Schreibsperre: die Zeilen des Durchgangs und die Set-Ordner, die ein Set-Protokoll bekommen – je
    Set-Ordner unterhalb des Durchgangsordners, in dem mindestens ein Artikel geprüft wurde (F2 b: nicht beim Abbruch,
    nicht bei „alles ausgenommen“). r ist der Durchgang, wie er nach dem Abschluss bzw. Abbruch dasteht."""
    eintraege = _eintraege(r)
    sets = [] if r["aborted"] else [fid for fid, s in set_ordner_von(eintraege, r["folder_id"]).items() if s["geprueft"]]
    return {"eintraege": eintraege, "sets": sets}


def t_nummern_reservieren(anzahl):
    """Die Kennungen (= Nummern T-<jahr>-<nr>, F3 a) für anzahl Set-Protokolle vorab vergeben – in einer eigenen, kurzen
    Schreibtransaktion, die den Zähler der Tabelle (AUTOINCREMENT, sqlite_sequence) um anzahl hebt. So verdrängen sich
    gleichzeitige Abschlüsse verschiedener Durchgänge nicht mehr (Nachprüfung vom 25.10.2026, N1): Jeder rendert mit
    seinen eigenen Nummern. Verworfene Versuche hinterlassen Lücken – wie verworfene Entwürfe (siehe Kopf)."""
    if not anzahl:
        return []
    with db.transaction(sofort=True):
        zeile = db.query("SELECT seq FROM sqlite_sequence WHERE name = 'mat_round_setprotokoll'", one=True)
        basis = max(zeile["seq"] if zeile else 0,
                    db.query("SELECT COALESCE(MAX(id), 0) AS n FROM mat_round_setprotokoll", one=True)["n"])
        if zeile:
            db.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'mat_round_setprotokoll'", (basis + anzahl,))
        else:
            db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('mat_round_setprotokoll', ?)", (basis + anzahl,))
    return list(range(basis + 1, basis + anzahl + 1))


def durchgang_vorbereiten(r, ts, kennungen, eintraege=None):
    """Stufe 1b des Festschreibens eines Durchgangs, ohne Schreibsperre: was entstünde, als Daten. r ist der Durchgang,
    wie er nach dem Abschluss bzw. Abbruch dasteht (closed_on, closed_by_name, aborted). Je Set-Ordner aus
    durchgang_auswahl ein Set-Protokoll mit der nächsten der vorab reservierten Kennungen (t_nummern_reservieren; erst
    alle Nummern, ein inneres Set nennt sein Protokoll im äußeren) und seinen Daten; dazu die Protokoll-ID des
    Sammelprotokolls. Passt die Zahl der Sets nicht mehr zu den Kennungen, hat sich etwas geändert (Veraendert). Unter
    der Sperre rechnet durchgang_festschreiben dasselbe mit denselben Kennungen noch einmal."""
    pid = protokoll_id("sammelprotokoll", r["id"], ts)
    if eintraege is None:
        eintraege = _eintraege(r)
    haupt = {"protokoll_id": pid, "ordner": _pfad_text(r["folder_id"])}
    je_set, set_daten = {}, {}
    auswahl = [] if r["aborted"] else [(fid, s) for fid, s in set_ordner_von(eintraege, r["folder_id"]).items()
                                       if s["geprueft"]]
    if len(auswahl) != len(kennungen):
        raise Veraendert()
    for (fid, s), kennung in zip(auswahl, kennungen):
        je_set[fid] = dict(s, kennung=kennung, protokoll_id=protokoll_id("setprotokoll", kennung, ts))
    for fid, s in je_set.items():
        set_daten[fid] = _sammelprotokoll(r, s["protokoll_id"], ts, eintraege, wurzel=fid, haupt=haupt, je_set=je_set)
    return {"r": r, "ts": ts, "pid": pid, "eintraege": eintraege, "je_set": je_set, "set_daten": set_daten}


def durchgang_rendern(v):
    """Stufe 2, ohne Schreibsperre und innerhalb von zwischendateien(): alle Set-Protokolle, dann das Sammelprotokoll mit
    ihren Prüfsummen – gerendert und unter Zwischennamen abgelegt. Ergänzt v (aus durchgang_vorbereiten) um die Felder
    der Dateien und die Daten des Sammelprotokolls."""
    for fid, s in v["je_set"].items():
        fertig, felder = _rendern("setprotokoll", s["protokoll_id"], v["set_daten"][fid])
        _zwischen_ablegen(felder["pdf_path"], fertig)
        s.update(felder)
    v["daten"] = _sammelprotokoll(v["r"], v["pid"], v["ts"], v["eintraege"], je_set=v["je_set"])
    fertig, v["felder"] = _rendern("sammelprotokoll", v["pid"], v["daten"])
    _zwischen_ablegen(v["felder"]["pdf_path"], fertig)


def durchgang_festschreiben(rid, v):
    """Stufe 3: das Sammelprotokoll (und beim regulären Abschluss die Set-Protokolle) eines eben abgeschlossenen oder
    abgebrochenen Durchgangs festschreiben – in dessen Schreibtransaktion, nach dem Schließen, und innerhalb von
    dateien_sichern(). Die Daten werden unter der Sperre noch einmal ausgerechnet; nur wenn sie genau denen gleichen, aus
    denen v gerendert wurde, kommen die vorab gerenderten Dateien unter ihre endgültigen Namen und die Zeilen in die
    Datenbank – sonst Veraendert (die Transaktion rollt zurück, nichts ist abgelegt). Liefert die Protokoll-ID des
    Sammelprotokolls."""
    r = db.query("SELECT * FROM mat_round WHERE id = ?", (rid,), one=True)
    if not r or not r["closed_on"] or r["locked_at"]:
        raise RuntimeError("Sammelprotokoll nur einmal und erst nach dem Abschluss.")
    ts, pid, je_set = v["ts"], v["pid"], v["je_set"]
    jetzt = durchgang_vorbereiten(r, ts, [s["kennung"] for s in je_set.values()])
    if (jetzt["pid"] != pid or list(jetzt["je_set"]) != list(je_set)
            or any({k: je_set[fid][k] for k in s} != s for fid, s in jetzt["je_set"].items())
            or jetzt["set_daten"] != v["set_daten"]
            or _sammelprotokoll(r, pid, ts, jetzt["eintraege"], je_set=je_set) != v["daten"]):
        raise Veraendert()
    for fid, s in je_set.items():
        _zwischen_uebernehmen(s["pdf_path"])
        db.execute("INSERT INTO mat_round_setprotokoll (id, round_id, folder_id, ordner, artikel, protocol_id, locked_at, "
                   "pdf_path, pdf_sha256, pdf_hashed_bytes, file_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (s["kennung"], rid, fid, s["ordner"], s["artikel"], s["protokoll_id"], ts, s["pdf_path"],
                    s["pdf_sha256"], s["pdf_hashed_bytes"], s["file_sha256"]))
    felder = v["felder"]
    _zwischen_uebernehmen(felder["pdf_path"])
    db.execute("UPDATE mat_round SET protocol_id = ?, locked_at = ?, pdf_path = ?, pdf_sha256 = ?, pdf_hashed_bytes = ?, "
               "file_sha256 = ? WHERE id = ?",
               (pid, ts, felder["pdf_path"], felder["pdf_sha256"], felder["pdf_hashed_bytes"], felder["file_sha256"], rid))
    nachher = {"protocol_id": pid, "pdf_sha256": felder["pdf_sha256"], "pdf_hashed_bytes": felder["pdf_hashed_bytes"],
               "file_sha256": felder["file_sha256"]}
    if je_set:
        nachher["set_protokolle"] = [{"protocol_id": s["protokoll_id"], "folder_id": fid, "file_sha256": s["file_sha256"]}
                                     for fid, s in je_set.items()]
    journal.eintragen("round", rid, "festgeschrieben", None, nachher)
    return pid


def set_protokolle(rid):
    """Die Set-Protokolle eines Durchgangs (Zeilen von mat_round_setprotokoll), nach Nummer."""
    return db.query("SELECT * FROM mat_round_setprotokoll WHERE round_id = ? ORDER BY id", (rid,))


# --- Lesen und ausliefern ---------------------------------------------------------------------------------

def protokoll_json(row, url):
    """Was Oberfläche und Lebenslauf über ein Protokoll zeigen (None ohne Protokoll)."""
    if not row.get("locked_at") or not row.get("pdf_path"):
        return None
    return {"id": row["protocol_id"], "url": url, "sha256": row["pdf_sha256"], "bytes": row["pdf_hashed_bytes"],
            "datei_sha256": row["file_sha256"], "festgeschrieben": row["locked_at"],
            "anmeldung": row.get("locked_login") or ""}


def datei(row):
    """Pfad der Protokolldatei – nur wenn sie noch genau die festgeschriebene ist."""
    if not row or not row.get("pdf_path"):
        raise Abgelehnt("Zu diesem Vorgang gibt es kein Protokoll.", 404)
    pfad = voller_pfad(row["pdf_path"])
    try:
        with open(pfad, "rb") as fh:
            summe = hashlib.file_digest(fh, "sha256").hexdigest()
    except OSError:
        current_app.logger.error("Protokolldatei fehlt: %s", row["pdf_path"])
        raise Abgelehnt("Die Protokolldatei fehlt im Datenverzeichnis – bitte die Sicherung prüfen.", 404)
    if summe != row["file_sha256"]:
        current_app.logger.error("Protokolldatei verändert: %s", row["pdf_path"])
        raise Abgelehnt("Die Protokolldatei stimmt nicht mehr mit ihrer Prüfsumme überein – bitte die Sicherung "
                        "prüfen.", 409)
    return pfad


def dateiname(row, inventarnummer=None):
    return f"{row['protocol_id']}" + (f"_{inventarnummer}" if inventarnummer else "") + ".pdf"


# --- Prüfseite -----------------------------------------------------------------------------------------

_PROTOKOLL_TABELLEN = ("mat_inspection", "mat_round", "mat_round_setprotokoll")
# Seit Schritt 31 erkennt die Prüfseite auch ausgegebene Lebensläufe (mat_lebenslauf, Kennung L-<jahr>-<nr>) – in der
# Antwort mit ihrer Kennung als protokoll_id und dem Stand, ohne Inventarnummer.
_LEBENSLAUF_SQL = "SELECT kennung AS protocol_id, pdf_hashed_bytes, pdf_sha256, stand FROM mat_lebenslauf WHERE "


def _per_summe(spalte, summe):
    for tabelle in _PROTOKOLL_TABELLEN:
        r = db.query(f"SELECT protocol_id, pdf_hashed_bytes, pdf_sha256 FROM {tabelle} WHERE {spalte} = ? "
                     "AND locked_at IS NOT NULL", (summe,), one=True)
        if r:
            return r
    return db.query(_LEBENSLAUF_SQL + f"{spalte} = ?", (summe,), one=True)


def _per_id(pid):
    if pid[:1] == "L":
        return db.query(_LEBENSLAUF_SQL + "kennung = ?", (pid,), one=True)
    tabelle = {"S": "mat_round", "T": "mat_round_setprotokoll"}.get(pid[:1], "mat_inspection")
    return db.query(f"SELECT protocol_id, pdf_hashed_bytes, pdf_sha256 FROM {tabelle} WHERE protocol_id = ? "
                    "AND locked_at IS NOT NULL", (pid,), one=True)


def _art(pid):
    return {"P": "Prüfprotokoll", "A": "Aussonderungsprotokoll", "S": "Sammelprotokoll",
            "T": "Set-Protokoll", "L": "Lebenslauf"}.get(pid[:1], "Protokoll")


# Die Sätze der Prüfseite je Art der Datei: Protokoll (festgeschrieben) oder Lebenslauf (ausgegeben).
_SAETZE = {
    "protokoll": {
        "unveraendert": "Die Datei ist Byte für Byte das festgeschriebene Protokoll.",
        "ohne_stempel": "Der Inhalt entspricht dem Protokoll, aber der Prüfsummen-Stempel fehlt – das ist nicht die "
                        "ausgegebene Datei.",
        "danach": "Die ersten {n} Bytes (das Protokoll selbst) sind unverändert; geändert wurde danach – am Stempel oder "
                  "durch Anhängen. Das ist nicht die ausgegebene Datei.",
        "inhalt": "Der Inhalt des Protokolls wurde verändert – die Prüfsumme stimmt nicht mehr.",
    },
    "lebenslauf": {
        "unveraendert": "Die Datei ist Byte für Byte der Lebenslauf, den strömis.de ausgegeben hat.",
        "ohne_stempel": "Der Inhalt entspricht dem Lebenslauf, aber der Prüfsummen-Stempel fehlt – das ist nicht die "
                        "ausgegebene Datei.",
        "danach": "Die ersten {n} Bytes (der Lebenslauf selbst) sind unverändert; geändert wurde danach – am Stempel oder "
                  "durch Anhängen. Das ist nicht die ausgegebene Datei.",
        "inhalt": "Der Inhalt des Lebenslaufs wurde verändert – die Prüfsumme stimmt nicht mehr.",
    },
}


def _antwort(r, ergebnis, satz):
    lebenslauf = r["protocol_id"].startswith("L-")
    out = {"ergebnis": ergebnis, "protokoll_id": r["protocol_id"], "art": _art(r["protocol_id"]),
           "hinweis": _SAETZE["lebenslauf" if lebenslauf else "protokoll"][satz].format(n=r["pdf_hashed_bytes"])}
    if lebenslauf:
        out["stand"] = zeit_text(r["stand"])
    return out


def _kopf_summe(fh, n):
    fh.seek(0)
    h, rest = hashlib.sha256(), n
    while rest > 0:
        stueck = fh.read(min(rest, 1 << 20))
        if not stueck:
            return None
        h.update(stueck)
        rest -= len(stueck)
    return h.hexdigest()


def _kopf_kandidaten(fh, hoechstens=12):
    """In einem Durchgang: (N, SHA-256 der ersten N Bytes) für die ersten Grenzen hinter %%EOF (mit und ohne
    Zeilenende) – Kandidaten für den Protokollinhalt einer Datei, deren Kennung beschädigt ist. Begrenzt auf
    `hoechstens` Grenzen: eine präparierte Datei voller %%EOF kostet so weder Speicher noch Zeit."""
    fh.seek(0)
    h, gelesen, kandidaten, rest = hashlib.sha256(), 0, [], b""
    while len(kandidaten) < hoechstens and (stueck := fh.read(1 << 20)):
        daten = rest + stueck                 # rest: Ende des vorigen Stücks, nur zum Finden über die Grenze
        basis = gelesen - len(rest)
        verbraucht = len(rest)                # bis hierher steckt daten schon in h
        start = 0
        while len(kandidaten) < hoechstens and (i := daten.find(b"%%EOF", start)) != -1:
            start = i + 5
            for ende in sorted({i + 5, i + 6 if daten[i + 5:i + 6] in (b"\n", b"\r") else i + 5,
                                i + 7 if daten[i + 5:i + 7] == b"\r\n" else i + 5}):
                if ende < verbraucht or ende > len(daten):
                    continue
                h.update(daten[verbraucht:ende])
                verbraucht = ende
                kandidaten.append((basis + ende, h.copy().hexdigest()))
        h.update(daten[verbraucht:])
        gelesen += len(stueck)
        rest = daten[-8:]
    return kandidaten[:hoechstens]


def pruefen(fh):
    """Ein hochgeladenes PDF gegen die gespeicherten Prüfsummen der Protokolle und – seit Schritt 31 – der ausgegebenen
    Lebensläufe. Liefert {ergebnis, protokoll_id, art, hinweis} mit ergebnis „unveraendert“, „veraendert“ oder
    „unbekannt“, beim Lebenslauf dazu stand (sein Zeitpunkt) – ohne Personendaten und ohne Inventarnummer."""
    fh.seek(0)
    h, groesse = hashlib.sha256(), 0
    while stueck := fh.read(1 << 20):
        h.update(stueck)
        groesse += len(stueck)
    voll = h.hexdigest()
    r = _per_summe("file_sha256", voll)
    if r:
        return _antwort(r, "unveraendert", "unveraendert")
    r = _per_summe("pdf_sha256", voll)
    if r:
        return _antwort(r, "veraendert", "ohne_stempel")
    # Zugeordnet wird nur über die Kennung im Stempel-Nachtrag – ein unkomprimierter Kommentar am Dateiende. Den
    # Text der Datei liest die Prüfseite bewusst nicht: Ein PDF zu zerlegen kostet bei präparierten Dateien
    # Minuten und Gigabytes, und jeder kann hier hochladen. Die Kennung gilt nur, wenn N und Prüfsumme zum
    # gespeicherten Protokoll passen – sonst ließen sich mit erfundenen Kennungen die vergebenen IDs abfragen.
    fh.seek(max(0, groesse - 4 * 1024 * 1024))
    kennung = stempel.kennung_lesen(fh.read())
    r = _per_id(kennung[0]) if kennung else None
    if r and (r["pdf_hashed_bytes"] != kennung[1] or r["pdf_sha256"] != kennung[2]):
        r = None
    if not r:
        # Kennung beschädigt: Jeder Nachtrag endet mit %%EOF – eine dieser Grenzen ist das Ende der ersten N Bytes.
        # Stimmt die Summe bis dorthin mit einem Protokoll überein, liegt dessen Inhalt vor (das verrät nichts,
        # was der Hochladende nicht schon hat).
        for n, summe in _kopf_kandidaten(fh):
            r = _per_summe("pdf_sha256", summe)
            if r and r["pdf_hashed_bytes"] == n:
                break
            r = None
    if not r:
        return {"ergebnis": "unbekannt", "protokoll_id": None, "art": None,
                "hinweis": "Diese Datei ist kein Protokoll und kein Lebenslauf von strömis.de – oder so verändert, dass "
                           "sie sich keinem mehr zuordnen lässt."}
    kopf = _kopf_summe(fh, r["pdf_hashed_bytes"])
    return _antwort(r, "veraendert", "danach" if kopf == r["pdf_sha256"] else "inhalt")
