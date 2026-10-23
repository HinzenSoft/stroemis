"""Hersteller-Sets, Oberfläche Teil 1 (Phase 4 · Lieferung 2, Paket O1):  python tests/test_material_sets_oberflaeche.py

Statisch: material.js, suche.js, global.js und material.css für den Stand K1 – Produkt-Dialog mit „Hersteller-Set“ und
Reiter „Bestandteile“ (Werte und Grenzen gleich wie auf dem Server), Produktseite mit Stückliste, Artikel anlegen mit
Teilblöcken, Set-Seite und Teil-Seite (keine Knöpfe, die am Teil 409 gäben), Listen mit Set-Zeile und Kopf, Meine PSA
mit Teilen, Steckbrief, Importbericht und Export-Vorschau; Knopfsprache und Container-Abfragen.
Dazu ein Vertragstest: Die Schlüssel, die die Oberfläche liest, stehen in den Antworten des Servers.

Alle Hersteller, Modelle und Nummern hier sind erfunden und nur für den Test da."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import neues_konto  # noqa: E402
from test_material_import import ok  # noqa: E402
from test_material_sets import set_aufbau  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(rel):
    return open(os.path.join(WURZEL, rel), encoding="utf-8").read()


def funktion(js, name):
    """Der Quelltext einer Funktion (bis zur schließenden Klammer auf Einrückungstiefe 2)."""
    anfang = js.index(f"function {name}(")
    ende = js.index("\n  }\n", anfang)
    return js[anfang:ende]


def test_werte_wie_server():
    """AUSTAUSCH, HILFE_EINZELN und die Grenzen der Stückliste in material.js gleich wie in models.py und
    stueckliste.py – die Produktantwort trägt den Hilfetext nicht, ein neues Produkt keine Grenzen."""
    from app.material import models
    from app.material.services import stueckliste
    js = lies("app/material/static/material.js")
    block = js[js.index("const AUSTAUSCH = {"):]
    block = block[:block.index("}")]
    assert dict(re.findall(r'([a-z_]+): "([^"]*)"', block)) == models.AUSTAUSCH
    hilfe = re.search(r'const HILFE_EINZELN = "([^"]*)";', js).group(1)
    assert hilfe == stueckliste.HILFE_EINZELN
    grenzen = re.search(r"const STUECK_GRENZEN = \{ positionen: (\d+), anzahl: (\d+), teile: (\d+), bezeichnung: (\d+) \};", js)
    assert tuple(int(x) for x in grenzen.groups()) == (models.STUECKLISTE_POSITIONEN_MAX, models.BESTANDTEIL_ANZAHL_MAX,
                                                         models.SET_TEILE_MAX, models.BEZEICHNUNG_MAX)
    print("Werte wie auf dem Server bestanden.")


def test_oberflaeche_statisch():
    js = lies("app/material/static/material.js")
    css = lies("app/material/static/material.css")
    such, glob = lies("app/material/static/suche.js"), lies("app/material/static/global.js")
    # Katalog: Häkchen, Reiter, Speichern der Stückliste als Ganzes, Variante mit „Stückliste übernehmen“.
    dlg = funktion(js, "produktDialog")
    for haken in ('id="pd-set"', "set_umschalt_grund", 'role="tablist"', 'data-reiter="bestandteile"',
                  "/bestandteile`, { method: \"PUT\"", "stueckliste: !!(", "daten.is_set = alsSet", "confirm("):
        assert haken in dlg, haken
    # Häkchen nur senden, wenn es sich umschalten lässt; keine Set-Steuerung aus Meldung oder Nacharbeit.
    assert "if (setFeld && !setFeld.disabled)" in dlg and "const mitSet = !p.variante_von && !p.meldung && !opt.danach;" in dlg
    ed = funktion(js, "stuecklisteEditor")
    for haken in ("HILFE_EINZELN", "produktTreffer(", "prod.is_set", "AUSTAUSCH", "Position (\\d+)", 'data-bt="hoch"',
                  '<span class="k-text"><span class="k-plus" aria-hidden="true">+ </span>Bestandteil<span class="k-anlegen"> anlegen</span></span>'):
        assert haken in ed, haken
    assert 'class="btn"' not in ed and "btn ghost" not in ed and "btn danger" not in ed
    assert "stuecklisteHtml(p, k)" in js and "bestandteil_von" in js and 'data-act="stueckliste"' in js
    # Importbericht und Export-Vorschau.
    assert "b.stuecklisten" in js and "v.set_verstoesse" in js
    # Artikel anlegen: Teilblöcke aus dem Vorschlag, Hinweise der Antwort, Fehler am Feld.
    for haken in ("v.set && teileFuer !== produkt.id", "teil_felder", "daten.teile = teileDaten()", "r.hinweise",
                  "teileServerFehler(e.message)", 'setAttribute("aria-invalid", "true")', "STR-Nummer"):
        assert haken in js, haken
    # Set-Seite und Teil-Seite: am Teil kein Verschieben, Zuordnen, Aussondern – stattdessen der Hinweis aufs Set.
    for haken in ("${frei && !tv ? '<button class=\"btn secondary small\" data-act=\"verschieben\">", "${tv ? \"\" : zuKnoepfe}",
                  "&& !a.entwurf && !tv;", "mat-teil-hinweis", "Teil von Set", "setKasten(sb, a)", "setBanner(sb, a)",
                  "rueckrufe_teile", "sb.vollstaendig", "faellig_durch", "lebensende_durch"):
        assert haken in js, haken
    kasten = funktion(js, "setKasten")
    assert "<button" not in kasten and "esc(" in kasten
    # Listen: Set-Zeile und Kopf in Ordner und Fälligen, Teil mit Set in der Suche.
    assert "setKopf(d.artikel_gesamt, d.sets)" in js and "setKopf(d.gesamt, d.sets)" in js
    assert "a.teil_von" in js and "a.set.mangel_teile" in js and "a.set.rueckruf_teile" in js
    assert "a.teil_von" in such and "a.set" in such
    assert "t.teil_eines_sets" in glob
    # Meine PSA: Teile in der Set-Karte, Einzelansicht eines Teils zeigt sein Set.
    assert "psaTeil(t, banner[0])" in js and "(k.teile || []).some((t) => t.id === DATEN.id)" in js
    # Journal: Listen aus Objekten (Teile, Positionen) lesbar.
    assert "listenWert(x)" in js
    # Knopfsprache: kein btn ghost; CSS mit Container-Abfrage und Touch-Regeln unter pointer: coarse.
    assert "btn ghost" not in js
    teil = css[css.index("/* Phase 4 – Lieferung 2: Hersteller-Sets (Oberfläche O1) */"):]
    assert "@container mat-seite" in teil and "@media (pointer: coarse)" in teil
    assert "min-height: 44px" in teil[teil.index("@media (pointer: coarse)"):]
    print("Oberfläche (statisch) bestanden.")


def test_vertrag_mit_dem_server():
    """Was die Oberfläche liest, liefert der Server (Stand K1): Produkt, Vorschlag, Set- und Teil-Seite, Listen mit
    Kopf, Suche, Meine PSA."""
    with ohne_post(), tempfile.TemporaryDirectory() as tmp:
        t = set_aufbau(tmp)
        w, mv = t.wart_a, t.k["katalog"]
        p = ok(mv.get(f"/api/material/produkte/{t.set_p}"))["produkt"]
        assert {"is_set", "bestandteile", "bestandteil_von", "set_umschaltbar", "set_umschalt_grund",
                "stueckliste_grenzen"} <= set(p)
        assert set(p["stueckliste_grenzen"]) == {"positionen", "anzahl", "teile", "bezeichnung"}
        assert {"id", "bezeichnung", "anzahl", "einzeln", "austausch", "austausch_text", "produkt"} <= set(p["bestandteile"][0])
        h = ok(mv.get(f"/api/material/produkte/{t.ids['hms']}"))["produkt"]
        assert h["bestandteil_von"] and {"id", "name"} == set(h["bestandteil_von"][0])
        assert "is_set" in ok(mv.get("/api/material/produkte?q=Testset"))["produkte"][0]
        v = ok(w.get(f"/api/material/artikel/vorschlag?product_id={t.set_p}&folder_id={t.lager_a}"))["vorschlag"]
        assert {"bestandteile", "teil_felder"} <= set(v["set"])
        assert {"laenge_moeglich", "material_kind", "demo", "id"} <= set(v["set"]["bestandteile"][0]["produkt"])
        a = ok(w.get(f"/api/material/artikel/{t.s['id']}"))["artikel"]
        sb = a["set"]
        assert {"status", "next_due_on", "faellig_durch", "retire_by", "lebensende_durch", "eigen", "teile", "teile_anzahl",
                "bestandteile", "vollstaendig", "fehlend", "rueckrufe_teile"} <= set(sb)
        assert {"id", "inventory_no", "serial_no", "serial_generated", "produkt", "bestandteil", "status", "next_due_on",
                "retire_by", "lock_state", "lock_reason", "mangel", "rueckruf"} <= set(sb["teile"][0])
        assert {"name", "manufacturer", "model", "description", "article_no"} <= set(sb["teile"][0]["produkt"])
        assert {"vorhanden", "fehlt"} <= set(next(b for b in sb["bestandteile"] if b["einzeln"]))
        tv = ok(w.get(f"/api/material/artikel/{t.teile[0]}"))["artikel"]["teil_von"]
        assert {"id", "inventory_no", "produkt", "status", "bestandteil"} <= set(tv)
        o = ok(w.get(f"/api/material/ordner/{t.lager_a}"))["ordner"]
        assert o["sets"] == {"anzahl": 1, "teile": 3} and "artikel_gesamt" in o
        zeile = next(x for x in o["artikel"] if x["id"] == t.s["id"])
        assert {"teile", "vollstaendig", "mangel_teile", "rueckruf_teile", "faellig_durch"} <= set(zeile["set"])
        f = ok(w.get(f"/api/material/faellig?ordner={t.lager_a}&status=neu"))
        assert f["sets"]["anzahl"] == 1 and "gesamt" in f
        s = ok(w.get("/api/material/suche?q=SET-A-K1"))["treffer"]
        assert s and {"id", "inventory_no", "produkt"} == set(s[0]["teil_von"])
        person, person_id = neues_konto(t.app, "psa_o1@example.org", name="PSA O1", stufe=0)
        ok(w.put(f"/api/material/artikel/{t.s['id']}/zuordnung", json={"user_id": person_id}))
        k = ok(person.get("/api/material/meine-psa"))["artikel"][0]
        assert len(k["teile"]) == 3 and {"artikel_link", "rueckruf", "produkt"} <= set(k["teile"][0])
    print("Vertrag mit dem Server bestanden.")


if __name__ == "__main__":
    test_werte_wie_server()
    test_oberflaeche_statisch()
    test_vertrag_mit_dem_server()
