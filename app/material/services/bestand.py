"""Bestand: Ordnerbaum je Gliederung und die Artikel darin.

Regeln aus dem Konzept, wie sie hier umgesetzt sind:
  - Auf oberster Ebene stehen nur Gliederungen. Darunter ist der Baum frei verschachtelbar (Standort,
    Fahrzeug, Set, persönlich, sonstiges). So hat jeder Artikel eine Gliederung – und damit die beiden
    Systemordner, in die ihn Sperre und Aussonderung verschieben.
  - Legt jemand eine Gliederung an, entstehen darunter „Gesperrt“ und „Ausgesondert“. Sie lassen sich
    weder umbenennen noch verschieben noch löschen, und niemand legt etwas von Hand hinein.
  - Inventarnummer und – falls der Hersteller keine vergibt – Seriennummer kommen vom System
    (nummern.py), beide eineindeutig. Das Bild kommt vom Produkt, nie vom Artikel.
  - retire_by (Lebensende) gibt es nur bei textilem Material: Herstelldatum + Lebensdauer. Es lässt
    sich vorziehen, nicht verschieben. Ebenso die nächste Fälligkeit: Ein neuer Artikel bekommt einen
    Vorschlag aus dem Intervall (interval.py); höher als „heute + ein Intervall“ geht es ohne Prüfung
    nicht, und danach wird sie nur noch vorgezogen – später setzt sie allein eine Prüfung.
"""
import hashlib
import json
from datetime import date

from ... import db
from ...images import delete_photo_files
from ..models import ORDNERARTEN, SYSTEMORDNER
from . import Abgelehnt, akteur, auswahl, datum, erster_tag, ganzzahl, heute, kennung, monat_oder_datum, text
from . import faelligkeit, journal, katalog, nummern, qr
from . import status as st
from .interval import faelligkeit_vorschlag, herstellerseite, lebensende, spaetestens, wirksam

SYSTEMORDNER_FEST = "„Gesperrt“ und „Ausgesondert“ gehören dem System: Sie lassen sich weder umbenennen, verschieben noch löschen."
NUR_SYSTEM = ("In „Gesperrt“ und „Ausgesondert“ kommen Artikel nur durch eine Sperre oder Aussonderung – "
              "nicht von Hand.")
GESPERRT_BLEIBT = ("Gesperrte und ausgesonderte Artikel bleiben in ihrem Systemordner. Zurück bringt einen "
                   "gesperrten Artikel nur eine Freiprüfung mit dem Ergebnis „einsatzbereit“.")
NUR_GLIEDERUNG_OBEN = "Auf oberster Ebene stehen nur Gliederungen – lege den Ordner in einer Gliederung an."
VORZIEHEN = ("Die nächste Prüfung lässt sich nur vorziehen, nicht verschieben – auf einen späteren Tag setzt "
             "sie nur eine Prüfung.")


# --- Ordner -------------------------------------------------------------------------------------------

def ordner(fid):
    o = db.query("SELECT * FROM mat_folder WHERE id = ?", (fid,), one=True)
    if not o:
        raise Abgelehnt("Ordner nicht gefunden.", 404)
    return o


def pfad(fid):
    """Ordner von der Gliederung bis hierher."""
    kette, gesehen = [], set()
    while fid and fid not in gesehen:
        gesehen.add(fid)
        o = db.query("SELECT id, parent_id, name, kind, system_kind FROM mat_folder WHERE id = ?", (fid,), one=True)
        if not o:
            break
        kette.insert(0, {"id": o["id"], "name": o["name"], "kind": o["kind"], "system_kind": o["system_kind"]})
        fid = o["parent_id"]
    return kette


def gliederung_von(fid):
    """Die nächste Gliederung über dem Ordner (oder er selbst)."""
    for o in reversed(pfad(fid)):
        if o["kind"] == "gliederung" and not o["system_kind"]:
            return o
    return None


def systemordner(gliederung_id, art):
    return db.query("SELECT * FROM mat_folder WHERE parent_id = ? AND system_kind = ?", (gliederung_id, art), one=True)


def unterbaum(fid):
    return {r["id"] for r in db.query(
        "WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f JOIN baum b ON f.parent_id = b.id) "
        "SELECT id FROM baum", (fid,))}


ORDNER_FELDER = ("name", "description", "kind", "interval_months")


def ordner_werte(d, alt=None):
    e = {f: (alt or {}).get(f) for f in ORDNER_FELDER} if alt else {}
    e.update({f: d[f] for f in ORDNER_FELDER if f in d})
    return {"name": text(e, "name", "Name", 120, pflicht=True),
            "description": text(e, "description", "Beschreibung", 2000, einzeilig=False),
            "kind": auswahl(e.get("kind") or "sonstiges", ORDNERARTEN, "Ordnertyp"),
            "interval_months": ganzzahl(e.get("interval_months"), "Prüfintervall (Monate)", 1, 120)}


def _systemordner_anlegen(gid, demo):
    ts = db.now()
    for art, name in SYSTEMORDNER.items():
        if not systemordner(gid, art):
            sid = db.execute("INSERT INTO mat_folder (parent_id, name, kind, system_kind, position, demo, created_at, "
                             "updated_at) VALUES (?,?,'sonstiges',?,?,?,?,?)",
                             (gid, name, art, 100000 + (1 if art == "ausgesondert" else 0), int(bool(demo)), ts, ts))
            journal.eintragen("folder", sid, "angelegt", None, {"name": name, "parent_id": gid, "system_kind": art})


def ordner_anlegen(d, demo=False):
    parent_id = kennung(d.get("parent_id"), "Oberordner", leer_erlaubt=True)
    w = ordner_werte(d)
    if parent_id is None and w["kind"] != "gliederung":
        raise Abgelehnt(NUR_GLIEDERUNG_OBEN)
    if parent_id is not None and ordner(parent_id)["system_kind"]:
        raise Abgelehnt(NUR_SYSTEM, 409)
    ts = db.now()
    with db.transaction(sofort=True):
        fid = db.execute("INSERT INTO mat_folder (parent_id, name, description, kind, interval_months, demo, created_at, "
                         "updated_at) VALUES (?,?,?,?,?,?,?,?)",
                         (parent_id, w["name"], w["description"], w["kind"], w["interval_months"], int(bool(demo)), ts, ts))
        journal.eintragen("folder", fid, "angelegt", None, dict(w, parent_id=parent_id))
        if w["kind"] == "gliederung":
            _systemordner_anlegen(fid, demo)
    return fid


def ordner_aendern(fid, d):
    alt = ordner(fid)
    if alt["system_kind"]:
        raise Abgelehnt(SYSTEMORDNER_FEST, 409)
    w = ordner_werte(d, alt)
    if alt["kind"] == "gliederung" and w["kind"] != "gliederung":
        raise Abgelehnt("Eine Gliederung bleibt eine Gliederung – an ihr hängen „Gesperrt“ und „Ausgesondert“. "
                        "Lege einen neuen Ordner an und verschiebe den Inhalt.", 409)
    with db.transaction():
        db.execute("UPDATE mat_folder SET name = ?, description = ?, kind = ?, interval_months = ?, updated_at = ? "
                   "WHERE id = ?", (w["name"], w["description"], w["kind"], w["interval_months"], db.now(), fid))
        if w["kind"] == "gliederung" and alt["kind"] != "gliederung":
            _systemordner_anlegen(fid, alt["demo"])
        journal.aenderung("folder", fid, alt, w)
        if w["interval_months"] != alt["interval_months"]:
            faelligkeit.kappen(*faelligkeit.im_unterbaum(fid))


def ordner_verschieben(fid, ziel_id):
    # Prüfen und Schreiben unter einer Schreibsperre: Zwei gleichzeitige Verschiebungen A→B und B→A
    # bestünden einzeln jede Prüfung und ergäben zusammen einen Zyklus, der aus dem Baum fällt.
    with db.transaction(sofort=True):
        alt = ordner(fid)
        if alt["system_kind"]:
            raise Abgelehnt(SYSTEMORDNER_FEST, 409)
        if ziel_id is None:
            if alt["kind"] != "gliederung":
                raise Abgelehnt(NUR_GLIEDERUNG_OBEN)
        else:
            if ordner(ziel_id)["system_kind"]:
                raise Abgelehnt(NUR_SYSTEM, 409)
            if ziel_id in unterbaum(fid):
                raise Abgelehnt("Ein Ordner kann nicht in sich selbst liegen.")
        if ziel_id == alt["parent_id"]:
            return
        db.execute("UPDATE mat_folder SET parent_id = ?, updated_at = ? WHERE id = ?", (ziel_id, db.now(), fid))
        journal.eintragen("folder", fid, "verschoben",
                          {"parent_id": alt["parent_id"], "pfad": _pfad_text(alt["parent_id"])},
                          {"parent_id": ziel_id, "pfad": _pfad_text(ziel_id)})
        faelligkeit.kappen(*faelligkeit.im_unterbaum(fid))


def _pfad_text(fid):
    return " / ".join(o["name"] for o in pfad(fid)) if fid else "(oberste Ebene)"


def ordner_loeschen(fid):
    alt = ordner(fid)
    if alt["system_kind"]:
        raise Abgelehnt(SYSTEMORDNER_FEST, 409)
    kinder = db.query("SELECT * FROM mat_folder WHERE parent_id = ?", (fid,))
    if any(not k["system_kind"] for k in kinder):
        raise Abgelehnt("Der Ordner hat Unterordner – erst diese verschieben oder löschen.", 409)
    betroffen = [fid] + [k["id"] for k in kinder]
    marken = ",".join("?" * len(betroffen))
    if db.query(f"SELECT 1 FROM mat_item WHERE folder_id IN ({marken}) LIMIT 1", betroffen, one=True):
        raise Abgelehnt("Im Ordner liegen noch Artikel (auch gesperrte oder ausgesonderte zählen).", 409)
    if db.query(f"SELECT 1 FROM mat_round WHERE folder_id IN ({marken}) LIMIT 1", betroffen, one=True):
        raise Abgelehnt("Für diesen Ordner gibt es Prüfdurchgänge – er bleibt.", 409)
    if db.query(f"SELECT 1 FROM mat_item WHERE origin_folder_id IN ({marken}) LIMIT 1", betroffen, one=True):
        raise Abgelehnt("Gesperrte Artikel kehren nach ihrer Freiprüfung hierher zurück – der Ordner bleibt.", 409)
    with db.transaction():
        for k in kinder:
            db.execute("DELETE FROM mat_folder WHERE id = ?", (k["id"],))
            journal.eintragen("folder", k["id"], "geloescht", k, None)
        db.execute("DELETE FROM mat_folder WHERE id = ?", (fid,))
        journal.eintragen("folder", fid, "geloescht", alt, None)
    if alt["photo"]:
        delete_photo_files(katalog.medien_dir(), alt["photo"])


def ordner_foto_setzen(fid, file_storage):
    alt = ordner(fid)
    if alt["system_kind"]:
        raise Abgelehnt(SYSTEMORDNER_FEST, 409)
    neu = katalog.foto_ablegen(file_storage)
    with db.transaction():
        if not db.execute_zeilen("UPDATE mat_folder SET photo = ?, updated_at = ? WHERE id = ? AND photo = ?",
                                 (neu, db.now(), fid, alt["photo"])):
            delete_photo_files(katalog.medien_dir(), neu)
            raise Abgelehnt("Das Foto wurde zwischenzeitlich anderswo geändert. Bitte neu laden.", 409)
        journal.eintragen("folder", fid, "foto", {"photo": alt["photo"]}, {"photo": neu})
    if alt["photo"]:
        delete_photo_files(katalog.medien_dir(), alt["photo"])


def ordner_foto_entfernen(fid):
    alt = ordner(fid)
    if not alt["photo"]:
        return
    with db.transaction():
        if not db.execute_zeilen("UPDATE mat_folder SET photo = '', updated_at = ? WHERE id = ? AND photo = ?",
                                 (db.now(), fid, alt["photo"])):
            return
        journal.eintragen("folder", fid, "foto", {"photo": alt["photo"]}, {"photo": ""})
    delete_photo_files(katalog.medien_dir(), alt["photo"])


def _zaehlungen():
    """Status je Ordner (nur direkt darin liegende Artikel) – eine Abfrage für den ganzen Baum."""
    out = {}
    for r in db.query(f"SELECT folder_id, {st.status_sql('i')} AS s, COUNT(*) AS n FROM mat_item i "
                      f"GROUP BY folder_id, s", st.parameter()):
        out.setdefault(r["folder_id"], st.leere_zaehlung())[r["s"]] = r["n"]
    return out


def ordner_json(o, direkt=None, gesamt=None):
    out = {f: o[f] for f in ("id", "parent_id", "name", "description", "kind", "system_kind", "interval_months",
                             "position", "created_at", "updated_at")}
    out["demo"] = bool(o["demo"])
    out["foto"] = katalog.bild_url(o["photo"])
    out["vorschau"] = katalog.bild_url(o["photo"], "thumb")
    if direkt is not None:
        out["direkt"] = direkt
    if gesamt is not None:
        out["zaehlung"] = gesamt
        out["bestand"] = sum(gesamt[s] for s in st.BESTAND)
    return out


def baum():
    """Alle Ordner flach mit Zählungen: direkt darin und im ganzen Unterbaum. Den Baum zeichnet die
    Oberfläche aus parent_id."""
    ordner_alle = db.query("SELECT * FROM mat_folder ORDER BY position, name COLLATE NOCASE")
    direkt = _zaehlungen()
    gesamt = {o["id"]: dict(direkt.get(o["id"], st.leere_zaehlung())) for o in ordner_alle}
    eltern = {o["id"]: o["parent_id"] for o in ordner_alle}
    for fid, z in direkt.items():
        p, gesehen = eltern.get(fid), set()
        while p and p not in gesehen:
            gesehen.add(p)
            for s, n in z.items():
                gesamt[p][s] += n
            p = eltern.get(p)
    return [ordner_json(o, direkt.get(o["id"], st.leere_zaehlung()), gesamt[o["id"]]) for o in ordner_alle]


# --- Artikel ---------------------------------------------------------------------------------------

ARTIKEL_FELDER = ("product_id", "serial_no", "manufactured_on", "purchased_on", "first_use_on", "next_due_on",
                  "retire_by", "interval_months", "notes")


def artikel(iid):
    i = db.query("SELECT * FROM mat_item WHERE id = ?", (iid,), one=True)
    if not i:
        raise Abgelehnt("Artikel nicht gefunden.", 404)
    return i


def ablageordner_pruefen(fid):
    """Wohin ein Artikel von Hand darf: in jeden Ordner einer Gliederung außer den Systemordnern."""
    o = ordner(fid)
    if o["system_kind"]:
        raise Abgelehnt(NUR_SYSTEM, 409)
    if not gliederung_von(fid):
        raise Abgelehnt("Artikel liegen immer unterhalb einer Gliederung.")
    return o


def _vor(a, b):
    """Liegt a vor b? Beide 'YYYY-MM' oder 'YYYY-MM-DD'; ist eins nur ein Monat, zählt der Monat – ein Erstgebrauch
    „05/2025“ liegt nicht vor einer Herstellung am 20.05.2025, und der laufende Monat liegt nicht in der Zukunft."""
    if len(a) == 7 or len(b) == 7:
        return a[:7] < b[:7]
    return a < b


def artikel_werte(d, alt=None):
    e = {f: alt.get(f) for f in ARTIKEL_FELDER} if alt else {}
    e.update({f: d[f] for f in ARTIKEL_FELDER if f in d})
    w = {"product_id": kennung(e.get("product_id"), "Produkt"),
         "serial_no": text(e, "serial_no", "Seriennummer", 80),
         "manufactured_on": monat_oder_datum(e.get("manufactured_on"), "Herstelldatum"),
         # Kauf und Erstgebrauch wie die Herstellung: Monat genügt (so steht es auf Rechnung und Prüfkarte).
         "purchased_on": monat_oder_datum(e.get("purchased_on"), "Kaufdatum"),
         "first_use_on": monat_oder_datum(e.get("first_use_on"), "Erstgebrauch"),
         "next_due_on": datum(e.get("next_due_on"), "Nächste Prüfung"),
         "retire_by": datum(e.get("retire_by"), "Lebensende"),
         "interval_months": ganzzahl(e.get("interval_months"), "Prüfintervall (Monate)", 1, 120),
         "notes": text(e, "notes", "Bemerkung", 4000, einzeilig=False)}
    p = katalog.produkt(w["product_id"])
    h = heute()
    hergestellt = erster_tag(w["manufactured_on"])
    if hergestellt and hergestellt > h:
        raise Abgelehnt("Das Herstelldatum liegt in der Zukunft.")
    for feld, name in (("purchased_on", "Kaufdatum"), ("first_use_on", "Erstgebrauch")):
        if w[feld] and w["manufactured_on"] and _vor(w[feld], w["manufactured_on"]):
            raise Abgelehnt(f"{name} liegt vor dem Herstelldatum.")
        # Ein Datum in der Zukunft verschöbe die errechnete erste Fälligkeit über „heute + Intervall“
        # hinaus – ein Artikel stünde ohne Prüfung jahrelang als einsatzbereit da.
        if w[feld] and _vor(h.isoformat(), w[feld]):
            raise Abgelehnt(f"{name} liegt in der Zukunft.")
    if p["material_kind"] == "textil" and not w["manufactured_on"]:
        raise Abgelehnt("Bei textilem Material ist das Herstelldatum Pflicht – an ihm hängt die Lebensdauer.")
    if w["serial_no"] and nummern.sieht_generiert_aus(w["serial_no"]) and (
            not alt or w["serial_no"].casefold() != alt["serial_no"].casefold()):
        raise Abgelehnt("Seriennummern der Form „STR-…“ vergibt nur das System – bitte die Herstellernummer "
                        "eintragen oder das Feld leer lassen.")
    hm = herstellerseite(p)[0]
    if w["interval_months"] and hm and w["interval_months"] > hm:
        raise Abgelehnt(f"Das Intervall am Artikel darf die Herstellervorgabe ({hm} Monate) nicht überschreiten.")
    return w, p


def _lebensende_wirksam(rechnung, manuell):
    """Wirksames Lebensende: die Rechnung, außer ein vorgezogenes Datum liegt früher."""
    if rechnung and manuell:
        return min(rechnung, manuell)
    return rechnung or manuell


def _serie_frei(produkt_id, serie, ausser=None):
    andere = db.query("SELECT id, inventory_no FROM mat_item WHERE product_id = ? AND serial_no = ? COLLATE NOCASE",
                      (produkt_id, serie), one=True)
    if andere and andere["id"] != ausser:
        raise Abgelehnt(f"Diese Seriennummer gibt es bei diesem Produkt schon (Inventarnummer {andere['inventory_no']}).",
                        409)


def vorschlag(d):
    """Was das System einem neuen Artikel vorschlägt – für das Formular, bevor gespeichert wird."""
    p = katalog.produkt(kennung(d.get("product_id"), "Produkt"))
    fid = kennung(d.get("folder_id"), "Ordner", leer_erlaubt=True)
    monate = ganzzahl(d.get("interval_months"), "Prüfintervall (Monate)", 1, 120)
    iv = wirksam(p, fid, monate)
    erst = monat_oder_datum(d.get("first_use_on"), "Erstgebrauch")
    kauf = monat_oder_datum(d.get("purchased_on"), "Kaufdatum")
    herst = monat_oder_datum(d.get("manufactured_on"), "Herstelldatum")
    h = heute().isoformat()
    for wert, name in ((erst, "Erstgebrauch"), (kauf, "Kaufdatum")):
        if wert and _vor(h, wert):
            raise Abgelehnt(f"{name} liegt in der Zukunft.")
    grenze = spaetestens(iv["monate"])
    vorschlag_due = faelligkeit_vorschlag(iv["monate"], erst, kauf)
    return {"intervall": iv,
            "next_due_on": min(vorschlag_due, grenze) if vorschlag_due and grenze else vorschlag_due,
            "spaetestens": grenze,
            "retire_by": lebensende(herst, p["lifetime_years"]) if p["material_kind"] == "textil" else None,
            "material_kind": p["material_kind"], "lifetime_years": p["lifetime_years"],
            "lifetime_source": p["lifetime_source"]}


def artikel_anlegen(d):
    w, p = artikel_werte(d)
    fid = kennung(d.get("folder_id"), "Ordner")
    ablageordner_pruefen(fid)
    iv = wirksam(p, fid, w["interval_months"])
    if not iv["monate"]:
        raise Abgelehnt(katalog.KEIN_INTERVALL)
    manuell = None
    if p["material_kind"] == "textil":
        rechnung = lebensende(w["manufactured_on"], p["lifetime_years"])
        if w["retire_by"] and w["retire_by"] > rechnung:
            raise Abgelehnt(f"Das Lebensende lässt sich nur vorziehen (spätestens {rechnung}).")
        manuell = w["retire_by"] if w["retire_by"] and w["retire_by"] < rechnung else None
        w["retire_by"] = _lebensende_wirksam(rechnung, manuell)
    elif w["retire_by"]:
        raise Abgelehnt("Ein Lebensende gibt es nur bei textilem Material.")
    grenze = spaetestens(iv["monate"])
    if not w["next_due_on"]:
        w["next_due_on"] = min(faelligkeit_vorschlag(iv["monate"], w["first_use_on"], w["purchased_on"]), grenze)
    elif w["next_due_on"] > grenze:
        raise Abgelehnt(f"Ohne Prüfung liegt die nächste Fälligkeit höchstens ein Intervall in der Zukunft "
                        f"(spätestens {grenze}).")
    uid, _ = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        inventar = nummern.naechste_inventarnummer()
        serie, generiert = (w["serial_no"], 0) if w["serial_no"] else (nummern.seriennummer_fuer(inventar), 1)
        _serie_frei(p["id"], serie)
        iid = db.execute(
            "INSERT INTO mat_item (product_id, folder_id, serial_no, serial_generated, inventory_no, manufactured_on, "
            "purchased_on, first_use_on, retire_by, retire_by_manual, lock_state, next_due_on, interval_months, qr_token, "
            "notes, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,'frei',?,?,?,?,?,?,?)",
            (p["id"], fid, serie, generiert, inventar, w["manufactured_on"], w["purchased_on"], w["first_use_on"],
             w["retire_by"], manuell, w["next_due_on"], w["interval_months"], qr.neues_token(), w["notes"], uid, ts, ts))
        journal.eintragen("item", iid, "angelegt", None,
                          dict(w, folder_id=fid, serial_no=serie, serial_generated=generiert, inventory_no=inventar,
                               retire_by_manual=manuell, ordner=_pfad_text(fid)))
    return iid


def stand_von(i):
    """Fingerabdruck einer Artikelzeile: ändert sich mit jedem Feld – genauer als updated_at, das nur
    sekundengenau ist."""
    return hashlib.sha256(json.dumps(dict(i), sort_keys=True, default=str).encode()).hexdigest()[:20]


def artikel_aendern(iid, d):
    alt = artikel(iid)
    # Der Dialog schickt den Stand mit, den er geladen hat. Hat sich der Artikel seitdem geändert (eine
    # Prüfung, eine Sperre), überschriebe er sonst still deren Ergebnis – etwa die neue Fälligkeit.
    if d.get("stand") and d.get("stand") != stand_von(alt):
        raise Abgelehnt("Der Artikel wurde inzwischen geändert (etwa durch eine Prüfung). Bitte neu laden.", 409)
    if alt["lock_state"] == "ausgesondert":
        raise Abgelehnt("Ein ausgesonderter Artikel bleibt, wie er ist.", 409)
    if "folder_id" in d and d.get("folder_id") != alt["folder_id"]:
        raise Abgelehnt("Den Ordner wechselt „Verschieben“.")
    for fest in ("inventory_no", "qr_token", "lock_state"):
        if fest in d and d.get(fest) != alt[fest]:
            raise Abgelehnt("Inventarnummer, QR-Kennung und Sperrzustand lassen sich nicht bearbeiten.")
    w, p = artikel_werte(d, alt)
    if w["product_id"] != alt["product_id"] and db.query("SELECT 1 FROM mat_inspection WHERE item_id = ? LIMIT 1",
                                                         (iid,), one=True):
        raise Abgelehnt("Das Produkt lässt sich nur ändern, solange der Artikel nicht geprüft wurde.", 409)
    # Seriennummer: leer heißt „bleibt“. Eine echte Herstellernummer ersetzt die vergebene.
    if not w["serial_no"]:
        w["serial_no"], generiert = alt["serial_no"], alt["serial_generated"]
    else:
        generiert = alt["serial_generated"] if w["serial_no"].casefold() == alt["serial_no"].casefold() else 0
    # Lebensende: nur textil. Es ist die Rechnung aus Herstelldatum und Lebensdauer – oder ein von Hand
    # vorgezogenes Datum, solange das früher liegt. Ein neues Datum muss vor dem bisherigen liegen
    # (nur vorziehen, auch ein schon vorgezogenes nicht wieder nach hinten); ein leeres Feld lässt es,
    # wie es ist. Das vorgezogene Datum bleibt gespeichert, auch wenn eine Korrektur der Lebensdauer es
    # zeitweise überholt.
    manuell = alt["retire_by_manual"]
    if p["material_kind"] == "textil":
        rechnung = lebensende(w["manufactured_on"], p["lifetime_years"])
        if "retire_by" in d and d.get("retire_by") not in (None, "") and w["retire_by"] != alt["retire_by"]:
            if w["retire_by"] > rechnung or (alt["retire_by"] and w["retire_by"] > alt["retire_by"]):
                raise Abgelehnt(f"Das Lebensende lässt sich nur vorziehen (spätestens "
                                f"{min(rechnung, alt['retire_by'] or rechnung)}).")
            manuell = w["retire_by"]
        w["retire_by"] = _lebensende_wirksam(rechnung, manuell)
    else:
        if "retire_by" in d and d.get("retire_by") not in (None, ""):
            raise Abgelehnt("Ein Lebensende gibt es nur bei textilem Material.")
        w["retire_by"], manuell = None, None
    # Fälligkeit: nur vorziehen – und nie über „heute + wirksames Intervall“ hinaus, wie beim Anlegen.
    iv = wirksam(p, alt["folder_id"], w["interval_months"])
    if not iv["monate"]:
        raise Abgelehnt(katalog.KEIN_INTERVALL)
    grenze = spaetestens(iv["monate"])
    if w["next_due_on"] != alt["next_due_on"]:
        if not w["next_due_on"]:
            raise Abgelehnt("Die nächste Prüfung lässt sich nicht löschen.")
        if alt["next_due_on"] and w["next_due_on"] > alt["next_due_on"]:
            raise Abgelehnt(VORZIEHEN)
        if alt.get("last_inspected_on") and w["next_due_on"] <= alt["last_inspected_on"]:
            raise Abgelehnt(f"Die nächste Prüfung muss nach der letzten Prüfung ({alt['last_inspected_on']}) liegen.")
        if w["next_due_on"] > grenze:
            raise Abgelehnt(f"Ohne Prüfung liegt die nächste Fälligkeit höchstens ein Intervall in der Zukunft "
                            f"(spätestens {grenze}).")
    neu = dict(w, serial_generated=generiert, retire_by_manual=manuell)
    with db.transaction(sofort=True):
        _serie_frei(w["product_id"], w["serial_no"], ausser=iid)
        db.execute("UPDATE mat_item SET product_id = ?, serial_no = ?, serial_generated = ?, manufactured_on = ?, "
                   "purchased_on = ?, first_use_on = ?, retire_by = ?, retire_by_manual = ?, next_due_on = ?, "
                   "interval_months = ?, notes = ?, updated_at = ? WHERE id = ?",
                   (w["product_id"], w["serial_no"], generiert, w["manufactured_on"], w["purchased_on"],
                    w["first_use_on"], w["retire_by"], manuell, w["next_due_on"], w["interval_months"], w["notes"],
                    db.now(), iid))
        journal.aenderung("item", iid, alt, neu)
        # Ein anderes Produkt oder ein kürzeres Intervall am Artikel zieht die Fälligkeit nach.
        faelligkeit.kappen("i.id = ?", (iid,))


def artikel_verschieben(ids, ziel_id):
    """Mehrere Artikel auf einmal in einen Ordner – ganz oder gar nicht."""
    if not isinstance(ids, list) or not ids or len(ids) > 500:
        raise Abgelehnt("Bitte 1 bis 500 Artikel auswählen.")
    ids = [kennung(x, "Artikel") for x in ids]
    # Prüfen und Schreiben unter einer Sperre: Eine Sperre, die dazwischen fertig wird, holte den Artikel
    # sonst wieder aus „Gesperrt“ heraus.
    with db.transaction(sofort=True):
        ablageordner_pruefen(ziel_id)
        zeilen = db.query(f"SELECT * FROM mat_item WHERE id IN ({','.join('?' * len(ids))})", ids)
        if len(zeilen) != len(set(ids)):
            raise Abgelehnt("Mindestens ein Artikel wurde nicht gefunden.", 404)
        if any(z["lock_state"] != "frei" for z in zeilen):
            raise Abgelehnt(GESPERRT_BLEIBT, 409)
        ziel_text = _pfad_text(ziel_id)
        for z in zeilen:
            if z["folder_id"] == ziel_id:
                continue
            if not db.execute_zeilen("UPDATE mat_item SET folder_id = ?, updated_at = ? WHERE id = ? AND lock_state = 'frei'",
                                     (ziel_id, db.now(), z["id"])):
                raise Abgelehnt(GESPERRT_BLEIBT, 409)
            journal.eintragen("item", z["id"], "verschoben",
                              {"folder_id": z["folder_id"], "ordner": _pfad_text(z["folder_id"])},
                              {"folder_id": ziel_id, "ordner": ziel_text})
        faelligkeit.kappen(f"i.id IN ({','.join('?' * len(ids))})", ids)
    return len(zeilen)


def artikel_loeschen(iid):
    """Nur ein falsch angelegter Artikel ohne Prüfung lässt sich löschen; seine Inventarnummer wird nie
    wieder vergeben. Alles andere wird ausgesondert, nicht gelöscht."""
    with db.transaction(sofort=True):
        alt = artikel(iid)
        if db.query("SELECT 1 FROM mat_inspection WHERE item_id = ? LIMIT 1", (iid,), one=True):
            raise Abgelehnt("Der Artikel hat Prüfungen und bleibt mit seinem Lebenslauf – aussondern statt löschen.", 409)
        if db.query("SELECT 1 FROM mat_round_item WHERE item_id = ? LIMIT 1", (iid,), one=True):
            raise Abgelehnt("Der Artikel steht in einem Prüfdurchgang und bleibt.", 409)
        db.execute("DELETE FROM mat_item WHERE id = ?", (iid,))
        journal.eintragen("item", iid, "geloescht", dict(alt, ordner=_pfad_text(alt["folder_id"])), None)


# Mit dem offenen Entwurf (höchstens einer je Artikel): Listen zeigen „in Prüfung bei …“.
ARTIKEL_LISTE_SQL = ("SELECT i.*, p.manufacturer, p.model, p.article_no, p.material_kind, p.image AS product_image, "
                     "p.demo AS product_demo, e.id AS entwurf_id, e.inspector_name AS entwurf_pruefer, "
                     "e.inspector_user_id AS entwurf_pruefer_id FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
                     "LEFT JOIN mat_inspection e ON e.item_id = i.id AND e.completed_at IS NULL ")


def artikel_kurz(i, stichtag=None):
    """Eine Zeile für Listen: Nummern, Produkt, Ordner, Fälligkeiten, Status."""
    s = st.status(i, stichtag)
    return {"id": i["id"], "inventory_no": i["inventory_no"], "serial_no": i["serial_no"],
            "serial_generated": bool(i["serial_generated"]), "folder_id": i["folder_id"],
            "product_id": i["product_id"], "manufacturer": i.get("manufacturer"), "model": i.get("model"),
            "article_no": i.get("article_no"), "material_kind": i.get("material_kind"),
            "vorschau": katalog.bild_url(i.get("product_image"), "thumb"), "demo": bool(i.get("product_demo")),
            "next_due_on": i["next_due_on"], "retire_by": i["retire_by"], "lock_state": i["lock_state"],
            "last_inspected_on": i.get("last_inspected_on"), "status": s, "status_text": st.LABEL[s],
            "entwurf": ({"id": i["entwurf_id"], "pruefer": i.get("entwurf_pruefer"),
                         "pruefer_id": i.get("entwurf_pruefer_id")} if i.get("entwurf_id") else None)}


def artikel_json(i, voll=False):
    p = katalog.produkt(i["product_id"])
    s = st.status(i)
    iv = wirksam(p, i["folder_id"], i["interval_months"])
    gl = gliederung_von(i["folder_id"])
    out = {f: i[f] for f in ("id", "product_id", "folder_id", "origin_folder_id", "serial_no", "inventory_no",
                             "manufactured_on", "purchased_on", "first_use_on", "retire_by", "lock_state",
                             "lock_reason", "next_due_on", "interval_months", "notes", "created_at", "updated_at",
                             "last_inspected_on")}
    out["serial_generated"] = bool(i["serial_generated"])
    out["stand"] = stand_von(i)
    out["status"], out["status_text"] = s, st.LABEL[s]
    out["produkt"] = katalog.produkt_json(p)
    out["pfad"] = pfad(i["folder_id"])
    out["gliederung"] = gl
    out["intervall"] = iv
    out["qr_adresse"] = qr.adresse(i["qr_token"])
    if p["material_kind"] == "textil" and i["retire_by"]:
        out["lebensdauer"] = {"ende": i["retire_by"], "festgeschrieben": True,
                              "rest_tage": (date.fromisoformat(i["retire_by"]) - heute()).days,
                              "jahre": p["lifetime_years"],
                              "vorgezogen": bool(i["retire_by_manual"]) and i["retire_by"] == i["retire_by_manual"]}
    elif p["lifetime_years"]:
        out["lebensdauer"] = {"festgeschrieben": False, "jahre": p["lifetime_years"], "quelle": p["lifetime_source"]}
    else:
        out["lebensdauer"] = None
    if voll:
        out["journal"] = journal.fuer_artikel(i)
        out["dokumente"] = katalog.gueltige_dokumente(p["id"], heute().isoformat())   # samt denen der Kategorien
        f = katalog.formular_fuer_produkt(p["id"])
        out["formular"] = ({"id": f["id"], "version": f["version"], "title": f["title"], "quelle": f["quelle"],
                            "punkte": f["punkte_anzahl"]} if f else None)
        from . import durchgang, pruefung
        out["pruefungen"] = pruefung.fuer_artikel(i["id"])
        e = pruefung.offener_entwurf(i["id"])
        out["entwurf"] = ({"id": e["id"], "pruefer": e["inspector_name"], "pruefer_id": e["inspector_user_id"],
                           "seit": e["created_at"], "art": e["kind"]} if e else None)
        if i["lock_state"] != "ausgesondert":
            arten, vorschlag = pruefung.arten_fuer(i)
            out["pruefarten"] = {"arten": arten, "vorschlag": vorschlag}
        rid = durchgang.offene_runde_fuer(i["id"])
        out["durchgang"] = ({"id": rid, "titel": durchgang.runde(rid)["title"]} if rid else None)
        out["darf_loeschen"] = not out["pruefungen"]
    return out


def artikel_sortierung():
    """Sortierbare Spalten der Artikellisten: Name in der Anfrage → SQL über i = mat_item, p = mat_product.
    „faellig“ stellt neue Artikel (Eingangsprüfung) nach vorn und gesperrte und ausgesonderte nach hinten,
    „status“ sortiert nach Dringlichkeit. Die Stichtage stehen als Literale im Ausdruck (vom Server
    berechnete ISO-Daten), damit er auch in Abfragen mit ?-Parametern taugt (Suche)."""
    par = st.parameter()
    status = st.status_sql("i").replace(":st_heute", f"'{par['st_heute']}'").replace(":st_bald", f"'{par['st_bald']}'")
    return {
        "inventar": "i.inventory_no",
        "hersteller": "p.manufacturer COLLATE NOCASE",
        "produkt": "p.model COLLATE NOCASE",
        "serie": "i.serial_no COLLATE NOCASE",
        "faellig": ("CASE WHEN i.lock_state <> 'frei' THEN NULL WHEN i.last_inspected_on IS NULL THEN '' "
                    "ELSE i.next_due_on END"),
        "status": (f"CASE {status} WHEN 'ueberfaellig' THEN 0 WHEN 'lebensdauer' THEN 1 WHEN 'neu' THEN 2 "
                   f"WHEN 'gesperrt' THEN 3 WHEN 'bald_faellig' THEN 4 WHEN 'einsatzbereit' THEN 5 ELSE 6 END"),
    }


def ordner_inhalt(fid, status_filter=None, seite=1, pro_seite=100, sort=None, richtung="auf"):
    """Ein Ordner mit Pfad, Unterordnern (mit Zählung) und den Artikeln direkt darin."""
    from .search import sortierung
    ordnung = sortierung(artikel_sortierung(), sort, richtung, "i.inventory_no")
    o = ordner(fid)
    alle = {x["id"]: x for x in baum()}
    kinder = [x for x in alle.values() if x["parent_id"] == fid]
    kinder.sort(key=lambda x: (x["system_kind"] is not None, x["position"], x["name"].casefold()))
    params = dict(st.parameter(), fid=fid)
    bedingung = "WHERE i.folder_id = :fid"
    if status_filter:
        if status_filter not in st.STATUS:
            raise Abgelehnt("Unbekannter Status.")
        bedingung += f" AND {st.status_sql('i')} = :sf"
        params["sf"] = status_filter
    gesamt = db.query(f"SELECT COUNT(*) AS n FROM mat_item i {bedingung}", params, one=True)["n"]
    seite = max(1, int(seite or 1))
    rows = db.query(ARTIKEL_LISTE_SQL + bedingung + f" ORDER BY {ordnung} LIMIT :lim OFFSET :off",
                    dict(params, lim=pro_seite, off=(seite - 1) * pro_seite))
    out = alle[fid]
    out["pfad"] = pfad(fid)
    gl = gliederung_von(fid)
    out["gliederung"] = gl
    out["unterordner"] = kinder
    out["artikel"] = [artikel_kurz(r) for r in rows]
    out["artikel_gesamt"] = gesamt
    out["seite"], out["pro_seite"] = seite, pro_seite
    out["journal"] = journal.lesen([("folder", fid)], grenze=50)
    out["intervall"] = {"monate": o["interval_months"]}
    return out


# Fällig ist, was vor dem nächsten Einsatz ein Prüfer in die Hand nehmen muss: überfällig, Lebensdauer erreicht
# (die Prüfung endet mit „aussondern“), neu (Eingangsprüfung) und bald fällig. Dieselbe Regel wie das rote
# Abzeichen der Ordnerleiste, das überfällig und Lebensdauer erreicht zusammen zählt.
FAELLIG = ("ueberfaellig", "lebensdauer", "neu", "bald_faellig")


def faellige(ordner_id=None, nur=FAELLIG, seite=1, pro_seite=100, sort=None, richtung="auf"):
    """Artikel, die geprüft werden müssen – überfällige zuerst, dann die am Lebensende, dann neue
    (Eingangsprüfung), dann nach Datum; oder nach einer gewählten Spalte."""
    from .search import sortierung
    params = st.parameter()
    bedingungen = [f"{st.status_sql('i')} IN ({','.join(':n' + str(k) for k in range(len(nur)))})"]
    params.update({f"n{k}": s for k, s in enumerate(nur)})
    if ordner_id:
        # Der Unterbaum in der Abfrage selbst – nicht ein Parameter je Ordner.
        bedingungen.append("i.folder_id IN (WITH RECURSIVE baum(id) AS (SELECT :ordner UNION SELECT f.id FROM mat_folder f "
                           "JOIN baum b ON f.parent_id = b.id) SELECT id FROM baum)")
        params["ordner"] = ordner_id
    where = "WHERE " + " AND ".join(bedingungen)
    gesamt = db.query(f"SELECT COUNT(*) AS n FROM mat_item i {where}", params, one=True)["n"]
    reihe = (f"CASE {st.status_sql('i')} WHEN 'ueberfaellig' THEN 0 WHEN 'lebensdauer' THEN 1 WHEN 'neu' THEN 2 "
             f"WHEN 'bald_faellig' THEN 3 ELSE 4 END")
    ordnung = sortierung(artikel_sortierung(), sort, richtung,
                         f"{reihe}, i.next_due_on IS NOT NULL, i.next_due_on, i.inventory_no")
    rows = db.query(ARTIKEL_LISTE_SQL + where + f" ORDER BY {ordnung} LIMIT :lim OFFSET :off",
                    dict(params, lim=pro_seite, off=(max(1, seite) - 1) * pro_seite))
    liste = []
    for r in rows:
        k = artikel_kurz(r)
        k["pfad"] = _pfad_text(r["folder_id"])
        liste.append(k)
    return liste, gesamt


def zaehlung(ordner_ids=None):
    params = st.parameter()
    where = ""
    if ordner_ids is not None:
        ordner_ids = list(ordner_ids) or [0]
        where = f"WHERE i.folder_id IN ({','.join(':f' + str(k) for k in range(len(ordner_ids)))})"
        params.update({f"f{k}": fid for k, fid in enumerate(ordner_ids)})
    z = st.leere_zaehlung()
    for r in db.query(f"SELECT {st.status_sql('i')} AS s, COUNT(*) AS n FROM mat_item i {where} GROUP BY s", params):
        z[r["s"]] = r["n"]
    return z
