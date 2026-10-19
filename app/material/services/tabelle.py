"""Tabellen lesen für den Bestandsimport (Phase 2 · Lieferung 3): CSV und Excel-Arbeitsmappe (.xlsx) – ohne Flask und
ohne Datenbank, damit sich jede Regel für sich prüfen lässt.

Die Excel-Seite kommt aus app/pruefungen_import.py (pi: Arbeitsblatt öffnen, Zellwerte, Datumsformate, Grenzen) –
genutzt, nicht kopiert und nicht verändert. pi lädt openpyxl beim Import des Moduls; geholt wird es deshalb erst hier
in der Funktion (_pi), wie api_pruefungen._import_modul: Kein Arbeitsprozess lädt openpyxl beim Start. Auch private
Namen aus pi werden genutzt (_arbeitsblatt, _beginnt_mit, _leer, _ist_textzelle) – eine bewusste Abwägung; der Test
test_material_import.test_migration_12 ruft jeden genutzten Namen einmal auf, damit ein Umbau von pi sofort auffällt.

Grenzen VOR dem Laden: pi lädt eine Arbeitsmappe vollständig und zählt die Zellen erst danach (gemessen: 14,8 MB xlsx
mit 6 Mio. Zellen brauchen 2,7 GB, bevor die Grenze greift), und eine CSV, die ganz in Zeilenlisten gelesen wird, wird
aus 25 MB „a\\n“ 1,5 GB. Deshalb hier: höchstens MAX_BYTES Upload, eine xlsx entpackt höchstens MAX_ENTPACKT (eigene
Prüfung des ZIP-Inhaltsverzeichnisses, bevor pi etwas entpackt), eine CSV Zeile für Zeile mit Abbruch nach
MAX_CSV_ZEILEN Zeilen bzw. MAX_CSV_ZELLEN Feldern.

Alles, was hier schiefgeht, ist ein Fehler der Datei: Abgelehnt mit Klartext (400, zu groß 413)."""
import csv
import hashlib
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime

from . import Abgelehnt

MAX_BYTES = 5 * 1024 * 1024            # Upload (eine Liste mit 2000 Zeilen hat als xlsx < 1 MB, als CSV < 2 MB)
MAX_ENTPACKT = 10 * 1024 * 1024        # xlsx: Summe aller Einträge entpackt (2000 Zeilen × 80 Spalten ≈ 5 MB XML)
MAX_CSV_ZEILEN = 10_000                # physische Zeilen, auch leere
MAX_CSV_ZELLEN = 600_000
TRENNZEICHEN = (";", "\t", ",")        # bei Gleichstand in dieser Reihenfolge

SPEICHERN = "Bitte in Excel als „Excel-Arbeitsmappe (.xlsx)“ oder als „CSV (Trennzeichen-getrennt)“ speichern."
UNLESBAR_XLSX = "Die Datei ließ sich nicht als Excel-Arbeitsmappe lesen."
ZEICHENSATZ = ("Zeichensatz nicht erkannt – bitte in Excel als „CSV UTF-8 (durch Trennzeichen getrennt)“ "
               "speichern.")
_ALTE_ENDUNGEN = (".xls", ".ods", ".numbers")
_BILD = (b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")
_MONAT = re.compile(r"^(\d{1,2})\s*[/.\-]\s*(\d{4})$")           # 03/2021, 3/2021, 03.2021, 03-2021
_MONAT_ISO = re.compile(r"^(\d{4})-(\d{1,2})$")                   # 2021-03
_JAHR = re.compile(r"^\d{4}$")
_EXPONENT = re.compile(r"^\d([.,]\d+)?[eE][+-]\d+$")              # so schreibt Excel große Zahlen: 1,23457E+11

_log = logging.getLogger(__name__)


def _pi():
    """pruefungen_import erst laden, wenn eine Datei kommt (es zieht openpyxl nach)."""
    from ... import pruefungen_import
    return pruefungen_import


@dataclass
class Tabelle:
    art: str             # "csv" | "xlsx"
    kodierung: str       # "utf-8" | "utf-8-sig" | "utf-16" | "cp1252" | "" (xlsx)
    trennzeichen: str    # ";" | "," | "\t" | "" (xlsx)
    zeilen: list         # Zeilen als Listen von Zellwerten (CSV: str; xlsx: Werte wie openpyxl)
    sha256: str          # der hochgeladenen Bytes


def spalte_buchstabe(index):
    """0 → „A“, 26 → „AA“ – wie Excel die Spalten nennt (ohne openpyxl)."""
    n, out = index + 1, ""
    while n:
        n, rest = divmod(n - 1, 26)
        out = chr(65 + rest) + out
    return out


# --- Datei lesen -------------------------------------------------------------------------------------------------

def lesen(roh, dateiname):
    """Bytes einer hochgeladenen Datei → Tabelle. Erst der Dateikopf (alte Excel-Datei, PDF, Bild), dann .xlsx (ZIP)
    oder CSV. Wirft Abgelehnt mit einem Satz, der sagt, was zu tun ist."""
    roh = bytes(roh or b"")
    if not roh:
        raise Abgelehnt("Die Datei ist leer.")
    if len(roh) > MAX_BYTES:
        raise Abgelehnt(f"Die Datei ist größer als {MAX_BYTES // (1024 * 1024)} MB – bitte nur die Liste speichern "
                        "(ohne Bilder und weitere Blätter) oder als CSV.", 413)
    name = (dateiname or "").lower()
    if name.endswith(_ALTE_ENDUNGEN):
        raise Abgelehnt(SPEICHERN)
    if roh.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise Abgelehnt("Das ist eine alte Excel-Datei (.xls). Bitte in Excel als „Excel-Arbeitsmappe (.xlsx)“ "
                        "speichern.")
    if roh.startswith(b"%PDF"):
        raise Abgelehnt("Das ist eine PDF-Datei – bitte die Liste als .xlsx oder CSV speichern.")
    if roh.startswith(_BILD):
        raise Abgelehnt("Das ist ein Bild – bitte die Liste als .xlsx oder CSV speichern.")
    sha = hashlib.sha256(roh).hexdigest()
    if roh.startswith(b"PK"):
        return Tabelle("xlsx", "", "", _xlsx(roh), sha)
    kodierung, text = _dekodieren(roh)
    trenn = trennzeichen_erkennen(text)
    return Tabelle("csv", kodierung, trenn, _csv_zeilen(text, trenn), sha)


def _xlsx(roh):
    """Eigene Vorprüfung des ZIP-Inhaltsverzeichnisses, dann das erste Blatt mit Inhalt über pi. zipfile hält sich beim
    Entpacken an die eingetragenen Größen (mehr wird abgeschnitten, die Prüfsumme schlägt fehl) – die Summe taugt als
    Obergrenze dessen, was gleich im Speicher landet (dieselbe Überlegung wie pi._archiv_pruefen)."""
    try:
        with zipfile.ZipFile(io.BytesIO(roh)) as zf:
            eintraege = zf.infolist()
    except Exception as exc:                                 # noqa: BLE001 – jede Leseausnahme ist ein Dateiproblem
        _log.warning("Bestandsimport: ZIP unlesbar: %r", exc)
        raise Abgelehnt(UNLESBAR_XLSX)
    pi = _pi()
    if len(eintraege) > pi.MAX_ZIP_EINTRAEGE:
        raise Abgelehnt(f"Die Datei besteht aus {len(eintraege)} Einträgen – eine Excel-Arbeitsmappe hat höchstens "
                        f"{pi.MAX_ZIP_EINTRAEGE}. Bitte nur die Bestandsliste hochladen.")
    entpackt = sum(e.file_size for e in eintraege)
    if entpackt > MAX_ENTPACKT:
        raise Abgelehnt(f"Die Arbeitsmappe ist entpackt {-(-entpackt // (1024 * 1024))} MB groß – höchstens "
                        f"{MAX_ENTPACKT // (1024 * 1024)} MB lassen sich einlesen. Bitte nur die Liste speichern (ohne "
                        "Bilder und weitere Blätter) oder als CSV.")
    try:
        # Leerer Dateiname: Die Endung hat lesen() schon geprüft.
        return pi._arbeitsblatt(roh, "")
    except pi.ImportFehler as exc:
        raise Abgelehnt(str(exc).replace("die Teilnehmerliste", "die Bestandsliste"))
    except Exception as exc:                                 # noqa: BLE001 – was openpyxl wirft, ist ein Dateiproblem
        _log.warning("Bestandsimport: Arbeitsmappe unlesbar: %r", exc)
        raise Abgelehnt(UNLESBAR_XLSX)


def _dekodieren(roh):
    """(Kodierung, Text): BOM UTF-8 → utf-8-sig, BOM UTF-16 → utf-16, sonst UTF-8 streng und danach Windows-1252 streng
    (deutsches Excel). Jeder Versuch steht für sich – scheitert der letzte, ist es ein Fehler der Datei."""
    if roh.startswith(b"\xef\xbb\xbf"):
        versuche = ("utf-8-sig",)
    elif roh.startswith((b"\xff\xfe", b"\xfe\xff")):
        versuche = ("utf-16",)
    else:
        versuche = ("utf-8", "cp1252")
    for kodierung in versuche:
        try:
            text = roh.decode(kodierung)
        except (UnicodeDecodeError, LookupError):
            continue
        if "\x00" in text:
            raise Abgelehnt("Die Datei enthält Steuerzeichen – ist es wirklich eine CSV-Datei?")
        return kodierung, text
    raise Abgelehnt(ZEICHENSATZ)


def trennzeichen_erkennen(text):
    """In den ersten 40 nicht leeren Zeilen (pi.MAX_KOPF_SUCHE): wie oft kommen „;“, Tab und „,“ außerhalb von
    Anführungszeichen vor? Es gewinnt das häufigste, bei Gleichstand „;“ vor Tab vor „,“ – ohne jedes ein „;“."""
    zahl = dict.fromkeys(TRENNZEICHEN, 0)
    grenze = _pi().MAX_KOPF_SUCHE
    zitat, inhalt, zeilen = False, False, 0
    for zeichen in text:
        if zeichen == '"':
            zitat, inhalt = not zitat, True
        elif zitat:
            continue
        elif zeichen == "\n":
            zeilen += inhalt
            if zeilen >= grenze:
                break
            inhalt = False
        elif zeichen in zahl:
            zahl[zeichen] += 1
        elif not zeichen.isspace():
            inhalt = True
    return max(TRENNZEICHEN, key=lambda t: (zahl[t], -TRENNZEICHEN.index(t)))


def _csv_zeilen(text, trenn):
    """Gestreamt: Zeile für Zeile, mit Zählern für physische Zeilen und Felder – bricht ab, sobald eine Grenze
    überschritten ist, nicht erst, wenn alles gelesen ist. Mehr als pi.MAX_SPALTEN Spalten in einer Zeile: Fehler wie in
    pi. Die Zahl der Datenzeilen prüft bestandsimport.spalten nach der Kopfzeile."""
    max_spalten = _pi().MAX_SPALTEN
    leser = csv.reader(io.StringIO(text, newline=""), delimiter=trenn, quotechar='"')
    zeilen, zellen = [], 0
    try:
        for zeile in leser:
            zellen += len(zeile)
            if leser.line_num > MAX_CSV_ZEILEN or zellen > MAX_CSV_ZELLEN:
                raise Abgelehnt(f"Die CSV-Datei hat mehr als {MAX_CSV_ZEILEN:,} Zeilen bzw. {MAX_CSV_ZELLEN:,} Felder – "
                                "bitte nur die Liste speichern.".replace(",", "."))
            if len(zeile) > max_spalten:
                raise Abgelehnt(f"Zeile {leser.line_num} reicht bis Spalte {len(zeile)} – höchstens {max_spalten} "
                                "Spalten lassen sich einlesen. Bitte Inhalte weit außerhalb der Liste entfernen.")
            zeilen.append(zeile)
    except csv.Error:
        raise Abgelehnt(f"Die CSV-Datei ist unlesbar (Zeile {leser.line_num}).")
    return zeilen


# --- Zellen ------------------------------------------------------------------------------------------------------

def zelltext(wert):
    """Zellwert als Text (pi.als_text: Datum → ISO, 3.0 → „3“, Leerraum – auch geschützte Leerzeichen – zusammengezogen),
    dazu der Formelschutz aus dem eigenen CSV-Export zurück: Beginnt der Text mit ' und danach mit einem Zeichen aus
    export.FORMEL_ANFANG, fällt das ' weg (genau die Umkehrung von export._zelle); ein ' vor anderem Text bleibt."""
    text = _pi().als_text(wert.replace("\xa0", " ") if isinstance(wert, str) else wert)
    if text.startswith("'") and text[1:2] and text[1] in _formel_anfang():
        return text[1:]
    return text


def _formel_anfang():
    # Aus export.py (dort steht die Regel des Exports) – in der Funktion geholt, tabelle.py bleibt frei von Flask.
    from .export import FORMEL_ANFANG
    return FORMEL_ANFANG


def ist_leer(wert):
    return wert is None or (isinstance(wert, str) and not wert.strip())


def serientext(wert):
    """Seriennummer aus dem ROHWERT der Zelle, bevor als_text aus einer Gleitkommazahl still „12345678901234567168“
    macht. (Text, Hinweis | None): eine Zahl ab 10^15 in Exponentenschreibweise (Excel hat Ziffern verloren – die
    Prüfregel erkennt sie daran), eine kleinere ganze Zahl als Ziffern mit dem Hinweis auf führende Nullen, ein Datum
    als ISO (die Prüfregel erkennt es), sonst zelltext."""
    if isinstance(wert, (int, float)) and not isinstance(wert, bool):
        if abs(wert) >= 10 ** 15:
            return f"{float(wert):E}", None
        if float(wert).is_integer():
            return str(int(wert)), "Seriennummer war als Zahl gespeichert – führende Nullen prüfen"
        return zelltext(wert), "Seriennummer war als Zahl gespeichert – bitte prüfen"
    if isinstance(wert, (datetime, date)):
        return _pi().als_text(wert)[:10], None
    return zelltext(wert), None


def sieht_aus_wie_exponent(text):
    return bool(_EXPONENT.match(text or ""))


def sieht_aus_wie_datum(text):
    """Liest pi.datum_lesen den Text als Tag (auch ISO aus einer Datumszelle)?"""
    return _pi().datum_lesen(text) is not None


# --- Datums- und Monatsangaben -----------------------------------------------------------------------------------

def _monat_ok(jahr, monat):
    return jahr >= 1900 and 1 <= monat <= 12


def datum(text, art):
    """Ein Datum aus der Liste. art „tag“ (zuletzt geprüft, nächste Prüfung, Lebensende) oder „monat“ (hergestellt,
    gekauft, Erstgebrauch). Liefert (iso | None, fehler | None, hinweis | None):

      15.03.2021, 15.3.21, 2021-03-15 (auch mit Uhrzeit), Datumszelle  → „2021-03-15“
      03/2021, 3/2021, 03.2021, 03-2021, 2021-03                         → „2021-03“ (monat) bzw. „2021-03-01“ mit
                                                                           Hinweis (tag – eher zu früh als zu spät)
      2021                                                               → Fehler „nur Jahr“
      alles andere (März 2021, 03/21, 31.02.2021, 44270)                  → Fehler „unlesbar“

    Ob ein Fehler die Zeile blockiert oder nur ein Hinweis ist, entscheidet der Aufrufer."""
    t = (text or "").strip()
    if not t:
        return None, None, None
    iso = _pi().datum_lesen(t)
    if iso:
        return iso, None, None
    m = _MONAT.match(t) or _MONAT_ISO.match(t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        jahr, monat = (b, a) if m.re is _MONAT else (a, b)
        if not _monat_ok(jahr, monat):
            return None, "unlesbar", None
        if art == "monat":
            return f"{jahr:04d}-{monat:02d}", None, None
        return f"{jahr:04d}-{monat:02d}-01", None, "Monatsangabe – als 1. des Monats gelesen"
    if _JAHR.match(t):
        return None, "nur Jahr", None
    return None, "unlesbar", None


# --- Kopfzeile ---------------------------------------------------------------------------------------------------

def kopfzeile(zeilen, erkennen):
    """(Index, Warnung | None) der Kopfzeile: die erste Zeile unter den ersten 40, in der mindestens zwei Titel ein Feld
    treffen (erkennen(titel) → Feld oder None); sonst die Zeile mit den meisten Textzellen (mindestens drei) mit einer
    Warnung. Zeilen darüber (Titel, Stand) werden übergangen."""
    bester, beste_anzahl = None, 0
    for i, zeile in enumerate(zeilen[:_pi().MAX_KOPF_SUCHE]):
        titel = [w for w in zeile if isinstance(w, str) and w.strip()]
        if sum(1 for w in titel if erkennen(w)) >= 2:
            return i, None
        if len(titel) >= 3 and len(titel) > beste_anzahl:
            bester, beste_anzahl = i, len(titel)
    if bester is None:
        raise Abgelehnt("In der Datei wurde keine Kopfzeile gefunden (etwa „Hersteller“, „Modell“, „Seriennummer“).")
    return bester, (f"Keine Kopfzeile mit bekannten Spaltentiteln gefunden – Zeile {bester + 1} wird als Kopfzeile "
                    "verwendet. Bitte die Zuordnung prüfen.")
