#!/usr/bin/env python3
"""Übungsdateien der Einführung erzeugen (app/einfuehrung.py, README „Einführungen (Übungen je Modul)“).

Die Übungen zeigen nie echte Bilder oder Dokumente (Bauvorlage planung/tutorial/entwurf.md, 2.3 und 3): Was in einer
Übung als Foto oder Datei auftaucht, liegt unter app/static/uebung/ – schlichte Grafiken mit der Aufschrift
„Übungsbild n“ (Fläche, Wellenlinien und Rahmen in den Farben der Tokens, Schrift DLRG Univers Bold aus
app/static/fonts, höchstens 60 KB) und ein einseitiges PDF „Übungsdatei – kein echtes Dokument“ (Helvetica, ohne
eingebettete Schrift, von Hand gesetzt – klein und gültig).

Aufruf im Wurzelordner des Repositories (Pillow wie in requirements.txt):
    python3 scripts/uebungsdateien.py                       # uebungsbild-1…3.jpg und uebungsdatei.pdf in app/static/uebung/
    python3 scripts/uebungsdateien.py --ziel app/static/uebung/karte --von 4 --bis 6 --ohne-pdf
                                                            # weitere Bilder gleicher Art für einen Modul-Teil
Die Dateien werden überschrieben und eingecheckt."""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(WURZEL, "app", "static", "uebung")
SCHRIFT = os.path.join(WURZEL, "app", "static", "fonts", "dlrg-univers-bold.woff2")
WASSER = (0x00, 0x69, 0xB4)       # --wasser
ANTHRAZIT = (0x57, 0x57, 0x56)    # --anthrazit
WEISS = (0xFF, 0xFF, 0xFF)        # --weiss
# Flächen der Hinweiskästen (--co-info-fl, --co-success-fl, --co-sonne-fl, --co-flieder-fl …) – je Bild eine andere.
FLAECHEN = ((0xEA, 0xF2, 0xF9), (0xE9, 0xF5, 0xEC), (0xFD, 0xF6, 0xD8), (0xEF, 0xE6, 0xF7), (0xF3, 0xED, 0xE3),
            (0xE4, 0xF0, 0xFA))
BREITE, HOEHE = 800, 600
MAX_BYTES = 60 * 1024


def bild(n):
    """Ein Übungsbild: Fläche, drei Wellenlinien in --wasser, ein weißes Schild mit „Übungsbild n“."""
    flaeche = Image.new("RGB", (BREITE, HOEHE), FLAECHEN[(n - 1) % len(FLAECHEN)])
    z = ImageDraw.Draw(flaeche)
    for reihe in range(3):
        y0 = HOEHE * (0.62 + reihe * 0.1)
        punkte = [(x, y0 + 14 * math.sin((x / BREITE) * 2 * math.pi * 2 + n + reihe)) for x in range(0, BREITE + 1, 8)]
        z.line(punkte, fill=WASSER, width=6)
    z.rectangle((10, 10, BREITE - 11, HOEHE - 11), outline=WASSER, width=6)
    schrift = ImageFont.truetype(SCHRIFT, 72)
    text = f"Übungsbild {n}"
    links, oben, rechts, unten = z.textbbox((0, 0), text, font=schrift)
    b, h = rechts - links, unten - oben
    schild = (BREITE // 2 - b // 2 - 36, HOEHE * 0.36 - h // 2 - 28, BREITE // 2 + b // 2 + 36, HOEHE * 0.36 + h // 2 + 28)
    z.rounded_rectangle(schild, radius=12, fill=WEISS, outline=ANTHRAZIT, width=3)
    z.text((BREITE // 2 - b // 2 - links, HOEHE * 0.36 - h // 2 - oben), text, font=schrift, fill=ANTHRAZIT)
    return flaeche


def bild_speichern(n, ordner):
    pfad = os.path.join(ordner, f"uebungsbild-{n}.jpg")
    for qualitaet in (82, 70, 60, 50):
        bild(n).save(pfad, "JPEG", quality=qualitaet, optimize=True, progressive=True)
        if os.path.getsize(pfad) <= MAX_BYTES:
            return pfad
    raise SystemExit(f"{pfad} bleibt über {MAX_BYTES} Byte.")


def _pdf_text(text):
    """Ein Text für einen PDF-String in WinAnsi (Ü, ö, – sind darin) mit maskierten Klammern."""
    roh = text.encode("cp1252")
    return roh.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _pdf_info(text):
    """Ein Text für das Info-Verzeichnis: UTF-16BE mit Byte-Order-Mark als Hex-String (dort gilt nicht WinAnsi)."""
    return b"<FEFF" + text.encode("utf-16-be").hex().upper().encode() + b">"


def pdf():
    """Ein einseitiges PDF (A4) mit zwei Zeilen Text, Helvetica aus den Standardschriften."""
    zeilen = [(16, 760, "Übungsdatei – kein echtes Dokument"),
              (11, 730, "Diese Datei gehört zu den Übungen in strömis.de. Sie enthält keine echten Daten."),
              (11, 712, "Echte Protokolle und Dokumente öffnest du außerhalb der Übung.")]
    inhalt = b"".join(b"BT /F1 %d Tf 56 %d Td (%s) Tj ET\n" % (g, y, _pdf_text(t)) for g, y, t in zeilen)
    objekte = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n%sendstream" % (len(inhalt), inhalt),
        b"<< /Title %s /Producer %s >>" % (_pdf_info("Übungsdatei – kein echtes Dokument"), _pdf_info("strömis.de")),
    ]
    daten = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    stellen = []
    for i, obj in enumerate(objekte, 1):
        stellen.append(len(daten))
        daten += b"%d 0 obj\n%s\nendobj\n" % (i, obj)
    xref = len(daten)
    daten += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)
    daten += b"".join(b"%010d 00000 n \n" % s for s in stellen)
    daten += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objekte) + 1, xref)
    return daten


def main(argv=None):
    a = argparse.ArgumentParser(description="Übungsbilder und Übungsdatei der Einführung erzeugen.")
    a.add_argument("--ziel", default=ZIEL, help="Ordner (Vorgabe app/static/uebung)")
    a.add_argument("--von", type=int, default=1)
    a.add_argument("--bis", type=int, default=3)
    a.add_argument("--ohne-pdf", action="store_true", help="nur Bilder")
    args = a.parse_args(argv)
    os.makedirs(args.ziel, exist_ok=True)
    for n in range(args.von, args.bis + 1):
        print(bild_speichern(n, args.ziel))
    if not args.ohne_pdf:
        pfad = os.path.join(args.ziel, "uebungsdatei.pdf")
        with open(pfad, "wb") as fh:
            fh.write(pdf())
        print(pfad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
