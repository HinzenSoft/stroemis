"""Titel im Prüfformular-Editor bleibt beim Bearbeiten: python tests/test_material_formular_titel.py  oder  pytest

Meldung des Nutzers (03.11.2026): „Der Titel von Prüfformularen verschwindet beim Bearbeiten andauernd.“ Ursache:
zeichnen() baut den Editor neu (Prüfpunkt anlegen, verschieben, entfernen, Art ändern); einsammeln() übernahm vorher nur
die Prüfpunkte, das Titelfeld kam wieder mit dem gespeicherten Titel (f.titel) – das Getippte war weg. Jetzt merkt sich
einsammeln() auch den Titel (titelEingabe), und das Feld wird damit gezeichnet. Die Überschrift zeigt weiter den
gespeicherten Titel."""
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
    # Aufbau, eine Zeile nur aus „zeichnen();“.
    neu = [z.strip() for z in editor.splitlines() if re.search(r"\bzeichnen\(\);", z) and z.strip() != "zeichnen();"]
    assert len(neu) == 5, neu      # Art ändern, Prüfpunkt anlegen, hoch, runter, entfernen
    for zeile in neu:
        assert "einsammeln();" in zeile.split("zeichnen();")[0], zeile
    # Speichern und Aktivieren nehmen den Titel aus dem Feld.
    assert editor.count('titel: $("#fp-titel").value') == 2
    print("Titel im Formular-Editor bestanden.")


if __name__ == "__main__":
    test_titel_bleibt_beim_neuzeichnen()
