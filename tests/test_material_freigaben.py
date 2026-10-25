"""Freigaben je Ordner – Vergeben, Ändern, Entziehen, Verlängern und Nutzerverwaltung (Phase 2 · Lieferung 1,
Paket B):  python tests/test_material_freigaben.py  oder  pytest tests/test_material_freigaben.py

Nach dem Bauentwurf 8.3: Journal ohne Notiz, Vorlagen in einer Transaktion, die Grenzen aus 1.6 einzeln, der
Übernahme-Schutz (Kritik 4), die Listen direkt/geerbt/unten, „Meine Freigaben“, der Verlängern-Knopf, die Nutzersuche
ohne E-Mail, die Nutzerverwaltung (Material nur Anzeige, gruppierte Abfrage, Journal ohne E-Mail, Häkchen nur mit
Namen). Die DEMO-Konten prüft seit dem 25.10.2026 tests/test_material_beispielbestand.py (das DEMO-Skript ist
entfernt).

Tests, die erst mit einem anderen Paket laufen können, tragen @braucht("<Paket>", <Prüfung>): Fehlt das Paket noch,
werden sie übersprungen (mit Meldung); ist es da, laufen sie voll. Alle Namen und Nummern hier sind erfunden und nur
für den Test da."""
import functools
import inspect
import json
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import (H, _heute, freigeben, gliederung, katalog_grund, neuer_artikel, neues_konto,  # noqa: E402
                           pruef_formulare, starten, umgebung)
from test_material_ueberblick import ordner_neu  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FR = "/api/material/ordner/{}/freigaben"
EINTRAG = {"id", "ordner", "konto", "recht", "bis", "gueltig", "wirkt", "wirkt_nicht", "grundrecht_dort", "traegt_pruefen",
           "laeuft_ab_in_tagen", "vergeben_von", "seit", "aenderbar", "entziehbar", "eigen"}
KONTO = {"id", "name", "gliederung", "aktiv", "haekchen", "qualifiziert", "zugang"}


def braucht(paket, vorhanden):
    """Ein Test, der erst mit einem anderen Paket grün sein kann: Ohne es übersprungen (pytest: skip), mit ihm voll."""
    def deko(f):
        @functools.wraps(f)
        def lauf():
            if not vorhanden():
                meldung = f"{f.__name__}: übersprungen – braucht Paket {paket}."
                if "pytest" in sys.modules:
                    import pytest
                    pytest.skip(meldung)
                print(meldung)
                return
            return f()
        return lauf
    return deko


def _a1_ordner_loeschen():
    """Paket A1 schreibt beim Löschen eines Ordners vorher „freigabe_entfernt“ je Freigabe (bestand.ordner_loeschen)."""
    from app.material.services import bestand
    return "freigabe_entfernt" in inspect.getsource(bestand)


def tag(n):
    return (_heute() + timedelta(days=n)).isoformat()


def erteilen(c, fid, **d):
    return c.post(FR.format(fid), json=d)


def liste(c, fid):
    r = c.get(FR.format(fid))
    assert r.status_code == 200, r.get_json()
    return r.json


def zeilen(app, abfrage, args=()):
    with app.app_context():
        from app import db
        return db.query(abfrage, args)


def sql(app, befehl, args=()):
    with app.app_context():
        from app import db
        db.execute(befehl, args)


def grant(app, fid, uid, recht):
    r = zeilen(app, "SELECT * FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission = ?",
               (fid, uid, recht))
    return r[0] if r else None


def journal(app, fid):
    """Die Freigabe-Einträge am Ordner, älteste zuerst – mit gelesenem JSON."""
    out = []
    for e in zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'folder' AND entity_id = ? AND action LIKE 'freigabe_%' "
                         "ORDER BY id", (fid,)):
        out.append(dict(e, vorher=json.loads(e["before_json"]) if e["before_json"] else None,
                        nachher=json.loads(e["after_json"]) if e["after_json"] else None))
    return out


def ref(app, uid):
    return zeilen(app, "SELECT mat_ref FROM users WHERE id = ?", (uid,))[0]["mat_ref"]


def adm_id(adm):
    return adm.get("/api/me").json["user"]["id"]


# --- Erteilen, ändern, entziehen – mit Journal, ohne Notiz -------------------------------------------------------

def test_erteilen_aendern_entziehen():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        helfer, helfer_id = neues_konto(app, "helfer@example.org", name="Helfer Test")
        # Mitglied ohne Freigabe: Modulzugang (Katalog, Suche), aber kein Bestand.
        r = helfer.get("/api/material/start")
        assert r.status_code == 200 and not r.json["darf"]["lesen"], r.get_json()

        r = erteilen(w, lager, user_id=helfer_id, grundrecht="lesen", notiz="Testnotiz Schrank 3")
        assert r.status_code == 201, r.get_json()
        f = r.json["freigaben"][0]
        assert set(f) == EINTRAG | {"notiz"} and set(f["konto"]) == KONTO, f
        assert (f["recht"], f["bis"], f["notiz"], f["vergeben_von"], f["aenderbar"], f["wirkt"]) == (
            "lesen", None, "Testnotiz Schrank 3", "wart", True, True), f
        assert f["ordner"] == {"id": lager, "pfad": "OG Musterstadt / Lager"}, f
        assert [x["id"] for x in r.json["liste"]["direkt"]] == [f["id"]]
        # Wirkt sofort – die Person sieht das Lager, aber nicht die Gliederung darüber.
        assert helfer.get(f"/api/material/ordner/{lager}").status_code == 200
        assert helfer.get(f"/api/material/ordner/{gid}").status_code == 404

        e = journal(app, lager)
        assert [x["action"] for x in e] == ["freigabe_erteilt"] and e[0]["user_name"] == "wart"
        assert e[0]["vorher"] is None and e[0]["nachher"] == {
            "freigabe": f["id"], "konto": {"ref": ref(app, helfer_id)}, "recht": "lesen", "bis": None,
            "notiz_geaendert": True}, e[0]

        # Ändern: Recht, Ende, Notiz – im Journal vorher und nachher, die Notiz nur als „geändert“.
        r = w.put(f"/api/material/freigaben/{f['id']}", json={"recht": "verwalten", "bis": tag(100), "notiz": "Testnotiz neu"})
        assert r.status_code == 200 and r.json["freigabe"]["recht"] == "verwalten", r.get_json()
        assert r.json["freigabe"]["bis"] == tag(100) and r.json["freigabe"]["notiz"] == "Testnotiz neu"
        r = w.put(f"/api/material/freigaben/{f['id']}", json={"notiz": "Testnotiz drei"})
        assert r.status_code == 200, r.get_json()
        assert w.put(f"/api/material/freigaben/{f['id']}", json={"notiz": "Testnotiz drei"}).status_code == 200   # nichts neu
        e = journal(app, lager)
        assert [x["action"] for x in e] == ["freigabe_erteilt", "freigabe_geaendert", "freigabe_geaendert"], e
        assert e[1]["vorher"] == {"freigabe": f["id"], "konto": {"ref": ref(app, helfer_id)}, "recht": "lesen", "bis": None}
        assert e[1]["nachher"] == {"freigabe": f["id"], "konto": {"ref": ref(app, helfer_id)}, "recht": "verwalten",
                                   "bis": tag(100), "notiz_geaendert": True}
        assert e[2]["vorher"]["recht"] == e[2]["nachher"]["recht"] == "verwalten" and e[2]["nachher"]["notiz_geaendert"]
        assert grant(app, lager, helfer_id, "verwalten")["updated_at"]

        # Entziehen: Journal mit dem Stand davor; danach ist das Lager zu.
        r = w.delete(f"/api/material/freigaben/{f['id']}", headers=H)
        assert r.status_code == 200 and r.json["offene_entwuerfe"] == 0, r.get_json()
        e = journal(app, lager)
        assert e[-1]["action"] == "freigabe_entzogen" and e[-1]["nachher"] is None
        assert e[-1]["vorher"] == {"freigabe": f["id"], "konto": {"ref": ref(app, helfer_id)}, "recht": "verwalten",
                                   "bis": tag(100)}
        assert helfer.get(f"/api/material/ordner/{lager}").status_code == 404     # Mitglied ohne Freigabe: wie unbekannt
        assert w.delete(f"/api/material/freigaben/{f['id']}", headers=H).json == w.delete("/api/material/freigaben/999999", headers=H).json

        # Die Notiz steht nirgends im Journal – auch Name und E-Mail der Person nicht (nur der Verweis).
        alles = json.dumps(zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'folder'"), ensure_ascii=False, default=str)
        assert "Testnotiz" not in alles and "helfer@example.org" not in alles and "Helfer Test" not in alles
        # Der Verlauf nennt das Konto mit Namen – den Verweis selbst gibt er nicht heraus.
        v = liste(w, lager)["verlauf"]
        assert [x["aktion"] for x in v] == ["freigabe_entzogen", "freigabe_geaendert", "freigabe_geaendert",
                                            "freigabe_erteilt"], v
        assert {x["konto"] for x in v} == {"Helfer Test"} and {x["wer"] for x in v} == {"wart"}
        assert v[2]["recht_vorher"] == "lesen" and v[2]["bis_vorher"] is None and v[2]["notiz_geaendert"]
        assert ref(app, helfer_id) not in json.dumps(v)

        # Nach jedem Schreiben gilt sofort der neue Stand (sicht_verwerfen): Setzt sich der Materialwart selbst auf
        # lesen herab, zeigt schon die Antwort, dass er die Zeile nicht mehr ändern darf.
        w2, w2_id = neues_konto(app, "wart2@example.org", name="Wart Zwei")
        freigeben(adm, gid, w2_id, "verwalten")
        eigen = grant(app, gid, k["wart_id"], "verwalten")
        r = w.put(f"/api/material/freigaben/{eigen['id']}", json={"recht": "lesen"})
        assert r.status_code == 200 and r.json["freigabe"]["recht"] == "lesen", r.get_json()
        assert r.json["freigabe"]["eigen"] and not r.json["freigabe"]["aenderbar"], r.get_json()
        assert w.get(FR.format(gid)).status_code == 403
        # Ebenso beim Erteilen: Die Liste in der Antwort zeigt die neue Zeile mit Notiz.
        r = erteilen(w2, gid, user_id=helfer_id, grundrecht="lesen", notiz="Testnotiz")
        assert r.status_code == 201 and helfer_id in [x["konto"]["id"] for x in r.json["liste"]["direkt"]], r.get_json()
    print("Erteilen, ändern, entziehen bestanden.")


# --- Vorlagen: zwei Zeilen in einer Transaktion -----------------------------------------------------------------

def test_vorlagen_eine_transaktion():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        vorher = len(journal(app, gid))
        # „Prüfer“ an ein Konto ohne Qualifikation: Die Prüffreigabe scheitert – und das Grundrecht entsteht auch nicht.
        _, ohne_id = neues_konto(app, "ohne-quali@example.org", name="Ohne Quali")
        r = erteilen(w, gid, user_id=ohne_id, grundrecht="lesen", pruefen_bis=tag(200))
        assert r.status_code == 409 and "Prüferqualifikation" in r.json["error"], r.get_json()
        assert not zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE user_id = ?", (ohne_id,))
        assert len(journal(app, gid)) == vorher

        p2, p2_id = neues_konto(app, "pruefer2@example.org", name="Prüferin Zwei", mat_pruefer=True, urkundennummer="1012-4712")
        r = erteilen(w, gid, user_id=p2_id, grundrecht="lesen", pruefen_bis=tag(200))          # Vorlage „Prüfer“
        assert r.status_code == 201 and [(f["recht"], f["bis"]) for f in r.json["freigaben"]] == [
            ("lesen", None), ("pruefen", tag(200))], r.get_json()
        e = journal(app, gid)[vorher:]
        assert [(x["action"], x["nachher"]["recht"]) for x in e] == [("freigabe_erteilt", "lesen"),
                                                                      ("freigabe_erteilt", "pruefen")], e
        # Noch einmal mit anderem Ende: die vorhandenen Zeilen ändern sich, es entsteht keine zweite.
        r = erteilen(w, gid, user_id=p2_id, grundrecht="verwalten", pruefen_bis=tag(300))     # „Materialwart und Prüfer“
        assert r.status_code == 201, r.get_json()
        assert [(x["permission"], x["valid_until"]) for x in zeilen(
            app, "SELECT permission, valid_until FROM mat_folder_grant WHERE user_id = ? ORDER BY permission", (p2_id,))] == [
            ("pruefen", tag(300)), ("verwalten", None)]
        assert [x["action"] for x in journal(app, gid)[vorher + 2:]] == ["freigabe_geaendert", "freigabe_geaendert"]
        # „Externer Prüfer“: nur die Prüffreigabe, an einem Unterordner.
        lager = ordner_neu(w, gid, "Lager")
        ext, ext_id = neues_konto(app, "extern@example.org", name="Extern Test", mat_pruefer=True, urkundennummer="1012-8001")
        r = erteilen(w, lager, user_id=ext_id, grundrecht=None, pruefen_bis=tag(60))
        assert r.status_code == 201 and [f["recht"] for f in r.json["freigaben"]] == ["pruefen"], r.get_json()
        assert ext.get(f"/api/material/ordner/{lager}").status_code == 200
        # Weder Grundrecht noch Prüffreigabe: 400.
        r = erteilen(w, gid, user_id=ext_id, grundrecht=None, pruefen_bis=None)
        assert r.status_code == 400 and "Recht wählen" in r.json["error"], r.get_json()
        r = erteilen(w, gid, user_id=ext_id, grundrecht="pruefen")
        assert r.status_code == 400, r.get_json()
    print("Vorlagen in einer Transaktion bestanden.")


# --- Die Grenzen aus 1.6 einzeln ----------------------------------------------------------------------------------

def test_grenzen():
    from app.material.services.interval import plus_monate
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, sys_a = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        b, sys_b = gliederung(adm, "OG Nachbarstadt", standard=False)
        wart_b, wart_b_id = neues_konto(app, "wart_b@example.org", name="Wart Nachbarstadt")
        fremd = freigeben(adm, b, wart_b_id, "verwalten")
        helfer, helfer_id = neues_konto(app, "helfer@example.org", name="Helfer Test")

        # Nr. 11: fremder Ordner (andere Gliederung) antwortet wie ein unbekannter – beim Lesen, Erteilen, Ändern.
        for m in ("get", "post"):
            r1 = getattr(w, m)(FR.format(b), json={"user_id": helfer_id, "grundrecht": "lesen"})
            r2 = getattr(w, m)(FR.format(999999), json={"user_id": helfer_id, "grundrecht": "lesen"})
            assert r1.status_code == r2.status_code == 404 and r1.json == r2.json, (r1.get_json(), r2.get_json())
        for m in ("put", "delete"):
            r1 = getattr(w, m)(f"/api/material/freigaben/{fremd}", json={"bis": tag(5)}, headers=H)
            r2 = getattr(w, m)("/api/material/freigaben/999999", json={"bis": tag(5)}, headers=H)
            assert r1.status_code == r2.status_code == 404 and r1.json == r2.json, (r1.get_json(), r2.get_json())
        r = w.post(f"{FR.format(b)}/verlaengern", json={"bis": tag(30)})
        assert r.status_code == 404 and r.json == w.post(f"{FR.format(999999)}/verlaengern", json={}).json
        # Sichtbar, aber nicht verwaltet: 403 (Führungskraft).
        assert k["fuehrung"].get(FR.format(gid)).status_code == 403
        assert erteilen(k["fuehrung"], gid, user_id=helfer_id, grundrecht="lesen").status_code == 403
        eigen_w = grant(app, gid, k["wart_id"], "verwalten")["id"]
        assert k["fuehrung"].put(f"/api/material/freigaben/{eigen_w}", json={}).status_code == 403
        # Nr. 11: Systemordner 409 – auch für den Verwalter der Gliederung.
        for s in sys_a.values():
            r = erteilen(w, s, user_id=helfer_id, grundrecht="lesen")
            assert r.status_code == 409 and "Gesperrt" in r.json["error"], r.get_json()
            assert w.get(FR.format(s)).status_code == 409

        # Nr. 12: nicht vorhanden, deaktiviert, ohne Namen – dieselbe 404; Unsinn 400; „7“ und 7.0 gelten.
        inaktiv, inaktiv_id = neues_konto(app, "inaktiv@example.org", name="Inaktiv Test")
        assert adm.put(f"/api/admin/users/{inaktiv_id}", json={"active": False}).status_code == 200
        ohne = adm.post("/api/admin/users", json={"email": "ohne@example.org", "password": "passwort1",
                                                  "rechte": {"material": 0}}).json["user"]["id"]
        antworten = [erteilen(w, gid, user_id=u, grundrecht="lesen") for u in (999999, inaktiv_id, ohne)]
        assert all(r.status_code == 404 for r in antworten) and len({json.dumps(r.json) for r in antworten}) == 1, \
            [r.get_json() for r in antworten]
        assert antworten[0].json == {"error": "Konto nicht gefunden."}
        assert erteilen(w, gid, user_id="sieben", grundrecht="lesen").status_code == 400
        assert erteilen(w, gid, user_id=str(helfer_id), grundrecht="lesen").status_code == 201
        assert erteilen(w, gid, user_id=float(helfer_id), grundrecht="verwalten").status_code == 201
        # Nr. 2/12: ein aktives Konto mit Namen, aber ohne Zugang zum Modul (Stufe 0) – 409 mit Klartext, nichts
        # geschrieben; zuordnen ließe sich ihm dagegen ein Artikel (test_material_stufen).
        stufenlos, stufenlos_id = neues_konto(app, "stufenlos@example.org", name="Stufenlos Test", stufe=0)
        r = erteilen(w, gid, user_id=stufenlos_id, grundrecht="lesen")
        assert r.status_code == 409 and "keinen Zugang zum Modul Material" in r.json["error"], r.get_json()
        assert grant(app, gid, stufenlos_id, "lesen") is None

        # Nr. 8 und 9: Enddaten. Ohne Ende („“ oder null) nur mit Grundrecht am Anker – das hat der Prüfer (lesen an
        # der Gliederung), der externe Prüfer nicht (Nachbesserung vom 18.10.2026, mehr in test_dauerhaft_pruefen).
        ext, ext_id = neues_konto(app, "extern@example.org", name="Extern Test", mat_pruefer=True, urkundennummer="1012-8001")
        r = erteilen(w, gid, user_id=ext_id, pruefen_bis="")
        assert r.status_code == 400 and "nur zusammen mit lesen oder verwalten" in r.json["error"], r.get_json()
        assert grant(app, gid, ext_id, "pruefen") is None
        assert erteilen(w, gid, user_id=ext_id, pruefen_bis=tag(30)).status_code == 201
        pz = grant(app, gid, ext_id, "pruefen")["id"]
        r = w.put(f"/api/material/freigaben/{pz}", json={"bis": None})
        assert r.status_code == 400 and "Enddatum" in r.json["error"], r.get_json()
        assert grant(app, gid, ext_id, "pruefen")["valid_until"] == tag(30)
        assert erteilen(w, gid, user_id=k["pruefer_id"], pruefen_bis="").status_code == 201
        assert grant(app, gid, k["pruefer_id"], "pruefen")["valid_until"] is None
        grenze = plus_monate(_heute(), 24)
        r = erteilen(w, gid, user_id=k["pruefer_id"], pruefen_bis=(grenze + timedelta(days=1)).isoformat())
        assert r.status_code == 400 and "24 Monate" in r.json["error"], r.get_json()
        assert erteilen(w, gid, user_id=k["pruefer_id"], pruefen_bis=grenze.isoformat()).status_code == 201
        r = erteilen(w, gid, user_id=helfer_id, grundrecht="lesen", grund_bis=tag(-1))
        assert r.status_code == 400 and "Vergangenheit" in r.json["error"], r.get_json()
        assert erteilen(w, gid, user_id=helfer_id, grundrecht="lesen", grund_bis="31.12.2027").status_code == 400
        # Nr. 8: ohne Qualifikation – Häkchen fehlt oder Urkundennummer fehlt – 409 mit demselben Text.
        urk, urk_id = neues_konto(app, "haekchen@example.org", name="Nur Häkchen", mat_pruefer=True)
        r1 = erteilen(w, gid, user_id=helfer_id, pruefen_bis=tag(30))
        r2 = erteilen(w, gid, user_id=urk_id, pruefen_bis=tag(30))
        assert r1.status_code == r2.status_code == 409 and r1.json == r2.json, (r1.get_json(), r2.get_json())
        assert "Häkchen der Verwaltung und Urkundennummer" in r1.json["error"]
        # Nr. 10: Notiz höchstens 200 Zeichen, eine Zeile.
        assert erteilen(w, gid, user_id=helfer_id, grundrecht="lesen", notiz="x" * 201).status_code == 400
        assert erteilen(w, gid, user_id=helfer_id, grundrecht="lesen", notiz="Testzeile eins\nTestzeile zwei").status_code == 201
        assert grant(app, gid, helfer_id, "lesen")["note"] == "Testzeile eins Testzeile zwei"

        # Nr. 3 und 5 mit einem befristeten Verwalter (verwalten bis in 80 Tagen, dazu eine eigene Lesefreigabe am Lager).
        gast, gast_id = neues_konto(app, "gast@example.org", name="Gast Test")
        freigeben(adm, gid, gast_id, "verwalten", bis=tag(80))
        eigen = freigeben(adm, lager, gast_id, "lesen", bis=tag(20))
        hilfe2, hilfe2_id = neues_konto(app, "helfer2@example.org", name="Helfer Zwei")
        r = erteilen(gast, lager, user_id=hilfe2_id, grundrecht="lesen")
        assert r.status_code == 403 and "Dauerhaft vergibt nur" in r.json["error"], r.get_json()
        r = erteilen(gast, lager, user_id=hilfe2_id, grundrecht="lesen", grund_bis=tag(81))
        assert r.status_code == 403 and "eigene Verwalterfreigabe" in r.json["error"], r.get_json()
        assert erteilen(gast, lager, user_id=hilfe2_id, grundrecht="lesen", grund_bis=tag(80)).status_code == 201
        r = gast.put(f"/api/material/freigaben/{eigen}", json={"bis": tag(30)})                # eigene verlängern
        assert r.status_code == 403 and "eigene Freigabe" in r.json["error"], r.get_json()
        r = gast.put(f"/api/material/freigaben/{eigen}", json={"recht": "verwalten"})          # eigene heraufsetzen
        assert r.status_code == 403, r.get_json()
        r = erteilen(gast, lager, user_id=gast_id, pruefen_bis=tag(10))                         # sich selbst neu
        assert r.status_code == 403 and "Dir selbst" in r.json["error"], r.get_json()
        assert gast.put(f"/api/material/freigaben/{eigen}", json={"bis": tag(10)}).status_code == 200   # verkürzen geht
        assert grant(app, lager, gast_id, "lesen")["valid_until"] == tag(10)

        # Nr. 1: Die Verwaltung darf überall – dauerhaft, auch sich selbst eine Prüffreigabe (mit Qualifikation); die
        # 24 Monate und die Qualifikation gelten auch für sie.
        assert erteilen(adm, b, user_id=helfer_id, grundrecht="verwalten").status_code == 201
        a_id = adm_id(adm)
        assert erteilen(adm, b, user_id=a_id, pruefen_bis=tag(30)).status_code == 409
        assert adm.put(f"/api/admin/users/{a_id}", json={"mat_pruefer": True, "urkundennummer": "1012-0099"}).status_code == 200
        assert erteilen(adm, b, user_id=a_id, pruefen_bis=tag(30)).status_code == 201
        assert erteilen(adm, b, user_id=a_id, pruefen_bis=(grenze + timedelta(days=1)).isoformat()).status_code == 400
        assert erteilen(adm, sys_b["gesperrt"], user_id=helfer_id, grundrecht="lesen").status_code == 409
    print("Grenzen aus 1.6 bestanden.")


# --- Übernahme-Schutz (Kritik 4) -----------------------------------------------------------------------------------

def test_uebernahme_schutz():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        gast, gast_id = neues_konto(app, "gast@example.org", name="Gast Test")
        freigeben(adm, gid, gast_id, "verwalten", bis=tag(40))
        dauer = grant(app, gid, k["wart_id"], "verwalten")["id"]
        # Der befristete Gast kann den dauerhaften Verwalter weder entziehen noch kürzen noch herabsetzen.
        for m, d in (("delete", None), ("put", {"bis": tag(10)}), ("put", {"recht": "lesen"})):
            r = getattr(gast, m)(f"/api/material/freigaben/{dauer}", json=d, headers=H)
            assert r.status_code == 403 and "reicht weiter als deine eigene" in r.json["error"], (m, d, r.get_json())
        assert grant(app, gid, k["wart_id"], "verwalten")["valid_until"] is None
        assert not [x for x in liste(gast, gid)["direkt"] if x["id"] == dauer][0]["aenderbar"]

        # Der dauerhafte Verwalter entzieht oder kürzt sich nicht, wenn danach nur der Gast bliebe – die Liste sagt es
        # vorab („entziehbar“), statt „Entziehen“ anzubieten. Der Gast dagegen kann sich selbst entziehen.
        eigen = [x for x in liste(w, gid)["direkt"] if x["id"] == dauer][0]
        assert eigen["eigen"] and eigen["aenderbar"] and not eigen["entziehbar"], eigen
        g_eigen = [x for x in liste(gast, gid)["direkt"] if x["eigen"]][0]
        assert g_eigen["aenderbar"] and g_eigen["entziehbar"], g_eigen
        for m, d in (("delete", None), ("put", {"bis": tag(30)}), ("put", {"recht": "lesen"})):
            r = getattr(w, m)(f"/api/material/freigaben/{dauer}", json=d, headers=H)
            assert r.status_code == 409 and "das macht nur die Material-Verwaltung" in r.json["error"], (m, d, r.get_json())
        assert grant(app, gid, k["wart_id"], "verwalten")["valid_until"] is None
        assert not [x for x in journal(app, gid) if x["action"] != "freigabe_erteilt"]
        # Mit einem zweiten dauerhaften geht es.
        w2, w2_id = neues_konto(app, "wart2@example.org", name="Wart Zwei")
        zweit = freigeben(adm, gid, w2_id, "verwalten")
        assert [x for x in liste(w, gid)["direkt"] if x["id"] == dauer][0]["entziehbar"]
        # Fremde Zeilen: entziehbar, soweit änderbar; die Verwaltung entzieht alles.
        assert all(x["entziehbar"] == x["aenderbar"] for x in liste(w, gid)["direkt"] if not x["eigen"])
        assert all(x["entziehbar"] for x in liste(adm, gid)["direkt"])
        assert w.delete(f"/api/material/freigaben/{dauer}", headers=H).status_code == 200
        assert grant(app, gid, k["wart_id"], "verwalten") is None

        # Zwei dauerhafte ändern sich gegenseitig – wer danach kürzer verwaltet, kommt an den anderen nicht mehr heran.
        dauer = freigeben(adm, gid, k["wart_id"], "verwalten")
        r = w2.put(f"/api/material/freigaben/{dauer}", json={"bis": tag(200)})
        assert r.status_code == 200, r.get_json()
        assert w.put(f"/api/material/freigaben/{zweit}", json={"bis": tag(100)}).status_code == 403
        assert w2.put(f"/api/material/freigaben/{dauer}", json={"bis": None}).status_code == 200
        assert w.put(f"/api/material/freigaben/{zweit}", json={"recht": "lesen"}).status_code == 200
        assert grant(app, gid, w2_id, "lesen") and not grant(app, gid, w2_id, "verwalten")
        # Die Verwaltung ist an die Grenzen nicht gebunden: Sie entzieht auch den letzten dauerhaften Verwalter.
        assert adm.delete(f"/api/material/freigaben/{dauer}", headers=H).status_code == 200
        # Gleichrangige Gäste (gleiches Ende) ändern sich gegenseitig.
        gast2, gast2_id = neues_konto(app, "gast2@example.org", name="Gast Zwei")
        g2 = freigeben(adm, gid, gast2_id, "verwalten", bis=tag(40))
        assert gast.put(f"/api/material/freigaben/{g2}", json={"bis": tag(20)}).status_code == 200
    print("Übernahme-Schutz bestanden.")


# --- Eigene Zeilen: verkürzen und entziehen gehen immer (1.6 Nr. 5) ------------------------------------------------

def test_eigene_laenger_als_verwalten():
    """Eine eigene Freigabe, die länger läuft als das eigene Verwalten (hier eine Prüffreigabe von der Verwaltung), lässt
    sich verkürzen und entziehen – Nr. 4 („reicht weiter als deine eigene“) gilt nur für fremde Zeilen. Was danach
    bleibt, endet nach Nr. 3 nicht später als das eigene Verwalten."""
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        gid, _ = gliederung(adm)
        gast, gast_id = neues_konto(app, "gast@example.org", name="Gast Test", mat_pruefer=True, urkundennummer="1012-0042")
        freigeben(adm, gid, gast_id, "verwalten", bis=tag(30))
        eigen = freigeben(adm, gid, gast_id, "pruefen", bis=tag(300))
        zeile = [x for x in liste(gast, gid)["direkt"] if x["id"] == eigen][0]
        assert zeile["eigen"] and zeile["aenderbar"], zeile
        r = gast.put(f"/api/material/freigaben/{eigen}", json={"bis": tag(200)})          # Nr. 3: länger als bis +30
        assert r.status_code == 403 and "eigene Verwalterfreigabe" in r.json["error"], r.get_json()
        r = gast.put(f"/api/material/freigaben/{eigen}", json={"bis": tag(20)})
        assert r.status_code == 200 and r.json["freigabe"]["bis"] == tag(20), r.get_json()
        assert gast.put(f"/api/material/freigaben/{eigen}", json={"bis": tag(25)}).status_code == 403   # nie verlängern
        freigeben(adm, gid, gast_id, "pruefen", bis=tag(300))
        eigen = grant(app, gid, gast_id, "pruefen")["id"]
        assert gast.delete(f"/api/material/freigaben/{eigen}", headers=H).status_code == 200
        assert grant(app, gid, gast_id, "pruefen") is None
        # Fremde Zeilen, die weiter reichen, bleiben gesperrt (Nr. 4).
        fremd = grant(app, gid, k["wart_id"], "verwalten")["id"]
        assert gast.delete(f"/api/material/freigaben/{fremd}", headers=H).status_code == 403
    print("Eigene Freigabe länger als das eigene Verwalten bestanden.")


# --- Notiz: nie geerbt, nie unter „Meine Freigaben“ --------------------------------------------------------------

def test_notiz_geerbt_und_meine():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        helfer, helfer_id = neues_konto(app, "helfer@example.org", name="Helfer Test")
        assert erteilen(w, gid, user_id=helfer_id, grundrecht="lesen", notiz="Testnotiz oben").status_code == 201
        lw, lw_id = neues_konto(app, "lagerwart@example.org", name="Lagerwart Test")
        freigeben(adm, lager, lw_id, "verwalten")
        d = liste(lw, lager)
        oben = [x for x in d["geerbt"] if x["konto"]["id"] == helfer_id][0]
        assert "notiz" not in oben and not oben["aenderbar"] and oben["ordner"]["pfad"] == "OG Musterstadt", oben
        assert all("notiz" not in x for x in d["geerbt"])
        assert all("notiz" in x for x in d["direkt"]) and d["direkt"][0]["konto"]["id"] == lw_id
        # Auch wer oben verwaltet, sieht in der Liste des Unterordners keine Notiz geerbter Zeilen – dafür „aenderbar“.
        oben_w = [x for x in liste(w, lager)["geerbt"] if x["konto"]["id"] == helfer_id][0]
        assert "notiz" not in oben_w and oben_w["aenderbar"]
        assert [x for x in liste(w, gid)["direkt"] if x["konto"]["id"] == helfer_id][0]["notiz"] == "Testnotiz oben"
        # Unter „Meine Freigaben“ nie – dafür Pfad, Zustand und wer verlängern kann.
        r = helfer.get("/api/material/freigaben/meine")
        assert r.status_code == 200 and "Testnotiz" not in r.get_data(as_text=True), r.get_json()
        m = r.json["freigaben"]
        assert len(m) == 1 and set(m[0]) == {"id", "ordner", "recht", "bis", "gueltig", "wirkt", "wirkt_nicht", "grundrecht_dort",
                                             "laeuft_ab_in_tagen", "verwalter"}, m
        assert m[0]["ordner"]["pfad"] == "OG Musterstadt" and m[0]["verwalter"] == ["wart"] and m[0]["wirkt"]
        assert r.json["zugang"] and not r.json["alles"]
        # Die Verwaltung sieht sie in der Nutzerverwaltung.
        r = adm.get("/api/material/freigaben", query_string={"user_id": helfer_id})
        assert r.status_code == 200 and r.json["freigaben"][0]["notiz"] == "Testnotiz oben", r.get_json()
    print("Notiz geerbt und unter Meine Freigaben bestanden.")


# --- Listen und Verlängern ------------------------------------------------------------------------------------------

def test_listen_und_verlaengern():
    from app.material.services.interval import plus_monate
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        fach = ordner_neu(w, lager, "Fach")
        konten = {}
        for n, felder in (("frisch", {"urkundennummer": "1012-0101"}), ("alt", {"urkundennummer": "1012-0102"}),
                          ("uralt", {"urkundennummer": "1012-0103"}), ("ohne", {}), ("lang", {"urkundennummer": "1012-0104"}),
                          ("weg", {"urkundennummer": "1012-0105"})):
            konten[n] = neues_konto(app, f"{n}@example.org", name=f"Prüfer {n}", mat_pruefer=True, **felder)[1]
        freigeben(adm, gid, k["pruefer_id"], "pruefen", bis=tag(10))           # gilt, läuft bald ab
        freigeben(adm, lager, konten["alt"], "pruefen", bis=tag(-30))           # seit 30 Tagen abgelaufen
        freigeben(adm, lager, konten["uralt"], "pruefen", bis=tag(-100))        # zu lange her – bleibt außen vor
        freigeben(adm, fach, konten["ohne"], "pruefen", bis=tag(5))             # Urkundennummer fehlt
        lang = plus_monate(_heute(), 24)
        freigeben(adm, fach, konten["lang"], "pruefen", bis=lang)                # läuft schon so lange wie möglich
        freigeben(adm, fach, konten["weg"], "pruefen", bis=tag(15))             # Konto deaktiviert
        freigeben(adm, lager, konten["frisch"], "lesen")
        assert adm.put(f"/api/admin/users/{konten['weg']}", json={"active": False}).status_code == 200

        d = liste(w, lager)
        assert set(d) == {"ordner", "anker_wahl", "anker_vorgabe", "direkt", "geerbt", "unten", "verlauf", "laeuft_ab",
                          "grenzen", "alles", "kette"}, set(d)
        assert d["ordner"] == {"id": lager, "name": "Lager", "pfad": "OG Musterstadt / Lager", "gliederung": False}
        assert [a["id"] for a in d["anker_wahl"]] == [lager, gid] and d["anker_vorgabe"] == gid
        assert all(a["ende"] is None for a in d["anker_wahl"])
        assert {x["ordner"]["id"] for x in d["direkt"]} == {lager} and {x["ordner"]["id"] for x in d["geerbt"]} == {gid}
        assert {x["ordner"]["id"] for x in d["unten"]} == {fach} and len(d["unten"]) == 3
        for x in d["direkt"] + d["geerbt"] + d["unten"]:
            assert set(x) - {"notiz"} == EINTRAG and set(x["konto"]) == KONTO, x
        zeile = {x["konto"]["id"]: x for x in d["direkt"] + d["unten"]}
        assert not zeile[konten["alt"]]["gueltig"] and not zeile[konten["alt"]]["wirkt"]
        assert zeile[konten["ohne"]]["gueltig"] and not zeile[konten["ohne"]]["wirkt"]
        assert not zeile[konten["ohne"]]["konto"]["qualifiziert"] and zeile[konten["ohne"]]["konto"]["haekchen"]
        assert not zeile[konten["weg"]]["konto"]["aktiv"] and not zeile[konten["weg"]]["wirkt"]
        assert zeile[konten["ohne"]]["laeuft_ab_in_tagen"] == 5 and zeile[konten["lang"]]["laeuft_ab_in_tagen"] is None
        assert d["laeuft_ab"] == 2                                       # ohne (5 Tage) und weg (15 Tage) im Zweig
        assert liste(w, gid)["laeuft_ab"] == 3                           # dazu der Prüfer an der Gliederung
        assert d["grenzen"]["vorgabe_bis"] == min(f"{_heute().year + 1}-12-31", d["grenzen"]["pruefen_max"])
        # Wer nur das Lager verwaltet, wählt nur das Lager als Anker – Vorgabe ist dann der Ordner selbst.
        lw, lw_id = neues_konto(app, "lagerwart@example.org", name="Lagerwart Test")
        freigeben(adm, lager, lw_id, "verwalten", bis=tag(400))
        dl = liste(lw, lager)
        assert [(a["id"], a["ende"]) for a in dl["anker_wahl"]] == [(lager, tag(400))] and dl["anker_vorgabe"] == lager
        assert not [x for x in dl["geerbt"] if x["aenderbar"]]

        # Verlängern: alle Prüffreigaben im Zweig der Gliederung – gültige und seit höchstens 90 Tagen abgelaufene.
        bis = d["grenzen"]["vorgabe_bis"]

        def eintraege():
            return {e["id"]: e for f in (gid, lager, fach) for e in journal(app, f)}
        vorher = set(eintraege())
        r = w.post(f"{FR.format(gid)}/verlaengern", json={"bis": bis})
        assert r.status_code == 200, r.get_json()
        assert r.json["verlaengert"] == 2, r.get_json()
        assert grant(app, gid, k["pruefer_id"], "pruefen")["valid_until"] == bis
        assert grant(app, lager, konten["alt"], "pruefen")["valid_until"] == bis
        assert grant(app, lager, konten["uralt"], "pruefen")["valid_until"] == tag(-100)
        gruende = {u["konto"]: u["grund"] for u in r.json["uebersprungen"]}
        assert gruende == {"Prüfer ohne": "Qualifikation fehlt", "Prüfer lang": f"läuft schon bis {lang.strftime('%d.%m.%Y')}",
                           "Prüfer weg": "Konto deaktiviert"}, gruende
        assert all(u["ordner"] == "OG Musterstadt / Lager / Fach" for u in r.json["uebersprungen"])
        neu = [e for i, e in eintraege().items() if i not in vorher]
        assert len(neu) == 2 and {e["action"] for e in neu} == {"freigabe_geaendert"}
        assert all(e["nachher"]["bis"] == bis and e["nachher"]["grund"] == "alle verlängert" for e in neu)
        # Eingaben: ohne Datum, über 24 Monate.
        assert w.post(f"{FR.format(gid)}/verlaengern", json={}).status_code == 400
        assert w.post(f"{FR.format(gid)}/verlaengern", json={"bis": tag(800)}).status_code == 400
        # Der befristete Lagerwart: nicht über sein eigenes Ende; was weiter reicht als er, überspringt er.
        assert lw.post(f"{FR.format(lager)}/verlaengern", json={"bis": tag(401)}).status_code == 403
        freigeben(adm, lager, konten["alt"], "pruefen", bis=tag(500))
        freigeben(adm, lager, konten["frisch"], "pruefen", bis=tag(20))
        r = lw.post(f"{FR.format(lager)}/verlaengern", json={"bis": tag(390)})
        assert r.status_code == 200 and r.json["verlaengert"] == 1, r.get_json()      # nur „frisch“
        assert grant(app, lager, konten["frisch"], "pruefen")["valid_until"] == tag(390)
        gruende = {u["konto"]: u["grund"] for u in r.json["uebersprungen"]}
        assert gruende["Prüfer lang"] == gruende["Prüfer alt"] == "reicht weiter als deine eigene Freigabe", gruende

        # Ein Konto ohne Namen (etwa aus der Migration, die Freigaben unabhängig vom Namen vergibt): Die Liste nennt es
        # „(Konto ohne Namen)“ – nie mit E-Mail – und die Zeile wirkt nicht.
        ohne_name = adm.post("/api/admin/users", json={"email": "ohne-name@example.org", "password": "passwort1",
                                                       "rechte": {"material": 0}}).json["user"]["id"]
        freigeben(adm, fach, ohne_name, "lesen")
        x = [x for x in liste(w, lager)["unten"] if x["konto"]["id"] == ohne_name][0]
        assert x["konto"]["name"] == "(Konto ohne Namen)" and not x["wirkt"] and x["wirkt_nicht"] == "Konto ohne Namen", x
        assert "ohne-name@example.org" not in w.get(FR.format(lager)).get_data(as_text=True)
    print("Listen und Verlängern bestanden.")


# --- Prüffreigaben dauerhaft mit Grundrecht, befristet nur für externe (Nachbesserung vom 18.10.2026) ---------------

def test_dauerhaft_pruefen():
    """1.6 Nr. 8 neu: Eine Prüffreigabe darf dauerhaft sein, wo die Person am Anker oder darüber ein Grundrecht hat –
    auch eins aus derselben Anfrage (Vorlagen) oder geerbt von oben; ohne (externer Prüfer) 400 mit Klartext. Mit Ende
    höchstens 24 Monate, dauerhaft nur, wer selbst dauerhaft verwaltet (Nr. 3). Zur Laufzeit wirkt eine dauerhafte nur
    mit gültigem Grundrecht am Anker oder darüber: entzogen oder abgelaufen – kein Prüfrecht, keine Prüfsicht (auch
    nicht in einem Unterordner mit eigenem Grundrecht), „wirkt nicht“ in der Liste; wieder erteilt – wirkt wieder.
    „Alle verlängern“ übergeht dauerhafte; Entziehen und Kürzen eines Grundrechts sagen vorher, welche dauerhafte daran
    hängt (traegt_pruefen), und das Entziehen zählt die offenen Prüfungen mit."""
    from app.material.services import rechte
    from app.material.services.interval import plus_monate
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        fach = ordner_neu(w, lager, "Fach")
        artikel = neuer_artikel(w, ids["hms"], fach)["id"]

        def konto(name, nummer):
            return neues_konto(app, f"{name}@example.org", name=f"Prüfer {name}", mat_pruefer=True,
                               urkundennummer=nummer)

        def sicht(uid):
            with app.app_context():
                from app import db
                return rechte.sicht(db.query("SELECT * FROM users WHERE id = ?", (uid,), one=True))

        def zeile_von(fid, uid, recht="pruefen", art="direkt"):
            return [x for x in liste(w, fid)[art] if x["konto"]["id"] == uid and x["recht"] == recht][0]

        # Vorlage „Prüfer“ (lesen und prüfen) und „Materialwart und Prüfer“: dauerhaft in einem Schritt – das
        # Grundrecht aus derselben Anfrage zählt.
        eins, eins_id = konto("eins", "1012-5001")
        r = erteilen(w, gid, user_id=eins_id, grundrecht="lesen", pruefen=True, pruefen_bis=None)
        assert r.status_code == 201 and [(f["recht"], f["bis"], f["wirkt"]) for f in r.json["freigaben"]] == [
            ("lesen", None, True), ("pruefen", None, True)], r.get_json()
        assert sicht(eins_id).darf("pruefen", fach) and sicht(eins_id).ende("pruefen", fach) is None
        assert journal(app, gid)[-1]["nachher"]["bis"] is None
        zwei, zwei_id = konto("zwei", "1012-5002")
        r = erteilen(w, lager, user_id=zwei_id, grundrecht="verwalten", pruefen=True)
        assert r.status_code == 201 and grant(app, lager, zwei_id, "pruefen")["valid_until"] is None, r.get_json()
        # „Einzeln“: nur die Prüffreigabe, das Grundrecht geerbt von oben (lesen an der Gliederung, prüfen am Lager).
        drei, drei_id = konto("drei", "1012-5003")
        assert erteilen(w, gid, user_id=drei_id, grundrecht="lesen").status_code == 201
        r = erteilen(w, lager, user_id=drei_id, pruefen=True)
        assert r.status_code == 201 and r.json["freigaben"][0]["grundrecht_dort"], r.get_json()
        assert sicht(drei_id).darf("pruefen", fach)

        # Ohne Grundrecht am Anker oder darüber – der externe Prüfer – 400, nichts geschrieben; auch ein Grundrecht nur
        # weiter unten zählt nicht.
        ext, ext_id = konto("extern", "1012-8001")
        vorher = len(journal(app, lager))
        for d in ({"pruefen": True}, {"pruefen": True, "pruefen_bis": ""}, {"pruefen_bis": ""}):
            r = erteilen(w, lager, user_id=ext_id, **d)
            assert r.status_code == 400 and "nur zusammen mit lesen oder verwalten" in r.json["error"], (d, r.get_json())
            assert "externe Prüfer" in r.json["error"] and "24 Monate" in r.json["error"]
        assert grant(app, lager, ext_id, "pruefen") is None and len(journal(app, lager)) == vorher
        assert erteilen(w, fach, user_id=ext_id, grundrecht="lesen").status_code == 201
        assert erteilen(w, lager, user_id=ext_id, pruefen=True).status_code == 400
        assert erteilen(w, lager, user_id=ext_id, pruefen=True, pruefen_bis=tag(60)).status_code == 201
        # „pruefen“: false heißt keine Prüffreigabe, auch mit Datum; Unsinn 400.
        assert erteilen(w, lager, user_id=eins_id, pruefen=False, pruefen_bis=tag(5)).status_code == 400   # nichts
        assert erteilen(w, lager, user_id=eins_id, pruefen="vielleicht").status_code == 400
        assert grant(app, lager, eins_id, "pruefen") is None
        # Befristet höchstens 24 Monate – auch mit Grundrecht.
        grenze = plus_monate(_heute(), 24)
        r = erteilen(w, gid, user_id=eins_id, pruefen=True, pruefen_bis=(grenze + timedelta(days=1)).isoformat())
        assert r.status_code == 400 and "24 Monate" in r.json["error"], r.get_json()
        assert grant(app, gid, eins_id, "pruefen")["valid_until"] is None

        # Ein befristeter Verwalter vergibt nichts Dauerhaftes (Nr. 3) – auch keine Prüffreigabe mit Grundrecht.
        gast, gast_id = neues_konto(app, "gast@example.org", name="Gast Test")
        freigeben(adm, gid, gast_id, "verwalten", bis=tag(80))
        vier, vier_id = konto("vier", "1012-5004")
        freigeben(adm, gid, vier_id, "lesen", bis=tag(200))
        r = erteilen(gast, lager, user_id=vier_id, pruefen=True)
        assert r.status_code == 403 and "Dauerhaft vergibt nur" in r.json["error"], r.get_json()
        assert erteilen(gast, lager, user_id=vier_id, pruefen=True, pruefen_bis=tag(60)).status_code == 201
        # Ändern: befristet → dauerhaft mit Grundrecht (Dauer dann so lang wie das Grundrecht), zurück auf ein Datum.
        pv = grant(app, lager, vier_id, "pruefen")["id"]
        assert gast.put(f"/api/material/freigaben/{pv}", json={"bis": None}).status_code == 403
        r = w.put(f"/api/material/freigaben/{pv}", json={"bis": None})
        assert r.status_code == 200 and r.json["freigabe"]["bis"] is None and r.json["freigabe"]["wirkt"], r.get_json()
        assert sicht(vier_id).ende("pruefen", fach) == tag(200)              # endet mit dem Grundrecht
        assert w.put(f"/api/material/freigaben/{pv}", json={"bis": tag(100)}).status_code == 200
        assert w.put(f"/api/material/freigaben/{pv}", json={"bis": None}).status_code == 200
        pe = grant(app, lager, ext_id, "pruefen")["id"]
        r = w.put(f"/api/material/freigaben/{pe}", json={"bis": None})
        assert r.status_code == 400 and "nur zusammen mit lesen oder verwalten" in r.json["error"], r.get_json()
        # Aus einem Grundrecht wird eine Prüffreigabe nur mit ausdrücklichem „bis“; dauerhaft nur, wenn danach noch ein
        # Grundrecht bleibt.
        fuenf, fuenf_id = konto("fuenf", "1012-5005")
        assert erteilen(w, fach, user_id=fuenf_id, grundrecht="lesen").status_code == 201
        g5 = grant(app, fach, fuenf_id, "lesen")["id"]
        r = w.put(f"/api/material/freigaben/{g5}", json={"recht": "pruefen"})
        assert r.status_code == 400 and "„bis“" in r.json["error"], r.get_json()
        r = w.put(f"/api/material/freigaben/{g5}", json={"recht": "pruefen", "bis": None})
        assert r.status_code == 400 and "nur zusammen mit" in r.json["error"], r.get_json()
        assert grant(app, fach, fuenf_id, "lesen")["id"] == g5
        assert w.put(f"/api/material/freigaben/{g5}", json={"recht": "pruefen", "bis": tag(30)}).status_code == 200

        # Die Plattform-Verwaltung hat das Grundrecht überall – auch ohne Zeile dauerhaft.
        a_id = adm_id(adm)
        assert adm.put(f"/api/admin/users/{a_id}", json={"mat_pruefer": True, "urkundennummer": "1012-0099"}).status_code == 200
        r = erteilen(adm, lager, user_id=a_id, pruefen=True)
        assert r.status_code == 201 and r.json["freigaben"][0]["wirkt"], r.get_json()
        assert sicht(a_id).darf("pruefen", fach)

        # Zur Laufzeit: Wer das Grundrecht verliert, prüft nicht mehr – keine Prüfsicht, „wirkt nicht“; wieder erteilt,
        # wirkt es wieder. Entziehen und Kürzen sagen vorher, was daran hängt.
        g3 = grant(app, gid, drei_id, "lesen")["id"]
        oben = zeile_von(gid, drei_id, "lesen")
        assert oben["traegt_pruefen"] == 1 and zeile_von(lager, drei_id)["grundrecht_dort"], oben
        assert zeile_von(gid, eins_id, "lesen")["traegt_pruefen"] == 1             # trägt ihre Prüffreigabe an der Gliederung
        assert zeile_von(gid, k["pruefer_id"], "lesen")["traegt_pruefen"] == 0     # dessen Prüffreigabe ist befristet
        assert drei.get(f"/api/material/ordner/{fach}").status_code == 200
        r = w.delete(f"/api/material/freigaben/{g3}", headers=H)
        assert r.status_code == 200 and r.json["offene_entwuerfe"] == 0, r.get_json()
        assert not sicht(drei_id).darf("pruefen", lager) and not sicht(drei_id).menge("pruefen")
        assert drei.get(f"/api/material/ordner/{fach}").status_code == 404
        z = zeile_von(lager, drei_id)
        assert (z["bis"], z["gueltig"], z["wirkt"], z["grundrecht_dort"]) == (None, True, False, False), z
        m = drei.get("/api/material/freigaben/meine").json["freigaben"]
        assert [(x["recht"], x["wirkt"], x["grundrecht_dort"], x["laeuft_ab_in_tagen"]) for x in m] == [
            ("pruefen", False, False, None)], m
        assert erteilen(w, gid, user_id=drei_id, grundrecht="lesen").status_code == 201
        assert sicht(drei_id).darf("pruefen", fach) and zeile_von(lager, drei_id)["wirkt"]
        # Abgelaufen wie entzogen; zwei Grundrechte tragen gemeinsam – keins allein.
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE folder_id = ? AND user_id = ? AND permission = 'lesen'",
            (tag(-1), gid, drei_id))
        assert not sicht(drei_id).darf("pruefen", fach) and not zeile_von(lager, drei_id)["wirkt"]
        sql(app, "UPDATE mat_folder_grant SET valid_until = NULL WHERE folder_id = ? AND user_id = ? AND permission = 'lesen'",
            (gid, drei_id))
        assert erteilen(w, lager, user_id=drei_id, grundrecht="lesen").status_code == 201
        assert zeile_von(gid, drei_id, "lesen")["traegt_pruefen"] == 0 == zeile_von(lager, drei_id, "lesen")["traegt_pruefen"]
        # Ein Grundrecht nur weiter unten trägt eine dauerhafte Prüffreigabe auch zur Laufzeit nicht – wie Schreibregel
        # und Liste: Oben entzogen, unten behalten, prüft die Person auch im Unterordner nicht mehr.
        sechs, sechs_id = konto("sechs", "1012-5006")
        assert erteilen(w, gid, user_id=sechs_id, grundrecht="lesen", pruefen=True).status_code == 201
        assert erteilen(w, fach, user_id=sechs_id, grundrecht="lesen").status_code == 201
        assert zeile_von(gid, sechs_id, "lesen")["traegt_pruefen"] == 1
        assert zeile_von(fach, sechs_id, "lesen")["traegt_pruefen"] == 0                # das untere trägt sie nicht
        r = w.delete(f"/api/material/freigaben/{grant(app, gid, sechs_id, 'lesen')['id']}", headers=H)
        assert r.status_code == 200 and r.json["offene_entwuerfe"] == 0, r.get_json()
        assert not sicht(sechs_id).darf("pruefen", fach) and not sicht(sechs_id).menge("pruefen")
        assert sicht(sechs_id).darf("lesen", fach) and sechs.get(f"/api/material/ordner/{fach}").status_code == 200
        z = zeile_von(gid, sechs_id)
        assert (z["bis"], z["wirkt"], z["grundrecht_dort"]) == (None, False, False), z
        assert [(x["recht"], x["wirkt"]) for x in sechs.get("/api/material/freigaben/meine").json["freigaben"]] == [
            ("pruefen", False), ("lesen", True)]
        r = starten(sechs, artikel)
        assert r.status_code == 403 and r.json["error"] == rechte.KEINE_PRUEFFREIGABE, r.get_json()
        assert erteilen(w, gid, user_id=sechs_id, grundrecht="lesen").status_code == 201        # wieder erteilt
        assert sicht(sechs_id).darf("pruefen", fach) and sicht(sechs_id).ende("pruefen", fach) is None

        # „Alle Prüffreigaben verlängern“ übergeht dauerhafte – nicht einmal unter „übersprungen“; ablaufen tun sie nie.
        dauerhaft = {x["id"] for x in zeilen(app, "SELECT id FROM mat_folder_grant WHERE permission = 'pruefen' "
                                                  "AND valid_until IS NULL")}
        r = w.post(f"{FR.format(gid)}/verlaengern", json={"bis": liste(w, gid)["grenzen"]["vorgabe_bis"]})
        assert r.status_code == 200 and r.json["verlaengert"] >= 1, r.get_json()
        namen = {u["konto"] for u in r.json["uebersprungen"]}
        assert not namen & {"Prüfer eins", "Prüfer zwei", "Prüfer drei", "Prüfer vier"}, namen
        assert {x["id"] for x in zeilen(app, "SELECT id FROM mat_folder_grant WHERE permission = 'pruefen' "
                                             "AND valid_until IS NULL")} == dauerhaft
        assert all(x["laeuft_ab_in_tagen"] is None for x in liste(w, gid)["unten"] + liste(w, gid)["direkt"]
                   if x["bis"] is None)
        assert w.post(f"{FR.format(gid)}/verlaengern", json={"bis": None}).status_code == 400

        # Entzieht man das Grundrecht, an dem eine dauerhafte Prüffreigabe hängt, zählen offene Prüfungen mit.
        pz = grant(app, gid, k["pruefer_id"], "pruefen")["id"]
        assert w.put(f"/api/material/freigaben/{pz}", json={"bis": None}).status_code == 200
        assert starten(k["pruefer"], artikel).status_code == 201
        r = w.delete(f"/api/material/freigaben/{grant(app, gid, k['pruefer_id'], 'lesen')['id']}", headers=H)
        assert r.status_code == 200 and r.json["offene_entwuerfe"] == 1, r.get_json()
    print("Prüffreigaben dauerhaft mit Grundrecht bestanden.")


# --- Entziehen mit offenen Entwürfen --------------------------------------------------------------------------------

def test_entziehen_offene_entwuerfe():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        ids = katalog_grund(adm)
        pruef_formulare(k["katalog"], ids)
        gid, _ = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        a = neuer_artikel(w, ids["hms"], lager)["id"]
        assert starten(k["pruefer"], a).status_code == 201
        lesen = grant(app, gid, k["pruefer_id"], "lesen")["id"]
        pruefen = grant(app, gid, k["pruefer_id"], "pruefen")["id"]
        r = w.delete(f"/api/material/freigaben/{lesen}", headers=H)
        assert r.status_code == 200 and r.json["offene_entwuerfe"] == 0, r.get_json()   # prüfen darf er noch
        r = w.delete(f"/api/material/freigaben/{pruefen}", headers=H)
        assert r.status_code == 200 and r.json["offene_entwuerfe"] == 1, r.get_json()
        # Der Entwurf bleibt – der Materialwart gibt ihn frei.
        assert zeilen(app, "SELECT 1 FROM mat_inspection WHERE item_id = ? AND completed_at IS NULL", (a,))
    print("Entziehen mit offenen Entwürfen bestanden.")


# --- Nutzersuche ----------------------------------------------------------------------------------------------------

def test_nutzersuche():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gliederung(adm)
        for n in range(25):
            assert adm.post("/api/admin/users", json={"email": f"tp{n}@example.org", "password": "passwort1",
                                                      "name": f"Testperson {n:02d}", "gliederung": "OG Test"}).status_code == 201
        inaktiv = adm.post("/api/admin/users", json={"email": "ti@example.org", "password": "passwort1",
                                                     "name": "Testperson Inaktiv"}).json["user"]["id"]
        assert adm.put(f"/api/admin/users/{inaktiv}", json={"active": False}).status_code == 200
        adm.post("/api/admin/users", json={"email": "Testperson@example.org", "password": "passwort1",
                                           "rechte": {"material": 0}})                                     # ohne Namen
        neues_konto(app, "joerg@example.org", name="Jörg Prüfmann", mat_pruefer=True, urkundennummer="1012-7001")

        r = w.get("/api/material/nutzer", query_string={"q": "Testperson"})
        assert r.status_code == 200 and len(r.json["nutzer"]) == 20 and r.json["mehr"], r.get_json()
        assert all(set(x) == {"id", "name", "gliederung", "qualifiziert", "grundrecht_ueberall"} for x in r.json["nutzer"])
        assert "@" not in r.get_data(as_text=True) and "Inaktiv" not in r.get_data(as_text=True)
        assert r.json["nutzer"][0] == {"id": r.json["nutzer"][0]["id"], "name": "Testperson 00", "gliederung": "OG Test",
                                       "qualifiziert": False, "grundrecht_ueberall": False}
        r = w.get("/api/material/nutzer", query_string={"q": "person 2"})
        assert [x["name"] for x in r.json["nutzer"]] == [f"Testperson {n}" for n in range(20, 25)] and not r.json["mehr"]
        # Groß und klein egal, auch bei Umlauten; qualifiziert sagt, ob Prüfvorlagen gehen. Keine Urkundennummer.
        r = w.get("/api/material/nutzer", query_string={"q": "PRÜFM"})
        assert [(x["name"], x["qualifiziert"]) for x in r.json["nutzer"]] == [("Jörg Prüfmann", True)], r.get_json()
        assert "1012-7001" not in r.get_data(as_text=True)
        # Die Material-Verwaltung (Plattform-Verwaltung eingeschlossen) hat das Grundrecht überall – der Reiter bietet
        # ihr beim Prüfen „dauerhaft“ auch ohne lesen oder verwalten an, wie der Dienst es annimmt (grundrecht_an).
        r = w.get("/api/material/nutzer", query_string={"q": "Administrator"})
        assert [(x["name"], x["grundrecht_ueberall"]) for x in r.json["nutzer"]] == [("Administrator", True)], r.get_json()
        r = w.get("/api/material/nutzer", query_string={"q": "katalog"})
        assert [(x["name"], x["grundrecht_ueberall"]) for x in r.json["nutzer"]] == [("katalog", True)], r.get_json()
        # Unter 3 Zeichen 400; Führungskraft 403; Material-Verwaltung und Plattform-Verwaltung dürfen; ohne Anmeldung 401.
        for q in ("Te", " T ", "", None):
            r = w.get("/api/material/nutzer", query_string={"q": q} if q is not None else None)
            assert r.status_code == 400 and "3 Zeichen" in r.json["error"], (q, r.get_json())
        assert k["fuehrung"].get("/api/material/nutzer", query_string={"q": "Test"}).status_code == 403
        assert k["katalog"].get("/api/material/nutzer", query_string={"q": "Test"}).status_code == 200
        assert adm.get("/api/material/nutzer", query_string={"q": "Test"}).status_code == 200
        assert app.test_client().get("/api/material/nutzer", query_string={"q": "Test"}).status_code == 401

        # Zweck: Für Freigaben (Vorgabe) nur Konten mit Zugang zum Modul, für die Zuordnung alle aktiven mit Namen.
        stufenlos = neues_konto(app, "tp-ohne@example.org", name="Testperson ohne Stufe", stufe=0)[1]
        haekchen = neues_konto(app, "tp-haken@example.org", name="Testperson Häkchen", stufe=0, mat_pruefer=True,
                               urkundennummer="1012-7002")[1]
        for zweck in (None, "freigabe"):
            q = {"q": "Testperson", **({"zweck": zweck} if zweck else {})}
            namen = {x["name"] for x in w.get("/api/material/nutzer", query_string=dict(q, q="ohne Stufe")).json["nutzer"]}
            assert namen == set(), (zweck, namen)
            assert w.get("/api/material/nutzer", query_string=dict(q, q="Häkchen")).json["nutzer"] == []
        r = w.get("/api/material/nutzer", query_string={"q": "ohne Stufe", "zweck": "zuordnung"})
        assert [x["id"] for x in r.json["nutzer"]] == [stufenlos], r.get_json()
        # Das Häkchen ohne Stufe wirkt nicht: nicht qualifiziert.
        r = w.get("/api/material/nutzer", query_string={"q": "Häkchen", "zweck": "zuordnung"})
        assert [(x["id"], x["qualifiziert"]) for x in r.json["nutzer"]] == [(haekchen, False)], r.get_json()
        assert w.get("/api/material/nutzer", query_string={"q": "Testperson", "zweck": "irgendwas"}).status_code == 400

        # Der Kontoverweis löst sich zum Namen auf – ohne Namen „(ohne Namen)“, nie zur E-Mail.
        ohne = adm.post("/api/admin/users", json={"email": "ohne@example.org", "password": "passwort1",
                                                  "rechte": {"material": 0}}).json["user"]["id"]
        with app.app_context():
            from app.material.services import journal as mj
            assert mj.konto_name(mj.konto_ref(ohne)["ref"]) == "(ohne Namen)"
            assert mj.konto_name(mj.konto_ref(k["wart_id"])["ref"]) == "wart"
            assert mj.konto_name("0" * 32) == "(gelöschtes Konto)"
    print("Nutzersuche bestanden.")


# --- „Meine Freigaben“ ohne Modulzugang ------------------------------------------------------------------------------

def test_meine_ohne_zugang():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        gid, _ = gliederung(adm)
        r = k["nutzer"].get("/api/material/freigaben/meine")
        assert r.status_code == 200 and r.json == {"freigaben": [], "alles": False, "qualifiziert": False,
                                                   "zugang": False}, r.get_json()
        assert app.test_client().get("/api/material/freigaben/meine").status_code == 401
        # Eine vor 100 Tagen abgelaufene Freigabe steht da (mit dem Verwalter, der verlängern kann), eine vor 400 nicht.
        freigeben(adm, gid, k["nutzer_id"], "lesen", bis=tag(-100))
        lager = ordner_neu(k["wart"], gid, "Lager")
        freigeben(adm, lager, k["nutzer_id"], "pruefen", bis=tag(-400))
        assert k["nutzer"].get("/api/material/start").status_code == 403
        m = k["nutzer"].get("/api/material/freigaben/meine").json["freigaben"]
        assert [(x["ordner"]["id"], x["gueltig"], x["bis"], x["verwalter"], x["wirkt_nicht"]) for x in m] == [
            (gid, False, tag(-100), ["wart"], None)], m
        # Eine gültige Freigabe ohne Stufe im Modul wirkt nicht – und sagt warum.
        freigeben(adm, lager, k["nutzer_id"], "lesen")
        assert k["nutzer"].get("/api/material/start").status_code == 403
        x = [x for x in k["nutzer"].get("/api/material/freigaben/meine").json["freigaben"] if x["gueltig"]][0]
        assert (x["wirkt"], x["wirkt_nicht"]) == (False, "kein Zugang zum Modul Material"), x
        z = [f for f in adm.get("/api/material/freigaben", query_string={"user_id": k["nutzer_id"]}).json["freigaben"]
             if f["gueltig"]][0]
        assert (z["wirkt"], z["wirkt_nicht"], z["konto"]["zugang"]) == (False, "kein Zugang zum Modul Material", False), z
        sql(app, "DELETE FROM mat_folder_grant WHERE folder_id = ? AND user_id = ? AND permission = 'lesen'",
            (lager, k["nutzer_id"]))
        # Höchstens drei Verwalter, nach Namen.
        for n in "bcde":
            freigeben(adm, gid, neues_konto(app, f"w{n}@example.org", name=f"Verwalter {n}")[1], "verwalten")
        assert k["nutzer"].get("/api/material/freigaben/meine").json["freigaben"][0]["verwalter"] == [
            "Verwalter b", "Verwalter c", "Verwalter d"]
        assert adm.get("/api/material/freigaben/meine").json["alles"]
        assert k["katalog"].get("/api/material/freigaben/meine").json["alles"]          # Material-Verwaltung
        assert not k["wart"].get("/api/material/freigaben/meine").json["alles"]
    print("Meine Freigaben ohne Modulzugang bestanden.")


# --- Nutzerverwaltung -----------------------------------------------------------------------------------------------

def test_nutzerverwaltung():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        gid, _ = gliederung(adm)
        # Freigaben eines Kontos: nur die Verwaltung; unbekannt 404, Unsinn 400.
        r = adm.get("/api/material/freigaben", query_string={"user_id": k["pruefer_id"]})
        assert r.status_code == 200 and sorted(f["recht"] for f in r.json["freigaben"]) == ["lesen", "pruefen"], r.get_json()
        assert all("notiz" in f and f["aenderbar"] for f in r.json["freigaben"])
        assert adm.get("/api/material/freigaben", query_string={"user_id": 999999}).status_code == 404
        assert adm.get("/api/material/freigaben", query_string={"user_id": "x"}).status_code == 400
        assert adm.get("/api/material/freigaben").status_code == 400
        for c in (k["wart"], k["fuehrung"], k["nutzer"]):
            assert c.get("/api/material/freigaben", query_string={"user_id": k["pruefer_id"]}).status_code == 403
        # Ein Konto aus Phase 1 – Migration und vergeben von „Migration“ (kein Konto).
        sql(app, "UPDATE users SET recht_material = 1 WHERE id = ?", (k["nutzer_id"],))
        z = freigeben(adm, gid, k["nutzer_id"], "lesen")
        sql(app, "UPDATE mat_folder_grant SET granted_by = NULL WHERE id = ?", (z,))
        sql(app, "INSERT INTO mat_audit (entity, entity_id, user_id, user_name, action, after_json, created_at) VALUES "
                 "('folder', ?, NULL, 'Migration Schritt 8', 'freigabe_erteilt', ?, '2026-10-18T00:00:00+00:00')",
            (gid, json.dumps({"freigabe": z, "recht": "lesen"})))
        assert adm.get("/api/material/freigaben", query_string={"user_id": k["nutzer_id"]}).json["freigaben"][0][
            "vergeben_von"] == "Migration"

        # list_users: Zahl gültiger Freigaben; Material ist die gespeicherte Stufe (die Plattform-Verwaltung hat 2).
        sql(app, "UPDATE mat_folder_grant SET valid_until = ? WHERE id = ?", (tag(-1), z))
        nutzer = {u["id"]: u for u in adm.get("/api/admin/users").json["users"]}
        assert (nutzer[k["nutzer_id"]]["mat_freigaben"], nutzer[k["nutzer_id"]]["rechte"]["material"]) == (0, 1)
        assert (nutzer[k["pruefer_id"]]["mat_freigaben"], nutzer[k["pruefer_id"]]["rechte"]["material"]) == (2, 1)
        assert (nutzer[k["wart_id"]]["mat_freigaben"], nutzer[k["wart_id"]]["rechte"]["material"]) == (1, 1)
        assert nutzer[k["katalog_id"]]["rechte"]["material"] == 2 and nutzer[adm_id(adm)]["rechte"]["material"] == 2
        assert all("mat_stufe_alt" not in u and "mat_katalog" not in u for u in nutzer.values())

        # Material wie jedes Modul: 0/1/2 wird gespeichert und gelesen – beim Anlegen wie beim Ändern; Unsinn 400;
        # Verwaltung zieht auf 2.
        r = adm.post("/api/admin/users", json={"email": "neu@example.org", "password": "passwort1", "name": "Neu Test",
                                               "rechte": {"material": 2, "wiki": 2}})
        assert r.status_code == 201 and r.json["user"]["rechte"]["material"] == 2 and r.json["user"]["rechte"]["wiki"] == 2
        neu = r.json["user"]["id"]
        stufe = lambda: zeilen(app, "SELECT recht_material FROM users WHERE id = ?", (neu,))[0]["recht_material"]  # noqa: E731
        assert stufe() == 2
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"material": 1}}).status_code == 200 and stufe() == 1
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"material": "Unsinn"}}).status_code == 400
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"material": 3}}).status_code == 400 and stufe() == 1
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"verwaltung": 2}}).status_code == 200 and stufe() == 2
        # Die Plattform-Verwaltung wieder weg: Material bleibt auf Verwaltung, bis es jemand einzeln senkt.
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"verwaltung": 0}}).status_code == 200 and stufe() == 2
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"material": 1}}).status_code == 200 and stufe() == 1

        # Der Rolleneintrag beim Anlegen trägt keine E-Mail – und die Stufe.
        r = adm.post("/api/admin/users", json={"email": "rolle@example.org", "password": "passwort1", "name": "Rolle Test",
                                               "mat_pruefer": True})
        assert r.status_code == 201, r.get_json()
        e = zeilen(app, "SELECT * FROM mat_audit WHERE entity = 'user' AND entity_id = ?", (r.json["user"]["id"],))
        assert len(e) == 1 and e[0]["action"] == "rollen" and "@" not in e[0]["after_json"], e
        assert json.loads(e[0]["after_json"]) == {"mat_pruefer": 1, "recht_material": 1}
        # Stufe und Häkchen nur mit Namen – beim Anlegen und wenn eines dazukommt oder der Name verschwindet.
        for wunsch in ({"mat_pruefer": True, "rechte": {"material": 0}}, {"rechte": {"material": 1}},
                       {"rechte": {"material": 2}}, {}):
            r = adm.post("/api/admin/users", json=dict({"email": "x@example.org", "password": "passwort1"}, **wunsch))
            assert r.status_code == 400 and "Erst einen Namen eintragen" in r.json["error"], (wunsch, r.get_json())
        # Das Häkchen „Produktkatalogpfleger“ gibt es nicht mehr – auch nicht beim Anlegen.
        r = adm.post("/api/admin/users", json={"email": "x@example.org", "password": "passwort1", "name": "X",
                                               "mat_katalog": False})
        assert r.status_code == 400 and "Produktkatalogpfleger" in r.json["error"], r.get_json()
        ohne = adm.post("/api/admin/users", json={"email": "ohne@example.org", "password": "passwort1",
                                                  "rechte": {"material": 0}}).json["user"]["id"]
        for wunsch in ({"mat_pruefer": True}, {"rechte": {"material": 1}}):
            r = adm.put(f"/api/admin/users/{ohne}", json=wunsch)
            assert r.status_code == 400 and "Erst einen Namen eintragen" in r.json["error"], (wunsch, r.get_json())
        assert adm.put(f"/api/admin/users/{ohne}", json={"rechte": {"material": 1}, "name": "Jetzt mit Namen"}).status_code == 200
        r = adm.put(f"/api/admin/users/{k['pruefer_id']}", json={"name": ""})
        assert r.status_code == 400 and "Erst einen Namen eintragen" in r.json["error"], r.get_json()
        # Plattform-Verwaltung ohne Namen geht (sie hat Material von selbst, die Stufe bringt dort nichts Neues).
        assert adm.put(f"/api/admin/users/{ohne}", json={"name": "", "rechte": {"material": 0}}).status_code == 200
        assert adm.put(f"/api/admin/users/{ohne}", json={"rechte": {"verwaltung": 2}}).status_code == 200
        assert adm.put(f"/api/admin/users/{ohne}", json={"rechte": {"verwaltung": 0}}).status_code == 200
        # Ein namenloses Konto mit Stufe und Häkchen aus der Zeit davor bleibt bearbeitbar – etwa um beides zu nehmen.
        sql(app, "UPDATE users SET name = '', mat_pruefer = 1, recht_material = 1 WHERE id = ?", (neu,))
        assert adm.put(f"/api/admin/users/{neu}", json={"phone": "0000"}).status_code == 200
        assert adm.put(f"/api/admin/users/{neu}", json={"name": "", "mat_pruefer": True,
                                                        "rechte": {"material": 1}}).status_code == 200   # wie der Dialog
        assert adm.put(f"/api/admin/users/{neu}", json={"rechte": {"material": 2}}).status_code == 400
        assert adm.put(f"/api/admin/users/{neu}", json={"mat_pruefer": False, "rechte": {"material": 0}}).status_code == 200
    print("Nutzerverwaltung bestanden.")


def test_list_users_abfragen():
    """list_users: die Zahl der Abfragen hängt nicht an der Zahl der Konten (gruppierte Abfrage für die Freigaben), und
    die Stufe Material ist die gespeicherte (die Plattform-Verwaltung hat 2)."""
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm = k["adm"]
        gid, _ = gliederung(adm)
        abfragen = []
        alt = db_mod.get_db

        def mit_zaehler():
            conn = alt()
            conn.set_trace_callback(abfragen.append)
            return conn

        def zaehlen():
            del abfragen[:]
            db_mod.get_db = mit_zaehler
            try:
                r = adm.get("/api/admin/users")
            finally:
                db_mod.get_db = alt
            assert r.status_code == 200
            return len(abfragen), r.json["users"]

        def konten(von, bis):
            for n in range(von, bis):
                uid = adm.post("/api/admin/users", json={"email": f"k{n}@example.org", "password": "passwort1",
                                                         "name": f"Konto {n}", "rechte": {"material": n % 3}}).json["user"]["id"]
                if n % 2:
                    freigeben(adm, gid, uid, "verwalten" if n % 4 == 1 else "lesen")
        konten(0, 10)
        wenige, _ = zaehlen()
        konten(10, 50)
        viele, users = zaehlen()
        assert len(users) >= 55 and viele == wenige, (wenige, viele)
        with app.app_context():
            from app import db
            for u in users:
                r = db.query("SELECT recht_material, recht_verwaltung FROM users WHERE id = ?", (u["id"],), one=True)
                assert u["rechte"]["material"] == (2 if r["recht_verwaltung"] == 2 else r["recht_material"]), u
    print("list_users: Abfragezahl bestanden.")


def test_liste_abfragen():
    """GET /ordner/<fid>/freigaben: Die Zahl der Abfragen hängt nicht an der Länge des Verlaufs – die Namen hinter den
    Kontoverweisen kommen mit einer Abfrage (journal.konto_namen), nicht je Eintrag."""
    from app import db as db_mod
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        lager = ordner_neu(w, gid, "Lager")
        konten = [neues_konto(app, f"helfer{n}@example.org", name=f"Helfer {n}")[1] for n in range(6)]
        abfragen = []
        alt = db_mod.get_db

        def mit_zaehler():
            conn = alt()
            conn.set_trace_callback(abfragen.append)
            return conn

        def zaehlen():
            del abfragen[:]
            db_mod.get_db = mit_zaehler
            try:
                r = w.get(FR.format(lager))
            finally:
                db_mod.get_db = alt
            assert r.status_code == 200, r.get_json()
            return len(abfragen), r.json["verlauf"]

        assert erteilen(w, lager, user_id=konten[0], grundrecht="lesen").status_code == 201
        wenige, verlauf = zaehlen()
        assert len(verlauf) == 1
        for runde in range(4):
            for uid in konten:
                assert erteilen(w, lager, user_id=uid, grundrecht="lesen", grund_bis=tag(10 + runde)).status_code == 201
        viele, verlauf = zaehlen()
        assert len(verlauf) == 25 and {v["konto"] for v in verlauf} == {f"Helfer {n}" for n in range(6)}, verlauf
        assert viele == wenige, (wenige, viele)
        # Dieselben Namen wie konto_name – auch für unbekannte Verweise und Konten ohne Namen.
        sql(app, "UPDATE users SET name = '' WHERE id = ?", (konten[1],))
        with app.app_context():
            from app.material.services import journal as jn
            refs = [ref(app, uid) for uid in konten[:3]] + ["0" * 32]
            assert jn.konto_namen(refs + [None, ""]) == {r: jn.konto_name(r) for r in refs}
            assert jn.konto_namen(refs)["0" * 32] == "(gelöschtes Konto)" and jn.konto_namen(refs)[refs[1]] == "(ohne Namen)"
    print("Freigabenliste: Abfragezahl bestanden.")


# --- Ordner löschen schreibt „freigabe_entfernt“ (Paket A1) ---------------------------------------------------------

@braucht("A1", _a1_ordner_loeschen)
def test_braucht_a1_ordner_loeschen_journal():
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        fach = ordner_neu(w, gid, "Fach")
        helfer, helfer_id = neues_konto(app, "helfer@example.org", name="Helfer Test")
        f = erteilen(w, fach, user_id=helfer_id, grundrecht="lesen", notiz="Testnotiz").json["freigaben"][0]
        assert w.delete(f"/api/material/ordner/{fach}", headers=H).status_code == 200
        assert not zeilen(app, "SELECT 1 FROM mat_folder_grant WHERE id = ?", (f["id"],))
        e = journal(app, fach)
        assert [x["action"] for x in e] == ["freigabe_erteilt", "freigabe_entfernt"], e
        spur = e[-1]["vorher"] or e[-1]["nachher"]
        assert spur["freigabe"] == f["id"] and spur["konto"] == {"ref": ref(app, helfer_id)} and spur["recht"] == "lesen"
        assert "Testnotiz" not in (e[-1]["before_json"] or "") + (e[-1]["after_json"] or "")
    print("Ordner löschen schreibt freigabe_entfernt bestanden.")


if __name__ == "__main__":
    test_erteilen_aendern_entziehen()
    test_vorlagen_eine_transaktion()
    test_grenzen()
    test_uebernahme_schutz()
    test_eigene_laenger_als_verwalten()
    test_notiz_geerbt_und_meine()
    test_listen_und_verlaengern()
    test_dauerhaft_pruefen()
    test_entziehen_offene_entwuerfe()
    test_nutzersuche()
    test_meine_ohne_zugang()
    test_nutzerverwaltung()
    test_list_users_abfragen()
    test_liste_abfragen()
    test_braucht_a1_ordner_loeschen_journal()
