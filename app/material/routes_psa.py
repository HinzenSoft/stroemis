"""Routen zu „Meine PSA“ und zur Mangelmeldung (Phase 3 · Lieferung 1, Bauentwurf 2.2 und 6.1).

„Meine PSA“ hat einen eigenen, engen Zugangsweg neben rechte.zugang: jedes aktive Konto mit Namen (psa.konto), auch
ohne Stufe im Modul Material – und nur die eigenen, nicht ausgesonderten Artikel als Karte (psa.artikel_json). Die
Seite fragt nicht _seite() (das verlangt den Modulzugang); requires_folder und die 404-Regel bleiben, wie sie sind.
Mangel melden darf die zugeordnete Person (auch ohne Stufe) und jeder mit Leserecht am Artikel
(rechte.requires_artikel_oder_zugeordnet); der Dienst prüft vor den Fotos und in der Transaktion noch einmal
(services/mangel.py)."""
import json
from functools import wraps

from flask import jsonify, redirect, render_template, request, url_for

from ..auth import current_user, json_body, login_required
from .routes import _eingabe, _fehlerseite, api, seiten
from .services import Abgelehnt, mangel, psa, wahr
from .services import status as st
from .services.rechte import darf_alles, requires_artikel_oder_zugeordnet, zugang


def psa_required(f):
    """Angemeldet (sonst 401) und PSA-Konto (sonst 403 mit PSA_NAME_FEHLT) – ohne Blick auf die Modulstufe."""
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return jsonify(error="Nicht angemeldet"), 401
        if not psa.konto(u):
            return jsonify(error=psa.PSA_NAME_FEHLT), 403
        return f(*a, **kw)
    return wrapper


# --- Seiten ---------------------------------------------------------------------------------------------------------

def _psa_seite(iid=None):
    """Die Seite „Meine PSA“ (Liste oder ein Artikel) im Gerüst des Moduls – ohne Modulzugang ohne Modulnavigation und
    Ordnerleiste (nur_psa). Ein fremder, unbekannter oder ausgesonderter Artikel antwortet gleich: 404."""
    u = current_user()
    if not u:
        return redirect(url_for("pages.login", next=request.full_path.rstrip("?")))
    if not psa.konto(u):
        return _fehlerseite(403, psa.PSA_NAME_FEHLT)
    if iid is not None:
        try:
            psa.eigener(iid, u)
        except Abgelehnt as exc:
            return _fehlerseite(exc.code, str(exc))
    return render_template("material/seite.html", user=u, active="meine_psa" if psa.kopfleiste(u) else "material",
                           ansicht="meine_psa", nur_psa=not zugang(u), daten=json.dumps({"id": iid}),
                           darf=json.dumps(darf_alles(u)), warnung=None)


@seiten.get("/material/meine-psa")
def meine_psa():
    return _psa_seite()


@seiten.get("/material/meine-psa/<int:iid>")
def meine_psa_artikel(iid):
    return _psa_seite(iid)


# --- Schnittstelle --------------------------------------------------------------------------------------------------

@api.get("/meine-psa")
@psa_required
def psa_liste():
    """Die eigenen Artikel als Karten (dringende zuerst, höchstens psa.MAX_ARTIKEL), dazu gesamt, ob Erinnerungen per
    Mail an sind (users.mat_psa_mails) und die Schwelle „bald fällig“. Die Einzelansicht filtert im Browser."""
    u = current_user()
    karten, gesamt = psa.liste(u)
    return jsonify(artikel=karten, gesamt=gesamt, mails=bool(u["mat_psa_mails"]), schwelle_tage=st.schwelle_tage())


@api.put("/meine-psa/mails")
@login_required
def psa_mails():
    """Erinnerungen zur eigenen PSA an oder aus: {"an": true | false} – nur fürs eigene Konto (eine Kennung im Inhalt
    zählt nicht)."""
    d = json_body()
    if not isinstance(d, dict) or d.get("an") in (None, ""):
        raise Abgelehnt("Bitte „an“ angeben (ja oder nein).")
    return jsonify(an=psa.mails_setzen(current_user(), wahr(d, "an", "Erinnerungen per Mail")))


@api.post("/artikel/<int:iid>/mangel")
@requires_artikel_oder_zugeordnet("lesen")
def artikel_mangel(iid):
    """Mangel melden – als Formular (Feld „beschreibung“, Fotos im Feld „fotos“, höchstens 3) oder als JSON ohne Fotos.
    Sperrt sofort. „gesperrt“: diese Meldung hat gesperrt; „mail“: mindestens eine Mail an Materialwart, Prüfer oder
    Verwaltung ging an den Versand (false bei DEMO-Artikel, Umgebungssperre oder ohne Empfänger)."""
    mid, gesperrt, mail = mangel.melden(iid, _eingabe(), request.files.getlist("fotos"))
    # Die eigene Meldung – den eigenen Namen sieht der Melder immer.
    return jsonify(mangel=mangel.mangel_json(mangel.meldung(mid), True), gesperrt=gesperrt, mail=mail), 201
