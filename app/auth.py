"""Anmeldung, Registrierung, Passwort-Reset und Profil."""
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, abort, current_app, g, jsonify, redirect, request, session, url_for
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
               "Du bekommst eine E-Mail, sobald dein Konto freigegeben ist. "
               "Sieh dann bitte auch im Spam-Ordner nach – automatisch verschickte Mails landen "
               "dort häufiger.")

# Bremse gegen Passwort-Raten: mehr Fehlversuche je Adresse oder je IP sperren für ATTEMPT_WINDOW.
ATTEMPT_WINDOW = timedelta(minutes=15)
MAX_LOGIN_TRIES = 10
MAX_FORGOT_TRIES = 10
MAX_REGISTER_TRIES = 10

# Genau eine Mail je Kontoanfrage: bei mehreren Admins würde sonst die Antwortzeit verraten,
# ob die Adresse schon ein Konto hat (eine Hinweismail) oder nicht (eine Mail je Admin).
# Die übrigen Admins sehen die Anfrage weiterhin in der Leitstelle (/leitstelle).
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
            # Die Sitzung trägt den Passwortstand mit (sitzung_beginnen): Nach einer Änderung des
            # Passworts – auch per Reset-Link – gilt sie in jedem anderen Browser nicht mehr.
            if u and session.get("pw") != sitzungsmarke(u):
                u = None
            g.user = u
    return g.user


def sitzungsmarke(u):
    return (u.get("password_hash") or "")[-12:]


def sitzung_beginnen(u):
    """Anmelden: die Sitzung an Konto UND Passwortstand binden. Ändert sich das Passwort,
    verfallen alle anderen Sitzungen dieser Person – ein entwendetes Cookie hilft danach nicht
    mehr, und wer sein Passwort zurücksetzt, wirft damit auch fremde Anmeldungen hinaus."""
    session.clear()
    session["uid"] = u["id"]
    session["pw"] = sitzungsmarke(u)
    session.permanent = True


def _einzeilig(text, n=120):
    """Ein Feld für eine Zeile: Steuerzeichen und Zeilenumbrüche raus, Länge gedeckelt. Ein
    Zeilenumbruch im Namen landete sonst im Betreff der Admin-Mail – die der Mailer zu Recht
    verwirft, womit die Anfrage unbemerkt nur in der Leitstelle läge."""
    text = "".join(c for c in (text or "") if c >= " " and c != "\x7f")
    return text.strip()[:n]


def _im_hintergrund(funktion, *args):
    """Mailversand neben der Anfrage statt in ihr: Die Antwortzeit soll nicht verraten, ob eine
    Mail hinausging – sonst ließe sich an der Dauer ablesen, welche Adressen ein Konto haben."""
    app = current_app._get_current_object()

    def lauf():
        with app.app_context():
            try:
                funktion(*args)
            except Exception as exc:
                app.logger.error("Mailversand im Hintergrund fehlgeschlagen: %s", exc)
    threading.Thread(target=lauf, name="mail", daemon=True).start()


# --- Rechte-Matrix ------------------------------------------------------------------------------
# Statt Rollen trägt jedes Konto je Modul eine Stufe: 0 kein Zugriff, 1 Mitglied, 2 Verwaltung.
#   karte       Mitglied: eigene Alben anlegen und bearbeiten; Verwaltung: alle Alben.
#   wiki        Mitglied: eigene und freigegebene Seiten; Verwaltung: alle Seiten, beschränkte lesen,
#               veröffentlichen, HTML-Bausteine, Ersteller ändern, endgültig löschen. Kein Zugriff heißt hier:
#               Lesemodus – nur die Seiten, die der öffentliche Teil zeigt (siehe wiki_lesemodus).
#   pruefungen  Mitglied: Prüfungen abnehmen; Verwaltung: Kataloge pflegen, jeden Lehrgang leiten.
#   material    Mitglied: das Modul nutzen (Katalog, Suche, Profil) – Bestand nur über Freigaben je Ordner, die der
#               Verwalter eines Ordners vergibt; Verwaltung (Material-Verwaltung): zusätzlich Produktkatalog pflegen,
#               alle Bestände, Gliederungen anlegen, jede Freigabe. Prüfen nie über die Stufe – nur mit Häkchen
#               „Prüfer“, Urkundennummer und Prüffreigabe. Ohne Stufe wirken weder Freigaben noch das Häkchen
#               (app/material/services/rechte.py).
#   verwaltung  Verwaltung: Nutzer, Rechte, Einstellungen – und damit alle Rechte überall; eine
#               Mitglied-Stufe gibt es hier nicht.
# Die Werte liegen als Spalten recht_<modul> am Nutzer (db.py); api_admin schreibt sie.
MODULE = ("karte", "wiki", "pruefungen", "material", "verwaltung")
KEIN_ZUGRIFF, MITGLIED, VERWALTUNG = 0, 1, 2
STUFEN = (KEIN_ZUGRIFF, MITGLIED, VERWALTUNG)
# Vorgabe für neue Konten (Kontoanfrage und Nutzerverwaltung): Mitglied in der Materialablage, sonst nichts – Spots und
# Wiki gibt es nicht mehr von selbst (Wunsch vom 18.10.2026; ohne Wiki-Stufe bleibt der Lesemodus). Vorhandene Konten
# behalten ihre Stufen.
VORGABE_NEU = {"karte": KEIN_ZUGRIFF, "wiki": KEIN_ZUGRIFF, "pruefungen": KEIN_ZUGRIFF, "material": MITGLIED,
               "verwaltung": KEIN_ZUGRIFF}


def stufe(modul, user=None):
    """Wirksame Stufe eines Nutzers im Modul – Verwaltung im Modul „verwaltung“ gilt überall."""
    user = user or current_user()
    if not user:
        return KEIN_ZUGRIFF
    if int(user["recht_verwaltung"] or 0) >= VERWALTUNG:
        return VERWALTUNG
    return int(user[f"recht_{modul}"] or 0)


def nutzt(modul, user=None):
    """Hat Zugang zum Modul (Mitglied oder Verwaltung)."""
    return stufe(modul, user) >= MITGLIED


def verwaltet(modul, user=None):
    return stufe(modul, user) >= VERWALTUNG


def wiki_lesemodus(user=None):
    """Angemeldet und freigeschaltet, aber ohne Stufe im Wiki: Das Konto liest die Seiten, die der öffentliche Teil
    ohne Anmeldung zeigt – im angemeldeten Bereich, unter der eigenen Kopfleiste. Erreichen könnte es sie über
    wiki.strömis.de ohnehin. Mehr als dort gibt es nicht: Der Lesemodus holt alles über die öffentliche Schnittstelle
    (/api/public, api_wiki.is_public), die internen Endpunkte bleiben bei wiki_required und antworten weiter 403.
    Wartende und deaktivierte Konten haben keine Sitzung (current_user) – für sie ändert sich nichts."""
    user = user or current_user()
    return bool(user and user["active"] and (user.get("status") or "active") == "active" and not nutzt("wiki", user))


def rechte_von(user):
    """Die wirksamen Stufen als Wörterbuch – so gehen sie an die Oberfläche."""
    return {m: stufe(m, user) for m in MODULE}


def is_admin(user=None):
    """Verwaltung in der Leitstelle: Nutzer und Einstellungen – und alle Rechte überall."""
    return verwaltet("verwaltung", user)


def is_pruefer(user=None):
    """Darf Prüfungen abnehmen (Mitglied oder Verwaltung in den Riegenkarten). Der Bereich enthält
    personenbezogene Daten von Teilnehmenden – wer ihn nicht braucht, bekommt die Stufe nicht."""
    return nutzt("pruefungen", user)


def initialen(name):
    """Die Buchstaben im Kreis, wenn kein Profilbild vorliegt – gleiche Regel wie im Wiki:
    die Anfangsbuchstaben der ersten beiden Wörter."""
    teile = str(name or "?").split()[:2]
    return "".join(t[0] for t in teile).upper() or "?"


def avatar_url(datei):
    """Adresse eines Profilbilds – oder None. Gezeigt wird es nur Angemeldeten (siehe media())."""
    return f"/media/avatar/{datei}" if datei else None


def public_user(u):
    out = {k: u[k] for k in ("id", "email", "name", "gliederung", "phone", "active", "created_at")}
    out["status"] = u.get("status", "active")
    out["reason"] = u.get("reason", "")
    out["avatar"] = avatar_url(u.get("avatar") or "")
    out["rechte"] = rechte_von(u)
    # Modul Material: das Häkchen „Prüfer“, wie es gespeichert ist, und die Urkundennummer. Was davon wirkt (nur mit
    # Stufe im Modul und Urkundennummer), entscheidet app/material/services/rechte.py.
    out["mat_pruefer"] = bool(u.get("mat_pruefer"))
    out["urkundennummer"] = u.get("urkundennummer") or ""
    # Taugt die Nummer (Buchstaben oder Ziffern)? Die Nutzerverwaltung zeigt sonst „Prüfer – Urkundennummer fehlt“.
    from .material.services.rechte import urkunde_gueltig, urkunde_saeubern
    out["urkunde_gueltig"] = urkunde_gueltig(urkunde_saeubern(out["urkundennummer"]))
    out["unterschrift"] = bool(u.get("signature_png"))
    return out


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return jsonify(error="Nicht angemeldet"), 401
        return f(*a, **kw)
    return wrapper


# Die Meldungen nennen die sichtbaren Modulnamen (app/module.py); die Schlüssel bleiben.
KEIN_ZUGANG = {"karte": "Für dein Konto sind die Ankerplätze nicht freigeschaltet.",
               "wiki": "Für dein Konto ist die Strömipedia nicht freigeschaltet.",
               "pruefungen": "Für dein Konto sind die Riegenkarten nicht freigeschaltet.",
               "material": "Für dein Konto ist die Materialablage nicht freigeschaltet.",
               "verwaltung": "Für dein Konto ist die Leitstelle nicht freigeschaltet."}


def modul_required(modul, mindestens=MITGLIED):
    """Schnittstellen eines Moduls: angemeldet UND die Stufe im Modul. Ein ausgeblendeter Reiter
    ist kein Schutz – jede Route prüft selbst, sonst genügte eine getippte Adresse."""
    def deko(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not current_user():
                return jsonify(error="Nicht angemeldet"), 401
            if stufe(modul) < mindestens:
                return jsonify(error=KEIN_ZUGANG[modul] if mindestens == MITGLIED else "Nur für die Verwaltung"), 403
            return f(*a, **kw)
        return wrapper
    return deko


karte_required = modul_required("karte")
wiki_required = modul_required("wiki")
pruefer_required = modul_required("pruefungen")
admin_required = modul_required("verwaltung", VERWALTUNG)


def page_login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("pages.login", next=request.path))
        return f(*a, **kw)
    return wrapper


def page_modul_required(modul):
    """Seiten eines Moduls: ohne Anmeldung zum Login, ohne Stufe die Fehlerseite."""
    def deko(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not current_user():
                return redirect(url_for("pages.login", next=request.path))
            if not nutzt(modul):
                abort(403)
            return f(*a, **kw)
        return wrapper
    return deko


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
                "INSERT INTO users (email, password_hash, name, recht_karte, recht_wiki, recht_pruefungen, "
                "recht_material, recht_verwaltung, created_at) VALUES (?,?,?,2,2,2,2,2,?)",
                (email, generate_password_hash(pw), "Administrator", db.now()))
            current_app.logger.info("Administrator %s angelegt.", email)
        except sqlite3.IntegrityError:
            # Gunicorn startet die App in jedem Arbeitsprozess getrennt. Beim allerersten Start
            # laufen sie gleichzeitig hier durch; einer legt den Administrator an, die anderen
            # finden ihn zwischen Abfrage und Einfügen bereits vor. Ohne diesen Fang stürbe der
            # zweite Prozess beim Hochfahren – und gunicorn fährt daraufhin ganz herunter.
            u = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if u and u["recht_verwaltung"] != VERWALTUNG:
        # status mitziehen: ein noch wartendes Konto käme sonst trotz Verwaltungsrecht nicht an der
        # Anmeldung vorbei (login() weist 'pending' vor 'active' ab).
        db.execute("UPDATE users SET recht_karte = 2, recht_wiki = 2, recht_pruefungen = 2, recht_material = 2, "
                   "recht_verwaltung = 2, active = 1, status = 'active' WHERE id = ?", (u["id"],))


# --- Endpunkte ---------------------------------------------------------------

def notify_admins_about_request(user):
    """Alle Administratoren (oder ADMIN_NOTIFY_EMAIL) über eine neue Kontoanfrage informieren."""
    cfg = current_app.config
    to = ([cfg["ADMIN_NOTIFY_EMAIL"]] if cfg.get("ADMIN_NOTIFY_EMAIL") else
          [a["email"] for a in db.query(
              "SELECT email FROM users WHERE recht_verwaltung = 2 AND active = 1 ORDER BY id")])[:MAX_NOTIFY_MAILS]
    body = (
        "Eine neue Kontoanfrage wartet auf Freigabe:\n\n"
        f"Name:        {user['name']}\n"
        f"E-Mail:      {user['email']}\n"
        f"Gliederung:  {user['gliederung']}\n"
        f"Telefon:     {user['phone'] or '–'}\n"
        f"Begründung:  {user['reason'] or '–'}\n\n"
        f"Freigeben oder ablehnen: {cfg['BASE_URL'].rstrip('/')}/leitstelle\n"
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
    name = _einzeilig(sfield(d, "name"))
    gliederung = _einzeilig(sfield(d, "gliederung"))
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
    try:
        # Prüfung und Eintrag unter einer Schreibsperre: Zwei gleichzeitige Erstanfragen sähen
        # sonst beide „noch kein Nutzer“ – und beide würden Administrator.
        with db.transaction(sofort=True):
            first = not db.query("SELECT 1 FROM users LIMIT 1", one=True)
            uid = db.execute(
                "INSERT INTO users (email, password_hash, name, gliederung, phone, recht_karte, recht_wiki, "
                "recht_pruefungen, recht_material, recht_verwaltung, active, status, reason, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                # Der allererste Nutzer bekommt überall Verwaltung; alle weiteren die Vorgabe (Mitglied im
                # Modul Material, sonst nichts – das Wiki lesen sie im Lesemodus; VORGABE in api_admin.py)
                # und warten auf die Freigabe.
                (email, pw_hash, name, gliederung, _einzeilig(sfield(d, "phone")),
                 *((2, 2, 2, 2, 2) if first else tuple(VORGABE_NEU[m] for m in MODULE)),
                 1 if first else 0, "active" if first else "pending",
                 sfield(d, "reason").strip()[:2000], db.now()))
    except sqlite3.IntegrityError:
        # Dieselbe Adresse im selben Augenblick zweimal angefragt: Die zweite Anfrage bekommt die
        # Antwort von oben – als gäbe es das Konto schon. Gibt es jetzt ja auch.
        return jsonify(pending=True, message=PENDING_MSG), 201
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if first:
        sitzung_beginnen(u)
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
    # Wann zuletzt angemeldet – in der Nutzerverwaltung die Antwort auf „wer arbeitet hier
    # eigentlich noch mit?“. Nur bei der erfolgreichen Anmeldung, nicht bei jedem Aufruf: Der
    # Zeitpunkt soll das Anmelden bezeichnen, nicht das letzte Lebenszeichen des Browsers.
    db.execute("UPDATE users SET last_login = ? WHERE id = ?", (db.now(), u["id"]))
    sitzung_beginnen(u)
    return jsonify(user=public_user(u))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.post("/auth/forgot")
def forgot():
    email = sfield(json_body(), "email").strip().lower()
    # Je Absender UND je Adresse: Sonst ließe sich ein Postfach mit Reset-Mails fluten, sobald die
    # Absenderadresse nicht festliegt (mehrere Rechner, gefälschte Weiterleitungskopfzeile).
    scopes = [f"forgot:{request.remote_addr or '?'}", f"forgot-mail:{email}"]
    if attempts_exceeded(scopes, MAX_FORGOT_TRIES):
        return jsonify(error="Zu viele Anfragen. Bitte in einer Viertelstunde noch einmal probieren."), 429
    with db.transaction():
        for scope in scopes:
            note_attempt(scope)
    u = db.query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if can_reset(u):
        # Im Hintergrund: Der Versand (Verbindung, STARTTLS, Anmeldung) dauert spürbar – und nur
        # bei vorhandenem Konto. An der Antwortzeit wäre sonst abzulesen, welche Adressen eins haben.
        _im_hintergrund(send_reset_mail, u)
    return jsonify(ok=True, message="Falls ein Konto existiert, wurde eine E-Mail mit einem Link "
                                    "verschickt. Sieh bitte auch im Spam-Ordner nach – automatisch "
                                    "verschickte Mails landen dort häufiger.")


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
    neu = generate_password_hash(pw)
    with db.transaction():
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (neu, u["id"]))
        clear_attempts([f"ip:{request.remote_addr or '?'}", f"mail:{u['email']}"])
    sitzung_beginnen({**u, "password_hash": neu})
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
    alt = u.get("avatar") or ""
    # Bedingt wie beim Hochladen: Hat ein anderer Reiter inzwischen ein neues Bild gesetzt, bleibt
    # das stehen – sonst löschte dieser Aufruf dessen Datei und ließe die Zeile ins Leere zeigen.
    if alt and db.execute_zeilen("UPDATE users SET avatar = '' WHERE id = ? AND avatar = ?", (u["id"], alt)):
        delete_avatar(current_app.config["MEDIA_DIR"], alt)
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
    neu = generate_password_hash(new)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (neu, u["id"]))
    # Diese Sitzung bleibt, alle anderen verfallen (siehe sitzung_beginnen).
    session["pw"] = neu[-12:]
    return jsonify(ok=True)
