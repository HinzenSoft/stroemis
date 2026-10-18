"""Freigaben je Ordner vergeben, ändern, entziehen und verlängern (Phase 2 · Lieferung 1, Abschnitt 4).

Was eine Freigabe ist und wie sie wirkt, steht in rechte.py. Hier stehen die Regeln, wer sie schreiben darf (Bauentwurf
1.6, mit der Nachbesserung vom 18.10.2026 zu Nr. 8), und die Listen für den Reiter „Freigaben“ in „Ordner bearbeiten“
(freigaben.js), „Meine Freigaben“ und die Nutzerverwaltung:

  1  Die Material-Verwaltung (Stufe Verwaltung im Modul Material) vergibt überall, ohne die Grenzen 3–7. Für
     Prüffreigaben gilt auch für sie Nr. 8 – Sachkunde lässt sich nicht verwalten, nur nachweisen.
  2  Wer einen Ordner verwaltet, vergibt dort und darunter – an jedes aktive Konto mit Namen und Zugang zum Modul
     (Stufe Mitglied oder Verwaltung, die gibt die Plattform-Verwaltung in der Nutzerverwaltung), auch aus anderen
     Gliederungen (rechte.waehlbares_konto mit modulzugang).
  3  Was er vergibt oder nach einer Änderung hinterlässt, endet nicht später als sein eigenes Verwalten am Anker
     (Sicht.ende). Unbefristet vergibt nur, wer selbst unbefristet verwaltet.
  4  Eine fremde Zeile ändert oder entzieht er nur, wenn sie schon vorher in diesen Grenzen liegt – ein befristeter
     Verwalter kann einen dauerhaften weder entziehen noch kürzen noch herabsetzen.
  5  Die eigene Zeile nur verkürzen, herabsetzen (verwalten → lesen) oder entziehen – das immer, auch wenn sie länger
     läuft als das eigene Verwalten (Nr. 4 gilt nur für fremde).
  6  Zeilen oberhalb des eigenen Bereichs sieht er als „geerbt“, ohne Notiz, und ändert sie nicht.
  7  Danach hat jede Gliederung im Zweig des Ankers noch einen Verwalter, der mindestens so lange bleibt wie er – sonst
     409 (_verwaltung_danach).
  8  Prüffreigaben nur an qualifizierte Konten (Häkchen, Urkundennummer und Zugang zum Modul). Befristet nur für
     externe Prüfer: Dauerhaft (ohne Ende) darf eine Prüffreigabe sein, wenn das Konto am Anker oder darüber heute ein
     Grundrecht hat – auch eines aus derselben Anfrage (Vorlagen „Prüfer“, „Materialwart und Prüfer“) – oder
     Material-Verwaltung ist (rechte.grundrecht_an, nach dem Schreiben gefragt; sonst 400). Wirken tut sie nur, solange das Grundrecht gilt (rechte.Sicht). Mit Ende
     höchstens 24 Monate – für alle. Nr. 3 gilt auch hier: dauerhaft nur, wer selbst dauerhaft verwaltet.
  9  lesen und verwalten: Enddatum frei, wenn gesetzt nicht in der Vergangenheit.
 10  Die Notiz (200 Zeichen, eine Zeile) sehen nur Verwalter des Ankers und die Material-Verwaltung – ins Journal
     kommt nur „notiz_geaendert“.
 11  Nicht an „Gesperrt“ und „Ausgesondert“ (409); Unsichtbares antwortet 404 (requires_folder).
 12  Ein Konto, das es nicht gibt, das deaktiviert ist oder keinen Namen hat: dieselbe 404. Ein Konto ohne Zugang zum
     Modul: 409 mit Klartext (die Personensuche für Freigaben zeigt es gar nicht erst) – ebenso beim Ändern, wenn die
     Zeile danach weiter reicht (anderes Recht als verwalten → lesen, späteres Ende); kürzen, herabsetzen, die Notiz
     ändern und entziehen gehen immer (_reicht_weiter).
 13  Nach jedem Schreiben rechte.sicht_verwerfen() – die Antwort zeigt schon den neuen Stand.

Journal am Ordner, an dem die Freigabe verankert ist: freigabe_erteilt, freigabe_geaendert, freigabe_entzogen mit
{"freigabe", "konto": {"ref"}, "recht", "bis"} – das Konto nur als pseudonymer Verweis (journal.konto_ref), der Name
dessen, der handelt, steht wie immer in user_name."""
import json
from datetime import date, timedelta

from ... import db
from ...auth import current_user
from .. import services as dienste
from ..models import FREIGABEN, MIGRATION_8
from . import Abgelehnt, auswahl, datum, journal, kennung, text, wahr
from . import rechte
from .bestand import heimat
from .interval import plus_monate

SYSTEMORDNER = "Freigaben gibt es nicht für „Gesperrt“ und „Ausgesondert“ – sie gelten über die Gliederung."
FREIGABE_FEHLT = "Freigabe nicht gefunden."
NICHT_QUALIFIZIERT = ("Prüffreigaben nur an Konten mit Zugang zum Modul und Prüferqualifikation (Häkchen der Verwaltung "
                      "und Urkundennummer im Profil).")
LETZTER_VERWALTER = ("Danach hätte die Gliederung keinen Verwalter mehr, der so lange bleibt wie du – das macht nur die "
                     "Material-Verwaltung.")
EIGENE = "Deine eigene Freigabe kannst du nur verkürzen, herabsetzen oder entziehen."
EIGENE_NEU = "Dir selbst vergibst du keine Freigabe – das macht ein anderer Verwalter oder die Material-Verwaltung."
NICHT_AENDERBAR = ("Diese Freigabe reicht weiter als deine eigene – ändern kann sie nur, wer mindestens so lange "
                   "verwaltet, oder die Material-Verwaltung.")
NUR_VERWALTER = "Freigaben ändert nur, wer den Ordner verwaltet, an dem sie vergeben sind."
PRUEFEN_BIS = "Für die Prüffreigabe bitte „bis“ angeben – ein Enddatum oder null für dauerhaft."
PRUEFEN_DAUERHAFT = ("Dauerhaft gibt es eine Prüffreigabe nur zusammen mit lesen oder verwalten an diesem Ordner oder "
                     "darüber. Für externe Prüfer (nur prüfen) bitte ein Enddatum setzen – höchstens 24 Monate.")
VERGANGEN = "Das Enddatum liegt in der Vergangenheit."
KEIN_RECHT = "Bitte ein Recht wählen – Grundrecht, Prüffreigabe oder beides."
SUCHE_KURZ = "Bitte mindestens 3 Zeichen des Namens eingeben."
NUR_VERWALTUNG = "Nur für die Plattform-Verwaltung."
# Warum eine Freigabe nicht wirkt (Feld „wirkt_nicht“ der Listen) – in dieser Reihenfolge geprüft.
DEAKTIVIERT = "Konto deaktiviert"
OHNE_NAMEN = "Konto ohne Namen"
OHNE_ZUGANG = "kein Zugang zum Modul Material"
OHNE_QUALI = "Qualifikation fehlt"
OHNE_GRUNDRECHT_DORT = "dauerhaft nur mit lesen oder verwalten"
# Wofür die Personensuche sucht: Freigabe (nur Konten mit Zugang zum Modul) oder Personenzuordnung (alle mit Namen).
ZWECKE = ("freigabe", "zuordnung")

NOTIZ_MAX = 200
PRUEFEN_MONATE = 24                 # längste Prüffreigabe (1.6 Nr. 8)
ABLAUF_TAGE = 30                    # „läuft in n Tagen ab“
VERLAENGERN_TAGE = 90               # so lange abgelaufene Prüffreigaben nimmt „Alle verlängern“ noch mit
MEINE_TAGE = 365                    # so lange zeigt „Meine Freigaben“ abgelaufene
SUCHE_MIN, SUCHE_MAX = 3, 20
# Wer eine Freigabe ohne Konto (granted_by NULL) vergeben hat – Name im Journal → Anzeige. Sonst war es ein Konto, das
# es nicht mehr gibt. „Beispielbestand“: scripts/material_beispielbestand.py (nur dev).
SYSTEM = {MIGRATION_8: "Migration", "Demodaten": "Demodaten", "Beispielbestand": "Beispielbestand"}
RECHT_TEXT = {"lesen": "lesen", "verwalten": "verwalten", "pruefen": "prüfen"}


# --- Kleinigkeiten ---------------------------------------------------------------------------------------------

def _heute():
    return dienste.heute()


def _tag(iso):
    return date.fromisoformat(iso).strftime("%d.%m.%Y")


def _spaeter(a, b):
    """Endet a später als b? Ohne Enddatum (None) ist am spätesten."""
    if a is None:
        return b is not None
    return b is not None and a > b


def pruefen_max(tag=None):
    """Spätestes Ende einer neuen Prüffreigabe: heute + 24 Monate."""
    return plus_monate(tag or _heute(), PRUEFEN_MONATE).isoformat()


def vorgabe_bis(tag=None):
    """Vorgabe im Dialog für „bis“: 31.12. des Folgejahres, höchstens 24 Monate."""
    t = tag or _heute()
    return min(f"{t.year + 1}-12-31", pruefen_max(t))


def _bis(wert, recht):
    """Enddatum einer Freigabe aus der Anfrage (1.6 Nr. 8 und 9), None heißt dauerhaft. Bei pruefen mit Ende höchstens
    24 Monate – ob sie ohne Ende sein darf, hängt am Grundrecht und wird nach dem Schreiben geprüft (_schreiben).
    Gesetzt nie in der Vergangenheit."""
    bis = datum(wert, "bis")
    if recht == "pruefen" and bis is not None and bis > pruefen_max():
        raise Abgelehnt(f"Eine Prüffreigabe läuft höchstens {PRUEFEN_MONATE} Monate – also bis spätestens "
                        f"{_tag(pruefen_max())} – oder dauerhaft, wo die Person auch lesen oder verwalten hat.")
    if bis is not None and bis < _heute().isoformat():
        raise Abgelehnt(VERGANGEN)
    return bis


def _notiz(d):
    return text(d, "notiz", "Notiz", n=NOTIZ_MAX)


def _ordner_alle():
    """Alle Ordner (eine Abfrage) – für Pfade, Zweige und Ketten in dieser Anfrage."""
    return {o["id"]: o for o in db.query("SELECT id, parent_id, name, kind, system_kind FROM mat_folder")}


def _kette(fid, ordner):
    """fid und seine Oberordner, von unten nach oben (ein Zyklus hält an)."""
    out = []
    while fid is not None and fid in ordner and fid not in out:
        out.append(fid)
        fid = ordner[fid]["parent_id"]
    return out


def _zweig(fid, ordner):
    """fid und alles darunter."""
    kinder = {}
    for o in ordner.values():
        kinder.setdefault(o["parent_id"], []).append(o["id"])
    gesehen, offen = set(), [fid]
    while offen:
        x = offen.pop()
        if x not in gesehen:
            gesehen.add(x)
            offen.extend(kinder.get(x, ()))
    return gesehen


def _pfad(fid, ordner):
    return " / ".join(ordner[x]["name"] for x in reversed(_kette(fid, ordner)))


def _gliederung(o):
    return o["kind"] == "gliederung" and not o["system_kind"]


def _konto(uid):
    return db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)


def _name(name):
    """Ein Kontoname für die Listen – ohne Namen „(Konto ohne Namen)“, nie die E-Mail. So entstehen Zeilen etwa aus der
    Migration (Schritt 8 vergibt Freigaben unabhängig vom Namen); wirken tun sie erst mit Namen."""
    return (name or "").strip() or dienste.OHNE_NAMEN


def _aktiv(u):
    return bool(u["active"]) and (u["status"] or "active") == "active"


def _ende(s, fid):
    """Das eigene wirksame Ende von verwalten an fid (None = unbefristet, auch für die Verwaltung)."""
    return s.ende("verwalten", fid)


def zeile(gid):
    return db.query("SELECT * FROM mat_folder_grant WHERE id = ?", (gid,), one=True)


# --- Regeln (1.6) ------------------------------------------------------------------------------------------------

def _reicht_weiter(alt, neu):
    """Gibt die Änderung dem Konto mehr als vorher? Eine neue Zeile, ein anderes Recht (außer verwalten → lesen) oder
    ein späteres Ende (ohne Ende ist am spätesten). Kürzen, Herabsetzen, die Notiz und Entziehen (neu None) nicht."""
    if neu is None:
        return False
    if alt is None:
        return True
    return _spaeter(neu["valid_until"], alt["valid_until"]) or (
        neu["permission"] != alt["permission"] and (alt["permission"], neu["permission"]) != ("verwalten", "lesen"))


def _regeln(s, ich, anker, alt, neu, konto):
    """Prüft eine Änderung an einer Zeile – vorher alt (None beim Anlegen), nachher neu (None beim Entziehen) – gegen
    1.6 Nr. 3, 4, 5, 8 und 12. Der Anker ist sichtbar und wird vom Handelnden verwaltet (Route); Nr. 7 prüft der Aufrufer
    nach dem Schreiben."""
    if not s.alles:
        ende = _ende(s, anker)
        # Nr. 4 nur für fremde Zeilen – die eigene darf man immer verkürzen und entziehen (Nr. 5), auch wenn sie
        # länger läuft als das eigene Verwalten; was danach bleibt, prüft Nr. 3.
        if alt is not None and alt["user_id"] != ich["id"] and _spaeter(alt["valid_until"], ende):
            raise Abgelehnt(NICHT_AENDERBAR, 403)
        if neu is not None and _spaeter(neu["valid_until"], ende):
            if neu["valid_until"] is None:
                raise Abgelehnt("Dauerhaft vergibt nur, wer selbst dauerhaft verwaltet – setze ein Enddatum (spätestens "
                                f"{_tag(ende)}).", 403)
            raise Abgelehnt(f"Länger als deine eigene Verwalterfreigabe hier (bis {_tag(ende)}) vergibst du nichts.", 403)
        if (alt or neu)["user_id"] == ich["id"]:
            if alt is None:
                raise Abgelehnt(EIGENE_NEU, 403)
            if _reicht_weiter(alt, neu):
                raise Abgelehnt(EIGENE, 403)
    # Nr. 12: Mehr bekommt nur ein Konto mit Zugang zum Modul – beim Ändern wie beim Erteilen (waehlbares_konto). Sonst
    # ließe sich eine ruhende Zeile eines Kontos ohne Stufe hochstufen und wirkte, sobald es die Stufe bekommt.
    if _reicht_weiter(alt, neu) and not rechte.zugang(konto):
        raise Abgelehnt(rechte.KONTO_OHNE_ZUGANG, 409)
    # Nr. 8: Eine Prüffreigabe entsteht oder reicht weiter – das Konto muss qualifiziert sein (mit Zugang zum Modul).
    # Kürzen geht immer.
    if neu is not None and neu["permission"] == "pruefen" and (
            alt is None or alt["permission"] != "pruefen" or _spaeter(neu["valid_until"], alt["valid_until"])):
        if not rechte.qualifiziert(konto):
            raise Abgelehnt(NICHT_QUALIFIZIERT, 409)


def _spur(gid, z, notiz=False, grund=None):
    """Was ins Journal kommt: Kennung, pseudonymer Kontoverweis, Recht, Ende – nie die Notiz."""
    out = {"freigabe": gid, "konto": journal.konto_ref(z["user_id"]), "recht": z["permission"], "bis": z["valid_until"]}
    if notiz:
        out["notiz_geaendert"] = True
    if grund:
        out["grund"] = grund
    return out


def _dauerhaft_pruefen(alt, neu, anker, konto):
    """1.6 Nr. 8: Entsteht eine Prüffreigabe ohne Ende (neu, aus einer befristeten oder aus einem Grundrecht), braucht
    das Konto am Anker oder darüber ein Grundrecht – nach dem Schreiben gefragt, noch in der Transaktion: So zählt ein
    Grundrecht aus derselben Anfrage mit, und eines, das die Änderung selbst wegnimmt, nicht mehr. Eine schon dauerhafte
    Zeile bleibt änderbar (Notiz), auch wenn sie gerade nicht wirkt."""
    if neu is None or neu["permission"] != "pruefen" or neu["valid_until"] is not None:
        return
    if alt is not None and alt["permission"] == "pruefen" and alt["valid_until"] is None:
        return
    if not rechte.grundrecht_an(konto, anker):
        raise Abgelehnt(PRUEFEN_DAUERHAFT)


def _schreiben(s, ich, anker, alt, neu, konto, grund=None):
    """Eine Zeile anlegen (alt None), ändern oder entziehen (neu None) – nach den Regeln, mit Journal. Liefert die
    Kennung. Läuft in der Transaktion des Aufrufers."""
    _regeln(s, ich, anker, alt, neu, konto)
    jetzt = db.now()
    if alt is None:
        gid = db.execute("INSERT INTO mat_folder_grant (folder_id, user_id, permission, valid_until, granted_by, "
                         "created_at, note, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                         (anker, neu["user_id"], neu["permission"], neu["valid_until"], ich["id"], jetzt, neu["note"],
                          jetzt))
        _dauerhaft_pruefen(alt, neu, anker, konto)
        journal.eintragen("folder", anker, "freigabe_erteilt", None, _spur(gid, neu, bool(neu["note"]), grund))
        return gid
    if neu is None:
        db.execute("DELETE FROM mat_folder_grant WHERE id = ?", (alt["id"],))
        journal.eintragen("folder", anker, "freigabe_entzogen", _spur(alt["id"], alt), None)
        return alt["id"]
    if all(neu[k] == alt[k] for k in ("permission", "valid_until", "note")):
        return alt["id"]
    db.execute("UPDATE mat_folder_grant SET permission = ?, valid_until = ?, note = ?, updated_at = ? WHERE id = ?",
               (neu["permission"], neu["valid_until"], neu["note"], jetzt, alt["id"]))
    _dauerhaft_pruefen(alt, neu, anker, konto)
    journal.eintragen("folder", anker, "freigabe_geaendert", _spur(alt["id"], alt),
                      _spur(alt["id"], neu, neu["note"] != alt["note"], grund))
    return alt["id"]


def _verwaltung_vorher(s, anker, ordner, noetig=True):
    """Für Nr. 7: je Gliederung im Zweig des Ankers, die gerade einen Verwalter hat, das eigene Ende dort. Die
    Verwaltung ist ausgenommen (Nr. 1); ohne verwalten vorher oder nachher (noetig) ändert sich nichts daran."""
    if s.alles or not noetig:
        return {}
    return {x: _ende(s, x) for x in _zweig(anker, ordner)
            if _gliederung(ordner[x]) and s.darf("verwalten", x) and rechte.verwalter_von(x)}


def _verwaltung_danach(vorher, ohne_freigabe=None):
    """Nach dem Schreiben (noch in der Transaktion): Jede Gliederung aus vorher hat einen Verwalter, dessen Ende nicht
    vor dem bisherigen eigenen liegt – sonst 409, und die Transaktion rollt zurück. ohne_freigabe: vorab rechnen, als
    wäre diese Zeile schon entzogen (_entziehbar)."""
    for gl, ende in vorher.items():
        if not any(not _spaeter(ende, v["ende"]) for v in rechte.verwalter_von(gl, ohne_freigabe)):
            raise Abgelehnt(LETZTER_VERWALTER, 409)


def _entziehbar(s, r, ordner, aenderbar):
    """Ob „Entziehen“ gelingt: Die Zeile ist änderbar, und danach bleibt jede Gliederung im Zweig des Ankers so lange
    verwaltet wie bisher (Nr. 7, vorab gerechnet). Scheitern kann das nur an der eigenen verwalten-Zeile: Bei einer
    fremden bleibt der Handelnde selbst mit seinem Ende Verwalter jeder Gliederung, die er dort verwaltet."""
    if not aenderbar or s.alles or r["user_id"] != s.uid or r["permission"] != "verwalten":
        return aenderbar
    try:
        _verwaltung_danach(_verwaltung_vorher(s, r["folder_id"], ordner), ohne_freigabe=r["id"])
    except Abgelehnt:
        return False
    return True


def _anker_pruefen(fid, ordner):
    o = ordner.get(fid)
    if not o:
        raise Abgelehnt(rechte.ORDNER_FEHLT, 404)
    if o["system_kind"]:
        raise Abgelehnt(SYSTEMORDNER, 409)
    return o


# --- Schreiben ---------------------------------------------------------------------------------------------------

def erteilen(fid, d):
    """POST /ordner/<fid>/freigaben: bis zu zwei Zeilen am Anker fid in EINER Transaktion – ein Grundrecht (lesen oder
    verwalten, Ende frei) und eine Prüffreigabe (mit Ende, oder dauerhaft, wo das Konto ein Grundrecht hat – auch das
    aus dieser Anfrage, es wird zuerst geschrieben). So entstehen die Vorlagen des Reiters in einem Schritt; scheitert
    die zweite Zeile, gibt es auch die erste nicht. Vorhandene Zeilen derselben Art werden geändert. grundrecht null
    lässt das Grundrecht unberührt. Die Prüffreigabe: mit „pruefen“ true gewünscht, pruefen_bis null, "" oder fehlend
    heißt dann dauerhaft; ohne „pruefen“ wie bisher – pruefen_bis null (oder fehlend) lässt sie unberührt, "" heißt
    „ohne Ende“. Liefert die Kennungen der geschriebenen Zeilen."""
    ich, s = current_user(), rechte.sicht()
    ordner = _ordner_alle()
    _anker_pruefen(fid, ordner)
    konto = rechte.waehlbares_konto(d.get("user_id"), modulzugang=True)
    grund = auswahl(d.get("grundrecht"), rechte.GRUNDRECHTE, "Grundrecht", leer_erlaubt=True)
    grund_bis = _bis(d.get("grund_bis"), grund) if grund else None
    mit_pruefen = wahr(d, "pruefen", "Prüffreigabe") if "pruefen" in d else d.get("pruefen_bis") is not None
    pruefen_bis = _bis(d.get("pruefen_bis"), "pruefen") if mit_pruefen else None
    if not grund and not mit_pruefen:
        raise Abgelehnt(KEIN_RECHT)
    notiz = _notiz(d) if "notiz" in d else None
    wunsch = []
    if grund:
        wunsch.append((rechte.GRUNDRECHTE, grund, grund_bis))
    if mit_pruefen:
        wunsch.append((("pruefen",), "pruefen", pruefen_bis))
    ids = []
    with db.transaction(sofort=True):
        # Ein Grundrecht kann ein vorhandenes verwalten herabsetzen – dann gilt Nr. 7.
        vorher = _verwaltung_vorher(s, fid, ordner, noetig=bool(grund))
        for arten, recht, bis in wunsch:
            alt = db.query(f"SELECT * FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission IN "
                           f"({','.join('?' * len(arten))})", (fid, konto["id"], *arten), one=True)
            neu = {"user_id": konto["id"], "permission": recht, "valid_until": bis,
                   "note": notiz if notiz is not None else (alt["note"] if alt else "")}
            ids.append(_schreiben(s, ich, fid, alt, neu, konto))
        _verwaltung_danach(vorher)
    rechte.sicht_verwerfen()
    return ids


def aendern(gid, d):
    """PUT /freigaben/<gid>: Recht, Ende und Notiz einer Zeile. „bis“: null heißt unbefristet – bei einer Prüffreigabe
    nur mit Grundrecht (Nr. 8). Aus einem Grundrecht wird eine Prüffreigabe und umgekehrt nur, wenn es die andere Art
    dort noch nicht gibt (409); zur Prüffreigabe nur mit ausdrücklichem „bis“."""
    ich, s = current_user(), rechte.sicht()
    alt = zeile(gid)
    neu = dict(alt)
    if "recht" in d:
        neu["permission"] = auswahl(d.get("recht"), FREIGABEN, "Recht")
    if "bis" in d:
        neu["valid_until"] = _bis(d.get("bis"), neu["permission"])
    elif neu["permission"] == "pruefen" and alt["permission"] != "pruefen":
        raise Abgelehnt(PRUEFEN_BIS)
    if "notiz" in d:
        neu["note"] = _notiz(d)
    if (neu["permission"] == "pruefen") != (alt["permission"] == "pruefen"):
        arten = ("pruefen",) if neu["permission"] == "pruefen" else rechte.GRUNDRECHTE
        if db.query(f"SELECT 1 FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND id <> ? AND permission IN "
                    f"({','.join('?' * len(arten))})", (alt["folder_id"], alt["user_id"], gid, *arten), one=True):
            raise Abgelehnt("Für dieses Konto gibt es an diesem Ordner schon " + (
                "eine Prüffreigabe" if neu["permission"] == "pruefen" else "ein Grundrecht") + " – ändere diese Zeile.",
                409)
    with db.transaction(sofort=True):
        vorher = _verwaltung_vorher(s, alt["folder_id"], _ordner_alle(), noetig=alt["permission"] == "verwalten")
        _schreiben(s, ich, alt["folder_id"], alt, neu, _konto(alt["user_id"]))
        _verwaltung_danach(vorher)
    rechte.sicht_verwerfen()
    return gid


def entziehen(gid):
    """DELETE /freigaben/<gid>. Liefert die Zahl offener Prüfungen des Kontos im Zweig des Ankers, die es danach nicht
    mehr fortsetzen darf – die gibt ein Verwalter unter Material → Prüfungen → Offene Prüfungen frei. Das gilt auch für
    ein Grundrecht: An ihm kann eine dauerhafte Prüffreigabe hängen, die ohne es nicht mehr wirkt."""
    ich, s = current_user(), rechte.sicht()
    alt = zeile(gid)
    ordner = _ordner_alle()
    with db.transaction(sofort=True):
        vorher = _verwaltung_vorher(s, alt["folder_id"], ordner, noetig=alt["permission"] == "verwalten")
        _schreiben(s, ich, alt["folder_id"], alt, None, _konto(alt["user_id"]))
        _verwaltung_danach(vorher)
    rechte.sicht_verwerfen()
    konto = _konto(alt["user_id"])
    zweig = _zweig(alt["folder_id"], ordner)
    offen = db.query("SELECT i.* FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE x.inspector_user_id = ? "
                     "AND x.completed_at IS NULL", (alt["user_id"],))
    return sum(1 for i in offen if heimat(i) in zweig and not rechte.darf("pruefen", heimat(i), konto))


def verlaengern(fid, d):
    """POST /ordner/<fid>/freigaben/verlaengern: alle befristeten Prüffreigaben an fid oder darunter, die noch gelten
    oder seit höchstens 90 Tagen abgelaufen sind, auf „bis“ – soweit der Handelnde sie nach 1.6 ändern darf, das Konto
    aktiv ist, Zugang zum Modul hat und qualifiziert ist und die Freigabe dadurch länger wird. Dauerhafte laufen nicht ab und kommen gar nicht
    erst in die Auswahl (auch nicht unter „übersprungen“). Je Zeile ein Journaleintrag; was übersprungen wurde, steht
    mit Grund in der Antwort."""
    ich, s = current_user(), rechte.sicht()
    ordner = _ordner_alle()
    _anker_pruefen(fid, ordner)
    bis = _bis(d.get("bis"), "pruefen")
    if bis is None:
        raise Abgelehnt("Bitte ein Enddatum angeben – verlängert werden nur befristete Prüffreigaben.")
    if not s.alles and _spaeter(bis, _ende(s, fid)):
        raise Abgelehnt(f"Länger als deine eigene Verwalterfreigabe hier (bis {_tag(_ende(s, fid))}) verlängerst du "
                        "nichts.", 403)
    zweig = _zweig(fid, ordner)
    ab = (_heute() - timedelta(days=VERLAENGERN_TAGE)).isoformat()
    rows = db.query("SELECT g.*, u.name AS konto_name FROM mat_folder_grant g JOIN users u ON u.id = g.user_id "
                    "WHERE g.permission = 'pruefen' AND g.valid_until IS NOT NULL AND g.valid_until >= ? "
                    "AND g.folder_id IN (SELECT value FROM json_each(?)) ORDER BY u.name COLLATE NOCASE, g.id",
                    (ab, json.dumps(sorted(zweig))))
    verlaengert, uebersprungen = 0, []
    with db.transaction(sofort=True):
        for r in rows:
            konto = _konto(r["user_id"])
            grund = None
            if not _aktiv(konto):
                grund = DEAKTIVIERT
            elif not rechte.zugang(konto):
                grund = OHNE_NAMEN if not (konto["name"] or "").strip() else OHNE_ZUGANG
            elif not rechte.qualifiziert(konto):
                grund = OHNE_QUALI
            elif not s.alles and r["user_id"] == ich["id"]:
                grund = "eigene Freigabe"
            elif not s.alles and _spaeter(r["valid_until"], _ende(s, r["folder_id"])):
                grund = "reicht weiter als deine eigene Freigabe"
            elif not _spaeter(bis, r["valid_until"]):
                grund = f"läuft schon bis {_tag(r['valid_until'])}"
            if grund:
                uebersprungen.append({"konto": _name(r["konto_name"]), "ordner": _pfad(r["folder_id"], ordner),
                                      "grund": grund})
                continue
            _schreiben(s, ich, r["folder_id"], r, dict(r, valid_until=bis), konto, grund="alle verlängert")
            verlaengert += 1
    rechte.sicht_verwerfen()
    return {"verlaengert": verlaengert, "uebersprungen": uebersprungen}


# --- Lesen -------------------------------------------------------------------------------------------------------

_ZEILEN_SQL = ("SELECT g.*, u.name AS u_name, u.gliederung AS u_gliederung, u.active AS u_active, u.status AS u_status, "
               "u.mat_pruefer AS u_pruefer, u.urkundennummer AS u_urkunde, u.recht_verwaltung AS u_verwaltung, "
               "u.recht_material AS u_stufe, "
               "v.name AS von_name FROM mat_folder_grant g JOIN users u ON u.id = g.user_id "
               "LEFT JOIN users v ON v.id = g.granted_by ")


def _grundlage(rows, verwaltung=None):
    """Was neben einer Zeile für „grundrecht_dort“, „wirkt“ und „traegt_pruefen“ zählt (eine Abfrage für alle Konten
    der Liste): je Konto die gültigen Grundrechte {Kennung: Ordner}, die Anker der dauerhaften Prüffreigaben und ob es
    die Stufe Verwaltung im Modul Material hat (Material-Verwaltung – die hat das Grundrecht überall, wie
    rechte.grundrecht_an). verwaltung: diese Konten sind es (sonst aus u_stufe und u_verwaltung der Zeilen)."""
    uids = sorted({r["user_id"] for r in rows})
    if verwaltung is None:
        verwaltung = {r["user_id"] for r in rows if _stufe(r) >= 2}
    out = {uid: {"grund": {}, "dauer": [], "alles": uid in verwaltung} for uid in uids}
    if uids:
        for x in db.query("SELECT id, user_id, folder_id, permission FROM mat_folder_grant WHERE user_id IN "
                          "(SELECT value FROM json_each(?)) AND ((permission IN ('lesen', 'verwalten') AND "
                          "(valid_until IS NULL OR valid_until >= ?)) "
                          "OR (permission = 'pruefen' AND valid_until IS NULL))",
                          (json.dumps(uids), _heute().isoformat())):
            if x["permission"] == "pruefen":
                out[x["user_id"]]["dauer"].append(x["folder_id"])
            else:
                out[x["user_id"]]["grund"][x["id"]] = x["folder_id"]
    return out


def _am_grundrecht(r, g, ordner):
    """(grundrecht_dort, traegt_pruefen) einer Zeile r mit der Grundlage g ihres Kontos (_grundlage):
    grundrecht_dort – das Konto hat am Anker oder darüber heute ein Grundrecht (oder ist Material-Verwaltung): Nur dann
    darf eine Prüffreigabe dort dauerhaft sein und wirkt es eine dauerhafte. traegt_pruefen – bei einem gültigen
    Grundrecht: an wie vielen dauerhaften Prüffreigaben des Kontos es allein hängt (ohne es wirkten sie nicht mehr) – so
    sagen Entziehen und Kürzen es vorher."""
    oben = set(_kette(r["folder_id"], ordner))
    dort = g["alles"] or any(f in oben for f in g["grund"].values())
    traegt = 0
    if r["permission"] != "pruefen" and r["id"] in g["grund"] and not g["alles"]:
        andere = [f for gid, f in g["grund"].items() if gid != r["id"]]
        for p in g["dauer"]:
            kette = set(_kette(p, ordner))
            if r["folder_id"] in kette and not any(f in kette for f in andere):
                traegt += 1
    return dort, traegt


def _von_system(rows):
    """Wer Zeilen ohne vergebendes Konto vergeben hat (Migration, Demodaten) – aus dem Journal, eine Abfrage."""
    ohne = sorted({r["id"] for r in rows if r["granted_by"] is None})
    if not ohne:
        return {}
    out = {}
    for e in db.query("SELECT user_name, json_extract(after_json, '$.freigabe') AS f FROM mat_audit WHERE entity = "
                      "'folder' AND action = 'freigabe_erteilt' AND user_id IS NULL AND json_extract(after_json, "
                      "'$.freigabe') IN (SELECT value FROM json_each(?)) ORDER BY id", (json.dumps(ohne),)):
        if e["user_name"] in SYSTEM:
            out[e["f"]] = SYSTEM[e["user_name"]]
    return out


def _stufe(r):
    """Stufe im Modul Material eines Kontos aus einer Zeile von _ZEILEN_SQL (die Plattform-Verwaltung hat 2)."""
    return 2 if int(r["u_verwaltung"] or 0) >= 2 else int(r["u_stufe"] or 0)


def _wirkt_nicht(gueltig, aktiv, mit_namen, zugang, quali_fehlt, pruefen_wirkt):
    """Warum eine gültige Freigabe nicht wirkt – als Text für die Listen, in fester Reihenfolge – oder None (sie wirkt,
    oder sie ist abgelaufen; das sagen „gueltig“ und „bis“)."""
    if not gueltig:
        return None
    for fehlt, grund in ((not aktiv, DEAKTIVIERT), (not mit_namen, OHNE_NAMEN), (not zugang, OHNE_ZUGANG),
                         (quali_fehlt, OHNE_QUALI), (not pruefen_wirkt, OHNE_GRUNDRECHT_DORT)):
        if fehlt:
            return grund
    return None


def _eintrag(r, ordner, s, system, notiz, grundlage):
    """Eine Zeile für die Listen (4.1). notiz: ob die Notiz mitkommt (V am Anker oder Material-Verwaltung, nie
    geerbt); grundlage: _grundlage der Liste. Ohne Zugang zum Modul (Stufe und Name) wirkt keine Freigabe; eine
    dauerhafte Prüffreigabe ohne Grundrecht am Anker auch nicht. Warum nicht, sagt „wirkt_nicht“."""
    heute = _heute()
    mit_namen = bool((r["u_name"] or "").strip())
    zugang = mit_namen and _stufe(r) >= 1
    qualifiziert = zugang and rechte.ist_pruefer({"mat_pruefer": r["u_pruefer"], "urkundennummer": r["u_urkunde"]})
    aktiv = bool(r["u_active"]) and (r["u_status"] or "active") == "active"
    gueltig = rechte.gueltig(r["valid_until"])
    tage = (date.fromisoformat(r["valid_until"]) - heute).days if gueltig and r["valid_until"] else None
    anker = r["folder_id"]
    darf_anker = s.alles or s.darf("verwalten", anker)
    dort, traegt = _am_grundrecht(r, grundlage[r["user_id"]], ordner)
    pruefen_wirkt = r["permission"] != "pruefen" or (qualifiziert and (r["valid_until"] is not None or dort))
    out = {"id": r["id"], "ordner": {"id": anker, "pfad": _pfad(anker, ordner)},
           "konto": {"id": r["user_id"], "name": _name(r["u_name"]), "gliederung": r["u_gliederung"], "aktiv": aktiv,
                     "haekchen": bool(r["u_pruefer"]), "qualifiziert": qualifiziert, "zugang": zugang},
           "recht": r["permission"], "bis": r["valid_until"], "gueltig": gueltig,
           "wirkt": gueltig and aktiv and zugang and pruefen_wirkt,
           "wirkt_nicht": _wirkt_nicht(gueltig, aktiv, mit_namen, zugang,
                                       r["permission"] == "pruefen" and not qualifiziert, pruefen_wirkt),
           "grundrecht_dort": dort, "traegt_pruefen": traegt,
           "laeuft_ab_in_tagen": tage if tage is not None and tage <= ABLAUF_TAGE else None,
           "vergeben_von": _name(r["von_name"]) if r["granted_by"] is not None
           else system.get(r["id"], "(gelöschtes Konto)"),
           "seit": r["created_at"], "eigen": r["user_id"] == s.uid,
           "aenderbar": bool(s.alles or (darf_anker and (r["user_id"] == s.uid
                                                         or not _spaeter(r["valid_until"], _ende(s, anker)))))}
    out["entziehbar"] = _entziehbar(s, r, ordner, out["aenderbar"])
    if notiz and darf_anker:
        out["notiz"] = r["note"] or ""
    return out


def _sortiert(rows, ordner):
    return sorted(rows, key=lambda r: (len(_kette(r["folder_id"], ordner)), _pfad(r["folder_id"], ordner).casefold(),
                                       (r["u_name"] or "").casefold(), r["permission"], r["id"]))


def _verlauf(fid):
    """Die Journaleinträge freigabe_* dieses Ordners, neueste zuerst – seit seiner letzten Löschung (eine Kennung kann
    wiederkommen). Konten stehen mit ihrem heutigen Namen da (journal.konto_namen, eine Abfrage für alle), der Verweis
    selbst geht nicht hinaus."""
    ab = db.query("SELECT MAX(id) AS m FROM mat_audit WHERE entity = 'folder' AND entity_id = ? AND action = 'geloescht'",
                  (fid,), one=True)["m"] or 0
    marken = ",".join("?" * len(rechte.FREIGABE_AKTIONEN))
    eintraege = []
    for e in db.query(f"SELECT * FROM mat_audit WHERE entity = 'folder' AND entity_id = ? AND id > ? AND action IN "
                      f"({marken}) ORDER BY id DESC LIMIT 200", (fid, ab, *rechte.FREIGABE_AKTIONEN)):
        vorher = json.loads(e["before_json"]) if e["before_json"] else {}
        nachher = json.loads(e["after_json"]) if e["after_json"] else {}
        eintraege.append((e, vorher, nachher, ((nachher or vorher).get("konto") or {}).get("ref")))
    namen = journal.konto_namen(ref for *_, ref in eintraege)
    out = []
    for e, vorher, nachher, ref in eintraege:
        stand = nachher or vorher
        out.append({"id": e["id"], "zeit": e["created_at"], "wer": e["user_name"], "aktion": e["action"],
                    "konto": namen.get(ref, "(gelöschtes Konto)"),
                    "recht": stand.get("recht"), "bis": stand.get("bis"),
                    "recht_vorher": vorher.get("recht") if nachher and vorher else None,
                    "bis_vorher": vorher.get("bis") if nachher and vorher else None,
                    "notiz_geaendert": bool(nachher.get("notiz_geaendert")), "grund": stand.get("grund")})
    return out


def liste(fid):
    """GET /ordner/<fid>/freigaben (V am Ordner): die Freigaben hier („direkt“), darüber („geerbt“, ohne Notiz) und
    darunter („unten“), die Anker zur Auswahl (fid und die Oberordner, die der Handelnde verwaltet – mit seinem Ende
    dort), fid und seine Oberordner von unten nach oben („kette“ – damit „dauerhaft“ beim Prüfen nur erscheint, wo die
    Person schon ein Grundrecht hat), den Verlauf und die Zahl der Freigaben im Zweig, die in den nächsten 30 Tagen
    ablaufen (dauerhafte laufen nicht ab)."""
    s = rechte.sicht()
    ordner = _ordner_alle()
    _anker_pruefen(fid, ordner)
    kette = _kette(fid, ordner)
    zweig = _zweig(fid, ordner)
    rows = db.query(_ZEILEN_SQL + "WHERE g.folder_id IN (SELECT value FROM json_each(?))",
                    (json.dumps(sorted(set(kette) | zweig)),))
    system = _von_system(rows)
    grundlage = _grundlage(rows)
    direkt = [r for r in rows if r["folder_id"] == fid]
    geerbt = [r for r in rows if r["folder_id"] != fid and r["folder_id"] in kette]
    unten = [r for r in rows if r["folder_id"] != fid and r["folder_id"] in zweig]
    anker = [{"id": x, "pfad": _pfad(x, ordner), "gliederung": _gliederung(ordner[x]), "ende": _ende(s, x)}
             for x in kette if not ordner[x]["system_kind"] and s.darf("verwalten", x)]
    # Vorgabe: die nächste Gliederung, wenn man sie verwaltet, sonst der Ordner selbst.
    naechste = next((x for x in kette if _gliederung(ordner[x])), None)
    vorgabe = naechste if any(a["id"] == naechste for a in anker) else fid
    eintraege = {"direkt": [_eintrag(r, ordner, s, system, True, grundlage) for r in _sortiert(direkt, ordner)],
                 "geerbt": [_eintrag(r, ordner, s, system, False, grundlage) for r in _sortiert(geerbt, ordner)],
                 "unten": [_eintrag(r, ordner, s, system, True, grundlage) for r in _sortiert(unten, ordner)]}
    o = ordner[fid]
    return dict(eintraege, ordner={"id": fid, "name": o["name"], "pfad": _pfad(fid, ordner),
                                   "gliederung": _gliederung(o)},
                anker_wahl=anker, anker_vorgabe=vorgabe, kette=kette, verlauf=_verlauf(fid),
                laeuft_ab=sum(1 for e in eintraege["direkt"] + eintraege["unten"] if e["laeuft_ab_in_tagen"] is not None),
                grenzen={"heute": _heute().isoformat(), "pruefen_max": pruefen_max(), "vorgabe_bis": vorgabe_bis()},
                alles=s.alles)


def eintrag(gid):
    """Eine Zeile nach dem Ändern – wie in der Liste ihres Ankers (mit Notiz, wenn der Handelnde ihn verwaltet)."""
    rows = db.query(_ZEILEN_SQL + "WHERE g.id = ?", (gid,))
    if not rows:
        return None
    return _eintrag(rows[0], _ordner_alle(), rechte.sicht(), _von_system(rows), True, _grundlage(rows))


def des_kontos(uid):
    """GET /freigaben?user_id= (nur die Verwaltung): alle Freigaben eines Kontos, auch abgelaufene, mit Notiz – für den
    Dialog „Bearbeiten“ der Nutzerverwaltung."""
    u = _konto(kennung(uid, "Konto"))
    if not u:
        raise Abgelehnt(rechte.KONTO_FEHLT, 404)
    ordner = _ordner_alle()
    rows = db.query(_ZEILEN_SQL + "WHERE g.user_id = ?", (u["id"],))
    system = _von_system(rows)
    grundlage = _grundlage(rows)
    s = rechte.sicht()
    return [_eintrag(r, ordner, s, system, True, grundlage) for r in _sortiert(rows, ordner)]


def meine(user):
    """GET /freigaben/meine (jeder Angemeldete, auch ohne Modulzugang): die eigenen Freigaben – gültige und in den
    letzten 365 Tagen abgelaufene – mit Pfad, Zustand und bis zu drei Verwaltern des Ankers (wer verlängern kann).
    Ohne Notiz. Ohne Zugang zum Modul (Stufe und Name) wirkt keine; eine dauerhafte Prüffreigabe läuft nicht ab und
    wirkt ohne Grundrecht dort nicht (grundrecht_dort). Warum eine nicht wirkt, sagt „wirkt_nicht“ wie in den Listen;
    „alles“: das Konto ist Material-Verwaltung."""
    heute = _heute()
    ab = (heute - timedelta(days=MEINE_TAGE)).isoformat()
    rows = db.query("SELECT * FROM mat_folder_grant WHERE user_id = ? AND (valid_until IS NULL OR valid_until >= ?) "
                    "ORDER BY id", (user["id"], ab))
    ordner = _ordner_alle()
    zugang = rechte.zugang(user)
    qualifiziert = rechte.qualifiziert(user)
    mit_namen = bool((user["name"] or "").strip())
    grundlage = _grundlage(rows, {user["id"]} if rechte.grundrecht_ueberall(user) else set())
    out = []
    for r in _sortiert([dict(r, u_name=user["name"]) for r in rows], ordner):
        gueltig = rechte.gueltig(r["valid_until"])
        tage = (date.fromisoformat(r["valid_until"]) - heute).days if gueltig and r["valid_until"] else None
        dort, _ = _am_grundrecht(r, grundlage[user["id"]], ordner)
        pruefen_wirkt = r["permission"] != "pruefen" or (qualifiziert and (r["valid_until"] is not None or dort))
        out.append({"id": r["id"], "ordner": {"id": r["folder_id"], "pfad": _pfad(r["folder_id"], ordner)},
                    "recht": r["permission"], "bis": r["valid_until"], "gueltig": gueltig,
                    "wirkt": gueltig and zugang and pruefen_wirkt, "grundrecht_dort": dort,
                    "wirkt_nicht": _wirkt_nicht(gueltig, True, mit_namen, zugang,
                                                r["permission"] == "pruefen" and not qualifiziert, pruefen_wirkt),
                    "laeuft_ab_in_tagen": tage if tage is not None and tage <= ABLAUF_TAGE else None,
                    "verwalter": [v["name"] for v in rechte.verwalter_von(r["folder_id"]) if v["id"] != user["id"]][:3]})
    return {"freigaben": out, "alles": rechte.sicht(user).alles, "qualifiziert": qualifiziert, "zugang": zugang}


def nutzer_suchen(q, zweck=None):
    """GET /nutzer?q=&zweck= (Verwalter irgendwo, Material-Verwaltung): aktive Konten mit Namen, deren Name q enthält
    (ab 3 Zeichen, Groß/klein egal, auch bei Umlauten), höchstens 20 – nur Name, Gliederung (Freitext), ob qualifiziert
    und ob das Konto das Grundrecht überall hat (Material-Verwaltung – dann darf eine Prüffreigabe auch ohne lesen oder
    verwalten dauerhaft sein, grundrecht_an). Keine E-Mail, keine Urkundennummer: kaum mehr, als die Wiki-Nutzerliste
    jedem Mitglied zeigt. zweck „freigabe“ (Vorgabe): nur Konten mit Zugang zum Modul (Stufe Mitglied oder Verwaltung) –
    an andere ließe sich keine Freigabe vergeben (erteilen antwortet 409); „zuordnung“: alle, denn wer PSA trägt,
    braucht keinen Modulzugang."""
    zweck = auswahl(zweck or "freigabe", ZWECKE, "Zweck")
    q = text({"q": q}, "q", "Suche", n=80)
    if len(q) < SUCHE_MIN:
        raise Abgelehnt(SUCHE_KURZ)
    such = q.casefold()
    stufe = " AND (recht_material >= 1 OR recht_verwaltung >= 2)" if zweck == "freigabe" else ""
    treffer = [u for u in db.query("SELECT id, name, gliederung, mat_pruefer, urkundennummer, recht_material, "
                                   "recht_verwaltung FROM users WHERE active = 1 AND status = 'active' "
                                   f"AND trim(name) <> ''{stufe} ORDER BY name COLLATE NOCASE, id")
               if such in u["name"].casefold()]
    return {"nutzer": [{"id": u["id"], "name": u["name"], "gliederung": u["gliederung"],
                        "qualifiziert": rechte.qualifiziert(u), "grundrecht_ueberall": rechte.grundrecht_ueberall(u)}
                       for u in treffer[:SUCHE_MAX]],
            "mehr": len(treffer) > SUCHE_MAX}


# --- Nutzerverwaltung (api_admin.list_users) -----------------------------------------------------------------------

def zahlen_je_konto():
    """Für die Nutzerliste mit EINER gruppierten Abfrage: je Konto die Zahl gültiger Freigaben und ob darunter ein
    Grundrecht bzw. verwalten ist. {uid: (freigaben, grundrechte, verwalten)}"""
    return {r["user_id"]: (r["n"], r["grund"] or 0, bool(r["v"])) for r in db.query(
        "SELECT user_id, COUNT(*) AS n, SUM(permission IN ('lesen', 'verwalten')) AS grund, "
        "MAX(permission = 'verwalten') AS v FROM mat_folder_grant WHERE valid_until IS NULL OR valid_until >= ? "
        "GROUP BY user_id", (_heute().isoformat(),))}
