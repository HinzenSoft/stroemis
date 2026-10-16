"""Inventar- und Seriennummern, die das System vergibt.

Inventarnummer: plattformweit eineindeutig, fortlaufend „M-000001“ – der Zähler steht in mat_meta und
wird nie zurückgesetzt, auch nicht, wenn ein falsch angelegter Artikel wieder gelöscht wird: Eine
Nummer, die einmal auf einem Etikett stand, bezeichnet nie ein anderes Stück.
Seriennummer ohne Herstellerangabe: „STR-000001“ mit derselben Zahl wie die Inventarnummer – damit
ebenso eindeutig. Das Muster ist für Herstellernummern gesperrt, damit nie eine echte mit einer
vergebenen zusammenfällt.

Beides muss in der Schreibtransaktion laufen, in der auch der Artikel entsteht (BEGIN IMMEDIATE):
Zwei gleichzeitige Anlagen bekämen sonst dieselbe Nummer."""
import re

from ... import db

INVENTAR_VORSATZ = "M-"
SERIEN_VORSATZ = "STR-"
_GENERIERT = re.compile(r"^\s*STR-\d+\s*$", re.I)


def naechste_inventarnummer():
    row = db.query("SELECT wert FROM mat_meta WHERE schluessel = 'inventar_zaehler'", one=True)
    n = int(row["wert"]) + 1 if row else 1
    db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES ('inventar_zaehler', ?) "
               "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (str(n),))
    return f"{INVENTAR_VORSATZ}{n:06d}"


def seriennummer_fuer(inventarnummer):
    return SERIEN_VORSATZ + inventarnummer[len(INVENTAR_VORSATZ):]


def sieht_generiert_aus(seriennummer):
    return bool(_GENERIERT.match(seriennummer or ""))


def inventar_ziffern(eingabe):
    """„m-123“, „M000123“, „123“ → 123, wenn die Eingabe eine Inventarnummer meint – sonst None."""
    m = re.fullmatch(r"\s*(?:m-?)?0*(\d{1,9})\s*", eingabe or "", re.I)
    return int(m.group(1)) if m else None
