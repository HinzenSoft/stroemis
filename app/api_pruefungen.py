"""Prüfungen: Lehrgänge, Teilnehmende, Voraussetzungen, Prüfungsleistungen, Bewertungen (Versuche),
Medien, Mängelübersicht und Excel-Import.

Jede Route verlangt das Zusatzrecht „Prüfer“ – der Bereich enthält personenbezogene Daten von
Teilnehmenden, und ein ausgeblendeter Reiter ist kein Schutz. Wer etwas setzt, prüft oder hochlädt,
steht mit Kennung UND Namens-Schnappschuss in der Zeile: Die Nachvollziehbarkeit einer Prüfung darf
nicht daran hängen, dass das Konto des Prüfers noch besteht."""
import json
import os
import re
import sqlite3
from datetime import date

from flask import Blueprint, current_app, jsonify, request

from . import db
from .auth import current_user, eingabefehler_abfangen, is_admin, json_body, pruefer_required, sfield
from .images import BildFehler, delete_avatar, delete_photo_files, store_avatar, store_upload

bp = Blueprint("pruefungen", __name__, url_prefix="/api/pruefungen")
eingabefehler_abfangen(bp)

STATUS_WERTE = ("geplant", "laufend", "abgeschlossen")
ERGEBNISSE = ("bestanden", "mangelhaft")
# Längster erlaubter Zeitwert: ein Tag. Eine Prüfungsleistung, die länger dauert, gibt es nicht –
# alles darüber ist ein Tippfehler („1200:00“ statt „12:00“) und soll als solcher auffallen.
MAX_SEKUNDEN = 24 * 3600
KOMMENTAR_PFLICHT = "Bei „mangelhaft“ ist ein Kommentar Pflicht."
SCHON_BEWERTET = ("Für diese Leistung gibt es schon eine Bewertung – bearbeite sie oder lege eine "
                  "Nachprüfung an.")
NUR_NACH_MANGEL = "Eine Nachprüfung gibt es nur nach einer mangelhaften Bewertung."
ERGEBNISSE_LEHRGANG = ("bestanden", "nicht_bestanden")
EINGEFROREN = ("Für diese Person ist das Lehrgangsergebnis vermerkt – die Prüfungsdaten sind eingefroren. "
               "Die Lehrgangsleitung kann das Ergebnis aufheben.")
NUR_LEITUNG = "Nur die Lehrgangsleitung oder die Administration darf das."
GERADE_GELOESCHT = ("Die Person, die Leistung oder der Lehrgang wurde inzwischen von jemand anderem gelöscht – "
                    "bitte die Seite neu laden.")


class Abgelehnt(Exception):
    """Eine Antwort mit Fehlertext und Statuscode, die aus einer Hilfsfunktion heraus ausgelöst wird.

    Die Prüfungen („gibt es den Lehrgang?“, „ist das ein Datum?“) stecken in Helfern, die von
    vielen Routen gebraucht werden. Statt in jeder Route ein Tupel durchzureichen, wirft der Helfer –
    der Blueprint-Handler unten macht daraus die übliche JSON-Antwort. Bewusst KEIN ValueError:
    den fängt eingabefehler_abfangen und ersetzte den Klartext durch „Unbrauchbare Eingabe.“."""

    def __init__(self, meldung, code=400):
        super().__init__(meldung)
        self.code = code


@bp.errorhandler(Abgelehnt)
def _abgelehnt(exc):
    return jsonify(error=str(exc)), exc.code


@bp.errorhandler(sqlite3.IntegrityError)
def _integritaet(exc):
    """Zwei Prüfer arbeiten gleichzeitig: Der eine löscht eine Person, der andere hakt ihr gerade
    eine Voraussetzung ab. Der Fremdschlüssel weist das zweite ab – das ist kein Serverfehler,
    sondern ein Hinweis, die Seite neu zu laden."""
    current_app.logger.warning("Integritätsfehler an %s %s: %s", request.method, request.path, exc)
    return jsonify(error=GERADE_GELOESCHT), 409


# --- Hilfsfunktionen ---------------------------------------------------------

def _medien_dir():
    """Eigener Unterordner unter dem Medienverzeichnis: store_upload legt darin orig/web/thumb an,
    und die Route /media/pruefung/… liefert nur aus diesem Ordner – getrennt von den Albumbildern,
    die jeder Angemeldete sehen darf."""
    return os.path.join(current_app.config["MEDIA_DIR"], "pruefungen")


def _ich():
    """Kennung und Anzeigename des angemeldeten Nutzers – für alle „*_von“-Felder."""
    u = current_user()
    return u["id"], (u["name"] or u["email"])


def _ist_leitungsfunktion(funktion):
    """„Lehrgangsleitung“, „Leitung“, „Leiter:in“ – alles, was „leit“ enthält. Referierende ohne
    Leitungsfunktion prüfen und haken ab, verändern aber keine Stammdaten."""
    return "leit" in (funktion or "").lower()


def _darf_leiten(lid):
    """Lehrgangsleitung ist, wer im Lehrgang mit dem Kennzeichen „Leitung“ eingetragen ist (über sein
    Nutzerkonto) – und die Administration. Mehrere Personen je Lehrgang sind möglich. Ein Freitext-
    Eintrag ohne Konto zählt nicht: Er ließe sich von jedem hineinschreiben."""
    if is_admin():
        return True
    uid = current_user()["id"]
    return bool(db.query("SELECT 1 FROM pruef_ausbilder WHERE lehrgang_id = ? AND user_id = ? AND ist_leitung = 1",
                         (lid, uid)))


def _leitung(lid):
    if not _darf_leiten(lid):
        raise Abgelehnt(NUR_LEITUNG, 403)


def _leitung_ergaenzen(ausbilder):
    """Wer einen Lehrgang anlegt, wird seine Leitung – sonst könnte er ihn gleich danach nicht mehr
    bearbeiten. Administratoren brauchen den Eintrag nicht; wer sich selbst schon als Leitung
    eingetragen hat, bekommt keinen zweiten."""
    uid, name = _ich()
    if is_admin() or any(a_uid == uid and leit for a_uid, _, _, leit in ausbilder):
        return ausbilder
    return [(uid, name, "", 1)] + list(ausbilder)


def _eingefroren_pruefen(tn):
    """Prüfungsdaten einer Person mit vermerktem Lehrgangsergebnis sind eingefroren."""
    if tn.get("ergebnis"):
        raise Abgelehnt(EINGEFROREN, 409)


def _bild_url(datei):
    return f"/media/pruefung/avatar/{datei}" if datei else None


def _datum(wert, feld):
    """'YYYY-MM-DD' oder None; alles andere wird abgewiesen. Ein Datumsfeld, das irgendeinen Text
    aufnimmt, ließe sich später weder sortieren noch nach Jahr filtern."""
    if wert in (None, ""):
        return None
    if isinstance(wert, str):
        s = wert.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            try:
                date.fromisoformat(s)
                return s
            except ValueError:
                pass
    raise Abgelehnt(f"„{feld}“ muss ein Datum im Format JJJJ-MM-TT sein.")


def _sekunden(wert, feld="Zeit"):
    """Zeitangabe nach Sekunden: None/leer → None; ganze Zahl; Text „mm:ss“, „m:ss“, „h:mm:ss“
    oder nur „ss“. Die Stoppuhr liefert ganze Sekunden, ein Mensch tippt „2:31“ – beides soll gehen.
    Ein Bruchteil in der letzten Stelle („02:31.4“) wird gerundet."""
    if wert is None or wert == "":
        return None
    if isinstance(wert, bool):
        raise Abgelehnt(f"„{feld}“ ist keine gültige Zeitangabe.")
    if isinstance(wert, int):
        n = wert
    elif isinstance(wert, float):
        n = round(wert)
    elif isinstance(wert, str):
        # Nur Ziffern und Doppelpunkte, Minuten und Sekunden hinter dem ersten Doppelpunkt 0–59:
        # int()/float() nähmen sonst auch „1:-5“, „1:90“ oder „1_0:00“ an und rechneten daraus
        # eine harmlos aussehende Zahl.
        m = re.fullmatch(r"\s*(?:(\d{1,3}):)?(?:(\d{1,2}):)?(\d{1,5})(?:[.,](\d+))?\s*", wert)
        if not m or (m.group(1) is not None and (m.group(2) is not None) and int(m.group(2)) > 59) \
                or ((m.group(1) is not None or m.group(2) is not None) and int(m.group(3)) > 59):
            raise Abgelehnt(f"„{wert}“ ist keine gültige Zeitangabe (Format mm:ss).")
        h, mi, se, bruch = m.groups()
        if h is not None and mi is None:          # „mm:ss“ – die erste Gruppe sind die Minuten
            h, mi = None, h
        n = (int(h or 0) * 60 + int(mi or 0)) * 60 + int(se)
        if bruch and int(bruch[0]) >= 5:
            n += 1
    else:
        raise Abgelehnt(f"„{feld}“ ist keine gültige Zeitangabe.")
    if n < 0 or n > MAX_SEKUNDEN:
        raise Abgelehnt(f"„{feld}“ liegt außerhalb des zulässigen Bereichs (0 bis 24 Stunden).")
    return n


def _bool(d, key):
    """Ein Ja/Nein-Feld aus dem JSON: echte Booleans, 0/1 und die üblichen Wörter. Reine
    Wahrheitsprüfung reichte nicht – der Text „false“ wäre wahr."""
    v = d.get(key)
    if v is None or isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in ("true", "false", "1", "0", "ja", "nein", "yes", "no", ""):
        return v.strip().lower() in ("true", "1", "ja", "yes")
    raise Abgelehnt(f"„{key}“ muss wahr oder falsch sein.")


def _ganzzahl(wert, feld):
    try:
        n = int(wert)
    except (TypeError, ValueError, OverflowError):
        raise Abgelehnt(f"„{feld}“ ist keine gültige Zahl.")
    if abs(n) > 10 ** 9:
        raise Abgelehnt(f"„{feld}“ ist keine gültige Zahl.")
    return n


def _id_liste(roh):
    """Kennungen aus einer Reihenfolge-Anfrage: Liste aus Zahlen (oder Ziffernfolgen), sonst 400."""
    if not isinstance(roh, list) or len(roh) > 1000:
        raise Abgelehnt("„ids“ muss eine Liste von Kennungen sein.")
    ids = []
    for x in roh:
        if isinstance(x, bool) or not (isinstance(x, int) or (isinstance(x, str) and x.isdigit())):
            raise Abgelehnt("„ids“ muss eine Liste von Kennungen sein.")
        ids.append(int(x))
    return ids


def _zellstatus(letzter):
    """Status einer Zelle (TN × Leistung) – maßgeblich ist der letzte Versuch."""
    if not letzter:
        return "offen"
    return ("nachpruefung_" if letzter["ist_nachpruefung"] else "") + letzter["ergebnis"]


def _extra(text):
    try:
        d = json.loads(text or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


# --- Nachschlagen (404 aus dem Helfer heraus) ------------------------------------------

def _lehrgang(lid):
    row = db.query("SELECT * FROM pruef_lehrgaenge WHERE id = ?", (lid,), one=True)
    if not row:
        raise Abgelehnt("Lehrgang nicht gefunden", 404)
    return row


def _tn(tid):
    row = db.query("SELECT * FROM pruef_teilnehmer WHERE id = ?", (tid,), one=True)
    if not row:
        raise Abgelehnt("Teilnehmende:r nicht gefunden", 404)
    return row


def _voraussetzung(vid):
    row = db.query("SELECT * FROM pruef_voraussetzungen WHERE id = ?", (vid,), one=True)
    if not row:
        raise Abgelehnt("Voraussetzung nicht gefunden", 404)
    return row


def _leistung(lid):
    row = db.query("SELECT * FROM pruef_leistungen WHERE id = ?", (lid,), one=True)
    if not row:
        raise Abgelehnt("Prüfungsleistung nicht gefunden", 404)
    return row


def _katalog(kid):
    row = db.query("SELECT * FROM pruef_kataloge WHERE id = ?", (kid,), one=True)
    if not row:
        raise Abgelehnt("Katalog nicht gefunden", 404)
    return row


def _katalog_leistung(lid):
    row = db.query("SELECT * FROM pruef_katalog_leistungen WHERE id = ?", (lid,), one=True)
    if not row:
        raise Abgelehnt("Katalogeintrag nicht gefunden", 404)
    return row


def _katalog_admin():
    """Kataloge sind lehrgangsübergreifend – es gibt keine Leitung, die sie verwalten könnte.
    Deshalb bleibt das Anlegen, Ändern und Löschen der Administration vorbehalten; jede:r Prüfer:in
    darf sie lesen und beim Anlegen eines Lehrgangs als Vorlage wählen."""
    if not is_admin():
        raise Abgelehnt("Kataloge verwaltet nur die Administration.", 403)


# Ein Versuch samt dem, was zur Anzeige immer dazugehört: Leistung und Teilnehmende:r.
_VERSUCH_SQL = (
    "SELECT v.*, p.bezeichnung AS leistung_bezeichnung, p.sortierung AS leistung_sortierung, "
    "       p.zeitansatz_sekunden, t.name AS tn_name, t.vorname AS tn_vorname, "
    "       t.gliederung AS tn_gliederung, t.lehrgang_id "
    "FROM pruef_versuche v "
    "JOIN pruef_leistungen p ON p.id = v.leistung_id "
    "JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id ")


def _versuch(vid):
    row = db.query(_VERSUCH_SQL + "WHERE v.id = ?", (vid,), one=True)
    if not row:
        raise Abgelehnt("Bewertung nicht gefunden", 404)
    return row


def _medium(mid):
    row = db.query("SELECT * FROM pruef_medien WHERE id = ?", (mid,), one=True)
    if not row:
        raise Abgelehnt("Medium nicht gefunden", 404)
    return row


# --- JSON-Formen -------------------------------------------------------------

def _medium_json(m):
    key = os.path.splitext(m["file"])[0]
    return {"id": m["id"], "versuch_id": m["versuch_id"], "kind": m["kind"], "original_name": m["original_name"],
            "width": m["width"], "height": m["height"], "hochgeladen_von_name": m["hochgeladen_von_name"],
            "hochgeladen_am": m["hochgeladen_am"],
            "thumb": f"/media/pruefung/thumb/{key}.jpg", "web": f"/media/pruefung/web/{key}.jpg",
            "orig": f"/media/pruefung/orig/{m['file']}"}


def _versuche_json(rows):
    """Versuche (Zeilen aus _VERSUCH_SQL) samt Medien und Verlauf. Medien und Verlauf werden für
    alle Zeilen auf einmal geholt – die Mängelübersicht zeigt Dutzende Versuche, eine Abfrage je
    Versuch wäre unnötig langsam."""
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    medien, verlauf = {}, {}
    for m in db.query(f"SELECT * FROM pruef_medien WHERE versuch_id IN ({marks}) ORDER BY id", ids):
        medien.setdefault(m["versuch_id"], []).append(_medium_json(m))
    for h in db.query(f"SELECT * FROM pruef_versuch_verlauf WHERE versuch_id IN ({marks}) "
                      "ORDER BY stand_ab, id", ids):
        verlauf.setdefault(h["versuch_id"], []).append(
            {"ergebnis": h["ergebnis"], "zeit_sekunden": h["zeit_sekunden"], "kommentar": h["kommentar"],
             "von_name": h["von_name"], "stand_ab": h["stand_ab"], "ersetzt_am": h["ersetzt_am"]})
    out = []
    for v in rows:
        out.append({
            "id": v["id"], "teilnehmer_id": v["teilnehmer_id"], "leistung_id": v["leistung_id"],
            "versuch_nr": v["versuch_nr"], "ist_nachpruefung": bool(v["ist_nachpruefung"]),
            "ergebnis": v["ergebnis"], "zeit_sekunden": v["zeit_sekunden"], "kommentar": v["kommentar"],
            "geprueft_von_name": v["geprueft_von_name"], "geprueft_am": v["geprueft_am"],
            "bearbeitet_von_name": v["bearbeitet_von_name"], "bearbeitet_am": v["bearbeitet_am"],
            "medien": medien.get(v["id"], []), "verlauf": verlauf.get(v["id"], []),
            "leistung_bezeichnung": v["leistung_bezeichnung"],
            "teilnehmer_name": f"{v['tn_vorname']} {v['tn_name']}".strip()})
    return out


def _versuch_json(row):
    return _versuche_json([row])[0]


def _leistung_json(p):
    return {k: p[k] for k in ("id", "bezeichnung", "beschreibung_md", "zeitansatz_sekunden", "sortierung")}


def _voraussetzung_json(v):
    return {k: v[k] for k in ("id", "bezeichnung", "sortierung")}


# Kataloge tragen dieselben Spalten wie eine Prüfungsleistung (bezeichnung, beschreibung_md,
# zeitansatz_sekunden, sortierung) – _leistung_json passt deshalb unverändert auf beide Tabellen.
_KATALOG_SQL = ("SELECT k.*, (SELECT COUNT(*) FROM pruef_katalog_leistungen kl WHERE kl.katalog_id = k.id) "
               "AS leistungen_anzahl FROM pruef_kataloge k ")


def _katalog_kurz(r):
    return {k: r[k] for k in ("id", "titel", "beschreibung", "created_by_name", "created_at",
                              "updated_at", "leistungen_anzahl")}


def _katalog_detail(kid):
    r = db.query(_KATALOG_SQL + "WHERE k.id = ?", (kid,), one=True)
    if not r:
        raise Abgelehnt("Katalog nicht gefunden", 404)
    out = _katalog_kurz(r)
    out["leistungen"] = [_leistung_json(p) for p in db.query(
        "SELECT * FROM pruef_katalog_leistungen WHERE katalog_id = ? ORDER BY sortierung, id", (kid,))]
    return out


def _teilnehmer_liste(lid, nur_tid=None):
    """Teilnehmende eines Lehrgangs in der Form aus LehrgangDetail: Stammdaten, gesetzte
    Voraussetzungen, Zellstände je Leistung. Mit nur_tid für eine:n Einzelne:n."""
    # Überall mit Alias t – in der Versuche-Abfrage hätten sonst zwei Tabellen ein „id“.
    where, args = "t.lehrgang_id = ?", [lid]
    if nur_tid is not None:
        where += " AND t.id = ?"
        args.append(nur_tid)
    tn = db.query(f"SELECT t.* FROM pruef_teilnehmer t WHERE {where} "
                  "ORDER BY t.sortierung, t.name COLLATE NOCASE, t.vorname COLLATE NOCASE", args)
    anzahl_v = db.query("SELECT COUNT(*) AS n FROM pruef_voraussetzungen WHERE lehrgang_id = ?", (lid,), one=True)["n"]
    status = {}
    for s in db.query("SELECT s.* FROM pruef_voraussetzung_status s "
                      "JOIN pruef_teilnehmer t ON t.id = s.teilnehmer_id WHERE " + where, args):
        status.setdefault(s["teilnehmer_id"], {})[str(s["voraussetzung_id"])] = {
            "erfuellt": bool(s["erfuellt"]), "gesetzt_von_name": s["gesetzt_von_name"],
            "gesetzt_am": s["gesetzt_am"], "quelle": s["quelle"]}
    # Zellen: aufsteigend nach versuch_nr, damit der letzte Versuch am Ende gewinnt.
    zellen = {}
    for v in db.query("SELECT v.* FROM pruef_versuche v JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id "
                      "WHERE " + where + " ORDER BY v.versuch_nr", args):
        z = zellen.setdefault(v["teilnehmer_id"], {}).setdefault(str(v["leistung_id"]), {"versuche": 0, "medien_anzahl": 0})
        z["versuche"] += 1
        z.update({"status": _zellstatus(v), "letzter_versuch_id": v["id"], "letztes_ergebnis": v["ergebnis"],
                  "letzte_zeit_sekunden": v["zeit_sekunden"], "letzter_kommentar": v["kommentar"],
                  "geprueft_von_name": v["geprueft_von_name"], "geprueft_am": v["geprueft_am"]})
    # Anhänge je Zelle über alle Versuche – die Übersichten zeigen dafür eine Büroklammer.
    for m in db.query("SELECT v.teilnehmer_id, v.leistung_id, COUNT(*) AS n FROM pruef_medien m "
                      "JOIN pruef_versuche v ON v.id = m.versuch_id JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id "
                      "WHERE " + where + " GROUP BY v.teilnehmer_id, v.leistung_id", args):
        z = zellen.get(m["teilnehmer_id"], {}).get(str(m["leistung_id"]))
        if z:
            z["medien_anzahl"] = m["n"]
    out = []
    for t in tn:
        vs = status.get(t["id"], {})
        erfuellt = sum(1 for s in vs.values() if s["erfuellt"])
        out.append({
            "id": t["id"], "name": t["name"], "vorname": t["vorname"], "geburtsdatum": t["geburtsdatum"],
            "gliederung": t["gliederung"], "email": t["email"], "bemerkung": t["bemerkung"],
            "extra": _extra(t["extra"]), "sortierung": t["sortierung"],
            "bild": _bild_url(t["bild"]), "kommentar": t["kommentar"],
            "ergebnis": t["ergebnis"], "ergebnis_von_name": t["ergebnis_von_name"], "ergebnis_am": t["ergebnis_am"],
            "eingefroren": bool(t["ergebnis"]),
            "voraussetzungen": vs, "voraussetzungen_offen": max(0, anzahl_v - erfuellt),
            "leistungen": zellen.get(t["id"], {})})
    return out


def _tn_json(tid):
    t = _tn(tid)
    return _teilnehmer_liste(t["lehrgang_id"], nur_tid=tid)[0]


# Lehrgang mit Fortschrittszahlen. Alles als Unterabfragen, damit die Liste eine Abfrage bleibt.
# Eine „Zelle“ ist ein Paar (Teilnehmer, Leistung); abgenommen heißt: mindestens ein Versuch.
# Offener Mangel: der Versuch mit der höchsten Nummer seiner Zelle ist mangelhaft.
_LEHRGANG_SQL = (
    "SELECT l.*, "
    "  (SELECT COUNT(*) FROM pruef_teilnehmer t WHERE t.lehrgang_id = l.id) AS tn_anzahl, "
    "  (SELECT COUNT(*) FROM pruef_leistungen p WHERE p.lehrgang_id = l.id) AS leistungen_anzahl, "
    "  (SELECT COUNT(DISTINCT v.teilnehmer_id || ':' || v.leistung_id) FROM pruef_versuche v "
    "     JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id WHERE t.lehrgang_id = l.id) AS zellen_abgenommen, "
    "  (SELECT COUNT(*) FROM pruef_versuche v JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id "
    "     WHERE t.lehrgang_id = l.id AND v.ergebnis = 'mangelhaft' "
    "       AND v.versuch_nr = (SELECT MAX(v2.versuch_nr) FROM pruef_versuche v2 "
    "                           WHERE v2.teilnehmer_id = v.teilnehmer_id AND v2.leistung_id = v.leistung_id)"
    "  ) AS offene_maengel, "
    "  (SELECT COUNT(*) FROM pruef_teilnehmer t WHERE t.lehrgang_id = l.id AND EXISTS ("
    "     SELECT 1 FROM pruef_voraussetzungen vo WHERE vo.lehrgang_id = l.id AND NOT EXISTS ("
    "       SELECT 1 FROM pruef_voraussetzung_status s WHERE s.teilnehmer_id = t.id "
    "         AND s.voraussetzung_id = vo.id AND s.erfuellt = 1))"
    "  ) AS voraussetzungen_offen, "
    "  (SELECT COUNT(*) FROM pruef_teilnehmer t WHERE t.lehrgang_id = l.id AND t.ergebnis = 'bestanden') AS ergebnis_bestanden, "
    "  (SELECT COUNT(*) FROM pruef_teilnehmer t WHERE t.lehrgang_id = l.id AND t.ergebnis = 'nicht_bestanden') AS ergebnis_nicht_bestanden "
    "FROM pruef_lehrgaenge l ")


def _lehrgang_kurz(r):
    out = {k: r[k] for k in ("id", "titel", "nummer", "datum_von", "datum_bis", "ort", "status", "created_by_name",
                             "created_at", "updated_at", "tn_anzahl", "leistungen_anzahl", "zellen_abgenommen",
                             "offene_maengel", "voraussetzungen_offen", "ergebnis_bestanden", "ergebnis_nicht_bestanden")}
    out["zellen_gesamt"] = r["tn_anzahl"] * r["leistungen_anzahl"]
    out["darf_leiten"] = _darf_leiten(r["id"])
    return out


def _lehrgang_detail(lid):
    r = db.query(_LEHRGANG_SQL + "WHERE l.id = ?", (lid,), one=True)
    if not r:
        raise Abgelehnt("Lehrgang nicht gefunden", 404)
    out = _lehrgang_kurz(r)
    out["beschreibung"] = r["beschreibung"]
    out["ausbilder"] = [dict(a, ist_leitung=bool(a["ist_leitung"])) for a in db.query(
        "SELECT id, user_id, name, funktion, ist_leitung FROM pruef_ausbilder WHERE lehrgang_id = ? "
        "ORDER BY sortierung, id", (lid,))]
    out["voraussetzungen"] = [_voraussetzung_json(v) for v in db.query(
        "SELECT * FROM pruef_voraussetzungen WHERE lehrgang_id = ? ORDER BY sortierung, id", (lid,))]
    out["leistungen"] = [_leistung_json(p) for p in db.query(
        "SELECT * FROM pruef_leistungen WHERE lehrgang_id = ? ORDER BY sortierung, id", (lid,))]
    out["teilnehmer"] = _teilnehmer_liste(lid)
    return out


def _medien_dateien(where, args):
    """Dateinamen aller Medien unter einer Bedingung – VOR dem Löschen einsammeln, weil die Zeilen
    per CASCADE mitgehen und danach niemand mehr weiß, welche Dateien dazugehörten."""
    return [m["file"] for m in db.query(
        "SELECT m.file FROM pruef_medien m JOIN pruef_versuche v ON v.id = m.versuch_id "
        "JOIN pruef_teilnehmer t ON t.id = v.teilnehmer_id WHERE " + where, args)]


def _bilder_loeschen(bilder):
    for b in bilder:
        try:
            delete_avatar(_medien_dir(), b)
        except OSError as exc:
            current_app.logger.warning("Profilbild %s ließ sich nicht löschen: %s", b, exc)


def _dateien_loeschen(dateien):
    """Mediendateien wegräumen, NACHDEM die Zeilen weg sind. Eine Datei, die sich nicht löschen
    lässt (Rechte, gerade geöffnet), darf weder die übrigen aufhalten noch die Antwort zu einem
    Fehler machen – der Datensatz ist ja korrekt gelöscht; der Rest steht im Protokoll."""
    for f in dateien:
        try:
            delete_photo_files(_medien_dir(), f)
        except OSError as exc:
            current_app.logger.warning("Prüfungsmedium %s ließ sich nicht löschen: %s", f, exc)


# --- 4.1 Nutzer (Ausbilder-Auswahl) -------------------------------------------------

@bp.get("/nutzer")
@pruefer_required
def nutzer():
    rows = db.query("SELECT id, name, gliederung FROM users WHERE active = 1 AND status = 'active' "
                    "ORDER BY name COLLATE NOCASE, id")
    return jsonify(nutzer=rows)


# --- 4.2 Lehrgänge -----------------------------------------------------------

def _lehrgang_felder(d, neu):
    """Textfelder, Daten und Status aus dem Body. Beim Anlegen alle Felder, beim Ändern nur die
    mitgeschickten – ein Aufruf, der bloß den Status setzt, darf nicht den Titel leeren."""
    vals = {}
    grenzen = {"titel": 200, "nummer": 60, "ort": 200, "beschreibung": 20000}
    for feld, grenze in grenzen.items():
        if neu or feld in d:
            vals[feld] = sfield(d, feld).strip()[:grenze]
    if "titel" in vals and not vals["titel"]:
        raise Abgelehnt("Bitte einen Titel angeben.")
    for feld, label in (("datum_von", "Datum von"), ("datum_bis", "Datum bis")):
        if neu or feld in d:
            vals[feld] = _datum(d.get(feld), label)
    if neu or "status" in d:
        status = sfield(d, "status").strip()
        vals["status"] = status if status in STATUS_WERTE else "geplant"
    return vals


def _zeitraum_pruefen(von, bis):
    if von and bis and bis < von:
        raise Abgelehnt("„Datum bis“ liegt vor „Datum von“.")


def _ausbilder_liste(roh):
    """Ausbilder aus dem Body: (user_id|None, name, funktion, ist_leitung). Ein Verweis auf ein Nutzerkonto
    zieht dessen Namen, wenn keiner mitkommt; ein unbekanntes Konto wird zum Freitext –
    so bleibt der Eintrag erhalten, auch wenn die Kennung nicht (mehr) stimmt."""
    if roh is None:
        return []
    if not isinstance(roh, list) or len(roh) > 100:
        raise Abgelehnt("„ausbilder“ muss eine Liste sein.")
    out = []
    for e in roh:
        if not isinstance(e, dict):
            continue
        name = sfield(e, "name").strip()[:120]
        funktion = sfield(e, "funktion").strip()[:80]
        # Das Kennzeichen kommt aus dem Dialog. Fehlt es (ältere Aufrufe), zählt wie bisher ein „leit“
        # in der Funktion – so bleibt ein Aufruf mit funktion="Lehrgangsleitung" weiter gültig.
        leit = _bool(e, "ist_leitung") if "ist_leitung" in e else _ist_leitungsfunktion(funktion)
        uid, user = e.get("user_id"), None
        if uid not in (None, "") and not isinstance(uid, bool):
            try:
                uid = int(uid)
            except (TypeError, ValueError, OverflowError):
                uid = None
            else:
                user = db.query("SELECT name, email FROM users WHERE id = ?", (uid,), one=True)
        if user:
            name = name or user["name"] or user["email"]
        else:
            uid = None
        if name:
            out.append((uid, name, funktion, int(leit)))
    return out


def _ausbilder_schreiben(lid, ausbilder):
    db.execute("DELETE FROM pruef_ausbilder WHERE lehrgang_id = ?", (lid,))
    for i, (uid, name, funktion, leit) in enumerate(ausbilder):
        db.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, ist_leitung, sortierung) "
                   "VALUES (?,?,?,?,?,?)", (lid, uid, name, funktion, leit, i))


@bp.get("/lehrgaenge")
@pruefer_required
def list_lehrgaenge():
    """Alle Lehrgänge, neueste zuerst (ohne Datum ganz hinten). Das Jahr filtert die Datenbank;
    die Textsuche läuft in Python: SQLites lower() kennt nur ASCII, „Köln“ fände „köln“ nicht."""
    jahr = (request.args.get("jahr") or "").strip()
    q = (request.args.get("q") or "").strip().casefold()
    where, args = "", []
    if jahr:
        if not re.fullmatch(r"\d{4}", jahr):
            raise Abgelehnt("„jahr“ muss vierstellig sein.")
        where, args = "WHERE substr(l.datum_von, 1, 4) = ? ", [jahr]
    rows = db.query(_LEHRGANG_SQL + where + "ORDER BY (l.datum_von IS NULL), l.datum_von DESC, l.id DESC", args)
    if q:
        rows = [r for r in rows if q in f"{r['titel']} {r['nummer']} {r['ort']}".casefold()]
    return jsonify(lehrgaenge=[_lehrgang_kurz(r) for r in rows])


@bp.post("/lehrgaenge")
@pruefer_required
def create_lehrgang():
    d = json_body()
    vals = _lehrgang_felder(d, neu=True)
    _zeitraum_pruefen(vals["datum_von"], vals["datum_bis"])
    ausbilder = _leitung_ergaenzen(_ausbilder_liste(d.get("ausbilder")))
    # Katalog als Vorlage (optional): seine Leistungen werden gleich unten hineinkopiert, nicht
    # verlinkt – wie bei kopieren(). Erst hier nachschlagen, damit ein unbekannter Katalog den
    # Lehrgang gar nicht erst halb anlegt.
    katalog = _katalog(_ganzzahl(d["katalog_id"], "Katalog")) if d.get("katalog_id") not in (None, "") else None
    uid, name = _ich()
    ts = db.now()
    with db.transaction():
        lid = db.execute(
            "INSERT INTO pruef_lehrgaenge (titel, nummer, datum_von, datum_bis, ort, beschreibung, status, "
            "created_by, created_by_name, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (vals["titel"], vals["nummer"], vals["datum_von"], vals["datum_bis"], vals["ort"],
             vals["beschreibung"], vals["status"], uid, name, ts, ts))
        _ausbilder_schreiben(lid, ausbilder)
        if katalog:
            for i, p in enumerate(db.query("SELECT * FROM pruef_katalog_leistungen WHERE katalog_id = ? "
                                           "ORDER BY sortierung, id", (katalog["id"],))):
                db.execute("INSERT INTO pruef_leistungen (lehrgang_id, bezeichnung, beschreibung_md, "
                          "zeitansatz_sekunden, sortierung) VALUES (?,?,?,?,?)",
                          (lid, p["bezeichnung"], p["beschreibung_md"], p["zeitansatz_sekunden"], i))
    return jsonify(lehrgang=_lehrgang_detail(lid)), 201


@bp.get("/lehrgaenge/<int:lid>")
@pruefer_required
def get_lehrgang(lid):
    return jsonify(lehrgang=_lehrgang_detail(lid))


@bp.put("/lehrgaenge/<int:lid>")
@pruefer_required
def update_lehrgang(lid):
    alt = _lehrgang(lid)
    _leitung(lid)
    d = json_body()
    vals = _lehrgang_felder(d, neu=False)
    _zeitraum_pruefen(vals.get("datum_von", alt["datum_von"]), vals.get("datum_bis", alt["datum_bis"]))
    # Die Liste wird komplett ersetzt: So ist „Zeile entfernt“ im Dialog eindeutig. Die bearbeitende
    # Leitung bleibt dabei eingetragen – wer sich selbst vergisst, stünde sonst sofort ohne Rechte da.
    ausbilder = _leitung_ergaenzen(_ausbilder_liste(d.get("ausbilder"))) if "ausbilder" in d else None
    with db.transaction():
        if vals:
            sets = ", ".join(f"{k} = ?" for k in vals) + ", updated_at = ?"
            db.execute(f"UPDATE pruef_lehrgaenge SET {sets} WHERE id = ?", (*vals.values(), db.now(), lid))
        if ausbilder is not None:
            _ausbilder_schreiben(lid, ausbilder)
            db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (db.now(), lid))
    return jsonify(lehrgang=_lehrgang_detail(lid))


@bp.delete("/lehrgaenge/<int:lid>")
@pruefer_required
def delete_lehrgang(lid):
    _lehrgang(lid)
    _leitung(lid)
    dateien = _medien_dateien("t.lehrgang_id = ?", (lid,))
    bilder = [t["bild"] for t in db.query("SELECT bild FROM pruef_teilnehmer WHERE lehrgang_id = ? AND bild != ''", (lid,))]
    with db.transaction():
        db.execute("DELETE FROM pruef_lehrgaenge WHERE id = ?", (lid,))
    # Dateien erst, wenn die Zeilen wirklich weg sind – sonst bliebe ein Lehrgang voller kaputter Bilder.
    _dateien_loeschen(dateien)
    _bilder_loeschen(bilder)
    return jsonify(ok=True)


@bp.post("/lehrgaenge/<int:lid>/kopieren")
@pruefer_required
def kopieren(lid):
    """Vorlage für den nächsten Durchgang: Stammdaten, Ausbilder, Voraussetzungs-Definitionen und
    Leistungen kommen mit – Teilnehmende, Haken, Bewertungen und Medien nicht. Die Lehrgangsnummer
    wird geleert: Sie bezeichnet eine Durchführung, nicht den Lehrgangstyp."""
    alt = _lehrgang(lid)
    _leitung(lid)
    d = json_body()
    titel = (sfield(d, "titel").strip() or f"{alt['titel'][:200 - len(' (Kopie)')]} (Kopie)")[:200]
    von, bis = _datum(d.get("datum_von"), "Datum von"), _datum(d.get("datum_bis"), "Datum bis")
    _zeitraum_pruefen(von, bis)
    uid, name = _ich()
    ts = db.now()
    with db.transaction():
        neu = db.execute(
            "INSERT INTO pruef_lehrgaenge (titel, nummer, datum_von, datum_bis, ort, beschreibung, status, "
            "created_by, created_by_name, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (titel, "", von, bis, alt["ort"], alt["beschreibung"], "geplant", uid, name, ts, ts))
        for a in db.query("SELECT * FROM pruef_ausbilder WHERE lehrgang_id = ? ORDER BY sortierung, id", (lid,)):
            db.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, ist_leitung, sortierung) "
                       "VALUES (?,?,?,?,?,?)", (neu, a["user_id"], a["name"], a["funktion"], a["ist_leitung"], a["sortierung"]))
        for v in db.query("SELECT * FROM pruef_voraussetzungen WHERE lehrgang_id = ? ORDER BY sortierung, id", (lid,)):
            db.execute("INSERT INTO pruef_voraussetzungen (lehrgang_id, bezeichnung, sortierung) VALUES (?,?,?)",
                       (neu, v["bezeichnung"], v["sortierung"]))
        for p in db.query("SELECT * FROM pruef_leistungen WHERE lehrgang_id = ? ORDER BY sortierung, id", (lid,)):
            db.execute("INSERT INTO pruef_leistungen (lehrgang_id, bezeichnung, beschreibung_md, zeitansatz_sekunden, "
                       "sortierung) VALUES (?,?,?,?,?)",
                       (neu, p["bezeichnung"], p["beschreibung_md"], p["zeitansatz_sekunden"], p["sortierung"]))
    return jsonify(lehrgang=_lehrgang_detail(neu)), 201


# --- 4.3 Teilnehmende --------------------------------------------------------

TN_GRENZEN = {"name": 120, "vorname": 120, "gliederung": 120, "email": 200, "bemerkung": 2000}


def _tn_felder(d, neu):
    vals = {}
    for feld, grenze in TN_GRENZEN.items():
        if neu or feld in d:
            vals[feld] = sfield(d, feld).strip()[:grenze]
    if "name" in vals and not vals["name"]:
        raise Abgelehnt("Bitte einen Nachnamen angeben.")
    if neu or "geburtsdatum" in d:
        vals["geburtsdatum"] = _datum(d.get("geburtsdatum"), "Geburtsdatum")
    return vals


def _naechste_sortierung(tabelle, lid):
    return db.query(f"SELECT COALESCE(MAX(sortierung), -1) + 1 AS n FROM {tabelle} WHERE lehrgang_id = ?",
                    (lid,), one=True)["n"]


@bp.post("/lehrgaenge/<int:lid>/teilnehmer")
@pruefer_required
def create_teilnehmer(lid):
    _lehrgang(lid)
    _leitung(lid)
    vals = _tn_felder(json_body(), neu=True)
    with db.transaction():
        tid = db.execute(
            "INSERT INTO pruef_teilnehmer (lehrgang_id, name, vorname, geburtsdatum, gliederung, email, bemerkung, "
            "extra, sortierung, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lid, vals["name"], vals["vorname"], vals["geburtsdatum"], vals["gliederung"], vals["email"],
             vals["bemerkung"], "{}", _naechste_sortierung("pruef_teilnehmer", lid), db.now()))
        db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (db.now(), lid))
    return jsonify(teilnehmer=_tn_json(tid)), 201


@bp.put("/teilnehmer/<int:tid>")
@pruefer_required
def update_teilnehmer(tid):
    t = _tn(tid)
    _leitung(t["lehrgang_id"])
    d = json_body()
    vals = _tn_felder(d, neu=False)
    if "sortierung" in d:
        vals["sortierung"] = _ganzzahl(d.get("sortierung"), "sortierung")
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        with db.transaction():
            db.execute(f"UPDATE pruef_teilnehmer SET {sets} WHERE id = ?", (*vals.values(), tid))
            db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (db.now(), t["lehrgang_id"]))
    return jsonify(teilnehmer=_tn_json(tid))


@bp.delete("/teilnehmer/<int:tid>")
@pruefer_required
def delete_teilnehmer(tid):
    t = _tn(tid)
    _leitung(t["lehrgang_id"])
    dateien = _medien_dateien("v.teilnehmer_id = ?", (tid,))
    with db.transaction():
        db.execute("DELETE FROM pruef_teilnehmer WHERE id = ?", (tid,))
        db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (db.now(), t["lehrgang_id"]))
    _dateien_loeschen(dateien)
    _bilder_loeschen([t["bild"]] if t["bild"] else [])
    return jsonify(ok=True)


@bp.post("/teilnehmer/<int:tid>/bild")
@pruefer_required
def upload_tn_bild(tid):
    """Profilbild einer teilnehmenden Person – wie das Profilbild der Nutzer: quadratisch auf Maß
    gebracht, ohne Aufnahmedaten. Das vorige Bild fällt erst weg, wenn das neue in der Zeile steht."""
    t = _tn(tid)
    _leitung(t["lehrgang_id"])
    f = request.files.get("file")
    if not f or not f.filename:
        raise Abgelehnt("Es wurde keine Datei mitgeschickt.")
    try:
        name = store_avatar(f, _medien_dir())
    except BildFehler as exc:
        raise Abgelehnt(str(exc))
    with db.transaction():
        db.execute("UPDATE pruef_teilnehmer SET bild = ? WHERE id = ?", (name, tid))
    _bilder_loeschen([t["bild"]] if t["bild"] else [])
    return jsonify(teilnehmer=_tn_json(tid))


@bp.delete("/teilnehmer/<int:tid>/bild")
@pruefer_required
def delete_tn_bild(tid):
    t = _tn(tid)
    _leitung(t["lehrgang_id"])
    with db.transaction():
        db.execute("UPDATE pruef_teilnehmer SET bild = '' WHERE id = ?", (tid,))
    _bilder_loeschen([t["bild"]] if t["bild"] else [])
    return jsonify(teilnehmer=_tn_json(tid))


@bp.put("/teilnehmer/<int:tid>/kommentar")
@pruefer_required
def set_tn_kommentar(tid):
    """Freier Kommentar der Prüfenden zur Person – Beobachtungen, die zu keiner einzelnen
    Leistung gehören. Für alle Prüfenden, solange die Person nicht eingefroren ist."""
    t = _tn(tid)
    _eingefroren_pruefen(t)
    kommentar = sfield(json_body(), "kommentar").strip()[:5000]
    with db.transaction():
        db.execute("UPDATE pruef_teilnehmer SET kommentar = ? WHERE id = ?", (kommentar, tid))
        db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (db.now(), t["lehrgang_id"]))
    return jsonify(teilnehmer=_tn_json(tid))


@bp.put("/teilnehmer/<int:tid>/ergebnis")
@pruefer_required
def set_tn_ergebnis(tid):
    """Lehrgangsergebnis der Leitung: bestanden oder nicht bestanden – oder null zum Aufheben.
    Mit dem Ergebnis sind die Prüfungsdaten der Person eingefroren: Was im Abschlussgespräch
    besprochen wurde, darf sich hinterher nicht mehr stillschweigend ändern."""
    t = _tn(tid)
    _leitung(t["lehrgang_id"])
    d = json_body()
    ergebnis = d.get("ergebnis")
    if ergebnis in (None, ""):
        vals = (None, None, "", None)
    elif ergebnis in ERGEBNISSE_LEHRGANG:
        uid, name = _ich()
        vals = (ergebnis, uid, name, db.now())
    else:
        raise Abgelehnt("Das Ergebnis muss „bestanden“, „nicht_bestanden“ oder leer sein.")
    with db.transaction():
        db.execute("UPDATE pruef_teilnehmer SET ergebnis = ?, ergebnis_von = ?, ergebnis_von_name = ?, ergebnis_am = ? "
                   "WHERE id = ?", (*vals, tid))
        db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (db.now(), t["lehrgang_id"]))
    return jsonify(teilnehmer=_tn_json(tid))


@bp.get("/teilnehmer/<int:tid>/versuche")
@pruefer_required
def tn_versuche(tid):
    """Alle Bewertungen einer Person – auch die bestandenen mit ihren Kommentaren, für das
    Abschlussgespräch."""
    rows = db.query(_VERSUCH_SQL + "WHERE v.teilnehmer_id = ? ORDER BY p.sortierung, p.id, v.versuch_nr", (tid,))
    return jsonify(teilnehmer=_tn_json(tid), versuche=_versuche_json(rows))


# --- 4.4 Voraussetzungen -----------------------------------------------------

@bp.post("/lehrgaenge/<int:lid>/voraussetzungen")
@pruefer_required
def create_voraussetzung(lid):
    _lehrgang(lid)
    _leitung(lid)
    bez = sfield(json_body(), "bezeichnung").strip()[:300]
    if not bez:
        raise Abgelehnt("Bitte eine Bezeichnung angeben.")
    vid = db.execute("INSERT INTO pruef_voraussetzungen (lehrgang_id, bezeichnung, sortierung) VALUES (?,?,?)",
                     (lid, bez, _naechste_sortierung("pruef_voraussetzungen", lid)))
    return jsonify(voraussetzung=_voraussetzung_json(_voraussetzung(vid))), 201


@bp.put("/voraussetzungen/<int:vid>")
@pruefer_required
def update_voraussetzung(vid):
    _leitung(_voraussetzung(vid)["lehrgang_id"])
    bez = sfield(json_body(), "bezeichnung").strip()[:300]
    if not bez:
        raise Abgelehnt("Die Bezeichnung darf nicht leer sein.")
    db.execute("UPDATE pruef_voraussetzungen SET bezeichnung = ? WHERE id = ?", (bez, vid))
    return jsonify(voraussetzung=_voraussetzung_json(_voraussetzung(vid)))


@bp.delete("/voraussetzungen/<int:vid>")
@pruefer_required
def delete_voraussetzung(vid):
    _leitung(_voraussetzung(vid)["lehrgang_id"])
    with db.transaction():
        db.execute("DELETE FROM pruef_voraussetzungen WHERE id = ?", (vid,))
    return jsonify(ok=True)


def _reihenfolge(tabelle, lid, ids):
    """sortierung = Stelle in der Liste; nur Zeilen dieses Lehrgangs – eine fremde Kennung in der
    Liste darf keine andere Veranstaltung umsortieren."""
    with db.transaction():
        for i, kennung in enumerate(ids):
            db.execute(f"UPDATE {tabelle} SET sortierung = ? WHERE id = ? AND lehrgang_id = ?", (i, kennung, lid))


@bp.put("/lehrgaenge/<int:lid>/voraussetzungen/reihenfolge")
@pruefer_required
def reihenfolge_voraussetzungen(lid):
    _lehrgang(lid)
    _leitung(lid)
    _reihenfolge("pruef_voraussetzungen", lid, _id_liste(json_body().get("ids")))
    return jsonify(ok=True)


@bp.put("/teilnehmer/<int:tid>/voraussetzungen/<int:vid>")
@pruefer_required
def set_voraussetzung_status(tid, vid):
    """Haken setzen oder entfernen. Der aktuelle Stand wird überschrieben (UPSERT), jeder Vorgang
    wandert zusätzlich in den Verlauf – auch das Entfernen bleibt so nachlesbar."""
    t, v = _tn(tid), _voraussetzung(vid)
    if t["lehrgang_id"] != v["lehrgang_id"]:
        raise Abgelehnt("Die Voraussetzung gehört nicht zum Lehrgang dieser Person.")
    _eingefroren_pruefen(t)
    erfuellt = 1 if _bool(json_body(), "erfuellt") else 0
    uid, name = _ich()
    ts = db.now()
    with db.transaction():
        db.execute(
            "INSERT INTO pruef_voraussetzung_status (teilnehmer_id, voraussetzung_id, erfuellt, gesetzt_von, "
            "gesetzt_von_name, gesetzt_am, quelle) VALUES (?,?,?,?,?,?,'manuell') "
            "ON CONFLICT(teilnehmer_id, voraussetzung_id) DO UPDATE SET erfuellt = excluded.erfuellt, "
            "gesetzt_von = excluded.gesetzt_von, gesetzt_von_name = excluded.gesetzt_von_name, "
            "gesetzt_am = excluded.gesetzt_am, quelle = excluded.quelle",
            (tid, vid, erfuellt, uid, name, ts))
        db.execute("INSERT INTO pruef_voraussetzung_verlauf (teilnehmer_id, voraussetzung_id, erfuellt, user_id, "
                   "user_name, zeit, quelle) VALUES (?,?,?,?,?,?,'manuell')", (tid, vid, erfuellt, uid, name, ts))
    return jsonify(status={"erfuellt": bool(erfuellt), "gesetzt_von_name": name, "gesetzt_am": ts,
                           "quelle": "manuell"})


@bp.get("/teilnehmer/<int:tid>/voraussetzungen/<int:vid>/verlauf")
@pruefer_required
def voraussetzung_verlauf(tid, vid):
    _tn(tid)
    _voraussetzung(vid)
    rows = db.query("SELECT erfuellt, user_name, zeit, quelle FROM pruef_voraussetzung_verlauf "
                    "WHERE teilnehmer_id = ? AND voraussetzung_id = ? ORDER BY zeit DESC, id DESC", (tid, vid))
    for r in rows:
        r["erfuellt"] = bool(r["erfuellt"])
    return jsonify(verlauf=rows)


# --- 4.5 Prüfungsleistungen --------------------------------------------------

def _leistung_felder(d, neu):
    vals = {}
    if neu or "bezeichnung" in d:
        vals["bezeichnung"] = sfield(d, "bezeichnung").strip()[:300]
        if not vals["bezeichnung"]:
            raise Abgelehnt("Bitte eine Bezeichnung angeben.")
    if neu or "beschreibung_md" in d:
        vals["beschreibung_md"] = sfield(d, "beschreibung_md")[:50000]
    if neu or "zeitansatz_sekunden" in d:
        vals["zeitansatz_sekunden"] = _sekunden(d.get("zeitansatz_sekunden"), "Zeitansatz")
    return vals


@bp.post("/lehrgaenge/<int:lid>/leistungen")
@pruefer_required
def create_leistung(lid):
    _lehrgang(lid)
    _leitung(lid)
    vals = _leistung_felder(json_body(), neu=True)
    pid = db.execute(
        "INSERT INTO pruef_leistungen (lehrgang_id, bezeichnung, beschreibung_md, zeitansatz_sekunden, sortierung) "
        "VALUES (?,?,?,?,?)", (lid, vals["bezeichnung"], vals["beschreibung_md"], vals["zeitansatz_sekunden"],
                               _naechste_sortierung("pruef_leistungen", lid)))
    return jsonify(leistung=_leistung_json(_leistung(pid))), 201


@bp.put("/leistungen/<int:lid>")
@pruefer_required
def update_leistung(lid):
    _leitung(_leistung(lid)["lehrgang_id"])
    vals = _leistung_felder(json_body(), neu=False)
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        db.execute(f"UPDATE pruef_leistungen SET {sets} WHERE id = ?", (*vals.values(), lid))
    return jsonify(leistung=_leistung_json(_leistung(lid)))


@bp.delete("/leistungen/<int:lid>")
@pruefer_required
def delete_leistung(lid):
    _leitung(_leistung(lid)["lehrgang_id"])
    dateien = _medien_dateien("v.leistung_id = ?", (lid,))
    with db.transaction():
        db.execute("DELETE FROM pruef_leistungen WHERE id = ?", (lid,))
    _dateien_loeschen(dateien)
    return jsonify(ok=True)


@bp.put("/lehrgaenge/<int:lid>/leistungen/reihenfolge")
@pruefer_required
def reihenfolge_leistungen(lid):
    _lehrgang(lid)
    _leitung(lid)
    _reihenfolge("pruef_leistungen", lid, _id_liste(json_body().get("ids")))
    return jsonify(ok=True)


# --- 4.6 Versuche (Bewertungen) ----------------------------------------------

def _zelle(tid, lid):
    """Teilnehmer und Leistung einer Zelle – beide müssen zum selben Lehrgang gehören."""
    t, p = _tn(tid), _leistung(lid)
    if t["lehrgang_id"] != p["lehrgang_id"]:
        raise Abgelehnt("Die Prüfungsleistung gehört nicht zum Lehrgang dieser Person.")
    return t, p


def _zellen_versuche(tid, lid):
    return db.query(_VERSUCH_SQL + "WHERE v.teilnehmer_id = ? AND v.leistung_id = ? ORDER BY v.versuch_nr", (tid, lid))


def _bewertung_pruefen(ergebnis, kommentar):
    if ergebnis not in ERGEBNISSE:
        raise Abgelehnt("Bitte „bestanden“ oder „mangelhaft“ wählen.")
    if ergebnis == "mangelhaft" and not kommentar:
        raise Abgelehnt(KOMMENTAR_PFLICHT)


@bp.get("/teilnehmer/<int:tid>/leistungen/<int:lid>/versuche")
@pruefer_required
def zelle_versuche(tid, lid):
    _, p = _zelle(tid, lid)
    rows = _zellen_versuche(tid, lid)
    return jsonify(versuche=_versuche_json(rows), status=_zellstatus(rows[-1] if rows else None),
                   teilnehmer=_tn_json(tid), leistung=_leistung_json(p))


@bp.post("/teilnehmer/<int:tid>/leistungen/<int:lid>/versuche")
@pruefer_required
def create_versuch(tid, lid):
    """Bewertung anlegen. Der erste Versuch ist die Prüfung; jeder weitere ist eine Nachprüfung und
    nur nach einem mangelhaften Versuch erlaubt. Der Erstversuch bleibt unangetastet stehen."""
    t, _ = _zelle(tid, lid)
    _eingefroren_pruefen(t)
    d = json_body()
    ergebnis = sfield(d, "ergebnis").strip()
    kommentar = sfield(d, "kommentar").strip()[:5000]
    _bewertung_pruefen(ergebnis, kommentar)
    zeit = _sekunden(d.get("zeit_sekunden"))
    bisher = _zellen_versuche(tid, lid)
    if bisher:
        if not _bool(d, "nachpruefung"):
            raise Abgelehnt(SCHON_BEWERTET, 409)
        if bisher[-1]["ergebnis"] != "mangelhaft":
            raise Abgelehnt(NUR_NACH_MANGEL, 409)
        nr, nachpruefung = bisher[-1]["versuch_nr"] + 1, 1
    else:
        nr, nachpruefung = 1, 0
    uid, name = _ich()
    try:
        vid = db.execute(
            "INSERT INTO pruef_versuche (teilnehmer_id, leistung_id, versuch_nr, ist_nachpruefung, ergebnis, "
            "zeit_sekunden, kommentar, geprueft_von, geprueft_von_name, geprueft_am) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tid, lid, nr, nachpruefung, ergebnis, zeit, kommentar, uid, name, db.now()))
    except sqlite3.IntegrityError as exc:
        # Zwei Prüfer speichern dieselbe Zelle im selben Augenblick: UNIQUE(teilnehmer, leistung, nr)
        # fängt den zweiten ab – er bekommt dieselbe Auskunft wie beim nachträglichen Versuch.
        # Ein Fremdschlüsselfehler heißt dagegen: Person oder Leistung ist gerade gelöscht worden.
        if "UNIQUE" in str(exc).upper():
            raise Abgelehnt(SCHON_BEWERTET, 409)
        raise Abgelehnt(GERADE_GELOESCHT, 409)
    return jsonify(versuch=_versuch_json(_versuch(vid))), 201


@bp.put("/versuche/<int:vid>")
@pruefer_required
def update_versuch(vid):
    """Bewertung ändern. Der bisherige Stand wandert in den Verlauf – mit dem, der ihn geschrieben
    hatte, und dem Zeitraum, in dem er galt; die Zeile bekommt „bearbeitet von … am …“."""
    v = _versuch(vid)
    _eingefroren_pruefen(_tn(v["teilnehmer_id"]))
    d = json_body()
    ergebnis = sfield(d, "ergebnis").strip() if "ergebnis" in d else v["ergebnis"]
    kommentar = sfield(d, "kommentar").strip()[:5000] if "kommentar" in d else v["kommentar"]
    zeit = _sekunden(d.get("zeit_sekunden")) if "zeit_sekunden" in d else v["zeit_sekunden"]
    _bewertung_pruefen(ergebnis, kommentar)
    if (ergebnis, kommentar, zeit) == (v["ergebnis"], v["kommentar"], v["zeit_sekunden"]):
        return jsonify(versuch=_versuch_json(v))      # nichts geändert – kein Verlaufseintrag
    # Sonst stünde eine Nachprüfung hinter einer bestandenen Prüfung – ein Stand, den es beim
    # Anlegen nie geben kann und den die Mängelübersicht nicht deuten könnte. Die Bedingung
    # steckt im UPDATE selbst: Zwischen einer getrennten Abfrage und dem Schreiben könnte ein
    # zweiter Prüfer gerade die Nachprüfung anlegen.
    keine_spaetere = ergebnis == "bestanden" and v["ergebnis"] != "bestanden"
    KEIN_SPAETERER = ("Auf diese Bewertung folgt schon eine Nachprüfung – sie lässt sich nicht mehr auf "
                      "„bestanden“ ändern. Bitte zuerst die Nachprüfung löschen.")
    uid, name = _ich()
    ts = db.now()
    with db.transaction():
        bedingung = (" AND NOT EXISTS (SELECT 1 FROM pruef_versuche s WHERE s.teilnehmer_id = ? AND s.leistung_id = ? "
                     "AND s.versuch_nr > ?)" if keine_spaetere else "")
        args = (v["teilnehmer_id"], v["leistung_id"], v["versuch_nr"]) if keine_spaetere else ()
        # Wer den alten Stand geschrieben hatte: der letzte Bearbeiter, sonst der Prüfer.
        alt_von = v["bearbeitet_von"] if v["bearbeitet_am"] else v["geprueft_von"]
        alt_name = v["bearbeitet_von_name"] if v["bearbeitet_am"] else v["geprueft_von_name"]
        # Bedingt schreiben – und nur wenn geschrieben wurde, gehört der alte Stand in den Verlauf.
        # Der Vergleich mit dem gelesenen Stand fängt zugleich zwei gleichzeitige Bearbeitungen:
        # Der zweite trifft die Zeile nicht mehr und bekommt den Hinweis statt eines stummen Verlusts.
        n = db.execute_zeilen(
            "UPDATE pruef_versuche SET ergebnis = ?, zeit_sekunden = ?, kommentar = ?, bearbeitet_von = ?, "
            "bearbeitet_von_name = ?, bearbeitet_am = ? WHERE id = ? AND ergebnis = ? AND kommentar = ? "
            "AND COALESCE(bearbeitet_am, '') = COALESCE(?, '')" + bedingung,
            (ergebnis, zeit, kommentar, uid, name, ts, vid, v["ergebnis"], v["kommentar"], v["bearbeitet_am"], *args))
        if not n:
            if keine_spaetere and db.query("SELECT 1 FROM pruef_versuche WHERE teilnehmer_id = ? AND leistung_id = ? "
                                           "AND versuch_nr > ?", args, one=True):
                raise Abgelehnt(KEIN_SPAETERER, 409)
            raise Abgelehnt("Diese Bewertung wurde inzwischen von jemand anderem geändert – bitte die Seite neu "
                            "laden und die Änderung noch einmal eintragen.", 409)
        db.execute("INSERT INTO pruef_versuch_verlauf (versuch_id, ergebnis, zeit_sekunden, kommentar, von_user_id, "
                   "von_name, stand_ab, ersetzt_am) VALUES (?,?,?,?,?,?,?,?)",
                   (vid, v["ergebnis"], v["zeit_sekunden"], v["kommentar"], alt_von, alt_name,
                    v["bearbeitet_am"] or v["geprueft_am"], ts))
    return jsonify(versuch=_versuch_json(_versuch(vid)))


@bp.delete("/versuche/<int:vid>")
@pruefer_required
def delete_versuch(vid):
    """Nur der letzte Versuch einer Zelle darf weg: Ein Loch in der Reihe (Versuch 1 fehlt, Nach-
    prüfung 2 steht) wäre für niemanden mehr nachvollziehbar."""
    v = _versuch(vid)
    t = _tn(v["teilnehmer_id"])
    _leitung(t["lehrgang_id"])
    _eingefroren_pruefen(t)
    with db.transaction():
        dateien = [m["file"] for m in db.query("SELECT file FROM pruef_medien WHERE versuch_id = ?", (vid,))]
        # Die Bedingung „kein späterer Versuch“ steckt im DELETE: Eine getrennte Abfrage ließe
        # zwischen Prüfung und Löschen Platz für eine gleichzeitig angelegte Nachprüfung.
        n = db.execute_zeilen(
            "DELETE FROM pruef_versuche WHERE id = ? AND NOT EXISTS (SELECT 1 FROM pruef_versuche s "
            "WHERE s.teilnehmer_id = ? AND s.leistung_id = ? AND s.versuch_nr > ?)",
            (vid, v["teilnehmer_id"], v["leistung_id"], v["versuch_nr"]))
        if not n:
            raise Abgelehnt("Nur die letzte Bewertung einer Leistung kann gelöscht werden – bitte zuerst die "
                            "Nachprüfung löschen.", 409)
    _dateien_loeschen(dateien)
    return jsonify(ok=True)


@bp.post("/versuche/<int:vid>/medien")
@pruefer_required
def upload_medien(vid):
    """Fotos und Videos zu einer Bewertung. Fehler je Datei werden gesammelt, nicht geworfen –
    eine kaputte Datei darf die anderen nicht mitreißen. Standbilder zu Videos (posters) kommen
    in der Reihenfolge der Dateien vom Browser."""
    v = _versuch(vid)
    _eingefroren_pruefen(_tn(v["teilnehmer_id"]))
    files = request.files.getlist("files")
    if not files:
        raise Abgelehnt("Keine Dateien empfangen.")
    posters = request.files.getlist("posters")
    uid, name = _ich()
    medien, errors = [], []
    for i, f in enumerate(files):
        try:
            poster = posters[i] if i < len(posters) and posters[i].filename else None
            meta = store_upload(f, _medien_dir(), poster=poster)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        except Exception:
            # Der Grund steht im Protokoll – dem Nutzer nützen Serverpfade und Ausnahmetexte nichts.
            current_app.logger.exception("Upload von %s fehlgeschlagen", f.filename)
            errors.append(f"Die Datei „{f.filename or '?'}“ konnte nicht verarbeitet werden.")
            continue
        mid = db.execute(
            "INSERT INTO pruef_medien (versuch_id, file, kind, original_name, width, height, hochgeladen_von, "
            "hochgeladen_von_name, hochgeladen_am) VALUES (?,?,?,?,?,?,?,?,?)",
            (vid, meta["file"], meta["kind"], meta["original_name"], meta["width"], meta["height"], uid, name, db.now()))
        medien.append(_medium_json(_medium(mid)))
    return jsonify(medien=medien, errors=errors), 201


@bp.delete("/medien/<int:mid>")
@pruefer_required
def delete_medium(mid):
    m = _medium(mid)
    _eingefroren_pruefen(_tn(_versuch(m["versuch_id"])["teilnehmer_id"]))
    with db.transaction():
        db.execute("DELETE FROM pruef_medien WHERE id = ?", (mid,))
    _dateien_loeschen([m["file"]])
    return jsonify(ok=True)


# --- 4.7 Mängel / Feedback ---------------------------------------------------

@bp.get("/lehrgaenge/<int:lid>/maengel")
@pruefer_required
def maengel(lid):
    """Alle mangelhaften Versuche des Lehrgangs, je mit dem Stand der Nachprüfung. Gefiltert wird
    nach Teilnehmer und Leistung – beides schneidet ganze Zellen aus, nie einzelne Versuche einer
    Zelle, sodass der Nachprüfungsstand immer aus der vollständigen Zelle gerechnet wird."""
    _lehrgang(lid)
    where, args = ["t.lehrgang_id = ?"], [lid]
    for param, spalte, label in (("teilnehmer", "v.teilnehmer_id", "teilnehmer"), ("leistung", "v.leistung_id", "leistung")):
        wert = (request.args.get(param) or "").strip()
        if wert:
            where.append(f"{spalte} = ?")
            args.append(_ganzzahl(wert, label))
    nur_offen = (request.args.get("nur_offen") or "").strip().lower() in ("1", "true", "ja")
    rows = db.query(_VERSUCH_SQL + "WHERE " + " AND ".join(where) +
                    " ORDER BY t.name COLLATE NOCASE, t.vorname COLLATE NOCASE, t.id, p.sortierung, p.id, v.versuch_nr", args)
    zellen = {}
    for v in rows:
        zellen.setdefault((v["teilnehmer_id"], v["leistung_id"]), []).append(v)
    treffer = []
    for v in rows:
        if v["ergebnis"] != "mangelhaft":
            continue
        zelle = zellen[(v["teilnehmer_id"], v["leistung_id"])]
        letzter = zelle[-1]
        ist_letzter = letzter["id"] == v["id"]
        if ist_letzter:
            np_status = "offen"
        elif letzter["ergebnis"] == "bestanden":
            np_status = "bestanden"
        else:
            np_status = "erneut_mangelhaft"
        zellstatus = _zellstatus(letzter)
        if nur_offen and not (ist_letzter and zellstatus in ("mangelhaft", "nachpruefung_mangelhaft")):
            continue
        treffer.append((v, np_status, zellstatus))
    versuche = _versuche_json([t[0] for t in treffer])
    out = []
    for vj, (v, np_status, zellstatus) in zip(versuche, treffer):
        out.append({"versuch": vj,
                    "teilnehmer": {"id": v["teilnehmer_id"], "name": v["tn_name"], "vorname": v["tn_vorname"],
                                   "gliederung": v["tn_gliederung"]},
                    "leistung": {"id": v["leistung_id"], "bezeichnung": v["leistung_bezeichnung"],
                                 "zeitansatz_sekunden": v["zeitansatz_sekunden"]},
                    "nachpruefung_status": np_status, "zellstatus": zellstatus})
    return jsonify(
        maengel=out,
        teilnehmer=db.query("SELECT id, name, vorname FROM pruef_teilnehmer WHERE lehrgang_id = ? "
                            "ORDER BY sortierung, name COLLATE NOCASE, vorname COLLATE NOCASE", (lid,)),
        leistungen=db.query("SELECT id, bezeichnung FROM pruef_leistungen WHERE lehrgang_id = ? "
                            "ORDER BY sortierung, id", (lid,)))


# --- 4.8 Excel-Import --------------------------------------------------------

def _import_modul():
    """Das Import-Modul erst laden, wenn es gebraucht wird: Es zieht openpyxl nach, das jeder
    Gunicorn-Arbeitsprozess sonst beim Start lüde – für eine Funktion, die ein paarmal im Jahr
    läuft."""
    from . import pruefungen_import
    return pruefungen_import


def _import_eingaben():
    """Datei, Zielkurs und Spaltenzuordnung aus dem Multipart-Formular lesen (für Vorschau und
    Übernahme gleich). Liefert (FileStorage, lehrgang|None, zuordnung|None)."""
    f = request.files.get("file")
    if not f or not f.filename:
        raise Abgelehnt("Bitte eine Excel-Datei (.xlsx) auswählen.")
    if not f.filename.lower().endswith(".xlsx"):
        raise Abgelehnt("Nur Excel-Dateien im Format .xlsx lassen sich einlesen.")
    lehrgang = None
    lid = (request.form.get("lehrgang_id") or "").strip()
    if lid:
        lehrgang = _lehrgang(_ganzzahl(lid, "lehrgang_id"))
    zuordnung = None
    roh = (request.form.get("zuordnung") or "").strip()
    if roh:
        try:
            zuordnung = json.loads(roh)
        except ValueError:
            raise Abgelehnt("Die Spaltenzuordnung ist kein gültiges JSON.")
        if not isinstance(zuordnung, dict) or not all(isinstance(v, str) for v in zuordnung.values()):
            raise Abgelehnt("Die Spaltenzuordnung muss ein Objekt {Spaltenindex: Zuordnung} sein.")
    return f, lehrgang, zuordnung


def _analysieren(f, zuordnung):
    imp = _import_modul()
    try:
        return imp.analysieren(f.stream, zuordnung, f.filename)
    except imp.ImportFehler as exc:
        raise Abgelehnt(str(exc))
    except Exception as exc:
        # Alles, was openpyxl an einer kaputten Datei wirft, ist für den Nutzer ein Lesefehler –
        # der Grund steht im Protokoll.
        current_app.logger.warning("Excel-Import: %s ließ sich nicht lesen: %r", f.filename, exc)
        raise Abgelehnt("Die Datei ließ sich nicht als Excel-Arbeitsmappe lesen.")


def _tn_schluessel(lid):
    """(Schlüssel, Zeile) für alle Teilnehmenden eines Lehrgangs – der Abgleich beim Import."""
    imp = _import_modul()
    return [(imp.schluessel(t["vorname"], t["name"], t["geburtsdatum"]), t)
            for t in db.query("SELECT * FROM pruef_teilnehmer WHERE lehrgang_id = ?", (lid,))]


def _passende_tns(imp, bestand, tn):
    """Alle Teilnehmenden des Lehrgangs, auf die eine Dateizeile passt. Meist genau einer; ohne
    Geburtsdatum in der Datei können es bei Namensgleichheit zwei sein – dann wird nicht geraten."""
    key = imp.schluessel(tn.get("vorname") or "", tn.get("name") or "", tn.get("geburtsdatum"))
    return [zeile for alt_key, zeile in bestand if imp.passt(key, alt_key)]


def _passender_tn(imp, bestand, tn, warnungen=None):
    treffer = _passende_tns(imp, bestand, tn)
    if len(treffer) > 1:
        if warnungen is not None:
            warnungen.append(f"Zeile {tn.get('zeile')}: „{tn.get('vorname', '')} {tn.get('name', '')}“ passt auf "
                             f"{len(treffer)} Teilnehmende des Lehrgangs (Geburtsdatum fehlt in der Datei) – "
                             "die Zeile wird nicht übernommen. Bitte das Geburtsdatum ergänzen.")
        return "mehrdeutig"
    return treffer[0] if treffer else None


def _zeitraum_aus_datei(kopf, warnungen, alt_von=None, alt_bis=None):
    """Datum von/bis aus dem Kopfbereich – nur, wenn das Paar zusammen mit dem vorhandenen
    Stand stimmig ist. Ein verdrehter Zeitraum wird gedreht, ein unpassender nicht übernommen:
    Sonst ließe sich der Lehrgang danach nicht mehr speichern (PUT prüft das Paar)."""
    von, bis = kopf.get("datum_von"), kopf.get("datum_bis")
    if von and bis and bis < von:
        warnungen.append(f"Zeitraum in der Datei steht verdreht ({von} bis {bis}) – wurde gedreht.")
        von, bis = bis, von
    wirksam_von, wirksam_bis = alt_von or von, alt_bis or bis
    if wirksam_von and wirksam_bis and wirksam_bis < wirksam_von:
        warnungen.append("Der Zeitraum aus der Datei passt nicht zum vorhandenen Datum des Lehrgangs – "
                         "das Datum wurde nicht übernommen.")
        return None, None
    return von, bis


@bp.post("/import/vorschau")
@pruefer_required
def import_vorschau():
    """Datei auswerten, nichts speichern. Ergänzt zur reinen Analyse, was nur die Datenbank weiß:
    welche Teilnehmenden und Voraussetzungen es im Ziel-Lehrgang schon gibt."""
    f, lehrgang, zuordnung = _import_eingaben()
    imp = _import_modul()
    ergebnis = _analysieren(f, zuordnung)
    bestand = _tn_schluessel(lehrgang["id"]) if lehrgang else []
    vorhandene = {imp.normalisiert(v["bezeichnung"]) for v in db.query(
        "SELECT bezeichnung FROM pruef_voraussetzungen WHERE lehrgang_id = ?", (lehrgang["id"],))} if lehrgang else set()
    for tn in ergebnis["teilnehmer"]:
        treffer = _passender_tn(imp, bestand, tn, ergebnis["warnungen"])
        tn["vorhanden"] = treffer is not None
        tn["mehrdeutig"] = treffer == "mehrdeutig"
    for v in ergebnis["voraussetzungen"]:
        v["vorhanden"] = imp.normalisiert(v["bezeichnung"]) in vorhandene
    return jsonify(**ergebnis)


@bp.post("/import")
@pruefer_required
def import_uebernehmen():
    """Datei in die Datenbank übernehmen – als eine Transaktion, damit ein Fehler in Zeile 40
    nicht 39 halbe Teilnehmende hinterlässt. Bestehende Teilnehmende (gleicher Schlüssel) werden
    ergänzt statt verdoppelt; ein Haken aus der Datei setzt einen manuell gesetzten nie zurück."""
    f, lehrgang, zuordnung = _import_eingaben()
    if lehrgang is not None:
        _leitung(lehrgang["id"])
    imp = _import_modul()
    ergebnis = _analysieren(f, zuordnung)
    kopf = dict(ergebnis.get("lehrgang") or {})
    warnungen = list(ergebnis.get("warnungen") or [])
    if not ergebnis.get("teilnehmer") and not ergebnis.get("ausbilder"):
        raise Abgelehnt("Es gibt nichts zu übernehmen. " + " ".join(warnungen))
    uid, name = _ich()
    ts = db.now()
    angelegt = aktualisiert = voraussetzungen_neu = ausbilder_neu = 0
    with db.transaction():
        if lehrgang is None:
            titel = (kopf.get("titel") or "").strip()[:200] or os.path.splitext(os.path.basename(f.filename))[0][:200]
            von, bis = _zeitraum_aus_datei(kopf, warnungen)
            lid = db.execute(
                "INSERT INTO pruef_lehrgaenge (titel, nummer, datum_von, datum_bis, ort, beschreibung, status, "
                "created_by, created_by_name, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (titel, (kopf.get("nummer") or "")[:60], von, bis,
                 (kopf.get("ort") or "")[:200], "", "geplant", uid, name, ts, ts))
            _ausbilder_schreiben(lid, _leitung_ergaenzen([]))
        else:
            lid = lehrgang["id"]
            # Leere Lehrgangsfelder aus der Datei füllen, gefüllte nicht anfassen. Das Datumspaar
            # muss danach stimmig sein – sonst ließe sich der Lehrgang nicht mehr speichern.
            kopf["datum_von"], kopf["datum_bis"] = _zeitraum_aus_datei(
                kopf, warnungen, lehrgang.get("datum_von"), lehrgang.get("datum_bis"))
            grenzen = {"titel": 200, "nummer": 60, "ort": 200}
            vals = {feld: (kopf.get(feld)[:grenzen[feld]] if feld in grenzen else kopf.get(feld))
                    for feld in ("titel", "nummer", "datum_von", "datum_bis", "ort")
                    if not lehrgang.get(feld) and kopf.get(feld)}
            if vals:
                sets = ", ".join(f"{k} = ?" for k in vals)
                db.execute(f"UPDATE pruef_lehrgaenge SET {sets} WHERE id = ?", (*vals.values(), lid))
        db.execute("UPDATE pruef_lehrgaenge SET updated_at = ? WHERE id = ?", (ts, lid))

        # Voraussetzungs-Definitionen: gleichnamige wiederverwenden, fehlende hinten anhängen.
        defs = {imp.normalisiert(v["bezeichnung"]): v["id"] for v in db.query(
            "SELECT id, bezeichnung FROM pruef_voraussetzungen WHERE lehrgang_id = ?", (lid,))}
        spalte_zu_vid = {}
        for v in ergebnis.get("voraussetzungen") or []:
            bez = (v.get("bezeichnung") or "").strip()[:300]
            if not bez:
                continue
            norm = imp.normalisiert(bez)
            if norm not in defs:
                defs[norm] = db.execute(
                    "INSERT INTO pruef_voraussetzungen (lehrgang_id, bezeichnung, sortierung) VALUES (?,?,?)",
                    (lid, bez, _naechste_sortierung("pruef_voraussetzungen", lid)))
                voraussetzungen_neu += 1
            spalte_zu_vid[str(v["spaltenindex"])] = defs[norm]

        # Ausbilder: gleichnamige nicht doppelt.
        vorhandene_ausbilder = {imp.normalisiert(a["name"]) for a in db.query(
            "SELECT name FROM pruef_ausbilder WHERE lehrgang_id = ?", (lid,))}
        for a in ergebnis.get("ausbilder") or []:
            a_name = (a.get("name") or "").strip()[:120]
            if not a_name or imp.normalisiert(a_name) in vorhandene_ausbilder:
                continue
            funktion = (a.get("funktion") or "").strip()[:80]
            # Aus der ISC-Liste kommt die Leitung als Freitext ohne Konto – sichtbar, aber ohne Rechte.
            db.execute("INSERT INTO pruef_ausbilder (lehrgang_id, user_id, name, funktion, ist_leitung, sortierung) "
                       "VALUES (?,?,?,?,?,?)", (lid, None, a_name, funktion, int(_ist_leitungsfunktion(funktion)),
                                               _naechste_sortierung("pruef_ausbilder", lid)))
            vorhandene_ausbilder.add(imp.normalisiert(a_name))
            ausbilder_neu += 1

        # Teilnehmende
        bestand = _tn_schluessel(lid)
        sortierung = _naechste_sortierung("pruef_teilnehmer", lid)
        for tn in ergebnis.get("teilnehmer") or []:
            felder = {feld: (tn.get(feld) or "").strip()[:TN_GRENZEN[feld]] for feld in TN_GRENZEN}
            felder["geburtsdatum"] = tn.get("geburtsdatum") or None
            extra_neu = tn.get("extra") if isinstance(tn.get("extra"), dict) else {}
            alt = _passender_tn(imp, bestand, tn, warnungen)
            if alt == "mehrdeutig":
                continue
            if alt and alt.get("ergebnis"):
                warnungen.append(f"Zeile {tn.get('zeile')}: „{felder['vorname']} {felder['name']}“ hat schon ein "
                                 "Lehrgangsergebnis – eingefroren, nicht aktualisiert.")
                continue
            if alt:
                tid = alt["id"]
                vals = {k: v for k, v in felder.items() if v and not alt.get(k)}
                # Die Zusatzspalten stammen ohnehin aus der Datei: ein neuer Wert ersetzt den alten,
                # ein leerer lässt ihn stehen.
                extra = _extra(alt["extra"])
                extra.update({k: v for k, v in extra_neu.items() if v not in (None, "")})
                vals["extra"] = json.dumps(extra, ensure_ascii=False)
                sets = ", ".join(f"{k} = ?" for k in vals)
                db.execute(f"UPDATE pruef_teilnehmer SET {sets} WHERE id = ?", (*vals.values(), tid))
                aktualisiert += 1
            else:
                if not felder["name"]:
                    warnungen.append(f"Zeile {tn.get('zeile')}: kein Nachname – nicht übernommen.")
                    continue
                tid = db.execute(
                    "INSERT INTO pruef_teilnehmer (lehrgang_id, name, vorname, geburtsdatum, gliederung, email, "
                    "bemerkung, extra, sortierung, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (lid, felder["name"], felder["vorname"], felder["geburtsdatum"], felder["gliederung"],
                     felder["email"], felder["bemerkung"], json.dumps(extra_neu, ensure_ascii=False), sortierung, ts))
                sortierung += 1
                angelegt += 1
                neu = db.query("SELECT * FROM pruef_teilnehmer WHERE id = ?", (tid,), one=True)
                bestand.append((imp.schluessel(neu["vorname"], neu["name"], neu["geburtsdatum"]), neu))
            # Häkchen aus der Datei: nur setzen, nie zurücknehmen – und nur, wenn er noch nicht steht.
            for spalte, erfuellt in (tn.get("voraussetzungen") or {}).items():
                vid = spalte_zu_vid.get(str(spalte))
                if not vid or not erfuellt:
                    continue
                stand = db.query("SELECT erfuellt FROM pruef_voraussetzung_status WHERE teilnehmer_id = ? "
                                 "AND voraussetzung_id = ?", (tid, vid), one=True)
                if stand and stand["erfuellt"]:
                    continue
                db.execute(
                    "INSERT INTO pruef_voraussetzung_status (teilnehmer_id, voraussetzung_id, erfuellt, gesetzt_von, "
                    "gesetzt_von_name, gesetzt_am, quelle) VALUES (?,?,1,?,?,?,'import') "
                    "ON CONFLICT(teilnehmer_id, voraussetzung_id) DO UPDATE SET erfuellt = 1, "
                    "gesetzt_von = excluded.gesetzt_von, gesetzt_von_name = excluded.gesetzt_von_name, "
                    "gesetzt_am = excluded.gesetzt_am, quelle = 'import'", (tid, vid, uid, name, ts))
                db.execute("INSERT INTO pruef_voraussetzung_verlauf (teilnehmer_id, voraussetzung_id, erfuellt, "
                           "user_id, user_name, zeit, quelle) VALUES (?,?,1,?,?,?,'import')", (tid, vid, uid, name, ts))
    current_app.logger.info("Excel-Import in Lehrgang %s durch %s: %s neu, %s aktualisiert", lid, name, angelegt, aktualisiert)
    return jsonify(lehrgang=_lehrgang_detail(lid), angelegt=angelegt, aktualisiert=aktualisiert,
                   voraussetzungen_neu=voraussetzungen_neu, ausbilder_neu=ausbilder_neu,
                   warnungen=warnungen), 201


# --- 4.9 Prüfungsleistungskataloge --------------------------------------------
# Vorlagen für die Prüfungsleistungen eines Lehrgangs, unabhängig von einer einzelnen
# Durchführung. Jede:r Prüfer:in darf sie lesen und beim Anlegen eines Lehrgangs wählen; ändern
# und löschen darf sie nur die Administration (_katalog_admin) – es gibt anders als beim Lehrgang
# keine Leitung, die dafür geradestünde. Eine Änderung am Katalog wirkt sich nie auf einen schon
# angelegten Lehrgang aus: create_lehrgang() kopiert die Zeilen nur einmal hinein (wie kopieren()).

@bp.get("/kataloge")
@pruefer_required
def list_kataloge():
    rows = db.query(_KATALOG_SQL + "ORDER BY titel COLLATE NOCASE")
    return jsonify(kataloge=[_katalog_kurz(r) for r in rows])


def _katalog_felder(d, neu):
    vals = {}
    if neu or "titel" in d:
        vals["titel"] = sfield(d, "titel").strip()[:200]
        if not vals["titel"]:
            raise Abgelehnt("Bitte einen Titel angeben.")
    if neu or "beschreibung" in d:
        vals["beschreibung"] = sfield(d, "beschreibung").strip()[:20000]
    return vals


@bp.post("/kataloge")
@pruefer_required
def create_katalog():
    _katalog_admin()
    vals = _katalog_felder(json_body(), neu=True)
    uid, name = _ich()
    ts = db.now()
    kid = db.execute(
        "INSERT INTO pruef_kataloge (titel, beschreibung, created_by, created_by_name, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?)", (vals["titel"], vals["beschreibung"], uid, name, ts, ts))
    return jsonify(katalog=_katalog_detail(kid)), 201


@bp.get("/kataloge/<int:kid>")
@pruefer_required
def get_katalog(kid):
    return jsonify(katalog=_katalog_detail(kid))


@bp.put("/kataloge/<int:kid>")
@pruefer_required
def update_katalog(kid):
    _katalog(kid)
    _katalog_admin()
    vals = _katalog_felder(json_body(), neu=False)
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals) + ", updated_at = ?"
        db.execute(f"UPDATE pruef_kataloge SET {sets} WHERE id = ?", (*vals.values(), db.now(), kid))
    return jsonify(katalog=_katalog_detail(kid))


@bp.delete("/kataloge/<int:kid>")
@pruefer_required
def delete_katalog(kid):
    _katalog(kid)
    _katalog_admin()
    db.execute("DELETE FROM pruef_kataloge WHERE id = ?", (kid,))
    return jsonify(ok=True)


def _katalog_naechste_sortierung(kid):
    return db.query("SELECT COALESCE(MAX(sortierung), -1) + 1 AS n FROM pruef_katalog_leistungen "
                    "WHERE katalog_id = ?", (kid,), one=True)["n"]


@bp.post("/kataloge/<int:kid>/leistungen")
@pruefer_required
def create_katalog_leistung(kid):
    _katalog(kid)
    _katalog_admin()
    # Dieselben Felder und Grenzen wie bei einer Prüfungsleistung im Lehrgang – _leistung_felder
    # kennt nur den Body, keine Tabelle.
    vals = _leistung_felder(json_body(), neu=True)
    lid = db.execute(
        "INSERT INTO pruef_katalog_leistungen (katalog_id, bezeichnung, beschreibung_md, zeitansatz_sekunden, "
        "sortierung) VALUES (?,?,?,?,?)", (kid, vals["bezeichnung"], vals["beschreibung_md"],
                                          vals["zeitansatz_sekunden"], _katalog_naechste_sortierung(kid)))
    return jsonify(leistung=_leistung_json(_katalog_leistung(lid))), 201


@bp.put("/katalog-leistungen/<int:lid>")
@pruefer_required
def update_katalog_leistung(lid):
    _katalog_leistung(lid)
    _katalog_admin()
    vals = _leistung_felder(json_body(), neu=False)
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        db.execute(f"UPDATE pruef_katalog_leistungen SET {sets} WHERE id = ?", (*vals.values(), lid))
    return jsonify(leistung=_leistung_json(_katalog_leistung(lid)))


@bp.delete("/katalog-leistungen/<int:lid>")
@pruefer_required
def delete_katalog_leistung(lid):
    _katalog_leistung(lid)
    _katalog_admin()
    db.execute("DELETE FROM pruef_katalog_leistungen WHERE id = ?", (lid,))
    return jsonify(ok=True)


@bp.put("/kataloge/<int:kid>/leistungen/reihenfolge")
@pruefer_required
def reihenfolge_katalog_leistungen(kid):
    _katalog(kid)
    _katalog_admin()
    ids = _id_liste(json_body().get("ids"))
    with db.transaction():
        for i, lid in enumerate(ids):
            db.execute("UPDATE pruef_katalog_leistungen SET sortierung = ? WHERE id = ? AND katalog_id = ?",
                      (i, lid, kid))
    return jsonify(ok=True)
