/* Übungsdatei der Einführung: Materialablage (Bauvorlage planung/tutorial/entwurf.md, Abschnitt 3.1; Schnittstelle
   S.einfuehrung.modul in app/static/js/einfuehrung.js; Teile und Titel der Abläufe stehen auch in app/einfuehrung.py,
   TEILE – tests/test_einfuehrung.py vergleicht beide).
   Gehört dem Modul-Teil; Grundgerüst nur Gerüst. Je Teil ein Ablauf mit einem Info-Schritt auf der Startseite und die
   Antworten, die die Startseite zum Zeichnen braucht (leerer, aber gültiger Bestand). Übungsdaten nur als Platzhalter
   „Übung“, Kennungen im Bereich 9000000xx. */
(function () {
  // Was die Übersicht unter „darf“ liefert, ist in der Übung das data-darf der Seite (Rechte des Teils, app/einfuehrung.py).
  const darf = () => { try { return JSON.parse(document.getElementById("mat").dataset.darf || "{}"); } catch (e) { return {}; } };
  const nullen = { ausgesondert: 0, bald_faellig: 0, einsatzbereit: 0, gesperrt: 0, lebensdauer: 0, neu: 0, ueberfaellig: 0 };
  const STATUS = { ausgesondert: "ausgesondert", bald_faellig: "bald fällig", einsatzbereit: "einsatzbereit", gesperrt: "gesperrt",
                   lebensdauer: "Lebensdauer erreicht", neu: "neu", ueberfaellig: "überfällig" };
  const ORDNERARTEN = { fahrzeug: "Fahrzeug", gliederung: "Gliederung", persoenlich: "persönlich", set: "Set",
                        sonstiges: "sonstiges", standort: "Standort" };
  const info = (titel, text) => ({ ablaeufe: [{ titel, start: "/materialablage", schritte: [{ ziel: ".mat-reiter", text }] }] });

  S.einfuehrung.modul("material", {
    bestand: () => ({ ordner: [], artikel: [] }),
    antworten: [
      ["GET", /^\/api\/material\/ordner$/, (m, body, z) => ({ ordner: z.ordner, ordnerarten: ORDNERARTEN })],
      ["GET", /^\/api\/material\/start$/, () => ({
        antraege_offen: 0, aussonderung_empfohlen: [], bestand: 0, darf: darf(), erinnerungen: null, faellig_gesamt: 0,
        gliederungen: [], maengel: [], maengel_gesamt: 0, mailfehler: null, meine_psa: null, meldungen_offen: null,
        nacharbeit: [], naechste: [], ordner_uebersicht: [], rueckrufe: [], schwelle_tage: 30, status_text: STATUS,
        zaehlung: Object.assign({}, nullen) })],
      ["GET", /^\/api\/material\/durchgaenge$/, () => ({ durchgaenge: [] })],
      ["GET", /^\/api\/material\/freigaben\/meine$/, () => ({ alles: Boolean(darf().alles), freigaben: [],
        qualifiziert: Boolean(darf().qualifiziert), zugang: true })],
    ],
    dateien: [[/\/(pdf|sammelprotokoll)$|\.pdf$/, "/static/uebung/uebungsdatei.pdf"]],
    teile: {
      grund: info("Zurechtfinden", "Das ist die Materialablage. Oben wechselst du zwischen Übersicht, Prüfungen, Bestand und Katalog."),
      pruefer: info("Prüfung durchführen", "Als Prüfer findest du fällige Artikel unter „Prüfungen“ und prüfst sie direkt am Artikel."),
      materialwart: info("Artikel anlegen", "Als Materialwart pflegst du unter „Bestand“ die Ordner und Artikel deines Bereichs."),
      verwaltung: info("Katalog und Prüfformular", "Als Material-Verwaltung pflegst du unter „Katalog“ Produkte und Prüfformulare für alle Gliederungen."),
    },
  });
})();
