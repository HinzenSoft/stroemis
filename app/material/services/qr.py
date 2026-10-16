"""QR-Kennung eines Artikels und die Adresse, die auf Etikett, NFC- oder RFID-Tag steht.

Die Kennung ist zufällig und lang genug, dass sich keine fremden Artikel erraten lassen; sie verrät
nichts über Gliederung oder Inventarnummer. Das Etikett selbst (segno, Bogen als PDF) kommt mit
Lieferung 4 – die Adresse gilt schon jetzt und lässt sich am Artikel kopieren."""
import secrets

from flask import current_app

PFAD = "/m/"


def neues_token():
    return secrets.token_urlsafe(12)          # 16 Zeichen, 96 Bit Zufall


def adresse(token):
    """Vollständige Adresse für das Etikett. Der Hostname geht in Punycode hinaus (xn--…): Nicht
    jede Kamera-App öffnet einen Link mit Umlaut, jede aber die Punycode-Form."""
    basis = (current_app.config.get("BASE_URL") or "").rstrip("/")
    try:
        schema, rest = basis.split("://", 1)
        host, _, pfad = rest.partition("/")
        basis = f"{schema}://{host.encode('idna').decode()}" + (f"/{pfad}" if pfad else "")
    except (ValueError, UnicodeError):
        pass
    return f"{basis}{PFAD}{token}"
