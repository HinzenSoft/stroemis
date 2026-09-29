"""Excel-Import für den Prüfungsbereich: liest eine Teilnehmerliste (.xlsx) und macht daraus
Teilnehmende, Ausbilder, Voraussetzungen und Lehrgangsdaten – reines Python ohne Flask und
ohne Datenbank, damit sich jede Regel einzeln prüfen lässt.

Die Dateien kommen aus dem Seminarsystem der DLRG und sehen immer ähnlich aus: oben ein
Kopfbereich mit Paaren „Nr.“/„Titel“/„Zeitraum“/„Ort“ (Wert über mehrere verbundene Zellen),
darunter eine Leerzeile, dann die Kopfzeile der Tabelle und die Teilnehmenden. Weil aber auch
von Hand gebaute Listen hochgeladen werden, verlässt sich nichts auf feste Zeilen- oder
Spaltennummern: Die Kopfzeile wird gesucht, die Spalten werden an ihrem Titel erkannt, und
alles Erkannte kann das Frontend über `zuordnung` noch korrigieren.

Das Modul liefert bewusst nur Rohdaten (Dicts und Listen). Der Abgleich mit der Datenbank
(„vorhanden“) und das Schreiben der Tabellen passieren in api_pruefungen.py.
"""
import io
import re
import warnings
from datetime import date, datetime, timedelta

import openpyxl
from openpyxl.utils import get_column_letter


class ImportFehler(ValueError):
    """Meldung, die dem Nutzer gezeigt werden darf (falscher Dateityp, keine Kopfzeile, unlesbar)."""


ZUORDNUNGEN = ("vorname", "name", "geburtsdatum", "gliederung", "email", "rolle", "bemerkung",
               "extra", "voraussetzung", "ignorieren")

# Stammdaten-Felder, die je Datei nur einmal vorkommen dürfen – eine zweite Spalte mit gleicher
# Zuordnung würde die erste stumm überschreiben; sie wird deshalb zu „extra“ zurückgestuft.
STAMMDATEN = ("vorname", "name", "geburtsdatum", "gliederung", "email", "rolle", "bemerkung")

# Wörter, die in einer Voraussetzungsspalte „erfüllt“ bedeuten …
JA_WOERTER = frozenset(["ja", "j", "x", "✓", "✔", "☑", "wahr", "true", "yes", "y", "1", "ok",
                        "erfüllt", "erfuellt", "vorhanden", "liegt vor", "bestanden"])
# … und die, die „nicht erfüllt“ bedeuten. Beide zusammen entscheiden, ob eine Spalte überhaupt
# boolesch ist; für ist_erfuellt() zählt nur die Ja-Liste (alles andere ist nicht erfüllt).
NEIN_WOERTER = frozenset(["nein", "n", "-", "–", "—", "falsch", "false", "no", "0", "offen",
                          "fehlt", "leer", "✗", "✘", "☐", "nicht erfüllt", "nicht erfuellt", "nicht vorhanden"])

MAX_KOPF_SUCHE = 40          # so weit unten wird die Kopfzeile höchstens gesucht
MIN_TEXTZELLEN_KOPF = 3      # weniger Titel ist keine Tabelle

_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?\s*(?:uhr)?$", re.I)
_RE_DE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*(?:uhr)?$", re.I)
# Für den Zeitraum im Kopfbereich: alle Daten irgendwo im Text („04.12.2026 18:00 Uhr bis 13.12.2026 …“).
_RE_DATUM_IM_TEXT = re.compile(r"(?<!\d)(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\.\d{1,2}\.\d{4}|\d{1,2}\.\d{1,2}\.\d{2}(?!\d))(?!\d)")


# --- Kleine, reine Helfer -----------------------------------------------------------------

def normalisiert(text):
    """klein, Leerraum auf ein Leerzeichen, Zeilenumbrüche weg, Rand getrimmt – für Vergleiche
    von Namen und Titeln. „Nachname\\n(laut Ausweis)“ und „nachname (laut ausweis)“ sind gleich."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def schluessel(vorname, name, geburtsdatum):
    """(normalisiert(vorname), normalisiert(name), geburtsdatum or None) – der Vergleichsschlüssel
    eines Teilnehmenden. Ob zwei Schlüssel zusammenpassen, entscheidet passt()."""
    return (normalisiert(vorname), normalisiert(name), geburtsdatum or None)


def passt(a, b):
    """Zwei Schlüssel passen, wenn die Namen gleich sind und die Geburtsdaten gleich sind ODER eines
    fehlt. Ein fehlendes Datum ist ein Platzhalter: Eine Liste ohne Geburtsdaten darf einen TN
    nicht als Fremden anlegen, nur weil die erste Liste eines hatte."""
    if a[0] != b[0] or a[1] != b[1]:
        return False
    return a[2] is None or b[2] is None or a[2] == b[2]


def _datum_text(j, m, t):
    """Jahr/Monat/Tag → 'YYYY-MM-DD' – oder None, wenn es den Tag nicht gibt (31.02.)."""
    try:
        return date(int(j), int(m), int(t)).isoformat()
    except ValueError:
        return None


def _excel_serie(zahl):
    """Excel speichert Daten als Tage seit dem 30.12.1899. Erst ab 366 (Jahr 1901) gilt eine Zahl
    als Datum – ein Alter wie 17 oder 45 wäre sonst ein Tag im Januar 1900."""
    if isinstance(zahl, bool) or not isinstance(zahl, (int, float)):
        return None
    if not 366 <= zahl <= 2958465:            # 2958465 = 31.12.9999
        return None
    return (datetime(1899, 12, 30) + timedelta(days=float(zahl))).date().isoformat()


def datum_lesen(wert, excel_zahl=False):
    """datetime/date/Text -> 'YYYY-MM-DD' oder None. Texte: „yyyy-mm-dd[ hh:mm:ss]“, „dd.mm.yyyy“,
    „dd.mm.yy“ (jeweils mit oder ohne Uhrzeit). Zweistellige Jahre wie strptime: 69–99 → 19xx,
    00–68 → 20xx. Mit excel_zahl=True wird auch eine Zahl als Excel-Seriennummer gelesen – das
    ist nur in Spalten sinnvoll, die ausdrücklich ein Datum enthalten."""
    if isinstance(wert, datetime):
        return wert.date().isoformat()
    if isinstance(wert, date):
        return wert.isoformat()
    if isinstance(wert, (int, float)) and not isinstance(wert, bool):
        return _excel_serie(wert) if excel_zahl else None
    if not isinstance(wert, str):
        return None
    text = wert.strip()
    m = _RE_ISO.match(text)
    if m:
        return _datum_text(m.group(1), m.group(2), m.group(3))
    m = _RE_DE.match(text)
    if m:
        jahr = m.group(3)
        if len(jahr) == 2:
            jahr = 2000 + int(jahr) if int(jahr) <= 68 else 1900 + int(jahr)
        return _datum_text(jahr, m.group(2), m.group(1))
    return None


def ist_erfuellt(wert):
    """Ein Haken in einer Voraussetzungsspalte: Ja-Wörter, 1/True oder ein Datum (wann der Nachweis
    vorlag). Alles andere – auch leer – ist nicht erfüllt."""
    if wert is None:
        return False
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (datetime, date)):
        return True
    if isinstance(wert, (int, float)):
        return wert == 1
    text = normalisiert(wert)
    if not text:
        return False
    if text in JA_WOERTER:
        return True
    return datum_lesen(text) is not None


def _ist_datum(wert):
    return isinstance(wert, (datetime, date)) or (isinstance(wert, str) and datum_lesen(wert) is not None)


def _ist_boolesch(wert):
    """Sieht der Zellwert nach ja/nein aus? Entscheidet, ob eine unbekannte Spalte eine
    Voraussetzung ist (≥ 80 % solcher Werte) oder eine freie Angabe."""
    if isinstance(wert, bool) or isinstance(wert, (datetime, date)):
        return True
    if isinstance(wert, (int, float)):
        return wert in (0, 1)
    text = normalisiert(wert)
    return text in JA_WOERTER or text in NEIN_WOERTER or datum_lesen(text) is not None


def zeitraum_lesen(text):
    """'04.12.2026 18:00 Uhr bis 13.12.2026 19:00 Uhr' -> ('2026-12-04', '2026-12-13').
    Erstes Datum im Text = von, letztes = bis; ein einzelnes Datum gilt für beide. Ein echtes
    Datumsobjekt (die Zelle war als Datum formatiert) ebenso."""
    if isinstance(text, (datetime, date)):
        d = datum_lesen(text)
        return (d, d)
    if not isinstance(text, str):
        return (None, None)
    daten = [datum_lesen(t) for t in _RE_DATUM_IM_TEXT.findall(text)]
    daten = [d for d in daten if d]
    if not daten:
        return (None, None)
    return (daten[0], daten[-1])


def als_text(wert):
    """Zellwert als Anzeigetext: None → '', Datum → ISO, 3.0 → '3', True → 'ja'. Für Beispiele,
    Zusatzangaben (extra) und Kopfwerte – nie für Vergleiche."""
    if wert is None:
        return ""
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    if isinstance(wert, datetime):
        if wert.hour == 0 and wert.minute == 0 and wert.second == 0:
            return wert.date().isoformat()
        return wert.strftime("%Y-%m-%d %H:%M")
    if isinstance(wert, date):
        return wert.isoformat()
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    return re.sub(r"\s+", " ", str(wert)).strip()


def _leer(wert):
    """Leer ist None, "" und alles, was nur aus Leerraum besteht – Excel-Exporte füllen gern
    „leere“ Zellen mit "" und heben damit max_row an."""
    return wert is None or (isinstance(wert, str) and not wert.strip())


def _ist_textzelle(wert):
    return isinstance(wert, str) and bool(wert.strip())


# --- Datei öffnen -------------------------------------------------------------------------

def _arbeitsblatt(datei, dateiname):
    """Liest die Datei und liefert das erste Arbeitsblatt mit Inhalt als Liste von Zeilen
    (jede Zeile eine Liste der Zellwerte). Alles, was hier schiefgeht, ist ein Fehler der Datei,
    nicht des Servers – deshalb ImportFehler mit Klartext."""
    if dateiname and not str(dateiname).lower().endswith(".xlsx"):
        raise ImportFehler("Bitte eine Excel-Datei im Format .xlsx hochladen.")
    if isinstance(datei, (bytes, bytearray)):
        roh = bytes(datei)
    else:
        try:
            if hasattr(datei, "seek"):
                datei.seek(0)
            roh = datei.read()
        except (OSError, ValueError, AttributeError) as e:
            raise ImportFehler("Die Datei konnte nicht gelesen werden.") from e
    if not roh:
        raise ImportFehler("Die Datei ist leer.")
    # Eine .xlsx ist ein ZIP-Archiv – alte .xls-Dateien, CSV oder Umbenanntes scheitern hier
    # mit einer verständlichen Meldung statt mit einer openpyxl-Ausnahme.
    if not roh.startswith(b"PK"):
        raise ImportFehler("Das ist keine .xlsx-Datei. Bitte die Liste in Excel als „Excel-Arbeitsmappe (.xlsx)“ speichern.")
    try:
        # openpyxl warnt bei Kopf-/Fußzeilen, die es nicht versteht (Seminarsystem-Exporte) –
        # für den Import ohne Belang, soll aber nicht das Protokoll füllen.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # read_only=False (Standard), damit verbundene Zellen wie in Excel erscheinen:
            # Wert oben links, Rest None. data_only=True liefert Formelergebnisse statt Formeln.
            wb = openpyxl.load_workbook(io.BytesIO(roh), data_only=True)
    except Exception as e:                                   # noqa: BLE001 – jede Leseausnahme ist ein Dateiproblem
        raise ImportFehler("Die Excel-Datei konnte nicht gelesen werden (beschädigt oder kein .xlsx).") from e
    for ws in wb.worksheets:
        zeilen = [list(z) for z in ws.iter_rows(values_only=True)]
        if any(not _leer(w) for z in zeilen for w in z):
            return zeilen
    raise ImportFehler("Die Excel-Datei enthält keine Daten.")


# --- Kopfzeile und Kopfbereich ------------------------------------------------------------

def _kopfzeile_finden(zeilen):
    """Index (0-basiert) der Kopfzeile: die erste Zeile mit ≥ 3 Textzellen, die einen Namens-Titel
    trägt. Fehlt so eine, nimmt der Import die Zeile mit den meisten Textzellen und warnt –
    besser eine korrigierbare Vorschau als gar keine. Liefert (index, warnung|None)."""
    bester, beste_anzahl = None, 0
    for i, zeile in enumerate(zeilen[:MAX_KOPF_SUCHE]):
        titel = [normalisiert(w) for w in zeile if _ist_textzelle(w)]
        # Eine Liste aus nur „Vorname“ und „Nachname“ ist eine Liste – zwei Titel reichen, wenn
        # einer davon ein Namens-Titel ist. Für den Rückfall ohne Namensspalte bleibt es bei drei.
        if len(titel) >= 2 and any(t in ("vorname", "nachname", "name") or t.startswith(("vorname", "nachname", "name"))
                                   or "nachname" in t or "familienname" in t for t in titel):
            return i, None
        if len(titel) < MIN_TEXTZELLEN_KOPF:
            continue
        if len(titel) > beste_anzahl:
            bester, beste_anzahl = i, len(titel)
    if bester is None:
        raise ImportFehler("In der Datei wurde keine Kopfzeile mit Spaltentiteln (z. B. Vorname, Nachname) gefunden.")
    return bester, (f"Keine Kopfzeile mit Namensspalte gefunden – Zeile {bester + 1} mit den meisten "
                    f"Spaltentiteln wird als Kopfzeile verwendet. Bitte die Zuordnung prüfen.")


def _kopfdaten_lesen(zeilen, kopf_index, warnungen):
    """Die Paare über der Kopfzeile: Spalte A ist der Bezeichner, die nächste gefüllte Zelle rechts
    der Wert (bei verbundenen Zellen B:G steht er in B). Unbekannte Bezeichner („Stand“) bleiben
    unbeachtet."""
    lehrgang = {"titel": None, "nummer": None, "datum_von": None, "datum_bis": None, "ort": None}
    for zeile in zeilen[:kopf_index]:
        if not zeile or _leer(zeile[0]):
            continue
        bez = normalisiert(zeile[0]).rstrip(":.").strip()
        wert = next((w for w in zeile[1:] if not _leer(w)), None)
        if wert is None:
            continue
        if bez in ("nr", "nummer", "lehrgangsnummer", "lehrgangs-nr", "lehrgangsnr", "seminarnummer", "seminar-nr"):
            lehrgang["nummer"] = lehrgang["nummer"] or als_text(wert)
        elif bez in ("titel", "lehrgang", "bezeichnung", "lehrgangstitel", "lehrgangsbezeichnung", "seminar", "veranstaltung"):
            lehrgang["titel"] = lehrgang["titel"] or als_text(wert)
        elif bez in ("zeitraum", "datum", "termin", "termine", "zeit"):
            von, bis = zeitraum_lesen(wert)
            if von is None:
                warnungen.append(f"Der Zeitraum „{als_text(wert)}“ im Kopfbereich konnte nicht als Datum gelesen werden.")
            elif lehrgang["datum_von"] is None:
                lehrgang["datum_von"], lehrgang["datum_bis"] = von, bis
        elif bez in ("ort", "veranstaltungsort", "lehrgangsort"):
            lehrgang["ort"] = lehrgang["ort"] or als_text(wert)
    return lehrgang


# --- Spalten erkennen ---------------------------------------------------------------------

def _beginnt_mit(t, *synonyme):
    """Titel ist genau das Synonym oder beginnt damit und danach kommt kein Buchstabe mehr
    („e-mail-adresse“, „name (laut ausweis)“ – aber nicht „benutzername“)."""
    for s in synonyme:
        if t == s or (t.startswith(s) and not t[len(s)].isalnum()):
            return True
    return False


def _mehrheitlich(werte, pruefung):
    """≥ 80 % der gefüllten Werte bestehen die Prüfung – und es gibt überhaupt welche."""
    gefuellt = [w for w in werte if not _leer(w)]
    return bool(gefuellt) and sum(1 for w in gefuellt if pruefung(w)) >= 0.8 * len(gefuellt)


def _zuordnung_erkennen(titel, werte):
    """Automatische Zuordnung einer Spalte aus ihrem Titel; unbekannte Titel werden an den Werten
    erkannt (ja/nein → Voraussetzung, sonst freie Angabe). Stammdaten werden zuerst nur am
    Anfang des Titels erkannt: „Bestätigung Gliederung“ oder „… bei der Heimatgliederung
    angefragt“ sind Voraussetzungen mit ja/nein, keine Gliederungsspalten. Erst wenn die Werte
    nicht boolesch sind, darf ein Synonym mitten im Titel entscheiden („DLRG-Gliederung“)."""
    t = normalisiert(titel)
    if not t:
        return "ignorieren"
    if _beginnt_mit(t, "vorname", "vornamen", "rufname"):
        return "vorname"
    if _beginnt_mit(t, "nachname", "nachnamen", "familienname", "zuname") or (_beginnt_mit(t, "name") and "vor" not in t):
        return "name"
    if _beginnt_mit(t, "geburtsdatum", "geburtstag", "geb.", "geb-", "geb", "geburt"):
        return "geburtsdatum"
    if t == "alter":
        # Das Seminarsystem schreibt in „Alter“ das Geburtsdatum als Text. Stehen dort aber
        # Zahlen (17, 45), bleibt es eine freie Angabe – eine Zahl ist hier kein Excel-Datum.
        return "geburtsdatum" if _mehrheitlich(werte, lambda w: datum_lesen(w) is not None) else "extra"
    if _beginnt_mit(t, "gliederung", "heimatgliederung", "ortsgruppe", "og", "verein", "ortsverband"):
        return "gliederung"
    if _beginnt_mit(t, "e-mail", "email", "mail", "e-mail-adresse", "mailadresse"):
        return "email"
    if _beginnt_mit(t, "rolle", "funktion"):
        return "rolle"
    if _beginnt_mit(t, "bemerkung", "bemerkungen", "hinweis", "hinweise", "notiz", "notizen", "anmerkung", "anmerkungen"):
        return "bemerkung"
    # Eine Spalte, in der bei allen ein Datum steht und deren Titel nach Zeitpunkt klingt
    # („Anmeldung“, „Stand“, „Eintritt“), ist eine Angabe, keine Voraussetzung – sonst bekäme
    # jede Person dafür einen Haken. Ein Nachweisdatum („DRSA Silber“) steht dagegen nur bei
    # denen, die ihn haben, und bleibt eine Voraussetzung.
    gefuellt = [w for w in werte if not _leer(w)]
    if gefuellt and all(_ist_datum(w) for w in gefuellt) and any(
            k in t for k in ("datum", "anmeld", "stand", "eintritt", "geändert", "geaendert", "erstellt", "aktualisiert", "zeitpunkt")):
        return "extra"
    if _mehrheitlich(werte, _ist_boolesch):
        return "voraussetzung"
    if "nachname" in t or "familienname" in t:
        return "name"
    if "geburtsdatum" in t or "geburtstag" in t:
        return "geburtsdatum"
    if "gliederung" in t or "ortsgruppe" in t:
        return "gliederung"
    if "mail" in t:
        return "email"
    if "bemerkung" in t or "hinweis" in t or "notiz" in t:
        return "bemerkung"
    return "extra"


def _ueberschreibungen(zuordnung, warnungen):
    """Die vom Frontend mitgeschickte Zuordnung {index: zuordnung} – Schlüssel als int oder str
    (JSON kennt nur Text-Schlüssel). Unbrauchbares wird gemeldet und übergangen, nicht zum Fehler."""
    out = {}
    if not isinstance(zuordnung, dict):
        return out
    for k, v in zuordnung.items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            warnungen.append(f"Zuordnung für „{k}“ ignoriert: kein Spaltenindex.")
            continue
        if v not in ZUORDNUNGEN:
            warnungen.append(f"Unbekannte Zuordnung „{v}“ für Spalte {idx + 1} ignoriert.")
            continue
        out[idx] = v
    return out


def _spalten_bestimmen(kopf, daten, zuordnung, warnungen):
    """Liste der Spalten mit Titel, Zuordnung und Beispielwerten. Spalten ohne Titel werden nur
    aufgeführt, wenn sie Daten enthalten (dann als „ignorieren“, korrigierbar); leere Spalten ohne
    Titel fehlen ganz. Doppelte Stammdaten-Zuordnungen: die erste Spalte gewinnt."""
    vorgaben = _ueberschreibungen(zuordnung, warnungen)
    breite = max([len(kopf)] + [len(z) for z in daten])
    spalten = []
    vergeben = set()
    for idx in range(breite):
        titel_roh = kopf[idx] if idx < len(kopf) else None
        titel = als_text(titel_roh) if not _leer(titel_roh) else ""
        werte = [z[idx] for z in daten if idx < len(z) and not _leer(z[idx])]
        if not titel and not werte:
            continue
        if idx in vorgaben:
            zu = vorgaben[idx]
        elif not titel:
            zu = "ignorieren"
        else:
            zu = _zuordnung_erkennen(titel, werte)
        if zu in STAMMDATEN:
            if zu in vergeben:
                warnungen.append(f"Spalte „{titel or get_column_letter(idx + 1)}“ ist ein zweites Mal als „{zu}“ "
                                 f"zugeordnet – sie wird als weitere Angabe übernommen.")
                zu = "extra"
            else:
                vergeben.add(zu)
        beispiele = []
        for w in werte:
            text = als_text(w)
            if text and text not in beispiele:
                beispiele.append(text)
            if len(beispiele) == 3:
                break
        spalten.append({"index": idx, "titel": titel, "zuordnung": zu, "beispiele": beispiele})
    return spalten


# --- Zeilen zu Teilnehmenden ----------------------------------------------------------------

def _zelle(zeile, idx):
    return zeile[idx] if idx is not None and idx < len(zeile) else None


def _text(zeile, idx):
    return als_text(_zelle(zeile, idx))


AUSBILDER_WOERTER = ("lehrgangsleit", "leitung", "leiter", "ausbild", "referent", "prüfer", "pruefer", "dozent",
                     "trainer", "helfer", "lehrkraft", "instruktor", "multiplikator")
TEILNEHMER_WOERTER = ("teilnehm", "tn", "teiln", "teiln.", "gast", "kandidat", "prüfling", "pruefling", "schüler", "schueler")


def _ist_ausbilder_rolle(rolle, nr, warnungen):
    """Zeilen mit Ausbilderrolle werden nicht Teilnehmende. „TN“ und „Teiln.“ sind die üblichen
    Abkürzungen für Teilnehmende; eine unbekannte Rolle bleibt Teilnehmer, mit Hinweis – lieber
    eine Person zu viel in der Liste als eine Prüfung, die keiner ablegen kann."""
    t = normalisiert(rolle)
    if not t or any(w in t for w in TEILNEHMER_WOERTER):
        return False
    if any(w in t for w in AUSBILDER_WOERTER):
        return True
    warnungen.append(f"Zeile {nr}: Rolle „{rolle}“ ist unbekannt – als Teilnehmende:r übernommen.")
    return False


def _namen_trennen(vorname, name):
    """Steht der ganze Name in einer Spalte („Max Mustermann“) und ist die andere leer, wird
    getrennt: letztes Wort = Nachname, Rest = Vorname. Doppelnamen mit Bindestrich bleiben zusammen."""
    voll = name if name and not vorname else vorname if vorname and not name else None
    if voll and "," in voll:
        # „Mustermann, Max“ – das Komma ist eindeutig: davor der Nachname, dahinter der Vorname.
        nach, vor = (t.strip() for t in voll.split(",", 1))
        return vor, nach
    if name and not vorname and len(name.split()) >= 2:
        teile = name.split()
        return " ".join(teile[:-1]), teile[-1]
    if vorname and not name and len(vorname.split()) >= 2:
        teile = vorname.split()
        return " ".join(teile[:-1]), teile[-1]
    return vorname, name


def analysieren(datei, zuordnung=None, dateiname=""):
    """datei: Dateiobjekt (z. B. werkzeug FileStorage.stream oder BytesIO) oder bytes.
    zuordnung: optional {int|str(index): zuordnung} – überschreibt die automatische Erkennung je Spalte.
    Liefert:
    {"kopfzeile": int,                                    # Excel-Zeilennummer der Kopfzeile (1-basiert)
     "spalten": [{"index": int, "titel": str, "zuordnung": str, "beispiele": [str, …bis 3]}],   # index = 0-basierte Spaltennummer
     "lehrgang": {"titel": str|None, "nummer": str|None, "datum_von": str|None, "datum_bis": str|None, "ort": str|None},
     "teilnehmer": [{"vorname", "name", "geburtsdatum", "gliederung", "email", "bemerkung", "extra": {titel: text},
                     "voraussetzungen": {"<index>": bool},   # Schlüssel = str(Spaltenindex) der Voraussetzungsspalte
                     "zeile": int}],
     "ausbilder": [{"name": str, "funktion": str, "ist_leitung": bool, "zeile": int}],
     "voraussetzungen": [{"spaltenindex": int, "bezeichnung": str}],   # Reihenfolge wie in der Datei; Titel mit Umbruch → Leerzeichen
     "warnungen": [str]}
    Wirft ImportFehler bei unlesbarer Datei / keiner Kopfzeile / keiner Datenzeile."""
    warnungen = []
    zeilen = _arbeitsblatt(datei, dateiname)
    kopf_index, kopf_warnung = _kopfzeile_finden(zeilen)
    if kopf_warnung:
        warnungen.append(kopf_warnung)
    lehrgang = _kopfdaten_lesen(zeilen, kopf_index, warnungen)
    kopf = zeilen[kopf_index]
    daten = zeilen[kopf_index + 1:]
    spalten = _spalten_bestimmen(kopf, daten, zuordnung, warnungen)

    # Nachschlagetabellen aus der Zuordnung: Stammdaten-Feld → Spaltenindex, dazu die Listen
    # der Voraussetzungs- und Extra-Spalten in Dateireihenfolge.
    feld_idx = {s["zuordnung"]: s["index"] for s in spalten if s["zuordnung"] in STAMMDATEN}
    vor_spalten = [s for s in spalten if s["zuordnung"] == "voraussetzung"]
    extra_spalten = [s for s in spalten if s["zuordnung"] == "extra"]
    voraussetzungen = [{"spaltenindex": s["index"], "bezeichnung": s["titel"] or f"Spalte {get_column_letter(s['index'] + 1)}"}
                       for s in vor_spalten]
    rolle_titel = next((s["titel"] for s in spalten if s["zuordnung"] == "rolle"), "Rolle")

    teilnehmer, ausbilder = [], []
    schluessel_gesehen = []          # (schluessel, Excel-Zeile) – für die Duplikatwarnung
    ausbilder_gesehen = {}
    leerzeilen = 0
    ohne_namen = []
    for offset, zeile in enumerate(daten):
        nr = kopf_index + 1 + offset + 1           # Excel-Zeilennummer (1-basiert)
        if all(_leer(w) for w in zeile):
            leerzeilen += 1
            continue
        vorname = _text(zeile, feld_idx.get("vorname"))
        name = _text(zeile, feld_idx.get("name"))
        vorname, name = _namen_trennen(vorname, name)
        if not vorname and not name:
            ohne_namen.append(nr)
            continue
        if not name:
            # Ohne Nachnamen entsteht kein Teilnehmender (Pflichtfeld). Fehlt die Spalte ganz,
            # genügt ein Hinweis am Ende statt einer Zeile je Person.
            if "name" in feld_idx:
                warnungen.append(f"Zeile {nr}: „{vorname}“ hat keinen Nachnamen – übersprungen.")
            continue

        geburtsdatum = None
        geb_roh = _zelle(zeile, feld_idx.get("geburtsdatum"))
        if not _leer(geb_roh):
            geburtsdatum = datum_lesen(geb_roh, excel_zahl=True)
            if geburtsdatum is None:
                warnungen.append(f"Zeile {nr}: Geburtsdatum „{als_text(geb_roh)}“ nicht lesbar – bleibt leer.")

        extra = {}
        for s in extra_spalten:
            text = _text(zeile, s["index"])
            if text:
                extra[s["titel"] or f"Spalte {get_column_letter(s['index'] + 1)}"] = text

        rolle = _text(zeile, feld_idx.get("rolle"))
        if rolle:
            # Der Rollentext bleibt als Zusatzangabe sichtbar – auch bei Teilnehmenden, damit
            # „Teilnehmender“ vs. „Gast“ o. Ä. später noch nachlesbar ist.
            extra[rolle_titel] = rolle
        voller_name = " ".join(t for t in (vorname, name) if t)
        if rolle and _ist_ausbilder_rolle(rolle, nr, warnungen):
            k = normalisiert(voller_name)
            if k in ausbilder_gesehen:
                warnungen.append(f"Zeile {nr}: „{voller_name}“ ({rolle}) steht schon in Zeile {ausbilder_gesehen[k]} – übersprungen.")
            else:
                ausbilder_gesehen[k] = nr
                ausbilder.append({"name": voller_name, "funktion": rolle, "ist_leitung": "leit" in normalisiert(rolle), "zeile": nr})
            continue

        k = schluessel(vorname, name, geburtsdatum)
        doppelt = next((z for ks, z in schluessel_gesehen if passt(ks, k)), None)
        if doppelt is not None:
            warnungen.append(f"Zeile {nr}: „{voller_name}“ kommt schon in Zeile {doppelt} vor – die zweite Zeile wird übersprungen.")
            continue
        schluessel_gesehen.append((k, nr))

        teilnehmer.append({
            "vorname": vorname,
            "name": name,
            "geburtsdatum": geburtsdatum,
            "gliederung": _text(zeile, feld_idx.get("gliederung")),
            "email": _text(zeile, feld_idx.get("email")),
            "bemerkung": _text(zeile, feld_idx.get("bemerkung")),
            "extra": extra,
            "voraussetzungen": {str(s["index"]): ist_erfuellt(_zelle(zeile, s["index"])) for s in vor_spalten},
            "zeile": nr,
        })

    if ohne_namen:
        if len(ohne_namen) == 1:
            warnungen.append(f"Zeile {ohne_namen[0]} hat weder Vor- noch Nachnamen und wurde übersprungen.")
        else:
            warnungen.append(f"{len(ohne_namen)} Zeilen ohne Vor- und Nachnamen übersprungen (Zeilen "
                             + ", ".join(str(z) for z in ohne_namen) + ").")
    if leerzeilen:
        warnungen.append("Eine leere Zeile übersprungen." if leerzeilen == 1 else f"{leerzeilen} leere Zeilen übersprungen.")
    if "name" not in feld_idx:
        # Die Spalten sind da, nur keine ist als Nachname erkannt („Teilnehmer“, „Person“) oder
        # zugeordnet. Das lässt sich in der Vorschau korrigieren – ein Fehler nähme dem Nutzer
        # diese Möglichkeit.
        warnungen.append("Keine Spalte für den Nachnamen zugeordnet – ohne Nachnamen werden keine Teilnehmenden "
                         "übernommen. Bitte in der Zuordnung eine Spalte auf „Nachname“ (und ggf. „Vorname“) setzen.")
    elif not teilnehmer and not ausbilder:
        raise ImportFehler("Unter der Kopfzeile stehen keine Teilnehmenden – die Datei enthält keine "
                           "Datenzeilen mit Namen. " + " ".join(warnungen))

    return {
        "kopfzeile": kopf_index + 1,
        "spalten": spalten,
        "lehrgang": lehrgang,
        "teilnehmer": teilnehmer,
        "ausbilder": ausbilder,
        "voraussetzungen": voraussetzungen,
        "warnungen": warnungen,
    }
