"""Chromium über das DevTools-Protokoll (CDP) – Treiber der Browser-Tests überall dort, wo der des Entwicklungsrechners
(/home/harness/devtools/cdp) fehlt, etwa in GitHub Actions. Selbst kein Test (kein „test_“ im Namen); ausgewählt wird
er in tests/einfuehrung_browser.py (treiber()).

Nur die Standardbibliothek: Chromium läuft kopflos und spricht über --remote-debugging-pipe (Dateideskriptoren 3 und
4, Nachrichten mit NUL getrennt) – kein WebSocket, kein Wettlauf um einen Port. Ist ein Port angegeben, öffnet
Chromium ihn zusätzlich (/json/list für Tests, die die Reiter zählen); gesprochen wird trotzdem über die Leitung.

Schnittstelle wie beim Treiber des Entwicklungsrechners:

    b = Browser(port=None, breite=1280, hoehe=900, profil=None, zusatz=())
    b.rufen("Input.dispatchKeyEvent", type="keyDown", ...)   # CDP-Befehl an die Seite → result, Fehler als RuntimeError
    b.js("document.title")                                   # Wert des Ausdrucks (Zusagen abgewartet), Ausnahme → RuntimeError
    b.oeffnen(url, warten=0.3)                               # laden bis zum load-Ereignis, dann noch warten Sekunden
    b.warten(0.5)                                            # Sekunden warten und dabei Ereignisse einsammeln
    b.cookie("session", wert)                                # Cookie für 127.0.0.1 (alle Ports)
    b.foto(pfad, ganz=True)                                  # Bildschirmfoto als PNG (.png wird angehängt)
    b.fehler()                                               # Konsolenfehler, Ausnahmen und Log-Fehler seit dem Start
    b.ereignisse                                             # CDP-Ereignisse der Seite; die Liste gehört dem Aufrufer
    b.proc                                                   # der Chromium-Prozess (subprocess.Popen)
    b.schliessen()
    anmelden(basis, mail, passwort)                          # Anmeldung über die API → Wert des Cookies „session“

Ereignisse kommen nur an, während der Treiber liest – in rufen, js, oeffnen und warten, nie im Hintergrund. So geht
keines verloren, wenn der Aufrufer ereignisse durch eine neue Liste ersetzt. Dialoge (alert, confirm, beforeunload)
bleiben stehen, bis jemand Page.handleJavaScriptDialog ruft – wie beim Treiber des Entwicklungsrechners.

Welches Chromium: CHROMIUM aus der Umgebung, sonst das erste von google-chrome, google-chrome-stable, chromium,
chromium-browser, /opt/pw-browsers/chromium."""
import base64
import fcntl
import http.cookies
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

KANDIDATEN = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "/opt/pw-browsers/chromium")
FRIST = 30          # Sekunden je Befehl; ein offener Dialog hält Runtime.evaluate sonst unbegrenzt an
SCHALTER = (
    "--headless", "--remote-debugging-pipe", "--no-first-run", "--no-default-browser-check", "--no-sandbox",
    "--no-proxy-server", "--disable-dev-shm-usage", "--disable-background-networking", "--disable-component-update",
    "--disable-default-apps", "--disable-extensions", "--disable-sync", "--metrics-recording-only",
    # Zeitgeber der Seite (Autosave, Herzschlag) laufen wie im Vordergrund.
    "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
    "--password-store=basic", "--use-mock-keychain", "--mute-audio", "--force-color-profile=srgb",
)
# Legt die Leitungen auf 3 und 4 und startet Chromium – ein eigener kleiner Prozess statt preexec_fn, das neben den
# Server-Fäden der Tests nicht sicher ist.
TRAMPOLIN = ("import os, sys; e, a = int(sys.argv[1]), int(sys.argv[2]); os.dup2(e, 3); os.dup2(a, 4); os.close(e); "
             "os.close(a); os.execv(sys.argv[3], sys.argv[3:])")


def chromium():
    """Pfad zu Chromium oder Chrome – oder None."""
    for name in (os.environ.get("CHROMIUM") or "",) + KANDIDATEN:
        if not name:
            continue
        pfad = shutil.which(name)
        if pfad:
            return pfad
    return None


def _hoch(fd):
    """Den Deskriptor über 9 legen, damit dup2 auf 3 und 4 keinen der beiden überschreibt."""
    neu = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 10)
    os.close(fd)
    return neu


class Browser:
    def __init__(self, port=None, breite=1280, hoehe=900, profil=None, zusatz=()):
        programm = chromium()
        if not programm:
            raise RuntimeError("kein Chromium gefunden (CHROMIUM setzen)")
        self.port = port
        self._breite, self._hoehe = breite, hoehe
        self._eigenes_profil = profil is None
        self.profil = profil or tempfile.mkdtemp(prefix="cdp-profil-")
        os.makedirs(self.profil, exist_ok=True)
        self.ereignisse = []
        self._fehler = []
        self._antworten = {}
        self._puffer = b""
        self._nr = 0
        self._ladungen = 0
        self._sitzung = None
        self._zu = False
        befehle_lesen, befehle_schreiben = map(_hoch, os.pipe())      # wir schreiben, Chromium liest auf 3
        antwort_lesen, antwort_schreiben = map(_hoch, os.pipe())      # Chromium schreibt auf 4, wir lesen
        argumente = [programm, *SCHALTER, f"--user-data-dir={self.profil}", f"--window-size={breite},{hoehe}"]
        if port:
            argumente.append(f"--remote-debugging-port={port}")
        argumente += [*zusatz, "about:blank"]
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", TRAMPOLIN, str(befehle_lesen), str(antwort_schreiben), *argumente],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                pass_fds=(befehle_lesen, antwort_schreiben))
        finally:
            os.close(befehle_lesen)
            os.close(antwort_schreiben)
        self._aus, self._ein = befehle_schreiben, antwort_lesen
        try:
            self._verbinden()
        except BaseException:
            self.schliessen()
            raise

    # --- Verbindung --------------------------------------------------------------------------------------------------
    def _verbinden(self):
        ende = time.monotonic() + FRIST
        while True:
            seiten = [t for t in self._befehl("Target.getTargets", {}, None)["targetInfos"] if t["type"] == "page"]
            if seiten or time.monotonic() > ende:
                break
            self.warten(0.1)
        ziel = seiten[0]["targetId"] if seiten else self._befehl("Target.createTarget", {"url": "about:blank"},
                                                                     None)["targetId"]
        self._sitzung = self._befehl("Target.attachToTarget", {"targetId": ziel, "flatten": True}, None)["sessionId"]
        for methode in ("Page.enable", "Runtime.enable", "Network.enable", "Log.enable"):
            self.rufen(methode)
        # Kopflos hat das Fenster sonst keinen Fokus: focus/blur und :focus verhielten sich anders als am Bildschirm.
        self.rufen("Emulation.setFocusEmulationEnabled", enabled=True)
        # Die Sichtfläche ist breite × hoehe – kopflos zöge Chromium sonst Platz für eine Leiste ab, die es nicht zeigt.
        self.rufen("Emulation.setDeviceMetricsOverride", width=self._breite, height=self._hoehe, deviceScaleFactor=1,
                   mobile=False)
        self.ereignisse = []

    def _senden(self, methode, parameter, sitzung):
        if self._zu:
            raise RuntimeError(f"{methode}: Chromium ist beendet")
        self._nr += 1
        nachricht = {"id": self._nr, "method": methode, "params": parameter}
        if sitzung:
            nachricht["sessionId"] = sitzung
        daten = json.dumps(nachricht).encode() + b"\0"
        while daten:
            daten = daten[os.write(self._aus, daten):]
        return self._nr

    def _lesen(self, sekunden):
        """Höchstens so lange auf Nachrichten warten; jede vollständige wird verteilt."""
        if self._zu:
            raise RuntimeError("Chromium ist beendet")
        bereit, _, _ = select.select([self._ein], [], [], max(sekunden, 0))
        if not bereit:
            return
        daten = os.read(self._ein, 1 << 20)
        if not daten:
            self._zu = True
            raise RuntimeError("Chromium ist beendet")
        self._puffer += daten
        while b"\0" in self._puffer:
            teil, self._puffer = self._puffer.split(b"\0", 1)
            self._verteilen(json.loads(teil))

    def _verteilen(self, n):
        if "id" in n:
            self._antworten[n["id"]] = n
            return
        if n.get("sessionId") != self._sitzung:
            return                                       # Ereignisse des Browsers selbst (Target.*)
        m, p = n.get("method"), n.get("params", {})
        if m == "Page.loadEventFired":
            self._ladungen += 1
        elif m == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            self._fehler.append("Ausnahme: " + ((d.get("exception") or {}).get("description") or d.get("text", "")))
        elif m == "Runtime.consoleAPICalled" and p.get("type") == "error":
            self._fehler.append("Konsole: " + " ".join(str(a.get("value", a.get("description", "")))
                                                     for a in p.get("args", [])))
        elif m == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            self._fehler.append("Log: " + p["entry"].get("text", "") + " " + p["entry"].get("url", ""))
        self.ereignisse.append({"method": m, "params": p})

    def _befehl(self, methode, parameter, sitzung, frist=FRIST):
        nr = self._senden(methode, parameter, sitzung)
        ende = time.monotonic() + frist
        while nr not in self._antworten:
            rest = ende - time.monotonic()
            if rest <= 0:
                raise RuntimeError(f"{methode}: keine Antwort in {frist} s")
            self._lesen(min(rest, 1.0))
        antwort = self._antworten.pop(nr)
        if "error" in antwort:
            f = antwort["error"]
            raise RuntimeError(f"{methode}: {f.get('message', '')} {f.get('data', '')}".strip())
        return antwort.get("result", {})

    # --- Schnittstelle -----------------------------------------------------------------------------------------------
    def rufen(self, methode, **parameter):
        return self._befehl(methode, parameter, self._sitzung)

    def js(self, ausdruck):
        r = self.rufen("Runtime.evaluate", expression=ausdruck, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError((d.get("exception") or {}).get("description") or d.get("text", "Ausnahme"))
        return r.get("result", {}).get("value")

    def warten(self, sekunden):
        ende = time.monotonic() + sekunden
        while (rest := ende - time.monotonic()) > 0:
            self._lesen(rest)

    def oeffnen(self, url, warten=0.3):
        vorher = self._ladungen
        r = self.rufen("Page.navigate", url=url)
        if r.get("errorText"):
            raise RuntimeError(f"{url}: {r['errorText']}")
        if r.get("loaderId"):                            # ohne: nur der Anker hat sich geändert, nichts lädt
            ende = time.monotonic() + FRIST
            while self._ladungen == vorher:
                if time.monotonic() > ende:
                    raise RuntimeError(f"{url}: lädt nicht in {FRIST} s")
                self._lesen(0.2)
        self.warten(warten)

    def cookie(self, name, wert, url=None):
        ort = {"url": url} if url else {"domain": "127.0.0.1"}
        return self.rufen("Network.setCookie", name=name, value=wert, path="/", **ort)

    def foto(self, pfad, ganz=True):
        if not pfad.endswith(".png"):
            pfad += ".png"
        parameter = {"format": "png"}
        if ganz:
            m = self.rufen("Page.getLayoutMetrics")
            g = m.get("cssContentSize") or m["contentSize"]
            parameter.update(captureBeyondViewport=True,
                             clip={"x": 0, "y": 0, "width": g["width"], "height": g["height"], "scale": 1})
        bild = base64.b64decode(self.rufen("Page.captureScreenshot", **parameter)["data"])
        os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
        with open(pfad, "wb") as fh:
            fh.write(bild)
        return pfad

    def fehler(self):
        return list(self._fehler)

    def schliessen(self):
        if not self._zu:
            try:
                self._befehl("Browser.close", {}, None, frist=5)
            except RuntimeError:
                pass                                     # Chromium schließt die Leitung oft vor der Antwort
            self._zu = True
        for fd in (getattr(self, "_aus", None), getattr(self, "_ein", None)):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._aus = self._ein = None
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)
        if self._eigenes_profil:
            shutil.rmtree(self.profil, ignore_errors=True)


def anmelden(basis, mail, passwort):
    """Über POST /api/auth/login anmelden und den Wert des Sitzungscookies liefern – ohne Proxy (nur 127.0.0.1)."""
    anfrage = urllib.request.Request(basis + "/api/auth/login", method="POST",
                                     data=json.dumps({"email": mail, "password": passwort}).encode(),
                                     headers={"Content-Type": "application/json"})
    oeffner = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with oeffner.open(anfrage, timeout=30) as antwort:
        kekse = http.cookies.SimpleCookie()
        for zeile in antwort.headers.get_all("Set-Cookie") or []:
            kekse.load(zeile)
    if "session" not in kekse:
        raise RuntimeError(f"Anmeldung als {mail}: kein Cookie „session“")
    return kekse["session"].value
