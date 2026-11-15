"""Freigabe-Mail mit Hinweis „Entwicklungsserver“ (Wunsch vom 15.11.2026):
python tests/test_freigabe_mail_dev.py  oder  pytest tests/test_freigabe_mail_dev.py

Auf dev (STROEMIS_NAME endet auf „-dev“) sagt die Mail „dein Konto ist freigegeben“ ausdrücklich, dass es der
Entwicklungsserver ist – derselbe Wortlaut wie der Dialog nach jeder Anmeldung, samt Fehleradresse; in der Produktion
nicht. Alle Konten sind Platzhalter, es geht keine Mail hinaus."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_module_pwa_kontakt import Umgebung, _anmelden, _app  # noqa: E402


def _freigabe_mail(name):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, Umgebung(STROEMIS_NAME=name):
        app = _app(tmp)
        from app import api_admin
        mails = []
        echt = api_admin.send_mail
        api_admin.send_mail = lambda to, s, b: mails.append((to, s, b)) or True
        try:
            anon = app.test_client()
            anon.post("/api/auth/register", json={"email": "neu@example.org", "password": "passwort1",
                                                  "name": "Neu Platzhalter", "gliederung": "OG Platzhalter"})
            adm = app.test_client()
            _anmelden(adm)
            uid = [u for u in adm.get("/api/admin/users").json["users"] if u["email"] == "neu@example.org"][0]["id"]
            assert adm.post(f"/api/admin/users/{uid}/approve", json={}).status_code == 200
        finally:
            api_admin.send_mail = echt
    assert len(mails) == 1 and mails[0][0] == "neu@example.org"
    return mails[0][2]


def test_dev_mit_hinweis():
    text = _freigabe_mail("stroemis-dev")
    assert "wurde freigegeben" in text and "/login" in text
    assert "Dies ist der Entwicklungsserver von strömis.de, nicht die eigentliche Plattform." in text
    assert "Daten können sich jederzeit ändern, verschwinden oder neu auftauchen." in text
    assert "Es kann und wird zu Fehlern und Problemen kommen." in text
    assert "bugs@stroemis.de" in text


def test_produktion_ohne_hinweis():
    text = _freigabe_mail(None)
    assert "wurde freigegeben" in text and "Entwicklungsserver" not in text


if __name__ == "__main__":
    test_dev_mit_hinweis()
    test_produktion_ohne_hinweis()
    print("ok")
