"""Der eingebaute Tageslauf des Moduls Material: ein Thread je Gunicorn-Arbeitsprozess, der alle 15 Minuten aufwacht und
ab 6 Uhr deutscher Zeit einmal am Tag services/erinnerung.tageslauf anstößt (Pflege und Erinnerungsmails). Keine
Arbeit auf dem Server nötig – kein cron im Container. Dass zwei Arbeitsprozesse, ein Neustart oder die Kommandozeile
(flask material remind) nie doppelt mahnen, regeln Tagesmarken, Herzschlag und das Log (erinnerung.py) – außer, wenn
ein Prozess genau zwischen der Annahme einer Mail und ihrem Vermerk endet; dann kommt diese eine Mail am nächsten
Morgen noch einmal.

Gestartet wird bei der ersten Anfrage, nicht in create_app: Kommandozeile, Skripte und Tests rufen create_app auch,
bedienen aber keine Anfragen – ein Thread dort könnte nach 6 Uhr den Tag belegen, während der Prozess gleich endet. Tests
setzen TESTING, dann startet nichts. Im Container kommt die erste Anfrage spätestens mit dem HEALTHCHECK."""
import random
import threading
import time

from flask import current_app

WACH_SEKUNDEN = 15 * 60
_gestartet = False
_sperre = threading.Lock()
_schlafen = time.sleep          # Tests ersetzen es


def anstossen():
    """before_request des Moduls: startet beim ersten Aufruf je Arbeitsprozess den Thread, danach nur ein Vergleich.
    Wirft nie: Ein Fehler beim Start (etwa „can't start new thread“) wird einmal geloggt und _gestartet trotzdem gesetzt
    – sonst versuchte es jede Anfrage erneut und endete mit 500."""
    global _gestartet
    if _gestartet:
        return
    try:
        app = current_app._get_current_object()
        if app.config.get("TESTING"):
            return
        with _sperre:
            if _gestartet:
                return
            _gestartet = True
            threading.Thread(target=_schleife, args=(app,), name="tageslauf", daemon=True).start()
    except Exception as exc:
        _gestartet = True
        try:
            current_app.logger.error("Tageslauf: Thread nicht gestartet – %s", exc)
        except Exception:
            pass


def _schleife(app):
    """Erst 60–180 s warten (Arbeitsprozesse versetzt), dann je Runde _einmal(app) und WACH_SEKUNDEN schlafen. Runde und
    Schlaf stehen je in try/except Exception, damit der Thread nie endet."""
    try:
        _schlafen(random.uniform(60, 180))
    except Exception:
        pass
    while True:
        try:
            _einmal(app)
        except Exception as exc:
            try:
                app.logger.error("Tageslauf: Runde gescheitert – %s", exc)
            except Exception:
                pass
        try:
            _schlafen(WACH_SEKUNDEN)
        except Exception:
            pass


def _einmal(app):
    """Eine Runde: die Einstellungen aus dem Browser über die Konfiguration legen (Schalter, Mailserver, BASE_URL und
    SITE_NAME wie in einer Anfrage – sonst gälte der Stand vom Start des Prozesses), dann erinnerung.tageslauf_versuchen.
    Ausnahmen werden geloggt."""
    from .. import einstellungen
    from .services import erinnerung
    with app.app_context():
        try:
            einstellungen.anwenden()
            return erinnerung.tageslauf_versuchen()
        except Exception as exc:
            app.logger.exception("Tageslauf: %s", exc)
            return None
