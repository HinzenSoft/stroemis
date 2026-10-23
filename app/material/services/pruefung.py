"""Prüfungen: Entwurf (zugleich Reservierung), Befunde je Prüfpunkt, Anhänge, Abschluss; Sperre ohne
Prüfung, Freiprüfung und Aussonderung.

Ablauf: Ein Prüfer startet die Prüfung eines Artikels – jederzeit, nicht erst wenn sie fällig ist. Es
entsteht ein Entwurf mit einer Kopie der Prüfpunkte des passenden Formulars (aktives spezifisches des
Produkts, sonst aktives generisches der Kategorie), jeder mit seinem Sollwert vorbelegt: Der Prüfer
ändert nur Abweichungen. Der Entwurf ist die Reservierung – höchstens einer je Artikel (eindeutiger
Index), die anderen sehen „in Prüfung bei …“. Eine liegen gebliebene Reservierung hebt der
Materialwart auf. Die erste Prüfung eines Artikels ist immer die Eingangsprüfung; bis sie
abgeschlossen ist, steht er auf „neu“.

Abschließen heißt Festschreiben (Lieferung 3): Es setzt Ergebnis, Sperrzustand und Fälligkeit und erzeugt in
derselben Transaktion das Prüfprotokoll als PDF mit Unterschrift, Anmeldung, Zeitpunkt und Prüfsumme
(protokoll.py). Danach ist die Prüfung unveränderlich – auch die Datenbank weist jede Änderung ab
(Trigger, models.py). Eine Korrektur ist eine Berichtigung: ein neuer Entwurf mit allen Befunden, Fotos und
Anhängen, demselben Prüftag und Verweis auf das Original, das unverändert bleibt. Regeln beim Abschluss:
  - Jeder Pflichtpunkt hat einen Wert oder ist „nicht zutreffend“; jeder Mangel hat ein Foto und eine Bemerkung.
  - Ein kritischer Punkt mit Mangel schließt „einsatzbereit“ aus, ebenso ein erreichtes Lebensende
    (nur textil – bei Metall entscheidet allein der Befund).
  - „instandsetzen“ und „aussondern“ ohne Mangel brauchen einen Grund.
  - Die nächste Fälligkeit (nur bei „einsatzbereit“) ist Prüftag + wirksames Intervall und lässt sich
    nur vorziehen.
  - „instandsetzen“ sperrt: Der Artikel wandert in „Gesperrt“ seiner Gliederung, der Herkunftsordner
    bleibt gemerkt. „einsatzbereit“ an einem gesperrten Artikel ist die Freiprüfung – sie bringt ihn
    zurück in den Herkunftsordner. „aussondern“ ist zugleich die Aussonderung (eigener Vorgang mit
    eigenem Aussonderungsprotokoll).
  - Festschreiben verlangt eine Urkundennummer und eine im Profil hinterlegte Unterschrift; Unterschrifts-
    felder des Formulars sind wie andere Pflichtpunkte zu füllen.
  - Gemeldete Mängel (Phase 3 · L1, mangel.py): „einsatzbereit“ geht bei offenen Meldungen nur, wenn der Prüfer jede
    einzeln als geprüft abgehakt hat (maengel_gesehen) – dann erledigt die Freiprüfung sie; eine Berichtigung gibt bei
    offener Meldung nie frei. Die Aussonderung erledigt sie ebenso, „instandsetzen“ nicht.
  - Hersteller-Sets (Phase 4 · L2, Paket K2): An Set-Artikel und Teil wirkt jedes Ergebnis über das Set
    (_wirkung_im_set): „instandsetzen“ sperrt das ganze Set (sets.sperren), „einsatzbereit“ im gesperrten Set nimmt nur den
    eigenen Grund („eigen“ → „set“), „aussondern“ an einem Teil entnimmt und sondert es aus, am Set-Artikel ist es „Set
    aussondern“. Den Set-Artikel prüft man nur in einer Set-Prüfung (setlauf.py) – erst ihr Festschreiben kann das Set
    freigeben; jede Prüfung an Set oder Teil zählt, solange eine offen ist, in ihr (set_lauf_id). Eine nur geerbte Sperre
    („set“) zählt für Prüfart und Berichtigung wie frei.

Wer handelt, kommt als „pruefer“-dict herein ({id, name, urkunde, unterschrift, login}) – aus dem
angemeldeten Konto (pruefer_aus) oder, für die Demodaten auf der Kommandozeile, von Hand."""
import json
from datetime import date

from flask import has_request_context

from ... import db
from ...images import delete_photo_files
from ..models import ANHANGARTEN, AUSSONDERUNGSGRUENDE, BEFUNDE, ERGEBNISSE, PRUEFARTEN, SPERRGRUENDE
from . import OHNE_NAMEN, Abgelehnt, auswahl, datum, erster_tag, heute, laenge, laenge_text, text, wahr
from . import anhang as anh
from . import bestand, journal, katalog, protokoll, rechte
from . import status as st
from . import unterschrift as us
from .interval import plus_monate, wirksam

BEFUND_TEXT = {"ok": "in Ordnung", "mangel": "Mangel", "nicht_zutreffend": "nicht zutreffend"}
ABGESCHLOSSEN = ("Die Prüfung ist festgeschrieben und lässt sich nicht mehr ändern – eine Korrektur geht nur als "
                 "Berichtigung.")
URKUNDE_FEHLT = ("Prüfen dürfen nur Prüfer mit Urkundennummer – das Häkchen „Prüfer“ setzt die Verwaltung in der "
                 "Nutzerverwaltung, die Urkundennummer trägt der Prüfer selbst im Profil ein.")
# Artikellänge (Schritt 20, nach der Prüfung vom 22.10.2026): Längenpunkt ohne vorgesehene Länge; Länge während der
# Prüfung geändert.
KEINE_LAENGE_PUNKT = ("Für Artikel dieser Kategorie ist keine Länge vorgesehen – der Prüfpunkt ist „nicht zutreffend“ "
                      "(das Häkchen „Artikel haben eine Länge“ setzt die Material-Verwaltung an der Kategorie).")
LAENGE_GEAENDERT = ("Die Länge am Artikel wurde während der Prüfung auf {laenge} geändert – bitte den Messwert "
                    "bestätigen (der Prüfpunkt zeigt jetzt die neue Länge).")
UNTERSCHRIFT_FEHLT = ("Zum Festschreiben fehlt deine Unterschrift – bitte im Profil hinterlegen "
                      "oder direkt hier unterschreiben.")


def pruefer_aus(user):
    """Der Prüfer aus dem angemeldeten Konto – mit Unterschrift und Anmeldung fürs Festschreiben. Er steht mit Namen da,
    nie mit der E-Mail (ohne Namen gibt es keinen Modulzugang; für den theoretischen Rest der Platzhalter)."""
    from .rechte import ist_pruefer, urkunde_saeubern
    return {"id": user["id"], "name": (user["name"] or "").strip() or OHNE_NAMEN,
            "urkunde": urkunde_saeubern(user["urkundennummer"] or "") if ist_pruefer(user) else "",
            "unterschrift": user.get("signature_png") or None, "login": user["email"]}


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
    # Nur mit dem Set gesperrt (lock_cause „set“, Schritt 21): wie frei – das Teil selbst hat keinen Schaden (A23).
    if item["lock_state"] in ("gesperrt", "verloren") and item.get("lock_cause") != "set":
        # Nach einer Mangelmeldung, die noch kein Prüfer angesehen hat, ist die Freiprüfung außerplanmäßig – erst nach
        # „instandsetzen“ wieder eine Prüfung nach Reparatur.
        from . import mangel
        return arten, ("ausserplanmaessig" if mangel.ungeprueft(item["id"]) else "reparatur")
    from . import durchgang
    if st.status(item) in ("ueberfaellig", "bald_faellig") or durchgang.offene_runde_fuer(item["id"]):
        return arten, "periodisch"
    return arten, "ausserplanmaessig"


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
            "foto": foto, "unterschrift": us.daten_uri(r.get("signature_png"))}


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
            "basis_id": p["basis_inspection_id"],
            "protokoll": protokoll.protokoll_json(p, f"/material/pruefung/{p['id']}/pdf"),
            "berichtigt": _verweis(p["corrects_inspection_id"]),
            "berichtigt_durch": _berichtigung_von(p["id"]) if p["completed_at"] else None}


def _verweis(pid):
    """Kurzangaben zu einer anderen Prüfung (Original einer Berichtigung)."""
    if not pid:
        return None
    r = db.query("SELECT id, protocol_id, inspected_on FROM mat_inspection WHERE id = ?", (pid,), one=True)
    return {"id": r["id"], "protokoll_id": r["protocol_id"], "datum": r["inspected_on"]} if r else None


def _berichtigung_von(pid):
    r = db.query("SELECT id, protocol_id, completed_at, inspector_name FROM mat_inspection WHERE corrects_inspection_id = ?",
                 (pid,), one=True)
    if not r:
        return None
    return {"id": r["id"], "protokoll_id": r["protocol_id"], "entwurf": r["completed_at"] is None,
            "pruefer": r["inspector_name"]}


def pruefung_json(p, pruefer_id=None):
    """Eine Prüfung mit „darf“ an der Heimat ihres Artikels; der Durchgang einheitlich wie am Artikel."""
    item = bestand.artikel(p["item_id"])
    produkt = katalog.produkt(item["product_id"])
    out = kurz_json(p)
    out["darf"] = rechte.rechte_artikel(item)
    out["eigen"] = bool(pruefer_id) and p["inspector_user_id"] == pruefer_id
    out["artikel"] = bestand.artikel_kurz(item)
    out["artikel"]["pfad"] = bestand.pfad(item["folder_id"])
    out["artikel"]["origin_folder_id"] = item["origin_folder_id"]
    if out["artikel"].get("teil_von"):
        # „Austausch laut Hersteller“ der Position – bei „nein“ lässt „aussondern“ das Teil gesperrt im Set (Ablauf N3).
        from . import setaustausch
        z = setaustausch._position(item["parent_item_id"], item)
        out["artikel"]["teil_von"]["austausch"] = z["austausch"] if z else None
    out["produkt"] = {"id": produkt["id"], "name": katalog.produktname(produkt), "manufacturer": produkt["manufacturer"],
                      "model": produkt["model"], "description": produkt["description"],
                      "article_no": produkt["article_no"], "norm": produkt["norm"],
                      "material_kind": produkt["material_kind"], "demo": bool(produkt["demo"])}
    out["formular"] = None
    if p["form_id"]:
        f = db.query("SELECT id, version, title FROM mat_form WHERE id = ?", (p["form_id"],), one=True)
        out["formular"] = {"id": p["form_id"], "version": p["form_version"], "titel": f["title"] if f else ""}
    punkte = befunde(p["id"])
    out["punkte"] = [befund_json(r) for r in punkte]
    out["anhaenge"] = [anhang_json(a) for a in anhaenge(p["id"])]
    from . import durchgang
    out["durchgang"] = durchgang.verweis(p["round_id"]) if p["round_id"] else None
    out["dokumente"] = json.loads(p["documents_json"] or "[]")
    out["unterschrift"] = us.daten_uri(p["signature_png"])
    out["grund_berichtigung"] = p["correction_reason"]
    # Länge des Artikels (Schritt 20): die gespeicherte und ob die Kategorie eine vorsieht – für den Längenpunkt.
    out["laenge"] = {"wert": item["length_m"], "text": laenge_text(item["length_m"]),
                     "moeglich": katalog.laenge_wirksam(produkt["category_id"])}
    if not out["entwurf"]:
        out["berichtigbar"] = berichtigbar(p, item)
    tag = p["inspected_on"] if out["entwurf"] and p["corrects_inspection_id"] else (
        heute().isoformat() if out["entwurf"] else p["inspected_on"])
    if out["entwurf"]:
        out["prueftag"] = tag            # der Tag, den Festschreiben jetzt setzen würde (deutsche Zeit)
    out["lebensdauer"] = _lebensdauer(item, produkt, tag)
    if out["entwurf"]:
        # Gesperrte liegen in „Gesperrt“; ihr Intervall kommt aus der Heimat, in die die Freiprüfung sie zurückbringt.
        iv = wirksam(produkt, bestand.heimat(item), item["interval_months"])
        out["intervall"] = iv
        out["vorschlag_naechste"] = plus_monate(date.fromisoformat(tag), iv["monate"]).isoformat() if iv["monate"] else None
        kritisch = [r["checklist_text"] for r in punkte if r["finding"] == "mangel" and r["is_critical"]]
        gruende = []
        if kritisch:
            gruende.append("kritischer Mangel: " + "; ".join(kritisch))
        if out["lebensdauer"] and out["lebensdauer"]["erreicht"]:
            gruende.append(f"Lebensende erreicht am {_fmt(out['lebensdauer']['ende'])}")
        out["einsatzbereit_gesperrt"] = gruende
        out["freipruefung"] = item["lock_state"] in ("gesperrt", "verloren") and item.get("lock_cause") != "set"
        out["arten"] = arten_fuer(item)[0]
        # Offene Mangelmeldungen – die Grundlage der Häkchen im Festschreib-Dialog; Text, Fotos und Melder nur für Prüfer
        # und Materialwart (mangel.darf_inhalt) und die eigene Meldung.
        from . import mangel
        out["maengel"] = mangel.offene_json(item, mangel.darf_inhalt(item))
    # Prüfanleitung aus dem Wiki (Phase 2 · L3) – nur in offenen Prüfungen; an abgeschlossenen nichts (die heutige
    # Fassung ist nicht die, nach der geprüft wurde). Festgehalten wird sie nirgends.
    from . import wikiverweis
    out["anleitung"] = wikiverweis.anleitung(p["form_id"]) if out["entwurf"] else None
    # Hersteller-Sets (K2): Set-Prüfung, zu der die Prüfung gehört, am Entwurf des Set-Artikels der Stand des Laufs
    # (Umfang, Fortschritt, Freigabe-Gründe, Vorbelegung „verbleib“), an der abgeschlossenen die Teiletabelle.
    from . import setlauf
    out.update(setlauf.pruefung_teil(p, item))
    return out


def fuer_artikel(iid):
    """Alle Prüfungen und Aussonderungen eines Artikels, neueste zuerst – der Prüfteil des Lebenslaufs."""
    rows = db.query("SELECT * FROM mat_inspection WHERE item_id = ? "
                    "ORDER BY completed_at IS NOT NULL, inspected_on DESC, id DESC", (iid,))
    return [kurz_json(r) for r in rows]


def entwuerfe(pruefer_id=None):
    """Offene Prüfungen (Reservierungen) mit Artikel – die eigenen zuerst, dann die ältesten; nur zu Artikeln, die das
    Konto sieht."""
    offen = db.query(f"SELECT x.* FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE x.completed_at IS NULL "
                     f"AND {rechte.artikel_filter('i')} ORDER BY (x.inspector_user_id IS ?) DESC, x.created_at",
                     (pruefer_id or -1,))
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

def _vorbelegung(punkt, item=None, laenge_moeglich=False):
    """(Befund, Wert, Soll) eines frischen Prüfpunkts: Befund „in Ordnung“ und der Sollwert, denn das ist der
    Normalfall. Bei Text und Zahl ist das Soll seit Lieferung 1 ein Hinweis („max. 22 mm“) – den
    übernimmt kein Wert, er steht nur als Platzhalter im Feld. Einzig ein Soll, das selbst eine Zahl ist,
    gilt bei Zahlpunkten als Sollwert. Ein Längenpunkt (Schritt 20) bekommt als Soll und Wert die Länge des Artikels
    („57,5“; leer, wenn er keine hat); sieht die Kategorie keine Länge vor, ist er „nicht zutreffend“."""
    soll = punkt["expected_value"]
    if punkt["editor"] == "yesno":
        return "ok", soll, soll
    if punkt["editor"] == "number" and _ist_zahl(soll):
        return "ok", soll.strip(), soll
    if punkt["editor"] == "laenge":
        if not laenge_moeglich:
            return "nicht_zutreffend", "", ""
        jetzt = laenge_text(item["length_m"] if item else None, einheit=False)
        return "ok", jetzt, jetzt
    return "ok", "", soll


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
        if durchgang_id:
            # Ein fremder oder unbekannter Durchgang antwortet 404 – auch wenn es schon einen eigenen Entwurf gibt.
            durchgang.runde_des_artikels(durchgang_id, iid)
        offen = offener_entwurf(iid)
        if offen:
            if _eigen(offen, pruefer):
                return offen["id"], False
            raise Abgelehnt(reserviert_text(offen) + " Eine liegen gebliebene Reservierung hebt der Materialwart auf.",
                            409)
        # Hersteller-Sets (K2): Den Set-Artikel prüft man nur in einer Set-Prüfung; Prüfungen an Set und Teilen zählen,
        # solange eine offen ist, in ihr.
        from . import sets, setlauf
        lauf = setlauf.offener(sets.set_kennung(item)) if sets.im_set(item) else None
        set_artikel = sets.ist_set_artikel(item) and not item["parent_item_id"]
        if set_artikel and not lauf:
            raise Abgelehnt(setlauf.NUR_IM_LAUF, 409)
        arten, vorschlag = arten_fuer(item)
        art = art or vorschlag
        if art not in arten:
            if arten == ["eingang"]:
                raise Abgelehnt("Die erste Prüfung eines Artikels ist die Eingangsprüfung.")
            raise Abgelehnt(f"Prüfart „{art}“ ist hier nicht wählbar ({', '.join(PRUEFARTEN[a] for a in arten)}).")
        formular = katalog.formular_fuer_produkt(item["product_id"])
        if not formular:
            raise Abgelehnt("Für dieses Produkt gibt es kein aktives Prüfformular – weder am Produkt noch in "
                            "seiner Kategorie. Die Material-Verwaltung legt es im Katalog an.", 409)
        punkte = katalog.punkte(formular["id"])
        if durchgang_id:
            runde = durchgang.runde_fuer_start(durchgang_id, iid)
        else:
            runde = durchgang.offene_runde_fuer(iid)
        ts = db.now()
        pid = db.execute(
            "INSERT INTO mat_inspection (item_id, round_id, inspector_user_id, inspector_name, inspector_certificate, "
            "form_id, form_version, inspected_on, kind, set_lauf_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (iid, runde, pruefer.get("id"), pruefer["name"], pruefer["urkunde"], formular["id"], formular["version"],
             heute().isoformat(), art, lauf["id"] if lauf else None, ts, ts))
        laenge_moeglich = katalog.laenge_wirksam(katalog.produkt(item["product_id"])["category_id"])
        for p in punkte:
            befund, wert, soll = _vorbelegung(p, item, laenge_moeglich)
            db.execute("INSERT INTO mat_inspection_result (inspection_id, checklist_item_id, position, group_name, "
                       "checklist_text, editor, mandatory, expected_value, is_critical, finding, value) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (pid, p["id"], p["position"], p["group_name"], p["label"], p["editor"], p["mandatory"],
                        soll, p["is_critical"], befund, wert))
        if set_artikel:
            setlauf.bestandteil_zeilen(pid, iid)
        journal.eintragen("inspection", pid, "begonnen", None,
                          {"item_id": iid, "kind": art, "form_id": formular["id"], "form_version": formular["version"],
                           "round_id": runde, "set_lauf_id": lauf["id"] if lauf else None})
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
        p = _entwurf_des(pid, pruefer)
        r = _befund(pid, rid)
        art = r["editor"]
        befund, wert, notiz = r["finding"], r["value"], r["note"]
        if "notiz" in d:
            notiz = text(d, "notiz", "Bemerkung zum Prüfpunkt", 1000, einzeilig=False)
        if art == "signature":
            # Unterschriftsfeld des Formulars: gezeichnet auf dem Signatur-Pad; leer = noch nicht unterschrieben.
            bild = r["signature_png"]
            if d.get("befund") == "nicht_zutreffend":
                befund, bild = "nicht_zutreffend", None
            elif "unterschrift" in d:
                bild = us.lesen(d["unterschrift"], r["checklist_text"]) if d["unterschrift"] else None
                befund = "ok"
            elif d.get("befund") == "ok":
                befund = "ok"
            elif "befund" in d or "wert" in d:
                raise Abgelehnt("Ein Unterschriftsfeld nimmt eine Unterschrift auf (oder „nicht zutreffend“).")
            db.execute("UPDATE mat_inspection_result SET finding = ?, value = '', note = ?, signature_png = ? WHERE id = ?",
                       (befund, notiz, bild, rid))
            _beruehrt(pid)
            return befund_json(_befund(pid, rid))
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
            # Sieht die Kategorie keine Länge vor, ist der Längenpunkt nur „nicht zutreffend“ (Prüfung der Länge, B4):
            # „in Ordnung“ führte in die Sackgasse (Pflichtpunkt ohne Wert), „Mangel“ zählte und verschwand dann.
            if art == "laenge" and befund != "nicht_zutreffend" and not _laenge_moeglich(p):
                raise Abgelehnt(KEINE_LAENGE_PUNKT, 409)
        if art != "yesno" and "wert" in d:
            if art == "date":
                wert = datum(d.get("wert"), r["checklist_text"]) or ""
            elif art == "number":
                roh = d.get("wert")
                wert = _zahl(roh if isinstance(roh, str) else "" if roh is None else str(roh), r["checklist_text"])
            elif art == "text":
                wert = text(d, "wert", r["checklist_text"], 1000, einzeilig=False)
            elif art == "laenge":
                # Die gemessene Länge in Metern („55“, „55,0“, „55.0“) – gespeichert als „55,0“; beim Festschreiben
                # wird ein anderer Wert als die Artikellänge in den Artikel übernommen (abschliessen). Sieht die
                # Kategorie keine Länge vor, bleibt der Punkt „nicht zutreffend“.
                if not _laenge_moeglich(p):
                    raise Abgelehnt(katalog.KEINE_LAENGE, 409)
                roh = d.get("wert")
                roh = "" if roh is None else roh if isinstance(roh, (str, bool)) else str(roh)   # 0 ist 0, nicht leer
                wert = laenge_text(laenge(roh, r["checklist_text"]), einheit=False)
            else:
                raise Abgelehnt("Dieser Prüfpunkt nimmt ein Foto auf, keinen Wert.")
        db.execute("UPDATE mat_inspection_result SET finding = ?, value = ?, note = ? WHERE id = ?",
                   (befund, wert, notiz, rid))
        _beruehrt(pid)
    return befund_json(_befund(pid, rid))


def _laenge_moeglich(p):
    """Sieht die Kategorie des Artikels dieser Prüfung eine Länge vor (katalog.laenge_wirksam)?"""
    item = bestand.artikel(p["item_id"])
    return katalog.laenge_wirksam(katalog.produkt(item["product_id"])["category_id"])


def _laenge_zahl(text):
    """Der Text eines Längenpunkts („57,5“) als Zahl – leer → None."""
    t = (text or "").strip()
    return laenge(t) if t else None


def _laenge_ohne_vorgabe(item, punkte):
    """Sieht die Kategorie (inzwischen) keine Länge vor, ist jeder Längenpunkt „nicht zutreffend“ – gesetzt vor den
    Pflicht-, Mangel- und Grundprüfungen des Abschlusses (Prüfung der Länge, B4). Ein gemessener Wert, der vom Soll
    abweicht, verfällt nicht still: Er steht danach in der Bemerkung des Punkts (V5). Liefert, ob etwas gesetzt wurde."""
    zeilen = [r for r in punkte if r["editor"] == "laenge"
              and (r["finding"] != "nicht_zutreffend" or r["value"] or r["expected_value"])]
    if not zeilen or katalog.laenge_wirksam(katalog.produkt(item["product_id"])["category_id"]):
        return False
    for r in zeilen:
        notiz = r["note"] or ""
        wert = (r["value"] or "").strip()
        if wert and wert != (r["expected_value"] or "").strip():
            zusatz = f"Gemessen: {wert} m – die Kategorie sieht keine Länge mehr vor, nicht übernommen."
            notiz = (f"{notiz}\n{zusatz}" if notiz.strip() else zusatz)[:1000]
        db.execute("UPDATE mat_inspection_result SET finding = 'nicht_zutreffend', value = '', expected_value = '', "
                   "note = ? WHERE id = ?", (notiz, r["id"]))
    return True


def _laenge_konflikte(p, item, punkte):
    """Längenpunkte einer Prüfung (keiner Berichtigung), deren Vorbelegung (Soll) nicht mehr die Länge des Artikels ist,
    während der Messwert davon abweicht: Jemand hat die Länge geändert, seit die Prüfung begann (Prüfung der Länge, B1).
    Ohne diese Prüfung schriebe der alte, vorbelegte Wert die neuere Länge zurück."""
    if p["corrects_inspection_id"]:
        return []
    aktuell = item["length_m"]
    return [r for r in punkte if r["editor"] == "laenge" and r["finding"] != "nicht_zutreffend"
            and (r["value"] or "").strip() and _laenge_zahl(r["expected_value"]) != aktuell
            and _laenge_zahl(r["value"]) != aktuell]


def _laenge_vormerken(pid, pruefer):
    """Vor dem Festschreiben, in eigener Transaktion: Hat sich die Länge des Artikels seit der Vorbelegung geändert
    (_laenge_konflikte), bekommt der Längenpunkt die neue Länge als Soll – und als Wert, wenn der Prüfer den
    vorbelegten Wert nicht angefasst hat; ein eigener Messwert bleibt. Liefert die neue Länge als Text (dann bricht
    abschliessen mit 409 ab und der Prüfer bestätigt den Messwert) oder None."""
    with db.transaction(sofort=True):
        p = _entwurf_des(pid, pruefer)
        item = bestand.artikel(p["item_id"])
        if not katalog.laenge_wirksam(katalog.produkt(item["product_id"])["category_id"]):
            return None
        konflikte = _laenge_konflikte(p, item, befunde(pid))
        neu = laenge_text(item["length_m"], einheit=False)
        for r in konflikte:
            wert = neu if (r["value"] or "").strip() == (r["expected_value"] or "").strip() else r["value"]
            db.execute("UPDATE mat_inspection_result SET expected_value = ?, value = ? WHERE id = ?", (neu, wert, r["id"]))
        if konflikte:
            _beruehrt(pid)
            return laenge_text(item["length_m"]) or "keine Angabe"
    return None


def _laenge_uebernehmen(p, item, punkte):
    """Beim Festschreiben (Schritt 20): Ein Längenpunkt mit Befund und Wert trägt die gemessene Länge in den Artikel,
    wenn sie von der gespeicherten abweicht – mit eigenem Journaleintrag „laenge_geaendert“ (vorher/nachher, Verweis
    auf die Prüfung). Bei einer Prüfung ist das Soll die Vorbelegung, also die Länge zu Beginn; hat sie sich seitdem
    geändert, hat _laenge_vormerken schon abgebrochen (hier nur noch der Wettlauf: 409). Bei einer Berichtigung bleibt
    das Soll das des Originals – die Länge vor der berichtigten Prüfung –, damit ihr Protokoll „alt → neu“ jenes
    Prüftags zeigt (B3); in den Artikel geht der Messwert nur, wenn die Berichtigung ihn gegenüber dem Original
    ändert, abgeglichen mit der aktuellen Länge. Punkte ohne vorgesehene Länge hat _laenge_ohne_vorgabe schon auf
    „nicht zutreffend“ gesetzt. Liefert die Länge nach dem Festschreiben."""
    laengenpunkte = [r for r in punkte if r["editor"] == "laenge"]
    aktuell = item["length_m"]
    if not laengenpunkte or not katalog.laenge_wirksam(katalog.produkt(item["product_id"])["category_id"]):
        return aktuell
    if _laenge_konflikte(p, item, laengenpunkte):
        raise Abgelehnt(LAENGE_GEAENDERT.format(laenge=laenge_text(aktuell) or "keine Angabe"), 409)
    original = {}
    if p["corrects_inspection_id"]:
        original = {(o["checklist_item_id"], o["position"]): o["value"] for o in db.query(
            "SELECT checklist_item_id, position, value FROM mat_inspection_result WHERE inspection_id = ?",
            (p["corrects_inspection_id"],))}
    for r in laengenpunkte:
        if not p["corrects_inspection_id"]:
            db.execute("UPDATE mat_inspection_result SET expected_value = ? WHERE id = ?",
                       (laenge_text(aktuell, einheit=False), r["id"]))
        if r["finding"] == "nicht_zutreffend" or not (r["value"] or "").strip():
            continue
        neu = laenge(r["value"], r["checklist_text"])
        vorher = original.get((r["checklist_item_id"], r["position"]))
        if p["corrects_inspection_id"] and vorher is not None and _laenge_zahl(vorher) == neu:
            continue                           # die Berichtigung lässt den Messwert des Originals stehen
        if neu != aktuell:
            db.execute("UPDATE mat_item SET length_m = ?, updated_at = ? WHERE id = ?", (neu, db.now(), item["id"]))
            journal.eintragen("item", item["id"], "laenge_geaendert", {"length_m": aktuell},
                              {"length_m": neu, "pruefung": p["id"], "art": p["kind"]})
            aktuell = neu
    return aktuell


def punkt_foto_setzen(pid, rid, file_storage, pruefer):
    _entwurf_des(pid, pruefer)
    alt = _befund(pid, rid)
    if alt["editor"] == "signature":
        raise Abgelehnt("Ein Unterschriftsfeld nimmt eine Unterschrift auf, kein Foto.")
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
        if "art" in d and p["corrects_inspection_id"]:
            if d.get("art") != art:
                raise Abgelehnt("Die Prüfart einer Berichtigung ist die des Originals.", 409)
        elif "art" in d:
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
    """Entwurf löschen: der eigene (verwerfen) oder – als Materialwart – eine fremde Reservierung aufheben."""
    with db.transaction(sofort=True):
        p = pruefung(pid)
        if p["completed_at"]:
            raise Abgelehnt(ABGESCHLOSSEN, 409)
        eigen = _eigen(p, akteur)
        if not eigen and not darf_freigeben:
            raise Abgelehnt("Eine fremde Reservierung hebt nur der Materialwart auf.", 403)
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
        return bool(r["signature_png"])
    return bool((r["value"] or "").strip())


def abschliessen(pid, d, pruefer, pruefdatum=None):
    """Ergebnis festlegen und festschreiben (Protokoll mit Unterschrift und Prüfsumme). pruefdatum nur für
    Demodaten und Tests – über die Schnittstelle gilt heute, bei einer Berichtigung der Prüftag des Originals."""
    if not pruefer.get("urkunde"):
        raise Abgelehnt(URKUNDE_FEHLT, 403)
    if not pruefer.get("unterschrift"):
        raise Abgelehnt(UNTERSCHRIFT_FEHLT, 403)
    ergebnis = auswahl(d.get("ergebnis"), ERGEBNISSE, "Ergebnis")
    gesehen = _maengel_gesehen(d)
    geaendert = _laenge_vormerken(pid, pruefer)
    if geaendert:
        raise Abgelehnt(LAENGE_GEAENDERT.format(laenge=geaendert), 409)
    with protokoll.dateien_sichern(), db.transaction(sofort=True):
        p = _entwurf_des(pid, pruefer)
        item = bestand.artikel(p["item_id"])
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel wurde inzwischen ausgesondert.", 409)
        if ergebnis == "einsatzbereit":
            # Gemeldete Mängel: frisch gelesen – auch eine Meldung, die während der Prüfung kam. Jede offene muss der
            # Prüfer einzeln abgehakt haben; eine Berichtigung gibt bei offener Meldung nie frei.
            from . import mangel
            offen = mangel.offene_ids(item["id"])
            if offen and p["corrects_inspection_id"]:
                raise Abgelehnt(mangel.NUR_NEUE_PRUEFUNG, 409)
            if offen - gesehen:
                raise Abgelehnt(mangel.MANGEL_NEU, 409)
        produkt = katalog.produkt(item["product_id"])
        tag = _tag(pruefdatum or (p["inspected_on"] if p["corrects_inspection_id"] else heute()))
        heimat = bestand.heimat(item)
        # Set-Artikel (K2): nur im offenen Set-Lauf – sein Festschreiben schließt ihn (Prüfumfang geprüft, keine anderen
        # Entwürfe, „verbleib“ bei „aussondern“; setlauf.vorbereiten). Eine Berichtigung gehört zu ihrem Original.
        from . import sets, setlauf
        satz = None
        if sets.ist_set_artikel(item) and not item["parent_item_id"] and not p["corrects_inspection_id"]:
            if not p["set_lauf_id"]:
                raise Abgelehnt(setlauf.NUR_IM_LAUF, 409)
            satz = setlauf.vorbereiten(p, item, ergebnis, d, tag)
        _laenge_ohne_vorgabe(item, befunde(pid))      # vor den Prüfungen unten: Längenpunkte „nicht zutreffend“ (B4)
        punkte = befunde(pid)
        offen = [r["checklist_text"] for r in punkte if r["mandatory"] and not _beantwortet(r)]
        if offen:
            raise Abgelehnt("Noch ohne Befund: " + "; ".join(offen[:5]) + (" …" if len(offen) > 5 else ""))
        ohne_foto = [r["checklist_text"] for r in punkte if r["finding"] == "mangel" and not r["photo"]]
        if ohne_foto:
            raise Abgelehnt("Jeder Mangel braucht ein Foto – es fehlt bei: " + "; ".join(ohne_foto[:5]))
        # Was wo zu sehen ist, sagt das Foto allein nicht – jeder Mangel braucht dazu eine Bemerkung (Wunsch aus dem Pilot).
        ohne_notiz = [r["checklist_text"] for r in punkte if r["finding"] == "mangel" and not (r["note"] or "").strip()]
        if ohne_notiz:
            raise Abgelehnt("Jeder Mangel braucht eine Bemerkung – sie fehlt bei: " + "; ".join(ohne_notiz[:5]))
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
            iv = wirksam(produkt, bestand.heimat(item), item["interval_months"])
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
        # Die gemessene Länge in den Artikel – vor dem Abschluss, solange die Ergebniszeile ihr Soll noch annimmt
        # (Trigger mat_result_aendern); das Protokoll liest „alt → neu“ aus ihr.
        _laenge_uebernehmen(p, item, punkte)
        if satz:
            setlauf.zeilen_schreiben(p, satz)        # die Teiletabelle als Kopie – nur am offenen Entwurf (Trigger)
        db.execute("UPDATE mat_inspection SET result = ?, inspected_on = ?, next_due_on = ?, reason = ?, remarks = ?, "
                   "inspector_name = ?, inspector_certificate = ?, documents_json = ?, completed_at = ?, updated_at = ? "
                   "WHERE id = ?",
                   (ergebnis, tag, naechste, grund, bemerkung, pruefer["name"], pruefer["urkunde"],
                    json.dumps(dokumente, ensure_ascii=False), ts, ts, pid))
        journal.eintragen("inspection", pid, "abgeschlossen", None,
                          {"result": ergebnis, "inspected_on": tag, "next_due_on": naechste, "kind": p["kind"],
                           "maengel": len(maengel), "reason": grund})
        if satz:
            setlauf.wirkung(item, p, ergebnis, tag, naechste, grund, pruefer, ts, satz)
        else:
            _wirkung(item, p, ergebnis, tag, naechste, grund, pruefer, ts, d)
        nr = protokoll.pruefung_festschreiben(pid, ts, pruefer["unterschrift"], pruefer.get("login"), heimat)
        if p["corrects_inspection_id"]:
            journal.eintragen("inspection", p["corrects_inspection_id"], "berichtigt", None,
                              {"berichtigung": pid, "protocol_id": nr, "grund": p["correction_reason"]})
    return pid


def _maengel_gesehen(d):
    """„maengel_gesehen“: die Kennungen der gemeldeten Mängel, die der Prüfer im Festschreib-Dialog einzeln als geprüft
    abgehakt hat (fehlt es, keine). Liefert eine Menge."""
    from . import kennung
    werte = d.get("maengel_gesehen")
    if werte is None:
        return set()
    if not isinstance(werte, list) or len(werte) > 1000:
        raise Abgelehnt("„maengel_gesehen“ muss eine Liste von Kennungen sein.")
    return {kennung(x, "Mangelmeldung") for x in werte}


def _wirkung(item, p, ergebnis, tag, naechste, grund, pruefer, ts=None, d=None):
    """Was das Ergebnis am Artikel bewirkt – in der Transaktion des Abschlusses. Set-Artikel und Teile: _wirkung_im_set."""
    from . import sets
    if sets.im_set(item):
        return _wirkung_im_set(item, p, ergebnis, tag, naechste, grund, pruefer, ts, d)
    iid = item["id"]
    gesperrt = item["lock_state"] in ("gesperrt", "verloren")
    vorher = {"lock_state": item["lock_state"], "next_due_on": item["next_due_on"],
              "last_inspected_on": item["last_inspected_on"], "folder_id": item["folder_id"],
              "ordner": bestand._pfad_text(item["folder_id"])}
    if ergebnis == "einsatzbereit":
        ziel = item["folder_id"]
        if gesperrt:
            ziel = _rueckweg(item)
        # Frei heißt ohne Sperrursache – ein „eigen“ aus „Teil entnehmen“ blieb sonst stehen (Prüfung Sicherheit, H1).
        db.execute("UPDATE mat_item SET lock_state = 'frei', lock_cause = NULL, lock_reason = '', origin_folder_id = NULL, "
                   "folder_id = ?, next_due_on = ?, last_inspected_on = ?, updated_at = ? WHERE id = ?",
                   (ziel, naechste, tag, db.now(), iid))
        nachher = {"lock_state": "frei", "next_due_on": naechste, "last_inspected_on": tag, "folder_id": ziel,
                   "ordner": bestand._pfad_text(ziel)}
        alt, neu = journal.unterschied(vorher, nachher)
        journal.eintragen("item", iid, "freigeprueft" if gesperrt else "geprueft",
                          alt, dict(neu, pruefung=p["id"], ergebnis=ergebnis, art=p["kind"]))
        if not p["corrects_inspection_id"]:
            # Die Freiprüfung erledigt gemeldete Mängel (abgehakt hat sie der Prüfer, abschliessen prüft das).
            from . import mangel
            mangel.erledigen(iid, p["id"])
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
                    tag, pruefer, basis_id=p["id"], ts=ts)


def _wirkung_im_set(item, p, ergebnis, tag, naechste, grund, pruefer, ts=None, d=None):
    """Das Ergebnis an einem Teil oder – als Berichtigung – am Set-Artikel (Entwurf D, S8, A12; die Prüfung, die eine
    Set-Prüfung schließt, wirkt über setlauf.wirkung):
      einsatzbereit   Fälligkeit und letzte Prüfung; im gesperrten Set nur „eigen“ → „set“ (verloren → gesperrt) – Lage und
                      Sperre bleiben, frei wird nur das ganze Set in einer Set-Prüfung; erledigt gemeldete Mängel (keine
                      Berichtigung).
      instandsetzen   eigene Sperre – sperrt das ganze Set, auch an einem schon mitgesperrten Teil (sets.sperren).
      aussondern      am Teil: entnehmen und aussondern, das Set ist unvollständig gesperrt – bei „Austausch laut Hersteller:
                      nein“ bleibt es mit eigener Sperre im Set (dann das Set aussondern); am Set-Artikel: Set aussondern
                      mit „verbleib“ je Teil (Vorbelegung)."""
    from . import mangel, sets, setaustausch, setlauf
    iid = item["id"]
    gesperrt = item["lock_state"] in ("gesperrt", "verloren")
    zusatz = {"pruefung": p["id"], "ergebnis": ergebnis, "art": p["kind"]}
    if ergebnis == "einsatzbereit":
        vorher = {"next_due_on": item["next_due_on"], "last_inspected_on": item["last_inspected_on"],
                  "lock_state": item["lock_state"], "lock_cause": item["lock_cause"], "lock_reason": item["lock_reason"]}
        db.execute("UPDATE mat_item SET next_due_on = ?, last_inspected_on = ?, updated_at = ? WHERE id = ?",
                   (naechste, tag, db.now(), iid))
        nachher = dict(vorher, next_due_on=naechste, last_inspected_on=tag)
        if gesperrt and (item["lock_cause"] == "eigen" or item["lock_state"] == "verloren"):
            nachher.update(sets.eigen_aufheben(item)[1])
        alt, neu = journal.unterschied(vorher, nachher)
        journal.eintragen("item", iid, "geprueft", alt, dict(neu, **zusatz))
        if not p["corrects_inspection_id"]:
            mangel.erledigen(iid, p["id"])
    elif ergebnis == "instandsetzen":
        db.execute("UPDATE mat_item SET last_inspected_on = ?, updated_at = ? WHERE id = ?", (tag, db.now(), iid))
        if gesperrt and item["lock_cause"] == "eigen":
            journal.eintragen("item", iid, "geprueft", {"last_inspected_on": item["last_inspected_on"]},
                              dict({"last_inspected_on": tag}, **zusatz))
        else:
            sperrgrund = f"Prüfung vom {_fmt(tag)}: instandsetzen" + (f" – {grund}" if grund else "")
            sets.sperren(sets.set_kennung(item), eigen=iid, grund=sperrgrund, zusatz={"pruefung": p["id"]})
    else:
        db.execute("UPDATE mat_item SET last_inspected_on = ?, updated_at = ? WHERE id = ?", (tag, db.now(), iid))
        text_ = "Prüfergebnis „aussondern“" + (f": {grund}" if grund else "")
        if item["parent_item_id"] and setaustausch.nicht_austauschbar(item):
            # „Austausch laut Hersteller: nein“ (Entwurf G, Nachbesserung Ablauf N3): Das Teil verlässt das Set nicht – es
            # bleibt mit eigener Sperre darin, der Materialwart sondert das Set aus (das Teil ist dort mit aussondern
            # vorbelegt).
            setaustausch.teil_bleibt_gesperrt(bestand.artikel(iid), p, text_ + setaustausch.SET_AUSSONDERN_HINWEIS)
        elif item["parent_item_id"]:
            setaustausch.teil_aus_pruefung(bestand.artikel(iid), p, text_, tag, pruefer, ts)
        else:
            _, tz = sets.zeilen(iid)
            setaustausch.set_aussondern(bestand.artikel(iid), text_, "", tag, pruefer,
                                        setlauf._verbleib((d or {}).get("verbleib"), tz), basis_id=p["id"], ts=ts)


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


def _sperren(item, zustand, grund, pruefung_id=None, aktion="gesperrt", zusatz=None):
    """Sperre wirken lassen: in „Gesperrt“ der Gliederung, Herkunft merken – ein Journaleintrag (aktion; die
    Mangelmeldung schreibt „mangel_gemeldet“ mit zusatz {"mangel": Kennung}). Set-Artikel und Teile: die Sperr-Kaskade
    (sets.sperren) – eigene Sperre hier, das ganze Set mit (auch an einem schon mitgesperrten Teil)."""
    from . import sets
    if sets.im_set(item):
        z = dict(zusatz or {})
        if pruefung_id:
            z["pruefung"] = pruefung_id
        sets.sperren(sets.set_kennung(item), eigen=item["id"], zustand=zustand, grund=grund, aktion=aktion, zusatz=z)
        return
    ziel = _systemziel(item, "gesperrt")
    db.execute("UPDATE mat_item SET lock_state = ?, lock_reason = ?, origin_folder_id = ?, folder_id = ?, "
               "last_inspected_on = ?, updated_at = ? WHERE id = ?",
               (zustand, grund, item["folder_id"], ziel, item["last_inspected_on"], db.now(), item["id"]))
    nachher = {"lock_state": zustand, "lock_reason": grund, "folder_id": ziel, "ordner": bestand._pfad_text(ziel),
               "origin_folder_id": item["folder_id"], "herkunft": bestand._pfad_text(item["folder_id"])}
    if pruefung_id:
        nachher["pruefung"] = pruefung_id
    if zusatz:
        nachher.update(zusatz)
    journal.eintragen("item", item["id"], aktion,
                      {"lock_state": item["lock_state"], "folder_id": item["folder_id"],
                       "ordner": bestand._pfad_text(item["folder_id"])}, nachher)


def sperren(iid, d, pruefer):
    """Sperre ohne Prüfung – nur Prüfer, nach Sturzbelastung, Beschädigung, bei Verlust oder Rückruf."""
    if not pruefer.get("urkunde"):
        raise Abgelehnt(URKUNDE_FEHLT, 403)
    art = auswahl(d.get("grund"), SPERRGRUENDE, "Grund der Sperre")
    zusatz = text(d, "text", "Erläuterung", 300)
    with db.transaction(sofort=True):
        item = bestand.artikel(iid)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel ist ausgesondert.", 409)
        # Ein nur mit dem Set gesperrtes Teil (oder ein so gesperrter Set-Artikel) nimmt eine eigene Sperre an (Entwurf D).
        if item["lock_state"] != "frei" and item.get("lock_cause") != "set":
            raise Abgelehnt("Der Artikel ist schon gesperrt.", 409)
        offen = offener_entwurf(iid)
        if offen:
            raise Abgelehnt(reserviert_text(offen) + " Über die Sperre entscheidet diese Prüfung (Ergebnis "
                            "„instandsetzen“); eine liegen gebliebene Reservierung hebt der Materialwart auf.", 409)
        grund = SPERRGRUENDE[art] + (f": {zusatz}" if zusatz else "")
        _sperren(item, "verloren" if art == "verlust" else "gesperrt", grund)


def _aussondern(item, grund, bemerkung, tag, akteur, basis_id=None, ts=None, bewegen=True):
    """Aussonderung als eigener Vorgang (mat_inspection, Art „aussonderung“, ohne Formular) mit eigenem,
    festgeschriebenem Aussonderungsprotokoll; der Artikel wandert in „Ausgesondert“ und zählt nirgends mehr
    als Bestand. Seit Phase 2 behält er seine Heimat (origin_folder_id): Wer nur den Herkunftsordner verwaltet,
    sieht ihn und sein Protokoll weiter. Eine Zuordnung an eine Person löst sich (Journal mit Grund). Läuft in der
    Transaktion des Aufrufers, innerhalb von protokoll.dateien_sichern(). bewegen=False: Lage, Zustand und Zuordnung hat
    der Aufrufer schon gesetzt – für ein ganzes Set in einer Anweisung (setaustausch.set_aussondern); item ist dann der
    Stand davor (für Journal und Sperrvermerk)."""
    from . import durchgang
    ziel = _systemziel(item, "ausgesondert")
    ts = ts or db.now()
    heimat = bestand.heimat(item)
    sperre = ""
    if item["lock_state"] in ("gesperrt", "verloren"):
        sperre = ("verloren gemeldet" if item["lock_state"] == "verloren" else "gesperrt") + (
            f" – {item['lock_reason']}" if item["lock_reason"] else "")
    aid = db.execute(
        "INSERT INTO mat_inspection (item_id, inspector_user_id, inspector_name, inspector_certificate, inspected_on, "
        "kind, result, reason, remarks, basis_inspection_id, completed_at, created_at, updated_at) "
        "VALUES (?,?,?,?,?,'aussonderung','aussondern',?,?,?,?,?,?)",
        (item["id"], akteur.get("id"), akteur["name"], akteur.get("urkunde") or "", tag, grund, bemerkung, basis_id,
         ts, ts, ts))
    if bewegen:
        db.execute("UPDATE mat_item SET lock_state = 'ausgesondert', lock_reason = ?, origin_folder_id = ?, folder_id = ?, "
                   "assigned_user_id = NULL, lock_cause = NULL, updated_at = ? WHERE id = ?",
                   (grund, heimat, ziel, ts, item["id"]))
    journal.eintragen("inspection", aid, "ausgesondert", None,
                      {"item_id": item["id"], "reason": grund, "inspected_on": tag, "basis": basis_id})
    journal.eintragen("item", item["id"], "ausgesondert",
                      {"lock_state": item["lock_state"], "folder_id": item["folder_id"],
                       "ordner": bestand._pfad_text(item["folder_id"])},
                      {"lock_state": "ausgesondert", "folder_id": ziel, "ordner": bestand._pfad_text(ziel),
                       "grund": grund, "datum": tag, "aussonderung": aid})
    if item.get("assigned_user_id"):
        # Betroffene stehen nur pseudonym im Journal (Kontoverweis, 6.2).
        journal.eintragen("item", item["id"], "zuordnung_geloest", None,
                          {"konto": journal.konto_ref(item["assigned_user_id"]), "grund": "ausgesondert"})
    from . import mangel
    mangel.erledigen(item["id"], aid)              # die Aussonderung erledigt gemeldete Mängel
    durchgang.nach_aussonderung(item["id"], tag, basis_id)
    protokoll.pruefung_festschreiben(aid, ts, akteur.get("unterschrift"), akteur.get("login"), heimat, sperre)
    return aid


def sperrtag(item):
    """Der Kalendertag (deutsche Ortszeit) der aktuellen Sperre: der jüngste Journaleintrag des Artikels mit dem Übergang
    frei → gesperrt/verloren (wie die Sperren im Jahresbericht) – oder None (Altbestand ohne Journal)."""
    r = db.query("SELECT MAX(created_at) AS ts FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                 "AND created_at >= ? AND json_extract(before_json, '$.lock_state') = 'frei' "
                 "AND json_extract(after_json, '$.lock_state') IN ('gesperrt', 'verloren')",
                 (item["id"], item["created_at"]), one=True)
    return protokoll.ortszeit(r["ts"]).date().isoformat() if r and r["ts"] else None


def aussondern_grenzen(item, tag, wer=""):
    """Die Datumsgrenzen einer Aussonderung (wer: Vorsatz der Meldung, etwa die Inventarnummer eines Teils): nicht vor der
    Erfassung, der letzten abgeschlossenen Prüfung, dem Herstelldatum und dem Tag der Sperre."""
    if tag < item["created_at"][:10]:
        raise Abgelehnt(f"{wer}Das Datum liegt vor der Erfassung des Artikels.")
    # Nicht vor der letzten abgeschlossenen Prüfung und nicht vor dem Herstelldatum (C2 in P4-L1, S20): „01.03.2016“
    # statt 2026 ging vorher durch – 409 mit Klartext, die Oberfläche nennt dieselben Grenzen als Hilfetext.
    letzte = db.query("SELECT MAX(inspected_on) AS tag FROM mat_inspection WHERE item_id = ? AND completed_at IS NOT NULL",
                      (item["id"],), one=True)["tag"]
    if letzte and tag < letzte:
        raise Abgelehnt(f"{wer}Das Datum der Aussonderung ({_fmt(tag)}) liegt vor der letzten Prüfung ({_fmt(letzte)}).", 409)
    hergestellt = erster_tag(item["manufactured_on"])
    if hergestellt and tag < hergestellt.isoformat():
        raise Abgelehnt(f"{wer}Das Datum der Aussonderung ({_fmt(tag)}) liegt vor dem Herstelldatum "
                        f"({_fmt(hergestellt.isoformat())}).", 409)
    # Nicht vor dem Tag der Sperre (Ablaufprüfung V2): Ausgesondert wird, was gesperrt ist – sonst wäre ein Artikel
    # laut Datum ausgesondert, bevor er verloren ging, und der Jahresbericht zählte beides in verschiedenen Jahren.
    gesperrt = sperrtag(item)
    if gesperrt and tag < gesperrt:
        raise Abgelehnt(f"{wer}Das Datum der Aussonderung ({_fmt(tag)}) liegt vor der Sperre ({_fmt(gesperrt)}) – "
                        "ausgesondert wird, was gesperrt ist.", 409)


def aussondern(iid, d, akteur):
    """Aussonderung durch den Materialwart – nur für Artikel, die ein Prüfer vorher gesperrt hat. Eine Sperre aus einer
    Mangelmeldung zählt erst, wenn ein Prüfer den Artikel danach geprüft hat (mangel.nur_gemeldet) – so hat, was der
    Materialwart aussondert, vorher ein Sachkundiger gesehen. Auch sie wird festgeschrieben und braucht daher die
    Unterschrift dessen, der aussondert. Am Set-Artikel ist es „Set aussondern“ mit „verbleib“ je Teil
    (setaustausch.set_aussondern_wart); an einem Teil geht es nur über „Teil entnehmen“."""
    if not akteur.get("unterschrift"):
        raise Abgelehnt("Zum Aussondern fehlt deine Unterschrift – das Aussonderungsprotokoll wird damit "
                        "festgeschrieben. Bitte im Profil hinterlegen.", 403)
    art = auswahl(d.get("grund"), AUSSONDERUNGSGRUENDE, "Grund der Aussonderung")
    bemerkung = text(d, "bemerkung", "Bemerkung", 2000, einzeilig=False)
    tag = datum(d.get("datum"), "Datum") or heute().isoformat()
    if tag > heute().isoformat():
        raise Abgelehnt("Das Datum der Aussonderung liegt in der Zukunft.")
    with protokoll.dateien_sichern(), db.transaction(sofort=True):
        item = bestand.artikel(iid)
        from . import sets
        sets.teil_weiche(item, "Aussondern")              # am Teil nur über „Teil entnehmen“ (Schritt 21, K2)
        if item["lock_state"] == "ausgesondert":
            raise Abgelehnt("Der Artikel ist schon ausgesondert.", 409)
        if item["lock_state"] not in ("gesperrt", "verloren"):
            raise Abgelehnt("Aussondern lassen sich nur gesperrte Artikel – zuerst sperrt ein Prüfer (aus einer "
                            "Prüfung mit „instandsetzen“ oder direkt nach Sturz, Beschädigung oder Verlust). Eine Sperre "
                            "aus einer Mangelmeldung zählt erst, wenn ein Prüfer den Artikel danach geprüft hat.", 409)
        aussondern_grenzen(item, tag)
        offen = offener_entwurf(iid)
        if offen:
            raise Abgelehnt(reserviert_text(offen) + " Erst die Reservierung aufheben.", 409)
        from . import mangel
        if mangel.nur_gemeldet(iid):
            raise Abgelehnt(mangel.NUR_GEMELDET, 409)
        if sets.ist_set_artikel(item):
            from . import setaustausch
            return setaustausch.set_aussondern_wart(item, AUSSONDERUNGSGRUENDE[art], bemerkung, tag, akteur,
                                                    d.get("verbleib"))
        return _aussondern(item, AUSSONDERUNGSGRUENDE[art], bemerkung, tag, akteur)


# --- Berichtigung ---------------------------------------------------------------------------------------

def berichtigbar(p, item=None):
    """Lässt sich diese abgeschlossene Prüfung berichtigen? {ok, grund} – grund erklärt ein Nein."""
    def nein(grund):
        return {"ok": False, "grund": grund}
    if not p["completed_at"]:
        return nein("Ein Entwurf wird weiter bearbeitet, nicht berichtigt.")
    if p["kind"] == "aussonderung" or p["result"] == "aussondern":
        return nein("Eine Aussonderung lässt sich nicht berichtigen – der Artikel bleibt ausgesondert.")
    item = item or bestand.artikel(p["item_id"])
    if item["lock_state"] == "ausgesondert":
        return nein("Der Artikel ist ausgesondert.")
    from . import mangel
    if mangel.offene_ids(item["id"]):
        return nein(mangel.NUR_NEUE_PRUEFUNG)
    # Gesperrt, ohne dass diese Prüfung gesperrt hat („instandsetzen“): Dann kam die Sperre danach (Sturz,
    # Beschädigung, Verlust). Eine Berichtigung mit dem alten Prüftag gäbe den Artikel sonst als Freiprüfung frei. Nur mit
    # dem Set gesperrt (lock_cause „set“) zählt wie frei (A23) – frei gibt ein Set ohnehin nur eine Set-Prüfung.
    if item["lock_state"] in ("gesperrt", "verloren") and p["result"] != "instandsetzen" and item.get("lock_cause") != "set":
        return nein("Nach dieser Prüfung wurde der Artikel gesperrt – freigeben kann ihn nur eine neue Prüfung.")
    schon = _berichtigung_von(p["id"])
    if schon:
        return nein(f"Die Berichtigung ist schon in Arbeit ({schon['pruefer']})." if schon["entwurf"] else
                    f"Schon berichtigt durch {schon['protokoll_id'] or 'eine spätere Prüfung'} – berichtigt wird "
                    "dann diese.")
    # Zeitstempel haben ganze Sekunden: Bei Gleichstand entscheidet die Kennung (AUTOINCREMENT, wächst nur).
    spaeter = db.query("SELECT 1 FROM mat_inspection WHERE item_id = ? AND id <> ? AND completed_at IS NOT NULL "
                       "AND kind <> 'aussonderung' AND (completed_at > ? OR (completed_at = ? AND id > ?)) LIMIT 1",
                       (p["item_id"], p["id"], p["completed_at"], p["completed_at"], p["id"]), one=True)
    if spaeter:
        return nein("Berichtigen lässt sich nur die letzte Prüfung des Artikels – danach wurde er erneut geprüft.")
    offen = offener_entwurf(p["item_id"])
    if offen:
        return nein(reserviert_text(offen))
    return {"ok": True, "grund": ""}


def _foto_kopieren(name):
    """Mangelfoto für die Berichtigung kopieren (Original-, Web- und Vorschaufassung) – die Berichtigung hat
    eigene Dateien, damit ihr Verwerfen die des Originals nicht mitnimmt. Liefert den neuen Namen oder ''."""
    import os
    import secrets
    import shutil
    if not name:
        return ""
    d = katalog.medien_dir()
    alt_key, ext = os.path.splitext(name)
    neu_key = secrets.token_hex(8)
    paare = [(os.path.join(d, "orig", name), os.path.join(d, "orig", neu_key + ext)),
             (os.path.join(d, "web", alt_key + ".jpg"), os.path.join(d, "web", neu_key + ".jpg")),
             (os.path.join(d, "thumb", alt_key + ".jpg"), os.path.join(d, "thumb", neu_key + ".jpg"))]
    if not os.path.isfile(paare[1][0]):
        return ""
    try:
        for quelle, ziel in paare:
            if os.path.isfile(quelle):
                shutil.copyfile(quelle, ziel)
    except OSError:
        delete_photo_files(d, neu_key + ext)
        raise Abgelehnt("Ein Foto des Originals ließ sich nicht kopieren.", 500)
    return neu_key + ext


def berichtigen(pid, d, pruefer):
    """Berichtigung einer abgeschlossenen Prüfung beginnen: ein neuer Entwurf mit allen Befunden, Fotos und
    Anhängen des Originals, demselben Prüftag und derselben Prüfart, Verweis und Grund. Das Original bleibt
    unverändert (mit seinem Protokoll) und zeigt künftig „berichtigt durch …“; die Berichtigung wird wie jede
    Prüfung festgeschrieben und wirkt dann am Artikel. Berichtigen darf nur, wer die Prüfung gemacht hat, und
    nur die letzte Prüfung eines Artikels. Liefert die Kennung des neuen Entwurfs."""
    from . import durchgang
    if not pruefer.get("urkunde"):
        raise Abgelehnt(URKUNDE_FEHLT, 403)
    grund = text(d, "grund", "Grund der Berichtigung", 300, pflicht=True)
    fotos, dateien = [], []
    try:
        with db.transaction(sofort=True):
            p = pruefung(pid)
            if p["completed_at"] and not _eigen(p, pruefer):
                raise Abgelehnt(f"Berichtigen darf nur, wer die Prüfung gemacht hat ({p['inspector_name']}). Wer "
                                "selbst prüft, macht eine neue Prüfung.", 403)
            ok = berichtigbar(p)
            if not ok["ok"]:
                raise Abgelehnt(ok["grund"], 409)
            runde = None
            if p["round_id"] and durchgang.runde(p["round_id"])["closed_on"] is None:
                runde = p["round_id"]
            # Wie der Durchgang: Läuft die Set-Prüfung des Originals noch, zählt die Berichtigung dort (K2) – nur, solange
            # der Artikel noch zu diesem Set gehört; ein inzwischen entnommenes Teil berichtigt als Einzelprüfung
            # (Nachbesserung, Sicherheit 3).
            lauf = None
            lf = db.query("SELECT set_item_id FROM mat_set_lauf WHERE id = ? AND state = 'offen'", (p["set_lauf_id"],),
                          one=True) if p["set_lauf_id"] else None
            if lf:
                a = db.query("SELECT id, parent_item_id FROM mat_item WHERE id = ?", (p["item_id"],), one=True)
                if a and lf["set_item_id"] in (a["id"], a["parent_item_id"]):
                    lauf = p["set_lauf_id"]
            ts = db.now()
            neu = db.execute(
                "INSERT INTO mat_inspection (item_id, round_id, inspector_user_id, inspector_name, inspector_certificate, "
                "form_id, form_version, inspected_on, kind, reason, remarks, corrects_inspection_id, correction_reason, "
                "set_lauf_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["item_id"], runde, pruefer.get("id"), pruefer["name"], pruefer["urkunde"], p["form_id"],
                 p["form_version"], p["inspected_on"], p["kind"], p["reason"], p["remarks"], pid, grund, lauf, ts, ts))
            # Berichtigung der Set-Prüfung (Prüfung des Set-Artikels mit Teiletabelle): die Tabelle des Originals.
            from . import setlauf
            setlauf.berichtigung_zeilen(neu, pid)
            for r in befunde(pid):
                foto = _foto_kopieren(r["photo"])
                if foto:
                    fotos.append(foto)
                db.execute("INSERT INTO mat_inspection_result (inspection_id, checklist_item_id, position, group_name, "
                           "checklist_text, editor, mandatory, expected_value, is_critical, finding, value, note, photo, "
                           "signature_png) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (neu, r["checklist_item_id"], r["position"], r["group_name"], r["checklist_text"], r["editor"],
                            r["mandatory"], r["expected_value"], r["is_critical"], r["finding"], r["value"], r["note"],
                            foto, r["signature_png"]))
            for a in anhaenge(pid):
                try:
                    with open(f"{anh.anhang_dir(katalog.medien_dir())}/{a['file_path']}", "rb") as fh:
                        name, summe = anh.ablegen(katalog.medien_dir(), fh.read())
                except OSError:
                    raise Abgelehnt(f"Der Anhang „{a['title']}“ des Originals fehlt im Datenverzeichnis.", 409)
                dateien.append(name)
                db.execute("INSERT INTO mat_inspection_attachment (inspection_id, kind, title, file_path, mime, pages, "
                           "sha256, uploaded_by, uploaded_by_name, uploaded_at, in_pdf) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (neu, a["kind"], a["title"], name, a["mime"], a["pages"], summe, a["uploaded_by"],
                            a["uploaded_by_name"], a["uploaded_at"], a["in_pdf"]))
            journal.eintragen("inspection", neu, "berichtigung_begonnen", None,
                              {"item_id": p["item_id"], "kind": p["kind"], "berichtigt": pid,
                               "protocol_id": p["protocol_id"], "grund": grund, "round_id": runde})
    except BaseException:
        for f in fotos:
            delete_photo_files(katalog.medien_dir(), f)
        for f in dateien:
            anh.entfernen(katalog.medien_dir(), f)
        raise
    return neu
