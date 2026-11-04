/* Übungsdatei der Einführung: Ankerplätze (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.3; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide).
   Gehört dem Modul-Teil; Grundgerüst nur Gerüst. Je Teil ein Ablauf mit einem Info-Schritt auf der Startseite und die
   Antworten, die die Startseite zum Zeichnen braucht (leerer, aber gültiger Bestand). Übungsdaten nur als Platzhalter
   „Übung“, Kennungen im Bereich 9200000xx; Bilder nur unter /static/uebung/. */
(function () {
  const info = (titel, text) => ({ ablaeufe: [{ titel, start: "/ankerplaetze", schritte: [{ ziel: "#map", text }] }] });

  S.einfuehrung.modul("karte", {
    bestand: () => ({ alben: [], bilder: [] }),
    antworten: [
      ["GET", /^\/api\/map$/, (m, body, z) => ({ photos: z.bilder })],
      ["GET", /^\/api\/albums$/, (m, body, z) => ({ albums: z.alben })],
    ],
    dateien: [],
    teile: {
      grund: info("Karte und Album", "Auf der Karte stehen die Ankerplätze mit ihren Bildern."),
      redakteur: info("Album anlegen", "Als Redakteur legst du über „Album anlegen“ eigene Alben an und lädst Bilder hoch."),
    },
  });
})();
