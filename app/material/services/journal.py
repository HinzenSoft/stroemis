"""Änderungsjournal (mat_audit): wer hat wann was geändert – mit Vorher und Nachher je Feld.

Geschrieben wird in derselben Transaktion wie die Änderung selbst: Eine Änderung ohne Eintrag gibt
es damit nicht, ein Eintrag ohne Änderung auch nicht. Gelesen wird es am Produkt, am Artikel (dort
zusammen mit dem Journal seines Produkts) und an Ordnern. Die Tabelle ist per Trigger nur
fortschreibbar (models.py).

Seit Phase 2 stehen Betroffene nur pseudonym darin (Kontoverweise, unten). Beim Lesen wird ein Verweis zum Namen
aufgelöst – die Antworten tragen den Namen, nie den Verweis selbst. Wer welches Journal lesen darf, entscheiden die
Aufrufer (Grundrecht am Ordner bzw. Artikel, Freigabe-Einträge nur für Verwalter, Meldungen über darf_meldung)."""
import json
import secrets

from flask import g, has_request_context

from ... import db
from ...auth import current_user
from . import OHNE_NAMEN

# Felder, die nie ins Journal gehören: Binärdaten und reine Zeitstempel der Zeile selbst.
_AUSGENOMMEN = {"signature_png", "created_at", "updated_at", "dedupe_key"}


def _sauber(daten):
    if daten is None:
        return None
    return {k: v for k, v in dict(daten).items() if k not in _AUSGENOMMEN and not isinstance(v, (bytes, bytearray))}


def unterschied(alt, neu):
    """Nur die geänderten Felder, jeweils vorher und nachher. Gleich ist gleich – auch wenn ein
    Feld einmal None und einmal leer ist, zählt das als Änderung; das Journal soll nichts glätten."""
    alt, neu = _sauber(alt) or {}, _sauber(neu) or {}
    felder = [k for k in neu if k in alt and alt[k] != neu[k]]
    return {k: alt[k] for k in felder}, {k: neu[k] for k in felder}


def _als_text(werte):
    return json.dumps(_sauber(werte), ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)


def eintragen(entity, entity_id, action, vorher=None, nachher=None, name=None):
    """Einen Eintrag schreiben. name: Anzeigename, wenn niemand angemeldet ist (Import, Startlauf);
    ein Kommandozeilenlauf setzt ihn für alle Einträge über g.mat_akteur. Wer angemeldet handelt, steht mit Namen da –
    nie mit der E-Mail. NaN und Unendlich nimmt json.dumps hier nicht an (allow_nan=False – ValueError statt eines
    ungültigen JSON im unveränderlichen Journal, das sonst jede Antwort mit diesem Eintrag unlesbar machte)."""
    u = current_user() if has_request_context() else None
    if not u and not name:
        name = g.get("mat_akteur")
    db.execute(
        "INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, after_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (entity, entity_id, u["id"] if u else None,
         ((u["name"] or "").strip() or OHNE_NAMEN) if u else (name or "System"), action,
         _als_text(vorher) if vorher is not None else None, _als_text(nachher) if nachher is not None else None,
         db.now()))


def aenderung(entity, entity_id, alt, neu, action="geaendert"):
    """Eintrag für eine Änderung – nur wenn sich wirklich etwas geändert hat. Liefert, ob."""
    vorher, nachher = unterschied(alt, neu)
    if not nachher:
        return False
    eintragen(entity, entity_id, action, vorher, nachher)
    return True


def _aufloesen(daten, namen):
    """Kontoverweise {"ref": …} im Eintrag durch {"name": …} ersetzen (namen: Zwischenspeicher je Lesevorgang)."""
    if not isinstance(daten, dict):
        return daten
    konto = daten.get("konto")
    if isinstance(konto, dict) and "ref" in konto:
        ref = konto["ref"]
        if ref not in namen:
            namen[ref] = konto_name(ref)
        daten = dict(daten, konto={"name": namen[ref]})
    return daten


def _json(row, namen=None):
    namen = {} if namen is None else namen
    return {"id": row["id"], "entity": row["entity"], "entity_id": row["entity_id"], "user_name": row["user_name"],
            "action": row["action"], "created_at": row["created_at"],
            "vorher": _aufloesen(json.loads(row["before_json"]), namen) if row["before_json"] else None,
            "nachher": _aufloesen(json.loads(row["after_json"]), namen) if row["after_json"] else None}


# Womit ein Objekt endet. Prüfungen und Durchgänge vergeben ihre Kennung nie zweimal (AUTOINCREMENT,
# models.py); Artikel, Ordner, Produkte, Kategorien, Formulare können nach dem Löschen eine Kennung
# wiederbekommen. Was vor der letzten Löschung unter derselben Kennung steht, gehört einem Vorgänger.
LOESCHUNG = {"inspection": ("geloescht", "verworfen", "reservierung_freigegeben")}


def lesen(paare, grenze=500, ohne=()):
    """Einträge zu mehreren (entity, id)-Paaren, neueste zuerst – je Paar nur die seit seiner letzten
    Löschung (siehe LOESCHUNG). ohne: Aktionen, die nicht mitkommen (z. B. rechte.FREIGABE_AKTIONEN für alle, die den
    Ordner nicht verwalten)."""
    if not paare:
        return []
    bedingung = "(" + " OR ".join("(entity = ? AND entity_id = ?)" for _ in paare) + ")"
    args = [x for p in paare for x in p]
    if ohne:
        bedingung += f" AND action NOT IN ({','.join('?' * len(ohne))})"
        args += list(ohne)
    ab = {}
    for e, eid in paare:
        aktionen = LOESCHUNG.get(e, ("geloescht",))
        r = db.query(f"SELECT MAX(id) AS m FROM mat_audit WHERE entity = ? AND entity_id = ? AND action IN "
                     f"({','.join('?' * len(aktionen))})", (e, eid, *aktionen), one=True)
        ab[(e, eid)] = r["m"] or 0
    rows = db.query(f"SELECT * FROM mat_audit WHERE {bedingung} ORDER BY id DESC LIMIT ?", (*args, grenze))
    namen = {}
    return [_json(r, namen) for r in rows if r["id"] > ab.get((r["entity"], r["entity_id"]), 0)]


# --- Kontoverweise ------------------------------------------------------------------------------------------
# Betroffene (wem eine Freigabe oder ein Artikel zugeordnet ist) stehen im Journal nur pseudonym: {"ref": users.mat_ref},
# eine Zufallskennung, die nirgends sonst gespeichert ist. Wird das Konto gelöscht, führt von ihr nichts mehr zur Person.
# Handelnde stehen weiter mit Namen in user_name (Nachweis).

def konto_ref(uid):
    """Der Kontoverweis fürs Journal: {"ref": mat_ref} – fehlt mat_ref (Konto nach Schritt 8 angelegt), wird es jetzt
    gesetzt. Ein Konto, das es nicht gibt, hat keinen Verweis (ref None)."""
    db.execute("UPDATE users SET mat_ref = ? WHERE id = ? AND (mat_ref IS NULL OR mat_ref = '')",
               (secrets.token_hex(16), uid))
    r = db.query("SELECT mat_ref FROM users WHERE id = ?", (uid,), one=True)
    return {"ref": r["mat_ref"] if r else None}


def konto_name(ref):
    """Der Name hinter einem Kontoverweis – „(gelöschtes Konto)“, wenn es ihn nicht mehr gibt, „(ohne Namen)“ bei
    leerem Namen. Kein Rückfall auf die E-Mail."""
    r = db.query("SELECT name FROM users WHERE mat_ref = ?", (ref,), one=True) if ref else None
    if not r:
        return "(gelöschtes Konto)"
    return (r["name"] or "").strip() or "(ohne Namen)"


def konto_namen(refs):
    """Wie konto_name, für viele Verweise mit EINER Abfrage (Listen wie der Verlauf der Freigaben): {ref: Name}."""
    refs = sorted({r for r in refs if r})
    gefunden = {r["mat_ref"]: (r["name"] or "").strip() or "(ohne Namen)" for r in db.query(
        "SELECT mat_ref, name FROM users WHERE mat_ref IN (SELECT value FROM json_each(?))", (json.dumps(refs),))} \
        if refs else {}
    return {r: gefunden.get(r, "(gelöschtes Konto)") for r in refs}


def fuer_produkt(pid, user=None, meldungen=True):
    """Journal eines Produkts: seine Stammdaten, seine Dokumente, seine spezifischen Formulare und die
    Meldungen, über die es in den Katalog kam – diese nur, soweit das Konto die Meldung sehen darf
    (rechte.darf_meldung: Melder, Material-Verwaltung, wer den Ordner der Meldung sieht). meldungen=False lässt
    sie ganz weg."""
    paare = [("product", pid)]
    paare += [("document", r["id"]) for r in db.query("SELECT id FROM mat_product_document WHERE product_id = ?", (pid,))]
    paare += [("form", r["id"]) for r in db.query("SELECT id FROM mat_form WHERE product_id = ?", (pid,))]
    if meldungen:
        from .rechte import darf_meldung
        paare += [("request", r["id"]) for r in db.query(
            "SELECT id, created_by, folder_id FROM mat_product_request WHERE product_id = ?", (pid,))
            if darf_meldung(r, user)]
    return lesen(paare)


# Einträge am Artikel, die das Produkt wechseln (Produkt im Dialog „Bearbeiten“ bis zur ersten Prüfung, per Antrag danach).
PRODUKTWECHSEL = ("produkt_geaendert", "antrag_bestaetigt")


def produkt_zeitraeume(item):
    """Welches Produkt der Artikel wann hatte – aus seinem eigenen Journal (Kennungen steigen streng mit der Zeit):
    [{product_id, ab, bis, ab_zeit, bis_zeit}] in zeitlicher Folge; ab/bis sind die Kennungen der Wechsel-Einträge
    (None: seit dem Anlegen bzw. bis heute), *_zeit ihre Zeitpunkte. Ohne Wechsel ein Zeitraum mit dem heutigen Produkt;
    passt das Journal nicht zum heutigen Produkt (ein Altbestand ohne Wechsel-Eintrag), ebenso (Prüfung der Anträge,
    Ablauf 1: nach einem Produktwechsel zeigten Journal und Lebenslauf die Geschichte des falschen Produkts)."""
    ab_loesch = db.query("SELECT MAX(id) AS m FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                         "AND action = 'geloescht'", (item["id"],), one=True)["m"] or 0
    rows = db.query(f"SELECT id, action, created_at, before_json, after_json FROM mat_audit WHERE entity = 'item' "
                    f"AND entity_id = ? AND id > ? AND action IN ('angelegt', {', '.join('?' * len(PRODUKTWECHSEL))}) "
                    f"ORDER BY id", (item["id"], ab_loesch, *PRODUKTWECHSEL))
    out, pid, ab, ab_zeit = [], None, None, None
    for r in rows:
        vorher = json.loads(r["before_json"]) if r["before_json"] else {}
        nachher = json.loads(r["after_json"]) if r["after_json"] else {}
        if r["action"] == "angelegt":
            pid = nachher.get("product_id", pid) if pid is None else pid
            continue
        neu = nachher.get("product_id")
        if neu is None or neu == vorher.get("product_id"):
            continue
        alt = pid if pid is not None else vorher.get("product_id")
        if alt is not None:
            out.append({"product_id": alt, "ab": ab, "bis": r["id"], "ab_zeit": ab_zeit, "bis_zeit": r["created_at"]})
        pid, ab, ab_zeit = neu, r["id"], r["created_at"]
    if pid is not None and pid != item["product_id"]:
        out, ab, ab_zeit = [], None, None
    out.append({"product_id": item["product_id"], "ab": ab, "bis": None, "ab_zeit": ab_zeit, "bis_zeit": None})
    return out


def im_zeitraum(e, z):
    return (z["ab"] is None or e["id"] > z["ab"]) and (z["bis"] is None or e["id"] < z["bis"])


def fuer_artikel(item):
    """Lebenslauf-Journal eines Artikels: seine eigenen Einträge und die seiner Produkte – je Produkt nur aus der Zeit,
    in der der Artikel es hatte (produkt_zeitraeume; das erste mit seiner Geschichte davor, wie bisher), ohne die
    Meldungen, über die das Produkt in den Katalog kam (die gehören zum Katalog, nicht zum Artikel, und kämen oft aus
    einem fremden Bereich)."""
    eintraege = lesen([("item", item["id"])])
    for z in produkt_zeitraeume(item):
        eintraege += [e for e in fuer_produkt(z["product_id"], meldungen=False) if im_zeitraum(e, z)]
    eintraege.sort(key=lambda e: e["id"], reverse=True)
    return eintraege
