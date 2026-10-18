"""Lebenslauf eines Artikels als PDF (Lieferung 4; Konzept: „Stammdaten plus alle Prüfungen chronologisch, für
Weitergabe oder Aussonderungsnachweis“).

Auf Abruf gesetzt und NICHT festgeschrieben: kein Prüfsummen-Stempel, keine Datei unter DATA_DIR/pdf, kein Eintrag in
mat_inspection oder im Journal – der Fuß jeder Seite sagt „nicht festgeschrieben“. Verbindlich bleiben die Protokolle;
der Lebenslauf nennt jedes mit Protokoll-ID und der Prüfsumme der Datei, so lässt es sich zuordnen und auf der
Prüfseite prüfen. Gesetzt wird über services/pdf.py als PDF/A-3b wie die Protokolle (Vorlage
templates/material/pdf/lebenslauf.html). Gelesen wird ohne Transaktion – das Setzen hält keine Schreibsperre.

Inhalt: Stammdaten (wie im Protokoll), Zustand (Status, Sperre, Fälligkeit, wirksames Intervall, Lebensdauer,
Bemerkung), alle abgeschlossenen Prüfungen und die Aussonderung in zeitlicher Reihenfolge, die Prüfdurchgänge, in
denen der Artikel stand, und die Ereignisse aus seinem Journal (ohne die des Produkts) mit lesbaren Beschriftungen."""
from datetime import date

from ... import db
from ..models import ERGEBNISSE, MATERIALARTEN
from . import bestand, heute, journal, katalog, protokoll, qr
from . import status as st
from .beschriftung import SPERRZUSTAND, journal_zeilen
from .interval import wirksam
from .protokoll import PRUEFART_TEXT, datum_text, ortszeit, zeit_text

# So viele Journaleinträge nimmt der Lebenslauf höchstens auf (journal.lesen liest die neuesten zuerst).
JOURNAL_MAX = 2000
OHNE_PROTOKOLL = "kein Protokoll – abgeschlossen vor Einführung der PDF-Protokolle"


def _tage(n):
    return f"{n} Tag" if n == 1 else f"{n} Tage"


def _intervall_text(iv):
    """Wie in der Artikelansicht: Monate, Herkunft und – wenn die Organisation länger wollte – der Hinweis darauf."""
    if not iv["monate"]:
        return "kein Intervall"
    text = f"{iv['monate']} Monate ({iv['quelle'] or ''})"
    om, hm = iv["organisation"][0], iv["hersteller"][0]
    if om and hm and om > hm:
        text += f" – {iv['organisation'][1]} wollte {om}, die Herstellervorgabe ist kürzer"
    return text


def _lebensdauer_text(item, produkt, tag):
    if produkt["material_kind"] == "textil" and item["retire_by"]:
        rest = (date.fromisoformat(item["retire_by"]) - tag).days
        if rest <= 0:
            return f"erreicht am {datum_text(item['retire_by'])}"
        vorgezogen = bool(item["retire_by_manual"]) and item["retire_by"] == item["retire_by_manual"]
        herkunft = "von Hand vorgezogen" if vorgezogen else f"{produkt['lifetime_years']} Jahre ab Herstellung"
        return f"{datum_text(item['retire_by'])} (noch {_tage(rest)}; {herkunft})"
    if produkt["lifetime_years"]:
        quelle = f" ({produkt['lifetime_source']})" if produkt["lifetime_source"] else ""
        art = MATERIALARTEN.get(produkt["material_kind"], produkt["material_kind"])
        return f"Herstellerangabe {produkt['lifetime_years']} Jahre{quelle} – bei „{art}“ kein festgeschriebenes Lebensende"
    return "keine festgeschriebene Lebensdauer"


def _naechste_text(item, s):
    if s == "ausgesondert":
        return "–"
    if s == "gesperrt":
        return "setzt die Freiprüfung"
    if s == "neu":
        return "Eingangsprüfung ausstehend"
    return datum_text(item["next_due_on"]) or "keine"


def _hinweis(item, s, aussonderung):
    """Der Kasten oben – wie das Banner der Artikelansicht."""
    if s == "ausgesondert":
        text = "Dieser Artikel ist außer Dienst und darf nicht mehr verwendet werden."
        if aussonderung:
            text = (f"Ausgesondert am {datum_text(aussonderung['inspected_on'])} – {aussonderung['reason']}"
                    + (f" (Aussonderungsprotokoll {aussonderung['protocol_id']})" if aussonderung["protocol_id"] else "")
                    + ". " + text)
        return {"titel": "AUSGESONDERT", "text": text}
    if s == "gesperrt":
        titel = "VERLOREN GEMELDET (GESPERRT)" if item["lock_state"] == "verloren" else "GESPERRT"
        return {"titel": titel, "text": (f"{item['lock_reason']}. " if item["lock_reason"] else "")
                + "Nicht verwenden, bis eine Freiprüfung ihn freigibt."}
    if s == "lebensdauer":
        return {"titel": "LEBENSDAUER ERREICHT", "text": "Aussondern."}
    if s == "neu":
        return {"titel": "NEU", "text": "Die Eingangsprüfung steht aus. Bis dahin nicht einsetzen."}
    return None


def _zustand(item, produkt, s, tag, baum_pfad):
    # Gesperrte liegen in „Gesperrt“; ihr Intervall kommt aus der Heimat (wie bei der Freiprüfung).
    heimat = bestand.heimat(item)
    return {"status": s, "status_text": st.LABEL[s],
            "sperrzustand": SPERRZUSTAND.get(item["lock_state"], item["lock_state"]) if item["lock_state"] != "frei" else "",
            "grund": item["lock_reason"] or "",
            "herkunft": baum_pfad(item["origin_folder_id"]) if item["origin_folder_id"] else "",
            "zuletzt": datum_text(item["last_inspected_on"]) or "noch nie",
            "naechste": _naechste_text(item, s),
            "intervall": "" if s == "ausgesondert" else _intervall_text(wirksam(produkt, heimat, item["interval_months"])),
            "lebensdauer": _lebensdauer_text(item, produkt, tag), "bemerkung": item["notes"] or ""}


def _pruefungen(iid):
    """Alle abgeschlossenen Prüfungen und Aussonderungen, älteste zuerst; eine Berichtigung steht hinter ihrem Original
    (gleicher Prüftag, höhere Kennung)."""
    rows = db.query("SELECT id, round_id, protocol_id, inspector_name, inspector_certificate, inspected_on, kind, result, "
                    "reason, remarks, next_due_on, corrects_inspection_id, basis_inspection_id, correction_reason, "
                    "locked_at, pdf_path, file_sha256 FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL "
                    "ORDER BY inspected_on, id", (iid,))
    maengel = {r["inspection_id"]: r["n"] for r in db.query(
        "SELECT inspection_id, COUNT(*) AS n FROM mat_inspection_result WHERE finding = 'mangel' AND inspection_id IN "
        "(SELECT id FROM mat_inspection WHERE item_id = ?) GROUP BY inspection_id", (iid,))}
    runden = {r["id"]: r["title"] for r in db.query(
        "SELECT id, title FROM mat_round WHERE id IN (SELECT round_id FROM mat_inspection WHERE item_id = ?)", (iid,))}
    nach_id = {r["id"]: r for r in rows}
    durch = {r["corrects_inspection_id"]: r for r in rows if r["corrects_inspection_id"]}
    out = []
    for nr, r in enumerate(rows, start=1):
        aus = r["kind"] == "aussonderung"
        protokoll_da = bool(r["locked_at"] and r["pdf_path"])
        original = nach_id.get(r["corrects_inspection_id"])
        nachfolger = durch.get(r["id"])
        basis = nach_id.get(r["basis_inspection_id"])
        out.append({
            "nr": nr, "datum": datum_text(r["inspected_on"]), "art": PRUEFART_TEXT.get(r["kind"], r["kind"]),
            "aussonderung": aus, "pruefer": r["inspector_name"], "urkunde": r["inspector_certificate"] or "",
            "ergebnis": r["result"] or "",
            "ergebnis_text": "ausgesondert" if aus else ERGEBNISSE.get(r["result"], r["result"] or ""),
            "maengel": None if aus else maengel.get(r["id"], 0),
            "naechste": datum_text(r["next_due_on"]) or ("entfällt" if r["result"] in ("instandsetzen", "aussondern") else "–"),
            "grund": r["reason"] or "", "bemerkung": r["remarks"] or "", "durchgang": runden.get(r["round_id"], ""),
            "protokoll_id": r["protocol_id"] if protokoll_da else "", "datei_sha256": r["file_sha256"] if protokoll_da else "",
            "ohne_protokoll": OHNE_PROTOKOLL if not protokoll_da else "",
            "berichtigung_von": ({"protokoll_id": original["protocol_id"] or "(ohne Protokoll)",
                                  "datum": datum_text(original["inspected_on"]), "grund": r["correction_reason"] or ""}
                                 if original else None),
            "berichtigt_durch": (nachfolger["protocol_id"] or "(ohne Protokoll)") if nachfolger else "",
            "basis": (basis["protocol_id"] or f"Prüfung vom {datum_text(basis['inspected_on'])}") if basis else ""})
    return out, rows


def _durchgaenge(iid, baum_pfad):
    """Die Prüfdurchgänge, in denen der Artikel stand – mit dem, was darin aus ihm wurde."""
    runden = db.query("SELECT r.id, r.title, r.folder_id, r.opened_on, r.closed_on, r.aborted, r.protocol_id, r.locked_at, "
                      "r.pdf_path, r.file_sha256, ri.excluded_reason, ri.excluded_by_name, ri.excluded_at "
                      "FROM mat_round_item ri JOIN mat_round r ON r.id = ri.round_id WHERE ri.item_id = ? "
                      "ORDER BY r.opened_on, r.id", (iid,))
    geprueft = {}
    for x in db.query("SELECT round_id, result, inspected_on FROM mat_inspection WHERE item_id = ? AND round_id IS NOT NULL "
                      "AND completed_at IS NOT NULL ORDER BY completed_at, id", (iid,)):
        geprueft[x["round_id"]] = x                      # die letzte zählt (auch eine Berichtigung)
    out = []
    for r in runden:
        x = geprueft.get(r["id"])
        if x:
            darin = f"geprüft am {datum_text(x['inspected_on'])} – {ERGEBNISSE.get(x['result'], x['result'])}"
        elif r["excluded_reason"]:
            darin = (f"ausgenommen: {r['excluded_reason']} ({r['excluded_by_name']}, "
                     f"{ortszeit(r['excluded_at']).strftime('%d.%m.%Y') if r['excluded_at'] else ''})")
        elif r["closed_on"]:
            darin = "nicht geprüft"
        else:
            darin = "noch offen"
        if not r["closed_on"]:
            zeitraum = f"seit {datum_text(r['opened_on'])}, läuft"
        else:
            zeitraum = (f"{datum_text(r['opened_on'])} bis {datum_text(r['closed_on'])}"
                        + (" (abgebrochen)" if r["aborted"] else ""))
        da = bool(r["locked_at"] and r["pdf_path"])
        out.append({"titel": r["title"], "ordner": baum_pfad(r["folder_id"]), "zeitraum": zeitraum, "darin": darin,
                    "protokoll_id": r["protocol_id"] if da else "", "datei_sha256": r["file_sha256"] if da else "",
                    "ohne_protokoll": "" if da or not r["closed_on"] else OHNE_PROTOKOLL})
    return out


def _rueckrufe(item):
    """Rückrufe zum Produkt, die den Artikel betreffen (services/rueckruf.py) – mit dem Zustand für ihn, solange sie
    laufen, und dem Vermerk, wenn sie beendet sind."""
    from . import rueckruf
    zustaende = {"gesperrt": "erledigt – gesperrt", "ausgesondert": "erledigt – ausgesondert",
                 "geprueft": "erledigt – nach dem Rückruf geprüft"}
    out = []
    for r in rueckruf.fuer_lebenslauf(item):
        if r["closed_at"]:
            stand = f"beendet am {zeit_text(r['closed_at'])}" + (f" von {r['closed_by_name']}" if r["closed_by_name"] else "")
        elif r["zustand"] == "offen":
            stand = "läuft – für diesen Artikel offen (seit dem Rückruf weder geprüft noch gesperrt)"
        else:
            stand = "läuft – für diesen Artikel " + zustaende.get(r["grund"], "erledigt")
        out.append({"titel": r["title"], "angelegt": zeit_text(r["created_at"]), "von": r["created_by_name"] or "–",
                    "betrifft": "alle Artikel des Produkts" if r["alle"] else "betrifft diese Seriennummer",
                    "beschreibung": r["description"], "link": r["url"], "stand": stand, "vermerk": r["close_note"]})
    return out


def daten(iid):
    """Alle Werte für die Vorlage, fertig formatiert."""
    item = bestand.artikel(iid)
    produkt = katalog.produkt(item["product_id"])
    tag = heute()
    s = st.status(item, tag)
    pfade = {}

    def baum_pfad(fid):
        if fid not in pfade:
            pfade[fid] = protokoll._pfad_text(fid)
        return pfade[fid]

    pruefungen, rows = _pruefungen(iid)
    aussonderung = next((r for r in reversed(rows) if r["kind"] == "aussonderung"), None)
    verweise = {r["id"]: r["protocol_id"] for r in db.query(
        "SELECT id, protocol_id FROM mat_inspection WHERE item_id = ? AND protocol_id IS NOT NULL", (iid,))}
    eintraege = journal.lesen([("item", iid)], grenze=JOURNAL_MAX + 1)     # einer mehr: Wurde gekürzt?
    gekuerzt = len(eintraege) > JOURNAL_MAX
    eintraege = eintraege[:JOURNAL_MAX]                                      # die neuesten zuerst – der älteste fällt weg
    return {
        "dokument": {"art": "lebenslauf", "titel": "Lebenslauf", "stand": zeit_text(db.now()),
                     "plattform": qr.anzeige(qr.basis()).split("://", 1)[-1], "pruefseite": protokoll.pruefseite(),
                     "demo": bool(produkt["demo"])},
        "artikel": protokoll._artikel(item, produkt, item["folder_id"]),
        "zustand": _zustand(item, produkt, s, tag, baum_pfad),
        "hinweis": _hinweis(item, s, aussonderung),
        "pruefungen": pruefungen,
        "durchgaenge": _durchgaenge(iid, baum_pfad),
        "rueckrufe": _rueckrufe(item),
        "ereignisse": journal_zeilen(list(reversed(eintraege)), verweise),
        "ereignisse_gekuerzt": gekuerzt,
    }


def rendern(iid):
    """(PDF als bytes, Inventarnummer) – nichts davon wird gespeichert."""
    from . import pdf
    d = daten(iid)
    return pdf.rendern("lebenslauf", d), d["artikel"]["inventarnummer"]
