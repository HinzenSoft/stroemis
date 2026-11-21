"""Läufe über die Claude API – der gemeinsame Baustein aller Module (Entscheidung des Nutzers vom 21.11.2026).

Zuerst nutzt ihn die Recherche an „Produkt melden“ der Materialablage (material/services/recherche.py), später der
Artikelentwurf der Strömipedia. Ein Modul bringt seine Anweisung, seine Werkzeuge und seine Prüfungen selbst mit; hier
steht, was für alle gleich ist:

  - Client-Fabrik CLIENT (Tests setzen eine Attrappe ein) und verfuegbar(): Die Funktion gibt es nur mit
    ANTHROPIC_API_KEY in der Umgebung (.env). Der Schlüssel wird nur aus os.environ gelesen – nie aus Leitstelle →
    Einstellungen, nie in Seiten, Logs oder Fehlertexten; das Protokoll des SDK bleibt stumm (Stufe WARNING).
    `anthropic` wird erst in der Fabrik bzw. in der Fehlerabbildung importiert – ohne Schlüssel braucht es niemand.
  - Modell, Preise und kosten_cent(): eine Schätzung aus dem gemeldeten Verbrauch (usage) aller Aufrufe eines Laufs.
  - Ein Lauf im Hintergrund (Tabelle ki_laeufe, app/db.py): starten() legt die Zeile unter BEGIN IMMEDIATE an – mit
    Prüfung von Schlüssel, Kontingent je Kalendermonat (deutsche Zeit) und „höchstens einer je Art“ (dazu ein
    eindeutiger Index) – und startet einen Daemon-Thread im selben Arbeitsprozess mit App- und Anfragekontext (das
    Journal der Module schreibt mit dem Konto, das gestartet hat). Ein zweiter Thread, der Puls, schreibt alle
    PULS_SEK ein Lebenszeichen und liest das Abbruch-Kennzeichen; ist es gesetzt oder die Zeitgrenze der Art
    überschritten, schließt er den offenen Stream und einen offenen Download (download_merken) – mit shutdown() auf dem
    Socket, denn close() allein weckt ein blockiertes recv nicht –, der Lauf endet dann „abgebrochen“, auch mitten in
    einer langen Antwort. Ohne Lebenszeichen seit TOT_NACH Sekunden gilt ein Lauf als tot (Neustart, Deploy):
    tote_aufraeumen() bei jeder Statusabfrage, jedem Start und im Tageslauf; das Modul erfährt es über bei_tod().
  - Die Gesprächsschleife Lauf.gespraech(): streamt jede Antwort (Ereignis-Schleife, dann get_final_message()), hängt
    sie unverändert an (nach einem Ausweichen mitten in der Ausgabe ohne das, was das ablehnende Modell vor dem
    fallback-Block schrieb), setzt nach pause_turn fort (höchstens PAUSEN_MAX), führt eigene Werkzeuge aus (alle Ergebnisse
    in EINER Nutzernachricht, Fehler als is_error; scheitert dasselbe Werkzeug zweimal, endet der Lauf), beendet
    max_tokens und refusal sauber und hält Grenzen für Runden und Gesamtzeit ein. Verbrauch und Kosten stehen nach jeder
    Antwort in der Zeile; bricht eine Antwort mitten im Stream ab, zählt ihr Zwischenstand als Zeile „unvollstaendig“ –
    die Kosten sind dann „mindestens“. Je Lauf steht der größte Abstand zwischen zwei Ereignissen des Streams (rohe
    Ereignisse samt ping) im Protokoll des Servers – Grundlage, um die Lese-Zeitgrenze später zu senken.
  - Ein Ordner je Lauf für Downloads (DATA_DIR/ki/<Kennung>/, 0700): weg mit dem Lauf, wenn er nicht fertig wird.

Was hinausging, hält eingabe_json fest (Nachweis); das Ergebnis steht in ergebnis_json. Das Modul entscheidet, was davon
wer sieht – hier gibt es keine Routen."""
import json
import logging
import os
import shutil
import socket
import threading
import time
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app, g

from . import db

log = logging.getLogger(__name__)

MODELL = "claude-opus-5-5"
# Preise von Claude Opus 5.5 in US-Cent je Million Token (Stand 21.11.2026): Eingabe 4 $, Ausgabe 20 $, Lesen aus dem
# Zwischenspeicher 0,20 $, Schreiben in ihn (5 Minuten) 1,25 × Eingabe; die Websuche kostet 10 $ je 1 000 Suchen.
# Antwortet nach einer Ablehnung ein Ausweichmodell, bleibt es bei diesen Preisen – die Anzeige sagt dann „Schätzung“.
PREIS_EINGABE = 400
PREIS_AUSGABE = 2000
PREIS_CACHE_LESEN = 20
PREIS_CACHE_SCHREIBEN = 500
PREIS_WEBSUCHE = 1                     # Cent je Suche
# Die Arten von Läufen – die Tabelle prüft nur „nicht leer“. Je Art: Name im Text, Monatskontingent (Umgebungsvariable,
# sonst Vorgabe) und die Zeitgrenze eines Laufs.
ARTEN = {
    "mat_recherche": {"name": "Recherche", "umgebung": "MATERIAL_RECHERCHE_JE_MONAT", "vorgabe": 20,
                      "gesamt_sek": 20 * 60},
}
LAUFEND = ("wartet", "laeuft")
PULS_SEK = 10
TOT_NACH = 120
PAUSEN_MAX = 5
ORDNER = "ki"
ZONE = ZoneInfo("Europe/Berlin")
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
          "Dezember")
GELOESCHT = "(gelöschtes Konto)"
TOT_TEXT = "Unterbrochen – der Server wurde neu gestartet."
ZEIT_TEXT = "Abgebrochen nach {} Minuten (Zeitgrenze)."
UNERWARTET = "Unerwarteter Fehler – Einzelheiten stehen im Protokoll des Servers."
WERKZEUG_FEHLER_MAX = 2                # so oft darf dasselbe eigene Werkzeug in einem Gespräch scheitern

# Was ein eigenes Werkzeug zurückgibt: der Inhalt für das tool_result, ob es ein Fehler ist (is_error) und ob das
# Gespräch damit endet (das Ergebnis ist abgegeben).
Antwort = namedtuple("Antwort", "inhalt fehler ende", defaults=(False, False))

_LAEUFER = {}                          # Kennung → Lauf dieses Arbeitsprozesses, solange sein Thread lebt
_LAEUFER_SPERRE = threading.Lock()
_NACH_TOD = {}                         # Art → f(zeile): was das Modul nachträgt, wenn tote_aufraeumen einen Lauf beendet


class KiFehler(Exception):
    """Eine Antwort mit Klartext und Statuscode (Start, Abbruch) – die Module machen daraus ihre JSON-Antwort."""

    def __init__(self, meldung, code=400, lauf=None):
        super().__init__(meldung)
        self.code = code
        self.lauf = lauf


class Abgebrochen(Exception):
    """Der Lauf endet „abgebrochen“ – auf Wunsch, nach der Zeitgrenze oder weil sein Bezug erledigt ist."""


class LaufFehler(Exception):
    """Der Lauf endet „fehlgeschlagen“ mit diesem Text (ohne Schlüssel, ohne Rohantwort)."""


# --- Schlüssel und Client -----------------------------------------------------------------------------------------

def verfuegbar():
    """Gibt es die Funktion? Nur mit ANTHROPIC_API_KEY in der Umgebung – nicht über Leitstelle → Einstellungen."""
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())


def _client():
    """Der API-Client: Schlüssel ausdrücklich aus der Umgebung (so sucht das SDK keine anderen Zugangsdaten auf der
    Platte), zwei Wiederholungen des SDK bei 429/5xx (H2 A), Verbindungsaufbau höchstens 10 s. Das Protokoll des SDK
    und seines HTTP-Clients bleibt auf WARNING, auch wenn jemand ANTHROPIC_LOG setzt."""
    import anthropic
    for name in ("anthropic", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"].strip(), max_retries=2,
                               timeout=anthropic.Timeout(600.0, connect=10.0))


CLIENT = _client


def _schluessel_weg(text):
    """Falls je ein Text den Schlüssel enthielte (Fehlermeldung eines Proxys): unkenntlich machen."""
    k = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    text = str(text or "")
    return text.replace(k, "***") if k else text


def fehlertext(exc, lauf_id=None):
    """Eine Ausnahme des SDK als Satz für die Anzeige – ohne Schlüssel, ohne Rohantwort. Ins Protokoll kommen Klasse,
    Status und Anfragekennung (request-id), bei 400 dazu der Anfang der Meldung (Parameterfehler lassen sich sonst
    nicht finden). Spezifische Klassen zuerst (die Kette der SDK-Doku)."""
    try:
        import anthropic
    except ImportError:                       # ohne Paket kommt keine Ausnahme des SDK zustande
        log.exception("KI-Lauf %s: unerwarteter Fehler", lauf_id)
        return UNERWARTET
    status = getattr(exc, "status_code", None)
    anfrage = getattr(exc, "request_id", None)
    if isinstance(exc, anthropic.APIStatusError):
        if isinstance(exc, anthropic.BadRequestError):
            log.warning("KI-Lauf %s: %s (Status %s, Anfrage %s): %s", lauf_id, type(exc).__name__, status, anfrage,
                        _schluessel_weg(getattr(exc, "message", ""))[:300])
        else:
            log.warning("KI-Lauf %s: %s (Status %s, Anfrage %s)", lauf_id, type(exc).__name__, status, anfrage)
        if isinstance(exc, anthropic.AuthenticationError):
            return "Der API-Schlüssel wurde abgelehnt (ungültig oder gesperrt)."
        if isinstance(exc, anthropic.PermissionDeniedError):
            return "Der API-Schlüssel darf das nicht (Arbeitsbereich, Modell oder Region gesperrt)."
        if isinstance(exc, anthropic.NotFoundError):
            return "Modell oder Schnittstelle nicht gefunden."
        if isinstance(exc, anthropic.BadRequestError):
            return "Die Schnittstelle hat die Anfrage abgelehnt – Einzelheiten stehen im Protokoll des Servers."
        if isinstance(exc, anthropic.RateLimitError):
            return "Ratenlimit oder Monatslimit der Schnittstelle erreicht – bitte später erneut versuchen."
        if status == 402:
            return "Die Schnittstelle meldet ein Problem mit der Abrechnung des Kontos."
        if status is not None and status >= 500:
            return "Der Dienst ist überlastet oder gestört – bitte später erneut versuchen."
        return f"Die Schnittstelle meldet einen Fehler ({status})."
    if isinstance(exc, anthropic.APITimeoutError):
        log.warning("KI-Lauf %s: Zeitüberschreitung", lauf_id)
        return "Zeitüberschreitung bei der Verbindung zur Schnittstelle."
    if isinstance(exc, anthropic.APIConnectionError):
        log.warning("KI-Lauf %s: keine Verbindung", lauf_id)
        return "Keine Verbindung zur Schnittstelle."
    log.exception("KI-Lauf %s: unerwarteter Fehler", lauf_id)
    return UNERWARTET


# --- Verbrauch und Kosten -----------------------------------------------------------------------------------------

def _zahl(obj, feld):
    v = getattr(obj, feld, None) if not isinstance(obj, dict) else obj.get(feld)
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def verbrauch(msg):
    """Der Verbrauch einer Antwort als einfache Zeile für usage_json. Mit usage.iterations (Schleife der Server-Werkzeuge,
    Ausweichmodell nach einer Ablehnung) zählen die Einträge je Durchgang – oben steht nach einem Ausweichen nur der
    Durchgang, der geantwortet hat; ohne sie die Summen oben. Suchen und Abrufe stehen nur oben."""
    u = getattr(msg, "usage", None)
    iterationen = [i for i in (getattr(u, "iterations", None) or [])
                   if getattr(i, "type", None) in ("message", "fallback_message")]
    quellen = iterationen or ([u] if u is not None else [])
    werkzeuge = getattr(u, "server_tool_use", None)
    return {
        "modell": str(getattr(msg, "model", "") or ""),
        "eingabe": sum(_zahl(q, "input_tokens") for q in quellen),
        "ausgabe": sum(_zahl(q, "output_tokens") for q in quellen),
        "cache_lesen": sum(_zahl(q, "cache_read_input_tokens") for q in quellen),
        "cache_schreiben": sum(_zahl(q, "cache_creation_input_tokens") for q in quellen),
        "websuche": _zahl(werkzeuge, "web_search_requests"),
        "abrufe": _zahl(werkzeuge, "web_fetch_requests"),
        "ausweichen": any(getattr(i, "type", None) == "fallback_message" for i in iterationen),
    }


def kosten_cent(usage_liste):
    """Geschätzte Kosten in US-Cent (gerundet) aus Zeilen wie verbrauch() sie liefert."""
    summe = 0.0
    for z in usage_liste or ():
        summe += (_zahl(z, "eingabe") * PREIS_EINGABE + _zahl(z, "ausgabe") * PREIS_AUSGABE
                  + _zahl(z, "cache_lesen") * PREIS_CACHE_LESEN
                  + _zahl(z, "cache_schreiben") * PREIS_CACHE_SCHREIBEN) / 1_000_000
        summe += _zahl(z, "websuche") * PREIS_WEBSUCHE
    return int(round(summe))


def kosten_text(cent, mindestens=False):
    """„ca. 1,80 $“ – leer ohne Angabe; mindestens: „mindestens ca. 1,80 $“ (eine Antwort brach mitten im Stream ab)."""
    if cent is None:
        return ""
    return f"{'mindestens ' if mindestens else ''}ca. {cent // 100},{cent % 100:02d} $"


def unvollstaendig(usage_liste):
    """Fehlt in den Kosten etwas? Ja, wenn eine Antwort mitten im Stream abbrach (ihr Zwischenstand ist nur ein Teil)."""
    return any(isinstance(z, dict) and z.get("unvollstaendig") for z in usage_liste or ())


def ausweichmodell(usage_liste):
    """Das Modell, das nach einer Ablehnung geantwortet hat (sonst None) – dann sind die Kosten nur eine Schätzung."""
    for z in usage_liste or ():
        if z.get("ausweichen") or (z.get("modell") and z["modell"] != MODELL):
            return z.get("modell") or "unbekannt"
    return None


# --- Kontingent ---------------------------------------------------------------------------------------------------

def grenze(art):
    """Läufe je Kalendermonat: aus der Umgebungsvariablen der Art (ganze Zahl ≥ 0), sonst die Vorgabe."""
    a = ARTEN[art]
    roh = (os.environ.get(a["umgebung"]) or "").strip()
    return int(roh) if roh.isdigit() else a["vorgabe"]


def _monat(jetzt=None):
    """(Beginn, Beginn des nächsten) des laufenden Kalendermonats in deutscher Zeit, als UTC-Zeitstempel wie db.now()."""
    jetzt = (jetzt or datetime.now(timezone.utc)).astimezone(ZONE)
    anfang = jetzt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    naechster = (anfang + timedelta(days=32)).replace(day=1)
    utc = [datetime(t.year, t.month, 1, tzinfo=ZONE).astimezone(timezone.utc).isoformat() for t in (anfang, naechster)]
    return utc[0], utc[1], jetzt.month


def kontingent(art, jetzt=None):
    """{grenze, verbraucht, rest, monat}: Jeder Start im laufenden Kalendermonat zählt (C4 A) – auch gescheiterte und
    abgebrochene, und auch, wenn sein Bezug inzwischen gelöscht ist (die Zeile bleibt)."""
    von, bis, monat = _monat(jetzt)
    n = db.query("SELECT COUNT(*) AS n FROM ki_laeufe WHERE art = ? AND gestartet_am >= ? AND gestartet_am < ?",
                 (art, von, bis), one=True)["n"]
    gr = grenze(art)
    return {"grenze": gr, "verbraucht": n, "rest": max(0, gr - n), "monat": MONATE[monat - 1]}


# --- Zeilen ---------------------------------------------------------------------------------------------------------

def zeile(lauf_id):
    return db.query("SELECT * FROM ki_laeufe WHERE id = ?", (lauf_id,), one=True)


def letzter(art, bezug):
    """Der jüngste Lauf einer Art zu einem Bezug (oder None)."""
    return db.query("SELECT * FROM ki_laeufe WHERE art = ? AND bezug = ? ORDER BY id DESC LIMIT 1", (art, bezug),
                    one=True)


def laufend(art):
    """Der Lauf dieser Art, der gerade läuft oder wartet (höchstens einer), oder None."""
    return db.query(f"SELECT * FROM ki_laeufe WHERE art = ? AND status IN ({_in(LAUFEND)}) LIMIT 1", (art,), one=True)


def _in(werte):
    return ", ".join(f"'{w}'" for w in werte)


def json_lesen(text, sonst=None):
    try:
        return json.loads(text) if text else sonst
    except ValueError:
        return sonst


# --- Ordner je Lauf -----------------------------------------------------------------------------------------------

def ordner(lauf_id, anlegen=False):
    """DATA_DIR/ki/<Kennung> – mit anlegen samt übergeordnetem Ordner (beide 0700)."""
    basis = os.path.join(current_app.config["DATA_DIR"], ORDNER)
    pfad = os.path.join(basis, str(int(lauf_id)))
    if anlegen:
        os.makedirs(basis, mode=0o700, exist_ok=True)
        os.makedirs(pfad, mode=0o700, exist_ok=True)
    return pfad


def ordner_entfernen(lauf_id):
    shutil.rmtree(ordner(lauf_id), ignore_errors=True)


# --- Start, Abbruch, Ende -------------------------------------------------------------------------------------------

def starten(art, bezug, eingabe, arbeit, effort="", beendet=None, mit_ordner=False, vor_start=None):
    """Einen Lauf anlegen und im Hintergrund starten; liefert die Zeile. arbeit(lauf) läuft im Thread und liefert das
    Ergebnis (ein JSON-fähiges dict) – oder wirft Abgebrochen bzw. LaufFehler. vor_start(zeile) läuft nach dem Anlegen
    und vor dem Thread in der Anfrage (Journal „gestartet“ des Moduls – so steht es vor allem, was der Lauf schreibt);
    beendet(lauf, status) läuft am Ende im Thread. Wirft KiFehler: 503 ohne Schlüssel, 409 wenn schon einer dieser Art läuft
    (lauf = dessen Zeile), 429 bei erschöpftem Kontingent."""
    if art not in ARTEN:
        raise KiFehler("Unbekannte Art eines KI-Laufs.", 500)
    if not verfuegbar():
        raise KiFehler("Die Recherche per Claude API ist nicht eingerichtet (kein API-Schlüssel).", 503)
    from .auth import current_user
    tote_aufraeumen()
    u = current_user()
    uid = u["id"] if u else None
    name = ((u["name"] or "").strip() if u else "") or ("(Konto ohne Namen)" if u else "System")
    import sqlite3
    try:
        with db.transaction(sofort=True):
            da = laufend(art)
            if da:
                raise KiFehler(f"Es läuft schon eine {ARTEN[art]['name']}.", 409, lauf=da)
            k = kontingent(art)
            if not k["rest"]:
                raise KiFehler(f"Das Kontingent für {k['monat']} ist aufgebraucht ({k['verbraucht']} von "
                               f"{k['grenze']}).", 429)
            jetzt = db.now()
            lid = db.execute(
                "INSERT INTO ki_laeufe (art, bezug, status, eingabe_json, modell, effort, gestartet_von, "
                "gestartet_von_name, gestartet_am, lebenszeichen_am) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (art, bezug, "wartet", json.dumps(eingabe, ensure_ascii=False, sort_keys=True), MODELL, effort, uid,
                 name, jetzt, jetzt))
    except sqlite3.IntegrityError:                 # ein anderer Arbeitsprozess war schneller (ux_ki_laeufe_einer)
        raise KiFehler(f"Es läuft schon eine {ARTEN[art]['name']}.", 409, lauf=laufend(art))
    if mit_ordner:
        try:
            ordner(lid, anlegen=True)
        except OSError as exc:
            log.warning("KI-Lauf %s: Ordner ließ sich nicht anlegen: %s", lid, exc)
            _beenden_zeile(lid, "fehlgeschlagen", None, "Der Ablageordner ließ sich nicht anlegen.", [])
            raise KiFehler("Der Ablageordner für die Recherche ließ sich nicht anlegen.", 500)
    if vor_start:
        try:
            vor_start(zeile(lid))
        except Exception:                          # noqa: BLE001 – der Lauf soll daran nicht scheitern
            log.exception("KI-Lauf %s: Vorarbeit gescheitert", lid)
    app = current_app._get_current_object()
    t = threading.Thread(target=_ausfuehren, args=(app, lid, arbeit, beendet), name=f"ki-{art}-{lid}", daemon=True)
    with _LAEUFER_SPERRE:
        _LAEUFER[lid] = None
    try:
        t.start()
    except RuntimeError as exc:                   # „can't start new thread“
        with _LAEUFER_SPERRE:
            _LAEUFER.pop(lid, None)
        log.error("KI-Lauf %s: Thread nicht gestartet: %s", lid, exc)
        _beenden_zeile(lid, "fehlgeschlagen", None, "Der Lauf ließ sich nicht starten.", [])
        ordner_entfernen(lid)
        raise KiFehler("Der Lauf ließ sich nicht starten – bitte später erneut versuchen.", 503)
    return zeile(lid)


def abbrechen(lauf_id):
    """Das Abbruch-Kennzeichen setzen (nur an einem laufenden Lauf). Läuft er in diesem Arbeitsprozess, erfährt er es
    sofort, sonst mit dem nächsten Lebenszeichen. Liefert, ob etwas zu tun war."""
    n = db.execute_zeilen(f"UPDATE ki_laeufe SET abbrechen = 1 WHERE id = ? AND status IN ({_in(LAUFEND)})",
                          (lauf_id,))
    with _LAEUFER_SPERRE:
        lauf = _LAEUFER.get(lauf_id)
    if n and lauf is not None:
        lauf.abbrechen_intern("Abgebrochen.")
    return bool(n)


def leeren(lauf_id):
    """Inhalt eines Laufs entfernen, die Zeile bleibt (Kontingent) – etwa wenn sein Bezug gelöscht wird. Ein laufender
    Lauf wird zugleich abgebrochen. Der Ordner geht sofort."""
    db.execute("UPDATE ki_laeufe SET eingabe_json = '{}', ergebnis_json = NULL WHERE id = ?", (lauf_id,))
    abbrechen(lauf_id)
    ordner_entfernen(lauf_id)


def _beenden_zeile(lauf_id, status, ergebnis, fehler, usage):
    """Den Endstand schreiben – nur an einem noch laufenden Lauf; „fertig“ nur ohne Abbruch-Kennzeichen (sonst
    „abgebrochen“). Verbrauch und Kosten in jedem Fall. Liefert den Status, der gilt."""
    kosten = kosten_cent(usage)
    u_json = json.dumps(usage, ensure_ascii=False)
    jetzt = db.now()
    with db.transaction(sofort=True):
        if status == "fertig":
            if db.execute_zeilen(
                    f"UPDATE ki_laeufe SET status = 'fertig', ergebnis_json = ?, fehler = '', phase = '', fortschritt = "
                    f"'', usage_json = ?, kosten_cent = ?, beendet_am = ? WHERE id = ? AND status IN ({_in(LAUFEND)}) "
                    f"AND abbrechen = 0",
                    (json.dumps(ergebnis, ensure_ascii=False), u_json, kosten, jetzt, lauf_id)):
                return "fertig"
            status, fehler = "abgebrochen", fehler or "Abgebrochen."
        if not db.execute_zeilen(
                f"UPDATE ki_laeufe SET status = ?, fehler = ?, usage_json = ?, kosten_cent = ?, beendet_am = ? "
                f"WHERE id = ? AND status IN ({_in(LAUFEND)})", (status, fehler, u_json, kosten, jetzt, lauf_id)):
            # schon beendet (für tot erklärt) oder gelöscht: nur noch den Verbrauch nachtragen
            db.execute("UPDATE ki_laeufe SET usage_json = ?, kosten_cent = ? WHERE id = ?", (u_json, kosten, lauf_id))
            r = zeile(lauf_id)
            return r["status"] if r else status
    return status


def tote_aufraeumen():
    """Läufe ohne Lebenszeichen seit TOT_NACH Sekunden (ihr Prozess endete) als „abgebrochen“ beenden und ihren Ordner
    entfernen. Läufe, deren Thread in diesem Prozess noch lebt, nie. Liefert die Kennungen."""
    grenze_zeit = (datetime.now(timezone.utc) - timedelta(seconds=TOT_NACH)).replace(microsecond=0).isoformat()
    tot = []
    for r in db.query(f"SELECT id, art FROM ki_laeufe WHERE status IN ({_in(LAUFEND)}) "
                      "AND COALESCE(lebenszeichen_am, gestartet_am) < ?", (grenze_zeit,)):
        with _LAEUFER_SPERRE:
            if r["id"] in _LAEUFER:
                continue
        if db.execute_zeilen(f"UPDATE ki_laeufe SET status = 'abgebrochen', fehler = ?, beendet_am = ? WHERE id = ? "
                             f"AND status IN ({_in(LAUFEND)}) AND COALESCE(lebenszeichen_am, gestartet_am) < ?",
                             (TOT_TEXT, db.now(), r["id"], grenze_zeit)):
            ordner_entfernen(r["id"])
            tot.append(r["id"])
            nach = _NACH_TOD.get(r["art"])
            if nach:
                try:
                    nach(zeile(r["id"]))
                except Exception:                  # noqa: BLE001 – das Aufräumen soll daran nicht scheitern
                    log.exception("KI-Lauf %s: Nacharbeit nach dem Tod gescheitert", r["id"])
    return tot


def bei_tod(art, f):
    """Ein Modul meldet an, was es nachträgt, wenn tote_aufraeumen einen seiner Läufe beendet (etwa „Recherche beendet“
    im Journal) – f(zeile) läuft im Kontext dessen, der aufräumt (Anfrage, Start, Tageslauf), nicht im Lauf."""
    _NACH_TOD[art] = f


def aufraeumen():
    """Für den Tageslauf: tote Läufe beenden und Ordner ohne Zeile oder mit gescheitertem Lauf entfernen. Ordner
    fertiger Läufe räumt das Modul (es weiß, wann sein Bezug erledigt ist). Wirft nie."""
    try:
        tote_aufraeumen()
        basis = os.path.join(current_app.config["DATA_DIR"], ORDNER)
        for name in (os.listdir(basis) if os.path.isdir(basis) else ()):
            if not name.isdigit():
                continue
            r = zeile(int(name))
            if not r or r["status"] in ("fehlgeschlagen", "abgebrochen"):
                ordner_entfernen(int(name))
    except Exception as exc:                    # noqa: BLE001 – der Tageslauf soll daran nicht scheitern
        log.warning("KI-Läufe: Aufräumen gescheitert: %s", exc)


def konto_loeschen(uid):
    """Vor DELETE FROM users (api_admin.delete_user): der Name des Startenden wird „(gelöschtes Konto)“; die Kennung
    setzt die Datenbank selbst auf NULL."""
    db.execute("UPDATE ki_laeufe SET gestartet_von_name = ? WHERE gestartet_von = ?", (GELOESCHT, uid))


def warten(lauf_id, sekunden=60):
    """Bis der Thread dieses Laufs (in diesem Prozess) zu Ende ist – für Tests. Liefert, ob er zu Ende ist."""
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        with _LAEUFER_SPERRE:
            if lauf_id not in _LAEUFER:
                return True
        time.sleep(0.02)
    return False


# --- Der Lauf im Thread ------------------------------------------------------------------------------------------

class Lauf:
    """Ein laufender Lauf im Thread: Kennung, Eingabe, Ordner, Verbrauch – und die Gesprächsschleife."""

    def __init__(self, z):
        self.id = z["id"]
        self.art = z["art"]
        self.bezug = z["bezug"]
        self.eingabe = json_lesen(z["eingabe_json"], {})
        self.effort = z["effort"]
        self.usage = []
        self.grenze_sek = ARTEN[self.art]["gesamt_sek"]
        self._start = time.monotonic()
        # Gelesen mit wait(0): „is_set“ meint seit dem Rückbau der Sets im Code der Anwendung den
        # früheren Set-Schlüssel und ist dort gesperrt (tests/test_material_set_rueckbau.py).
        self._abbruch = threading.Event()
        self._grund = ""
        self._stream = None
        self._download = None              # Socket eines laufenden Downloads (download_merken)
        self._client = None
        self._sperre = threading.Lock()
        self.abstand_max = 0.0             # größter Abstand zwischen zwei Ereignissen eines Streams (Sekunden)
        self.ereignisse = 0
        self._zuletzt = None

    @property
    def ordner(self):
        return ordner(self.id)

    def client(self):
        if self._client is None:
            self._client = CLIENT()
        return self._client

    # Abbruch ------------------------------------------------------------------------------------------------

    def abbrechen_intern(self, grund):
        """Von außen (Puls, Abbrechen im selben Prozess): Kennzeichen setzen, einen offenen Stream und einen offenen
        Download beenden – das Lesen im Lauf endet dann mit einer Ausnahme, die gespraech() bzw. der Download als Abbruch
        erkennt. Vor close() kommt shutdown() auf den Socket: close() aus einem anderen Thread weckt ein blockiertes recv
        nicht (Prüfung Sicherheit vom 21.11.2026, Befunde 1 und 2)."""
        with self._sperre:
            if not self._abbruch.wait(0):
                self._grund = grund
                self._abbruch.set()
            stream, download = self._stream, self._download
        _socket_beenden(download)
        if stream is not None:
            _socket_beenden(_stream_socket(stream))
            try:
                stream.close()
            except Exception:                    # noqa: BLE001 – schließen darf nicht scheitern
                pass

    def download_merken(self, sock):
        """Der Socket des Downloads, der gerade läuft (None: keiner) – damit der Puls ihn beenden kann. Kam der Abbruch
        schon vorher, endet er sofort."""
        with self._sperre:
            self._download = sock
        if sock is not None and self._abbruch.wait(0):
            _socket_beenden(sock)

    def zeit_um(self):
        return time.monotonic() - self._start > self.grenze_sek

    def pruefen(self):
        """Zwischen den Schritten und bei jedem Ereignis des Streams: abgebrochen oder Zeit um → Abgebrochen."""
        if not self._abbruch.wait(0) and self.zeit_um():
            self.abbrechen_intern(ZEIT_TEXT.format(self.grenze_sek // 60))
        if self._abbruch.wait(0):
            raise Abgebrochen(self._grund or "Abgebrochen.")

    def schritt(self, phase, fortschritt=""):
        """Phase und Fortschritt für die Anzeige (mit Lebenszeichen); prüft vorher auf Abbruch."""
        self.pruefen()
        db.execute(f"UPDATE ki_laeufe SET status = 'laeuft', phase = ?, fortschritt = ?, lebenszeichen_am = ? "
                   f"WHERE id = ? AND status IN ({_in(LAUFEND)})", (phase, fortschritt, db.now(), self.id))

    def _verbrauch_merken(self, msg, unvollstaendig=False):
        z = verbrauch(msg)
        if unvollstaendig:
            z["unvollstaendig"] = True
        self.usage.append(z)
        db.execute("UPDATE ki_laeufe SET usage_json = ?, kosten_cent = ? WHERE id = ?",
                   (json.dumps(self.usage, ensure_ascii=False), kosten_cent(self.usage), self.id))

    def _teilverbrauch(self, stream):
        """Eine Antwort brach mitten im Stream ab (Abbruch, Zeitgrenze, unlesbares Werkzeug-JSON, Fehler): Der
        Zwischenstand des SDK (message_start trägt die Eingabe, message_delta die bisherige Ausgabe) zählt als Zeile
        „unvollstaendig“ – ohne ihn fehlte gerade die teuerste Runde. Wirft nie."""
        try:
            schnappschuss = stream.current_message_snapshot
        except Exception:                        # noqa: BLE001 – vor message_start gibt es keinen (AssertionError)
            return
        if getattr(schnappschuss, "usage", None) is None:
            return
        try:
            self._verbrauch_merken(schnappschuss, unvollstaendig=True)
        except Exception:                        # noqa: BLE001
            log.exception("KI-Lauf %s: Zwischenstand des Verbrauchs nicht gespeichert", self.id)

    def _ereignis(self):
        """Ein Ereignis des Streams ist da: Abstand zum vorigen (bzw. zum Senden der Anfrage) messen."""
        jetzt = time.monotonic()
        if self._zuletzt is not None:
            self.abstand_max = max(self.abstand_max, jetzt - self._zuletzt)
        self._zuletzt = jetzt
        self.ereignisse += 1

    def _rohe_ereignisse_messen(self, stream):
        """Das SDK reicht ping nicht durch (anthropic 1.17.0: _streaming.Stream überspringt sie) – gemessen wird deshalb
        an den rohen SSE-Ereignissen. Fehlt der Weg (andere Fassung, Attrappe), misst die Ereignis-Schleife. Liefert, ob
        roh gemessen wird."""
        roh = getattr(stream, "_raw_stream", None)
        lesen = getattr(roh, "_iter_events", None)
        if not callable(lesen):
            return False

        def gemessen():
            for sse in lesen():
                self._ereignis()
                yield sse
        try:
            roh._iter_events = gemessen
        except Exception:                        # noqa: BLE001 – nur eine Messung
            return False
        return True

    # Gespräch ------------------------------------------------------------------------------------------------

    def _streamen(self, anfrage):
        """Eine Antwort streamen. Die Ereignis-Schleife prüft bei jedem Ereignis auf Abbruch; das Ergebnis ist
        get_final_message(). JSON eines Werkzeugs, das das SDK gar nicht lesen kann (eager_input_streaming), wirft es
        als ValueError aus dem Stream – dann gibt es keinen tool_use-Block zu beantworten, die Runde wird höchstens
        zweimal neu gestellt."""
        versuche = 0
        while True:
            self.pruefen()
            stream, fertig = None, False
            self._zuletzt = time.monotonic()
            try:
                with self.client().beta.messages.stream(**anfrage) as stream:
                    with self._sperre:
                        self._stream = stream
                    roh = self._rohe_ereignisse_messen(stream)
                    try:
                        for _ereignis in stream:
                            if not roh:
                                self._ereignis()
                            self.pruefen()
                    except ValueError:
                        # Nur der Iterator wirft so bei unlesbarem Werkzeug-JSON – nicht get_final_message.
                        if self._abbruch.wait(0):
                            raise Abgebrochen(self._grund or "Abgebrochen.")
                        versuche += 1
                        if versuche > 2:
                            raise LaufFehler("Die Antwort ließ sich nicht lesen (ungültiges JSON eines Werkzeugs).")
                        continue
                    msg = stream.get_final_message()
                    fertig = True
                    return msg
            except (Abgebrochen, LaufFehler):
                raise
            except Exception:
                # Ein Stream, den der Puls geschlossen hat, endet mit irgendeiner Ausnahme des HTTP-Clients.
                if self._abbruch.wait(0):
                    raise Abgebrochen(self._grund or "Abgebrochen.")
                raise
            finally:
                with self._sperre:
                    self._stream = None
                if self._zuletzt is not None:               # auch das Schweigen bis zum Abbruch zählt
                    self.abstand_max = max(self.abstand_max, time.monotonic() - self._zuletzt)
                    self._zuletzt = None
                if stream is not None and not fertig:
                    self._teilverbrauch(stream)

    def gespraech(self, anfrage, werkzeuge=None, runden=20, nachfrage=None):
        """Die Gesprächsschleife. anfrage: Parameter für client.beta.messages.stream; anfrage["messages"] wächst mit
        (jede Antwort unverändert angehängt – Denkblöcke bleiben, wie sie kamen; nur nach einem Ausweichen mitten in der
        Ausgabe ohne die Denk- und Werkzeugblöcke des ablehnenden Modells, _nach_ausweichen). werkzeuge: {Name: f(input) ->
        Antwort} für eigene Werkzeuge; endet eines mit ende=True, ist das Gespräch fertig. nachfrage: Text, der einmal
        nachgeschickt wird, wenn Claude ohne Ergebnis aufhört. Liefert die letzte Antwort.

        pause_turn → erneut senden (höchstens PAUSEN_MAX), max_tokens → LaufFehler, refusal → LaufFehler mit Kategorie
        (nach dem Ausweichmodell, wenn eingeschaltet)."""
        werkzeuge = werkzeuge or {}
        pausen = 0
        nachgefragt = False
        gescheitert = {}
        for _ in range(runden):
            msg = self._streamen(anfrage)
            self._verbrauch_merken(msg)
            grund = msg.stop_reason
            if grund == "refusal":
                details = getattr(msg, "stop_details", None)
                kat = getattr(details, "category", None)
                raise LaufFehler(f"Claude hat die Anfrage abgelehnt (Kategorie: {kat or 'ohne Angabe'}).")
            if grund == "max_tokens":
                log.warning("KI-Lauf %s: Antwort abgeschnitten (max_tokens)", self.id)
                raise LaufFehler("Die Antwort wurde zu lang und ist abgeschnitten – bitte erneut versuchen.")
            zurueck, gueltig = _nach_ausweichen(msg.content)
            anfrage["messages"].append({"role": "assistant", "content": zurueck})
            if grund == "pause_turn":
                pausen += 1
                if pausen > PAUSEN_MAX:
                    raise LaufFehler(f"Mehr als {PAUSEN_MAX} Fortsetzungen (pause_turn) – abgebrochen.")
                continue
            aufrufe = [b for b in gueltig if getattr(b, "type", None) == "tool_use"]
            if grund == "tool_use" and aufrufe:
                ergebnisse, fertig = [], False
                for b in aufrufe:
                    a = self._werkzeug(werkzeuge, b, gescheitert)
                    ergebnis = {"type": "tool_result", "tool_use_id": b.id, "content": a.inhalt}
                    if a.fehler:
                        ergebnis["is_error"] = True
                    ergebnisse.append(ergebnis)
                    fertig = fertig or a.ende
                if fertig:
                    return msg
                anfrage["messages"].append({"role": "user", "content": ergebnisse})
                continue
            if nachfrage and not nachgefragt:
                nachgefragt = True
                anfrage["messages"].append({"role": "user", "content": nachfrage})
                continue
            return msg
        raise LaufFehler(f"Mehr als {runden} Runden – abgebrochen.")

    def _werkzeug(self, werkzeuge, block, gescheitert):
        """Ein eigenes Werkzeug ausführen. Scheitert dasselbe (oder ruft Claude dasselbe unbekannte) zum
        WERKZEUG_FEHLER_MAX-ten Mal, endet das Gespräch – sonst wiederholte sich Claude bis zur Rundengrenze, und jede
        Runde schickt den ganzen Verlauf erneut (Prüfung Sicherheit vom 21.11.2026, Befund 3)."""
        f = werkzeuge.get(block.name)
        try:
            if f is not None:
                return f(block.input)
        except (Abgebrochen, LaufFehler):
            raise
        except Exception:                        # noqa: BLE001 – ein Fehler im Werkzeug geht als is_error zurück
            log.exception("KI-Lauf %s: Werkzeug %s gescheitert", self.id, block.name)
        gescheitert[block.name] = gescheitert.get(block.name, 0) + 1
        if gescheitert[block.name] >= WERKZEUG_FEHLER_MAX:
            raise LaufFehler(f"Das Werkzeug „{str(block.name)[:60]}“ ist {gescheitert[block.name]}-mal gescheitert – "
                             "abgebrochen.")
        if f is None:
            return Antwort(f"Unbekanntes Werkzeug „{block.name}“.", fehler=True)
        return Antwort("Das Werkzeug ist gescheitert.", fehler=True)


def gueltig(msg):
    """Die Blöcke einer Antwort, die gelten: nach einem Ausweichen mitten in der Ausgabe nur die nach dem letzten
    fallback-Block (davor schrieb das Modell, das abgelehnt hat), sonst alle."""
    return _nach_ausweichen(list(getattr(msg, "content", None) or []))[1]


def _socket_beenden(sock):
    """Ein blockiertes recv in einem anderen Thread wecken: shutdown() (close() allein tut das nicht). Wirft nie."""
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except (OSError, ValueError):
        pass


def _stream_socket(stream):
    """Der Socket unter einem Stream des SDK (httpx2/httpcore2: response.extensions["network_stream"]) – oder None."""
    try:
        return stream.response.extensions["network_stream"].get_extra_info("socket")
    except Exception:                            # noqa: BLE001 – andere Fassung, Attrappe, HTTP/2
        return None


def _nach_ausweichen(inhalt):
    """(was zurückgeht, was gilt) einer Antwort. Normalfall: alles unverändert. Wich die Antwort mitten in der Ausgabe auf
    ein anderes Modell aus (fallback-Block), gehen vor dem letzten fallback-Block keine Denk- und tool_use-Blöcke und
    keine Server-Werkzeugaufrufe ohne ihr Ergebnis zurück – Text, gepaarte Server-Werkzeuge, der fallback-Block selbst
    (an seiner Stelle) und alles danach schon (SDK-Doku „Echoing fallback turns back“). Ausgeführt werden nur die
    Werkzeugaufrufe nach dem Block: davor hat das Modell gesprochen, das abgelehnt hat."""
    stellen = [i for i, b in enumerate(inhalt) if getattr(b, "type", None) == "fallback"]
    if not stellen:
        return inhalt, inhalt
    grenze = stellen[-1]
    vorher = inhalt[:grenze]
    beantwortet = {getattr(b, "tool_use_id", None) for b in vorher if str(getattr(b, "type", "")).endswith("_result")}
    behalten = [b for b in vorher if getattr(b, "type", None) not in ("thinking", "redacted_thinking", "tool_use")
                and not (getattr(b, "type", None) == "server_tool_use" and b.id not in beantwortet)]
    return behalten + list(inhalt[grenze:]), list(inhalt[grenze:])


def _puls(app, lauf, stopp):
    """Lebenszeichen alle PULS_SEK; liest Abbruch-Kennzeichen und Zustand der Zeile. Ist der Lauf von außen beendet
    (für tot erklärt, gelöscht) oder abgebrochen oder die Zeit um, bricht er ab."""
    with app.app_context():
        while not stopp.wait(PULS_SEK):
            try:
                db.execute(f"UPDATE ki_laeufe SET lebenszeichen_am = ? WHERE id = ? AND status IN ({_in(LAUFEND)})",
                           (db.now(), lauf.id))
                r = db.query("SELECT status, abbrechen FROM ki_laeufe WHERE id = ?", (lauf.id,), one=True)
                if not r or r["status"] not in LAUFEND:
                    lauf.abbrechen_intern("Der Lauf wurde beendet.")
                elif r["abbrechen"]:
                    lauf.abbrechen_intern("Abgebrochen.")
                elif lauf.zeit_um():
                    lauf.abbrechen_intern(ZEIT_TEXT.format(lauf.grenze_sek // 60))
            except Exception as exc:              # noqa: BLE001 – der Puls soll nie enden, solange der Lauf lebt
                log.warning("KI-Lauf %s: Lebenszeichen gescheitert: %s", lauf.id, exc)


def _ausfuehren(app, lauf_id, arbeit, beendet):
    """Der Thread eines Laufs – in einem Anfragekontext mit dem Konto, das gestartet hat (Journal der Module)."""
    try:
        with app.test_request_context("/api/ki", method="POST"):
            z = zeile(lauf_id)
            if not z:
                return
            g.user = (db.query("SELECT * FROM users WHERE id = ? AND active = 1", (z["gestartet_von"],), one=True)
                      if z["gestartet_von"] else None)
            lauf = Lauf(z)
            with _LAEUFER_SPERRE:
                _LAEUFER[lauf_id] = lauf
            stopp = threading.Event()
            puls = threading.Thread(target=_puls, args=(app, lauf, stopp), name=f"ki-puls-{lauf_id}", daemon=True)
            puls.start()
            status, ergebnis, fehler = "fehlgeschlagen", None, ""
            try:
                db.execute("UPDATE ki_laeufe SET status = 'laeuft', lebenszeichen_am = ? WHERE id = ? "
                           "AND status = 'wartet'", (db.now(), lauf_id))
                if db.query("SELECT abbrechen FROM ki_laeufe WHERE id = ?", (lauf_id,), one=True)["abbrechen"]:
                    lauf.abbrechen_intern("Abgebrochen.")
                lauf.pruefen()
                ergebnis = arbeit(lauf)
                status = "fertig"
            except Abgebrochen as exc:
                status, fehler = "abgebrochen", str(exc) or "Abgebrochen."
            except LaufFehler as exc:
                fehler = str(exc)
            except Exception as exc:               # noqa: BLE001 – der Thread soll nie unbemerkt enden
                if lauf._abbruch.wait(0):
                    status, fehler = "abgebrochen", lauf._grund or "Abgebrochen."
                else:
                    fehler = fehlertext(exc, lauf_id)
            finally:
                stopp.set()
                puls.join(PULS_SEK + 5)
            try:
                status = _beenden_zeile(lauf_id, status, ergebnis, _schluessel_weg(fehler), lauf.usage)
            except Exception:                      # noqa: BLE001
                log.exception("KI-Lauf %s: Endstand ließ sich nicht schreiben", lauf_id)
            if lauf.ereignisse:
                log.info("KI-Lauf %s: größter Abstand zwischen zwei Ereignissen des Streams %.1f s (%d Ereignisse, "
                         "Status %s)", lauf_id, lauf.abstand_max, lauf.ereignisse, status)
            if status != "fertig":
                ordner_entfernen(lauf_id)
            # Das Konto, das gestartet hat, kann inzwischen gelöscht sein (die Kennung ist dann NULL): Der Eintrag
            # der Nacharbeit steht dann ohne Kennung da, sonst scheiterte er am Fremdschlüssel des Journals.
            try:
                r = zeile(lauf_id)
                g.user = (db.query("SELECT * FROM users WHERE id = ?", (r["gestartet_von"],), one=True)
                          if r and r["gestartet_von"] else None)
            except Exception:                      # noqa: BLE001
                g.user = None
            if beendet:
                try:
                    beendet(lauf, status)
                except Exception:                  # noqa: BLE001
                    log.exception("KI-Lauf %s: Nacharbeit gescheitert", lauf_id)
    except Exception:                              # noqa: BLE001
        log.exception("KI-Lauf %s: Thread gescheitert", lauf_id)
    finally:
        with _LAEUFER_SPERRE:
            _LAEUFER.pop(lauf_id, None)
