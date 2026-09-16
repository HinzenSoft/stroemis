"""Bildverarbeitung: EXIF-Geotags lesen, Thumbnails erzeugen, Dateien ablegen."""
import json
import logging
import os
import secrets
import shutil
import subprocess
from datetime import datetime

from PIL import Image, ImageOps

try:  # HEIC/HEIF von iPhones – optional
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass

class BildFehler(ValueError):
    """Fehler, dessen Text dem Nutzer gezeigt werden darf – im Unterschied zu allem, was Pillow
    oder das Dateisystem selbst werfen. Erbt von ValueError, damit vorhandene Aufrufer, die
    ValueError abfangen, unverändert weiterlaufen."""


ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm"}
# Anhänge, die unverändert abgelegt und im Artikel verlinkt werden (Handbücher, Listen, Tracks).
# Bewusst ohne ausführbare Formate.
AUDIO_EXT = {".mp3", ".m4a", ".ogg", ".oga", ".wav"}
DOC_EXT = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".csv",
           ".ppt", ".pptx", ".odp", ".txt", ".zip", ".gpx", ".kml", ".kmz"} | AUDIO_EXT
WIKI_EXT = ALLOWED_EXT | VIDEO_EXT | DOC_EXT | {".gif", ".svg"}
THUMB_SIZE = 256      # quadratischer Ausschnitt für Karte und Raster
AVATAR_SIZE = 256     # Profilbild: quadratisch, gezeigt wird es in 24 bis 30 px
# Ein Profilbild kommt vom Telefon oder aus einer Kamera; mehr als 8 MB hat keins davon. Die
# allgemeine Obergrenze für Uploads ist wegen der Filme riesig und taugt hier nicht als Bremse;
# size_guard in __init__.py weist alles Größere ab, bevor überhaupt etwas gepuffert wird.
AVATAR_MAX_BYTES = 8 * 1024 * 1024
# Und eine eigene Pixelgrenze: Herauskommen 256×256, ein 60-MP-Bild (die Grenze für Alben) wäre
# hier nur eine Einladung, für ein paar hundert Kilobyte ein halbes Gigabyte Arbeitsspeicher zu
# binden. 4096×4096 deckt jede Kamera ab, deren Bild jemand als Profilbild nimmt.
AVATAR_MAX_PIXEL = 4096 * 4096
WEB_MAX = 1800        # längste Kante der Web-Variante
# Ein 2,6-MB-JPEG mit 13000×13000 Pixeln belegt beim Drehen und Kopieren rund 1,4 GB – acht davon
# gleichzeitig und der Arbeiter ist tot. Über der Grenze wird gar nicht erst dekodiert. 60 MP
# reicht für jede Kamera, die ein Mitglied in die Hand nimmt.
MAX_PIXEL = 60_000_000


def _pixel_pruefen(img, name, grenze=None):
    grenze = grenze or MAX_PIXEL
    if img.width * img.height > grenze:
        raise BildFehler(f"„{name}“ hat {img.width}×{img.height} Pixel – das ist zu groß. "
                         f"Bitte auf höchstens {grenze // 1_000_000} Megapixel verkleinern.")

GPS_IFD = 0x8825
EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL = 0x9003
TAG_DATETIME = 0x0132


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _rm(*paths):
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


def _dms_to_deg(dms, ref):
    try:
        if not dms or len(dms) < 3:
            return None
    except TypeError:  # Pillow liefert statt des Tripels manchmal eine nackte IFDRational
        return None
    d, m, s = (_to_float(x) for x in dms[:3])
    if d is None or m is None or s is None:
        return None
    deg = d + m / 60.0 + s / 3600.0
    if ref in ("S", "W"):
        deg = -deg
    return deg


def read_exif(img):
    """Liefert dict(lat, lon, altitude, taken_at) – Werte sind None, wenn nicht vorhanden."""
    out = {"lat": None, "lon": None, "altitude": None, "taken_at": None}
    try:
        exif = img.getexif()
    except Exception:
        return out
    if not exif:
        return out
    try:  # kaputte EXIF-Daten dürfen ein gültiges Bild nie zu Fall bringen
        gps = exif.get_ifd(GPS_IFD)
        if gps:
            lat = _dms_to_deg(gps.get(2), gps.get(1))
            lon = _dms_to_deg(gps.get(4), gps.get(3))
            if lat is not None and lon is not None and (lat, lon) != (0.0, 0.0) \
                    and -90 <= lat <= 90 and -180 <= lon <= 180:
                out["lat"], out["lon"] = lat, lon
            alt = _to_float(gps.get(6))
            if alt is not None:
                ref = gps.get(5)
                if ref in (1, b"\x01"):
                    alt = -alt
                out["altitude"] = alt
    except Exception:
        out["lat"] = out["lon"] = out["altitude"] = None
    try:
        sub = exif.get_ifd(EXIF_IFD)
        raw = sub.get(TAG_DATETIME_ORIGINAL) or exif.get(TAG_DATETIME)
        if raw:
            out["taken_at"] = datetime.strptime(str(raw)[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        out["taken_at"] = None
    return out


def media_paths(media_dir):
    paths = {k: os.path.join(media_dir, k) for k in ("orig", "web", "thumb")}
    for p in paths.values():
        os.makedirs(p, exist_ok=True)
    return paths


# --- Videos ------------------------------------------------------------------
# Aufnahmen vom iPhone kommen als .mov mit HEVC. Safari spielt das, Chrome und Firefox nicht –
# dort blieb der Player stumm bei 0:00 stehen. Deshalb wird beim Hochladen alles, was nicht
# jeder Browser kann, nach H.264/AAC in ein MP4 gewandelt. Fehlt ffmpeg (etwa bei einer
# Entwicklungsumgebung ohne Container), bleibt es beim Original – dann ist die Anzeige wie bisher.
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
# Was jeder gängige Browser abspielt. Alles andere wird gewandelt.
WEB_VIDEO = {"h264", "vp8", "vp9", "av1"}
WEB_AUDIO = {"aac", "mp3", "opus", "vorbis", None}
VIDEO_MAX_KANTE = 1920                 # größere Aufnahmen werden verkleinert
VIDEO_FRIST_SEK = 30 * 60              # eine hängende Umwandlung darf keinen Arbeiter festhalten


def _ffprobe(pfad):
    """Spuren einer Videodatei lesen. Liefert (videocodec, audiocodec, breite, höhe)."""
    if not FFPROBE:
        return None, None, None, None
    try:
        roh = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", pfad],
            capture_output=True, timeout=60, check=True).stdout
        spuren = json.loads(roh).get("streams", [])
    except (subprocess.SubprocessError, ValueError, OSError):
        return None, None, None, None
    video = next((s for s in spuren if s.get("codec_type") == "video"), None)
    ton = next((s for s in spuren if s.get("codec_type") == "audio"), None)
    return ((video or {}).get("codec_name"), (ton or {}).get("codec_name"),
            (video or {}).get("width"), (video or {}).get("height"))


def _video_umwandeln(quelle, ziel):
    """Nach H.264/AAC wandeln. "faststart" schiebt die Sprungtabelle nach vorn, sonst lädt der
    Browser erst die ganze Datei, bevor er das erste Bild zeigt."""
    if not FFMPEG:
        return False
    befehl = [FFMPEG, "-y", "-i", quelle,
              "-map", "0:v:0", "-map", "0:a:0?",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
              "-vf", f"scale='min({VIDEO_MAX_KANTE},iw)':-2",
              "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", ziel]
    try:
        subprocess.run(befehl, capture_output=True, timeout=VIDEO_FRIST_SEK, check=True)
    except (subprocess.SubprocessError, OSError):
        _rm(ziel)
        return False
    return os.path.exists(ziel) and os.path.getsize(ziel) > 0


def _video_pruefen(pfad):
    """Muss das Video gewandelt werden, und welche Maße hat es? Ohne ffmpeg wird nie gewandelt –
    dann bleibt die Anzeige wie bisher (Safari spielt HEVC, die anderen nicht)."""
    ext = os.path.splitext(pfad)[1].lower()
    vcodec, acodec, breite, hoehe = _ffprobe(pfad)
    wandeln = bool(FFMPEG and vcodec and (vcodec not in WEB_VIDEO or acodec not in WEB_AUDIO
                                          or ext not in (".mp4", ".m4v", ".webm")))
    return wandeln, breite, hoehe


def video_nachbereiten(pfad):
    """Ein Video an Ort und Stelle web-tauglich machen – beim Hochladen wie für den Bestand.

    Liefert (stand, dateiname, breite, hoehe). stand ist "bleibt" (spielt überall, nichts zu
    tun), "gewandelt" (die Datei heißt jetzt <basis>.mp4, das Original ist weg) oder "fehler".
    Zwei Fassungen aufzuheben wäre bei Aufnahmen in Gigabyte-Größe teuer, und die gewandelte
    lässt sich überall abspielen – auch beim Herunterladen."""
    wandeln, breite, hoehe = _video_pruefen(pfad)
    name = os.path.basename(pfad)
    if not wandeln:
        return "bleibt", name, breite, hoehe
    basis = os.path.splitext(pfad)[0]
    ziel = basis + ".umwandlung.mp4"
    if not _video_umwandeln(pfad, ziel):
        return "fehler", name, breite, hoehe
    neu = basis + ".mp4"
    if os.path.abspath(neu) != os.path.abspath(pfad):
        _rm(pfad)
    os.replace(ziel, neu)
    _, breite, hoehe = _video_pruefen(neu)
    return "gewandelt", os.path.basename(neu), breite, hoehe


def _video_standbild(quelle, ziel):
    """Ein Bild aus der Mitte der ersten Sekunden als Vorschau ziehen."""
    if not FFMPEG:
        return False
    try:
        subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", quelle, "-frames:v", "1", "-q:v", "3", ziel],
                       capture_output=True, timeout=120, check=True)
    except (subprocess.SubprocessError, OSError):
        _rm(ziel)
        return False
    return os.path.exists(ziel) and os.path.getsize(ziel) > 0


def _placeholder_poster(path_web, path_thumb):
    """Grauer Platzhalter mit Play-Dreieck, wenn der Browser kein Vorschaubild geliefert hat."""
    from PIL import ImageDraw
    img = Image.new("RGB", (640, 480), (87, 87, 86))
    d = ImageDraw.Draw(img)
    d.polygon([(260, 160), (260, 320), (400, 240)], fill=(255, 255, 255))
    img.save(path_web, "JPEG", quality=80)
    ImageOps.fit(img, (THUMB_SIZE, THUMB_SIZE)).save(path_thumb, "JPEG", quality=80)


def store_upload(file_storage, media_dir, poster=None):
    """Speichert Original, erzeugt Web- und Thumb-Variante. Liefert Metadaten oder wirft ValueError.
    Videos werden unverändert abgelegt; als Vorschau dient das vom Browser mitgeschickte Standbild (poster)."""
    name = file_storage.filename or "bild"
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT and ext not in VIDEO_EXT:
        raise ValueError(f"Dateityp {ext or '(ohne Endung)'} wird nicht unterstützt.")
    paths = media_paths(media_dir)
    key = secrets.token_hex(8)
    orig_name = key + ext
    orig_path = os.path.join(paths["orig"], orig_name)
    web_path = os.path.join(paths["web"], key + ".jpg")
    thumb_path = os.path.join(paths["thumb"], key + ".jpg")

    def _cleanup():
        _rm(orig_path, web_path, thumb_path)

    try:  # erst ab hier räumt _cleanup auf, deshalb muss auch das Original hier hinein
        file_storage.save(orig_path)
    except Exception as exc:
        _cleanup()
        raise ValueError(f"Die Datei „{name}“ konnte nicht gespeichert werden ({exc}).")

    if ext in VIDEO_EXT:
        meta = {"lat": None, "lon": None, "altitude": None, "taken_at": None}
        width = height = None
        # Was nicht jeder Browser abspielt, wird gewandelt; das Ergebnis ersetzt das Original.
        stand, orig_name, vbreite, vhoehe = video_nachbereiten(orig_path)
        orig_path = os.path.join(paths["orig"], orig_name)
        if vbreite and vhoehe:
            width, height = vbreite, vhoehe
        # Ohne Standbild vom Browser (der es bei HEVC gar nicht erzeugen kann) zieht ffmpeg eines.
        if poster is None and FFMPEG:
            aus_film = os.path.join(paths["web"], key + ".ffmpeg.jpg")
            if _video_standbild(orig_path, aus_film):
                try:
                    with Image.open(aus_film) as bild:
                        if bild.mode not in ("RGB", "L"):
                            bild = bild.convert("RGB")
                        netz = bild.copy()
                        netz.thumbnail((WEB_MAX, WEB_MAX))
                        netz.save(web_path, "JPEG", quality=85, optimize=True)
                        ImageOps.fit(bild, (THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS).save(
                            thumb_path, "JPEG", quality=82, optimize=True)
                    meta.update({"file": orig_name, "width": width, "height": height,
                                 "original_name": name, "kind": "video"})
                    return meta
                except Exception:
                    pass
                finally:
                    _rm(aus_film)
        try:
            if poster is not None:
                with Image.open(poster.stream) as img:
                    img = ImageOps.exif_transpose(img)
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    width, height = width or img.size[0], height or img.size[1]
                    web = img.copy()
                    web.thumbnail((WEB_MAX, WEB_MAX))
                    web.save(web_path, "JPEG", quality=85, optimize=True)
                    ImageOps.fit(img, (THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS).save(
                        thumb_path, "JPEG", quality=82, optimize=True)
            else:
                _placeholder_poster(web_path, thumb_path)
        except Exception:
            try:
                _placeholder_poster(web_path, thumb_path)
            except Exception as exc:
                _cleanup()
                raise ValueError(f"Für „{name}“ ließ sich keine Vorschau anlegen ({exc}).")
        meta.update({"file": orig_name, "width": width, "height": height, "original_name": name,
                     "kind": "video"})
        return meta

    try:
        with Image.open(orig_path) as img:
            _pixel_pruefen(img, name)
            meta = read_exif(img)
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            web = img.copy()
            web.thumbnail((WEB_MAX, WEB_MAX))
            web.save(web_path, "JPEG", quality=85, optimize=True)
            thumb = ImageOps.fit(img, (THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            thumb.save(thumb_path, "JPEG", quality=82, optimize=True)
    except ValueError:
        _cleanup()
        raise
    except Exception:
        # Pillows Meldung nennt den Pfad auf dem Server – der geht niemanden etwas an.
        _cleanup()
        raise ValueError(f"Die Datei „{name}“ konnte nicht als Bild gelesen werden.")

    meta.update({"file": orig_name, "width": width, "height": height, "original_name": name,
                 "kind": "image"})
    return meta


def store_avatar(file_storage, media_dir):
    """Profilbild ablegen: quadratisch aus der Mitte, AVATAR_SIZE Kantenlänge, JPEG.

    Ein Profilbild wird klein gezeigt – ein Rundbild von 24 px. Alles, was darüber hinausgeht,
    kostet nur Platz und Ladezeit, deshalb wird es beim Hochladen fest auf Maß gebracht
    statt in Originalgröße gespeichert. Liefert den Dateinamen; ein etwaiger Vorgänger wird vom
    Aufrufer entfernt, nachdem der neue Name in der Datenbank steht."""
    name = file_storage.filename or "bild"
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT and ext not in (".gif",):
        raise BildFehler(f"Dateityp {ext or '(ohne Endung)'} eignet sich nicht als Profilbild.")
    file_storage.stream.seek(0, os.SEEK_END)
    groesse = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if groesse > AVATAR_MAX_BYTES:
        raise BildFehler(f"„{name}“ ist mit {groesse // (1024 * 1024)} MB zu groß – "
                         f"ein Profilbild darf höchstens {AVATAR_MAX_BYTES // (1024 * 1024)} MB haben.")
    d = os.path.join(media_dir, "avatar")
    os.makedirs(d, exist_ok=True)
    key = secrets.token_hex(8)
    ziel = os.path.join(d, key + ".jpg")
    # Zwei Schritte, zwei Fehlerbilder: Was beim Lesen schiefgeht, ist ein Fehler der Datei und
    # gehört dem Nutzer gesagt. Was beim Schreiben schiefgeht (volle Platte, fehlende Rechte),
    # ist ein Fehler des Servers – dafür taugt „das ist kein Bild“ nicht als Auskunft.
    try:
        with Image.open(file_storage.stream) as img:
            _pixel_pruefen(img, name, AVATAR_MAX_PIXEL)
            # Bei JPEG verkleinert draft() schon beim Dekodieren – aus 4096 Pixeln werden 512,
            # ohne dass das volle Bild je im Speicher steht. Das Ergebnis ist ohnehin 256 Pixel;
            # die doppelte Kantenlänge lässt genug Spielraum für den Zuschnitt.
            img.draft("RGB", (AVATAR_SIZE * 2, AVATAR_SIZE * 2))
            bild = ImageOps.exif_transpose(img)      # Hochformat vom Telefon steht sonst quer
            bild = ImageOps.fit(bild, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
            if bild.mode in ("RGBA", "LA", "P"):
                # JPEG kennt keine Durchsichtigkeit. Ohne Untergrund würde sie schwarz – ein
                # freigestelltes PNG bekäme im runden Rahmen einen schwarzen Rand. Weiß passt
                # zur Fläche, auf der das Bild später steht.
                bild = bild.convert("RGBA")
                grund = Image.new("RGB", bild.size, (255, 255, 255))
                grund.paste(bild, mask=bild.split()[-1])
                bild = grund
            elif bild.mode != "RGB":
                bild = bild.convert("RGB")
            bild.load()                              # vollständig im Speicher, bevor img schließt
    except BildFehler:
        raise
    except Exception:
        raise BildFehler(f"Die Datei „{name}“ konnte nicht als Bild gelesen werden.")
    try:
        # Ohne exif= schreibt Pillow keine Aufnahmedaten mit: Ein Profilbild soll nicht den
        # Wohnort verraten, nur weil das Telefon den Aufnahmeort hineingeschrieben hat.
        bild.save(ziel, "JPEG", quality=85, optimize=True)
    except OSError as exc:
        _rm(ziel)
        logging.getLogger(__name__).warning("Profilbild konnte nicht abgelegt werden: %s", exc)
        raise BildFehler(f"„{name}“ konnte nicht gespeichert werden. Bitte später erneut versuchen.")
    return os.path.basename(ziel)


def delete_avatar(media_dir, datei):
    """Ein abgelegtes Profilbild entfernen. Der Name kommt aus der Datenbank und darf
    keinen Pfad enthalten – sonst zeigte er aus dem Verzeichnis heraus."""
    if not datei or "/" in datei or "\\" in datei or ".." in datei:
        return
    _rm(os.path.join(media_dir, "avatar", datei))


def store_wiki_file(file_storage, media_dir):
    """Bild, Video oder Anhang für Artikel. Bilder werden als Web-Variante gespeichert,
    alles andere unverändert. Liefert (Dateiname, 'image'|'video'|'file')."""
    name = file_storage.filename or "datei"
    ext = os.path.splitext(name)[1].lower()
    if not ext and (file_storage.mimetype or "").startswith("image/"):
        ext = "." + file_storage.mimetype.split("/")[1].replace("jpeg", "jpg")
    if ext not in WIKI_EXT:
        raise ValueError(f"Dateityp {ext or '(ohne Endung)'} wird nicht unterstützt.")
    d = os.path.join(media_dir, "wiki")
    os.makedirs(d, exist_ok=True)
    key = secrets.token_hex(8)
    if ext in VIDEO_EXT or ext in DOC_EXT or ext in (".gif", ".svg"):
        out = key + ext
        try:  # ein abgebrochener Schreibvorgang darf keine Waise in media/wiki hinterlassen
            file_storage.save(os.path.join(d, out))
        except Exception:
            _rm(os.path.join(d, out))
            raise
        if ext in VIDEO_EXT:
            # Wie bei den Alben: Was nicht jeder Browser spielt, wird gewandelt. Der Artikel
            # bekommt gleich die Adresse der gewandelten Datei.
            _, out, _, _ = video_nachbereiten(os.path.join(d, out))
        return out, ("video" if ext in VIDEO_EXT else "file" if ext in DOC_EXT else "image")
    with Image.open(file_storage.stream) as img:
        _pixel_pruefen(img, name)
        out = _bild_ablegen(ImageOps.exif_transpose(img), d, key)
    return out, "image"


# --- Zuschneiden und Drehen -------------------------------------------------------------

# Beides geht nur bei Rasterbildern, die Pillow auch wieder schreiben kann. GIF und SVG
# bleiben außen vor: Beim GIF ginge die Bewegung verloren, das SVG ist gar kein Raster.
CROP_EXT = {".jpg", ".jpeg", ".png", ".webp"}
# Vierteldrehungen. Gezählt wird im Uhrzeigersinn, so wie der Knopf im Menü heißt; Pillows
# Transpose-Namen laufen andersherum, deshalb die Zuordnung hier an einer Stelle.
DREHUNGEN = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
             270: Image.Transpose.ROTATE_90}


def _wiki_pfad(media_dir, name):
    """Pfad einer Artikeldatei – und die Prüfung, dass er auch wirklich unter media/wiki liegt.
    Importierte Seiten legen ihre Bilder in Unterordnern ab, ein Name darf also Striche
    enthalten; hinausführen darf er nicht."""
    wurzel = os.path.realpath(os.path.join(media_dir, "wiki"))
    pfad = os.path.realpath(os.path.join(wurzel, name.lstrip("/")))
    if pfad != wurzel and not pfad.startswith(wurzel + os.sep):
        raise ValueError("Ungültiger Dateiname.")
    return pfad


def _bild_ablegen(img, verzeichnis, key):
    """Ein Bild als Web-Variante speichern – JPEG, oder PNG, wenn es durchsichtig ist.
    Liefert den Dateinamen."""
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if has_alpha:
        img = img.convert("RGBA")
        out, fmt, opts = key + ".png", "PNG", {"optimize": True}
    else:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out, fmt, opts = key + ".jpg", "JPEG", {"quality": 85, "optimize": True}
    img.thumbnail((WEB_MAX, WEB_MAX))
    ziel = os.path.join(verzeichnis, out)
    try:
        img.save(ziel, fmt, **opts)
    except Exception:
        _rm(ziel)
        raise
    return out


def crop_wiki_image(media_dir, name, kasten):
    """Ausschnitt eines Artikelbildes als NEUE Datei; das Ausgangsbild bleibt liegen.
    So lässt sich ein Zuschnitt rückgängig machen, indem der Text wieder auf das alte Bild
    zeigt – und ein Bild, das an zwei Stellen steht, verliert nicht an beiden seine Ränder.
    Der Kasten kommt als vier Anteile (links, oben, Breite, Höhe) zwischen 0 und 1: Damit ist
    der Aufruf unabhängig davon, wie groß das Bild im Editor gerade dargestellt war."""
    quelle = _wiki_pfad(media_dir, name)
    if os.path.splitext(quelle)[1].lower() not in CROP_EXT:
        raise ValueError("Dieses Format lässt sich nicht zuschneiden.")
    if not os.path.isfile(quelle):
        raise ValueError("Das Bild ist nicht mehr da.")
    try:
        links, oben, breite, hoehe = (float(v) for v in kasten)
    except (TypeError, ValueError):
        raise ValueError("Der Ausschnitt ist unvollständig.")
    if not (0 <= links and 0 <= oben and breite > 0 and hoehe > 0
            and links + breite <= 1.001 and oben + hoehe <= 1.001):
        raise ValueError("Der Ausschnitt liegt außerhalb des Bildes.")
    d = os.path.join(media_dir, "wiki")
    os.makedirs(d, exist_ok=True)
    with Image.open(quelle) as img:
        img = ImageOps.exif_transpose(img)
        b, h = img.size
        rand = (round(links * b), round(oben * h),
                min(b, round((links + breite) * b)), min(h, round((oben + hoehe) * h)))
        if rand[2] - rand[0] < 16 or rand[3] - rand[1] < 16:
            raise ValueError("Der Ausschnitt ist zu klein.")
        return _bild_ablegen(img.crop(rand), d, secrets.token_hex(8))


def rotate_wiki_image(media_dir, name, grad):
    """Ein Artikelbild um eine Vierteldrehung im Uhrzeigersinn kippen – als NEUE Datei, aus
    demselben Grund wie beim Zuschneiden: Ein Bild, das an zwei Stellen steht, soll sich nicht
    an beiden mitdrehen, und ein versehentlicher Klick bleibt mit Strg+Z zurücknehmbar.
    Gedreht wird in Vierteln (90, 180, 270); alles andere führte zu schrägen Rändern."""
    quelle = _wiki_pfad(media_dir, name)
    if os.path.splitext(quelle)[1].lower() not in CROP_EXT:
        raise ValueError("Dieses Format lässt sich nicht drehen.")
    if not os.path.isfile(quelle):
        raise ValueError("Das Bild ist nicht mehr da.")
    try:
        schritt = DREHUNGEN[int(grad)]
    except (TypeError, ValueError, KeyError):
        raise ValueError("Gedreht wird in Vierteln: 90, 180 oder 270 Grad.")
    d = os.path.join(media_dir, "wiki")
    os.makedirs(d, exist_ok=True)
    with Image.open(quelle) as img:
        _pixel_pruefen(img, name)
        # exif_transpose zuerst: Sonst drehte die Vierteldrehung ein Bild, das der Browser
        # wegen seiner Aufnahmerichtung ohnehin schon gekippt zeigt, um eine Vierteldrehung
        # zu viel. Nach dem Ablegen steht die Richtung fest im Bild, nicht mehr im EXIF.
        return _bild_ablegen(ImageOps.exif_transpose(img).transpose(schritt), d, secrets.token_hex(8))


def delete_photo_files(media_dir, file):
    key = os.path.splitext(file)[0]
    _rm(*(os.path.join(media_dir, sub, fn)
          for sub, fn in (("orig", file), ("web", key + ".jpg"), ("thumb", key + ".jpg"))))
