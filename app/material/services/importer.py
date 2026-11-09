"""Katalogimport – der Weg, auf dem die Ergebnisse aus Phase 0 (Produkte, Intervalle, Lebensdauern,
Prüfformulare der Sachkundigen) ins System kommen; seit Lieferung 4 auch der Katalog einer anderen Instanz
(Katalog-Export, katalog_export.py – etwa von dev in die Produktion).

    flask --app "app:create_app()" material import-catalog katalog.zip|katalog.json [--trocken]
    POST /api/material/katalog/import  (Datei „file“, Feld „trocken“)

Der Import läuft durch dieselben Regeln wie die Oberfläche (katalog.py) und ist ganz oder gar nicht:
Findet er auch nur einen Fehler, wird nichts gespeichert, und der Bericht nennt jeden Fehler mit
seiner Stelle in der Datei. Er ist wiederholbar: Vorhandene Kategorien (gleicher Name an gleicher
Stelle) und Produkte (gleiche Dublette Hersteller + Modell + Artikelnummer) werden abgeglichen statt
doppelt angelegt; ein Formular, dessen Prüfpunkte sich nicht geändert haben, bleibt bei seiner
Version. Das Format steht in CHANGELOG-Material.md. Einzige Ausnahme von den Regeln der Oberfläche: Die Beschreibung
eines Produkts darf länger sein als katalog.BESCHREIBUNG_MAX und mehrzeilig – Beschreibungen von vor dieser Grenze
kommen unverändert herein, der Austausch dev → Produktion scheitert nicht an ihnen. In der Oberfläche und im Bericht
heißt sie seit dem Wunsch vom 18.10.2026 „Bemerkung“; die Datei nennt sie weiter „beschreibung“ (so schreibt der
Export), gleichwertig nimmt der Import „bemerkung“ an (_bemerkung_pruefen).

Format 2 (ZIP mit katalog.json und den Dateien; als reine JSON-Datei nur ohne Dateien) bringt dazu:
  - die Katalogkennung uid an Kategorien und Produkten. Abgeglichen wird zuerst über sie, sonst wie oben – dann
    übernimmt der Datensatz hier die uid der Datei, und der nächste Lauf findet ihn auch nach Umbenennen oder
    Verschieben wieder.
  - Produktbilder (gleich heißt: gleiche SHA-256 des Originals) und die aktuellen Dokumente an Kategorien und
    Produkten, je Dokument mit den Kennungen seiner früheren Versionen („vorgaenger“) – daran findet eine neue Version
    ihre Kette hier, auch wenn mehrere Dokumente gleich heißen.
  Gelöscht, zurückgezogen oder deaktiviert wird nie etwas: Was hier mehr ist als in der Datei, bleibt.
  Ausnahme seit Schritt 25: Die Bestandteil-Liste eines Produkts („bestandteile“, je Position {bezeichnung, anzahl}, nur
  Text) wird als Ganzes ersetzt (Journal am Produkt, gleich heißt unverändert, gezählt unter „bestandteillisten“); []
  entfernt sie, ohne den Schlüssel bleibt sie, wie sie ist – in einem zweiten Durchgang nach allen Produkten der Datei.
  Positionen außerhalb der Regeln (stueckliste.py) sind Fehler dieses Produkts; eine Liste aus Texten (Recherche-
  Manifeste) ist ein Hinweis und wird übergangen. Auch in Format 1 gelesen.
  Seit dem Rückbau der Set-Funktion (Schritt 26, Wunsch vom 25.10.2026) ist „set“: true ein Fehler dieses Produkts
  (SET_ENTFALLEN – wie jeder Fehler wird dann nichts gespeichert); „set“: false wird übergangen.
Format 3 (seit Schritt 38, Formular-Pool; Entscheidungen vom 04.11.2026) – Kategorien und Produkte wie Format 2, die
Formulare als Einträge des Pools: {uid, kategorie/kategorie_uid (Heimat), titel, punkte, standard_fuer: [{kategorie,
kategorie_uid}], zugewiesen: [{uid, hersteller, modell, artikelnummer}]}. Der Export schreibt nur Formulare mit aktiver
Version (E1); hier wird das Formular aktiv – eine neue Version, wenn Titel oder Prüfpunkte von der aktiven abweichen,
sonst bleibt alles (zweiter Import ändert nichts). Abgeglichen über die uid, sonst über den Titel in derselben Heimat (E3);
ein Verschieben in eine andere Heimat gibt es nicht (Fehler). Die Datei ist für Zuweisungen maßgeblich (E2): Für jedes
Formular und jedes Ziel der Datei gilt danach genau, was sie sagt – eine Zuweisung hier, die sie nicht nennt, wird
gelöst (_zuweisungen). Einzige Ausnahme von „gelöscht wird nie etwas“ außer der Bestandteil-Liste.
Seit Schritt 39 trägt ein Prüfpunkt „untergruppe“ (in jedem Format gelesen; fehlt das Feld, ist sie leer) – sie zählt
beim Vergleich mit der aktiven Version mit (_PUNKTFELDER).
Ältere Dateien (Format 1/2) kommen weiter herein: Ein Formular mit „kategorie“ kommt in deren Pool und wird ihr Standard,
eins mit „produkt“ in den Pool der Kategorie des Produkts und ihm zugewiesen (mit „aktivieren“: false nur als Version,
ohne Zuweisung); „formular_von“ an einem Produkt (Schritt 35) wird die Zuweisung an das Formular, das der Quelle hier
zugewiesen ist (sonst ein Hinweis), null ändert nichts mehr. Nichts davon löst eine Zuweisung.
In jedem Format: Der Import übernimmt nie ein DEMO-Kennzeichen (ein Feld „demo“ der Datei zählt nicht) und nimmt ein
führendes „DEMO“ aus Formulartiteln („DEMO – “, „DEMO-“, „DEMO “); ein leerer Titel (ältere Dateien) wird „Prüfformular
<Kategorie bzw. Produkt>“ – Titel sind Pflicht.

Dateien sind nicht Teil der Datenbanktransaktion. Ein Probelauf schreibt deshalb keine einzige. Der echte Lauf
ermittelt erst in einem Probedurchgang, welche Dateien er braucht, legt nur diese ab – außerhalb der Schreibsperre,
denn die Bildverarbeitung dauert – und schreibt dann die Datenbank. Scheitert das, verschwinden die neu abgelegten
Dateien wieder; ersetzte Produktbilder werden erst nach dem Commit gelöscht.

Seit dem 24.10.2026 läuft der Import der Oberfläche im Hintergrund (importauftrag.py). Dafür nehmen datei_importieren
und importieren einen optionalen Rückruf fortschritt(phase, n=None, m=None, abgelegt=None) an; er ändert nichts am
Ablauf, ohne ihn (Kommandozeile) ist alles wie vorher. Phasen: „pruefen“ (Datei lesen, dann n von m Dateien geprüft),
„probe“ (Probedurchgang bzw. der ganze Probelauf), „ablegen“ (n von m Dateien abgelegt; abgelegt nennt jede eben
abgelegte Datei als (Art, abgelegt) – damit räumt der Auftrag auf, wenn sein Prozess mitten im Lauf endet) und
„schreiben“ (der Durchgang, der die Datenbank schreibt; legt er selbst eine Datei nach, kommt sie ebenso mit abgelegt).
Gleich nach dem Commit kommt „gespeichert“ (ohne Zahlen) – daran erkennt der Auftrag nach einem Abbruch, ob die Datenbank
schon geschrieben war (Nachbesserung nach der Sicherheitsprüfung vom 24.10.2026).
"""
import hashlib
import json
import logging
import os
import re
import sqlite3
import zipfile
import zlib

from flask import g
from PIL import Image
from werkzeug.datastructures import FileStorage

from ... import db
from ...images import ALLOWED_EXT, MAX_PIXEL, delete_photo_files
from ..models import MATERIALARTEN
from . import Abgelehnt, akteur, heute, journal, katalog, stueckliste, text, wahr
from .faelligkeit import in_kategorie
from .interval import herstellerseite

log = logging.getLogger(__name__)

FORMAT = "stroemis-material-katalog"
VERSIONEN = (1, 2, 3)

# Grenzen für Katalogdateien: Upload der Route (routes.py), Export (katalog_export.py) und das Archiv, bevor
# irgendetwas daraus gelesen wird. Ein Katalog mit Bildern und Herstellerdokumenten hat schnell einige hundert
# Megabyte; die Bilder und PDF darin packen sich kaum, mehr als 2 GB hat keiner.
ZIP_MAX_BYTES = 2 * 1024 ** 3
MAX_EINTRAEGE = 20_000                 # Einträge im Archiv
# Bytes im Inhaltsverzeichnis: Ein Eintrag eines Exports braucht dort gut 130 (46 Kopf, dazu der Pfad), andere
# Packprogramme legen Zeitstempel dazu. zipfile liest das Verzeichnis nach dieser Größe ein, nicht nach der Zahl.
MAX_VERZEICHNIS = MAX_EINTRAEGE * 256
MAX_ENTPACKT = 3 * 1024 ** 3           # Summe der entpackten Größen laut Inhaltsverzeichnis
JSON_MAX_BYTES = 5 * 1024 * 1024       # katalog.json bzw. eine reine JSON-Datei
MAX_VERHAELTNIS = 100                  # entpackt zu gepackt je Eintrag ab 1 MB – mehr ist eine Packbombe
MAX_TIEFE = 30                         # Ebenen im Kategorienbaum
MAX_LISTE = 2000                       # Zeilen in der Änderungsliste des Berichts
MAX_VORGAENGER = 1000                  # Kennungen früherer Versionen je Dokument
# Produktbilder: dieselbe Grenze wie beim Hochladen. Dort begrenzt nur die ganze Anfrage (routes.UPLOAD_GRENZEN:
# BILD_MAX_BYTES + 1 MB) – ein angenommenes Original kann also etwas größer sein als BILD_MAX_BYTES, und der Import
# darf es dann nicht abweisen. Dokumente prüft schon das Hochladen genau gegen DOK_MAX_BYTES.
BILD_MAX_IMPORT = katalog.BILD_MAX_BYTES + 1024 * 1024
_UID = re.compile(r"[0-9a-f]{32}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# Was beim Lesen eines Archiveintrags schiefgehen kann: kaputte Kompression, falsche Prüfsumme (CRC),
# Verschlüsselung, abgeschnittene Datei, unbekanntes Packverfahren.
_LESEFEHLER = (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, RuntimeError, OSError,
               NotImplementedError, ValueError)

# Für die Änderungsliste: welche Felder sich geändert haben, in Worten.
_FELDNAMEN = {"name": "Name", "parent_id": "Oberkategorie", "norm": "Norm", "default_material_kind": "Materialart",
              "default_interval_months": "Prüfintervall", "default_lifetime_years": "Lebensdauer",
              "position": "Reihenfolge", "category_id": "Kategorie", "manufacturer": "Hersteller", "model": "Modell",
              "article_no": "Artikelnummer", "material_kind": "Materialart", "interval_months": "Prüfintervall",
              "lifetime_years": "Lebensdauer", "lifetime_source": "Fundstelle der Lebensdauer",
              "description": "Bemerkung"}


class _Rueckgaengig(Exception):
    pass


class _Konflikt(Exception):
    """Ein Namens-, Dubletten- oder Artikelnummernkonflikt mit einem Datensatz hier, gemeldet von einer Regel aus
    katalog.py, bevor sie etwas geschrieben hat. Ein späterer Eintrag der Datei kann ihn auflösen – die übliche Kette
    „das alte Modell bekommt einen Zusatz, das neue den alten Namen“ –, deshalb wird der Eintrag zurückgestellt
    (_nachholen) statt gleich als Fehler gemeldet."""


def _ohne_konflikt(regel, *args, **kwargs):
    """regel aus katalog.py aufrufen; ihr Abgelehnt mit 409 wird zum _Konflikt."""
    try:
        return regel(*args, **kwargs)
    except Abgelehnt as exc:
        if exc.code == 409:
            raise _Konflikt(str(exc)) from exc
        raise


def _name(wert, was="Name", n=120):
    """Ein Name, vereinheitlicht wie beim Speichern (Leerraum zusammengezogen, Steuerzeichen raus) –
    sonst fände ein zweiter Lauf „PSA  gegen Absturz“ nicht wieder, was der erste gespeichert hat."""
    return text({"wert": wert}, "wert", was, n)


def _pfad(wert):
    """Kategoriepfad: Liste von Namen oder ein Text mit „ / “ dazwischen."""
    if isinstance(wert, str):
        teile = [_name(t) for t in wert.split(" / ")]
    elif isinstance(wert, list) and all(isinstance(t, str) for t in wert):
        teile = [_name(t) for t in wert]
    else:
        raise Abgelehnt("„kategorie“ muss ein Pfad sein (Liste von Namen oder „Ober / Unter“).")
    if not teile or not all(teile):
        raise Abgelehnt("Der Kategoriepfad ist leer.")
    return teile


def _kategorie_finden(pfad):
    parent = None
    for name in pfad:
        k = db.query("SELECT * FROM mat_category WHERE COALESCE(parent_id, 0) = ? AND name = ? COLLATE NOCASE",
                     (parent or 0, name), one=True)
        if not k:
            raise Abgelehnt(f"Kategorie „{' / '.join(pfad)}“ gibt es nicht (weder im Katalog noch in der Datei).")
        parent = k["id"]
    return parent


_KATEGORIE_ABBILDUNG = {"norm": "norm", "materialart": "default_material_kind",
                        "intervall_monate": "default_interval_months", "lebensdauer_jahre": "default_lifetime_years",
                        "position": "position", "artikel_laenge": "items_have_length"}
_PRODUKT_ABBILDUNG = {"hersteller": "manufacturer", "modell": "model", "artikelnummer": "article_no", "norm": "norm",
                      "materialart": "material_kind", "intervall_monate": "interval_months",
                      "lebensdauer_jahre": "lifetime_years", "lebensdauer_quelle": "lifetime_source",
                      "beschreibung": "description", "bemerkung": "description"}


# Schlüssel, deren null wie „fehlt“ gilt (bleibt unverändert) – „artikel_laenge“: null nähme das Häkchen sonst weg
# wie false (Prüfung der Länge, V8).
_NULL_WIE_FEHLT = ("artikel_laenge",)


def _abbilden(eintrag, abbildung):
    return {ziel: eintrag[quelle] for quelle, ziel in abbildung.items()
            if quelle in eintrag and not (quelle in _NULL_WIE_FEHLT and eintrag[quelle] is None)}


def _bericht():
    return {"kategorien": {"neu": 0, "geaendert": 0, "unveraendert": 0},
            "produkte": {"neu": 0, "geaendert": 0, "unveraendert": 0},
            "formulare": {"neu": 0, "unveraendert": 0},
            "zuweisungen": {"neu": 0, "geloest": 0, "unveraendert": 0},
            "bilder": {"neu": 0, "geaendert": 0, "unveraendert": 0},
            "dokumente": {"neu": 0, "neue_version": 0, "unveraendert": 0},
            "bestandteillisten": {"neu": 0, "geaendert": 0, "unveraendert": 0},
            "kategoriewechsel": None,
            "aenderungen": [], "hinweise": [], "warnungen": [], "fehler": [], "gespeichert": False}


def aktuelle_dokumente(spalte, ziel):
    """Die aktuellen Dokumente eines Produkts oder einer Kategorie (spalte product_id bzw. category_id): je Kette die
    neueste Version, sofern nicht zurückgezogen – wie bei „Variante anlegen“. Neueste zuerst."""
    return db.query(f"SELECT * FROM mat_product_document d WHERE {spalte} = ? "
                    "AND (withdrawn_on IS NULL OR withdrawn_on > ?) "
                    "AND NOT EXISTS (SELECT 1 FROM mat_product_document n WHERE n.replaces_id = d.id) "
                    "ORDER BY id DESC", (ziel, heute().isoformat()))


# --- Ein Durchgang über die Datei ------------------------------------------------------------------

class _Lauf:
    """Zustand eines Durchgangs. Ohne ablage plant er nur (Probelauf und erster Durchgang des echten Laufs): Eine
    Datei, die er neu bräuchte, merkt er in bedarf vor und schreibt einen Platzhalter, der mit der Transaktion
    verschwindet. Mit ablage nimmt er die vorher abgelegten Dateien – und legt nur selbst ab, wenn sich die
    Datenbank seit dem Probedurchgang geändert hat und er eine Datei mehr braucht."""

    def __init__(self, version, dateien, archiv, uids=({}, {}), ablage=None, fortschritt=None):
        self.version, self.dateien, self.archiv = version, dateien, archiv
        self.fortschritt = fortschritt        # Rückruf des Hintergrundauftrags, siehe oben
        self.kategorie_uids, self.produkt_uids = set(uids[0]), set(uids[1])
        self.planen = ablage is None
        self.ablage = ablage or {}            # Fundstelle → (Art, abgelegt)
        self.benutzt = set()                  # Fundstellen der Ablage, die dieser Durchgang verwendet hat
        self.bedarf = {}                      # Fundstelle → geprüfte Datei aus dem Archiv
        self.abgelegt = []                    # (Art, abgelegt), im Durchgang selbst abgelegt
        self.alte_bilder = []                 # ersetzte Produktbilder – gelöscht erst nach dem Commit
        self.belegt = set()                   # Dokumente hier, die schon einem Eintrag der Datei entsprechen
        self.summen = {}                      # Produktbild hier → SHA-256 des Originals
        self.zugeordnet = {"category": 0, "product": 0, "formular": 0}
        self.zurueckgestellt = []             # (nochmal, Fehlermeldung) – Einträge mit _Konflikt, siehe _nachholen
        self.intervall_offen = {}             # geänderte Kategorie → (Fundstelle, Name), siehe _intervalle_pruefen
        self.listen = []                      # (Fundstelle, Name, Eintrag, Produkt) mit „bestandteile“, _bestandteillisten
        self.unveraendert = set()             # Produkte, die als „unveraendert“ zählen – bis _bestandteillisten etwas ändert
        self.formularverweise = []            # (Fundstelle, Name, Angabe, Produkt) mit „formular_von“ (Format 1/2)
        self.formulare = []                   # (Fundstelle, Titel, Formular, standard_fuer, zugewiesen), _zuweisungen
        self.kategorien, self.produkte = set(), set()     # Kennungen hier, die die Datei nennt (E2, _zuweisungen)
        self.neue_kategorien = set()          # Kategorien, die dieser Durchgang angelegt hat
        self.geltend_vorher = {}              # Produkt → (Version, Formular, Standard-Kategorie) vor dem Durchgang
        self.pfade_vorher = {}                # Kategorie → Pfad (Namen) vor dem Durchgang, siehe _pfad_vorher
        self.kategoriewechsel = {}            # Produkt → Wechsel der Kategorie, siehe _kategoriewechsel_melden
        self.wechsel_gespeichert = []         # (Stelle in warnungen, Satz nach dem Speichern), _kategoriewechsel_melden
        self.verschoben = {}                  # verschobene Kategorie → gelöste Zuweisungen, Warnung; _verschiebung_merken
        self.gruppen = []                     # (Gruppe im Probelauf, nach dem Speichern), _kategoriewechsel_melden
        self.neu_angelegt = []                # Satzteile „„Neu“ (unter …) nimmt n Produkte aus … auf“, ebenda
        self.bericht = _bericht()

    def notiz(self, zeile):
        liste = self.bericht["aenderungen"]
        if len(liste) < MAX_LISTE:
            liste.append(zeile)
        elif len(liste) == MAX_LISTE:
            liste.append("… und weitere Änderungen")

    def uid(self, e, feld="uid"):
        """Die Katalogkennung eines Eintrags (ab Format 2) – oder None."""
        wert = e.get(feld) if self.version >= 2 else None
        if wert in (None, ""):
            return None
        if not isinstance(wert, str) or not _UID.fullmatch(wert):
            raise Abgelehnt(f"„{feld}“ ist keine Katalogkennung (32 Zeichen 0–9 und a–f).")
        return wert

    def uid_setzen(self, tabelle, rid, uid):
        """Ein eben angelegter Datensatz bekommt die Kennung aus der Datei statt der zufälligen des Triggers."""
        if uid:
            try:
                db.execute(f"UPDATE {tabelle} SET uid = ? WHERE id = ?", (uid, rid))
            except sqlite3.IntegrityError:
                raise Abgelehnt(f"Die Katalogkennung {uid} trägt hier schon ein anderer Eintrag.", 409)

    def uid_uebernehmen(self, tabelle, entity, row, uid):
        """Über Name bzw. Dublette gefunden: Der Datensatz übernimmt die Kennung der Datei – mit Journaleintrag,
        denn ab jetzt findet ihn jeder weitere Import über sie."""
        if not uid or row["uid"] == uid:
            return
        self.uid_setzen(tabelle, row["id"], uid)
        journal.eintragen(entity, row["id"], "geaendert", {"uid": row["uid"]}, {"uid": uid})
        self.zugeordnet[entity] += 1

    def datei(self, pfad, art):
        """Die geprüfte Datei hinter einem Verweis (art „bild“ oder „dokument“) – oder Abgelehnt mit dem Grund."""
        if not isinstance(pfad, str) or not pfad:
            raise Abgelehnt("Der Dateiverweis muss ein Pfad im Archiv sein.")
        if self.archiv is None:
            raise Abgelehnt("Eine reine JSON-Datei bringt keine Dateien mit – „bild“ und „datei“ gibt es nur im "
                            "ZIP-Archiv eines Katalog-Exports.")
        eintrag = self.dateien.get((pfad, art))
        if eintrag is None:
            raise Abgelehnt(f"„{pfad[:120]}“ wurde nicht geprüft.")
        if "fehler" in eintrag:
            raise Abgelehnt(eintrag["fehler"])
        return eintrag

    def ablegen(self, ort, eintrag):
        """Die Datei für diese Fundstelle: beim Planen ein Platzhalter (vorgemerkt), sonst die vorher abgelegte.
        Bild: Dateiname; Dokument: (Name, MIME, Größe, SHA-256)."""
        if self.planen:
            self.bedarf[ort] = eintrag
            ext = os.path.splitext(eintrag["name"])[1].lower()
            if eintrag["art"] == "bild":
                return "probelauf" + ext
            return "probelauf" + ext, katalog.DOK_TYPEN[ext][0], eintrag["info"].file_size, eintrag["sha256"]
        if ort in self.ablage:
            self.benutzt.add(ort)
            art, wert = self.ablage[ort]
            # Eine Dokumentdatei muss noch liegen: Zwischen dem Ablegen (vor der Transaktion, bei einer großen Lieferung
            # minutenlang) und jetzt kann jemand das letzte Dokument mit diesem Inhalt gelöscht und die Datei
            # freigegeben haben – dann unter der Schreibsperre, die dieser Durchgang hält, noch einmal aus dem Archiv
            # (Befund 1 der Prüfung vom 22.10.2026).
            if art == "bild" or os.path.isfile(os.path.join(katalog.dok_dir(), wert[0])):
                return wert
        neu = _ablegen(self.archiv, eintrag)
        self.abgelegt.append((eintrag["art"], neu))
        if self.fortschritt:
            self.fortschritt("schreiben", abgelegt=(eintrag["art"], neu))
        return neu

    def bild_summe(self, name):
        """SHA-256 des Originals eines Produktbilds hier – None, wenn die Datei fehlt."""
        if name not in self.summen:
            summe = hashlib.sha256()
            try:
                with open(os.path.join(katalog.medien_dir(), "orig", name), "rb") as fh:
                    for stueck in iter(lambda: fh.read(1024 * 1024), b""):
                        summe.update(stueck)
                self.summen[name] = summe.hexdigest()
            except OSError:
                self.summen[name] = None
        return self.summen[name]


def _reihenfolge(liste, tabelle, lauf):
    """(Index, Eintrag) in der Reihenfolge der Bearbeitung: Im Format 2 zuerst, was es hier unter seiner uid schon
    gibt. So wird eine umbenannte Kategorie umbenannt, bevor eine neue mit ihrem alten Namen kommt."""
    paare = list(enumerate(liste))
    if lauf.version < 2:
        return paare
    vorhanden = {r["uid"] for r in db.query(f"SELECT uid FROM {tabelle} WHERE uid IS NOT NULL")}
    return sorted(paare, key=lambda p: not (isinstance(p[1], dict) and p[1].get("uid") in vorhanden))


def _journalstand():
    return db.query("SELECT COALESCE(MAX(id), 0) AS m FROM mat_audit", one=True)["m"]


def _folgen(seit):
    """Was eine Katalogänderung an Artikeln hier ausgelöst hat – abgelesen am Journal seit dem Stand seit:
    (Artikel mit vorgezogener Fälligkeit, Artikel mit geändertem Lebensende)."""
    n = {r["action"]: r["n"] for r in db.query(
        "SELECT action, COUNT(DISTINCT entity_id) AS n FROM mat_audit WHERE id > ? AND entity = 'item' "
        "AND action IN ('faelligkeit', 'lebensende') GROUP BY action", (seit,))}
    return n.get("faelligkeit", 0), n.get("lebensende", 0)


def _folgen_satz(teile, artikel, vorgezogen, lebensende, zusatz=""):
    """„Prüfintervall … – betrifft n Artikel im Bestand[zusatz]; bei n rückt die nächste Prüfung vor …“ (ohne Punkt)."""
    satz = "; ".join(teile) or "verschoben"
    satz += f" – betrifft {artikel} Artikel im Bestand{zusatz}"
    if vorgezogen:
        satz += f"; bei {vorgezogen} rückt die nächste Prüfung vor"
    if lebensende:
        satz += f"; bei {lebensende} ändert sich das Lebensende"
    return satz


def _folgen_melden(lauf, ort, name, artikel, teile, seit):
    """Warnung für den Bericht, wenn eine Änderung an Intervall oder Lebensdauer Artikel im Bestand betrifft – liefert
    ihre Stelle in „warnungen“ (None: keine Warnung)."""
    vorgezogen, lebensende = _folgen(seit)
    if not artikel or not (teile or vorgezogen or lebensende):
        return None
    lauf.bericht["warnungen"].append(f"{ort} ({name}): {_folgen_satz(teile, artikel, vorgezogen, lebensende)}.")
    return len(lauf.bericht["warnungen"]) - 1


# --- Produkte wechseln die Kategorie (Wunsch des Nutzers vom 09.11.2026) --------------------------------------------------
# Anlass: Eine alte Katalog-ZIP (Kategorien am Namen erkannt) legt nach dem Umbenennen einer Kategorie die alte neu an und
# schiebt ihre Produkte dorthin zurück – sie erben den Standard der bisherigen Kategorie nicht mehr, eine Zuweisung an
# das Produkt wird gelöst (katalog.produkt_aendern, Z6), ihre Artikel lassen sich danach nicht prüfen. Der Import
# verhält sich weiter so; er meldet es nur: je Produkt mit Artikeln eine Warnung, oben im Bericht eine Zusammenfassung
# (_kategoriewechsel_text) und die gelösten Zuweisungen unter „zuweisungen“ → „geloest“.
# Feinschliff (09.11.2026, planung/import-warnung-feinschliff/auftrag.md): ebenso für Kategorien, die eine Datei mit
# Kennung unter eine andere Oberkategorie verschiebt – katalog.kategorie_aendern löst dabei Zuweisungen, die außerhalb der
# Heimat ihres Formulars lägen (Z6); die Warnung „verschoben – betrifft n Artikel“ der Kategorie nennt dann auch, was aus
# den Prüfformularen ihrer Produkte wird. Für die Oberfläche fasst „gruppen“ die Warnungen je alte → neue Kategorie und
# gleicher Folge in einer Zeile zusammen, die Produkte darunter (Prüfung Browser r3, Verbesserung 1: keine Textwände).

def _zuweisungen_stand(pid):
    """(Zahl aller Zuweisungen hier, Formular der Zuweisung an das Produkt pid oder None) – vor und nach dem Wechsel."""
    n = db.query("SELECT COUNT(*) AS n FROM mat_formular_zuweisung", one=True)["n"]
    z = db.query("SELECT formular_id FROM mat_formular_zuweisung WHERE product_id = ?", (pid,), one=True)
    return n, z["formular_id"] if z else None


def _kategoriewechsel_merken(lauf, ort, name, vorhanden, nach, stand_vorher):
    """Das Produkt vorhanden ist eben in die Kategorie nach gewechselt; stand_vorher aus _zuweisungen_stand. Zählt, was
    produkt_aendern dabei gelöst hat, und merkt den Wechsel für _kategoriewechsel_melden."""
    pid = vorhanden["id"]
    n_nach, eigen_nach = _zuweisungen_stand(pid)
    w = lauf.kategoriewechsel.setdefault(pid, {"ort": ort, "name": name, "von": vorhanden["category_id"],
                                               "geloest": 0, "eigene": None})
    w["nach"] = nach
    w["geloest"] += stand_vorher[0] - n_nach
    if stand_vorher[1] and eigen_nach != stand_vorher[1]:
        w["eigene"] = stand_vorher[1]
    lauf.bericht["zuweisungen"]["geloest"] += stand_vorher[0] - n_nach


def _verschiebung_merken(lauf, kid, ort, name, folgen, n_vorher, warnung, satz):
    """Die Kategorie kid ist eben unter eine andere Oberkategorie gewandert; folgen: was katalog.verschieben_folgen davor
    als gelöst ankündigte, n_vorher: Zahl aller Zuweisungen davor, warnung: Stelle ihrer Warnung in „warnungen“ (oder
    None, wenn darunter keine Artikel stehen), satz: ihre Teile (die übrigen Änderungen, Artikel, vorgezogen, Lebensende)
    – _verschoben_melden schreibt sie am Ende neu. Zählt die gelösten Zuweisungen und merkt sie für
    _kategoriewechsel_melden."""
    geloest = n_vorher - db.query("SELECT COUNT(*) AS n FROM mat_formular_zuweisung", one=True)["n"]
    lauf.bericht["zuweisungen"]["geloest"] += geloest
    lauf.verschoben[kid] = {"ort": ort, "name": name, "geloest": geloest, "folgen": folgen, "warnung": warnung,
                            "satz": satz}


def _namen(kid):
    return [k["name"] for k in katalog.kategorie_pfad(kid)]


def _pfade():
    """Kategorie → Pfad (Liste der Namen), festgehalten zu Beginn des Durchgangs – für _pfad_vorher."""
    zeilen = {k["id"]: k for k in db.query("SELECT id, parent_id, name FROM mat_category")}
    out = {}
    for kid in zeilen:
        pfad, k, gesehen = [], kid, set()
        while k in zeilen and k not in gesehen:
            gesehen.add(k)
            pfad.insert(0, zeilen[k]["name"])
            k = zeilen[k]["parent_id"]
        out[kid] = pfad
    return out


def _pfad_vorher(lauf, kid):
    """Der Pfad der Kategorie kid vor dem Durchgang (Prüfung Ablauf r1, Befund 2): Verschiebt dieselbe Datei sie oder
    eine darüber, stünde sonst schon der neue Pfad als „alt“ da. Eine eben angelegte hat keinen – dann der jetzige."""
    return lauf.pfade_vorher.get(kid) or _namen(kid)


def _unter(neu, aus):
    """„„Neu“ (unter „Ober“)“ und die Pfade aus (Listen der Namen) ohne den gemeinsamen Anfang aller – für „Neu angelegt:
    … nimmt n Produkte aus … auf“ wie in _pfeil (Prüfung Browser r2, Verbesserung 2: der volle Oberpfad stand zweimal)."""
    n = 0
    while all(n < len(p) - 1 and p[n] == neu[n] for p in [neu] + aus):
        n += 1
    return (f"„{' / '.join(neu[n:])}“" + (f" (unter „{' / '.join(neu[:n])}“)" if n else ""),
            [f"„{' / '.join(p[n:])}“" for p in aus])


def _pfeil(von, nach):
    """„alt“ → „neu“ für zwei Kategoriepfade (Listen der Namen), den gemeinsamen Anfang nur einmal dahinter: „Schlingen“ →
    „Textilmaterial“ (unter „Persönliche Schutzausrüstung gegen Absturz“). Prüfung Browser r1/r3: Der volle Pfad stand
    sonst zweimal in jeder Zeile."""
    n = 0
    while n < min(len(von), len(nach)) - 1 and von[n] == nach[n]:
        n += 1
    satz = f"„{' / '.join(von[n:])}“ → „{' / '.join(nach[n:])}“"
    return satz + (f" (unter „{' / '.join(von[:n])}“)" if n else "")


def _herkunft(geltend):
    """Woher ein Formular für ein Produkt gilt (Tripel aus katalog._geltend), in Worten wie formular_fuer_produkt."""
    if geltend[2] is None:
        return "dem Produkt zugewiesen"
    k = db.query("SELECT name FROM mat_category WHERE id = ?", (geltend[2],), one=True)
    return f"Standard der Kategorie „{k['name'] if k else '?'}“"


def _titel(geltend):
    return f"„{katalog._anzeige_titel(geltend[1])}“"


def _formularfolge(n, alt, jetzt, eigene, fertig, produkte=1):
    """Was aus dem Prüfformular von n Artikeln wird, deren Produkt (bzw. produkte Produkte mit gleicher Folge) die
    Kategorie gewechselt hat – als Teilsätze; alt, jetzt: was vorher und nachher gilt (katalog._geltend), eigene: die
    dabei gelöste Zuweisung an das Produkt. Deren Titel steht nur einmal da (sie war das bisherige Formular)."""
    er = n == 1
    gilt = "jetzt gilt" if fertig else "künftig gilt"
    teile = []
    if eigene:
        teile.append(f"die Zuweisung von „{katalog._anzeige_titel(eigene)}“ an das Produkt "
                     + ("wurde gelöst" if fertig else "wird gelöst") if produkte == 1 else
                     f"die Zuweisungen von „{katalog._anzeige_titel(eigene)}“ an die Produkte "
                     + ("wurden gelöst" if fertig else "werden gelöst"))
    bisher_genannt = bool(eigene) and bool(alt) and alt[1] == eigene
    if alt and not jetzt:
        bisher = "" if bisher_genannt else f" (bisher {_titel(alt)}, {_herkunft(alt)})"
        teile.append(f"{'er hat' if er else 'sie haben'} danach kein Prüfformular mehr{bisher} und "
                     f"{'lässt' if er else 'lassen'} sich nicht prüfen")
    elif alt and jetzt[1] != alt[1]:
        statt = "" if bisher_genannt else f" statt {_titel(alt)} ({_herkunft(alt)})"
        teile.append(f"{gilt} {_titel(jetzt)} ({_herkunft(jetzt)}){statt}")
    elif alt:
        teile.append(f"das Prüfformular {_titel(jetzt)} gilt weiter ({_herkunft(jetzt)})")
    elif jetzt:
        teile.append(f"{gilt} {_titel(jetzt)} ({_herkunft(jetzt)}), bisher keins")
    else:
        teile.append(f"ein Prüfformular {'hat er' if er else 'haben sie'} weiterhin nicht")
    return teile


def _kategoriewechsel_satz(lauf, w, n, alt, jetzt, fertig):
    """Die Warnung für ein Produkt mit n Artikeln, das die Kategorie gewechselt hat (w aus _kategoriewechsel_merken) –
    fertig: nach dem Speichern."""
    satz = f"Kategorie {_pfeil(_pfad_vorher(lauf, w['von']), _namen(w['nach']))} – betrifft {n} Artikel im Bestand"
    return f"{w['ort']} ({w['name']}): " + "; ".join([satz] + _formularfolge(n, alt, jetzt, w["eigene"], fertig)) + "."


def _folgen_je_artikel(eintraege, fertig):
    """Was aus den Prüfformularen der Artikel unter einer verschobenen Kategorie wird – eintraege: (n, alt, jetzt) je
    Produkt mit Artikeln; gleiche Folgen zusammengezählt, die schwerste zuerst."""
    summe = {}
    for n, alt, jetzt in eintraege:
        if alt and not jetzt:
            k = (0, _titel(alt), _herkunft(alt), None, None)
        elif alt and jetzt[1] != alt[1]:
            k = (1, _titel(alt), _herkunft(alt), _titel(jetzt), _herkunft(jetzt))
        elif jetzt and not alt:
            k = (2, None, None, _titel(jetzt), _herkunft(jetzt))
        elif jetzt:
            k = (3, None, None, _titel(jetzt), _herkunft(jetzt))
        else:
            k = (4, None, None, None, None)
        summe[k] = summe.get(k, 0) + n
    gilt = "gilt jetzt" if fertig else "gilt künftig"
    teile = []
    for (art, alt, h_alt, jetzt, h_jetzt), n in sorted(summe.items(), key=lambda x: x[0][0]):
        er = n == 1
        teile.append([f"{n} Artikel {'hat' if er else 'haben'} danach kein Prüfformular mehr (bisher {alt}, {h_alt}) "
                      f"und {'lässt' if er else 'lassen'} sich nicht prüfen",
                      f"für {n} Artikel {gilt} {jetzt} ({h_jetzt}) statt {alt} ({h_alt})",
                      f"für {n} Artikel {gilt} {jetzt} ({h_jetzt}), bisher keins",
                      f"für {n} Artikel gilt {jetzt} weiter ({h_jetzt})",
                      f"{n} Artikel {'hat' if er else 'haben'} weiterhin kein Prüfformular"][art])
    return teile


def _geloest_text(lauf, v, fertig):
    """Die Zuweisungen, die das Verschieben der Kategorie (v aus _verschiebung_merken) gelöst hat – oder None. Eine
    Kategorie als Ziel mit ihrem Pfad vor dem Durchgang (Prüfung Ablauf r2): verschieben_folgen läuft mitten darin, nach
    einer schon verschobenen Oberkategorie stünde sonst ein Zwischenstand da."""
    n = v["geloest"]
    if not n:
        return None
    namen = [f"„{f['formular'] or 'ohne Titel'}“ an "
             + (f"Kategorie „{' / '.join(_pfad_vorher(lauf, f['kategorie_id']))}“" if f["kategorie_id"] else f["ziel"])
             for f in v["folgen"]]
    if n == 1 and len(namen) == 1:
        return f"die Zuweisung von {namen[0]} " + ("wurde gelöst" if fertig else "wird gelöst")
    return (f"{n} Zuweisungen " + ("wurden gelöst" if fertig else "werden gelöst")
            + (": " + ", ".join(namen[:3]) + (" und weitere" if len(namen) > 3 else "") if namen else ""))


def _verb(fertig, n, eins, viele, eins_vorbei, viele_vorbei):
    if fertig:
        return eins_vorbei if n == 1 else viele_vorbei
    return eins if n == 1 else viele


def _folgen_kurz(ohne, anders, geloest, zuweisung, fertig):
    """„; n Artikel verlieren ihr Prüfformular, n bekommen ein anderes, n Zuweisungen werden gelöst“ – für die
    Zusammenfassung und die Zeilen der Gruppen; leer, wenn nichts davon zutrifft."""
    out = []
    if ohne:
        out.append(f"{ohne} Artikel " + _verb(fertig, ohne, "verliert sein Prüfformular", "verlieren ihr Prüfformular",
                                              "hat sein Prüfformular verloren", "haben ihr Prüfformular verloren"))
    if anders:
        out.append(f"{anders} Artikel " + _verb(fertig, anders, "bekommt ein anderes Prüfformular",
                                                "bekommen ein anderes Prüfformular",
                                                "hat ein anderes Prüfformular bekommen",
                                                "haben ein anderes Prüfformular bekommen"))
    if geloest:
        out.append(f"{geloest} {zuweisung}{'en' if geloest != 1 else ''} "
                   + _verb(fertig, geloest, "wird gelöst", "werden gelöst", "wurde gelöst", "wurden gelöst"))
    return "; " + ", ".join(out) if out else ""


def _folge_art(alt, jetzt):
    """0 Prüfformular verloren, 1 ein anderes, sonst 2 (gilt weiter, neu, weiterhin keins) – für die Zahlen."""
    return 0 if alt and not jetzt else 1 if alt and jetzt[1] != alt[1] else 2


def _unterzeile(liste, eigene, fertig):
    """Eine Zeile unter „Einzelheiten“ einer Gruppe: liste [(Name, n Artikel, alt, jetzt)] mit gleicher Folge – dazu die
    Namen, wenn es mehrere Produkte sind."""
    n = sum(e[1] for e in liste)
    wer = liste[0][0] if len(liste) == 1 else f"{len(liste)} Produkte"
    satz = "; ".join(_formularfolge(n, liste[0][2], liste[0][3], eigene, fertig, len(liste)))
    return f"{n} Artikel ({wer}): {satz}.", [f"{e[0]} ({e[1]} Artikel)" for e in liste] if len(liste) > 1 else []


def _gruppe(zeile, folgen, warnungen):
    """Eine Gruppe für die Oberfläche: die Zeile, darunter aufklappbar je gleicher Folge eine Zeile mit den Produkten
    (folgen: [(Zeile, [Namen])]), dazu die Stellen der Warnungen in „warnungen“, die sie zusammenfasst."""
    return {"zeile": zeile, "folgen": [{"zeile": z, "einzeln": namen} for z, namen in folgen], "warnungen": warnungen}


def _kategoriewechsel_melden(lauf):
    """Nach den Zuweisungen der Datei – erst dann steht fest, welches Formular danach gilt: je Produkt mit Artikeln
    (nicht ausgesondert), das die Kategorie gewechselt hat, eine Warnung; die Warnung jeder verschobenen Kategorie um die
    Folgen für die Prüfformulare ergänzt; die Gruppen für die Oberfläche (lauf.gruppen, je Probelauf und Ergebnis) und
    die Zahlen für die Zusammenfassung in bericht["kategoriewechsel"] (Wortlaut in _kategoriewechsel_text, erst wenn
    feststeht, ob gespeichert wurde)."""
    wechsel = {pid: w for pid, w in lauf.kategoriewechsel.items() if w["nach"] != w["von"]}
    if not (wechsel or lauf.verschoben):
        return
    nachher = katalog._geltend()

    def artikel(pid):
        return db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ? AND lock_state <> 'ausgesondert'",
                        (pid,), one=True)["n"]

    zahl = {"produkte": len(wechsel), "mit_artikeln": 0, "artikel": 0, "ohne_formular": 0, "anderes_formular": 0,
            "zuweisungen_geloest": sum(w["geloest"] for w in lauf.kategoriewechsel.values()), "neue_kategorien": [],
            "verschoben": None}
    neu = {}                               # neu angelegte Kategorie → {bisherige Kategorie: Produkte}
    paare = {}                             # (von, nach) → {(eigene, alt, jetzt): [(w, n, alt, jetzt, Stelle)]}
    for pid, w in wechsel.items():
        if w["nach"] in lauf.neue_kategorien and w["von"] not in lauf.neue_kategorien:
            aus = neu.setdefault(w["nach"], {})
            aus[w["von"]] = aus.get(w["von"], 0) + 1
        n = artikel(pid)
        if not n:
            continue
        zahl["mit_artikeln"] += 1
        zahl["artikel"] += n
        alt, jetzt = lauf.geltend_vorher.get(pid), nachher.get(pid)
        if alt and not jetzt:
            zahl["ohne_formular"] += n
        elif alt and jetzt[1] != alt[1]:
            zahl["anderes_formular"] += n
        # Im Probelauf als Aussicht; nach dem Speichern tauscht _abschluss den Satz gegen den im Ergebnis („wurde
        # gelöst“, „jetzt gilt“ – Prüfung Browser r1, B2), damit er zur Zusammenfassung darüber passt.
        i = len(lauf.bericht["warnungen"])
        lauf.bericht["warnungen"].append(_kategoriewechsel_satz(lauf, w, n, alt, jetzt, False))
        lauf.wechsel_gespeichert.append((i, _kategoriewechsel_satz(lauf, w, n, alt, jetzt, True)))
        folge = (w["eigene"], alt and alt[1:], jetzt and jetzt[1:])
        paare.setdefault((w["von"], w["nach"]), {}).setdefault(folge, []).append((w, n, alt, jetzt, i))
    zahl["neue_kategorien"] = [{"kategorie": _kategorie_pfadname(kid), "produkte": sum(aus.values()),
                                "aus": [" / ".join(_pfad_vorher(lauf, k)) for k in sorted(aus, key=aus.get, reverse=True)]}
                               for kid, aus in neu.items()]
    for kid, aus in list(neu.items())[:3]:
        name, von = _unter(_namen(kid), [_pfad_vorher(lauf, k) for k in sorted(aus, key=aus.get, reverse=True)[:3]])
        n = sum(aus.values())
        lauf.neu_angelegt.append(f"{name} nimmt {n} Produkt{'e' if n != 1 else ''} aus " + ", ".join(von)
                                 + (" und weiteren" if len(aus) > 3 else "") + " auf")
    for (von, nach), folgen in paare.items():
        alle = [x for liste in folgen.values() for x in liste]
        n = sum(x[1] for x in alle)
        zahlen = [sum(x[1] for x in alle if _folge_art(x[2], x[3]) == art) for art in (0, 1)]
        wer = alle[0][0]["name"] if len(alle) == 1 else f"{len(alle)} Produkte"
        kopf = (f"Kategorie {_pfeil(_pfad_vorher(lauf, von), _namen(nach))} – {wer} mit {n} Artikel{'n' if n != 1 else ''} im "
                "Bestand")
        geloest = sum(x[0]["geloest"] for x in alle)
        lauf.gruppen.append(tuple(_gruppe(
            kopf + _folgen_kurz(*zahlen, geloest, "Produkt-Zuweisung", fertig) + ".",
            [_unterzeile([(x[0]["name"], *x[1:4]) for x in liste], liste[0][0]["eigene"], fertig)
             for liste in folgen.values()],
            [x[4] for x in alle]) for fertig in (False, True)))
    if lauf.verschoben:
        zahl["verschoben"] = _verschoben_melden(lauf, wechsel, nachher, artikel)
    lauf.bericht["kategoriewechsel"] = zahl


def _verschoben_text(von, nach):
    """„verschoben „alt“ → „neu““ für zwei Kategoriepfade; auf die oberste Ebene „→ oberste Ebene“ (Prüfung Browser r1,
    Verbesserung 2: „→ „Schlingen““ las sich wie ein doppelter Name)."""
    if len(nach) == 1:
        return f"verschoben „{' / '.join(von)}“ → " + ("oberste Ebene" if von[-1:] == nach else
                                                     f"„{nach[0]}“ (oberste Ebene)")
    return f"verschoben {_pfeil(von, nach)}"


def _verschoben_melden(lauf, wechsel, nachher, artikel):
    """Die verschobenen Kategorien (lauf.verschoben): Folgen für die Prüfformulare der Produkte darunter, die nicht selbst
    die Kategorie gewechselt haben (die haben ihre eigene Warnung) – an die Warnung „verschoben – betrifft n Artikel“ der
    Kategorie angehängt statt doppelt gemeldet, als Gruppe mit den Produkten und als Zahlen. Jedes Produkt steht bei der
    innersten verschobenen Kategorie über ihm, einmal (Prüfung Ablauf r1, Befund 3: verschiebt die Datei auch eine
    Kategorie darüber, stand es sonst bei beiden). „betrifft n Artikel“ zählt wie bisher beim Verschieben; wie viele
    davon eine eigene Warnung haben – ihr Produkt wechselt selbst die Kategorie oder steht unter einer weiteren
    verschobenen –, sagt ein Zusatz (Befund 1). Pfade wie vor dem Durchgang → wie am Ende (Befund 2)."""
    zahl = {"kategorien": len(lauf.verschoben), "mit_artikeln": 0, "artikel": 0, "ohne_formular": 0,
            "anderes_formular": 0, "zuweisungen_geloest": sum(v["geloest"] for v in lauf.verschoben.values())}
    eintraege, gezaehlt = {}, set()
    for kid in sorted(lauf.verschoben, key=lambda k: len(_namen(k)), reverse=True):      # die innerste zuerst
        bedingung, args = in_kategorie(kid)
        eintraege[kid] = []
        for p in db.query(f"SELECT p.* FROM mat_product p WHERE {bedingung} ORDER BY p.manufacturer COLLATE NOCASE, "
                          "p.model COLLATE NOCASE, p.id", args):
            if p["id"] in gezaehlt:
                continue
            gezaehlt.add(p["id"])
            n = artikel(p["id"]) if p["id"] not in wechsel else 0
            if not n:
                continue
            alt, jetzt = lauf.geltend_vorher.get(p["id"]), nachher.get(p["id"])
            eintraege[kid].append((katalog.produktname(p), n, alt, jetzt))
            zahl["mit_artikeln"] += 1
            zahl["artikel"] += n
            if alt and not jetzt:
                zahl["ohne_formular"] += n
            elif alt and jetzt[1] != alt[1]:
                zahl["anderes_formular"] += n
    for kid, v in lauf.verschoben.items():
        i = v["warnung"]
        if i is None:
            continue
        liste = eintraege[kid]
        teile, n_vorher, vorgezogen, lebensende = v["satz"]
        rest = n_vorher - sum(e[1] for e in liste)
        zusatz = (f", davon {rest} mit eigener Warnung" if liste else ", alle mit eigener Warnung") if rest > 0 else ""
        ort = f"{v['ort']} ({v['name']}): "
        basis = ort + _folgen_satz(teile + [_verschoben_text(_pfad_vorher(lauf, kid), _namen(kid))], n_vorher,
                                   vorgezogen, lebensende, zusatz)

        def satz(fertig, basis=basis, liste=liste, v=v):
            g = _geloest_text(lauf, v, fertig)
            return "; ".join([basis] + _folgen_je_artikel([e[1:] for e in liste], fertig) + ([g] if g else [])) + "."
        lauf.bericht["warnungen"][i] = satz(False)
        lauf.wechsel_gespeichert.append((i, satz(True)))
        if not liste:
            continue
        # Für die Oberfläche: die Warnung ohne Fundstelle mit den Zahlen, aufklappbar je gleicher Folge die Produkte.
        folgen = {}
        for e in liste:
            folgen.setdefault((e[2] and e[2][1:], e[3] and e[3][1:]), []).append(e)
        zahlen = [sum(e[1] for e in liste if _folge_art(e[2], e[3]) == art) for art in (0, 1)]

        def unterzeilen(fertig, folgen=folgen, v=v):
            out = [_unterzeile(gleich, None, fertig) for gleich in folgen.values()]
            g = _geloest_text(lauf, v, fertig)
            return out + ([(g[0].upper() + g[1:] + ".", [])] if g else [])
        lauf.gruppen.append(tuple(_gruppe(
            f"Kategorie „{v['name']}“: {basis.removeprefix(ort)}"
            + _folgen_kurz(*zahlen, v["geloest"], "Zuweisung", fertig) + ".", unterzeilen(fertig), [i])
            for fertig in (False, True)))
    return zahl


def _kategoriewechsel_text(b, neu_angelegt):
    """Die Zusammenfassung oben im Bericht (Oberfläche und Kommandozeile): wenn ein Produkt mit Artikeln die Kategorie
    wechselt oder eine neu angelegte Kategorie Produkte aus einer bestehenden aufnimmt – dann vielleicht eine alte Datei
    mit einem früheren Kategorienamen (README „Kategorie im Katalog umbenennen“) –, und eigens, wenn verschobene
    Kategorien Produkte mit Artikeln tragen. Dazu „davon“ für die Zeile der gelösten Zuweisungen. Im Probelauf (und wenn
    nichts gespeichert wurde) als Aussicht, nach dem Speichern als Ergebnis. neu_angelegt: die Satzteile der neuen
    Kategorien aus _kategoriewechsel_melden."""
    z = b.get("kategoriewechsel")
    if not z:
        return
    z["zusammenfassung"] = z["verschiebung"] = z["alte_datei"] = None
    v = z["verschoben"] or {}
    a, k = z["zuweisungen_geloest"], v.get("zuweisungen_geloest", 0)
    z["davon"] = (f"davon {a + k} durch " + ("Kategoriewechsel und verschobene Kategorien" if a and k else
                                             "Kategoriewechsel" if a else "verschobene Kategorien")) if a + k else None
    fertig = b.get("gespeichert")

    def verb(n, *formen):
        return _verb(fertig, n, *formen)

    if v.get("mit_artikeln"):
        n, m = v["kategorien"], v["mit_artikeln"]
        satz = f"{n} Kategorie{'n' if n != 1 else ''} " + verb(n, "wird verschoben", "werden verschoben",
                                                             "wurde verschoben", "wurden verschoben")
        satz += (f" – darin 1 Produkt mit {v['artikel']} Artikel{'n' if v['artikel'] != 1 else ''} im Bestand" if m == 1
                 else f" – darin {m} Produkte mit Artikeln im Bestand ({v['artikel']} Artikel)")
        z["verschiebung"] = satz + _folgen_kurz(v["ohne_formular"], v["anderes_formular"], k, "Zuweisung", fertig) + "."
    if not (z["mit_artikeln"] or z["neue_kategorien"]):
        return
    p, m = z["produkte"], z["mit_artikeln"]
    satz = f"{p} Produkt{'e' if p != 1 else ''} " + verb(p, "wechselt die Kategorie", "wechseln die Kategorie",
                                                        "hat die Kategorie gewechselt", "haben die Kategorie gewechselt")
    if not m:
        satz += " – ohne Artikel im Bestand" if p == 1 else " – keins mit Artikeln im Bestand"
    elif p == 1:
        satz += f" – mit {z['artikel']} Artikel{'n' if z['artikel'] != 1 else ''} im Bestand"
    else:
        satz += f" – {'alle' if m == p else f'davon {m}'} mit Artikeln im Bestand ({z['artikel']} Artikel)"
    z["zusammenfassung"] = satz + _folgen_kurz(z["ohne_formular"], z["anderes_formular"], a, "Produkt-Zuweisung",
                                               fertig) + "."
    if z["neue_kategorien"]:
        rest = len(z["neue_kategorien"]) - 3
        z["alte_datei"] = ("Neu angelegt: " + "; ".join(neu_angelegt) + (f"; dazu {rest} weitere" if rest > 0 else "")
                           + ". Vielleicht ist die Datei älter und nennt eine Kategorie noch mit ihrem früheren Namen – "
                           + ("dann jedes Produkt auf seiner Seite über „Bearbeiten“ (Feld „Kategorie“) "
                              "zurückverschieben und seine Zuweisungen neu setzen."
                              if fertig else "dann nicht übernehmen, sondern eine aktuelle Datei nehmen."))


def _geaendert(vorher, nachher):
    return ", ".join(_FELDNAMEN.get(k, k) for k in nachher if nachher[k] != vorher.get(k))


# So oft kommen zurückgestellte Einträge höchstens noch einmal dran. Jede Runde löst mindestens ein Glied einer
# Namenskette; ohne Grenze kostete eine (von Hand gebaute) Kette aus Tausenden Gliedern in ungünstiger Reihenfolge
# quadratisch viele Versuche – unter der Schreibsperre.
MAX_NACHHOLRUNDEN = 50


def _nachholen(lauf):
    """Zurückgestellte Einträge (_Konflikt) erneut versuchen, solange dabei einer durchgeht – so löst sich eine
    Namenskette auf, gleich in welcher Reihenfolge die Datei sie bringt. Eine Kategorie kommt mit ihrem Teilbaum dran.
    Was sich nicht mehr bewegt (etwa zwei Namen, die die Plätze tauschen), ist ein Fehler mit dem Grund des letzten
    Versuchs. Ein Versuch schreibt erst, wenn die Regeln in katalog.py durch sind – vorher steht nichts halb."""
    runden = 0
    while lauf.zurueckgestellt and runden < MAX_NACHHOLRUNDEN:
        runden += 1
        offen, lauf.zurueckgestellt = lauf.zurueckgestellt, []
        # Jeder Versuch liefert, ob der Eintrag erledigt ist; ein erneuter Konflikt stellt ihn wieder zurück.
        if not any([nochmal() for nochmal, _ in offen]):
            break
    zusatz = (f" (Mehr als {MAX_NACHHOLRUNDEN} Umbenennungen warten hier aufeinander – so lange Ketten löst der Import "
              "nicht auf; die Namen hier zuerst von Hand angleichen.)") if runden >= MAX_NACHHOLRUNDEN and lauf.zurueckgestellt else ""
    for _, meldung in lauf.zurueckgestellt:
        lauf.bericht["fehler"].append(meldung + zusatz)
    lauf.zurueckgestellt = []


def _intervalle_pruefen(lauf):
    """Jedes Produkt hat ein Prüfintervall – geprüft für die Kategorien, die der Import geändert hat, erst nach den
    Produkten: katalog.kategorie_aendern prüft es im Import nicht (intervall_pruefen=False), weil ein Produkt in
    derselben Datei ein eigenes Intervall bekommen kann, während seine Kategorie die Vorgabe verliert. Gemeldet an der
    Stelle der Kategorie, mit der Meldung der Oberfläche; jedes Produkt einmal."""
    gemeldet = set()
    for kid, (ort, name) in lauf.intervall_offen.items():
        bedingung, args = in_kategorie(kid)
        ohne = []
        for p in db.query(f"SELECT * FROM mat_product p WHERE {bedingung} ORDER BY p.id", args):
            if p["id"] not in gemeldet and herstellerseite(p)[0] is None:
                gemeldet.add(p["id"])
                ohne.append(katalog.produktname(p))
        if ohne:
            lauf.bericht["fehler"].append(f"{ort} ({name}): {katalog.ohne_intervall_meldung(ohne)}")


# --- Kategorien ------------------------------------------------------------------------------------

def _kategorie_vorhanden(uid, name, parent, lauf):
    if uid:
        k = db.query("SELECT * FROM mat_category WHERE uid = ?", (uid,), one=True)
        if k:
            return k
    k = db.query("SELECT * FROM mat_category WHERE COALESCE(parent_id, 0) = ? AND name = ? COLLATE NOCASE",
                 (parent or 0, name), one=True)
    # Trägt die gleichnamige Kategorie die Kennung eines anderen Eintrags der Datei, gehört sie zu jenem.
    if k and k["uid"] != uid and k["uid"] in lauf.kategorie_uids:
        return None
    return k


def _kategorie_pfadname(kid):
    return " / ".join(k["name"] for k in katalog.kategorie_pfad(kid))


def _kategorien(liste, parent, stelle, lauf, tiefe=0):
    if not isinstance(liste, list):
        raise Abgelehnt(f"{stelle}: „kategorien“ muss eine Liste sein.")
    if tiefe > MAX_TIEFE:
        raise Abgelehnt(f"{stelle}: Der Kategorienbaum ist tiefer als {MAX_TIEFE} Ebenen.")
    for n, e in _reihenfolge(liste, "mat_category", lauf):
        _kategorie(e, parent, f"{stelle}[{n}]", lauf, tiefe)


def _kategorie(e, parent, ort, lauf, tiefe):
    """Ein Eintrag samt Teilbaum. Liefert, ob er erledigt ist – False: zurückgestellt (_Konflikt), dann kommt er mit
    seinem Teilbaum in _nachholen noch einmal dran."""
    bericht = lauf.bericht
    try:
        if not isinstance(e, dict):
            raise Abgelehnt("Eintrag ist kein Objekt.")
        name = _name(e.get("name")) if isinstance(e.get("name"), str) else ""
        if not name:
            raise Abgelehnt("„name“ fehlt.")
        uid = lauf.uid(e)
        d = dict(_abbilden(e, _KATEGORIE_ABBILDUNG), name=name, parent_id=parent)
        vorhanden = _kategorie_vorhanden(uid, name, parent, lauf)
        if vorhanden:
            kid = vorhanden["id"]
            vorher = katalog.kategorie_werte({}, vorhanden)
            nachher = _ohne_konflikt(katalog.kategorie_werte, d, vorhanden)
            if vorher != nachher:
                seit = _journalstand()
                # Unter eine andere Oberkategorie: Was das Verschieben an Zuweisungen löst (Z6), sagt
                # verschieben_folgen vorher – für die Warnung, gezählt in _verschiebung_merken.
                verschoben = nachher["parent_id"] != vorher["parent_id"]
                if verschoben:
                    folgen = katalog.verschieben_folgen(kategorie_id=kid, parent_id=nachher["parent_id"])
                    n_zuweisungen = db.query("SELECT COUNT(*) AS n FROM mat_formular_zuweisung", one=True)["n"]
                # „Jedes Produkt hat ein Prüfintervall“ erst nach den Produkten der Datei (_intervalle_pruefen).
                _ohne_konflikt(katalog.kategorie_aendern, kid, d, intervall_pruefen=False)
                lauf.intervall_offen.setdefault(kid, (ort, name))
                bericht["kategorien"]["geaendert"] += 1
                lauf.notiz(f"Kategorie „{_kategorie_pfadname(kid)}“: geändert ({_geaendert(vorher, nachher)})")
                teile = []
                if nachher["default_interval_months"] != vorher["default_interval_months"]:
                    teile.append(f"Prüfintervall (Vorgabe) {vorher['default_interval_months'] or '–'} → "
                                 f"{nachher['default_interval_months'] or '–'} Monate")
                if verschoben:
                    teile.append(_verschoben_text(_pfad_vorher(lauf, kid), _namen(kid)))
                warnung = None
                if teile:
                    bedingung, args = in_kategorie(kid)
                    artikel = db.query("SELECT COUNT(*) AS n FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
                                       f"WHERE i.lock_state <> 'ausgesondert' AND {bedingung}", args, one=True)["n"]
                    warnung = _folgen_melden(lauf, ort, name, artikel, teile, seit)
                if verschoben:
                    _verschiebung_merken(lauf, kid, ort, name, folgen, n_zuweisungen, warnung,
                                         (teile[:-1], artikel, *_folgen(seit)))
            else:
                bericht["kategorien"]["unveraendert"] += 1
            lauf.uid_uebernehmen("mat_category", "category", vorhanden, uid)
        else:
            kid = _ohne_konflikt(katalog.kategorie_anlegen, d)
            lauf.uid_setzen("mat_category", kid, uid)
            lauf.neue_kategorien.add(kid)
            bericht["kategorien"]["neu"] += 1
            lauf.notiz(f"Kategorie „{_kategorie_pfadname(kid)}“: neu")
        lauf.kategorien.add(kid)
        if lauf.version >= 2:
            _dokumente(e.get("dokumente"), "category_id", kid, ort, name, lauf)
    except _Konflikt as exc:
        lauf.zurueckgestellt.append((lambda: _kategorie(e, parent, ort, lauf, tiefe), f"{ort} ({e.get('name')}): {exc}"))
        return False
    except Abgelehnt as exc:
        bericht["fehler"].append(f"{ort} ({e.get('name') if isinstance(e, dict) else '?'}): {exc}")
        return True
    if e.get("unterkategorien"):
        _kategorien(e["unterkategorien"], kid, f"{ort}.unterkategorien", lauf, tiefe + 1)
    return True


def _kategorie_ziel(e, lauf):
    """Die Kategorie, auf die ein Produkt oder Formular verweist: im Format 2 über „kategorie_uid“, sonst (und wenn
    es die nicht gibt) über den Pfad."""
    uid = lauf.uid(e, "kategorie_uid")
    if uid:
        k = db.query("SELECT id FROM mat_category WHERE uid = ?", (uid,), one=True)
        if k:
            return k["id"]
    return _kategorie_finden(_pfad(e.get("kategorie")))


# --- Produkte --------------------------------------------------------------------------------------

def _produkt_key(e):
    if not isinstance(e, dict):
        raise Abgelehnt("Produktangabe ist kein Objekt.")
    teile = [e.get(k) if isinstance(e.get(k), str) else "" for k in ("hersteller", "modell", "artikelnummer")]
    return katalog.dedupe_key(*teile)


def _produkt_vorhanden(e, uid, lauf):
    if uid:
        p = db.query("SELECT * FROM mat_product WHERE uid = ?", (uid,), one=True)
        if p:
            return p
    p = db.query("SELECT * FROM mat_product WHERE dedupe_key = ?", (_produkt_key(e),), one=True)
    if p and p["uid"] != uid and p["uid"] in lauf.produkt_uids:
        return None
    return p


def _materialart_pruefen(alt, w):
    """Die Materialart eines Produkts mit Artikeln ändert sich nie (produkt_aendern weist es ab) – hier mit Namen
    und Zahl, damit klar ist, warum der ganze Import steht."""
    if w["material_kind"] == alt["material_kind"]:
        return
    n = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ?", (alt["id"],), one=True)["n"]
    if n:
        raise Abgelehnt(f"Die Materialart wechselte von „{MATERIALARTEN[alt['material_kind']]}“ auf "
                        f"„{MATERIALARTEN[w['material_kind']]}“ – hier gibt es aber schon {n} Artikel dieses Produkts, "
                        "und an der Materialart hängen Lebensdauer und Aussonderung. Erst klären: in der Quelle "
                        "zurückändern oder dort ein eigenes Produkt dafür anlegen.", 409)


def _lange_beschreibung(lauf, name, beschreibung):
    """Eine Beschreibung, die länger ist als katalog.BESCHREIBUNG_MAX, kommt unverändert herein (siehe oben) – der
    Bericht sagt es, damit sie beim nächsten Bearbeiten gekürzt wird."""
    if len(beschreibung or "") > katalog.BESCHREIBUNG_MAX:
        lauf.bericht["hinweise"].append(
            f"Produkt „{name}“: Die Bemerkung hat {len(beschreibung)} Zeichen und ist so übernommen. Gedacht ist ein "
            f"kurzer Zusatz hinter dem Namen (höchstens {katalog.BESCHREIBUNG_MAX} Zeichen) – Listen zeigen sie gekürzt, "
            "beim nächsten Bearbeiten bitte kürzen.")


def _bemerkung_pruefen(e):
    """„beschreibung“ und „bemerkung“ sind in einem Produkteintrag gleichwertig (das Feld heißt in der Oberfläche seit
    dem 18.10.2026 „Bemerkung“, der Export schreibt weiter „beschreibung“). Stehen beide da, müssen sie gleich sein –
    sonst wäre offen, welche gilt."""
    if "beschreibung" in e and "bemerkung" in e and e["beschreibung"] != e["bemerkung"]:
        raise Abgelehnt("„beschreibung“ und „bemerkung“ meinen dasselbe Feld (die Bemerkung hinter dem Namen), stehen "
                        "hier aber mit verschiedenen Werten – bitte nur eins angeben.")


def _produktname_datei(e):
    """Der Name eines Produkteintrags der Datei für Bericht und Fehlerorte – „Hersteller Modell Beschreibung“ wie
    katalog.produktname, damit sich Varianten unterscheiden, die nur die Beschreibung trennt (etwa die Verschlussart).
    Noch ungeprüft: Fehlt Hersteller oder Modell, steht „?“; eine Beschreibung, die kein Text ist, bleibt weg."""
    if not isinstance(e, dict):
        return "?"
    beschr = e.get("beschreibung", e.get("bemerkung"))
    return katalog.produktname({"manufacturer": str(e.get("hersteller", "?")), "model": str(e.get("modell", "?")),
                                "description": beschr if isinstance(beschr, str) else ""})


def _produkte(liste, lauf):
    if not isinstance(liste, list):
        raise Abgelehnt("„produkte“ muss eine Liste sein.")
    for n, e in _reihenfolge(liste, "mat_product", lauf):
        _produkt(n, e, lauf)


def _produkt(n, e, lauf):
    """Ein Eintrag mit Bild und Dokumenten. Liefert, ob er erledigt ist – False: zurückgestellt (_Konflikt)."""
    bericht = lauf.bericht
    ort = f"produkte[{n}]"
    name = _produktname_datei(e)
    try:
        if not isinstance(e, dict):
            raise Abgelehnt("Eintrag ist kein Objekt.")
        _bemerkung_pruefen(e)
        if e.get("set") is not None and wahr(e, "set", "set"):
            raise Abgelehnt(SET_ENTFALLEN)
        uid = lauf.uid(e)
        d = _abbilden(e, _PRODUKT_ABBILDUNG)
        d["category_id"] = _kategorie_ziel(e, lauf)
        vorhanden = _produkt_vorhanden(e, uid, lauf)
        if vorhanden:
            pid = vorhanden["id"]
            # Der Stand hier, ungeprüft übernommen, wenn er die Regeln gerade nicht erfüllt: Hat die Kategorie in
            # diesem Lauf ihre Vorgabe verloren, ist das Produkt erst mit dem Intervall aus der Datei wieder gültig.
            try:
                vorher = katalog.produkt_werte({}, vorhanden, importiert=True)
            except Abgelehnt:
                vorher = {f: vorhanden[f] for f in katalog.PRODUKT_FELDER}
            # importiert: Die Beschreibung kommt wie bisher herein – auch länger als katalog.BESCHREIBUNG_MAX, sonst
            # scheiterte der Austausch dev → Produktion an Beschreibungen von vor der Grenze.
            nachher = katalog.produkt_werte(d, vorhanden, importiert=True)
            if vorher != nachher:
                _materialart_pruefen(vorhanden, nachher)
                intervall_vorher = herstellerseite(vorhanden)[0]
                seit = _journalstand()
                wechsel = nachher["category_id"] != vorhanden["category_id"]
                zuweisungen = _zuweisungen_stand(pid) if wechsel else None
                _ohne_konflikt(katalog.produkt_aendern, pid, d, importiert=True)
                if wechsel:
                    _kategoriewechsel_merken(lauf, ort, name, vorhanden, nachher["category_id"], zuweisungen)
                bericht["produkte"]["geaendert"] += 1
                lauf.notiz(f"Produkt „{katalog.produktname(nachher)}“: geändert "
                           f"({_geaendert(vorher, nachher)})")
                if nachher["description"] != vorher["description"]:
                    _lange_beschreibung(lauf, name, nachher["description"])
                intervall = herstellerseite(katalog.produkt(pid))[0]
                teile = []
                if intervall != intervall_vorher:
                    teile.append(f"Prüfintervall {intervall_vorher or '–'} → {intervall or '–'} Monate")
                if nachher["lifetime_years"] != vorher["lifetime_years"]:
                    teile.append(f"Lebensdauer {vorher['lifetime_years'] or '–'} → {nachher['lifetime_years'] or '–'} Jahre")
                artikel = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ? AND lock_state <> 'ausgesondert'",
                                   (pid,), one=True)["n"]
                _folgen_melden(lauf, ort, name, artikel, teile, seit)
            else:
                bericht["produkte"]["unveraendert"] += 1
                lauf.unveraendert.add(pid)
            lauf.uid_uebernehmen("mat_product", "product", vorhanden, uid)
            bild = vorhanden["image"]
        else:
            pid = _ohne_konflikt(katalog.produkt_anlegen, d, importiert=True)
            lauf.uid_setzen("mat_product", pid, uid)
            bericht["produkte"]["neu"] += 1
            lauf.notiz(f"Produkt „{name}“: neu")
            _lange_beschreibung(lauf, name, katalog.produkt(pid)["description"])
            bild = ""
    except _Konflikt as exc:
        lauf.zurueckgestellt.append((lambda: _produkt(n, e, lauf), f"{ort} ({name}): {exc}"))
        return False
    except Abgelehnt as exc:
        bericht["fehler"].append(f"{ort} ({name}): {exc}")
        return True
    lauf.produkte.add(pid)
    if lauf.version >= 2:
        _bild(e, pid, bild, ort, name, lauf)
        try:
            _dokumente(e.get("dokumente"), "product_id", pid, ort, name, lauf)
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort} ({name}): {exc}")
    if "bestandteile" in e:
        lauf.listen.append((ort, name, e, pid))
    if "formular_von" in e:
        lauf.formularverweise.append((ort, name, e["formular_von"], pid))
    return True


# --- Bestandteil-Listen (Schritt 25) ---------------------------------------------------------------------------------

# Seit dem Rückbau der Set-Funktion (Schritt 26, Wunsch vom 25.10.2026) – Fehler dieses Produkts.
SET_ENTFALLEN = ("„set“: true – Sets gibt es nicht mehr. Ein Herstellerset steht als Produkt mit Bestandteil-Liste in der "
                 "Datei („bestandteile“: [{„bezeichnung“, „anzahl“}]); zusammengestellte Sätze legst du im Bestand als "
                 "Ordner der Art „Set“ an.")
LISTE_ABGEWIESEN = ("Die Bestandteil-Liste ließ sich nicht speichern – eine Position verletzt eine Regel (etwa eine leere "
                    "Bezeichnung). Bitte die Positionen dieses Produkts prüfen.")


def _liste_angabe(ort, name, e, lauf):
    """Die Bestandteil-Liste aus einem Produkteintrag als Liste von Objekten – oder None (übergangen): Eine Liste aus
    Texten (Recherche-Manifeste) ist ein Hinweis und zählt wie „fehlt“."""
    liste = e.get("bestandteile")
    if liste is None:
        return None
    if not isinstance(liste, list):
        raise Abgelehnt("„bestandteile“ muss eine Liste sein.")
    if liste and all(isinstance(x, str) for x in liste):
        lauf.bericht["hinweise"].append(f"{ort} ({name}): „bestandteile“ ist eine Liste aus Texten – übergangen. Eine "
                                        "Bestandteil-Liste braucht je Position ein Objekt (bezeichnung, anzahl).")
        return None
    if any(not isinstance(x, dict) for x in liste):
        raise Abgelehnt("„bestandteile“: jede Position ist ein Objekt (bezeichnung, anzahl).")
    return liste


def _bestandteillisten(lauf):
    """Zweiter Durchgang nach allen Produkten der Datei: die Bestandteil-Listen als Ganzes ersetzen."""
    bericht = lauf.bericht
    for ort, name, e, pid in lauf.listen:
        try:
            liste = _liste_angabe(ort, name, e, lauf)
            if liste is None:
                continue
            neu = not stueckliste.zeilen(pid)
            if stueckliste.ersetzen(pid, liste, grund="Katalogimport"):
                bericht["bestandteillisten"]["neu" if neu and liste else "geaendert"] += 1
                # Ändert sich am Produkt nur die Liste, zählt es nicht mehr als „unveraendert“.
                if pid in lauf.unveraendert:
                    lauf.unveraendert.discard(pid)
                    bericht["produkte"]["unveraendert"] -= 1
                    bericht["produkte"]["geaendert"] += 1
                lauf.notiz(f"Produkt „{name}“: Bestandteil-Liste ersetzt ({len(liste)} Position"
                           f"{'en' if len(liste) != 1 else ''})")
            else:
                bericht["bestandteillisten"]["unveraendert"] += 1
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort} ({name}): {exc}")
        except sqlite3.IntegrityError as exc:
            # Was die Prüfung im Dienst nicht fängt und erst die Datenbank abweist, ist ein Fehler dieses Produkts –
            # nicht ein Abbruch des ganzen Imports ohne Fundstelle (Prüfung Sicherheit, S1). Mit dem Fehler wird
            # ohnehin nichts gespeichert (_durchgang rollt zurück).
            log.warning("Katalogimport, %s (%s): %s", ort, name, exc)
            bericht["fehler"].append(f"{ort} ({name}): {LISTE_ABGEWIESEN}")


def _bild(e, pid, alt, ort, name, lauf):
    """Produktbild: gleiche SHA-256 des Originals – unverändert; sonst ein neues, das alte wird nach dem Commit
    gelöscht. Ohne „bild“ in der Datei bleibt das Bild hier, wie es ist."""
    if e.get("bild") in (None, ""):
        return
    try:
        datei = lauf.datei(e["bild"], "bild")
        if alt and lauf.bild_summe(alt) == datei["sha256"]:
            lauf.bericht["bilder"]["unveraendert"] += 1
            return
        neu = lauf.ablegen(f"{ort}.bild", datei)
        db.execute("UPDATE mat_product SET image = ?, updated_at = ? WHERE id = ?", (neu, db.now(), pid))
        journal.eintragen("product", pid, "bild", {"image": alt}, {"image": neu})
    except Abgelehnt as exc:
        lauf.bericht["fehler"].append(f"{ort}.bild ({name}): {exc}")
        return
    if alt:
        lauf.alte_bilder.append(alt)
    lauf.bericht["bilder"]["geaendert" if alt else "neu"] += 1
    lauf.notiz(f"Bild an „{name}“: {'ersetzt' if alt else 'neu'}")


# --- Dokumente -------------------------------------------------------------------------------------

class _Dateiname:
    """Für katalog._dokument_werte: Ein Dokument mit Datei braucht keine Adresse; ohne Titel gilt der Dateiname."""

    def __init__(self, name):
        self.filename = name


def _vorgaenger(e):
    """Die Kennungen der früheren Versionen eines Dokuments aus der Datei („vorgaenger“, neueste zuerst):
    [("datei", SHA-256) | ("link", Adresse, Versionsstand)]. Ältere Exporte und Dateien von Hand haben keine."""
    liste = e.get("vorgaenger")
    if liste is None:
        return []
    if not isinstance(liste, list) or len(liste) > MAX_VORGAENGER:
        raise Abgelehnt(f"„vorgaenger“ muss eine Liste sein (höchstens {MAX_VORGAENGER} Einträge).")
    out = []
    for v in liste:
        if isinstance(v, dict) and isinstance(v.get("sha256"), str) and _SHA256.fullmatch(v["sha256"]):
            out.append(("datei", v["sha256"]))
        elif isinstance(v, dict) and isinstance(v.get("url"), str) and v["url"]:
            out.append(("link", text(v, "url", "Adresse", 500), text(v, "version", "Versionsstand", 40)))
        else:
            raise Abgelehnt("„vorgaenger“: Jeder Eintrag braucht eine „sha256“ (64 Zeichen 0–9 und a–f) oder eine „url“.")
    return out


def _passt(x, kennung):
    """Ist das Dokument x hier das mit dieser Kennung – gleiche Datei bzw. gleicher Link in gleicher Version?"""
    if kennung[0] == "datei":
        return bool(x["file_path"]) and x["sha256"] == kennung[1]
    return not x["file_path"] and x["url"] == kennung[1] and (x["version"] or "") == kennung[2]


def _vorgaenger_nach_titel(aktuelle, w):
    """Rückgriff ohne passende Vorgängerkennung: das aktuelle Dokument gleicher Art und gleichen Titels – aber nur, wenn
    genau eins davon schon gilt, wenn die neue Version beginnt. Bei zwei (etwa „Datenblatt“ in den Fassungen de und
    en) wäre jede Wahl geraten und könnte die Versionsketten über Kreuz verknüpfen."""
    kandidaten = [x for x in aktuelle if x["kind"] == w["kind"] and x["title"].casefold() == w["title"].casefold()]
    frueher = [x for x in kandidaten if x["valid_from"] <= w["valid_from"]]
    if len(frueher) > 1:
        raise Abgelehnt(f"Mehrdeutig: Hier gibt es {len(frueher)} aktuelle Dokumente dieser Art mit dem Titel "
                        f"„{w['title']}“, und welches die neue Version bekommt, steht nicht in der Datei. Die Titel hier "
                        "unterscheiden – oder die Datei neu exportieren: Ein Export dieser Version nennt je Dokument "
                        "seine früheren Versionen.")
    if frueher:
        return frueher[0]
    return min(kandidaten, key=lambda x: x["valid_from"]) if kandidaten else None


def _dokumente(liste, spalte, ziel, stelle, zielname, lauf):
    """Dokumente an einer Kategorie oder einem Produkt, in drei Schritten:
      1. Jeder Eintrag belegt sein Gegenstück, wenn es dasselbe Dokument hier schon gibt – gleiche Datei (SHA-256)
         bzw. gleicher Link in gleicher Version unter den aktuellen: unverändert.
      2. Die übrigen werden neue Version des aktuellen Dokuments, das eine ihrer früheren Versionen ist
         („vorgaenger“ in der Datei).
      3. Sonst gleiche Art und gleicher Titel, nur eindeutig (_vorgaenger_nach_titel); sonst ein neues Dokument.
    Erst alle exakten Treffer, dann die Ketten: Sonst nähme ein Eintrag einem späteren das Gegenstück weg. Nichts wird
    gelöscht oder zurückgezogen."""
    if liste is None:
        return
    if not isinstance(liste, list):
        raise Abgelehnt("„dokumente“ muss eine Liste sein.")
    bericht = lauf.bericht

    def frei():
        return [x for x in aktuelle_dokumente(spalte, ziel) if x["id"] not in lauf.belegt]

    offen = []
    for n, e in enumerate(liste):
        ort = f"{stelle}.dokumente[{n}]"
        titel = e.get("titel") if isinstance(e, dict) and isinstance(e.get("titel"), str) else "?"
        try:
            if not isinstance(e, dict):
                raise Abgelehnt("Eintrag ist kein Objekt.")
            if ("datei" in e) == ("url" in e):
                raise Abgelehnt("Ein Dokument hat entweder eine „datei“ (im Archiv) oder eine „url“.")
            d = {"kind": e.get("art"), "title": e.get("titel"), "version": e.get("version"),
                 "valid_from": e.get("gueltig_ab"), "url": e.get("url")}
            datei = lauf.datei(e["datei"], "dokument") if "datei" in e else None
            w = katalog._dokument_werte(d, None, _Dateiname(datei["name"]) if datei else None)
            vorgaenger = _vorgaenger(e)
            kennung = ("datei", datei["sha256"]) if datei else ("link", w["url"], w["version"])
            gleich = next((x for x in frei() if _passt(x, kennung)), None)
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort} ({zielname}: {titel}): {exc}")
            continue
        if gleich:
            lauf.belegt.add(gleich["id"])
            bericht["dokumente"]["unveraendert"] += 1
        else:
            offen.append({"ort": ort, "titel": titel, "w": w, "datei": datei, "vorgaenger": vorgaenger})

    def einfuegen(x, alt):
        w = x["w"]
        try:
            if alt and w["valid_from"] < alt["valid_from"]:
                raise Abgelehnt(f"Die neue Version gälte ab {w['valid_from']}, die vorhandene hier aber erst ab "
                                f"{alt['valid_from']} – eine neue Version kann nicht vor der alten gültig werden. Das "
                                "Dokument hier umbenennen oder zurückziehen, dann kommt es als eigenes dazu.")
            abgelegt = lauf.ablegen(x["ort"], x["datei"]) if x["datei"] else None
            did = _dokument_einfuegen(spalte, ziel, w, abgelegt, alt)
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{x['ort']} ({zielname}: {x['titel']}): {exc}")
            return
        lauf.belegt.add(did)
        bericht["dokumente"]["neue_version" if alt else "neu"] += 1
        lauf.notiz(f"Dokument „{w['title']}“ an „{zielname}“: {'neue Version' if alt else 'neu'}")

    rest = []
    for x in offen:
        kandidaten = frei()
        alt = next((d for k in x["vorgaenger"] for d in kandidaten if _passt(d, k)), None)
        if alt:
            einfuegen(x, alt)
        else:
            rest.append(x)
    for x in rest:
        try:
            alt = _vorgaenger_nach_titel(frei(), x["w"])
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{x['ort']} ({zielname}: {x['titel']}): {exc}")
            continue
        einfuegen(x, alt)


def _dokument_einfuegen(spalte, ziel, w, abgelegt, ersetzt):
    """Wie katalog.dokument_anlegen – nur mit einer schon abgelegten Datei (abgelegt: Name, MIME, Größe, SHA-256),
    die der Import selbst wieder entfernt, wenn die Transaktion scheitert. Dass die Datei unter der Schreibsperre
    dieses Durchgangs wirklich liegt, hat _Lauf.ablegen eben davor sichergestellt (beim Planen ist sie ein
    Platzhalter)."""
    name, mime, groesse, sha = abgelegt or (None, "", 0, None)
    pid, kid = (ziel, None) if spalte == "product_id" else (None, ziel)
    uid, uname = akteur()
    did = db.execute(
        "INSERT INTO mat_product_document (product_id, category_id, kind, title, file_path, url, mime, size, sha256, "
        "version, valid_from, replaces_id, uploaded_by, uploaded_by_name, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, kid, w["kind"], w["title"], name, w["url"], mime or "", groesse, sha or "", w["version"], w["valid_from"],
         ersetzt["id"] if ersetzt else None, uid, uname, db.now()))
    nachher = dict(w, file_path=name, sha256=sha, size=groesse)
    nachher.update({"category_id": kid} if kid else {"product_id": pid})
    journal.eintragen("document", did, "neue_version" if ersetzt else "angelegt",
                      {"ersetzt": ersetzt["id"]} if ersetzt else None, nachher)
    return did


# --- Formulare (seit Schritt 38 ein Pool je Kategorie, siehe Kopf) -------------------------------------------------

def _produkt_ziel(angabe, lauf):
    if not isinstance(angabe, dict):
        raise Abgelehnt("Produktangabe ist kein Objekt.")
    uid = lauf.uid(angabe)
    p = db.query("SELECT * FROM mat_product WHERE uid = ?", (uid,), one=True) if uid else None
    p = p or db.query("SELECT * FROM mat_product WHERE dedupe_key = ?", (_produkt_key(angabe),), one=True)
    if not p:
        teile = [angabe.get(k) if isinstance(angabe.get(k), str) and angabe.get(k).strip() else "–"
                 for k in ("hersteller", "modell", "artikelnummer")]
        raise Abgelehnt(f"Das Produkt „{' | '.join(teile)}“ (Hersteller | Modell | Artikelnummer) gibt es weder im Katalog "
                        "noch in der Datei.")
    return p


def _produkt_text(p):
    """Ein Produkt hier für Meldungen: „Hersteller Modell (Artikelnummer)“."""
    return katalog.produktname(p) + (f" ({p['article_no']})" if p.get("article_no") else "")


# Verglichen wird ohne „kritisch“: Die Marke ist am 03.11.2026 entfallen (die Spalte is_critical mit Schritt 37) – eine
# Katalogdatei, die sie noch trägt, gilt beim erneuten Import als unverändert (keine neue Version nur wegen der Marke).
# Seit Schritt 39 zählt auch die Untergruppe (fehlt sie in einer älteren Datei, ist sie leer – katalog.punkte_pruefen).
_PUNKTFELDER = ("group_name", "untergruppe", "label", "editor", "mandatory", "expected_value")
# Ein führendes „DEMO“ im Formulartitel („DEMO – “, „DEMO-“, „DEMO “) nimmt der Import heraus – auf dev heißen die
# Platzhalter so, in der Produktion gibt es kein DEMO (Entscheidung vom 04.11.2026, katalog-transfer). Groß oder klein
# („demo - …“, „Demo – …“; Sicherheitsprüfung Formular-Pool, Hinweis 4); „Demonstration …“ bleibt.
_DEMO_VORN = re.compile(r"^DEMO(?:\s*[–—-]\s*|\s+)", re.IGNORECASE)


def ohne_demo(titel):
    return _DEMO_VORN.sub("", titel, count=1).strip()


def _formular_titel(e, ersatz):
    """Der Titel eines Formulareintrags ohne führendes „DEMO“; leer (ältere Dateien) heißt er „Prüfformular <ersatz>“
    wie nach der Migration (Titel sind seit dem Formular-Pool Pflicht)."""
    titel = _name(e.get("titel"), "Titel", 160) if isinstance(e.get("titel"), str) else ""
    return ohne_demo(titel) or f"Prüfformular {ersatz}"[:160]


def _formular_mit_titel(heimat, titel, passt=None):
    """Ein Formular im Pool von heimat, dessen aktive (sonst neueste) Version so heißt – das erste, für das passt(Kennung)
    gilt – oder None."""
    for r in db.query("SELECT id FROM mat_formular WHERE category_id = ? ORDER BY id", (heimat,)):
        if katalog._anzeige_titel(r["id"]) == titel and (passt is None or passt(r["id"])):
            return katalog.pool_formular(r["id"])
    return None


def _nur_fuer(pf, erlaubt):
    """Gilt das Formular höchstens für diese Ziele (erlaubt: {(„category_id“ | „product_id“, Kennung)}) – ist es nirgends
    sonst Standard und keinem anderen Produkt zugewiesen? Nur ein solches darf ein Eintrag aus Format 1/2 umschreiben
    (Sicherheitsprüfung Formular-Pool, Befund 1)."""
    return all((("category_id", z["category_id"]) if z["category_id"] else ("product_id", z["product_id"])) in erlaubt
               for z in db.query("SELECT category_id, product_id FROM mat_formular_zuweisung WHERE formular_id = ?",
                                 (pf,)))


def _uebernehmer(ziel, lauf):
    """Die Produkte, die laut derselben Datei das Formular von Produkt ziel übernehmen („formular_von“, Format 1/2) – an
    ihnen hängt es nach dem Import ohnehin (_zuweisungen); ein Formular, das nur ihnen und ziel gilt, bleibt das eigene."""
    out = set()
    for _ort, _name, angabe, pid in lauf.formularverweise:
        if angabe is None:
            continue
        try:
            if _produkt_ziel(angabe, lauf)["id"] == ziel:
                out.add(pid)
        except Abgelehnt:
            continue                               # meldet _zuweisungen
    return out


def _versionen(pf, titel, punkte_roh, aktivieren, zielname, lauf, frisch=False):
    """Die Versionen eines Formulars an die Datei angleichen: Gleicht die aktive Version Titel und Prüfpunkten, bleibt
    alles; sonst wird die neueste aktiviert, wenn sie gleicht, oder eine neue Version angelegt (und aktiviert). Ohne
    aktivieren (Format 1/2 mit „aktivieren“: false) nur angelegt. frisch: eben angelegtes Formular (Version 1 aus der
    Datei), zählt als neu. Liefert die Version, die der Datei entspricht."""
    bericht = lauf.bericht
    neu = [{k: p[k] for k in _PUNKTFELDER} for p in katalog.punkte_pruefen(punkte_roh)]

    def gleich(f):
        return f["title"] == titel and [{k: p[k] for k in _PUNKTFELDER} for p in katalog.punkte(f["id"])] == neu

    aktive = katalog._aktive_version(pf)
    letzte = db.query("SELECT * FROM mat_form WHERE formular_id = ? ORDER BY version DESC LIMIT 1", (pf,), one=True)
    if frisch:
        fid = letzte["id"]
    elif aktivieren and aktive and gleich(aktive):
        fid = aktive["id"]
    elif letzte and gleich(letzte):
        fid = letzte["id"]
    else:
        fid = None
    angelegt = frisch or not fid
    if not fid:
        fid = katalog.formular_anlegen({"formular_id": pf, "titel": titel, "punkte": punkte_roh})
    if angelegt:
        bericht["formulare"]["neu"] += 1
    else:
        bericht["formulare"]["unveraendert"] += 1
    aktiviert = aktivieren and not katalog.formular(fid)["active"]
    if aktiviert:
        katalog.formular_aktivieren(fid)
    if angelegt or aktiviert:
        version = katalog.formular(fid)["version"]
        # Wofür das geänderte Formular schon gilt (vor den Zuweisungen der Datei) – ein geteiltes ändert mehr als das
        # Ziel des Eintrags (Sicherheitsprüfung Formular-Pool, Befund 1).
        ziele = "" if frisch else katalog._ziele_text(pf)
        lauf.notiz(f"Formular „{titel}“ ({zielname}): " + (f"neue Version {version}{', aktiv' if aktiviert else ''}"
                                                          if angelegt else f"Version {version} aktiviert")
                   + (" – neu im Pool" if frisch else f" – gilt bisher: {ziele}" if ziele else " – bisher nirgends zugewiesen"))
    return fid


def _neues_formular(heimat, titel, punkte_roh, lauf, uid=None):
    pf, _vid = katalog.pool_anlegen({"kategorie_id": heimat, "titel": titel, "punkte": punkte_roh})
    lauf.uid_setzen("mat_formular", pf, uid)
    return pf


def _formulare(liste, lauf):
    if not isinstance(liste, list):
        raise Abgelehnt("„formulare“ muss eine Liste sein.")
    bericht = lauf.bericht
    gesehen = {}
    for n, e in enumerate(liste):
        ort = f"formulare[{n}]"
        try:
            if not isinstance(e, dict):
                raise Abgelehnt("Eintrag ist kein Objekt.")
            if lauf.version >= 3:
                _formular_3(e, ort, lauf, gesehen)
            else:
                _formular_alt(e, ort, lauf)
        except Abgelehnt as exc:
            titel_roh = e.get("titel") if isinstance(e, dict) and isinstance(e.get("titel"), str) else ""
            bericht["fehler"].append(f"{ort}{f' ({titel_roh})' if titel_roh else ''}: {exc}")


def _formular_3(e, ort, lauf, gesehen):
    """Format 3: ein Formular des Pools mit Heimat, Titel, Prüfpunkten und seinen Zuweisungen (gesetzt erst nach allen
    Formularen, _zuweisungen). Abgeglichen über die uid, sonst über den Titel in derselben Heimat (Entscheidung E3); die
    Datei kommt nur mit aktiven Formularen (E1) – es wird hier aktiv."""
    uid = lauf.uid(e)
    if uid and uid in gesehen:
        raise Abgelehnt(f"Die Katalogkennung {uid} steht schon bei {gesehen[uid]}.")
    if uid:
        gesehen[uid] = ort
    heimat = _kategorie_ziel(e, lauf)
    titel = _formular_titel(e, katalog.kategorie(heimat)["name"])
    if not katalog.punkte_pruefen(e.get("punkte")):
        raise Abgelehnt("Ein Formular braucht mindestens einen Prüfpunkt.")
    zielname = f"Kategorie „{_kategorie_pfadname(heimat)}“"
    pf_row = db.query("SELECT * FROM mat_formular WHERE uid = ?", (uid,), one=True) if uid else None
    if pf_row and pf_row["category_id"] != heimat:
        raise Abgelehnt(f"Das Prüfformular steht hier im Pool von „{_kategorie_pfadname(pf_row['category_id'])}“, in der "
                        f"Datei in „{_kategorie_pfadname(heimat)}“ – Formulare lassen sich nicht verschieben.")
    if not pf_row:
        pf_row = _formular_mit_titel(heimat, titel)
        if pf_row:
            # Über den Titel gefunden (E3): Das Formular hier übernimmt Punkte und Kennung der Datei – der Bericht sagt,
            # wofür es bisher galt (Sicherheitsprüfung Formular-Pool, Hinweis 1).
            ziele = katalog._ziele_text(pf_row["id"])
            lauf.bericht["hinweise"].append(
                f"{ort} ({titel}): über den Titel dem Prüfformular hier im Pool von „{_kategorie_pfadname(heimat)}“ "
                f"zugeordnet{' – es übernimmt die Katalogkennung der Datei' if uid and pf_row['uid'] != uid else ''}; "
                + (f"bisher {ziele}." if ziele else "bisher nirgends zugewiesen."))
        if pf_row and uid and pf_row["uid"] != uid:
            lauf.uid_uebernehmen("mat_formular", "formular", pf_row, uid)
    pf = pf_row["id"] if pf_row else _neues_formular(heimat, titel, e.get("punkte"), lauf, uid)
    _versionen(pf, titel, e.get("punkte"), True, zielname, lauf, frisch=not pf_row)
    lauf.formulare.append((ort, titel, pf, e.get("standard_fuer"), e.get("zugewiesen")))


def _formular_alt(e, ort, lauf):
    """Format 1 und 2: ein Formular gehört zu einer „kategorie“ (generisch) oder einem „produkt“ (spezifisch). Es kommt in
    den Pool der Kategorie bzw. der Kategorie des Produkts (wie in der Migration, Schritt 38) und wird – mit „aktivieren“
    (Vorgabe) – Standard der Kategorie bzw. dem Produkt zugewiesen. Abgeglichen über den Titel in der Heimat, sonst das
    Formular, das dort schon Standard bzw. dem Produkt zugewiesen ist – beides nur, wenn es für nichts anderes gilt
    (_nur_fuer; beim Produkt zählen die mit, die es laut derselben Datei übernehmen): Format 1/2 kannte nur Formulare je
    Ziel, ein geteiltes Formular des Pools (Standard, weitere Produkte) darf ein solcher Eintrag nicht umschreiben – er
    bekommt ein neues im Pool (Sicherheitsprüfung Formular-Pool, Befund 1)."""
    if ("kategorie" in e) == ("produkt" in e):
        raise Abgelehnt("Ein Formular gehört entweder zu einer „kategorie“ oder zu einem „produkt“.")
    if "kategorie" in e:
        heimat = _kategorie_ziel(e, lauf)
        spalte, ziel = "category_id", heimat
        name = katalog.kategorie(heimat)["name"]
        zielname = f"Kategorie „{_kategorie_pfadname(heimat)}“"
    else:
        p = _produkt_ziel(e["produkt"], lauf)
        heimat, spalte, ziel = p["category_id"], "product_id", p["id"]
        name = katalog.produktname(p)
        zielname = f"Produkt „{name}“"
    titel = _formular_titel(e, name)
    if not katalog.punkte_pruefen(e.get("punkte")):
        raise Abgelehnt("Ein Formular braucht mindestens einen Prüfpunkt.")
    aktivieren = e.get("aktivieren", True) is not False
    erlaubt = {(spalte, ziel)} | ({("product_id", q) for q in _uebernehmer(ziel, lauf)} if spalte == "product_id"
                                  else set())
    pf_row = _formular_mit_titel(heimat, titel, lambda pf: _nur_fuer(pf, erlaubt))
    if not pf_row:
        z = db.query(f"SELECT f.* FROM mat_formular_zuweisung z JOIN mat_formular f ON f.id = z.formular_id "
                     f"WHERE z.{spalte} = ? AND f.category_id = ?", (ziel, heimat), one=True)
        pf_row = z if z and _nur_fuer(z["id"], erlaubt) else None
        geteilt = None if pf_row else (_formular_mit_titel(heimat, titel) or z)
        if geteilt:
            lauf.bericht["hinweise"].append(
                f"{ort} ({titel}): Das Prüfformular „{katalog._anzeige_titel(geteilt['id'])}“ hier ist "
                f"{katalog._ziele_text(geteilt['id'])} – {zielname} bekommt ein neues im Pool, das bestehende bleibt "
                "unverändert.")
    pf = pf_row["id"] if pf_row else _neues_formular(heimat, titel, e.get("punkte"), lauf)
    _versionen(pf, titel, e.get("punkte"), aktivieren, zielname, lauf, frisch=not pf_row)
    if aktivieren:
        lauf.formulare.append((ort, titel, pf, *(([{"_id": ziel}], None) if spalte == "category_id"
                                                 else (None, [{"_id": ziel}]))))


def _zuweisungen(lauf):
    """Die Zuweisungen aus der Datei setzen – nach allen Formularen. Format 3: Die Datei ist maßgeblich (Entscheidung E2):
    Für jedes Formular und jedes Ziel (Kategorie, Produkt) der Datei gilt danach genau, was sie sagt; eine Zuweisung hier,
    an der ein Formular oder ein Ziel der Datei beteiligt ist und die sie nicht nennt, wird gelöst. Zuweisungen zwischen
    Formularen und Zielen, die nur es hier gibt, bleiben. Format 1/2 setzt nur (Standard bzw. Produkt des Formulars und
    „formular_von“) und löst nichts. Was hier nicht geht (Ziel fehlt, liegt nicht unter der Heimat, Länge), ist ein
    Hinweis."""
    bericht = lauf.bericht
    zahl = bericht["zuweisungen"]
    wunsch = {}                                    # ("category_id"|"product_id", Kennung) → (Formular, Titel, Fundstelle)
    for ort, titel, pf, kats, prods in lauf.formulare:
        for spalte, liste, wo in (("category_id", kats, "standard_fuer"), ("product_id", prods, "zugewiesen")):
            if liste is None:
                continue
            if not isinstance(liste, list):
                bericht["fehler"].append(f"{ort} ({titel}): „{wo}“ muss eine Liste sein.")
                continue
            for x in liste:
                try:
                    if isinstance(x, dict) and "_id" in x:
                        ziel = x["_id"]
                    elif spalte == "category_id":
                        if not isinstance(x, dict):
                            raise Abgelehnt("Kategorieangabe ist kein Objekt.")
                        ziel = _kategorie_ziel(x, lauf)
                    else:
                        ziel = _produkt_ziel(x, lauf)["id"]
                except Abgelehnt as exc:
                    bericht["hinweise"].append(f"{ort} ({titel}): nicht zugewiesen – {exc}")
                    continue
                if (spalte, ziel) in wunsch and wunsch[(spalte, ziel)][0] != pf:
                    bericht["hinweise"].append(f"{ort} ({titel}): {_ziel_text(spalte, ziel)} steht in der Datei schon bei "
                                               f"„{wunsch[(spalte, ziel)][1]}“ – bleibt dort.")
                    continue
                wunsch[(spalte, ziel)] = (pf, titel, ort)
    for ort, name, angabe, pid in lauf.formularverweise:
        if angabe is None:
            continue
        try:
            q = _produkt_ziel(angabe, lauf)
            # Das Formular der Quelle: aus derselben Datei (gleich gesetzt) oder hier schon zugewiesen.
            pf = (wunsch.get(("product_id", q["id"])) or (None,))[0]
            z = db.query("SELECT formular_id FROM mat_formular_zuweisung WHERE product_id = ?", (q["id"],), one=True)
            pf = pf or (z["formular_id"] if z else None)
            if not pf:
                raise Abgelehnt(f"„{katalog.produktname(q)}“ hat hier kein zugewiesenes Prüfformular")
        except Abgelehnt as exc:
            bericht["hinweise"].append(f"{ort} ({name}): Prüfformular nicht übernommen – {exc}.")
            continue
        wunsch.setdefault(("product_id", pid), (pf, katalog._anzeige_titel(pf), ort))
    if lauf.version >= 3:
        formulare = {pf for _o, _t, pf, _k, _p in lauf.formulare}
        geloest = []
        for z in db.query("SELECT * FROM mat_formular_zuweisung ORDER BY id"):
            spalte, ziel = ("category_id", z["category_id"]) if z["category_id"] else ("product_id", z["product_id"])
            beteiligt = (z["formular_id"] in formulare or ziel in (lauf.kategorien if spalte == "category_id"
                                                                    else lauf.produkte))
            if beteiligt and wunsch.get((spalte, ziel), (None,))[0] != z["formular_id"]:
                if (spalte, ziel) in wunsch:
                    continue                       # wechselt gleich zum Formular der Datei (Journal dort)
                titel_z = katalog._anzeige_titel(z["formular_id"])
                katalog._zuweisung_loesen(z, "steht nicht in der Katalogdatei")
                zahl["geloest"] += 1
                geloest.append(f"„{titel_z}“ an {_ziel_text(spalte, ziel)}")
                lauf.notiz(f"Prüfformular „{titel_z}“: {_ziel_text(spalte, ziel)} nicht mehr zugewiesen")
        if geloest and not lauf.formulare:
            # Eine Datei ohne Formulare (etwa der Export einer Instanz ohne aktive) ist trotzdem maßgeblich (E2) – das
            # soll niemand übersehen (Sicherheitsprüfung Formular-Pool, Hinweis 2).
            bericht["warnungen"].append(
                f"Die Datei enthält keine Prüfformulare. Weil sie maßgeblich ist, löst der Import {len(geloest)} "
                f"Zuweisung{'en' if len(geloest) != 1 else ''} an ihre Kategorien und Produkte: "
                + "; ".join(geloest[:10]) + (f" und {len(geloest) - 10} weitere" if len(geloest) > 10 else "")
                + ". Diese Produkte fallen auf den Standard darüber zurück oder sind danach nicht prüfbar.")
    for (spalte, ziel), (pf, titel, ort) in wunsch.items():
        da = db.query(f"SELECT formular_id FROM mat_formular_zuweisung WHERE {spalte} = ?", (ziel,), one=True)
        if da and da["formular_id"] == pf:
            zahl["unveraendert"] += 1
            continue
        heimat = katalog.pool_formular(pf)["category_id"]
        kategorie = ziel if spalte == "category_id" else katalog.produkt(ziel)["category_id"]
        if kategorie not in katalog._unterkategorien(heimat):
            bericht["hinweise"].append(f"{ort} ({titel}): {_ziel_text(spalte, ziel)} liegt in dieser Materialablage nicht unter "
                                       f"„{_kategorie_pfadname(heimat)}“ – nicht zugewiesen.")
            continue
        aktiv = katalog._aktive_version(pf)
        grund = (katalog.laenge_grund(katalog.produkt(ziel), katalog._hat_laengenpunkt(aktiv["id"]))
                 if spalte == "product_id" and aktiv else "" if aktiv else katalog.NUR_AKTIV_ZUWEISEN)
        if grund:
            bericht["hinweise"].append(f"{ort} ({titel}): {_ziel_text(spalte, ziel)} nicht zugewiesen – {grund}")
            continue
        katalog._zuweisen(pf, spalte, ziel, aktiv["title"], None)
        zahl["neu"] += 1
        lauf.notiz(f"Prüfformular „{titel}“: " + ("Standard für " if spalte == "category_id" else "zugewiesen an ")
                   + _ziel_text(spalte, ziel))


def _ziel_text(spalte, ziel):
    if spalte == "category_id":
        return f"Kategorie „{_kategorie_pfadname(ziel)}“"
    return f"„{katalog.produktname(katalog.produkt(ziel))}“"


def _gekuerzt(t, n):
    """Höchstens n Zeichen: ein längerer Text endet am letzten Leerzeichen davor mit „…“ (geschütztes Leerzeichen davor)."""
    if len(t) <= n:
        return t
    kurz = t[:n - 2]
    return (kurz.rsplit(" ", 1)[0] if " " in kurz else kurz).rstrip(" ,;") + "\u00a0…"          # „…“ bricht nicht allein um


# --- Dateien im Archiv -----------------------------------------------------------------------------

def _uids(daten):
    """Die Katalogkennungen der Datei: ({uid: [Fundstellen]} der Kategorien, … der Produkte)."""
    kat, prod = {}, {}

    def kats(liste, stelle, tiefe):
        if not isinstance(liste, list) or tiefe > MAX_TIEFE:
            return
        for n, e in enumerate(liste):
            if isinstance(e, dict):
                if isinstance(e.get("uid"), str) and e["uid"]:
                    kat.setdefault(e["uid"], []).append(f"{stelle}[{n}]")
                kats(e.get("unterkategorien"), f"{stelle}[{n}].unterkategorien", tiefe + 1)

    kats(daten.get("kategorien"), "kategorien", 0)
    produkte = daten.get("produkte")
    for n, e in enumerate(produkte if isinstance(produkte, list) else []):
        if isinstance(e, dict) and isinstance(e.get("uid"), str) and e["uid"]:
            prod.setdefault(e["uid"], []).append(f"produkte[{n}]")
    return kat, prod


def _verweise(daten):
    """Alle Dateiverweise der Datei: {(Pfad, Art)} mit Art „bild“ oder „dokument“."""
    out = set()

    def doks(e):
        liste = e.get("dokumente")
        for x in liste if isinstance(liste, list) else []:
            if isinstance(x, dict) and isinstance(x.get("datei"), str):
                out.add((x["datei"], "dokument"))

    def kats(liste, tiefe):
        if not isinstance(liste, list) or tiefe > MAX_TIEFE:
            return
        for e in liste:
            if isinstance(e, dict):
                doks(e)
                kats(e.get("unterkategorien"), tiefe + 1)

    kats(daten.get("kategorien"), 0)
    produkte = daten.get("produkte")
    for e in produkte if isinstance(produkte, list) else []:
        if isinstance(e, dict):
            if isinstance(e.get("bild"), str) and e["bild"]:
                out.add((e["bild"], "bild"))
            doks(e)
    return out


def _pfad_pruefen(pfad):
    """Ein Verweis ist ein schlichter relativer Pfad im Archiv. Entpackt wird ohnehin nie nach Namen – aber ein
    absoluter Pfad, „..“ oder ein Rückstrich hat in einem Katalog-Export nichts zu suchen."""
    teile = pfad.split("/")
    if (len(pfad) > 300 or pfad.startswith("/") or "\\" in pfad or ":" in pfad
            or re.search(r"[\x00-\x1f\x7f]", pfad) or any(t in ("", ".", "..") for t in teile)):
        raise Abgelehnt(f"Unzulässiger Dateiverweis „{pfad[:120]}“ – erlaubt sind Pfade im Archiv wie "
                        "„dateien/bilder/….jpg“.")


def _datei_pruefen(archiv, eintraege, pfad, art):
    """Einen Archiveintrag prüfen, ohne ihn abzulegen: Name, Größe und Packverhältnis laut Inhaltsverzeichnis
    (vor dem Lesen), dann Inhalt – Dokumente nach Kennbytes wie beim Hochladen, Bilder mit Pillow – und die
    SHA-256. Liefert {"info", "name", "art", "sha256"}."""
    _pfad_pruefen(pfad)
    info = eintraege.get(pfad)
    if info is None or info.is_dir():
        raise Abgelehnt(f"„{pfad}“ fehlt im Archiv.")
    name = pfad.rsplit("/", 1)[-1]
    ext = os.path.splitext(name)[1].lower()
    if art == "bild" and ext not in ALLOWED_EXT:
        raise Abgelehnt(f"„{name}“: Dateityp {ext or '(ohne Endung)'} ist kein Foto (JPEG, PNG, WebP, HEIC, TIFF).")
    if art == "dokument" and ext not in katalog.DOK_TYPEN:
        raise Abgelehnt(f"„{name}“: Herstellerdokumente nur als PDF oder Bild (JPEG, PNG, WebP).")
    if info.flag_bits & 0x1:
        raise Abgelehnt(f"„{pfad}“ ist verschlüsselt.")
    grenze = BILD_MAX_IMPORT if art == "bild" else katalog.DOK_MAX_BYTES
    if info.file_size > grenze:
        raise Abgelehnt(f"„{name}“ ist größer als {grenze // (1024 * 1024)} MB.")
    if info.file_size > 1024 * 1024 and info.file_size > MAX_VERHAELTNIS * max(info.compress_size, 1):
        raise Abgelehnt(f"„{pfad}“ ist ungewöhnlich stark gepackt und wird nicht gelesen.")
    summe, kopf = hashlib.sha256(), b""
    try:
        with archiv.open(info) as fh:
            for stueck in iter(lambda: fh.read(1024 * 1024), b""):
                if len(kopf) < 16:
                    kopf += stueck[:16 - len(kopf)]
                summe.update(stueck)
    except _LESEFEHLER:
        raise Abgelehnt(f"„{pfad}“ ist beschädigt oder lässt sich nicht lesen.")
    if art == "dokument":
        kennungen = katalog.DOK_TYPEN[ext][1]
        if not any(kopf.startswith(k) for k in kennungen) or (ext == ".webp" and kopf[8:12] != b"WEBP"):
            raise Abgelehnt(f"Der Inhalt von „{name}“ passt nicht zur Endung {ext}.")
    else:
        try:
            with archiv.open(info) as fh, Image.open(fh) as bild:
                breite, hoehe = bild.size
        except Exception:                    # noqa: BLE001 – was Pillow nicht öffnet, ist kein Bild
            raise Abgelehnt(f"„{name}“ lässt sich nicht als Bild lesen.")
        if breite * hoehe > MAX_PIXEL:
            raise Abgelehnt(f"„{name}“ hat {breite}×{hoehe} Pixel – höchstens {MAX_PIXEL // 1_000_000} Megapixel.")
    return {"info": info, "name": name, "art": art, "sha256": summe.hexdigest()}


def _dateien_pruefen(archiv, verweise, fortschritt=None):
    """Jede Datei, auf die katalog.json verweist – und nur diese –, prüfen. Ein Fehler steht danach am Eintrag
    und erscheint im Durchgang mit der Fundstelle des Verweises."""
    eintraege = {i.filename: i for i in archiv.infolist()}
    out = {}
    for i, (pfad, art) in enumerate(sorted(verweise)):
        if fortschritt:
            fortschritt("pruefen", i, len(verweise))
        try:
            out[(pfad, art)] = _datei_pruefen(archiv, eintraege, pfad, art)
        except Abgelehnt as exc:
            out[(pfad, art)] = {"fehler": str(exc)}
    return out


class _Strom:
    """Datenstrom eines Archiveintrags. Lesefehler (Prüfsumme, kaputte Kompression) kommen als OSError – so
    räumen _datei_ablegen und store_upload ihre halb geschriebene Datei selbst weg."""

    def __init__(self, fh):
        self.fh = fh

    def read(self, n=-1):
        try:
            return self.fh.read(n)
        except _LESEFEHLER as exc:
            raise OSError(f"Archiveintrag nicht lesbar: {exc}") from exc

    def close(self):
        self.fh.close()


def _ablegen(archiv, eintrag):
    """Eine geprüfte Datei aus dem Archiv ablegen: Bilder durch dieselbe Pipeline wie beim Hochladen (foto_ablegen:
    Endung, Pillow, Web- und Vorschaufassung), Dokumente unverändert (_datei_ablegen: Endung, Kennbytes, Größe).
    Liefert den Dateinamen bzw. (Name, MIME, Größe, SHA-256)."""
    try:
        strom = _Strom(archiv.open(eintrag["info"]))
    except _LESEFEHLER:
        raise Abgelehnt(f"„{eintrag['name']}“ ließ sich nicht aus dem Archiv lesen.")
    try:
        datei = FileStorage(stream=strom, filename=eintrag["name"])
        if eintrag["art"] == "bild":
            return katalog.foto_ablegen(datei, vorschau_ganz=True)
        return katalog._datei_ablegen(datei)
    finally:
        strom.close()


def _wegraeumen(liste):
    """Abgelegte Dateien wieder entfernen: [(Art, abgelegt)]. Eine Dokumentdatei heißt nach ihrem Inhalt und kann
    schon vor diesem Import dagewesen sein (dasselbe PDF an einem anderen Produkt) – katalog._datei_freigeben lässt
    sie stehen, solange irgendein Dokument sie nennt, und entfernt nur, was ohne diese Zeilen übrig bliebe."""
    for art, wert in liste:
        if art == "bild":
            delete_photo_files(katalog.medien_dir(), wert)
        else:
            katalog._datei_freigeben(wert[0])


# --- Katalogdatei lesen ----------------------------------------------------------------------------

def _json_laden(roh):
    try:
        return json.loads(roh.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise Abgelehnt(f"Die Datei ließ sich nicht als JSON lesen: {exc}")


def _verzeichnis_pruefen(fh):
    """Zahl der Einträge und Größe des Inhaltsverzeichnisses, gelesen aus dem Ende-Satz des Archivs (bei Zip64 aus
    dem Zip64-Ende-Satz) – bevor zipfile das Verzeichnis einliest. Das legt für jeden Eintrag ein Objekt an (gut ein
    halbes KB) und liest dabei so viele, wie in die angegebene Größe passen, egal was im Zählfeld steht; ein Archiv
    aus lauter leeren Einträgen brächte einen Arbeiter sonst um seinen Speicher, bevor irgendetwas abgewiesen wäre.
    zipfile._EndRecData ist die Stelle, an der zipfile selbst den Ende-Satz liest: Die Grenzen gelten so für genau
    die Zahlen, nach denen es danach liest."""
    try:
        ende = zipfile._EndRecData(fh)
    except _LESEFEHLER:
        ende = None
    if not ende:
        raise Abgelehnt("Das ZIP-Archiv ist beschädigt oder keins.")
    eintraege, groesse = ende[zipfile._ECD_ENTRIES_TOTAL], ende[zipfile._ECD_SIZE]
    if eintraege > MAX_EINTRAEGE:
        raise Abgelehnt(f"Das Archiv hat {eintraege} Einträge – höchstens {MAX_EINTRAEGE} werden gelesen.")
    if groesse > MAX_VERZEICHNIS:
        raise Abgelehnt(f"Das Inhaltsverzeichnis des Archivs ist {groesse // 1024} KB groß – höchstens "
                        f"{MAX_VERZEICHNIS // 1024} KB werden gelesen.")
    fh.seek(0)


def _archiv_oeffnen(fh):
    """Das ZIP öffnen und seine Grenzen prüfen, bevor irgendetwas entpackt wird – Zahl der Einträge und Größe des
    Inhaltsverzeichnisses sogar, bevor es eingelesen wird. zipfile hält sich beim Lesen an die Größen im
    Inhaltsverzeichnis (mehr wird abgeschnitten), deshalb taugen sie als Obergrenze."""
    _verzeichnis_pruefen(fh)
    try:
        archiv = zipfile.ZipFile(fh)
        eintraege = archiv.infolist()
    except _LESEFEHLER:
        raise Abgelehnt("Das ZIP-Archiv ist beschädigt oder keins.")
    try:
        if len(eintraege) > MAX_EINTRAEGE:
            raise Abgelehnt(f"Das Archiv hat {len(eintraege)} Einträge – höchstens {MAX_EINTRAEGE} werden gelesen.")
        gesehen = set()
        for i in eintraege:
            if i.filename in gesehen:
                raise Abgelehnt(f"„{i.filename[:120]}“ steht doppelt im Archiv – so ein Archiv wird nicht gelesen.")
            gesehen.add(i.filename)
        entpackt = sum(i.file_size for i in eintraege)
        if entpackt > MAX_ENTPACKT:
            raise Abgelehnt(f"Das Archiv ist entpackt {entpackt // (1024 * 1024)} MB groß – höchstens "
                            f"{MAX_ENTPACKT // (1024 * 1024)} MB werden gelesen.")
    except BaseException:
        archiv.close()
        raise
    return archiv


def _katalog_json(archiv):
    info = next((i for i in archiv.infolist() if i.filename == "katalog.json"), None)
    if info is None:
        raise Abgelehnt("Im Archiv fehlt „katalog.json“ – ist das ein Katalog-Export?")
    if info.flag_bits & 0x1:
        raise Abgelehnt("„katalog.json“ ist verschlüsselt.")
    if info.file_size > JSON_MAX_BYTES:
        raise Abgelehnt(f"„katalog.json“ ist größer als {JSON_MAX_BYTES // (1024 * 1024)} MB.")
    try:
        with archiv.open(info) as fh:
            return fh.read(JSON_MAX_BYTES + 1)
    except _LESEFEHLER:
        raise Abgelehnt("„katalog.json“ ist beschädigt oder lässt sich nicht lesen.")


def datei_lesen(fh):
    """(daten, archiv) aus einer Katalogdatei – einem ZIP-Archiv (an „PK“ erkannt) mit katalog.json oder einer reinen
    JSON-Datei; archiv ist dann None. fh: seekbarer Binärstrom. Was sich nicht lesen lässt, ist Abgelehnt."""
    kopf = fh.read(4)
    fh.seek(0)
    if kopf.startswith(b"PK"):
        archiv = _archiv_oeffnen(fh)
        try:
            return _json_laden(_katalog_json(archiv)), archiv
        except BaseException:
            archiv.close()
            raise
    roh = fh.read(JSON_MAX_BYTES + 1)
    if len(roh) > JSON_MAX_BYTES:
        raise Abgelehnt(f"Die Datei ist größer als {JSON_MAX_BYTES // (1024 * 1024)} MB – als reine JSON-Datei zu groß.")
    return _json_laden(roh), None


def datei_importieren(fh, trocken=False, quelle="Datei", fortschritt=None):
    """Eine Katalogdatei (ZIP oder JSON, siehe datei_lesen) importieren. Liefert den Bericht. fortschritt: siehe oben."""
    if fortschritt:
        fortschritt("pruefen")
    daten, archiv = datei_lesen(fh)
    try:
        return importieren(daten, trocken=trocken, quelle=quelle, archiv=archiv, fortschritt=fortschritt)
    finally:
        if archiv is not None:
            archiv.close()


# --- Import ----------------------------------------------------------------------------------------

def _durchgang(daten, lauf, speichern):
    """Ein Durchgang über die ganze Datei, in einer Transaktion unter der Schreibsperre; speichern(lauf)
    entscheidet am Ende, ob er bleibt. Liefert, ob gespeichert wurde."""
    try:
        with db.transaction(sofort=True):
            # Was vor dem Durchgang galt – für _kategoriewechsel_melden, gelesen unter der Schreibsperre.
            lauf.geltend_vorher = katalog._geltend()
            lauf.pfade_vorher = _pfade()
            try:
                _kategorien(daten.get("kategorien") or [], None, "kategorien", lauf)
                _nachholen(lauf)
                _produkte(daten.get("produkte") or [], lauf)
                _nachholen(lauf)
                _bestandteillisten(lauf)
                _intervalle_pruefen(lauf)
                _formulare(daten.get("formulare") or [], lauf)
                _zuweisungen(lauf)
                _kategoriewechsel_melden(lauf)
            except Abgelehnt as exc:
                lauf.bericht["fehler"].append(str(exc))
            if not speichern(lauf):
                raise _Rueckgaengig()
        return True
    except _Rueckgaengig:
        return False


def _abschluss(lauf, bericht_basis):
    """Kennzahlen, die nicht aus dem Durchgang selbst kommen, in seinen Bericht übernehmen."""
    b = lauf.bericht
    b.update(bericht_basis)
    if b.get("kategoriewechsel"):
        b["kategoriewechsel"]["gruppen"] = [g[1] if b.get("gespeichert") else g[0] for g in lauf.gruppen]
    _kategoriewechsel_text(b, lauf.neu_angelegt)
    if b.get("gespeichert"):
        for i, satz in lauf.wechsel_gespeichert:
            b["warnungen"][i] = satz
    k, p, f = lauf.zugeordnet["category"], lauf.zugeordnet["product"], lauf.zugeordnet["formular"]
    if k or p or f:
        # Prüfformulare zählen mit: gefunden über den Titel in derselben Heimat (E3; Sicherheitsprüfung Formular-Pool,
        # Hinweis 1 – je Formular steht dazu eine Zeile mit seinen bisherigen Zuweisungen).
        teile = [f"{k} Kategorie{'n' if k != 1 else ''}" if k else "", f"{p} Produkt{'e' if p != 1 else ''}" if p else "",
                 f"{f} Prüfformular{'e' if f != 1 else ''}" if f else ""]
        teile = [t for t in teile if t]
        b["hinweise"].append(f"{', '.join(teile[:-1]) + ' und ' if len(teile) > 1 else ''}{teile[-1]} gab es hier schon "
                             "unter gleichem Namen bzw. gleicher Dublette – sie übernehmen die Katalogkennung der Datei "
                             "und werden künftig auch nach Umbenennen oder Verschieben wiedergefunden.")
    return b


def importieren(daten, trocken=False, quelle="Datei", archiv=None, fortschritt=None):
    """Den Katalog aus einem geladenen JSON-Objekt übernehmen; archiv (zipfile.ZipFile) liefert die Dateien, auf die
    es verweist. Liefert einen Bericht; bei Fehlern oder im Probelauf ist danach nichts gespeichert – auch keine
    Datei abgelegt. fortschritt: siehe oben."""
    bericht = _bericht()
    if not isinstance(daten, dict) or daten.get("format") != FORMAT:
        bericht["fehler"].append(f"Das ist keine Katalogdatei (\"format\": \"{FORMAT}\" fehlt).")
        return bericht
    version = daten.get("version")
    if type(version) is not int or version not in VERSIONEN:
        bericht["fehler"].append("Unbekannte Formatversion – erwartet wird \"version\": 1, 2 oder 3.")
        return bericht
    basis = {"version": version, "trocken": bool(trocken)}
    if version >= 2:
        # Höchstens 200 Zeichen – gekürzt am Wortende mit „…“, nicht mitten im Wort (Browserprüfung vor dem Merge, V7).
        herkunft = {k: _gekuerzt(daten[k], 200) for k in ("quelle", "erstellt") if isinstance(daten.get(k), str)}
        if herkunft:
            basis["herkunft"] = herkunft
    bericht.update(basis)
    # Ein Feld „demo“ der Datei zählt nicht: Der Import übernimmt nie ein DEMO-Kennzeichen (Entscheidung vom 04.11.2026,
    # katalog-transfer) – nicht an Kategorien, Produkten, Formularen.
    uids, dateien = ({}, {}), {}
    if version >= 2:
        uids = _uids(daten)
        for gruppe in uids:
            for uid, orte in gruppe.items():
                if len(orte) > 1:
                    bericht["fehler"].append(f"Die Katalogkennung {uid[:40]} steht mehrfach in der Datei: {', '.join(orte)}.")
        if bericht["fehler"]:
            return bericht
        if archiv is not None:
            dateien = _dateien_pruefen(archiv, _verweise(daten), fortschritt)
    g.mat_akteur = f"Katalogimport ({quelle})"
    try:
        if fortschritt:
            fortschritt("probe")
        erster = _Lauf(version, dateien, archiv, uids)
        # Braucht der Lauf keine neue Datei (Format 1, nur Links, nichts geändert), speichert gleich der erste
        # Durchgang. Sonst plant er nur.
        gespeichert = _durchgang(daten, erster, lambda lauf: not (lauf.bericht["fehler"] or trocken or lauf.bedarf))
        if gespeichert and fortschritt:
            fortschritt("gespeichert")
        if gespeichert or trocken or erster.bericht["fehler"]:
            erster.bericht["gespeichert"] = gespeichert
            return _abschluss(erster, basis)
        # Die Dateien zuerst – außerhalb der Schreibsperre –, dann die Datenbank. Fehlt eine Datei beim Schreiben der
        # Zeile wieder (inzwischen freigegeben), legt _Lauf.ablegen sie unter der Sperre aus dem Archiv nach.
        ablage = {}
        try:
            for i, (ort, eintrag) in enumerate(erster.bedarf.items()):
                if fortschritt:
                    fortschritt("ablegen", i, len(erster.bedarf))
                ablage[ort] = (eintrag["art"], _ablegen(archiv, eintrag))
                if fortschritt:
                    fortschritt("ablegen", i + 1, len(erster.bedarf), abgelegt=ablage[ort])
        except Abgelehnt as exc:
            _wegraeumen(ablage.values())
            erster.bericht["fehler"].append(f"{ort}: {exc}")
            return _abschluss(erster, basis)
        except BaseException:
            _wegraeumen(ablage.values())
            raise
        if fortschritt:
            fortschritt("schreiben")
        zweiter = _Lauf(version, dateien, archiv, uids, ablage, fortschritt)
        try:
            gespeichert = _durchgang(daten, zweiter, lambda lauf: not lauf.bericht["fehler"])
        except BaseException:
            _wegraeumen(list(ablage.values()) + zweiter.abgelegt)
            raise
        if gespeichert and fortschritt:
            fortschritt("gespeichert")
        if gespeichert:
            _wegraeumen([w for ort, w in ablage.items() if ort not in zweiter.benutzt])
            for name in zweiter.alte_bilder:
                delete_photo_files(katalog.medien_dir(), name)
        else:
            _wegraeumen(list(ablage.values()) + zweiter.abgelegt)
        zweiter.bericht["gespeichert"] = gespeichert
        return _abschluss(zweiter, basis)
    finally:
        g.pop("mat_akteur", None)
