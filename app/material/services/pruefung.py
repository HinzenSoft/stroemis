"""Prüfungen: Entwurf (zugleich Reservierung), Befunde je Prüfpunkt, Anhänge, Abschluss; Sperre ohne
Prüfung, Freiprüfung und Aussonderung.

Ablauf: Ein Prüfer startet die Prüfung eines Artikels – jederzeit, nicht erst wenn sie fällig ist. Es
entsteht ein Entwurf mit einer Kopie der Prüfpunkte des passenden Formulars (aktives spezifisches des
Produkts, sonst aktives generisches der Kategorie), jeder mit seinem Sollwert vorbelegt: Der Prüfer
ändert nur Abweichungen. Der Entwurf ist die Reservierung – höchstens einer je Artikel (eindeutiger
Index), die anderen sehen „in Prüfung bei …“. Eine liegen gebliebene Reservierung gibt der
Materialwart frei. Die erste Prüfung eines Artikels ist immer die Eingangsprüfung; bis sie
abgeschlossen ist, steht er auf „neu“.

Abschließen setzt Ergebnis, Sperrzustand und Fälligkeit (Unterschrift, PDF und Festschreiben folgen mit
Lieferung 3). Regeln dabei:
  - Jeder Pflichtpunkt hat einen Wert oder ist „nicht zutreffend“; jeder Mangel hat ein Foto.
  - Ein kritischer Punkt mit Mangel schließt „einsatzbereit“ aus, ebenso ein erreichtes Lebensende
    (nur textil – bei Metall entscheidet allein der Befund).
  - „instandsetzen“ und „aussondern“ ohne Mangel brauchen einen Grund.
  - Die nächste Fälligkeit (nur bei „einsatzbereit“) ist Prüftag + wirksames Intervall und lässt sich
    nur vorziehen.
  - „instandsetzen“ sperrt: Der Artikel wandert in „Gesperrt“ seiner Gliederung, der Herkunftsordner
    bleibt gemerkt. „einsatzbereit“ an einem gesperrten Artikel ist die Freiprüfung – sie bringt ihn
    zurück in den Herkunftsordner. „aussondern“ ist zugleich die Aussonderung (eigener Vorgang).

Wer handelt, kommt als „pruefer“-dict herein ({id, name, urkunde}) – aus dem angemeldeten Konto
(pruefer_aus) oder, für die Demodaten auf der Kommandozeile, von Hand."""
import json
from datetime import date

from flask import has_request_context

from ... import db
from ...images import delete_photo_files
from ..models import ANHANGARTEN, AUSSONDERUNGSGRUENDE, BEFUNDE, ERGEBNISSE, PRUEFARTEN, SPERRGRUENDE
from . import Abgelehnt, auswahl, datum, heute, text, wahr
from . import anhang as anh
from . import bestand, journal, katalog
from . import status as st
from .interval import plus_monate, wirksam

BEFUND_TEXT = {"ok": "in Ordnung", "mangel": "Mangel", "nicht_zutreffend": "nicht zutreffend"}
ABGESCHLOSSEN = "Die Prüfung ist abgeschlossen und lässt sich nicht mehr ändern."
URKUNDE_FEHLT = "Prüfen dürfen nur Prüfer mit hinterlegter Urkundennummer."


def pruefer_aus(user):
    """Der Prüfer aus dem angemeldeten Konto."""
    from .rechte import urkunde_saeubern
    return {"id": user["id"], "name": user["name"] or user["email"],
            "urkunde": urkunde_saeubern(user["urkundennummer"] or "")}


def _tag(d):
    return d.isoformat() if isinstance(d, date) else d


def _fmt(iso):
    """'2026-10-17' → '17.10.2026' für Meldungen."""
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return iso or ""


# --- Lesen --------------------------------------------------------------------------------------------

def pruefung(pid):
    p = db.query("SELECT * FROM mat_inspection WHERE id = ?", (pid,), one=True)
    if not p:
        raise Abgelehnt("Prüfung nicht gefunden.", 404)
    return p


def offener_entwurf(iid):
    return db.query("SELECT * FROM mat_inspection WHERE item_id = ? AND completed_at IS NULL", (iid,), one=True)


def befunde(pid):
    return db.query("SELECT * FROM mat_inspection_result WHERE inspection_id = ? ORDER BY position, id", (pid,))


def anhaenge(pid):
    return db.query("SELECT * FROM mat_inspection_attachment WHERE inspection_id = ? ORDER BY id", (pid,))


def reserviert_text(entwurf):
    return f"In Prüfung bei {entwurf['inspector_name'] or 'unbekannt'} seit {_fmt(entwurf['created_at'])}."


def arten_fuer(item):
    """(wählbare Prüfarten, Vorschlag). Ohne abgeschlossene Prüfung gibt es nur die Eingangsprüfung."""
    if not item.get("last_inspected_on"):
        return ["eingang"], "eingang"
    arten = ["periodisch", "ausserplanmaessig", "reparatur"]
    if item["lock_state"] in ("gesperrt", "verloren"):
        return arten, "reparatur"
    from . import durchgang
    if st.status(item) in ("ueberfaellig", "bald_faellig") or durchgang.offene_runde_fuer(item["id"]):
        return arten, "periodisch"
    return arten, "ausserplanmaessig"


def _intervall_ordner(item):
    """Gesperrte Artikel liegen in „Gesperrt“; ihr Intervall kommt aus dem Herkunftsordner, in den die
    Freiprüfung sie zurückbringt."""
    if item["lock_state"] in ("gesperrt", "verloren") and item["origin_folder_id"]:
        return item["origin_folder_id"]
    return item["folder_id"]


def _lebensdauer(item, produkt, tag):
    if produkt["material_kind"] != "textil" or not item["retire_by"]:
        return None
    rest = (date.fromisoformat(item["retire_by"]) - date.fromisoformat(tag)).days
    return {"ende": item["retire_by"], "rest_tage": rest, "erreicht": rest <= 0}


def befund_json(r):
    foto = None
    if r["photo"]:
        foto = {"web": katalog.bild_url(r["photo"]), "vorschau": katalog.bild_url(r["photo"], "thumb"),
                "original": katalog.bild_url(r["photo"], "orig")}
    return {"id": r["id"], "position": r["position"], "gruppe": r["group_name"], "text": r["checklist_text"],
            "art": r["editor"], "pflicht": bool(r["mandatory"]), "soll": r["expected_value"],
            "kritisch": bool(r["is_critical"]), "befund": r["finding"], "wert": r["value"], "notiz": r["note"],
            "foto": foto}


def anhang_json(a):
    return {"id": a["id"], "art": a["kind"], "art_text": ANHANGARTEN.get(a["kind"], a["kind"]), "titel": a["title"],
            "datei": f"/media/material/anhang/{a['file_path']}", "seiten": a["pages"], "sha256": a["sha256"],
            "im_protokoll": bool(a["in_pdf"]), "von": a["uploaded_by_name"], "am": a["uploaded_at"]}


def kurz_json(p):
    """Eine Zeile für Listen (Lebenslauf, offene Prüfungen)."""
    return {"id": p["id"], "item_id": p["item_id"], "round_id": p["round_id"], "art": p["kind"],
            "art_text": PRUEFARTEN.get(p["kind"], p["kind"]), "datum": p["inspected_on"],
            "pruefer": p["inspector_name"], "pruefer_id": p["inspector_user_id"], "urkunde": p["inspector_certificate"],
            "ergebnis": p["result"], "ergebnis_text": ERGEBNISSE.get(p["result"], "") if p["result"] else "",
            "grund": p["reason"], "bemerkung": p["remarks"], "naechste": p["next_due_on"],
            "entwurf": p["completed_at"] is None, "abgeschlossen_am": p["completed_at"], "begonnen_am": p["created_at"],
            "basis_id": p["basis_inspection_id"]}


def pruefung_json(p, pruefer_id=None):
    item = bestand.artikel(p["item_id"])
    produkt = katalog.produkt(item["product_id"])
    out = kurz_json(p)
    out["eigen"] = bool(pruefer_id) and p["inspector_user_id"] == pruefer_id
    out["artikel"] = bestand.artikel_kurz(item)
    out["artikel"]["pfad"] = bestand.pfad(item["folder_id"])
    out["artikel"]["origin_folder_id"] = item["origin_folder_id"]
    out["produkt"] = {"id": produkt["id"], "name": f"{produkt['manufacturer']} {produkt['model']}".strip(),
                      "article_no": produkt["article_no"], "norm": produkt["norm"],
                      "material_kind": produkt["material_kind"], "demo": bool(produkt["demo"])}
    out["formular"] = None
    if p["form_id"]:
        f = db.query("SELECT id, version, title FROM mat_form WHERE id = ?", (p["form_id"],), one=True)
        out["formular"] = {"id": p["form_id"], "version": p["form_version"], "titel": f["title"] if f else ""}
    punkte = befunde(p["id"])
    out["punkte"] = [befund_json(r) for r in punkte]
    out["anhaenge"] = [anhang_json(a) for a in anhaenge(p["id"])]
    out["durchgang"] = None
    if p["round_id"]:
        r = db.query("SELECT id, title, closed_on FROM mat_round WHERE id = ?", (p["round_id"],), one=True)
        if r:
            out["durchgang"] = {"id": r["id"], "titel": r["title"], "offen": r["closed_on"] is None}
    out["dokumente"] = json.loads(p["documents_json"] or "[]")
    tag = heute().isoformat() if out["entwurf"] else p["inspected_on"]
    out["lebensdauer"] = _lebensdauer(item, produkt, tag)
    if out["entwurf"]:
        iv = wirksam(produkt, _intervall_ordner(item), item["interval_months"])
        out["intervall"] = iv
        out["vorschlag_naechste"] = plus_monate(date.fromisoformat(tag), iv["monate"]).isoformat() if iv["monate"] else None
        kritisch = [r["checklist_text"] for r in punkte if r["finding"] == "mangel" and r["is_critical"]]
        gruende = []
        if kritisch:
            gruende.append("kritischer Mangel: " + "; ".join(kritisch))
        if out["lebensdauer"] and out["lebensdauer"]["erreicht"]:
            gruende.append(f"Lebensende erreicht am {_fmt(out['lebensdauer']['ende'])}")
        out["einsatzbereit_gesperrt"] = gruende
        out["freipruefung"] = item["lock_state"] in ("gesperrt", "verloren")
        out["arten"] = arten_fuer(item)[0]
    return out


def fuer_artikel(iid):
    """Alle Prüfungen und Aussonderungen eines Artikels, neueste zuerst – der Prüfteil des Lebenslaufs."""
    rows = db.query("SELECT * FROM mat_inspection WHERE item_id = ? "
                    "ORDER BY completed_at IS NOT NULL, inspected_on DESC, id DESC", (iid,))
    return [kurz_json(r) for r in rows]


def entwuerfe(pruefer_id=None):
    """Offene Prüfungen (Reservierungen) mit Artikel – die eigenen zuerst, dann die ältesten."""
    offen = db.query("SELECT * FROM mat_inspection WHERE completed_at IS NULL "
                     "ORDER BY (inspector_user_id IS ?) DESC, created_at", (pruefer_id or -1,))
    if not offen:
        return []
    ids = [x["item_id"] for x in offen]
    artikel = {r["id"]: r for r in db.query(bestand.ARTIKEL_LISTE_SQL + f"WHERE i.id IN ({','.join('?' * len(ids))})",
                                            ids)}
    out = []
    for x in offen:
        k = kurz_json(x)
        k["eigen"] = bool(pruefer_id) and x["inspector_user_id"] == pruefer_id
        k["artikel"] = bestand.artikel_kurz(artikel[x["item_id"]])
        k["artikel"]["pfad"] = bestand._pfad_text(artikel[x["item_id"]]["folder_id"])
        out.append(k)
    return out


# --- Entwurf ------------------------------------------------------------------------------------------

def _vorbelegung(punkt):
    """(Befund, Wert) eines frischen Prüfpunkts: Befund „in Ordnung“ und der Sollwert, denn das ist der
    Normalfall. Bei Text und Zahl ist das Soll seit Lieferung 1 ein Hinweis („max. 22 mm“) – den
    übernimmt kein Wert, er steht nur als Platzhalter im Feld. Einzig ein Soll, das selbst eine Zahl ist,
    gilt bei Zahlpunkten als Sollwert."""
    if punkt["editor"] == "yesno":
        return "ok", punkt["expected_value"]
    if punkt["editor"] == "number" and _ist_zahl(punkt["expected_value"]):
        return "ok", punkt["expected_value"].strip()
    return "ok", ""


def _ist_zahl(s):
    s = (s or "").strip().replace(" ", "").replace(",", ".")
    try:
        float(s)
        return bool(s)
    except ValueError:
        return False


def starten(iid, pruefer, art=None, durchgang_id=None):
    """Entwurf anlegen – oder den eigenen offenen zurückgeben. Liefert (Prüfungs-ID, neu angelegt?)."""
    from . import durchgang
    if not pruefer.get("urkunde"):
        raise Abgelehnt(URKUNDE_FEHLT, 403)
    with db.transaction(sofort=True):
        item = bestand.artikel(iid)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Ein ausgesonderter Artikel wird nicht mehr geprüft.", 409)
        offen = offener_entwurf(iid)
        if offen:
            if _eigen(offen, pruefer):
                return offen["id"], False
            raise Abgelehnt(reserviert_text(offen) + " Eine liegen gebliebene Reservierung gibt der Materialwart frei.",
                            409)
        arten, vorschlag = arten_fuer(item)
        art = art or vorschlag
        if art not in arten:
            if arten == ["eingang"]:
                raise Abgelehnt("Die erste Prüfung eines Artikels ist die Eingangsprüfung.")
            raise Abgelehnt(f"Prüfart „{art}“ ist hier nicht wählbar ({', '.join(PRUEFARTEN[a] for a in arten)}).")
        formular = katalog.formular_fuer_produkt(item["product_id"])
        if not formular:
            raise Abgelehnt("Für dieses Produkt gibt es kein aktives Prüfformular – weder am Produkt noch in "
                            "seiner Kategorie. Der Produktkatalogpfleger legt es im Katalog an.", 409)
        punkte = katalog.punkte(formular["id"])
        if durchgang_id:
            runde = durchgang.runde_fuer_start(durchgang_id, iid)
        else:
            runde = durchgang.offene_runde_fuer(iid)
        ts = db.now()
        pid = db.execute(
            "INSERT INTO mat_inspection (item_id, round_id, inspector_user_id, inspector_name, inspector_certificate, "
            "form_id, form_version, inspected_on, kind, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (iid, runde, pruefer.get("id"), pruefer["name"], pruefer["urkunde"], formular["id"], formular["version"],
             heute().isoformat(), art, ts, ts))
        for p in punkte:
            befund, wert = _vorbelegung(p)
            db.execute("INSERT INTO mat_inspection_result (inspection_id, checklist_item_id, position, group_name, "
                       "checklist_text, editor, mandatory, expected_value, is_critical, finding, value) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (pid, p["id"], p["position"], p["group_name"], p["label"], p["editor"], p["mandatory"],
                        p["expected_value"], p["is_critical"], befund, wert))
        journal.eintragen("inspection", pid, "begonnen", None,
                          {"item_id": iid, "kind": art, "form_id": formular["id"], "form_version": formular["version"],
                           "round_id": runde})
    return pid, True


def _eigen(p, pruefer):
    """Gehört der Entwurf diesem Prüfer? Über die Schnittstelle zählt allein die Kontokennung. Ohne Anfrage
    (Demodaten auf der Kommandozeile) gibt es kein Konto – dort gehört ein Entwurf ohne Konto dem Lauf."""
    if pruefer.get("id"):
        return p["inspector_user_id"] == pruefer["id"]
    return not has_request_context() and p["inspector_user_id"] is None


def _entwurf_des(pid, pruefer):
    """Der Entwurf, an dem dieser Prüfer arbeiten darf – sonst eine klare Absage."""
    p = pruefung(pid)
    if p["completed_at"]:
        raise Abgelehnt(ABGESCHLOSSEN, 409)
    if not _eigen(p, pruefer):
        raise Abgelehnt(f"Diese Prüfung gehört {p['inspector_name'] or 'jemand anderem'} – nur der Prüfer selbst "
                        "arbeitet daran weiter.", 403)
    return p


def _beruehrt(pid):
    db.execute("UPDATE mat_inspection SET updated_at = ? WHERE id = ?", (db.now(), pid))


def _befund(pid, rid):
    r = db.query("SELECT * FROM mat_inspection_result WHERE id = ? AND inspection_id = ?", (rid, pid), one=True)
    if not r:
        raise Abgelehnt("Prüfpunkt nicht gefunden.", 404)
    return r


def _zahl(wert, name):
    s = (wert or "").strip().replace(" ", "")
    if not s:
        return ""
    try:
        float(s.replace(",", "."))
    except ValueError:
        raise Abgelehnt(f"„{name}“ ist keine Zahl.")
    if len(s) > 30:
        raise Abgelehnt(f"„{name}“ ist zu lang.")
    return s


def punkt_setzen(pid, rid, d, pruefer):
    """Befund eines Prüfpunkts ändern. Ja/Nein: Wert „ja“/„nein“ – weicht er vom Soll ab, ist das ein Mangel;
    befund „nicht_zutreffend“ nimmt den Punkt heraus. Andere Arten: Wert und Befund (ok, mangel,
    nicht_zutreffend) getrennt. Was die Anfrage nicht nennt, bleibt."""
    with db.transaction(sofort=True):
        _entwurf_des(pid, pruefer)
        r = _befund(pid, rid)
        art = r["editor"]
        if art == "signature":
            raise Abgelehnt("Unterschriftsfelder kommen mit Lieferung 3.", 409)
        befund, wert, notiz = r["finding"], r["value"], r["note"]
        if "notiz" in d:
            notiz = text(d, "notiz", "Bemerkung zum Prüfpunkt", 1000, einzeilig=False)
        if art == "yesno":
            # Der Befund folgt aus dem Wert: Weicht er vom Soll ab, ist das ein Mangel.
            if d.get("befund") == "nicht_zutreffend":
                befund, wert = "nicht_zutreffend", ""
            elif "wert" in d:
                wert = auswahl(d.get("wert"), ("ja", "nein"), "Wert")
                befund = "ok" if wert == r["expected_value"] else "mangel"
            elif "befund" in d:
                befund = auswahl(d.get("befund"), ("ok", "mangel"), "Befund")
                gegenteil = "nein" if r["expected_value"] == "ja" else "ja"
                wert = r["expected_value"] if befund == "ok" else gegenteil
        elif "befund" in d:
            befund = auswahl(d.get("befund"), BEFUNDE, "Befund")
        if art != "yesno" and "wert" in d:
            if art == "date":
                wert = datum(d.get("wert"), r["checklist_text"]) or ""
            elif art == "number":
                wert = _zahl(d.get("wert") if isinstance(d.get("wert"), str) else str(d.get("wert") or ""),
                             r["checklist_text"])
            elif art == "text":
                wert = text(d, "wert", r["checklist_text"], 1000, einzeilig=False)
            else:
                raise Abgelehnt("Dieser Prüfpunkt nimmt ein Foto auf, keinen Wert.")
        db.execute("UPDATE mat_inspection_result SET finding = ?, value = ?, note = ? WHERE id = ?",
                   (befund, wert, notiz, rid))
        _beruehrt(pid)
    return befund_json(_befund(pid, rid))


def punkt_foto_setzen(pid, rid, file_storage, pruefer):
    _entwurf_des(pid, pruefer)
    alt = _befund(pid, rid)
    if alt["editor"] == "signature":
        raise Abgelehnt("Unterschriftsfelder kommen mit Lieferung 3.", 409)
    neu = katalog.foto_ablegen(file_storage, vorschau_ganz=True)
    try:
        with db.transaction(sofort=True):
            _entwurf_des(pid, pruefer)            # unter der Sperre noch einmal: inzwischen abgeschlossen?
            if not db.execute_zeilen("UPDATE mat_inspection_result SET photo = ? WHERE id = ? AND photo = ?",
                                     (neu, rid, alt["photo"])):
                raise Abgelehnt("Das Foto wurde zwischenzeitlich geändert. Bitte neu laden.", 409)
            _beruehrt(pid)
    except BaseException:
        delete_photo_files(katalog.medien_dir(), neu)       # auch bei Sperrzeitüberschreitung kein Waisenfoto
        raise
    if alt["photo"]:
        delete_photo_files(katalog.medien_dir(), alt["photo"])
    return befund_json(_befund(pid, rid))


def punkt_foto_entfernen(pid, rid, pruefer):
    with db.transaction(sofort=True):
        _entwurf_des(pid, pruefer)
        alt = _befund(pid, rid)
        if not alt["photo"]:
            return befund_json(alt)
        db.execute("UPDATE mat_inspection_result SET photo = '' WHERE id = ?", (rid,))
        _beruehrt(pid)
    delete_photo_files(katalog.medien_dir(), alt["photo"])
    return befund_json(_befund(pid, rid))


def kopf_setzen(pid, d, pruefer):
    """Prüfart, Bemerkung und Grund am Entwurf (Ergebnis und Fälligkeit setzt erst der Abschluss)."""
    with db.transaction(sofort=True):
        p = _entwurf_des(pid, pruefer)
        art = p["kind"]
        if "art" in d:
            arten = arten_fuer(bestand.artikel(p["item_id"]))[0]
            art = auswahl(d.get("art"), arten, "Prüfart")
        bemerkung = text(d, "bemerkung", "Bemerkung", 4000, einzeilig=False) if "bemerkung" in d else p["remarks"]
        grund = text(d, "grund", "Grund", 300) if "grund" in d else p["reason"]
        db.execute("UPDATE mat_inspection SET kind = ?, remarks = ?, reason = ?, updated_at = ? WHERE id = ?",
                   (art, bemerkung, grund, db.now(), pid))


def anhang_hinzufuegen(pid, d, dateien, pruefer):
    """Ein Anhang aus einer oder mehreren Dateien (Fotos eines Scans und/oder PDFs) – immer ein PDF."""
    _entwurf_des(pid, pruefer)
    art = auswahl(d.get("art") or "externes_pruefformular", ANHANGARTEN, "Art des Anhangs")
    titel = text(d, "titel", "Titel", 160) or ANHANGARTEN[art]
    im_protokoll = wahr(d, "im_protokoll", "ans Protokoll anhängen")
    roh, gesamt = [], 0
    for f in dateien:
        if not f or not f.filename:
            continue
        daten = f.read(anh.MAX_BYTES + 1)
        gesamt += len(daten)
        if gesamt > anh.MAX_BYTES:
            raise Abgelehnt(f"Zusammen höchstens {anh.MAX_BYTES // (1024 * 1024)} MB je Anhang.")
        roh.append((f.filename, daten))
    pdf, seiten = anh.zusammenfassen(roh)
    name, summe = anh.ablegen(katalog.medien_dir(), pdf)
    uid, uname = pruefer.get("id"), pruefer["name"]
    try:
        with db.transaction(sofort=True):
            _entwurf_des(pid, pruefer)
            aid = db.execute("INSERT INTO mat_inspection_attachment (inspection_id, kind, title, file_path, mime, pages, "
                             "sha256, uploaded_by, uploaded_by_name, uploaded_at, in_pdf) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (pid, art, titel, name, "application/pdf", seiten, summe, uid, uname, db.now(),
                              int(im_protokoll)))
            journal.eintragen("inspection", pid, "anhang", None,
                              {"title": titel, "kind": art, "seiten": seiten, "sha256": summe, "dateien": len(roh)})
            _beruehrt(pid)
    except BaseException:
        anh.entfernen(katalog.medien_dir(), name)
        raise
    return anhang_json(db.query("SELECT * FROM mat_inspection_attachment WHERE id = ?", (aid,), one=True))


def anhang_entfernen(pid, aid, pruefer):
    with db.transaction(sofort=True):
        _entwurf_des(pid, pruefer)
        a = db.query("SELECT * FROM mat_inspection_attachment WHERE id = ? AND inspection_id = ?", (aid, pid), one=True)
        if not a:
            raise Abgelehnt("Anhang nicht gefunden.", 404)
        db.execute("DELETE FROM mat_inspection_attachment WHERE id = ?", (aid,))
        journal.eintragen("inspection", pid, "anhang_entfernt", {"title": a["title"], "sha256": a["sha256"]}, None)
        _beruehrt(pid)
    anh.entfernen(katalog.medien_dir(), a["file_path"])


def verwerfen(pid, akteur, darf_freigeben=False):
    """Entwurf löschen: der eigene (verwerfen) oder – als Materialwart – eine fremde Reservierung freigeben."""
    with db.transaction(sofort=True):
        p = pruefung(pid)
        if p["completed_at"]:
            raise Abgelehnt(ABGESCHLOSSEN, 409)
        eigen = _eigen(p, akteur)
        if not eigen and not darf_freigeben:
            raise Abgelehnt("Eine fremde Reservierung gibt nur der Materialwart frei.", 403)
        fotos = [r["photo"] for r in befunde(pid) if r["photo"]]
        dateien = [a["file_path"] for a in anhaenge(pid)]
        db.execute("DELETE FROM mat_inspection_result WHERE inspection_id = ?", (pid,))
        db.execute("DELETE FROM mat_inspection_attachment WHERE inspection_id = ?", (pid,))
        db.execute("DELETE FROM mat_inspection WHERE id = ?", (pid,))
        journal.eintragen("inspection", pid, "verworfen" if eigen else "reservierung_freigegeben",
                          {"item_id": p["item_id"], "kind": p["kind"], "inspector_name": p["inspector_name"],
                           "begonnen": p["created_at"]}, None)
        journal.eintragen("item", p["item_id"], "verworfen" if eigen else "reservierung_freigegeben",
                          {"pruefung": pid, "pruefer": p["inspector_name"]}, None)
    for f in fotos:
        delete_photo_files(katalog.medien_dir(), f)
    for f in dateien:
        anh.entfernen(katalog.medien_dir(), f)


# --- Abschluss -----------------------------------------------------------------------------------------

def _beantwortet(r):
    if r["finding"] == "nicht_zutreffend":
        return True
    if r["editor"] == "photo":
        return bool(r["photo"])
    if r["editor"] == "signature":
        return True                      # Unterschriftsfelder: Lieferung 3
    return bool((r["value"] or "").strip())


def abschliessen(pid, d, pruefer, pruefdatum=None):
    """Ergebnis festlegen. pruefdatum nur für Demodaten und Tests – über die Schnittstelle gilt heute."""
    if not pruefer.get("urkunde"):
        raise Abgelehnt(URKUNDE_FEHLT, 403)
    ergebnis = auswahl(d.get("ergebnis"), ERGEBNISSE, "Ergebnis")
    with db.transaction(sofort=True):
        p = _entwurf_des(pid, pruefer)
        item = bestand.artikel(p["item_id"])
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel wurde inzwischen ausgesondert.", 409)
        produkt = katalog.produkt(item["product_id"])
        tag = _tag(pruefdatum or heute())
        punkte = befunde(pid)
        offen = [r["checklist_text"] for r in punkte if r["mandatory"] and not _beantwortet(r)]
        if offen:
            raise Abgelehnt("Noch ohne Befund: " + "; ".join(offen[:5]) + (" …" if len(offen) > 5 else ""))
        ohne_foto = [r["checklist_text"] for r in punkte if r["finding"] == "mangel" and not r["photo"]]
        if ohne_foto:
            raise Abgelehnt("Jeder Mangel braucht ein Foto – es fehlt bei: " + "; ".join(ohne_foto[:5]))
        maengel = [r for r in punkte if r["finding"] == "mangel"]
        kritisch = [r["checklist_text"] for r in maengel if r["is_critical"]]
        lebensdauer = _lebensdauer(item, produkt, tag)
        grund = text(d, "grund", "Grund", 300) if "grund" in d else p["reason"]
        bemerkung = text(d, "bemerkung", "Bemerkung", 4000, einzeilig=False) if "bemerkung" in d else p["remarks"]
        naechste = None
        if ergebnis == "einsatzbereit":
            grund = ""                          # ein Grund gehört zu Sperre und Aussonderung, nicht zur Freigabe
            if kritisch:
                raise Abgelehnt("Kritischer Mangel (" + "; ".join(kritisch[:3]) + ") – „einsatzbereit“ ist ausgeschlossen. "
                                "Bitte „instandsetzen“ oder „aussondern“ wählen.")
            if lebensdauer and lebensdauer["erreicht"]:
                raise Abgelehnt(f"Das Lebensende ist erreicht ({_fmt(lebensdauer['ende'])}) – „einsatzbereit“ ist "
                                "nicht mehr wählbar.")
            iv = wirksam(produkt, _intervall_ordner(item), item["interval_months"])
            if not iv["monate"]:
                raise Abgelehnt(katalog.KEIN_INTERVALL)
            spaetestens = plus_monate(date.fromisoformat(tag), iv["monate"]).isoformat()
            naechste = datum(d.get("next_due_on"), "Nächste Prüfung") or spaetestens
            if naechste > spaetestens:
                raise Abgelehnt(f"Die nächste Prüfung lässt sich nur vorziehen, nicht verschieben (spätestens "
                                f"{_fmt(spaetestens)}, {iv['monate']} Monate ab Prüftag).")
            if naechste <= tag:
                raise Abgelehnt("Die nächste Prüfung muss nach dem Prüftag liegen.")
        elif not maengel and not grund:
            raise Abgelehnt(f"Ohne Mangel braucht „{ERGEBNISSE[ergebnis]}“ einen Grund.")
        dokumente = [{"id": x["id"], "title": x["title"], "kind": x["kind"], "version": x["version"],
                      "valid_from": x["valid_from"], "sha256": x["sha256"],
                      "kategorie": x["herkunft"]["name"] if x.get("herkunft") else None}
                     for x in katalog.gueltige_dokumente(produkt["id"], tag)]
        ts = db.now()
        db.execute("UPDATE mat_inspection SET result = ?, inspected_on = ?, next_due_on = ?, reason = ?, remarks = ?, "
                   "inspector_name = ?, inspector_certificate = ?, documents_json = ?, completed_at = ?, updated_at = ? "
                   "WHERE id = ?",
                   (ergebnis, tag, naechste, grund, bemerkung, pruefer["name"], pruefer["urkunde"],
                    json.dumps(dokumente, ensure_ascii=False), ts, ts, pid))
        journal.eintragen("inspection", pid, "abgeschlossen", None,
                          {"result": ergebnis, "inspected_on": tag, "next_due_on": naechste, "kind": p["kind"],
                           "maengel": len(maengel), "reason": grund})
        _wirkung(item, p, ergebnis, tag, naechste, grund, pruefer)
    return pid


def _wirkung(item, p, ergebnis, tag, naechste, grund, pruefer):
    """Was das Ergebnis am Artikel bewirkt – in der Transaktion des Abschlusses."""
    iid = item["id"]
    gesperrt = item["lock_state"] in ("gesperrt", "verloren")
    vorher = {"lock_state": item["lock_state"], "next_due_on": item["next_due_on"],
              "last_inspected_on": item["last_inspected_on"], "folder_id": item["folder_id"],
              "ordner": bestand._pfad_text(item["folder_id"])}
    if ergebnis == "einsatzbereit":
        ziel = item["folder_id"]
        if gesperrt:
            ziel = _rueckweg(item)
        db.execute("UPDATE mat_item SET lock_state = 'frei', lock_reason = '', origin_folder_id = NULL, folder_id = ?, "
                   "next_due_on = ?, last_inspected_on = ?, updated_at = ? WHERE id = ?",
                   (ziel, naechste, tag, db.now(), iid))
        nachher = {"lock_state": "frei", "next_due_on": naechste, "last_inspected_on": tag, "folder_id": ziel,
                   "ordner": bestand._pfad_text(ziel)}
        alt, neu = journal.unterschied(vorher, nachher)
        journal.eintragen("item", iid, "freigeprueft" if gesperrt else "geprueft",
                          alt, dict(neu, pruefung=p["id"], ergebnis=ergebnis, art=p["kind"]))
    elif ergebnis == "instandsetzen":
        db.execute("UPDATE mat_item SET last_inspected_on = ?, updated_at = ? WHERE id = ?", (tag, db.now(), iid))
        if gesperrt:
            journal.eintragen("item", iid, "geprueft", {"last_inspected_on": item["last_inspected_on"]},
                              {"last_inspected_on": tag, "pruefung": p["id"], "ergebnis": ergebnis, "art": p["kind"]})
        else:
            sperrgrund = f"Prüfung vom {_fmt(tag)}: instandsetzen" + (f" – {grund}" if grund else "")
            _sperren(dict(item, last_inspected_on=tag), "gesperrt", sperrgrund, pruefung_id=p["id"])
    else:                                                  # aussondern
        db.execute("UPDATE mat_item SET last_inspected_on = ?, updated_at = ? WHERE id = ?", (tag, db.now(), iid))
        _aussondern(bestand.artikel(iid), "Prüfergebnis „aussondern“" + (f": {grund}" if grund else ""), "",
                    tag, pruefer, basis_id=p["id"])


def _rueckweg(item):
    """Wohin die Freiprüfung einen gesperrten Artikel bringt: in seinen Herkunftsordner – gibt es den nicht
    mehr oder ist er kein Ablageordner, in seine Gliederung."""
    herkunft = item["origin_folder_id"]
    if herkunft:
        o = db.query("SELECT * FROM mat_folder WHERE id = ?", (herkunft,), one=True)
        if o and not o["system_kind"] and bestand.gliederung_von(herkunft):
            return herkunft
    gl = bestand.gliederung_von(item["folder_id"])
    if not gl:
        raise Abgelehnt("Der Artikel hängt unter keiner Gliederung – bitte den Ordnerbaum prüfen.", 409)
    return gl["id"]


def _systemziel(item, art):
    gl = bestand.gliederung_von(item["folder_id"])
    ziel = bestand.systemordner(gl["id"], art) if gl else None
    if not ziel:
        raise Abgelehnt(f"Der Systemordner „{art}“ der Gliederung fehlt – bitte den Ordnerbaum prüfen.", 409)
    return ziel["id"]


def _sperren(item, zustand, grund, pruefung_id=None):
    """Sperre wirken lassen: in „Gesperrt“ der Gliederung, Herkunft merken."""
    ziel = _systemziel(item, "gesperrt")
    db.execute("UPDATE mat_item SET lock_state = ?, lock_reason = ?, origin_folder_id = ?, folder_id = ?, "
               "last_inspected_on = ?, updated_at = ? WHERE id = ?",
               (zustand, grund, item["folder_id"], ziel, item["last_inspected_on"], db.now(), item["id"]))
    nachher = {"lock_state": zustand, "lock_reason": grund, "folder_id": ziel, "ordner": bestand._pfad_text(ziel),
               "origin_folder_id": item["folder_id"], "herkunft": bestand._pfad_text(item["folder_id"])}
    if pruefung_id:
        nachher["pruefung"] = pruefung_id
    journal.eintragen("item", item["id"], "gesperrt",
                      {"lock_state": item["lock_state"], "folder_id": item["folder_id"],
                       "ordner": bestand._pfad_text(item["folder_id"])}, nachher)


def sperren(iid, d, pruefer):
    """Sperre ohne Prüfung – nur Prüfer, nach Sturzbelastung, Beschädigung oder bei Verlust."""
    if not pruefer.get("urkunde"):
        raise Abgelehnt(URKUNDE_FEHLT, 403)
    art = auswahl(d.get("grund"), SPERRGRUENDE, "Grund der Sperre")
    zusatz = text(d, "text", "Erläuterung", 300)
    with db.transaction(sofort=True):
        item = bestand.artikel(iid)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel ist ausgesondert.", 409)
        if item["lock_state"] != "frei":
            raise Abgelehnt("Der Artikel ist schon gesperrt.", 409)
        offen = offener_entwurf(iid)
        if offen:
            raise Abgelehnt(reserviert_text(offen) + " Über die Sperre entscheidet diese Prüfung (Ergebnis "
                            "„instandsetzen“); eine liegen gebliebene Reservierung gibt der Materialwart frei.", 409)
        grund = SPERRGRUENDE[art] + (f": {zusatz}" if zusatz else "")
        _sperren(item, "verloren" if art == "verlust" else "gesperrt", grund)


def _aussondern(item, grund, bemerkung, tag, akteur, basis_id=None):
    """Aussonderung als eigener Vorgang (mat_inspection, Art „aussonderung“, ohne Formular); der Artikel
    wandert in „Ausgesondert“ und zählt nirgends mehr als Bestand."""
    from . import durchgang
    ziel = _systemziel(item, "ausgesondert")
    ts = db.now()
    aid = db.execute(
        "INSERT INTO mat_inspection (item_id, inspector_user_id, inspector_name, inspector_certificate, inspected_on, "
        "kind, result, reason, remarks, basis_inspection_id, completed_at, created_at, updated_at) "
        "VALUES (?,?,?,?,?,'aussonderung','aussondern',?,?,?,?,?,?)",
        (item["id"], akteur.get("id"), akteur["name"], akteur.get("urkunde") or "", tag, grund, bemerkung, basis_id,
         ts, ts, ts))
    db.execute("UPDATE mat_item SET lock_state = 'ausgesondert', lock_reason = ?, origin_folder_id = NULL, folder_id = ?, "
               "updated_at = ? WHERE id = ?", (grund, ziel, ts, item["id"]))
    journal.eintragen("inspection", aid, "ausgesondert", None,
                      {"item_id": item["id"], "reason": grund, "inspected_on": tag, "basis": basis_id})
    journal.eintragen("item", item["id"], "ausgesondert",
                      {"lock_state": item["lock_state"], "folder_id": item["folder_id"],
                       "ordner": bestand._pfad_text(item["folder_id"])},
                      {"lock_state": "ausgesondert", "folder_id": ziel, "ordner": bestand._pfad_text(ziel),
                       "grund": grund, "datum": tag, "aussonderung": aid})
    durchgang.nach_aussonderung(item["id"], tag, basis_id)
    return aid


def aussondern(iid, d, akteur):
    """Aussonderung durch den Materialwart – nur für Artikel, die ein Prüfer vorher gesperrt hat."""
    art = auswahl(d.get("grund"), AUSSONDERUNGSGRUENDE, "Grund der Aussonderung")
    bemerkung = text(d, "bemerkung", "Bemerkung", 2000, einzeilig=False)
    tag = datum(d.get("datum"), "Datum") or heute().isoformat()
    if tag > heute().isoformat():
        raise Abgelehnt("Das Datum der Aussonderung liegt in der Zukunft.")
    with db.transaction(sofort=True):
        item = bestand.artikel(iid)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel ist schon ausgesondert.", 409)
        if item["lock_state"] not in ("gesperrt", "verloren"):
            raise Abgelehnt("Aussondern lassen sich nur gesperrte Artikel – zuerst sperrt ein Prüfer (aus einer "
                            "Prüfung mit „instandsetzen“ oder direkt nach Sturz, Beschädigung oder Verlust).", 409)
        if tag < item["created_at"][:10]:
            raise Abgelehnt("Das Datum liegt vor der Erfassung des Artikels.")
        offen = offener_entwurf(iid)
        if offen:
            raise Abgelehnt(reserviert_text(offen) + " Erst die Reservierung freigeben.", 409)
        return _aussondern(item, AUSSONDERUNGSGRUENDE[art], bemerkung, tag, akteur)
