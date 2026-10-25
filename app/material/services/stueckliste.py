"""Bestandteil-Liste eines Produkts (Schritt 25, Wunsch vom 25.10.2026; seit dem Rückbau der Set-Funktion, Schritt 26, die
einzige Form der Tabelle mat_product_component): Ein Produkt kann eine Liste „Bestandteile“ haben – nur Text, je Position
Bezeichnung und Anzahl, ohne eigenes Produkt und ohne eigenen Artikel; leer heißt keine Liste. Ein Herstellerset steht so
als ein Produkt im Katalog; zusammengestellte Sätze (Rucksack, Kiste) sind ein Ordner der Art „Set“ im Bestand.

Regeln, wie sie hier umgesetzt sind (die Trigger aus Schritt 26 fangen, was an ihnen vorbeiginge):
  - Je Position: Bezeichnung (Pflicht, eine Zeile, höchstens 120 Zeichen, je Liste eindeutig ohne Groß und klein) und
    Anzahl 1–20 (Vorgabe 1); höchstens 30 Positionen. Die stillgelegten Spalten einzeln, component_product_id und
    austausch schreibt der Dienst mit ihren Vorgaben (0, NULL, „nicht belegt“) und liest sie nicht mehr.
  - Die Liste wird als Ganzes ersetzt (Oberfläche wie Katalogimport) – unveränderte Positionen (gleiche Bezeichnung)
    behalten dabei ihre Kennung, denn an ihr hängen die Seriennummern der Bestandteile am Artikel (teilnummern.py) – und
    steht mit einem Eintrag „bestandteile“ im Journal des Produkts.
  - Jede Prüfung eines Artikels dieses Produkts fragt je Position „vorhanden“ ab (pruefzeilen) – was fehlt, ist ein
    Mangel (Entscheidung F1 a).

Pflegen darf die Material-Verwaltung (Routen an katalog_required); lesen jeder mit Modulzugang (produkt_json)."""
import json

from ... import db
from ..models import BESTANDTEIL_ANZAHL_MAX, BEZEICHNUNG_MAX, STUECKLISTE_POSITIONEN_MAX
from . import Abgelehnt, ganzzahl, journal, katalog, text, wahr

NUR_TEXT = ("Eine Bestandteil-Liste ist nur Text (Bezeichnung und Anzahl) – „einzeln“, ein Produkt und „austausch“ gibt es "
            "nicht mehr.")
DOPPELT = "„{name}“ steht schon in Position {n} – die Anzahl anpassen."
LISTE_MAX = f"Höchstens {STUECKLISTE_POSITIONEN_MAX} Positionen je Liste."
# Gruppe der Prüfzeilen „… vorhanden“ (wie BESTANDTEIL_GRUPPE in material.js) und ihre Position hinter den
# Formularpunkten. SET_GRUPPE: die Gruppe der Bestandteil-Zeilen in Prüfungen früherer Set-Artikel (bis Schritt 26) –
# bleibt, damit alte Prüfungen ihre Zeilen „vorhanden/fehlt“ zeigen.
BESTANDTEIL_GRUPPE = "Bestandteile"
SET_GRUPPE = "Bestandteile des Sets"
BESTANDTEIL_POS = 9000


def zeilen(pid):
    """Die Positionen der Bestandteil-Liste in ihrer Reihenfolge (Tabellenzeilen)."""
    return db.query("SELECT * FROM mat_product_component WHERE set_product_id = ? ORDER BY position, id", (pid,))


def kurz_form(r):
    """Eine Position der Bestandteil-Liste in Journal und Antworten: {bezeichnung, anzahl}."""
    return {"bezeichnung": r["bezeichnung"], "anzahl": r["anzahl"]}


def zeile_json(r):
    return {"id": r["id"], "position": r["position"], **kurz_form(r)}


def produkt_json_ergaenzen(out, p, voll=False):
    """Bestandteil-Liste an katalog.produkt_json (nur voll) samt den Grenzen für den Produktdialog."""
    if not voll:
        return out
    out["bestandteile"] = [zeile_json(r) for r in zeilen(p["id"])]
    out["stueckliste_grenzen"] = {"positionen": STUECKLISTE_POSITIONEN_MAX, "anzahl": BESTANDTEIL_ANZAHL_MAX,
                                  "bezeichnung": BEZEICHNUNG_MAX}
    return out


def _schluessel(bezeichnung):
    """Bezeichnung zum Vergleich: ohne Groß und klein, Leerraum zusammengefasst."""
    return " ".join(str(bezeichnung or "").split()).casefold()


def eintraege_lesen(liste):
    """Die Positionen aus einer Anfrage (oder einer Katalogdatei) nach den Regeln oben – noch ohne zu schreiben: je
    Position ein Objekt mit Bezeichnung und Anzahl; „einzeln“ (wahr), ein Produkt und ein „austausch“ außer „nicht
    belegt“ weist es ab (400 „Position n: …“). Leer heißt keine Liste. Liefert die Form der Tabelle (ohne Kennung),
    Reihenfolge = Position."""
    if not isinstance(liste, list):
        raise Abgelehnt("„bestandteile“ muss eine Liste sein.")
    if len(liste) > STUECKLISTE_POSITIONEN_MAX:
        raise Abgelehnt(LISTE_MAX)
    out, gesehen = [], {}
    for n, e in enumerate(liste, start=1):
        if not isinstance(e, dict):
            raise Abgelehnt(f"Position {n}: kein Objekt.")
        try:
            if wahr(e, "einzeln", "einzeln geführt") or e.get("produkt") is not None \
                    or e.get("produkt_id") not in (None, "") \
                    or (e.get("austausch") or "nicht_belegt") != "nicht_belegt":
                raise Abgelehnt(NUR_TEXT)
            bezeichnung = text(e, "bezeichnung", "Bezeichnung", BEZEICHNUNG_MAX)
            if not bezeichnung:
                raise Abgelehnt("Bitte eine Bezeichnung angeben.")
            schluessel = _schluessel(bezeichnung)
            if schluessel in gesehen:
                raise Abgelehnt(DOPPELT.format(name=bezeichnung, n=gesehen[schluessel]))
            gesehen[schluessel] = n
            anzahl = ganzzahl(e.get("anzahl", 1), "Anzahl", 1, BESTANDTEIL_ANZAHL_MAX, leer_erlaubt=False)
        except Abgelehnt as exc:
            raise Abgelehnt(f"Position {n}: {exc}", exc.code)
        out.append({"bezeichnung": bezeichnung, "anzahl": anzahl, "position": n})
    return out


def anfrage_lesen(d):
    """POST /produkte und „aus Meldung anlegen“: „bestandteile“ ist die Bestandteil-Liste (darf fehlen oder leer sein).
    Liefert die rohe Liste oder None – geprüft wird sie in katalog.produkt_anlegen (eintraege_lesen). Frühere Schlüssel
    der Set-Funktion („is_set“) werden übergangen wie jeder unbekannte."""
    liste = d.get("bestandteile")
    if liste is not None and not isinstance(liste, list):
        raise Abgelehnt("„bestandteile“ muss eine Liste sein.")
    return liste


def _vergleich(r):
    return (r["bezeichnung"], r["anzahl"])


def _ersetzen(p, neu, grund=None):
    """Die Bestandteil-Liste von p durch neu (eintraege_lesen) ersetzen – nur, wenn sie sich ändert (in der Transaktion
    des Aufrufers). Positionen mit gleicher Bezeichnung (_schluessel) bleiben dieselbe Zeile – Bezeichnung, Anzahl und
    Reihenfolge werden nachgezogen –, damit die Seriennummern der Bestandteile an den Artikeln bleiben (teilnummern.py);
    wegfallende Positionen gehen samt ihren Nummern (ON DELETE CASCADE), Stück über einer gesunkenen Anzahl ebenso – je
    betroffenem Artikel vorher ein Eintrag im Journal (teilnummern.entfallen). Neue Positionen werden VOR dem Löschen der
    wegfallenden geschrieben: Die Kennung (INTEGER PRIMARY KEY ohne AUTOINCREMENT) ginge sonst an die neue Position über,
    und eine Nummer aus einem offenen Prüfentwurf oder Antrag landete am anderen Bestandteil (Prüfung Ablauf, B1). Über
    mehrere Änderungen hinweg kann eine Kennung trotzdem wiederkommen; Prüfung und Antrag vergleichen deshalb auch die
    Bezeichnung. Journal „bestandteile“ am Produkt (vorher, nachher). Liefert, ob sich etwas geändert hat."""
    from . import teilnummern
    alt = zeilen(p["id"])
    if [_vergleich(r) for r in alt] == [_vergleich(r) for r in neu]:
        return False
    bleibt = {_schluessel(r["bezeichnung"]): r for r in alt}
    behalten = set()
    for r in neu:
        z = bleibt.get(_schluessel(r["bezeichnung"]))
        if z:
            behalten.add(z["id"])
    teilnummern.entfallen(p["id"], [r for r in alt if r["id"] not in behalten],
                          {bleibt[_schluessel(r["bezeichnung"])]["id"]: r["anzahl"] for r in neu
                           if _schluessel(r["bezeichnung"]) in bleibt})
    for r in neu:
        z = bleibt.get(_schluessel(r["bezeichnung"]))
        if z:
            db.execute("UPDATE mat_product_component SET bezeichnung = ?, anzahl = ?, position = ? WHERE id = ?",
                       (r["bezeichnung"], r["anzahl"], r["position"], z["id"]))
        else:
            db.execute("INSERT INTO mat_product_component (set_product_id, component_product_id, bezeichnung, anzahl, "
                       "einzeln, austausch, position) VALUES (?, NULL, ?, ?, 0, 'nicht_belegt', ?)",
                       (p["id"], r["bezeichnung"], r["anzahl"], r["position"]))
    for r in alt:
        if r["id"] not in behalten:
            db.execute("DELETE FROM mat_product_component WHERE id = ?", (r["id"],))
    # Erst die Anzahl, dann die Stück darüber: Solange das Stück zur Position gehört, schützt der Trigger seine Nummer.
    for r in neu:
        z = bleibt.get(_schluessel(r["bezeichnung"]))
        if z and r["anzahl"] < z["anzahl"]:
            db.execute("DELETE FROM mat_item_component_serial WHERE component_id = ? AND stueck > ?", (z["id"], r["anzahl"]))
    nachher = {"bestandteile": [kurz_form(r) for r in neu]}
    if grund:
        nachher["grund"] = grund
    journal.eintragen("product", p["id"], "bestandteile", {"bestandteile": [kurz_form(r) for r in alt]}, nachher)
    db.execute("UPDATE mat_product SET updated_at = ? WHERE id = ?", (db.now(), p["id"]))
    return True


def ersetzen(pid, liste, grund=None):
    """PUT /produkte/<pid>/bestandteile bzw. Katalogimport: die Bestandteil-Liste als Ganzes ersetzen (unter der
    Schreibsperre; in einer äußeren Transaktion läuft es flach mit); [] entfernt sie. Liefert, ob sie sich geändert hat."""
    with db.transaction(sofort=True):
        p = katalog.produkt(pid)
        return _ersetzen(p, eintraege_lesen(liste), grund)


# --- Bestandteil-Liste an Artikel, Meine PSA, Lebenslauf und Prüfung -----------------------------------------------------

def kurzlisten(pids):
    """{Produkt: [{id, bezeichnung, anzahl}]} – die Bestandteil-Listen der Produkte in einer Abfrage (Meine PSA).
    Produkte ohne Liste fehlen."""
    pids = list(dict.fromkeys(p for p in pids if p))
    if not pids:
        return {}
    out = {}
    for r in db.query(f"SELECT * FROM mat_product_component WHERE set_product_id IN ({','.join('?' * len(pids))}) "
                      f"ORDER BY set_product_id, position, id", pids):
        out.setdefault(r["set_product_id"], []).append({"id": r["id"], **kurz_form(r)})
    return out


def kurzliste(pid):
    """Die Bestandteil-Liste eines Produkts als [{id, bezeichnung, anzahl}] – leer ohne Liste."""
    return kurzlisten([pid]).get(pid, [])


def zeile_text(bezeichnung, anzahl):
    """Der Text der Prüfzeile: „Tasche vorhanden“, bei mehr als einem Stück „Tasche (2×) vorhanden“."""
    return bezeichnung + (f" ({anzahl}×)" if anzahl > 1 else "") + " vorhanden"


def pruefzeilen(pruefung_id, item):
    """Beim Start einer Prüfung (jede Prüfart, einzeln oder im Durchgang): je Position der Bestandteil-Liste des Produkts
    eine Ja/Nein-Zeile „… vorhanden“ – Pflicht, Soll „ja“, nicht kritisch, vorbelegt „ja“, ohne Formularpunkt, Gruppe
    BESTANDTEIL_GRUPPE hinter den Formularpunkten; einmal je Prüfung. Was fehlt, ist ein Mangel wie jeder andere (F1 a).
    Dazu je Zeile die Position und die Seriennummern ihrer Stück am Artikel (teilnummern) – „alt“ wie heute, „neu“
    trägt der Prüfer ein."""
    from . import teilnummern
    if db.query("SELECT 1 FROM mat_inspection_result WHERE inspection_id = ? AND checklist_item_id IS NULL "
                "AND group_name = ? LIMIT 1", (pruefung_id, BESTANDTEIL_GRUPPE), one=True):
        return
    nummern = teilnummern.nummern(item["id"])
    for n, z in enumerate(kurzliste(item["product_id"])):
        serien = [{"alt": nummern.get((z["id"], st), ""), "neu": None} for st in range(1, z["anzahl"] + 1)]
        db.execute("INSERT INTO mat_inspection_result (inspection_id, checklist_item_id, position, group_name, "
                   "checklist_text, editor, mandatory, expected_value, is_critical, finding, value, component_id, "
                   "component_serials) VALUES (?, NULL, ?, ?, ?, 'yesno', 1, 'ja', 0, 'ok', 'ja', ?, ?)",
                   (pruefung_id, BESTANDTEIL_POS + n, BESTANDTEIL_GRUPPE, zeile_text(z["bezeichnung"], z["anzahl"]),
                    z["id"], json.dumps(serien, ensure_ascii=False)))
