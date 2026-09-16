"""Bestandsvideos aufbereiten.

Videos, die vor der Umwandlung beim Hochladen ins System kamen, liegen noch so, wie sie vom
Telefon kamen – meist .mov mit HEVC, das Chrome und Firefox nicht abspielen. Beim Start
prüft ein Hintergrundlauf jedes Video und wandelt, was nötig ist, mit demselben Verfahren wie
beim Hochladen. Gunicorn startet mehrere Arbeiter zugleich; eine Dateisperre sorgt dafür,
dass genau einer den Lauf übernimmt. Ohne ffmpeg passiert nichts – dann kann auch das
Hochladen nicht wandeln, und der Bestand bliebe ohnehin, wie er ist."""
import fcntl
import json
import logging
import os
import threading

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
    if not FFMPEG or os.environ.get("VIDEOPFLEGE", "1") == "0" or app.config.get("TESTING"):
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
            _alben(app.config["MEDIA_DIR"], app)
            _wiki(app.config["MEDIA_DIR"], app)
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
                for tabelle in ("wiki_pages", "wiki_revisions"):
                    db.execute(f"UPDATE {tabelle} SET content = replace(content, ?, ?) WHERE instr(content, ?) > 0",
                               (f"/media/wiki/{alt}", f"/media/wiki/{neu}", f"/media/wiki/{alt}"))
            STAND["gewandelt"] += 1
            _stand_schreiben(app)
            log.info("Video gewandelt: Artikeldatei %s → %s, Verweise nachgezogen", alt, neu)
