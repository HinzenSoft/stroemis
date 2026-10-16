"""Rechte im Modul Material.

Abbildung der Rollen aus dem Konzept auf das Rechtemodell der Plattform (Rechte-Matrix je Modul):

  Führungskraft (lesend)    Stufe „Mitglied“ im Modul Material
  Materialwart              Stufe „Verwaltung“ im Modul Material
  Prüfer (Sachkundiger)     Kennzeichen mat_pruefer – wirkt nur mit hinterlegter Urkundennummer
  Produktkatalogpfleger     Kennzeichen mat_katalog (plattformweit)
  Admin                     Verwaltung im Modul Verwaltung: Materialwart und Katalog überall –
                            Prüfer aber nur mit eigenem Kennzeichen und eigener Urkundennummer,
                            denn Sachkunde lässt sich nicht verwalten, nur nachweisen.
  Nutzer                    im MVP keine Rechte im Modul

Prüfer und Katalogpfleger haben mindestens Leserecht (api_admin hebt die Stufe beim Vergeben an).
Die Rollen gelten im MVP global. requires_folder löst den Ordner einer Anfrage aber schon jetzt auf:
In Phase 2 kommen hier die befristeten Freigaben aus mat_folder_grant dazu, ohne dass sich an den
Routen etwas ändert.
"""
import re
import unicodedata
from functools import wraps

from flask import g, jsonify, request

from ... import db
from ...auth import MITGLIED, current_user, is_admin, nutzt, stufe, verwaltet
from . import Abgelehnt, text, wahr

BERECHTIGUNGEN = ("lesen", "pruefen", "verwalten")
URKUNDE_FEHLT = "Ohne Urkundennummer keine Prüferrolle."


def urkunde_gueltig(nummer):
    """Eine Urkundennummer muss Buchstaben oder Ziffern enthalten – Leerzeichen, Bindestriche oder
    unsichtbare Zeichen allein sind keine."""
    return bool(re.search(r"[^\W_]", nummer or ""))


def urkunde_saeubern(nummer):
    """Unsichtbare Zeichen (Formatzeichen wie U+200B, U+FEFF, weiches Trennzeichen) entfernen."""
    return "".join(c for c in (nummer or "") if unicodedata.category(c) not in ("Cf", "Cc")).strip()


def ist_pruefer(user=None):
    """Sachkundiger mit Urkundennummer – nur das zählt, kein Schulungskatalog, kein Ablaufdatum."""
    user = user or current_user()
    return bool(user and user["mat_pruefer"] and urkunde_gueltig(urkunde_saeubern(user["urkundennummer"])))


def ist_katalogpfleger(user=None):
    user = user or current_user()
    return bool(user and (is_admin(user) or user["mat_katalog"]))


def darf(berechtigung, ordner_id=None, user=None):
    """Darf der Nutzer das im Ordner (und darunter)? Im MVP entscheiden allein die Rollen; der
    Ordner ist schon Teil der Frage, damit Phase 2 die Freigaben ergänzen kann."""
    user = user or current_user()
    if not user:
        return False
    if berechtigung == "lesen":
        return nutzt("material", user) or ist_pruefer(user) or ist_katalogpfleger(user)
    if berechtigung == "verwalten":
        return verwaltet("material", user)
    if berechtigung == "pruefen":
        return ist_pruefer(user)
    raise ValueError(f"Unbekannte Berechtigung {berechtigung}")


def darf_alles(user=None):
    """Was die Oberfläche anbietet – der Server prüft jede Aktion trotzdem selbst."""
    user = user or current_user()
    return {"lesen": darf("lesen", user=user), "verwalten": darf("verwalten", user=user),
            "pruefen": darf("pruefen", user=user), "katalog": ist_katalogpfleger(user),
            "urkundennummer": (user["urkundennummer"] or "") if user else "",
            "unterschrift": bool(user and user["signature_png"])}


def _ordner_aus_anfrage(quelle, kwargs):
    """Kennung des Ordners, um den es geht: aus der Route (Ordner, Artikel) oder dem JSON."""
    if quelle == "fid":
        return kwargs.get("fid")
    if quelle == "iid":
        row = db.query("SELECT folder_id FROM mat_item WHERE id = ?", (kwargs.get("iid"),), one=True)
        if not row:
            raise Abgelehnt("Artikel nicht gefunden.", 404)
        return row["folder_id"]
    if quelle and quelle.startswith("json:"):
        d = request.get_json(silent=True)
        wert = d.get(quelle[5:]) if isinstance(d, dict) else None
        return wert if isinstance(wert, int) and not isinstance(wert, bool) else None
    return None


def requires_folder(berechtigung, quelle=None):
    """Decorator für Routen, die einen Ordner betreffen: angemeldet, Berechtigung im Ordner (geerbt
    von allen darüberliegenden), sonst 401/403. quelle sagt, woher der Ordner kommt: "fid" (Route),
    "iid" (Artikel der Route), "json:<feld>" (Anfrage) oder None (ganzer Bestand). Der gefundene
    Ordner steht danach in g.mat_ordner_id."""
    if berechtigung not in BERECHTIGUNGEN:
        raise ValueError(berechtigung)

    def deko(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not current_user():
                return jsonify(error="Nicht angemeldet"), 401
            # Erst der Zugang zum Modul, dann die Frage nach dem Ordner: Sonst verriete 404 gegen 403
            # einem Konto ohne Zugang, welche Artikel es gibt.
            if not darf("lesen"):
                return jsonify(error=_meldung("lesen")), 403
            try:
                ordner_id = _ordner_aus_anfrage(quelle, kw)
            except Abgelehnt as exc:
                return jsonify(error=str(exc)), exc.code
            if not darf(berechtigung, ordner_id):
                return jsonify(error=_meldung(berechtigung)), 403
            g.mat_ordner_id = ordner_id
            return f(*a, **kw)
        return wrapper
    return deko


def _meldung(berechtigung):
    if berechtigung == "pruefen":
        return "Nur für Prüfer mit hinterlegter Urkundennummer."
    if berechtigung == "verwalten":
        return "Nur für Materialwarte."
    return "Für dein Konto ist das Modul Material nicht freigeschaltet."


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
    """Material-Rollen aus einer Anfrage der Nutzerverwaltung über den Bestand legen.

    d: JSON der Anfrage; user_row: bisheriger Datensatz (oder {} beim Anlegen); rechte: die schon
    gelesenen Stufen der Matrix (werden hier angepasst). Liefert die zu schreibenden Spalten.
    Regeln: Prüfer nur mit Urkundennummer; Prüfer und Katalogpfleger haben mindestens Leserecht."""
    basis = user_row or {}
    pruefer = bool(basis.get("mat_pruefer"))
    katalog = bool(basis.get("mat_katalog"))
    urkunde = basis.get("urkundennummer") or ""
    if "mat_pruefer" in d:
        pruefer = wahr(d, "mat_pruefer", "Prüfer")
    if "mat_katalog" in d:
        katalog = wahr(d, "mat_katalog", "Produktkatalogpfleger")
    if "urkundennummer" in d:
        urkunde = urkunde_saeubern(text(d, "urkundennummer", "Urkundennummer", n=40))
    if pruefer and not urkunde_gueltig(urkunde):
        raise Abgelehnt(URKUNDE_FEHLT)
    if (pruefer or katalog) and rechte.get("material", 0) < MITGLIED:
        # Wer das Modul ausdrücklich auf „kein Zugriff“ stellt, soll nicht stillschweigend etwas anderes
        # gespeichert sehen; wer nur das Kennzeichen vergibt, bekommt das Leserecht dazu.
        if isinstance(d.get("rechte"), dict) and "material" in d["rechte"]:
            raise Abgelehnt("Prüfer und Produktkatalogpfleger brauchen im Modul Material mindestens „Mitglied“.")
        rechte["material"] = MITGLIED
    return {"mat_pruefer": int(pruefer), "mat_katalog": int(katalog), "urkundennummer": urkunde}


def material_stufe(user=None):
    return stufe("material", user)
