"""Bestandsvideos aufbereiten.

Videos, die vor der Umwandlung beim Hochladen ins System kamen, liegen noch so, wie sie vom
Telefon kamen – meist .mov mit HEVC, das Chrome und Firefox nicht abspielen. Beim Start
prüft ein Hintergrundlauf jedes Video und wandelt, was nötig ist, mit demselben Verfahren wie
beim Hochladen. Gunicorn startet mehrere Arbeiter zugleich; eine Dateisperre sorgt dafür,
dass genau einer den Lauf übernimmt. Ohne ffmpeg wird nicht gewandelt – dann kann auch das
Hochladen nicht wandeln, und der Bestand bliebe ohnehin, wie er ist.

Derselbe Lauf räumt verwaiste Artikeldateien auf (siehe _wiki_waisen)."""
import fcntl
import json
import logging
import os
import threading
import time
from urllib.parse import quote

from . import db
from .images import FFMPEG, VIDEO_EXT, video_nachbereiten

log = logging.getLogger(__name__)

# Was der Lauf bisher getan hat – für die Nutzerverwaltung, damit man sieht, ob noch etwas im
# Gange ist. Gunicorn hat mehrere Arbeiter; welcher eine Anfrage beantwortet, ist Zufall. Der
# Stand liegt deshalb in einer Datei, die alle lesen, und nicht nur im Speicher des Läufers.
STAND = {"laeuft": False, "geprueft": 0, "gewandelt": 0, "fehler": 0, "fertig": False}
_SPERRE = None          # bleibt bis zum Prozessende offen – siehe _lauf


def stand(app):
    """Der zuletzt geschriebene Stand – aus der Datei, sonst aus dem Speicher."""
    try:
        with open(_standdatei(app), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return dict(STAND)


def _standdatei(app):
    return os.path.join(app.config["DATA_DIR"], "videopflege.json")


def _stand_schreiben(app):
    try:
        with open(_standdatei(app) + ".neu", "w", encoding="utf-8") as fh:
            json.dump(STAND, fh)
        os.replace(_standdatei(app) + ".neu", _standdatei(app))
    except OSError:
        pass


def starten(app):
    """Den Lauf im Hintergrund anstoßen. Kehrt sofort zurück. VIDEOPFLEGE=0 schaltet ihn ab –
    für Tests und Werkzeuge, die die Anwendung nur kurz laden, ohne Medien anfassen zu wollen."""
    if os.environ.get("VIDEOPFLEGE", "1") == "0" or app.config.get("TESTING"):
        STAND["fertig"] = True
        return
    threading.Thread(target=_lauf, args=(app,), name="videopflege", daemon=True).start()


def _lauf(app):
    global _SPERRE
    with app.app_context():
        # Die Sperre wird nicht mehr freigegeben: Sonst liefe der zweite Arbeiter, der eine
        # Sekunde später startet, den ganzen Bestand noch einmal ab, sobald der erste fertig
        # ist. Mit dem Prozess endet sie von selbst.
        _SPERRE = open(os.path.join(app.config["DATA_DIR"], "videopflege.lock"), "w")
        try:
            fcntl.flock(_SPERRE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            _SPERRE.close()
            _SPERRE = None
            return                                   # ein anderer Arbeiter ist schon dabei
        STAND["laeuft"] = True
        _stand_schreiben(app)
        try:
            if FFMPEG:                                   # ohne ffmpeg gibt es nichts zu wandeln
                _alben(app.config["MEDIA_DIR"], app)
                _wiki(app.config["MEDIA_DIR"], app)
            _wiki_waisen(app.config["MEDIA_DIR"])
            if STAND["gewandelt"] or STAND["fehler"]:
                log.info("Videopflege: %d geprüft, %d gewandelt, %d Fehler",
                         STAND["geprueft"], STAND["gewandelt"], STAND["fehler"])
        except Exception:
            log.exception("Videopflege abgebrochen")
        finally:
            STAND["laeuft"] = False
            STAND["fertig"] = True
            _stand_schreiben(app)


def _alben(media_dir, app):
    """Videos der Alben: der Dateiname steht in photos.file, Vorschaubilder hängen am Schlüssel
    davor und bleiben gültig."""
    for r in db.query("SELECT id, file FROM photos WHERE kind = 'video'"):
        pfad = os.path.join(media_dir, "orig", r["file"])
        if not os.path.isfile(pfad) or ".umwandlung." in r["file"]:
            continue
        STAND["geprueft"] += 1
        stand, neu, breite, hoehe = video_nachbereiten(pfad)
        if stand == "fehler":
            STAND["fehler"] += 1
        elif stand == "gewandelt":
            db.execute("UPDATE photos SET file = ?, width = COALESCE(?, width), height = COALESCE(?, height) "
                       "WHERE id = ?", (neu, breite, hoehe, r["id"]))
            STAND["gewandelt"] += 1
            _stand_schreiben(app)
            log.info("Video gewandelt: Album-Bild %d, %s → %s", r["id"], r["file"], neu)


def _wiki(media_dir, app):
    """Videos in Artikeln: Die Dateien liegen unter media/wiki (auch in Unterordnern aus
    Importen), verwiesen wird per Adresse im Text. Nach dem Wandeln heißt die Datei anders –
    Verweise in Seiten, Fassungen und Zuordnungen ziehen mit. Ein gerade offener Editor
    hält noch die alte Adresse; die Auslieferung führt sie zur gewandelten Datei
    (siehe media() in __init__)."""
    wurzel = os.path.join(media_dir, "wiki")
    if not os.path.isdir(wurzel):
        return
    for ordner, _, dateien in os.walk(wurzel):
        for name in dateien:
            if os.path.splitext(name)[1].lower() not in VIDEO_EXT or ".umwandlung." in name:
                continue
            pfad = os.path.join(ordner, name)
            alt = os.path.relpath(pfad, wurzel).replace(os.sep, "/")
            STAND["geprueft"] += 1
            stand, neu_name, _, _ = video_nachbereiten(pfad)
            if stand == "fehler":
                STAND["fehler"] += 1
                continue
            if stand != "gewandelt" or neu_name == name:
                continue
            neu = alt[: -len(name)] + neu_name
            with db.transaction():
                db.execute("UPDATE wiki_files SET file = ? WHERE file = ?", (neu, alt))
                db.execute("UPDATE OR REPLACE wiki_page_files SET file = ? WHERE file = ?", (neu, alt))
                # Auch die Beschreibungen im Prüfungsbereich können auf Artikeldateien zeigen.
                for tabelle, spalte in VERWEIS_SPALTEN:
                    db.execute(f"UPDATE {tabelle} SET {spalte} = replace({spalte}, ?, ?) WHERE instr({spalte}, ?) > 0",
                               (f"/media/wiki/{alt}", f"/media/wiki/{neu}", f"/media/wiki/{alt}"))
            STAND["gewandelt"] += 1
            _stand_schreiben(app)
            log.info("Video gewandelt: Artikeldatei %s → %s, Verweise nachgezogen", alt, neu)


# --- Verwaiste Artikeldateien ---------------------------------------------------------------

WAISEN_ALTER_SEK = 7 * 24 * 60 * 60     # so lange darf eine Datei ohne Verweis liegen bleiben


def _wiki_waisen(media_dir):
    """Artikeldateien ohne Verweis entfernen. Hochgeladen wird, bevor die Seite gespeichert ist;
    Drehen und Zuschneiden legen je Klick eine neue Datei an; endgültig gelöschte Seiten nehmen
    ihre Anhänge nicht mit. Ohne Aufräumen wüchse media/wiki nur – und ein einzelnes Mitglied
    könnte die Platte füllen, ohne dass je etwas davon auf einer Seite stünde.

    Entfernt wird, was seit einer Woche weder eine Seite (wiki_page_files), noch eine Fassung im
    Verlauf nennt. Die Woche schützt, was gerade erst hochgeladen und noch nicht gespeichert ist;
    länger hält auch ein Entwurf im Browser keinen Upload fest. Abgebrochene Umwandlungen
    (*.umwandlung.*) fallen gleich mit weg."""
    wurzel = os.path.join(media_dir, "wiki")
    if not os.path.isdir(wurzel):
        return 0
    grenze = time.time() - WAISEN_ALTER_SEK
    entfernt = 0
    for ordner, _, dateien in os.walk(wurzel):
        for name in dateien:
            pfad = os.path.join(ordner, name)
            try:
                if os.path.getmtime(pfad) > grenze:
                    continue
            except OSError:
                continue
            ref = os.path.relpath(pfad, wurzel).replace(os.sep, "/")
            if ".umwandlung." not in name and _wird_gebraucht(ref):
                continue
            try:
                os.remove(pfad)
            except OSError:
                continue
            db.execute("DELETE FROM wiki_files WHERE file = ?", (ref,))
            entfernt += 1
    if entfernt:
        log.info("Medienpflege: %d verwaiste Artikeldateien entfernt", entfernt)
    return entfernt


# Alle Spalten mit Markdown, das auf Artikeldateien zeigen kann – auch die Beschreibungen im
# Prüfungsbereich. Wer hier eine Spalte vergisst, dessen Dateien gelten als verwaist.
VERWEIS_SPALTEN = (("wiki_pages", "content"), ("wiki_revisions", "content"),
                   ("pruef_leistungen", "beschreibung_md"), ("pruef_katalog_leistungen", "beschreibung_md"))


def _wird_gebraucht(ref):
    """Nennt irgendeine Seite oder Fassung die Datei? Die Seitenzuordnung ist indiziert; der
    Verlauf wird mit instr durchsucht – einmal je Kandidat, nicht je Seite. Die Adresse kann im
    Text auch kodiert stehen (Umlaute, Leerzeichen aus Importen), deshalb beide Schreibweisen.
    Ein gewandeltes Video wird unter seiner alten Adresse weiter ausgeliefert (media(): .mov →
    .mp4); deshalb hält bei Videos auch ein Verweis mit einer anderen Videoendung die Datei."""
    basis, ext = os.path.splitext(ref)
    namen = {ref} | ({basis + e for e in VIDEO_EXT} if ext.lower() in VIDEO_EXT else set())
    if db.query(f"SELECT 1 FROM wiki_page_files WHERE file IN ({','.join('?' * len(namen))})", tuple(namen), one=True):
        return True
    marken = {"/media/wiki/" + n for n in namen} | {"/media/wiki/" + quote(n, safe="/") for n in namen}
    for tabelle, spalte in VERWEIS_SPALTEN:
        for marke in marken:
            if db.query(f"SELECT 1 FROM {tabelle} WHERE instr({spalte}, ?) > 0 LIMIT 1", (marke,), one=True):
                return True
    return False
