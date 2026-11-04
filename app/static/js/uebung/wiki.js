/* Übungsdatei der Einführung: Strömipedia (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.2; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide).
   Gehört dem Modul-Teil; Grundgerüst nur Gerüst. Je Teil ein Ablauf mit einem Info-Schritt auf der Startseite und die
   Antworten, die die Startseite zum Zeichnen braucht (leerer, aber gültiger Bestand). Übungsdaten nur als Platzhalter
   „Übung“, Kennungen im Bereich 9100000xx. */
(function () {
  const info = (titel, text) => ({ ablaeufe: [{ titel, start: "/stroemipedia", schritte: [{ ziel: "#wiki-content", text }] }] });

  S.einfuehrung.modul("wiki", {
    bestand: () => ({ seiten: [] }),
    antworten: [
      ["GET", /^\/api\/wiki\/tree$/, (m, body, z) => ({ pages: z.seiten })],
    ],
    dateien: [],
    teile: {
      grund: info("Lesen", "Das ist die Strömipedia. Den Seitenbaum findest du links – am Telefon hinter „☰“."),
      redakteur: info("Seite anlegen", "Als Redakteur legst du über „Neue Seite“ eigene Seiten an und bearbeitest sie."),
      verwaltung: info("Für alle Angemeldeten freigeben", "Als Wiki-Verwaltung gibst du Seiten über „Teilen“ für alle Angemeldeten frei."),
    },
  });
})();
