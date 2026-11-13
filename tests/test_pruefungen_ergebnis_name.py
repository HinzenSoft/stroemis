"""Wünsche des Nutzers zu den Riegenkarten vom 13.11.2026:
- „In der Matrix kann beim Namen vermerkt werden, wenn eine Person bestanden hat oder durchgefallen ist.“ und „Ggf. kann
  der Name einfach global Rot/Grün eingefärbt werden und die Bubbles auch auf anderen Seiten des Moduls entfernt werden“
- „Der Fade bei den Beschreibungen kann entfallen.“ (Karten im Reiter „Leistungen“)
python tests/test_pruefungen_ergebnis_name.py  oder  pytest tests/test_pruefungen_ergebnis_name.py

Vorher stand in der Matrix am Namen nur das Schloss; das Ergebnis zeigten Marken („bestanden“/„nicht bestanden“) in der
Teilnehmerliste, „je Leistung“, den Mängeln und am großen Bild. Jetzt ist der Name selbst grün bzw. rot – in der
Teilnehmerliste, der Matrix, „je Leistung“ und „je Teilnehmende“ –, die Marken sind fort, und die Vorlesehilfe hört das
Ergebnis als Wort. Über der letzten Zeile einer Leistungsbeschreibung lag ein Verlauf, auch wenn sie ganz dastand; jetzt
endet nur eine längere nach drei Zeilen mit „…“. Geprüft in der echten App (Server im Faden) in Chromium als Leitung und
als Ausbilder ohne Leitung; ohne Chromium übersprungen."""
import os
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "tests"))

from einfuehrung_browser import Umgebung, uebersprungen  # noqa: E402

PERSONEN = [("Bestanden", "Anna", "bestanden"), ("Durchgefallen", "Bert", "nicht_bestanden"), ("Offen", "Clara", None)]
LANG = " ".join(["Folgende Knoten müssen jederzeit sicher und richtig beherrscht werden."] * 8)
# Je Person: Farbe des sichtbaren Namens und was die Vorlesehilfe dazu hört; dazu alle Marken mit „bestanden“
NAMEN = r"""(() => { const farbe = (v) => { const d = document.createElement('span'); d.style.color = v; document.body.appendChild(d);
    const f = getComputedStyle(d).color; d.remove(); return f; };
  const soll = { ok: farbe('var(--ok)'), rot: farbe('var(--rot-auf-flaeche)') };
  const namen = [...document.querySelectorAll('#pruef .tn-name, #pruef .tn-kopfzeile .linkbtn')].filter((e) => e.offsetParent)
    .map((e) => [e.textContent.replace(/,\s*Lehrgang.*$/, '').trim(), getComputedStyle(e).color, (e.querySelector('.nur-vorlesen') || {}).textContent || '']);
  const marken = [...document.querySelectorAll('#pruef .badge')].filter((b) => /bestanden/.test(b.textContent)).length;
  return { soll, namen, marken }; })()"""


def _lauf(u):
    r = u.adm.post("/api/pruefungen/lehrgaenge", json={"titel": "Farbe", "status": "laufend", "ausbilder": [
        {"user_id": u.ids["redakteur"], "funktion": "Leitung", "ist_leitung": True},
        {"user_id": u.ids["mitglied"], "funktion": "Wasser", "ist_leitung": False}]})
    assert r.status_code == 201, r.get_json()
    lid = r.json["lehrgang"]["id"]
    for bez, besch in (("Knotenprüfung", LANG), ("Wurfsack", "Kurz.")):
        assert u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/leistungen",
                          json={"bezeichnung": bez, "beschreibung_md": besch}).status_code == 201
    for name, vorname, erg in PERSONEN:
        r = u.adm.post(f"/api/pruefungen/lehrgaenge/{lid}/teilnehmer", json={"name": name, "vorname": vorname})
        assert r.status_code == 201, r.get_json()
        if erg:
            tid = r.json["teilnehmer"]["id"]
            assert u.adm.put(f"/api/pruefungen/teilnehmer/{tid}/ergebnis", json={"ergebnis": erg}).status_code == 200

    def pruefen(s, wo, erwartet):
        time.sleep(0.4)
        k = s.js(NAMEN)
        assert k["marken"] == 0, (wo, k)
        farben = {"bestanden": k["soll"]["ok"], "nicht_bestanden": k["soll"]["rot"]}
        gesehen = {}
        for text, farbe, vorlesen in k["namen"]:
            for name, vorname, erg in PERSONEN:
                if name in text:
                    gesehen[name] = (farbe, vorlesen)
        assert set(gesehen) == set(erwartet), (wo, k["namen"])
        for name, vorname, erg in PERSONEN:
            if name not in erwartet:
                continue
            farbe, vorlesen = gesehen[name]
            if erg:
                wort = "bestanden" if erg == "bestanden" else "nicht bestanden"
                assert farbe == farben[erg] and vorlesen == f", Lehrgang {wort}", (wo, name, farbe, vorlesen, k["soll"])
            else:
                assert farbe not in farben.values() and not vorlesen, (wo, name, farbe, vorlesen)

    alle = {p[0] for p in PERSONEN}
    for rolle in ("redakteur", "mitglied"):
        s = u.seite(rolle, 1300, 1000)
        try:
            s.oeffnen(f"/riegenkarten/{lid}#teilnehmer", warten=1.5)
            s.ruhe(1.0)
            pruefen(s, (rolle, "Teilnehmende"), alle)
            s.oeffnen(f"/riegenkarten/{lid}#bewertung", warten=1.5)
            s.ruhe(1.0)
            for ansicht, erwartet in (("matrix", alle), ("leistung", alle), ("tn", {"Bestanden"})):
                s.klick(f'[data-act="bew-ansicht"][data-a="{ansicht}"]')
                pruefen(s, (rolle, ansicht), erwartet)
            # je Teilnehmende ohne Leitung: das Ergebnis als farbiges Wort statt Marke
            if rolle == "mitglied":
                w = s.js("(() => { const e = document.querySelector('.erg-block .erg-wort'); return e && [e.textContent, getComputedStyle(e).color]; })()")
                assert w and w[0] == "bestanden" and w[1] == s.js(NAMEN)["soll"]["ok"], w
            # Leistungen: kein Verlauf mehr; die kurze Beschreibung steht ganz da, die lange endet nach drei Zeilen
            s.oeffnen(f"/riegenkarten/{lid}#leistungen", warten=1.5)
            s.ruhe(1.0)
            v = s.js(r"""[...document.querySelectorAll('.leistung-karte .md-vorschau')].map((e) => {
              const zeile = parseFloat(getComputedStyle(e.querySelector('p') || e).lineHeight);
              return [getComputedStyle(e, '::after').content, e.scrollHeight > e.clientHeight + 1, Math.round(e.clientHeight / zeile)]; })""")
            assert [x[0] for x in v] == ["none", "none"], v
            assert v[0][1] and v[0][2] == 3 and not v[1][1] and v[1][2] == 1, v
        finally:
            s.schliessen()


def test_ergebnis_name():
    if uebersprungen():
        print("übersprungen – kein Chromium")
        return
    with Umgebung() as u:
        _lauf(u)


if __name__ == "__main__":
    test_ergebnis_name()
    print("ok")
