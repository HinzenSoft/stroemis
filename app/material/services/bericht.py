"""Jahresbericht je Zweig (Phase 4 · Lieferung 1, Entwurf Abschnitt A): ein Ordnerzweig – in der Regel die Gliederung –
für ein Kalenderjahr als Seite (JSON), PDF und CSV-Prüfungsliste. Empfänger: die Gliederung intern. Der Bericht ist kein
Prüfnachweis – Nachweise sind die Protokolle; er wird wie der Lebenslauf auf Abruf gesetzt und nicht festgeschrieben.

Menge und Zuordnung: Zum Zweig gehört, was heute seine Heimat (bestand.heimat) in ihm hat – wie Export und Durchgang –,
eingeschränkt auf das, was das Konto sieht (rechte.artikel_filter). Die Menge wird EINMAL je Anfrage gebildet und als
Liste der Kennungen (json_each) an alle Teilabfragen gereicht; keine Teilabfrage wiederholt die rekursive Ordner-CTE.
Gesperrte und ausgesonderte zählen damit bei ihrem Herkunftsordner (die Übersicht zeigt sie bei der Gliederung – die
Summe je Gliederung ist dieselbe). Artikel, die den Bereich verlassen haben, fehlen; hinzugekommene bringen ihre
Historie mit.

Zeitgrenzen: Datumsspalten (inspected_on, opened_on, closed_on, next_due_on, retire_by) mit BETWEEN über das
Kalenderjahr; UTC-Zeitstempel (mat_audit, mat_defect_report, mat_recall, mat_item.created_at) mit Grenzen aus
Europe/Berlin, in UTC umgerechnet (grenzen) – ein Journaleintrag am 31.12. um 23:30 UTC zählt zum Folgejahr.
Bestandszahlen gelten zum Stichtag heute (ein Status wird nie gespeichert), Ereigniszahlen für das Jahr.

Zählregeln (Kritiken S1–S24, A1–A19 zum Entwurf):
  - Prüfungen: kind <> 'aussonderung' (die Aussonderung aus einer Prüfung ist eine zweite Zeile mit basis_inspection_id
    und zählt nur im Aussonderungsblock); berichtigte Originale rundenunabhängig ausgeschlossen (OHNE_BERICHTIGTE);
    Entwürfe nur als Zahl.
  - Sperren aus dem Journal: nur der Übergang frei → gesperrt/verloren (before/after_json), unabhängig von der Aktion –
    eine Meldung am schon gesperrten Artikel zählt nicht. Hersteller-Sets (Schritt 21, Entscheidung A13/S13): Eine
    Set-Sperre zählt einmal – an dem Artikel mit eigenem Grund bzw. am Set-Artikel, wenn das Set aus eigenem Anlass sperrt
    (unvollständig, Teil getauscht – Art „set“; ebenso ein Teil, das beim Aussondern des Sets entnommen und gesperrt
    weitergeführt wird); die mitgesperrten Zeilen („set_gesperrt“) zählen nicht, ebenso wenig das
    Mitfreigeben („set_frei“) – frei gibt die Set-Prüfung am Set-Artikel („freigeprueft“). Ausgegeben wird nur lock_reason, nie ein Pfadtext aus dem
    Journal. Journalzeilen nur mit a.created_at >= i.created_at (Kennungen werden wiedervergeben).
  - Personen: ohne den Haken „Prüfer nennen“ enthält keine Ausgabe einen Personennamen oder eine Urkundennummer außer
    dem Ersteller – keine Melder, keine Durchgangs-Eröffner, keine Aussonderer, keine Zuordnungen.
  - DEMO-Artikel zählen mit und sind gekennzeichnet (Zahl im Kopf, Marke je Zeile, Spalte DEMO, Präfix „DEMO-“ im
    Dateinamen) – wie der CSV-Export; sonst wäre der Bericht auf dev leer.
  - Listen im PDF sind auf KAPPUNG Zeilen je Liste und KAPPUNG_GESAMT Zeilen im ganzen PDF gekürzt, die betroffenen
    Artikel eines Rückrufs auf KAPPUNG_RUECKRUF (die offenen zuerst) – ein Abruf hält sonst bei vielen laufenden
    Rückrufen einen Server-Thread lange fest (Sicherheitsprüfung B3). Seite und CSV kürzen nicht."""
import json
from datetime import date, datetime, timezone

from ... import db
from ..models import AUSSONDERUNGSGRUENDE, ERGEBNISSE, PRUEFARTEN
from . import ZONE, akteur, bestand, export, heute, katalog, mangel, protokoll, qr, rechte, rueckruf, ueberblick
from . import status as st
from .durchgang import AUS_DEM_BEREICH
from .protokoll import PRUEFART_TEXT, datum_text, zeit_text

EMPFAENGER = "Gliederung intern"
JAHR_MIN, JAHR_MAX = 1990, 2100
JAHRE_MAX = 15                      # so viele Jahre bietet die Auswahl höchstens an
KAPPUNG = 500                       # so viele Zeilen je Liste im PDF
KAPPUNG_GESAMT = 1500               # so viele Listenzeilen im ganzen PDF
KAPPUNG_RUECKRUF = 50               # so viele betroffene Artikel je Rückruf im PDF
# Die Sperrarten, wie sie aus dem Nachher eines Journaleintrags folgen (Reihenfolge der Ausgabe).
SPERRARTEN = (("pruefung", "aus Prüfung (instandsetzen)"), ("mangel", "aus Mangelmeldung"), ("verlust", "Verlust"),
              ("ohne_pruefung", "Sperre durch Prüfer ohne Prüfung"),
              ("set", "Set unvollständig, Teil getauscht oder Set ausgesondert"))
# Die Grundarten einer Aussonderung aus dem Präfix des Grundtexts (pruefung._wirkung bzw. AUSSONDERUNGSGRUENDE).
GRUNDARTEN = (("pruefung", "aus Prüfung (Ergebnis „aussondern“)"),) + tuple(AUSSONDERUNGSGRUENDE.items()) + (
    ("sonstiges", "sonstiger Grund"),)
# Spalten der CSV-Prüfungsliste – benannt wie export.VERZEICHNIS_SPALTEN, dazu Mängel und kritischer Mangel.
CSV_SPALTEN = ("Datum", "Art", "Prüfart", "Ergebnis", "Grund", "Inventarnummer", "Seriennummer", "Hersteller", "Modell",
               "Artikelnummer", "Kategorie", "Ordner", "Gliederung", "Prüfdurchgang", "Protokoll-ID", "Berichtigung von",
               "Mängel", "kritischer Mangel", "Prüfer", "Urkundennummer", "Bemerkung", "DEMO")
FUSS = ("Zahlen zum Stichtag; der Bericht ist kein Prüfnachweis – Nachweise sind die Protokolle.",
        "Bestandszahlen gelten zum Stichtag (heute), Ereigniszahlen für das Kalenderjahr; ein Status zum 31.12. lässt "
        "sich nicht rekonstruieren.",
        "Gesperrte und ausgesonderte Artikel zählen hier bei ihrem Herkunftsordner; die Übersicht zeigt sie bei der "
        "Gliederung – die Summe je Gliederung ist dieselbe.",
        "Zuordnung nach heutiger Heimat: Artikel, die den Bereich verlassen haben, fehlen; hinzugekommene bringen ihre "
        "Historie mit.",
        "Berichtigungen ändern Zahlen rückwirkend; Stand ist der Erstellungszeitpunkt.")

# Die Zweigmenge: einmal je Anfrage als Liste der Artikelkennungen (Parameter :zweig), siehe Kopf.
MENGE = "i.id IN (SELECT value FROM json_each(:zweig))"
# Prüfungen, die im Jahr zählen (x = mat_inspection): abgeschlossen, keine Aussonderung, Prüftag im Jahr, nicht durch
# eine abgeschlossene Berichtigung ersetzt – rundenunabhängig (durchgang.OHNE_BERICHTIGTE passt hier nicht).
OHNE_BERICHTIGTE = ("NOT EXISTS (SELECT 1 FROM mat_inspection b WHERE b.corrects_inspection_id = x.id "
                    "AND b.completed_at IS NOT NULL)")
PRUEFUNG_IM_JAHR = (f"x.completed_at IS NOT NULL AND x.kind <> 'aussonderung' AND x.inspected_on BETWEEN :d_von AND :d_bis "
                    f"AND {OHNE_BERICHTIGTE}")
AUSSONDERUNG_IM_JAHR = "x.completed_at IS NOT NULL AND x.kind = 'aussonderung' AND x.inspected_on BETWEEN :d_von AND :d_bis"
# Sperre = Übergang frei → gesperrt/verloren im Journal des Artikels (a = mat_audit, i = mat_item).
SPERRE = ("a.entity = 'item' AND a.entity_id = i.id AND a.created_at >= i.created_at "
          "AND json_extract(a.before_json, '$.lock_state') = 'frei' "
          "AND json_extract(a.after_json, '$.lock_state') IN ('gesperrt', 'verloren')")
IM_JAHR_UTC = "{spalte} >= :von AND {spalte} < :bis"


# --- Zeit und Menge -----------------------------------------------------------------------------------------------

def grenzen(jahr):
    """Parameter der Zeitgrenzen: d_von/d_bis für Datumsspalten (BETWEEN), von/bis für UTC-Zeitstempel im Format von
    db.now() – Jahresanfang und -anfang des Folgejahres in deutscher Zeit, nach UTC umgerechnet (sortiert als Text)."""
    def utc(j):
        return datetime(j, 1, 1, tzinfo=ZONE).astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return {"d_von": f"{jahr:04d}-01-01", "d_bis": f"{jahr:04d}-12-31", "von": utc(jahr), "bis": utc(jahr + 1)}


def _jahr_utc(iso):
    """Das deutsche Kalenderjahr eines UTC-Zeitstempels (für die Jahr-Auswahl)."""
    try:
        return datetime.fromisoformat(iso).astimezone(ZONE).year
    except (TypeError, ValueError):
        return None


def zweigmenge(fid, sicht):
    """Die Kennungen der Artikel des Zweigs, die das Konto sieht – einmal je Anfrage (siehe Kopf)."""
    bedingung, args = bestand.heimat_im_zweig(fid)
    return [r["id"] for r in db.query(
        f"SELECT i.id FROM mat_item i WHERE {bedingung} AND {rechte.artikel_filter('i', s=sicht)}", args)]


def jahre(ids, tag):
    """Die Jahr-Auswahl: vom frühesten Jahr aus Anlage (created_at, deutsches Jahr) und Prüftag bis heute, höchstens
    JAHRE_MAX Jahre; ohne Artikel oder Prüfung nur das laufende Jahr."""
    zweig = json.dumps(ids)
    r = db.query(f"SELECT MIN(i.created_at) AS angelegt, (SELECT MIN(x.inspected_on) FROM mat_inspection x "
                 f"WHERE x.item_id IN (SELECT value FROM json_each(:zweig))) AS geprueft FROM mat_item i WHERE {MENGE}",
                 {"zweig": zweig}, one=True)
    erstes = tag.year
    for j in (_jahr_utc(r["angelegt"]) if r and r["angelegt"] else None,
              int(r["geprueft"][:4]) if r and r["geprueft"] else None):
        if j and JAHR_MIN <= j < erstes:
            erstes = j
    erstes = max(erstes, tag.year - JAHRE_MAX + 1)
    return list(range(erstes, tag.year + 1))


# --- Blöcke -------------------------------------------------------------------------------------------------------

def _produkt(r):
    return katalog.produktname(r, r.get("product_description"))


def _ordnerzeilen(fid):
    """Die Ordner des Zweigs (Unterbaum) mit Oberordner, Art, Systemkennzeichen und DEMO – eine Abfrage."""
    rows = db.query(
        "WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f JOIN baum b ON f.parent_id = b.id) "
        f"SELECT f.id, f.parent_id, f.name, f.kind, f.system_kind, f.position, {bestand.demo_ordner_sql('f.id')} AS demo "
        "FROM mat_folder f JOIN baum ON baum.id = f.id", (fid,))
    return {o["id"]: o for o in rows}


def _bestand(fid, o, ordner, params):
    """Bestand zum Stichtag: Zeilen nach status.STATUS, verloren, DEMO, je Kategorie der obersten Ebene und je Unterordner
    der ersten Ebene nach Heimat – aus EINER Gruppierung über die Zweigmenge."""
    rows = db.query(
        f"SELECT {bestand.heimat_sql('i')} AS heimat, {st.status_sql('i')} AS s, i.lock_state, p.category_id, "
        f"{bestand.demo_sql('i', 'p')} AS demo, COUNT(*) AS n FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
        f"WHERE {MENGE} GROUP BY heimat, s, i.lock_state, p.category_id, demo", params)
    zaehlung, verloren, demo = st.leere_zaehlung(), 0, 0
    kategorien, ebene = {}, {}
    # Oberste Kategorieebene (parent_id leer) je Kategorie – eine Abfrage über alle Kategorien.
    alle_kat = {k["id"]: k for k in db.query("SELECT id, parent_id, name FROM mat_category")}

    def oberste(kid):
        gesehen = set()
        while kid in alle_kat and alle_kat[kid]["parent_id"] is not None and kid not in gesehen:
            gesehen.add(kid)
            kid = alle_kat[kid]["parent_id"]
        return alle_kat[kid]["name"] if kid in alle_kat else "(ohne Kategorie)"

    def erste_ebene(heimat):
        """Der Unterordner der ersten Ebene, in dem die Heimat liegt – None, wenn die Heimat der Zweig selbst ist."""
        x, gesehen = heimat, set()
        while x in ordner and ordner[x]["parent_id"] != fid and x != fid and x not in gesehen:
            gesehen.add(x)
            x = ordner[x]["parent_id"]
        return None if x == fid or x not in ordner else x

    for r in rows:
        zaehlung[r["s"]] += r["n"]
        if r["lock_state"] == "verloren":
            verloren += r["n"]
        if r["demo"]:
            demo += r["n"]
        if r["s"] != "ausgesondert":
            # Eine Kategorie nur mit Ausgesonderten bekommt keine Zeile (sie hätte nur Nullen).
            k = kategorien.setdefault(oberste(r["category_id"]), {"bestand": 0, "faellig": 0, "gesperrt": 0})
            k["bestand"] += r["n"]
            if r["s"] in bestand.FAELLIG:
                k["faellig"] += r["n"]
            if r["s"] == "gesperrt":
                k["gesperrt"] += r["n"]
        kind = erste_ebene(r["heimat"])
        heimat = ordner.get(r["heimat"])
        if kind is None:
            # Direkt im Zweig zu Hause – oder ohne Herkunftsordner in einem Systemordner des Zweigs selbst.
            schluessel = ("ohne_herkunft", 0) if heimat and heimat["system_kind"] else ("direkt", 0)
        elif ordner[kind]["system_kind"]:
            schluessel = ("ohne_herkunft", 0)
        else:
            schluessel = ("ordner", kind)
        z = ebene.setdefault(schluessel, st.leere_zaehlung())
        z[r["s"]] += r["n"]
    zeilen = []
    if ("direkt", 0) in ebene:
        zeilen.append(_ebenenzeile(f"{o['name']} (direkt)", "", bool(ordner[fid]["demo"]) if fid in ordner else False,
                                   ebene[("direkt", 0)]))
    kinder = sorted((k for k in ordner.values() if k["parent_id"] == fid and not k["system_kind"]),
                    key=lambda k: (k["position"], k["name"].casefold(), k["id"]))
    for k in kinder:
        if ("ordner", k["id"]) in ebene:
            zeilen.append(_ebenenzeile(k["name"], "Gliederung" if k["kind"] == "gliederung" else "", bool(k["demo"]),
                                       ebene[("ordner", k["id"])]))
    if ("ohne_herkunft", 0) in ebene:
        zeilen.append(_ebenenzeile(f"{o['name']} (ohne Herkunftsordner)", "", False, ebene[("ohne_herkunft", 0)]))
    return {"zaehlung": zaehlung, "zeilen": [{"status": s, "text": st.LABEL[s], "n": zaehlung[s]} for s in st.STATUS],
            "bestand": sum(zaehlung[s] for s in st.BESTAND), "verloren": verloren,
            "kategorien": [dict(name=n, **k) for n, k in sorted(kategorien.items(), key=lambda x: x[0].casefold())],
            "unterordner": zeilen}, demo


def _ebenenzeile(name, kennzeichen, demo, z):
    return {"name": name, "kennzeichen": kennzeichen, "demo": demo, "zaehlung": z,
            "bestand": sum(z[s] for s in st.BESTAND), "gesperrt": z["gesperrt"], "ausgesondert": z["ausgesondert"],
            "faellig": sum(z[s] for s in bestand.FAELLIG)}


def _bewegungen(ordner_ids, params):
    """Zugänge (Anlage im Jahr, Import eingeschlossen) und Gelöschte (Journal „geloescht“ eines Artikels, dessen Heimat im
    sichtbaren Zweig lag – der Artikel selbst ist weg, die Heimat steht im Vorher); Aussonderungen setzt daten() ein."""
    zugaenge = db.query(f"SELECT COUNT(*) AS n FROM mat_item i WHERE {MENGE} AND "
                        + IM_JAHR_UTC.format(spalte="i.created_at"), params, one=True)["n"]
    geloescht = db.query(
        "SELECT COUNT(*) AS n FROM mat_audit a WHERE a.entity = 'item' AND a.action = 'geloescht' AND "
        + IM_JAHR_UTC.format(spalte="a.created_at") +
        " AND (CASE WHEN json_extract(a.before_json, '$.lock_state') <> 'frei' "
        "AND json_extract(a.before_json, '$.origin_folder_id') IS NOT NULL "
        "THEN json_extract(a.before_json, '$.origin_folder_id') ELSE json_extract(a.before_json, '$.folder_id') END) "
        "IN (SELECT value FROM json_each(:ordner))", dict(params, ordner=json.dumps(ordner_ids)), one=True)["n"]
    return {"zugaenge": zugaenge, "geloescht": geloescht}


def _pruefungen(params):
    """Prüfungen im Jahr (PRUEFUNG_IM_JAHR): gesamt, je Prüfart, je Ergebnis, mit Mangel, mit kritischem Mangel, offene
    Entwürfe – und die Prüfabdeckung über den Bestand (ohne Ausgesonderte) mit der Liste der nicht geprüften."""
    rows = db.query(
        "SELECT x.kind, x.result, x.item_id, i.lock_state, "
        "EXISTS (SELECT 1 FROM mat_inspection_result r WHERE r.inspection_id = x.id AND r.finding = 'mangel') AS mangel, "
        "EXISTS (SELECT 1 FROM mat_inspection_result r WHERE r.inspection_id = x.id AND r.finding = 'mangel' "
        "AND r.is_critical = 1) AS kritisch "
        f"FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE {MENGE} AND {PRUEFUNG_IM_JAHR}", params)
    arten = {k: 0 for k in PRUEFARTEN if k != "aussonderung"}
    ergebnisse = {e: 0 for e in ERGEBNISSE}
    mit_mangel = kritisch = 0
    geprueft = set()
    for r in rows:
        arten[r["kind"]] = arten.get(r["kind"], 0) + 1
        ergebnisse[r["result"]] = ergebnisse.get(r["result"], 0) + 1
        mit_mangel += 1 if r["mangel"] else 0
        kritisch += 1 if r["kritisch"] else 0
        if r["lock_state"] != "ausgesondert":
            geprueft.add(r["item_id"])
    entwuerfe = db.query(f"SELECT COUNT(*) AS n FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE {MENGE} "
                         "AND x.completed_at IS NULL AND x.inspected_on BETWEEN :d_von AND :d_bis", params, one=True)["n"]
    nicht = db.query(
        "SELECT i.inventory_no, i.last_inspected_on, p.manufacturer, p.model, p.description AS product_description, "
        f"{bestand.demo_sql('i', 'p')} AS demo FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
        f"WHERE {MENGE} AND i.lock_state <> 'ausgesondert' AND NOT EXISTS (SELECT 1 FROM mat_inspection x "
        f"WHERE x.item_id = i.id AND {PRUEFUNG_IM_JAHR}) ORDER BY i.inventory_no", params)
    bestand_n = db.query(f"SELECT COUNT(*) AS n FROM mat_item i WHERE {MENGE} AND i.lock_state <> 'ausgesondert'",
                         params, one=True)["n"]
    return {"gesamt": len(rows),
            "arten": [{"art": k, "text": PRUEFART_TEXT.get(k, k), "n": n} for k, n in arten.items()],
            "ergebnisse": [{"ergebnis": e, "text": ERGEBNISSE.get(e, e), "n": n} for e, n in ergebnisse.items()],
            "mit_mangel": mit_mangel, "kritisch": kritisch, "entwuerfe": entwuerfe,
            "abdeckung": {"bestand": bestand_n, "geprueft": len(geprueft), "nicht_geprueft": len(nicht)},
            "nicht_geprueft": [{"inventarnummer": r["inventory_no"], "produkt": _produkt(r),
                                "letzte": datum_text(r["last_inspected_on"]) or "noch nie", "demo": bool(r["demo"])}
                               for r in nicht]}


def _durchgaenge(ordner_ids, params):
    """Prüfdurchgänge im Zweig (Ordner des Durchgangs im sichtbaren Unterbaum), die im Jahr eröffnet oder beendet wurden
    oder am 31.12. offen waren – Zahlen über round_id, Ausnahmen mit Grund; Artikel außerhalb der Zweigmenge ohne
    Inventarnummer (AUS_DEM_BEREICH); keine Namen."""
    p = dict(params, ordner=json.dumps(ordner_ids))
    runden = db.query(
        "SELECT r.id, r.title, r.opened_on, r.closed_on, r.aborted, r.protocol_id, "
        f"{bestand.demo_ordner_sql('r.folder_id')} AS demo, "
        "(SELECT COUNT(*) FROM mat_round_item ri WHERE ri.round_id = r.id) AS gesamt, "
        "(SELECT COUNT(*) FROM mat_round_item ri WHERE ri.round_id = r.id AND ri.excluded_reason IS NOT NULL) AS ausgenommen, "
        "(SELECT COUNT(DISTINCT x.item_id) FROM mat_inspection x WHERE x.round_id = r.id AND x.completed_at IS NOT NULL) "
        "AS erledigt FROM mat_round r WHERE r.folder_id IN (SELECT value FROM json_each(:ordner)) "
        "AND (r.opened_on BETWEEN :d_von AND :d_bis OR r.closed_on BETWEEN :d_von AND :d_bis "
        "OR (r.opened_on <= :d_bis AND (r.closed_on IS NULL OR r.closed_on > :d_bis))) ORDER BY r.opened_on, r.id", p)
    ausnahmen = {}
    if runden:
        for z in db.query(
                "SELECT ri.round_id, ri.excluded_reason, i.inventory_no, "
                "(i.id IN (SELECT value FROM json_each(:zweig))) AS im_zweig FROM mat_round_item ri "
                "JOIN mat_item i ON i.id = ri.item_id WHERE ri.excluded_reason IS NOT NULL "
                "AND ri.round_id IN (SELECT value FROM json_each(:runden)) ORDER BY ri.round_id, i.inventory_no",
                {"zweig": params["zweig"], "runden": json.dumps([r["id"] for r in runden])}):
            ausnahmen.setdefault(z["round_id"], []).append(
                {"inventarnummer": z["inventory_no"] if z["im_zweig"] else AUS_DEM_BEREICH, "grund": z["excluded_reason"]})
    out = []
    for r in runden:
        geschlossen = r["closed_on"] is not None
        offen = max(0, r["gesamt"] - r["erledigt"] - r["ausgenommen"])
        stand = ("abgebrochen" if r["aborted"] else "abgeschlossen") if geschlossen else "offen"
        out.append({"titel": r["title"], "stand": stand, "demo": bool(r["demo"]),
                    "zeitraum": (f"{datum_text(r['opened_on'])} bis {datum_text(r['closed_on'])}" if geschlossen
                                 else f"seit {datum_text(r['opened_on'])}, läuft"),
                    "gesamt": r["gesamt"], "erledigt": r["erledigt"], "ausgenommen": r["ausgenommen"],
                    "nicht_geprueft": offen if geschlossen else 0, "offen": 0 if geschlossen else offen,
                    "protokoll_id": r["protocol_id"] or "", "ausnahmen": ausnahmen.get(r["id"], [])})
    return out


def _pruefer(params):
    """Nur mit Haken: je (Name, Urkundennummer) die Zahl der Prüfungen; Aussonderungen durch – getrennt und ohne
    Urkundennummer (Materialwarte sondern aus)."""
    pruefer = db.query(
        "SELECT x.inspector_name AS name, x.inspector_certificate AS urkunde, COUNT(*) AS n FROM mat_inspection x "
        f"JOIN mat_item i ON i.id = x.item_id WHERE {MENGE} AND {PRUEFUNG_IM_JAHR} GROUP BY name, urkunde "
        "ORDER BY name COLLATE NOCASE, urkunde", params)
    aussonderer = db.query(
        "SELECT x.inspector_name AS name, COUNT(*) AS n FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id "
        f"WHERE {MENGE} AND {AUSSONDERUNG_IM_JAHR} GROUP BY name ORDER BY name COLLATE NOCASE", params)
    return {"pruefer": pruefer, "aussonderungen_durch": aussonderer}


def _sperren(params):
    """Sperren im Jahr aus dem Journal (SPERRE) mit Art aus dem Nachher; Ausgabe nur lock_reason. Dazu die Zahl der
    Freiprüfungen („wieder freigegeben“)."""
    rows = db.query(
        "SELECT a.created_at, i.inventory_no, json_extract(a.after_json, '$.lock_state') AS zustand, "
        "json_extract(a.after_json, '$.lock_reason') AS grund, "
        "json_extract(a.after_json, '$.pruefung') IS NOT NULL AS aus_pruefung, "
        "json_extract(a.after_json, '$.mangel') IS NOT NULL AS aus_mangel, "
        "json_extract(a.after_json, '$.set_grund') IS NOT NULL AS aus_set, "
        f"{bestand.demo_sql('i', 'p')} AS demo FROM mat_audit a JOIN mat_item i ON i.id = a.entity_id "
        f"JOIN mat_product p ON p.id = i.product_id WHERE {MENGE} AND {SPERRE} AND a.action <> 'set_gesperrt' AND "
        + IM_JAHR_UTC.format(spalte="a.created_at") + " ORDER BY a.created_at, a.id", params)
    arten = {k: 0 for k, _ in SPERRARTEN}
    liste = []
    for r in rows:
        # Ein Set-Anlass geht der Prüfung vor: Ein Teil, das beim Aussondern des Sets aus einer Prüfung entnommen und
        # gesperrt weitergeführt wird, trägt beides – gesperrt hat es das Aussondern, kein „instandsetzen“ (Ablauf N2).
        art = ("verlust" if r["zustand"] == "verloren" else "set" if r["aus_set"] else "pruefung" if r["aus_pruefung"]
               else "mangel" if r["aus_mangel"] else "ohne_pruefung")
        arten[art] += 1
        liste.append({"datum": datum_text(protokoll.ortszeit(r["created_at"]).date().isoformat()),
                      "inventarnummer": r["inventory_no"], "art": art, "art_text": dict(SPERRARTEN)[art],
                      "grund": r["grund"] or "", "demo": bool(r["demo"])})
    freigegeben = db.query(
        "SELECT COUNT(*) AS n FROM mat_audit a JOIN mat_item i ON i.id = a.entity_id "
        f"WHERE {MENGE} AND a.entity = 'item' AND a.action = 'freigeprueft' AND a.created_at >= i.created_at AND "
        + IM_JAHR_UTC.format(spalte="a.created_at"), params, one=True)["n"]
    return {"gesamt": len(rows), "arten": [{"art": k, "text": t, "n": arten[k]} for k, t in SPERRARTEN],
            "freigegeben": freigegeben, "liste": liste}


def _grundart(r):
    if r["basis_inspection_id"] or (r["reason"] or "").startswith("Prüfergebnis"):
        return "pruefung"
    for k, text in AUSSONDERUNGSGRUENDE.items():
        if (r["reason"] or "").startswith(text):
            return k
    return "sonstiges"


def _aussonderungen(params, pruefer_nennen):
    """Aussonderungen im Jahr (kind = 'aussonderung'): Liste mit Grund und Grundart aus dem Präfix; „durch“ nur mit
    Haken."""
    rows = db.query(
        "SELECT x.inspected_on, x.reason, x.inspector_name, x.basis_inspection_id, x.protocol_id, i.inventory_no, "
        f"p.manufacturer, p.model, p.description AS product_description, {bestand.demo_sql('i', 'p')} AS demo "
        "FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id JOIN mat_product p ON p.id = i.product_id "
        f"WHERE {MENGE} AND {AUSSONDERUNG_IM_JAHR} ORDER BY x.inspected_on, x.id", params)
    arten = {k: 0 for k, _ in GRUNDARTEN}
    liste = []
    for r in rows:
        art = _grundart(r)
        arten[art] += 1
        liste.append({"datum": datum_text(r["inspected_on"]), "inventarnummer": r["inventory_no"],
                      "produkt": _produkt(r), "grund": r["reason"] or "", "art": art, "art_text": dict(GRUNDARTEN)[art],
                      "protokoll_id": r["protocol_id"] or "", "durch": r["inspector_name"] if pruefer_nennen else "",
                      "demo": bool(r["demo"])})
    return {"gesamt": len(rows), "arten": [{"art": k, "text": t, "n": arten[k]} for k, t in GRUNDARTEN], "liste": liste}


def _maengel(params):
    """Mangelmeldungen: gemeldet im Jahr, davon heute offen (mangel.stand – auch „wieder offen“), erledigt durch
    Freiprüfung/Aussonderung; offene zum Stichtag als Liste ohne Meldernamen."""
    rows = db.query(
        "SELECT d.id, d.item_id, d.created_at, d.closed_at, d.closed_inspection_id, x.kind AS closed_kind, "
        f"{mangel.KANDIDAT} AS kandidat, i.inventory_no, {bestand.demo_sql('i', 'p')} AS demo "
        "FROM mat_defect_report d JOIN mat_item i ON i.id = d.item_id JOIN mat_product p ON p.id = i.product_id "
        f"LEFT JOIN mat_inspection x ON x.id = d.closed_inspection_id WHERE {MENGE} AND (("
        + IM_JAHR_UTC.format(spalte="d.created_at") + f") OR {mangel.OFFEN_SQL}) ORDER BY d.created_at, d.id", params)
    stand = mangel.stand(rows)
    gemeldet = offen_im_jahr = freipruefung = aussonderung = 0
    offen = []
    for r in rows:
        ist_offen = stand[r["id"]][0]
        im_jahr = params["von"] <= r["created_at"] < params["bis"]
        if im_jahr:
            gemeldet += 1
            if ist_offen:
                offen_im_jahr += 1
            elif r["closed_kind"] == "aussonderung":
                aussonderung += 1
            else:
                freipruefung += 1
        if ist_offen:
            offen.append({"inventarnummer": r["inventory_no"], "gemeldet": zeit_text(r["created_at"]),
                          "demo": bool(r["demo"])})
    return {"gemeldet": gemeldet, "offen": offen_im_jahr, "freipruefung": freipruefung, "aussonderung": aussonderung,
            "offen_stichtag": len(offen), "offen_liste": offen}


def _rueckrufe(params):
    """Rückrufe, die im Jahr angelegt oder beendet wurden oder heute laufen und vor Jahresende angelegt waren (ein
    später angelegter steht nicht im Bericht eines früheren Jahres), zu Produkten mit Artikeln im Bestand des Zweigs
    (ohne Ausgesonderte – sonst stünde dort „betroffen 0“) – mit Zahl und Liste der betroffenen Artikel im Zweig (Sicht);
    Titel und URL nur als Text."""
    rows = db.query(
        "SELECT r.*, p.manufacturer, p.model, p.description AS product_description FROM mat_recall r "
        "JOIN mat_product p ON p.id = r.product_id WHERE ((" + IM_JAHR_UTC.format(spalte="r.created_at") + ") OR ("
        + IM_JAHR_UTC.format(spalte="r.closed_at") + ") OR (r.closed_at IS NULL AND r.created_at < :bis)) "
        "AND EXISTS (SELECT 1 FROM mat_item i WHERE i.product_id = r.product_id AND i.lock_state <> 'ausgesondert' "
        f"AND {MENGE}) ORDER BY r.created_at, r.id", params)
    out = []
    for r in rows:
        alle = db.query(
            "SELECT i.id, i.inventory_no, i.serial_no, i.lock_state, (SELECT MAX(x.completed_at) FROM mat_inspection x "
            "WHERE x.item_id = i.id AND x.completed_at IS NOT NULL AND x.corrects_inspection_id IS NULL) AS geprueft_um, "
            f"{bestand.demo_sql('i', 'p')} AS demo FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
            f"WHERE i.product_id = :pid AND i.lock_state <> 'ausgesondert' AND {MENGE} ORDER BY i.inventory_no",
            {"pid": r["product_id"], "zweig": params["zweig"]})
        liste = rueckruf.betroffene(r, alle)
        out.append({"titel": r["title"], "produkt": _produkt(r), "angelegt": zeit_text(r["created_at"]),
                    "beendet": zeit_text(r["closed_at"]) if r["closed_at"] else "", "laeuft": r["closed_at"] is None,
                    "url": r["url"] or "", "alle": not rueckruf.serien(r),
                    "betroffen": len(liste), "offen": sum(1 for a in liste if a["zustand"] == "offen"),
                    "artikel": [{"inventarnummer": a["inventory_no"], "zustand": a["zustand"], "demo": bool(a["demo"])}
                                for a in liste]})
    return out


def _monate(tag):
    """Die zwölf Monate ab dem laufenden: (Schlüssel JJJJ-MM, Anfang, Ende) – der laufende beginnt mit dem Stichtag."""
    out = []
    j, m = tag.year, tag.month
    for _ in range(12):
        anfang = date(j, m, 1)
        j2, m2 = (j + 1, 1) if m == 12 else (j, m + 1)
        ende = date(j2, m2, 1).toordinal() - 1
        out.append((f"{j:04d}-{m:02d}", max(anfang, tag).isoformat(), date.fromordinal(ende).isoformat()))
        j, m = j2, m2
    return out


def _ausblick(params, zaehlung, tag):
    """Fälligkeiten je Monat (zwölf Monate ab dem Stichtag) nur für Status in ueberblick.NACH_DATUM, zweite Reihe
    Lebensende (textil) aus retire_by freier Artikel; davor die Zeile „jetzt“. Das Fenster beginnt mit dem Stichtag:
    Überfällige stehen nur in „jetzt“, nicht noch einmal im laufenden Monat."""
    monate = _monate(tag)
    p = dict(params, m_von=monate[0][1], m_bis=monate[-1][2])
    marken = ",".join(f"'{s}'" for s in ueberblick.NACH_DATUM)
    faellig = {r["m"]: r["n"] for r in db.query(
        f"SELECT substr(i.next_due_on, 1, 7) AS m, COUNT(*) AS n FROM mat_item i WHERE {MENGE} "
        f"AND {st.status_sql('i')} IN ({marken}) AND i.next_due_on BETWEEN :m_von AND :m_bis GROUP BY m", p)}
    ende = {r["m"]: r["n"] for r in db.query(
        f"SELECT substr(i.retire_by, 1, 7) AS m, COUNT(*) AS n FROM mat_item i WHERE {MENGE} AND i.lock_state = 'frei' "
        "AND i.retire_by BETWEEN :m_von AND :m_bis GROUP BY m", p)}
    return {"jetzt": {"ueberfaellig": zaehlung["ueberfaellig"], "neu": zaehlung["neu"], "gesperrt": zaehlung["gesperrt"]},
            "monate": [{"monat": k, "text": f"{k[5:7]}/{k[:4]}", "faellig": faellig.get(k, 0), "lebensende": ende.get(k, 0)}
                       for k, _, _ in monate]}


# --- Der Bericht --------------------------------------------------------------------------------------------------

def daten(fid, jahr, sicht=None, pruefer_nennen=False):
    """Alle Blöcke des Berichts für den Zweig fid und das Kalenderjahr jahr, fertig formatiert, für Seite, PDF und
    CSV. sicht: die Sicht des Kontos (rechte.sicht(), einmal je Anfrage); pruefer_nennen: der Haken „Prüfer nennen“ –
    ohne ihn kein Personenname und keine Urkundennummer außer dem Ersteller."""
    if not isinstance(jahr, int) or not JAHR_MIN <= jahr <= JAHR_MAX:
        raise ValueError(f"Jahr {jahr!r}")
    sicht = sicht or rechte.sicht()
    o = bestand.ordner(fid)
    tag = heute()
    ids = zweigmenge(fid, sicht)
    ordner = _ordnerzeilen(fid)
    # Die Ordner des Zweigs, die das Konto sieht – für Durchgänge (r.folder_id) und Gelöschte (Heimat im Vorher).
    ordner_ids = [f for f in ordner if sicht.darf("lesen", f)]
    # Zeitgrenzen, Zweigmenge und der Stichtag für status_sql (st_heute, st_bald) – ein Parametersatz für alle Blöcke.
    params = dict(grenzen(jahr), zweig=json.dumps(ids), **st.parameter(tag))
    bestand_block, demo = _bestand(fid, o, ordner, params)
    bewegungen = _bewegungen(ordner_ids, params)
    aussonderungen = _aussonderungen(params, pruefer_nennen)
    bewegungen["aussonderungen"] = aussonderungen["gesamt"]
    gl = bestand.gliederung_von(fid)
    _, ersteller = akteur()
    return {
        # Der Titel steht als Überschrift, im Fuß jeder Seite und in den PDF-Metadaten – mit „[DEMO]“, sobald DEMO-Artikel
        # enthalten sind.
        "dokument": {"art": "bericht", "titel": ("[DEMO] " if demo else "") + f"Jahresbericht Material {o['name']} {jahr}",
                     "stand": zeit_text(db.now()), "plattform": qr.anzeige(qr.basis()).split("://", 1)[-1],
                     "demo": demo > 0},
        "kopf": {"ordner_id": fid, "ordner": o["name"], "pfad": bestand._pfad_text(fid),
                 "gliederung": gl["name"] if gl else "", "jahr": jahr, "jahre": jahre(ids, tag),
                 "stichtag": datum_text(tag.isoformat()), "ersteller": ersteller, "erstellt_am": zeit_text(db.now()),
                 "empfaenger": EMPFAENGER, "pruefer_nennen": bool(pruefer_nennen), "artikel": len(ids), "demo": demo},
        "bestand": bestand_block,
        "bewegungen": bewegungen,
        "pruefungen": _pruefungen(params),
        "durchgaenge": _durchgaenge(ordner_ids, params),
        "pruefer": _pruefer(params) if pruefer_nennen else None,
        "sperren": _sperren(params),
        "aussonderungen": aussonderungen,
        "maengel": _maengel(params),
        "rueckrufe": _rueckrufe(params),
        "ausblick": _ausblick(params, bestand_block["zaehlung"], tag),
        "fuss": list(FUSS),
    }


def _name(o, jahr, demo, pruefer_nennen, vorsatz, endung):
    return (("DEMO-" if demo else "") + f"{vorsatz}_{export.dateiname(o['name'])}_{jahr}"
            + ("-mit-pruefern" if pruefer_nennen else "") + endung)


def _kappen(d):
    """Die Listen des PDF kürzen – je Liste auf KAPPUNG Zeilen, alle zusammen (in der Reihenfolge des PDF) auf
    KAPPUNG_GESAMT, die betroffenen Artikel eines Rückrufs auf KAPPUNG_RUECKRUF (die offenen zuerst); je Liste bleibt
    die Zahl der fehlenden Zeilen stehen. Zahlen bleiben vollständig."""
    budget = [KAPPUNG_GESAMT]

    def kappen(liste, grenze=KAPPUNG):
        n = min(grenze, budget[0], len(liste))
        budget[0] -= n
        return liste[:n], len(liste) - n
    d["pruefungen"]["nicht_geprueft"], d["pruefungen"]["gekappt"] = kappen(d["pruefungen"]["nicht_geprueft"])
    d["sperren"]["liste"], d["sperren"]["gekappt"] = kappen(d["sperren"]["liste"])
    d["aussonderungen"]["liste"], d["aussonderungen"]["gekappt"] = kappen(d["aussonderungen"]["liste"])
    d["maengel"]["offen_liste"], d["maengel"]["gekappt"] = kappen(d["maengel"]["offen_liste"])
    for r in d["durchgaenge"]:
        r["ausnahmen"], r["gekappt"] = kappen(r["ausnahmen"])
    for r in d["rueckrufe"]:
        r["artikel"], r["gekappt"] = kappen(sorted(r["artikel"], key=lambda a: a["zustand"] != "offen"),
                                            KAPPUNG_RUECKRUF)
    d["kappung"], d["kappung_gesamt"] = KAPPUNG, KAPPUNG_GESAMT
    return d


def pdf(fid, jahr, sicht=None, pruefer_nennen=False):
    """(PDF als bytes, Dateiname) – Vorlage templates/material/pdf/bericht.html, PDF/A-3b wie die Protokolle, nicht
    festgeschrieben; Listen gekürzt (_kappen)."""
    from . import pdf as pdf_dienst
    d = _kappen(daten(fid, jahr, sicht, pruefer_nennen))
    return (pdf_dienst.rendern("bericht", d),
            _name({"name": d["kopf"]["ordner"]}, jahr, d["dokument"]["demo"], pruefer_nennen, "Jahresbericht", ".pdf"))


def csv(fid, jahr, sicht=None, pruefer_nennen=False):
    """(CSV als bytes, Dateiname): die Prüfungen und Aussonderungen des Jahres im Zweig, eine Zeile je Vorgang –
    berichtigte Originale ausgeschlossen (wie die Zahlen; die Berichtigung nennt ihr Original), ohne Kappung, Spalten
    CSV_SPALTEN; Prüfer und Urkundennummer nur mit Haken, sonst leer; Formelschutz über export.csv_bytes."""
    sicht = sicht or rechte.sicht()
    o = bestand.ordner(fid)
    ids = zweigmenge(fid, sicht)
    params = dict(grenzen(jahr), zweig=json.dumps(ids))
    rows = db.query(
        "SELECT x.id, x.inspected_on, x.kind, x.result, x.reason, x.remarks, x.protocol_id, x.inspector_name, "
        "x.inspector_certificate, x.corrects_inspection_id, "
        "(SELECT o.protocol_id FROM mat_inspection o WHERE o.id = x.corrects_inspection_id) AS original_protokoll, "
        "(SELECT COUNT(*) FROM mat_inspection_result r WHERE r.inspection_id = x.id AND r.finding = 'mangel') AS maengel, "
        "EXISTS (SELECT 1 FROM mat_inspection_result r WHERE r.inspection_id = x.id AND r.finding = 'mangel' "
        "AND r.is_critical = 1) AS kritisch, r.title AS durchgang, i.inventory_no, i.serial_no, i.folder_id, "
        f"i.origin_folder_id, i.lock_state, {bestand.heimat_sql('i')} AS heimat, p.manufacturer, p.model, p.article_no, "
        f"p.category_id, {bestand.demo_sql('i', 'p')} AS demo FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id "
        "JOIN mat_product p ON p.id = i.product_id LEFT JOIN mat_round r ON r.id = x.round_id "
        f"WHERE {MENGE} AND (({PRUEFUNG_IM_JAHR}) OR ({AUSSONDERUNG_IM_JAHR})) ORDER BY x.inspected_on, x.id", params)
    baum, kategorien = export._ordnerbaum(), export._kategoriepfade()
    ohne = {"pfad": "", "gliederung": ""}
    zeilen = []
    demo = False
    for x in rows:
        demo = demo or bool(x["demo"])
        aus = x["kind"] == "aussonderung"
        ordner = baum.get(x["heimat"], ohne)
        zeilen.append([
            datum_text(x["inspected_on"]), "Aussonderungsprotokoll" if aus else "Prüfprotokoll",
            PRUEFART_TEXT.get(x["kind"], x["kind"]), ERGEBNISSE.get(x["result"], x["result"] or ""), x["reason"] or "",
            x["inventory_no"], x["serial_no"], x["manufacturer"], x["model"], x["article_no"] or "",
            kategorien.get(x["category_id"], ""), ordner["pfad"], ordner["gliederung"], x["durchgang"] or "",
            x["protocol_id"] or "", (x["original_protokoll"] or "(ohne Protokoll)") if x["corrects_inspection_id"] else "",
            "" if aus else x["maengel"], "" if aus else ("ja" if x["kritisch"] else "nein"),
            x["inspector_name"] if pruefer_nennen else "", (x["inspector_certificate"] or "") if pruefer_nennen else "",
            x["remarks"] or "", "ja" if x["demo"] else "nein"])
    return export.csv_bytes(CSV_SPALTEN, zeilen), _name(o, jahr, demo, pruefer_nennen, "Pruefungen", ".csv")
