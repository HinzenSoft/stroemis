"""Globale Seriennummernsuche und QR-Steckbrief fremder Artikel (Phase 2 · L1, Abschnitt 3).

Gesucht wird nur nach der exakten Herstellerseriennummer, angeboten wird die Suche erst, wenn im eigenen Bereich kein
Artikel genau diese Nummer hat; sie läuft nach Bestätigung, durch die Bremse und ins Protokoll (globalprotokoll). Ein
Treffer zeigt nur Stammdaten und Zugehörigkeit – genau die Schlüssel in FELDER.

Dieser Teil (Schalter, Felder, Normalform, Angebot) ist der gemeinsame Unterbau; die Suche selbst und der Steckbrief
folgen unten (Paket C)."""
from .nummern import INVENTAR_VORSATZ, sieht_generiert_aus

# FRAGE 2 – wann die globale Suche angeboten wird: „ohne_exakten_treffer“ (gebaut) – kein sichtbarer Artikel hat genau
# diese Seriennummer, Teiltreffer dürfen da sein; „ohne_treffer“ – wörtlich nach Vorgabe: die lokale Suche fand nichts.
ANGEBOT = "ohne_exakten_treffer"
ANGEBOTE = ("ohne_exakten_treffer", "ohne_treffer")
# FRAGE 1 – Sperrzustand im Steckbrief („sperre“: ausgesondert, gesperrt, verloren gemeldet). Gebaut wird ohne.
STECKBRIEF_MIT_SPERRE = False
# Genau diese Schlüssel hat jeder Treffer (der Test prüft Gleichheit) – keine Kennungen, kein Status, keine Prüfungen.
FELDER = frozenset({"inventory_no", "serial_no", "hersteller", "modell", "artikelnummer", "norm", "materialart",
                    "kategorie", "vorschau", "hergestellt", "lebensende", "gliederung", "ordner", "demo"})
MIN_ZEICHEN, MAX_ZEICHEN = 4, 80


def normalform(q):
    """Die Anfrage, wie sie gesucht und protokolliert wird: Leerraum zusammengezogen, außen keiner."""
    return " ".join(str(q or "").split())


def suchbar(q):
    """Taugt die Anfrage für die globale Suche? 4 bis 80 Zeichen und keine vom System vergebene Nummer – Inventar- und
    STR-Nummern sind fortlaufend und ließen sich abzählen."""
    n = normalform(q)
    return (MIN_ZEICHEN <= len(n) <= MAX_ZEICHEN and not sieht_generiert_aus(n)
            and not n.upper().startswith(INVENTAR_VORSATZ))


def angebot(q, lokale_treffer, exakt_lokal):
    """Soll die Trefferseite (und suche.js) die globale Suche anbieten? lokale_treffer: Zahl der sichtbaren Treffer der
    lokalen Suche; exakt_lokal: ein sichtbarer Artikel hat genau diese Seriennummer."""
    if not suchbar(q) or exakt_lokal:
        return False
    if ANGEBOT == "ohne_treffer":
        return not lokale_treffer
    return True
