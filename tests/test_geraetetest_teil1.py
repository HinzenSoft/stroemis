"""Gerätetest 01.11.2026, Teil 1 – Anmeldung und Gemeinsames (Auftrag planung/geraetetest/auftrag_geraetetest.md):
python tests/test_geraetetest_teil1.py  oder  pytest tests/test_geraetetest_teil1.py

  B1  Slideshow der Anmeldeseite: kleine WebP-Fassung (/media/slide/…), nur das gezeigte und das nächste Bild.
  B5  Zurück und Esc schließen das Menü „Mehr“ der Kopfleiste und jedes S.menue-Menü (S.overlayVerlauf).
  B7  Fehlermeldung der Anmeldeseiten role="alert", Felder mit aria-describedby.   B9  „Passwort anzeigen“.
  B11 eine H1 je Anmeldeseite.   B15 nach dem Anmelden location.replace.
  B14 zugeklappte Schubladen inert + aria-hidden, aria-expanded am Seitenbaum-Knopf.
  Q1  Kopfleiste klebt bei wenig Höhe bzw. offener Tastatur nicht; html.tastatur auch auf Android.
  FT4 Toast als gemeinsame Rückmeldung (role="status"), bleibt als Live-Region bestehen.   FT7 S.feldFehler mit role="alert".
Das Verhalten selbst (Zurück, Ansage, Tastatur) prüft die Browserprobe (Bericht planung/geraetetest/bericht_teil1.md);
hier stehen die Bausteine und die Bildfassung. Alle Inhalte sind Platzhalter."""
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image  # noqa: E402

from test_smoke import H, make_app  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _bild(breite=2400, hoehe=1600):
    buf = io.BytesIO()
    Image.new("RGB", (breite, hoehe), (20, 90, 160)).save(buf, "JPEG", quality=90)
    buf.seek(0)
    return buf


def test_b1_slideshow_webp():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = app.test_client()
        assert c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
        aid = c.post("/api/albums", json={"title": "Platzhalter", "category": "seil"}).json["album"]["id"]
        r = c.post(f"/api/albums/{aid}/photos", data={"files": [(_bild(), "1.jpg")]}, headers=H,
                   content_type="multipart/form-data")
        assert r.status_code == 201, r.json
        foto = r.json["photos"][0]
        key = os.path.splitext(foto["file"])[0] if "file" in foto else foto["web"].rsplit("/", 1)[1][:-4]
        anon = app.test_client()
        url = anon.get("/api/public/slideshow").json["images"][0]["url"]
        r = anon.get(url)
        assert r.status_code == 200 and r.mimetype == "image/webp", r.mimetype
        with Image.open(io.BytesIO(r.data)) as img:
            assert img.format == "WEBP" and max(img.size) <= 1000 and img.size[0] == 1000, img.size
        media = os.path.join(tmp, "media")
        ziel = os.path.join(media, "slide", key + ".webp")
        assert os.path.exists(ziel)
        web = os.path.join(media, "web", key + ".jpg")
        assert len(r.data) < os.path.getsize(web)
        # Ein zweiter Abruf nimmt die fertige Datei; ist die Web-Variante jünger (Reparatur), entsteht sie neu.
        alt = os.path.getmtime(ziel)
        assert anon.get(url).status_code == 200 and os.path.getmtime(ziel) == alt
        os.utime(web, (alt + 10, alt + 10))
        assert anon.get(url).status_code == 200 and os.path.getmtime(ziel) > alt
        # Ohne lesbare Web-Variante: wie bisher 404, kein Absturz; gefälschte Adressen 404.
        assert anon.get("/media/slide/kaputt").status_code == 404
        # Mit dem Foto verschwindet auch die Slideshow-Fassung.
        assert c.delete(f"/api/photos/{foto['id']}", headers=H).status_code == 200
        assert not os.path.exists(ziel) and not os.path.exists(web)


def test_b1_slideshow_skript():
    js = lies("app/static/js/auth.js")
    show = js[js.index("/* Slideshow auf der Anmeldeseite"):]
    assert "if (images.length > 1) vorrat = laden(i);        // das nächste – mehr nicht" in show
    assert "if (!images.length || document.hidden) return;" in show
    assert "new IntersectionObserver(" in show and "beobachter.disconnect();" in show


def test_anmeldeseiten_b7_b9_b11_b15():
    t = lies("app/templates/login.html")
    assert "<h2>" not in t and t.count("<h1>") == 4, "eine H1 je Modus (B11)"
    assert t.count('<div class="error" id="err" role="alert"></div>') == 4
    assert 'class="error hidden" id="err"' not in t
    # Jede Eingabe für Adresse und Passwort verweist auf die Meldung.
    for feld in re.findall(r'<input id="(?:email|password|password2)"[^>]*>', t):
        assert 'aria-describedby="' in feld and "err" in feld, feld
    assert t.count("data-pw-zeigen") == 3 and "Passwörter anzeigen" in t
    assert '<form id="f-forgot" aria-live="polite">' in t and '<form id="f-register" aria-live="polite">' in t
    assert "data-pw-zeigen" in lies("app/templates/profil.html")
    js = lies("app/static/js/auth.js")
    assert "location.href" not in js and "const ziel = (adresse) => location.replace(adresse);" in js
    assert "fLogin.password);" in js and "if (fehler) showErr(fehler.message, feld);" in js
    css = lies("app/static/css/app.css")
    assert ".login-form .error:empty { margin: 0; }" in css and ".login-form h1 {" in css
    touch = css[css.index("  .profil-seite label.inline { min-height: 44px; }"):]
    assert touch.startswith("  .profil-seite label.inline { min-height: 44px; }\n  .login-form label.inline { min-height: 44px; }")
    co = lies("app/static/js/common.js")
    assert 'e.target.closest("input[data-pw-zeigen]")' in co and 'f.type = h.checked ? "text" : "password";' in co


def test_b5_menues_zurueck():
    co = lies("app/static/js/common.js")
    kopf = co[co.index("  (function kopfleiste() {"):co.index("  /* Sichtbarer Ausschnitt")]
    assert "const v = overlayVerlauf(() => {" in kopf and "if (verlauf) { const v = verlauf; verlauf = null; v.zu(); }" in kopf
    assert 'window.addEventListener("pagehide", () => { if (!liste.hidden) zu(); });' in kopf
    menue = co[co.index("  const menueVerlauf = new Map();"):co.index("  /* Markup eines Menüs.")]
    assert "if (!m.open) { menueVerlaufAus(m); return; }\n    menueVerlaufAn(m);" in menue
    assert "setTimeout(menueVerlaufPruefen, 0);" in menue
    schwebend = co[co.index("  function menueSchwebend(anker, box) {"):co.index("  /* Info zu einem Begriff")]
    assert "menueVerlaufAus(box);" in schwebend and "menueVerlaufAn(box);" in schwebend


def test_b14_schubladen():
    co = lies("app/static/js/common.js")
    assert "function schubladeZustand(el, knoepfe) {" in co and "           schubladeZustand,\n" in co
    assert 'S.schubladeZustand(side, "#wiki-menu, #pg-baum");' in lies("app/static/js/wiki.js")
    assert 'S.schubladeZustand(side, "#wiki-menu");' in lies("app/static/js/public.js")
    # Seit der Suchzeile (02.11.2026, test_wiki_suchzeile.py) trägt nur noch die Leiste des Editors ein eigenes „☰“; in der
    # Strömipedia steht „☰“ in der Suchzeile („Seiten“ nur zum Vorlesen) – seit dem 02.11.2026 auch im Lesemodus.
    assert lies("app/static/js/wiki.js").count('aria-controls="wiki-side" aria-expanded="${side.classList.contains("open")}"') == 1
    for vorlage in ("app/templates/wiki.html", "app/templates/wiki_lesemodus.html"):
        assert ('aria-controls="wiki-side" aria-expanded="false" id="wiki-menu"><span aria-hidden="true">☰</span><span '
                'class="nur-vorlesen">Seiten</span></button>') in lies(vorlage), vorlage
    assert 'if (leiste.inert) leiste.setAttribute("aria-hidden", "true"); else leiste.removeAttribute("aria-hidden");' in lies(
        "app/material/static/material.js")


def test_q1_wenig_hoehe():
    css = lies("app/static/css/app.css")
    wurzel = css[css.index(":root {"):css.index("}", css.index(":root {"))]
    assert "--topbar: 52px;" in wurzel and "--kopf-hoehe: 52px;" in wurzel
    assert "  height: var(--kopf-hoehe);" in css
    assert ("@media (max-height: 500px) {\n  :root { --topbar: 0px; }\n  .bauchbinde { position: relative; z-index: 1080; }\n}\n"
            "html.tastatur { --topbar: 0px; }\nhtml.tastatur .bauchbinde { position: relative; z-index: 1080; }") in css
    # Was die Leiste selbst misst, rechnet weiter mit ihrer Höhe – die Karte füllt das Fenster ohne Bildlauf.
    assert ".map-shell { position: relative; height: calc(100vh - var(--kopf-hoehe)); height: calc(100dvh - var(--kopf-hoehe));" in css
    co = lies("app/static/js/common.js")
    assert "const android = grob.matches && istEingabe(ae) && window.innerHeight < volleHoehe - 150;" in co
    assert "const tastatur = vv.scale <= 1.01 && (vv.height < window.innerHeight - 100 || android);" in co
    assert "if (tastatur && !warTastatur) feldNachziehen(ae, true);" in co


def test_ft4_ft7_rueckmeldung():
    co = lies("app/static/js/common.js")
    toast = co[co.index("  function toast(msg, isError) {"):co.index("  /* --- Zurück schließt Overlays")]
    assert "el.hidePopover();\n      el.showPopover();" in toast and "toastTimer = setTimeout(() => { el.textContent = \"\"; }, 250);" in toast
    assert 'const rolle = isError ? "alert" : "status";' in toast
    assert 'p.className = "error feld-fehler";\n      // Vorgelesen, sobald sie erscheint (Gerätetest FT7); das Feld verweist zusätzlich mit aria-describedby darauf.\n      p.setAttribute("role", "alert");' in co
    assert 'S.toast("Profil gespeichert");' in lies("app/static/js/profile.js")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print(name, "bestanden")
