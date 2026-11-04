"""Hilfe für die Browser-Durchläufe der Einführung (Bauvorlage planung/tutorial/entwurf.md 5.2 und 5.3) – selbst kein
Test (kein „test_“ im Namen). Genutzt von tests/test_einfuehrung_browser.py und den Modul-Teilen
(tests/test_einfuehrung_<modul>.py):

    from einfuehrung_browser import Umgebung, uebersprungen
    if uebersprungen():
        print("übersprungen – kein Chromium"); sys.exit(0)
    with Umgebung() as u:                 # Server im Faden: freier Port, eigener Datenordner, Konten je Rolle
        befunde = u.durchlauf("material", "grund", 1280, 900, touch=False)
        assert not befunde, befunde

Server: werkzeug.serving.make_server im Faden (freier Port, Datenordner in einem eigenen Temp-Ordner, nie Mails – kein
SMTP_HOST); jede Anfrage, die ihn erreicht, steht in Umgebung.protokoll (Methode, Pfad, Referer). Konten über die Nutzerverwaltung: je Rolle eines (KONTEN), welcher Teil welches Konto nimmt, sagt
KONTO_JE_TEIL. Chromium über /home/harness/devtools/cdp/cdp.py mit freiem CDP-Port und eigenem Profil unter
/home/harness/cdp-profile (das snap-Chromium liest /tmp nicht); Touch per Emulation (pointer: coarse, mobil, Tippen als
Geste), sonst Maus (pointer: fine, hover). Alle Anfragen kommen aus Network.requestWillBeSent ins Netzprotokoll.

durchlauf(modul, teil, breite, hoehe, touch) führt alle Schritte eines Teils aus – je Schritt die probe der Übungsdatei,
ohne probe einen Klick auf warten.klick bzw. auf „Weiter“ – und liefert Befunde als Sätze (leer = bestanden). Rot wird
es, wenn ein Ziel fehlt oder nicht im Bild ist (auch verdeckt von der Leiste), eine Anfrage unbeantwortet bleibt, eine
Anfrage an /api/ (außer Merker und /api/me) oder /media/ das Netz erreicht, eine Seite ohne Übungskennung lädt, die
Konsole einen Fehler zeigt, die Seite waagerecht rollt, ein Schritt nicht weiterzählt oder am Ende nicht „Geschafft“ mit
dem Merker „erledigt“ steht."""
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDP = "/home/harness/devtools/cdp"
PROFILE = "/home/harness/cdp-profile"
PASSWORT = "passwort1"
for _p in (os.path.join(WURZEL, "tests"), WURZEL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Rolle → (Rechte, weitere Felder). Namen mit „Übung“ – nur Platzhalter.
KONTEN = {
    "mitglied": ({"material": 1, "wiki": 1, "karte": 1, "pruefungen": 1}, {}),
    "pruefer": ({"material": 1}, {"mat_pruefer": True, "urkundennummer": "UEBUNG-1"}),
    "materialwart": ({"material": 1}, {}),
    "matverwaltung": ({"material": 3}, {}),
    "redakteur": ({"wiki": 2, "karte": 2, "pruefungen": 2}, {}),
    "wikiverwaltung": ({"wiki": 3}, {}),
    "leitung": ({"pruefungen": 1}, {}),
}
KONTO_JE_TEIL = {
    ("material", "grund"): "mitglied", ("material", "pruefer"): "pruefer", ("material", "materialwart"): "materialwart",
    ("material", "verwaltung"): "matverwaltung",
    ("wiki", "grund"): "mitglied", ("wiki", "redakteur"): "redakteur", ("wiki", "verwaltung"): "wikiverwaltung",
    ("karte", "grund"): "mitglied", ("karte", "redakteur"): "redakteur",
    ("pruefungen", "grund"): "mitglied", ("pruefungen", "leitung"): "leitung", ("pruefungen", "redakteur"): "redakteur",
}
MAUS = ("--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4",)


def frei():
    """Ein freier Port auf 127.0.0.1."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def uebersprungen():
    """Ohne Chromium und Treiber laufen die Browser-Tests nicht – sie melden „übersprungen“ und enden mit rc 0."""
    return not (os.path.isfile(os.path.join(CDP, "cdp.py")) and shutil.which("chromium-browser"))


def mail(rolle):
    return f"uebung-{rolle}@example.invalid"


class Umgebung:
    """Server im Faden mit eigenem Datenordner und je Rolle einem Konto. Als Kontextmanager: räumt Server, Browser,
    Profile und Datenordner am Ende weg. dev=True: der Server gilt als Entwicklungsumgebung (Hinweis
    „Entwicklungsserver“ nach jeder Anmeldung)."""

    def __init__(self, dev=False):
        self.dev = dev
        self.seiten = []

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._name_vorher = os.environ.get("STROEMIS_NAME")
        os.environ["STROEMIS_NAME"] = "stroemis-dev" if self.dev else "stroemis-test"
        os.environ.pop("SMTP_HOST", None)
        from test_material import make_app
        from werkzeug.serving import make_server
        self.app = make_app(self._tmp.name)
        self.port = frei()
        self.basis = f"http://127.0.0.1:{self.port}"
        self.protokoll = []          # (Methode, Pfad, Referer) jeder Anfrage, die den Server erreicht
        app = self.app

        def mitschreiben(environ, start_response):
            self.protokoll.append((environ.get("REQUEST_METHOD", ""), environ.get("PATH_INFO", ""),
                                   environ.get("HTTP_REFERER", "")))
            return app(environ, start_response)
        self._server = make_server("127.0.0.1", self.port, mitschreiben, threaded=True)
        self._faden = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._faden.start()
        self.adm = self._anmelden("admin@example.org", "geheim123")
        self.ids = {}
        for rolle, (rechte, felder) in KONTEN.items():
            r = self.adm.post("/api/admin/users", json=dict({"email": mail(rolle), "password": PASSWORT,
                                                             "name": f"Übungskonto {rolle}", "rechte": rechte}, **felder))
            assert r.status_code == 201, (rolle, r.get_json())
            self.ids[rolle] = r.json["user"]["id"]
        # Materialwart: eine Verwalterfreigabe an einer Gliederung; Leitung: Leitung in einem Lehrgang.
        r = self.adm.post("/api/material/ordner", json={"name": "Übung Gliederung", "kind": "gliederung"})
        assert r.status_code == 201, r.get_json()
        self.sql("INSERT INTO mat_folder_grant (folder_id, user_id, permission, valid_until, granted_by, created_at) "
                 "VALUES (?, ?, 'verwalten', NULL, 1, datetime('now'))", (r.json["ordner"]["id"], self.ids["materialwart"]))
        r = self.adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Übung Platzhalter", "status": "laufend", "ausbilder": [
            {"user_id": self.ids["leitung"], "funktion": "Platzhalter", "ist_leitung": True}]})
        assert r.status_code == 201, r.get_json()
        return self

    def __exit__(self, *_):
        for s in list(self.seiten):
            s.schliessen()
        self._server.shutdown()
        self._server.server_close()
        if self._name_vorher is None:
            os.environ.pop("STROEMIS_NAME", None)
        else:
            os.environ["STROEMIS_NAME"] = self._name_vorher
        self._tmp.cleanup()

    def _anmelden(self, adresse, passwort):
        c = self.app.test_client()
        r = c.post("/api/auth/login", json={"email": adresse, "password": passwort})
        assert r.status_code == 200, (adresse, r.get_json())
        return c

    def sql(self, befehl, args=()):
        with self.app.app_context():
            from app import db
            if befehl.lstrip().upper().startswith("SELECT"):
                return db.query(befehl, args)
            db.execute(befehl, args)
            return None

    def merker(self, rolle):
        """Der Merker der Einführung eines Kontos ({„modul:teil“: {zustand, ablauf, am}})."""
        z = self.sql("SELECT wert FROM mat_meta WHERE schluessel = ?", (f"einfuehrung:{self.ids[rolle]}",))
        return json.loads(z[0]["wert"]) if z else {}

    def merker_leeren(self, rolle):
        self.sql("DELETE FROM mat_meta WHERE schluessel = ?", (f"einfuehrung:{self.ids[rolle]}",))

    def seite(self, rolle, breite=1280, hoehe=900, touch=False):
        s = Seite(self, rolle, breite, hoehe, touch)
        self.seiten.append(s)
        return s

    def adresse(self, modul, teil, ablauf=0):
        with self.app.test_request_context():
            from app import einfuehrung
            return einfuehrung.adresse(modul, teil, ablauf)

    def durchlauf(self, modul, teil, breite, hoehe, touch=False, rolle=None):
        """Alle Schritte eines Teils bis „Geschafft“ – Befunde als Liste von Sätzen (leer = bestanden)."""
        rolle = rolle or KONTO_JE_TEIL[(modul, teil)]
        s = self.seite(rolle, breite, hoehe, touch)
        try:
            return s.durchlauf(modul, teil)
        finally:
            s.schliessen()


class Seite:
    """Ein Chromium mit einem angemeldeten Konto."""

    def __init__(self, umgebung, rolle, breite, hoehe, touch):
        if CDP not in sys.path:
            sys.path.insert(0, CDP)
        from cdp import Browser, anmelden
        self.u, self.rolle, self.touch = umgebung, rolle, touch
        self.breite, self.hoehe = breite, hoehe
        self.port = frei()
        self.profil = os.path.join(PROFILE, f"einfuehrung-{self.port}")
        self.b = Browser(port=self.port, breite=breite, hoehe=hoehe, profil=self.profil, zusatz=() if touch else MAUS)
        self.b.rufen("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe, deviceScaleFactor=1, mobile=touch)
        self.b.rufen("Emulation.setTouchEmulationEnabled", enabled=touch, maxTouchPoints=5 if touch else 1)
        self.b.cookie("session", anmelden(umgebung.basis, mail(rolle), PASSWORT))
        self.anfragen = []           # (url, typ, documentURL)
        self.fehler = []             # Konsolenfehler und Ausnahmen (eigene Herkunft)
        self.offen = True

    def schliessen(self):
        if not self.offen:
            return
        self.offen = False
        try:
            self.b.schliessen()
            try:
                self.b.proc.wait(timeout=10)
            except Exception:
                self.b.proc.kill()
        finally:
            # Kindprozesse von Chromium schreiben beim Beenden noch ins Profil – bis es wirklich weg ist (höchstens 3 s).
            for _ in range(10):
                shutil.rmtree(self.profil, ignore_errors=True)
                time.sleep(0.3)
                if not os.path.exists(self.profil):
                    break
            if self in self.u.seiten:
                self.u.seiten.remove(self)

    # --- Ereignisse ------------------------------------------------------------------------------------------------
    def sammeln(self):
        for e in self.b.ereignisse:
            m, p = e.get("method"), e.get("params", {})
            if m == "Network.requestWillBeSent":
                self.anfragen.append((p["request"]["url"], p.get("type", ""), p.get("documentURL", "")))
            elif m == "Runtime.exceptionThrown":
                d = p["exceptionDetails"]
                self.fehler.append("Ausnahme: " + (d.get("exception", {}).get("description") or d.get("text", "")))
            elif m == "Runtime.consoleAPICalled" and p.get("type") == "error":
                self.fehler.append("Konsole: " + " ".join(str(a.get("value", a.get("description", ""))) for a in p["args"]))
            elif m == "Log.entryAdded" and p["entry"]["level"] == "error":
                url = p["entry"].get("url", "")
                # Kartenkacheln von fremden Servern (ohne Netz in der Sandbox) zählen nicht – nur die eigene Herkunft.
                if not url or url.startswith(self.u.basis):
                    self.fehler.append("Log: " + p["entry"]["text"] + " " + url)
        self.b.ereignisse = []

    def oeffnen(self, pfad, warten=0.3):
        self.sammeln()
        self.b.oeffnen(self.u.basis + pfad, warten=warten)
        self.sammeln()

    def js(self, ausdruck, versuche=30):
        """JavaScript im Fenster; während eines Seitenwechsels noch einmal versuchen."""
        letzter = None
        for _ in range(versuche):
            try:
                return self.b.js(ausdruck)
            except RuntimeError as exc:
                letzter = exc
                self.b.warten(0.1)
        raise letzter

    def warte(self, ausdruck, sek=10):
        """Bis der Ausdruck etwas Wahres liefert – sonst None."""
        ende = time.time() + sek
        while time.time() < ende:
            try:
                r = self.b.js(ausdruck)
            except RuntimeError:
                r = None
            if r:
                return r
            self.b.warten(0.1)
        return None

    def zustand(self):
        return self.js("window.S && S.einfuehrung ? S.einfuehrung.zustand() : null")

    def ruhe(self, sek=2.5):
        """Bis Bildlauf, Ziel und Blase ruhen: Die Führung rollt das Ziel weich ins Bild, Schubladen gleiten herein – ein
        Tipp mitten in der Bewegung hält am Telefon nur den Bildlauf an (kein Klick), und gemessen wäre eine Zwischenlage."""
        letzte, ruhig, ende = None, 0, time.time() + sek
        while time.time() < ende:
            try:
                lage = self.b.js("(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand();"
                                 " return JSON.stringify([scrollX, scrollY, z && z.zielRect, z && z.blaseRect]); })()")
            except RuntimeError:
                return
            ruhig = ruhig + 1 if lage == letzte else 0
            if ruhig >= 2:
                return
            letzte = lage
            self.b.warten(0.08)

    # --- Bedienen --------------------------------------------------------------------------------------------------
    def punkt(self, sel, blase=False):
        """Mitte des ersten sichtbaren Elements zu sel (ohne Blase und Rahmen, außer blase=True), ins Bild geholt, und
        ob ein Tipp dorthin wirklich dieses Element trifft."""
        return self.js(f"""(() => {{
          const el = [...document.querySelectorAll({json.dumps(sel)})].find((e) => e.getClientRects().length
            && ({'true' if blase else 'false'} || !e.closest('.fuehrung-blase, .fuehrung-rahmen')));
          if (!el) return null;
          const r0 = el.getBoundingClientRect();
          if (r0.top < 0 || r0.bottom > innerHeight) el.scrollIntoView({{ block: 'center' }});
          const r = el.getBoundingClientRect();
          const x = r.left + r.width / 2, y = r.top + r.height / 2;
          const t = document.elementFromPoint(x, y);
          return {{ x, y, trifft: Boolean(t && (t === el || el.contains(t))), was: t ? t.outerHTML.slice(0, 120) : '' }};
        }})()""")

    def klick(self, sel, blase=False):
        """Ein echter Klick (Maus) bzw. Tipp (Touch) auf die Mitte des Elements. Liefert einen Befund oder None."""
        p = self.punkt(sel, blase)
        if not p:
            return f"„{sel}“ nicht gefunden"
        if not p["trifft"]:
            return f"Ein Tipp auf die Mitte von „{sel}“ trifft etwas anderes: {p['was']}"
        if self.touch:
            # Ein Tipp: Finger auf und ab (synthesizeTapGesture löst im kopflosen Chromium keinen Klick aus).
            self.b.rufen("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": p["x"], "y": p["y"]}])
            self.b.rufen("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
        else:
            for art in ("mouseMoved", "mousePressed", "mouseReleased"):
                self.b.rufen("Input.dispatchMouseEvent", type=art, x=p["x"], y=p["y"], button="left", clickCount=1)
        return None

    def tippen(self, sel, text):
        if not self.js(f"(() => {{ const el = document.querySelector({json.dumps(sel)}); if (!el) return false; el.focus(); return true; }})()"):
            return f"Eingabefeld „{sel}“ nicht gefunden"
        self.b.rufen("Input.insertText", text=text)
        return None

    def taste(self, taste="Escape", code="Escape", tastencode=27):
        for art in ("keyDown", "keyUp"):
            self.b.rufen("Input.dispatchKeyEvent", type=art, key=taste, code=code, windowsVirtualKeyCode=tastencode)

    # --- Prüfungen ---------------------------------------------------------------------------------------------------
    def netz_befunde(self, bis=None, von=0):
        """Im Übungsmodus darf nur der Merker, /api/me und /static/ ans Netz; jede Seite trägt die Kennung. von/bis: der
        Abschnitt des Netzprotokolls, in dem geübt wurde."""
        out = []
        for url, typ, _dok in self.anfragen[von:bis]:
            teile = urlsplit(url)
            if not url.startswith(self.u.basis):
                continue
            pfad = teile.path
            if pfad.startswith("/api/") and not (pfad.startswith("/api/einfuehrung/") or pfad == "/api/me"):
                out.append(f"Anfrage ans Netz in der Übung: {url}")
            elif pfad.startswith("/media/"):
                out.append(f"Medium ans Netz in der Übung: {url}")
            elif typ == "Document" and "uebung" not in parse_qs(teile.query):
                out.append(f"Seite ohne Übungskennung geladen: {url}")
        return out

    def durchlauf(self, modul, teil, max_schritte=200):
        befunde = []
        rolle = self.rolle
        self.oeffnen(self.u.adresse(modul, teil))
        # Auf dev kommt nach der Anmeldung zuerst der Hinweis „Entwicklungsserver“ – die Führung beginnt nach ihm.
        if self.warte("document.querySelector('#dev-hinweis')?.open", 1):
            self.klick("#dev-hinweis-ok")
        beschreibung = self.js(f"S.einfuehrung.teile({json.dumps(modul)})") or {}
        if teil not in beschreibung:
            return [f"Die Übungsdatei kennt den Teil „{teil}“ nicht."]
        ende_netz = None
        for _ in range(max_schritte):
            z = self.warte("(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand();"
                           " return z && (z.bereit || z.geschafft || z.sackgasse) && !z.umgeleitet ? z : null; })()", 15)
            self.sammeln()
            self.ruhe()
            if not z:
                befunde.append("Die Führung zeigt keinen Schritt (15 s).")
                break
            if z["geschafft"]:
                break
            wo = f"Ablauf {z['ablauf'] + 1}, Schritt {z['schritt'] + 1} ({self.breite}×{self.hoehe}{', Touch' if self.touch else ''})"
            if z["sackgasse"]:
                befunde.append(f"{wo}: Sackgasse – Ziel {z['ziel']!r} fehlt.")
                break
            if self.js("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
                befunde.append(f"{wo}: Die Seite rollt waagerecht.")
            schritt = beschreibung[teil]["ablaeufe"][z["ablauf"]]["schritte"][z["schritt"]]
            lage = self.js("""(() => { const z = S.einfuehrung.zustand(); return { ziel: z.zielRect, blase: z.blaseRect,
                leiste: z.leiste, hoehe: innerHeight }; })()""")
            if z["ziel"] is not None:
                r = lage["ziel"]
                unten = lage["blase"]["top"] if lage["leiste"] and lage["blase"] else lage["hoehe"]
                if not r or r["bottom"] <= 0 or r["top"] >= unten or (r["height"] < unten and r["bottom"] > unten + 1):
                    befunde.append(f"{wo}: Ziel {z['ziel']!r} nicht ganz im Bild bzw. von der Leiste verdeckt ({r}).")
            probe = schritt.get("probe") or {}
            warten = schritt.get("warten") or {}
            vorher = (z["ablauf"], z["schritt"])
            if "tippen" in probe:
                fehler = self.tippen(*probe["tippen"])
            elif "datei" in probe:
                fehler = self.klick(".fuehrung-blase .fuehrung-bild", blase=True)
            elif "klick" in probe or "klick" in warten:
                fehler = self.klick(probe.get("klick") or warten["klick"])
            elif not warten:
                fehler = self.klick(".fuehrung-blase .fuehrung-weiter", blase=True)
            else:
                fehler = "Der Schritt wartet auf eine Aktion, hat aber keine probe."
            if fehler:
                befunde.append(f"{wo}: {fehler}")
                break
            weiter = self.warte(f"""(() => {{ const z = window.S && S.einfuehrung && S.einfuehrung.zustand();
                return z && (z.geschafft || z.sackgasse || z.ablauf !== {vorher[0]} || z.schritt !== {vorher[1]}); }})()""", 10)
            if not weiter:
                befunde.append(f"{wo}: Der Schritt zählt nach der Aktion nicht weiter.")
                break
        else:
            befunde.append(f"Mehr als {max_schritte} Schritte – die Übung endet nicht.")
        # Abschluss: Dialog „Geschafft“, dann zurück zur Startseite des Moduls ohne Kennung; Merker „erledigt“.
        if not befunde:
            if not self.warte("document.querySelector('dialog.fuehrung-geschafft[open] h2')?.textContent === 'Geschafft'", 10):
                befunde.append("Kein Dialog „Geschafft“ am Ende.")
            else:
                fokus = self.js("document.activeElement && document.activeElement.id")
                if fokus not in ("fg-ende", "fg-weiter"):
                    befunde.append(f"Fokus im Dialog „Geschafft“ nicht auf der Hauptaktion ({fokus}).")
                unbekannt = self.zustand()["unbekannt"]
                if unbekannt:
                    befunde.append(f"Unbeantwortete Anfragen: {unbekannt}")
                self.sammeln()
                ende_netz = len(self.anfragen)
                knopf = "#fg-ende" if self.js("Boolean(document.querySelector('#fg-ende'))") else "#fg-spaeter"
                fehler = self.klick(knopf, blase=True)
                if fehler:
                    befunde.append(fehler)
                elif not self.warte("!new URLSearchParams(location.search).has('uebung') && document.readyState === 'complete'", 10):
                    befunde.append("Nach „Geschafft“ nicht zur Seite ohne Übungskennung.")
                stand = self.u.merker(rolle).get(f"{modul}:{teil}", {})
                if stand.get("zustand") != "erledigt":
                    befunde.append(f"Merker nach „Geschafft“ nicht „erledigt“: {stand}")
        self.sammeln()
        befunde += self.netz_befunde(ende_netz)
        befunde += [f"Konsole: {f}" for f in self.fehler]
        return befunde
