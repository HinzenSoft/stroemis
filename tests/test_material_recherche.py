"""Recherche per Claude API an „Produkt melden“ (services/recherche.py, recherche_netz.py, routes_recherche.py; Entscheidungen
vom 21.11.2026):  python tests/test_material_recherche.py  oder  pytest …

Keine echten API-Aufrufe (Attrappe aus test_ki.py), keine echten Downloads: ein lokaler HTTPS-Server mit eigenem
Zertifikat, Namen über einen eingesetzten Auflöser. Geprüft: Downloads (nur https, nur Herstellerdomains und
Subdomains, Webarchiv nur mit Original auf der Herstellerdomain und in der Roh-Fassung, Weiterleitungen auf fremde
Hosts und private Adressen, SSRF-Auflösung auf 127.0.0.1/10.x/169.254.x, HTML statt PDF, falsche Magic Bytes, zu groß
mit und ohne Content-Length, Zeitüberschreitung, kaputtes PDF, gleiche SHA-256); der ganze Lauf über die Routen (was an
die API geht und was nie, Werkzeuge und Parameter, Schemaverstoß mit is_error, Dokumentprüfung, Zusammenführen nach den
Katalogregeln, Dubletten); die Mehrfach-Übernahme (zwei Ausführungen, eine dritte schon im Katalog, Teilfehler bei einer
Datei, Nachladen idempotent); Rechte je Rolle und das Feld „recherche“; Kontingent, „eine app-weit“, Erledigen bricht
ab, Meldung löschen, dev-zuruecksetzen, dev-bestand-leeren, Tageslauf. Alle Namen, Nummern, Normen und Angaben hier
sind Platzhalter."""
import datetime as dt
import io
import json
import os
import re
import socket
import ssl
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ki import SCHLUESSEL, Attrappe, _Strom, einsetzen, nachricht, text, werkzeug  # noqa: E402
from test_material import H, gliederung, jpeg, katalog_grund, mails_abfangen, mails_zurueck, umgebung  # noqa: E402

HOSTS = ("hersteller.test", "cdn.hersteller.test", "web.archive.org", "haendler.test", "intern.hersteller.test",
         "privat.hersteller.test", "linklocal.hersteller.test")


# --- Lokaler HTTPS-Server ---------------------------------------------------------------------------------------------

def pdf(titel, seiten=1):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(seiten):
        w.add_blank_page(width=200, height=200)
    w.add_metadata({"/Title": titel})
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def zertifikat(ordner):
    """Ein selbst signiertes Zertifikat für die Testnamen – geschrieben nach ordner/{cert,key}.pem."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Testserver")])
    jetzt = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(jetzt - dt.timedelta(days=1))
            .not_valid_after(jetzt + dt.timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in HOSTS]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    pfade = os.path.join(ordner, "cert.pem"), os.path.join(ordner, "key.pem")
    with open(pfade[0], "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(pfade[1], "wb") as fh:
        fh.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    return pfade


class Server:
    """HTTPS auf 127.0.0.1 (freier Port). routen: Pfad → (Status, Kopfzeilen, Inhalt | Funktion(handler))."""

    def __init__(self, ordner, routen):
        cert, key = zertifikat(ordner)
        self.cert = cert
        self.routen = routen
        self.abrufe = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                server.abrufe.append((self.headers.get("Host"), self.path, dict(self.headers)))
                ziel = server.routen.get(self.path)
                if ziel is None and self.path.startswith("/web/"):
                    ziel = server.routen.get("/web/*")
                if ziel is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if callable(ziel):
                    return ziel(self)
                status, kopf, inhalt = ziel
                self.send_response(status)
                for k, v in kopf.items():
                    self.send_header(k, v.replace("PORT", str(server.port)))
                if "Content-Length" not in kopf:
                    self.send_header("Content-Length", str(len(inhalt)))
                self.end_headers()
                self.wfile.write(inhalt)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]
        self.faden = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.faden.start()

    def url(self, host, pfad):
        return f"https://{host}:{self.port}{pfad}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def netz_einsetzen(server, privat=None):
    """Auflöser (alle Testnamen → 127.0.0.1, ausgewählte auf private Adressen), Zulassung nur für 127.0.0.1 (sonst die
    echte Regel), ein TLS-Kontext, der dem Testzertifikat traut, und der Port des Servers neben 443. Liefert den alten
    Stand."""
    from app.material.services import recherche_netz as netz
    alt = (netz.AUFLOESER, netz.ADRESSE_ERLAUBT, netz.KONTEXT, netz.PORTE)
    netz.PORTE = (443, server.port)
    privat = privat or {"intern.hersteller.test": "10.0.0.5", "privat.hersteller.test": "192.168.1.2",
                        "linklocal.hersteller.test": "169.254.169.254"}

    def aufloeser(host, port, type=0):
        ip = privat.get(host, "127.0.0.1")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
    netz.AUFLOESER = aufloeser
    netz.ADRESSE_ERLAUBT = lambda ip: ip == "127.0.0.1" or netz.oeffentlich(ip)
    netz.KONTEXT = lambda: ssl.create_default_context(cafile=server.cert)
    return alt


def netz_zurueck(alt):
    from app.material.services import recherche_netz as netz
    netz.AUFLOESER, netz.ADRESSE_ERLAUBT, netz.KONTEXT, netz.PORTE = alt


PDF_A = pdf("Gebrauchsanleitung")
PDF_B = pdf("Konformitaetserklaerung")
PDF_C = pdf("Pruefanweisung alt")
PDF_LANG = pdf("Lange Anleitung", seiten=45)


def _langsam(h):
    h.send_response(200)
    h.send_header("Content-Length", "100000")
    h.end_headers()
    h.wfile.write(b"%PDF-1.4\n")
    h.wfile.flush()
    time.sleep(3)


def _gross_ohne_laenge(h):
    h.send_response(200)
    h.send_header("Connection", "close")
    h.end_headers()
    h.wfile.write(b"%PDF-1.4\n" + b"0" * 6000)


def routen(bild):
    return {
        "/anleitung.pdf": (200, {"Content-Type": "application/pdf"}, PDF_A),
        "/erklaerung.pdf": (200, {"Content-Type": "application/pdf"}, PDF_B),
        "/datenblatt.pdf": (200, {"Content-Type": "application/pdf"}, PDF_A),      # gleicher Inhalt wie die Anleitung
        "/lang.pdf": (200, {"Content-Type": "application/pdf"}, PDF_LANG),
        "/seite.pdf": (200, {"Content-Type": "application/pdf"}, b"<!doctype html><html><body>Bitte anmelden</body>"),
        "/kaputt.pdf": (200, {}, b"%PDF-1.4\nkeine Objekte, kein Ende"),
        "/falsch.png": (200, {"Content-Type": "image/png"}, b"GIF89a" + b"\0" * 40),
        "/bild.jpg": (200, {"Content-Type": "image/jpeg"}, bild),
        "/gross.pdf": (200, {}, b"%PDF-1.4\n" + b"0" * 6000),
        "/gross-ohne-laenge.pdf": _gross_ohne_laenge,
        "/langsam.pdf": _langsam,
        "/weiter": (302, {"Location": "/anleitung.pdf"}, b""),
        "/weiter-fremd": (302, {"Location": "https://haendler.test:PORT/anleitung.pdf"}, b""),
        "/weiter-privat": (302, {"Location": "https://intern.hersteller.test:PORT/anleitung.pdf"}, b""),
        "/weiter-http": (302, {"Location": "http://hersteller.test/anleitung.pdf"}, b""),
        "/schleife": (302, {"Location": "/schleife"}, b""),
        "/fehlt.pdf": (404, {}, b"weg"),
    }


def netz_server(tmp):
    bild = jpeg(60, 40).getvalue()
    r = routen(bild)

    def archiv(h):
        """Webarchiv: nur die Roh-Fassung (…id_/…) liefert die Datei, die Ansicht mit Leiste nicht."""
        roh = re.match(r"^/web/(\d+)id_/(https?://.+)$", h.path)
        inhalt = PDF_C if roh and roh.group(2) == "https://hersteller.test/alt.pdf" else None
        h.send_response(200 if inhalt else 404)
        h.send_header("Content-Length", str(len(inhalt or b"")))
        h.end_headers()
        h.wfile.write(inhalt or b"")
    r["/web/*"] = archiv
    return Server(tmp, r), bild


# --- Downloads -----------------------------------------------------------------------------------------------------

def test_downloads():
    from app.material.services import katalog
    from app.material.services import recherche_netz as netz
    with tempfile.TemporaryDirectory() as tmp:
        ablage = os.path.join(tmp, "ablage")
        os.makedirs(ablage)
        server, bild = netz_server(tmp)
        alt = netz_einsetzen(server)
        domains = ["hersteller.test"]
        try:
            from test_material import make_app
            app = make_app(os.path.join(tmp, "daten"))
            with app.app_context():
                d = netz.herunterladen(server.url("hersteller.test", "/anleitung.pdf"), domains, ablage)
                assert d.ext == ".pdf" and d.seiten == 1 and d.groesse == len(PDF_A) and d.mime == "application/pdf"
                assert os.path.basename(d.pfad) == d.sha256 + ".pdf" and open(d.pfad, "rb").read() == PDF_A
                assert oct(os.stat(d.pfad).st_mode & 0o777) == "0o600"
                host, pfad, kopf = server.abrufe[-1]
                assert kopf.get("User-Agent") == netz.AGENT and "Cookie" not in kopf and "Referer" not in kopf, kopf
                # Gleicher Inhalt unter anderer Adresse: derselbe Name (SHA-256).
                d2 = netz.herunterladen(server.url("hersteller.test", "/datenblatt.pdf"), domains, ablage)
                assert d2.sha256 == d.sha256 and d2.pfad == d.pfad
                # Subdomain erlaubt, Bild nur als Bild.
                b = netz.herunterladen(server.url("cdn.hersteller.test", "/bild.jpg"), domains, ablage, bild=True)
                assert b.ext == ".jpg" and b.seiten is None
                # Weiterleitung auf demselben Host geht.
                assert netz.herunterladen(server.url("hersteller.test", "/weiter"), domains, ablage).sha256 == d.sha256
                # Webarchiv: nur mit Original auf der Herstellerdomain, geladen wird die Roh-Fassung.
                a = netz.herunterladen(server.url("web.archive.org", "/web/20240501123000/https://hersteller.test/alt.pdf"),
                                       domains, ablage)
                assert open(a.pfad, "rb").read() == PDF_C and "id_/" in server.abrufe[-1][1], server.abrufe[-1]
                assert netz.quelle(server.url("web.archive.org", "/web/2024/https://hersteller.test/x"), domains) \
                    == "webarchiv" and netz.archiv_stand("20240501123000") == "2024-05-01"
                # Was nicht geladen wird – mit dem Satz für den Vorschlag.
                n_vorher = len(server.abrufe)
                for url, teil, kwargs in (
                        ("http://hersteller.test/anleitung.pdf", "Nur https", {}),
                        (server.url("haendler.test", "/anleitung.pdf"), "Nicht von einer bestätigten Herstellerseite", {}),
                        (server.url("hersteller.test.boese.test", "/anleitung.pdf"), "Nicht von einer bestätigten", {}),
                        (server.url("web.archive.org", "/web/2024/https://haendler.test/x.pdf"), "Nicht von einer", {}),
                        ("https://nutzer:pw@hersteller.test/anleitung.pdf", "Zugangsdaten", {}),
                        (server.url("intern.hersteller.test", "/anleitung.pdf"), "nicht öffentliche Adresse", {}),
                        (server.url("privat.hersteller.test", "/anleitung.pdf"), "nicht öffentliche Adresse", {}),
                        (server.url("linklocal.hersteller.test", "/anleitung.pdf"), "nicht öffentliche Adresse", {})):
                    try:
                        netz.herunterladen(url, domains, ablage, **kwargs)
                        raise AssertionError(f"geladen: {url}")
                    except netz.Fehler as exc:
                        assert teil in str(exc), (url, str(exc))
                assert len(server.abrufe) == n_vorher, "bei abgelehnten Adressen darf keine Verbindung entstehen"
                for pfad, teil, kwargs in (
                        ("/weiter-fremd", "Nicht von einer bestätigten Herstellerseite", {}),
                        ("/weiter-privat", "nicht öffentliche Adresse", {}),
                        ("/weiter-http", "Nur https", {}),
                        ("/schleife", "Weiterleitungen", {}),
                        ("/seite.pdf", "Seite statt Datei", {}),
                        ("/falsch.png", "Unbekannter Dateityp", {}),
                        ("/kaputt.pdf", "lässt sich nicht lesen", {}),
                        ("/fehlt.pdf", "404", {}),
                        ("/anleitung.pdf", "Unbekannter Dateityp", {"bild": True}),
                        ("/langsam.pdf", "Zeitüberschreitung", {"frist": time.monotonic() + 0.8})):
                    try:
                        netz.herunterladen(server.url("hersteller.test", pfad), domains, ablage, **kwargs)
                        raise AssertionError(f"geladen: {pfad}")
                    except netz.Fehler as exc:
                        assert teil in str(exc), (pfad, str(exc))
                # Zu groß: mit Content-Length vorab, ohne beim Lesen gezählt.
                alt_max = katalog.DOK_MAX_BYTES
                katalog.DOK_MAX_BYTES = 4000
                try:
                    for pfad in ("/gross.pdf", "/gross-ohne-laenge.pdf"):
                        try:
                            netz.herunterladen(server.url("hersteller.test", pfad), domains, ablage)
                            raise AssertionError(pfad)
                        except netz.Fehler as exc:
                            assert "größer als" in str(exc), (pfad, str(exc))
                finally:
                    katalog.DOK_MAX_BYTES = alt_max
                # Keine Zwischendateien übrig.
                assert not [n for n in os.listdir(ablage) if n.startswith(".")], os.listdir(ablage)
            # Die echte Regel: private, Loopback-, Link-Local- und Multicast-Adressen sind nie öffentlich.
            for ip, oeff in (("127.0.0.1", False), ("10.1.2.3", False), ("172.16.0.1", False), ("192.168.0.1", False),
                             ("169.254.169.254", False), ("100.64.0.1", False), ("224.0.0.1", False), ("0.0.0.0", False),
                             ("::1", False), ("fe80::1", False), ("fc00::1", False), ("::ffff:10.0.0.1", False),
                             ("93.184.216.34", True), ("2606:4700::1111", True), ("kaputt", False)):
                assert netz.oeffentlich(ip) is oeff, ip
            netz.ADRESSE_ERLAUBT = netz.oeffentlich
            try:
                netz.herunterladen(server.url("hersteller.test", "/anleitung.pdf"), domains, ablage)
                raise AssertionError("127.0.0.1 mit der echten Regel geladen")
            except netz.Fehler as exc:
                assert "nicht öffentliche Adresse" in str(exc), str(exc)
            # Domains aus der Eingabe
            assert netz.domain_lesen("https://www.Hersteller.TEST/produkt") == "hersteller.test"
            assert netz.domain_lesen("münchen.test") == "xn--mnchen-3ya.test"
            for falsch in ("", "localhost", "10.0.0.1", "web.archive.org", "x", "-a.test", "a..test"):
                assert netz.domain_lesen(falsch) is None, falsch
        finally:
            netz_zurueck(alt)
            server.stop()
    print("Downloads der Recherche bestanden.")


# --- Der ganze Lauf --------------------------------------------------------------------------------------------------

def _beleg(wert, url="", art="hersteller", fundstelle="Produktseite", zitat="Zitat"):
    return {"wert": wert, "quelle_url": url, "fundstelle": fundstelle, "zitat": zitat, "beleg": art}


def ergebnis_probe(server, kategorie_id):
    seite = server.url("hersteller.test", "/produkt")
    return {
        "gemeinsam": {
            "hersteller": _beleg("hersteller", seite), "modell": _beleg("Rettungsgurt Probe", seite),
            "kategorie_id": _beleg(kategorie_id, seite, "hersteller"), "materialart": _beleg("textil", seite),
            "normen_seite": _beleg(["CE", "EN 813", "UIAA", "UKCA"], seite),
            "lebensdauer_jahre": _beleg(None, "", "nicht_belegt"),
            "pruefintervall_monate": _beleg(None, "", "nicht_belegt"),
            "dokumente": [
                {"art": "gebrauchsanleitung", "url": server.url("hersteller.test", "/anleitung.pdf"),
                 "titel": "Gebrauchsanleitung Probe", "sprache": "de", "quelle_url": seite},
                {"art": "konformitaetserklaerung", "url": server.url("hersteller.test", "/erklaerung.pdf"),
                 "titel": "EU-Konformitätserklärung Probe", "sprache": "de", "quelle_url": seite},
                {"art": "pruefanweisung",
                 "url": server.url("web.archive.org", "/web/20240501123000/https://hersteller.test/alt.pdf"),
                 "titel": "Prüfanweisung (alt)", "sprache": "de", "quelle_url": seite},
                {"art": "datenblatt", "url": server.url("haendler.test", "/blatt.pdf"), "titel": "Händlerblatt",
                 "sprache": "de", "quelle_url": server.url("haendler.test", "/angebot")}],
            "nicht_mehr_im_angebot": False, "nachfolger": ""},
        "ausfuehrungen": [
            {"artikelnummer": _beleg("PR-1", seite), "bemerkung": _beleg("Gr. M/L", seite),
             "dokumente": [], "bild": {"url": server.url("cdn.hersteller.test", "/bild.jpg"), "quelle_url": seite,
                                       "beleg": "hersteller"}},
            {"artikelnummer": _beleg("PR-2", seite),
             "bemerkung": _beleg("Gr. XL laut Händler", server.url("haendler.test", "/angebot")),
             "dokumente": [{"art": "datenblatt", "url": server.url("hersteller.test", "/datenblatt.pdf"),
                            "titel": "Datenblatt PR-2", "sprache": "de", "quelle_url": seite},
                           {"art": "sonstiges", "url": server.url("hersteller.test", "/seite.pdf"),
                            "titel": "Prüfbericht", "sprache": "de", "quelle_url": seite}],
             "bild": None},
            {"artikelnummer": _beleg("PR-9", seite), "bemerkung": _beleg(None, "", "nicht_belegt"),
             "dokumente": [], "bild": None}],
        "hinweise": ["Größe S nicht gefunden."], "rueckfragen": ["Gibt es eine deutsche Prüfanweisung?"],
    }


def pruefung_antwort(url, server):
    """Die Antwort der Dokumentprüfung je Datei (Structured Output als Text)."""
    leer = {"seite": None, "zitat": ""}
    basis = {"passt": "ja", "gehoert_zu": ["PR-1", "PR-2", "PR-9"], "beleg": {"seite": 1, "zitat": "PR-1, PR-2, PR-9"},
             "begruendung": "Artikelnummern auf dem Titelblatt", "art": "gebrauchsanleitung", "sprache": "de",
             "version": "A-2024", "datum": None, "normen": [],
             "lebensdauer": {"jahre": None, "seite": None, "zitat": ""},
             "pruefintervall": {"monate": None, "seite": None, "zitat": ""},
             "ukca": {"genannt": False, **leer}, "hinweise": []}
    if url.endswith("/anleitung.pdf"):
        basis.update(lebensdauer={"jahre": 12, "seite": 4, "zitat": "Lebensdauer: 12 Jahre ab Herstellung"},
                     pruefintervall={"monate": 12, "seite": 5, "zitat": "mindestens alle 12 Monate prüfen"})
    elif url.endswith("/erklaerung.pdf"):
        basis.update(art="konformitaetserklaerung", gehoert_zu=["PR-1"], version="DoC 7", datum="2024-03-01",
                     normen=[{"norm": "EN 813:2008", "einschraenkung": ""},
                             {"norm": "EN 12277:2015", "einschraenkung": "außer Typ D"}])
    elif "alt.pdf" in url:
        basis.update(passt="nein", gehoert_zu=[], begruendung="anderes Modell", art="pruefanweisung")
    return json.dumps(basis)


def abruf(server, kennung, pfad, host="hersteller.test"):
    """Ein web_fetch mit Ergebnis (Server-Werkzeug) – die Seite gilt danach als abgerufen."""
    url = server.url(host, pfad)
    return [{"type": "server_tool_use", "id": kennung, "name": "web_fetch", "input": {"url": url}},
            {"type": "web_fetch_tool_result", "tool_use_id": kennung, "content": {
                "type": "web_fetch_result", "url": url, "retrieved_at": "2026-11-21T10:00:00Z",
                "content": {"type": "document", "source": {"type": "text", "media_type": "text/plain",
                                                           "data": "Produktseite (Platzhalter)"}}}}]


def antworter(server, kategorie_id, stand):
    """Aufruf 1: erst ein Schemaverstoß (mit Websuche und Abruf der Produktseite davor), dann das Ergebnis; Aufruf 2 je
    PDF nach Adresse."""
    def antwort(anfrage, nr):
        if (anfrage.get("output_config") or {}).get("format"):
            frage = anfrage["messages"][0]["content"][-1]["text"]
            url = re.search(r"geladen von (\S+?)\.\n", frage).group(1)
            stand["geprueft"].append(url)
            return nachricht([text(pruefung_antwort(url, server))],
                             usage={"input_tokens": 3000, "output_tokens": 500})
        if nr == 0:
            return nachricht([
                {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "Probe"}},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1",
                 "content": {"type": "web_search_tool_result_error", "error_code": "unavailable"}},
                *abruf(server, "srvtoolu_2", "/produkt"),
                werkzeug("ergebnis_abgeben", {"gemeinsam": {}, "ausfuehrungen": []}, "toolu_1")], stop="tool_use",
                usage={"input_tokens": 20000, "output_tokens": 3000,
                       "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0}})
        return nachricht([werkzeug("ergebnis_abgeben", ergebnis_probe(server, kategorie_id), "toolu_2")],
                         stop="tool_use", usage={"input_tokens": 5000, "output_tokens": 4000,
                                                 "cache_read_input_tokens": 18000})
    return antwort


def melden(k, gid, **f):
    d = dict({"manufacturer": "Hersteller", "model": "Rettungsgurt Probe", "article_no": "PR-1", "norm": "EN 813",
              "folder_id": gid, "note": "Gehört Max Platzhalter, bitte schnell",
              "links": "https://hersteller.test/produkt?ref=haendler\nhttps://haendler.test/angebot?id=5"}, **f)
    r = k["wart"].post("/api/material/meldungen", json=d, headers=H)
    assert r.status_code == 201, r.get_json()
    return r.json["meldung"]["id"]


def warten(mid, app, sekunden=30):
    from app import ki
    from app.material.services import recherche
    with app.app_context():
        z = recherche._lauf(mid)
    assert ki.warten(z["id"], sekunden), "Recherche nicht fertig"
    with app.app_context():
        return ki.zeile(z["id"])


def test_lauf_und_uebernahme():
    from app import ki
    from app.material.services import meldung, recherche
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
        os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT", None)
        server, bild = netz_server(tmp)
        alt_netz = netz_einsetzen(server)
        post = []
        alt_mail = mails_abfangen(meldung, lambda an, betreff, inhalt: post.append((an, betreff, inhalt)) or True)
        stand = {"geprueft": []}
        try:
            app, k = umgebung(os.path.join(tmp, "daten"))
            ids = katalog_grund(k["adm"])
            gid, _ = gliederung(k["wart"])
            kat = k["katalog"]
            # PR-9 steht schon im Katalog (Dublette über die Artikelnummer beim selben Hersteller).
            r = kat.post("/api/material/produkte", json={"category_id": ids["gurte"], "manufacturer": "Hersteller",
                                                         "model": "Rettungsgurt Probe", "article_no": "PR-9",
                                                         "material_kind": "textil", "lifetime_years": 10})
            assert r.status_code == 201, r.get_json()
            mid = melden(k, gid)
            # Startdaten: Domains aus den Links mit dem Herstellernamen, Bemerkung zur Kontrolle, was hinausgeht.
            r = kat.get(f"/api/material/meldungen/{mid}/recherche")
            assert r.status_code == 200 and r.json["recherche"] is None and r.json["moeglich"]["an"], r.get_json()
            assert r.json["start"]["domains"] == ["hersteller.test"] and r.json["start"]["fotos"] == 0
            ds = r.json["start"]["datenschutz"]
            assert r.json["start"]["bemerkung"].startswith("Gehört") and "Anthropic" in ds["titel"] \
                and len(ds["gesendet"]) == 4 and ds["nie"].startswith("Nie:"), ds
            assert r.json["start"]["links"] == ["https://hersteller.test/produkt", "https://haendler.test/angebot"]
            # Eingaben
            for falsch, teil in (({"domains": []}, "1 bis 3"), ({"domains": ["a.test", "b.test", "c.test", "d.test"]},
                                                                  "1 bis 3"),
                                 ({"domains": ["localhost"]}, "keine Domain"), ({"domains": "x"}, "keine Domain"),
                                 ({"domains": ["hersteller.test"], "fotos": "vielleicht"}, "ja oder nein")):
                r = kat.post(f"/api/material/meldungen/{mid}/recherche", json=falsch, headers=H)
                assert r.status_code == 400 and teil in r.json["error"], (falsch, r.get_json())

            a = Attrappe(antworter(server, ids["gurte"], stand))
            alt = einsetzen(a)
            try:
                r = kat.post(f"/api/material/meldungen/{mid}/recherche", headers=H,
                             json={"domains": ["https://www.hersteller.test/"], "fotos": False, "bemerkung": False})
                assert r.status_code == 202 and r.json["recherche"]["status"] in ("wartet", "laeuft", "fertig"), \
                    r.get_json()
                z = warten(mid, app)
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig", dict(z)

            # Was an die API ging – und was nie.
            erste = a.anfragen[0]
            assert erste["model"] == "claude-opus-5-5" and erste["betas"] == ["server-side-fallback-2026-07-01"] \
                and erste["fallbacks"] == "default" and erste["thinking"] == {"type": "adaptive"} \
                and erste["output_config"] == {"effort": "high"} and "tool_choice" not in erste \
                and erste["cache_control"] == {"type": "ephemeral"} \
                and erste["system"][0]["cache_control"] == {"type": "ephemeral"}, sorted(erste)
            werkzeuge = {w["name"]: w for w in erste["tools"]}
            assert werkzeuge["web_search"] == {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}
            assert werkzeuge["web_fetch"]["allowed_domains"] == ["haendler.test", "hersteller.test", "web.archive.org"] \
                and werkzeuge["web_fetch"]["max_uses"] == 12
            assert werkzeuge["ergebnis_abgeben"]["eager_input_streaming"] is True \
                and "strict" not in werkzeuge["ergebnis_abgeben"]
            assert "Katalogregeln" in erste["system"][0]["text"] and "## Felder" in erste["system"][0]["text"] \
                and "/home/" not in erste["system"][0]["text"]
            gesendet = json.dumps([x for x in erste["messages"]], ensure_ascii=False, default=str)
            for nie in ("wart@example.org", "OG Musterstadt", "Max Platzhalter", "katalog@example.org", "?ref=", "?id="):
                assert nie not in gesendet, nie
            nutzer = erste["messages"][0]["content"][-1]["text"]
            assert "Hersteller: Hersteller" in nutzer and "Artikelnummer: PR-1" in nutzer \
                and f"{ids['gurte']}: PSA gegen Absturz / Gurte" in nutzer and "https://hersteller.test/" in nutzer \
                and "PR-9 – Rettungsgurt Probe" in nutzer, nutzer
            assert not [b for b in erste["messages"][0]["content"] if b["type"] == "image"]
            # Der Schemaverstoß ging mit is_error und der Fehlerliste zurück; danach das gültige Ergebnis.
            zurueck = a.anfragen[1]["messages"][-1]["content"][0]
            assert zurueck["is_error"] and "ausfuehrungen" in zurueck["content"], zurueck
            # Dokumentprüfung: je geladenem PDF ein Aufruf mit Structured Output, ohne Werkzeuge, PDF als Dokument.
            pruef = [x for x in a.anfragen if (x.get("output_config") or {}).get("format")]
            assert len(pruef) == 3 and all("tools" not in x and x["messages"][0]["content"][0]["type"] == "document"
                                           for x in pruef), len(pruef)
            assert sorted(u.rsplit("/", 1)[1] for u in stand["geprueft"]) == ["alt.pdf", "anleitung.pdf",
                                                                               "erklaerung.pdf"]
            eingabe = json.loads(z["eingabe_json"])
            assert eingabe["domains"] == ["hersteller.test"] and not eingabe["bemerkung"] \
                and "bemerkung" not in eingabe["meldung"] and eingabe["fotos"] == []

            # Der Vorschlag.
            r = kat.get(f"/api/material/meldungen/{mid}/recherche")
            st = r.json["recherche"]
            v = st["vorschlag"]
            assert st["status"] == "fertig" and st["kosten_cent"] == ki.kosten_cent(json.loads(z["usage_json"])) \
                and st["kosten"].startswith("ca. ") and st["ausweichmodell"] is None, st
            g = v["gemeinsam"]
            assert g["manufacturer"]["wert"] == "Hersteller" and g["category_id"]["wert"] == ids["gurte"] \
                and g["material_kind"]["wert"] == "textil"
            # Lebensdauer textil = min(12, 10) mit Fundstelle aus der Anleitung; Intervall 12 mit Zitat.
            assert g["lifetime_years"]["wert"] == 10 and "höchstens 10" in g["lifetime_years"]["vermerk"], g
            assert g["lifetime_source"]["wert"] == ("Gebrauchsanleitung Probe, Version A-2024, S. 4: „Lebensdauer: 12 "
                                                    "Jahre ab Herstellung“"), g["lifetime_source"]
            assert g["interval_months"]["wert"] == 12 and g["interval_months"]["zitat"]
            dateien = {f["url"].rsplit("/", 1)[1]: f for f in v["dateien"]}
            assert set(dateien) == {"anleitung.pdf", "erklaerung.pdf", "alt.pdf", "blatt.pdf", "seite.pdf", "bild.jpg"}, \
                set(dateien)
            # Gleiche SHA-256 (Datenblatt = Anleitung): ein Eintrag, die zweite Art als „auch_als“.
            assert dateien["anleitung.pdf"]["auch_als"] == ["datenblatt"]
            assert dateien["blatt.pdf"]["datei"] is False and "Herstellerseite" in dateien["blatt.pdf"]["fehler"]
            assert dateien["seite.pdf"]["datei"] is False and "Seite statt Datei" in dateien["seite.pdf"]["fehler"]
            alt_f = dateien["alt.pdf"]
            assert alt_f["quelle"] == "webarchiv" and alt_f["stand"] == "2024-05-01" and not alt_f["anbieten"] \
                and alt_f["pruefung"]["begruendung"] == "anderes Modell", alt_f            # F3 A
            erkl = dateien["erklaerung.pdf"]
            assert erkl["anbieten"] and erkl["vorgewaehlt"] and erkl["version"] == "DoC 7" \
                and erkl["gueltig_ab"] == "2024-03-01" and erkl["gehoert_zu"] == [1], erkl
            assert dateien["bild.jpg"]["art"] == "produktbild" and dateien["bild.jpg"]["gehoert_zu"] == [1]
            a1, a2, a3 = v["ausfuehrungen"]
            # Norm: PR-1 mit Erklärung (Normen mit Jahr + Zusatz der Seite, ohne CE, UKCA zuletzt); PR-2 nur die Seite.
            assert a1["felder"]["norm"]["wert"] == "EN 813:2008, EN 12277:2015, UIAA, UKCA", a1["felder"]["norm"]
            assert a2["felder"]["norm"]["wert"] == "EN 813, UIAA, UKCA" \
                and "ohne Konformitätserklärung" in a2["felder"]["norm"]["vermerk"], a2["felder"]["norm"]
            assert any("außer Typ D" in h for h in v["hinweise"]), v["hinweise"]
            # Werte von Händlerseiten werden nie vorbelegt.
            assert a2["felder"]["description"]["beleg"] == "nur_identifikation" \
                and not a2["felder"]["description"]["vorbelegt"]
            assert a1["felder"]["article_no"]["vorbelegt"] and a1["felder"]["description"]["wert"] == "Gr. M/L"
            assert a1["anlegbar"] and a2["anlegbar"] and not a3["anlegbar"] and "PR-9" in a3["im_katalog"]["name"]
            assert a1["bild"] == dateien["bild.jpg"]["n"] and a2["bild"] is None
            assert dateien["anleitung.pdf"]["n"] in a1["dateien"] and dateien["anleitung.pdf"]["n"] in a2["dateien"]
            assert dateien["erklaerung.pdf"]["n"] in a1["dateien"] and dateien["erklaerung.pdf"]["n"] not in a2["dateien"]
            assert v["rueckfragen"] == ["Gibt es eine deutsche Prüfanweisung?"]
            # Liste: „recherche“ nur für die Material-Verwaltung.
            r = kat.get("/api/material/meldungen")
            m = next(x for x in r.json["meldungen"] if x["id"] == mid)
            assert m["recherche"]["status"] == "fertig" and "vorschlag" not in m["recherche"] \
                and r.json["recherche_moeglich"]["an"], r.json.get("recherche_moeglich")
            for wer in ("wart", "fuehrung"):
                r = k[wer].get("/api/material/meldungen", query_string={"eigene": "0"})
                assert r.status_code == 200 and "recherche_moeglich" not in r.json \
                    and all("recherche" not in x for x in r.json["meldungen"]), wer
            # Datei ausliefern: nur die Material-Verwaltung, mit strengen Kopfzeilen.
            n = dateien["anleitung.pdf"]["n"]
            r = kat.get(f"/api/material/meldungen/{mid}/recherche/dateien/{n}")
            assert r.status_code == 200 and r.data == PDF_A and r.mimetype == "application/pdf"
            assert "sandbox" in r.headers["Content-Security-Policy"] and r.headers["X-Content-Type-Options"] == "nosniff" \
                and "no-store" in r.headers["Cache-Control"], dict(r.headers)
            for wer, code in (("wart", 403), ("fuehrung", 403), ("pruefer", 403), ("nutzer", 403)):
                assert k[wer].get(f"/api/material/meldungen/{mid}/recherche/dateien/{n}").status_code == code, wer
            assert app.test_client().get(f"/api/material/meldungen/{mid}/recherche/dateien/{n}").status_code == 401
            assert kat.get(f"/api/material/meldungen/{mid}/recherche/dateien/999").status_code == 404
            assert kat.get(f"/api/material/meldungen/{mid}/recherche/dateien/{dateien['alt.pdf']['n']}").status_code \
                in (200, 404)

            # Übernehmen: die dritte Ausführung steht schon im Katalog.
            gem = {"manufacturer": "Hersteller", "model": "Rettungsgurt Probe", "category_id": ids["gurte"],
                   "material_kind": "textil", "lifetime_years": 10, "interval_months": 12,
                   "lifetime_source": g["lifetime_source"]["wert"]}
            n_anl, n_erkl = dateien["anleitung.pdf"]["n"], dateien["erklaerung.pdf"]["n"]
            wahl = [{"nr": 1, "article_no": "PR-1", "description": "Gr. M/L", "norm": a1["felder"]["norm"]["wert"],
                     "dateien": [n_anl, n_erkl], "bild": True},
                    {"nr": 2, "article_no": "PR-2", "description": "Gr. XL", "norm": a2["felder"]["norm"]["wert"],
                     "dateien": [n_anl]}]
            url = f"/api/material/meldungen/{mid}/recherche/uebernehmen"
            r = kat.post(url, json={"gemeinsam": gem, "ausfuehrungen": wahl + [{"nr": 3, "article_no": "PR-9"}]},
                         headers=H)
            assert r.status_code == 409 and "Ausführung 3 steht schon im Katalog" in r.json["error"], r.get_json()
            for falsch, teil in (({"ausfuehrungen": wahl}, "gemeinsam"), ({"gemeinsam": gem, "ausfuehrungen": []},
                                                                           "mindestens eine"),
                                 ({"gemeinsam": gem, "ausfuehrungen": [{"nr": 7}]}, "Unbekannte Ausführung"),
                                 ({"gemeinsam": gem, "ausfuehrungen": [wahl[0], wahl[0]]}, "doppelt"),
                                 ({"gemeinsam": gem, "ausfuehrungen": [dict(wahl[1], bild=True)]}, "kein Bild"),
                                 ({"gemeinsam": gem, "ausfuehrungen": [dict(wahl[1], dateien=[alt_f["n"]])]},
                                  "nicht angebotene"),
                                 ({"gemeinsam": dict(gem, lifetime_years=None),
                                   "ausfuehrungen": [wahl[0]]}, "Ausführung 1 (PR-1): Bei textilem Material ist die Lebensdauer Pflicht")):
                r = kat.post(url, json=falsch, headers=H)
                assert r.status_code in (400, 409) and teil in r.json["error"], (teil, r.get_json())
            with app.app_context():
                from app import db
                assert db.query("SELECT COUNT(*) AS n FROM mat_product WHERE manufacturer = 'Hersteller'",
                                one=True)["n"] == 1, "eine gescheiterte Übernahme hat etwas angelegt"
                assert meldung.meldung(mid)["status"] == "offen"
            # Teilfehler: die Datei der Erklärung fehlt beim Anhängen.
            ordner = os.path.join(app.config["DATA_DIR"], "ki", str(z["id"]))
            pfad_erkl = os.path.join(ordner, erkl["sha256"] + ".pdf")
            beiseite = pfad_erkl + ".beiseite"
            os.rename(pfad_erkl, beiseite)
            post.clear()
            r = kat.post(url, json={"gemeinsam": gem, "ausfuehrungen": wahl, "antwort": "Danke!"}, headers=H)
            assert r.status_code == 201, r.get_json()
            produkte = {p["article_no"]: p for p in r.json["produkte"]}
            assert set(produkte) == {"PR-1", "PR-2"} and r.json["meldung"]["status"] == "eingepflegt"
            assert r.json["meldung"]["produkt"]["article_no"] == "PR-1"                # die gemeldete Nummer
            an = r.json["anhaengen"]
            assert an["angehaengt"] == 3 and an["uebersprungen"] == 0 and len(an["fehler"]) == 1 \
                and an["fehler"][0]["datei"] == n_erkl and "von Hand" in an["fehler"][0]["fehler"], an
            assert r.json["recherche"]["status"] == "uebernommen"
            p1, p2 = produkte["PR-1"], produkte["PR-2"]
            assert p1["norm"] == "EN 813:2008, EN 12277:2015, UIAA, UKCA" and p1["description"] == "Gr. M/L" \
                and p1["lifetime_years"] == 10 and p1["bild"] and not p2["bild"], p1
            # Mail an den Melder nennt beide Produkte.
            assert len(post) == 1 and post[0][0] == "wart@example.org" and "PR-1" in post[0][2] \
                and "PR-2" in post[0][2] and "mehreren Ausführungen" in post[0][2], post
            os.rename(beiseite, pfad_erkl)
            # Nachladen: hängt nur das Fehlende an; ein zweites Mal überspringt alles; „Übernehmen“ erneut ebenso.
            r = kat.post(f"/api/material/meldungen/{mid}/recherche/nachladen", headers=H)
            assert r.status_code == 200 and r.json["anhaengen"] == {"angehaengt": 1, "uebersprungen": 3, "fehler": []}, \
                r.get_json()
            r = kat.post(url, json={}, headers=H)
            assert r.status_code == 200 and r.json["anhaengen"]["angehaengt"] == 0 \
                and r.json["anhaengen"]["uebersprungen"] == 4, r.get_json()
            with app.app_context():
                docs = db.query("SELECT product_id, kind, file_path, sha256, version, valid_from FROM mat_product_document"
                                " WHERE product_id IN (?, ?) ORDER BY product_id, kind", (p1["id"], p2["id"]))
                assert [(d["product_id"], d["kind"]) for d in docs] == [
                    (p1["id"], "gebrauchsanleitung"), (p1["id"], "konformitaetserklaerung"),
                    (p2["id"], "gebrauchsanleitung")], docs
                assert docs[0]["file_path"] == docs[2]["file_path"]                      # liegt einmal auf der Platte
                assert docs[1]["version"] == "DoC 7" and docs[1]["valid_from"] == "2024-03-01"
                m_row = meldung.meldung(mid)
                assert m_row["product_id"] == p1["id"]
                eintraege = db.query("SELECT entity, action, after_json FROM mat_audit WHERE entity IN ('request', "
                                     "'recherche') AND entity_id = ? ORDER BY id", (mid,))
                aktionen = [(e["entity"], e["action"]) for e in eintraege]
                assert aktionen == [("request", "angelegt"), ("recherche", "recherche_gestartet"),
                                    ("recherche", "recherche_beendet"), ("request", "eingepflegt"),
                                    ("recherche", "recherche_uebernommen")], aktionen
                assert json.loads(eintraege[3]["after_json"])["produkte"] == [p1["id"], p2["id"]]
                uebernommen = json.loads(eintraege[4]["after_json"])
                assert uebernommen["produkte"] == [p1["id"], p2["id"]] \
                    and any(x.startswith("Konformitätserklärung: ") for x in uebernommen["dateien"]), uebernommen
                beendet = json.loads(eintraege[2]["after_json"])
                assert beendet["status"] == "fertig" and beendet["dateien"] == 4 and "kosten" not in beendet, beendet
            # Journal am Produkt: Einträge der Recherche nur für die Material-Verwaltung.
            j = kat.get(f"/api/material/produkte/{p1['id']}").json["produkt"]["journal"]
            assert any(e["entity"] == "recherche" for e in j), [e["entity"] for e in j]
            jw = k["wart"].get(f"/api/material/produkte/{p1['id']}").json["produkt"]["journal"]
            assert any(e["entity"] == "request" for e in jw) and not any(e["entity"] == "recherche" for e in jw)
            # Auch am zweiten Produkt aus derselben Meldung stehen Meldung und Recherche.
            j2 = kat.get(f"/api/material/produkte/{p2['id']}").json["produkt"]["journal"]
            assert {e["entity"] for e in j2} >= {"product", "document", "request", "recherche"}, {e["entity"] for e in j2}
            # Die Liste nennt die angelegten Produkte (Satz an der Karte, Oberfläche vom 21.11.2026) – ein gelöschtes nicht
            # mehr, auch wenn SQLite seine Kennung einem neueren Produkt gibt.
            liste = kat.get("/api/material/meldungen?status=erledigt").json["meldungen"]
            lauf_kurz = next(x for x in liste if x["id"] == mid)["recherche"]
            assert [p["id"] for p in lauf_kurz["produkte"]] == [p1["id"], p2["id"]] \
                and lauf_kurz["produkte"][1]["article_no"] == "PR-2", lauf_kurz
            assert kat.delete(f"/api/material/produkte/{p2['id']}", headers=H).status_code == 200
            neu = kat.post("/api/material/produkte", json={"category_id": ids["gurte"], "manufacturer": "Andere",
                                                            "model": "Platzhalter", "material_kind": "textil",
                                                            "lifetime_years": 10}, headers=H).json["produkt"]
            with app.app_context():
                db.execute("UPDATE mat_product SET created_at = '2099-01-01T00:00:00+00:00' WHERE id = ?", (neu["id"],))
            r = kat.get(f"/api/material/meldungen/{mid}/recherche").json["recherche"]
            assert [p["id"] for p in r["produkte"]] == [p1["id"]], (neu["id"], p2["id"], r["produkte"])
            # Nach der Übernahme kein neuer Start (Meldung erledigt).
            r = kat.post(f"/api/material/meldungen/{mid}/recherche", json={"domains": ["hersteller.test"]}, headers=H)
            assert r.status_code == 409 and "erledigt" in r.json["error"]
            # Tageslauf: Die Dateien bleiben 30 Tage nach dem Erledigen, danach gehen sie.
            with app.app_context():
                recherche.aufraeumen()
                assert os.path.isdir(ordner)
                db.execute("UPDATE mat_product_request SET resolved_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
                           (mid,))
                recherche.aufraeumen()
                assert not os.path.isdir(ordner)
        finally:
            mails_zurueck(alt_mail)
            netz_zurueck(alt_netz)
            server.stop()
    print("Lauf, Vorschlag und Mehrfach-Übernahme bestanden.")


def test_rechte_und_wechselwirkungen():
    """Rechte je Rolle für alle Routen, ohne Schlüssel, Kontingent, eine app-weit, Erledigen bricht ab, Fotos und
    Bemerkung nur mit Häkchen, Meldung löschen, Kontolöschung, dev-zuruecksetzen, dev-bestand-leeren."""
    from app import ki
    from app.material.services import meldung
    alt_puls = ki.PULS_SEK
    ki.PULS_SEK = 0.05
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
        os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT", None)
        alt_mail = mails_abfangen(meldung)
        try:
            app, k = umgebung(os.path.join(tmp, "daten"))
            katalog_grund(k["adm"])
            gid, _ = gliederung(k["wart"])
            kat = k["katalog"]
            mid = melden(k, gid)
            r = k["wart"].post("/api/material/meldungen", headers=H, data={
                "manufacturer": "Hersteller", "model": "Seil Probe", "folder_id": str(gid), "note": "Notiz Probe",
                "fotos": (jpeg(), "etikett.jpg")})
            assert r.status_code == 201, r.get_json()
            mid2 = r.json["meldung"]["id"]
            basis = f"/api/material/meldungen/{mid}/recherche"
            wege = [("post", basis, {"domains": ["hersteller.test"]}), ("get", basis, None),
                    ("post", basis + "/abbrechen", None), ("get", basis + "/dateien/1", None),
                    ("post", basis + "/uebernehmen", {}), ("post", basis + "/nachladen", None)]

            def aufruf(c, art, weg, d):
                return getattr(c, art)(weg, json=d, headers=H) if art == "post" else c.get(weg)
            for wer in ("wart", "fuehrung", "pruefer", "nutzer"):
                for art, weg, d in wege:
                    assert aufruf(k[wer], art, weg, d).status_code == 403, (wer, weg)
            for art, weg, d in wege:
                assert aufruf(app.test_client(), art, weg, d).status_code == 401, weg
            # Fremde oder unbekannte Meldung: 404.
            assert kat.get("/api/material/meldungen/99999/recherche").status_code == 404
            assert kat.post("/api/material/meldungen/99999/recherche", json={"domains": ["hersteller.test"]},
                            headers=H).status_code == 404
            # Noch keine Recherche: Abbrechen, Übernehmen, Nachladen, Datei → 404.
            for art, weg, d in wege[2:]:
                assert aufruf(kat, art, weg, d).status_code == 404, weg
            # Ohne Schlüssel: Start und Abbrechen 503 für die Material-Verwaltung; was schon da ist, bleibt lesbar (ohne
            # Aufruf der API – V2 der Browserprüfung): GET 200 ohne Startdaten, die übrigen wie mit Schlüssel (hier 404,
            # es gibt noch keinen Lauf). 403 für alle anderen; die Liste trägt „recherche“, aber kein „recherche_moeglich“.
            os.environ.pop("ANTHROPIC_API_KEY")
            for art, weg, d in wege:
                code = 503 if weg in (basis, basis + "/abbrechen") and art == "post" else 200 if art == "get" \
                    and weg == basis else 404
                assert aufruf(kat, art, weg, d).status_code == code, (weg, code)
                assert aufruf(k["wart"], art, weg, d).status_code == 403, weg
            r = kat.get(basis)
            assert r.json["start"] is None and r.json["moeglich"]["eingerichtet"] is False \
                and not r.json["moeglich"]["an"], r.json
            r = kat.get("/api/material/meldungen")
            assert "recherche_moeglich" not in r.json and all("recherche" in x for x in r.json["meldungen"])
            os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL

            # Eine app-weit: Während eine läuft (hängt), 409 für jede andere Meldung; Erledigen bricht sie ab.
            strom = _Strom(nachricht([text("nie")]), haengen=True)
            a = Attrappe(lambda anfrage, nr: strom)
            alt = einsetzen(a)
            try:
                r = kat.post(basis, json={"domains": ["hersteller.test"], "fotos": True, "bemerkung": True}, headers=H)
                assert r.status_code == 202, r.get_json()
                r = kat.post(f"/api/material/meldungen/{mid2}/recherche", json={"domains": ["hersteller.test"],
                                                                                "fotos": True, "bemerkung": True},
                             headers=H)
                assert r.status_code == 409 and "Es läuft schon eine Recherche zu „Hersteller Rettungsgurt Probe“" \
                    in r.json["error"], r.get_json()
                r = kat.get("/api/material/meldungen")
                assert not r.json["recherche_moeglich"]["an"] and "läuft schon" in r.json["recherche_moeglich"]["grund"]
                assert kat.post(f"/api/material/meldungen/{mid}/ablehnen", json={"antwort": "Doppelt gemeldet."},
                                headers=H).status_code == 200
                z = warten(mid, app)
            finally:
                ki.CLIENT = alt
            assert z["status"] == "abgebrochen" and strom.geschlossen.is_set(), dict(z)
            # Mit Häkchen: Bemerkung und Foto (EXIF-freie Web-Fassung) gehen mit – und stehen im Nachweis.
            eingabe = json.loads(z["eingabe_json"])
            assert eingabe["bemerkung"] and eingabe["meldung"]["bemerkung"].startswith("Gehört")
            a = Attrappe([nachricht([text("ohne Ergebnis")])] * 2)
            alt = einsetzen(a)
            try:
                r = kat.post(f"/api/material/meldungen/{mid2}/recherche", headers=H,
                             json={"domains": ["hersteller.test"], "fotos": True, "bemerkung": True})
                assert r.status_code == 202, r.get_json()
                z2 = warten(mid2, app)
            finally:
                ki.CLIENT = alt
            assert z2["status"] == "fehlgeschlagen" and "kein Ergebnis" in z2["fehler"], dict(z2)
            inhalt = a.anfragen[0]["messages"][0]["content"]
            bilder = [b for b in inhalt if b["type"] == "image"]
            assert len(bilder) == 1 and "Notiz Probe" in inhalt[-1]["text"]
            from PIL import Image
            import base64
            with Image.open(io.BytesIO(base64.b64decode(bilder[0]["source"]["data"]))) as b:
                assert not dict(b.getexif()) and "exif" not in b.info, b.info
            assert a.anfragen[1]["messages"][-1]["content"].startswith("Bitte gib das Ergebnis")   # einmal nachgefragt
            r = kat.get(f"/api/material/meldungen/{mid2}/recherche")
            assert r.json["recherche"]["status"] == "fehlgeschlagen" and r.json["recherche"]["vorschlag"] is None \
                and r.json["recherche"]["phase"] == "recherche" and r.json["recherche"]["phase_text"] == ""
            assert r.json["recherche"]["eingabe"]["fotos"] == 1 and r.json["start"]["domains"] == ["hersteller.test"]
            # Kontingent erschöpft: 429 mit Monat und Zahlen.
            os.environ["MATERIAL_RECHERCHE_JE_MONAT"] = "2"
            try:
                r = kat.post(f"/api/material/meldungen/{mid2}/recherche", json={"domains": ["hersteller.test"]},
                             headers=H)
                assert r.status_code == 429 and "aufgebraucht" in r.json["error"], r.get_json()
                r = kat.get("/api/material/meldungen")
                rm = r.json["recherche_moeglich"]
                assert not rm["an"] and rm["rest"] == 0 and "aufgebraucht" in rm["grund"], rm
            finally:
                os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT")
            # Meldung löschen (der Melder): Inhalt und Ordner weg, die Zeile bleibt fürs Kontingent.
            with app.app_context():
                os.makedirs(ki.ordner(z2["id"]), exist_ok=True)
            assert k["wart"].delete(f"/api/material/meldungen/{mid2}", headers=H).status_code == 200
            with app.app_context():
                z2 = ki.zeile(z2["id"])
                assert z2["eingabe_json"] == "{}" and z2["ergebnis_json"] is None \
                    and not os.path.isdir(ki.ordner(z2["id"])) and ki.kontingent("mat_recherche")["verbraucht"] == 2
            # Kontolöschung der Material-Verwaltung: Name in den Läufen „(gelöschtes Konto)“.
            uid = next(x["id"] for x in k["adm"].get("/api/admin/users").json["users"]
                       if x["email"] == "katalog@example.org")
            assert k["adm"].delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
            with app.app_context():
                from app import db
                assert {r["gestartet_von_name"] for r in db.query("SELECT gestartet_von_name FROM ki_laeufe")} \
                    == {"(gelöschtes Konto)"}
                fremd = db.execute("INSERT INTO ki_laeufe (art, status, gestartet_am, beendet_am) VALUES "
                                   "('wiki_entwurf', 'fertig', ?, ?)", (db.now(), db.now()))
                os.makedirs(ki.ordner(z["id"]), exist_ok=True)
            # dev-bestand-leeren: Läufe und Journal der Recherche bleiben (entity „recherche“ ist eingeordnet).
            from test_material_bestand_leeren import aufrufen as leeren_aufrufen
            from test_material_dev_zuruecksetzen import DEV, aufrufen, umwelt
            with umwelt(app, **DEV):
                ausgabe, rc = leeren_aufrufen(app, "--ja-bestand-loeschen")
                assert rc == 0, ausgabe
                with app.app_context():
                    assert db.query("SELECT COUNT(*) AS n FROM ki_laeufe", one=True)["n"] == 3
                # dev-zuruecksetzen: Läufe der Recherche und ihre Ordner gehen, andere Arten bleiben.
                ausgabe, rc = aufrufen(app, "--trocken")
                assert rc == 0 and "2 Läufe der Recherche per Claude API" in ausgabe, ausgabe
                ausgabe, rc = aufrufen(app, "--ja-alles-loeschen")
                assert rc == 0 and "2 Läufe der Recherche per Claude API" in ausgabe, ausgabe
            with app.app_context():
                assert [r["id"] for r in db.query("SELECT id FROM ki_laeufe")] == [fremd]
                assert not os.path.isdir(ki.ordner(z["id"]))
        finally:
            mails_zurueck(alt_mail)
            ki.PULS_SEK = alt_puls
    print("Rechte und Wechselwirkungen der Recherche bestanden.")


def test_zusammenfuehren_regeln():
    """Katalogregeln im Zusammenführen ohne Lauf: Metall ohne Lebensdauer, textil ohne Herstellerzahl 10 mit Vermerk,
    Edelrid überall 10, sonstiges nur mit Angabe, Intervall-Vermerk, Händlernummer nicht vorbelegt, Webarchiv-Vermerk,
    lange Fundstelle ohne Zitat; Schemaprüfung von ergebnis_abgeben."""
    from app.material.services import recherche
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
        app, k = umgebung(tmp)
        ids = katalog_grund(k["adm"])
        with app.app_context():
            from app import db
            kats = [{"id": r["id"], "pfad": str(r["id"])} for r in db.query("SELECT id FROM mat_category")]
            eingabe = {"domains": ["hersteller.test"], "meldung": {"hersteller": "Edelrid", "modell": "M",
                                                                     "kategorie": None},
                       "katalog": {"kategorien": kats, "hersteller": ["Testwerk"], "produkte": []}}

            def lauf(materialart, hersteller="Hersteller", nummer_url="https://hersteller.test/p", dok=None, iv=None):
                e = ergebnis_probe(SimpleServer(), ids["gurte"])
                e["gemeinsam"]["materialart"]["wert"] = materialart
                e["gemeinsam"]["hersteller"]["wert"] = hersteller
                e["gemeinsam"]["dokumente"] = []
                e["gemeinsam"]["pruefintervall_monate"] = iv or _beleg(None, "", "nicht_belegt")
                e["ausfuehrungen"] = [{"artikelnummer": _beleg("X-1", nummer_url), "bemerkung": _beleg(None, "",
                                                                                                     "nicht_belegt"),
                                       "abweichend": {}, "dokumente": [], "bild": None}]
                erg, fehler = recherche.ergebnis_pruefen(e)
                assert not fehler, fehler
                dateien = dok or []
                return recherche.zusammenfuehren(erg, dateien, eingabe)
            v = lauf("metall_hardware")
            assert v["gemeinsam"]["lifetime_years"]["wert"] is None and "Metall" in v["gemeinsam"]["lifetime_years"][
                "vermerk"]
            v = lauf("textil")
            assert v["gemeinsam"]["lifetime_years"]["wert"] == 10 \
                and "keine Herstellerangabe" in v["gemeinsam"]["lifetime_years"]["vermerk"]
            assert v["gemeinsam"]["interval_months"]["wert"] == 12 \
                and v["gemeinsam"]["interval_months"]["vermerk"] == "Intervall nicht vom Hersteller belegt"
            v = lauf("sonstiges")
            assert v["gemeinsam"]["lifetime_years"]["wert"] is None
            v = lauf("textil", hersteller="EDELRID")
            assert v["gemeinsam"]["lifetime_years"]["wert"] == 10 and "Edelrid" in v["gemeinsam"]["lifetime_years"][
                "vermerk"]
            v = lauf("textil", nummer_url="https://haendler.test/p")
            nr = v["ausfuehrungen"][0]["felder"]["article_no"]
            assert nr["beleg"] == "nur_identifikation" and not nr["vorbelegt"] and "Händlernummern" in nr["vermerk"], nr
            v = lauf("textil", nummer_url="https://web.archive.org/web/20230102000000/https://hersteller.test/p")
            nr = v["ausfuehrungen"][0]["felder"]["article_no"]
            assert nr["beleg"] == "webarchiv" and nr["vorbelegt"] and "Stand 2023-01-02" in nr["vermerk"], nr
            v = lauf("textil", iv=_beleg(6, "https://hersteller.test/p", zitat="alle 6 Monate"))
            assert v["gemeinsam"]["interval_months"]["wert"] == 12 and "6 Monate" in v["gemeinsam"]["interval_months"][
                "vermerk"]
            # Lange Fundstelle: ohne Zitat, mit Hinweis (Zitate nicht verstümmeln).
            dok = [{"art": "gebrauchsanleitung", "url": "https://hersteller.test/a.pdf", "titel": "Anleitung",
                    "sprache": "de", "fuer": [0], "bild": False, "quelle": "hersteller", "stand": None, "fehler": "",
                    "datei": {"sha256": "a" * 64, "ext": ".pdf", "mime": "application/pdf", "groesse": 10, "seiten": 1},
                    "pruefung": recherche.pruefung_lesen(json.loads(pruefung_antwort("x/anleitung.pdf", None)) | {
                        "lebensdauer": {"jahre": 8, "seite": 3, "zitat": "z" * 400}}, ["X-1"])}]
            v = lauf("textil", dok=dok)
            assert v["gemeinsam"]["lifetime_years"]["wert"] == 8 \
                and v["gemeinsam"]["lifetime_source"]["wert"] == "Anleitung, Version A-2024, S. 3", v["gemeinsam"]
            assert any("ohne Zitat" in h for h in v["hinweise"])
            # Schemaprüfung: Fehlerliste statt Ausnahme.
            _, fehler = recherche.ergebnis_pruefen({"gemeinsam": {"hersteller": {"wert": 3, "beleg": "irgendwas"}},
                                                    "ausfuehrungen": [{"artikelnummer": "PR-1"}] * 11, "x": 1})
            text_f = " ".join(fehler)
            for teil in ("gemeinsam.hersteller.wert: Text erwartet", "beleg: eine von", "höchstens 10", "x: unbekanntes",
                         "artikelnummer: Objekt"):
                assert teil in text_f, (teil, fehler)
            _, fehler = recherche.ergebnis_pruefen("kein Objekt")
            assert fehler
    print("Zusammenführen nach den Katalogregeln bestanden.")


class SimpleServer:
    """Adressen ohne Server – für Tests, die nur das Zusammenführen brauchen."""
    port = 443

    def url(self, host, pfad):
        return f"https://{host}{pfad}"


def test_statisch():
    """Übung: GET /meldungen der Übung nennt keine Recherche (kein Knopf); Beschriftungen in Python und JS gleich."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(wurzel, "app", "static", "js", "uebung", "material.js"), encoding="utf-8") as fh:
        uebung = fh.read()
    assert "recherche" not in uebung.lower()
    with open(os.path.join(wurzel, "app", "material", "static", "material.js"), encoding="utf-8") as fh:
        js = fh.read()
    from app.material.services import beschriftung
    for aktion in ("recherche_gestartet", "recherche_beendet", "recherche_uebernommen"):
        assert f'{aktion}: "{beschriftung.AKTION[aktion]}"' in js, aktion
    for feld in ("domains", "bemerkung_mit", "ki_modell", "effort", "ki_lauf", "belegt", "produkte"):
        assert f'{feld}: "{beschriftung.FELD[feld]}"' in js, feld
    assert f'recherche: "{beschriftung.ENTITAET["recherche"]}"' in js
    print("Statische Prüfungen der Recherche bestanden.")


def _quelle(text, anfang, ende):
    a = text.index(anfang)
    return text[a:text.index(ende, a + len(anfang))]


def test_oberflaeche_statisch():
    """Oberfläche (21.11.2026): Knopf und Statuszeile an der Karte nur mit recherche_moeglich bzw. Lauf; Knopfsprache der
    neuen Dialoge (genau eine rote Hauptaktion bzw. keine, nur graue Nebenknöpfe, keine „…“, kein btn ghost); Nachfragen
    alle 5 s nur bei laufendem Lauf und sichtbarer Seite; die Übernahme nutzt die Feldbausteine des Produktdialogs;
    Links aus dem Netz nur http(s); keine Touch-Regeln außerhalb von (pointer: coarse)."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(wurzel, "app", "material", "static", "material.js"), encoding="utf-8") as fh:
        js = fh.read()
    with open(os.path.join(wurzel, "app", "material", "static", "material.css"), encoding="utf-8") as fh:
        css = fh.read()
    karte = _quelle(js, "function meldeKarte(m, bearbeiten, moeglich)", "\n  async function meldungen()")
    assert "if (moeglich && !rechercheLaeuft(m.recherche))" in karte
    assert ('class="btn secondary small" data-act="recherche" data-id="${m.id}"${grund ? knopfAus("mr-grund", grund) : ""}>'
            '${m.recherche ? "Erneut recherchieren" : "Recherchieren lassen"}</button>') in karte
    # Der Sperrgrund steht einmal über der Liste (V6), nicht je Karte.
    assert "grundSatz(" not in karte and "${bearbeiten ? rechercheZeile(m, moeglich) : \"\"}" in karte
    assert "meldeKarte(m, d.bearbeiten, d.recherche_moeglich)" in js and "${rechercheSperre(d, liste)}" in js
    sperre = _quelle(js, "function rechercheSperre(d, liste)", "\n  }\n")
    assert 'class="notice mat-recherche-sperre" id="mr-grund"' in sperre
    zeile = _quelle(js, "function rechercheZeile(m, moeglich)", "\n  }\n")
    assert 'role="status"' in zeile and '${moeglich ? `<button type="button" class="lnk" data-act="recherche-abbrechen"' in zeile
    assert 'class="btn secondary small" data-act="vorschlag"' in zeile
    # Nachfragen: nur mit laufendem Lauf, nur sichtbar, alle 5 s.
    seite = _quelle(js, "  async function meldungen() {", "\n  /* --- Änderungsanträge im Bestand")
    assert 'document.visibilityState !== "visible"' in seite and "}, 5000);" in seite
    assert 'document.addEventListener("visibilitychange", beobachten);' in seite
    assert "{ endgueltig: false }" in _quelle(seite, '"recherche-abbrechen": async', "},\n")
    # Je Dialog genau eine rote Hauptaktion (class="btn" ohne secondary) – bzw. keine im Ergebnis der Übernahme.
    for name, haupt in (("async function rechercheStartDialog(", 1), ("async function vorschlagDialog(", 1),
                        ("function uebernahmeDialog(", 1), ("function anhaengenErgebnis(", 1)):
        f = _quelle(js, name, "\n  }\n")
        assert len(re.findall(r'class="btn"', f)) == haupt, name
        assert "btn ghost" not in f and "btn danger" not in f and "…</button>" not in f, name
    assert ">Recherchieren</button>" in js and '"Produkt anlegen" : "Produkte anlegen"' in js and ">Anlegen</button>" in js
    # Im Teilfehler-Dialog ist „Fehlendes nachladen“ die Hauptaktion (V5), im Vorschlag nur, wenn etwas fehlt.
    assert '<button class="btn" id="ue-nach" type="button">Fehlendes nachladen</button>' in js
    assert "${fehlt ? '<button class=\"btn secondary\" id=\"vs-nach\" type=\"button\">Fehlendes nachladen</button>' : \"\"}" in js
    # Fokus nach dem Wechsel des Dialoginhalts (B1, V9), Fehler an der Artikelnummer über S.feldFehler (B2).
    assert '$("h2", body).focus({ preventScroll: true });' in _quelle(js, "function uebernahmeDialog(", "\n  }\n")
    assert "S.feldFehler(art, e.message)" in js and "nach.focus();" in js
    assert '.mat-ue-felder", fs).inert = !an;' in js and 'dlg.addEventListener("cancel", escFrage);' in js
    # Die Übernahme nimmt die Felder und Prüfungen des Produktdialogs.
    ue = _quelle(js, "function uebernahmeDialog(", "\n  }\n")
    assert 'produktFelderHtml(p, kats, { ohne: ["article_no", "description", ...je], quelle, mehrzeilig: true })' in ue
    assert "produktFelderVerdrahten(body, kats, { neu: true })" in ue and "artikelnummerPruefen(" in ue
    pd = _quelle(js, "async function produktDialog(p, opt)", "\n  }\n")
    assert "${produktFelderHtml(p, kats)}" in pd and "produktFelderVerdrahten(body, kats," in pd
    assert "const fremdLink = (url, text) => (/^https?:\\/\\//i.test(url || \"\")" in js
    # CSS der Recherche: keine Tippflächen-Regeln (die stehen app-weit unter pointer: coarse).
    block = _quelle(css, "/* Recherche per Claude API an einer Meldung", "/* Änderungsanträge")
    assert "44px" not in block and ":hover" not in block
    # Karten nach der Dialogbreite (V4), nicht nach der Fensterbreite.
    assert ".mat-vorschlag { container: vorschlag / inline-size; }" in block and "@container vorschlag (max-width: 640px)" in block
    print("Oberfläche der Recherche (statisch) bestanden.")


if __name__ == "__main__":
    test_downloads()
    test_zusammenfuehren_regeln()
    test_lauf_und_uebernahme()
    test_rechte_und_wechselwirkungen()
    test_statisch()
    test_oberflaeche_statisch()
