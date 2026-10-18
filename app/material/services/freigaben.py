"""Freigaben je Ordner vergeben, ändern, entziehen und verlängern (Phase 2 · Lieferung 1, Abschnitt 4).

Was eine Freigabe ist und wie sie wirkt, steht in rechte.py. Hier stehen die Regeln, wer sie schreiben darf (Bauentwurf
1.6), und die Listen für den Dialog „Freigaben“ (freigaben.js), „Meine Freigaben“ und die Nutzerverwaltung:

  1  Die Plattform-Verwaltung vergibt überall, ohne die Grenzen 3–7. Für Prüffreigaben gelten auch für sie Nr. 8 und
     die 24 Monate – Sachkunde lässt sich nicht verwalten, nur nachweisen.
  2  Wer einen Ordner verwaltet, vergibt dort und darunter – an jedes aktive Konto mit Namen, auch aus anderen
     Gliederungen (rechte.waehlbares_konto).
  3  Was er vergibt oder nach einer Änderung hinterlässt, endet nicht später als sein eigenes Verwalten am Anker
     (Sicht.ende). Unbefristet vergibt nur, wer selbst unbefristet verwaltet.
  4  Eine fremde Zeile ändert oder entzieht er nur, wenn sie schon vorher in diesen Grenzen liegt – ein befristeter
     Verwalter kann einen dauerhaften weder entziehen noch kürzen noch herabsetzen.
  5  Die eigene Zeile nur verkürzen, herabsetzen (verwalten → lesen) oder entziehen.
  6  Zeilen oberhalb des eigenen Bereichs sieht er als „geerbt“, ohne Notiz, und ändert sie nicht.
  7  Danach hat jede Gliederung im Zweig des Ankers noch einen Verwalter, der mindestens so lange bleibt wie er – sonst
     409 (_verwaltung_danach).
  8  Prüffreigaben nur an qualifizierte Konten, immer befristet, höchstens 24 Monate.
  9  lesen und verwalten: Enddatum frei, wenn gesetzt nicht in der Vergangenheit.
 10  Die Notiz (200 Zeichen, eine Zeile) sehen nur Verwalter des Ankers und die Verwaltung – ins Journal kommt nur
     „notiz_geaendert“.
 11  Nicht an „Gesperrt“ und „Ausgesondert“ (409); Unsichtbares antwortet 404 (requires_folder).
 12  Ein Konto, das es nicht gibt, das deaktiviert ist oder keinen Namen hat: dieselbe 404.
 13  Nach jedem Schreiben rechte.sicht_verwerfen() – die Antwort zeigt schon den neuen Stand.

Journal am Ordner, an dem die Freigabe verankert ist: freigabe_erteilt, freigabe_geaendert, freigabe_entzogen mit
{"freigabe", "konto": {"ref"}, "recht", "bis"} – das Konto nur als pseudonymer Verweis (journal.konto_ref), der Name
dessen, der handelt, steht wie immer in user_name."""
import json
from datetime import date, timedelta

from flask import g

from ... import db
from ...auth import current_user, is_admin
from .. import services as dienste
from ..models import FREIGABEN, MIGRATION_8
from . import Abgelehnt, auswahl, datum, journal, kennung, text
from . import rechte
from .bestand import heimat
from .interval import plus_monate

SYSTEMORDNER = "Freigaben gibt es nicht für „Gesperrt“ und „Ausgesondert“ – sie gelten über die Gliederung."
FREIGABE_FEHLT = "Freigabe nicht gefunden."
NICHT_QUALIFIZIERT = ("Prüffreigaben nur an Konten mit Prüferqualifikation (Häkchen der Verwaltung und Urkundennummer im "
                      "Profil).")
LETZTER_VERWALTER = ("Danach hätte die Gliederung keinen Verwalter mehr, der so lange bleibt wie du – das macht nur die "
                     "Plattform-Verwaltung.")
EIGENE = "Deine eigene Freigabe kannst du nur verkürzen, herabsetzen oder entziehen."
EIGENE_NEU = "Dir selbst vergibst du keine Freigabe – das macht ein anderer Verwalter oder die Plattform-Verwaltung."
NICHT_AENDERBAR = ("Diese Freigabe reicht weiter als deine eigene – ändern kann sie nur, wer mindestens so lange "
                   "verwaltet, oder die Plattform-Verwaltung.")
NUR_VERWALTER = "Freigaben ändert nur, wer den Ordner verwaltet, an dem sie vergeben sind."
PRUEFEN_BIS = "Eine Prüffreigabe braucht ein Enddatum."
VERGANGEN = "Das Enddatum liegt in der Vergangenheit."
KEIN_RECHT = "Bitte ein Recht wählen – Grundrecht, Prüffreigabe oder beides."
SUCHE_KURZ = "Bitte mindestens 3 Zeichen des Namens eingeben."
NUR_VERWALTUNG = "Nur für die Plattform-Verwaltung."

NOTIZ_MAX = 200
PRUEFEN_MONATE = 24                 # längste Prüffreigabe (1.6 Nr. 8)
ABLAUF_TAGE = 30                    # „läuft in n Tagen ab“
VERLAENGERN_TAGE = 90               # so lange abgelaufene Prüffreigaben nimmt „Alle verlängern“ noch mit
MEINE_TAGE = 365                    # so lange zeigt „Meine Freigaben“ abgelaufene
SUCHE_MIN, SUCHE_MAX = 3, 20
# Wer eine Freigabe ohne Konto (granted_by NULL) vergeben hat – Name im Journal → Anzeige. Sonst war es ein Konto, das
# es nicht mehr gibt.
SYSTEM = {MIGRATION_8: "Migration", "Demodaten": "Demodaten"}
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
    """Enddatum einer Freigabe aus der Anfrage (1.6 Nr. 8 und 9): bei pruefen Pflicht und höchstens 24 Monate, sonst frei;
    gesetzt nie in der Vergangenheit."""
    bis = datum(wert, "bis")
    if recht == "pruefen":
        if bis is None:
            raise Abgelehnt(PRUEFEN_BIS)
        if bis > pruefen_max():
            raise Abgelehnt(f"Eine Prüffreigabe läuft höchstens {PRUEFEN_MONATE} Monate – also bis spätestens "
                            f"{_tag(pruefen_max())}.")
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


def _aktiv(u):
    return bool(u["active"]) and (u["status"] or "active") == "active"


def _ende(s, fid):
    """Das eigene wirksame Ende von verwalten an fid (None = unbefristet, auch für die Verwaltung)."""
    return s.ende("verwalten", fid)


def zeile(gid):
    return db.query("SELECT * FROM mat_folder_grant WHERE id = ?", (gid,), one=True)


# --- Regeln (1.6) ------------------------------------------------------------------------------------------------

def _regeln(s, ich, anker, alt, neu, konto):
    """Prüft eine Änderung an einer Zeile – vorher alt (None beim Anlegen), nachher neu (None beim Entziehen) – gegen
    1.6 Nr. 3, 4, 5 und 8. Der Anker ist sichtbar und wird vom Handelnden verwaltet (Route); Nr. 7 prüft der Aufrufer
    nach dem Schreiben."""
    if not s.alles:
        ende = _ende(s, anker)
        if alt is not None and _spaeter(alt["valid_until"], ende):
            raise Abgelehnt(NICHT_AENDERBAR, 403)
        if neu is not None and _spaeter(neu["valid_until"], ende):
            if neu["valid_until"] is None:
                raise Abgelehnt("Dauerhaft vergibt nur, wer selbst dauerhaft verwaltet – setze ein Enddatum (spätestens "
                                f"{_tag(ende)}).", 403)
            raise Abgelehnt(f"Länger als deine eigene Verwalterfreigabe hier (bis {_tag(ende)}) vergibst du nichts.", 403)
        if (alt or neu)["user_id"] == ich["id"]:
            if alt is None:
                raise Abgelehnt(EIGENE_NEU, 403)
            if neu is not None and (_spaeter(neu["valid_until"], alt["valid_until"]) or (
                    neu["permission"] != alt["permission"]
                    and (alt["permission"], neu["permission"]) != ("verwalten", "lesen"))):
                raise Abgelehnt(EIGENE, 403)
    # Nr. 8: Eine Prüffreigabe entsteht oder reicht weiter – das Konto muss qualifiziert sein. Kürzen geht immer.
    if neu is not None and neu["permission"] == "pruefen" and (
            alt is None or alt["permission"] != "pruefen" or _spaeter(neu["valid_until"], alt["valid_until"])):
        if not rechte.ist_pruefer(konto):
            raise Abgelehnt(NICHT_QUALIFIZIERT, 409)


def _spur(gid, z, notiz=False, grund=None):
    """Was ins Journal kommt: Kennung, pseudonymer Kontoverweis, Recht, Ende – nie die Notiz."""
    out = {"freigabe": gid, "konto": journal.konto_ref(z["user_id"]), "recht": z["permission"], "bis": z["valid_until"]}
    if notiz:
        out["notiz_geaendert"] = True
    if grund:
        out["grund"] = grund
    return out


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


def _verwaltung_danach(vorher):
    """Nach dem Schreiben (noch in der Transaktion): Jede Gliederung aus vorher hat einen Verwalter, dessen Ende nicht
    vor dem bisherigen eigenen liegt – sonst 409, und die Transaktion rollt zurück."""
    for gl, ende in vorher.items():
        if not any(not _spaeter(ende, v["ende"]) for v in rechte.verwalter_von(gl)):
            raise Abgelehnt(LETZTER_VERWALTER, 409)


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
    verwalten, Ende frei) und eine Prüffreigabe (Ende Pflicht). So entstehen die Vorlagen des Dialogs in einem Schritt;
    scheitert die zweite Zeile, gibt es auch die erste nicht. Vorhandene Zeilen derselben Art werden geändert.
    grundrecht null lässt das Grundrecht unberührt, pruefen_bis null (oder fehlend) die Prüffreigabe; pruefen_bis ""
    heißt „Prüffreigabe ohne Ende“ und ist ein Fehler. Liefert die Kennungen der geschriebenen Zeilen."""
    ich, s = current_user(), rechte.sicht()
    ordner = _ordner_alle()
    _anker_pruefen(fid, ordner)
    konto = rechte.waehlbares_konto(d.get("user_id"))
    grund = auswahl(d.get("grundrecht"), rechte.GRUNDRECHTE, "Grundrecht", leer_erlaubt=True)
    grund_bis = _bis(d.get("grund_bis"), grund) if grund else None
    mit_pruefen = d.get("pruefen_bis") is not None
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
    """PUT /freigaben/<gid>: Recht, Ende und Notiz einer Zeile. „bis“: null heißt unbefristet (nur Grundrechte). Aus
    einem Grundrecht wird eine Prüffreigabe und umgekehrt nur, wenn es die andere Art dort noch nicht gibt (409)."""
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
    mehr fortsetzen darf – die gibt ein Verwalter unter Prüfungen → Entwürfe frei."""
    ich, s = current_user(), rechte.sicht()
    alt = zeile(gid)
    ordner = _ordner_alle()
    with db.transaction(sofort=True):
        vorher = _verwaltung_vorher(s, alt["folder_id"], ordner, noetig=alt["permission"] == "verwalten")
        _schreiben(s, ich, alt["folder_id"], alt, None, _konto(alt["user_id"]))
        _verwaltung_danach(vorher)
    rechte.sicht_verwerfen()
    if alt["permission"] != "pruefen":
        return 0
    konto = _konto(alt["user_id"])
    zweig = _zweig(alt["folder_id"], ordner)
    offen = db.query("SELECT i.* FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE x.inspector_user_id = ? "
                     "AND x.completed_at IS NULL", (alt["user_id"],))
    return sum(1 for i in offen if heimat(i) in zweig and not rechte.darf("pruefen", heimat(i), konto))


def verlaengern(fid, d):
    """POST /ordner/<fid>/freigaben/verlaengern: alle Prüffreigaben an fid oder darunter, die noch gelten oder seit
    höchstens 90 Tagen abgelaufen sind, auf „bis“ – soweit der Handelnde sie nach 1.6 ändern darf, das Konto qualifiziert
    und aktiv ist und die Freigabe dadurch länger wird. Je Zeile ein Journaleintrag; was übersprungen wurde, steht mit
    Grund in der Antwort."""
    ich, s = current_user(), rechte.sicht()
    ordner = _ordner_alle()
    _anker_pruefen(fid, ordner)
    bis = _bis(d.get("bis"), "pruefen")
    if not s.alles and _spaeter(bis, _ende(s, fid)):
        raise Abgelehnt(f"Länger als deine eigene Verwalterfreigabe hier (bis {_tag(_ende(s, fid))}) verlängerst du "
                        "nichts.", 403)
    zweig = _zweig(fid, ordner)
    ab = (_heute() - timedelta(days=VERLAENGERN_TAGE)).isoformat()
    rows = db.query("SELECT g.*, u.name AS konto_name FROM mat_folder_grant g JOIN users u ON u.id = g.user_id "
                    "WHERE g.permission = 'pruefen' AND g.valid_until >= ? AND g.folder_id IN "
                    "(SELECT value FROM json_each(?)) ORDER BY u.name COLLATE NOCASE, g.id",
                    (ab, json.dumps(sorted(zweig))))
    verlaengert, uebersprungen = 0, []
    with db.transaction(sofort=True):
        for r in rows:
            konto = _konto(r["user_id"])
            grund = None
            if not _aktiv(konto):
                grund = "Konto deaktiviert"
            elif not rechte.ist_pruefer(konto):
                grund = "Qualifikation fehlt"
            elif not s.alles and r["user_id"] == ich["id"]:
                grund = "eigene Freigabe"
            elif not s.alles and _spaeter(r["valid_until"], _ende(s, r["folder_id"])):
                grund = "reicht weiter als deine eigene Freigabe"
            elif not _spaeter(bis, r["valid_until"]):
                grund = f"läuft schon bis {_tag(r['valid_until'])}"
            if grund:
                uebersprungen.append({"konto": r["konto_name"], "ordner": _pfad(r["folder_id"], ordner), "grund": grund})
                continue
            _schreiben(s, ich, r["folder_id"], r, dict(r, valid_until=bis), konto, grund="alle verlängert")
            verlaengert += 1
    rechte.sicht_verwerfen()
    return {"verlaengert": verlaengert, "uebersprungen": uebersprungen}


# --- Lesen -------------------------------------------------------------------------------------------------------

_ZEILEN_SQL = ("SELECT g.*, u.name AS u_name, u.gliederung AS u_gliederung, u.active AS u_active, u.status AS u_status, "
               "u.mat_pruefer AS u_pruefer, u.urkundennummer AS u_urkunde, v.name AS von_name FROM mat_folder_grant g "
               "JOIN users u ON u.id = g.user_id LEFT JOIN users v ON v.id = g.granted_by ")


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


def _eintrag(r, ordner, s, system, notiz):
    """Eine Zeile für die Listen (4.1). notiz: ob die Notiz mitkommt (V am Anker oder Verwaltung, nie geerbt)."""
    heute = _heute()
    qualifiziert = rechte.ist_pruefer({"mat_pruefer": r["u_pruefer"], "urkundennummer": r["u_urkunde"]})
    aktiv = bool(r["u_active"]) and (r["u_status"] or "active") == "active"
    gueltig = rechte.gueltig(r["valid_until"])
    tage = (date.fromisoformat(r["valid_until"]) - heute).days if gueltig and r["valid_until"] else None
    anker = r["folder_id"]
    darf_anker = s.alles or s.darf("verwalten", anker)
    out = {"id": r["id"], "ordner": {"id": anker, "pfad": _pfad(anker, ordner)},
           "konto": {"id": r["user_id"], "name": r["u_name"], "gliederung": r["u_gliederung"], "aktiv": aktiv,
                     "haekchen": bool(r["u_pruefer"]), "qualifiziert": qualifiziert},
           "recht": r["permission"], "bis": r["valid_until"], "gueltig": gueltig,
           "wirkt": gueltig and aktiv and bool((r["u_name"] or "").strip()) and (r["permission"] != "pruefen" or qualifiziert),
           "laeuft_ab_in_tagen": tage if tage is not None and tage <= ABLAUF_TAGE else None,
           "vergeben_von": (r["von_name"] or "") if r["granted_by"] is not None
           else system.get(r["id"], "(gelöschtes Konto)"),
           "seit": r["created_at"], "eigen": r["user_id"] == s.uid,
           "aenderbar": bool(s.alles or (darf_anker and not _spaeter(r["valid_until"], _ende(s, anker))))}
    if notiz and darf_anker:
        out["notiz"] = r["note"] or ""
    return out


def _sortiert(rows, ordner):
    return sorted(rows, key=lambda r: (len(_kette(r["folder_id"], ordner)), _pfad(r["folder_id"], ordner).casefold(),
                                       (r["u_name"] or "").casefold(), r["permission"], r["id"]))


def _verlauf(fid):
    """Die Journaleinträge freigabe_* dieses Ordners, neueste zuerst – seit seiner letzten Löschung (eine Kennung kann
    wiederkommen). Konten stehen mit ihrem heutigen Namen da (journal.konto_name), der Verweis selbst geht nicht hinaus."""
    ab = db.query("SELECT MAX(id) AS m FROM mat_audit WHERE entity = 'folder' AND entity_id = ? AND action = 'geloescht'",
                  (fid,), one=True)["m"] or 0
    marken = ",".join("?" * len(rechte.FREIGABE_AKTIONEN))
    out = []
    for e in db.query(f"SELECT * FROM mat_audit WHERE entity = 'folder' AND entity_id = ? AND id > ? AND action IN "
                      f"({marken}) ORDER BY id DESC LIMIT 200", (fid, ab, *rechte.FREIGABE_AKTIONEN)):
        vorher = json.loads(e["before_json"]) if e["before_json"] else {}
        nachher = json.loads(e["after_json"]) if e["after_json"] else {}
        stand = nachher or vorher
        out.append({"id": e["id"], "zeit": e["created_at"], "wer": e["user_name"], "aktion": e["action"],
                    "konto": journal.konto_name((stand.get("konto") or {}).get("ref")),
                    "recht": stand.get("recht"), "bis": stand.get("bis"),
                    "recht_vorher": vorher.get("recht") if nachher and vorher else None,
                    "bis_vorher": vorher.get("bis") if nachher and vorher else None,
                    "notiz_geaendert": bool(nachher.get("notiz_geaendert")), "grund": stand.get("grund")})
    return out


def liste(fid):
    """GET /ordner/<fid>/freigaben (V am Ordner): die Freigaben hier („direkt“), darüber („geerbt“, ohne Notiz) und
    darunter („unten“), die Anker zur Auswahl (fid und die Oberordner, die der Handelnde verwaltet – mit seinem Ende
    dort), den Verlauf und die Zahl der Freigaben im Zweig, die in den nächsten 30 Tagen ablaufen."""
    s = rechte.sicht()
    ordner = _ordner_alle()
    _anker_pruefen(fid, ordner)
    kette = _kette(fid, ordner)
    zweig = _zweig(fid, ordner)
    rows = db.query(_ZEILEN_SQL + "WHERE g.folder_id IN (SELECT value FROM json_each(?))",
                    (json.dumps(sorted(set(kette) | zweig)),))
    system = _von_system(rows)
    direkt = [r for r in rows if r["folder_id"] == fid]
    geerbt = [r for r in rows if r["folder_id"] != fid and r["folder_id"] in kette]
    unten = [r for r in rows if r["folder_id"] != fid and r["folder_id"] in zweig]
    anker = [{"id": x, "pfad": _pfad(x, ordner), "gliederung": _gliederung(ordner[x]), "ende": _ende(s, x)}
             for x in kette if not ordner[x]["system_kind"] and s.darf("verwalten", x)]
    # Vorgabe: die nächste Gliederung, wenn man sie verwaltet, sonst der Ordner selbst.
    naechste = next((x for x in kette if _gliederung(ordner[x])), None)
    vorgabe = naechste if any(a["id"] == naechste for a in anker) else fid
    eintraege = {"direkt": [_eintrag(r, ordner, s, system, True) for r in _sortiert(direkt, ordner)],
                 "geerbt": [_eintrag(r, ordner, s, system, False) for r in _sortiert(geerbt, ordner)],
                 "unten": [_eintrag(r, ordner, s, system, True) for r in _sortiert(unten, ordner)]}
    o = ordner[fid]
    return dict(eintraege, ordner={"id": fid, "name": o["name"], "pfad": _pfad(fid, ordner),
                                   "gliederung": _gliederung(o)},
                anker_wahl=anker, anker_vorgabe=vorgabe, verlauf=_verlauf(fid),
                laeuft_ab=sum(1 for e in eintraege["direkt"] + eintraege["unten"] if e["laeuft_ab_in_tagen"] is not None),
                grenzen={"heute": _heute().isoformat(), "pruefen_max": pruefen_max(), "vorgabe_bis": vorgabe_bis()},
                alles=s.alles)


def eintrag(gid):
    """Eine Zeile nach dem Ändern – wie in der Liste ihres Ankers (mit Notiz, wenn der Handelnde ihn verwaltet)."""
    rows = db.query(_ZEILEN_SQL + "WHERE g.id = ?", (gid,))
    return _eintrag(rows[0], _ordner_alle(), rechte.sicht(), _von_system(rows), True) if rows else None


def des_kontos(uid):
    """GET /freigaben?user_id= (nur die Verwaltung): alle Freigaben eines Kontos, auch abgelaufene, mit Notiz – für den
    Dialog „Bearbeiten“ der Nutzerverwaltung."""
    u = _konto(kennung(uid, "Konto"))
    if not u:
        raise Abgelehnt(rechte.KONTO_FEHLT, 404)
    ordner = _ordner_alle()
    rows = db.query(_ZEILEN_SQL + "WHERE g.user_id = ?", (u["id"],))
    system = _von_system(rows)
    s = rechte.sicht()
    return [_eintrag(r, ordner, s, system, True) for r in _sortiert(rows, ordner)]


def meine(user):
    """GET /freigaben/meine (jeder Angemeldete, auch ohne Modulzugang): die eigenen Freigaben – gültige und in den
    letzten 365 Tagen abgelaufene – mit Pfad, Zustand und bis zu drei Verwaltern des Ankers (wer verlängern kann).
    Ohne Notiz."""
    heute = _heute()
    ab = (heute - timedelta(days=MEINE_TAGE)).isoformat()
    rows = db.query("SELECT * FROM mat_folder_grant WHERE user_id = ? AND (valid_until IS NULL OR valid_until >= ?) "
                    "ORDER BY id", (user["id"], ab))
    ordner = _ordner_alle()
    qualifiziert = rechte.ist_pruefer(user)
    mit_namen = bool((user["name"] or "").strip())
    out = []
    for r in _sortiert([dict(r, u_name=user["name"]) for r in rows], ordner):
        gueltig = rechte.gueltig(r["valid_until"])
        tage = (date.fromisoformat(r["valid_until"]) - heute).days if gueltig and r["valid_until"] else None
        out.append({"id": r["id"], "ordner": {"id": r["folder_id"], "pfad": _pfad(r["folder_id"], ordner)},
                    "recht": r["permission"], "bis": r["valid_until"], "gueltig": gueltig,
                    "wirkt": gueltig and mit_namen and (r["permission"] != "pruefen" or qualifiziert),
                    "laeuft_ab_in_tagen": tage if tage is not None and tage <= ABLAUF_TAGE else None,
                    "verwalter": [v["name"] for v in rechte.verwalter_von(r["folder_id"]) if v["id"] != user["id"]][:3]})
    return {"freigaben": out, "alles": is_admin(user), "qualifiziert": qualifiziert, "zugang": rechte.zugang(user)}


def nutzer_suchen(q):
    """GET /nutzer?q= (Verwalter irgendwo, Verwaltung): aktive Konten mit Namen, deren Name q enthält (ab 3 Zeichen,
    Groß/klein egal, auch bei Umlauten), höchstens 20 – nur Name, Gliederung (Freitext) und ob qualifiziert. Keine
    E-Mail, keine Urkundennummer: nicht mehr, als die Wiki-Nutzerliste jedem Mitglied zeigt."""
    q = text({"q": q}, "q", "Suche", n=80)
    if len(q) < SUCHE_MIN:
        raise Abgelehnt(SUCHE_KURZ)
    such = q.casefold()
    treffer = [u for u in db.query("SELECT id, name, gliederung, mat_pruefer, urkundennummer FROM users WHERE active = 1 "
                                   "AND status = 'active' AND trim(name) <> '' ORDER BY name COLLATE NOCASE, id")
               if such in u["name"].casefold()]
    return {"nutzer": [{"id": u["id"], "name": u["name"], "gliederung": u["gliederung"],
                        "qualifiziert": rechte.ist_pruefer(u)} for u in treffer[:SUCHE_MAX]],
            "mehr": len(treffer) > SUCHE_MAX}


# --- Nutzerverwaltung (api_admin.list_users) -----------------------------------------------------------------------

def zahlen_je_konto():
    """Für die Nutzerliste mit EINER gruppierten Abfrage: je Konto die Zahl gültiger Freigaben und ob darunter ein
    Grundrecht bzw. verwalten ist. {uid: (freigaben, grundrechte, verwalten)}"""
    return {r["user_id"]: (r["n"], r["grund"] or 0, bool(r["v"])) for r in db.query(
        "SELECT user_id, COUNT(*) AS n, SUM(permission IN ('lesen', 'verwalten')) AS grund, "
        "MAX(permission = 'verwalten') AS v FROM mat_folder_grant WHERE valid_until IS NULL OR valid_until >= ? "
        "GROUP BY user_id", (_heute().isoformat(),))}


def stufen_vormerken(users, zahlen):
    """Die wirksame Material-Stufe aller Konten der Liste aus zahlen_je_konto in den Zwischenspeicher der Anfrage
    (g.mat_stufe) legen – dieselbe Regel wie rechte.material_stufe_wirksam (der Test vergleicht beide), aber ohne eine
    Abfrage je Konto. public_user liest sie dann von dort."""
    speicher = g.setdefault("mat_stufe", {})
    for u in users:
        _, grund, verwalten = zahlen.get(u["id"], (0, 0, False))
        if not (u["name"] or "").strip():
            n = 0
        elif is_admin(u) or verwalten:
            n = 2
        elif grund or u["mat_katalog"] or u["mat_pruefer"]:
            n = 1
        else:
            n = 0
        speicher[u["id"]] = n
