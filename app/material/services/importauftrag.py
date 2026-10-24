"""Katalogimport im Hintergrund (Wunsch des Nutzers, 24.10.2026).

Anlass: Die kombinierte Katalogdatei (1,13 GB, 1 428 Produkte, 1 905 Dateien) bekam beim „Übernehmen“ einen 504 vom
Reverse-Proxy – der Import lief länger, als der Proxy auf die Antwort wartet. Seitdem speichert die Anfrage nur die
Datei, legt einen Auftrag an und antwortet sofort (202); ein Thread im selben Arbeitsprozess führt
importer.datei_importieren aus – Probelauf wie Übernehmen –, und die Oberfläche fragt den Stand ab. Die Kommandozeile
(material import-catalog) bleibt synchron und kennt keine Aufträge.

Alles liegt unter DATA_DIR/katalog-import (Ordner 0700, Dateien 0600), nichts nur im Speicher – Gunicorn hat mehrere
Arbeitsprozesse, und welcher eine Abfrage beantwortet, ist Zufall:
  <kennung>.json          Zustand: wartet, laeuft, fertig, fehlgeschlagen, abgebrochen; Phase, Fortschritt, Lebenszeichen
  <kennung>.bericht.json  der Bericht im bisherigen Format, sobald der Lauf zu Ende ist
  <kennung>.datei         die hochgeladene Datei – weg, sobald der Lauf endet; nur nach einem Probelauf, der etwas zu
                          übernehmen fand, bleibt sie DATEI_FRIST liegen, damit „Übernehmen“ ohne neuen Upload startet
  <kennung>.abgelegt      die Dateien, die ein echter Lauf schon unter media/material abgelegt hat (eine Zeile je
                          Datei) – zum Aufräumen, falls sein Prozess mitten im Lauf endet
  sperre                  Dateisperre (fcntl.flock): höchstens ein Katalogimport gleichzeitig in der ganzen App. Sie
                          gehört dem Thread des Laufs und endet mit ihm – auch mit seinem Prozess (Neustart, Deploy).
                          Der Inhalt (Kennung, PID, Zeit) ist nur ein Hinweis, entschieden wird über die Sperre selbst.
Geschrieben wird jede Datei atomar (Zwischendatei, dann os.replace); was sich nicht lesen lässt, gilt als nicht da.
Die Kennung ist zufällig (32 Hex-Zeichen) und wird gegen ein Muster geprüft, bevor sie in einen Pfad kommt.

Endet der Prozess eines Laufs, steht im Zustand noch „wartet“ oder „laeuft“. Als abgebrochen gilt ein solcher Auftrag,
wenn niemand die Sperre hält UND sein Lebenszeichen (alle LEBENSZEICHEN_SEK) älter als TOT_NACH ist – beides zusammen,
damit weder eine Sperre, die ein Dateisystem nicht hält, noch ein langsamer Schritt einen lebenden Lauf für tot erklärt.
Wer das feststellt (die nächste Abfrage, der nächste Start, der Tageslauf), hält dabei selbst die Sperre: Er setzt den
Zustand auf „abgebrochen“, entfernt die hochgeladene Datei und räumt die abgelegten Dateien weg, die das Protokoll nennt
und keine Zeile (Produktbilder ohne mat_product.image; Dokumentdateien über katalog._datei_freigeben, das nur entfernt,
was kein Dokument nennt). Eine Datei, die der Lauf im Moment des Abbruchs gerade schrieb, steht noch in keinem Protokoll
und kann liegen bleiben – sie ist mit nichts verknüpft und wird nie angezeigt (Dokumente heißen nach ihrem Inhalt und
werden beim nächsten Lauf wiederverwendet). Bilder ohne Besitzer aus dem Zeitfenster des Laufs wegzuräumen wäre nicht
sicher: Ein Bild, das jemand anderes gerade hochlädt, hat bis zu seinem Commit auch noch keine Zeile.
Die Datenbank schreibt der Import in einer Transaktion – halb geschrieben ist dort nie etwas. Unmittelbar nach dem Commit
vermerkt der Zustand „gespeichert“ (Rückruf des Importers); daran entscheiden Abbruch und unerwarteter Fehler, was sie
melden. Bricht ein „Übernehmen“ ab, bevor es gespeichert hat, bekommt der Probelauf seine Datei zurück und lässt sich
noch einmal DATEI_FRIST lang übernehmen (Nachbesserung nach der Sicherheitsprüfung vom 24.10.2026). Das ist ohne
Risiko: Die Transaktion hat nichts geschrieben – und fiele der Abbruch genau zwischen Commit und Vermerk, fände der
zweite Lauf nichts mehr zu ändern, denn der Import gleicht ab und legt nichts doppelt an.

Plattenplatz: Ein neuer Auftrag löscht die Dateien älterer Probeläufe (es läuft ohnehin nur einer, und ihr „Übernehmen“
wäre damit überholt); vor dem Kopieren der hochgeladenen Datei und vor „Übernehmen“ muss so viel frei sein, wie die Datei
groß ist, plus RESERVE – sonst 507 mit einer Meldung ohne Pfad.

Aufgehoben werden Zustände und Berichte AUFHEBEN lang (7 Tage). Der Bericht nennt keine Personen. Der Zustand nennt das
Konto, das den Import gestartet hat, nur über seinen pseudonymen Kontoverweis users.mat_ref (von_ref, wie das Journal) –
nie Name, E-Mail oder users.id: Die Kontokennung vergibt SQLite nach dem Löschen eines Kontos neu, mat_ref verschwindet
mit der Kontozeile. Den Namen löst jede Anzeige frisch auf (journal.konto_name); nach dem Löschen steht dort
„(gelöschtes Konto)“, und ein neues Konto mit derselben Kennung kann einen fremden Probelauf nicht übernehmen
(Nachbesserung nach der Sicherheitsprüfung vom 24.10.2026). Zustände aus der ersten Fassung mit von_id und Namen verlieren
beide Felder beim nächsten Aufräumen; übernehmen lässt sich ein solcher Probelauf nicht mehr."""
import fcntl
import json
import logging
import os
import re
import secrets
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import current_app, g

from ... import db
from ...images import delete_photo_files
from . import Abgelehnt, importer, journal, katalog

log = logging.getLogger(__name__)

ORDNER = "katalog-import"
KENNUNG = re.compile(r"[0-9a-f]{32}")
ZUSTAENDE = ("wartet", "laeuft", "fertig", "fehlgeschlagen", "abgebrochen")
OFFEN = ("wartet", "laeuft")
PHASEN = ("pruefen", "probe", "ablegen", "schreiben")
DATEI_FRIST = 60 * 60              # so lange bleibt die Datei eines Probelaufs für „Übernehmen“ liegen
AUFHEBEN = 7 * 24 * 60 * 60        # Zustände und Berichte beendeter Aufträge
HINWEIS_FRIST = 24 * 60 * 60       # so lange zeigt die Katalogseite einen beendeten Auftrag als Hinweis
LEBENSZEICHEN_SEK = 5
TOT_NACH = 30                      # ohne Sperre und ohne Lebenszeichen seit so vielen Sekunden: abgebrochen
SCHREIB_ABSTAND = 1.0              # Fortschritt höchstens einmal je Sekunde auf die Platte
SPERRE_WARTEN = 3.0                # so lange wartet ein Start, falls gerade jemand nur aufräumt
RESERVE = 64 * 1024 * 1024         # so viel bleibt nach der Datei mindestens frei (wie zuruecksetzen.RESERVE)
# Abgelegte Dateien im Protokoll: Produktbilder heißen <16 Hex>.<Endung> (store_upload), Dokumente <SHA-256>.<Endung>.
_ABGELEGT = re.compile(r"[0-9a-f]{16,64}\.[a-z0-9]{1,5}")

_LAEUFER = {}                      # Kennung → Thread, nur in diesem Prozess – für warten() in Tests


class Belegt(Abgelehnt):
    """Es läuft schon ein Katalogimport: 409 mit dem laufenden Auftrag."""

    def __init__(self, meldung, auftrag=None):
        super().__init__(meldung, 409)
        self.auftrag = auftrag


# --- Dateien ---------------------------------------------------------------------------------------

def _ordner():
    pfad = os.path.join(current_app.config["DATA_DIR"], ORDNER)
    os.makedirs(pfad, mode=0o700, exist_ok=True)
    try:
        os.chmod(pfad, 0o700)
    except OSError:
        pass
    return pfad


def _pfad(kennung, endung):
    if not isinstance(kennung, str) or not KENNUNG.fullmatch(kennung):
        raise ValueError("ungültige Auftragskennung")
    return os.path.join(_ordner(), kennung + endung)


def _entfernen(pfad):
    try:
        os.remove(pfad)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("Katalogimport: %s ließ sich nicht entfernen: %s", os.path.basename(pfad), exc)


def _atomar(pfad, daten):
    """JSON nach pfad: erst in eine eigene Zwischendatei (0600), dann os.replace – wer liest, sieht den alten oder den
    neuen Stand, nie einen halben."""
    zwischen = f"{pfad}.{secrets.token_hex(4)}.neu"
    fd = os.open(zwischen, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(daten, fh, ensure_ascii=False)
        os.replace(zwischen, pfad)
    except BaseException:
        _entfernen(zwischen)
        raise


def _json(pfad):
    try:
        with open(pfad, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError, RecursionError):
        return None


def _lesen(kennung):
    """Der Zustand eines Auftrags – oder None, wenn es ihn nicht gibt oder die Datei nicht zu gebrauchen ist."""
    try:
        z = _json(_pfad(kennung, ".json"))
    except ValueError:
        return None
    if (not isinstance(z, dict) or z.get("id") != kennung or z.get("zustand") not in ZUSTAENDE
            or not isinstance(z.get("gestartet"), str) or not isinstance(z.get("trocken"), bool)):
        return None
    return z


def _alle():
    """Alle lesbaren Zustände, neueste zuerst."""
    try:
        namen = os.listdir(_ordner())
    except OSError:
        return []
    out = []
    for name in namen:
        if name.endswith(".json") and KENNUNG.fullmatch(name[:-5]):
            z = _lesen(name[:-5])
            if z:
                out.append(z)
    # gestartet hat Sekunden – Probelauf und Übernehmen können in dieselbe fallen; beginn (time.time()) entscheidet dann.
    return sorted(out, key=lambda z: (z["gestartet"], z.get("beginn") if isinstance(z.get("beginn"), float) else 0.0),
                  reverse=True)


def _sekunden_seit(iso):
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return float("inf")
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds()


def _spaeter(sekunden):
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=sekunden)).isoformat()


# --- Sperre ----------------------------------------------------------------------------------------

def _sperre_nehmen(warten=0.0):
    """Die app-weite Sperre (flock auf DATA_DIR/katalog-import/sperre) – als offene Datei, die sie hält, bis sie
    geschlossen wird; None, wenn sie in warten Sekunden nicht frei wird. Jede open() ist eine eigene Sperrbeschreibung:
    Auch ein anderer Thread desselben Prozesses bekommt sie nicht, solange der Lauf sie hält."""
    pfad = os.path.join(_ordner(), "sperre")
    ende = time.monotonic() + warten
    while True:
        fd = os.open(pfad, os.O_RDWR | os.O_CREAT, 0o600)
        fh = os.fdopen(fd, "r+", encoding="utf-8")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            fh.close()
        if time.monotonic() >= ende:
            return None
        time.sleep(0.1)


def _sperre_beschriften(fh, kennung):
    """Nur ein Hinweis für Menschen und für die 409-Antwort – entschieden wird über flock."""
    try:
        fh.seek(0)
        fh.truncate()
        if kennung:
            json.dump({"auftrag": kennung, "pid": os.getpid(), "seit": db.now()}, fh)
        fh.flush()
    except OSError:
        pass


def _inhaber():
    """Die Kennung, die in der Sperrdatei steht – oder None (leer, kaputt, fremd)."""
    d = _json(os.path.join(_ordner(), "sperre"))
    k = d.get("auftrag") if isinstance(d, dict) else None
    return k if isinstance(k, str) and KENNUNG.fullmatch(k) else None


def _lebt(z):
    """Ein offener Auftrag gilt als lebendig, solange sein Lebenszeichen frisch ist – ob die Sperre gehalten wird,
    prüft der Aufrufer (_aufraeumen_unter_sperre läuft nur, wenn er sie selbst bekommen hat)."""
    return _sekunden_seit(z.get("lebenszeichen") or z["gestartet"]) < TOT_NACH


# --- Öffentliche Sicht ------------------------------------------------------------------------------

def _uebernehmbar(z):
    return (z["trocken"] and z["zustand"] == "fertig" and not z.get("uebernommen_in") and bool(z.get("datei_bis"))
            and _sekunden_seit(z["datei_bis"]) < 0 and os.path.isfile(_pfad(z["id"], ".datei")))


def _ref(uid, setzen=False):
    """Der Kontoverweis (users.mat_ref) des Kontos uid – mit setzen wird er angelegt, falls er fehlt (journal.konto_ref,
    beim Start); die Abfragen alle paar Sekunden lesen nur. None ohne Konto."""
    if uid is None:
        return None
    if setzen:
        return journal.konto_ref(uid)["ref"]
    r = db.query("SELECT mat_ref FROM users WHERE id = ?", (uid,), one=True)
    return r["mat_ref"] if r and r["mat_ref"] else None


def _von(z):
    """Der Name dessen, der den Auftrag gestartet hat – frisch aufgelöst, „(gelöschtes Konto)“ nach dem Löschen."""
    ref = z.get("von_ref")
    return journal.konto_name(ref) if isinstance(ref, str) and ref else None


def _erneut(z):
    """Für ein abgebrochenes „Übernehmen“, dessen Probelauf seine Datei zurückbekam (_abbrechen): dieser Probelauf,
    solange er sich übernehmen lässt – sonst None."""
    if z["trocken"] or z["zustand"] != "abgebrochen" or not isinstance(z.get("aus"), str):
        return None
    alt = _lesen(z["aus"]) if KENNUNG.fullmatch(z["aus"]) else None
    if alt and alt.get("von_ref") == z.get("von_ref") and _uebernehmbar(alt):
        return alt
    return None


def oeffentlich(z, nutzer_id=None, mit_bericht=False):
    """Was die Schnittstelle von einem Auftrag zeigt. Ohne Kontoverweis und ohne Pfade; bericht nur auf Wunsch (die
    Abfrage während des Laufs braucht ihn nicht). Ein abgebrochenes „Übernehmen“, das sich wiederholen lässt, zeigt
    uebernehmbar und datei_bis seines Probelaufs."""
    ref = _ref(nutzer_id)
    eigener = ref is not None and z.get("von_ref") == ref
    out = {k: z.get(k) for k in ("id", "zustand", "trocken", "quelle", "groesse", "gestartet", "beendet",
                                 "lebenszeichen", "phase", "n", "m", "fehler", "aus", "uebernommen_in")}
    out["von"] = _von(z)
    out["eigener"] = eigener
    bereit = z if _uebernehmbar(z) else _erneut(z)
    out["uebernehmbar"] = eigener and bereit is not None
    out["datei_bis"] = bereit.get("datei_bis") if bereit else None
    if mit_bericht:
        out["bericht"] = None
        if z["zustand"] not in OFFEN:
            b = _json(_pfad(z["id"], ".bericht.json"))
            out["bericht"] = b if isinstance(b, dict) else None
    return out


def lesen(kennung, nutzer_id=None):
    """Ein Auftrag für GET …/katalog/import/<kennung>: erst, ob ein offener noch lebt (sonst „abgebrochen“), dann die
    öffentliche Sicht mit Bericht. Unbekannt oder unlesbar: Abgelehnt 404."""
    z = _lesen(kennung) if isinstance(kennung, str) and KENNUNG.fullmatch(kennung) else None
    if z and z["zustand"] in OFFEN and not _lebt(z):
        sperre = _sperre_nehmen()
        if sperre:
            try:
                _aufraeumen_unter_sperre()
            finally:
                sperre.close()
            z = _lesen(kennung)
    if not z:
        raise Abgelehnt("Diesen Importauftrag gibt es nicht (mehr).", 404)
    return oeffentlich(z, nutzer_id, mit_bericht=True)


def aktuell(nutzer_id=None):
    """Für den Hinweis auf der Katalogseite: der neueste Auftrag, wenn er noch läuft oder vor höchstens HINWEIS_FRIST
    endete – sonst None. Räumt vorher auf (dabei werden Aufträge toter Prozesse zu „abgebrochen“)."""
    aufraeumen()
    alle = _alle()
    if alle and (alle[0]["zustand"] in OFFEN or _sekunden_seit(alle[0].get("beendet")) < HINWEIS_FRIST):
        return oeffentlich(alle[0], nutzer_id)
    return None


def _belegt_meldung():
    z = None
    k = _inhaber()
    if k:
        z = _lesen(k)
    if not z or z["zustand"] not in OFFEN:
        z = next((x for x in _alle() if x["zustand"] in OFFEN), None)
    wer = f" von {_von(z)}" if z and _von(z) else ""
    text = ("Es läuft schon ein Katalogimport" + wer + ". Es kann immer nur einer laufen – bitte warten, bis er fertig "
            "ist; sein Stand steht auf der Katalogseite.")
    return Belegt(text, oeffentlich(z) if z else None)


# --- Start -----------------------------------------------------------------------------------------

def _neuer_zustand(kennung, trocken, quelle, groesse, nutzer, aus=None):
    jetzt = db.now()
    return {"id": kennung, "zustand": "wartet", "trocken": bool(trocken), "quelle": quelle, "groesse": groesse,
            "von_ref": _ref(nutzer[0], setzen=True), "gestartet": jetzt, "lebenszeichen": jetzt, "beendet": None,
            "phase": None, "n": None, "m": None, "fehler": None, "aus": aus, "uebernommen_in": None,
            "gespeichert": False, "datei_bis": None, "beginn": time.time()}


def _gb(n):
    return f"{n / 1024 ** 3:.1f} GB".replace(".", ",")


def _platz_pruefen(groesse, wofuer):
    """507, wenn auf dem Dateisystem von DATA_DIR weniger frei ist als groesse + RESERVE. Die Meldung nennt Zahlen,
    keinen Pfad."""
    try:
        frei = shutil.disk_usage(_ordner()).free
    except OSError as exc:
        log.warning("Katalogimport: freier Platz nicht feststellbar: %s", exc)
        return
    if frei < (groesse or 0) + RESERVE:
        log.warning("Katalogimport: zu wenig Platz (%s frei, %s gebraucht)", frei, (groesse or 0) + RESERVE)
        raise Abgelehnt(f"Auf dem Server ist zu wenig Platz für {wofuer}: frei {_gb(frei)}, gebraucht etwa "
                        f"{_gb((groesse or 0) + RESERVE)}. Bitte die Betreuung des Servers bitten, Platz zu schaffen, "
                        "dann erneut versuchen.", 507)


def _alte_probelaeufe_freigeben():
    """Die Dateien aller älteren Probeläufe entfernen (nur unter der Sperre, vor einem neuen Auftrag): Ihr „Übernehmen“
    ist mit dem neuen Auftrag überholt, und jede liegt sonst eine Stunde mit voller Größe auf der Platte."""
    for z in _alle():
        if z["trocken"] and z["zustand"] not in OFFEN:
            _entfernen(_pfad(z["id"], ".datei"))


def _hochgeladen_groesse(datei):
    """Wie groß die hochgeladene Datei ist (Werkzeug hält sie in einem Zwischenspeicher) – 0, wenn sich das nicht
    feststellen lässt; dann prüft _platz_pruefen nur die Reserve."""
    try:
        datei.stream.seek(0, os.SEEK_END)
        return datei.stream.tell()
    except (AttributeError, OSError, ValueError):
        return 0


def starten(datei, trocken, quelle, nutzer):
    """Die hochgeladene Datei (FileStorage) unter DATA_DIR/katalog-import ablegen und den Lauf im Hintergrund starten.
    nutzer: (Kontokennung, Name) – akteur(). Liefert die öffentliche Sicht des neuen Auftrags; Belegt (409), wenn schon
    einer läuft; 507, wenn der Platz für die Datei nicht reicht."""
    aufraeumen()
    sperre = _sperre_nehmen(SPERRE_WARTEN)
    if sperre is None:
        raise _belegt_meldung()
    ziel = None
    try:
        if _aufraeumen_unter_sperre():
            raise _belegt_meldung()
        _alte_probelaeufe_freigeben()
        _platz_pruefen(_hochgeladen_groesse(datei), "die Katalogdatei")
        kennung = secrets.token_hex(16)
        _sperre_beschriften(sperre, kennung)
        ziel = _pfad(kennung, ".datei")
        groesse = _hochgeladen_ablegen(datei, ziel)
        z = _neuer_zustand(kennung, trocken, quelle, groesse, nutzer)
        _atomar(_pfad(kennung, ".json"), z)
        _thread_starten(z, sperre)
    except BaseException:
        if ziel:
            _entfernen(ziel)
        sperre.close()
        raise
    return oeffentlich(z, nutzer[0])


def _hochgeladen_ablegen(datei, ziel):
    """Die Datei der Anfrage (Werkzeug hält sie unter TMP_DIR) an ihren Platz kopieren – sie verschwindet mit der Anfrage.
    Liefert die Größe. Ein Fehler des Dateisystems nennt den Pfad – der gehört ins Protokoll, nicht in die Antwort."""
    try:
        datei.stream.seek(0)
        fd = os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as aus:
            shutil.copyfileobj(datei.stream, aus, 1024 * 1024)
        return os.path.getsize(ziel)
    except OSError as exc:
        _entfernen(ziel)
        log.warning("Katalogimport: Datei ließ sich nicht zwischenspeichern: %s", exc)
        raise Abgelehnt("Die Datei ließ sich auf dem Server nicht zwischenspeichern (Platte voll?). Bitte später "
                        "erneut versuchen.", 500)


def uebernehmen(kennung, nutzer):
    """„Übernehmen“ nach einem Probelauf: derselbe Import echt, mit der Datei des Probelaufs – ohne neuen Upload. Nur
    wer den Probelauf gestartet hat, solange seine Datei liegt (DATEI_FRIST). kennung darf auch ein abgebrochenes
    „Übernehmen“ sein, dessen Probelauf seine Datei zurückbekam – dann gilt dieser. Liefert den neuen Auftrag."""
    if not isinstance(kennung, str) or not KENNUNG.fullmatch(kennung) or not _lesen(kennung):
        raise Abgelehnt("Diesen Importauftrag gibt es nicht (mehr).", 404)
    sperre = _sperre_nehmen(SPERRE_WARTEN)
    if sperre is None:
        raise _belegt_meldung()
    try:
        if _aufraeumen_unter_sperre():
            raise _belegt_meldung()
        alt = _lesen(kennung)
        if alt and not alt["trocken"] and alt["zustand"] == "abgebrochen" and isinstance(alt.get("aus"), str) \
                and KENNUNG.fullmatch(alt["aus"]):
            kennung = alt["aus"]
            alt = _lesen(kennung)
        if not alt:
            raise Abgelehnt("Diesen Importauftrag gibt es nicht (mehr).", 404)
        ref = _ref(nutzer[0])
        if ref is None or alt.get("von_ref") != ref:
            raise Abgelehnt("Übernehmen kann nur, wer den Probelauf gestartet hat.", 403)
        if not alt["trocken"] or alt["zustand"] != "fertig":
            raise Abgelehnt("Übernehmen geht nur nach einem Probelauf ohne Fehler.", 409)
        if alt.get("uebernommen_in"):
            raise Abgelehnt("Dieser Probelauf ist schon übernommen worden.", 409)
        if not _uebernehmbar(alt):
            raise Abgelehnt("Die Datei des Probelaufs liegt nicht mehr bereit (sie bleibt eine Stunde, bis zum nächsten "
                            "Import). Bitte die Datei noch einmal wählen.", 409)
        # Der Import legt Bilder und Dokumente ab – ungefähr so viel, wie die Datei groß ist.
        _platz_pruefen(alt.get("groesse") if isinstance(alt.get("groesse"), int) else 0, "die Dateien des Katalogs")
        neu = secrets.token_hex(16)
        _sperre_beschriften(sperre, neu)
        os.replace(_pfad(kennung, ".datei"), _pfad(neu, ".datei"))
        z = _neuer_zustand(neu, False, alt.get("quelle") or "Datei", alt.get("groesse"), nutzer, aus=kennung)
        try:
            _atomar(_pfad(neu, ".json"), z)
            alt.update(uebernommen_in=neu, datei_bis=None)
            _atomar(_pfad(kennung, ".json"), alt)
        except BaseException:
            _entfernen(_pfad(neu, ".datei"))
            raise
        _alte_probelaeufe_freigeben()
        _thread_starten(z, sperre)
    except BaseException:
        sperre.close()
        raise
    return oeffentlich(z, nutzer[0])


# --- Der Lauf ---------------------------------------------------------------------------------------

def _thread_starten(z, sperre):
    app = current_app._get_current_object()
    t = threading.Thread(target=_ausfuehren, args=(app, z, sperre), name=f"katalogimport-{z['id'][:8]}", daemon=True)
    _LAEUFER[z["id"]] = t
    t.start()


def warten(kennung, sekunden=120):
    """Bis der Lauf dieses Prozesses zu Ende ist (Tests). Liefert, ob er zu Ende ist."""
    t = _LAEUFER.get(kennung)
    if t is not None:
        t.join(sekunden)
        return not t.is_alive()
    return True


class _Lauf:
    """Zustand und Rückruf eines laufenden Auftrags. Der Zustand wird von zwei Threads geschrieben – dem Lauf und dem
    Lebenszeichen (ohne Anwendungskontext, deshalb die Pfade schon hier) –, also unter einer Sperre und immer als Ganzes
    (_atomar)."""

    def __init__(self, z):
        self.z = z
        self.zustand_pfad = _pfad(z["id"], ".json")
        self.protokoll_pfad = _pfad(z["id"], ".abgelegt")
        self.sperre = threading.Lock()
        self.geschrieben = 0.0
        self.protokoll = None              # <kennung>.abgelegt, offen ab der ersten abgelegten Datei

    def sichern(self, erzwingen=False, **felder):
        with self.sperre:
            phase_neu = "phase" in felder and felder["phase"] != self.z.get("phase")
            self.z.update(felder)
            if not (erzwingen or phase_neu or time.monotonic() - self.geschrieben >= SCHREIB_ABSTAND):
                return
            self.z["lebenszeichen"] = db.now()
            try:
                _atomar(self.zustand_pfad, self.z)
                self.geschrieben = time.monotonic()
            except OSError as exc:
                log.warning("Katalogimport: Zustand ließ sich nicht schreiben: %s", exc)

    def fortschritt(self, phase, n=None, m=None, abgelegt=None):
        """Der Rückruf für importer.datei_importieren. Wirft nie – der Import soll an der Anzeige nicht scheitern.
        „gespeichert“ (gleich nach dem Commit) geht sofort auf die Platte."""
        try:
            if abgelegt:
                self._vermerken(abgelegt)
            if phase == "gespeichert":
                self.sichern(erzwingen=True, gespeichert=True)
            elif phase in PHASEN:
                self.sichern(phase=phase, n=n, m=m)
        except Exception as exc:              # noqa: BLE001 – siehe oben
            log.warning("Katalogimport: Fortschritt nicht vermerkt: %s", exc)

    def _vermerken(self, abgelegt):
        """Eine abgelegte Datei sofort ins Protokoll – endet der Prozess gleich danach, weiß der Aufräumer von ihr."""
        art, wert = abgelegt
        name = wert if art == "bild" else wert[0]
        if self.protokoll is None:
            fd = os.open(self.protokoll_pfad, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            self.protokoll = os.fdopen(fd, "a", encoding="utf-8")
        self.protokoll.write(json.dumps([art, name]) + "\n")
        self.protokoll.flush()

    def schliessen(self):
        if self.protokoll is not None:
            try:
                self.protokoll.close()
            except OSError:
                pass
            self.protokoll = None


def _gespeichert_text(z):
    """Was ein Abbruch über die Datenbank sagen kann: Ein Probelauf und ein Lauf vor seinem Commit haben nichts
    gespeichert; nach dem Vermerk „gespeichert“ (gleich nach dem Commit) ist die Datenbank geschrieben."""
    if z["trocken"] or not z.get("gespeichert"):
        return "Gespeichert wurde nichts."
    return ("Die Datenbank war da schon geschrieben; ob alles übernommen ist, zeigt ein neuer Probelauf mit derselben "
            "Datei.")


def _lebenszeichen(lauf, stopp):
    while not stopp.wait(LEBENSZEICHEN_SEK):
        lauf.sichern(erzwingen=True)


def _fehlerbericht(trocken, meldung):
    """Ein Bericht im bisherigen Format, der nur einen Fehler nennt – für eine Datei, die sich nicht lesen lässt
    (synchron war das ein 400), und für einen unerwarteten Abbruch."""
    b = importer._bericht()
    b["trocken"] = bool(trocken)
    b["fehler"].append(meldung)
    return b


def _ausfuehren(app, z, sperre):
    """Der Thread eines Auftrags. Läuft in einem Anfragekontext mit dem Konto, das den Import gestartet hat – so stehen
    Journal und Bearbeiter wie beim synchronen Import da (journal.eintragen, akteur). Die Sperre gibt erst das Ende des
    Threads frei, nach dem letzten Zustand."""
    try:
        with app.test_request_context("/api/material/katalog/import", method="POST"):
            _lauf_im_kontext(z)
    except Exception:                             # noqa: BLE001 – der Thread soll nie unbemerkt enden
        log.exception("Katalogimport %s: Lauf gescheitert", z["id"][:8])
    finally:
        try:
            sperre.close()
        finally:
            _LAEUFER.pop(z["id"], None)


def _lauf_im_kontext(z):
    """Import, dann in dieser Reihenfolge: Lebenszeichen aus, Datei weg (oder für „Übernehmen“ behalten), Bericht,
    Zustand."""
    lauf = _Lauf(z)
    stopp = threading.Event()
    ticker = threading.Thread(target=_lebenszeichen, args=(lauf, stopp), name=f"katalogimport-lz-{z['id'][:8]}",
                              daemon=True)
    ticker.start()
    zustand, bericht, fehler = "fehlgeschlagen", None, None
    try:
        g.user = (db.query("SELECT * FROM users WHERE mat_ref = ? AND active = 1", (z["von_ref"],), one=True)
                  if isinstance(z.get("von_ref"), str) and z["von_ref"] else None)
        lauf.sichern(erzwingen=True, zustand="laeuft")
        try:
            with open(_pfad(z["id"], ".datei"), "rb") as fh:
                bericht = importer.datei_importieren(fh, trocken=z["trocken"], quelle=z.get("quelle") or "Datei",
                                                     fortschritt=lauf.fortschritt)
            zustand = "fehlgeschlagen" if bericht["fehler"] else "fertig"
        except Abgelehnt as exc:
            bericht = _fehlerbericht(z["trocken"], str(exc))
        except Exception:                         # noqa: BLE001 – jeder andere Fehler beendet den Auftrag
            log.exception("Katalogimport %s abgebrochen", z["id"][:8])
            fehler = "Der Import brach mit einem unerwarteten Fehler ab. " + _gespeichert_text(lauf.z) + \
                " Einzelheiten stehen im Protokoll des Servers."
            bericht = _fehlerbericht(z["trocken"], fehler)
    finally:
        stopp.set()
        ticker.join(LEBENSZEICHEN_SEK + 1)
        lauf.schliessen()
        behalten = (zustand == "fertig" and z["trocken"] and bericht is not None
                    and bool(bericht["aenderungen"] or bericht["hinweise"]))
        if not behalten:
            _entfernen(_pfad(z["id"], ".datei"))
        _entfernen(lauf.protokoll_pfad)
        try:
            if bericht is not None:
                _atomar(_pfad(z["id"], ".bericht.json"), bericht)
        except (OSError, ValueError) as exc:
            log.warning("Katalogimport: Bericht ließ sich nicht schreiben: %s", exc)
            zustand, fehler = "fehlgeschlagen", "Der Bericht ließ sich nicht speichern."
        lauf.sichern(erzwingen=True, zustand=zustand, fehler=fehler, beendet=db.now(),
                     datei_bis=_spaeter(DATEI_FRIST) if behalten else None)


# --- dev-zuruecksetzen ------------------------------------------------------------------------------

def anhalten():
    """Für dev-zuruecksetzen: die Sperre nehmen und behalten, damit währenddessen kein Katalogimport startet (ein Start
    bekommt 409). Liefert die offene Sperrdatei – schließen gibt sie frei – oder None, wenn gerade ein Import läuft oder
    eben erst endete (frisches Lebenszeichen)."""
    sperre = _sperre_nehmen()
    if sperre is None:
        return None
    try:
        if _aufraeumen_unter_sperre():
            sperre.close()
            return None
        _sperre_beschriften(sperre, None)
    except BaseException:
        sperre.close()
        raise
    return sperre


def laeuft():
    """Ob gerade ein Katalogimport läuft (Sperre gehalten oder offener Auftrag mit frischem Lebenszeichen) – nur
    nachsehen, ohne aufzuräumen und ohne etwas anzulegen (dev-zuruecksetzen --trocken). Ohne Sperrdatei lief nie einer."""
    if not os.path.exists(os.path.join(current_app.config["DATA_DIR"], ORDNER, "sperre")):
        return False
    sperre = _sperre_nehmen()
    if sperre is None:
        return True
    sperre.close()
    return any(z["zustand"] in OFFEN and _lebt(z) for z in _alle())


def zwischendaten():
    """(Dateien, Bytes) unter DATA_DIR/katalog-import ohne die Sperrdatei – für den Bericht von dev-zuruecksetzen."""
    pfad = os.path.join(current_app.config["DATA_DIR"], ORDNER)
    dateien = groesse = 0
    try:
        namen = os.listdir(pfad)
    except OSError:
        return 0, 0
    for name in namen:
        if KENNUNG.fullmatch(name.partition(".")[0]):
            try:
                groesse += os.lstat(os.path.join(pfad, name)).st_size
                dateien += 1
            except OSError:
                pass
    return dateien, groesse


def leeren_unter_sperre():
    """Alle Aufträge mit Zustand, Bericht, Datei und Protokoll entfernen – nur mit der Sperre aus anhalten() in der Hand
    (dev-zuruecksetzen nach dem COMMIT: Sie beziehen sich auf den geleerten Katalog). Die Sperrdatei bleibt, andere
    Dateien auch; entfernt wird jede Datei einzeln mit genauem Namen."""
    ordner = _ordner()
    for name in os.listdir(ordner):
        if KENNUNG.fullmatch(name.partition(".")[0]):
            _entfernen(os.path.join(ordner, name))


# --- Aufräumen --------------------------------------------------------------------------------------

def _abgelegte_wegraeumen(kennung):
    """Was ein abgebrochener echter Lauf schon abgelegt hatte: Produktbilder, die keine Zeile nennt, weg; Dokumentdateien
    über katalog._datei_freigeben (entfernt nur, was kein Dokument nennt – eine schon gespeicherte bleibt). Hatte der
    Lauf noch committet, nennt die Datenbank seine Dateien, und sie bleiben."""
    pfad = _pfad(kennung, ".abgelegt")
    try:
        with open(pfad, encoding="utf-8") as fh:
            zeilen = fh.read().splitlines()
    except OSError:
        return
    for zeile in zeilen:
        try:
            art, name = json.loads(zeile)
        except (ValueError, TypeError):
            continue                               # die letzte Zeile kann halb geschrieben sein
        if not isinstance(name, str) or not _ABGELEGT.fullmatch(name):
            continue
        if art == "bild":
            if not db.query("SELECT 1 FROM mat_product WHERE image = ? LIMIT 1", (name,), one=True):
                delete_photo_files(katalog.medien_dir(), name)
        elif art == "dokument":
            katalog._datei_freigeben(name)
    _entfernen(pfad)


def _zurueck_zum_probelauf(z):
    """Ein abgebrochenes „Übernehmen“ ohne Vermerk „gespeichert“: Die Datei geht an seinen Probelauf zurück, der sich
    dann wieder DATEI_FRIST lang übernehmen lässt (siehe oben). Nur, wenn dieser Probelauf noch auf genau diesen Auftrag
    zeigt und die Datei da ist. Liefert, ob es geklappt hat."""
    aus = z.get("aus")
    if (z["trocken"] or z.get("gespeichert") or not isinstance(aus, str) or not KENNUNG.fullmatch(aus)
            or not isinstance(z.get("von_ref"), str)):
        return False
    alt = _lesen(aus)
    datei = _pfad(z["id"], ".datei")
    if not (alt and alt["trocken"] and alt["zustand"] == "fertig" and alt.get("uebernommen_in") == z["id"]
            and alt.get("von_ref") == z.get("von_ref") and os.path.isfile(datei)):
        return False
    os.replace(datei, _pfad(aus, ".datei"))
    alt.update(uebernommen_in=None, datei_bis=_spaeter(DATEI_FRIST))
    try:
        _atomar(_pfad(aus, ".json"), alt)
    except BaseException:
        _entfernen(_pfad(aus, ".datei"))
        raise
    return True


def _abbrechen(z):
    """Einen offenen Auftrag, dessen Prozess weg ist, beenden (nur unter der Sperre)."""
    if not z["trocken"]:
        _abgelegte_wegraeumen(z["id"])
    _entfernen(_pfad(z["id"], ".abgelegt"))
    erneut = _zurueck_zum_probelauf(z)
    _entfernen(_pfad(z["id"], ".datei"))
    # Was er schon unter media/material abgelegt hatte, ist weggeräumt (bis auf höchstens die eine Datei, die er gerade
    # schrieb – siehe oben); das sagt die Meldung nicht mehr, es steht im README.
    unterbrochen = f"Der {'Probelauf' if z['trocken'] else 'Import'} wurde unterbrochen (etwa durch einen Neustart des " \
        "Servers)"
    if z["trocken"]:
        text = f"{unterbrochen}. Gespeichert wurde nichts."
    elif z.get("gespeichert"):
        text = f"{unterbrochen}. {_gespeichert_text(z)}"
    else:
        text = f"{unterbrochen}, bevor er gespeichert hatte – die Datenbank schreibt er ganz oder gar nicht. "
        text += ("„Übernehmen“ geht noch einmal, solange die Datei des Probelaufs bereitliegt (eine Stunde)." if erneut
                 else "Ob noch etwas zu übernehmen ist, zeigt ein neuer Probelauf mit derselben Datei.")
    z.update(zustand="abgebrochen", beendet=db.now(), fehler=text, datei_bis=None)
    _atomar(_pfad(z["id"], ".json"), z)
    log.warning("Katalogimport %s: als abgebrochen erkannt (Prozess weg)", z["id"][:8])


def _aufraeumen_unter_sperre():
    """Nur mit der Sperre in der Hand – dann läuft gerade kein Import und keiner startet: Offene Aufträge ohne frisches
    Lebenszeichen sind abgebrochen; Dateien ohne Zustand (ein Start, der vor dem Schreiben des Zustands endete) und
    liegengebliebene Zwischendateien gehen weg. Liefert, ob ein offener Auftrag mit frischem Lebenszeichen da ist – dann
    endete sein Prozess eben erst (oder die Sperre hält auf diesem Dateisystem nicht), und gestartet wird nicht."""
    lebendig = False
    for z in _alle():
        if z["zustand"] in OFFEN:
            if _lebt(z):
                lebendig = True
            else:
                try:
                    _abbrechen(z)
                except Exception as exc:          # noqa: BLE001 – ein Auftrag soll die übrigen nicht aufhalten
                    log.warning("Katalogimport %s: Abbruch nicht vermerkt: %s", z["id"][:8], exc)
    ordner = _ordner()
    try:
        namen = os.listdir(ordner)
    except OSError:
        return lebendig
    for name in namen:
        kennung, _, endung = name.partition(".")
        if not KENNUNG.fullmatch(kennung):
            continue
        pfad = os.path.join(ordner, name)
        if endung.endswith(".neu"):
            try:
                if time.time() - os.path.getmtime(pfad) > 60:
                    _entfernen(pfad)
            except OSError:
                pass
        elif endung in ("datei", "abgelegt") and not os.path.exists(os.path.join(ordner, kennung + ".json")):
            if endung == "abgelegt":
                _abgelegte_wegraeumen(kennung)
            _entfernen(pfad)
    return lebendig


def aufraeumen():
    """Abgelaufenes entfernen: Zustand und Bericht beendeter Aufträge nach AUFHEBEN, die Datei eines Probelaufs nach
    DATEI_FRIST, unlesbare Zustände nach einer Stunde; ist die Sperre frei, dazu _aufraeumen_unter_sperre. Bei jedem
    Start, bei der Abfrage für die Katalogseite und im Tageslauf. Wirft nie."""
    try:
        ordner = _ordner()
        for name in os.listdir(ordner):
            kennung, _, endung = name.partition(".")
            if endung != "json" or not KENNUNG.fullmatch(kennung):
                continue
            z = _lesen(kennung)
            if z is None:
                try:
                    if time.time() - os.path.getmtime(os.path.join(ordner, name)) > 3600:
                        _entfernen(os.path.join(ordner, name))
                except OSError:
                    pass
                continue
            if z["zustand"] in OFFEN:
                continue
            if "von_id" in z or "von" in z:            # erste Fassung (30cf668): Name und users.id raus
                z.pop("von_id", None)
                z.pop("von", None)
                _atomar(os.path.join(ordner, name), z)
            if _sekunden_seit(z.get("beendet") or z["gestartet"]) > AUFHEBEN:
                for e in (".datei", ".abgelegt", ".bericht.json", ".json"):
                    _entfernen(_pfad(kennung, e))
            elif os.path.exists(_pfad(kennung, ".datei")) and not _uebernehmbar(z):
                _entfernen(_pfad(kennung, ".datei"))
        for name in os.listdir(ordner):
            kennung, _, endung = name.partition(".")
            if endung == "bericht.json" and KENNUNG.fullmatch(kennung) and not os.path.exists(
                    os.path.join(ordner, kennung + ".json")):
                _entfernen(os.path.join(ordner, name))
        sperre = _sperre_nehmen()
        if sperre:
            try:
                _aufraeumen_unter_sperre()
            finally:
                sperre.close()
    except Exception as exc:                      # noqa: BLE001 – Aufräumen darf nie eine Anfrage scheitern lassen
        log.warning("Katalogimport: Aufräumen gescheitert: %s", exc)
