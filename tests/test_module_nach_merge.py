"""Lieferung nach dem Merge, Teil B – Strömipedia, Ankerplätze, Riegenkarten, Leitstelle, Anmeldung (27.10.2026):
python tests/test_module_nach_merge.py  oder  pytest tests/test_module_nach_merge.py

Punkte der nach_merge_liste:
  16  Wiki-Export: „-<slug>“ ist selbst vergeben (drittes Geschwister „Foo-<slug>“) → weiter zählen, bis der Pfad frei
      ist; der Import liest den Export wieder ein (Fall der Probe q06_wiki_export.py).
  20  Export → Import: Seite ohne „# Titel“ mit gleichnamigem Geschwister behält ihren Titel (der Export schreibt die
      Titelzeile), auch der Einzelexport.
  17  Riegenkarten: kein Name von Teilnehmenden im Seitentitel (Browserverlauf).
Die Oberflächenpunkte (9, 10, 12, 13, 14) sind im Browser gemessen (Bericht); hier die Stellen im Code, an denen die
Lösungen hängen. Alle Namen und Seiten sind Platzhalter."""
import io
import os
import re
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_wiki_import import aufbau, importieren, seite  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def _positionen(app, seiten):
    """Reihenfolge der Geschwister erzwingen (die erste Seite zuerst exportiert)."""
    with app.app_context():
        from app import db
        for pos, x in enumerate(seiten):
            db.execute("UPDATE wiki_pages SET position = ? WHERE id = ?", (pos, x["id"]))


# --- 16: Namenskollision im Export -------------------------------------------------------------------------------------

def test_export_kollision_weiter_zaehlen():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        oben = seite(t.adm, "Probe Kollision", "# Probe Kollision\n")
        b = seite(t.adm, "Foo", "# Foo\n\nB-INHALT\n", oben["id"])
        c = seite(t.adm, "Foo", "# Foo\n\nC-INHALT\n", oben["id"])
        # Ein drittes Geschwister trägt genau den Namen, den der Export dem zweiten „Foo“ anhängen würde – an erster
        # Stelle; ein viertes heißt so, wie der erste Ausweichname weiterzählt.
        a = seite(t.adm, f"Foo-{c['slug']}", f"# Foo-{c['slug']}\n\nA-INHALT\n", oben["id"])
        d = seite(t.adm, f"Foo-{c['slug']}-2", f"# Foo-{c['slug']}-2\n\nD-INHALT\n", oben["id"])
        for x, n in ((a, "A"), (b, "B"), (c, "C"), (d, "D")):
            seite(t.adm, f"Kind {n}", f"# Kind {n}\n\nKIND-{n}\n", x["id"])
        _positionen(t.app, (a, d, b, c))
        r = t.adm.get(f"/api/wiki/pages/{oben['id']}/export?children=1")
        assert r.status_code == 200
        namen = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
        assert len(namen) == len({n.lower() for n in namen}) == 9, namen
        # A und D behalten ihren Namen, B heißt „Foo“, C weicht auf „Foo-<slug>-3“ aus (-<slug> und -<slug>-2 sind belegt).
        ziel_c = f"Probe Kollision/Foo-{c['slug']}-3"
        assert f"{ziel_c}.md" in namen and f"{ziel_c}/Kind C.md" in namen, namen
        assert f"Probe Kollision/Foo-{c['slug']}/Kind A.md" in namen, namen
        assert "Probe Kollision/Foo/Kind B.md" in namen, namen
        ziel = seite(t.adm, "Ziel Kollision", "# Ziel Kollision\n")
        imp = importieren(t.adm, r.data, ziel["id"])
        assert imp.status_code == 201, imp.json
        sx = imp.json["seiten"]
        nach_id = {x["id"]: x for x in sx}

        def text(x):
            return t.adm.get(f"/api/wiki/pages/{x['slug']}").json["page"]["content"]

        for n in "ABCD":
            kind = [x for x in sx if x["title"] == f"Kind {n}"]
            assert len(kind) == 1, (n, sx)
            assert f"{n}-INHALT" in text(nach_id[kind[0]["parent_id"]]), n
        # Titel bleiben erhalten (aus der Titelzeile, nicht aus dem Ausweichnamen).
        assert sorted(x["title"] for x in sx if x["parent_id"] != ziel["id"] and not x["title"].startswith("Kind")) == \
            sorted(["Foo", "Foo", f"Foo-{c['slug']}", f"Foo-{c['slug']}-2"]), sx
    print("Export: Kollision weiter gezählt bestanden.")


# --- 20: Seite ohne Titelzeile -----------------------------------------------------------------------------------------

def test_export_ohne_titelzeile_behaelt_titel():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        oben = seite(t.adm, "Probe ohne Kopf", "# Probe ohne Kopf\n")
        # Per API angelegt, nie im Editor gespeichert: keine Zeile „# …“ (eine leer, eine mit Text, eine mit Leerzeilen).
        e1 = seite(t.adm, "Ohne Kopf", "ERSTER TEXT\n", oben["id"])
        e2 = seite(t.adm, "Ohne Kopf", "ZWEITER TEXT\n", oben["id"])
        e3 = seite(t.adm, "Leer Platzhalter", "", oben["id"])
        seite(t.adm, "Mit Kopf", "\n\n# Mit Kopf\n\nTEXT\n", oben["id"])
        _positionen(t.app, (e1, e2, e3))
        r = t.adm.get(f"/api/wiki/pages/{oben['id']}/export?children=1")
        assert r.status_code == 200
        z = zipfile.ZipFile(io.BytesIO(r.data))
        zweite = f"Probe ohne Kopf/Ohne Kopf-{e2['slug']}.md"
        assert z.read(zweite).decode("utf-8") == "# Ohne Kopf\n\nZWEITER TEXT\n"
        assert z.read("Probe ohne Kopf/Ohne Kopf.md").decode("utf-8") == "# Ohne Kopf\n\nERSTER TEXT\n"
        assert z.read("Probe ohne Kopf/Leer Platzhalter.md").decode("utf-8") == "# Leer Platzhalter\n"
        # Eine vorhandene Titelzeile (auch nach Leerzeilen) bleibt unverändert – keine zweite davor.
        assert z.read("Probe ohne Kopf/Mit Kopf.md").decode("utf-8") == "\n\n# Mit Kopf\n\nTEXT\n"
        ziel = seite(t.adm, "Ziel ohne Kopf", "# Ziel ohne Kopf\n")
        imp = importieren(t.adm, r.data, ziel["id"])
        assert imp.status_code == 201, imp.json
        titel = sorted(x["title"] for x in imp.json["seiten"])
        assert titel == ["Leer Platzhalter", "Mit Kopf", "Ohne Kopf", "Ohne Kopf", "Probe ohne Kopf"], titel
        # Einzelexport (.md) trägt die Titelzeile ebenso.
        r = t.adm.get(f"/api/wiki/pages/{e2['id']}/export")
        assert r.status_code == 200 and r.data.decode("utf-8") == "# Ohne Kopf\n\nZWEITER TEXT\n"
        # Gespeichert bleibt der Text wie er war – nur der Export ergänzt.
        assert t.adm.get(f"/api/wiki/pages/{e2['slug']}").json["page"]["content"] == "ZWEITER TEXT\n"
    print("Export ohne Titelzeile bestanden.")


# --- 17: Seitentitel der Riegenkarten ----------------------------------------------------------------------------------

def test_riegenkarten_titel_ohne_namen():
    js = lies("app/static/js/pruefungen.js")
    aufrufe = re.findall(r"S\.titel\(([^;]*)\);", js)
    assert aufrufe, "keine S.titel-Aufrufe gefunden"
    for a in aufrufe:
        assert "tnName" not in a and "tnVoll" not in a and ".vorname" not in a and ".name" not in a, a
    assert 'S.titel(["Prüfungsleistungen", lg.titel], "pruefungen");' in js
    print("Riegenkarten-Titel ohne Namen bestanden.")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
