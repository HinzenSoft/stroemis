"""E-Mail-Versand. Ohne SMTP_HOST wird die Mail nur ins Log geschrieben (docker logs)."""
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from flask import current_app


def _umschlag_und_domain(cfg):
    """Absender des Umschlags (Return-Path) und die Domain für die Message-ID.

    Der Umschlagabsender entscheidet, gegen welche Domain der Empfänger SPF prüft. Python nimmt
    dafür sonst stillschweigend die Adresse aus "From"; SMTP_ENVELOPE_FROM setzt sie ausdrücklich
    – gebraucht etwa, wenn Rückläufer in ein eigenes Postfach sollen oder der Versanddienst eine
    Adresse seiner eigenen Domain verlangt. Wer nichts angibt, bleibt bei From, und damit liegen
    beide Domains übereinander (das verlangt DMARC)."""
    aus_from = parseaddr(cfg.get("MAIL_FROM") or "")[1]
    umschlag = (cfg.get("SMTP_ENVELOPE_FROM") or "").strip() or aus_from
    # Die Message-ID trägt üblicherweise die Domain des Absenders. Eine fremde Domain darin ist
    # ein Merkmal, auf das Spamfilter achten.
    domain = (aus_from.rsplit("@", 1)[-1] or "").strip() or None
    return umschlag, (domain or None)


def absender(roh):
    """Der From-Kopf aus MAIL_FROM – als Address-Objekt, nicht als Zeichenkette.

    Python kodiert einen Anzeigenamen mit Umlaut sonst nur wortweise: Aus "strömis.de" wurde
    "=?utf-8?q?str=C3=B6mis?=.de" – ein abgeschnittenes kodiertes Wort, das ein Teil der
    Empfänger wörtlich anzeigt. Über Address wird der ganze Name als eine Einheit kodiert."""
    name, adresse = parseaddr(roh)
    if not adresse:
        return roh
    return Address(display_name=name, addr_spec=adresse) if name else Address(addr_spec=adresse)


def _abgewiesen_text(abgewiesen):
    """Die Antwort des Mailservers je Empfänger lesbar machen – sie ist der Grund, aus dem die
    Mail nicht hinausging, und gehört wörtlich ins Log und in den Bericht."""
    teile = []
    for adr, antwort in (abgewiesen or {}).items():
        code, text = antwort if isinstance(antwort, (tuple, list)) and len(antwort) == 2 else ("?", antwort)
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        teile.append(f"{adr}: {code} {text}")
    return "; ".join(teile)


def versand(to, subject, body):
    """Verschickt eine Mail und berichtet, was dabei herauskam: (ok, Meldung).

    Wirft nicht. Die Meldung ist das, was der Mailserver gesagt hat – sie steht im Log und
    hinter „Testmail senden“ in der Nutzerverwaltung. Ohne sie war eine Ablehnung nicht zu
    erkennen: Ein abgewiesener Empfänger kommt nicht als Ausnahme, sondern als Rückgabewert
    von send_message, und der wurde früher weggeworfen."""
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    if not host:
        return False, "SMTP ist nicht eingerichtet (SMTP_HOST fehlt) – die Mail steht nur im Log."

    umschlag, domain = _umschlag_und_domain(cfg)
    msg = EmailMessage()
    msg["From"] = absender(cfg.get("MAIL_FROM") or "")
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    # Ohne Message-ID gilt eine Mail vielen Filtern als verdächtig, und nicht jeder Relay trägt
    # eine nach. Sie muss eindeutig sein; make_msgid sorgt dafür.
    msg["Message-ID"] = make_msgid(domain=domain)
    # Systemmail: kennzeichnet die Nachricht als nicht von Hand geschrieben. Ordentliche
    # Abwesenheitsassistenten antworten darauf nicht – sonst schaukelt sich ein Wechselspiel auf.
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(body)

    port = int(cfg.get("SMTP_PORT") or (465 if cfg.get("SMTP_SSL") else 587))
    try:
        if cfg.get("SMTP_SSL"):
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
        with server:
            server.ehlo()
            if not cfg.get("SMTP_SSL") and cfg.get("SMTP_STARTTLS", True):
                server.starttls()
                server.ehlo()
            if cfg.get("SMTP_USER"):
                server.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD") or "")
            # send_message liefert die Empfänger, die der Server NICHT angenommen hat. Nimmt er
            # keinen einzigen an, wirft es stattdessen – beides ist hier ein Fehlschlag.
            abgewiesen = server.send_message(msg, from_addr=umschlag)
    except smtplib.SMTPAuthenticationError as exc:
        return False, f"Anmeldung am Mailserver abgelehnt ({host}:{port}): {exc}"
    except smtplib.SMTPRecipientsRefused as exc:
        # Kein einziger Empfänger angenommen – dieselbe Auskunft wie unten, nur als Ausnahme.
        return False, f"Der Mailserver hat den Empfänger abgewiesen – {_abgewiesen_text(exc.recipients)}"
    except smtplib.SMTPException as exc:
        return False, f"Der Mailserver hat abgelehnt ({host}:{port}): {exc}"
    except OSError as exc:
        return False, f"Keine Verbindung zum Mailserver {host}:{port}: {exc}"

    if abgewiesen:
        return False, f"Der Mailserver hat den Empfänger abgewiesen – {_abgewiesen_text(abgewiesen)}"
    return True, f"Vom Mailserver {host}:{port} angenommen (Umschlagabsender {umschlag})."


def send_mail(to, subject, body):
    """Verschickt eine Mail. Liefert True, wenn der Mailserver sie angenommen hat.

    Fehler werden protokolliert, nicht geworfen: Keine Meldung an einen Nutzer soll davon
    abhängen, ob gerade ein Mailserver erreichbar ist."""
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        current_app.logger.warning(
            "SMTP nicht konfiguriert – Mail an %s wird nicht verschickt.\nBetreff: %s\n%s", to, subject, body)
        return False
    ok, meldung = versand(to, subject, body)
    if ok:
        current_app.logger.info("Mail an %s: %s", to, meldung)
    else:
        current_app.logger.error("Mail an %s ging nicht hinaus – %s", to, meldung)
    return ok
