"""strömis.de als installierbare Web-App (PWA, Wunsch vom 28.10.2026, Punkt 1; Entscheidungen vom 01.11.2026).

Drei Adressen am Ursprung „/“, ohne Anmeldung und ohne Datenbank:
  /manifest.webmanifest  Name, Symbole, Farben, Kurzbefehle – auf dev („-dev“, module.dev_umgebung) mit eigenem Namen
                         und Symbol mit der Marke „dev“, damit beide Apps auf einem Telefon zu unterscheiden sind.
  /sw.js                 der Service Worker (Quelle app/static/js/sw.js) mit Versionsstempel; Geltungsbereich „/“.
  /offline               die Hinweisseite ohne Netz – das EINZIGE, was der Worker zwischenspeichert (Entscheidung „ohne
                         Netz nur eine Hinweisseite“: nichts Angemeldetes, keine Seiten, keine Antworten der
                         Schnittstelle, keine Medien). Sie hat keine Mittel: Stil, Zeichen und Knopf stehen in ihr selbst.

Die Symbole liegen fertig unter static/img/pwa/ (erzeugt mit scripts/pwa_symbole.py aus dem Maskottchen, siehe README
„Als App installieren“). Die öffentliche Strömipedia (wiki.strömis.de) verweist nicht auf das Manifest: Dort leitet
PublicHostMiddleware jede Adresse nach /oeffentlich/ – eine eigene Installation der öffentlichen Seiten ist nicht
vorgesehen (Wunsch Punkt 1: „eigene Installation nicht nötig“)."""
import base64
import hashlib
import json
import os

from flask import Blueprint, current_app, render_template

from . import module

bp = Blueprint("pwa", __name__)

SW_QUELLE = os.path.join(os.path.dirname(__file__), "static", "js", "sw.js")
OFFLINE_VORLAGE = os.path.join(os.path.dirname(__file__), "templates", "offline.html")
# Die Zeile in sw.js, die beim Ausliefern den Stand bekommt – steht dort genau so (Test).
STAND_ZEILE = 'const STAND = "entwicklung";'
# Farben aus app.css (:root): --rot für Leiste und Startbildschirm-Rand, --weiss für den Hintergrund beim Start.
FARBE_THEMA = "#e30613"
FARBE_GRUND = "#ffffff"


def _lesen(pfad, binaer=False):
    with open(pfad, "rb" if binaer else "r", **({} if binaer else {"encoding": "utf-8"})) as fh:
        return fh.read()


def _maskottchen_daten():
    """Das Zeichen der Kopfleiste als data:-Adresse für die Hinweisseite – sie lädt ohne Netz nichts nach. Ohne
    Maskottchen (anderes Zeichen der Gliederung, siehe create_app) bleibt die Seite ohne Bild."""
    datei = current_app.config.get("MASKOTTCHEN") or ""
    if not datei.endswith((".webp", ".png")):
        return ""
    pfad = os.path.join(current_app.static_folder, datei)
    art = "image/webp" if datei.endswith(".webp") else "image/png"
    return f"data:{art};base64," + base64.b64encode(_lesen(pfad, binaer=True)).decode()


def stand(app):
    """Versionsstempel des Workers: Prüfsumme über seine Quelle, die Hinweisseite und das Zeichen darin. Ändert sich
    eins davon (Deploy), ist /sw.js ein anderes Byte-Muster – der Browser holt den neuen Worker, legt die neue
    Hinweisseite ab und räumt die alte weg. Ändert sich nichts, bleibt der installierte Worker, wie er ist."""
    h = hashlib.sha256()
    h.update(_lesen(SW_QUELLE, binaer=True))
    h.update(_lesen(OFFLINE_VORLAGE, binaer=True))
    datei = app.config.get("MASKOTTCHEN") or ""
    if datei:
        h.update(_lesen(os.path.join(app.static_folder, datei), binaer=True))
    h.update(b"dev" if module.dev_umgebung() else b"")
    return h.hexdigest()[:16]


def _antwort(text, art, cache="no-cache"):
    resp = current_app.response_class(text, mimetype=art)
    resp.headers["Cache-Control"] = cache
    return resp


def manifest_daten():
    """Das Web-App-Manifest. Kurzbefehle zu allen fünf Modulen (einfachste Lösung, Auftrag vom 01.11.2026): Das
    Manifest ist für alle Konten gleich und wird ohne Anmeldung geladen; wer ein Modul nicht hat, landet auf der
    Fehlerseite, die den Bereich seines Kontos nennt."""
    dev = module.dev_umgebung()
    name = "strömis.de dev" if dev else "strömis.de"
    zusatz = "-dev" if dev else ""
    symbol = lambda groesse, zweck: {  # noqa: E731
        "src": f"/static/img/pwa/symbol{'-maskable' if zweck == 'maskable' else ''}-{groesse}{zusatz}.png",
        "sizes": f"{groesse}x{groesse}", "type": "image/png", "purpose": zweck}
    kurz = [{"name": module.NAME[m], "short_name": module.NAME[m],
             "url": "/" if m == "wiki" else module.PFAD[m],
             "icons": [{"src": f"/static/img/pwa/symbol-96{zusatz}.png", "sizes": "96x96", "type": "image/png"}]}
            for m in ("wiki", "karte", "pruefungen", "material", "verwaltung")]
    return {
        "id": "/",
        "name": name,
        "short_name": name,
        "description": "Strömungsrettung: Strömipedia, Ankerplätze, Riegenkarten, Materialablage und Leitstelle.",
        "lang": "de",
        "dir": "ltr",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "theme_color": FARBE_THEMA,
        "background_color": FARBE_GRUND,
        "prefer_related_applications": False,
        "icons": [symbol(192, "any"), symbol(512, "any"), symbol(192, "maskable"), symbol(512, "maskable")],
        "shortcuts": kurz,
    }


@bp.get("/manifest.webmanifest")
def manifest():
    # Einen Tag im Zwischenspeicher: Der Browser fragt es ohnehin selten neu ab; der Name ändert sich nie im Betrieb.
    return _antwort(json.dumps(manifest_daten(), ensure_ascii=False, indent=1), "application/manifest+json",
                    "public, max-age=86400")


@bp.get("/sw.js")
def service_worker():
    """Der Worker mit Versionsstempel. „no-cache“: Jede Prüfung auf eine neue Fassung fragt den Server (Browser
    umgehen den HTTP-Zwischenspeicher für Worker-Skripte ohnehin höchstens 24 Stunden lang). Liegt am Ursprung, also
    gilt er für „/“ – eine Kopfzeile Service-Worker-Allowed braucht es nicht."""
    quelle = _lesen(SW_QUELLE)
    text = quelle.replace(STAND_ZEILE, f'const STAND = "{current_app.config["PWA_STAND"]}";', 1)
    resp = _antwort(text, "text/javascript")
    resp.headers["Content-Type"] = "text/javascript; charset=utf-8"
    return resp


@bp.get("/offline")
def offline():
    """Die Hinweisseite ohne Netz. Der Worker legt sie bei der Installation ab und zeigt sie, wenn eine Seite nicht
    geladen werden kann. Ohne Anmeldung, ohne Kopfleiste mit Konto – sie steht für jeden Ursprung gleich im Speicher."""
    html = render_template("offline.html", maskottchen=_maskottchen_daten(), dev=module.dev_umgebung())
    return _antwort(html, "text/html")
