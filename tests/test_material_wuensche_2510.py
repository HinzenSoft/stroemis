"""Wünsche vom 25.10.2026 (Entwurf entwurf_l2c_wuensche.md, Entscheidungen F1–F4 je Option A):
python tests/test_material_wuensche_2510.py

  W1 Artikelseite: die Norm in einer eigenen Zeile der Stammdaten (nicht mehr hinter Name und Bemerkung).
  W2 Nacharbeit des Bestandsimports: Prüfen und Übernehmen je Produktangabe (Karte, „Übernehmen …“ und direkt nach dem
     Zuordnen), „Fehlendes Produkt melden …“ für Konten ohne Katalogrecht, Bemerkung der Meldung vorbelegt.
  W3 Bestand: Spalte „Kategorie“ in der Artikelliste des Ordners, Filter nach Kategorie (mit Status und Person
     kombiniert), Zahlen je Gruppe, Sortierung; Filtermenü in der Seitenleiste, „Filter (n)“ über der Liste.
Der Wiki-Import (W4) steht in tests/test_wiki_import.py. Alle Namen, Nummern und Texte sind Platzhalter."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import neuer_artikel  # noqa: E402
from test_material_import import aufbau, csv_bytes, offene_zeilen, ok, uebernehmen  # noqa: E402
from test_material_trennung import zeilen  # noqa: E402
from test_material_ueberblick import ohne_post  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _js():
    return open(os.path.join(WURZEL, "app/material/static/material.js"), encoding="utf-8").read()


# --- W1 ---------------------------------------------------------------------------------------------------------------

def test_norm_eigene_zeile():
    js = _js()
    artikel = js[js.index("async function artikel()"):js.index("function artikelDialog(a,")]
    assert '${zeile("Produkt", `${nameHtml(p)}${zusatzHtml(p)}`)}' in artikel
    assert '${zeile("Norm", p.norm ? esc(p.norm) : \'<span class="muted">–</span>\')}' in artikel
    assert "· ${esc(p.norm)}" not in artikel
    print("W1 Norm in eigener Zeile bestanden.")


# --- W2 ---------------------------------------------------------------------------------------------------------------

def test_nacharbeit_uebernehmen_je_angabe():
    """„Übernehmen …“ an der Karte: prüfen und übernehmen alle offenen Zeilen genau dieser Angabe in diesem Ordner;
    angabe und zeilen zugleich 400, unbekannte Angabe 404, ohne verwalten 403; Journal am Ordner und am Artikel wie
    beim „Erneut prüfen“."""
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        app, w = t.app, t.w
        kopf = ["Hersteller", "Modell", "Seriennummer"]
        ok(uebernehmen(w, t.lager, csv_bytes([kopf, ["Testwerk", "HMS Gamma", "UA-0001"],
                                              ["Testwerk", "HMS Gamma", "UA-0002"],
                                              ["Nirgendwerk", "Phantom", "UA-0003"]])), 201)
        offen = offene_zeilen(app, t.lager)
        gamma = offen[0]["offer_key"]
        url = f"/api/material/ordner/{t.lager}/nacharbeit"
        assert ok(w.post(f"{url}/produkt", json={"angabe": gamma, "product_id": t.ids["hms"]}))["gesetzt"] == 2
        # Fehlerfälle
        r = w.post(f"{url}/pruefen", json={"angabe": gamma, "zeilen": "alle"})
        assert r.status_code == 400 and "Produktangabe oder Zeilen" in r.json["error"], r.get_json()
        assert w.post(f"{url}/pruefen", json={}).status_code == 400
        assert w.post(f"{url}/pruefen", json={"angabe": "gibt|es|nicht"}).status_code == 404
        assert w.post(f"{url}/pruefen", json={"angabe": ""}).status_code == 400
        assert t.k["pruefer"].post(f"{url}/pruefen", json={"angabe": gamma}).status_code == 403
        # Prüfen ohne Übernehmen: nur die zwei Zeilen der Angabe.
        r = ok(w.post(f"{url}/pruefen", json={"angabe": gamma}))
        assert r["zahlen"]["zeilen"] == 2 and r["zahlen"]["uebernehmbar"] == 2, r["zahlen"]
        assert len(offene_zeilen(app, t.lager)) == 3
        r = ok(w.post(f"{url}/pruefen", json={"angabe": gamma, "uebernehmen": True}))
        assert [z["status"] for z in r["zeilen"]] == ["angelegt", "angelegt"], r["zeilen"]
        assert [o["id"] for o in offene_zeilen(app, t.lager)] == [offen[2]["id"]]
        aid = r["zeilen"][0]["artikel"]["id"]
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'item' AND entity_id = ? "
                           "AND action = 'angelegt' AND after_json LIKE '%aus_nacharbeit%'", (aid,))[0]["n"] == 1
        assert zeilen(app, "SELECT COUNT(*) AS n FROM mat_audit WHERE entity = 'folder' AND entity_id = ? "
                           "AND action = 'nacharbeit_uebernommen'", (t.lager,))[0]["n"] == 1
        # Erledigt: dieselbe Angabe hat keine offenen Zeilen mehr.
        assert w.post(f"{url}/pruefen", json={"angabe": gamma}).status_code == 404
    print("W2 Übernehmen je Angabe bestanden.")


def test_meldung_vorbelegt():
    """Die Karte trägt meldung_bemerkung: Satz zum Import und die verschiedenen Bemerkungen der Zeilen (höchstens fünf,
    je höchstens 200 Zeichen) – keine Serien- und Inventarnummern, kein Dateiname. Eine Meldung aus der Nacharbeit
    bleibt eine Produktmeldung, auch mit is_set (S8)."""
    with tempfile.TemporaryDirectory() as tmp, ohne_post():
        t = aufbau(tmp)
        app, w = t.app, t.w
        kopf = ["Hersteller", "Modell", "Seriennummer", "Inventarnummer", "Bemerkung"]
        lang = "Platzhalter " + "x" * 300
        liste = [kopf] + [["Meldewerk", "Gerät Delta", f"MV-{n:04d}", f"INV-{n}", b] for n, b in enumerate(
            ["Größe M", "Größe M", "Farbe rot", "", lang, "Bem 4", "Bem 5", "Bem 6", "Bem 7"])]
        ok(uebernehmen(w, t.lager, csv_bytes(liste), "Liste Vorname Nachname.csv"), 201)
        imp = offene_zeilen(app, t.lager)[0]["import_id"]
        karte = ok(w.get(f"/api/material/ordner/{t.lager}/nacharbeit"))["gruppen"][0]
        text = karte["meldung_bemerkung"]
        assert text.startswith(f"Aus dem Bestandsimport Nr. {imp}: 9 Artikel warten in der Nacharbeit."), text
        punkte = [z[2:] for z in text.split("\n") if z.startswith("– ")]
        assert punkte[:3] == ["Größe M", "Farbe rot", f"{lang[:199]}…"] and len(punkte) == 5, punkte
        assert all(len(x) <= 200 for x in punkte)
        for verboten in ("MV-0", "INV-", "Vorname", "Nachname", ".csv"):
            assert verboten not in text, verboten
        # Melden mit der Vorbelegung (die Oberfläche schickt sie als note) und mit is_set: bleibt ein Produkt.
        r = w.post(f"/api/material/ordner/{t.lager}/nacharbeit/melden",
                   json={"angabe": karte["angabe"], "note": text, "is_set": "1", "set_teile": "Teil A"})
        m = ok(r, 201)["meldung"]
        assert m["note"] == text and m["is_set"] is False and not m.get("set_teile"), m
    print("W2 Meldung vorbelegt bestanden.")


def test_nacharbeit_oberflaeche():
    js = _js()
    anfang = js.index("  async function bestandsimport() {")
    block = js[anfang:js.index("\n  }\n", anfang)]
    # Konten ohne Katalogrecht: „Fehlendes Produkt melden …“; Material-Verwaltung behält „Im Katalog anlegen …“.
    assert "if (!g.produkt && DARF.katalog) knoepfe.push(" in block and "Im Katalog anlegen …" in block
    assert 'data-act="na-melden" data-i="${i}">Fehlendes Produkt melden …</button>' in block
    assert ">Produkt melden …<" not in block
    # „Übernehmen …“ an der zugeordneten Karte (grau), öffnet die Prüfung je Angabe.
    assert ('if (g.produkt || g.zugeordnet || (m && m.status === "eingepflegt")) knoepfe.push(`<button type="button" '
            'class="btn secondary small" data-act="na-uebernehmen"') in block
    assert '"na-uebernehmen": (b) => nachpruefen({ angabe: na.gruppen[+b.dataset.i].angabe })' in block
    # Nach dem Zuordnen und nach „Im Katalog anlegen …“ direkt die Prüfung (F1), Titel „Zugeordnet – übernehmen?“.
    assert "if (pid) nachpruefen(ziel, r.gesetzt);" in block and "nachpruefen({ angabe: g.angabe }, r.gesetzt);" in block
    assert '"Zugeordnet – übernehmen?"' in block and "„Erneut prüfen“ übernimmt" not in block
    # Meldung vorbelegt mit der Bemerkung der Karte; der Dialog nimmt note, norm, category_id.
    assert "note: g.meldung_bemerkung" in block
    dlg = js[js.index("async function meldungDialog(v, danach)"):js.index("/* --- Rückrufe (Lieferung 4)")]
    assert '${esc(v.note || "")}</textarea>' in dlg and 'value="${esc(v.norm || "")}"' in dlg
    assert "kategorieOptionen(kats, v.category_id || null)" in dlg
    # Knopfregel: in der Nacharbeit weiter nur die zwei roten Knöpfe der Dialoge, keine Piktogramme.
    assert block.count('class="btn"') == 2 and block.count('class="btn mat-knopf-umbruch"') == 1
    print("W2 Oberfläche (statisch) bestanden.")


# --- W3 ---------------------------------------------------------------------------------------------------------------

def _ordner(c, fid, **q):
    from urllib.parse import urlencode
    r = c.get(f"/api/material/ordner/{fid}?{urlencode(q)}")
    return r


def test_bestand_kategorie():
    """lager_a: Set S (Set-Produkt in „Gurte“), F und art_a (HMS Beta in „Karabiner“), dazu ein Artikel in einer
    zweiten Kategorie „Karabiner“ unter „Wasserrettung“ (gleicher Name, anderer Pfad)."""
    from test_material_sets import set_aufbau
    with tempfile.TemporaryDirectory() as tmp, ohne_post():
        t = set_aufbau(tmp)
        w, mv = t.wart_a, t.k["katalog"]
        wr = ok(mv.post("/api/material/kategorien", json={"name": "Wasserrettung"}), 201)["kategorie"]["id"]
        kar2 = ok(mv.post("/api/material/kategorien", json={"name": "Karabiner", "parent_id": wr,
                                                            "default_material_kind": "metall_hardware"}), 201)["kategorie"]["id"]
        p2 = ok(mv.post("/api/material/produkte", json={"category_id": kar2, "manufacturer": "Testwerk",
                                                        "model": "Schnapper Zeta", "article_no": "SZ-1",
                                                        "material_kind": "metall_hardware", "interval_months": 12}),
                201)["produkt"]["id"]
        z = neuer_artikel(w, p2, t.lager_a, serial_no="KAT-Z-1")
        d = ok(_ordner(w, t.lager_a))["ordner"]
        assert len(d["artikel"]) == 4 and all(a["kategorie"] for a in d["artikel"])
        kats = {(k["id"], k["name"], k["pfad"], k["n"]) for k in d["kategorien"]}
        assert kats == {(t.ids["gurte"], "Gurte", "PSA gegen Absturz / Gurte", 1),
                        (t.ids["karabiner"], "Karabiner", "PSA gegen Absturz / Karabiner", 2),
                        (kar2, "Karabiner", "Wasserrettung / Karabiner", 1)}, kats
        assert [k["name"] for k in d["kategorien"]] == ["Gurte", "Karabiner", "Karabiner"]
        # Filter: die Set-Zeile nach dem Set-Produkt, Teile nie.
        d = ok(_ordner(w, t.lager_a, kategorie=t.ids["gurte"]))["ordner"]
        assert [a["id"] for a in d["artikel"]] == [t.s["id"]] and d["artikel_gesamt"] == 1 and d["artikel"][0]["set"]
        d = ok(_ordner(w, t.lager_a, kategorie=t.ids["karabiner"]))["ordner"]
        assert {a["id"] for a in d["artikel"]} == {t.f["id"], t.art_a["id"]} and not set(t.teile) & {a["id"] for a in d["artikel"]}
        # Zahlen je Gruppe mit den übrigen Filtern: Status mit Kategorie, Kategorien mit Status.
        assert sum(d["direkt"].values()) == 2, d["direkt"]
        assert {k["id"]: k["n"] for k in d["kategorien"]}[t.ids["gurte"]] == 1      # Kategorien ohne Kategoriefilter
        status = ok(_ordner(w, t.lager_a))["ordner"]["artikel"]
        s_set = next(a["status"] for a in status if a["id"] == t.s["id"])
        d = ok(_ordner(w, t.lager_a, status=s_set, kategorie=t.ids["gurte"]))["ordner"]
        assert [a["id"] for a in d["artikel"]] == [t.s["id"]]
        nach_status = {k["id"]: k["n"] for k in ok(_ordner(w, t.lager_a, status="gesperrt"))["ordner"]["kategorien"]}
        assert sum(nach_status.values()) == sum(1 for a in status if a["status"] == "gesperrt")
        # Mit Person kombiniert: niemandem zugeordnet → leer.
        d = ok(_ordner(w, t.lager_a, kategorie=t.ids["karabiner"], zugeordnet=t.k["wart_id"]))["ordner"]
        assert d["artikel"] == [] and d["artikel_gesamt"] == 0
        # Unbekannte Kennung: leere Liste; keine Zahl: 400.
        d = ok(_ordner(w, t.lager_a, kategorie=999999))["ordner"]
        assert d["artikel"] == [] and d["artikel_gesamt"] == 0
        assert _ordner(w, t.lager_a, kategorie="abc").status_code == 400
        # Sortierung nach Kategorie auf und ab.
        auf = [a["kategorie"]["name"] for a in ok(_ordner(w, t.lager_a, sort="kategorie"))["ordner"]["artikel"]]
        ab = [a["kategorie"]["name"] for a in ok(_ordner(w, t.lager_a, sort="kategorie", richtung="ab"))["ordner"]["artikel"]]
        assert auf == ["Gurte", "Karabiner", "Karabiner", "Karabiner"] and ab == auf[::-1], (auf, ab)
        # Rechte: Leser sieht Kategorie und Filter, fremde Gliederung 404.
        d = ok(_ordner(t.k["fuehrung"], t.lager_a, kategorie=kar2))["ordner"]
        assert [a["id"] for a in d["artikel"]] == [z["id"]]
        assert _ordner(t.wart_b, t.lager_a, kategorie=t.ids["gurte"]).status_code == 404
        # Fällige und Suche: Kategorie sortierbar, schadet nicht.
        assert t.wart_a.get("/api/material/faellig?sort=kategorie").status_code == 200
    print("W3 Kategorie im Bestand bestanden.")


def test_bestand_oberflaeche():
    js = _js()
    css = open(os.path.join(WURZEL, "app/material/static/material.css"), encoding="utf-8").read()
    seite = open(os.path.join(WURZEL, "app/material/templates/material/seite.html"), encoding="utf-8").read()
    assert ('<section class="mat-side-filter" id="mat-side-filter" aria-labelledby="mat-filter-titel" hidden>' in seite
            and '<h2 id="mat-filter-titel" tabindex="-1">Filter</h2>' in seite)
    ordner = js[js.index("  async function ordner() {"):js.index("/* --- Produktsuche mit allen Treffern")]
    # Die Reiterzeile in der Liste entfällt; Status, Kategorie und Person stehen im Filtermenü.
    assert "c-tabs mat-filter" not in ordner and "mat-filterzeile" not in ordner
    assert 'wahlKnopf("filter", "data-f"' in ordner and 'wahlKnopf("kategorie", "data-k"' in ordner
    assert 'aria-pressed="${an}"' in ordner and 'class="mat-filtergruppe mat-filter-person">${personWahl}' in ordner
    assert 'data-act="filter-auf" data-leiste-auf' in ordner and "`Filter (${gefiltert.length})`" in ordner
    assert 'Gefiltert: ${gefiltert.join(" · ")} – <button type="button" class="lnk" data-act="filter-weg">Filter zurücksetzen</button>' in ordner
    assert 'leer("Keine Artikel mit diesen Filtern.")' in ordner
    assert "kategorie: true })" in ordner and 'q.set("kategorie", kategorie)' in ordner
    # Spalte vorn, eng und als Karte über Hersteller/Produkt; Sortierwahl der Karten mit Kategorie.
    tab = js[js.index("  function artikelTabelle(liste, opts) {"):js.index("  function wahlFeld(a) {")]
    assert 'sortKopf("Kategorie", "kategorie", s, { klasse: "mat-schmal-weg" })' in tab
    assert 'kopfZusatz("Kategorie", "kategorie", s, "schmal")' in tab and "kat ? ARTIKEL_SORT_KAT : ARTIKEL_SORT" in tab
    assert '<td data-l="Kategorie" class="mat-schmal-weg mat-kategorie">${a.kategorie ? esc(a.kategorie.name) : ""}</td>' in tab
    # Leiste: Klicks und Personenwahl aus dem Filtermenü an die Ansicht, „Filter (n)“ öffnet die Schublade dort.
    assert 'e.target.closest("#mat-side-filter [data-act]")' in js and '"#mat-side-filter select[data-personwahl]"' in js
    assert "function leisteOeffnen(von, ziel)" in js and '!e.target.closest("[data-leiste-auf]")' in js
    # CSS: Knopf „Filter“ nur als Schublade, Tippflächen nur am Finger.
    teil = css[css.index("/* Filtermenü unter dem Ordnerbaum"):css.index("/* Ordnerleiste: ab 1024 px fest")]
    assert ".mat-filter-auf { display: none; }" in teil and "@media (max-width: 1023px) {\n  .mat-filter-auf { display: inline-flex; }" in teil
    assert "@media (pointer: coarse) { .mat-filterwahl, .mat-filter-person select { min-height: 44px; } }" in teil
    assert "min-height" not in teil.replace("@media (pointer: coarse) { .mat-filterwahl, .mat-filter-person select { min-height: 44px; } }", "")
    assert "btn ghost" not in js
    print("W3 Oberfläche (statisch) bestanden.")


if __name__ == "__main__":
    test_norm_eigene_zeile()
    test_nacharbeit_uebernehmen_je_angabe()
    test_meldung_vorbelegt()
    test_nacharbeit_oberflaeche()
    test_bestand_kategorie()
    test_bestand_oberflaeche()
