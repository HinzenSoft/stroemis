#!/usr/bin/env python3
"""Maskottchen der Entwicklungsumgebung erzeugen (Wunsch des Nutzers vom 11.11.2026, Variante „Leitkegel als Hut“).

Auf dev.strömis.de steht in Kopfleiste, Anmeldung, öffentlicher Strömipedia und Hinweisseite ohne Netz statt des
Maskottchens dieselbe Figur mit einem orangefarbenen Leitkegel auf dem Helm (create_app wählt die Datei, wenn
module.dev_umgebung() gilt). Aus app/static/img/maskottchen.png entsteht app/static/img/maskottchen-dev.webp – im selben
Maßstab wie maskottchen.webp (256 px für die Figur ohne Kegel), der Kegel kommt obendrauf.

Aufruf im Wurzelordner des Repositories (Pillow wie in requirements.txt):
    python3 scripts/maskottchen_dev.py
Die Datei wird überschrieben; eingecheckt wird sie mit. Nötig nur, wenn sich das Maskottchen ändert."""
import math
import os
import sys

from PIL import Image, ImageDraw

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUELLE = os.path.join(WURZEL, "app", "static", "img", "maskottchen.png")
ZIEL = os.path.join(WURZEL, "app", "static", "img", "maskottchen-dev.webp")
ORANGE = (0xFF, 0x6A, 0x00, 255)
ORANGE_DUNKEL = (0xC8, 0x50, 0x00, 255)
WEISS = (0xFF, 0xFF, 0xFF, 255)
OBEN = 300                      # Platz über der Vorlage für den Kegel (Pixel der 1024er Vorlage)
SS = 4                          # gezeichnet wird vierfach, dann verkleinert – glatte Kanten
HOEHE_FIGUR = 256               # wie maskottchen.webp


def kegel(ebene):
    """Leitkegel mit zwei weißen Streifen und Fußplatte auf dem Helmscheitel (≈ 458/90 in der Vorlage), 8° geneigt
    wie der Kopf."""
    z = ImageDraw.Draw(ebene)
    cx, fuss = 458, 108 + OBEN
    w = math.radians(-8)

    def r(x, y):
        dx, dy = x - cx, y - fuss
        return ((cx + dx * math.cos(w) - dy * math.sin(w)) * SS, (fuss + dx * math.sin(w) + dy * math.cos(w)) * SS)

    hoehe, unten, oben = 380, 200, 46

    def band(t0, t1):
        b0, b1 = unten + (oben - unten) * t0, unten + (oben - unten) * t1
        return [r(cx - b0 / 2, fuss - hoehe * t0), r(cx + b0 / 2, fuss - hoehe * t0),
                r(cx + b1 / 2, fuss - hoehe * t1), r(cx - b1 / 2, fuss - hoehe * t1)]

    z.polygon(band(0, 1), fill=ORANGE)
    for t0, t1 in ((0.22, 0.38), (0.55, 0.69)):
        z.polygon(band(t0, t1), fill=WEISS)
    z.polygon([r(cx - 150, fuss + 4), r(cx + 150, fuss + 4), r(cx + 150, fuss - 30), r(cx - 150, fuss - 30)], fill=ORANGE)
    z.polygon([r(cx - 150, fuss + 4), r(cx + 150, fuss + 4), r(cx + 150, fuss - 6), r(cx - 150, fuss - 6)],
              fill=ORANGE_DUNKEL)


def main():
    vorlage = Image.open(QUELLE).convert("RGBA")
    figur_hoehe = vorlage.getchannel("A").getbbox()
    figur_hoehe = figur_hoehe[3] - figur_hoehe[1]
    bild = Image.new("RGBA", (vorlage.width, vorlage.height + OBEN), (0, 0, 0, 0))
    bild.paste(vorlage, (0, OBEN), vorlage)
    ebene = Image.new("RGBA", (bild.width * SS, bild.height * SS), (0, 0, 0, 0))
    kegel(ebene)
    bild.alpha_composite(ebene.resize(bild.size, Image.LANCZOS))
    bild = bild.crop(bild.getchannel("A").getbbox())
    faktor = HOEHE_FIGUR / figur_hoehe
    bild = bild.resize((round(bild.width * faktor), round(bild.height * faktor)), Image.LANCZOS)
    bild.save(ZIEL, "WEBP", quality=90, method=6)
    print(os.path.relpath(ZIEL, WURZEL), bild.size, os.path.getsize(ZIEL), "Byte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
