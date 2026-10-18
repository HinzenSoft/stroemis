"""Routen der Rückrufe (Lieferung 4, Überblick).

Lesen dürfen alle mit Zugang zum Modul (wie den Katalog), anlegen und beenden nur Katalogpfleger und die
Verwaltung. Betroffene Artikel und ihre Zahlen zeigt jede Antwort nur aus dem eigenen Bereich (Phase 2); was darüber
hinausgeht, nur der Plattform-Verwaltung. Gesperrt wird über die vorhandene Route der Prüfer (POST
/artikel/<iid>/sperren, Grund „rueckruf“).
Die Kennung eines Rückrufs heißt in den Pfaden ruid – rid ist der Prüfdurchgang. Die Fachregeln stehen in
services/rueckruf.py."""
from flask import jsonify

from ..auth import current_user, json_body
from .routes import _katalog_lesen, api
from .services import katalog, rueckruf
from .services.rechte import katalog_required, requires_zugang


@api.get("/produkte/<int:pid>/rueckrufe")
def produkt_rueckrufe(pid):
    if not current_user():
        return jsonify(error="Nicht angemeldet"), 401
    _katalog_lesen()
    katalog.produkt(pid)
    return jsonify(rueckrufe=rueckruf.fuer_produkt(pid))


@api.post("/produkte/<int:pid>/rueckrufe")
@katalog_required
def rueckruf_anlegen(pid):
    """Felder: title (Pflicht), description, url (nur http/https), serials (eine je Zeile; leer = alle Artikel),
    mail (Vorgabe ja). Die Antwort sagt, wie viele Artikel im eigenen Bereich betroffen sind und ob für sie eine Mail
    hinausgeht („benachrichtigt“); der Plattform-Verwaltung dazu, wie viele Mails hinausgehen („empfaenger“) und welche
    Seriennummern zu keinem Artikel im Bestand passen („nicht_gefunden“)."""
    ruid, info = rueckruf.anlegen(pid, json_body(), current_user())
    return jsonify(rueckruf=rueckruf.rueckruf_json(rueckruf.rueckruf(ruid), mit_artikel=True), **info), 201


@api.post("/rueckrufe/<int:ruid>/beenden")
@katalog_required
def rueckruf_beenden(ruid):
    """Beenden mit Vermerk (Pflicht): kein Hinweis mehr an den Artikeln, am Produkt bleibt er sichtbar."""
    rueckruf.beenden(ruid, json_body())
    return jsonify(rueckruf=rueckruf.rueckruf_json(rueckruf.rueckruf(ruid), mit_artikel=True))


@api.get("/rueckrufe")
@requires_zugang
def rueckrufe():
    """Alle laufenden Rückrufe mit Produkt und Zahlen aus dem eigenen Bereich – auch solche ohne betroffene Artikel
    darin."""
    return jsonify(rueckrufe=rueckruf.uebersicht(nur_bestand=False))
