"""Recherche per Claude API – Nachbesserung nach der Sicherheits- und Ablaufprüfung vom 21.11.2026:
python tests/test_material_recherche_robust.py  oder  pytest …

Keine echten API-Aufrufe (Attrappe aus test_ki.py), keine echten Downloads (lokaler HTTPS-Server aus
test_material_recherche.py). Geprüft: ein tröpfelnder Server hält weder Frist noch „Abbrechen“ noch Zeitgrenze auf und
sperrt die Recherche nicht app-weit (S1); Adressen mit Backslash, Leer-/Steuerzeichen oder Zugangsdaten, auch als
Original im Webarchiv, nur Port 443, NAT64 und IPv4-kompatibles IPv6 (S6, Hinweis S2); Fotos ohne JPEG-Kommentar und
XMP (S5); eine unlesbare Eingabe von ergebnis_abgeben zählt als Verstoß, Hinweise als Text sind eine Zeile (S3, S9);
Dokumentprüfung nach einem Ausweichen (A1); Werte aus „unklar“ zugeordneten Dokumenten nicht vorbelegt (A2); Beleg
„hersteller“ nur für abgerufene Seiten (Hinweis S1/A1); Übernahme nach der Live-Prüfung (A3), wieder vergebene
Produktkennung (O1), gleichzeitiges Nachladen (S4); Wettlauf Start ↔ Ablehnen (A4); Kontolöschung während des Laufs
(A6); tote Läufe im Journal (Hinweis A2); Domains aus Links der Meldung und gemeinsame Endungen (Hinweis S3). Alle Namen,
Nummern, Normen und Angaben hier sind Platzhalter."""
import io
import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ki import SCHLUESSEL, Attrappe, einsetzen, im_kontext, nachricht, text, werkzeug  # noqa: E402
from test_material import (H, anmelden, gliederung, katalog_grund, mails_abfangen, mails_zurueck,  # noqa: E402
                           neues_konto, umgebung)
from test_material_recherche import (Server, abruf, antworter, ergebnis_probe, melden, netz_einsetzen,  # noqa: E402
                                     netz_server, netz_zurueck, pruefung_antwort, warten)

BYTES_TROPFEN = 80


def _tropfen(h):
    """Kopfzeilen sofort, dann ein Byte je 0,2 s – endet, wenn der Client weg ist (oder nach BYTES_TROPFEN)."""
    try:
        h.send_response(200)
        h.send_header("Content-Length", "100000")
        h.end_headers()
        h.wfile.write(b"%PDF-1.4\n")
        h.wfile.flush()
        for _ in range(BYTES_TROPFEN):
            time.sleep(0.2)
            h.wfile.write(b"0")
            h.wfile.flush()
    except OSError:
        pass


def _tropfkopf(h):
    """Schon die Kopfzeilen kommen Byte für Byte (getresponse liest sie über readline)."""
    try:
        for b in b"HTTP/1.1 200 OK\r\nX-Langsam: " + b"a" * BYTES_TROPFEN:
            h.wfile.write(bytes([b]))
            h.wfile.flush()
            time.sleep(0.1)
    except OSError:
        pass
    h.close_connection = True


def _stumm(h):
    """Kopfzeilen und ein Anfang, dann Schweigen (16 s) – nur shutdown() weckt das recv vor seiner Zeitgrenze."""
    try:
        h.send_response(200)
        h.send_header("Content-Length", "100000")
        h.end_headers()
        h.wfile.write(b"%PDF-1.4\n")
        h.wfile.flush()
        time.sleep(BYTES_TROPFEN * 0.2)
    except OSError:
        pass


def _zu_kurz(h):
    h.send_response(200)
    h.send_header("Content-Length", "5000")
    h.send_header("Connection", "close")
    h.end_headers()
    h.wfile.write(b"%PDF-1.4\n" + b"0" * 100)
    h.close_connection = True


def test_tropfender_download():
    """S1: read1 statt read, Frist nach jedem Stück und für die Kopfzeilen (Wächter), Abbrechen und Zeitgrenze des
    Laufs beenden den Socket mit shutdown – danach ist die app-weite Sperre frei."""
    from app import ki
    from app.material.services import recherche_netz as netz
    alt_puls, alt_grenze = ki.PULS_SEK, ki.ARTEN["mat_recherche"]["gesamt_sek"]
    ki.PULS_SEK = 0.05
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
        server = Server(tmp, {"/tropfen.pdf": _tropfen, "/tropfkopf.pdf": _tropfkopf, "/stumm.pdf": _stumm,
                              "/kurz.pdf": _zu_kurz})
        alt = netz_einsetzen(server)
        domains = ["hersteller.test"]
        try:
            from test_material import make_app
            app = make_app(os.path.join(tmp, "daten"))
            ablage = os.path.join(tmp, "ablage")
            os.makedirs(ablage)
            with app.app_context():
                # Frist je Datei: gilt nach jedem Stück und schon für die Kopfzeilen; nach der Frist beendet der
                # Wächter den Socket (alt_zeit: die Zeitgrenze je Empfang allein hülfe dann nicht).
                alt_zeit = netz._zeit
                netz._zeit = lambda frist: netz.VERBINDEN_SEK
                try:
                    for pfad in ("/tropfen.pdf", "/tropfkopf.pdf", "/stumm.pdf"):
                        t0 = time.monotonic()
                        try:
                            netz.herunterladen(server.url("hersteller.test", pfad), domains, ablage,
                                               frist=time.monotonic() + 1.0)
                            raise AssertionError(pfad)
                        except netz.Fehler as exc:
                            assert "Zeitüberschreitung" in str(exc), (pfad, str(exc))
                        assert time.monotonic() - t0 < 2.5, (pfad, time.monotonic() - t0)
                finally:
                    netz._zeit = alt_zeit
                # Zu kurz angekommen (read1 meldet das nicht selbst).
                try:
                    netz.herunterladen(server.url("hersteller.test", "/kurz.pdf"), domains, ablage)
                    raise AssertionError("zu kurz angenommen")
                except netz.Fehler as exc:
                    assert "nicht vollständig" in str(exc), str(exc)
                assert not [n for n in os.listdir(ablage) if n.startswith(".")], os.listdir(ablage)

            def arbeit(lauf, pfad="/stumm.pdf"):
                lauf.schritt("dateien")
                netz.herunterladen(server.url("hersteller.test", pfad), domains, lauf.ordner,
                                   frist=time.monotonic() + 60, pruefen=lauf.pruefen, merken=lauf.download_merken)
                return {}
            ctx = im_kontext(app)
            try:
                # Abbrechen mitten im Download – der Server schweigt (das recv wartete sonst 10 s) bzw. tröpfelt.
                for pfad in ("/stumm.pdf", "/tropfen.pdf"):
                    t0 = time.monotonic()
                    z = ki.starten("mat_recherche", "mat_meldung:1", {}, lambda lauf, p=pfad: arbeit(lauf, p),
                                   mit_ordner=True)
                    time.sleep(0.6)
                    assert ki.abbrechen(z["id"]) and ki.warten(z["id"], 10)
                    z = ki.zeile(z["id"])
                    assert z["status"] == "abgebrochen" and z["fehler"] == "Abgebrochen." \
                        and time.monotonic() - t0 < 2.5, (pfad, dict(z), time.monotonic() - t0)
                # Die app-weite Sperre ist frei: Ein neuer Lauf startet sofort – und endet an der Zeitgrenze.
                ki.ARTEN["mat_recherche"]["gesamt_sek"] = 0.8
                t0 = time.monotonic()
                z = ki.starten("mat_recherche", "mat_meldung:2", {}, arbeit, mit_ordner=True)
                assert ki.warten(z["id"], 10)
                z = ki.zeile(z["id"])
                assert z["status"] == "abgebrochen" and "Zeitgrenze" in z["fehler"] \
                    and time.monotonic() - t0 < 3.0, (dict(z), time.monotonic() - t0)
                assert ki.laufend("mat_recherche") is None
                assert not os.path.isdir(ki.ordner(z["id"]))
            finally:
                ctx.pop()
        finally:
            ki.PULS_SEK = alt_puls
            ki.ARTEN["mat_recherche"]["gesamt_sek"] = alt_grenze
            netz_zurueck(alt)
            server.stop()
    print("Tröpfelnder Download bestanden.")


def test_adressen():
    """S6 und Hinweis S2: Backslash, Leer-/Steuerzeichen und Zugangsdaten gelten nirgends (auch nicht als Original im
    Archiv); geladen wird die neu zusammengesetzte Adresse; nur Port 443; NAT64 und IPv4-kompatibles IPv6 sind nicht
    öffentlich; ergebnis_abgeben lehnt solche Adressen ab."""
    from app.material.services import recherche
    from app.material.services import recherche_netz as netz
    d = ["hersteller.test"]
    for url in ("https://boese.test\\@hersteller.test/doc.pdf", "https://hersteller.test/a b.pdf",
                "https://hersteller.test/a\tb", "https://hersteller.test/\x00", "https://nutzer:pw@hersteller.test/",
                "https://nutzer@hersteller.test/", "https://hersteller.test:99999/", "ftp://hersteller.test/",
                "https://hersteller.test/\u0085"):
        assert not netz.sauber(url) and netz.quelle(url, d) == "fremd", url
        try:
            netz._ziel(url, d)
            raise AssertionError(url)
        except netz.Fehler:
            pass
    for inner in ("https://boese.test\\@hersteller.test/doc.pdf", "https://x:y@hersteller.test/doc.pdf"):
        archiv = f"https://web.archive.org/web/20240501000000/{inner}"
        assert netz.archiv_original(archiv) is None and netz.quelle(archiv, d) == "fremd", archiv
    # Aus den geprüften Teilen neu zusammengesetzt (ohne Anker, Schema/Host klein).
    assert netz._ziel("https://CDN.Hersteller.test/a/b.pdf?v=1#x", d) == "https://cdn.hersteller.test/a/b.pdf?v=1"
    assert netz._ziel("https://web.archive.org/web/2024im_/https://Hersteller.test:8443/alt.pdf#s", d) \
        == "https://web.archive.org/web/2024id_/https://hersteller.test:8443/alt.pdf"
    assert netz.archiv_original("https://web.archive.org/web/2024/http://hersteller.test/x") \
        == ("2024", "http://hersteller.test/x")
    # Nur Port 443 (Tests ergänzen den Port ihres Servers).
    try:
        netz._ziel("https://hersteller.test:6379/x.pdf", d)
        raise AssertionError("Port 6379 geladen")
    except netz.Fehler as exc:
        assert "Port 443" in str(exc), str(exc)
    assert netz._ziel("https://hersteller.test:443/x.pdf", d) == "https://hersteller.test/x.pdf"
    # NAT64 und IPv4-kompatibles IPv6 (ipaddress hielte sie für öffentlich).
    for ip in ("64:ff9b::a9fe:a9fe", "64:ff9b:1::a00:1", "::127.0.0.1", "::a9fe:a9fe", "2002:a9fe:a9fe::1"):
        assert not netz.oeffentlich(ip), ip
    assert netz.oeffentlich("2606:4700::1111") and netz.oeffentlich("::ffff:93.184.216.34")
    # ergebnis_abgeben: solche Adressen sind ein Verstoß (Claude bekommt die Stelle genannt).
    e = ergebnis_probe(_OhneServer(), 1)
    e["ausfuehrungen"][0]["artikelnummer"]["quelle_url"] = "https://boese.test\\@hersteller.test/p"
    _, fehler = recherche.ergebnis_pruefen(e)
    assert any("ausfuehrungen[0].artikelnummer.quelle_url" in f for f in fehler), fehler
    # Gemeinsame Endungen sind keine Herstellerdomain; ihre Subdomains bleiben möglich.
    for s in ("github.io", "co.uk", "https://www.amazonaws.com/", "sharepoint.com", "dropbox.com"):
        assert netz.domain_lesen(s) is None and netz.gemeinsam(s), s
    assert netz.domain_lesen("hersteller.co.uk") == "hersteller.co.uk" and not netz.gemeinsam("hersteller.co.uk")
    print("Adressen bestanden.")


class _OhneServer:
    port = 443

    def url(self, host, pfad):
        return f"https://{host}{pfad}"


def test_fotos_ohne_kommentar():
    """S5: Die Fassung an die API trägt weder JPEG-Kommentar noch XMP (noch EXIF)."""
    from PIL import Image

    from app.material.services import katalog, recherche
    with tempfile.TemporaryDirectory() as tmp:
        from test_material import make_app
        app = make_app(tmp)
        with app.app_context():
            web = os.path.join(katalog.medien_dir(), "web")
            os.makedirs(web, exist_ok=True)
            exif = Image.Exif()
            exif[0x013B] = "Platzhalter Fotograf"                   # Artist
            Image.new("RGB", (40, 30), "red").save(os.path.join(web, "probe.jpg"), "JPEG", exif=exif.tobytes(),
                                                     comment=b"Foto: Platzhalter Name",
                                                     xmp=b"<x:xmpmeta>XMP-Platzhalter</x:xmpmeta>")
            with Image.open(os.path.join(web, "probe.jpg")) as b:
                assert "comment" in b.info and "xmp" in b.info                 # die Probe trägt beides
            block = recherche._foto_block("probe.jpg")
        import base64
        roh = base64.b64decode(block["source"]["data"])
        assert b"Platzhalter" not in roh, "Metadaten gingen mit"
        with Image.open(io.BytesIO(roh)) as b:
            assert not {"comment", "xmp", "exif", "icc_profile"} & set(b.info) and not dict(b.getexif()), b.info
    print("Fotos ohne Kommentar bestanden.")


def _lauf_umgebung(tmp):
    os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
    os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT", None)
    server, _ = netz_server(tmp)
    alt_netz = netz_einsetzen(server)
    app, k = umgebung(os.path.join(tmp, "daten"))
    ids = katalog_grund(k["adm"])
    gid, _ = gliederung(k["wart"])
    return server, alt_netz, app, k, ids, gid


def _starten(k, mid, a):
    from app import ki
    alt = einsetzen(a)
    try:
        r = k["katalog"].post(f"/api/material/meldungen/{mid}/recherche", headers=H,
                              json={"domains": ["hersteller.test"]})
        assert r.status_code == 202, r.get_json()
    except BaseException:
        ki.CLIENT = alt
        raise
    return alt


def test_ergebnis_robust():
    """S3 und S9: materialart als Liste ist ein Verstoß (kein TypeError) – nach zwei Korrekturen ist Schluss (3 Aufrufe,
    nicht 20); eine Ausnahme der Prüfung zählt ebenso; Hinweise und Rückfragen als Text sind eine Zeile."""
    from app import ki
    from app.material.services import meldung, recherche
    e = ergebnis_probe(_OhneServer(), 1)
    e["gemeinsam"]["materialart"]["wert"] = ["textil"]
    e["hinweise"], e["rueckfragen"] = "Ein Satz als Text.", "Eine Frage als Text?"
    erg, fehler = recherche.ergebnis_pruefen(e)
    assert any("materialart.wert" in f for f in fehler) and erg["gemeinsam"]["materialart"]["wert"] is None, fehler
    assert erg["hinweise"] == ["Ein Satz als Text."] and erg["rueckfragen"] == ["Eine Frage als Text?"], erg
    with tempfile.TemporaryDirectory() as tmp:
        server, alt_netz, app, k, ids, gid = _lauf_umgebung(tmp)
        alt_mail = mails_abfangen(meldung)
        try:
            for art in ("liste", "ausnahme"):
                mid = melden(k, gid, model=f"Probe {art}")
                eingabe = ergebnis_probe(server, ids["gurte"])
                eingabe["gemeinsam"]["materialart"]["wert"] = ["textil"]
                a = Attrappe(lambda anfrage, nr, eingabe=eingabe: nachricht(
                    [werkzeug("ergebnis_abgeben", eingabe, f"toolu_{nr}")], stop="tool_use"))
                alt_pruefen = recherche.ergebnis_pruefen
                if art == "ausnahme":
                    recherche.ergebnis_pruefen = lambda x: 1 / 0
                alt = _starten(k, mid, a)
                try:
                    z = warten(mid, app)
                finally:
                    ki.CLIENT = alt
                    recherche.ergebnis_pruefen = alt_pruefen
                assert z["status"] == "fehlgeschlagen" and "zwei Korrekturen" in z["fehler"] and len(a.anfragen) == 3, \
                    (art, dict(z), len(a.anfragen))
                if art == "ausnahme":
                    rueck = a.anfragen[1]["messages"][-1]["content"][0]
                    assert rueck["is_error"] and "nicht lesbar" in rueck["content"], rueck
                with app.app_context():
                    assert ki.laufend("mat_recherche") is None
        finally:
            mails_zurueck(alt_mail)
            netz_zurueck(alt_netz)
            server.stop()
    print("Ergebnis robust bestanden.")


def test_pruefung_ausweichen_unklar_abgerufen():
    """A1: Die Dokumentprüfung liest nach einem Ausweichen mitten in der Ausgabe den Text nach dem fallback-Block.
    A2: Lebensdauer und Intervall aus einer Anleitung mit Zuordnung „unklar“ stehen mit Fundstelle und Vermerk da,
    aber nicht vorbelegt (statt 10 nach Katalogregel). Hinweis S1/A1: Eine Fundstelle auf der Herstellerdomain, die
    Claude nie abgerufen hat, ist nur Identifikation."""
    from app import ki
    from app.material.services import meldung, recherche
    with tempfile.TemporaryDirectory() as tmp:
        server, alt_netz, app, k, ids, gid = _lauf_umgebung(tmp)
        alt_mail = mails_abfangen(meldung)
        try:
            mid = melden(k, gid)
            basis = antworter(server, ids["gurte"], {"geprueft": []})
            fb = {"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-4-8"},
                  "trigger": {"type": "refusal", "category": "cyber"}}

            def antwort(anfrage, nr):
                if (anfrage.get("output_config") or {}).get("format"):
                    url = anfrage["messages"][0]["content"][-1]["text"].split("geladen von ", 1)[1].split(".\n")[0]
                    p = json.loads(pruefung_antwort(url, server))
                    if url.endswith("/anleitung.pdf"):
                        p.update(passt="unklar", gehoert_zu=[], lebensdauer={"jahre": 5, "seite": 4, "zitat": "5 Jahre"})
                    if url.endswith("/erklaerung.pdf"):
                        voll = json.dumps(p)
                        return nachricht([text(voll[:40]), fb, text(voll)], modell="claude-opus-4-8")
                    return nachricht([text(json.dumps(p))])
                if nr == 0:
                    e = ergebnis_probe(server, ids["gurte"])
                    # PR-2: Nummer „von der Herstellerseite“, die Claude aber nie abgerufen hat.
                    e["ausfuehrungen"][1]["artikelnummer"]["quelle_url"] = server.url("hersteller.test", "/nie-gelesen")
                    return nachricht([*abruf(server, "srvtoolu_9", "/produkt"),
                                      werkzeug("ergebnis_abgeben", e, "toolu_9")], stop="tool_use")
                return basis(anfrage, nr)
            a = Attrappe(antwort)
            alt = _starten(k, mid, a)
            try:
                z = warten(mid, app)
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig", dict(z)
            v = k["katalog"].get(f"/api/material/meldungen/{mid}/recherche").json["recherche"]["vorschlag"]
            dateien = {f["url"].rsplit("/", 1)[1]: f for f in v["dateien"]}
            erkl = dateien["erklaerung.pdf"]
            assert erkl["pruefung"] and erkl["pruefung_fehler"] == "" and erkl["vorgewaehlt"], erkl      # A1
            a1, a2, _ = v["ausfuehrungen"]
            assert a1["felder"]["norm"]["wert"].startswith("EN 813:2008, EN 12277:2015"), a1["felder"]["norm"]
            lj, iv, q = (v["gemeinsam"].get(x) or a1["felder"][x] for x in ("lifetime_years", "interval_months",
                                                                              "lifetime_source"))
            assert lj["wert"] == 5 and not lj["vorbelegt"] and recherche.NICHT_SICHER in lj["vermerk"], lj      # A2
            assert not iv["vorbelegt"] and iv["zitat"] and recherche.NICHT_SICHER in iv["vermerk"], iv
            assert not q["vorbelegt"] and "anleitung" in q["quelle_url"], q
            assert not dateien["anleitung.pdf"]["vorgewaehlt"] and dateien["anleitung.pdf"]["anbieten"]
            nr1, nr2 = a1["felder"]["article_no"], a2["felder"]["article_no"]
            assert nr1["beleg"] == "hersteller" and nr1["vorbelegt"], nr1
            assert nr2["beleg"] == "nur_identifikation" and not nr2["vorbelegt"] \
                and recherche.NICHT_ABGERUFEN in nr2["vermerk"], nr2
            with app.app_context():
                erg = json.loads(ki.zeile(z["id"])["ergebnis_json"])["ergebnis"]
                assert erg["abgerufen"] == [server.url("hersteller.test", "/produkt")], erg["abgerufen"]
        finally:
            mails_zurueck(alt_mail)
            netz_zurueck(alt_netz)
            server.stop()
    print("Dokumentprüfung nach Ausweichen, „unklar“ und abgerufene Seiten bestanden.")


def test_uebernahme_robust():
    """A3: Ein inzwischen gelöschtes Produkt (PR-9) lässt sich aus dem Vorschlag anlegen – es zählt der Katalog von
    jetzt. S4: Zwei gleichzeitige „Nachladen“ hängen dieselbe Datei nur einmal an. O1: Ein Produkt mit wieder vergebener
    Kennung bekommt beim Nachladen nichts („Das Produkt gibt es nicht mehr.“)."""
    from app import db, ki
    from app.material.services import katalog, meldung
    with tempfile.TemporaryDirectory() as tmp:
        server, alt_netz, app, k, ids, gid = _lauf_umgebung(tmp)
        alt_mail = mails_abfangen(meldung)
        kat = k["katalog"]
        try:
            r = kat.post("/api/material/produkte", json={"category_id": ids["gurte"], "manufacturer": "Hersteller",
                                                         "model": "Rettungsgurt Probe", "article_no": "PR-9",
                                                         "material_kind": "textil", "lifetime_years": 10}, headers=H)
            pr9 = r.json["produkt"]["id"]
            mid = melden(k, gid)
            alt = _starten(k, mid, Attrappe(antworter(server, ids["gurte"], {"geprueft": []})))
            try:
                z = warten(mid, app)
            finally:
                ki.CLIENT = alt
            v = kat.get(f"/api/material/meldungen/{mid}/recherche").json["recherche"]["vorschlag"]
            assert not v["ausfuehrungen"][2]["anlegbar"]
            # V2: Ohne Schlüssel bleiben Vorschlag, Dateien und Statuszeile lesbar; nur der Start fehlt.
            os.environ.pop("ANTHROPIC_API_KEY")
            try:
                r = kat.get(f"/api/material/meldungen/{mid}/recherche")
                assert r.status_code == 200 and r.json["recherche"]["vorschlag"] and r.json["start"] is None, r.json
                assert kat.get(f"/api/material/meldungen/{mid}/recherche/dateien/1").status_code == 200
                liste = kat.get("/api/material/meldungen").json
                assert "recherche_moeglich" not in liste \
                    and next(x for x in liste["meldungen"] if x["id"] == mid)["recherche"]["status"] == "fertig"
                assert kat.post(f"/api/material/meldungen/{mid}/recherche", headers=H,
                                json={"domains": ["hersteller.test"]}).status_code == 503
            finally:
                os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
            assert kat.delete(f"/api/material/produkte/{pr9}", headers=H).status_code == 200
            v = kat.get(f"/api/material/meldungen/{mid}/recherche").json["recherche"]["vorschlag"]
            assert v["ausfuehrungen"][2]["anlegbar"] and v["ausfuehrungen"][2]["im_katalog"] is None, v["ausfuehrungen"][2]
            dateien = {f["url"].rsplit("/", 1)[1]: f for f in v["dateien"]}
            n_anl, n_erkl = dateien["anleitung.pdf"]["n"], dateien["erklaerung.pdf"]["n"]
            gem = {"manufacturer": "Hersteller", "model": "Rettungsgurt Probe", "category_id": ids["gurte"],
                   "material_kind": "textil", "lifetime_years": 10, "interval_months": 12}
            # Die Erklärung fehlt beim Übernehmen (beiseite gelegt) – sie kommt mit dem Nachladen.
            ordner = os.path.join(app.config["DATA_DIR"], "ki", str(z["id"]))
            pfad_erkl = os.path.join(ordner, dateien["erklaerung.pdf"]["sha256"] + ".pdf")
            os.rename(pfad_erkl, pfad_erkl + ".beiseite")
            r = kat.post(f"/api/material/meldungen/{mid}/recherche/uebernehmen", headers=H, json={
                "gemeinsam": gem, "ausfuehrungen": [{"nr": 3, "article_no": "PR-9", "dateien": [n_anl, n_erkl]},
                                                    {"nr": 1, "article_no": "PR-1", "dateien": [n_anl, n_erkl]}]})
            assert r.status_code == 201 and len(r.json["anhaengen"]["fehler"]) == 2, r.get_json()          # A3
            produkte = {p["article_no"]: p["id"] for p in r.json["produkte"]}
            assert kat.get(f"/api/material/meldungen/{mid}/recherche").json["recherche"]["fehlt"] == 2       # V5
            os.rename(pfad_erkl + ".beiseite", pfad_erkl)
            # S4: zwei gleichzeitige „Nachladen“ – das Fenster zwischen „schon da?“ und dem Einfügen gedehnt.
            original = katalog._datei_schreiben

            def langsam(*a, **kw):
                time.sleep(0.4)
                return original(*a, **kw)
            katalog._datei_schreiben = langsam
            zweiter = anmelden(app, "katalog@example.org", "passwort1")
            antworten = {}

            def klick(name, c, warten_s):
                time.sleep(warten_s)
                r = c.post(f"/api/material/meldungen/{mid}/recherche/nachladen", headers=H)
                antworten[name] = (r.status_code, r.get_json()["anhaengen"])
            faeden = [threading.Thread(target=klick, args=("a", kat, 0)),
                      threading.Thread(target=klick, args=("b", zweiter, 0.1))]
            try:
                for f in faeden:
                    f.start()
                for f in faeden:
                    f.join(30)
            finally:
                katalog._datei_schreiben = original
            assert {x[0] for x in antworten.values()} == {200}, antworten
            assert sum(x[1]["angehaengt"] for x in antworten.values()) == 2, antworten
            with app.app_context():
                for pid in produkte.values():
                    arten = [d["kind"] for d in db.query("SELECT kind FROM mat_product_document WHERE product_id = ? "
                                                         "ORDER BY kind", (pid,))]
                    assert arten == ["gebrauchsanleitung", "konformitaetserklaerung"], (pid, arten)
            assert kat.get(f"/api/material/meldungen/{mid}/recherche").json["recherche"]["fehlt"] == 0
            # O1: PR-1 löschen, ein neues Produkt bekommt dieselbe Kennung (SQLite ohne AUTOINCREMENT).
            pid1 = produkte["PR-1"]
            with app.app_context():
                assert pid1 == db.query("SELECT MAX(id) AS n FROM mat_product", one=True)["n"]
            assert kat.delete(f"/api/material/produkte/{pid1}", headers=H).status_code == 200
            neu = kat.post("/api/material/produkte", json={"category_id": ids["gurte"], "manufacturer": "Andere",
                                                            "model": "Platzhalter", "material_kind": "textil",
                                                            "lifetime_years": 10}, headers=H).json["produkt"]["id"]
            assert neu == pid1, (neu, pid1)
            with app.app_context():
                db.execute("UPDATE mat_product SET created_at = '2099-01-01T00:00:00+00:00' WHERE id = ?", (neu,))
            r = kat.post(f"/api/material/meldungen/{mid}/recherche/nachladen", headers=H)
            an = r.json["anhaengen"]
            assert r.status_code == 200 and an["angehaengt"] == 0 \
                and any(f["product_id"] == neu and "gibt es nicht mehr" in f["fehler"] for f in an["fehler"]), an
            with app.app_context():
                assert not db.query("SELECT 1 FROM mat_product_document WHERE product_id = ?", (neu,), one=True)
        finally:
            mails_zurueck(alt_mail)
            netz_zurueck(alt_netz)
            server.stop()
    print("Übernahme robust bestanden.")


def test_wettlauf_konto_tote():
    """A4: Lehnt jemand die Meldung ab, während der Start noch läuft, bricht der Lauf ab, bevor er etwas fragt.
    A6: Wird das Konto, das gestartet hat, während des Laufs gelöscht, steht „Recherche beendet“ ohne Kennung im
    Journal. Hinweis A2: Ein toter Lauf bekommt „Recherche beendet“ nachgetragen. Hinweis S3: Domains aus Links der
    Meldung sind gekennzeichnet, gemeinsame Endungen werden nicht vorgeschlagen und beim Bestätigen abgelehnt."""
    from app import db, ki
    from app.material.services import meldung, recherche
    with tempfile.TemporaryDirectory() as tmp:
        server, alt_netz, app, k, ids, gid = _lauf_umgebung(tmp)
        alt_mail = mails_abfangen(meldung)
        kat = k["katalog"]

        def journal(mid):
            with app.app_context():
                return [(r["action"], r["user_id"], r["user_name"], json.loads(r["after_json"] or "{}"))
                        for r in db.query("SELECT * FROM mat_audit WHERE entity = 'recherche' AND entity_id = ? "
                                          "ORDER BY id", (mid,))]
        try:
            # A4
            mid = melden(k, gid)
            orig = recherche.eingabe_bauen

            def eingabe_bauen(m, *a):
                e = orig(m, *a)
                meldung.ablehnen(mid, {"antwort": "Kein PSA-Produkt (Platzhalter)."})
                return e
            recherche.eingabe_bauen = eingabe_bauen
            a = Attrappe(antworter(server, ids["gurte"], {"geprueft": []}))
            try:
                alt = _starten(k, mid, a)
                try:
                    z = warten(mid, app)
                finally:
                    ki.CLIENT = alt
            finally:
                recherche.eingabe_bauen = orig
            assert z["status"] == "abgebrochen" and not a.anfragen and z["kosten_cent"] == 0, (dict(z), len(a.anfragen))
            assert [x[0] for x in journal(mid)] == ["recherche_gestartet", "recherche_beendet"]

            # A6: ein zweites Konto der Material-Verwaltung startet, wird während des Laufs gelöscht.
            zweit, uid = neues_konto(app, "zweit@example.org", rechte={"material": 3})
            mid2 = melden(k, gid, model="Probe Konto")
            weiter = threading.Event()
            basis = antworter(server, ids["gurte"], {"geprueft": []})

            def antwort(anfrage, nr):
                weiter.wait(10)
                return basis(anfrage, nr)
            alt = einsetzen(Attrappe(antwort))
            try:
                r = zweit.post(f"/api/material/meldungen/{mid2}/recherche", headers=H,
                               json={"domains": ["hersteller.test"]})
                assert r.status_code == 202, r.get_json()
                assert k["adm"].delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
                weiter.set()
                z = warten(mid2, app)
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig" and z["gestartet_von"] is None, dict(z)
            j = journal(mid2)
            assert [x[0] for x in j] == ["recherche_gestartet", "recherche_beendet"], j
            assert j[1][1] is None and j[1][2] == ki.GELOESCHT and j[1][3]["status"] == "fertig", j

            # Hinweis A2: tote Läufe
            mid3 = melden(k, gid, model="Probe tot")
            with app.app_context():
                alt_zeit = "2026-01-01T00:00:00+00:00"
                tot = db.execute("INSERT INTO ki_laeufe (art, bezug, status, gestartet_von_name, gestartet_am, "
                                 "lebenszeichen_am) VALUES ('mat_recherche', ?, 'laeuft', 'Platzhalter', ?, ?)",
                                 (recherche.bezug(mid3), alt_zeit, alt_zeit))
            assert kat.get(f"/api/material/meldungen/{mid3}/recherche").status_code == 200      # räumt auf
            j = journal(mid3)
            assert j and j[-1][0] == "recherche_beendet" and j[-1][2] == "Platzhalter" \
                and j[-1][3] == {"status": "abgebrochen", "ki_lauf": tot, "grund": ki.TOT_TEXT}, j

            # Hinweis S3: Domains aus den Links der Meldung gekennzeichnet; gemeinsame Endungen nie.
            mid4 = melden(k, gid, model="Probe Links", links="https://hersteller-doku.github.io/a\nhttps://github.io/x")
            s = kat.get(f"/api/material/meldungen/{mid4}/recherche").json["start"]
            assert "hersteller-doku.github.io" in s["domains"] and "github.io" not in s["domains"] \
                and s["domains_aus_links"] == ["hersteller-doku.github.io"], s
            for falsch in ("github.io", "co.uk", "https://www.sharepoint.com/"):
                r = kat.post(f"/api/material/meldungen/{mid4}/recherche", headers=H, json={"domains": [falsch]})
                assert r.status_code == 400 and "gemeinsame Endung" in r.json["error"], (falsch, r.get_json())
        finally:
            mails_zurueck(alt_mail)
            netz_zurueck(alt_netz)
            server.stop()
    print("Wettlauf, Kontolöschung, tote Läufe und Domains bestanden.")


if __name__ == "__main__":
    test_tropfender_download()
    test_adressen()
    test_fotos_ohne_kommentar()
    test_ergebnis_robust()
    test_pruefung_ausweichen_unklar_abgerufen()
    test_uebernahme_robust()
    test_wettlauf_konto_tote()
