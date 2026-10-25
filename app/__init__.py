"""strömis.de – Übungsobjekte, Übungsgewässer und Wiki für die Strömungsrettung."""
import logging
import os
import random
import secrets
import base64
import tempfile
import time
from datetime import date, timedelta
from urllib.parse import urlsplit

from flask import (Blueprint, Flask, Request, abort, current_app, g, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from . import api_admin, api_albums, api_pruefungen, api_wiki, auth, db, einstellungen, material, medienpflege
from .images import AVATAR_MAX_BYTES, EMBED_EXT, VIDEO_EXT


def _env_bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _idna(host):
    """Hostnamen mit Umlaut in die Punycode-Form bringen, wie sie im Host-Header ankommt."""
    host = (host or "").strip().lower().split(":")[0]
    try:
        return host.encode("idna").decode()
    except UnicodeError:
        return host


class PublicHostMiddleware:
    """Anfragen an die Wiki-Subdomain landen im öffentlichen Bereich (/oeffentlich/…).
    API, Medien und statische Dateien bleiben unverändert erreichbar."""

    def __init__(self, wsgi, app):
        self.wsgi, self.app = wsgi, app

    def __call__(self, environ, start_response):
        # Den Namen bei jeder Anfrage frisch aus der Konfiguration lesen, nicht beim Bauen
        # einmal festhalten: Sonst ließe sich der öffentliche Hostname zwar in den Einstellungen
        # ändern, bliebe aber bis zum nächsten Neustart wirkungslos.
        host = self.app.config.get("PUBLIC_HOST") or ""
        req_host = _idna(environ.get("HTTP_X_FORWARDED_HOST") or environ.get("HTTP_HOST", ""))
        path = environ.get("PATH_INFO", "/")
        if host and req_host == host and not path.startswith(("/static/", "/media/", "/api/", "/oeffentlich")):
            environ["PATH_INFO"] = "/oeffentlich" + (path if path != "/" else "/")
        return self.wsgi(environ, start_response)


def _load_secret(data_dir):
    """Sitzungsschlüssel laden oder einmalig erzeugen. Gunicorn startet die App in jedem Worker
    getrennt – der Schlüssel wird deshalb erst vollständig in eine Nebendatei geschrieben und
    dann per hartem Link unter seinen endgültigen Namen gehängt. So sieht ein zweiter Worker
    entweder gar keine Datei oder einen fertigen Schlüssel, aber nie eine halb geschriebene –
    sonst liefen zwei Worker mit verschiedenen Schlüsseln und die Anmeldung ginge sporadisch verloren."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = os.path.join(data_dir, "secret_key")
    for versuch in range(10):
        try:
            with open(path) as fh:
                key = fh.read().strip()
            if key:
                return key
        except FileNotFoundError:
            key = secrets.token_urlsafe(48)
            fd, tmp = tempfile.mkstemp(dir=data_dir)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w") as fh:
                    fh.write(key)
                    fh.flush()
                    os.fsync(fh.fileno())
                try:
                    os.link(tmp, path)
                    return key
                except FileExistsError:
                    pass             # ein anderer Worker war schneller – dessen Schlüssel gilt
            finally:
                os.unlink(tmp)
        time.sleep(0.05 * (versuch + 1))
    raise RuntimeError(f"Sitzungsschlüssel {path} konnte nicht angelegt werden.")


pages = Blueprint("pages", __name__)


@pages.get("/")
@auth.page_login_required
def index():
    """Startseite ist das Wiki – oder das erste Modul, das die Rechte-Matrix dem Konto öffnet. Ohne jedes Modul der
    Lesemodus des Wikis (die öffentlichen Seiten) statt einer Sackgasse; ein Modul mit eigener Stufe geht ihm vor.
    Das Modul Material öffnet sich nur mit Stufe UND Namen (rechte.zugang) – ein namenloses Konto von früher landete
    sonst auf der Fehlerseite des Moduls."""
    if auth.nutzt("wiki"):
        return render_template("wiki.html", user=auth.current_user(), slug="")
    from .material.services import rechte as mat_rechte
    for modul, ziel in (("karte", "/karte"), ("pruefungen", "/pruefungen"), ("material", "/material"),
                        ("verwaltung", "/admin")):
        if mat_rechte.zugang() if modul == "material" else auth.nutzt(modul):
            return redirect(ziel)
    if auth.wiki_lesemodus():
        return redirect(url_for("pages.wiki"))
    # Mit Kopfleiste (user): Profil und Abmelden bleiben erreichbar – ohne sie saß man auf der Fehlerseite fest.
    return render_template("error.html", user=auth.current_user(), code=403, message="Für dein Konto ist noch kein "
                           "Bereich freigeschaltet. Bitte wende dich an die Verwaltung."), 403


@pages.get("/karte")
@auth.page_modul_required("karte")
def karte():
    return render_template("index.html", user=auth.current_user())


def _wiki(slug):
    """Mitglied und Verwaltung bekommen das Wiki. Ein Konto ohne Stufe im Wiki bekommt den Lesemodus: genau die Seiten,
    die der öffentliche Teil zeigt, unter der eigenen Kopfleiste. Die Vorlage lädt dafür den Leser des öffentlichen
    Teils (public.js), der nur /api/public abfragt. Was „öffentlich“ ist, entscheidet so weiter eine Stelle
    (api_wiki.is_public), und keine interne Schnittstelle musste dafür aufgehen – die bleiben bei wiki_required."""
    if auth.nutzt("wiki"):
        return render_template("wiki.html", user=auth.current_user(), slug=slug)
    if auth.wiki_lesemodus():
        return render_template("wiki_lesemodus.html", user=auth.current_user(), slug=slug)
    abort(403)


@pages.get("/wiki")
@auth.page_login_required
def wiki():
    return _wiki("")


@pages.get("/wiki/<slug>")
@auth.page_login_required
def wiki_page(slug):
    return _wiki(slug)


# --- Öffentliches Wiki (ohne Login; unter der Subdomain wiki.* oder unter /oeffentlich) ---------

@pages.get("/oeffentlich/")
def public_index():
    return render_template("public.html", slug="")


@pages.get("/oeffentlich/<slug>")
def public_page(slug):
    return render_template("public.html", slug=slug)


def _slide_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="login-slideshow")


@pages.get("/api/public/slideshow")
def slideshow():
    """Zufällige Bilder aus den Spots für die Anmeldeseite – als signierte, 24 h gültige Links."""
    if not current_app.config["LOGIN_SLIDESHOW"]:
        return jsonify(images=[])
    # Ohne Anmeldung gibt es nur die Bilder selbst – Albumtitel wären sonst durch wiederholtes Abrufen auslesbar.
    # Und je Tag dieselbe Auswahl statt neuer Zufall je Aufruf: Wer die Adresse in Schleife abriefe,
    # bekäme sonst nach und nach den ganzen Bestand ohne Anmeldung. Zwölf Bilder am Tag sind das
    # Schaufenster, nicht die Sammlung.
    rows = db.query("SELECT file FROM photos WHERE kind = 'image' ORDER BY id")
    wahl = random.Random(f"{current_app.config['SECRET_KEY']}:{date.today().isoformat()}")
    rows = wahl.sample(rows, min(12, len(rows)))
    ser = _slide_serializer()
    key = lambda f: os.path.splitext(f)[0] + ".jpg"  # noqa: E731
    return jsonify(images=[{"url": "/media/slide/" + ser.dumps(key(r["file"]))} for r in rows])


_STRICT_MEDIA_CSP = "default-src 'none'; img-src 'self' data:; media-src 'self'; sandbox"
# Gilt nur für hochgeladene HTML-Bausteine (EMBED_EXT in images.py; nur Redakteur/Admin dürfen sie
# einstellen, siehe api_wiki.upload_file). "sandbox allow-scripts" ohne "allow-same-origin" heißt:
# der Inhalt darf sein eigenes Skript ausführen (sonst bliebe vom Einbetten nichts übrig), läuft
# dabei aber in einem eigenen, nicht wiederverwendbaren Ursprung – kein Zugriff auf Cookies,
# Sitzung oder DOM dieser Seite, keine Top-Level-Navigation, keine Popups. Das gilt auch dann,
# wenn die Adresse direkt aufgerufen wird, nicht nur innerhalb der <iframe sandbox="allow-scripts">,
# mit der der Artikel sie einbettet (siehe markdown.js/wiki.js, EMBED_RE).
_EMBED_CSP = "sandbox allow-scripts"


def _media_response(directory, filename, max_age, private, csp=None):
    """Mediendatei ausliefern. Angemeldeten-Inhalte dürfen nur im Browser des Nutzers liegen,
    nicht in einem gemeinsamen Zwischenspeicher. Skripte sind in Medien grundsätzlich nicht
    erwünscht – die eigene CSP macht auch ein direkt aufgerufenes SVG harmlos; die eine bewusste
    Ausnahme ist der HTML-Baustein (csp=_EMBED_CSP, siehe media())."""
    resp = send_from_directory(directory, filename, max_age=max_age)
    if private:
        resp.cache_control.public = None
        resp.cache_control.private = True
    resp.headers["Content-Security-Policy"] = csp or _STRICT_MEDIA_CSP
    return resp


@pages.get("/media/slide/<token>")
def slide(token):
    try:
        name = _slide_serializer().loads(token, max_age=60 * 60 * 24)
    except BadSignature:
        abort(404)
    return _media_response(os.path.join(current_app.config["MEDIA_DIR"], "web"), name, 3600, private=True)


@pages.get("/profil")
@auth.page_login_required
def profile():
    u = auth.current_user()
    # Modul Material: Ob die Urkundennummer gilt, entscheidet rechte.py – das Profil zeigt einem Prüfer ohne gültige
    # Nummer den Hinweis, dass er erst danach prüfen kann. Den Abschnitt „Unterschrift“ gibt es mit Zugang zum Modul für
    # Prüfer und wer neu unterschreiben darf (darf_unterschreiben – wer festschreibt oder aussondert, auch ein Materialwart
    # mit Stufe Mitglied, der über seine Freigabe verwaltet); ist schon eine hinterlegt, immer – auch ohne Zugang, dann
    # nur zum Entfernen.
    # Abschnitt „Meine PSA“ (Phase 3 · L1): mit Zuordnung oder abbestellten Erinnerungen – so lässt sich eine Abmeldung
    # auch ohne Zuordnung zurücknehmen.
    from .material.services import psa as mat_psa
    from .material.services import rechte as mat_rechte
    mat_zugang, mat_unterschrift = mat_rechte.zugang(u), mat_rechte.darf_unterschreiben(u)
    return render_template("profil.html", user=u, avatar=auth.avatar_url(u.get("avatar") or ""),
                           initialen=auth.initialen(u.get("name") or u["email"]), darf_pruefen=mat_rechte.ist_pruefer(u),
                           mat_zugang=mat_zugang, mat_unterschrift=mat_unterschrift,
                           psa_anzahl=mat_psa.anzahl(u["id"]) if mat_psa.konto(u) else 0,
                           psa_mails=bool(u["mat_psa_mails"]),
                           mat_abschnitt=bool((mat_zugang and (u["mat_pruefer"] or mat_unterschrift))
                                              or u.get("signature_png")))


@pages.get("/admin")
@auth.page_login_required
def admin():
    if not auth.is_admin():
        abort(403)
    return render_template("admin.html", user=auth.current_user())


# --- Prüfungen: nur für Nutzer mit dem Zusatzrecht „Prüfer“ -------------------------------------
# Der Bereich hat drei Ansichten unter einer Seite: die Lehrgangsliste, ein Lehrgang mit seinen
# Reitern und eine druckfreundliche Mängelübersicht. Was zu zeigen ist, liest das JavaScript aus
# den Datenattributen; das Recht prüft jede Route selbst – ein ausgeblendeter Reiter ist kein Schutz.

def _pruefungen_seite(ansicht, lehrgang_id=None, katalog_id=None):
    if not auth.is_pruefer():
        abort(403)
    return render_template("pruefungen.html", user=auth.current_user(), ansicht=ansicht,
                           lehrgang_id=lehrgang_id, katalog_id=katalog_id)


@pages.get("/pruefungen")
@auth.page_login_required
def pruefungen():
    return _pruefungen_seite("liste")


# Kataloge sind kein Lehrgang – eigene, wortgleiche Routen (nicht unter <int:lid>, sonst gäbe es
# einen Lehrgang mit der Nummer „kataloge“ nie zu sehen). Vor der <int:lid>-Route eingetragen ist
# das nicht nötig: Flasks Konverter lässt „kataloge“ dort ohnehin nie durch.
@pages.get("/pruefungen/kataloge")
@auth.page_login_required
def pruefungen_kataloge():
    return _pruefungen_seite("kataloge")


@pages.get("/pruefungen/kataloge/<int:kid>")
@auth.page_login_required
def pruefungen_katalog(kid):
    return _pruefungen_seite("katalog", katalog_id=kid)


@pages.get("/pruefungen/<int:lid>")
@auth.page_login_required
def pruefungen_lehrgang(lid):
    return _pruefungen_seite("lehrgang", lid)


@pages.get("/pruefungen/<int:lid>/druck")
@auth.page_login_required
def pruefungen_druck(lid):
    return _pruefungen_seite("druck", lid)


@pages.get("/media/pruefung/<kind>/<path:filename>")
def pruefung_media(kind, filename):
    """Bilder und Videos zu Prüfungen. Sie zeigen Teilnehmende – also nur an Prüfer, und nie in
    einen gemeinsamen Zwischenspeicher. Der Weg liegt außerhalb von /media/<kind>/, damit die
    allgemeine Medienroute (jeder Angemeldete) hier nicht greift."""
    if kind not in ("orig", "web", "thumb", "avatar"):
        abort(404)
    if not auth.current_user():
        abort(401)
    if not auth.is_pruefer():
        abort(403)
    wurzel = os.path.join(current_app.config["MEDIA_DIR"], "pruefungen", kind)
    return _media_response(wurzel, filename, 60 * 60, private=True)


def _safe_next(value):
    """Nur seiteneigene Ziele zulassen – „//fremde.seite“ wäre eine offene Weiterleitung.
    Browser lesen den Rückstrich wie einen Schrägstrich („/\\fremde.seite“) und werfen führende
    Steuerzeichen vor dem Auswerten weg – beides muss deshalb ebenfalls scheitern."""
    v = value or ""
    if "\\" in v or any(c < " " or c == "\x7f" for c in v):
        return "/"
    return v if v.startswith("/") and not v.startswith("//") else "/"


def _auth_page(mode):
    if auth.current_user() and mode in ("login", "register"):
        return redirect(url_for("pages.index"))
    # Der Reset-Token steht im Fragment der Adresse und erreicht den Server nie – ihn liest auth.js.
    return render_template("login.html", mode=mode, next=_safe_next(request.args.get("next")),
                           allow_registration=current_app.config["ALLOW_REGISTRATION"])


# Jede Seite braucht eine eigene View-Funktion: mehrere Routen auf einer Funktion
# ergeben denselben Endpunkt, und url_for() würde dann die falsche Adresse bauen.
@pages.get("/login")
def login():
    return _auth_page("login")


@pages.get("/register")
def register():
    return _auth_page("register")


@pages.get("/forgot")
def forgot():
    return _auth_page("forgot")


@pages.get("/reset")
def reset():
    return _auth_page("reset")


@pages.get("/media/<kind>/<path:filename>")
def media(kind, filename):
    if kind not in ("orig", "web", "thumb", "wiki", "avatar"):
        abort(404)
    wurzel = os.path.join(current_app.config["MEDIA_DIR"], kind)
    # Ein Bestandsvideo, das inzwischen gewandelt ist, liegt unter neuer Endung. Alte Adressen –
    # aus einem gerade offenen Editor, einer Fassung im Verlauf, einem Lesezeichen – führen
    # weiter zum Film.
    # safe_join statt os.path.join: Ohne das verriete die Probe auch ohne Anmeldung, ob eine
    # Datei außerhalb des Verzeichnisses existiert (".. %2f"-Pfade). safe_join gibt dafür None.
    gesucht = safe_join(wurzel, filename)
    if kind in ("orig", "wiki") and gesucht and not os.path.isfile(gesucht):
        basis, ext = os.path.splitext(filename)
        ziel = safe_join(wurzel, basis + ".mp4")
        if ext.lower() in VIDEO_EXT and ziel and os.path.isfile(ziel):
            filename = basis + ".mp4"
    public = kind == "wiki" and api_wiki.file_is_public(filename)
    if not public and not auth.current_user():
        # Anhänge öffentlicher Wiki-Seiten dürfen ohne Login geladen werden
        abort(401)
    # Medien gehören zu ihrem Modul: Bilder der Spots nur mit Zugang zu den Spots, Artikeldateien
    # nur mit Zugang zum Wiki (oder öffentlich). Profilbilder sieht jeder Angemeldete.
    if kind in ("orig", "web", "thumb") and not auth.nutzt("karte"):
        abort(403)
    if kind == "wiki" and not public and not auth.nutzt("wiki"):
        abort(403)
    # Ein Profilbild ist eine Angabe zur Person: Wer es entfernt, soll es nicht wochenlang aus
    # dem eigenen Zwischenspeicher weiterbekommen. Eine Stunde genügt, um die Autorenzeilen
    # eines Rundgangs durchs Wiki abzudecken. Öffentliche Anhänge einen Tag: Die dürfen in
    # gemeinsamen Zwischenspeichern liegen, und eine zurückgenommene Freigabe soll dort nicht
    # wochenlang nachwirken.
    dauer = 60 * 60 if kind == "avatar" else 60 * 60 * 24 if public else 60 * 60 * 24 * 30
    csp = _EMBED_CSP if kind == "wiki" and os.path.splitext(filename)[1].lower() in EMBED_EXT else None
    return _media_response(wurzel, filename, dauer, private=not public, csp=csp)


@pages.get("/healthz")
def healthz():
    return jsonify(ok=True)


class _Anfrage(Request):
    """Hochgeladene Dateien, die Werkzeug nicht mehr im Speicher hält, landen auf dem Datenvolumen
    (TMP_DIR) statt im Wurzeldateisystem des Containers. Dort wäre ein 5-GB-Film zweimal unterwegs
    – einmal als Zwischendatei, einmal am Ziel –, und der Platz ist dafür nicht bemessen."""

    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        return tempfile.SpooledTemporaryFile(max_size=500 * 1024, mode="rb+", dir=current_app.config["TMP_DIR"])


def _kachel_quellen(cfg):
    """Herkünfte der Kartenkacheln für die CSP – aus denselben Einstellungen, die die Karte benutzt.
    Leaflets Platzhalter {s} (Subdomains) wird zum Jokerzeichen. Alles andere an fremden Bildern
    bleibt draußen: Ein Bild von einer fremden Adresse meldete dieser bei jedem Aufruf, wer die
    Seite liest – auch im öffentlichen Wiki."""
    quellen = []
    for schluessel in ("TILE_URL", "SAT_URL", "SAT_LABELS_URL", "TOPO_URL"):
        for adresse in str(cfg.get(schluessel) or "").split(","):
            adresse = adresse.strip().replace("{s}.", "*.")
            if not adresse:
                continue
            try:
                teile = urlsplit(adresse)
            except ValueError:
                continue
            if teile.scheme in ("http", "https") and teile.netloc:
                quelle = f"{teile.scheme}://{teile.netloc}"
                if quelle not in quellen:
                    quellen.append(quelle)
    return " ".join(quellen)


def create_app():
    data_dir = os.environ.get("DATA_DIR", "/data")
    media_dir = os.path.join(data_dir, "media")
    os.makedirs(media_dir, exist_ok=True)
    # Zwischendateien auf dem Datenvolumen: große Upload-Teile (siehe _Anfrage) und der ZIP-Export.
    tmp_dir = os.path.join(data_dir, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.request_class = _Anfrage
    app.config.update(
        TMP_DIR=tmp_dir,
        SECRET_KEY=_load_secret(data_dir),
        DATA_DIR=data_dir,
        MEDIA_DIR=media_dir,
        DB_PATH=os.path.join(data_dir, "stroemis.db"),
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_MB", "5120")) * 1024 * 1024,
        MAX_REQUEST_LENGTH=int(os.environ.get("MAX_REQUEST_MB", "1")) * 1024 * 1024,
        MAX_REVISIONS=int(os.environ.get("WIKI_MAX_REVISIONS", "100")),
        # Wiki-Import (ZIP): eine eigene Grenze – der Import läuft in einer Anfrage, Videos nimmt er nicht mit.
        WIKI_IMPORT_MAX_BYTES=int(os.environ.get("WIKI_IMPORT_MB", "200")) * 1024 * 1024,
        SITE_NAME=os.environ.get("SITE_NAME", "strömis.de"),
        # Absender des Umschlags (Return-Path). Leer = die Adresse aus MAIL_FROM; dann liegen
        # Umschlag und From auf derselben Domain, wie DMARC es verlangt.
        SMTP_ENVELOPE_FROM=os.environ.get("SMTP_ENVELOPE_FROM", ""),
        ADMIN_NOTIFY_EMAIL=os.environ.get("ADMIN_NOTIFY_EMAIL", ""),
        LOGIN_SLIDESHOW=_env_bool("LOGIN_SLIDESHOW", True),
        SPRACHEINGABE=_env_bool("SPRACHEINGABE", True),     # Diktat an den Kommentarfeldern der Prüfungen
        # Modul Material: Ab wie vielen Tagen vor der Fälligkeit ein Artikel „bald fällig“ heißt.
        MATERIAL_BALD_FAELLIG_TAGE=int(os.environ.get("MATERIAL_BALD_FAELLIG_TAGE", "30")),
        # Modul Material: Erinnerungsmails an die Materialwarte (täglich ab 6 Uhr). Vorgabe aus – eingeschaltet wird in
        # der Produktion unter Verwaltung → Einstellungen; MATERIAL_ERINNERUNGEN_SPERRE (nur Umgebung) sperrt hart.
        MATERIAL_ERINNERUNGEN=_env_bool("MATERIAL_ERINNERUNGEN", False),
        PUBLIC_HOST=_idna(os.environ.get("PUBLIC_HOST", "wiki.strömis.de")),
        PUBLIC_URL=os.environ.get("PUBLIC_URL", "https://wiki.strömis.de").rstrip("/"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_env_bool("COOKIE_SECURE", True),
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        BASE_URL=os.environ.get("BASE_URL", "https://strömis.de"),
        ALLOW_REGISTRATION=_env_bool("ALLOW_REGISTRATION", True),
        ADMIN_EMAIL=os.environ.get("ADMIN_EMAIL", ""),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),
        SMTP_HOST=os.environ.get("SMTP_HOST", ""),
        SMTP_PORT=os.environ.get("SMTP_PORT", ""),
        SMTP_USER=os.environ.get("SMTP_USER", ""),
        SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
        SMTP_SSL=_env_bool("SMTP_SSL", False),
        SMTP_STARTTLS=_env_bool("SMTP_STARTTLS", True),
        MAIL_FROM=os.environ.get("MAIL_FROM", "strömis.de <noreply@xn--strmis-yxa.de>"),
        MAP_CENTER=os.environ.get("MAP_CENTER", "51.0,10.4"),
        MAP_ZOOM=int(os.environ.get("MAP_ZOOM", "6")),
        TILE_URL=os.environ.get("TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
        # "or": Eine leer gesetzte Variable soll die Vorgabe nicht abschalten, sondern auf sie
        # zurückfallen – so steht es auch in .env.example. Ohne das verschwände der Rechtehinweis,
        # den OpenStreetMap und Esri verlangen, sobald jemand die Zeile leer stehen lässt.
        TILE_ATTRIBUTION=os.environ.get("TILE_ATTRIBUTION")
        or '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende',
        # Luftbild: Stege, Slipstellen, Kiesbänke und Wehre sind darauf zu erkennen, auf der
        # Straßenkarte nicht – deshalb ist es die Startebene. Esri verlangt die Namensnennung.
        # Achtung: Esri ordnet die Kacheln {z}/{y}/{x}, nicht {z}/{x}/{y} wie OpenStreetMap.
        # Adresssuche beim Platzieren von Bildern. Leeren schaltet sie ab; wer viel sucht,
        # trägt hier eine eigene Nominatim-Adresse ein (die öffentliche erlaubt eine Anfrage
        # je Sekunde und keine Massenabfragen).
        GEOCODE_URL=os.environ.get("GEOCODE_URL", "https://nominatim.openstreetmap.org/search"),
        SAT_URL=os.environ.get(
            "SAT_URL",
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        # Beschriftung über dem Luftbild: Straßen mit Namen, Orts- und Gewässernamen – ohne sie
        # ist ein Luftbild zur Orientierung mühsam. Mehrere Ebenen durch Komma getrennt, von
        # unten nach oben gestapelt. Leeren schaltet die Beschriftung ab.
        SAT_LABELS_URL=os.environ.get(
            "SAT_LABELS_URL",
            "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x},"
            "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"),
        SAT_ATTRIBUTION=os.environ.get("SAT_ATTRIBUTION")
        or 'Luftbilder: &copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics',
        TOPO_URL=os.environ.get("TOPO_URL", "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"),
        TOPO_ATTRIBUTION=os.environ.get("TOPO_ATTRIBUTION")
        or ('Kartendaten: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, SRTM | '
            'Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)'),
    )
    app.json.ensure_ascii = False
    app.wsgi_app = PublicHostMiddleware(ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1), app)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db.init_app(app)
    # Das Modul Material bringt Schema, Blueprints und Kommandozeile selbst mit; es meldet seine
    # Migration an, bevor die Datenbank eingerichtet wird.
    material.init_app(app)
    with app.app_context():
        new_tables = db.init_db()
        if new_tables & {"wiki_page_files", "wiki_page_links"}:
            # einmalig: Anhänge und Seitenverweise vorhandener Seiten zuordnen
            api_wiki.backfill_page_files()
        auth.ensure_admin()
    # Was jetzt in der Konfiguration steht, kommt aus Umgebung und Vorgaben. Diese Kopie ist die
    # Grundlage für "zurück auf die Vorgabe" – danach liegen die gespeicherten Werte darüber.
    einstellungen.grundstand_merken(app)
    einstellungen.beim_start_anwenden(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(api_albums.bp)
    app.register_blueprint(api_wiki.bp)
    app.register_blueprint(api_wiki.public_bp)
    app.register_blueprint(api_admin.bp)
    app.register_blueprint(api_pruefungen.bp)
    app.register_blueprint(pages)

    # Bestandsvideos, die noch nicht jeder Browser abspielt, werden im Hintergrund gewandelt.
    medienpflege.starten(app)

    # Offizielle DLRG-Wortmarke (SVG aus dem DLRG-Downloadbereich) wird verwendet, sobald sie vorliegt.
    app.config["WORTMARKE"] = os.path.exists(os.path.join(app.static_folder, "img", "dlrg-wortmarke.svg"))
    # Eigenes Zeichen der Gliederung: Liegt eine Datei "img/maskottchen.<endung>" bereit, steht
    # sie in Kopfzeile und Anmeldung anstelle des Schriftzugs. Fehlt sie, bleibt alles wie bisher –
    # so lässt sich das Bild austauschen, ohne eine Zeile Code anzufassen.
    app.config["MASKOTTCHEN"] = next(
        (f"img/{n}" for n in ("maskottchen.webp", "maskottchen.png", "maskottchen.jpg", "maskottchen.svg")
         if os.path.exists(os.path.join(app.static_folder, "img", n))), "")

    # Was jede Route höchstens entgegennimmt. Nicht aufgeführt heißt: die enge Grenze für
    # gewöhnliche Aufrufe. Das Profilbild braucht mehr als die – eine Aufnahme vom Telefon hat
    # mehrere Megabyte –, aber längst nicht so viel wie ein Film, und die Grenze muss greifen,
    # bevor irgendetwas gepuffert wird.
    # Welche Route die große Grenze bekommt – die Zahl selbst wird bei jeder Anfrage frisch
    # gelesen, sonst bliebe eine in den Einstellungen geänderte Grenze bis zum Neustart wirkungslos.
    GROSSE_UPLOADS = ("albums.upload_photos", "albums.einwurf", "wiki.upload_file", "pruefungen.upload_medien")
    # Eine Excel-Teilnehmerliste hat einige hundert Kilobyte; sie wird vollständig in den Speicher
    # gelesen. Die Filmgrenze wäre hier eine Einladung, den Arbeitsprozess mit Gigabytes zu füllen.
    IMPORT_MAX_BYTES = 25 * 1024 * 1024
    IMPORT_ROUTEN = ("pruefungen.import_vorschau", "pruefungen.import_uebernehmen")
    # Modul Material: Produkt- und Ordnerfotos, Herstellerdokumente – eigene, feste Grenzen.
    MATERIAL_UPLOADS = material.upload_grenzen()

    @app.before_request
    def einstellungen_anwenden():
        """Die im Browser gesetzten Werte über die Konfiguration legen.

        Muss vor allem anderen laufen: size_guard liest MAX_REQUEST_LENGTH, die Seiten lesen
        SITE_NAME, der Mailversand die SMTP-Angaben. Statische Dateien und Medien bleiben außen
        vor – eine Bilddatei soll keine Datenbankabfrage kosten."""
        if not einstellungen.ist_statisch():
            einstellungen.anwenden()

    @app.before_request
    def size_guard():
        """MAX_CONTENT_LENGTH gilt prozessweit und muss wegen der Uploads riesig sein. Überall
        sonst genügt ein enges Limit, sonst puffert der Server auch für einen anonymen Aufruf
        gigabyteweise Daten, bevor überhaupt eine Prüfung greift."""
        if request.endpoint in ("auth.set_avatar", "pruefungen.upload_tn_bild"):
            limit = AVATAR_MAX_BYTES
        elif request.endpoint in MATERIAL_UPLOADS:
            limit = MATERIAL_UPLOADS[request.endpoint]
        elif request.endpoint in IMPORT_ROUTEN:
            limit = IMPORT_MAX_BYTES
        elif request.endpoint == "wiki.import_pages":
            limit = app.config["WIKI_IMPORT_MAX_BYTES"]
        elif request.endpoint in GROSSE_UPLOADS:
            limit = app.config["MAX_CONTENT_LENGTH"]
        else:
            limit = app.config["MAX_REQUEST_LENGTH"]
        # Eine Anfrage ohne Content-Length (Transfer-Encoding: chunked) trägt keine Länge – und
        # wurde sonst bis zur prozessweiten Filmgrenze in den Arbeitsspeicher gelesen, auch ohne
        # Anmeldung. Browser schicken die Länge immer mit; wer sie weglässt, bekommt 411. Dazu die
        # Grenze am Datenstrom selbst: Werkzeug liest dann in keinem Fall mehr als diese Zahl.
        if request.content_length is None and request.headers.get("Transfer-Encoding"):
            return jsonify(error="Diese Anfrage braucht eine Content-Length-Kopfzeile."), 411
        request.max_content_length = limit
        if (request.content_length or 0) > limit:
            return jsonify(error="Die gesendeten Daten sind zu groß (Grenze: "
                                 f"{limit // (1024 * 1024)} MB)."), 413

    @app.before_request
    def csrf_guard():
        """Schreibende API-Aufrufe nur aus eigenem JavaScript: JSON-Body oder X-Requested-With.
        Zusammen mit SameSite=Lax-Cookies schließt das Cross-Site-Request-Forgery aus."""
        g.csp_nonce = base64.b64encode(secrets.token_bytes(12)).decode()
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
            site = request.headers.get("Sec-Fetch-Site")
            if site and site not in ("same-origin", "none"):
                return jsonify(error="Anfrage von fremder Seite abgelehnt."), 403
            ctype = (request.content_type or "").split(";")[0].strip().lower()
            if ctype != "application/json" and request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return jsonify(error="Anfrage abgelehnt (X-Requested-With fehlt)."), 403

    @app.after_request
    def security_headers(resp):
        nonce = getattr(g, "csp_nonce", "")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Mikrofon nur für die eigene Seite: das Diktat der Prüfungen (Web Speech API) braucht es.
        resp.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(self)")
        resp.headers.setdefault(
            "Content-Security-Policy",
            f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: blob: {_kachel_quellen(app.config)}; media-src 'self' blob:; "
            "font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'self'; form-action 'self'; base-uri 'self'; object-src 'none'")
        return resp

    @app.context_processor
    def inject():
        # material_zugang: der Reiter „Material“ der Kopfleiste nur, wenn sich das Modul auch öffnet (Stufe und Name,
        # ohne Abfrage) – rechte.material allein zeigte ihn einem namenlosen Konto, das dort nur 403 bekäme.
        # meine_psa: der Eintrag „Meine PSA“ für Konten mit Zuordnung, die nirgends im Bestand lesen dürfen (Phase 3 ·
        # L1) – eine Abfrage über den Index der Zuordnung, die Sicht nur mit Zuordnung und Modulzugang.
        from .material.services.psa import kopfleiste as material_psa
        from .material.services.rechte import zugang as material_zugang
        return {"cfg": app.config, "is_admin": auth.is_admin(), "is_pruefer": auth.is_pruefer(),
                "meine_psa": material_psa() if auth.current_user() else 0,
                "rechte": auth.rechte_von(auth.current_user()) if auth.current_user() else {},
                "wiki_lesemodus": auth.wiki_lesemodus(),
                "material_zugang": material_zugang(),
                "csp_nonce": getattr(g, "csp_nonce", "")}

    @app.errorhandler(413)
    def too_large(_e):
        # Die Grenze der Route (size_guard), nicht die prozessweite: Sonst stünde bei einem zu großen
        # JSON-Aufruf „5120 MB“ in der Meldung.
        grenze = request.max_content_length or app.config["MAX_CONTENT_LENGTH"]
        return jsonify(error=f"Die gesendeten Daten sind zu groß (Grenze: {grenze // (1024 * 1024)} MB)."), 413

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Nicht gefunden"), 404
        # Eine fehlende Mediendatei hängt in einem <img> – dort wäre eine vollständige
        # Fehlerseite als Antwort nur Ballast, einmal je Bild.
        if request.path.startswith("/media/"):
            return "", 404
        return render_template("error.html", user=auth.current_user(), code=404, message="Diese Seite gibt es nicht."), 404

    @app.errorhandler(403)
    def forbidden(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Keine Berechtigung"), 403
        return render_template("error.html", user=auth.current_user(), code=403, message="Dafür fehlt die Berechtigung."), 403

    @app.errorhandler(401)
    def unauthorized(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Nicht angemeldet"), 401
        return redirect(url_for("pages.login", next=request.path))

    return app
