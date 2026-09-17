"""Nutzerverwaltung für Administratoren."""
import secrets

from flask import Blueprint, current_app, jsonify

from . import db, medienpflege
from .auth import (EMAIL_RE, MIN_PW, ROLLEN, admin_required, can_reset, clear_attempts, current_user,
                   eingabefehler_abfangen, json_body, public_user, send_reset_mail)
from .images import delete_avatar
from .mailer import send_mail, versand
from werkzeug.security import generate_password_hash

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
eingabefehler_abfangen(bp)


def _rolle(wert):
    """Unbekanntes wird zur einfachen Rolle – so kann kein Tippfehler Rechte verteilen."""
    return wert if wert in ROLLEN else "user"


@bp.post("/testmail")
@admin_required
def testmail():
    """Eine Probemail verschicken und wörtlich berichten, was der Mailserver dazu sagt.

    Gedacht zum Nachsehen, wenn Mails nicht ankommen: Ob es an der Verbindung liegt, an der
    Anmeldung oder daran, dass die Gegenseite den Empfänger abweist, steht in der Antwort.
    Inhalt und Betreff sind fest – der Knopf verschickt nichts, was jemand hineinschreiben
    könnte. Ohne Angabe geht die Mail an die eigene Adresse."""
    cfg = current_app.config
    ich = current_user()
    ziel = (json_body().get("to") or "").strip() or ich["email"]
    if not EMAIL_RE.match(ziel):
        return jsonify(error="Bitte eine gültige E-Mail-Adresse angeben."), 400
    if not cfg.get("SMTP_HOST"):
        return jsonify(ok=False, meldung="SMTP ist nicht eingerichtet (SMTP_HOST fehlt). "
                                         "Ohne Mailserver schreibt die Anwendung Mails nur ins Log.",
                       an=ziel, absender=cfg.get("MAIL_FROM", ""))
    ok, meldung = versand(
        ziel, f"{cfg['SITE_NAME']} – Probemail",
        f"Diese Mail hat {ich['name'] or ich['email']} in der Nutzerverwaltung von {cfg['SITE_NAME']} "
        "ausgelöst, um den Versand zu prüfen.\n\n"
        "Kommt sie an, funktioniert der Weg vom Server bis zu diesem Postfach. Landet sie im "
        "Spam oder gar nicht, liegt es meist an SPF, DKIM oder DMARC der Absenderdomain – die "
        "Unzustellbarkeitsmeldung nennt den Grund.\n")
    current_app.logger.info("Probemail an %s von %s: %s", ziel, ich["email"], meldung)
    return jsonify(ok=ok, meldung=meldung, an=ziel, absender=cfg.get("MAIL_FROM", ""),
                   umschlag=(cfg.get("SMTP_ENVELOPE_FROM") or "").strip() or None)


@bp.get("/videos")
@admin_required
def videos():
    """Stand der Videopflege – ob im Hintergrund noch Bestandsvideos gewandelt werden."""
    return jsonify(medienpflege.stand(current_app))


@bp.get("/users")
@admin_required
def list_users():
    rows = db.query(
        "SELECT u.*, (SELECT COUNT(*) FROM albums a WHERE a.owner_id = u.id) AS album_count, "
        "(SELECT COUNT(*) FROM photos p WHERE p.owner_id = u.id) AS photo_count "
        "FROM users u ORDER BY (u.status = 'pending') DESC, u.created_at")
    out = []
    for r in rows:
        u = public_user(r)
        u["album_count"], u["photo_count"] = r["album_count"], r["photo_count"]
        out.append(u)
    return jsonify(users=out)


@bp.post("/users")
@admin_required
def create_user():
    d = json_body()
    email = (d.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify(error="Bitte eine gültige E-Mail-Adresse angeben."), 400
    if db.query("SELECT 1 FROM users WHERE email = ?", (email,), one=True):
        return jsonify(error="Für diese E-Mail-Adresse gibt es bereits ein Konto."), 409
    pw = d.get("password") or secrets.token_urlsafe(12)
    if len(pw) < MIN_PW:
        return jsonify(error=f"Das Passwort muss mindestens {MIN_PW} Zeichen lang sein."), 400
    uid = db.execute(
        "INSERT INTO users (email, password_hash, name, gliederung, phone, role, created_at) VALUES (?,?,?,?,?,?,?)",
        (email, generate_password_hash(pw), (d.get("name") or "").strip(), (d.get("gliederung") or "").strip(),
         (d.get("phone") or "").strip(), _rolle(d.get("role")), db.now()))
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    mailed = False
    if d.get("send_invite"):
        try:
            mailed = bool(send_reset_mail(u))
        except Exception as exc:
            current_app.logger.error("Einladung an %s fehlgeschlagen: %s", email, exc)
    out = public_user(u)
    return jsonify(user=out, initial_password=None if d.get("password") else pw, invite_sent=mailed), 201


@bp.put("/users/<int:uid>")
@admin_required
def update_user(uid):
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if not u:
        return jsonify(error="Nutzer nicht gefunden"), 404
    d = json_body()
    vals = {}
    for f in ("name", "gliederung", "phone"):
        if f in d:
            vals[f] = (d.get(f) or "").strip()
    if "email" in d:
        email = (d.get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return jsonify(error="Bitte eine gültige E-Mail-Adresse angeben."), 400
        other = db.query("SELECT id FROM users WHERE email = ?", (email,), one=True)
        if other and other["id"] != uid:
            return jsonify(error="Diese E-Mail-Adresse wird bereits verwendet."), 409
        vals["email"] = email
    if "role" in d:
        role = _rolle(d.get("role"))
        if uid == current_user()["id"] and role != "admin":
            return jsonify(error="Du kannst dir nicht selbst die Administratorrechte entziehen."), 400
        vals["role"] = role
    if "active" in d:
        active = 1 if d.get("active") else 0
        if uid == current_user()["id"] and not active:
            return jsonify(error="Du kannst dein eigenes Konto nicht deaktivieren."), 400
        vals["active"] = active
    if d.get("password"):
        if len(d["password"]) < MIN_PW:
            return jsonify(error=f"Das Passwort muss mindestens {MIN_PW} Zeichen lang sein."), 400
        vals["password_hash"] = generate_password_hash(d["password"])
    if vals:
        sets = ", ".join(f"{k} = ?" for k in vals)
        db.execute(f"UPDATE users SET {sets} WHERE id = ?", (*vals.values(), uid))
    if "password_hash" in vals:
        # Ein Admin setzt das Passwort meist genau dann neu, wenn sich jemand ausgesperrt hat –
        # ohne das Löschen der Fehlversuche bliebe die Anmeldung trotzdem gesperrt.
        clear_attempts(sorted({f"mail:{u['email']}", f"mail:{vals.get('email', u['email'])}"}))
    return jsonify(user=public_user(db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)))


@bp.post("/users/<int:uid>/reset-mail")
@admin_required
def reset_mail(uid):
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if not u:
        return jsonify(error="Nutzer nicht gefunden"), 404
    # /api/auth/reset weist den Token für gesperrte Konten ab – dann wäre der verschickte Link wertlos.
    if not can_reset(u):
        return jsonify(error="Für dieses Konto lässt sich kein Passwort-Link erzeugen. "
                             "Bitte das Konto zuerst freigeben bzw. wieder aktivieren."), 400
    try:
        sent = send_reset_mail(u)
    except Exception as exc:
        return jsonify(error=f"Versand fehlgeschlagen: {exc}"), 500
    return jsonify(ok=True, sent=bool(sent),
                   message="E-Mail verschickt." if sent else "SMTP nicht konfiguriert – Link steht im Server-Log.")


@bp.delete("/users/<int:uid>")
@admin_required
def delete_user(uid):
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if not u:
        return jsonify(error="Nutzer nicht gefunden"), 404
    me = current_user()["id"]
    if uid == me:
        return jsonify(error="Du kannst dein eigenes Konto nicht löschen."), 400
    bild = u.get("avatar") or ""
    # Inhalte bleiben erhalten und gehen an den ausführenden Administrator über –
    # entweder vollständig oder gar nicht, sonst stünde der Bestand halb umgeschrieben da.
    with db.transaction():
        db.execute("UPDATE albums SET owner_id = ? WHERE owner_id = ?", (me, uid))
        db.execute("UPDATE photos SET owner_id = ? WHERE owner_id = ?", (me, uid))
        db.execute("UPDATE wiki_pages SET created_by = ? WHERE created_by = ?", (me, uid))
        db.execute("UPDATE wiki_pages SET updated_by = ? WHERE updated_by = ?", (me, uid))
        db.execute("UPDATE wiki_revisions SET user_id = ? WHERE user_id = ?", (me, uid))
        db.execute("UPDATE wiki_files SET user_id = ? WHERE user_id = ?", (me, uid))
        db.execute("DELETE FROM users WHERE id = ?", (uid,))
    # Erst nach dem Festschreiben: Bricht die Umschreibung ab, bleibt das Konto samt Bild stehen.
    delete_avatar(current_app.config["MEDIA_DIR"], bild)
    return jsonify(ok=True)


@bp.post("/users/<int:uid>/approve")
@admin_required
def approve_user(uid):
    u = db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if not u:
        return jsonify(error="Nutzer nicht gefunden"), 404
    # Nur offene Anfragen freigeben: sonst würde dieser Endpunkt ein bewusst deaktiviertes Konto
    # wieder scharf schalten und dazu eine Freigabe-Mail verschicken.
    if (u.get("status") or "active") != "pending":
        return jsonify(error="Zu diesem Nutzer gibt es keine offene Anfrage. Ein deaktiviertes Konto "
                             "wird über die Nutzerbearbeitung wieder aktiviert."), 400
    db.execute("UPDATE users SET status = 'active', active = 1 WHERE id = ?", (uid,))
    cfg = current_app.config
    mailed = False
    try:
        mailed = send_mail(u["email"], f"{cfg['SITE_NAME']} – dein Konto ist freigegeben",
                           f"Hallo {u['name'] or u['email']},\n\ndein Konto bei {cfg['SITE_NAME']} wurde freigegeben. "
                           f"Du kannst dich jetzt anmelden:\n\n{cfg['BASE_URL'].rstrip('/')}/login\n")
    except Exception as exc:
        current_app.logger.error("Freigabe-Mail an %s fehlgeschlagen: %s", u["email"], exc)
    return jsonify(user=public_user(db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True)), mailed=bool(mailed))


@bp.post("/users/<int:uid>/reject")
@admin_required
def reject_user(uid):
    u = db.query("SELECT * FROM users WHERE id = ? AND status = 'pending'", (uid,), one=True)
    if not u:
        return jsonify(error="Keine offene Anfrage zu diesem Nutzer."), 404
    db.execute("DELETE FROM users WHERE id = ?", (uid,))
    return jsonify(ok=True)
