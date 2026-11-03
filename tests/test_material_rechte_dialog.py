"""Dialog „Rechte ändern“ mit Rollen wie beim Anlegen (Wunsch des Nutzers vom 02.11.2026):
python tests/test_material_rechte_dialog.py  oder  pytest tests/test_material_rechte_dialog.py

Geprüft wird hier:
  - statisch: dieselben Rollenkarten in „Freigabe anlegen“ und „Rechte ändern“, die Gültigkeit als Radiogruppe
    „dauerhaft / bis [Datum]“ in beiden (kein „Grundrecht bis“/„Prüfen bis“ mit Kästchen „dauerhaft“ mehr), „Grundrecht“
    nur unter „Einzeln“, Gründe als Satz, Erklärungen im „i“, Notiz zugeklappt, Touch-Regeln nur unter pointer: coarse;
  - mit Node.js die reinen Teile aus freigaben.js: Zuordnung Rechte → Rolle (alle Fälle), warum eine Rolle nicht geht,
    was eine Rolle an die Schnittstelle schickt;
  - gegen die Schnittstelle: Jede Rolle ergibt über die Abbildung aus freigaben.js die erwarteten Rechte (anlegen und
    ändern), eigene Rechte nur herab, Prüfen nur mit Qualifikation, externer Prüfer höchstens 24 Monate – und was der
    Dialog ausgraut, lehnt auch der Server ab.
Seit dem 03.11.2026 („Prüfen folgt dem Grundrecht“, Entscheidung des Nutzers): Das Prüfen der Rollen mit Grundrecht ist
immer dauerhaft, auch vom befristeten Verwalter; ein Datum ist nur beim externen Prüfer vorbelegt (Gültigkeitszeile mit
Node.js und nachgebautem DOM); der Fall aus dem Anlass (befristet über 24 Monate hinaus verwaltet, „Prüfer“ mit dem
eigenen Ende) gegen die Schnittstelle. Alle Konten, Namen und Nummern sind Platzhalter."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_material import H, _heute, freigeben, gliederung, neues_konto, umgebung  # noqa: E402
from test_material_ueberblick import ordner_neu  # noqa: E402

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRG = os.path.join(WURZEL, "app/material/static/freigaben.js")
FR = "/api/material/ordner/{}/freigaben"
PERSON = "/api/material/ordner/{}/freigaben/person/{}"


def lies(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def tag(n):
    return (_heute() + timedelta(days=n)).isoformat()


def abschnitt(text, anfang, ende):
    a = text.index(anfang)
    return text[a:text.index(ende, a)]


def coarse_bloecke(css):
    """Inhalt aller @media (pointer: coarse) { … }-Blöcke (Klammern gezählt)."""
    out = []
    for m in re.finditer(r"@media \(pointer: coarse\) \{", css):
        tiefe, i = 1, m.end()
        while tiefe:
            tiefe += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return "\n@@\n".join(out)


# --- Node.js: die reinen Teile aus freigaben.js ---------------------------------------------------------------

NODE = shutil.which("node")
SKRIPT = r"""
const fs = require("fs");
const js = fs.readFileSync(process.argv[1], "utf8");
const teil = (a, b) => { const i = js.indexOf(a); return js.slice(i, js.indexOf(b, i)); };
const code = teil("  /* Die Rollen (Nutzer 02.11.2026", "  // Die Erklärungen hinter den")
  + teil("  /* Die Rolle zu den heutigen Rechten", "  /* Gültigkeit als Radiogruppe");
const f = new Function(code + `; return { ROLLEN, rolleMit, rolleZu, rollenGruende, rolleAnlegen, rolleAendern,
  texte: { OHNE_QUALIFIKATION, EIGENE_NEU, EIGENE_MEHR, FEST_ROLLE, NUR_PV_HERAB, OHNE_ZUGANG_MEHR, PRUEFEN_FOLGT } };`)();
// Die Gültigkeitszeile (gueltig) mit einem nachgebauten DOM: zwei Radioknöpfe, Datumsfeld, Hilfezeile.
const gcode = teil("  // „2027-12-31“ → „31.12.2027“", "  /* Datumsfelder wie im Modul")
  + teil("  function datumWert(feld, name) {", "  /* Zustand einer Zeile")
  + teil("  // Ein Fehler mit dem Feld,", "  // Ablehnungen des Servers");
const G = new Function("$", gcode + "; return { gueltig, eigenesEndeText };")((sel, el) => el.querySelector(sel));
function element(mehr) {
  const hoerer = {};
  const klassen = new Set();
  return Object.assign({ value: "", hidden: false, textContent: "",
    classList: { toggle: (k, an) => (an ? klassen.add(k) : klassen.delete(k)), contains: (k) => klassen.has(k),
      remove: (k) => klassen.delete(k), add: (k) => klassen.add(k) },
    addEventListener: (t, h) => { (hoerer[t] = hoerer[t] || []).push(h); },
    feuern: (t) => (hoerer[t] || []).forEach((h) => h({})) }, mehr);
}
function zeile(vorschlag) {
  let wahl = null;
  const knopf = (v) => { const r = element(); Object.defineProperty(r, "checked", { get: () => wahl === v,
    set: (x) => { if (x) wahl = v; else if (wahl === v) wahl = null; } }); return r; };
  const dauer = knopf("dauerhaft");
  const bis = knopf("bis");
  const gruppe = element({ getAttribute: () => "Gültig", querySelector: (s) => (s.includes("dauerhaft") ? dauer : bis) });
  const feld = element();
  const hilfe = element({ hidden: true });
  const wurzel = { querySelector: (s) => ({ "#z": gruppe, "#z-bis": feld, "#z-hilfe": hilfe })[s] };
  let rufe = 0;
  const g = G.gueltig(wurzel, "z", vorschlag, () => { rufe += 1; });
  const stand = () => ({ wahl, feld: feld.value, nurBis: gruppe.classList.contains("nur-bis"), vomNutzer: g.vomNutzer(),
    dauerhaft: g.dauerhaft(), wert: (() => { try { return g.wert(); } catch (e) { return { fehler: e.message, amFeld: e.feld === feld }; } })() });
  const klick = (r) => { r.checked = true; r.feuern("change"); };
  return { g, stand, dauer, bis, feld, klick, rufe: () => rufe };
}
function gueltigFaelle() {
  const out = {};
  // Ohne Vorschlag (alle Rollen außer dem externen Prüfer): „bis“ wählen lässt das Feld leer; Speichern → Fehler am Feld.
  let z = zeile(null);
  z.g.setzen(null);
  out.dauerhaft = z.stand();
  z.klick(z.bis);
  out.bisGeklickt = z.stand();
  // Befristeter Verwalter: „dauerhaft“ geht nicht – „bis“ mit leerem Feld, Satz ohne „oder dauerhaft“.
  z = zeile(null);
  z.g.setzen("");
  z.g.erlauben(false);
  out.nurBisLeer = z.stand();
  // „dauerhaft“ war gewählt und ging nicht mehr (Einzeln: Grundrecht abgewählt) – geht es wieder, kommt es zurück.
  z = zeile(null);
  z.g.setzen(null);
  z.g.erlauben(false);
  out.erzwungen = z.stand();
  z.g.erlauben(true);
  out.zurueck = z.stand();
  // Der Nutzer tippt ein Datum: angefasst – ein Rollenwechsel ließe es; setzen() fängt neu an.
  z = zeile(null);
  z.g.setzen(null);
  z.feld.value = "31.12.2026";
  z.feld.feuern("input");
  out.getippt = z.stand();
  z.g.setzen("2027-06-30");
  out.neuGesetzt = z.stand();
  // Mit Vorschlag (externer Prüfer): erzwungenes „bis“ bekommt ihn, ein schon gefülltes Feld bleibt.
  z = zeile(() => "2027-12-31");
  z.g.setzen(null);
  z.g.erlauben(false);
  out.extern = z.stand();
  z = zeile(() => "2027-12-31");
  z.g.setzen("2027-03-31");
  z.g.erlauben(false);
  out.externGespeichert = z.stand();
  out.eigenesEnde = [G.eigenesEndeText("2028-11-02"), G.eigenesEndeText(null)];
  return out;
}
const aufrufe = JSON.parse(process.argv[2]);
const aus = aufrufe.map(([was, ...a]) => {
  if (was === "rollen") return f.ROLLEN.map((r) => [r.k, r.t, r.kurz, r.grund, r.pruefen]);
  if (was === "texte") return f.texte;
  if (was === "rolleZu") return f.rolleZu(...a);
  if (was === "rollenGruende") return f.rollenGruende(...a);
  if (was === "rolleAnlegen") return f.rolleAnlegen(f.rolleMit(a[0]), a[1]);
  if (was === "rolleAendern") return f.rolleAendern(f.rolleMit(a[0]), a[1], a[2], a[3]);
  if (was === "gueltig") return gueltigFaelle();
  throw new Error(was);
});
console.log(JSON.stringify(aus));
"""


def js(*aufrufe):
    """Ruft die reinen Funktionen aus freigaben.js mit Node.js auf – eine Liste von [Name, Argumente …]."""
    aus = subprocess.run([NODE, "-e", SKRIPT, FRG, json.dumps(list(aufrufe))], capture_output=True, text=True,
                         check=True, timeout=60).stdout
    return json.loads(aus)


def ohne_node(name):
    if NODE:
        return False
    meldung = f"{name}: übersprungen (kein Node.js)."
    if "pytest" in sys.modules:
        import pytest
        pytest.skip(meldung)
    print(meldung)
    return True


# Rechte, wie sie die Liste des Reiters liefert (nur die Felder, die die Zuordnung braucht).
def gr(recht, bis=None, entziehbar=True):
    return {"recht": recht, "bis": bis, "entziehbar": entziehbar}


def pr(bis=None):
    return {"recht": "pruefen", "bis": bis}


# --- statisch ---------------------------------------------------------------------------------------------------

def test_oberflaeche_statisch():
    fjs = lies("app/material/static/freigaben.js")
    css = lies("app/material/static/freigaben.css")
    form = abschnitt(fjs, "  function formHtml(d) {", "  /* Der Zustand des Formulars")
    steuerung = abschnitt(fjs, "  function formVerdrahten(body, stand, nachher) {", "  // An einem Grundrecht hängen")
    dlg = abschnitt(fjs, "  function personDialog(p, stand, nachher) {", "  // „Entziehen“ in der Personenzeile")
    # Dieselben Rollenkarten an beiden Stellen (eine Komponente), Legende „Rolle“ mit „i“ samt Strömipedia-Link.
    assert '${rollenHtml("mf-rollen", "mf-vorlage")}' in form and '${rollenHtml("mfp-rollen", "mfp-rolle")}' in dlg
    assert fjs.count("${rollenHtml(") == 2 and "VORLAGEN" not in fjs
    karten = abschnitt(fjs, "  const rollenHtml = (id, name) =>", "  // gruende:")
    assert '<legend>Rolle${info("Rolle", rollenInfo())}</legend>' in karten and 'class="mf-vorlage"' in karten
    assert '<p class="help mf-gruende" id="${id}-gruende" hidden></p>' in karten
    assert 'mehrDazu("freigaben")' in abschnitt(fjs, "  const rollenInfo = ", "  /* --- Listen")
    # Gültigkeit als Radiogruppe mit immer sichtbarem Datumsfeld – im Dialog und im Anlegen-Formular (je eine Zeile für
    # die Rolle, mit „i“; unter „Einzeln“ je Recht eine).
    zeile = abschnitt(fjs, "  const gueltigHtml = (id, name, mitInfo) =>", "  // „Einzeln“:")
    for teil in ('role="radiogroup"', 'value="dauerhaft"> dauerhaft</label>', 'value="bis"> bis</label>${datumFeld(',
                 'info("Gültig", gueltigInfo())', "feld-gruppe"):
        assert teil in zeile, teil
    assert '${gueltigHtml("mf-gueltig", "Gültig", true)}' in form and '${gueltigHtml("mfp-gueltig", "Gültig", true)}' in dlg
    for k in ("mf-grund-g", "mf-pruefen-g"):
        assert f'gueltigHtml("{k}", ' in form, k
    for k in ("mfp-grund-g", "mfp-pruefen-g"):
        assert f'gueltigHtml("{k}", ' in dlg, k
    steuer = abschnitt(fjs, "  function gueltig(wurzel, id, vorschlag, geaendert) {", "  // Ablehnungen des Servers")
    assert 'feld.addEventListener("pointerdown", bisNehmen);' in steuer and 'feld.addEventListener("input", bisNehmen);' in steuer
    assert '"focus"' not in steuer and "feld.hidden" not in steuer          # Tab ändert nichts, das Feld bleibt sichtbar
    # Kein „Grundrecht bis“/„Prüfen bis“ mit Kästchen „dauerhaft“ mehr; „Grundrecht“ nur unter „Einzeln“.
    for alt in ("Grundrecht bis", "Prüfen bis", 'id="mf-dauerhaft"', "mf-pruefen-dauerhaft", "mfp-grund-dauerhaft",
                "mfp-pruefen-dauerhaft", "PRUEFEN_DAUERHAFT", "mf-enden", "mfp-ende"):
        assert alt not in fjs, alt
    assert re.findall(r"<label for=\"mfp?-grund\">Grundrecht</label>", fjs) == [
        '<label for="mf-grund">Grundrecht</label>', '<label for="mfp-grund">Grundrecht</label>']
    assert '${einzelnHtml("mf", `<label for="mf-grund">Grundrecht</label>' in form
    assert '${einzelnHtml("mfp", grundHtml, pruefHtml)}' in dlg
    # Externer Prüfer nur „bis“; „dauerhaft“ nur, wer selbst dauerhaft verwaltet – sonst der Satz zum eigenen Ende.
    assert 'gRolle.erlauben(v.k !== "extern" && dauerhaftGeht);' in steuerung
    assert 'gRolle.erlauben(v.k !== "extern" && grundDauerGeht);' in dlg
    assert "const eigenesEndeText = (ende) => (ende ? `Du verwaltest hier bis ${fmtTag(ende)} – länger geht nicht.` : \"\");" in fjs
    assert "const eigenesEnde = eigenesEndeText(a.ende);" in steuerung and "eigenesEndeText(ende)" in dlg
    assert "Spätestens ${fmtTag(frueher(" in steuerung and "Spätestens ${fmtTag(frueher(" in dlg
    # Vorgewählt die Rolle zu den heutigen Rechten; nicht änderbar → „Einzeln“; Gründe als Satz.
    assert 'const start = grundFrei && pruefFrei ? rolleZu(g, pf) || "einzeln" : "einzeln";' in dlg
    assert 'gruendeZeigen(feld("mfp-rollen"), gruende);' in dlg and 'gruendeZeigen(feld("mf-rollen"),' in steuerung
    # Speichern: eine Anfrage über den Endpunkt je Person; ohne Änderung schließt der Dialog ohne Anfrage; Rückfrage,
    # wenn ein Recht wegfällt; Fehler zum Ende an der Gültigkeit.
    assert "if (unveraendert(x)) { dlg.close(); return; }" in dlg
    assert dlg.count("await api(") == 1 and "/freigaben/person/${p.konto.id}`, { method: \"PUT\", body: x }" in dlg
    assert 'confirm(text, "Entziehen", "", { endgueltig: false })' in dlg
    assert "UM_DAS_ENDE.test(text) && sichtbar(zeile.gruppe) ? zeile.fehlerZiel() : wahl" in dlg
    assert "Object.assign(daten, rolleAnlegen(v, gRolle.wert()));" in steuerung
    assert 'return rolleAendern(v, gRolle.wert(), g, pf);' in dlg
    # „Prüfen folgt dem Grundrecht“ (03.11.2026): kein Datum vorbelegt außer beim externen Prüfer, Hilfetext neu,
    # Rollenwechsel lässt, was man selbst gesetzt hat.
    for alt in ("Das Prüfen endet am selben Tag", "rolleEnde", "pruefDauer)", "pruefDauer,", "länger vergibst du nichts"):
        assert alt not in fjs, alt
    assert 'const PRUEFEN_FOLGT = "Prüfen gilt, solange das Grundrecht gilt.";' in fjs
    assert steuerung.count("PRUEFEN_FOLGT") == 1 and dlg.count("PRUEFEN_FOLGT") == 1
    assert 'gueltig(body, "mf-gueltig", () => (rolle() && rolle().k === "extern" ? pruefenEnde() : null), () => zeigen());' in steuerung
    assert 'gueltig(body, "mf-grund-g", null, ' in steuerung and 'gueltig(body, "mf-pruefen-g", null, ' in steuerung
    assert 'gueltig(body, "mfp-gueltig", () => (rolle() && rolle().k === "extern" ? pruefenEnde : null), () => zeigen());' in dlg
    assert 'gueltig(body, "mfp-grund-g", null, ' in dlg and 'gueltig(body, "mfp-pruefen-g", null, ' in dlg
    assert 'gRolle.setzen(v && v.k === "extern" ? pruefenEnde() : anker().ende === null ? null : "");' in steuerung
    assert 'gGrund.setzen(anker().ende === null ? null : "");' in steuerung and "gPruef.setzen(null);" in steuerung
    assert "if (!gRolle.vomNutzer()) rolleVorgabe();" in steuerung
    assert "if (!gRolle.vomNutzer()) gRolle.setzen(rolleVorgabe());" in dlg
    assert 'gGrund.setzen(g ? g.bis : grundDauerGeht ? null : "");' in dlg and "gPruef.setzen(pf ? pf.bis : null);" in dlg
    # Prüfen dauerhaft unter „Einzeln“: mit Grundrecht auch für befristete Verwalter.
    assert "gPruef.erlauben(!!grund || grundrechtDort(a));" in steuerung
    assert "const pruefDauerGeht = eigen ? !!(pf && pf.bis === null) : true;" in dlg
    # „Daran hängt …“ ohne die Prüffreigabe hier, wo die Rolle sie selbst regelt (sonst stünde es doppelt da).
    assert "const bleibt = ez && (pruefWahl ? pruefWahl.checked && gPruef.dauerhaft() : pfDauer);" in dlg
    assert '<p class="help" id="mfp-traegt" hidden></p>' in dlg
    # Nicht änderbar (Nr. 4, auch eine dauerhafte Prüffreigabe mit längerem Grundrecht): Dialog in „Einzeln“, das Recht
    # als Text; „Entziehen“ an der Zeile nur, wenn jedes Recht änderbar ist.
    assert "const pruefFrei = !pf || pf.aenderbar;" in dlg and "pruefHtml = `<p class=\"mfp-titel\">Prüffreigabe</p>${fest(pf)}`;" in dlg
    assert "const ganzEntziehbar = (p) => p.rechte.every((f) => f.aenderbar && f.entziehbar !== false);" in fjs
    # Notiz zugeklappt wie beim Anlegen, offen, wenn es eine gibt; der Datenschutzsatz bleibt sichtbar darin.
    assert '<details class="mf-notiz"${notiz || abweichend ? " open" : ""}><summary>Notiz</summary>' in dlg
    assert "Sehen nur Verwalter dieses Ordners und die Material-Verwaltung" in dlg
    # Keine reinen Erklärungen mehr als Hilfezeile (stehen im „i“ an „Gültig“).
    assert "Gilt, solange die Person hier lesen oder verwalten hat" not in fjs
    # Stile: Zeile bricht um („bis“ und Feld zusammen), hidden gewinnt, 44 px nur unter pointer: coarse.
    assert ".mf-gueltig { display: flex; flex-wrap: wrap;" in css and ".mf-bis { display: inline-flex;" in css
    assert ".mf-gueltig[hidden], .mf-gueltig-hilfe[hidden] { display: none; }" in css
    assert '.mf-gueltig.nur-bis .mf-dauerhaft, .mf-gueltig.nur-bis .mf-bis input[type="radio"] { display: none; }' in css
    touch = coarse_bloecke(css)
    for regel in (".mf-vorlage { min-height: 44px; }", ".mf-gueltig label.inline, .mf-einzel-teil label.inline { min-height: 44px; }",
                  ".mf-gueltig .mat-datum { min-height: 44px; }"):
        assert regel in touch, regel
    ohne_touch = css
    for block in touch.split("\n@@\n"):
        ohne_touch = ohne_touch.replace(block, "")
    assert "min-height: 44px" not in ohne_touch
    # Der Text der Leitstelle nennt die Rolle.
    assert "Freigaben, Rolle „Materialwart“." in lies("app/static/js/admin.js")
    print("Oberfläche (statisch) bestanden.")


# --- Node.js: Zuordnung, Gründe, Abbildung -------------------------------------------------------------------------

def test_rollen_zuordnung_und_gruende():
    if ohne_node("test_rollen_zuordnung_und_gruende"):
        return
    d = tag(40)
    zu = [  # (Grundrecht, Prüffreigabe) → Rolle
        (gr("lesen"), None, "fuehrungskraft"),
        (gr("lesen", d), None, "fuehrungskraft"),
        (gr("verwalten"), None, "materialwart"),
        (gr("lesen"), pr(), "pruefer"),
        (gr("lesen", d), pr(), "pruefer"),                       # Grundrecht befristet, Prüfen gilt solange
        (gr("verwalten"), pr(), "materialwart_pruefer"),
        (None, pr(d), "extern"),
        (gr("lesen"), pr(d), "einzeln"),                         # befristet prüfen mit Grundrecht
        (gr("verwalten", tag(90)), pr(d), "einzeln"),            # verschiedene Enddaten
        (None, pr(), "einzeln"),                                 # dauerhaft prüfen, Grundrecht nur von oben
        (None, None, None),
    ]
    rollen, texte, *aus = js(["rollen"], ["texte"], *[["rolleZu", g, p] for g, p, _ in zu])
    assert aus == [r for *_, r in zu], aus
    # Karten: Titel und Kurztexte wie in der Skizze, in ihrer Reihenfolge.
    assert [r[:3] for r in rollen] == [
        ["fuehrungskraft", "Führungskraft", "ansehen, Mängel melden"],
        ["materialwart", "Materialwart", "Ordner und Artikel pflegen"],
        ["materialwart_pruefer", "Materialwart und Prüfer", "wie Materialwart, dazu prüfen"],
        ["pruefer", "Prüfer", "ansehen und prüfen"],
        ["extern", "Externer Prüfer", "nur prüfen, höchstens 24 Monate"],
        ["einzeln", "Einzeln", ""]], rollen

    x = {"fest": False, "eigen": False, "qualifiziert": True, "ohneZugang": False}
    faelle = [
        # fremde, qualifizierte Person: alles wählbar
        (gr("lesen"), None, x, {}),
        # ohne Qualifikation: keine neue oder längere Prüffreigabe – eine schon dauerhafte bleibt wählbar
        (gr("lesen"), None, dict(x, qualifiziert=False),
         {k: "OHNE_QUALIFIKATION" for k in ("materialwart_pruefer", "pruefer", "extern")}),
        (gr("lesen"), pr(), dict(x, qualifiziert=False), {}),
        (gr("lesen"), pr(d), dict(x, qualifiziert=False),
         {k: "OHNE_QUALIFIKATION" for k in ("materialwart_pruefer", "pruefer")}),
        # eigene Rechte: nur herab und kürzen
        (gr("verwalten"), None, dict(x, eigen=True), {k: "EIGENE_NEU" for k in ("materialwart_pruefer", "pruefer", "extern")}),
        (gr("lesen"), None, dict(x, eigen=True),
         {"materialwart": "EIGENE_MEHR", "materialwart_pruefer": "EIGENE_NEU", "pruefer": "EIGENE_NEU", "extern": "EIGENE_NEU"}),
        (gr("lesen"), pr(), dict(x, eigen=True), {"materialwart": "EIGENE_MEHR", "materialwart_pruefer": "EIGENE_MEHR"}),
        (gr("lesen"), pr(d), dict(x, eigen=True),
         {"materialwart": "EIGENE_MEHR", "materialwart_pruefer": "EIGENE_MEHR", "pruefer": "EIGENE_MEHR"}),
        # eigene letzte Verwalterfreigabe (Nr. 7): nicht herab, nicht weg
        (gr("verwalten", entziehbar=False), pr(), dict(x, eigen=True),
         {k: "NUR_PV_HERAB" for k in ("fuehrungskraft", "pruefer", "extern")}),
        # ein Recht reicht weiter als das eigene Verwalten: nur „Einzeln“
        (gr("lesen"), pr(d), dict(x, fest=True), {k: "FEST_ROLLE" for k in ("fuehrungskraft", "materialwart",
                                                                            "materialwart_pruefer", "pruefer", "extern")}),
        # Konto ohne Zugang oder deaktiviert: nichts mehr, nur kürzen und weniger
        (gr("lesen"), None, dict(x, ohneZugang=True),
         {k: "OHNE_ZUGANG_MEHR" for k in ("materialwart", "materialwart_pruefer", "pruefer", "extern")}),
    ]
    aus = js(*[["rollenGruende", g, p, kx] for g, p, kx, _ in faelle])
    for (g, p, kx, erwartet), ist in zip(faelle, aus):
        assert ist == {k: texte[v] for k, v in erwartet.items()}, (g, p, kx, ist)
    assert texte["OHNE_QUALIFIKATION"] == "Prüfen erst mit Häkchen durch die Verwaltung und Urkundennummer im Profil."
    print("Zuordnung Rechte → Rolle und Gründe bestanden.")


def test_rolle_als_anfrage():
    if ohne_node("test_rolle_als_anfrage"):
        return
    d = "2027-06-30"
    aus = js(["rolleAnlegen", "fuehrungskraft", None], ["rolleAnlegen", "materialwart", d],
             ["rolleAnlegen", "pruefer", None], ["rolleAnlegen", "pruefer", d],
             ["rolleAnlegen", "materialwart_pruefer", d], ["rolleAnlegen", "extern", d],
             ["rolleAendern", "fuehrungskraft", None, gr("lesen"), pr()],
             ["rolleAendern", "materialwart", d, None, pr(d)],
             ["rolleAendern", "pruefer", d, gr("verwalten"), None],
             ["rolleAendern", "materialwart_pruefer", d, gr("verwalten"), pr()],
             ["rolleAendern", "extern", d, gr("lesen"), pr()],
             ["rolleAendern", "extern", d, None, None])
    assert aus == [
        {"grundrecht": "lesen", "grund_bis": None, "pruefen": False, "pruefen_bis": None},
        {"grundrecht": "verwalten", "grund_bis": d, "pruefen": False, "pruefen_bis": None},
        {"grundrecht": "lesen", "grund_bis": None, "pruefen": True, "pruefen_bis": None},
        {"grundrecht": "lesen", "grund_bis": d, "pruefen": True, "pruefen_bis": None},      # prüft, solange lesen gilt
        {"grundrecht": "verwalten", "grund_bis": d, "pruefen": True, "pruefen_bis": None},   # auch selbst befristet
        {"grundrecht": None, "grund_bis": None, "pruefen": True, "pruefen_bis": d},
        {"grundrecht": {"recht": "lesen", "bis": None}, "pruefen": None},                   # Prüfen fällt weg
        {"grundrecht": {"recht": "verwalten", "bis": d}, "pruefen": None},
        {"grundrecht": {"recht": "lesen", "bis": d}, "pruefen": {"bis": None}},
        {"grundrecht": {"recht": "verwalten", "bis": d}, "pruefen": {"bis": None}},          # Prüfen folgt dem Grundrecht
        {"grundrecht": None, "pruefen": {"bis": d}},                                        # Grundrecht fällt weg
        {"pruefen": {"bis": d}}], aus
    print("Rolle als Anfrage bestanden.")


def test_gueltigkeit_ohne_vorbelegung():
    """„Prüfen folgt dem Grundrecht“ (03.11.2026): Die Gültigkeitszeile schlägt nur dort ein Datum vor, wo man ihr einen
    Vorschlag gibt (nur der externe Prüfer); sonst bleibt „bis“ leer, Speichern ohne Datum ist ein Fehler am Feld. Was
    man selbst angefasst hat, merkt sie sich (der Rollenwechsel lässt es); ein erzwungenes „bis“ wird wieder
    „dauerhaft“, sobald das geht und niemand die Zeile angefasst hat."""
    if ohne_node("test_gueltigkeit_ohne_vorbelegung"):
        return
    f, texte = js(["gueltig"], ["texte"])
    assert f["dauerhaft"] == {"wahl": "dauerhaft", "feld": "", "nurBis": False, "vomNutzer": False, "dauerhaft": True,
                              "wert": None}, f
    assert f["bisGeklickt"] == {"wahl": "bis", "feld": "", "nurBis": False, "vomNutzer": True, "dauerhaft": False,
                                "wert": {"fehler": "Bitte ein Datum angeben – oder „dauerhaft“.", "amFeld": True}}, f
    assert f["nurBisLeer"] == {"wahl": "bis", "feld": "", "nurBis": True, "vomNutzer": False, "dauerhaft": False,
                               "wert": {"fehler": "Bitte ein Datum angeben.", "amFeld": True}}, f
    assert (f["erzwungen"]["wahl"], f["erzwungen"]["feld"], f["erzwungen"]["nurBis"]) == ("bis", "", True), f
    assert (f["zurueck"]["wahl"], f["zurueck"]["nurBis"], f["zurueck"]["wert"]) == ("dauerhaft", False, None), f
    assert (f["getippt"]["wahl"], f["getippt"]["vomNutzer"], f["getippt"]["wert"]) == ("bis", True, "2026-12-31"), f
    assert (f["neuGesetzt"]["wahl"], f["neuGesetzt"]["feld"], f["neuGesetzt"]["vomNutzer"]) == ("bis", "30.06.2027", False), f
    assert (f["extern"]["wahl"], f["extern"]["feld"], f["extern"]["wert"]) == ("bis", "31.12.2027", "2027-12-31"), f
    assert f["externGespeichert"]["feld"] == "31.03.2027", f          # ein gespeichertes Datum bleibt
    assert f["eigenesEnde"] == ["Du verwaltest hier bis 02.11.2028 – länger geht nicht.", ""], f
    assert texte["PRUEFEN_FOLGT"] == "Prüfen gilt, solange das Grundrecht gilt."
    print("Gültigkeit ohne Vorbelegung bestanden.")


# --- gegen die Schnittstelle --------------------------------------------------------------------------------------

def _rechte(c, fid, uid):
    """Grundrecht und Prüffreigabe einer Person am Ordner aus der Liste des Reiters (wie der Dialog sie bekommt)."""
    r = c.get(FR.format(fid))
    assert r.status_code == 200, r.get_json()
    zeilen = [f for f in r.json["direkt"] if f["konto"]["id"] == uid]
    g = next((f for f in zeilen if f["recht"] != "pruefen"), None)
    p = next((f for f in zeilen if f["recht"] == "pruefen"), None)
    return g, p


def _kurz(g, p):
    return ((g["recht"], g["bis"]) if g else None, p["bis"] if p else "keine")


def test_rollen_gegen_die_schnittstelle():
    if ohne_node("test_rollen_gegen_die_schnittstelle"):
        return
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        _, hid = neues_konto(app, "helfer@example.org", name="Helfer Platzhalter", mat_pruefer=True,
                             urkundennummer="1012-0201")
        _, oid = neues_konto(app, "ohne@example.org", name="Ohne Platzhalter")
        d50, d100 = tag(50), tag(100)

        # Anlegen: jede Rolle über rolleAnlegen (der Anlegende verwaltet dauerhaft) an je eine neue Person.
        erwartet = {"fuehrungskraft": (("lesen", None), "keine"), "materialwart": (("verwalten", None), "keine"),
                    "materialwart_pruefer": (("verwalten", None), None), "pruefer": (("lesen", None), None),
                    "extern": (None, d100)}
        for i, (rolle, soll) in enumerate(erwartet.items()):
            _, uid = neues_konto(app, f"neu{i}@example.org", name=f"Neu {i} Platzhalter", mat_pruefer=True,
                                 urkundennummer=f"1012-03{i:02d}")
            daten, = js(["rolleAnlegen", rolle, d100 if rolle == "extern" else None])
            r = w.post(FR.format(gid), json=dict(daten, user_id=uid))
            assert r.status_code == 201, (rolle, r.get_json())
            assert _kurz(*_rechte(w, gid, uid)) == soll, (rolle, _rechte(w, gid, uid))

        # Ändern: dieselbe Person reihum durch alle Rollen – mit den Rechten aus der Liste, wie der Dialog sie hat.
        schritte = [("fuehrungskraft", None, (("lesen", None), "keine")),
                    ("materialwart_pruefer", None, (("verwalten", None), None)),
                    ("materialwart", None, (("verwalten", None), "keine")),            # Prüfen fällt weg
                    ("pruefer", d50, (("lesen", d50), None)),                          # prüft, solange lesen gilt
                    ("extern", d100, (None, d100)),                                    # Grundrecht fällt weg
                    ("fuehrungskraft", d50, (("lesen", d50), "keine"))]
        for rolle, bis, soll in schritte:
            g, p = _rechte(w, gid, hid)
            daten, zu = js(["rolleAendern", rolle, bis, g, p], ["rolleZu", g, p])
            r = w.put(PERSON.format(gid, hid), json=daten)
            assert r.status_code == 200, (rolle, r.get_json())
            assert _kurz(*_rechte(w, gid, hid)) == soll, (rolle, _rechte(w, gid, hid))
            assert js(["rolleZu", *_rechte(w, gid, hid)]) == [rolle], rolle            # öffnet wieder in dieser Rolle

        # Externer Prüfer: höchstens 24 Monate – der Server lehnt mit „„Prüffreigabe“: …“ ab (Fehler am Feld).
        with app.app_context():
            from app.material.services import freigaben
            grenze = freigaben.pruefen_max()
        g, p = _rechte(w, gid, hid)
        zuviel = (_heute().fromisoformat(grenze) + timedelta(days=1)).isoformat()
        daten, = js(["rolleAendern", "extern", zuviel, g, p])
        r = w.put(PERSON.format(gid, hid), json=daten)
        assert r.status_code == 400 and r.json["error"].startswith("„Prüffreigabe“: Eine Prüffreigabe läuft höchstens 24 Monate"), r.get_json()
        assert _kurz(*_rechte(w, gid, hid)) == (("lesen", d50), "keine")                 # alles oder nichts
        daten, = js(["rolleAendern", "extern", grenze, g, p])
        assert w.put(PERSON.format(gid, hid), json=daten).status_code == 200
        assert _kurz(*_rechte(w, gid, hid)) == (None, grenze)

        # Ohne Qualifikation: Was der Dialog ausgraut, lehnt der Server ab (409); Führungskraft (gekürzt) geht.
        freigeben(adm, gid, oid, "lesen")
        g, p = _rechte(w, gid, oid)
        x = {"fest": False, "eigen": False, "qualifiziert": g["konto"]["qualifiziert"], "ohneZugang": False}
        gruende, = js(["rollenGruende", g, p, x])
        assert set(gruende) == {"materialwart_pruefer", "pruefer", "extern"}, gruende
        for rolle in gruende:
            daten, = js(["rolleAendern", rolle, d100 if rolle == "extern" else None, g, p])
            r = w.put(PERSON.format(gid, oid), json=daten)
            assert r.status_code == 409 and "Prüferqualifikation" in r.json["error"], (rolle, r.get_json())
        daten, = js(["rolleAendern", "fuehrungskraft", d50, g, p])
        assert w.put(PERSON.format(gid, oid), json=daten).status_code == 200
        assert _kurz(*_rechte(w, gid, oid)) == (("lesen", d50), "keine")

        # Eigene Rechte: In einer zweiten Gliederung ist der Materialwart der einzige Verwalter – herab geht nicht (Nr. 7),
        # mehr nie (Nr. 5).
        b, _ = gliederung(adm, "OG Nachbarstadt", standard=False)
        freigeben(adm, b, k["wart_id"], "verwalten")
        g, p = _rechte(w, b, k["wart_id"])
        assert g["eigen"] and g["entziehbar"] is False, g
        x = {"fest": False, "eigen": True, "qualifiziert": True, "ohneZugang": False}
        gruende, = js(["rollenGruende", g, p, x])
        assert set(gruende) == {"fuehrungskraft", "materialwart_pruefer", "pruefer", "extern"}, gruende
        for rolle in gruende:
            daten, = js(["rolleAendern", rolle, d100 if rolle == "extern" else None, g, p])
            r = w.put(PERSON.format(b, k["wart_id"]), json=daten)
            assert r.status_code in (403, 409), (rolle, r.get_json())
        # Mit einem zweiten dauerhaften Verwalter: herabsetzen und kürzen gehen, die Prüfrollen bleiben gesperrt.
        freigeben(adm, b, hid, "verwalten")
        g, p = _rechte(w, b, k["wart_id"])
        gruende, = js(["rollenGruende", g, p, x])
        assert set(gruende) == {"materialwart_pruefer", "pruefer", "extern"}, gruende
        daten, = js(["rolleAendern", "materialwart", d50, g, p])
        assert w.put(PERSON.format(b, k["wart_id"]), json=daten).status_code == 200      # kürzen
        g, p = _rechte(w, b, k["wart_id"])
        daten, = js(["rolleAendern", "materialwart", d100, g, p])
        r = w.put(PERSON.format(b, k["wart_id"]), json=daten)                              # verlängern: nein
        assert r.status_code == 403, r.get_json()
        daten, = js(["rolleAendern", "fuehrungskraft", d50, g, p])
        r = w.put(PERSON.format(b, k["wart_id"]), json=daten)                              # herabsetzen
        assert r.status_code == 200 and r.json["liste"] is None, r.get_json()               # verwaltet nicht mehr
        assert _kurz(*_rechte(adm, b, k["wart_id"])) == (("lesen", d50), "keine")
    print("Rollen gegen die Schnittstelle bestanden.")


def test_pruefen_folgt_dem_grundrecht():
    """Entscheidung des Nutzers vom 03.11.2026: Bei internen Rollen ist Prüfen immer dauerhaft und gilt, solange das
    Grundrecht gilt – auch vom befristeten Verwalter. Das Grundrecht bleibt höchstens bis zu seinem eigenen Ende, ohne
    Grundrecht gibt es kein dauerhaftes Prüfen, extern höchstens 24 Monate, die eigene Zeile nur herab. Dazu der Fall
    aus dem Anlass: Wer befristet über heute + 24 Monate hinaus verwaltet, gibt „Prüfer“ mit seinem eigenen Ende – der
    Server lehnte das mit „höchstens 24 Monate“ ab, weil das Prüfen dasselbe Datum bekam."""
    if ohne_node("test_pruefen_folgt_dem_grundrecht"):
        return
    with tempfile.TemporaryDirectory() as tmp:
        app, k = umgebung(tmp)
        adm, w = k["adm"], k["wart"]
        gid, _ = gliederung(adm)
        with app.app_context():
            from app.material.services import freigaben
            grenze = freigaben.pruefen_max()
        ende_lang, ende_kurz = tag(900), tag(80)              # > 24 Monate und < 24 Monate
        assert ende_lang > grenze > ende_kurz
        lang, lang_id = neues_konto(app, "lang@example.org", name="Lang Platzhalter", mat_pruefer=True,
                                    urkundennummer="1012-0401")
        kurz, kurz_id = neues_konto(app, "kurz@example.org", name="Kurz Platzhalter", mat_pruefer=True,
                                    urkundennummer="1012-0402")
        freigeben(adm, gid, lang_id, "verwalten", bis=ende_lang)
        freigeben(adm, gid, kurz_id, "verwalten", bis=ende_kurz)

        def person_neu(i):
            return neues_konto(app, f"p{i}@example.org", name=f"Person {i} Platzhalter", mat_pruefer=True,
                               urkundennummer=f"1012-05{i:02d}")[1]

        # Anlegen: „Prüfer“ und „Materialwart und Prüfer“ mit dem eigenen Ende (bzw. früher) – Prüfen dauerhaft.
        for c, ende, i in ((lang, ende_lang, 1), (kurz, ende_kurz, 2)):
            for rolle, recht in (("pruefer", "lesen"), ("materialwart_pruefer", "verwalten")):
                uid = person_neu(i * 10 + len(rolle) % 10)
                daten, = js(["rolleAnlegen", rolle, ende])
                assert daten["pruefen_bis"] is None, daten
                r = c.post(FR.format(gid), json=dict(daten, user_id=uid))
                assert r.status_code == 201, (rolle, ende, r.get_json())
                g, p = _rechte(c, gid, uid)
                assert _kurz(g, p) == ((recht, ende), None), (rolle, _kurz(g, p))
                # Die Zeile bleibt für ihn änderbar und öffnet wieder in derselben Rolle (nichts ausgegraut).
                assert g["aenderbar"] and p["aenderbar"] and js(["rolleZu", g, p]) == [rolle], (g, p)
                gruende, = js(["rollenGruende", g, p, {"fest": False, "eigen": False, "qualifiziert": True,
                                                       "ohneZugang": False}])
                assert gruende == {}, gruende
                # Das Grundrecht nicht über das eigene Ende, nicht dauerhaft (Phase-2-Regel bleibt).
                for bis, text in ((tag(901 if c is lang else 81), "eigene Verwalterfreigabe"), (None, "Dauerhaft vergibt nur")):
                    daten, = js(["rolleAendern", rolle, bis, g, p])
                    r = c.put(PERSON.format(gid, uid), json=daten)
                    assert r.status_code == 403 and r.json["error"].startswith("„Grundrecht“: ") and text in r.json["error"], r.get_json()
                assert _kurz(*_rechte(c, gid, uid)) == ((recht, ende), None)

        # Der Fall aus dem Anlass: Führungskraft bis zum eigenen Ende (> 24 Monate) → „Prüfer“ mit diesem Datum.
        uid = person_neu(31)
        daten, = js(["rolleAnlegen", "fuehrungskraft", ende_lang])
        assert lang.post(FR.format(gid), json=dict(daten, user_id=uid)).status_code == 201
        g, p = _rechte(lang, gid, uid)
        daten, = js(["rolleAendern", "pruefer", g["bis"], g, p])               # der Dialog zeigt das gespeicherte Ende
        assert daten == {"grundrecht": {"recht": "lesen", "bis": ende_lang}, "pruefen": {"bis": None}}, daten
        r = lang.put(PERSON.format(gid, uid), json=daten)
        assert r.status_code == 200, r.get_json()
        assert _kurz(*_rechte(lang, gid, uid)) == (("lesen", ende_lang), None)
        # Befristetes Prüfen mit Grundrecht (Bestand, „Einzeln“) → „Prüfer“: wird dauerhaft.
        uid = person_neu(32)
        r = kurz.post(FR.format(gid), json={"user_id": uid, "grundrecht": "lesen", "grund_bis": tag(40), "pruefen": True,
                                            "pruefen_bis": tag(30)})
        assert r.status_code == 201, r.get_json()
        g, p = _rechte(kurz, gid, uid)
        assert js(["rolleZu", g, p]) == ["einzeln"]
        daten, = js(["rolleAendern", "pruefer", g["bis"], g, p])
        assert kurz.put(PERSON.format(gid, uid), json=daten).status_code == 200
        assert _kurz(*_rechte(kurz, gid, uid)) == (("lesen", tag(40)), None)
        # „Prüfer“ → „Externer Prüfer“: Das Grundrecht fällt (zuerst geschrieben) weg, die bis eben dauerhafte
        # Prüffreigabe ist für ihn änderbar (Stand vor der Anfrage) und bekommt das Datum.
        g, p = _rechte(kurz, gid, uid)
        daten, = js(["rolleAendern", "extern", tag(60), g, p])
        r = kurz.put(PERSON.format(gid, uid), json=daten)
        assert r.status_code == 200, r.get_json()
        assert _kurz(*_rechte(kurz, gid, uid)) == (None, tag(60))

        # Ohne Grundrecht kein dauerhaftes Prüfen – auch nicht vom befristeten Verwalter (400 wie für alle).
        uid = person_neu(33)
        for c in (lang, kurz):
            r = c.post(FR.format(gid), json={"user_id": uid, "pruefen": True, "pruefen_bis": None})
            assert r.status_code == 400 and "nur zusammen mit lesen oder verwalten" in r.json["error"], r.get_json()
            r = c.put(PERSON.format(gid, uid), json={"pruefen": {"bis": None}})
            assert r.status_code == 400 and r.json["error"].startswith("„Prüffreigabe“: Dauerhaft gibt es"), r.get_json()
        # Extern: höchstens 24 Monate (und nicht länger als das eigene Verwalten).
        zuviel = (_heute().fromisoformat(grenze) + timedelta(days=1)).isoformat()
        for daten in ({"user_id": uid, "pruefen": True, "pruefen_bis": zuviel},):
            r = lang.post(FR.format(gid), json=daten)
            assert r.status_code == 400 and "24 Monate" in r.json["error"], r.get_json()
        r = lang.put(PERSON.format(gid, uid), json={"pruefen": {"bis": zuviel}})
        assert r.status_code == 400 and "24 Monate" in r.json["error"], r.get_json()
        r = kurz.put(PERSON.format(gid, uid), json={"pruefen": {"bis": tag(81)}})
        assert r.status_code == 403 and "eigene Verwalterfreigabe" in r.json["error"], r.get_json()
        assert lang.put(PERSON.format(gid, uid), json={"pruefen": {"bis": grenze}}).status_code == 200
        assert _kurz(*_rechte(lang, gid, uid)) == (None, grenze)

        # „Nur innerhalb seiner Zeit“ (Nutzer 03.11.2026): Eine dauerhafte Prüffreigabe ändert ein befristeter Verwalter
        # nur, wenn das Grundrecht, das sie vor der Anfrage trug, nicht länger läuft als sein Verwalten.
        lager = ordner_neu(w, gid, "Lager")
        # (a) eigene Vergabe mit Grundrecht bis vor seinem Ende: kürzen und entziehen gehen, auch einzeln an der Zeile.
        for i, weg in ((34, "put"), (35, "delete")):
            uid = person_neu(i)
            daten, = js(["rolleAnlegen", "pruefer", tag(40)])
            assert kurz.post(FR.format(gid), json=dict(daten, user_id=uid)).status_code == 201
            g, p = _rechte(kurz, gid, uid)
            assert p["aenderbar"] and p["entziehbar"], p
            if weg == "put":
                assert kurz.put(PERSON.format(gid, uid), json={"pruefen": {"bis": tag(30)}}).status_code == 200
                assert kurz.put(PERSON.format(gid, uid), json={"pruefen": None}).status_code == 200
            else:
                assert kurz.delete(f"/api/material/freigaben/{p['id']}", headers=H).status_code == 200
            assert _kurz(*_rechte(kurz, gid, uid)) == (("lesen", tag(40)), "keine")
        # (b) dauerhaftes bzw. längeres Grundrecht hier (von der Verwaltung): nicht änderbar – Liste, PUT, Entziehen.
        # (c) geerbt: lesen dauerhaft an der Gliederung, dauerhaftes Prüfen am Lager – vergeben darf er es, danach
        # ändern nicht mehr.
        faelle = []
        for i, bis in ((36, None), (37, tag(200))):
            uid = person_neu(i)
            freigeben(adm, gid, uid, "lesen", bis=bis)
            r = adm.put(PERSON.format(gid, uid), json={"pruefen": {"bis": None}})
            assert r.status_code == 200, r.get_json()
            faelle.append((gid, uid))
        uid = person_neu(38)
        freigeben(adm, gid, uid, "lesen")
        r = kurz.post(FR.format(lager), json={"user_id": uid, "pruefen": True, "pruefen_bis": None})
        assert r.status_code == 201 and r.json["freigaben"][0]["bis"] is None, r.get_json()
        assert not r.json["freigaben"][0]["aenderbar"], r.get_json()
        faelle.append((lager, uid))
        for fid, uid in faelle:
            p = next(f for f in kurz.get(FR.format(fid)).json["direkt"] if f["konto"]["id"] == uid and f["recht"] == "pruefen")
            assert (p["bis"], p["aenderbar"], p["entziehbar"]) == (None, False, False), p
            gruende, = js(["rollenGruende", None, p, {"fest": True, "eigen": False, "qualifiziert": True, "ohneZugang": False}])
            assert set(gruende) == {"fuehrungskraft", "materialwart", "materialwart_pruefer", "pruefer", "extern"}, gruende
            for daten in ({"pruefen": {"bis": tag(30)}}, {"pruefen": None}, {"pruefen": {"bis": None}, "notiz": "x"}):
                r = kurz.put(PERSON.format(fid, uid), json=daten)
                assert r.status_code == 403 and r.json["error"].startswith("„Prüffreigabe“: Diese Freigabe reicht weiter"), (daten, r.get_json())
            r = kurz.delete(f"/api/material/freigaben/{p['id']}", headers=H)
            assert r.status_code == 403 and "reicht weiter als deine eigene" in r.json["error"], r.get_json()
            assert _rechte(adm, fid, uid)[1]["bis"] is None
        # Der dauerhafte Verwalter und die Material-Verwaltung ändern sie weiter.
        fid, uid = faelle[0]
        assert w.put(PERSON.format(fid, uid), json={"pruefen": {"bis": tag(30)}}).status_code == 200
        fid, uid = faelle[2]
        assert adm.put(PERSON.format(fid, uid), json={"pruefen": None}).status_code == 200
        # Grundrecht genau bis zu seinem Ende: änderbar.
        uid = person_neu(39)
        freigeben(adm, gid, uid, "lesen", bis=ende_kurz)
        assert kurz.put(PERSON.format(gid, uid), json={"pruefen": {"bis": None}}).status_code == 200
        assert _rechte(kurz, gid, uid)[1]["aenderbar"]
        assert kurz.put(PERSON.format(gid, uid), json={"pruefen": None}).status_code == 200

        # Die eigene Zeile bleibt, wie sie war: befristetes eigenes Prüfen nicht dauerhaft, kein neues eigenes Prüfen.
        freigeben(adm, gid, kurz_id, "pruefen", bis=tag(30))
        g, p = _rechte(kurz, gid, kurz_id)
        assert g["eigen"] and p["bis"] == tag(30)
        r = kurz.put(PERSON.format(gid, kurz_id), json={"pruefen": {"bis": None}})
        assert r.status_code == 403 and r.json["error"] == "„Prüffreigabe“: Deine eigene Freigabe kannst du nur " \
            "verkürzen, herabsetzen oder entziehen.", r.get_json()
        assert _rechte(kurz, gid, kurz_id)[1]["bis"] == tag(30)
        r = lang.put(PERSON.format(gid, lang_id), json={"pruefen": {"bis": None}})
        assert r.status_code == 403 and r.json["error"].startswith("„Prüffreigabe“: Dir selbst"), r.get_json()
    print("Prüfen folgt dem Grundrecht bestanden.")


if __name__ == "__main__":
    test_oberflaeche_statisch()
    test_rollen_zuordnung_und_gruende()
    test_rolle_als_anfrage()
    test_gueltigkeit_ohne_vorbelegung()
    test_rollen_gegen_die_schnittstelle()
    test_pruefen_folgt_dem_grundrecht()
