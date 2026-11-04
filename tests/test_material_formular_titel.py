"""Titel im Prüfformular-Editor bleibt beim Bearbeiten: python tests/test_material_formular_titel.py  oder  pytest

Meldung des Nutzers (03.11.2026): „Der Titel von Prüfformularen verschwindet beim Bearbeiten andauernd.“ Ursache:
zeichnen() baut den Editor neu (Prüfpunkt anlegen, verschieben, entfernen, Art ändern); einsammeln() übernahm vorher nur
die Prüfpunkte, das Titelfeld kam wieder mit dem gespeicherten Titel (f.titel) – das Getippte war weg. Jetzt merkt sich
einsammeln() auch den Titel (titelEingabe), und das Feld wird damit gezeichnet. Die Überschrift zeigt weiter den
gespeicherten Titel. Seit dem 04.11.2026 sammelt einsammeln() auch die Gruppennamen der Zwischenzeilen
(tests/test_material_formular_editor.py prüft das im Browser)."""
import os
import re

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lesen(pfad):
    with open(os.path.join(WURZEL, pfad), encoding="utf-8") as fh:
        return fh.read()


def abschnitt(text, anfang, ende):
    i = text.index(anfang)
    return text[i:text.index(ende, i + len(anfang))]


def test_titel_bleibt_beim_neuzeichnen():
    js = lesen("app/material/static/material.js")
    editor = abschnitt(js, "  async function formular() {", "\n  }\n")
    sammeln = abschnitt(editor, "    function einsammeln() {", "\n    }\n")
    # einsammeln() merkt sich den getippten Titel …
    assert 'const titelFeld = $("#fp-titel", inhalt);' in sammeln and "titelEingabe = titelFeld.value" in sammeln
    # … und das Feld wird damit gezeichnet, nicht mit dem gespeicherten Titel.
    assert '<input type="text" id="fp-titel" value="${esc(titelEingabe)}" maxlength="160">' in editor
    assert 'id="fp-titel" value="${esc(f.titel' not in editor
    assert 'let titelEingabe = f.titel || "";' in editor
    # Jedes Neuzeichnen nach einer Eingabe sammelt vorher ein (sonst ginge Getipptes verloren) – ausgenommen der erste
    # Aufbau, eine Zeile nur aus „zeichnen();“. Seit dem 04.11.2026 (Gruppen als Zwischenzeile, Ziehgriff, Menü „⋯“) steht
    # einsammeln() am Anfang jedes Handlers, der neu zeichnet; das Ziehen sammelt beim Aufsetzen ein.
    zeilen = editor.splitlines()
    anfang = re.compile(r'^\s+("[\w-]+"|[\w-]+): (async )?\(|^\s+(async )?function \w+\(|addEventListener\("change"')
    aufrufe = 0
    for nr, z in enumerate(zeilen):
        if (not re.search(r"(?<!function )\bzeichnen\(", z) or z.strip() == "zeichnen();"
                or z.lstrip().startswith(("//", "/*", "*")) or "zeichnen() " in z):
            continue
        aufrufe += 1
        start = max(i for i in range(nr + 1) if anfang.search(zeilen[i]))
        assert "einsammeln();" in "\n".join(zeilen[start:nr + 1]), (nr, z.strip())
    # Art ändern; Punkt: neu, hoch, runter, in Gruppe, weg; Gruppe: neu, hoch, runter, weg (das Ende des Ziehens zeichnet
    # mit „zeichnen();“ – eingesammelt ist beim Aufsetzen).
    assert aufrufe == 10, aufrufe
    ziehen = abschnitt(editor, "    function ziehen(e) {", "\n    }\n")
    assert ziehen.index("einsammeln();") < ziehen.index("zeichnen();")
    # Speichern und Aktivieren nehmen den Titel aus dem Feld.
    assert editor.count('titel: $("#fp-titel").value') == 2
    print("Titel im Formular-Editor bestanden.")


if __name__ == "__main__":
    test_titel_bleibt_beim_neuzeichnen()
