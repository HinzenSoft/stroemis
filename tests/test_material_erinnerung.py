"""Tests zu den Erinnerungen im Modul „Material“ (Phase 2 · Lieferung 2):  python tests/test_material_erinnerung.py

Ein Tageslauf ab 6 Uhr deutscher Zeit schickt den Verwaltern eines Ordners eine Sammelmail zu Fälligkeiten (30 und 7 Tage
vorher, überfällig), zum Lebensende (90 Tage vorher) und zu Freigaben, die in 30 Tagen ablaufen – je Stufe einmal (Log
mit Kontoverweis). Dazu der Pflegeteil (Journal „freigabe_abgelaufen“, Aufräumen), der Schalter je Ordner, Laufstand und
Probelauf, die Kommandozeile „flask material remind“ und der Thread. Echte Mails gehen nie hinaus: erinnerung.send_mail
ist ersetzt, der Mailserver heißt smtp.example.invalid. Alle Namen, Produkte, Nummern und Daten sind erfunden."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import types
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, freigeben, gliederung, katalog_grund, make_app, neuer_artikel, pruef_formulare,  # noqa: E402
                           starten, umgebung)
from test_material_rueckruf import konto  # noqa: E402
from test_material_trennung import (endversion, erinnerungslog_wie_schritt_1, erinnerungslog_wie_schritt_11, sql,  # noqa: E402
                                    zeilen)
from test_material_ueberblick import ordner_neu, zustand  # noqa: E402

# Die Tests rechnen ohne Sperre aus der Umgebung (test_schalter_aus setzt sie gezielt).
for _name in ("MATERIAL_ERINNERUNGEN", "MATERIAL_ERINNERUNGEN_SPERRE", "STROEMIS_NAME"):
    os.environ.pop(_name, None)

ZONE = ZoneInfo("Europe/Berlin")
T0 = date(2026, 11, 2)                 # ein Montag; jeder Test stellt die Uhr selbst
SMTP = "smtp.example.invalid"
BASIS = "https://strömis.de"


# --- Hilfen --------------------------------------------------------------------------------------------------------

class Uhr(datetime):
    """Ersetzt services.datetime: heute() und jetzt() rechnen dann mit dieser Uhr (Muster aus test_material_trennung)."""
    jetzt = None

    @classmethod
    def now(cls, tz=None):
        return cls.jetzt.astimezone(tz) if tz else cls.jetzt


def um(tag, stunde=8, minute=0):
    """Ein Zeitpunkt in deutscher Zeit."""
    return datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=ZONE)


@contextmanager
def uhr(jetzt):
    from app.material import services
    alt = services.datetime
    Uhr.jetzt = jetzt
    services.datetime = Uhr
    try:
        yield Uhr
    finally:
        services.datetime = alt


def tag(n, stunde=8):
    """Die Uhr auf T0 + n Tage stellen (deutsche Zeit)."""
    Uhr.jetzt = um(T0 + timedelta(days=n), stunde)


@contextmanager
def post(scheitert=(), wirft=(), bei=None, schlaf=0):
    """erinnerung.send_mail durch eine Liste ersetzen: an Adressen aus scheitert geht nichts hinaus (False), an Adressen
    aus wirft gibt es eine Ausnahme; bei(an) läuft vor jeder Mail (etwa: etwas löschen, die Uhr stellen)."""
    import time
    from app.material.services import erinnerung
    liste = []
    alt = erinnerung.send_mail

    def senden(an, betreff, text):
        liste.append((an, betreff, text))
        if bei:
            bei(an)
        if schlaf:
            time.sleep(schlaf)
        if an in wirft:
            raise RuntimeError("Testausnahme beim Senden")
        return an not in scheitert
    erinnerung.send_mail = senden
    try:
        yield liste
    finally:
        erinnerung.send_mail = alt


@contextmanager
def versand(app, an=True, smtp=SMTP):
    """Schalter und Mailserver nur für die Dauer des Blocks (der Mailserver ist erfunden, gesendet wird nie)."""
    alt = {k: app.config.get(k) for k in ("MATERIAL_ERINNERUNGEN", "SMTP_HOST")}
    app.config.update(MATERIAL_ERINNERUNGEN=an, SMTP_HOST=smtp)
    try:
        yield
    finally:
        app.config.update(alt)


@contextmanager
def umwelt(**werte):
    """Umgebungsvariablen für die Dauer des Blocks (None entfernt sie)."""
    alt = {k: os.environ.get(k) for k in werte}
    for k, v in werte.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in alt.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def erinnerung_modul():
    from app.material.services import erinnerung
    return erinnerung


def lauf(app, **kw):
    with app.app_context():
        return erinnerung_modul().tageslauf(**kw)


def planen(app, stichtag=None):
    from app.material import services
    with app.app_context():
        return erinnerung_modul().planen(stichtag or services.heute())


def mit(app, f, *a, **kw):
    with app.app_context():
        return f(*a, **kw)


def log(app, ab=0):
    return zeilen(app, "SELECT * FROM mat_reminder_log WHERE id > ? ORDER BY id", (ab,))


def letzte_log_id(app):
    return zeilen(app, "SELECT COALESCE(MAX(id), 0) AS m FROM mat_reminder_log")[0]["m"]


def ref(app, uid):
    return zeilen(app, "SELECT mat_ref FROM users WHERE id = ?", (uid,))[0]["mat_ref"]


def an(liste, adresse):
    return [m for m in liste if m[0] == adresse]


def cli(app, *args):
    """flask material remind … – Rückgabe (Exit-Code, Ausgabe samt Fehlerausgabe)."""
    r = app.test_cli_runner().invoke(args=["material", "remind", *args])
    if r.exception and not isinstance(r.exception, SystemExit):
        raise r.exception
    text = r.output
    try:
        text += r.stderr
    except (ValueError, AttributeError):
        pass
    return r.exit_code, text


def artikel(app, c, produkt, ordner, serie, faellig=None, lebensende=None, neu=False):
    """Ein Artikel über die Schnittstelle, danach Fälligkeit, Lebensende und letzte Prüfung direkt gesetzt."""
    a = neuer_artikel(c, produkt, ordner, serial_no=serie, manufactured_on="2024-03")   # textil: Herstellung Pflicht
    zustand(app, a["id"], next_due_on=faellig.isoformat() if faellig else None,
            retire_by=lebensende.isoformat() if lebensende else None,
            last_inspected_on=None if neu else "2025-01-15")
    return a


def viele(app, produkt, ordner, n, faellig, vorsatz):
    """n Artikel direkt in der Datenbank (schneller als über die Schnittstelle) – alle mit derselben Fälligkeit."""
    with app.app_context():
        from app import db
        jetzt = db.now()
        with db.transaction():
            for i in range(n):
                db.execute("INSERT INTO mat_item (product_id, folder_id, serial_no, inventory_no, next_due_on, "
                           "last_inspected_on, qr_token, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                           (produkt, ordner, f"{vorsatz}-{i}", f"{vorsatz}-{i:05d}", faellig.isoformat(), "2025-01-15",
                            f"tok-{vorsatz}-{i}", jetzt, jetzt))


def aufbau(tmp):
    """Umgebung mit Katalog und der Gliederung „OG Musterstadt“ samt „Lager“ – wart verwaltet sie (Standardfreigaben),
    katalog ist die Material-Verwaltung, adm die Plattform-Verwaltung („Administrator“)."""
    app, k = umgebung(tmp)
    ids = katalog_grund(k["adm"])
    gid, system = gliederung(k["wart"])
    lager = ordner_neu(k["wart"], gid, "Lager")
    k["adm_id"] = zeilen(app, "SELECT id FROM users WHERE email = 'admin@example.org'")[0]["id"]
    return app, k, ids, gid, system, lager


# --- 1. Migration ------------------------------------------------------------------------------------------------

def test_migration_11():
    from app.material import models
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        pfad = os.path.join(tmp, "stroemis.db")
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == "11"
        assert erinnerungslog_wie_schritt_11(app)
        tabelle = zeilen(app, "SELECT sql FROM sqlite_master WHERE name = 'mat_reminder_log'")[0]["sql"]
        assert "freigabe_ablauf" in tabelle and "sent_to" not in tabelle, tabelle
        conn = sqlite3.connect(pfad)
        conn.execute("INSERT INTO mat_folder (name, created_at, updated_at) VALUES ('Test', 'x', 'x')")
        assert conn.execute("SELECT reminders_off FROM mat_folder").fetchone()[0] == 0
        for befehl in ("UPDATE mat_folder SET reminders_off = 2",):
            try:
                conn.execute(befehl)
                raise AssertionError(befehl)
            except sqlite3.IntegrityError:
                pass
        einfuegen = "INSERT INTO mat_reminder_log (item_id, grant_id, kind, due_on, konto_ref, sent_at) VALUES (?,?,?,?,?,?)"
        conn.execute(einfuegen, (1, None, "30_tage", "2026-11-01", "abc", "t"))
        conn.execute(einfuegen, (1, None, "7_tage", "2026-11-01", "abc", "t"))      # andere Stufe: erlaubt
        conn.execute(einfuegen, (None, 1, "freigabe_ablauf", "2026-11-01", "abc", "t"))
        for zeile in ((1, None, "30_tage", "2026-11-01", "abc", "t"),             # doppelt (Artikel)
                      (None, 1, "freigabe_ablauf", "2026-11-01", "abc", "t"),     # doppelt (Freigabe)
                      (None, None, "30_tage", "2026-11-01", "abc", "t"),          # kein Ziel
                      (1, 1, "30_tage", "2026-11-01", "abc", "t"),                # zwei Ziele
                      (1, None, "freigabe_ablauf", "2026-11-01", "abc", "t"),     # Freigabestufe am Artikel
                      (None, 2, "faellig", "2026-11-01", "abc", "t"),             # Artikelstufe an der Freigabe
                      (2, None, "30_tage", None, "abc", "t"),                     # ohne Fälligkeit
                      (2, None, "30_tage", "1.11.2026", "abc", "t"),              # kein JJJJ-MM-TT
                      (2, None, "30_tage", "2026-11-01", "", "t"),                # ohne Kontoverweis
                      (2, None, "erinnert", "2026-11-01", "abc", "t")):           # unbekannte Stufe
            try:
                conn.execute(einfuegen, zeile)
                raise AssertionError(zeile)
            except sqlite3.IntegrityError:
                pass
        conn.rollback()
        conn.close()

        # 10 → 11: das Log in der Form aus Schritt 1 mit zwei gleichen Altzeilen, ohne Schalter am Ordner.
        app_k, k = umgebung(tmp)
        gid, _ = gliederung(k["adm"], "OG Altstand")
        ordner_vorher = zeilen(app_k, "SELECT * FROM mat_folder ORDER BY id")
        erinnerungslog_wie_schritt_1(pfad)
        conn = sqlite3.connect(pfad)
        for _ in range(2):
            conn.execute("INSERT INTO mat_reminder_log (item_id, kind, due_on, sent_to, sent_at) "
                         "VALUES (1, '30_tage', '2026-11-01', 'alt@example.org', '2026-10-01T04:00:00+00:00')")
        conn.execute("UPDATE mat_meta SET wert = '10' WHERE schluessel = 'schema_version'")
        conn.commit()
        assert "reminders_off" not in [r[1] for r in conn.execute("PRAGMA table_info(mat_folder)")]
        conn.close()
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        assert erinnerungslog_wie_schritt_11(app) and not log(app)
        assert zeilen(app, "SELECT * FROM mat_folder ORDER BY id") == [dict(o, reminders_off=0) for o in ordner_vorher]

        # Ein zweiter Lauf ändert nichts – auch Schritt 11 direkt nicht.
        conn = sqlite3.connect(pfad)
        n = conn.total_changes
        assert models.migrieren(conn) == models.SCHEMA_VERSION
        conn.execute("BEGIN")
        models._schritt_11(conn)
        assert conn.total_changes == n
        conn.rollback()
        conn.close()
    print("Migration 11 bestanden.")


# --- 2. Stufen ---------------------------------------------------------------------------------------------------

def test_stufen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        e = erinnerung_modul()
        d = date(2026, 12, 1)
        assert [e.stufe(d.isoformat(), d - timedelta(days=n)) for n in (31, 30, 8, 7, 0, -1)] == \
            [None, "30_tage", "30_tage", "7_tage", "7_tage", "faellig"]
        try:
            e.stufe("2026-02-30", d)
            raise AssertionError("unlesbares Datum")
        except ValueError:
            pass
        with uhr(um(T0)):
            r = T0 + timedelta(days=91)
            a = artikel(app, k["wart"], ids["gurt"], lager, "G-1", faellig=T0 + timedelta(days=200), lebensende=r)
            neu = artikel(app, k["wart"], ids["hms"], lager, "N-1", faellig=T0 + timedelta(days=20), neu=True)
            kand, _ = mit(app, e.artikel_kandidaten, T0)
            assert [(x.kennung, x.stufe) for x in kand] == [(neu["id"], "30_tage")], kand
            kand, _ = mit(app, e.artikel_kandidaten, T0 + timedelta(days=1))          # R − 90
            assert (a["id"], "lebensdauer", r.isoformat()) in [(x.kennung, x.stufe, x.faellig_am) for x in kand]
            # Freigabe: V − 31 nichts, V − 30 ein Eintrag.
            ext, ext_id = konto(app, k["adm"], "extern@example.org")
            v = T0 + timedelta(days=31)
            freigeben(k["adm"], gid, ext_id, "lesen", bis=v)
            assert not mit(app, e.freigaben_kandidaten, T0)[0]
            kand = mit(app, e.freigaben_kandidaten, T0 + timedelta(days=1))[0]
            assert [(x.stufe, x.faellig_am, x.daten["recht"]) for x in kand] == [("freigabe_ablauf", v.isoformat(),
                                                                                  "lesen")]
            # Status „neu“: Zusatz in der Mail.
            p = planen(app)
            text = an([(m.adresse, m.betreff, m.text) for m in p.mails], "wart@example.org")[0][2]
            assert "N-1   fällig am" in text and "Eingangsprüfung offen" in text, text
    print("Stufen bestanden.")


# --- 3. Nachholen ------------------------------------------------------------------------------------------------

def test_nachholen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        wart_ref = None
        with uhr(um(T0)), versand(app), post() as liste:
            d1 = T0 + timedelta(days=20)
            a1 = artikel(app, k["wart"], ids["hms"], lager, "NH-1", faellig=d1)
            a2 = artikel(app, k["wart"], ids["hms"], lager, "NH-2")          # zunächst ohne Fälligkeit
            d3 = T0 + timedelta(days=3)
            a3 = artikel(app, k["wart"], ids["hms"], lager, "NH-3", faellig=d3)
            gesehen, mailtage = {}, set()

            def lauf_am(n):
                tag(n)
                ab = letzte_log_id(app)
                r = lauf(app)
                assert r.get("mails") and not r["mails"]["fehler"], r
                if log(app, ab):
                    mailtage.add(n)
                # nur Artikel – die Prüffreigabe der Standardfreigaben läuft nach einem Jahr auch ab
                neu = {(z["item_id"], z["kind"], z["due_on"]) for z in log(app, ab) if z["item_id"]}
                gesehen[n] = neu
                return neu

            assert lauf_am(0) == {(a1["id"], "30_tage", d1.isoformat()), (a3["id"], "7_tage", d3.isoformat())}
            wart_ref = ref(app, k["wart_id"])
            assert {z["konto_ref"] for z in log(app)} == {wart_ref}
            # Zweiter Artikel: erst jetzt eine Fälligkeit in 5 Tagen – nur 7_tage, danach nie 30_tage.
            d2 = T0 + timedelta(days=6)
            zustand(app, a2["id"], next_due_on=d2.isoformat())
            # Dritter Artikel: Prüfung am Tag 1, neue Fälligkeit ein Jahr später – neuer Zyklus.
            from app.material.services.interval import plus_monate
            d3neu = plus_monate(d3, 12)
            zustand(app, a3["id"], next_due_on=d3neu.isoformat(), last_inspected_on=(T0 + timedelta(days=1)).isoformat())
            assert lauf_am(1) == {(a2["id"], "7_tage", d2.isoformat())}
            for n in range(2, 22):
                neu = lauf_am(n)
                erwartet = set()
                if n == 13:                                     # D1 − 7
                    erwartet = {(a1["id"], "7_tage", d1.isoformat())}
                if n == 7:                                      # D2 + 1
                    erwartet = {(a2["id"], "faellig", d2.isoformat())}
                if n == 21:                                     # D1 + 1
                    erwartet = {(a1["id"], "faellig", d1.isoformat())}
                assert neu == erwartet, (n, neu)
            assert lauf_am(22) == set() and lauf_am(60) == set()   # D1 + 2, D1 + 40: nichts mehr
            # Der neue Zyklus des dritten Artikels: bei D3′ − 30 (ausgefallene Tage dazwischen sind egal).
            n = (d3neu - T0).days - 30
            neu = lauf_am(n)
            assert neu == {(a3["id"], "30_tage", d3neu.isoformat())}, (n, neu, d3neu)
            assert not [z for z in log(app) if z["item_id"] == a2["id"] and z["kind"] == "30_tage"]
            # Tag D1 (letzter Tag, Status „bald fällig“): nichts – 7_tage steht schon im Log.
            assert gesehen[20] == set()
            assert len(liste) == len(mailtage) and {n for n, neu in gesehen.items() if neu} <= mailtage   # je Tag eine
    print("Nachholen bestanden.")


# --- 4. Doppelläufe ----------------------------------------------------------------------------------------------

def test_doppellaeufe():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        e = erinnerung_modul()
        # Eine zweite Gliederung mit eigenem Verwalter – zwei Empfänger.
        g2, _ = gliederung(k["adm"], "OG Nachbarstadt", standard=False)
        w2, w2_id = konto(app, k["adm"], "wart2@example.org")
        freigeben(k["adm"], g2, w2_id, "verwalten")
        with uhr(um(T0)), versand(app):
            artikel(app, k["wart"], ids["hms"], lager, "DL-1", faellig=T0 + timedelta(days=5))
            artikel(app, w2, ids["hms"], g2, "DL-2", faellig=T0 + timedelta(days=5))
            with post() as liste:
                assert lauf(app)["mails"]["mails"] == 2
                assert lauf(app) == {"uebersprungen": "erledigt", "um": e._utc(um(T0))}, lauf(app)
                assert len(liste) == 2

            # Zwei Läufe gleichzeitig (zwei Arbeitsprozesse): jede Adresse genau eine Mail, einer meldet „läuft“.
            tag(1)
            artikel(app, k["wart"], ids["hms"], lager, "DL-3", faellig=T0 + timedelta(days=30))
            artikel(app, w2, ids["hms"], g2, "DL-4", faellig=T0 + timedelta(days=30))
            ergebnisse, start = [], threading.Barrier(2)

            def los():
                start.wait()
                ergebnisse.append(lauf(app))
            with post(schlaf=0.2) as liste:
                faeden = [threading.Thread(target=los) for _ in range(2)]
                for f in faeden:
                    f.start()
                for f in faeden:
                    f.join()
            assert sorted(liste_an[0] for liste_an in liste) == ["wart2@example.org", "wart@example.org"], liste
            assert sorted(str(r.get("uebersprungen")) for r in ergebnisse) == ["None", "laeuft"], ergebnisse

            # Herzschlag vor 10 min: kein Lauf; vor 31 min: der Lauf übernimmt. Gerechnet mit services.jetzt().
            tag(2)
            sql(app, "INSERT INTO mat_meta (schluessel, wert) VALUES ('tageslauf_laeuft', ?) ON CONFLICT(schluessel) "
                     "DO UPDATE SET wert = excluded.wert", ((Uhr.jetzt - timedelta(minutes=10)).isoformat(),))
            r = lauf(app)
            assert r["uebersprungen"] == "laeuft", r
            code, text = cli(app)
            assert code == 0 and "Ein anderer Lauf ist gerade im Gange (seit 07:50)" in text, text
            code, text = cli(app, "--erneut")
            assert code == 0 and "Ein anderer Lauf ist gerade im Gange" in text, text
            sql(app, "UPDATE mat_meta SET wert = ? WHERE schluessel = 'tageslauf_laeuft'",
                ((Uhr.jetzt - timedelta(minutes=31)).isoformat(),))
            with post():
                r = lauf(app)
            assert r.get("pflege") and r["pflege"]["tag"] == (T0 + timedelta(days=2)).isoformat(), r
            assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'tageslauf_laeuft'")[0]["wert"] == ""
            code, text = cli(app)
            assert code == 0 and "Heute schon gelaufen (08:00)" in text, text
            # --erneut: nur, was noch nicht im Log steht.
            neu = artikel(app, k["wart"], ids["hms"], lager, "DL-5", faellig=T0 + timedelta(days=10))
            with post() as liste:
                code, text = cli(app, "--erneut")
            assert code == 0 and len(liste) == 1 and "DL-5" in liste[0][2] and "DL-3" not in liste[0][2], (text, liste)
            assert {z["item_id"] for z in log(app) if z["due_on"] == (T0 + timedelta(days=10)).isoformat()} == {neu["id"]}

            # Ein Lauf um 23:50, dessen Versand über Mitternacht geht: Plan, Text und Marken bleiben beim Tag T.
            tag(5, 23)
            Uhr.jetzt = Uhr.jetzt.replace(minute=50)
            t = T0 + timedelta(days=5)
            spaet = artikel(app, k["wart"], ids["hms"], lager, "DL-6", faellig=t + timedelta(days=25))

            def mitternacht(_an):
                Uhr.jetzt = um(t + timedelta(days=1), 0, 10)
            with post(bei=mitternacht) as liste:
                r = lauf(app)
            assert r["mails"]["tag"] == t.isoformat() and f"Stand {t.strftime('%d.%m.%Y')}" in liste[0][2], r
            assert "in 25 Tagen" in liste[0][2], liste[0][2]
            assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'erinnerung_tag'")[0]["wert"] == t.isoformat()
            Uhr.jetzt = um(t + timedelta(days=1), 6, 30)
            with post() as liste:
                r = lauf(app)
            assert r["mails"]["tag"] == (t + timedelta(days=1)).isoformat(), r
            assert not [m for m in liste if "DL-6" in m[2]], liste            # DL-1 ist jetzt überfällig, DL-6 nicht neu
            assert len([z for z in log(app) if z["item_id"] == spaet["id"]]) == 1

        # Eine von Hand doppelt eingefügte Zeile verletzt UNIQUE.
        z = log(app)[0]
        conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
        try:
            conn.execute("INSERT INTO mat_reminder_log (item_id, kind, due_on, konto_ref, sent_at) VALUES (?,?,?,?,?)",
                         (z["item_id"], z["kind"], z["due_on"], z["konto_ref"], "2026-11-02T05:00:00+00:00"))
            raise AssertionError("doppelte Zeile angenommen")
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    print("Doppelläufe bestanden.")


# --- 5. Zeitzone -------------------------------------------------------------------------------------------------

def test_zeitzone():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        e = erinnerung_modul()
        from app.material import services
        utc = timezone.utc

        def versuch(jetzt):
            Uhr.jetzt = jetzt
            return mit(app, e.tageslauf_versuchen)
        with uhr(datetime(2026, 10, 17, 22, 30, tzinfo=utc)):
            assert versuch(datetime(2026, 10, 17, 22, 30, tzinfo=utc)) == {"uebersprungen": "zu_frueh"}  # 0:30 MESZ
            assert services.heute() == date(2026, 10, 18)
            assert versuch(datetime(2026, 10, 18, 3, 59, tzinfo=utc)) == {"uebersprungen": "zu_frueh"}   # 5:59 MESZ
            r = versuch(datetime(2026, 10, 18, 4, 0, tzinfo=utc))                                        # 6:00 MESZ
            assert r["pflege"]["tag"] == "2026-10-18", r
            assert versuch(datetime(2026, 10, 18, 4, 15, tzinfo=utc)) == {"uebersprungen": "erledigt"}
            # Tag der Zeitumstellung (25.10.2026, 3 Uhr MESZ → 2 Uhr MEZ): 6 Uhr ist jetzt 5 Uhr UTC.
            assert versuch(datetime(2026, 10, 25, 4, 59, tzinfo=utc)) == {"uebersprungen": "zu_frueh"}
            assert versuch(datetime(2026, 10, 25, 5, 0, tzinfo=utc))["pflege"]["tag"] == "2026-10-25"
            # Winter.
            assert versuch(datetime(2026, 12, 14, 4, 59, tzinfo=utc)) == {"uebersprungen": "zu_frueh"}
            assert versuch(datetime(2026, 12, 14, 5, 0, tzinfo=utc))["pflege"]["tag"] == "2026-12-14"
            # Um 23:30 UTC ist in Deutschland schon der nächste Tag: Eine Fälligkeit am UTC-Tag ist dann überfällig.
            Uhr.jetzt = datetime(2026, 12, 14, 23, 30, tzinfo=utc)
            a = artikel(app, k["wart"], ids["hms"], lager, "TZ-1", faellig=date(2026, 12, 14))
            b = artikel(app, k["wart"], ids["hms"], lager, "TZ-2", faellig=date(2026, 12, 15))
            kand, _ = mit(app, e.artikel_kandidaten, services.heute())
            assert {(x.kennung, x.stufe) for x in kand} >= {(a["id"], "faellig"), (b["id"], "7_tage")}, kand
    print("Zeitzone bestanden.")


# --- 6. Rechteschnitt --------------------------------------------------------------------------------------------

def test_rechteschnitt():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        with uhr(um(T0)):
            f = T0 + timedelta(days=5)
            a = artikel(app, k["wart"], ids["hms"], lager, "RS-A", faellig=f)
            sql(app, "UPDATE mat_item SET assigned_user_id = ? WHERE id = ?", (k["fuehrung_id"], a["id"]))
            gb, _ = gliederung(adm, "OG Nachbarstadt", standard=False)
            wb, wb_id = konto(app, adm, "wart_b@example.org")
            freigeben(adm, gb, wb_id, "verwalten")
            b = artikel(app, wb, ids["hms"], gb, "RS-B", faellig=f)

            def mails(p=None):
                p = p or planen(app)
                return {m.adresse.casefold(): m for m in p.mails}
            m = mails()
            assert set(m) == {"wart@example.org", "wart_b@example.org"}, set(m)
            assert "RS-A" in m["wart@example.org"].text and "RS-B" not in m["wart@example.org"].text
            assert "OG Nachbarstadt" not in m["wart@example.org"].text
            assert "RS-B" in m["wart_b@example.org"].text and "OG Musterstadt" not in m["wart_b@example.org"].text
            assert "kein Materialwart" not in m["wart@example.org"].text

            # Gliederung ohne Verwalter: an die Material-Verwaltung, gekennzeichnet; ohne sie an die Plattform-Verwaltung;
            # eine Plattform-Verwaltung ohne Namen bekommt nichts – der Artikel steht dann „ohne Empfänger“.
            gc, _ = gliederung(adm, "OG Ohnewart", standard=False)
            c = artikel(app, adm, ids["hms"], gc, "RS-C", faellig=f)
            m = mails()
            kat = m["katalog@example.org"].text
            assert "RS-C" in kat and "OG Ohnewart (1) – kein Materialwart eingetragen, darum an die Material-Verwaltung" \
                in kat, kat
            assert f"Materialwart vergeben: {BASIS}/material/ordner/{gc}?freigaben=materialwart" in kat
            assert "weil du zur Material-Verwaltung gehörst" in kat and "RS-A" not in kat
            assert "weil du diese Ordner verwaltest" not in kat                # nur Rückfall – der Satz entfällt
            assert "Du bekommst diese Mail, weil du diese Ordner verwaltest." in m["wart@example.org"].text
            sql(app, "UPDATE users SET recht_material = 1 WHERE id = ?", (k["katalog_id"],))
            m = mails()
            assert "katalog@example.org" not in m and "an die Plattform-Verwaltung" in m["admin@example.org"].text
            sql(app, "UPDATE users SET name = '' WHERE id = ?", (k["adm_id"],))
            p = planen(app)
            assert "admin@example.org" not in mails(p) and [x.kennung for x in p.ohne_empfaenger] == [c["id"]], p
            sql(app, "UPDATE users SET name = 'Administrator' WHERE id = ?", (k["adm_id"],))
            sql(app, "UPDATE users SET recht_material = 2 WHERE id = ?", (k["katalog_id"],))

            # Plattform-Verwaltung als eingetragener Materialwart (und eine zweite Material-Verwaltung): Die PV bekommt
            # ihre Gliederung ohne Rückfall, die übrige Verwaltung nicht. Ebenso eine MV als Materialwart.
            mv2, mv2_id = konto(app, adm, "mv2@example.org", rechte={"material": 2})
            gd, _ = gliederung(adm, "OG Plattform", standard=False)
            freigeben(adm, gd, k["adm_id"], "verwalten")
            artikel(app, adm, ids["hms"], gd, "RS-D", faellig=f)
            ge, _ = gliederung(adm, "OG Verwaltung", standard=False)
            freigeben(adm, ge, k["katalog_id"], "verwalten")
            artikel(app, adm, ids["hms"], ge, "RS-E", faellig=f)
            m = mails()
            assert "RS-D" in m["admin@example.org"].text and "kein Materialwart" not in m["admin@example.org"].text
            assert "RS-E" in m["katalog@example.org"].text and "RS-D" not in m["katalog@example.org"].text
            assert "RS-D" not in m["mv2@example.org"].text and "RS-E" not in m["mv2@example.org"].text
            assert "RS-C" in m["mv2@example.org"].text and "RS-C" in m["katalog@example.org"].text

            # Befristet: gültiger Verwalter ja, abgelaufener nicht. Kein Mail an Deaktivierte, Konten ohne Namen oder
            # ohne Stufe, Prüfer (auch mit Prüffreigabe), Führungskraft (lesen) und die zugeordnete Person.
            gf, _ = gliederung(adm, "OG Befristet", standard=False)
            wf, wf_id = konto(app, adm, "wart_f@example.org")
            wg, wg_id = konto(app, adm, "wart_g@example.org")
            freigeben(adm, gf, wf_id, "verwalten", bis=T0 + timedelta(days=10))
            freigeben(adm, gf, wg_id, "verwalten", bis=T0 - timedelta(days=1))
            artikel(app, adm, ids["hms"], gf, "RS-F", faellig=f)
            sonder = {}
            for name, spalten in (("deaktiviert", "active = 0"), ("namenlos", "name = ''"), ("stufe0", "recht_material = 0")):
                _, uid = konto(app, adm, f"{name}@example.org")
                freigeben(adm, gid, uid, "verwalten")
                sql(app, f"UPDATE users SET {spalten} WHERE id = ?", (uid,))
                sonder[name] = uid
            freigeben(adm, gid, k["pruefer_id"], "pruefen")
            m = mails()
            assert "RS-F" in m["wart_f@example.org"].text and "wart_g@example.org" not in m
            for adresse in ("deaktiviert@example.org", "namenlos@example.org", "stufe0@example.org", "pruefer@example.org",
                            "fuehrung@example.org", "nutzer@example.org"):
                assert adresse not in m, adresse

            # Zwei Konten mit derselben Adresse in anderer Schreibung: eine Mail, beide vermerkt.
            _, dopp_id = konto(app, adm, "doppelt@example.org")
            sql(app, "UPDATE users SET email = 'Wart_B@Example.org' WHERE id = ?", (dopp_id,))
            freigeben(adm, gb, dopp_id, "verwalten")
            gleich = [x for x in planen(app).mails if x.adresse.casefold() == "wart_b@example.org"]
            assert len(gleich) == 1 and len(gleich[0].konten) == 2, gleich
            with versand(app), post() as liste:
                r = lauf(app)
            assert len([x for x in liste if x[0].casefold() == "wart_b@example.org"]) == 1, liste
            refs = {z["konto_ref"] for z in log(app) if z["item_id"] == b["id"]}
            assert refs == {ref(app, wb_id), ref(app, dopp_id)}, (refs, r)
    print("Rechteschnitt bestanden.")


# --- 7. Fehlschläge ----------------------------------------------------------------------------------------------

def test_gescheitert():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        e = erinnerung_modul()
        g2, _ = gliederung(adm, "OG Zweite", standard=False)
        w2, w2_id = konto(app, adm, "zweite@example.org", name="Zweite Wartin")
        freigeben(adm, g2, w2_id, "verwalten")
        with uhr(um(T0)), versand(app):
            d = T0 + timedelta(days=7)
            a = artikel(app, k["wart"], ids["hms"], lager, "GS-1", faellig=d)
            artikel(app, w2, ids["hms"], g2, "GS-2", faellig=d)
            with post(scheitert=("wart@example.org",)) as liste:
                r = lauf(app)
            assert r["mails"]["mails"] == 1 and r["mails"]["fehlgeschlagen"] == 1 and len(liste) == 2, r
            assert {z["konto_ref"] for z in log(app)} == {ref(app, w2_id)}
            st = mit(app, e.stand)
            assert st["letzter"]["fehlgeschlagen_an"] == ["wart"] and "fehlgeschlagen_refs" not in st["letzter"], st
            r = k["katalog"].get("/api/material/start").json["erinnerungen"]
            assert r["letzter"]["fehlgeschlagen"] == 1 and r["letzter"]["fehlgeschlagen_an"] == ["wart"], r
            tag(1)
            with post() as liste:
                lauf(app)
            assert [m[0] for m in liste] == ["wart@example.org"] and "GS-1" in liste[0][2]
            assert [(z["item_id"], z["kind"]) for z in log(app) if z["konto_ref"] == ref(app, k["wart_id"])] == \
                [(a["id"], "7_tage")]

            # send_mail wirft: zählt als Fehlschlag, der nächste Empfänger bekommt seine Mail.
            tag(2)
            artikel(app, k["wart"], ids["hms"], lager, "GS-3", faellig=T0 + timedelta(days=20))
            artikel(app, w2, ids["hms"], g2, "GS-4", faellig=T0 + timedelta(days=20))
            with post(wirft=("wart@example.org",)) as liste:
                r = lauf(app)
            assert r["mails"]["fehlgeschlagen"] == 1 and r["mails"]["mails"] == 1 and len(liste) == 2, r

            # Ein frisch angelegtes Konto (ohne Kontoverweis) als einzige Material-Verwaltung im Rückfall – seine Mail
            # scheitert: Der Stand nennt es trotzdem mit Namen.
            tag(3)
            neu, neu_id = konto(app, adm, "neu-mv@example.org", name="Neue Verwaltung", rechte={"material": 2})
            sql(app, "UPDATE users SET mat_ref = NULL WHERE id = ?", (neu_id,))
            sql(app, "UPDATE users SET recht_material = 1 WHERE id = ?", (k["katalog_id"],))
            g3, _ = gliederung(adm, "OG Ohnewart", standard=False)
            artikel(app, adm, ids["hms"], g3, "GS-5", faellig=T0 + timedelta(days=10))
            with post(scheitert=("neu-mv@example.org",)):
                r = lauf(app)
            assert mit(app, e.stand)["letzter"]["fehlgeschlagen_an"] == ["Neue Verwaltung"], r
            assert ref(app, neu_id)
            sql(app, "UPDATE users SET recht_material = 2 WHERE id = ?", (k["katalog_id"],))

            # Während des Versands werden ein Artikel gelöscht und eine Freigabe der Mail entzogen: kein
            # Fremdschlüsselfehler, die übrigen Zeilen stehen im Log, die Mails danach gehen hinaus.
            tag(4)
            weg = artikel(app, k["wart"], ids["hms"], lager, "GS-6", faellig=T0 + timedelta(days=20))
            bleibt = artikel(app, k["wart"], ids["hms"], lager, "GS-7", faellig=T0 + timedelta(days=20))
            _, ext_id = konto(app, adm, "extern@example.org")
            grant = freigeben(adm, gid, ext_id, "lesen", bis=T0 + timedelta(days=20))
            artikel(app, w2, ids["hms"], g2, "GS-8", faellig=T0 + timedelta(days=20))

            def loeschen(adresse):
                if adresse == "wart@example.org":
                    conn = sqlite3.connect(os.path.join(tmp, "stroemis.db"))
                    conn.execute("DELETE FROM mat_item WHERE id = ?", (weg["id"],))
                    conn.execute("DELETE FROM mat_folder_grant WHERE id = ?", (grant,))
                    conn.commit()
                    conn.close()
            ab = letzte_log_id(app)
            with post(bei=loeschen) as liste:
                r = lauf(app)
            reihe = [m for m in liste if m[0] in ("wart@example.org", "zweite@example.org")]
            assert [m[0] for m in reihe] == ["wart@example.org", "zweite@example.org"], liste
            assert "GS-6" in reihe[0][2] and "extern – lesen bis" in reihe[0][2], reihe[0][2]
            assert r["mails"]["vermerk_fehler"] == 0 and r["mails"]["fehlgeschlagen"] == 0, r
            neu_log = log(app, ab)
            assert bleibt["id"] in {z["item_id"] for z in neu_log} and weg["id"] not in {z["item_id"] for z in neu_log}
            assert not [z for z in neu_log if z["grant_id"]], neu_log

            # Die Pflege scheitert: Der Mailteil läuft trotzdem, der Stand trägt den Fehler.
            tag(5)
            artikel(app, k["wart"], ids["hms"], lager, "GS-9", faellig=T0 + timedelta(days=30))
            alt = e.abgelaufene_eintragen

            def kaputt(_stichtag):
                raise RuntimeError("Testfehler in der Pflege")
            e.abgelaufene_eintragen = kaputt
            try:
                with post() as liste:
                    r = lauf(app)
            finally:
                e.abgelaufene_eintragen = alt
            assert "Testfehler in der Pflege" in r["pflege"]["fehler"] and r["mails"]["mails"] == 1, r
            assert "Testfehler" in mit(app, e.stand)["pflege"]["fehler"]

            # Eine Datenzeile mit unlesbarem Datum: übersprungen und gezählt, die übrigen Mails gehen hinaus; Exit 1.
            tag(6)
            kaputt_a = artikel(app, k["wart"], ids["hms"], lager, "GS-10")
            sql(app, "UPDATE mat_item SET next_due_on = '2026-02-30' WHERE id = ?", (kaputt_a["id"],))
            artikel(app, w2, ids["hms"], g2, "GS-11", faellig=T0 + timedelta(days=30))
            with post() as liste:
                code, text = cli(app)
            assert code == 1 and "1 Datenzeilen ließen sich nicht lesen" in text, text
            assert [m[0] for m in liste] == ["zweite@example.org"], liste
            st = k["katalog"].get("/api/material/start").json["erinnerungen"]
            assert st["letzter"]["fehlerhaft"] == 1 and st["letzter"]["ausloeser"] == "kommandozeile", st
            sql(app, "UPDATE mat_item SET next_due_on = NULL WHERE id = ?", (kaputt_a["id"],))

            # Der Mailteil bricht ganz ab (etwa in der Auswahl): der Fehler steht als letzter.fehler im Stand.
            tag(7)
            alt = e.planen

            def planen_kaputt(_stichtag):
                raise RuntimeError("Testfehler beim Planen")
            e.planen = planen_kaputt
            try:
                r = lauf(app)
            finally:
                e.planen = alt
            st = k["adm"].get("/api/material/start").json["erinnerungen"]
            assert "Testfehler beim Planen" in st["letzter"]["fehler"] and st["letzter"]["tag"] == "2026-11-09", st

        # Versand an, aber kein Mailserver: Es wird nichts versucht, der Pflegeteil läuft, der Stand sagt es.
        with uhr(um(T0 + timedelta(days=8))), versand(app, smtp=""), post() as liste:
            r = lauf(app)
            assert r["mails"] is None and r["pflege"]["tag"] == "2026-11-10" and not liste, r
            st = k["katalog"].get("/api/material/start").json["erinnerungen"]
            assert st["versand"] and not st["smtp"] and st["letzter"]["tag"] == "2026-11-09", st
    print("Fehlschläge bestanden.")


# --- 8. DEMO -----------------------------------------------------------------------------------------------------

def test_demo():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        with uhr(um(T0)):
            f = T0 + timedelta(days=5)
            r = adm.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                         "model": "Demo Gamma", "material_kind": "metall_hardware",
                                                         "interval_months": 12})
            demo_produkt = r.json["produkt"]["id"]
            sql(app, "UPDATE mat_product SET demo = 1 WHERE id = ?", (demo_produkt,))
            artikel(app, k["wart"], demo_produkt, lager, "DM-1", faellig=f)              # DEMO-Produkt, echter Ordner
            gdemo, _ = gliederung(adm, "DEMO OG Beispiel", standard=False)
            sql(app, "UPDATE mat_folder SET demo = 1 WHERE id = ?", (gdemo,))
            artikel(app, adm, ids["hms"], gdemo, "DM-2", faellig=f)                        # echtes Produkt, DEMO-Ordner
            echt = artikel(app, k["wart"], ids["hms"], lager, "DM-3", faellig=f)
            # Ein DEMO-Konto als einziger Verwalter einer Gliederung, die einzige Material-Verwaltung ein DEMO-Konto:
            # Die Mail geht an die Plattform-Verwaltung.
            gx, _ = gliederung(adm, "OG Demowart", standard=False)
            _, dw_id = konto(app, adm, "demo-wart@example.invalid")
            freigeben(adm, gx, dw_id, "verwalten")
            artikel(app, adm, ids["hms"], gx, "DM-4", faellig=f)
            sql(app, "UPDATE users SET email = 'demo-mv@example.invalid' WHERE id = ?", (k["katalog_id"],))
            # Freigaben an einem DEMO-Ordner und eines DEMO-Kontos laufen ab: keine Ablaufmail.
            _, ext_id = konto(app, adm, "extern@example.org")
            freigeben(adm, gdemo, ext_id, "lesen", bis=T0 + timedelta(days=10))
            freigeben(adm, gid, dw_id, "lesen", bis=T0 + timedelta(days=10))
            p = planen(app)
            adressen = {m.adresse for m in p.mails}
            assert adressen == {"wart@example.org", "admin@example.org"}, adressen
            alle = "\n".join(m.text for m in p.mails)
            assert "DM-1" not in alle and "DM-2" not in alle and "DM-3" in alle and "DM-4" in alle, alle
            assert "Plattform-Verwaltung" in {m.adresse: m for m in p.mails}["admin@example.org"].text
            assert not [x for m in p.mails for x in m.eintraege if x.art == "freigabe"]
            assert p.ausgelassen["demo"] == 2 and not p.ohne_empfaenger, p.ausgelassen
            assert echt["id"] in {x.kennung for m in p.mails for x in m.eintraege}
    print("DEMO bestanden.")


def test_demo_probelauf():
    """Probelauf mit DEMO (nur Ansicht): Ohne demo zeigt er nichts aus DEMO, mit demo=1 DEMO-Artikel, -Freigaben und
    -Konten wie echte, mit DEMO-Kennzeichen. Verschicken und Vermerken lehnen einen solchen Plan ab; Tageslauf und
    Kommandozeile ohne --trocken lassen DEMO weiter aus."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        url = "/api/material/erinnerungen/probelauf"
        with uhr(um(T0)):
            f = T0 + timedelta(days=5)
            r = adm.post("/api/material/produkte", json={"category_id": ids["karabiner"], "manufacturer": "Testwerk",
                                                         "model": "Demo Gamma", "material_kind": "metall_hardware",
                                                         "interval_months": 12})
            demo_produkt = r.json["produkt"]["id"]
            sql(app, "UPDATE mat_product SET demo = 1 WHERE id = ?", (demo_produkt,))
            dm1 = artikel(app, k["wart"], demo_produkt, lager, "DM-1", faellig=f)        # DEMO-Produkt, echter Ordner
            gdemo, _ = gliederung(adm, "DEMO OG Beispiel", standard=False)
            sql(app, "UPDATE mat_folder SET demo = 1 WHERE id = ?", (gdemo,))
            dm2 = artikel(app, adm, ids["hms"], gdemo, "DM-2", faellig=f)                  # echtes Produkt, DEMO-Ordner
            artikel(app, k["wart"], ids["hms"], lager, "DM-3", faellig=f)                  # echt
            _, dw_id = konto(app, adm, "demo-wart@example.invalid")                        # DEMO-Materialwart
            freigeben(adm, gdemo, dw_id, "verwalten")
            _, ext_id = konto(app, adm, "extern@example.org")
            demo_freigabe = freigeben(adm, gdemo, ext_id, "lesen", bis=T0 + timedelta(days=10))   # DEMO-Freigabe
            gc, _ = gliederung(adm, "OG Ohnewart", standard=False)
            artikel(app, adm, ids["hms"], gc, "DM-5", faellig=f)                           # echt, Rückfall

            def tabellen():
                return [zeilen(app, f"SELECT * FROM {t} ORDER BY rowid") for t in ("mat_reminder_log", "mat_audit",
                                                                                   "mat_meta")] + \
                    [zeilen(app, "SELECT id, mat_ref FROM users ORDER BY id")]
            vorher = tabellen()

            # Ohne demo: nichts aus DEMO, aber gezählt – das Kästchen der Oberfläche hängt daran.
            p = k["katalog"].get(url).json
            assert p["demo"] is False and all(m["demo"] is False for m in p["mails"]), p
            alle = "\n".join(m["text"] for m in p["mails"])
            assert "DM-1" not in alle and "DM-2" not in alle and "DEMO" not in alle and "DM-3" in alle, alle
            assert p["ausgelassen"]["demo"] == 2 and p["ausgelassen"]["demo_freigaben"] == 1, p["ausgelassen"]
            assert {m["name"] for m in p["mails"]} == {"wart", "katalog"}
            assert k["katalog"].get(url + "?demo=0").json == p

            # Mit demo=1: DEMO-Artikel, die DEMO-Freigabe und der DEMO-Materialwart als Empfänger – gekennzeichnet.
            for c in (k["katalog"], adm):
                assert c.get(url + "?demo=1").status_code == 200
            for c in (k["wart"], k["nutzer"]):
                assert c.get(url + "?demo=1").status_code == 403
            assert k["katalog"].get(url + "?demo=vielleicht").status_code == 400
            p = k["katalog"].get(url + "?demo=1").json
            assert tabellen() == vorher                                         # schreibt nichts
            assert p["demo"] is True and p["ausgelassen"]["demo"] == 0 and p["ausgelassen"]["demo_freigaben"] == 0, p
            assert "@" not in json.dumps(p, ensure_ascii=False)
            namen = {m["name"]: m for m in p["mails"]}
            assert set(namen) == {"wart", "katalog", "demo-wart"}, namen
            w, d, kv = namen["wart"], namen["demo-wart"], namen["katalog"]
            assert w["demo"] is True and w["artikel"] == 2 and w["betreff"].startswith("[DEMO] "), w
            assert w["text"].startswith("DEMO – geht nie hinaus."), w["text"]
            zeile_dm1 = next(z for z in w["text"].splitlines() if "DM-1" in z)
            zeile_dm3 = next(z for z in w["text"].splitlines() if "DM-3" in z)
            assert zeile_dm1.endswith(" · DEMO") and "DEMO" not in zeile_dm3, (zeile_dm1, zeile_dm3)
            assert d["demo"] is True and d["artikel"] == 1 and d["freigaben"] == 1, d
            assert "DM-2" in d["text"] and "extern – lesen bis" in d["text"] and "DEMO OG Beispiel (1)" in d["text"], d
            assert "kein Materialwart" not in d["text"]                         # DEMO-Wart zählt wie ein echter
            assert kv["demo"] is False and "DEMO" not in kv["text"] + kv["betreff"] and "DM-5" in kv["text"], kv

            # Strukturell: Ein Plan mit DEMO geht nie hinaus und wird nie vermerkt.
            e = erinnerung_modul()
            with post() as liste:
                with app.app_context():
                    plan = e.planen(T0, demo=True)
                    assert plan.nur_ansicht and any(m.demo for m in plan.mails)
                    for versuch in (lambda: e.verschicken(plan), lambda: e.vermerken(plan.mails[0])):
                        try:
                            versuch()
                            raise AssertionError("Plan mit DEMO wurde angenommen")
                        except ValueError as exc:
                            assert "nur zur Ansicht" in str(exc)
                    # Auch eine einzelne DEMO-Mail in einem sonst echten Plan hält verschicken an.
                    echt = e.planen(T0)
                    assert not echt.nur_ansicht and not any(m.demo for m in echt.mails)
                    echt.mails.append(next(m for m in plan.mails if m.demo))
                    try:
                        e.verschicken(echt)
                        raise AssertionError("DEMO-Mail wurde angenommen")
                    except ValueError:
                        pass
                    assert e.planen(T0, demo=1).nur_ansicht is False       # nur ein echtes True
                assert liste == []
            assert tabellen() == vorher

            # Kommandozeile: --demo nur mit --trocken; --trocken --demo zeigt dasselbe mit Adressen.
            code, text = cli(app, "--demo")
            assert code == 2 and "--demo nur mit --trocken" in text, text
            with versand(app):
                code, text = cli(app, "--demo", "--erneut")
                assert code == 2, text
            code, text = cli(app, "--trocken")
            assert code == 0 and "DM-2" not in text and "demo-wart@" not in text, text
            assert "Ausgelassen: 2 DEMO-Artikel; 1 DEMO-Freigabe" in text and "remind --trocken --demo" in text, text
            code, text = cli(app, "--trocken", "--demo")
            assert code == 0 and "DEMO-Bestand einbezogen" in text, text
            assert "An: demo-wart <demo-wart@example.invalid>" in text and "[DEMO – geht nie hinaus]" in text, text
            assert "DM-1" in text and "DM-2" in text and "Ausgelassen" not in text, text
            assert tabellen() == vorher

            # Der echte Lauf lässt DEMO weiter aus: keine DEMO-Zeile in Mail, Log und Stand.
            with versand(app), post() as liste:
                erg = lauf(app)
            assert erg["mails"]["mails"] == 2 and erg["mails"]["ausgelassen"]["demo"] == 2, erg
            assert {m[0] for m in liste} == {"wart@example.org", "katalog@example.org"}, [m[0] for m in liste]
            text = "\n".join(m[2] for m in liste)
            assert "DM-1" not in text and "DM-2" not in text and "DEMO" not in text, text
            gemahnt = log(app)
            assert gemahnt and not {r["item_id"] for r in gemahnt} & {dm1["id"], dm2["id"]}, gemahnt
            assert demo_freigabe not in {r["grant_id"] for r in gemahnt}
            assert ref(app, dw_id) is None                                      # kein Kontoverweis für DEMO
    # Oberfläche (statisch): Kästchen nur bei ausgelassenem oder einbezogenem DEMO, kein neuer Knopf; Umschalten lädt
    # neu, öffnet den Dialog aber nicht wieder, wenn er inzwischen geschlossen wurde (Prüfung vom 19.10.2026).
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(wurzel, "app/material/static/material.js"), encoding="utf-8").read()
    anfang = js.index("async function probelaufDialog(")
    block = js[anfang:js.index("\n  }\n", anfang)]
    assert "const demoFeld = p.demo || demoAus.length ?" in block and "DEMO-Bestand einbeziehen (nur Ansicht)" in block
    assert '${demo ? "?demo=1" : ""}' in block and "probelaufDialog(neu, feld)" in block
    assert "if (kaestchen && !(kaestchen.isConnected && $(\"#dlg\").open)) return false;" in block
    assert block.count('class="btn') == 1 and 'class="btn secondary" data-close' in block, block
    print("DEMO im Probelauf bestanden.")


# --- 9. Schalter je Ordner ---------------------------------------------------------------------------------------

def test_ordner_aus():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm, w = k["adm"], k["wart"]
        e = erinnerung_modul()
        regal = ordner_neu(w, lager, "Regal")
        with uhr(um(T0)), versand(app):
            a = artikel(app, w, ids["hms"], regal, "OA-1", faellig=T0 + timedelta(days=20))
            _, ext_id = konto(app, adm, "extern@example.org")
            freigeben(adm, lager, ext_id, "lesen", bis=T0 + timedelta(days=20))
            r = w.put(f"/api/material/ordner/{lager}", json={"reminders_off": True})
            assert r.status_code == 200 and r.json["ordner"]["reminders_off"] is True, r.get_json()
            o = w.get(f"/api/material/ordner/{regal}").json["ordner"]
            assert o["reminders_off"] is False and o["erinnerungen"] == {
                "aus": True, "eigen": False, "geerbt_von": {"id": lager, "pfad": "OG Musterstadt / Lager",
                                                            "sichtbar": True}}, o
            # Wer nur „Regal“ verwaltet, sieht „Lager“ nur als Pfad – ohne Link (sonst 404).
            rw, rw_id = konto(app, adm, "regalwart@example.org")
            freigeben(adm, regal, rw_id, "verwalten")
            o = rw.get(f"/api/material/ordner/{regal}").json["ordner"]
            assert o["erinnerungen"]["geerbt_von"] == {"id": lager, "pfad": "OG Musterstadt / Lager",
                                                       "sichtbar": False}, o
            assert rw.get(f"/api/material/ordner/{lager}").status_code == 404
            sql(app, "DELETE FROM mat_folder_grant WHERE user_id = ?", (rw_id,))     # bekäme sonst unten auch Mails
            o = w.get(f"/api/material/ordner/{lager}").json["ordner"]
            assert o["erinnerungen"] == {"aus": True, "eigen": True, "geerbt_von": None}, o
            journal_e = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'folder' AND entity_id = ? "
                                    "AND action = 'geaendert' ORDER BY id DESC", (lager,))[0]
            assert json.loads(journal_e["before_json"]) == {"reminders_off": 0}
            assert json.loads(journal_e["after_json"]) == {"reminders_off": 1}
            assert journal_e["user_name"] == "wart"
            # Rechte und Eingaben: lesen 403, fremd 404, Systemordner 409, Unsinn 400.
            assert k["fuehrung"].put(f"/api/material/ordner/{lager}", json={"reminders_off": False}).status_code == 403
            gb, _ = gliederung(adm, "OG Nachbarstadt", standard=False)
            wb, wb_id = konto(app, adm, "wart_b@example.org")
            freigeben(adm, gb, wb_id, "verwalten")
            assert wb.put(f"/api/material/ordner/{lager}", json={"reminders_off": False}).status_code == 404
            assert w.put(f"/api/material/ordner/{system['gesperrt']}", json={"reminders_off": True}).status_code == 409
            r = w.put(f"/api/material/ordner/{lager}", json={"reminders_off": "vielleicht"})
            assert r.status_code == 400 and "Erinnerungsmails aus" in r.json["error"], r.get_json()
            # Nichts zum Artikel, die Ablaufmail der Freigabe geht weiter; der Probelauf nennt den Ordner.
            with post() as liste:
                lauf(app)
            assert len(liste) == 1 and "OA-1" not in liste[0][2] and "extern – lesen bis" in liste[0][2], liste
            p = mit(app, e.probelauf)
            assert p["ausgelassen"]["ordner_aus"] == [{"id": regal, "pfad": "OG Musterstadt / Lager / Regal",
                                                       "artikel": 1}], p
            # Wieder an: Am nächsten Tag kommt die höchste offene Stufe.
            assert w.put(f"/api/material/ordner/{lager}", json={"reminders_off": "nein"}).status_code == 200
            tag(13)
            with post() as liste:
                lauf(app)
            assert len(liste) == 1 and "OA-1" in liste[0][2], liste
            assert [(z["item_id"], z["kind"]) for z in log(app) if z["item_id"]] == [(a["id"], "7_tage")]
            # Anlegen mit Schalter.
            r = w.post("/api/material/ordner", json={"name": "Keller", "kind": "standort", "parent_id": gid,
                                                     "reminders_off": True})
            assert r.status_code == 201 and r.json["ordner"]["reminders_off"] is True, r.get_json()
    print("Schalter je Ordner bestanden.")


# --- 10. Ablaufmail für Freigaben --------------------------------------------------------------------------------

def test_freigabe_ablauf():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        pruef_formulare(k["katalog"], ids)
        with uhr(um(T0)), versand(app):
            ext, ext_id = konto(app, adm, "extern@example.org", name="Erika Extern", mat_pruefer=True,
                                urkundennummer="1012-4799")
            v = T0 + timedelta(days=30)
            grant = freigeben(adm, gid, ext_id, "pruefen", bis=v)
            for s in ("FA-1", "FA-2"):
                a = artikel(app, k["wart"], ids["hms"], lager, s)
                r = starten(ext, a["id"])
                assert r.status_code in (200, 201), r.get_json()
            with post() as liste:
                lauf(app)
            assert [m[0] for m in liste] == ["wart@example.org"], liste
            text = liste[0][2]
            assert "Erika Extern – prüfen bis 02.12.2026 (in 30 Tagen) · 2 offene Prüfungen" in text, text
            assert f"Verlängern: {BASIS}/material/ordner/{gid}?freigaben=verlaengern" in text
            assert "1 Freigabe läuft ab" in liste[0][1]
            # Nur Freigaben: Der Schalter am Ordner hält sie nicht an – die Fußzeile verspricht es auch nicht.
            assert "abschalten" not in text and text.rstrip().endswith(
                "Ablaufende Freigaben melden sich immer – auch in Ordnern mit „Erinnerungsmails aus“."), text
            assert [(z["grant_id"], z["kind"], z["due_on"]) for z in log(app)] == [(grant, "freigabe_ablauf", v.isoformat())]
            tag(1)
            with post() as liste:
                lauf(app)
            assert not liste
            # Verlängert auf T + 100: bei T + 70 eine neue Mail.
            sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE id = ?",
                ((T0 + timedelta(days=100)).isoformat(), grant))
            tag(69)
            with post() as liste:
                lauf(app)
            assert not liste
            tag(70)
            with post() as liste:
                lauf(app)
            assert len(liste) == 1 and "(in 30 Tagen)" in liste[0][2], liste
            # Dauerhafte Freigaben laufen nicht ab; die eines deaktivierten Kontos und eine Prüffreigabe ohne
            # Qualifikation wirken nicht – keine Mail.
            tag(71)
            _, dauer_id = konto(app, adm, "dauer@example.org")
            freigeben(adm, gid, dauer_id, "lesen")
            _, deakt_id = konto(app, adm, "deaktiviert@example.org")
            freigeben(adm, gid, deakt_id, "lesen", bis=T0 + timedelta(days=80))
            sql(app, "UPDATE users SET active = 0 WHERE id = ?", (deakt_id,))
            _, ohneq_id = konto(app, adm, "ohnequali@example.org")
            freigeben(adm, gid, ohneq_id, "pruefen", bis=T0 + timedelta(days=80))
            with post() as liste:
                lauf(app)
            assert not liste, liste
            # Ist der Inhaber der einzige Verwalter, geht die Mail an die Material-Verwaltung – nicht an ihn.
            tag(72)
            gx, _ = gliederung(adm, "OG Einzelwart", standard=False)
            _, ew_id = konto(app, adm, "einzel@example.org")
            freigeben(adm, gx, ew_id, "verwalten", bis=T0 + timedelta(days=90))
            with post() as liste:
                lauf(app)
            assert [m[0] for m in liste] == ["katalog@example.org"], liste
            text = liste[0][2]
            # Ein Materialwart ist eingetragen – nur eben der Inhaber selbst: kein „kein Materialwart eingetragen“, kein
            # „Materialwart vergeben“, aber „Verlängern“.
            assert "OG Einzelwart (1) – nur der Inhaber selbst verwaltet hier, darum an die Material-Verwaltung" in text, text
            assert "einzel – verwalten bis" in text and "kein Materialwart" not in text
            assert f"Verlängern: {BASIS}/material/ordner/{gx}?freigaben=verlaengern" in text
            assert "freigaben=materialwart" not in text, text
            assert "Gruppen mit „nur der Inhaber selbst verwaltet hier“ bekommst du, weil du zur Material-Verwaltung " \
                   "gehörst." in " ".join(text.split()), text
            # Befristetes lesen, daran eine dauerhafte Prüffreigabe mit offenem Entwurf: Mit dem lesen endet auch das
            # Prüfen – die Mail nennt den Entwurf. Ein befristetes lesen ohne dauerhaftes Prüfen nennt keine.
            tag(73)
            p_c, p_id = konto(app, adm, "pruef2@example.org", name="Paul Probe", mat_pruefer=True,
                              urkundennummer="1012-4800")
            freigeben(adm, gid, p_id, "lesen", bis=T0 + timedelta(days=93))
            gp = freigeben(adm, gid, p_id, "pruefen")
            sql(app, "UPDATE mat_folder_grant SET valid_until = NULL WHERE id = ?", (gp,))
            a = artikel(app, k["wart"], ids["hms"], lager, "FA-3")
            assert starten(p_c, a["id"]).status_code in (200, 201)
            _, l_id = konto(app, adm, "leser@example.org", name="Lena Leser")
            freigeben(adm, gid, l_id, "lesen", bis=T0 + timedelta(days=95))
            with post() as liste:
                lauf(app)
            text = an(liste, "wart@example.org")[0][2]
            assert "Paul Probe – lesen bis 03.02.2027 (in 20 Tagen) · 1 offene Prüfung\n" in text, text
            assert "Lena Leser – lesen bis 05.02.2027 (in 22 Tagen)\n" in text, text
    print("Ablaufmail für Freigaben bestanden.")


# --- 11. Journal „freigabe_abgelaufen“ ---------------------------------------------------------------------------

def test_freigabe_abgelaufen_journal():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]

        def abgelaufen():
            return zeilen(app, "SELECT * FROM mat_audit WHERE action = 'freigabe_abgelaufen' ORDER BY id")
        with uhr(um(T0)):
            _, ext_id = konto(app, adm, "extern@example.org", name="Erika Extern")
            gestern = T0 - timedelta(days=1)
            grant = freigeben(adm, lager, ext_id, "lesen", bis=gestern)
            r = lauf(app)                                   # Versand aus: der Pflegeteil läuft trotzdem
            assert r["pflege"]["abgelaufen"] == 1 and r["mails"] is None, r
            e1 = abgelaufen()
            assert len(e1) == 1 and e1[0]["entity_id"] == lager and e1[0]["user_name"] == "Tageslauf"
            assert json.loads(e1[0]["after_json"]) == {"freigabe": grant, "konto": {"ref": ref(app, ext_id)},
                                                       "recht": "lesen", "bis": gestern.isoformat()}
            assert e1[0]["before_json"] is None and e1[0]["user_id"] is None
            tag(1)
            assert lauf(app)["pflege"]["abgelaufen"] == 0
            # Verlängert nach dem Ablauf, wieder abgelaufen: ein zweiter Eintrag.
            sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE id = ?", ((T0 + timedelta(days=3)).isoformat(),
                                                                                 grant))
            tag(2)
            assert lauf(app)["pflege"]["abgelaufen"] == 0
            tag(4)
            assert lauf(app)["pflege"]["abgelaufen"] == 1 and len(abgelaufen()) == 2
            # Sichtbarkeit: Verlauf der Freigaben für den Verwalter, nicht im Ordnerjournal der Führungskraft.
            v = k["wart"].get(f"/api/material/ordner/{lager}/freigaben").json["verlauf"]
            ab = [x for x in v if x["aktion"] == "freigabe_abgelaufen"]
            assert len(ab) == 2 and ab[0]["konto"] == "Erika Extern" and ab[0]["wer"] == "Tageslauf", ab
            assert ab[0]["recht"] == "lesen" and ab[0]["bis"] == (T0 + timedelta(days=3)).isoformat()
            j = k["wart"].get(f"/api/material/ordner/{lager}").json["ordner"]["journal"]
            assert any(x["action"] == "freigabe_abgelaufen" for x in j)
            j = k["fuehrung"].get(f"/api/material/ordner/{lager}").json["ordner"]["journal"]
            assert not any(x["action"] == "freigabe_abgelaufen" for x in j), j
            # Gelöscht und mit derselben Kennung neu erteilt (kein AUTOINCREMENT): Bei ihrem Ablauf ein eigener Eintrag.
            sql(app, "DELETE FROM mat_folder_grant WHERE id = ?", (grant,))
            with app.app_context():
                from app import db
                from app.material.services import journal
                neu = db.execute("INSERT INTO mat_folder_grant (id, folder_id, user_id, permission, valid_until, "
                                 "created_at) VALUES (?,?,?,?,?,?)", (grant, lager, ext_id, "lesen",
                                                                      (T0 + timedelta(days=3)).isoformat(), db.now()))
                journal.eintragen("folder", lager, "freigabe_erteilt", None,
                                  {"freigabe": neu, "konto": journal.konto_ref(ext_id), "recht": "lesen",
                                   "bis": (T0 + timedelta(days=3)).isoformat()}, name="Test")
            assert neu == grant
            tag(5)
            assert lauf(app)["pflege"]["abgelaufen"] == 1 and len(abgelaufen()) == 3
    print("Journal freigabe_abgelaufen bestanden.")


# --- 12. Mailtext ------------------------------------------------------------------------------------------------

def test_mailtext():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        w = k["wart"]
        with uhr(um(T0)), versand(app):
            fahrzeug = ordner_neu(w, gid, "Fahrzeug 1", kind="fahrzeug")
            artikel(app, w, ids["hms"], fahrzeug, "MT-1", faellig=T0 + timedelta(days=30), neu=True)
            artikel(app, w, ids["hms"], lager, "MT-2", faellig=T0 - timedelta(days=10))
            artikel(app, w, ids["hms"], lager, "MT-3", faellig=T0 + timedelta(days=5))
            artikel(app, w, ids["gurt"], lager, "MT-4", faellig=T0 + timedelta(days=200), lebensende=T0 + timedelta(days=88))
            artikel(app, w, ids["gurt"], lager, "MT-5", faellig=T0 + timedelta(days=200), lebensende=T0 - timedelta(days=3))
            artikel(app, w, ids["gurt"], lager, "MT-6", faellig=T0 + timedelta(days=6), lebensende=T0 + timedelta(days=60))
            p = planen(app)
            m = {x.adresse: x for x in p.mails}["wart@example.org"]
            assert m.betreff == ("strömis.de – Material: 1 überfällig, 1 Lebensdauer erreicht, 2 in 7 Tagen fällig, "
                                 "1 in 30 Tagen fällig, 2 erreichen bald das Lebensende"), m.betreff
            t = m.text
            assert t.startswith("Hallo wart,\n\nhier steht nur, was seit der letzten Erinnerung neu fällig ist"), t
            assert f"Alles Fällige: {BASIS}/material/pruefungen" in t
            assert t.index("OG Musterstadt / Fahrzeug 1 (1)") < t.index("OG Musterstadt / Lager (5)"), t
            assert "MT-5" in t and "Lebensdauer erreicht seit 30.10.2026 – aussondern" in t, t
            assert "Lebensende am 30.01.2027 (in 89 Tagen)" not in t and "Lebensende am 29.01.2027 (in 88 Tagen)" in t
            assert "fällig am 08.11.2026 (in 6 Tagen) · Lebensende am 01.01.2027 (in 60 Tagen)" in t, t
            assert "überfällig – fällig war der 23.10.2026" in t
            zeilen_lager = t.split("OG Musterstadt / Lager (5)\n")[1].split("\n\n")[0].splitlines()
            assert [z.split("SN ")[1].split()[0] for z in zeilen_lager[:5]] == ["MT-2", "MT-5", "MT-3", "MT-6", "MT-4"], \
                zeilen_lager
            links = [z for z in t.splitlines() if "http" in z]
            assert links and all(f"{BASIS}/material/" in z for z in links), links
            assert t.endswith("Für einen Ordner abschalten: Ordner → Bearbeiten → „Erinnerungsmails aus“.\n"), t
            assert "@" not in t, t
            # Steuerzeichen im Namen der Seite: der Betreff bleibt eine Zeile.
            app.config["SITE_NAME"] = "strömis .de\n"
            p = planen(app)
            betreff = p.mails[0].betreff
            assert "\n" not in betreff and " " not in betreff and betreff.startswith("strömis .de – Material:")
            app.config["SITE_NAME"] = "strömis.de"

            with post():
                lauf(app)                                        # die Artikel oben sind damit gemeldet
            # 120 fällige Artikel in drei Ordnern: 100 Zeilen, jede Gruppe mit Pfad, Zahl und Link, der Rest gezählt –
            # vermerkt werden alle.
            tag(1)
            gross, _ = gliederung(k["adm"], "OG Großlager")
            o = [ordner_neu(k["adm"], gross, n) for n in ("A-Halle", "B-Halle", "C-Halle")]
            for fid, n, v in zip(o, (50, 40, 30), ("A", "B", "C")):
                viele(app, ids["hms"], fid, n, T0 + timedelta(days=4 + ord(v) - 65), f"V{v}")
            zaehler = []

            def gezaehlt():
                with app.app_context():
                    from app import db
                    from app.material import services
                    n = [0]
                    db.get_db().set_trace_callback(lambda _s: n.__setitem__(0, n[0] + 1))
                    p = erinnerung_modul().planen(services.heute())
                    db.get_db().set_trace_callback(None)
                    zaehler.append(n[0])
                    return p
            p = gezaehlt()
            m = {x.adresse: x for x in p.mails}["wart@example.org"]
            t = m.text
            zeilen_a = [z for z in t.splitlines() if z.startswith("  V")]
            assert len(zeilen_a) == 100, len(zeilen_a)
            for name, n in (("A-Halle", 50), ("B-Halle", 40), ("C-Halle", 30)):
                assert f"OG Großlager / {name} ({n})" in t, name
            for fid in o:
                assert f"Ordner: {BASIS}/material/ordner/{fid}" in t
            assert "… und 20 weitere in diesem Ordner" in t and "… und 0 weitere" not in t, t
            assert t.index("OG Großlager / A-Halle") < t.index("OG Großlager / B-Halle") < t.index("OG Großlager / C-Halle")
            # Dringlichkeit: A und B (früher fällig) ganz, C nur zu 10 Zeilen.
            assert len([z for z in zeilen_a if z.startswith("  VC")]) == 10
            viele(app, ids["hms"], o[0], 60, T0 + timedelta(days=4), "VD")
            gezaehlt()
            assert zaehler[1] == zaehler[0] and zaehler[0] < 80, zaehler
            sql(app, "DELETE FROM mat_item WHERE serial_no LIKE 'VD-%'")
            with post():
                lauf(app)
            assert len({z["item_id"] for z in log(app) if z["konto_ref"] == ref(app, k["wart_id"])}) >= 120
            # Artikel und Freigaben in einer Mail: Abschalten gilt nur für die Artikel.
            _, f_id = konto(app, k["adm"], "fuss@example.org", name="Fritz Fuss")
            freigeben(k["adm"], gid, f_id, "lesen", bis=T0 + timedelta(days=20))
            artikel(app, w, ids["hms"], lager, "MT-9", faellig=T0 + timedelta(days=12))
            t = {x.adresse: x for x in planen(app).mails}["wart@example.org"].text
            assert "MT-9" in t and "Fritz Fuss – lesen bis" in t, t
            assert t.endswith("Für einen Ordner abschalten: Ordner → Bearbeiten → „Erinnerungsmails aus“. Ablaufende "
                              "Freigaben melden sich weiter.\n"), t
    print("Mailtext bestanden.")


# --- 13. Schalter und Sperre -------------------------------------------------------------------------------------

def test_schalter_aus():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        e = erinnerung_modul()
        with uhr(um(T0)):
            artikel(app, k["wart"], ids["hms"], lager, "SA-1", faellig=T0 + timedelta(days=5))
            with post() as liste:
                r = lauf(app)
            assert r["pflege"]["tag"] == T0.isoformat() and r["mails"] is None and not liste and not log(app), r
            code, text = cli(app)
            assert code == 2 and "ausgeschaltet (Verwaltung → Einstellungen)" in text, text
            code, text = cli(app, "--stichtag", "2026-11-20")
            assert code == 2 and "Ein echter Lauf gilt immer für heute." in text, text
            code, text = cli(app, "--trocken", "--stichtag", "20.11.2026")
            assert code == 2 and "JJJJ-MM-TT" in text, text

            # --trocken zeigt die Mails mit Adresse – und schreibt nichts (Log, Journal, Meta, Kontoverweise).
            sql(app, "UPDATE users SET mat_ref = NULL WHERE id = ?", (k["wart_id"],))

            def stand():
                return [zeilen(app, f"SELECT * FROM {t} ORDER BY rowid") for t in ("mat_reminder_log", "mat_audit",
                                                                                   "mat_meta")] + \
                    [zeilen(app, "SELECT id, mat_ref FROM users ORDER BY id")]
            vorher = stand()
            code, text = cli(app, "--trocken")
            assert code == 0 and "An: wart <wart@example.org> (1 Artikel, 0 Freigaben)" in text, text
            assert "Probelauf für heute, den 02.11.2026" in text and "SA-1" in text and "ausgeschaltet" in text, text
            code, text = cli(app, "--trocken", "--stichtag", "2026-11-20")
            assert code == 0 and "Probelauf für den 20.11.2026" in text and "überfällig" in text, text
            assert stand() == vorher

            # Sperre aus der Umgebung: Schalter an, Mailserver da – trotzdem keine Mail, kein Log; Pflege und Probelauf
            # laufen, remind endet mit 2. Ein Wert in den Browser-Einstellungen ändert daran nichts.
            tag(1)
            with versand(app), umwelt(MATERIAL_ERINNERUNGEN_SPERRE="1"), post() as liste:
                r = lauf(app)
                assert r["pflege"] and r["mails"] is None and not liste and not log(app), r
                code, text = cli(app)
                assert code == 2 and "in dieser Umgebung gesperrt" in text, text
                assert mit(app, e.probelauf)["mails"] and mit(app, e.stand)["gesperrt"]
            with versand(app), umwelt(MATERIAL_ERINNERUNGEN_SPERRE=None, STROEMIS_NAME="stroemis-dev"):
                assert mit(app, e.gesperrt) and not mit(app, e.versand_an)
                with app.app_context():
                    from app import einstellungen
                    einstellungen.speichern({"MATERIAL_ERINNERUNGEN": True}, k["adm_id"])
                    einstellungen.anwenden()
                    assert app.config["MATERIAL_ERINNERUNGEN"] is True and not e.versand_an()
                    einstellungen.zuruecksetzen("MATERIAL_ERINNERUNGEN")
                    einstellungen.anwenden()                 # der Prozess vergisst den übernommenen Wert …
                    app.config["MATERIAL_ERINNERUNGEN"] = True   # … und setzt den Grundstand – hier wieder an
                with umwelt(MATERIAL_ERINNERUNGEN_SPERRE="0"):
                    assert mit(app, e.versand_an)
                with umwelt(MATERIAL_ERINNERUNGEN_SPERRE="vielleicht"):
                    assert mit(app, e.gesperrt)
            with umwelt(MATERIAL_ERINNERUNGEN_SPERRE="off", STROEMIS_NAME="stroemis-dev"):
                assert not mit(app, e.gesperrt)

            # Echter Lauf über die Kommandozeile: Exit 0, mit Fehlschlag Exit 1.
            with versand(app), post() as liste:
                code, text = cli(app)
            assert code == 0 and len(liste) == 1 and "Mails: 1 verschickt" in text, text
            tag(2)
            artikel(app, k["wart"], ids["hms"], lager, "SA-2", faellig=T0 + timedelta(days=20))
            with versand(app), post(scheitert=("wart@example.org",)):
                code, text = cli(app)
            assert code == 1 and "Gescheitert an: wart" in text, text
            with versand(app, smtp=""):
                code, text = cli(app, "--erneut")
            assert code == 2 and "Kein Mailserver eingerichtet" in text, text
    print("Schalter und Sperre bestanden.")


# --- 14. Aufräumen -----------------------------------------------------------------------------------------------

def test_aufraeumen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        e = erinnerung_modul()
        with uhr(um(T0)):
            a = artikel(app, k["wart"], ids["hms"], lager, "AR-1", faellig=T0 + timedelta(days=5))
            with app.app_context():
                from app.material.services import journal
                wart = journal.konto_ref(k["wart_id"])["ref"]

            def zeile(kind, due, konto, gesendet):
                sql(app, "INSERT INTO mat_reminder_log (item_id, kind, due_on, konto_ref, sent_at) VALUES (?,?,?,?,?)",
                    (a["id"], kind, due, konto, gesendet))
            zeile("30_tage", "2025-09-30", wart, "2025-10-01T04:00:00+00:00")     # 13 Monate und einen Tag
            zeile("7_tage", "2025-11-01", wart, "2025-11-02T04:00:00+00:00")      # 12 Monate
            zeile("faellig", "2026-10-01", "unbekannt", "2026-10-02T04:00:00+00:00")
            sql(app, "INSERT INTO mat_global_search (user_id, user_name, art, anfrage, treffer, item_ids, created_at) "
                     "VALUES (NULL, 'Test', 'suche', 'x', 0, '[]', '2025-01-01T00:00:00+00:00')")
            r = mit(app, e.aufraeumen)
            assert r == {"log": 1, "waisen": 1, "suche": 1}, r
            assert [z["kind"] for z in log(app)] == ["7_tage"]
            # Beim Start: dieselbe Frist, ohne Thread.
            zeile("30_tage", "2025-09-29", wart, "2025-09-30T04:00:00+00:00")
            zeile("faellig", "2026-10-02", "weg", "2026-10-02T04:00:00+00:00")
            app = make_app(tmp)
            assert [z["kind"] for z in log(app)] == ["7_tage"]
            # pflege_veraltet: nach 7 Uhr ohne Pflege heute – auch bei Versand aus.
            Uhr.jetzt = um(T0, 7, 30)
            st = mit(app, e.stand)
            assert st["pflege_veraltet"] and not st["veraltet"] and not st["versand"] and st["pflege"] is None, st
            lauf(app)
            assert not mit(app, e.stand)["pflege_veraltet"]
            tag(1, 6)
            assert not mit(app, e.stand)["pflege_veraltet"]                  # vor 7 Uhr noch nicht
            Uhr.jetzt = um(T0 + timedelta(days=1), 7, 1)
            assert mit(app, e.stand)["pflege_veraltet"]
            # veraltet: Versand an, Mailserver da, nach 7 Uhr, letzter Mailteil gestern.
            with versand(app), post():
                Uhr.jetzt = um(T0 + timedelta(days=1), 6, 10)
                lauf(app)
                Uhr.jetzt = um(T0 + timedelta(days=2), 7, 5)
                assert mit(app, e.stand)["veraltet"]
    print("Aufräumen bestanden.")


# --- 15. Kontolöschen --------------------------------------------------------------------------------------------

def test_kontoloeschen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        with uhr(um(T0)), versand(app):
            w2, w2_id = konto(app, adm, "wart2@example.org")
            freigeben(adm, gid, w2_id, "verwalten")
            a = artikel(app, k["wart"], ids["hms"], lager, "KL-1", faellig=T0 + timedelta(days=5))
            b = artikel(app, k["wart"], ids["hms"], lager, "KL-2", faellig=T0 + timedelta(days=5))
            _, ext_id = konto(app, adm, "extern@example.org")
            grant = freigeben(adm, gid, ext_id, "lesen", bis=T0 + timedelta(days=10))
            with post():
                lauf(app)
            r2, rw = ref(app, w2_id), ref(app, k["wart_id"])
            assert {z["konto_ref"] for z in log(app)} == {r2, rw}
            r = adm.delete(f"/api/admin/users/{w2_id}", headers=H)
            assert r.status_code == 200, r.get_json()
            assert {z["konto_ref"] for z in log(app)} == {rw}
            # Löschen eines Artikels und einer Freigabe nimmt ihre Zeilen mit (Fremdschlüssel).
            sql(app, "DELETE FROM mat_item WHERE id = ?", (a["id"],))
            sql(app, "DELETE FROM mat_folder_grant WHERE id = ?", (grant,))
            assert {(z["item_id"], z["grant_id"]) for z in log(app)} == {(b["id"], None)}
    print("Kontolöschen bestanden.")


# --- 16. Routen --------------------------------------------------------------------------------------------------

def test_routen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        adm = k["adm"]
        url = "/api/material/erinnerungen/probelauf"
        with uhr(um(T0)):
            assert app.test_client().get(url).status_code == 401
            for c, code in ((k["katalog"], 200), (adm, 200), (k["wart"], 403), (k["fuehrung"], 403), (k["nutzer"], 403)):
                assert c.get(url).status_code == code, (c, code)
            artikel(app, k["wart"], ids["hms"], lager, "RT-1", faellig=T0 + timedelta(days=5))
            artikel(app, k["wart"], ids["hms"], lager, "RT-2", faellig=T0 + timedelta(days=31))   # morgen 30_tage
            gc, _ = gliederung(adm, "OG Ohnewart", standard=False)
            artikel(app, adm, ids["hms"], gc, "RT-3", faellig=T0 + timedelta(days=5))
            aus = ordner_neu(k["wart"], gid, "Fahrzeug 1", kind="fahrzeug")
            artikel(app, k["wart"], ids["hms"], aus, "RT-4", faellig=T0 + timedelta(days=5))
            assert k["wart"].put(f"/api/material/ordner/{aus}", json={"reminders_off": True}).status_code == 200

            def tabellen():
                return [zeilen(app, f"SELECT * FROM {t} ORDER BY rowid") for t in ("mat_reminder_log", "mat_audit",
                                                                                   "mat_meta")] + \
                    [zeilen(app, "SELECT id, mat_ref FROM users ORDER BY id")]
            vorher = tabellen()
            p = k["katalog"].get(url).json
            assert tabellen() == vorher
            assert p["stichtag"] == T0.isoformat() and p["morgen"] is False and p["letzter"] is None, p
            assert p["versand"] is False and p["gesperrt"] is False and p["smtp"] is False
            namen = {m["name"]: m for m in p["mails"]}
            assert set(namen) == {"wart", "katalog"}, namen
            assert namen["wart"]["artikel"] == 1 and "RT-1" in namen["wart"]["text"] and namen["wart"]["gliederung"] == ""
            assert "kein Materialwart eingetragen" in namen["katalog"]["text"]
            assert p["ausgelassen"] == {"ordner_aus": [{"id": aus, "pfad": "OG Musterstadt / Fahrzeug 1", "artikel": 1}],
                                        "demo": 0, "demo_freigaben": 0}, p["ausgelassen"]
            assert p["demo"] is False
            assert "@" not in json.dumps(p, ensure_ascii=False)
            # Nach dem Mailteil: der Probelauf zeigt morgen – mit dem heutigen Log und der Zeile zum letzten Lauf.
            with versand(app), post():
                lauf(app)
                assert k["katalog"].get(url).json["smtp"] is True
            p = k["katalog"].get(url).json
            assert p["stichtag"] == (T0 + timedelta(days=1)).isoformat() and p["morgen"] is True, p
            assert p["letzter"]["mails"] == 2 and p["letzter"]["fehlgeschlagen"] == 0, p["letzter"]
            assert [m["name"] for m in p["mails"]] == ["wart"] and "RT-2" in p["mails"][0]["text"], p["mails"]
            assert "RT-1" not in p["mails"][0]["text"]
            # Ohne Empfänger (keine Material-Verwaltung, Plattform-Verwaltung ohne Namen): Ordner mit Zahl.
            artikel(app, adm, ids["hms"], gc, "RT-5", faellig=T0 + timedelta(days=12))
            sql(app, "UPDATE users SET recht_material = 1 WHERE id = ?", (k["katalog_id"],))
            sql(app, "UPDATE users SET name = '' WHERE id = ?", (k["adm_id"],))
            p = mit(app, erinnerung_modul().probelauf)
            sql(app, "UPDATE users SET name = 'Administrator' WHERE id = ?", (k["adm_id"],))
            sql(app, "UPDATE users SET recht_material = 2 WHERE id = ?", (k["katalog_id"],))
            assert p["ohne_empfaenger"] == [{"ordner": "OG Ohnewart", "artikel": 2, "freigaben": 0}], p["ohne_empfaenger"]
            # /start: der Laufstand nur für Material- und Plattform-Verwaltung.
            assert k["katalog"].get("/api/material/start").json["erinnerungen"]["letzter"]["mails"] == 2
            assert adm.get("/api/material/start").json["erinnerungen"]["startzeit"] == "06:00"
            for c in (k["wart"], k["fuehrung"]):
                assert c.get("/api/material/start").json["erinnerungen"] is None
            o = k["wart"].get(f"/api/material/ordner/{lager}").json["ordner"]
            assert o["erinnerungen"] == {"aus": False, "eigen": False, "geerbt_von": None} and o["reminders_off"] is False
    print("Routen bestanden.")


# --- 17. Thread --------------------------------------------------------------------------------------------------

def test_thread_start():
    import logging
    with tempfile.TemporaryDirectory() as tmp:
        app, k, ids, gid, system, lager = aufbau(tmp)
        from app.material import tageslauf
        alt = (tageslauf.threading, tageslauf._gestartet, tageslauf._einmal, tageslauf._schlafen)
        try:
            # Mit TESTING startet nichts.
            tageslauf._gestartet = False
            assert k["fuehrung"].get("/api/material/start").status_code == 200 and not tageslauf._gestartet

            # Thread.start wirft: die Anfrage gelingt, einmal geloggt, die nächste Anfrage versucht es nicht noch einmal.
            versuche, meldungen = [], []

            class Kaputt:
                def __init__(self, *a, **kw):
                    versuche.append(kw)

                def start(self):
                    raise RuntimeError("can't start new thread")

            class Fang(logging.Handler):
                def emit(self, record):
                    meldungen.append(record.getMessage())
            fang = Fang()
            app.logger.addHandler(fang)
            tageslauf.threading = types.SimpleNamespace(Thread=Kaputt)
            app.config["TESTING"] = False
            try:
                for _ in range(2):
                    assert k["fuehrung"].get("/api/material/start").status_code == 200
            finally:
                app.config["TESTING"] = True
                app.logger.removeHandler(fang)
            assert len(versuche) == 1 and tageslauf._gestartet
            assert len([m for m in meldungen if "Thread nicht gestartet" in m]) == 1, meldungen

            # Parallele erste Anfragen: genau ein Thread.
            gestartet = []

            class Zaehler:
                def __init__(self, *a, **kw):
                    self.kw = kw

                def start(self):
                    gestartet.append(self.kw["name"])
            tageslauf.threading = types.SimpleNamespace(Thread=Zaehler)
            tageslauf._gestartet = False
            app.config["TESTING"] = False
            schranke = threading.Barrier(8)

            def anfrage():
                with app.test_request_context("/api/material/start"):
                    schranke.wait()
                    tageslauf.anstossen()
            try:
                faeden = [threading.Thread(target=anfrage) for _ in range(8)]
                for f in faeden:
                    f.start()
                for f in faeden:
                    f.join()
            finally:
                app.config["TESTING"] = True
            assert gestartet == ["tageslauf"], gestartet

            # Eine Runde wirft: Die Schleife läuft weiter (Runde und Schlaf ersetzt, angehalten über BaseException).
            class Halt(BaseException):
                pass
            runden, schlaefe = [], []

            def runde(_app):
                runden.append(1)
                if len(runden) == 1:
                    raise RuntimeError("Testfehler in der Runde")

            def schlafen(s):
                schlaefe.append(s)
                if len(schlaefe) > 3:
                    raise Halt()
            tageslauf._einmal, tageslauf._schlafen = runde, schlafen
            try:
                tageslauf._schleife(app)
                raise AssertionError("Schleife endete")
            except Halt:
                pass
            assert len(runden) == 3 and 60 <= schlaefe[0] <= 180 and schlaefe[1:] == [tageslauf.WACH_SEKUNDEN] * 3
            tageslauf._einmal = alt[2]

            # _einmal wendet eine eben im Browser gespeicherte Einstellung an.
            e = erinnerung_modul()
            gesehen = []
            alt_versuch = e.tageslauf_versuchen
            e.tageslauf_versuchen = lambda: gesehen.append(bool(__import__("flask").current_app.config.get(
                "MATERIAL_ERINNERUNGEN")))
            app.config["MATERIAL_ERINNERUNGEN"] = False
            try:
                with app.app_context():
                    from app import einstellungen
                    einstellungen.speichern({"MATERIAL_ERINNERUNGEN": "true"}, k["adm_id"])
                tageslauf._einmal(app)
                assert gesehen == [True], gesehen
                with app.app_context():
                    einstellungen.zuruecksetzen("MATERIAL_ERINNERUNGEN")
                    einstellungen.anwenden()
            finally:
                e.tageslauf_versuchen = alt_versuch
                app.config["MATERIAL_ERINNERUNGEN"] = False
        finally:
            tageslauf.threading, tageslauf._gestartet, tageslauf._einmal, tageslauf._schlafen = alt
    print("Thread bestanden.")


# --- 18. Einstellung ---------------------------------------------------------------------------------------------

def test_einstellung():
    with tempfile.TemporaryDirectory() as tmp:
        with umwelt(MATERIAL_ERINNERUNGEN=None):
            app = make_app(tmp)
            with app.app_context():
                from app import einstellungen
                feld = next(f for f in einstellungen.als_json()["felder"] if f["schluessel"] == "MATERIAL_ERINNERUNGEN")
            assert feld["gruppe"] == "Material" and feld["art"] == "schalter" and feld["wert"] == "false", feld
            assert feld["titel"] == "Erinnerungsmails verschicken" and "ab 6 Uhr" in feld["hilfe"]
            assert app.config["MATERIAL_ERINNERUNGEN"] is False
    print("Einstellung bestanden.")


# --- Stand-7-Kopie (nur von Hand, wenn eine Kopie da ist) ----------------------------------------------------------

def migration_aus_kopie(quelle):
    """Eine KOPIE einer Datenbank auf Stand 7 durch alle Schritte bis 11 – von Hand:
    python tests/test_material_erinnerung.py --kopie /pfad/zur/kopie.db (die Quelle bleibt unberührt)."""
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(quelle, os.path.join(tmp, "stroemis.db"))
        app = make_app(tmp)
        assert zeilen(app, "SELECT wert FROM mat_meta WHERE schluessel = 'schema_version'")[0]["wert"] == endversion()
        assert erinnerungslog_wie_schritt_11(app)
        print("Kopie migriert:", zeilen(app, "SELECT COUNT(*) AS n FROM mat_folder")[0]["n"], "Ordner,",
              zeilen(app, "SELECT COUNT(*) AS n FROM mat_folder_grant")[0]["n"], "Freigaben,",
              zeilen(app, "SELECT COUNT(*) AS n FROM mat_reminder_log")[0]["n"], "Log-Zeilen")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--kopie":
        migration_aus_kopie(sys.argv[2])
        sys.exit(0)
    test_migration_11()
    test_stufen()
    test_nachholen()
    test_doppellaeufe()
    test_zeitzone()
    test_rechteschnitt()
    test_gescheitert()
    test_demo()
    test_demo_probelauf()
    test_ordner_aus()
    test_freigabe_ablauf()
    test_freigabe_abgelaufen_journal()
    test_mailtext()
    test_schalter_aus()
    test_aufraeumen()
    test_kontoloeschen()
    test_routen()
    test_thread_start()
    test_einstellung()
    print("Alle Erinnerungstests bestanden.")
