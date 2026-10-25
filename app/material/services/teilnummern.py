"""Seriennummern der Bestandteile am Artikel (Schritt 25, Zusatz zum Wunsch vom 25.10.2026 – S1 bis S3).

Hat das Produkt eines Artikels eine Bestandteil-Liste (stueckliste.py), trägt der
Artikel je Position und Stück FREIWILLIG eine Seriennummer (mat_item_component_serial; leer heißt keine Zeile – ein
Beutel hat keine). Regeln, wie sie hier umgesetzt sind (die Trigger aus Schritt 25 fangen, was an ihnen vorbeiginge):
  - Bis zur ersten abgeschlossenen Prüfung direkt: beim Anlegen und im Dialog „Bearbeiten“ (Materialwart, wie die
    übrigen Stammdaten vor der Prüfung – bestand.anlegen, bestand.artikel_aendern).
  - Danach trägt der PRÜFER eine neue oder fehlende Nummer in der Prüfung ein (Zeile „… vorhanden“, pruefung.punkt_setzen;
    beim Festschreiben übernommen, das Protokoll hält alt → neu fest – uebernehmen) – außerhalb einer Prüfung nur per
    Änderungsantrag (Feld component_serial, antrag.py; Freigabe wie die übrigen Stammdaten).
  - Grenzen wie die Seriennummer des Artikels: eine Zeile, höchstens 80 Zeichen. Eindeutig muss sie nicht sein.
  - Ändert die Material-Verwaltung die Bestandteil-Liste, bleiben die Nummern an unveränderten Positionen (gleiche
    Bezeichnung); wegfallende Positionen und Stück über einer gesunkenen Anzahl verlieren ihre Nummer – sie steht danach
    nur noch in Journal und Protokollen (entfallen). Wechselt der Artikel das Produkt, ebenso (aufraeumen).
  - Die Suche findet den Artikel auch über die Nummer eines Bestandteils (search.artikel); Rückrufe treffen
    Bestandteile nicht – sie sind kein Katalogprodukt.

Journal des Artikels: „bestandteil_nummern“ mit vorher/nachher als Liste {bestandteil, seriennummer} (bestandteil:
„Tasche“ bzw. „Tasche (Stück 2 von 3)“), dazu die Prüfung oder der Grund."""
import re

from ... import db
from ..models import SERIE_MAX
from . import Abgelehnt, ganzzahl, journal, kennung, text

FEST = ("Seit der ersten Prüfung stehen die Seriennummern der Bestandteile fest – eine neue Nummer trägt der Prüfer in der "
        "Prüfung ein (Zeile „… vorhanden“), sonst per Änderungsantrag.")
UNBEKANNT = "Diese Position steht nicht in der Bestandteil-Liste des Produkts."
GRUND_LISTE = "Bestandteil-Liste des Produkts geändert"
GRUND_PRODUKT = "Produkt gewechselt"


def stueck_text(bezeichnung, stueck, anzahl):
    """Die Beschriftung eines Stücks: „Tasche“, bei mehr als einem Stück „Tasche (Stück 2 von 3)“ – endet die Bezeichnung
    selbst mit einer Klammer, „Bestandteil A (rot) – Stück 2 von 3“ (keine doppelte Klammer; Prüfung Browser)."""
    if anzahl <= 1:
        return bezeichnung
    return f"{bezeichnung} – Stück {stueck} von {anzahl}" if bezeichnung.rstrip().endswith(")") \
        else f"{bezeichnung} (Stück {stueck} von {anzahl})"


def gleiche_position(beschriftung, z, stueck):
    """Nennt die Beschriftung eines Stücks (stueck_text von damals – etwa component_label eines Antrags) noch dieses Stück
    der Position z (kurzliste)? Gleich heißt: dieselbe Bezeichnung ohne Groß und klein und Leerraum, mit oder ohne
    „(Stück n von m)“ – die Anzahl darf sich geändert haben, das Stück muss es noch geben. Die Kennung allein reicht
    nicht: Eine entfallene Position kann sie an eine neue abgeben (Prüfung Ablauf, B1)."""
    from .stueckliste import _schluessel
    if not z or stueck > z["anzahl"]:
        return False
    b, k = _schluessel(z["bezeichnung"]), _schluessel(beschriftung)
    return k == b or re.fullmatch(re.escape(b) + rf" (\(stück {stueck} von \d+\)|– stück {stueck} von \d+)", k) is not None


def nummern(item_id):
    """{(Position, Stück): Seriennummer} – alle Zeilen des Artikels (auch die einer weggefallenen Position gibt es nicht:
    sie gehen mit ihr)."""
    return {(r["component_id"], r["stueck"]): r["serial_no"] for r in db.query(
        "SELECT component_id, stueck, serial_no FROM mat_item_component_serial WHERE item_id = ?", (item_id,))}


def _liste(positionen, werte):
    return [{"id": z["id"], "bezeichnung": z["bezeichnung"], "anzahl": z["anzahl"],
             "nummern": [werte.get((z["id"], st), "") for st in range(1, z["anzahl"] + 1)]} for z in positionen]


def liste_json(item):
    """Die Bestandteil-Liste des Produkts mit den Nummern dieses Artikels: [{id, bezeichnung, anzahl, nummern: [Text je
    Stück, leer ohne]}] – leer ohne Liste."""
    from . import stueckliste
    return _liste(stueckliste.kurzliste(item["product_id"]), nummern(item["id"]))


def listen_json(items):
    """liste_json für viele Artikel in zwei Abfragen (Meine PSA): {Artikel: Liste}."""
    from . import stueckliste
    listen = stueckliste.kurzlisten([i["product_id"] for i in items])
    ids = [i["id"] for i in items if listen.get(i["product_id"])]
    werte = {}
    if ids:
        for r in db.query(f"SELECT item_id, component_id, stueck, serial_no FROM mat_item_component_serial "
                          f"WHERE item_id IN ({','.join('?' * len(ids))})", ids):
            werte.setdefault(r["item_id"], {})[(r["component_id"], r["stueck"])] = r["serial_no"]
    return {i["id"]: _liste(listen.get(i["product_id"], []), werte.get(i["id"], {})) for i in items}


def lesen(roh, product_id):
    """„bestandteil_nummern“ aus einer Anfrage: [{bestandteil_id, stueck, seriennummer}] – je Position der
    Bestandteil-Liste des Produkts und Stück (1 bis Anzahl) höchstens einmal; leer heißt keine Nummer. Liefert
    {(Position, Stück): Text}."""
    from . import stueckliste
    if roh is None:
        return {}
    if not isinstance(roh, list):
        raise Abgelehnt("„bestandteil_nummern“ muss eine Liste sein.")
    positionen = {z["id"]: z for z in stueckliste.kurzliste(product_id)}
    out = {}
    for n, e in enumerate(roh, start=1):
        if not isinstance(e, dict):
            raise Abgelehnt(f"Seriennummer {n}: kein Objekt.")
        cid = kennung(e.get("bestandteil_id"), "Bestandteil")
        z = positionen.get(cid)
        if not z:
            raise Abgelehnt(f"Seriennummer {n}: {UNBEKANNT}")
        st = ganzzahl(e.get("stueck", 1), "Stück", 1, z["anzahl"], leer_erlaubt=False)
        wert = text(e, "seriennummer", f"Seriennummer {stueck_text(z['bezeichnung'], st, z['anzahl'])}", SERIE_MAX)
        if (cid, st) in out:
            raise Abgelehnt(f"Seriennummer {n}: {stueck_text(z['bezeichnung'], st, z['anzahl'])} steht doppelt da.")
        out[(cid, st)] = wert
    return out


def aenderungen(item_id, werte):
    """Was sich gegenüber dem Artikel ändert: [(Position, Stück, alt, neu)] – leer heißt keine Nummer (""), gleiche
    Schreibweise ist keine Änderung."""
    jetzt = nummern(item_id)
    return [(cid, st, jetzt.get((cid, st), ""), neu) for (cid, st), neu in sorted(werte.items())
            if jetzt.get((cid, st), "") != neu]


def _beschriftungen(product_id):
    from . import stueckliste
    return {z["id"]: z for z in stueckliste.kurzliste(product_id)}


def journal_form(positionen, cid, st, wert):
    z = positionen.get(cid)
    name = stueck_text(z["bezeichnung"], st, z["anzahl"]) if z else f"Position Nr. {cid}, Stück {st}"
    return {"bestandteil": name, "seriennummer": wert or ""}


def schreiben(item, liste, zusatz=None, journal_an=True):
    """In der Transaktion des Aufrufers: die Änderungen (aenderungen) an den Artikel – einfügen, ändern oder (leer)
    entfernen; ein Eintrag „bestandteil_nummern“ im Journal (zusatz: etwa die Prüfung oder der Antrag). Die Trigger
    weisen nach der ersten Prüfung alles ab, was keine Prüfung und kein bestätigter Antrag deckt. Liefert (vorher,
    nachher) in Journalform."""
    if not liste:
        return [], []
    positionen = _beschriftungen(item["product_id"])
    ts = db.now()
    vorher, nachher = [], []
    for cid, st, alt, neu in liste:
        if neu and alt:
            db.execute("UPDATE mat_item_component_serial SET serial_no = ?, updated_at = ? WHERE item_id = ? "
                       "AND component_id = ? AND stueck = ?", (neu, ts, item["id"], cid, st))
        elif neu:
            db.execute("INSERT INTO mat_item_component_serial (item_id, component_id, stueck, serial_no, updated_at) "
                       "VALUES (?,?,?,?,?)", (item["id"], cid, st, neu, ts))
        else:
            db.execute("DELETE FROM mat_item_component_serial WHERE item_id = ? AND component_id = ? AND stueck = ?",
                       (item["id"], cid, st))
        vorher.append(journal_form(positionen, cid, st, alt))
        nachher.append(journal_form(positionen, cid, st, neu))
    if journal_an:
        journal.eintragen("item", item["id"], "bestandteil_nummern", {"bestandteil_nummern": vorher},
                          dict({"bestandteil_nummern": nachher}, **(zusatz or {})))
    return vorher, nachher


def entfallen(product_id, weg, neue_anzahl):
    """Vor dem Ersetzen einer Bestandteil-Liste (stueckliste._ersetzen): Je Artikel, dessen Nummern dabei wegfallen
    – an den Positionen weg (Zeilen) und an Stück über neue_anzahl {Position: Anzahl} –, ein Journaleintrag mit den
    Nummern vorher. Gelöscht wird danach in stueckliste._ersetzen (mit der Position bzw. nach dem Kürzen der Anzahl)."""
    positionen = _beschriftungen(product_id)
    bedingungen, args = [], []
    if weg:
        bedingungen.append(f"s.component_id IN ({','.join('?' * len(weg))})")
        args += [r["id"] for r in weg]
    for cid, anzahl in neue_anzahl.items():
        bedingungen.append("(s.component_id = ? AND s.stueck > ?)")
        args += [cid, anzahl]
    if not bedingungen:
        return
    rows = db.query(f"SELECT s.* FROM mat_item_component_serial s JOIN mat_item i ON i.id = s.item_id "
                    f"WHERE i.product_id = ? AND ({' OR '.join(bedingungen)}) ORDER BY s.item_id, s.component_id, s.stueck",
                    (product_id, *args))
    je = {}
    for r in rows:
        je.setdefault(r["item_id"], []).append(journal_form(positionen, r["component_id"], r["stueck"], r["serial_no"]))
    for iid, vorher in je.items():
        journal.eintragen("item", iid, "bestandteil_nummern", {"bestandteil_nummern": vorher},
                          {"bestandteil_nummern": [], "grund": GRUND_LISTE})


def aufraeumen(item, alt_product_id):
    """Nach einem Produktwechsel (in der Transaktion des Aufrufers): Nummern, deren Position nicht zum neuen Produkt
    gehört, gelten nicht mehr – sie gehen (der Trigger lässt es zu), das Journal behält sie."""
    rows = db.query("SELECT s.* FROM mat_item_component_serial s JOIN mat_product_component k ON k.id = s.component_id "
                    "WHERE s.item_id = ? AND k.set_product_id IS NOT ? ORDER BY s.component_id, s.stueck",
                    (item["id"], item["product_id"]))
    if not rows:
        return
    positionen = _beschriftungen(alt_product_id)
    vorher = [journal_form(positionen, r["component_id"], r["stueck"], r["serial_no"]) for r in rows]
    db.execute("DELETE FROM mat_item_component_serial WHERE id IN (" + ",".join("?" * len(rows)) + ")",
               [r["id"] for r in rows])
    journal.eintragen("item", item["id"], "bestandteil_nummern", {"bestandteil_nummern": vorher},
                      {"bestandteil_nummern": [], "grund": GRUND_PRODUKT})


def pdf_zeilen(item):
    """Für Lebenslauf: je Position „2 × Tasche“ und die Nummern ihrer Stück als Text (leer ohne)."""
    out = []
    for z in liste_json(item):
        mit = [(st, n) for st, n in enumerate(z["nummern"], start=1) if n]
        if z["anzahl"] == 1:
            nr = mit[0][1] if mit else ""
        else:
            nr = ", ".join(f"Stück {st}: {n}" for st, n in mit)
        out.append({"text": f"{z['anzahl']} × {z['bezeichnung']}", "nummern": nr})
    return out
