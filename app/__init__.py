"""strömis.de – Übungsobjekte, Übungsgewässer und Wiki für die Strömungsrettung."""
import logging
import os
import secrets
import base64
import tempfile
import time
from datetime import timedelta

from flask import (Blueprint, Flask, abort, current_app, g, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from . import api_admin, api_albums, api_wiki, auth, db, medienpflege
from .images import AVATAR_MAX_BYTES, VIDEO_EXT


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

    def __init__(self, wsgi, host):
        self.wsgi, self.host = wsgi, host

    def __call__(self, environ, start_response):
        req_host = _idna(environ.get("HTTP_X_FORWARDED_HOST") or environ.get("HTTP_HOST", ""))
        path = environ.get("PATH_INFO", "/")
        if self.host and req_host == self.host and not path.startswith(("/static/", "/media/", "/api/", "/oeffentlich")):
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
    """Startseite ist das Wiki."""
    return render_template("wiki.html", user=auth.current_user(), slug="")


@pages.get("/karte")
@auth.page_login_required
def karte():
    return render_template("index.html", user=auth.current_user())


@pages.get("/wiki")
@auth.page_login_required
def wiki():
    return render_template("wiki.html", user=auth.current_user(), slug="")


@pages.get("/wiki/<slug>")
@auth.page_login_required
def wiki_page(slug):
    return render_template("wiki.html", user=auth.current_user(), slug=slug)


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
    rows = db.query("SELECT file FROM photos WHERE kind = 'image' ORDER BY RANDOM() LIMIT 12")
    ser = _slide_serializer()
    key = lambda f: os.path.splitext(f)[0] + ".jpg"  # noqa: E731
    return jsonify(images=[{"url": "/media/slide/" + ser.dumps(key(r["file"]))} for r in rows])


def _media_response(directory, filename, max_age, private):
    """Mediendatei ausliefern. Angemeldeten-Inhalte dürfen nur im Browser des Nutzers liegen,
    nicht in einem gemeinsamen Zwischenspeicher. Skripte sind in Medien nie erwünscht –
    die eigene CSP macht auch ein direkt aufgerufenes SVG harmlos."""
    resp = send_from_directory(directory, filename, max_age=max_age)
    if private:
        resp.cache_control.public = None
        resp.cache_control.private = True
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; media-src 'self'; sandbox"
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
    return render_template("profil.html", user=u, avatar=auth.avatar_url(u.get("avatar") or ""),
                           initialen=auth.initialen(u.get("name") or u["email"]))


@pages.get("/admin")
@auth.page_login_required
def admin():
    if not auth.is_admin():
        abort(403)
    return render_template("admin.html", user=auth.current_user())


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
    # Ein Profilbild ist eine Angabe zur Person: Wer es entfernt, soll es nicht wochenlang aus
    # dem eigenen Zwischenspeicher weiterbekommen. Eine Stunde genügt, um die Autorenzeilen
    # eines Rundgangs durchs Wiki abzudecken.
    dauer = 60 * 60 if kind == "avatar" else 60 * 60 * 24 * 30
    return _media_response(wurzel, filename, dauer, private=not public)


@pages.get("/healthz")
def healthz():
    return jsonify(ok=True)


def create_app():
    data_dir = os.environ.get("DATA_DIR", "/data")
    media_dir = os.path.join(data_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(
        SECRET_KEY=_load_secret(data_dir),
        DATA_DIR=data_dir,
        MEDIA_DIR=media_dir,
        DB_PATH=os.path.join(data_dir, "stroemis.db"),
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_MB", "5120")) * 1024 * 1024,
        MAX_REQUEST_LENGTH=int(os.environ.get("MAX_REQUEST_MB", "1")) * 1024 * 1024,
        MAX_REVISIONS=int(os.environ.get("WIKI_MAX_REVISIONS", "100")),
        SITE_NAME=os.environ.get("SITE_NAME", "strömis.de"),
        ADMIN_NOTIFY_EMAIL=os.environ.get("ADMIN_NOTIFY_EMAIL", ""),
        LOGIN_SLIDESHOW=_env_bool("LOGIN_SLIDESHOW", True),
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
    app.wsgi_app = PublicHostMiddleware(ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1), app.config["PUBLIC_HOST"])

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db.init_app(app)
    with app.app_context():
        new_tables = db.init_db()
        if new_tables & {"wiki_page_files", "wiki_page_links"}:
            # einmalig: Anhänge und Seitenverweise vorhandener Seiten zuordnen
            api_wiki.backfill_page_files()
        auth.ensure_admin()

    app.register_blueprint(auth.bp)
    app.register_blueprint(api_albums.bp)
    app.register_blueprint(api_wiki.bp)
    app.register_blueprint(api_wiki.public_bp)
    app.register_blueprint(api_admin.bp)
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
    upload_limits = {
        "albums.upload_photos": app.config["MAX_CONTENT_LENGTH"],
        "albums.einwurf": app.config["MAX_CONTENT_LENGTH"],
        "wiki.upload_file": app.config["MAX_CONTENT_LENGTH"],
        "auth.set_avatar": AVATAR_MAX_BYTES,
    }

    @app.before_request
    def size_guard():
        """MAX_CONTENT_LENGTH gilt prozessweit und muss wegen der Uploads riesig sein. Überall
        sonst genügt ein enges Limit, sonst puffert der Server auch für einen anonymen Aufruf
        gigabyteweise Daten, bevor überhaupt eine Prüfung greift."""
        limit = upload_limits.get(request.endpoint, app.config["MAX_REQUEST_LENGTH"])
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
        resp.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=()")
        resp.headers.setdefault(
            "Content-Security-Policy",
            f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; media-src 'self' blob:; font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'self'; form-action 'self'; base-uri 'self'; object-src 'none'")
        return resp

    @app.context_processor
    def inject():
        return {"cfg": app.config, "is_admin": auth.is_admin(), "csp_nonce": getattr(g, "csp_nonce", "")}

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(error="Die gesendeten Daten sind zu groß (Grenze: "
                             f"{app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB)."), 413

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Nicht gefunden"), 404
        # Eine fehlende Mediendatei hängt in einem <img> – dort wäre eine vollständige
        # Fehlerseite als Antwort nur Ballast, einmal je Bild.
        if request.path.startswith("/media/"):
            return "", 404
        return render_template("error.html", code=404, message="Diese Seite gibt es nicht."), 404

    @app.errorhandler(403)
    def forbidden(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Keine Berechtigung"), 403
        return render_template("error.html", code=403, message="Dafür fehlt die Berechtigung."), 403

    @app.errorhandler(401)
    def unauthorized(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Nicht angemeldet"), 401
        return redirect(url_for("pages.login", next=request.path))

    return app
