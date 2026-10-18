"""Bremse und Protokoll der Blicke über den eigenen Bereich hinaus (Phase 2 · L1, Abschnitt 3.3).

Wer in einer Gliederung arbeitet, sieht nur ihren Bestand. Drei Wege zeigen trotzdem etwas aus fremden Gliederungen:
die globale Seriennummernsuche (Art „suche“), der Steckbrief nach einem QR-Scan („qr“) und die Meldung, dass es eine
Seriennummer bei diesem Produkt schon gibt („dublette“, bestand._serie_frei). Alle drei laufen durch dieselbe Bremse –
höchstens GRENZE in 15 Minuten je Konto, gezählt in login_attempts wie die Anmeldeversuche – und schreiben je
Anfrage eine Zeile in mat_global_search: Konto, Name, Art, Anfrage, Treffer.

Bewusst nicht in mat_audit: Das Journal ist unveränderlich, das Protokoll aber hat eine Frist. aufraeumen() löscht,
was älter als AUFBEWAHRUNG_TAGE ist – vor jeder neuen Zeile, beim Start der Anwendung, beim Lesen des Protokolls und
ab Lieferung 2 im Nachtlauf."""
import json
from datetime import datetime, timedelta, timezone

from ... import db
from ...auth import attempts_exceeded, note_attempt
from . import Abgelehnt, akteur

ARTEN = ("suche", "qr", "dublette")
GRENZE = 10                                   # je Konto in 15 Minuten (auth.ATTEMPT_WINDOW) – Suche, QR und Dublette
AUFBEWAHRUNG_TAGE = 365
PRO_SEITE = 50
ZU_VIELE = "Zu viele globale Suchen – bitte in einer Viertelstunde noch einmal."


def _bereich(uid):
    return f"mat-global:{uid}"


def bremse(uid):
    """Vor jeder globalen Abfrage: Ist die Grenze erreicht, 429 (Abgelehnt); sonst zählt dieser Versuch mit. Prüfen und
    Zählen unter einer Schreibsperre – zwei gleichzeitige Anfragen kämen sonst beide an der zehnten vorbei."""
    with db.transaction(sofort=True):
        if attempts_exceeded([_bereich(uid)], GRENZE):
            raise Abgelehnt(ZU_VIELE, 429)
        note_attempt(_bereich(uid))


def _grenze_zeit():
    return (datetime.now(timezone.utc) - timedelta(days=AUFBEWAHRUNG_TAGE)).replace(microsecond=0).isoformat()


def aufraeumen(conn=None):
    """Zeilen löschen, die älter als die Aufbewahrungsfrist sind. conn: die Verbindung des Startlaufs (Material-Init,
    nach der Migration); sonst die der Anfrage. Liefert die Zahl der gelöschten Zeilen."""
    if conn is not None:
        n = conn.execute("DELETE FROM mat_global_search WHERE created_at < ?", (_grenze_zeit(),)).rowcount
        conn.commit()
        return n
    return db.execute_zeilen("DELETE FROM mat_global_search WHERE created_at < ?", (_grenze_zeit(),))


def eintragen(art, anfrage, item_ids):
    """Eine Zeile fürs Protokoll – mit Namen dessen, der fragt, der Anfrage (Normalform; bei „qr“ die Inventarnummer)
    und den Kennungen der Treffer. Liefert die Kennung der Zeile."""
    if art not in ARTEN:
        raise ValueError(art)
    ids = [int(i) for i in item_ids]
    uid, name = akteur()
    with db.transaction():
        aufraeumen()
        return db.execute("INSERT INTO mat_global_search (user_id, user_name, art, anfrage, treffer, item_ids, created_at) "
                          "VALUES (?,?,?,?,?,?,?)", (uid, name, art, anfrage, len(ids), json.dumps(ids), db.now()))


def liste(seite=1):
    """Das Protokoll für die Verwaltung, neueste zuerst, je Seite PRO_SEITE Zeilen – mit den Gliederungen der Treffer
    (soweit es die Artikel noch gibt)."""
    from .bestand import gliederung_von, heimat
    aufraeumen()
    seite = max(1, int(seite or 1))
    gesamt = db.query("SELECT COUNT(*) AS n FROM mat_global_search", one=True)["n"]
    rows = db.query("SELECT * FROM mat_global_search ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                    (PRO_SEITE, (seite - 1) * PRO_SEITE))
    artikel, gliederungen = {}, {}
    ids = sorted({i for r in rows for i in json.loads(r["item_ids"] or "[]")})
    if ids:
        for i in db.query(f"SELECT * FROM mat_item WHERE id IN ({','.join('?' * len(ids))})", ids):
            artikel[i["id"]] = i
    out = []
    for r in rows:
        namen = []
        for iid in json.loads(r["item_ids"] or "[]"):
            if iid not in artikel:
                continue
            h = heimat(artikel[iid])
            if h not in gliederungen:
                gl = gliederung_von(h)
                gliederungen[h] = gl["name"] if gl else ""
            if gliederungen[h] and gliederungen[h] not in namen:
                namen.append(gliederungen[h])
        out.append({"id": r["id"], "zeit": r["created_at"], "name": r["user_name"], "art": r["art"],
                    "anfrage": r["anfrage"], "treffer": r["treffer"], "gliederungen": namen})
    return {"eintraege": out, "gesamt": gesamt, "seite": seite, "pro_seite": PRO_SEITE}
