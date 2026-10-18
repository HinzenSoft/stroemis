"""Routen der Freigaben je Ordner und der Nutzersuche (Phase 2 · Lieferung 1, Abschnitt 4.1).

Vergeben, ändern, entziehen und verlängern darf, wer den Ordner verwaltet, an dem die Freigabe verankert ist – nach
den Regeln in services/freigaben.py (1.6). Fremdes und Unsichtbares antwortet 404 mit derselben Meldung wie „gibt es
nicht“; 403 gibt es nur, wenn man den Ordner sieht, ihn aber nicht verwaltet. „Meine Freigaben“ liest jeder
Angemeldete, auch ohne Modulzugang – genau dann braucht er den Hinweis, wer verlängern kann. Die Freigaben eines
Kontos (für die Nutzerverwaltung) liest nur die Plattform-Verwaltung."""
from functools import wraps

from flask import jsonify, request

from ..auth import current_user, is_admin, json_body, login_required
from .routes import api
from .services import freigaben
from .services.rechte import requires_folder, requires_zugang, sicht, zugang, zugang_meldung


@api.get("/ordner/<int:fid>/freigaben")
@requires_folder("verwalten", "fid")
def ordner_freigaben(fid):
    return jsonify(freigaben.liste(fid))


@api.post("/ordner/<int:fid>/freigaben")
@requires_folder("verwalten", "fid")
def freigabe_erteilen(fid):
    """Felder: user_id, grundrecht („lesen“, „verwalten“ oder null), grund_bis, pruefen_bis (null: keine Prüffreigabe),
    notiz. Antwort: die geschriebenen Zeilen und – solange man den Ordner noch verwaltet – die neue Liste."""
    ids = freigaben.erteilen(fid, json_body())
    liste = freigaben.liste(fid) if sicht().darf("verwalten", fid) else None
    return jsonify(freigaben=[freigaben.eintrag(gid) for gid in ids], liste=liste), 201


@api.post("/ordner/<int:fid>/freigaben/verlaengern")
@requires_folder("verwalten", "fid")
def freigaben_verlaengern(fid):
    return jsonify(freigaben.verlaengern(fid, json_body()))


def _freigabe_recht(f):
    """Wie requires_folder für eine Freigabe: 401, 403 ohne Modulzugang, 404 für unbekannte und für solche an einem
    Ordner, den man nicht sieht, 403 ohne verwalten am Anker."""
    @wraps(f)
    def wrapper(gid):
        u = current_user()
        if not u:
            return jsonify(error="Nicht angemeldet"), 401
        if not zugang(u):
            return jsonify(error=zugang_meldung(u)), 403
        z = freigaben.zeile(gid)
        s = sicht(u)
        if not z or not s.sichtbar(z["folder_id"]):
            return jsonify(error=freigaben.FREIGABE_FEHLT), 404
        if not s.darf("verwalten", z["folder_id"]):
            return jsonify(error=freigaben.NUR_VERWALTER), 403
        return f(gid)
    return wrapper


@api.put("/freigaben/<int:gid>")
@_freigabe_recht
def freigabe_aendern(gid):
    """Felder (jedes optional): recht, bis (null = unbefristet, nur Grundrechte), notiz."""
    freigaben.aendern(gid, json_body())
    return jsonify(freigabe=freigaben.eintrag(gid))


@api.delete("/freigaben/<int:gid>")
@_freigabe_recht
def freigabe_entziehen(gid):
    return jsonify(ok=True, offene_entwuerfe=freigaben.entziehen(gid))


@api.get("/freigaben/meine")
@login_required
def meine_freigaben():
    return jsonify(freigaben.meine(current_user()))


@api.get("/freigaben")
def konto_freigaben():
    """?user_id= – alle Freigaben eines Kontos mit Notiz (Nutzerverwaltung, Dialog „Bearbeiten“)."""
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    if not is_admin():
        return jsonify(error=freigaben.NUR_VERWALTUNG), 403
    return jsonify(freigaben=freigaben.des_kontos(request.args.get("user_id")))


@api.get("/nutzer")
@requires_zugang
def nutzer():
    """?q= – Personensuche für Freigaben und Zuordnung: nur Name, Gliederung und Qualifikation."""
    if not sicht().irgendwo("verwalten"):
        return jsonify(error="Personen suchen nur Materialwarte und die Plattform-Verwaltung."), 403
    return jsonify(freigaben.nutzer_suchen(request.args.get("q")))
