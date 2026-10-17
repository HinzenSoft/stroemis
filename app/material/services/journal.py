"""Änderungsjournal (mat_audit): wer hat wann was geändert – mit Vorher und Nachher je Feld.

Geschrieben wird in derselben Transaktion wie die Änderung selbst: Eine Änderung ohne Eintrag gibt
es damit nicht, ein Eintrag ohne Änderung auch nicht. Gelesen wird es am Produkt, am Artikel (dort
zusammen mit dem Journal seines Produkts) und an Ordnern. Die Tabelle ist per Trigger nur
fortschreibbar (models.py)."""
import json

from flask import g, has_request_context

from ... import db
from ...auth import current_user

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


def eintragen(entity, entity_id, action, vorher=None, nachher=None, name=None):
    """Einen Eintrag schreiben. name: Anzeigename, wenn niemand angemeldet ist (Import, Startlauf);
    ein Kommandozeilenlauf setzt ihn für alle Einträge über g.mat_akteur."""
    u = current_user() if has_request_context() else None
    if not u and not name:
        name = g.get("mat_akteur")
    db.execute(
        "INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, before_json, after_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (entity, entity_id, u["id"] if u else None,
         (u["name"] or u["email"]) if u else (name or "System"), action,
         json.dumps(_sauber(vorher), ensure_ascii=False, sort_keys=True, default=str) if vorher is not None else None,
         json.dumps(_sauber(nachher), ensure_ascii=False, sort_keys=True, default=str) if nachher is not None else None,
         db.now()))


def aenderung(entity, entity_id, alt, neu, action="geaendert"):
    """Eintrag für eine Änderung – nur wenn sich wirklich etwas geändert hat. Liefert, ob."""
    vorher, nachher = unterschied(alt, neu)
    if not nachher:
        return False
    eintragen(entity, entity_id, action, vorher, nachher)
    return True


def _json(row):
    return {"id": row["id"], "entity": row["entity"], "entity_id": row["entity_id"], "user_name": row["user_name"],
            "action": row["action"], "created_at": row["created_at"],
            "vorher": json.loads(row["before_json"]) if row["before_json"] else None,
            "nachher": json.loads(row["after_json"]) if row["after_json"] else None}


# Womit ein Objekt endet. Prüfungen und Durchgänge vergeben ihre Kennung nie zweimal (AUTOINCREMENT,
# models.py); Artikel, Ordner, Produkte, Kategorien, Formulare können nach dem Löschen eine Kennung
# wiederbekommen. Was vor der letzten Löschung unter derselben Kennung steht, gehört einem Vorgänger.
LOESCHUNG = {"inspection": ("geloescht", "verworfen", "reservierung_freigegeben")}


def lesen(paare, grenze=500):
    """Einträge zu mehreren (entity, id)-Paaren, neueste zuerst – je Paar nur die seit seiner letzten
    Löschung (siehe LOESCHUNG)."""
    if not paare:
        return []
    bedingung = " OR ".join("(entity = ? AND entity_id = ?)" for _ in paare)
    args = [x for p in paare for x in p]
    ab = {}
    for e, eid in paare:
        aktionen = LOESCHUNG.get(e, ("geloescht",))
        r = db.query(f"SELECT MAX(id) AS m FROM mat_audit WHERE entity = ? AND entity_id = ? AND action IN "
                     f"({','.join('?' * len(aktionen))})", (e, eid, *aktionen), one=True)
        ab[(e, eid)] = r["m"] or 0
    rows = db.query(f"SELECT * FROM mat_audit WHERE {bedingung} ORDER BY id DESC LIMIT ?", (*args, grenze))
    return [_json(r) for r in rows if r["id"] > ab.get((r["entity"], r["entity_id"]), 0)]


def fuer_produkt(pid):
    """Journal eines Produkts: seine Stammdaten, seine Dokumente und seine spezifischen Formulare."""
    paare = [("product", pid)]
    paare += [("document", r["id"]) for r in db.query("SELECT id FROM mat_product_document WHERE product_id = ?", (pid,))]
    paare += [("form", r["id"]) for r in db.query("SELECT id FROM mat_form WHERE product_id = ?", (pid,))]
    return lesen(paare)


def fuer_artikel(item):
    """Lebenslauf-Journal eines Artikels: seine eigenen Einträge und die seines Produkts."""
    paare = [("item", item["id"])]
    eintraege = lesen(paare) + fuer_produkt(item["product_id"])
    eintraege.sort(key=lambda e: e["id"], reverse=True)
    return eintraege
