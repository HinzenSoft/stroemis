"""Leerzeilen im Editor der Strömipedia lassen sich löschen (Wunsch des Nutzers, 11.11.2026):
python tests/test_wiki_leerzeile.py  oder  pytest tests/test_wiki_leerzeile.py

Zwischen zwei Klappboxen wehrte der Löschschutz (editor-layout.js) Rücktaste und Entf ab, weil die Box in Reichweite
stand; zwischen zwei Absätzen kam die Taste durch, änderte aber nichts oder machte aus der gesetzten Leerzeile (&nbsp;)
zwei. Jetzt nimmt jeder Tastendruck genau eine sichtbare Leerzeile weg – Marken, Boxen und Überschriften bleiben, wie
sie sind, eine zugeklappte Box bleibt zu. Stehen bleibt die Leerzeile als ganzer Inhalt eines Abschnitts und als
letzter Block. Nachtrag vom selben Tag: auch von der Nachbarzeile aus – Rücktaste am Anfang der Zeile darunter
(auch eines Box-Titels), Entf am Ende der Zeile darüber (auch des Titels einer zugeklappten Box); eine Zeile aus
unsichtbaren Zeichen gilt als leer, ebenso eine Überschrift ohne Text („#### “). Geprüft im echten Editor (Toast UI mit den Plugins der Strömipedia) in Chromium über echte
Tastenereignisse; die Seite liefert ein kleiner Server aus dem Projektordner. Ohne Chromium übersprungen."""
import functools
import http.server
import json
import os
import sys
import threading
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import CDP, frei, uebersprungen  # noqa: E402

SEITE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<link rel="stylesheet" href="/static/vendor/toastui/toastui-editor.min.css">
<link rel="stylesheet" href="/static/css/app.css"></head>
<body><div class="wiki-editor"><div id="ed"></div></div>
<script src="/static/vendor/marked/marked.min.js"></script>
<script src="/static/vendor/dompurify/purify.min.js"></script>
<script src="/static/js/markdown.js"></script>
<script src="/static/js/editor-format.js"></script>
<script src="/static/vendor/toastui/toastui-editor-all.min.js"></script>
<script src="/static/js/editor-layout.js"></script>
<script src="/static/js/editor-verlauf.js"></script>
<script>
window.ed = EDVERLAUF.oeffnen(() => new toastui.Editor({
  el: document.querySelector("#ed"), height: "600px", initialEditType: "wysiwyg", hideModeSwitch: true,
  usageStatistics: false, initialValue: "", widgetRules: MD.widgetRules(),
  plugins: [EDLAYOUT.layoutPlugin, EDLAYOUT.markenSchuetzen, EDVERLAUF.plugin],
}));
window.gemeldet = [];
document.addEventListener("edlayout:geschuetzt", (e) => gemeldet.push(e.detail.art));
const sicht = () => ed.wwEditor.view;
// Schreibstrich in den n-ten obersten Block, ans Ende, wenn ende gesetzt ist.
window.setze = (md, n, ende) => {
  EDVERLAUF.laden(ed, EDMD.toEditorMd(md));         // wie die Seite: Laden kommt nicht in den Verlauf
  gemeldet.length = 0;
  const v = sicht(); let i = 0, ziel = -1;
  v.state.doc.forEach((k, off) => { if (i++ === n) ziel = ende ? off + k.nodeSize - 1 : off + 1; });
  v.focus();
  v.dispatch(v.state.tr.setSelection(v.state.selection.constructor.create(v.state.doc, ziel)));
};
window.bloecke = () => { const r = []; sicht().state.doc.forEach((k) => r.push(k.type.name === "customBlock" ? "$" + k.attrs.info : k.textContent)); return r; };
window.strich = () => { const $ = sicht().state.selection.$from; return [$.parent.textContent, $.parentOffset]; };
window.zu = () => [...document.querySelectorAll(".toastui-editor-contents > .ak-versteckt")].map((e) => e.textContent);
window.md = () => EDMD.fromEditorMd(ed.getMarkdown());
</script></body></html>"""

ZWEI_BOXEN = ":::accordion Eins\nA\n:::\n\n{}\n\n:::accordion Zwei\nB\n:::\n\nEnde."
TASTE = {"Backspace": 8, "Delete": 46}


class _Seite(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/probe.html":
            daten = SEITE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)
            return
        if self.path.startswith("/static/"):                # wie in der App: /static/ ist app/static/
            self.path = "/app" + self.path
        super().do_GET()

    def log_message(self, *args):
        pass


class Editor:
    def __enter__(self):
        sys.path.insert(0, CDP)
        from cdp import Browser
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", frei()), functools.partial(_Seite, directory=WURZEL))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.b = Browser(port=frei())
        self.b.oeffnen(f"http://127.0.0.1:{self.server.server_address[1]}/probe.html", warten=1.0)
        for _ in range(50):
            if self.b.js("typeof window.setze === 'function' && !!window.ed"):
                break
            time.sleep(0.1)
        return self

    def __exit__(self, *args):
        self.b.schliessen()
        self.server.shutdown()
        self.server.server_close()

    def js(self, ausdruck):
        return self.b.js(ausdruck)

    def setze(self, md, n, ende=False):
        self.js(f"setze({json.dumps(md)}, {n}, {json.dumps(ende)})")

    def taste(self, name):
        for art in ("rawKeyDown", "keyUp"):
            self.b.rufen("Input.dispatchKeyEvent", type=art, key=name, code=name, windowsVirtualKeyCode=TASTE.get(name, 0))
        time.sleep(0.1)

    def strg_z(self):
        for art in ("rawKeyDown", "keyUp"):
            self.b.rufen("Input.dispatchKeyEvent", type=art, key="z", code="KeyZ", windowsVirtualKeyCode=90, modifiers=2)
        time.sleep(0.1)

    def stand(self):
        return {"md": self.js("md()"), "strich": self.js("strich()"), "gemeldet": self.js("gemeldet"),
                "zu": self.js("zu()"), "bloecke": self.js("bloecke()")}


def _lauf(e):
    # 1. Leerzeile zwischen zwei zugeklappten Boxen – gesetzt (&nbsp;) und als <br>, beide Tasten, Strich am Anfang
    #    und am Ende der Zeile. Danach stehen die Boxen direkt untereinander und bleiben zu.
    for leer in ("&nbsp;", "<br>"):
        for taste in ("Backspace", "Delete"):
            for ende in (False, True):
                e.setze(ZWEI_BOXEN.format(leer), 5, ende)
                assert e.js("bloecke()[5]").strip() == "", e.js("bloecke()")
                e.taste(taste)
                s = e.stand()
                fall = (leer, taste, ende, s)
                assert s["md"] == ":::accordion Eins\nA\n:::\n\n:::accordion Zwei\nB\n:::\n\nEnde.", fall
                assert s["gemeldet"] == [], fall
                assert s["strich"] == (["Eins", 4] if taste == "Backspace" else ["Zwei", 0]), fall
                assert s["zu"] == ["", "A", "", "B"], fall              # Trennmarke und Körper beider Boxen versteckt

    # 2. Zurücknehmen bringt die Zeile wieder (Pause: dichte Schritte fasst der Verlauf zusammen).
    e.setze(ZWEI_BOXEN.format("&nbsp;"), 5)
    time.sleep(0.6)
    e.taste("Backspace")
    e.strg_z()
    assert e.js("md()") == ZWEI_BOXEN.format("&nbsp;"), e.js("md()")

    # 3. Die obere Box ist aufgeklappt: Der Strich landet am Ende ihres Inhalts, nicht im Titel.
    e.setze(ZWEI_BOXEN.format("&nbsp;"), 3, True)                       # in „A“ – die Box klappt dabei auf
    e.js("(() => { const v = sicht(); let o = 0, i = 0; v.state.doc.forEach((k, off) => { if (i++ === 5) o = off + 1; });"
         " v.dispatch(v.state.tr.setSelection(v.state.selection.constructor.create(v.state.doc, o))); })()")
    e.taste("Backspace")
    s = e.stand()
    assert s["md"] == ":::accordion Eins\nA\n:::\n\n:::accordion Zwei\nB\n:::\n\nEnde.", s
    assert s["strich"] == ["A", 1] and s["zu"] == ["", "B"], s

    # 4. Zwei Leerzeilen zwischen den Boxen: ein Tastendruck, eine Zeile weniger – mit der Fuge zwischen den beiden
    #    gesetzten Leerzeilen, sonst stünde sie danach als leere Zeile da.
    for taste in ("Backspace", "Delete"):
        e.setze(ZWEI_BOXEN.format("&nbsp;\n\n&nbsp;"), 5)
        e.taste(taste)
        s = e.stand()
        assert s["md"] == ZWEI_BOXEN.format("&nbsp;"), (taste, s)
        assert s["gemeldet"] == [], (taste, s)

    # 5. Zwischen zwei Absätzen: vorher blieb alles, wie es war, oder aus einer Leerzeile wurden zwei.
    for taste in ("Backspace", "Delete"):
        for ende in (False, True):
            e.setze("Text.\n\n&nbsp;\n\nText2.", 2, ende)
            e.taste(taste)
            s = e.stand()
            assert s["md"] == "Text.\n\nText2.", (taste, ende, s)
            assert s["strich"] == (["Text.", 5] if taste == "Backspace" else ["Text2.", 0]), (taste, ende, s)
            e.setze("Text.\n\n&nbsp;\n\n&nbsp;\n\nText2.", 2, ende)
            e.taste(taste)
            assert e.js("md()") == "Text.\n\n&nbsp;\n\nText2.", (taste, ende, e.js("md()"))

    # 6. Entf vor einer Überschrift: Die Leerzeile geht, die Überschrift bleibt Überschrift.
    e.setze("Text.\n\n&nbsp;\n\n## Kopf\n\nMehr.", 2)
    e.taste("Delete")
    s = e.stand()
    assert s["md"] == "Text.\n\n## Kopf\n\nMehr.", s
    assert s["strich"] == ["Kopf", 0], s

    # 7. Vor einer Tabelle, hinter einem Hinweis.
    e.setze("Davor.\n\n:::info\nX\n:::\n\n&nbsp;\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nDanach.", 4)
    assert e.js("bloecke()[4]").strip() == "", e.js("bloecke()")
    e.taste("Delete")
    s = e.stand()
    assert s["md"] == "Davor.\n\n:::info 💡\nX\n:::\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nDanach.", s
    assert s["gemeldet"] == [] and s["strich"] == ["A", 0], s

    # 8. Stehen bleibt sie als ganzer Inhalt eines Hinweises und als letzter Block – dort wehrt der Schutz wie
    #    bisher ab und meldet sich.
    e.setze("Davor.\n\n:::info\n&nbsp;\n:::\n\nDanach.", 2)
    vorher = e.js("md()")
    e.taste("Backspace")
    s = e.stand()
    assert s["md"] == vorher and s["gemeldet"] == ["hinweis"], s
    e.setze(":::accordion Eins\nA\n:::\n\n&nbsp;", 5)              # die letzte Leerzeile schreibt Toast UI nicht mit
    e.taste("Backspace")
    s = e.stand()
    assert len(s["bloecke"]) == 6 and s["gemeldet"] == ["akkordeon"], s

    # 9. Der Schutz selbst bleibt: Rücktaste am Anfang eines Absatzes direkt hinter einer Box löscht nichts.
    e.setze(":::accordion Eins\nA\n:::\n\nDanach.", 5)
    e.taste("Backspace")
    s = e.stand()
    assert s["md"] == ":::accordion Eins\nA\n:::\n\nDanach." and s["gemeldet"] == ["akkordeon"], s

    # 10. Nachtrag (Rückmeldung „lässt sich immer noch nicht löschen“): von der Zeile darunter bzw. darüber aus.
    #     Rücktaste am Anfang des Titels der unteren Box, Entf am Ende des Titels der oberen, zugeklappten Box – die
    #     Leerzeile geht, der Strich bleibt, beide Boxen bleiben zu, nichts wird gemeldet.
    for leer in ("&nbsp;", "<br>", "&#8203;"):
        for taste, block, ende, strich in (("Backspace", 7, False, ["Zwei", 0]), ("Delete", 1, True, ["Eins", 4])):
            e.setze(ZWEI_BOXEN.format(leer), block, ende)
            assert e.js("strich()") == strich, e.js("strich()")
            e.taste(taste)
            s = e.stand()
            fall = (leer, taste, s)
            assert s["md"] == ":::accordion Eins\nA\n:::\n\n:::accordion Zwei\nB\n:::\n\nEnde.", fall
            assert s["gemeldet"] == [] and s["strich"] == strich and s["zu"] == ["", "A", "", "B"], fall

    # 11. Ist die obere Box offen, liegt unter ihrem Titel ihr Inhalt: Entf am Titelende wehrt wie bisher ab.
    e.setze(ZWEI_BOXEN.format("&nbsp;"), 3)                              # in „A“ – die Box klappt dabei auf
    e.js("(() => { const v = sicht(); let o = 0, i = 0; v.state.doc.forEach((k, off) => { if (i++ === 1) o = off + k.nodeSize - 1; });"
         " v.dispatch(v.state.tr.setSelection(v.state.selection.constructor.create(v.state.doc, o))); })()")
    e.taste("Delete")
    s = e.stand()
    assert s["md"] == ZWEI_BOXEN.format("&nbsp;") and s["gemeldet"] == ["akkordeon"], s

    # 12. Ohne Leerzeile zwischen den Boxen bleibt der Schutz: Rücktaste am Anfang des unteren Titels löscht nichts.
    e.setze(":::accordion Eins\nA\n:::\n\n:::accordion Zwei\nB\n:::", 6)
    assert e.js("strich()") == ["Zwei", 0], e.js("strich()")
    e.taste("Backspace")
    s = e.stand()
    assert s["md"] == ":::accordion Eins\nA\n:::\n\n:::accordion Zwei\nB\n:::" and s["gemeldet"] == ["akkordeon"], s

    # 13. Zwischen Absätzen und vor einer Überschrift, von der Nachbarzeile aus. Vorher machte die Rücktaste am Anfang
    #     von „Text2.“ aus der gesetzten Leerzeile eine zweite.
    for md, nach, unten in (("Text.\n\n&nbsp;\n\nText2.", "Text.\n\nText2.", "Text2."),
                            ("Text.\n\n&nbsp;\n\n## Kopf\n\nMehr.", "Text.\n\n## Kopf\n\nMehr.", "Kopf")):
        e.setze(md, 0)
        b = e.js("bloecke()")
        for taste, block, ende, strich in (("Backspace", b.index(unten), False, [unten, 0]),
                                           ("Delete", 0, True, ["Text.", 5])):
            e.setze(md, block, ende)
            e.taste(taste)
            s = e.stand()
            assert s["md"] == nach and s["strich"] == strich and s["gemeldet"] == [], (md, taste, s)

    # 14. Zweiter Nachtrag (Rückmeldung mit dem Artikeltext): Die Zeile zwischen den Boxen war eine Überschrift ohne
    #     Text („#### “). Sie geht wie eine leere Zeile – in ihr wie von den Titeln daneben aus; vorher wehrte der Schutz
    #     alle vier Wege ab. Eine Überschrift mit Text bleibt.
    for kopf in ("#### ", "## "):
        for taste, block, ende, strich in (("Backspace", 5, False, ["Eins", 4]), ("Delete", 5, False, ["Zwei", 0]),
                                           ("Backspace", 7, False, ["Zwei", 0]), ("Delete", 1, True, ["Eins", 4])):
            e.setze(ZWEI_BOXEN.format(kopf), block, ende)
            e.taste(taste)
            s = e.stand()
            fall = (kopf, taste, block, s)
            assert s["md"] == ":::accordion Eins\nA\n:::\n\n:::accordion Zwei\nB\n:::\n\nEnde.", fall
            assert s["gemeldet"] == [] and s["strich"] == strich and s["zu"] == ["", "A", "", "B"], fall
    for taste, block, ende, strich in (("Backspace", 1, False, ["Text.", 5]), ("Delete", 1, False, ["Text2.", 0]),
                                       ("Backspace", 2, False, ["Text2.", 0]), ("Delete", 0, True, ["Text.", 5])):
        e.setze("Text.\n\n#### \n\nText2.", block, ende)
        e.taste(taste)
        s = e.stand()
        assert s["md"] == "Text.\n\nText2." and s["strich"] == strich and s["gemeldet"] == [], (taste, block, s)
    e.setze("Text.\n\n## Kopf\n\nText2.", 1)
    e.taste("Backspace")
    assert "Kopf" in e.js("md()"), e.js("md()")


def test_leerzeilen_loeschen():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Editor() as e:
        _lauf(e)
        fehler = [f for f in e.b.fehler() if "favicon" not in f]
        assert not fehler, fehler


def test_quelltext():
    with open(os.path.join(WURZEL, "app/static/js/editor-layout.js"), encoding="utf-8") as fh:
        js = fh.read()
    # Die Leerzeile kommt vor dem Schutz an die Reihe – sonst wehrte er zwischen zwei Boxen weiter ab.
    taste = js[js.index("handleKeyDown(sicht, ereignis) {"):]
    assert taste.index("leerzeileLoeschen(") < taste.index("loeschenAbwehren(")


if __name__ == "__main__":
    test_quelltext()
    test_leerzeilen_loeschen()
    print("ok")
