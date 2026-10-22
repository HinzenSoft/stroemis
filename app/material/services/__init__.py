"""Fachlogik des Moduls Material.

Die Regeln stehen hier, nicht in den Routen: Schnittstelle, Katalogimport und Tests sollen dieselben
Prüfungen durchlaufen. Eine verletzte Regel wird als Abgelehnt geworfen – mit Klartext und Statuscode;
routes.py macht daraus die übliche JSON-Antwort, der Import eine Fehlerzeile."""
import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Berlin")
# Wer handelt, steht mit Namen im Journal – nie mit der E-Mail. Ohne Namen gibt es keinen Modulzugang (rechte.zugang);
# für den theoretischen Rest steht dieser Platzhalter da.
OHNE_NAMEN = "(Konto ohne Namen)"


class Abgelehnt(Exception):
    """Eine Antwort mit Fehlertext und Statuscode. Bewusst KEIN ValueError: den fängt
    auth.eingabefehler_abfangen und ersetzte den Klartext durch „Unbrauchbare Eingabe.“."""

    def __init__(self, meldung, code=400):
        super().__init__(meldung)
        self.code = code


def jetzt():
    """Die Uhrzeit in Deutschland (mit Zeitzone) – für den Tageslauf der Erinnerungen: ab 6 Uhr deutscher Zeit, Herzschlag
    und Stichtag aus derselben Uhr. Tests stellen sie über services.datetime um (wie heute)."""
    return datetime.now(ZONE)


def heute():
    """Der Kalendertag in Deutschland, gegen den Fälligkeiten und Lebensdauer gemessen werden und der als Prüftag
    ins Protokoll kommt. Der Container läuft in UTC – zwischen Mitternacht und 1 bzw. 2 Uhr wäre sonst noch
    gestern. Eine eigene Funktion, damit Tests einen Stichtag setzen können, ohne die Uhr zu verstellen."""
    return jetzt().date()


# --- Eingaben lesen ------------------------------------------------------------------------------

def eingabe():
    """JSON-Body oder – bei Dateiuploads – die Formularfelder der Multipart-Anfrage. Dieselbe Regel für die Routen
    (routes._eingabe) und für rechte.requires_folder („eingabe:<feld>“): Beide lesen eine Kennung aus demselben Feld."""
    from flask import request

    from ...auth import json_body
    if request.files or (request.content_type or "").startswith("multipart/"):
        return request.form
    return json_body()


def text(d, feld, name, n=200, pflicht=False, einzeilig=True):
    """Ein Textfeld aus dem JSON: Zahl, Liste oder None gelten als leer; Steuerzeichen fliegen raus;
    zu lang ist ein Fehler statt stiller Kürzung – sonst stünde im Katalog etwas anderes als getippt."""
    v = d.get(feld)
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise Abgelehnt(f"„{name}“ muss Text sein.")
    v = v.strip()
    if einzeilig:
        v = re.sub(r"[\x00-\x1f\x7f]+", " ", v)
        v = re.sub(r"\s{2,}", " ", v)
    else:
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
    if pflicht and not v:
        raise Abgelehnt(f"„{name}“ fehlt.")
    if len(v) > n:
        raise Abgelehnt(f"„{name}“ ist zu lang (höchstens {n} Zeichen).")
    return v


def ganzzahl(wert, name, mini=None, maxi=None, leer_erlaubt=True):
    """Ganze Zahl oder None (leer). Wahrheitswerte und Kommazahlen sind Tippfehler, keine Zahlen."""
    if wert is None or wert == "":
        if leer_erlaubt:
            return None
        raise Abgelehnt(f"„{name}“ fehlt.")
    if isinstance(wert, bool):
        raise Abgelehnt(f"„{name}“ ist keine ganze Zahl.")
    if isinstance(wert, str):
        if not re.fullmatch(r"\s*-?\d{1,9}\s*", wert):
            raise Abgelehnt(f"„{name}“ ist keine ganze Zahl.")
        wert = int(wert)
    if isinstance(wert, float):
        if not wert.is_integer():
            raise Abgelehnt(f"„{name}“ ist keine ganze Zahl.")
        wert = int(wert)
    if not isinstance(wert, int):
        raise Abgelehnt(f"„{name}“ ist keine ganze Zahl.")
    if (mini is not None and wert < mini) or (maxi is not None and wert > maxi):
        raise Abgelehnt(f"„{name}“ muss zwischen {mini} und {maxi} liegen.")
    return wert


def dezimal(wert, name, mini=None, maxi=None, stellen=1, leer_erlaubt=True):
    """Kommazahl oder None (leer): „57,5“ wie „57.5“ (deutsches Komma oder Punkt, auch als Zahl), gerundet auf
    `stellen` Nachkommastellen; die Grenzen gelten nach dem Runden. Wahrheitswerte sind Tippfehler, keine Zahlen; NaN
    und Unendlich (JSON lässt „NaN“ und „Infinity“ zu) ebenso – NaN bestünde jeden Grenzvergleich. Nur ASCII-Ziffern."""
    if wert is None or wert == "":
        if leer_erlaubt:
            return None
        raise Abgelehnt(f"„{name}“ fehlt.")
    if isinstance(wert, bool):
        raise Abgelehnt(f"„{name}“ ist keine Zahl.")
    if isinstance(wert, str):
        s = wert.strip().replace(" ", "").replace(",", ".")
        if not re.fullmatch(r"-?[0-9]{1,9}(\.[0-9]{1,6})?", s):
            raise Abgelehnt(f"„{name}“ ist keine Zahl (etwa 57,5).")
        wert = float(s)
    if not isinstance(wert, (int, float)):
        raise Abgelehnt(f"„{name}“ ist keine Zahl.")
    try:
        wert = float(wert)
    except OverflowError:
        raise Abgelehnt(f"„{name}“ ist zu groß.")
    if not math.isfinite(wert):
        raise Abgelehnt(f"„{name}“ ist keine Zahl (etwa 57,5).")
    wert = round(wert, stellen)
    if (mini is not None and wert < mini) or (maxi is not None and wert > maxi):
        raise Abgelehnt(f"„{name}“ muss zwischen {dezimal_text(mini, stellen)} und {dezimal_text(maxi, stellen)} liegen.")
    return wert


def dezimal_text(wert, stellen=1):
    """57.5 → „57,5“ – mit genau `stellen` Nachkommastellen und deutschem Komma; None → ''."""
    if wert is None or wert == "":
        return ""
    return f"{float(wert):.{stellen}f}".replace(".", ",")


# Die Länge eines Artikels in Metern (Schritt 20): eine Nachkommastelle, über 0 und unter 10 000 (wie der CHECK).
LAENGE_MIN, LAENGE_MAX = 0.1, 9999.9


def laenge(wert, name="Länge (m)"):
    """Eine Artikellänge aus der Eingabe: Meter mit einer Nachkommastelle, Komma oder Punkt; leer → None."""
    return dezimal(wert, name, LAENGE_MIN, LAENGE_MAX, 1)


def laenge_text(meter, einheit=True):
    """57.5 → „57,5 m“ (Anzeige, Protokoll, Lebenslauf); ohne Einheit „57,5“ (Eingabefeld, CSV); None → ''."""
    if meter is None:
        return ""
    return dezimal_text(meter, 1) + (" m" if einheit else "")


def kennung(wert, name, leer_erlaubt=False):
    """Eine Datensatzkennung (positive ganze Zahl). „7“ und 7.0 gelten als 7 – im Dienst wie in der Rechteprüfung
    (rechte._bezug), damit beide dieselbe Kennung meinen; alles andere ist 400."""
    n = ganzzahl(wert, name, 1, 10 ** 12, leer_erlaubt=leer_erlaubt)
    return n


def datum(wert, name, leer_erlaubt=True):
    """'YYYY-MM-DD' oder None. Alles andere wird abgewiesen – ein Datumsfeld, das beliebigen Text
    aufnimmt, ließe sich weder sortieren noch für Fälligkeiten rechnen."""
    if wert in (None, ""):
        if leer_erlaubt:
            return None
        raise Abgelehnt(f"„{name}“ fehlt.")
    if isinstance(wert, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", wert.strip()):
        try:
            return date.fromisoformat(wert.strip()).isoformat()
        except ValueError:
            pass
    raise Abgelehnt(f"„{name}“ muss ein Datum im Format JJJJ-MM-TT sein.")


def monat_oder_datum(wert, name, leer_erlaubt=True):
    """Herstelldatum: Monat ('YYYY-MM') genügt – mehr steht auf den meisten Etiketten nicht."""
    if wert in (None, ""):
        if leer_erlaubt:
            return None
        raise Abgelehnt(f"„{name}“ fehlt.")
    if isinstance(wert, str):
        s = wert.strip()
        m = re.fullmatch(r"(\d{4})-(\d{2})", s)
        if m and 1 <= int(m.group(2)) <= 12 and int(m.group(1)) >= 1900:
            return s
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            try:
                return date.fromisoformat(s).isoformat()
            except ValueError:
                pass
    raise Abgelehnt(f"„{name}“ muss ein Monat (JJJJ-MM) oder ein Datum (JJJJ-MM-TT) sein.")


def erster_tag(monat_oder_tag):
    """'2020-03' → date(2020, 3, 1); '2020-03-17' → date(2020, 3, 17). Für Monatsangaben zählt der
    erste Tag: Die Lebensdauer endet damit eher zu früh als zu spät."""
    if not monat_oder_tag:
        return None
    if len(monat_oder_tag) == 7:
        return date.fromisoformat(monat_oder_tag + "-01")
    return date.fromisoformat(monat_oder_tag)


def wahr(d, feld, name):
    """Ja/Nein aus dem JSON: echte Wahrheitswerte, 0/1 und die üblichen Wörter."""
    v = d.get(feld)
    if v is None or isinstance(v, bool):
        return bool(v)
    if isinstance(v, int) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in ("true", "false", "1", "0", "ja", "nein", ""):
        return v.strip().lower() in ("true", "1", "ja")
    raise Abgelehnt(f"„{name}“ muss ja oder nein sein.")


def auswahl(wert, werte, name, leer_erlaubt=False):
    """Ein Wert aus einer festen Liste (Materialart, Ordnertyp …)."""
    if wert in (None, ""):
        if leer_erlaubt:
            return None
        raise Abgelehnt(f"„{name}“ fehlt.")
    if not isinstance(wert, str) or wert not in werte:
        raise Abgelehnt(f"„{name}“ ist keiner der erlaubten Werte ({', '.join(werte)}).")
    return wert


def antwort_privat(resp):
    """Personenbezogene Daten (Prüfer, Urkundennummern): nie in einen Zwischenspeicher – für Export, Lebenslauf und
    Jahresbericht (routes_export, routes_bericht)."""
    resp.cache_control.public = None
    resp.cache_control.max_age = None
    resp.cache_control.private = True
    resp.cache_control.no_store = True
    return resp


def akteur():
    """Kennung und Anzeigename dessen, der gerade handelt – für created_by und *_name-Felder. Nur der Name, kein
    Rückfall auf die E-Mail (siehe OHNE_NAMEN). Ohne Anfrage (Katalogimport auf der Kommandozeile) gilt der Name aus
    g.mat_akteur."""
    from flask import g, has_request_context

    from ...auth import current_user
    u = current_user() if has_request_context() else None
    if u:
        return u["id"], (u["name"] or "").strip() or OHNE_NAMEN
    return None, g.get("mat_akteur") or "System"
