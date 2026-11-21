"""Downloads der Recherche per Claude API (services/recherche.py, Entwurf 3.4): Claude nennt nur Adressen, geladen wird
hier – vom Server, nach festen Regeln, nie von Claude.

  - Nur https und nur von den bestätigten Herstellerdomains (oder deren Subdomains). Aus dem Webarchiv
    (web.archive.org, E5 B) nur, wenn die archivierte Original-Adresse auf einer Herstellerdomain liegt – geladen wird
    dann die Roh-Fassung (/web/<Zeitstempel>id_/<Adresse>) ohne die Leiste des Archivs. Händlerseiten nie.
  - Gegen SSRF: Der Name wird aufgelöst (AUFLOESER, Tests setzen ihn), jede Adresse muss öffentlich sein (keine
    privaten, Loopback-, Link-Local-, Multicast- oder reservierten Netze), und verbunden wird mit genau der geprüften
    Adresse – der TLS-Name bleibt der Host, das Zertifikat wird gegen ihn geprüft. Weiterleitungen von Hand, höchstens
    WEITERLEITUNGEN, jede neu geprüft. Keine Cookies, kein Referer, ein neutraler User-Agent.
  - Zeitgrenzen: Verbindung VERBINDEN_SEK, je Datei insgesamt GESAMT_SEK. Größe beim Lesen gezählt (nicht nach
    Content-Length); zu groß bricht ab.
  - Der Typ zählt nur nach dem Inhalt (Magic Bytes wie katalog.DOK_TYPEN): PDF, JPEG, PNG, WebP. Eine HTML-Seite statt
    der Datei (Sperre, JavaScript) ist ein Fehler mit dem Hinweis „bitte von Hand hochladen“. Ein PDF muss sich mit
    pypdf öffnen lassen (verschlüsselt mit leerem Kennwort geht). Nichts wird ausgeführt oder entpackt.
  - Abgelegt im Ordner des Laufs (ki.ordner) unter <SHA-256><Endung>, 0600, über eine Zwischendatei mit Punkt und
    os.replace."""
import hashlib
import http.client
import ipaddress
import os
import re
import secrets
import socket
import ssl
import time
from collections import namedtuple
from urllib.parse import urljoin, urlsplit

from . import katalog

AGENT = "stroemis.de Katalogrecherche"
VERBINDEN_SEK = 10
GESAMT_SEK = 60
WEITERLEITUNGEN = 3
ARCHIV = "web.archive.org"
# /web/<Zeitstempel>[<Kennung>_]/<Original-Adresse> – die Kennung (id_, im_, if_ …) wählt die Darstellung des Archivs.
_ARCHIV_PFAD = re.compile(r"^/web/(\d{4,14})(?:[a-z]{2}_)?/(https?://.+)$", re.IGNORECASE)
_HOST = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
BILD_TYPEN = {k: v for k, v in katalog.DOK_TYPEN.items() if k != ".pdf"}
SEITE_STATT_DATEI = "Seite statt Datei (Sperre oder JavaScript) – bitte von Hand hochladen."

AUFLOESER = socket.getaddrinfo          # Tests setzen einen eigenen Auflöser ein
KONTEXT = ssl.create_default_context    # Tests: ein Kontext, der ihrem Zertifikat traut

Datei = namedtuple("Datei", "pfad sha256 mime ext groesse seiten url")


class Fehler(Exception):
    """Ein Download, der nicht klappt – der Text steht so im Vorschlag (mit dem Link zum Hochladen von Hand)."""


def domain_lesen(wert):
    """Eine Herstellerdomain aus der Eingabe: ohne Schema, Pfad und „www.“, klein, IDNA – oder None."""
    s = (wert or "").strip().lower()
    if "://" in s:
        s = urlsplit(s).hostname or ""
    s = s.split("/")[0].split(":")[0].rstrip(".")
    try:
        s = s.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if s.startswith("www."):
        s = s[4:]
    if not _HOST.match(s) or re.fullmatch(r"[\d.]+", s) or s == ARCHIV or s.endswith(".archive.org"):
        return None
    return s


def host_erlaubt(host, domains):
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def archiv_original(url):
    """(Zeitstempel, Original-Adresse) einer Adresse im Webarchiv – sonst None."""
    t = urlsplit(url or "")
    if (t.hostname or "").lower() != ARCHIV:
        return None
    m = _ARCHIV_PFAD.match(t.path + (("?" + t.query) if t.query else ""))
    return (m.group(1), m.group(2)) if m else None


def archiv_stand(zeitstempel):
    """„20240501123000“ → „2024-05-01“ (so weit der Zeitstempel reicht)."""
    z = zeitstempel or ""
    return "-".join(x for x in (z[:4], z[4:6], z[6:8]) if x)


def quelle(url, domains):
    """Woher ein Wert stammt: „hersteller“ (Herstellerdomain), „webarchiv“ (Archivstand einer Herstelleradresse) oder
    „fremd“ (Händler, sonstige Seiten – nur zur Identifikation)."""
    try:
        t = urlsplit(url or "")
    except ValueError:
        return "fremd"
    if t.scheme not in ("http", "https"):
        return "fremd"
    if host_erlaubt(t.hostname, domains):
        return "hersteller"
    a = archiv_original(url)
    if a and host_erlaubt(urlsplit(a[1]).hostname, domains):
        return "webarchiv"
    return "fremd"


def _ziel(url, domains):
    """Die Adresse, die wirklich geladen wird – geprüft: https, Herstellerdomain oder deren Archivstand (dann die
    Roh-Fassung). Wirft Fehler."""
    try:
        t = urlsplit(url or "")
    except ValueError:
        raise Fehler("Keine gültige Adresse.")
    if t.scheme != "https" or not t.hostname:
        raise Fehler("Nur https-Adressen werden geladen.")
    if t.username or t.password:
        raise Fehler("Adressen mit Zugangsdaten werden nicht geladen.")
    q = quelle(url, domains)
    if q == "hersteller":
        return url
    if q == "webarchiv":
        stempel, original = archiv_original(url)
        return f"https://{t.netloc}/web/{stempel}id_/{original}"
    raise Fehler("Nicht von einer bestätigten Herstellerseite – nicht geladen.")


def oeffentlich(ip):
    """Ist die Adresse im öffentlichen Netz? Private, Loopback-, Link-Local-, Multicast-, reservierte und gemeinsam
    genutzte Netze nicht (ipaddress.is_global); IPv4 in IPv6 wird als IPv4 geprüft."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_global and not a.is_multicast


ADRESSE_ERLAUBT = oeffentlich           # Tests lassen für ihren lokalen Server 127.0.0.1 zu


def _aufloesen(host, port):
    try:
        treffer = AUFLOESER(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError, UnicodeError):
        raise Fehler(f"Der Name „{host}“ lässt sich nicht auflösen.")
    ips = [t[4][0] for t in treffer]
    if not ips:
        raise Fehler(f"Der Name „{host}“ lässt sich nicht auflösen.")
    if not all(ADRESSE_ERLAUBT(ip) for ip in ips):
        raise Fehler(f"„{host}“ zeigt auf eine nicht öffentliche Adresse – nicht geladen.")
    return ips[0]


class _Verbindung(http.client.HTTPSConnection):
    """HTTPS zu genau der geprüften Adresse; Name für SNI und Zertifikat bleibt der Host."""

    def __init__(self, host, ip, port, kontext):
        super().__init__(host, port, timeout=VERBINDEN_SEK, context=kontext)
        self._ip = ip

    def connect(self):
        roh = socket.create_connection((self._ip, self.port), VERBINDEN_SEK)
        try:
            self.sock = self._context.wrap_socket(roh, server_hostname=self.host)
        except BaseException:
            roh.close()
            raise


def _entfernen(pfad):
    try:
        os.remove(pfad)
    except OSError:
        pass


def _art(kopf, arten):
    for ext, (mime, kennungen) in arten.items():
        if any(kopf.startswith(k) for k in kennungen) and (ext != ".webp" or kopf[8:12] == b"WEBP"):
            return ext, mime
    return None


def pdf_seiten(pfad):
    """Seitenzahl eines PDF (verschlüsselt mit leerem Kennwort geht) – None, wenn es sich nicht öffnen lässt."""
    from pypdf import PdfReader
    try:
        r = PdfReader(pfad)
        if r.is_encrypted and not r.decrypt(""):
            return None
        return len(r.pages)
    except Exception:                            # noqa: BLE001 – kaputte PDFs werfen alles Mögliche
        return None


def herunterladen(url, domains, ordner, bild=False, frist=None):
    """Eine Datei laden, prüfen und im Ordner des Laufs ablegen → Datei. bild: nur Bilder (Produktbild), sonst
    Dokumente (PDF oder Bild). frist: time.monotonic(), bis wann es fertig sein muss (sonst GESAMT_SEK ab jetzt).
    Wirft Fehler mit einem Satz für den Vorschlag."""
    arten = BILD_TYPEN if bild else katalog.DOK_TYPEN
    grenze = katalog.BILD_MAX_BYTES if bild else katalog.DOK_MAX_BYTES
    frist = frist or (time.monotonic() + GESAMT_SEK)
    adresse = url
    for _ in range(WEITERLEITUNGEN + 1):
        ziel = _ziel(adresse, domains)
        t = urlsplit(ziel)
        port = t.port or 443
        ip = _aufloesen(t.hostname, port)
        verbindung = _Verbindung(t.hostname, ip, port, KONTEXT())
        try:
            pfad = (t.path or "/") + (f"?{t.query}" if t.query else "")
            verbindung.request("GET", pfad, headers={"User-Agent": AGENT, "Accept": "*/*",
                                                    "Accept-Encoding": "identity", "Connection": "close"})
            antwort = verbindung.getresponse()
            if antwort.status in (301, 302, 303, 307, 308):
                weiter = antwort.getheader("Location")
                if not weiter:
                    raise Fehler("Weiterleitung ohne Ziel.")
                adresse = urljoin(ziel, weiter.strip())
                continue
            if antwort.status != 200:
                raise Fehler(f"Der Server antwortet mit {antwort.status} – bitte von Hand hochladen.")
            laenge = antwort.getheader("Content-Length")
            if laenge and laenge.strip().isdigit() and int(laenge) > grenze:
                raise Fehler(f"Die Datei ist größer als {grenze // (1024 * 1024)} MB.")
            return _ablegen(antwort, verbindung, ordner, arten, grenze, frist, ziel)
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            if isinstance(exc, (socket.timeout, TimeoutError)):
                raise Fehler("Zeitüberschreitung beim Laden.")
            raise Fehler(f"Laden gescheitert ({type(exc).__name__}) – bitte von Hand hochladen.")
        finally:
            verbindung.close()
    raise Fehler(f"Mehr als {WEITERLEITUNGEN} Weiterleitungen – nicht geladen.")


def _ablegen(antwort, verbindung, ordner, arten, grenze, frist, url):
    zwischen = os.path.join(ordner, ".lade-" + secrets.token_hex(8))
    summe, groesse, kopf = hashlib.sha256(), 0, b""
    fd = os.open(zwischen, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            while True:
                rest = frist - time.monotonic()
                if rest <= 0:
                    raise Fehler("Zeitüberschreitung beim Laden.")
                if verbindung.sock is not None:
                    verbindung.sock.settimeout(max(0.1, min(VERBINDEN_SEK, rest)))
                stueck = antwort.read(64 * 1024)
                if not stueck:
                    break
                groesse += len(stueck)
                if groesse > grenze:
                    raise Fehler(f"Die Datei ist größer als {grenze // (1024 * 1024)} MB.")
                if len(kopf) < 16:
                    kopf = (kopf + stueck)[:16]
                summe.update(stueck)
                fh.write(stueck)
        art = _art(kopf, arten)
        if not art:
            raise Fehler(SEITE_STATT_DATEI if kopf.lstrip()[:1] == b"<" or not kopf
                         else "Unbekannter Dateityp – bitte von Hand hochladen.")
        ext, mime = art
        sha = summe.hexdigest()
        ziel = os.path.join(ordner, sha + ext)
        os.replace(zwischen, ziel)
    except BaseException:
        _entfernen(zwischen)
        raise
    seiten = None
    if ext == ".pdf":
        seiten = pdf_seiten(ziel)
        if seiten is None:
            _entfernen(ziel)
            raise Fehler("Das PDF lässt sich nicht lesen (beschädigt oder verschlüsselt) – bitte von Hand hochladen.")
    return Datei(ziel, sha, mime, ext, groesse, seiten, url)
