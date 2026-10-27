"""Lebenslauf eines Artikels als PDF (Lieferung 4; Konzept: „Stammdaten plus alle Prüfungen chronologisch, für
Weitergabe oder Aussonderungsnachweis“).

Auf Abruf gesetzt, nie festgeschrieben (auch nicht bei der Aussonderung): keine Datei unter DATA_DIR/pdf, kein Eintrag in
mat_inspection oder im Journal. Seit Schritt 31 (Wunsch vom 27.10.2026) bekommt jeder Abruf eine Kennung L-<jahr>-<nr>
(fortlaufend je Jahr, Zähler in mat_meta) und einen Prüfsummen-Stempel wie ein Protokoll (stempel.py); mat_lebenslauf
verzeichnet Kennung, Inventarnummer, Stand und die Prüfsummen – nicht, wer abgerufen hat, nicht den Inhalt, keine Datei.
So erkennt die Prüfseite (protokoll.pruefen) einen ausgegebenen Lebenslauf Byte für Byte wieder. Die Kennung wird in
einer eigenen kurzen Schreibtransaktion vergeben, gesetzt wird ohne Schreibsperre, verzeichnet in einer zweiten kurzen
Transaktion; scheitert das Setzen dazwischen, bleibt eine Lücke in den Nummern (wie bei den T-Nummern). Der Lebenslauf
nennt außerdem jedes Protokoll mit Protokoll-ID und der Prüfsumme der Datei, so lässt es sich zuordnen und ebenfalls auf
der Prüfseite prüfen. Gesetzt wird über services/pdf.py als PDF/A-3b wie die Protokolle (Vorlage
templates/material/pdf/lebenslauf.html). Gelesen wird ohne Transaktion – das Setzen hält keine Schreibsperre.

Inhalt: Stammdaten (wie im Protokoll), Zustand (Status, Sperre, Fälligkeit, wirksames Intervall, Lebensdauer,
Bemerkung), alle abgeschlossenen Prüfungen und die Aussonderung in zeitlicher Reihenfolge, die Prüfdurchgänge, in
denen der Artikel stand, und die Ereignisse aus seinem Journal mit lesbaren Beschriftungen – bei Änderungsanträgen für
Konten, die nur lesen, ohne Begründung und Namen (antrag.journal_verbergen); bei „Mangel gemeldet“ mit dem Namen des
Melders und der Mangelbeschreibung für Prüfer und Materialwart und für den Melder bei seiner eigenen Meldung, sonst
„(Person)“ ohne Text wie in der Oberfläche (_maengel, Wunsch vom 26.10.2026; Fotos nie). Dazu die Änderungen an den
Daten seines Produkts seit dem Anlegen des Artikels (PRODUKT_AKTIONEN, als „Produkt …“ – Entscheidung E8 vom 24.10.2026: Die
Material-Verwaltung pflegt Katalogprodukte weiter, jede Änderung steht im Produktjournal und im Lebenslauf der Artikel);
Rückrufe stehen in ihrem eigenen Abschnitt, Meldungen gehören zum Katalog."""
from datetime import date

from ... import db
from ..models import ERGEBNISSE, MATERIALARTEN
from . import bestand, heute, journal, katalog, protokoll, qr, stempel, teilnummern
from . import status as st
from .beschriftung import SPERRZUSTAND, journal_zeilen
from .interval import wirksam
from .protokoll import PRUEFART_TEXT, datum_text, ortszeit, zeit_text

VORSATZ = "L"
ZAEHLER = "lebenslauf_zaehler_{jahr}"         # Schlüssel in mat_meta, je Jahr ein Zähler
ART = "Lebenslauf"                            # so nennt ihn die Prüfseite

# So viele Journaleinträge nimmt der Lebenslauf höchstens auf (journal.lesen liest die neuesten zuerst).
JOURNAL_MAX = 2000
# Einträge im Journal des Produkts, die der Lebenslauf zeigt: Stammdaten, Bild, Bestandteil-Liste (Schritt 25; „stueckliste“
# aus der Set-Funktion bis Schritt 26) – keine Rückrufe (eigener Abschnitt; ihre Seriennummernlisten nennen Artikel aller Gliederungen).
PRODUKT_AKTIONEN = ("geaendert", "bild", "stueckliste", "bestandteile")
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
            "naechste": datum_text(r["next_due_on"]) or ("entfällt" if r["result"] in ("instandsetzen", "aussondern_empfohlen", "aussondern") else "–"),
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
        if r.get("frueheres_produkt"):
            stand = (f"betraf den Artikel mit dem früheren Produkt {r['frueheres_produkt']} (bis "
                     f"{zeit_text(r['bis'])})" + (f"; beendet am {zeit_text(r['closed_at'])}" if r["closed_at"] else ""))
        elif r["closed_at"]:
            stand = f"beendet am {zeit_text(r['closed_at'])}" + (f" von {r['closed_by_name']}" if r["closed_by_name"] else "")
        elif r["zustand"] == "offen":
            stand = "läuft – für diesen Artikel offen (seit er betroffen ist weder geprüft noch gesperrt)"
        else:
            stand = "läuft – für diesen Artikel " + zustaende.get(r["grund"], "erledigt")
        out.append({"titel": r["title"], "angelegt": zeit_text(r["created_at"]), "von": r["created_by_name"] or "–",
                    "betrifft": "alle Artikel des Produkts" if r["alle"] else "betrifft diese Seriennummer",
                    "beschreibung": r["description"], "link": r["url"], "stand": stand, "vermerk": r["close_note"]})
    return out


def _maengel(item):
    """{Kennung: (Name des Melders, Beschreibung)} der Meldungen am Artikel, deren Inhalt das Konto sehen darf – wie in
    der Oberfläche (mangel.darf_inhalt; bestand._melder_verbergen): Prüfer und Materialwart alle, sonst nur die eigenen.
    Der Name ist der beim Melden gespeicherte – er bleibt, auch wenn das Konto später gelöscht wird (F3)."""
    from . import mangel
    alle = mangel.darf_inhalt(item)
    return {r["id"]: (r["reporter_name"], r["description"])
            for r in db.query("SELECT id, reporter_id, reporter_name, description FROM mat_defect_report WHERE item_id = ?",
                              (item["id"],))
            if alle or mangel.eigen(r)}


def daten(iid, stand=None):
    """Alle Werte für die Vorlage, fertig formatiert. stand: Zeitpunkt (UTC, wie db.now()), Vorgabe jetzt; die Kennung
    trägt rendern() nach (dokument.kennung)."""
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
    # Produktänderungen je Produkt nur aus der Zeit, in der der Artikel es hatte (journal.produkt_zeitraeume).
    for z in journal.produkt_zeitraeume(item):
        eintraege += [e for e in journal.lesen([("product", z["product_id"])], grenze=JOURNAL_MAX + 1)
                      if e["action"] in PRODUKT_AKTIONEN and e["created_at"] >= item["created_at"]
                      and journal.im_zeitraum(e, z)]
    eintraege.sort(key=lambda e: e["id"], reverse=True)
    gekuerzt = len(eintraege) > JOURNAL_MAX
    eintraege = eintraege[:JOURNAL_MAX]                                      # die neuesten zuerst – der älteste fällt weg
    # Änderungsanträge: Begründung, Namen, Anmerkung und Ablehnungsgrund nur für Materialwart und Prüfer – wie die
    # Antragsansicht und der Verlauf am Artikel (Prüfung vom 21.10.2026).
    from . import antrag
    if not antrag.darf_beantragen(item):
        antrag.journal_verbergen(eintraege)
    return {
        "dokument": {"art": "lebenslauf", "titel": "Lebenslauf", "stand": zeit_text(stand or db.now()), "kennung": "",
                     "plattform": qr.anzeige(qr.basis()).split("://", 1)[-1], "pruefseite": protokoll.pruefseite(),
                     "demo": bestand.ist_demo(iid)},
        "artikel": protokoll._artikel(item, produkt, item["folder_id"]),
        # Bestandteil-Liste des Produkts (Schritt 25, F3 a) mit den Seriennummern dieses Artikels – der heutige Stand; was
        # am Prüftag galt, steht im jeweiligen Protokoll. Nicht in protokoll._artikel: sonst stünde es im Prüfprotokoll.
        "bestandteile": teilnummern.pdf_zeilen(item),
        "zustand": _zustand(item, produkt, s, tag, baum_pfad),
        "hinweis": _hinweis(item, s, aussonderung),
        "pruefungen": pruefungen,
        "durchgaenge": _durchgaenge(iid, baum_pfad),
        "rueckrufe": _rueckrufe(item),
        "ereignisse": journal_zeilen(list(reversed(eintraege)), verweise, mit_entitaet={"product"},
                                     maengel=_maengel(item)),
        "ereignisse_gekuerzt": gekuerzt,
    }


def kennung_vergeben(stand):
    """Die nächste Kennung L-<jahr>-<nr> (Jahr des Stands in deutscher Zeit) – in einer eigenen, kurzen
    Schreibtransaktion. Der Zähler steht in mat_meta; die höchste verzeichnete Nummer des Jahres zählt mit, falls er
    fehlt oder zurückliegt."""
    jahr = ortszeit(stand).year
    schluessel = ZAEHLER.format(jahr=jahr)
    vorsatz = f"{VORSATZ}-{jahr}-"
    with db.transaction(sofort=True):
        zeile = db.query("SELECT wert FROM mat_meta WHERE schluessel = ?", (schluessel,), one=True)
        hoechste = db.query("SELECT MAX(CAST(substr(kennung, ?) AS INTEGER)) AS n FROM mat_lebenslauf WHERE kennung LIKE ?",
                            (len(vorsatz) + 1, vorsatz + "%"), one=True)["n"] or 0
        n = max(int(zeile["wert"]) if zeile else 0, hoechste) + 1
        db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) "
                   "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, str(n)))
    return f"{vorsatz}{n:06d}"


def stempel_zeilen(kennung, n, summe):
    """Zwei Zeilen wie beim Protokoll (protokoll.stempel_zeilen), die Kennung vorn – jede bleibt unter
    pdf.STEMPEL_ZEICHEN."""
    return [f"{ART} {kennung} · {stempel.stempel_text(n, summe)}",
            f"nachrechnen: head -c {n} datei.pdf | sha256sum · prüfen: {protokoll.pruefseite()}"]


def rendern(iid):
    """(PDF als bytes, Inventarnummer, Kennung): setzen, Kennung vergeben, stempeln und in mat_lebenslauf verzeichnen.
    Die Datei selbst wird nicht gespeichert."""
    from . import pdf
    stand = db.now()
    d = daten(iid, stand)
    kennung = kennung_vergeben(stand)
    d["dokument"]["kennung"] = kennung
    basis = pdf.rendern("lebenslauf", d)
    n, summe = len(basis), stempel.sha256(basis)
    fertig = stempel.stempeln(basis, pdf.stempelvorlage(stempel_zeilen(kennung, n, summe)), kennung, art=ART)
    inventarnummer = d["artikel"]["inventarnummer"]
    with db.transaction(sofort=True):
        db.execute("INSERT INTO mat_lebenslauf (kennung, inventory_no, stand, pdf_sha256, pdf_hashed_bytes, file_sha256) "
                   "VALUES (?,?,?,?,?,?)", (kennung, inventarnummer, stand, summe, n, stempel.sha256(fertig)))
    return fertig, inventarnummer, kennung
