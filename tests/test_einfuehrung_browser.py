"""Interaktive Einführung je Modul – Grundgerüst im Browser (Bauvorlage planung/tutorial/entwurf.md 5.2):
python tests/test_einfuehrung_browser.py  oder  pytest tests/test_einfuehrung_browser.py

Chromium über tests/einfuehrung_browser.py (Server im Faden, Konten je Rolle; ohne Chromium „übersprungen“ mit rc 0).
Je 1280×900 (Maus) und 360×740 (Telefon, Touch):
  1. Das Angebot erscheint erst nach dem Hinweis „Entwicklungsserver“ und dem Willkommen der Materialablage, nicht modal,
     am Ende der Tab-Reihenfolge, ohne den Fokus zu nehmen; „Nicht jetzt“ → Toast und Merker „abgelehnt“.
  2. Der Knopf im Profil führt in die Übung.
  3. Die Gerüst-Übung jedes Moduls läuft bis „Geschafft“ (Merker „erledigt“) – ohne Anfrage an /api/ (außer Merker und
     /api/me) und /media/, ohne Seite ohne Übungskennung, ohne Konsolenfehler, ohne waagerechten Bildlauf.
  4. Esc fragt „Übung unterbrechen?“ („Weiter üben“ bleibt, „Unterbrechen“ führt hinaus, Merker „unterbrochen“).
  5. Fokus auf „Weiter“; in einem offenen Dialog steht die Blase im Dialog und ist bedienbar.
  6. „Bewegung reduzieren“: der Rahmen ohne Übergang.
  Nachbesserung nach der Sicherheitsprüfung (04.11.2026):
  7. Ablage: Die Übung liest und schreibt nicht die echte Ablage (Stoppuhr, zugeklappte Ordner, ausgeblendeter Hinweis,
     sessionStorage); ihre Werte überstehen Seitenwechsel in der Übung, nach dem Verlassen ist alles Echte wie vorher.
  8. Seiten ohne Übungszweig: Link auf Meine PSA, Knopf „Echtheit prüfen“ und Seitenwechsel per Code → Toast „In der
     Übung nicht verfügbar.“, die Übung läuft weiter, keine Anfrage; „Meine PSA“ der Kopfleiste führt hinaus.
  9. Ohne Referer: Bild, Rahmen und Video an /api/ bzw. /media/ erreichen den Server nicht (CSP), rel="noreferrer" und
     referrerpolicy verschwinden.
  10. Abmelden aus der Übung: /login, Sitzung weg, Übungszustand und Übungsablage leer, echte Entwürfe weg.
Alle Inhalte sind Platzhalter."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

GROESSEN = ((1280, 900, False), (360, 740, True))


def warte_merker(u, rolle, schluessel, zustand, sek=5):
    import time
    ende = time.time() + sek
    while time.time() < ende:
        if u.merker(rolle).get(schluessel, {}).get("zustand") == zustand:
            return True
        time.sleep(0.1)
    return False


def _wiki_anleitung(u):
    """Die Anleitung „Materialablage“ in der Strömipedia, für alle Angemeldeten freigegeben – sonst gibt es kein
    Willkommen (und im Abschluss keinen Anleitungslink)."""
    r = u.adm.post("/api/wiki/pages", json={"title": "Materialablage", "content": "Platzhalter für die Übung."})
    assert r.status_code == 201, r.get_json()
    assert u.adm.put(f"/api/wiki/pages/{r.json['page']['id']}/share", json={"is_public": True}).status_code == 200


def _angebot_und_profil(u, breite, hoehe, touch):
    wo = f"{breite}×{hoehe}"
    u.merker_leeren("mitglied")
    u.sql("DELETE FROM mat_meta WHERE schluessel = ?", (f"willkommen:{u.ids['mitglied']}",))
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/materialablage", warten=0.5)
        # Hinweis „Entwicklungsserver“ zuerst, dann das Willkommen – das Angebot erst danach.
        assert s.warte("document.querySelector('#dev-hinweis')?.open", 5), wo
        s.b.warten(0.8)
        assert not s.js("Boolean(document.querySelector('.einfuehrung-angebot'))"), wo
        assert s.klick("#dev-hinweis-ok") is None
        assert s.warte("document.querySelector('#mat-willkommen')?.open", 5), wo
        s.b.warten(0.8)
        assert not s.js("Boolean(document.querySelector('.einfuehrung-angebot'))"), wo
        assert s.klick("#mat-willkommen-spaeter") is None
        assert s.warte("Boolean(document.querySelector('.einfuehrung-angebot'))", 5), wo
        info = s.js("""(() => { const k = document.querySelector('.einfuehrung-angebot');
          const sichtbar = (e) => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[inert], [hidden]');
          const alle = [...document.querySelectorAll('a[href], button:not([disabled]), input, select, textarea')].filter(sichtbar);
          const r = k.getBoundingClientRect();
          return { titel: k.querySelector('h2').textContent, text: k.querySelector('p').textContent, rolle: k.getAttribute('role'),
                   fokusDrin: k.contains(document.activeElement), letzterDrin: k.contains(alle[alle.length - 1]),
                   leiste: k.classList.contains('als-leiste'), unten: Math.round(innerHeight - r.bottom), breite: Math.round(r.width),
                   polster: parseInt(getComputedStyle(document.body).paddingBottom, 10), hoehe: Math.round(r.height),
                   modal: Boolean(document.querySelector('dialog[open]')),
                   rollt: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                   knoepfe: [...k.querySelectorAll('button')].map((b) => [b.textContent, b.className]) }; })()""")
        assert info["titel"] == "Kurze Übung zur Materialablage", info
        assert info["text"] == ("Probier die wichtigsten Abläufe an Übungsdaten aus. Dein echter Bestand bleibt unverändert. "
                                "Etwa 5 Minuten, jederzeit unterbrechbar."), info
        assert info["rolle"] == "region" and not info["fokusDrin"] and info["letzterDrin"] and not info["modal"], info
        assert info["knoepfe"] == [["Nicht jetzt", "btn secondary"], ["Übung starten", "btn"]], info
        assert not info["rollt"], info
        if breite < 600:
            assert info["leiste"] and info["unten"] == 0 and info["breite"] == breite and info["polster"] == info["hoehe"], info
        else:
            assert not info["leiste"] and info["unten"] == 16 and info["breite"] <= 380, info
        if touch:
            hoehen = s.js("[...document.querySelectorAll('.einfuehrung-angebot button')].map((b) => b.getBoundingClientRect().height)")
            assert min(hoehen) >= 44, hoehen
        # „Nicht jetzt“: Toast, Merker „abgelehnt“, kein Angebot mehr.
        assert s.klick("#einf-nicht-jetzt") is None
        assert s.warte("document.getElementById('toast').textContent === "
                       "'Die Übung findest du jederzeit im Profil unter „Einführungen“.'", 5), wo
        assert s.warte("!document.querySelector('.einfuehrung-angebot')", 5)
        assert u.merker("mitglied")["material:grund"]["zustand"] == "abgelehnt"
        s.oeffnen("/materialablage/bestand", warten=1.2)
        assert not s.js("Boolean(document.querySelector('.einfuehrung-angebot'))"), wo
        # Profil: „Starten“ führt in die Übung (und setzt den Stand auf „unterbrochen“).
        s.oeffnen("/profil", warten=0.3)
        assert s.js("document.querySelector('#einfuehrungen .einf-zeile[data-modul=material][data-teil=grund] a').textContent") == "Starten"
        s.sammeln()
        von = len(s.anfragen)
        assert s.klick("#einfuehrungen .einf-zeile[data-modul=material][data-teil=grund] a") is None
        z = s.warte("(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand(); return z && z.bereit ? z : null; })()", 10)
        assert z and z["teil"] == "grund" and z["modul"] == "material", z
        assert "uebung=grund" in s.js("location.search") and s.js("document.title").startswith("Übung · ")
        assert warte_merker(u, "mitglied", "material:grund", "unterbrochen"), u.merker("mitglied")
        # Fokus auf „Weiter“ (der Schritt verlangt keine Aktion).
        assert s.js("document.activeElement && document.activeElement.classList.contains('fuehrung-weiter')"), wo
        s.sammeln()
        befunde = s.netz_befunde(von=von) + s.fehler
        assert not befunde, befunde
    finally:
        s.schliessen()


def _esc_dialog_bewegung(u, breite, hoehe, touch):
    wo = f"{breite}×{hoehe}"
    u.merker_leeren("mitglied")
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/ankerplaetze?uebung=grund", warten=0.3)
        bereit = "(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand(); return z && z.bereit ? z : null; })()"
        # Hinweis „Entwicklungsserver“ (dev) zuerst – die Führung beginnt erst nach ihm.
        assert s.warte("document.querySelector('#dev-hinweis')?.open", 5), wo
        s.b.warten(0.5)
        assert not s.js("Boolean(document.querySelector('#fuehrung-blase'))"), wo
        assert s.klick("#dev-hinweis-ok") is None
        assert s.warte(bereit, 10), wo
        # Blase im offenen Dialog: wandert hinein, ist bedienbar (ein Tipp auf „Weiter“ trifft), und wieder heraus.
        s.js("S.dialog('<h2>Platzhalter</h2><p>Übung</p><div class=\"dlg-actions\"><button class=\"btn\" type=\"button\" data-close>OK</button></div>')")
        assert s.warte("document.querySelector('#fuehrung-blase')?.parentElement?.id === 'dlg'", 5), wo
        p = s.punkt(".fuehrung-blase .fuehrung-weiter", blase=True)
        assert p and p["trifft"], p
        # Das Ziel liegt hinter dem Dialog: kein Rahmen, der Dialog bleibt ohne Abdunkelung.
        assert s.js("document.querySelector('.fuehrung-rahmen').parentElement.id") == "dlg"
        assert s.warte("document.querySelector('.fuehrung-rahmen').hidden", 2)
        assert s.klick("#dlg [data-close]") is None
        assert s.warte("document.querySelector('#fuehrung-blase')?.parentElement === document.body", 5), wo
        # „Bewegung reduzieren“: der Rahmen gleitet sonst, so springt er.
        assert s.js("getComputedStyle(document.querySelector('.fuehrung-rahmen')).transitionDuration").startswith("0.15s")
        s.b.rufen("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
        assert s.js("getComputedStyle(document.querySelector('.fuehrung-rahmen')).transitionDuration") == "0s"
        s.b.rufen("Emulation.setEmulatedMedia", features=[])
        # Esc: Rückfrage; „Weiter üben“ bleibt in der Übung.
        s.taste()
        assert s.warte("document.querySelector('dialog[open] #c-titel')?.textContent === 'Übung unterbrechen?'", 5), wo
        s.b.warten(0.5)
        assert s.js("document.querySelector('.fuehrung-rahmen').hidden && document.querySelector('#fuehrung-blase').hidden")
        assert s.js("[...document.querySelectorAll('dialog[open] .dlg-actions button')].map((b) => b.textContent + '|' + b.className)") \
            == ["Weiter üben|btn secondary", "Unterbrechen|btn"]
        assert s.klick("dialog[open] #c-no") is None
        assert s.warte("!document.querySelector('dialog[open]') && !document.querySelector('#fuehrung-blase').hidden", 5)
        # Esc und „Unterbrechen“: hinaus zur Startseite des Moduls ohne Kennung; der Stand bleibt „unterbrochen“.
        s.taste()
        assert s.warte("Boolean(document.querySelector('dialog[open] #c-ok'))", 5)
        s.sammeln()
        grenze = len(s.anfragen)
        assert s.klick("dialog[open] #c-ok") is None
        assert s.warte("location.pathname === '/ankerplaetze' && !location.search && document.readyState === 'complete'", 10), wo
        assert s.js("sessionStorage.getItem('stroemis-uebung')") is None
        assert u.merker("mitglied")["karte:grund"]["zustand"] == "unterbrochen"
        # Danach schweigt das Angebot in diesem Reiter; ein neuer Seitenaufruf ohne Übung zeigt keine Blase.
        s.b.warten(1)
        assert not s.js("Boolean(document.querySelector('.einfuehrung-angebot, .fuehrung-blase'))")
        s.sammeln()
        # Bis „Unterbrechen“ in der Übung: nichts ans Netz; danach lädt die echte Seite – das ist kein Befund.
        befunde = s.netz_befunde(grenze) + s.fehler
        assert not befunde, befunde
    finally:
        s.schliessen()


BEREIT = "(() => { const z = window.S && S.einfuehrung && S.einfuehrung.zustand(); return z && z.bereit ? z : null; })()"
NICHT_HIER = "In der Übung nicht verfügbar."
# Echte Werte in der Ablage, wie Riegenkarten (Stoppuhr), Materialablage (Ordner, Katalogimport) und Strömipedia sie legen.
ECHT_LOKAL = {"pruef:stoppuhr": '{"lehrgang":5,"start":1}', "mat-ordner-klapp": '{"7":true}',
              "mat-katalogimport-ausgeblendet": "3", "stroemis-sidebar": "300"}
ECHT_SITZUNG = {"pruef:meldung": "echt", "stroemis-reiter": "echt"}


def _ablage_setzen(s):
    s.js(f"""(() => {{ for (const [k, v] of Object.entries({json.dumps(ECHT_LOKAL)})) localStorage.setItem(k, v);
      for (const [k, v] of Object.entries({json.dumps(ECHT_SITZUNG)})) sessionStorage.setItem(k, v); }})()""")


def _ablage(s):
    return s.js("""(() => { const l = {}, z = {};
      for (let i = 0; i < localStorage.length; i++) l[localStorage.key(i)] = localStorage.getItem(localStorage.key(i));
      for (let i = 0; i < sessionStorage.length; i++) z[sessionStorage.key(i)] = sessionStorage.getItem(sessionStorage.key(i));
      return { lokal: l, sitzung: z }; })()""")


def _toast_leeren(s):
    s.js("(() => { const t = document.getElementById('toast'); t.textContent = ''; t.className = ''; })()")


def _ablage_abgeschottet(u, breite, hoehe, touch):
    wo = f"{breite}×{hoehe}"
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/profil", warten=0.3)
        _ablage_setzen(s)
        vorher = _ablage(s)
        s.oeffnen("/materialablage?uebung=grund", warten=0.3)
        assert s.warte(BEREIT, 10), wo
        # In der Übung: nichts Echtes zu lesen; was die Seite ablegt, bleibt in der Übungsablage – auch über Seitenwechsel.
        assert s.js("localStorage.length === 0 && localStorage.getItem('pruef:stoppuhr') === null"), wo
        assert s.js("sessionStorage.getItem('pruef:meldung') === null && sessionStorage.getItem('stroemis-uebung') === null")
        s.js("""(() => { localStorage.setItem('pruef:stoppuhr', 'UEBUNG'); localStorage.setItem('mat-ordner-klapp', '{"900000001":true}');
          localStorage.setItem('mat-katalogimport-ausgeblendet', '900000002'); localStorage.removeItem('stroemis-sidebar');
          sessionStorage.setItem('pruef:meldung', 'UEBUNG'); })()""")
        s.js("location.href = S.ziel('/materialablage/bestand')")
        assert s.warte("location.pathname === '/materialablage/bestand' && document.readyState === 'complete'", 10), wo
        assert s.warte(BEREIT, 10), wo
        assert s.js("localStorage.getItem('pruef:stoppuhr')") == "UEBUNG"
        assert s.js("sessionStorage.getItem('pruef:meldung')") == "UEBUNG"
        assert s.js("localStorage.length") == 3 and s.js("localStorage.key(5)") is None
        # Hinaus über die Kopfleiste (Profil): alles Echte wie vorher, Übungsablage und Übungszustand weg.
        if not s.js("Boolean([...document.querySelectorAll('header.bauchbinde a[href=\"/profil\"]')].find((a) => a.getClientRects().length))"):
            assert s.klick("#nav-mehr-knopf") is None, wo
        assert s.klick("header.bauchbinde a[href='/profil']") is None, wo
        assert s.warte("location.pathname === '/profil' && document.readyState === 'complete'", 10), wo
        nachher = _ablage(s)
        assert nachher["lokal"] == vorher["lokal"], (nachher, vorher)
        assert {k: v for k, v in nachher["sitzung"].items() if k in ECHT_SITZUNG} == ECHT_SITZUNG, nachher
        assert not any(k.startswith("stroemis-uebung") and k != "stroemis-uebung-ruhe" for k in nachher["sitzung"]), nachher
    finally:
        s.schliessen()


def _seiten_ohne_uebung(u, breite, hoehe, touch):
    wo = f"{breite}×{hoehe}"
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/profil", warten=0.3)
        s.oeffnen("/materialablage?uebung=grund", warten=0.3)
        assert s.warte(BEREIT, 10), wo
        s.sammeln()
        von, server_von = len(s.anfragen), len(u.protokoll)
        # Link wie „Meine PSA ansehen →“ der Übersicht (material.js): Toast, die Übung bleibt auf der Seite.
        s.js("document.querySelector('main').insertAdjacentHTML('afterbegin', "
             "'<p><a id=\"probe-psa\" href=\"/materialablage/meine-psa\">Meine PSA ansehen</a></p>')")
        _toast_leeren(s)
        assert s.klick("#probe-psa") is None, wo
        assert s.warte(f"document.getElementById('toast').textContent === {json.dumps(NICHT_HIER)}", 5), wo
        s.b.warten(0.8)
        assert s.js("location.pathname + location.search") == "/materialablage?uebung=grund", wo
        assert s.js(BEREIT), wo
        # Seitenwechsel per Code – mit S.ziel und ohne (vergessen): angehalten (Navigation API), Toast.
        for befehl in ("location.href = S.ziel('/materialablage/ordner/900000001/bericht')",
                       "location.assign('/materialablage/pruefen')", "location.replace('/materialablage/meine-psa/900000001')"):
            _toast_leeren(s)
            s.js(befehl)
            assert s.warte(f"document.getElementById('toast').textContent === {json.dumps(NICHT_HIER)}", 5), (wo, befehl)
            s.b.warten(0.5)
            assert s.js("location.pathname + location.search") == "/materialablage?uebung=grund", (wo, befehl)
        assert s.js("S.ziel('/materialablage/meine-psa')") == "/materialablage/meine-psa"
        assert s.js("S.ziel('/materialablage/bestand')") == "/materialablage/bestand?uebung=grund"
        # Knopf „Echtheit prüfen“ im Reiter „Prüfungen“ (material.js).
        s.js("location.href = S.ziel('/materialablage/pruefungen')")
        assert s.warte("location.pathname === '/materialablage/pruefungen' && document.readyState === 'complete'", 10), wo
        assert s.warte(BEREIT, 10), wo
        assert s.warte("Boolean(document.querySelector('a[href=\"/materialablage/pruefen\"]'))", 10), wo
        s.b.warten(0.5)
        _toast_leeren(s)
        assert s.klick("a[href='/materialablage/pruefen']") is None, wo
        assert s.warte(f"document.getElementById('toast').textContent === {json.dumps(NICHT_HIER)}", 5), wo
        s.b.warten(0.8)
        assert s.js("location.pathname + location.search") == "/materialablage/pruefungen?uebung=grund", wo
        assert s.js(BEREIT), wo
        s.sammeln()
        befunde = s.netz_befunde(von=von)
        assert not befunde, befunde
        erreicht = [x for x in u.protokoll[server_von:] if x[1].startswith(("/materialablage/meine-psa", "/materialablage/pruefen",
                                                                            "/materialablage/ordner/"))]
        assert not erreicht, erreicht
        # „Meine PSA“ der Kopfleiste (für Konten mit Zuordnung) führt hinaus – ohne Übungs-Referer, also die echte Seite.
        s.js("document.querySelector('header.bauchbinde').insertAdjacentHTML('beforeend', "
             "'<a id=\"probe-kopf\" href=\"/materialablage/meine-psa\">Meine PSA</a>')")
        server_von = len(u.protokoll)
        assert s.klick("#probe-kopf") is None, wo
        assert s.warte("location.pathname === '/materialablage/meine-psa' && document.readyState === 'complete'", 10), wo
        assert s.js("document.title").startswith("Meine PSA") and not s.js("document.title").startswith("Übung")
        assert s.js("sessionStorage.getItem('stroemis-uebung')") is None
        seite = [x for x in u.protokoll[server_von:] if x[1] == "/materialablage/meine-psa"]
        assert seite and seite[0][2] == "", seite
    finally:
        s.schliessen()


def _ohne_referer(u, breite, hoehe, touch):
    wo = f"{breite}×{hoehe}"
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/profil", warten=0.3)
        s.oeffnen("/stroemipedia?uebung=grund", warten=0.3)
        assert s.warte(BEREIT, 10), wo
        s.sammeln()
        server_von = len(u.protokoll)
        s.js("""(() => { window.__csp = [];
          document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.effectiveDirective + ' ' + e.blockedURI));
          document.querySelector('main, body').insertAdjacentHTML('beforeend',
            '<div id="probe-referer"><img id="p-bild" referrerpolicy="no-referrer" src="/api/material/start" alt="">'
            + '<iframe id="p-rahmen" referrerpolicy="no-referrer" src="/media/wiki/probe.html"></iframe>'
            + '<video id="p-video" src="/media/probe.mp4"></video>'
            + '<a id="p-link" rel="noopener noreferrer" target="_blank" href="/media/probe.pdf">Probe</a></div>');
          const b = document.createElement('img'); b.setAttribute('referrerpolicy', 'no-referrer'); b.src = '/media/thumb/probe.jpg';
          document.getElementById('probe-referer').appendChild(b); })()""")
        s.b.warten(1.5)
        erreicht = [x for x in u.protokoll[server_von:] if x[1].startswith(("/api/", "/media/"))
                    and not x[1].startswith("/api/einfuehrung/") and x[1] != "/api/me"]
        assert not erreicht, (wo, erreicht)
        csp = s.js("window.__csp")
        for teil in ("img-src", "frame-src", "media-src"):
            assert any(c.startswith(teil) for c in csp), (wo, teil, csp)
        assert s.js("document.getElementById('p-link').getAttribute('rel')") == "noopener"
        assert s.js("document.querySelectorAll('#probe-referer [referrerpolicy]').length") == 0
        # Die Kopfleiste behält ihren Ausgang ohne Referer.
        assert s.js("[...document.querySelectorAll('header.bauchbinde a[href]')].every((a) => a.referrerPolicy === 'no-referrer')")
        s.sammeln()
        # Die CSP meldet die Sperre als Fehler in der Konsole – das ist hier gewollt.
        s.fehler = [f for f in s.fehler if "Content Security Policy" not in f]
        assert not s.fehler, s.fehler
    finally:
        s.schliessen()


def _abmelden(u, breite, hoehe, touch):
    wo = f"{breite}×{hoehe}"
    s = u.seite("mitglied", breite, hoehe, touch)
    try:
        s.oeffnen("/profil", warten=0.3)
        s.js("localStorage.setItem('stroemis-entwurf-probe', 'echt'); localStorage.setItem('stroemis-sidebar', '280')")
        s.oeffnen("/ankerplaetze?uebung=grund", warten=0.3)
        assert s.warte(BEREIT, 10), wo
        s.js("localStorage.setItem('stroemis-entwurf-uebung', 'UEBUNG')")
        assert s.js("sessionStorage.getItem('stroemis-entwurf-uebung') === null")
        _toast_leeren(s)
        if not s.js("Boolean(document.querySelector('#logout').getClientRects().length)"):
            assert s.klick("#nav-mehr-knopf") is None, wo
        assert s.klick("#logout") is None, wo
        assert s.warte("location.pathname === '/login' && document.readyState === 'complete'", 10), \
            (wo, s.js("location.href"), s.js("document.getElementById('toast') && document.getElementById('toast').textContent"))
        a = _ablage(s)
        assert not any(k.startswith("stroemis-uebung") for k in a["sitzung"]), a
        assert "stroemis-entwurf-probe" not in a["lokal"] and a["lokal"].get("stroemis-sidebar") == "280", a
        assert s.js("fetch('/api/me').then((r) => r.status)") == 401
    finally:
        s.schliessen()


def test_browser():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung(dev=True) as u:
        _wiki_anleitung(u)
        for breite, hoehe, touch in GROESSEN:
            _angebot_und_profil(u, breite, hoehe, touch)
            _esc_dialog_bewegung(u, breite, hoehe, touch)
            _ablage_abgeschottet(u, breite, hoehe, touch)
            _seiten_ohne_uebung(u, breite, hoehe, touch)
            _ohne_referer(u, breite, hoehe, touch)
            _abmelden(u, breite, hoehe, touch)
            for modul in ("material", "wiki", "karte", "pruefungen"):
                befunde = u.durchlauf(modul, "grund", breite, hoehe, touch)
                assert not befunde, (modul, breite, befunde)
            # Ein Zusatzteil mit Abschluss „Geschafft“ (Weiter mit … entfällt, alle anderen Teile sind erledigt).
            befunde = u.durchlauf("pruefungen", "leitung", breite, hoehe, touch)
            assert not befunde, ("pruefungen/leitung", breite, befunde)
    print("Browser bestanden.")


if __name__ == "__main__":
    test_browser()
