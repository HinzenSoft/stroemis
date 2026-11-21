"""Die Prüfstände tests/*.html in Chromium – bisher nur von Hand per Doppelklick geöffnet: Rundlauf des Editors
(rundlauf.html), Gleichstand von Leseansicht und Editor (gleichstand.html), nachgeholtes Speichern
(nachgeholtes_speichern.html), Mitlesen (live_mitlesen.html, rund eine halbe Minute) und HTML-Baustein
(baustein_editor.html). Jede Seite öffnet wie per Doppelklick über file:// in einem eigenen Chromium; bestanden ist sie,
wenn alle Kopfzeilen (#kopf, #kopf2, #kopf3) von „läuft …“ auf „ok“ gewechselt haben, keine Zeile rot ist und weder eine
Ausnahme noch ein Konsolenfehler kam. Rote Zeilen stehen samt Text im Befund. Ohne Chromium übersprungen.

    python tests/test_pruefstaende_html.py                      # alle
    python tests/test_pruefstaende_html.py rundlauf gleichstand # nur diese"""
import glob
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

from einfuehrung_browser import treiber, uebersprungen  # noqa: E402

FRIST = 180          # Sekunden je Seite; live_mitlesen.html wartet die echten Takte ab
KOPFZEILEN = "Array.from(document.querySelectorAll('[id^=kopf]')).map((k) => [k.id, k.className, k.textContent.trim()])"
ROT = ("Array.from(document.querySelectorAll('.zeile.fehler'))"
       ".map((z) => z.textContent.trim().replace(/\\s+/g, ' ').slice(0, 800))")


def _erwartet(fehler):
    """Über file:// gibt es die Wurzelpfade der App nicht: Die Beispieltexte zeigen auf /media/…, das CSS der App lädt
    seine Schrift aus /static/fonts/. Beides scheitert beim Doppelklick genauso – kein Befund. Ein fehlendes Skript der
    Seite (../app/static/…) zählt weiter."""
    return fehler.startswith("Log: Failed to load resource") and (" file:///media/" in fehler
                                                                   or " file:///static/" in fehler)


def seiten():
    return sorted(glob.glob(os.path.join(HIER, "*.html")))


def pruefen(pfad):
    """Befunde einer Seite als Sätze – leer heißt bestanden."""
    name = os.path.basename(pfad)
    b = treiber().Browser()
    try:
        b.oeffnen("file://" + pfad, warten=0.2)
        ende = time.time() + FRIST
        while True:
            kopf = b.js(KOPFZEILEN) or []
            if kopf and all(c in ("ok", "fehler") for _, c, _ in kopf):
                break
            if time.time() > ende:
                return [f"{name}: nach {FRIST} s nicht fertig – {kopf}"]
            b.warten(0.5)
        befunde = [f"{name} #{i}: {t}" for i, c, t in kopf if c != "ok"]
        befunde += [f"{name}: {z}" for z in b.js(ROT) or []]
        befunde += [f"{name}: {f}" for f in b.fehler() if not _erwartet(f)]
        if not befunde:
            print(f"{name}: " + " · ".join(t for _, _, t in kopf))
        return befunde
    finally:
        b.schliessen()


def test_pruefstaende():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    wahl = sys.argv[1:] if __name__ == "__main__" else []
    befunde = []
    for pfad in seiten():
        if not wahl or any(w in os.path.basename(pfad) for w in wahl):
            befunde += pruefen(pfad)
    assert not befunde, "\n".join(befunde)


if __name__ == "__main__":
    test_pruefstaende()
    print("Prüfstände bestanden.")
