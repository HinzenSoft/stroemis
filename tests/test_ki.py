"""Gemeinsamer Baustein für Läufe über die Claude API (app/ki.py, 21.11.2026):  python tests/test_ki.py  oder  pytest …

Keine echten API-Aufrufe: Der Client ist eine Attrappe (beta.messages.stream mit Ereignissen und get_final_message,
Antworten als echte SDK-Typen über BetaMessage.model_validate), für Parameter und Fehlerkette zusätzlich der echte
SDK-Client gegen einen MockTransport von httpx2 – so ist auch geprüft, dass das SDK die Parameter annimmt und den
Verlauf (Inhalt der Antworten unverändert) serialisiert. Geprüft: Tabelle ki_laeufe (CHECKs, „einer je Art“), Schlüssel,
Kosten, Kontingent je Kalendermonat deutscher Zeit, Gesprächsschleife (pause_turn ≤ 5, eigene Werkzeuge mit is_error in
einer Nutzernachricht, refusal mit Kategorie, max_tokens, Nachfrage, unlesbares JSON, dasselbe Werkzeug zweimal
gescheitert), Ausweichmodell, Abbruch (im selben Prozess, über das Kennzeichen, mitten in einem hängenden Stream,
Zeitgrenze – auch mit dem echten SDK-Client gegen einen lokalen, schweigenden SSE-Server), Zwischenstand der Kosten
eines abgebrochenen Streams („mindestens“), größter Abstand der Stream-Ereignisse im Protokoll (samt ping), tote Läufe
(mit Nacharbeit des Moduls), gleichzeitige Starts, Fehlerkette ohne Schlüssel im Text, Kontolöschung, Leeren. Alle
Angaben hier sind Platzhalter."""
import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_material import H, make_app  # noqa: E402

SCHLUESSEL = "sk-ant-test-0000-geheim-nie-zeigen"


# --- Attrappe des Clients ------------------------------------------------------------------------------------------

def nachricht(inhalt, stop="end_turn", modell="claude-opus-5-5", usage=None, **extra):
    """Eine Antwort als dict in der Form der API (wird zu BetaMessage)."""
    return dict({"id": "msg_test", "type": "message", "role": "assistant", "model": modell, "content": inhalt,
                 "stop_reason": stop, "stop_sequence": None,
                 "usage": usage or {"input_tokens": 1000, "output_tokens": 200}}, **extra)


def text(t):
    return {"type": "text", "text": t}


def werkzeug(name, eingabe, kennung="toolu_1"):
    return {"type": "tool_use", "id": kennung, "name": name, "input": eingabe}


class _Strom:
    """Was beta.messages.stream liefert: Kontextmanager, iterierbar (Ereignisse), get_final_message(), close().
    haengen: die Iteration blockiert ohne Ereignis, bis jemand close() ruft – wie ein Stream, der auf Server-Werkzeuge
    wartet; danach eine Ausnahme wie beim abgerissenen Lesen. fehler: eine Ausnahme statt der Antwort. teil: der
    Zwischenstand (current_message_snapshot) wie beim SDK nach message_start – ohne teil wirft er wie dort."""

    def __init__(self, antwort, ereignisse=3, haengen=False, fehler=None, teil=None):
        self.antwort, self.ereignisse, self.haengen, self.fehler = antwort, ereignisse, haengen, fehler
        self.teil = teil
        self.geschlossen = threading.Event()

    @property
    def current_message_snapshot(self):
        assert self.teil is not None
        from anthropic.types.beta import BetaMessage
        return BetaMessage.model_validate(self.teil)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        self.geschlossen.set()

    def __iter__(self):
        for i in range(self.ereignisse):
            yield SimpleNamespace(type="content_block_delta", index=i)
        if self.haengen:
            self.geschlossen.wait(30)
            raise RuntimeError("Verbindung geschlossen")
        if self.fehler is not None:
            raise self.fehler

    def get_final_message(self):
        from anthropic.types.beta import BetaMessage
        return BetaMessage.model_validate(self.antwort)


class Attrappe:
    """Client-Ersatz für ki.CLIENT. antworten: Liste (der Reihe nach) oder Funktion(anfrage, nr) – je Eintrag ein dict
    (Antwort), ein _Strom oder eine Ausnahme (wird beim Iterieren geworfen). anfragen hält jede Anfrage fest, mit einer
    Kopie der Nachrichtenliste zum Zeitpunkt des Aufrufs."""

    def __init__(self, antworten):
        self.antworten = antworten
        self.anfragen = []
        self.stroeme = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **anfrage):
        self.anfragen.append(dict(anfrage, messages=list(anfrage["messages"])))
        nr = len(self.anfragen) - 1
        a = self.antworten(anfrage, nr) if callable(self.antworten) else self.antworten[nr]
        if isinstance(a, _Strom):
            s = a
        elif isinstance(a, BaseException):
            s = _Strom(None, fehler=a)
        else:
            s = _Strom(a)
        self.stroeme.append(s)
        return s


def einsetzen(attrappe):
    from app import ki
    alt = ki.CLIENT
    ki.CLIENT = lambda: attrappe
    return alt


# --- Umgebung -------------------------------------------------------------------------------------------------------

def app_mit_schluessel(tmp, schluessel=SCHLUESSEL):
    if schluessel:
        os.environ["ANTHROPIC_API_KEY"] = schluessel
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT", None)
    return make_app(tmp)


def im_kontext(app):
    """Ein Anfragekontext mit dem Administrator als Konto (wie eine Anfrage der Verwaltung)."""
    from flask import g
    ctx = app.test_request_context()
    ctx.push()
    from app import db
    g.user = db.query("SELECT * FROM users ORDER BY id LIMIT 1", one=True)
    return ctx


def lauf_starten(arbeit, eingabe=None, beendet=None, art="mat_recherche", bezug="mat_meldung:1"):
    from app import ki
    z = ki.starten(art, bezug, eingabe or {"probe": 1}, arbeit, effort="high", beendet=beendet, mit_ordner=True)
    assert ki.warten(z["id"], 30), "Der Lauf ist nicht fertig geworden."
    return ki.zeile(z["id"])


def gespraech_arbeit(anfrage, werkzeuge=None, nachfrage=None, runden=20):
    def arbeit(lauf):
        msg = lauf.gespraech(anfrage, werkzeuge, runden=runden, nachfrage=nachfrage)
        return {"stop": msg.stop_reason}
    return arbeit


def anfrage(**extra):
    return dict({"model": "claude-opus-5-5", "max_tokens": 1000, "messages": [{"role": "user", "content": "Probe"}]},
                **extra)


# --- Tests ----------------------------------------------------------------------------------------------------------

def test_tabelle():
    """ki_laeufe im Kernschema: ohne CHECK auf die Art (nur nicht leer), beendet_am passend zum Status, höchstens ein
    laufender Lauf je Art; ein zweiter Start der App ändert nichts."""
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        db_pfad = app.config["DB_PATH"]
        conn = sqlite3.connect(db_pfad)
        schema = conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name = 'ki_laeufe' ORDER BY name").fetchall()
        assert schema, "ki_laeufe fehlt"
        jetzt = "2026-11-21T10:00:00+00:00"
        ein = "INSERT INTO ki_laeufe (art, status, gestartet_am, beendet_am) VALUES (?,?,?,?)"
        conn.execute(ein, ("wiki_entwurf", "fertig", jetzt, jetzt))          # eine künftige Art braucht keinen Umbau
        for falsch in (("", "fertig", jetzt, jetzt), ("x", "fertig", jetzt, None), ("x", "laeuft", jetzt, jetzt),
                       ("x", "unbekannt", jetzt, jetzt)):
            try:
                conn.execute(ein, falsch)
                raise AssertionError(f"angenommen: {falsch}")
            except sqlite3.IntegrityError:
                pass
        conn.execute(ein, ("mat_recherche", "laeuft", jetzt, None))
        conn.execute(ein, ("wiki_entwurf", "wartet", jetzt, None))           # andere Art darf gleichzeitig
        try:
            conn.execute(ein, ("mat_recherche", "wartet", jetzt, None))
            raise AssertionError("zwei laufende Läufe derselben Art angenommen")
        except sqlite3.IntegrityError:
            pass
        conn.commit()
        conn.close()
        make_app(tmp)                                                        # zweiter Start
        conn = sqlite3.connect(db_pfad)
        assert conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name = 'ki_laeufe' ORDER BY name").fetchall() \
            == schema
        assert conn.execute("SELECT COUNT(*) FROM ki_laeufe").fetchone()[0] == 3
        conn.close()
    print("ki_laeufe: Schema, CHECKs, einer je Art, zweiter Start bestanden.")


def test_schluessel_und_kosten():
    from app import ki
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp, schluessel=None)
        assert not ki.verfuegbar()
        ctx = im_kontext(app)
        try:
            aufgerufen = []
            alt = ki.CLIENT
            ki.CLIENT = lambda: aufgerufen.append(1)
            try:
                ki.starten("mat_recherche", "mat_meldung:1", {}, lambda lauf: {})
                raise AssertionError("ohne Schlüssel gestartet")
            except ki.KiFehler as exc:
                assert exc.code == 503 and "API-Schlüssel" in str(exc), exc
            finally:
                ki.CLIENT = alt
            assert not aufgerufen
            from app import db
            assert db.query("SELECT COUNT(*) AS n FROM ki_laeufe", one=True)["n"] == 0
            os.environ["ANTHROPIC_API_KEY"] = "   "
            assert not ki.verfuegbar()
            os.environ["ANTHROPIC_API_KEY"] = SCHLUESSEL
            assert ki.verfuegbar()
        finally:
            ctx.pop()
    # Kosten: Opus 5.5 – 4 $/20 $ je Mio., Cache lesen 0,20 $, schreiben 1,25 × Eingabe, Suche 1 Cent.
    assert ki.kosten_cent([{"eingabe": 1_000_000}]) == 400
    assert ki.kosten_cent([{"ausgabe": 100_000}, {"cache_lesen": 1_000_000}, {"cache_schreiben": 1_000_000},
                           {"websuche": 3}]) == 200 + 20 + 500 + 3
    assert ki.kosten_cent([]) == 0 and ki.kosten_text(180) == "ca. 1,80 $" and ki.kosten_text(5) == "ca. 0,05 $"
    assert ki.kosten_text(None) == ""
    from anthropic.types.beta import BetaMessage
    m = BetaMessage.model_validate(nachricht([text("x")], usage={
        "input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 3,
        "server_tool_use": {"web_search_requests": 2, "web_fetch_requests": 4}}))
    assert ki.verbrauch(m) == {"modell": "claude-opus-5-5", "eingabe": 10, "ausgabe": 5, "cache_lesen": 7,
                               "cache_schreiben": 3, "websuche": 2, "abrufe": 4, "ausweichen": False}
    # Mit Ausweichmodell: oben nur der Durchgang, der geantwortet hat – gezählt wird je Durchgang (usage.iterations).
    m = BetaMessage.model_validate(nachricht([text("x")], modell="claude-opus-4-8", usage={
        "input_tokens": 50, "output_tokens": 30, "iterations": [
            {"type": "message", "input_tokens": 100, "output_tokens": 0, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0},
            {"type": "fallback_message", "model": "claude-opus-4-8", "input_tokens": 50, "output_tokens": 30,
             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}]}))
    v = ki.verbrauch(m)
    assert v["eingabe"] == 150 and v["ausgabe"] == 30 and v["ausweichen"], v
    assert ki.ausweichmodell([v]) == "claude-opus-4-8" and ki.ausweichmodell([{"modell": ki.MODELL}]) is None
    print("Schlüssel und Kosten bestanden.")


def test_kontingent():
    """Je Kalendermonat in deutscher Zeit; jeder Start zählt (auch gescheiterte, auch ohne Bezug); Grenze aus der
    Umgebung, sonst 20."""
    from app import db, ki
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        with app.app_context():
            ein = ("INSERT INTO ki_laeufe (art, bezug, status, gestartet_am, beendet_am, eingabe_json) "
                   "VALUES ('mat_recherche', ?, ?, ?, ?, ?)")
            # 31.10. 23:00 UTC = 1.11. 0:00 deutscher Zeit (MEZ) – zählt für November; eine Sekunde davor für Oktober.
            for zeit, status in (("2026-10-31T22:59:59+00:00", "fertig"), ("2026-10-31T23:00:00+00:00", "abgebrochen"),
                                 ("2026-11-15T09:00:00+00:00", "fehlgeschlagen"),
                                 ("2026-11-30T22:59:59+00:00", "fertig"), ("2026-11-30T23:00:00+00:00", "fertig")):
                db.execute(ein, ("mat_meldung:1", status, zeit, zeit, "{}"))
            db.execute("INSERT INTO ki_laeufe (art, status, gestartet_am, beendet_am) VALUES "
                       "('wiki_entwurf', 'fertig', '2026-11-10T09:00:00+00:00', '2026-11-10T09:00:00+00:00')")
            nov = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
            k = ki.kontingent("mat_recherche", nov)
            assert k == {"grenze": 20, "verbraucht": 3, "rest": 17, "monat": "November"}, k
            assert ki.kontingent("mat_recherche", datetime(2026, 10, 31, 22, 0, tzinfo=timezone.utc))["verbraucht"] == 1
            dez = ki.kontingent("mat_recherche", datetime(2026, 11, 30, 23, 30, tzinfo=timezone.utc))
            assert dez["monat"] == "Dezember" and dez["verbraucht"] == 1, dez
            os.environ["MATERIAL_RECHERCHE_JE_MONAT"] = "3"
            assert ki.kontingent("mat_recherche", nov)["rest"] == 0
            os.environ["MATERIAL_RECHERCHE_JE_MONAT"] = "viele"
            assert ki.kontingent("mat_recherche", nov)["grenze"] == 20
            os.environ["MATERIAL_RECHERCHE_JE_MONAT"] = "0"
            assert ki.kontingent("mat_recherche", nov)["rest"] == 0
            os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT")
        # Erschöpft: Start mit 429, kein neuer Lauf.
        os.environ["MATERIAL_RECHERCHE_JE_MONAT"] = "1"
        ctx = im_kontext(app)
        try:
            vorher = db.query("SELECT COUNT(*) AS n FROM ki_laeufe", one=True)["n"]
            db.execute("INSERT INTO ki_laeufe (art, status, gestartet_am, beendet_am) VALUES "
                       "('mat_recherche', 'fertig', ?, ?)", (db.now(), db.now()))
            try:
                ki.starten("mat_recherche", "mat_meldung:2", {}, lambda lauf: {})
                raise AssertionError("trotz Kontingent gestartet")
            except ki.KiFehler as exc:
                assert exc.code == 429 and "aufgebraucht (" in str(exc) and "von 1)." in str(exc), exc
            assert db.query("SELECT COUNT(*) AS n FROM ki_laeufe", one=True)["n"] == vorher + 1
        finally:
            ctx.pop()
            os.environ.pop("MATERIAL_RECHERCHE_JE_MONAT")
    print("Kontingent je Kalendermonat bestanden.")


def test_gespraech():
    """pause_turn (Inhalt unverändert zurück), eigene Werkzeuge (alle Ergebnisse in einer Nachricht, Fehler als
    is_error, Ende mit ende=True), Grenzen und Endgründe."""
    from app import ki
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        ctx = im_kontext(app)
        try:
            denken = {"type": "thinking", "thinking": "", "signature": "sig-1"}
            suche = {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "q"}}
            suche_fehler = {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1",
                            "content": {"type": "web_search_tool_result_error", "error_code": "unavailable"}}
            a = Attrappe([
                nachricht([denken, suche, suche_fehler], stop="pause_turn"),
                nachricht([text("weiter")], stop="pause_turn"),
                nachricht([werkzeug("eins", {"x": 1}, "toolu_a"), werkzeug("kaputt", {}, "toolu_b"),
                           werkzeug("fremd", {}, "toolu_c")], stop="tool_use",
                          usage={"input_tokens": 10, "output_tokens": 1,
                                 "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0}}),
                nachricht([werkzeug("eins", {"x": 2}, "toolu_d")], stop="tool_use"),
            ])
            alt = einsetzen(a)
            gesehen = []

            def eins(e):
                gesehen.append(e)
                return ki.Antwort("fertig", ende=True) if e["x"] == 2 else ki.Antwort("ok")

            def kaputt(e):
                raise KeyError("x")

            try:
                z = lauf_starten(gespraech_arbeit(anfrage(), {"eins": eins, "kaputt": kaputt}))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig", dict(z)
            assert gesehen == [{"x": 1}, {"x": 2}]
            # Nach pause_turn: dieselbe Antwort unverändert als letzte Nachricht, keine Nutzernachricht dazwischen.
            m1 = a.anfragen[1]["messages"]
            assert len(m1) == 2 and m1[1]["role"] == "assistant"
            assert [b.type for b in m1[1]["content"]] == ["thinking", "server_tool_use", "web_search_tool_result"]
            assert m1[1]["content"][0].signature == "sig-1"
            # Werkzeuge: alle drei Ergebnisse in EINER Nutzernachricht, Fehler mit is_error.
            erg = a.anfragen[3]["messages"][-1]
            assert erg["role"] == "user" and [r["tool_use_id"] for r in erg["content"]] == ["toolu_a", "toolu_b",
                                                                                             "toolu_c"], erg
            assert "is_error" not in erg["content"][0] and erg["content"][1]["is_error"] \
                and erg["content"][2]["is_error"] and "Unbekanntes Werkzeug" in erg["content"][2]["content"], erg
            usage = json.loads(z["usage_json"])
            assert len(usage) == 4 and z["kosten_cent"] == ki.kosten_cent(usage) and usage[2]["websuche"] == 1

            # Mehr als PAUSEN_MAX Fortsetzungen → gescheitert.
            a = Attrappe([nachricht([text("p")], stop="pause_turn")] * 7)
            alt = einsetzen(a)
            try:
                z = lauf_starten(gespraech_arbeit(anfrage()))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fehlgeschlagen" and "pause_turn" in z["fehler"] and len(a.anfragen) == 6, dict(z)

            # refusal: mit Kategorie und ohne; max_tokens.
            for antwort, teil in ((nachricht([], stop="refusal", stop_details={"type": "refusal", "category": "cyber"}),
                                   "Kategorie: cyber"),
                                  (nachricht([], stop="refusal"), "ohne Angabe"),
                                  (nachricht([text("abgeschnitten")], stop="max_tokens"), "zu lang und ist abgeschnitten")):
                a = Attrappe([antwort])
                alt = einsetzen(a)
                try:
                    z = lauf_starten(gespraech_arbeit(anfrage()))
                finally:
                    ki.CLIENT = alt
                assert z["status"] == "fehlgeschlagen" and teil in z["fehler"], (teil, dict(z))
                assert z["kosten_cent"] is not None and json.loads(z["usage_json"]), "Verbrauch fehlt"

            # Ausweichmodell nach einer Ablehnung: Antwort des anderen Modells, Fallback-Block bleibt im Verlauf.
            a = Attrappe([nachricht([{"type": "fallback", "from": {"model": "claude-opus-5-5"},
                                      "to": {"model": "claude-opus-4-8"},
                                      "trigger": {"type": "refusal", "category": "cyber"}}, text("ok")],
                                    modell="claude-opus-4-8",
                                    usage={"input_tokens": 5, "output_tokens": 5, "iterations": [
                                        {"type": "fallback_message", "model": "claude-opus-4-8", "input_tokens": 5,
                                         "output_tokens": 5, "cache_creation_input_tokens": 0,
                                         "cache_read_input_tokens": 0}]})])
            alt = einsetzen(a)
            try:
                z = lauf_starten(gespraech_arbeit(anfrage()))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig" and ki.ausweichmodell(json.loads(z["usage_json"])) == "claude-opus-4-8"

            # Ausweichen mitten in der Ausgabe: Was das ablehnende Modell vor dem fallback-Block schrieb (Denken,
            # Werkzeugaufruf, Server-Aufruf ohne Ergebnis), geht nicht zurück und wird nicht ausgeführt.
            fb = {"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-4-8"},
                  "trigger": {"type": "refusal", "category": "cyber"}}
            a = Attrappe([
                nachricht([{"type": "thinking", "thinking": "", "signature": "alt"}, text("Teil davor"),
                           werkzeug("eins", {"x": 9}, "toolu_alt"),
                           {"type": "server_tool_use", "id": "srvtoolu_x", "name": "web_search", "input": {"query": "q"}},
                           fb, text("weiter"), werkzeug("eins", {"x": 2}, "toolu_neu")], stop="tool_use",
                          modell="claude-opus-4-8"),
                nachricht([text("fertig")])])
            alt = einsetzen(a)
            gesehen.clear()
            try:
                z = lauf_starten(gespraech_arbeit(anfrage(), {"eins": lambda e: gesehen.append(e) or ki.Antwort("ok")}))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig" and gesehen == [{"x": 2}], (dict(z), gesehen)
            zurueck = a.anfragen[1]["messages"][1]["content"]
            assert [b.type for b in zurueck] == ["text", "fallback", "text", "tool_use"] and zurueck[3].id == "toolu_neu"
            assert [r["tool_use_id"] for r in a.anfragen[1]["messages"][2]["content"]] == ["toolu_neu"]

            # Nachfrage: einmal, wenn Claude ohne Ergebnis aufhört – dann ist Schluss.
            a = Attrappe([nachricht([text("fertig ohne Werkzeug")])] * 3)
            alt = einsetzen(a)
            try:
                z = lauf_starten(gespraech_arbeit(anfrage(), nachfrage="Bitte abgeben."))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig" and len(a.anfragen) == 2
            assert a.anfragen[1]["messages"][-1] == {"role": "user", "content": "Bitte abgeben."}

            # JSON eines Werkzeugs, das das SDK nicht lesen kann (ValueError aus dem Stream): höchstens zweimal neu.
            for fehlversuche, status in ((2, "fertig"), (3, "fehlgeschlagen")):
                a = Attrappe([ValueError("kaputtes JSON")] * fehlversuche + [nachricht([text("ok")])])
                alt = einsetzen(a)
                try:
                    z = lauf_starten(gespraech_arbeit(anfrage()))
                finally:
                    ki.CLIENT = alt
                assert z["status"] == status, (fehlversuche, dict(z))
            # Dasselbe eigene Werkzeug scheitert zweimal (bzw. Claude ruft zweimal ein unbekanntes): Schluss, statt bis
            # zur Rundengrenze bezahlte Runden zu drehen.
            for name in ("kaputt", "gibtsnicht"):
                a = Attrappe([nachricht([werkzeug(name, {}, f"toolu_{i}")], stop="tool_use") for i in range(5)])
                alt = einsetzen(a)
                try:
                    z = lauf_starten(gespraech_arbeit(anfrage(), {"kaputt": kaputt}))
                finally:
                    ki.CLIENT = alt
                assert z["status"] == "fehlgeschlagen" and "2-mal gescheitert" in z["fehler"] \
                    and len(a.anfragen) == 2, (name, dict(z), len(a.anfragen))
            # Grenze der Runden.
            a = Attrappe([nachricht([werkzeug("eins", {"x": 1})], stop="tool_use")] * 5)
            alt = einsetzen(a)
            try:
                z = lauf_starten(gespraech_arbeit(anfrage(), {"eins": lambda e: ki.Antwort("ok")}, runden=3))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fehlgeschlagen" and "Runden" in z["fehler"], dict(z)
        finally:
            ctx.pop()
    print("Gesprächsschleife bestanden.")


def test_abbruch_und_tote():
    """Abbrechen mitten in einem hängenden Stream (im selben Prozess sofort, über das Kennzeichen mit dem Puls), die
    Zeitgrenze, „Erledigt“ von außen, tote Läufe ohne Lebenszeichen, gleichzeitige Starts."""
    from app import db, ki
    alt_puls, alt_grenze = ki.PULS_SEK, ki.ARTEN["mat_recherche"]["gesamt_sek"]
    ki.PULS_SEK = 0.05
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        ctx = im_kontext(app)
        try:
            def hoerer(ende):
                def beendet(lauf, status):
                    ende.append(status)
                return beendet

            for weg in ("selber_prozess", "kennzeichen"):
                strom = _Strom(nachricht([text("nie")]), haengen=True)
                a = Attrappe([strom])
                alt = einsetzen(a)
                ende = []
                try:
                    z = ki.starten("mat_recherche", "mat_meldung:1", {}, gespraech_arbeit(anfrage()),
                                   beendet=hoerer(ende), mit_ordner=True)
                    for _ in range(200):
                        if a.stroeme:
                            break
                        time.sleep(0.01)
                    assert os.path.isdir(ki.ordner(z["id"]))
                    if weg == "selber_prozess":
                        assert ki.abbrechen(z["id"])
                    else:
                        db.execute("UPDATE ki_laeufe SET abbrechen = 1 WHERE id = ?", (z["id"],))
                    assert ki.warten(z["id"], 10), weg
                finally:
                    ki.CLIENT = alt
                z = ki.zeile(z["id"])
                assert z["status"] == "abgebrochen" and z["beendet_am"] and z["fehler"] == "Abgebrochen.", (weg, dict(z))
                assert strom.geschlossen.is_set() and ende == ["abgebrochen"] and not os.path.isdir(ki.ordner(z["id"]))
                assert not ki.abbrechen(z["id"])                       # läuft nicht mehr
            # Abbruch mitten in einer Antwort: Ihr Zwischenstand (Eingabe aus message_start, bisherige Ausgabe) zählt als
            # Zeile „unvollstaendig“ – die Kosten sind dann „mindestens“ (Prüfung Ablauf, Befund 5).
            teil = nachricht([], stop=None, usage={"input_tokens": 500_000, "output_tokens": 30_000})
            a = Attrappe([nachricht([text("p")], stop="pause_turn"), _Strom(None, haengen=True, teil=teil)])
            alt = einsetzen(a)
            try:
                z = ki.starten("mat_recherche", "mat_meldung:1", {}, gespraech_arbeit(anfrage()))
                for _ in range(200):
                    if len(a.stroeme) == 2:
                        break
                    time.sleep(0.01)
                assert ki.abbrechen(z["id"]) and ki.warten(z["id"], 10)
            finally:
                ki.CLIENT = alt
            z = ki.zeile(z["id"])
            usage = json.loads(z["usage_json"])
            assert z["status"] == "abgebrochen" and len(usage) == 2 and usage[1]["unvollstaendig"] \
                and usage[1]["eingabe"] == 500_000 and "unvollstaendig" not in usage[0], usage
            assert z["kosten_cent"] == ki.kosten_cent(usage) >= 260 and ki.unvollstaendig(usage) \
                and ki.kosten_text(z["kosten_cent"], True).startswith("mindestens ca. ") and not ki.unvollstaendig(
                    usage[:1]), z["kosten_cent"]
            # Unlesbares Werkzeug-JSON mitten im Stream: Auch der verworfene Versuch zählt (mit Zwischenstand).
            a = Attrappe([_Strom(None, fehler=ValueError("kaputt"), teil=teil), nachricht([text("ok")])])
            alt = einsetzen(a)
            try:
                z = lauf_starten(gespraech_arbeit(anfrage()))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig" and [u.get("unvollstaendig", False) for u in json.loads(z["usage_json"])] \
                == [True, False], z["usage_json"]
            # Zeitgrenze
            ki.ARTEN["mat_recherche"]["gesamt_sek"] = 0.3
            a = Attrappe([_Strom(nachricht([text("nie")]), haengen=True)])
            alt = einsetzen(a)
            try:
                z = lauf_starten(gespraech_arbeit(anfrage()))
            finally:
                ki.CLIENT = alt
                ki.ARTEN["mat_recherche"]["gesamt_sek"] = alt_grenze
            assert z["status"] == "abgebrochen" and "Zeitgrenze" in z["fehler"], dict(z)
            # Von außen beendet (für tot erklärt oder gelöscht): Der Lauf hört auf und schreibt kein Ergebnis.
            a = Attrappe([_Strom(nachricht([text("nie")]), haengen=True)])
            alt = einsetzen(a)
            try:
                z = ki.starten("mat_recherche", "mat_meldung:1", {}, gespraech_arbeit(anfrage()))
                time.sleep(0.1)
                db.execute("DELETE FROM ki_laeufe WHERE id = ?", (z["id"],))
                assert ki.warten(z["id"], 10)
            finally:
                ki.CLIENT = alt
            assert ki.zeile(z["id"]) is None
            # Fertig gegen ein Kennzeichen, das kurz vor dem Ende kam: „abgebrochen“, kein Ergebnis.
            def arbeit(lauf):
                db.execute("UPDATE ki_laeufe SET abbrechen = 1 WHERE id = ?", (lauf.id,))
                return {"x": 1}
            z = lauf_starten(arbeit)
            assert z["status"] == "abgebrochen" and z["ergebnis_json"] is None, dict(z)

            # Tote Läufe: ohne Lebenszeichen seit 120 s (Prozess endete) – nicht, wenn sein Thread hier noch lebt.
            alt_zeit = "2026-01-01T00:00:00+00:00"
            tot = db.execute("INSERT INTO ki_laeufe (art, bezug, status, gestartet_am, lebenszeichen_am) VALUES "
                             "('mat_recherche', 'mat_meldung:9', 'laeuft', ?, ?)", (alt_zeit, alt_zeit))
            os.makedirs(ki.ordner(tot), exist_ok=True)
            frisch = db.execute("INSERT INTO ki_laeufe (art, bezug, status, gestartet_am, lebenszeichen_am) VALUES "
                                "('wiki_entwurf', '', 'laeuft', ?, ?)", (alt_zeit, db.now()))
            lebend = db.execute("INSERT INTO ki_laeufe (art, bezug, status, gestartet_am, lebenszeichen_am) VALUES "
                                "('anders', '', 'laeuft', ?, ?)", (alt_zeit, alt_zeit))
            ki._LAEUFER[lebend] = None
            nach_tod = []
            alt_nach = dict(ki._NACH_TOD)
            ki.bei_tod("mat_recherche", lambda z: nach_tod.append((z["id"], z["status"], z["fehler"])))
            try:
                assert ki.tote_aufraeumen() == [tot]
            finally:
                ki._LAEUFER.pop(lebend, None)
                ki._NACH_TOD.clear()
                ki._NACH_TOD.update(alt_nach)
            assert nach_tod == [(tot, "abgebrochen", ki.TOT_TEXT)], nach_tod
            z = ki.zeile(tot)
            assert z["status"] == "abgebrochen" and z["fehler"] == ki.TOT_TEXT and not os.path.isdir(ki.ordner(tot))
            assert ki.zeile(frisch)["status"] == "laeuft" and ki.zeile(lebend)["status"] == "laeuft"
            db.execute("DELETE FROM ki_laeufe WHERE id IN (?, ?)", (frisch, lebend))

            # Zwei gleichzeitige Starts derselben Art: genau einer läuft, der andere bekommt 409.
            strom = _Strom(nachricht([text("nie")]), haengen=True)
            a = Attrappe(lambda anfrage_, nr: strom)
            alt = einsetzen(a)
            ergebnisse = []

            def starten(bez):
                with app.test_request_context():
                    from flask import g
                    g.user = db.query("SELECT * FROM users ORDER BY id LIMIT 1", one=True)
                    try:
                        ergebnisse.append(ki.starten("mat_recherche", bez, {}, gespraech_arbeit(anfrage()))["id"])
                    except ki.KiFehler as exc:
                        ergebnisse.append(exc.code)
            try:
                fäden = [threading.Thread(target=starten, args=(f"mat_meldung:{i}",)) for i in (20, 21)]
                for f in fäden:
                    f.start()
                for f in fäden:
                    f.join(10)
                assert sorted(ergebnisse, key=str).count(409) == 1, ergebnisse
                lid = next(x for x in ergebnisse if x != 409)
                ki.abbrechen(lid)
                assert ki.warten(lid, 10)
            finally:
                ki.CLIENT = alt
        finally:
            ctx.pop()
            ki.PULS_SEK = alt_puls
    print("Abbruch, Zeitgrenze, tote Läufe und gleichzeitige Starts bestanden.")


def _echter_client(antwort_fn, protokoll):
    """Der echte SDK-Client, dessen HTTP-Verkehr ein MockTransport beantwortet (kein Netz)."""
    import anthropic
    import httpx2

    def handler(anfrage_http):
        protokoll.append((dict(anfrage_http.headers), json.loads(anfrage_http.content)))
        return antwort_fn(anfrage_http)
    return anthropic.Anthropic(api_key=SCHLUESSEL, base_url="http://api.test", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))


def _sse(nachricht_dict, bloecke):
    """Ein SSE-Strom wie von der API: message_start, je Block start/delta/stop, message_delta, message_stop."""
    ereignisse = [{"type": "message_start", "message": dict(nachricht_dict, content=[], stop_reason=None)}]
    for i, b in enumerate(bloecke):
        if b["type"] == "text":
            ereignisse += [{"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}},
                           {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": b["text"]}}]
        elif b["type"] == "tool_use":
            ereignisse += [{"type": "content_block_start", "index": i,
                            "content_block": {"type": "tool_use", "id": b["id"], "name": b["name"], "input": {}}},
                           {"type": "content_block_delta", "index": i,
                            "delta": {"type": "input_json_delta", "partial_json": json.dumps(b["input"])}}]
        ereignisse.append({"type": "content_block_stop", "index": i})
    ereignisse += [{"type": "message_delta", "delta": {"stop_reason": nachricht_dict["stop_reason"],
                                                       "stop_sequence": None}, "usage": {"output_tokens": 7}},
                   {"type": "message_stop"}]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in ereignisse).encode()


def test_echter_client_und_fehlerkette():
    """Der echte SDK-Client nimmt die Parameter an (Beta-Kopfzeile, fallbacks, output_config, cache_control, Werkzeuge
    mit eager_input_streaming) und serialisiert den Verlauf; HTTP-Fehler werden zu Sätzen ohne Schlüssel."""
    import httpx2

    from app import ki
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        ctx = im_kontext(app)
        try:
            protokoll = []
            antworten = [
                (nachricht([], stop="tool_use"), [werkzeug("eins", {"x": 1}, "toolu_q")]),
                (nachricht([], stop="end_turn"), [text("fertig")]),
            ]

            def antwort(_r):
                n, b = antworten[len(protokoll) - 1]
                return httpx2.Response(200, headers={"content-type": "text/event-stream", "request-id": "req_x"},
                                       content=_sse(n, b))
            client = _echter_client(antwort, protokoll)
            alt = ki.CLIENT
            ki.CLIENT = lambda: client
            try:
                anf = anfrage(betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                              thinking={"type": "adaptive"}, output_config={"effort": "high"},
                              cache_control={"type": "ephemeral"},
                              system=[{"type": "text", "text": "Anweisung", "cache_control": {"type": "ephemeral"}}],
                              tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
                                     {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 12,
                                      "allowed_domains": ["hersteller.test", "web.archive.org"]},
                                     {"name": "eins", "description": "Probe", "eager_input_streaming": True,
                                      "input_schema": {"type": "object"}}])
                z = lauf_starten(gespraech_arbeit(anf, {"eins": lambda e: ki.Antwort(f"gesehen {e['x']}")}))
            finally:
                ki.CLIENT = alt
            assert z["status"] == "fertig", dict(z)
            kopf, rumpf = protokoll[0]
            assert kopf["anthropic-beta"] == "server-side-fallback-2026-07-01" and kopf["x-api-key"] == SCHLUESSEL
            assert rumpf["fallbacks"] == "default" and rumpf["output_config"] == {"effort": "high"} \
                and rumpf["thinking"] == {"type": "adaptive"} and rumpf["stream"] is True \
                and rumpf["tools"][2]["eager_input_streaming"] is True and "tool_choice" not in rumpf, rumpf
            _, rumpf2 = protokoll[1]
            assert rumpf2["messages"][1] == {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_q", "name": "eins", "input": {"x": 1}}]}, rumpf2["messages"][1]
            assert rumpf2["messages"][2] == {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_q", "content": "gesehen 1"}]}, rumpf2["messages"][2]

            # Fehlerkette: Status → Satz, nie der Schlüssel; ins Protokoll Klasse, Status, Anfragekennung.
            protokolliert = []

            class Fang(logging.Handler):
                def emit(self, record):
                    protokolliert.append(record.getMessage())
            fang = Fang()
            logging.getLogger("app.ki").addHandler(fang)
            try:
                for status, teil in ((401, "Schlüssel wurde abgelehnt"), (403, "darf das nicht"),
                                     (404, "nicht gefunden"), (400, "Anfrage abgelehnt"), (429, "Ratenlimit"),
                                     (402, "Abrechnung"), (500, "überlastet"), (529, "überlastet"),
                                     (418, "Fehler (418)"), ("netz", "Keine Verbindung"),
                                     ("zeit", "Zeitüberschreitung")):
                    def antwort_f(r, status=status):
                        if status == "netz":
                            raise httpx2.ConnectError("weg", request=r)
                        if status == "zeit":
                            raise httpx2.ReadTimeout("zu langsam", request=r)
                        return httpx2.Response(status, headers={"request-id": "req_fehler"}, json={
                            "type": "error", "error": {"type": "x", "message": f"Fehler mit {SCHLUESSEL}"}})
                    client = _echter_client(antwort_f, [])
                    ki.CLIENT = lambda client=client: client
                    try:
                        z = lauf_starten(gespraech_arbeit(anfrage()))
                    finally:
                        ki.CLIENT = alt
                    assert z["status"] == "fehlgeschlagen" and teil in z["fehler"], (status, dict(z))
                    assert SCHLUESSEL not in z["fehler"] and "sk-ant" not in z["fehler"], z["fehler"]
            finally:
                logging.getLogger("app.ki").removeHandler(fang)
            assert protokolliert and not any(SCHLUESSEL in p for p in protokolliert), protokolliert
            assert any("req_fehler" in p for p in protokolliert)
            # Ein unerwarteter Fehler in der Arbeit: allgemeiner Satz, Einzelheiten im Protokoll.
            z = lauf_starten(lambda lauf: 1 / 0)
            assert z["status"] == "fehlgeschlagen" and z["fehler"] == ki.UNERWARTET
        finally:
            ctx.pop()
    print("Echter SDK-Client und Fehlerkette bestanden.")


class _StummeApi(BaseHTTPRequestHandler):
    """Ein lokaler Ersatz der API (http://127.0.0.1): sendet message_start und dann – je nach Modus – nichts mehr bis
    zum Schließen nach schliessen_nach Sekunden (wie eine lange Phase der Server-Werkzeuge ohne ping), oder ping alle
    ping Sekunden und am Ende die Antwort. Prüfung Sicherheit vom 21.11.2026, Befund 2 / Probe 11."""
    protocol_version = "HTTP/1.1"
    modus = {"ping": None, "schliessen_nach": 4.0, "anfragen": 0}

    def log_message(self, *a):
        pass

    def _schreiben(self, daten):
        self.wfile.write(f"{len(daten):x}\r\n".encode() + daten + b"\r\n")
        self.wfile.flush()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        _StummeApi.modus["anfragen"] += 1
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        n = nachricht([], stop="end_turn", usage={"input_tokens": 123_000, "output_tokens": 1})
        alles = _sse(n, [text("fertig")]).split(b"\n\n")
        try:
            self._schreiben(alles[0] + b"\n\n")                     # message_start
            t0, ping = time.monotonic(), self.modus["ping"]
            while time.monotonic() - t0 < self.modus["schliessen_nach"]:
                time.sleep(ping or 0.05)
                if ping:
                    self._schreiben(b'event: ping\ndata: {"type": "ping"}\n\n')
            if ping:
                self._schreiben(b"\n\n".join(alles[1:]))
                self._schreiben(b"")
        except OSError:
            return
        self.close_connection = True


def test_echter_client_abbruch():
    """Mit dem echten SDK-Client (anthropic 1.17.0) gegen einen lokalen SSE-Server, der nach message_start schweigt:
    Abbrechen und die Zeitgrenze beenden den Lauf sofort – der Puls erreicht den Socket über das SDK und weckt das
    blockierte recv mit shutdown() (vorher erst, wenn der Server schloss). Der Zwischenstand aus message_start zählt
    („mindestens“). Mit ping alle 0,2 s steht im Protokoll ein größter Abstand unter 1 s – gemessen an den rohen
    Ereignissen, denn das SDK reicht ping nicht durch."""
    import anthropic

    from app import ki
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _StummeApi)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{httpd.server_address[1]}"
    alt_client, alt_puls, alt_grenze = ki.CLIENT, ki.PULS_SEK, ki.ARTEN["mat_recherche"]["gesamt_sek"]
    ki.CLIENT = lambda: anthropic.Anthropic(api_key=SCHLUESSEL, base_url=basis, max_retries=0)
    ki.PULS_SEK = 0.05
    protokoll = []

    class Fang(logging.Handler):
        def emit(self, record):
            protokoll.append(record.getMessage())
    fang = Fang()
    logger = logging.getLogger("app.ki")
    alt_stufe = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(fang)
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        ctx = im_kontext(app)
        try:
            _StummeApi.modus.update(ping=None, schliessen_nach=6.0)
            for weg in ("abbrechen", "zeitgrenze"):
                ki.ARTEN["mat_recherche"]["gesamt_sek"] = 0.6 if weg == "zeitgrenze" else alt_grenze
                vorher = _StummeApi.modus["anfragen"]
                t0 = time.monotonic()
                z = ki.starten("mat_recherche", "mat_meldung:1", {}, gespraech_arbeit(anfrage()))
                for _ in range(300):
                    if _StummeApi.modus["anfragen"] > vorher:
                        break
                    time.sleep(0.01)
                time.sleep(0.3)
                if weg == "abbrechen":
                    assert ki.abbrechen(z["id"])
                assert ki.warten(z["id"], 10), weg
                dauer = time.monotonic() - t0
                z = ki.zeile(z["id"])
                assert z["status"] == "abgebrochen" and dauer < 3.0, (weg, dauer, dict(z))
                assert ("Zeitgrenze" in z["fehler"]) == (weg == "zeitgrenze"), z["fehler"]
                usage = json.loads(z["usage_json"])
                assert usage and usage[-1]["unvollstaendig"] and usage[-1]["eingabe"] == 123_000, usage
            ki.ARTEN["mat_recherche"]["gesamt_sek"] = alt_grenze
            # Mit ping: Der Lauf endet normal; der größte Abstand liegt bei den 0,2 s der pings, nicht bei 1 s.
            _StummeApi.modus.update(ping=0.2, schliessen_nach=1.0)
            protokoll.clear()
            z = lauf_starten(gespraech_arbeit(anfrage()))
            assert z["status"] == "fertig", dict(z)
            zeile_log = [p for p in protokoll if "größter Abstand" in p]
            assert len(zeile_log) == 1, protokoll
            import re
            abstand = float(re.search(r"Streams ([\d.]+) s", zeile_log[0]).group(1))
            assert abstand < 0.8, zeile_log
        finally:
            ctx.pop()
            logger.removeHandler(fang)
            logger.setLevel(alt_stufe)
            ki.CLIENT, ki.PULS_SEK = alt_client, alt_puls
            ki.ARTEN["mat_recherche"]["gesamt_sek"] = alt_grenze
            httpd.shutdown()
            httpd.server_close()
    print("Echter SDK-Client: Abbruch, Zeitgrenze und Abstand der Ereignisse bestanden.")


def test_konto_leeren_statisch():
    """Kontolöschung setzt den Namen, Leeren entfernt Inhalt und Ordner (die Zeile bleibt), der Schlüssel kommt nur
    aus der Umgebung und nur in app/ki.py vor."""
    from app import db, ki
    with tempfile.TemporaryDirectory() as tmp:
        app = app_mit_schluessel(tmp)
        adm = app.test_client()
        assert adm.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code \
            == 200
        r = adm.post("/api/admin/users", json={"email": "starter@example.org", "password": "passwort1",
                                               "name": "Starter Probe"})
        assert r.status_code == 201, r.get_json()
        uid = r.json["user"]["id"]
        with app.app_context():
            jetzt = db.now()
            lid = db.execute("INSERT INTO ki_laeufe (art, bezug, status, eingabe_json, ergebnis_json, gestartet_von, "
                             "gestartet_von_name, gestartet_am, beendet_am) VALUES ('mat_recherche', 'mat_meldung:1', "
                             "'fertig', '{\"a\": 1}', '{\"b\": 2}', ?, 'Starter Probe', ?, ?)", (uid, jetzt, jetzt))
            os.makedirs(ki.ordner(lid), exist_ok=True)
        assert adm.delete(f"/api/admin/users/{uid}", headers=H).status_code == 200
        with app.app_context():
            z = ki.zeile(lid)
            assert z["gestartet_von"] is None and z["gestartet_von_name"] == ki.GELOESCHT, dict(z)
            ki.leeren(lid)
            z = ki.zeile(lid)
            assert z["eingabe_json"] == "{}" and z["ergebnis_json"] is None and not os.path.isdir(ki.ordner(lid))
            assert ki.kontingent("mat_recherche")["verbraucht"] == 1
            # Aufräumen: Ordner ohne Zeile und gescheiterter Läufe gehen, fertige bleiben (Sache des Moduls).
            for n in (lid, 999):
                os.makedirs(ki.ordner(n), exist_ok=True)
            db.execute("UPDATE ki_laeufe SET status = 'abgebrochen' WHERE id = ?", (lid,))
            fertig = db.execute("INSERT INTO ki_laeufe (art, status, gestartet_am, beendet_am) VALUES "
                                "('mat_recherche', 'fertig', ?, ?)", (jetzt, jetzt))
            os.makedirs(ki.ordner(fertig), exist_ok=True)
            ki.aufraeumen()
            assert not os.path.isdir(ki.ordner(lid)) and not os.path.isdir(ki.ordner(999)) \
                and os.path.isdir(ki.ordner(fertig))
    # Statisch: ANTHROPIC_API_KEY nur in app/ki.py (dort nur aus os.environ), nicht in Einstellungen, Vorlagen, JS.
    wurzel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
    fundstellen = []
    for w, _, namen in os.walk(wurzel):
        for n in namen:
            if n.endswith((".py", ".js", ".html", ".css", ".md")):
                with open(os.path.join(w, n), encoding="utf-8") as fh:
                    inhalt = fh.read()
                rel = os.path.relpath(os.path.join(w, n), wurzel)
                if '"ANTHROPIC_API_KEY"' in inhalt or "'ANTHROPIC_API_KEY'" in inhalt:
                    fundstellen.append(rel)          # als Zeichenkette im Code – nur dort wird er gelesen
                if n.endswith((".js", ".html")) or n == "einstellungen.py":
                    assert "ANTHROPIC" not in inhalt, rel
                if n.endswith(".js"):
                    assert "anthropic" not in inhalt.lower(), n
    assert fundstellen == ["ki.py"], fundstellen
    with open(os.path.join(wurzel, "ki.py"), encoding="utf-8") as fh:
        quelle = fh.read()
    import re
    # Im Code wird der Schlüssel nur über os.environ gelesen (sonst steht er nur in Kommentaren und Docstrings).
    zugriffe = re.findall(r'(.{0,16})"ANTHROPIC_API_KEY"', quelle)
    assert zugriffe and all(z.endswith(("os.environ.get(", "os.environ[")) for z in zugriffe), zugriffe
    print("Kontolöschung, Leeren, Aufräumen und statische Prüfung bestanden.")


if __name__ == "__main__":
    test_tabelle()
    test_schluessel_und_kosten()
    test_kontingent()
    test_gespraech()
    test_abbruch_und_tote()
    test_echter_client_und_fehlerkette()
    test_echter_client_abbruch()
    test_konto_leeren_statisch()
