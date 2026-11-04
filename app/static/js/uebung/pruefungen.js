/* Übungsdatei der Einführung: Riegenkarten (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.4; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide).
   Gehört dem Modul-Teil; Grundgerüst nur Gerüst. Je Teil ein Ablauf mit einem Info-Schritt auf der Startseite und die
   Antworten, die die Startseite zum Zeichnen braucht (leerer, aber gültiger Bestand). Übungsdaten nur als Platzhalter
   „Übung“, Kennungen im Bereich 9300000xx. */
(function () {
  const info = (titel, text) => ({ ablaeufe: [{ titel, start: "/riegenkarten", schritte: [{ ziel: "#lg-liste", text }] }] });

  S.einfuehrung.modul("pruefungen", {
    bestand: () => ({ lehrgaenge: [] }),
    antworten: [
      ["GET", /^\/api\/pruefungen\/lehrgaenge$/, (m, body, z) => ({ lehrgaenge: z.lehrgaenge })],
    ],
    dateien: [],
    teile: {
      grund: info("Lehrgang öffnen", "Hier stehen die Lehrgänge, in denen du eingetragen bist."),
      leitung: info("Teilnehmende eintragen", "Als Leitung eines Lehrgangs trägst du dort Teilnehmende ein und setzt das Lehrgangsergebnis."),
      redakteur: info("Lehrgang anlegen", "Als Redakteur legst du hier eigene Lehrgänge an."),
    },
  });
})();
