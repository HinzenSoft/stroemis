"""Anmeldung, Registrierung, Passwort-Reset und Profil."""
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .images import delete_avatar, store_avatar
from .mailer import send_mail

bp = Blueprint("auth", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PW = 8

# Antwort auf eine Kontoanfrage – wortgleich, egal ob es die Adresse schon gibt (keine Nutzer-Enumeration).
PENDING_MSG = ("Danke! Deine Anfrage wurde an die Administratoren geschickt. "
               "Du bekommst eine E-Mail, sobald dein Konto freigegeben ist.")

# Bremse gegen Passwort-Raten: mehr Fehlversuche je Adresse oder je IP sperren für ATTEMPT_WINDOW.
ATTEMPT_WINDOW = timedelta(minutes=15)
MAX_LOGIN_TRIES = 10
MAX_FORGOT_TRIES = 10
MAX_REGISTER_TRIES = 10

# Genau eine Mail je Kontoanfrage: bei mehreren Admins würde sonst die Antwortzeit verraten,
# ob die Adresse schon ein Konto hat (eine Hinweismail) oder nicht (eine Mail je Admin).
# Die übrigen Admins sehen die Anfrage weiterhin unter /admin.
MAX_NOTIFY_MAILS = 1

# Fester Wegwerf-Hash für Anmeldungen ohne Treffer: auch dann wird die KDF gerechnet,
# damit unbekannte Adressen nicht schneller antworten als vorhandene.
DUMMY_HASH = generate_password_hash("kein-konto")


# --- Hilfsfunktionen ---------------------------------------------------------

def current_user():
    if "user" not in g:
        uid = session.get("uid")
        g.user = None
        if uid:
            u = db.query("SELECT * FROM users WHERE id = ? AND active = 1", (uid,), one=True)
            g.user = u
    return g.user


def is_admin(user=None):
    user = user or current_user()
    return bool(user and user["role"] == "admin")


# Die Rollen: "user" schreibt an eigenen und freigegebenen Seiten, "editor" an allen Inhalten,
# "admin" zusätzlich an Nutzern und Freigaben.
ROLLEN = ("user", "editor", "admin")


def darf_inhalte(user=None):
    """Darf alle Inhalte bearbeiten – Administratoren und Redakteure.

    Bewusst NICHT dasselbe wie is_admin: Nutzerverwaltung, das Veröffentlichen ohne Anmeldung
    und das Verschieben in öffentliche Abschnitte bleiben beim Administrator. Ein Redakteur
    pflegt das Wiki, verteilt aber keine Rechte und stellt nichts ins offene Netz."""
    user = user or current_user()
    return bool(user and user["role"] in ("admin", "editor"))


def initialen(name):
    """Die Buchstaben im Kreis, wenn kein Profilbild vorliegt – gleiche Regel wie im Wiki:
    die Anfangsbuchstaben der ersten beiden Wörter."""
    teile = str(name or "?").split()[:2]
    return "".join(t[0] for t in teile).upper() or "?"


def avatar_url(datei):
    """Adresse eines Profilbilds – oder None. Gezeigt wird es nur Angemeldeten (siehe media())."""
    return f"/media/avatar/{datei}" if datei else None


def public_user(u):
    out = {k: u[k] for k in ("id", "email", "name", "gliederung", "phone", "role", "active", "created_at")}
    out["status"] = u.get("status", "active")
    out["reason"] = u.get("reason", "")
    out["avatar"] = avatar_url(u.get("avatar") or "")
    return out


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return jsonify(error="Nicht angemeldet"), 401
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return jsonify(error="Nicht angemeldet"), 401
        if not is_admin():
            return jsonify(error="Nur für Administratoren"), 403
        return f(*a, **kw)
    return wrapper


def page_login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("pages.login", next=request.path))
        return f(*a, **kw)
    return wrapper


def eingabefehler_abfangen(bp):
    """Falsche Typen im JSON – eine Zahl statt Text, eine Liste statt Kennung, 1e30 als id –
    endeten als Ausnahme im Handler und damit als 500. Das ist kein Serverfehler, sondern
    eine unbrauchbare Eingabe; sie bekommt 400 und eine Zeile im Protokoll, damit ein echter
    Fehler an derselben Stelle trotzdem auffällt."""
    import sqlite3
    from flask import request as _request

    @bp.errorhandler(TypeError)
    @bp.errorhandler(ValueError)
    @bp.errorhandler(AttributeError)
    @bp.errorhandler(OverflowError)
    @bp.errorhandler(sqlite3.InterfaceError)
    @bp.errorhandler(sqlite3.ProgrammingError)
    def _eingabefehler(exc):
        current_app.logger.warning("Unbrauchbare Eingabe an %s %s: %r", _request.method, _request.path, exc)
        return jsonify(error="Unbrauchbare Eingabe."), 400


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def sfield(d, key):
    """Feld aus dem JSON-Body als Zeichenkette – alles andere (Zahl, Liste, None) gilt als leer,
    sonst würde eine falsch getippte Eingabe später als 500 statt als 400 enden."""
    v = d.get(key)
    return v if isinstance(v, str) else ""


def can_reset(u):
    """Darf für dieses Konto ein Passwort-Link erzeugt werden?"""
    return bool(u and u["active"] and (u.get("status") or "active") == "active")


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="pw-reset")


# --- Bremse gegen Passwort-Raten ---------------------------------------------

def _cutoff():
    return (datetime.now(timezone.utc) - ATTEMPT_WINDOW).replace(microsecond=0).isoformat()


def note_attempt(scope):
    db.execute("INSERT INTO login_attempts (scope, created_at) VALUES (?, ?)", (scope, db.now()))


def attempts_exceeded(scopes, limit):
    """True, sobald einer der Bereiche (IP, Adresse) das Limit im Zeitfenster erreicht hat."""
    cutoff = _cutoff()
    db.execute("DELETE FROM login_attempts WHERE created_at < ?", (cutoff,))
    for scope in scopes:
        n = db.query("SELECT COUNT(*) AS n FROM login_attempts WHERE scope = ? AND created_at >= ?",
                     (scope, cutoff), one=True)["n"]
        if n >= limit:
            return True
    return False


def clear_attempts(scopes):
    marks = ",".join("?" * len(scopes))
    db.execute(f"DELETE FROM login_attempts WHERE scope IN ({marks})", tuple(scopes))


def make_reset_token(user):
    # Teil des Hashes einbetten: Token wird ungültig, sobald das Passwort geändert wurde.
    return _serializer().dumps({"uid": user["id"], "h": user["password_hash"][-12:]})


def send_reset_mail(user):
    token = make_reset_token(user)
    # Der Token steht hinter '#': Fragmente werden nicht an den Server geschickt und landen
    # damit weder im Zugriffsprotokoll noch im Referer.
    link = current_app.config["BASE_URL"].rstrip("/") + "/reset#token=" + token
    body = (
        f"Hallo {user['name'] or user['email']},\n\n"
        "für dein Konto bei strömis.de wurde ein neues Passwort angefordert.\n"
        "Über diesen Link kannst du innerhalb der nächsten Stunde ein neues Passwort setzen:\n\n"
        f"{link}\n\n"
        "Falls du das nicht warst, kannst du diese E-Mail ignorieren.\n"
    )
    return send_mail(user["email"], "strömis.de – Passwort zurücksetzen", body)


def ensure_admin():
    """Legt beim Start den Administrator aus ADMIN_EMAIL / ADMIN_PASSWORD an, falls nötig."""
    email = (current_app.config.get("ADMIN_EMAIL") or "").strip().lower()
    pw = current_app.config.get("ADMIN_PASSWORD") or ""
    if not email or not pw:
        if not db.query("SELECT 1 FROM users LIMIT 1", one=True):
            current_app.logger.warning(
                "Noch kein Nutzer vorhanden und ADMIN_EMAIL/ADMIN_PASSWORD nicht gesetzt – "
                "der erste registrierte Nutzer wird Administrator.")
        return
    u = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if not u:
        try:
            db.execute(
                "INSERT INTO users (email, password_hash, name, role, created_at) VALUES (?,?,?,?,?)",
                (email, generate_password_hash(pw), "Administrator", "admin", db.now()))
            current_app.logger.info("Administrator %s angelegt.", email)
        except sqlite3.IntegrityError:
            # Gunicorn startet die App in jedem Arbeitsprozess getrennt. Beim allerersten Start
            # laufen sie gleichzeitig hier durch; einer legt den Administrator an, die anderen
            # finden ihn zwischen Abfrage und Einfügen bereits vor. Ohne diesen Fang stürbe der
            # zweite Prozess beim Hochfahren – und gunicorn fährt daraufhin ganz herunter.
            u = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if u and u["role"] != "admin":
        # status mitziehen: ein noch wartendes Konto käme sonst trotz Admin-Rolle nicht an der
        # Anmeldung vorbei (login() weist 'pending' vor 'active' ab).
        db.execute("UPDATE users SET role = 'admin', active = 1, status = 'active' WHERE id = ?", (u["id"],))


# --- Endpunkte ---------------------------------------------------------------

def notify_admins_about_request(user):
    """Alle Administratoren (oder ADMIN_NOTIFY_EMAIL) über eine neue Kontoanfrage informieren."""
    cfg = current_app.config
    to = ([cfg["ADMIN_NOTIFY_EMAIL"]] if cfg.get("ADMIN_NOTIFY_EMAIL") else
          [a["email"] for a in db.query(
              "SELECT email FROM users WHERE role = 'admin' AND active = 1 ORDER BY id")])[:MAX_NOTIFY_MAILS]
    body = (
        "Eine neue Kontoanfrage wartet auf Freigabe:\n\n"
        f"Name:        {user['name']}\n"
        f"E-Mail:      {user['email']}\n"
        f"Gliederung:  {user['gliederung']}\n"
        f"Telefon:     {user['phone'] or '–'}\n"
        f"Begründung:  {user['reason'] or '–'}\n\n"
        f"Freigeben oder ablehnen: {cfg['BASE_URL'].rstrip('/')}/admin\n"
    )
    for addr in to:
        try:
            send_mail(addr, f"{cfg['SITE_NAME']} – Kontoanfrage von {user['name'] or user['email']}", body)
        except Exception as exc:
            current_app.logger.error("Admin-Benachrichtigung an %s fehlgeschlagen: %s", addr, exc)


@bp.post("/auth/register")
def register():
    """Konto anfragen: das Konto wird angelegt, bleibt aber bis zur Freigabe durch einen Admin gesperrt.
    Ausnahme: der allererste Nutzer wird sofort Administrator."""
    if not current_app.config["ALLOW_REGISTRATION"]:
        return jsonify(error="Kontoanfragen sind deaktiviert. Bitte an den Administrator wenden."), 403
    d = json_body()
    email = sfield(d, "email").strip().lower()
    # Eigene Bereiche, damit die Anmeldebremse und diese hier sich nicht gegenseitig auslösen.
    # Jede Anfrage zählt – eine Kontoanfrage hat keinen Erfolg, der umsonst sein dürfte.
    scopes = [f"reg-ip:{request.remote_addr or '?'}", f"reg-mail:{email}"]
    if attempts_exceeded(scopes, MAX_REGISTER_TRIES):
        return jsonify(error="Zu viele Anfragen. Bitte in einer Viertelstunde noch einmal probieren."), 429
    with db.transaction():
        for scope in scopes:
            note_attempt(scope)
    pw = sfield(d, "password")
    name = sfield(d, "name").strip()
    gliederung = sfield(d, "gliederung").strip()
    if not EMAIL_RE.match(email):
        return jsonify(error="Bitte eine gültige E-Mail-Adresse angeben."), 400
    if not name or not gliederung:
        return jsonify(error="Bitte Name und Gliederung angeben."), 400
    if len(pw) < MIN_PW:
        return jsonify(error=f"Das Passwort muss mindestens {MIN_PW} Zeichen lang sein."), 400
    # Hash immer berechnen, auch wenn die Adresse längst vergeben ist: sonst verrät die
    # Antwortzeit (scrypt), welche Adressen ein Konto haben.
    pw_hash = generate_password_hash(pw)
    if db.query("SELECT 1 FROM users WHERE email = ?", (email,), one=True):
        # Gleiche Antwort wie bei einer echten Anfrage: von außen ist nicht zu erkennen,
        # welche Adressen ein Konto haben. Der Inhaber erfährt den Versuch per E-Mail.
        try:
            send_mail(email, f"{current_app.config['SITE_NAME']} – Kontoanfrage",
                      f"Für diese Adresse wurde eine Kontoanfrage bei {current_app.config['SITE_NAME']} gestellt, "
                      "obwohl es hier bereits ein Konto gibt.\n\n"
                      "Warst du das und kennst dein Passwort nicht mehr? Dann setze es über „Passwort vergessen“ "
                      f"neu: {current_app.config['BASE_URL'].rstrip('/')}/forgot\n\n"
                      "Sonst kannst du diese E-Mail ignorieren – es wurde kein zweites Konto angelegt.\n")
        except Exception as exc:
            current_app.logger.error("Hinweismail an %s fehlgeschlagen: %s", email, exc)
        current_app.logger.info("Kontoanfrage für bereits vorhandene Adresse %s abgewiesen.", email)
        return jsonify(pending=True, message=PENDING_MSG), 201
    first = not db.query("SELECT 1 FROM users LIMIT 1", one=True)
    uid = db.execute(
        "INSERT INTO users (email, password_hash, name, gliederung, phone, role, active, status, reason, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (email, pw_hash, name, gliederung, sfield(d, "phone").strip(),
         "admin" if first else "user", 1 if first else 0, "active" if first else "pending",
         sfield(d, "reason").strip()[:2000], db.now()))
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if first:
        session.clear()
        session["uid"] = uid
        session.permanent = True
        return jsonify(user=public_user(u), pending=False), 201
    notify_admins_about_request(u)
    return jsonify(pending=True, message=PENDING_MSG), 201


def warne_wenn_cookie_verworfen():
    """Häufigster Stolperstein beim ersten Start: COOKIE_SECURE steht auf true (richtig hinter
    TLS), aufgerufen wird die Anwendung aber über einfaches HTTP. Der Browser wirft das
    Sitzungscookie dann stillschweigend weg – die Anmeldung gelingt und man landet trotzdem
    wieder auf der Anmeldeseite. Das ist von außen nicht zu erkennen, deshalb hier ein Hinweis
    im Protokoll."""
    if current_app.config.get("SESSION_COOKIE_SECURE") and not request.is_secure:
        current_app.logger.warning(
            "Anmeldung über unverschlüsseltes HTTP, aber COOKIE_SECURE=true – der Browser "
            "verwirft das Sitzungscookie und die Anmeldung wirkt wirkungslos. Für lokale Tests "
            "COOKIE_SECURE=false setzen; im Betrieb muss der Reverse-Proxy X-Forwarded-Proto "
            "mitschicken.")


@bp.post("/auth/login")
def login():
    d = json_body()
    email = sfield(d, "email").strip().lower()
    scopes = [f"ip:{request.remote_addr or '?'}", f"mail:{email}"]
    if attempts_exceeded(scopes, MAX_LOGIN_TRIES):
        return jsonify(error="Zu viele Fehlversuche. Bitte in einer Viertelstunde noch einmal probieren "
                             "oder das Passwort zurücksetzen."), 429
    u = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    stimmt = check_password_hash(u["password_hash"] if u else DUMMY_HASH, sfield(d, "password"))
    if not u or not stimmt:
        with db.transaction():
            for scope in scopes:
                note_attempt(scope)
        return jsonify(error="E-Mail-Adresse oder Passwort ist falsch."), 401
    if u.get("status") == "pending":
        return jsonify(error="Deine Kontoanfrage wartet noch auf die Freigabe durch einen Administrator."), 403
    if not u["active"]:
        return jsonify(error="Dieses Konto ist deaktiviert."), 403
    # Nur den Zähler des Kontos zurücksetzen: sonst könnte ein Angreifer mit einem einzigen
    # gültigen Konto die IP-Bremse beliebig oft lösen und weiter Passwörter durchprobieren.
    clear_attempts([f"mail:{email}"])
    warne_wenn_cookie_verworfen()
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True
    return jsonify(user=public_user(u))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.post("/auth/forgot")
def forgot():
    email = sfield(json_body(), "email").strip().lower()
    scope = f"forgot:{request.remote_addr or '?'}"
    if attempts_exceeded([scope], MAX_FORGOT_TRIES):
        return jsonify(error="Zu viele Anfragen. Bitte in einer Viertelstunde noch einmal probieren."), 429
    note_attempt(scope)
    u = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if can_reset(u):
        try:
            send_reset_mail(u)
        except Exception as exc:  # Versand darf die Antwort nicht verändern (kein Nutzer-Enumeration)
            current_app.logger.error("Reset-Mail an %s fehlgeschlagen: %s", email, exc)
    return jsonify(ok=True, message="Falls ein Konto existiert, wurde eine E-Mail mit einem Link verschickt.")


@bp.post("/auth/reset")
def reset():
    d = json_body()
    pw = sfield(d, "password")
    if len(pw) < MIN_PW:
        return jsonify(error=f"Das Passwort muss mindestens {MIN_PW} Zeichen lang sein."), 400
    try:
        data = _serializer().loads(sfield(d, "token"), max_age=3600)
    except SignatureExpired:
        return jsonify(error="Der Link ist abgelaufen. Bitte ein neues Passwort anfordern."), 400
    except BadSignature:
        return jsonify(error="Der Link ist ungültig."), 400
    u = db.query("SELECT * FROM users WHERE id = ?", (data.get("uid"),), one=True)
    if not u or u["password_hash"][-12:] != data.get("h"):
        return jsonify(error="Der Link wurde bereits verwendet."), 400
    if not can_reset(u):
        if (u.get("status") or "active") == "pending":
            return jsonify(error="Deine Kontoanfrage wartet noch auf die Freigabe durch einen Administrator."), 403
        return jsonify(error="Dieses Konto ist deaktiviert."), 403
    with db.transaction():
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(pw), u["id"]))
        clear_attempts([f"ip:{request.remote_addr or '?'}", f"mail:{u['email']}"])
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True
    return jsonify(ok=True)


@bp.get("/me")
@login_required
def me():
    return jsonify(user=public_user(current_user()))


@bp.put("/me")
@login_required
def update_me():
    d = json_body()
    u = current_user()
    # Nur, was mitgeschickt wurde: Ein Aufruf, der bloß die Telefonnummer ändert, darf nicht
    # nebenbei Name und Gliederung leeren. Der Name bleibt Pflicht.
    vals = {k: sfield(d, k).strip()[:120] for k in ("name", "gliederung", "phone") if k in d}
    if "name" in vals and not vals["name"]:
        return jsonify(error="Der Name darf nicht leer sein."), 400
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        db.execute(f"UPDATE users SET {sets} WHERE id = ?", (*vals.values(), u["id"]))
    return jsonify(user=public_user(db.query("SELECT * FROM users WHERE id = ?", (u["id"],), one=True)))


@bp.post("/me/avatar")
@login_required
def set_avatar():
    """Profilbild hochladen. Es ersetzt ein vorhandenes; die alte Datei wird gelöscht."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Es wurde keine Datei mitgeschickt."), 400
    u = current_user()
    alt = u.get("avatar") or ""
    medien = current_app.config["MEDIA_DIR"]
    try:
        name = store_avatar(f, medien)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    # Bedingt schreiben: Laden zwei Reiter gleichzeitig hoch, gewinnt einer – der andere räumt
    # seine Datei wieder weg, statt sie unbemerkt liegen zu lassen. Und erst wenn der neue Name
    # steht, fällt der alte weg; andersherum zeigte die Zeile nach einem Fehlschlag beim
    # Schreiben auf eine Datei, die es nicht mehr gibt.
    if not db.execute_zeilen("UPDATE users SET avatar = ? WHERE id = ? AND avatar = ?",
                             (name, u["id"], alt)):
        delete_avatar(medien, name)
        return jsonify(error="Das Profilbild wurde zwischenzeitlich anderswo geändert. "
                             "Bitte die Seite neu laden."), 409
    delete_avatar(medien, alt)
    return jsonify(user=public_user(db.query("SELECT * FROM users WHERE id = ?", (u["id"],), one=True)))


@bp.delete("/me/avatar")
@login_required
def remove_avatar():
    u = current_user()
    db.execute("UPDATE users SET avatar = '' WHERE id = ?", (u["id"],))
    delete_avatar(current_app.config["MEDIA_DIR"], u.get("avatar") or "")
    return jsonify(user=public_user(db.query("SELECT * FROM users WHERE id = ?", (u["id"],), one=True)))


@bp.put("/me/password")
@login_required
def change_password():
    d = json_body()
    u = current_user()
    if not check_password_hash(u["password_hash"], sfield(d, "current")):
        return jsonify(error="Das aktuelle Passwort ist falsch."), 400
    new = sfield(d, "password")
    if len(new) < MIN_PW:
        return jsonify(error=f"Das neue Passwort muss mindestens {MIN_PW} Zeichen lang sein."), 400
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), u["id"]))
    return jsonify(ok=True)
