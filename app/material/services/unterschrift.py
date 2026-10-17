"""Unterschriften: die eigene im Profil und die Unterschriftsfelder eines Prüfformulars.

Ein Prüfer (und wer aussondert) hinterlegt seine Unterschrift einmal im Profil, gezeichnet mit dem
Signatur-Pad (signature_pad.js). Beim Festschreiben wird eine Kopie in die Prüfung übernommen und ins
Protokoll gesetzt – zusammen mit Anmeldung, Zeitpunkt und Prüfsumme. Ändert er sie später, bleiben alte
Protokolle, wie sie sind.

Angenommen wird nur ein PNG als data:-URL, wie es das Signatur-Pad liefert. Der Server liest es mit
Pillow, verlangt sichtbare Striche, schneidet den leeren Rand ab, verkleinert es bei Bedarf und speichert
ein frisch geschriebenes PNG – nie die Bytes, die der Browser geschickt hat."""
import base64
import binascii
import hashlib
import io

from PIL import Image

from ... import db
from . import Abgelehnt, journal

VORSATZ = "data:image/png;base64,"
MAX_ZEICHEN = 1_000_000             # data:-URL (gut 700 KB PNG) – ein Signatur-Pad liefert ein Vielfaches weniger
MAX_SEITE = 3000                    # Pixel je Kante beim Lesen
MAX_PIXEL = 4_000_000               # Fläche: ein Signatur-Pad liefert selbst bei Pixeldichte 3 rund 2 000 × 700
MIN_TINTE = 40                      # so viele deckende Pixel braucht eine Unterschrift mindestens
ZIEL_BREITE, ZIEL_HOEHE = 900, 360  # größer wird nichts gespeichert
RAND = 8


def _tinte(bild):
    """Deckkraft je Pixel (L-Bild): aus dem Alphakanal, oder – bei deckendem Hintergrund – aus der
    Helligkeit (dunkel = Tinte)."""
    rgba = bild.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 255:
        return rgba, alpha
    hell = rgba.convert("L")
    deckung = hell.point(lambda v: 0 if v > 225 else 255 - v)
    rgba.putalpha(deckung)
    return rgba, deckung


def lesen(wert, name="Unterschrift"):
    """data:-URL → normalisiertes PNG (bytes). Abgelehnt mit Klartext, wenn es keine brauchbare Unterschrift ist."""
    if not isinstance(wert, str) or not wert.startswith(VORSATZ):
        raise Abgelehnt(f"„{name}“ muss ein PNG-Bild vom Signatur-Pad sein.")
    if len(wert) > MAX_ZEICHEN:
        raise Abgelehnt(f"„{name}“ ist zu groß.")
    try:
        roh = base64.b64decode(wert[len(VORSATZ):], validate=True)
    except (binascii.Error, ValueError):
        raise Abgelehnt(f"„{name}“ ist kein lesbares Bild.")
    if not roh.startswith(b"\x89PNG\r\n\x1a\n"):
        raise Abgelehnt(f"„{name}“ muss ein PNG-Bild sein.")
    try:
        with Image.open(io.BytesIO(roh)) as bild:
            if (bild.format != "PNG" or bild.width > MAX_SEITE or bild.height > MAX_SEITE
                    or bild.width * bild.height > MAX_PIXEL):
                raise Abgelehnt(f"„{name}“ ist kein brauchbares Bild.")
            bild.load()
            rgba, deckung = _tinte(bild)
    except Abgelehnt:
        raise
    except Exception:
        raise Abgelehnt(f"„{name}“ ist kein lesbares Bild.")
    maske = deckung.point(lambda v: 255 if v > 24 else 0)
    kasten = maske.getbbox()
    if not kasten or maske.histogram()[255] < MIN_TINTE:
        raise Abgelehnt(f"„{name}“ ist leer – bitte mit Finger, Stift oder Maus unterschreiben.")
    x0, y0, x1, y1 = kasten
    rgba = rgba.crop((max(0, x0 - RAND), max(0, y0 - RAND), min(rgba.width, x1 + RAND), min(rgba.height, y1 + RAND)))
    if rgba.width > ZIEL_BREITE or rgba.height > ZIEL_HOEHE:
        rgba.thumbnail((ZIEL_BREITE, ZIEL_HOEHE), Image.Resampling.LANCZOS)
    puffer = io.BytesIO()
    rgba.save(puffer, "PNG", optimize=True)
    return puffer.getvalue()


def daten_uri(png):
    return VORSATZ + base64.b64encode(png).decode("ascii") if png else None


def _kurz(png):
    return hashlib.sha256(png).hexdigest()[:16] if png else None


def setzen(user, wert):
    """Die eigene Unterschrift im Profil hinterlegen oder ersetzen. Liefert die data:-URL des gespeicherten Bilds."""
    png = lesen(wert)
    with db.transaction(sofort=True):
        alt = db.query("SELECT signature_png FROM users WHERE id = ?", (user["id"],), one=True)
        db.execute("UPDATE users SET signature_png = ? WHERE id = ?", (png, user["id"]))
        journal.eintragen("user", user["id"], "unterschrift", {"unterschrift": _kurz(alt and alt["signature_png"])},
                          {"unterschrift": _kurz(png)})
    return daten_uri(png)


def entfernen(user):
    with db.transaction(sofort=True):
        alt = db.query("SELECT signature_png FROM users WHERE id = ?", (user["id"],), one=True)
        if not alt or not alt["signature_png"]:
            return
        db.execute("UPDATE users SET signature_png = NULL WHERE id = ?", (user["id"],))
        journal.eintragen("user", user["id"], "unterschrift", {"unterschrift": _kurz(alt["signature_png"])},
                          {"unterschrift": None})


def von(user_id):
    r = db.query("SELECT signature_png FROM users WHERE id = ?", (user_id,), one=True)
    return r["signature_png"] if r and r["signature_png"] else None
