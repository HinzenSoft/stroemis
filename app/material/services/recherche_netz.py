"""Downloads der Recherche per Claude API (services/recherche.py, Entwurf 3.4): Claude nennt nur Adressen, geladen wird
hier – vom Server, nach festen Regeln, nie von Claude.

  - Nur https auf Port 443 (PORTE) und nur von den bestätigten Herstellerdomains (oder deren Subdomains). Aus dem
    Webarchiv (web.archive.org, E5 B) nur, wenn die archivierte Original-Adresse auf einer Herstellerdomain liegt –
    geladen wird dann die Roh-Fassung (/web/<Zeitstempel>id_/<Adresse>) ohne die Leiste des Archivs. Händlerseiten nie.
    Adressen mit Backslash, Leer- oder Steuerzeichen oder Zugangsdaten gelten nirgends (sauber() – Browser lesen sie
    anders als urlsplit), auch nicht als Original im Archiv; geladen wird eine aus den geprüften Teilen neu
    zusammengesetzte Adresse, nie der Rohtext.
  - Gegen SSRF: Der Name wird aufgelöst (AUFLOESER, Tests setzen ihn), jede Adresse muss öffentlich sein (keine
    privaten, Loopback-, Link-Local-, Multicast- oder reservierten Netze, kein NAT64 und kein IPv4-kompatibles IPv6),
    und verbunden wird mit genau der geprüften Adresse – der TLS-Name bleibt der Host, das Zertifikat wird gegen ihn
    geprüft. Weiterleitungen von Hand, höchstens WEITERLEITUNGEN, jede neu geprüft. Keine Cookies, kein Referer, ein
    neutraler User-Agent.
  - Zeitgrenzen: Verbindung VERBINDEN_SEK, je Datei insgesamt GESAMT_SEK – auch gegen einen Server, der Byte für Byte
    tröpfelt: gelesen wird mit read1 (kehrt nach jedem Empfang zurück), die Frist gilt nach jedem Stück und schon für
    die Kopfzeilen, und ein Wächter beendet den Socket, wenn sie um ist. Der Lauf erfährt den Socket (merken) und kann
    ihn bei „Abbrechen“ oder seiner Zeitgrenze beenden; pruefen (Abbruch-Prüfer des Laufs) läuft nach jedem Stück.
    Größe beim Lesen gezählt (nicht nach Content-Length); zu groß bricht ab, zu kurz angekommen auch.
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
import threading
import time
from collections import namedtuple
from urllib.parse import urljoin, urlsplit

from . import katalog

AGENT = "stroemis.de Katalogrecherche"
VERBINDEN_SEK = 10
GESAMT_SEK = 60
WEITERLEITUNGEN = 3
ARCHIV = "web.archive.org"
PORTE = (443,)                          # Tests ergänzen den Port ihres lokalen Servers
ZEIT_UM = "Zeitüberschreitung beim Laden."
# Endungen, unter denen viele Fremde eigene Domains bzw. Seiten haben – nie selbst eine Herstellerdomain, sonst gälte
# jede Seite darunter als Hersteller (Prüfung Sicherheit vom 21.11.2026, Hinweis 3). Eine kleine feste Liste, keine
# Public Suffix List: Länderendungen zweiter Stufe und gemeinsam genutzte Plattformen.
GEMEINSAME_SUFFIXE = frozenset("""
    co.uk org.uk me.uk ltd.uk plc.uk ac.uk gov.uk com.au net.au org.au co.nz co.jp ne.jp or.jp co.at or.at co.za
    com.br com.cn com.tr co.in com.mx com.ar co.kr com.tw com.hk com.sg co.il com.pl com.es com.ua uk.com us.com eu.com
    github.io gitlab.io gitbook.io readthedocs.io blogspot.com wordpress.com wixsite.com jimdofree.com squarespace.com
    weebly.com tumblr.com myshopify.com notion.site amazonaws.com cloudfront.net azurewebsites.net blob.core.windows.net
    sharepoint.com dropbox.com dropboxusercontent.com googleusercontent.com storage.googleapis.com appspot.com
    firebaseapp.com web.app herokuapp.com netlify.app vercel.app pages.dev r2.dev onrender.com fly.dev
""".split())
_UNSAUBER = re.compile(r"[\\\s\x00-\x1f\x7f-\x9f]")
# NAT64 (RFC 6052/8215) und IPv4-kompatibles IPv6 (::a.b.c.d) tragen eine IPv4-Adresse in sich – ipaddress hält sie
# für öffentlich, ein Netz mit NAT64 führte aber zu ihr (etwa 64:ff9b::a9fe:a9fe → 169.254.169.254).
_NICHT_OEFFENTLICH = tuple(ipaddress.ip_network(n) for n in ("64:ff9b::/96", "64:ff9b:1::/48", "::/96"))
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


def _domain_roh(wert):
    """Eingabe → Host ohne Schema, Pfad, Port und „www.“, klein, IDNA (ungeprüft) – oder None."""
    s = (wert or "").strip().lower()
    if "://" in s:
        try:
            s = urlsplit(s).hostname or ""
        except ValueError:
            return None
    s = s.split("/")[0].split(":")[0].rstrip(".")
    try:
        s = s.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    return s[4:] if s.startswith("www.") else s


def domain_lesen(wert):
    """Eine Herstellerdomain aus der Eingabe: ohne Schema, Pfad und „www.“, klein, IDNA – oder None (auch für eine
    gemeinsame Endung wie github.io oder co.uk)."""
    s = _domain_roh(wert)
    if not s or not _HOST.match(s) or re.fullmatch(r"[\d.]+", s) or s == ARCHIV or s.endswith(".archive.org") \
            or s in GEMEINSAME_SUFFIXE:
        return None
    return s


def gemeinsam(wert):
    """Ist die Eingabe eine gemeinsame Endung (github.io, co.uk …) – für einen eigenen Satz beim Bestätigen."""
    return _domain_roh(wert) in GEMEINSAME_SUFFIXE


def sauber(url):
    """Eine Adresse, die überall gleich gelesen wird: http(s), mit Host, ohne Zugangsdaten, ohne Backslash, Leer- oder
    Steuerzeichen, mit lesbarem Port – sonst False. (Bei „https://a.test\\@b.test/“ liest urlsplit den Host b.test,
    ein Browser a.test.)"""
    if not isinstance(url, str) or _UNSAUBER.search(url):
        return False
    try:
        t = urlsplit(url)
        _ = t.port                              # wirft bei einem unlesbaren Port
    except ValueError:
        return False
    return t.scheme in ("http", "https") and bool(t.hostname) and t.username is None and t.password is None


def _ursprung(t):
    """„https://host[:port]“ aus geprüften Teilen (urlsplit) – ohne Zugangsdaten."""
    standard = {"https": 443, "http": 80}.get(t.scheme)
    return f"{t.scheme}://{t.hostname}" + (f":{t.port}" if t.port and t.port != standard else "")


def _zusammensetzen(t):
    """Die Adresse aus geprüften Teilen (urlsplit) – ohne Zugangsdaten und Anker."""
    return _ursprung(t) + (t.path or "/") + (f"?{t.query}" if t.query else "")


def host_erlaubt(host, domains):
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def archiv_original(url):
    """(Zeitstempel, Original-Adresse) einer Adresse im Webarchiv – sonst None. Beide müssen sauber sein; die
    Original-Adresse kommt neu zusammengesetzt zurück."""
    if not sauber(url):
        return None
    t = urlsplit(url)
    if (t.hostname or "").lower() != ARCHIV:
        return None
    m = _ARCHIV_PFAD.match(t.path + (("?" + t.query) if t.query else ""))
    if not m or not sauber(m.group(2)):
        return None
    return m.group(1), _zusammensetzen(urlsplit(m.group(2)))


def archiv_stand(zeitstempel):
    """„20240501123000“ → „2024-05-01“ (so weit der Zeitstempel reicht)."""
    z = zeitstempel or ""
    return "-".join(x for x in (z[:4], z[4:6], z[6:8]) if x)


def quelle(url, domains):
    """Woher ein Wert stammt: „hersteller“ (Herstellerdomain), „webarchiv“ (Archivstand einer Herstelleradresse) oder
    „fremd“ (Händler, sonstige Seiten – nur zur Identifikation)."""
    if not sauber(url):
        return "fremd"
    t = urlsplit(url)
    if host_erlaubt(t.hostname, domains):
        return "hersteller"
    a = archiv_original(url)
    if a and host_erlaubt(urlsplit(a[1]).hostname, domains):
        return "webarchiv"
    return "fremd"


def _ziel(url, domains):
    """Die Adresse, die wirklich geladen wird – geprüft: https auf Port 443, Herstellerdomain oder deren Archivstand
    (dann die Roh-Fassung), aus den geprüften Teilen neu zusammengesetzt. Wirft Fehler."""
    try:
        t = urlsplit(url or "")
        port = t.port
    except ValueError:
        raise Fehler("Keine gültige Adresse.")
    if t.scheme != "https" or not t.hostname:
        raise Fehler("Nur https-Adressen werden geladen.")
    if t.username is not None or t.password is not None:
        raise Fehler("Adressen mit Zugangsdaten werden nicht geladen.")
    if not sauber(url):
        raise Fehler("Keine gültige Adresse (Leer- oder Steuerzeichen, Backslash).")
    if (port or 443) not in PORTE:
        raise Fehler("Nur Port 443 wird geladen.")
    q = quelle(url, domains)
    if q == "hersteller":
        return _zusammensetzen(t)
    if q == "webarchiv":
        stempel, original = archiv_original(url)
        return f"{_ursprung(t)}/web/{stempel}id_/{original}"
    raise Fehler("Nicht von einer bestätigten Herstellerseite – nicht geladen.")


def oeffentlich(ip):
    """Ist die Adresse im öffentlichen Netz? Private, Loopback-, Link-Local-, Multicast-, reservierte und gemeinsam
    genutzte Netze nicht (ipaddress.is_global); IPv4 in IPv6 wird als IPv4 geprüft."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address):
        if a.ipv4_mapped:
            a = a.ipv4_mapped
        elif any(a in n for n in _NICHT_OEFFENTLICH):
            return False
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
    """HTTPS zu genau der geprüften Adresse; Name für SNI und Zertifikat bleibt der Host. merken(sock) erfährt den
    Socket (erst den rohen, für den TLS-Handschlag, dann den mit TLS); beenden() weckt ihn aus einem anderen Thread.
    tls hält den Socket fest: Mit „Connection: close“ gibt http.client ihn nach getresponse() an die Antwort weiter und
    setzt sock auf None – gelesen wird aber weiter auf ihm."""

    def __init__(self, host, ip, port, kontext, merken=None, frist=None):
        super().__init__(host, port, timeout=VERBINDEN_SEK, context=kontext)
        self._ip = ip
        self._merken = merken
        self._frist = frist
        self._roh = None
        self.tls = None

    def connect(self):
        zeit = VERBINDEN_SEK if self._frist is None else max(0.1, min(VERBINDEN_SEK, self._frist - time.monotonic()))
        roh = socket.create_connection((self._ip, self.port), zeit)
        self._roh = roh
        if self._merken:
            self._merken(roh)
        try:
            self.sock = self.tls = self._context.wrap_socket(roh, server_hostname=self.host)
        except BaseException:
            roh.close()
            raise
        if self._merken:
            self._merken(self.tls)

    def beenden(self):
        for s in (self.tls, self._roh):
            if s is not None:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                    return
                except (OSError, ValueError):        # schon zu bzw. vom TLS-Socket übernommen (detach)
                    continue


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


def _zeit(frist):
    """Die Zeitgrenze je Empfang: höchstens VERBINDEN_SEK, nie über die Frist hinaus."""
    return max(0.1, min(VERBINDEN_SEK, frist - time.monotonic()))


def _zeitgrenze(verbindung, frist, antwort=None):
    """Die Zeitgrenze je Empfang auf den TLS-Socket setzen – nicht mehr, wenn die Antwort schon fertig gelesen ist
    (dann hat http.client den Socket geschlossen)."""
    if verbindung.tls is None or (antwort is not None and antwort.isclosed()):
        return
    try:
        verbindung.tls.settimeout(_zeit(frist))
    except OSError:
        pass


def herunterladen(url, domains, ordner, bild=False, frist=None, pruefen=None, merken=None):
    """Eine Datei laden, prüfen und im Ordner des Laufs ablegen → Datei. bild: nur Bilder (Produktbild), sonst
    Dokumente (PDF oder Bild). frist: time.monotonic(), bis wann es fertig sein muss (sonst GESAMT_SEK ab jetzt).
    pruefen(): Abbruch-Prüfer des Laufs (wirft, wenn er abgebrochen ist) – vor jeder Verbindung und nach jedem Stück;
    merken(sock): der Lauf erfährt den offenen Socket (None am Ende), um ihn beim Abbruch zu beenden. Wirft Fehler mit
    einem Satz für den Vorschlag."""
    arten = BILD_TYPEN if bild else katalog.DOK_TYPEN
    grenze = katalog.BILD_MAX_BYTES if bild else katalog.DOK_MAX_BYTES
    frist = frist or (time.monotonic() + GESAMT_SEK)
    pruefen = pruefen or (lambda: None)
    adresse = url
    for _ in range(WEITERLEITUNGEN + 1):
        ziel = _ziel(adresse, domains)
        t = urlsplit(ziel)
        port = t.port or 443
        pruefen()
        if time.monotonic() >= frist:
            raise Fehler(ZEIT_UM)
        ip = _aufloesen(t.hostname, port)
        verbindung = _Verbindung(t.hostname, ip, port, KONTEXT(), merken, frist)
        # Der Wächter beendet den Socket, wenn die Frist um ist – auch mitten im TLS-Handschlag oder in Kopfzeilen,
        # die ein Server Byte für Byte schickt (die Zeitgrenze des Sockets gilt nur je Empfang).
        waechter = threading.Timer(max(0.0, frist - time.monotonic()), verbindung.beenden)
        waechter.daemon = True
        waechter.start()
        try:
            pfad = (t.path or "/") + (f"?{t.query}" if t.query else "")
            verbindung.request("GET", pfad, headers={"User-Agent": AGENT, "Accept": "*/*",
                                                    "Accept-Encoding": "identity", "Connection": "close"})
            _zeitgrenze(verbindung, frist)
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
            return _ablegen(antwort, verbindung, ordner, arten, grenze, frist, ziel, pruefen)
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            pruefen()                           # beendet vom Lauf (Abbrechen, Zeitgrenze): dessen Ausnahme
            if isinstance(exc, (socket.timeout, TimeoutError)) or time.monotonic() >= frist:
                raise Fehler(ZEIT_UM)
            raise Fehler(f"Laden gescheitert ({type(exc).__name__}) – bitte von Hand hochladen.")
        finally:
            waechter.cancel()
            if merken:
                merken(None)
            verbindung.close()
    raise Fehler(f"Mehr als {WEITERLEITUNGEN} Weiterleitungen – nicht geladen.")


def _ablegen(antwort, verbindung, ordner, arten, grenze, frist, url, pruefen):
    zwischen = os.path.join(ordner, ".lade-" + secrets.token_hex(8))
    summe, groesse, kopf = hashlib.sha256(), 0, b""
    fd = os.open(zwischen, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            while True:
                pruefen()
                if time.monotonic() >= frist:
                    raise Fehler(ZEIT_UM)
                _zeitgrenze(verbindung, frist, antwort)
                # read1 kehrt nach einem Empfang zurück; read(n) wartete, bis n Bytes da sind (Befund 1).
                stueck = antwort.read1(64 * 1024)
                if not stueck:
                    break
                groesse += len(stueck)
                if groesse > grenze:
                    raise Fehler(f"Die Datei ist größer als {grenze // (1024 * 1024)} MB.")
                if len(kopf) < 16:
                    kopf = (kopf + stueck)[:16]
                summe.update(stueck)
                fh.write(stueck)
        # Leer zurück kam read1 auch, weil der Wächter oder der Lauf den Socket beendet hat – oder der Server zu früh
        # aufhörte (read1 meldet das nicht wie read mit IncompleteRead).
        pruefen()
        if time.monotonic() >= frist:
            raise Fehler(ZEIT_UM)
        if antwort.length:
            raise Fehler("Die Datei kam nicht vollständig an – bitte von Hand hochladen.")
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
