"""Kopfleiste der Entwicklungsumgebung (Wunsch des Nutzers, 11.11.2026):
python tests/test_dev_kopf.py  oder  pytest tests/test_dev_kopf.py

Auf dev.strömis.de (STROEMIS_NAME endet auf „-dev“, module.dev_umgebung) steht neben dem Zeichen „Entwicklungsserver“
statt „Strömungsrettung“ und darunter „dev.strömis.de“; das Maskottchen trägt einen Leitkegel als Hut
(maskottchen-dev.webp aus scripts/maskottchen_dev.py). Gilt in der Kopfleiste nach der Anmeldung, auf der Anmeldeseite,
in der öffentlichen Strömipedia (Vorlage) und auf der Hinweisseite ohne Netz. In der Produktion bleibt alles, wie es war.
Keine Mails."""
import base64
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_module_pwa_kontakt import Umgebung, _anmelden, _app, lies  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = '<span class="funktion">Entwicklungsserver<small>dev.strömis.de</small></span>'
PROD = '<span class="funktion">Strömungsrettung<small>strömis.de</small></span>'


def _seiten(dev):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
            Umgebung(STROEMIS_NAME="stroemis-dev" if dev else None):
        app = _app(tmp)
        c = app.test_client()
        login = c.get("/login").get_data(as_text=True)
        offline = c.get("/offline").get_data(as_text=True)
        _anmelden(c)
        innen = c.get("/profil").get_data(as_text=True)
        return app.config["MASKOTTCHEN"], login, offline, innen


def test_dev():
    maskottchen, login, offline, innen = _seiten(True)
    assert maskottchen == "img/maskottchen-dev.webp"
    for html in (login, innen):
        assert DEV in html and "Strömungsrettung<small>" not in html
        assert '<img src="/static/img/maskottchen-dev.webp' in html
    assert '<span class="name">Entwicklungsserver<small>dev.strömis.de</small></span>' in offline
    # Die Hinweisseite trägt das Bild als data:-Adresse – die Figur mit Kegel.
    with open(os.path.join(WURZEL, "app/static/img/maskottchen-dev.webp"), "rb") as fh:
        assert "data:image/webp;base64," + base64.b64encode(fh.read()).decode() in offline


def test_produktion_unveraendert():
    maskottchen, login, offline, innen = _seiten(False)
    assert maskottchen == "img/maskottchen.webp"
    for html in (login, innen):
        assert PROD in html and "Entwicklungsserver<small>" not in html
        assert "maskottchen-dev" not in html
    assert '<span class="name">Strömungsrettung<small>strömis.de</small></span>' in offline


def test_vorlagen_und_bild():
    # Öffentliche Strömipedia (Vorlage; /oeffentlich/ leitet heute zur Anmeldung).
    oeff = lies("app/templates/public.html")
    assert ("{% if dev_umgebung %}Entwicklungsserver<small>dev.strömis.de · öffentliche Strömipedia</small>"
            "{% else %}Strömungsrettung<small>strömis.de · öffentliche Strömipedia</small>{% endif %}") in oeff
    # Das Bild: höher als das Maskottchen (Kegel obendrauf), Figur im selben Maßstab, oben orange.
    from PIL import Image
    dev = Image.open(os.path.join(WURZEL, "app/static/img/maskottchen-dev.webp")).convert("RGBA")
    normal = Image.open(os.path.join(WURZEL, "app/static/img/maskottchen.webp"))
    assert dev.width == normal.width and dev.height > normal.height * 1.2, (dev.size, normal.size)
    spitze = [dev.getpixel((x, y)) for y in range(5, 40) for x in range(dev.width)]
    assert any(r > 200 and 60 < g < 150 and b < 60 and a > 200 for r, g, b, a in spitze), "kein orangefarbener Kegel oben"
    skript = lies("scripts/maskottchen_dev.py")
    assert 'QUELLE = os.path.join(WURZEL, "app", "static", "img", "maskottchen.png")' in skript
    assert re.search(r'ZIEL = os\.path\.join\(WURZEL, "app", "static", "img", "maskottchen-dev\.webp"\)', skript)


if __name__ == "__main__":
    test_dev()
    test_produktion_unveraendert()
    test_vorlagen_und_bild()
    print("Kopfleiste dev bestanden.")
