"""Mailfehler-Protokoll und Versand-Wrapper (Phase 4 · Lieferung 1, Kern K2):  python tests/test_material_mailprotokoll.py
oder  pytest tests/test_material_mailprotokoll.py

services/mailprotokoll.senden verschickt jede Modul-Mail und schreibt einen Fehlschlag in mat_mail_fehler (Schritt 19):
Reinigung der Serverantwort (nie eine Adresse, nie der Mailserver), Ausnahmepfad und gesperrte Tabelle (die zweite Mail
geht trotzdem hinaus), Stille je Mailart ohne Zeile (kein Mailserver, Umgebungssperre, DEMO), Sicht (Verwaltung alles,
Zweig-Verwalter seine Gliederungen ohne Verwaltungs-Rollen, Leser nichts, fremde Gliederung 404), Erledigt idempotent und
„Alle erledigt“ nur in der eigenen Sicht, Nachholen durch eine spätere Erinnerung, Pflegefristen, Löschen des Kontos,
Trigger und Migration 18 → 19. Echte Mails gehen nie hinaus: die Nahtstelle mailprotokoll.versand ist ersetzt. Alle Namen,
Adressen und Texte sind Platzhalter."""
import os
import sqlite3
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, freigeben, gliederung, katalog_grund, make_app, neuer_artikel, neues_konto, umgebung  # noqa: E402
from test_material_antrag import logzeilen  # noqa: E402
from test_material_erinnerung import umwelt  # noqa: E402
from test_material_rueckruf import anlegen as rueckruf_anlegen  # noqa: E402
from test_material_rueckruf import post_abfangen, post_zurueck  # noqa: E402
from test_material_trennung import bis_schritt, endversion, sql, zeilen, zwei_gliederungen  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

SMTP = "smtp.example.invalid"
ABGEWIESEN = "Der Mailserver hat den Empfänger abgewiesen – {an}: 550 <{an}> User unknown"
VERBINDUNG = f"Keine Verbindung zum Mailserver {SMTP}:587: [Errno 111] Connection refused"
ANMELDUNG = f"Anmeldung am Mailserver abgelehnt ({SMTP}:587): (535, b'Authentication failed')"


# --- Hilfen --------------------------------------------------------------------------------------------------------

def modul():
    from app.material.services import mailprotokoll
    return mailprotokoll


def fehler(app, wo="", args=()):
    return zeilen(app, f"SELECT * FROM mat_mail_fehler {wo} ORDER BY id", args)


def ref(app, uid):
    with app.app_context():
        from app.material.services import journal
        return journal.konto_ref(uid)["ref"]


class Ersatz:
    """mailprotokoll.versand und MAILSERVER für die Dauer des Blocks ersetzen: antwort(an, betreff, text) liefert
    (ok, meldung) oder wirft; alle Aufrufe stehen in liste."""

    def __init__(self, antwort=None, mailserver=True):
        self.antwort = antwort or (lambda an, b, t: (True, "angenommen (Test)"))
        self.mailserver = mailserver
        self.liste = []

    def __enter__(self):
        m = modul()
        self.alt = (m.versand, m.MAILSERVER)

        def versand(an, betreff, text):
            self.liste.append((an, betreff, text))
            return self.antwort(an, betreff, text)
        m.versand = versand
        m.MAILSERVER = lambda: self.mailserver
        return self.liste

    def __exit__(self, *a):
        m = modul()
        m.versand, m.MAILSERVER = self.alt


def senden(app, an, betreff="Testbetreff", text="Testtext", **kw):
    with app.app_context():
        return modul().senden(an, betreff, text, **kw)


def einfuegen(app, konto_ref, folder_id=None, art="mangel", rolle="verwalter", klasse="verbindung", bezug=("report", 1),
              betreff="Testbetreff", created_at=None, erledigt=None):
    with app.app_context():
        from app import db
        return db.execute(
            "INSERT INTO mat_mail_fehler (art, klasse, bezug_art, bezug_id, folder_id, konto_ref, rolle, betreff, meldung, "
            "created_at, erledigt_at, erledigt_von_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (art, klasse, bezug[0], bezug[1], folder_id, konto_ref, rolle, betreff, "[Mailserver] nicht erreichbar",
             created_at or db.now(), erledigt, "Test" if erledigt else None))


def aufbau(tmp):
    """zwei_gliederungen (A mit wart, fuehrung, katalog = Material-Verwaltung, pruefer; B mit wart_b) und ein Mailserver in
    der Konfiguration (erfunden, gesendet wird nie)."""
    t = zwei_gliederungen(tmp)
    t.app.config["SMTP_HOST"] = SMTP
    t.app.config["SMTP_PORT"] = 587
    return t


def mailfehler(c):
    r = c.get("/api/material/start")
    assert r.status_code == 200, r.get_json()
    return r.json["mailfehler"]


# --- 1. Reinigung ---------------------------------------------------------------------------------------------------

def test_reinigung():
    """Drei Fehlerbilder – abgewiesene Adresse, Ausnahme mit Adresse im Text, Verbindungsfehler mit Host und Port – und
    eine abgelehnte Anmeldung: Keine Zeile trägt ein „@“ oder den Mailserver; Klasse, Bezug, Rolle, Gliederung und
    Kontoverweis stimmen; Betreff und Meldung sind gekürzt (160/300)."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, wart = t.app, t.k["wart_id"]
        an = "Wart@Example.org"
        antworten = {
            "abgewiesen": lambda a, b, x: (False, ABGEWIESEN.format(an=a)),
            "verbindung": lambda a, b, x: (False, VERBINDUNG),
            "anmeldung": lambda a, b, x: (False, ANMELDUNG),
        }

        def wirft(a, b, x):
            raise RuntimeError(f"Timeout beim Senden an {a.lower()} über {SMTP}:587 (Umschlag <noreply@example.org>)")
        antworten["ausnahme"] = wirft
        lang = "Betreff " + "x" * 200
        for name, antwort in antworten.items():
            with Ersatz(antwort) as liste:
                ok = senden(app, an, lang, "Text", art="mangel", konto_id=wart, rolle="verwalter", bezug_art="report",
                            bezug_id=7, folder_id=t.a)
            assert ok is False and len(liste) == 1, (name, liste)
        rows = fehler(app)
        assert [r["klasse"] for r in rows] == ["empfaenger_abgewiesen", "verbindung", "anmeldung", "ausnahme"], rows
        for r in rows:
            assert "@" not in r["meldung"] and SMTP not in r["meldung"] and "example" not in r["meldung"].lower(), r
            assert (r["art"], r["bezug_art"], r["bezug_id"], r["folder_id"], r["rolle"]) == ("mangel", "report", 7, t.a,
                                                                                            "verwalter"), r
            assert r["konto_ref"] == ref(app, wart) and r["erledigt_at"] is None and len(r["betreff"]) == 160, r
        assert rows[0]["meldung"] == "Der Mailserver hat den Empfänger abgewiesen – [Adresse]: 550 <[Adresse]> User unknown"
        assert rows[1]["meldung"] == "Keine Verbindung zum Mailserver [Mailserver]: [Errno 111] Connection refused"
        assert rows[2]["meldung"].startswith("Anmeldung am Mailserver abgelehnt ([Mailserver]): (535")
        assert rows[3]["meldung"] == ("Ausnahme beim Versand: Timeout beim Senden an [Adresse] über [Mailserver] "
                                      "(Umschlag [Adresse])"), rows[3]
        # Überlange Serverantwort: 300 Zeichen, auch wenn die Adresse erst am Ende stünde.
        with Ersatz(lambda a, b, x: (False, "Der Mailserver hat abgelehnt: " + "y" * 400 + f" {a}")):
            senden(app, an, "B", "T", art="mangel", konto_id=wart, rolle="verwalter", bezug_art="report", bezug_id=7,
                   folder_id=t.a)
        r = fehler(app)[-1]
        assert len(r["meldung"]) == 300 and "@" not in r["meldung"] and r["klasse"] == "abgelehnt", r
        # Befund B1 der Sicherheitsprüfung: der Anmeldename in der 535-Antwort (Exim „set_id=…“, ohne „@“) wird ersetzt –
        # als ganzes Wort, ohne Rücksicht auf die Schreibweise; Wörter, die ihn nur enthalten, bleiben.
        app.config["SMTP_USER"] = "smtp-login-xyz"
        with Ersatz(lambda a, b, x: (False, f"Anmeldung am Mailserver abgelehnt ({SMTP}:587): (535, b'Incorrect "
                                            "authentication data (set_id=SMTP-Login-XYZ)') smtp-login-xyz2")):
            senden(app, an, "B", "T", art="mangel", konto_id=wart, rolle="verwalter", bezug_art="report", bezug_id=7,
                   folder_id=t.a)
        r = fehler(app)[-1]
        assert r["meldung"] == ("Anmeldung am Mailserver abgelehnt ([Mailserver]): (535, b'Incorrect authentication "
                                "data (set_id=[Anmeldename])') smtp-login-xyz2"), r["meldung"]
        with app.app_context():
            assert modul().reinigen("Username smtp-login-xyz and password not accepted") == \
                "Username [Anmeldename] and password not accepted"
        # Ein Anmeldename mit „@“ ist eine Adresse und fällt ebenso.
        app.config["SMTP_USER"] = "Login@Example.org"
        with app.app_context():
            assert modul().reinigen("535 set_id=login@example.org") == "535 set_id=[Anmeldename]"
        app.config["SMTP_USER"] = ""
        # Befund B2: Der Betreff läuft durch dieselbe Reinigung (Rückruf-Titel ist freier Text).
        with Ersatz(lambda a, b, x: (False, VERBINDUNG)):
            senden(app, an, f"Rückruf: Produkt – Kontakt {an.lower()}, <info@example.org> über {SMTP}", "T",
                   art="rueckruf", konto_id=wart, rolle="verwalter", bezug_art="recall", bezug_id=3, folder_id=t.a)
        r = fehler(app)[-1]
        assert r["betreff"] == "Rückruf: Produkt – Kontakt [Adresse], [Adresse] über [Mailserver]", r["betreff"]
        n = len(fehler(app))
        # Eine Zeile mit „@“ – in der Meldung oder im Betreff – nimmt die Tabelle nicht an (Netz hinter der Reinigung).
        with app.app_context():
            from app import db
            try:
                db.execute("INSERT INTO mat_mail_fehler (art, klasse, bezug_art, folder_id, konto_ref, rolle, betreff, "
                           "meldung, created_at) VALUES ('mangel', 'verbindung', 'none', NULL, 'abc', 'verwalter', "
                           "'an x@y', 'm', 't')")
                raise AssertionError("Betreff mit @ angenommen")
            except sqlite3.IntegrityError:
                pass
        with app.app_context():
            from app import db
            try:
                db.execute("INSERT INTO mat_mail_fehler (art, klasse, bezug_art, folder_id, konto_ref, rolle, betreff, "
                           "meldung, created_at) VALUES ('mangel', 'verbindung', 'none', NULL, 'abc', 'verwalter', 'b', "
                           "'an x@y', 't')")
                raise AssertionError("Zeile mit @ angenommen")
            except sqlite3.IntegrityError:
                pass
        # Erfolg: keine Zeile, Rückgabe True, nichts geloggt als Fehler.
        with Ersatz() as liste, logzeilen(app) as log:
            assert senden(app, an, art="mangel", konto_id=wart, rolle="pruefer", bezug_art="report", bezug_id=7,
                          folder_id=t.a) is True
        assert len(liste) == 1 and len(fehler(app)) == n and not log, (liste, log)
        # Unbekannte Art oder Rolle: Programmfehler, laut.
        for kw in ({"art": "sms", "rolle": "verwalter"}, {"art": "mangel", "rolle": "chef"},
                   {"art": "mangel", "rolle": "verwalter", "bezug_art": "x"}):
            try:
                senden(app, an, konto_id=wart, **kw)
                raise AssertionError(kw)
            except ValueError:
                pass
    print("Reinigung bestanden.")


# --- 2. Ausnahmepfad und gesperrte Tabelle --------------------------------------------------------------------------

def test_ausnahme_und_gesperrte_tabelle():
    """Eine zweite Verbindung hält die Schreibsperre (BEGIN IMMEDIATE): Die Protokollzeile der ersten, gescheiterten Mail
    lässt sich nicht schreiben – nur eine Logzeile, senden wirft nicht, und die zweite Mail geht trotzdem hinaus. Nach dem
    Ende der Sperre schreibt der nächste Fehlschlag wieder. senden innerhalb einer Transaktion: Logzeile, keine Zeile."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, wart = t.app, t.k["wart_id"]
        sperre = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        sperre.execute("BEGIN IMMEDIATE")
        try:
            with Ersatz(lambda a, b, x: (a != "eins@example.org", "Keine Verbindung zum Mailserver x:1: zu")) as liste, \
                    logzeilen(app) as log, app.app_context():
                from app import db
                db.get_db().execute("PRAGMA busy_timeout = 300")       # nicht 15 s auf die Sperre warten
                erg = [modul().senden(a, "B", "T", art="rueckruf", konto_id=wart, rolle="verwalter", bezug_art="recall",
                                      bezug_id=1, folder_id={t.a}) for a in ("eins@example.org", "zwei@example.org")]
            assert erg == [False, True] and [m[0] for m in liste] == ["eins@example.org", "zwei@example.org"], (erg, liste)
            assert any("Zeile zu rueckruf" in z and "nicht geschrieben" in z for z in log), log
        finally:
            sperre.rollback()
            sperre.close()
        assert fehler(app) == []
        with Ersatz(lambda a, b, x: (False, "Keine Verbindung zum Mailserver x:1: zu")):
            assert senden(app, "eins@example.org", art="rueckruf", konto_id=wart, rolle="verwalter", bezug_art="recall",
                          bezug_id=1, folder_id={t.a}) is False
        assert [(r["klasse"], r["folder_id"]) for r in fehler(app)] == [("verbindung", t.a)]
        # Innerhalb einer Transaktion: Versand ja, Zeile nein (Logzeile).
        with Ersatz(lambda a, b, x: (False, "Keine Verbindung zum Mailserver x:1: zu")), logzeilen(app) as log, \
                app.app_context():
            from app import db
            with db.transaction():
                assert modul().senden("drei@example.org", "B", "T", art="mangel", konto_id=wart, rolle="verwalter",
                                      bezug_art="report", bezug_id=1, folder_id=t.a) is False
        assert any("innerhalb einer Transaktion" in z for z in log), log
        assert len(fehler(app)) == 1
        # Ein Konto, das es nicht (mehr) gibt: keine Zeile, Logzeile.
        with Ersatz(lambda a, b, x: (False, "Keine Verbindung zum Mailserver x:1: zu")), logzeilen(app) as log:
            assert senden(app, "vier@example.org", art="mangel", konto_id=999999, rolle="verwalter", bezug_art="report",
                          bezug_id=1, folder_id=t.a) is False
        assert any("kein Konto 999999" in z for z in log) and len(fehler(app)) == 1, log
        # Ein Ordner, den es nicht mehr gibt: Zeile ohne Gliederung.
        with Ersatz(lambda a, b, x: (False, "Keine Verbindung zum Mailserver x:1: zu")):
            senden(app, "fuenf@example.org", art="mangel", konto_id=wart, rolle="verwalter", bezug_art="report",
                   bezug_id=1, folder_id=999999)
        assert fehler(app)[-1]["folder_id"] is None
    print("Ausnahmepfad und gesperrte Tabelle bestanden.")


# --- 3. Stille ------------------------------------------------------------------------------------------------------

def test_stille():
    """Je Mailart: ohne Mailserver, unter der Umgebungssperre (Variable und …-dev) und an eine DEMO-Adresse bzw. für einen
    DEMO-Gegenstand kein Versand, keine Zeile, Rückgabe False – nur eine Logzeile mit Grund. Über die Dienste: Rückruf-
    und Produktmeldungs-Mails bleiben unter der Sperre jetzt ebenfalls still (Entscheidung Nr. 6)."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, wart = t.app, t.k["wart_id"]
        faelle = [("kein Mailserver", {}, False, "wart@example.org", False),
                  ("Umgebungssperre", {"MATERIAL_ERINNERUNGEN_SPERRE": "1"}, True, "wart@example.org", False),
                  ("Umgebungssperre", {"STROEMIS_NAME": "stroemis-dev"}, True, "wart@example.org", False),
                  ("DEMO-Adresse", {}, True, "demo@beispiel.invalid", False),
                  ("DEMO-Artikel", {}, True, "wart@example.org", True)]
        for art in models.MAILARTEN:
            for grund, umg, mailserver, an, demo in faelle:
                with umwelt(**umg), Ersatz(mailserver=mailserver) as liste, logzeilen(app) as log:
                    ok = senden(app, an, "Testbetreff still", "Testtext still", art=art, konto_id=wart, rolle="verwalter",
                                demo=demo)
                assert ok is False and not liste and not fehler(app), (art, grund, liste)
                assert any(f"Mail nicht verschickt ({grund})" in z and "Testbetreff still" in z and "Testtext still" in z
                           for z in log), (art, grund, log)
        # Rückruf über den Dienst unter der Sperre: kein Versand, mat_recall zählt die Mails als nicht hinausgegangen.
        with umwelt(MATERIAL_ERINNERUNGEN_SPERRE="1"):
            post, alt = post_abfangen()
            try:
                r = rueckruf_anlegen(t.k["katalog"], t.ids["hms"], title="Still")
            finally:
                post_zurueck(alt)
            assert r.status_code == 201 and r.json["empfaenger"] >= 1, r.get_json()
            assert post == [] and not fehler(app)
            z = zeilen(app, "SELECT mail_count, mail_failed FROM mat_recall WHERE id = ?", (r.json["rueckruf"]["id"],))[0]
            assert z["mail_count"] == 0 and z["mail_failed"] >= 1, z
            # Produktmeldung ebenso.
            from app.material.services import meldung
            alt = meldung.HINTERGRUND
            meldung.HINTERGRUND = lambda f, *a: f(*a)
            try:
                with Ersatz() as liste, logzeilen(app) as log:
                    r = t.wart_a.post("/api/material/meldungen", json={"manufacturer": "Stillwerk", "model": "Modell still",
                                                                       "folder_id": t.lager_a})
            finally:
                meldung.HINTERGRUND = alt
            assert r.status_code == 201 and liste == [] and not fehler(app), (r.get_json(), liste)
            assert any("Produktmeldung: Mail nicht verschickt (Umgebungssperre)" in z for z in log), log
    print("Stille bestanden.")


# --- 4. Sicht, Erledigt, Alle erledigt --------------------------------------------------------------------------------

def test_sicht_und_erledigt():
    """Vier Zeilen: A/verwalter, A/verwaltung, B/verwalter, ohne Gliederung (Erinnerung an die Verwaltung). Die
    Material-Verwaltung sieht alle vier, wart_a nur A/verwalter, wart_b nur B/verwalter, fuehrung (liest) nichts (kein
    Block). Erledigt: eigene Zeile 200 und idempotent, fremde und unbekannte 404; „Alle erledigt“ trifft nur die eigene
    Sicht (Leser 403). Ohne Mailserver: Dauerhinweis nur für die Verwaltung."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, k = t.app, t.k
        rw, rb, rk = ref(app, k["wart_id"]), ref(app, t.wart_b_id), ref(app, k["katalog_id"])
        z1 = einfuegen(app, rw, t.a, art="mangel", rolle="verwalter", betreff="Mangel A")
        z2 = einfuegen(app, rk, t.a, art="antrag", rolle="verwaltung", bezug=("change", 3), betreff="Antrag A")
        z3 = einfuegen(app, rb, t.b, art="rueckruf", rolle="verwalter", bezug=("recall", 2), betreff="Rückruf B")
        z4 = einfuegen(app, rk, None, art="erinnerung", rolle="verwaltung", bezug=("none", None), betreff="Erinnerung")
        mv = mailfehler(k["katalog"])
        assert mv["offen"] == 4 and mv["alle"] is True and mv["kein_mailserver"] is False, mv
        assert [z["id"] for z in mv["zeilen"]] == [z4, z3, z2, z1], mv
        z = {x["id"]: x for x in mv["zeilen"]}
        assert (z[z1]["empfaenger"], z[z1]["rolle"], z[z1]["folder_id"], z[z1]["bezug_art"], z[z1]["bezug_id"],
                z[z1]["art_text"]) == ("wart", "verwalter", t.a, "report", 1, "Mangel"), z[z1]
        assert z[z3]["empfaenger"] == "Wart Nachbarstadt" and z[z4]["folder_id"] is None
        assert set(z[z1]) == {"id", "created_at", "art", "art_text", "klasse", "empfaenger", "rolle", "bezug_art",
                              "bezug_id", "folder_id", "betreff", "meldung", "erledigt_at", "erledigt_von_name", "bezug"}
        assert all("@" not in str(v) for x in mv["zeilen"] for v in x.values())
        # Der Bezug als Weg ins Modul (Oberfläche, P4-L1): Mangelmeldung 1 gibt es nicht → Text ohne Weg; Antrag →
        # Meldungen-Seite; Rückruf 2 gibt es nicht → nur Text; Erinnerung ohne Gliederung → nichts.
        assert z[z1]["bezug"] == {"text": "Mangelmeldung", "pfad": None}, z[z1]["bezug"]
        assert z[z2]["bezug"] == {"text": "Änderungsantrag", "pfad": "/materialablage/bestand/antraege"}
        assert z[z3]["bezug"] == {"text": "Rückruf", "pfad": None} and z[z4]["bezug"] == {"text": "", "pfad": None}
        wa = mailfehler(t.wart_a)
        assert wa["offen"] == 1 and [x["id"] for x in wa["zeilen"]] == [z1] and wa["alle"] is False, wa
        wb = mailfehler(t.wart_b)
        assert wb["offen"] == 1 and [x["id"] for x in wb["zeilen"]] == [z3], wb
        assert mailfehler(k["fuehrung"]) is None
        assert mailfehler(k["pruefer"]) is None
        # „Weitere anzeigen“ (Browserprüfung V2): alle offenen Zeilen der Sicht, höchstens LISTE_ALLE; Leser 403.
        r = k["katalog"].get("/api/material/mailfehler")
        assert r.status_code == 200 and r.json["offen"] == 4 and len(r.json["zeilen"]) == 4, r.get_json()
        assert r.json["grenze"] == modul().LISTE_ALLE and r.json["zeilen"][0]["id"] == z4, r.get_json()
        r = t.wart_a.get("/api/material/mailfehler")
        assert r.status_code == 200 and [x["id"] for x in r.json["zeilen"]] == [z1], r.get_json()
        assert k["fuehrung"].get("/api/material/mailfehler").status_code == 403
        # Ohne Mailserver: Dauerhinweis für die Verwaltung, auch ohne Zeilen; für Verwalter und Leser kein Block.
        app.config["SMTP_HOST"] = ""
        assert mailfehler(k["katalog"])["kein_mailserver"] is True
        assert mailfehler(k["fuehrung"]) is None and mailfehler(t.wart_a)["kein_mailserver"] is False
        app.config["SMTP_HOST"] = SMTP

        # Erledigt: eigene Zeile, idempotent; fremde und unbekannte 404; Leser 404.
        r = t.wart_a.post(f"/api/material/mailfehler/{z1}/erledigt", headers=H)
        assert r.status_code == 200 and r.json["zeile"]["erledigt_von_name"] == "wart", r.get_json()
        erledigt_at = r.json["zeile"]["erledigt_at"]
        assert erledigt_at
        r = t.wart_a.post(f"/api/material/mailfehler/{z1}/erledigt", json={})
        assert r.status_code == 200 and r.json["zeile"]["erledigt_at"] == erledigt_at, r.get_json()
        for c, zid in ((t.wart_a, z3), (t.wart_a, z2), (t.wart_a, z4), (t.wart_a, 999999), (k["fuehrung"], z1),
                       (k["fuehrung"], z3), (k["nutzer"], z3)):
            r = c.post(f"/api/material/mailfehler/{zid}/erledigt", headers=H)
            assert r.status_code in (403, 404), (zid, r.status_code, r.get_json())
            if r.status_code == 404:
                assert r.json["error"] == "Mailfehler nicht gefunden.", r.get_json()
        assert t.wart_a.post(f"/api/material/mailfehler/{z3}/erledigt").status_code == 403   # CSRF-Wache
        assert mailfehler(t.wart_a) is None and mailfehler(k["katalog"])["offen"] == 3
        # Alle erledigt: wart_b nur seine; Leser 403; die Verwaltung den Rest.
        r = t.wart_b.post("/api/material/mailfehler/alle-erledigt", headers=H)
        assert r.status_code == 200 and r.json["anzahl"] == 1, r.get_json()
        r = k["fuehrung"].post("/api/material/mailfehler/alle-erledigt", headers=H)
        assert r.status_code == 403 and "Materialwarte" in r.json["error"], r.get_json()
        offen = fehler(app, "WHERE erledigt_at IS NULL")
        assert [x["id"] for x in offen] == [z2, z4], offen
        r = k["katalog"].post("/api/material/mailfehler/alle-erledigt", headers=H)
        assert r.status_code == 200 and r.json["anzahl"] == 2, r.get_json()
        assert not fehler(app, "WHERE erledigt_at IS NULL") and mailfehler(k["katalog"]) is None
        assert {x["erledigt_von_name"] for x in fehler(app)} == {"wart", "Wart Nachbarstadt", "katalog"}
        r = k["katalog"].post("/api/material/mailfehler/alle-erledigt", headers=H)
        assert r.status_code == 200 and r.json["anzahl"] == 0
    print("Sicht und Erledigt bestanden.")


# --- 5. Dienste schreiben mit Bezug, Rolle und Gliederung ----------------------------------------------------------------

def test_dienste():
    """Mangelmeldung: je Empfänger eine Zeile mit Rolle (Verwalter, Prüfer, zugeordnete Person) und der Heimat des
    Artikels als Ordner (Einzelmail); Produktmeldung: Bescheid an den Melder mit Rolle Melder (Konto-Kennung aus der
    Abfrage) und dem Ordner der Meldung; Rückruf: je Gliederung der Artikel in der Mail eine Zeile (Sammelmail)."""
    from app.material.services import mangel, meldung
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, k = t.app, t.k
        _, person_id = neues_konto(app, "person@example.org", name="Person Platzhalter", stufe=0)
        assert t.wart_a.put(f"/api/material/artikel/{t.art_a['id']}/zuordnung", json={"user_id": person_id}).status_code == 200
        alt = mangel.HINTERGRUND
        mangel.HINTERGRUND = lambda f, *a: f(*a)
        try:
            with Ersatz(lambda a, b, x: (False, ABGEWIESEN.format(an=a))) as liste:
                r = k["fuehrung"].post(f"/api/material/artikel/{t.art_a['id']}/mangel", headers=H,
                                       json={"beschreibung": "Platzhalter Mangel"})
            assert r.status_code == 201 and r.json["mail"] is True, r.get_json()
        finally:
            mangel.HINTERGRUND = alt
        rows = fehler(app)
        assert sorted(m[0] for m in liste) == ["person@example.org", "pruefer@example.org", "wart@example.org"], liste
        assert sorted((x["rolle"], x["folder_id"], x["bezug_art"], x["bezug_id"], x["art"]) for x in rows) == \
            sorted([("verwalter", t.lager_a, "report", 1, "mangel"), ("pruefer", t.lager_a, "report", 1, "mangel"),
                    ("zugeordnet", t.lager_a, "report", 1, "mangel")]), rows
        assert {x["konto_ref"] for x in rows} == {ref(app, k["wart_id"]), ref(app, k["pruefer_id"]), ref(app, person_id)}
        assert all("@" not in x["meldung"] and "[Adresse]" in x["meldung"] for x in rows), rows
        assert all("Mangel gemeldet" in x["betreff"] for x in rows if x["rolle"] != "zugeordnet"), rows
        # Der Bezug im Kasten: die Mangelmeldung führt zum Artikel (Inventarnummer, Modul-Route) – auch für wart_a.
        z = mailfehler(t.wart_a)["zeilen"]
        assert z and all(x["bezug"] == {"text": f"Mangelmeldung {t.art_a['inventory_no']}",
                                        "pfad": f"/materialablage/artikel/{t.art_a['id']}"} for x in z), z
        sql(app, "DELETE FROM mat_mail_fehler")

        # Produktmeldung: Melder wart_a bekommt den Bescheid nicht – Zeile mit Rolle Melder und dem Ordner der Meldung.
        alt = meldung.HINTERGRUND
        meldung.HINTERGRUND = lambda f, *a: f(*a)
        try:
            with Ersatz(lambda a, b, x: (False, VERBINDUNG)) as liste:
                r = t.wart_a.post("/api/material/meldungen", json={"manufacturer": "Meldewerk", "model": "Modell X",
                                                                   "folder_id": t.lager_a})
                assert r.status_code == 201, r.get_json()
                mid = r.json["meldung"]["id"]
                r = k["katalog"].post(f"/api/material/meldungen/{mid}/ablehnen", json={"antwort": "Platzhalter nein"})
                assert r.status_code == 200, r.get_json()
        finally:
            meldung.HINTERGRUND = alt
        rows = fehler(app)
        assert [m[0] for m in liste] == ["katalog@example.org", "wart@example.org"], liste
        assert [(x["rolle"], x["folder_id"], x["bezug_art"], x["bezug_id"], x["art"], x["konto_ref"]) for x in rows] == \
            [("verwaltung", t.lager_a, "request", mid, "meldung", ref(app, k["katalog_id"])),
             ("melder", t.lager_a, "request", mid, "meldung", ref(app, k["wart_id"]))], rows
        # Der Zweig-Verwalter sieht beide Zeilen nicht (Rollen nur für die Verwaltung), die Verwaltung schon.
        assert mailfehler(t.wart_a) is None and mailfehler(k["katalog"])["offen"] == 2
        sql(app, "DELETE FROM mat_mail_fehler")

        # Rückruf über beide Gliederungen: Die Material-Verwaltung verwaltet nirgends – Verwalter sind wart (A) und
        # wart_b (B); dazu ein Ordner in A ohne eigenen Verwalter? Nein: alle Artikel in A hat wart. Ein Konto, das beide
        # verwaltet, bekommt eine Mail mit zwei Gliederungen → zwei Zeilen.
        _, beide_id = neues_konto(app, "beide@example.org", name="Beide Warte")
        freigeben(t.adm, t.a, beide_id, "verwalten")
        freigeben(t.adm, t.b, beide_id, "verwalten")
        post, alt = post_abfangen(scheitert=("beide@example.org", "wart_b@example.org"))
        try:
            r = rueckruf_anlegen(k["katalog"], t.ids["hms"], title="Testrückruf")
        finally:
            post_zurueck(alt)
        assert r.status_code == 201, r.get_json()
        ruid = r.json["rueckruf"]["id"]
        assert sorted(m[0] for m in post) == ["beide@example.org", "wart@example.org", "wart_b@example.org"], post
        rows = fehler(app)
        assert sorted((x["konto_ref"], x["folder_id"], x["rolle"], x["bezug_art"], x["bezug_id"]) for x in rows) == \
            sorted([(ref(app, beide_id), t.a, "verwalter", "recall", ruid), (ref(app, beide_id), t.b, "verwalter", "recall", ruid),
                    (ref(app, t.wart_b_id), t.b, "verwalter", "recall", ruid)]), rows
        assert all(x["art"] == "rueckruf" and x["betreff"].startswith("Rückruf: ") for x in rows)
        # wart_a sieht nur die Zeile seiner Gliederung (die von beide an A), wart_b die zwei von B.
        assert [x["folder_id"] for x in mailfehler(t.wart_a)["zeilen"]] == [t.a]
        assert mailfehler(t.wart_b)["offen"] == 2
    print("Dienste bestanden.")


def test_unterordner_verwalter():
    """Befund B1 der Ablaufprüfung: Wer nur einen Unterordner verwaltet (Freigabe „verwalten“ am Lager), bekommt die
    Mangel-Mail als Verwalter der Heimat – und sieht deren Fehlschlag im Kasten, hakt ihn ab; den Fehlschlag aus dem
    Nachbarordner sieht er nicht (404). Der Gliederungs-Verwalter sieht beide (Vererbung nach unten)."""
    from app.material.services import mangel
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, k = t.app, t.k
        fahrzeug = ordner_neu(t.wart_a, t.a, "Fahrzeug Platzhalter")
        art_f = neuer_artikel(t.wart_a, t.ids["hms"], fahrzeug, serial_no="TEST-F-0001")
        lagerwart, lagerwart_id = neues_konto(app, "lagerwart@example.org", name="Lagerwart Platzhalter")
        freigeben(t.adm, t.lager_a, lagerwart_id, "verwalten")
        alt = mangel.HINTERGRUND
        mangel.HINTERGRUND = lambda f, *a: f(*a)
        try:
            with Ersatz(lambda a, b, x: (False, ABGEWIESEN.format(an=a))) as liste:
                for iid in (t.art_a["id"], art_f["id"]):
                    r = k["fuehrung"].post(f"/api/material/artikel/{iid}/mangel", headers=H,
                                           json={"beschreibung": "Platzhalter Mangel"})
                    assert r.status_code == 201, r.get_json()
        finally:
            mangel.HINTERGRUND = alt
        assert "lagerwart@example.org" in [m[0] for m in liste], liste
        eigene = fehler(app, "WHERE konto_ref = ?", (ref(app, lagerwart_id),))
        assert [(x["folder_id"], x["rolle"]) for x in eigene] == [(t.lager_a, "verwalter")], eigene
        nachbar = [x for x in fehler(app) if x["folder_id"] == fahrzeug]
        assert nachbar, fehler(app)
        # Der Lagerwart sieht nur die Zeilen des Lagers (seine und die des Gliederungs-Verwalters bzw. Prüfers dort).
        lw = mailfehler(lagerwart)
        assert lw and {x["folder_id"] for x in lw["zeilen"]} == {t.lager_a} and eigene[0]["id"] in \
            [x["id"] for x in lw["zeilen"]], lw
        # Der Gliederungs-Verwalter sieht beide Ordner.
        assert {x["folder_id"] for x in mailfehler(t.wart_a)["zeilen"]} == {t.lager_a, fahrzeug}
        # Nachbarordner: 404 wie unbekannt; eigene Zeile abhaken: 200.
        r = lagerwart.post(f"/api/material/mailfehler/{nachbar[0]['id']}/erledigt", headers=H)
        assert r.status_code == 404, r.get_json()
        r = lagerwart.post(f"/api/material/mailfehler/{eigene[0]['id']}/erledigt", headers=H)
        assert r.status_code == 200 and r.json["zeile"]["erledigt_von_name"] == "Lagerwart Platzhalter", r.get_json()
        # „Alle erledigt“ trifft nur das Lager – die Zeilen des Fahrzeugs bleiben offen.
        r = lagerwart.post("/api/material/mailfehler/alle-erledigt", headers=H)
        assert r.status_code == 200, r.get_json()
        assert all(x["erledigt_at"] is None for x in fehler(app) if x["folder_id"] == fahrzeug)
        assert all(x["erledigt_at"] for x in fehler(app) if x["folder_id"] == t.lager_a)
    print("Unterordner-Verwalter bestanden.")


def test_oberflaeche_kasten():
    """Statisch (Browserprüfung P4-L1): Fokus nach „Erledigt“ auf die nächste Zeile bzw. die Überschrift, nach „Alle
    erledigt“ auf die Meldung; „Alle erledigt“ nur nach Rückfrage, btn danger nur dort; „Weitere anzeigen“ über
    GET …/mailfehler; vier Spalten, Fehlertext vor der Serverantwort; Karten bis 800 px Inhaltsbreite."""
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    css = open(os.path.join(wurzel, "app/material/static/material.css"), encoding="utf-8").read()
    anfang = js.index("  function mailZeile(z) {")
    block = js[anfang:js.index("  /* Fälligkeiten je Ordner", anfang)]
    assert "<th>Mail</th>" in block and "<th>Empfänger</th><th>Fehler</th>" in block and block.count("</th>") == 4, block[:400]
    assert 'class="mat-mail-fehler">${esc(MAIL_KLASSE[z.klasse] || z.klasse)}${z.meldung ? `<div class="mat-mail-meldung">' in block
    assert 'nachbar = tr.nextElementSibling || tr.previousElementSibling' in block
    assert '$(\'[data-act="mail-erledigt"]\', nachbar).focus()' in block and '$("#mat-mail-titel").focus()' in block
    assert '$("#mat-mail-stand").focus()' in block and 'id="mat-mail-stand" tabindex="-1"' in block
    assert 'id="mat-mail-titel" tabindex="-1"' in block and "api(`${API}/mailfehler`)" in block
    assert block.count('class="btn danger"') == 1 and 'id="mf-alle-ok"' in block and "als erledigt markieren?" in block
    assert "deiner Sicht" not in block and "btn ghost" not in block
    assert "@container mat-seite (max-width: 800px)" in css and "@container mat-seite (max-width: 1100px) {\n  #mat-inhalt table.list.mat-mail" not in css
    print("Oberfläche Kasten bestanden.")


# --- 6. Nachgeholt, Pflege, Konto löschen, Trigger ------------------------------------------------------------------------

def test_nachgeholt_pflege_loeschen_trigger():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, k = t.app, t.k
        rw, rb = ref(app, k["wart_id"]), ref(app, t.wart_b_id)
        # Nachgeholt: Eine gelungene Erinnerung schließt nur offene Erinnerungs-Fehler desselben Kontos.
        e1 = einfuegen(app, rw, t.a, art="erinnerung", bezug=("none", None))
        e2 = einfuegen(app, rb, t.b, art="erinnerung", bezug=("none", None))
        m1 = einfuegen(app, rw, t.a, art="mangel")
        with Ersatz():
            assert senden(app, "wart@example.org", art="erinnerung", konto_id=k["wart_id"], rolle="verwalter",
                          folder_id={t.a}) is True
        rows = {x["id"]: x["erledigt_von_name"] for x in fehler(app)}
        assert rows == {e1: "nachgeholt", e2: None, m1: None}, rows
        with Ersatz():
            assert senden(app, "wart@example.org", art="mangel", konto_id=k["wart_id"], rolle="verwalter",
                          bezug_art="report", bezug_id=1, folder_id=t.a) is True
        assert {x["id"]: x["erledigt_von_name"] for x in fehler(app)}[m1] is None     # nur Erinnerungen holen nach
        sql(app, "DELETE FROM mat_mail_fehler")

        # Pflege: älter als 13 Monate weg, erledigte älter als 3 Monate weg, Waisen weg, der Rest bleibt.
        from app.material.services.interval import plus_monate
        heute = date.today()
        alt = plus_monate(heute, -14).isoformat() + "T06:00:00+00:00"
        jung = plus_monate(heute, -12).isoformat() + "T06:00:00+00:00"
        e_alt = plus_monate(heute, -4).isoformat() + "T06:00:00+00:00"
        e_jung = plus_monate(heute, -2).isoformat() + "T06:00:00+00:00"
        a = einfuegen(app, rw, t.a, created_at=alt)
        b = einfuegen(app, rw, t.a, created_at=jung)
        c = einfuegen(app, rw, t.a, created_at=jung, erledigt=e_alt)
        d = einfuegen(app, rw, t.a, created_at=jung, erledigt=e_jung)
        w = einfuegen(app, "waise-ohne-konto", t.a, created_at=jung)
        with app.app_context():
            erg = modul().aufraeumen()
        assert erg == {"alt": 1, "erledigt": 1, "waisen": 1}, erg
        assert [x["id"] for x in fehler(app)] == [b, d], (a, c, w)
        # Dasselbe beim Start (Verbindung des Startlaufs) und im Tageslauf.
        einfuegen(app, rw, t.a, created_at=alt)
        app2 = make_app(tmp)
        assert [x["id"] for x in fehler(app2)] == [b, d]
        einfuegen(app2, rw, t.a, created_at=alt)
        with app2.app_context():
            from app.material.services import erinnerung
            p = erinnerung.aufraeumen()
        assert p["mailfehler"] == {"alt": 1, "erledigt": 0, "waisen": 0}, p
        sql(app2, "DELETE FROM mat_mail_fehler")

        # Konto löschen: seine Zeilen gehen mit, andere bleiben; die Zahl im Dialog bleibt, wie sie war.
        _, weg_id = neues_konto(app, "weg@example.org", name="Geht Weg")
        freigeben(t.adm, t.a, weg_id, "verwalten")
        rweg = ref(app2, weg_id)
        einfuegen(app2, rweg, t.a)
        einfuegen(app2, rweg, None, art="erinnerung", bezug=("none", None))
        bleibt = einfuegen(app2, rw, t.a)
        adm = t.adm
        assert adm.delete(f"/api/admin/users/{weg_id}", headers=H).status_code == 200
        assert [x["id"] for x in fehler(app2)] == [bleibt]

        # Trigger: nur erledigt_* ändern; Löschen des Ordners setzt die Gliederung auf NULL; kein Ersetzen.
        pfad = os.path.join(tmp, "stroemis.db")
        conn = sqlite3.connect(pfad)
        conn.execute("PRAGMA foreign_keys = ON")
        for befehl in ("UPDATE mat_mail_fehler SET betreff = 'anders'", "UPDATE mat_mail_fehler SET meldung = 'anders'",
                       "UPDATE mat_mail_fehler SET art = 'antrag'", "UPDATE mat_mail_fehler SET klasse = 'ausnahme'",
                       "UPDATE mat_mail_fehler SET konto_ref = 'x'", "UPDATE mat_mail_fehler SET rolle = 'pruefer'",
                       "UPDATE mat_mail_fehler SET bezug_id = 9", "UPDATE mat_mail_fehler SET created_at = 'x'",
                       f"UPDATE mat_mail_fehler SET folder_id = {t.b}",
                       "UPDATE mat_mail_fehler SET erledigt_at = 'x'"):          # ohne Namen: CHECK
            try:
                conn.execute(befehl)
                raise AssertionError(befehl)
            except sqlite3.IntegrityError:
                conn.rollback()
        conn.execute("UPDATE mat_mail_fehler SET erledigt_at = 'x', erledigt_von_name = 'Test'")
        conn.commit()
        conn.close()
        # Ordner löschen: ein leerer Unterordner mit einer Zeile (die Gliederung selbst hat Artikel).
        leer = ordner_neu(t.wart_a, t.a, "Leer")
        z = einfuegen(app2, rw, leer)
        assert t.wart_a.delete(f"/api/material/ordner/{leer}", headers=H).status_code == 200
        assert fehler(app2, "WHERE id = ?", (z,))[0]["folder_id"] is None
    print("Nachgeholt, Pflege, Konto löschen und Trigger bestanden.")


# --- 7. Migration 18 → 19 -----------------------------------------------------------------------------------------------

def test_migration_19():
    """18 → 19 auf einem Datenordner mit Bestand: Tabelle, Indizes und Trigger entstehen, die Zeilen bleiben; ein zweiter
    Lauf ändert nichts (nur IF NOT EXISTS); Schritt 19 ist für sich wiederholbar; eine Datenbank auf Stand 18 trägt noch
    keine Tabelle, die Startpflege übersteht das (Tabellen-Guard)."""
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        app18 = bis_schritt(18)(make_app, tmp)
        pfad = os.path.join(tmp, "stroemis.db")

        def schema():
            conn = sqlite3.connect(pfad)
            out = {(r[0], r[1]) for r in conn.execute("SELECT type, name FROM sqlite_master WHERE name LIKE '%mail_fehler%' "
                                                        "OR name IN ('idx_mat_inspection_inspected_on', "
                                                        "'idx_mat_audit_entity_action')")}
            conn.close()
            return out
        assert zeilen(app18, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == "18"
        assert schema() == set()
        app, k = umgebung(tmp)
        gid, _ = gliederung(k["adm"])
        lager = ordner_neu(k["wart"], gid, "Lager")
        ids = katalog_grund(k["adm"])
        art = neuer_artikel(k["wart"], ids["hms"], lager, serial_no="MIG-1")
        vorher = zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"]
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        soll = {("table", "mat_mail_fehler"), ("index", "idx_mat_mail_fehler_offen"), ("index", "idx_mat_mail_fehler_ordner"),
                ("index", "idx_mat_mail_fehler_konto"), ("trigger", "mat_mail_fehler_fest"),
                ("trigger", "mat_mail_fehler_ordner"), ("index", "idx_mat_inspection_inspected_on"),
                ("index", "idx_mat_audit_entity_action")}
        assert schema() == soll, schema()
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_item")[0]["n"] == vorher and art["id"]
        # Zweiter Lauf und Schritt 19 für sich: keine Änderung.
        make_app(tmp)
        assert schema() == soll
        conn = sqlite3.connect(pfad)
        for befehl in models.SCHRITT_19:
            conn.execute(befehl)
        conn.commit()
        conn.close()
        assert schema() == soll
        assert models.SCHEMA_VERSION >= 20 and models.SCHRITTE[19] is models.SCHRITT_19   # seit Schritt 21: 21
    print("Migration 18 → 19 bestanden.")


if __name__ == "__main__":
    test_reinigung()
    test_ausnahme_und_gesperrte_tabelle()
    test_stille()
    test_sicht_und_erledigt()
    test_dienste()
    test_unterordner_verwalter()
    test_oberflaeche_kasten()
    test_nachgeholt_pflege_loeschen_trigger()
    test_migration_19()
    print("Alle Tests zum Mailfehler-Protokoll bestanden.")
