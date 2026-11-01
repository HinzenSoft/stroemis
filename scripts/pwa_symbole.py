#!/usr/bin/env python3
"""App-Symbole für die installierbare Web-App erzeugen (app/pwa.py, README „Als App installieren“).

Entscheidung des Nutzers vom 01.11.2026: das Maskottchen der Kopfleiste auf Rot (--rot #e30613). Aus
app/static/img/maskottchen.png entstehen unter app/static/img/pwa/:

  symbol-192.png, symbol-512.png                   „any“: Maskottchen groß, unten angeschnitten wie in der Kopfleiste
  symbol-maskable-192.png, symbol-maskable-512.png „maskable“: kleiner, mit Schutzrand – Android schneidet Kreis,
                                                   Tropfen oder Quadrat aus; alles Wichtige liegt im inneren Kreis
                                                   (Radius 40 % der Kantenlänge)
  symbol-96.png                                    Kurzbefehle (lange auf das App-Symbol drücken)
  apple-touch-icon.png (180 px)                    iPhone/iPad, „Zum Home-Bildschirm“ – iOS rundet die Ecken selbst

und dieselben noch einmal mit „-dev“ vor der Endung: mit einer gelben Marke „dev“ in der Hausschrift (DLRG Univers Bold
aus app/static/fonts), damit die App der Entwicklungsumgebung auf einem Telefon neben der echten zu erkennen ist.

Aufruf im Wurzelordner des Repositories (Pillow wie in requirements.txt):
    python3 scripts/pwa_symbole.py
Die Dateien werden überschrieben; eingecheckt werden sie mit. Nötig nur, wenn sich das Maskottchen ändert."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUELLE = os.path.join(WURZEL, "app", "static", "img", "maskottchen.png")
ZIEL = os.path.join(WURZEL, "app", "static", "img", "pwa")
SCHRIFT = os.path.join(WURZEL, "app", "static", "fonts", "dlrg-univers-bold.woff2")
ROT = (0xE3, 0x06, 0x13)        # --rot
GELB = (0xFF, 0xED, 0x00)       # --gelb
SCHWARZ = (0x3C, 0x3C, 0x3B)    # --schwarz
GROSS = 1024                    # gezeichnet wird groß, dann verkleinert


def maskottchen():
    """Das Maskottchen ohne leeren Rand (Alphakanal)."""
    bild = Image.open(QUELLE).convert("RGBA")
    return bild.crop(bild.getchannel("A").getbbox())


def zeichnen(figur, hoehe_anteil, dev):
    """Eine Fläche GROSS × GROSS in Rot, die Figur unten bündig und waagerecht mittig, so hoch wie hoehe_anteil."""
    flaeche = Image.new("RGBA", (GROSS, GROSS), ROT + (255,))
    h = round(GROSS * hoehe_anteil)
    b = round(figur.width * h / figur.height)
    klein = figur.resize((b, h), Image.LANCZOS)
    flaeche.alpha_composite(klein, ((GROSS - b) // 2, GROSS - h))
    if dev:
        marke(flaeche)
    return flaeche


def marke(flaeche):
    """Gelbe Pille „dev“, mittig im unteren Drittel – innerhalb des Schutzkreises der maskable-Symbole."""
    z = ImageDraw.Draw(flaeche)
    breite, hoehe = round(GROSS * .40), round(GROSS * .16)
    mx, my = GROSS // 2, round(GROSS * .77)
    kasten = (mx - breite // 2, my - hoehe // 2, mx + breite // 2, my + hoehe // 2)
    z.rounded_rectangle(kasten, radius=hoehe // 2, fill=GELB + (255,), outline=SCHWARZ + (255,), width=round(GROSS * .008))
    schrift = ImageFont.truetype(SCHRIFT, round(hoehe * .72))
    z.text((mx, my), "dev", font=schrift, fill=SCHWARZ + (255,), anchor="mm")


def speichern(bild, groesse, name):
    pfad = os.path.join(ZIEL, name)
    bild.resize((groesse, groesse), Image.LANCZOS).convert("RGB").save(pfad, optimize=True)
    return pfad


def main():
    os.makedirs(ZIEL, exist_ok=True)
    figur = maskottchen()
    pfade = []
    for dev in (False, True):
        zusatz = "-dev" if dev else ""
        voll = zeichnen(figur, .90, dev)             # „any“ und iOS: die Figur füllt das Symbol
        maskierbar = zeichnen(figur, .70, dev)       # „maskable“: Kopf und Marke im inneren Kreis
        for g in (192, 512):
            pfade.append(speichern(voll, g, f"symbol-{g}{zusatz}.png"))
            pfade.append(speichern(maskierbar, g, f"symbol-maskable-{g}{zusatz}.png"))
        pfade.append(speichern(voll, 96, f"symbol-96{zusatz}.png"))
        pfade.append(speichern(voll, 180, f"apple-touch-icon{zusatz}.png"))
    for p in pfade:
        print(os.path.relpath(p, WURZEL), os.path.getsize(p), "Byte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
