<!-- Wörtlicher Auszug aus den Katalogregeln des Katalogimports (REGELN.md, Stand 25.10.2026), übernommen am
21.11.2026 für die Recherche per Claude API (services/recherche.py, Entscheidung E3 A). Ausgelassen ([…]): Arbeitsweise,
Lieferung, Sets, interne Pfade und Abgleich mit Nutzerlisten. Bei jeder Änderung der Katalogregeln nachziehen und den
Stand oben ändern. Alles vor der ersten Überschrift „## “ geht nicht an Claude. -->

## Quellen
- Nur offizielle Herstellerquellen (Produktseite, Notice/Gebrauchsanleitung, Datenblatt, Konformitätserklärung,
  Prüfanweisung) mit Fundstelle: Dokument, Version/Datum, Seite, wörtliches Zitat.
- Herstellerquelle geht vor Shop (Farbnamen, Nummern, Inhalt); Abweichungen in den Bericht mit Rückfrage an den
  Hersteller.
- Händler (waterrescue.bayern, industriekletter-material.de, decathlon.de …) nur zur Identifikation; Händlernummer/-bild
  nur gekennzeichnet und nur, wenn der Hersteller nichts hat oder der Nutzer es ausdrücklich will. Archiv (Wayback),
  Papertrail, Händlerkopien von Erklärungen nur gekennzeichnet.
- Nichts erfinden, schätzen oder von einem anderen Produkt übertragen.
- […] jedes PDF
  prüfen (echt, lesbar, gehört zum Modell). Erklärungen VOLLSTÄNDIG lesen (alle Seiten, Datum, alle Normen). Gedrehte oder
  als Grafik gesetzte Randtexte (Edelrid „54530 10.26“) rendern und lesen – nie „ohne Versionsangabe“, wenn etwas
  gedruckt ist. […]

## Umfang
- Je Herstellerartikelnummer ein Produkt; ALLE aktuellen Varianten mit eigener Nummer (Größen, Farben, Ausführungen,
  ANSI/international, Sonderfarben, RFID/NFC, Inox …), keine anderen Modelle.
- Ältere Versionen (beim Hersteller nicht mehr gelistet): aufnehmen mit Hinweis „nicht mehr im Herstellerangebot“, Daten
  nur aus Unterlagen genau dieser Version (Webarchiv, Papertrail, Herstellerseiten anderer Länder – gekennzeichnet),
  Nachfolger nennen; trägt die ältere Version denselben Namen wie ihr Nachfolger, endet ihre Bemerkung mit „ältere
  Version“.
- Produkte ohne Konformitätserklärung: aufnehmen, Normfeld nur nach Herstellerseite mit Hinweis, Rückfrage an den
  Hersteller; ohne Seite, Erklärung UND Bild weglassen. Händlernummern nie als Artikelnummer.
- […]

## Kategorien
[…] Keine neue Kategorie ohne Rückfrage. Sets sind keine Kategorie (Set-Produkt steht in seiner Kategorie).

## Felder
- **Hersteller**: einheitliche Schreibweise wie im Katalog (Petzl, Edelrid, CAMP, Kong, SMC, ISC, Skylotec, Singing
  Rock, Climbing Technology, Rock Exotica, Peguet, Aliens …) – nicht an die Groß/Klein-Regel anpassen.
- **Modell**: reiner Modellname. Schreibweise (Nutzer 25.10.2026, wendet der BAU an; Recherche liefert den
  Herstellerwortlaut): Wortanfänge groß, Rest klein; Ausnahmen: Abkürzungen (HMS, DNA, XL, ANSI, PMP …), römische Zahlen
  (II, III), Codes mit Ziffern (CRx2, P41, 2D643). Beispiele: „Rollclip Z“, „HMS Strike Slider II“, „Ovalone DNA“,
  „Asap Lock“, „Falcon + Top“, „Jag System“.
- **Artikelnummer**: Herstellernummer; ohne: abgeleitet und im Bericht gekennzeichnet (Seile: Modellnummer ohne
  Längenteil; Kombinations-Sets „<Sitzgurt> + <Brustgurt>“; CAMP „Referenz-Größe“ wie 298201-M).
- **Bemerkung** (≤ 80): Größe/Farbe/Ausführung; bei nur einer Ausführung leer (Maße in den Bericht); Farben wie beim
  Hersteller; leere Bemerkung → Schlüssel „beschreibung“ weglassen (der Import leert nie).
  - Karabiner: „<Verschluss>, <Farbe>“ – Verschluss genau Screwlock/Twistlock/Trilock/Balllock/Gate/Wiregate, exotische
    mit Herstellername.
  - Rollen: vorne „Single“/„Double“/„Tandem“ laut Hersteller (Beleg), Spezialfälle ohne (Liste im Bericht).
  - Ausführungen: „inter. ver.“ (ANSI/international) und „euro. ver.“ (europäisch) – nur in der Bemerkung.
  - Bandschlingen und Expressschlingen: „<Breite>mm/<Länge>cm“ (z. B. „16mm/60cm“, danach ggf. „, <Farbe>“); Maße nicht
    im Modellnamen (Recherche liefert `breite_mm`, `laenge_cm`).
  - Seile: Bemerkung = Farbe, keine Längen.
- **Norm** (K1): Normen der Konformitätserklärung mit Jahr + zusätzliche Zertifizierungen der Produktseite (UIAA, ANSI,
  NFPA, EAC …), ohne Kommentare, ohne „CE“; Einschränkungen („außer §2.2“) nur im Bericht (K2); ohne Erklärung nur die
  Zertifizierungen der Seite, Normen aus Anleitungen nur als Hinweis; Kombinationsnorm (EN 361 Brust- + Sitzgurt) nur am
  Set. **UKCA** (Nutzer 26.10.2026: „Ja“): wie jede Zusatz-Zertifizierung aufnehmen, wenn die Produktseite des
  Herstellers (bzw. deren Archivstand bei älteren Versionen) sie nennt – Schreibweise „UKCA“ ohne Zusatz, hinter den
  übrigen Zusatz-Zertifizierungen. TOP CROLL S/L (C081BA00/C081CA00): zusätzlich „EAC“ der Archivseite (Nutzer
  26.10.2026, ergänzt Entscheidung D).
  Nachtrag 26.10.2026 (Nutzer): UKCA gilt auch als belegt, wenn die Herstellerseite eine UKCA-Konformitätserklärung
  genau dieses Produkts anbietet, oder wenn die Gebrauchsanleitung des Herstellers dieses Produkt als UKCA nennt
  (Ausnahme von „Normen aus Anleitungen nur als Hinweis“, nur für UKCA; allgemeine Sätze wie „UKCA-Erklärungen auf der
  Website“ ohne Produktbezug nur als Hinweis). Fehlende Zusatz-Zertifizierungen der Seite (EAC, GB/T, XF 494, NFPA,
  CSA, ANSI, JSFAD, UIAA, TS 16415 …) werden nachgetragen (K1 vollständig; Beal erst nach Rückfrage). Trenner im
  Normfeld überall „, “ (Komma + Leerzeichen).
  Seiten mit mehreren Produkten/Blöcken: Werte nur aus dem Block genau dieses Produkts (Blocküberschrift im Zitat).
  Offensichtliche Druckfehler der Herstellerseite (z. B. „XF 949“, „ANSI 459.1“, „ANSI Z459.1“) nicht übernehmen,
  sondern als Rückfrage an den Hersteller im Bericht (Abschnitt 8); vorhandener Altbestand bleibt bis zur Antwort.
- **Materialart** textil / metall_hardware / sonstiges. Textil: Lebensdauer min(Herstellerzahl ab Herstellung, 10), ohne
  Zahl 10 mit Vermerk, Edelrid überall 10. Metall: keine Lebensdauerzahl („unbegrenzt“ nur im Zitat).
  lebensdauer_quelle ≤ 300 Zeichen, Zitate nicht verstümmeln (zu lang → melden).
- **Intervall** überall 12 Monate; Zitat, sonst Vermerk „Intervall nicht vom Hersteller belegt“ (K3).
- **Dokumente**: Gebrauchsanleitung, Konformitätserklärung (deutsche Fassung, z. B. CAMP K5), Prüfanweisung (nie
  entfernen, K7), Datenblatt; deutsche Fassung beim Hersteller vorhanden → sie ERSETZT die fremdsprachige, wo möglich
  (Nutzer 26.10.2026; als neue Version über „vorgaenger", Zitate auf die deutsche Stelle umstellen; weicht der Inhalt ab:
  zusätzlich aufnehmen); ohne Herstellerquelle auch die deutsche Händlerkopie, wenn sie erkennbar das unveränderte
  Herstellerdokument ist (Nutzer 26.10.2026; Titel „(deutsch; Kopie: Händler <Name>)", Echtheit in der Fundstelle begründet); Version wie gedruckt (Petzl-Code ist kein Datum, K4), gueltig_ab nur mit gedrucktem
  Tagesdatum (mehrere Daten: Spanne als Version, spätestes als gueltig_ab), version ≤ 40; gleiche Datei (SHA-256) überall
  mit EINER Beschriftung; Verpackungserklärungen „sonstiges“ oder raus; Prüfformulare der App (mat_form) nicht im Katalog, PDF-Prüfberichte der Hersteller (z. B. Petzl) als „sonstiges“; Peguet K10.
- **Bild**: genau diese Nummer/Farbe/Ausführung; sonst Händlerbild mit Vermerk; sonst keins. Hat der Hersteller später ein
  passendes Bild, ERSETZT es ein vorhandenes Händlerbild (Nutzer 26.10.2026). CAMP-Karabiner:
  Frontalansicht, wo vorhanden.
- **Seile**: ohne Länge, je Modell UND Farbe ein Produkt (Länge am Artikel).
