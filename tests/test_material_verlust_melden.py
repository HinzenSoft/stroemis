"""„Verlust melden“ statt „Sperren“ an der Artikelseite (Entscheidung des Nutzers vom 01.11.2026):  python
tests/test_material_verlust_melden.py  oder pytest

Ohne Prüfung sperrt ein Prüfer nur noch bei Verlust („Verlust melden“ im Menü „Mehr“, Zustand „verloren“) und Rückruf
(„Sperren (Rückruf)“ im Rückruf-Banner); Beschädigung und Sturzbelastung gehen über „Mangel melden“. Der Server lehnt
„sturz“ und „beschaedigung“ mit Klartext ab (400). Ältere Sperren mit diesen Gründen bleiben in Artikel, Journal,
Lebenslauf, Jahresbericht und „Meine PSA“ lesbar. Dazu die Oberfläche statisch (Menü, Dialog, Banner, Marke).

Alle Namen, Nummern und Texte hier sind Platzhalter."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import pdf_seiten  # noqa: E402
from test_material_bericht import bericht  # noqa: E402
from test_material_meine_psa import LISTE, aufbau, post_mangel, zuordnen  # noqa: E402
from test_material_uiux_u2 import MAT, abschnitt, lies  # noqa: E402

API = "/api/material"


def artikel(c, iid):
    return c.get(f"{API}/artikel/{iid}").json["artikel"]


def sperren(c, iid, grund, text=""):
    return c.post(f"{API}/artikel/{iid}/sperren", json={"grund": grund, "text": text})


def test_server_gruende():
    """sturz und beschaedigung: 400 mit Hinweis auf „Mangel melden“, nichts ändert sich (auch kein Journal); verlust
    sperrt als „verloren“, rueckruf als „gesperrt“; ohne Grund und mit unbekanntem Grund 400; wer nicht prüft, 403."""
    from app.material.services import pruefung as dienst
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1, a2, a3 = t.art
        p = t.k["pruefer"]
        vorher = artikel(t.w, a1)
        for alt in ("sturz", "beschaedigung"):
            r = sperren(p, a1, alt, "Platzhalter")
            assert r.status_code == 400 and r.json["error"] == dienst.SPERRE_ALT_GRUND, r.get_json()
            assert "„Mangel melden“" in r.json["error"]
        nachher = artikel(t.w, a1)
        assert nachher["lock_state"] == "frei" and nachher["journal"] == vorher["journal"], nachher["journal"][:2]
        for falsch in ("", "unfug", None):
            assert sperren(p, a1, falsch).status_code == 400
        # Wer nicht prüfen darf, kommt gar nicht bis zum Grund.
        assert sperren(t.w, a1, "verlust").status_code == 403
        assert sperren(t.w, a1, "sturz").status_code == 403
        r = sperren(p, a1, "verlust", "Platzhalter nach dem Einsatz weg")
        assert r.status_code == 200, r.get_json()
        a = r.json["artikel"]
        assert a["lock_state"] == "verloren" and a["status"] == "gesperrt" and a["folder_id"] == t.system["gesperrt"]
        assert a["lock_reason"] == "Verlust: Platzhalter nach dem Einsatz weg"
        # Verloren gemeldet: Der Materialwart kann sofort aussondern, Grund „Verlust“.
        assert artikel(t.w, a1)["aussondern"] == {"ok": True, "grund": ""}
        r = sperren(p, a2, "rueckruf", "Platzhalter-Rückruf")
        assert r.status_code == 200 and r.json["artikel"]["lock_state"] == "gesperrt", r.get_json()
        assert r.json["artikel"]["lock_reason"] == "Rückruf: Platzhalter-Rückruf"
        # Schon gesperrt: 409 wie bisher – ein alter Grund bleibt dennoch 400 (er ist nie erlaubt).
        assert sperren(p, a2, "verlust").status_code == 409
        assert sperren(p, a2, "sturz").status_code == 400
        # Der Text bleibt auf 300 Zeichen begrenzt.
        assert sperren(p, a3, "verlust", "x" * 301).status_code == 400
        assert sperren(p, a3, "verlust", "x" * 300).status_code == 200
    print("Gründe am Server bestanden.")


def test_alte_sperre_lesbar():
    """Eine Sperre mit dem Grund „Sturzbelastung“ von vor dem 01.11.2026 (wie sie pruefung._sperren damals schrieb):
    Artikel, Journal, Lebenslauf, Jahresbericht (Art „Sperre durch Prüfer ohne Prüfung“) und „Meine PSA“ zeigen sie
    weiter; Aussondern erst nach einer Prüfung wie bisher."""
    from app import db
    from app.material.services import bestand
    from app.material.services import pruefung as dienst
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        zuordnen(t, a1, t.person_id)
        with t.app.app_context(), db.transaction(sofort=True):
            dienst._sperren(bestand.artikel(a1), "gesperrt", "Sturzbelastung: Platzhalter Sturz")
        a = artikel(t.w, a1)
        assert a["lock_state"] == "gesperrt" and a["status"] == "gesperrt", a
        assert a["lock_reason"] == "Sturzbelastung: Platzhalter Sturz"
        assert a["aussondern"] == {"ok": False, "grund": dienst.AUSSONDERN_OHNE_PRUEFUNG}
        j = next(x for x in a["journal"] if x["action"] == "gesperrt")
        assert "Sturzbelastung: Platzhalter Sturz" in str(j), j
        r = t.w.get(f"/materialablage/artikel/{a1}/lebenslauf.pdf")
        assert r.status_code == 200, r.status_code
        pfad = os.path.join(tmp, "lebenslauf.pdf")
        with open(pfad, "wb") as fh:
            fh.write(r.data)
        text = " ".join(" ".join(pdf_seiten(pfad)).split())
        assert "Sturzbelastung: Platzhalter Sturz" in text, text[-2000:]
        b = bericht(t.k["fuehrung"], t.gid)
        zeile = [x for x in b["sperren"]["liste"] if x["grund"] == "Sturzbelastung: Platzhalter Sturz"]
        assert len(zeile) == 1 and zeile[0]["art"] == "ohne_pruefung", b["sperren"]
        assert {x["art"]: x["n"] for x in b["sperren"]["arten"]}["ohne_pruefung"] == 1
        karte = next(k for k in t.person.get(LISTE).json["artikel"] if k["id"] == a1)
        assert karte["gesperrt"] and not karte["verloren"], karte
    print("Alte Sperre lesbar bestanden.")


def test_meine_psa_verloren():
    """„Verlust melden“ an einem zugeordneten Artikel: Die Karte in „Meine PSA“ trägt verloren (Banner „Als verloren
    gemeldet“ in material.js)."""
    with post_mangel(), tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        a1 = t.art[0]
        zuordnen(t, a1, t.person_id)
        assert sperren(t.k["pruefer"], a1, "verlust").status_code == 200
        karte = next(k for k in t.person.get(LISTE).json["artikel"] if k["id"] == a1)
        assert karte["gesperrt"] and karte["verloren"], karte
    js = lies(MAT)
    assert 'if (k.verloren) return ["s-gesperrt", "Als verloren gemeldet' in js
    print("Meine PSA bestanden.")


def test_oberflaeche():
    """Menü „Mehr“: „Mangel melden“ vor „Verlust melden“, kein „Sperren“; Dialog ohne Auswahlfeld mit Titel „… als
    verloren melden“, Freitext bis 300 Zeichen, Folgesatz, Hauptaktion btn „Verlust melden“, Toast mit Gegenstand;
    Rückruf-Banner mit „Sperren (Rückruf)“ unverändert; Banner und Marke „verloren“ am Artikel."""
    js = lies(MAT)
    mehr = abschnitt(js, "function artikelMehr(a, eintraege) {", "\n  }")
    assert 'sperren: {' not in mehr and '"Sperren"' not in mehr
    assert 'verlust: { text: "Verlust melden", satz: "Sperrt den Artikel als verloren.", attrs: \'data-act="verlust"\' }' in mehr
    assert mehr.index("mangel: {") < mehr.index("verlust: {")
    assert len("Sperrt den Artikel als verloren.") <= 45
    assert 'pruefKnopf && darfMelden && !schonGemeldet ? "mangel" : "", pruefKnopf && verlustKnopf ? "verlust" : ""' in js
    assert "const verlustKnopf = frei && darf.pruefen && !a.entwurf;" in js
    assert 'data-act="sperren"' not in js and "SPERRGRUND" not in js and "sd-grund" not in js
    dlg = abschnitt(js, "function sperrDialog(a, grund, text) {", "\n  }\n")
    assert "<select" not in dlg
    assert '${esc(a.inventory_no)} ${verlust ? "als verloren melden" : "sperren"}</h2>' in dlg
    assert '<label for="sd-text">Was ist passiert?</label><input type="text" id="sd-text" maxlength="300"' in dlg
    assert '<button class="btn" id="sd-ok" type="button">${verlust ? "Verlust melden" : "Sperren"}</button>' in dlg
    assert 'body: { grund, text: $("#sd-text", body).value }' in dlg
    assert 'toast(`${a.inventory_no} ${verlust ? "als verloren gemeldet" : "gesperrt"}`)' in dlg
    folge = abschnitt(js, "const VERLUST_FOLGE = ", ";\n")
    for teil in ("gesperrt", "zählt als verloren", "Taucht er wieder auf: nicht verwenden", "Freiprüfung",
                 "Der Materialwart kann ihn mit dem Grund „Verlust“ sofort aussondern."):
        assert teil in folge, teil
    assert 'verlust: () => sperrDialog(a, "verlust"),' in js
    assert '"rr-sperren": (b) => sperrDialog(a, "rueckruf", ' in js
    # Rückruf-Banner unverändert.
    assert ('<button class="btn small" type="button" data-act="rr-sperren" data-id="${r.id}">Sperren (Rückruf)</button>'
            in js)
    # Am Artikel: Marke „verloren“ und „Taucht er wieder auf“ im GESPERRT-Banner.
    assert ("${verloren ? '<span class=\"mat-status s-gesperrt gross\">verloren</span>' : statusMarke(a.status, true)}"
            in js)
    assert '${verloren ? "Taucht er wieder auf: nicht verwenden" : "Nicht verwenden"}, bis eine Freiprüfung ihn freigibt.' in js
    assert "als verloren gemeldet${m[1] ? ` (${m[1]})` : \"\"}" in js
    print("Oberfläche bestanden.")


if __name__ == "__main__":
    test_server_gruende()
    test_alte_sperre_lesbar()
    test_meine_psa_verloren()
    test_oberflaeche()
