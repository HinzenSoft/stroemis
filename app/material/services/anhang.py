"""Anhänge einer Prüfung: externes Prüfformular, Prüfbericht, Foto, Sonstiges – immer als ein PDF.

Was der Prüfer anhängt, landet als eine PDF-Datei unter media/material/anhang: ein hochgeladenes PDF
unverändert, ein Scan mit der Handykamera (mehrere Fotos, eins je Seite) oder eine Mischung aus Fotos
und PDFs zusammengefasst in der gewählten Reihenfolge. So hat jeder Anhang eine Prüfsumme über genau
die abgelegte Datei, eine Seitenzahl, und Lieferung 3 kann ihn hinten an das Protokoll hängen.

Fotos werden gedreht wie aufgenommen (EXIF), auf höchstens DIN A4 bei 300 dpi verkleinert und als
JPEG in die Seite gelegt; HEIC vom iPhone geht über pillow-heif wie überall im Bestand."""
import hashlib
import io
import os
import secrets

from PIL import Image, ImageOps

from . import Abgelehnt

MAX_BYTES = 60 * 1024 * 1024        # eine Anfrage, alle Dateien zusammen
MAX_DATEIEN = 30
MAX_SEITEN = 200
# Ein Scan braucht keine 60 Megapixel wie ein Albumfoto: 50 MP deckt jede Telefonkamera, und ein großes PNG
# bindet beim Dekodieren sonst Hunderte Megabyte.
MAX_PIXEL_SCAN = 50_000_000
# DIN A4 bei 300 dpi: Ein Telefonfoto (4032 × 3024) wird damit eine Seite in Papiergröße.
A4_KURZ, A4_LANG, DPI = 2480, 3508, 300


def anhang_dir(medien_dir):
    d = os.path.join(medien_dir, "anhang")
    os.makedirs(d, exist_ok=True)
    return d


def _ist_pdf(kopf):
    return kopf.startswith(b"%PDF-")


def _bild_als_pdf(daten, name):
    """Ein Foto als PDF-Seite (bytes)."""
    try:
        with Image.open(io.BytesIO(daten)) as roh:
            if roh.width * roh.height > MAX_PIXEL_SCAN:
                raise Abgelehnt(f"„{name}“ hat zu viele Pixel ({roh.width} × {roh.height}).")
            # JPEG gleich verkleinert dekodieren (DCT-Skalierung) – schnell und sparsam; die Seite wird ohnehin
            # höchstens A4 bei 300 dpi.
            roh.draft("RGB", (A4_KURZ, A4_KURZ))
            bild = ImageOps.exif_transpose(roh)
            if bild.mode in ("RGBA", "LA", "P"):
                bild = bild.convert("RGBA")
                grund = Image.new("RGB", bild.size, (255, 255, 255))
                grund.paste(bild, mask=bild.split()[-1])
                bild = grund
            elif bild.mode not in ("RGB", "L"):
                bild = bild.convert("RGB")
            kurz, lang = sorted(bild.size)
            faktor = min(1.0, A4_KURZ / kurz, A4_LANG / lang)
            if faktor < 1.0:
                bild = bild.resize((max(1, round(bild.width * faktor)), max(1, round(bild.height * faktor))),
                                   Image.Resampling.LANCZOS)
            puffer = io.BytesIO()
            bild.save(puffer, "PDF", resolution=DPI, quality=85)
            return puffer.getvalue()
    except Abgelehnt:
        raise
    except Exception:
        raise Abgelehnt(f"„{name}“ ist weder ein PDF noch ein lesbares Foto (JPEG, PNG, WebP, HEIC).")


def _pdf_lesen(daten, name):
    from pypdf import PdfReader
    try:
        leser = PdfReader(io.BytesIO(daten))
        if leser.is_encrypted and not leser.decrypt(""):
            raise Abgelehnt(f"„{name}“ ist verschlüsselt – bitte ohne Kennwort speichern.")
        seiten = len(leser.pages)
    except Abgelehnt:
        raise
    except Exception:
        raise Abgelehnt(f"„{name}“ ist kein lesbares PDF.")
    if not seiten:
        raise Abgelehnt(f"„{name}“ hat keine Seite.")
    return leser, seiten


def zusammenfassen(dateien):
    """Liste von (name, bytes) → (pdf_bytes, seitenzahl). Ein einzelnes PDF bleibt Byte für Byte, wie es
    ist; alles andere wird in der gegebenen Reihenfolge zu einem PDF."""
    if not dateien:
        raise Abgelehnt("Es wurde keine Datei mitgeschickt.")
    if len(dateien) > MAX_DATEIEN:
        raise Abgelehnt(f"Höchstens {MAX_DATEIEN} Dateien auf einmal.")
    from pypdf import PdfWriter
    schreiber = PdfWriter()
    seiten = 0
    for name, daten in dateien:
        if _ist_pdf(daten[:5]):
            leser, n = _pdf_lesen(daten, name)
        else:
            leser, n = _pdf_lesen(_bild_als_pdf(daten, name), name)
        seiten += n
        if seiten > MAX_SEITEN:                 # vor dem Anfügen: das kostet bei vielen Seiten am meisten
            raise Abgelehnt(f"Höchstens {MAX_SEITEN} Seiten je Anhang.")
        # Auch ein einzelnes PDF muss sich anfügen lassen – Lieferung 3 hängt es hinten an das Protokoll.
        try:
            schreiber.append(leser)
        except Exception:
            raise Abgelehnt(f"„{name}“ ließ sich nicht verarbeiten – bitte als PDF neu speichern oder fotografieren.")
    if len(dateien) == 1 and _ist_pdf(dateien[0][1][:5]):
        return dateien[0][1], seiten            # ein einzelnes PDF bleibt Byte für Byte, wie es ist
    puffer = io.BytesIO()
    schreiber.write(puffer)
    return puffer.getvalue(), len(schreiber.pages)


def ablegen(medien_dir, pdf):
    """PDF ablegen; liefert (Dateiname, SHA-256). Der Name ist zufällig – er verrät nichts und ist nicht
    zu erraten."""
    name = secrets.token_hex(16) + ".pdf"
    pfad = os.path.join(anhang_dir(medien_dir), name)
    with open(pfad, "xb") as fh:
        fh.write(pdf)
    return name, hashlib.sha256(pdf).hexdigest()


def entfernen(medien_dir, name):
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return
    try:
        os.remove(os.path.join(anhang_dir(medien_dir), name))
    except OSError:
        pass
