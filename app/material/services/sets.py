"""Hersteller-Sets im Bestand (Phase 4 · Lieferung 2, Entwurf C, F, H, I): Set-Artikel mit Teil-Artikeln.

Ein Set-Artikel ist ein Artikel eines Produkts mit dem Häkchen „Hersteller-Set“ (stueckliste.py) – das tragende
PSA-Produkt (Kong-Etikett, Petzl-Einzelnummer; ein Kit ohne eigene Kennzeichnung bekommt eine STR-Nummer). Jedes Stück
eines einzeln geführten Bestandteils ist ein eigener Artikel darunter, ein Teil (mat_item.parent_item_id, eine Ebene) –
mit Inventarnummer, QR und Etikett wie jeder Artikel. Beim Anlegen kommt die Stückliste als Kopie an das Set
(mat_item_set_slot): Vollständigkeit und Bestandteile lesen daraus, eine spätere Katalogänderung färbt kein Set um.

Regeln, wie sie hier umgesetzt sind:
  - Teile liegen, sperren und gehören wie ihr Set: folder_id, origin_folder_id, „frei oder nicht“ und assigned_user_id
    sind an Set und Teilen gleich – alle Rechte- und Filterwege lesen die Zeile des Teils selbst. Das hält NUR der
    Dienst, nicht die Datenbank (Kreuzzeilen-Trigger brächen Ordner- und Kontolöschen, Kritik S1/A8): set_lage ändert
    Set und Teile in EINER Anweisung, set_stimmig prüft am Ende jeder Transaktion, die ein Set berührt (Abweichung →
    Ausnahme, Rollback). Wege, die Zeilen einzeln schreiben (_systemordner_nachziehen, Ordner und Konto löschen), lassen
    Set und Teile gleich, weil sie für beide dasselbe tun – set_stimmig prüft danach. Beim Start prüft beim_start alle
    Sets (nur Log, wie die Fremdschlüssel).
  - Weichen im Dienst (Entwurf C, S9): Verschieben, Zuordnen, Sammelzuordnung, Produktwechsel und Aussondern am Teil
    → 409 mit Hinweis auf das Set (teil_weiche). Ein Set verschieben oder zuordnen nimmt die Teile mit (set_lage). Ein
    Set löschen geht nur ganz und nur ungeprüft (bestand.artikel_loeschen); ein Teil ohne Prüfung, Mangel und
    Durchgangszeile einzeln (setaustausch.teil_loeschen – das Set ist danach unvollständig und gesperrt).
  - Sperr-Kaskade (Entwurf D, Paket K2): Jede eigene Sperre an Set-Artikel oder Teil (Prüfer-Sperre, Ergebnis
    „instandsetzen“, Mangelmeldung, Verlust) setzt dort lock_cause „eigen“ und sperrt alle anderen mit „set“ – alle nach
    „Gesperrt“ der Gliederung, Herkunft = Heimat des Sets (sperren, eine Anweisung über set_lage). Eine eigene Sperre
    geht auch an einem schon mitgesperrten Teil. Unvollständigkeit (Teil entnommen, gelöscht, ausgesondert) und ein
    getauschtes oder eingesetztes Teil sperren das Set ebenso (Ursache „set“ am Set-Artikel, Anlass im Grund und im
    Journal als set_grund). Was im Freigabe-Lauf zu prüfen ist, steht in set_lock_origin (am Set) und set_pruefen (je
    Teil). Eine Freiprüfung im gesperrten Set setzt nur „eigen“ → „set“ (eigen_aufheben); frei wird das Set allein beim
    Festschreiben der Set-Artikel-Prüfung eines Set-Laufs (setlauf.py, freigeben). Mitsperren und Mitfreigeben schreiben
    eigene Journal-Aktionen („set_gesperrt“, „set_frei“) mit dem Handelnden „System“ – so zählt der Jahresbericht eine
    Set-Sperre einmal, und an Set und übrigen Teilen steht kein Meldername.
  - Teil entnehmen, tauschen, einsetzen und löschen, Set aussondern: setaustausch.py; Set prüfen: setlauf.py.
  - Set-Status = schlechtester aus Set-Artikel und aktuellen Teilen (status.SET_RANG, Rangfolge wie status.status()),
    Set-Fälligkeit = früheste nächste Prüfung, Set-Lebensende = frühestes Lebensende – je mit dem auslösenden Artikel.
    Listen (Ordner, Fällige, Suche) zeigen die Set-Zeile mit diesen Werten und filtern und sortieren nach ihnen
    (gruppen_status_sql); Teile stehen auf der Set-Seite und in der Suche („teil_von“). Zählungen in Baum, Übersicht,
    Bericht und Export bleiben je Artikel (Teile zählen mit).
  - Abfragen, die Set und Teil verbinden, filtern beide Zeilen mit rechte.artikel_filter (H, S17).

Rechte prüfen die Routen wie für jeden Artikel (requires_folder an der Heimat); die Teile haben dieselbe Heimat."""
import logging

from flask import g, has_request_context

from ... import db
from . import Abgelehnt, kennung, laenge_text
from . import journal, katalog, rechte, stueckliste
from . import status as st

log = logging.getLogger(__name__)

SET_OHNE_TEILE = ("Ein Hersteller-Set legst du mit seinen Teilen an („teile“: je einzeln geführtem Bestandteil so viele, "
                  "wie die Stückliste nennt).")
OHNE_STUECKLISTE = ("Für dieses Hersteller-Set ist noch keine Stückliste gepflegt – das macht die Material-Verwaltung im "
                    "Katalog (Reiter „Bestandteile“).")
NUR_FUER_SETS = "„teile“ gibt es nur beim Anlegen eines Hersteller-Sets."
SET_NUR_DIALOG = "Ein Hersteller-Set legst du mit seinen Teilen über „Artikel anlegen“ an – nicht über diesen Weg."
STR_HINWEIS = "STR-Nummer am Teil anbringen (Etikett oder Gravur): {inv} – {name}, {serie}"
STR_HINWEIS_SET = "STR-Nummer am Set anbringen (Etikett oder Gravur): {inv} – {name}, {serie}"
UNSTIMMIG = ("Set und Teile liegen nicht mehr gleich (Ordner, Sperre oder Zuordnung) – nichts gespeichert. Bitte der "
             "Material-Verwaltung melden.")
# Was ein Teil beim Anlegen aus der Anfrage übernimmt (Entwurf C) – Produkt und Ordner setzt der Dienst.
TEIL_FELDER = ("serial_no", "manufactured_on", "purchased_on", "first_use_on", "length_m")
# Was set_lage je Zeile verschieden setzen darf (K2: Sperrursache, Grund, Prüfpflicht im Freigabe-Lauf).
_JE_ZEILE = ("lock_state", "lock_reason", "lock_cause", "set_pruefen", "set_lock_origin")
_GLEICH = object()
BLEIBT = _GLEICH                      # Vorgabe in je_zeile: die übrigen Zeilen behalten ihren Wert
# Gründe der Set-Sperre (lock_reason) – am mitgesperrten Teil, am Set-Artikel und für die Anlässe ohne eigenen Grund.
MIT_SET = "mit dem Set {inv} gesperrt"
MIT_SET_ANLASS = "mit dem Set {inv} gesperrt ({anlass})"
WEGEN_TEIL = "wegen Teil {inv}: {grund}"
SET_PRUEFEN = "Set-Prüfung ausstehend"
UNVOLLSTAENDIG = "unvollständig: {bez} {was}"
GETAUSCHT = "Teil getauscht – Set prüfen"
EINGESETZT = "Teil eingesetzt – Set prüfen"
# Wohin ein Teil beim Aussondern des Sets geht (Entscheidung vom 23.10.2026: je Teil wählbar).
VERBLEIB = {"aussondern": "mit aussondern", "weiterfuehren": "entnehmen und gesperrt weiterführen"}
TEIL_FEHLT = "Teil nicht gefunden."
# Anlass einer Set-Sperre ohne eigenen Grund eines Artikels (Journal „set_grund“; der Jahresbericht zählt sie eigens).
SET_GRUENDE = ("unvollstaendig", "tausch")


class SetUnstimmig(Abgelehnt):
    """Set und Teile liegen nicht mehr gleich – die Transaktion rollt zurück (set_stimmig). Ein Fehler im Dienst, kein
    Fehler der Eingabe: 500 mit Klartext, im Log mit dem Set."""

    def __init__(self, set_id):
        super().__init__(UNSTIMMIG, 500)
        self.set_id = set_id


# --- Was ist ein Set, was ein Teil --------------------------------------------------------------------------------

def set_produkte():
    """Die Kennungen aller Produkte mit dem Häkchen „Hersteller-Set“ – einmal je Anfrage (Listen fragen je Zeile)."""
    speicher = g if has_request_context() else None
    if speicher is not None and "mat_set_produkte" in speicher:
        return speicher.mat_set_produkte
    out = {r["id"] for r in db.query("SELECT id FROM mat_product WHERE is_set = 1")}
    if speicher is not None:
        speicher.mat_set_produkte = out
    return out


def set_produkte_vergessen():
    """Nach dem Umschalten von „Hersteller-Set“: den Zwischenspeicher der Anfrage leeren."""
    if has_request_context():
        g.pop("mat_set_produkte", None)


def ist_set_artikel(item):
    """Ist der Artikel ein Set-Artikel (Produkt mit „Hersteller-Set“)?"""
    if "product_is_set" in item:
        return bool(item["product_is_set"])
    return item["product_id"] in set_produkte()


def ist_teil(item):
    return item.get("parent_item_id") is not None


def im_set(item):
    """Gehört der Artikel zu einem Set – als Set-Artikel oder als Teil?"""
    return ist_teil(item) or ist_set_artikel(item)


def set_zeile(set_id, gefiltert=True):
    """Die Zeile des Set-Artikels – gefiltert: nur, wenn das Konto sie sieht (artikel_filter, H). None sonst."""
    bedingung = f" AND {rechte.artikel_filter('s')}" if gefiltert else ""
    return db.query(f"SELECT s.*, p.manufacturer, p.model, p.description AS product_description, p.article_no "
                    f"FROM mat_item s JOIN mat_product p ON p.id = s.product_id WHERE s.id = ?{bedingung}",
                    (set_id,), one=True)


def teile(set_id, gefiltert=True):
    """Die aktuellen Teile eines Sets (parent_item_id = Set) mit Produktangaben, nach Kennung – gefiltert wie set_zeile."""
    bedingung = f" AND {rechte.artikel_filter('t')}" if gefiltert else ""
    return db.query(f"SELECT t.*, p.manufacturer, p.model, p.description AS product_description, p.article_no, "
                    f"p.material_kind, p.image AS product_image FROM mat_item t JOIN mat_product p ON p.id = t.product_id "
                    f"WHERE t.parent_item_id = ?{bedingung} ORDER BY t.id", (set_id,))


def _kurzname(r, beschr_feld="product_description"):
    return katalog.produktname(r, r.get(beschr_feld) if beschr_feld in r else None)


def _set_text(s):
    return f"{s['inventory_no']} ({_kurzname(s)})" if s.get("manufacturer") else s["inventory_no"]


# --- Weichen in den vorhandenen Einzelwegen --------------------------------------------------------------------------

def teil_weiche(item, was):
    """Einzelwege, die es an einem Teil nicht gibt (Verschieben, Zuordnen, Produktwechsel, Aussondern, Löschen): 409 mit
    dem Set. was: was gerade versucht wurde, etwa „Verschieben“."""
    if not ist_teil(item):
        return
    s = set_zeile(item["parent_item_id"], gefiltert=False)
    raise Abgelehnt(f"{item['inventory_no']} ist Teil des Sets {_set_text(s) if s else ''} – {was} geht nur mit dem ganzen "
                    "Set. Ein Teil verlässt das Set nur über „Teil entnehmen“.", 409)


def produktwechsel_weiche(alt, neues_produkt):
    """bestand.artikel_aendern: kein Produktwechsel an Teilen, an Sets und von oder zu einem Set-Produkt (A7b)."""
    if neues_produkt == alt["product_id"]:
        return
    teil_weiche(alt, "ein Produktwechsel")
    if ist_set_artikel(alt) or neues_produkt in set_produkte():
        raise Abgelehnt("Von einem Hersteller-Set oder zu einem wechselt das Produkt nicht – lege das Set neu an (es bringt "
                        "seine Teile mit).", 409)


# --- Lage, Sperre und Zuordnung: nur gemeinsam ------------------------------------------------------------------------

def set_lage(set_id, folder_id=_GLEICH, origin_folder_id=_GLEICH, lock_state=_GLEICH, assigned_user_id=_GLEICH,
             je_zeile=None):
    """Lage, Sperrzustand und Zuordnung von Set und Teilen – in EINER Anweisung über den Set-Artikel und alle aktuellen
    Teile (WHERE id = :s OR parent_item_id = :s), in der Transaktion des Aufrufers. Nur die genannten Spalten ändern
    sich. je_zeile: {spalte: ({kennung: wert}, vorgabe)} für Werte, die je Zeile verschieden sind – lock_state (Verlust
    an einem Teil), lock_reason, lock_cause, set_pruefen, set_lock_origin (Sperr-Kaskade, K2); die Vorgabe BLEIBT lässt
    die übrigen Zeilen, wie sie sind. Das Journal schreibt der Aufrufer (je Zeile wie bisher). Danach set_stimmig.
    Liefert die Zahl der Zeilen."""
    setzen, args = [], {"s": set_id, "ts": db.now()}
    for spalte, wert in (("folder_id", folder_id), ("origin_folder_id", origin_folder_id), ("lock_state", lock_state),
                         ("assigned_user_id", assigned_user_id)):
        if wert is not _GLEICH:
            setzen.append(f"{spalte} = :{spalte}")
            args[spalte] = wert
    for spalte, (werte, vorgabe) in (je_zeile or {}).items():
        if spalte not in _JE_ZEILE or spalte in args:
            raise ValueError(spalte)
        faelle = []
        for n, (iid, wert) in enumerate(sorted(werte.items())):
            faelle.append(f"WHEN :{spalte}_k{n} THEN :{spalte}_w{n}")
            args[f"{spalte}_k{n}"], args[f"{spalte}_w{n}"] = iid, wert
        sonst = spalte if vorgabe is BLEIBT else f":{spalte}_v"
        if vorgabe is not BLEIBT:
            args[f"{spalte}_v"] = vorgabe
        if not faelle and vorgabe is BLEIBT:
            continue
        setzen.append(f"{spalte} = CASE id {' '.join(faelle)} ELSE {sonst} END" if faelle else f"{spalte} = {sonst}")
    if not setzen:
        return 0
    n = db.execute_zeilen(f"UPDATE mat_item SET {', '.join(setzen)}, updated_at = :ts "
                          "WHERE id = :s OR parent_item_id = :s", args)
    set_stimmig(set_id)
    return n


_ABWEICHUNG = ("(t.folder_id IS NOT s.folder_id OR t.origin_folder_id IS NOT s.origin_folder_id "
               "OR (t.lock_state = 'frei') <> (s.lock_state = 'frei') OR t.assigned_user_id IS NOT s.assigned_user_id)")


def set_stimmig(set_id):
    """Am Ende jeder Transaktion, die ein Set berührt: Liegen, sperren und gehören alle Teile wie ihr Set? Sonst
    SetUnstimmig – die Transaktion rollt zurück. Eine Abfrage."""
    n = db.query("SELECT COUNT(*) AS n FROM mat_item t JOIN mat_item s ON s.id = t.parent_item_id "
                 f"WHERE s.id = ? AND {_ABWEICHUNG}", (set_id,), one=True)["n"]
    if n:
        log.error("Set %s: %s Teile liegen nicht wie das Set – zurückgerollt.", set_id, n)
        raise SetUnstimmig(set_id)


def sets_stimmig(set_ids):
    for sid in sorted(set(set_ids)):
        set_stimmig(sid)


def betroffene_sets(item_ids):
    """Die Sets, die eine Änderung an diesen Artikeln berührt (als Set-Artikel oder über ein Teil)."""
    ids = sorted({int(x) for x in item_ids})
    if not ids:
        return set()
    marken = ",".join("?" * len(ids))
    return {r["sid"] for r in db.query(
        f"SELECT COALESCE(i.parent_item_id, i.id) AS sid FROM mat_item i WHERE i.id IN ({marken}) "
        f"AND (i.parent_item_id IS NOT NULL OR EXISTS (SELECT 1 FROM mat_item t WHERE t.parent_item_id = i.id))", ids)}


UNSTIMMIG_SQL = ("SELECT DISTINCT s.id FROM mat_item t JOIN mat_item s ON s.id = t.parent_item_id "
                 f"WHERE {_ABWEICHUNG} ORDER BY s.id")


def unstimmige(conn=None):
    """Alle Sets, deren Teile nicht wie sie liegen – leer heißt: alles in Ordnung."""
    if conn is not None:
        return [r[0] for r in conn.execute(UNSTIMMIG_SQL)]
    return [r["id"] for r in db.query(UNSTIMMIG_SQL)]


def beim_start(conn):
    """Startprüfung „Sets stimmig“ (Entwurf B, S1) – nur ein Log, kein Abbruch (wie die Fremdschlüssel nach einem
    Umbau). Vor Schritt 21 (keine Spalte parent_item_id) gibt es nichts zu prüfen."""
    if "parent_item_id" not in [r[1] for r in conn.execute("PRAGMA table_info(mat_item)")]:
        return
    falsch = unstimmige(conn)
    if falsch:
        log.warning("Sets nicht stimmig (Teile liegen, sperren oder gehören anders als ihr Set): %s",
                    ", ".join(str(x) for x in falsch[:20]))


# --- Sperr-Kaskade und Freigabe (Entwurf D, Paket K2) -----------------------------------------------------------------

def set_kennung(item):
    """Die Kennung des Sets, zu dem der Artikel gehört (er selbst als Set-Artikel, sonst sein Set)."""
    return item["parent_item_id"] or item["id"]


def zeilen(set_id):
    """Set-Artikel und aktuelle Teile frisch und ungefiltert (in der Transaktion des Aufrufers): (Set, [Teile])."""
    s = db.query("SELECT * FROM mat_item WHERE id = ?", (set_id,), one=True)
    if not s:
        raise Abgelehnt("Artikel nicht gefunden.", 404)
    return s, db.query("SELECT * FROM mat_item WHERE parent_item_id = ? ORDER BY id", (set_id,))


def _pfad(fid):
    from . import bestand
    return bestand._pfad_text(fid)


def mit_grund(s, x):
    """Der Grund einer nur geerbten Sperre (lock_cause „set“): am Teil „mit dem Set … gesperrt“, am Set-Artikel „Set-Prüfung
    ausstehend“."""
    return SET_PRUEFEN if x["id"] == s["id"] else MIT_SET.format(inv=s["inventory_no"])


def sperren(set_id, eigen=None, zustand="gesperrt", grund="", aktion="gesperrt", zusatz=None, set_grund=None, anlass="",
            neu=()):
    """Die Sperr-Kaskade, in der Transaktion des Aufrufers. eigen: Kennung des Artikels (Set-Artikel oder Teil) mit eigener
    Sperre (zustand gesperrt oder verloren, grund, Journal aktion mit zusatz – „gesperrt“ oder „mangel_gemeldet“) – oder
    None, wenn das Set aus eigenem Anlass sperrt (set_grund „unvollstaendig“ | „tausch“, anlass als Text). neu: Teile,
    die neu im Set sind und im Freigabe-Lauf geprüft werden (set_pruefen), ohne eigenen Grund.

    Ist das Set frei: EIN UPDATE über Set und Teile (set_lage) nach „Gesperrt“ der Gliederung, Herkunft = Heimat des Sets;
    eigen bekommt „eigen“, alle anderen „set“; Verlust am Set-Artikel heißt: alle verloren, an einem Teil nur dieses.
    Journal: am Anlass die Aktion mit dem Handelnden (sie zählt im Jahresbericht als die eine Sperre), an allen anderen
    „set_gesperrt“ als „System“. Ist das Set schon gesperrt: eigen bekommt „eigen“ (auch ein nur mitgesperrtes Teil),
    ein Teil set_pruefen, der Set-Artikel den Ursprung „set“ (der Freigabe-Lauf prüft dann alle Teile); hatte eigen
    schon einen eigenen Grund, bleibt die Sperre mit ihm (nur der Eintrag). Liefert, ob das Set dabei gesperrt wurde."""
    from . import bestand
    s, tz = zeilen(set_id)
    alle = {r["id"]: r for r in [s] + tz}
    x = alle[eigen] if eigen else None
    pruefen = {int(t) for t in neu} | ({eigen} if eigen and eigen != set_id else set())
    zusatz = dict(zusatz or {})
    if s["lock_state"] == "frei":
        gl = bestand.gliederung_von(s["folder_id"])
        ziel = bestand.systemordner(gl["id"], "gesperrt") if gl else None
        if not ziel:
            raise Abgelehnt("Der Systemordner „Gesperrt“ der Gliederung fehlt – bitte den Ordnerbaum prüfen.", 409)
        ziel, heimat = ziel["id"], s["folder_id"]
        if eigen and eigen != set_id:
            anlass = WEGEN_TEIL.format(inv=x["inventory_no"], grund=grund)
        elif eigen:
            anlass = grund
        gruende = {set_id: anlass}
        if eigen:
            gruende[eigen] = grund
        verlust_am_set = eigen == set_id and zustand == "verloren"
        set_lage(set_id, folder_id=ziel, origin_folder_id=heimat, je_zeile={
            "lock_state": ({eigen: zustand} if eigen else {}, "verloren" if verlust_am_set else "gesperrt"),
            "lock_cause": ({eigen: "eigen"} if eigen else {}, "set"),
            "lock_reason": (gruende, MIT_SET_ANLASS.format(inv=s["inventory_no"], anlass=anlass)),
            "set_pruefen": ({t: 1 for t in pruefen}, 0),
            "set_lock_origin": ({set_id: "set" if eigen == set_id else "teil"}, None)})
        s2, tz2 = zeilen(set_id)
        nach = {r["id"]: r for r in [s2] + tz2}
        ausloeser = eigen or set_id
        for r in [s] + tz:
            n = nach[r["id"]]
            vorher = {"lock_state": r["lock_state"], "folder_id": r["folder_id"], "ordner": _pfad(r["folder_id"])}
            nachher = {"lock_state": n["lock_state"], "lock_reason": n["lock_reason"], "lock_cause": n["lock_cause"],
                       "folder_id": ziel, "ordner": _pfad(ziel), "origin_folder_id": heimat, "herkunft": _pfad(heimat)}
            if r["id"] != set_id:
                nachher["set"] = set_id
            if r["id"] == ausloeser:
                if set_grund:
                    nachher["set_grund"] = set_grund
                journal.eintragen("item", r["id"], aktion, vorher, dict(nachher, **zusatz))
            else:
                if r["id"] == set_id and eigen:
                    nachher["teil"] = x["inventory_no"]
                journal.eintragen("item", r["id"], "set_gesperrt", vorher, nachher, system=True)
        return True
    if eigen:
        if x["lock_cause"] == "eigen" and not (zustand == "verloren" and x["lock_state"] != "verloren"):
            # Schon aus eigenem Grund gesperrt: Die Sperre bleibt mit ihrem Grund – nur der Eintrag (wie bisher an einem
            # gesperrten Artikel: Mangelmeldung, „instandsetzen“).
            journal.eintragen("item", eigen, aktion, None, dict(zusatz, **({"set": set_id} if eigen != set_id else {})))
            return False
        je = {"lock_cause": ({eigen: "eigen"}, BLEIBT), "lock_reason": ({eigen: grund}, BLEIBT)}
        if zustand == "verloren":
            je["lock_state"] = ({eigen: "verloren"}, "verloren" if eigen == set_id else BLEIBT)
        if eigen != set_id:
            je["set_pruefen"] = ({eigen: 1}, BLEIBT)
        else:
            je["set_lock_origin"] = ({set_id: "set"}, BLEIBT)
        set_lage(set_id, je_zeile=je)
        vorher = {"lock_state": x["lock_state"], "lock_cause": x["lock_cause"], "lock_reason": x["lock_reason"]}
        nachher = {"lock_state": "verloren" if zustand == "verloren" else x["lock_state"], "lock_cause": "eigen",
                   "lock_reason": grund}
        if eigen != set_id:
            nachher["set"] = set_id
        journal.eintragen("item", eigen, aktion, vorher, dict(nachher, **zusatz))
        if eigen != set_id:
            journal.eintragen("item", set_id, "teil_gesperrt", None, {"teil": x["inventory_no"], "grund": grund},
                              system=True)
        if zustand == "verloren" and eigen == set_id:
            for r in tz:
                if r["lock_state"] != "verloren":
                    journal.eintragen("item", r["id"], "set_gesperrt", {"lock_state": r["lock_state"]},
                                      {"lock_state": "verloren", "set": set_id}, system=True)
        return False
    if pruefen:
        # Neu eingesetzte Teile in ein schon gesperrtes Set: Lage, Sperre und Zuordnung wie das Set, Ursache „set“.
        mit = MIT_SET.format(inv=s["inventory_no"])
        set_lage(set_id, folder_id=s["folder_id"], origin_folder_id=s["origin_folder_id"],
                 assigned_user_id=s["assigned_user_id"], je_zeile={
                     "lock_state": ({t: "gesperrt" for t in pruefen}, BLEIBT),
                     "lock_cause": ({t: "set" for t in pruefen}, BLEIBT),
                     "lock_reason": ({t: mit for t in pruefen}, BLEIBT),
                     "set_pruefen": ({t: 1 for t in pruefen}, BLEIBT)})
        for t in pruefen:
            r = alle[t]
            journal.eintragen("item", t, "set_gesperrt",
                              {"lock_state": r["lock_state"], "folder_id": r["folder_id"], "ordner": _pfad(r["folder_id"])},
                              {"lock_state": "gesperrt", "lock_reason": mit, "lock_cause": "set", "folder_id": s["folder_id"],
                               "ordner": _pfad(s["folder_id"]), "origin_folder_id": s["origin_folder_id"],
                               "herkunft": _pfad(s["origin_folder_id"]), "set": set_id}, system=True)
    return False


def eigen_aufheben(item):
    """Freiprüfung im gesperrten Set (Entwurf D, S8): Der Artikel verliert seinen eigenen Grund („eigen“ → „set“, verloren →
    gesperrt) – Lage und Sperre bleiben, frei wird erst das ganze Set (freigeben). In der Transaktion des Aufrufers.
    Liefert (vorher, nachher) für das Journal des Aufrufers."""
    sid = set_kennung(item)
    s, _ = zeilen(sid)
    x = db.query("SELECT * FROM mat_item WHERE id = ?", (item["id"],), one=True)
    neu_grund = mit_grund(s, x)
    set_lage(sid, je_zeile={"lock_cause": ({x["id"]: "set"}, BLEIBT), "lock_reason": ({x["id"]: neu_grund}, BLEIBT),
                            "lock_state": ({x["id"]: "gesperrt"}, BLEIBT)})
    return ({"lock_state": x["lock_state"], "lock_cause": x["lock_cause"], "lock_reason": x["lock_reason"]},
            {"lock_state": "gesperrt", "lock_cause": "set", "lock_reason": neu_grund})


def freigeben(set_id, ziel):
    """Der eine Freigabe-Übergang (Entwurf D, S10) – nur aus setlauf.wirkung: EIN UPDATE über Set und Teile auf frei, in
    den Rückweg ziel; Ursache, Grund, Prüfpflicht und Ursprung zurückgesetzt. Journal an den Teilen „set_frei“ als
    „System“ (den Eintrag am Set-Artikel schreibt der Aufrufer)."""
    s, tz = zeilen(set_id)
    set_lage(set_id, folder_id=ziel, origin_folder_id=None, lock_state="frei", je_zeile={
        "lock_cause": ({}, None), "lock_reason": ({}, ""), "set_pruefen": ({}, 0), "set_lock_origin": ({}, None)})
    for t in tz:
        journal.eintragen("item", t["id"], "set_frei",
                          {"lock_state": t["lock_state"], "lock_cause": t["lock_cause"], "folder_id": t["folder_id"],
                           "ordner": _pfad(t["folder_id"])},
                          {"lock_state": "frei", "folder_id": ziel, "ordner": _pfad(ziel), "set": set_id}, system=True)


def _artikel_verweis(x, set_id):
    return {"id": x["id"], "inventory_no": x["inventory_no"], "set_artikel": x["id"] == set_id}


def sperrgruende(s, teil_zeilen, voll=None, slot_zeilen=None):
    """Warum ein Set gesperrt ist – abgeleitet, nie gespeichert (Entwurf C, A12-5): je Artikel mit eigenem Grund (oder
    verloren) {art „eigen“ | „verloren“, artikel, text}, „unvollstaendig“ mit den fehlenden Positionen, je Teil, das im
    Freigabe-Lauf zu prüfen ist, „pruefen“ – und immer zuletzt „set_pruefung“ (frei gibt nur „Set prüfen“). Leer, wenn das
    Set frei oder ausgesondert ist."""
    if s["lock_state"] in ("frei", "ausgesondert"):
        return []
    out = []
    for x in [s] + list(teil_zeilen):
        if x["lock_state"] == "verloren" and (x["lock_cause"] == "eigen" or x["id"] == s["id"]):
            out.append({"art": "verloren", "artikel": _artikel_verweis(x, s["id"]),
                        "text": f"{x['inventory_no']}: verloren" + (f" ({x['lock_reason']})" if x["lock_reason"] else "")})
        elif x["lock_cause"] == "eigen":
            out.append({"art": "eigen", "artikel": _artikel_verweis(x, s["id"]),
                        "text": f"{x['inventory_no']}: {x['lock_reason'] or 'gesperrt'}"})
    if voll is None:
        voll, fehlend = vollstaendigkeit(slot_zeilen if slot_zeilen is not None else slots(s["id"]), teil_zeilen)
    else:
        fehlend = vollstaendigkeit(slot_zeilen if slot_zeilen is not None else slots(s["id"]), teil_zeilen)[1]
    if not voll:
        out.append({"art": "unvollstaendig", "artikel": None,
                    "text": "unvollständig: " + ", ".join(f"„{f['bezeichnung']}“ fehlt" + (f" {f['fehlt']}×" if f["fehlt"] > 1
                                                                                         else "") for f in fehlend)})
    for t in teil_zeilen:
        if t["set_pruefen"] and t["lock_cause"] != "eigen":
            out.append({"art": "pruefen", "artikel": _artikel_verweis(t, s["id"]),
                        "text": f"{t['inventory_no']}: in der Set-Prüfung zur Freigabe zu prüfen"})
    out.append({"art": "set_pruefung", "artikel": None,
                "text": "Frei gibt das Set nur „Set prüfen“ mit dem Ergebnis „einsatzbereit“."})
    return out


def verbleib_vorschlag(t):
    """Vorbelegung im Dialog „Set aussondern“ je Teil (Entscheidung vom 23.10.2026): mit aussondern, wer einen eigenen
    Aussonderungsgrund hat – eigene Sperre durch einen Prüfer (nicht nur aus einer ungeprüften Mangelmeldung) oder
    verloren –, sonst entnehmen und gesperrt weiterführen."""
    from . import mangel
    if t["lock_state"] == "verloren":
        return "aussondern"
    if t["lock_cause"] == "eigen" and not mangel.ungeprueft(t["id"]):
        return "aussondern"
    return "weiterfuehren"


# --- Set anlegen ------------------------------------------------------------------------------------------------------

def _hinweis_str(vorlage, inv, p, serie):
    return vorlage.format(inv=inv, name=katalog.produktname(p), serie=serie)


def set_anlegen(d, plan):
    """POST /artikel mit einem Set-Produkt (bestand.anlegen): der Set-Artikel nach plan (bestand.artikel_plan) und je
    einzeln geführter Position der Stückliste genau „anzahl“ Teile – „teile“: [{"bestandteil_id": Kennung der Position,
    "serial_no", "manufactured_on", "purchased_on", "first_use_on", "length_m"}]. Das Produkt eines Teils kommt aus der
    Stückliste, nie aus der Anfrage; der Ordner ist der des Sets. Doppelte Seriennummern in der Anfrage → 400 vor jedem
    Schreiben. Eine Transaktion: Set, Kopie der Stückliste, Teile, Journal „set_angelegt“ mit der Teileliste am Set,
    set_stimmig. Liefert (Kennung des Sets, Hinweise – etwa „STR-Nummer am Teil anbringen“)."""
    from . import bestand
    p = plan["p"]
    roh = d.get("teile")
    if roh is None:
        raise Abgelehnt(SET_OHNE_TEILE)
    if not isinstance(roh, list):
        raise Abgelehnt("„teile“ muss eine Liste sein.")
    stueck = stueckliste.zeilen(p["id"])
    if not stueck:
        raise Abgelehnt(OHNE_STUECKLISTE, 409)
    einzeln = {z["id"]: z for z in stueck if z["einzeln"]}
    je = {zid: [] for zid in einzeln}
    for n, t in enumerate(roh, start=1):
        if not isinstance(t, dict):
            raise Abgelehnt(f"Teil {n}: kein Objekt.")
        zid = kennung(t.get("bestandteil_id"), f"Teil {n}: Bestandteil")
        if zid not in einzeln:
            raise Abgelehnt(f"Teil {n}: Diese Position steht nicht als einzeln geführter Bestandteil in der Stückliste "
                            "des Sets.")
        je[zid].append(t)
    for zid, z in einzeln.items():
        if len(je[zid]) != z["anzahl"]:
            raise Abgelehnt(f"„{z['bezeichnung']}“: genau {z['anzahl']} Teil{'e' if z['anzahl'] != 1 else ''} angeben "
                            f"(hier {len(je[zid])}).")
    plaene, gesehen = [], {}
    for z in stueck:
        for t in je.get(z["id"], []):
            felder = {f: t[f] for f in TEIL_FELDER if f in t}
            try:
                pt = bestand.artikel_plan(dict(felder, product_id=z["component_product_id"], folder_id=plan["fid"]))
            except Abgelehnt as exc:
                raise Abgelehnt(f"Teil „{z['bezeichnung']}“: {exc}", exc.code)
            serie = pt["w"]["serial_no"]
            if serie:
                schluessel = (pt["p"]["id"], serie.casefold())
                if schluessel in gesehen:
                    raise Abgelehnt(f"Die Seriennummer „{serie}“ steht zweimal in den Teilen ({z['bezeichnung']}).")
                gesehen[schluessel] = True
            plaene.append((z, pt))
    hinweise = []
    with db.transaction(sofort=True):
        sid = bestand.artikel_schreiben(plan, als_set=True)
        s = bestand.artikel(sid)
        if s["serial_generated"]:
            hinweise.append(_hinweis_str(STR_HINWEIS_SET, s["inventory_no"], p, s["serial_no"]))
        for z in stueck:
            db.execute("INSERT INTO mat_item_set_slot (set_item_id, position, product_id, bezeichnung, anzahl, einzeln, "
                       "austausch) VALUES (?,?,?,?,?,?,?)",
                       (sid, z["position"], z["component_product_id"], z["bezeichnung"], z["anzahl"], z["einzeln"],
                        z["austausch"]))
        liste = []
        for z, pt in plaene:
            tid = bestand.artikel_schreiben(pt, journal_zusatz={"set": sid, "set_inventar": s["inventory_no"]},
                                            parent_id=sid)
            t = bestand.artikel(tid)
            liste.append({"teil": tid, "inventory_no": t["inventory_no"], "serial_no": t["serial_no"],
                          "bestandteil": z["bezeichnung"], "produkt": katalog.produktname(pt["p"])})
            if t["serial_generated"]:
                hinweise.append(_hinweis_str(STR_HINWEIS, t["inventory_no"], pt["p"], t["serial_no"]))
        journal.eintragen("item", sid, "set_angelegt", None,
                          {"teile": liste, "bestandteile": [z["bezeichnung"] for z in stueck if not z["einzeln"]]})
        set_stimmig(sid)
    return sid, hinweise


def anlegen_vorschlag(p):
    """GET /artikel/vorschlag mit einem Set-Produkt: die Stückliste für den Dialog „Set anlegen“ (je einzeln geführter
    Position „anzahl“ Teilblöcke; Produkt mit Materialart und laenge_moeglich) – sonst None."""
    if not p["is_set"]:
        return None
    return {"bestandteile": stueckliste.stueckliste_json(p["id"]), "teil_felder": list(TEIL_FELDER),
            "hilfe_einzeln": stueckliste.HILFE_EINZELN}


# --- Set-Werte: Status, Fälligkeit, Lebensende, Vollständigkeit -------------------------------------------------------

def slots(set_id):
    """Die Kopie der Stückliste eines Sets mit Produktangaben (wie stueckliste.zeilen)."""
    return db.query(
        "SELECT z.*, p.manufacturer, p.model, p.description, p.article_no, p.material_kind, p.category_id, p.demo, "
        "p.lifetime_years FROM mat_item_set_slot z LEFT JOIN mat_product p ON p.id = z.product_id "
        "WHERE z.set_item_id = ? ORDER BY z.position, z.id", (set_id,))


def _zuteilen(slot_zeilen, teil_zeilen):
    """Teile den Positionen zuteilen – je Produkt der Reihe nach (zwei Positionen mit demselben Produkt teilen sich die
    Teile in Positionsreihenfolge). Liefert ({Teil-Kennung: Position}, {Positions-Kennung: Zahl vorhanden})."""
    frei = {}
    for t in teil_zeilen:
        frei.setdefault(t["product_id"], []).append(t["id"])
    zu, vorhanden = {}, {}
    for z in slot_zeilen:
        if not z["einzeln"]:
            continue
        liste = frei.get(z["product_id"], [])
        nimm, frei[z["product_id"]] = liste[:z["anzahl"]], liste[z["anzahl"]:]
        vorhanden[z["id"]] = len(nimm)
        for tid in nimm:
            zu[tid] = z
    return zu, vorhanden


def vollstaendigkeit(slot_zeilen, teil_zeilen):
    """(vollständig, [{bezeichnung, fehlt}]) – laut Kopie der Stückliste (nur einzeln geführte Positionen; ob die übrigen
    Bestandteile da sind, bestätigt der Prüfer in der Set-Prüfung)."""
    _, vorhanden = _zuteilen(slot_zeilen, teil_zeilen)
    fehlend = [{"bezeichnung": z["bezeichnung"], "fehlt": z["anzahl"] - vorhanden.get(z["id"], 0)}
               for z in slot_zeilen if z["einzeln"] and vorhanden.get(z["id"], 0) < z["anzahl"]]
    return not fehlend, fehlend


def _verweis(x):
    return {"id": x["id"], "inventory_no": x["inventory_no"], "set_artikel": x.get("parent_item_id") is None}


def werte(s, teil_zeilen, stichtag=None):
    """Set-Status, Set-Fälligkeit und Set-Lebensende aus Set-Artikel s und den aktuellen Teilen: {status, status_text,
    next_due_on, faellig_durch, retire_by, lebensende_durch} – faellig_durch/lebensende_durch: der Artikel, der den Wert
    bestimmt ({id, inventory_no, set_artikel})."""
    alle = [s] + list(teil_zeilen)
    status = st.schlechtester([st.status(x, stichtag) for x in alle])
    faellig = min((x for x in alle if x["next_due_on"]), key=lambda x: (x["next_due_on"], x["id"]), default=None)
    ende = min((x for x in alle if x["retire_by"]), key=lambda x: (x["retire_by"], x["id"]), default=None)
    return {"status": status, "status_text": st.LABEL[status],
            "next_due_on": faellig["next_due_on"] if faellig else None,
            "faellig_durch": _verweis(faellig) if faellig else None,
            "retire_by": ende["retire_by"] if ende else None,
            "lebensende_durch": _verweis(ende) if ende else None}


def gruppen_status_sql(alias="i"):
    """SQL über mat_item (alias): für eine Set-Zeile der Set-Status (werte), sonst status_sql – für Filter und
    Sortierung der Listen. Beide Zeilen (Set und Teil) gefiltert (artikel_filter). Braucht die Parameter aus
    status.parameter()."""
    a = rechte._bezeichner(alias)
    rang = st.rang_sql(st.status_sql("gt"))
    return (f"(CASE WHEN EXISTS (SELECT 1 FROM mat_item gk WHERE gk.parent_item_id = {a}.id) THEN "
            f"(SELECT {st.aus_rang_sql(f'MIN({rang})')} FROM mat_item gt WHERE (gt.id = {a}.id OR gt.parent_item_id = "
            f"{a}.id) AND {rechte.artikel_filter('gt')}) ELSE {st.status_sql(a)} END)")


def gruppen_faellig_sql(alias="i"):
    """SQL: die Set-Fälligkeit (früheste nächste Prüfung aus Set-Artikel und Teilen), sonst next_due_on."""
    a = rechte._bezeichner(alias)
    return (f"(CASE WHEN EXISTS (SELECT 1 FROM mat_item gk WHERE gk.parent_item_id = {a}.id) THEN "
            f"(SELECT MIN(gt.next_due_on) FROM mat_item gt WHERE gt.id = {a}.id OR gt.parent_item_id = {a}.id) "
            f"ELSE {a}.next_due_on END)")


def gruppen_sortier_faellig_sql(alias="i"):
    """SQL für die Sortierung „faellig“ (bestand.artikel_sortierung) über die Set-Zeile: neue zuerst, gesperrte hinten –
    über Set-Artikel und Teile das Früheste."""
    a = rechte._bezeichner(alias)
    einzeln = ("(CASE WHEN {x}.lock_state <> 'frei' THEN NULL WHEN {x}.last_inspected_on IS NULL THEN '' "
               "ELSE {x}.next_due_on END)")
    return (f"(CASE WHEN EXISTS (SELECT 1 FROM mat_item gk WHERE gk.parent_item_id = {a}.id) THEN "
            f"(SELECT MIN({einzeln.format(x='gt')}) FROM mat_item gt WHERE gt.id = {a}.id OR gt.parent_item_id = {a}.id) "
            f"ELSE {einzeln.format(x=a)} END)")


TEILE_ZAHL_SQL = "(SELECT COUNT(*) FROM mat_item tz WHERE tz.parent_item_id = {}.id)"


def zahlen(von_where, params):
    """Kopf der Listen: {anzahl: Sets unter den Zeilen, teile: ihre Teile} über dieselbe Bedingung wie die Liste
    (von_where: „FROM mat_item i … WHERE …“)."""
    r = db.query("SELECT COALESCE(SUM(EXISTS (SELECT 1 FROM mat_product zp WHERE zp.id = i.product_id AND zp.is_set = 1)), "
                 "0) AS m, "
                 f"COALESCE(SUM({TEILE_ZAHL_SQL.format('i')}), 0) AS k {von_where}", params, one=True)
    return {"anzahl": r["m"], "teile": r["k"]}


# --- Antworten ----------------------------------------------------------------------------------------------------------

def listenzeile(k, r):
    """Eine Listenzeile (bestand.artikel_kurz) eines Set-Artikels zur Set-Zeile machen: Status, Fälligkeit und Lebensende
    des Sets, dazu „set“ = {teile, eigen (Werte des Set-Artikels allein), faellig_durch, lebensende_durch, mangel_teile,
    rueckruf_teile, vollstaendig}. Für andere Zeilen bleibt k, wie es ist (set = None)."""
    from . import mangel, rueckruf
    k.setdefault("set", None)
    if not ist_set_artikel(r):
        return k
    tz = teile(r["id"])
    w = werte(r, tz)
    offen = mangel.offene_artikel()
    rr = rueckruf.offene_artikel()
    k["set"] = {"teile": len(tz), "eigen": {"status": k["status"], "status_text": k["status_text"],
                                             "next_due_on": k["next_due_on"], "retire_by": k["retire_by"]},
                "faellig_durch": w["faellig_durch"], "lebensende_durch": w["lebensende_durch"],
                "mangel_teile": [t["inventory_no"] for t in tz if t["id"] in offen],
                "rueckruf_teile": [{"inventory_no": t["inventory_no"], "titel": rr[t["id"]]} for t in tz if t["id"] in rr],
                "vollstaendig": vollstaendigkeit(slots(r["id"]), tz)[0]}
    k.update({"status": w["status"], "status_text": w["status_text"], "next_due_on": w["next_due_on"],
              "retire_by": w["retire_by"]})
    return k


def teil_von_json(item):
    """Am Teil: {id, inventory_no, produkt, status, status_text, bestandteil} des Sets – nur, wenn das Konto das Set sieht
    (artikel_filter auf der Set-Zeile), sonst None. Für Nicht-Teile None."""
    if not ist_teil(item):
        return None
    s = set_zeile(item["parent_item_id"])
    if not s:
        return None
    tz = teile(s["id"])
    w = werte(s, tz)
    zu, _ = _zuteilen(slots(s["id"]), tz)
    z = zu.get(item["id"])
    return {"id": s["id"], "inventory_no": s["inventory_no"], "produkt": _kurzname(s), "status": w["status"],
            "status_text": w["status_text"], "bestandteil": z["bezeichnung"] if z else None}


def teil_kurz(item):
    """Für Listenzeilen (Suche, Durchgang): {id, inventory_no, produkt} des Sets – gefiltert wie teil_von_json."""
    if not ist_teil(item):
        return None
    s = set_zeile(item["parent_item_id"])
    return {"id": s["id"], "inventory_no": s["inventory_no"], "produkt": _kurzname(s)} if s else None


def _teil_json(t, z, offen, rr):
    s = st.status(t)
    return {"id": t["id"], "inventory_no": t["inventory_no"], "serial_no": t["serial_no"],
            "serial_generated": bool(t["serial_generated"]),
            "produkt": {"id": t["product_id"], "name": _kurzname(t), "manufacturer": t["manufacturer"],
                        "model": t["model"], "description": t["product_description"] or "", "article_no": t["article_no"],
                        "material_kind": t["material_kind"], "vorschau": katalog.bild_url(t.get("product_image"), "thumb")},
            "bestandteil": z["bezeichnung"] if z else None, "status": s, "status_text": st.LABEL[s],
            "next_due_on": t["next_due_on"], "retire_by": t["retire_by"], "last_inspected_on": t["last_inspected_on"],
            "lock_state": t["lock_state"], "lock_cause": t["lock_cause"],
            "lock_reason": t["lock_reason"] if t["lock_state"] != "frei" else "",
            "length_m": t["length_m"], "laenge_text": laenge_text(t["length_m"]),
            "mangel": t["id"] in offen, "rueckruf": rr.get(t["id"]),
            # K2: Position der Kopie (für „Teil tauschen“), Prüfpflicht im Freigabe-Lauf, Vorbelegung „Set aussondern“.
            "slot_id": z["id"] if z else None, "austausch": z["austausch"] if z else None,
            "set_pruefen": bool(t["set_pruefen"]), "verbleib_vorschlag": verbleib_vorschlag(t)}


def set_json(item):
    """Der Block „set“ an einem Set-Artikel (bestand.artikel_json) – None für andere Artikel:
      status, status_text, next_due_on, faellig_durch, retire_by, lebensende_durch   die Set-Werte (werte)
      eigen        {status, status_text, next_due_on, retire_by} des Set-Artikels allein
      teile        je aktuellem Teil Nummern, Produkt, Position („bestandteil“), Status, Fälligkeit, Lebensende, Sperre
                   (lock_state, lock_cause, lock_reason), Länge, offener Mangel, Rückruf (Titel)
      bestandteile die Kopie der Stückliste: je Position bezeichnung, anzahl, einzeln, austausch(_text), produkt und –
                   einzeln geführt – vorhanden/fehlt
      vollstaendig, fehlend   laut Kopie (nur einzeln geführte Positionen)
      rueckrufe_teile         [{teil: {id, inventory_no}, titel}] – Banner am Set (A17)
      teile_anzahl, ursprung (set_lock_origin), sperrgruende (abgeleitet, sperrgruende)
      lauf         die offene Set-Prüfung (setlauf.kurz) oder None; letzte_pruefung: die zuletzt abgeschlossene mit
                   Gesamtergebnis und berichtigten Teilprüfungen (setlauf.letzte) oder None
    Teile nur, soweit das Konto sie sieht (artikel_filter auf beiden Zeilen)."""
    from . import mangel, rueckruf, setlauf
    if not ist_set_artikel(item):
        return None
    tz = teile(item["id"])
    sz = slots(item["id"])
    w = werte(item, tz)
    zu, vorhanden = _zuteilen(sz, tz)
    offen, rr = mangel.offene_artikel(), rueckruf.offene_artikel()
    voll, fehlend = vollstaendigkeit(sz, tz)
    eigen = st.status(item)
    bestandteile = []
    for z in sz:
        b = {"id": z["id"], "position": z["position"], "bezeichnung": z["bezeichnung"], "anzahl": z["anzahl"],
             "einzeln": bool(z["einzeln"]), "austausch": z["austausch"],
             "austausch_text": stueckliste.AUSTAUSCH[z["austausch"]], "produkt": stueckliste._produkt_kurz(z)}
        if z["einzeln"]:
            b["vorhanden"] = vorhanden.get(z["id"], 0)
            b["fehlt"] = z["anzahl"] - b["vorhanden"]
        bestandteile.append(b)
    return dict(w, eigen={"status": eigen, "status_text": st.LABEL[eigen], "next_due_on": item["next_due_on"],
                          "retire_by": item["retire_by"]},
                teile=[_teil_json(t, zu.get(t["id"]), offen, rr) for t in tz], teile_anzahl=len(tz),
                bestandteile=bestandteile, vollstaendig=voll, fehlend=fehlend,
                rueckrufe_teile=[{"teil": {"id": t["id"], "inventory_no": t["inventory_no"]}, "titel": rr[t["id"]]}
                                 for t in tz if t["id"] in rr],
                ursprung=item.get("set_lock_origin"), sperrgruende=sperrgruende(item, tz, voll, sz),
                lauf=setlauf.kurz(setlauf.offener(item["id"])), letzte_pruefung=setlauf.letzte(item["id"]))


def darf_loeschen(item):
    """Ein Set löschen: nur ganz und nur, solange weder der Set-Artikel noch ein Teil eine Prüfung, eine Mangelmeldung
    oder eine Zeile in einem Prüfdurchgang hat und kein Set-Prüflauf daran hängt. Ein Teil einzeln (Entwurf C, A10): unter
    denselben Bedingungen für das Teil allein – das Set ist danach unvollständig und gesperrt (setaustausch.teil_loeschen)."""
    ids = [item["id"]]
    if not ist_teil(item):
        ids += [r["id"] for r in db.query("SELECT id FROM mat_item WHERE parent_item_id = ?", (item["id"],))]
    marken = ",".join("?" * len(ids))
    for tabelle in ("mat_inspection", "mat_defect_report", "mat_round_item"):
        if db.query(f"SELECT 1 FROM {tabelle} WHERE item_id IN ({marken}) LIMIT 1", ids, one=True):
            return False
    return ist_teil(item) or not db.query("SELECT 1 FROM mat_set_lauf WHERE set_item_id = ? LIMIT 1", (item["id"],),
                                          one=True)


def set_loeschen(item):
    """Ein ungeprüftes Set ganz löschen (bestand.artikel_loeschen, in dessen Transaktion): erst die Teile (Journal
    „geloescht“ mit Grund „mit dem Set gelöscht“), dann der Set-Artikel – die Kopie der Stückliste geht mit (ON DELETE
    CASCADE). Inventarnummern werden nie wieder vergeben."""
    from . import bestand
    if not darf_loeschen(item):
        raise Abgelehnt("Das Set oder eines seiner Teile hat Prüfungen, eine Mangelmeldung oder steht in einem "
                        "Prüfdurchgang – es bleibt mit seinem Lebenslauf; aussondern statt löschen.", 409)
    for t in db.query("SELECT * FROM mat_item WHERE parent_item_id = ? ORDER BY id", (item["id"],)):
        db.execute("DELETE FROM mat_item WHERE id = ?", (t["id"],))
        journal.eintragen("item", t["id"], "geloescht", dict(t, ordner=bestand._pfad_text(t["folder_id"])),
                          {"grund": "mit dem Set gelöscht", "set": item["id"]})
    db.execute("DELETE FROM mat_item WHERE id = ?", (item["id"],))
