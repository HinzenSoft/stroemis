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
  Ausnahme seit Schritt 21 (Sets mit Komponenten): Die Stückliste eines Sets („set“: true, „bestandteile“)
  wird als Ganzes ersetzt (Journal am Produkt) – in einem zweiten Durchgang nach allen Produkten der Datei, denn ein
  Bestandteil kann hinter dem Set stehen. Verweise auf Bestandteile werden aufgelöst wie Formulare an Produkten
  (_produkt_ziel: uid, dann Hersteller + Modell + Artikelnummer). „set“ an einem Produkt mit Artikeln umschalten, ein
  DEMO-Bestandteil in einem echten Set und Positionen außerhalb der Regeln (stueckliste.py) sind Fehler dieses
  Produkts; eine Liste aus Texten (Recherche-Manifeste) ist ein Hinweis und wird übergangen. Auch in Format 1 gelesen.

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
from . import Abgelehnt, akteur, heute, journal, katalog, setkopie, stueckliste, text, wahr
from .faelligkeit import in_kategorie
from .interval import herstellerseite

FORMAT = "stroemis-material-katalog"
VERSIONEN = (1, 2)

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
            "bilder": {"neu": 0, "geaendert": 0, "unveraendert": 0},
            "dokumente": {"neu": 0, "neue_version": 0, "unveraendert": 0},
            "stuecklisten": {"neu": 0, "geaendert": 0, "unveraendert": 0},
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

    def __init__(self, version, demo, dateien, archiv, uids=({}, {}), ablage=None, fortschritt=None):
        self.version, self.demo, self.dateien, self.archiv = version, demo, dateien, archiv
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
        self.zugeordnet = {"category": 0, "product": 0}
        self.zurueckgestellt = []             # (nochmal, Fehlermeldung) – Einträge mit _Konflikt, siehe _nachholen
        self.intervall_offen = {}             # geänderte Kategorie → (Fundstelle, Name), siehe _intervalle_pruefen
        self.sets = []                        # (Fundstelle, Name, Eintrag, Produkt) mit „set“/„bestandteile“, _stuecklisten
        self.unveraendert = set()             # Produkte, die als „unveraendert“ zählen – bis _stuecklisten etwas ändert
        self.bericht = _bericht()

    def notiz(self, zeile):
        liste = self.bericht["aenderungen"]
        if len(liste) < MAX_LISTE:
            liste.append(zeile)
        elif len(liste) == MAX_LISTE:
            liste.append("… und weitere Änderungen")

    def uid(self, e, feld="uid"):
        """Die Katalogkennung eines Eintrags (nur Format 2) – oder None."""
        wert = e.get(feld) if self.version == 2 else None
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
    if lauf.version != 2:
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


def _folgen_melden(lauf, ort, name, artikel, teile, seit):
    """Warnung für den Bericht, wenn eine Änderung an Intervall oder Lebensdauer Artikel hier betrifft."""
    vorgezogen, lebensende = _folgen(seit)
    if not artikel or not (teile or vorgezogen or lebensende):
        return
    satz = "; ".join(teile) or "verschoben"
    satz += f" – betrifft {artikel} Artikel hier"
    if vorgezogen:
        satz += f"; bei {vorgezogen} rückt die nächste Prüfung vor"
    if lebensende:
        satz += f"; bei {lebensende} ändert sich das Lebensende"
    lauf.bericht["warnungen"].append(f"{ort} ({name}): {satz}.")


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
                # „Jedes Produkt hat ein Prüfintervall“ erst nach den Produkten der Datei (_intervalle_pruefen).
                _ohne_konflikt(katalog.kategorie_aendern, kid, d, intervall_pruefen=False)
                lauf.intervall_offen.setdefault(kid, (ort, name))
                bericht["kategorien"]["geaendert"] += 1
                lauf.notiz(f"Kategorie „{_kategorie_pfadname(kid)}“: geändert ({_geaendert(vorher, nachher)})")
                teile = []
                if nachher["default_interval_months"] != vorher["default_interval_months"]:
                    teile.append(f"Prüfintervall (Vorgabe) {vorher['default_interval_months'] or '–'} → "
                                 f"{nachher['default_interval_months'] or '–'} Monate")
                if teile or nachher["parent_id"] != vorher["parent_id"]:
                    bedingung, args = in_kategorie(kid)
                    artikel = db.query("SELECT COUNT(*) AS n FROM mat_item i JOIN mat_product p ON p.id = i.product_id "
                                       f"WHERE i.lock_state <> 'ausgesondert' AND {bedingung}", args, one=True)["n"]
                    _folgen_melden(lauf, ort, name, artikel, teile, seit)
            else:
                bericht["kategorien"]["unveraendert"] += 1
            lauf.uid_uebernehmen("mat_category", "category", vorhanden, uid)
        else:
            kid = _ohne_konflikt(katalog.kategorie_anlegen, d, demo=lauf.demo)
            lauf.uid_setzen("mat_category", kid, uid)
            bericht["kategorien"]["neu"] += 1
            lauf.notiz(f"Kategorie „{_kategorie_pfadname(kid)}“: neu")
        if lauf.version == 2:
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
                _ohne_konflikt(katalog.produkt_aendern, pid, d, importiert=True)
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
            pid = _ohne_konflikt(katalog.produkt_anlegen, d, demo=lauf.demo, importiert=True)
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
    if lauf.version == 2:
        _bild(e, pid, bild, ort, name, lauf)
        try:
            _dokumente(e.get("dokumente"), "product_id", pid, ort, name, lauf)
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort} ({name}): {exc}")
    if "set" in e or "bestandteile" in e:
        lauf.sets.append((ort, name, e, pid))
    return True


# --- Stücklisten der Sets (Schritt 21) -----------------------------------------------------------------------

def _set_angaben(ort, name, e, lauf):
    """(„set“ als ja/nein oder None, Stückliste als Liste von Objekten oder None) aus einem Produkteintrag – eine Liste
    aus Texten (heutige Recherche-Manifeste) ist ein Hinweis und zählt wie „fehlt“."""
    an = wahr(e, "set", "set") if e.get("set") is not None else None
    liste = e.get("bestandteile")
    if liste is None:
        return an, None
    if not isinstance(liste, list):
        raise Abgelehnt("„bestandteile“ muss eine Liste sein.")
    if liste and all(isinstance(x, str) for x in liste):
        lauf.bericht["hinweise"].append(f"{ort} ({name}): „bestandteile“ ist eine Liste aus Texten – übergangen. Eine "
                                        "Stückliste braucht je Position ein Objekt (Katalogdatei, Sets).")
        return an, None
    if any(not isinstance(x, dict) for x in liste):
        raise Abgelehnt("„bestandteile“: jede Position ist ein Objekt (produkt, bezeichnung, anzahl, einzeln, austausch).")
    return an, liste


def _stuecklisten(lauf):
    """Zweiter Durchgang nach allen Produkten der Datei: „set“ umschalten und Stücklisten ersetzen – in vier Schritten,
    damit ein Produkt, das in derselben Datei aus einer Stückliste fällt und selbst ein Set wird, nicht am eigenen
    Vorher scheitert: 1. Sets ausschalten, 2. Stücklisten bleibender Sets, 3. Sets einschalten, 4. ihre Stücklisten."""
    bericht = lauf.bericht
    angaben = []

    def geaendert(pid):
        """Ändern sich am Produkt nur „Set“ oder die Stückliste, zählt es nicht mehr als „unveraendert“."""
        if pid in lauf.unveraendert:
            lauf.unveraendert.discard(pid)
            bericht["produkte"]["unveraendert"] -= 1
            bericht["produkte"]["geaendert"] += 1

    for ort, name, e, pid in lauf.sets:
        try:
            an, liste = _set_angaben(ort, name, e, lauf)
            if an is False and liste:
                raise Abgelehnt("„set“: false und dazu eine Stückliste – nur ein Set hat Bestandteile.")
            angaben.append((ort, name, pid, an, liste))
        except Abgelehnt as exc:
            bericht["fehler"].append(f"{ort} ({name}): {exc}")

    def umschalten(ort, name, pid, an):
        p = katalog.produkt(pid)
        if bool(p["is_set"]) == an:
            return
        n = db.query("SELECT COUNT(*) AS n FROM mat_item WHERE product_id = ?", (pid,), one=True)["n"]
        if n:
            raise Abgelehnt(f"„set“ wechselte für „{_produkt_text(p)}“ auf {'true' if an else 'false'} – hier gibt es aber "
                            f"schon {n} Artikel dieses Produkts. Ob ein Artikel Teile hat, hängt daran; erst klären: in der "
                            "Quelle zurückändern oder dort ein eigenes Produkt (Variante) für das Set anlegen.")
        stueckliste.set_umschalten(pid, an, grund_journal="Katalogimport")
        geaendert(pid)
        lauf.notiz(f"Produkt „{name}“: „Set“ {'gesetzt' if an else 'entfernt'}")

    def ersetzen(ort, name, pid, liste):
        if not katalog.produkt(pid)["is_set"]:
            raise Abgelehnt("Bestandteile hat nur ein Set – „set“: true fehlt.")
        def aufloesen(x):
            return _produkt_ziel(x["produkt"], lauf) if x.get("produkt") is not None else None
        neu = not stueckliste.zeilen(pid)
        if stueckliste.ersetzen(pid, liste, aufloesen=aufloesen, grund="Katalogimport"):
            bericht["stuecklisten"]["neu" if neu else "geaendert"] += 1
            geaendert(pid)
            lauf.notiz(f"Produkt „{name}“: Stückliste ersetzt ({len(liste)} Position{'en' if len(liste) != 1 else ''})")
            # Der Import überträgt nie selbst (Wunsch vom 24.10.2026): angelegte Sets behalten ihre Kopie.
            k = setkopie.aelter(pid)
            if k:
                bericht["hinweise"].append(f"{ort} ({name}): {k} angelegte{'s' if k == 1 else ''} Set{'' if k == 1 else 's'} "
                                           f"{'hat' if k == 1 else 'haben'} die bisherige Stückliste – übertragen auf der "
                                           "Produktseite („Auf vorhandene Sets übertragen …“).")
        else:
            bericht["stuecklisten"]["unveraendert"] += 1

    fehlerhaft, ersetzt = set(), set()
    for schritt in ("aus", "bleibend", "ein", "neu"):
        for ort, name, pid, an, liste in angaben:
            if ort in fehlerhaft:
                continue
            try:
                if schritt == "aus" and an is False:
                    umschalten(ort, name, pid, False)
                elif schritt == "bleibend" and liste is not None and an is not False and katalog.produkt(pid)["is_set"]:
                    ersetzen(ort, name, pid, liste)
                    ersetzt.add(ort)
                elif schritt == "ein" and an is True:
                    umschalten(ort, name, pid, True)
                elif schritt == "neu" and liste is not None and ort not in ersetzt:
                    ersetzen(ort, name, pid, liste)
            except Abgelehnt as exc:
                fehlerhaft.add(ort)
                bericht["fehler"].append(f"{ort} ({name}): {exc}")
    # Entscheidung S3: Ein Set ohne einzeln geführtes Teil ist ein Fehler dieses Produkts – auch „set“: true ohne
    # „bestandteile“ an einem Produkt, das noch keine Stückliste hat (ersetzen prüft nur eine mitgeschickte Liste).
    for ort, name, pid, _, _ in angaben:
        if ort not in fehlerhaft and katalog.produkt(pid)["is_set"] and \
                not any(z["einzeln"] for z in stueckliste.zeilen(pid)):
            bericht["fehler"].append(f"{ort} ({name}): {stueckliste.EINZELN_PFLICHT} – „bestandteile“ mit mindestens einer "
                                     "einzeln geführten Position fehlt.")


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


# --- Formulare -------------------------------------------------------------------------------------

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


_PUNKTFELDER = ("group_name", "label", "editor", "mandatory", "expected_value", "is_critical")


def _formulare(liste, lauf):
    if not isinstance(liste, list):
        raise Abgelehnt("„formulare“ muss eine Liste sein.")
    bericht = lauf.bericht
    for n, e in enumerate(liste):
        ort = f"formulare[{n}]"
        try:
            if not isinstance(e, dict):
                raise Abgelehnt("Eintrag ist kein Objekt.")
            if ("kategorie" in e) == ("produkt" in e):
                raise Abgelehnt("Ein Formular gehört entweder zu einer „kategorie“ oder zu einem „produkt“.")
            if "kategorie" in e:
                kid = _kategorie_ziel(e, lauf)
                ziel = {"kategorie_id": kid}
                spalte, wert = "category_id", kid
                zielname = f"Kategorie „{_kategorie_pfadname(kid)}“"
            else:
                p = _produkt_ziel(e["produkt"], lauf)
                ziel = {"produkt_id": p["id"]}
                spalte, wert = "product_id", p["id"]
                zielname = f"Produkt „{katalog.produktname(p)}“"
            punkte = katalog.punkte_pruefen(e.get("punkte"))
            if not punkte:
                raise Abgelehnt("Ein Formular braucht mindestens einen Prüfpunkt.")
            titel = _name(e.get("titel"), "Titel", 160) if isinstance(e.get("titel"), str) else ""
            aktivieren = e.get("aktivieren", True) is not False
            neu = [{k: p[k] for k in _PUNKTFELDER} for p in punkte]

            # Ein leerer Titel in der Datei gibt keinen vor (das erste Formular legt die Oberfläche ohne Titel an):
            # Verglichen werden dann nur die Prüfpunkte. Eine neue Version erbt ohnehin den Titel der letzten hier.
            def gleich(f):
                return ((not titel or f["title"] == titel)
                        and [{k: p[k] for k in _PUNKTFELDER} for p in katalog.punkte(f["id"])] == neu)

            # Verglichen wird mit dem aktiven Formular des Ziels (soll es aktiv werden), dann mit der neuesten
            # Version – ein Entwurf hier führt so nicht zu einer neuen Version mit dem Inhalt der aktiven.
            aktive = db.query(f"SELECT * FROM mat_form WHERE {spalte} = ? AND active = 1", (wert,), one=True)
            letzte = db.query(f"SELECT * FROM mat_form WHERE {spalte} = ? ORDER BY version DESC LIMIT 1", (wert,), one=True)
            if aktivieren and aktive and gleich(aktive):
                fid = aktive["id"]
            elif letzte and gleich(letzte):
                fid = letzte["id"]
            else:
                fid = None
            angelegt = not fid
            if angelegt:
                fid = katalog.formular_anlegen(dict(ziel, titel=titel, punkte=e.get("punkte")), demo=lauf.demo)
                bericht["formulare"]["neu"] += 1
            else:
                bericht["formulare"]["unveraendert"] += 1
            aktiviert = aktivieren and not katalog.formular(fid)["active"]
            if aktiviert:
                katalog.formular_aktivieren(fid)
            if angelegt or aktiviert:
                version = katalog.formular(fid)["version"]
                lauf.notiz(f"Formular „{titel or katalog.formular(fid)['title']}“ ({zielname}): "
                           + (f"neue Version {version}{', aktiv' if aktiviert else ''}" if angelegt
                              else f"Version {version} aktiviert"))
        except Abgelehnt as exc:
            titel_roh = e.get("titel") if isinstance(e, dict) and isinstance(e.get("titel"), str) else ""
            bericht["fehler"].append(f"{ort}{f' ({titel_roh})' if titel_roh else ''}: {exc}")


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
            try:
                _kategorien(daten.get("kategorien") or [], None, "kategorien", lauf)
                _nachholen(lauf)
                _produkte(daten.get("produkte") or [], lauf)
                _nachholen(lauf)
                _stuecklisten(lauf)
                _intervalle_pruefen(lauf)
                _formulare(daten.get("formulare") or [], lauf)
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
    k, p = lauf.zugeordnet["category"], lauf.zugeordnet["product"]
    if k or p:
        teile = [f"{k} Kategorie{'n' if k != 1 else ''}" if k else "", f"{p} Produkt{'e' if p != 1 else ''}" if p else ""]
        b["hinweise"].append(f"{' und '.join(t for t in teile if t)} gab es hier schon unter gleichem Namen bzw. gleicher "
                             "Dublette – sie übernehmen die Katalogkennung der Datei und werden künftig auch nach "
                             "Umbenennen oder Verschieben wiedergefunden.")
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
        bericht["fehler"].append("Unbekannte Formatversion – erwartet wird \"version\": 1 oder 2.")
        return bericht
    basis = {"version": version, "trocken": bool(trocken)}
    if version == 2:
        herkunft = {k: daten[k][:200] for k in ("quelle", "erstellt") if isinstance(daten.get(k), str)}
        if herkunft:
            basis["herkunft"] = herkunft
    bericht.update(basis)
    demo = daten.get("demo") is True
    uids, dateien = ({}, {}), {}
    if version == 2:
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
        erster = _Lauf(version, demo, dateien, archiv, uids)
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
        zweiter = _Lauf(version, demo, dateien, archiv, uids, ablage, fortschritt)
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
