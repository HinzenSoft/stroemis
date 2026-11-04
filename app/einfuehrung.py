"""Interaktive Einführung je Modul (Wunsch des Nutzers vom 28.10.2026, Entscheidungen vom 03.11.2026; Bauvorlage
planung/tutorial/entwurf.md, README „Einführungen (Übungen je Modul)“).

Freiwillig mit Angebot: Beim Betreten eines Moduls bietet die Seite eine kurze Übung an – Grundteil für alle mit
Modulzugang, dazu ein Zusatzteil je Rolle (TEILE). Geübt wird auf der gewohnten Seite mit dem Abfrageteil
„uebung=<teil>“: Der Server zeichnet dann nur die Hülle der Seite – ohne echte Daten, mit den Rechten des Teils –, und
im Browser beantwortet einfuehrung.js jede Anfrage der Seite aus dem Übungsbestand der Übungsdatei
(app/static/js/uebung/<modul>.js). Die Übung gilt nur, wenn ihr Teil für das Konto gilt (Nachtrag des Hauptagenten vom
03.11.2026): Ein Mitglied mit ?uebung=verwaltung bekommt die normale Seite – niemand sieht über die Übung die Oberfläche
einer Rolle, die er nicht hat, und die Übungsstufe ist nie höher als die echte.

Zweite Absicherung ist die Sperre (sperre, aus csrf_guard in app/__init__.py): Eine Übungsanfrage – Kopfzeile
„X-Uebung: 1“ oder ein Referer derselben Herkunft mit „uebung=“ im Abfrageteil – kommt an /api/ und /media/ nicht
durch (auch nicht lesend), ebenso wenig jede schreibende Methode und jede Datei. Ausnahmen: der Merker
(/api/einfuehrung/…), GET /api/me, /static/ und Seitenaufrufe – so führt die Kopfleiste aus der Übung hinaus.

Merker ohne Schemaschritt in mat_meta (wie Startseite und Willkommen der Materialablage; Schema bleibt 34):
  einfuehrung:<Konto>  {"<modul>:<teil>": {"zustand": "abgelehnt" | "unterbrochen" | "erledigt", "ablauf": n, "am": …}}
Kein Eintrag heißt: noch nie angeboten. „unterbrochen“ trägt den nächsten unfertigen Ablauf (gesetzt beim Start und nach
jedem fertigen Ablauf), fortgesetzt wird an seinem Anfang. Aus „erledigt“ wird nichts anderes mehr. Der Merker geht mit
dem Konto (konto_vergessen in api_admin.delete_user); ein Zurücksetzen der Materialablage auf dev leert mat_meta und
damit auch ihn. Kein Journal, keine Mail, keine Anzeige in der Leitstelle (Entscheidung 1)."""
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from flask import Blueprint, abort, g, has_request_context, jsonify, request

from . import auth, db, module

bp = Blueprint("einfuehrung", __name__, url_prefix="/api/einfuehrung")
auth.eingabefehler_abfangen(bp)

SCHLUESSEL = "einfuehrung:{uid}"            # in mat_meta
ZUSTAENDE = ("abgelehnt", "unterbrochen", "erledigt")
GESPERRT = "In der Übung gesperrt – es wird nichts gespeichert."

# Je Modul die Wörter für Angebot und Abschluss („Bestand“ heißt in der Strömipedia „Seiten“ usw.).
MODULE = {
    "material": {"zu": "zur Materialablage", "bleibt": "Dein echter Bestand bleibt unverändert.",
                 "ist": "Dein echter Bestand ist unverändert."},
    "wiki": {"zu": "zur Strömipedia", "bleibt": "Die echten Seiten bleiben unverändert.",
             "ist": "Die echten Seiten sind unverändert."},
    "karte": {"zu": "zu den Ankerplätzen", "bleibt": "Die echten Alben bleiben unverändert.",
              "ist": "Die echten Alben sind unverändert."},
    "pruefungen": {"zu": "zu den Riegenkarten", "bleibt": "Die echten Lehrgänge bleiben unverändert.",
                   "ist": "Die echten Lehrgänge sind unverändert."},
}

# Die Teile je Modul in der Reihenfolge des Angebots (Bauvorlage 1.6 und 3). titel: wie Angebot, Abschluss und Profil
# ihn nennen; minuten: geschätzte Dauer; stufe: die Stufe, die rechte[modul] in der Übung trägt (nie höher als die echte,
# weil der Teil nur gilt, wenn das Konto die Rolle hat); start: Adresse des ersten Ablaufs; ablaeufe: die Titel der
# Abläufe in ihrer Reihenfolge. Die Abläufe selbst (Startadresse je Ablauf, Schritte, Antworten) stehen in der
# Übungsdatei uebung/<modul>.js – tests/test_einfuehrung.py vergleicht Teile und Titel mit ihr. Ändert ein Modul-Teil
# seine Abläufe, gehören Titel und Startadresse des ersten Ablaufs hierher.
TEILE = {
    "material": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 5, "stufe": auth.MITGLIED, "start": "/materialablage",
         "ablaeufe": ("Zurechtfinden",)},
        {"teil": "pruefer", "titel": "Prüfer", "minuten": 4, "stufe": auth.MITGLIED, "start": "/materialablage",
         "ablaeufe": ("Prüfung durchführen",)},
        {"teil": "materialwart", "titel": "Materialwart", "minuten": 4, "stufe": auth.MITGLIED, "start": "/materialablage",
         "ablaeufe": ("Artikel anlegen",)},
        {"teil": "verwaltung", "titel": "Material-Verwaltung", "minuten": 3, "stufe": auth.VERWALTUNG,
         "start": "/materialablage", "ablaeufe": ("Katalog und Prüfformular",)},
    ),
    "wiki": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 5, "stufe": auth.MITGLIED, "start": "/stroemipedia",
         "ablaeufe": ("Lesen",)},
        {"teil": "redakteur", "titel": "Redakteur", "minuten": 3, "stufe": auth.REDAKTEUR, "start": "/stroemipedia",
         "ablaeufe": ("Seite anlegen",)},
        {"teil": "verwaltung", "titel": "Verwaltung", "minuten": 2, "stufe": auth.VERWALTUNG, "start": "/stroemipedia",
         "ablaeufe": ("Für alle Angemeldeten freigeben",)},
    ),
    "karte": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 3, "stufe": auth.MITGLIED, "start": "/ankerplaetze",
         "ablaeufe": ("Karte und Album", "Suchen und filtern")},
        {"teil": "redakteur", "titel": "Redakteur", "minuten": 4, "stufe": auth.REDAKTEUR, "start": "/ankerplaetze",
         "ablaeufe": ("Album anlegen", "Bilder hochladen", "Bild beschreiben")},
    ),
    "pruefungen": (
        {"teil": "grund", "titel": "Grundteil", "minuten": 5, "stufe": auth.MITGLIED, "start": "/riegenkarten",
         "ablaeufe": ("Lehrgang öffnen",)},
        {"teil": "leitung", "titel": "Leitung", "minuten": 3, "stufe": auth.MITGLIED, "start": "/riegenkarten",
         "ablaeufe": ("Teilnehmende eintragen",)},
        {"teil": "redakteur", "titel": "Redakteur", "minuten": 3, "stufe": auth.REDAKTEUR, "start": "/riegenkarten",
         "ablaeufe": ("Lehrgang anlegen",)},
    ),
}

# Was data-darf der Materialablage in der Übung trägt (rechte.darf_alles mit den Rechten des Teils statt der echten).
# uid ist die eigene Kennung, die Urkundennummer ein Platzhalter.
_DARF_AUS = {"lesen": True, "grund": True, "verwalten": False, "pruefen": False, "katalog": False, "alles": False,
             "gliederung_anlegen": False, "qualifiziert": False, "urkundennummer": "", "pruefer_haekchen": False,
             "unterschrift": False}
DARF_MATERIAL = {
    "grund": dict(_DARF_AUS),
    "pruefer": dict(_DARF_AUS, pruefen=True, qualifiziert=True, urkundennummer="ÜBUNG", pruefer_haekchen=True,
                    unterschrift=True),
    "materialwart": dict(_DARF_AUS, verwalten=True, unterschrift=True),
    "verwaltung": dict(_DARF_AUS, verwalten=True, katalog=True, alles=True, gliederung_anlegen=True, unterschrift=True),
}


# --- Wer welchen Teil hat (Bauvorlage 1.6) ---------------------------------------------------------------------------

def _leitung(user):
    """Leitung in einem Lehrgang der Riegenkarten – oder Redakteur, der jeden eigenen Lehrgang leitet."""
    return auth.schreibt("pruefungen", user) or bool(db.query(
        "SELECT 1 FROM pruef_ausbilder WHERE user_id = ? AND ist_leitung = 1 LIMIT 1", (user["id"],), one=True))


def _praedikat(modul, teil, user):
    from .material.services import rechte as mat
    if modul == "material":
        if not mat.zugang(user):
            return False
        return {"grund": lambda: True, "pruefer": lambda: mat.qualifiziert(user),
                "materialwart": lambda: bool(mat.darf_alles(user)["verwalten"]),
                "verwaltung": lambda: mat.ist_material_verwaltung(user)}[teil]()
    if not auth.nutzt(modul, user):
        return False
    if teil == "grund":
        return True
    if teil == "redakteur":
        return auth.schreibt(modul, user)
    if teil == "verwaltung":
        return auth.verwaltet(modul, user)
    if teil == "leitung":
        return _leitung(user)
    return False


def teil_von(modul, teil):
    """Die Angaben eines Teils aus TEILE – oder None."""
    return next((t for t in TEILE.get(modul, ()) if t["teil"] == teil), None)


def gilt(modul, teil, user=None):
    """Gilt der Teil für das Konto (Prädikat aus der Bauvorlage 1.6)? Je Anfrage einmal gerechnet."""
    user = user or auth.current_user()
    if not user or not teil_von(modul, teil):
        return False
    speicher = g.setdefault("einfuehrung_gilt", {}) if has_request_context() else {}
    schluessel = (int(user["id"]), modul, teil)
    if schluessel not in speicher:
        speicher[schluessel] = bool(_praedikat(modul, teil, user))
    return speicher[schluessel]


def uebung(modul):
    """Der Teil, in dem diese Seite geübt wird – nur mit einem bekannten Teil des Moduls in ?uebung= UND wenn er für das
    Konto gilt (sonst wird der Parameter übergangen: normale Seite). Sonst None."""
    if not has_request_context():
        return None
    teil = request.args.get("uebung")
    if not teil or not teil_von(modul, teil):
        return None
    return teil if gilt(modul, teil) else None


def stufe(modul, teil):
    t = teil_von(modul, teil)
    return t["stufe"] if t else auth.KEIN_ZUGRIFF


def darf_material(teil, user=None):
    """data-darf der Materialablage in der Übung (DARF_MATERIAL, uid = eigene Kennung)."""
    user = user or auth.current_user()
    return dict(DARF_MATERIAL[teil], uid=user["id"] if user else None)


# --- Merker ----------------------------------------------------------------------------------------------------------

def merker(uid):
    """{"<modul>:<teil>": {zustand, ablauf, am}} des Kontos – leer ohne Eintrag oder bei unlesbarem Wert."""
    row = db.query("SELECT wert FROM mat_meta WHERE schluessel = ?", (SCHLUESSEL.format(uid=int(uid)),), one=True)
    try:
        wert = json.loads(row["wert"]) if row else {}
    except ValueError:
        return {}
    return wert if isinstance(wert, dict) else {}


def konto_vergessen(uid):
    """Beim Löschen eines Kontos (api_admin.delete_user): der Merker geht mit."""
    db.execute("DELETE FROM mat_meta WHERE schluessel = ?", (SCHLUESSEL.format(uid=int(uid)),))


def adresse(modul, teil, ablauf=0):
    """Die Übungsadresse eines Teils: Startadresse des ersten Ablaufs mit uebung=<teil> (und ablauf=n beim Fortsetzen;
    die Übungsdatei kennt die Startadresse jedes Ablaufs und führt dorthin)."""
    t = teil_von(modul, teil)
    s = urlsplit(t["start"])
    abfrage = [(k, v) for k, werte in parse_qs(s.query, keep_blank_values=True).items() for v in werte
               if k not in ("uebung", "ablauf")]
    abfrage.append(("uebung", teil))
    if ablauf:
        abfrage.append(("ablauf", str(int(ablauf))))
    return urlunsplit(("", "", s.path, urlencode(abfrage), s.fragment))


def _eintrag(modul, t, m):
    """Ein Teil, wie Angebot, Abschluss und Profil ihn brauchen."""
    stand = m.get(f"{modul}:{t['teil']}") if isinstance(m.get(f"{modul}:{t['teil']}"), dict) else {}
    zustand = stand.get("zustand") if stand.get("zustand") in ZUSTAENDE else "offen"
    ablauf = stand.get("ablauf") if isinstance(stand.get("ablauf"), int) and not isinstance(stand.get("ablauf"), bool) \
        else 0
    ablauf = ablauf if 0 <= ablauf < len(t["ablaeufe"]) else 0
    return {"teil": t["teil"], "titel": t["titel"], "minuten": t["minuten"], "zustand": zustand, "ablauf": ablauf,
            "ablaeufe": len(t["ablaeufe"]), "ablauf_titel": t["ablaeufe"][ablauf], "am": stand.get("am") or "",
            "adresse": adresse(modul, t["teil"], ablauf if zustand == "unterbrochen" else 0)}


def teile(modul, user=None, m=None):
    """Die Teile des Moduls, die für das Konto gelten, mit ihrem Stand."""
    user = user or auth.current_user()
    if not user or modul not in TEILE:
        return []
    m = merker(user["id"]) if m is None else m
    return [_eintrag(modul, t, m) for t in TEILE[modul] if gilt(modul, t["teil"], user)]


def angebot(modul, user=None, m=None):
    """Was beim Betreten angeboten wird: Teile, die für das Konto gelten und offen oder unterbrochen sind (Bauvorlage
    2.6). „Nicht jetzt“ setzt sie auf abgelehnt – dann kommt nur noch ein Teil dazu, der durch eine neue Rolle gilt."""
    return [t for t in teile(modul, user, m) if t["zustand"] in ("offen", "unterbrochen")]


def seite(modul):
    """Für eine Seite des Moduls (vor dem Zeichnen, nicht für Fehler- und Druckseiten): setzt g.einfuehrung – base.html
    gibt es als STROEMIS.einfuehrung an einfuehrung.js, inject legt im Übungsmodus die Stufe des Teils auf rechte[modul].
    Liefert den Teil der Übung oder None."""
    user = auth.current_user()
    if not user:
        return None
    teil = uebung(modul)
    m = merker(user["id"])
    alle = teile(modul, user, m)
    daten = {"modul": modul, "name": module.NAME[modul], "start": module.PFAD[modul], **MODULE[modul],
             "uebung": teil, "teile": alle,
             # Im Übungsmodus kein Angebot; Seiten der Übung bieten nichts an.
             "angebot": [] if teil else [t for t in alle if t["zustand"] in ("offen", "unterbrochen")],
             "anleitung": ""}
    if teil:
        daten["stufe"] = stufe(modul, teil)
        daten["anleitung"] = _anleitung_uebersicht(modul, user)
    g.einfuehrung = daten
    return teil


def _anleitung_uebersicht(modul, user):
    """Die Adresse der Anleitung des Moduls in der Strömipedia (Thema „uebersicht“) – nur, wenn das Konto sie lesen darf."""
    if modul == "material":
        from .material.services import anleitung as mat_anleitung
        return mat_anleitung.verweise(user).get("uebersicht") or ""
    from . import anleitung
    return anleitung.verweise(modul, user).get("uebersicht") or ""


def rechte_in_uebung(rechte):
    """Für den Kontextprozessor: im Übungsmodus trägt rechte[modul] die Stufe des Teils."""
    e = getattr(g, "einfuehrung", None) if has_request_context() else None
    if not e or not e.get("uebung"):
        return rechte
    return dict(rechte, **{e["modul"]: e["stufe"]})


# --- Profil „Einführungen“ (Bauvorlage 2.9) ----------------------------------------------------------------------------

def _datum(zeitpunkt):
    from datetime import datetime, timezone

    from .material.services import ZONE
    try:
        t = datetime.fromisoformat(zeitpunkt)
    except (TypeError, ValueError):
        return ""
    t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return t.astimezone(ZONE).strftime("%d.%m.%Y")


def profil(user=None):
    """Je Modul mit Übung für das Konto: Name und je geltendem Teil eine Zeile (Titel, Minuten, Stand, Knopf, Adresse).
    Leer, wenn das Konto kein Modul mit Übung hat – dann gibt es den Abschnitt nicht."""
    user = user or auth.current_user()
    if not user:
        return []
    m = merker(user["id"])
    out = []
    for modul in TEILE:
        zeilen = []
        for t in teile(modul, user, m):
            if t["zustand"] == "erledigt":
                datum = _datum(t["am"])
                stand, knopf = (f"erledigt am {datum}" if datum else "erledigt"), "Erneut ansehen"
            elif t["zustand"] == "unterbrochen":
                stand, knopf = f"unterbrochen bei „{t['ablauf_titel']}“", "Fortsetzen"
            else:
                stand, knopf = "noch nicht begonnen", "Starten"
            zeilen.append(dict(t, stand=stand, knopf=knopf))
        if zeilen:
            out.append({"modul": modul, "name": module.NAME[modul], "zeilen": zeilen})
    return out


# --- Sperre (Bauvorlage 2.4) -------------------------------------------------------------------------------------------

def _uebungsanfrage():
    """Kopfzeile X-Uebung: 1 oder ein Referer derselben Herkunft mit „uebung=“ im Abfrageteil (fängt, was keine
    Kopfzeile tragen kann: <img>, Beacon, Datei-Links, window.open; die Referrer-Policy schickt bei gleicher Herkunft die
    volle Adresse)."""
    if request.headers.get("X-Uebung") == "1":
        return True
    ref = request.headers.get("Referer") or ""
    if not ref:
        return False
    try:
        teile_ref = urlsplit(ref)
    except ValueError:
        return False
    if teile_ref.netloc.lower() != (request.host or "").lower():
        return False
    return "uebung" in parse_qs(teile_ref.query, keep_blank_values=True)


def _datei(pfad):
    """Eine Datei statt einer Seite – dieselbe Regel wie der Service Worker (app/static/js/sw.js): Endung im letzten
    Abschnitt oder …/pdf, …/sammelprotokoll."""
    endung = pfad.rsplit("/", 1)[-1].rpartition(".")
    return bool(endung[1] and re.fullmatch(r"[A-Za-z0-9]{1,8}", endung[2])) or pfad.endswith(("/pdf", "/sammelprotokoll"))


_FREI = ("/static/", "/sw.js", "/manifest.webmanifest", "/offline")


def sperre():
    """Erster Schritt von csrf_guard: Eine Übungsanfrage an /api/ oder /media/, mit schreibender Methode oder an eine
    Datei bekommt 403 mit GESPERRT (Schnittstelle als JSON, sonst die deutsche Fehlerseite). Erlaubt bleiben der Merker,
    GET /api/me, /static/ (und was zur App gehört: Worker, Manifest, Hinweisseite) und Seitenaufrufe. Sonst None."""
    if not _uebungsanfrage():
        return None
    pfad = request.path
    if pfad.startswith("/api/einfuehrung/") or pfad.startswith(_FREI) or pfad in _FREI:
        return None
    if pfad == "/api/me" and request.method in ("GET", "HEAD"):
        return None
    if not (pfad.startswith(("/api/", "/media/")) or request.method not in ("GET", "HEAD") or _datei(pfad)):
        return None
    if pfad.startswith("/api/"):
        return jsonify(error=GESPERRT), 403
    abort(403, description=GESPERRT)


# --- Schnittstelle: Merker -------------------------------------------------------------------------------------------

@bp.put("/<modul>/<teil>")
@auth.login_required
def merken(modul, teil):
    """Den Stand eines Teils merken: {zustand: abgelehnt | unterbrochen | erledigt, ablauf: n}. 404 für unbekannte Teile,
    403, wenn der Teil nicht für das Konto gilt (ohne Modulzugang nie), 400 bei falschem Zustand oder Ablauf. Aus
    „erledigt“ wird nichts anderes (Antwort trotzdem ok). Unter der Schreibsperre: Zwei gleichzeitige Aufrufe (zwei
    Teile, zwei Reiter) verlieren nichts."""
    t = teil_von(modul, teil)
    if not t:
        return jsonify(error="Diese Übung gibt es nicht."), 404
    user = auth.current_user()
    if not gilt(modul, teil, user):
        return jsonify(error="Diese Übung gibt es für dein Konto nicht."), 403
    d = auth.json_body()
    zustand, ablauf = d.get("zustand"), d.get("ablauf", 0)
    if zustand not in ZUSTAENDE:
        return jsonify(error="Unbekannter Zustand der Übung."), 400
    if not isinstance(ablauf, int) or isinstance(ablauf, bool) or not 0 <= ablauf < len(t["ablaeufe"]):
        return jsonify(error="Diesen Ablauf gibt es in der Übung nicht."), 400
    schluessel = SCHLUESSEL.format(uid=int(user["id"]))
    with db.transaction(sofort=True):
        alle = merker(user["id"])
        alt = alle.get(f"{modul}:{teil}")
        if not (isinstance(alt, dict) and alt.get("zustand") == "erledigt"):
            alle[f"{modul}:{teil}"] = {"zustand": zustand, "ablauf": ablauf, "am": db.now()}
            db.execute("INSERT INTO mat_meta (schluessel, wert) VALUES (?, ?) "
                       "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert", (schluessel, json.dumps(alle)))
    return jsonify(ok=True)
