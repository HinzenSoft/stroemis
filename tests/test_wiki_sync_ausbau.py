"""Auftrag des Nutzers vom 13.11.2026: „Entferne die Funktion synchronisierter Abschnitte“.
python tests/test_wiki_sync_ausbau.py  oder  pytest tests/test_wiki_sync_ausbau.py

Entscheidungen des Nutzers: Ein synchronisierter Abschnitt (":::baustein kennung" … ":::") verliert nur sein Markenpaar,
der Text bleibt, wo er steht; ein Einbau (":::einbau seite#kennung" + ":::") wird ein Link auf die Seite; vorhandene
Seiten werden beim Start einmalig still umgeschrieben (ohne Fassung im Verlauf). Geprüft: das Auflösen selbst
(Verschachtelung, Codeblöcke, einzeilige Kisten, Einzug, keine zusammenwachsenden Absätze, Titel mit Klammern, alte
Adresse, fehlende Seite, wiederholbar), der Startschritt an einem Bestand mit db.DERIVED_VERSION 5 (Inhalt, Version,
Verlauf, Rückverweise, auch im Papierkorb) und dass Katalog und Einbau-Kennzeichen am Server fort sind."""
import os
import sqlite3
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from test_material import make_app  # noqa: E402

H = {"X-Requested-With": "XMLHttpRequest"}


def _anmelden(app):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": "admin@example.org", "password": "geheim123"}).status_code == 200
    return c


def _seite(c, titel, inhalt=""):
    r = c.post("/api/wiki/pages", json={"title": titel, "content": inhalt})
    assert r.status_code == 201, r.get_json()
    return r.json["page"]


def test_aufloesen():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = _anmelden(app)
        ziel = _seite(c, "Ankertechnik [Grundlagen]", "Text.")
        alt = _seite(c, "Umbenannt", "Text.")
        with app.app_context():
            from app import db
            from app.api_wiki import sync_abschnitte_aufloesen as auf
            db.execute("INSERT INTO wiki_slugs (slug, page_id) VALUES ('frueher-name', ?)", (alt["id"],))
            link = f"→ Abschnitt „sicherung“ auf der Seite [Ankertechnik \\[Grundlagen\\]](/stroemipedia/{ziel['slug']})"
            faelle = [
                # Markenpaar weg, Text samt Formatierung bleibt
                ("Davor.\n\n:::baustein sicherung\nInhalt **fett**.\n:::\n\nDanach.",
                 "Davor.\n\nInhalt **fett**.\n\nDanach."),
                # ohne Leerzeilen drumherum: Die Absätze wachsen nicht zusammen
                ("Text\n:::baustein a\nInhalt\n:::\nWeiter", "Text\n\nInhalt\n\nWeiter"),
                # Einbau → Link (Titel mit Klammern maskiert), auch eingerückt und unter einer alten Adresse
                (f":::einbau {ziel['slug']}#sicherung\n:::", link),
                (f"Davor.\n  :::einbau {ziel['slug']}#sicherung\n  :::\nDanach.", f"Davor.\n\n{link}\n\nDanach."),
                (":::einbau frueher-name#teil\n:::",
                 f"→ Abschnitt „teil“ auf der Seite [Umbenannt](/stroemipedia/{alt['slug']})"),
                (":::einbau gibt-es-nicht#teil\n:::", "→ Abschnitt „teil“ auf der Seite „gibt-es-nicht“"),
                # verschachtelt: Die Marken der anderen Kästen bleiben, wo sie waren
                (":::info 💡\n:::baustein drin\nText\n:::\n:::", ":::info 💡\nText\n:::"),
                (":::baustein quer\n:::warning ⚠️\nX\n:::\n:::", ":::warning ⚠️\nX\n:::"),
                (":::columns\n:::baustein links\nA\n:::\n|||\n:::einbau gibt-es-nicht#b\n:::\n:::",
                 ":::columns\nA\n|||\n→ Abschnitt „b“ auf der Seite „gibt-es-nicht“\n:::"),
                # eine einzeilige Kiste im Abschnitt zählt nicht als öffnende Marke
                (":::baustein k\n:::info Kurz :::\nText\n:::\n\nDanach.", ":::info Kurz :::\nText\n\nDanach."),
                # im Codeblock ist es Text
                ("```\n:::baustein code\nx\n:::\n```", "```\n:::baustein code\nx\n:::\n```"),
            ]
            for vorher, soll in faelle:
                ist = auf(vorher)
                assert ist == soll, (vorher, ist, soll)
                assert auf(ist) == ist, ("wiederholbar", ist)
            ohne = "Nichts zu tun.\n\n:::info 💡\nKiste\n:::"
            assert auf(ohne) is ohne and auf("") == "" and auf(None) is None


def test_startschritt():
    with tempfile.TemporaryDirectory() as tmp:
        app = make_app(tmp)
        c = _anmelden(app)
        quelle = _seite(c, "Quelle", ":::baustein sicherung\nGeteilter Text.\n:::")
        nutzer = _seite(c, "Nutzer", f"Davor.\n\n:::einbau {quelle['slug']}#sicherung\n:::\n\nDanach.")
        papierkorb = _seite(c, "Weg", ":::baustein alt\nIm Papierkorb.\n:::")
        unberuehrt = _seite(c, "Ohne", "Nur Text.")
        assert c.delete(f"/api/wiki/pages/{papierkorb['id']}", headers=H).status_code == 200
        pfad = app.config["DB_PATH"]
        # Stand vor dem Ausbau: abgeleitete Tabellen auf Version 5
        con = sqlite3.connect(pfad)
        con.execute("PRAGMA user_version = 5")
        vorher = {r[0]: (r[1], r[2]) for r in con.execute("SELECT id, version, content FROM wiki_pages")}
        fassungen = con.execute("SELECT COUNT(*) FROM wiki_revisions").fetchone()[0]
        con.commit()
        con.close()

        app2 = make_app(tmp)                     # Neustart: DERIVED_VERSION 6 löst die Marken auf
        con = sqlite3.connect(pfad)
        nachher = {r[0]: (r[1], r[2]) for r in con.execute("SELECT id, version, content FROM wiki_pages")}
        assert con.execute("PRAGMA user_version").fetchone()[0] == 6
        assert con.execute("SELECT COUNT(*) FROM wiki_revisions").fetchone()[0] == fassungen      # still, ohne Fassung
        con.close()
        assert nachher[quelle["id"]][1] == "Geteilter Text."
        assert nachher[nutzer["id"]][1] == (f"Davor.\n\n→ Abschnitt „sicherung“ auf der Seite "
                                            f"[Quelle](/stroemipedia/{quelle['slug']})\n\nDanach.")
        assert nachher[papierkorb["id"]][1] == "Im Papierkorb."
        assert nachher[unberuehrt["id"]] == vorher[unberuehrt["id"]]
        for p in (quelle, nutzer, papierkorb):
            assert nachher[p["id"]][0] == vorher[p["id"]][0] + 1, p["title"]   # ein offener Editor schreibt nicht darüber

        c2 = _anmelden(app2)
        # Der Link ist ein gewöhnlicher Verweis – ohne Einbau-Kennzeichen; den Katalog gibt es nicht mehr
        rueck = c2.get(f"/api/wiki/pages/{quelle['id']}/backlinks").json["pages"]
        assert rueck == [{"id": nutzer["id"], "title": "Nutzer", "slug": nutzer["slug"], "icon": ""}], rueck
        assert c2.get("/api/wiki/bausteine").status_code == 404
        # Ein zweiter Neustart ändert nichts mehr
        make_app(tmp)
        con = sqlite3.connect(pfad)
        assert {r[0]: (r[1], r[2]) for r in con.execute("SELECT id, version, content FROM wiki_pages")} == nachher
        con.close()


if __name__ == "__main__":
    test_aufloesen()
    test_startschritt()
    print("ok")
