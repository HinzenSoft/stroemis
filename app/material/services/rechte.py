"""Rechte im Modul Material – seit Phase 2 Freigaben je Ordner.

Woher die Rechte kommen (Bauentwurf Phase 2 · Lieferung 1, Abschnitt 1):

  Plattform-Verwaltung    Verwaltung im Modul Verwaltung (auth.is_admin): sieht und verwaltet den ganzen Bestand,
                          pflegt den Katalog, legt Gliederungen an, vergibt jede Freigabe. Prüfen nur wie alle anderen –
                          mit Qualifikation UND Prüffreigabe; Sachkunde lässt sich nicht verwalten, nur nachweisen.
  Freigabe                eine Zeile in mat_folder_grant: lesen, pruefen oder verwalten an einem Ordner – sie gilt dort
                          und in allen Unterordnern, solange sie gültig ist (valid_until leer oder heute und später,
                          deutscher Kalendertag; der letzte Tag zählt mit). Rechte addieren sich nur. Eine Prüffreigabe
                          ohne Ende (dauerhaft) wirkt nur, wo das Konto zugleich ein Grundrecht hat – befristet ist nur
                          noch der externe Prüfer (Nachbesserung vom 18.10.2026, Schritt 9).
  Qualifikation Prüfer    Häkchen mat_pruefer (setzt die Verwaltung) und gültige Urkundennummer (trägt der Prüfer selbst
                          im Profil ein, urkunde_setzen). Voraussetzung jeder Prüfhandlung und dafür, dass eine
                          Prüffreigabe überhaupt wirkt. Allein gibt sie Modulzugang (Katalog, Profil), keinen Bestand.
  Produktkatalogpfleger   Häkchen mat_katalog: Katalog pflegen, Meldungen abarbeiten, Rückrufe – plattformweit, ohne
                          Bestand.
  Name                    Ohne Namen gibt es keinen Modulzugang: Wer handelt, steht namentlich im Journal.

Die Material-Stufe aus Phase 1 (users.recht_material) liest der Code nicht mehr – sie bleibt als Rückweg stehen;
Schritt 8 der Migration hat aus ihr Freigaben gemacht. Die Stufe, die Kopfleiste und Profil zeigen, rechnet
material_stufe_wirksam aus den Freigaben.

Rechte in einem Ordner F (RECHTE): grund – Grundrecht, Verwaltung oder gültiges lesen/verwalten an F oder darüber;
pruefen – qualifiziert und gültiges pruefen an F oder darüber (auch für Verwalter und die Verwaltung), ein dauerhaftes
nur, wo zugleich grund gilt; lesen – grund oder pruefen (mit pruefen allein: die Prüfsicht – also nur mit einer
befristeten Prüffreigabe, der des externen Prüfers); verwalten – Verwaltung oder gültiges verwalten. Läuft das
Grundrecht ab oder wird es entzogen, wirkt eine dauerhafte Prüffreigabe dort nicht mehr: So entsteht nie ein
unbefristetes Prüfrecht ohne Grundrecht. Ein Artikel zählt über seine Heimat (bestand.heimat). sicht() rechnet das
einmal je Anfrage und Konto; Listen filtern in SQL mit artikel_filter und ordner_filter, nie mit darf() je Zeile.

Fremdes – nicht vorhanden oder nicht sichtbar – beantwortet requires_folder mit 404 und derselben Meldung wie „gibt es
nicht“. 403 gibt es nur, wenn man den Gegenstand sehen, die Aktion aber nicht ausführen darf.
"""
import json
import re
import unicodedata
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import wraps

from flask import g, has_app_context, has_request_context, jsonify, request

from ... import db
from ...auth import current_user, is_admin, json_body
from .. import services as dienste
from . import Abgelehnt, eingabe, journal, kennung, text, wahr

# Rechte, nach denen darf() fragt. Die Arten einer Freigabe (lesen, pruefen, verwalten) stehen in models.FREIGABEN.
RECHTE = ("lesen", "grund", "pruefen", "verwalten")
FREIGABE_AKTIONEN = ("freigabe_erteilt", "freigabe_geaendert", "freigabe_entzogen", "freigabe_entfernt")
GRUNDRECHTE = ("lesen", "verwalten")
# Welche Arten einer Freigabe ein Recht tragen (pruefen nur bei Qualifikation, siehe Sicht.ende).
_ARTEN = {"lesen": ("lesen", "verwalten", "pruefen"), "grund": GRUNDRECHTE, "pruefen": ("pruefen",),
          "verwalten": ("verwalten",)}
# Woher requires_folder den Bezug einer Anfrage nimmt: aus dem Pfad (Ordner, Artikel, Prüfung, Durchgang) oder einem Feld
# der Anfrage – JSON, Formular, Adresse oder wie routes._eingabe (Formular bei Dateien, sonst JSON).
QUELLEN = ("fid", "iid", "pid", "rid")
QUELLEN_FELD = ("json", "form", "arg", "eingabe")
# Was eine leere Quelle heißt: global – nur die Verwaltung; irgendwo – das Recht irgendwo; zugang – Modulzugang genügt.
LEER = ("global", "irgendwo", "zugang")

ORDNER_FEHLT = "Ordner nicht gefunden."
ARTIKEL_FEHLT = "Artikel nicht gefunden."
PRUEFUNG_FEHLT = "Prüfung nicht gefunden."
DURCHGANG_FEHLT = "Prüfdurchgang nicht gefunden."
KONTO_FEHLT = "Konto nicht gefunden."

NAME_FEHLT = "Für das Modul Material braucht dein Konto einen Namen – trag ihn im Profil ein."
NICHT_FREIGESCHALTET = ("Für dein Konto ist das Modul Material nicht freigeschaltet – der Materialwart deiner Gliederung "
                        "vergibt Freigaben.")
KEINE_PRUEFFREIGABE = ("Häkchen und Urkundennummer hast du, aber für diesen Ordner keine Prüffreigabe – die vergibt der "
                       "Materialwart des Ordners unter Ordner → Bearbeiten → Freigaben.")
NUR_GRUNDRECHT = ("Dafür braucht es eine Lese- oder Verwalterfreigabe für diesen Ordner – die Prüffreigabe allein "
                  "reicht nicht.")
NUR_VERWALTUNG_GLOBAL = "Ohne Ordner nur für die Plattform-Verwaltung."

URKUNDE_UNGUELTIG = "Eine Urkundennummer braucht Buchstaben oder Ziffern."
URKUNDE_NUR_PRUEFER = ("Die Urkundennummer trägt nur ein, wer das Häkchen „Prüfer“ hat – das setzt die Verwaltung in der "
                       "Nutzerverwaltung.")
# Für ein Konto mit Häkchen, aber ohne Urkundennummer: wo es weitergeht.
URKUNDE_IM_PROFIL = ("Deine Urkundennummer fehlt noch – trage sie im Profil ein (Profil → Urkundennummer und "
                     "Unterschrift), dann kannst du prüfen.")

Freigabe = namedtuple("Freigabe", "id folder_id permission valid_until")
# Worauf sich eine Anfrage bezieht (requires_folder): art „ordner“, „artikel“ oder „durchgang“, der Ordner (bei Artikeln
# die Heimat; None bei leerer Quelle), die Artikelzeile und die Meldung für „gibt es nicht“.
Bezug = namedtuple("Bezug", "art ordner_id artikel meldung")


# --- Urkundennummer und Qualifikation --------------------------------------------------------------------------

def urkunde_gueltig(nummer):
    """Eine Urkundennummer muss Buchstaben oder Ziffern enthalten – Leerzeichen, Bindestriche oder
    unsichtbare Zeichen allein sind keine."""
    return bool(re.search(r"[^\W_]", nummer or ""))


def urkunde_saeubern(nummer):
    """Unsichtbare Zeichen (Formatzeichen wie U+200B, U+FEFF, weiches Trennzeichen) entfernen."""
    return "".join(c for c in (nummer or "") if unicodedata.category(c) not in ("Cf", "Cc")).strip()


def urkunde_lesen(d, feld="urkundennummer"):
    """Urkundennummer aus einer Anfrage – gesäubert. Leer heißt „keine“; wer etwas eingibt, das ohne unsichtbare
    Zeichen weder Buchstaben noch Ziffern hat, bekommt eine Meldung statt einer stillschweigend leeren Nummer."""
    roh = text(d, feld, "Urkundennummer", n=40)
    nummer = urkunde_saeubern(roh)
    if roh and not urkunde_gueltig(nummer):
        raise Abgelehnt(URKUNDE_UNGUELTIG)
    return nummer


def ist_pruefer(user=None):
    """Sachkundiger mit Urkundennummer – nur das zählt, kein Schulungskatalog, kein Ablaufdatum. Das Häkchen allein
    (gesetzt von der Verwaltung) genügt nicht: Die Urkundennummer trägt der Prüfer selbst im Profil ein. Prüfen darf er
    damit noch nirgends – dafür braucht es zusätzlich eine Prüffreigabe am Ordner."""
    user = user or current_user()
    return bool(user and user["mat_pruefer"] and urkunde_gueltig(urkunde_saeubern(user["urkundennummer"])))


def urkunde_fehlt(user=None):
    """Häkchen „Prüfer“ gesetzt, aber (noch) keine gültige Urkundennummer – die Oberfläche zeigt dann den Weg ins Profil."""
    user = user or current_user()
    return bool(user and user["mat_pruefer"] and not ist_pruefer(user))


def ist_katalogpfleger(user=None):
    user = user or current_user()
    return bool(user and (is_admin(user) or user["mat_katalog"]))


# --- Gültigkeit und Sicht --------------------------------------------------------------------------------------

def _stichtag(tag=None):
    """Stichtag als 'JJJJ-MM-TT' – ohne Angabe heute in deutscher Zeit. services.heute über das Modul gerufen, damit ein
    Test den Tag ersetzen kann."""
    t = tag or dienste.heute()
    return t.isoformat() if hasattr(t, "isoformat") else str(t)


def gueltig(valid_until, tag=None):
    """Gilt eine Freigabe mit diesem Enddatum am Stichtag? Ohne Enddatum immer; sonst bis einschließlich zum letzten
    Tag – ab 0:00 Uhr deutscher Zeit des Folgetags nicht mehr. Abgelaufene Zeilen bleiben stehen (Liste, Verlängern)."""
    return valid_until is None or valid_until >= _stichtag(tag)


def _speicher(name):
    """Zwischenspeicher je Anfrage (g) – ohne Anwendungskontext keiner."""
    return g.setdefault(name, {}) if has_app_context() else None


@dataclass(frozen=True)
class Sicht:
    """Was ein Konto im Bestand darf, ausgerechnet für alle Ordner (Unterbäume inklusive, Systemordner sichtbarer
    Gliederungen gehören dazu). Bei der Verwaltung (alles) bleiben grund, lesbar und verwaltbar leer – sie darf überall;
    gefragt wird deshalb über darf(), menge() und die Filter, nicht über die Mengen selbst. pruefbar ist ohne
    Qualifikation immer leer, auch bei der Verwaltung nur, was ihre eigenen Prüffreigaben decken."""
    uid: object
    alles: bool
    qualifiziert: bool
    grund: frozenset = frozenset()
    pruefbar: frozenset = frozenset()
    lesbar: frozenset = frozenset()
    verwaltbar: frozenset = frozenset()
    # Systemordner („Gesperrt“, „Ausgesondert“) einer Gliederung, die selbst nicht sichtbar ist, zu der aber ein sichtbarer
    # Ordner gehört: Darin zählt nur, was im eigenen Bereich zu Hause ist.
    teil_system: frozenset = frozenset()
    # Oberordner sichtbarer Knoten ohne eigenes Recht: nur Name und Lage im Baum, kein Inhalt.
    pfad_knoten: frozenset = frozenset()
    # Die gültigen eigenen Freigaben (auch Prüffreigaben, die mangels Qualifikation nicht wirken).
    freigaben: tuple = ()
    # Oberordner je Ordner, soweit der Baum geladen wurde (für ende()).
    eltern: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    def menge(self, recht):
        """Die Ordner mit diesem Recht (bei der Verwaltung leer, außer pruefen – siehe oben)."""
        if recht not in RECHTE:
            raise ValueError(f"Unbekanntes Recht {recht}")
        return {"lesen": self.lesbar, "grund": self.grund, "pruefen": self.pruefbar,
                "verwalten": self.verwaltbar}[recht]

    def darf(self, recht, fid):
        """Recht im Ordner fid (und damit darunter). fid None heißt global: lesen, grund und verwalten nur die
        Verwaltung, prüfen niemand – eine Prüffreigabe hängt immer an einem Ordner."""
        menge = self.menge(recht)
        if self.alles and recht != "pruefen":
            return True
        return fid is not None and fid in menge

    def irgendwo(self, recht):
        menge = self.menge(recht)
        if self.alles and recht != "pruefen":
            return True
        return bool(menge)

    def sichtbar(self, fid):
        """Ordner, den man öffnen darf: lesen oder ein teilweise sichtbarer Systemordner."""
        return self.darf("lesen", fid) or fid in self.teil_system

    def kette(self, fid):
        """fid und seine Oberordner (nach dem geladenen Baum), von unten nach oben."""
        out, x = [], fid
        while x is not None and x not in out:
            out.append(x)
            x = self.eltern.get(x)
        return out

    def ende(self, recht, fid):
        """Wirksames Ende des Rechts in fid: None, wenn eine deckende gültige Freigabe unbefristet ist (oder die
        Verwaltung es ohnehin hat), sonst das späteste Enddatum der deckenden. Eine dauerhafte Prüffreigabe endet mit
        dem Grundrecht, ohne das sie nicht wirkt. Ohne das Recht: Abgelehnt."""
        if not self.darf(recht, fid):
            raise Abgelehnt("Dieses Recht hast du in diesem Ordner nicht.", 403)
        if self.alles and recht != "pruefen":
            return None
        arten = tuple(a for a in _ARTEN[recht] if a != "pruefen" or self.qualifiziert)
        kette = set(self.kette(fid))
        enden = []
        for f in self.freigaben:
            if f.folder_id not in kette or f.permission not in arten:
                continue
            if f.permission == "pruefen" and f.valid_until is None and not self.alles:
                if self.darf("grund", fid):
                    enden.append(self.ende("grund", fid))
            else:
                enden.append(f.valid_until)
        return None if any(e is None for e in enden) else max(enden)


_KEINE = Sicht(uid=None, alles=False, qualifiziert=False)


def sicht(user=None):
    """Die Sicht des Kontos – einmal je Anfrage und Konto gerechnet (g.mat_sicht[uid]). Nach dem Schreiben von Freigaben
    oder Rechten sicht_verwerfen() rufen, sonst antwortet dieselbe Anfrage noch mit dem alten Stand. Ohne Konto (auch
    ohne Anfrage, etwa auf der Kommandozeile) ist die Sicht leer."""
    user = user or (current_user() if has_request_context() else None)
    if not user:
        return _KEINE
    speicher = _speicher("mat_sicht")
    if speicher is not None and user["id"] in speicher:
        return speicher[user["id"]]
    s = _sicht_rechnen(user)
    if speicher is not None:
        speicher[user["id"]] = s
    return s


def sicht_verwerfen():
    """Zwischengespeicherte Sichten und Stufen dieser Anfrage vergessen."""
    if has_app_context():
        g.pop("mat_sicht", None)
        g.pop("mat_stufe", None)


def _sicht_rechnen(user):
    """Eine Abfrage für die eigenen gültigen Freigaben; nur wenn eine wirkt, eine zweite für den Ordnerbaum. Die
    Unterbäume entstehen in Python – mit einer Menge der schon gesehenen Ordner, so hält auch ein Zyklus an."""
    alles = is_admin(user)
    qualifiziert = ist_pruefer(user)
    freigaben = tuple(Freigabe(r["id"], r["folder_id"], r["permission"], r["valid_until"]) for r in db.query(
        "SELECT id, folder_id, permission, valid_until FROM mat_folder_grant WHERE user_id = ? "
        "AND (valid_until IS NULL OR valid_until >= ?) ORDER BY id", (user["id"], _stichtag())))
    anker = {a: {f.folder_id for f in freigaben if f.permission == a} for a in ("lesen", "pruefen", "verwalten")}
    # Eine dauerhafte Prüffreigabe wirkt nur, wo zugleich ein Grundrecht gilt (die Verwaltung hat es überall): Sie
    # öffnet selbst nichts, zählt also nicht als Anker und wird unten mit dem Grundrecht geschnitten.
    dauerhaft = {f.folder_id for f in freigaben if f.permission == "pruefen" and f.valid_until is None}
    if not alles:
        anker["pruefen"] -= dauerhaft               # je Konto und Ordner gibt es nur eine Prüffreigabe
    if not qualifiziert:
        anker["pruefen"], dauerhaft = set(), set()  # eine Prüffreigabe ohne Qualifikation wirkt gar nicht
    if alles:
        anker["lesen"], anker["verwalten"] = set(), set()
    alle_anker = anker["lesen"] | anker["verwalten"] | anker["pruefen"]
    if not alle_anker:
        return Sicht(uid=user["id"], alles=alles, qualifiziert=qualifiziert, freigaben=freigaben)

    ordner = {o["id"]: o for o in db.query("SELECT id, parent_id, kind, system_kind FROM mat_folder")}
    eltern = {fid: o["parent_id"] for fid, o in ordner.items()}
    kinder = {}
    for fid, o in ordner.items():
        if o["parent_id"] is not None:
            kinder.setdefault(o["parent_id"], []).append(fid)

    def unter(wurzeln):
        gesehen, offen = set(), [w for w in wurzeln if w in ordner]
        while offen:
            x = offen.pop()
            if x not in gesehen:
                gesehen.add(x)
                offen.extend(kinder.get(x, ()))
        return frozenset(gesehen)

    pruefbar = unter(anker["pruefen"])
    if alles:
        return Sicht(uid=user["id"], alles=True, qualifiziert=qualifiziert, pruefbar=pruefbar, freigaben=freigaben,
                     eltern=eltern)
    grund = unter(anker["lesen"] | anker["verwalten"])
    pruefbar |= unter(dauerhaft) & grund
    lesbar = grund | pruefbar
    teil, pfad = set(), set()
    # Was über einem Anker liegt, ist sichtbar oder Pfad. Liegt die nächste Gliederung eines Ankers selbst nicht im
    # sichtbaren Bereich, sind ihre Systemordner teilweise sichtbar – andere Lagen gibt es nicht: Alles unter dem Anker
    # (auch verschachtelte Gliederungen) ist ohnehin sichtbar.
    for a in alle_anker:
        if a not in ordner:
            continue
        gliederung, x, gesehen = None, a, set()
        while x is not None and x not in gesehen:
            gesehen.add(x)
            o = ordner.get(x)
            if not o:
                break
            if gliederung is None and o["kind"] == "gliederung" and not o["system_kind"]:
                gliederung = x
            if x != a and x not in lesbar:
                pfad.add(x)
            x = o["parent_id"]
        if gliederung is not None and gliederung not in lesbar:
            teil.update(k for k in kinder.get(gliederung, ()) if ordner[k]["system_kind"])
    teil = frozenset(teil) - lesbar
    return Sicht(uid=user["id"], alles=False, qualifiziert=qualifiziert, grund=grund, pruefbar=pruefbar,
                 lesbar=lesbar, verwaltbar=unter(anker["verwalten"]), teil_system=teil,
                 pfad_knoten=frozenset(pfad) - lesbar - teil, freigaben=freigaben, eltern=eltern)


# --- Fragen an die Sicht -----------------------------------------------------------------------------------------

def darf(recht, ordner_id, user=None):
    """Darf das Konto das im Ordner (und darunter)? ordner_id None heißt global (siehe Sicht.darf)."""
    return sicht(user).darf(recht, ordner_id)


def darf_artikel(recht, item, user=None):
    """Recht an einem Artikel – über seine Heimat (bestand.heimat)."""
    from .bestand import heimat
    return darf(recht, heimat(item), user)


def darf_meldung(meldung, user=None):
    """Eine Produktmeldung sehen: Katalogpfleger und die Verwaltung, der Melder selbst und wer den Ordner der Meldung
    sehen darf."""
    user = user or current_user()
    if not user or not meldung:
        return False
    if ist_katalogpfleger(user) or meldung.get("created_by") == user["id"]:
        return True
    return meldung.get("folder_id") is not None and darf("lesen", meldung["folder_id"], user)


def rechte_ordner(fid, user=None):
    """Das Feld „darf“ an Ordnern, Artikeln, Prüfungen und Durchgängen: was das Konto genau dort darf."""
    s = sicht(user)
    return {r: s.darf(r, fid) for r in ("lesen", "grund", "pruefen", "verwalten")}


def rechte_artikel(item, user=None):
    from .bestand import heimat
    return rechte_ordner(heimat(item), user)


def _bezeichner(name, punkt=False):
    """Spaltenname oder Kürzel für die Filter – nur Buchstaben, Ziffern, Unterstrich (und Punkt bei Spalten)."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?" if punkt else r"[A-Za-z_][A-Za-z0-9_]*",
                        name or ""):
        raise ValueError(f"Unbrauchbarer Bezeichner {name!r}")
    return name


def _liste(ids):
    # Kennungen aus der eigenen Datenbank (ganze Zahlen) als JSON-Literal: passt in Abfragen mit ?- und :name-Parametern.
    return f"(SELECT value FROM json_each('{json.dumps(sorted(int(x) for x in ids))}'))"


def artikel_filter(alias="i", recht="lesen", user=None):
    """SQL-Bedingung über mat_item (Kürzel alias): Artikel, deren Heimat im Bereich mit diesem Recht liegt. Die Form nutzt
    die Indizes auf folder_id und origin_folder_id; „1“ für die Verwaltung, „0“ ohne Bereich."""
    a = _bezeichner(alias)
    s = sicht(user)
    if s.alles and recht != "pruefen":
        return "1"
    menge = s.menge(recht)
    if not menge:
        return "0"
    ids = _liste(menge)
    return (f"((({a}.lock_state = 'frei' OR {a}.origin_folder_id IS NULL) AND {a}.folder_id IN {ids}) "
            f"OR ({a}.lock_state <> 'frei' AND {a}.origin_folder_id IN {ids}))")


def ordner_filter(spalte, recht="lesen", user=None):
    """SQL-Bedingung: die Ordnerspalte (z. B. „r.folder_id“) liegt im Bereich mit diesem Recht; „1“ bzw. „0“ wie oben."""
    sp = _bezeichner(spalte, punkt=True)
    s = sicht(user)
    if s.alles and recht != "pruefen":
        return "1"
    menge = s.menge(recht)
    return f"{sp} IN {_liste(menge)}" if menge else "0"


def verwalter_von(fid, ohne_freigabe=None):
    """Aktive Konten (ohne die Verwaltung) mit gültigem verwalten an fid oder darüber – nach Namen sortiert, je Konto
    mit dem wirksamen Ende („ende“, None = unbefristet). Für Meldungstexte, Empfänger von Mails und die Regel
    „keine Gliederung ohne Verwalter“. ohne_freigabe: so rechnen, als gäbe es diese Freigabezeile nicht (ob ein
    Entzug die Regel verletzen würde – vorab, ohne zu schreiben)."""
    rows = db.query(
        "WITH RECURSIVE kette(id) AS (SELECT ? UNION SELECT f.parent_id FROM mat_folder f JOIN kette k ON f.id = k.id "
        "WHERE f.parent_id IS NOT NULL) "
        "SELECT u.id, u.name, u.email, MAX(COALESCE(x.valid_until, '9999-12-31')) AS ende FROM mat_folder_grant x "
        "JOIN users u ON u.id = x.user_id WHERE x.folder_id IN (SELECT id FROM kette) AND x.permission = 'verwalten' "
        "AND (x.valid_until IS NULL OR x.valid_until >= ?) AND u.active = 1 AND u.status = 'active' "
        "AND u.recht_verwaltung < 2 AND x.id IS NOT ? GROUP BY u.id ORDER BY u.name COLLATE NOCASE, u.id",
        (fid, _stichtag(), ohne_freigabe))
    return [dict(r, ende=None if r["ende"] == "9999-12-31" else r["ende"]) for r in rows]


def grundrecht_an(user, fid):
    """Hat das Konto an fid oder darüber heute ein Grundrecht (lesen oder verwalten) – oder ist es die
    Plattform-Verwaltung? Frisch aus der Datenbank, auch mitten in einer Transaktion: Eine Prüffreigabe ohne Ende ist
    nur so erlaubt (freigaben._schreiben), und ein Grundrecht aus derselben Anfrage zählt schon mit. Ohne Sicht, ohne
    Blick auf Name oder Aktivität."""
    if is_admin(user):
        return True
    return bool(db.query(
        "WITH RECURSIVE kette(id) AS (SELECT ? UNION SELECT f.parent_id FROM mat_folder f JOIN kette k ON f.id = k.id "
        "WHERE f.parent_id IS NOT NULL) SELECT 1 FROM mat_folder_grant WHERE user_id = ? AND permission IN "
        "('lesen', 'verwalten') AND (valid_until IS NULL OR valid_until >= ?) AND folder_id IN (SELECT id FROM kette) "
        "LIMIT 1", (fid, user["id"], _stichtag()), one=True))


def waehlbares_konto(user_id):
    """Ein Konto, das man auswählen darf (Freigabe, Personenzuordnung): aktiv und mit Namen. Nicht vorhanden,
    deaktiviert und ohne Namen antworten gleich – die Auswahl verrät nicht, welche Konten es gibt (1.6 Nr. 12)."""
    uid = kennung(user_id, "Konto")
    u = db.query("SELECT * FROM users WHERE id = ? AND active = 1 AND status = 'active' AND trim(name) <> ''", (uid,),
                 one=True)
    if not u:
        raise Abgelehnt(KONTO_FEHLT, 404)
    return u


# --- Modulzugang und wirksame Stufe ------------------------------------------------------------------------------

def material_stufe_wirksam(user):
    """Stufe für Kopfleiste, Startweiche und Profil (auth.stufe): 2 = Verwaltung oder irgendwo gültig verwalten,
    1 = Modulzugang, 0 = sonst. Ohne Namen 0. Höchstens eine Abfrage (Grundrechte, gruppiert) – nicht sicht(), denn das
    fragt jede Seite der Plattform; je Anfrage und Konto in g.mat_stufe."""
    if not user:
        return 0
    speicher = _speicher("mat_stufe")
    if speicher is not None and user["id"] in speicher:
        return speicher[user["id"]]
    if not (user["name"] or "").strip():
        n = 0
    elif is_admin(user):
        n = 2
    else:
        r = db.query("SELECT COUNT(*) AS n, MAX(permission = 'verwalten') AS v FROM mat_folder_grant WHERE user_id = ? "
                     "AND permission IN ('lesen', 'verwalten') AND (valid_until IS NULL OR valid_until >= ?)",
                     (user["id"], _stichtag()), one=True)
        if r["v"]:
            n = 2
        elif r["n"] or user["mat_katalog"] or user["mat_pruefer"]:
            # Mit Häkchen „Prüfer“: Katalog und Profil (Urkundennummer, Unterschrift) – eine Prüffreigabe wirkt ohnehin
            # nur mit Qualifikation, also nie ohne Häkchen.
            n = 1
        else:
            n = 0
    if speicher is not None:
        speicher[user["id"]] = n
    return n


def material_stufe(user=None):
    return material_stufe_wirksam(user or current_user())


def zugang(user=None):
    """Modulzugang: Name UND (Verwaltung, ein gültiges Grundrecht, Häkchen Prüfer oder Häkchen Katalog). Wer ihn hat,
    sieht Katalog, Suchfeld und Profil – vom Bestand nur, was seine Freigaben zeigen."""
    return material_stufe_wirksam(user or current_user()) >= 1


def _datum_text(iso):
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return iso or ""


def _namen(liste):
    namen = [n for n in liste if n][:3]
    if not namen:
        return "die Plattform-Verwaltung"
    return namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + " oder " + namen[-1]


def zugang_meldung(user=None):
    """Klartext für 403 ohne Modulzugang: was fehlt und wer hilft."""
    user = user or current_user()
    if not user:
        return "Nicht angemeldet"
    if not (user["name"] or "").strip():
        return NAME_FEHLT
    heute_ = dienste.heute()
    r = db.query("SELECT folder_id, valid_until FROM mat_folder_grant WHERE user_id = ? AND valid_until < ? "
                 "AND valid_until >= ? ORDER BY valid_until DESC, id DESC LIMIT 1",
                 (user["id"], _stichtag(heute_), _stichtag(heute_ - timedelta(days=365))), one=True)
    if r:
        from .bestand import pfad
        ordner = " / ".join(o["name"] for o in pfad(r["folder_id"]))
        return (f"Deine Freigabe für „{ordner}“ ist am {_datum_text(r['valid_until'])} abgelaufen. Verlängern kann sie: "
                f"{_namen(v['name'] for v in verwalter_von(r['folder_id']))}.")
    return NICHT_FREIGESCHALTET


def darf_unterschreiben(user=None):
    """Die eigene Unterschrift hinterlegen: wer festschreibt (Prüfer – schon mit dem Häkchen, damit er Urkundennummer
    und Unterschrift in beliebiger Reihenfolge im Profil eintragen kann) oder aussondert (Verwalter irgendwo)."""
    user = user or current_user()
    return bool(user and zugang(user) and (user["mat_pruefer"] or sicht(user).irgendwo("verwalten")))


def darf_alles(user=None):
    """Was die Oberfläche anbietet (data-darf) – „irgendwo“; am Objekt selbst steht „darf“ (rechte_ordner). Der Server
    prüft jede Aktion trotzdem selbst."""
    user = user or current_user()
    s = sicht(user)
    return {"lesen": s.irgendwo("lesen"), "grund": s.irgendwo("grund"), "verwalten": s.irgendwo("verwalten"),
            "pruefen": s.irgendwo("pruefen"), "katalog": ist_katalogpfleger(user), "alles": s.alles,
            "gliederung_anlegen": s.alles, "qualifiziert": s.qualifiziert,
            "uid": user["id"] if user else None,
            "urkundennummer": (user["urkundennummer"] or "") if user else "",
            # Häkchen „Prüfer“ gesetzt – mit qualifiziert = False heißt das: Urkundennummer fehlt (Hinweis mit Link ins Profil).
            "pruefer_haekchen": bool(user and user["mat_pruefer"]),
            "unterschrift": bool(user and user["signature_png"])}


# --- Decorators --------------------------------------------------------------------------------------------------

def requires_zugang(f):
    """Lesende Routen über den ganzen Bestand und das eigene Profil: angemeldet (sonst 401) und Modulzugang (sonst 403
    mit zugang_meldung). Was die Route liefert, filtert sie selbst nach der Sicht."""
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return jsonify(error="Nicht angemeldet"), 401
        if not zugang(u):
            return jsonify(error=zugang_meldung(u)), 403
        return f(*a, **kw)
    return wrapper


_FELDNAMEN = {"parent_id": "Oberordner", "folder_id": "Ordner"}


def _bezug(quelle, kwargs):
    """Den Bezug einer Anfrage auflösen (ohne Rechte zu prüfen). Kennungen aus der Anfrage über services.kennung – „7“
    und 7.0 gelten wie im Dienst, Unsinn gibt 400. Nicht gefunden: 404. Felder der Anfrage meinen immer einen Ordner."""
    if quelle == "fid":
        if not db.query("SELECT 1 FROM mat_folder WHERE id = ?", (kwargs.get("fid"),), one=True):
            raise Abgelehnt(ORDNER_FEHLT, 404)
        return Bezug("ordner", kwargs["fid"], None, ORDNER_FEHLT)
    if quelle == "iid":
        i = db.query("SELECT * FROM mat_item WHERE id = ?", (kwargs.get("iid"),), one=True)
        if not i:
            raise Abgelehnt(ARTIKEL_FEHLT, 404)
        from .bestand import heimat
        return Bezug("artikel", heimat(i), i, ARTIKEL_FEHLT)
    if quelle == "pid":
        i = db.query("SELECT i.* FROM mat_inspection x JOIN mat_item i ON i.id = x.item_id WHERE x.id = ?",
                     (kwargs.get("pid"),), one=True)
        if not i:
            raise Abgelehnt(PRUEFUNG_FEHLT, 404)
        from .bestand import heimat
        return Bezug("artikel", heimat(i), i, PRUEFUNG_FEHLT)
    if quelle == "rid":
        r = db.query("SELECT folder_id FROM mat_round WHERE id = ?", (kwargs.get("rid"),), one=True)
        if not r:
            raise Abgelehnt(DURCHGANG_FEHLT, 404)
        return Bezug("durchgang", r["folder_id"], None, DURCHGANG_FEHLT)
    art, feld = quelle.split(":", 1)
    d = {"json": json_body, "form": lambda: request.form, "arg": lambda: request.args, "eingabe": eingabe}[art]()
    fid = kennung(d.get(feld), _FELDNAMEN.get(feld, "Ordner"), leer_erlaubt=True)
    if fid is not None and not db.query("SELECT 1 FROM mat_folder WHERE id = ?", (fid,), one=True):
        raise Abgelehnt(ORDNER_FEHLT, 404)
    return Bezug("ordner", fid, None, ORDNER_FEHLT)


def _quelle_pruefen(quelle):
    if quelle in QUELLEN:
        return quelle
    art, _, feld = (quelle or "").partition(":")
    if art in QUELLEN_FELD and re.fullmatch(r"[a-z_]+", feld):
        return quelle
    raise ValueError(f"Unbekannte Quelle {quelle!r}")


def requires_folder(recht, quelle, leer="global"):
    """Decorator für Routen, die einen Ordner, Artikel, eine Prüfung oder einen Durchgang betreffen.

    recht: eines aus RECHTE oder ein Tupel davon (eines genügt – „Materialwart oder Prüfer“). quelle (Pflicht): „fid“,
    „iid“, „pid“ (Artikel der Prüfung), „rid“ (Ordner des Durchgangs) oder ein Feld der Anfrage – „json:<feld>“,
    „form:<feld>“, „arg:<feld>“, „eingabe:<feld>“ (wie routes._eingabe: Formular bei Dateien, sonst JSON). leer sagt,
    was ein leeres Feld heißt (LEER). Ablauf: 401 ohne Anmeldung; 403 ohne Modulzugang (zugang_meldung); Bezug
    auflösen (400 Unsinn, 404 nicht gefunden); nicht sichtbar → 404 mit derselben Meldung; Recht fehlt → 403 mit
    Klartext. Danach stehen der Ordner (bei Artikeln die Heimat) in g.mat_ordner_id und die Artikelzeile in
    g.mat_artikel."""
    erlaubt = recht if isinstance(recht, tuple) else (recht,)
    if not erlaubt or any(b not in RECHTE for b in erlaubt):
        raise ValueError(recht)
    _quelle_pruefen(quelle)
    if leer not in LEER:
        raise ValueError(leer)

    def deko(f):
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                return jsonify(error="Nicht angemeldet"), 401
            # Erst der Zugang zum Modul, dann die Frage nach dem Gegenstand: Sonst verriete 404 gegen 403 einem Konto
            # ohne Zugang, welche Artikel es gibt.
            if not zugang(u):
                return jsonify(error=zugang_meldung(u)), 403
            try:
                bezug = _bezug(quelle, kw)
            except Abgelehnt as exc:
                return jsonify(error=str(exc)), exc.code
            s = sicht(u)
            fid = bezug.ordner_id
            if fid is None:
                ok = (any(s.darf(b, None) for b in erlaubt) if leer == "global"
                      else any(s.irgendwo(b) for b in erlaubt) if leer == "irgendwo" else True)
            else:
                # Fremdes antwortet wie Unbekanntes. Ein Artikel zählt über seine Heimat; ein Systemordner, den man
                # nur teilweise sieht, lässt sich öffnen (lesen), sonst nichts.
                sichtbar = s.darf("lesen", fid) if bezug.art == "artikel" else s.sichtbar(fid)
                if not sichtbar:
                    return jsonify(error=bezug.meldung), 404
                ok = any(s.darf(b, fid) for b in erlaubt) or (
                    "lesen" in erlaubt and bezug.art == "ordner" and fid in s.teil_system)
            if not ok:
                return jsonify(error=_meldung(erlaubt, fid, s, u, leer)), 403
            g.mat_ordner_id = fid
            g.mat_artikel = bezug.artikel
            return f(*a, **kw)
        # Woher die Route ihren Bezug liest – der Trennungstest gleicht Felder der Anfrage gegen seine Tabelle ab.
        wrapper.mat_quelle, wrapper.mat_recht = quelle, erlaubt
        return wrapper
    return deko


def _meldung(erlaubt, fid, s, user, leer="global"):
    """Klartext, wenn das Recht fehlt. Wer das Häkchen „Prüfer“ schon hat, erfährt, was ihm fehlt und wo er es bekommt."""
    if fid is None:
        return NUR_VERWALTUNG_GLOBAL if leer == "global" else "Nur für Materialwarte."
    if "pruefen" in erlaubt:
        if s.qualifiziert:
            hinweis = KEINE_PRUEFFREIGABE
        elif user["mat_pruefer"]:
            hinweis = URKUNDE_IM_PROFIL
        else:
            hinweis = ""
        if "verwalten" in erlaubt:
            if s.qualifiziert:
                return "Nur für Materialwarte und Prüfer dieses Ordners. " + hinweis
            return "Nur für Materialwarte und Prüfer mit Urkundennummer." + (" " + hinweis if hinweis else "")
        if s.qualifiziert:
            return hinweis
        return ("Nur für Prüfer mit Urkundennummer (Häkchen „Prüfer“ in der Nutzerverwaltung, Urkundennummer im eigenen "
                "Profil)." + (" " + hinweis if hinweis else ""))
    if "verwalten" in erlaubt:
        return "Nur für Materialwarte dieses Ordners."
    if "grund" in erlaubt:
        return NUR_GRUNDRECHT
    return "Für diesen Ordner hast du keine Freigabe."


def katalog_required(f):
    """Katalog ändern: nur Admin und Produktkatalogpfleger."""
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return jsonify(error="Nicht angemeldet"), 401
        if not ist_katalogpfleger():
            return jsonify(error="Den Katalog pflegen nur Produktkatalogpfleger und die Verwaltung."), 403
        return f(*a, **kw)
    return wrapper


# --- Rollen vergeben (aus der Nutzerverwaltung) -----------------------------------------------------

def rollen_lesen(d, user_row, rechte):
    """Material-Kennzeichen aus einer Anfrage der Nutzerverwaltung über den Bestand legen.

    d: JSON der Anfrage; user_row: bisheriger Datensatz (oder {} beim Anlegen); rechte: die schon gelesenen Stufen der
    Matrix (bleiben unberührt – die Material-Stufe wirkt seit Phase 2 nicht mehr, Bestand gibt es nur über Freigaben).
    Liefert die zu schreibenden Spalten. Das Häkchen „Prüfer“ geht auch ohne Urkundennummer – die trägt der Prüfer selbst
    im Profil ein, bis dahin darf er nicht prüfen (ist_pruefer).

    „urkundennummer“ nimmt die Schnittstelle weiter an (Skripte, Tests, eine Berichtigung durch die Verwaltung); die
    Oberfläche der Nutzerverwaltung schickt es nicht mehr. Geprüft wird wie im Profil (urkunde_lesen). Geliefert wird
    die Nummer nur, wenn sie sich ändert: ausdrücklich angegeben – oder geleert, weil die Verwaltung das Häkchen
    wegnimmt (eine alte Nummer gälte sonst beim nächsten Häkchen ungefragt wieder, und das Konto könnte sie nirgends
    mehr entfernen). Sonst bleibt, was der Prüfer im Profil eingetragen hat."""
    basis = user_row or {}
    pruefer = bool(basis.get("mat_pruefer"))
    katalog = bool(basis.get("mat_katalog"))
    urkunde = None
    if "mat_pruefer" in d:
        pruefer = wahr(d, "mat_pruefer", "Prüfer")
    if "mat_katalog" in d:
        katalog = wahr(d, "mat_katalog", "Produktkatalogpfleger")
    if "urkundennummer" in d:
        urkunde = urkunde_lesen(d)
    elif basis.get("mat_pruefer") and not pruefer and (basis.get("urkundennummer") or ""):
        urkunde = ""
    out = {"mat_pruefer": int(pruefer), "mat_katalog": int(katalog)}
    if urkunde is not None:
        out["urkundennummer"] = urkunde
    return out


# --- Urkundennummer (aus dem eigenen Profil) ---------------------------------------------------------------

def urkunde_setzen(user, d):
    """Die eigene Urkundennummer im Profil eintragen, ändern oder – leer – entfernen (dann darf er nicht mehr prüfen).
    Nur mit dem Häkchen „Prüfer“, das die Verwaltung setzt. Jede Änderung steht im Journal am Konto, wie eine
    Rollenänderung aus der Nutzerverwaltung. Liefert die gespeicherte Nummer."""
    if not user["mat_pruefer"]:
        raise Abgelehnt(URKUNDE_NUR_PRUEFER, 403)
    if not isinstance(d, dict) or "urkundennummer" not in d:
        raise Abgelehnt("Bitte die Urkundennummer angeben – leer entfernt sie.")
    nummer = urkunde_lesen(d)
    with db.transaction(sofort=True):
        # Frisch gelesen: Nimmt die Verwaltung das Häkchen gerade weg, trägt hier niemand mehr eine Nummer ein.
        alt = db.query("SELECT mat_pruefer, urkundennummer FROM users WHERE id = ?", (user["id"],), one=True)
        if not alt or not alt["mat_pruefer"]:
            raise Abgelehnt(URKUNDE_NUR_PRUEFER, 403)
        vorher = alt["urkundennummer"] or ""
        if vorher != nummer:
            db.execute("UPDATE users SET urkundennummer = ? WHERE id = ?", (nummer, user["id"]))
            journal.eintragen("user", user["id"], "urkundennummer", {"urkundennummer": vorher},
                              {"urkundennummer": nummer})
        sicht_verwerfen()
    return nummer
