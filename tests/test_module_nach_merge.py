"""Lieferung nach dem Merge, Teil B – Strömipedia, Ankerplätze, Riegenkarten, Leitstelle, Anmeldung (27.10.2026):
python tests/test_module_nach_merge.py  oder  pytest tests/test_module_nach_merge.py

Punkte der nach_merge_liste:
  16  Wiki-Export: „-<slug>“ ist selbst vergeben (drittes Geschwister „Foo-<slug>“) → weiter zählen, bis der Pfad frei
      ist; der Import liest den Export wieder ein (Fall der Probe q06_wiki_export.py).
  20  Export → Import: Seite ohne „# Titel“ mit gleichnamigem Geschwister behält ihren Titel (der Export schreibt die
      Titelzeile), auch der Einzelexport.
  17  Riegenkarten: kein Name von Teilnehmenden im Seitentitel (Browserverlauf).
  9/10 Leitstelle: „Globale Suchen“ höchstens 100ch, Spalten Name/E-Mail/Gliederung breiter.
  12  Tippflächen ≥ 44 px unter pointer: coarse (Dialoge, Anmeldung, Kommentar-Aktionen, Sortierpfeile, „Kopieren“,
      Album-Panel, Haken und Stempel der Riegenkarten).
  13  Knopfsprache: kein btn ghost, keine Emoji in Knöpfen, eine rote Hauptaktion, btn danger nur in der Rückfrage,
      Zeilenmenü „Mehr“ (app-weit in common.js), Sprunglink „Zum Inhalt“, „Teilnehmende“ statt „TN“/„Teilnehmende:r“.
  14  Reset-Mail mit Rückfrage, Einstellungen ohne Entwicklersprache, Lehrgangsliste auf Ultrawide begrenzt.
Die Oberflächenpunkte sind im Browser gemessen (Bericht); hier die Stellen im Code, an denen die Lösungen hängen. Alle
Namen und Seiten sind Platzhalter."""
import io
import os
import re
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_smoke import H  # noqa: E402
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



# --- 13: Knopfsprache und Sprunglink -----------------------------------------------------------------------------------

ALTE_MODULE = ("app/static/js/pruefungen.js", "app/static/js/wiki.js", "app/static/js/map.js", "app/static/js/admin.js",
               "app/templates/wiki.html", "app/templates/index.html", "app/templates/admin.html")
# Emoji und Bildzeichen, die als Knopfbeschriftung nichts zu suchen haben (☰ und ⋯ als Menüzeichen bleiben erlaubt,
# ‹ › × in Großansicht und Panel ebenso).
BILDZEICHEN = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u25A0-\u25FF]")


def test_knopfsprache_alte_module():
    for pfad in ALTE_MODULE:
        text = lies(pfad)
        assert "btn ghost" not in text.replace("(btn ghost)", ""), pfad
        for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", text, re.S):
            # Bewusst geblieben (Bericht, „Bitte bestätigen“): Zustandszeichen in den Bewertungszellen, 👍/👎 der großen
            # Bewertungswahl am Gewässer (immer mit Wort) und das Farbfeld „keine Farbe“ im Callout-Menü.
            if 'data-act="zelle"' in m.group(1) or "data-erg=" in m.group(1) or 'class="farbe' in m.group(1):
                continue
            innen = re.sub(r"\$\{[^}]*\}", "", m.group(2))
            assert not BILDZEICHEN.search(innen.replace("☰", "")), (pfad, m.group(0)[:160])
    assert ".btn.ghost" not in lies("app/static/css/app.css")
    pr = lies("app/static/js/pruefungen.js")
    # btn danger nur noch in der Rückfrage (common.js S.confirm), nicht als Auslöser.
    for pfad in ("app/static/js/pruefungen.js", "app/static/js/map.js"):
        assert "btn danger" not in lies(pfad), pfad
    assert 'class="btn danger small" data-act="reject"' not in lies("app/static/js/admin.js")
    assert '<button class="btn danger" id="c-ok" type="button">' in lies("app/static/js/common.js")
    # Lehrgangs- und Katalogliste: „Öffnen“ grau, Seltenes im Zeilenmenü; je Leistung „Bearbeiten“ + „Mehr“.
    assert '<a class="btn secondary small" href="/riegenkarten/${lg.id}">Öffnen</a>' in pr
    assert pr.count("zeilenMenue(`") == 3
    assert 'const zeilenMenue = (eintraege) => `<details class="zeilenmenue">' in pr
    # Eine rote Hauptaktion: Mängel-Reiter und Stoppuhr grau, „Bewertung speichern“ rot.
    assert '<button class="btn secondary small" data-act="m-np"' in pr
    assert '<button type="button" class="btn secondary" data-su="start">Start</button>' in pr
    # Zeilenmenü app-weit: Schließen per Klick daneben und Escape in common.js, nicht mehr nur in admin.js.
    co = lies("app/static/js/common.js")
    assert 'document.querySelectorAll("details.zeilenmenue[open]")' in co
    assert 'details.zeilenmenue[open]' not in lies("app/static/js/admin.js")
    # Kopfleiste der Strömipedia: Sprechblase als Symbol statt Emoji, grau umrandet.
    wiki = lies("app/static/js/wiki.js")
    assert 'aria-label="Kommentieren">${I.kommentar}</button>' in wiki and "kommentar: ico(" in wiki
    assert wiki.count('class="btn secondary small kopfknopf') == 7
    print("Knopfsprache bestanden.")


def test_sprunglink_und_begriffe():
    with tempfile.TemporaryDirectory() as tmp:
        t = aufbau(tmp)
        anon = t.app.test_client()
        for c, pfad in ((anon, "/login"), (t.adm, "/leitstelle"), (t.adm, "/riegenkarten"), (t.adm, "/ankerplaetze")):
            r = c.get(pfad)
            assert r.status_code == 200, pfad
            text = r.get_data(as_text=True)
            # Erster Tab-Stopp: der Sprunglink, sein Ziel direkt hinter der Kopfleiste.
            body = text[text.index("<body"):]
            assert re.search(r"<body[^>]*>\s*(?:\{#.*?#\}\s*)?<a class=\"sprunglink\" href=\"#inhalt\">Zum Inhalt</a>", body), pfad
            assert '<span id="inhalt" class="sprungziel" tabindex="-1"></span>' in text, pfad
            assert body.index('id="inhalt"') > body.index("</header>"), pfad
        assert '<a class="sprunglink" href="#inhalt">Zum Inhalt</a>' in lies("app/templates/public.html")
        # Reset-Mail: Meldung ohne Mailserver in Alltagssprache; im Menü mit Rückfrage.
        uid = [u for u in t.adm.get("/api/admin/users").json["users"] if u["email"] == "mitglied@example.org"][0]["id"]
        r = t.adm.post(f"/api/admin/users/{uid}/reset-mail", json={}, headers=H)
        assert r.status_code == 200 and r.json["message"] == "Kein Mailserver eingerichtet – der Link steht im Protokoll des Servers.", r.json
    admin = lies("app/static/js/admin.js")
    assert 'S.confirm(`Eine Mail zum Zurücksetzen des Passworts an ${u.email} senden?`, "Senden")' in admin
    assert "Server-Log" not in admin and "in allen\n      Arbeitsprozessen" not in lies("app/templates/admin.html")
    pr = lies("app/static/js/pruefungen.js")
    for alt in ("Teilnehmende:r", "Teilnehmende:n", "je TN<", ">TN<", " TN mit "):
        assert alt not in pr, alt
    print("Sprunglink und Begriffe bestanden.")


# --- 9, 10, 12, 14: Regeln im Stylesheet -------------------------------------------------------------------------------

def test_stylesheet_regeln():
    css = lies("app/static/css/app.css")
    block = css[css.index("Lieferung nach dem Merge, Teil B"):]
    assert "#mat-globalsuche .accordion-body > p.help { max-width: 100ch; }" in block
    assert ".page.breit.leitstelle { max-width: 1280px; }" in block
    coarse = block[block.index("@media (pointer: coarse) {"):]
    for regel in ("dialog select, dialog .btn { min-height: 44px; }",
                  ".login-form input, .login-form .btn { min-height: 44px; }",
                  ".login-links a { display: inline-flex; align-items: center; min-height: 44px; }",
                  ".c-actions .lnk { min-height: 44px;", ".th-sort { right: 0; width: 44px; height: 44px;",
                  ".code-copy { min-height: 44px;", ".panel .btn { min-height: 44px; }", ".lb-nav { min-width: 44px; }"):
        assert regel in coarse, regel
    # Touch-Regeln nur unter pointer: coarse – außerhalb des Blocks keine 44-px-Mindesthöhen.
    ausserhalb = block[:block.index("@media (pointer: coarse) {")]
    assert "44px" not in ausserhalb
    pcss = lies("app/static/css/pruefungen.css")
    assert ".vk input[type=checkbox] { width: 44px; height: 44px; }" in pcss
    assert ".vk-stempel { min-height: 44px; display: inline-flex; align-items: center; }" in pcss
    assert ".pruef[data-ansicht=liste], .pruef[data-ansicht=kataloge] { max-width: 1280px; }" in pcss
    assert "ghost" not in pcss
    admin = lies("app/templates/admin.html")
    assert '<col style="width:11%"><col style="width:12%"><col style="width:12%">' in admin
    assert '<main class="page breit leitstelle">' in admin
    print("Stylesheet-Regeln bestanden.")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
