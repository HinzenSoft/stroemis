"""Sichtbare Namen und Seitenadressen der Module (Umbenennung 26.10.2026).

Die internen Schlüssel bleiben (auth.MODULE, Spalten recht_<modul>, Endpunkt- und Dateinamen, /api/…): Umbenannt sind
nur die Namen, die man sieht, und die Adressen der Seiten. Die alten Adressen leiten für immer weiter – gedruckte
Protokolle tragen /material/pruefen, Mails und Lesezeichen /wiki/…, /karte, /pruefungen…, /admin, und gespeicherte
Wiki-Seiten verlinken weiter mit /wiki/<slug>.

Fließtexte setzen die Namen nicht aus NAME zusammen, sie sind wörtlich formuliert (die Strömipedia, die Ankerplätze,
die Riegenkarten, die Materialablage, die Leitstelle). NAME gilt für Reiter, Seitentitel und die Spalten der
Rechte-Matrix."""
import unicodedata
from urllib.parse import quote

NAME = {"wiki": "Strömipedia", "karte": "Ankerplätze", "pruefungen": "Riegenkarten",
        "material": "Materialablage", "verwaltung": "Leitstelle"}
PFAD = {"wiki": "/stroemipedia", "karte": "/ankerplaetze", "pruefungen": "/riegenkarten",
        "material": "/materialablage", "verwaltung": "/leitstelle"}
ALT = {"wiki": "/wiki", "karte": "/karte", "pruefungen": "/pruefungen",
       "material": "/material", "verwaltung": "/admin"}
# Wer die Adresse von Hand tippt, schreibt sie oft mit Umlaut – auch das führt hin (Entscheidung F3 A).
UMLAUT = {"wiki": "/strömipedia", "karte": "/ankerplätze"}

# Präfix → neues Präfix, längste zuerst (keins ist Anfang eines anderen, die Ordnung hält das auch künftig sicher).
_WEITER = sorted([(ALT[m], PFAD[m]) for m in ALT] + [(UMLAUT[m], PFAD[m]) for m in UMLAUT],
                 key=lambda x: -len(x[0]))
# Startseiten mit Schrägstrich am Ende (Lesezeichen, von Hand getippt) gab es nie – sie führen auf die Adresse ohne.
_MIT_STRICH = {PFAD[m] + "/": PFAD[m] for m in PFAD}
# Was in einem Pfadsegment unkodiert stehen darf (RFC 3986, pchar ohne „%“) – alles andere wird kodiert, auch der
# Rückstrich: Ein Browser läse „/\\“ sonst wie „//“.
_PFAD_ZEICHEN = "/!$&'()*+,;=:@-._~"


def weiterleitung(pfad, abfrage=""):
    """Neue Adresse für einen alten Seitenpfad – oder None. pfad ist der dekodierte Pfad der Anfrage (request.path),
    abfrage der rohe Abfrageteil ohne „?“ (bleibt, wie er kam). Das Ziel ist immer ein eigener Pfad: festes Präfix plus
    der Rest des angefragten Pfads, kodiert – nie ein anderer Host, nie ein Schema, nie „//“ am Anfang. Ein
    Schrägstrich am Ende der Startseite eines Moduls („/stroemipedia/“, auch „/wiki/“) fällt weg."""
    pfad = unicodedata.normalize("NFC", pfad or "")
    if pfad in _MIT_STRICH:
        return _MIT_STRICH[pfad] + ("?" + abfrage if abfrage else "")
    for alt, neu in _WEITER:
        if pfad == alt or pfad.startswith(alt + "/"):
            rest = pfad[len(alt):]
            ziel = neu + ("" if rest == "/" else quote(rest, safe=_PFAD_ZEICHEN))
            return ziel + ("?" + abfrage if abfrage else "")
    return None
