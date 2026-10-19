"""Bestandsimport (Phase 2 · Lieferung 3): Bestandslisten aus Excel oder CSV in einen Zielordner übernehmen – erst ein
Probelauf, dann „Übernehmen“; was nicht sicher passt, kommt in die Nacharbeit.

Ablauf und Regeln (Bauentwurf L3, Abschnitt 2):
  - Lesen: services/tabelle.py (Grenzen vor dem Laden, CSV gestreamt, xlsx über pruefungen_import).
  - Spalten: Synonyme mit Rangfolge (Modell vor Typ vor Bezeichnung), mehrere Spalten dürfen auf „Bemerkung“ zeigen
    („Größe: M“), Personenspalten lassen sich keinem Feld zuordnen. Die eigene Nacharbeits-CSV wird an der Spalte
    „Nacharbeit-Nr.“ erkannt.
  - Produkt: nie geraten – automatisch nur gleicher Dublettenschlüssel, gleiche Artikelnummer bei gleichem Hersteller
    oder Hersteller + Modellname (vor „|“) bei genau einem Produkt des Herstellers. Alles andere wird in der
    Nacharbeit zugeordnet.
  - Blockiert wird nur durch Pflicht- und Sicherheitswerte; Unlesbares ohne Wirkung wird Hinweis, der Originaltext
    kommt in die Bemerkung. Nichts wird erfunden.
  - Importierte Artikel stehen auf „neu“ (keine Prüfung im System); die Fälligkeit kommt aus „nächste Prüfung“ bzw.
    „zuletzt geprüft“ + Intervall, höchstens heute + Intervall – ohne beides ist die Eingangsprüfung sofort fällig.
  - Zeilen ohne Herstellerseriennummer bekommen eine Seriennummer vom System (STR-…) wie beim Anlegen von Hand
    (Entscheidung vom 19.10.2026, kein Haken). Gegen doppeltes Anlegen: dieselbe Datei in denselben Ordner ist zehn
    Minuten lang gesperrt, und die Nacharbeits-CSV erledigt ihre Zeilen über die „Nacharbeit-Nr.“.
  - Offene Nacharbeit verfällt nach FRIST_MONATE (einem Monat, Entscheidung vom 19.10.2026) – beim Start der App und
    in jeder Runde des Tageslaufs.
  - Anlegen nach denselben Regeln wie von Hand: bestand.artikel_plan (nur lesen) und bestand.artikel_schreiben.
  - Übernehmen schreibt in EINER Transaktion; Inventarnummern entstehen in Dateireihenfolge.
  - Fremde Dubletten (Seriennummer in einem Bereich, den das Konto nicht sieht) nennt der Bericht ohne Merkmale und
    schreibt dafür eine Zeile ins Protokoll der globalen Suche; Nummern, die die globale Suche nicht beantwortet (kurz
    oder in der Form einer Inventarnummer), legt der Import nie an – gleich, ob es sie anderswo gibt.

Rechte prüfen die Routen (routes_import.py): alles nur mit „verwalten“ am Zielordner. Zeilen der Nacharbeit gehören zu
genau einem Zielordner; eine fremde Kennung antwortet wie eine unbekannte (404). Texte aus der Datei (Spaltentitel,
Werte, Gründe) gehen als reiner Text hinaus – die Oberfläche setzt sie nur maskiert ein."""
import json
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from flask import g

from ... import db
from ..models import IMPORT_STATUS
from . import ZONE, Abgelehnt, akteur, heute, kennung
from . import bestand, export, globalprotokoll, globalsuche, journal, katalog, meldung, nummern, rechte, rueckruf
from . import tabelle
from .interval import lebensende, plus_monate, spaetestens, wirksam

MAX_BYTES = tabelle.MAX_BYTES
MAX_DATENZEILEN = 2000                 # = pruefungen_import.MAX_DATENZEILEN
WIEDERHOLUNG_MINUTEN = 10              # dieselbe Datei in denselben Ordner: so lange abgelehnt
FRIST_MONATE = 1                       # offene Nacharbeit verfällt nach so vielen Monaten (Entscheidung 19.10.2026)
FRIST_TEXT = ("Offene Zeilen der Nacharbeit verfallen einen Monat nach dem Import – danach sind sie verworfen und ihre "
              "Werte gelöscht.")
SEITE = 200                            # Zeilen der Nacharbeit je Seite
ERLEDIGT_MAX = 100
GRUPPEN_MAX = 100                      # Produktangaben (Karten) in der Nacharbeit
AUSWAHL_MAX = 2000                     # Zeilen je Aktion der Nacharbeit
BEMERKUNG_MAX = 4000
# Vor dem Speichern (und schon beim Lesen, damit „erneut prüfen“ dasselbe sieht wie der erste Lauf): je Feld gekürzt –
# die Feldgrenze plus Spielraum, damit der Grund „zu lang“ erkennbar bleibt.
LAENGEN = {"bemerkung": 4100, "seriennummer": 100}
LAENGE_SONST = 200

# Ein Import je Arbeitsprozess gleichzeitig (Gunicorn: 2 Prozesse × 4 Threads) – Probelauf, Übernehmen, erneut prüfen.
SPERRE = threading.BoundedSemaphore(1)
SPERRE_WARTEN = 10                     # Sekunden
BELEGT = "Gerade läuft ein anderer Bestandsimport – bitte in einem Moment noch einmal."

ZEILE_FEHLT = "Zeile nicht gefunden."
SCHON_ERLEDIGT = "Mindestens eine Zeile ist schon erledigt. Bitte neu laden."
NUR_SYSTEM = "In „Gesperrt“ und „Ausgesondert“ wird nichts importiert."
BAUM_GEAENDERT = "Der Ordnerbaum hat sich geändert – bitte den Probelauf wiederholen."
NACHARBEIT_GEAENDERT = "Die Nacharbeit wurde inzwischen bearbeitet – bitte den Probelauf wiederholen."
NICHTS = "Nichts zu übernehmen – alles steht schon im Bestand oder ist erledigt."
FEHLT_ZUORDNUNG = "Ordne mindestens Hersteller und Modell (oder Artikelnummer) zu."
DEMO_PRODUKT = "Ein DEMO-Produkt passt nur in einen DEMO-Ordner."
NEUBESCHRIFTEN = ("Alte Inventarnummern stehen in der Bemerkung und sind nicht suchbar – die Artikel bitte neu "
                  "beschriften (Liste: „Export“ im Ordner).")

# --- Felder und Spalten ------------------------------------------------------------------------------------------

# Reihenfolge der Auswahlliste; die Schlüssel sind auch die Schlüssel von mat_import_row.values_json.
FELDER = (("hersteller", "Hersteller"), ("modell", "Modell"), ("artikelnummer", "Artikelnummer"),
          ("seriennummer", "Seriennummer"), ("inventarnummer", "Bisherige Inventarnummer"),
          ("ordner", "Ordner (Pfad unter dem Zielordner)"), ("hergestellt", "Herstelldatum"), ("gekauft", "Kaufdatum"),
          ("erstgebrauch", "Erstgebrauch"), ("zuletzt_geprueft", "Zuletzt geprüft"),
          ("naechste_pruefung", "Nächste Prüfung"), ("intervall", "Prüfintervall (Monate)"),
          ("lebensende", "Lebensende"), ("anzahl", "Anzahl"), ("bemerkung", "Bemerkung (mehrfach)"),
          ("ignorieren", "– ignorieren –"))
FELD_TEXT = dict(FELDER)

# Synonyme der Spaltentitel – verglichen nach pi.normalisiert und ohne Umlaute („Prüfdatum“ = „Pruefdatum“), mit
# pi._beginnt_mit („genau das Synonym oder beginnt damit, danach kein Buchstabe und keine Ziffer“). Geprüft wird in
# dieser Reihenfolge: Personen → Vorrang „ignorieren“ → Seriennummer → Hersteller → Artikelnummer → Modell (mit Rang)
# → die übrigen Felder. „hersteller-seriennummer“ begänne sonst mit „hersteller“, „artikel-nr“ mit „artikel“.
PERSONEN = ("vorname", "nachname", "besitzer", "ausgegeben an", "ausgegeben", "zugeordnet an", "in prüfung bei",
            "nutzer", "benutzer", "person", "träger", "e-mail", "email", "mail", "telefon", "tel", "handy", "mobil",
            "geburtsdatum", "adresse", "anschrift")
# „Hersteller-Nr.“: Seriennummer oder Artikelnummer? Nicht raten. „Grund“ und „Zeile“: Spalten der Nacharbeits-CSV.
VORRANG_IGNORIEREN = ("hersteller-nr", "hersteller nr", "herstellernummer", "lfd. nr", "lfd nr", "lfd.-nr", "nr",
                      "status", "kategorie", "grund", "zeile")
SERIENNUMMER = ("seriennummer", "serien-nr", "seriennr", "serien nr", "s/n", "sn", "serial", "serial number",
                "hersteller-seriennummer", "herstellerseriennummer", "hersteller seriennummer", "seriennummer hersteller",
                "fabriknummer", "fabrik-nr")
HERSTELLER = ("hersteller", "marke", "fabrikat", "manufacturer")
ARTIKELNUMMER = ("artikelnummer", "artikel-nr", "artikelnr", "artikel nr", "art.-nr", "art.nr", "art-nr", "art. nr",
                 "artnr", "referenz", "ref", "article number")
MODELL = ((1, ("modell", "model", "modellbezeichnung")), (2, ("typ", "type", "typbezeichnung")),
          (3, ("bezeichnung", "produkt", "produktbezeichnung", "artikel", "artikelbezeichnung", "gegenstand")))
BEMERKUNG_WERT = ("bemerkung", "bemerkungen", "notiz", "hinweis", "anmerkung", "kommentar")
BEMERKUNG_TITEL = ("größe", "groesse", "farbe", "länge", "standort", "lagerort")
UEBRIGE = (
    ("inventarnummer", ("inventarnummer", "inventar-nr", "inventarnr", "inv.-nr", "inv-nr", "inv. nr", "inv nr",
                        "inventar")),
    ("ordner", ("ordner", "unterordner")),
    ("hergestellt", ("hergestellt", "herstelldatum", "herstellungsdatum", "herstellung", "herstellungsjahr",
                     "produktionsdatum", "baujahr")),
    ("gekauft", ("gekauft", "kaufdatum", "kauf", "anschaffung", "anschaffungsdatum", "beschafft", "beschaffung",
                 "lieferdatum")),
    ("erstgebrauch", ("erstgebrauch", "erster gebrauch", "erstbenutzung", "erste verwendung", "in gebrauch seit",
                      "inbetriebnahme", "in betrieb seit")),
    ("zuletzt_geprueft", ("zuletzt geprüft", "letzte prüfung", "geprüft am", "prüfdatum", "letzte sachkundigenprüfung")),
    ("naechste_pruefung", ("nächste prüfung", "naechste pruefung", "nächster prüftermin", "prüfung fällig", "fällig am",
                           "fällig", "fälligkeit")),
    ("intervall", ("prüfintervall", "intervall", "prüfzyklus")),
    ("lebensende", ("lebensende", "ablaufdatum", "ablauf", "nutzungsende", "aussondern bis", "aussonderung spätestens")),
    ("anzahl", ("anzahl", "menge", "stück", "stückzahl", "stk")),
    ("bemerkung", BEMERKUNG_WERT + BEMERKUNG_TITEL),
)

# Die eigene Nacharbeits-CSV (Download der Nacharbeit) in dieser Reihenfolge: Titel → Feld. „Nacharbeit-Nr.“ dient nur
# zum Nachschlagen (nicht gespeichert), „Grund“ und „Zeile“ werden ignoriert.
NACHARBEIT_NR = "Nacharbeit-Nr."
NACHARBEIT_SPALTEN = ((NACHARBEIT_NR, None), ("Grund", None), ("Hersteller", "hersteller"), ("Modell", "modell"),
                      ("Artikelnummer", "artikelnummer"), ("Seriennummer", "seriennummer"),
                      ("Bisherige Inventarnummer", "inventarnummer"), ("Ordner", "ordner"),
                      ("Herstelldatum", "hergestellt"), ("Kaufdatum", "gekauft"), ("Erstgebrauch", "erstgebrauch"),
                      ("Zuletzt geprüft", "zuletzt_geprueft"), ("Nächste Prüfung", "naechste_pruefung"),
                      ("Prüfintervall (Monate)", "intervall"), ("Lebensende", "lebensende"), ("Anzahl", "anzahl"),
                      ("Bemerkung", "bemerkung"), ("Zeile", None))

# Gründe (code → Kurztext für Filter und CSV) und ihre Gruppen – in dieser Reihenfolge stehen sie an einer Zeile; der
# erste bestimmt die Gruppe (Filter der Nacharbeit).
GRUENDE = {
    "produkt_fehlt": "Produktangabe fehlt", "produkt_unbekannt": "Produkt nicht im Katalog",
    "produkt_mehrdeutig": "Produkt mehrdeutig", "produkt_vorschlag": "Produkt nicht sicher erkannt",
    "serie_unbrauchbar": "Seriennummer unbrauchbar",
    "serie_von_hand": "Seriennummer von Hand anlegen", "serie_variante": "Seriennummer bei anderer Variante",
    "doppelt_in_datei": "doppelt in der Datei", "fremde_dublette": "Seriennummer anderswo vorhanden",
    "datum": "Datum", "pflicht": "Pflichtangabe fehlt", "intervall": "Prüfintervall",
    "ordner": "Ordner", "sammelzeile": "Sammelzeile", "regel": "Regel",
}
GRUPPEN = (("produkt", ("produkt_fehlt", "produkt_unbekannt", "produkt_mehrdeutig", "produkt_vorschlag")),
           ("seriennummer", ("serie_unbrauchbar", "serie_von_hand", "serie_variante", "doppelt_in_datei",
                             "fremde_dublette")),
           ("daten", ("datum", "pflicht", "intervall")),
           ("ordner", ("ordner",)),
           ("sonstige", ("sammelzeile", "regel")))
GRUPPE_VON = {code: gruppe for gruppe, codes in GRUPPEN for code in codes}
_RANG = {code: n for n, (_, codes) in enumerate(GRUPPEN) for code in codes}
PRODUKT_ART = {"produkt_mehrdeutig": "mehrdeutig", "produkt_vorschlag": "vorschlag", "produkt_unbekannt": "unbekannt"}

# Datumsfelder: Art (tag/monat) und Name in Texten
DATEN = {"hergestellt": ("monat", "Herstelldatum"), "gekauft": ("monat", "Kaufdatum"),
         "erstgebrauch": ("monat", "Erstgebrauch"), "zuletzt_geprueft": ("tag", "Zuletzt geprüft"),
         "naechste_pruefung": ("tag", "Nächste Prüfung"), "lebensende": ("tag", "Lebensende")}
ZUKUNFT_VERBOTEN = ("hergestellt", "gekauft", "erstgebrauch", "zuletzt_geprueft")
SERIE_EXCEL = ("Excel hat die Seriennummer als Zahl gespeichert und Ziffern gekürzt (mehr als 15 Stellen). Bitte die "
               "Spalte in Excel als Text formatieren und die Nummern neu eintragen.")


# --- Kleine Helfer -----------------------------------------------------------------------------------------------

@contextmanager
def _laeuft():
    """Höchstens ein Import je Arbeitsprozess; wer nach SPERRE_WARTEN Sekunden nicht dran ist, bekommt 429."""
    if not SPERRE.acquire(timeout=SPERRE_WARTEN):
        raise Abgelehnt(BELEGT, 429)
    try:
        yield
    finally:
        SPERRE.release()


def _pi():
    return tabelle._pi()


def _falten(t):
    return t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _titel(t):
    """Spaltentitel zum Vergleichen: pi.normalisiert, ohne Umlaute."""
    return _falten(_pi().normalisiert(t))


def _beginnt(t, synonyme):
    return _pi()._beginnt_mit(t, *(_falten(s) for s in synonyme))


def _kuerzen(feld, wert):
    return wert[:LAENGEN.get(feld, LAENGE_SONST)]


def _einzeilig(v):
    """Wie services.text: Rand weg, Steuerzeichen raus, Leerraum zusammengezogen."""
    v = re.sub(r"[\x00-\x1f\x7f]+", " ", (v or "").strip())
    return re.sub(r"\s{2,}", " ", v).strip()


def _sauber(t):
    """Ein Klartext für die Liste der Gründe – „ · “ trennt die Gründe und darf darin nicht vorkommen."""
    return t.replace(" · ", " – ")


def _tag(iso):
    """'2021-03-15' → '15.03.2021', '2021-03' → '03/2021' (für Texte)."""
    if not iso:
        return ""
    if len(iso) == 7:
        return f"{iso[5:7]}/{iso[:4]}"
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def _jetzt_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def produkt_kurz(p):
    if not p:
        return None
    return {"id": p["id"], "name": katalog.produktname(p), "article_no": p["article_no"],
            "vorschau": katalog.bild_url(p.get("image"), "thumb"), "demo": bool(p["demo"])}


def _artikel_ref(iid, pruefen=True):
    """{id, inventory_no} eines Artikels – nur, wenn das Konto ihn sieht (pruefen)."""
    if not iid:
        return None
    i = db.query("SELECT * FROM mat_item WHERE id = ?", (iid,), one=True)
    if not i or (pruefen and not rechte.darf_artikel("lesen", i)):
        return None
    return {"id": i["id"], "inventory_no": i["inventory_no"]}


def _liste(ids):
    return json.dumps(sorted({int(x) for x in ids}))


# --- Spalten -----------------------------------------------------------------------------------------------------

def erkennen(titel):
    """(Feld, Rang, gesperrt) einer Spalte aus ihrem Titel. Rang zählt nur bei „modell“ (1 Modell, 2 Typ,
    3 Bezeichnung); gesperrt: Personenangaben – die Spalte lässt sich keinem Feld zuordnen."""
    t = _titel(titel)
    if not t:
        return "ignorieren", 0, False
    if _beginnt(t, PERSONEN):
        return "ignorieren", 0, True
    if _beginnt(t, VORRANG_IGNORIEREN):
        return "ignorieren", 0, False
    for feld, synonyme in (("seriennummer", SERIENNUMMER), ("hersteller", HERSTELLER),
                           ("artikelnummer", ARTIKELNUMMER)):
        if _beginnt(t, synonyme):
            return feld, 0, False
    for rang, synonyme in MODELL:
        if _beginnt(t, synonyme):
            return "modell", rang, False
    for feld, synonyme in UEBRIGE:
        if _beginnt(t, synonyme):
            return feld, 0, False
    return "ignorieren", 0, False


def _erkannt(titel):
    """Für die Kopfzeilensuche: trifft der Titel ein Feld?"""
    feld, _, gesperrt = erkennen(titel)
    return feld != "ignorieren" and not gesperrt


def _bemerkung_als_wert(titel):
    """Eine Spalte mit einem Bemerkungstitel steht als Wert allein in der Bemerkung, jede andere als „Titel: Wert“."""
    return bool(titel) and _beginnt(_titel(titel), BEMERKUNG_WERT)


def felder_json():
    return [{"feld": f, "text": t, "mehrfach": f == "bemerkung"} for f, t in FELDER]


def _zuordnung_lesen(zuordnung, warnungen):
    """{"<index>": feld} aus der Anfrage – Unbrauchbares wird gemeldet und übergangen."""
    out = {}
    if not zuordnung:
        return out
    if not isinstance(zuordnung, dict):
        warnungen.append("Die Spaltenzuordnung muss ein Objekt {Spaltenindex: Feld} sein – sie wird ignoriert.")
        return out
    for k, v in zuordnung.items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            warnungen.append(f"Zuordnung für „{k}“ ignoriert: kein Spaltenindex.")
            continue
        if v not in FELD_TEXT:
            warnungen.append(f"Unbekannte Zuordnung „{v}“ für Spalte {idx + 1} ignoriert.")
            continue
        out[idx] = v
    return out


def spalten(tab, zuordnung=None):
    """Kopfzeile und Zuordnung der Spalten. Liefert (spalten, nacharbeit_csv, kopf_index, warnungen): spalten =
    [{index, titel, zuordnung, gesperrt, beispiele}]. Eine Kopfzeile mit „Nacharbeit-Nr.“ ist die eigene
    Nacharbeits-CSV: feste Zuordnung (NACHARBEIT_SPALTEN), die Nummer selbst wird beim Lesen der Zeilen immer aus ihrer
    Spalte genommen. zuordnung aus der Anfrage überschreibt die Erkennung – außer bei gesperrten Spalten. Jedes Feld
    höchstens einmal (die erste Spalte gewinnt, bei „modell“ der beste Rang), nur „bemerkung“ beliebig oft. Mehr als
    MAX_DATENZEILEN Datenzeilen: Abgelehnt."""
    warnungen = []
    zeilen = tab.zeilen
    kopf_index, nacharbeit_csv = None, False
    for i, zeile in enumerate(zeilen[:_pi().MAX_KOPF_SUCHE]):
        if any(isinstance(w, str) and w.strip() == NACHARBEIT_NR for w in zeile):
            kopf_index, nacharbeit_csv = i, True
            break
    if kopf_index is None:
        kopf_index, warnung = tabelle.kopfzeile(zeilen, _erkannt)
        if warnung:
            warnungen.append(warnung)
    kopf = zeilen[kopf_index]
    daten = zeilen[kopf_index + 1:]
    belegt = sum(1 for z in daten if not all(tabelle.ist_leer(w) for w in z))
    if belegt > MAX_DATENZEILEN:
        raise Abgelehnt(f"Die Datei hat {belegt} Datenzeilen – höchstens {MAX_DATENZEILEN} lassen sich auf einmal "
                        "übernehmen. Bitte die Liste aufteilen.")
    vorgaben = _zuordnung_lesen(zuordnung, warnungen)
    fest = {_titel(t): f for t, f in NACHARBEIT_SPALTEN}
    breite = max([len(kopf)] + [len(z) for z in daten]) if (kopf or daten) else 0
    out = []
    for idx in range(breite):
        roh = kopf[idx] if idx < len(kopf) else None
        titel = tabelle.zelltext(roh) if not tabelle.ist_leer(roh) else ""
        werte = [z[idx] for z in daten if idx < len(z) and not tabelle.ist_leer(z[idx])]
        if not titel and not werte:
            continue
        if nacharbeit_csv:
            feld, rang, gesperrt = (fest.get(_titel(titel)) or "ignorieren"), 0, False
        elif titel:
            feld, rang, gesperrt = erkennen(titel)
        else:
            feld, rang, gesperrt = "ignorieren", 0, False
        explizit = False
        if idx in vorgaben:
            if gesperrt:
                if vorgaben[idx] != "ignorieren":
                    warnungen.append(f"Spalte „{titel}“ enthält Personenangaben und wird nicht übernommen.")
            else:
                feld, explizit = vorgaben[idx], True
        beispiele = []
        if not gesperrt:
            for w in werte:
                t = tabelle.zelltext(w)[:100]
                if t and t not in beispiele:
                    beispiele.append(t)
                if len(beispiele) == 3:
                    break
        out.append({"index": idx, "titel": titel, "zuordnung": feld, "gesperrt": gesperrt, "beispiele": beispiele,
                    "_rang": rang, "_explizit": explizit})
    for i in sorted(set(vorgaben) - {s["index"] for s in out}):
        warnungen.append(f"Zuordnung für Spalte {i + 1} ignoriert: Die Spalte gibt es nicht.")
    # Jedes Feld höchstens einmal – außer „bemerkung“. Eine ausdrückliche Wahl geht der Erkennung vor; unter den
    # erkannten Modellspalten gewinnt der beste Rang, sonst die linke.
    for f, _ in FELDER:
        if f in ("bemerkung", "ignorieren"):
            continue
        kandidaten = [s for s in out if s["zuordnung"] == f]
        if len(kandidaten) < 2:
            continue
        ausdruecklich = [s for s in kandidaten if s["_explizit"]]
        sieger = ausdruecklich[0] if ausdruecklich else min(kandidaten, key=lambda s: (s["_rang"], s["index"]))
        for s in kandidaten:
            if s is sieger:
                continue
            name = s["titel"] or f"Spalte {tabelle.spalte_buchstabe(s['index'])}"
            if f == "modell" and not s["_explizit"] and not sieger["_explizit"] and s["_rang"] > sieger["_rang"]:
                warnungen.append(f"Spalte „{name}“ wird nicht als Modell verwendet – „{sieger['titel']}“ hat Vorrang. "
                                 "Bei Bedarf als Bemerkung zuordnen.")
            else:
                warnungen.append(f"Spalte „{name}“ ist ein zweites Mal als „{FELD_TEXT[f]}“ zugeordnet – sie wird "
                                 "ignoriert.")
            s["zuordnung"] = "ignorieren"
    for s in out:
        del s["_rang"], s["_explizit"]
    return out, nacharbeit_csv, kopf_index, warnungen


def fehlt(spalten_liste):
    """Pflichtzuordnungen, die fehlen: Hersteller und (Modell oder Artikelnummer)."""
    da = {s["zuordnung"] for s in spalten_liste}
    out = []
    if "hersteller" not in da:
        out.append("hersteller")
    if "modell" not in da and "artikelnummer" not in da:
        out.append("modell")
    return out


def _bemerkungstext(wert):
    """Bemerkung aus einer Zelle: Zeilenumbrüche bleiben (die Nacharbeits-CSV trägt mehrzeilige Bemerkungen), in jeder
    Zeile wie zelltext."""
    if not isinstance(wert, str):
        return tabelle.zelltext(wert)
    teile = [tabelle.zelltext(t) for t in wert.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(t for t in teile if t)


def datensaetze(tab, spalten_liste, kopf_index, nacharbeit_csv=False):
    """Die Datenzeilen unter der Kopfzeile: (zeilen, leerzeilen, uebergangen). zeilen = [{nr, werte, serie_hinweis,
    nacharbeit_nr}] – werte nur mit zugeordneten, nicht leeren Feldern, als Text (je Feld gekürzt). nr zählt wie Excel
    (1 = erste Zeile der Datei). Eine Zeile, deren zugeordnete Zellen alle leer sind, wird übergangen (ihre Nummer steht
    in uebergangen)."""
    zugeordnet = [s for s in spalten_liste if s["zuordnung"] != "ignorieren" and not s["gesperrt"]]
    nr_spalte = None
    if nacharbeit_csv:
        kopf = tab.zeilen[kopf_index]
        nr_spalte = next((i for i, w in enumerate(kopf) if isinstance(w, str) and w.strip() == NACHARBEIT_NR), None)
    zeilen, leer, ohne = [], 0, []
    for offset, zeile in enumerate(tab.zeilen[kopf_index + 1:]):
        nr = kopf_index + offset + 2
        if all(tabelle.ist_leer(w) for w in zeile):
            leer += 1
            continue
        werte, bemerkung, hinweis = {}, [], None
        for s in zugeordnet:
            roh = zeile[s["index"]] if s["index"] < len(zeile) else None
            if tabelle.ist_leer(roh):
                continue
            f = s["zuordnung"]
            if f == "seriennummer":
                text, hinweis = tabelle.serientext(roh)
            elif f == "bemerkung":
                text = _bemerkungstext(roh)
                if text:
                    titel = s["titel"] or f"Spalte {tabelle.spalte_buchstabe(s['index'])}"
                    bemerkung.append(text if _bemerkung_als_wert(s["titel"]) else f"{titel}: {text}")
                continue
            else:
                text = tabelle.zelltext(roh)
            if text:
                werte[f] = _kuerzen(f, text)
        if bemerkung:
            werte["bemerkung"] = _kuerzen("bemerkung", "\n".join(bemerkung))
        nacharbeit_nr = None
        if nr_spalte is not None and nr_spalte < len(zeile):
            t = tabelle.zelltext(zeile[nr_spalte])
            nacharbeit_nr = int(t) if re.fullmatch(r"\d{1,12}", t) else None
        if not werte:
            ohne.append(nr)
            continue
        zeilen.append({"nr": nr, "werte": werte, "serie_hinweis": hinweis if "seriennummer" in werte else None,
                       "nacharbeit_nr": nacharbeit_nr})
    return zeilen, leer, ohne


# --- Zielordner und Ordnerspalte ---------------------------------------------------------------------------------

def _pfad_norm(text):
    """„Regal 1 / Fach 2“ = „regal 1/fach 2“: an „/“ getrennt, jedes Glied ohne Rand und mit einfachem Leerraum, ohne
    Groß/klein."""
    teile = [" ".join(t.split()).casefold() for t in (text or "").split("/")]
    return "/".join(t for t in teile if t)


@dataclass
class Ziel:
    id: int
    name: str
    demo: bool
    pfade: dict          # normalisierter Pfad relativ zum Ziel → [Ordnerzeilen]
    ordner: dict         # Kennung → Ordnerzeile (Unterbaum samt Ziel)


def _unterbaum(fid):
    return db.query("WITH RECURSIVE baum(id) AS (SELECT ? UNION SELECT f.id FROM mat_folder f JOIN baum b "
                    "ON f.parent_id = b.id) SELECT o.id, o.parent_id, o.name, o.system_kind FROM mat_folder o "
                    "WHERE o.id IN (SELECT id FROM baum)", (fid,))


def ziel_pruefen(fid):
    """Der Zielordner: ein Ablageordner (kein Systemordner, unter einer Gliederung), sonst 409. Dazu einmal der
    Unterbaum mit Namen und Systemkennzeichen und die Karte normalisierter Pfad → Ordner."""
    o = bestand.ordner(fid)
    if o["system_kind"]:
        raise Abgelehnt(NUR_SYSTEM, 409)
    if not bestand.gliederung_von(fid):
        raise Abgelehnt("Artikel liegen immer unterhalb einer Gliederung.", 409)
    rows = {r["id"]: r for r in _unterbaum(fid)}
    pfade = {}
    for r in rows.values():
        glieder, x, gesehen = [], r, set()
        while x and x["id"] != fid and x["id"] not in gesehen:
            gesehen.add(x["id"])
            glieder.insert(0, x["name"])
            x = rows.get(x["parent_id"])
        pfade.setdefault(_pfad_norm("/".join(glieder)), []).append(r)
    return Ziel(fid, o["name"], bestand.ordner_ist_demo(fid), pfade, rows)


def _ordner_finden(ziel, wert):
    """(Ordnerzeile | None, Fehlertext | None, unbekannt: bool) für den Wert der Spalte „Ordner“."""
    if not wert:
        return ziel.ordner[ziel.id], None, False
    treffer = ziel.pfade.get(_pfad_norm(wert), [])
    if not treffer:
        return None, f"Ordner „{wert}“ gibt es unter „{ziel.name}“ nicht.", True
    if len(treffer) > 1:
        return None, f"„{wert}“ ist mehrdeutig – bitte umbenennen.", False
    if treffer[0]["system_kind"]:
        return None, "In „Gesperrt“ und „Ausgesondert“ legt der Import nichts ab.", False
    return treffer[0], None, False


def _baum_unveraendert(fid, ordner_ids):
    """Unter der Schreibsperre: Ist das Ziel noch ein Ablageordner, liegt jeder Ordner des Plans noch darunter und ist
    keiner ein Systemordner? Sonst 409 – ein Unterordner, der inzwischen in eine andere Gliederung gewandert ist, bekäme
    sonst Artikel ohne Verwalterrecht."""
    o = db.query("SELECT system_kind FROM mat_folder WHERE id = ?", (fid,), one=True)
    if not o or o["system_kind"] or not bestand.gliederung_von(fid):
        raise Abgelehnt(BAUM_GEAENDERT, 409)
    baum = {r["id"]: r for r in _unterbaum(fid)}
    for oid in ordner_ids:
        if oid not in baum or baum[oid]["system_kind"]:
            raise Abgelehnt(BAUM_GEAENDERT, 409)


# --- Produktabgleich ---------------------------------------------------------------------------------------------

def produkt_finden(hersteller, modell, artikelnummer, demo_erlaubt):
    """Das Produkt zu einer Produktangabe – nie geraten. {"art", "produkt", "vorschlaege"}:
      genau          gleicher Dublettenschlüssel
      artikelnummer  die (katalogweit eindeutige) Artikelnummer, beim selben Hersteller
      modell         ohne Artikelnummer in der Liste: genau ein Produkt des Herstellers mit diesem Modellnamen (vor „|“)
      mehrdeutig     mehrere davon (Varianten, Größen) – die Treffer als Vorschläge
      vorschlag      Artikelnummer bei anderem Hersteller, gleicher Modellname mit anderer Artikelnummer oder ein
                     unscharfer Treffer der Katalogsuche – nur ein Angebot
      unbekannt      nichts
    DEMO-Produkte zählen nur für einen DEMO-Zielordner (demo_erlaubt) – in keiner Stufe und keinem Vorschlag sonst."""
    h, m, a = hersteller or "", modell or "", katalog.artikelnummer(artikelnummer)
    he = katalog._einheitlich(h)

    def ok(p):
        return p and (demo_erlaubt or not p["demo"])

    p = db.query("SELECT * FROM mat_product WHERE dedupe_key = ?", (katalog.dedupe_key(h, m, a),), one=True)
    if ok(p):
        return {"art": "genau", "produkt": p, "vorschlaege": []}
    vorschlaege = []
    if a:
        v = katalog.artikelnummer_vergeben(a)
        p = katalog.produkt(v["id"]) if v else None
        if ok(p):
            if he and katalog._einheitlich(p["manufacturer"]) == he:
                return {"art": "artikelnummer", "produkt": p, "vorschlaege": []}
            vorschlaege.append(p)
    if he and m:
        name = katalog._einheitlich(katalog.modell_teile(m)[0])
        gleich = [p for p in db.query("SELECT * FROM mat_product WHERE dedupe_key LIKE ? ORDER BY id", (he + "|%",))
                  if ok(p) and katalog._einheitlich(katalog.modell_teile(p["model"])[0]) == name]
        if not a:
            if len(gleich) == 1:
                return {"art": "modell", "produkt": gleich[0], "vorschlaege": []}
            if len(gleich) > 1:
                return {"art": "mehrdeutig", "produkt": None, "vorschlaege": gleich[:10]}
        vorschlaege += [p for p in gleich if p["id"] not in {x["id"] for x in vorschlaege}]
    if not vorschlaege:
        from .search import produkte
        for q in (f"{h} {m}".strip(), m, a, h):
            if not q or len(vorschlaege) >= 5:
                continue
            try:
                rows, _ = produkte(q, None, 1, 5)
            except Abgelehnt:
                continue
            vorschlaege += [p for p in rows if ok(p) and p["id"] not in {x["id"] for x in vorschlaege}]
    vorschlaege = vorschlaege[:5]
    return {"art": "vorschlag" if vorschlaege else "unbekannt", "produkt": None, "vorschlaege": vorschlaege}


# --- Prüfregeln je Zeile -----------------------------------------------------------------------------------------

@dataclass
class Ergebnis:
    nr: int                     # Zeile in der Datei
    werte: dict                 # {feld: text} – nur zugeordnete, nicht leere Felder (so gespeichert)
    status: str = "nacharbeit"  # "uebernehmbar" | "im_bestand" | "erledigt" | "nacharbeit" (nach dem Schreiben „angelegt“)
    gruende: list = field(default_factory=list)    # [(code, text)] – nach Gruppe geordnet
    hinweise: list = field(default_factory=list)   # [text]
    angabe: str = ""            # offer_key
    produkt: dict = None        # Produktzeile
    ordner_id: int = None
    ordner_text: str = None
    plan: dict = None           # bestand.artikel_plan(...), nur bei „uebernehmbar“
    faellig: str = None         # next_due_on (ISO)
    faellig_art: str = None     # "liste" | "ohne_datum"
    lebensdauer: bool = False   # Lebensende erreicht
    journal: dict = field(default_factory=dict)    # Zusatz fürs Journal des Artikels
    item_id: int = None         # bei „im_bestand“ (und nach dem Schreiben)
    fremd: int = None           # Kennung einer fremden Dublette (fürs Protokoll, nie nach außen)
    alte_zeile: int = None      # offene Nacharbeitszeile dieses Ziels, die diese Zeile ersetzt
    wahl: dict = None           # Produktwahl und Meldung aus der Nacharbeit {"product_id", "request_id"}
    zeile_id: int = None        # Nacharbeit-Nr. (erneut prüfen)
    import_id: int = None       # Import der Zeile (erneut prüfen)
    serie: str = ""             # Herstellerseriennummer, wie sie angelegt würde ("" = ohne; nach dem Anlegen die STR-…)
    serie_ok: bool = False      # brauchbar (nicht leer, keine Fehlerform)
    ohne_serie: bool = False    # ohne Herstellerseriennummer – bekommt beim Anlegen eine STR-Nummer
    rueckruf: str = None
    artikel: dict = None        # {id, inventory_no} – angelegt bzw. schon im Bestand
    daten: dict = field(default_factory=dict)      # Datumsfeld → (iso, fehler, hinweis, text)
    intervall: int = None       # Prüfintervall laut Liste (lesbar)
    konflikt: dict = None       # bestand.serie_konflikt bei Produkt und Seriennummer

    def grund(self, code, text):
        self.gruende.append((code, _sauber(text)))


class Lauf:
    """Was eine Prüfung über alle Zeilen braucht – Ziel, Stichtag, Nacharbeit-Nr. der Nacharbeits-CSV – und ihre
    Zwischenspeicher: Abgleich je Produktangabe, wirksames Intervall je (Produkt, Ordner, Intervall), Rückrufe je
    Produkt."""

    def __init__(self, ziel, stichtag, alte=None, mehrfach_text="in der Datei", zeilen_wort="Zeilen"):
        self.ziel, self.stichtag = ziel, stichtag
        self.alte = alte or {}
        self.mehrfach_text, self.zeilen_wort = mehrfach_text, zeilen_wort
        self._treffer, self._wirksam, self._rueckruf, self._produkte = {}, {}, {}, {}
        self.ordner_unbekannt = {}
        self.fremde_nr = 0

    def treffer(self, h, m, a):
        key = katalog.dedupe_key(h, m, a)
        if key not in self._treffer:
            self._treffer[key] = produkt_finden(h, m, a, self.ziel.demo)
        return self._treffer[key]

    def produkt(self, pid):
        if pid not in self._produkte:
            self._produkte[pid] = db.query("SELECT * FROM mat_product WHERE id = ?", (pid,), one=True)
        return self._produkte[pid]

    def monate(self, p, fid, artikel_monate):
        key = (p["id"], fid, artikel_monate)
        if key not in self._wirksam:
            self._wirksam[key] = wirksam(p, fid, artikel_monate)["monate"]
        return self._wirksam[key]

    def rueckrufe(self, pid, serie):
        if pid not in self._rueckruf:
            self._rueckruf[pid] = bool(db.query("SELECT 1 FROM mat_recall WHERE product_id = ? AND closed_at IS NULL "
                                                "LIMIT 1", (pid,), one=True))
        return rueckruf.betrifft(pid, serie) if self._rueckruf[pid] else []


def _intervall_lesen(text):
    """„12“, „12 Monate“, „1 Jahr“, „2 Jahre“ → Monate (1–120) oder None (unlesbar)."""
    t = " ".join((text or "").lower().split())
    m = re.fullmatch(r"(\d{1,3})(?:\s*(monate?|mon\.?|m))?", t)
    if m:
        n = int(m.group(1))
    else:
        m = re.fullmatch(r"(\d{1,2})\s*(jahre?|j\.?)", t)
        n = int(m.group(1)) * 12 if m else None
    return n if n and 1 <= n <= 120 else None


def _seriennummer(e, lauf):
    """Seriennummer nach 2.4.2 – Fehler werden Gründe; e.serie und e.serie_ok setzen."""
    s = _einzeilig(e.werte.get("seriennummer", ""))
    e.serie = s
    if not s:
        e.ohne_serie = True
        return
    if tabelle.sieht_aus_wie_exponent(s):
        e.grund("serie_unbrauchbar", SERIE_EXCEL)
    elif tabelle.sieht_aus_wie_datum(s):
        e.grund("serie_unbrauchbar", f"Seriennummer „{s}“ sieht aus wie ein Datum – hat Excel die Nummer umgewandelt "
                                     "(etwa „1-2“)?")
    elif nummern.sieht_generiert_aus(s):
        e.grund("serie_unbrauchbar", "Seriennummern der Form „STR-…“ vergibt nur das System.")
    elif len(s) > 80:
        e.grund("serie_unbrauchbar", "„Seriennummer“ ist zu lang (höchstens 80 Zeichen).")
    else:
        e.serie_ok = True


def _vorpruefen(z, lauf):
    """Schritte 0–3 (Bauentwurf 2.6.2): Nacharbeit-Nr., was ohne Produkt prüfbar ist, Produkt, schon im Bestand."""
    w = z["werte"]
    e = Ergebnis(nr=z["nr"], werte=w, zeile_id=z.get("zeile_id"), import_id=z.get("import_id"), wahl=z.get("wahl"))
    h, m, a = w.get("hersteller", ""), w.get("modell", ""), w.get("artikelnummer", "")
    e.angabe = katalog.dedupe_key(h, m, a)
    if z.get("serie_hinweis"):
        e.hinweise.append(z["serie_hinweis"])
    # 0. Nacharbeit-Nr. (nur in der Nacharbeits-CSV) – nur Zeilen dieses Ziels zählen.
    nr_alt = z.get("nacharbeit_nr")
    if nr_alt is not None:
        alt = lauf.alte.get(nr_alt)
        if not alt:
            lauf.fremde_nr += 1
        elif alt["status"] != "offen":
            e.status = "erledigt"
            e.hinweise.append(f"schon erledigt ({IMPORT_STATUS.get(alt['status'], alt['status'])} am "
                              f"{_tag((alt['resolved_at'] or '')[:10])})")
            e.artikel = _artikel_ref(alt["item_id"])
            return e
        elif not alt.get("_vergeben"):
            alt["_vergeben"] = True                 # dieselbe Nummer zweimal in der Datei: nur die erste ersetzt
            e.alte_zeile = alt["id"]
            if alt["offer_key"] == e.angabe:
                e.wahl = {"product_id": alt["product_id"], "request_id": alt["request_id"]}
    # 1. Ohne Produkt prüfbar.
    anzahl = w.get("anzahl", "")
    if anzahl and anzahl != "1":
        if re.fullmatch(r"\d{1,6}", anzahl) and int(anzahl) > 1:
            e.grund("sammelzeile", f"Sammelzeile (Anzahl {int(anzahl)}) – bitte je Artikel eine Zeile anlegen")
        else:
            e.grund("sammelzeile", f"Anzahl laut Liste unlesbar („{anzahl}“) – je Artikel eine Zeile mit Anzahl 1")
    for f, (art, _) in DATEN.items():
        text = w.get(f, "")
        iso, fehler, hinweis = tabelle.datum(text, art)
        if iso and f in ZUKUNFT_VERBOTEN and bestand._vor(lauf.stichtag.isoformat(), iso):
            iso, fehler = None, "liegt in der Zukunft"
        e.daten[f] = (iso, fehler, hinweis, text)
    _seriennummer(e, lauf)
    if w.get("intervall"):
        e.intervall = _intervall_lesen(w["intervall"])
        if e.intervall is None:
            e.grund("intervall", f"Prüfintervall laut Liste unlesbar („{w['intervall']}“)")
    o, fehler, unbekannt = _ordner_finden(lauf.ziel, w.get("ordner", ""))
    if fehler:
        e.grund("ordner", fehler)
        if unbekannt:
            lauf.ordner_unbekannt[w["ordner"]] = lauf.ordner_unbekannt.get(w["ordner"], 0) + 1
    else:
        e.ordner_id = o["id"]
        e.ordner_text = bestand._pfad_text(o["id"])
    if not ((h and m) or a):
        e.grund("produkt_fehlt", "Keine Produktangabe – Hersteller und Modell oder eine Artikelnummer fehlen.")
        return e
    # 2. Produkt: Wahl aus der Nacharbeit vor eingepflegter Meldung vor dem automatischen Abgleich.
    p = None
    wahl = e.wahl or {}
    if wahl.get("product_id"):
        p = lauf.produkt(wahl["product_id"])
        if p and p["demo"] and not lauf.ziel.demo:
            e.grund("regel", DEMO_PRODUKT)
            return e
    if not p and wahl.get("request_id"):
        r = db.query("SELECT status, product_id FROM mat_product_request WHERE id = ?", (wahl["request_id"],), one=True)
        if r and r["status"] == "eingepflegt" and r["product_id"]:
            p = lauf.produkt(r["product_id"])
            if p and p["demo"] and not lauf.ziel.demo:
                p = None
    if not p:
        t = lauf.treffer(h, m, a)
        p = t["produkt"]
        if not p:
            if t["art"] == "mehrdeutig":
                e.grund("produkt_mehrdeutig", "Produkt nicht eindeutig – im Katalog gibt es mehrere Varianten dazu; "
                                              "bitte in der Nacharbeit zuordnen.")
            elif t["art"] == "vorschlag":
                e.grund("produkt_vorschlag", "Produkt nicht sicher erkannt – im Katalog gibt es Ähnliches; bitte in "
                                             "der Nacharbeit zuordnen.")
            else:
                e.grund("produkt_unbekannt", "Produkt nicht im Katalog – bitte in der Nacharbeit zuordnen oder melden.")
            return e
    e.produkt = p
    # 3. Schon im Bestand (sichtbar): übersprungen, keine Aktualisierung.
    if e.serie_ok:
        k = bestand.serie_konflikt(p["id"], e.serie)
        if k and k["sichtbar"]:
            e.status, e.item_id = "im_bestand", k["item"]["id"]
            e.artikel = {"id": k["item"]["id"], "inventory_no": k["item"]["inventory_no"]}
            e.hinweise.append(f"schon im Bestand (Inventarnummer {k['item']['inventory_no']})")
        e.konflikt = k
    return e


def _fertig_pruefen(e, lauf, doppelt):
    """Schritte 4–9: doppelt in der Datei, fremde Bereiche, andere Variante, blockierende Werte, Fälligkeit und Plan,
    Rückruf. Danach der Status. Eine Zeile ohne Herstellerseriennummer ist übernehmbar wie jede andere – sie bekommt
    beim Anlegen eine STR-Nummer (Entscheidung vom 19.10.2026)."""
    if e.status in ("erledigt", "im_bestand"):
        return
    p = e.produkt
    if p is not None:
        _mit_produkt(e, lauf, doppelt)
    e.gruende.sort(key=lambda g_: _RANG.get(g_[0], 99))
    if not e.gruende:
        e.status = "uebernehmbar"
        if e.ohne_serie:
            e.hinweise.append("ohne Herstellerseriennummer – bekommt eine Seriennummer vom System (STR-…), bitte am "
                              "Artikel anbringen")
    else:
        e.status = "nacharbeit"
        e.plan = None


def _mit_produkt(e, lauf, doppelt):
    p, w, T = e.produkt, e.werte, lauf.stichtag
    textil = p["material_kind"] == "textil"
    # 4. Doppelt in der Datei – welche Zeile stimmt, wird nicht geraten.
    if e.serie:
        andere = doppelt.get((p["id"], e.serie.casefold()), [])
        if len(andere) > 1:
            e.grund("doppelt_in_datei", f"kommt {lauf.mehrfach_text} mehrfach vor ({lauf.zeilen_wort} "
                                        f"{', '.join(str(n) for n in andere)})")
    # 5. Fremde Bereiche – nur für Nummern, die auch die globale Suche beantwortet.
    if e.serie_ok:
        if not globalsuche.suchbar(e.serie):
            e.grund("serie_von_hand", f"Seriennummer „{e.serie}“ ist für den Import zu kurz (weniger als 4 Zeichen) "
                                      "oder hat die Form einer Inventarnummer – bitte prüfen und von Hand anlegen.")
        elif e.konflikt:
            e.grund("fremde_dublette", bestand.FremdeDublette.TEXT)
            e.fremd = e.konflikt["item"]["id"]
        # 6. Dieselbe Nummer bei einer anderen Variante desselben Herstellers (nur Sichtbares).
        he = katalog._einheitlich(p["manufacturer"])
        for r in db.query(f"SELECT i.id, i.inventory_no, i.lock_state, i.folder_id, i.origin_folder_id, "
                          f"p.manufacturer, p.model, p.description FROM mat_item i JOIN mat_product p "
                          f"ON p.id = i.product_id WHERE i.serial_no = ? COLLATE NOCASE AND i.product_id <> ? "
                          f"AND {rechte.artikel_filter('i')} ORDER BY i.id", (e.serie, p["id"])):
            if katalog._einheitlich(r["manufacturer"]) == he:
                e.grund("serie_variante", f"Seriennummer gibt es schon bei {katalog.produktname(r)} (Inventarnummer "
                                          f"{r['inventory_no']}) – andere Variante oder Größe? Bitte das Produkt "
                                          "prüfen.")
                break
    # 7. Blockierende Werte, Hinweise und Bemerkungszeilen.
    laut_liste, d = [], e.daten
    herg_iso, herg_fehler, _, herg_text = d["hergestellt"]
    if textil:
        if not herg_text:
            e.grund("pflicht", "Bei textilem Material ist das Herstelldatum Pflicht – an ihm hängt die Lebensdauer.")
        elif herg_fehler:
            zusatz = " – bitte vom Etikett ergänzen (MM/JJJJ)" if herg_fehler == "nur Jahr" else ""
            e.grund("datum", f"Herstelldatum „{herg_text}“: {herg_fehler}{zusatz}")
    elif herg_fehler:
        e.hinweise.append(f"Herstelldatum „{herg_text}“: {herg_fehler} – nicht übernommen")
        laut_liste.append(f"Herstelldatum laut Liste: {herg_text}")
        herg_iso = None
    werte_plan = {"manufactured_on": herg_iso}
    for f, spalte in (("gekauft", "purchased_on"), ("erstgebrauch", "first_use_on")):
        iso, fehler, _, text = d[f]
        name = DATEN[f][1]
        if fehler:
            e.hinweise.append(f"{name} „{text}“: {fehler} – nicht übernommen")
            laut_liste.append(f"{name} laut Liste: {text}")
            iso = None
        werte_plan[spalte] = iso
    pruefdaten = {}
    for f in ("zuletzt_geprueft", "naechste_pruefung"):
        iso, fehler, hinweis, text = d[f]
        name = DATEN[f][1]
        if fehler:
            e.hinweise.append(f"{name} „{text}“: {fehler} – nicht verwendet")
            laut_liste.append(f"{name} laut Liste: {text}")
            iso = None
        elif hinweis:
            e.hinweise.append(f"{name}: {hinweis}")
        pruefdaten[f] = iso
    if pruefdaten["zuletzt_geprueft"] and herg_iso and bestand._vor(pruefdaten["zuletzt_geprueft"], herg_iso):
        e.hinweise.append(f"Zuletzt geprüft laut Liste ({_tag(pruefdaten['zuletzt_geprueft'])}) liegt vor dem "
                          "Herstelldatum – nicht verwendet")
        laut_liste.append(f"Zuletzt geprüft laut Liste: {d['zuletzt_geprueft'][3]}")
        pruefdaten["zuletzt_geprueft"] = None
    end_iso, end_fehler, end_hinweis, end_text = d["lebensende"]
    retire = None
    if end_text and not textil:
        e.hinweise.append("Ein Lebensende gibt es nur bei textilem Material – nicht übernommen.")
    elif end_fehler:
        e.grund("datum", f"Lebensende laut Liste „{end_text}“: {end_fehler}")
    elif end_iso:
        if end_hinweis:
            e.hinweise.append(f"Lebensende: {end_hinweis}")
        rechnung = lebensende(herg_iso, p["lifetime_years"]) if herg_iso and not herg_fehler else None
        if rechnung and end_iso < rechnung:
            retire = end_iso
            e.hinweise.append(f"Lebensende laut Liste ({_tag(end_iso)}) früher als Herstellung + Lebensdauer – "
                              "übernommen (vorgezogen)")
        elif rechnung and end_iso > rechnung:
            e.hinweise.append(f"Lebensende laut Liste später als Herstellung + Lebensdauer – es gilt {_tag(rechnung)}")
    # 8. Fälligkeit und Plan – nur mit Ordner, Intervall und (bei textilem Material) Herstelldatum.
    if e.ordner_id is None or (textil and (not herg_iso or herg_fehler)):
        return
    eigenes = None
    ohne = lauf.monate(p, e.ordner_id, None)
    if not ohne:
        e.grund("intervall", katalog.KEIN_INTERVALL)
        return
    if e.intervall:
        if e.intervall < ohne:
            eigenes = e.intervall
        else:
            e.hinweise.append(f"Intervall laut Liste ({e.intervall}) nicht kürzer als das wirksame ({ohne}) – es gilt "
                              f"{ohne}")
    iv = lauf.monate(p, e.ordner_id, eigenes)
    grenze = spaetestens(iv, T)
    n, letzte = pruefdaten["naechste_pruefung"], pruefdaten["zuletzt_geprueft"]
    kandidaten = []
    if n:
        kandidaten.append(n)
    if letzte:
        kandidaten.append(plus_monate(date.fromisoformat(letzte), iv).isoformat())
    if kandidaten:
        faellig = min(kandidaten + [grenze])
        e.faellig_art = "liste"
        if n and faellig < n:
            if faellig == grenze and n > grenze:
                e.hinweise.append(f"Nächste Prüfung laut Liste ({_tag(n)}) liegt mehr als ein Intervall in der Zukunft "
                                  f"– auf {_tag(faellig)} vorgezogen")
            else:
                e.hinweise.append(f"Nächste Prüfung laut Liste ({_tag(n)}) – nach „zuletzt geprüft“ + Intervall auf "
                                  f"{_tag(faellig)} vorgezogen")
    else:
        faellig, e.faellig_art = T.isoformat(), "ohne_datum"
        e.hinweise.append("ohne Prüfdatum in der Liste – Eingangsprüfung sofort fällig")
    e.faellig = faellig
    zeilen = []
    if w.get("inventarnummer"):
        zeilen.append(f"Bisherige Inventarnummer: {w['inventarnummer']}")
    if w.get("bemerkung"):
        zeilen.append(w["bemerkung"])
    notes = "\n".join(zeilen + laut_liste)
    if len(notes) > BEMERKUNG_MAX:
        notes = notes[:BEMERKUNG_MAX]
        e.hinweise.append(f"Bemerkung auf {BEMERKUNG_MAX} Zeichen gekürzt")
    d_plan = dict(werte_plan, product_id=p["id"], folder_id=e.ordner_id, serial_no=e.serie if e.serie_ok else "",
                  next_due_on=faellig, retire_by=retire, interval_months=eigenes, notes=notes)
    try:
        e.plan = bestand.artikel_plan(d_plan)
    except Abgelehnt as exc:
        text = str(exc)
        code = ("intervall" if text == katalog.KEIN_INTERVALL else
                "pflicht" if "Herstelldatum Pflicht" in text else "regel")
        e.grund(code, text)
        return
    rb = e.plan["w"]["retire_by"]
    if rb and rb <= T.isoformat():
        e.lebensdauer = True
        e.hinweise.append("Lebensdauer erreicht – nach dem Import aussondern")
    # Journal des Artikels: woher er kommt (ohne Dateinamen) und was die Liste sagte.
    if w.get("inventarnummer"):
        e.journal["liste_inventarnummer"] = w["inventarnummer"]
    for f, schluessel in (("zuletzt_geprueft", "liste_zuletzt_geprueft"), ("naechste_pruefung", "liste_naechste_pruefung")):
        if d[f][3]:
            e.journal[schluessel] = d[f][0] or d[f][3]
    # 9. Rückruf.
    titel = []
    for r in lauf.rueckrufe(p["id"], e.serie):
        titel.append(r["title"])
        e.hinweise.append(f"Rückruf (alle Artikel des Produkts): {r['title']}" if r["alle"] else f"Rückruf: {r['title']}")
    e.rueckruf = " · ".join(titel) or None


def zeilen_pruefen(daten, lauf):
    """Alle Zeilen in zwei Durchgängen (erst alle Schlüssel Produkt + Seriennummer, dann die Entscheidung)."""
    ergebnisse = [_vorpruefen(z, lauf) for z in daten]
    doppelt = {}
    for e in ergebnisse:
        if e.produkt is not None and e.serie and e.status not in ("erledigt",):
            doppelt.setdefault((e.produkt["id"], e.serie.casefold()), []).append(e.zeile_id or e.nr)
    for e in ergebnisse:
        _fertig_pruefen(e, lauf, doppelt)
    return ergebnisse


# --- Probelauf ---------------------------------------------------------------------------------------------------

@dataclass
class Bericht:
    ziel: Ziel
    tab: object
    dateiname: str
    spalten: list
    nacharbeit_csv: bool
    kopf_index: int
    warnungen: list
    fehlt: list
    datenzeilen: int = 0
    leerzeilen: int = 0
    ergebnisse: list = field(default_factory=list)
    schon_importiert: list = field(default_factory=list)
    ordner_unbekannt: dict = field(default_factory=dict)
    import_info: dict = None

    @property
    def fremde(self):
        return [e.fremd for e in self.ergebnisse if e.fremd]


def _alte_zeilen(fid, nummern_liste):
    """Die genannten Nacharbeit-Nr., soweit sie zu Importen genau dieses Ziels gehören."""
    if not nummern_liste:
        return {}
    return {r["id"]: r for r in db.query(
        "SELECT r.* FROM mat_import_row r JOIN mat_import i ON i.id = r.import_id WHERE i.folder_id = ? "
        "AND r.id IN (SELECT value FROM json_each(?))", (fid, _liste(nummern_liste)))}


def _schon_importiert(fid, sha):
    return [{"id": r["id"], "am": r["created_at"], "von": r["created_by_name"], "angelegt": r["rows_created"]}
            for r in db.query("SELECT * FROM mat_import WHERE folder_id = ? AND file_sha256 = ? ORDER BY id DESC",
                              (fid, sha))]


def _pruefen(fid, roh, dateiname, zuordnung=None):
    """Prüfung einer Datei für Probelauf und Übernehmen – schreibt nichts."""
    ziel = ziel_pruefen(fid)
    tab = tabelle.lesen(roh, dateiname)
    sp, nacharbeit_csv, kopf_index, warnungen = spalten(tab, zuordnung)
    b = Bericht(ziel, tab, (dateiname or "")[:200], sp, nacharbeit_csv, kopf_index, warnungen, fehlt(sp))
    b.schon_importiert = _schon_importiert(fid, tab.sha256)
    if b.schon_importiert:
        s = b.schon_importiert[0]
        warnungen.insert(0, f"Diese Datei wurde am {_tag(_ortszeit(s['am']).date().isoformat())} schon in diesen "
                            f"Ordner importiert ({s['angelegt']} Artikel). Zeilen mit Seriennummer erkennt der Import "
                            "wieder; Zeilen ohne Seriennummer würden noch einmal angelegt (mit neuer STR-Nummer).")
    daten, b.leerzeilen, ohne = datensaetze(tab, sp, kopf_index, nacharbeit_csv)
    b.datenzeilen = len(daten) + len(ohne)
    if ohne:
        liste = ", ".join(str(n) for n in ohne[:20]) + (" …" if len(ohne) > 20 else "")
        warnungen.append(f"{len(ohne)} Zeilen ohne Angaben in den zugeordneten Spalten werden übergangen (Zeile "
                         f"{liste}).")
    if b.fehlt:
        return b
    alte = _alte_zeilen(fid, [z["nacharbeit_nr"] for z in daten if z.get("nacharbeit_nr")])
    lauf = Lauf(ziel, heute(), alte)
    b.ergebnisse = zeilen_pruefen(daten, lauf)
    b.ordner_unbekannt = lauf.ordner_unbekannt
    if lauf.fremde_nr:
        warnungen.append(f"{lauf.fremde_nr} Nacharbeit-Nr. gehören nicht zur Nacharbeit dieses Ordners und werden "
                         "übergangen (dort bleiben die Zeilen offen).")
    if not daten:
        warnungen.append("Unter der Kopfzeile stehen keine Daten.")
    return b


def _protokollieren(fremde):
    """Eine Zeile im Protokoll der globalen Suche für alle fremden Dubletten eines Laufs – ohne Dateinamen (er kann
    Namen enthalten). Sonst wäre der Import eine unprotokollierte Abfrage fremder Seriennummern."""
    if fremde:
        globalprotokoll.eintragen("dublette", f"Bestandsimport: {len(fremde)} Seriennummern", fremde)


def probelauf(fid, roh, dateiname, zuordnung=None):
    """Probelauf: prüft alles, schreibt nichts – außer einer Zeile im Protokoll der globalen Suche, wenn der Bericht
    fremde Dubletten nennt."""
    with _laeuft():
        b = _pruefen(fid, roh, dateiname, zuordnung)
    _protokollieren(b.fremde)
    return b


def _ortszeit(iso):
    return datetime.fromisoformat(iso).astimezone(ZONE)


def uebernehmen(fid, roh, dateiname, zuordnung=None):
    """Übernehmen: dieselbe Prüfung, dann in EINER Transaktion – übernehmbare Zeilen werden Artikel (Nummern in
    Dateireihenfolge), der Rest kommt in die Nacharbeit, ersetzte Zeilen der Nacharbeit werden erledigt. Liefert
    (Bericht, Kennung des Imports)."""
    with _laeuft():
        b = _pruefen(fid, roh, dateiname, zuordnung)
        if b.fehlt:
            raise Abgelehnt(FEHLT_ZUORDNUNG)
        if not any(e.status in ("uebernehmbar", "nacharbeit") or e.alte_zeile for e in b.ergebnisse):
            raise Abgelehnt(NICHTS, 409)
        imp = _schreiben(b)
    _protokollieren(b.fremde)
    g.pop("mat_rueckruf_offen", None)
    return b, imp


def _schreiben(b):
    fid = b.ziel.id
    uid, name = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        grenze = (_jetzt_utc() - timedelta(minutes=WIEDERHOLUNG_MINUTEN)).isoformat()
        eben = db.query("SELECT * FROM mat_import WHERE folder_id = ? AND file_sha256 = ? AND created_at >= ? "
                        "ORDER BY id DESC LIMIT 1", (fid, b.tab.sha256, grenze), one=True)
        if eben:
            raise Abgelehnt(f"Diese Datei wurde um {_ortszeit(eben['created_at']).strftime('%H:%M')} von "
                            f"{eben['created_by_name'] or 'jemandem'} schon in diesen Ordner übernommen. Was offen "
                            "blieb, steht in der Nacharbeit.", 409)
        _baum_unveraendert(fid, {e.ordner_id for e in b.ergebnisse if e.status == "uebernehmbar"})
        imp = db.execute("INSERT INTO mat_import (folder_id, file_name, file_sha256, file_kind, created_by, "
                         "created_by_name, created_at) VALUES (?,?,?,?,?,?,?)",
                         (fid, b.dateiname, b.tab.sha256, b.tab.art, uid, name, ts))
        zahl = {"angelegt": 0, "im_bestand": 0, "nacharbeit": 0, "ersetzt": 0}
        for e in sorted(b.ergebnisse, key=lambda x: x.nr):
            if e.status == "uebernehmbar":
                _anlegen(e, {"bestandsimport": imp, "zeile": e.nr})
            if e.status == "nacharbeit":
                wahl = e.wahl or {}
                db.execute("INSERT INTO mat_import_row (import_id, line_no, values_json, reason_code, reason, offer_key, "
                           "product_id, request_id) VALUES (?,?,?,?,?,?,?,?)",
                           (imp, e.nr, json.dumps(e.werte, ensure_ascii=False), ",".join(c for c, _ in e.gruende),
                            " · ".join(t for _, t in e.gruende), e.angabe, wahl.get("product_id"),
                            wahl.get("request_id")))
            zahl["angelegt" if e.status == "angelegt" else "nacharbeit" if e.status == "nacharbeit"
                 else "im_bestand"] += 1
            if e.alte_zeile:
                if not db.execute_zeilen(
                        "UPDATE mat_import_row SET status = 'ersetzt', values_json = '{}', resolved_by = ?, "
                        "resolved_by_name = ?, resolved_at = ?, reason = ? WHERE id = ? AND status = 'offen'",
                        (uid, name, ts, f"neu eingelesen mit Bestandsimport Nr. {imp}, Zeile {e.nr}", e.alte_zeile)):
                    raise Abgelehnt(NACHARBEIT_GEAENDERT, 409)
                zahl["ersetzt"] += 1
        db.execute("UPDATE mat_import SET rows_total = ?, rows_created = ?, rows_existing = ?, rows_rework = ? "
                   "WHERE id = ?", (len(b.ergebnisse), zahl["angelegt"], zahl["im_bestand"], zahl["nacharbeit"], imp))
        journal.eintragen("folder", fid, "bestandsimport", None,
                          {"bestandsimport": imp, "datei": b.dateiname, "zeilen": len(b.ergebnisse),
                           "artikel_angelegt": zahl["angelegt"], "schon_im_bestand": zahl["im_bestand"],
                           "nacharbeit": zahl["nacharbeit"], "ersetzt": zahl["ersetzt"]})
    b.import_info = {"id": imp, "angelegt": zahl["angelegt"], "im_bestand": zahl["im_bestand"],
                     "nacharbeit": zahl["nacharbeit"], "ersetzt": zahl["ersetzt"]}
    return imp


def _anlegen(e, zusatz):
    """Eine übernehmbare Zeile unter der Schreibsperre: die Seriennummer noch einmal gegen den Bestand (jemand könnte
    seit der Prüfung angelegt haben) – sichtbar: schon im Bestand, fremd: Nacharbeit; sonst der Artikel."""
    if e.serie:
        k = bestand.serie_konflikt(e.produkt["id"], e.serie)
        if k and k["sichtbar"]:
            e.status, e.item_id = "im_bestand", k["item"]["id"]
            e.artikel = {"id": k["item"]["id"], "inventory_no": k["item"]["inventory_no"]}
            return
        if k:
            e.status, e.fremd = "nacharbeit", k["item"]["id"]
            e.grund("fremde_dublette", bestand.FremdeDublette.TEXT)
            e.gruende.sort(key=lambda g_: _RANG.get(g_[0], 99))
            return
    iid = bestand.artikel_schreiben(e.plan, dict(e.journal, **zusatz))
    i = db.query("SELECT id, inventory_no, serial_no FROM mat_item WHERE id = ?", (iid,), one=True)
    e.status, e.item_id = "angelegt", iid
    e.artikel = {"id": iid, "inventory_no": i["inventory_no"]}
    e.serie = i["serial_no"]


# --- Antworten ---------------------------------------------------------------------------------------------------

def _angabe_text(w):
    return " ".join(t for t in (w.get("hersteller"), w.get("modell"), w.get("artikelnummer")) if t)


def zeile_json(e):
    return {"nr": e.nr, "status": e.status, "gruende": [{"code": c, "text": t} for c, t in e.gruende],
            "hinweise": list(e.hinweise), "angabe": e.angabe, "angabe_text": _angabe_text(e.werte),
            "produkt": produkt_kurz(e.produkt), "seriennummer": e.serie or None, "ordner": e.ordner_text,
            "faellig": e.faellig if e.status in ("uebernehmbar", "angelegt") else None, "rueckruf": e.rueckruf,
            "bisherige_nummer": e.werte.get("inventarnummer"), "artikel": e.artikel}


def _zahlen(ergebnisse):
    z = {s: sum(1 for e in ergebnisse if e.status == s) for s in ("uebernehmbar", "angelegt", "im_bestand", "erledigt",
                                                                 "nacharbeit")}
    z["zeilen"] = len(ergebnisse)
    # Zeilen ohne Herstellerseriennummer, die eine STR-Nummer bekommen (Probelauf) bzw. bekommen haben.
    z["ohne_serie"] = sum(1 for e in ergebnisse if e.ohne_serie and e.status in ("uebernehmbar", "angelegt"))
    return z


def _hinweis_ohne_serie(ergebnisse):
    """Der Satz zu den STR-Nummern – vor dem Übernehmen und danach."""
    angelegt = sum(1 for e in ergebnisse if e.ohne_serie and e.status == "angelegt")
    if angelegt:
        return (f"{angelegt} Artikel ohne Herstellerseriennummer haben eine Seriennummer vom System (STR-…) bekommen – "
                "bitte am Artikel anbringen.")
    kommt = sum(1 for e in ergebnisse if e.ohne_serie and e.status == "uebernehmbar")
    if kommt:
        return f"{kommt} Zeilen ohne Seriennummer – bekommen eine STR-Nummer vom System (bitte am Artikel anbringen)."
    return None


def _faelligkeit(ergebnisse, stichtag):
    fertig = [e for e in ergebnisse if e.status in ("uebernehmbar", "angelegt")]
    return {"laut_liste_ueberfaellig": sum(1 for e in fertig if e.faellig_art == "liste"
                                           and e.faellig < stichtag.isoformat()),
            "ohne_pruefdatum": sum(1 for e in fertig if e.faellig_art == "ohne_datum"),
            "lebensdauer_erreicht": sum(1 for e in fertig if e.lebensdauer)}


def _produkte_offen(ergebnisse):
    out = {}
    for e in ergebnisse:
        code = e.gruende[0][0] if e.gruende else None
        if e.status != "nacharbeit" or code not in PRODUKT_ART:
            continue
        x = out.setdefault(e.angabe, {"angabe": e.angabe, "hersteller": e.werte.get("hersteller", ""),
                                      "modell": e.werte.get("modell", ""),
                                      "artikelnummer": e.werte.get("artikelnummer", ""), "zeilen": 0,
                                      "art": PRODUKT_ART[code]})
        x["zeilen"] += 1
    return sorted(out.values(), key=lambda x: (-x["zeilen"], x["angabe"]))


def bericht_json(b):
    """Der Bericht in der Gestalt der Schnittstelle (Bauentwurf 8.5)."""
    t = b.tab
    out = {"datei": {"name": b.dateiname, "art": t.art, "kodierung": t.kodierung, "trennzeichen": t.trennzeichen,
                     "kopfzeile": b.kopf_index + 1, "datenzeilen": b.datenzeilen, "leerzeilen": b.leerzeilen},
           "nacharbeit_csv": b.nacharbeit_csv, "spalten": b.spalten, "felder": felder_json(), "fehlt": b.fehlt,
           "warnungen": list(b.warnungen) + [t for t in (_hinweis_ohne_serie(b.ergebnisse),) if t],
           "schon_importiert": b.schon_importiert,
           "zahlen": _zahlen(b.ergebnisse), "faelligkeit": _faelligkeit(b.ergebnisse, heute()),
           "produkte_offen": _produkte_offen(b.ergebnisse),
           "ordner_unbekannt": [{"wert": w, "zeilen": n} for w, n in sorted(b.ordner_unbekannt.items(),
                                                                          key=lambda x: (-x[1], x[0]))],
           "zeilen": [zeile_json(e) for e in b.ergebnisse], "frist": FRIST_TEXT}
    if b.import_info:
        out["import"] = b.import_info
    return out


# --- Nacharbeit --------------------------------------------------------------------------------------------------

def _offene_sql():
    return ("SELECT r.*, i.file_name, i.created_at AS import_am, i.folder_id FROM mat_import_row r "
            "JOIN mat_import i ON i.id = r.import_id WHERE i.folder_id = ? AND r.status = 'offen' "
            "ORDER BY r.import_id, r.line_no, r.id")


def zeilen_laden(fid, zeilen, nur_offen=True):
    """Die Zeilen einer Aktion: Liste von Kennungen oder „alle“ (alle offenen des Ziels). Jede Kennung muss zu einem
    Import mit genau diesem Zielordner gehören – sonst 404 wie für eine unbekannte; schon erledigte: 409."""
    if zeilen == "alle":
        rows = db.query(_offene_sql(), (fid,))
        if not rows:
            raise Abgelehnt("In der Nacharbeit ist nichts offen.", 409)
        return rows
    if not isinstance(zeilen, list) or not zeilen:
        raise Abgelehnt("Bitte Zeilen auswählen (Liste von Nacharbeit-Nr. oder „alle“).")
    if len(zeilen) > AUSWAHL_MAX:
        raise Abgelehnt(f"Höchstens {AUSWAHL_MAX} Zeilen auf einmal.")
    ids = [kennung(x, "Zeile") for x in zeilen]
    rows = db.query("SELECT r.*, i.file_name, i.created_at AS import_am, i.folder_id FROM mat_import_row r "
                    "JOIN mat_import i ON i.id = r.import_id WHERE i.folder_id = ? "
                    "AND r.id IN (SELECT value FROM json_each(?)) ORDER BY r.import_id, r.line_no, r.id",
                    (fid, _liste(ids)))
    if len(rows) != len(set(ids)):
        raise Abgelehnt(ZEILE_FEHLT, 404)
    if nur_offen and any(r["status"] != "offen" for r in rows):
        raise Abgelehnt(SCHON_ERLEDIGT, 409)
    return rows


def _gruende_aus(r):
    codes = [c for c in (r["reason_code"] or "").split(",") if c]
    texte = (r["reason"] or "").split(" · ") if r["reason"] else []
    if len(codes) == len(texte):
        return [{"code": c, "text": t} for c, t in zip(codes, texte)]
    return [{"code": codes[0] if codes else "", "text": r["reason"] or ""}]


def _gruppe(r):
    return GRUPPE_VON.get((r["reason_code"] or "").split(",")[0], "sonstige")


def offen_im_ordner(fid):
    """Offene Zeilen der Nacharbeit mit genau diesem Zielordner."""
    return db.query("SELECT COUNT(*) AS n FROM mat_import_row r JOIN mat_import i ON i.id = r.import_id "
                    "WHERE i.folder_id = ? AND r.status = 'offen'", (fid,), one=True)["n"]


def offen_uebersicht():
    """Für die Übersicht: je Zielordner, den das Konto verwaltet, die Zahl offener Zeilen (höchstens 20)."""
    rows = db.query(f"SELECT i.folder_id, COUNT(*) AS n FROM mat_import_row r JOIN mat_import i ON i.id = r.import_id "
                    f"WHERE r.status = 'offen' AND {rechte.ordner_filter('i.folder_id', 'verwalten')} "
                    f"GROUP BY i.folder_id ORDER BY n DESC, i.folder_id LIMIT 20")
    return [{"ordner": {"id": r["folder_id"], "pfad": bestand._pfad_text(r["folder_id"])}, "offen": r["n"]}
            for r in rows]


def _meldung_json(mid):
    m = db.query("SELECT * FROM mat_product_request WHERE id = ?", (mid,), one=True) if mid else None
    if not m:
        return None
    p = db.query("SELECT * FROM mat_product WHERE id = ?", (m["product_id"],), one=True) if m["product_id"] else None
    return {"id": m["id"], "status": m["status"], "antwort": m["answer"], "produkt": produkt_kurz(p)}


def nacharbeit_json(fid, gruppe=None, seite=1):
    """Die Nacharbeit eines Zielordners: Zahlen je Gruppe, Produktangaben (Karten), offene Zeilen seitenweise
    (Filter gruppe), die zuletzt erledigten."""
    if gruppe in (None, "", "alle"):
        gruppe = None
    elif gruppe not in dict(GRUPPEN):
        raise Abgelehnt("Unbekannte Gruppe.")
    offen = db.query(_offene_sql(), (fid,))
    zahlen = {"offen": len(offen), **{gname: 0 for gname, _ in GRUPPEN}}
    for r in offen:
        zahlen[_gruppe(r)] += 1
    demo = bestand.ordner_ist_demo(fid)
    produkte = {}

    def kurz(pid):
        if pid not in produkte:
            produkte[pid] = produkt_kurz(db.query("SELECT * FROM mat_product WHERE id = ?", (pid,), one=True))
        return produkte[pid]
    karten = {}
    for r in offen:
        code = (r["reason_code"] or "").split(",")[0]
        if code in PRODUKT_ART:
            karten.setdefault(r["offer_key"], []).append(r)
    gruppen = []
    for angabe, rows in sorted(karten.items(), key=lambda x: (-len(x[1]), x[0]))[:GRUPPEN_MAX]:
        w = json.loads(rows[0]["values_json"] or "{}")
        h, m, a = w.get("hersteller", ""), w.get("modell", ""), w.get("artikelnummer", "")
        wahl = {r["product_id"] for r in rows}
        t = produkt_finden(h, m, a, demo)
        vorschlaege = ([t["produkt"]] if t["produkt"] else []) + t["vorschlaege"]
        gruppen.append({"angabe": angabe, "hersteller": h, "modell": m, "artikelnummer": a, "offen": len(rows),
                        "art": PRODUKT_ART[(rows[0]["reason_code"] or "").split(",")[0]],
                        "produkt": kurz(wahl.pop()) if len(wahl) == 1 and None not in wahl else None,
                        "meldung": _meldung_json(next((r["request_id"] for r in rows if r["request_id"]), None)),
                        "vorschlaege": [produkt_kurz(p) for p in vorschlaege[:5]]})
    gefiltert = [r for r in offen if gruppe is None or _gruppe(r) == gruppe]
    seiten = max(1, -(-len(gefiltert) // SEITE))
    seite = min(max(1, int(seite or 1)), seiten)
    zeilen = [{"id": r["id"], "nr": r["line_no"],
               "import": {"id": r["import_id"], "datei": r["file_name"], "am": r["import_am"]},
               "gruende": _gruende_aus(r), "werte": json.loads(r["values_json"] or "{}"), "angabe": r["offer_key"],
               "produkt": kurz(r["product_id"]) if r["product_id"] else None, "offen_bis": offen_bis(r["import_am"])}
              for r in gefiltert[(seite - 1) * SEITE:seite * SEITE]]
    erledigt = []
    for r in db.query("SELECT r.* FROM mat_import_row r JOIN mat_import i ON i.id = r.import_id WHERE i.folder_id = ? "
                      "AND r.status <> 'offen' ORDER BY r.resolved_at DESC, r.id DESC LIMIT ?", (fid, ERLEDIGT_MAX)):
        erledigt.append({"id": r["id"], "nr": r["line_no"], "status": r["status"], "grund": r["reason"],
                         "artikel": _artikel_ref(r["item_id"]), "von": r["resolved_by_name"], "am": r["resolved_at"]})
    return {"zahlen": zahlen, "felder": [{"feld": f, "text": t} for f, t in FELDER if f != "ignorieren"],
            "gruppen": gruppen, "zeilen": zeilen, "seite": seite, "seiten": seiten, "erledigt": erledigt,
            "frist": FRIST_TEXT}


def produkt_setzen(fid, product_id, angabe=None, zeilen=None):
    """Ein Produkt den offenen Zeilen einer Angabe (Karte) oder den gewählten Zeilen zuordnen – None nimmt die Wahl
    zurück. Prüft und übernimmt nicht (das macht „erneut prüfen“); kein Journal. Liefert die Zahl der Zeilen."""
    if (angabe is None) == (zeilen is None):
        raise Abgelehnt("Bitte eine Produktangabe oder Zeilen wählen.")
    if zeilen is not None:
        ids = [r["id"] for r in zeilen_laden(fid, zeilen)]
    else:
        if not isinstance(angabe, str) or not angabe:
            raise Abgelehnt("Bitte eine Produktangabe wählen.")
        ids = [r["id"] for r in db.query(_offene_sql(), (fid,)) if r["offer_key"] == angabe]
        if not ids:
            raise Abgelehnt(ZEILE_FEHLT, 404)
    pid = kennung(product_id, "Produkt", leer_erlaubt=True)
    if pid is not None:
        p = katalog.produkt(pid)
        if p["demo"] and not bestand.ordner_ist_demo(fid):
            raise Abgelehnt(DEMO_PRODUKT)
    with db.transaction(sofort=True):
        n = db.execute_zeilen("UPDATE mat_import_row SET product_id = ? WHERE status = 'offen' "
                              "AND id IN (SELECT value FROM json_each(?))", (pid, _liste(ids)))
        if n != len(ids):
            raise Abgelehnt(SCHON_ERLEDIGT, 409)
    return n


def melden(fid, angabe, d, fotos):
    """„Produkt melden“ aus der Nacharbeit: die vorhandene Meldung (meldung.anlegen) mit Zielordner, vorbelegt mit
    Hersteller, Modell und Artikelnummer der Angabe (der Dialog kann sie ändern), ohne Bemerkung mit einem Satz zum
    Import (ohne Dateinamen). Danach hängt die Meldung an allen offenen Zeilen der Angabe."""
    if not isinstance(angabe, str) or not angabe:
        raise Abgelehnt("Bitte eine Produktangabe wählen.")
    rows = [r for r in db.query(_offene_sql(), (fid,)) if r["offer_key"] == angabe]
    if not rows:
        raise Abgelehnt(ZEILE_FEHLT, 404)
    w = json.loads(rows[0]["values_json"] or "{}")
    daten = {"manufacturer": w.get("hersteller", ""), "model": w.get("modell", ""),
             "article_no": w.get("artikelnummer", "")}
    for k in d.keys():
        if k not in ("folder_id", "angabe", "fotos") and d.get(k) not in (None, ""):
            daten[k] = d.get(k)
    if not (daten.get("note") or "").strip():
        daten["note"] = (f"Aus dem Bestandsimport Nr. {rows[0]['import_id']}: {len(rows)} Artikel warten in der "
                         "Nacharbeit.")
    daten["folder_id"] = fid
    mid = meldung.anlegen(daten, fotos)
    db.execute("UPDATE mat_import_row SET request_id = ? WHERE status = 'offen' AND offer_key = ? "
               "AND import_id IN (SELECT id FROM mat_import WHERE folder_id = ?)", (mid, angabe, fid))
    return mid


def nachpruefen(fid, zeilen, uebernehmen=False):
    """Erneut prüfen (Bericht wie der Probelauf; schreibt nichts außer der einen Protokollzeile) – mit uebernehmen in
    EINER Transaktion: übernehmbare Zeilen werden Artikel, gefundene „schon im Bestand“, weiter offene bekommen ihre
    neuen Gründe. Geprüft wird auf den gespeicherten Werten; doppelt nur unter den gewählten Zeilen und gegen den
    Bestand."""
    rows = zeilen_laden(fid, zeilen)
    if len(rows) > AUSWAHL_MAX:
        raise Abgelehnt(f"Höchstens {AUSWAHL_MAX} Zeilen auf einmal – bitte filtern oder auswählen.")
    with _laeuft():
        ziel = ziel_pruefen(fid)
        daten = [{"nr": r["line_no"], "werte": json.loads(r["values_json"] or "{}"), "zeile_id": r["id"],
                  "import_id": r["import_id"], "wahl": {"product_id": r["product_id"], "request_id": r["request_id"]}}
                 for r in rows]
        lauf = Lauf(ziel, heute(), mehrfach_text="in der Auswahl", zeilen_wort="Nacharbeit-Nr.")
        ergebnisse = zeilen_pruefen(daten, lauf)
        if uebernehmen:
            _nacharbeit_schreiben(fid, ergebnisse)
    _protokollieren([e.fremd for e in ergebnisse if e.fremd])
    if uebernehmen:
        g.pop("mat_rueckruf_offen", None)
    zeilen_out = []
    for e in ergebnisse:
        z = zeile_json(e)
        z["id"] = e.zeile_id
        zeilen_out.append(z)
    return {"zahlen": _zahlen(ergebnisse), "faelligkeit": _faelligkeit(ergebnisse, heute()), "zeilen": zeilen_out,
            "hinweise": [t for t in (_hinweis_ohne_serie(ergebnisse),) if t]}


def _nacharbeit_schreiben(fid, ergebnisse):
    uid, name = akteur()
    ts = db.now()
    with db.transaction(sofort=True):
        offen = {r["id"] for r in db.query("SELECT id FROM mat_import_row WHERE status = 'offen' "
                                           "AND id IN (SELECT value FROM json_each(?))",
                                           (_liste(e.zeile_id for e in ergebnisse),))}
        if len(offen) != len(ergebnisse):
            raise Abgelehnt(SCHON_ERLEDIGT, 409)
        _baum_unveraendert(fid, {e.ordner_id for e in ergebnisse if e.status == "uebernehmbar"})
        zahl = {"angelegt": 0, "im_bestand": 0}
        for e in sorted(ergebnisse, key=lambda x: (x.import_id, x.nr)):
            if e.status == "uebernehmbar":
                _anlegen(e, {"bestandsimport": e.import_id, "zeile": e.nr, "aus_nacharbeit": True})
            if e.status in ("angelegt", "im_bestand"):
                zahl[e.status] += 1
                db.execute("UPDATE mat_import_row SET status = ?, item_id = ?, values_json = '{}', resolved_by = ?, "
                           "resolved_by_name = ?, resolved_at = ? WHERE id = ?",
                           ("uebernommen" if e.status == "angelegt" else "im_bestand", e.item_id, uid, name, ts,
                            e.zeile_id))
            else:
                db.execute("UPDATE mat_import_row SET reason_code = ?, reason = ? WHERE id = ?",
                           (",".join(c for c, _ in e.gruende), " · ".join(t for _, t in e.gruende), e.zeile_id))
        if zahl["angelegt"] or zahl["im_bestand"]:
            journal.eintragen("folder", fid, "nacharbeit_uebernommen", None,
                              {"artikel_angelegt": zahl["angelegt"], "schon_im_bestand": zahl["im_bestand"]})


def verwerfen(fid, zeilen):
    """Offene Zeilen verwerfen – Werte geleert, Journal am Ziel. Liefert die Zahl."""
    rows = zeilen_laden(fid, zeilen)
    uid, name = akteur()
    with db.transaction(sofort=True):
        n = db.execute_zeilen("UPDATE mat_import_row SET status = 'verworfen', values_json = '{}', resolved_by = ?, "
                              "resolved_by_name = ?, resolved_at = ? WHERE status = 'offen' "
                              "AND id IN (SELECT value FROM json_each(?))",
                              (uid, name, db.now(), _liste(r["id"] for r in rows)))
        if n != len(rows):
            raise Abgelehnt(SCHON_ERLEDIGT, 409)
        journal.eintragen("folder", fid, "nacharbeit_verworfen", None, {"zeilen": n})
    return n


def nacharbeit_csv(fid):
    """Alle offenen Zeilen des Ziels als CSV (NACHARBEIT_SPALTEN, „;“, UTF-8 mit BOM, Formelschutz). Korrigiert und in
    denselben Ordner wieder hochgeladen, erkennt der Import sie an „Nacharbeit-Nr.“ und erledigt die alten Zeilen.
    Liefert (Bytes, Dateiname)."""
    o = bestand.ordner(fid)
    zeilen = []
    for r in db.query(_offene_sql(), (fid,)):
        w = json.loads(r["values_json"] or "{}")
        zeilen.append([r["id"] if t == NACHARBEIT_NR else r["reason"] if t == "Grund" else r["line_no"] if t == "Zeile"
                       else w.get(f, "") for t, f in NACHARBEIT_SPALTEN])
    daten = export.csv_bytes([t for t, _ in NACHARBEIT_SPALTEN], zeilen)
    return daten, f"Nacharbeit_{export.dateiname(o['name'])}_{heute().isoformat()}.csv"


def _frist_grenze():
    """Imports vor diesem Tag (UTC) sind abgelaufen: heute minus FRIST_MONATE."""
    return plus_monate(_jetzt_utc().date(), -FRIST_MONATE).isoformat()


def offen_bis(import_am):
    """Bis zu diesem Tag (einschließlich) bleibt eine offene Zeile eines Imports vom import_am stehen."""
    return plus_monate(datetime.fromisoformat(import_am).astimezone(timezone.utc).date(), FRIST_MONATE).isoformat()


_FRIST_SQL = ("UPDATE mat_import_row SET status = 'verworfen', values_json = '{}', resolved_by = NULL, "
              "resolved_by_name = 'System', resolved_at = ?, reason = ? WHERE status = 'offen' "
              "AND import_id IN (SELECT id FROM mat_import WHERE created_at < ?)")
_FRIST_GRUND = "verworfen nach einem Monat ohne Bearbeitung"


def aufraeumen(conn=None):
    """Offene Zeilen aus Importen, die älter als FRIST_MONATE sind, werden verworfen (Werte geleert, „System“, kein
    Journal – die Zeile sagt selbst, warum sie zu ist). conn: die Verbindung des Startlaufs (überspringt sich, solange
    Schritt 12 fehlt); ohne conn die der Anfrage bzw. des Tageslaufs – geschrieben wird nur, wenn etwas abgelaufen ist.
    Liefert die Zahl der Zeilen."""
    grenze, jetzt = _frist_grenze(), _jetzt_utc().isoformat()
    if conn is not None:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'mat_import_row'").fetchone():
            return 0
        n = conn.execute(_FRIST_SQL, (jetzt, _FRIST_GRUND, grenze)).rowcount
        conn.commit()
        return n
    if not db.query("SELECT 1 FROM mat_import_row r JOIN mat_import i ON i.id = r.import_id WHERE r.status = 'offen' "
                    "AND i.created_at < ? LIMIT 1", (grenze,), one=True):
        return 0
    return db.execute_zeilen(_FRIST_SQL, (jetzt, _FRIST_GRUND, grenze))
