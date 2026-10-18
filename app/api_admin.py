"""Nutzerverwaltung für Administratoren."""
import secrets

from flask import Blueprint, current_app, jsonify

from . import db, einstellungen, medienpflege
from .auth import (EMAIL_RE, MIN_PW, MODULE, STUFEN, VERWALTUNG, admin_required, can_reset, clear_attempts,
                   current_user, eingabefehler_abfangen, json_body, public_user, send_reset_mail)
from .images import delete_avatar
from .mailer import send_mail, versand
from .material.services import Abgelehnt
from .material.services import freigaben as mat_freigaben
from .material.services import journal as mat_journal
from .material.services import loeschung as mat_loeschung
from .material.services.rechte import rollen_lesen
from werkzeug.security import generate_password_hash

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
eingabefehler_abfangen(bp)


# Vorgabe für neue Konten: Mitglied in Spots und Wiki, sonst nichts.
VORGABE = {"karte": 1, "wiki": 1, "pruefungen": 0, "material": 0, "verwaltung": 0}
# Was am Konto zum Modul Material gehört – Änderungen daran stehen im Journal des Moduls.
MATERIAL_SPALTEN = ("recht_material", "mat_pruefer", "mat_katalog", "urkundennummer")
OHNE_NAMEN = "Erst einen Namen eintragen – Prüfer und Katalogpfleger stehen mit Namen in Journal und Protokollen."


def _rechte_lesen(d, basis):
    """Stufen aus der Anfrage über den Bestand legen. Nur bekannte Module, nur 0/1/2 – ein Tippfehler
    verteilt keine Rechte. Verwaltung kennt kein Mitglied, und Verwaltung im Modul Verwaltung zieht
    alle anderen Module auf Verwaltung: So steht in der Matrix, was gilt.

    Die Stufe im Modul Material wird übergangen: Rechte am Bestand gibt es seit Phase 2 nur über Freigaben je Ordner
    (Bestand → Ordner → Bearbeiten → Freigaben). Die Spalte recht_material behält ihren Wert als Rückweg – außer wie
    bisher bei Verwaltung, die alle Module auf Verwaltung zieht."""
    neu = dict(basis)
    angaben = d.get("rechte")
    if not isinstance(angaben, dict):
        raise ValueError("„rechte“ muss ein Objekt mit den Modulen sein.")
    for modul, wert in angaben.items():
        if modul not in MODULE:
            raise ValueError(f"Unbekanntes Modul „{modul}“.")
        if modul == "material":
            current_app.logger.warning("Nutzerverwaltung: Stufe im Modul Material (%r) übergangen – Rechte am Bestand "
                                       "vergeben Freigaben je Ordner.", wert)
            continue
        if isinstance(wert, bool) or wert not in STUFEN:
            raise ValueError("Eine Stufe ist 0 (kein Zugriff), 1 (Mitglied) oder 2 (Verwaltung).")
        if modul == "verwaltung" and wert == 1:
            raise ValueError("Im Modul Verwaltung gibt es nur „kein Zugriff“ oder „Verwaltung“.")
        neu[modul] = wert
    if neu["verwaltung"] == VERWALTUNG:
        neu = {m: VERWALTUNG for m in MODULE}
    return neu


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


@bp.get("/einstellungen")
@admin_required
def einstellungen_lesen():
    """Alle einstellbaren Werte samt Herkunft. Das Mailkennwort ist nie dabei."""
    return jsonify(**einstellungen.als_json(), aus=einstellungen.abgeschaltet())


@bp.put("/einstellungen")
@admin_required
def einstellungen_schreiben():
    """Werte speichern. Sie gelten ab der nächsten Anfrage, auch in den anderen Arbeitsprozessen.

    Unbekannte Schlüssel werden übergangen – so kann kein Aufruf von außen beliebige Werte in
    die Konfiguration schreiben."""
    d = json_body()
    try:
        anzahl = einstellungen.speichern(d.get("werte") or {}, current_user()["id"])
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    einstellungen.anwenden()
    current_app.logger.info("Einstellungen geändert von %s: %s Felder", current_user()["email"], anzahl)
    return jsonify(**einstellungen.als_json(), gespeichert=anzahl)


@bp.delete("/einstellungen/<schluessel>")
@admin_required
def einstellungen_zuruecksetzen(schluessel):
    """Einen Wert wieder aus .env und Vorgabe holen."""
    if not einstellungen.zuruecksetzen(schluessel):
        return jsonify(error="Diese Einstellung gibt es nicht."), 404
    current_app.logger.info("Einstellung %s von %s zurückgesetzt", schluessel, current_user()["email"])
    return jsonify(**einstellungen.als_json())


@bp.get("/videos")
@admin_required
def videos():
    """Stand der Videopflege – ob im Hintergrund noch Bestandsvideos gewandelt werden."""
    return jsonify(medienpflege.stand(current_app))


@bp.get("/users")
@admin_required
def list_users():
    """Alle Konten mit ihren Inhalten. Im Modul Material zusätzlich die Zahl gültiger Freigaben (mat_freigaben) und die
    stillgelegte Stufe aus Phase 1 (mat_stufe_alt, für die Marke „ohne Freigabe“). Die Zahlen und die wirksame Stufe
    kommen für alle Konten aus einer gruppierten Abfrage – nicht je Konto eine."""
    rows = db.query(
        "SELECT u.*, (SELECT COUNT(*) FROM albums a WHERE a.owner_id = u.id) AS album_count, "
        "(SELECT COUNT(*) FROM photos p WHERE p.owner_id = u.id) AS photo_count, "
        # Artikel, die der Nutzer angelegt hat – ohne den Papierkorb, der zählt nicht als Inhalt.
        "(SELECT COUNT(*) FROM wiki_pages w WHERE w.created_by = u.id AND w.deleted_at IS NULL) AS page_count "
        "FROM users u ORDER BY (u.status = 'pending') DESC, u.created_at")
    zahlen = mat_freigaben.zahlen_je_konto()
    mat_freigaben.stufen_vormerken(rows, zahlen)
    out = []
    for r in rows:
        u = public_user(r)
        u["album_count"], u["photo_count"], u["page_count"] = r["album_count"], r["photo_count"], r["page_count"]
        u["last_login"] = r["last_login"]
        u["mat_freigaben"] = zahlen.get(r["id"], (0,))[0]
        u["mat_stufe_alt"] = int(r["recht_material"] or 0)
        out.append(u)
    return jsonify(users=out)


@bp.post("/users")
@admin_required
def create_user():
    """Ein Konto anlegen. Die Stufe im Modul Material wird übergangen (_rechte_lesen); die Häkchen Prüfer und Katalog
    gibt es nur mit Namen. Der Rolleneintrag im Journal des Moduls trägt keine E-Mail – er bleibt auch nach dem Löschen
    des Kontos stehen."""
    d = json_body()
    email = (d.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify(error="Bitte eine gültige E-Mail-Adresse angeben."), 400
    if db.query("SELECT 1 FROM users WHERE email = ?", (email,), one=True):
        return jsonify(error="Für diese E-Mail-Adresse gibt es bereits ein Konto."), 409
    pw = d.get("password") or secrets.token_urlsafe(12)
    if len(pw) < MIN_PW:
        return jsonify(error=f"Das Passwort muss mindestens {MIN_PW} Zeichen lang sein."), 400
    try:
        rechte = _rechte_lesen(d, VORGABE) if "rechte" in d else dict(VORGABE)
        mat = rollen_lesen(d, {}, rechte)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Abgelehnt as exc:
        return jsonify(error=str(exc)), exc.code
    name = (d.get("name") or "").strip()
    if (mat["mat_pruefer"] or mat["mat_katalog"]) and not name:
        return jsonify(error=OHNE_NAMEN), 400
    spalten = [f"recht_{m}" for m in MODULE] + list(mat)
    with db.transaction():
        uid = db.execute(
            f"INSERT INTO users (email, password_hash, name, gliederung, phone, {', '.join(spalten)}, created_at) "
            f"VALUES ({','.join('?' * (6 + len(spalten)))})",
            (email, generate_password_hash(pw), name, (d.get("gliederung") or "").strip(),
             (d.get("phone") or "").strip(), *(rechte[m] for m in MODULE), *mat.values(), db.now()))
        neu = dict(mat, recht_material=rechte["material"])
        if neu["recht_material"] or neu["mat_pruefer"] or neu["mat_katalog"]:
            mat_journal.eintragen("user", uid, "rollen", None, neu)
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
    if "rechte" in d or any(k in d for k in ("mat_pruefer", "mat_katalog", "urkundennummer")):
        rechte = {m: u[f"recht_{m}"] for m in MODULE}
        try:
            if "rechte" in d:
                rechte = _rechte_lesen(d, rechte)
            mat = rollen_lesen(d, u, rechte)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Abgelehnt as exc:
            return jsonify(error=str(exc)), exc.code
        # Wer sich selbst die Verwaltung nähme, käme an diese Seite nicht mehr heran – und wäre das
        # letzte Verwaltungskonto, stünde die Anwendung ohne da.
        if uid == current_user()["id"] and rechte["verwaltung"] < VERWALTUNG:
            return jsonify(error="Du kannst dir nicht selbst die Verwaltungsrechte entziehen."), 400
        for m in MODULE:
            vals[f"recht_{m}"] = rechte[m]
        vals.update(mat)
    # Die Häkchen Prüfer und Katalog nur mit Namen – geprüft, wenn eines neu dazukommt oder der Name sich ändert, damit
    # ein namenloses Konto aus der Zeit davor sich weiter bearbeiten lässt (etwa um das Häkchen zu nehmen).
    name = vals.get("name", u["name"] or "")
    haekchen = [k for k in ("mat_pruefer", "mat_katalog") if vals.get(k, u[k])]
    if haekchen and not name and (name != (u["name"] or "") or any(not u[k] for k in haekchen)):
        return jsonify(error=OHNE_NAMEN), 400
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
        with db.transaction():
            db.execute(f"UPDATE users SET {sets} WHERE id = ?", (*vals.values(), uid))
            # Wer Prüfer ist und mit welcher Urkundennummer, gehört zur Nachvollziehbarkeit der Prüfungen.
            mat_journal.aenderung("user", uid, {k: u[k] for k in MATERIAL_SPALTEN},
                                  {k: vals.get(k, u[k]) for k in MATERIAL_SPALTEN}, action="rollen")
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
    # Die Schreibsperre von Anfang an: Zwischen dem Aufräumen im Modul Material und dem Löschen
    # soll keine neue Freigabe oder Zuordnung an das Konto dazukommen.
    with db.transaction(sofort=True):
        # Modul Material (Löschkonzept): Journal je Freigabe und Zuordnung, Zuordnungen lösen,
        # Entwürfe, Meldungen und Suchprotokoll ohne Namen – vor dem Löschen, solange der
        # Kontoverweis noch auflösbar ist.
        mat_loeschung.konto_loeschen_vorbereiten(uid)
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


@bp.get("/users/<int:uid>/material-folgen")
@admin_required
def material_folgen(uid):
    """Was das Löschen des Kontos im Modul Material bewirkt – Zahlen für den Dialog „Löschen“: Freigaben, Zuordnungen,
    offene Entwürfe und abgeschlossene Prüfungen (material.services.loeschung.folgen)."""
    if not db.query("SELECT 1 FROM users WHERE id = ?", (uid,), one=True):
        return jsonify(error="Nutzer nicht gefunden"), 404
    return jsonify(mat_loeschung.folgen(uid))


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
