# Changelog: Modul „Material“ (Phase 1, MVP, und Phase 2)

Material- und Prüfmanagement für strömis.de nach dem Konzept vom 16.10.2026: Ausrüstungsbestand der
Gliederungen, Prüfnachweise je Ausrüstungsteil, später unveränderliche PDF-Prüfprotokolle. Phase 1 ist in fünf
Lieferungen umgesetzt, Phase 2 (mehrere Gliederungen und externe Prüfer in einer Instanz) folgt in drei; jede ist
für sich deploybar.

| Lieferung | Inhalt | Stand |
| --- | --- | --- |
| 1 – Fundament | Schema, Migration, Rollen, Katalog mit Dokumenten und Formularen, Ordnerbaum, Artikel, Suche, Journal | geliefert 16.10.2026, freigegeben 17.10.2026 |
| 2 – Prüfung | Prüfformular, Mangelfoto, Anhänge, Ergebnis, Sperre, Aussonderung, Lebenslauf, Prüfdurchgang; dazu Status „neu“ mit Eingangsprüfung, Prüfen jederzeit, Ordnernavigation | geliefert 17.10.2026, freigegeben 17.10.2026 |
| 3 – Nachweis | Unterschrift, Festschreiben, PDF mit Prüfsumme, Prüfseite; dazu Berichtigung und Unterschriftsfelder | geliefert 17.10.2026, freigegeben 17.10.2026 |
| 4 – Überblick | Übersicht mit Fälligkeiten je Ordner, Führungskraft nur lesend, QR-Adresse mit Status, Export (CSV, Protokoll-ZIP, Lebenslauf-PDF); dazu Katalogaustausch (Katalog und Formulare von dev in die Produktion, ohne Bestand und Prüfungen) und Rückrufe zu Produkten (Hinweis in der Anwendung und per Mail). Kein Etikettenbogen (nicht gewünscht) | geliefert 17.10.2026, freigegeben 17.10.2026 |
| 5 – Feinschliff | Rückmeldungen aus dem Pilotbetrieb: Ordnerkopf, einheitliche Knöpfe, Suchvorschläge, Urkundennummer im Profil, Pflicht-Bemerkung bei Mangel, Produktsuche, Bedienung auf Telefon, Foldable und Tablet | geliefert 18.10.2026, freigegeben 18.10.2026 („Starte mit Phase 2“) |
| Phase 2 · 1 – Freigaben je Ordner | Freigaben lesen/prüfen/verwalten je Ordner mit Vererbung und Enddatum, strenge Trennung je Gliederung, Freigaben im Dialog „Ordner bearbeiten“ (Reiter) mit Vorlagen und Verlängern, „Meine Freigaben“; globale Seriennummernsuche und QR-Steckbrief mit Protokoll; Personenzuordnung; Rückrufe und Meldungen je Bereich; Löschkonzept | geliefert 18.10.2026, die drei offenen Fragen am 18.10.2026 entschieden und eingearbeitet; freigegeben 19.10.2026 („Starte Lieferung 2“) |
| Phase 2 · 2 – Erinnerungen | Täglicher Erinnerungslauf ab 6 Uhr (eingebaut, abschaltbar, dazu `flask material remind`): Sammelmail an die Verwalter zu Fälligkeit (30/7 Tage, überfällig), Lebensende (90 Tage) und ablaufenden Freigaben (30 Tage); Erinnerungslog mit Kontoverweis; „Erinnerungsmails aus“ je Ordner; Laufstand und Probelauf auf der Übersicht | geliefert 19.10.2026, wartet auf Freigabe |
| Phase 2 · 3 – Bestandsimport und Prüfanleitung | Bestandslisten aus Excel oder CSV in einen Ordner: Probelauf, Übernehmen in einer Transaktion (Artikel auf „neu“, Fälligkeit aus der Liste, STR-Nummern für Zeilen ohne Seriennummer, eine Liste ganz ohne Seriennummernspalte nur mit Häkchen) und Nacharbeit je Zielordner (Produkte zuordnen, melden oder im Katalog anlegen, erneut prüfen, CSV-Rundweg, Frist ein Monat); Prüfanleitung aus dem Wiki am Prüfformular, Abschnitt „Prüfung“ eingeblendet in offenen Prüfungen | geliefert 19.10.2026, vier Punkte am 20.10.2026 entschieden (einer geändert und eingearbeitet), wartet auf Freigabe |
| Artikellänge (Schritt 20) | Häkchen „Artikel haben eine Länge“ je Kategorie (vererbt), Feld „Länge (m)“ am Artikel (Steckbrief, Listen, Lebenslauf, Meine PSA, CSV, Bestandsimport), Prüfpunkt-Typ „Länge“ – vorbelegt, ein abweichender Wert geht beim Festschreiben in den Artikel (Journal, Protokoll „alt → neu“) | gebaut 22.10.2026, wartet auf Freigabe |
| Phase 4 · 2 – Sets mit Komponenten | Hersteller-Sets: Stückliste im Katalog (auch in der Katalogdatei), Set-Artikel mit Teil-Artikeln, Set-Status, -Fälligkeit und -Lebensende, Listen mit der Set-Zeile, Verschieben und Zuordnen mit allen Teilen, Meine PSA; Sperr-Kaskade, Set prüfen mit Set-Protokoll, Austausch, Aussondern mit Wahl je Teil, Oberfläche | geliefert 23.10.2026 (c5e1b06), freigegeben 23.10.2026 |
| Phase 4 · 2b – Sets, Teil 2 | Vorhandenen Artikel als Teil einsetzen (mit Auswahl, auch über die bisherige Inventarnummer), Set auflösen, „Bestandteil ersetzt“, Prüfumfang eines nie geprüften Sets; dazu (KERN Z) Zahlen, CSV-Spalten, gebündelte Mails | geliefert 23.10.2026 (Schema bleibt 21) – wartet auf Freigabe |
| Feintuning nach dem Kommentar-Dokument | Produkt am Artikel ändern bis zur ersten Prüfung (Dialog „Bearbeiten“, Weg aus „aus dem Bestand wählen“), Jahresbericht: ausgesondertes Set als eine Zeile, weitergeführte Teile mit eigener Sperre | gebaut 23.10.2026 (Schema bleibt 21) – wartet auf Freigabe |
| Katalogimport im Hintergrund | Probelauf und Übernehmen laufen als Auftrag im Hintergrund (202, Stand per Abfrage, Bericht wie bisher), „Übernehmen“ ohne neuen Upload, höchstens ein Import gleichzeitig, Abbruch bei Neustart erkannt, Hinweis auf der Katalogseite; Nachbesserung nach der Sicherheitsprüfung (Kontoverweis statt Kontokennung und Name, Plattenplatz, Übernehmen nach Abbruch wiederholbar, dev-zuruecksetzen wartet) | gebaut 24.10.2026 (kein Schemaschritt, Schema bleibt 21) – wartet auf Freigabe |
| Sets anlegen und Stückliste übertragen (Schritt 22) | Knopf „Set anlegen“ (Produkt und Stückliste in einem Zug, mindestens ein einzeln geführtes Teil), Umstellen Produkt ↔ Set nur per Katalogdatei, „Stückliste übertragen“ auf angelegte Sets mit Vorschau, Fehlendes Produkt oder Set melden, Begriff „Set“, Ordnerart „Set-Ordner“ | gebaut 24.10.2026, wartet auf Prüfung und Freigabe |
| Änderungsanträge an alle Stammdaten (Schritt 23) | Freigabepflichtig nach der ersten Prüfung: Produkt, Seriennummer, Herstellung, Kauf, Erstgebrauch, Lebensende, Prüfintervall – als ein Sammelantrag; entscheiden die Materialwarte des Ordners (auch den eigenen Antrag, die Material-Verwaltung nur mit eigener Verwalterfreigabe); Liste „Änderungsanträge“ im Bestand, Katalog → Meldungen nur Produkt- und Set-Meldungen; Prüfer bearbeiten Bemerkung, Länge, nächste Prüfung; Produktänderungen im Lebenslauf; Nachtrag 25.10.2026 (Schritt 24): Lebensende per Antrag auch wieder nach hinten bis zur Rechnung | gebaut 24.10.2026, Nachtrag 25.10.2026, wartet auf Prüfung und Freigabe |
| Wünsche vom 25.10.2026 (W1–W4) | Norm in eigener Zeile auf der Artikelseite; Nacharbeit: „Übernehmen …“ und nach dem Zuordnen direkt übernehmen, „Fehlendes Produkt melden“ vorbelegt; Bestand: Spalte „Kategorie“, Filtermenü in der Seitenleiste mit „Filter (n)“; Wiki: Seiten aus ZIP importieren | gebaut 25.10.2026 (kein Schemaschritt), wartet auf Prüfung und Freigabe |
| Bestandteil-Liste an normalen Produkten (Schritt 25) | Herstellersets als flache Produkte mit Liste „Bestandteile“ (Bezeichnung und Anzahl): Produktdialog, Produkt- und Artikelseite, Meine PSA, Lebenslauf; jede Prüfung fragt je Position „vorhanden“ ab („fehlt“ = Mangel); Katalogdatei; Set-Meldung → „Produkt anlegen“; dazu Seriennummern der Bestandteile je Stück am Artikel (direkt bis zur ersten Prüfung, dann in der Prüfung oder per Antrag, suchbar) | gebaut 25.10.2026, wartet auf Prüfung und Freigabe |
| Nachbesserung L2c nach den Prüfungen | Bestandteile: Kennung nie an eine andere Position, Bezeichnung mitverglichen; Berichtigung gegen den wirksamen Wert; Protokoll ohne „neu“, wo nichts übernommen wurde; Wettlauf Prüfung ↔ Antrag 409; Steuerzeichen; Rückweg 25; Ordnerliste ohne Überlauf (Kategorie über dem Hersteller), Prüfung „fehlt“, doppelte Nummer als Hinweis, Schublade, Produktseite „Mehr“ | gebaut 25.10.2026, wartet auf Freigabe |
| Nachbesserung Sets und Anträge nach den Prüfungen | Sets: Kennungen der Kopie, „Anzahl verringert“, Texte; Anträge: Produktgeschichte nach Wechsel, Intervall-Obergrenze nur bei Änderung, Fälligkeit ohne Namen, 409 statt 500, Texte, Zähl-Aufruf | gebaut 25.10.2026, wartet auf Prüfung und Freigabe |
| Neue Modulnamen | Strömipedia, Ankerplätze, Riegenkarten, Materialablage, Leitstelle samt Adressen; alte Adressen leiten dauerhaft weiter (301, Abfrage bleibt, Umlaut-Schreibweisen), neue Protokolle mit `/materialablage/pruefen` | gebaut 26.10.2026, wartet auf Prüfung und Freigabe |
| Feinschliff aus den Wiki-Fragen | „Deine PSA“ auch in Ordnern mit „Erinnerungsmails aus“ (E2 B), Verlauf des Kontos im Nutzerdialog der Leitstelle (E3 A), geerbtes generisches Formular in der Kategorie (K9), Texte (K19, K21, T, E1, E6), README | gebaut 26.10.2026, wartet auf Prüfung und Freigabe |
| Katalog am Telefon (26.10.2026) | „☰ Kategorien“ links in der mitlaufenden Suchzeile der Katalogliste; keine Nummernsuche in den Katalogansichten | gebaut 26.10.2026 (kein Schemaschritt), wartet auf Prüfung und Freigabe |

## Abgleich mit dem Bestand (vor Lieferung 1)

- **Andocken.** Eigenes Paket `app/material/` mit zwei Blueprints: Seiten unter `/material…` und `/m/<token>`,
  Schnittstelle unter `/api/material…`, dazu eigenes Template und eigener Static-Ordner (`/static/material/`).
  Muster wie im Prüfungsbereich: Die Seite ist eine dünne Hülle, `material.js` baut den Inhalt aus JSON. Das
  Schema läuft in der vorhandenen Startmigration (`db.init_db`) mit; das Modul meldet seine Migration dort an
  (`db.SCHEMA_MODULE`) und führt seine Version selbst in `mat_meta`.
- **Wiederverwendet.** Datenbankhelfer (`db.query/execute/transaction(sofort=True)`), die Rechte-Matrix,
  `images.store_upload` für Produkt- und Ordnerfotos (EXIF-Drehung, HEIC, Web- und Vorschaufassung),
  Größenbremse und CSRF-Schutz, die Einstellungen im Browser, Layout und Bausteine aus `app.css`, Flask-CLI,
  der Testrahmen (`make_app`, Testclient).
- **Rollen.** Rollen gibt es seit dem 16.10.2026 nicht mehr, sondern die Rechte-Matrix je Modul. Material ist
  dort die fünfte Spalte: Mitglied = Führungskraft (lesend), Verwaltung = Materialwart. Prüfer und
  Produktkatalogpfleger stehen quer dazu als zwei Kennzeichen am Konto; Prüfer wirkt nur mit Urkundennummer.
  Wer eines davon trägt, hat mindestens Leserecht. Die Verwaltung (Admin) ist überall Materialwart und
  Katalogpfleger, aber nie von selbst Prüfer – Sachkunde wird nachgewiesen, nicht verwaltet. Die Rollen gelten
  im MVP global; die Trennung je Gliederung kommt in Phase 2 über `mat_folder_grant`, die der Decorator
  `@requires_folder` dann zusätzlich auswertet (er löst den Ordner jeder Anfrage schon heute auf).
- **Abweichungen vom Konzept.** Siehe unten unter Lieferung 1.

## Lieferung 1 – Fundament (16.10.2026)

### Neu

- **Schema** (`app/material/models.py`): alle 14 Tabellen aus dem Auftrag (`mat_category`, `mat_product`,
  `mat_product_document`, `mat_form`, `mat_checklist_item`, `mat_folder`, `mat_item`, `mat_inspection`,
  `mat_inspection_result`, `mat_inspection_attachment`, `mat_round`, `mat_folder_grant`, `mat_reminder_log`,
  `mat_audit`) plus `mat_meta` (Schemaversion, Inventarzähler, Volltext an/aus) und `mat_round_item`. Auch die
  erst ab Lieferung 2 und Phase 2 genutzten Tabellen sind angelegt. Regeln, die die Datenbank selbst halten
  kann, stehen als CHECK oder eindeutiger Index darin: Lebensdauer je Materialart, höchstens ein aktives
  Formular je Ziel, höchstens ein offener Prüfentwurf (= Reservierung) je Artikel, Dublettenschlüssel,
  Prüfrechte nur befristet. Das Journal ist per Trigger nur fortschreibbar.
- **Volltextindex** (FTS5 mit Trigrammen) für Katalog- und Nummernsuche, über Trigger aktuell gehalten. Fehlt
  FTS5 oder der Trigramm-Zerleger (SQLite älter als 3.34), läuft die Suche ohne Index über LIKE weiter.
- **Rollen** in der Nutzerverwaltung: Spalte „Material“ in der Matrix; Häkchen „Prüfer“ mit Urkundennummer
  und „Produktkatalogpfleger“ im Nutzerdialog. Ohne Urkundennummer weist der Server die Prüferrolle ab.
  Rollenänderungen schreiben einen Journaleintrag (Entität `user`).
- **Katalog**: Kategorien (Baum, Norm, Vorgabe-Materialart, -Intervall, -Lebensdauer nur textil), Produkte mit
  Dublettenprüfung und Lebensdauerregeln, Produktbild, Herstellerdokumente mit Versionen und Zurückziehen,
  Prüfformulare mit Versionen, Aktivieren/Deaktivieren und Editor. Serverseitige Suche mit Seiten.
- **Bestand**: Ordnerbaum mit Systemordnern, Artikel anlegen (Produktsuche, Vorschläge für nächste Prüfung und
  Lebensende), bearbeiten, löschen (nur ohne Prüfung), einzeln und mehrfach verschieben.
- **Suche** nach Serien-, Inventar- und Herstellernummer mit Teiltreffern; ein eindeutiger Treffer öffnet den
  Artikel (`/material/suche?q=…` leitet weiter). `/m/<token>` führt über die Anmeldung zum Artikel.
- **Journal** mit Vorher/Nachher je Feld an Produkt (samt Dokumenten und spezifischen Formularen), Artikel
  (samt Produkt) und Ordner.
- **Oberfläche**: Übersicht, Prüfungen (fällig/überfällig), Bestand, Katalog, Suche; DLRG-CD, auf dem
  Telefon als Karten ohne Querscrollen.
- **Kommandozeile**: `flask --app "app:create_app()" material import-catalog datei.json [--trocken]`.
- **Demodaten**: `python scripts/material_demo.py --demo` – nur mit Schalter, außerhalb von `app/`, läuft damit
  nie im Docker-Image. Alles darin heißt „DEMO …“, trägt das Kennzeichen `demo` und wird überall als
  „DEMO – nicht für echte Prüfungen“ markiert; Prüfpunkte sind ausdrücklich Platzhalter.
- **Einstellung** `MATERIAL_BALD_FAELLIG_TAGE` (Vorgabe 30), auch unter „Verwaltung → Einstellungen“.

### Migration

- Beim ersten Start legt die Anwendung die Tabellen an und setzt `mat_meta.schema_version = 1`. Der Lauf ist
  wiederholbar und verträgt mehrere gleichzeitig startende Arbeitsprozesse (Schreibsperre, Version unter der
  Sperre neu gelesen).
- `users` bekommt `recht_material`, `mat_pruefer`, `mat_katalog`, `urkundennummer`, `signature_png`. Wer schon
  Verwaltung im Modul Verwaltung hat, bekommt Material = Verwaltung; alle anderen haben zunächst keinen Zugang –
  die Verwaltung vergibt ihn in der Nutzerverwaltung.
- Keine bestehende Tabelle wird umgebaut; ein Zurückspielen der Sicherung von vorher ist jederzeit möglich.

### Neue Abhängigkeiten

Keine. WeasyPrint (mit Pango und Cairo im Image), pypdf ≥ 5, segno und signature_pad.js kommen mit den
Lieferungen 3 und 4, in denen sie gebraucht werden.

### Entscheidungen zu den offenen Punkten

- **Rangfolge der Prüfintervalle.** Innerhalb jeder Seite überschreibt die genauere Ebene: Herstellerseite =
  Produkt, sonst Kategorie (mit Oberkategorien); Organisation = Artikel, sonst der nächste Ordner bis zur
  Gliederung. Zwischen den Seiten gilt das kürzere Intervall – die Herstellerangabe ist eine Obergrenze, die
  eine Gliederung verschärfen, aber nicht verlängern kann. Am Artikel wird ein längerer Wert gar nicht erst
  angenommen; die Oberfläche nennt die Herkunft („6 Monate – Ordner „Fahrzeug““).
- **Rollen global oder je Gliederung.** Global im MVP (siehe Abgleich); je Ordner über Freigaben ab Phase 2.
- **`/m/<token>` ohne Anmeldung** führt zur Anmeldung und danach zum Artikel; ohne Zugang zum Modul gibt es
  403, ohne passenden Artikel 404 – ein Unbefugter erfährt nicht, ob es den Artikel gibt.
- **Verlust** und **`/material/pruefen`** entscheide ich mit den Lieferungen 2 und 3; vorgesehen ist der
  Vorschlag aus dem Auftrag (Sperre mit Grund „Verlust“ durch den Prüfer; Prüfseite öffentlich, nur
  „unverändert/verändert“ plus Protokoll-ID).

### Abweichungen vom Konzept, mit Begründung

- `mat_round_item` statt der Spalte `excluded` an `mat_round`: Ein Durchgang braucht die Liste seiner Artikel
  (Fortschritt, Abschlussbedingung), auch wenn ein Artikel während des Durchgangs gesperrt und damit in
  „Gesperrt“ verschoben wird. Der Ausnahmegrund steht je Artikel in derselben Zeile.
- `mat_checklist_item.group_name` statt `group` (SQL-Schlüsselwort).
- `mat_category.default_material_kind`: Ohne sie ließe sich „Lebensdauer nur bei textilen Kategorien“ nicht
  prüfen; zugleich Vorbelegung beim Anlegen eines Produkts.
- `mat_product.lifetime_source` (Fundstelle der Herstellerangabe): Grundlage für „bei sonstiges nur mit
  Herstellerangabe“ und für die Nachvollziehbarkeit jeder Lebensdauer.
- `mat_product.dedupe_key`: vereinheitlichter Schlüssel aus Hersteller + Modell + Artikelnummer (nur
  Buchstaben und Ziffern, Groß/klein egal, „-“ als Artikelnummer = keine). Fängt die Dubletten, die der
  Testaccount von homebase zeigte („Gurt / -“, „gurt / .“).
- `mat_audit` kennt zusätzlich die Entitäten `category`, `form`, `round` und `user`; Namensschnappschüsse
  (`*_name`) und das Kennzeichen `demo` wie im übrigen Bestand.
- `mat_inspection` hat schon jetzt `inspector_name`, `inspector_certificate` (Urkundennummer zum Prüfzeitpunkt),
  `reason`, `documents_json` (gültige Herstellerdokumente zum Prüftag), `completed_at` und `protocol_id`.
- Oben im Ordnerbaum stehen nur Gliederungen. So hat jeder Artikel eine Gliederung und damit die Systemordner,
  in die Sperre und Aussonderung ihn verschieben.
- `mat_item.retire_by_manual`: ein von Hand vorgezogenes Lebensende. `retire_by` ist immer das frühere aus
  Rechnung (Herstellung + Lebensdauer) und diesem Datum – so bleibt „vorgezogen“ auch dann erhalten, wenn die
  Lebensdauer am Produkt korrigiert und wieder zurückgesetzt wird.
- Eindeutiger Index auf `mat_product_document.replaces_id`: Jede Dokumentversion hat höchstens einen Nachfolger.
- Herstelldatum als Monat (`JJJJ-MM`) oder Tag; bei textilem Material Pflicht, weil daran das Lebensende hängt.
  Bei einer Monatsangabe zählt der Monatserste – das Lebensende kommt eher zu früh als zu spät.
- Ohne Prüfung liegt die nächste Fälligkeit höchstens ein Intervall in der Zukunft; danach lässt sie sich nur
  vorziehen. Wird das wirksame Intervall kürzer (anderes Produkt, kürzere Vorgabe an Artikel, Ordner, Produkt
  oder Kategorie, Verschieben in einen strengeren Ordner), zieht das System Fälligkeiten hinter „heute + neues
  Intervall“ auf diese Grenze vor und vermerkt es im Journal des Artikels. Kauf und Erstgebrauch liegen nie in
  der Zukunft. Das Lebensende lässt sich ebenfalls nur vorziehen – auch ein schon vorgezogenes nicht wieder
  nach hinten; ein leeres Feld lässt es, wie es ist.
- Eine Kategorie lässt sich nicht so ändern, dass Produkte, die ihr Intervall von ihr erben, keins mehr haben.
- Ein Artikel lässt sich nur löschen, solange er keine Prüfung hat (Tippfehler beim Anlegen); seine
  Inventarnummer wird trotzdem nie wieder vergeben. Alles andere wird künftig ausgesondert, nicht gelöscht.
- Herstellerdokumente werden nicht gelöscht, sondern abgelöst oder zurückgezogen – ein altes Protokoll muss
  auf die damals gültige Fassung verweisen können.

### Review vor der Auslieferung

Ein unabhängiger Review hat den Code von Lieferung 1 vor der Auslieferung geprüft: Rechte, SQL, XSS, Pfade, CSRF
und Migration ohne Befund (Fuzzprobe über alle Routen, 8 parallel startende Prozesse, 120 gleichzeitige Anlagen
mit eindeutigen Nummern). Die 15 Befunde – keiner „hoch“ – sind behoben und stehen einzeln als Regressionstest in
`test_review_befunde` (`tests/test_material.py`):

| # | Befund | Behebung |
| --- | --- | --- |
| 1 | Errechnete erste Fälligkeit konnte hinter „heute + Intervall“ liegen (Kauf/Erstgebrauch in der Zukunft) | Daten in der Zukunft abgewiesen, Vorschlag gekappt |
| 2 | Produktwechsel oder kürzeres Artikelintervall ließ die Fälligkeit stehen | Fälligkeit zieht nach (auch bei Ordner-, Produkt-, Kategorievorgaben und beim Verschieben) |
| 3 | Kategorie ohne Intervall machte erbende Produkte intervalllos | Änderung abgewiesen (409); ohne Fälligkeit keine beliebige setzbar |
| 4 | Vorgezogenes Lebensende ließ sich zurückschieben; leeres Feld widersprach dem Hilfetext | nur vorziehen, leer = bleibt, Hilfetext angepasst |
| 5 | Vorgezogenes Lebensende ging nach Korrektur hin und zurück verloren | eigenes Feld `retire_by_manual` |
| 6 | Lebensdaueränderung schrieb auch ausgesonderte Artikel um | ausgesonderte bleiben unverändert |
| 7 | Import fand Namen mit doppeltem Leerraum nicht wieder | Namen beim Import vereinheitlicht wie beim Speichern |
| 8 | Suche mit genau einem Treffer auf Seite 2 gab 500 | behoben |
| 9 | NUL im Suchbegriff gab 500 (FTS5) | Steuerzeichen entfernt, FTS-Fehler → 400 |
| 10 | Zwei gleichzeitige „Neue Version“ ergaben zwei Nachfolger | Prüfung unter Schreibsperre plus eindeutiger Index |
| 11 | Gleichzeitiges Verschieben A→B und B→A ergab einen Zyklus | Prüfung und Schreiben unter einer Schreibsperre (auch bei Kategorien) |
| 12 | Einstellung „bald fällig“ = 0 wirkte als 30 | 0 gilt |
| 13 | 403/404 verrieten Konten ohne Modul, welche Artikel es gibt | erst Modulzugang prüfen, dann den Artikel suchen |
| 14 | Urkundennummer aus unsichtbaren Zeichen wurde angenommen | Formatzeichen entfernt, Buchstabe oder Ziffer Pflicht |
| 15 | Negative Seitengröße hob die Obergrenze auf | Seitengrößen geklemmt; die Ordneransicht blättert jetzt |

### Zu prüfen

- **Docker-Build**: In dieser Umgebung gibt es kein Docker; gebaut wurde nicht. Lieferung 1 bringt keine neue
  Abhängigkeit und ändert das Dockerfile nicht, der Build sollte also unverändert durchlaufen.
- **SQLite im Image** muss FTS5 mit Trigrammen können (ab 3.34; Debian bookworm hat 3.40). Ohne läuft die Suche
  über LIKE weiter – der Test deckt beide Wege ab.
- **Lebensende nur bei textil** (Vorgabe aus dem Auftrag): Helme und Schwimmwesten („sonstiges“) mit einer
  Lebensdauer laut Hersteller bekommen damit kein festgeschriebenes Lebensende und nie den Status
  „Lebensdauer erreicht“ – die Angabe steht nur als Hinweis am Artikel. Bitte fachlich bestätigen oder ändern.
- **Erste Fälligkeit** eines neu erfassten Artikels: Beginn der Nutzung (Erstgebrauch, sonst Kauf, sonst heute)
  plus Intervall. Altbestand ohne Prüfnachweis wird damit sofort überfällig; wer den Stand einer Papierkarte
  übernimmt, trägt die Fälligkeit von Hand ein (höchstens heute plus ein Intervall).
- **Kürzeres Intervall**: Fälligkeiten ziehen auf „heute + neues Intervall“ vor. Ohne Prüfhistorie ist das die
  einzige Grenze, die sich ziehen lässt; sobald es Prüfungen gibt (Lieferung 2), wäre „letzte Prüfung + neues
  Intervall“ genauer. Bitte fachlich bestätigen.
- **Inventarnummernformat** `M-000001` und Seriennummernformat `STR-000001` sind Vorschläge. Bisherige Nummern
  der Gliederungen haben noch kein eigenes Feld (vorerst in der Bemerkung).
- **QR-Adresse** steht in Punycode (`https://xn--strmis-yxa.de/m/…`), weil nicht jede Kamera-App Umlaute im
  Hostnamen öffnet. Das ist dieselbe Adresse wie `https://strömis.de/m/…`.
- **Normen je Kategorie** in `docs/material-katalog-vorlage.json` stammen aus den DLRG Standardverfahren
  Grundlagen V1.9; Wurfsäcke und Neopren-/Trockenanzüge haben dort keine Norm, die Materialart „textil“ ist
  eine Annahme. Intervalle, Lebensdauern, Produkte und Prüfpunkte sind bewusst leer.
- **Oberfläche** wurde in einem echten Chromium gegen den laufenden Server geprüft (Desktop 1280 px und Telefon
  390 px, alle Ansichten und die wichtigsten Abläufe), nicht aber in Safari/iOS.

### Nachbesserung nach der Auslieferung

- **Produktbild in den Listen abgeschnitten** (gemeldet am 17.10.2026): Die Vorschau entstand wie bei Karte und
  Alben als quadratischer Ausschnitt aus der Bildmitte – einem hochkant fotografierten Produkt fehlten oben und
  unten Stücke. Produktbilder bekommen jetzt eine Vorschau mit dem ganzen Bild (`store_upload(…, vorschau_ganz=True)`),
  Katalog, Bestand und „Artikel anlegen“ zeigen es vollständig auf weißem Grund. Ordnerfotos bleiben beim
  quadratischen Ausschnitt. Schon hochgeladene Produktbilder behalten ihre alte Vorschau, bis sie neu hochgeladen
  werden.

## Lieferung 2 – Prüfung (17.10.2026)

Zu den Punkten aus dem Auftrag kommen drei Wünsche aus der Durchsicht von Lieferung 1: neue Artikel stehen auf
„neu“, bis eine Eingangsprüfung gemacht ist; eine Prüfung lässt sich aus der Artikelansicht jederzeit starten;
links steht der Ordnerbaum als Navigation.

### Neu

- **Prüfung** (`services/pruefung.py`, Seiten `/material/artikel/<id>/pruefung/neu` und `/material/pruefung/<id>`):
  Ein Prüfer startet sie aus der Artikelansicht, der Liste „Prüfungen“ oder einem Prüfdurchgang – jederzeit, nicht
  erst wenn sie fällig ist. Es entsteht ein Entwurf mit einer Kopie der Prüfpunkte des passenden Formulars (aktives
  spezifisches des Produkts, sonst aktives generisches der Kategorie oder der nächsten Oberkategorie). Jeder Befund
  ist mit „in Ordnung“ vorbelegt, Ja/Nein-Punkte mit ihrem Sollwert; bei Zahl und Text ist das Soll seit
  Lieferung 1 ein Hinweis und steht als Platzhalter im Feld (nur ein Soll, das selbst eine Zahl ist, wird als Wert
  vorbelegt). Jede Eingabe geht sofort an den Server; der Entwurf ist immer gespeichert.
- **Eingangsprüfung und Status „neu“**: Ein Artikel ohne abgeschlossene Prüfung hat den Status „neu“ (blau) –
  auch mit einer Fälligkeit in der Zukunft. Seine erste Prüfung ist immer die Eingangsprüfung; erst sie gibt ihn
  frei und setzt die erste Fälligkeit. „neu“ zählt zum Bestand, steht in Übersicht, Ordnerzählern, Filtern und in
  der Liste „Prüfungen“ (Standard: überfällig, neu, bald fällig).
- **Prüfformular fürs Telefon**: je Prüfpunkt eine Karte mit großen Umschaltern (Ja/Nein/n. z. bzw. in Ordnung/
  Mangel/n. z.), Kamera-Knopf und Bemerkung bei Bedarf; unten eine feste Leiste mit Ergebnis, nächster Fälligkeit
  oder Grund und „Abschließen“. Die Leiste zeigt vorab, was der Server prüfen wird (Pflichtpunkte ohne Befund,
  Mangel ohne Foto, kritischer Mangel, Lebensende).
- **Regeln beim Abschluss**: Pflichtpunkte brauchen einen Wert oder „nicht zutreffend“; jeder Mangel braucht ein
  Foto; ein kritischer Mangel und ein erreichtes Lebensende (nur textil) schließen „einsatzbereit“ aus; die
  nächste Fälligkeit ist Prüftag + wirksames Intervall und lässt sich nur vorziehen (frühestens auf morgen);
  „instandsetzen“ und „aussondern“ ohne Mangel brauchen einen Grund. Am Prüftag gültige Herstellerdokumente
  werden mit der Prüfung gespeichert.
- **Anhänge** (`services/anhang.py`): externes Prüfformular, Prüfbericht, Foto, Sonstiges – immer als ein PDF.
  Ein hochgeladenes PDF bleibt Byte für Byte, wie es ist; mehrere Fotos („Seite fotografieren“ mit der Handykamera,
  eine je Seite) und PDFs werden in der gewählten Reihenfolge zu einem PDF zusammengefasst, Fotos auf DIN A4
  bei 300 dpi. Mit SHA-256 und Seitenzahl; Kennzeichen „ans Protokoll hängen“ für Lieferung 3.
- **Reservierung**: Der offene Entwurf ist die Reservierung – höchstens einer je Artikel (eindeutiger Index). Andere
  sehen „in Prüfung bei …“ in Listen, am Artikel und im Durchgang. Der Prüfer verwirft seinen Entwurf selbst; eine
  liegen gebliebene Reservierung gibt der Materialwart frei (Befunde, Fotos und Anhänge gehen mit, Journal).
- **Sperre und Freiprüfung**: „instandsetzen“ sperrt und verschiebt in „Gesperrt“ der Gliederung, der
  Herkunftsordner bleibt gemerkt. Ein Prüfer kann auch ohne Prüfung sperren (Sturzbelastung, Beschädigung,
  Verlust). Von Hand kommt nichts zurück; eine Prüfung mit „einsatzbereit“ an einem gesperrten Artikel ist die
  Freiprüfung und bringt ihn in den Herkunftsordner zurück (gibt es den nicht mehr, in seine Gliederung).
- **Aussonderung**: aus der Prüfung („aussondern“ – das Prüfergebnis ist zugleich die Sperrentscheidung, eine
  vorherige Sperre braucht es dort nicht) oder durch den Materialwart, und zwar nur bei gesperrten Artikeln, mit
  Grund (Lebensdauer erreicht, Verlust, irreparabel), Datum und Bemerkung. Jede Aussonderung ist ein eigener
  Vorgang (`mat_inspection`, Art „Aussonderung“, ohne Formular, mit ausführender Person; aus einer Prüfung mit
  Verweis auf diese). Der Artikel wandert nach „Ausgesondert“, zählt nirgends mehr als Bestand und wird nicht
  mehr geprüft, gesperrt oder bearbeitet.
- **Lebenslauf**: Die Artikelansicht zeigt alle Prüfungen und Aussonderungen (neueste zuerst, mit Ergebnis,
  Prüfer und Urkundennummer, nächster Fälligkeit) über dem Journal; jede Prüfung öffnet sich mit allen Befunden,
  Fotos, Anhängen und den am Prüftag gültigen Dokumenten.
- **Prüfdurchgang** (`services/durchgang.py`, Seite `/material/durchgang/<id>`): Materialwart oder Prüfer eröffnet
  ihn für einen Ordner; alle Artikel darin und darunter – auch die aus diesem Zweig nach „Gesperrt“ gewanderten,
  ausgesonderte nicht – stehen auf einer festen Liste mit dem
  Stand offen, in Prüfung bei …, erledigt (mit Ergebnis und Prüfer) oder ausgenommen (mit Grund). Mehrere Prüfer
  arbeiten gleichzeitig, jeder mit eigener Urkundennummer. Abschließen erst, wenn alles geprüft oder ausgenommen
  und keine Prüfung des Durchgangs mehr offen ist. Ein leerer Durchgang (noch nichts geprüft) lässt sich löschen.
- **Ordnernavigation**: Links steht in Übersicht, Prüfungen, Ordner, Artikel, Prüfung, Durchgang und Suche der
  Ordnerbaum – der eigene Ordner markiert, der Weg dorthin aufgeklappt, je Ordner die Zahl der überfälligen und
  neuen Artikel. Auf- und Zuklappen merkt sich der Browser. Unter 1200 px Breite ist er eine Schublade hinter
  „☰ Ordner“ wie die Seitenleiste im Wiki. Im Bestand (dort ist der Baum der Inhalt) und im Katalog (eigener
  Kategorienbaum) steht er nicht.
- **Seite „Prüfungen“**: offene Prüfungen aller Prüfer (eigene zuerst, Materialwart kann freigeben), Prüfdurchgänge
  mit Fortschritt, „+ Prüfdurchgang“, Liste der zu prüfenden Artikel mit Knopf „Prüfen“.
- **Demodaten**: `scripts/material_demo.py --demo` legt zusätzlich DEMO-Eingangsprüfungen an (zurückdatiert, damit
  jeder Status einmal vorkommt). Ein schon vorhandener DEMO-Bestand aus Lieferung 1 bekommt sie beim nächsten
  Lauf nachgereicht; danach legt das Skript nichts mehr an.

### Migration

- Schemaversion 2, läuft beim Start von selbst und einmal: `mat_inspection` und `mat_round` werden neu aufgebaut –
  die Prüfart „Eingangsprüfung“ muss in die CHECK-Regel (SQLite ändert sie nur mit einer neuen Tabelle), und beide
  vergeben ihre Kennungen jetzt mit AUTOINCREMENT nie zweimal. Vorhandene Zeilen bleiben samt Befunden und Anhängen
  erhalten (Verfahren aus der SQLite-Dokumentation: Fremdschlüssel aus, neue Tabelle, kopieren, umbenennen,
  Indizes neu, `foreign_key_check`; alles in einer Transaktion). Neu sind `mat_inspection.basis_inspection_id` und
  `mat_item.last_inspected_on`. Geprüft: sechs gleichzeitig startende Arbeitsprozesse auf einer Datenbank aus
  Lieferung 1 mit 2 000 Artikeln und 5 000 Prüfungen – alle Zeilen da, keine Verweise gebrochen.
- Bis Lieferung 1 konnte keine Prüfung entstehen. Nach dem Start stehen deshalb **alle vorhandenen Artikel auf
  „neu“**, bis ihre Eingangsprüfung gemacht ist – auf dev auch die DEMO-Artikel (ein erneuter Demolauf legt deren
  DEMO-Prüfungen an).
- Keine Handarbeit; `docker compose up -d --build` installiert pypdf mit.

### Neue Abhängigkeiten

- `pypdf==6.19.0` (BSD-Lizenz, reines Python, vom 16.09.2026): Anhänge zu einem PDF zusammenfassen, PDFs lesen und
  Seiten zählen. Lieferung 3 braucht es ohnehin für den Prüfsummen-Stempel.

### Entscheidungen

- **Verlust** (offener Punkt aus dem Auftrag): Der Prüfer sperrt ohne Prüfung mit Grund „Verlust“
  (`lock_state = verloren`, Status „gesperrt“); danach sondert der Materialwart mit Grund „Verlust“ aus. Taucht
  der Artikel wieder auf, gibt ihn eine Freiprüfung frei.
- **Prüfart**: die erste immer Eingangsprüfung; danach wählbar periodisch, außerplanmäßig, Reparatur. Vorschlag:
  gesperrt → Reparatur; überfällig, bald fällig oder in einem offenen Durchgang → periodisch; sonst
  außerplanmäßig.
- **Fälligkeit nach der Prüfung**: nur bei „einsatzbereit“ (bei „instandsetzen“ gilt die alte nicht mehr – die
  Freiprüfung setzt sie neu). Bei gesperrten Artikeln zählt das Intervall des Herkunftsordners, in den die
  Freiprüfung sie zurückbringt.
- **Aussonderung aus der Prüfung** ergibt zwei Einträge im Lebenslauf: die Prüfung mit Ergebnis „aussondern“ und
  die Aussonderung selbst mit Verweis darauf – so hat jede Aussonderung ihren eigenen Vorgang (und in
  Lieferung 3 ihr eigenes Protokoll).
- **Prüfdurchgang**: feste Liste ab Eröffnung; ein Artikel steht höchstens in einem offenen Durchgang. Eine
  Prüfung, die ohne Angabe des Durchgangs beginnt, zählt in dem offenen Durchgang, in dem der Artikel noch zu
  prüfen ist; ein Entwurf, der schon vor der Eröffnung (oder während einer Ausnahme) begann, zählt dort ebenso.
  Wird ein Artikel eines offenen Durchgangs ausgesondert, nimmt das System ihn mit Grund heraus, und er lässt
  sich nicht wieder einbeziehen. Gesperrte Artikel stehen mit auf der Liste (auch die, die aus dem Zweig nach
  „Gesperrt“ gewandert sind): Freiprüfung oder Ausnahme mit Grund. Ausnehmen, Abschließen und Löschen dürfen
  Materialwart und Prüfer.
- **Reservierung** entsteht mit „Prüfung beginnen“, nicht schon beim Ansehen eines Artikels – wer nur nachschaut,
  soll niemanden aussperren.
- **Kürzeres Intervall** (offener Punkt aus Lieferung 1): Mit Prüfungen gilt jetzt „letzte Prüfung + neues
  Intervall“ als Grenze, ohne Prüfung weiter „heute + neues Intervall“. Liegt die Grenze schon zurück, ist der
  Artikel sofort überfällig.
- **Sperre und Aussonderung warten auf eine offene Prüfung**: Solange ein Entwurf den Artikel reserviert,
  entscheidet dessen Ergebnis; eine liegen gebliebene Reservierung gibt der Materialwart vorher frei.
- **Abgeschlossen heißt unveränderlich** – schon jetzt, auch wenn Festschreiben, Unterschrift und PDF erst mit
  Lieferung 3 kommen; eine Korrektur als neue Prüfung mit Verweis folgt dort.
- **Unterschriftsfelder** in Prüfformularen kommen mit Lieferung 3 (Signatur-Pad); bis dahin gelten sie nicht
  als Pflicht.

### Abweichungen vom Konzept, mit Begründung

- Status „neu“ und Prüfart „Eingangsprüfung“: Wunsch des Nutzers nach Lieferung 1, im Konzept nicht vorgesehen.
  Rangfolge: ausgesondert, gesperrt, Lebensdauer erreicht, neu, überfällig, bald fällig, einsatzbereit.
- `mat_item.last_inspected_on` (Tag der letzten abgeschlossenen Prüfung): Daraus folgt „neu“. Der Status selbst
  bleibt abgeleitet, wie im Auftrag verlangt.
- Beim Anlegen eines Artikels fragt das Formular nicht mehr nach der nächsten Prüfung – die setzt die
  Eingangsprüfung. Intern bleibt der Vorschlag gespeichert (die Regeln aus Lieferung 1 gelten unverändert).
- Ein Anhang ist immer ein PDF, auch ein einzelnes Foto: einheitlich für Prüfsumme, Anzeige und das Anfügen an
  das Protokoll in Lieferung 3. Scans laufen deshalb nicht durch `store_upload` (das legt Web- und
  Vorschaubilder an, die ein PDF nicht braucht), sondern direkt durch Pillow – mit derselben EXIF-Drehung und
  HEIC-Unterstützung. Mangelfotos je Prüfpunkt laufen wie Produktbilder durch die vorhandene Pipeline.
- Altbestand: Auch übernommene Artikel mit Papierkarte stehen auf „neu“, bis ein Prüfer die Eingangsprüfung im
  System gemacht hat; die Papierkarte gehört als Anhang dazu.

### Review vor der Auslieferung

Drei unabhängige Durchsichten: Fachlogik und Sicherheit (mit Gegenproben, darunter 1 500 unsinnige Eingaben an
alle neuen Routen und 33 absichtlich kaputte PDFs – kein 500), Oberfläche (im Browser nachgestellt, auch bei
390 px) und Abgleich mit dem Auftrag. Keiner der Befunde war „hoch“; alle sind behoben und in
`test_review_lieferung2` und `test_review_lieferung2_robust` bzw. im Browser nachgeprüft.

| # | Befund | Behebung |
| --- | --- | --- |
| 1 | Ein Entwurf, der vor der Eröffnung eines Durchgangs begann, zählte dort nie | Eröffnen (und Wiedereinbeziehen) übernimmt offene Entwürfe |
| 2 | Zahlpunkte übernahmen einen Soll-Hinweis („max. 22 mm“) als Messwert – Abschluss ohne Messung möglich | nur eine reine Zahl wird vorbelegt, sonst Platzhalter |
| 3 | Durchgang für einen Unterordner vergaß dessen gesperrte Artikel | Herkunftsordner im Zweig zählt |
| 4 | Ein ausgesonderter Artikel ließ sich in den Durchgang zurückholen und blockierte den Abschluss | abgewiesen, Knopf weg |
| 5 | Verschieben prüfte den Sperrzustand vor der Schreibsperre – eine gleichzeitige Sperre ließ sich aushebeln | Prüfen und Schreiben unter einer Sperre, nur freie Artikel |
| 6 | Ein vor einer Prüfung geöffneter Bearbeiten-Dialog überschrieb deren Fälligkeit | Fingerabdruck des geladenen Stands, sonst 409; Fälligkeit nie vor der letzten Prüfung |
| 7 | Kennungen verworfener Entwürfe und gelöschter Durchgänge kamen wieder – das Journal hing am falschen Vorgang | AUTOINCREMENT; das Journal zeigt je Objekt nur, was seit seiner letzten Löschung geschah |
| 8 | Anhänge: Seitengrenze erst nach dem Zusammenfügen, sehr große PNGs teuer | Seiten vorher zählen, 50 MP, JPEG verkleinert dekodieren, 30 Dateien |
| 9 | Ein einzelnes PDF, das sich nicht anfügen lässt, wurde angenommen | Probe-Anfügen auch für ein einzelnes PDF |
| 10 | Fotodatei blieb liegen, wenn die Schreibsperre nicht kam | bei jedem Fehler aufgeräumt |
| 11 | Formular speichern/löschen und Artikel/Produkt löschen prüften außerhalb der Sperre | unter `BEGIN IMMEDIATE` |
| 12 | Eine Serverantwort zeichnete die Karte neu, während darin getippt wurde – Tastatur zu, Fokus weg | Text, offene Bemerkung und Fokus bleiben; Ungespeichertes speichert der Blur |
| 13 | Während des Hochladens fotografierte Scan-Seiten gingen verloren oder kamen doppelt | nur die hochgeladenen werden abgezogen, Knopf bis zum Ende gesperrt |
| 14 | Nach einer Ablehnung blieb in fünf Dialogen der Knopf gesperrt (`ev.currentTarget` nach `await`) | Knopf vorher festgehalten (auch im Fotodialog aus Lieferung 1) |
| 15 | Kamera- und Dateiknöpfe nicht per Tastatur erreichbar | Eingabe nur optisch versteckt, Fokusrahmen am Knopf |
| 16 | Geschlossene Schublade blieb in der Tab-Reihenfolge; gemerktes Zuklappen versteckte den eigenen Ordner | `inert`, Escape gibt den Fokus zurück; der Weg zum Ordner ist immer offen |
| 17 | Kleinigkeiten: Grund bei „einsatzbereit“ gespeichert, Leiste deckte Felder bei offener Tastatur, Liste nach Freigabe veraltet, Journal mit Kennungen statt Namen | behoben |

### Zu prüfen

- **Docker-Build** mit `pypdf==6.19.0` (reines Python-Rad): hier ohne Docker nicht gebaut. Die Tests laufen mit
  genau dieser Version.
- **Altbestand**: Die Fälligkeit einer Papierkarte lässt sich nicht übernehmen – jeder übernommene Artikel steht
  auf „neu“, bis ein Prüfer im System die Eingangsprüfung gemacht hat (die Papierkarte gehört als Anhang dazu). Ohne
  aktives Prüfformular lässt sich nicht prüfen; vor dem Pilotbetrieb muss der Katalog aus Phase 0 also stehen.
- **Prüftag** ist der Tag des Abschlusses, nicht des Beginns; Prüfername und Urkundennummer werden beim Abschluss
  übernommen.
- **Vorschläge für die Prüfart** und die Gründe für Sperre (Sturzbelastung, Beschädigung, Verlust) und
  Aussonderung (Lebensdauer erreicht, Verlust, irreparabel) bitte fachlich bestätigen.
- **Freigabe einer Reservierung** löscht den fremden Entwurf samt Befunden, Fotos und Anhängen (im Journal
  vermerkt). Alternative wäre, ihn einem anderen Prüfer zu übergeben – das sieht der Auftrag nicht vor.
- **Lebensende und Fälligkeit**: Die nächste Prüfung wird nicht auf das Lebensende begrenzt; ab dem Lebensende
  zeigt der Status ohnehin „Lebensdauer erreicht“.
- **Kennungen**: Prüfungen und Durchgänge vergeben jede Kennung nur einmal. Artikel, Ordner, Produkte, Kategorien
  und Formulare können nach dem Löschen eine Kennung wiederbekommen; ihr Journal zeigt dann nur, was seit der
  letzten Löschung unter ihr geschah.
- **Unterschriftsfelder** in Prüfformularen sind bis Lieferung 3 nicht Pflicht.
- **Ordnerleiste**: Schublade schon unter 1200 px (das Wiki erst unter 800 px), weil die Listen des Moduls neben
  einer festen Leiste sonst zu schmal würden.
- **Oberfläche** in Chromium geprüft (1280 px und 390 px, alle neuen Ansichten, Prüfung mit Mangel, Foto, Scan,
  Abschluss, Durchgang); nicht in Safari/iOS – dort besonders Kamera-Knopf (`capture`), Datumsfeld, feste Leiste
  und `:has()` ansehen.
- **Nach dem Deploy auf dev** stehen alle vorhandenen Artikel auf „neu“. Wer die Demo-Zustände sehen will, lässt
  den Demolauf noch einmal laufen (Befehl wie bisher) – er legt die DEMO-Prüfungen einmal an.

### Nachbesserungen nach der Auslieferung (Durchsicht vom 17.10.2026)

- **Prüfpunkte im Formular-Editor** brechen um und wachsen mit dem Text; die Spalte ist breiter, ein Prüfpunkt darf
  bis 1000 Zeichen lang sein (vorher 300) – auch im Katalogimport (`punkte[].text`).
- **Katalog mit der Leiste links**: Der Kategorienbaum steht wie der Ordnerbaum in der Leiste (Katalog, Produkt,
  Formular; markiert, aufklappbar, Produktzahl samt Unterkategorien, am Telefon „☰ Kategorien“). Die gewählte
  Kategorie steht über der Produktliste mit ihren Angaben und Knöpfen.
- **Listen**: Produktbilder 25 % größer (40 px), der Hersteller in eigener Spalte, Spalten sortierbar (Klick auf
  den Kopf, noch einmal: absteigend). Katalog, Ordner, „Prüfungen“ und Suche sortieren auf dem Server – sie kommen
  seitenweise, eine Sortierung im Browser stimmte nur auf der einen Seite; der Prüfdurchgang sortiert im Browser.
  „Nächste Prüfung“ stellt neue Artikel (Eingangsprüfung) nach vorn, „Status“ sortiert nach Dringlichkeit, das
  Intervall im Katalog auch geerbt von der Oberkategorie. Der Katalog lädt endlos nach (je 50 Produkte, sobald das
  Ende der Liste ins Bild rückt) statt in Seiten; seine Suchzeile bleibt dabei unter der Kopfleiste stehen.
- **Dokumente umbenennen**: Den Namen eines hochgeladenen Dokuments ändert der Katalogpfleger nachträglich – jeder
  Version, mit Journaleintrag. Datei, Version und Prüfsumme bleiben; alte Prüfungen zeigen den Namen vom Prüftag.
- **Kauf und Erstgebrauch als Monat, Datumsfelder auf Deutsch**: In „Artikel anlegen“ und „Artikel bearbeiten“ sind
  Herstellung, Kauf und Erstgebrauch Monatsfelder (MM/JJJJ), Lebensende und nächste Prüfung Tagesfelder (TT.MM.JJJJ) –
  deutsche Textfelder statt der Datumsfelder des Browsers, die das Format seiner Sprache zeigen (in einem englischen
  Browser mm/dd/yyyy). Die Trenner setzt das Feld beim Tippen; Ungültiges wird rot markiert und nicht gespeichert.
  Der Server nimmt Kauf und Erstgebrauch jetzt wie die Herstellung auch als Monat an: Die erste Fälligkeit rechnet
  ab dem Monatsersten, der laufende Monat liegt nicht in der Zukunft, der Monat der Herstellung nicht vor ihr. Ein
  vorhandenes Tagesdatum bleibt beim Bearbeiten erhalten, solange der Monat gleich bleibt. Die übrigen Datumsfelder
  (Gültig ab, Aussonderung, nächste Prüfung im Prüfformular, Datums-Prüfpunkte) nutzen weiter das des Browsers.
- **Produkt als Variante kopieren**: „Als Variante kopieren“ in der Produktansicht öffnet den Produktdialog mit den
  Stammdaten des Produkts (Kategorie, Hersteller, Modell, Norm, Materialart, Intervall, Lebensdauer, Beschreibung);
  eine eigene, neue Artikelnummer ist Pflicht, alles andere lässt sich anpassen. Die aktuellen Dokumente – je
  Dokument die neueste, nicht zurückgezogene Version – kommen nach Wahl mit (Häkchen je Dokument); ihre Dateien
  werden kopiert, damit das Löschen des einen Produkts die Dokumente des anderen nicht mitnimmt. Das Produktbild
  kommt nie mit, ein spezifisches Prüfformular auch nicht. Das Journal der Variante nennt ihr Vorbild.
- **Artikelnummern eindeutig**: Jede Artikelnummer gibt es im Katalog nur einmal – Schreibweise egal wie bei der
  Dublette („KR13B-R-GI“ = „kr13b r gi“), leer oder „-“ zählt nicht. Geprüft beim Anlegen, beim Ändern der Nummer,
  im Katalogimport (Fehlerzeile, nichts gespeichert) und bei Meldungen; Produkt- und Meldedialog sagen schon beim
  Tippen, welchem Produkt die Nummer gehört. Eine Dopplung aus der Zeit davor bleibt, bis jemand eine der Nummern
  ändert – andere Änderungen am Produkt blockiert sie nicht.
- **Mehrere Dokumente auf einmal**: „+ Dokument“ (am Produkt und an der Kategorie) nimmt mehrere Dateien – per
  Mehrfachauswahl oder hineingezogen – und Links. Je Eintrag Titel (aus dem Dateinamen vorbelegt), Art als
  Auswahlliste (aus dem Dateinamen vorgeschlagen, wo es eindeutig ist, sonst Pflicht) und Versionsstand; „Gültig ab“
  gilt für alle. Jede Datei geht einzeln an den Server; was scheitert, bleibt mit Grund im Dialog stehen. Eine neue
  Version eines Dokuments bleibt ein eigener Dialog für genau eine Datei.
- **Dokumente an Kategorien** (Schemaversion 3): Pflegehinweise, allgemeine Anleitungen oder Links lassen sich an
  eine Kategorie hängen und gelten dann für alle Produkte darin und in den Unterkategorien – an Produkt, Artikel
  und Prüfung bei den Herstellerdokumenten unter der Zwischenzeile „Dokumente für die Kategorie …“ (je Kategorie
  eine, geerbte in der Reihenfolge des Pfads); eine Prüfung hält die am Prüftag gültigen fest. Versionen,
  Zurückziehen und Umbenennen wie am Produkt; neue Art „Pflegehinweis“. Dafür baut der Start
  `mat_product_document` einmal neu auf (ein Dokument hängt jetzt an einem Produkt ODER an einer Kategorie; alle
  Zeilen bleiben, Kennungen kommen nie wieder). Eine leere Kategorie lässt sich samt ihren Dokumenten löschen.
- **Fehlende Produkte melden** (Schemaversion 4, neue Tabelle `mat_product_request`): Wer Artikel anlegt und das
  Produkt nicht im Katalog findet, meldet es dort („Fehlendes Produkt melden“, vorbelegt aus der Suche): Hersteller,
  Modell, Artikelnummer, Norm, Kategorie (Vorschlag), bis zu fünf Links (nur http/https) und bis zu drei Fotos
  (Etikett, Typenschild) sowie eine Bemerkung; der gewählte Ordner geht mit. Steht das Produkt schon im Katalog
  (gleiche Dublette), gibt es nichts zu melden. Die Produktkatalogpfleger bekommen eine Mail (gibt es keinen: die
  Verwaltung) und arbeiten die Meldungen unter Katalog → „Meldungen“ ab: **Produkt anlegen** öffnet den
  Produktdialog mit den Angaben der Meldung (Anlegen und Erledigen in einem Zug), **Vorhandenes zuordnen**, wenn es
  anders geschrieben schon da ist – kommt es inzwischen mit gleicher Dublette in den Katalog, zeigt die Meldung es
  als Treffer zum Zuordnen mit einem Klick –, **Ablehnen** nur mit Begründung. Der Melder bekommt Bescheid per Mail,
  nach dem Einpflegen mit einem Link, der „Artikel anlegen“ mit Produkt und Ordner öffnet; seine Meldungen sieht er
  auch unter dem Formular „Artikel anlegen“ (ein Klick wählt das eingepflegte Produkt). Offene Meldungen zählt eine
  Blase oben rechts am Knopf „Meldungen“ im Katalog, dazu ein Hinweis auf der Übersicht. Wer eine Meldung gemacht
  hat, kann sie löschen – offen (sie verschwindet bei den Katalogpflegern) oder erledigt; ein Produkt aus ihr bleibt,
  ihre Fotos gehen mit, das Journal vermerkt die Löschung. Sonst bleiben Meldungen stehen und erscheinen im Journal
  des Produkts, das aus ihnen entstand.
- **Prüfdurchgang abbrechen** (Schemaversion 5, Spalte `mat_round.aborted`): Neben „Durchgang abschließen“ steht
  „Durchgang abbrechen“ (Materialwart oder Prüfer). Offene Prüfungen darin laufen als einzelne Prüfungen weiter.
  Wurde darin noch nichts abgeschlossen, verschwindet der Durchgang ganz (das ersetzt den Knopf „Löschen“); sonst
  endet er als „abgebrochen“: Geprüftes und Ausgenommenes bleibt ihm zugeordnet, jeder andere Artikel steht darin
  als „nicht geprüft“. In der Ansicht „Prüfungen“ stehen die Prüfdurchgänge jetzt ganz oben.
- **Kleinere Anpassungen der Oberfläche**: Materialart „Metall“ statt „Metall/Hardware“ (nur die Anzeige, der
  Schlüssel `metall_hardware` bleibt). Im Prüfformular erst die Bemerkung, dann die Anhänge; der Hinweis zur
  Bemerkung sagt, dass Mängel, die der Prüfer während der Prüfung selbst behebt, dort mit der Maßnahme zu
  dokumentieren sind. Am Rechner (Maus, ab 700 px Breite) stehen die Prüfpunkte dichter: niedrigere Umschalter,
  Foto und „+ Bemerkung“ in derselben Zeile, auch die Leiste unten ist niedriger – eine Ja/Nein-Karte ist knapp
  halb so hoch; am Telefon bleibt alles groß. Produktansicht: Artikelnummer, Materialart und Norm stehen in den
  Stammdaten, „+ Artikel dieses Produkts“ in eigener Zeile über den Knöpfen des Katalogpflegers (Bearbeiten und
  Löschen als umrandete Knöpfe); das Produktbild ändert oder entfernt man im Dialog „Bearbeiten“, beim Anlegen lässt
  es sich gleich mitgeben.
  Kategorieansicht: Wer den Katalog pflegt, erreicht das generische Formular über den Knopf; den Verweis in der
  Angabenzeile sehen nur noch Lesende, die keinen Knopf haben.

## Lieferung 3 – Nachweis (17.10.2026)

Unterschrift im Profil, Festschreiben, PDF-Einzel-, Sammel- und Aussonderungsprotokoll, aufgedruckte Prüfsumme und
Prüfseite. Lieferung 2 wurde am 17.10.2026 mit „Erstelle Lieferung 3“ freigegeben.

### Neu

- **Unterschrift im Profil** (`services/unterschrift.py`, Signatur-Pad `signature_pad.js`): Wer im Modul Material
  arbeitet, zeichnet seine Unterschrift einmal unter „Profil → Unterschrift“ (Finger, Stift oder Maus) und kann sie
  ändern oder entfernen. Der Server nimmt nur ein PNG vom Pad an, verlangt sichtbare Striche, schneidet den leeren
  Rand ab, verkleinert bei Bedarf und speichert ein frisch geschriebenes Bild – nie die Bytes des Browsers. Jede
  Änderung steht im Journal (Konto, ohne das Bild). Fehlt sie beim Festschreiben, öffnet das Prüfformular das Pad
  direkt im Ablauf.
- **Festschreiben** (`services/pruefung.py`, `services/protokoll.py`): „Abschließen“ heißt jetzt „Festschreiben“
  und braucht Urkundennummer und Unterschrift. In derselben Schreibtransaktion setzt es Ergebnis, Sperrzustand und
  Fälligkeit wie bisher, übernimmt eine Kopie der Unterschrift, die Anmeldung (E-Mail des Kontos) und den Zeitpunkt
  und erzeugt das Prüfprotokoll. Danach ist die Prüfung unveränderlich – die Oberfläche bietet nichts mehr an, die
  Schnittstelle antwortet mit 409, und Datenbank-Trigger weisen jede Änderung an Prüfung, Befunden und Anhängen ab,
  auch an der Anwendung vorbei.
- **Prüfprotokoll** nach dem Muster der EN-365-Karte (`templates/material/pdf/`): Gliederung und Ordner,
  Artikel-Stammdaten mit Serien- und Inventarnummer, Herstell-, Kauf- und Erstgebrauchsdatum, Lebensende (textil),
  Produktbild, QR-Code zum Online-Lebenslauf; Prüfart, Prüftag, Prüfer mit Urkundennummer und Anmeldung, Formular
  mit Version, Durchgang; alle Prüfpunkte mit Soll, Befund, Wert und Bemerkung (Mängel und kritische Punkte
  markiert), Fotos der Mängel, Ergebnis mit nächster Fälligkeit und Folge (gesperrt, ausgesondert), Bemerkung, die am
  Prüftag gültigen Herstellerdokumente, das Verzeichnis der Anhänge mit SHA-256 und Seitenzahl, die Unterschrift
  mit Name, Urkundennummer, Anmeldung und Zeitpunkt, Protokoll-ID. Anhänge mit „hinten ans Protokoll hängen“ folgen
  als Seiten im selben PDF – entschärft: Skripte, ausführende Aktionen und Formular-Wörterbücher eines Anhangs
  kommen nicht mit, Verweise und ausgefüllte Felder (ihr Erscheinungsbild) bleiben sichtbar.
- **Aussonderungsprotokoll**: Jede Aussonderung – aus der Prüfung („aussondern“) oder durch den Materialwart – wird
  mit eigenem Protokoll festgeschrieben: Artikel, Grund, Datum, Bemerkung, Sperrvermerk, ausführende Person mit
  Rolle, Urkundennummer (falls Prüfer), Anmeldung und Unterschrift, Verweis auf die auslösende Prüfung und die letzte
  Prüfung davor. Auch der Materialwart braucht dafür seine Unterschrift.
- **Sammelprotokoll** je Prüfdurchgang: entsteht beim Abschließen – und beim Abbrechen, wenn darin schon geprüft
  wurde – in derselben Transaktion: Durchgang, Ordner, eröffnet und abgeschlossen (von, wann), Ergebnisübersicht,
  alle beteiligten Prüfer mit Urkundennummer, Zahl der Prüfungen und Unterschrift, alle Artikel mit Ergebnis,
  Prüftag, Prüfer und Protokoll-ID, ausgenommene mit Grund, nicht geprüfte (Abbruch) als solche, dazu das
  Verzeichnis der Einzelprotokolle mit der SHA-256 ihrer Datei – so belegt es auch, welche Einzelprotokolle zur
  Jahresprüfung gehören. Danach ist der Durchgang unveränderlich (auch per Trigger).
- **Prüfsumme** (`services/stempel.py`): WeasyPrint erzeugt das Protokoll vollständig, angefügte Anhänge kommen
  per inkrementellem Update dazu; über diese N Bytes geht SHA-256. Ein zweites inkrementelles Update legt den Stempel
  „SHA-256 (erste N Bytes): <hex>“ samt Protokoll-ID, Befehl zum Nachrechnen und Adresse der Prüfseite in den Fuß
  jeder Seite – auch auf angefügte Seiten (gedrehte und andere Formate eingeschlossen): Die bekommen dafür unten einen
  eigenen Streifen von 14 mm (und mindestens die Breite von DIN A4), damit der Stempel nichts vom Anhang verdeckt und
  auf kleinen Fotoseiten lesbar bleibt; nur die Seitengrenzen ändern sich, im Nachtrag. Die ersten N Bytes bleiben
  Byte für Byte: `head -c N datei.pdf | sha256sum` ergibt die aufgedruckte Summe. In der Datenbank stehen
  `pdf_sha256`, `pdf_hashed_bytes` und `file_sha256` (ganze Datei mit Stempel).
- **Ablage**: `DATA_DIR/pdf/<jahr>/<protokoll-id>.pdf`, exklusiv angelegt, auf Platte geschrieben (fsync),
  schreibgeschützt. Ausgeliefert wird nur an Angemeldete mit Leserecht und nur, solange die Datei ihre Prüfsumme
  hat (`/material/pruefung/<id>/pdf`, `/material/durchgang/<id>/sammelprotokoll`, Dateiname
  `<Protokoll-ID>_<Inventarnummer>.pdf`). Scheitert der Vorgang nach dem Schreiben, wird die Datei wieder gelöscht.
- **Prüfseite** `/material/pruefen` (ohne Anmeldung): PDF hochladen, die Antwort ist „unverändert“, „verändert“ oder
  „kein Protokoll erkannt“ samt Protokoll-ID – keine Personendaten, nichts wird gespeichert. Eine veränderte Datei
  erkennt sie an einer Kennung im Stempel-Nachtrag wieder (nur wenn N und Prüfsumme darin zum Protokoll passen) und
  sagt, ob der Protokollinhalt (die ersten N Bytes) noch stimmt. Den Inhalt einer hochgeladenen Datei zerlegt sie
  nicht. Angemeldete mit Zugang bekommen zusätzlich den Weg zum Vorgang. Gebremst auf 20 Prüfungen je
  Adresse in 15 Minuten, höchstens 200 MB je Datei.
- **Berichtigung**: Eine festgeschriebene Prüfung korrigiert nur, wer sie gemacht hat – „Berichtigen“ mit Grund legt
  einen neuen Entwurf an: alle Befunde, Fotos (kopiert) und Anhänge (kopiert) des Originals, derselbe Prüftag,
  dieselbe Prüfart, Verweis auf das Original. Festgeschrieben wird sie wie jede Prüfung (ihr Protokoll nennt das
  Original und den Grund) und wirkt dann am Artikel; das Original bleibt Byte für Byte erhalten und zeigt
  „berichtigt durch …“. Berichtigen lässt sich nur die letzte Prüfung eines Artikels, keine Aussonderung und jede
  Prüfung höchstens einmal (wer danach weiter korrigiert, berichtigt die Berichtigung).
- **Unterschriftsfelder** in Prüfformularen: auf dem Signatur-Pad zu füllen (Name des Feldes als Titel), Pflicht wie
  andere Prüfpunkte, „nicht zutreffend“ möglich; das Bild steht im Protokoll beim Prüfpunkt.
- **Oberfläche**: Protokollabschnitt in jeder abgeschlossenen Prüfung (Protokoll-ID, PDF, festgeschrieben von/am,
  Prüfsumme, Unterschrift), „PDF“ im Lebenslauf, Knopf „Sammelprotokoll“ im Durchgang, Berichtigen mit Hinweisen am
  Original und an der Berichtigung, Unterschrift im Aussonderungsdialog, Verweis auf die Prüfseite.
- **Demodaten**: Die DEMO-Prüfungen werden mit einer DEMO-Unterschrift festgeschrieben; ein DEMO-Bestand aus
  Lieferung 2 bekommt seine Protokolle beim nächsten Lauf nachgereicht (nur DEMO-Prüfungen, mit DEMO-Hinweis).

### Behoben (gemeldet während Lieferung 3)

- **Produktbilder mit durchsichtigem Hintergrund** (freigestellte PNGs, auch WebP mit Alphakanal) standen in Listen,
  Produktansicht und Protokoll auf Schwarz: Beim Umwandeln nach JPEG ging der Alphakanal verloren. Durchsichtige
  Flächen werden jetzt weiß – für alle Bilder, die durch die gemeinsame Bildverarbeitung gehen (Produkt-, Ordner-,
  Mangel- und Meldungsfotos, Alben, Prüfungsbereich). Schon hochgeladene Bilder des Moduls Material repariert der
  Start einmal: Web- und Vorschaufassung entstehen aus dem erhaltenen Original neu. Alben und Prüfungsbereich werden
  nicht nachträglich repariert (dort sind freigestellte Bilder unüblich) – ein betroffenes Bild dort einfach neu
  hochladen.

### Migration

- Schemaversion 6, läuft beim Start von selbst: neue Spalten `mat_inspection.locked_login`,
  `mat_inspection.correction_reason`, `mat_inspection_result.signature_png`, `mat_round.locked_at`; ein eindeutiger
  Index (höchstens eine Berichtigung je Prüfung), Indizes für die Prüfseite und 22 Trigger für die
  Unveränderlichkeit (auch gegen `INSERT OR REPLACE` über Kennung, Protokoll-ID oder Berichtigungsverweis, gegen
  Nachschieben in einen abgeschlossenen Durchgang und gegen das Umschreiben der Prüferkennung – nur das Leeren beim
  Löschen eines Kontos bleibt erlaubt). Die Verbindungen der App schalten dazu `recursive_triggers` ein, damit
  Lösch-Trigger auch bei einem `REPLACE` greifen. Keine Tabelle wird umgebaut; alle Zeilen bleiben.
- Prüfungen, die vor Lieferung 3 abgeschlossen wurden, behalten ihren Inhalt, bekommen aber kein Protokoll (ohne
  Unterschrift ließe sich keins festschreiben); sie sind ab jetzt auch in der Datenbank unveränderlich und lassen
  sich wie jede abgeschlossene Prüfung berichtigen. Die Produktion hat noch keine Daten des Moduls.
- Neues Verzeichnis `/data/pdf` – es gehört in die Sicherung (der Cron-Eintrag aus der README kopiert `data/` ohnehin
  ganz). Beim Zurückspielen werden Protokolle nur ergänzt, nie gelöscht (Befehl in der README geändert): Was nach der
  Sicherung festgeschrieben wurde, legt der Start nach `pdf/verwaist/`, und seine Protokoll-ID wird nicht noch
  einmal vergeben (Zähler gehoben bzw. Folgenummer).
- `docker compose up -d --build` installiert Pango, HarfBuzz und DejaVu im Image und die neuen Python-Pakete; keine
  Handarbeit.

### Neue Abhängigkeiten

| Paket | Version | Lizenz | Wofür |
| --- | --- | --- | --- |
| WeasyPrint | 70.0 (08.09.2026) | BSD-3-Clause | Protokolle als PDF/A-3b aus Jinja-Vorlagen |
| pydyf | 0.12.1 | BSD-3-Clause | schreibt das PDF für WeasyPrint – festgehalten |
| segno | 1.6.6 | BSD-3-Clause | QR-Code zum Lebenslauf im Protokoll |
| tzdata | 2026.4 | Apache-2.0 | deutsche Ortszeit im Protokoll (das schlanke Image hat keine Zeitzonen) |
| cryptography | 50.0.2 (30.09.2026) | Apache-2.0 oder BSD-3-Clause | pypdf liest damit mit AES verschlüsselte Anhänge (leeres Benutzerkennwort, bei Herstellern üblich) – ohne nur RC4; das betraf schon den Upload aus Lieferung 2 |
| signature_pad | 5.1.4 (JavaScript) | MIT | Unterschrift zeichnen; wie die übrigen Bibliotheken geladen und gegen `vendor.sha256` geprüft |
| Debian: libpango-1.0-0, libpangoft2-1.0-0, libharfbuzz-subset0, fonts-dejavu-core | aus dem Basis-Image | LGPL / MIT / Bitstream Vera | für WeasyPrint; DejaVu setzt Prüfsummen und Zeichen, die DLRG Univers nicht hat |

WeasyPrint zieht außerdem tinycss2, cssselect2, tinyhtml5, Pyphen, fontTools (mit brotli/zopfli für WOFF2) und
cffi nach (alle BSD/MIT). Das Image wird dadurch größer (geschätzt 60–80 MB); im Speicher kostet WeasyPrint je
Arbeitsprozess beim ersten Protokoll etwa 50–100 MB.

### Entscheidungen

- **Protokoll-ID** `P-<jahr>-<nr>` (Prüfung), `A-…` (Aussonderung), `S-…` (Sammelprotokoll): Die Nummer ist die
  Kennung des Vorgangs (nie zweimal vergeben), das Jahr das des Festschreibens. Lücken sind verworfene Entwürfe.
  Kein eigener Zähler – so hängt die ID nicht an einer zweiten Transaktion. Liegt unter einer ID schon eine Datei
  (nach dem Zurückspielen einer Sicherung kann ein Entwurf wieder offen sein, dessen Protokoll schon ausgehändigt
  wurde), bekommt das neue Protokoll eine Folgenummer (`P-2026-000007-2`); eine ID bezeichnet nie zwei Dateien.
- **Festschreiben in einem Schritt mit dem Abschluss** und in derselben Schreibtransaktion wie das Rendern: Was im
  PDF steht, ist genau das, was die Datenbank festhält. Das hält die Schreibsperre für die Dauer des Renderns
  (gemessen siehe unten); andere Prüfer warten so lange mit dem Speichern, der Lesebetrieb nicht.
- **Stempel als ein gemeinsames Form-XObject**, auf das jede Seite verweist; die Seiteninhalte bleiben unangetastet
  (in `q … Q` gerahmt). Zusammenführen mit `merge_page` hätte die von WeasyPrint geteilte Farbraumtabelle bei jeder
  Seite um eine Kopie erweitert (5 KB je Seite, quadratisch wachsend). Jetzt: rund 450 Byte je Seite.
- **Die Warnung von qpdf** aus dem Prototyp kam von pypdf: Sein inkrementelles Update führt den Querverweis-Strom
  nicht in dessen eigenem Index (und schreibt nach „obj“ keinen Zeilenumbruch, was PDF/A verletzt). `stempel.py`
  schreibt den Querverweis-Strom deshalb selbst (Unterklasse von `PdfWriter`, pypdf ist festgehalten); qpdf meldet
  danach nichts mehr, veraPDF bestätigt PDF/A-3b auch nach dem Stempel.
- **PDF/A-3b** (WeasyPrint `pdf_variant`): erlaubt Transparenz (Unterschrift mit Alphakanal) und ist für die
  Archivierung gängig. Schrift im Protokoll ist DLRG Univers (eingebettet; die Schrift erlaubt Einbettung für Ansicht
  und Druck), Prüfsummen in DejaVu Sans Mono.
- **Kennung im Stempel-Nachtrag**: ein PDF-Kommentar `%Stroemis-Protokoll <ID> N=… SHA-256=…` – unkomprimiert lesbar,
  auch wenn eine veränderte Datei sich nicht mehr öffnen lässt. Daran ordnet die Prüfseite eine veränderte Kopie
  ihrem Protokoll zu.
- **Berichtigung** (offener Punkt aus Lieferung 2): nur der Prüfer selbst (wer anders prüft, macht eine neue
  Prüfung), nur die letzte Prüfung eines Artikels (sonst wirkte die Korrektur einer alten Prüfung am heutigen Stand
  vorbei), nie eine Aussonderung (unumkehrbar). Prüftag und Prüfart bleiben die des Originals, die Fälligkeit
  rechnet ab diesem Prüftag. Liegt das Original in einem noch offenen Durchgang, zählt die Berichtigung dort.
- **Aussonderung durch den Materialwart** braucht seine Unterschrift – jedes festgeschriebene Protokoll trägt eine.
- **Sammelprotokoll ohne eigene Unterschrift dessen, der abschließt**: Es fasst unterschriebene Einzelprotokolle
  zusammen; die Unterschriften der Prüfer stehen darin, der Abschließende mit Name und Zeitpunkt.
- **E-Mail-Versand von Protokollen** gibt es nicht – laut Auftrag höchstens eine Option; das PDF lädt jeder mit
  Leserecht.
- **Lebenslauf als PDF** kommt mit Lieferung 4 (Export), wie im Auftrag unter den Smoke-Tests dort genannt.
- **Zeitstempel** stehen in deutscher Ortszeit (Europe/Berlin) im Protokoll, in der Datenbank weiter in UTC.

### Abweichungen vom Konzept, mit Begründung

- `mat_inspection.locked_login`: Die „Login-Identität“ aus dem Auftrag ist die E-Mail-Adresse des Kontos zum
  Zeitpunkt des Festschreibens – als Kopie, wie Name und Urkundennummer.
- `mat_inspection.correction_reason`: Grund der Berichtigung (der Verweis selbst steht seit Lieferung 1 in
  `corrects_inspection_id`).
- `mat_inspection_result.signature_png`: das gezeichnete Unterschriftsfeld eines Formulars – kein Foto, keine Datei.
- `mat_round.locked_at`: Zeitpunkt des Sammelprotokolls (`closed_on` ist nur ein Tag).
- Die Unveränderlichkeit sichern zusätzlich Datenbank-Trigger (verlangt war „Schreibschutz in der
  Service-Schicht“) – sie fangen ab, was an der Service-Schicht vorbeiginge. Ausgenommen sind die Nutzerkennungen,
  die SQLite beim Löschen eines Kontos selbst auf NULL setzt.

### Messwerte

Gemessen in der Entwicklungsumgebung (Intel i5-6500T): Prüfprotokoll mit drei Fotos 0,7 s (erstes Protokoll eines
Arbeitsprozesses 1,9 s – Import von WeasyPrint, Silbentrennung, Schriften), Aussonderungsprotokoll 0,3 s, Stempel
0,13 s, Sammelprotokoll mit 300 Artikeln 4,7 s, mit 500 Artikeln 8 s. So lange hält der Vorgang die Schreibsperre der
Datenbank; andere schreiben in dieser Zeit nicht, lesen aber weiter. Der Stempel macht eine Datei um rund 450 Byte
je Seite größer.

### Review vor der Auslieferung

Zuerst haben unabhängige Agenten die PDF-Vorlagen (Prüfen und Nachbessern, u. a. veraPDF mit Grenzfällen) und die
Oberfläche (im Browser bei 1280 und 390 px, Maus und Touch) geprüft. Danach eine Durchsicht in sechs Blickwinkeln –
Sicherheit, Datenintegrität, Abgleich mit dem Auftrag, PDF-Technik, Oberfläche, Betrieb – mit Gegenprüfung jedes
Befunds durch einen zweiten Agenten. Alle bestätigten Befunde sind behoben; die Gegenprüfung hat die Korrekturen
nachgestellt. Abgesichert in `test_review_lieferung3` (und `test_durchsichtige_bilder`):

| # | Befund | Schwere | Behebung |
| --- | --- | --- | --- |
| 1 | Prüfseite zerlegte jede hochgeladene Datei mit pypdf – eine präparierte 50-KB-Datei band ohne Anmeldung 40 s und 770 MB | hoch | Die Prüfseite liest nur die Kennung am Dateiende und rechnet Prüfsummen; Rückgriff über höchstens zwölf %%EOF-Grenzen in einem Durchgang |
| 2 | Eine Berichtigung mit altem Prüftag konnte eine spätere Sperre (Sturz, Verlust) als Freiprüfung aufheben | hoch | Berichtigen abgelehnt, wenn der Artikel nach der Prüfung gesperrt wurde |
| 3 | JavaScript und ausführende Aktionen angehängter PDFs kamen ins Protokoll | mittel | Anhänge werden vor dem Anfügen entschärft; Verweise und ausgefüllte Felder bleiben |
| 4 | Der Stempel verdeckte den unteren Rand angefügter Scan-Seiten und wurde auf kleinen Seiten unlesbar | mittel | eigener 14-mm-Streifen unter angefügten Seiten, mindestens A4-Breite |
| 5 | Ein angehängtes, schon gestempeltes Protokoll verlor seinen eigenen Stempel | mittel | Stempel-XObject mit eigenem Namen je Protokoll |
| 6 | AES-verschlüsselte Anhänge scheiterten im Image (`cryptography` fehlte; in der Testumgebung kam es aus dem System) | mittel | `cryptography==50.0.2`; Tests laufen isoliert (`python -S`) |
| 7 | Laufende Nummern ab 100 brachen im PDF zwischen den Ziffern um | mittel | Spalte 10 mm, kein Umbruch |
| 8 | Ein neuer Durchgang übernahm offene Berichtigungen und zählte alte Prüfungen als „erledigt“ | mittel | Berichtigungen bleiben beim Durchgang ihres Originals |
| 9 | Zurückspielen laut README löschte neuere Protokolle und vergab ihre IDs noch einmal | mittel | Zurückspielen ergänzt Protokolle nur; Zähler gehoben, sonst Folgenummer |
| 10 | Trigger umgehbar (INSERT/UPDATE OR REPLACE, Nachschieben in geschlossene Durchgänge, Wieder-Öffnen, Prüferkennung umschreiben) | niedrig | 22 Trigger, `recursive_triggers` an |
| 11 | Prüfseite nannte zu erfundenen Kennungen vorhandene Protokoll-IDs; ein Byte in der Kennung ergab „unbekannt“ | niedrig | Kennung gilt nur mit passendem N und SHA-256; Zuordnung über den Inhalt |
| 12 | Bei „instandsetzen“ fehlte im Protokoll die Angabe zur nächsten Prüfung | niedrig | „entfällt – … Freiprüfung nötig“ |
| 13 | Prüftag nach UTC (Container), Dialog nach Browserdatum – zwischen 0 und 2 Uhr verschieden | niedrig | `heute()` in deutscher Zeit; Dialog zeigt den Tag des Servers |
| 14 | Prüferzählung im Sammelprotokoll zählte berichtigte Originale mit | niedrig | ohne Originale, deren Berichtigung im Durchgang steht |
| 15 | Absturz zwischen Datei und Commit ließ ein unterschriebenes Protokoll ohne Vorgang liegen | niedrig | Start legt solche Dateien nach `pdf/verwaist/` |
| 16 | Riesige Unterschriftsbilder (16 MP) banden 220 MB je Anfrage | niedrig | höchstens 4 MP |
| 17 | Kleinere Mängel: veraltete Unterschrift im Dialog, Umbruch „nicht unterschrieben“, Fokus im Profil, Überschrift allein am Seitenende, Doku zu `/tmp` und Ubuntu 22.04, Demo-Nachreichen mit falschen Ordnern bzw. fremden Prüfungen | niedrig | behoben |

Ohne Befund geprüft: Rechte aller neuen Routen (auch kein Existenz-Leck über 403/404), CSRF auf der öffentlichen
Prüfseite, Pfade, WeasyPrint lädt nichts aus dem Netz und keine fremden Dateien, Escaping aller Texte, parallele
Festschreib-Anfragen (eine gewinnt, die anderen 409, eine Datei), Commitfehler (Datei wieder weg), Kontolöschung nach
Festschreiben, Migration mit vier gleichzeitig startenden Prozessen, PDF/A-3b und qpdf für alle Protokollarten samt
Grenzfällen, Stempel auf jeder Seite (auch 210 Seiten), Docker-Pakete und Auflösung der Abhängigkeiten für Python 3.12
(x86_64 und aarch64), Testlauf unter CPython 3.12.

### Zu prüfen

- **Docker-Build**: hier ohne Docker nicht gebaut. Die Debian-Pakete gibt es unter diesen Namen in bookworm und
  trixie (`python:3.12-slim` ist derzeit trixie); WeasyPrint 70 und seine Abhängigkeiten sind reine Python-Räder
  bzw. haben Räder für Python 3.12 (cffi). Nach dem Deploy auf dev einmal ein Protokoll erzeugen.
- **PDF/A**: veraPDF 1.30.3 bestätigt PDF/A-3b für alle Protokolle – mit Fotos, Unterschriften, Scans aus der App,
  gedrehten und quer liegenden Seiten, vor und nach dem Stempel. **Hinten angefügte fremde PDFs** können die
  Konformität brechen (etwa nicht eingebettete Schriften); umgewandelt werden sie nicht – sie bleiben, wie sie
  hochgeladen wurden, und stehen mit Prüfsumme im Verzeichnis.
- **PDF-Betrachter**: geprüft mit pdftotext, Ghostscript, pypdf, qpdf und veraPDF – nicht mit Adobe Acrobat, macOS
  Vorschau und den Betrachtern von iOS und Android. Dort bitte ansehen, ob Stempel, Unterschrift und QR-Code sauber
  erscheinen. Den eingebauten Betrachter von Chrome zeigt das kopflose Chromium hier nicht; die Antwort der Route ist
  `200 application/pdf` mit einer CSP ohne `sandbox`.
- **Schrift**: DLRG Univers wird als Teilmenge eingebettet; die Schrift erlaubt laut ihren Angaben die Einbettung
  für Ansicht und Druck. Bestätigt am 19.10.2026: Die Lizenz der DLRG deckt das für PDF-Protokolle ab.
- **Rechtliche Einordnung**: Die Unterschrift im Protokoll ist eine einfache elektronische Unterschrift (Bild plus
  Anmeldung, Zeitpunkt und Prüfsumme), keine qualifizierte. Eine PDF-Signatur (PAdES), die Acrobat selbst prüft,
  wäre ein späterer Schritt.
- **Protokollinhalt** nach EN 365 bitte mit den Sachkundigen gegen die Papierkarte abgleichen – insbesondere, ob
  etwas fehlt (etwa Nutzer der PSA, das kommt mit der Personenzuordnung in Phase 2).
- **Regeln der Berichtigung** (nur der eigene Prüfer, nur die letzte Prüfung, keine Aussonderung, Prüftag bleibt)
  fachlich bestätigen.
- **Große Prüfdurchgänge**: Ab etwa 1 000 Artikeln dauerte das Sammelprotokoll länger als die 15 s, die andere
  Schreibvorgänge auf die Sperre warten; solche Durchgänge besser teilen.
- **Speicher**: WeasyPrint belegt je Arbeitsprozess nach dem ersten Protokoll grob 50–100 MB mehr.
- **Prüfseite**: Grenze 20 Prüfungen je Adresse in 15 Minuten, 200 MB je Datei – bei Bedarf anpassen.
- **Oberfläche** in Chromium geprüft (1280 px und 390 px, Maus und Touch, Drehen des Telefons, Pixeldichte 2 und
  3); nicht in Safari/iOS – dort besonders das Zeichnen auf dem Signatur-Pad ansehen.
- **dev nach dem Deploy**: Prüfungen, die dort in Lieferung 2 abgeschlossen wurden, stehen „ohne Protokoll“. Ein
  erneuter Demolauf (Befehl wie bisher) schreibt die DEMO-Prüfungen nachträglich fest; eigene Testprüfungen
  bleiben ohne Protokoll (oder lassen sich berichtigen).

### Nachbesserungen nach der Auslieferung (Durchsicht vom 17.10.2026)

- **Fotos groß zeigen**: Ein Klick auf ein Foto öffnet es über der Seite statt in einem neuen Tab – Befundfotos
  einer Prüfung (auch im Entwurf), Fotos einer Meldung und das Produktbild in Artikel- und Produktansicht. Mehrere
  Fotos derselben Prüfung oder Meldung lassen sich mit den Pfeilen oder den Pfeiltasten durchblättern; darunter
  stehen Prüfpunkt und Bemerkung, „Original“ öffnet die hochgeladene Datei. Schließen mit ×, Escape oder einem
  Klick neben das Foto. Strg-/Cmd-Klick und die mittlere Maustaste öffnen weiter einen neuen Tab.
- **Befunde einer abgeschlossenen Prüfung**: „kritisch“ steht in einer eigenen schmalen Spalte neben dem Prüfpunkt
  statt im Text; als Karte (schmale Bildschirme) entfällt die leere Zelle. „(Soll …)“ bricht nicht mehr um.
  Das PDF-Protokoll ist unverändert.

## Lieferung 4 – Überblick (17.10.2026)

Übersicht mit den Fälligkeiten je Ordner, die Führungskraft nur lesend, `/m/<token>` mit deutlichem Status, Export
(CSV je Ordner, ZIP aller Protokolle, Lebenslauf-PDF) – dazu auf Wunsch der Katalogaustausch zwischen dev und
Produktion und Rückrufe zu Produkten. Lieferung 3 wurde am 17.10.2026 mit „Implementiere Lieferung 4“ freigegeben.
Den Etikettenbogen (QR-Etiketten als PDF) braucht der Nutzer nicht – er entfällt (siehe „Abweichungen“).

### Neu

- **Übersicht „Fälligkeiten je Ordner“** (`services/ueberblick.py`) statt der Tabelle je Gliederung: Gliederungen
  mit ihren Unterordnern eingerückt, Spalten Bestand, überfällig, neu, bald fällig, gesperrt, Lebensdauer erreicht
  und nächste Fälligkeit. Die Zahlen kommen aus derselben Abfrage wie die Ordnerleiste (abgeleiteter Status, auf die
  Oberordner hochgerechnet) – keine zweite Wahrheit. Systemordner sind keine eigenen Zeilen, ihr Inhalt zählt bei
  der Gliederung; eine Gliederung in einer Gliederung ist eine eingerückte Zeile und zählt nicht doppelt. Jede Zahl
  öffnet die gefilterte Liste (`/material/pruefungen?ordner=…&status=…`), die nächste Fälligkeit alles Fällige im
  Zweig. Ab 30 Zeilen starten tiefere Ebenen zugeklappt; unter 860 px Karten.
- **Prüfungen nach Ordner**: Die Liste zeigt den gewählten Zweig („Nur … mit Unterordnern · alle Ordner“) und
  behält ihn beim Wechsel des Filters; neuer Reiter „einsatzbereit“ (die gleichnamige Kachel führte ins Leere).
- **„Fällig“ umfasst „Lebensdauer erreicht“** – im Standardfilter, in „Als Nächstes zu prüfen“ und in der Zahl der
  fälligen Prüfungen, wie schon im roten Abzeichen der Ordnerleiste.
- **Führungskraft sieht alles und ändert nichts**: Ein Test ruft jede schreibende Route aller Blueprints des Moduls
  (auch die neuen) als Führungskraft auf und erwartet 403 aus der Rechteprüfung, jede lesende 200 – und vergleicht
  danach alle Tabellen des Moduls. Neu lesbar für sie: die Produktmeldungen (ohne Knöpfe zum Abarbeiten).
  Eine Unterschrift hinterlegen nur noch Prüfer und Materialwarte; wer keins von beiden ist, sieht im Profil eine
  alte Unterschrift nur noch zum Entfernen.
- **`/m/<token>`**: Die Artikelseite trägt bei ausgesonderten, gesperrten und abgelaufenen Artikeln schon im HTML
  ein Banner („AUSGESONDERT – … darf nicht mehr verwendet werden“) – sofort nach dem Scan sichtbar, noch bevor die
  Ansicht geladen ist; nur nach der Rechteprüfung. Der QR-Abschnitt am Artikel heißt „QR-Code und NFC“: Adresse
  kopieren und auf einen Tag schreiben oder mit einem beliebigen Etikettenprogramm als QR-Code drucken.
- **Export** (`services/export.py`, `services/lebenslauf.py`, für alle mit Zugang zum Modul):
  - **CSV je Ordner** `/material/export/<ordner>.csv`: alle Artikel im Ordner und darunter, dazu die von hier
    gesperrten (sie liegen in „Gesperrt“ der Gliederung); Ausgesonderte im Export ihrer Gliederung. Spalten: Nummern,
    Produkt, Kategorie, Norm, Materialart, Ablage, Gliederung, Status, Sperrzustand und -grund, Herkunft, zuletzt
    geprüft, nächste Prüfung, wirksames Intervall, Herstellung, Kauf, Erstgebrauch, Lebensende, Bemerkung, in Prüfung
    bei, DEMO. Für deutsches Excel: `;`, UTF-8 mit BOM, Datumswerte TT.MM.JJJJ bzw. MM/JJJJ, Schutz gegen Formeln.
  - **ZIP aller Protokolle** `/material/export/<ordner>-protokolle.zip`: die festgeschriebenen Prüf- und
    Aussonderungsprotokolle dieser Artikel (auch berichtigte Originale samt Berichtigung) und die Sammelprotokolle
    der Durchgänge im Zweig, dazu `Verzeichnis.csv` mit Protokoll-ID, Artikel, Prüfer, Ergebnis, beiden Prüfsummen und
    Zustand. Eine fehlende oder veränderte Datei kommt nicht mit, steht aber im Verzeichnis („fehlt“, „verändert“) und
    im Log – der Export bricht nicht ab. Höchstens 2 GB, gebaut als Zwischendatei unter `/data/tmp`.
  - **Lebenslauf-PDF** `/material/artikel/<id>/lebenslauf.pdf`: Stammdaten mit QR-Code, Zustand (Status, Sperre,
    Fälligkeit, wirksames Intervall, Lebensende), alle abgeschlossenen Prüfungen und die Aussonderung chronologisch
    mit Prüfer, Urkundennummer, Ergebnis, Mängelzahl, Protokoll-ID und Prüfsumme der Datei (Berichtigungen mit
    Verweis), die Prüfdurchgänge, die Rückrufe, die den Artikel betreffen, und die Ereignisse aus seinem Journal. PDF/A-3b
    wie die Protokolle, aber auf Abruf und **nicht festgeschrieben**: kein Stempel, keine Ablage, kein Journaleintrag;
    das steht im Fuß jeder Seite.
  - Knöpfe: „CSV“ und „Protokolle (ZIP)“ in jedem Ordner, „Lebenslauf (PDF)“ an jedem Artikel.
- **Katalogaustausch** (`services/katalog_export.py`, `services/importer.py`, Katalog → „Katalog exportieren“ /
  „Katalog importieren“, nur Katalogpfleger und Verwaltung; Kommandozeile `export-catalog`, `import-catalog` nimmt
  jetzt auch ZIP): Der Export ist ein ZIP im neuen **Format 2** (siehe „Katalogdatei“) mit Kategorien, Produkten samt
  Originalbild und aktuellen Herstellerdokumenten (Datei oder Link) und je Ziel dem aktiven Prüfformular – ohne
  DEMO-Einträge, ohne Bestand, Prüfungen, Meldungen und Rückrufe; `bericht.txt` im ZIP und eine Vorschau im Dialog
  sagen, was drin ist und was ausgelassen wurde. Der Import gleicht über die neue **Katalogkennung** (`uid`) ab, sonst
  wie bisher über Name bzw. Hersteller + Modell + Artikelnummer und übernimmt dann die Kennung – Umbenennen und
  Verschieben auf dev kommen als Änderung an, nicht als Dublette. Bilder gelten über ihre SHA-256 als gleich,
  Dokumente über Datei bzw. Link und Version (sonst neue Version bei gleicher Art und gleichem Titel). Erst ein
  Probelauf mit Bericht (neu, geändert, unverändert je Art, Bilder, Dokumente, Hinweise) – er schreibt nichts, auch
  keine Datei –, dann „Übernehmen“. Warnungen nennen Intervall- und Lebensdaueränderungen, die vorhandene Artikel
  betreffen; ein Wechsel der Materialart bei vorhandenen Artikeln ist ein Fehler. Gelöscht, deaktiviert oder
  zurückgezogen wird nie etwas.
- **Rückrufe** (`services/rueckruf.py`): Ein Katalogpfleger legt am Produkt einen Rückruf an – Titel, was betroffen
  ist und was zu tun ist, Link auf die Meldung des Herstellers, optional die betroffenen Seriennummern (eine je
  Zeile, leer = alle Artikel) – und beendet ihn später mit Vermerk. Sichtbar für alle mit Zugang: am Produkt (mit den
  betroffenen Artikeln samt Ablage und Zustand), als rotes Banner an jedem betroffenen Artikel, als Hinweis in dessen
  Prüfung, als Marke „Rückruf“ in den Artikellisten, als Kasten auf der Übersicht und im Lebenslauf. Die Mail geht an
  alle Materialwarte (gibt es keinen, an die Verwaltung) und an die Prüfer, die einen betroffenen Artikel schon
  geprüft haben – entdoppelt, im Hintergrund; das Ergebnis (wie viele, wie viele nicht hinausgingen) steht am
  Rückruf. Gesperrt wird nicht automatisch: Prüfer sperren über „Sperren (Rückruf)“ im Banner mit dem neuen
  Sperrgrund **„Rückruf“**. Je Artikel gilt ein Rückruf als erledigt, wenn der Artikel gesperrt ist oder nach dem
  Rückruf geprüft wurde – abgeleitet, nie gespeichert. Journal am Produkt („Rückruf angelegt“, „Rückruf beendet“).

### Migration

- Schemaversion 7, läuft beim Start von selbst: neue Tabelle `mat_recall` (Rückrufe, mit dem Produkt gelöscht);
  neue Spalte `uid` an `mat_category` und `mat_product` mit eindeutigem Index – vorhandene Zeilen bekommen beim Start
  eine zufällige Kennung, neue per Trigger. Keine Tabelle wird umgebaut; alle Zeilen bleiben.
- Keine neuen Abhängigkeiten, keine Handarbeit: `docker compose up -d --build` genügt.

### Neue Abhängigkeiten

Keine. Der Lebenslauf nutzt WeasyPrint und segno aus Lieferung 3, Export und Katalogaustausch nur die
Standardbibliothek (`csv`, `zipfile`).

### Entscheidungen

- **Rückrufe** (vom Nutzer entschieden): Mail an alle Materialwarte plus die Prüfer betroffener Artikel; Hinweis
  statt automatischer Sperre, Sperrgrund „Rückruf“ nur für Prüfer. Materialwarte sind die Konten mit Stufe
  „Verwaltung“ im Modul Material (das Startkonto gehört dazu); die Verwaltung der Plattform bekommt die Mail nur, wenn
  es keinen Materialwart gibt. Ausgesonderte Artikel sind außer Dienst und nie betroffen. Eine Berichtigung zählt
  nicht als Prüfung nach dem Rückruf (sie ändert eine alte Prüfung), eine Prüfung in derselben Sekunde wie der Rückruf
  zählt als vorher. Ein laufender Rückruf blockiert die Freiprüfung nicht – der Prüfer entscheidet.
- **Gesperrte zählen bei der Gliederung**, nicht im Herkunftsordner – dort liegen sie, so zählt die Ordnerleiste.
  Im CSV- und ZIP-Export eines Ordners sind sie dagegen dabei (sie stammen von dort), wie beim Prüfdurchgang.
- **Ausgesonderte gehören zum Export ihrer Gliederung**, nicht mehr zum Unterordner, aus dem sie kamen – die
  Aussonderung löscht die Herkunft, und „Ausgesondert“ zählt nirgends mehr als Bestand.
- **Nächste Fälligkeit** in der Übersicht: frühestes Datum unter einsatzbereiten, bald und überfälligen Artikeln;
  neue (sofort fällig), gesperrte und abgelaufene haben ihre eigenen Spalten.
- **Lebenslauf**: nur das Journal des Artikels (Produktänderungen stehen am Produkt), höchstens 2000 Einträge;
  verbindlich bleiben die Protokolle, deren Prüfsummen er nennt.
- **Katalogaustausch**: Originalbilder gehen unverändert mit (nur so stimmt die SHA-256 zwischen den Instanzen; der
  Dialog weist darauf hin, dass Fotos ihre Metadaten mitnehmen). Formulare: je Ziel das aktive, sonst die neueste
  Version mit Prüfpunkten; ein DEMO-Formular lässt das Ziel ganz weg. Der Import legt Dateien vor der Schreibsperre ab
  (Bildverarbeitung blockiert nie andere) und räumt sie bei einem Fehler wieder weg; ein unveränderter Katalog kostet
  keine Bildverarbeitung. Der Import über die Oberfläche ist ohne ausdrückliches „Übernehmen“ immer ein Probelauf.
- **Meldungen lesen** jetzt alle mit Zugang zum Modul (auch Materialwarte fremde); abarbeiten weiter nur
  Katalogpfleger.

### Abweichungen vom Konzept, mit Begründung

- **Kein Etikettenbogen**: Das Konzept nennt „Etikettenbogen als PDF für Standard-Klebeetiketten und Anhänger“ und
  die Route `/material/etiketten/<ordner_id>.pdf`; der Nutzer braucht die Funktion ausdrücklich nicht. Die
  QR-Adresse jedes Artikels bleibt und lässt sich kopieren (NFC/RFID oder eigenes Etikettenprogramm).
- **Routen**: Für das Protokoll-ZIP und den Lebenslauf nennt das Konzept keine; gewählt sind
  `/material/export/<ordner>-protokolle.zip` und `/material/artikel/<id>/lebenslauf.pdf`.
- **Katalogaustausch und Rückrufe** stehen nicht im Konzept – Wünsche des Nutzers für diese Lieferung.
- **„Sätze vollständig“** (Szenario der Führungskraft) lässt sich ohne Soll-Bestand und Set-Konzept nicht prüfen;
  die Übersicht zeigt je Ordner, ob alles einsatzbereit ist.

### Review vor der Auslieferung

Gebaut haben vier Agenten parallel in getrennten Arbeitsbäumen (Übersicht und Rechte, Export, Katalogaustausch,
Rückrufe), jeder mit eigenen Tests, Browserprüfung und der ganzen bestehenden Suite; zusammengeführt auf dev. Danach
eine Durchsicht in fünf Bereichen – Katalogaustausch, Rückrufe, Export, Übersicht und Rechte, Oberfläche (mit
Browserrundgang je Rolle bei 1280 und 390 px) – mit Gegenprüfung jedes Befunds durch einen zweiten Agenten, der ihn
nachzustellen und zu widerlegen versuchte. Von 25 Meldungen hat die Gegenprüfung 16 bestätigt; alle sind behoben,
die Korrekturen im Katalogaustausch noch einmal gegengeprüft (dabei kam Nr. 16 dazu). Abgesichert in
`test_material_katalog.py` (Intervall-Reihenfolge, Dokumentketten, Formulartitel, Namenskette und ihre Grenze,
Bildgrenze, ZIP-Verzeichnis) und je `test_review_lieferung4` in `test_material_rueckruf.py` und
`test_material_export.py`:

| # | Befund | Schwere | Behebung |
| --- | --- | --- | --- |
| 1 | Katalogimport: Verliert eine Kategorie ihre Intervall-Vorgabe, während ihr Produkt in derselben Datei ein eigenes Intervall bekommt, stand der ganze Import (die Prüfung lief gegen den alten Stand der Produkte und hatte schon geschrieben) | mittel | Die Prüfung „jedes Produkt hat ein Prüfintervall“ läuft im Import nach den Produkten; „Kategorie ändern“ prüft (unverändert für die Oberfläche) vor dem Schreiben |
| 2 | Importdialog: „Übernehmen“ war von Anfang an sichtbar – `.btn` schlug das hidden-Attribut | mittel | `.btn[hidden]` bleibt verborgen; „Übernehmen“ erst nach einem fehlerfreien Probelauf mit Änderungen |
| 3 | Zwei aktuelle Dokumente gleicher Art und gleichen Titels (etwa Datenblatt de/en): Neue Versionen landeten an der falschen Kette oder ließen den Import scheitern | niedrig | Der Export schreibt die Vorgänger einer Kette mit (`vorgaenger`); der Import belegt erst exakte Treffer, dann Vorgänger, sonst nur Eindeutiges („Mehrdeutig“ statt über Kreuz) |
| 4 | Die Ablage-Handler von Import- und Dokumentdialog sammelten sich am gemeinsamen Dialog: doppelte Uploads, falsche Meldungen | niedrig | Handler gelten nur, solange ihr Dialog offen ist |
| 5 | Formular ohne Titel: Jeder Import legte eine neue, aktive Formularversion an | niedrig | Leerer Titel = keine Vorgabe beim Vergleich |
| 6 | Namenskette („altes Modell bekommt einen Zusatz, neues den alten Namen“, ebenso Geschwisterkategorien und wandernde Artikelnummern) brach den Import ab | niedrig | Konflikte werden zurückgestellt und nachgeholt, solange sich etwas bewegt |
| 7 | Produktbild zwischen 30 und 31 MB: beim Hochladen angenommen, im Import abgewiesen – der ganze Austausch stand | niedrig | Import nimmt, was das Hochladen nimmt (31 MB); Größeres lässt der Export aus und nennt es |
| 8 | ZIP-Import: Die Grenze von 20 000 Einträgen griff erst nach dem Einlesen des ganzen Inhaltsverzeichnisses (Speicher) | niedrig | Zahl und Größe des Verzeichnisses werden am Ende-Satz geprüft, bevor es gelesen wird (auch Zip64) |
| 9 | Prüfung: Der Rückruf-Hinweis versprach auch in einer Berichtigung, ihr Abschluss erledige den Rückruf | niedrig | eigener Satz für Berichtigungen |
| 10 | Ein Zeilentrenner (U+2028) im Titel ließ jede Rückruf-Mail scheitern | niedrig | Betreff wird auf eine Zeile gebracht |
| 11 | Seriennummern mit doppeltem oder geschütztem Leerzeichen (aus kopierten Listen) trafen keinen Artikel | niedrig | Vergleich wie am Artikel: innerer Leerraum zählt als ein Leerzeichen |
| 12 | Die Prüfung nannte nur einen von mehreren offenen Rückrufen | niedrig | alle Titel |
| 13 | Rückrufdatum („seit“, „angelegt am“, „beendet am“) als UTC-Datum – nachts der Vortag | niedrig | in Ortszeit |
| 14 | Datum einer Ausnahme im Durchgang als UTC-Datum – im Lebenslauf und im Sammelprotokoll (aus Lieferung 3) | niedrig | in Ortszeit |
| 15 | „Die ältesten fehlen“ im Lebenslauf auch bei genau 2000 vollständigen Einträgen | niedrig | gekürzt heißt: es gibt mehr |
| 16 | (aus der Gegenprüfung der Korrekturen) Eine von Hand gebaute, lange Namenskette in ungünstiger Reihenfolge kostete quadratisch viele Versuche unter der Schreibsperre | niedrig | höchstens 50 Nachholrunden, danach ein Fehler mit Hinweis |

Nicht bestätigt (mit Begründung verworfen) wurden unter anderem: Artikel mit vom System vergebener Seriennummer bei
Rückrufen mit Seriennummern (folgt dem Datenmodell), Abfragen je Artikel auf der Produktseite (gemessen: 64 ms bei
300 Artikeln und drei Rückrufen), führende Nullen in Excel (Eigenschaft jeder CSV), der Rechte-Rundumtest
(Testabdeckung, kein Produktfehler – jede Route prüft ihr Recht).

### Zu prüfen

- **Rückruf-Mail auf dev.strömis.de**: Ohne `SMTP_HOST` steht die Mail nur im Log, und die Produktseite meldet sie
  als „nicht hinausgegangen“. Mit echtem Mailserver einmal anlegen und den Empfang prüfen. Startet Gunicorn während
  des Versands neu, geht der Rest verloren; die Seite zeigt nach 10 Minuten „Versand nicht bestätigt“ (kein
  Nachversand). Gespeichert wird die Zahl der Empfänger, nicht wer.
- **CSV in Excel und LibreOffice** nicht geöffnet: erwartet passend für deutsches Excel; „03/2021“ kann Excel als
  Datum lesen; ein Formel-Schutz-`'` (etwa `'-7`) bleibt in der Zelle sichtbar.
- **Große Bestände** nicht gemessen: Protokoll-ZIP (jede Datei wird zweimal gelesen, ein Gunicorn-Thread ist so
  lange belegt, `/data/tmp` braucht bis 2 GB frei) und Katalogaustausch mit echten Herstellerdokumenten (Upload ohne
  Fortschrittsanzeige).
- **Katalogaustausch, seltene Umbauten**: Wandert eine Kategorie in eine andere Ebene und nimmt eine neue ihren
  alten Namen am alten Ort ein, oder tauschen zwei Geschwister ihre Namen, bricht der Import mit „gibt es an dieser
  Stelle schon“ ab – dann in zwei Schritten austauschen. Eine neue Dokumentversion, die früher gültig wäre als ein
  in der Produktion schon von Hand hochgeladenes Dokument gleicher Art und gleichen Titels, ist ein Fehler mit
  Abhilfe im Text. Bricht der Prozess zwischen Ablegen und Speichern hart ab, bleiben Dateien ohne Eintrag liegen.
- **Fotos mit Ortsangaben**: Der Katalog-Export nimmt die Originalbilder samt EXIF/GPS mit.
- **Phase 2 (Freigaben je Ordner)**: Export eines Unterordners enthält dessen gesperrte Artikel aus „Gesperrt“ der
  Gliederung; der Lebenslauf prüft das Recht im aktuellen Ordner; `/faellig?ordner=` und die Produktseite eines
  Rückrufs (alle betroffenen Artikel samt Ablage) müssen dann nach Leserecht filtern. **Erledigt mit Phase 2 ·
  Lieferung 1**: Export und Lebenslauf gehen über die Heimat des Artikels und brauchen das Grundrecht dort,
  `/faellig?ordner=` verlangt Leserecht am Ordner (sonst 404), und Produktseite, Liste und Mail eines Rückrufs
  zeigen nur die Artikel, die der Leser bzw. Empfänger sieht.
- **Varianten**: Ein Rückruf gilt für genau ein Produkt; über „Als Variante kopieren“ entstandene Produkte sind
  nicht erfasst – bei Bedarf je Variante anlegen.
- **Oberfläche** in Chromium geprüft (1280 und 390 px, je Rolle); nicht in Safari/iOS.
- **Originalfotos mit Ortsangaben**: Wer im Modul lesen darf, kann Originale abrufen – auch die Fotos von
  Produktmeldungen, die jetzt die Führungskraft sieht (so schon vor Lieferung 4 bei Prüffotos). Trägt ein Foto
  GPS-Daten, gehen sie mit; ebenso im Katalog-Export.
- **Katalogimport „Mehrdeutig“**: Hat die Produktion selbst zwei aktuelle Dokumente gleicher Art und gleichen Titels,
  die nicht aus dem Austausch stammen, stoppt ein Dokument gleichen Titels aus der Datei den Import mit „Mehrdeutig“
  (vorher wurde still eins gewählt). Abhilfe: Titel in der Produktion unterscheiden.
- **Fälligkeiten im Import**: Ändert der Import das Intervall einer Kategorie, zieht er Fälligkeiten wie bisher vor,
  bevor die Produkte der Datei übernommen sind – im ungünstigen Fall eine Prüfung früher als nötig, nie später.
- **Python-Version**: Die Prüfung des ZIP-Inhaltsverzeichnisses nutzt `zipfile._EndRecData` (Python 3.12 und 3.14
  geprüft); ändert eine künftige Version sie, schlägt `test_zip_verzeichnis_vor_dem_lesen` an.

## Lieferung 5 – Feinschliff nach Pilot (18.10.2026)

Rückmeldungen aus dem Pilotbetrieb. Lieferung 4 wurde am 17.10.2026 mit „Lieferung 5 starten“ freigegeben, Lieferung 5
am 18.10.2026 mit „Starte mit Phase 2“. Keine neue Schemaversion (bleibt 7), keine neuen Abhängigkeiten.

### Neu

- **Ordnerkopf aufgeräumt**: „+ Prüfdurchgang“ steht nicht mehr im Kopf jedes Ordners – eröffnet wird ein Durchgang
  unter „Prüfungen“ (mit Wahl des Ordners). An seiner Stelle sitzt der Knopf **„Export“** mit einem Untermenü:
  „Artikelliste (CSV)“ und „Protokolle (ZIP)“, je mit einem Satz, was drinsteckt; die beiden Knöpfe und der Hinweis
  unter dem Kopf entfallen. Das Menü schließt mit einem Klick daneben, auf einen Eintrag oder mit Escape und bleibt
  am Telefon ganz im Bild.
- **Ordnerfoto im Dialog „Bearbeiten“** (wie das Produktbild): Foto wählen, ersetzen oder entfernen beim Bearbeiten –
  und schon beim Anlegen; der eigene Knopf „Foto“ entfällt.
- **Einheitliche Knöpfe**: Grau umrandet ist der Standard für jede Aktion – in Kopfzeilen (auch „+ Artikel“,
  „Bearbeiten“, „Verschieben“, „Löschen“, „Export“), in Listen und in Formularen; die roten Textknöpfe gibt es im Modul
  nicht mehr, auch „Suchen“ ist grau. Rot gefüllt bleibt nur die eine Hauptaktion eines Schritts (bestätigender
  Dialogknopf, „Prüfung starten“, „Prüfung beginnen“, „Festschreiben“, „Durchgang abschließen“, „Speichern“ im
  Formular-Editor, „Prüfen“ auf der Prüfseite), rot umrandet nur das Bestätigen von Endgültigem (Sperren, Aussondern,
  Meldung ablehnen, Rückruf beenden, „Festschreiben“ mit Ergebnis „aussondern“). Die kleinen „PDF“-Felder in Listen
  sind grau, die Filter der Produktmeldungen sehen aus wie die übrigen Filterleisten.
- **Ordnerseite**: „Bestand im ganzen Zweig“ steht unten über dem Journal statt als Erstes unter dem Kopf; Foto,
  Beschreibung und Prüfintervall des Ordners bleiben oben.
- **Urkundennummer im eigenen Profil**: Die Verwaltung setzt in der Nutzerverwaltung nur noch das Häkchen „Prüfer“ –
  jetzt auch ohne Nummer; das Eingabefeld im Dialog entfällt, dort steht die Nummer nur noch lesend („noch keine –
  solange darf er nicht prüfen“). Der Prüfer trägt sie selbst im Profil ein, im Abschnitt „Urkundennummer und
  Unterschrift“ (`PUT /api/material/urkundennummer`, nur eigenes Konto, nur mit Häkchen; leer entfernt sie). Prüfen
  darf er weiterhin erst mit gültiger Nummer; bis dahin zeigt das Profil einen Hinweis, Artikel- und Prüfungsseite
  einen Link dorthin (`/profil#unterschrift`), die Nutzerliste die gelbe Marke „Prüfer – Urkundennummer fehlt“. Jede
  Änderung steht im Journal am Konto („Urkundennummer geändert“, vorher/nachher). Die Unterschrift kann er schon mit
  dem Häkchen hinterlegen. Die Schnittstelle der Verwaltung nimmt `urkundennummer` weiter an (Skripte, Tests), geprüft
  wie im Profil – nur leer statt „ohne Nummer abgewiesen“.
- **Profilseite neu geordnet**: Profilbild oben, darunter „Stammdaten“ (jetzt mit Überschrift), dann „Urkundennummer
  und Unterschrift“ (bzw. „Unterschrift“ für Materialwarte), zuletzt „Passwort ändern“ – an der Funktion ändert sich
  nichts.
  Nimmt die Verwaltung einem Konto das Häkchen „Prüfer“, verschwindet auch seine Urkundennummer (sie gälte sonst beim
  nächsten Häkchen ungefragt wieder); aufs Protokoll – etwa einer Aussonderung durch den Materialwart – kommt eine
  Nummer nur, solange das Konto wirksam Prüfer ist.
- **Vorschläge im Suchfeld** (Kopfzeile jeder Modulseite, `suche.js`): schon ab zwei Zeichen – auch Teile einer
  Nummer – bis zu acht Artikel als Steckbrief unter dem Feld: Produktfoto, Inventarnummer mit Status (Rückruf, DEMO
  markiert), Produkt, Seriennummer und Ablage, der getippte Teil gelb hervorgehoben. Tipp oder Klick öffnet den
  Artikel; Pfeiltasten wählen, Enter öffnet, Escape schließt; ohne Wahl führt Enter wie bisher zur Trefferliste,
  „Alle N Treffer anzeigen“ ebenso. Ohne JavaScript bleibt es ein gewöhnliches Suchformular.
- **Jeder Mangel braucht eine Bemerkung** – nicht mehr nur ein Foto. Festschreiben (auch einer Berichtigung oder mit
  „aussondern“) lehnt sonst ab („Jeder Mangel braucht eine Bemerkung – sie fehlt bei: …“); im Formular steht am
  Mangel „Bemerkung ist Pflicht“, das Feld ist bei einem Mangel immer offen, die Abschlussleiste zählt „Mängel ohne
  Bemerkung“ mit. Eine eben getippte Bemerkung wird vor der Prüfung gespeichert – kein falscher Alarm.
- **Produktsuche zeigt alle Treffer** (Artikel anlegen, Meldung zuordnen): statt acht Treffern und „genauer suchen“
  eine scrollbare Liste aller Treffer; je 50 kommen vom Server, die nächsten, sobald das Ende der Liste ins Bild rückt.

### Telefon, Foldable und Tablet

Grundlage war eine Bestandsaufnahme im Browser mit Touch-Emulation: vier Agenten, je eine Geräteklasse (Telefon hoch
und quer, Foldable zu/auf und Doppelbildschirm mit Scharnier, Tablet hoch und quer, Bedienung mit Tastatur, Kerbe und
Einhandbedienung), 70 Befunde mit Messwert und Bildschirmfoto. Gebaut in vier Paketen, danach je Geräteklasse und für
die übrige App nachgeprüft, die Nachbefunde behoben und gegengeprüft. Am Rechner mit Maus ändert sich nichts (Pixelvergleich).

- **Prüfformular im Feld**: Mit Bildschirmtastatur (auch quer) bleibt das Feld, in das man tippt, ganz sichtbar – Kopf-
  und Abschlussleiste kleben dann nicht. Quer und bei wenig Höhe ist die Abschlussleiste einzeilig (58–85 statt
  120–145 px), auf breiten Touch-Geräten stehen Umschalter, Foto und Bemerkung je Prüfpunkt in einer Zeile (Karten
  halb so hoch) und „Festschreiben“ neben den Ergebnissen. **Wert und Bemerkungen werden schon beim Tippen
  gespeichert** (entprellt, je Prüfpunkt nacheinander, beim Verlassen der Seite noch einmal) – ein Neuladen verliert
  nichts mehr; Ergebnis, Grund und nächste Prüfung merkt sich das Fenster bis zum Festschreiben. „Foto entfernen“
  fragt nach; neben „📷 Foto“ (Kamera) gibt es am Finger „Galerie“.
- **Fotos groß**: Wischen blättert, nach unten wischen schließt; die Seite dahinter rollt nicht mit; Schließen und
  Pfeile am Finger 44 px, mit Abstand zu Kerbe und Wischleiste. Die Unterschrift auf dem Pad bleibt beim Auf- und
  Zuklappen eines Foldables richtig groß.
- **Kopfleiste der ganzen App**: Was nicht in die Zeile passt, steht im Menü „Mehr ▾“ – zuerst weichen Name und
  Schriftzug, dann wandern Abmelden, Profil und Module ins Menü; der aktive Punkt bleibt stehen. Vorher lagen
  „Profil“ und „Abmelden“ am Telefon und am Tablet hochkant unsichtbar hinter dem Rand.
- **Modulnavigation** in einer Zeile: Reiter rollen mit Randhinweis, die Nummernsuche liegt hinter einer Lupe (auf
  Übersicht, Bestand und Trefferseite offen); am Telefon beginnt der Inhalt bei 130 statt 218 px, quer klebt die
  Kopfleiste im Modul nicht mehr. Die Suchvorschläge passen bei offener Tastatur in den sichtbaren Bereich.
- **Ordnerleiste** steht schon ab 1024 px (Tablet quer) fest neben dem Inhalt; als Schublade: Schließen 44 px,
  Wischen nach links schließt, lange Namen brechen um statt „…“.
- **Listen nach Inhaltsbreite** (Container-Abfragen statt Fensterbreite): volle Tabelle, ab 820 px Inhalt eine enge
  Tabelle mit zusammengelegten Spalten, ab 600 px dichte Karten – neben der Leiste und im Doppelbildschirm passend.
  In der Kartenansicht gibt es „Sortieren nach“, die Richtung und „alle auswählen“; leere Felder entfallen.
  Auswahlkästchen 24 px mit Beschriftung, Knöpfe, Reiter und Zähler am Finger mindestens 44 px hoch.
- **Dialoge**: Am Touchgerät öffnet ein Dialog keine Tastatur mehr (der Fokus liegt auf der Überschrift, außer ein
  Feld ist ausdrücklich dafür vorgesehen, etwa der Wiki-Kommentar); die Knöpfe bleiben sichtbar, die Seite dahinter
  rollt nicht mit. Foto im Ordner- und Produktdialog als richtiges Fotofeld: Vorschau vor dem Speichern, Kamera oder
  Galerie, am Rechner auch Hineinziehen. Das Ordnerfoto lässt sich groß ansehen.
- **Doppelbildschirm mit Scharnier**: Nichts Bedienbares liegt unter der Falz – Ordnerleiste links, Inhalt rechts,
  Dialoge und Großansicht in einer Hälfte.
- **Kleinigkeiten**: Kerbe und Wischleiste frei (safe-area) für feste Leisten, Schublade und Sammelleiste; Hinweise,
  die nur im Tooltip standen, sind ohne Maus sichtbar (ein Tipp auf Zähler und Marken erklärt sie); Seriennummer- und
  Suchfelder ohne Autokorrektur und Kleinschreibung; das QR-Adressfeld zoomt unter iOS nicht mehr; Brotkrumen am
  Finger leichter zu treffen.
- **Übrige App**: Ein Konto ohne Wiki-Recht landet nach der Anmeldung nicht mehr auf einer Fehlerseite ohne
  Kopfleiste – mit Material-Recht geht es nach /material, sonst zeigt die Seite Kopfleiste, Profil und Abmelden.

### Zu prüfen

- **Auf echten Geräten** (nur emuliert geprüft): Android Chrome und iOS Safari mit Bildschirmtastatur hoch und quer
  (Prüfformular), Wischen in der Großansicht und der erste Tipp danach, Kamera bzw. Galerie bei Prüf- und
  Ordnerfotos, keine Tastatur beim Öffnen von Dialogen, Rollsperre hinter Dialogen ab iOS 16, Silbentrennung in der
  schmalen Ordnerleiste, Surface Duo / Pixel Fold mit Segmenten.
- **iOS 15 und älter** kennen keine Container-Abfragen: Dort gelten für die Listen die alten Regeln nach Fensterbreite.
- **Tablet quer 1093–1199 px** neben der Leiste bekommt die volle Tabelle (Inhalt ab 821 px, kein Überlauf gemessen) –
  wie ein Rechner gleicher Inhaltsbreite.
- **Speichern beim Tippen** schickt beim Schreiben mehr Anfragen als früher (je Feld höchstens eine gleichzeitig,
  800 ms nach dem letzten Tastendruck); sie füllen weder Journal noch Lebenslauf.

## Phase 2 · Lieferung 1 – Freigaben je Ordner (18.10.2026)

Phase 2 bringt mehrere Gliederungen und externe Prüfer in dieselbe Instanz. Lieferung 1 trennt den Bestand je
Gliederung über Freigaben je Ordner und bringt dazu die globale Seriennummernsuche, die Personenzuordnung und das
Löschkonzept. Erinnerungen per Mail folgen mit Lieferung 2, der CSV-Import mit Lieferung 3. Lieferung 5 aus Phase 1
wurde am 18.10.2026 mit „Starte mit Phase 2“ freigegeben. Gebaut nach dem Bauentwurf vom 18.10.2026; die drei Fragen,
die daraus offen waren, hat der Betreiber am 18.10.2026 entschieden – eingearbeitet und beschrieben unter „Die drei
offenen Fragen – entschieden“ und „Nachbesserungen nach der Auslieferung (Entscheidungen vom 18.10.2026)“; dazu kommen
die „Nachbesserungen nach der Auslieferung (Wünsche vom 18.10.2026)“, zuletzt die Modulstufe Material und die
Vorgabe für neue Konten; vier weitere offene Punkte hat der Betreiber am 18.10.2026 entschieden („Vier weitere Punkte –
entschieden“, darunter die Rückfrage beim einzigen Materialwart). „Neu“ und „Schnittstelle“ beschreiben den Stand
danach. Schemaversion 8 (mit den Nachbesserungen vom 18.10.2026: 9, mit der Modulstufe: 10), keine neuen
Abhängigkeiten. Stand: freigegeben am 19.10.2026 („Starte Lieferung 2“).

„Plattform-Verwaltung“ heißt hier: Verwaltung im Modul Verwaltung der Rechte-Matrix (das Startkonto gehört dazu) –
Nutzer, Stufen, Häkchen, Einstellungen, das Protokoll der globalen Suchen. „Material-Verwaltung“ heißt: Stufe
„Verwaltung“ im Modul Material (seit der Nachbesserung „Modulstufe Material“; die Plattform-Verwaltung gehört immer
dazu) – Produktkatalog, alle Bestände, Gliederungen, jede Freigabe. Bis zu dieser Nachbesserung hatte die
Plattform-Verwaltung diese Rechte im Modul und der Produktkatalogpfleger (Häkchen) die Katalogpflege; die Texte unten
sind angeglichen.

### Neu

- **Freigaben je Ordner** (`services/rechte.py`): Den Bestand zeigen nur noch Freigaben. Eine Freigabe gibt einem
  Konto an einem Ordner das Recht **lesen**, **prüfen** oder **verwalten** – im Ordner und in allen Unterordnern, auch
  über verschachtelte Gliederungen hinweg. Rechte addieren sich nur; einen Entzug weiter unten gibt es nicht. Je Konto
  und Ordner höchstens ein Grundrecht (lesen oder verwalten, dauerhaft oder bis zu einem Tag) und höchstens eine
  Prüffreigabe (seit der Nachbesserung: dauerhaft, wo die Person dort auch ein Grundrecht hat, sonst – externer
  Prüfer – befristet; mit Ende höchstens 24 Monate). Der letzte Tag zählt mit; ab 0:00 Uhr deutscher Zeit des
  Folgetags greift die Freigabe nicht mehr. Abgelaufene bleiben stehen („abgelaufen am …“), bis jemand sie verlängert
  oder entfernt. An „Gesperrt“ und „Ausgesondert“ gibt es keine Freigaben – sie gelten über ihre Gliederung. Die
  Material-Verwaltung sieht und verwaltet alles. Freigaben wirken nur bei Konten mit Zugang zum Modul (Stufe und Name).
- **Was die Rechte erlauben**:
  - **lesen**: alles ansehen – Bestand, Prüfungen samt Protokollen, Durchgänge, CSV und Protokoll-ZIP, Lebenslauf,
    Journal von Ordner und Artikel, zugeordnete Personen.
  - **prüfen** – nur mit Qualifikation (Häkchen „Prüfer“ und Urkundennummer); ohne sie wirkt die Prüffreigabe gar
    nicht, auch nicht als Leserecht. Sie gibt die **Prüfsicht** – Ordnerbaum, Artikel mit Stammdaten, Zustand und
    Bemerkung, ihre Prüfungen mit Protokollen und Fotos, die Durchgänge – und erlaubt prüfen, sperren und Durchgänge
    führen. Kein Export, kein Lebenslauf, kein Journal, keine Personen.
  - **verwalten**: dazu Ordner und Artikel pflegen, aussondern, Reservierungen freigeben, Personen zuordnen und
    Freigaben vergeben. Prüfen nur mit eigener Prüffreigabe – das gilt auch für die Material-Verwaltung.
- **Modulzugang** (seit der Nachbesserung „Modulstufe Material“): Name im Profil **und** die Stufe „Mitglied“ oder
  „Verwaltung“ im Modul Material, gesetzt in der Nutzerverwaltung (die Plattform-Verwaltung hat sie von selbst). Ohne
  Stufe wirken weder Freigaben noch das Häkchen „Prüfer“. Ein Mitglied ohne Freigabe sieht Katalog, Suchfeld und
  Profil, aber keinen Bestand. Ohne Zugang antwortet das Modul mit 403 und sagt, was fehlt: der Name oder die Stufe
  („Für dein Konto ist das Modul Material nicht freigeschaltet – das macht die Verwaltung in der Nutzerverwaltung.“).
  Kopfleiste, Weiterleitung nach der Anmeldung und Profil lesen die gespeicherte Stufe – ohne Abfrage. Ohne Leserecht
  fehlen nur die Reiter „Prüfungen“ und „Bestand“; das Suchfeld bleibt, und die Übersicht zeigt statt der Zahlen
  „Meine Freigaben“ (mit abgelaufenen samt den Verwaltern, die verlängern können) und den Weg zu Katalog und
  Nummernsuche.
- **Trennung je Gliederung**: Was ein Konto nicht sieht, antwortet wie etwas, das es nicht gibt – 404 mit derselben
  Meldung, ob die Kennung im Pfad steht oder im Inhalt der Anfrage (auch als `"7"` oder `7.0`). 403 gibt es nur, wenn
  man den Gegenstand sieht, die Aktion aber nicht darf, mit Klartext (etwa „Häkchen und Urkundennummer hast du, aber
  für diesen Ordner keine Prüffreigabe – die vergibt der Materialwart des Ordners unter Ordner → Bearbeiten →
  Freigaben.“). Gefiltert sind Übersicht, Ordnerbaum, Listen und Zählungen, Fällige, Entwürfe, Durchgänge, Suche samt
  Vorschlägen, die Spalte „Bestand“ im Katalog, Produktseite und Produktjournal, Rückrufe, Meldungen, Exporte und
  Mediendateien. Ein Oberordner ohne eigenes Recht steht in Ordnerleiste, Bestand, Übersicht und Pfadzeile nur als
  grauer Pfad (Name, keine Zahlen, nicht anklickbar). „Gesperrt“ und „Ausgesondert“ einer Gliederung, die man nicht
  ganz sieht, zeigen nur die eigenen Artikel – auf der Übersicht als Zeile „Gesperrt (deine Artikel)“. 403 und 404
  zeigt die Oberfläche als Klartext mit dem Knopf „Zur Übersicht“.
- **Oberfläche nach dem Recht am Gegenstand** (`static/material.js`): Knöpfe richten sich nach `darf` des Ordners,
  Artikels, der Prüfung oder des Durchgangs, nicht mehr nach einer Stufe des Kontos. Export, Lebenslauf, Journal und
  die Spalte „Person“ gibt es nur mit Grundrecht, „Prüfen“ nur mit Prüffreigabe dort. Fehlt einem qualifizierten
  Prüfer nur die Prüffreigabe, sagt die Artikelansicht: „Für diesen Ordner hast du keine Prüffreigabe – die vergibt
  der Materialwart unter Ordner → Bearbeiten → Freigaben.“ Die Ordnerwahl beim Anlegen und Verschieben bietet nur
  Ordner an, die man verwaltet (beim Prüfdurchgang auch solche mit Prüffreigabe), Ordner einer anderen Gliederung nur,
  wer beide verwaltet – sonst mit Hinweis darauf.
- **Eine Heimat je Artikel**: Gesperrte, verlorene und ausgesonderte Artikel gehören zu ihrem Herkunftsordner, alle
  anderen zu dem Ordner, in dem sie liegen – für Rechte, Filter, Export und Durchgänge gleich. Das Aussondern behält
  jetzt die Herkunft: Wer nur „Fahrzeug 1“ verwaltet, sieht dessen ausgesonderte Artikel und ihre
  Aussonderungsprotokolle weiter, und der Export von „Fahrzeug 1“ enthält sie. Vor Schritt 8 Ausgesonderte und solche,
  deren Herkunftsordner gelöscht wurde, gehören zur Gliederung. Das Löschen eines Ordners sperren nur noch gesperrte
  und verlorene Artikel, die dorthin zurückkehren.
- **Freigaben am Ordner** (`static/freigaben.js`) – seit der Nachbesserung vom 18.10.2026 der Reiter **Freigaben** im
  Dialog „Ordner bearbeiten“ (Knopf **Bearbeiten** im Ordnerkopf; einen eigenen Knopf „Freigaben“ gibt es nicht
  mehr), nur für Verwalter, nicht an Systemordnern:
  - **+ Freigabe**: Person suchen (ab 3 Zeichen, nur aktive Konten mit Namen und Zugang zum Modul, ohne E-Mail), „Gilt für“ (der Ordner
    oder ein Oberordner, den man verwaltet; Vorgabe ist die Gliederung, wenn man sie verwaltet), eine **Vorlage** und
    optional eine Notiz. Vorlagen: „Führungskraft“ (lesen, dauerhaft), „Materialwart“ (verwalten, dauerhaft), „Prüfer“
    (lesen und prüfen, beides dauerhaft – seit der Nachbesserung), „Materialwart und Prüfer“ (ebenso), „Externer
    Prüfer“ (nur prüfen bis … – die Prüfsicht) und „Einzeln …“. Grundrecht und Prüffreigabe entstehen in einem Schritt,
    ganz oder gar nicht. Vorlagen mit Prüfen gibt es nur für qualifizierte Konten; „bis“ steht auf dem 31.12. des
    Folgejahres, „dauerhaft“ gibt es nur für den, der selbst dauerhaft verwaltet (beim Prüfen dazu nur mit Grundrecht).
  - **Hier vergeben**: Person (ein Konto ohne Namen als „(Konto ohne Namen)“), Gliederung, Recht, Ende, Zustand
    (gültig, gelb „läuft in n Tagen ab“, grau „abgelaufen am …“, „wirkt nicht – …“ mit dem Grund vom Server: „Konto
    deaktiviert“, „Konto ohne Namen“, „kein Zugang zum Modul Material“, „Qualifikation fehlt“ oder „dauerhaft nur mit
    lesen oder verwalten“), Notiz, von wem
    und wann vergeben; Ändern und Entziehen, wo man darf – „Entziehen“ nur, wo es auch gelingt (sonst steht dort, dass
    es nur über die Material-Verwaltung geht). Darüber **„Alle Prüffreigaben verlängern bis …“** für den ganzen Zweig
    (auch bis zu 90 Tage abgelaufene), mit den übersprungenen Zeilen samt Grund. Am Telefon und am Tablet (bis etwa
    920 px Fensterbreite) stehen die Listen als Karten, am Rechner als Tabelle.
  - Zugeklappt **Geerbt von oben** (nur lesbar, ohne Notiz), **In Unterordnern** und **Verlauf**.
  - Wer eine Prüffreigabe entzieht, erfährt, wie viele offene Prüfungen das Konto dort noch hat (unter Prüfungen →
    „Offene Prüfungen“ → „Freigeben“).
  - Im Ordnerkopf steht für Verwalter „n Freigaben laufen in den nächsten 30 Tagen ab“ mit dem Knopf „Verlängern …“;
    er öffnet „Ordner bearbeiten“ im Reiter „Freigaben“ gleich bei „Alle Prüffreigaben verlängern bis …“. Hat sich an
    den Freigaben etwas geändert, lädt der Ordner nach dem Schließen neu (eigene Rechte, Ablaufhinweis).
- **Wer Freigaben vergibt**: Wer einen Ordner verwaltet, vergibt dort und darunter an jedes aktive Konto mit Namen und
  Zugang zum Modul (Stufe Mitglied oder Verwaltung; sonst 409 mit Klartext) – auch aus anderen Gliederungen. Nie länger, als er dort selbst verwaltet (unbefristet nur, wer selbst unbefristet
  verwaltet). Eine fremde Freigabe ändert oder entzieht er nur, wenn er sie selbst so hätte vergeben dürfen – ein
  befristeter Verwalter kann einen dauerhaften weder entziehen noch kürzen noch herabsetzen. Die eigene kann er nur
  verkürzen, herabsetzen oder entziehen – das immer, auch wenn sie länger läuft als sein Verwalten –, sich selbst gibt
  er nichts. Danach muss jede Gliederung noch einen Verwalter haben, der mindestens so lange bleibt wie er (sonst 409
  „… das macht nur die Material-Verwaltung“; Verwalter ohne Stufe oder Namen zählen nicht). Prüffreigaben gibt es nur
  für qualifizierte Konten (409). Die Notiz (eine Zeile, höchstens 200 Zeichen) sehen nur die Verwalter des Ordners und
  die Material-Verwaltung – der Inhaber also nur, wenn er dort selbst verwaltet, nie unter „Meine Freigaben“. Die
  Material-Verwaltung vergibt überall ohne diese Grenzen – Prüffreigaben aber auch sie nur an qualifizierte Konten, befristet für höchstens 24 Monate und
  dauerhaft nur mit Grundrecht (Nachbesserung).
- **Meine Freigaben** auf der Übersicht: die eigenen Freigaben, gültige und im letzten Jahr abgelaufene, mit Ordner,
  Recht und Ende; gelb, was in 30 Tagen abläuft – dort und bei abgelaufenen steht, wer verlängern kann. Der Abschnitt
  ist zugeklappt und öffnet sich von selbst, wenn eine Freigabe bald abläuft, abgelaufen ist oder nicht wirkt. Wer noch
  keine hat, liest „Du hast noch keine Freigabe im Bestand – der Materialwart deiner Gliederung vergibt sie.“ Die
  Schnittstelle dazu antwortet jedem Angemeldeten, auch ohne Modulzugang.
- **Gliederungen anlegen**: auf oberster Ebene nur die Material-Verwaltung; nach „+ Gliederung“ öffnet sich gleich
  „Ordner bearbeiten“ im Reiter „Freigaben“ mit der Vorlage „Materialwart“. Eine Gliederung in einem Ordner legt an,
  wer den Oberordner verwaltet. Einen vorhandenen Ordner zur Gliederung macht nur, wer die Gliederung darüber verwaltet
  (sonst 403; der Dialog „Ordner bearbeiten“ bietet die Art dann nicht an) – alles darin wechselt dabei die
  Gliederung. Gesperrte und ausgesonderte Artikel mit Heimat darin ziehen in seine neuen Systemordner (Journal „Ordner
  zur Gliederung gemacht“).
- **Verschieben zwischen Gliederungen**: nur, wer beide Gliederungen verwaltet, oder die Material-Verwaltung (sonst
  403); ein Ziel, das man nicht sieht, antwortet 404 (vorher 403). Mit einem Ordner wandern seine gesperrten und
  ausgesonderten Artikel in die Systemordner der neuen Gliederung (Journal mit Grund „Ordner in andere Gliederung
  verschoben“). Freigaben am Ordner gehen mit; was vom alten Oberordner geerbt war, gilt nicht mehr. Verlässt ein
  Artikel beim Verschieben den Zweig eines offenen Durchgangs – auch innerhalb einer Gliederung –, nimmt ihn der
  Durchgang aus („verschoben am TT.MM.JJJJ – nicht mehr im Bereich des Durchgangs“), und ein offener Entwurf darin
  verliert den Durchgang; erledigte Zeilen bleiben als Nachweis. Danach antwortet „Einbeziehen“ mit 409 und ein
  Prüfstart mit diesem Durchgang mit 404; beim Eröffnen zählen ausgenommene und erledigte Zeilen nicht mehr als
  Konflikt. Das Sammelprotokoll druckt statt eines Pfads aus der anderen Gliederung „(aus dem Bereich des Durchgangs
  verschoben)“, und Prüfer von dort stehen nicht darin. Die Verschieben-Dialoge sagen vorher, was mit Freigaben, Systemordnern und
  Durchgängen geschieht. In der Durchgangsansicht steht ein hinausverschobener Artikel, den man nicht mehr sieht, ohne
  Link und ohne Knöpfe mit „nicht in deinem Bereich“; „Einbeziehen“ bietet sie für Hinausverschobene nicht an.
- **Globale Seriennummernsuche** (`services/globalsuche.py`, `static/global.js`): Unter den eigenen Treffern bieten
  Trefferseite und Suchvorschläge „In anderen Gliederungen nach der Seriennummer „…“ suchen“ an – zu jeder Anfrage,
  die dafür taugt, auch neben eigenen Treffern und wenn ein eigener Artikel genau diese Nummer hat; nicht der
  Material-Verwaltung, die alles sieht. Nach einer Bestätigung („wird mit deinem Namen protokolliert“) sucht der
  Server exakt (Groß/klein egal) nach Herstellerseriennummern ab 4 Zeichen – nie nach Inventar- oder STR-Nummern, die
  sind fortlaufend – und nur unter den Artikeln, die das Konto nicht sieht. Höchstens zehn Steckbriefe ohne Link
  stehen direkt unter der eigenen Liste, ab der Trennlinie „Aus anderen Gliederungen“, gestrichelt umrandet und mit
  der Gliederung als Marke ganz oben: Produktbild, Inventar- und Seriennummer, Produkt, Kategorie, Norm, Herstellung,
  Lebensende, ein Sperrwort („gesperrt“, „verloren gemeldet“, „ausgesondert“) und „Gehört zu <Gliederung> · <Ordner>“
  (ein persönlicher Ordner heißt dort nur „persönlicher Ordner“). Keine Kennungen, kein Prüfstatus, kein Sperrgrund,
  keine Prüfungen, Fotos, Bemerkungen oder Personen. Das Suchfeld haben jetzt alle mit Modulzugang, auch
  Mitglieder und Prüfer ohne Freigabe.
- **QR-Steckbrief**: Ein Scan an einem Artikel außerhalb des eigenen Bereichs zeigt „Dieser Artikel gehört nicht zu
  deinem Bereich.“ und auf Wunsch („Steckbrief anzeigen (wird protokolliert)“) denselben Steckbrief – mit dem
  Sperrwort, damit ein Finder sieht, ob ein fremdes Seil gesperrt, verloren gemeldet oder ausgesondert ist.
- **Fremde Dubletten**: Gibt es die Seriennummer beim selben Produkt schon in einem Bereich, den man nicht sieht,
  lehnen Anlegen und Ändern ab (409) – ohne Inventarnummer und ohne Gliederung, mit Verweis auf die globale Suche.
  Eine sichtbare Dublette nennt wie bisher die Inventarnummer.
- **Protokoll**: Globale Suche, QR-Steckbrief und fremde Dublette stehen jedes Mal mit Konto, Name, Art, Anfrage und
  Treffern in `mat_global_search` – zwölf Monate lang, dann fällt eine Zeile heraus (aufgeräumt beim Schreiben, beim
  Start und beim Lesen). Die Plattform-Verwaltung liest das Protokoll in der Nutzerverwaltung unter „Globale Suchen
  (Modul Material)“ – die Material-Verwaltung nicht, es ist eine Aufzeichnung über Personen. Ausgeliefert mit einer
  Bremse (zusammen höchstens zehnmal je Konto in 15 Minuten, danach 429); sie ist am 18.10.2026 auf Wunsch entfernt
  (siehe „Nachbesserungen nach der Auslieferung“) – die Kontrolle ist das Protokoll.
- **Personenzuordnung** (`services/zuordnung.py`): Wer einen Artikel verwaltet, ordnet ihn einer Person zu, ändert
  oder löst die Zuordnung – an jedes aktive Konto mit Namen; die Person braucht keinen Modulzugang (die Personensuche
  dafür fragt mit `zweck=zuordnung` und findet auch Konten ohne Stufe). In der
  Artikelansicht steht „Zugeordnet an“ mit „Zuordnen …“, „Ändern“ und „Lösen“ (Personensuche wie bei den Freigaben;
  Hinweis „Nur für PSA, die eine Person dauerhaft nutzt. Erscheint nicht in Protokollen.“), in der Ordnerliste die
  Spalte „Person“, der Filter „Zugeordnet an …“ (sobald im Zweig jemandem etwas zugeordnet ist) und neben „Verschieben
  nach …“ die Sammelaktionen „Zuordnen an …“ und „Zuordnung lösen“ (bis 500 Artikel, ganz oder gar nicht). Mit
  gesetztem Filter führt „Fällige Artikel dieser Person im ganzen Zweig →“ in die Liste unter Prüfungen
  (`?zugeordnet=`). Sehen nur mit Grundrecht – nicht in der Prüfsicht, nicht im Steckbrief,
  nicht in Prüf-, Aussonderungs- und Sammelprotokollen und nicht im Lebenslauf-PDF. Die CSV hat die neue Spalte
  „Zugeordnet an“ (vor „DEMO“). Aussondern löst die Zuordnung; ausgesonderte Artikel lassen sich niemandem zuordnen
  (409). Deaktivierte Konten sind nicht wählbar, eine bestehende Zuordnung steht mit „(deaktiviert)“ da.
- **Rückrufe je Bereich**: Liste, Zahlen, Übersicht und Produktseite zeigen jedem nur die betroffenen Artikel, die er
  sieht. Die Mail geht je betroffenem Artikel an die Verwalter seiner Heimat (mit Stufe und Namen) und an die Prüfer,
  die ihn geprüft haben und dort heute prüfen dürfen; hat er keinen Verwalter, an die Material-Verwaltung (ohne die
  Plattform-Verwaltung; gibt es keine, an die Plattform-Verwaltung). Jeder Empfänger bekommt eine Mail mit genau den
  Artikeln, die er sehen darf. Anlegen und beenden darf nur die Material-Verwaltung; sie sieht alle Bestände und
  bekommt die vollen Zahlen, nicht gefundene Seriennummern und die Zahl der Mails. Ein Mitglied ohne Bestand liest
  statt „0 Artikel“: „Wie viele Artikel betroffen sind, sehen die Materialwarte der Gliederungen.“
- **Meldungen je Bereich**: Eine Produktmeldung sehen die Material-Verwaltung, der Melder und wer ihren Ordner sieht –
  auch im Produktjournal; im Artikeljournal steht sie gar nicht mehr. Den Ordnerpfad zeigt sie nur dem, der den
  Ordner sieht (die Material-Verwaltung sieht jeden), sonst nur die Gliederung. Die Mail zu einer neuen Meldung geht an
  die Material-Verwaltung (gibt es keine außer der Plattform-Verwaltung, an diese) und nennt nur die Gliederung.
- **Medien je Datei** (`services/medien.py`): Ordnerfotos nur mit Leserecht am Ordner, Befundfotos und Prüfanhänge mit
  Leserecht am Artikel, Meldungsfotos wie die Meldung; Produktbilder und Herstellerdokumente für alle mit Modulzugang.
  Sonst 404.
- **Löschkonzept** (`services/loeschung.py`): Beim Löschen eines Kontos räumt die Anwendung in derselben Transaktion
  vorher auf – je Freigabe und je Zuordnung ein Journaleintrag (Grund „Konto gelöscht“), Zuordnungen gelöst, offene
  Entwürfe auf „(gelöschtes Konto)“ und ohne Urkundennummer (der Materialwart gibt die Reservierung frei),
  Produktmeldungen und Suchprotokoll ohne Namen. Abgeschlossene und festgeschriebene Prüfungen, Aussonderungen,
  Durchgänge, Rückrufe und das Journal bleiben mit den Namen der Handelnden (EN 365). Prüfnachweise werden unbefristet
  aufbewahrt, auch nach der Aussonderung – die Anwendung löscht sie auf keinem Weg (Entscheidung des Betreibers vom
  18.10.2026). Der Dialog „Löschen“ der
  Nutzerverwaltung nennt die Folgen vorher („n Freigaben werden entfernt, m Artikel verlieren ihre Zuordnung, k offene
  Prüfungen werden zu Reservierungen ohne Prüfer …“), beim einzigen Materialwart einer Gliederung auch, dass dort
  danach nur noch die Material-Verwaltung verwaltet (Entscheidung vom 18.10.2026). Deaktivieren ändert im Modul
  nichts – Freigaben wirken nicht mehr, Zuordnungen bleiben. Die Stufe bleibt am Konto und geht mit ihm.
- **Journal**: Freigaben stehen am Ordner, an dem sie vergeben sind („Freigabe erteilt“, „geändert“, „entzogen“,
  „entfernt“), und nur dessen Verwalter sehen sie; Zuordnungen stehen am Artikel. Betroffene stehen darin nur als
  pseudonymer Kontoverweis (`users.mat_ref`, 128 Bit Zufall), der erst beim Lesen zum Namen wird; die Notiz nie, nur
  „Notiz geändert“. Handelnde stehen mit Namen, nie mehr mit E-Mail – auch der Rolleneintrag beim Anlegen eines Kontos
  nicht. Ordner- und Artikeljournal gibt es nur mit Grundrecht.
- **Nutzerverwaltung** (seit der Nachbesserung „Modulstufe Material“): Die Spalte „Material“ ist eine Auswahl wie die
  anderen Module – „–“, „Mitglied“, „Verwaltung“ –, darunter die Marke „Prüfer“ (gelb „Prüfer – Urkundennummer
  fehlt“), klein „n Freigaben“ und gelb „wirkt nicht – kein Zugang“ (Häkchen oder Freigaben ohne Stufe) bzw. „ohne
  Namen – kein Zugang“. Stufe Mitglied oder Verwaltung und das Häkchen „Prüfer“ gibt es nur mit Namen (400); das
  Häkchen „Produktkatalogpfleger“ gibt es nicht mehr (400, wenn es jemand schickt). „Bearbeiten“ zeigt die
  Freigaben des Kontos mit Ordner, Recht, Ende und Zustand (Entziehen ja, angelegt und geändert wird am Ordner – der
  Ordnerpfad führt dort gleich in den Reiter „Freigaben“; bleiben offene Prüfungen, führt ein Hinweis zu Material →
  Prüfungen → „Offene Prüfungen“; ohne Stufe darüber „Diese Freigaben wirken nicht …“). Ist das Konto heute der
  einzige Materialwart einer Gliederung, fragt die Nutzerverwaltung vor Material „–“ (Tabelle und Dialog) und vor dem
  Deaktivieren nach („Einziger Materialwart“, nur eine Warnung; Entscheidung vom 18.10.2026), und der Dialog „Löschen“
  nennt es. Die Liste holt die Zahlen aller Konten mit einer Abfrage. Der Hilfetext erklärt das Modell.
- **DEMO-Daten** (`scripts/material_demo.py`): zweite Gliederung „DEMO-Gliederung Nachbarstadt“ mit „DEMO-Lager NS“
  und drei Artikeln, einer davon mit der Seriennummer `DEMO-NS-4711` für die globale Suche; sie kommt auch zu einem
  vorhandenen Demo-Bestand dazu. `--demo --konten` legt einmalig fünf DEMO-Konten mit Namen und zufälligem Passwort
  an (wird einmal ausgegeben): `demo-wart-a@example.invalid` (verwaltet die DEMO-Gliederung),
  `demo-wart-b@example.invalid` (verwaltet die Nachbarstadt), `demo-pruefer@example.invalid` (lesen und prüfen in der
  DEMO-Gliederung, seit der Nachbesserung beides dauerhaft) und `demo-extern@example.invalid` (nur 30 Tage prüfen im
  DEMO-Lager) – alle mit Stufe Mitglied – sowie seit der Modulstufe `demo-mv@example.invalid`
  („DEMO-Material-Verwaltung“: Stufe Verwaltung im Modul Material, keine Plattform-Verwaltung, keine Freigaben). Nur
  für dev.

### Migration

- Schemaversion 8, läuft beim Start von selbst, wiederholbar – ein zweiter Lauf ändert nichts:
  - `users.mat_ref`: pseudonymer Kontoverweis für jedes Konto (128 Bit Zufall, eindeutiger Index);
  - `mat_folder_grant` bekommt `note` und `updated_at`, einen eindeutigen Index „ein Grundrecht je Konto und Ordner“
    und Trigger gegen Freigaben an Systemordnern und gegen ein Enddatum, das nicht `JJJJ-MM-TT` ist;
  - neue Tabelle `mat_global_search` (Protokoll der globalen Suchen, QR-Steckbriefe und fremden Dubletten);
  - Indizes für die Filter über die Heimat, die exakte Seriennummer und die Medien je Datei.
- **Freigaben aus Phase 1** – wer bisher in den vorhandenen Gliederungen sah, sieht weiter: An jeder vorhandenen
  obersten Gliederung bekommt jedes Konto (auch deaktivierte) mit Stufe „Mitglied“ `lesen`, mit Stufe „Verwaltung“
  `verwalten`, beides dauerhaft; die Plattform-Verwaltung braucht keins. Jedes Konto mit Häkchen „Prüfer“ – auch
  Materialwarte und die Plattform-Verwaltung – bekommt dazu eine Prüffreigabe bis zum 31.12. des Folgejahres (bei
  einem Start 2026: **31.12.2027**); sie wirkt erst mit Urkundennummer. Seit der Nachbesserung (Schritt 9) ist sie
  dauerhaft, wo das Konto dort ein Grundrecht hat oder Plattform-Verwaltung ist – befristet bleibt sie nur bei Konten
  ohne Stufe aus Phase 1 (externe Prüfer). Katalogpfleger hatten mindestens die Stufe
  „Mitglied“ und lesen damit weiter; das entzieht bei Bedarf die Verwaltung. Schritt 10 (Modulstufe, unten) macht sie
  zur Material-Verwaltung. Je Freigabe ein Journaleintrag am Ordner
  („Migration Schritt 8“, das Konto nur als Verweis). In der Produktion gibt es noch keine Gliederung – dort entstehen
  keine Freigaben (siehe „Zu prüfen“).
- **Altfälle**: Gesperrte und verlorene Artikel, die im „Gesperrt“ einer anderen Gliederung liegen als ihr
  Herkunftsordner, kommen nach „Gesperrt“ der Gliederung ihrer Heimat. Offene Zeilen offener Durchgänge, deren Heimat
  nicht im Zweig des Durchgangs liegt, werden ausgenommen („verschoben (Bereinigung Schritt 8)“), offene Entwürfe dazu
  verlieren den Durchgang. Ausgesonderte aus Phase 1 bleiben ohne Herkunft und gehören zur Gliederung. Alles mit
  Journal.
- Die Stufe im Modul Material (`users.recht_material`) bleibt stehen; bis Schritt 10 wurde sie nicht mehr gelesen und
  nicht mehr geschrieben (außer wie bisher automatisch bei Verwaltung = 2), seit Schritt 10 ist sie wieder die Stufe
  (siehe „Modulstufe Material“). `mat_pruefer` und `mat_katalog` bleiben unverändert.
- **Rückweg**: nur neue Spalten, Tabellen, Indizes und Trigger. Eine Fassung aus Phase 1 startet auf einer Datenbank
  mit Schritt 8 und arbeitet wieder mit den globalen Stufen; Freigaben, Suchprotokoll und Kontoverweise übergeht sie.
  Die behaltene Herkunft an Ausgesonderten macht dort nur das Löschen eines Ordners strenger. Schritt 9 und 10
  (Nachbesserungen) siehe unten.
- Keine Handarbeit beim Update: `docker compose up -d --build` genügt. Danach braucht die Produktion ihre erste
  Gliederung (README, „Inbetriebnahme in der Produktion“).

### Neue Abhängigkeiten

Keine.

### Entscheidungen

- **Sichtbarkeit nur über Freigaben** – für Mitglieder: Rechte am Bestand haben genau eine Quelle, und jede Gliederung
  vergibt sie selbst. Die Stufe der Rechte-Matrix war dafür zunächst stillgelegt; seit der Nachbesserung „Modulstufe
  Material“ gibt sie wieder den Zugang zum Modul (Mitglied) und die Material-Verwaltung (Verwaltung), die alles sieht –
  getrennt vom Rechtekonzept der Gliederungen und ihrer Ordner.
- **Prüfen braucht für alle eine Prüffreigabe** – auch für Verwalter und die Material-Verwaltung: nur an Konten mit
  Häkchen und Urkundennummer; befristet (höchstens 24 Monate) seit der Nachbesserung nur noch für externe Prüfer, wer
  dort lesen oder verwalten hat, prüft dauerhaft. `verwalten` schließt prüfen nicht ein. Eine
  Prüffreigabe allein gibt nur die Prüfsicht; die Bemerkung bleibt darin, weil dort Prüfhinweise stehen
  (Sturzbelastung, Vorschaden). Das Häkchen „Prüfer“ setzt weiter nur die Plattform-Verwaltung – es ist eine
  Qualifikation für alle Gliederungen und wirkt nur mit Stufe im Modul.
- **Eine Heimat je Artikel**, auch für Ausgesonderte (die Herkunft bleibt beim Aussondern). Ein Artikel gehört genau
  einem Bereich – kein „Herkunft oder Ablage“ mehr.
- **Verschieben über Gliederungsgrenzen** nur mit verwalten an beiden Gliederungen: Ein externer Materialwart mit
  Rechten in zwei Gliederungen kann Bestand nicht von der einen in die andere abziehen. Offene Durchgänge nehmen
  verschobene Artikel mit Grund aus, statt Zeilen zu verdecken – ein festgeschriebenes Sammelprotokoll ist für alle
  gleich.
- **404 statt 403 für Fremdes**: Ein Konto erfährt nicht, ob es einen Gegenstand in einer anderen Gliederung gibt.
  Pfadnamen fremder Ordner stehen nur, wo sie zur Geschichte eines Artikels gehören: im Journal eines verschobenen
  Artikels, in festgeschriebenen Protokollen und als Titel und Ordner eines Durchgangs, in dem er stand.
- **Globale Suche nur nach der ganzen Herstellerseriennummer**, nach Bestätigung und protokolliert – zwölf Monate,
  deshalb nicht im unveränderlichen Journal. Dubletten beim Anlegen stehen im selben Protokoll; sonst taugte das
  Anlegen als Suche am Protokoll vorbei. Ausgeliefert zusätzlich mit einer gemeinsamen Bremse für Suche, QR-Steckbrief
  und Dublette; sie ist am 18.10.2026 auf Wunsch entfernt (siehe „Nachbesserungen nach der Auslieferung“).
- **Personenzuordnung** an jedes aktive Konto, setzen nur Verwalter, sehen nur mit Grundrecht, nie in PDFs und im
  Steckbrief – der Lebenslauf ist zur Weitergabe gedacht. Kein Namensschnappschuss: Den Stand hält der Artikel, die
  Geschichte das Journal mit Kontoverweis.
- **Löschkonzept**: Handelnde bleiben mit Namen (Nachweis, EN 365), Betroffene stehen nur pseudonym im Journal. Das
  ist **Pseudonymisierung, keine Anonymisierung** – aus dem Zusammenhang (Zeitpunkt, wer gleichzeitig handelte) bleibt
  ein Rückschluss möglich. So steht es auch im Textvorschlag fürs Verfahrensverzeichnis (README, „Austritt und
  Löschen“).
- **Rückrufe**: Empfänger sind die Verwalter der betroffenen Bereiche, nicht mehr alle Materialwarte. Anlegen und
  beenden darf nur die Material-Verwaltung, die alle Bestände sieht – so taugt ein Rückruf ohne Mail nicht als Abfrage,
  welche Seriennummern es anderswo gibt (die Antwort enthielte für andere nur die Zahlen des eigenen Bereichs).
- **Handelnde nur mit Namen**: Ohne Namen gibt es keinen Modulzugang; einen Rückfall auf die E-Mail gibt es nicht
  mehr, weder im Journal noch im Prüfernamen.

### Abweichungen vom Konzept, mit Begründung

- **Reihenfolge der Lieferungen**: Das Konzept nennt für Phase 2 zuerst den Erinnerungslauf, dann die Freigaben.
  Gebaut sind zuerst die Freigaben: Die Erinnerungen gehen an „die Verwalter des Ordners“, und die gibt es erst mit
  den Freigaben – vorher bekäme jeder Materialwart Mails für alle Gliederungen. Erinnerungen und Ablaufmails folgen
  mit Lieferung 2.
- **Ablauf im Journal**: Laut Konzept bleibt eine abgelaufene Freigabe „im Journal sichtbar“. Ablaufen ist aber kein
  Schreibvorgang: Im Journal steht die Erteilung mit Enddatum, die Liste zeigt „abgelaufen am …“. Einen eigenen
  Eintrag „Freigabe abgelaufen“ schreibt ab Lieferung 2 der Nachtlauf.
- **Materialwart prüft nicht von selbst**: Laut Konzept hat der Materialwart „bestehende Editor-Rechte, auf Ordner
  bezogen“. Prüfen gibt es hier für jeden nur mit eigener Prüffreigabe (Häkchen und Urkundennummer vorausgesetzt) –
  `verwalten` allein gibt kein Prüfrecht. Seit der Nachbesserung vom 18.10.2026 darf diese Prüffreigabe dauerhaft sein
  (Vorlage „Materialwart und Prüfer“); sie wirkt aber nur, solange das Grundrecht dort gilt – so entsteht auch über
  `verwalten` kein unbefristetes Prüfrecht ohne Grundrecht.
- **`mat_folder.owner_user_id`** bleibt ungenutzt; Verwalter eines Ordners sind die Konten mit `verwalten` dort oder
  darüber.
- **Pseudonymisierung statt „Anonymisierung beim Austritt“** (Risikotabelle des Konzepts): Der Prüfername in
  festgeschriebenen Prüfungen bleibt (EN 365), und aus dem Zusammenhang bleibt ein Rückschluss möglich – „anonym“ wäre
  falsch.

### Abweichungen vom Bauentwurf

- **Prüfsicht ohne Qualifikation** (Entwurf 8.2/11 „nimmt die Verwaltung das Häkchen weg → alles 404“): Ohne Häkchen
  oder Urkundennummer wirkt die Prüffreigabe nicht, und alles antwortet wie Unbekanntes mit 404 – den Modulzugang gibt
  seit der Modulstufe die Stufe, nicht mehr das Häkchen. Ohne Stufe antwortet alles 403 „… nicht freigeschaltet …“,
  bevor nach dem Gegenstand gefragt wird.
- **Journal beim Ausnehmen nach dem Verschieben**: Am Durchgang steht als „ausgenommen von“ „System“
  (`excluded_by_name`), der Journaleintrag „ausgenommen“ steht aber unter dem Namen dessen, der verschoben hat – das
  Journal hält fest, wer gehandelt hat. Die Bereinigung in Schritt 8 schreibt „Migration Schritt 8“.
- **`GET /ordner/<id>/zugeordnete`** liefert je Person zusätzlich `aktiv` – für „(deaktiviert)“ im Filter.
- **Zusätze**: `MatFreigaben.kopfhinweis(element, ordner, verlaengern)` für den Ablaufhinweis im Ordnerkopf und die
  Vorlage `"verlaengern"`, die direkt zum Knopf „Alle Prüffreigaben verlängern“ springt (seit der Nachbesserung
  `MatFreigaben.inhalt(element, ordner, {vorlage: "verlaengern"})` statt `oeffnen`). `requires_folder` kennt neben
  `leer="global"` und `leer="irgendwo"` auch `leer="zugang"`: `GET /artikel/vorschlag` braucht ohne Ordner nur
  Modulzugang, mit Ordner Leserecht dort (sonst 404). „Alle verlängern“ überspringt mit Grund
  auch deaktivierte Konten, die eigene Freigabe und Freigaben, die schon länger laufen.

### Schnittstelle

Die neuen Routen stehen in der Tabelle „Schnittstelle“ unten (Zeilen mit „Phase 2“). An vorhandenen Antworten ändert
sich:

- Jede Antwort mit Ordner, Artikel, Prüfung oder Durchgang trägt `darf` (`lesen`, `grund`, `pruefen`, `verwalten`) für
  genau dieses Objekt (Artikel und Prüfung: an der Heimat). `data-darf` der Seite heißt jetzt „irgendwo“ und hat neu
  `grund`, `gliederung_anlegen` und `qualifiziert`.
- Ordnerbaum: Knoten mit `nur_pfad` (nur `id`, `parent_id`, `name`, `kind`, `system_kind`) und mit `teilweise`
  (Systemordner, gezählt nur die eigenen Artikel).
- Artikel: `zugeordnet` (`id`, `name`, `gliederung`, `aktiv`) und `journal` nur mit Grundrecht, sonst `null`; in
  Listen `zugeordnet_name`. `durchgang` an Artikel und Prüfung einheitlich `{id, titel, ordner, sichtbar}`. Zeilen
  eines Durchgangs, die man nicht sieht, haben `sichtbar: false` und keine Kennung.
- `GET /suche` liefert `exakt_lokal` (ein sichtbarer Artikel hat genau diese Seriennummer) und `global_angebot` (zu
  jeder Anfrage, die für die globale Suche taugt – unabhängig von den lokalen Treffern –, außer für die
  Material-Verwaltung); `GET /ordner/<id>` und `GET /faellig` nehmen `zugeordnet=<Konto>`.
- `POST /globalsuche` findet nur Artikel, die das Konto nicht sieht; ein Treffer im eigenen Bereich ist kein 409 mehr.
  409 bekommt nur die Material-Verwaltung („Du siehst den Bestand aller Gliederungen – die normale Suche findet jeden
  Artikel.“). Jeder Steckbrief (Suche und QR) trägt `sperre`: „gesperrt“, „verloren gemeldet“, „ausgesondert“ oder
  `null`. Seit dem 18.10.2026 ungebremst: `POST /globalsuche` und `POST /globalsuche/qr` antworten nie 429.
- `DELETE /kategorien/<id>`: 409, wenn ein Dokument der Kategorie in einem Prüfprotokoll steht.
- Rückruf anlegen und beenden (nur die Material-Verwaltung): `betroffen`, `offen`, `nicht_gefunden`, `empfaenger`; ein
  Konto mit Teilsicht bekäme `betroffen`, `offen` und `benachrichtigt` seines Bereichs (kommt seit der Modulstufe nicht
  mehr vor).
- Ziel beim Verschieben nicht sichtbar: 404 statt 403. Fremde Dublette: 409 mit festem Text (seit dem 18.10.2026
  ohne Bremse, nie 429). 403 ohne Modulzugang nennt, was fehlt. Listeneinträge der Freigaben tragen `wirkt_nicht`
  (Grund oder `null`) und am Konto `zugang`; die Personensuche nimmt `zweck` (`freigabe` | `zuordnung`).

### Im Browser geprüft

Chromium am Rechner (1280 px) mit den DEMO-Daten und den vier DEMO-Konten:

- Plattform-Verwaltung: „+ Gliederung“ führt in den Freigaben-Dialog der neuen Gliederung (seit der Nachbesserung:
  „Ordner bearbeiten“, Reiter „Freigaben“), Vorlage „Materialwart“ vorgewählt, „dauerhaft“ angeboten.
- Materialwart: Ordnerkopf mit „Freigaben“ (seit der Nachbesserung im Dialog „Bearbeiten“), Export und dem
  Ablaufhinweis samt „Verlängern …“; Spalte „Person“;
  Sammelleiste mit „Verschieben nach …“ und „Zuordnen an …“. Mit `verwalten` an beiden DEMO-Gliederungen bietet die
  Ordnerwahl beim Verschieben die Ordner beider an.
- Prüfer mit Prüffreigabe in der DEMO-Gliederung und nur `lesen` in der Nachbarstadt: Ein Artikel der Nachbarstadt
  zeigt „Für diesen Ordner hast du keine Prüffreigabe …“.
- Externer Prüfer: Übersicht mit „Meine Freigaben“ (gelb, „Verlängern kann: …“), grauer Gliederung über dem Lager
  und der Zeile „Gesperrt (deine Artikel)“; im Ordner „Prüfen“ je Artikel, ohne Export, Journal und Spalte „Person“.

### Prüfung vor Auslieferung

Drei unabhängige Prüfungen – Sicherheit (Trennung je Gliederung, mit eigenen Konten am DEMO-Server nachgestellt),
Browser (Rundgang mit den DEMO-Konten am Telefon, am Tablet und am Rechner) und Abgleich mit dem Bauentwurf (mit
Skripten) – haben 13 Befunde gemeldet, zwei davon dieselbe Lücke. Jeder Befund ist vor der Behebung nachvollzogen
worden (Test, Anfrage, Browser oder im Code), alle zwölf sind behoben, die Rechte- und Trennungsfehler mit
Regressionstest. Danach liefen alle Suiten grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Wer nur einen Unterordner verwaltete – etwa ein externer Materialwart mit verwalten an G/Lager und an H –, machte ihn über „Ordner bearbeiten“ zur Gliederung und zog danach Artikel und Ordner von G nach H ab; die Regel „über Gliederungsgrenzen nur mit Verwalten an beiden“ (1.7 Nr. 2) war umgangen, rückgängig machen konnte G nichts (von zwei Prüfungen gemeldet) | hoch | Zur Gliederung machen ist ein Gliederungswechsel für alles darin: nur mit Verwalten an der bisherigen Gliederung (oben: Plattform-Verwaltung), sonst 403; „Ordner bearbeiten“ bietet die Art sonst nicht an. Gesperrte und Ausgesonderte mit Heimat darin ziehen in die neuen Systemordner (1.3). Tests `test_kein_abziehen`, `test_eine_heimat` |
| 2 | Freigaben-Dialog am Tablet hochkant (768–834 px): Die Tabelle mit sieben Spalten ragte aus dem Dialog, „Entziehen“ war abgeschnitten, der Dialog scrollte waagerecht | mittel | Karten bis 840 px Inhaltsbreite (Fenster bis etwa 920 px), Tabelle im vollen Dialog am Rechner; nachgemessen als Materialwart und Verwaltung bei 390–1280 px |
| 3 | Die Hilfe zur Notiz versprach „nicht die Person selbst“ – wer den Ordner mitverwaltet, liest aber die Notiz zu seiner eigenen Freigabe | mittel | So im Bauentwurf (1.6 Nr. 10: die Notiz sehen alle Verwalter des Ankers, nie „Meine Freigaben“); die Hilfe sagt das jetzt. Verbergen bei eigenen Zeilen: am 18.10.2026 verworfen (siehe „Vier weitere Punkte – entschieden“) |
| 4 | Eine schon erledigte Zeile im offenen Durchgang des alten Bereichs sperrte nach dem Verschieben jeden neuen Durchgang im Zielbereich (1.7 Nr. 6 verfehlt) | mittel | Die Konfliktabfrage beim Eröffnen lässt erledigte Zeilen außen vor, wie „Einbeziehen“ und der Prüfstart. Test `test_verschieben_und_durchgaenge` |
| 5 | `DELETE /meldungen/<id>` antwortete für jede vorhandene Meldung 403, auch ohne Modulzugang – so ließ sich erfragen, welche Kennungen es gibt | niedrig | 404 wie für eine unbekannte, wenn man die Meldung nicht sieht; 403 nur für sichtbare fremde. Tests `test_nichts_aus_b_paket_d`, `test_produktmeldung` |
| 6 | Nutzerverwaltung: Nach dem Entziehen einer Prüffreigabe schickte der Hinweis nach „Prüfungen → Entwürfe freigeben“ – das gibt es nicht | niedrig | bleibender Hinweis mit Link: Material → Prüfungen → „Offene Prüfungen“ freigeben |
| 7 | „Entziehen“ an der eigenen Verwalterfreigabe wurde angeboten, obwohl der Server sicher mit 409 ablehnte (1.6 Nr. 7) | niedrig | Feld `entziehbar` je Zeile, Nr. 7 vorab gerechnet; statt des Knopfs „Entziehen nur über die Plattform-Verwaltung – sonst verwaltet hier niemand so lange wie du.“ Test `test_uebernahme_schutz` |
| 8 | Die Freigabe eines Kontos ohne Namen (etwa aus der Migration) stand ohne jede Personenangabe in der Liste | niedrig | „(Konto ohne Namen)“, nie die E-Mail – auch bei „vergeben von“ und beim Verlängern. Test `test_listen_und_verlaengern` |
| 9 | Rückruf als Katalogpfleger ohne Bestand: „0 Artikel in deinem Bereich betroffen“ klang, als träfe er nichts; Tippfehler in Seriennummern blieben unbemerkt | niedrig | Datenregel 2.6 unverändert; ohne Bestand statt der Zahl „Wie viele Artikel betroffen sind, sehen die Materialwarte der Gliederungen.“, bei Seriennummern der Hinweis, dass nur die Plattform-Verwaltung Nummern ohne Treffer sieht. Seit der Modulstufe gegenstandslos: Rückrufe legt nur die Material-Verwaltung an, und die sieht alles |
| 10 | Eine eigene Freigabe, die länger lief als das eigene Verwalten, ließ sich weder verkürzen noch entziehen (1.6 Nr. 5) | niedrig | Grenze Nr. 4 („reicht weiter als deine eigene“) nur für fremde Zeilen; für eigene gelten Nr. 5 und Nr. 3. Test `test_eigene_laenger_als_verwalten` |
| 11 | Freigabenliste: eine Abfrage je Verlaufseintrag (bis 200) | niedrig | `journal.konto_namen` löst alle Kontoverweise mit einer Abfrage auf. Test `test_liste_abfragen` |
| 12 | DEMO-Skript: Herstell-, Erstgebrauchs- und Prüfdaten mit `date.today()` – im UTC-Container nachts einen Tag daneben | niedrig | `services.heute()` wie im übrigen Modul |

### Nachbesserungen nach der Auslieferung (Wünsche vom 18.10.2026)

- **Freigaben als Reiter in „Ordner bearbeiten“** (Wunsch: „Der Freigaben-Button soll verschwinden und das Menü in die
  Bearbeiten-Funktion der Ordner verschoben werden, ggf. mit Tab statt unten einfach drangehangen.“): Der Knopf
  „Freigaben“ im Ordnerkopf ist weg. „Bearbeiten“ öffnet einen Dialog mit zwei Reitern – **Ordner** (Name, Art,
  Prüfintervall, Beschreibung, Foto; rote Hauptaktion „Speichern“) und **Freigaben** (Vorlagen, „+ Freigabe“ mit der
  roten Hauptaktion „Freigabe erteilen“, Listen, „Alle Prüffreigaben verlängern bis …“, Verlauf; unten „Schließen“).
  Die Reiter sind Tabs nach WAI-ARIA (← und → wechseln, Pos1 und Ende springen), kleben beim Rollen oben, die
  Knopfzeile wie seit Lieferung 5 unten; der Dialog ist in beiden Reitern so breit wie früher der Freigaben-Dialog.
  Den Reiter gibt es genau dort, wo es „Bearbeiten“ gibt: Beides verlangt verwalten am Ordner, an Systemordnern gibt
  es keins von beiden – den Fall „darf Freigaben, aber nicht bearbeiten“ gibt es also nicht. Die Freigaben lädt der
  Reiter erst, wenn man ihn öffnet. Ändern, Entziehen und Verlängern öffnen wie bisher eigene Dialoge darüber; danach
  steht man wieder im Reiter „Freigaben“, und was im Reiter „Ordner“ eingetippt, aber nicht gespeichert ist, bleibt
  stehen. Wer den Dialog aus dem Reiter „Freigaben“ heraus verlässt („Schließen“, Esc, „Dort öffnen“), während im
  Reiter „Ordner“ noch Ungespeichertes steht, wird gefragt („Verwerfen“). Ein Foto, das man im Reiter „Freigaben“
  auf den Dialog zieht, nimmt der Dialog nicht (Hinweis). Alle Einstiege führen jetzt dorthin: nach „+ Gliederung“
  (`?freigaben=materialwart`), der Ablaufhinweis im Ordnerkopf mit „Verlängern …“ (er bleibt ein Hinweis am Ordner;
  läuft eine befristete Prüffreigabe ab, führt er zu „Alle Prüffreigaben verlängern bis …“, läuft nur anderes ab –
  etwa ein Grundrecht –, zur ersten ablaufenden Zeile mit ihrem „Ändern“; bis der Reiter geladen ist, steht der Fokus
  auf dem gewählten Reiter),
  „Dort öffnen“ an geerbten Zeilen und der Ordnerpfad einer Freigabe in der Nutzerverwaltung (`?freigaben`). „Meine
  Freigaben“ verlinkt wie bisher den Ordner selbst. Hat sich an den Freigaben etwas geändert, lädt der Ordner nach dem
  Schließen neu – über einen Rückruf aus `MatFreigaben`, nicht mehr über eine Klasse am gemeinsamen Dialogelement.
  Schnittstelle von `window.MatFreigaben`: `inhalt(element, ordner, optionen)` füllt den Reiter (optionen `vorlage`,
  `fokus`, `geaendert`, `dort`) statt `oeffnen(ordner, vorlage)`; `kopfhinweis(element, ordner, verlaengern)`.
  Hilfetexte und Meldungen sagen „Ordner → Bearbeiten → Freigaben“.
- **Prüfrecht nur für externe Prüfer befristet** (Wunsch zum Freigaben-Dialog mit der Vorlage „Prüfer“: „Prüfrecht
  soll nur für externe Prüfer befristet sein.“): Eine Prüffreigabe darf dauerhaft sein, wenn die Person am Anker oder
  darüber heute ein Grundrecht (lesen oder verwalten) hat – auch eins aus derselben Anfrage – oder Plattform-Verwaltung
  ist. Ohne Grundrecht, also beim externen Prüfer, bleibt es beim Enddatum (Pflicht, höchstens 24 Monate); dauerhaft
  antwortet dort 400 mit Klartext. Befristet höchstens 24 Monate gilt weiter für alle, dauerhaft vergibt weiter nur,
  wer selbst dauerhaft verwaltet (1.6 Nr. 3); Häkchen und Urkundennummer bleiben Pflicht.
  - **Schutz zur Laufzeit** (`services/rechte.py`): Eine dauerhafte Prüffreigabe wirkt nur, solange die Person an
    ihrem Anker oder darüber ein gültiges Grundrecht hat – dieselbe Frage wie beim Erteilen und in der Liste; ein
    Grundrecht nur weiter unten trägt sie nicht, auch nicht dort. Wird das Grundrecht entzogen, gekürzt oder läuft es
    ab, prüft die Person nicht mehr (auch keine Prüfsicht); so entsteht nie ein unbefristetes Prüfrecht ohne
    Grundrecht. Die Liste sagt dann „wirkt nicht – dauerhaft nur mit lesen oder verwalten“ (ebenso „Meine Freigaben“
    und die Nutzerverwaltung); wird das Grundrecht wieder erteilt, wirkt sie wieder. Die Rückfrage beim Entziehen eines
    Grundrechts, an dem eine dauerhafte Prüffreigabe hängt, und der Ändern-Dialog sagen das vorher („Daran hängt eine
    dauerhafte Prüffreigabe …“); offene Prüfungen, die die Person danach nicht fortsetzen kann, nennt das Entziehen
    jetzt auch beim Grundrecht.
  - **Reiter „Freigaben“**: Die Vorlagen „Prüfer“ („lesen und prüfen“) und „Materialwart und Prüfer“ („verwalten und
    prüfen“) wählen bei „Prüfen bis“ das neue Häkchen „dauerhaft“ vor (angeboten nur, wer selbst dauerhaft verwaltet).
    „Externer Prüfer“ verlangt ein Datum, „Einzeln“ bietet „dauerhaft“ nur mit gewähltem Grundrecht oder wenn die
    Person dort schon eins hat (die Plattform-Verwaltung hat es überall). Der Ändern-Dialog einer Prüffreigabe wechselt zwischen dauerhaft und Datum (gleiche
    Regeln). „Alle Prüffreigaben verlängern“ betrifft nur befristete; dauerhafte laufen nicht ab und zählen beim
    Ablaufhinweis nicht mit. Nebenbei behoben: Das Häkchen „dauerhaft“ beim Grundrecht blieb für befristete Verwalter
    sichtbar, obwohl der Dialog es verbergen wollte (`label.inline` schlug `hidden`).
  - **Schnittstelle**: `POST …/freigaben` nimmt `pruefen` (true: mit Prüffreigabe; `pruefen_bis` null oder leer heißt
    dann dauerhaft); ohne `pruefen` gilt wie bisher `pruefen_bis` (null: keine Prüffreigabe, "" jetzt: ohne Ende).
    `PUT /freigaben/<id>` nimmt `bis: null` auch für Prüffreigaben (nur mit Grundrecht); zur Prüffreigabe wird ein
    Grundrecht nur mit ausdrücklichem `bis`. Listeneinträge haben neu `grundrecht_dort` (Grundrecht am Anker oder
    darüber, auch in „Meine Freigaben“) und `traegt_pruefen` (an wie vielen dauerhaften Prüffreigaben ein Grundrecht
    allein hängt), die Liste hat `kette` (der Ordner und seine Oberordner). `DELETE` zählt `offene_entwuerfe` für jede
    Art. Die Personensuche `GET /nutzer` sagt je Konto neu `grundrecht_ueberall` (Plattform-Verwaltung).
  - **DEMO-Daten**: Der DEMO-Prüfer prüft dauerhaft, der externe DEMO-Prüfer befristet. Auf einer Datenbank, deren
    DEMO-Konten ein früherer Lauf angelegt hat (dev), stellt `material_demo.py --demo --konten` die befristete
    DEMO-Prüffreigabe des DEMO-Prüfers einmal auf dauerhaft – nur die eigene Zeile der Demodaten (Notiz „DEMO“, Journal
    „Demodaten“), wenn sie seitdem niemand geändert hat und er dort lesen hat; Journaleintrag unter „Demodaten“. Schritt
    9 fasst DEMO-Zeilen nicht an. **Auf dev nach dem Deploy einmal `material_demo.py --demo --konten` laufen lassen.**
- **Migration Schritt 9** (Schemaversion 9, beim Start, wiederholbar): SQLite entfernt ein CHECK nur mit einer neuen
  Tabelle – `mat_folder_grant` wird ohne „Prüfrechte nur befristet“ neu aufgebaut wie in Schritt 2 (Fremdschlüssel
  aus, neue Tabelle, alle Zeilen mit ihren Kennungen kopieren, alte löschen, umbenennen, `foreign_key_check`). Indizes
  (auch der Teil-Unique „ein Grundrecht“) und Trigger (keine Freigaben an Systemordnern, Datumsformat) entstehen danach
  Wort für Wort so, wie sie in `sqlite_master` standen; fehlt eine Zeile, bricht die Migration ab. Die Prüffreigaben,
  die Schritt 8 aus dem Häkchen „Prüfer“ gemacht hat, werden dauerhaft, wo das Konto am selben Anker ein Grundrecht
  hat oder Plattform-Verwaltung ist und niemand die Zeile seitdem geändert hat (kein `updated_at`, kein „geändert“ im
  Journal) – je Zeile ein Journaleintrag „Migration Schritt 9“ (Konto nur als Verweis, Grund „nur externe Prüfer
  befristet“). Externe Prüfer behalten ihr Ende. Schritt 8 legt sie für noch nicht migrierte Datenbanken (Produktion)
  gleich so an und baut die Tabelle dafür schon selbst um. Neue Datenbanken bekommen die Tabelle ohne das CHECK über
  denselben Weg – Schritt 1 bleibt, wie er ausgeliefert wurde. Rückweg: Eine Fassung bis Schritt 8 startet weiter auf
  der Datenbank, kennt aber den Schutz zur Laufzeit nicht – dort wirkte eine dauerhafte Prüffreigabe auch ohne
  Grundrecht. Vor einem Rückweg also dauerhafte Prüffreigaben ohne Grundrecht („wirkt nicht“) entziehen.
- **Geprüft**: Tests `test_dauerhaft_pruefen`, `test_migration_8_9`, `test_neue_datenbank_ohne_check` (dazu
  angepasst `test_migration_7_8` mit dem CHECK in der Ausgangstabelle und einem externen Prüfer) und die statische
  Prüfung der Reiter in `test_material_l5`. Schritt 9 an echtem Stand: eine Datenbank aus Phase 1 (Stand 7) mit der
  ausgelieferten Fassung auf Schritt 8 gebracht, DEMO-Daten mit Konten dazu, dann die neue Fassung gestartet –
  Schemaversion 9, alle 61 Tabellen mit gleicher Zeilenzahl (nur das Journal um die drei Umwandlungen länger), alle
  Kennungen gleich, Indizes und Trigger Wort für Wort gleich und wirksam, die Prüffreigaben aus Phase 1 mit Grundrecht
  bzw. Verwaltung dauerhaft, die des externen Prüfers und die der DEMO-Konten unverändert; ein zweiter Start ändert
  nichts. Im Chromium als DEMO-Materialwart A und als Plattform-Verwaltung bei 1280 × 900, 820 × 1180 und 390 × 844
  (Touch) der ganze Weg – Ordnerkopf, Reiter (auch per Tastatur), Vorlagen, Erteilen, Ändern, Entziehen, Verlängern,
  Kopfhinweis, „Dort öffnen“, „+ Gliederung“, Nutzerverwaltung – ohne Konsolenfehler und ohne waagerechten Überlauf.
- **Produktfoto beim Artikel anlegen groß** (Wunsch: „Bei Artikel anlegen die Möglichkeit, auf das Foto des Produkts
  zu klicken, dass es groß wird, um es besser zu erkennen.“): Das Foto des gewählten Produkts unter „Produkt aus dem
  Katalog“ öffnet beim Antippen die Großansicht des Moduls – dieselbe wie bei Produktbildern, Befund- und
  Meldungsfotos, mit der Webfassung statt der Vorschau und „Original“; ✕, Esc oder Wischen nach unten schließt, das
  Produkt bleibt gewählt. Ebenso die Fotos in der Trefferliste der Produktsuche (`produktTreffer`, damit auch in
  „Vorhandenem Produkt zuordnen“ bei den Meldungen): Bisher war die ganze Zeile ein Knopf, jetzt hat jeder Treffer
  zwei getrennte Flächen – links das Foto (öffnet groß, wählt nichts), durch einen Strich getrennt der Knopf mit dem
  Namen (wählt). Zeiger mit Lupe, eine kleine Lupe unten rechts am Foto als Hinweis auch am Telefon, Trefferfläche
  mindestens 46 px; aria-label „Produktfoto groß anzeigen: …“ mit dem Produktnamen, mit Tab erreichbar, Enter und –
  neu für alle Fotos des Moduls – die Leertaste öffnen. Ohne Produktbild steht dort nichts Anklickbares. Am Telefon
  rücken Artikelnummer und DEMO in den Treffern unter den Namen, statt ihn in eine schmale Spalte zu drücken. Geprüft:
  `test_produktfoto_gross_in_der_produktwahl` in `test_material_l5` (die Suche liefert Web-, Vorschau- und
  Originalfassung, ohne Bild keine; statische Haken) und im Chromium als DEMO-Materialwart A bei 1280 × 900 (Maus und
  Tastatur) und 390 × 844 (Touch): Foto in den Treffern und am gewählten Produkt groß, schließen, Produkt bleibt
  gewählt, ohne Bild nichts anklickbar; im Zuordnen-Dialog liegt die Großansicht über dem Dialog und Esc schließt nur
  sie; die Personensuche („Zuordnen …“ am Artikel) sieht aus wie bisher – ohne Konsolenfehler und ohne waagerechten
  Überlauf.
  Nachgebessert nach einer Browserprüfung: Am Telefon nutzte die Großansicht nur rund 70 % der Breite – 120 px blieben
  für Blätterpfeile frei, die dort (bis 640 px) unten stehen oder bei einem einzelnen Foto ganz fehlen. Jetzt reicht
  das Foto bis auf den Rand des Dialogs (24 px je Seite; gilt für alle Fotos des Moduls): bei 390 × 844 342 × 513 statt
  270 × 405, bei 360 × 740 312 × 468 statt 240 × 360. Damit es dabei nicht unter ✕ rutscht – so wäre es am iPhone SE
  (375 × 667 mit Statusleiste) und bei 320 × 568 gekommen –, hält der Dialog oben den Streifen von ✕ frei (60 px plus
  Kerbe), und wird es eng (hohes Foto, lange Unterschrift), wird das Foto im Seitenverhältnis kleiner, statt „Original“
  unten aus dem Bild zu schieben. Ab 641 px ändert sich nichts. Geprüft: statische Haken in
  `test_produktfoto_gross_in_der_produktwahl` und im Chromium (Touch) mit Produktfoto, einer Gruppe von drei
  Meldungsfotos und einem hohen Foto mit langer Unterschrift im Tastaturmodus bei 390 × 844 (auch mit Kerbe und
  Wischleiste), 360 × 740, 375 × 667 (auch mit Statusleiste), 320 × 568, 640/641 × 900, 700 × 1050, 568 × 320,
  844 × 390 und 1280 × 900 (Maus): Bild, ✕, Unterschrift mit „Original“ und die Pfeile überlappen nicht, „Original“
  bleibt sichtbar, kein waagerechter Überlauf, keine weißen Ränder; Antippen von Pfeil, Foto und ✕ wirkt wie
  bisher.

**Prüfung der Nachbesserung**: Zwei unabhängige Prüfungen – Rechte (mit Angriffsskript gegen den Testclient und an
DEMO-Datenbanken alter Stände) und Browser (Rundgang mit DEMO-Konten bei 390–1280 px) – haben sieben Befunde
gemeldet, zwei davon derselbe. Jeder ist vor der Behebung nachgestellt worden, alle sind behoben – Rechte- und
Datenfehler mit Regressionstest, die Oberfläche im Chromium nachgeprüft. Danach liefen alle Suiten grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Laufzeit und Liste widersprachen sich: Lag das Grundrecht nur noch an einem Unterordner, prüfte die Person dort mit der dauerhaften Prüffreigabe von oben weiter (Prüfung starten 201), Liste und „Meine Freigaben“ sagten „wirkt nicht“, die Rückfrage beim Entziehen des unteren Grundrechts warnte nicht | mittel | Eine Regel überall, die strengere der Schreibregel: Die Sicht fragt nach dem Grundrecht am Anker oder darüber (`unter(dauerhaft & grund)`), `Sicht.ende` nach dessen Ende. Regressionstest in `test_dauerhaft_pruefen` (oben entzogen, unten behalten: kein Prüfrecht, „wirkt nicht“, Prüfung starten 403) |
| 2 | Die Plattform-Verwaltung zählt im Dienst als Grundrecht, „Einzeln“ mit nur „prüfen“ bot ihr im Reiter aber kein „dauerhaft“ (Datum Pflicht) – von beiden Prüfungen gemeldet | niedrig | Die Personensuche sagt je Konto `grundrecht_ueberall`, der Reiter bietet damit „dauerhaft“ an; Test in `test_nutzersuche`, im Chromium als Plattform-Verwaltung (für sich selbst) und als Materialwart nachgeprüft, der externe Prüfer bekommt es weiter nicht |
| 3 | Auf einer DEMO-Datenbank von früher (dev) blieb die DEMO-Prüffreigabe des DEMO-Prüfers befristet, `--konten` meldete „unverändert“ | niedrig | `material_demo.py --demo --konten` stellt sie einmal auf dauerhaft (nur die unveränderte eigene Zeile der Demodaten, mit Grundrecht, Journal „Demodaten“); Test `test_demo_pruefer_von_frueher`. Auf dev nach dem Deploy einmal laufen lassen |
| 4 | „Daran hängt 2 dauerhafte Prüffreigaben … wirkt sie nicht mehr“ – Verb und Pronomen im Singular (Reiter und Nutzerverwaltung) | niedrig | Bei mehreren „Daran hängen n … wirken sie nicht mehr“; im Chromium an Ändern-Dialog und beiden Rückfragen nachgeprüft |
| 5 | „Verlängern …“ im Ordnerkopf führte ins Leere, wenn nur ein Grundrecht ablief, und der Fokus blieb auf dem nicht gewählten Reiter „Ordner“ | niedrig | Zur ersten ablaufenden Zeile (Abschnitt auf, Fokus auf „Ändern“), läuft eine befristete Prüffreigabe ab, wie bisher zum Knopf; Fokus beim Öffnen auf dem gewählten Reiter. Nachgeprüft bei 1280, 820 und 390 px |
| 6 | Die Phasenübersicht oben nannte noch den „Freigaben-Dialog“ | niedrig | Jetzt „Freigaben im Dialog „Ordner bearbeiten“ (Reiter)“ |

Zwei weitere Wünsche vom selben Tag – Modulstufe Material und Vorgabe für neue Konten – mit Migration Schritt 10
(Bauentwurf „Stufen Mitglied und Verwaltung“ vom 18.10.2026; seine offenen Fragen hat der Betreiber am selben Tag
entschieden bzw. nicht widersprochen):

- **Modulstufe Material** (Wunsch, wörtlich: „In der Verwaltung soll die Rollenvergabe Mitglied (sieht das Modul
  überhaupt und kann damit arbeiten), Produktkatalogpfleger/Verwaltung (Recht zusätzlich Produkte/Katalog zu
  verwalten, Zugriff auf alle Bestände im System, etc.) haben, um das Wording und die Ebenen gleich zu ziehen. Das soll
  separat vom Rechtekonzept der Gliederungen und ihren Ordnern sein. Die Gliederungsordner werden von Verwaltern
  initial angelegt und dann die ersten Personen hinzugefügt, die ihren Ordner dann weiter selbstständig verwalten.“):
  - **Die Stufe wirkt wieder** (`auth.stufe` liest `users.recht_material`; die Plattform-Verwaltung hat überall 2 – das
    Ableiten aus den Freigaben, `material_stufe_wirksam` und `freigaben.stufen_vormerken` sind entfallen, die Kopfleiste
    fragt keine Freigaben mehr ab). **Mitglied** = Modulzugang: Katalog, Suche, Profil, „Meine Freigaben“ – Bestand
    nur über Freigaben je Ordner. **Verwaltung** = **Material-Verwaltung**: alles, was im Modul bisher an der
    Plattform-Verwaltung hing (alle Bestände, `darf.alles`, Freigaben überall ohne die Grenzen 3–7 samt Notizen,
    Gliederungen anlegen, verschieben, löschen, Meldungen abarbeiten, Rückrufe anlegen und beenden mit vollen Zahlen),
    dazu die Katalogpflege (bisher Häkchen „Produktkatalogpfleger“, `mat_katalog` – wird nicht mehr gelesen und bleibt
    als Rückweg). Prüfen nie über die Stufe: Häkchen, Urkundennummer und Prüffreigabe – auch die Material-Verwaltung
    (sie kann sich die Prüffreigabe wie bisher die Plattform-Verwaltung selbst geben, dauerhaft auch ohne Zeile für
    lesen oder verwalten). Nutzer, Stufen, Häkchen, die Freigaben eines Kontos, die Löschfolgen und das Protokoll der
    globalen Suchen bleiben bei der Plattform-Verwaltung.
  - **Ohne Stufe wirkt nichts** (Modulzugang = Konto mit Namen, aktiv, Stufe ≥ 1): Jede Route des Moduls antwortet
    403 „… nicht freigeschaltet – das macht die Verwaltung in der Nutzerverwaltung.“, bevor sie nach dem Gegenstand
    fragt; die Sicht ist leer – auch wenn sie für ein anderes Konto gerechnet wird (Rückruf-Empfänger, Entziehen,
    Verlängern). Freigaben wirken nicht (Listen: „wirkt nicht – kein Zugang zum Modul Material“), das Häkchen „Prüfer“
    macht nicht qualifiziert, ein Verwalter ohne Stufe oder Namen zählt nicht als Verwalter (Regel 1.6 Nr. 7,
    Rückruf-Empfänger, „Verlängern kann …“). „Meine Freigaben“ antwortet weiter und nennt den Grund. Ausnahmen, weil
    es die eigenen Daten sind: die eigene Unterschrift lesen und entfernen, die eigene Meldung löschen (nicht lesen).
    Eine ruhende Freigabe eines solchen Kontos lässt sich kürzen, herabsetzen oder entziehen, aber nicht ausweiten.
  - **Nutzerverwaltung** (`api_admin.py`, `static/js/admin.js`, `templates/admin.html`): Material ist eine Auswahl wie
    die anderen Module („–“, „Mitglied“, „Verwaltung“, gleiche Hilfetexte); Verwaltung im Modul Verwaltung zieht
    Material mit, ihr Entzug lässt es stehen (wie bei den anderen Modulen). Unter der Auswahl: „Prüfer“ (gelb
    „Prüfer – Urkundennummer fehlt“), klein „n Freigaben“, gelb „wirkt nicht – kein Zugang“ (Häkchen oder Freigaben
    ohne Stufe) und „ohne Namen – kein Zugang“. „alles“, die Marke „Katalog“, das Häkchen „Produktkatalogpfleger“ und
    „Stufe aus Phase 1 – ohne Freigabe“ (`mat_stufe_alt`) sind weg. Setzt man im Dialog das Häkchen „Prüfer“, während
    Material auf „–“ steht, springt die Auswahl sichtbar auf „Mitglied“ (mit Hinweis, gespeichert erst mit
    „Speichern“); stellt man Material danach ausdrücklich auf „–“, bleiben Häkchen und Urkundennummer gespeichert,
    wirken aber nicht. Über den Freigaben eines Kontos ohne Stufe: „Diese Freigaben wirken nicht – das Konto hat keinen
    Zugang zum Modul Material.“ Stufe Mitglied oder Verwaltung (außer bei der Plattform-Verwaltung) und das Häkchen
    gibt es nur mit Namen (400 „Erst einen Namen eintragen – … Ohne Namen geht nur Material „–“.“); ein namenloses
    Konto von früher bleibt bearbeitbar (Stufe senken, Häkchen nehmen). `mat_katalog` in einer Anfrage: 400.
  - **Personensuche je Zweck** (`GET /nutzer?zweck=`): Für Freigaben (`freigabe`, Vorgabe) nur Konten mit Zugang zum
    Modul – erteilen an ein Konto ohne Stufe antwortet 409 mit Klartext („Dieses Konto hat keinen Zugang zum Modul
    Material – den gibt die Verwaltung in der Nutzerverwaltung.“); für die Personenzuordnung (`zuordnung`) alle aktiven
    Konten mit Namen. Die Suche dürfen Verwalter und die Material-Verwaltung.
  - **Listen der Freigaben** (Reiter, „Meine Freigaben“, Nutzerverwaltung): neues Feld `wirkt_nicht` mit dem Grund in
    fester Reihenfolge – „Konto deaktiviert“ › „Konto ohne Namen“ › „kein Zugang zum Modul Material“ › „Qualifikation
    fehlt“ › „dauerhaft nur mit lesen oder verwalten“ –, am Konto `zugang`; „Alle verlängern“ überspringt ein Konto
    ohne Zugang mit diesem Grund.
  - **Mails**: Neue Produktmeldungen und Rückrufe an Artikeln ohne wirksamen Verwalter gehen an die
    Material-Verwaltung (aktive Konten mit Namen und Stufe Verwaltung, ohne die Plattform-Verwaltung), an die
    Plattform-Verwaltung nur, wenn es keine Material-Verwaltung gibt.
  - **Profil**: Den Abschnitt „Unterschrift“ und das Hinterlegen bekommt, wer mit Zugang festschreibt oder aussondert
    (`rechte.darf_unterschreiben`) – auch der Materialwart mit Stufe Mitglied, der über seine Freigabe verwaltet. Bisher
    hing das an „Stufe 2“, die jetzt die Material-Verwaltung bedeutet; ohne die Änderung verlöre der Materialwart den
    Abschnitt. Ist eine Unterschrift hinterlegt, steht der Abschnitt auch ohne Zugang da – nur zum Entfernen.
  - **Texte**: „Material-Verwaltung“ statt „Plattform-Verwaltung“ und „(Produkt-)Katalogpfleger“, wo die Stufe
    Verwaltung gemeint ist – Meldungen des Servers, Hilfen, Rückfragen, Mails („Die Material-Verwaltung hat einen
    Rückruf … angelegt“). Das Journal zeigt `recht_material` als „kein Zugriff (0)“, „Mitglied (1)“, „Verwaltung (2)“
    – mit der Zahl, weil Einträge vor Schritt 10 die Stufen aus Phase 1 meinten.
  - **DEMO-Daten**: Die vier DEMO-Konten bekommen beim Anlegen die Stufe Mitglied, dazu `demo-mv@example.invalid`
    („DEMO-Material-Verwaltung“, Stufe Verwaltung, keine Plattform-Verwaltung, keine Freigaben). Vorhandene DEMO-Konten
    hebt Schritt 10 auf Mitglied; das neue Konto entsteht beim nächsten `material_demo.py --demo --konten`
    (**auf dev nach dem Deploy einmal laufen lassen**).
- **Vorgabe für neue Konten** (Wunsch, wörtlich: „Neue Konten sollen nun Zugriff Mitglied auf Material bekommen und
  nicht mehr automatisch Zugriff auf Spots und Wiki.“): Kontoanfrage und Nutzerverwaltung ohne Angabe geben Mitglied im
  Modul Material und sonst nichts (Spots, Wiki, Prüfungen, Verwaltung „–“; im Wiki gilt damit der Lesemodus). Die
  Vorgabe steht an einer Stelle (`auth.VORGABE_NEU`, auch für `api_admin.VORGABE`, in `admin.js` dieselbe). Der
  allererste Nutzer bekommt weiter überall Verwaltung; vorhandene Konten behalten ihre Stufen. Die Startseite führt ein
  neues Konto ins Modul Material (ein Konto ohne Namen in den Lesemodus des Wikis). Mit der Freigabe einer
  Kontoanfrage steht die Stufe im Journal des Moduls („rollen“, Grund „Kontoanfrage freigegeben“). In der Nutzerverwaltung braucht ein neues Konto damit einen Namen – oder Material „–“.
- **Migration Schritt 10** (Schemaversion 10, beim Start, wiederholbar, ohne neues Schema): `recht_material` := 2,
  wenn `mat_katalog = 1` oder Plattform-Verwaltung; sonst 1, wenn eine Stufe aus Phase 1 (`recht_material ≥ 1` – auch
  der Phase-1-Materialwart mit 2 wird **Mitglied**, er verwaltet weiter über seine Freigabe aus Schritt 8), irgendeine
  Freigabe (auch abgelaufen) oder das Häkchen „Prüfer“; sonst 0. Name, Aktivität und Status zählen nicht. Häkchen,
  Urkundennummern, Freigaben und `mat_katalog` bleiben. Je Konto mit geänderter Stufe oder aufgelöstem Katalog-Häkchen
  ein Journaleintrag „rollen“ am Konto (`user_name` „Migration Schritt 10“, das Konto im Inhalt nur als Verweis
  `{"ref": mat_ref}`, Grund „Modulstufe Material (Schritt 10)“); keiner für 2 → 2, 1 → 1, 0 → 0. Damit verliert
  niemand Zugang. **Rechteausweitung, gewollt:** Jeder bisherige Katalogpfleger wird Material-Verwaltung und sieht
  danach alle Bestände aller Gliederungen samt Prüfungen, Protokollen, Journal, zugeordneten Personen und den Notizen
  an Freigaben, vergibt jede Freigabe und legt Gliederungen an. Konten mit einer Stufe aus Phase 1 ohne wirksame
  Freigabe und solche mit nur abgelaufenen Freigaben bekommen den Zugang zurück (Katalog, Suche – keinen Bestand;
  für die abgelaufenen so entschieden am 18.10.2026, siehe Prüfung der Modulstufen Nr. 3). In
  der Produktion (ohne Modul) ändert Schritt 10 nichts: Die Plattform-Verwaltung hat 2, alle anderen 0. Rückweg: Eine
  Fassung bis Schritt 9 liest `recht_material` nicht und `mat_katalog` wieder – ohne Datenverlust. Eine Fassung aus
  Phase 1 deutete die Stufen um (bisherige Katalogpfleger wären dort Materialwarte, Phase-1-Materialwarte nur
  Führungskräfte) – nur auf dev denkbar.
- **Eigene Entscheidungen beim Bau**: Mail-Empfänger „Material-Verwaltung“ sind Konten mit Stufe Verwaltung **ohne**
  Plattform-Verwaltung (sonst bekäme die Plattform-Verwaltung, die immer Stufe 2 hat, die Fachmails stets mit). Das
  Journal von Schritt 10 schreibt nur geänderte Konten (nicht 1 → 1, obwohl die Stufe ab jetzt wirkt). Das Profil
  fragt für „Unterschrift“ die Sicht (wer irgendwo verwaltet) – die einzige Seite außerhalb des Moduls mit einer
  Abfrage auf Freigaben. `katalog_required` heißt jetzt `material_verwaltung_required` (der alte Name bleibt als
  Alias) und verlangt Zugang und Stufe Verwaltung – ein namenloses Konto pflegt den Katalog nicht mehr.
  `rechte.grundrecht_an` und die Listen zählen die Material-Verwaltung als „Grundrecht überall“ (dauerhafte
  Prüffreigabe ohne lesen oder verwalten), wie bisher die Plattform-Verwaltung. Schritt 8 liest `recht_material` als
  Stufe aus Phase 1 – er läuft nie nach Schritt 10.
- **Geprüft**: neue Datei `tests/test_material_stufen.py` – Migration 9 → 10 mit allen Fällen (Phase-1-Mitglied,
  Phase-1-Materialwart 2 → 1, Katalogpfleger mit Stufe 1 und 0, nur Häkchen, gültige und abgelaufene Freigabe,
  nichts, Plattform-Verwaltung mit 2 und 0, ohne Namen, deaktiviert, wartend; Journal, zweiter Start, direkter zweiter
  Aufruf), Produktion ohne Modul, ein Konto mit Verwalter- und Prüffreigabe, Häkchen und Urkunde, aber ohne Stufe
  gegen jede Route der `url_map` (403, nichts geändert), Mitglied und Material-Verwaltung ohne Plattform-Verwaltung
  (alles sehen, Katalog, Gliederung, erster Materialwart, Rückruf; prüfen nur mit Prüffreigabe), Häkchen ohne Stufe,
  Personensuche je Zweck, Verwalter ohne Stufe (Regel Nr. 7, Rückrufmail an die Material-Verwaltung), Mails zu
  Meldungen, Profil „Unterschrift“, Vorgabe neuer Konten (auch der allererste), Oberfläche der Nutzerverwaltung.
  Angepasst: `umgebung` (Materialwart Stufe 1 statt 2 – mit 2 wäre er Material-Verwaltung und die Trennungstests
  prüften nichts mehr –, „katalog“ ist Material-Verwaltung, `neues_konto(…, stufe=)` mit Vorgabe Mitglied),
  `test_rollen`, `test_nutzerverwaltung`, `test_list_users_abfragen`, `test_ablauf`, `test_abfragezahl` (Seiten außerhalb
  des Moduls: keine Abfrage auf `mat_folder_grant`), `test_migration_7_8` (bis Stand 9, dann Schritt 10),
  Rückruf- und Meldungstests, `test_smoke.test_rechte` (Vorgabe neuer Konten), `test_wiki_lesemodus` (Startseite mit
  Material). Migration an echtem Stand: Datenbank mit der Fassung 20085f1 (Stand 9) und ihren DEMO-Daten samt
  Konten angelegt, dazu ein Katalogpfleger, ein Phase-1-Mitglied, ein Phase-1-Materialwart (DEMO-Materialwart A mit
  2), ein Konto nur mit Häkchen und eins ohne alles; dann diese Fassung gestartet – Schemaversion 10, Stufen wie die
  Regel (Katalogpfleger 2, Phase-1-Materialwart 1, DEMO-Konten 1, Häkchen 1, ohne alles 0, Plattform-Verwaltung 2),
  sechs Journaleinträge, sonst nur `mat_meta` und zwei neue Kontoverweise anders, alle Zeilenzahlen gleich; ein zweiter
  Start ändert nichts; `--demo --konten` legt danach nur die DEMO-Material-Verwaltung an. Im Chromium bei 1280 und
  390 px: Nutzerverwaltung (Spalte, Marken, Häkchen-Automatik, neues Konto mit Vorgabe, ohne Namen der Klartext,
  Freigaben ohne Stufe im Dialog), das Modul als Mitglied ohne Freigabe, als Materialwart (Bestand, Profil mit
  „Unterschrift“) und als DEMO-Material-Verwaltung (Katalog mit Pflegeknöpfen, beide DEMO-Gliederungen, „+ Gliederung“
  mit dem ersten Materialwart im Reiter „Freigaben“; die Personensuche findet ein Konto ohne Stufe nicht) – keine
  Konsolenfehler, nichts rollt waagerecht.

- **Produktbeschreibung als Zusatz hinter dem Namen** (Wunsch, wörtlich: „Die Beschreibung eines Produkts soll direkt
  hinter den Namen, vor der Modellnummer auftauchen. Quasi wie der Text hinter dem Querbalken in den Beispielen. Mache
  außerdem das Feld für Beschreibungen in bearbeiten dialog genauso "klein" wie die anderen Felder, damit es nicht so
  aussieht, als soll ein ganzer text hinein. Gedacht ist hier nur weitere Infos, wie z.B. der Verschluss eines
  Karabiners o.Ä.“). Am Datenbestand ändert sich nichts – kein Schemaschritt, keine Umstellung von Beschreibungen oder
  Modellnamen. (Stand heute: Sichtbar heißt das Feld „Bemerkung“, die CSV-Spalte „Bemerkung (Produkt)“ – siehe
  „Bemerkung statt Beschreibung“ unten; dieser Eintrag beschreibt die Auslieferung mit dem alten Namen.)
  - **Anzeige** (Stand nach dem zweiten Wunsch, siehe „Ohne Strich, grau“ unten): Wo ein Produkt genannt wird, steht
    die Beschreibung direkt hinter dem Modell und vor der Artikelnummer, ohne Strich und grau wie die Artikelnummer in
    der Katalogliste – „**D Classic** Screwlock K496B“: der Name wie bisher hervorgehoben bzw. verlinkt, der Zusatz
    außerhalb davon. Eine Regel für alle Stellen: `modellTeile` und `produktZusatz` mit den Ausgaben `produktName`
    (Text), `nameHtml` und `zusatzHtml` (maskiert) in `material.js`, für `suche.js` und `global.js` als
    `window.MatProdukt`; auf dem Server `katalog.modell_teile`, `zusatz`, `produkt_teile` und `produktname` (PDF, CSV,
    Mails, Meldungen). Ohne Beschreibung nur der Name. Steht der Zusatz schon von Hand im Modellnamen („D Classic |
    Screwlock“, Beschreibung leer), zeigt die Anzeige den Teil vor dem Strich als Namen und den dahinter grau als
    Zusatz – genau wie bei einer Beschreibung; steht dieselbe Angabe in beiden, kommt sie nicht doppelt, zwei
    verschiedene stehen mit Komma („Screwlock, Aluminium“). Eine ältere, längere Beschreibung steht in einer Zeile,
    nach 80 Zeichen am Wortende mit „…“ gekürzt, der volle Text im `title`; die Produktseite zeigt sie zusätzlich ganz
    in den Stammdaten (mit Hinweis), eine kurze steht dort nicht noch einmal.
    Stellen: Katalogliste und Kategorieansicht, Produktseite (Überschrift), „Artikel anlegen“ (Produktsuche und gewählte
    Produktkarte) und „Vorhandenes zuordnen“, Artikelansicht (Produktzeile, Stammdaten), Artikellisten (Ordner,
    Prüfungen, Trefferliste), offene Prüfungen, Prüfdurchgang (auch Zeilen außerhalb des eigenen Bereichs), Prüfung
    starten, Prüfung und Festschreiben-Dialog, Rückruf-Kasten der Übersicht, Meldungen (Treffer, eingepflegtes
    Produkt), Suchvorschläge, globaler Steckbrief (neues Feld `beschreibung` – Katalogdaten, keine Prüfdaten; `FELDER`
    hat jetzt 16 Schlüssel), Titel „Variante von …“, Rückfragen, Hinweis „Schon vergeben“ zur Artikelnummer, „Produkt …
    (spezifisch)“ am Formular, Dubletten- und Artikelnummernfehler, Rückruf- und Meldungsmail. In den Suchvorschlägen
    darf die Produktzeile am Telefon zwei Zeilen haben – in einer fiele der Zusatz dort ganz weg.
  - **Feld im Dialog** (Anlegen, Bearbeiten, Variante, Produkt aus einer Meldung): einzeilig und halb breit wie die
    anderen, direkt unter Hersteller und Modell, daneben der Hilfetext „Kurzer Zusatz hinter dem Namen, z. B. die
    Verschlussart.“; höchstens **80 Zeichen**. Warum 80: so viel wie eine Artikelnummer – das reicht für zwei Angaben
    („Twistlock, Aluminium“) und passt mit dem Modell noch in eine Listenzeile, ein Absatz passt nicht hinein;
    Ausführliches gehört in ein Dokument am Produkt. Der Server prüft beim Speichern über die Oberfläche
    (`katalog.beschreibung`, für jede Anfrage, die `description` mitschickt): länger ist ein Fehler mit Klartext
    („… höchstens 80 Zeichen, hier sind es 175. Bitte kürzen; Ausführliches gehört in ein Dokument am Produkt.“),
    Zeilenumbrüche werden Leerzeichen. Eine Änderung, die die Beschreibung nicht nennt, lässt eine ältere stehen. **Nie still
    gekürzt**: Öffnet man ein Produkt mit einer älteren, längeren Beschreibung (bis dahin war das Feld mehrzeilig, bis
    4000 Zeichen), zeigt das Feld sie ganz – in einer Zeile – und darunter „Bitte kürzen“ mit dem bisherigen Text;
    gespeichert wird erst, wenn sie kürzer ist (auch die Oberfläche sagt es schon vor dem Senden).
  - **Katalogimport unverändert** (Format 1 und 2, also auch der Austausch dev → Produktion): Er übernimmt
    Beschreibungen wie bisher – mehrzeilig, bis 4000 Zeichen –, sonst scheiterte die Übernahme eines Katalogs, der
    noch Beschreibungen von vor der Grenze hat, als Ganzes (der Import ist ganz oder gar nicht). Kommt dabei eine
    längere neu herein, nennt der Bericht sie als Hinweis (kein Fehler); die Anzeige kürzt sie. Der Export bleibt, wie
    er ist.
  - **Suche**: Die Produktsuche (Katalog, „Artikel anlegen“, „Vorhandenes zuordnen“) findet auch über die Beschreibung,
    ganze und halbe Wörter, auch gemischt („Classic Screwlock“). Die Beschreibung steht nicht im Trigramm-Index, sie
    wird mit `LIKE` durchsucht – sie ist kurz, der Katalog hat Hunderte Produkte, und den Index umzubauen hieße einen
    Schemaschritt. Die Platzhalter der Suchfelder nennen sie.
  - **PDF und CSV**: Neue Prüf- und Aussonderungsprotokolle, Sammelprotokolle und der Lebenslauf nennen das Produkt
    mit der Beschreibung dahinter, grau und nicht fett (seit dem zweiten Wunsch ohne Strich; die Angabe „Modell“
    darunter bleibt das Modell ohne Zusatz) – Varianten unterscheiden sich oft nur im Verschluss, das hilft beim
    Erkennen. Festgeschriebene Protokolle bleiben, wie sie
    sind (es sind die abgelegten Dateien). Die CSV je Ordner hat eine eigene Spalte „Beschreibung“ hinter „Modell“,
    voll und ungekürzt – eine Datenausgabe, das Modell bleibt eigene Spalte; im `Verzeichnis.csv` des Protokoll-ZIP
    steht das Produkt mit Zusatz.
  - **DEMO-Daten**: Die DEMO-Produkte haben keine Beschreibung mehr – bis dahin „DEMO – nicht für echte Prüfungen“,
    als Zusatz stand das doppelt zur DEMO-Marke („DEMO Gurt A | DEMO – nicht für echte Prüfungen“). Ein neuer Lauf von
    `material_demo.py --demo` leert sie auch in einem älteren DEMO-Katalog (auf dev einmal laufen lassen); die
    DEMO-Gliederung behält den Hinweis.
  - **Geprüft**: neue Datei `tests/test_material_beschreibung.py` – Länge beim Speichern (81 abgewiesen, 80 und
    Zeilenumbrüche, ältere lange bleibt bei einer Änderung ohne sie und wird unverändert zurückgeschickt abgewiesen,
    Variante, Produkt aus Meldung), Import mit langer mehrzeiliger Beschreibung (Format 1, Wiederholung, Export und
    Import in eine zweite Instanz, unverändert, Hinweis im Bericht), die Regel (leer, Zusatz von Hand, nicht doppelt,
    Kürzen am Wortende), Server-Ausgaben (Artikellisten, Suche, offene Prüfungen, Prüfung, Prüfprotokoll und
    Lebenslauf per `pdftotext`, CSV, Artikelnummer-Hinweis), Suche über die Beschreibung mit und ohne Volltextindex,
    Oberfläche statisch (Grenze gleich, Feld, Hilfetext, Hinweis, keine eigene Verkettung mehr, Ladereihenfolge).
    Angepasst: `test_material_globalsuche` und `test_material_trennung` (16 Schlüssel im Steckbrief),
    `test_artikelnummer_eindeutig` (Name mit Zusatz), `test_betroffene_und_hinweise` (Produkt im Rückruf-Kasten mit
    `description`). Im Chromium bei 1280 × 900 und 390 × 844 (Touch) mit eigenem DATA_DIR (DEMO-Katalog, ein Produkt
    mit kurzer Beschreibung per Schnittstelle, eins mit langer mehrzeiliger per Katalogimport, eins mit dem Zusatz von
    Hand im Modellnamen): Katalogliste, Produktseite, Dialog (Feld so hoch wie Modell, Altbestand mit Hinweis,
    Speichern abgewiesen, nichts gekürzt), „Artikel anlegen“ (Suche „Screwlock“ findet über Beschreibung und
    Modellnamen), Artikelansicht, Trefferliste, Suchvorschläge, Prüfung, offene Prüfungen, Prüfdurchgang, Meldungen,
    Rückruf-Kasten, globaler Steckbrief, Prüfprotokoll-PDF (`pdftotext`: „DEMO-Hersteller DEMO D-Karabiner |
    Screwlock“) – keine Konsolenfehler, nichts rollt waagerecht.
  - **Prüfung der Nachbesserung**: Eine unabhängige Prüfung meldete drei Befunde (niedrig), jeder ist nachgestellt und
    behoben – am Telefon brach der Browser direkt hinter „|“ um, und das geschützte Leerzeichen stand im Link
    unterstrichen am Anfang der nächsten Zeile (damals hielt ein Wortverbinder U+2060 Strich und Zusatz zusammen; im
    Chromium bei 360, 390, 820 und 1280 px in Artikelansicht, Ordner, Katalog, Suchvorschlägen und Steckbrief
    nachgemessen – mit dem Strich ist er seit dem zweiten Wunsch fort), die DEMO-Produkte hießen „… | DEMO – nicht
    für echte Prüfungen“ (siehe DEMO-Daten), und
    Importbericht, Fehlerorte, Formularziel, Meldung „kein Prüfintervall mehr“ und der Journaleintrag „als Variante
    angelegt“ nannten Produkte ohne Zusatz, sodass zwei Varianten gleich lauteten (jetzt über `katalog.produktname`;
    Tests `test_bericht_und_journal_mit_zusatz` und `test_demo_ohne_beschreibung`, vorher rot).
  - **Ohne Strich, grau** (zweiter Wunsch vom 18.10.2026, wörtlich, zu einem Bildschirmfoto der Katalogliste mit
    „D Classic | Screwlock“ als rotem Link und grauem „K496B“: „Entferne den | und der Text der Beschreibung soll so
    wie der Produktschlüssel in grau sein.“): Der Strich ist überall fort. In der Oberfläche steht hinter dem Namen ein
    Leerzeichen und dann der Zusatz in derselben Gestaltung wie die Artikelnummer der Katalogliste – Klasse `muted`
    (grau, `var(--grau)`), normale Schrift, nicht fett, nicht unterstrichen –, außerhalb des roten Links bzw. der
    fetten Hervorhebung: „**D Classic** Screwlock K496B“. Dafür liefert `material.js` Name und Zusatz getrennt
    (`nameHtml` kommt in den Link oder in `<strong>`, `zusatzHtml` dahinter: ` <span class="muted mat-zusatz">…</span>`,
    bei einer gekürzten älteren Beschreibung mit `title`); `.mat-zusatz { font-weight: 400; }` hält ihn auch in der
    Überschrift der Produktseite und in der halbfetten Produktzeile des Steckbriefs dünn. Alle 16 Stellen in
    `material.js` (Katalogliste und Kategorieansicht, Produktseite, Treffer und gewählte Karte bei „Artikel anlegen“,
    „Vorhandenes zuordnen“, Artikelansicht mit Stammdaten, Artikellisten, offene Prüfungen, Prüfung starten, Prüfung,
    Festschreiben-Dialog, Meldungen, Rückruf-Kasten, seit der Prüfung unten auch der Hinweis „Schon vergeben“ zur
    Artikelnummer) und die Suchvorschläge (`suche.js`) und der globale Steckbrief
    (`global.js`) sind umgestellt; `produktHtml` gibt es nicht mehr. Der Wortverbinder hinter dem Strich ist mit ihm
    fort – zwischen Name und Zusatz darf die Zeile normal umbrechen. In den PDFs (Prüf- und Aussonderungsprotokoll,
    Lebenslauf mit Kopfzeile, Sammelprotokoll) setzt das Makro `produkt_mit_zusatz` (`pdf/basis.html`) den Zusatz grau
    wie die Kategorie darunter und nicht fett; das Feld „Modell“ nennt das Modell ohne Zusatz, bei einem Zusatz von
    Hand also den Teil vor dem Strich. **Reiner Text** (Rückfragen, Dialogtitel, Alternativtexte, Fehlermeldungen,
    Mails, `Verzeichnis.csv` im Protokoll-ZIP, Journal, Importbericht, Feld `name` in `GET
    /api/material/produkte/artikelnummer` und in der Prüfung): Name und Zusatz durch ein Leerzeichen getrennt –
    „Hersteller D Classic Screwlock“. Warum kein Komma: Der Zusatz ist gewollt kurz (höchstens 80 Zeichen, meist ein Wort
    wie die Verschlussart) und liest sich mit dem Namen wie die Handelsbezeichnung; der Text ist damit genau das, was
    auf dem Bildschirm steht (nur ohne Grau) und was man von dort kopiert. Ein Komma stünde zudem doppelt, wo der
    Zusatz selbst eins hat („Twistlock, Aluminium“) oder in einer Aufzählung mehrerer Produkte. Die CSV je Ordner bleibt
    eine Datenausgabe: Spalten „Modell“ und „Beschreibung“ so, wie sie gepflegt sind (ein Zusatz von Hand steht dort
    also weiter mit Strich im Modell). Katalogdaten ändern sich nicht. Geprüft: `test_material_beschreibung` neu bzw.
    angepasst – Regel ohne Strich (Text, getrennte Teile, Zusatz von Hand, nicht doppelt, Komma, Kürzen nur der
    Beschreibung), Protokoll und Lebenslauf über das gesetzte HTML (grauer Zusatz, Feld „Modell“, Zusatz von Hand) und
    `pdftotext`, Oberfläche statisch (jede der 16 Stellen setzt `zusatzHtml` hinter den Schluss von Link und `<strong>`,
    Klasse `muted`, nie fett, kein Strich, PDF-Makro an allen drei Stellen), dazu `test_regel_gleich_in_material_js`:
    die Regel aus `material.js` mit Node.js gegen den Server für 15 Fälle (läuft, wenn Node.js da ist);
    `test_artikelnummer_eindeutig` angepasst. Im Chromium bei 1280 × 900 und 390 × 844 (Touch) mit eigenem DATA_DIR
    (`material_demo.py --demo --konten`, dazu per Schnittstelle „DEMO D Classic“ mit Beschreibung „Screwlock“ und
    Produktbild und „Platzhalter | Twistlock“ ohne Beschreibung): Katalogliste wie im Bildschirmfoto, Produktseite,
    „Artikel anlegen“ (Treffer, gewählte Karte), Artikelansicht mit Stammdaten, Ordnerliste, Suchvorschläge, Prüfung,
    Prüfung starten, offene Prüfungen und – als Materialwart der anderen Gliederung – der globale Steckbrief: Zusatz da,
    grau wie die Artikelnummer, Schriftgewicht 400, außerhalb von Link und `<strong>`, kein „|“, keine
    Konsolenfehler, nichts rollt waagerecht (332 Prüfungen, alle erfüllt). Prüfprotokoll, Lebenslauf und
    Sammelprotokoll per `pdftotext`: „DEMO-Hersteller DEMO D Classic Screwlock“, „DEMO-Hersteller Platzhalter
    Twistlock“, Feld „Modell“ „Platzhalter“; `Verzeichnis.csv` ebenso ohne Strich.
  - **Prüfung von „Ohne Strich, grau“**: Eine unabhängige Prüfung meldete zwei Befunde (niedrig); beide sind im
    Chromium bei 1280 × 900 und 390 × 844 (Touch) nachgestellt und behoben. (1) Der Hinweis „Schon vergeben“ beim
    Tippen der Artikelnummer (Dialog „+ Produkt“ bzw. „Produkt bearbeiten“ und „Fehlendes Produkt melden“) setzte noch
    Name und Zusatz zusammen in den roten, fetten, unterstrichenen Link – „DEMO-Hersteller DEMO Altname Twistlock“ –,
    als einzige Stelle der Oberfläche. Jetzt liefert `GET /api/material/produkte/artikelnummer` neben `name` auch
    `manufacturer`, `model` und `description` (wie gepflegt, ein Zusatz von Hand also mit Strich im Modell – zerlegt
    wird erst in der Anzeige), und die Zeile lautet wie überall `nameHtml` im Link, `zusatzHtml` grau dahinter:
    „Schon vergeben: **DEMO-Hersteller DEMO Altname** Twistlock (DEMO-K-ALT1)“; Zusatz `rgb(109, 109, 108)`,
    Schriftgewicht 400, nicht unterstrichen, außerhalb des Links, Maskierung unverändert. (2) Im Rückruf-Kasten der
    Übersicht (hellroter Grund `--rot-hell`) hatte der graue Zusatz nur 4,48:1 – knapp unter 4,5:1 (WCAG AA) für
    normale Schrift; auf weißem Grund sind es 5,18:1. Dort ist er jetzt ein Viertel zum Textgrau hin abgedunkelt
    (`.mat-rr-kasten .mat-zusatz { color: color-mix(in srgb, var(--grau) 75%, var(--anthrazit)); }`): gemessen 4,86:1,
    weiter grau und heller als der Text daneben; ein Browser ohne `color-mix()` erbt das Textgrau
    (`--anthrazit`, 80 % Schwarz). Katalogdaten unverändert. Tests in `test_material_beschreibung` erweitert (Teile in
    der Schnittstelle, auch mit Zusatz von Hand; 16 Stellen; Regel für den Kasten), mit dem alten Stand rot.
- **Bemerkung statt Beschreibung** (Antwort auf die Rückfrage „80 Zeichen und CSV-Spalte“, wörtlich: „Grundsätzlich
  bestätigt. Benenne ‚Beschreibung‘ in Bemerkung um.“): Das Produktfeld (der Zusatz hinter dem Namen) heißt überall,
  wo man es sieht, **Bemerkung** – Feld und Hinweis „Bitte kürzen“ im Produktdialog (auch Variante und Produkt aus
  Meldung), Fehlermeldungen von Oberfläche und Server, Zeile auf der Produktseite, Platzhalter der Produktsuche,
  Importbericht und Journal am Produkt. **Eindeutig gemacht:** die CSV-Spalte hinter „Modell“ heißt „Bemerkung
  (Produkt)“, weil weiter hinten seit Lieferung 4 die „Bemerkung“ des Artikels steht (die bleibt, damit Auswertungen
  über den Spaltennamen weiter laufen); im Dialog „Produkt aus Meldung anlegen“ heißt die Bemerkung der Meldung im
  Kasten oben „Bemerkung des Melders“. **Bewusst geblieben:** der Schlüssel `beschreibung` im Katalogformat 1 und 2
  (vorhandene Katalog-ZIPs bleiben lesbar, der Export schreibt ihn weiter) – der Import nimmt `bemerkung` gleichwertig
  an, beide mit verschiedenen Werten sind ein Fehler; Spalte `description`, Schnittstelle, Namen im Code; die
  Beschreibung von Ordnern und Rückrufen. In „Artikel anlegen“ nennt der Platzhalter der Produktsuche unter „Produkt
  aus dem Katalog“ die Bemerkung des Produkts, weiter unten steht das eigene Feld „Bemerkung“ des Artikels – ohne
  Zusatz, weil der Platzhalter sichtbar zur Produktsuche gehört, beim Tippen verschwindet und die Umbenennung auch
  für die Suchfelder gilt. Kein Schemaschritt, Katalogdaten unverändert. Geprüft:
  `test_bemerkung_heisst_so` (neu, gegen den alten Stand rot) und die angepassten Tests in
  `test_material_beschreibung`; im Chromium bei 1280 × 900 und 390 × 844 (Touch) mit DEMO-Daten (Dialoge, Meldung bei
  81 Zeichen, Altbemerkung, Produktseite, Suchfelder, CSV-Köpfe) – keine Konsolenfehler, nichts rollt waagerecht.
- **Bremse der globalen Suche entfernt** (Wunsch, wörtlich: „Entferne die Bremse komplett“ – auf den Hinweis, dass seit
  dem immer angebotenen Angebot auch Suchen nach eigenen Nummern gegen die Grenze von zehn Suchen je 15 Minuten
  zählen): Globale Suche, QR-Steckbrief und fremde Dublette beim Anlegen zählen nicht mehr – kein 429, keine Meldung
  „Zu viele Suchen außerhalb deines Bereichs …“. Die Kontrolle ist das Protokoll mit Namen. Es bleibt alles andere:
  die ausdrückliche Bestätigung (`bestaetigt: true`, Rückfrage „Außerhalb deines Bereichs suchen“), jede Suche, jeder
  Steckbrief und jede fremde Dublette im Protokoll (`mat_global_search`, zwölf Monate, „Globale Suchen (Modul
  Material)“ in der Nutzerverwaltung), die Eingaberegeln (4 bis 80 Zeichen, keine Inventar- und STR-Nummern), nur
  fremde Treffer und höchstens zehn Treffer je Suche mit „mehr“.
  - **Code**: `globalprotokoll.bremse`, `GRENZE`, `ZU_VIELE` und der Bereich `mat-global:<Konto>` in `login_attempts`
    sind fort, ebenso die Aufrufe in `globalsuche.suchen`, `globalsuche.steckbrief_qr` und `routes._fremde_dublette`;
    die beiden Dienste brauchen das Konto nicht mehr. Kopf- und Hilfetexte (`globalprotokoll.py`, `globalsuche.py`,
    `routes_global.py`, `global.js`, `suche.js`, `material.js`, README) nennen keine Bremse mehr. Unberührt bleiben die
    Anmeldebremse (`login_attempts` für Anmeldung, „Passwort vergessen“ und Kontoanfrage) und die Bremse der
    öffentlichen Prüfseite.
  - **Alte Zeilen `mat-global:…`**: kein eigener Aufräumschritt und kein Schemaschritt. Jede Prüfung der
    Anmeldebremse (`auth.attempts_exceeded` – bei jeder Anmeldung, „Passwort vergessen“, Kontoanfrage und Prüfseite)
    löscht alle Zeilen in `login_attempts`, die älter als 15 Minuten sind, gleich welcher Bereich; gelesen werden die
    alten Zeilen nicht mehr. Sie verfallen also von selbst.
  - **Geprüft**: `test_keine_bremse` (zwölf Suchen nach einer fremden und zwölf nach einer eigenen Seriennummer und
    zwölf QR-Steckbriefe hintereinander – alle 200, alle 36 mit Namen im Protokoll und in der Ansicht der Verwaltung,
    keine Zeile `mat-global:…`; die Anmeldebremse daneben weiter 429 nach zehn Fehlversuchen) und
    `test_dublette_ohne_bremse` (zwölf Suchen und zwölf fremde Dubletten im Wechsel, alle im Protokoll) ersetzen
    `test_bremse` und `test_bremse_mit_dublette` – gegen den alten Stand beide rot. `test_dublette` und `test_unterbau`
    in `test_material_trennung.py` ohne Bremse; der Test der Anmeldebremse in `test_smoke.py` ist unverändert grün.
    Im Chromium (eigenes DATA_DIR, `material_demo.py --demo --konten`) bei 1280 × 900 und 390 × 844 (Touch): Als
    DEMO-Materialwart A je Bildschirm zwölfmal hintereinander nach `DEMO-NS-4711` gesucht (1280: achtmal auf der
    Trefferseite, viermal in den Vorschlägen; 390: je sechsmal) und je einen QR-Steckbrief geöffnet – jedes Mal die
    Rückfrage und der Steckbrief, nie eine Sperrmeldung, in keinem Text „Viertelstunde“ oder „zu viele“, keine
    Konsolenfehler, nichts rollt waagerecht. Das Protokoll in der Nutzerverwaltung zeigt alle 26 Zeilen (24 Suchen,
    2 QR-Steckbriefe) mit Namen; das Serverprotokoll hat keine einzige 429.
- **„kritisch“ als eigene Spalte im Prüfprotokoll** (Wunsch vom 19.10.2026, wörtlich: „Das Kritisch soll auch in den
  PDFs eine eigene Spalte erhalten.“): In der Befundtabelle des Prüfprotokolls steht „kritisch“ jetzt wie in der
  Oberfläche (seit der Nachbesserung zu Lieferung 3) in einer eigenen schmalen Spalte rechts neben dem Prüfpunkt; die
  Marke hinter dem Text des Prüfpunkts entfällt. Kopf „kritisch“ wie die übrigen Spaltenköpfe, in der Zelle die Marke
  klein geschrieben wie in der Oberfläche (DLRG Univers fett, 6 pt, dunkelrot mit Rahmen – auch schwarz-weiß gedruckt
  erkennbar); bei nicht kritischen Punkten bleibt die Zelle leer. Die Spalte steht immer da, auch wenn kein Punkt
  kritisch ist – wie in der Oberfläche. Breiten (A4 hoch, 180 mm): Nr. 10 mm, Prüfpunkt 70 mm, kritisch 13 mm, Soll
  14 mm, Befund 27 mm (fasst „nicht zutreffend“ weiter in einer Zeile), Wert / Bemerkung 46 mm – vorher Prüfpunkt
  79 mm, Befund 29 mm, Wert / Bemerkung 48 mm, und die Marke nahm einem kritischen Prüfpunkt gut 12 mm seiner letzten
  Zeile. Gruppenzeilen gehen über alle sechs Spalten, der Tabellenkopf wiederholt sich auf jeder Seite wie bisher. Die
  Legende unter der Tabelle zeigt die Marke als Muster wie die rote Nummer: „[Nr.] Mangel · [kritisch] Ein kritischer
  Punkt mit Mangel schließt „einsatzbereit“ aus.“ (der Satz wie im Prüfformular der Oberfläche; vorher „KRITISCH: …“).
  Prüfpunkte hat nur das Prüfprotokoll (auch als Berichtigung) – Aussonderungsprotokoll, Sammelprotokoll und
  Lebenslauf zeigen keine und sind unverändert. Die neue Gestaltung gilt für neu erzeugte Protokolle; festgeschriebene
  bleiben Byte für Byte, wie sie sind. Kein Schemaschritt.
  - **Geprüft**: `test_kritisch_eigene_spalte` (neu) am HTML der Vorlage – sechs Spalten, Köpfe, Gruppenzeilen über
    sechs Spalten, die Marke nur in der Spalte und nie im Text des Prüfpunkts, nicht kritische Zellen leer, Legende –
    und am PDF mit `pdftotext -layout`: Kopf zwischen „Prüfpunkt“ und „Soll“, Zeilen mit und ohne Marke, Mangel am
    kritischen Punkt, langer Prüfpunkt, 45 Punkte in zwei Gruppen über mehrere Seiten mit wiederholtem Kopf.
    `test_festschreiben` prüft die Spalte zusätzlich am ersten Protokoll. Beide gegen den alten Stand rot.
    DEMO-Nachweis mit eigenem DATA_DIR (`material_demo.py --demo --konten`, dazu ein DEMO-Formular mit 36
    Platzhalter-Punkten in drei Gruppen für den DEMO HMS-Karabiner): Prüfung mit Mangel an einem kritischen (langer
    Platzhaltertext) und an einem nicht kritischen Punkt und einem Punkt „nicht zutreffend“, Ergebnis „aussondern“
    (Prüfprotokoll mit Befundtabelle über drei Seiten, Aussonderungsprotokoll), eine zweite Prüfung ohne Mangel, der
    Durchgang abgeschlossen (Sammelprotokoll). Seitenbilder angesehen, auch in Graustufen. veraPDF: alle zehn neu
    erzeugten Protokolle PDF/A-3b gültig; eingebettet nur DLRG Univers (normal und fett) und DejaVu Sans Mono normal
    und fett (Stempel, Protokoll-ID). Stempel auf jeder Seite, `head -c N | sha256sum` gleich dem aufgedruckten Wert,
    die Prüfseite sagt „unverändert“, mit einem geänderten Byte „verändert“.
  - **Prüfung der Änderung**: Eine unabhängige Prüfung meldete drei Befunde (niedrig), jeder ist nachgestellt. Behoben:
    Die Unterschrift eines Unterschriftsfelds behielt ihre feste Höchstbreite von 48 mm und ragte in der schmaleren
    Spalte „Wert / Bemerkung“ (46 mm, davon 43 mm Inhalt) rund 3 mm über den rechten Tabellenrand – rund 1 mm schon
    vorher. Sie ist jetzt höchstens so breit wie der Inhalt der Spalte (`max-width: 100%`) und endet bei 193,5 mm,
    innerhalb der Tabelle (195 mm); die Höhe bleibt auf 14 mm begrenzt. `test_unterschriftsfeld` prüft das mit einem
    sehr breiten Strich an der Lage des Bilds im PDF (gegen den alten Stand rot); bei 600 dpi an neu erzeugten
    DEMO-Protokollen nachgemessen. Behoben: Die Angabe der eingebetteten Schriften oben nannte DejaVu Sans Mono fett
    (Protokoll-ID im Kopf) nicht. Ein Zeichen, das DLRG Univers nicht hat (etwa „≤“ in einem Soll), setzt WeasyPrint
    wie bisher in DejaVu Sans, das dann ebenfalls eingebettet ist. Ebenfalls behoben (schon vor dieser Änderung so,
    die neue Spalte verschob nur die Seitenumbrüche): Fiel die Bemerkung zum Ergebnis an ein Seitenende, konnte ihre
    Beschriftung „Bemerkung“ allein unten stehen und der Text auf der nächsten Seite. `.bemerkung` hat jetzt
    `break-inside: avoid` (gilt auch für „Folge“); an den nachgestellten DEMO-Protokollen neu gerendert stehen
    Beschriftung und Text zusammen, veraPDF: PDF/A-3b gültig.

#### Prüfung der Modulstufen

Zwei unabhängige Prüfungen (Rechte mit Angriffsskripten gegen eigene Datenbanken, Oberfläche im Chromium je Rolle bei
1280, 820 und 390 px) fanden elf Befunde, keinen hohen. Neun sind behoben, je mit eigenem Commit; Rechtefehler mit
Regressionstest in `tests/test_material_stufen.py` (vorher rot, jetzt grün), Oberflächen im Chromium nachgeprüft.

| Nr. | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Eine ruhende Freigabe eines Kontos ohne Stufe ließ sich per `PUT /freigaben/<id>` hochstufen (lesen → verwalten) oder verlängern, obwohl Erteilen an dasselbe Konto 409 gab – mit der Stufe Mitglied wäre es sofort Verwalter gewesen | niedrig | Behoben: Regel 1.6 Nr. 12 auch beim Ändern – reicht die Zeile danach weiter (anderes Recht als verwalten → lesen, späteres Ende), 409 „Dieses Konto hat keinen Zugang …“, auch für die Material-Verwaltung; kürzen, herabsetzen, Notiz und entziehen gehen weiter (`freigaben._reicht_weiter`). Test `test_ruhende_freigabe_nicht_hochstufen` |
| 2 | Ein Konto ohne Stufe konnte seine hinterlegte Unterschrift nicht mehr entfernen (Abschnitt weg, `DELETE /unterschrift` 403), obwohl das Profil es versprach | niedrig | Behoben: `GET` und `DELETE /unterschrift` brauchen nur die Anmeldung (die eigenen Daten); ist eine Unterschrift hinterlegt, zeigt das Profil den Abschnitt auch ohne Zugang – nur mit „Entfernen“, ohne Urkundennummer. `PUT` bleibt bei Zugang und Prüfer/Materialwart. Test `test_haekchen_ohne_stufe`, Chromium 1280/390 |
| 3 | Schritt 10 gibt Konten, die nur abgelaufene Freigaben haben, die Stufe Mitglied – mit 20085f1 hatten sie keinen Zugang (Katalog, Suche, globale Suche) | niedrig | **Nicht geändert – so entschieden am 18.10.2026** (siehe „Vier weitere Punkte – entschieden“). Gründe für die Regel: Bis 20085f1 brachte das Verlängern einer abgelaufenen Freigabe durch den Verwalter des Ordners den Zugang zurück – mit Stufe 0 überspränge „Alle verlängern“ diese Konten, und erteilen ginge nicht mehr (409), der Verwalter bräuchte dafür die Plattform-Verwaltung; „Mitglied“ ist ohnehin die Vorgabe jedes neuen Kontos und zeigt keinen Bestand. Verworfene Alternative (nur erhalten, was am Tag der Migration wirkte): in `STUFE_10` nur gültige Freigaben zählen (`valid_until IS NULL OR valid_until >= heute`) und im Test den Fall „abgelaufen“ auf 0 setzen |
| 4 | Ein Melder ohne Stufe las seine Meldung weiter (Hersteller, Modell, Gliederung, Antwort, Produkt aus dem Katalog) und konnte sie löschen | niedrig | Behoben: Lesen nur mit Zugang (`GET /meldungen/<id>` 403 vor der Frage nach der Meldung, `darf_meldung` und Listenfilter mit `zugang()`, Meldungsfotos ebenso). Die eigene Meldung **löschen** darf der Melder weiter auch ohne Stufe – es sind seine Angaben (wie die Unterschrift); eine fremde antwortet wie eine unbekannte. Test `test_meldung_ohne_stufe` |
| 5, 7 | Kontoanfrage und Freigabe gaben Material „Mitglied“ ohne Journaleintrag „rollen“ – beim Anlegen in der Nutzerverwaltung steht er da, und die Kontoanfrage ist seit der neuen Vorgabe der häufigste Weg ins Modul (zweimal gemeldet) | mittel | Behoben: Die Freigabe einer Kontoanfrage schreibt in derselben Transaktion „rollen“ am Konto (vorher –, nachher `recht_material`, `mat_pruefer`, Grund „Kontoanfrage freigegeben“), Handelnde ist die freigebende Plattform-Verwaltung. Erst bei der Freigabe, weil die Stufe erst dann wirkt – abgelehnte Anfragen hinterlassen nichts; ohne Stufe und Häkchen kein Eintrag. Der allererste Nutzer (überall Verwaltung) bleibt ohne Eintrag. Test `test_vorgabe_neue_konten`, Chromium 820 |
| 6 | Ein Konto ohne Namen und ohne Stufe bekam nur den Hinweis auf den Namen – mit Namen dann „nicht freigeschaltet“, also zwei Runden | niedrig | Behoben: `zugang_meldung` fragt zuerst die Stufe, den Namen nur bei vorhandener Stufe. Test `test_migration_9_10` |
| 8 | Dialog „Bearbeiten“: Häkchen „Prüfer“ gesetzt, während die Verwaltung auf „Verwaltung“ stand – nach dem Zurückstellen Material „–“ mit Häkchen, ohne den zugesagten Sprung auf „Mitglied“; umgekehrt blieb der Hinweis zum Sprung neben „Verwaltung (aus)“ stehen | niedrig | Behoben (`admin.js`): Das überdeckt gesetzte Häkchen hebt beim Zurückstellen, falls Material dann auf „–“ stünde (mit Hinweis); ein von Hand gewähltes „–“ bleibt auch über ein Hin und Her der Verwaltung; der Hinweis steht nur, solange Material nicht überdeckt ist. Im Chromium bei 1280 und 390 px vier Abläufe nachgeprüft |
| 9 | Ein namenloses Konto mit Stufe (gibt es nach Schritt 10) sah „Material“ in der Kopfleiste, und die Startseite leitete es auf die 403-Seite des Moduls | niedrig | Behoben: Startseite und Kopfleiste fragen für Material `rechte.zugang` (Stufe und Name, ohne Abfrage) – ohne Namen in den Lesemodus des Wikis, der Reiter erst mit Namen; `/material` sagt weiter, was fehlt. Test `test_namenlos_startseite`, Chromium 1280/390 |
| 10 | Kontoanfrage: Konsolenfehler `TypeError … setting 'disabled'` in `auth.js` nach dem Erfolg (vorbestehend) | niedrig | Behoben: `busy()` prüft, ob es den Absendeknopf noch gibt (die Antwort ersetzt das Formular). Chromium 390 px: vorher die Ausnahme, jetzt keine |
| 11 | Zeilenknöpfe der Nutzerverwaltung („Bearbeiten“, „Reset-Mail“, „Löschen“) sind `btn ghost` (vorbestehend) | niedrig | **Nicht geändert**: Die Knopfsprache (grau umrandet als Standard, kein `ghost`) hat der Betreiber für das Modul Material festgelegt; die Nutzerverwaltung gehört zur Plattform, wo Wiki, Spots und Prüfungen `ghost` durchgängig nutzen. Eine Umstellung nur hier wäre eine eigene Gestaltungsentscheidung – auf Wunsch gern für die ganze Plattform |

### Zu prüfen

- **Leistung mit vielen Ordnern**: Die Sicht eines Kontos wird je Anfrage einmal gerechnet – eine Abfrage der eigenen
  Freigaben, gibt es welche, dazu eine des ganzen Ordnerbaums –, die Filter setzen die Ordnerkennungen als Liste ein.
  Gemessen ist nur die Zahl der Abfragen (Kopfleiste seit der Modulstufe ohne jede Abfrage auf Freigaben; im Modul
  die Sicht einmal je Anfrage), nicht die Laufzeit mit echten Beständen mehrerer Gliederungen.
- **Inventar- und Protokollnummern verraten die Gesamtzahl**: `M-000123` und `P-2026-000123` sind plattformweit
  fortlaufend; wer zwei eigene Nummern vergleicht, sieht grob, wie viel es insgesamt gibt. Hingenommen – das Konzept
  verlangt eineindeutige Nummern; eine Nummer je Gliederung wäre ein Umbau der Etiketten.
- **Pfadnamen in verschobenen Artikeln**: Im Journal eines Artikels aus einer anderen Gliederung, in seinen
  festgeschriebenen Protokollen und in Titel und Ordner alter Durchgänge stehen Ordnernamen der alten Gliederung – sie
  gehören zur Geschichte des Artikels. Bestätigt am 19.10.2026.
- **Telefon und Tablet**: Reiter „Freigaben“ in „Ordner bearbeiten“ (Vorlagen, Karten, Verlängern) und Zuordnen
  (Personensuche, Sammelaktion) auf dem Telefon durchgehen. Am Tablet hochkant und quer (bis etwa 920 px) sind die
  Freigabenlisten jetzt Karten – im Browser nachgemessen, auf einem echten Gerät noch nicht gesehen.
- **Erledigte Zeilen und neue Durchgänge**: Eine schon erledigte Zeile eines offenen Durchgangs sperrt keinen neuen
  mehr (Prüfung vor Auslieferung, Nr. 4) – das gilt auch innerhalb einer Gliederung: Sind alle Artikel eines
  Unterordners im laufenden Durchgang schon geprüft, lässt sich dort ein eigener eröffnen. Bestätigt am 19.10.2026.
- **Migrierte Prüffreigaben externer Prüfer laufen am 31.12.2027 ab** (die übrigen sind seit Schritt 9 dauerhaft): Mit
  „Alle Prüffreigaben verlängern bis …“ geht das je Gliederung in einem Schritt. Ablaufmails an die Verwalter kommen
  erst mit Lieferung 2 – bis dahin warnen nur „Meine Freigaben“ und der Hinweis im Ordnerkopf (30 Tage vorher).
- **Verfahrensverzeichnis**: Der Textvorschlag (README, „Austritt und Löschen“) ist mit der Gliederung abzustimmen und
  juristisch prüfen zu lassen; die Fristen weiterer Sicherungen trägt der Betreiber ein. Dazu gehört jetzt die
  **unbefristete Aufbewahrung der Prüfnachweise** (Entscheidung vom 18.10.2026): Ihre Begründung im
  Verfahrensverzeichnis sollte juristisch geprüft werden – die Anwendung behauptet dazu nichts.
- **Inbetriebnahme in der Produktion**: Dort gibt es keine Gliederung, also nach dem Update auch keine Freigaben; nur
  die Plattform-Verwaltung hat das Modul. Sie gibt der Material-Verwaltung und den Mitgliedern die Stufe; die
  Material-Verwaltung legt die Gliederung an und wählt im selben Schritt den ersten Materialwart (README).
- **Protokollinhalt nach EN 365 – bestätigt am 19.10.2026** (aus Lieferung 3): Die zugeordnete Person kommt bewusst nicht ins Protokoll – mit
  den Sachkundigen bestätigen, dass die Prüfkarte sie nicht verlangt.
- **Bremse bei immer angebotener Suche – entschieden**: Bremse am 18.10.2026 auf Wunsch entfernt; Kontrolle bleibt das
  Protokoll mit Namen. (Bis dahin zählte, seit die Suche auch neben eigenen Treffern angeboten wird, auch eine Suche
  nach einer eigenen Seriennummer gegen die Grenze von zehn je Viertelstunde.)
- **Eindeutiger eigener Treffer**: `/material/suche` öffnet ihn wie bisher direkt; seit der Prüfung der Nachbesserung
  nimmt die Weiterleitung die Anfrage mit (`?q=`), und die Artikelseite bietet die Suche außerhalb des eigenen
  Bereichs unter dem Kopf an – „immer angeboten“ gilt damit auch dort. Bitte ansehen, ob der Platz zwischen
  Artikelkopf und Stammdaten passt.
- **Sperrwort für alle mit Modulzugang**: Auch ein Mitglied oder ein Prüfer ohne Freigabe sieht über Suche und QR, ob
  ein fremder Artikel gesperrt, verloren gemeldet oder ausgesondert ist (ein Wort, kein Grund, kein Datum).
- **Wer durch Schritt 10 Material-Verwaltung wird – vor dem Übernehmen auf main durchsehen**: Jeder bisherige
  Produktkatalogpfleger sieht danach alle Bestände aller Gliederungen (samt Prüfungen, Personen, Notizen) und vergibt
  jede Freigabe. Liste auf dev (lesend): `SELECT id, name, gliederung FROM users WHERE mat_katalog = 1 AND
  recht_verwaltung < 2;` – wer das nicht sein soll, bekommt in der Nutzerverwaltung „Mitglied“. Die Zahl der Konten
  mit Stufe Verwaltung klein halten. Ebenso ansehen, wer den Zugang zurückbekommt (Stufe aus Phase 1 oder nur
  abgelaufene Freigaben): Er sieht Katalog und Suche, keinen Bestand.
- **Entzug der Plattform-Verwaltung lässt Material auf „Verwaltung“** (wie die anderen Module): Wer nur kurz
  Plattform-Verwaltung war, sieht weiter alle Bestände, bis jemand Material einzeln senkt. Bestätigt am 19.10.2026.
- **Neue Konten brauchen einen Namen**: Mit der Vorgabe „Mitglied“ im Modul Material lehnt die Nutzerverwaltung ein
  neues Konto ohne Namen ab (oder Material „–“). Kontoanfragen haben den Namen ohnehin als Pflichtfeld.
- **Zusatz von Hand im Modellnamen – selbst umstellen, nicht automatisch**: Produkte, deren Modellname den Zusatz schon
  mit „ | “ enthält (etwa „D Classic | Screwlock“), zeigen sich schon jetzt ohne Strich – der Teil vor dem Strich als
  Name, der dahinter grau wie eine Bemerkung, auch im PDF. Umstellen bleibt trotzdem empfohlen, denn im Katalog
  steht der Strich weiter: im Dialog „Bearbeiten“, in der CSV je Ordner (Spalte „Modell“), im Katalog-Export und bei
  der Dublettenprüfung, die „D Classic | Screwlock“ und „D Classic“ mit Bemerkung „Screwlock“ als zwei Modelle
  sieht. Umstellen kannst du sie selbst: im Dialog „Bearbeiten“ den Teil hinter „ | “ aus dem Modell löschen und ins
  Feld „Bemerkung“ schreiben – die Anzeige bleibt gleich, die Suche findet weiter beide Teile. Automatisch stellt
  nichts um, der Katalog bleibt, wie du ihn gepflegt hast. Der Katalog-Export trägt die Katalogkennung, die Produktion findet ein so umbenanntes Produkt beim nächsten
  Import wieder. Liste auf dev (lesend): `SELECT id, manufacturer, model, description FROM mat_product WHERE model
  LIKE '%|%';`
- **Ältere lange Bemerkungen**: Bemerkungen über 80 Zeichen oder mit Zeilenumbruch stammen aus der Zeit vor der
  Grenze (damals hieß das Feld noch „Beschreibung“). Sie bleiben, wie sie sind, bis jemand das Produkt bearbeitet –
  dann verlangt der Dialog, sie zu kürzen. Liste auf dev (lesend): `SELECT id, manufacturer, model, length(description) FROM mat_product WHERE
  length(description) > 80 OR instr(description, char(10)) > 0;` – bitte vor der Übernahme in die Produktion
  durchsehen (der Import nimmt sie mit und nennt sie im Bericht).
- **80 Zeichen und CSV-Spalte – bestätigt am 18.10.2026**, mit dem Namen „Bemerkung“ („Grundsätzlich bestätigt.
  Benenne ‚Beschreibung‘ in Bemerkung um.“): höchstens 80 Zeichen; in der CSV je Ordner steht hinter „Modell“ die
  Spalte „Bemerkung (Produkt)“ (die „Bemerkung“ des Artikels weiter hinten bleibt). Wer eine Tabellenvorlage mit
  festen Spaltenpositionen nutzt, muss sie einmal anpassen. Umgesetzt unter „Bemerkung statt Beschreibung“.

### Die drei offenen Fragen – entschieden

Mit der Auslieferung waren drei Fragen offen und mit einer Vorgabe gebaut. Der Betreiber hat sie am 18.10.2026
entschieden; die Schalter sind fort.

1. **Sperrzustand im globalen Steckbrief und nach dem QR-Scan.** Gebaut war die Variante ohne – ein Finder sah nicht,
   ob ein fremdes Seil ausgesondert, gesperrt oder verloren gemeldet ist. **Entscheidung:** „Gerne ein Wort dazu
   anzeigen.“ **Umgesetzt:** Jeder Steckbrief trägt `sperre` – „gesperrt“, „verloren gemeldet“, „ausgesondert“ oder
   `null` (frei); kein Grund, kein Datum, auch kein Sperrgrund „Rückruf“. Die Karte zeigt das Wort als Marke in den
   Farben des Moduls (anthrazit gesperrt und verloren gemeldet, grau ausgesondert) – auf der Trefferseite, in den
   Vorschlägen und in der Ansicht „fremd“ nach dem QR-Scan.
2. **Wann die globale Suche angeboten wird.** Gebaut war „sobald kein sichtbarer Artikel genau diese Seriennummer
   hat“. **Entscheidung:** „Die Suche kann immer angeboten werden, jedoch sollten erst die Ergebnisse der für einen
   normal sichtbaren in der Liste angezeigt werden. Die ‚fremden‘ Ergebnisse sollten direkt erkennbar sein, z.B. mit
   einer dezenten Umrandung, Trennung wenn sie anfangen und/oder direkt ersichtlicher Indikation zu welcher
   Gliederung sie gehören.“ **Umgesetzt:** Angeboten wird zu jeder Anfrage, die für die globale Suche taugt (4 bis 80
   Zeichen, keine Inventar- oder STR-Nummer) – auch neben eigenen Treffern und wenn ein eigener Artikel genau diese
   Nummer hat (dann sagt der Text, dass nur Artikel anderer Gliederungen kommen); nur die Plattform-Verwaltung, die
   alles sieht, bekommt kein Angebot. Die Suche findet nur, was das Konto nicht sieht. Ihre Treffer stehen unter der
   eigenen Liste: Trennlinie mit „Aus anderen Gliederungen“, gestrichelt umrandete Karten, die Gliederung als blaue
   Marke ganz oben. Alle drei Kennzeichen zugleich – sie sind dezent genug, um sich nicht zu stören. Bestätigung,
   Bremse und Protokoll sind unverändert. (Die Bremse ist danach, ebenfalls am 18.10.2026, auf Wunsch entfallen –
   siehe „Nachbesserungen nach der Auslieferung“.)
3. **Aufbewahrung der Prüfnachweise nach der Aussonderung.** Offen war die Frist. **Entscheidung:** „Es soll nichts
   gelöscht werden, Prüfnachweise sollen ewig gespeichert bleiben.“ **Umgesetzt:** keine Frist, keine Löschroutine.
   Jeder Weg, auf dem ein Nachweis verschwinden könnte, ist durchgesehen und mit einem Regressionstest belegt; eine
   Lücke war offen und ist geschlossen (Herstellerdokumente einer leer gewordenen Kategorie, siehe unten). README
   („Austritt und Löschen“, Verfahrensverzeichnis) und der Kopf von `services/loeschung.py` nennen die unbefristete
   Aufbewahrung.

### Vier weitere Punkte – entschieden

Nach der Gesamtprüfung waren vier Punkte offen – drei standen unter „Zu prüfen“, die Vorschaubilder in der Rückmeldung
zur Nachbesserung. Der Betreiber hat sie am 18.10.2026 entschieden.

1. **Nur abgelaufene Freigaben → Mitglied** (Prüfung der Modulstufen Nr. 3). Schritt 10 zählt jede Freigabe, auch
   abgelaufene: Konten mit nur abgelaufenen Freigaben hatten mit 20085f1 keinen Zugang und bekommen „Mitglied“ – sie
   sehen das Modul (Katalog, Suche, globale Suche), aber keinen Bestand; dafür holt der Verwalter ihres Ordners sie
   durch Verlängern selbst zurück, ohne die Plattform-Verwaltung. **Entscheidung:** „Ja“ – bleibt so. `models.STUFE_10`
   und der Fall „abgelaufen“ in `test_migration_9_10` sind unverändert.
2. **Notiz an der eigenen Freigabe** (Prüfung vor Auslieferung Nr. 3). Wer einen Ordner mitverwaltet, liest im Reiter
   „Freigaben“ auch die Notiz zu seiner eigenen Freigabe (Bauentwurf 1.6 Nr. 10). **Entscheidung:** „Nein“ – sie wird
   bei eigenen Zeilen nicht verborgen und bleibt für Mitverwaltende sichtbar, wie die Hilfe im Dialog sagt. Unter „Meine
   Freigaben“ steht die Notiz weiter nie. Nichts geändert.
3. **Weitere Vorschaubilder vergrößerbar?** Nach dem Produktfoto in „Artikel anlegen“ (Wünsche vom 18.10.2026) war
   offen, ob auch die Vorschaubilder in Artikellisten, Katalogliste, Suchvorschlägen, im globalen Steckbrief und in der
   Bildvorschau der Dialoge groß öffnen sollen. **Entscheidung:** „Nein“ – sie bleiben, wie sie sind. Nichts geändert.
4. **Warnung beim letzten Materialwart.** Senkte die Plattform-Verwaltung die Stufe des einzigen Materialwarts einer
   Gliederung auf „–“, kam keine Warnung (Regel 1.6 Nr. 7 gilt nur im Reiter „Freigaben“) – danach verwaltet dort nur
   noch die Material-Verwaltung. **Entscheidung:** „Ja“, eine Warnung soll kommen. **Umgesetzt** – nur als Warnung,
   gesperrt wird nichts:
   - `GET /api/admin/users/<uid>/material-folgen` (nur die Plattform-Verwaltung) liefert zusätzlich
     `letzter_materialwart`: die Gliederungen, deren einziger wirksamer Verwalter das Konto heute ist, als
     `[{id, name, pfad}]` (`freigaben.einziger_materialwart`). Gezählt wird wie bei Nr. 7 mit `rechte.verwalter_von` –
     gültiges verwalten an der Gliederung oder darüber (auch bei verschachtelten Gliederungen), nur aktive Konten mit
     Namen und Stufe Mitglied: Die Material-Verwaltung zählt nicht als Materialwart, ein Mitverwalter ohne Stufe,
     deaktiviert oder mit abgelaufener Freigabe auch nicht. Infrage kommen nur Gliederungen in den Zweigen der eigenen
     gültigen verwalten-Zeilen; wer nur unterhalb einer Gliederung verwaltet, ist nicht ihr Materialwart.
   - Nutzerverwaltung (`admin.js`): Stellt der Dialog „Bearbeiten“ Material von „Mitglied“ oder „Verwaltung“ auf „–“
     oder nimmt er „Konto aktiv“ weg, oder stellt die Tabelle Material direkt auf „–“, und ist das Konto einziger
     Materialwart einer Gliederung, kommt vor dem Speichern die Rückfrage „Einziger Materialwart“. Sie nennt die
     Gliederung(en) (mit Pfad, falls verschachtelt), sagt, dass dort danach nur noch die Material-Verwaltung verwaltet
     und Freigaben vergibt, und nennt den Weg zu einem zweiten Materialwart (Bestand → Gliederung → Bearbeiten →
     Freigaben, Vorlage „Materialwart“). „Abbrechen“ (grau, vorn, mit Fokus; Esc ebenso) lässt alles, wie es war – der
     Dialog bleibt offen, in der Tabelle springt die Auswahl zurück, und der Fokus steht wieder auf „Speichern“ bzw. der
     Auswahl; „Trotzdem speichern“ ist der rote Hauptknopf, nicht der Knopf für Endgültiges, denn gelöscht wird nichts.
     Ohne betroffene Gliederung keine Rückfrage. Die Tabelle gehört dazu, weil sich die Stufe dort mit einem Wechsel
     ändern lässt. Der Dialog „Löschen“ nennt dieselbe Folge unter den Folgen im Modul Material.
   - Tests: `test_material_stufen.test_letzter_materialwart` (einziger Verwalter, zwei Verwalter, geerbt von oben samt
     verschachtelter Gliederung, nur unterhalb verwaltet, abgelaufen – fremd und eigen –, Material-Verwaltung zählt
     nicht, deaktivierte und Mitverwalterin ohne Stufe zählen nicht, 403 für Material-Verwaltung, Materialwart und
     Führungskraft, Speichern geht trotzdem) und `test_letzter_materialwart_oberflaeche` (statisch: Tabelle und Dialog,
     Knöpfe, Fokus, Löschdialog); `test_material_zuordnung.test_loeschkonzept` erwartet das neue Feld.
   - Im Browser geprüft (Chromium, eigenes DATA_DIR mit DEMO-Daten und DEMO-Konten, als Plattform-Verwaltung bei
     1280 × 900 mit Maus und 390 × 844 mit Touch): DEMO-Materialwart A, einziger Verwalter der DEMO-Gliederung, im
     Dialog auf Material „–“ → Rückfrage mit „DEMO-Gliederung“, Fokus auf „Abbrechen“; Abbrechen ändert nichts,
     „Trotzdem speichern“ speichert; Deaktivieren ebenso; in der Tabelle ebenso; der Dialog „Löschen“ nennt die Folge;
     mit dem DEMO-Prüfer als zweitem Verwalter keine Rückfrage, weder im Dialog noch in der Tabelle. Keine
     Konsolenfehler, nichts rollt waagerecht.

#### Prüfung der Rückfrage

Eine unabhängige Prüfung der Rückfrage (Chromium bei 1280 und 390 px, dazu dieser Abschnitt) meldete zwei Befunde,
beide niedrig. Beide sind nachgestellt und behoben; danach liefen alle Suiten grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Nach „Abbrechen“ oder Esc in der Rückfrage aus „Bearbeiten“ stand der Fokus auf der Seite, und Tab begann oben im langen Dialog: Beim Schließen gibt der Browser den Fokus an „Speichern“ zurück, das bis zum Ende der Rückfrage gesperrt ist. In der Tabelle verlor die Auswahl den Fokus ebenso – dort schon vorher bei jedem Wechsel, weil sie gesperrt und neu gezeichnet wird | niedrig | Behoben (`admin.js`): Bleibt der Dialog offen – nach dem Abbrechen oder einem Fehler beim Speichern, der den Fokus genauso verlor –, bekommt „Speichern“ ihn zurück, sobald der Knopf wieder frei ist; in der Tabelle nach jedem Wechsel die neu gezeichnete Auswahl desselben Moduls. Beides nur, wenn der Fokus nicht schon anderswo steht. Statischer Test in `test_letzter_materialwart_oberflaeche` (scheitert ohne die Änderung). Im Chromium nachgestellt und nachgeprüft bei 1280 × 900 (Esc, Enter auf „Abbrechen“, Maus; Tabelle mit Abbrechen, Speichern und „Trotzdem speichern“; Fehler beim Speichern ohne Namen) und 390 × 844 mit Touch: vorher BODY, jetzt „Speichern“ bzw. die Auswahl; keine Konsolenfehler, nichts rollt waagerecht |
| 2 | „Neu“ nannte die Rückfrage nicht, obwohl die Einleitung sagt, „Neu“ beschreibe den Stand danach – weder unter „Nutzerverwaltung“ noch beim Löschkonzept | niedrig | Behoben: Der Punkt „Nutzerverwaltung“ nennt die Rückfrage (Tabelle, Dialog, Deaktivieren) und den Dialog „Löschen“, das Löschkonzept den zweiten Hinweis |

### Nachbesserungen nach der Auslieferung (Entscheidungen vom 18.10.2026)

- **Sperrwort im Steckbrief** (`services/globalsuche.py`, `static/global.js`): `sperre` gehört fest zu den Feldern
  (`FELDER`, der Test prüft Gleichheit); der Schalter `STECKBRIEF_MIT_SPERRE` ist entfernt. Gesperrte und Ausgesonderte
  stehen weiter unter ihrem Herkunftsordner – den Zustand sagt nur das eine Wort.
- **Globale Suche immer angeboten, fremde Treffer unter den eigenen** (`services/globalsuche.py`, `routes.py`,
  `static/global.js`, `static/suche.js`, `static/material.js`, `static/global.css`):
  - `globalsuche.angebot(q)` hängt nur noch an der Anfrage und daran, ob das Konto alles sieht; die Schalter `ANGEBOT`
    und `ANGEBOTE`, die Meldung `IM_BEREICH` und `exakt_sichtbar` sind entfernt.
  - Die Suche schließt sichtbare Artikel in derselben Abfrage aus (`NOT COALESCE(artikel_filter, 0)`) – zehn Treffer
    und „mehr“ zählen nur Fremde, und das Protokoll nennt nur diese. Das COALESCE braucht es, weil der Filter bei
    Ausgesonderten ohne Herkunft NULL ergibt; ohne fänden andere sie gar nicht.
  - Trefferseite: erst die eigene Liste (Tabelle mit Seiten wie bisher, ohne Treffer „Kein Artikel in deinem Bereich
    gefunden.“), darunter das Angebot als grauer Knopf mit „die Suche wird mit deinem Namen protokolliert“, nach der
    Suche an seiner Stelle die fremden Treffer; der Fokus geht zur Überschrift „Aus anderen Gliederungen“. Blättern und
    Sortieren der eigenen Liste behalten das Ergebnis, ohne noch einmal zu suchen.
  - Vorschläge: erst die eigenen, dann „Alle Treffer“, dann die Angebotszeile; nach der Suche bleiben die eigenen
    stehen, statt des Angebots folgen die Trennzeile und die fremden Steckbriefe (gewählt mit ↑/↓, `aria-disabled`,
    Enter öffnet nichts); die Liste rollt bis zum Beginn der fremden. Weitertippen verwirft das Ergebnis, das Angebot
    kommt zurück.
  - Rückfrage „In anderen Gliederungen suchen“ mit dem roten Hauptknopf „Suchen“ und dem Hinweis auf das Sperrwort.
  - Ein eindeutiger eigener Treffer öffnet `/material/suche` weiter direkt den Artikel; das Angebot steht dann in den
    Vorschlägen unter dem Suchfeld.
- **Prüfnachweise bleiben** (`services/katalog.py`, `services/loeschung.py`): Durchgesehen sind Artikel löschen (409
  bei jeder Prüfung), Ordner löschen (409, solange Artikel oder Durchgänge daran hängen; ein von dort Ausgesonderter
  verliert beim Löschen des leeren Ordners nur die Herkunft), Durchgang entfernen (409 mit Geprüftem) und abbrechen
  (bleibt mit Sammelprotokoll), Konto löschen (nur die Kontokennung wird NULL), Anhang, Befundfoto und Prüfung
  entfernen (nur an Entwürfen), Berichtigung verwerfen (nur ihre eigenen Kopien der Dateien), Produkt löschen (nur
  ohne Artikel), Formular löschen (nur unbenutzt), Kategorie löschen, Protokolldateien (entfernt werden nur neue
  Dateien einer gescheiterten Transaktion, Verwaistes legt der Start beiseite, nie gelöscht), Aufräumen beim Start
  und die Trigger und Fremdschlüssel in `models.py`. **Geschlossen:** Eine Kategorie, aus der ein Produkt nach einer
  Prüfung fortgezogen war, ließ sich als leere Kategorie samt ihren Herstellerdokumenten löschen – die das
  Prüfprotokoll mit Version und Prüfsumme nennt. Jetzt 409 „Ein Dokument dieser Kategorie steht in Prüfprotokollen
  und bleibt – damit auch die Kategorie.“ Tests `test_material_zuordnung.test_pruefnachweise_bleiben` (alle Wege,
  Dateien Byte für Byte, Neustart) und `test_dokument_im_protokoll_bleibt`.
- **Tests**: `test_material_globalsuche.py` mit `test_sperrwort`, `test_angebot` und `test_nur_fremde` (gleiche
  Seriennummer in A und B, LIMIT und „mehr“ nur über Fremde, Protokoll nur mit fremden Kennungen) statt der beiden
  Schaltertests; `test_material_trennung.test_unterbau` angeglichen.
- **Im Browser geprüft** (Chromium, DEMO-Daten mit den DEMO-Konten, 1280 × 900, 820 × 1180 und 390 × 844 mit
  Touch): als DEMO-Materialwart A die Seriennummer `DEMO-NS-4711` nur in der Nachbarstadt und – nach zwei eigenen
  DEMO-Artikeln mit derselben Nummer – lokal und fremd, je Trefferseite und Vorschläge samt Tastatur; als
  DEMO-Materialwart B ein gesperrter Artikel der DEMO-Gliederung über Suche, Vorschläge und QR-Seite „fremd“. Keine
  Konsolenfehler, nichts rollt waagerecht.

#### Prüfung der Nachbesserung

Zwei unabhängige Prüfungen – Sicherheit (mit eigenen Konten nachgestellt) und Browser (Rundgang mit den DEMO-Konten,
darunter der externe Prüfer mit Freigabe nur am DEMO-Lager) – haben fünf Befunde gemeldet, zwei davon dieselbe
Abweichung. Jeder ist vor der Behebung nachgestellt worden (Anfrage, Browser oder im Code); alle vier sind behoben,
der Daten- und der Weiterleitungsfall mit Regressionstest, die Oberfläche im Browser nachgeprüft (Chromium,
DEMO-Konten, 1280 × 900, 1024 × 768, 820 × 1180 und 390 × 844 bzw. 390 × 560 mit Touch; keine Konsolenfehler,
nichts rollt waagerecht). Danach liefen alle Suiten grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | „Aus anderen Gliederungen“ zeigte auch Artikel der eigenen Gliederung, wenn das Konto nur einen Teil davon sieht (externer Prüfer, Materialwart eines Standorts); der Hinweis „… wer in der Gliederung eine Freigabe hat“ stimmte dann nicht | mittel | Gesucht wird weiter über alles, was das Konto nicht sieht; die Texte sagen jetzt „außerhalb deines Bereichs“ – Angebot, Trennlinie, Überschrift, Rückfrage (nennt andere Gliederungen und Ordner ohne eigene Freigabe), exakt-Text, leeres Ergebnis. Zu welcher Gliederung ein Treffer gehört, sagt weiter die Marke auf seiner Karte. Hinweis: „… wer für den Ordner des Artikels eine Freigabe hat.“ Test `test_teilfreigabe` |
| 2 | Bei genau einem eigenen Treffer leitete `/material/suche` gleich zum Artikel – nach Enter, „Suchen“ oder „Als Trefferliste anzeigen“ stand das Angebot nirgends, auch nicht bei einem Teiltreffer; „immer angeboten“ galt dort nicht (von beiden Prüfungen gemeldet) | niedrig | Der eindeutige Treffer öffnet weiter direkt (Phase 1), die Weiterleitung nimmt die Anfrage aber mit, wenn sie für die globale Suche taugt (`?q=`); die Artikelseite zeigt dann unter dem Kopf dasselbe Angebot wie die Trefferseite (grauer Knopf, Rückfrage, Ergebnis an seiner Stelle, bleibt beim Neuzeichnen). Ohne `q` bei Inventar- und STR-Nummern und für die Plattform-Verwaltung; die Artikelseite übergeht ein `q`, das nicht taugt. Test `test_eindeutiger_treffer` |
| 3 | Angebot („Nur Stammdaten und Zugehörigkeit“), Rückfrage („gesperrt oder ausgesondert“) und Ergebnis (drei Sperrwörter) beschrieben den Inhalt unterschiedlich | niedrig | Angebot und Angebotszeile: „Nur Stammdaten, Zugehörigkeit und Sperrzustand“; die Rückfrage nennt „gesperrt, verloren gemeldet oder ausgesondert“ wie die QR-Ansicht „fremd“. `test_sperrwort` prüft die Texte mit |
| 4 | Die Vorschlagsliste rollte nach der globalen Suche immer bis zur Trennzeile und schnitt eigene Vorschläge ab, auch wenn alles ohne Rollen zu sehen gewesen wäre | niedrig | Gerollt wird nur, bis Trennzeile und erste fremde Karte ganz zu sehen sind, höchstens bis die Trennzeile oben steht. Nachgemessen: 1280 × 900, 1024 × 768 und 390 × 844 rollen nicht mehr; 390 × 560 rollt 47 px |

#### Gesamtprüfung vor Auslieferung

Eine unabhängige Gesamtprüfung über alles seit 0835927 (Läufe auf einer Kopie der migrierten dev-Datenbank, Rundgang
im Chromium je Rolle) meldete acht Befunde, alle niedrig. Jeder ist vor der Behebung nachgestellt (Lauf, Anfrage oder
Chromium) und behoben, mit Test, wo es einen braucht – die Tests zu Nr. 1 und 2 scheitern ohne die Änderung. Die
Oberfläche ist im Chromium bei 390 × 844 (Touch) und 1280 × 900 nachgeprüft (eigenes DATA_DIR mit DEMO-Daten und
einem DEMO-Produkt mit Beschreibung; keine Konsolenfehler, nichts rollt waagerecht). Danach liefen alle Suiten grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Beispielbestand: Die DEMO-Prüferin bekam eine befristete Prüffreigabe (bis 31.12. des Folgejahres), obwohl nur Externe befristet prüfen | niedrig | Ihre Prüffreigabe ist dauerhaft (lesen steht in derselben Schleife davor), der externe Prüfer bleibt bei 30 Tagen; Docstring, README und Abschnitt „Beispielbestand“ angeglichen. Test in `test_beispielbestand` |
| 2 | Ein abgebrochener Beispielbestand-Lauf (SIGHUP wie beim SSH-Abbruch während `docker exec`) hinterließ Artikel ohne Durchgänge und Zuordnungen; der nächste Lauf meldete „schon da“ mit Rückgabewert 0, eine Protokolldatei blieb verwaist | niedrig | Merker `beispielbestand` in `mat_meta` erst am Ende – gibt es die Gliederungen ohne ihn, meldet ein neuer Lauf „unvollständig“ mit Rückgabewert 1. SIGHUP und SIGTERM brechen wie Strg-C ab: Der Artikel in Arbeit rollt samt Protokolldateien zurück, und der Hinweis sagt, ob nichts, ein Teil oder alles angelegt ist. README: den Befehl in `tmux` oder `screen` starten; nach einem Abbruch geht es nur mit zurückgesetzter dev-Datenbank und Katalogimport weiter. Test `test_abgebrochener_lauf` (SIGHUP in der ersten Gliederung und mitten in einer Prüfung; vorher beendete das Signal den Prozess) |
| 3 | Die README nannte keinen Container-Befehl für den nach dem Deploy nötigen Lauf `material_demo.py --demo --konten` | niedrig | Neuer Abschnitt „DEMO-Daten und DEMO-Konten (nur dev)“ mit dem Befehl per stdin, „nach dem Deploy einmal ausführen“, wiederholbar, nie in der Produktion (das Skript prüft die Adresse nicht). Die stdin-Form ist mit einem Skript außerhalb des Repositorys nachgestellt; ein zweiter Lauf ändert nichts |
| 4 | „Art.-Nr.“ und Artikelnummer brachen am Bindestrich um („Art.-“ / „Nr. EC-1“, „DEMO-K-“ / „1“), mit dem Zusatz „\| Beschreibung“ auch am Desktop; auf der Prüfseite ebenso die Seriennummer | niedrig | An allen fünf Stellen (Artikelseite, Prüfformular, Prüfung, Vorschläge, Steckbrief) über `MatProdukt.artNr` bzw. `.nummer` (material.js): „Art.-Nr. …“ und „Seriennummer …“ stehen als ein Stück (`.mat-ganz`, inline-block mit `max-width: 100%`) und rutschen ganz in die nächste Zeile; nur was breiter ist als eine Zeile, bricht darin um. Das ersetzt den vorgeschlagenen geschützten Bindestrich und `nowrap` bis 30 Zeichen – so bleibt der kopierte Text gleich, und auch eine sehr lange Nummer rollt nie waagerecht. Nachgemessen bei 390 und 1280 px, auch mit 60 Zeichen; statischer Test in `test_material_beschreibung` |
| 5 | Bremse und fremde Dublette sprachen von „globaler Suche“, die Oberfläche von „Außerhalb deines Bereichs … suchen“ | niedrig | „Zu viele Suchen außerhalb deines Bereichs – bitte in einer Viertelstunde noch einmal.“ und „… Wo der Artikel geführt wird, zeigt die Nummernsuche oben („Außerhalb deines Bereichs … suchen“).“ (vorher bezog sich „er“ auf die Seriennummer); ebenso die Antwort ohne Bestätigung. Das Protokoll in der Verwaltung heißt weiter „Globale Suchen“. Tests in `test_material_globalsuche` |
| 6 | Übersicht ohne Freigabe – die erste Seite jedes neuen Kontos – mit dem alten Wortlaut „… auch in allen Gliederungen“ | niedrig | „Die Nummernsuche oben findet eine Herstellerseriennummer auf Wunsch auch außerhalb deines Bereichs – das wird mit deinem Namen protokolliert.“ Test `test_teilfreigabe` |
| 7 | Nutzerverwaltung, Dialog „Bearbeiten“: Dass der Prüfer die Urkundennummer selbst im Profil einträgt, stand zweimal untereinander | niedrig | Die Zeile unter dem Häkchen nennt nur den Zustand („Urkundennummer: noch keine – solange darf er nicht prüfen.“ bzw. die Nummer), den Weg nennt allein der Hilfetext. Test `test_nutzerverwaltung_oberflaeche` |
| 8 | Profil: Das Profilbild stehe „an jedem Artikel“ – im Modul Material ist ein Artikel der Ausrüstungsgegenstand, und neue Konten lesen das Wiki nur | niedrig | „Es steht neben deinem Namen an jeder Wiki-Seite, die du erstellt oder bearbeitet hast.“ – für jedes Konto richtig, ohne Fallunterscheidung. Test `test_vorgabe_neue_konten` |

### Bestätigungen vom 19.10.2026

Alle bis dahin offenen Annahmen hat der Nutzer am 19.10.2026 bestätigt (an Ort und Stelle als „bestätigt“ markiert):

- **Pfadnamen in verschobenen Artikeln** bleiben in Journal, Protokollen und alten Durchgängen (Zu prüfen oben).
- **Erledigte Zeilen sperren keinen neuen Durchgang**, auch innerhalb einer Gliederung (Zu prüfen oben).
- **Entzug der Plattform-Verwaltung lässt Material auf „Verwaltung“** (Zu prüfen oben).
- **Reiner Text „Name Zusatz“** mit Leerzeichen, ohne Komma (Bemerkung statt Beschreibung).
- **„Bemerkung (Produkt)“** als CSV-Spalte und **„Bemerkung des Melders“** im Dialog „Produkt aus Meldung anlegen“.
- **Warnung beim letzten Materialwart** auch in der Tabelle der Nutzerverwaltung und im Dialog „Löschen“.
- **Spalte „kritisch“ im Prüfprotokoll** steht immer da, die Marke klein geschrieben wie in der Oberfläche.
- **Protokollinhalt nach EN 365**: Die zugeordnete Person kommt nicht ins Protokoll.
- **Schrift**: Die Lizenz der DLRG deckt das Einbetten von DLRG Univers in PDF-Protokolle (Lieferung 3, Zu prüfen).

## Phase 2 · Lieferung 2 – Erinnerungen (19.10.2026)

Lieferung 1 von Phase 2 wurde am 19.10.2026 mit „Starte Lieferung 2“ freigegeben. Lieferung 2 bringt den
Erinnerungslauf aus dem Konzept: eine Sammelmail am Morgen an die Materialwarte zu Prüffristen, Lebensende und
ablaufenden Freigaben, abschaltbar je Ordner, mit Laufstand und Probelauf für die Material-Verwaltung. Gebaut nach dem
Bauentwurf vom 19.10.2026 (überarbeitet nach zwei Kritiken, „Betrieb“ und „Fach“) in zwei Paketen: KERN (Schema,
Dienst, Tageslauf, Kommandozeile, Tests) und OBERFLÄCHE (Ordnerdialog, Ordnerkopf, Übersicht, Verlauf, Doku).
Schemaversion 11, keine neuen Abhängigkeiten. Der Versand ist in der Vorgabe **aus**. Stand: wartet auf Freigabe.

### Neu

- **Tageslauf, eingebaut** (`app/material/tageslauf.py`, `services/erinnerung.py`): Jeder Arbeitsprozess startet mit
  der ersten Anfrage einen Hintergrundthread. Er wacht alle 15 Minuten auf und arbeitet **einmal am Tag ab 6 Uhr
  deutscher Zeit** (Sommerzeit über `zoneinfo`). Es gibt keinen Cron und keine Arbeit auf dem VPS. Jede Runde legt
  vorher die Einstellungen aus dem Browser über die Konfiguration (Schalter, Mailserver, `BASE_URL`, `SITE_NAME`).
  Der Lauf hat zwei Teile:
  - **Pflege** (täglich, auch bei ausgeschaltetem Versand): Journaleintrag „Freigabe abgelaufen“ am Ankerordner für
    jede befristete Freigabe, deren Enddatum vorbei ist (einmal je Freigabe und Enddatum, `user_name` „Tageslauf“,
    Konto nur als Verweis). Dazu das Löschen des Erinnerungslogs nach 13 Monaten, die Zeilen gelöschter Konten und das
    Kürzen des Protokolls der globalen Suche. Log und Waisen räumt zusätzlich jeder Start auf.
  - **Erinnerungsmails** (nur bei eingeschaltetem Versand, ohne Sperre und mit `SMTP_HOST`).
- **Stufen** (fest): Prüfung fällig in höchstens 30 Tagen, in höchstens 7 Tagen, überfällig (einmal je
  Fälligkeitsdatum), Lebensende in höchstens 90 Tagen oder erreicht (nur textiles Material, einmal je Lebensende) und
  befristete Freigaben, die in höchstens 30 Tagen enden (einmal je Freigabe und Enddatum, nach „Verlängern“ neu).
  Gemeldet wird je Ziel nur die höchste erreichte Stufe, die für das Konto noch nicht im Log steht. Ausgefallene Tage
  holt der nächste Lauf so nach, ohne eine Stufe doppelt zu melden.
- **Auswahl**: nur Artikel im Zustand „frei“ mit Fälligkeit bzw. Lebensende; nie DEMO-Artikel, nie Artikel in Ordnern
  mit „Erinnerungsmails aus“ (vererbt). Artikel im Status „neu“ werden nach ihrem Datum gemahnt, mit dem Zusatz
  „Eingangsprüfung offen“. Freigaben nur befristete, die heute wirken, nie an DEMO-Ordnern oder von DEMO-Konten.
- **Empfänger**: wer an der Heimat des Artikels (bzw. am Anker der Freigabe) oder darüber gültig verwaltet –
  Material- und Plattform-Verwaltung eingeschlossen, wenn sie dort eingetragen sind. Verwaltet dort niemand, geht die
  Gruppe an die Material-Verwaltung, ohne sie an die Plattform-Verwaltung, gekennzeichnet mit „kein Materialwart
  eingetragen“ und dem Link „Materialwart vergeben“ – bei einer Freigabe, an deren Anker nur ihr Inhaber selbst
  verwaltet, mit „nur der Inhaber selbst verwaltet hier“ und nur „Verlängern“. Nur aktive Konten mit Namen, Modulzugang und Adresse, nie
  DEMO-Konten (Adresse `….invalid`). Jeder bekommt nur, was er sieht. Zugeordnete Personen und Prüfer bekommen nichts.
  Der Inhaber einer ablaufenden Freigabe bekommt sie zusätzlich selbst, im Abschnitt „Deine Freigaben“ mit den Namen
  derer, die verlängern können (Entscheidung vom 19.10.2026, siehe unten). Bei einer Freigabe werden die offenen
  Prüfungen des Inhabers im Zweig genannt – bei befristetem lesen oder verwalten die, deren dauerhafte Prüffreigabe an
  diesem Grundrecht hängt.
- **Mail**: eine je Empfänger und Tag, Artikel und Freigaben zusammen, gruppiert nach Ordnerpfad, in der Gruppe nach
  Dringlichkeit. Jede Gruppe steht mit Pfad, Zahl und Link zum Ordner da (Links aus `BASE_URL`). Höchstens 100
  Artikel- und 50 Freigabezeilen je Mail, der Rest einer Gruppe als „… und n weitere in diesem Ordner“. Die Einleitung
  sagt in einem Satz, dass nur Neues drinsteht, mit dem Link auf alles Fällige. Die Fußzeile nennt den Weg zum
  Abschalten, wenn die Mail Artikel nennt; eine Mail nur mit Freigaben sagt, dass die sich immer melden (eine Mail nur
  mit eigenen Freigaben sagt dazu nichts). Keine Adressen anderer Personen.
- **Erinnerungslog** `mat_reminder_log`: Ziel (Artikel oder Freigabe), Stufe, Datum, pseudonymer Kontoverweis
  (`users.mat_ref`, nie die Adresse) und Zeitpunkt. Eine Zeile entsteht nur, wenn der Mailserver die Mail angenommen
  hat; was scheitert, kommt am nächsten Morgen wieder. Das Log ist **kein Prüfnachweis**: 13 Monate, beim Löschen des
  Kontos sofort weg (`loeschung.py`).
- **Einmaligkeit**: Tagesmarken und ein Herzschlag in `mat_meta`, gesetzt unter `BEGIN IMMEDIATE`, dazu UNIQUE-Indizes
  im Log – zwei Arbeitsprozesse, ein Neustart oder Thread und Kommandozeile mahnen nie doppelt. Einzige Ausnahme:
  Endet ein Prozess genau zwischen der Annahme einer Mail und ihrem Vermerk (etwa beim Neustart nach einem Deploy),
  kommt diese eine Mail am nächsten Morgen noch einmal – erst senden, dann vermerken. Pflege, Mailteil und
  jede einzelne Mail laufen in eigenem `try`: Ein Fehler kostet nicht den Rest des Laufs und steht im Laufstand.
- **Schalter „Erinnerungsmails verschicken“** unter Verwaltung → Einstellungen → Material (`MATERIAL_ERINNERUNGEN`,
  Vorgabe aus), mit Hilfetext zu den Stufen. Dazu die **Sperre** `MATERIAL_ERINNERUNGEN_SPERRE`, nur über die
  Umgebung: Kein Wert im Browser übersteuert sie. Ohne Eintrag greift sie, wenn `STROEMIS_NAME` auf `-dev` endet – die
  Entwicklung bleibt so ohne Handgriff still. `dev-einrichten.sh` trägt sie künftig ausdrücklich ein, `.env.example`
  nennt beide.
- **„Erinnerungsmails aus“ je Ordner**: Kästchen im Dialog „Ordner bearbeiten“, Reiter „Ordner“, unter Art und
  Prüfintervall – nur beim Bearbeiten eines vorhandenen Ordners, nicht an Systemordnern, also nur mit verwalten. Es
  gilt für den Ordner und alle Unterordner, auch für die Verwalter darüber und die Material-Verwaltung; ablaufende
  Freigaben melden sich weiter. Das Kästchen zeigt den eigenen Wert; ist es von oben geerbt, sagt ein Hinweis „Ohnehin
  aus – geerbt von „…““. Ungespeichert erkennt der Dialog auch das Kästchen (Rückfrage beim Verlassen aus dem Reiter
  „Freigaben“). Jede Änderung steht im Journal des Ordners („Erinnerungsmails aus: nein → ja“). Im Ordnerkopf steht
  für Verwalter „Erinnerungsmails aus“ bzw. „Erinnerungsmails aus – geerbt von <Pfad>“ (Link zum Oberordner).
- **Laufstand und Probelauf** (nur Material- und Plattform-Verwaltung): ganz unten auf der Übersicht eine Zeile
  „Erinnerungsmails: an · letzter Lauf heute 06:02 – 4 Mails, 1 fehlgeschlagen (Name) · Probelauf ansehen“ (bzw.
  „aus – einschalten unter Verwaltung → Einstellungen (Plattform-Verwaltung)“, „in dieser Umgebung gesperrt“, „an,
  aber kein Mailserver eingerichtet“, „noch kein Lauf“). Die Uhrzeit steht in deutscher Zeit. „Probelauf ansehen“ ist
  ein Textlink, kein Knopf im Kopf. Was Handeln verlangt, steht zusätzlich gelb oben neben dem Hinweis auf
  Produktmeldungen, mit „Einzelheiten unten“: Lauf steht (nach 7 Uhr heute keiner, auch für den Pflegeteil bei
  ausgeschaltetem Versand), an ohne Mailserver, gescheiterte Mails („… geht morgen erneut“), Fehler des Mail- oder
  Pflegeteils, unlesbare Datenzeilen, nicht vermerkte Mails.
- **Probelauf-Dialog** „Probelauf Erinnerungsmails“: rechnet den **nächsten** echten Lauf – heute, oder morgen, wenn
  heute schon verschickt wurde (mit dem heutigen Log) – und sagt das in der Überschrift („Heute ab 6 Uhr gingen
  hinaus:“ / „Morgen …“). Oben die Zeile zum letzten Lauf und, wenn der Versand aus oder gesperrt ist, „… so gingen sie
  hinaus, wenn sie an wären“. Je Empfänger ein aufklappbarer Eintrag „Name (Gliederung) – n Artikel, m Freigaben“ mit
  Betreff und Text wie verschickt. Darunter „Ohne Empfänger“ und „Ausgelassen: Erinnerungen aus in <Pfade mit Link>
  (n Artikel); n DEMO-Artikel; n DEMO-Freigaben“. Keine Adressen. Nichts wird verschickt, vermerkt oder ins Journal
  geschrieben. Einziger Knopf „Schließen“ (grau umrandet).
- **Probelauf mit DEMO-Bestand (nur Ansicht)** – Nachtrag vom 19.10.2026: Auf dev ist der ganze Bestand DEMO, und DEMO
  wird absichtlich nie gemahnt – der Probelauf zeigte dort nichts. Hat er DEMO ausgelassen, steht im Dialog jetzt das
  Kästchen „DEMO-Bestand einbeziehen (nur Ansicht)“; Anhaken lädt den Probelauf neu (`?demo=1`). Dann zählen
  DEMO-Artikel, DEMO-Freigaben und DEMO-Konten als Empfänger wie echte (gleiche Stufen, Rechte, Gruppen, Rückfall).
  Jede Mail mit DEMO-Empfänger oder DEMO-Einträgen trägt die gelbe Marke „DEMO“ und „DEMO – geht nie hinaus“, der
  Betreff beginnt mit „[DEMO]“, der Text mit „DEMO – geht nie hinaus. Diese Mail zeigt nur der Probelauf mit
  DEMO-Bestand.“, jede DEMO-Zeile endet auf „· DEMO“. Gelb darüber: „DEMO-Bestand einbezogen – nur zur Ansicht …“.
  Ohne DEMO im Bestand (Produktion) erscheint das Kästchen nicht. Kein neuer Knopf. Der echte Lauf (Tageslauf,
  `remind` ohne `--trocken`, Log, Journal, Laufstand) ist unverändert und lässt DEMO weiter aus – im Code
  abgesichert: Nur Probelauf und `remind --trocken --demo` rufen `planen(…, demo=True)`; ein solcher Plan heißt
  `nur_ansicht`, und `verschicken` und `vermerken` lehnen jeden Plan und jede Mail mit DEMO-Kennzeichen oder
  DEMO-Adresse ab (`ValueError`), bevor etwas hinausgeht oder ein Kontoverweis entsteht.
- **Verlauf der Freigaben** (Reiter „Freigaben“ → „Verlauf“): „„lesen“ von Eva Probe abgelaufen (bis 18.10.2026)“, als
  Handelnder „Tageslauf“. Im Ordnerjournal heißt die Aktion „Freigabe abgelaufen“ (nur für Verwalter, wie die übrigen
  Freigabe-Einträge).
- **Kommandozeile** `flask material remind` (README, „Erinnerungsmails (Modul Material)“): `--trocken` zeigt die Mails
  des nächsten Laufs mit Adressen und schreibt nichts, auch bei ausgeschaltetem oder gesperrtem Versand;
  `--stichtag JJJJ-MM-TT` nur mit `--trocken`; ohne `--trocken` ein echter Lauf, `--erneut` schickt am selben Tag noch
  einmal, was nicht im Log steht; `--trocken --demo` bezieht den DEMO-Bestand ein (nur Ansicht, Nachtrag vom
  19.10.2026; `--trocken` nennt dazu unter „Ausgelassen“ DEMO-Artikel und DEMO-Freigaben getrennt und den Hinweis
  „DEMO-Bestand ansehen: remind --trocken --demo“). Rückgabewert 0, 1 (Mail gescheitert oder Fehler) oder 2 (aus,
  gesperrt, kein Mailserver, `--stichtag` oder `--demo` ohne `--trocken`, unlesbares Datum).

### Migration

- Schemaversion 11, läuft beim Start von selbst, wiederholbar – ein zweiter Lauf ändert nichts:
  - `mat_folder.reminders_off` (0/1, Vorgabe 0) – rein additiv.
  - `mat_reminder_log` wird **verworfen und neu angelegt**: Kontoverweis `konto_ref` statt der Adresse `sent_to`,
    `due_on` Pflicht, Artikel **oder** Freigabe (`grant_id`, CASCADE), die neue Stufe `freigabe_ablauf`, UNIQUE je
    Ziel, Stufe, Datum und Konto. Bis Schritt 11 hat kein Code ins Log geschrieben; es gibt nichts zu übernehmen.
  - `mat_meta` bekommt beim ersten Lauf die Schlüssel `tageslauf_laeuft`, `tageslauf_pflege_tag`, `erinnerung_tag` und
    `tageslauf_stand` (der Schritt legt keinen an).
- Geprüft: frische Datenbank, 10→11 (auch mit zwei gleichen Altzeilen im alten Log), 7→11 an einer Kopie des Stands 7
  (dieselben Freigaben, Stufen, Journalzahlen, Artikel und Ordner wie 7→10 mit dem Stand vor dieser Lieferung;
  Fremdschlüssel und `integrity_check` in Ordnung).
- **Rückweg**: Eine Fassung mit Schemaversion 10 übergeht `reminders_off` und das neue Log; sie schreibt beides nicht.
- Keine Handarbeit beim Update: `docker compose up -d --build` genügt. **Der Versand bleibt aus**, bis ihn die
  Plattform-Verwaltung in der Produktion im Browser einschaltet. Der erste Lauf danach schickt den Rückstand (Zu
  prüfen, Nr. 3).

### Neue Abhängigkeiten

Keine.

### Entscheidungen

Die Vorgaben des Auftrags, so gebaut (zur Bestätigung unter „Zu prüfen“):

1. **Schalter „Erinnerungsmails verschicken“** in Verwaltung → Einstellungen (Gruppe Material, `.env`
   `MATERIAL_ERINNERUNGEN`), **Vorgabe aus**. Dev bleibt still – zusätzlich über die Sperre aus der Umgebung, die kein
   Browserwert übersteuert. In der Produktion schaltet der Betreiber nach dem Merge im Browser ein. Der Probelauf geht
   auch bei „aus“.
2. **Einmal am Tag ab 6 Uhr deutscher Zeit**, Einmaligkeit über Tagesmarken und Herzschlag in `mat_meta` unter
   Schreibsperre plus UNIQUE im Log: Arbeitsprozesse, Neustarts und Kommandozeile mahnen nie doppelt – außer, wenn ein
   Prozess genau zwischen der Annahme einer Mail und ihrem Vermerk endet; dann kommt diese eine Mail am nächsten
   Morgen noch einmal. Ausgefallene
   Tage holt der nächste Lauf nach (Fenster mit `<=`, höchste erreichte Stufe).
3. **Überfällig einmal je Fälligkeitsdatum**, nicht wiederholt – den Rest zeigt die Übersicht „Fällig“.
4. **Mailstufen 30/7 Tage fest**, unabhängig von „bald fällig“; Lebensdauer-Vorlauf 90 Tage fest (Konzept).
5. **Nur Artikel im Zustand frei mit Fälligkeit**; nie DEMO-Artikel, nie DEMO-Konten als Empfänger; Ordner mit
   „Erinnerungsmails aus“ (vererbt) fallen weg. (Der Probelauf zeigt DEMO auf Wunsch zur Ansicht – siehe „Neu“.)
6. **Empfänger**: Verwalter des Heimatordners über die Freigaben, sonst Material-Verwaltung, Rückfall
   Plattform-Verwaltung – wie bei Rückruf und Meldung; nur aktive Konten mit Namen und Modulzugang, jeder nur mit dem,
   was er sieht. Zugeordnete Personen bekommen keine Mails. (Anders als Rückruf und Meldung zählen Material- und
   Plattform-Verwaltung als Verwalter, wenn sie am Ordner eingetragen sind – siehe „Abweichungen“, Nr. 2.)
7. **Eine Mail je Empfänger und Tag**, Artikelstufen und ablaufende Freigaben zusammen, gruppiert nach Ordnerpfad, mit
   Links (`BASE_URL`) und Obergrenze (100 Artikel-, 50 Freigabezeilen; jede Gruppe erscheint).
8. **Log-Eintrag nur bei angenommener Mail** (sonst am nächsten Tag erneut), mit Kontoverweis statt Adresse;
   Aufbewahrung 13 Monate (täglich und bei jedem Start); Kontolöschen räumt die Zeilen des Kontos.
9. **„Erinnerungsmails aus“ je Ordner** im Dialog „Ordner bearbeiten“, Reiter „Ordner“, nur mit verwalten; vererbt
   auf Unterordner, Anzeige „Ohnehin aus – geerbt von …“ im Dialog und „aus – geerbt von …“ im Ordnerkopf; Änderung im
   Journal.
10. **Laufstand und Probelauf** für Material- und Plattform-Verwaltung: ganz unten auf der Übersicht als Zeile mit
    Textlink, kein Knopf im Kopf; was Handeln verlangt, zusätzlich gelb oben. Der Probelauf verschickt und
    protokolliert nichts.
11. **Ablaufmail für Freigaben**: nur befristete, einmal je Freigabe und Enddatum 30 Tage vorher (nach Verlängern neu),
    an die Verwalter des Ankers ohne den Inhaber (ohne Verwalter: Material- bzw. Plattform-Verwaltung); offene
    Prüfungen des Inhabers im Zweig werden genannt. **Geändert am 19.10.2026:** Der Inhaber bekommt sie zusätzlich
    selbst (siehe „Entscheidungen vom 19.10.2026“).

### Abweichungen vom Konzept, mit Begründung

1. **Kein nächtlicher Cron-Lauf** (Konzept: „flask material remind, nachts per Cron“), sondern ein eingebauter
   Tageslauf ab 6 Uhr plus derselbe Befehl auf der Kommandozeile – so entschieden: keine Arbeit auf dem VPS, Mails
   kommen morgens. Ein Cron mit `remind` ginge weiterhin und mahnte nicht doppelt.
2. **Empfänger mit Rückfall.** Laut Konzept die Verwalter des Ordners; ohne Verwalter hier die Material-Verwaltung,
   ohne sie die Plattform-Verwaltung, wie bei Rückruf und Meldung – sonst bliebe ein Bestand ohne Materialwart stumm.
   Anders als dort zählen Material- und Plattform-Verwaltung als Verwalter, wenn sie am Ordner eingetragen sind: Sonst
   fiele ein eingetragener Materialwart mit dieser Stufe heraus, und die ganze übrige Material-Verwaltung bekäme seine
   Gliederung täglich.
3. **Ablaufmails für Freigaben** sind neu (Vorgabe aus Lieferung 1), mit eigener Stufe in derselben Tabelle.
4. **`mat_reminder_log` neu aufgebaut**: Kontoverweis statt Adresse, Datum Pflicht, Freigaben, UNIQUE.
5. **„Erinnerungen konfigurieren“** heißt in dieser Lieferung: der Schalter je Ordner, vererbt. Feste Stufen ohne
   Einstellung, keine Abmeldung einzelner Verwalter, keine Wiederholung bei Überfälligkeit.
6. Die **Mailstufen sind fest** (30/7) und hängen nicht an der Einstellung „bald fällig“.
7. Ein **Pflegeteil** (Journal „Freigabe abgelaufen“, Aufräumen von Log und Suchprotokoll) läuft täglich, auch bei
   ausgeschaltetem Versand.

### Abweichungen vom Bauentwurf

- `veraltet` (gelber Hinweis „heute ist noch keiner gelaufen“) bleibt falsch, solange nie ein Mailteil lief – sonst
  stünde er gleich nach dem Einschalten bis zur nächsten Runde da. Ein Thread, der nie lief, fällt über den Hinweis zum
  Pflegeteil auf.
- Ein unklarer Wert in `MATERIAL_ERINNERUNGEN_SPERRE` (weder 1/true/yes/on noch 0/false/no/off) sperrt.
- Beim Rückfall werden Material- und Plattform-Verwaltung vorher auf zulässige Konten geschnitten (Adresse, kein
  DEMO, Modulzugang): Eine Material-Verwaltung ohne Adresse führt wie eine DEMO-Material-Verwaltung zur
  Plattform-Verwaltung.
- Mailtext: „(heute)“ und „(in 1 Tag)“; Fälligkeit und Lebensende eines Artikels in einer Zeile; nennt eine Mail nur
  Rückfallgruppen, entfällt „Du bekommst diese Mail, weil du diese Ordner verwaltest.“
- `reminders_off: null` im PUT gilt wie „nein“; unverändert bleibt der Wert nur, wenn das Feld fehlt.
- Der Probelauf liefert zusätzlich `fehlerhaft` und `smtp`, `letzter` dort auch `tag` und `fehler`; `remind --trocken`
  sagt, wenn der Versand aus oder gesperrt ist. Der Dialog sagt bei eingeschaltetem Versand ohne Mailserver „Kein
  Mailserver eingerichtet – so gingen sie hinaus, wenn einer eingerichtet wäre.“
- Oberfläche: Bei ausgeschaltetem Versand ohne je einen Lauf entfällt „noch kein Lauf“ in der Zeile. Die gelben
  Hinweise zu Fehlschlägen erscheinen nur bei eingeschaltetem, nicht gesperrtem Versand („geht morgen erneut“ stimmte
  sonst nicht). Der Probelauf-Dialog ist am Rechner 820 px breit (Mailzeilen), am Telefon wie jeder Dialog.

### Schnittstelle

Die neuen Routen stehen in der Tabelle „Schnittstelle“ unten (Zeilen mit „Phase 2 · 2“). An vorhandenen Antworten
ändert sich:

- `GET /api/material/start`: neu `erinnerungen` – der Laufstand (`versand`, `gesperrt`, `smtp`, `startzeit`, `laeuft`,
  `veraltet`, `pflege_veraltet`, `letzter` mit `tag`, `beginn`, `ende`, `ausloeser`, `mails`, `fehlgeschlagen`,
  `fehlgeschlagen_an` (Namen), `artikel`, `freigaben`, `ohne_empfaenger`, `ausgelassen`, `fehlerhaft`,
  `vermerk_fehler`, `fehler`; `pflege` mit `tag`, `abgelaufen`, `log`, `waisen`, `suche`, `fehler`). Zeitpunkte in UTC.
  Nur für Material- und Plattform-Verwaltung, sonst `null`.
- `GET /api/material/ordner/<id>`: `ordner.reminders_off` (eigener Wert) und `ordner.erinnerungen` = `{aus, eigen,
  geerbt_von: {id, pfad, sichtbar} | null}` (`sichtbar`: ob das Konto den Oberordner öffnen darf – sonst ohne Link);
  der Ordnerbaum liefert `reminders_off`.
- `PUT /api/material/ordner/<id>` nimmt `reminders_off` (ja/nein; fehlt = unverändert; anderes → 400 „„Erinnerungsmails
  aus“ muss ja oder nein sein.“).
- Journal: Ordner `geaendert` mit `{"reminders_off": 0 → 1}` („Erinnerungsmails aus“); neue Aktion
  `freigabe_abgelaufen` („Freigabe abgelaufen“, nur für Verwalter), im Verlauf von `GET …/ordner/<id>/freigaben` mit
  `konto`, `recht`, `bis`, `wer: "Tageslauf"`.
- Einstellung `MATERIAL_ERINNERUNGEN` (Gruppe „Material“, Art Schalter, Vorgabe aus) in `GET/PUT /api/admin/einstellungen`.
- `GET /api/material/erinnerungen/probelauf?demo=1` (Nachtrag vom 19.10.2026): bezieht den DEMO-Bestand ein (nur
  Ansicht; `demo` ja/nein, anderes → 400 „„DEMO-Bestand einbeziehen“ muss ja oder nein sein.“). Neu in jeder Antwort:
  `demo` (einbezogen ja/nein), `mails[].demo` (Mail mit DEMO-Empfänger oder DEMO-Einträgen – geht nie hinaus) und
  `ausgelassen.demo_freigaben` (ausgelassene DEMO-Freigaben neben `ausgelassen.demo`, den DEMO-Artikeln); mit `demo=1`
  sind beide Zahlen 0. Rechte unverändert (Material- und Plattform-Verwaltung). `remind --trocken --demo` zeigt
  dasselbe mit Adressen; `--demo` ohne `--trocken` → Exit 2. Der Laufstand (`/start`) bleibt, wie er war.
- `GET /api/material/erinnerungen/probelauf` (Entscheidungen vom 19.10.2026): neu `mails[].eigene` – wie viele eigene
  ablaufende Freigaben die Mail dem Empfänger nennt (Abschnitt „Deine Freigaben“); `mails[].freigaben` zählt nur noch
  die Freigaben, die er als Verwalter bekommt. Der Laufstand zählt die Mails an Inhaber unter `mails` mit.

### Verfahrensverzeichnis (Ergänzung)

Zweck „Erinnerung an Prüffristen und ablaufende Freigaben“. Empfänger: Verwalter des Ordners (auch Material- oder
Plattform-Verwaltung, wenn dort eingetragen); ohne Verwalter die Material-Verwaltung, ohne sie die
Plattform-Verwaltung; bei einer ablaufenden Freigabe zusätzlich ihr Inhaber, nur mit seiner eigenen (seit dem
19.10.2026). Inhalt: Artikel und Freigaben, die der Empfänger in der Anwendung ohnehin sieht, bei Freigaben der Name
des Inhabers, dem Inhaber die Namen von bis zu drei Verwaltern des Ankers (wie unter „Meine Freigaben“), nie eine
Adresse. Erinnerungslog: Artikel bzw. Freigabe, Stufe, Datum, pseudonymer
Kontoverweis, Zeitpunkt – 13 Monate (täglich und bei jedem Start durchgesetzt), Zeilen eines gelöschten Kontos
sofort. Der Laufstand hält nur Zahlen und die Kontoverweise der Fehlschläge des letzten Laufs.

### Im Browser geprüft

Chromium gegen einen lokalen Server **ohne `SMTP_HOST`**, mit einem Bestand ohne DEMO-Kennzeichen wie in den Tests
(Platzhalter: OG Musterstadt mit Lager, „Fahrzeug 1“ mit „Erinnerungsmails aus“ und Unterordner „Kiste A“, OG
Nachbarstadt ohne Materialwart, eine befristete und eine abgelaufene Freigabe), je bei 1280 px und 360 px, ohne
JavaScript-Fehler und ohne waagerechten Bildlauf:

- **Plattform-Verwaltung**: Zeile unten auf der Übersicht in allen Zuständen – aus, an ohne Mailserver, gesperrt
  (Server mit `MATERIAL_ERINNERUNGEN_SPERRE=1`) –, Probelauf heute und (nach einem Lauf heute) morgen; Einstellung
  „Erinnerungsmails verschicken“ mit Hilfetext, eingeschaltet über „Speichern“. Die gelben Hinweise sind mit einem
  in den Stand geschriebenen Lauf nachgestellt (Fehlschlag mit Namen, Fehler beider Teile – HTML im Fehlertext
  bleibt Text –, unlesbare Zeilen, nicht vermerkte Mail), „veraltet“ mit Mailserver über eine im Browser
  umgeschriebene Antwort von `/start` (lokal läuft nie ein Mailserver). „Einzelheiten unten“ springt zur Zeile.
- **Material-Verwaltung**: dieselbe Zeile; Probelauf mit Rückfallgruppe „kein Materialwart eingetragen“ (OG
  Nachbarstadt), der Mail des Materialwarts und „Ausgelassen: Erinnerungen aus in … Fahrzeug 1 (1 Artikel), … Kiste A
  (1 Artikel)“ mit Links; nur „Schließen“ (grau umrandet). Am Telefon bricht der Mailtext um und rollt im Kasten.
- **Materialwart** (verwaltet OG Musterstadt): keine Zeile, kein Hinweis auf der Übersicht. Kästchen im Dialog
  „Ordner bearbeiten“ an „Fahrzeug 1“ gesetzt, an „Kiste A“ leer mit „Ohnehin aus – geerbt von „OG Musterstadt /
  Fahrzeug 1““; Kopfzeile „Erinnerungsmails aus – geerbt von <Link>“. Am „Lager“ gesetzt: Rückfrage „ungespeicherte
  Änderungen“ beim Schließen aus dem Reiter „Freigaben“, nach „Speichern“ Kopfzeile und Journal („Erinnerungsmails
  aus: nein → ja“), danach wieder zurückgesetzt. Verlauf „„lesen“ von Eva Probe abgelaufen (bis 18.10.2026)“ von
  „Tageslauf“ – geschrieben vom echten Thread des lokalen Servers (Pflegeteil bei ausgeschaltetem Versand).
- **Mitglied** (nur lesen): keine Zeile, kein Hinweis, keine Kopfzeile im Ordner; `GET /erinnerungen/probelauf` 403.
- **DEMO im Probelauf** (Nachtrag vom 19.10.2026): derselbe Bestand plus `scripts/material_demo.py --demo --konten`
  (DEMO-Gliederungen, fünf DEMO-Konten), Server ohne `SMTP_HOST`, als Plattform- und als Material-Verwaltung bei
  1280 und 360 px. Ohne Haken: „Ausgelassen: … 3 DEMO-Artikel; 1 DEMO-Freigabe“ und das Kästchen. Mit Haken: gelber
  Hinweis, Mails an „DEMO-Material-Verwaltung“ und „DEMO-Materialwart A“ mit Marke „DEMO“, aufgeklappt „DEMO – geht
  nie hinaus“, Betreff „[DEMO] …“, Zeilen „· DEMO“; die Mails an „katalog“ und „wart“ unverändert ohne Marke. Zurück
  ohne Haken wie vorher; der Fokus bleibt am Kästchen; nur „Schließen“ (grau umrandet); kein waagerechter Bildlauf,
  keine Fehler in der Konsole. Materialwart: keine Zeile, kein Probelauf.

### Prüfung vor Auslieferung

- Bauentwurf vorher von zwei Kritiken geprüft („Betrieb“: 8 Befunde, „Fach“: 9 Befunde); alle übernommen –
  unter anderem eigene Fehlerbehandlung je Teil und Mail, die Sperre für dev ohne Handgriff auf dem VPS, Aufräumen auch
  beim Start, eigene Empfängerregel für eingetragene Material- und Plattform-Verwaltung, Kennzeichnung der
  Rückfallgruppen und der Probelauf für den nächsten Lauf.
- Neue Testdatei `tests/test_material_erinnerung.py` mit dem Testplan des Entwurfs (Migration, Stufen, Nachholen,
  Doppelläufe mit zwei Threads, Zeitzone und Zeitumstellung, Rechteschnitt, Fehler je Teil, Ordnerschalter,
  Freigaben, Journal, Mailtext und Obergrenzen, Schalter und Sperre, Aufräumen, Kontolöschen, Routen, Thread-Start,
  Einstellung); echte Mails gehen in keinem Test hinaus (`send_mail` ersetzt). Die ganze Suite läuft grün, `st-js`,
  `st-css` und `st-py` ohne neue Meldungen. Nachtrag vom 19.10.2026: `test_demo_probelauf` (ohne `demo` nichts aus
  DEMO, mit `demo=1` DEMO-Mails mit Kennzeichen und echte Mails unverändert, nichts geschrieben; `verschicken` und
  `vermerken` lehnen einen Plan bzw. eine Mail mit DEMO ab, auch eine einzelne DEMO-Mail in einem echten Plan;
  Tageslauf mahnt und vermerkt kein DEMO; `remind --demo` ohne `--trocken` → Exit 2, `--trocken --demo` mit Adressen).
  Unabhängige Prüfung des Nachtrags (Proben gegen eine Testdatenbank und im Browser): Ohne `demo` sind Probelauf,
  Mails, Log, Kontoverweise und Laufstand dieselben wie vor dem Nachtrag (bis auf die getrennte Zählung unter
  „Ausgelassen“); `demo=1` als POST, PUT, PATCH oder DELETE → 405, andere Werte als ja/nein → 400, kein Weg zu
  Versand, Log, Journal oder Laufstand (Thread, `remind`, `--erneut`). Ein Befund behoben: Wer den Dialog schloss,
  während er nach dem Umschalten neu lud, bekam ihn wieder geöffnet – jetzt bleibt er zu (mit statischem Test).

Nach dem Bau zwei unabhängige Prüfungen – Lauf (Mailtexte, Empfänger, Einmaligkeit mit Abbruch zwischen Annahme und
Vermerk, Kommandozeile, mit Skripten gegen eine Testdatenbank) und Browser (Rundgang als Plattform-Verwaltung,
Material-Verwaltung, Materialwart, Verwalter eines Unterordners und Mitglied, Server ohne `SMTP_HOST`) – haben 7 Befunde
gemeldet. Jeder ist vor der Behebung nachvollzogen worden (Skript, Anfrage oder Browser); alle sind behoben, die im
Code mit Test, die übrigen in der Dokumentation. Danach lief die ganze Suite grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Die Fußzeile „Für einen Ordner abschalten: … „Erinnerungsmails aus““ stand auch in Mails, die nur ablaufende Freigaben nennen – der Schalter am Ordner hält Freigaben aber nicht an | niedrig | Der Satz nur noch, wenn die Mail Artikel nennt (mit Freigaben dazu „Ablaufende Freigaben melden sich weiter.“); eine Mail nur mit Freigaben endet mit „Ablaufende Freigaben melden sich immer – auch in Ordnern mit „Erinnerungsmails aus“.“ Tests `test_mailtext` (nur Artikel, gemischt), `test_freigabe_ablauf` (nur Freigaben) |
| 2 | Lief die Freigabe des einzigen Materialwarts ab, bekam die Material-Verwaltung „kein Materialwart eingetragen“ und den Link „Materialwart vergeben“ – eingetragen ist aber einer, nur eben der Inhaber selbst | niedrig | Eigene Kennzeichnung: „– nur der Inhaber selbst verwaltet hier, darum an die Material-Verwaltung“, nur der Link „Verlängern“, Fußzeile entsprechend; gilt ebenso im Probelauf (gleicher Text). Test `test_freigabe_ablauf` |
| 3 | Die Zusage „Arbeitsprozesse, Neustarts und Kommandozeile mahnen nie doppelt“ gilt nicht, wenn ein Prozess zwischen der Annahme einer Mail und ihrem Vermerk endet (etwa beim Deploy-Neustart; der Thread ist ein Daemon) – dann kommt diese Mail am nächsten Morgen noch einmal | niedrig | Nachgestellt (Abbruch direkt nach der Annahme, zweiter Lauf am Folgetag: zwei gleiche Mails). Code unverändert – erst senden, dann vermerken ist Absicht, umgekehrt ginge eine Mahnung verloren. Die Zusage ist jetzt genau gefasst: „Neu“ (Einmaligkeit), Entscheidung 2, „Zu prüfen“ Nr. 18, README, Docstrings von `erinnerung.py`, `tageslauf.py` und `remind`, Bauentwurf 3.1 |
| 4 | Lief ein befristetes lesen oder verwalten ab, an dem eine dauerhafte Prüffreigabe hängt, nannte die Mail die offenen Prüfentwürfe nicht, obwohl das Prüfen mit dem Grundrecht endet (Vorgabe 11) | mittel | `freigaben_kandidaten` zählt bei befristetem lesen und verwalten die offenen Prüfungen in den Zweigen der dauerhaften Prüffreigaben des Kontos am Anker oder darunter („· 1 offene Prüfung“); ohne dauerhafte Prüffreigabe keine Angabe. Test `test_freigabe_ablauf` (beide Fälle), Bauentwurf 2.4 b |
| 5 | Wer nur einen Unterordner verwaltet, bekam im Ordnerkopf „Erinnerungsmails aus – geerbt von <Link>“ auf einen Oberordner, den er nicht öffnen darf – der Klick endete auf „404 – Ordner nicht gefunden“ | niedrig | `ordner_stand` liefert `geerbt_von.sichtbar` (`rechte.sicht().sichtbar`); ohne verlinkt der Kopf nicht, der Pfad steht als Text wie im Brotkrumen. Test `test_ordner_aus`; im Browser nachgesehen (Verwalter von „Kiste A“: Text ohne Link, Materialwart: Link; 1280 und 360 px, ohne Fehler in der Konsole) |
| 6 | Bei eingeschaltetem Versand ohne `SMTP_HOST` sagte der Probelauf „Heute ab 6 Uhr gingen hinaus:“ ohne Einschränkung – tatsächlich geht nichts hinaus | niedrig | Der Probelauf liefert `smtp`; der Dialog zeigt dann gelb „Kein Mailserver eingerichtet – so gingen sie hinaus, wenn einer eingerichtet wäre.“ (wie bei aus und gesperrt). Test `test_routen`; im Browser als Material-Verwaltung bei 1280 und 360 px nachgesehen |
| 7 | README nannte für Rückgabewert 2 nur „Versand aus, gesperrt oder kein Mailserver“ – `remind` gibt 2 auch bei `--stichtag` ohne `--trocken` und bei einem unlesbaren Datum | niedrig | README und Docstring von `remind`: „… oder falscher Aufruf (`--stichtag` ohne `--trocken`, unlesbares Datum)“; ebenso „Neu“ und „Zu prüfen“ Nr. 16 |

### Entscheidungen vom 19.10.2026

Der Betreiber hat am 19.10.2026 sieben Punkte aus „Zu prüfen“ entschieden – sechs bestätigt, einer geändert.

**Bestätigt** (bleibt, wie gebaut):

- Nr. 3 – **Der erste Lauf schickt den Rückstand**: alles, was schon in einem Fenster liegt, einmal; kein „stiller
  Start“.
- Nr. 4 – **Überfällig einmal je Fälligkeitsdatum**, keine Wiederholung.
- Nr. 11 – **„Erinnerungsmails aus“ hält Freigabe-Ablaufmails nicht an** – das gilt auch für die neue Mail an den
  Inhaber (unten).
- Nr. 14 – **Nachtrag „Freigabe abgelaufen“ beim ersten Lauf** (heutiges Datum, echtes Enddatum), auch bei
  ausgeschaltetem Versand.
- Nr. 15 – **DEMO-Konten erkennt man an der Adresse `….invalid`.**
- Nr. 18 – **Einmaligkeit mit einer Lücke**: Endet ein Prozess zwischen der Annahme einer Mail und ihrem Vermerk, kommt
  diese eine Mail am nächsten Morgen noch einmal (erst senden, dann vermerken).

**Geändert – Nr. 13, Ablaufmail und Inhaber.** Gebaut war: an die Verwalter des Ankers ohne den Inhaber; ist er der
einzige Verwalter, an die Material-Verwaltung. **Entscheidung:** „beide sollen eine Mail bekommen“. **Umgesetzt**
(`services/erinnerung.py`, `cli.py`, `static/material.js`):

- Der **Inhaber** einer befristeten Freigabe, die in höchstens 30 Tagen endet, bekommt sie **zusätzlich** zu den
  Verwaltern – in seiner täglichen Sammelmail im eigenen Abschnitt **„DEINE FREIGABEN, DIE BALD ABLAUFEN“**, vor
  Artikeln und Freigaben, die er als Verwalter bekommt. Je Anker steht der Ordnerpfad da, darunter je Freigabe Recht
  und Ende („lesen bis 22.11.2026 (in 20 Tagen)“), seine offenen Prüfungen im Zweig (dieselbe Zählung wie für die
  Verwalter, auch bei befristetem lesen oder verwalten mit daran hängender dauerhafter Prüffreigabe) und „Verlängern
  kann: Max Muster, wart oder Wilma Wartin.“ – bis zu drei Verwalter des Ankers mit Namen, genau wie unter „Meine
  Freigaben“ (`rechte.verwalter_von` ohne ihn selbst), ohne sie „die Material-Verwaltung“. Hat er dort offene
  Prüfungen, folgt „Offene Prüfungen schließt du am besten vor dem Ablauf ab – danach kannst du sie nicht mehr
  fortsetzen.“ Der einzige Link führt auf die Übersicht mit „Meine Freigaben“ (`/material`), die jeder mit
  Modulzugang öffnet – keiner in den Ordner, der nach dem Ablauf ins Leere führte. Er erfährt nichts, was „Meine
  Freigaben“ ihm nicht ohnehin zeigt: keine Adressen, keine Notiz, keine fremden Freigaben. Der Abschnitt hat keine
  Obergrenze (100/50 gelten weiter für Artikel und Freigaben der Verwalter) – es sind nur die eigenen.
- **Betreff und Text**: „strömis.de – Material: Deine Freigabe läuft ab“ (bei mehreren „2 deiner Freigaben laufen
  ab“), mit weiterem Inhalt „Deine Freigabe läuft ab, außerdem 1 in 7 Tagen fällig, 1 Freigabe läuft ab“. Eine Mail
  nur für den Inhaber beginnt mit „hier steht, welche deiner Freigaben im Modul Material bald ablaufen (Stand …) und
  wer sie verlängern kann.“ und endet mit „Du bekommst diese Mail, weil es deine eigenen Freigaben sind – einmal je
  Freigabe und Enddatum.“ – ohne Satz zu „Erinnerungsmails aus“, den Schalter bedienen Verwalter. In einer gemischten
  Mail sagt die Fußzeile zusätzlich „„Deine Freigaben“ bekommst du, weil es deine eigenen sind.“ (und „Ablaufende
  Freigaben melden sich weiter.“, wenn sie Artikel nennt).
- **Die Verwalter wie bisher**: Sie bekommen die Freigabe weiter, ohne den Inhaber; ist er der einzige Verwalter, die
  Material-Verwaltung (ohne sie die Plattform-Verwaltung) mit „nur der Inhaber selbst verwaltet hier“ und
  „Verlängern“ – jetzt bekommen **beide** eine Mail. Im Code geprüft: Wer nicht Material-Verwaltung ist, kann die
  eigene Freigabe nur verkürzen, herabsetzen oder entziehen (`freigaben._regeln`, Regel 1.6 Nr. 5: „Deine eigene
  Freigabe kannst du nur verkürzen, herabsetzen oder entziehen.“) – der Rückfall bleibt also nötig. Die
  Material-Verwaltung ist von dieser Regel ausgenommen (Nr. 1) und könnte die eigene verlängern – siehe „Zu prüfen“
  Nr. 20.
- **Nur einmal**: Als Verwalter bekommt der Inhaber die eigene Freigabe nie (er ist bei den Verwaltern ausgenommen wie
  bisher). Verwaltet er den Anker mit – etwa mit einer eigenen befristeten verwalten-Freigabe dort –, steht seine
  Freigabe in seiner Mail einmal, unter „Deine Freigaben“; die übrigen Freigaben des Ankers bekommt er als Verwalter.
  Haben zwei Konten dieselbe Adresse (nur Groß/klein verschieden), steht eine Freigabe unter „Deine Freigaben“ nicht
  noch einmal bei den Verwaltern und zählt im Betreff nur dort.
- **Dieselben Regeln wie für jeden Empfänger**: nur befristete Freigaben, die heute wirken; nur aktive Konten mit
  Namen, Modulzugang und Adresse; nie DEMO-Konten (`….invalid`) und nie Freigaben an DEMO-Ordnern – außer im Probelauf
  mit DEMO, dort gekennzeichnet. „Erinnerungsmails aus“ am Ordner hält auch diese Mail nicht an.
- **Einmal je Freigabe und Enddatum je Empfänger**: Der Inhaber bekommt einen eigenen Vermerk im Log (sein
  Kontoverweis, Stufe `freigabe_ablauf`, UNIQUE wie bisher – keine Schemaänderung). Nach „Verlängern“ meldet sich die
  Freigabe 30 Tage vor dem neuen Ende wieder, auch bei ihm. Seine Zeilen verschwinden wie alle: mit dem Konto, mit der
  Freigabe, nach 13 Monaten. Scheitert seine Mail, kommt sie am nächsten Morgen wieder.
- **Probelauf** (Dialog und `remind --trocken`, auch mit DEMO-Bestand) zeigt die Mails der Inhaber. Die Zeile je
  Mail nennt die eigenen Freigaben getrennt: „Erika Extern – 1 eigene Freigabe“, „Wilma Wartin – 1 Artikel, 1
  Freigabe, 1 eigene Freigabe“; eine Mail ohne eigene bleibt bei „n Artikel, m Freigaben“. `remind --trocken`:
  „An: Erika Extern <…> (0 Artikel, 0 Freigaben, 1 eigene Freigabe)“. Neues Feld `mails[].eigene` (siehe
  „Schnittstelle“); `mails[].freigaben` zählt nur noch die Freigaben, die er als Verwalter bekommt. Im Laufstand zählt
  `mails` die Mails an Inhaber mit, `freigaben` jede gemeldete Freigabe weiter einmal.
- Dazu: README (Empfänger), Hilfetext der Einstellung „Erinnerungsmails verschicken“ („wessen Freigabe abläuft,
  bekommt sie auch selbst“), „Neu“, Entscheidung 11 und Verfahrensverzeichnis oben, Kopf von `erinnerung.py`.
- **Tests**: `test_inhaber` (neu) – der Inhaber bekommt die Mail (ganzer Text), mit denselben Verwaltern, demselben
  Pfad und Ende wie unter „Meine Freigaben“; Probelauf mit `eigene` und `remind --trocken`; die Inhaberin, die den
  Anker mitverwaltet, bekommt ihre eigene einmal (unter „Deine Freigaben“) und die übrigen als Verwalterin, mit
  gemischtem Betreff; eigener Vermerk je Freigabe und Enddatum; am nächsten Tag nichts, nach Verlängern erneut; ein
  DEMO-Inhaber nie (im Probelauf mit DEMO gekennzeichnet), ein Inhaber ohne Adresse nie; „Erinnerungsmails aus“ am
  Anker hält nicht an; zwei Konten mit derselben Adresse; die Zeile im Dialog (statisch). Angepasst:
  `test_freigabe_ablauf` (Inhaber und Verwalter; einziger Verwalter → Inhaber und Material-Verwaltung; nach
  Verlängern beide), `test_ordner_aus`, `test_demo_probelauf` (Inhaber einer DEMO-Freigabe nur in der Ansicht),
  `test_gescheitert`, `test_kontoloeschen` (die Zeile des Inhabers geht mit Konto und Freigabe), `test_nachholen`.
- **Im Browser geprüft** (Chromium, lokaler Server ohne `SMTP_HOST`, Bestand ohne DEMO mit Platzhaltern: OG
  Musterstadt mit Lager, Materialwart „wart“ und „Max Muster“, Erika Extern mit befristetem lesen am Lager, Wilma
  Wartin mit befristetem verwalten am Lager, ein Artikel in 5 Tagen fällig), als Material-Verwaltung bei 1280 und
  360 px: Probelauf mit „Erika Extern – 1 eigene Freigabe“ und „Wilma Wartin – 1 Artikel, 1 Freigabe, 1 eigene
  Freigabe“, aufgeklappt Betreff und Text wie oben; als Erika bei 360 px nennt „Meine Freigaben“ dieselben Namen
  („Verlängern kann: Max Muster, wart oder Wilma Wartin.“). Keine Konsolenfehler, kein waagerechter Bildlauf.

### Zu prüfen

**Bitte bestätigen** (Vorgaben 1–11 oben sind gebaut wie formuliert; dazu die Folgen, die beim Bau festgelegt wurden).
Am 19.10.2026 entschieden: Nr. 3, 4, 11, 14, 15 und 18 bestätigt, Nr. 13 geändert (siehe „Entscheidungen vom
19.10.2026“); Nr. 20 und 21 sind danach dazugekommen.

1. **Schalter in der Vorgabe aus – bestätigt am 19.10.2026**, eingeschaltet wird in der Produktion **im Browser** (nicht in der `.env`, weil
   dev sie kopiert). Danach kommen die ersten Mails binnen 15 Minuten, dann jeden Morgen ab 6 Uhr.
2. **Ab 6:00 Uhr deutscher Zeit – bestätigt am 19.10.2026**, fest, einmal am Tag; ausgefallene Tage holt der nächste Lauf mit der höchsten
   erreichten Stufe nach.
3. **Der erste Lauf nach dem Einschalten schickt den Rückstand – bestätigt am 19.10.2026**: jeden schon überfälligen Artikel einmal, alles im
   7- und 30-Tage-Fenster und alles, was in 90 Tagen das Lebensende erreicht – höchstens 100 Zeilen je Mail, der Rest
   einer Gruppe als „… und n weitere“, gilt ebenfalls als gemahnt. Einen „stillen Start“, der den Bestand nur
   vermerkt, gibt es nicht.
4. **Überfällig nur einmal je Fälligkeitsdatum – bestätigt am 19.10.2026**; erneut frühestens nach 13 Monaten, wenn die Log-Zeile verfallen ist.
5. **Stufen 30/7 fest, Lebensende 90 Tage, Freigaben 30 Tage – bestätigt am 19.10.2026.** Weitere Stufen bräuchten einen Neuaufbau der Tabelle.
6. **Artikel ohne Fälligkeitsdatum bekommen keine Mail – bestätigt am 19.10.2026**; „neu“ wird nach dem Datum gemahnt, mit „Eingangsprüfung
   offen“.
7. **Wer neu Empfänger wird – bestätigt am 19.10.2026** (neuer Materialwart, Artikel verschoben), bekommt am nächsten Morgen einmal alles, was
   dort schon in einem Fenster liegt – das Log gilt je Empfänger.
8. **Empfänger auch Material- und Plattform-Verwaltung, wenn am Ordner eingetragen – bestätigt am 19.10.2026** (anders als bei Rückruf und
   Meldung), sonst Material-Verwaltung, sonst Plattform-Verwaltung, gekennzeichnet. Eine Plattform-Verwaltung ohne
   Namen bekommt nichts; ihre Artikel stehen im Probelauf unter „Ohne Empfänger“.
9. **Kein Link je Artikel – bestätigt am 19.10.2026**, ein Link je Ordner – die Mail bleibt lesbar. Die Stufenregeln stehen in der Hilfe der
   Einstellung, nicht in der Mail.
10. **Bei eingeschaltetem Versand ohne `SMTP_HOST` – bestätigt am 19.10.2026** wird nichts versucht (Hinweis auf der Übersicht).
11. **„Erinnerungsmails aus“ hält Freigabe-Ablaufmails nicht an – bestätigt am 19.10.2026** – Freigaben sind Rechte,
    keine Prüffristen; das gilt auch für die Mail an den Inhaber.
12. **Laufstand unten als Textlink – bestätigt am 19.10.2026**, Handlungsbedarf oben gelb; der Probelauf zeigt nach dem Morgenlauf den Lauf von
    morgen.
13. **Geändert am 19.10.2026 – der Inhaber bekommt jetzt auch eine Mail**, im Abschnitt „Deine Freigaben“, die
    Verwalter wie bisher (siehe „Entscheidungen vom 19.10.2026“). Gebaut war: **Ablaufmail ohne den Inhaber**, der die
    eigene Freigabe nicht verlängern kann; ist er der einzige Verwalter, geht
    sie an die Material-Verwaltung („nur der Inhaber selbst verwaltet hier“, mit „Verlängern“). Freigaben, die kürzer
    als 30 Tage laufen, melden sich am nächsten Morgen. Offene Prüfungen nennt die Mail auch beim Ablauf eines
    befristeten lesen oder verwalten, an dem eine dauerhafte Prüffreigabe hängt.
14. **„Freigabe abgelaufen“ – bestätigt am 19.10.2026**: Der erste Lauf trägt alle früher abgelaufenen Freigaben ins Journal nach (heutiges
    Datum, echtes Enddatum), auch bei ausgeschaltetem Versand.
15. **DEMO-Konten erkennt man an der Adresse `….invalid` – bestätigt am 19.10.2026** – neu; die Skripte vergeben nur solche.
16. **Kommandozeile – bestätigt am 19.10.2026**: `--stichtag` nur mit `--trocken`, `--erneut` für einen zweiten Mailteil am selben Tag; Exit 1
    bei Fehlschlag oder Fehler, 2 bei aus, gesperrt, ohne Mailserver oder falschem Aufruf.
17. **Sperre `MATERIAL_ERINNERUNGEN_SPERRE` – bestätigt am 19.10.2026** nur in der Umgebung; ohne Eintrag an, wenn `STROEMIS_NAME` auf `-dev`
    endet. Einen Notschalter nur für den Thread gibt es nicht.
18. **Einmaligkeit mit einer Lücke – bestätigt am 19.10.2026**: Endet ein Prozess genau zwischen der Annahme einer Mail und ihrem Vermerk (etwa
    beim Deploy-Neustart kurz nach 6 Uhr), kommt diese eine Mail am nächsten Morgen noch einmal. Umgekehrt (erst
    vermerken, dann senden) ginge bei einem Abbruch eine Mahnung verloren – das schien schlechter.
19. **DEMO im Probelauf nur zur Ansicht – bestätigt am 19.10.2026** (Nachtrag): Das Kästchen erscheint nur, wenn DEMO ausgelassen wurde. Mit
    Haken zählen auch DEMO-Konten als Empfänger und im Rückfall – eine DEMO-Material-Verwaltung bekommt dann auch die
    echten Gruppen „kein Materialwart eingetragen“ (gekennzeichnet). Der echte Lauf bleibt ohne DEMO.
20. **Material-Verwaltung als Inhaberin – bestätigt am 19.10.2026** (zu Nr. 13): Läuft eine eigene befristete Freigabe eines Kontos mit Stufe
    Verwaltung ab (für sie zählt praktisch nur eine Prüffreigabe), sagt ihre Mail wie „Meine Freigaben“ „Verlängern
    kann: … / die Material-Verwaltung“ – tatsächlich kann sie die eigene selbst verlängern (Regel 1.6 Nr. 1). Die
    übrige Material-Verwaltung bekommt die Freigabe trotzdem, wenn am Anker niemand sonst verwaltet. Belassen, damit
    Mail und „Meine Freigaben“ dasselbe sagen.
21. **Externe Prüfer bekommen jetzt Mails – bestätigt am 19.10.2026** (zu Nr. 13): Wer nur eine befristete Prüffreigabe hat, bekommt 30 Tage vor
    ihrem Ende eine Mail – erstmals überhaupt eine Erinnerungsmail aus dem Modul. Die migrierten Prüffreigaben externer
    Prüfer enden alle am 31.12.2027 (Phase 2 · Lieferung 1, „Zu prüfen“): Ohne Verlängern bekommt am 01.12.2027 jeder
    von ihnen eine Mail mit allen seinen Ordnern, dazu die Materialwarte ihre.

**Nach dem Deploy**:

- **Auf dev**: Material → Übersicht (als Material- oder Plattform-Verwaltung) zeigt ganz unten „Erinnerungsmails: in
  dieser Umgebung gesperrt“. „Probelauf ansehen“: ohne Haken nichts aus DEMO – DEMO wird absichtlich nie gemahnt;
  „Ausgelassen: n DEMO-Artikel; n DEMO-Freigaben“. Dann das Kästchen **„DEMO-Bestand einbeziehen (nur Ansicht)“**
  anhaken: Die Mails an die DEMO-Materialwarte und die DEMO-Material-Verwaltung erscheinen mit Marke „DEMO“ –
  aufklappen und Betreff und Text ansehen; wer eine befristete DEMO-Freigabe hat, die in 30 Tagen endet, steht dort
  mit „… eigene Freigabe“ (Abschnitt „Deine Freigaben“, Entscheidung vom 19.10.2026). Hinaus gehen sie nie (auf dev
  sperrt ohnehin die Sperre). Gelb oben „Der
  tägliche Lauf … ist noch nie gelaufen“ verschwindet nach der ersten Runde (1–3 Minuten nach der ersten Anfrage, ab
  6 Uhr).
- **In der Produktion nach dem Merge**: erst den Probelauf ansehen (oder `remind --trocken`), dann unter Verwaltung →
  Einstellungen „Erinnerungsmails verschicken“ einschalten. Am nächsten Tag die Zeile auf der Übersicht ansehen
  (Uhrzeit, Zahl der Mails, Fehlschläge).
- **Produktionsdatenbank auf dev**: Die Sperre schützt vor Mails; `EINSTELLUNGEN_AUS=1` dazu, damit Mailserver und
  `BASE_URL` der Produktion nicht gelten.
- **Verfahrensverzeichnis** um den Abschnitt oben ergänzen.
- **Nicht in dieser Lieferung**: CSV-Import, Wiki-Verknüpfung (Lieferung 3), Mails an zugeordnete Personen, „Meine
  PSA“.

## Phase 2 · Lieferung 3 – Bestandsimport und Prüfanleitung (19.10.2026)

Lieferung 3 bringt zwei Punkte aus dem Konzept: den **Bestandsimport** – vorhandene Bestandslisten aus Excel oder CSV
in einen Ordner übernehmen, mit Probelauf und einer Nacharbeit für alles, was nicht sicher passt – und die
**Prüfanleitung aus dem Wiki** am Prüfformular, deren Abschnitt „Prüfung“ in offenen Prüfungen eingeblendet wird.
Gebaut nach dem Bauentwurf vom 19.10.2026 (zweite Fassung nach zwei Kritiken, „Fach“ und „Sicherheit“, mit den
Entscheidungen des Betreibers vom selben Tag) in zwei Paketen: KERN (Schema, Dienste, Routen, Tests) und OBERFLÄCHE
(Importseite mit Nacharbeit, Formularzeile, Einblendung in der Prüfung, Doku). Schemaversion 12, keine neuen
Abhängigkeiten. Stand: wartet auf Freigabe.

### Neu

- **Bestandsimport** (`services/tabelle.py`, `services/bestandsimport.py`, `routes_import.py`; Oberfläche in
  `material.js`, Ansicht `bestandsimport`): Wer einen Ordner verwaltet, findet im Ordnerkopf das Untermenü
  **„Export / Import“** (für alle anderen weiter „Export“) mit „Bestandsliste importieren …“ und, solange etwas offen
  ist, „Nacharbeit (n offen)“. Beide führen auf die Seite `/material/ordner/<id>/import` (Pfad „Bestand / … / Import“).
  - **Dateien**: Excel-Arbeitsmappe (.xlsx, erstes Blatt mit Inhalt) oder CSV (UTF-8 mit oder ohne BOM, sonst
    Windows-1252 wie deutsches Excel, UTF-16 mit BOM; Trennzeichen `;`, `,` oder Tab erkannt). Höchstens 5 MB, als
    xlsx entpackt 10 MB, als CSV 10 000 Zeilen bzw. 600 000 Felder – geprüft, **bevor** die Datei geladen wird; dann
    2000 Datenzeilen, 300 Spalten, Kopfzeile in den ersten 40 Zeilen. Alte .xls, .ods, PDF und Bilder werden am
    Dateikopf erkannt und mit einem Satz zum richtigen Speichern abgelehnt.
  - **Probelauf sofort** nach der Wahl (oder dem Hineinziehen) der Datei, mit automatischer Spaltenzuordnung:
    Synonyme mit Rangfolge (Modell vor Typ vor Bezeichnung, Seriennummer vor Hersteller, Artikelnummer vor Modell),
    mehrere Spalten in die Bemerkung („Größe: M“, „Standort: MTW“), Personenspalten (Ausgegeben an, Telefon …) lassen
    sich keinem Feld zuordnen. Die Zuordnung steht als Tabelle (am Telefon als Karten) mit Beispielen und Auswahl je
    Spalte; eine Änderung startet den Probelauf nach 600 ms Ruhe neu, eine laufende Anfrage bricht dabei ab, und bis
    zum neuen Ergebnis ist „Übernehmen“ gesperrt. Eine eigene Nacharbeits-CSV wird erkannt („Nacharbeits-CSV erkannt –
    Spalten zugeordnet“, „Zuordnung ändern“). Ist keine Spalte als Seriennummer zugeordnet, gibt erst ein Häkchen
    direkt über „Übernehmen“ den Knopf frei (Entscheidung vom 20.10.2026, siehe unten).
  - **Ergebnis** vor dem Übernehmen: Hinweise (schon importiert, Bezeichnung nicht als Modell, unbekannte Ordner mit
    Zahl der Zeilen, „n Zeilen ohne Seriennummer – bekommen eine STR-Nummer …“), „Produkte, die der Katalog nicht
    sicher kennt“ (je Angabe mit Zahl und Art), Fälligkeit (laut Liste überfällig, ohne Prüfdatum sofort fällig,
    Lebensdauer erreicht) und die Zeilen nach Reitern „übernehmbar“, „schon im Bestand“, „Nacharbeit“, „schon
    erledigt“ (je 100, „weitere …“) mit Produkt, Seriennummer, Ordner, Fälligkeit, Gründen (rot) und Hinweisen (grau),
    Rückrufe als rote Marke.
  - **„Übernehmen: n Artikel anlegen, m Zeilen in die Nacharbeit“** – der eine rote Knopf der Seite – schreibt in einer
    Transaktion: übernehmbare Zeilen werden Artikel (Nummern in Dateireihenfolge), der Rest kommt in die Nacharbeit.
    Danach die Tabelle **„angelegt“** mit Zeile, neuer Inventarnummer (Link), bisheriger Nummer, Seriennummer (vom
    System vergebene STR-Nummern mit „(System)“) und Fälligkeit – zum Beschriften –, dazu „Alte Inventarnummern stehen
    in der Bemerkung und sind nicht suchbar …“. Importierte Artikel stehen auf **„neu“**; die Fälligkeit kommt aus
    „nächste Prüfung“ bzw. „zuletzt geprüft“ + Intervall (höchstens heute + Intervall), ohne beides ist die
    Eingangsprüfung sofort fällig. Was schon im Bestand ist (Produkt und Seriennummer), wird erkannt und übersprungen;
    dieselbe Datei in denselben Ordner innerhalb von 10 Minuten wird abgelehnt.
  - **Nacharbeit** (Abschnitt derselben Seite, eine Liste je Zielordner über alle Importe dorthin): Karten je
    Produktangabe mit „Produkt zuordnen …“ (Vorschläge und Produktsuche) und – für Materialwarte – „Produkt melden …“
    (die vorhandene Meldung, vorbelegt, mit Link zur Nacharbeit in der Mail nach dem Einpflegen) bzw. – für die
    Material-Verwaltung – „Im Katalog anlegen …“ (der Produktdialog, vorbelegt; danach wird das neue Produkt der
    Angabe zugeordnet, die Seite bleibt stehen). Darunter die offenen Zeilen mit Kästchen, Nacharbeit-Nr., „Datei ·
    Zeile n“, den Gründen als Liste, den wichtigsten Werten, „alle Werte“ und „offen bis …“; Filter nach Grund
    (Produkt, Seriennummer, Daten, Ordner, Sonstige); je Seite 200, „weitere …“. Die Sammelleiste (klebt unten) hat
    „alle n offenen auswählen“, „Produkt zuordnen …“ (auch zeilenweise – Größen und Varianten), „Erneut prüfen“ (erst
    das Ergebnis, dann „n Artikel übernehmen“ mit der Tabelle der neuen Inventarnummern) und „Verwerfen“ (Rückfrage).
    „Mehr → Als CSV herunterladen“ liefert die offenen Zeilen mit „Nacharbeit-Nr.“; korrigiert und hier wieder
    hochgeladen, erledigt die Datei die alten Zeilen in derselben Transaktion – zweimal hochgeladen legt sie nichts
    doppelt an. „Zuletzt erledigt“ zeigt die letzten 100 mit wer und wann. **Offene Zeilen verfallen einen Monat nach
    dem Import** (Startschritt und Tageslauf; danach verworfen, Werte gelöscht, „System“).
  - **Hinweise**: im Ordnerkopf „Aus einem Bestandsimport warten n Zeilen auf Nacharbeit. Nacharbeit öffnen“ (nur für
    Verwalter), auf der Übersicht „Nacharbeit aus Bestandsimporten: <Ordnerpfad> (n), …“ mit Links.
  - Alles aus der Datei (Spaltentitel, Beispiele, Werte, Ordner, Gründe, Hinweise) ist reiner Text und geht nur
    maskiert in die Seite.
  - Ein Import je Arbeitsprozess gleichzeitig; sonst „Gerade läuft ein anderer Bestandsimport – bitte in einem Moment
    noch einmal.“ mit „Erneut versuchen“. Zu große Dateien sagt die Seite schon vor dem Hochladen.
- **Prüfanleitung aus dem Wiki** (`services/wikiverweis.py`, `routes_wiki.py`; Oberfläche in `material.js`):
  - **Am Formular**: Die Material-Verwaltung sieht unter dem Titel „Prüfanleitung im Wiki: <Titel>“ (Link, graue Marke
    der Reichweite „öffentlich“, „intern“ oder „beschränkt“ mit Hinweis, wer sie nicht sieht), „Seite Nr. n – du darfst
    sie nicht lesen“, „Die verknüpfte Seite liegt im Wiki-Papierkorb.“ oder „keine“. **„Ändern …“** öffnet die
    Seitenwahl (Titelsuche über die Seiten, die man im Wiki lesen darf, „Verknüpfen“, „Verknüpfung entfernen“) – nur
    mit Stufe Mitglied im Wiki; ohne sie steht dort „Verknüpfen kann, wer im Wiki mindestens Mitglied ist.“ Auch an
    benutzten Versionen (die Verknüpfung gehört nicht zum Prüfinhalt); neue Versionen und der Katalogimport erben sie.
  - **In offenen Prüfungen** steht im Kopf „📖 Prüfanleitung aus dem Wiki: <Titel>“ zum Aufklappen. Beim ersten
    Öffnen holt die Seite die Wiki-Seite über den Endpunkt des Wikis selbst (mit dessen Rechten, ohne als Besuch zu
    zählen) und blendet den **Abschnitt „Prüfung“** ein – die erste Überschrift h1–h5 „Prüfung“ (auch „Prüfung:“) bis
    zur nächsten gleich hohen –, darunter immer „Ganze Seite im Wiki öffnen ↗“. Ohne solchen Abschnitt: „Die Seite hat
    keinen Abschnitt „Prüfung“ – bitte im Wiki lesen.“ und der Link. Der Kasten ist höchstens 60 % der Fensterhöhe
    hoch und rollt in sich, breite Tabellen rollen seitlich. Wer die Seite nicht lesen darf, sieht nur „Zu diesem
    Formular gibt es eine Prüfanleitung im Wiki, die du nicht lesen darfst.“ – ohne Titel. An abgeschlossenen Prüfungen
    erscheint nichts; festgehalten wird die Seite nirgends (kein Protokoll, kein PDF, nur die Seitennummer im Journal
    des Formulars).
  - **Abgeschirmt**: Der Abschnitt wird nach dem Rendern wie im Wiki ein zweites Mal streng gereinigt (keine ids,
    Namen, `data-*`, Formularelemente, Labels, Stile), im `<template>` ausgeschnitten und in einen geschlossenen
    Shadow-Root gesetzt. Die Klick-Delegation der Prüfansicht übergeht die Einblendung, Festschreiben liest Grund,
    Datum und Bemerkung nur aus den eigenen Feldern.
- Journal-Beschriftungen (Bestandsimport, Nacharbeit übernommen/verworfen, Prüfanleitung (Wiki) geändert) gleich in
  Oberfläche und Lebenslauf-PDF.

### Migration

- **Schritt 12**, Schemaversion 12, läuft beim Start von selbst, rein additiv und wiederholbar (ein zweiter Lauf ändert
  nichts): neue Tabellen `mat_import` (ein Lauf „Übernehmen“: Zielordner, Dateiname, SHA-256, Art, Zahlen, wer, wann)
  und `mat_import_row` (Zeile der Nacharbeit: Werte, Gründe, Produktangabe, Wahl, Meldung, Status mit „ersetzt“; offen
  ⇔ ohne `resolved_at`, UNIQUE je Import und Zeile), beide mit AUTOINCREMENT; Spalte `mat_form.wiki_page_id`
  (`ON DELETE SET NULL`) mit Teilindex.
- Geprüft: frische Datenbank, 11→12, 7→12 (Trennungstest) und 1→12 (Altbestand); einmalig an einer Kopie des Stands 7
  über `create_app` bis 12 (Fremdschlüssel und `integrity_check` in Ordnung, Formulare und Artikel unverändert).
- **Rückweg**: Eine Fassung mit Schemaversion 11 übergeht die neuen Tabellen und die Spalte. Sie zeigt weder
  Nacharbeit noch Anleitung, neue Formularversionen erben die Verknüpfung nicht, und ein Ordner mit offener Nacharbeit
  ließe sich dort löschen (die Nacharbeit verschwände mit).
- Keine Handarbeit beim Update: `docker compose up -d --build` genügt.

### Neue Abhängigkeiten

Keine (openpyxl kommt aus dem Prüfungsimport, marked und DOMPurify liegen schon unter `app/static/vendor`).

### Entscheidungen

Entschieden bzw. bestätigt am 19.10.2026 – die Entscheidungen des Betreibers vor dem Bau:

1. **Importierte Artikel stehen immer auf „neu“**, bis sie im System geprüft sind – kein „Prüfstand aus der Liste“.
2. **Wiki-Verknüpfung nur am Prüfformular** – nicht am Produkt, nicht am Prüfpunkt; beim generischen Formular ist sie
   die Anleitung der ganzen Kategorie.
3. **In der Prüfung wird der Abschnitt „Prüfung“ eingeblendet** (aufklappbar) plus Link zur ganzen Seite; ohne
   Abschnitt nur der Link. Kein wählbarer Abschnitt, kein Anker.
4. **Die Wiki-Seite wird beim Festschreiben nicht festgehalten**; eingeblendet nur in offenen Prüfungen.
5. **Monatsangabe in einem Tagesfeld** („03/2027“) gilt als 1. des Monats, mit Hinweis.
6. **Zeilen mit laufendem Rückruf werden mit Hinweis übernommen**; der Artikel trägt danach das Banner.
7. **Nur „letzte Prüfung“ in der Liste**: Fälligkeit = letzte Prüfung + Intervall, höchstens heute + Intervall;
   laut Liste Überfällige stehen in der nächsten Erinnerung.

Die Liste „Bitte bestätigen“ des Bauentwurfs (20 Punkte) – bestätigt am 19.10.2026, mit **drei Änderungen**:

- **Geändert (Nr. 5)**: **Zeilen ohne Herstellerseriennummer brauchen keinen Haken mehr** – sie bekommen beim
  Übernehmen automatisch eine Seriennummer vom System (STR-…) wie beim Anlegen von Hand. Der Probelauf nennt die Zahl,
  das Ergebnis listet die vergebenen Nummern mit Inventarnummer. Doppeltes Anlegen begrenzen weiter die 10-Minuten-
  Sperre derselben Datei und die Nacharbeit-Nr. der Nacharbeits-CSV.
- **Geändert (Frist)**: **Offene Nacharbeit verfällt nach einem Monat** statt nach 12 Monaten. Der Betreiber schrieb
  „reduziere auf 1 Monat“ bei Nr. 12; gemeint ist die 12-Monats-Frist aus Nr. 13 (Nr. 12 hat keine Frist). Die
  Oberfläche nennt die Frist und je Zeile „offen bis …“.
- **Geändert (Nr. 18)**: **Verknüpfen darf nur die Material-Verwaltung mit mindestens Stufe Mitglied im Wiki** (die
  Plattform-Verwaltung hat sie überall); ohne Wiki-Stufe sieht sie die Verknüpfung und einen Hinweis statt
  „Ändern …“, die Schnittstelle antwortet 403 mit Klartext.

Bestätigt, wie im Entwurf: nur mit „verwalten“ am Zielordner, Ordnerspalte als Pfad unter dem Ziel (Standort und
Lagerort werden Bemerkung) (Nr. 1); Einstieg im Untermenü „Export / Import“, eigene Seite, Hinweise im Ordnerkopf und
auf der Übersicht (2); Probelauf beim Wählen, Produkte erst in der Nacharbeit zuordnen (3); Übernehmen in einer
Transaktion, alte Inventarnummern nur in der Bemerkung (4); wiederholbar ohne Aktualisierung, 10-Minuten-Sperre (5,
ohne den Haken); ohne Prüfdatum sofort fällig (6); nur Pflicht- und Sicherheitswerte blockieren, nichts wird erfunden
(7); Intervall nur kürzer, Lebensende nur früher (8); Sammelzeilen in die Nacharbeit (9); Seriennummern aus
Excel-Zahlen mit mehr als 15 Stellen in die Nacharbeit (10); kurze Seriennummern nie angelegt, fremde Dubletten ohne
Merkmale mit einer Protokollzeile je Lauf (11); Spaltenregeln, „Prüffrist“ und „Bestellnummer“ nicht automatisch (12);
Nacharbeit je Zielordner, Werte nur über die CSV (13, mit der Frist von einem Monat); Melden bzw. „Im Katalog anlegen
…“ (14); Grenzen (15); Datenschutz und Löschen – Dateiname nur am Import und im Ordnerjournal, Namen beim Kontolöschen
„(gelöschtes Konto)“, Ordner mit offener Nacharbeit nicht löschbar (16); kein Import über die Kommandozeile, keine
Aktualisierung, keine Produkt- oder Ordneranlage durch den Import (17); jeder sieht im Wiki nur, was er lesen darf,
neue Konten nur öffentliche Seiten (18, mit der Änderung oben); benutzte Formulare: Verknüpfung änderbar ohne neue
Version, vererbt, nicht im Katalogaustausch (19); Einblendung der ersten Überschrift „Prüfung“, Bausteine nur als
Hinweis, Aufgabenlisten ohne Kästchen (20).

### Abweichungen vom Konzept, mit Begründung

1. **Auch .xlsx, nicht nur CSV** – Materialwarte haben Excel-Listen; „Speichern unter CSV“ verliert Kodierung und
   Seriennummern (1,23E+11, führende Nullen).
2. **Produktabgleich nicht nur über Hersteller und Modell**: zuerst der Dublettenschlüssel, dann die katalogweit
   eindeutige Artikelnummer, Hersteller + Modellname nur bei genau einem Produkt des Herstellers – Varianten wären
   sonst mehrdeutig. Nie raten.
3. **Nacharbeit für jede Zeile, die nicht sicher übernehmbar ist** (Produkt, Pflichtangaben, Dubletten, Ordner,
   Sammelzeilen), gespeichert als Tabelle.
4. **Teilübernahme**: Übernommen wird, was passt; der Rest wartet (anders als der Katalogimport).
5. **Prüfdaten aus der Liste**: Artikel stehen auf „neu“, die Fälligkeit kommt aus der Liste.
6. **Alte Inventarnummern** nur in der Bemerkung (keine eigene, suchbare Spalte).
7. **Wiki am Formular statt am Produkt**; eingeblendet im Browser über die Endpunkte des Wikis; keine Anzeige
   „verwendet im Modul Material“ im Wiki.
8. **Wiki-Verknüpfung an benutzten Formularen änderbar** ohne neue Version.
9. **Produkte werden in der Nacharbeit zugeordnet**, nicht schon im Probelauf – diese Artikel bekommen ihre Nummern
   erst dort, also nicht in Dateireihenfolge.

### Abweichungen vom Bauentwurf

Paket KERN (Bauentwurf, Abschnitt 10):

1. `mat_import_row.reason_code` hält alle Codes der Zeile, mit „,“ getrennt und nach Gruppe geordnet – so trägt die
   Nacharbeit die Gründe als Liste wie der Probelauf.
2. Über 5 MB lehnt schon das Lesen mit 413 ab (der Rahmen von `size_guard` ließe 5 MB + 1 Byte sonst durch).
3. Die Frist der Nacharbeit läuft außer beim Start auch in jeder Runde des Tageslaufs (bei einem Monat käme der
   nächste Start zu selten); `services/erinnerung.py` bleibt unberührt.
4. Zusätzlich an der Schnittstelle: `frist`, `offen_bis`, `hinweise` beim erneuten Prüfen, `formular.wiki_aendern`.
5. Spaltentitel werden auch ohne Umlaute verglichen („Pruefdatum“), dazu wenige Synonyme mehr („artikel nr“,
   „art.nr“, „hersteller seriennummer“, „lfd.-nr“).
6. „Nacharbeit-Nr.“ steht in `spalten` als „ignorieren“, gelesen wird sie immer aus ihrer Spalte; dieselbe Nummer
   zweimal: nur die erste Zeile ersetzt die alte; inzwischen erledigt → 409.
7. Grenzen der Nacharbeit: höchstens 2000 Zeilen je Aktion, 100 Produktkarten; „alle“ ohne Offenes → 409.
8. Doppelt beim erneuten Prüfen nennt die Nacharbeit-Nr. statt der Zeilennummer.
9. Innere Aufteilung (Klasse `Lauf`, `zeilen_pruefen`) statt der Signatur `zeile_pruefen(…)`.
10. In der Seitenwahl ist `lesemodus` immer falsch (ohne Wiki-Stufe gibt es sie nicht mehr); die Formularansicht zeigt
    der Material-Verwaltung die Verknüpfung auch ohne Wiki-Stufe.
11. Ordner löschen prüft offene Nacharbeit nur am Ordner selbst.

Paket OBERFLÄCHE:

1. **Link in der Formularzeile**: `formular.wiki` trägt zusätzlich `url` („/wiki/<slug>“, nur bei „ok“) – die
   Schnittstelle 8.5 hatte keinen, der Entwurf (4.4) verlangt „<Titel> mit Link“. Python-Änderung in
   `wikiverweis.editor_json` mit angepasstem Test.
2. **Einzahl im STR-Satz** („1 Zeile ohne Seriennummer – bekommt …“, „1 Artikel … hat …“) – vorher „1 Zeilen“;
   behoben in `bestandsimport._hinweis_ohne_serie` mit Test.
3. Nach einer geänderten Zuordnung ist „Übernehmen“ gesperrt, bis der neue Probelauf da ist (seine Zahlen gehörten
   sonst zur alten Zuordnung); dazu der Textlink „Zuordnung wie erkannt“.
4. Eine Nacharbeits-CSV, deren Zeilen inzwischen alle im Bestand stehen, zeigt „Übernehmen: Nacharbeit abgleichen
   (nichts anzulegen)“ – sonst blieben die alten Zeilen offen.
5. „Erneut prüfen“ mit nur „schon im Bestand“ bietet „m Zeilen als „schon im Bestand“ erledigen“ an (rot); der
   Entwurf kannte nur „n Artikel übernehmen“.
6. Nach dem Übernehmen ersetzt der Reiter „angelegt“ den Reiter „übernehmbar“ und ist die Tabelle „Angelegt“ (keine
   zweite Tabelle darüber).
7. Die Karte einer Meldung sagt „Gemeldet – die Material-Verwaltung nimmt das Produkt auf.“ ohne Datum (die
   Schnittstelle liefert keins); „Produkt melden …“ steht auch nach einer abgelehnten Meldung wieder da.
8. Alte HTML-Seiten im Wiki: „Diese Seite lässt sich hier nicht einblenden – bitte im Wiki lesen.“ und der Link.
9. Die strenge Reinigung nimmt auch `target` weg; jeder Link im Abschnitt bekommt danach `target="_blank"
   rel="noopener noreferrer"`.
10. Ergebnis- und Filterreiter brechen am Telefon um wie im Ordner (statt seitlich zu rollen).

### Schnittstelle

Die neuen Routen stehen in der Tabelle „Schnittstelle“ unten (Zeilen mit „Phase 2 · 3“). An vorhandenen Antworten
ändert sich:

- `GET /api/material/start`: neu `nacharbeit` = `[{ordner: {id, pfad}, offen}]` – Zielordner mit offener Nacharbeit,
  die das Konto verwaltet (höchstens 20, sonst `[]`).
- `GET /api/material/ordner/<id>`: neu `ordner.nacharbeit` – Zahl offener Zeilen mit diesem Ziel, nur mit verwalten
  (sonst `null`). `DELETE` antwortet 409, solange dort Nacharbeit offen ist.
- `GET /api/material/pruefungen/<id>`: neu `anleitung` = `{titel, url, quelle}` | `{kein_zugang: true}` | `null` (an
  abgeschlossenen Prüfungen immer `null`).
- `GET /api/material/formulare/<id>`: neu `formular.wiki` = `{seite, titel, url, reichweite, zustand}` | `null` (nur
  für die Material-Verwaltung) und `formular.wiki_aendern`.
- Journal: Ordner `bestandsimport` (Import Nr., Datei, Zeilen, angelegt, schon im Bestand, Nacharbeit, neu
  eingelesen), `nacharbeit_uebernommen`, `nacharbeit_verworfen`; Artikel `angelegt` mit `bestandsimport`, `zeile` und
  den Werten „laut Liste“ (ohne Dateinamen); Formular `wiki` (nur die Seitennummer).
- Meldung aus der Nacharbeit: Die Mail an den Melder nach dem Einpflegen verlinkt die Nacharbeit statt „Artikel
  anlegen“.

### Messwerte

Beim Bau gemessen (KERN, Proben außerhalb des Repositorys):

| Fall | Ergebnis | Zeit | Speicher (maxRSS) |
| --- | --- | --- | --- |
| Zip-Bombe aus der Sicherheitskritik, auf 4,87 MB verkleinert (51 MB XML) | 400 „entpackt 49 MB … höchstens 10 MB“, ohne openpyxl | 0,10 s | 84 MB (vorher mit openpyxl: 2,67 GB bei 14,8 MB) |
| dieselbe Bombe mit 11,8 MB (126 MB XML) | 413 vor dem Lesen | 0,00 s | – |
| zulässige Grenze: xlsx mit 9,9 MB XML | von openpyxl gelesen (Probedaten ohne Kopfzeile → 400) | 2,5 s | 222–239 MB |
| CSV 5 MB „a\n“ | 400 nach 10 000 Zeilen | 0,12 s | 105 MB (vorher bei 25 MB: 1,47 GB) |
| CSV 5 MB, 299 Spalten je Zeile | 400 nach 600 000 Feldern | 0,19 s | 136 MB |
| 2000 Zeilen | Probelauf / Übernehmen | 0,8 s / 1,3 s | 10 bzw. 29 Abfragen je Zeile |
| Kopie des Stands 7 → 12 über `create_app` | Version 12, Fremdschlüssel und `integrity_check` in Ordnung | – | – |

### Im Browser geprüft

Chromium gegen einen lokalen Server **ohne `SMTP_HOST`** mit Platzhalter-Katalog (Testwerk HMS Beta, Gurt Alpha, Gurt
Sigma in zwei Varianten), -Bestand (OG Musterstadt mit Lager, Fahrzeug 1, Kiste A) und -Wiki (öffentliche Anleitung
mit Abschnitt „Prüfung:“, Kasten, Liste und breiter Tabelle; Seite ohne Abschnitt; interne Seite; Probeseite), bei
1280 und 360 px, ohne Fehler in der Konsole und ohne waagerechten Bildlauf:

- **Materialwart**: Ordnerkopf mit „Export / Import“; Vereinsliste als xlsx (Titelzeilen, Personenspalte, Bezeichnung
  links vom Typ, Größe und Standort) – Zuordnung ohne Eingriff, „Ausgegeben an“ ohne Auswahl; zweimal schnell
  umgestellt: nur die neueste Antwort zählt; Übernehmen „5 Artikel anlegen, 4 Zeilen in die Nacharbeit“, Tabelle
  „angelegt“ mit Inventarnummern und „STR-000012 (System)“; Hinweise im Ordnerkopf und auf der Übersicht; Varianten
  zeilenweise zugeordnet (Größe S und M), Helm gemeldet (Dialog vorbelegt), alle ausgewählt, erneut geprüft und
  übernommen (Tabelle mit Nacharbeit-Nr. und Inventarnummer), eine Zeile verworfen (Rückfrage mit „Verwerfen“);
  CSV heruntergeladen, korrigiert und wieder hochgeladen („Nacharbeits-CSV erkannt“, alte Zeile „neu eingelesen“),
  dieselbe Datei neu gespeichert noch einmal: alles „schon erledigt“, nichts übernommen, Nacharbeit unverändert.
  Zu große Datei (Hinweis vor dem Hochladen), 413 ohne JSON (Proxy) und 429 mit „Erneut versuchen“ nachgestellt.
- **Maskierung**: Spaltentitel `<b>Titel</b>`, Werte `<img src=x>` und `<img src=x onerror=alert(1)>`, Ordner
  `<a href="/x">MTW</a>`, Hersteller `<b>Fett GmbH</b>` erscheinen als Text in Zuordnung, Ergebnis, Gründen,
  Nacharbeit, Karten und „alle Werte“ – kein Element daraus im Dokument.
- **Material-Verwaltung** mit Wiki-Stufe: Formularzeile, Seitenwahl (Reichweite und Hinweis je Treffer, Suche),
  Verknüpfen der internen Probeseite, Satz zu benutzten Versionen. **Ohne Wiki-Stufe**: „Seite Nr. 8 – du darfst sie
  nicht lesen“, kein „Ändern …“, Hinweis auf die Wiki-Stufe; Import der cp1252-CSV, unbekanntes Produkt mit „Im
  Katalog anlegen …“ angelegt und zugeordnet (Seite bleibt stehen), erneut geprüft und übernommen.
- **Plattform-Verwaltung**: Formularzeile mit „Ändern …“, Übersicht mit „Nacharbeit aus Bestandsimporten: OG
  Musterstadt / Lager Musterstadt (2)“.
- **Prüfer mit Wiki-Stufe** und **externer Prüfer ohne**: Anleitung aufgeklappt – nur der Abschnitt „Prüfung:“ bis
  vor „Pflege“ (Einleitung und Pflege nicht), Kasten, Liste, Tabelle (am Telefon seitlich rollend), Link in neuem Tab;
  der Kasten rollt bei 360 px in sich, die Umschalter darunter bleiben bedienbar. Seite ohne Abschnitt: Satz und Link.
  Interne Seite für den externen Prüfer: nur der Satz, kein Titel im HTML. Abgeschlossene Prüfung: keine Anleitung.
- **Abschirmung** (DOM-Clobbering-Probe der Sicherheitskritik und Bauentwurf 6.3 an der echten Einblendung): Abschnitt
  mit `<data id="pr-grund" value=…>`, `<data id="pr-due">`, `<output id="pr-bem">`, `<form id="pr-abschluss">` mit
  `<input id="pr-grund">`, `<a id="pr-ok" data-act="festschreiben">`, `<a data-act="ergebnis" data-e="einsatzbereit">`,
  `<span class="mat-pwert" data-rid="1">`, `<div id="pp-26">`, `<label for="pr-grund">`, `<img name="pr-ok">`.
  Im Schatten bleiben davon nur Text, Links ohne `data-*`, ein `<span class="mat-pwert">` ohne Attribute und das Bild
  ohne Namen; alle Elemente mit echten Mausklicks angeklickt – kein Ergebnis gesetzt, `#pr-grund`, `#pr-due`, `#pr-bem`,
  `#pr-abschluss` und `window["pr-ok"]` sind die echten Felder, `.mat-pwert` wie vorher, kein `#pp-26`. Festgeschrieben
  mit „einsatzbereit“ und Bemerkung „ECHTE-BEMERKUNG“: Ergebnis, leerer Grund, Bemerkung und Datum kamen aus den
  echten Feldern; danach keine Anleitung mehr.
- **Mitglied (Führungskraft, lesen)**: Menü nur „Export“, Importseite 403 „Bestandslisten importiert, wer den Ordner
  verwaltet.“, kein Hinweis auf Nacharbeit.

Zwei Befunde der Durchsicht sind behoben: Nach der Wahl einer neuen Datei stand bis zur Antwort der Bericht der
vorigen; der lange rote Knopf brach am Telefon nicht um (waagerechter Bildlauf). Dazu Abweichung 2 (Einzahl).

### Prüfung vor Auslieferung

- Bauentwurf vorher von zwei Kritiken geprüft („Fach“: 15 Befunde, „Sicherheit“: 15 Befunde) – alle übernommen oder
  begründet abgelehnt (Bauentwurf, Abschnitt 9).
- Neue Testdateien `tests/test_material_import.py` (Testplan 6.1, dazu statisch die Oberfläche: Ansicht, Einstieg,
  Knopfregel, Abbruch, 413/429, Nacharbeit, Maskierung) und `tests/test_material_wiki.py` (Testplan 6.2, dazu statisch
  Reinigung, Schatten, Ausschneiden, Härtung der Prüfansicht, Formularzeile); angepasst: Trennungs-, Überblicks-,
  Erinnerungs-, L5- und Beschreibungstest. `tests/test_pruefungen_import.py` unverändert grün. Die ganze Suite läuft grün, `st-js`,
  `st-css` und `st-py` ohne Meldungen.

Nach dem Bau drei unabhängige Prüfungen – **Sicherheit** (Datenschutz, Rechte, Robustheit; Proben gegen Dienste,
Routen und eine Testdatenbank, Messungen je Datei in einem eigenen Prozess mit Speicherdeckel), **Importlogik**
(Entscheidungen 1–10, Regeln 2.x, Schnittstelle 8.5, Rundweg, Frist; Proben gegen eine Testdatenbank) und **Browser**
(Rundgang als Plattform-Verwaltung, Material-Verwaltung mit und ohne Wiki-Stufe, Materialwart, Prüfer mit und ohne
Wiki-Stufe, Externer, Mitglied und neues Konto bei 1280 und 360 px, Server ohne `SMTP_HOST`) – haben 20 Befunde
gemeldet (3 + 8 + 9). Jeder ist vor der Behebung mit dem Skript der Prüfung nachgestellt worden; alle 20 ließen sich
nachstellen, alle sind behoben – im Code mit Test (Python, statisch für die Oberfläche) und, wo es um die Oberfläche
geht, im Browser nachgesehen. Befund 1 traf genauso den älteren Excel-Import der Prüfungen: Die Vorprüfung ist eine
gemeinsame Funktion in `pruefungen_import.py`, aufgerufen in `_arbeitsblatt`, über das beide Importe lesen (eigener
Commit, `CHANGELOG-Pruefungen.md` Nachtrag vom 19.10.2026). Danach liefen die ganze Suite und `pytest` grün.

| Nr. | Quelle | Befund | Schwere | Umgang |
| --- | --- | --- | --- | --- |
| 1 | Sicherheit 1 | xlsx: Ein Bereich verbundener Zellen, ein Link-Bereich (`<mergeCell ref="A3:KN20000"/>`, 5 KB) oder 9,5 MB dichte leere Zellen `<c/>` blähen openpyxl beim Laden auf (1,8–2,8 GB, bis 76 s, „A3:XFD1048576“ unbegrenzt), bevor eine Grenze greift; der Probelauf eines beliebigen Ordnerverwalters bringt den Container an die Speichergrenze | hoch | `pruefungen_import._blaetter_vorpruefen` vor `load_workbook`: jeder XML-Teil des Archivs durch denselben Parser wie openpyxl (expat), nur zählend – Zellen, Zeilen und die Fläche jedes Bereichs verbundener Zellen, Links und Kommentare (auch Kommentare legen Zellen an) zusammen höchstens 500.000, kein Bereich über Zeile 20.000/Spalte 300, höchstens 20 Blätter und 5 Mio. Elemente; unabhängig von Pfad, Präfix, Zeichenreferenz, UTF-16 und Entitäten. Jetzt 400 in höchstens 0,4 s ohne openpyxl (Messwerte unten). Tests `test_grenzen_vor_dem_laden` (Prüfungen) und `test_lesen_xlsx_und_grenzen` (Bestandsimport, auch über die Route), beide mit `xlsx_bomben` |
| 2 | Sicherheit 2 | Prüfanleitung: Klassen aus app.css mit `position: fixed` (etwa `md-lightbox`) im Abschnitt „Prüfung“ legten sich über die ganze Prüfansicht – wer die Wiki-Seite bearbeiten darf, konnte Prüfern die Ansicht sperren oder eine Meldung vortäuschen | niedrig | `ANLEITUNG_STIL`: `:host { display: block; contain: paint; }` – der Kasten ist Bezugsrahmen auch für fixe Elemente und schneidet ab. Statischer Test in `test_material_wiki`; im Browser mit einer Probeseite (`<div class="md-lightbox">`) bei 1280 und 360 px: Überlagerung nur im Kasten, „einsatzbereit“ per echtem Mausklick erreichbar |
| 3 | Sicherheit 3 | In der Nacharbeits-CSV (Spalte „Nacharbeit-Nr.“) war eine ergänzte Personenspalte („Ausgegeben an“) nicht gesperrt – über „Zuordnung ändern“ kam der Name in Bemerkung und Artikeljournal | niedrig | Auch dort `gesperrt` aus der Personenliste, das Feld weiter aus der festen Zuordnung. Test `test_spalten`; Probe der Prüfung danach: gesperrt, ohne Beispiele, Bemerkung leer |
| 4 | Importlogik 1 | „Serien-Nummer“, „Ser.-Nr.“, „Ser. Nr.“ wurden nicht erkannt – jede Zeile bekam still eine STR-Nummer, die echten Nummern gingen verloren | mittel | Synonyme ergänzt (auch „ser.nr“, „ser-nr“, „serialnumber“, „Fabr.-Nr.“, „Fabrikationsnummer“). Ist keine Spalte als Seriennummer zugeordnet, steht die Warnung zuerst („Keine Spalte ist als Seriennummer zugeordnet – alle n Zeilen bekämen eine Seriennummer vom System … Nicht zugeordnet: „…““) und noch einmal über „Übernehmen“ (`keine_seriennummer`). Bewusst keine Pflichtzuordnung: Listen ohne Seriennummern sollen nach Entscheidung 8 ohne Rückfrage gehen, und eine Zuordnung „keine Seriennummer“ gäbe es nur als neuen Haken. Tests `test_spalten`, `test_befunde_vor_auslieferung`; im Browser bei 1280 und 360 px. **Geändert am 20.10.2026**: Übernehmen nur mit ausdrücklicher Bestätigung (Häkchen, `ohne_seriennummern`) – siehe „Entscheidungen vom 20.10.2026“ |
| 5 | Importlogik 2 | „Prüfintervall (Jahre)“ = 1 wurde als 1 Monat gelesen und ohne Hinweis am Artikel gespeichert | mittel | Die Einheit kommt aus dem Spaltentitel („(Jahre)“, „in Jahren“, „[J]“; „(Monate)“, „[M]“) und bleibt am Wert („1 Jahr“) – auch in Nacharbeit und CSV; eine 1 oder 2 ohne Einheit geht in die Nacharbeit („Monate oder Jahre?“, die Spalte „Prüfintervall (Monate)“ der eigenen CSV zählt dafür nicht als Einheit); ein übernommenes kürzeres Intervall steht als Hinweis an der Zeile. Test `test_befunde_vor_auslieferung` |
| 6 | Importlogik 3 | Dieselbe Ursprungsliste nach mehr als 10 Minuten noch einmal, während ihre Zeilen in der Nacharbeit standen: Die Nacharbeit entstand doppelt, Zeilen ohne Seriennummer wurden zweimal angelegt (5 Artikel aus 3 Zeilen); die Warnung führte in die Irre | mittel | Bei gleicher Prüfsumme ersetzt jede Zeile ihre offene Vorgängerin gleicher Zeilennummer wie über die Nacharbeit-Nr. (Produktwahl aus der Nacharbeit gilt weiter); die Warnung nennt die Zahl („… werden neu eingelesen und dort erledigt, nicht doppelt angelegt“) und den STR-Satz nur noch, wenn damals Artikel angelegt wurden. Test `test_befunde_vor_auslieferung`; Probe der Prüfung danach: 3 Artikel, nichts offen |
| 7 | Importlogik 4 | Stufe 1 (Dublettenschlüssel) ordnete „Modell“ ohne Artikelnummer still dem Grundprodukt zu, obwohl es „Modell \| Zusatz“ gibt | mittel | Trifft Stufe 1 ohne Artikelnummer ein Grundprodukt, das Varianten hat, ist die Angabe „mehrdeutig“ wie in Stufe 3; „Modell \| Zusatz“ und „Modell Zusatz“ bleiben genau. Test `test_befunde_vor_auslieferung` |
| 8 | Importlogik 5 | Dieselbe Seriennummer bei zwei Varianten desselben Herstellers in einer Datei (oder Auswahl der Nacharbeit) wurde zweimal angelegt | niedrig | Im ersten Durchgang auch nach Hersteller + Seriennummer gesammelt: alle betroffenen Zeilen bekommen „Seriennummer bei anderer Variante“ mit den Zeilen bzw. Nacharbeit-Nr. Test `test_befunde_vor_auslieferung` |
| 9 | Importlogik 6 | Eine vor Ablauf der Frist heruntergeladene Nacharbeits-CSV wurde danach komplett als „schon erledigt“ übersprungen – nie ein Artikel entstanden | niedrig | Nach Ablauf der Frist verworfene Zeilen werden wie neue geprüft (Hinweis „Nacharbeit-Nr. n war nach Ablauf der Frist verworfen – neu geprüft“); von Hand verworfene bleiben erledigt und sagen „… in der Datei die Nacharbeit-Nr. leeren“. Test `test_befunde_vor_auslieferung` |
| 10 | Importlogik 7 | Anzahl „01“, „1,0“, „1 Stk.“ wurden Sammelzeilen, Intervall „jährlich“, „halbjährlich“, „alle 12 Monate“ unlesbar | niedrig | Anzahl mit Nullen, Dezimal-0 oder Stückwort ist 1 (größere bleiben Sammelzeilen); Intervall: „jährlich“, „1x jährlich“, „2x jährlich“, „halbjährlich“, „vierteljährlich“, „monatlich“, „2-jährlich“, „alle n Monate/Jahre“, „0,5 Jahre“. Tests `test_befunde_vor_auslieferung` (Tabellen) und `test_sammelzeilen` |
| 11 | Importlogik 8 | Ein Lebensende laut Liste bei nicht-textilem Material verschwand nach dem Import ohne Spur | niedrig | „Lebensende laut Liste: …“ in die Bemerkung wie die anderen Angaben, der Hinweis sagt es. Tests `test_daten_und_blockieren`, `test_befunde_vor_auslieferung` |
| 12 | Browser 1 | Dialog „Übernommen“ der Nacharbeit bei 360 px: die Tabelle „angelegt“ ohne Karten, zeichenweise umbrochen („Nac/har/beit“) | mittel | Die Tabelle hat im Dialog einen eigenen Behälter `mat-seite` (`.mat-dlg-liste`), der Dialog ist ab 641 px 820 px breit (`mat-uebernommen`, nur solange er offen ist); in den Karten steht die Seriennummer in ganzer Breite. Statischer Test; im Browser: 360 px Karten, 1280 px Tabelle |
| 13 | Browser 2 | Der Probelauf bot „Übernehmen“ an, obwohl die 10-Minuten-Sperre greift – erst die Fehlermeldung, und die Warnung sagte „würden noch einmal angelegt“ | leicht bis mittel | Der Bericht trägt `sperre_bis`; die Warnung sagt „Noch einmal übernehmen geht erst ab hh:mm Uhr.“, über den Knöpfen steht es noch einmal mit „(dann „Probelauf wiederholen“)“, der rote Knopf entfällt (der Server lehnt weiter mit 409 ab). Tests `test_befunde_vor_auslieferung` und statisch; im Browser bei 1280 und 360 px |
| 14 | Browser 3 | „Fällig“ und „Zeile“ brachen bei 1280 px mitten in der Zahl um („19.03.2 / 027“) | leicht | Zeile, Nacharbeit-Nr. und Fällig tragen `.mat-ungeteilt` (`white-space: nowrap`, `overflow-wrap: normal`) – Produkt, Ordner, Gründe und Seriennummer brechen weiter überall; „Zeile n“ in der Nacharbeit mit festem Leerzeichen. Statischer Test; im Browser je Zelle eine Zeile (1280 und 360 px, auch im Dialog) |
| 15 | Browser 4 | Nach einer Auswahl landete der Fokus auf `<body>` (Seitenwahl, Suchtreffer im Dialog „Produkt zuordnen“, „n Artikel übernehmen“, „Übernehmen“) | leicht | Seitenwahl: der gewählte Eintrag; Suchtreffer: „Zuordnen“; Ergebnisdialog: sein Titel; Übernehmen: der Satz „Übernommen: …“ (Ring nur bei Tastatur). Statischer Test; im Browser per Tastatur |
| 16 | Browser 5 | Nach zeilenweiser Zuordnung sagte die Karte nichts davon, ihr Dialog überschrieb die Wahl ohne Hinweis | leicht | `gruppen[].zugeordnet` (Zahl zugeordneter Zeilen); die Karte zeigt „zeilenweise zugeordnet: k von n“, ihr Dialog „Das ersetzt die zeilenweise Zuordnung (k Zeilen) …“ und „Zuordnung entfernen“. Tests `test_befunde_vor_auslieferung`, statisch; im Browser |
| 17 | Browser 6 | Nach „Im Katalog anlegen …“ blieb die Karte bei „nicht im Katalog“ und bot das Anlegen weiter an | leicht | Ist allen Zeilen ein Produkt zugeordnet, trägt die Karte die Marke „zugeordnet“ und nur „Produkt zuordnen …“ (kein Anlegen, kein Melden). Statischer Test; im Browser als Material-Verwaltung bei 1280 und 360 px |
| 18 | Browser 7 | Zeilen „schon erledigt“ zeigten „Seriennummer: ohne“, obwohl die Datei eine hat | leicht | `zeile_json` liefert auch dort die Seriennummer der Datei; ohne steht „–“. Test `test_befunde_vor_auslieferung`; im Browser (CSV zweimal) |
| 19 | Browser 8 | Die Bemerkungsvorschau der Nacharbeit verschluckte die Zeilenumbrüche („Gurt Größe: L Standort: Lager“) | leicht | `.mat-na-bem { white-space: pre-line }`. Statischer Test; im Browser |
| 20 | Browser 9 | Telefon: „Datei wählen“ nicht in ganzer Breite, Kästchen der Nacharbeit-Karten unten statt links oben (Bauentwurf 4.6, nicht als Abweichung genannt) | leicht | Gebaut wie im Entwurf statt nachgetragen: bis 600 px Inhaltsbreite „Datei wählen“ über die ganze Ablagefläche, das Kästchen links oben vor der Nacharbeit-Nr. („auswählen“ nur noch für die Vorlesehilfe). Statischer Test; im Browser bei 360 px |

**Messwerte xlsx vor dem Laden** (je Datei ein eigener Prozess mit 3-GB-Speicherdeckel; Weg Bestandsimport =
`tabelle.lesen`, Weg Prüfungen = `pruefungen_import.analysieren`; die Werte beider Wege lagen je Datei gleichauf):

| Datei (Upload) | vorher: Ergebnis, maxRSS, Zeit | nachher |
| --- | --- | --- |
| verbundene Zellen A3:KN20000 (5 KB) | 400 nach dem Laden, 1,85 GB, 60 s | 400, 79 MB, < 0,1 s |
| Link-Bereich A3:KN20000 (5 KB) | 400 nach dem Laden, 2,85 GB, 76 s | 400, 79 MB, < 0,1 s |
| Kommentar über A3:KN20000 (6 KB) | 400 nach dem Laden, 1,55 GB, 14 s | 400, 79 MB, < 0,1 s |
| verbundene Zellen A3:XFD1048576 (5 KB) | Speicherdeckel (2,9 GB) nach 14 s, ohne Deckel unbegrenzt | 400 („bis Zeile 1048576“), 79 MB, < 0,1 s |
| 9,5 MB leere Zellen `<c/>` (31 KB) | 400 nach dem Laden, 0,83 GB, 8 s | 400, 79 MB, 0,3–0,4 s |
| dieselben verkleidet (Präfix, Zeichenreferenz, UTF-16, Blatt unter fremdem Pfad) | wie oben: 1,85 GB, 60 s | 400, 79 MB, < 0,1 s |
| leere Zellen über eine Entität vervielfacht (5 KB) | 400 (unlesbar) erst nach dem Laden, 377 MB, 1,6 s | 400, 79 MB, 0,3–0,4 s |
| Link über ganze Spalten „A:KN“ mit einer Zelle in Zeile 20000 | Speicherdeckel (2,9 GB) nach 73 s | 400 (unlesbar), 79 MB, < 0,1 s |
| zulässig: 2000 Zeilen × 80 Spalten (7,8 MB XML) | gelesen, 115 MB, 2,4 s | gelesen, 115 MB, 2,9 s |
| zulässig: Liste mit verbundenen Kopfzellen und Links | gelesen | gelesen |

Über die Route (Probe der Sicherheitsprüfung, Materialwart, `merge_6m.xlsx`): vorher 400 nach 61 s bei 1,88 GB, ein
gleichzeitiger Probelauf im selben Arbeitsprozess bekam nach 10 s 429; nachher 400 nach 0,1 s bei 117 MB, der zweite
Probelauf läuft durch.

### Entscheidungen vom 20.10.2026

Der Betreiber hat am 20.10.2026 vier Punkte entschieden – einen geändert, drei bestätigt.

**Geändert – Nr. 1, Liste ohne Seriennummernspalte** („Zu prüfen“ Nr. 5). Gebaut war: Der Probelauf warnt (zuerst und
über dem Knopf, mit den nicht zugeordneten Spalten), blockiert aber nicht – alle Zeilen bekämen still STR-Nummern.
**Entscheidung:** „Soll ausdrücklich bestätigt werden müssen.“ **Umgesetzt** (`services/bestandsimport.py`,
`routes_import.py`, `static/material.js`, `static/material.css`):

- **Schnittstelle**: Ist im Übernehmen keine Spalte als Seriennummer zugeordnet und schriebe der Lauf Zeilen (Artikel
  oder Nacharbeit), verlangt `POST …/ordner/<id>/import` das Feld `ohne_seriennummern` = ja. Ohne das Feld (auch mit
  „nein“, leer oder nur dem alten `ohne_serie`) antwortet er **409** „Keine Spalte ist als Seriennummer zugeordnet –
  bitte bestätigen, dass die Liste keine Seriennummern hat (alle Artikel bekommen eine Seriennummer vom System, STR-…),
  oder die Spalte mit den Seriennummern zuordnen.“ und schreibt nichts; anderes als ja/nein → 400. Der Probelauf sagt
  es mit `ohne_seriennummern_bestaetigen` (nach dem Übernehmen `false`); `keine_seriennummer` bleibt.
- **Einzelne Zeilen ohne Seriennummer bei vorhandener Spalte** bekommen ihre STR-Nummer weiter ohne Bestätigung (wie am
  19.10.2026 entschieden). Wird eine Spalte von Hand als Seriennummer zugeordnet, entfällt die Bestätigung.
- **Auch wenn nur Nacharbeit entstünde – bestätigt am 20.10.2026**: Die Bestätigung gilt für alles, was der Lauf schreibt – auch für eine Liste,
  deren Zeilen alle in die Nacharbeit gehen. Grund: Die Nacharbeit speichert nur die Werte der zugeordneten Spalten und
  weiß später nicht mehr, ob die Liste eine Seriennummernspalte hatte; „erneut prüfen und übernehmen“ vergäbe dort
  sonst STR-Nummern, ohne dass je jemand gefragt wurde. Darum wird beim Import gefragt und **in der Nacharbeit nicht
  noch einmal** (`nacharbeit/pruefen` bleibt unverändert, dessen Hinweis nennt die STR-Nummern wie bisher).
- **Nacharbeits-CSV**: Sie läuft durch denselben Import und folgt derselben Regel. Mit ihrer Spalte „Seriennummer“ – auch
  leer – braucht sie keine Bestätigung; ist die Spalte gelöscht oder unter „Zuordnung ändern“ auf „ignorieren“ gestellt,
  braucht sie eine.
- **Oberfläche**: Direkt über dem roten Knopf steht in diesem Fall ein Kästchen – „Diese Liste hat keine Seriennummern –
  alle n Artikel bekommen eine Seriennummer vom System (STR-…)“, bei Nacharbeit „…, die m Zeilen der Nacharbeit später
  auch“ (nur Nacharbeit: „die m Zeilen der Nacharbeit bekommen beim Übernehmen dort eine Seriennummer vom System …“),
  darunter „Keine Spalte ist als Seriennummer zugeordnet. Steht die Seriennummer doch in einer Spalte, ordne sie oben
  unter „Spalten“ zu – dann braucht es kein Häkchen.“ (vorher dort nur ein Hinweis). Der rote Knopf bleibt gesperrt,
  bis das Häkchen gesetzt ist; erst dann geht `ohne_seriennummern` mit. Eine neue Datei, jeder neue Probelauf, eine
  geänderte Zuordnung (sofort, nicht erst mit dem neuen Ergebnis) und „Neu wählen“ nehmen das Häkchen zurück. Das
  Häkchen gibt den Knopf frei, ohne die Seite neu zu zeichnen – der Fokus bleibt am Kästchen, Tab führt weiter zu
  „Neu wählen“ und „Übernehmen“. Die Warnung oben sagt jetzt „…, Übernehmen nur mit ausdrücklicher Bestätigung“; im
  Ergebnis nach dem Übernehmen steht sie nicht mehr (dort nennt der STR-Satz die vergebenen Nummern). In „Welche
  Listen passen?“ steht der Satz „Hat die Liste gar keine Spalte mit Seriennummern, bestätigst du das vor dem
  Übernehmen mit einem Häkchen.“
- **Tests**: `test_ohne_seriennummernspalte` (neu) – Probelauf mit `ohne_seriennummern_bestaetigen`; 409 ohne Feld, mit
  „false“, leer und mit `ohne_serie`, 400 bei „vielleicht“, dabei nichts geschrieben; 201 mit dem Feld (STR-Nummern,
  Warnung nicht mehr im Ergebnis); „erneut prüfen und übernehmen“ ohne Feld; nur Nacharbeit 409/201; Spalte vorhanden
  mit leerer Zeile und Spalte von Hand zugeordnet ohne Feld; Nacharbeits-CSV mit Spalte ohne, ohne Spalte bzw. mit
  „ignorieren“ mit Bestätigung (409, dann 201 mit „ersetzt“). Statisch: Kästchen vor der Knopfzeile, Sperre des Knopfs,
  Feld nur mit Häkchen, Zurücksetzen, CSS. Angepasst: `test_oberflaeche_statisch` (statt des Hinweises das Kästchen).
- **Im Browser geprüft** (Chromium, lokaler Server ohne `SMTP_HOST`, Platzhalter-Bestand OG Musterstadt mit Lager,
  Materialwart) bei 1280 und 360 px: Liste „Hersteller; Modell; Kennung“ mit zwei bekannten und einem unbekannten
  Produkt – Kästchen ungesetzt, Knopf gesperrt, Satz „… alle 2 Artikel bekommen …, die Zeile der Nacharbeit später
  auch.“; ein erzwungener Klick am gesperrten Knopf schickt nichts; per Tastatur Tab zum Kästchen, Leertaste setzt das
  Häkchen (Fokus bleibt, Knopf frei), Tab weiter zu „Neu wählen“ und „Übernehmen“; „Kennung“ auf „Bemerkung“
  umgestellt – Häkchen sofort und nach dem neuen Probelauf zurück, Knopf gesperrt; Häkchen gesetzt und übernommen
  („Übernommen: 2 Artikel angelegt, 1 Zeile in die Nacharbeit.“, Tabelle mit „STR-… (System)“); „Kennung“ als
  Seriennummer zugeordnet – kein Kästchen, Knopf frei. Am Telefon bricht der Satz neben dem Kästchen um, der Knopf
  steht in ganzer Breite darunter. Keine Konsolenfehler, kein waagerechter Bildlauf.

**Bestätigt** (bleibt, wie gebaut):

- Nr. 2 – **Prüfintervall 1 oder 2 ohne Einheit** kommt in die Nacharbeit („Monate oder Jahre?“); ab 3 gilt eine Zahl
  ohne Einheit als Monate; eine Einheit im Spaltentitel („Prüfintervall (Jahre)“) wird umgerechnet („Zu prüfen“ Nr. 6).
- Nr. 3 – **Dieselbe Liste nach mehr als 10 Minuten noch einmal** legt Zeilen ohne Seriennummer, die beim ersten Mal
  angelegt wurden, neu an (mit neuer STR-Nummer); der Probelauf sagt es. Offene Zeilen der Nacharbeit werden über die
  Zeilennummer ersetzt („Zu prüfen“ Nr. 7).
- Nr. 4 – **Folge von „immer neu“** (Entscheidungen 1 und 7): Ein Artikel mit „nächste Prüfung“ in elf Monaten steht so
  lange auf „neu – bis dahin nicht einsetzen“ und erscheint erst 30 Tage vor der Fälligkeit in einer Erinnerung (in der
  Prüfliste sofort). Kein eigener Punkt unter „Zu prüfen“ – Befund der Prüfung „Importlogik“ zur Kenntnis.

### Zu prüfen

Am 20.10.2026 entschieden: Nr. 5 geändert, Nr. 6 und 7 bestätigt (siehe „Entscheidungen vom 20.10.2026“).

1. **Eine echte Liste der Gliederung** im Probelauf (dev oder anonymisiert): Gebaut und geprüft ist mit einer
   typischen Vereinsliste aus Platzhaltern. Ungewöhnliche Listen (verbundene Zellen, mehrere Tabellen auf einem Blatt,
   Summenzeilen) fangen Kopfzeilensuche und Sammelzeilen nur grob ab.
2. **Anleitungen für alle Prüfer gehören in den öffentlichen Teil des Wikis**: Neue Konten haben keine Wiki-Stufe und
   sehen interne Seiten nur als Satz ohne Titel. Bitte mit der Wiki-Redaktion abstimmen, welche Anleitungen
   öffentlich werden.
3. **Mail an den Melder** aus der Nacharbeit (Link zur Nacharbeit) einmal auf dev mit Mailserver ansehen – lokal ist
   ohne `SMTP_HOST` geprüft.
4. **Frist von einem Monat – bestätigt am 20.10.2026** im Betrieb: Was nach einem Monat offen ist, verwirft „System“ ohne Rückfrage; danach hilft
   ein neuer Import der Liste oder eine vorher heruntergeladene Nacharbeits-CSV (deren verfallene Zeilen werden wie
   neue geprüft).
5. **Geändert am 20.10.2026 – ohne Seriennummernspalte nur mit ausdrücklicher Bestätigung** (Kästchen über dem Knopf,
   Feld `ohne_seriennummern`, sonst 409; siehe „Entscheidungen vom 20.10.2026“). Gebaut war: **Ohne
   Seriennummernspalte** (Prüfung vor Auslieferung, Nr. 4): Der Probelauf warnt deutlich, blockiert aber nicht –
   nach Entscheidung 8 sollte eine Liste ohne Seriennummern ohne Rückfrage gehen.
6. **Prüfintervall 1 oder 2 ohne Einheit – bestätigt am 20.10.2026** (Nr. 5) kommt in die Nacharbeit („Monate oder
   Jahre?“); ab 3 gilt eine Zahl ohne Einheit als Monate, eine Einheit im Spaltentitel wird umgerechnet.
7. **Dieselbe Liste noch einmal – bestätigt am 20.10.2026** (Nr. 6): Offene Zeilen der Nacharbeit werden über die
   Zeilennummer ersetzt; Zeilen ohne Seriennummer, die beim ersten Mal angelegt wurden, entstehen nach 10 Minuten
   weiterhin noch einmal (wie in Entscheidung 8 vorgesehen, der Probelauf sagt es).
8. **Weitere Blätter zählen mit – bestätigt am 20.10.2026** (Nr. 1): Die Vorprüfung zählt alle Blätter der Arbeitsmappe – openpyxl lud sie schon
   immer ganz. Eine Arbeitsmappe, deren weitere Blätter zusammen mehr als 500.000 Felder haben, wird jetzt abgelehnt
   (auch im Prüfungsimport); bitte dann nur die Liste speichern.

### Nachbesserungen nach der Auslieferung (Wünsche vom 20.10.2026)

- **Katalog: „Export / Import“ als Untermenü** – „Katalog exportieren“ und „Katalog importieren“ sind keine eigenen
  Knöpfe mehr, sondern zwei Einträge im Untermenü „Export / Import“ im Kopf des Katalogs, je mit einem Satz dazu (wie
  „Export / Import“ im Ordnerkopf). Die Dialoge sind unverändert. Reihenfolge im Kopf: „Kategorie anlegen“, „Produkt anlegen“, „Meldungen“, ganz rechts
  „Export / Import“.
- **Ordnerkopf: Export klarer benannt** – im Untermenü „Export / Import“ heißen die Einträge jetzt „Artikelliste
  exportieren (CSV)“ und „Protokolle exportieren (ZIP)“.
- **Ordnerkopf: „Bearbeiten“ als Untermenü** – „Verschieben“ und „Löschen“ stehen nicht mehr als eigene Knöpfe im
  Ordnerkopf, sondern mit „Ordner bearbeiten …“ im Untermenü „Bearbeiten“. Wer den Ordner pflegt, ihn aber nicht
  verschieben oder löschen darf, behält den einfachen Knopf „Bearbeiten“.
- **Übersicht ohne Knöpfe im Kopf** – „Bestand pflegen“ und „+ Artikel“ sind entfallen; beides erreicht man über den
  Reiter „Bestand“ (dort „Artikel anlegen“ im Ordnerkopf).
- **Prüfungen: „Prüfdurchgang anlegen“** statt „+ Prüfdurchgang“ als Beschriftung des Knopfs.
- **Bestand: „Gliederung anlegen“** statt „+ Gliederung“ als Beschriftung des Knopfs (README nachgezogen).
- **Überall „… anlegen“ statt „+ …“** im Modul: Unterordner, Artikel, Artikel dieses Produkts, Kategorie, Produkt,
  Dokument, Prüfpunkt, Freigabe (Abschnitt im Reiter „Freigaben“), Link beim Hersteller und Bemerkung (in der Prüfung).
- **Auf dem Telefon kurz „+ …“** – bis 600 px Breite zeigen die Knöpfe zum Anlegen „+ Artikel“ statt „Artikel
  anlegen“ (reines CSS, Klassen `k-text`/`k-plus`/`k-anlegen` in app.css); Screenreader lesen immer „Artikel anlegen“.
  Tablet und Rechner zeigen den vollen Text. Piktogramme bewusst nicht: „+“ steht schon für Anlegen, für Unterordner,
  Prüfpunkt, Freigabe usw. gibt es keine eindeutigen Bilder. Gilt app-weit, auch in Prüfungen, Wiki und Verwaltung
  („Nutzer anlegen“, „Lehrgang anlegen“ …; „+ Neues Album“/„+ Neue Seite“ heißen jetzt „Neues Album“/„Neue Seite“).
- Im Browser bei 1280 und 360 px geprüft (Untermenüs öffnen die Dialoge, das Menü schließt dabei, kein waagerechter
  Bildlauf, keine Konsolenfehler).

## Phase 3 · Lieferung 1 – Meine PSA und Mangelmeldung (20.10.2026)

Lieferung 1 der Phase 3 bringt drei Punkte aus dem Plan (`p3/plan_phase3.md`): **„Meine PSA“** – jede Person sieht
die Ausrüstung, die ihr zugeordnet ist, auch ohne Stufe im Modul Material –, die **Mangelmeldung**, die den Artikel
sofort sperrt, und den Abschnitt **„Deine PSA“** in der täglichen Sammelmail. Gebaut nach dem Bauentwurf vom
20.10.2026 (zweite Fassung nach zwei Kritiken, „Fach“ und „Sicherheit“, mit den Entscheidungen des Betreibers vom
selben Tag) in zwei Paketen: KERN (Schema, Dienste, Routen, Vorlagen, Tests) und OBERFLÄCHE (`material.js`, CSS,
Nebenskripte, Browser, Doku). Schemaversion 13, keine neuen Abhängigkeiten. Stand: wartet auf Freigabe.

### Neu

- **Meine PSA** (`services/psa.py`, `routes_psa.py`; Oberfläche in `material.js`, Ansicht `meine_psa`):
  `/material/meine-psa` (Liste) und `/material/meine-psa/<id>` (ein Artikel) für jedes aktive Konto mit Namen –
  **auch ohne Modulstufe**; dann fehlen Modulnavigation und Ordnerleiste (`seite.html` mit `nur_psa`), `material.js`
  kommt ohne beide aus. Gezeigt werden nur die eigenen, nicht ausgesonderten Artikel, dringende zuerst (höchstens 200,
  darunter „… und n weitere – frag deinen Materialwart“). Je Artikel eine Karte (am Telefon untereinander, ab 900 px
  Inhaltsbreite zwei nebeneinander): Banner mit dem, was zu tun ist (Mangel gemeldet, gesperrt, verloren, überfällig
  „nicht verwenden, bis sie geprüft ist“, Lebensdauer erreicht „nicht mehr verwenden“, neu, DEMO), Produktbild
  (Vorschau, groß nur die Webfassung), Inventarnummer mit Statusmarke, Produkt, Seriennummer, nächste Prüfung,
  Lebensende, zuletzt geprüft, Gliederung (nur der Name), Sperrgrund, Bemerkung, Herstellerdokumente
  (Gebrauchsanleitung, Pflegehinweis, Konformitätserklärung, Datenblatt), Titel laufender Rückrufe („bitte deinem
  Materialwart zeigen“), „Deine Meldungen“ eingeklappt mit Text, Fotos und „offen“/„erledigt“, Knopf „Mangel melden …“
  (grau; bei eigener offener Meldung ausgegraut mit „Du hast schon gemeldet“) und mit Leserecht „Zum Artikel“. Unter
  der Liste „Erinnerungen per Mail: an/aus – im Profil ändern“ (wie der Abschnitt im Profil nur mit Zuordnung oder
  abbestellten Erinnerungen). Ohne Zuordnung: „Dir ist keine Ausrüstung zugeordnet.“ Ohne Modulstufe heißt der
  Browser-Reiter „Meine PSA – strömis.de“.
- **Einstieg**: Kopfleiste „Meine PSA“, sobald dem Konto etwas zugeordnet ist und es nirgends im Bestand lesen darf
  (ohne Stufe ebenso wie Mitglied ohne Freigabe); `/material` ohne Stufe mit Zuordnung führt auf „Meine PSA“. Wer
  liest, verwaltet oder prüft, sieht unten auf der Übersicht den Kasten „Dir sind n Artikel zugeordnet – Meine PSA
  ansehen →“ (gelb mit „davon m nicht einsatzbereit“). Der QR-Link der eigenen PSA führt ohne Leserecht auf ihre Karte,
  mit Leserecht auf die Artikelansicht; fremde Artikel antworten ohne Stufe weiter mit 403.
- **Mangel melden** (`services/mangel.py`, `POST /api/material/artikel/<id>/mangel`): die zugeordnete Person und jeder
  mit lesen, verwalten oder prüfen an der Heimat. Dialog „Mangel melden – <Inventarnummer>“ (an der Karte und an der
  Artikelansicht gleich): roter Hinweis „Mit dem Melden wird der Artikel sofort gesperrt. Leg ihn sofort beiseite (aus
  Fahrzeug oder Lager) und gib ihn deinem Materialwart …“, Beschreibung Pflicht (bis 2000 Zeichen, Fehler am Feld),
  bis zu 3 Fotos über die Datei-Eingabe **ohne** `capture` (am Telefon Kamera oder Galerie) – jede Wahl hängt an die
  Liste an, „Auswahl entfernen“ leert sie, mehr als drei nimmt sie nicht („Höchstens 3 Fotos.“), „Dein Name steht bei
  der Meldung.“; „Abbrechen“ grau, **„Melden und sperren“** `btn danger`. Danach Toast und ein Hinweis oben auf der
  Seite (er bekommt den Fokus), je nach Antwort: „Gemeldet – der Artikel ist gesperrt (war schon gesperrt). Die Mail
  an Materialwart und Prüfer ist unterwegs. Leg ihn beiseite und gib ihn deinem Materialwart.“ bzw. „… Es ging keine
  Mail hinaus – sag deinem Materialwart Bescheid und gib ihm den Artikel.“
- **Sperre durch die Meldung**: in derselben Transaktion nach „Gesperrt“ der Gliederung (Herkunft gemerkt), Grund
  „Mangel gemeldet am TT.MM.JJJJ“, Journal „Mangel gemeldet“ mit Namen und Nummer der Meldung (im Lebenslauf
  „(Person)“, ohne Text) – auch bei offenem Prüfentwurf. Fotos: Original sofort nach der Verarbeitung gelöscht, es
  bleiben Web- und Vorschaufassung ohne EXIF. Eine offene Meldung je Konto und Artikel (409), keine Tagesgrenze.
- **Sichtbarkeit**: rotes Banner je offener Meldung an der Artikelansicht („MANGEL GEMELDET am … · von <Name>“, Text,
  Fotos, „Nicht verwenden – beiseitelegen und beim Materialwart abgeben …“), erledigte eingeklappt unter „Gemeldete
  Mängel“ mit Link auf die Freiprüfung bzw. Aussonderung; Marke „Mangel“ in Listen und Suchtreffern; Kasten
  **„Gemeldete Mängel“** oben auf der Übersicht (vor den Rückrufen) mit allen Meldungen, nach denen noch kein Prüfer
  geprüft hat; Hinweis „GEMELDETER MANGEL“ in der Prüfung (Start und Entwurf), Prüfart „außerplanmäßig“ vorgeschlagen.
  Den Namen des Melders sieht, wer am Artikel ein Grund- oder Prüfrecht hat.
- **Freiprüfung**: Mit „einsatzbereit“ steht im Festschreib-Dialog je offener Meldung ein Häkchen „Gemeldeten Mangel
  vom … geprüft“ mit dem Kurztext; „Festschreiben“ ist erst frei, wenn alle abgehakt sind, und nur die abgehakten gehen
  als `maengel_gesehen` hinaus. Kam während der Prüfung eine Meldung dazu (409), lädt die Prüfung neu und zeigt sie mit
  eigenem Häkchen. Die Freiprüfung (oder eine Aussonderung) erledigt die Meldung; „instandsetzen“ nicht. Wird die
  erledigende Freiprüfung später zu „instandsetzen“ berichtigt, ist die Meldung wieder offen (abgeleitet, die Zeile
  bleibt): Banner mit „Freiprüfung später berichtigt (jetzt: instandsetzen)“, Marke, Häkchen bei der nächsten
  Freiprüfung.
- **Aussondern** durch den Materialwart nach einer reinen Mangelsperre erst, wenn ein Prüfer den Artikel seither
  geprüft hat: Bis dahin ist der Knopf ausgegraut, darunter steht der Grund.
- **Artikelansicht**: „Mangel melden …“ (grau, `btn secondary small`) neben „Sperren“; stehen beide da (Prüfer), sagt
  eine Hilfezeile den Unterschied („Mangel melden: mit Beschreibung und Fotos, Materialwarte und Prüfer bekommen eine
  Mail. Sperren: ohne Meldung, mit Sperrgrund.“). Hat das Konto dort schon eine offene Meldung, ist der Knopf
  ausgegraut mit „Du hast am … schon gemeldet – ein Prüfer sieht es sich an.“ (wer nicht verwaltet, liest dazu
  „Ergänzungen bitte direkt an den Materialwart.“). Ansicht „fremd“ (QR ohne Recht): „Schaden entdeckt? Sag dem
  Materialwart der Gliederung Bescheid.“
- **Mails bei einer Meldung**, sofort im Hintergrund: an die Verwalter der Heimat (ohne sie Material-, ohne diese
  Plattform-Verwaltung) und jeden Prüfer mit wirksamer Prüffreigabe dort oder darüber; der zugeordneten Person, wenn
  ein anderer ihre PSA meldet, eine kurze Sperrmitteilung ohne Melder und Text (nicht abbestellbar). Nie an den
  Melder, nie an DEMO-Adressen; bei DEMO-Artikeln, Umgebungssperre (dev) und ohne Mailserver (`SMTP_HOST` leer) ins
  Log statt ins Postfach. Die Sperrmitteilung sagt, was die Meldung bewirkt hat: „Sie ist damit gesperrt.“, „Sie war
  schon gesperrt und bleibt es.“ oder „Sie ist als verloren gemeldet.“
- **„Deine PSA“ in der Sammelmail** (`services/erinnerung.py`): 30 Tage vor der Prüfung, überfällig, Lebensende in 90
  Tagen (kein 7-Tage-Schritt), höchstens 50 Zeilen, einziger Link „Meine PSA“; zulässig ohne Modulstufe, Vorgabe an,
  Abmeldung im Profil (Abschnitt „Meine PSA“, `users.mat_psa_mails`). Wer den Artikel zugleich verwaltet, bekommt ihn
  wie bisher unter ARTIKEL. Probelauf: Zeile „<Name> – 1 PSA“ bzw. „… 2 Artikel, 1 Freigabe, 1 PSA“.
- **Texte**: Zuordnung „Die Person sieht sie unter „Meine PSA“, bekommt Erinnerungen per Mail und kann Mängel melden
  (das sperrt).“; Vorlage „Führungskraft“ der Freigaben „… Lebensläufe und Journal ansehen, Mängel melden (sperrt)“;
  Dialog „Konto löschen“ „n Mangelmeldungen behalten den Namen.“; Beispielbestand: die Einsatzkraft ohne Modulzugang
  „sieht „Meine PSA““.

### Migration

- **Schritt 13**, Schemaversion 13, läuft beim Start von selbst, rein additiv und wiederholbar: Tabelle
  `mat_defect_report` (Artikel, Beschreibung, Fotos, Melder mit Kennung und Namen, Sperrzustand davor, Zeitpunkt,
  Erledigung durch eine Prüfung) mit sieben Triggern – unveränderlich, nur offen einfügbar, „erledigt“ einmal und nur
  durch eine abgeschlossene Prüfung desselben Artikels, kein Löschen. Im Kernschema die Spalte `users.mat_psa_mails`
  (Vorgabe 1). Keine neue Erinnerungsstufe, kein Neuaufbau.
- Geprüft: frische Datenbank, 12→13, 7→13 an einer Kopie des Stands 7 (Zahlen aller Tabellen wie nach 7→12, Trigger
  da), zweiter Lauf ohne Änderung.
- **Rückweg**: Eine Fassung mit Schemaversion 12 übergeht Tabelle und Spalte; gemeldete Artikel bleiben dort gesperrt
  (Sperrgrund „Mangel gemeldet am …“), die Meldungen sieht sie nicht.
- Keine Handarbeit beim Update: `docker compose up -d --build` genügt.

### Entscheidungen

Entschieden bzw. bestätigt am 20.10.2026 – die Entscheidungen des Betreibers vor dem Bau (Plan
`p3/plan_phase3.md`, Bauentwurf 0.2 und 0.3):

1. **Meine PSA für jedes aktive Konto mit Namen und Zuordnung, auch ohne Modulstufe**; nur eigene Artikel; eng
   geschnitten neben der Modulzugangsprüfung, ohne Trennung und 404-Regeln aufzuweichen; der QR-Link landet sinnvoll.
2. **Keine Sichtprüfung im System.**
3. **Mangel melden**: die zugeordnete Person und alle mit lesen, verwalten oder prüfen an der Heimat.
4. **Jede Mangelmeldung sperrt sofort**; zurück nur über eine Freiprüfung; rotes Banner; sofort Mail an Materialwarte
   (Rückfall Material-/Plattform-Verwaltung wie bei den Erinnerungen) und Prüfer mit Prüffreigabe; Fotos optional bis 3;
   Beschreibung Pflicht; Missbrauch: Freiprüfung hebt auf, Journal mit Namen.
5. **Abschnitt „Deine PSA“** in der Sammelmail: 30 Tage vorher, überfällig, Lebensende in 90 Tagen; Vorgabe an;
   Abmeldung im Profil; Log, Einmaligkeit, Probelauf und DEMO wie bei den Erinnerungen; Link auf „Meine PSA“.
6. **Offline und Scan entfallen.**
7. **F1 – Einstieg**: Kopfleiste für Konten ohne Leserecht im Bestand (präzisiert: auch Mitglied ohne Freigabe – seit
   18.10.2026 Vorgabe neuer Konten), mit Leserecht Kasten unten auf der Übersicht.
8. **F2 – Inhalt**: zusätzlich Herstellerdokumente (Gebrauchsanleitung, Pflegehinweis, Konformitätserklärung,
   Datenblatt – keine Prüfanweisung) und Titel laufender Rückrufe.
9. **F3 – Aufbewahrung**: Mangelmeldungen (Text, Fotos, Melder) bleiben unbefristet mit dem Artikel; beim Löschen des
   Kontos verschwindet nur die Kennung, der Name bleibt; der Dialog „Konto löschen“ nennt ihre Zahl.
10. **F4 – Fotos**: Original sofort löschen (je Foto gleich nach seiner Verarbeitung), es bleiben Web- und
    Vorschaufassung ohne EXIF.
11. **A – Meine PSA zeigt zusätzlich** Sperrgrund (nur gesperrt/verloren), Bemerkung, Tag der letzten Prüfung und den
    Namen der Gliederung (keinen Ordnerpfad); weiter keine Protokolle, keine Prüfhistorie, kein Journal.
12. **B – Name und Text der Meldung** sieht, wer am Artikel ein Grund- **oder** Prüfrecht hat – auch der externe Prüfer
    mit befristeter Prüffreigabe: am Artikel, in der Prüfung, im Kasten „Gemeldete Mängel“ und in der Mail an Prüfer.
    Der Sperrgrund bleibt ohne Namen und Text, der Lebenslauf sagt „(Person)“. **Geändert am 21.10.2026** (siehe
    „Entscheidungen vom 21.10.2026“): Text, Fotos und Name nur noch für Prüfer und Materialwarte des Artikels und den
    Melder selbst.
13. Bestätigt (Bauentwurf 8.2): Sperre auch bei offenem Prüfentwurf, Häkchen je Meldung bei „einsatzbereit“;
    „instandsetzen“ erledigt nicht; Aussondern durch den Materialwart erst nach einer Prüfung seit der Meldung;
    Prüfart „außerplanmäßig“; keine Freigabe per Berichtigung; eine offene Meldung je Konto und Artikel, keine
    Tagesgrenze, kein Zurückziehen; keine Auswahl „Art des Mangels“; Sperrmitteilung an die zugeordnete Person (nicht
    abbestellbar, keine bei einer Sperre durch den Prüfer); Mails bei DEMO und auf dev ins Log; „Deine PSA“ nur, wer den
    Artikel nicht auch verwaltet, höchstens 50 Zeilen; „Mangel melden …“ grau, „Melden und sperren“ `btn danger`.
14. **Prüfer weit oben als Empfänger**: Anders als beim Rückruf (nur wer den Artikel geprüft hat) bekommt jeder Prüfer
    mit einer Prüffreigabe an der Heimat oder darüber die Mangel-Mail – so gewollt (Entscheidung 4).

### Abweichungen vom Konzept, mit Begründung

1. **Sperre durch die Meldung** – das Konzept ließ nur Prüfer sperren. Grund: Entscheidung 4; ein gemeldeter Mangel
   soll nie übersehen weiter benutzt werden. Zurück nur über die Freiprüfung.
2. **Sichtprüfung nicht quittiert** – das Konzept sah „Sichtprüfung quittieren“ vor. Grund: Entscheidung 2.
3. **Offline und Scan gestrichen** (In-App-Scan, Herstellercodes, Offline/PWA). Grund: Entscheidung nach der Recherche
   und Entscheidung 6; der QR-Link mit der Kamera-App des Telefons genügt.
4. **Mails an Zugeordnete** – das Konzept nannte nur Verwalter, Phase 2 · Lieferung 2 „nie an zugeordnete Personen“.
   Grund: Entscheidung 5, dazu die Sperrmitteilung bei fremder Meldung.
5. **Ohne Modulstufe die eigene PSA** – der Auftrag sah im MVP keine Rechte ohne Stufe vor. Grund: Entscheidung 1.

### Abweichungen vom Bauentwurf

KERN (Bauentwurf Abschnitt 11, hier vollständig):

1. Die Karte in „Meine PSA“ hat zusätzlich `last_inspected_on`, `lock_reason`, `notes` und `gliederung` (Entscheidung
   A); die Gliederung kommt aus einem einmal geladenen Ordnerbaum – die Zahl der Abfragen hängt nicht an der Zahl der
   Karten.
2. `melder` in der Schnittstelle und der Name in der Mail für Konten mit Grund- **oder** Prüfrecht (`mangel.darf_name`,
   Entscheidung B). Seit 21.10.2026 `mangel.darf_inhalt` – verwalten oder Prüfrecht, für Text, Fotos und Namen.
3. `_mailtext_zugeordnet` bekommt das Konto als viertes Argument – „Hallo <Name>“ braucht die Person.
4. `mangel.py` hat zusätzlich `meldung`, `fotos_json`, `offene_json`, `darf_name`, `_dateien_pruefen`, `_pruefer_von`,
   `NUR_NEUE_PRUEFUNG`, `LISTE_MAX`, `KURZ_MAX`; `offene_liste()` liefert (Zeilen, gesamt). Keine neue Schnittstelle.
5. Häkchen im Profil mit `label.inline` statt `label.check` (das es in `app.css` nicht gibt).
6. `mangel.melder` in der Antwort von `POST …/mangel` ist immer gesetzt – es ist der eigene Name.
7. **Der Melder fällt erst nach der Wahl der Verwalter heraus**: Ist er der einzige Verwalter der Heimat, gibt es
   keinen Rückfall der Mail auf Material- oder Plattform-Verwaltung – nur die Prüfer bekommen sie (er weiß es ja
   selbst).
8. Aussondern antwortet wie bisher 200 (nicht 201).
9. Der Test 7 → 13 läuft nur, wenn `MATERIAL_KOPIE_STAND_7` auf eine Kopie zeigt (sonst übersprungen); geprüft an
   einer Kopie des Stands 7.
10. `test_demo_probelauf` bis auf die vierte Zahl unverändert; DEMO-Einsatzkräfte mit PSA prüfen `test_psa_auswahl`
    und der Probelauf im Beispielbestand.
11. Zusätzlich angepasst: `test_material_stufen`, `test_material_beispielbestand`,
    `test_material_erinnerung.test_rechteschnitt` (Folgen der Entscheidungen 1 und 5).
12. **Ein Mangelfoto `orig`** antwortet mit Modulzugang 404, ohne Zugang 403 (wie alles ohne Zugang) – es gibt keine
    Datei, und ohne Stufe verrät die Antwort nichts.
13. **`maengel_gesehen`** mit unbrauchbarem Inhalt (keine Liste) → 400.

OBERFLÄCHE: Nach dem Melden steht der Text des Toasts zusätzlich als Hinweis oben auf der Seite, bis neu gezeichnet
wird – der Toast allein ist am Telefon schnell weg. „Mangel melden …“ in „Meine PSA“ ist ein normaler grauer Knopf (am
Telefon volle Breite), an der Artikelansicht `small` wie „Sperren“.

### Schnittstelle

Neu bzw. geändert (Einzelheiten in der Tabelle am Ende): `GET /material/meine-psa[/<id>]`, `GET /api/material/meine-psa`,
`PUT /api/material/meine-psa/mails`, `POST /api/material/artikel/<id>/mangel`; `GET /m/<token>`, `GET /material`
(ohne Stufe), Medien (eigene PSA ohne Stufe, Mangelfotos), `GET /api/material/start` (`maengel`, `maengel_gesamt`,
`meine_psa`), Artikel (`maengel`, `mangel_nur_gemeldet`, `mangel_eigen_offen`, Prüfart-Vorschlag), Listen (`mangel`),
Prüfung (`maengel`, `maengel_gesehen`, 409), Aussondern (409), Artikel löschen (409), Kontofolgen (`maengel`), Probelauf
(`mails[].psa`).
Meldung überall in derselben Gestalt: `{id, created_at, inhalt, description|null, fotos: [{vorschau, web}], melder|null,
offen, lock_before, erledigt: {am, pruefung, art}|null, wieder_offen: {pruefung, berichtigung, ergebnis, am}|null}` –
`inhalt: false` (seit 21.10.2026) für Konten, die den Artikel nur lesen und nicht gemeldet haben: dann `description`
und `melder` `null`, `fotos` leer;
`wieder_offen`, wenn die erledigende Freiprüfung später zu einem nicht freigebenden Ergebnis berichtigt wurde (dann
`offen: true`, `erledigt: null`).

### Im Browser geprüft

Chromium gegen einen lokalen Server **ohne `SMTP_HOST`** mit Platzhalter-Bestand (OG Musterstadt mit Lager und
DEMO-Kiste, Produktbild, Gebrauchsanleitung und Prüfanweisung, ein laufender Rückruf, ein Prüfentwurf mit allen
Punkten), bei 1280 und 360 px, Zeitzone Europe/Berlin, ohne Fehler in der Konsole und ohne waagerechten Bildlauf:

- **Ohne Modulstufe, mit Zuordnung**: keine Modulnavigation, keine Ordnerleiste, Kopfleiste „Meine PSA“ aktiv; drei
  Karten (überfällig mit Rückruf, einsatzbereit mit Bemerkung, DEMO), Prüfanweisung nicht in der Liste; QR-Link →
  eigene Karte, fremder Artikel 403; Dialog: leere Beschreibung → Fehler am Feld; Fotos nacheinander 1, 2, „Auswahl
  entfernen“ 0, dann 1 + 1 + 2 → 3 mit „Höchstens 3 Fotos.“ und ausgegrauter Wahl; gemeldet mit zwei Fotos →
  „Materialwart und Prüfer bekommen eine Mail …“, Karte gesperrt mit Banner „beiseite … Materialwart“, Knopf
  ausgegraut, Fotos groß („1 von 2“, Webfassung); DEMO-Artikel → „Es ging keine Mail hinaus …“ (Mail im Log);
  Profil-Häkchen aus und wieder an; `/material` → „Meine PSA“.
- **Mitglied ohne Freigabe, mit Zuordnung**: Übersicht mit Navigation, Kopfleiste „Meine PSA“, Kasten unten; „Meine
  PSA“ ohne „Zum Artikel“; QR fremd → Ansicht „fremd“ mit „Schaden entdeckt? …“.
- **Materialwart**: Kasten „Gemeldete Mängel“ oben (vor den Rückrufen) mit Namen, eigener Kasten „Meine PSA“ ganz
  unten, keine Kopfleiste; Banner mit Namen und zwei Fotos, „Aussondern“ ausgegraut mit Erklärung; Marke „Mangel“ in
  den Suchtreffern; selbst gemeldet → Prüfer bekommt die Mail (der Melder nicht), „Aussondern“ ausgegraut.
- **Prüfer intern**: „Prüfung starten“, „Sperren“, „Mangel melden …“ mit Hilfezeile; Prüfung starten am gemeldeten
  Artikel: Hinweis mit Namen, Prüfart „außerplanmäßig“ vorgewählt; 409-Weg: Entwurf offen, im zweiten Reiter meldet
  die Führungskraft – Festschreiben ohne Häkchen → 409, Prüfung lädt neu, Hinweis erscheint; zweiter Versuch mit
  Häkchen (Fokus darauf, „Festschreiben“ erst nach dem Abhaken frei) → festgeschrieben, Artikel frei, Meldung
  „erledigt durch Freiprüfung“ unter „Gemeldete Mängel“.
- **Externer Prüfer**: Name im Kasten und im Banner (Entscheidung B), „Mangel melden …“ da.
- **Plattform-Verwaltung**: Dialog „Nutzer löschen“ „… 2 Mangelmeldungen behalten den Namen.“; Probelauf
  „Person Platzhalter – 1 PSA“.

### Prüfung vor Auslieferung

Nach dem Bau drei unabhängige Prüfungen – **Sicherheit** (Datenschutz, Rechte, Robustheit; Proben gegen Dienste und
Routen, Migration an Kopien des Stands 7), **Ablauf** (Entscheidungen, Bauentwurf und Fachkritik gegen den Code; Proben
mit Platzhaltern, ohne Mailserver) und **Browser** (Rundgang in allen Rollen bei 1280 und 360 px, Server ohne
`SMTP_HOST`) – haben 11 Befunde gemeldet (3 + 3 + 5); Sicherheit 2 und Ablauf 1 sind derselbe. Jeder ist mit dem
Skript der Prüfung nachgestellt worden – die Oberflächenbefunde gegen eine Kopie des alten Stands auf denselben
Platzhalterdaten –, alle ließen sich nachstellen. Neun sind behoben, jeweils mit Test (Python bzw. statisch für die
Oberfläche), die neuen Tests scheitern am alten Stand; Sicherheit 3 ist bewusst unverändert (Zu prüfen). Die
Oberfläche ist im Browser bei 1280 und 360 px nachgesehen (ohne Konsolenfehler und waagerechten Bildlauf). Danach
liefen die ganze Suite und `pytest tests/test_pruefungen_import.py` grün, `st-py`, `st-js` und `st-css` ohne Meldung.

| Nr. | Quelle | Befund | Schwere | Umgang |
| --- | --- | --- | --- | --- |
| 1 | Sicherheit 1 | Die zweite Rechteprüfung in der Transaktion las das Leserecht aus der zu Beginn der Anfrage gerechneten Sicht und die Kontozeile von dort: Wurde während der Fotoverarbeitung (HEIC, bis zu 3 × 60 MP) die Freigabe entzogen oder das Konto deaktiviert, ging die Meldung durch und sperrte | niedrig | `mangel.melden` verwirft in der Transaktion die Sicht (`rechte.sicht_verwerfen`) und liest die Kontozeile neu (nur aktiv, sonst 404); `_recht` rechnet damit. Test `test_recht_in_der_transaktion` (Freigabe entzogen, Konto deaktiviert: 404, keine Meldung, keine Sperre, Fotos weg) |
| 2 | Sicherheit 2, Ablauf 1 | Ohne Mailserver (`SMTP_HOST` leer) antwortete `POST …/mangel` mit `mail: true`, die Quittung sagte „Materialwart und Prüfer bekommen eine Mail“ – `send_mail` schrieb nur ins Log | niedrig–mittel | Ohne Mailserver wie bei DEMO und dev: Betreff und Text ins Log („Mail nicht verschickt (kein Mailserver)“), `mail: false`, Quittung „Es ging keine Mail hinaus – sag deinem Materialwart Bescheid …“. Mit Mailserver vorsichtiger: „Die Mail an Materialwart und Prüfer ist unterwegs.“ – ein späterer Fehlschlag im Hintergrund steht weiter nur im Log (so entworfen, Zu prüfen Nr. 5). Test `test_ohne_mailserver`; im Browser ohne `SMTP_HOST` |
| 3 | Sicherheit 3 | Prüfanweisung und Original des Produktbilds (mit Aufnahmedaten) bekommt ein Mitglied ohne Freigabe weiter über den Katalog – die Grenzen von „Meine PSA“ gelten nur ohne Modulstufe | niedrig (vorbestehend) | Nicht geändert: Der Katalog ist für jeden mit Modulzugang lesbar, so seit Phase 1 und vor dieser Lieferung. Festgehalten unter Zu prüfen Nr. 6 |
| 4 | Ablauf 2 | Eine Freiprüfung, die eine Meldung erledigt hatte, ließ sich zu „instandsetzen“ berichtigen (sperrt wieder) – die Meldung stand aber weiter „erledigt durch Freiprüfung“: kein Banner, keine Marke, die nächste Freiprüfung ohne Häkchen | niedrig | Abgeleitet, ohne die unveränderliche Zeile zu ändern (`mangel.stand`): Wurde die erledigende Freiprüfung – auch über eine Kette von Berichtigungen – zu einem nicht freigebenden Ergebnis berichtigt, ist die Meldung wieder offen, bis die nächste Freiprüfung (mit Häkchen) oder Aussonderung kommt. Banner und Prüfung zeigen „Freiprüfung später berichtigt (jetzt: instandsetzen)“ mit Link auf die Berichtigung, `wieder_offen` an der Meldung; Marke, „Meine PSA“, eigene offene Meldung (409), keine weitere Berichtigung. Der Kasten „Gemeldete Mängel“ bleibt leer und die Prüfart „Reparatur“ – ein Prüfer hat den Artikel angesehen, wie nach „instandsetzen“. Eine weitere Abfrage nur, wenn es am Artikel eine solche Berichtigung gibt. Test `test_berichtigte_freipruefung`; im Browser (Link im roten Banner weiß, wie im Rückruf-Banner) |
| 5 | Ablauf 3 | Die Sperrmitteilung an die Trägerin sagte „Sie ist damit gesperrt.“ (Betreff „ist gesperrt“) auch, wenn der Artikel schon gesperrt oder als verloren gemeldet war | niedrig | Wie die Mail an Verwalter und Prüfer nach dem Zustand vor der Meldung: „Sie war schon gesperrt und bleibt es.“ bzw. „Sie ist als verloren gemeldet. Taucht sie auf: nicht verwenden, gib sie deinem Materialwart.“ (Betreff „… ist als verloren gemeldet – nicht verwenden“). Test `test_sperrmitteilung_vorher` |
| 6 | Browser 1 | An der Artikelseite blieb „Mangel melden …“ aktiv, obwohl das Konto dort schon eine offene Meldung hatte – Text und Fotos waren umsonst, erst „Melden und sperren“ brachte 409 | niedrig–mittel | Neues Feld `artikel.mangel_eigen_offen` (Zeitpunkt der eigenen offenen Meldung oder `null`); der Knopf ist dann ausgegraut mit Hilfezeile wie in „Meine PSA“ („Du hast am … schon gemeldet – ein Prüfer sieht es sich an.“, ohne den Satz „an den Materialwart“ für den, der den Artikel verwaltet). Test `test_eigene_offene_am_artikel` und statisch; im Browser |
| 7 | Browser 2 | „Meine PSA“ ohne Zuordnung verlinkte „im Profil ändern“ auf einen Abschnitt, den das Profil dann nicht zeigt | niedrig | Die Zeile steht unter derselben Bedingung wie der Abschnitt im Profil (zugeordnet oder abbestellt). Statisch; im Browser |
| 8 | Browser 3 | Für die Abweichungen des KERN verwies der CHANGELOG auf den Bauentwurf außerhalb des Repositorys – verhaltensrelevant u. a. Nr. 7, 12, 13 | niedrig (Doku) | Alle 13 Abweichungen kurz unter „Abweichungen vom Bauentwurf“ |
| 9 | Browser 4 | Ohne Modulstufe hieß der Browser-Reiter „Material – strömis.de“, obwohl die Person nirgends „Material“ sieht | Hinweis | Ohne Modulzugang „Meine PSA – strömis.de“ (`seite.html`, `nur_psa`). Statisch; im Browser |
| 10 | Browser 5 | Nach „Melden und sperren“ zeichnete die Seite neu und der Fokus fiel auf `body` | Hinweis | Die Quittung oben (`role="status"`) hat `tabindex="-1"` und bekommt nach dem Neuzeichnen den Fokus – in „Meine PSA“ und an der Artikelseite. Statisch; im Browser |

### Entscheidungen vom 21.10.2026

Nach der Prüfung vor Auslieferung entschieden bzw. bestätigt:

1. **Geändert – Text, Fotos und Name der Mangelmeldung nur für Prüfer und Materialwarte des Artikels** (und den Melder
   bei seiner eigenen Meldung). Ersetzt Entscheidung B (Nr. 12: jedes Grund- oder Prüfrecht). Sehen dürfen
   (`mangel.darf_inhalt`): Konten mit Prüfrecht am Artikel (wirksame Prüffreigabe, auch die befristete des externen
   Prüfers) und Konten, die ihn verwalten (Materialwart; Material- und Plattform-Verwaltung zählen wie verwalten). Wer
   den Artikel nur liest, sieht weiter das Banner „MANGEL GEMELDET am …“ mit dem Satz „Was gemeldet wurde, sehen nur
   Prüfer und Materialwart.“, die Marke „Mangel“ und – im Kasten „Gemeldete Mängel“ – Artikel und Tag, aber keinen
   Text, kein Foto, keinen Namen. **Der Name des Melders folgt derselben Regel** (vorher sah ihn jeder mit Grundrecht):
   in `artikel.maengel`, `pruefung.maengel`, `start.maengel` und im Verlauf am Artikel („Mangel gemeldet“ von
   „(Person)“, außer bei der eigenen Meldung). Die Mangelfotos antworten reinen Lesern 404 wie Unbekanntes (auch die
   Vorschau). Die Trägerin sieht eine fremde Meldung weiter nur als Zeitpunkt („Meine PSA“), der Lebenslauf sagt weiter
   „(Person)“ ohne Text. Mails: wie bisher an Verwalter (Rückfall Material-/Plattform-Verwaltung) und Prüfer – die
   volle Mail mit Namen und Text geht nur an Konten, die beides sehen dürfen; reine Leser bekamen ohnehin keine (die
   Prüfung dafür ist jetzt `darf_inhalt` statt des Leserechts, der Zweig „Jemand mit Zugriff auf den Artikel“ in der
   Mail ist entfallen). **Nicht geändert**: Prüfanweisungen und Bild-Originale im Katalog bleiben wie bisher für alle
   mit Modulzugang sichtbar (Zu prüfen Nr. 6). Tests `test_inhalt_nur_pruefer_und_materialwart` (neu),
   `test_sichtbarkeit`, `test_mail` und `test_material_meine_psa.test_medien` angepasst. Im Browser bei 1280 und
   360 px gegengeprüft: Leser (Banner ohne Text, Name und Fotos, Kasten nur mit Artikel und Tag, Foto-Adresse 404),
   Materialwart und externer Prüfer (Text, Name, Fotos groß).
2. **Bestätigt – wieder offene Meldung nach berichtigter Freiprüfung** steht nicht im Kasten „Gemeldete Mängel“ (ein
   Prüfer hat den Artikel angesehen), vorgeschlagen ist die Prüfart „Reparatur“ (Prüfung vor Auslieferung Nr. 4).
3. **Bestätigt – Versandfehler im Hintergrund nur im Log** („Mangel …: Mail an … gescheitert“); die Quittung sagt
   „unterwegs“ (Prüfung vor Auslieferung Nr. 2).

### Zu prüfen

1. **Am eigenen iPhone**: QR-Link einer zugeordneten PSA ohne Modulstufe, zwei Fotos nacheinander mit der Kamera
   (Liste zeigt beide), HEIC.
2. **Mails an Konten ohne Modulstufe** – auch die nicht abbestellbare Sperrmitteilung an die zugeordnete Person – im
   Verfahrensverzeichnis der Gliederung (Vorschlag im README unter „Austritt und Löschen“) abstimmen.
3. **Auf dev.strömis.de** die Mangel-Mails im Log des Dienstes lesen, bevor sie in der Produktion hinausgehen.
4. **Prüfer weit oben**: Ob jeder Prüfer mit Prüffreigabe an einer übergeordneten Gliederung die Mangel-Mail bekommen
   soll (so gebaut, Entscheidung 4) – nach den ersten Wochen im Betrieb ansehen.
5. **Versand im Hintergrund** (Prüfung Nr. 2): Lehnt der Mailserver eine Mangel-Mail ab, steht das nur im Log
   („Mangel …: Mail an … gescheitert“); der Melder hat da schon „Die Mail an Materialwart und Prüfer ist unterwegs.“
   gelesen. Ohne Mailserver sagt die Quittung „Es ging keine Mail hinaus“. Ob das genügt – die Quittung sagt ohnehin,
   den Artikel dem Materialwart zu geben –, nach den ersten Meldungen im Betrieb ansehen. **Bestätigt am 21.10.2026**
   (Entscheidungen vom 21.10.2026 Nr. 3): bleibt so.
6. **Prüfanweisung und Bild-Original für Mitglieder ohne Freigabe** (Prüfung Nr. 3, vorbestehend): „Meine PSA“ zeigt
   keine Prüfanweisung und vom Produktbild nur Web- und Vorschaufassung – das schützt aber nur Konten **ohne**
   Modulstufe. Wer Mitglied ist (seit dem 18.10.2026 die Vorgabe neuer Konten), liest wie bisher den ganzen Katalog
   (`/api/material/produkte/<id>`, `/media/material/dok/…`, `/media/material/orig/…`), auch ohne Freigabe. Bewusst so
   gelassen; entscheiden, ob für Konten ohne Grundrecht irgendwo dieselben Grenzen wie in „Meine PSA“ gelten sollen.
   **Am 21.10.2026 nicht geändert** (Entscheidungen vom 21.10.2026 Nr. 1): Prüfanweisungen und Bild-Originale im
   Katalog bleiben für alle mit Modulzugang sichtbar; enger geworden sind nur Text, Fotos und Name der Mangelmeldung.
7. **Berichtigte Freiprüfung** (Prüfung Nr. 4): Eine wieder offene Meldung steht nicht im Kasten „Gemeldete Mängel“
   (ein Prüfer hat den Artikel angesehen), Banner und Marke zeigen sie. Ob das so passt, beim ersten Fall ansehen.
   **Bestätigt am 21.10.2026** (Entscheidungen vom 21.10.2026 Nr. 2): so lassen, Prüfart „Reparatur“.

### Nachbesserungen nach der Auslieferung (Wünsche vom 21.10.2026)

1. **Seriennummer und Herstelldatum stehen seit der ersten Prüfung fest.** Wunsch: „Die Seriennummer und das
   Herstelldatum eines Artikels sollen nach der ersten Prüfung nicht mehr geändert werden dürfen. Setze sie daher im
   Bearbeiten-Dialog auch nebeneinander ganz oben.“
   - **Wann fest**: sobald der Artikel eine **abgeschlossene** Prüfung hat (`mat_inspection.completed_at` gesetzt – im
     Modul heißt das zugleich festgeschrieben, mit Protokoll). Jede Prüfart zählt, auch Eingangsprüfung, Berichtigung und
     Aussonderung; ein offener **Entwurf zählt nicht** – bis zum Festschreiben lässt sich die Nummer noch berichtigen
     (etwa wenn der Prüfer bei der Eingangsprüfung das Etikett liest). Beide Werte stehen im Prüfprotokoll
     („Seriennummer“, „hergestellt“) und tragen das Lebensende textiler Artikel.
   - **Dienst** (`bestand.artikel_aendern`): eine echte Änderung von `serial_no` oder `manufactured_on` → **409**
     „Seriennummer und Herstelldatum stehen seit der ersten Prüfung fest – sie sind Teil des Prüfnachweises.“ Geprüft
     frisch unter der Schreibsperre (eine eben abgeschlossene Prüfung zählt schon). Keine Änderung sind: weggelassene
     Felder, eine leere Seriennummer („behält“), dieselbe Seriennummer in anderer Groß- und Kleinschreibung (wie beim
     Vergleich der Seriennummern; gespeichert bleibt die bisherige Schreibweise) und dasselbe Herstelldatum. Aus einem
     Tagesdatum einen Monat zu machen (oder umgekehrt) und ein Herstelldatum nachzutragen oder zu löschen ist eine
     Änderung. **Auch eine vom System vergebene STR-Nummer** lässt sich danach nicht mehr durch eine Herstellernummer
     ersetzen – die STR-Nummer steht im Protokoll (siehe Offen Nr. 1). Andere Felder (Kauf, Erstgebrauch, Intervall,
     Fälligkeit, Lebensende, Bemerkung) wie bisher. Andere Schreibwege gibt es nicht: Bestandsimport und Anlegen legen
     nur neue Artikel an (ein vorhandener wird übersprungen, nie aktualisiert), Verschieben, Sperren, Prüfen, Zuordnen
     und die Katalogpflege schreiben andere Spalten.
   - **Datenbank**: Trigger `mat_item_stammdaten_fest` (Schritt 14) – `BEFORE UPDATE OF serial_no, manufactured_on ON
     mat_item`, wenn sich ein Wert wirklich ändert und eine abgeschlossene Prüfung des Artikels existiert. Wie die
     Trigger aus Schritt 6 fängt er, was am Dienst vorbeiginge (über die Schnittstelle käme er als 409 „Bitte neu
     laden“ an); derselbe Wert geht durch, weil `artikel_aendern` jede Spalte neu schreibt.
   - **Schnittstelle**: Der Artikel trägt `stammdaten_fest` (true/false).
   - **Oberfläche** (Dialog „Artikel … bearbeiten“): Seriennummer und Herstellung (Monat) stehen **ganz oben
     nebeneinander** – auch am Telefon (unter 480 px im Verhältnis 3 : 2, die Felder unten bündig). Sind sie fest,
     sind beide schreibgeschützt (grau hinterlegt, Wert sichtbar, ein fehlendes Herstelldatum als „–“; bei einer
     STR-Nummer heißt das Feld „Seriennummer (vom System)“), darunter steht „Seit der ersten Prüfung fest – Teil des
     Prüfnachweises.“, und der Dialog schickt sie nicht mehr mit. Sonst wie bisher, mit dem Hinweis „Seriennummer:
     Leer lassen behält die Nummer. Eine echte Herstellernummer ersetzt die vom System vergebene.“ Darunter Kauf |
     Erstgebrauch, Prüfintervall | nächste Prüfung, Lebensende (textil), Bemerkung – die Felder selbst unverändert.
   - **Anlegen bleibt, wie es war**: Es ist ein eigenes Formular (nicht derselbe Dialog), dort kommen Produkt und
     Ordner zuerst, die Seriennummer hat ihren langen Hinweis zur STR-Nummer über die volle Breite, und Herstellung
     folgt direkt darunter neben Kauf – festschreiben lässt sich beim Anlegen noch nichts.
   - **Migration**: **Schritt 14**, Schemaversion 14, beim Start von selbst, rein additiv und wiederholbar (nur der
     Trigger). Geprüft: frische Datenbank, 13→14 (Daten unverändert), 7→14 an einer Kopie des Stands 7 (Zahlen aller
     Tabellen wie nach 7→13, Trigger greift an einem geprüften Artikel der Kopie), zweiter Lauf ohne Änderung.
     **Rückweg**: Eine Fassung mit Schemaversion 13 übergeht den Trigger – er bliebe dann aber wirksam (eine Änderung
     der Werte nach der ersten Prüfung käme dort als 409 „Bitte neu laden“ an); `DROP TRIGGER mat_item_stammdaten_fest`
     nimmt ihn heraus. Keine Handarbeit beim Update.
   - Tests: `tests/test_material_stammdaten.py` (neu: Dienst – 200 vor der Prüfung und mit Entwurf, 409 nach der
     Prüfung für Seriennummer, Herstelldatum, Tag statt Monat, Löschen und STR-Nummer, 200 bei denselben Werten;
     Trigger; Migration 14; Oberfläche statisch), `test_material_mangel.test_migration_13` liest die Endversion statt
     „13“. Im Browser bei 1280 und 360 px gegengeprüft: Artikel vor der ersten Prüfung (beide Felder bearbeitbar, oben
     nebeneinander), geprüfter Karabiner, geprüfter Karabiner mit STR-Nummer ohne Herstelldatum, geprüfter Gurt (textil,
     mit Lebensende) – schreibgeschützt mit Hinweis, Speichern der Bemerkung geht, keine Konsolenfehler, kein
     waagerechtes Scrollen.
   - **Offen**:
     1. **STR-Nummer nach der ersten Prüfung**: Findet sich später doch eine Herstellernummer (etwa nach einem Rückruf
        mit Seriennummern, die eine STR-Nummer nie trifft), lässt sie sich nicht mehr eintragen – nur in die Bemerkung.
        Eine Ausnahme „STR → Herstellernummer, einmal, mit Journal“ ist nicht gebaut; entscheiden, ob sie gewünscht ist.
     2. **Herstelldatum nachtragen**: Bei Metall ist das Herstelldatum keine Pflicht; fehlt es bei der ersten Prüfung,
        lässt es sich danach nicht mehr nachtragen (auch das wäre eine Änderung gegenüber dem Protokoll). Entscheiden,
        ob „leer → Wert“ erlaubt sein soll.
     3. **Tippfehler nach der ersten Prüfung**: Korrigieren geht nicht mehr – auch nicht über eine Berichtigung der
        Prüfung (die berichtigt die Befunde, nicht die Stammdaten). Bleibt es dabei, ist der Weg Aussondern und neu
        anlegen; sonst bräuchte es eine Korrektur der Material-Verwaltung mit Grund und Journal.
   - Die drei offenen Punkte hat der Nutzer am selben Tag entschieden – siehe Nr. 2.

2. **Änderungsanträge an festen Stammdaten** (Entscheidungen des Nutzers vom 21.10.2026 zu den Offen-Punkten aus Nr. 1).
   - **Entscheidungen**:
     1. **Herstelldatum nachtragen** (vorher leer → Wert) ist nach der ersten Prüfung direkt erlaubt, ohne Antrag – aber
        **nur bei Material „Metall“** (`metall_hardware`). Bei textil (dort ohnehin Pflicht) und „sonstiges“ nicht.
        Ändern und Entfernen eines vorhandenen Herstelldatums bleibt gesperrt.
     2. + 3. **Jede andere Änderung** von Seriennummer oder Herstelldatum nach der ersten Prüfung – ausdrücklich auch das
        Ersetzen einer vom System vergebenen STR-Nummer durch die echte Herstellernummer – lässt sich **mit Begründung
        beantragen**, ähnlich dem Produkt-Melden-System. Die Material-Verwaltung (die Plattform-Verwaltung zählt wie sie)
        bestätigt oder lehnt ab, über den Knopf „Meldungen“ im Katalog (eigener Bereich „Änderungsanträge“ neben den
        Produktmeldungen; die Blase am Knopf zählt die offenen mit). Bestätigt wird die Änderung übernommen (Journal am
        Artikel mit altem und neuem Wert, Antragsteller, Bestätiger, Begründung), abgelehnt mit Begründung. Mail an die
        Material-Verwaltung bei neuem Antrag (Muster Produktmeldung, Rückfall Plattform-Verwaltung) und an den
        Antragsteller bei der Entscheidung; DEMO, dev-Sperre und ohne Mailserver ins Log wie im Modul üblich.
   - **Nachtragen bei Metall** (`bestand.artikel_aendern`, `herstellung_nachtragbar`): Ist das Herstelldatum leer und das
     Produkt aus Metall, geht ein Wert durch (Journal „geändert“ wie bisher); danach steht es wie die Seriennummer fest.
     Nur, solange der Artikel noch nie eins hatte – nach einem Entfernen per Antrag nur per Antrag (Befund 5 der Prüfung).
     Im Dialog „Artikel … bearbeiten“ ist das Feld dann bearbeitbar, der Hinweis sagt „Herstellung: Nur Nachtragen möglich
     – danach steht sie ebenfalls fest.“ Ein Antrag fürs Nachtragen bei Metall wird mit 409 und dem Hinweis auf den
     direkten Weg abgewiesen. Die 409 beim Bearbeiten sagt jetzt dazu: „Eine Änderung beantragst du mit Begründung bei der
     Material-Verwaltung.“
   - **Wer beantragt**: wer den Artikel verwaltet (Materialwart; Material- und Plattform-Verwaltung zählen wie
     verwalten) **und Prüfer mit wirksamem Prüfrecht am Artikel** (auch der externe mit befristeter Prüffreigabe) – sie
     sehen Abweichungen beim Prüfen. Fremde Gliederung 404 wie unbekannt, nur Leserecht 403. Kein Antrag an einem
     ungeprüften Artikel (dort geht es direkt, 409 mit Hinweis) und an einem ausgesonderten (409).
   - **Wer entscheidet**: die Material-Verwaltung, die Plattform-Verwaltung eingeschlossen. **Ihren eigenen Antrag darf
     sie selbst bestätigen** – einfachste Lösung; das Journal nennt Antragsteller und Bestätiger (Bitte bestätigen, Nr. 1).
   - **Antrag**: je Feld eine Zeile mit altem und neuem Wert, alle aus einem Dialog mit derselben Begründung (Pflicht,
     höchstens 1000 Zeichen); **höchstens ein offener Antrag je Artikel und Feld** (409 „läuft schon ein Antrag (vom …)“),
     das andere Feld geht. Geprüft **beim Antrag und beim Bestätigen** am frisch gelesenen Artikel: Seriennummer nicht
     leer, nicht dieselbe, nicht in der Form „STR-…“, je Produkt eindeutig (sichtbare Dublette 409 mit Inventarnummer,
     fremde 409 ohne und protokolliert wie beim Bearbeiten); Herstelldatum als Monat oder Tag, nicht in der Zukunft, nicht
     nach Kauf oder Erstgebrauch, bei textil nicht entfernen (bei Metall und „sonstiges“ ließ sich das Entfernen
     beantragen – „Herstelldatum entfernen (unbekannt)“; **seit 21.10.2026 nicht mehr**, siehe „Entscheidungen vom
     21.10.2026 zur Prüfung“). Beim Bestätigen muss der Artikel noch den alten Wert tragen
     (sonst 409 „bitte ablehnen“), ein inzwischen ausgesonderter lässt nur noch Ablehnen zu (409).
   - **Bestätigen** (`antrag.bestaetigen`): in einer Transaktion Antrag entscheiden und Artikel ändern. Eine
     Herstellernummer ersetzt die STR-Nummer (`serial_generated` 0); bei textil rechnet das Lebensende mit dem neuen
     Herstelldatum neu (ein von Hand vorgezogenes bleibt, wenn es früher liegt). Journal am Artikel „Änderung bestätigt
     (Antrag)“: vorher/nachher je Feld, dazu `antrag` (Nr.), `beantragt_von`, `begruendung`, ggf. `anmerkung`; als
     Handelnder steht der Bestätiger. Dazu „Änderung beantragt“ beim Antrag und „Änderungsantrag abgelehnt“ (mit
     `ablehnung`). Der **Lebenslauf** zeigt dieselben Einträge (beschriftung.py). **Festgeschriebene Protokolle und ihre
     PDFs bleiben unverändert** – sie nennen die alte Nummer; ein Sammelprotokoll, das ein Durchgang erst nach der
     Bestätigung festschreibt, liest den Artikel dann mit der neuen.
   - **Rückrufe**: Der Seriennummernabgleich liest `mat_item.serial_no` beim Abfragen – nach der Bestätigung trifft ein
     Rückruf die neue Nummer, die alte nicht mehr (Test).
   - **Datenbank (Schritt 15)**: Tabelle `mat_item_change` (AUTOINCREMENT; Feld, alter und neuer Wert, Begründung,
     Stand offen | bestätigt | abgelehnt, Antwort – bei Ablehnung Pflicht –, Antragsteller und Entscheider je mit Kennung
     und Namen, `applied_at`), eindeutiger Index „ein offener je Artikel und Feld“. Der Trigger
     `mat_item_stammdaten_fest` wird ersetzt (gleicher Name): Nach der ersten Prüfung lässt er nur noch (a) das
     Nachtragen bei Metall und (b) **genau die Änderung eines bestätigten, noch nicht angewendeten Antrags** zu – alter
     UND neuer Wert müssen passen. `mat_item_antrag_angewendet` (AFTER UPDATE) setzt in derselben Anweisung
     `applied_at`: Ein Antrag wirkt genau einmal. Die Antragstabelle ist per Trigger fest: nur offen einfügbar, Inhalt
     unveränderlich, einmal entscheiden, kein Löschen (auch nicht per INSERT OR REPLACE), `applied_at` einmal und nur
     nach der Bestätigung, Kontokennungen nur auf NULL. Wer die Datenbank direkt bearbeitet, ändert Seriennummer und
     Herstelldatum damit nicht mehr per `UPDATE` ohne Antragsspur; die Umwege über `INSERT OR REPLACE`, Kennung,
     Löschen, Produktwechsel und Materialart schließt erst Schritt 16 (siehe „Prüfung“ unten). Wer Trigger entfernt
     (`DROP TRIGGER`), kommt an allem vorbei – die Trigger schützen vor Versehen und Umwegen, nicht vor jemandem mit
     Schreibzugriff auf die Datei.
   - **Löschkonzept**: Antragsteller und Entscheider bleiben namentlich (Handelnde an Prüfnachweisdaten, wie Prüfer und
     Melder eines Mangels), die Kennungen setzt die Datenbank auf NULL – anders als bei Produktmeldungen, die
     Arbeitsdaten des Katalogs sind und „(gelöschtes Konto)“ bekommen (Bitte bestätigen, Nr. 2). Der Dialog „Konto
     löschen“ nennt die Zahl („… Änderungsanträge behalten den Namen.“, `material-folgen.antraege`).
   - **Oberfläche**: Dialog „Artikel … bearbeiten“ – bei festen Stammdaten unter den beiden Feldern grau „Änderung
     beantragen …“ und je offenem Antrag der Hinweis „Seriennummer: alt → neu – Änderung beantragt am … von … – wartet
     auf die Material-Verwaltung.“; Prüfer ohne Verwalterrecht finden denselben Knopf unter den Stammdaten der
     Artikelseite, dort steht auch der Hinweis (wer nur liest, sieht nur Feld und Datum). Antragsdialog: neue
     Seriennummer und/oder neue Herstellung, bei Metall und „sonstiges“ „Herstelldatum entfernen“ (seit 21.10.2026
     entfallen), Begründung Pflicht, ein
     roter Knopf „Antrag senden“. Katalog → „Meldungen“: Bereichswahl „Produktmeldungen | Änderungsanträge (n)“, darunter
     offen | erledigt | alle; je Karte Artikel (Link), Produkt, Feld alt → neu, Begründung, Antragsteller, Datum und
     Gliederung, „dein eigener Antrag“; nur graue Knöpfe „Bestätigen …“ und „Ablehnen …“ (Knopfregel: mehrere Karten,
     also kein Rot in der Liste) – der rote Hauptknopf „Bestätigen“ steht im Rückfragedialog (mit freiwilliger Anmerkung),
     „Ablehnen“ ist wie bei den Produktmeldungen endgültig und rot umrandet (`btn danger`), Begründung Pflicht. Die Blase
     am Knopf „Meldungen“ zählt Produktmeldungen und Anträge zusammen (Titel nennt beide), die Übersicht der
     Material-Verwaltung nennt offene Anträge mit Link. Materialwarte und Prüfer sehen im Bereich ihre eigenen Anträge.
   - **Migration**: **Schritt 15**, Schemaversion 15, beim Start von selbst, rein additiv und wiederholbar (Tabelle,
     Indizes, Trigger; der alte Trigger wird entfernt und in der neuen Fassung angelegt). Geprüft: frische Datenbank,
     14 → 15 (Tabelle und Trigger entfernt, Trigger aus Schritt 14 wieder angelegt: Zahlen aller Tabellen gleich, Trigger
     ersetzt), 7 → 15 an einer **Kopie** des Stands 7 (Zahlen wie 7 → 14, neue Tabelle leer, Trigger greift an einem
     geprüften Artikel), zweiter Lauf ohne Änderung. **Rückweg**: Eine Fassung mit Schemaversion 14 übergeht Schritt 15;
     der neue Trigger bliebe wirksam – gegenüber Schritt 14 lässt er nur die beiden Ausnahmen zu, und Anträge legt eine
     ältere Fassung nicht an –, die Tabelle bliebe ungenutzt. Keine Handarbeit beim Update.
   - **Schnittstelle**: `POST /api/material/artikel/<id>/antrag`, `GET /api/material/antraege`,
     `POST /api/material/antraege/<id>/bestaetigen`, `…/ablehnen`; Artikel `antraege`, `darf_antrag`,
     `herstellung_nachtragbar`; `start.antraege_offen`, `meldungen.antraege_offen`, Kontofolgen `antraege` (Tabelle
     unten).
   - **Tests**: `tests/test_material_antrag.py` (neu: Nachtragen Metall direkt vs. „sonstiges“ und textil 409; Rechte je
     Rolle mit fremder Gliederung 404, ohne Stufe, Führungskraft, Prüfer, Material- und Plattform-Verwaltung; Eingaben
     und Eindeutigkeit beim Antrag und beim Bestätigen; Bestätigen mit Journal, Lebensende, Stand geändert, ausgesondert,
     eigener Antrag der Material-Verwaltung; Ablehnen; Trigger an der Schnittstelle vorbei; Mails mit Rückfall, dev-Sperre,
     ohne Mailserver und DEMO; Artikel und Zahlen; Rückruf mit neuer Nummer; Löschkonzept; Migration 15; Oberfläche
     statisch). Angepasst: `test_material_stammdaten.py` (neuer Text der 409, Endversion, Trigger 15),
     `test_material_trennung`, `test_material_stufen`, `test_material_ueberblick` (Kennung für die neuen Routen),
     `test_material_stufen` und `test_material_zuordnung` (Kontofolgen mit `antraege`), `test_material_mangel` (7 → 13
     zählt die neue Tabelle nicht mit), `test_material_beschreibung` (21 statt 19 Stellen mit Produktname und Zusatz).
   - **Im Browser geprüft** (Platzhalterbestand, kein Mailserver – die Mails standen im Log) bei 1280 und 360 px:
     Materialwart trägt bei einem geprüften Karabiner mit STR-Nummer das Herstelldatum nach, beantragt die
     Herstellernummer (ohne Angabe und ohne Begründung kommt ein Hinweis), sieht den offenen Antrag an Artikel und
     Dialog; Prüfer beantragt am Gurt über die Stammdaten ein anderes Herstelldatum; die Material-Verwaltung sieht die
     Blase (2), wechselt zu „Änderungsanträge“, bestätigt den einen (Rückfrage mit Anmerkung) und lehnt den anderen ab
     (ohne Begründung Hinweis), „erledigt“ zeigt beide; das Journal des Karabiners zeigt Antrag und Bestätigung.
     Keine Konsolenfehler, kein waagerechtes Scrollen, je Dialog höchstens ein roter Knopf.
   - **Bitte bestätigen** (entschieden am 21.10.2026 – Nr. 1 bis 3 bestätigt, Nr. 4 und 5 geändert, siehe
     „Entscheidungen vom 21.10.2026 zur Prüfung“ unten):
     1. **Eigener Antrag**: Die Material-Verwaltung darf ihren eigenen Antrag selbst bestätigen (auch wenn es eine
        zweite gibt) – das Journal nennt beide Namen, die Karte sagt „dein eigener Antrag“. Alternative: sperren, wenn es
        eine zweite Material-Verwaltung gibt. **Bestätigt am 21.10.2026.**
     2. **Namen beim Kontolöschen**: Anträge behalten Antragsteller und Entscheider namentlich (wie Mangelmeldungen) –
        bei Produktmeldungen werden die Namen „(gelöschtes Konto)“. Begründung: Der Antrag erklärt eine Änderung an
        Prüfnachweisdaten; das Journal nennt dieselben Namen ohnehin. **Bestätigt am 21.10.2026.**
     3. **Prüfer dürfen beantragen** (neben dem Materialwart), auch der externe Prüfer mit befristeter Prüffreigabe.
        **Bestätigt am 21.10.2026.**
     4. **Kein Zurückziehen**: Einen offenen Antrag kann der Antragsteller nicht selbst zurücknehmen – ein Tippfehler im
        Antrag wird von der Material-Verwaltung abgelehnt, danach lässt sich neu beantragen. **Geändert am 21.10.2026**:
        Der Antragsteller zieht seinen offenen Antrag selbst zurück.
     5. **Entfernen eines Herstelldatums** (Metall, „sonstiges“) ist als Antrag möglich; bei textil nicht. **Geändert am
        21.10.2026**: Das Herstelldatum lässt sich nicht entfernen, auch nicht per Antrag – nur ändern.
   - **Prüfung** (unabhängige Prüfung von 315425a am 21.10.2026, Proben mit Platzhaltern, Migration nur an einer Kopie
     des Stands 7): sechs Befunde, jeder vor der Behebung mit der Probe der Prüfung nachgestellt; alle behoben, jeweils
     mit Test (`tests/test_material_antrag.py`, Abschnitt 10 – jeder neue Test scheitert ohne die Änderung), Befund 5
     nach der Entscheidung des Nutzers vom selben Tag.

     | # | Befund | Schwere | Umgang |
     | --- | --- | --- | --- |
     | 1 | Wer den Artikel nur liest (etwa Führungskraft), sah im Verlauf des Artikels und im Lebenslauf-PDF Begründung, Antragsteller, Bestätiger, Anmerkung und Ablehnungsgrund – die Antragsansicht verbirgt genau das (`inhalt: false`) | mittel | Eine Linie: Für Konten ohne Inhaltsrecht (dieselbe Regel wie `antrag_json`: verwalten oder Prüfrecht am Artikel) entfernt `antrag.journal_verbergen` aus den Einträgen „Änderung beantragt / bestätigt (Antrag) / Änderungsantrag abgelehnt“ `begruendung`, `beantragt_von`, `anmerkung`, `ablehnung`, als Handelnder steht „(Person)“ – Muster `_melder_verbergen`, in `artikel_json` und im Lebenslauf (`lebenslauf.daten`). Feld, alter und neuer Wert, Antrag Nr. und Zeitpunkt bleiben: Die Stammdaten sieht der Leser ohnehin, die Antragsansicht zeigt ihm dieselben Werte. Materialwart und Prüfer sehen alles. Test `test_leser_ohne_inhalt` (API und PDF-Text) |
     | 2 | Der Bescheid an den Antragsteller ging ohne Blick auf seine heutigen Rechte hinaus – nach abgelaufener befristeter Prüffreigabe oder nach dem Verschieben in eine fremde Gliederung mit Inventarnummer, Seriennummern, Begründung und der fremden Gliederung | niedrig–mittel | Bescheid nur, wenn der Antragsteller den Artikel heute liest (`rechte.darf_artikel("lesen", …)` – schließt Prüfrecht und befristete Prüffreigabe ein, wie seine Liste der Anträge); sonst gar keine Mail (Muster Mangelmeldung), nur eine Zeile im Log. Test `test_bescheid_nur_mit_recht` (mit Recht Mail, abgelaufen keine, verschoben keine, zurück wieder) |
     | 3 | Die Datenbanksperre ließ sich an der Schnittstelle vorbei umgehen: `INSERT OR REPLACE` eines geprüften Artikels, Produktwechsel → Metall → Nachtragen → zurück, `UPDATE mat_product.material_kind` – Widerspruch zum Satz „Wer die Datenbank direkt bearbeitet, kann damit nichts mehr ohne Antragsspur ändern“ | niedrig | **Schritt 16** (Schemaversion 16), Trigger: `mat_item_ersetzen` (BEFORE INSERT bei vorhandener Kennung, wie `mat_item_change_ersetzen`), `mat_item_kennung` (Kennung ändern), `mat_item_geprueft_loeschen` (geprüften Artikel löschen – ohne Fremdschlüssel ginge es sonst samt Neuanlage), `mat_item_produkt_fest` (anderes Produkt nach der ersten abgeschlossenen Prüfung; derselbe Wert geht, `artikel_aendern` schreibt jede Spalte neu), `mat_product_materialart_fest` (Materialart, sobald ein Artikel des Produkts geprüft ist; der Dienst sperrt schon ab dem ersten Artikel, „Die Materialart lässt sich nur ändern, solange es keine Artikel … gibt“), `mat_product_ersetzen`, `mat_product_kennung`. Vorher geprüft: Kein App-Weg ändert `product_id` nach einer Prüfung (`artikel_aendern` lehnt ab, sobald es eine Prüfung gibt; Bestandsimport und Anlegen legen nur neu an; „Variante“ legt ein neues Produkt an; ein Katalog-Zusammenführen gibt es nicht), keiner nutzt REPLACE/UPSERT auf `mat_item` oder `mat_product`, gelöscht werden nur ungeprüfte Artikel. CHANGELOG-Satz oben ehrlich abgeschwächt (`DROP TRIGGER` hilft immer). Tests `test_trigger_16` (mit und ohne Fremdschlüssel; App-Wege wie bisher), `test_migration_16` |
     | 4 | Ein Artikel fiel nach bestätigter Seriennummer still aus einem laufenden Rückruf – Antragskarte und Bestätigung sagten nichts | Hinweis | Antragsdialog: trifft ein laufender Rückruf mit Seriennummernliste den Artikel, steht dort „Artikel ist von Rückruf „…“ betroffen – nach einer Änderung der Seriennummer trifft der Rückruf ihn nicht mehr (außer die neue Nummer steht ebenfalls in seiner Liste).“ Karte und Rückfrage „Bestätigen“ nennen es genau (`antrag.rueckruf: {nicht_mehr, neu}` je offenem Seriennummern-Antrag, über `rueckruf.betrifft` mit alter und neuer Nummer): „… nach der Änderung trifft der Rückruf ihn nicht mehr.“ bzw. „Mit der neuen Seriennummer trifft ihn der laufende Rückruf „…“.“ Beim Bestätigen vermerkt das Journal `rueckruf_nicht_mehr` / `rueckruf_neu` („Rückruf trifft ihn nicht mehr / jetzt“, Titel mit Nr.). Ein Rückruf für alle Artikel des Produkts bleibt außen vor. Test `test_rueckruf_hinweis`, Oberfläche statisch `test_oberflaeche_pruefung` |
     | 5 | Bei Metall ergibt „Herstelldatum entfernen“ per Antrag und danach „direkt nachtragen“ eine beliebige Änderung, deren Zielwert niemand bestätigt hat | Hinweis | **Entschieden am 21.10.2026**: Direkt nachtragen nur, solange der Artikel noch nie ein Herstelldatum hatte; wurde eins per Antrag entfernt, geht ein neues nur wieder per Antrag. Dienst: `herstellung_nachtragbar` ist dann falsch (`bestand.herstellung_entfernt`: ein angewendeter Antrag auf das Herstelldatum mit vorhandenem altem Wert – nach der ersten Prüfung der einzige Weg, auf dem das Feld wieder leer wird), PUT → 409 „Das Herstelldatum dieses Artikels wurde per Antrag entfernt – ein neues trägst du nicht direkt nach, sondern beantragst es mit Begründung bei der Material-Verwaltung („Änderung beantragen …“).“, der Antrag auf einen neuen Wert geht (statt „trag direkt nach“). Oberfläche ohne Änderung: Der Dialog „Bearbeiten“ zeigt das Feld dann schreibgeschützt, der Antragsdialog lässt es zu. Datenbank: Schritt 16 ersetzt `mat_item_stammdaten_fest` (gleicher Name) – Nachtragen nur ohne einen solchen Antrag. Ein Herstelldatum, das schon **vor** der ersten Prüfung entfernt wurde, zählt nicht: Es stand in keinem Protokoll, die Felder waren bis dahin frei (**bestätigt am 21.10.2026**). Seit Schritt 17 lässt sich ein Herstelldatum nach der ersten Prüfung gar nicht mehr entfernen – die Regel gilt nur noch für Altfälle (siehe unten). Test `test_nachtragen_nach_entfernen` (409 mit Hinweis, Trigger, Antrag auf neuen Wert bestätigt; ein Artikel ohne je ein Herstelldatum bleibt nachtragbar) |
     | 6 | Sammelprotokoll und Einzelprotokoll derselben Prüfung widersprachen sich ohne Verweis (Einzelprotokoll alte, Sammelprotokoll neue Seriennummer) | Hinweis | Hat ein bestätigter Antrag die Seriennummer nach dem Festschreiben der Prüfung ersetzt, steht in der Zeile des Sammelprotokolls unter der Nummer „vormals AN-… (Änderungsantrag Nr. …)“ (`protokoll._vormals`; „danach“ über die Reihenfolge der Journaleinträge, genauer als Zeitstempel in Sekunden). Nur neue Sammelprotokolle – festgeschriebene bleiben Byte für Byte, wie sie sind. PDF/A-3b mit veraPDF (`bin/st-vera`) geprüft: PASS. Test `test_sammelprotokoll_vormals` (Änderung vor der Prüfung im Durchgang: kein Vermerk; festgeschriebenes Sammelprotokoll unverändert) |

     **Migration Schritt 16**: beim Start von selbst, rein additiv und wiederholbar (nur Trigger; `mat_item_stammdaten_fest`
     wird entfernt und in der engeren Fassung neu angelegt). Geprüft: frische Datenbank, 15 → 16 (neue Trigger entfernt,
     Artikeltrigger in der Fassung aus 15: Zahlen aller Tabellen gleich, Trigger da und ersetzt), 7 → 16 an einer **Kopie**
     des Stands 7 (Zahlen wie 7 → 15, Löschen, Umnummerieren und Produktwechsel eines geprüften Artikels der Kopie
     abgewiesen), zweiter Lauf ohne Änderung. **Rückweg**: Eine Fassung mit Schemaversion 15 übergeht Schritt 16; die
     Trigger blieben wirksam – sie sperren nur, was keine Fassung über die Oberfläche tut; einzig das Nachtragen nach einem
     Entfernen per Antrag käme dort als 409 „Bitte neu laden“ an. Keine Handarbeit beim Update.
     **Schnittstelle**: je Antrag neu `rueckruf` (`{nicht_mehr, neu}` mit `id`, `title`; nur offen, sonst `null`); für
     Leser fehlen in den Journaleinträgen der Anträge `begruendung`, `beantragt_von`, `anmerkung`, `ablehnung`, Handelnder
     „(Person)“; Journal der Bestätigung ggf. mit `rueckruf_nicht_mehr`, `rueckruf_neu`.
   - **Entscheidungen vom 21.10.2026 zur Prüfung** (zu „Bitte bestätigen“ oben und zu Befund 5):
     - **Bestätigt am 21.10.2026**: Ein Herstelldatum, das **vor** der ersten Prüfung entfernt wurde, sperrt späteres
       direktes Nachtragen nicht; die Material-Verwaltung darf ihren eigenen Antrag selbst bestätigen; Antragsteller
       und Entscheider behalten beim Kontolöschen ihren Namen; Prüfer (auch externe mit befristeter Prüffreigabe) dürfen
       beantragen.
     - **Geändert 1 – Zurückziehen**: Einen **offenen** Antrag zieht der **Antragsteller selbst** zurück
       (`antrag.zurueckziehen`, `POST /api/material/antraege/<id>/zurueckziehen`). Nur den eigenen und nur, solange er
       den Artikel liest – sonst 404 wie unbekannt (auch für die Material-Verwaltung, wenn es nicht ihr eigener ist);
       schon entschieden oder zurückgezogen 409. Neuer Stand **„zurückgezogen“** – ein Endzustand wie bestätigt und
       abgelehnt, mit dem Antragsteller als Handelndem (`resolved_by`, `resolved_by_name`, `resolved_at`), ohne
       Antwort. Journal am Artikel „Änderungsantrag zurückgezogen“ (`antrag`, `feld`; für Leser ohne Namen wie die
       übrigen Antragseinträge), auch im Lebenslauf. **Keine Mail** – die Material-Verwaltung braucht keinen Bescheid
       (einfachste Lösung): Der offene Zähler (Blase, Übersicht, „offen (n)“) sinkt, unter „erledigt“ steht der Antrag
       als „zurückgezogen“. Danach lässt sich fürs Feld neu beantragen. Oberfläche: Am Artikel (Stammdaten bzw. Dialog
       „Bearbeiten“) trägt der Hinweis „… Änderung beantragt am … – wartet auf die Material-Verwaltung.“ beim **eigenen**
       Antrag den grauen Knopf **„Antrag zurückziehen …“**; die Rückfrage („Deinen Antrag „Seriennummer: alt → neu“
       zurückziehen? Die Material-Verwaltung entscheidet dann nicht mehr darüber; neu beantragen kannst du jederzeit.“)
       hat als einzigen roten Knopf „Zurückziehen“ (`btn danger` – endgültig), danach schließt der Dialog „Bearbeiten“.
       In „Meldungen“ → „Änderungsanträge“ trägt die eigene offene Karte grau „Zurückziehen …“ (neben „Bestätigen …“
       und „Ablehnen …“ bei der Material-Verwaltung), erledigte zeigen die graue Marke „zurückgezogen“ und „Vom
       Antragsteller zurückgezogen am …“.
     - **Geändert 2 – Herstelldatum nicht entfernbar**: Nach der ersten Prüfung lässt sich das Herstelldatum **nicht
       entfernen, auch nicht per Antrag** – nur auf Antrag ändern (neuer Wert). Die Option „Herstelldatum entfernen
       (unbekannt)“ im Antragsdialog ist weg (Hilfe: „bisher 11/2023 – nur ändern, nicht entfernen“); der Dienst weist
       `herstellung_entfernen` mit 400 ab („Das Herstelldatum lässt sich nicht entfernen – nur auf Antrag ändern (neues
       Datum angeben).“), ein leeres Feld heißt wie bisher „keine Änderung beantragt“. Ein offener Antrag aufs Entfernen
       aus der Zeit davor lässt sich **nicht mehr bestätigen** (409 „… diesen älteren Antrag kannst du nur noch
       ablehnen.“, `antrag.entfernen` = true, die Karte zeigt nur „Ablehnen …“ und den Hinweis „Ein Herstelldatum lässt
       sich nicht mehr entfernen – der Antrag lässt sich nur noch ablehnen.“); der Antragsteller kann ihn zurückziehen. Diese
       Altanträge bleiben offen, bis jemand sie ablehnt oder zurückzieht – kein automatisches Schließen (**bestätigt am
       21.10.2026**).
       **Altfälle**: Die Regel aus Befund 5 („Nachtragen nach Entfernen nur per Antrag“, `bestand.herstellung_entfernt`,
       Trigger `_NACHTRAGEN_16`) bleibt unverändert – für neue Fälle gegenstandslos (es entsteht keiner mehr), für einen
       auf dev womöglich schon per Antrag entfernten Fall weiter wirksam. Begründung: Sie zu streichen hieße, an genau
       diesen Artikeln ein beliebiges Datum ohne Bestätigung eintragen zu lassen – die Lücke aus Befund 5; sie zu
       behalten kostet nichts. **Bestätigt am 21.10.2026.**
       **Vom Nutzer am 22.10.2026 auf dev geprüft und bestätigt**: Antrag gestellt und wieder zurückgezogen; im
       Antragsdialog gibt es keine Option „Herstelldatum entfernen“ mehr.
     - **Datenbank (Schritt 17, Schemaversion 17)**: `mat_item_change` wird umgebaut (`_umbauen`: alle Zeilen und
       Kennungen bleiben, der AUTOINCREMENT-Stand ebenso, Indizes neu angelegt) – der CHECK kennt den Stand
       „zurückgezogen“ (Schritt 15 bleibt mit `ANTRAGSSTATUS_15`, wie er ausgeliefert wurde). Neue Trigger
       (`TRIGGER_17`): `mat_item_change_zurueckziehen` (zurückziehen nur mit der Kennung des Antragstellers und ohne
       Antwort; danach fest wie entschieden – `mat_item_change_entschieden`), `mat_item_change_herstellung_leer` (kein
       Antrag mit leerem neuem Herstelldatum), `mat_item_change_entfernen_bestaetigen` (ein alter Antrag aufs Entfernen
       lässt sich nicht bestätigen). `mat_item_stammdaten_fest` wird ersetzt (gleicher Name): Nach der ersten Prüfung
       wird das Herstelldatum nie mehr leer – nachtragen (Metall) und ein bestätigter Antrag gehen nur auf einen Wert.
       Die Trigger aus Schritt 15 an der Tabelle und `mat_item_antrag_angewendet` werden nach dem Umbau neu angelegt
       (unverändert). Umgebaut wird nur, wenn der CHECK „zurückgezogen“ noch nicht kennt – ein zweiter Lauf ändert
       nichts. **Geprüft**: frische Datenbank; 16 → 17 an einem Stand 16 **mit Anträgen** (per Antrag entferntes
       Herstelldatum, offener Antrag aufs Entfernen, offener Antrag auf eine Herstellernummer – Test
       `test_migration_17`: alle Zeilen gleich, `sqlite_sequence` gleich, Zahlen aller Tabellen gleich, Trigger = Stand 16
       + die drei neuen, danach bestätigt bzw. abgewiesen wie beschrieben); 7 → 17 an einer **Kopie** des Stands 7
       (Zahlen wie 7 → 16, Tabelle leer und umgebaut, ein geprüftes Herstelldatum der Kopie lässt sich nicht leeren);
       zweiter Lauf ohne Änderung. **Rückweg**: Eine Fassung mit Schemaversion 16 übergeht Schritt 17; die Tabelle mit
       dem weiteren Stand und die Trigger blieben – dort ließe sich ein Herstelldatum dann auch per Antrag nicht mehr
       entfernen (der Trigger lehnt ab, die ältere Fassung meldete einen Fehler), sonst arbeitet sie wie bisher. Keine
       Handarbeit beim Update.
     - **Schnittstelle**: neu `POST /api/material/antraege/<id>/zurueckziehen` (Modulzugang; nur der Antragsteller);
       Stand `zurueckgezogen` (`status_text` „zurückgezogen“, Filter `erledigt` schließt ihn ein); je Antrag `entfernen`
       (true bei einem alten Antrag aufs Entfernen); `POST /api/material/artikel/<id>/antrag` ohne
       `herstellung_entfernen` (→ 400); Journal-Aktion `antrag_zurueckgezogen`.
     - **Tests** (`tests/test_material_antrag.py`, Abschnitt 11): `test_zurueckziehen` (nur der eigene, fremd 404 auch
       für die Material-Verwaltung, ohne Leserecht 404, zweimal 409, danach weder bestätigen noch ablehnen, keine Mail,
       Journal und Lebenslauf, Leser ohne Namen, Zähler sinkt, „erledigt“, neu beantragen; Trigger nur für den
       Antragsteller), `test_herstellung_nicht_entfernen` (Metall und textil 400, Bearbeiten weist Leeren ab, ändern per
       Antrag geht, vor der ersten Prüfung entfernen und danach nachtragen geht), `test_migration_17`,
       `test_oberflaeche_17` (statisch). Angepasst: `test_eingaben`, `test_trigger` (Entfernen per Antrag jetzt
       abgewiesen), `test_nachtragen_nach_entfernen` (jetzt an einem Stand 16 mit Altfall, danach 16 → 17),
       `test_migration_15`/`_16` (Schritt 17 bzw. Stand 16 ausdrücklich), `test_oberflaeche_statisch`;
       `test_material_stammdaten` (Kopie-Pfad 7 → Endversion: die Artikeltrigger aus Schritt 16 gehören seit dort dazu –
       schlug mit gesetzter Kopie schon seit Schritt 16 fehl), `test_material_ueberblick` (die neue Route antwortet der
       Führungskraft 404 – kein eigener Antrag –, nichts geändert).
     - **Im Browser geprüft** (Platzhalterbestand, kein Mailserver) bei 1280 und 360 px: Prüfer zieht am Karabiner
       seinen Antrag über „Antrag zurückziehen …“ zurück (Rückfrage, Hinweis weg, Journal „Änderungsantrag
       zurückgezogen“); Materialwart bricht die Rückfrage im Dialog „Bearbeiten“ ab (Dialog bleibt) und zieht dann
       zurück (Dialog schließt); Antragsdialog ohne „entfernen“; Prüfer zieht in „Deine Änderungsanträge“ über die Karte
       zurück; die Material-Verwaltung sieht den alten Antrag aufs Entfernen nur mit „Ablehnen …“, zieht ihren eigenen
       zurück, „erledigt“ zeigt die grauen Marken „zurückgezogen“. Keine Konsolenfehler, kein waagerechtes Scrollen, je
       Dialog höchstens ein roter Knopf.

## Artikellänge und Prüfpunkt „Länge“ (Schritt 20, 22.10.2026)

Wunsch des Nutzers vom 22.10.2026: „Beim Anlegen von Seilen/Meterwaren soll im Artikel die tatsächliche Länge hinterlegt
werden können. Diese Länge soll beim Prüfen dann als Prüfpunkt abgefragt werden und ggf. korrigiert werden können.“
Gebaut nach seinen drei Entscheidungen (unten), Schemaversion 20, keine neuen Abhängigkeiten. Stand: nach der
unabhängigen Prüfung nachgebessert (siehe „Prüfung vor Auslieferung“), wartet auf Freigabe.

### Neu

- **Häkchen „Artikel haben eine Länge“ an der Kategorie** (Dialog „Kategorie anlegen/bearbeiten“, nur Katalogpflege;
  `mat_category.items_have_length`): Es gilt für die Kategorie und alle Unterkategorien (`katalog.laenge_wirksam`,
  einmal je Anfrage berechnet); die Katalogansicht nennt es in der Angabenzeile, der Dialog einer Unterkategorie sagt
  „hier schon durch eine Oberkategorie gesetzt“. Jede Kategorie trägt `items_have_length` und `laenge_wirksam`, jedes
  Produkt `laenge_moeglich`. Im Journal der Kategorie als „Artikel haben eine Länge: ja/nein“.
- **Länge am Artikel** (`mat_item.length_m`, REAL, CHECK 0 < x < 10 000; Feld „Länge (m)“ in „Artikel anlegen“ und im
  Dialog „Bearbeiten“, nur wenn die Kategorie des Produkts sie vorsieht): Eingabe „57,5“ oder „57.5“, gerundet auf eine
  Nachkommastelle, Grenzen 0,1 bis 9999,9 m (`services.laenge`, `dezimal`); Anzeige „57,5 m“ (`laenge_text`) im
  Steckbrief (Zeile „Länge“, sobald die Kategorie sie vorsieht oder der Artikel eine trägt), grau hinter dem Produkt
  in Artikellisten (ohne Umbau der Tabelle), im Lebenslauf-PDF und Prüfprotokoll (Artikelblock), in „Meine PSA“
  (`length_m`, `laenge_text`), als CSV-Spalte **„Länge (m)“** hinter „Lebensende“ („57,5“, deutsches Komma, ohne Einheit)
  und im Bestandsimport als Spalte „Länge“ (Synonyme „Länge (m)“, „Seillänge“, „length“; Feld `laenge`, auch in der
  Nacharbeits-CSV; „Länge“ ist kein Bemerkungstitel mehr). Ein Wert bei einer Kategorie ohne Länge oder ein unlesbarer
  Wert blockiert den Import nicht: Hinweis an der Zeile, der Wert steht als „Länge laut Liste: …“ in der Bemerkung.
  Server: Länge bei einer Kategorie ohne Länge → **409** mit Klartext (`katalog.KEINE_LAENGE`); eine vorhandene Länge
  bleibt nach dem Entfernen des Häkchens lesbar und unverändert speicherbar, nur ein anderer Wert ist 409, leeren geht.
  Die Länge gehört **nicht** zu den festen Stammdaten (kein Änderungsantrag, auch nach der ersten Prüfung direkt
  änderbar); Journal „geändert“ mit `length_m` (Beschriftung „Länge (m)“, Wert „57,5 m“).
- **Prüfpunkt-Typ „Länge (m)“** (`EDITOREN["laenge"]`, Formular-Editor: Art wählbar, Soll „Artikellänge“ nicht
  editierbar, nie kritisch): In der Prüfung ist der Punkt mit der Artikellänge vorbelegt (Soll und Wert „57,5“, leer
  ohne Länge – dann Pflicht wie jeder Pflichtpunkt oder „n. z.“), die Kopfzeile sagt „am Artikel 57,5 m“. Eingabe
  wie am Artikel, gespeichert als „55,0“ (`pruefung.punkt_setzen`). Beim **Festschreiben** (`abschliessen`, auch einer
  Berichtigung) übernimmt `_laenge_uebernehmen` einen abweichenden Wert in den Artikel – vor dem Abschluss, solange die
  Ergebniszeile ihr Soll noch annimmt: Hat jemand die Länge seit dem Beginn der Prüfung geändert, bricht das
  Festschreiben mit **409** ab („Die Länge am Artikel wurde während der Prüfung auf 60,0 m geändert – bitte den
  Messwert bestätigen“), der Punkt bekommt die neue Länge als Soll (und als Wert, wenn der Prüfer ihn nicht angefasst
  hat) und die Prüfung lädt neu; eine Berichtigung behält das Soll ihres Originals (die Länge vor der berichtigten
  Prüfung) und übernimmt den Messwert nur, wenn sie ihn gegenüber dem Original ändert. Dann `mat_item.length_m` und
  ein eigener Journaleintrag
  **„laenge_geaendert“** (`length_m` vorher/nachher, `pruefung`, `art`). Unverändert → kein Journal. Im Protokoll-PDF
  steht in „Wert / Bemerkung“ „57,5 m → 55,0 m“ bzw. „55,0 m (unverändert)“, in der Lese-Ansicht „55,0 m (vorher 57,5 m)“.
  Festgeschriebene Ergebniszeilen bleiben unveränderlich (Trigger aus Schritt 6 unberührt).
- **Artikel ohne vorgesehene Länge** (Kategorie ohne Häkchen, Formular mit Längenpunkt – etwa ein generisches
  Formular einer Oberkategorie, deren Seile das Häkchen tragen, ihre Karabiner nicht): Der Punkt wird angezeigt, steht
  aber „nicht zutreffend“ mit dem Hinweis, dass für diese Kategorie keine Länge vorgesehen ist; nur der Knopf „n. z.“
  steht da, ein Wert und die Befunde „in Ordnung“/„Mangel“ sind 409; das Festschreiben setzt den Punkt vor allen
  Pflicht-, Mangel- und Grundprüfungen auf „nicht zutreffend“ (ein vorher gemessener Wert steht dann in der Bemerkung
  des Punkts) und ändert nichts am Artikel. **Entwurfsentscheidung**: Ausblenden hieße, dass das Formular je Artikel
  anders aussieht und die Nummerierung im Protokoll springt; „nicht zutreffend“ ist der Befund, den das Modul für
  genau diesen Fall schon kennt, und steht so auch im Protokoll.

### Migration (Schritt 20, `models._schritt_20`)

`ALTER TABLE mat_category ADD COLUMN items_have_length INTEGER NOT NULL DEFAULT 0 CHECK (… IN (0, 1))`,
`ALTER TABLE mat_item ADD COLUMN length_m REAL CHECK (… IS NULL OR (… > 0 AND … < 10000))` – jeweils nur, wenn die
Spalte fehlt. `mat_checklist_item` trägt einen CHECK über die Prüfpunktarten; SQLite ändert ihn nur mit einer neuen
Tabelle, deshalb wird sie wie `mat_item_change` in Schritt 17 einmal neu aufgebaut (`_umbauen_checklist`: alle Zeilen
und Kennungen bleiben, Index neu, kein AUTOINCREMENT – `mat_inspection_result.checklist_item_id` zeigt weiter hin) –
nur, wenn der CHECK „laenge“ noch nicht kennt. Schritt 1 bleibt mit `EDITOREN_1`, wie er ausgeliefert wurde.
Wiederholbar; zweiter Lauf ohne Änderung. Geprüft frisch, 19 → 20 an einem Datenordner mit Bestand (Tabellen, Indizes
und Trigger danach genau wie frisch), Schritt 20 für sich. Wer `mat_checklist_item` künftig neu aufbaut, legt den Index
neu an.

### Entscheidungen des Nutzers (22.10.2026)

1. Sichtbarkeit über das Kategorie-Häkchen „Artikel haben eine Länge“, vererbt auf Unterkategorien; nur dort zeigt der
   Artikel das Feld.
2. Neuer Prüfpunkt-Typ „Länge“ im Formular-Editor; in der Prüfung mit der Artikellänge vorbelegt; ein abweichender Wert
   geht beim Festschreiben in den Artikel (Journal „Länge geändert“, Protokoll „alt → neu“).
3. Einheit Meter mit einer Nachkommastelle, Eingabe mit Komma oder Punkt, Anzeige „57,5 m“ – in Steckbrief, Listen,
   CSV-Export und Bestandsimport (Spalte „Länge“).

### Abweichungen und eigene Entscheidungen

- CSV-Spalte „Länge (m)“ steht hinter „Lebensende“ (nicht hinter „Bemerkung (Produkt)“ und nicht am Ende): Die Länge
  ist eine Artikelangabe und gehört zu den Artikeldaten in der Reihenfolge des Steckbriefs (hergestellt, gekauft,
  Erstgebrauch, Lebensende, Länge, Bemerkung); der Bestandsimport liest Spalten am Titel, nicht an der Stelle, und
  die bestehenden Tests prüfen nur „Bemerkung (Produkt)“ direkt hinter „Modell“. **Alle Spalten ab „Bemerkung“ rücken
  damit eine Stelle nach hinten** – wer Excel-Auswertungen nach Spaltenbuchstaben gebaut hat, zieht sie nach.
- Zwei Journalaktionen: „geändert“ (Bearbeiten-Dialog, wie jedes andere Artikelfeld) und „laenge_geaendert“
  (Festschreiben einer Prüfung, mit Verweis auf die Prüfung) – so bleibt im Lebenslauf sichtbar, ob ein Prüfer oder
  der Materialwart die Länge gesetzt hat.
- Der Wert eines Längenpunkts wird normalisiert gespeichert („55,0“), nicht roh wie bei Zahlpunkten – Protokoll und
  Vergleich mit der Artikellänge brauchen eine feste Form.
- `docs/material-katalog-vorlage.json`: „Statikseile“ trägt `"artikel_laenge": true` (Format 1 liest den Schlüssel
  ebenso).

### Schnittstelle

Siehe die Tabelle unten: `GET/POST /api/material/kategorien` (`items_have_length`, `laenge_wirksam`),
`POST/PUT /api/material/artikel` (`length_m`, `laenge_text`, `laenge_moeglich`, 409), `GET /api/material/pruefungen/<id>`
(`laenge`), `PUT …/punkte/<pid>` (Art `laenge`), `GET /material/export/<ordner>.csv` („Länge (m)“), Bestandsimport
(Feld `laenge`), Katalogdatei (`artikel_laenge`, `punkte[].art` = `laenge`), `GET /api/material/meine-psa` (`length_m`,
`laenge_text`).

### Geprüft

`tests/test_material_laenge.py` (Migration 19 → 20 und bis Schritt 19, Häkchen mit Vererbung, Format 2 Export/Import,
Artikel mit Länge samt Rundung, Grenzen, 409, Journal, CSV-Spalte, Bestandsimport-Spalte, Formular-Editor, Prüfung
vorbelegt, Festschreiben übernimmt, unverändert ohne Journal, Berichtigung, Artikel ohne vorgesehene Länge, Trigger,
Lebenslauf, Meine PSA, Trennung); `test_material_mailprotokoll.test_migration_19` auf Schemaversion 20 angepasst;
`test_material_trennung.bis_schritt` rüstet auf älteren Ständen nur die beiden neuen Spalten nach (sonst ließe sich dort
über den Dienst keine Kategorie und kein Artikel mehr anlegen; Schemaversion und CHECK bleiben alt, `nachruesten=False`
für den Migrationstest); feste Listen in `test_material_import` (Kopf der Nacharbeits-CSV) und
`test_material_meine_psa` (Schlüssel der Karte) um die Länge ergänzt; ganze
Suite, Lint (st-py, st-js, st-css), Browserprobe 1280 und 360 px (Artikel anlegen mit Länge, Prüfung mit Längenpunkt).

### Prüfung vor Auslieferung

Unabhängige Prüfung von Commit 80e02f0 (Bericht `planung/material-phase4/pruefung_laenge.md`, Proben unter
`probe-laenge/`, außerhalb des Repositorys) mit der Brille Sicherheit, Rechte, Migration, Robustheit und Ablauf:
**0 hoch, 3 mittel, 2 niedrig, 8 Verbesserungen**; Migration 19 → 20 an fünf Kopien, CHECKs, Rechte, Trennung,
Rollback, PDF/A ohne Befund. Alle fünf Befunde sind behoben, jeweils mit Test in `tests/test_material_laenge.py`
(`test_nachbesserung_pruefung`, `test_import_einheiten`, `test_katalogformat`):

| Nr. | Befund / Verbesserung | Schwere | Umgang |
| --- | --- | --- | --- |
| B1 | Eine veraltete Vorbelegung überschrieb eine während der Prüfung eingetragene Länge (Materialwart 60,0, Prüfer lässt 57,5 stehen → Artikel wieder 57,5, Protokoll „60,0 m → 57,5 m“) | mittel | Vor dem Festschreiben (eigene kurze Transaktion, `_laenge_vormerken`): weicht die Artikellänge vom Soll der Vorbelegung ab und der Messwert von ihr, bekommt der Punkt die neue Länge als Soll (als Wert nur, wenn der Prüfer ihn nicht angefasst hat) und das Festschreiben bricht mit 409 ab; die Oberfläche lädt die Prüfung neu, der Prüfer bestätigt. Im Abschluss selbst noch einmal geprüft (Wettlauf: 409). Berichtigungen: siehe B3 |
| B2 | `NaN` per JSON galt als gültige Länge, das unveränderliche Journal bekam `{"length_m": NaN}` – jede Antwort mit diesem Eintrag war kein gültiges JSON mehr, die Artikelseite lud nicht | mittel | `dezimal` weist NaN und Unendlich ab (400, auch „1e309“), nur ASCII-Ziffern (V2); `journal.eintragen` schreibt mit `allow_nan=False` (Ausnahme statt eines ungültigen Eintrags, für alle Dienste) |
| B3 | Das Protokoll einer Berichtigung verglich mit der Länge nach dem Original: Tippfehler 57,5 → 5,0 berichtigt auf 57,5 ergab „5,0 m → 57,5 m“, eine echte Kürzung verschwand als „50,0 m (unverändert)“ | mittel | Die Berichtigung behält das Soll des Originals (Länge vor der berichtigten Prüfung) für „alt → neu“; in den Artikel geht ihr Messwert nur, wenn er sich gegenüber dem Original ändert, abgeglichen mit der aktuellen Länge (Journal). Tests: „57,5 m (unverändert)“ und Artikel 57,5; „57,5 m → 50,0 m“ und Artikel 50,0 |
| B4 | Ohne vorgesehene Länge nahm der Punkt „in Ordnung“ (Sackgasse bei Pflicht) und „Mangel“ an (zählte als Mangel, „instandsetzen“ ohne Grund, dann still „n. z.“) | niedrig | Nur „nicht zutreffend“ (ok/Mangel → 409 mit Klartext), die Oberfläche zeigt nur „n. z.“; das Zurücksetzen läuft vor den Pflicht-, Mangel- und Grundprüfungen |
| B5 | Bestandsimport las „Länge (cm)“ = 3000 als 3000,0 m und „1.200“ still als 1,2 m | niedrig | Einheit aus dem Spaltentitel (cm, mm, dm, km, ft/Fuß, in/Zoll, yd – „(cm)“, „[mm]“, „in ft“) oder am Wert: nur Meter wird gelesen, sonst Hinweis „Länge laut Liste „3000 cm“ in cm – bitte in Metern angeben“ und der Wert in der Bemerkung; „1.200“ ist mehrdeutig (Hinweis, Bemerkung). Wie ein unlesbarer Wert blockiert das die Zeile nicht |
| V1 | JSON-Zahl 0 am Längenpunkt galt als „leer“ | – | 0 ist 0 (400), auch am Zahlpunkt |
| V2 | Unicode-Ziffern („０５７“) wurden 57,0 m | – | nur ASCII-Ziffern |
| V3 | Zwei Längenpunkte in einem Formular – der letzte gewann still | – | höchstens einer je Formular (400) |
| V4 | Produktwechsel auf ein Produkt ohne Länge behielt die Länge | – | sie fällt weg (Journal „geändert“ nennt den alten Wert) |
| V5 | Häkchen weg während eines Entwurfs: gemessener Wert verfiel still | – | steht in der Bemerkung des Punkts („Gemessen: 12,0 m – …“) |
| V6 | „50 m“, „50m“ im Bestandsimport unlesbar | – | als Meter gelesen |
| V7 | Kategorie-Dialog: Hinweis „durch eine Oberkategorie gesetzt“ folgt nicht einer im Dialog geänderten Oberkategorie | – | nicht geändert (Zu prüfen) |
| V8 | Katalogdatei: `"artikel_laenge": null` nahm das Häkchen weg | – | null gilt wie ein fehlender Schlüssel (unverändert) |

### Zu prüfen / Bitte bestätigen

- Stelle der CSV-Spalte (siehe Abweichungen; Spalten ab „Bemerkung“ eine Stelle weiter) – die Prüfung empfiehlt, sie
  zu bestätigen.
- „nicht zutreffend“ für Artikel ohne vorgesehene Länge in einem Formular mit Längenpunkt (siehe Neu) – jetzt
  zusammen mit B4: der Punkt nimmt nur noch „n. z.“ an.
- Nachkommastelle: „57,56“ wird still „57,6“ – kein Fehler, da die Entscheidung eine Nachkommastelle vorgibt (im
  Bestandsimport werden fremde Einheiten und „1.200“ nicht mehr still gelesen).
- **Neu: 409 bei geänderter Länge während der Prüfung** – der Prüfer muss nach dem Neuladen noch einmal
  festschreiben; eine Berichtigung prüft das nicht (sie übernimmt nur einen gegenüber dem Original geänderten
  Messwert). Bitte bestätigen.
- V7 (Kategorie-Dialog mit geerbtem Häkchen als gesperrtes Kästchen) ist nicht umgesetzt – Oberfläche, eigener
  Schritt, falls gewünscht.

## Phase 4 · Lieferung 1 – Auswertung und Betriebsreife (22.10.2026)

Lieferung 1 der Phase 4 bringt den **Jahresbericht je Zweig** (Seite, PDF, CSV-Prüfungsliste – Entwurf
`planung/material-phase4/entwurf_l1.md`, Fassung 2 nach den Kritiken „Ablauf“ und „Sicherheit“, mit den Entscheidungen
des Nutzers vom 22.10.2026, Abschnitt F), das **Mailfehler-Protokoll** mit dem Kasten „Mailversand“ auf der Übersicht
und zwei Nachbesserungen außerhalb des Entwurfskerns: **C1** Wiki und Nutzerverwaltung am Finger, **C2** Datumsfelder
als deutsche Textfelder. Gebaut in drei Paketen – KERN K1 (Bericht), KERN K2 (Schema 19, Versand-Wrapper, Routen) und
OBERFLÄCHE (`material.js`, CSS, C1, C2, Doku). Schemaversion 19, keine neuen Abhängigkeiten. Stand: nach drei
unabhängigen Prüfungen (Sicherheit, Ablauf, Browser) nachgebessert – siehe „Prüfung vor Auslieferung“; wartet auf die
Freigabe.

### Neu

- **Jahresbericht je Zweig** (`services/bericht.py`, `routes_bericht.py`, Vorlage `pdf/bericht.html`, Ansicht
  `bericht` in `material.js`): für einen Ordnerzweig – in der Regel die Gliederung – und ein Kalenderjahr. Einstieg im
  Ordnerkopf über das Untermenü „Export“ → „Jahresbericht“ (nur mit Grundrecht, nicht an Systemordnern). Die Seite
  `/material/ordner/<fid>/bericht` hat Jahr-Auswahl (frühestes Jahr aus Anlage oder Prüfung bis heute, höchstens 15),
  Haken „Prüfer nennen“ und die grauen Knöpfe „PDF“ und „Prüfungen (CSV)“; Auswahl und Haken stehen in der Adresse
  (`?jahr=&pruefer=1`). Blöcke in der Reihenfolge des Entwurfs (A4): Kopf (Zweig, Gliederung, Stichtag, Ersteller,
  Empfänger „Gliederung intern“, Artikel in der Sicht, DEMO-Zahl), Bestand zum Stichtag (Statuszeilen genau nach
  `status.STATUS`, verloren gemeldet, je Kategorie der obersten Ebene, je Unterordner nach Heimat), Bewegungen,
  Prüfungen (je Art, je Ergebnis, mit Mangel, mit kritischem Mangel, offene Entwürfe) mit Prüfabdeckung und der Liste
  der nicht geprüften Artikel, Prüfdurchgänge mit Ausnahmen, Prüfer (nur mit Haken: je Name und Urkundennummer, dazu
  „Aussonderungen durch“), Sperren und Freigaben (aus dem Journal: nur der Übergang frei → gesperrt/verloren),
  Aussonderungen mit Grundart, Mangelmeldungen (über `mangel.stand`, auch „wieder offen“), Rückrufe mit betroffenen
  Artikeln im Zweig, Ausblick über zwölf Monate (fällig je Monat, Lebensende textil), Fußsätze. Jede Zelle über
  `esc()`, keine DOM-ids aus Daten, Rückruf-URL nur als Text; am Telefon Karten (Containerabfrage `mat-seite`), die
  Zahlentabellen wie im PDF, zwei nebeneinander ab 700 px Inhaltsbreite. Unter dem Kopf Sprungmarken zu den Blöcken.
  Die Seite zeigt Listen ganz – „Im Jahr nicht geprüft“ ab 26 Zeilen zugeklappt, die betroffenen Artikel eines
  Rückrufs aufklappbar (offene zuerst); das PDF kürzt jede Liste auf 500 Zeilen, alle zusammen auf 1 500 und je Rückruf
  auf 50 Artikel (Hinweis auf der Seite, sobald eine Liste länger als 500 ist). 400 (Jahr außerhalb 1990…2100), 403
  und 404 kommen als Meldung, die Jahr-Auswahl bleibt bedienbar – auch beim ersten Laden. Der Tab-Titel nennt Zweig
  und Jahr.
- **PDF** `GET /material/ordner/<fid>/bericht-<jahr>.pdf` (mit Haken `…-mit-pruefern.pdf`): PDF/A-3b wie die
  Protokolle, nicht festgeschrieben (kein Stempel, keine Unterschrift, keine Protokoll-ID), Titel „Jahresbericht
  Material <Zweig> <Jahr>“ (mit „[DEMO] “, sobald DEMO-Artikel enthalten sind), Fuß „… · kein Prüfnachweis“, Dateiname
  `Jahresbericht_<Ordner>_<Jahr>[-mit-pruefern].pdf` mit Präfix `DEMO-`. **CSV**
  `GET /material/export/<fid>-pruefungen-<jahr>.csv` (`…-mit-pruefern.csv`): eine Zeile je Prüfung und Aussonderung des
  Jahres, berichtigte Originale ausgeschlossen, Spalten nach `export.VERZEICHNIS_SPALTEN` plus Art, Prüfdurchgang,
  Protokoll-ID, Berichtigung von, Mängel, kritischer Mangel, Prüfer und Urkundennummer (nur mit Haken), DEMO;
  Formelschutz, „;“, CRLF, BOM, ohne Kappung.
- **Rechte** – eine Funktion `bericht_zugang` für Seite, JSON, PDF und CSV in der Reihenfolge des Exports: 401 →
  403 ohne Modulzugang → 404 nicht sichtbar, unbekannt oder Systemordner → 403 ohne Grundrecht (externer Prüfer).
  Führungskraft (lesen) und Materialwart (verwalten) bekommen ihn, die Material-Verwaltung über ihre Allsicht. Eine
  Sichtberechnung je Anfrage; INFO-Logzeile „Bericht Ordner <fid> Jahr <jahr> Konto <id> pruefer=<0/1>“ ohne Namen,
  keine Journalzeile; alle Antworten `no-store`.
- **Personen**: Ohne den Haken enthält keine Ausgabe einen Personennamen oder eine Urkundennummer außer dem Ersteller –
  keine Melder, keine Durchgangs-Eröffner, keine Aussonderer, keine Zuordnungen. Mit Haken Prüferliste, „durch“ bei
  Aussonderungen, Prüfer-Spalten in der CSV und der Dateiname „-mit-pruefern“.
- **Mailfehler-Protokoll** (`services/mailprotokoll.py`, Tabelle `mat_mail_fehler`, Schritt 19): Jede Modul-Mail –
  Erinnerung, Mangel, Änderungsantrag, Produktmeldung, Rückruf – geht über `senden()`; nimmt der Mailserver sie nicht an,
  entsteht eine Zeile mit Art, Klasse (Empfänger abgewiesen, Verbindung, Anmeldung, abgelehnt, Ausnahme, sonstiges),
  Bezug, Ordner, Kontoverweis, Rolle, Betreff (160 Zeichen) und der gereinigten Serverantwort (300 Zeichen); Betreff
  und Antwort ohne Adressen, ohne Mailserver und ohne den Anmeldenamen des Mailservers – Platzhalter „[Adresse]“,
  „[Mailserver]“, „[Anmeldename]“; die CHECKs `instr(meldung,'@') = 0` und `instr(betreff,'@') = 0` sind das Netz. Erfolge werden nicht protokolliert. Stille einheitlich im Wrapper: kein Mailserver, Umgebungssperre (dev),
  DEMO-Artikel oder DEMO-Adresse → kein Versand, keine Zeile, nur eine Logzeile (Entscheidung Nr. 6 – gilt damit neu
  auch für Rückruf- und Produktmeldungs-Mails). Einzelmails (Mangel, Änderungsantrag, Produktmeldung) tragen als Ordner
  die Heimat des Artikels bzw. den Ordner der Meldung, Sammelmails (Erinnerung, Rückruf) bekommen je betroffener
  Gliederung eine Zeile (Nr. 5).
  Gelingt später eine Erinnerung an dasselbe Konto, schließt sie dessen offene Erinnerungs-Fehler („nachgeholt“).
- **Kasten „Mailversand“** auf der Übersicht unter dem Laufstand (`mailKasten` in `material.js`; Block `mailfehler`
  aus `/api/material/start`, `null` heißt kein Kasten): Material- und Plattform-Verwaltung sehen alles, wer verwaltet,
  die Zeilen der Ordner, die er verwaltet (nach unten vererbt – auch, wer nur einen Unterordner verwaltet, sieht den
  Fehlschlag seiner Mangel-Mail), ohne die Rollen, die nur die Verwaltung angehen (verwaltung, antragsteller, melder).
  Tabelle der letzten 20 offenen mit vier Spalten (Mail: Zeit · Art · Bezug als Link ins Modul, darunter klein der
  Betreff; Empfänger mit Rolle – nie eine Adresse; Fehler als deutscher Text, darunter klein die Antwort des
  Mailservers; „Erledigt“), bis 800 px Inhaltsbreite Karten; „Weitere anzeigen“ lädt alle offenen der Sicht (`GET
  /api/material/mailfehler`, höchstens 200); je Zeile „Erledigt“ (grau; `POST /api/material/mailfehler/<id>/erledigt`,
  die Zeile verschwindet, der Fokus geht zur nächsten Zeile, 404 als Meldung), im Untermenü „Mehr“ des Kastens „Alle
  erledigt“ mit Rückfrage (`POST …/alle-erledigt`, Antwort mit Zahl als Meldung im Kasten); Dauerzeile „Kein Mailserver eingerichtet – keine
  Modul-Mail geht hinaus“ für die Verwaltung; Hinweis „Erinnerungen holt der nächste Lauf nach; alles andere sagst du
  den Betroffenen selbst – ein erneuter Versand ist nicht möglich.“ Der Laufstand zeigt weiter die Zahl der
  Fehlschläge, die Namen stehen nur noch im Kasten (`fehlgeschlagen_an` entfällt).
- **Bezug-Links** (Oberfläche, vom Server aus Kennungen gebaut – `mailprotokoll._bezuege`, nie aus Datenbanktexten):
  Artikel und Mangelmeldung → Artikel (mit Inventarnummer), Ordner und Erinnerung → Ordner bzw. Gliederung (mit
  Namen), Rückruf → Produktseite, Änderungsantrag → Anträge, Produktmeldung → Meldungen; was es nicht mehr gibt, bleibt
  Text ohne Link.
- **Pflege und Löschkonzept**: Zeilen älter als 13 Monate, erledigte älter als 3 Monate und Waisen (Kontoverweis ohne
  Konto) löscht der Tageslauf und die Startpflege; `loeschung.konto_loeschen_vorbereiten` nimmt die Zeilen des Kontos
  mit (Absatz im Kopf von `loeschung.py`, README „Austritt und Löschen“, Verfahrensverzeichnis-Vorschlag
  „Mailfehler-Protokoll: Arbeitsdaten, 13 Monate, mit dem Konto gelöscht“).
- **CLI** `flask material remind`: „Gescheitert – an wen, steht im Mailfehler-Protokoll auf der Übersicht“; die
  Pflegezeile nennt die entfernten Mailfehler-Zeilen.
- **C1 – Wiki und Nutzerverwaltung am Finger** (`app.css`, `admin.html`; nur bei `(pointer: coarse)`, am Rechner
  unverändert; Befunde der Geräte-Prüfungen vom 21./22.10.2026 außerhalb des Moduls): Kopfknöpfe der Wiki-Seite (☰,
  💬, Teilen, ⋯: 30 → 44 px, bei Bedarf in einer zweiten Reihe), Umschalter Lesen/Bearbeiten (26 → 44), „Neue Seite“
  und Papierkorb über dem Seitenbaum (28 → 44), „☰ Seiten“, Seitensymbol und Angaben-Knopf unter dem Titel, Anker „#“
  an Überschriften, Zeilenknöpfe im Seitenbaum (20 → 44), Links der Liste „Unterseiten“, Reiter (Kommentare,
  Nutzerverwaltung); Nutzerverwaltung: Kopfknöpfe (36 → 44), Auswahlfelder der Rechte-Matrix (26–33 → 44),
  Zeilenknöpfe „Bearbeiten“, „Reset-Mail“, „Löschen“ (28 → 44). Die Wiki-Schublade ist zugeklappt auch unsichtbar
  (`visibility`, nach der Fahrt) – sie lag sonst 320 px links neben dem Fenster und fing den Tab-Fokus. Die
  Aktionsspalte der Nutzertabelle (jetzt `col.col-aktionen`) ist zwischen 861 und 1100 px 112 px breit – die Knöpfe
  ragten dort 2 px über den Fensterrand (waagerechter Bildlauf auf dem aufgeklappten Fold).
- **C2 – Datumsfelder als deutsche Textfelder** (`material.js`, Muster `datumFeld`/`datumWert` wie Freigaben und
  Artikelfelder): Aussonderungsdatum (Hilfetext „Frühestens <letzte Prüfung | Herstellung | Erfassung>, spätestens
  heute“), „Gültig ab“ beim Hinzufügen von Dokumenten und einer neuen Version, „Nächste Prüfung“ im Prüfformular
  (Hilfetext „frühestens morgen, spätestens <Intervall>“; ein Tippfehler bricht das Festschreiben mit Toast ab – vorher
  wurde daraus still „spätestens“; außerhalb der Grenzen ebenfalls Toast, der Server prüft noch einmal; sessionStorage
  weiter ISO) und Prüfpunkte der Art „Datum“ (TT.MM.JJJJ im Feld, ISO an den Server; ungültig bleibt rot im Feld und
  wird nicht gesendet). Serverseitig (`pruefung.aussondern`): das Aussonderungsdatum liegt nicht vor der letzten
  abgeschlossenen Prüfung und nicht vor dem Herstelldatum (bei einer Monatsangabe zählt der erste Tag) – 409 mit
  Klartext; Zukunft und „vor der Erfassung“ wie bisher 400.

### Migration

- **Schritt 19**, Schemaversion 19, läuft beim Start von selbst, rein additiv und wiederholbar (nur `IF NOT EXISTS`):
  Tabelle `mat_mail_fehler` mit CHECKs für Art, Klasse, Bezugsart und Rolle, Längen 160/300, `instr(meldung,'@') = 0`
  und – mit der Nachbesserung nach der Sicherheitsprüfung, Schritt 19 war noch nirgends ausgeliefert –
  `instr(betreff,'@') = 0`,
  `konto_ref <> ''`, `(erledigt_at IS NULL) = (erledigt_von_name IS NULL)`, `folder_id REFERENCES mat_folder(id) ON
  DELETE SET NULL`; Indizes (erledigt_at, created_at), (folder_id), (konto_ref); Trigger `mat_mail_fehler_fest`
  (alle Felder außer erledigt_* unveränderlich) und `mat_mail_fehler_ordner` (folder_id darf nur auf NULL gehen – so
  kommt das ON DELETE SET NULL des Ordners durch); dazu die Indizes für den Bericht `idx_mat_inspection_inspected_on`
  und `idx_mat_audit_entity_action`. Kein Umbau, keine Zeilenänderung; zweiter Lauf ohne Änderung. Frisch, 18 → 19
  (`bis_schritt(18)`) und 7 → 19 (`MATERIAL_KOPIE_STAND_7`, nur bei gesetzter Kopie) geprüft; die Startpflege auf einer
  Datenbank vor Schritt 19 läuft über den Tabellen-Guard ohne Fehler.
- **Neue Abhängigkeiten: keine.**

### Entscheidungen

Vom Nutzer am 22.10.2026 (Entwurf Abschnitt F):

1. Inhalt des Berichts: **alle Blöcke** (Bestand und Bewegungen; Prüfungen mit Prüfabdeckung; Durchgänge, Sperren,
   Aussonderungen, Mängel; Rückrufe und Ausblick über zwölf Monate).
2. Empfänger: **Gliederung intern** (Titel „Jahresbericht Material <Zweig> <Jahr>“, Fußtext für den internen Gebrauch,
   kein Nachweis-Charakter).
3. Personennamen **nur mit Haken „Prüfer nennen“**; Dateiname „-mit-pruefern“.
4. **DEMO einbeziehen und kennzeichnen** (wie der CSV-Export) – sonst wäre der Bericht auf dev leer.
5. Mailfehler-Sicht: **MV/PV alles, Zweig-Verwalter ihre Zeilen, Sammelmails je betroffener Gliederung eine Zeile.**
6. Versand-Wrapper hält **alle fünf Mailarten einheitlich still** (Sperre, DEMO, kein Mailserver) – gilt neu auch für
   Rückruf- und Produktmeldungs-Mails auf dev.
7. Zeitraum **Kalenderjahr**, Bestand zum **Stichtag heute**.
8. **C2 in dieser Lieferung** (mit Grenzprüfung).

Vorgaben des Baus, noch zu bestätigen (siehe „Zu prüfen“): Schrift DLRG Univers im Bericht; Aufbewahrung 13 Monate,
erledigte 3 Monate; kein „Erneut senden“; Kappung 500 Zeilen im PDF; Jahr-Auswahl bis 15 Jahre; keine eigene
Mailfehler-Seite.

### Abweichungen vom Konzept, mit Begründung

- Der Bericht ist **kein Nachweis** (Fußsatz „kein Prüfnachweis – Nachweise sind die Protokolle“) und wird wie der
  Lebenslauf auf Abruf gesetzt, nicht festgeschrieben: Zahlen ändern sich mit Berichtigungen rückwirkend, ein Status
  zum 31.12. lässt sich nicht rekonstruieren (Status wird nie gespeichert) – Bestandszahlen gelten daher zum Stichtag
  heute, Ereignisse für das Kalenderjahr.
- **Zuordnung nach heutiger Heimat** (wie Export und Durchgang): Artikel, die den Bereich verlassen haben, fehlen;
  hinzugekommene bringen ihre Historie mit (Fußsatz).
- **Mailtexte werden nicht gespeichert** – deshalb kein „Erneut senden“; Erinnerungen wiederholt der nächste Lauf von
  selbst, alles andere sagt der Verwalter den Betroffenen.

### Abweichungen vom Bauentwurf

KERN K1 (Bericht):

1. Jahr und Haken im **Pfad der Dateirouten** (`bericht-<jahr>.pdf`, `-pruefungen-<jahr>.csv`, eigener Pfad
   `-mit-pruefern`) statt als Abfrageparameter – der Dateiname sagt, was weitergegeben wird; `<int:jahr>` wird zusätzlich
   gegen 1990…2100 geprüft (400 als Fehlerseite).
2. Sperrart „sonst“ heißt **„Sperre durch Prüfer ohne Prüfung“** (nicht „durch Materialwart“): Ohne Prüfung sperrt nur
   ein Prüfer. Sperrdatum in der Liste ist der deutsche Kalendertag des UTC-Zeitstempels.
3. „davon fällig“ je Kategorie nach `bestand.FAELLIG` (überfällig, Lebensdauer, neu, bald fällig) – dieselbe Regel wie
   die Fälligkeitenliste; offene Entwürfe: Entwürfe mit Prüftag im Jahr; Prüfabdeckung zählt nur Artikel des Bestands
   (eine im Jahr ausgesonderte Prüfung zählt in „gesamt“, nicht in der Abdeckung); Gelöschte über das Journal
   „geloescht“ mit Heimat laut Vorher.
4. Aufschlüsselung je Unterordner: Zeile „<Zweig> (direkt)“, Unterordner der ersten Ebene in Baumreihenfolge,
   Untergliederungen mit Kennzeichen „Gliederung“, Systemordner ohne Zeile, Ausgesonderte ohne Herkunft unter
   „<Zweig> (ohne Herkunftsordner)“.
5. CSV: eine Zeile je Prüfung **und** Aussonderung (Spalte „Art“), berichtigte Originale ausgeschlossen wie in den
   Zahlen, „Berichtigung von“ nennt das Original.
6. Kappungshinweis im PDF „… die vollständige Liste zeigt die Berichtsseite (höchstens 500 Zeilen im PDF)“ – nicht „in
   der CSV“: nicht geprüfte Artikel, Sperren und Meldungen stehen nicht in der Prüfungs-CSV.
7. Ein heute laufender Rückruf steht auch im Bericht eines früheren Jahres, wenn er vor dessen Ende angelegt war (Regel
   „angelegt oder beendet im Jahr oder heute laufend“; seit der Ablaufprüfung nicht mehr in Jahren vor seiner Anlage);
   die Monate des Ausblicks beginnen mit dem Stichtag – Überfällige stehen nur unter „jetzt“.
8. `rechte.artikel_filter(…, s=None)` nimmt eine schon gerechnete Sicht an (additiv); `services.antwort_privat`
   (no-store) aus `routes_export._privat` gezogen; `bericht_zugang` antwortet auf `/api/…` mit JSON (401 statt
   Umleitung). Kennung `"jahr"` auch in `test_material_ueberblick` und `test_material_stufen` (laufen alle Routen durch).

KERN K2 (Mailfehler):

9. **Zweiter Trigger** `mat_mail_fehler_ordner` statt `folder_id` in `mat_mail_fehler_fest`: Ein BEFORE-UPDATE-OF-Trigger
   auf `folder_id` feuert auch bei `ON DELETE SET NULL` – mit `folder_id` in der Spaltenliste ließe sich kein Ordner mehr
   löschen, an dem eine Zeile hängt.
10. Zusätzlicher CHECK `(erledigt_at IS NULL) = (erledigt_von_name IS NULL)` – Abhaken ist immer mit Handelndem.
11. `senden(…, demo=False)` als zusätzlicher Parameter („DEMO-Artikel“ kennt nur der Dienst); die Dienste geben auch
    stille Mails an HINTERGRUND; Stille ohne Mailserver über `mailprotokoll.MAILSERVER` (Ersatzpunkt für Tests –
    `mangel.MAILSERVER` und `antrag.MAILSERVER` entfallen).
12. Rolle „verwaltung“ auch beim Rückruf (Rückfall ohne Verwalter); **eine Rolle je Erinnerungsmail** (verwalter >
    verwaltung > inhaber > zugeordnet) statt je Eintrag.
13. Trennungstest: Platzhalter `mfid` statt des Tupels („mailfehler“, „id“); „Alle erledigt“ ohne Sicht → **403** (statt
    200 mit 0) – für Leser gibt es keinen Kasten, Schreibrouten antworten der Führungskraft 403.
14. Testhelfer `mails_abfangen(dienst, f)` / `mails_zurueck(alt)` in `tests/test_material.py` ersetzen an einer Stelle
    HINTERGRUND, `mailprotokoll.versand` und MAILSERVER; alle Mail-Testdateien nutzen ihn (`<dienst>.send_mail` gibt es
    nicht mehr). Migrationstests nachgezogen (`test_migration_17`, `test_migration_18`). `senden` innerhalb einer
    Transaktion: Logzeile statt Ausnahme, der Versand läuft, die Zeile entfällt.
15. README: Die Löschkonzept-Sätze stehen bei „Austritt und Löschen“ und beim Pflegeteil der Erinnerungsmails (der
    Abschnitt „Daten und Sicherung“ hat keinen Löschkonzept-Absatz).

OBERFLÄCHE:

16. **Bezug-Links löst der Server auf** (`mailprotokoll._bezuege`, Feld `bezug` {text, pfad} je Zeile): Die Zeile einer
    Mangelmeldung trägt die Meldungskennung, nicht die des Artikels – der Entwurf ließ offen, wer sie auflöst. Aus
    Kennungen gebaute Modul-Routen, nie Links aus Datenbanktexten; höchstens vier Abfragen für den ganzen Kasten.
17. Das Untermenü des Kastens heißt „Mehr“ (wie bei anderen Kästen); „Alle erledigt“ fragt mit der Zahl der offenen
    Zeilen nach. Ist nichts mehr offen, bleibt der Kasten bis zum Neuladen mit der Meldung stehen (Fokus dorthin; ohne
    Mailserver dazu die Dauerzeile).
18. Der Laufstand-Hinweis oben („n Erinnerungsmails sind gescheitert“) verweist auf „Mailversand“ statt Namen zu
    nennen.
19. Berichtsseite: der Zweigpfad als Brotkrume über dem Titel (Bestand / <Pfad> → Ordner), die Blöcke als Abschnitte mit
    denselben Überschriften wie im PDF; der Kappungshinweis steht nur, wenn eine Liste länger als 500 Zeilen ist
    (`BERICHT_KAPPUNG` in `material.js` – der Server liefert die Grenze nicht im JSON).
20. C1 geht über die Liste des Entwurfs hinaus (Seitensymbol, Angaben-Knopf, Anker „#“, Liste „Unterseiten“,
    Kommentar-Reiter, Wiki-Schublade, Aktionsspalte): Nachgemessen am Platzhalter-Wiki und in der Nutzerverwaltung
    (360 und 882 px, Touch-Emulation) – ohne diese Punkte blieben dort Tippflächen unter 44 px und ein Überlauf.
    Zwei Punkte liegen außerhalb: Die Kopfknöpfe der Wiki-Seite brechen am Telefon (360 px) in eine zweite Reihe um
    (vier 44-px-Knöpfe und der Umschalter passen nicht nebeneinander) – siehe „Zu prüfen“.
21. C2: Die Datumsprüfung im Aussondern-Dialog läuft **vor** der Unterschrift (ein Tippfehler öffnet nicht erst das
    Unterschriften-Pad). Für den Prüftag gibt es kein Feld (Entwurf-Kritik C1): Er ist immer heute bzw. der des
    Originals.

### Schnittstelle

Neu bzw. geändert (Einzelheiten in der Tabelle am Ende): `GET /material/ordner/<fid>/bericht`,
`GET /api/material/ordner/<fid>/bericht?jahr=&pruefer=`, `GET /material/ordner/<fid>/bericht-<jahr>[-mit-pruefern].pdf`,
`GET /material/export/<fid>-pruefungen-<jahr>[-mit-pruefern].csv`; `GET /api/material/start` → `mailfehler`;
`POST /api/material/mailfehler/<mfid>/erledigt`, `POST /api/material/mailfehler/alle-erledigt`; Laufstand
`erinnerungen.letzter` ohne `fehlgeschlagen_an`, Pflegestand `pflege.mailfehler`; `POST /api/material/artikel/<id>/aussondern`
409 bei Datum vor der letzten Prüfung oder dem Herstelldatum. Konstanten: `bericht.KAPPUNG` 500, `JAHRE_MAX` 15,
`mailprotokoll.LISTE_MAX` 20, `AUFBEWAHRUNG_MONATE` 13, `ERLEDIGT_MONATE` 3, `NACHGEHOLT` „nachgeholt“.

### Im Browser geprüft

Chromium (cdp.py) gegen einen lokalen Server **ohne `SMTP_HOST`** mit dem DEMO-Bestand (`scripts/material_demo.py
--demo --konten`), einer Platzhalter-Mangelmeldung, sechs von Hand erzeugten Mailfehler-Zeilen (Erinnerung an die
Gliederung, Mangel an Materialwart und Prüfer, Antrag an die Verwaltung, Rückruf zu einem nicht vorhandenen Rückruf,
„Deine PSA“ mit Artikel-Bezug), einem Platzhalter-Wiki mit drei Unterseiten und einem Konto „Führungskraft“ (lesen),
bei 1280 und 360 px, ohne Konsolenfehler und ohne waagerechten Bildlauf:

- **Material-Verwaltung**: Übersicht mit Kasten „Mailversand“ unter dem Laufstand (Dauerzeile ohne Mailserver, sechs
  Zeilen mit Links „Artikel M-000002“, „Mangelmeldung M-000001“, „Änderungsantrag“, „DEMO-Gliederung“; „Rückruf“ nur als
  Text), „Erledigt“ nimmt die Zeile weg (Toast „Erledigt“), „Mehr“ → „Alle erledigt“ → „5 Zeilen erledigt“, Tabelle weg,
  Dauerzeile bleibt; Berichtsseite 2026 (Jahr-Auswahl 2025/2026), Haken „Prüfer nennen“ → Block „Prüfer im Jahr“, Adresse
  `?pruefer=1`, PDF-Link `…-mit-pruefern.pdf`; `?jahr=1800` → „„Jahr“ muss zwischen 1990 und 2100 liegen.“;
  Systemordner → 404-Seite; Dokumentdialog mit „Gültig ab“ als TT.MM.JJJJ (ungültig rot).
- **Führungskraft**: Übersicht ohne Kasten, Bericht als Seite, PDF (inline, `DEMO-Jahresbericht_DEMO-Gliederung_2026.pdf`)
  und CSV (`DEMO-Pruefungen_DEMO-Gliederung_2026-mit-pruefern.csv`).
- **Prüfer**: Prüfformular, „einsatzbereit“ → Feld „Nächste Prüfung“ als TT.MM.JJJJ mit „frühestens 23.10.2026,
  spätestens 22.04.2027“; „31.02.2027“ → Toast „bitte als TT.MM.JJJJ angeben“, Feld rot, nichts festgeschrieben;
  „01.01.2030“ → Toast „… vorziehen geht, verschieben nicht“.
- **Materialwart**: „Aussondern“ am gesperrten Artikel – Datum vorbelegt mit heute, Hilfetext „Frühestens 22.10.2026
  (Erfassung), spätestens heute“; „31.11.2026“ → Toast, Dialog bleibt offen (vor der Unterschrift).
- **Wiki und Nutzerverwaltung** (Touch-Emulation, Administrator): bei 360 px keine Tippfläche unter 44 px mehr auf
  der Wiki-Seite und in der Nutzerverwaltung; bei 882 px (Fold aufgeklappt) kein waagerechter Bildlauf mehr in der
  Nutzerverwaltung.
- **Geräte-Matrix** (`st-geraete`, Chromium 155, Firefox 158, WebKit 26.6 × 21 Geräte Telefon bis Superwide;
  Berichte und Fotos unter `/home/harness/geraete-laeufe/p4l1-oberflaeche-20261022/<rolle>/`): Material-Verwaltung
  (Übersicht mit Mail-Kasten, Bericht 2026, Bericht 2025 mit Prüfern), Führungskraft (Übersicht, Bericht), Prüfer
  (Prüfformular mit Entwurf, gesperrter Artikel), Administrator (Wiki-Seite, Nutzerverwaltung). Erster Lauf: der
  Mail-Kasten mit acht Spalten ragte zwischen 601 und 1024 px Inhaltsbreite (Tablet hochkant, Fold Duo hochkant,
  Tablet quer neben der Ordnerleiste) 29–49 px über den Rand – seitdem bis 1100 px Inhaltsbreite Karten; im Wiki
  und in der Nutzerverwaltung blieben drei Tippziele unter 44 px (Klappdreiecke im Seitenbaum 28 × 32, Suchfeld 36,
  Aufklapper „Globale Suchen“ 38). Zweiter Lauf (`mv2`, `admin2`): **keine Befunde** auf allen 21 Geräten in allen
  drei Engines – kein waagerechter Bildlauf, keine Tippfläche unter 44 px, keine Konsolenfehler, nichts außerhalb des
  Fensters.
- **Nach den Nachbesserungen** (Server ohne `SMTP_HOST`; reiche Platzhalterdaten der Browserprüfung mit 533 Artikeln,
  31 Mailfehler-Zeilen und laufendem Rückruf; Läufe unter `/home/harness/geraete-laeufe/p4l1-nachbesserung-20261022-final/`):
  Material-Verwaltung (Übersicht, Bericht 2026, `?jahr=1800`), Führungskraft (Übersicht, Bericht), Materialwart
  (Übersicht) auf allen 21 Geräten in Chromium, Firefox und WebKit; Wiki-Seite als Material-Verwaltung, Führungskraft
  (beide mit Wiki-Leserecht) und Administrator auf Telefon quer, Fold aufgeklappt und Tablet quer: **keine Befunde**
  außer der gewollten 400 bei `?jahr=1800`, keine Kontrasthinweise mehr. Abläufe in Chromium (cdp.py) bei 1280 und
  360 px: Fokus nach „Erledigt“, „Weitere anzeigen“ (28 Zeilen), Rückfrage „Alle erledigt“, Fehlerauswahl beim Jahr,
  Sprungmarken, Rückruf-Liste, Datumsfehler mit `aria-invalid`, Fehlerseiten mit „Zur Material-Übersicht“.

### Prüfung vor Auslieferung

Nach dem Bau drei unabhängige Prüfungen auf HEAD 3dd55af (Berichte unter `planung/material-phase4/pruefung_l1_*.md`,
außerhalb des Repositorys) – **Sicherheit** (Rechte je Rolle an allen Berichtsrouten, Namen ohne Haken, Injektion,
Reinigung, Hintergrund-Schreibpfad, Pflege, Migration 8 → 19 und 17 → 19 an Kopien, Leistung bei 1 500 Artikeln):
3 Befunde, alle niedrig, und 6 Hinweise; **Ablauf** (Zählregeln, Zeitgrenzen, Stille, Nachholen und Sicht gegen die
Entscheidungen, Proben mit Platzhaltern über den Testclient): 1 Befund (mittel) und 6 Verbesserungen; **Browser**
(Chromium, Firefox, WebKit × 21 Geräte je Rolle, Abläufe mit Tastatur über cdp.py, 520 Platzhalterartikel und 31
Mailfehler-Zeilen): 5 Befunde (2 mittel, 3 niedrig) und 18 Verbesserungen; keine Befunde der Geräte-Matrix auf
Übersicht und Berichtsseite. Alle Befunde sind behoben, jeweils mit Test (Python bzw. statisch für die Oberfläche)
und – für die Oberfläche – im Browser nachgesehen; von den Verbesserungen sind die in der Tabelle genannten umgesetzt,
die übrigen stehen unter „Zu prüfen“ (Nr. 12–14).

| Nr. | Quelle | Befund / Verbesserung | Schwere | Umgang |
| --- | --- | --- | --- | --- |
| 1 | Sicherheit B1 | Der Anmeldename des Mailservers (`SMTP_USER`) stand ungereinigt in der Serverantwort – Exim nennt ihn in der 535-Antwort („set_id=…“); Zeilen der Klasse „anmeldung“ sehen auch Zweig-Verwalter | niedrig | `reinigen` ersetzt ihn als ganzes Wort (ohne Rücksicht auf die Schreibweise) durch „[Anmeldename]“; mit „@“ ist er eine Adresse und fällt ebenso. Test in `test_reinigung` mit Exim-Wortlaut |
| 2 | Sicherheit B2 | Der Betreff lief nicht durch die Reinigung (Rückruf-Titel und Produktmeldung sind freier Text), kein CHECK | niedrig | Betreff und Meldung über dieselbe Säuberung (`_saeubern`); Schritt 19 war noch nirgends ausgeliefert (dev steht auf Schema 18) und bekommt `CHECK (instr(betreff, '@') = 0)` – weiter nur `IF NOT EXISTS`, wiederholbar. Lokale Probenbestände, die schon auf 19 standen, haben den CHECK nicht (nur Platzhalter). Test |
| 3 | Sicherheit B3 | PDF ohne Gesamtgrenze: 23 laufende Rückrufe × bis zu 500 Artikel → 19,7 s und 63 Seiten je Abruf, ein Gunicorn-Thread belegt | niedrig | Im PDF je Rückruf höchstens 50 Inventarnummern (offene zuerst, „… und n weitere, siehe Berichtsseite“), alle Listen zusammen höchstens 1 500 Zeilen (danach je Rückruf nur die Zahl); Zahlen bleiben vollständig. Laufzeittest in `test_kappung`: 600 Artikel × 30 Rückrufe → 21 Seiten, ≈ 5 s |
| 4 | Ablauf B1 | Wer nur einen Unterordner verwaltet, bekam die Mangel-Mail, sah ihren Fehlschlag aber nicht und konnte ihn nicht abhaken (Zeile trug die Gliederung) | mittel | Einzelmails (Mangel, Antrag, Produktmeldung) tragen die Heimat des Artikels bzw. den Ordner der Meldung; „verwalten“ gilt nach unten, der Gliederungs-Verwalter sieht sie weiter. Sammelmails bleiben je Gliederung (Entscheidung Nr. 5). Test `test_unterordner_verwalter` (eigene Zeile sichtbar und abhakbar, Nachbarordner 404, „Alle erledigt“ nur im eigenen Ordner) |
| 5 | Ablauf V1 | Ein heute laufender Rückruf stand im Bericht eines Jahres vor seiner Anlage | niedrig | Nur noch, wenn `created_at < :bis`. Test |
| 6 | Ablauf V2 | Das Aussonderungsdatum durfte vor der Sperre liegen (Verlust heute gemeldet, Aussonderung im Vorjahr) | niedrig | 409 mit Klartext „… liegt vor der Sperre (…)“ – Tag des jüngsten Journaleintrags frei → gesperrt/verloren (Ortszeit); Altbestand ohne Journal ohne Grenze. Test |
| 7 | Ablauf V3 | Ausblick: überfällige Fälligkeit des laufenden Monats zählte unter „jetzt“ und im Monat, ältere in keinem | niedrig | Das Monatsfenster beginnt mit dem Stichtag; Überfällige nur unter „jetzt“. Test |
| 8 | Ablauf V4 | Kategorie nur aus Ausgesonderten als Nullzeile, Rückruf zu nur ausgesonderten Artikeln mit „betroffen 0“ | niedrig | Beide ausgeblendet. Test |
| 9 | Ablauf V5 | Dieser Abschnitt war leer | niedrig (Doku) | gefüllt |
| 10 | Ablauf V6 | Rückruf unter Sperre zählt in `mat_recall` als „gescheitert“ | Hinweis | unverändert, Zu prüfen Nr. 5 |
| 11 | Browser B1 | Wiki-Seitenbaum am Finger (Telefon quer, Fold aufgeklappt, Tablet quer): Titel auf „Unt…“ gekürzt (52 px) – Nebenwirkung von C1 | mittel | Am Finger je Zeile nur „⋯“ („Unterseite anlegen“ steht dort als erster Eintrag), oberste Ebene ohne Einrückung, Titel brechen um: „Unterseite eins“ 119 px einzeilig. Nur unter `(pointer: coarse)`; Fotos vorher/nachher, Geräte-Matrix ohne Befund |
| 12 | Browser B2 | Fokus nach „Erledigt“ und „Alle erledigt“ fiel auf `body` | mittel | Nach „Erledigt“ auf „Erledigt“ der nächsten (sonst vorigen) Zeile, ist nichts mehr offen auf die Überschrift; nach „Alle erledigt“ auf die Meldung im Kasten. Statisch; im Browser |
| 13 | Browser B3 | Berichtsseite bei ungültigem Jahr: nur eine rote Zeile, keine Auswahl (CHANGELOG versprach sie) | niedrig | Meldung mit Jahr-Auswahl (die letzten 15 Jahre) und Brotkrume; ein anderes Jahr lädt den Bericht. Statisch; im Browser |
| 14 | Browser B4 | Tab-Titel beim ersten Laden „Material – strömis.de“ | niedrig | „Jahresbericht <Zweig> <Jahr> – strömis.de“ schon beim ersten Laden. Statisch; im Browser |
| 15 | Browser B5 | `btn ghost` „🗑“ in der Wiki-Seitenleiste, Kontrast 4,40:1 | niedrig | Grau umrandeter Textknopf „Papierkorb“ (`btn secondary`), Kontrast ≈ 7:1 |
| 16 | Browser V1 | Mail-Kasten 5 100–5 500 px hoch (Karten mit sieben Zeilen bis 1 100 px Inhaltsbreite) | mittel | Vier Spalten, Karten erst bis 800 px Inhaltsbreite, drei bis vier Inhaltszeilen (am Telefon umbrochen): 31 Zeilen beim Materialwart 1 773 px bei 1280 (vorher 5 173), 2 657 bei 768 (5 501), 3 551 bei 360 (5 520) |
| 17 | Browser V2 | „… und n weitere“ nur blind abhakbar, „Alle erledigt“ ohne Rückfrage | mittel | „Weitere anzeigen“ lädt alle offenen der Sicht (`GET /api/material/mailfehler`, höchstens 200; Test); „Alle erledigt“ mit Rückfrage „n Zeilen als erledigt markieren?“, `btn danger` nur dort |
| 18 | Browser V3 | Rückruf-Block als Textwand mit allen Inventarnummern (Seite und PDF) | mittel | Seite: Zahlen und aufklappbare Liste (offene zuerst); PDF: siehe Nr. 3 |
| 19 | Browser V4 | Berichtsseite ≈ 25 800 px ohne Einstieg | niedrig–mittel | Sprungmarken zu den Blöcken; „Im Jahr nicht geprüft“ ab 26 Zeilen zugeklappt (Zahl in der Überschrift) – 4 302 px bei 1280 |
| 20 | Browser V5 | Englische Serverantwort als Haupttext | niedrig | Spalte „Fehler“: deutsche Klasse als Haupttext, Antwort klein darunter |
| 21 | Browser V7 | Datumsfehler „bitte als TT.MM.JJJJ“ auch bei 31.02., kein `aria-invalid` | niedrig | „den 31.02.2026 gibt es nicht.“ getrennt vom Formatfehler; `aria-invalid` am Feld. Statisch; im Browser (Aussondern-Dialog) |
| 22 | Browser V8 | Wiki-Kopfzeile am Telefon in zwei Reihen (108 px) | niedrig | Am Telefon (grober Zeiger, bis 640 px) steht „Teilen“ im ⋯-Menü – eine Zeile, 62 px (Zu prüfen Nr. 9 erledigt) |
| 23 | Browser V12 | PDF öffnet einen leeren Tab ohne Rückmeldung | niedrig | Hinweis „Das PDF wird erzeugt …“ wie bei der CSV |
| 24 | Browser V13 | Fehlerseiten der Modul-Routen führten „Zum Wiki“ | niedrig | Unter `/material` mit Modulzugang „Zur Material-Übersicht“ (`error.html`); ohne Modulzugang wie bisher. Test |
| 25 | Browser V14 | Kasten „Gemeldete Mängel“: Kontrast 4,22:1 (Link) und 4,48:1 (Hilfetext) | niedrig (vorbestehend) | Link im dunklen Rot (≈ 6:1), Hilfetext dunkler (4,8:1) |

Danach liefen die ganze Suite (`st-test`) grün, `st-py`, `st-js` und `st-css` ohne Meldung, dazu die Geräte-Matrix
(siehe „Im Browser geprüft“, Nachbesserung).

### Zu prüfen / Bitte bestätigen

1. **Schrift DLRG Univers im Bericht** – die Lizenz nennt bisher nur „PDF-Protokolle“; sonst DejaVu einstellen.
2. **Beschriftung „Sperre durch Prüfer ohne Prüfung“** (statt „durch Materialwart“ im Entwurf).
3. **Kappung 500** und der Hinweistext „vollständige Liste auf der Berichtsseite“ (im PDF) bzw. „Im PDF stehen nur die
   ersten 500 Zeilen dieser Liste“ (auf der Seite); Jahr-Auswahl bis 15 Jahre; keine eigene Mailfehler-Seite.
4. **Aufbewahrung 13 Monate / erledigte 3 Monate**; kein „Erneut senden“.
5. **Rückruf unter Sperre oder ohne Mailserver** zählt in `mat_recall` weiter als `mail_failed` (die Verwaltung sieht
   „n gescheitert“) – alternativ ein eigener Zustand „still“.
6. **Eine Rolle je Erinnerungsmail** (verwalter > verwaltung > inhaber > zugeordnet) – gemischte Mails laufen als
   „verwalter“.
7. **Zeilen mit Rolle „verwaltung“ aus dem Rückfall** (Mangel oder Erinnerung ohne Verwalter) sieht nur die
   Material-Verwaltung – der Zweig-Verwalter, den es dort nicht gibt, hat nichts zu sehen.
8. **Bezug-Links**: Mangelmeldung und „Deine PSA“ führen zum Artikel, der Rückruf zur Produktseite, Antrag und
   Produktmeldung zur Meldungen-Seite, die Erinnerung zur Gliederung – oder anders gewünscht?
9. **Wiki-Kopfzeile am Telefon** (C1): umgesetzt wie in der Browserprüfung empfohlen – am Telefon steht „Teilen“ im
   ⋯-Menü, ☰, Umschalter, 💬 und ⋯ passen in eine Zeile. Bitte bestätigen.
10. **Aussonderungsdatum vor der letzten Prüfung oder vor der Sperre** ist ein Fehler (409) – auch, wenn jemand bewusst
    rückdatieren wollte (die Aussonderung aus einer Prüfung trägt ohnehin deren Prüftag). Den Tag der Sperre nennt der
    Hilfetext im Dialog nicht (er steht nicht im Artikel-JSON); die Grenze meldet erst der Server. Bitte bestätigen.
11. **Auf dev.strömis.de** den Kasten „Mailversand“ mit echten Fehlschlägen ansehen (dort bleibt alles still –
    Umgebungssperre; Zeilen entstehen nur, wenn ein Mailserver eingerichtet und die Sperre aus ist).
12. **Nicht umgesetzte Verbesserungen der Browserprüfung** (klein, aber nicht risikolos oder Geschmackssache): V6
    „Artikel im Zweig (Sicht)“ im Berichtskopf und PDF (Fachwort „Sicht“; im Kasten ist es ersetzt); V9 Zweispalt und
    Lesemaß der Berichtsblöcke ab 1 500 px; V10 Abstände der `h3` im Bericht, DEMO dreifach im Kopf, „fällig“ je
    Kategorie zählt „neu“ mit; V11 zwei Mangelmeldungen am selben Artikel als gleiche Zeilen (die Liste kennt keine
    Meldungsnummer); V12 Höhe beim Nachladen; V15 Erklärabsatz in der Nutzerverwaltung (außerhalb des Moduls); V16
    leerer Zweig mit Nullzeilen; V17 eingetippte ISO-Daten werden vom Trenner zerlegt; V18 Hinweis oben, wenn der Kasten
    „Mailversand“ Zeilen hat. Bitte sagen, was davon gewünscht ist.
13. **Wiki am Finger**: Die Einträge der ⋯-Menüs im Seitenbaum sind etwa 32 px hoch (st-geraete prüft geschlossene
    Menüs nicht); ☰, 💬 und ⋯ im Wiki-Kopf sind weiter `btn ghost` mit Piktogramm (vorbestehend, außerhalb des Moduls).
14. **Kasten „Mailversand“ am Telefon**: Eine Karte hat vier Inhaltszeilen (Mail mit Betreff, Empfänger, Fehler mit
    Antwort), bei 360 px umbrochen etwa 170 px hoch; die Antwort des Mailservers ließe sich noch hinter „Technische
    Antwort“ einklappen – bitte am Gerät ansehen.

## Katalog am Telefon: „☰ Kategorien“ in der Suchzeile, keine Nummernsuche im Katalog (26.10.2026)

Wünsche des Nutzers: „In der mobilen Ansicht vom Katalog scrollt das linke Burgermenü nicht mit runter. Es könnte
neben den Suchbalken links rutschen, der mitscrollt“ und „Im Katalog soll die Suche nach Artikeln oben rechts
verschwinden, das führt sonst nur zu Verwirrungen“.

- **„☰ Kategorien“ in der Suchzeile** (material.js `leisteKnopfSetzen`, material.css): In der Ansicht „Katalog“ steht
  der Knopf, solange die Kategorienleiste eine Schublade ist (unter 1024 px, kein Doppelbildschirm), links neben dem
  Suchfeld der Produktliste und klebt mit ihr unter der Kopfleiste – auch weit unten in der Liste kommt man an die
  Kategorien. Es ist derselbe Knopf (verschoben, nicht doppelt): Handler, `aria-expanded` und die Fokus-Rückkehr
  bleiben; dort steht nur „☰“, der Name „Kategorien“ bleibt für Vorleseprogramme. So hoch wie das Suchfeld, unter
  Touch 44 × 44 px. Wird das Fenster breiter (Leiste daneben, Tablet gedreht), kehrt er in die Modulnavigation zurück
  und wieder hinein; eine Kategorie aus der Schublade oder dem Pfad lässt ihn in der Suchzeile. Schließen mit ✕,
  Esc, Wischen oder Kategoriewahl gibt den Fokus an den Knopf zurück (Wischen und Kategoriewahl nur, wenn er in der
  Suchzeile steht – dort rollt der Fokus die Seite nicht). Produkt, Formular, Meldungen und die übrigen Ansichten:
  unverändert; am Rechner ab 1024 px unverändert.
- **Keine Nummernsuche im Katalog** (seite.html): In Katalog, Produkt, Formular und Meldungen liefert die
  Modulnavigation weder das Feld „Nummer suchen“ noch die Lupe aus; Übersicht, Prüfungen, Bestand, Ordner, Artikel
  und Trefferseite behalten sie. `navAnordnen` prüft die Einzeiligkeit jetzt auch über die Reiter selbst – stehen nur
  noch sie in der Zeile, rollen sie am Telefon seitlich statt umzubrechen.
- Test: `test_material_l5.py::test_katalog_ohne_nummernsuche_knopf_in_suchzeile`.

## Nachbesserung nach den Prüfungen der Umbenennung (26.10.2026)

Prüfungen von fa5ef38 (Sicherheit und Ablauf: lieferbar; Browser: nach Befund 1).
- **B1 (hoch, Browser)**: `wiki.js` `slugFromPath()` schnitt nur `/wiki/` ab – die Startseite `/stroemipedia` und die
  Zurück-/Vor-Taste nach einem Seitenwechsel luden „Seite nicht gefunden“ (`/api/wiki/pages/stroemipedia`). Jetzt
  `/^\/(?:(?:stroemipedia|wiki)(?:\/|$))?/`: „/“, „/stroemipedia“ → Startseite, „/stroemipedia/<slug>“ und
  „/wiki/<slug>“ → Slug. Alle JS-Dateien und Vorlagen nach weiteren Stellen durchsucht, die ein Präfix abschneiden,
  vergleichen oder zerlegen: `public.js` (Präfix aus `data-prefix`, Umschreiben beider Schreibweisen), `wiki.js`
  (Klickweiche beider Schreibweisen, `slugAus` mit `SEITEN`, Adresse nach dem Speichern), `error.html`
  (`/materialablage`), `material.js`/`map.js`/`common.js`/`pruefungen.js`/`auth.js` (nur `location.pathname` für
  `next=` bzw. `replaceState` ohne Präfixlogik) – sonst keine.
- **B2 (niedrig, Browser)**: Hauptnavigation – die Überlaufprüfung (`common.js`) ohne 1-px-Spielraum, und die
  Bauchbinde hat rechts mindestens 8 px (`max(8px, env(safe-area-inset-right))`; vorher setzte die Regel für Kerben den
  Rand am Rechner und am Telefon auf 0). „Abmelden“ bzw. „Mehr“ steht nicht mehr am Fensterrand.
- **Befund 1 (niedrig, Sicherheit)**: Verlauf des Kontos (E3) – Löschen und Ablehnen eines Kontos schreiben einen
  Grenzstein „geloescht“ ins Journal am Konto; `journal.lesen` schneidet dort (nach der Journalkennung, nicht nach der
  Uhr), ein Nachfolger mit derselben Kennung sieht nichts davor – auch in derselben Sekunde. Kein Schemaschritt. Für
  Löschungen vor dieser Nachbesserung (ohne Grenzstein) bleibt der Vergleich mit dem Anlagezeitpunkt – dort ist der
  Randfall „gleiche Kennung in derselben Sekunde“ weiter möglich.
- **Ablauf**: `st-test` nimmt `tests/test_umbenennung.py` ohne Angabe mit (Satz im Abschnitt „Neue Modulnamen“ korrigiert).
- **Verbesserungen**: Zugangsmeldungen „… das macht/gibt/setzt die Plattform-Verwaltung in der Leitstelle“ (statt „die
  Verwaltung in der Nutzerverwaltung“; rechte.py, pruefung.py, material.js, freigaben.js). Die 403-Seite eines Moduls
  nennt es wie die Schnittstelle („Für dein Konto sind die Riegenkarten nicht freigeschaltet.“ usw.; `abort(403,
  description=…)`, Ankerplätze, Strömipedia, Riegenkarten, Leitstelle). Rechte-Matrix in der Reihenfolge der Kopfleiste
  (Strömipedia vor Ankerplätze). Nutzerdialog: „Das Konto braucht einen Namen, damit es in der Materialablage handeln
  kann.“ Rückfrage „Ordner … endgültig löschen? Danach ist er weg. …“. Hilfe der Leitstelle in Absätzen mit einer
  Liste je Stufe. Tippflächen nur unter `@media (pointer: coarse)` auf 44 px: Zoom und „◎“ der Ankerplätze (auch ohne
  `.leaflet-touch`), Filter-Chips, „Alben“, „Neues Album“, im Profil Eingabefelder und Knöpfe (`.profil-seite`).
- Tests: `test_umbenennung.py` (Ausdruck von `slugFromPath` gegen Start-, Seiten- und alte Pfade, 403-Seite je Modul,
  Spaltenreihenfolge), `test_material_feinschliff.py` (Vorgänger nach Löschen und nach Ablehnen, Anlagezeit
  zurückgesetzt – nur der Grenzstein hält ihn fern; Rückfragetext).

## Feinschliff aus den Wiki-Fragen (26.10.2026)

Die 25 „Offenen Fragen“ des Wiki-Artikels „Materialablage“ (W5), eingeordnet im Bauentwurf
`entwurf_feinschliff_wiki_fragen.md`: 16 × Text/Doku (T), 3 × kleiner Code-Fehler (K), 6 × Entscheidung (E1–E6, am
26.10.2026 entschieden). Gebaut mit den neuen Modulnamen. Kein Schemaschritt.

**Entscheidungen.** E1 A: Die E-Mail-Adresse im Feld „Anmeldung“ der Prüf- und Aussonderungsprotokolle bleibt (die
„Login-Identität“ der einfachen elektronischen Unterschrift, Lieferung 3); die Texte sagen es jetzt ehrlich (README,
Profil „… zusammen mit deiner Anmeldung (E-Mail-Adresse) …“). E2 B: „Deine PSA“ läuft immer – auch in Ordnern mit
„Erinnerungsmails aus“; nur der eigene Haken im Profil zählt. E3 A: Verlauf des Kontos für die Leitstelle. E4 A:
Rückrufe bleiben (anlegen und beenden mit Vermerk; README sagt, wie man berichtigt). E5 B: betrifft nur den
Wiki-Artikel (Migrationshinweis ohne Kontaktadresse). E6 C: „Qualifikation 1012“ entfällt aus der Oberfläche.

**Code.**
- **E2 B** (`erinnerung.py`): `artikel_kandidaten` nimmt einen zugeordneten Artikel aus einem Ordner mit „Erinnerungsmails
  aus“ (auch geerbt) trotzdem mit – als Eintrag `nur_psa`; `planen` gibt ihn nur der zugeordneten Person als „Deine
  PSA“ (Stufe nach `PSA_STUFE`, Vermerk wie bisher je Kontoverweis), auch wenn sie den Ordner selbst verwaltet (sie
  bekäme ihn dort ja nicht unter ARTIKEL). Keine Sammelmail an Verwalter, kein „ohne Empfänger“; der Ordner zählt
  weiter unter „Erinnerungen aus in …“ (alle Artikel dort). Abbestellt (`mat_psa_mails = 0`): nichts.
- **E3 A** (`api_admin.py`): `GET /api/admin/users/<id>/journal` (nur Plattform-Verwaltung, `admin_required`; 401 ohne
  Anmeldung, 403 sonst, 404 unbekannt) – die letzten 50 Einträge des Journals am Konto (`entity = 'user'`: rollen,
  Urkundennummer, Unterschrift) als fertige Zeilen (`beschriftung.journal_zeilen`, Handelnde mit Namen). Die Unterschrift
  steht nur als „hinterlegt“/„–“ da, ohne Bild und ohne den Fingerabdruck aus dem Journal. Einträge von vor der Anlage
  des Kontos gehören einem gelöschten Konto mit derselben Kennung (`users.id` ohne AUTOINCREMENT) und bleiben draußen.
  Oberfläche (admin.js): im Dialog „Bearbeiten“ unter den Freigaben eingeklappt „Verlauf (Materialablage)“, geladen
  beim ersten Aufklappen; Tabelle Zeit · Was · Von · Änderung (auf dem Telefon Karten). Pfad wie die übrigen Routen der
  Nutzerverwaltung (`/users/<id>/…`) statt `/nutzer/<id>/journal` aus dem Entwurf.
- **K9** (material.js, Katalog): Ohne eigenes generisches Formular nennt die Angabenzeile einer Kategorie das der
  nächsten Oberkategorie – „· generisches Prüfformular von „<Name>““, Link zur Kategorie (Material-Verwaltung, dort
  steht der Knopf) bzw. zum Formular; ohne jedes weiter „kein aktives generisches Prüfformular“. Server unverändert.
- **K19** (material.js): Menütext „Löschen …“ und Rückfrage nennen alle Bedingungen des Servers (ohne Unterordner und
  Artikel, ohne Prüfdurchgänge und Set-Protokolle, ohne offene Nacharbeit, ohne gesperrte Artikel, die zurückkehren).
- **K21** (freigaben.js, admin.js): Hinweis nach „Entziehen“ „… unter Prüfungen → „Offene Prüfungen“ mit „Reservierung
  aufheben““ (so heißen Abschnitt und Knopf).

**Texte.** T12 neue Protokolle: QR-Beschriftung „Artikel online“ (basis.html; alte PDFs unverändert); T20 CSV-Menü
„… auch die von hier gesperrten und ausgesonderten …“; T24 „Sperren und Freiprüfungen im Jahr …“ (Seite und PDF des
Jahresberichts); E6 C „Urkundennummer (Prüfernummer)“ (Profil), „Prüfer (Sachkundiger)“ (Nutzerdialog); E2 B
Ordnerhilfe „Erinnerungsmails aus“ und Profil („… auch wenn der Materialwart für den Ordner die Erinnerungsmails
abgeschaltet hat“). README nachgezogen zu T1 (Ordner zur Gliederung: Material-Verwaltung), T2 (Prüfsicht), T6
(Fälligkeit nachziehen), T7 („bis“-Vorgaben), T8 (Katalogimport ändert, was die Datei nennt), T10 („n. z.“), E1 A, T12,
T13 („Alle Protokolle (ZIP)“ nur mit Set-Protokollen), T14 (wer abschließt, unterschreibt nicht), T16 („Zugeordnet an“),
T17/T18 („Nächste Prüfung“ erst nach der ersten Prüfung; Lebensende vor ihr nur vorziehen), T24, E2 B, E3 A, E4 A.
Vermerke im CHANGELOG: „Bitte bestätigen“ der Wünsche vom 25.10.2026 Nr. 2 und der Anträge Nr. 2 (T17, T18), Stand der
Punkte 1–5 von „Aussondern nur durch den Materialwart“ (T25).

**Tests.** `tests/test_material_feinschliff.py` (neu): E2 B im Plan und im Tageslauf (Person, Materialwart mit eigener
PSA, nicht zugeordneter Artikel bleibt still, Zählung „ausgelassen“, abbestellt, Schalter wieder an), E3 A je Rolle,
Inhalt ohne Bild und E-Mail, höchstens 50, Vorgänger mit derselben Kennung; neues Prüfprotokoll mit „Artikel online“
(veraPDF PDF/A-3b bestanden); Texte von K9, K19, K21, T12, T20, T24, E1, E2, E6 statisch.

## Neue Modulnamen (Wunsch des Nutzers, 26.10.2026)

Wunsch des Nutzers, wörtlich: „Strömipedia für Wiki / Ankerplätze für Karte / Materialablage für Materialmodul /
Leitstelle für Verwaltung“, Nachtrag „Prüfungen in Riegenkarten umbenennen“ (das Modul Prüfungen – nicht die
Prüfungen der Materialablage). Umfang: sichtbare Namen UND Adressen, die alten leiten weiter (Bauentwurf
`entwurf_umbenennung.md`, Entscheidungen F1–F5 vom 26.10.2026). Kein Schemaschritt, keine Datenänderung.

| Modul (Schlüssel) | bisher | neu | Seiten bisher → neu |
| --- | --- | --- | --- |
| `wiki` | Wiki | Strömipedia | `/wiki…` → `/stroemipedia…` (dazu `/strömipedia…`) |
| `karte` | Spots | Ankerplätze | `/karte` → `/ankerplaetze` (dazu `/ankerplätze`) |
| `pruefungen` | Prüfungen | Riegenkarten | `/pruefungen…` → `/riegenkarten…` |
| `material` | Material, „Modul Material“ | Materialablage | `/material…` → `/materialablage…` |
| `verwaltung` | Verwaltung | Leitstelle | `/admin` → `/leitstelle` |

**Entscheidungen.** F1 A: Rollennamen bleiben („Material-Verwaltung“, „Wiki-Verwaltung“, „Plattform-Verwaltung“), ebenso
die Stufe „Verwaltung“ in jedem Modul („Leitstelle: Verwaltung“). F2 A: Begriffe in den Modulen bleiben (Album, Lehrgang,
Katalog, Prüfer; in der Materialablage die Prüfungen, der Reiter „Prüfungen“, Prüfprotokoll …). F3 A: ASCII-Pfade, die
Umlaut-Schreibweisen leiten zusätzlich weiter. F4 A: gespeicherte Wiki-Links werden nicht umgeschrieben. F5 A: neue
Protokolle und Lebensläufe drucken `strömis.de/materialablage/pruefen`.

**KERN.**
- `app/module.py` (neu): `NAME`, `PFAD`, `ALT`, `UMLAUT` und `weiterleitung(pfad, abfrage)`. Interne Schlüssel bleiben
  (`auth.MODULE`, `recht_<modul>`, Blueprint- und Endpunktnamen, Dateinamen, `/api/…`, CLI-Gruppe `material`).
- Weiterleitung: erster `before_request`-Haken `alte_adressen` (vor `einstellungen_anwenden` – keine Datenbankabfrage),
  nur GET/HEAD, ohne Anmeldung und Rechteprüfung (das Ziel prüft selbst), 301 mit `Cache-Control: public,
  max-age=86400` (ein Rückbau bleibt möglich). Ziel = festes neues Präfix + der Rest des Pfads, kodiert nach RFC 3986
  (pchar; Rückstrich, Steuerzeichen und „%“ werden kodiert) + die rohe Abfrage – nie ein Host, ein Schema oder „//“
  am Anfang. Erfasst wird ein Pfad nur, wenn er dem alten Präfix gleicht oder mit „Präfix/“ beginnt (`/materialx`,
  `/wikis` nicht). Umlaute auch zerlegt (NFC). Auf der Wiki-Subdomain greift sie nicht (dort wird vorher auf
  `/oeffentlich/…` umgeschrieben). POST/PUT/DELETE auf alte Seitenpfade: 404/405 wie bei jeder unbekannten Seite.
- Seitenrouten in `app/__init__.py` und `app/material/routes*.py` auf die neuen Pfade; Startweiche über `module.PFAD`.
  Bleiben: `/`, `/m/<token>`, `/api/…`, `/media/…` (auch `/media/material/…`, `/media/pruefung/…`), `/static/…`,
  `/oeffentlich/…`, `/profil`, `/login` …
- Links in Mails (Erinnerung, Mangel, Meldung, Rückruf, Antrag, Mailfehler-Protokoll, Kontoanfrage → `/leitstelle`,
  Beobachten → `/stroemipedia/<slug>`) und in JSON-Antworten (`protokoll.url`, `weiter`, Wiki-Anleitung `url`) mit den
  neuen Pfaden. Gespeicherte Mailtexte (`mat_mail_fehler`) bleiben, wie sie verschickt wurden.
- PDFs: Kopf „Materialablage · Prüfnachweis | · Lebenslauf | · Jahresbericht“, `protokoll.PRUEFSEITE =
  "/materialablage/pruefen"`; Jahresbericht-Titel „Jahresbericht <Ordner> <Jahr>“ (ohne „Material“). Festgeschriebene
  PDFs bleiben byteweise, wie sie sind; ihre Prüfseite `/material/pruefen` leitet für immer weiter (ohne Anmeldung).
- Gespeicherte Wiki-Links (F4 A): `_LINK_REF_RE` erkennt `/wiki/<slug>` und `/stroemipedia/<slug>`; der ZIP-Import
  schreibt `/stroemipedia/<slug>`. Kein `DERIVED_VERSION`-Sprung (`wiki_page_links` gleicher Inhalt).
- Meldungen: `KEIN_ZUGANG` („Für dein Konto sind die Ankerplätze/Riegenkarten nicht freigeschaltet.“, „… ist die
  Strömipedia/Materialablage/Leitstelle …“; bisher „Nur für Prüfer“), Startseite ohne Modul „… an die
  Plattform-Verwaltung“, alle „Modul Material“-Texte („in der Materialablage“, „Zugang zur Materialablage“,
  `freigaben.OHNE_ZUGANG` „kein Zugang zur Materialablage“), „Leitstelle → Einstellungen“, Einstellungsgruppen
  „Riegenkarten“ und „Materialablage“, Erinnerungsbetreff „strömis.de – Materialablage: …“, Katalog-Export
  `bericht.txt` „Katalog-Export – Materialablage“, Journal-Beschriftung „Stufe Materialablage“, „Seite der Strömipedia
  Nr.“, „Prüfanleitung (Strömipedia) geändert“ (beschriftung.py und material.js). Die Meldung im Trigger des Journals
  („Das Journal des Moduls Material ist unveränderlich.“) bleibt – sie steht im Schema.

**OBERFLÄCHE.**
- Kopfleiste, Titel, Spalten der Rechte-Matrix und Dialogfelder der Nutzerverwaltung aus `module.NAME` (Jinja `modul`,
  `window.STROEMIS.module` für admin.js); Reihenfolge unverändert, Überlauf fängt das „Mehr“-Menü.
- Überschriften „Strömipedia“, „Riegenkarten“, „Materialablage“; Leitstelle-Seite behält „Nutzerverwaltung“;
  „Jahresbericht“ statt „Jahresbericht Material“; öffentliche Seite „öffentliche Strömipedia“, Suchfeld „Strömipedia
  durchsuchen …“, Titel „<Seite> – Strömipedia – strömis.de“; Fehlerseite „Zur Übersicht der Materialablage“ bzw. „Zur
  Strömipedia“; Lesemodus „Du siehst die öffentlichen Seiten der Strömipedia …“.
- Rund 150 Seitenlinks in material.js, 25 in wiki.js, 19 in pruefungen.js, je wenige in suche.js, freigaben.js,
  pruefen.js, admin.js und den Vorlagen auf die neuen Pfade (`${API}` = `/api/material` bleibt). wiki.js:
  `SEITEN`/`slugAus` statt `slice(6)`; Klickweiche, `public.js` (Umschreiben auf das Präfix) und die Prüfanleitung
  nehmen `/wiki/…` und `/stroemipedia/…`; der Editor schreibt neue Links als `/stroemipedia/<slug>`.

**Tests.** `tests/test_umbenennung.py` (neu; `st-test` nimmt die Datei ohne Angabe mit, wenn es sie gibt): jede alte
Adresse → neue (301, `Location`, Abfrage, `Cache-Control`, GET und HEAD, ohne Anmeldung, Plattform-Verwaltung, ohne
Stufe), Umlaute auch NFD, nichts sonst erfasst (`/materialx`, `/api/…`, `/media/…`, `/static/…`, `/m/…`, `/oeffentlich/`,
Wiki-Subdomain), keine Weiterleitung für POST/PUT/DELETE/PATCH, kein offener Sprung (`//`, Rückstrich, CRLF, `@`,
Schema im Pfad, RTL-Zeichen); neue Adressen wie die alten (Anmeldung mit `next`, 403, Startweiche, Lesemodus); Kopfleiste
(Namen, Reihenfolge), Titel, Rechte-Matrix, öffentliche Seite, Anmeldung, Fehlerseite, Zugangsmeldungen,
Einstellungsgruppen; Mails Kontoanfrage und Beobachten, statisch keine alten Pfade in Mail-Links; neues Prüfprotokoll
und Lebenslauf (Kopf, Prüfseite), ein Protokoll mit alter Prüfseite unverändert (Download, Prüfseite alt und neu);
Wiki-Links beider Schreibweisen in `wiki_page_links`; statisch (Zeichenketten ohne Kommentare/Docstrings) keine alten
Seitenpfade und Wortlaute in `app/`. Vorhandene Tests mechanisch auf die neuen Seitenpfade und Texte umgestellt.

## A4 „Aussonderung empfohlen“ als Filter und Übersichtszahl, N5 Mail bei Anträgen ohne Materialwart, W2 (25.10.2026)

Entscheidungen des Nutzers zur Freigabeliste L2c: „A4 N5 bestätigen“ – „Ja, beides bauen“; W2: „niemals hinter den
Produktwert, nur nach vorne“. **Schemaschritt 29.**

### A4 – Einstieg zu den Empfehlungen
- **Bestand:** Im Filtermenü der Seitenleiste (Telefon: Schublade) gibt es unter „Status“ den Eintrag **„Aussonderung
  empfohlen“** mit Zahl – angeboten, wo ein solcher Artikel liegt (fast immer im Ordner „Gesperrt“) oder der Filter
  gesetzt ist; er zählt wie die übrigen Filter (mit Kategorie, ohne Person). Schnittstelle: `GET /ordner/<fid>?status=
  aussonderung_empfohlen`, dazu `empfohlen` (Zahl) in der Antwort (`bestand.EMPFOHLEN`, `empfohlen_sql` – dieselbe Regel
  wie die Marke: gesperrt bzw. verloren und letzte Prüfung „aussondern empfohlen“).
- **Übersicht:** Hinweis „<n> Artikel mit Aussonderungsempfehlung – gesperrt, ein Prüfer empfiehlt die Aussonderung;
  aussondern kannst du sie als Materialwart.“ für Konten, die aussondern dürfen (Recht „verwalten“ an der Heimat; die
  Material-Verwaltung alle) – nur deren Artikel, je Gliederung getrennt. Der Link öffnet „Gesperrt“ mit gesetztem Filter
  (`/material/ordner/<Gesperrt>?status=aussonderung_empfohlen`); bei mehreren Gliederungen je eine Verknüpfung mit Zahl.
  Bei 0 nichts. Schnittstelle: `GET /start` → `aussonderung_empfohlen` [{ordner_id, gliederung, anzahl}].
- Gebaut als Hinweiskasten wie „offene Änderungsanträge“ (Muster der Übersicht), nicht als Kachel der Statuszahlen –
  die Empfehlung ist kein Status.

### N5 – Mail, wenn ein Ordner mit offenem Antrag keinen Materialwart mehr hat
- Fällt für die Heimat von Artikeln mit offenem Änderungsantrag die letzte wirksame Freigabe „verwalten“ weg (dort oder
  darüber; aktive Konten mit Modulzugang – dieselbe Regel wie „wer entscheidet“), bekommt die **Material-Verwaltung**
  eine Mail (dieselben Empfänger wie beim Antrag ohne Zuständige und bei Produktmeldungen; ohne Material-Verwaltung die
  Plattform-Verwaltung). Inhalt: Ordnerpfad, Gliederung, Zahl der offenen Anträge, Links auf die Freigaben des Ordners
  und die Anträge-Seite – keine Antragsinhalte, keine Namen.
- **Auslöser:** Freigabe entziehen, ändern oder herabsetzen (sofort, nach dem Commit), Konto deaktivieren, Stufe senken
  oder Namen leeren (Nutzerverwaltung), Konto löschen, Ordner verschieben (geerbte Verwalter wandern mit – seit der
  Ablaufprüfung vom 26.10.2026, N5-1), Ablauf befristeter Freigaben (Pflege im täglichen Lauf, `pflege.ohne_verwalter`). Antworten tragen ehrlich `mail` (ob eine Mail an den Versand ging; DEMO, dev-Sperre und
  ohne Mailserver nur ins Log, Fehlschläge ins Mailfehler-Protokoll).
- **Einmaligkeit** (`antrag.ohne_verwalter_melden`, Tabelle `mat_antrag_ohne_verwalter`): je Ordner und Wegfall eine Mail;
  hat der Ordner wieder einen Materialwart (oder keinen offenen Antrag mehr), verschwindet die Zeile, ein späterer
  Wegfall meldet neu. Ein Antrag, für den es schon beim Stellen keinen Zuständigen gab, zählt mit seiner Mail an die
  Material-Verwaltung als Meldung. Auch das Verschieben eines Ordners gleicht ab: Bekommt ein gemeldeter Ordner dort
  wieder einen Materialwart, verschwindet seine Meldung (der nächste Wegfall meldet neu); verliert er beim Verschieben
  den letzten, meldet das Verschieben selbst (`mail` in der Antwort von `POST …/ordner/<fid>/verschieben`). Mails
  bleiben je Ordner (nicht gebündelt). Test `test_n5_verschieben` (Fall 2b der Ablaufprüfung und der umgekehrte Fall).
- „Bitte bestätigen“ N5 der Freigabeliste: **entschieden** (Mail gewünscht, gebaut).
- Nachbesserung nach der Sicherheitsprüfung (26.10.2026, Befund 1): Welche Ordner ohne Verwalter sind, wird erst unter
  der Schreibsperre gerechnet – zwei gleichzeitige Entzüge konnten sonst den Vermerk des anderen löschen, und der
  nächste Lauf meldete denselben Wegfall ein zweites Mal. Test `test_n5_wettlauf` (wie p30 Teil 3; ohne die Änderung
  rot).

### W2 – Lebensende nie hinter den Produktwert (keine Änderung)
Geprüft, dass kein Weg ein Lebensende hinter die Rechnung aus Herstellung + Lebensdauer setzt: Anlegen
(`bestand.artikel_werte`: ein späteres Datum ist ein Fehler, ein früheres gilt als vorgezogen), „Bearbeiten“ (nur
vorziehen, auch ein vorgezogenes nicht wieder nach hinten), Antrag (höchstens bis zur Rechnung), Bestandsimport (ein
späteres Datum laut Liste wird nicht übernommen, Hinweis „es gilt …“), Lebensdauer am Produkt geändert
(`katalog.lebensende_nachziehen`: ein vorgezogenes Datum gilt nur, solange es früher liegt). **Entscheidung des Nutzers:
so lassen.**

### Schemaschritt 29
Neue Tabelle `mat_antrag_ohne_verwalter` (folder_id Primärschlüssel, ON DELETE CASCADE; gemeldet_at). Rein additiv,
wiederholbar (IF NOT EXISTS), frisch = migriert (Test). Rückweg: ein älterer Stand ignoriert die Tabelle.

### Tests
`tests/test_material_a4_n5.py`: Zählung je Recht und Gliederung (Materialwart je Gliederung, Prüfer und Leser nichts,
Material-Verwaltung alles), Filter mit Zahl und Kategorie, nach dem Aussondern weg; N5 mit allen vier Auslösern,
Einmaligkeit, erneute Meldung nach neuem Wegfall, keine Mail ohne offenen Antrag, nur an die Material-Verwaltung, kein
Antragsinhalt, Antrag ohne Zuständige zählt als Meldung; Schritt 29; Oberfläche statisch.

## Nachbesserung nach der Browserprüfung des Endstands 5de5e56 (25.10.2026)

- **B1:** Die Marke „Aussonderung empfohlen“ bricht in der Kartenansicht um (`white-space: normal`, höchstens so breit
  wie die Zelle) – bei 344 px ragte sie 3 px über die Karte.
- **B2:** Die Marke steht jetzt auch in der Artikelliste eines Durchgangs. Übrige Artikellisten (Ordner, „Gesperrt“,
  „Zu prüfen“, Übersicht „Als Nächstes“, Suchtreffer) nutzen dieselbe Tabelle und zeigen sie, sobald ein Artikel mit
  Empfehlung darin steht.
- **Artikelseite:** Der Grund einer Empfehlung steht nur noch im Hinweis „Aussonderung empfohlen – …“; hat die
  Empfehlung selbst gesperrt, sagt der Banner nur „GESPERRT – Aussonderung empfohlen. Nicht verwenden, …“ (eine Sperre
  aus anderem Grund nennt ihn weiter). Die Marke bleibt. Der Satz, warum „Aussondern“ ausgegraut ist, steht direkt
  über der Knopfzeile (der Prüfhinweis davor).
- **Designsprache in der Prüfung:** Die Statuszeile der Abschlussleiste (`#pr-hinweis`: fehlende Befunde, Fotos, was
  das Ergebnis bewirkt) steht über den Ergebnisknöpfen statt unter „Festschreiben“; Inhalt, `aria-live` unverändert,
  Ergebnisgruppe und „Festschreiben“ verweisen mit `aria-describedby` darauf. Damit ist das „Bitte bestätigen“ dazu
  aus der Designsprache-Nachbesserung erledigt.
- **PDF:** Zwischenzeilen der Sammel- und Set-Protokolle trennen keine Wörter mehr (`hyphens: manual`) – der Pfad bricht
  an Leerzeichen, › oder einem Bindestrich im Namen („DEMO-|Flaschenzugtasche“), nicht mehr als „Flaschenzugta-sche“.
- Unverändert (Wunsch bzw. Entscheidung offen): Umschalter der Ergebnisknöpfe, volle Breite der Hilfetexte, Bemerkung im
  Aussondern-Dialog, kein neuer Filter und keine Kachel.
- Browserprobe 1280/360/344 (Beispielbestand 40 Artikel, zwei Empfehlungen im offenen Durchgang): Marken ohne Überhang
  in „Gesperrt“ und im Durchgang, Banner/Hinweis wie oben, Statuszeile über den Knöpfen, kein waagerechter Bildlauf,
  keine Konsolenfehler; Sammelprotokoll PDF/A-3b. Statischer Test in `test_material_aussondern`.

## Designsprache: keine Erklärzeilen unter Knöpfen; Texte zur Lebensdauer (25.10.2026)

Entscheidung des Nutzers zu „Bitte bestätigen“ 5 von „Aussondern nur durch den Materialwart“: „an die Designsprache
anpassen“ (designsprache.md: keine Erklärtexte unter Knöpfen – Hilfe gehört an Felder oder in einen Satz über dem
Abschnitt). Dazu A1 und zwei Verbesserungen der Ablaufprüfung zu b7abddf.

- **Sätze über der Knopfzeile statt darunter** (die Knöpfe bleiben ausgegraut, `aria-describedby` zeigt auf den Satz):
  - Artikelseite: warum „Aussondern“ gerade nicht geht (Text vom Server, `artikel.aussondern.grund`) und „Du hast am …
    schon gemeldet …“ am ausgegrauten „Mangel melden …“; ebenso der Satz, warum „Prüfen“ fehlt („Prüfen dürfen Prüfer
    …“ bzw. der Hinweis zur Prüffreigabe) und – nur am Finger – die Erklärung zu „Lebenslauf (PDF)“.
  - „Meine PSA“: „Du hast schon gemeldet …“ am ausgegrauten „Mangel melden …“ der Karte.
  - Artikel anlegen: die Erklärung zu „Anlegen und nächsten“ (nur am Finger).
  - Bestandsimport: der Satz zur Frist der Nacharbeit über „Neu wählen“ | „Übernehmen“.
  Geprüft und nicht geändert (stehen über oder neben dem, was sie erklären): Hilfetexte an Feldern, Einleitungssätze
  von Abschnitten (Formularseite, Katalog, Prüfungen), Hinweise in Dialogen über den Knöpfen. Offen gelassen: die
  Statuszeile der Abschlussleiste in der Prüfung (`#pr-hinweis`, unter Ergebnis und „Festschreiben“) – sie meldet den
  Stand der Prüfung (fehlende Befunde, Fotos, was das Ergebnis bewirkt), keine Bedienhilfe – seit der Nachbesserung
  nach der Browserprüfung des Endstands steht auch sie über den Knöpfen.
- **Texte bei erreichter Lebensdauer (A1):** Erinnerungsmail „Lebensdauer erreicht seit … – prüfen lassen („aussondern
  empfohlen“), danach sondert der Materialwart aus“; Banner nach QR-Scan und auf der Artikelseite „LEBENSDAUER
  ERREICHT – … nicht mehr verwenden, prüfen lassen und aussondern.“; Bestandsimport (Hinweis je Zeile und Satz im
  Bericht) entsprechend. Kein Verhalten geändert.
- **Etiketten:** Aussonderungen heißen in `Verzeichnis.csv` und in der Prüfungsliste des Jahresberichts (CSV)
  „ausgesondert“ – „aussondern (ausgesondert)“ bleibt das Etikett alter Prüfungen. Die Ergebnisübersicht des
  Jahresberichts zeigt die Zeile „aussondern (ausgesondert)“ nur, wenn es solche Prüfungen im Jahr gibt.
- Die Lücken in den T-Nummern bei verworfenen Abschlüssen bleiben (N1, dokumentiert).
- **Browserprobe 1280/360** (60er-Beispielbestand auf Schema 28): Satz über „Mangel melden …“ | „Aussondern“ (ausgegraut,
  `aria-describedby` passt), kein waagerechter Bildlauf, keine Konsolenfehler. Die offene Beobachtung aus der vorigen
  Probe („aussondern empfohlen“ bei 360 px nach dem Skript-Klick nicht gedrückt) war kein Fehler: Das Ergebnis schaltet
  bei einem zweiten Klick wieder ab, und die Probe hatte den Zustand aus dem 1280-Durchgang (sessionStorage) übernommen
  – mit frischem Zustand stellen Skript-Klick und echter Tipp (Touch-Ereignis) es bei 1280 und 360 ein, der Hinweis
  der Abschlussleiste erscheint.
- Tests: statischer Test der Reihenfolge (Satz vor Knopfzeile) in `test_material_aussondern`; Texte in
  `test_material_erinnerung`; Etiketten in `test_material_export` und `test_material_bericht`.

## Zusammenführung: Beispielbestand (demo-formulare, 581aa38) in l2c-rest (25.10.2026)

Merge des Zweigs demo-formulare (großer Beispielbestand 4031ad2, Entfernen von `scripts/material_demo.py` und
`scripts/beispieldaten.py` 7da1bec, befaf58, „Neue Version“ eines DEMO-Formulars bleibt DEMO 7406f75, Nachbesserung
581aa38 – Abschnitte weiter unten) in den Stand mit Rückbau der Set-Funktion, Set-Protokollen (Schritt 26/27) und
„Aussondern nur durch den Materialwart“ (Schritt 28).

- `material_demo.py` und `beispieldaten.py` bleiben gelöscht. Was der Rückbau dort ergänzt hatte, deckt der
  Beispielbestand ab: Set-Ordner mit einem Set im Set (DEMO-Flaschenzugtasche im DEMO-Seilrucksack 1) – die
  Jahresprüfungen der Fahrzeuge bekommen so Set-Protokolle, auch verschachtelt. Die DEMO-Rettungsweste mit
  Bestandteil-Liste entfällt mit dem kleinen DEMO-Katalog.
- **Beispielbestand auf Schema 28 und die neuen Regeln:** keine Set-Funktion (nur Ordner der Art „Set“). Aussonderungen
  laufen nach einem kritischen Mangel oder dem Lebensende über „aussondern empfohlen“ (sperrt) und danach durch den
  Materialwart (`pruefung.aussondern`, Grund irreparabel bzw. Lebensdauer, am selben Tag der Uhr); nach Verlust sondert
  der Materialwart direkt aus. `sicherstellen` erkennt die beiden Wege daran statt an `basis_inspection_id`.
  Änderungsanträge sind Sammelanträge (Schritt 23): `stellen` liefert die Antrag-Nr., bestätigen und ablehnen der
  Materialwart des Ordners (bisher die Material-Verwaltung, die ohne Freigabe seit Schritt 23 nicht mehr entscheidet).
- **Produkte mit Bestandteil-Liste** (Schritt 25) bleiben ausgelassen – wie bisher die Set-Produkte; der Bericht nennt
  sie („mit Bestandteil-Liste“). Sie mit ihren „… vorhanden“-Zeilen zu prüfen, ginge, ist aber nicht gebaut (Mängel
  würden dann auch auf Bestandteil-Zeilen fallen).
- **Restrisiko 1 der Sicherheits-Nachprüfung zu 581aa38:** Die Ausnahme für localhost ohne dev-Kennung gilt nur
  außerhalb des Containers (`DATA_DIR` nicht `/data`) – im Produktionscontainer ließe sie sich sonst mit
  `BASE_URL=http://localhost:8080` erzwingen. Test in `test_ohne_schalter`; README.
- Alle Befunde der Prüfungen des Beispielbestands (S1–S6, A1–A7) bleiben behoben – die Nachbesserung 581aa38 ist
  unverändert übernommen, nur die Stellen oben sind angepasst.
- Tests: `test_material_beispielbestand` (Aussonderungen nur durch den Materialwart, kein Prüfergebnis „aussondern“,
  keine `basis_inspection_id`; Containersperre), `test_material_dev_zuruecksetzen` ohne das Set aus der alten
  Set-Funktion, `test_material_beschreibung` ohne den Test des DEMO-Skripts (Stand von l2c-rest, sonst unverändert),
  `test_material_sets.py` bleibt gelöscht.
- **Probe:** `--artikel 60` gegen die Teile 01, 21, 32, 46, 54, 55 der aktuellen Serie (Gurte, Karabiner, Seile,
  Seilklemmen, Seilrollen, Textilmaterial, Flaschenzüge; 13 Produkte mit Bestandteil-Liste – alle ausgelassen):
  rc 0, 1:57 min, keine Hinweise; 63 Artikel aus 32 Produkten (3 Nachkäufe), 139 Prüfungen mit Protokoll, davon 2
  „aussondern empfohlen“, 3 Aussonderungen durch den Materialwart (2 irreparabel, 1 Verlust), 18 Durchgänge mit
  Sammelprotokoll und 10 Set-Protokolle (PDF/A-3b), 1 Durchgang offen; Anträge 2 bestätigt, 2 abgelehnt, 1
  zurückgezogen, 1 offen. Laufzeit bei 800 Artikeln geschätzt rund 30–35 min (bisher 27:34 min, dazu jetzt die
  Set-Protokolle der Fahrzeug- und Bereichsdurchgänge).

## Aussondern nur durch den Materialwart (Wunsch des Nutzers, 25.10.2026)

Wunsch des Nutzers (wörtlich): „Prüfer sollen nicht aussondern können, sondern nur sperren. Materialwart kann aussondern,
nachdem eine Prüfung eine Sperre hervorgebracht hat (Mangelmeldungen oder Verlust bleiben wie gehabt)“. Entscheidungen
vom 25.10.2026: E1 „aussondern empfohlen“ sperrt nur, E2 Bedingungen des Materialwarts, E3 in L2c. **Schemaschritt 28.**

### Verhalten

- **Prüfergebnis „aussondern empfohlen“** (statt „aussondern“): sperrt wie „instandsetzen“ (Ordner „Gesperrt“, Herkunft
  gemerkt, Sperrgrund „Prüfung vom …: aussondern empfohlen – <Grund>“); ohne Mangel braucht es einen Grund. Am schon
  gesperrten Artikel bleibt die Sperre mit ihrem Grund. Das Prüfprotokoll nennt das Ergebnis rot, „nächste Prüfung:
  entfällt – Artikel gesperrt, Aussonderung empfohlen“ und „Der Prüfer empfiehlt, den Artikel auszusondern … aussondern
  kann der Materialwart“. Eine gemeldete Mangelmeldung bleibt offen (wie bei „instandsetzen“); die Aussonderung des
  Materialwarts erledigt sie. Kritischer Mangel und erreichtes Lebensende schließen weiter „einsatzbereit“ aus – wählbar
  sind „instandsetzen“ und „aussondern empfohlen“.
- **„aussondern“ ist kein Prüfergebnis mehr**: Die Schnittstelle antwortet 400 „Prüfer sondern nicht mehr aus – bitte
  „aussondern empfohlen“ wählen …“. Die Route `POST …/artikel/<id>/aussondern` bleibt dem Recht „verwalten“ vorbehalten
  (Prüfer ohne es: 403, wie bisher); ein Konto mit beiden Rechten geht denselben Weg wie jeder Materialwart.
- **Materialwart (E2)**: aussondern nur einen gesperrten Artikel, dessen **letzte Prüfung „instandsetzen“ oder
  „aussondern empfohlen“** ergab – die sperrende Prüfung zählt; weil nur eine Freiprüfung einen Artikel freigibt, liegt
  diese Prüfung immer seit der Sperre (`pruefung.aussondern_moeglich`). Nach einer direkten Sperre (Sturz,
  Beschädigung, Rückruf) also erst nach einer Prüfung; **verloren gemeldet: sofort**; nach einer Mangelmeldung wie bisher
  erst nach einer Prüfung seit der Meldung (`mangel.nur_gemeldet`, neuer Text). Meldungen: „Aussondern lassen sich nur
  gesperrte Artikel …“, „Aussondern geht erst, wenn ein Prüfer den Artikel seit der Sperre geprüft hat …“ (409).
  Die Aussonderung trägt keine `basis_inspection_id` (die bleibt Aussonderungen aus einer Prüfung vor Schritt 28 – der
  Jahresbericht zählt sie weiter als „aus Prüfung“); das Journal „ausgesondert“ nennt die Empfehlung (`empfehlung`:
  Kennung der Prüfung, Beschriftung „empfohlen in Prüfung“), das Aussonderungsprotokoll wie bisher die letzte Prüfung mit
  ihrem Ergebnis und die Sperre mit Grund.
- **Oberfläche**: Prüfdialog mit den Knöpfen „einsatzbereit“ | „instandsetzen“ | „aussondern empfohlen“; die Warnung
  „„aussondern“ ist endgültig“ und der rote Bestätigen-Knopf entfallen, stattdessen ein Satz (sperrt, aussondern kann der
  Materialwart). Artikelseite: Hinweis „Aussonderung empfohlen – <Prüfer> am <Tag> (Protokoll …): <Grund>. Aussondern
  kann der Materialwart.“ und die Marke „Aussonderung empfohlen“ neben dem Status; dieselbe Marke in allen Artikellisten
  (Ordner, „Gesperrt“, Durchgang …). „Aussondern“ ist ausgegraut, solange der Server es nicht erlaubt – darunter steht
  der Grund (`artikel.aussondern` {ok, grund}; bisher nur bei einer reinen Mangelsperre). Dialog „Aussondern“ mit der
  Empfehlung und vorbelegtem Grund (verloren → Verlust, Lebensende erreicht → Lebensdauer, sonst irreparabel).
- **Überall, wo Ergebnisse stehen**: Sammel- und Set-Protokolle („davon aussondern empfohlen“; „davon ausgesondert“ nur
  noch, wenn ein Altbestand-Ergebnis darin steht), Lebenslauf, Jahresbericht (Ergebnisse und Sperrart „aus Prüfung
  (instandsetzen, aussondern empfohlen)“), CSV-Exporte, Journal-Beschriftungen (beschriftung.py und material.js).
- **Altbestand**: Prüfungen mit „aussondern“ (vor Schritt 28 zugleich die Aussonderung) bleiben unverändert und heißen
  „aussondern (ausgesondert)“; sie lassen sich wie bisher nicht berichtigen. Keine Mail ändert sich (eine Sperre aus einer
  Prüfung verschickt keine).

### Schemaschritt 28

- `mat_inspection.result` kennt „aussondern_empfohlen“. SQLite ändert einen CHECK nur mit einer neuen Tabelle:
  mat_inspection wird einmal aus ihrer gespeicherten Fassung neu aufgebaut (nur der CHECK ändert sich), alle Zeilen,
  Kennungen und der Zähler bleiben. Alle Trigger an mat_inspection und alle Trigger anderer Tabellen, die sie nennen,
  sowie ihre Indizes werden vorher in ihrer **genauen gespeicherten Fassung** gelesen und danach unverändert neu angelegt –
  der Schutz festgeschriebener Prüfungen bleibt Wort für Wort. Schritt 1, 2 und 21 behalten ihre Werteliste
  (`ERGEBNISSE_1`), frisch = migriert. Wiederholbar (umgebaut nur, wenn der CHECK den Wert noch nicht kennt).
- **Rückweg**: Ein älterer Stand liest die Tabelle weiter, kennt den Wert aber nicht (Prüfungen mit „aussondern empfohlen“
  ohne Ergebnistext, die alte Regel des Materialwarts gälte wieder) – zurück nur über die Sicherung vor dem Deploy.

### Tests

- Neu `tests/test_material_aussondern.py`: Ergebnis sperrt nur (Sperre, Protokolltext, Marke in „Gesperrt“, kein
  Aussondern durch Prüfer per Ergebnis 400 und Route 403, Journal mit Empfehlung); Bedingungen je Sperrart (frei,
  Sturz/Beschädigung/Rückruf, Verlust, Mangelmeldung, Freiprüfung mit neuer Sperre, Empfehlung am gesperrten Artikel);
  kritischer Mangel, Lebensende, Berichtigung einer Empfehlung; Durchgang mit Sammelprotokoll; Altbestand „aussondern“;
  Schritt 28 (frisch = migriert, Trigger und Indizes gleich, Schutz wirkt, unbekannter Wert abgewiesen, zweiter Lauf);
  Oberfläche statisch. Bestehende Tests auf die neue Regel umgestellt (siehe Commit).

### Bitte bestätigen

1. Die Prüfung, die den Materialwart freischaltet, ist die **letzte** Prüfung des Artikels: Eine spätere Prüfung mit
   „instandsetzen“ ersetzt eine frühere Empfehlung (Marke und Hinweis verschwinden), das Aussondern bleibt erlaubt.
2. Altbestand auf der Produktion: Wer heute **direkt** (Sturz, Beschädigung, Rückruf) gesperrt ist und noch keine
   Prüfung danach hat, lässt sich erst nach einer Prüfung aussondern – auch wenn die Sperre vor dem Deploy entstand.
3. Grund im Dialog vorbelegt (verloren → Verlust, Lebensende → Lebensdauer, sonst irreparabel) – oder lieber ohne
   Vorbelegung?
4. Filter „Aussonderung empfohlen“ für Materialwarte: nicht gebaut – die Marke steht in der Liste „Gesperrt“ jeder
   Gliederung, die ohnehin der Arbeitsvorrat des Materialwarts ist. Ein eigener Eintrag im Filtermenü (Status) oder eine
   Zahl auf der Übersicht wäre der nächste Schritt – gewünscht?
5. Der ausgegraute Knopf „Aussondern“ behält seine Hilfezeile darunter (wie bisher bei der Mangelsperre), obwohl die
   Designsprache Erklärtexte unter Knöpfen meidet – sonst stünde ein toter Knopf ohne Grund da.

Stand der Punkte (Feinschliff aus den Wiki-Fragen, 26.10.2026): 1–3 gelten wie gebaut (Freigabeliste L2c A1–A3, ohne
Antwort gilt der Vorschlag – der Grund bleibt vorbelegt); 4 gebaut mit A4, Schema 29 (Filter „Aussonderung empfohlen“
und Übersichtszahl); 5 entschieden am 25.10.2026 – „an die Designsprache anpassen“ (siehe „Designsprache: keine
Erklärzeilen unter Knöpfen“).

## Nachbesserung Set-Rückbau und Set-Protokolle nach den Prüfungen (25.10.2026)

Grundlage: Berichte der Prüfer Ablauf, Sicherheit und Browser zu e951633 (`planung/material-phase4/
bericht_pruefung_set_rueckbau_l2c_*.md`) und die Entscheidungen des Nutzers vom 25.10.2026. Kein neuer Schemaschritt.

### Abschluss ohne lange Schreibsperre (Ablauf B2 = Sicherheit 1, Entscheidung „PDFs vorher erzeugen“)

- Bisher entstanden alle Set-Protokolle und das Sammelprotokoll **unter der Schreibsperre** der gemeinsamen Datenbank.
  Mit vielen Sets dauerte das länger, als jede andere schreibende Anfrage der Plattform wartet (15 s, `app/db.py`) – die
  scheiterten dann mit 500 (auch Anmeldungen).
- Jetzt **zweistufig** (`durchgang._beenden`, `protokoll.durchgang_vorbereiten` / `durchgang_rendern` /
  `durchgang_festschreiben`): Daten in einem Lesestand ohne Sperre lesen (WAL) → alle PDFs **ohne Sperre** rendern, unter
  Zwischennamen neben ihrem Ziel (`pdf/<jahr>/.<ID>.<zufall>.teil`) → kurze Schreibtransaktion (BEGIN IMMEDIATE): die
  üblichen Prüfungen (offen, Entwürfe), schließen, **alle Protokolldaten noch einmal ausrechnen** und mit den gerenderten
  vergleichen (Nummern, Artikel, Ordnerpfade, Prüfer, Ausnahmen, Seriennummern …). Gleich → die Dateien kommen per hartem
  Link unter ihren endgültigen Namen (nie überschreibend), Zeilen und Journal wie bisher. Anders → verwerfen
  (Zwischendateien weg) und neu, höchstens 3 Versuche; danach 409 „Während des Festschreibens wurde am Durchgang
  weitergearbeitet … oder gleichzeitig ein anderer Durchgang abgeschlossen … Bitte noch einmal versuchen.“ – nie 500. Kann die Datenbank trotzdem nicht
  gesperrt werden, 503 mit Meldung. Für Prüfer und Materialwart ändert sich nichts: Der Abschluss wartet wie bisher.
  Der Abbruch geht denselben Weg (nur das Sammelprotokoll).
- Nummernvergabe, Festschreiben, `verwaiste_beiseite` und Unveränderlichkeit bleiben, wie sie waren: Endgültige Namen
  entstehen nur unter der Sperre; Zwischennamen sind keine Protokolldateien (kein `.pdf`, heben den Zähler nicht).
  Bricht der Prozess beim Rendern ab, bleiben nur Zwischendateien liegen – der nächste Start löscht sie, wenn sie älter
  als ein Tag sind (jüngere können zu einem Abschluss in einem anderen Arbeitsprozess gehören).
- Das Protokoll der App nennt je Abschluss die Renderzeit und die Dauer der Schreibsperre.
- **Gemessen** (Probe der Sicherheitsprüfung p05 wiederholt: 15 Fahrzeuge × äußeres Set mit 2 inneren Sets = 45 Sets,
  450 Artikel, Server mit Threads, nebenher alle 0,5 s eine Anmeldung):

  | Last | Abschluss gesamt | davon Schreibsperre | Anmeldungen nebenher |
  |---|---|---|---|
  | unbelastet (4 Kerne) | 33,4 s | **0,15 s** | 51, alle 200, keine über 2 s |
  | Last ≈ 12 (10 Rechenschleifen) | 111,3 s | **0,56 s** | 109, alle 200, keine über 2 s |

  Vorher hielt derselbe Abschluss die Sperre 32,3 s bzw. 64,4 s (Bericht Sicherheit). Zwei gleichzeitige Abschlüsse in
  zwei Gliederungen (p07, je 12 Sets): beide 200, der zweite verwarf einmal (die T-Nummern hatte der erste vergeben –
  behoben mit N1, siehe unten), T-…001–012 und 013–024, keine Dopplung. Abbruch mitten im Rendern (SIGKILL nach 12 s): 17 Zwischendateien, kein `.pdf`,
  nichts in `pdf/verwaist/`; der erneute Abschluss vergibt T-…000001 (keine Lücke – Stand vor N1, siehe unten).
- **Nachtrag N1 (Nachprüfung der Sicherheit zu cf52a49)**: Gleichzeitige Abschlüsse *verschiedener* Durchgänge
  verwarfen sich gegenseitig, weil der gemeinsame Zähler der T-Nummern zum Vergleich gehörte (vier Gliederungen
  gleichzeitig → der vierte 409 mit der unpassenden Meldung). Jetzt reserviert jeder Abschluss seine T-Nummern **vor dem
  Rendern** in einer eigenen kurzen Schreibtransaktion (`protokoll.t_nummern_reservieren`, hebt `sqlite_sequence`);
  unter der Sperre wird mit denselben Nummern verglichen. Ein verworfener Versuch und ein Abbruch des Prozesses lassen
  seine reservierten Nummern als Lücke zurück – wie verworfene Entwürfe (Kopf von protokoll.py). Die 409-Meldung nennt
  auch den gleichzeitigen Abschluss. Probe p07 mit vier Gliederungen à 6 Sets (`p05_aufbau … 6 0 5 4`): alle vier 200 im
  ersten Versuch, T-…001–024 ohne Dopplung, Sperre je 0,01–0,07 s; Test `test_gleichzeitige_abschluesse` (vier Threads).

### Zwischenzeilen im Sammel- und Set-Protokoll (Ablauf B1 = Browser 1)

- Verglichen wird die **ganze Kette der Sets** auf dem Weg jeder Zeile unterhalb des Durchgangs- bzw. Set-Ordners, nicht
  nur das innerste Set (`protokoll._zwischenzeilen`): beim Eintritt je Set eine Zeile, **von außen nach innen** – auch für
  ein Set, das nur innere Sets enthält, mit seiner T-Nummer; beim Rückweg in ein äußeres Set „Set <Pfad> (Fortsetzung)“;
  beim Verlassen aller Sets **„Außerhalb von Sets · <gemeinsamer Ordner der folgenden Zeilen>“** (liegt der
  Durchgangsordner selbst in einem Set: „Außerhalb innerer Sets“). Im Set-Protokoll – und im Durchgang direkt auf einem
  Set – ist das Set selbst die äußerste Ebene („Set <Pfad> (Fortsetzung)“ nach einem inneren Set).
- „n Artikel“ zählt **genau die Zeilen bis zur nächsten Zwischenzeile**; hat das Set mehr (innere Sets, Fortsetzung),
  steht „n Artikel, im ganzen Set m“ bzw. „im ganzen Set m Artikel“ da – m ist die Zahl in seinem Set-Protokoll.
- Tests mit den Proben b3/b4 der Ablaufprüfung und dem Fall aus Browser S-2.png.

### Name „Set-Protokoll“ (Entscheidung des Nutzers)

- PDF-Titel und Fuß „Set-Protokoll T-…“, Prüfseite „Set-Protokoll“, Ordnerseite „Set-Protokolle“ (bzw. „Sammelprotokolle“
  oder „Set- und Sammelprotokolle“), Ordner-Export im ZIP-Ordner `Set-Protokolle/<jahr>/` (bisher `Sammelprotokolle/`),
  Verzeichnis „Art“ = „Set-Protokoll“, Text im Export-Menü, Prüfseite nennt Set-Protokolle. Die Nummer bleibt T-…; das
  Protokoll des Durchgangs bleibt „Sammelprotokoll“. Bereits festgeschriebene T-PDFs (nur dev) behalten ihren Titel.

### Kleinkram

- Durchgangsseite offen: „… ein eigenes Set-Protokoll (hier bis zu n; Sets mit Geprüftem bisher: m)“ statt „(hier n
  Sets)“.
- Abbruch-Rückfrage: „Set-Protokolle entstehen dabei keine – nur beim Abschließen.“ (wenn Sets im Durchgang sind);
  Knöpfe **„Zurück“ | „Durchgang abbrechen“** statt „Abbrechen“ | „Durchgang abbrechen“ (`S.confirm` hat dafür einen
  dritten Parameter).
- „PDF“-Links der Set-Protokolle (Durchgangs- und Ordnerseite) und der Durchgangsliste mit eigenem zugänglichem Namen
  („Set-Protokoll T-… (PDF)“).
- ZIP- und CSV-Downloads des Exports: ASCII-Ersatzname mit „ue“ statt verlorenem „ü“
  (`filename="Protokolle_DEMO-Jahrespruefung 2026_S-….zip"`, `filename*` wie bisher).
- `Verzeichnis.csv`: neue Spalte **„Set“** (hinter „Prüfdurchgang“) mit dem Pfad des Sets; „Grund“ bleibt bei
  Set-Protokollen leer (bisher „Set … (n Artikel)“ dort).
- Prüfsummen-Knopf: Die gestrichelte Linie sitzt am Text, nicht am 44 px hohen Knopf – am Finger schwebte sie unter der
  Zeile.
- Produktdialog am Telefon, „weißer Streifen am rechten Rand“: nachgemessen (Chromium, 360 px, Reiter „Bestandteile“
  ganz unten) – kein Element ragt aus dem Dialog (Reiter 28–332 px im Dialog 8–352 px); der Streifen ist die
  eingeblendete Bildlaufleiste des rollenden Dialoginhalts (oben weiß, darunter der graue Schieber). Keine Änderung.
- README: Set-Reste in „Bestand“ entfernt („nie an Sets und Teilen … Set-Produkt“, „Set-Meldungen“), Protokoll-IDs mit
  `T-`; Tippfehler „einzelner Stücke“ im Reiter „Bestandteile“.
- Unverändert (Wunsch des Nutzers): Hinweis- und Hilfetexte über die volle Inhaltsbreite.

### Nur auf dev (Ablauf B3)

- Der Jahresbericht eines Jahres mit Set-Altbestand (nur dev, Produktion hatte nie Sets) ordnet alte Set-Sperren nach dem
  allgemeinen Schlüssel ein: „aus ausgesondertem Set entnommen“ erscheint als „aus Prüfung (instandsetzen)“, jede
  Mitsperre einer Kaskade als eigene „Sperre durch Prüfer ohne Prüfung“. Bewusst keine eigene Lese-Art.

### Tests

- `tests/test_material_setprotokolle.py`: neu `test_zwischenzeilen` (b3/b4, S-2, Set-Protokoll des äußeren Sets, Durchgang
  direkt auf einem Set, PDF-Text), `test_abschluss_zweistufig` (eine andere Verbindung schreibt während des Renderns ohne
  zu warten; Änderung zwischen Rendern und Festschreiben → neu gerendert, seit N1 mit neuen Nummern; keine
  Zwischendatei, Rechte 0444; jedes Mal geändert → 409 nach 3 Versuchen, nichts festgeschrieben; Abbruch;
  `verwaiste_beiseite` löscht nur alte Zwischendateien und hebt den Zähler nicht), `test_dateiname_ascii`,
  `test_gleichzeitige_abschluesse` (N1); angepasst: Prüfseite „Set-Protokoll“, Verzeichnis mit Spalte „Set“, ZIP-Ordner
  `Set-Protokolle/`, Oberfläche statisch.

## Texte über die volle Breite (Wunsch des Nutzers, 25.10.2026)

Wunsch des Nutzers (mit Bildschirmfoto der Seite „Prüfformular“): „Die Texte gehen nicht über die vorgesehene Breite“.
Hinweiskästen (`.notice`) und Hilfe- bzw. Erklärtexte (`.help`, `.muted`, `p.small`, `p.mat-text`) im Modul Material
haben keine eigene Höchstbreite mehr (bisher 38em bzw. 38rem, `--mat-kastenmass` entfällt) – auf allen Seiten des
Moduls laufen sie so breit wie die Felder und Tabellen ihres Abschnitts; nur die Stammdatenwerte (`.mat-daten dd`)
bleiben lesbar schmal. Der Fließtext im Wiki behält seine Lesebreite. Browserprobe 1280/1920/360 auf Prüfformular,
Produktseite, Ordnerseite und Übersicht ohne waagerechten Bildlauf; statischer Test `tests/test_material_textbreite.py`.

## Set-Protokolle im Prüfdurchgang (Wunsch des Nutzers, 25.10.2026)

Teil des Wunsches zum Rückbau der Set-Funktion: „Implementiere dafür, dass wenn ein Prüfdurchgang einer Gliederung oder
allgemein eines Ordners Unterordner, die ein Set sind, enthält, diese ein eigenes PDF für den Prüfdurchgang erhalten, wie
bei einem Prüfdurchgang, der nur für diesen Set-Ordner angelegt wurde.“ Grundlage: `entwurf_set_rueckbau.md` Abschnitt 3.5
mit den Entscheidungen F1 b, F2 b, F3 a, F4 a, F5 a. **Schemaschritt 27.**

### Neu

- **Sammelprotokoll (S-…)**: weiter alle Artikel des Durchgangs. Die Artikel eines Ordners der Art „Set“ stehen jetzt
  sicher zusammen (sortiert wird nach der Folge der Ordner statt nach dem Pfadtext; auf jeder Ebene erst die Artikel,
  dann Unterordner, dann Sets) unter **Zwischenzeilen** „Set <Pfad> · n Artikel · Set-Protokoll T-…“ (sonst „kein
  Set-Protokoll (nichts geprüft)“ bzw. „(Durchgang abgebrochen)“) und mit einer Kennlinie in der Nummernspalte – seit der
  Nachbesserung vom 25.10.2026 nach der ganzen Kette der Sets (je Set von außen nach innen, „(Fortsetzung)“ beim Rückweg,
  „Außerhalb von Sets · <Ordner>“ danach; siehe „Nachbesserung Set-Rückbau und Set-Protokolle“). Neuer Abschnitt **„Set-Protokolle dieses Durchgangs“** hinter dem Verzeichnis der
  Einzelprotokolle: Protokoll-ID, Set, Artikel, SHA-256 der Datei.
- **Set-Protokoll (T-<jahr>-<nr>)** je Ordner der Art „Set“ **unterhalb** des Durchgangsordners – „wie ein Durchgang nur
  für diesen Ordner“: Kopf mit Durchgang, Gliederung, eröffnet, abgeschlossen, **Set** (Pfad) und **„Teil von
  Sammelprotokoll S-… (Ordner …)“**; Ergebnisübersicht und **„Prüfer in diesem Set“** (mit Urkunde und Unterschrift) nur
  über seine Artikel; Artikelliste mit eigener Nummerierung; Verzeichnis der Einzelprotokolle dieses Sets. PDF/A-3b,
  festgeschrieben mit eigener Prüfsumme und Stempel wie jedes Protokoll.
  - **F1 b – alles darunter**: Ein Set-Protokoll enthält alle Artikel unterhalb des Set-Ordners, auch die innerer Sets (die
    stehen zusätzlich im Protokoll des inneren Sets). Zugehörigkeit nach der Heimat beim Festschreiben (Gesperrte bei
    ihrem Herkunftsordner); Artikel „aus dem Bereich verschoben“ in keinem Set-Protokoll. Ist der Durchgangsordner selbst
    ein Set, ist das Sammelprotokoll „sein“ Protokoll – nur innere Sets bekommen eins; ein umgebendes Set nicht.
  - **F2 b**: nur beim **regulären Abschluss** und nur, wenn im Set **mindestens ein Artikel geprüft** wurde – nicht beim
    Abbruch, nicht bei „alles ausgenommen“.
  - **F3 a**: eigene laufende Nummer mit Buchstaben T (Kennung der neuen Tabelle, AUTOINCREMENT).
- Festgeschrieben in **derselben Transaktion** wie das Sammelprotokoll (erst alle Nummern, dann die Set-Protokolle, dann
  das Sammelprotokoll mit ihren Prüfsummen). Scheitert eines, wird nichts festgeschrieben und keine neue Datei bleibt
  liegen. Berichtigungen nach dem Abschluss ändern weder Sammel- noch Set-Protokoll (wie bisher). Journal am Durchgang
  „festgeschrieben“ mit `set_protokolle` [{protocol_id, folder_id, file_sha256}]. ~~Rechenzeit gemessen: 20 Sets à 10
  Artikel schreiben in 12,9 s fest (unter der Schreibsperre) – unter der Grenze von 30 s aus dem Entwurf.~~ Überholt: Die
  Grenze sind die 15 s, die jede andere Anfrage auf die Sperre wartet; seit der Nachbesserung entstehen die PDFs vor der
  Schreibtransaktion (siehe unten).
- **Oberfläche**: Durchgangsseite offen – der Satz über der Liste nennt die Zahl der Sets, die Rückfrage beim Abschließen
  „… und n Set-Protokolle werden festgeschrieben“, der Toast „Durchgang abgeschlossen – Sammelprotokoll S-… und n
  Set-Protokolle“. Geschlossen – neben „Sammelprotokoll (PDF)“ der graue Knopf **„Alle Protokolle (ZIP)“** und der
  Abschnitt **„Set-Protokolle“** (Pfad des Sets als Link, wenn das Konto den Ordner sieht; Artikel; ID; „PDF“).
  **Ordnerseite eines Sets**: Abschnitt **„Set-Protokolle“** (bzw. „Sammelprotokolle“ oder „Set- und
  Sammelprotokolle“, je nachdem, was darin steht – bis zur Nachbesserung immer „Sammelprotokolle“) unter der Artikelliste (Set-Protokolle dieses Ordners und
  Sammelprotokolle der Durchgänge, die für ihn eröffnet wurden; neueste zuerst, höchstens 20).
- **Rechte (F4 a)**: Ein Set-Protokoll öffnet, wer den Durchgang sehen darf (Leserecht am Durchgangsordner) **und
  zusätzlich, wer den Set-Ordner lesen darf**; das Sammelprotokoll und das ZIP nur, wer den Durchgang sieht. Fremdes und
  Unbekanntes 404, ohne Modulzugang 403.
- **ZIP „Alle Protokolle“ (F5 a)**: Sammelprotokoll, alle Set-Protokolle und `Verzeichnis.csv` (Spalten wie im
  Protokoll-Export des Ordners). Der **Protokoll-Export eines Ordners** nimmt zusätzlich die Set-Protokolle der
  Set-Ordner in seinem Zweig auf (Ordner „Set-Protokolle“, Art „Set-Protokoll“, Spalte „Set“ – seit der Nachbesserung).
- **Prüfseite** erkennt Set-Protokolle („Set-Protokoll“); der Nummernschutz beim Start hebt auch den Zähler der
  Set-Protokolle über die höchste T-Nummer in der Ablage; `verwaiste_beiseite` kennt ihre Dateien.
- **DEMO**: Ein frischer DEMO-Bestand hat im „DEMO-Seilrucksack“ (Set) das innere Set „DEMO-Karabinerbeutel“ mit einem
  DEMO HMS-Karabiner (zum Ausprobieren „verschachtelt“).

### Schemaschritt 27

- Neue Tabelle `mat_round_setprotokoll` (Kennung AUTOINCREMENT = Nummer, round_id, folder_id ohne ON DELETE, ordner –
  Pfad beim Festschreiben –, artikel, protocol_id UNIQUE, locked_at, pdf_path, pdf_sha256, pdf_hashed_bytes, file_sha256,
  UNIQUE (round_id, folder_id)) und Index auf folder_id. Trigger: Einfügen nur an einem geschlossenen, nicht abgebrochenen
  Durchgang, dessen Sammelprotokoll noch nicht festgeschrieben ist (also nur in `durchgang_festschreiben`), kein REPLACE
  über die Kennung, kein UPDATE, kein DELETE. Rein additiv, wiederholbar; frisch = migriert (Test).
- Einen Ordner mit Set-Protokoll löscht man nicht (409 „Für diesen Ordner gibt es Set-Protokolle aus Prüfdurchgängen –
  er bleibt.“).
- **Rückweg**: Ein Stand vor 27 ignoriert die Tabelle; die Set-Protokolldateien lägen dort aber ohne bekannte Zeile und
  wanderten beim nächsten Start nach `pdf/verwaist/` (verwaiste_beiseite des alten Stands). Zurück daher nur über die
  Sicherung vor dem Deploy (wie bei Schritt 26).

### Schnittstelle

| Route | Neu |
|---|---|
| `GET /api/material/durchgaenge/<rid>` | geschlossen: `set_protokolle` [{id, protokoll (wie protokoll_json), ordner, folder_id, ordner_sichtbar, artikel}]; offen (voll): `set_ordner` {anzahl, mit_pruefung} – Sets mit Zeilen bzw. mit Geprüftem, Stand jetzt. Auch die Antwort von `…/abschliessen` und `…/abbrechen` trägt `set_protokolle` |
| `GET /material/durchgang/<rid>/set/<sid>.pdf` | ein Set-Protokoll (angemeldet, Prüfsumme, im Browser; Rechte F4 a) |
| `GET /material/durchgang/<rid>/protokolle.zip` | Sammelprotokoll + Set-Protokolle + Verzeichnis.csv; nur wer den Durchgang sieht |
| `GET /api/material/ordner/<fid>` | an einem Ordner der Art „Set“: `sammelprotokolle` [{art „set“ \| „sammel“, protokoll, durchgang {id, titel, sichtbar}, geschlossen_am}] |
| `GET /material/export/<fid>-protokolle.zip` | dazu die Set-Protokolle der Set-Ordner im Zweig |

### Tests

- Neu `tests/test_material_setprotokolle.py`: Gliederung mit Set A (Tasche, inneres Set B), Set C, Lager › Set D (nur
  ausgenommen), Set E (leer), gesperrter Artikel mit Herkunft A, ein Artikel aus dem Bereich verschoben → 1 S + 3 T,
  Inhalt je PDF (F1 b), Nummern, Haupt-PDF mit Zwischenzeilen, zusammenhängend und Verzeichnis (SHA-256 = file_sha256),
  Journal; Durchgang für Set A → S + T(B); Abbruch → kein T; Fehler beim Rendern → nichts festgeschrieben, keine Datei;
  Schritt 27 (Tabelle, Trigger, 26 → 27, zweiter Lauf); Ordner löschen 409; Prüfseite; Nummernschutz; Rechte je Rolle
  (Leser nur am Set, Leser am Durchgang, fremde Gliederung, ohne Modul); Ordnerseite; ZIP des Durchgangs und
  Ordner-Export; statisch die Oberfläche.

### Bitte bestätigen

1. ~~Titel des Set-Protokolls „Sammelprotokoll“~~ – entschieden (Nutzer, 25.10.2026): überall **„Set-Protokoll“**
   (PDF-Titel und Fuß, Prüfseite, Ordnerseite, ZIP-Ordner, Verzeichnis); das Protokoll des ganzen Durchgangs bleibt
   „Sammelprotokoll“.
2. Die Zwischenzeilen im Sammelprotokoll nennen den vollen Pfad des Sets; seit der Nachbesserung nach der ganzen Kette
   der Sets (siehe dort).
3. Wird ein Set-Ordner später in eine andere Gliederung verschoben, öffnen seine neuen Leser auch seine alten
   Set-Protokolle (F4 a hängt am Ordner, nicht an der Gliederung des Durchgangs). **Folge:** Sie sehen darin auch
   Artikel, Prüfer (Name, Urkundennummer, Unterschrift), „eröffnet/abgeschlossen von“ und die Gliederung der alten
   Gliederung – auch Artikel, die vor dem Verschieben aus dem Set genommen wurden; der Ordner-Export der neuen Gliederung
   nimmt diese Set-Protokolle mit. **Vom Nutzer bestätigt (25.10.2026): „Ja, wie gebaut“.**

## Rückbau der Set-Funktion (Wunsch des Nutzers, 25.10.2026)

Wunsch des Nutzers (25.10.2026), wörtlich: „Ich hab es mir anders überlegt. Entferne die Set Funktion komplett. Entferne
auch die Gerätesätze aus dem Katalogimport. Die Produkte mit Bestandsliste können bleiben und auch vom Katalogverwalter
angelegt werden. Stattdessen werden Sets wie vorher über Unterordner der Kategorie „Set“ angelegt. […] Ich glaube die Set
Funktion würde zu viel Probleme verursachen in der Verwaltung und zu Verwirrungen bei Nutzern führen.“ Grundlage:
`planung/material-phase4/entwurf_set_rueckbau.md` mit den Entscheidungen des Nutzers (F6 a: stilllegen statt umbauen).
Gebaut auf Zweig `l2c-rest` (nach Schritt 25). **Schemaschritt 26.** Die Set-Protokolle im Prüfdurchgang (Schritt 27)
stehen im nächsten Abschnitt.

### Was entfällt

- Set-Produkt („Set anlegen“ im Katalog, Set-Marke in Katalog und Produktsuche), Stückliste mit einzeln geführten Teilen,
  Set-Artikel mit Teilen (Set-Dialog beim Anlegen, „aus dem Bestand wählen“), Kopie der Stückliste je Set und
  „Stückliste übertragen“, „Set prüfen“ (Prüflauf, Prüfumfang, Freigabe, Teiletabelle), die Sperr-Kaskade
  (Sperrursache, Set-Sperre), Teil tauschen/entnehmen/einsetzen/löschen, Set aussondern mit Verbleib je Teil, Set
  auflösen, „Bestandteil ersetzt“, Set-Status, Set-Fälligkeit und die Zählsätze „darunter k Teile in m Sets“ (Übersicht,
  Ordnerbaum, Listen, Fällige, Jahresbericht), Set-Zeilen und -Gruppen in Listen, Suche und Meine PSA, gebündelte
  Set-Zeilen in den Erinnerungsmails, die Set-Sätze in Mangel- und Rückrufmails, die Sperrarten „Set …“ und „aus
  ausgesondertem Set entnommen“ im Jahresbericht, die drei Set-Spalten der Artikel-CSV, die Startprüfung „Sets stimmig“,
  das DEMO-Set („DEMO Verbindungsmittel-Set“ mit Kategorie und Formular) und die Set-Meldung.
- Gelöscht: `services/sets.py`, `setlauf.py`, `setaustausch.py`, `setkopie.py`, `routes_sets.py`, die acht
  `tests/test_material_sets*.py` und `docs/material-katalog-set-vorlage.json` (ersetzt durch
  `docs/material-katalog-bestandteile-vorlage.json` nur mit dem Produkt mit Bestandteil-Liste).
- **„Fehlendes Produkt melden“** meldet nur ein Produkt: keine Wahl „Set“, kein Teile-Feld; an der Meldekarte nur
  „Produkt anlegen“ (ohne Teile-Vorlage). Alte Set-Meldungen zeigen ihre Teile schreibgeschützt als Zeile „Teile laut
  Meldung“; Mails und Bezüge heißen wieder „Produktmeldung“.
- **Katalogimport**: `"set": true` ist ein **Fehler dieses Produkts** – „„set“: true – Sets gibt es nicht mehr. Ein
  Herstellerset steht als Produkt mit Bestandteil-Liste in der Datei („bestandteile“: [{„bezeichnung“, „anzahl“}]);
  zusammengestellte Sätze legst du im Bestand als Ordner der Art „Set“ an.“ (wie jeder Fehler: nichts wird
  gespeichert). `"set": false` wird übergangen. Der Bericht hat keine `stuecklisten` mehr (`bestandteillisten` bleibt),
  der Export schreibt nie `"set"` und kein `set_verstoesse`.

### Was bleibt

- **Bestandteil-Liste** (Schritt 25) an jedem Produkt – nur Text, gepflegt von der Material-Verwaltung im Reiter
  „Bestandteile“ des Produktdialogs –, Seriennummern der Bestandteile, Prüfzeilen „… vorhanden“, Antragsfeld,
  Meine PSA, Lebenslauf. Die Produktantwort trägt `bestandteile` als `[{id, position, bezeichnung, anzahl}]` und
  `stueckliste_grenzen` `{positionen, anzahl, bezeichnung}`; `is_set`, `bestandteil_von` und `sets_aelter` entfallen.
- **Ordnerart „Set“** heißt wieder „Set“ (vom 24.10.2026 bis jetzt „Set-Ordner“).
- Journal-Beschriftungen der Set-Aktionen und -Felder bleiben zum Lesen alter Einträge (beschriftung.py, material.js,
  „Altbestand vor Schritt 26“); die Gruppe „Bestandteile des Sets“ zeigt an alten Prüfungen weiter „vorhanden/fehlt“.
- Festgeschriebene Set-Protokolle (P-Protokolle mit Teiletabelle) bleiben als Datei mit Prüfsumme abrufbar und prüfbar;
  `mat_set_lauf` und `mat_set_protokoll_zeile` bleiben eingefroren in der Datenbank (keine Anzeige mehr).

### Schemaschritt 26 – stilllegen (F6 a)

Schritte 21 und 22 bleiben, wie sie ausgeliefert wurden; Schritt 26 baut zurück (Akteur im Journal „Migration Schritt
26“), in dieser Reihenfolge:
1. Trigger entfernen, die den Umbau blockieren (mat_product_set_umschalten, mat_item_set_produkt, mat_item_teil_neu,
   mat_item_teil_setzen, mat_slot_*; die Fassungen von mat_component_neu/aendern, mat_set_lauf_neu,
   mat_inspection_in_set_lauf und mat_inspection_set_lauf_wechsel werden ersetzt).
2. **Offene Set-Prüfläufe** → „abgebrochen“ (vom Durchgang gelöst, Journal „Set-Prüfung abgebrochen“ am Set-Artikel mit
   Grund „Set-Funktion entfernt (Schritt 26)“); offene Entwürfe darin werden normale Entwürfe (`set_lauf_id` leer).
3. **Teile werden normale Artikel im selben Ordner** (Journal „aus dem Set gelöst“ am Teil, „Set aufgelöst – die Teile
   sind eigene Artikel (Schritt 26)“ am früheren Set-Artikel). Ordner, Herkunft, Zuordnung und Sperre bleiben.
4. **Sperrursachen** (`lock_cause`, `set_lock_origin`, `set_pruefen`) werden leer – ohne Journal, denn sichtbar ändert sich
   nichts: Gesperrte (auch nur mitgesperrte) bleiben gesperrt mit ihrem Grund, bis ein Prüfer frei prüft.
5. **Set-Produkte werden normale Produkte** (`is_set` 0, Journal „geändert“ Set ja → nein): einzeln geführte Positionen
   fallen weg (ihre Teile sind jetzt eigene Artikel), Text-Positionen bleiben die Bestandteil-Liste mit „Austausch“ „nicht
   belegt“ (Journal „Bestandteile geändert“).
6. `mat_item_set_slot` und die Indizes `idx_mat_item_parent`, `idx_mat_component_teil` werden entfernt.
7. Wächter (`TRIGGER_26`, gegen Programmfehler, nicht gegen direktes SQL): kein Produkt mit `is_set`, kein Artikel mit
   `parent_item_id`, Bestandteile nur als Text (einzeln 0, ohne Produkt, Austausch „nicht belegt“), kein neuer
   Set-Prüflauf, keine Prüfung mit `set_lauf_id`.
- Die übrigen Set-Spalten (`is_set`, `parent_item_id`, `lock_cause`, `set_lock_origin`, `set_pruefen`, `set_lauf_id`,
  `mat_product_request.is_set`/`set_teile`) bleiben leer stehen – sie zu entfernen hieße mat_item, mat_inspection,
  mat_product und mat_product_component neu aufbauen (Fremdschlüssel, CHECKs, Trigger, Volltext), ohne sichtbaren Gewinn.
- **Wiederholbar**: jede Änderung nur am Altzustand, Journal nur für Zeilen, die sich ändern; ein zweiter Lauf ändert
  keine Zeile. Frisch (1 → 26) ergibt dasselbe Schema wie 20 → 26 und 25 → 26 (Test).
- **Rückweg**: Ein Code-Stand vor 26 sieht Version 26 und migriert nicht; ohne `mat_item_set_slot` scheitern dort Produkt-
  und Set-Ansichten. Zurück also nur über die Sicherung vor dem Deploy (auf dev legt `flask material dev-zuruecksetzen`
  eine an). Empfehlung für dev: nach dem Deploy ohnehin `dev-zuruecksetzen` (DEMO frisch, danach die Katalogserie).
  Die Produktion hatte nie Sets (Modul Material dort noch nicht ausgeliefert).

### Schnittstelle

- Entfallen (404): `/material/artikel/<iid>/set-pruefung`, `/api/material/artikel/<iid>/set-lauf` (GET/POST/DELETE),
  `…/teil-entnehmen`, `…/teil-tauschen`, `…/teil-einsetzen`, `…/kandidaten`, `/api/material/ordner/<fid>/kandidaten`,
  `…/aufloesen`, `…/bestandteil-ersetzt`, GET/POST `/api/material/produkte/<pid>/stueckliste-uebertragen`.
- Übergangen wie jeder unbekannte Schlüssel (kein 400): `is_set` (POST /produkte, Variante, PUT /produkte, aus Meldung
  anlegen), `teile` (POST /artikel), `is_set`/`set_teile` (POST /meldungen). POST /artikel antwortet ohne `hinweise`.
- `bestandteile` an Produkten ist immer die Bestandteil-Liste: `einzeln`, `produkt`/`produkt_id` und `austausch` außer
  `nicht_belegt` → 400 „Position n: Eine Bestandteil-Liste ist nur Text (Bezeichnung und Anzahl) – …“.
- Entfallene Antwortschlüssel: am Artikel `ist_set`, `set`, `teil_von`, `lock_cause`; in Listen `set`, `teil_von`,
  `sets`, `andere_set_status`; `/start` `bestand_sets`; Ordner `bestand_sets`; Fällige `sets`, `andere_set_status`;
  Prüfung `set_lauf`, Teiletabelle, Verbleib; Durchgangszeile `set_lauf`; Meine PSA `teile`, `teil_eines_sets`;
  Steckbrief `teil_eines_sets`; Rückruf `set_inventar`; Jahresbericht `sets`, `sets_satz`, `set_text`; Meldung `is_set`
  (`set_teile` bleibt, nur Altbestand).

### Vom Entwurf gesetzt – Bitte bestätigen

1. Einzeln geführte Positionen früherer Set-Produkte fallen weg, Text-Positionen bleiben Bestandteil-Liste.
2. Gesperrte (auch nur mitgesperrte) frühere Teile bleiben nach dem Rückbau gesperrt, bis ein Prüfer frei prüft.
3. API-Schlüssel `is_set`, `set_teile`, `teile` werden übergangen (kein 400); nur die Katalogdatei lehnt `"set": true` ab.
4. Alte Set-Meldungen behalten ihre Teile als schreibgeschützte Zeile „Teile laut Meldung“.
5. Die Sperrursachen werden ohne Journaleintrag geleert (nichts Sichtbares ändert sich; Sperre und Grund bleiben).
6. Eine Berichtigung einer alten Prüfung eines Set-Artikels ist eine normale Berichtigung ohne Teiletabelle.

### Tests

- Neu `tests/test_material_set_rueckbau.py`: Migration frisch und 20 → Ende, **25 → 26 mit Set-Altbestand** (Set-Produkt
  mit einzeln geführter und Text-Position, Set-Artikel mit Kopie, drei Teile – frei, mitgesperrt, ausgesondert –,
  abgeschlossener Set-Lauf mit Teiletabelle und festgeschriebenem Protokoll, offener Set-Lauf aus einem Durchgang mit
  offenem Entwurf, Set-Meldung; Prüfseite „unverändert“, Journal je Zeile, zweiter Lauf, Schema = frisch), Trigger 26,
  Schnittstelle, Rechte am Reiter „Bestandteile“, statischer Test „kein Set-Rest“ in app/, scripts/ und tests/.
- Angepasst: test_material_bestandteile, _produktwechsel, _wuensche_2510, _trennung, _meine_psa, _globalsuche,
  _mailprotokoll, _antrag, _antrag_zustaendig, _bericht, _beschreibung, _mangel, _dev_zuruecksetzen.

## Bestandteil-Liste an normalen Produkten (Wunsch des Nutzers, 25.10.2026)

Wunsch des Nutzers (25.10.2026): „Alle Herstellersets sollen zu flachen Artikeln geändert werden mit einer Liste an
Bestandteilen darin. Sets im alten Sinne werden nur noch über die Oberfläche von Hand gestaltet.“ Dazu der Zusatz „In der
Bestandteilliste sollen Seriennummern der Teile eintragbar sein“. Grundlage: Bauentwurf
`planung/material-phase4/entwurf_bestandteile_flach.md` mit den Entscheidungen F1 (a), F2 (Fehler statt Umstellen),
F3 (a), F4 (a) und S1–S3. Gebaut auf Zweig `l2c-rest` (nach Schritt 24). **Schemaschritt 25.** Sets von Hand (Stückliste mit
einzeln geführten Teilen) bleiben unverändert.

### Bestandteil-Liste (Katalog)

- Ein Produkt, das **kein Set** ist, kann eine Liste **„Bestandteile“** haben: je Position Bezeichnung (eine Zeile,
  höchstens 120 Zeichen, je Liste eindeutig ohne Groß/klein) und Anzahl (1–20), höchstens 30 Positionen, leer heißt keine
  Liste. Nur Text – kein „einzeln geführt“, kein Produkt, kein „Austausch laut Hersteller“. Gespeichert in derselben
  Tabelle wie die Stückliste eines Sets (`mat_product_component`, `einzeln` 0, ohne Produkt).
- **Produktdialog**: Reiter „Produkt“ | „Bestandteile“ jetzt bei jedem Produkt (anlegen, bearbeiten, Variante, aus
  Meldung; nicht in der Nacharbeit). Im Reiter je Position Bezeichnung und Anzahl, ↑ ↓ „Entfernen“, „+ Bestandteil
  anlegen“ und „n von 30 Positionen“; doppelte Bezeichnung und Grenzen am Feld. Neu geht die Liste in derselben Anfrage
  mit (scheitert eine Position, entsteht nichts), beim Bearbeiten als `PUT …/bestandteile`, wenn sie sich geändert hat.
- **Produktseite**: Abschnitt „Bestandteile“ („2 × Bezeichnung“), nur mit Liste; mit Katalogrecht „Bestandteile
  bearbeiten“ (öffnet den Dialog im Reiter). **Artikelseite**: Zeile „Bestandteile“ unter „Norm“ mit den Seriennummern
  des Artikels. **Meine PSA** (F3 a): Zeile „Bestandteile“ in der Karte. **Lebenslauf-PDF**: Abschnitt „Bestandteile
  (laut Katalog)“ mit den Seriennummern (der heutige Stand; was am Prüftag galt, steht im Protokoll).
- Ändern darf die Material-Verwaltung jederzeit (kein Antrag): unveränderte Positionen (gleiche Bezeichnung) bleiben
  dieselbe Zeile, Bezeichnung, Anzahl und Reihenfolge werden nachgezogen. Journal am Produkt **„Bestandteile geändert“**
  (vorher/nachher), im Lebenslauf jedes Artikels ab seinem Anlegen. Festgeschriebene Protokolle und offene Entwürfe
  behalten ihre Zeilen; die nächste Prüfung nimmt die neue Liste.
- **Variante**: übernimmt die Liste des Vorbilds zum Bearbeiten (`bestandteile` oder die des Vorbilds; `[]` ohne Liste);
  die Variante eines Sets bleibt ein Set. Löschen nimmt die Liste mit (ON DELETE CASCADE).
- Ein Produkt mit Bestandteil-Liste ist kein Set: keine Set-Marke, keine Teile, keine Set-Prüfung; es kann selbst einzeln
  geführter Bestandteil eines Sets von Hand sein.

### Prüfung

- Jede Prüfung eines Artikels mit Bestandteil-Liste (jede Prüfart, einzeln und im Durchgang, auch ein Teil eines Sets von
  Hand) bekommt hinter den Formularpunkten je Position eine Ja/Nein-Zeile **„… vorhanden“** (Gruppe „Bestandteile“,
  „Tasche (2×) vorhanden“; Pflicht, Soll „ja“, nicht kritisch, vorbelegt „vorhanden“). Die Oberfläche zeigt
  „vorhanden“/„fehlt“ wie in der Set-Prüfung (Befund `bestandteil`).
- **„fehlt“ ist ein Mangel wie jeder andere (F1 a)**: Foto und Bemerkung Pflicht, nicht kritisch – das Ergebnis wählt der
  Prüfer. Protokoll-PDF: die Zeilen in der Befundtabelle unter „Bestandteile“ (keine Teiletabelle). Eine Berichtigung
  kopiert die Zeilen.

### Seriennummern der Bestandteile (Zusatz S1–S3)

- Am **Artikel** je Position und Stück ein freiwilliges Feld „Seriennummer“ (höchstens 80 Zeichen; leer erlaubt – ein
  Beutel hat keine). Neue Tabelle `mat_item_component_serial`.
- **Beim Anlegen und bis zur ersten abgeschlossenen Prüfung direkt** (Materialwart; Dialog „Bearbeiten“, Fieldset
  „Seriennummern der Bestandteile“; ein Prüfer 403). **Danach** trägt der **Prüfer** eine neue oder fehlende Nummer in der
  Prüfung ein (Felder an der Zeile „… vorhanden“, gespeichert beim Verlassen des Feldes, übernommen beim Festschreiben;
  das Protokoll hält „alt → neu“ fest, Journal „Seriennummern der Bestandteile geändert“ mit der Prüfung) – außerhalb
  einer Prüfung nur per **Änderungsantrag** (Feld „Seriennummer Bestandteil „…““, je Stück eine Zeile im Sammelantrag,
  Freigabe wie die übrigen Stammdaten; leer = Nummer entfernen; zusammen mit einem Produktwechsel nicht). Direkt nach der
  ersten Prüfung: 409.
- **Suche**: die lokale Suche findet den Artikel auch über die Nummer eines Bestandteils (Teiltreffer; Rechte wie beim
  Artikel). **Rückrufe treffen Bestandteile nicht** (kein Katalogprodukt). Die globale Seriennummernsuche (fremde
  Bereiche) kennt sie nicht.
- Ändert die Material-Verwaltung die Liste: Nummern an unveränderten Positionen bleiben; entfallene Positionen und Stück
  über einer gesunkenen Anzahl verlieren ihre Nummer (Journal je Artikel „Seriennummern der Bestandteile geändert“ mit
  Grund „Bestandteil-Liste des Produkts geändert“; Protokolle behalten sie). Wechselt der Artikel das Produkt (vor der
  ersten Prüfung oder per Antrag), ebenso (Grund „Produkt gewechselt“).

### Katalogdatei (Format 1 und 2)

- `"bestandteile"` **ohne** `"set": true` (fehlt oder `false`) ist die Bestandteil-Liste: je Position
  `{"bezeichnung", "anzahl"}`; `einzeln: true` oder `produkt` → Fehler „Position n: „einzeln“: true gibt es nur an einem
  Set …“, `austausch` außer `nicht_belegt` → Fehler; doppelte Bezeichnung, Anzahl, mehr als 30 Positionen → Fehler. `[]`
  entfernt die Liste, ohne den Schlüssel bleibt sie. Als Ganzes ersetzt (gleich = unverändert), Bericht
  **`bestandteillisten`** {neu, geaendert, unveraendert} und „Produkt „…“: Bestandteil-Liste ersetzt (n Positionen)“;
  ändert sich am Produkt nur die Liste, zählt es als „geändert“. Eine Liste aus Texten bleibt ein Hinweis.
- **F2**: Ist das Produkt hier ein **Set**, ist eine Bestandteil-Liste ohne `"set": true` ein **Fehler** dieses Produkts
  („Das Produkt ist hier ein Set – …“), nichts wird gespeichert; kein automatisches Umstellen.
- Export: an Nicht-Sets mit Liste `"bestandteile": [{"bezeichnung", "anzahl"}]`, kein `"set"`. DEMO-Vorlage
  `docs/material-katalog-set-vorlage.json` mit dem Beispiel „BEISPIEL Produkt mit Lieferumfang“ (seit Schritt 26
  `docs/material-katalog-bestandteile-vorlage.json`, nur dieses Beispiel).
- Die Katalogserie braucht wie bisher vorher `flask material dev-zuruecksetzen` (ehemalige Sets mit Artikeln scheitern
  sonst mit klarem Fehler).

### Meldungen (F4 a)

- An einer **Set-Meldung** stehen „Produkt anlegen“ (Produktdialog ohne Set-Modus, die gemeldeten Teile als Vorlage über
  dem Reiter „Bestandteile“) und „Set anlegen“. Der Meldedialog bleibt.

### Schritt 25 (Schema)

- Trigger `mat_component_neu`/`mat_component_aendern` ersetzt (gleiche Namen): am Nicht-Set nur Text-Positionen, am Set
  wie bisher.
- `mat_item_component_serial` (Artikel CASCADE, Position CASCADE, Stück 1–20, Nummer nicht leer, eindeutig je Artikel,
  Position, Stück) mit Triggern: nur an einer Position des Produkts des Artikels (Text-Bestandteil, kein Set, Stück ≤
  Anzahl); nach der ersten abgeschlossenen Prüfung einfügen, ändern, löschen nur gedeckt – durch einen bestätigten, noch
  nicht angewendeten Antrag (alt und neu passen, danach `applied_at`) oder durch den offenen Entwurf einer Prüfung dieses
  Artikels, dessen Zeile genau diese Nummer trägt; eine nicht mehr gültige Nummer (Position weg, Stück über der Anzahl,
  anderes Produkt) darf weg; Schlüssel nie ändern, INSERT OR REPLACE über die Kennung nie.
- `mat_inspection_result.component_id` und `component_serials` (je Stück `{alt, neu}`), geschützt wie die übrigen Spalten
  (`mat_result_bestandteil`).
- `mat_item_change` neu aufgebaut wie in Schritt 23 (alle Zeilen, Kennungen und der AUTOINCREMENT-Stand bleiben): Feld
  `component_serial`, Spalten `component_id`, `stueck`, `component_label`; der eindeutige Index „ein offener Antrag je
  Artikel und Feld“ zählt Position und Stück mit; die Antrags- und Artikeltrigger werden neu angelegt. Wiederholbar:
  umgebaut nur, wenn der CHECK `component_serial` nicht kennt; ein zweiter Lauf ändert nichts. Wer `mat_item_change`
  künftig neu aufbaut, muss die Trigger `mat_teilnummer_*` vorher entfernen und danach neu anlegen.
- **Rückweg**: Älterer Code sieht Version 25 ≥ seiner und tut nichts; Listen an Nicht-Sets zeigt er nicht, Prüfzeilen
  schreibt er nicht, Seriennummern der Bestandteile liest er nicht – kein Datenverlust. Vorher alle offenen Anträge auf
  Seriennummern der Bestandteile entscheiden. Vollständig zurück (an einer Kopie, nach Sicherung) **in dieser
  Reihenfolge** (berichtigt nach der Sicherheitsprüfung, S2): erst `DELETE FROM mat_product_component WHERE
  set_product_id IN (SELECT id FROM mat_product WHERE is_set = 0);` – die Nummern gehen per ON DELETE CASCADE mit (eine
  Nummer ohne gültige Position darf weg) –, dann `DELETE FROM mat_item_component_serial;` (leer, zur Sicherheit), dann die
  beiden Stücklisten-Trigger aus `TRIGGER_21` neu anlegen. Umgekehrt (erst die Nummern) bricht es an jeder Nummer eines
  geprüften Artikels ab (Trigger `mat_teilnummer_loeschen`). Anträge mit `component_serial` bleiben als Nachweis stehen
  (unveränderlich, Schritt 23) – **Code 24 kennt das Feld nicht**: Artikel mit offenem Teil-Antrag, die Antragsliste
  „offen“ und – solange es einen Teil-Antrag gibt – „alle“ antworten dort mit 500, ebenso das Ablehnen eines offenen
  Teil-Antrags. Hingenommen wie beim Rückweg 23 → 22; vorher entscheiden hält wenigstens „offen“ und die Artikel heil.

### Schnittstelle

| Route | Änderung |
| --- | --- |
| `POST /api/material/produkte` | `bestandteile` ohne `is_set`: Produkt mit Bestandteil-Liste (nur Text) → 201; `einzeln`/`produkt_id`/`austausch` darin 400 „Position n: …“; mit `is_set` wie bisher |
| `PUT /api/material/produkte/<pid>/bestandteile` | an Nicht-Sets: Liste nur Text, `[]` entfernt sie → `{produkt, geaendert}`; kein 409 mehr |
| `POST …/produkte/<pid>/variante` | Nicht-Set: `bestandteile` oder die Liste des Vorbilds |
| `POST …/meldungen/<mid>/produkt` | wie `POST /produkte` |
| `GET …/produkte/<pid>` | `bestandteile` an jedem Produkt (voll) |
| `GET …/artikel/<iid>` | `produkt.bestandteile` [{bezeichnung, anzahl}], `bestandteile` [{id, bezeichnung, anzahl, nummern}], `bestandteile_direkt` |
| `GET …/artikel/vorschlag` | `bestandteile` [{id, bezeichnung, anzahl}] für die Felder beim Anlegen |
| `POST …/artikel`, `PUT …/artikel/<iid>` | `bestandteil_nummern`: [{bestandteil_id, stueck, seriennummer}] – nach der ersten Prüfung 409, Prüfer 403 |
| `POST …/artikel/<iid>/antrag` | `bestandteil_nummern` wie oben (nur Geändertes zählt; nicht zusammen mit `product_id`) |
| `GET …/meine-psa` | Karte `bestandteile` [{id, bezeichnung, anzahl, nummern}] |
| `GET …/pruefungen/<id>` | Befund `bestandteil` (bool), `nummern` [{stueck, alt, neu, wert}] |
| `PUT …/pruefungen/<pid>/punkte/<rid>` | `seriennummern`: je Stück ein Text (nur an Zeilen „… vorhanden“ einer Bestandteil-Liste) |
| `GET …/suche` | findet auch über die Seriennummer eines Bestandteils; `exakt_lokal` ebenso |
| Katalogimport-Bericht | `bestandteillisten` {neu, geaendert, unveraendert} |

### Tests

- Neu `tests/test_material_bestandteile.py`: Migration 24 → 25 mit Altbestand (Set, Prüfung, offener Antrag), zweiter
  Lauf; Trigger 25; Katalog (Fehler, atomar, ersetzen, leeren, Journal, Variante, Löschen, Rechte); Prüfzeilen (Mangel,
  Entwurf behält, Berichtigung, Durchgang, PDF); Seriennummern (anlegen, bearbeiten, Prüfung, Antrag, Suche, PSA,
  Lebenslauf, Liste ändern); Katalogdatei (Format, Bericht, Fehler, F2, Export → Import, Vorlage); Oberfläche statisch.
- Angepasst: Migrationstests 15/17/23/24 (Trigger von Schritt 25, `_schritt_25` im zweiten Lauf, 23 → 24 nur bis 24),
  `bis_schritt` rüstet Tabelle und Spalten aus Schritt 25 nach.

### Bitte bestätigen

- Seriennummern in der Prüfung werden beim Verlassen des Feldes gespeichert (nicht schon beim Tippen wie Werte und
  Bemerkungen).
- Ein Antrag auf Seriennummern der Bestandteile darf eine Nummer auch entfernen (leer); ein Produktwechsel und neue
  Nummern gehen nicht in einen Antrag.
- Die globale Seriennummernsuche (fremde Bereiche) und der Bestandsimport kennen die Nummern der Bestandteile nicht.

## Nachbesserung L2c nach den Prüfungen (25.10.2026)

Grundlage: die Prüfungen Ablauf und Sicherheit der Bestandteil-Liste (f51c310) und die Browserprüfung der ganzen
Lieferung P4-L2c (Befunde in befunde_l2c.md). Kein neuer Schemaschritt – Schritt 25 bleibt, wie er ist.

### Behoben

- **Nummer am falschen Bestandteil (Ablauf B1)**: Die Kennung einer Position (`mat_product_component.id`, INTEGER PRIMARY
  KEY ohne AUTOINCREMENT) ging beim Ersetzen der Liste an eine neue Position über – eine Nummer aus einem offenen
  Prüfentwurf oder Antrag landete nach dem Umbenennen am anderen Bestandteil. Jetzt schreibt das Ersetzen erst die neuen
  Positionen und löscht dann die alten (wie „Stückliste übertragen“; nur an der Bestandteil-Liste, Set-Code bleibt
  unberührt). Weil eine Kennung über zwei
  Änderungen hinweg trotzdem wiederkommen kann (Tasche weg, später Beutel neu), vergleichen Prüfung und Antrag zusätzlich
  die **Bezeichnung**: die Prüfzeile ihren Text („Tasche (2×) vorhanden“) mit der heutigen Position, der Antrag seine
  `component_label` (ohne Groß und klein und Leerraum, eine geänderte Anzahl zählt nicht). Passt sie nicht, nimmt die
  Prüfzeile keine Nummer mehr an (409 „… diese Position gibt es so nicht mehr …“), das Festschreiben übernimmt nichts,
  und der Antrag „passt“ nicht mehr – Bestätigen 409 mit dem Satz zur Position, nur noch ablehnen.
- **Berichtigung und wirksamer Wert (Ablauf B2 = Sicherheit S3)**: „Unverändert“ heißt in einer Berichtigung jetzt: gleich
  dem wirksamen Wert des Originals (seine eingetragene Nummer, sonst die bisherige) – dann gilt wieder der Eintrag des
  Originals, das Stück steht im Protokoll wie dort. Weicht die Eingabe davon ab, vergleicht das Festschreiben mit dem Stand
  am Artikel und schreibt die Änderung; das Protokoll der Berichtigung nennt als „alt“ diesen Stand – auch einen, den ein
  Antrag nach dem Original gesetzt hat („AN → D“ statt „A-T → D“). Wer die Nummer des Originals zurücksetzen will
  (Original ALT1 → NEU1, Berichtigung ALT1), bekommt sie an den Artikel („NEU1 → ALT1“). Der Berichtigungsentwurf zeigt
  unter dem Feld „am Artikel heute …“, wenn der Stand am Artikel vom Feld abweicht.
- **Ordnerliste läuft über den Rand (Browser B1)**: Mit der Spalte „Kategorie“ bleibt die Liste bis 899 px Inhaltsbreite
  die enge Tabelle (Fold aufgeklappt – Firefox setzte die Zwischenstufe dort noch 33 px zu breit); zwischen 900 und 979 px
  steht die Kategorie klein über dem Hersteller statt in einer eigenen Spalte, ihr Sortierknopf im Kopf darüber; ab 980 px
  die volle Tabelle (ein Laptop mit 1280 px und Leiste zeigt also die Zwischenstufe). Gemessen (Prüfer, Touch-Emulation,
  Chromium): Fenster 800–1380 px in 20-px-Schritten ohne waagerechten Bildlauf; dazu st-geraete (foldable, tablet,
  laptop; drei Engines; Prüfer, Materialwart, Material-Verwaltung).
- **Protokoll ohne Übernahme (Ablauf B3)**: Bei „nicht zutreffend“, an einer Position, die es nicht mehr gibt, und an einem
  Stück über einer gesunkenen Anzahl wird „neu“ geleert – das festgeschriebene Protokoll hält nur fest, was am Artikel
  geschah.
- **Wettlauf Prüfung ↔ Antrag (Ablauf B4)**: Die Prüfzeile merkt beim Eintragen den Stand am Artikel. Hat er sich bis zum
  Festschreiben geändert (bestätigter Antrag, vor der ersten Prüfung auch das Bearbeiten), bricht das Festschreiben mit
  409 ab, wie beim Prüfpunkt Länge: „Die Seriennummer am Artikel wurde während der Prüfung geändert (Tasche: jetzt …) –
  bitte deine Eingabe prüfen …“. Die Zeile zeigt danach „bisher“ mit dem neuen Stand, der zweite Versuch schreibt den
  Eintrag des Prüfers („ANTRAG → PRUEFER“). Wer erst nach dem Antrag einträgt, sah den neuen Stand – kein Rückfragen.
- **Antragsmail (Ablauf V1)**: nach dem Doppelpunkt immer ein Leerzeichen („Seriennummer Bestandteil „Tasche“: (leer) →
  MT-1“).
- **Eingaben nur aus Steuerzeichen (Sicherheit S1)**: `text()` kürzt den Leerraum nach dem Ersetzen der Steuerzeichen noch
  einmal – „\x01“ ist leer (keine Nummer bzw. „Position n: Bitte eine Bezeichnung angeben.“) statt „ “, das die Datenbank
  abwies (409 „anderswo geändert“; Antrag 201 und danach nur ablehnbar, Prüfung ließ sich nicht abschließen). Weist die
  Datenbank im Katalogimport eine Bestandteil-Liste oder Stückliste trotzdem ab, ist das ein Fehler dieses Produkts mit
  Fundstelle und Name („… ließ sich nicht speichern – eine Position verletzt eine Regel …“), kein Abbruch des ganzen
  Imports.
- **Rückweg (Sicherheit S2)**: im Abschnitt Schritt 25 in der richtigen Reihenfolge, mit dem Hinweis auf offene
  Teil-Anträge und die 500 im Code 24.
- **Antrag auf eine entfallene Position (Sicherheit, Verbesserung)**: Bestätigen sagt „diese Position gibt es so nicht
  mehr“ (TEIL_WEG) vor „der Artikel trägt inzwischen nicht mehr den Wert …“.
- **Wiki-Import (Browser B2)**: Esc im Ergebnis wirkt wie „Schließen“ – der Baum lädt neu, die erste neue Seite öffnet.
- **README (Browser B3)**: die Schublade gilt unter 1024 px (nicht 1200).

### Oberfläche (Verbesserungen der Browserprüfung)

- **Prüfung „fehlt“**: Die Bemerkung hat eine sichtbare Beschriftung („Bemerkung zum Mangel“ bzw. „Bemerkung“) und steht
  vor den Seriennummern; die Nummern stehen in einem eigenen Fieldset („Seriennummer“ bzw. „Seriennummern“ mit „Stück n“).
- **Dieselbe Nummer an zwei Stück** eines Artikels (auch in anderer Schreibung): Hinweis am zweiten Feld „Diese Nummer
  steht schon an „…““ – beim Anlegen, im Dialog „Bearbeiten“, im Antrag und in der Prüfung; gespeichert wird trotzdem
  (eindeutig müssen die Nummern nicht sein).
- **Filter-Schublade am Telefon**: Der Kopf mit „✕“ bleibt oben stehen, auch wenn „Filter“ die Schublade bis zum
  Filtermenü rollt.
- **Produktseite**: „Als Variante kopieren …“ und „Rückruf anlegen …“ stehen im Untermenü „Mehr“ neben „Bearbeiten“
  (Knopfregel: seltene Funktionen im Untermenü).
- Niedrig: Im Filtermenü behält eine gewählte Kategorie ohne Treffer Namen und Platz (mit 0); der Wiki-Import wählt die
  ZIP-Datei über den grauen Knopf „ZIP-Datei wählen …“ mit dem gewählten Namen daneben; der schreibgeschützte Block
  „Seriennummern der Bestandteile“ im Dialog „Bearbeiten“ sagt bei einer Position ohne Nummer „keine Nummer
  eingetragen“; keine doppelte Klammer mehr („Bestandteil A (rot) – Stück 1 von 2“, in Feldern, Antrag und Journal neuer
  Einträge); der Trennpunkt vor „Art.-Nr.“ wandert beim Umbruch mit (Meine PSA am Telefon).

### Bewusst nicht geändert

- **Set-Punkte ausgelassen** (Änderung des Nutzers vom 25.10.2026: Die Set-Funktion wird in einem späteren Bau komplett
  entfernt): Verbesserung 5 (Fehler im Set-Dialog am Reiter, ruhige Dialoghöhe), der lange Satz im Dialog „Stückliste
  übertragen“ und `font-size` von `.mat-su-gruppe h3` (beide im Set-Dialog). Kein Set-Code geändert.
- Seiten ohne roten Hauptknopf im Kopf (Katalog, Ordner, Produktseite, Anträge, Meldungen) – gewollt nach der Knopfregel.
- Wiki-Kopf: Knöpfe 💬/Teilen/☰/⋯ als `btn ghost` mit Emoji und zwei rote Hauptknöpfe („Neue Seite“, „Anlegen“) – bekannte
  Altlast gegen die Knopfregel, nicht Teil dieser Lieferung.

### Schnittstelle

| Route | Änderung |
| --- | --- |
| `PUT …/pruefungen/<pid>/punkte/<rid>` | `seriennummern` an einer Zeile, deren Position es so nicht mehr gibt: 409 |
| `POST …/pruefungen/<pid>/abschliessen` bzw. `festschreiben` | 409 „Die Seriennummer am Artikel wurde während der Prüfung geändert (…)“, danach erneut |
| `GET …/pruefungen/<id>` | im Berichtigungsentwurf `nummern[].artikel` (Stand am Artikel heute) |
| `POST …/antraege/<aid>/bestaetigen` | 409 TEIL_WEG auch bei gleicher Kennung, anderer Bezeichnung; vor STAND_ANDERS |
| `GET …/artikel/<iid>` (Anträge) | `passt` false, wenn die Position nur noch die Kennung teilt |
| Katalogimport-Bericht | abgewiesene Liste als `fehler` des Produkts statt Abbruch |

### Tests

- `tests/test_material_bestandteile.py`: `test_kennung_und_bezeichnung` (R1, R2, neue Kennung beim Umbenennen, Gegenprobe
  andere Schreibung und höhere Anzahl), `test_berichtigung_wirksamer_wert` (Ablauf S1, Sicherheit probe10, unverändert
  gelassen, zurückgetippt), `test_nicht_uebernommen_und_wettlauf` (S2, S3, R3), `test_steuerzeichen_und_mail` (S1 mit
  Artikel, Liste, Prüfung, Antrag, Katalogdatei; V1). Alle vier scheitern am Stand f51c310.
- Rückweg an einer Kopie nachgestellt: die alte Reihenfolge bricht ab, die neue läuft durch.
- Statisch: `test_oberflaeche_statisch` (Hinweis bei doppelter Nummer, Bemerkung vor dem Fieldset, Untermenü „Mehr“,
  Zwischenstufe der Kategorie, `stueck_text`); `test_material_wuensche_2510` auf die Klasse `mat-kategorie` angepasst.

### Bitte bestätigen

- B4 gilt wie bei der Länge für jede Änderung seit dem Eintrag – auch, wenn der Materialwart die Nummer während der
  Eingangsprüfung ändert (bisher galt dort still der Eintrag des Prüfers): einmal 409, danach gilt der Eintrag.
- Berichtigung: ein angefasstes Stück nennt im Protokoll den Stand am Artikel als „alt“, ein nicht angefasstes bleibt wie
  im Original (auch wenn ein Antrag es danach geändert hat).
- Kennungen der Positionen: erst einfügen, dann löschen, dazu der Vergleich der Bezeichnung – kein AUTOINCREMENT (das
  hätte einen Umbau von `mat_product_component` gebraucht).
- Dieselbe Nummer an zwei Stück: nur Hinweis, kein Verbot.

## Wünsche vom 25.10.2026 (Norm-Zeile, Nacharbeit, Filter im Bestand, Wiki-Import)

Wünsche des Nutzers vom 25.10.2026 (W1–W4; W5 Wiki-Artikel folgt getrennt). Grundlage: Bauentwurf
`entwurf_l2c_wuensche.md` mit den Entscheidungen F1–F6 (alle Option A). Gebaut auf `antraege-l2c` (Zweig `l2c-rest`).
**Kein Schemaschritt für W1–W4** (Schritt 24 gehört zum Nachtrag der Anträge).

### W1 – Norm in eigener Zeile

- Artikelseite, Stammdaten: „Produkt“ zeigt nur noch Name und Bemerkung, darunter die Zeile **„Norm“** (mit „–“, wenn
  das Produkt keine hat) – wie auf der Produktseite. Sonst nirgends geändert (alle übrigen Produktanzeigen haben die Norm
  schon eigen oder zeigen sie nicht).

### W2 – Nacharbeit: direkt übernehmen, „Fehlendes Produkt melden“ vorbelegt

- **Nach „Zuordnen“** (Karte oder ausgewählte Zeilen) und nach **„Im Katalog anlegen …“** öffnet sich gleich die Prüfung
  genau dieser Zeilen (F1): Titel „Zugeordnet – übernehmen?“, „n Zeilen zugeordnet.“, „n Zeilen geprüft: k übernehmbar
  …“, roter Knopf **„k Artikel übernehmen“**, „Abbrechen“ (die Zuordnung bleibt). Zeilen, die aus anderen Gründen offen
  bleiben (Datum, Seriennummer …), nennt der Dialog unter „Weiter offen“ – nur dafür bleibt die CSV der Weg.
- **Karte**: Ist ein Produkt zugeordnet (ganz oder zeilenweise) oder die Meldung eingepflegt, steht neben „Produkt
  zuordnen …“ der graue Knopf **„Übernehmen …“** (dieselbe Prüfung je Produktangabe). Die Texte „„Erneut prüfen“
  übernimmt …“ entfallen bzw. sagen „Danach kannst du sie gleich übernehmen.“
- Konten **ohne Katalogrecht**: „**Fehlendes Produkt melden …**“ statt „Produkt melden …“ (Bedingung wie bisher: keine
  offene Meldung oder abgelehnt). Die Material-Verwaltung behält „Im Katalog anlegen …“.
- **Vorbelegt** (F2): Hersteller, Modell, Artikelnummer und die **Bemerkung** – „Aus dem Bestandsimport Nr. …: n Artikel
  warten in der Nacharbeit.“ (bei mehreren Importen „Nr. 3, 5“) und, falls die Liste welche hatte, „Angaben aus der
  Liste:“ mit den verschiedenen Bemerkungen der Zeilen (höchstens 5, je höchstens 200 Zeichen). Keine Serien- und
  Inventarnummern, keine Dateinamen. Norm und Kategorie bleiben leer (der Import liest sie nicht). Wer meldet, sieht und
  ändert den Text vor dem Senden; ohne Bemerkung setzt der Server weiter den Import-Satz. Aus der Nacharbeit bleibt es
  eine Produktmeldung (S8, `is_set` wird übergangen). `meldungDialog` nimmt dazu `note`, `norm`, `category_id` als
  Vorbelegung.

### W3 – Bestand: Spalte „Kategorie“ und Filtermenü in der Seitenleiste

- **Spalte „Kategorie“** nur in der Artikelliste des Ordners (F3): vorn, sortierbar (auch in der Sortierwahl der
  Karten); in der engen Tabelle und als Karte klein grau über Hersteller und Produkt. Lange Namen brechen um. Eine
  Set-Zeile trägt die Kategorie des Set-Produkts.
- **Filtermenü** unter dem Ordnerbaum (`#mat-side-filter`, nur die Ordneransicht füllt es): **Status** (alle,
  überfällig, neu, bald fällig, gesperrt, Lebensdauer erreicht, einsatzbereit), **Kategorie** (alle und die Kategorien
  der Artikel direkt hier; bei gleichem Namen der Pfad, voller Pfad im title), **Zugeordnet an** (die bisherige Auswahl,
  nur mit Grundrecht und Zuordnungen im Zweig). Zeilen wie der Baum, die gewählte markiert wie der aktive Ordner
  (`aria-pressed`), die Zahl grau rechts. Die Reiterzeile über der Liste entfällt.
- Über der Liste nur, wenn gefiltert: „Gefiltert: Status „…“ · Kategorie „…“ · zugeordnet an „…“ – **Filter
  zurücksetzen**“; leer: „Keine Artikel mit diesen Filtern.“ Als **Schublade** (unter 1024 px) davor der graue Knopf
  **„Filter (n)“** (F4): er öffnet dieselbe Schublade bei den Filtern (Fokus auf „Filter“), nach einer Wahl schließt sie
  und der Fokus geht auf den Satz bzw. die Überschrift der Liste; Esc gibt den Fokus an „Filter (n)“ zurück. Tippflächen
  ≥ 44 px nur am Finger. Jede Filteränderung setzt Seite 1, Sortierung bleibt; CSV-Export bleibt ungefiltert.
- **Server**: `ARTIKEL_LISTE_SQL` mit `product_category_id` und `kategorie_name` (Unterabfrage, kein weiterer JOIN),
  `artikel_kurz` liefert `kategorie` {id, name}; Sortierfeld `kategorie` (wirkt auch in Fälligen und Suche);
  `ordner_inhalt(…, kategorie)` und `kategorien` [{id, name, pfad, n}].

### Schnittstelle (W2, W3)

| Route | Wer | Was |
| --- | --- | --- |
| `GET /api/material/ordner/<id>?kategorie=<id>` | wie bisher | nur Zeilen mit Produkt in dieser Kategorie (unbekannte Kennung: leere Liste; keine Zahl: 400); neu `kategorien`, je Artikel `kategorie`; `sort=kategorie` |
| `POST /api/material/ordner/<id>/nacharbeit/pruefen` | Verwalter des Ordners | zusätzlich `{"angabe": …}` (alle offenen Zeilen der Produktangabe) statt `zeilen` – genau eins von beiden (sonst 400), unbekannte Angabe 404 |
| `GET /api/material/ordner/<id>/nacharbeit` | Verwalter des Ordners | je Karte neu `meldung_bemerkung` |

### W4 – Wiki-Import (ZIP)

Wunsch: „Import-Funktion bauen“. Entscheidungen F5 = A (immer neue Seiten, Hinweis bei gleichem Titel) und F6 = A (ZIP
bis 200 MB, Videos übergangen). Kein Schemaschritt; neues Modul `app/wiki_import.py`, Route in `app/api_wiki.py`.

- **Menü „⋯“ der Seite** (nur Wiki-Verwaltung, `can_publish`): „Seiten aus ZIP importieren …“ unter „Abschnitt als ZIP
  herunterladen“. Dialog „Seiten importieren“: ein Satz zum Aufbau, Dateiwahl (`.zip`), „Einsortieren unter“ (Seitenbaum
  eingerückt, „– oberste Ebene –“, vorgewählt die offene Seite), darunter ein Satz, wenn das Ziel ohne Anmeldung sichtbar
  („Dieser Abschnitt ist ohne Anmeldung sichtbar – die importierten Seiten sind es sofort auch.“) oder lesebeschränkt ist
  („… sind dann ebenso beschränkt.“); „Abbrechen“ grau | „Importieren“ rot, während der Anfrage „Wird importiert …“
  (gesperrt). Ergebnis im selben Dialog: „n Seiten und m Dateien importiert.“, die neuen Seiten als Links, „Hinweise“;
  „Schließen“ (auch Esc) lädt den Baum neu und öffnet die erste neue Seite. Kein `btn ghost`.
- **Archiv** (vor dem Entpacken): höchstens 2000 Einträge und 512 KB Inhaltsverzeichnis (aus dem Ende-Satz), keine
  doppelten Namen (auch nicht nach Unicode-Normalisierung), nichts verschlüsselt, entpackt höchstens 1 GB, je Eintrag ab
  1 MB ein Packverhältnis bis 100:1; gelesen wird nie mehr als die angegebene Größe.
- **Pfade**: Abbruch bei `..`, führendem `/`, `\`, Laufwerksbuchstaben, Steuerzeichen, symbolischen Verweisen und mehr
  als 20 Ebenen; still übergangen: Verzeichniseinträge, `__MACOSX/`, Teile mit führendem Punkt, `Thumbs.db`.
- **Seiten**: `*.md`/`*.markdown`, UTF-8 (BOM erlaubt, CRLF wird LF), ohne Nullzeichen, je höchstens `MAX_REQUEST_MB`
  (wie eine Seite im Editor), zusammen höchstens 64 MB, höchstens 500 je Import. Titel = erste Zeile `# …` ohne
  Auszeichnungen (Regel wie `titelZeile` im Editor), sonst der Dateiname – dann wird `# <Titel>` vorangestellt; länger
  als 200 Zeichen → Abbruch. `A.md` und `A.markdown` zugleich → Abbruch („wären dieselbe Seite“).
- **Baum**: `A.md` und Ordner `A/` sind dieselbe Seite, `A/B.md` ihre Unterseite; ein Ordner ohne eigene `.md` wird eine
  Seite mit seinem Namen (nur Titelzeile). Die oberste Ebene kommt unter das Ziel, hinter dessen vorhandene Unterseiten;
  Geschwister in natürlicher Reihenfolge der Namen. Ein Export lässt sich ohne Änderung wieder einlesen.
- **Anhänge**: nur Dateien, auf die eine Seite verweist, über dieselbe Ablage wie beim Hochladen (`store_wiki_file`:
  Bilder neu geschrieben ohne EXIF, Pixelgrenze; Dokumente, GIF, SVG, HTML-Bausteine unverändert), jede Archivdatei
  einmal, vermerkt in `wiki_files`. Videos → Hinweis „Video „…“ übergangen – Videos einzeln hochladen.“; fremde Endungen
  → „… übergangen – Dateityp … wird im Wiki nicht unterstützt.“; unbenutzte → „… keine Seite verweist darauf, nicht
  übernommen.“; eine Datei, die sich nicht verarbeiten lässt (kaputtes Bild), → Hinweis, der Verweis bleibt. Je Art
  höchstens 50 Hinweise einzeln, dann „… und n weitere“.
- **Verweise** (außerhalb von Codeblöcken und Inline-Code): Ziele von `](…)` (auch `](<…>)`) und `src="…"`;
  `/media/wiki/<ref>` → Eintrag `media/<ref>`, relative Pfade relativ zur `.md` (müssen im Archiv bleiben) → neue Datei
  mit erhaltenem `#…`; relativer Verweis auf eine importierte `.md` → `/wiki/<neuer slug>` (mit Anker). `/wiki/…`-Links,
  `:::einbau`, `:::baustein`, fremde Adressen bleiben; nicht auflösbar → bleibt stehen, Hinweis „Verweis ohne Datei in
  „…“: …“.
- **Schreiben**: Anhänge werden in einem Vorlauf ohne Schreibsperre abgelegt (Bilder neu schreiben dauert), dann alle
  Seiten in EINER Transaktion (`BEGIN IMMEDIATE`) wie `create_page` (freie Adresse, Ersteller = Importierender, eine
  Fassung je Seite, `wiki_page_files`, `wiki_page_links`); bei jedem Fehler Rückrollen und die schon abgelegten Dateien
  löschen. Keine Mails, keine Benachrichtigung von Beobachtern.
- **Konflikt (F5)**: Gleichnamige Seite unter dem Ziel → trotzdem neue Seite mit eigener Adresse (`…-2`), Hinweis „Unter
  „X“ gibt es schon eine Seite „Y“ – die importierte steht daneben unter eigener Adresse (/wiki/…).“ (oberste Ebene: „Auf
  der obersten Ebene …“).
- **Freigabe/Beschränkung**: nichts wird gesetzt, die neuen Seiten erben vom Ziel. `GET /api/wiki/tree` liefert dafür
  zusätzlich `read_restricted` (nur für Seiten, die das Konto ohnehin lesen darf).
- **Konfiguration**: `WIKI_IMPORT_MB` (Vorgabe 200), eigene Grenze in `size_guard` (413 darüber).

| Route | Wer | Was |
| --- | --- | --- |
| `POST /api/wiki/import` (multipart: `file`, `parent_id` leer = oberste Ebene) | Wiki-Verwaltung (Mitglied und Lesemodus 403, ohne Anmeldung 401) | 201 `{seiten: [{id, title, slug, parent_id}], dateien, hinweise}`; 400 mit Satz (Archiv, Pfad, Seite, Ziel unbekannt, keine Datei), 413 über `WIKI_IMPORT_MB` |

Tests: `tests/test_wiki_import.py` (Rundweg Export → Import samt zweitem Import unter dasselbe Ziel und oberster Ebene,
Regeln eines selbst gepackten Archivs, 19 Abbruchfälle ohne Spuren (dazu die Grenze für Seitentext) und ein Fehler mitten im Schreiben, Rechte je
Rolle, Grenze, Erben von Freigabe und Beschränkung, Oberfläche statisch); `tests/test_wiki_lesemodus.py` erfasst die
neue Route im Rundumtest von selbst (403). Browserprobe 1280/360 px: Export wieder eingelesen, gleicher Titel → neue
Seite mit Hinweis, Video und `.exe` übergangen, Satz zur Freigabe bei öffentlichem Ziel; keine Konsolenfehler, kein
waagerechter Bildlauf.

**Abweichungen vom Entwurf**
- Ein Bild, das sich nicht verarbeiten lässt, bricht den Import nicht ab: Hinweis, Verweis bleibt (ein kaputtes Bild
  soll nicht 300 Seiten verhindern); alle Prüfungen des Archivs und der Seiten brechen weiterhin ab.
- Zusätzlich: höchstens 64 MB Seitentext je Import (alle Seiten liegen beim Umschreiben im Speicher), Titel über 200
  Zeichen brechen ab (statt zu kürzen – die erste Zeile bliebe sonst länger als der Titel).
- Anhänge werden vor der Schreibsperre abgelegt (Vorlauf), damit ein Import mit vielen Bildern andere Schreiber nicht
  blockiert; Aufräumen bei einem Fehler wie im Entwurf.
- `GET /api/wiki/tree` liefert `read_restricted` mit (für den Satz zur Beschränkung im Dialog).

### Abweichungen vom Entwurf (W1–W3)

- **Zahlen im Filtermenü** zählen wie Filter in einer Leiste: Status mit dem Kategoriefilter, Kategorien mit dem
  Statusfilter (je Gruppe alle übrigen Filter außer dem eigenen; „Zugeordnet an“ zählt wie bisher bei beiden nicht mit).
  Der Entwurf hatte für beide die Sicht ohne Filter – dann stünde neben „überfällig (3)“ eine Liste mit einem Artikel.
- Der Status zeigt seine Zahl immer (auch 0) – eine ruhige Spalte wie die Zahlen im Baum.
- Die Personenauswahl trägt im Filtermenü die sichtbare Beschriftung „Zugeordnet an“ (statt der ersten Option
  „Zugeordnet an …“; die erste Option heißt jetzt „alle“).

### Bitte bestätigen

1. Zahlen im Filtermenü mit den übrigen Filtern (siehe Abweichungen).
2. Vor der ersten Prüfung lässt der Dialog „Bearbeiten“ das Lebensende weiterhin nur vorziehen; nach hinten (bis zur
   Rechnung) geht es nur per Antrag. Soll „Bearbeiten“ das auch können? **Entschieden am 25.10.2026 (W2 der
   Freigabeliste L2c): bleibt so** – vor der ersten Prüfung nur vorziehen; zurück erst nach ihr per Antrag, höchstens
   bis zur Rechnung.
3. W4: Ein Bild, das sich nicht verarbeiten lässt, bricht den Import nicht ab (Hinweis, der Verweis bleibt).
4. W4: Über den Feldern des Import-Dialogs steht ein Satz zum Aufbau des ZIP.

## Nachbesserung Sets nach den Prüfungen (25.10.2026)

> **Zurückgebaut durch Schritt 26** (Wunsch des Nutzers, 25.10.2026) – siehe „Rückbau der Set-Funktion“. Der Abschnitt
> bleibt als Geschichte stehen.

Befunde der Prüfungen Ablauf und Sicherheit zu „Sets anlegen und Stückliste übertragen“ (`befunde_l2c.md`, beide
„lieferbar ja“). Kein Schemaschritt.

- **Kennungen der Kopie** (Sicherheit 1): „Stückliste übertragen“ schreibt erst die neue Kopie und löscht dann die alten
  Zeilen über ihre Kennungen (vorher: erst löschen – `mat_item_set_slot` hat kein AUTOINCREMENT, SQLite vergab dieselben
  Nummern mit anderer Bedeutung neu; eine offene Set-Seite traf mit „Teil einsetzen“ still eine andere Position). Dazu
  schickt die Oberfläche zur Position ihr Produkt (`produkt_id`: „Teil einsetzen“, Auswahl „aus dem Bestand wählen“)
  bzw. ihre Bezeichnung (`bezeichnung`: „Bestandteil ersetzt“); passt die Position nicht mehr, **409 „Die Stückliste
  dieses Sets wurde inzwischen übertragen – bitte die Seite neu laden.“** Ohne die Angabe bleibt eine unbekannte Position
  404 wie bisher.
- **Anzahl verringert** (Ablauf 1): Gibt es die Position eines übrigen Teils noch – nur mit weniger Stück –, steht am
  Teil der neutrale Journaleintrag **„Anzahl in der Stückliste des Sets verringert – ein Stück zu entnehmen“**
  (`anzahl_verringert`, Beschriftung in `beschriftung.py` und `material.js`) statt „steht nicht mehr in der Stückliste“;
  Sperrgrund („„Verbindungselement“: Anzahl verringert – ein Stück zu entnehmen“), Banner, Gründe der Set-Prüfung („Für
  „…“ stehen weniger Stück in der Stückliste – erst ein Stück „Teil entnehmen“ (welches, wählst du).“), Vorschau und
  Set-Kasten („dieses oder ein anderes Stück entnehmen“) nennen die Position, nicht das eine Stück. Entnimmt der
  Materialwart ein anderes Stück, ist das Set vollständig, ohne dass an dem verbliebenen etwas Falsches stünde.
- **„Set aussondern“** (Ablauf 2): Der 409-Satz nennt jetzt auch „… oder die Stückliste übertragen wurde“.
- **Mail an den Melder** (Ablauf 3): Eine Set-Meldung, die als einfaches Produkt erledigt wird, sagt „das von dir
  gemeldete Set ist jetzt als Produkt (kein Set) im Katalog: …“.
- **S8-Texte**: „Produkt- oder Set-Meldung(en)“ bzw. „Produkt- und Set-Meldungen“ in Übersicht, Katalog → Meldungen
  (Überschrift, Blase), „Deine …“, „Vorhandenem Produkt oder Set zuordnen“, Journal (Entität), Mailfehler-Protokoll.
- **Docstring Schritt 22**: „nur als Ganzes“ erzwingen die Trigger nicht (direktes SQL an einem freien Set) – Schutz gegen
  Programmfehler an ausgesonderten Sets und während einer Set-Prüfung.
- **Importbericht** (Katalogdatei): Ein Set ohne einzeln geführte Position nennt, wie es zu beheben ist („bestandteile“ mit
  einer Position `"einzeln": true`, oder `"set": false`, solange es keine Artikel gibt; ein angelegtes Set auch in der
  Anwendung über „Bearbeiten“ → „Bestandteile“) – auch ein Altbestand aus der Zeit vor der Regel S3.
- Tests: `tests/test_material_sets_uebertragen.py` (`test_nachbesserung_pruefungen`,
  `test_nachbesserung_meldung_und_import`), statisch `tests/test_material_sets_oberflaeche.py`.
- Zur Kenntnis (unverändert): Die Kaskade nimmt ein Teil mit offenem Einzel-Entwurf mit (bestehendes Verhalten).

## Nachbesserung Anträge nach den Prüfungen (25.10.2026)

Befunde der Prüfungen Ablauf und Sicherheit zu den Änderungsanträgen (`befunde_l2c.md`, Berichte
`bericht_pruefung_antraege_l2c_ablauf.md` und `…_sicherheit.md`, beide „lieferbar ja nach Befund 1 (und 2)“). Die Proben
der Prüfer sind als Regressionstest übernommen (`tests/test_material_antrag_nachbesserung.py`). Kein weiterer
Schemaschritt (Schritt 24 gehört zum Nachtrag „Lebensende auch nach hinten“ im Abschnitt der Anträge).

- **Produktwechsel und Geschichte** (Ablauf 1, mittel): Artikeljournal und Lebenslauf lasen das Produktjournal nur des
  heutigen Produkts – nach einem Wechsel per Antrag fehlten die Änderungen am früheren Produkt, und die Geschichte des
  neuen aus der Zeit davor stand da. Jetzt leitet `journal.produkt_zeitraeume` die Zeiträume je Produkt aus dem
  Artikeljournal ab („angelegt“, „produkt_geaendert“, „antrag_bestaetigt“ mit `product_id`; Kennungen steigen streng),
  `journal.fuer_artikel` und der Lebenslauf lesen je Produkt nur dessen Zeitraum (das erste Produkt wie bisher mit
  seiner Geschichte davor). Ohne Wechsel – oder wenn das Journal nicht zum heutigen Produkt passt – bleibt alles wie
  bisher. **Rückrufe** im Lebenslauf: zusätzlich die des früheren Produkts, die angelegt wurden, als der Artikel es noch
  hatte, und ihn betrafen (alle Artikel oder eine Seriennummer, die er je trug), mit „betraf den Artikel mit dem
  früheren Produkt … (bis …)“.
- **Obergrenze des Intervalls** (Ablauf 2 = Sicherheit 1, mittel): `artikel_werte` prüft die Herstellervorgabe nur noch,
  wenn sich das Intervall am Artikel (oder das Produkt) ändert. Senkt der Katalog die Vorgabe unter ein gespeichertes
  Intervall, bleiben Bemerkung, Länge und nächste Prüfung bearbeitbar (Materialwart und Prüfer), ein Antrag ohne
  Intervall stellbar und ein offener bestätigbar; das wirksame Intervall nimmt ohnehin das kürzere. Ein Antrag auf ein
  Intervall über der Vorgabe bleibt 400.
- **Folgeeintrag Fälligkeit** (Sicherheit 2): `faelligkeit.kappen` schreibt beim Bestätigen `{"antrag": Nr.}` in den
  Eintrag „faelligkeit“, `antrag.journal_verbergen` zeigt Lesern dort „(Person)“ statt des Entscheiders (Journal und
  Lebenslauf).
- **Produkt + Lebensende** (Sicherheit 3): Ein Sammelantrag, dessen Lebensende schon von Hand so gesetzt ist (wirksam ist
  eine frühere Rechnung), wird beim Stellen abgewiesen: 400 „Das Lebensende … ist am Artikel schon von Hand gesetzt –
  bitte das Feld „Lebensende“ unverändert lassen.“ Ein Antrag, der sich beim Bestätigen nicht vollständig anwenden lässt,
  endet mit **409** „Der Antrag ließ sich nicht vollständig anwenden – bitte ablehnen; …“ (Protokoll im Log) statt 500.
- **Texte** (Ablauf 3 = Sicherheit 4, Ablauf 4): Die Karte eines Antrags ohne Materialwart sagt neutral „Dieser Ordner
  hat zurzeit keinen Materialwart mit Freigabe „verwalten“ – die Material-Verwaltung kann sich die Freigabe dort geben
  und dann entscheiden.“ (die Rückfall-Mail geht nur beim Stellen). Nach „Antrag senden“ im Rückfall „… die
  Material-Verwaltung bekommt eine Mail.“ bzw. ohne Mail „… der Ordner hat zurzeit keinen Materialwart, der ihn
  entscheiden kann.“
- **Löschdialog** (Sicherheit 5): „Konto löschen“ zählt Sammelanträge einmal (`COUNT(DISTINCT COALESCE(group_id, id))`).
- **Verbesserungen**: Die Blase „Änderungsanträge“ holt nur die Zahl (`GET /api/material/antraege?nur_zahl=1` →
  `{zu_entscheiden}`); eine Begründung nur aus unsichtbaren Format- und Leerzeichen (U+200B …) ist 400 „„Begründung“
  fehlt.“; Docstring Schritt 23 nennt die zwei nur per SQL erreichbaren Lücken (beim gedeckten Produktwechsel
  `retire_by_manual` in derselben Anweisung frei; Folgezeile mit gleichen Angaben nachträglich an einen offenen Kopf).
- Nicht geändert (Frage an den Nutzer, siehe unten): eine Mail, wenn die letzte Verwalterfreigabe eines Ordners mit
  offenem Antrag wegfällt.

| Route | Wer | Was |
| --- | --- | --- |
| `GET /api/material/antraege?nur_zahl=1` | Modulzugang | nur `{zu_entscheiden}` (die Blase im Bestand) |

### Bitte bestätigen

1. Fällt die letzte Verwalterfreigabe eines Ordners weg (abgelaufen, entzogen, Konto gelöscht), während dort ein Antrag
   offen ist, geht keine Mail an die Material-Verwaltung – der Antrag wartet, bis sich jemand die Freigabe gibt. Soll es
   dafür eine Mail geben?
2. Rückrufe des früheren Produkts im Lebenslauf: Sie zählen, wenn sie angelegt wurden, als der Artikel das Produkt hatte,
   und ihn betrafen – mit jeder Seriennummer, die er laut Journal je trug.

## Änderungsanträge an alle Stammdaten, Freigabe durch die zuständigen Materialwarte (Wunsch des Nutzers, 24.10.2026)

Wunsch: „Änderungen an allen Stammdaten eines Artikels sind nach der ersten Prüfung immer freizugeben, bisher war es nur
die Seriennummer. Die Freigabe soll durch die Materialwarte erfolgen können, die für den Artikel zuständig sind. Die
Meldungen sollen analog zum Meldungen-Knopf für fehlende Produkte auf die Bestandsseite verschoben werden. Verwalter des
Katalogs können nicht automatisch jeden Stammdatenänderungsantrag bearbeiten, auch sie brauchen die Rechte, um den
Antrag zu sehen und zu bearbeiten. Die Meldungen bzgl. fehlender Produkte bleiben unberührt bei den Katalogverwaltenden
und in dem Tab.“ Grundlage: Bauentwurf `entwurf_stammdaten_antraege.md` mit den Entscheidungen E1–E8 (unten), gebaut
auf dem Zweig `sets-l2c` (Schema 22). **Schema 23.**

### Was neu ist

- **Freigabepflichtig nach der ersten abgeschlossenen Prüfung** (E1): Produkt, Seriennummer, Herstellung, Kauf,
  Erstgebrauch, **Lebensende (auch vorziehen)** und **Prüfintervall am Artikel** – vorher nur Seriennummer und
  Herstellung. `PUT /artikel/<id>` weist jede Abweichung mit 409 ab („Seit der ersten Prüfung stehen die Stammdaten fest
  – sie sind Teil des Prüfnachweises. Eine Änderung beantragst du mit Begründung; entscheiden die Materialwarte des
  Ordners.“; beim Produkt der eigene Satz mit dem Hinweis auf „Änderung beantragen …“); dieselben Werte gehen durch.
- **Direkt bleiben** (E2) Bemerkung, Länge und „Nächste Prüfung vorziehen“ – für Materialwart **und Prüfer**: Prüfer mit
  wirksamem Prüfrecht bekommen auf der Artikelseite „Bearbeiten“ mit genau diesen drei Feldern (vor und nach der ersten
  Prüfung; jedes andere Feld 403 „Als Prüfer änderst du hier Bemerkung, Länge und die nächste Prüfung …“). Die Länge
  schreibt weiter auch der Prüfpunkt „Länge“ fest.
- **Leere Felder nachtragen** (E3) geht nach der ersten Prüfung nur noch per Antrag – der Sonderweg „Herstelldatum bei
  Metall direkt nachtragen“ entfällt (auch für die Altfälle aus Stand 16). Ein Herstelldatum lässt sich weiter nie
  entfernen; Kauf, Erstgebrauch und Intervall lassen sich per Antrag leeren, Seriennummer, Produkt und Lebensende nicht.
- **Produkt per Antrag** (E4): im Antragsdialog „anderes Produkt“ mit Produktsuche und den Folgen wie im Dialog
  „Bearbeiten“ (Lebensende nach dem neuen Produkt bzw. weg, Länge fällt weg, wenn seine Kategorie keine vorsieht, ein
  kürzeres Intervall rückt die nächste Prüfung vor, Rückrufe nach dem neuen Produkt; die nächste Prüfung nimmt sein
  Formular). Nicht an Sets und Teilen, nicht auf ein Set-Produkt, nicht mit offenem Prüfentwurf, nicht über die
  DEMO-Grenze; die Seriennummer muss beim neuen Produkt frei sein.
- **Sammelantrag**: Der Antragsdialog zeigt alle freigabepflichtigen Felder mit den heutigen Werten; geschickt wird nur,
  was sich ändert, als **ein** Antrag (Antrag-Nr. = Kopfzeile, weitere Felder als Folgezeilen); Begründung Pflicht;
  höchstens ein offener Antrag je Artikel („… läuft schon ein Änderungsantrag … – zurückziehen und neu stellen“).
  Geprüft wird der **ganze neue Stand** wie beim Anlegen (Herstellung nicht nach Kauf und Erstgebrauch, nicht in der
  Zukunft, textil mit Herstellung, keine STR-Nummer, Seriennummer je Produkt frei, Intervall nicht über der
  Herstellervorgabe, Lebensende nur textil und nur vorziehen) – beim Antrag und beim Bestätigen. Bestätigt, abgelehnt
  und zurückgezogen wird der ganze Antrag in einer Transaktion; trägt der Artikel einen alten Wert nicht mehr, lässt er
  sich nur noch ablehnen (die Karte markiert das Feld „am Artikel inzwischen anders“). Je Vorgang **ein**
  Journaleintrag mit allen Feldern (beim Produkt mit Namen), **eine** Mail.
- **Zuständig** (E5, E6): Entscheiden dürfen die Materialwarte des Ordners – Konten mit Modulzugang und **eigener**
  gültiger Freigabe „verwalten“ an der Heimat des Artikels oder darüber, gleich aus welcher Gliederung. **Kein
  Vier-Augen**: Wer zuständig ist, bestätigt auch den eigenen Antrag. Die **Material-Verwaltung** (und die
  Plattform-Verwaltung) nur mit so einer Freigabe – sie darf sie sich im Reiter „Freigaben“ selbst geben (Journal am
  Ordner wie jede Freigabe). Nicht lesbar 404 wie unbekannt, lesbar ohne Zuständigkeit 403 „Entscheiden dürfen die
  Materialwarte dieses Ordners (eigene Freigabe „verwalten“ hier oder darüber).“
- **Sichtbarkeit** (E7): Liste, Blase, Übersicht und Mail hängen am Ordnerrecht – jeder sieht seine eigenen Anträge
  (solange er den Artikel liest) und die, die er entscheiden darf. Artikelseite und Journal zeigen offene Anträge wie
  bisher jedem, der den Artikel liest (ohne Begründung und Namen für Leser).
- **Bestand → „Änderungsanträge“**: neben „Gliederung anlegen“ der graue Knopf „Änderungsanträge“ mit roter Blase (offene,
  die man entscheiden darf – eigene eingeschlossen; ab 100 „99+“; Titel „n offene Änderungsanträge zu entscheiden“; bei 0
  verborgen) für Materialwarte und Prüfer. Seite `/material/bestand/antraege`: Kopf mit grauem „Bestand“, ein Satz Hilfe,
  Filter offen | erledigt | alle, je Antrag eine Karte (Inventarnummer als Link, Produkt, Stand, Antrag-Nr., wer, wann,
  Gliederung und Ordner, „Feld: alt → neu“ je Feld, Begründung, Rückrufhinweis, „nur noch ablehnen“, Hinweis, wenn der
  Ordner gar keinen Materialwart hat) mit grauen Knöpfen „Bestätigen …“/„Ablehnen …“ (nur, wer entscheiden darf) und
  „Zurückziehen …“ (eigener); in der Rückfrage „Bestätigen“ der einzige rote Knopf, „Ablehnen“ endgültig rot umrandet.
- **Katalog → Meldungen** zeigt nur noch Produkt- und Set-Meldungen; die Bereichswahl entfällt, die Blase zählt nur sie.
  Die alte Adresse `/material/katalog/meldungen?bereich=antraege` (Mails, Lesezeichen) leitet mit 302 auf die neue Seite.
- **Übersicht**: Hinweis „n offene Änderungsanträge – Stammdaten nach der ersten Prüfung in Ordnern, die du
  verwaltest“ für jedes Konto, das etwas zu entscheiden hat.
- **Dialog „Bearbeiten“**: Nach der ersten Prüfung (und für Prüfer immer) stehen Produkt, Seriennummer | Herstellung,
  Kauf | Erstgebrauch, Lebensende | Prüfintervall schreibgeschützt oben als Block („Seit der ersten Prüfung fest – Teil
  des Prüfnachweises.“ bzw. für Prüfer „Diese Stammdaten ändert der Materialwart.“), darunter ein offener Antrag als
  Hinweis (der eigene mit „Antrag zurückziehen …“, Zuständige mit „Entscheiden …“) oder grau „Änderung beantragen …“;
  bearbeitbar bleiben Nächste Prüfung, Länge und Bemerkung; „Speichern“ rot.
- **Artikelseite**: „Änderung beantragen …“ in den Stammdaten für alle, die beantragen dürfen – ohne den bisherigen
  Hilfetext darunter (Regel „keine Erklärtexte unter Knöpfen“); der Hinweis zum offenen Antrag sagt „wartet auf einen
  Materialwart des Ordners“, wer entscheiden darf, kommt mit „Entscheiden …“ in die Liste.
- **Mails**: Ein neuer Antrag geht an die zuständigen Materialwarte (ohne den Antragsteller, höchstens zehn, Rolle
  „verwalter“, Fuß „… weil du den Ordner „…“ verwaltest“, Link auf die neue Seite). Nur wenn es **gar kein** zuständiges
  Konto gibt, an die Material-Verwaltung (ohne sie die Plattform-Verwaltung; Rolle „verwaltung“, mit dem Hinweis, sich
  die Freigabe zu geben); ist der Antragsteller selbst der einzige zuständige oder fehlen nur Adressen, an niemanden.
  Der Bescheid an den Antragsteller nennt alle Felder. Mailprotokoll: der Bezug „Änderungsantrag“ führt auf die neue
  Seite; Fehler mit Rolle „verwalter“ sehen die Verwalter des Zweigs.
- **Produktänderungen am Artikel** (E8): Katalogprodukte bleiben für die Material-Verwaltung bearbeitbar; das Journal
  am Artikel zeigt Produktänderungen schon bisher („Produkt geändert“, Feld alt → neu – journal.fuer_artikel liest das
  Produktjournal mit). Neu im **Lebenslauf** (PDF): die Einträge „geändert“, „Bild“ und „Stückliste“ aus dem
  Produktjournal seit dem Anlegen des Artikels, als „Produkt …“; Rückrufe stehen dort weiter in ihrem eigenen Abschnitt
  (ihre Seriennummernlisten nennen Artikel aller Gliederungen), Meldungen gehören zum Katalog. Löschen eines Produkts mit
  Artikeln bleibt gesperrt, die Materialart mit Artikeln 409 – unverändert.
- **Sammelprotokoll**: „vormals …“ kennt den Sammelantrag (Antrag-Nr. des Kopfes) und nennt auch ein per Antrag
  gewechseltes Produkt („vormals <Produkt> (Änderungsantrag Nr. …)“).

### Schritt 23 (wiederholbar)

- Die drei Artikeltrigger, die `mat_item_change` lesen, werden entfernt; `mat_item_change` wird mit `_umbauen` neu
  aufgebaut (nur, wenn ihr CHECK „purchased_on“ noch nicht kennt): CHECK auf alle Felder (`ANTRAGSFELDER`; Schritt 15
  bleibt mit `ANTRAGSFELDER_15`, wie er ausgeliefert wurde), Produkt und Lebensende nie leer, neue Spalte `group_id`
  (`REFERENCES mat_item_change(id)`, NULL = Kopf, `CHECK (group_id IS NULL OR group_id < id)`), Index
  `idx_mat_item_change_gruppe`. Alle Zeilen und Kennungen bleiben, der AUTOINCREMENT-Stand ebenso; Altanträge sind
  Einzelanträge (`group_id` NULL – ein gemeinsam gestellter Antrag aus Seriennummer und Herstellung bleibt zwei Karten).
- Trigger an `mat_item_change` (`TRIGGER_23_ANTRAG`): die aus Schritt 15 und 17, `mat_item_change_inhalt` schützt dazu
  `group_id`, neu `mat_item_change_gruppe` (Kopf nur ohne offenen Antrag am Artikel; Folgezeile nur zu einem offenen
  Kopf desselben Artikels mit gleichem Antragsteller, Zeitpunkt und gleicher Begründung). **Kein** Vier-Augen-Trigger
  (E5).
- Am Artikel (`TRIGGER_23_ARTIKEL`, gleiche Namen ersetzt): `mat_item_stammdaten_fest` deckt nach der ersten Prüfung
  Seriennummer, Herstellung (nie leer, kein Nachtragen mehr), Kauf, Erstgebrauch, Prüfintervall und das von Hand gesetzte
  Lebensende (`retire_by_manual`; beim Produktwechsel folgt es dem neuen Produkt) – jede Änderung nur mit bestätigtem,
  noch nicht angewendetem Antrag mit genau diesem alten und neuen Wert (Zahlen als Text, `CAST`); `mat_item_produkt_fest`
  ebenso für das Produkt (vorher: nie); `mat_item_antrag_angewendet` setzt `applied_at` je gedeckter Zeile. Das
  wirksame Lebensende (`retire_by`) bleibt frei – es folgt Herstellung, Lebensdauer und Katalogkorrekturen. Länge,
  Bemerkung und nächste Prüfung sind nicht freigabepflichtig.
- Geprüft: frisch; 22 → 23 mit Altbestand (zwei offene Anträge am selben Artikel, ein erledigter, Kennungsfolge über
  einer Lücke) und zweiter Lauf (`test_material_antrag_zustaendig.test_migration_23`); 14/15/16 → 23 über die
  vorhandenen Migrationstests; an **Kopien** vorhandener Sandbox-Datenbanken Stand 8 (12 Artikel), 15 (fünf
  Altanträge), 17 und 19 (533 Artikel) → 23 mit zweitem Lauf: Zahlen aller Tabellen gleich (außer Journal und Meta der
  Schritte 8–10), Anträge gleich, Trigger greifen an einem geprüften Artikel. Eine echte Stand-7-Datenbank gibt es in
  der Sandbox nicht (`MATERIAL_KOPIE_STAND_7` bleibt ungesetzt; ein frisch erzeugter Stand 7 startet mit dem heutigen
  Code nicht).
- **Rückweg** auf `sets-l2c` (Schema 22): Code 22 findet Schema 23 vor und lässt es (Version höher). Er liest die neuen
  Felder aber nicht – ein Antrag auf Kauf, Erstgebrauch, Lebensende, Intervall oder Produkt in der Tabelle bricht seine
  Antragsliste (unbekanntes Feld), und die Trigger aus 23 sperren sein Nachtragen bei Metall und das direkte Ändern von
  Kauf, Erstgebrauch und Intervall. Darum: Rückweg nur über die Datensicherung von vor dem Deploy – oder, solange es noch
  keinen Antrag auf ein neues Feld gibt, per SQL die Trigger der Fassung 22 zurück (`DROP TRIGGER
  mat_item_change_gruppe`; `mat_item_stammdaten_fest` = `TRIGGER_17_ARTIKEL[0]`, `mat_item_antrag_angewendet` =
  `TRIGGER_15_ARTIKEL[1]`, `mat_item_produkt_fest` aus `TRIGGER_16`, `mat_item_change_inhalt` = `TRIGGER_15_ANTRAG[0]`)
  und `schema_version` auf 22 – die umgebaute Tabelle (Spalte `group_id`, breiterer CHECK) stört Code 22 nicht.

### Schnittstelle

| Route | Wer | Was |
| --- | --- | --- |
| `POST /api/material/artikel/<id>/antrag` (`product_id`, `serial_no`, `manufactured_on`, `purchased_on`, `first_use_on`, `retire_by`, `interval_months` – nur Abweichungen zählen; `begruendung` Pflicht) | Materialwart oder Prüfer am Artikel (fremd 404, nur lesen 403) | Sammelantrag → 201 `antrag` (`id` = Antrag-Nr., `aenderungen` [{`feld`, `feld_text`, `alt`, `neu`, `alt_text`, `neu_text`, `passt`}], `felder_text`, `status`, `begruendung`, `antragsteller`, `eigen`, `passt`, `entfernen`, `entscheiden`, `ohne_zustaendige`, `rueckruf`), `artikel`, `mail`; 400 Eingaben (auch „nichts geändert“), 409 ungeprüft, ausgesondert, schon ein offener Antrag, Dublette, Set/Teil, Set-Produkt, offener Entwurf, DEMO-Grenze. Statt `antraege` (Liste je Feld) jetzt `antrag` |
| `GET /api/material/antraege?status=offen\|erledigt\|alle` (Vorgabe offen) | Modulzugang | Sammelanträge: eigene zu lesbaren Artikeln und die, die das Konto entscheiden darf; je Antrag `artikel` und `entscheiden`; `zu_entscheiden` (die Zahl der Blase). `alle`, `bearbeiten`, `offen`, `meldungen_offen` entfallen |
| `POST /api/material/antraege/<id>/bestaetigen`, `…/ablehnen`, `…/zurueckziehen` | Modulzugang; entscheiden die Materialwarte des Ordners (rechte „freigeben“, eigener Antrag eingeschlossen) – nicht lesbar 404, lesbar 403; zurückziehen nur der Antragsteller | wirkt auf den ganzen Sammelantrag (auch mit der Kennung einer Folgezeile); bestätigen zieht Lebensende, Länge und Fälligkeit nach (`faelligkeit.kappen`) |
| `PUT /api/material/artikel/<id>` | Materialwart **oder Prüfer** am Artikel | Prüfer nur `notes`, `length_m`, `next_due_on` (sonst 403); nach der ersten Prüfung 409 bei jeder Abweichung in den freigabepflichtigen Feldern |
| `GET /api/material/artikel/<id>` | wie bisher | neu `antrag_offen`, `darf_entscheiden`, `produkt_beantragbar`; `darf_antrag` nur ohne offenen Antrag; `herstellung_nachtragbar` entfällt |
| `GET /api/material/start` | wie bisher | `antraege_offen` = offene Anträge, die das Konto entscheiden darf (für jedes Konto, nicht mehr nur die Material-Verwaltung) |
| `GET /api/material/meldungen` | wie bisher | `antraege_offen` entfällt |
| `GET /material/bestand/antraege?status=` | Modulzugang (Seite) | neue Seite (Ansicht `antraege`) |
| `GET /material/katalog/meldungen?bereich=antraege[&status=]` | – | 302 auf `/material/bestand/antraege[?status=]` |

### Entscheidungen des Nutzers (24.10.2026)

- **E1** Freigabepflichtig nach der ersten Prüfung: Produkt, Seriennummer, Herstellung, Kauf, Erstgebrauch, Lebensende
  (auch vorziehen), Prüfintervall am Artikel; Länge nicht.
- **E2** Bemerkung, Länge und „Nächste Prüfung vorziehen“ direkt – durch Prüfer und Materialwart.
- **E3** Leere Felder nachtragen immer per Antrag.
- **E4** Produkt am Artikel nach der ersten Prüfung per Antrag (Grenzen und Folgen wie vor der Prüfung).
- **E5** Kein Vier-Augen; Rückfall-Mail an die Material-Verwaltung nur ohne jedes zuständige Konto.
- **E6** Die Material-Verwaltung entscheidet nur mit eigener Freigabe „verwalten“ und darf sie sich selbst geben.
- **E7** Nur Arbeitsliste, Blase, Übersicht und Mail hängen am Ordnerrecht; Artikelseite und Journal wie bisher.
- **E8** Katalogprodukte bleiben bearbeitbar; jede Produktänderung im Produktjournal und im Journal/Lebenslauf der
  Artikel; Löschen eines Produkts mit Artikeln bleibt gesperrt.

### Abweichungen vom Entwurf

- **Schemaschritt 23** statt 22 (Auftrag: Schritt 22 gehört „Sets anlegen“); Länge ist nicht freigabepflichtig (E1),
  deshalb kein Längen-Sonderfall im Trigger; kein Vier-Augen-Trigger (E5).
- **Lebensende im Antrag**: der Trigger schützt das von Hand gesetzte Lebensende (`retire_by_manual`), nicht das
  wirksame `retire_by` – sonst sperrte er jede Folge einer Herstellungs- oder Katalogänderung. Beantragt wird nur
  vorziehen (vor dem heutigen Lebensende und vor der Rechnung).
- **Zahl der Blase** zählt eigene Anträge mit, wenn der Antragsteller zuständig ist (E5 – er entscheidet sie selbst);
  der Entwurf hatte sie wegen Vier-Augen ausgenommen.
- **Artikeljournal und Produktänderung** (E8): Das Journal am Artikel las das Produktjournal schon (journal.fuer_artikel);
  es kommt kein zusätzlicher Eintrag je Artikel dazu (bei 500 Artikeln eines Produkts wären das 500 Zeilen je
  Katalogkorrektur, und das Artikeljournal zeigte jede Änderung doppelt). Neu ist nur der Lebenslauf.
- Das neue Recht `freigeben` steht weder in `darf_alles` noch im Feld `darf` an Ordnern und Artikeln (die Oberfläche
  fragt es am Antrag und an `artikel.darf_entscheiden` ab).
- „Änderung beantragen …“ bleibt auf der Artikelseite in den Stammdaten für alle, die beantragen dürfen (auch den
  Materialwart) – zusätzlich zum Knopf im Dialog „Bearbeiten“; nur der Hilfetext darunter ist weg.

### Nachtrag: Lebensende per Antrag auch nach hinten (Entscheidung des Nutzers, 25.10.2026, Schritt 24)

- **Antrag**: Das Feld „Lebensende“ (vorher „Lebensende (nur vorziehen)“) nimmt jedes Datum bis zur Rechnung aus
  Herstellung und Lebensdauer – vorziehen wie bisher, ein vorgezogenes wieder nach hinten. Die Hilfe am Feld nennt die
  Grenze („Vorziehen oder wieder nach hinten – höchstens bis TT.MM.JJJJ (Herstellung + n Jahre).“); darüber 400
  „Das Lebensende lässt sich höchstens bis zur Rechnung aus Herstellung und Lebensdauer setzen (TT.MM.JJJJ).“ Ändert
  derselbe Antrag die Herstellung (oder das Produkt), gilt die neue Rechnung; beim Bestätigen wird noch einmal mit der
  Rechnung von dann geprüft (eine inzwischen verkürzte Lebensdauer → 400, der Antrag lässt sich nur noch ablehnen).
- **Genau auf die Rechnung** heißt: nicht mehr von Hand gesetzt – `retire_by_manual` wird leer, das Lebensende folgt
  danach wieder Herstellung und Katalogkorrekturen; die Artikelseite sagt „n Jahre ab Herstellung“ statt „von Hand
  vorgezogen“. Ergäbe sich das beantragte Datum ohnehin aus den übrigen Änderungen desselben Antrags, lehnt der Server
  das Feld ab („… bitte das Feld „Lebensende“ unverändert lassen.“) – sonst bliebe die Antragszeile unangewendet.
- `GET /api/material/artikel/<id>`: `lebensdauer.berechnet` (die Rechnung, für die Hilfe im Dialog).
- **Schritt 24** (wiederholbar): Die Trigger aus 23 kannten beim Lebensende nur „neuer Wert = `retire_by_manual`“, und
  der neue Wert eines Antrags ist nie leer (CHECK) – das Zurücksetzen auf die Rechnung ging deshalb nicht ohne neuen
  Schritt. `mat_item_stammdaten_fest` und `mat_item_antrag_angewendet` (gleiche Namen ersetzt, `TRIGGER_24_ARTIKEL`)
  decken zusätzlich: `retire_by_manual` wird leer **und** das wirksame `retire_by` derselben Anweisung ist der beantragte
  Wert – weiterhin nur mit bestätigtem, noch nicht angewendetem Antrag mit genau diesem alten Wert, und nur einmal.
  Sonst alles wie Schritt 23; keine Tabelle, keine Zeile. Die Bedingung schwächt nichts ab: Ohne Antrag bleibt
  `retire_by_manual` nach der ersten Prüfung fest.
- Geprüft: frisch (Trigger gleich dem Stand nach 23 → 24), 23 → 24 mit offenem Antrag (wird danach bestätigt), zweiter
  Lauf ohne Änderung (`test_material_antrag_zustaendig.test_migration_24`); Trigger an der Schnittstelle vorbei
  (`test_trigger_24`); Ablauf `test_lebensende_nach_hinten`.
- **Rückweg** auf Schema 23: die zwei Trigger in der Fassung `TRIGGER_23_ARTIKEL[0]` und `[2]` neu anlegen und
  `schema_version` auf 23 – Artikel mit leerem `retire_by_manual` nach einem Rücksetzen stören Code 23 nicht.
- Unverändert: Vor der ersten Prüfung lässt der Dialog „Bearbeiten“ das Lebensende weiterhin nur vorziehen (siehe
  „Bitte bestätigen“ im Abschnitt „Wünsche vom 25.10.2026“). Entschieden am 25.10.2026 (W2): bleibt so – vor der ersten
  Prüfung nur vorziehen; zurück erst nach ihr per Antrag, höchstens bis zur Rechnung.

### Bitte bestätigen

1. ~~Ein Lebensende lässt sich per Antrag nur **vorziehen** …~~ **Entschieden am 25.10.2026:** Ein Antrag darf ein
   vorgezogenes Lebensende auch wieder nach hinten setzen, höchstens bis zum berechneten Lebensende (Herstellung +
   Lebensdauer des Produkts) – umgesetzt mit Schritt 24, siehe „Nachtrag: Lebensende per Antrag auch nach hinten“.
2. Prüfer bearbeiten Bemerkung, Länge und nächste Prüfung auch **vor** der ersten Prüfung (Entscheidung E2 nennt keinen
   Zeitpunkt); die übrigen Felder bleiben dann dem Materialwart. Präzisiert am 26.10.2026 (Feinschliff aus den
   Wiki-Fragen, Punkt 17 – gilt wie gebaut, N1 der Freigabeliste L2c): Bemerkung und Länge vor und nach der ersten
   Prüfung; das Feld „Nächste Prüfung“ zeigt der Dialog erst nach ihr – vorher steht dort „Eingangsprüfung
   ausstehend“, für Prüfer wie für den Materialwart (so seit Lieferung 2).
3. Die Zahl an „Änderungsanträge“ und auf der Übersicht zählt die eigenen offenen Anträge mit, wenn man zuständig ist.
4. Altanträge (vor Schritt 23 gestellt) bleiben Einzelanträge – ein damals gemeinsam gestellter Antrag auf Seriennummer
   und Herstellung erscheint als zwei Karten; Mails dazu gehen beim Umstieg keine.
5. Der Lebenslauf zeigt Produktänderungen ab dem Anlegen des Artikels (nicht die davor) und ohne Rückrufzeilen.
6. Rückweg nur über die Datensicherung, sobald ein Antrag auf ein neues Feld gestellt ist (siehe Schritt 23).

## Sets anlegen und Stückliste übertragen (Wunsch des Nutzers, 24.10.2026)

> **Zurückgebaut durch Schritt 26** (Wunsch des Nutzers, 25.10.2026) – siehe „Rückbau der Set-Funktion“. Der Abschnitt
> bleibt als Geschichte stehen.

Wünsche: „Sets sollen durch Verwalter mit einem neuen Button eigenständig erstellbar sein und bestehende Sets mit seinen
Bestandteilen bearbeitbar“ und – nachgereicht mit einem Bildschirmfoto des Dialogs „Fehlendes Produkt melden“ –
„Fehlendes Produkt anfrage funktion und im Text beschreiben soll auch anfragen für individuelle Sets umfassen“.
Grundlage: Bauentwurf `entwurf_sets_anlegen_uebertragen.md` mit den Entscheidungen S1–S8 (unten). **Schema 22.**

### Was neu ist

- **„Set anlegen“** (Material-Verwaltung): im Katalogkopf neben „Produkt anlegen“ ein grau umrandeter Knopf „Set anlegen“
  (am Telefon „+ Set“). Er öffnet den Produktdialog im Set-Modus: Titel „Set anlegen“, Reiter „Produkt“ (die Felder wie
  bisher, darüber ein Satz, was ein Set ist) und „Bestandteile“ (die Stückliste wie bisher). „Anlegen“ schickt Produkt
  **und** Stückliste in **einer** Anfrage (`POST /produkte` mit `is_set` und `bestandteile`) – scheitert eine Position,
  entsteht nichts, die Position ist markiert, der Dialog steht im Reiter „Bestandteile“. Bearbeiten heißt „Set
  bearbeiten“ (erst die Stammdaten, dann – falls geändert – die Stückliste mit `PUT …/bestandteile`). Das Häkchen
  „Hersteller-Set“ gibt es nicht mehr.
- **Pflicht** (S3): Ein Set braucht mindestens **ein einzeln geführtes Teil** – beim Anlegen, als Variante, beim Ersetzen
  der Stückliste (auch leer geht nicht mehr) und im Katalogimport (dort ein Fehler dieses Produkts, auch bei
  `"set": true` ohne `bestandteile` an einem Produkt ohne Stückliste). Text: „Ein Set braucht mindestens ein einzeln
  geführtes Teil.“ Geprüft wurde die Gesamtserie (`katalog-import/gesamt/lieferung/katalog.json`, Stand 24.10.2026):
  1 250 Produkte, 74 Sets, alle mit mindestens einer einzeln geführten Position.
- **Umstellen Produkt ↔ Set** (S2) nur noch über die Katalogdatei, solange es keine Artikel gibt: `PUT /produkte/<pid>`
  mit einem abweichenden `is_set` → 409 („Ob ein Produkt ein Set ist, legt das Anlegen fest …“), mit gleichem 200.
  `set_umschalten` ruft nur noch der Katalogimport.
- **Variante folgt dem Vorbild**: Die Variante eines Sets ist ein Set (der Dialog öffnet im Set-Modus mit der Stückliste
  des Vorbilds zum Bearbeiten; ohne `bestandteile` übernimmt der Server die des Vorbilds), die eines Produkts ein Produkt
  (`bestandteile` dann 400). Das Feld `stueckliste` und das Häkchen „Stückliste übernehmen“ entfallen.
- **Stückliste übertragen** (Entwurf B, S4–S7): Angelegte Sets behalten ihre Kopie der Stückliste. Nach dem Speichern
  sagt die Quittung „Gespeichert – n angelegte Sets haben noch die bisherige Stückliste.“; die Produktseite zeigt im
  Abschnitt „Stückliste“ den Hinweis „n angelegte Sets haben eine ältere Stückliste.“ und den Knopf „Auf vorhandene Sets
  übertragen …“ (beides nur für die Material-Verwaltung; der Hinweis bleibt, bis alles übertragen ist). Der Dialog
  „Stückliste übertragen“ zeigt je Gruppe gleicher bisheriger Stückliste einen Vergleich Position | bisher | jetzt |
  Wirkung (neu, entfällt, Anzahl a → b, jetzt einzeln geführt / ohne eigenen Artikel, anderes Produkt, Bezeichnung,
  Austausch, Reihenfolge – zugeordnet nur zur Anzeige) und darunter die Sets der Gruppe mit Inventarnummer (Link),
  Ordner, Status, Herstellung und Wirkung („bleibt frei – nur Angaben“, „gesperrt bis zur Set-Prüfung: „X“ fehlt 1×;
  M-… steht nicht mehr in der Stückliste“); alle übertragbaren sind gewählt (S4), die übrigen stehen mit Grund ohne
  Auswahl da. Die Schlusszeile zählt mit („Übertragen auf n Sets – k davon danach gesperrt bis zur Set-Prüfung.“).
- **Wirkung** (S5, S6): Die Kopie wird als Ganzes ersetzt; Teil-Artikel bewegen sich nicht. Fehlt danach ein einzeln
  geführtes Teil oder ist eines übrig (keiner Position mehr zugeteilt), ist das Set gesperrt (Sperr-Kaskade wie beim
  Entnehmen, Anlass „Stückliste übertragen“): Der Materialwart setzt das fehlende Teil mit „Teil einsetzen“ ein bzw.
  nimmt das übrige mit „Teil entnehmen“ heraus (weiterführen oder aussondern, er wählt das Stück) – frei wird es nur
  über „Set prüfen“. Ein übriges Teil steht im Set-Kasten mit „steht nicht mehr in der Stückliste“, sein Untermenü
  „Austausch“ bietet nur „Teil entnehmen …“; „Gesperrt, weil“ nennt es mit Link („… – erst „Teil entnehmen““), und die
  Set-Prüfung gibt nicht frei, solange es im Set ist. Bezeichnung, Austausch, Reihenfolge und Bestandteile ohne eigenen
  Artikel sperren nicht; die nächste Set-Prüfung fragt die Bestandteile nach der neuen Kopie ab.
- **Nicht übertragbar** (mit Grund): laufende Set-Prüfung, offene Prüfung am Set selbst, danach fehlte ein Teil an einer
  Position mit „Austausch laut Hersteller: nein“, der Systemordner „Gesperrt“ fehlt (nur wenn das Set sperren müsste).
  Nur gezählt: ausgesonderte Sets und Sets, die die Stückliste schon haben. Kein Ausschluss: Sperre, Mangel, Rückruf,
  DEMO. Der ganze Vorgang 409, wenn das Produkt kein Set ist oder seine Stückliste leer ist bzw. (Altbestand) kein
  einzeln geführtes Teil hat.
- **Set melden** (S8): Der Dialog heißt „Fehlendes Produkt oder Set melden“ und erklärt in einem Satz, was ein Set ist;
  oben die Wahl „Was fehlt? Produkt | Set“ (Vorgabe Produkt), bei „Set“ das Pflichtfeld „Teile des Sets“ (je Zeile ein
  Teil: Hersteller, Modell, Anzahl; höchstens 2 000 Zeichen wie die Bemerkung). Die Auslöser heißen „Fehlt das Produkt
  oder Set im Katalog? Fehlendes Produkt oder Set melden“ bzw. „Als fehlendes Produkt oder Set melden“. Aus der
  Nacharbeit eines Bestandsimports bleibt es „Fehlendes Produkt melden“ (die Nacharbeit nimmt kein Set). In „Katalog →
  Meldungen“ trägt eine Set-Meldung die Marke „Set“ und ihre Teile; der Knopf heißt „Set anlegen“ und öffnet den
  Set-Dialog vorbelegt („Set aus Meldung anlegen“, im Reiter „Bestandteile“ die gemeldeten Teile als Vorlage); Anlegen
  und Erledigen geschehen in einem Zug, der Melder bekommt die Mail wie bisher („das von dir gemeldete Set ist jetzt im
  Katalog“). „Vorhandenes zuordnen“ nimmt auch ein Set. Die Mail an die Material-Verwaltung heißt „Set-Meldung: …“ und
  nennt die Teile.
- **Begriff** (S1): überall „Set“ statt „Hersteller-Set“ (Oberfläche, Meldungen, Mails, Journal- und Berichtstexte, PDF,
  README, Docstrings). Die Ordnerart „Set“ heißt jetzt **„Set-Ordner“** (Schlüssel `set` bleibt): Sie stand in
  Ordnerlisten, im Ordnerkopf, in der Ordnerwahl und im Dialog „Ordner anlegen/bearbeiten“ neben der Marke „Set“ der
  Set-Artikel (etwa „DEMO-Seilrucksack“ mit einem Set darin). Unverändert bleiben die Texte der Datenbank-Trigger aus
  Schritt 21 („Hersteller-Set“ in drei RAISE-Meldungen – Schritt 21 bleibt, wie er ausgeliefert wurde; die Oberfläche
  zeigt sie nie, der Dienst weist vorher mit eigenem Text ab) und die älteren Abschnitte dieses CHANGELOG.

### Schritt 22 (in sich abgeschlossen, wiederholbar)

- `mat_slot_neu` und `mat_slot_loeschen` werden entfernt und neu angelegt: Einfügen in die Kopie nur an einem
  Set-Artikel (Produkt mit `is_set`, selbst kein Teil), Einfügen und Löschen **nie** an einem ausgesonderten Set und
  **nie** während einer offenen Set-Prüfung; INSERT OR REPLACE über eine vorhandene Kennung bleibt verboten,
  `mat_slot_aendern` (nie ein UPDATE) bleibt. Das Löschen mit dem Set (ON DELETE CASCADE) geht weiter.
- `mat_product_request.is_set` (INTEGER NOT NULL DEFAULT 0, CHECK 0/1) und `set_teile` (TEXT NOT NULL DEFAULT '') per
  ADD COLUMN, nur wenn sie fehlen.
- Keine Zeile ändert sich. Geprüft: frisch, 21 → 22 mit Altbestand (Set mit Teilen, Produktmeldung) und zweiter Lauf
  (`tests/test_material_sets_uebertragen.py`), 20 → 22 (`test_material_sets.test_migration_21`), ältere Stände über die
  vorhandenen Migrationstests.
- **Rückweg** auf 078fb4b (Schema 21): unkritisch. Code 21 findet Schema 22 vor und lässt es (Version höher); die neuen
  Spalten liest er nicht, die neuen Trigger stören ihn nicht (er schreibt Kopien nur beim Anlegen eines Sets). Neue
  Journal-Aktionen („stueckliste_uebertragen“, „nicht_in_stueckliste“) zeigt er roh. Ein übriges Teil aus einem
  Übertragen behandelt Code 21 wie Altbestand („mehr Stücke als die Kopie“): Es hält eine Freigabe nicht auf – vor einem
  Rückweg übrige Teile entnehmen. Set-Meldungen erscheinen dort als Produktmeldungen ohne Teile.

### Journal, Jahresbericht, Mails

- Am Set „Stückliste übertragen“ (vorher die alte Kopie; nachher die neue, was fehlt, welche Teile nicht mehr in der
  Stückliste stehen; Handelnder mit Namen), bei neuer Sperre „gesperrt“ mit Anlass „Stückliste übertragen“ und an den
  Teilen „mit dem Set gesperrt“ als „System“, an jedem übrigen Teil „steht nicht mehr in der Stückliste des Sets“. Kein
  Eintrag am Produkt (dessen Journal sieht jeder mit Modulzugang – es nennt keine Inventarnummern).
- Jahresbericht: Die Sperre aus dem Übertragen zählt einmal als Art „set“ („Set unvollständig, Teil getauscht oder
  eingesetzt, Bestandteil ersetzt oder Stückliste übertragen“).
- Katalogimport: Ersetzt er die Stückliste eines Sets, sagt der Bericht als Hinweis „k angelegte Sets haben die
  bisherige Stückliste – übertragen auf der Produktseite“; der Import überträgt nie selbst.
- Keine neue Mailart (eine neue Art hieße Tabellenumbau); sichtbar wird eine Sperre wie jede andere (Listen, „Fällige“,
  Übersicht, Banner, „Meine PSA“, Lebenslauf).

### Schnittstelle

| Route | Wer | Was |
| --- | --- | --- |
| `POST /api/material/produkte` (dazu `is_set: true`, `bestandteile`: Positionen wie `PUT …/bestandteile`) | Katalog | Set anlegen: Produkt und Stückliste in einer Transaktion → 201 `produkt`. `is_set` ohne Liste oder leer 400, `bestandteile` ohne `is_set` 400 (seit Schritt 25: Bestandteil-Liste eines Produkts, 201), ohne einzeln geführtes Teil 400, Fehler „Position n: …“ 400 – dann entsteht nichts |
| `PUT /api/material/produkte/<pid>` | Katalog | `is_set` abweichend 409, gleich ohne Wirkung |
| `POST /api/material/produkte/<pid>/variante` | Katalog | Variante eines Sets ist ein Set (`bestandteile` oder die des Vorbilds); eines Produkts ein Produkt (`bestandteile` 400; seit Schritt 25 seine Bestandteil-Liste); `stueckliste` und `is_set` zählen nicht mehr |
| `PUT /api/material/produkte/<pid>/bestandteile` | Katalog | wie bisher, aber nie leer und mindestens ein einzeln geführtes Teil (400) |
| `GET /api/material/produkte/<pid>` | lesen | neu `sets_aelter` (nur Material-Verwaltung, nur an Sets); `set_umschaltbar` und `set_umschalt_grund` entfallen |
| `GET /api/material/produkte/<pid>/stueckliste-uebertragen` | Katalog | Vorschau `{produkt {id, name}, stand, gruppen [{vergleich [{position, bisher, jetzt, wirkung}], sets [{id, inventory_no, ordner, status, status_text, lock_state, manufactured_on, demo, uebertragbar, grund, sperrt, wirkung}]}], ausgesondert, gleich, uebertragbar, sperrt}`; 409 kein Set / Stückliste leer oder ohne einzeln geführtes Teil |
| `POST /api/material/produkte/<pid>/stueckliste-uebertragen` (`stand`, `set_ids`) | Katalog | übertragen in einer Transaktion → `{uebertragen, gesperrt, produkt}`; leere Wahl 400; anderer `stand` („Inzwischen geändert“) oder ein nicht übertragbares Set 409 – nichts geschrieben |
| `POST /api/material/meldungen` (dazu `is_set`, `set_teile`) | Materialwart | Set melden; bei `is_set` sind `set_teile` Pflicht (400), sonst werden sie nicht gespeichert; Antwort `meldung` mit `is_set`, `set_teile` |
| `POST /api/material/meldungen/<mid>/produkt` (Felder wie `POST /produkte`) | Katalog | mit `is_set` und `bestandteile` ein Set aus der Meldung – atomar mit dem Erledigen |

Rechte unverändert: Stückliste pflegen und übertragen nur die Material-Verwaltung (`katalog_required`, S7);
Materialwarte setzen physische Teile ein, entnehmen und tauschen wie bisher.

### Entscheidungen des Nutzers (24.10.2026)

- **S1** Begriff überall „Set“; Ordnerart „Set-Ordner“, wo beides zusammentrifft (umgesetzt: die Beschriftung der
  Ordnerart überall).
- **S2** Umwandeln Produkt ↔ Set nur per Katalogdatei; `PUT` mit abweichendem `is_set` 409.
- **S3** Pflicht mindestens ein einzeln geführtes Teil – Oberfläche, Server, Variante, Ersetzen, Katalogimport.
- **S4** Übertragen je Set wählbar, alle vorbelegt, Herstellung zur Orientierung.
- **S5** Ein Teil, das nicht mehr in der Stückliste steht, bleibt im Set; das Set ist gesperrt; der Verwalter entnimmt es.
- **S6** Sperre nur, wenn danach ein einzeln geführtes Teil fehlt oder eines übrig ist.
- **S7** Stückliste pflegen und übertragen nur die Material-Verwaltung.
- **S8** Fehlendes Produkt **oder Set** melden; Set aus der Meldung über den Set-Dialog, atomar; Zuordnen auch mit Set.

### Bitte bestätigen

1. Die Variante folgt dem Vorbild (die eines Sets ist immer ein Set).
2. Der Katalogimport überträgt nie selbst (nur der Hinweis im Bericht).
3. Keine Mail beim Übertragen; kein Produktjournal-Eintrag mit Inventarnummern.
4. Eine Lücke an einer Position mit „Austausch: nein“ macht das Set nicht übertragbar; ausgesonderte Sets und Sets mit
   laufender Set-Prüfung bleiben, wie sie sind.
5. Ordnerart heißt überall „Set-Ordner“ (nicht nur an einzelnen Stellen).
6. S8: Die Wahl „Produkt | Set“ steht als Auswahlknöpfe unter „Was fehlt?“; „Teile des Sets“ hat die Grenze der
   Bemerkung (2 000 Zeichen); aus der Nacharbeit eines Bestandsimports gibt es nur Produktmeldungen; eine Set-Meldung
   darf die Material-Verwaltung auch einem einfachen Produkt zuordnen.
7. Die Texte der Datenbank-Trigger aus Schritt 21 behalten „Hersteller-Set“ (Schritt 21 bleibt, wie ausgeliefert).

## Beispielbestand: Nachbesserung nach der Sicherheits- und der Ablaufprüfung (25.10.2026)

Beide Prüfungen sahen den Stand befaf58 als deploybar an, den **Lauf** auf dev aber erst nach Nachbesserung. Behoben:

| Nr. | Befund | Stufe | Behebung |
| --- | --- | --- | --- |
| S1 | Der Lauf hielt die Schreibsperre fast ununterbrochen; auf dev scheiterten Schreibzugriffe und Anmeldungen (500) | mittel | Nach jedem Vorgang 0,05 s Pause (`PAUSE` in `_versuch`, auch nach einem abgelehnten). README: dev ist während des Laufs nur eingeschränkt benutzbar, Laufzeit mit Pause und unter Last |
| S2 | Vorhandene „DEMO-…“-Konten wurden nur am Namen erkannt: eine offene Kontoanfrage auf `demo-mv@…` wurde zur Material-Verwaltung hochgestuft, eine auf `demo-pruefer@…` ließ den Lauf mittendrin scheitern | mittel | `konten_pruefen` vor jedem Schreiben: übernommen wird nur ein Konto „DEMO-…“ mit `active = 1` und `status = 'active'`, das die Stufe seiner Rolle schon hat (Prüfer mit gültiger Urkundennummer); sonst Abbruch mit Adresse und Grund, nichts angelegt. Kein Konto wird hochgestuft oder in seinen Rollen geändert – der Bericht nennt Abweichungen (höhere Stufe, weitere Module). Test `test_konten` (offene Kontoanfrage, deaktiviertes Konto, fehlende Stufe, Prüfer ohne Urkunde; passendes Konto bleibt unverändert) |
| S3 | Ohne `BASE_URL` belegte das Skript im Klon selbst `http://localhost:8080` vor; die dev-Kennung fehlte | niedrig | Keine Vorbelegung mehr – fehlt `BASE_URL`, Abbruch. Dazu wie bei `dev-zuruecksetzen` `STROEMIS_NAME` auf `-dev` – ohne sie nur, wenn beide Adressen localhost/127.0.0.1 sind. Test in `test_ohne_schalter` |
| S4 | README: Strg-C und SSH-Abriss beenden den Lauf im Container nicht | niedrig | README: in `tmux`/`screen` starten, Ausgabe mit den Passwörtern sichern; der Befehl legt die PID in `/tmp/bb/pid` ab (`exec python …`), Abbruch mit `docker exec stroemis-dev sh -c 'kill -TERM "$(cat /tmp/bb/pid)"'` |
| S5 | „Neue Version“ eines DEMO-Formulars verlor das DEMO-Kennzeichen; die Petzl-Punkte kamen so in den Katalog-Export | niedrig | **App** (`katalog.formular_anlegen`): Übernimmt die neue Version die Punkte einer DEMO-Vorlage (ohne eigene Punkte, wie „Neue Version“ und „Formular anlegen“ der Oberfläche), bleibt sie DEMO. Mit eigenen Punkten (Katalogimport) zählt wie bisher nur der Parameter. Test `test_neue_version_demo` (Export ohne die neue Version) |
| S6 | Der Merker hieß wie beim alten kleinen Beispielbestand – ein abgebrochener Lauf galt dann als „schon da“ | niedrig | Eigener Schlüssel `beispielbestand_gross`. Test in `test_abgebrochener_lauf` (mit altem Merker) |
| S– | Bei sehr großem `--artikel` lief die Uhr über heute hinaus | Verbesserung | `Uhr.stellen` kappt bei gestern (heute läuft mit der echten Uhr). Test `test_uhr`, in `test_beispielbestand` keine Prüfung nach heute |
| A1 | Typ per Teilstring über den Kategoriepfad: Abseilgeräte, Abseilachten und Seilklemmen galten als Seile, Bandmaterial und Flaschenzüge als „sonstiges“ | mittel | `typ_fuer`: am Kategorienamen, die unterste Ebene zuerst; „abseil“ vor „seil“, Seilklemmen eigener Typ, Band- und Textilmaterial Schlingen, „flaschenz“ Rollen. Test `test_typen` mit den echten Kategorienamen beider Katalogstände |
| A2 | Ausgeschiedene Einsatzkräfte bekamen nach dem Austritt noch Ausrüstung (auch in ihren persönlichen Ordner) | mittel | Nach dem Austritt gehen alle Pläne der Person (auch noch nicht angelegte, Ersatz für Ausgesondertes) ohne Person in die Reserve; beim Anlegen wird das noch einmal geprüft. Test: keine Zuordnung nach dem Austrittstag, nichts Neues im Ordner, „Meine PSA“ leer |
| A3 | Gewöhnlicher Mangel („instandsetzen“) auf einem kritischen Punkt; fast alle Mängel auf „Seriennummer/CE lesbar“ | mittel | Gewöhnliche Mängel nur auf nicht kritischen Punkten, kritische nur bei Aussonderung; gestreut, die vorangehenden Kontrollen nur ohne Alternative. Test `test_mangelpunkt` mit den Petzl-Punkten, in `test_beispielbestand` kein „instandsetzen“ mit kritischem Mangel |
| A4 | Aussonderung wegen Lebensdauer mit „Lebensdauer nicht überschritten: ja“ | niedrig | Beim Lebensende weicht der Punkt zur Lebensdauer vom Soll ab (mit DEMO-Notiz und Platzhalterfoto); ein Formular ohne solchen Punkt bleibt ohne Abweichung |
| A5 | Petzl-Vorlage „Textilmaterial“ griff beim Katalogstand von dev („Bandmaterial“) nicht | niedrig | Alias `PETZL_ALIAS` „Bandmaterial“ → „Textilmaterial“. Test in `test_typen` |
| A6 | Antragszustand „abgelehnt“ fehlte im Standardlauf | niedrig | `sicherstellen` stellt je fehlendem Zustand (bestätigt, abgelehnt, zurückgezogen, offen) heute einen Antrag. Test: alle vier kommen vor |
| A7 | `applied_at` bestätigter Anträge trägt den Lauftag (Trigger mit SQLite-Zeit) | niedrig | Nicht umgangen (der Trigger bleibt), als bekannte Grenze in README und Docstring |

Dazu: Die persönliche Ausrüstung ist von Anfang an da (kein Nachkauf ohne Vorgänger – keine Einsatzkraft lange ohne
Gurt; Ersatz nach Aussonderungen bleibt). Die Testaussage „nichts länger als 60 Tage überfällig“ gilt jetzt mit
Ausnahme verschobener Artikel (die zwischen die Runden zweier Bereiche fallen können). Nicht geändert: Die erste Prüfung
des Erstbestands im Durchgang bleibt „Eingangsprüfung“ – ohne abgeschlossene Prüfung lässt die App keine andere Art zu
(`pruefung.arten_fuer`). Läufe mit 60 Artikeln gegen Teile der Lieferung 20261024 (Stand von dev, „Bandmaterial“) und der
aktuellen Lieferung („Textilmaterial“): Regal Seile nur mit Seilen, persönliche Ausrüstung Gurt, zwei Karabiner,
Schlinge, Abseilgerät. Laufzeit bei 800 Artikeln 27:34 min neben der laufenden Testsuite (830 Artikel, 1 822 Protokolle, 33 Aussonderungen – davon 7 wegen Lebensdauer, Lebensdauer-Punkt „nein“ –, kein „instandsetzen“ mit kritischem Mangel, 56 Mängel auf 27 Punkten, Anträge 8/4/4/1). Kein Schemaschritt.

## DEMO-Skript entfernt (Wunsch des Nutzers, 25.10.2026)

`scripts/material_demo.py` ist entfernt („Entferne das Demo-Skript material_demo.py, es wird dann nicht mehr
gebraucht.“), ebenso `scripts/beispieldaten.py` (Prüfungsbereich, CHANGELOG-Pruefungen.md). Was es leistete und weiter
gebraucht wird, macht `scripts/material_beispielbestand.py`: DEMO-Konten mit den bekannten Postfächern (vorhandene werden
übernommen, der Prüfer prüft dauerhaft, der externe befristet), DEMO-Unterschriften im Profil der Prüfer und
Materialwarte (für die Protokolle), Platzhalter- bzw. Petzl-Formulare, die dev-Sperre. Der kleine DEMO-Katalog
(DEMO-Kategorien, -Produkte, -Set) entfällt – der Beispielbestand braucht den echten Katalog. Entfallen sind auch die
Übergänge für alte dev-Stände (befristete DEMO-Prüffreigabe auf dauerhaft, Protokolle nachreichen). Tests: die
Prüfungen des DEMO-Skripts selbst sind gestrichen (test_material_freigaben: zweimal hintereinander, Prüfer von früher;
test_material_beschreibung: DEMO-Produkte ohne Beschreibung; test_material_sets: DEMO-Set;
test_material_demo_formulare.py) – die Konten, die Material-Verwaltung und die Formulare prüft jetzt
test_material_beispielbestand; test_material_dev_zuruecksetzen baut seinen Bestand mit einem eigenen Set und einem
kleinen Beispielbestand und lässt ihn nach dem Zurücksetzen (mit neuem Katalog) wieder laufen. Hinweistexte in
`services/zuruecksetzen.py` angepasst; README: Anleitung, wie Browserproben an DEMO-Daten kommen. Kein App-Verhalten
geändert, kein Schemaschritt.

## Beispielbestand: große Gliederung mit zwei Jahren Geschichte (Wunsch des Nutzers, 25.10.2026)

`scripts/material_beispielbestand.py` baut statt der drei kleinen DEMO-OGs den Bestand einer großen Gliederung aus dem
echten Katalog: „DEMO-Kreisverband Flussland“ (Zentrallager mit Regalen und Reserve, fünf Fahrzeuge mit Seilrucksäcken
und Taschen als Set-Ordner, auch ein Set im Set, drei Einsatzgruppen, persönliche Ordner für bis zu 40 Einsatzkräfte)
und die kleine „DEMO-OG Nachbarstadt“ für die Trennung; Vorgabe 800 Artikel, Produktmix nach Kategorien, keine Produkte
mit Stückliste. Die Geschichte reicht gut zwei Jahre zurück: Das Skript stellt die Uhr seines eigenen Prozesses zurück
(services.datetime, db.datetime, models.datetime – nie in der App) und spielt Ersterfassung, jährliche Prüfdurchgänge je
Bereich mit Sammelprotokoll, Einzel- und außerplanmäßige Prüfungen, Mängel mit Reparatur, Aussonderungen mit Nachkauf,
Verluste, Verschiebungen, Zuordnungen (auch beendete) und Änderungsanträge Tag für Tag über die Dienste der App ab;
heute ein offener Durchgang im Zentrallager, ein überfälliger und ein bald fälliger Bereich. Fehlt einer echten
Kategorie ein wirksames Formular, legt es DEMO-Formulare an (nicht im Katalog-Export): nach den Petzl-Prüfberichten aus
`scripts/beispielbestand_petzl_punkte.json` (Kopie der Recherche vom 25.10.2026, 13 Kategorien, 147 Punkte wörtlich mit
Fundstelle; drei zu lange Gruppenüberschriften ohne ihren Klammerzusatz, zwei zu lange Titel ohne Bezugsprodukt), sonst
Platzhalter wie `material_demo.py` seit 2edb9eb. Sperre wie `dev-zuruecksetzen` (Positivliste BASE_URL in Umgebung und
Anwendung, vorher nur „nicht die Produktion“). Konten mit den bekannten Postfächern (`demo-wart-a@…`, `demo-pruefer@…`,
`demo-extern@…`, `demo-mv@…` u. a.; vorhandene DEMO-Konten werden übernommen), Einsatzkräfte mit gemeinsamem Passwort.
Keine Mails (Hintergrund-Versender im Skriptprozess aus). Laufzeit bei 800 Artikeln rund 20 Minuten (gut eine halbe
Sekunde je Protokoll). Kein App-Code, kein Schemaschritt. Test: `tests/test_material_beispielbestand.py` (neu
`test_formulare`).

## DEMO-Skript: Platzhalter-Formulare (Wunsch des Nutzers, 25.10.2026)

`scripts/material_demo.py --demo` legt zum Schluss – nach dem unveränderten DEMO-Bestand – an jeder **echten** Kategorie
(ohne Kennzeichen demo) ohne wirksames aktives Prüfformular ein Platzhalter-Formular an: Titel „DEMO-Prüfformular
(Platzhalter) – <Kategorie>“, je ein Punkt Ja/Nein (Pflicht, Soll „ja“), Text und Zahl, bei einer Artikellänge im
Teilbaum dazu „Länge (m)“; mit DEMO-Kennzeichen und aktiviert. Es sitzt an der obersten Kategorie ohne Formular und
reicht über die Vererbung für ihren Teilbaum. Kein App-Code geändert, kein Schemaschritt. Damit lassen sich auf dev nach
dem Einspielen des echten Katalogs Prüfungen testen; der Katalog-Export lässt die Formulare wegen des Kennzeichens aus.
DEMO-Kategorien behalten ihre DEMO-Formulare (die DEMO-Kletterhelme bleiben ohne), echte Formulare bleiben unberührt –
eine Kategorie mit nur einem inaktiven echten Formular bekommt keins (aktiv verdrängte es das echte im Export), das
Skript nennt sie. Wiederholbar; nur wenn `BASE_URL` in der Umgebung und in der Anwendung auf dev oder localhost zeigt
(Positivliste wie `flask material dev-zuruecksetzen`). Test: `tests/test_material_demo_formulare.py`.

## Katalogimport im Hintergrund (Wunsch des Nutzers, 24.10.2026)

Anlass: Die kombinierte Katalogdatei (1,13 GB, 1 428 Produkte, 1 905 Dateien) bekam beim „Übernehmen“ über die
Oberfläche einen 504 vom Reverse-Proxy – der Import lief länger, als der Proxy auf die Antwort wartet. Wunsch: „Baue den
Hintergrundimport und deploye ihn“ (auf dev). Entschieden: Probelauf **und** Übernehmen laufen im Hintergrund; die
Anfrage speichert nur die Datei und antwortet sofort; der Dialog zeigt den Fortschritt und am Ende den Bericht wie
bisher. Kein Schemaschritt (Schema bleibt 21): Der Zustand eines Auftrags liegt als JSON-Datei unter `DATA_DIR`.

### Ablauf

- **Start**: `POST /api/material/katalog/import` (dieselbe Route, dieselben Rechte – Material-Verwaltung –, dieselbe
  Größengrenze `UPLOAD_GRENZEN` von 2 GB + 1 MB, ohne Datei weiter 400) legt die Datei unter
  `DATA_DIR/katalog-import/<kennung>.datei` ab (Ordner 0700, Dateien 0600), schreibt den Auftrag
  `<kennung>.json` („wartet“) und antwortet **202** mit dem Auftrag. Die Kennung ist zufällig (32 Hex-Zeichen,
  `secrets.token_hex(16)`) und wird gegen dieses Muster geprüft, bevor sie in einen Pfad kommt; kein Pfad stammt aus
  einer Eingabe (der Dateiname dient nur als Anzeige „quelle“, wie bisher auf 80 Zeichen gekürzt).
- **Lauf**: ein Thread im Arbeitsprozess, der die Anfrage angenommen hat, ruft `importer.datei_importieren(…,
  trocken=…)` auf – in einem Anfragekontext mit dem Konto, das gestartet hat: Journal (`mat_audit`: Kennung und Name)
  und Bearbeiter stehen da wie beim synchronen Import. Phasen über den neuen optionalen Rückruf des Importers
  (`fortschritt`): **Datei prüfen** (n von m Dateien), **Probedurchgang**, **Dateien ablegen** (n von m), **Datenbank
  schreiben**. Der Probelauf endet nach dem Probedurchgang. Der Zustand wird höchstens einmal je Sekunde und bei jedem
  Phasenwechsel geschrieben, das **Lebenszeichen** alle 5 s; jede Datei atomar (Zwischendatei, dann `os.replace`).
- **Ende**: Bericht nach `<kennung>.bericht.json` (das bisherige Format, unverändert), Zustand **fertig** (Bericht ohne
  Fehler) oder **fehlgeschlagen** (Bericht mit Fehlern – auch eine Datei, die sich nicht lesen lässt: synchron war
  das ein 400, jetzt ein Bericht mit diesem einen Fehler; ein unerwarteter Fehler ergibt „Der Import brach mit einem
  unerwarteten Fehler ab. Gespeichert wurde nichts; Einzelheiten stehen im Protokoll des Servers.“ – ohne Pfad), dann
  ist die hochgeladene Datei weg und die Sperre frei.
- **Übernehmen ohne neuen Upload**: Nach einem Probelauf ohne Fehler, der etwas zu übernehmen fand (Änderungen oder
  Hinweise – dieselbe Regel, nach der der Dialog den Knopf zeigt), bleibt die Datei **eine Stunde** liegen.
  `POST …/katalog/import/<kennung>/uebernehmen` startet damit den echten Lauf als neuen Auftrag (die Datei wandert zu
  ihm, der Probelauf vermerkt `uebernommen_in`). Nur wer den Probelauf gestartet hat; danach oder nach der Stunde 409
  („Die Datei des Probelaufs liegt nicht mehr bereit … Bitte die Datei noch einmal wählen.“).
- **Höchstens ein Katalogimport gleichzeitig, app-weit**: Dateisperre `DATA_DIR/katalog-import/sperre` (`fcntl.flock`,
  wie die Videopflege). Sie gehört dem Thread des Laufs und endet mit ihm – auch mit seinem Prozess. Ein zweiter Start
  (Probelauf oder Übernehmen, auch aus dem anderen Arbeitsprozess) bekommt **409** mit dem laufenden Auftrag
  („Es läuft schon ein Katalogimport von …“). Der Inhalt der Sperrdatei (Kennung, PID, Zeit) ist nur ein Hinweis;
  kaputte Sperr- und Zustandsdateien stören nicht (ein unlesbarer Zustand gilt als nicht da und ist nach einer Stunde
  weg). Die Kommandozeile (`material import-catalog`) bleibt synchron, unverändert und ohne Sperre.
- **Neustart, Deploy, Absturz**: Endet der Prozess eines Laufs, steht im Zustand noch „wartet“ oder „laeuft“. Als
  **abgebrochen** gilt er, wenn niemand die Sperre hält **und** sein Lebenszeichen älter als 30 s ist (beides – damit
  weder ein Dateisystem, auf dem flock nicht hält, noch ein langer Schritt einen lebenden Lauf für tot erklärt). Das
  stellt die nächste Abfrage fest (Dialog, Katalogseite), der nächste Start oder der Tageslauf – jeweils mit der Sperre
  in der Hand: Zustand „abgebrochen“ mit Grund, hochgeladene Datei weg, Sperre frei. In den 30 s nach dem Ende eines
  Prozesses bekommt ein neuer Start noch 409. Die **Datenbank** schreibt der Import in einer Transaktion – nach einem
  Abbruch ist dort nichts halb geschrieben (getestet mit SIGKILL mitten in der Schreibtransaktion). **Dateien**: Jede
  Datei, die ein echter Lauf unter `media/material` ablegt, steht sofort in `<kennung>.abgelegt`; nach einem Abbruch
  gehen Produktbilder weg, die keine Zeile nennt (`mat_product.image`), und Dokumentdateien über
  `katalog._datei_freigeben` (entfernt nur, was kein Dokument nennt). Hatte der Lauf noch committet, bleiben seine
  Dateien. Grenze: Die eine Datei, die beim Ende des Prozesses gerade abgelegt wurde, steht noch nicht im Protokoll –
  ein Produktbild mit Zufallsnamen bleibt dann als harmlose Waise liegen (nie verwendet), bei einem Dokument nur die
  Zwischendatei `.neu-…`, die der Start der App nach einem Tag aufräumt (Schritt 18); die fertig abgelegte
  Dokumentdatei heißt nach ihrem Inhalt und wird beim nächsten Lauf wiederverwendet. Ersetzte Produktbilder, die erst
  nach dem Commit gelöscht werden, bleiben bei einem Abbruch genau dazwischen liegen.
- **Aufräumen**: hochgeladene Datei sofort nach dem Ende (außer für „Übernehmen“, dann nach einer Stunde); Zustände und
  Berichte nach **7 Tagen**; Dateien ohne Zustand und liegengebliebene Zwischendateien, sobald niemand importiert. Das
  geschieht bei jedem Start eines Imports, bei der Abfrage der Katalogseite (`…/import/aktuell`) und im Tageslauf –
  nicht beim Start der App (die Startschritte laufen in der Migration; ein toter Auftrag fällt dort ohnehin bei der
  ersten Abfrage auf).
- **Personendaten**: Der Bericht nennt wie bisher keine Person. Der Zustand nennt den Namen dessen, der gestartet hat
  (wie das Journal, nie die E-Mail), und seine Kontokennung (für „Übernehmen“; die Schnittstelle gibt sie nicht aus) –
  7 Tage lang. **Seit der Nachbesserung (unten) nur noch den pseudonymen Kontoverweis.**

### Oberfläche

- **Dialog „Katalog importieren …“** (material.js, `katalogImportDialog`): Datei wählen oder hineinziehen → Hochladen
  mit Fortschrittsbalken („45 % · 12,0 MB von 26,1 MB“, XMLHttpRequest wegen des Upload-Fortschritts) → Stand des
  Auftrags alle 2,5 s („Probelauf: Datei prüfen – 120 von 1 905 …“ mit Balken, darunter „gestartet … von … · Datei“)
  → am Ende der Bericht wie bisher. „Übernehmen“ (rot, die eine Hauptaktion) erscheint, wenn der Probelauf
  übernehmbar ist, und startet den echten Lauf ohne neuen Upload; danach derselbe Fortschritt und der Bericht,
  „Katalog übernommen“, Neuladen beim Schließen wie bisher. „Schließen“ (grau) jederzeit: Der Import läuft auf dem
  Server weiter – nur während des Hochladens bricht Schließen das Hochladen ab („Hochladen abgebrochen – es wurde
  nichts importiert.“). Ohne Verbindung (Neustart, Deploy) fragt der Dialog weiter nach, mit wachsender Pause bis 15 s.
  409 beim Start: die Meldung und „Stand des laufenden Imports ansehen“.
- **Hinweis auf der Katalogseite** (nur Material-Verwaltung) über der Suchzeile: ein laufender Import („Katalogimport
  läuft – Probelauf: Dateien ablegen – 12 von 40 …“, alle 5 s neu) oder einer, der vor höchstens einem Tag endete
  („Probelauf fertig – noch nicht übernommen.“, „Katalogimport übernommen.“, „… abgebrochen.“, „… mit Fehlern beendet
  – nichts gespeichert.“), mit Name, Datei und Zeit. „Stand ansehen“ bzw. „Bericht ansehen“ öffnet den Dialog mit
  diesem Auftrag (dort auch „Übernehmen“, wenn man selbst den Probelauf gestartet hat), „Ausblenden“ blendet einen
  beendeten in diesem Browser aus. Textverweise wie bei „Erinnerungsmails“ auf der Übersicht, keine Piktogramme.

### Schnittstelle

| Aufruf | Recht | Antwort |
| --- | --- | --- |
| `POST /api/material/katalog/import` (`file`, `trocken`: Vorgabe `1`) | Katalog | **202** `auftrag`; 409 `error` + `auftrag` (der laufende); 400 ohne Datei; 500 ohne Platz zum Zwischenspeichern (ohne Pfad) |
| `GET /api/material/katalog/import/<kennung>` | Katalog (jedes Konto der Material-Verwaltung sieht jeden Auftrag) | `auftrag` mit `bericht` (null, solange er läuft, und bei „abgebrochen“); unbekannte oder unpassende Kennung 404 |
| `POST /api/material/katalog/import/<kennung>/uebernehmen` | Katalog, nur wer den Probelauf gestartet hat (sonst 403) | **202** `auftrag` (der echte Lauf, `aus` = Probelauf); 409 belegt, schon übernommen, nicht übernehmbar oder Datei nicht mehr da; 404 unbekannt |
| `GET /api/material/katalog/import/aktuell` | Katalog | `auftrag` (ohne Bericht): der neueste, wenn er läuft oder vor höchstens 24 h endete, sonst null |

`auftrag`: `id`, `zustand` (`wartet`, `laeuft`, `fertig`, `fehlgeschlagen`, `abgebrochen`), `trocken`, `quelle`,
`groesse` (Bytes), `von` (Name), `eigener`, `gestartet`, `beendet`, `lebenszeichen` (ISO-Zeit, UTC), `phase`
(`pruefen`, `probe`, `ablegen`, `schreiben` oder null), `n`, `m` (Fortschritt der Phase oder null), `fehler` (Grund bei
„abgebrochen“ und bei einem unerwarteten Fehler), `aus`, `uebernommen_in`, `uebernehmbar`, `datei_bis` (nur wenn
übernehmbar), `bericht` (nur bei `GET …/<kennung>`). Grenzen: Datei bis 2 GB (wie bisher), ein Import gleichzeitig,
Datei für „Übernehmen“ 1 h, Zustände 7 Tage, Hinweis 24 h, abgebrochen nach 30 s ohne Sperre und Lebenszeichen.

### Für Entwickler

- `services/importauftrag.py` (neu): Start, Übernehmen, Lauf, Sperre, Aufräumen; `warten(kennung)` für Tests.
- `services/importer.py`: optionaler Rückruf `fortschritt(phase, n=None, m=None, abgelegt=None)` an
  `datei_importieren`, `importieren`, `_dateien_pruefen` und `_Lauf` – ohne Rückruf (Kommandozeile, bisherige Aufrufer)
  ändert sich nichts, mit Rückruf ist der Bericht derselbe (getestet).
- `routes_katalog.py`: die Route antwortet 202; drei neue Routen. `tageslauf.py`: `importauftrag.aufraeumen()`.
- Proxy: Die Zeitgrenze des Reverse-Proxys gilt für den Katalogimport nicht mehr (die Antwort kommt nach dem Upload
  sofort). Für das Hochladen selbst bleiben `client_max_body_size` bzw. die Upload-Zeitgrenze des Proxys nötig.

### Tests

- `tests/test_material_importauftrag.py` (neu): Route 202 → „fertig“ (Thread abgewartet), Bericht des Probelaufs und
  des echten Laufs identisch mit dem synchronen Lauf derselben Datei (zwei Instanzen), Journal mit demselben Konto,
  Rechte 0700/0600; Probelauf → Übernehmen ohne neuen Upload (Datei wandert und ist danach weg, zweites Übernehmen
  409); Probelauf ohne Änderung behält keine Datei, abgelaufene Frist → 409 und aufgeräumt; zweiter Import während eines
  laufenden → 409 mit dem laufenden (auch von einem anderen Konto), die Datei des Versuchs bleibt nicht liegen;
  **Prozess weg**: ein eigener Prozess startet den Import über die Schnittstelle und wird mit SIGKILL beendet – einmal
  zwischen dem Ablegen zweier Dateien, einmal mitten in der Schreibtransaktion: erst noch „laeuft“ und 409 (frisches
  Lebenszeichen), dann „abgebrochen“, keine Zeile geschrieben, keine abgelegte Datei übrig, Sperre frei, derselbe Import
  geht danach durch; Aufräumen nach einem Abbruch behält, was die Datenbank nennt, und lässt Verweise mit Pfad aus dem
  Protokoll liegen; Rechte (403 für Führungskraft, Materialwart, Prüfer, Nutzer; 401 anonym; CSRF; 404 für fremde und
  unpassende Kennungen; Übernehmen nur der Starter; keine E-Mail im Zustand); Fehlerfälle (kaputtes ZIP und JSON,
  Prüfregel, unerwarteter Fehler ohne Pfad im Text – alle „fehlgeschlagen“ mit Bericht, Sperre frei; kaputte Sperr- und
  Zustandsdatei); Aufräumen (7 Tage, Hinweis 24 h, Waisen, Zwischendateien, Tageslauf); Rückruf des Importers (Phasen,
  Zahlen, abgelegte Dateien; Bericht mit und ohne Rückruf gleich); Kommandozeile unverändert synchron, ohne Auftrag.
- Angepasst (202 statt 200, Fehler im Bericht statt 400): `test_material_katalog.py`, `test_material_dokumente.py`,
  `test_material_wiki.py` über den neuen Helfer `import_abwarten` (test_material.py). Die Rechteprüfungen über alle
  Routen (`test_material_ueberblick.py`, `test_material_trennung.py`, `test_material_stufen.py`) kennen die neuen
  Routen mit einer Kennung, die es nicht gibt: Führungskraft, Materialwart aus A und ein Konto ohne Stufe bekommen 403.

### Im Browser geprüft (Chromium, 1280 und 360 px, zwei Serverprozesse auf denselben Daten)

- **Ganze Lieferung** `katalog-gesamt.zip` (1,13 GB, lokal): Hochladen 7 s mit Fortschritt, Probelauf 21 s („Datei
  prüfen – 836 von 1 905“ im Dialog und im Hinweis), Bericht wie bisher (1 395 Produkte, 1 369 Bilder, 3 959 Dokumente,
  24 Stücklisten neu), „Übernehmen“ ohne neuen Upload 218 s („Dateien ablegen – n von 5 315“), danach „Katalogimport
  übernommen.“ auf der Katalogseite. Ein zweiter Start über den anderen Prozess bekam 409 mit dem Namen; der andere
  Prozess sah Phase und Zahlen. Dialog während des Laufs geschlossen → Hinweis „Katalogimport läuft – …“, alle 5 s
  neu, dann „Probelauf fertig – noch nicht übernommen.“, „Bericht ansehen“ öffnet den Dialog mit „Übernehmen“.
- **Teil 1 der Gesamtserie** (26 MB): Hochladen gedrosselt mit Prozentanzeige, Probelauf, Übernehmen, Hinweis,
  „Ausblenden“; Schließen während des Hochladens → „Hochladen abgebrochen – es wurde nichts importiert.“, kein Auftrag.
- **DEMO-Datei** (zwei DEMO-Kategorien) bei 360 px: Dialog, Bericht, „Schließen“ und „Übernehmen“ nebeneinander, Hinweis
  ohne waagerechten Bildlauf, keine Konsolenfehler.
- **Neustart mitten im Übernehmen**: Server beim Ablegen (402 von 5 468) mit SIGKILL beendet und neu gestartet →
  Hinweis erst „läuft“, nach 14 s „Katalogimport abgebrochen.“, im Dialog der Grund; Datenbank ohne Produkt, Dokument und
  Journalzeile, von 325 abgelegten Dateien blieb genau die eine, die gerade in Arbeit war (ein Original unter
  `media/material/orig`, siehe Grenze oben).

### Bitte bestätigen

1. **Übernehmen nur durch den, der den Probelauf gestartet hat** – andere Konten der Material-Verwaltung sehen Stand und
   Bericht, starten aber selbst einen neuen Probelauf. Alternative: jedes Konto der Material-Verwaltung darf übernehmen.
2. **Datei des Probelaufs eine Stunde** für „Übernehmen“; danach die Datei neu wählen.
3. **Hinweis auf der Katalogseite 24 Stunden** nach dem Ende (ausblendbar je Browser); Zustände und Berichte 7 Tage.
4. **Eine unlesbare Datei** (kaputtes ZIP, kein JSON) ist jetzt ein „fehlgeschlagener“ Auftrag mit Bericht statt einer
   sofortigen Fehlermeldung (400) – die Prüfung braucht bei 1 GB selbst ihre Zeit.
5. **Abbruch erkannt nach 30 s** ohne Sperre und Lebenszeichen; bis dahin bekommt ein neuer Start nach einem Neustart
   noch 409.

## Nachbesserung Katalogimport im Hintergrund nach der Sicherheitsprüfung (24.10.2026)

Grundlage: Prüfbericht des Sicherheitsprüfers zu 30cf668 (zwei Befunde, mehrere Verbesserungen), Auftrag
`auftrag_nachbesserung_hintergrundimport.md`. Kein Schemaschritt, Schema bleibt 21. Gebaut im Worktree
`import-nachbesserung` (von dev e4fddcc).

### Befunde

- **Löschkonzept** (Befund 1): Der Zustand speicherte `von_id` (users.id – SQLite vergibt sie ohne AUTOINCREMENT nach
  dem Löschen neu) und den Namen. Ein neues Konto mit derselben Kennung hätte einen fremden Probelauf übernehmen können,
  und der Name stand bis zu 7 Tage auf der Platte. Jetzt steht im Zustand nur noch `von_ref` = `users.mat_ref`, der
  pseudonyme Kontoverweis, den auch das Journal benutzt (beim Start mit `journal.konto_ref` angelegt, falls er fehlt).
  Er verschwindet mit der Kontozeile; den Namen löst jede Anzeige frisch auf (`journal.konto_name`) – nach dem Löschen
  „(gelöschtes Konto)“, und „Übernehmen“ vergleicht den Verweis des angemeldeten Kontos, sodass ein Nachfolger mit
  derselben Kennung nur 403 bekommt. Der Lauf findet sein Konto (Journal, Bearbeiter) über `mat_ref`. So braucht das
  Löschen eines Kontos (`services/loeschung.py`) keinen eigenen Schritt für die Aufträge: Die Datei eines übernehmbaren
  Probelaufs enthält nur den Katalog und verschwindet spätestens mit ihrer Frist bzw. dem nächsten Import. Zustände der
  ersten Fassung verlieren `von_id` und `von` beim nächsten Aufräumen (Abfrage der Katalogseite, Start, Tageslauf);
  übernehmen lässt sich ein solcher Probelauf nicht mehr (nur auf dev entstanden).
- **Plattenplatz** (Befund 2): Ein neuer Auftrag (Probelauf wie „Übernehmen“) löscht unter der Sperre die Dateien
  älterer Probeläufe – es läuft ohnehin nur einer, und ihr „Übernehmen“ ist damit überholt (409 „liegt nicht mehr bereit
  (sie bleibt eine Stunde, bis zum nächsten Import)“). Vor dem Kopieren der hochgeladenen Datei prüft der Start
  `shutil.disk_usage` gegen Dateigröße + `RESERVE` (64 MB, wie `zuruecksetzen.RESERVE`), „Übernehmen“ ebenso gegen die
  Größe der Datei (der Import legt ungefähr so viel unter `media/material` ab). Zu wenig: **507** „Auf dem Server ist zu
  wenig Platz für die Katalogdatei: frei 0,4 GB, gebraucht etwa 1,2 GB …“ – Zahlen, kein Pfad; der Probelauf bleibt dann
  übernehmbar. Die alte Datei geht schon vor der Prüfung weg, damit ihr Platz mitzählt.

### Verbesserungen

- **Meldung nach einem Abbruch**: „schon abgelegte Dateien sind wieder entfernt“ steht nicht mehr da. README und Modul
  sagen genauer: Weggeräumt wird alles, was im Protokoll steht; die eine Datei, die im Moment des Abbruchs gerade
  geschrieben wurde, kann liegen bleiben (mit nichts verknüpft, nie angezeigt; ein Dokument heißt nach seinem Inhalt
  und wird wiederverwendet). Bilder ohne Besitzer aus dem Zeitfenster des Laufs wegzuräumen wäre **nicht sicher** – ein
  Bild, das jemand anderes gerade hochlädt, hat bis zu seinem Commit auch noch keine Zeile; deshalb nicht umgesetzt.
- **„Gespeichert wurde nichts“ nur vor dem Commit**: Der Importer meldet gleich nach dem Commit `fortschritt("gespeichert")`
  (ohne Rückruf – Kommandozeile – unverändert); der Auftrag vermerkt `gespeichert: true` sofort auf der Platte. Ein
  unerwarteter Fehler danach meldet „Die Datenbank war da schon geschrieben; ob alles übernommen ist, zeigt ein neuer
  Probelauf mit derselben Datei.“, ebenso ein Abbruch danach. Der Hinweis auf der Katalogseite sagt bei einem solchen
  Fehler nur „mit Fehler beendet.“ statt „– nichts gespeichert.“
- **Abgebrochenes „Übernehmen“ wiederholen**: Endet der Prozess eines „Übernehmen“, bevor es gespeichert hatte
  (Neustart, Deploy), bekommt der Probelauf seine Datei zurück und lässt sich wieder eine Stunde übernehmen – im Dialog
  des abgebrochenen Laufs steht „Übernehmen“ (die Route nimmt auch dessen Kennung und nimmt dann den Probelauf), der
  Hinweis sagt „Katalogimport abgebrochen – Übernehmen geht noch einmal.“ Ohne Risiko: Die Transaktion hat nichts
  geschrieben; und fiele der Abbruch genau zwischen Commit und Vermerk (Mikrosekunden), fände der zweite Lauf nichts mehr
  zu ändern – der Import gleicht ab und legt nichts doppelt an. Nach dem Vermerk „gespeichert“ gibt es keine zweite
  Runde.
- **Dialog**: Vor dem Hochladen fragt er `…/import/aktuell`; läuft schon einer, lädt er gar nicht erst hoch („Es läuft
  schon ein Katalogimport [von …]. Es kann immer nur einer laufen – bitte warten, bis er fertig ist.“ mit „Stand des
  laufenden Imports ansehen“). Nach 100 % steht „Datei wird abgelegt …“ (Balken ohne Wert) bis zur Antwort. Wer in
  diesem Fenster schließt, bricht nichts mehr ab: kein „es wurde nichts importiert“, sondern „Die Datei ist
  hochgeladen – der Probelauf startet auf dem Server. Sein Stand steht oben auf der Katalogseite.“; scheitert der Start
  dann doch (409, 507), kommt seine Meldung als Einblendung. `importBalken` wandelt n und m mit `Number()`.
- **dev-zuruecksetzen**: nimmt zuerst die Sperre des Katalogimports und hält sie bis zum Schluss – läuft gerade einer
  (Sperre gehalten oder frisches Lebenszeichen), bricht es mit „Gerade läuft ein Katalogimport … – nichts geändert.“
  ab (Rückgabewert 1), ein Start während des Laufs bekommt 409. Nach dem COMMIT leert es `DATA_DIR/katalog-import/` (jede
  Datei einzeln mit genauem Namen; die Sperrdatei bleibt). `--trocken` nennt den Ordner und warnt, wenn gerade einer läuft.
- **Nicht übernommen**: eigene `stream_factory` (der Upload landet weiter in Werkzeugs Zwischenspeicher und wird einmal
  kopiert) – nicht trivial genug für den Nutzen.

### Für Entwickler

- `importauftrag.py`: `von_ref` statt `von_id`/`von`, `_ref`, `_von`, `_erneut`, `_platz_pruefen` (507),
  `_alte_probelaeufe_freigeben`, `_zurueck_zum_probelauf`, `_gespeichert_text`; für dev-zuruecksetzen `anhalten`,
  `laeuft`, `zwischendaten`, `leeren_unter_sperre`. `importer.py`: Phase „gespeichert“ nach dem Commit (beide Wege).
  `zuruecksetzen.py`: Sperre, Leeren, Zeilen in Probelauf und Bericht. `material.js`: Vorabfrage, „Datei wird abgelegt
  …“, Schließen, Hinweistexte, `importBalken`.

### Tests

`tests/test_material_importauftrag.py` (13 Tests): neu `test_konto_geloescht` (Konto löschen → neues Konto mit derselben
Kennung bekommt 403, Name „(gelöschtes Konto)“ in Stand und Hinweis, kein Name in der Datei; Zustand der ersten Fassung
verliert Name und Kennung beim Aufräumen), `test_plattenplatz` (zweiter Probelauf löscht die Datei des ersten; 507 ohne
Pfad bei Übernehmen und Upload, nichts liegen geblieben), `test_uebernehmen_abgebrochen` (echt per SIGKILL mitten in der
Schreibtransaktion eines „Übernehmen“ → Probelauf wieder übernehmbar, Übernehmen über die Kennung des abgebrochenen
Laufs speichert; nachgestellter Abbruch nach dem Commit → keine zweite Runde, 409); `test_fehlerfaelle` mit einem Fehler
nach dem Commit; Rechte- und Fortschrittstest angepasst. `tests/test_material_dev_zuruecksetzen.py`: neu
`test_katalogimport` (Sperre gehalten bzw. frisches Lebenszeichen → Rückgabewert 1, nichts geändert, `--trocken` warnt;
danach geleert bis auf die Sperrdatei); `stand()` lässt die leere Sperrdatei aus.

### Im Browser geprüft (Chromium, 1280 und 360 px, DEMO-Katalogdatei mit Platzhaltern)

- Probelauf: Antwort des Servers per DevTools angehalten → „Datei wird abgelegt …“ mit laufendem Balken, danach der
  Bericht mit „Übernehmen bis …“.
- Schließen, während die Antwort angehalten war → Hinweis „Die Datei ist hochgeladen – der Probelauf startet …“, nach
  dem Freigeben steht der Probelauf oben auf der Katalogseite.
- Nachgestellter laufender Import (Zustand mit frischem Lebenszeichen, darin n/m mit HTML) → „Es läuft schon ein
  Katalogimport …“, **keine** POST-Anfrage; „Stand des laufenden Imports ansehen“ zeigt einen Balken ohne Wert (kein
  eingeschleustes Markup).
- Nachgestelltes abgebrochenes „Übernehmen“ → Hinweis „Katalogimport abgebrochen – Übernehmen geht noch einmal.“, im
  Dialog Grund und „Übernehmen“ (rot, die eine Hauptaktion) neben „Schließen“; „Übernehmen“ speichert.
- Keine Konsolenfehler, keine waagrechte Rollleiste bei 360 px.

### Bitte bestätigen

1. **Kontoverweis statt Löschschritt**: Statt beim Löschen des Kontos alle Zustände umzuschreiben, speichern die Aufträge
   nur noch `users.mat_ref`. Die Datei eines Probelaufs des gelöschten Kontos bleibt bis zum Ablauf ihrer Stunde bzw.
   bis zum nächsten Import liegen (sie enthält nur den Katalog) – übernehmen kann sie niemand mehr.
2. **Platz**: Grenze Dateigröße + 64 MB, bei „Übernehmen“ ebenso (grobe Schätzung dessen, was unter `media/material`
   landet). Ein neuer Import löscht die Datei eines älteren Probelaufs auch dann, wenn er selbst mit 507 abgelehnt wird.
3. **Übernehmen nach Abbruch** wiederholbar, solange kein „gespeichert“ vermerkt ist (Begründung oben).

## Modul Material auf dev zurücksetzen (Wunsch des Nutzers, 23.10.2026)

Wunsch: „Bereinige den Katalog und die Testdaten auf dev, ich möchte vor Lieferung 3 alles ausgiebig von null an
testen.“ Entschieden: nur das Modul Material, vorher alles sichern (umkehrbar); der Nutzer ruft den Befehl auf dem VPS
selbst auf (README, „Modul Material auf dev zurücksetzen (nur dev)“).

- **`flask material dev-zuruecksetzen [--trocken | --ja-alles-loeschen]`** (app/material/cli.py,
  services/zuruecksetzen.py). Wirkt nur auf dev: `STROEMIS_NAME` endet auf „-dev“ (`erinnerung.dev_umgebung`, aus
  `gesperrt()` herausgelöst – dieselbe Regel wie die harte Sperre der Erinnerungsmails), `BASE_URL` zeigt weder in der
  Umgebung noch unter Verwaltung → Einstellungen auf die Produktion (wie `scripts/material_beispielbestand.py`), und
  der Schalter `--ja-alles-loeschen` ist gesetzt (seit der Nachbesserung: `BASE_URL` als Positivliste, siehe unten). Sonst Klartext und Rückgabewert 2, nichts geändert; `--trocken` (auch
  nur auf dev) zeigt Tabellen mit Zeilen, Volltextindizes, Trigger, Indizes, Medienordner mit Dateien und MB, den
  Sicherungsordner mit Datenbankgröße und freiem Platz, was bleibt, und die DEMO-Konten.
- **Sicherung zuerst**, unter einer exklusiven Transaktion (busy_timeout 30 s): die ganze Datenbank über die Backup-API
  nach `<DATA_DIR>/sicherung-material-<JJJJ-MM-TT_hhmmss>/stroemis.db` (gewöhnliches Journal, quick_check, dieselben
  Zeilen je `mat_`-Tabelle), dann `media/material` und `pdf/` dorthin **verschoben** (umbenannt, nie kopiert). Scheitert
  die Sicherung, zu wenig Platz oder das Verschieben (etwa anderes Dateisystem): nichts gelöscht, Medien zurück, die
  eigene Teilsicherung wieder weg; Rückgabewert 1. Dazu `LIESMICH.txt` mit dem Rückweg.
- **Leeren und frisch anlegen** in derselben Transaktion: alle Tabellen, Trigger, Views und Volltextindizes des Moduls
  per DROP (keine Zeile wird einzeln gelöscht – die Trigger der unveränderlichen Nachweise werden nicht umgangen, das
  Modul wird als Ganzes neu angelegt). Das neue Schema stammt aus `models.migrieren` auf einer leeren Vorlage im
  Speicher, die nur die Form der übrigen Tabellen kennt – so entsteht es wie bei einer neuen Installation
  (Schemaversion 21), ohne dass Schritt 8 bis 10 die echten Konten anfassen (Schritt 10 rechnete die Modulstufen sonst
  aus Freigaben neu, die es danach nicht mehr gibt: eine Material-Verwaltung ohne Plattform-Verwaltung fiele auf
  „Mitglied“). Danach die Startschritte des Moduls (`START_SCHRITTE`, aus `schema_anmelden` herausgelöst) wie bei einem
  Start. Ausgabe: Sicherungsordner, geleerte Tabellen und Zeilen, verschobene Medien, DEMO-Konten, „docker compose
  restart“.
- **Bleibt**: Konten, Wiki, Spots, Prüfungen-Modul, Tabelle `einstellungen` (also auch „Bald fällig“ und der Schalter
  Erinnerungsmails). Die Spalten des Moduls an `users` (`recht_material`, `mat_pruefer`, `mat_katalog`,
  `urkundennummer`, `signature_png`, `mat_ref`, `mat_psa_mails`) bleiben unverändert: Keine verweist auf eine Zeile des
  Moduls (`mat_ref` ist der Verweis, auf den Journal und Erinnerungslog zeigen), es zeigt also nichts ins Leere. Die
  DEMO-Konten (`@example.invalid`) löscht der Befehl nicht, er nennt sie („über die Nutzerverwaltung löschen, falls nicht
  mehr gebraucht“) – sie haben danach keine Freigaben mehr, und `material_demo.py --konten` legt nur fehlende Konten an.
- **Tests**: tests/test_material_dev_zuruecksetzen.py – Sperren (ohne, mit falscher und mit Produktions-Kennung, BASE_URL
  der Produktion in Umgebung und Einstellungen, ohne Schalter; `--trocken` auch zusammen mit dem Schalter) ändern nichts;
  voller Lauf auf Katalog mit Bild und Dokument, Gliederung, Artikeln, Durchgang, Bestandsimport und dem DEMO-Bestand
  (festgeschriebene Prüfungen mit Protokollen, Set, DEMO-Konten): alle `mat_`-Tabellen leer, Schema und `mat_meta` gleich
  einer neuen Installation, Sicherung mit allen alten Zeilen und allen Mediendateien, außerhalb des Moduls jede Zeile,
  jedes Schema-Objekt und jede Datei byteidentisch; zweiter Lauf auf leerem Modul, App startet, `material_demo.py
  --demo --konten` läuft wieder; Sicherung, Verschieben und Anlegen scheitern jeweils ohne Änderung.

- **Nachbesserung nach der Sicherheitsprüfung** (pruefung_dev_zuruecksetzen.md, drei Befunde „niedrig“, alle behoben):
  1. *BASE_URL als Positivliste* (`zuruecksetzen.host`, `adresse_frei`): Der Host wird bereinigt – Leerraum weg,
     fehlendes Schema ergänzt, Unicode NFKC, ideographischer und vollbreiter Punkt als Punkt, IDNA, klein, ohne Punkt am
     Ende – und ist nur frei, wenn er mit „dev.“ beginnt oder localhost/127.0.0.1 ist; das gilt für die Umgebung und
     für die Anwendung (Verwaltung → Einstellungen). Leer, unlesbar oder sonst etwas sperrt (Exit 2), also auch
     `strömis.de` ohne Schema, mit Leerzeichen am Ende, mit zerlegtem „ö“ (NFD) oder mit „。“. Eine Test-Kennung für
     eine leere BASE_URL ist nicht nötig: Die Tests setzen `https://dev.strömis.de`, run.py `http://localhost:8080`, und
     ohne Eintrag gilt in der Anwendung die Vorgabe `https://strömis.de` (sperrt). Die bisherige Sperrliste
     `PRODUKTION` entfällt.
  2. *Abbruch per Signal*: LIESMICH.txt entsteht schon vor dem ersten Verschieben – mit „LAUF UNVOLLSTÄNDIG“ und den
     `mv`-Zeilen, die die Medien zurückbringen (die Datenbank verwirft SQLite dann selbst) – und wird nach dem COMMIT
     mit dem vollen Rückweg überschrieben. Von der exklusiven Transaktion bis nach dem Rückweg werden SIGTERM und
     SIGHUP zu einer Ausnahme (`_signale_abfangen`): `docker compose stop/restart` oder ein Deploy mitten im Lauf
     führen in den vorhandenen Rückweg (ROLLBACK, Medien zurück, eigene Sicherung weg, Exit 1). Ein zweites Signal
     unterbricht den Rückweg nicht, eines unmittelbar vor oder nach dem COMMIT lässt den Lauf zu Ende gehen; danach
     gelten die alten Handler. README: während des Laufs nicht pushen und nicht neu starten.
  3. *Sicherung mit Personendaten*: Sicherungsordner 0700, Kopie und LIESMICH.txt 0600. Bericht und Probelauf nennen
     die älteren `sicherung-material-*` mit Datum und Größe; Bericht, LIESMICH.txt und README fordern auf, die Sicherung
     zu löschen, sobald Neustart und ein erster Test geklappt haben (spätestens vor Lieferung 3), mit dem fertigen
     `rm -rf`-Befehl.
- **Löschkonzept**: Eine Sicherung von `dev-zuruecksetzen` ist eine Vollkopie der Datenbank – alle Konten mit E-Mail,
  Passwort-Hash, Urkundennummer und Unterschrift, Wiki und Prüfungen. Das Löschen eines Kontos auf dev erreicht sie
  nicht; sie ist deshalb nur für den Test gedacht und wird von Hand gelöscht, sobald Neustart und erster Test geklappt
  haben (spätestens vor Lieferung 3). Nur auf dev, nur für den Besitzer lesbar; der Befehl erinnert bei jedem Lauf an
  ältere Sicherungen.
- **Tests dazu** (tests/test_material_dev_zuruecksetzen.py): `test_sperre_schreibweisen` (die Fälle der Probe sperre.py
  und freie Schreibweisen, je in Umgebung und Anwendung, über `sperrgrund()` und `--trocken`), `test_abbruch_per_signal`
  (Probe kill.py nachgestellt: Kind hält in `_leeren`; SIGTERM und SIGHUP → Exit 1, alles wie vorher; SIGKILL →
  Datenbank unverändert, LIESMICH.txt „LAUF UNVOLLSTÄNDIG“, ihre `mv`-Zeilen stellen den Stand wieder her; Handler danach
  die alten), in `test_zuruecksetzen` Rechte 0700/0600, Löschaufforderung und ältere Sicherungen in Bericht und
  Probelauf.

## Phase 4 · Lieferung 2b – Sets, Teil 2 (23.10.2026, Stand: geliefert, wartet auf Freigabe)

> **Zurückgebaut durch Schritt 26** (Wunsch des Nutzers, 25.10.2026) – siehe „Rückbau der Set-Funktion“. Der Abschnitt
> bleibt als Geschichte stehen.

Grundlage: `planung/material-phase4/entwurf_l2b.md` (Fassung 2 nach den Kritiken „Sicherheit“ T1–T16 und „Ablauf“
U1–U16, mit den Entscheidungen des Nutzers vom 23.10.2026). Gebaut in Paketen: **KERN A** (vorhandenen Artikel einsetzen,
Auswahl, Prüfumfang, Set löschen/auflösen, „Bestandteil ersetzt“ – Dienste, Routen, Rechte, Tests), **KERN Z** (Zahlen,
CSV-Spalten, gebündelte Mails – eigener Abschnitt unten), danach **OBERFLÄCHE** (Abschnitt „Oberfläche (23.10.2026)“). **Kein Schemaschritt** – Schemaversion
bleibt 21, keine neuen Abhängigkeiten.

### Neu (KERN A)

- **Vorhandenen Artikel als Teil einsetzen** (Entwurf A): beim Set anlegen (`POST /artikel`, Teilblock
  `{"bestandteil_id", "item_id"}` statt der Felder eines neuen Teils) und bei „Teil einsetzen“ an einer fehlenden
  Position (`item_id`) – nicht beim Tauschen (400, „erst entnehmen, dann einsetzen“). Ein Dienst für beide Stellen
  (`setaustausch.vorhandenen_einsetzen`); alles in der Transaktion (BEGIN IMMEDIATE) am frisch gelesenen Artikel, in
  dieser Reihenfolge (T6):
  1. **Sicht**: verwalten an der Heimat des Artikels (und an der des Sets) – sonst 404 „Artikel nicht gefunden.“, gleich
     für fremd, unbekannt, nur lesbar und das Teil eines fremden Sets;
  2. **Produkt** der Position – sonst 409 „<Nr> ist <Produkt>; an dieser Position steht <Produkt> – Produkt am Artikel
     korrigieren.“ (auch für den Set-Artikel selbst);
  3. **dieselbe Gliederung** wie das Set (sonst 409 „… erst in die Gliederung des Sets verschieben …“) und die
     **DEMO-Grenze** (409 wie beim Verschieben);
  4. **Zustände** (409): frei (nicht gesperrt, verloren, ausgesondert), kein Teil eines Sets („erst dort „Teil
     entnehmen““), kein Set, kein offener Entwurf („In Prüfung bei …“), keine offene Mangelmeldung, kein offener Rückruf
     (frisch und ungefiltert, `rueckruf.aktive_fuer_artikel`), nicht „Lebensdauer erreicht“, eine Lücke an der Position
     (Stückzahl frisch je Produkt), keine Prüfung des Artikels im offenen Lauf dieses Sets (T2 – entnommen und wieder
     eingesetzt: „erst die Set-Prüfung abschließen oder abbrechen“).
  Wirkung: EIN bedingtes UPDATE `parent_item_id, folder_id, origin_folder_id, assigned_user_id` = wie das Set `WHERE id
  AND parent_item_id IS NULL AND lock_state = 'frei' AND folder_id = <gelesen> AND assigned_user_id IS <gelesen>`
  (Zeilenzahl 1, sonst 409 „… inzwischen geändert … – bitte neu laden.“, U9); dann – außer beim Anlegen –
  `sets.sperren(Set, set_grund="tausch", neu=[Artikel])` („Teil … neu eingesetzt – Set prüfen“), **erst danach**
  `durchgang.nach_verschieben` und `faelligkeit.kappen` nach der Heimat des Sets (T3; beim Anlegen nach allen Teilen).
  Journal am Teil: „verschoben“ (wenn der Ordner wechselt, mit `set`), „zuordnung_geloest“/„zugeordnet“ (Zuordnung des
  Sets, U10), „eingesetzt“ `{set, set_inventar, bestandteil}`; am Set „teil_eingesetzt“ `{teil, serial_no, bestandteil,
  austausch, vorhanden: true}` ohne Herkunftspfad (T14), beim Anlegen zusätzlich `vorhanden: true` je Eintrag in
  „set_angelegt“. „Austausch laut Hersteller“ gilt an „Teil einsetzen“ wie beim neuen Teil (nein → 409, nicht belegt →
  Bestätigung). Der Artikel bringt seine Historie mit (wie Verschieben); alte Protokolle bleiben ohne „Teil von Set“.
- **Auswahl „aus dem Bestand wählen“** (T10, U8): `GET /artikel/<Set>/kandidaten?slot_id=&q=` (verwalten am Set) und
  `GET /ordner/<fid>/kandidaten?product_id=&q=` (verwalten am Ordner, für „Artikel anlegen“). Treffer: freie Artikel ohne
  Set des Produkts der Position, verwaltbar (`artikel_filter(…, 'verwalten')`), in der Gliederung des Ziels, auf
  derselben Seite der DEMO-Grenze; Suche in Inventar-, Seriennummer und der Zeile „Bisherige Inventarnummer: …“ der
  Bemerkung (Bestandsimport), `LIKE … ESCAPE`, q 2–80 Zeichen, höchstens 20 Treffer (`weitere`). Kein Suchprotokoll,
  kein Hinweis auf Treffer außerhalb.
- **Prüfumfang** (U4): Ein Set, das selbst noch nie geprüft wurde, prüft in der Set-Prüfung **alle Teile**
  (`setlauf.umfang`) – auch wenn vorher ein Teil es gesperrt hat (Probe P-B). Ein eingesetztes vorhandenes Teil ist über
  `set_pruefen` im Umfang (Einbau prüfen, A26).
- **„Set löschen“** (U2) löscht nur Teile, die mit dem Set angelegt wurden (Journal „angelegt“ mit `{"set": Set}` seit
  der letzten Löschung der Kennung – `sets.beitritt`); enthält das Set eingesetzte vorhandene Artikel, 409 „Das Set enthält
  vorhandene Artikel (…) – „Set löschen“ löscht nur Teile, die mit dem Set angelegt wurden. „Set auflösen“ gibt die
  Teile frei in den Ordner zurück.“ (Probe P-A). Was auch ohne sie gegen das Löschen spricht (Prüfung, Meldung,
  Durchgang), meldet weiter der bisherige Text. `darf_loeschen` am Artikel ist dann `false`.
- **„Set auflösen“** (T1, T7, U1, U3): `POST /artikel/<Set>/aufloesen` (verwalten). Nur ein **freies** Set (weder das Set
  noch ein Teil gesperrt, verloren oder ausgesondert); das Set selbst allein löschbar – keine Prüfung (auch kein
  Entwurf), keine Mangelmeldung (auch keine erledigte), keine Durchgangszeile, kein Änderungsantrag, kein beendeter
  Set-Lauf und kein offener mit Prüfung; an keinem Teil ein offener Entwurf und keine abgeschlossene Prüfung, seit es im
  Set ist (deren Protokoll trägt „Teil von Set …“; gemessen am Journal: Eintritt ins Set gegen „abgeschlossen“ der
  Prüfung). Sonst 409 mit Grund und Weg („einzelne Teile verlassen es über „Teil entnehmen““). Wirkung in einer
  Transaktion: ein offener Lauf ohne Prüfung endet (`set_lauf_abgebrochen`, Grund „Set aufgelöst“); die Teile verlieren
  ihr Set in EINER Anweisung und bleiben frei im Ordner des Sets mit ihrer Zuordnung (Journal „aus_set_geloest“); der
  Set-Artikel wird gelöscht (Kopie der Stückliste per CASCADE), sein letzter Eintrag ist „geloescht“ `{grund: „Set
  aufgelöst“, teile}` – eine wiedervergebene Kennung zeigt den alten Verlauf nicht (S15). Ungeprüfte neue Teile lassen
  sich danach einzeln löschen. Ein Set, das je gesperrt war, ist nicht mehr auflösbar (frei wird es nur über eine
  Set-Prüfung) – im Jahresbericht fällt keine Sperre weg.
- **„Bestandteil ersetzt“** (Entwurf B; T4, T5, T15, U5, U13): `POST /artikel/<Set>/bestandteil-ersetzt` (verwalten) an
  einer nicht einzeln geführten Position der Kopie dieses Sets (sonst 404 wie unbekannt): „Austausch laut Hersteller“
  „ja“ ohne, „nicht belegt“ mit Pflichtbestätigung („laut Herstellerunterlagen zulässig“), „nein“ 409; Datum höchstens
  heute (Vorgabe heute), Bemerkung einzeilig ≤ 200 Zeichen; ausgesondert 409; **offener Entwurf am Set selbst 409** („…
  Erst festschreiben oder verwerfen – die begonnene Prüfung hat den ersetzten Bestandteil nicht gesehen.“). Wirkung:
  Journal am Set „bestandteil_ersetzt“ `{slot, bestandteil, datum, bemerkung, austausch, bestaetigt}`, Sperre wie beim
  Tausch (`set_grund` „bestandteil“, am freien Set Journal „gesperrt“ – im Jahresbericht Art „set“, am schon gesperrten
  Set keine zweite Sperre), danach in derselben Transaktion `set_pruefen = 1` an der **Zeile des Set-Artikels**
  (`sets.bestandteil_markieren`, nach der Kaskade, nie über `neu` – eine eigene Sperre des Set-Artikels bleibt mit ihrem
  Grund; `_kaskade` weist die Set-Kennung in `neu` ab). `anlass_text` und `sperrgruende` kennen den Marker („Bestandteil
  ersetzt – Set prüfen“, Art „bestandteil“); Freigabe und Aussondern setzen ihn zurück. Prüfumfang: das Set selbst mit
  seinen „vorhanden/fehlt“-Zeilen. Das Lebensende des Sets bleibt.
- **Bestandsimport**: Die Set-Zeile geht weiter in die Nacharbeit, jetzt mit dem Hinweis „Hersteller-Set – der Import
  legt keine Sets an. Set über „Artikel anlegen“ mit vorhandenen Teilen anlegen („aus dem Bestand wählen“), Angaben der
  Zeile übernehmen, dann „erneut prüfen“.“ (U11, U12).
- **Beschriftungen** (gleichlautend `beschriftung.py` und `material.js`, nur die Tabellen): Aktionen „eingesetzt“ („in
  ein Set eingesetzt“), „aus_set_geloest“ („aus dem Set gelöst (Set aufgelöst)“), „bestandteil_ersetzt“ („Bestandteil
  ersetzt“); Felder `vorhanden`, `slot`, `bemerkung`; `set_grund` „bestandteil“ („Bestandteil ersetzt – Set prüfen“);
  Jahresbericht Sperrart „set“: „Set unvollständig, Teil getauscht oder eingesetzt, Bestandteil ersetzt oder Set
  ausgesondert“.

### Schnittstelle (Stand KERN A – für die Oberfläche)

Zusätzlich zu L2. Fremdes antwortet 404 wie Unbekanntes (auch `item_id` und `slot_id` als Zahl, „7“ oder 7.0).

| Methode und Pfad | Recht | Anfrage → Antwort |
| --- | --- | --- |
| `POST /api/material/artikel` mit Set-Produkt | Materialwart (wie bisher) | Teilblock `{"bestandteil_id", "item_id"}` für einen vorhandenen Artikel (gefüllte Teilfelder dazu → 400 „… nicht beides.“, dieselbe Kennung zweimal → 400) → 201 wie bisher; 404/409 wie bei „Teil einsetzen“; alles oder nichts |
| `POST /api/material/artikel/<Set>/teil-einsetzen` | Materialwart | neu `"item_id"` statt der Felder (mit gefüllten Feldern 400), `slot_id`, `bestaetigt` wie bisher → 201 `{artikel (Set voll), teil (eingesetzt, voll), hinweise: []}`; 404 „Artikel nicht gefunden.“; 409 anderes Produkt, andere Gliederung, DEMO-Grenze, nicht frei, Teil/Set, Entwurf, Meldung, Rückruf, Lebensdauer, keine Lücke, Prüfung im offenen Lauf, inzwischen geändert |
| `POST /api/material/artikel/<Set>/teil-tauschen` | Materialwart | mit `item_id` → 400 „Tauschen geht nur mit einem neuen Teil …“ |
| `GET /api/material/artikel/<Set>/kandidaten?slot_id=&q=` | verwalten | → `{treffer: [{id, inventory_no, serial_no, bisherige_inventarnummer \| null, produkt, ordner, status, status_text, zugeordnet ({id, name, gliederung, aktiv}) \| null}], weitere}`; Position fremd/unbekannt/nicht einzeln → 404; ohne Treffer 404 „Kein passender Artikel gefunden.“ (fremd und unbekannt gleich) bzw. 409 (Nummer genau eines verwalteten Artikels mit anderem Produkt, Text wie oben); q < 2 oder > 80 Zeichen → 400; kein Set → 409 |
| `GET /api/material/ordner/<fid>/kandidaten?product_id=&q=` | verwalten | wie oben; `product_id` ein Set-Produkt → 400, unbekannt 404; Systemordner → 409 |
| `POST /api/material/artikel/<Set>/aufloesen` | verwalten | `{}` → `{ok: true, teile: [{id, inventory_no}]}`; 409 mit Grund (Text wie `set.aufloesen_hindernis`); kein Set/ausgesondert 409 |
| `POST /api/material/artikel/<Set>/bestandteil-ersetzt` | verwalten | `{"slot_id", "datum", "bemerkung", "bestaetigt"}` → `{artikel (Set voll)}`; 404 Position; 400 Datum/Bemerkung/fehlende Bestätigung; 409 „nein“, Entwurf am Set, ausgesondert |
| `DELETE /api/material/artikel/<Set>` | Materialwart (wie bisher) | mit vorhandenen Teilen 409 (Text oben) |

**Set-Block** (`artikel.set`) neu: `vorhandene_teile` (Inventarnummern eingesetzter vorhandener Artikel),
`aufloesen_hindernis` (ein Satz | null = auflösbar), `sperrgruende` mit Art „bestandteil“; `darf_loeschen` am Set
`false`, wenn es vorhandene Teile enthält. **Journal** neu: Aktionen „eingesetzt“, „aus_set_geloest“,
„bestandteil_ersetzt“; Felder `vorhanden`, `slot`, `bemerkung`; `set_grund` „bestandteil“.

Für den Dialog (Oberfläche): Zuordnung des gewählten Artikels ≠ Zuordnung des Sets → Rückfrage „Zuordnung an … endet“
(U10); Gliederungswechsel gibt es nicht (409) – Hinweis „erst verschieben“; „Bestandteil ersetzt“ mit Hinweis „Ist der
Ersatz älter als das Set, Lebensende am Set vorziehen“ und Knopf während der Anfrage gesperrt; „Set auflösen“ als
Rückfrage mit `btn danger`; Wort „vorhandenen Artikel einsetzen“ / „aus dem Bestand wählen“ (nicht „übernehmen“, U15).

### Abweichungen vom Entwurf und Entscheidungen des Baus (KERN A, mit Begründung)

1. **Journal „bestandteil_ersetzt“ mit `bestandteil` statt `bezeichnung`** (Entwurf B nennt `bezeichnung`), dazu `datum`
   und `austausch`: dasselbe Feld wie bei „teil_eingesetzt“, beschriftet als „Bestandteil“ – `bezeichnung` hätte im Verlauf
   roh gestanden.
2. **„Set auflösen“ zusätzlich nicht bei offenem Entwurf an einem Teil** (aus T7): Der Entwurf liefe sonst nach dem
   Auflösen als Einzelprüfung eines Artikels weiter, den der Prüfer als Teil begonnen hat.
3. **„Seit dem Einsetzen geprüft“ über das Journal** statt über Zeitstempel: Eintrag „angelegt“ mit dem Set bzw.
   „eingesetzt“ gegen den Eintrag „abgeschlossen“ der Prüfung (Kennungen steigen); Zeitstempel sind nur sekundengenau.
   Ohne Eintrittseintrag (Datenbank von Hand geändert) zählt jede Prüfung.
4. **Beim Anlegen zusätzlich „teil_eingesetzt“ am Set** je vorhandenem Artikel (neben `vorhanden: true` in
   „set_angelegt“): Der Lebenslauf des Sets zeigt nur Einträge am Set (S15) – so steht dort, welches Teil schon vorher
   im Bestand war.
5. **Auswahl ohne Treffer: 404, bei genauer Nummer mit anderem Produkt 409** – auch für einen verwalteten Artikel einer
   anderen Gliederung (er ist für das Konto ohnehin sichtbar); fremd und unbekannt antworten gleich.
6. **Set-Block um `vorhandene_teile` und `aufloesen_hindernis` ergänzt**, `darf_loeschen` beachtet vorhandene Teile –
   damit die Oberfläche „Löschen“ und „Set auflösen“ ohne eigenen Versuch richtig anbietet.
7. **Teilblock mit `item_id` und leeren Feldern** (`""`, `null`) gilt als vorhandener Artikel; nur gefüllte Felder
   daneben sind 400 – ein Formular schickt leere Felder mit.

### Rückweg (auf c5e1b06)

Kein Schemaschritt – der Rückweg ist unkritisch (T16): `set_pruefen = 1` an einer Set-Zeile ignoriert der L2-Code
(`anlass_text`/`sperrgruende` lesen es nur an Teilen), Freigabe und Aussondern setzen es zurück. Neue Journal-Aktionen
(„eingesetzt“, „aus_set_geloest“, „bestandteil_ersetzt“) und `set_grund` „bestandteil“ erscheinen dort roh. Eingesetzte
vorhandene Teile mit kleinerer Kennung als das Set deckt `test_stimmig_teil_vor_set` ab. **Achtung**: Auf c5e1b06 löscht
„Set löschen“ wieder alle Teile eines ungeprüften Sets – auch eingesetzte vorhandene Artikel; nach einem Rückweg ein
solches Set nicht löschen. Ein nie geprüftes Set prüft dort nach einer Teil-Sperre wieder nur den Umfang aus L2.

### Tests (KERN A)

`tests/test_material_sets_vorhanden.py` (neu, 6 Tests, Platzhalterdaten): Bestandsimport mit Set-Karabinern als eigenen
Zeilen (Nacharbeit-Hinweis), Auswahl im Ordner (bisherige Inventarnummer, Grenzen 2/80 Zeichen und 20 Treffer, LIKE-Zeichen,
fremd = unbekannt, anderes Produkt 409, DEMO und andere Gliederung ausgeschlossen), Set anlegen mit vorhandenen Teilen
(Eingabeform, Sicht/Produkt/Gliederung/DEMO/Zustände einzeln, Journal an Teil und Set); Teil einsetzen in ein gesperrtes
Set mit Durchgang und strengerem Ordnerintervall (T3: Durchgangszeile bleibt, Fälligkeit gekappt), freies Set beim
Anlegen (Durchgang des alten Zweigs nimmt heraus), Wettlauf am bedingten UPDATE (U9), Zuordnung (U10), Prüfung im offenen
Lauf (T2), `item_id` beim Tauschen; Prüfumfang P-B; Set löschen P-A und Set auflösen mit allen Bedingungen
(Fremdschlüssel-Fälle, Lauf ohne Prüfung, Prüfung seit dem Einsetzen, Wiedervergabe der Kennung); „Bestandteil ersetzt“
(Eingaben, P5/P6, Marker, Jahresbericht, Freigabe und Aussondern setzen zurück, Kaskade lehnt die Set-Kennung in `neu`
ab); Beschriftungen gleichlautend in `beschriftung.py` und `material.js` (statisch). Ergänzt:
`test_material_trennung.FELDER_IM_INHALT` um `teile[].item_id` und `item_id` (Formen B, „7“, 7.0, unbekannt),
`test_material_sets_pruefung.test_bericht_und_trennung` um die neuen Routen (Set aus B → 404 für Materialwart und
Prüfer), `test_material_ueberblick.NUR_VERWALTER_LESEN` um die beiden Auswahl-Routen (die Führungskraft liest sie nicht,
403). Die Rundum-Tabelle `test_nichts_aus_b` nimmt die neuen Routen von selbst auf.

### Bitte bestätigen (KERN A)

Aus Entwurf I (vom Bau gesetzt):
1. Vorhandenen Artikel nur beim Anlegen und Einsetzen, nicht beim Tauschen.
2. Eingesetzte vorhandene Teile kommen in den Prüfumfang; ein nie geprüftes Set prüft alle Teile.
3. Nicht einsetzbar: offener Rückruf, offene Meldung, offener Entwurf, „Lebensdauer erreicht“, Prüfung im offenen Lauf
   desselben Sets.
4. „Set löschen“ mit vorhandenen Teilen → Verweis auf „Set auflösen“.
5. „Bestandteil ersetzt“ sperrt bis zur Set-Prüfung; nicht während einer offenen Prüfung des Sets; Lebensende bleibt.

Aus dem Bau (Abweichungen oben):
6. „Austausch laut Hersteller“ gilt auch beim Einsetzen eines vorhandenen Artikels („nein“ 409, „nicht belegt“ mit
   Bestätigung) – wie beim neuen Teil.
7. Die Auswahl zeigt die bisherige Inventarnummer mit; ohne Treffer 404, bei genauer Nummer mit anderem Produkt 409 (5).
8. „Set auflösen“ auch nicht bei offenem Entwurf an einem Teil (2).
9. Beim Anlegen steht am Set je vorhandenem Teil zusätzlich „Teil eingesetzt“ (4).

### Neu (KERN Z)

- **Zählsatz „N Artikel, darunter k Teile in m Sets“** (Entwurf C). Gezählt wird weiter je Artikel. m (Zeilen mit
  Set-Produkt) und k (Zeilen mit Set, also Teile) kommen aus derselben gefilterten Menge und Gruppierung wie N. Mit
  ausgesonderte Teile und ausgesonderte Sets zählen nicht. Es gibt keinen JOIN und keine Unterabfrage auf die Set-Zeile
  und kein `TEILE_ZAHL_SQL` (Kritik T11, U7).
  - Baum (`GET /ordner`) und damit jede Ordnerantwort: `bestand_sets` = {anzahl, teile} im ganzen Zweig, neben
    `bestand`. Wird wie `zaehlung` in sichtbare Oberordner hochgerechnet.
  - Übersicht (`GET /start`): `bestand_sets` zu `bestand`; jede Zeile der `ordner_uebersicht` trägt `bestand_sets`.
  - Jahresbericht (Web-Antwort): `bestand.sets` = {anzahl, teile} und `bestand.sets_satz` (fertiger Satz oder null).
    PDF: der Satz als eigene Zeile unter „Bestand gesamt“, nur wenn es Sets gibt. Bericht zählt nach Heimat, Baum nach
    Ordner; die Summe je Gliederung ist gleich, auch bei einem gesperrten Set in „Gesperrt“.
- **Zusatz an Statuslisten** (Entwurf C, Kritik U7). Teile, die den gefilterten Status haben, deren Set aber einen
  anderen Set-Status hat: `andere_set_status` = {teile: k, sets: [{id, inventory_no, teile}], sets_gesamt}.
  - Gilt an `GET /ordner/<id>?status=…` und an `GET /faellig` (mit und ohne `?status=`).
  - Kommt nur aus der gefilterten Menge. Das Set erfüllt die Bedingung der Liste ohne Statusfilter (Ordner bzw.
    Unterbaum, Sicht, „Zugeordnet an“), das Teil die Sicht.
  - Höchstens 50 Sets in der Liste (`ANDERE_SETS_MAX`); k zählt alle.
  - Ohne Statusfilter ist es an der Ordnerliste null.
  - An den Fälligen ohne Filter ist k praktisch immer 0. Der Set-Status ist der schlechteste, und eine Sperre sperrt
    alle Teile mit. Der Zusatz greift also bei „einsatzbereit“, „bald fällig“ und Ähnlichem.
- **CSV-Export: „Set (Inventarnummer)“, „Set-Produkt“, „Set-Status“** (Entwurf D, Kritik T12). Die drei Spalten stehen
  hinter „Herkunftsordner“.
  - An einem Teil stehen die Werte seines Sets, an der Set-Zeile ihre eigenen, sonst bleiben die Spalten leer.
  - Die Werte kommen nur aus einem Wörterbuch der geladenen Zeilen (`export._set_spalten`). Fehlt die Set-Zeile in der
    Menge (verletzte Invariante), bleiben die Spalten leer und das Protokoll der App nennt die Set-Kennung. Es wird
    nichts nachgeladen.
  - Der Set-Status wird wie `sets.werte` gebildet (schlechtester aus Set-Artikel und Teilen), mit demselben Stichtag
    und derselben Schwelle wie die Spalte „Status“.
  - Die Formelvorsilbe gilt für jede Zelle; getestet mit einem Hersteller „=…“.
  - Der Bestandsimport ignoriert die drei Spalten: Alle beginnen mit „Set“, und dazu gibt es kein Synonym.
    „Set (Inventarnummer)“ wird nie zur „Bisherigen Inventarnummer“.
- **Gebündelte Erinnerungsmails** (Entwurf E, Kritiken U6, T13). Unter ARTIKEL und „Deine PSA“ stehen Set-Artikel und
  Teile immer unter einer Kopfzeile ihres Sets: „Set <Inventarnummer>  <Produkt> – Set fällig am … (in n Tagen)“ bzw.
  „Set überfällig (fällig war der …)“. Darunter stehen die anstehenden Artikel des Sets, der Set-Artikel zuerst, dann
  ein Link aufs Set: unter ARTIKEL `/material/artikel/<Set>`, unter „Deine PSA“ `/material/meine-psa/<Set>`.
  - Das gilt auch, wenn das Set selbst nicht im Plan steht (Probe P-C: Teil in 10 Tagen fällig, Set in 300 Tagen).
  - Die Set-Fälligkeit ist die früheste nächste Prüfung aus Set-Artikel und Teilen, wie in den Listen.
  - Set-Nummer, Set-Produkt und Set-Fälligkeit kommen aus derselben Kandidatenabfrage (LEFT JOIN auf das Set und sein
    Produkt). Je Zeile wird nichts nachgeladen.
  - Betreff und Zahlen (`erinnerung.zahlen`, Probelauf, `flask material remind --trocken`) zählen ein Set einmal, in
    seiner dringendsten Stufe. Beispiele: „Material: 1 Set überfällig“, gemischt „2 überfällig (davon 1 Set)“,
    „Deine PSA: 1 Set in 30 Tagen fällig“. Ein einzelner Artikel zählt wie bisher.
  - Die Zahl am Ordner („Pfad (n)“) zählt ein Set als eine Zeile.
  - Grenzen: An `MAIL_ARTIKEL_MAX` und `MAIL_PSA_MAX` ist ein Set eine Zeile. Darunter stehen höchstens
    `MAIL_SET_TEILE_MAX` = 10 seiner Artikel, der Rest als „… und n weitere Teile“.
  - Log je Artikel wie bisher (A27). Vermerkt wird alles, was die Mail nennt, auch gezählte weitere.
- **Mangel-Mail an einem nur mitgesperrten Artikel** (lock_cause „set“). Bisher stand dort „Er war schon gesperrt
  (Mangel gemeldet am …); die Sperre bleibt.“, also mit dem eben gesetzten Grund. Jetzt steht dort:
  - an einem Teil: „Er war bisher nur mit dem Hersteller-Set S-… gesperrt; jetzt ist er zusätzlich aus eigenem Grund
    gesperrt (diese Meldung). Freigeben kann das Set nur ein Prüfer mit der Set-Prüfung.“;
  - am Set-Artikel: „Das Set S-… war schon gesperrt; der Set-Artikel selbst ist jetzt zusätzlich aus eigenem Grund
    gesperrt (diese Meldung). …“.

  Ein schon aus eigenem Grund gesperrter Artikel behält den bisherigen Satz. Die Mail an die zugeordnete Person war
  schon set-bewusst und bleibt.

### Schnittstelle (Stand KERN Z – für die Oberfläche)

| Antwort | Feld | Inhalt |
| --- | --- | --- |
| `GET /api/material/ordner` (jeder Knoten mit Zahlen), `GET /ordner/<id>` (Kopf) | `bestand_sets` | {anzahl, teile} im Zweig |
| `GET /api/material/start` | `bestand_sets` | {anzahl, teile} zu `bestand` |
| `GET /api/material/start` → `ordner_uebersicht[]` | `bestand_sets` | {anzahl, teile} der Zeile |
| `GET /api/material/ordner/<id>?status=…` | `ordner.andere_set_status` | {teile, sets: [{id, inventory_no, teile}], sets_gesamt} oder null ohne Status |
| `GET /api/material/faellig` | `andere_set_status` | wie oben (immer da) |
| `GET /api/material/ordner/<id>/bericht` | `bericht.bestand.sets`, `bericht.bestand.sets_satz` | {anzahl, teile}; Satz oder null |
| CSV `/material/export/<id>.csv` | Spalten 17–19 | „Set (Inventarnummer)“, „Set-Produkt“, „Set-Status“ |

Formulierungen für die Oberfläche (Vorschlag aus Entwurf C):
- Satz: „N Artikel, darunter k Teile in m Sets“, nur wenn `anzahl` oder `teile` > 0. Singular „1 Teil“, „1 Set“, wie
  `bestand.zaehlsatz`.
- Unter einer Statusliste: „Dazu k Teile mit diesem Status in Sets mit anderem Set-Status: S-…“, mit Links auf
  `/material/artikel/<id>`.

### Abweichungen vom Entwurf (KERN Z, mit Begründung)

- **`routes.py` geändert** (Datei von KERN A), nur zwei Zeilen und zwei Doku-Zeilen:
  - `start()`: `bestand_sets=bestand.zaehlung_sets()`;
  - `faellig()`: `andere_set_status=…`.

  Die Felder in bestehende Wörterbücher zu legen (`sets` der Fälligen) hätte Tests in test_material_sets.py gebrochen,
  die `sets == {anzahl, teile}` genau vergleichen. Beim Zusammenführen sind es zwei eindeutige Einfügungen.
- **Set-Daten in den Mails per LEFT JOIN** in der Kandidatenabfrage. Kritik T13 schlug vor, nur `parent_item_id`
  aufzunehmen und die Nummer aus der Set-Zeile derselben Mail zu nehmen. Das ginge nicht, wenn das Set nicht im Plan
  steht (U6). Entwurf Fassung 2 verlangt „in derselben Kandidatenabfrage“, das ist so umgesetzt.
- **Zahlen im Laufstand** (`verschicken`: `artikel`, `psa`) zählen weiter je Artikel. Das ist der Gegenwert zum Log
  (A27). Nur Betreff, Mailtext und `zahlen()` zählen ein Set einmal.
- **Fällige ohne Statusfilter**: `andere_set_status` steht immer in der Antwort, ist dort aber praktisch immer 0 (siehe
  oben).

### Tests (KERN Z)

- Neu: `tests/test_material_sets_zahlen.py` mit 6 Tests, alle grün.
  - `test_zaehlsatz`: Baum, /start, Ordner-Übersicht und Bericht (Web und PDF-Text); Summe Bericht = Baum, auch
    gesperrt; fremde Gliederung und Ausgesondertes zählen nicht; ohne Sets kein Satz.
  - `test_andere_set_status`: Ordnerliste und Fällige mit Status, Unterbaum, fremde Gliederung (404 bzw. nur eigenes
    Set), gesperrtes Set.
  - `test_csv_set_spalten`: Spalten und Werte an Set-Zeile, Teilen und freien Artikeln; Set-Status ≠ eigener Status;
    Formelvorsilbe; fehlende Set-Zeile mit Log; Export → Bestandsimport-Probelauf (Spalten ignoriert,
    `bisherige_nummer` je Zeile die eigene).
  - `test_mails_probe_pc`: Probe P-C, Log nur fürs Teil, dringendste Stufe, gemischter Betreff, Deine PSA.
  - `test_mails_grenze`: Set mit 30 Teilen, MAIL_ARTIKEL_MAX/MAIL_PSA_MAX = 1, „… und 21 weitere Teile“, Log
    vollständig.
  - `test_mangel_mail_mitgesperrt`: Teil, Set-Artikel, eigener Grund.
- Bestehende Suite: siehe Bericht (volle Suite mit ST_REPO auf den Worktree).
- Bericht-PDF mit Set-Satz: veraPDF PDF/A-3b PASS.

### Bitte bestätigen (KERN Z)

1. Zählsatz „N Artikel, darunter k Teile in m Sets“ an Baum, Übersicht (gesamt und je Zeile) und Jahresbericht (Web und
   PDF), nur wenn es Sets gibt; ausgesonderte zählen nicht (Entwurf I Nr. 6).
2. Zusatz an Statuslisten als eigenes Feld `andere_set_status`, an der Ordnerliste nur mit Statusfilter, an den Fälligen
   immer; höchstens 50 Sets genannt (Entwurf I Nr. 6).
3. CSV-Spalten hinter „Herkunftsordner“, an der Set-Zeile die eigenen Werte (Entwurf I Nr. 7).
4. Mails: Teile immer unter ihrem Set mit Set-Fälligkeit und Link; die Gruppe zählt einmal in ihrer dringendsten Stufe,
   gemischt „n überfällig (davon m Sets)“; Set-Artikel steht als eigene Zeile unter der Kopfzeile, wenn er selbst
   ansteht (Entwurf I Nr. 8).
5. `MAIL_SET_TEILE_MAX` = 10 Artikel je Set in einer Mail (Wert vom Bau gesetzt, keine Fachangabe).
6. Link aufs Set unter „Deine PSA“ auf die Karte unter „Meine PSA“ (`/material/meine-psa/<Set>`), nicht auf die
   Artikelseite (die Person hat oft keine Modulstufe).
7. Mangel-Mail an nur mitgesperrten Artikeln: Wortlaut oben; „Freigeben kann das Set nur ein Prüfer mit der
   Set-Prüfung.“
8. `routes.py` zwei Zeilen (siehe Abweichungen) – beim Zusammenführen mit KERN A übernehmen.

### Oberfläche (23.10.2026)

`material.js` und `material.css` nach den Schnittstellen KERN A und KERN Z; dazu eine kleine Server-Ergänzung
(`beschriftung._listen_wert`). Kein Schemaschritt, keine neuen Abhängigkeiten.

- **„Aus dem Bestand wählen“** (Entwurf A): Jeder Teilblock beim Anlegen eines Sets und der Dialog „Teil einsetzen“
  haben oben die Wahl „neu erfassen“ | „aus dem Bestand wählen“ (`teilBlockHtml(…, mitBestand)`, `bestandWahl`). Beim
  Tauschen gibt es sie nicht (T9). Die Suche läuft ab 2 Zeichen über `GET /ordner/<Ablageordner>/kandidaten` bzw.
  `GET /artikel/<Set>/kandidaten`; ein Treffer zeigt Inventar- und Seriennummer, Status, bisherige Inventarnummer,
  Produkt, Ordner und „zugeordnet an …“, `weitere` als „Weitere Treffer – bitte genauer tippen.“. Fehlertexte des
  Servers (404 „Kein passender Artikel gefunden.“, 409 anderes Produkt) stehen rot am Feld (`aria-invalid`). Der
  gewählte Artikel steht mit „anderen wählen“ darunter; Hinweis „Lebenslauf und Protokolle gehen mit …“. Beim Anlegen
  ist ein schon für ein anderes Teil gewählter Artikel ausgegraut, ein Fehler des Servers mit seiner Inventarnummer
  steht am Block. Ist ein gewählter Artikel jemand anderem zugeordnet als das Set, fragt eine Rückfrage „Zuordnung
  endet“ (U10). „Anlegen und nächsten“ setzt die Blöcke auf „neu erfassen“ zurück.
- **Set auflösen / Set löschen**: „Set auflösen …“ im neuen Untermenü „Mehr“ der Set-Seite (Materialwart, nicht am
  ausgesonderten Set). Ist `aufloesen_hindernis` gesetzt, öffnet der Eintrag einen Dialog mit dem Grund – kein
  ausgegrauter Eintrag mit Text darunter. Sonst Rückfrage mit `btn danger` („Set auflösen“), danach zum Ordner.
  Enthält das Set vorhandene Teile (`vorhandene_teile`) und wäre es auflösbar, steht statt „Löschen“ der Knopf „Löschen …“:
  Der Dialog erklärt, dass „Löschen“ nur mit dem Set angelegte Teile löscht, und führt mit „Set auflösen …“ weiter.
- **„Bestandteil ersetzt“** (Entwurf B): Die Positionen ohne eigenen Artikel stehen jetzt als eigene Zeilen in der
  Tabelle „Bestandteile“ („1 × ohne eigenen Artikel“), für den Materialwart mit dem Untermenü „Austausch“ →
  „Bestandteil ersetzt …“. Bei „Austausch laut Hersteller: nein“ ist der Eintrag ausgegraut mit Grund (wie „Teil
  tauschen“, V14). Der Dialog: „Ersetzt am“ (Vorgabe heute, spätestens heute), Bemerkung (eine Zeile, höchstens
  200 Zeichen = `setaustausch.BEMERKUNG_MAX`, „keine Personennamen“), bei „nicht belegt“ die Pflichtbestätigung (Knopf
  bis dahin aus), Hinweis „Ist der Ersatz älter als das Set, Lebensende am Set vorziehen“ mit Link „Lebensende am Set
  ändern“ (öffnet „Bearbeiten“; nur bei textilem Material, wo es das Feld gibt). Der Knopf ist während der Anfrage
  gesperrt („Wird eingetragen …“). Der Sperrgrund „Bestandteil ersetzt – Set prüfen“ steht im GESPERRT-Banner, unter
  „Gesperrt, weil“ der Set-Seite, an jedem mitgesperrten Teil und in „Meine PSA“ (Sperrgrund der Set-Karte).
- **Zahlen** (Entwurf C): Zählsatz „N Artikel, darunter k Teile in m Sets“ (`zaehlSatz`, gleich `bestand.zaehlsatz`)
  unter den Kacheln der Übersicht, im Ordnerkopf („Bestand im ganzen Zweig: N, darunter k Teile in m Sets“), im
  Jahresbericht (`sets_satz`) und als Tooltip an der Bestandszahl im Baum der Seite „Bestand“; in der Tabelle
  „Fälligkeiten je Ordner“ kurz „k Teile in m Sets“ unter der Bestandszahl (Vorlesehilfen hören den ganzen Satz). Nur
  wenn es Sets gibt. Unter Statuslisten (Ordner mit Statusfilter, Fällige): „Dazu k Teile mit diesem Status in Sets
  mit anderem Set-Status: M-… “ mit Links, „und n weitere“ über 50 Sets; bei „alles Fällige“ „mit einem dieser Status“.
- **Knöpfe** (F): „Sperren“ und „Melden und sperren“ sind `btn` (rot gefüllt, die Hauptaktion) statt `btn danger` –
  Kommentare und `test_material_mangel` nachgezogen. Journalzeilen höchstens 90 Zeichen breit (V18,
  `.mat-journal > li { max-width: 90ch; }`).
- **Journal und Werte**: „in ein Set eingesetzt“, „aus dem Set gelöst (Set aufgelöst)“, „Bestandteil ersetzt“,
  „vorhandener Artikel“, „Position Nr.“, „Bemerkung“, `set_grund` „Bestandteil ersetzt – Set prüfen“ standen schon in
  den Tabellen (KERN A); neu: In Teilelisten (etwa „Set mit Teilen angelegt“) steht an einem vorhandenen Teil
  „, vorhandener Artikel“ – gleich in `listenWert` (material.js) und `beschriftung._listen_wert` (Lebenslauf-PDF).
  Der Nacharbeit-Hinweis an Set-Zeilen eines Bestandsimports („… „aus dem Bestand wählen“ …“) steht in der Spalte
  „Gründe“ der Nacharbeit (geprüft im Browser).

#### Abweichungen (Oberfläche, mit Begründung)

1. **„Set auflösen …“ im Untermenü „Mehr“ der Kopfzeile**, nicht in „Austausch“: „Austausch“ hängt je Position, das
   Auflösen betrifft das ganze Set.
2. **Positionen ohne eigenen Artikel als Tabellenzeilen** statt der Zeile „Ohne eigenen Artikel: …“ – sonst gäbe es
   keinen Ort für das Untermenü je Position.
3. **„Bestandteil ersetzt“ bei „nein“ ausgegraut mit Grund** statt gar nicht angeboten – wie „Teil tauschen“ (V14); der
   Server antwortet ohnehin 409.
4. **„Löschen …“ mit Verweis nur, wenn das Set auflösbar wäre**; sonst bleibt der Löschknopf weg wie bisher bei
   `darf_loeschen` = false (der Grund steht dann unter „Mehr → Set auflösen …“).
5. **Rückfrage „Zuordnung endet“ mit `btn`, nicht `btn danger`** (eigene `rueckfrage` statt `S.confirm`): Sie ist nicht
   endgültig, die Zuordnung lässt sich am Set neu setzen.
6. **Zählsatz in der Ordner-Übersicht gekürzt** („k Teile in m Sets“ unter der Zahl, ganzer Satz für Vorlesehilfen) und
   im Baum nur als Tooltip – ein ganzer Satz sprengt die Zahlenspalte; die Ordnerleiste links bleibt ohne Satz.
7. **Lebensende-Weg nur bei textilem Material als Link**: Nur dort hat „Bearbeiten“ das Feld „Lebensende“.
8. **Server-Ergänzung `beschriftung._listen_wert`** (vorhandene Teile in Listen) – damit Journal und Lebenslauf-PDF gleich
   lauten; Test in `test_material_sets_oberflaeche`.

#### Tests (Oberfläche)

- `tests/test_material_sets_oberflaeche.py`: neu `test_oberflaeche_l2b_statisch` (Haken aller Wege, Wortwahl ohne
  „übernehmen“, Grenze der Bemerkung gleich dem Dienst, Zählsatz gleich `bestand.zaehlsatz`, Knopfsprache je Dialog,
  CSS mit Container-Abfrage und 44 px unter `pointer: coarse`, V18) und `test_vertrag_l2b` (Auswahl, Set-Block,
  Teil einsetzen mit `item_id`, „Bestandteil ersetzt“, Set auflösen, `bestand_sets`, `andere_set_status`, `sets_satz`);
  der O2-Haken auf den Teilblock beim Anlegen angepasst.
- `tests/test_material_mangel.py`: „Melden und sperren“ als `btn`.
- Browserprobe (Chromium 1280 und 360 px, DEMO-Daten in eigenem Datenordner): Anlegen mit „aus dem Bestand wählen“
  (Treffer, 404/409 am Feld, belegt, Anlegen), Teil einsetzen mit Rückfrage „Zuordnung endet“, Set auflösen (Grund und
  Rückfrage), Löschen mit Verweis, Bestandteil ersetzt (mit Bestätigung, danach Banner, Sperrgründe, Meine PSA),
  Zählsätze (Übersicht, Ordner, Baum, Bericht), Statuslisten-Hinweis (Ordner, Fällige), Sperren und Mangel melden als
  `btn`, Nacharbeit-Hinweis; keine Konsolenfehler, kein waagerechter Bildlauf bei 360 px. `st-geraete` (Chromium,
  Firefox, WebKit × 21 Geräte) für zwei Set-Seiten, Anlegen mit Set-Produkt und Übersicht: alle 252 Aufrufe ohne Befund.

#### Bitte bestätigen (Oberfläche)

1. „Set auflösen …“ im Untermenü „Mehr“ der Set-Seite; geht es nicht, ein Dialog mit dem Grund (1).
2. Positionen ohne eigenen Artikel als Zeilen der Tabelle „Bestandteile“ mit „Austausch → Bestandteil ersetzt …“;
   bei „nein“ ausgegraut mit Grund (2, 3).
3. Rückfrage „Zuordnung endet“ als rote Hauptaktion (`btn`), nicht als `btn danger` (5).
4. Zählsatz kurz in der Tabelle „Fälligkeiten je Ordner“, als Tooltip im Baum, ganz unter den Kacheln, im Ordnerkopf und
   im Jahresbericht (6).
5. „Sperren“ und „Melden und sperren“ rot gefüllt (`btn`) – umgesetzt wie entschieden; damit ist V19 erledigt.
6. Bemerkung bei „Bestandteil ersetzt“ als einzeiliges Feld mit Hinweis „keine Personennamen“; Datum „Ersetzt am“ mit
   Vorgabe heute.

### Prüfung vor Auslieferung (23.10.2026)

Drei Prüfungen am Stand 3028eda: **Sicherheit** (`planung/material-phase4/pruefung_l2b_sicherheit.md`, ein Befund hoch,
dazu Hinweise), **Ablauf** (`pruefung_l2b_ablauf.md`, A1–A3 niedrig, eine Anmerkung) und **Browser**
(`pruefung_l2b_browser.md`, B1–B4, V1–V17; `st-geraete` in drei Engines ohne Befund). Danach die Nachbesserung (Dienste,
Oberfläche, Tests `tests/test_material_sets_l2b_nachbesserung.py` neu, `test_oberflaeche_l2b_nachbesserung_statisch`
neu, `test_material_sets_vorhanden` erweitert). **Kein Schemaschritt** (Schema bleibt 21), keine neuen Abhängigkeiten.

**Sicherheit**

| Nr. | Befund | Stand |
| --- | --- | --- |
| H1 (hoch) | Vorhandener Artikel mit übrig gebliebenem `lock_cause` „eigen“: „aussondern“ an einer Position „Austausch: nein“ wirkungslos, Set-Protokoll „einsatzbereit“ | Behoben, vierfach: (a) `vorhandenen_einsetzen` setzt im bedingten UPDATE `lock_cause = NULL, lock_reason = '', set_pruefen = 0`; (b) die Einzel-Freiprüfung (`pruefung._wirkung`, „einsatzbereit“) setzt `lock_cause = NULL`; Altzeilen (frei mit Ursache) bereinigt `sets.beim_start` bei jedem Start (wiederholbar, ohne Journaleintrag – die Ursache zeigt keine Ansicht –, Kennungen im Log); (c) `setaustausch.teil_bleibt_gesperrt` hängt an `sets._eigen_gesperrt` (Sperrzustand), sonst sperrt die Kaskade wie bei jedem freien Teil; (d) `setlauf.wirkung`: An einem freien Set mit einem Teil, das im Lauf nicht „einsatzbereit“ geprüft wurde, schreibt „einsatzbereit“ am Set-Artikel nicht fest (409 „… Erst … sperren …“). Test genau nach der Probe p9/p9b (`test_h1_altwert_eigen`), dazu Absicherung und Startbereinigung (`test_h1_absicherung_und_start`) |
| Hinweis | „Bestandteil ersetzt“: Datum ohne Untergrenze („01.01.1900“ bleibt unveränderlich im Journal) | Behoben: frühestens am Tag der Erfassung des Sets (`created_at`; 400 „„Ersetzt am“ liegt vor der Erfassung des Sets …“); die Oberfläche nennt die Grenze und prüft sie am Feld |
| Hinweis | „Bestandteil ersetzt“ dreimal gleichzeitig → drei Einträge | Behoben: dieselbe Position mit demselben Datum und derselben Bemerkung innerhalb von 60 s (`DOPPELT_SEKUNDEN`) → 409 „… ist schon eingetragen …“ (in BEGIN IMMEDIATE, also auch für gleichzeitige Anfragen) |
| Hinweis | Löschkonzept nennt die Freitext-Bemerkung von „Bestandteil ersetzt“ nicht | Behoben: `loeschung.py` und Absatz „Löschkonzept“ unten |
| Hinweis | Journal „verschoben“ nennt beim Einsetzen in ein gesperrtes Set die Heimat als Ziel | Nicht geändert: nur Darstellung; der folgende Eintrag „set_gesperrt“ nennt „Gesperrt“ – so steht der Weg vollständig im Lebenslauf |

**Ablauf**

| Nr. | Befund | Stand |
| --- | --- | --- |
| A1 | Sperrgrund „… war selbst gesperrt“ an einem eingesetzten vorhandenen Artikel | Behoben: `sets._pruef_anlass` vergleicht im Journal des Teils den Beitritt (`sets.beitritt`) mit dem letzten Eintrag mit eigener Ursache – „wurde eingesetzt (vorhandener Artikel)“, „war selbst gesperrt“, „ist neu im Set“ oder neutral „ist zu prüfen“ (`test_a1_sperrgrund_eingesetzt`) |
| A2 | Journal „gesperrt“ und Jahresbericht nennen bei „Bestandteil ersetzt“ „Set-Prüfung ausstehend“ | Behoben: Die Kaskade setzt bei `set_grund` „bestandteil“ die Marke `set_pruefen` an der Set-Zeile im selben `set_lage` (nur am freien Set; ein schon gesperrtes markiert wie bisher `bestandteil_markieren`, eine eigene Sperre bleibt, T4). Journal, mitgesperrte Teile und Sperrliste des Berichts: „Bestandteil ersetzt – Set prüfen“ (Test in `test_bestandteil_ersetzt`) |
| A3 | Auswahl schneidet nach 200 Zeilen vor dem Nachfiltern ab | Behoben: Die Auswahl liest seitenweise (200 je Seite, Schlüssel Inventarnummer + Kennung) weiter, bis 21 echte Treffer da sind oder nichts mehr kommt; die DEMO-Grenze steht in der Abfrage. Test mit 250 Bemerkungen „Standort: Halle K-2“ (`test_a3_auswahl_viele_fehltreffer`) |
| Anmerkung 4 | 409 beim Löschen verweist auf „Set auflösen“, auch wenn das nicht geht | Behoben: Ist das Set nicht auflösbar, nennt der Text den Grund („Auflösen geht auch nicht: …“) |
| Probe 6 | Nacharbeitshinweis an einem schon angelegten Set nach Re-Import | Nicht geändert: schadet nicht (Prüfung: „überflüssig“); die Zeile „erneut prüfen“ erledigt ihn |

**Browser** (Befunde)

| Nr. | Befund | Stand |
| --- | --- | --- |
| B1 | Journal „Bestandteil ersetzt“: „Position Nr.“ ist die interne Kennung der Kopie | Behoben: Feld `position` = Nummer der Position in der Stückliste (1, 2, …), beschriftet „Position“ (Journal und Lebenslauf-PDF); `slot` schreibt niemand mehr, ältere Einträge (nur Stand vor der Nachbesserung, nicht ausgeliefert) heißen ehrlich „Kennung der Position“ |
| B2 | Bestandsimport erkennt „Bisherige Inventarnummer“ nicht | Behoben: „bisherige inventarnummer“, „alte inventarnummer“, „bisherige nummer“, „alte nummer“ in `UEBRIGE`; „Set (Inventarnummer)“ bleibt ignoriert (Export → Import hält, `test_csv_set_spalten`); der Probelauf warnt bei einer ignorierten Spalte mit „Inventar“ im Titel (außer den Set-Spalten des Exports, einer ausdrücklichen Wahl und einer Doppelung) |
| B3 | Normale Leerzustände und Eingabefehler erzeugen HTTP 4xx (Konsolenfehler) | Behoben: Auswahl ohne Treffer 200 `{treffer: [], weitere: false, hinweis: null}` – fremd und unbekannt weiter gleich; anderes Produkt als `hinweis` {text, artikel} in der 200-Antwort (kein Informationsleck: genannt wird nur ein Artikel, den das Konto verwaltet – wie bisher im 409). Datumsfelder mit Grenzen (`datumFeld(…, {min, max})`, `datumWert` prüft) – der Fehler steht am Feld, bevor etwas gesendet wird |
| B4 | „Schließen“ in Hinweis-Dialogen rot | Behoben: `btn secondary` in „Set auflösen“ (Grund) und `aussondern-warum` |

**Browser** (Verbesserungen)

| Nr. | Vorschlag | Stand |
| --- | --- | --- |
| V1 | Statuslisten-Hinweis ohne Set-Status, wie Kleingedrucktes | Behoben: `.notice small`, „2 Teile sind einsatzbereit, ihr Set M-… ist insgesamt [neu] und steht in der Liste „neu““; bei mehreren Sets je Set Link und Statusmarke. Server: `andere_set_status.sets[]` mit `status`, `status_text` |
| V2 | „Teil einsetzen“ am Telefon: Pflichtbestätigung unter dem Falz, Knopf grau ohne Grund | Behoben: Der Knopf sieht bis zum Häkchen ausgeschaltet aus (`aria-disabled`, `.btn.mat-aus`), bleibt aber antippbar – ein Tipp holt die Bestätigung ins Bild, setzt den Fokus darauf und sagt „Bitte erst bestätigen …“ (`pflichtBestaetigung`; auch „Teil tauschen“ und „Bestandteil ersetzt“) |
| V3 | „Set auflösen“ ohne sichtbare Quittung | Behoben: Quittung auf der Ordnerseite (`role="status"`, Fokus): „Set M-… aufgelöst – M-… und M-… liegen jetzt frei in <Ordner>.“ – über `sessionStorage` dieses Fensters, einmal; ohne Speicher bleibt der Toast |
| V4 | Menü „Mehr“ mit einem Eintrag, „Löschen …“ uneinheitlich | Behoben: Untermenü „Auflösen / Löschen“ (bzw. „Auflösen“) mit „Set auflösen …“ und „Set löschen …“; am Set kein eigener Löschknopf mehr (am Artikel und am Teil bleibt „Löschen“) |
| V5 | Serverfehler beim Anlegen dreifach | Behoben: am Block (Fokus dorthin) und als Toast; der Absatz über dem Knopf nur, wenn kein Block getroffen ist |
| V6 | Zu viel Erklärtext im Dialog „Bestandteil ersetzt“, Lebensende-Satz auch bei Metall | Behoben: ein Hinweiskasten (Sperre, „nicht belegt“, Lebensende); der Lebensende-Satz nur bei textilem Material, als Weg („Bearbeiten“ → „Lebensende“) statt Link – der schloss den Dialog und verwarf Datum und Bemerkung |
| V7 | Sperrgrund in drei Wortlauten, doppelter Gedankenstrich im Banner | Behoben: überall „Bestandteil ersetzt – Set prüfen“ (unter „Gesperrt, weil“ mit „(dabei die Bestandteile ansehen)“); Set-Banner „GESPERRT: <Grund>. …“ |
| V8 | Zählsatz im Baum nur als Tooltip | Behoben: zusätzlich als versteckter Text für Vorlesehilfen (`.mat-vorlesen`) statt `aria-label` – an einem `span` ohne Rolle lesen Vorlesehilfen `aria-label` nicht zuverlässig |
| V9 | „k Teile in m Sets“ bricht um | Behoben: `white-space: nowrap` |
| V10 | „Führt ihr …“ | Behoben: „Führst du ein Teil schon im Bestand, wähle es aus dem Bestand.“ |
| V11 | Journal beim Anlegen mit vorhandenen Teilen dreifach | Behoben: am Set nur „Set mit Teilen angelegt“ (je Teil „vorhandener Artikel“, auch im Lebenslauf-PDF); die Einzel-Einträge „Teil eingesetzt“ am Set beim Anlegen entfallen (S15 hält: der Lebenslauf des Sets zeigt die Liste; die Teile tragen „eingesetzt“ selbst). Ersetzt KERN-A-Abweichung 4 |
| V12 | Meldung „anderes Produkt“ ohne Weg | Behoben: „M-… ist <Produkt>; an dieser Position steht <Produkt>. Einsetzen lässt sich nur ein Artikel dieses Produkts.“ mit Link „M-… öffnen“ (neuer Reiter). Der vorgeschlagene Weg „Artikel öffnen → Bearbeiten“ existiert nicht – „Bearbeiten“ hat kein Produktfeld (siehe Bitte bestätigen) |
| V13 | Piktogramm „📷“ im Mangel-Dialog | Behoben modulweit: „📷“ in allen Datei- und Kamera-Knöpfen (Mangel, Foto wählen, Prüfpunkt-Foto, Anhang fotografieren, Produktmeldung) und „📖“ an „Prüfanleitung aus dem Wiki“ entfernt. Nicht geändert: 🔒 an Systemordnern im Baum (kein Knopf) und die Bedienzeichen ☰, ✕, ↑ ↓, ▲ ▼ (siehe Bitte bestätigen) |
| V14 | WebKit-„x“ im Suchfeld | Nicht geändert (Auftrag): Engine-Unterschied |
| V15 | Teilquelle-Radios am Telefon je eine Zeile | Behoben: unter `pointer: coarse` nebeneinander (`flex-wrap: nowrap`), der Text bricht im Feld um, 44 px bleiben |
| V16 | Nacharbeit-Hinweis der Set-Zeile zu lang | Behoben: „Sets legt der Import nicht an – über „Artikel anlegen“ mit „aus dem Bestand wählen“ erfassen, dann „erneut prüfen“.“ |
| V17 | Datum in der Zukunft nicht am Feld | Behoben mit B3 |
| Abgleich | CHANGELOG/README „Ordnerleiste“ | README: „Übersicht, Ordnerbaum und Jahresbericht“ |

**Schnittstelle (Nachbesserung)** – Änderungen gegenüber KERN A/Z:
- `GET …/artikel/<Set>/kandidaten`, `GET …/ordner/<fid>/kandidaten`: immer 200 `{treffer, weitere, hinweis}` (bisher 404
  ohne Treffer, 409 bei anderem Produkt); `hinweis` = null oder {text, artikel: {id, inventory_no}}. 400/403/404 für
  Eingabe, Recht und Position/Produkt wie bisher.
- `andere_set_status.sets[]` zusätzlich `status`, `status_text`.
- `POST …/bestandteil-ersetzt`: Datum vor der Erfassung des Sets 400; Doppelung 409. Journal `position` statt `slot`.
- `DELETE /artikel/<Set>` mit vorhandenen Teilen: Text mit Grund, wenn Auflösen nicht geht.
- `POST /artikel` mit vorhandenen Teilen: am Set nur „set_angelegt“ (kein „teil_eingesetzt“ je Teil).
- Festschreiben der Set-Prüfung: 409 an einem freien Set mit nicht „einsatzbereit“ geprüftem Teil im Lauf.

**Löschkonzept**: Die Freitext-Bemerkung von „Bestandteil ersetzt“ (höchstens 200 Zeichen, einzeilig) steht unveränderlich
im Journal des Sets und bleibt beim Löschen eines Kontos wie das übrige Journal; der Dialog sagt „keine Personennamen“.
Steht in `services/loeschung.py`.

**Rückweg** (auf c5e1b06 bzw. 3028eda): unverändert unkritisch – kein Schemaschritt. Die Startbereinigung ist eine
Datenkorrektur ohne Gegenstück (ein freier Artikel ohne Ursache ist auf jedem Stand richtig). Journaleinträge mit
`position` erscheinen auf älteren Ständen roh.

**Tests**: `tests/test_material_sets_l2b_nachbesserung.py` (neu, 5 Tests: H1 nach p9/p9b, Absicherung und
Startbereinigung, A1, A3 mit 250 Fehltreffern, B2), `test_material_sets_vorhanden` (Auswahl 200/`hinweis`, ein Eintrag
beim Anlegen, Löschtext mit und ohne Auflösen, „Bestandteil ersetzt“ mit Untergrenze, Doppelklick, `position`,
Journal- und Berichtsgrund), `test_material_sets_oberflaeche` (`test_oberflaeche_l2b_nachbesserung_statisch` neu,
Vertrag nachgezogen).

**Browser** (Chromium über `cdp.py`, DEMO-Daten im eigenen Datenordner, Materialwart) bei 1280 und 360 px: Set-Seite mit
Menü „Auflösen / Löschen“ und Löschen-Verweis, Hindernis-Dialog („Schließen“ grau), Ordnerliste und Fällige mit
Statuslisten-Hinweis, „Teil einsetzen“ (kein Treffer ohne Konsolenfehler, anderes Produkt mit Link, Treffer über die
bisherige Inventarnummer, Pflichtbestätigung mit Fokus), „Bestandteil ersetzt“ (Hinweiskasten, Bestätigung, Datum am
Feld, danach Banner, „Gesperrt, weil“, Journal mit „Position 2“), „Set auflösen“ mit Quittung auf der Ordnerseite,
Zählsätze (Baum, Übersicht), Anlegen mit Set-Produkt (Radios nebeneinander), Mangel-Dialog ohne Piktogramm – ohne
Konsolenfehler, ohne waagerechten Bildlauf. `st-geraete` (Chromium, Firefox, WebKit × 21 Geräte) für zwei Set-Seiten
(frei mit vorhandenen Teilen, gesperrt nach „Bestandteil ersetzt“), Anlegen, Übersicht und Ordner: alle 315 Aufrufe ohne
Befund.

**Nebenbei behoben (aus L2)**: Der Hinweiskasten im Lebenslauf-PDF eines gesperrten Sets und seiner Teile sagt jetzt
„Nicht verwenden, bis „Set prüfen“ das Set freigibt.“ statt „… bis eine Freiprüfung ihn freigibt.“ (wie das Banner der
Artikelansicht); Test `test_lebenslauf_hinweis_set`.

### Bitte bestätigen (zusammengeführt)

Aus KERN A:
1. Vorhandenen Artikel nur beim Anlegen und Einsetzen, nicht beim Tauschen.
2. Eingesetzte vorhandene Teile kommen in den Prüfumfang; ein nie geprüftes Set prüft alle Teile.
3. Nicht einsetzbar: offener Rückruf, offene Meldung, offener Entwurf, „Lebensdauer erreicht“, Prüfung im offenen Lauf
   desselben Sets.
4. „Set löschen“ mit vorhandenen Teilen → Verweis auf „Set auflösen“ (seit der Nachbesserung nur, wenn Auflösen geht).
5. „Bestandteil ersetzt“ sperrt bis zur Set-Prüfung; nicht während einer offenen Prüfung des Sets; Lebensende bleibt.
6. „Austausch laut Hersteller“ gilt auch beim Einsetzen eines vorhandenen Artikels.
7. Die Auswahl zeigt die bisherige Inventarnummer mit; ohne Treffer und bei anderem Produkt seit der Nachbesserung 200
   (siehe 28).
8. „Set auflösen“ auch nicht bei offenem Entwurf an einem Teil.
9. *(entfällt mit der Nachbesserung V11, siehe 33)* Beim Anlegen am Set je vorhandenem Teil zusätzlich „Teil eingesetzt“.

Aus KERN Z:
10. Zählsatz „N Artikel, darunter k Teile in m Sets“ an Baum, Übersicht (gesamt und je Zeile) und Jahresbericht, nur wenn
    es Sets gibt; ausgesonderte zählen nicht.
11. Zusatz an Statuslisten (`andere_set_status`), an der Ordnerliste nur mit Statusfilter, an den Fälligen immer;
    höchstens 50 Sets genannt.
12. CSV-Spalten hinter „Herkunftsordner“, an der Set-Zeile die eigenen Werte.
13. Mails: Teile immer unter ihrem Set mit Set-Fälligkeit und Link; die Gruppe zählt einmal in ihrer dringendsten Stufe.
14. `MAIL_SET_TEILE_MAX` = 10 Artikel je Set in einer Mail.
15. Link aufs Set unter „Deine PSA“ auf die Karte unter „Meine PSA“.
16. Mangel-Mail an nur mitgesperrten Artikeln: Wortlaut siehe KERN Z.
17. `routes.py` zwei Zeilen (erledigt beim Zusammenführen).

Aus der Oberfläche:
18. „Set auflösen …“ im Untermenü der Set-Seite; geht es nicht, ein Dialog mit dem Grund (Menü seit der Nachbesserung
    „Auflösen / Löschen“, siehe 30).
19. Positionen ohne eigenen Artikel als Zeilen der Tabelle „Bestandteile“ mit „Austausch → Bestandteil ersetzt …“; bei
    „nein“ ausgegraut mit Grund.
20. Rückfrage „Zuordnung endet“ als rote Hauptaktion (`btn`), nicht als `btn danger`.
21. Zählsatz kurz in „Fälligkeiten je Ordner“, als Tooltip im Baum, ganz unter den Kacheln, im Ordnerkopf und im
    Jahresbericht.
22. „Sperren“ und „Melden und sperren“ rot gefüllt (`btn`).
23. Bemerkung bei „Bestandteil ersetzt“ einzeilig mit Hinweis „keine Personennamen“; Datum mit Vorgabe heute.

Aus der Nachbesserung:
24. **Startbereinigung**: freie Artikel mit Sperrursache verlieren sie bei jedem Start – ohne Journaleintrag, nur Log
    (die Ursache zeigt keine Ansicht). Alternative: ein Systemeintrag je Artikel.
25. **Absicherung beim Festschreiben**: ein freies Set mit einem im Lauf schlechter geprüften Teil → 409 mit Weg („erst
    sperren“) statt einer automatischen Sperre.
26. **„Bestandteil ersetzt“**: frühestens am Tag der Erfassung des Sets – ein Ersatz von vor dem Import lässt sich nicht
    mit seinem Datum eintragen (dann mit dem Erfassungstag und dem Datum in der Bemerkung). Doppelklick-Schutz: derselbe
    Eintrag (Position, Datum, Bemerkung) innerhalb von 60 s → 409.
27. Journal „Bestandteil ersetzt“ mit `position` (Nummer in der Stückliste) statt `slot`.
28. Auswahl ohne Treffer und mit anderem Produkt als 200 mit `hinweis` (mit Link auf den Artikel) statt 404/409.
29. **Produkt am Artikel**: „Bearbeiten“ hat kein Produktfeld; der Dienst ließe den Wechsel vor der ersten Prüfung zu. Soll
    die Oberfläche das anbieten (etwa für falsch importierte Artikel)? Bis dahin sagt die Meldung nur, dass das Produkt
    nicht passt.
30. Untermenü „Auflösen / Löschen“ (nur „Auflösen“, wenn Löschen nicht in Frage kommt); am Set kein eigener Löschknopf.
31. Pflichtbestätigung: Knopf sieht ausgeschaltet aus, bleibt antippbar und führt zur Bestätigung (statt `disabled`).
32. Zählsatz im Baum für Vorlesehilfen als versteckter Text statt `aria-label`.
33. Beim Anlegen mit vorhandenen Teilen nur ein Eintrag am Set (ersetzt 9).
34. Lebensende-Hinweis im Dialog „Bestandteil ersetzt“ nur bei textilem Material und als Weg ohne Link.
35. Piktogramme: „📷“ und „📖“ entfernt; 🔒 an Systemordnern im Baum und die Bedienzeichen ☰, ✕, ↑ ↓, ▲ ▼ bleiben.
36. Set-Banner „GESPERRT: <Grund>“ mit Doppelpunkt (am einzelnen Artikel bleibt „GESPERRT – <Grund>“).

## Feintuning nach dem Kommentar-Dokument (23.10.2026)

Der Nutzer hat das Kommentar-Dokument „Offene Annahmen und Fragen – Modul Material“ am 23.10.2026 freigegeben. Daraus
folgen zwei Änderungen an der App (Produkt am Artikel ändern, Jahresbericht bei ausgesonderten Sets); alle übrigen
offenen „Bitte bestätigen“ von Phase 4 · Lieferung 1, Artikellänge (Schritt 20), Lieferung 2 und Lieferung 2b gelten
wie gebaut. Ohne Schemaänderung (Schema bleibt 21).

### Antworten des Nutzers

- **L2 Nr. 37** („Austausch laut Hersteller: nein“): bleibt, wie gebaut – bei „nein“ kein Tauschen und kein Entnehmen;
  das Set sondert der Materialwart als eigenen Schritt aus.
- **L2 Nr. 39** (Jahresbericht): „Das Set sollte als ein gesperrtes Teil aufgelistet werden, wenn es als ganzes entsorgt
  wurde. Ansonsten sollten die Teile nach der Auflösung des Sets durch ihren eigenständigen Zustand gelistet werden.“ –
  geändert, siehe 2.
- **L2b Nr. 3**: Ein entnommenes, freies Teil ist wieder einsetzbar – so gebaut (jetzt mit Test).
- **L2b Nr. 14** (`MAIL_SET_TEILE_MAX` = 10 Artikel je Set in einer Mail) und **Nr. 26** („Bestandteil ersetzt“
  frühestens am Erfassungstag des Sets, Doppelklick-Schutz 60 s): bestätigt.
- **L2b Nr. 29**: „Ja, bis ein Artikel eines Produkts erstellt und geprüft wurde, soll das Produkt änderbar sein
  können.“ – geändert, siehe 1.
- Alle übrigen offenen „Bitte bestätigen“ aus P4-L1, Artikellänge, L2 und L2b: gelten wie gebaut.

### 1. Produkt am Artikel ändern (L2b Nr. 29)

- **Dialog „Bearbeiten“** hat ganz oben das Feld „Produkt“ (Anzeige wie beim Anlegen: Modell, Bemerkung, Artikelnummer,
  DEMO, Materialart) mit „anderes Produkt“ und der Produktsuche wie bei „Artikel anlegen“ (`produktTreffer`); nach der
  Wahl „zurück zum bisherigen“. Das Feld gibt es nur, solange der Artikel **keine abgeschlossene Prüfung** hat, nicht
  ausgesondert ist und weder Set noch Teil ist (`artikel.produkt_aenderbar`). Danach ist es weg – wie bei Seriennummer
  und Herstellung, aber ohne Änderungsantrag. Mit **offenem Entwurf** steht das Produkt fest mit dem Satz „Das Produkt
  lässt sich erst ändern, wenn die Prüfung festgeschrieben oder verworfen ist.“ (der Dienst antwortet sonst 409 mit
  „In Prüfung bei … seit …“ davor).
- **Vor dem Speichern** sagt ein Hinweiskasten, was der Wechsel nachzieht: Lebensende neu aus Herstellung und
  Lebensdauer des neuen Produkts (textil; die Herstellung ist dann Pflicht) bzw. weg (nicht textil); die Länge fällt
  weg, wenn die Kategorie des neuen Produkts keine vorsieht; ein kürzeres Prüfintervall rückt die nächste Prüfung vor;
  laufende Rückrufe gelten nach dem neuen Produkt. Die Felder „Lebensende“ und „Länge“ folgen der Wahl (ausgeblendet bzw.
  eingeblendet), „Herstellung (Monat, Pflicht)“ ebenso. Ein Set-Produkt lässt sich gar nicht erst wählen – der Satz
  steht am Feld (`sets.ZU_SET_PRODUKT`).
- **Dienst** (`bestand.artikel_aendern`, `produktwechsel_pruefen`, `produktwechsel_eintragen`): Rechte wie bisher
  (`verwalten` an der Heimat – Führungskraft und Prüfer 403, fremde Gliederung 404); Sets und Teile 409 mit eigenem Satz
  („… ist Teil des Sets … – sein Produkt legt die Stückliste fest …“, „Das Produkt eines Sets legt seine Stückliste
  fest …“), kein Wechsel auf ein Set-Produkt (409); abgeschlossene Prüfung 409 `PRODUKT_FEST` (der Trigger
  `mat_item_produkt_fest` fängt den Rest), offener Entwurf 409 – beides frisch unter der Schreibsperre noch einmal
  geprüft; **DEMO-Grenze**: außerhalb der DEMO-Gliederungen kein Wechsel zwischen DEMO- und echtem Produkt (409
  `PRODUKT_DEMO` – der Artikel würde sonst zu Demodaten bzw. echtem Bestand); Seriennummer je Produkt wie bisher (409 mit
  Inventarnummer, fremde Dublette protokolliert); die Gliederung ändert sich nicht.
- **Folgen**: Intervall und Herstellervorgabe aus dem neuen Produkt (ein Artikelintervall über der neuen Vorgabe → 400),
  Fälligkeit nur vorziehen (`faelligkeit.kappen`, eigener Journaleintrag „Fälligkeit vorgezogen“), Lebensende aus der
  Lebensdauer des neuen Produkts (ein von Hand vorgezogenes bleibt, wenn es früher liegt), Rückrufe produktbezogen (nichts
  gespeichert – Banner, Liste, Bericht folgen von selbst), Meine PSA und Durchgang unverändert (der Artikel bleibt
  zugeordnet und im Durchgang).
- **Journal** „produkt_geaendert“ – ein Eintrag mit allen geänderten Feldern, dazu `produkt` als lesbarer Name mit
  Artikelnummer („Testwerk HMS Beta (HB-7)“) vorher/nachher sowie `rueckruf_nicht_mehr`/`rueckruf_neu` (laufende
  Rückrufe, die den Artikel jetzt nicht mehr bzw. neu treffen); Beschriftung „Produkt geändert“, Feld „Produkt“ in
  `beschriftung.py` und `material.js`; die technische `product_id` fällt neben dem Namen weg (wie `folder_id` neben dem
  Ordner). Lebenslauf (Seite und PDF) zeigen ihn.
- **„aus dem Bestand wählen“**: Die Meldung „anderes Produkt“ nennt bei einem ungeprüften Artikel den Weg („Ist das
  Produkt am Artikel falsch: Artikel öffnen → Bearbeiten → Produkt.“, `setaustausch.PRODUKT_WEG`) – im Hinweis der
  Auswahl und im 409 beim Einsetzen; der Link heißt dann „Produkt von M-… ändern“ und öffnet die Artikelseite mit
  `?bearbeiten=produkt` (der Dialog geht mit der Produktsuche auf, der Parameter fällt danach weg). Bei geprüften
  Artikeln bleibt „M-… öffnen“.

### 2. Jahresbericht bei ausgesonderten Sets (L2 Nr. 39)

- **Aussonderungen**: Ein Set, das als Ganzes ausgesondert wurde, ist **eine Zeile** – die Aussonderung des Set-Artikels
  mit dem Zusatz „Set, mit k Teilen“ (`set_text`, Web und PDF); die Aussonderungsprotokolle der mit ausgesonderten Teile
  (sie hängen weiter am Set) zählen nicht eigens – weder in „Aussonderungen gesamt“, den Grundarten, „Bewegungen →
  Aussonderungen“ noch in „Aussonderungen durch“.
- **Sperren**: Teile, die beim Aussondern entnommen und gesperrt weitergeführt werden, zählen mit ihrer **eigenen
  Sperre** in der neuen Sperrart „aus ausgesondertem Set entnommen“ (`set_entnommen`) – aus einem freien Set wie aus
  einem gesperrten, in dem sie nur mitgesperrt waren (`lock_cause` „set“). War ein Teil schon aus eigenem Grund gesperrt
  oder verloren, zählte diese Sperre schon und zählt nicht noch einmal. Die Sperrart „set“ heißt jetzt „Set
  unvollständig, Teil getauscht oder eingesetzt oder Bestandteil ersetzt“. Die Zuordnung wird beim Abruf aus dem Journal
  gebildet – ältere Einträge zählen ebenso neu.
- Unverändert: die CSV-Prüfungsliste führt jedes Aussonderungsprotokoll (Set und Teile, je mit eigener Protokoll-ID);
  der Bestand zum Stichtag zählt ausgesonderte Artikel je Artikel.

### Schnittstelle

| Route | Änderung |
| --- | --- |
| `GET /api/material/artikel/<id>` | neu `produkt_aenderbar` (ohne abgeschlossene Prüfung, nicht ausgesondert, weder Set noch Teil) |
| `PUT /api/material/artikel/<id>` mit `product_id` | bis zur ersten abgeschlossenen Prüfung; 409 bei offenem Entwurf, Set/Teil, Set-Produkt, DEMO-Grenze; Journal „produkt_geaendert“ |
| `GET …/kandidaten` (`hinweis.artikel`) | neu `produkt_aenderbar`; `hinweis.text` mit Weg, solange ungeprüft |
| `GET /api/material/ordner/<fid>/bericht` | `sperren.arten` mit `set_entnommen`; `aussonderungen.liste[].set_text`; mit dem Set ausgesonderte Teile ohne eigene Zeile |
| Seite `/material/artikel/<id>?bearbeiten=produkt` | öffnet „Bearbeiten“ mit der Produktsuche (nur mit Recht und `produkt_aenderbar`) |

### Entscheidungen des Baus (mit Begründung)

1. **Länge beim Wechsel auf eine Kategorie ohne Länge: leeren mit Hinweis, nicht 409** – nach dem Muster der
   vorhandenen Regel (`bestand.artikel_werte`, seit der Prüfung zu Schritt 20, V4: „Wechselt ein Artikel auf ein Produkt
   ohne vorgesehene Länge, fällt sie weg“) und wie das Lebensende beim Wechsel auf nicht textil. Ein 409 hielte gerade
   die Korrektur eines falsch importierten Artikels auf, wegen eines Werts, den das richtige Produkt gar nicht kennt; der
   Dialog sagt es vor dem Speichern, das Journal behält den alten Wert.
2. **Ein Journaleintrag** „produkt_geaendert“ für das ganze Speichern (auch Bemerkung o. ä. im selben Schritt) statt
   zweier Einträge – Änderung und Folgen bleiben zusammen lesbar.
3. **DEMO-Grenze** als eigene Regel (die Gliederung ändert sich ja nicht): Ob ein Artikel DEMO ist, hängt auch am
   Produkt (`demo_sql`).
4. Fälligkeit nur vorziehen (wie bei jeder Intervalländerung) – ein längeres Intervall des neuen Produkts schiebt die
   nächste Prüfung nicht nach hinten.

### Tests

- Neu `tests/test_material_produktwechsel.py`: Regeln (Rechte, Set/Teil, Set-Produkt, Entwurf, festgeschrieben,
  DEMO-Grenze, Seriennummer je Produkt), Folgen (Lebensende, Länge, Fälligkeit, Rückrufe, Durchgang, Meine PSA,
  Lebenslauf-PDF, Beschriftung), Hinweis „anderes Produkt“ mit Weg (dazu L2b Nr. 3: entnommenes freies Teil wieder
  einsetzen), Oberfläche statisch.
- `test_material_sets_nachbesserung.py` (`test_nicht_austauschbar_und_bericht`): Sperrart `set_entnommen` aus freiem
  und gesperrtem Set, eine Zeile je ausgesondertem Set mit `set_text`, „Aussonderungen durch“, CSV mit jedem Protokoll,
  PDF mit Sperrart und Zusatz.
- Angepasst: `test_material_bericht.py` (Sperrarten), `test_material_antrag.py` (Text der 409, Signatur
  `artikelDialog(a, …)`), `test_material_stammdaten.py` (Produktfeld vor der Stammzeile).

### Im Browser geprüft

Chromium über `cdp.py`, 1280 × 900 und 360 × 780 (Touch), eigener Datenordner mit `scripts/material_demo.py --demo
--konten`: Dialog „Bearbeiten“ eines ungeprüften Artikels (Produktfeld, Suche, Wahl, Folgen-Hinweis, Lebensende
ausgeblendet, Set-Produkt mit Satz am Feld, Speichern → Journal „Produkt geändert“), Artikel mit offenem Entwurf (Satz,
kein „anderes Produkt“), geprüfter Artikel (kein Feld), Link `?bearbeiten=produkt`, Jahresbericht (Sperrart „aus
ausgesondertem Set entnommen“, eine Zeile „Set, mit 1 Teil“). Keine Konsolenfehler, kein waagrechtes Scrollen;
Jahresbericht- und Lebenslauf-PDF mit veraPDF: PDF/A-3b bestanden.

### Bitte bestätigen

1. Länge beim Wechsel auf eine Kategorie ohne Länge **leeren** (Hinweis vorher, Journal behält den Wert) statt 409.
2. Kein Wechsel zwischen DEMO- und echtem Produkt außerhalb der DEMO-Gliederungen (409).
3. Ein **ausgesondertes Set** steht nur bei den **Aussonderungen** als eine Zeile; bei den **Sperren** erscheint es nur,
   wenn es vorher gesperrt wurde (wie bisher einmal). Die CSV-Prüfungsliste und die Bestandszahl „ausgesondert“ zählen
   weiter je Artikel bzw. Protokoll.
4. Ein Teil, das in einem gesperrten Set nur mitgesperrt war und beim Aussondern weitergeführt wird, zählt jetzt als
   eigene Sperre (vorher gar nicht).

## Phase 4 · Lieferung 2 – Sets mit Komponenten (23.10.2026, Stand: geliefert und freigegeben)

> **Zurückgebaut durch Schritt 26** (Wunsch des Nutzers, 25.10.2026) – siehe „Rückbau der Set-Funktion“. Der Abschnitt
> bleibt als Geschichte stehen.

Grundlage: `planung/material-phase4/entwurf_l2.md` (Fassung 2 nach den Kritiken „Sicherheit“ S1–S31 und „Ablauf“
A1–A33, mit den Entscheidungen des Nutzers vom 23.10.2026: Hersteller-Sets, Set-Artikel mit Teil-Artikeln, Teil
gesperrt → ganzes Set gesperrt, Austausch, Kern in L2). Gebaut in Paketen: **K1** (Schema 21, Katalog, Bestand,
Tests, Doku), **K2** (Sperr-Kaskade und Freigabe, Set prüfen mit Set-Protokoll, Teil tauschen, entnehmen, einsetzen und
löschen, Aussondern mit Wahl je Teil, Mails, Jahresbericht – ohne Schemaänderung), danach **OBERFLÄCHE** (`material.js`
nach den Schnittstellen K1 und K2 unten), drei Prüfungen, Nachbesserung. Schemaversion 21, keine neuen Abhängigkeiten.
Die Oberfläche für den Stand K1 steht unter „Oberfläche (O1)“, die für K2 (Set prüfen, Tauschen, Aussondern, Durchgang,
Meine PSA) unter „Oberfläche (O2)“; danach „Prüfung vor Auslieferung“ (die drei Prüfungen und die Nachbesserung) und
„Bitte bestätigen (zusammengeführt)“ am Ende dieses Abschnitts.

### Neu (K1)

- **Hersteller-Set im Katalog** (Entwurf A): Häkchen „Hersteller-Set“ am Produkt (`is_set`) und die **Stückliste**
  (`mat_product_component`): je Position Bezeichnung (eine Zeile, höchstens 120 Zeichen), Anzahl 1–20, „einzeln geführt“
  und „Austausch laut Hersteller“ (ja | nein | nicht belegt, Vorgabe „nicht belegt“). Einzeln geführt wird ein
  Bestandteil nur mit eigener Kennzeichnung und eigenem Katalogprodukt – dann ist das Produkt Pflicht und jedes Stück
  wird beim Anlegen eines Sets ein Teil-Artikel; nicht einzeln geführte Bestandteile (Tasche, Seilsatz, Prusiks) sind nur
  Text, ohne Produkt (so trifft ein Rückruf keinen Bestandteil ins Leere, A17). Grenzen: 30 Positionen, zusammen
  50 einzeln geführte Stück je Set. Kein Set im Set, kein Set-Produkt als Bestandteil, kein DEMO-Bestandteil in einem
  echten Set. Die Stückliste wird als Ganzes ersetzt (Journal „stueckliste“ am Produkt mit vorher/nachher).
  „Hersteller-Set“ umschalten nur, solange es keine Artikel gibt; ein Bestandteil wird kein Set; ausschalten nimmt die
  Stückliste mit. Ein Bestandteil-Produkt lässt sich nicht löschen (409 „Das Produkt ist Bestandteil von „…“ – erst aus
  der Stückliste nehmen.“, dahinter ON DELETE RESTRICT); ebenso ein Produkt, das in der Kopie eines angelegten Sets steht.
  „Variante anlegen“ übernimmt die Stückliste auf Wunsch (`stueckliste`: ja – Häkchen wie bei den Dokumenten).
- **Katalogdatei** (Format 1 und 2): `"set": true` und `"bestandteile"` (siehe „Katalogdatei (Format 2)“). Der Import löst
  die Verweise in einem zweiten Durchgang nach allen Produkten der Datei auf (uid, dann Hersteller + Modell +
  Artikelnummer – wie die Formulare an Produkten), ersetzt die Stückliste als Ganzes (Journal unter „Katalogimport (…)“)
  und meldet im Bericht `stuecklisten` (geändert/unverändert). Fehler des Produkts: „set“ umschalten bei vorhandenen
  Artikeln, ein Bestandteil, der Set werden soll, „set“: false mit Bestandteilen, Bestandteile ohne „set“ (seit Schritt 25
  die Bestandteil-Liste eines Produkts – Fehler nur noch an einem Produkt, das hier ein Set ist), ein
  unbekannter Bestandteil, Positionen außerhalb der Regeln. Eine Liste aus Texten (heutige Recherche-Manifeste) ist ein
  Hinweis und wird übergangen. Der Export schreibt beides; steht ein DEMO-Bestandteil (oder einer aus einer
  DEMO-Kategorie) in einem echten Set, lässt er „bestandteile“ dieses Sets ganz weg und nennt es im Bericht
  (`set_verstoesse`, `bericht.txt`). Format-Vorlage: `docs/material-katalog-set-vorlage.json` (DEMO, nur Platzhalter).
- **Set anlegen** (Entwurf C): `POST /api/material/artikel` mit einem Set-Produkt braucht `teile` – je einzeln geführter
  Position genau „anzahl“ Teile mit Seriennummer (leer → STR-Nummer), Herstell-, Kauf- und Erstgebrauchsdatum und Länge
  (falls die Kategorie des Teil-Produkts sie vorsieht). Das Produkt eines Teils kommt aus der Stückliste, nie aus der
  Anfrage; der Ordner ist der des Sets; jedes Teil durchläuft die Regeln eines neuen Artikels (Herstelldatum bei textil,
  STR-Form, Dubletten – auch fremde, dann wird alles zurückgerollt und protokolliert). Doppelte Seriennummern in der
  Anfrage: 400 vor jedem Schreiben. Eine Transaktion: Set-Artikel, Kopie der Stückliste (`mat_item_set_slot`), Teile
  (eigene Inventarnummer, QR, Etikett), Journal „set_angelegt“ am Set mit der Teileliste, „angelegt“ am Teil mit
  `{"set", "set_inventar"}`. Hinweise „STR-Nummer am Teil anbringen (Etikett oder Gravur): …“ in der Antwort.
- **Set-Werte** (Entwurf F): Set-Status = der schwerste aus Set-Artikel und aktuellen Teilen in der Rangfolge von
  `status.status()` (`status.SET_RANG`, Test gegen `status()`); Set-Fälligkeit = früheste nächste Prüfung,
  Set-Lebensende = frühestes Lebensende – je mit dem auslösenden Artikel (am Set-Artikel steht meist das Textil).
  Vollständigkeit laut Kopie der Stückliste (einzeln geführte Positionen).
- **Listen** (Entwurf C, A9, S30): Ordnerliste, „Fällige“ und Suche zeigen die **Set-Zeile** mit Set-Status,
  Set-Fälligkeit, Set-Lebensende und dem Block `set`; Teile stehen nicht einzeln in Ordnerliste und „Fällige“ (sie
  stehen auf der Set-Seite und in der Suche, dort mit `teil_von`). Filter (`status`) und Sortierung (`status`,
  `faellig`, Vorgabe der Fälligen) gehen nach den Set-Werten (`sets.gruppen_status_sql` – SQL und Python im Test
  gegeneinander); Seiten zählen die Set-Zeile einmal. Kopf: `sets` = {anzahl, teile} („n Einträge, davon m Sets mit k
  Teilen“). Zählungen in Baum, Übersicht, Bericht und Export bleiben je Artikel (Teile zählen mit, „davon n Sets“
  später, Entwurf K).
- **Weichen im Dienst** (Entwurf C, S9): Verschieben, Zuordnen, Sammelzuordnung, Produktwechsel, Aussondern und Löschen
  an einem Teil → 409 „… ist Teil des Sets … – … geht nur mit dem ganzen Set. Ein Teil verlässt das Set nur über „Teil
  entnehmen“.“ Ein Set verschieben oder zuordnen nimmt alle Teile mit (`sets.set_lage`, eine Anweisung; Journal je Teil
  mit `{"set": …}`); die Sammelzuordnung zählt die Teile gegen die Grenze von 500. Produktwechsel an einem Set und zu
  einem Set-Produkt: 409 (A7b). Ein Set löschen geht nur ganz und nur, solange weder Set-Artikel noch Teile Prüfungen,
  Mangelmeldungen, Durchgangszeilen oder einen Set-Prüflauf haben (Teile mit Journal „mit dem Set gelöscht“).
- **Lage, Sperre und Zuordnung nur gemeinsam** (S1): `sets.set_lage` ändert Set und Teile in EINER Anweisung;
  `sets.set_stimmig` prüft am Ende jeder Set-Transaktion (Set anlegen, verschieben, zuordnen, Systemordner nachziehen,
  Ordner löschen), dass Teile wie ihr Set liegen (folder_id, origin_folder_id, frei oder nicht, assigned_user_id) – sonst
  500 „Set und Teile liegen nicht mehr gleich … nichts gespeichert“ und Rollback. Beim Start prüft `sets.beim_start` alle
  Sets (nur Log „Sets nicht stimmig …“). Getestet mit Teil-Kennung kleiner als Set-Kennung (eingesetzter Altartikel)
  bei Ordner über die Gliederungsgrenze verschieben, Artikel verschieben, Ordner löschen und Konto löschen (Probe P-D).
- **Artikelansicht**: am Set-Artikel `ist_set` und der Block `set` (Teile mit Status, Fälligkeit, Lebensende, Sperre,
  offenem Mangel, Rückruf; Kopie der Stückliste mit vorhanden/fehlt; Vollständigkeit; Rückrufe an Teilen als Banner-Daten),
  am Teil `teil_von` (Set mit Set-Status und Position) – nur, soweit das Konto beide Zeilen sieht (artikel_filter auf
  Set und Teil, H/S17). „Löschen“ am Teil aus (K2), am Set nach der Regel oben.
- **Meine PSA** (Entwurf C, A11): Ein zugeordnetes Set ist eine Karte mit Set-Status und Set-Fälligkeit, seine Teile
  stehen darunter als Karten (`teile`, dieselben Schlüssel, `teil_eines_sets`: true); die Zahl in der Kopfleiste, „Meine
  PSA“ auf der Übersicht und der Filter „Zugeordnet an“ zählen je Set.
- **Steckbrief** der globalen Suche: nur der Schlüssel `teil_eines_sets` – ohne Inventarnummer und Produkt des Sets (H).
- **Bestandsimport** (Entwurf I): Eine Zeile mit Set-Produkt geht in die Nacharbeit („Hersteller-Set – bitte über
  „Artikel anlegen“ mit seinen Teilen anlegen; der Import legt keine Sets an.“); die Produktwahl der Nacharbeit nimmt kein
  Set-Produkt (400). `bestand.artikel_schreiben` legt ein Set-Produkt nur über `sets.set_anlegen` an (sonst 409).
- **DEMO** (`scripts/material_demo.py --demo`): Kategorie „DEMO Verbindungsmittel-Sets“ mit Formular, Set-Produkt
  „DEMO Verbindungsmittel-Set“ (Stückliste: zwei einzeln geführte DEMO HMS-Karabiner, DEMO-Tasche als Text) und im
  DEMO-Lager der Set-Artikel DEMO-SET-1 mit den Teilen DEMO-SET-K1 und DEMO-SET-K2 – auch zu einem vorhandenen
  Demo-Bestand, einmal. Alles Platzhalter, alles DEMO.

### Migration (Schritt 21, Schemaversion 21)

Rein additiv: `mat_product.is_set`; `mat_product_component`; am Artikel `parent_item_id` (Index), `lock_cause` (NULL |
eigen | set), `set_lock_origin` (an der Set-Zeile: set | teil), `set_pruefen` (am Teil 0/1); `mat_item_set_slot`;
`mat_set_lauf` (AUTOINCREMENT, höchstens ein offener je Set); `mat_inspection.set_lauf_id` (Index);
`mat_set_protokoll_zeile`. Trigger nur für Übergänge einer Zeile: Teil nur über NULL und nur nach den Regeln (Set-Artikel
ohne eigenes Set, Teil-Produkt kein Set und einzeln geführt in der Kopie der Stückliste, beide nicht ausgesondert);
Produkt fest an Teilen, an Sets mit Teilen und von/zu Set-Produkten; „Hersteller-Set“ umschalten; Stückliste nur an
Sets und ohne Sets; Kopie der Stückliste unveränderlich (auch gegen REPLACE), weg nur mit dem Set; Set-Prüflauf (offen
anlegen, Kopf fest, beendet fest, nicht löschbar mit Prüfungen); Prüfungen nur in einen offenen Lauf ihres Sets;
Teiletabelle wie `mat_inspection_result`. **Keine** Kreuzzeilen-Trigger auf folder_id, origin_folder_id, lock_state,
assigned_user_id (S1, A8 – der Test sucht danach). `mat_inspection_festgeschrieben` und `mat_inspection_abgeschlossen`
(Schritt 6) werden mit `set_lauf_id` in der Spaltenliste neu angelegt (erst entfernen, dann anlegen, S4). Kein Umbau,
keine neuen Werte in vorhandenen CHECK-Listen (S6). `models.SPALTEN_21`/`TABELLEN_21`; die Testhilfe `bis_schritt`
rüstet sie für Stände unter 21 nach (S26).

Geprüft: frisch; 20 → 21 mit Bestand (Spalten mit Vorgaben, keine Zeile anders, Fremdschlüssel und integrity_check
sauber, Schema gleich dem frischen, zweiter Lauf und Schritt 21 für sich ändern nichts); an **Kopien** vorhandener
Probedatenbanken (Stand 19 mit 12 und 533 Artikeln, Stand 17, Stand 13 – Quellen nur lesend über die Backup-Schnittstelle
kopiert): je → 21, Fremdschlüssel 0, integrity ok, Zahlen und übrige Tabellen gleich, keine neuen Felder gesetzt,
Set-Objekte im Schema wie frisch, zweiter Start ändert nichts.

**Rückweg auf Code-Stand 20 mit Schema 21** (S27): Der alte Code migriert nicht zurück (Stand 21 ≥ 20) und kennt die
Spalten nicht. Solange es keine Sets gibt, läuft er unverändert. Mit Sets: Er zeigt Teile als eigene Artikel, verschiebt,
ordnet zu und sperrt sie einzeln (die Gleichheit von Set und Teilen geht verloren – die Startprüfung meldet es, sobald
wieder Code 21 läuft); „Set löschen“ endet im Fremdschlüsselfehler (409 „anderswo geändert“), Produktwechsel an Teilen
weisen die Trigger ab. Deshalb: zurück nur, solange keine Sets angelegt sind, oder die Sets vorher löschen.
Kommt nach so einem Rückweg wieder Code 21, behandelt die nächste Set-Sperre ein Teil, das der alte Code einzeln gesperrt
hat (gesperrt ohne `lock_cause`), als „eigen“ mit seinem Grund und nimmt es in den Prüfumfang der Freigabe – es wird nie
mit „set“ überschrieben (Nachbesserung, Sicherheit 6; Test `test_konto_loeschen_und_rueckweg`). Trotzdem zuerst die im
Startlog „Sets nicht stimmig“ genannten Sets ansehen.

**Nachbesserung vor der Auslieferung**: Schritt 21 ist noch nicht ausgeliefert (weder dev noch Produktion); der Trigger
`mat_set_lauf_kopf` wurde darin geändert statt in einem Schritt 22: Am **offenen** Lauf darf `round_id` auf NULL gehen
(Durchgang abgebrochen) und `opened_by_name` „(gelöschtes Konto)“ werden (Kontolöschen); sonst bleibt der Kopf fest, am
beendeten Lauf ganz. `_schritt_21` entfernt ihn vorher und legt ihn neu an (wie die beiden Fest-Trigger aus Schritt 6).
Eine Probedatenbank, die schon mit der Fassung vor der Nachbesserung auf 21 steht, behält den alten Trigger – neu anlegen
(betrifft nur Bau- und Prüfdaten). Geprüft: frisch, 20 → 21 und die Testhilfe `bis_schritt` (Suite).

### Abweichungen vom Entwurf und Entscheidungen des Baus (mit Begründung)

1. **Ursprung der Set-Sperre als zwei Spalten**: `set_lock_origin` an der Set-Zeile (set | teil) und `set_pruefen` am
   Teil. Der Prüfumfang der Freigabe („Set-Artikel + jedes Teil, das seit Beginn der Sperre neu eingesetzt wurde oder eine
   eigene Sperre hatte; vom Set-Artikel aus: alle“) ist eine Angabe je Teil – ein Teil hat nach seiner Freiprüfung wieder
   `lock_cause` „set“ und muss trotzdem in den Lauf. Gespeichert statt aus dem Journal erraten (wie im Entwurf erwogen).
2. **Sperren an Set-Artikel und Teil bis K2: 409.** Prüfer-Sperre, Ergebnis „instandsetzen“/„aussondern“, Mangelmeldung
   und Aussonderung an einem Set-Artikel oder Teil antworten bis zur Sperr-Kaskade 409 („Sperren und Aussondern im Set
   kommen mit der Set-Sperre …“) – die vorhandenen Einzelwege sperrten nur eine Zeile und rissen das Set auseinander.
   Eine Prüfung mit „einsatzbereit“ geht (sie ändert nur die Zeile selbst). Das gilt nur zwischen K1 und K2; ausgeliefert
   wird L2 erst mit K2.
3. **Teil einzeln löschen erst mit K2** (Entwurf C erlaubt es ohne Prüfung, Mangel und Durchgangszeile – dann sperrt es das
   Set „unvollständig“, also Kaskade). Ein ungeprüftes Set ganz löschen geht schon.
4. **Set anlegen über `POST /artikel`** (kein eigener Endpunkt): Recht, `FELDER_IM_INHALT` und das Protokoll fremder
   Dubletten bleiben, wie sie sind. Die neuen Kennungen im Inhalt (`teile[].bestandteil_id`, `bestandteile[].produkt_id`)
   sind Katalogkennungen (global) – keine Bestandsangabe, daher keine neue Zeile in `FELDER_IM_INHALT`; eine fremde
   Position antwortet 400.
5. **Felder eines Teils beim Anlegen**: genau die aus Entwurf C (Seriennummer, Herstell-, Kauf-, Erstgebrauchsdatum,
   Länge). Intervall, nächste Prüfung und Lebensende bekommt ein Teil wie jeder neue Artikel aus Produkt und Ordner;
   Bemerkung keine.
6. **Zwei Positionen mit demselben Produkt** (Kong: zwei Verbindungselemente an verschiedenen Stellen): Teile kennen ihre
   Position nicht – sie werden den Positionen in deren Reihenfolge zugeteilt (Anzeige „bestandteil“, vorhanden/fehlt).
7. **„Hersteller-Set“ ausschalten nimmt die Stückliste mit** (Journal) statt 409 – es gibt dann ohnehin keine Artikel.
8. **Katalogdatei**: `set`/`bestandteile` auch in Format 1 gelesen (wie `artikel_laenge`). DEMO-Bestandteil in einem
   echten Set: Der Export lässt `bestandteile` dieses Sets ganz weg (nicht nur die Position) – die Produktion behält
   ihre Stückliste, statt eine verkürzte zu übernehmen.
9. **Meine PSA**: Die Set-Karte trägt ihre Teile als Karten (`teile`) – Entwurf C „Set-Karte mit Teilen“; der Schlüssel
   `teil_eines_sets` wie in Entwurf H. Der Filter „Zugeordnet an“ zählt je Set (die Listen zeigen nur die Set-Zeile).
10. **Fehler „Set nicht stimmig“ als 500**: Es ist ein Fehler im Dienst, kein Eingabefehler; Log mit dem Set.
11. **Vorlage**: eine eigene Datei `docs/material-katalog-set-vorlage.json` (DEMO-Kennzeichen, Platzhalter) statt eines
    Beispielprodukts in `docs/material-katalog-vorlage.json` – die trägt echte Normen und kann importiert werden.

### Schnittstelle (Stand K1 – für die Oberfläche)

Alle Antworten wie bisher (`error` mit Klartext, 404 für Fremdes wie für Unbekanntes). Neu bzw. geändert:

| Methode und Pfad | Recht | Anfrage → Antwort |
| --- | --- | --- |
| `POST /api/material/produkte`, `PUT …/<pid>` | Katalog | neu `is_set` (ja/nein). PUT mit `is_set`: umschalten (409 mit Artikeln oder wenn das Produkt Bestandteil ist; aus nimmt die Stückliste mit) |
| `PUT /api/material/produkte/<pid>/bestandteile` | Katalog | `{"bestandteile": [{"produkt_id": Kennung \| null, "bezeichnung": Text, "anzahl": 1–20, "einzeln": ja/nein, "austausch": "ja" \| "nein" \| "nicht_belegt"}]}` – Reihenfolge = Position, ersetzt als Ganzes, leer entfernt alle → `{"produkt": (voll), "geaendert": bool}`. 409 kein Set; 400 Regeln/Grenzen (Text „Position n: …“); 404 unbekanntes Produkt. `bezeichnung` darf bei einzeln geführten fehlen (dann der Produktname) |
| `POST /api/material/produkte/<pid>/variante` | Katalog | neu `stueckliste` (ja: Stückliste übernehmen, die Variante wird Set; 400, wenn die Quelle keins ist) |
| `DELETE /api/material/produkte/<pid>` | Katalog | 409, wenn Bestandteil einer Stückliste oder in der Kopie eines angelegten Sets |
| `GET /api/material/produkte`, `…/<pid>` | lesen | je Produkt `is_set`; voll dazu `bestandteile` (Liste wie unten), `bestandteil_von` [{id, name}], `set_umschaltbar`, `set_umschalt_grund` (Text oder null), `stueckliste_grenzen` {positionen 30, anzahl 20, teile 50, bezeichnung 120}; `loeschbar` false auch für Bestandteile |
| Position der Stückliste | – | `{id, position, bezeichnung, anzahl, einzeln, austausch, austausch_text, produkt: {id, name, manufacturer, model, description, article_no, material_kind, lifetime_years, laenge_moeglich, demo} \| null}` |
| `GET /api/material/artikel/vorschlag?product_id=` | wie bisher | neu `set`: null oder `{bestandteile: [Position …], teil_felder: ["serial_no", "manufactured_on", "purchased_on", "first_use_on", "length_m"], hilfe_einzeln}` |
| `POST /api/material/artikel` | Materialwart | mit Set-Produkt: dazu `teile: [{"bestandteil_id": Position.id, "serial_no", "manufactured_on", "purchased_on", "first_use_on", "length_m"}]` – je einzeln geführter Position genau `anzahl`. 400: ohne `teile`, falsche Zahl, fremde Position, doppelte Seriennummer, Regel eines Teils („Teil „…“: …“); 409 ohne Stückliste, sichtbare Dublette; fremde Dublette wie bisher. `teile` an einem anderen Produkt: 400. Antwort neu `hinweise: [Text]` (STR-Nummer anbringen; sonst leer) |
| `GET /api/material/artikel/<iid>` (und jede Antwort mit `artikel`) | lesen | neu `ist_set`, `set` (null oder Set-Block, unten), `teil_von` (null oder `{id, inventory_no, produkt, status, status_text, bestandteil}`); `darf_loeschen` an Teilen false (seit K2: ungeprüftes Teil true), an Sets nach der Löschregel |
| Set-Block `set` | – | `status`, `status_text`, `next_due_on`, `faellig_durch` {id, inventory_no, set_artikel}, `retire_by`, `lebensende_durch`, `eigen` {status, status_text, next_due_on, retire_by}, `teile` [{id, inventory_no, serial_no, serial_generated, produkt {id, name, manufacturer, model, description, article_no, material_kind, vorschau}, bestandteil, status, status_text, next_due_on, retire_by, last_inspected_on, lock_state, lock_cause, lock_reason, length_m, laenge_text, mangel, rueckruf}], `teile_anzahl`, `bestandteile` [Position der Kopie: position, bezeichnung, anzahl, einzeln, austausch, austausch_text, produkt; einzeln dazu `vorhanden`, `fehlt`], `vollstaendig`, `fehlend` [{bezeichnung, fehlt}], `rueckrufe_teile` [{teil {id, inventory_no}, titel}], `ursprung` (set_lock_origin), `sperrgruende` (K2; bis dahin []) |
| `GET /api/material/ordner/<fid>`, `GET /api/material/faellig`, `GET /api/material/suche` | wie bisher | Listenzeilen neu `ist_set`, `set` (null oder `{teile, eigen, faellig_durch, lebensende_durch, mangel_teile [Inventarnummern], rueckruf_teile [{inventory_no, titel}], vollstaendig}`), `teil_von` (null oder `{id, inventory_no, produkt}`); an Set-Zeilen `status`, `status_text`, `next_due_on`, `retire_by` = Set-Werte. Ordner und Fällige ohne Teile; `ordner.sets` bzw. `sets` = {anzahl, teile}. Filter `status` und Sortierung `status`/`faellig` nach Set-Werten |
| `POST /api/material/artikel/verschieben`, `PUT …/<iid>/zuordnung`, `POST /api/material/artikel/zuordnen` | wie bisher | Teil → 409; Set nimmt die Teile mit; `geaendert` der Sammelzuordnung zählt die geänderten Zeilen (Set mit Teilen) |
| `PUT /api/material/artikel/<iid>` | Materialwart | Produktwechsel an Teil, Set oder zu einem Set-Produkt: 409 |
| `DELETE /api/material/artikel/<iid>` | Materialwart | Teil 409 (seit K2: ungeprüftes Teil gelöscht, Set gesperrt); Set ganz (Regel oben), sonst 409 |
| `POST …/sperren`, `…/aussondern`, `POST /api/material/artikel/<iid>/mangel`, `POST /api/material/pruefungen/<pid>/festschreiben` mit sperrendem Ergebnis | wie bisher | an Set-Artikel und Teil bis K2: 409 – seit K2 über das ganze Set (Schnittstelle K2) |
| `GET /api/material/meine-psa` | PSA-Konto | Karten neu `teile` (Set: Teil-Karten mit denselben Schlüsseln; sonst []) und `teil_eines_sets`; Set-Karte mit Set-Status und Set-Fälligkeit; `gesamt` zählt je Set |
| `POST /api/material/globalsuche`, `…/qr` | Modulzugang | Steckbrief neu `teil_eines_sets` (17 Schlüssel) |
| `POST /api/material/katalog/import` | Katalog | Bericht neu `stuecklisten` {geaendert, unveraendert}; `GET …/katalog/export/vorschau` neu `export.set_verstoesse` |

Journal neu: Aktion „stueckliste“ (Produkt), „set_angelegt“ (Artikel), Felder `is_set`, `bestandteile`, `teile`, `set`,
`set_inventar`, `stueckliste` – Beschriftungen in `services/beschriftung.py` und gleichlautend in `material.js` (FELD,
AKTION – der statische Abgleich in `test_material_l5` verlangt beide gleich; die einzige Änderung an `material.js` in K1).

### Nahtstellen für K2 (mit K2 erledigt – siehe „Neu (K2)“; `sets.vor_einzelsperre` gibt es nicht mehr)

- `sets.vor_einzelsperre(item)` – heute 409; K2 hängt hier die Kaskade ein (aufgerufen aus `pruefung._sperren` und
  `pruefung._aussondern`, damit auch aus Mangelmeldung, Prüfer-Sperre und Ergebnis „instandsetzen“/„aussondern“): eigene
  Sperre am Artikel (`lock_cause` „eigen“), alle anderen per `sets.set_lage(…, je_zeile={"lock_cause": …, "lock_reason":
  …, "lock_state": …, "set_pruefen": …, "set_lock_origin": …})` mitgesperrt, `set_stimmig`.
- `sets.set_lage` (EINE Anweisung über Set und Teile, `je_zeile` für Sperrursache, Grund, Zustand, Prüfpflicht und
  Ursprung) und `sets.set_stimmig`/`sets_stimmig`/`betroffene_sets` am Ende jeder Set-Transaktion.
- Freigabe: `mat_set_lauf` (offen/abgeschlossen/abgebrochen, `round_id`, `set_inspection_id`), `mat_inspection.set_lauf_id`,
  `mat_set_protokoll_zeile` (Kopie beim Festschreiben, Trigger stehen), Prüfumfang aus `set_lock_origin` + `set_pruefen`.
- `sets.werte`, `sets.vollstaendigkeit`, `sets.slots`, `sets._zuteilen` (Positionen der Teile) für Freigabe-Bedingungen
  und Set-Protokoll; `set_json["sperrgruende"]` ist für die abgeleiteten Sperrgründe vorgesehen.
- `sets.teil_weiche` (Aussondern/Löschen am Teil) – K2 ersetzt die Wege durch „Teil entnehmen“ (bedingtes UPDATE
  `… WHERE id = ? AND parent_item_id = ?`, Trigger erlauben nur Set → NULL) und „Teil tauschen“ (entnehmen + neues Teil:
  `bestand.artikel_schreiben(plan, parent_id=…)`; der Trigger verlangt Produkt laut Kopie der Stückliste).
- `sets.darf_loeschen`/`set_loeschen` (Set ganz) – K2 ergänzt „Teil löschen“ (sperrt „unvollständig“).
- Lebenslauf, Protokoll-PDF, Sammelprotokoll, Mails und Jahresbericht sind in K1 unverändert.

### Tests

`tests/test_material_sets.py` (neu, 12 Tests): Migration 20 → 21, Trigger aus Schritt 21, Stückliste im Katalog,
Katalogdatei Format 2 hin und zurück (mit Vorlage), Set anlegen, Rangfolge SET_RANG gegen `status()`, Listen und
Set-Status (SQL gegen Python), Routentabelle Set/Teil/frei, set_stimmig mit Teil vor Set (Ordner verschieben, Artikel
verschieben, Ordner löschen, Konto löschen, Rollback, Startlog), Trennung je Gliederung, Meine PSA und Bestandsimport,
DEMO-Set. Angepasst: `test_material_trennung.bis_schritt` (Nachrüsten für Stände unter 21), die Schlüsselmengen von
PSA-Karte und Steckbrief (`test_material_meine_psa`, `test_material_globalsuche`, `test_material_trennung`), feste
Endversionen und Triggerlisten in den Migrationstests (`test_material_laenge` – dort vergleicht der Rückbau auf Stand 19
die Spalten von `mat_item` statt ihres Textes, weil `length_m` danach hinter den Spalten aus Schritt 21 steht –,
`test_material_mailprotokoll`, `test_material_antrag`), die Zahl der DEMO-Produkte in `test_material_beschreibung`.

### Neu (K2 – Sperren, Set prüfen, Austausch)

- **Sperr-Kaskade** (Entwurf D, `sets.sperren`): Jede eigene Sperre an Set-Artikel oder Teil – Prüfer-Sperre (Sturz,
  Beschädigung, Verlust, Rückruf), Ergebnis „instandsetzen“, Mangelmeldung – setzt dort `lock_cause` „eigen“ und sperrt
  das ganze Set in EINER Anweisung (`sets.set_lage`): alle nach „Gesperrt“ der Gliederung, Herkunft = Heimat des Sets,
  alle anderen „set“. Am Set-Artikel steht der Ursprung (`set_lock_origin`: „set“, wenn er selbst den Grund hat, sonst
  „teil“), am Teil mit eigenem Grund `set_pruefen`. Verlust am Set-Artikel: alle verloren; an einem Teil: nur dieses.
  Eine eigene Sperre geht auch an einem schon mitgesperrten Teil (Prüfer-Sperre 200, Mangelmeldung, „instandsetzen“);
  eine zweite eigene nicht („schon gesperrt“, 409). Journal: am Anlass die Aktion mit dem Handelnden („gesperrt“,
  „mangel_gemeldet“ mit `{"mangel": …}`), an allen anderen „set_gesperrt“ mit dem Handelnden **„System“**, am
  Set-Artikel dazu „teil_gesperrt“ – so steht an Set und übrigen Teilen nie ein Meldername (S24).
- **Unvollständig und getauscht sperrt** (A25/A26): Teil entnehmen, Teil löschen und Ergebnis „aussondern“ an einem
  Teil sperren das Set („unvollständig: „…“ entnommen/gelöscht/ausgesondert“), Teil tauschen und einsetzen sperren es
  („Teil getauscht – Set prüfen“ bzw. „Teil eingesetzt – Set prüfen“); Ursache am Set-Artikel „set“, Journal mit
  `set_grund` („unvollstaendig“ | „tausch“).
- **Freiprüfung im gesperrten Set** (S8, A12): „einsatzbereit“ an einem Teil setzt nur „eigen“ → „set“ (verloren →
  gesperrt), erledigt Mängel und setzt die Fälligkeit; Lage und Sperre bleiben (Journal „geprueft“, nicht
  „freigeprueft“). „instandsetzen“ an einem Teil eines freien Sets sperrt das ganze Set. Eine nur geerbte Sperre zählt in
  Prüfart-Vorschlag und Berichtigung wie frei (A23).
- **Set prüfen** (Entwurf E, `services/setlauf.py`): „Set prüfen“ eröffnet einen Lauf (`mat_set_lauf`, höchstens einer je
  Set – ein zweiter Aufruf liefert den offenen); offene Entwürfe an Set und Teilen (keine Berichtigungen) zählen ab dann
  darin, jede neue Prüfung an ihnen ebenso (`set_lauf_id`). Den Set-Artikel prüft man **nur** im Lauf (sonst 409) – mit
  dem Formular seines Produkts, ergänzt um je eine Pflicht-Zeile „… vorhanden“ (Ja/Nein, Gruppe „Bestandteile des Sets“)
  je nicht einzeln geführtem Bestandteil. Jedes Teil hat seine eigene Prüfung mit eigenem P-Protokoll; das Protokoll eines
  Teils nennt „Teil von Set <Inventarnummer> – <Produkt>, SN …“ als Kopie (A24). Teilprüfungen außerhalb eines Laufs
  bleiben möglich (sie wirken über die Kaskade).
- **Prüfumfang** (Entscheidung „Set-Artikel + betroffene Teile“): freies Set (periodisch) – alle Teile; gesperrtes Set –
  ging die Sperre vom Set-Artikel aus, alle Teile, sonst die Teile mit `set_pruefen` (seit Beginn der Sperre neu
  eingesetzt oder mit eigenem Grund). Die übrigen stehen im Set-Protokoll als „übernommen“ mit Protokoll-ID und Prüfsumme
  ihrer letzten gültigen Prüfung (abgeschlossen, keine Aussonderung, nicht berichtigt). Weitere Teile darf man im Lauf
  prüfen („auch prüfen“) – dann zählt diese Prüfung. Die Prüfung des Set-Artikels lässt sich erst festschreiben, wenn
  jedes Teil im Umfang im Lauf geprüft und kein anderer Entwurf im Lauf offen ist (409 mit den Inventarnummern).
- **Freigabe – genau ein Übergang** (S10, A20): beim Festschreiben der Set-Artikel-Prüfung eines Laufs mit
  „einsatzbereit“, in derselben BEGIN-IMMEDIATE-Transaktion frisch gelesen (`setlauf.freigabe_gruende`): kein Artikel des
  Sets mit eigener Sperre, verloren, mit offener oder wieder offener Meldung, offenem Entwurf, Status „neu“, „überfällig“
  oder „Lebensdauer erreicht“ (Status ohne die Sperre gerechnet); vollständig laut Kopie der Stückliste; jedes Teil im
  Umfang im Lauf „einsatzbereit“, jedes übrige mit gültiger Prüfung „einsatzbereit“; eine Ausnahme zählt nie als geprüft.
  Dann EIN UPDATE über Set und Teile auf frei (`sets.freigeben`), zurück in die Heimat des Sets (Rückweg wie die
  Freiprüfung); Journal am Set-Artikel „freigeprueft“, an den Teilen „set_frei“ (System). Sonst bleibt das Set gesperrt
  und das Protokoll nennt die Gründe. **Eine Berichtigung gibt nie frei** (auch nicht die der Set-Prüfung).
- **Gesamtergebnis und Set-Protokoll** (S7, S19): Das Set-Protokoll ist das P-Protokoll der Set-Artikel-Prüfung – keine
  neue Protokollart, keine neue Ablage. Es trägt den Abschnitt „Set-Prüfung“ mit dem Gesamtergebnis („einsatzbereit“ |
  „nicht einsatzbereit – Set gesperrt“ | „Set ausgesondert“ – wie das Set danach steht), den Gründen, einem Hinweis bei
  mehr als 7 Tagen zwischen erster Teilprüfung und Abschluss (Prüftag = Tag des Abschlusses) und der Teiletabelle
  (`mat_set_protokoll_zeile`, Kopie vor dem Abschluss, durch die Trigger aus Schritt 21 unveränderlich): je Teil
  Bezeichnung der Position, Nummern, Ergebnis, Protokoll-ID und SHA-256 der Protokolldatei (oder „übernommen“), je
  fehlender Position „fehlt“, je Bestandteil „vorhanden“/„fehlt“, je im Lauf entnommenem Teil seine Prüfung. Das Journal
  am Set-Artikel bekommt „set_geprueft“ (`lauf`, `pruefung`, `gesamtergebnis`, `freigegeben`, `gruende`, `hinweis`). Die
  Berichtigung der Set-Prüfung übernimmt die Teiletabelle des Originals; Berichtigungen von Teilprüfungen danach nennt
  der Set-Block (`letzte_pruefung.berichtigte_teile`), das Protokoll bleibt.
- **Lauf abbrechen**: offene Teil-Entwürfe laufen als Einzelprüfungen weiter, festgeschriebene bleiben Einzelprüfungen mit
  Protokoll; ein Lauf ohne Prüfung verschwindet; ein offener Entwurf am Set-Artikel muss vorher weg (409). Abbrechen darf,
  wer prüft oder verwaltet.
- **Im Ordner-Durchgang** (A19, S18): Set und Teile bleiben eigene Durchgangszeilen; „Set prüfen“ von dort
  (`durchgang_id`) setzt `round_id` am Lauf (der Set-Artikel muss im Durchgang offen sein), die Prüfungen zählen in Lauf
  und Durchgang. Ein offener Lauf hält die Eröffnung eines Durchgangs nicht auf. Durchgangszeilen tragen `set_lauf` (Set)
  bzw. `teil_von` (Teil) zum Gruppieren. Das **Sammelprotokoll** stellt die Teile eingerückt unter ihr Set („Teil von Set
  …“), an der Set-Zeile „Set-Prüfung: <Gesamtergebnis>“ einer im Durchgang abgeschlossenen Set-Prüfung.
- **Aussondern** (Entscheidung „je Teil wählbar“, `services/setaustausch.py`): „Set aussondern“ über die vorhandene Route
  am Set-Artikel (Materialwart, Vorbedingungen von `pruefung.aussondern` am Set-Artikel; dazu mindestens ein eigener
  Grund im Set oder verloren und keine ungeprüfte Meldung an Set oder Teil) und Ergebnis „aussondern“ am Set-Artikel:
  je Teil `verbleib` „aussondern“ (mit aussondern) oder „weiterfuehren“ (entnehmen und gesperrt weiterführen). Vorbelegung:
  eigene Sperre durch einen Prüfer oder verloren → mit aussondern, sonst weiterführen (`set.teile[].verbleib_vorschlag`).
  Ein nur mitgesperrtes Teil darf mit ausgesondert werden. Mit ausgesonderte Teile bleiben am Set (Lebenslauf), jedes mit
  eigenem Aussonderungsprotokoll („mit dem Set … ausgesondert: …“; aus einer Prüfung mit ihr als Grundlage);
  weitergeführte verlassen das Set gesperrt mit eigenem Grund „aus ausgesondertem Set entnommen“, Herkunft die Heimat des
  Sets, ohne Zuordnung, bis zur Freiprüfung. Ergebnis „aussondern“ an einem Teil: das Teil verlässt das Set und ist
  ausgesondert, das Set unvollständig gesperrt. Aussondern am Teil durch den Materialwart nur über „Teil entnehmen“.
- **Teil entnehmen** (Entwurf G): Verbleib „weiterfuehren“ – aus einem gesperrten Set mit eigener Sperre „aus gesperrtem
  Set entnommen“ (eine eigene Sperre behält ihren Grund), aus einem freien frei im Ordner des Sets – oder „aussondern“ nur
  mit eigener Sperre durch einen Prüfer oder verloren, ohne ungeprüfte Meldung und mit den Datumsgrenzen von
  `pruefung.aussondern` (neu als `pruefung.aussondern_grenzen`). Bedingtes UPDATE `… WHERE id = ? AND parent_item_id = ?`
  mit Zeilenzahl-Prüfung; offener Entwurf am Teil → 409; seine Durchgangszeile bleibt; das Teil verliert die Zuordnung
  (Journal „zuordnung_geloest“, Grund „aus dem Set entnommen“).
- **Teil tauschen / Teil einsetzen**: tauschen = altes Teil entnehmen (Verbleib wie oben) + neues Teil anlegen; einsetzen =
  neues Teil an einer Position, an der eines fehlt. Produkt laut Kopie der Stückliste, Daten wie beim Set anlegen,
  angelegt in der Heimat des Sets und dann mit Lage, Sperre und Zuordnung des Sets (Journal „zugeordnet“, Grund
  „Zuordnung des Sets“); es ist im Freigabe-Lauf zu prüfen. „Austausch laut Hersteller“ der Position: „nein“ → 409 (nur
  Set aussondern), „nicht belegt“ → Pflichtbestätigung `bestaetigt` („laut Herstellerunterlagen zulässig“, Journal am
  Set), „ja“ ohne. STR-Hinweis wie beim Anlegen.
- **Teil löschen**: ein Teil ohne Prüfung, Mangelmeldung und Durchgangszeile über die vorhandene Lösch-Route; das Set ist
  danach unvollständig und gesperrt (Journal am Teil „geloescht“ mit Set, am Set „teil_geloescht“). `darf_loeschen` am
  Teil folgt dieser Regel.
- **Lebenslauf des Sets** (S15): nur Einträge am Set selbst – die Dienste schreiben dort „teil_gesperrt“,
  „teil_entnommen“, „teil_eingesetzt“, „teil_geloescht“, „set_lauf_eroeffnet“, „set_lauf_abgebrochen“, „set_geprueft“,
  „set_gesperrt“; Teil-Journale werden nie per Kennung nachgeladen. Beschriftungen in `beschriftung.py` (FELD, AKTION,
  Werte `SET_WERTE`) und gleichlautend in `material.js` (FELD, AKTION).
- **Jahresbericht** (A13, S13): Eine Set-Sperre zählt einmal – am Anlass; „set_gesperrt“ zählt nicht. Neue Sperrart
  „set“ („Set unvollständig oder Teil getauscht“) für Sperren aus Unvollständigkeit oder Tausch. Wieder freigegeben zählt
  die Set-Freigabe einmal („freigeprueft“ am Set-Artikel; „set_frei“ und Freiprüfungen im gesperrten Set zählen nicht).
  `pruefung.sperrtag` sieht „set_gesperrt“ (Übergang frei → gesperrt) – ein mitgesperrtes Teil hat seinen Sperrtag.
- **Mails** (S25, keine neue Mailart, nur über `mailprotokoll.senden`): Die Mangel-Mails an Materialwarte und Prüfer und
  an die zugeordnete Person sagen bei Set-Artikel und Teil, dass das ganze Set mit allen n Teilen gesperrt ist („nicht
  verwenden“, Betreff „… – Set M-… mit allen Teilen gesperrt“ bzw. „Deine PSA … (Set M-…) ist mit dem ganzen Set
  gesperrt – nicht verwenden“). Die Rückruf-Mail und die Liste der betroffenen Artikel nennen bei Teilen „Teil von Set
  M-…“ (`set_inventar`, A17).
- **Set-Block** am Set-Artikel (`artikel.set`) neu: `sperrgruende` (abgeleitet), `lauf` (offene Set-Prüfung kurz),
  `letzte_pruefung`, je Teil `slot_id`, `austausch`, `set_pruefen`, `verbleib_vorschlag`, je Position der Kopie `id`.

### Schnittstelle (Stand K2 – für die Oberfläche)

Zusätzlich zu K1. Alle Antworten wie bisher (`error` mit Klartext; Fremdes antwortet 404 wie Unbekanntes – auch eine
`teil_id`, die nicht zu diesem Set gehört, als Zahl, „7“ oder 7.0).

| Methode und Pfad | Recht | Anfrage → Antwort |
| --- | --- | --- |
| `GET /api/material/artikel/<iid>/set-lauf[?lauf=<id>]` | lesen | → `{lauf: Lauf (voll) \| null, laeufe: [Lauf (kurz)], neueste zuerst}`; ohne `lauf` die offene Set-Prüfung; `lauf` eines anderen Sets → 404; ein Artikel, der kein Set ist → `{lauf: null, laeufe: []}` |
| `POST /api/material/artikel/<iid>/set-lauf` | Prüfer (prüfen + Urkunde) | `{"durchgang_id": Kennung \| null}` → 201 neu bzw. 200 der offene: `{artikel (Set voll), lauf (voll)}`. 409: kein Set-Artikel, ausgesondert, offener Lauf in einem anderen/ohne Durchgang; Durchgang fremd/unbekannt/Set nicht darin → 404, Set dort schon geprüft/ausgenommen → 409; ohne Urkunde 403 |
| `DELETE /api/material/artikel/<iid>/set-lauf` | prüfen oder verwalten | → `{artikel, bleibt}` (`false`: der Lauf hatte keine Prüfung und ist weg); 409 ohne offenen Lauf und bei offenem Entwurf am Set-Artikel |
| `POST /api/material/artikel/<iid>/pruefungen` | Prüfer (wie bisher) | am Set-Artikel nur mit offenem Lauf (409 „über „Set prüfen““); an Set und Teil mit offenem Lauf → die Prüfung zählt darin |
| `GET /api/material/pruefungen/<pid>` und jede Antwort mit `pruefung` | lesen | neu `set_lauf` (Lauf kurz + `rolle` „set“ \| „teil“ + `set` {id, inventory_no}) \| null; am offenen Entwurf des Set-Artikels `set_abschluss` (Lauf voll + `verbleib_vorschlag` [{teil_id, inventory_no, verbleib}]) \| null; an der abgeschlossenen Set-Prüfung `set_protokoll` {zeilen, gesamt, gesamt_text, freigegeben, gruende, hinweis, berichtigung} \| null; `freipruefung` false bei nur geerbter Sperre. Punkte der Gruppe „Bestandteile des Sets“ (yesno, Soll „ja“, Pflicht, nicht kritisch) am Set-Artikel |
| `POST /api/material/pruefungen/<pid>/festschreiben` | Prüfer (wie bisher) | am Set-Artikel (Lauf): 409 „In der Set-Prüfung noch nicht geprüft: …“, „… noch eine Prüfung offen: …“; neu `verbleib: [{"teil_id", "verbleib": "aussondern" \| "weiterfuehren"}]` bei `ergebnis: "aussondern"` (fehlende Teile: Vorbelegung; fremdes Teil 404). An Teilen: Wirkung über das Set (siehe oben) |
| `POST /api/material/pruefungen/<pid>/berichtigen` | Prüfer (wie bisher) | an einem Teil mit nur geerbter Sperre möglich; zählt im noch offenen Lauf des Originals; an der Set-Prüfung mit deren Teiletabelle |
| `POST /api/material/artikel/<iid>/sperren` | Prüfer (wie bisher) | an Set-Artikel und Teil: Kaskade (200); an einem mitgesperrten Teil 200; mit eigenem Grund 409 |
| `POST /api/material/artikel/<iid>/mangel` | wie bisher | an Set-Artikel und Teil: Kaskade (201) |
| `POST /api/material/artikel/<iid>/aussondern` | Materialwart (wie bisher) | am Set-Artikel „Set aussondern“, neu `verbleib` wie oben → `{artikel, aussonderung}` (Aussonderung des Set-Artikels); 409 nur unvollständig/getauscht gesperrt, ungeprüfte Meldung an Set oder Teil („<Inventarnummer>: …“), offener Entwurf an Set oder Teil, Datum vor den Grenzen eines mit ausgesonderten Teils; am Teil 409 („Teil entnehmen“) |
| `DELETE /api/material/artikel/<iid>` | Materialwart (wie bisher) | Teil ohne Prüfung, Meldung und Durchgangszeile → gelöscht, Set gesperrt; sonst 409 wie jeder Artikel |
| `POST /api/material/artikel/<iid>/teil-entnehmen` | Materialwart | `{"teil_id", "verbleib": "weiterfuehren" (Vorgabe) \| "aussondern", bei „aussondern“ "grund" (lebensdauer \| verlust \| irreparabel), "bemerkung", "datum"}` → `{artikel (Set voll), teil (das entnommene, voll)}`; 404 Teil nicht im Set; 409 offener Entwurf, „aussondern“ ohne eigene Prüfer-Sperre, ungeprüfte Meldung, Datumsgrenzen; 403 ohne Unterschrift (nur „aussondern“) |
| `POST /api/material/artikel/<iid>/teil-tauschen` | Materialwart | `{"teil_id" (alt), "verbleib" … wie beim Entnehmen, "serial_no", "manufactured_on", "purchased_on", "first_use_on", "length_m", "bestaetigt"}` → 201 `{artikel, teil (neu, voll), hinweise}`; 409 Austausch „nein“, Teil ohne Position; 400 „nicht belegt“ ohne `bestaetigt`, Regeln des neuen Teils („Neues Teil „…“: …“); Dubletten wie beim Anlegen |
| `POST /api/material/artikel/<iid>/teil-einsetzen` | Materialwart | `{"slot_id" (Position der Kopie mit fehlendem Teil; bei genau einer darf es fehlen), Felder wie beim Tauschen, "bestaetigt"}` → 201 wie tauschen; 409 vollständig/Position voll, 404 Position unbekannt, 400 mehrere fehlen ohne `slot_id` |
| `GET /api/material/durchgaenge/<rid>` | lesen | Zeilen neu `set_lauf` (offene Set-Prüfung des Sets, kurz) \| null |
| `GET/POST /api/material/produkte/<pid>/rueckrufe`, `GET /api/material/rueckrufe/<ruid>` | wie bisher | betroffene Artikel neu `set_inventar` (Inventarnummer des Sets) \| null |
| `GET /api/material/ordner/<fid>/bericht` | wie bisher | `sperren.arten` neu Art „set“ |

**Lauf (kurz)**: `{id, state (offen | abgeschlossen | abgebrochen), round_id, durchgang ({id, titel, ordner, sichtbar}
| null), opened_at, opened_by_name, closed_at, set_inspection_id}`. **Lauf (voll)** dazu: `umfang` je Teil `{teil {id,
inventory_no, serial_no, bestandteil}, zu_pruefen, pruefung ({id, ergebnis, ergebnis_text, datum, pruefer,
protokoll_id} – im Lauf) | null, entwurf ({id, pruefer, eigen}) | null, uebernommen (wie pruefung – letzte gültige) |
null}`, `set_pruefung` ({id, entwurf, pruefer, eigen}) | null, `fortschritt` {geprueft, zu_pruefen, teile}, `bereit`
(der Set-Artikel lässt sich jetzt festschreiben), `freigabe_gruende` (Vorschau am gesperrten Set: was die Freigabe jetzt
noch verhindert, ohne den Set-Artikel selbst), `hinweis_tage` (> 7, sonst 0), `abschluss` ({gesamtergebnis, gesamt_text,
freigegeben, gruende, hinweis} am abgeschlossenen) | null.

**Set-Block** (`artikel.set`) neu: `sperrgruende` [{art „eigen“ | „verloren“ | „unvollstaendig“ | „pruefen“ |
„set_pruefung“, artikel ({id, inventory_no, set_artikel}) | null, text}] (leer bei freiem Set), `lauf` (kurz) | null,
`letzte_pruefung` {lauf, pruefung_id, protokoll_id, datum, gesamtergebnis, gesamt_text, freigegeben, berichtigt_durch,
berichtigte_teile [{inventarnummer, protokoll_id, durch}]} | null; je Teil `slot_id`, `austausch`, `set_pruefen`,
`verbleib_vorschlag`; je Position `id` (für `slot_id`).

**Teiletabelle** (`set_protokoll.zeilen`): `{art „teil“ | „bestandteil“, bezeichnung, inventarnummer, seriennummer,
ergebnis, ergebnis_text, protokoll_id, pruefsumme, vorhanden (true | false | null), vorhanden_text („vorhanden“ | „fehlt“
| „nicht zutreffend“ bei Bestandteilen, „fehlt“ bei einer fehlenden Position), uebernommen}`.

Journal neu: Aktionen „set_gesperrt“, „set_frei“, „teil_gesperrt“, „teil_entnommen“, „teil_eingesetzt“,
„teil_geloescht“, „entnommen“, „set_lauf_eroeffnet“, „set_lauf_abgebrochen“, „set_geprueft“; Felder `lock_cause`,
`teil`, `verbleib`, `gesamtergebnis`, `freigegeben`, `gruende`, `lauf`, `set_lauf_id`, `set_grund`, `bestandteil`,
`bestaetigt`, `ersetzt_teil`, `austausch`, `hinweis`, `geprueft` – Beschriftungen gleichlautend in `beschriftung.py` und
`material.js`; die Wörter für die Werte (`lock_cause`, `verbleib`, `gesamtergebnis`, `set_grund`, `austausch`) stehen in
`beschriftung.SET_WERTE` – `wert()` in `material.js` braucht sie noch (Oberfläche).

### Abweichungen vom Entwurf und Entscheidungen des Baus (K2, mit Begründung)

1. **Ergebnis „aussondern“ an einem Teil** = entnehmen und aussondern in einem Zug (Entwurf D nennt am Teil nur „Teil
   entnehmen“ – das gilt für den Materialwart). Ein Prüfergebnis „aussondern“ ist überall die Aussonderung; der
   Sachkundige hat das Teil gesehen. Das Set ist danach unvollständig gesperrt.
2. **„Teil einsetzen“ an einer fehlenden Position** zusätzlich zu „Teil tauschen“ (Entwurf G nennt nur tauschen): Nach
   Entnehmen, Löschen oder „aussondern“ am Teil bliebe ein Set sonst für immer unvollständig. Gleiche Regeln (Austausch
   laut Hersteller, Bestätigung, Produkt laut Kopie).
3. **Festschreiben der Set-Artikel-Prüfung erst mit vollständig geprüftem Umfang** (409) – wie „Durchgang abschließen“.
   Ein Gesamtergebnis „nicht vollständig geprüft“ hätte ein freies Set im Protokoll „nicht einsatzbereit“ genannt, ohne
   es zu sperren. Ein Teil, das sich nicht prüfen lässt (verloren), nimmt man über „Teil entnehmen“ heraus.
4. **Gesamtergebnis als Zustand des Sets danach** (einsatzbereit | gesperrt | ausgesondert) statt „schlechtestes aus den
   Ergebnissen“: dasselbe in allen Fällen (ein „instandsetzen“ eines Teils sperrt das Set), dazu bei „einsatzbereit“ am
   gesperrten Set die Gründe gegen die Freigabe. Gespeichert im Journal („set_geprueft“) und im PDF – keine neue Spalte,
   Schema bleibt 21.
5. **Mitsperr- und Mitfrei-Einträge mit dem Handelnden „System“** (`journal.eintragen(…, system=True)`, neuer
   Schlüsselwortparameter) statt Maskierung in Verlauf und Lebenslauf-PDF (S24 lässt beides zu) – so taucht der Name an
   keiner Stelle auf, auch nicht in künftigen Ausgaben.
6. **Set aussondern durch den Materialwart nur mit eigenem Grund im Set oder verloren und ohne ungeprüfte Meldung an Set
   oder Teil** (A15): Eine Sperre nur aus Unvollständigkeit oder Tausch hat kein Sachkundiger gesehen; eine Sperre aus
   einer Meldung an einem Teil hätte sonst über den Set-Artikel (dessen eigene Meldungen `nur_gemeldet` prüft) ein
   ungesehenes Set aussondern lassen.
7. **Aussondern beim Entnehmen**: statt `mangel.nur_gemeldet` (prüft `lock_before = frei`) `mangel.ungeprueft` – an einem
   mitgesperrten Teil steht in der Meldung `lock_before` „gesperrt“, obwohl der eigene Grund allein aus ihr kommt.
8. **Mit ausgesonderte Teile bleiben am Set** (`parent_item_id`), jedes mit eigenem Aussonderungsprotokoll: Lebenslauf und
   Set-Seite des ausgesonderten Sets zeigen sie weiter. Grund „mit dem Set … ausgesondert: …“; aus einer Prüfung trägt
   ihre Aussonderung die Set-Prüfung als Grundlage (Jahresbericht: „aus Prüfung“), beim Materialwart „sonstiger Grund“.
   `protokoll._folge` sucht die Aussonderung jetzt am selben Artikel (sonst fände es die eines Teils).
9. **Ursprung „set“ auch nachträglich**: Bekommt der Set-Artikel während einer Teil-Sperre einen eigenen Grund, wird
   `set_lock_origin` „set“ – der Prüfumfang wächst auf alle Teile (sicherer als ihn beim ersten Anlass festzuhalten).
10. **`set_pruefen` bleibt bis zur Freigabe**: Eine Set-Prüfung ohne Freigabe zählt für den nächsten Lauf nicht – die
    betroffenen Teile werden in dem Lauf geprüft, der freigibt (die Prüfung des Set-Artikels ohnehin).
11. **Bestandteil-Zeilen als Prüfpunkte ohne Formularpunkt** (`checklist_item_id` NULL, Gruppe „Bestandteile des Sets“):
    „fehlt“ ist ein Mangel und braucht wie jeder ein Foto und eine Bemerkung; nicht kritisch – ob das Set ohne den
    Bestandteil taugt, entscheidet der Prüfer im Ergebnis (keine fachliche Vorgabe erfunden).
12. **Neue Sperrart „set“ im Jahresbericht** (Set unvollständig oder Teil getauscht) – sonst stünde eine solche Sperre als
    „Sperre durch Prüfer ohne Prüfung“ da, obwohl sie der Materialwart auslöst.
13. **Routen am Set-Artikel, Teil-Kennung im Inhalt** (`teil_id`) statt eigener Pfad-Platzhalter: Bezug und Recht kommen
    über `<iid>` (requires_folder), die Teil-Kennung prüft der Dienst (404 wie unbekannt). Darum keine Zeile in
    `FELDER_IM_INHALT` nötig; die Formen B, „7“, 7.0 und unbekannt prüft `test_material_sets_pruefung` eigens.
14. **Lesen der Set-Prüfung an einem Artikel, der kein Set ist**: 200 mit `null` (wie ein Set ohne Prüfung) – die
    Rundum-Tests der Rollen lesen jede Route mit einem gewöhnlichen Artikel.
15. **Hinweis nach mehr als 7 Tagen** zwischen dem Prüftag der ersten Teilprüfung im Lauf und dem Abschluss; er steht im
    Protokoll, im Journal und am Lauf (`hinweis_tage`), verhindert nichts.
16. **Ein offener Lauf außerhalb eines Durchgangs** lässt sich nicht nachträglich einem Durchgang zuordnen
    (`round_id` steht fest, Trigger): „Set prüfen“ aus dem Durchgang antwortet dann 409 – abschließen oder abbrechen.

### Tests (K2)

`tests/test_material_sets_pruefung.py` (neu, 7 Tests): Kaskade je Sperrweg mit Journal und Datenschutz (Leser sieht am
Set und an den übrigen Teilen keinen Meldernamen) und Mails; Set prüfen (nur im Lauf, Umfang, Fortschritt, Teiletabelle,
PDF/A per veraPDF, „Teil von Set“ im Teil-Protokoll, Unveränderlichkeit der Teiletabelle gegen UPDATE, DELETE, INSERT,
REPLACE), Freigabe-Bedingungen einzeln (überfällig, Lebensdauer erreicht, verloren, neu, Wettlauf Meldung während
Entwurf), Berichtigungen geben nie frei („instandsetzen → einsatzbereit“ am Teil, Set-Prüfung), Abbrechen; Hinweis
nach mehr als 7 Tagen; Aussondern mit Wahl je Teil und Vorbedingungen, Ergebnis „aussondern“ an Teil und Set-Artikel;
Tauschen, Entnehmen, Einsetzen, Löschen mit Austausch-Regeln, Zuordnung und fremder Teil-Kennung; Durchgang mit Set
(Sammelprotokoll gruppiert); Jahresbericht (eine Set-Sperre zählt einmal, Art „set“, Freigabe einmal), Trennung der neuen
Routen, Rückruf nennt das Set. Angepasst: `tests/test_material_sets.py` (Routentabelle mit K2-Erwartungen, Teil
einzeln löschbar).

### Bitte bestätigen

Zusammengeführt am Ende dieses Abschnitts („Bitte bestätigen (zusammengeführt)“, Nr. 1–20).

### Oberfläche (O1, 23.10.2026)

`material.js`, `suche.js`, `global.js`, `material.css`, `global.css` für den Stand K1 – Dienste und Routen unverändert.

- **Katalog**: Produkt-Dialog mit Häkchen „Hersteller-Set“ (ausgegraut mit `set_umschalt_grund`, wenn es nicht
  umschaltbar ist); gesetzt erscheinen die Reiter „Produkt“ und „Bestandteile“ (Dialog dann breiter). Je Position
  „einzeln geführt“ (dann Katalogprodukt suchen wie bei „Artikel anlegen“, ein Set-Produkt wird abgewiesen), Bezeichnung
  (bei einzeln geführten leer = Produktname), Anzahl, „Austausch laut Hersteller“; ↑ ↓ ✕, „Bestandteil anlegen“, Zähler
  „n von 30 Positionen · k von 50 einzeln geführten Stück“, Hilfetext zum Kriterium. „Speichern“ (die eine Hauptaktion)
  speichert erst das Produkt samt `is_set`, dann `PUT …/bestandteile` (nur bei Änderung); „Position n: …“ vom Server
  markiert die Position. Häkchen weg an einem Set mit Stückliste fragt vorher. Produktseite: Abschnitt „Stückliste“
  (Knopf „Stückliste bearbeiten“ öffnet den Reiter), Stammdaten „Hersteller-Set“ und „Bestandteil von …“; Katalogliste
  mit Marke „Set“. „Als Variante kopieren“ eines Sets: Häkchen „Stückliste übernehmen“ (vorbelegt). Importbericht mit
  Zeile „Stücklisten“, Export-Vorschau mit `set_verstoesse`.
- **Artikel anlegen** mit Set-Produkt: unter den Feldern des Sets „Teile des Sets“ – je einzeln geführter Position und
  Anzahl ein Block mit den Feldern aus `set.teil_felder` (Länge nur bei `laenge_moeglich`), Kauf und Erstgebrauch des
  Sets als Vorgabe, Bestandteile ohne eigenen Artikel als Zeile. Doppelte Seriennummern (je Produkt, ohne Groß/klein)
  meldet die Seite am Feld (`aria-invalid`); Fehler des Servers stehen über dem Knopf und – wo sie eine Seriennummer
  oder einen Bestandteil nennen – am Teil. `hinweise` der Antwort (STR-Nummer anbringen) zeigt ein Dialog mit „Zum Set“
  bzw. „Nächsten anlegen“.
- **Set-Seite**: Überschrift mit Set-Status, Marke „Set“; Banner „Set unvollständig“ (mit `fehlend`), Rückruf an einem
  Teil (`rueckrufe_teile`, Link aufs Teil) und „Set überfällig/gesperrt/Lebensdauer erreicht – wegen eines Teils“, wenn ein
  Teil den Set-Status schwerer macht als den des Set-Artikels. Kasten „Bestandteile“: Set-Status, nächste Prüfung und
  Lebensende des Sets mit auslösendem Artikel; Tabelle Set-Artikel + Teile (Bestandteil, Produkt, Nummer, Status mit
  Mangel/Rückruf/Sperrgrund, nächste Prüfung, Lebensende), je fehlendem Stück eine Zeile „fehlt“, darunter die
  Bestandteile ohne eigenen Artikel. Verschieben und Löschen nennen die Teile. **Teil-Seite**: „Teil von Set
  <Inventarnummer> <Produkt>“ mit Link, Set-Status und Bestandteil; Verschieben, Zuordnen/Ändern/Lösen und Aussondern
  fehlen, dafür „Verschieben, Zuordnen und Aussondern gehen nur mit dem ganzen Set – zum Set …“. Sperren und
  „Mangel melden …“ stehen an Set und Teil wie bisher (bis K2 antwortet der Dienst 409).
- **Listen**: Ordner und „Fällige“ – Set-Zeile mit „Hersteller-Set · n Teile“, „unvollständig“, Mangel an Teilen, Rückruf
  an einem Teil als Marke, „Teil M-…“ unter der Fälligkeit, wenn ein Teil sie bestimmt; über der Liste „n Einträge,
  davon m Sets mit k Teilen“ (nur, wenn Sets darin sind). Suche (Liste und Vorschläge im Suchfeld): Teile mit „Teil von
  Set …“. Steckbrief der globalen Suche: „Teil eines Hersteller-Sets“.
- **Meine PSA**: Die Set-Karte trägt „Hersteller-Set mit n Teilen“ und darunter die Teile als kleine Karten (Banner nur,
  wo es vom Set abweicht); `/material/meine-psa/<Teil>` zeigt die Karte seines Sets.
- **Journal**: Listen aus Objekten (Teile beim Anlegen eines Sets, Positionen einer Stückliste) als lesbarer Text statt
  „[object Object]“.

Geprüft: `tests/test_material_sets_oberflaeche.py` (neu: Werte wie auf dem Server, statische Haken, Vertragstest der
gelesenen Schlüssel gegen die Antworten), st-js, st-css, ganze Suite; Browser (Chromium, DEMO-Daten) bei 1280 und
360 px: Katalog-Dialog (beide Reiter, Fehler an der Position, Stückliste speichern), Produktseite, Artikel anlegen
(Set, doppelte Seriennummer, Hinweise-Dialog), Set-Seite, Teil-Seite, Ordnerliste, Fällige, Suche, Meine PSA – ohne
Konsolenfehler, ohne waagerechtes Rollen.

**Abweichungen und Entscheidungen der Oberfläche**
1. Hilfetext „einzeln geführt“ und die Grenzen der Stückliste stehen zusätzlich in `material.js` (die Produktantwort
   trägt den Hilfetext nicht, ein neues Produkt hat noch keine `stueckliste_grenzen`); der Test hält beide gleich.
2. Aus einer Produktmeldung und für die Nacharbeit gibt es im Produkt-Dialog kein „Hersteller-Set“ (die Nacharbeit nimmt
   keins) – die Stückliste pflegt man danach unter „Bearbeiten“.
3. Scheitert die Stückliste nach dem Anlegen des Produkts, bleibt das Produkt (als Set ohne Stückliste) – wie beim
   Produktbild: Ein zweiter Klick speichert erneut, statt doppelt anzulegen.
4. Die Überschrift der Set-Seite zeigt den Set-Status; die Stammdaten darunter bleiben die des Set-Artikels.
5. Teil-Karten in „Meine PSA“ haben kein eigenes „Mangel melden …“ – nach Entwurf C meldet man am Set oder an einem
   gewählten Teil; den Dialog mit Teil-Wahl bringt O2.

**Fehlt an der Schnittstelle (für K2/O2)** – mit O2 erledigt (siehe „Oberfläche (O2)“, Server-Ergänzungen und Abweichung 3)
- Sichtbare Dublette eines Teils (409 „Diese Seriennummer gibt es bei diesem Produkt schon …“) nennt weder Teil noch
  Seriennummer – die Seite kann sie nur über dem Knopf zeigen. Vorschlag: Präfix „Teil „Bezeichnung“: “ wie bei den
  Regeln eines Teils.
- `ordner.direkt` (Zahlen an den Statusfiltern der Ordnerliste) zählt Teile einzeln (DEMO-Lager: „neu (3)“, die Liste
  zeigt eine Set-Zeile) – sollte je Set-Zeile mit Set-Status zählen.
- Lebenslauf-PDF (`beschriftung.wert_text`): Listen aus Objekten (`teile`, `bestandteile` im Journal) erscheinen als
  Python-Darstellung – K2 bzw. Lebenslauf.
- `set.sperrgruende` (K2) zeigt die Seite noch nicht; Set prüfen, Teil tauschen/entnehmen und der Aussondern-Dialog je
  Teil kommen mit O2.

**Bitte bestätigen (O1)** – zusammengeführt am Ende dieses Abschnitts, Nr. 21–25.

### Oberfläche (O2, 23.10.2026)

`material.js`, `material.css` für den Stand K2, dazu kleine Server-Ergänzungen (unten). Knopfsprache wie im Modul: je
Ansicht und Dialog höchstens ein roter Knopf, `btn danger` nur zum Bestätigen endgültiger Aktionen, Seltenes im
Untermenü, Touch-Regeln nur unter `@media (pointer: coarse)`, Listen per Container-Abfrage „mat-seite“.

- **Set-Seite**: Am Set-Artikel ersetzt **„Set prüfen“** die Einzelprüfung (rot, wenn das Set fällig – überfällig,
  bald fällig, neu, Lebensdauer erreicht – oder gesperrt ist; „Set-Prüfung fortsetzen“ rot bei laufender; sonst grau;
  wer nur liest oder verwaltet, sieht „Set-Prüfung ansehen“). Kasten „Bestandteile“ neu mit „Gesperrt, weil“ (aus
  `set.sperrgruende`, Teile verlinkt), der laufenden Set-Prüfung und der letzten (Datum, Gesamtergebnis, Protokoll,
  „berichtigt durch …“ und berichtigte Teilprüfungen). „Sperren“ gibt es auch an einem nur mitgesperrten Artikel
  (`lock_cause` „set“); Sperren und „Mangel melden …“ sagen, dass sie das ganze Set mit allen n Teilen sperren (Dialog,
  Toast, Quittung). „Set aussondern“ ist ausgegraut mit Grund, solange im Set kein eigener Grund eines Prüfers und kein
  Verlust steht (wie der Dienst, K2-Abweichung 6).
- **Seite „Set prüfen“** (`/material/artikel/<Set>/set-pruefung`, neue Seitenroute): ohne offene Set-Prüfung der
  Prüfumfang als Vorschau (periodisch alle Teile; nach einer Sperre der Set-Artikel und die betroffenen Teile, die
  übrigen „wird übernommen“), die Sperrgründe und „Set-Prüfung beginnen“ (aus dem Durchgang mit `durchgang_id`). Mit
  offener: Stand und Fortschritt („1 von 2 Teilen im Umfang geprüft“), Hinweis bei mehr als 7 Tagen, „Was die Freigabe
  noch verhindert“ (`freigabe_gruende` ohne die Zeilen „noch nicht geprüft“ – das zeigen die Karten), je Teil eine Karte
  „Teil n von m“ (zu prüfen → „Prüfen“, in Prüfung → „Weiter prüfen“ bzw. für den Materialwart „Reservierung
  aufheben“, geprüft mit Ergebnis und Protokoll, übernommen mit Datum und Protokoll → „auch prüfen“), zum Schluss der
  Set-Artikel. Rot ist genau ein Knopf: die nächste Prüfung, die jetzt dran ist (erst die Teile im Umfang, dann – sobald
  `bereit` – der Set-Artikel). „Set-Prüfung abbrechen …“ steht unter „Mehr“, mit Rückfrage. Abgeschlossen: Ergebnis mit
  Gesamtergebnis, Gründen, Hinweis und „Set-Protokoll ansehen“; frühere Set-Prüfungen sind verlinkt (`?lauf=`).
- **Prüfung starten**: am Set-Artikel ohne offene Set-Prüfung statt „Prüfung beginnen“ der Weg zu „Set prüfen“ (der
  Dienst antwortet sonst 409); an einem Teil „Teil von Set … · Teil n von m in der Set-Prüfung“, „Abbrechen“ führt dann
  zurück in die Set-Prüfung. Der Sperr-Banner sagt im Set, dass „einsatzbereit“ nur den eigenen Grund aufhebt (bzw. eine
  geerbte Sperre gar nicht) und frei erst „Set prüfen“ gibt.
- **Prüfansicht im Lauf**: unter der Produktzeile „Teil von Set … · Teil n von m · Set-Prüfung“ bzw. „Set-Artikel der
  Set-Prüfung“; nach dem Festschreiben (und an jeder abgeschlossenen Prüfung eines laufenden Laufs) ein Kasten mit dem
  Fortschritt und dem roten Weg zur nächsten Prüfung („Weiter prüfen: Teil …“ bzw. „Set-Artikel prüfen“) und „Zur
  Set-Prüfung“. Am Entwurf des Set-Artikels (`set_abschluss`) der Abschnitt „Set-Prüfung“ mit dem Umfang, ein Hinweis,
  solange er nicht `bereit` ist, und das **Gesamtergebnis vorab** je gewähltem Ergebnis (auch in der Abschlussleiste und
  im Festschreib-Dialog). Die Ja/Nein-Zeilen der Gruppe „Bestandteile des Sets“ heißen **„vorhanden“/„fehlt“** (gespeichert
  bleibt ja/nein). Ergebnis „aussondern“ am Set-Artikel: im Festschreib-Dialog die Wahl je Teil, vorbelegt mit
  `verbleib_vorschlag` (geht als `verbleib` mit). An Teilen sagen Leiste und Dialog, dass „instandsetzen“ das ganze Set
  sperrt und „aussondern“ das Teil aus dem Set nimmt. Abgeschlossen zeigt die Set-Prüfung ihre Teiletabelle
  (`set_protokoll`: Bestandteil, Nummern, Ergebnis bzw. „übernommen“, „vorhanden/fehlt“, Protokoll-ID mit Prüfsumme).
- **Teil tauschen, entnehmen, einsetzen** (Materialwart): je Teil in der Tabelle „Bestandteile“ das Untermenü
  „Austausch“ („Teil tauschen …“ – bei „Austausch laut Hersteller: nein“ grau mit Grund –, „Teil entnehmen …“), an einer
  Zeile „fehlt“ „Teil einsetzen …“ (bei „nein“ ausgegraut). Ein Dialog für alle drei: was danach mit dem Set ist, der
  Verbleib des alten Teils (weiterführen – mit dem Satz, was dann geschieht – oder aussondern mit Grund, Datum, Bemerkung
  und Unterschrift; nur wählbar, wo der Server es zulässt, `verbleib_vorschlag` „aussondern“; der Knopf wird dann
  `btn danger`), das neue Teil mit denselben Feldern wie beim Anlegen (`teilBlockHtml`, aus „Artikel anlegen“
  herausgelöst) und bei „nicht belegt“ das Häkchen „Der Austausch ist laut Herstellerunterlagen zulässig“ (Knopf erst
  danach frei). Fehler stehen im Dialog, ein abgelehntes neues Teil ist rot umrandet; `hinweise` (STR-Nummer anbringen)
  zeigt ein Dialog wie beim Anlegen.
- **Set aussondern**: der vorhandene Aussondern-Dialog am Set-Artikel („Set … aussondern“) mit der Wahl je Teil,
  vorbelegt, mit dem Sperrgrund je Teil.
- **Teil löschen** (ungeprüftes Teil, Teil-Seite): Die Rückfrage nennt, dass das Set danach unvollständig und gesperrt
  ist; danach geht es zur Set-Seite.
- **Durchgang**: Teile stehen eingerückt unter ihrer Set-Zeile (Tabelle und Karte), wenn die in der Auswahl steht – sonst
  für sich mit „Teil von Set …“; Set-Zeile mit Marke „Set“, der offenen Set-Prüfung (`set_lauf`, „läuft außerhalb dieses
  Durchgangs“, wenn sie nicht hierher gehört) und „Set prüfen“ bzw. „Set-Prüfung fortsetzen“ (mit `durchgang`) statt
  „Prüfen“.
- **Meine PSA**: „Mangel melden …“ an der Set-Karte fragt, was betroffen ist – Set-Artikel oder ein Teil (wo schon die
  eigene Meldung offen ist, ausgegraut); gemeldet wird am gewählten Artikel, die Texte nennen das ganze Set. Ausgegraut
  ist der Knopf erst, wenn an allen Artikeln des Sets die eigene Meldung offen ist.
- **Werte und Journal**: `wert()` liest `SET_WERTE` (Sperrursache, Verbleib, Gesamtergebnis, Anlass der Set-Sperre,
  Austausch) wie `beschriftung.SET_WERTE`; die neuen Aktionen standen schon in `AKTION`. Rückruf am Produkt: betroffene
  Teile mit „Teil von Set …“ (`set_inventar`).

**Server-Ergänzungen (mit Test)**
- Seite `GET /material/artikel/<iid>/set-pruefung[?durchgang=&lauf=]` (lesen; fremd 404 wie Unbekanntes).
- Abgelehnte Seriennummer eines Teils (sichtbare oder fremde Dublette) mit Präfix „Teil „Bezeichnung“: “ beim Anlegen
  eines Sets bzw. „Neues Teil „Bezeichnung“: “ beim Tauschen und Einsetzen (`sets.teil_schreiben`); die fremde bleibt
  `FremdeDublette` und wird weiter protokolliert.
- `ordner.direkt` (Zahlen an den Statusfiltern) zählt je Zeile der Liste, ein Set einmal mit seinem Set-Status
  (`baum()` für Leiste und Übersicht zählt weiter je Artikel).
- Lebenslauf-PDF (`beschriftung.wert_text`): Listen aus Objekten (Teile, Positionen) als Satz wie `listenWert()`.
- `artikel.lock_cause` (für „Sperren“ am mitgesperrten Artikel) und `teil_von.teile_anzahl` (Texte der Teil-Seite).

Geprüft: `tests/test_material_sets_oberflaeche.py` (neu: `test_oberflaeche_o2_statisch`, `test_vertrag_k2` gegen die
K2-Antworten, `test_server_ergaenzungen_o2`; Werte-Abgleich um `SET_WERTE`, `SET_GRUPPE`, `TEIL_FELDER`, `VERBLEIB`
erweitert), `tests/test_material_sets.py` (`teil_von` mit `teile_anzahl`), statische Zählungen in
`test_material_beschreibung.py` (Kopf von „Set prüfen“) und `test_material_mangel.py` (Aussondern ausgegraut auch am
Set ohne eigenen Grund) nachgezogen; st-js, st-css, st-py, ganze Suite (32 Dateien). Browser
(Chromium, DEMO-Daten, eigener Datenordner) bei 1280 und 360 px: Set-Seite (frei, gesperrt, nach Entnehmen und
Einsetzen), Teil-Seite, Set prüfen vorher/offen/abgeschlossen, Prüfung starten am Teil, Prüfansicht im Lauf (Entwurf,
festgeschrieben mit „weiter“, Set-Artikel mit Gesamtergebnis vorab, Festschreib-Dialog „aussondern“ mit Wahl je Teil,
Set-Protokoll), Untermenü „Austausch“, Dialoge Tauschen/Entnehmen (aussondern)/Einsetzen samt Hinweis-Dialog, Set
aussondern, Teil löschen, Durchgang mit Set, Meine PSA mit Teil-Wahl – ohne Konsolenfehler, ohne waagerechtes Rollen;
`st-geraete` (Chromium, Firefox, WebKit, alle Geräte) für Set prüfen, Durchgang, Prüfung starten und Meine PSA: ohne
Befund in den neuen Ansichten (die Tippflächen der Links in den Karten von „Set prüfen“ wurden dabei auf 44 px gebracht).

**Abweichungen und Entscheidungen der Oberfläche (O2)**
1. „Set prüfen“ ist eine **eigene Seite** statt eines Abschnitts der Set-Seite – wie „Prüfung starten“, am Telefon kurz
   und von jeder Prüfansicht aus erreichbar; die Set-Seite bleibt Übersicht.
2. „Set prüfen“ ist auch bei **laufender Set-Prüfung** rot („fortsetzen“) – sie ist dann die Hauptaktion des Sets.
3. **`hilfe_einzeln` und `stueckliste_grenzen` bleiben in `material.js`** (O1-Abweichung 1): Ein neues Produkt hat vor dem
   Speichern keine Antwort, die sie tragen könnte; eine eigene Anfrage nur dafür lohnt nicht. Der Test hält beide gleich.
4. **Teil löschen** bleibt auf der Teil-Seite („Löschen“, nur bei `darf_loeschen`); der Set-Block kennt `darf_loeschen`
   je Teil nicht, im Untermenü der Set-Seite stünde es sonst als Knopf, der 409 gäbe.
5. **„Mangel melden …“ an der Set-Seite** meldet am Set-Artikel, an der Teil-Seite am Teil; die Wahl im Dialog gibt es an
   der Set-Karte in „Meine PSA“ (wo die Teile keinen eigenen Knopf haben).
6. **Prüfen des Set-Artikels vor dem Ende der Teile** bleibt möglich (grau); festschreiben lässt er sich erst, wenn der
   Lauf `bereit` ist (Hinweis an Karte und Entwurf, der Server antwortet sonst 409).
7. Die **Zahlen an den Statusfiltern** zählen wie bisher ohne den Filter „Zugeordnet an“.
8. Im Durchgang behalten **Teil-Zeilen ihr „Prüfen“** (eine Einzelprüfung zählt in einem offenen Lauf mit, sonst wirkt
   sie über die Kaskade); nur an der Set-Zeile steht „Set prüfen“.

**Gefunden, nicht geändert (Dienst K2)** – beide mit der Nachbesserung erledigt (siehe „Prüfung vor Auslieferung“)
- Der **Sperrgrund am Set-Artikel bleibt stehen**, wenn das Teil, das die Sperre ausgelöst hat, entnommen wird
  (Probe: „wegen Teil M-000012: Sturzbelastung …“ nach „Teil entnehmen“ von M-000012) – Banner und Statusspalte zeigen
  den alten Grund, „Gesperrt, weil“ (abgeleitet) den richtigen („unvollständig …“). Vorschlag: `sets.sperren` zieht beim
  Anlass „unvollständig“/„Tausch“ den Grund am Set-Artikel nach, wenn er nur von dem entnommenen Teil stammt.
- Die Wahl „Art der Prüfung“ auf „Prüfung starten“ hat auf dem Telefon 43 px hohe Zeilen (`st-geraete` T, vorhanden seit
  Phase 1, nicht O2).

**Bitte bestätigen (O2)** – zusammengeführt am Ende dieses Abschnitts, Nr. 26–33.

### Prüfung vor Auslieferung (23.10.2026)

Drei Prüfungen am Stand 593a24b (K1, K2, O1, O2): **Sicherheit** (`planung/material-phase4/pruefung_l2_sicherheit.md`,
kein Befund hoch/mittel, sechs niedrige und ein bekannter), **Ablauf** (`pruefung_l2_ablauf.md`, M1–M2 mittel, N1–N4
niedrig) und **Browser** (`pruefung_l2_browser.md`, B1–B8, V1–V19; `st-geraete` in allen drei Engines ohne Befund).
Danach die Nachbesserung (Kern und Oberfläche, Tests `tests/test_material_sets_nachbesserung.py` neu und der statische
Test `test_oberflaeche_nachbesserung_statisch`). Kein neuer Schemaschritt (Trigger in Schritt 21 geändert, siehe
„Migration“).

**Ablauf**

| Nr. | Befund | Stand |
| --- | --- | --- |
| M1 | Veralteter Sperrgrund am Set-Artikel und an mitgesperrten Teilen – bis ins festgeschriebene Aussonderungsprotokoll | Behoben: `sets.gruende_nachziehen` setzt `lock_reason` an Set-Artikel (Ursache „set“) und mitgesperrten Teilen nach **jedem** Anlass aus dem jetzigen Stand (`sets.anlass_text`: eigener Grund des Sets, „wegen Teil …: …“ je Teil mit eigenem Grund, „unvollständig: „…“ fehlt“, „Teil … neu eingesetzt – Set prüfen“) – nach jeder Sperre (`sets.sperren`, auch Teil entnehmen, tauschen, einsetzen, löschen, Ergebnis „aussondern“ am Teil, Verlust), nach der Freiprüfung eines Teils (`eigen_aufheben`) und vor „Set aussondern“. Test genau nach der Probe (A-Protokoll nennt K2, nicht K1), dazu Teil löschen, Freiprüfung, „aussondern“ am Teil, Meine PSA |
| M2 | „Set prüfen“ an der Set-Seite bei offenem Durchgang: Lauf ohne Durchgang, Sammelprotokoll ohne Gesamtergebnis | Behoben: `setlauf.eroeffnen` ohne `durchgang_id` übernimmt `durchgang.offene_runde_fuer` (wie `pruefung.starten`); `sammel` findet einen Lauf auch über die Prüfung des Set-Artikels im Durchgang (deckt K2-Abweichung 16 mit ab). Test mit „Set-Prüfung: nicht einsatzbereit – Set gesperrt“ im Sammelprotokoll |
| N1 | Prüfumfang ohne übernehmbare Prüfung – der Set-Artikel ließ sich festschreiben, die Set-Prüfung war vergeblich | Behoben: Ein Teil ohne gültige „einsatzbereit“-Prüfung außerhalb des Laufs (neu, überfällig, keine) gehört von selbst zum Umfang (`setlauf.uebernehmbar`); 409 wie beim übrigen Umfang; die Vorschau liest den Umfang vom Server (`set.teile[].zu_pruefen`) |
| N2 | Jahresbericht: beim Aussondern eines freien Sets weitergeführte Teile zählten „aus Prüfung (instandsetzen)“ | Behoben: Journal „entnommen“ mit `set_grund` „ausgesondert“, Art „set“ geht im Bericht der Prüfung vor; Beschriftung „Set unvollständig, Teil getauscht oder Set ausgesondert“ |
| N3 | „Teil entnehmen“ bei „Austausch laut Hersteller: nein“ – Sackgasse | Behoben: Entnehmen 409 „Laut Hersteller nicht austauschbar – das Set aussondern …“; Ergebnis „aussondern“ an so einem Teil lässt es gesperrt im Set (eigener Grund „… – laut Hersteller nicht austauschbar: das Set aussondern“, kein Aussonderungsprotokoll), danach „Set aussondern“ durch den Materialwart (Teil vorbelegt „mit aussondern“); Oberfläche: Menüeinträge ausgegraut, Festschreib-Dialog sagt es |
| N4 | CLI `import-catalog` zählt geänderte Stücklisten als „unveraendert“ | Behoben: Zeile „Stücklisten neu, geaendert, unveraendert“; ein Set, an dem sich nur „set“ oder die Stückliste ändert, zählt bei den Produkten als geändert (auch im Bericht der App) |
| Nebenbei (M1) | Mail einer Mangelmeldung am nur mitgesperrten Set-Artikel nennt den neuen Grund als „war schon gesperrt (…)“ | Nicht geändert: Die Mail ist eine bestehende Formulierung der Mangelmeldung; der gespeicherte Grund stimmt jetzt. Beim nächsten Mail-Durchgang mitnehmen |
| Bitte bestätigen 15 | Fehlender Bestandteil ohne eigenen Artikel als nicht kritischer Mangel | Nicht geändert: Entscheidung des Nutzers (siehe Nr. 15 unten); „kritisch“ je Position wäre eine neue Spalte (später) |

**Sicherheit**

| Nr. | Befund | Stand |
| --- | --- | --- |
| 1 | Jeder Prüfer bricht eine fremde Set-Prüfung ab | Behoben: nur, wer sie eröffnet hat, oder wer den Ordner verwaltet; sonst 403 „Eine Set-Prüfung bricht ab, wer sie begonnen hat (…), oder der Materialwart …“; Lauf trägt `eigen`, „Mehr → abbrechen“ nur dann |
| 2 | Durchgang löschen bzw. abbrechen scheitert am Fremdschlüssel des offenen Set-Laufs | Behoben wie ein offener Entwurf: Löschen 409 mit dem Set („erst dort abbrechen oder den Durchgang abbrechen“), `loeschbar` false; Abbrechen löst die Set-Prüfung vom Durchgang (`round_id` NULL, Journal „set_lauf_geaendert“), ohne Prüfung verschwindet der Durchgang |
| 3 | Berichtigung einer Teilprüfung nach „Teil entnehmen“ bei offenem Lauf: 409 | Behoben: Die Berichtigung zählt nur dann im Lauf, wenn der Artikel noch zum Set gehört, sonst als Einzelprüfung |
| 4 | „Set aussondern“ durch den Materialwart lässt die Set-Prüfung offen | Behoben: `set_aussondern` beendet eine offene Set-Prüfung (abgebrochen bzw. ohne Prüfung entfernt, Journal mit Grund „Set ausgesondert“) – außer der, die das Ergebnis „aussondern“ gerade abschließt |
| 5 | Name des Eröffners einer offenen Set-Prüfung bleibt nach Kontolöschen, nicht dokumentiert | Behoben: an einem **offenen** Lauf „(gelöschtes Konto)“ wie am Entwurf; am abgeschlossenen oder abgebrochenen bleibt der Name (Prüfnachweis). `loeschung.py` (Kopf und Ablauf), Trigger, Abschnitt „Löschkonzept“ unten |
| 6 | Rückweg: Nach Code-Stand 20 überschreibt die nächste Set-Sperre die eigene Sperre eines Teils | Behoben: Eine gesperrte Zeile ohne `lock_cause` gilt als „eigen“ (Grund bleibt, `set_pruefen` 1); Hinweis unter „Migration“ |
| bekannt | Sperrgrund bleibt nach Entnehmen, Löschen, „aussondern“ – auch in „Meine PSA“ | Behoben mit Ablauf M1 |

**Browser** (Befunde)

| Nr. | Befund | Stand |
| --- | --- | --- |
| B1 | Reiter „Produkt \| Bestandteile“ auch ohne Häkchen | Behoben: `.c-tabs[hidden], .mat-reiter[hidden] { display: none; }` |
| B2 | Doppelte Teil-Seriennummer markiert beide Teile, nicht das Feld | Behoben: Server nennt Stück und Seriennummer („Teil „…“ 2 von 2 (Seriennummer „…“): …“, `sets.teil_wo`), die Seite markiert genau dieses Feld (`aria-invalid`, Text darunter, Fokus) |
| B3 | Ausgesondertes Set mit „unvollständig“, „fehlt“ und künftiger Fälligkeit | Behoben: kein Banner, keine „fehlt“-Zeilen, „Nächste Prüfung –“ |
| B4 | Veralteter Sperrgrund an weiteren Stellen | Behoben mit Ablauf M1 (der gespeicherte Grund ist überall der abgeleitete) |
| B5 | Fokus nach Esc/Abbrechen aus dem Untermenü „Austausch“ verloren | Behoben modulweit: Öffnet ein Eintrag eines Untermenüs einen Dialog, geht der Fokus beim Schließen auf den Menüknopf |
| B6 | „Nächste Prüfung“ im Kasten für gesperrte Sets | Behoben: „setzt die Freiprüfung („Set prüfen“)“ wie die Stammdaten |
| B7 | Vorschau „wird übernommen“ für Teil ohne Prüfung | Behoben mit Ablauf N1 |
| B8 | Kontrast 4,40:1 Rot auf Grau | Behoben: `--rot-auf-flaeche` auf grauen Zeilen (fehlende Position, Teilzeile im Durchgang) |

**Browser** (Verbesserungen)

| Nr. | Vorschlag | Stand |
| --- | --- | --- |
| V1 | Erklärtexte unter den Knöpfen der Set-Seite | Behoben: „Set aussondern …“ öffnet, wenn es nicht geht, einen Dialog mit der Begründung; „Prüfen dürfen …“ am Set weg |
| V2 | Zwei Banner bei „unvollständig“ | Behoben: ein GESPERRT-Banner nennt, was fehlt (und weitere Gründe); Rückruf- und Mangel-Banner bleiben |
| V3 | Prüfansicht des Set-Artikels zeigt nur „einsatzbereit“ | Behoben: Gesamtergebnis des Sets im Kopf, bei Abweichung als `.notice` |
| V4 | Kryptische Gründe, kein Trenner | Behoben: Sperr- und Freigabegründe als ganze Sätze vom Server, Gedankenstrich zwischen Marke und Satz |
| V5 | Seite „Set prüfen“ nach Abschluss | Behoben: Knopf grau, wenn nicht fällig/gesperrt; „Regelprüfung (alle Teile)“; Status und Auftrag getrennt; frühere Set-Prüfungen mit Gesamtergebnis und Protokoll (`kurz()` trägt `gesamtergebnis`, `gesamt_text`, `protokoll_id`) |
| V6 | Fällige: „Prüfen“ an der Set-Zeile | Behoben: „Set prüfen“ mit demselben Ziel wie im Durchgang |
| V7 | Marke „Set“ fehlt in Ordnerliste und Fällige | Behoben |
| V8 | ✕ im Reiter „Bestandteile“ | Behoben: „Entfernen“ als Text; ↑ ↓ bleiben wie im Formular-Editor |
| V9 | Produkt-Dialog springt beim Reiterwechsel | Behoben: Dialog mit Reitern steht oben |
| V10 | Meine PSA, „Mangel melden“ an der Set-Karte | Behoben: vom Set ist als „es“ die Rede (Dialog, Banner der Karte, Quittung), Hilfesatz unter dem Textfeld, Fokus auf die Wahl (Maus/Tastatur; am Touchgerät der Titel wie überall) |
| V11 | Begriffe | Behoben: „entnehmen“ überall, Menü „Teil tauschen …“/„Teil entnehmen …“/„Teil einsetzen …“, „das Set selbst“ statt „Set-Artikel“ in der Oberfläche; Glossar im README („Begriffe bei Hersteller-Sets“) |
| V12 | Zwei Absätze Hilfe im Reiter „Bestandteile“ | Behoben: eine Zeile, Rest aufklappbar |
| V13 | Tippflächen | Behoben unter `@media (pointer: coarse)`: Radiozeilen „Art der Prüfung“ (seit Phase 1) und eigenständige Links (zur Set-Prüfung, zum Set, Teil-Nummern der Set-Seite) 44 px |
| V14 | Ausgegrautes „Teil tauschen“ nicht fokussierbar | Behoben: `role="menuitem" aria-disabled="true" tabindex="0"` mit lesbarem Grund (bei „nein“ auch „Teil entnehmen“) |
| V15 | Eigene Schriftgröße | Behoben: `var(--fs-mittel)` |
| V16 | Fortschrittstext bricht einzeln um, Balken bei 0 % unsichtbar | Behoben |
| V17 | Grund im Dialog „Set aussondern“ vorbelegt | Behoben: „– bitte wählen –“, ohne Wahl Hinweis und Fokus aufs Feld (am einzelnen Artikel unverändert) |
| V18 | Journal-Einträge in der Breite | Nicht geändert: bestehendes Muster des Journals, nicht aus L2 |
| V19 | „Sperren“ und „Melden und sperren“ als `btn danger`, obwohl rückgängig | Nicht geändert: bestehend seit Phase 1, nicht aus L2 – im Entwurf der Knopfregel zu klären (Bitte bestätigen 45) |
| Abgleich 5 | README: Grund „Bestandteil von …“ beim ausgegrauten Häkchen | Nicht geändert: Der Grund kommt vom Server (`set_umschalt_grund`), am Bestandteil mit Artikeln nennt er die Artikel – beides trifft zu |

**Schnittstelle (Nachbesserung)** – nur Ergänzungen, nichts entfernt:
- `POST …/set-lauf` ohne `durchgang_id`: übernimmt den offenen Durchgang des Set-Artikels. `DELETE …/set-lauf`: 403 für
  andere als Eröffner und Materialwart. Lauf (voll) neu `eigen`; Lauf (kurz) neu `gesamtergebnis`, `gesamt_text`,
  `protokoll_id` (abgeschlossene, sonst null).
- Set-Block: je Teil `zu_pruefen` (Vorschau des Prüfumfangs); `sperrgruende[].text` und `freigabe_gruende` als ganze
  Sätze. Prüfung am Teil: `artikel.teil_von.austausch`; `GET …/artikel/<Teil>` `teil_von.austausch`.
- `POST …/teil-entnehmen` an „Austausch: nein“ → 409. `DELETE /durchgaenge/<id>` mit Set-Prüfung → 409; `loeschbar`
  entsprechend.
- Katalogimport-Bericht: `stuecklisten` {neu, geaendert, unveraendert}; Meldungen „Das Produkt „Hersteller | Modell |
  Artikelnummer“ … gibt es weder im Katalog noch in der Datei“ und „„set“ wechselte für „…“ auf …“.
- Journal: Aktion „set_lauf_geaendert“ (Set-Prüfung aus dem Durchgang gelöst), `set_grund` „ausgesondert“,
  `set_lauf_abgebrochen` mit `grund`.

**Löschkonzept (Set-Prüfungen)**: Beim Löschen eines Kontos wird der Eröffner einer **offenen** Set-Prüfung
„(gelöschtes Konto)“ – sie ist noch kein Nachweis (wie ein Entwurf); abbrechen kann sie danach der Materialwart. An einer
abgeschlossenen oder abgebrochenen Set-Prüfung bleibt der Name (Prüfnachweis wie die Prüfernamen in Protokollen, per
Trigger fest); die Kontokennung setzt die Datenbank auf NULL. Steht in `services/loeschung.py`.

**Tests**: `tests/test_material_sets_nachbesserung.py` (neu, 7 Tests: Sperrgrund nach der Probe M1 samt Löschen,
Freiprüfung und „aussondern“; Set-Prüfung im Durchgang mit Sammelprotokoll; Abbrechen-Recht, Durchgang löschen und
abbrechen; Berichtigung nach Entnehmen, Aussondern beendet die Set-Prüfung; Kontolöschen mit Triggerprobe, Rückweg;
„Austausch: nein“ und Jahresbericht; CLI). Angepasst: `test_material_sets_pruefung` (überfällig/neu jetzt im Umfang,
abgeleiteter Grund nach Tausch, Entnehmen bei „nein“), `test_material_sets` (Stücklisten-Zahlen, Meldungen),
`test_material_sets_oberflaeche` (Teil-Meldung mit Stück, ein roter Knopf, statischer Test der Nachbesserung).

**Browser** (Chromium über `cdp.py`, DEMO-Daten im eigenen Datenordner, Materialwart, Prüfer, Material-Verwaltung,
Mitglied) bei 1280 und 360 px: Set-Seite unvollständig (ein Banner, Grund ohne entnommenes Teil, „setzt die
Freiprüfung“, Dialog „warum“), mit gesperrtem Teil (Set aussondern ohne vorbelegten Grund), ausgesondert, „Austausch:
nein“ (Menü, Tastatur), Tauschen-Dialog mit Esc und Abbrechen (Fokus zurück auf „Austausch“), Ordnerliste und Fällige
(Marke, „Set prüfen“), Artikel anlegen mit doppelter Teil-Seriennummer (nur das eine Feld), Set prüfen vorher (grau,
Regelprüfung, Frühere mit Gesamtergebnis) und offen aus dem Durchgang (Fortschritt), Prüfansicht des Sets mit
Gesamtergebnis im Kopf, Produkt-Dialog neu (kein Reiter) und bearbeiten (Entfernen, Hilfe, keine Bewegung), Meine PSA
mit Set-Karte und Mangel-Dialog – ohne Konsolenfehler (außer der gewollten 409). `st-geraete` (Chromium, Firefox,
WebKit, alle Geräte) für Set-Seite, Set prüfen, Prüfansicht und Meine PSA.

### Katalog-Nachtrag „Sets“ (Katalogdaten, nicht im Repository)

Mit dieser Lieferung kommt der Katalog-Nachtrag `katalog-sets.zip` (Format 2, 41,3 MB; zwei Teile ≤ 28 MB, je allein
einspielbar): 14 neue Teilprodukte (MGO 60, Bm'D, Tango, Quick Link Asymmetric, CAMP Hercules/Oval/Hook/Express Ring,
Edelrid DSG Triton, Climbing Technology K-ADVANCE (Skylotec H-314), Singing Rock Big/Giga Connector) und die Stückliste
für 23 vorhandene Hersteller-Sets (Petzl ABSORBICA-Y MGO ×4, Kong Rescue TRIMMER, CAMP Dynatwo, Retexo Rewind Double,
Rope Adjuster ×3, Temporary Lifeline ×2, Edelrid Ombilix Adjust ×3, Skylotec LORY X ×4, Singing Rock Reactor ×4) –
nur aus Herstellerquellen, unabhängig geprüft (0 Fehler), Bericht mit Fundstellen, „Bitte bestätigen“ und Rückfragen an
die Hersteller beim Nachtrag. Einspielen erst NACH dem Deploy dieser Lieferung (ein älterer Stand übergeht „set“ und
„bestandteile“ ohne Meldung); vorher müssen die Lieferungen Selbstsicherungen und Karabiner eingespielt sein, und zu
keinem der 23 Set-Produkte darf es schon Artikel geben (sonst speichert der Import nichts und nennt das Produkt). Die
Ablaufprüfung hat Kong Rescue TRIMMER und Petzl ABSORBICA-Y MGO aus dem Nachtrag komplett durchgespielt (anlegen, Set
prüfen mit Set-Protokoll, Teil tauschen, Freigabe).

### Bitte bestätigen (zusammengeführt)

Aus Entwurf L (vom Bau gesetzt):
1. Entnehmen ohne Ersatz, Teil löschen und Teil tauschen sperren das Set bis zum Set-Lauf (K2).
2. Feld „Austausch laut Hersteller“ (ja/nein/nicht belegt) je Bestandteil; „nein“ verhindert den Tausch (K2) – seit der
   Nachbesserung auch das Entnehmen (siehe 37).
3. Teile ohne Herstellernummer bekommen eine STR-Nummer und ein eigenes Etikett (Hinweis beim Anlegen).
4. Eine Set-Sperre zählt im Jahresbericht einmal (K2).
5. „Hersteller-Set“ nur umschaltbar, solange das Produkt keine Artikel hat.
6. Nicht einzeln geführte Bestandteile erscheinen nur als Zeile „vorhanden/fehlt“ in der Set-Prüfung (K2).
7. Ordnerlisten und „Fällige“ zeigen nur die Set-Zeile; Teile auf der Set-Seite und in der Suche.
8. Ein nur mitgesperrtes Teil darf mit dem Set ausgesondert werden (K2).

Aus K1:
9. (erledigt mit K2) Zwischen K1 und K2 lehnte der Dienst Sperren, Mangelmeldung und Aussonderung an Sets und Teilen ab.
10. „Hersteller-Set“ ausschalten entfernt die Stückliste (mit Journal).
11. Der Filter „Zugeordnet an“ und „Meine PSA“ zählen ein Set einmal.

Aus K2 (Abweichungen oben, Nummern dort):
12. Ergebnis „aussondern“ an einem Teil entnimmt und sondert es aus; das Set ist danach unvollständig gesperrt (1) –
    außer bei „Austausch laut Hersteller: nein“ (37).
13. „Teil einsetzen“ an einer fehlenden Position (2).
14. Die Prüfung des Set-Artikels lässt sich erst festschreiben, wenn der Prüfumfang im Lauf geprüft ist (3).
15. Ein fehlender, nicht einzeln geführter Bestandteil ist ein (nicht kritischer) Mangel mit Foto und Bemerkung (11) –
    **bewusst entscheiden** (Ablaufprüfung): So kann ein Set mit „Falldämpfer fehlt“ freigegeben werden, wenn der Prüfer
    „einsatzbereit“ wählt; „kritisch“ je Position wäre eine spätere Ergänzung der Stückliste.
16. Set aussondern durch den Materialwart nur mit eigenem Grund (Prüfer) oder Verlust im Set und ohne ungeprüfte Meldung (6).
17. Mit ausgesonderte Teile bleiben am Set; Grund „mit dem Set … ausgesondert: …“ (8).
18. Betroffene Teile bleiben bis zur Freigabe im Prüfumfang – auch über einen Lauf ohne Freigabe hinweg (10).
19. Neue Sperrart im Jahresbericht (12) – seit der Nachbesserung „Set unvollständig, Teil getauscht oder Set ausgesondert“ (39).
20. Freigabe-Bedingung „Lebensdauer erreicht“ gilt für jeden Artikel des Sets, auch Metall mit eingetragenem Lebensende.

Aus O1:
21. Kopf „n Einträge, davon m Sets mit k Teilen“ nur, wenn die Liste Sets enthält.
22. Am Teil statt Verschieben, Zuordnen und Aussondern ein Hinweis mit Link aufs Set.
23. Hinweise beim Anlegen (STR-Nummer anbringen) als Dialog statt Toast.
24. Kauf und Erstgebrauch des Sets als Vorgabe der Teile (überschreibbar), Herstellung je Teil leer.
25. „Stückliste übernehmen“ bei einer Variante vorbelegt.

Aus O2:
26. „Set prüfen“ als eigene Seite; „Set-Prüfung abbrechen …“ unter „Mehr“ (mit Rückfrage).
27. „Set prüfen“ rot bei fälligem, gesperrtem Set und bei laufender Set-Prüfung, sonst grau (auf der Seite „Set prüfen“
    seit der Nachbesserung ebenso).
28. Gesamtergebnis vorab am Entwurf des Set-Artikels (Abschnitt, Leiste, Festschreib-Dialog).
29. „vorhanden“/„fehlt“ statt Ja/Nein für die Bestandteile ohne eigenen Artikel.
30. Durchgang: Teile eingerückt unter der Set-Zeile; Teil-Zeilen behalten „Prüfen“.
31. Meine PSA: Wahl des Artikels im Dialog; ausgegraut erst, wenn überall die eigene Meldung offen ist.
32. Statusfilter der Ordnerliste zählen Sets einmal mit ihrem Set-Status.
33. Aussondern beim Entnehmen und Tauschen nur dort wählbar, wo der Server es zulässt (sonst grau mit Satz).

Aus der Nachbesserung:
34. Der Sperrgrund an Set-Artikel und mitgesperrten Teilen ist **abgeleitet und wird bei jedem Anlass neu gesetzt** (ohne
    eigenen Journaleintrag – das Journal behält, was beim Sperren galt). Kurzform „wegen Teil …: …; unvollständig: „…“
    fehlt“; ein entnommenes Teil verschwindet daraus.
35. **Teile ohne übernehmbare Prüfung** (neu, überfällig, keine gültige „einsatzbereit“-Prüfung) gehören immer zum
    Prüfumfang – auch nach einer Sperre, die von einem anderen Teil ausging.
36. **Set-Prüfung folgt dem Durchgang**: „Set prüfen“ an der Set-Seite zählt im offenen Durchgang des Sets. Durchgang
    **abbrechen** löst eine offene Set-Prüfung (sie läuft ohne Durchgang weiter); **löschen** geht erst ohne Set-Prüfung.
37. **„Austausch laut Hersteller: nein“**: Teil entnehmen gesperrt; Ergebnis „aussondern“ an so einem Teil lässt es
    gesperrt im Set (die Prüfung trägt „aussondern“, ein Aussonderungsprotokoll entsteht erst mit dem Set); danach sondert
    der Materialwart das Set aus. Alternative wäre, „aussondern“ an so einem Teil gleich als „Set aussondern“ zu werten.
38. Abbrechen einer Set-Prüfung: wer sie begonnen hat, und der Materialwart.
39. Jahresbericht: Teile, die beim Aussondern eines freien Sets entnommen und gesperrt weitergeführt werden, zählen **je
    Teil** als Sperrart „set“ (drei Teile → drei Sperren). Alternative: sie nicht zählen, weil die Aussonderung des Sets
    schon zählt.
40. Kontolöschen: offene Set-Prüfung „(gelöschtes Konto)“, abgeschlossene behält den Namen.
41. Trigger `mat_set_lauf_kopf` in Schritt 21 geändert (Schritt noch nicht ausgeliefert) statt eines Schritts 22.
42. „Set aussondern“: Grund nicht vorbelegt; geht es noch nicht (nur unvollständig oder getauscht), öffnet der Knopf
    einen Dialog mit der Begründung statt ausgegraut mit Text darunter.
43. Fokus zurück auf den Menüknopf nach jedem Dialog aus einem Untermenü – modulweit, nicht nur „Austausch“.
44. „Set-Artikel“ heißt in der Oberfläche „das Set selbst“ (Schaltflächen „Set selbst prüfen“); Glossar im README.
45. (aus V19, nicht geändert) „Sperren“ und „Melden und sperren“ sind rot umrandet gefüllt (`btn danger`), obwohl eine
    Freiprüfung sie aufhebt – bleibt das so (Bestätigung einer folgenreichen Aktion) oder werden sie grau?
46. Katalogimport: „Stücklisten neu“ als eigene Zahl; ein Set mit nur geänderter Stückliste zählt bei den Produkten als
    „geändert“.

## Artikelnummern eindeutig je Hersteller (22.10.2026)

Entscheidung des Nutzers vom 22.10.2026, die die Regel vom 18.10.2026 („Artikelnummern eindeutig“, Lieferung 5) einengt:
Eine Artikelnummer muss nur noch **innerhalb eines Herstellers** eindeutig sein, nicht mehr katalogweit. Anlass: Echte
Herstellernummern kollidieren – Petzl MICRO TRAXION = P53 und JAG TRAXION = P54, Rock Exotica Omni-Block 2.0 Single =
P53 und Omni-Block 1.1 Single = P54; der Katalogimport „Seilrollen“ scheiterte an diesen zwei Produkten. Der
Dublettenschlüssel (Hersteller | Modell | Artikelnummer, UNIQUE) bleibt, kein Schemaschritt.

### Verhalten

- **Katalog** (`katalog.artikelnummer_vergeben(article_no, hersteller, ausser)`): Treffer nur beim selben
  vereinheitlichten Hersteller („Test-Werk“ = „Testwerk“); die Abfrage sucht `dedupe_key LIKE '<herst>|%|<nr>'` –
  vereinheitlichte Werte bestehen nur aus Buchstaben und Ziffern, enthalten also weder „|“ noch die Platzhalter von
  LIKE. Leer oder „-“ zählt weiter nicht. Fehlermeldung beim Anlegen, Ändern und Kopieren als Variante: „Die
  Artikelnummer „…“ ist bei <Hersteller> schon vergeben: …“ (409). Beim Ändern wird jetzt auch geprüft, wenn nur der
  **Hersteller** wechselt (die Nummer dann beim neuen Hersteller frei sein muss); eine Dopplung aus der Zeit vor der
  Regel blockiert andere Änderungen weiterhin nicht. Neu `katalog.produkte_mit_artikelnummer(article_no)`: alle
  Produkte mit dieser Nummer, gleich bei welchem Hersteller – für Aufrufer, die ein Produkt nur über die Nummer suchen.
- **Hinweis beim Tippen** (`GET /api/material/produkte/artikelnummer?nr=&hersteller=&ausser=`): neuer Parameter
  `hersteller` (wie im Formular getippt); Produkt- und Meldedialog schicken ihr Herstellerfeld mit und prüfen erneut,
  wenn sich der Hersteller ändert. Ohne Hersteller oder bei einem anderen gibt es keinen Hinweis; die Antwort ist
  unverändert.
- **Katalogimport** (Format 1 und 2): keine eigene Prüfung – die Regel greift über `produkt_anlegen`/`produkt_aendern`;
  dieselbe Nummer bei zwei Herstellern geht durch, beim selben Hersteller bleibt es die Fehlerzeile ohne Speichern.
- **Bestandsimport** (`bestandsimport.produkt_finden`): Stufe „artikelnummer“ trifft das Produkt des Herstellers der
  Liste. Tragen mehrere Hersteller die Nummer und die Liste nennt keinen davon (Hersteller fehlt oder passt zu keinem),
  geht die Zeile als „Produkt mehrdeutig“ in die Nacharbeit – Text: „Artikelnummer „P53“ gibt es bei mehreren
  Herstellern (A, B) – bitte den Hersteller in der Liste angeben oder in der Nacharbeit zuordnen.“, die Träger als
  Vorschläge. Gibt es die Nummer bei genau einem anderen Hersteller, bleibt es wie bisher ein Vorschlag. Eine
  Hersteller-Spalte hat der Import schon (Hersteller, Marke, Fabrikat, manufacturer) – damit ist die Zeile eindeutig.
- **Produktmeldung**: Beim Melden zählt nur die Nummer beim selben Hersteller als „gehört schon zu …“ (409); der
  Treffer „steht inzwischen im Katalog – ein Klick ordnet zu“ ist nur noch das Produkt desselben Herstellers mit der
  Nummer (oder die Dublette), nie eines eines anderen Herstellers. Beim Anlegen aus der Meldung prüft `produkt_anlegen`
  mit dem Hersteller.

### Tests

- `tests/test_material.py::test_artikelnummer_eindeutig` umgeschrieben: gleiche Nummer beim selben Hersteller
  (auch anders geschrieben) → 409 beim Anlegen, Ändern der Nummer und Wechsel des Herstellers; bei einem anderen
  Hersteller → 201/200; Hinweis beim Tippen mit und ohne Hersteller; Meldung bei anderem Hersteller erlaubt, Treffer
  nur beim selben; Katalogimport Format 1 (Fehlerzeile) und Format 2 (durch).
- `tests/test_material.py::test_produkt_variante`: Variante mit anderem Hersteller und der Nummer HB-7 → 201.
- `tests/test_material_import.py::test_produktabgleich`: P-53 bei zwei Herstellern – Zeile mit dem Hersteller
  übernehmbar, ohne Hersteller oder mit einem dritten → Nacharbeit „bei mehreren Herstellern (…)“.
- `tests/test_material_beschreibung.py`: der Hinweis beim Tippen mit `hersteller`.

### Bitte bestätigen

- Nacharbeit-Text „Artikelnummer „…“ gibt es bei mehreren Herstellern (A, B) – bitte den Hersteller in der Liste
  angeben oder in der Nacharbeit zuordnen.“ (Gruppe „Produkt mehrdeutig“, die Träger als Vorschläge).
- Produktmeldung: Der Ein-Klick-Treffer berücksichtigt nur den Hersteller der Meldung; ein Produkt eines anderen
  Herstellers mit derselben Nummer wird nicht angeboten (die Material-Verwaltung findet es über die Produktsuche).
- Beim Ändern wird die Nummer jetzt auch geprüft, wenn nur der Hersteller wechselt (vorher nur bei neuer Nummer).

## Texte: „Reservierung aufheben“, Hinweise in die Dialoge (Wunsch des Nutzers, 23.10.2026)

- Eine liegen gebliebene Prüfung eines anderen Prüfers heißt beim Aufheben jetzt überall **„Reservierung aufheben“**
  statt „Freigeben“ bzw. „Reservierung freigeben“: Liste der offenen Prüfungen, Artikelseite, Prüfansicht, Durchgang,
  Rückfrage („… verwerfen und die Reservierung aufheben?“, Knopf „Reservierung aufheben“), Meldung „Reservierung
  aufgehoben“, Fehlertexte der Dienste („… hebt der Materialwart auf“, „Erst die Reservierung aufheben“) und die
  Journal-Beschriftung (Verlauf, Lebenslauf-PDF) „Reservierung aufgehoben“. Der Schlüssel im Journal bleibt
  `reservierung_freigegeben` (gespeicherte Daten). „Freigeben“ im Sinne einer Freiprüfung (gesperrter Artikel) bleibt.
- Artikelseite: Die Hilfezeile unter „Sperren“/„Mangel melden …“ entfällt; der Dialog „Mangel melden“ sagt jetzt
  „Mit Beschreibung und Fotos – Materialwarte und Prüfer bekommen eine Mail.“ (der Dialog „Sperren“ erklärt sich schon
  selbst). Unter „Zuordnen …“ entfällt der Erklärtext – er steht im Dialog.
- Tests: statischer Oberflächentest in tests/test_material_mangel.py angepasst; Suite grün.
- Nach der Browserprobe (Chromium 1280/360 px, st-geraete für die Artikelseite: 21 Geräte × 3 Engines ohne Befund):
  Hilfetext über „Offene Prüfungen“ („Bleibt eine Prüfung liegen, hebt der Materialwart die Reservierung auf.“) und Schnittstellentabelle
  nachgezogen; auf der Artikelseite bleiben „· ansehen“ und „· Reservierung aufheben“ beim Umbruch je zusammen (kein
  Trennpunkt allein am Zeilenende); am Finger sind auch die Knöpfe der Rückfrage „Bist du sicher?“ 44 px hoch (vorher
  36 px, galt für alle Rückfragen im Modul).
- Artikellisten (Ordner, Prüfungen/Fällige, Suche, Durchgang): Der **Produktname** ist ein roter Link auf den Artikel
  wie die Ordner im Bestand und hebt sich so von Bemerkung, Artikelnummer, Länge und DEMO-Marke ab (die bleiben grau
  bzw. dahinter). Für die Tastatur bleibt die Inventar-Nr. der Link der Zeile (Name mit tabindex -1); eine fremde Zeile
  im Durchgang (nicht in deinem Bereich) zeigt den Namen weiter als Text. Statischer Test in
  tests/test_material_beschreibung.py; Browserprobe Chromium 1280/360 px ohne Konsolenfehler und ohne waagerechtes Rollen.
- Untermenü „Export“ bzw. „Export / Import“ im Ordnerkopf: „Jahresbericht“ heißt jetzt **„Jahresbericht exportieren“**
  (wie „Artikelliste exportieren“ und „Protokolle exportieren“), „Bestandsliste importieren …“ jetzt **„Bestandsliste
  importieren“** – der Eintrag öffnet eine Seite, keinen Dialog. Statischer Test in tests/test_material_import.py.
- Stückliste (Produktseite, Reiter „Bestandteile“ im Produkt-Dialog, Journal/Lebenslauf): Spalte bzw. Feld **„Einzeln
  geführt“** (vorher „einzeln geführt“) und **„Austausch laut Hersteller möglich“** (vorher „Austausch laut Hersteller“),
  gleichlautend in material.js und beschriftung.py (Wunsch des Nutzers, 24.10.2026).
- Produktsuche (Artikel anlegen, Produkt am Artikel ändern, Stückliste, Meldung zuordnen, Nacharbeit des
  Bestandsimports): Hersteller-Sets tragen die Marke „Set“ wie in der Katalogliste – in jedem Treffer und beim Anlegen
  am gewählten Produkt (Wunsch des Nutzers, 24.10.2026).
- Dieselbe Produktsuche sortiert die Treffer nach Kategorie; vor jeder Kategorie steht eine Trennlinie mit ihrem Namen in
  kleiner grauer Schrift, die Kategorie steht nicht mehr in jeder Zeile (Wunsch des Nutzers, 24.10.2026).

## Nachbesserung zu Schritt 18 nach der Sicherheitsprüfung (22.10.2026)

Die unabhängige Prüfung von Commit 9f6522c (Bericht `pruefung-schritt18/bericht.md`, außerhalb des Repositories) fand
drei Befunde, alle nachgestellt; Push auf dev war vertretbar, vor dem Import der ganzen Karabiner-Lieferung sollte
Befund 1 behoben sein. Alles drei ist behoben, sonst bleibt Schritt 18, wie er war (keine Schemaänderung).

- **Befund 1 (mittel) – Wettlauf „letztes Produkt löschen“ gegen „denselben Inhalt ablegen“.** `_datei_freigeben` fragte
  „nennt noch eine Zeile die Datei?“ und löschte ohne Sperre; `_einordnen` sah „Datei liegt schon“ und verwarf die
  Zwischendatei, die Zeile kam erst danach. Traf das Löschen des letzten Produkts mit dieser Datei dazwischen, nannte
  die neue Zeile eine Datei, die es nicht mehr gab – beim Hochladen ein Fenster von Millisekunden, beim Katalogimport
  (alle Dateien zuerst, Zeilen im zweiten Durchgang) Sekunden bis Minuten. Jetzt entscheiden Freigeben und Anlegen
  unter **derselben Schreibsperre**:
  - `katalog._datei_freigeben`: Abfrage und `os.remove` in `BEGIN IMMEDIATE` (`db.transaction(sofort=True)`); nie
    innerhalb einer Transaktion aufzurufen (Docstring) – alle Aufrufer stehen nach dem Commit bzw. Rollback.
  - Hochladen (`dokument_anlegen`): `_datei_schreiben` schreibt und hasht die Zwischendatei außerhalb der Sperre (bei
    50 MB dauert das); in der Transaktion der Zeile folgt erst der INSERT, dann `_einordnen` (Zwischendatei an ihren
    Inhaltsnamen oder weg, weil der Inhalt schon liegt). Scheitert die Transaktion, geht die Zwischendatei weg und
    `_datei_freigeben` räumt den Inhaltsnamen, wenn ihn keine Zeile nennt. `_datei_ablegen` (schreiben + einordnen)
    bleibt für den Import.
  - Katalogimport (`importer._Lauf.ablegen`): Die vorab abgelegten Dateien werden beim Schreiben jeder Zeile unter der
    Sperre geprüft (`os.path.isfile`); fehlt eine (inzwischen freigegeben), legt der Durchgang sie **aus dem Archiv
    nach** – der Import gelingt, kein Fehler für den Nutzer. Die nachgelegte Datei steht in `abgelegt` und geht bei
    einem Rollback mit weg.
  - Variante (`produkt_variante`): In der Transaktion prüft `_datei_sichern` je kopiertem Dokument, dass die Datei
    liegt; sonst **409** „Die Datei des Dokuments „…“ liegt nicht mehr unter media/material/dok – das Dokument wurde
    inzwischen gelöscht oder seine Datei fehlt. Bitte die Seite neu laden.“ und kein neues Produkt (Rollback). Das
    trifft auch eine Altzeile ohne Datei (Schritt 18 ließ sie stehen): Sie lässt sich nicht auf eine Variante
    kopieren, bis das Dokument neu hochgeladen ist.
- **Befund 2 (niedrig) – Waisen nach einem Abbruch zwischen Commit und Entfernen der alten Namen.** Ein zweiter Lauf
  sah nur Zeilen, die alten Namen (bei der Karabiner-Lieferung 269 MB) blieben still liegen; `--probe` meldete „nichts zu
  tun“. Jetzt (`dokablage.aufraeumen`): Jeder Lauf zählt **Dateien ohne Zeile** und entfernt die, deren SHA-256 einem
  Inhaltsnamen entspricht, den eine Zeile nennt (das sind genau die alten Namen); alle anderen bleiben liegen (eine
  Datei, die schon ihren Inhaltsnamen trägt, immer – ein laufender Import legt seine Dateien vor den Zeilen ab) und
  stehen im Bericht („Dateien ohne Zeile: n (x MB) – bleiben liegen; entfernt, weil der Inhalt unter seinem Inhaltsnamen
  liegt: k“) und im Log (`media/material/dok: n Dateien ohne Zeile (x MB) – sie bleiben liegen …` als Warnung,
  `media/material/dok aufgeräumt: k Dateien ohne Zeile entfernt …, z Zwischendateien älter als ein Tag entfernt.` als
  Info). Das Aufräumen läuft auch bei **jedem Start** mit gesetztem Kennzeichen (unter der Schreibsperre, damit es nur ein
  Arbeitsprozess tut; still, wenn nichts zu tun ist) – so heilt der Abbruch nach dem Commit beim nächsten Start von
  selbst, ohne Kommandozeile. Docstring von `dokablage.py` und „Bitte bestätigen 1“ berichtigt.
- **Befund 3 (niedrig) – Zwischendateien überleben einen Absturz, `.teil` zählte als Dokumentdatei.** Die Zwischendatei
  des Kopier-Rückfalls heißt jetzt `.<sha><ext>.teil` (Punkt davor wie `.neu-<token><ext>`); `_bestand` übergeht alle
  Punkt-Namen. Zwischendateien älter als einen Tag (`ZWISCHENDATEI_ALTER`) entfernt `aufraeumen` beim Start und in der
  Kommandozeile mit Zählung („Zwischendateien älter als ein Tag entfernt: z“); jüngere gehören einem laufenden Vorgang.
- **Nicht geändert**: Schema (18 bleibt), Auslieferung, Rechte, Export/Import-Format, Oberfläche. Die Hinweise des
  Berichts zu den „Bitte bestätigen“-Punkten 2 (bei jedem Start warnen) und 5 (Größenvergleich statt Hash beim
  Inhaltsnamen) sind offen und nicht Teil dieser Nachbesserung.
- **Tests** (`tests/test_material_dokumente.py`, aus den Proben der Prüfung): `test_wettlauf_loeschen_ablegen` – Haken an
  der Stelle außerhalb der Sperre (Hochladen: nach `_datei_schreiben`; Import: nach dem Ablegen vor dem zweiten
  Durchgang) löscht das letzte Produkt mit dem Inhalt; danach hat jede Zeile mit `file_path` ihre Datei, Abruf 200,
  Import gespeichert mit zwei neuen Zeilen; Variante mit fehlender Datei 409 ohne neues Produkt, mit Datei 201.
  `test_aufraeumen` – nach der Zusammenführung liegen die alten Namen wieder (Abbruch nach dem Commit), dazu eine
  fremde Datei ohne Zeile, zwei alte und eine junge Zwischendatei: der nächste Start entfernt die vier Dubletten und die
  zwei alten Zwischendateien, lässt fremde Datei und junge Zwischendatei liegen, Log mit Warnung und Info, kein zweiter
  Schritt-18-Lauf; noch ein Start meldet nur die fremde Datei; `dok-zusammenfuehren --probe` zählt (Zwischendateien
  nicht in „Dateien vorher“), echt räumt; Kopier-Rückfall ohne harte Verweise lässt keine `.teil`-Datei zurück. Die
  Wettlaufprobe der Prüfung (`proben/wettlauf_probe.py`) liefert nach der Änderung in beiden Fällen „Datei vorhanden:
  True“, Fall A Abruf 200, Fall B gespeichert mit 2 Zeilen.
- **Bitte bestätigen**: (1) Beim Import wird eine fehlende Datei nachgelegt, bei der Variante gibt es 409 – beim Import
  ist das Archiv da, bei der Variante gäbe es nur die Quellzeile, deren Datei eben fehlt. (2) Das Aufräumen bei jedem
  Start (nicht nur beim ersten) – es kostet ein Verzeichnislisting und hasht nur Dateien ohne Zeile.

## Herstellerdokumente einmal je Inhalt (Schritt 18, 22.10.2026)

Anlass: Der Katalogimport der Karabiner-Lieferung (472 Produkte, 320 verschiedene PDF, 1240 Verweise Produkt ↔ Dokument)
hätte 1240 Dateien mit 1,9 GB auf den VPS geschrieben – die Gebrauchsanleitung von Kong 115-mal, weil jede hochgeladene
oder importierte Dokumentdatei einen Zufallsnamen bekam und je Dokumentzeile einmal abgelegt wurde (`produkt_variante`
kopierte sie sogar eigens, damit das Löschen des einen Produkts die Dokumente des anderen nicht mitnahm). Entscheidung des
Nutzers vom 22.10.2026: „Ja“ zum Zusammenführen gleicher Dokumentdateien.

### Entwurf

- **Dateiname = Inhalt** (`katalog._datei_ablegen`, `inhaltsname`): Eine Dokumentdatei liegt unter
  `media/material/dok/<SHA-256><Endung>`. Hochladen und Import schreiben in eine Zwischendatei im selben Ordner (Name mit
  Punkt davor – die Medienroute liefert so etwas nie aus, `_name_ok`), zählen und hashen dabei und bringen sie dann per
  `os.replace` auf den Inhaltsnamen. Liegt der schon da, ist es derselbe Inhalt: Die Zwischendatei geht weg, die vorhandene
  gilt (`_einordnen`); zwei gleichzeitige Uploads desselben Inhalts gelingen so beide. Stimmt die Größe der vorhandenen
  Datei nicht (abgebrochene Kopie), ersetzt die eben geprüfte sie mit Vermerk im Log. Endungs-Whitelist, Kennbytes und die
  50-MB-Grenze bleiben, wie sie waren. Varianten nennen dieselbe Datei – `_datei_kopieren` ist weg.
- **Löschen nur ohne Verweis** (`katalog._datei_freigeben`, die eine Stelle für alle): Produkt löschen, Kategorie löschen,
  gescheiterter Upload, Rollback und Aufräumen im Importer (`importer._wegraeumen`) gehen alle hier durch – die Datei
  verschwindet nur, wenn **keine** Zeile von `mat_product_document` sie mehr nennt (Abfrage über den neuen Index). Die
  Regel aus Phase 1/P2, dass ein Dokument aus einem festgeschriebenen Protokoll seine Zeile nie verliert
  (`kategorie_loeschen` → 409 „steht in Prüfprotokollen“; `produkt_loeschen` scheitert an den Artikeln), hält damit auch
  seine Datei: Solange die Zeile steht, wird die Datei nicht angerührt. Kein `os.remove` auf eine Dokumentdatei außerhalb
  dieses Helfers (`_entfernen` nur noch für Zwischendateien). Eine zweite Tabelle mit Dokumentdateien gibt es nicht –
  `models.py` Zeile ~639 ist die Fassung derselben Tabelle aus Schritt 3; `mat_inspection_attachment` (Prüfanhänge unter
  `media/material/anhang`) ist ein anderer Ordner mit eigener Ablage (`anhang.py`) und bleibt unberührt.
- **Auslieferung** `/media/material/dok/<name>` unverändert (die Rechteprüfung `medien.darf_datei` fragt nach der Zeile
  mit diesem `file_path`; `darf_datei_psa` lässt eine gemeinsame Datei jedem sehen, der eines der Produkte sieht, die sie
  nennen – richtig so). Export/Import unverändert: Der Katalog-Export benannte seine Dateien schon nach der Prüfsumme;
  der Import legt denselben Inhalt nur einmal ab, egal wie viele Produkte ihn nennen, und ein Inhalt, der hier schon
  liegt, wird nicht noch einmal geschrieben. Oberfläche ohne Änderung.

### Migration (Schritt 18, Schemaversion 18)

- **Der Schemaschritt selbst ist klein**: Index `idx_mat_document_file` auf `mat_product_document(file_path)` (für die
  Auslieferung und das Freigeben) und das Kennzeichen `mat_meta.dok_inhalt = "0"`. Die Dateiarbeit steht **nicht** in
  der Schematransaktion: Die läuft mit abgeschalteten Fremdschlüsseln, alle Schritte eines Starts in einer Transaktion,
  und ein Dateisystem lässt sich nicht mit zurückrollen – hätte ein späterer Fehler die Transaktion verworfen, hießen die
  Dateien neu und die Zeilen alt. Deshalb macht sie `services/dokablage.beim_start`, gleich nach `models.migrieren` im
  selben Start (angemeldet in `db.SCHEMA_MODULE`, wie `durchsichtige_bilder_reparieren` und `verwaiste_beiseite`), in
  eigener Transaktion unter der Schreibsperre (nur ein Arbeitsprozess tut es; die anderen finden das Kennzeichen „1“).
- **Ablauf je alter Datei**: SHA-256 aus der Datei gerechnet (die Datenbank hat bei älteren Zeilen keine oder eine
  fremde), Zielname `<sha><ext>`; gibt es ihn noch nicht, entsteht er als **harter Verweis** (Kopie über Zwischendatei,
  wo das Dateisystem keine Verweise kann), sonst ist die alte Datei eine Dublette (Größe geprüft; bei Abweichung ersetzt
  die geprüfte Datei den Zielnamen mit Warnung). Alle Zeilen mit dem alten Namen bekommen den neuen samt Prüfsumme und
  Größe aus der Datei; Zeilen, die schon den Inhaltsnamen tragen, nur die Berichtigung von Prüfsumme/Größe. **Commit,
  dann** verschwinden die alten Namen. Ein Abbruch dazwischen lässt beide Namen stehen, und der nächste Lauf findet die
  alte Datei wieder vor – nichts geht verloren, nichts passiert zweimal; ein zweiter Lauf ändert nichts.
- **Fehlt die Datei einer Zeile**, behält die Zeile ihren Namen und steht als Warnung im Log (`Dokumentdatei fehlt unter
  media/material/dok: <name> (Dokument <id> „<Titel>“)`); das Kennzeichen wird trotzdem gesetzt – der Rest ist erledigt.
- **Sind die Medien beim Start nicht erreichbar** (kein Ordner `media/material/dok`, aber Zeilen mit Datei), geschieht
  nichts Destruktives, die Anwendung startet, das Log warnt (`media/material/dok ist nicht erreichbar – die
  Zusammenführung … wartet auf den nächsten Start`), das Kennzeichen bleibt „0“ und der nächste Start (oder die
  Kommandozeile) holt es nach. Eine frische Datenbank ohne Dokumente setzt das Kennzeichen sofort.
- **Kommandozeile** `flask --app "app:create_app()" material dok-zusammenfuehren [--probe]`: derselbe Lauf von Hand, mit
  Bericht (Dokumente mit Datei, Dateien und MB vorher/nachher, frei, umbenannt, Dubletten, berichtigte Prüfsummen, Zeilen
  umgeschrieben, fehlende Dateien als `ACHTUNG`); `--probe` rechnet nur. Exit 0; 1, wenn Dateien fehlen; 2, wenn der
  Ordner nicht erreichbar ist. Läuft auch, wenn das Kennzeichen schon gesetzt ist (dann ohne Änderung).
- **Rückweg**: Eine Fassung mit Schemaversion 17 liest die Inhaltsnamen anstandslos (sie stehen in `file_path` wie
  jeder andere Name), legt Neues aber wieder unter Zufallsnamen ab und löscht beim Produktlöschen ohne Verweisprüfung –
  eine gemeinsame Datei verschwände dann für die anderen Dokumente. Nach einem Rückweg also keine Produkte mit
  Dokumenten löschen, oder den Katalog vorher exportieren.
- Wer `mat_product_document` künftig neu aufbaut, muss den Index neu anlegen (Hinweis in `models.py`).

### Kong-Teil, echt gemessen

Import von `katalog-karabiner-teil03.zip` (Kong, 89 Produkte, 27 MB ZIP) über `material import-catalog` in einen frischen
Datenordner (`python3 -I`): Probelauf → 0 Dateien unter `media/material/dok`; echter Lauf → **178 Dokumentzeilen, 34
Dateien, 20 602 515 Bytes (19,6 MiB)**. Bisheriges Verhalten (eine Datei je Verweis, aus `katalog.json` gerechnet): 178
Dateien, 296 575 667 Bytes (282,8 MiB) – die Kong-Anleitung 89-mal. `dok-zusammenfuehren --probe` findet danach nichts
mehr zu tun; `dok_inhalt` = 1, Schemaversion 18. Hochgerechnet auf die ganze Lieferung (1240 Verweise, 320 PDF): 320
Dateien statt 1240.

### Tests

`tests/test_material_dokumente.py` (neu, läuft in `st-test` mit): dasselbe PDF an zwei Produkten → eine Datei, zwei
Zeilen; Variante ohne Kopie; Produkt löschen lässt die Datei, solange ein anderes sie nennt, mit der letzten Zeile ist
sie weg; keine Zwischendatei bleibt liegen; Upload an ein unbekanntes Produkt legt nichts ab. Neue Version lässt die alte
Datei liegen, auch nach Löschen des zweiten Produkts. Dokument aus einem festgeschriebenen Protokoll: Kategorie nicht
löschbar (409), Datei bleibt – auch nachdem das Produkt mit derselben Datei gelöscht ist. Katalogimport Format 2: ein
PDF für drei Produkte → eine Datei; Verweis auf einen hier schon liegenden Inhalt legt nichts Neues ab; Probelauf ohne
Datei; späterer Fehler im zweiten Durchgang (Formularteil ausgehebelt) → Rollback ohne neue Datei und ohne Verlust der
vorhandenen, Zeilen wie vorher; danach geht derselbe Import durch. Migration 17 → 18 auf einem Datenordner mit
Altbestand (drei Kopien eines PDF unter Zufallsnamen mit leerer, falscher und richtiger Prüfsumme, ein zweites PDF mit
falscher Prüfsumme, eine Zeile ohne Datei, ein Link): eine Datei je Inhalt, Zeilen umgeschrieben, Warnung für die
fehlende Datei, Info-Zeile im Log, Index da, zweiter Lauf (Start und von Hand) ohne Änderung, Auslieferung und Export mit
den neuen Namen. Medien beim Start nicht erreichbar: Kennzeichen „0“, Warnung, nichts angelegt; `dok-zusammenfuehren
--probe` (Exit 2) und nach dem Zurückhängen `--probe` (rechnet, ändert nichts, Exit 1 wegen der fehlenden Datei) und echt
(zusammengeführt, Kennzeichen „1“, nächster Start still). 7 → 18 aus `MATERIAL_KOPIE_STAND_7`, wenn gesetzt (hier
nicht). Angepasst: `test_material.py::test_produkt_variante` (dieselbe Datei statt Kopie; Löschen der Variante lässt sie
beim Original); `test_material_meine_psa.py::test_medien` (jedes Testdokument mit eigenem Inhalt – mit demselben PDF
überall wäre die gemeinsame Datei über die erlaubte Gebrauchsanleitung zu Recht sichtbar gewesen; dieser Fall wird jetzt
ausdrücklich geprüft); `test_material_antrag.py::test_migration_17` (Endversion statt „17“). Ganze Suite, `st-py`,
`st-js`, `st-css`: siehe Bericht.

### Bitte bestätigen

1. **Löschregel**: Eine Dokumentdatei verschwindet erst, wenn **keine** Zeile von `mat_product_document` sie mehr nennt –
   auch keine alte Version, kein zurückgezogenes Dokument, kein Dokument eines anderen Produkts. Dateien ohne Zeile
   zählt seit der Nachbesserung vom 22.10.2026 jeder Start und jeder Lauf von `dok-zusammenfuehren` („Dateien ohne
   Zeile: n (x MB)“); entfernt werden davon nur die, deren Inhalt unter seinem Inhaltsnamen liegt und von einer Zeile
   genannt wird (alte Namen aus einem Abbruch der Zusammenführung nach dem Commit) – alle anderen bleiben liegen und
   stehen als Warnung im Log (siehe „Nachbesserung zu Schritt 18“, Befund 2).
2. **Fehlende Datei**: Die Zeile behält ihren alten Namen, steht als Warnung im Log und die Zusammenführung gilt trotzdem
   als erledigt (Kennzeichen „1“). Alternative wäre, das Kennzeichen offen zu lassen und bei jedem Start zu warnen.
3. **Automatisch und von Hand**: Die Zusammenführung läuft beim ersten Start nach dem Update von selbst (keine
   Wartung nötig); `material dok-zusammenfuehren [--probe]` ist nur Bericht und Nachholen, kein Pflichtschritt.
4. **Prüfsumme berichtigt**: Stimmt die gespeicherte Prüfsumme oder Größe einer Zeile nicht mit der Datei überein, wird
   sie aus der Datei berichtigt. Ein Protokoll, das die alte (falsche) Prüfsumme in `documents_json` trägt, bleibt
   unverändert – es ist festgeschrieben.
5. **Beschädigter Inhaltsname**: Liegt unter einem Inhaltsnamen eine Datei anderer Größe, ersetzt die eben geprüfte sie
   (Upload wie Zusammenführung) mit Warnung im Log statt abzubrechen.
6. **Restfenster** – *geschlossen mit der Nachbesserung vom 22.10.2026 (Befund 1)*: Löschen des letzten Produkts mit
   einer Datei und Anlegen einer Zeile mit demselben Inhalt entscheiden jetzt unter derselben Schreibsperre.
   `_datei_freigeben` fragt und entfernt in `BEGIN IMMEDIATE`; das Hochladen ordnet die Datei erst in der Transaktion
   der Zeile ein, der Katalogimport prüft beim Schreiben jeder Zeile, ob die vorab abgelegte Datei noch liegt, und legt
   sie sonst aus dem Archiv nach; die Variante bricht mit 409 ab, wenn die Datei des Quelldokuments fehlt. Vorher lag
   zwischen „Datei liegt schon“ und der Zeile ein Fenster – beim Hochladen Millisekunden, beim Katalogimport die ganze
   Ablage- und Schreibphase (bei der Karabiner-Lieferung Minuten); die Formulierung „dieselbe Millisekunde“ war falsch.

**Alle sechs Punkte bestätigt am 22.10.2026**, dazu die Entscheidungen der Nachbesserung: Der Import legt eine fehlende
Datei aus dem Archiv nach, die Variante bricht mit 409 ab; das Aufräumen (Dateien ohne Zeile, Zwischendateien) läuft bei
jedem Start; nicht umgesetzt bleiben die beiden Vorschläge der Prüfung, bei jedem Start erneut zu warnen, solange eine
Datei fehlt (Nr. 2), und beim Ablegen eine vorhandene gleichnamige Datei zusätzlich zu hashen statt nur die Größe zu
vergleichen (Nr. 5) – beides als entbehrlich bestätigt.

## Artikelseite: offene Änderungsanträge rechts neben dem Steckbrief (22.10.2026)

Wunsch vom 22.10.2026: „Die ausstehenden Anträge sollen, zumindest am Desktop rechts, neben dem Steckbrief in dem
leeren Bereich stehen.“ Die grauen Hinweiskästen der offenen Änderungsanträge (mit „Antrag zurückziehen …“ für den
eigenen) standen links unter der Stammdatenliste. Jetzt bilden sie einen eigenen Abschnitt **„Offene Änderungsanträge“**
am Anfang der rechten Spalte – über „QR-Code und NFC“ und „Herstellerdokumente“, auf gleicher Höhe mit „Stammdaten“, nur
wenn es offene Anträge gibt. Der Knopf „Änderung beantragen …“ mit seiner Hilfe bleibt links bei den Stammdaten, der
Hinweis im Dialog „Bearbeiten“ unverändert; Knöpfe, Rückfrage und Schnittstelle sind dieselben. Die rechte Spalte liegt
dafür in einem Kasten (`.mat-spalte`), damit die beiden Abschnitte ein Gitterfeld bleiben. Nur `material.js`,
`material.css` – keine Schnittstelle, kein Schema.

- **Telefon und Tablet (eine Spalte unter 900 px).** Die rechte Spalte folgt im Dokument auf die linke; die Anträge
  stehen also direkt nach den Stammdaten und vor QR-Code und Dokumenten – dieselbe Lesefolge wie am Rechner (links
  oben → rechts oben), ohne CSS `order` (Tab- und Vorlesereihenfolge = Bildfolge). Browserprobe mit `st-geraete`
  (iPhone, Tablet hoch/quer, Laptop 1280, Desktop QHD × Chromium, Firefox, WebKit, zwei offene Anträge am geprüften
  Artikel): 15 × OK, keine Befunde; Fotos unter `/home/harness/geraete-laeufe/antraege-rechts-20261022/lauf/`.
- **Bitte bestätigen:** Der Abschnitt steht **über** „QR-Code und NFC“ (die Anträge sind das Dringende, QR und
  Dokumente ändern sich nie). Alternative wäre unter „Herstellerdokumente“ – dann stünden sie am Rechner nicht neben dem
  Steckbrief, sondern darunter rechts.

## Zweite Nachbesserung nach der Geräte-Prüfung (22.10.2026)

Eine unabhängige Prüfung von f085f12 im Browser (`st-geraete`, 20 Seiten × 21 Geräte × 3 Engines, dazu Trefferproben
mit `elementFromPoint`; `/home/harness/geraete-laeufe/pruefung-f085f12/bericht.txt`) fand sechs Befunde und neun
Verbesserungen im Modul. Nur Oberfläche (`material.js`, `material.css`, `seite.html`) – keine Schnittstelle, kein
Schema, keine Migration. Berührungsregeln nur bei `(pointer: coarse)`; mit der Maus ändern sich nur Filterknöpfe,
Seitenbreite ab 1600 px und Hinweiskästen.

### Befunde

1. **Sortierköpfe überlappten (neu durch f085f12).** In der engen Tabelle (601–820 px) stehen zwei Köpfe übereinander
   („Inventar-Nr.“ über „Seriennummer“); mit `margin-block: -12.5px` überlappten sie um 25 px – der obere behielt 18 px
   wirksame Höhe, sein Fokusring umschloss den unteren. Jetzt ist jeder Sortierknopf am Finger ein eigener 44 px hoher
   Streifen über die Spaltenbreite, die Kopfzelle (`th[aria-sort]`) verliert dafür ihr senkrechtes Polster: ein Kopf
   44 px, zwei 88 px. Die Knöpfe liegen über der vergrößerten Fläche des Links in der ersten Zeile. Der Klappknopf der
   Fälligkeiten reicht nicht mehr 6 px über den Ordnerlink (nur noch nach links ins leere Polster); bricht ein langer
   Ordnername um, beginnt die zweite Zeile hinter dem Knopf (hängender Einzug) statt unter ihm. Nachgemessen mit
   `elementFromPoint` (Tablet hoch, iPhone, Tablet quer): Sortierköpfe, Klappknöpfe, Filter, Durchgangslink und
   Ordnerleiste zu 100 % ihrer 44 px wirksam, keine Überlappung zweier Bedienelemente.
2. **Prüfformular am Telefon in Firefox** rollte waagerecht, „aussondern“ wurde abgeschnitten: Die Ergebnisknöpfe
   brechen jetzt in eine zweite Reihe um (`.mat-ergebnis { flex-wrap: wrap }`), statt die Seite zu verbreitern.
3. **„Fälligkeiten je Ordner“ bei tiefer Verschachtelung** zu breit (Firefox, Fold, Tablet quer): Eingerückt wird bis
   Tiefe 3 um 22 px je Ebene, darunter um 8 px (in der Karte 14/6 px); die Spaltenköpfe der Zähler dürfen umbrechen,
   wenn die Tabelle sonst nicht passt.
4. **Ordnerleiste (240 px) bei tiefen Bäumen** brach Zeichen für Zeichen um („Fac/h/Per/sönl/iche …“): Ab Tiefe 3 rückt
   jede Ebene nur noch 8 px ein; der 44 px breite Klappknopf reicht nach links in die leere Einrückung (sein Dreieck
   steht rechts darin) und nimmt dem Namen 30 statt 44 px. Namen brechen nur an Wortgrenzen um; ein Wort, das allein
   nicht passt, endet mit „…“ (voller Name im `title`).
5. **Tippflächen unter 44 px** auf Seiten, die der erste Nachbesserungslauf nicht enthielt: Prüfdurchgang in der Liste
   (Übersicht, Prüfungen) und die Prüfsumme zum Kopieren (Prüfung ansehen) haben jetzt eine echte Fläche statt
   `::after`; alle Eingabefelder, Auswahllisten und Textfelder in Modul und Dialogen sind am Finger 44 px hoch
   (Artikel anlegen, Formular-Editor, Anhänge); die Pfeil- und Entfernen-Knöpfe im Formular-Editor 44 px breit.
6. **Stammdaten der Prüfung** („… von pruefer3@…“) ragten in Firefox 18 px heraus: Werte brechen notfalls im Wort um.

Dazu beim Nachmessen gefunden: Die volle Artikeltabelle im Ordner ragte zwischen 821 und 900 px Inhaltsbreite (Fold
aufgeklappt, Fold Duo) um 3–8 px über den Rand. „Eingangs­prüfung“ in der Spalte „Nächste Prüfung“ und der Kopf
„Serien­nummer“ tragen jetzt eine weiche Trennstelle.

### Verbesserungen

- **Nullkacheln (V1):** Die Kacheln mit 0 stehen jetzt **in jeder Breite und schon im Dokument** hinter denen mit einer
  Zahl (`dashboard()`), nicht mehr per CSS `order` nur am Telefon – Tab- und Vorlesereihenfolge entsprechen der
  sichtbaren. Am Rechner ändert sich damit die Reihenfolge mit dem Bestand (Beispiel: 22 Bestand, 20 neu,
  2 einsatzbereit, dann die Nullen); „Artikel im Bestand“ bleibt vorn. Am Telefon bleiben die Nullen einzeilig.
- **Filterknöpfe (V2):** wachsen nicht mehr mit (`flex: 0 0 auto`, auch „Produktmeldungen/Änderungsanträge“) – jetzt
  wirklich so breit wie ihr Wort.
- **Breite Bildschirme (V3):** Listen und Übersichten wachsen ab 1600 px Fenster nur noch bis 1800 px (vorher 2200);
  Prüfung beginnen, ausfüllen und ansehen, Artikel anlegen und der Formular-Editor bleiben bei 1180 px. Die Übersicht
  steht dafür schon ab 1500 px Inhaltsbreite zweispaltig (bei 1920 px Fenster also auch).
- **Hinweiskästen (V5):** alle gleich breit, `p` wie `div`, klein wie groß: Token `--mat-kastenmass: 38rem` (608 px).
- **Kontrast (V6):** „Ändern …“ in der Wiki-Zeile des Formular-Editors (4,40:1) und Knopf-Links in Hinweisen im
  dunklen Rot (`--rot-auf-flaeche`). Hinweis Kontrast im Modul danach: 0.
- **Artikelnummern (V7):** „GS-S“ bricht nicht mehr am Strich: Die leise Artikelnummer hinter dem Namen steht an allen
  Stellen als ein Stück (`artNrKurz`, `.mat-ganz` wie bei „Art.-Nr. …“) – Listen, Katalog, Treffer, Meldungen, Dialoge.
- **Brotkrumen (V8):** am Finger eine umbrechende Reihe mit 6 px Abstand, jeder Link 44 px hoch, ein langer bricht in
  sich mit normalem Zeilenabstand um (vorher `line-height: 44px`, das bei Umbruch wie ein Absatz aussah).
- **Platzhalter (V9):** Nummernsuche „Nummer suchen“ (die drei Nummernarten stehen in Beschriftung und `title`); die
  Katalogsuche wechselt ihren Platzhalter auch nach dem Drehen des Geräts (`matchMedia`-Listener).

### Tests

`tests/test_material_l5.py::test_geraete_nachbesserung_zwei` (statisch, alle Punkte oben); angepasst:
`test_geraete_nachbesserung` (Sortierköpfe, Brotkrumen, Filter, Breite, Lesemaß) und
`tests/test_material_beschreibung.py::test_oberflaeche_statisch` (Artikelnummer über `artNrKurz`).

### Im Browser geprüft

`st-geraete` mit den 20 Seiten der Prüfung plus Prüfformular (`/material/pruefung/5`), Artikel 3 und den tiefen
Ordnern 5, 7, 9, 10 (26 Seiten × 21 Geräte × 3 Engines = 1638 Aufrufe), gegen eine Kopie des Platzhalterbestands
mit den Platzhalterdaten der Prüfung (Durchgang, Meldung, Kommentare, tiefe Ordner, angefangene Prüfung), Server ohne
Mailserver: vorher (f085f12) `/home/harness/geraete-laeufe/nachbesserung2-20261022/lauf-vorher/`, nachher
`…/lauf-nachher/`.

| Vorkommen | Modul vorher | Modul nachher | Wiki/Admin (unverändert, außerhalb des Auftrags) |
| --- | --- | --- | --- |
| T – Tippflächen unter 44 px | 784 | 0 | 5040 (Wiki 1722, Admin 3318) |
| H – waagerechter Bildlauf | 5 | 0 | 2 (Admin) |
| A – Element außerhalb des Fensters | 5 | 0 | 51 (Wiki 21, Admin 30) |
| U, F, K, X | 0 | 0 | 0 |
| Hinweis Kontrast unter 4,5:1 | 63 | 0 | – |

B2, B3 und B6 zeigten sich in diesem Lauf nicht (Firefox wählt hier eine schmalere Ersatzschrift als in der Prüfung);
nachgestellt mit erzwungener „DejaVu Sans“ in Firefox: vorher 383 px bei 360 px Fenster (Prüfformular), 963/1199 px
(Übersicht, Fold/Tablet quer), 1026 px (Prüfung ansehen) – nachher überall genau Fensterbreite. Fotos angesehen:
Tablet hoch (Durchgang, Prüfungen – gestapelte Köpfe), Tablet quer (Ordnerleiste bei Tiefe 6, Chromium und Firefox),
iPhone Firefox (Prüfformular), Superwide (Prüfformular 1180 px), Fold mit breiter Schrift (Ergebnisknöpfe in zwei
Reihen).

### Bitte bestätigen

1. **Nullkacheln überall hinten** (statt nur am Telefon): eine Reihenfolge für alle Breiten, dafür wandern die Kacheln
   am Rechner mit dem Bestand. **Bestätigt am 22.10.2026.**
2. **Gestapelte Sortierköpfe** in der engen Tabelle sind jetzt 88 px (im Durchgang mit drei Köpfen 132 px) hoch.
   **Bestätigt am 22.10.2026.**
3. **Ordnerleiste:** Silbentrennung entfällt dort am Finger (nur noch Wortgrenzen, sonst „…“). **Bestätigt am 22.10.2026.**
4. **Breiten:** Tabellen bis 1800 px, Formularseiten 1180 px; Übersicht zweispaltig schon ab 1500 px Inhaltsbreite.
   **Bestätigt am 22.10.2026**, mit einer Nachjustierung: Der Nutzer bemängelte den Versatz der beiden Spalten – der
   Absatz „Die Zahlen gelten für den ganzen Zweig …“ stand über der Tabelle „Fälligkeiten je Ordner“, deren Kopf
   dadurch rund 100 px tiefer begann als der von „Als Nächstes zu prüfen“. Die Erklärung steht jetzt in allen Breiten
   **unter** der Tabelle (`ordnerUebersichtHtml`, material.js); beide Tabellen beginnen direkt unter ihrer Überschrift
   auf gleicher Höhe. Geprüft mit `st-geraete` (Chromium, iPhone, Laptop 1280, Desktop QHD, Superwide): keine Befunde,
   Fotos unter /home/harness/geraete-nachjustierung/lauf/. Außerdem bestätigt am 22.10.2026: Hinweiskästen einheitlich
   38rem, dunkles Rot app-weit, Schloss grau und Name fett, Ordnerleiste ab Tiefe 3 mit kleinerem Einzug, Platzhalter
   „Nummer suchen“ (die Punkte der ersten Nachbesserung unten).

## Nachbesserung nach der Geräte-Prüfung (21.10.2026)

Der erste Lauf von `st-geraete` (Chromium, Firefox, WebKit × 21 Geräte von 344 bis 5120 px × Übersicht, Bestand,
Ordner, Katalog; `/home/harness/geraete-laeufe/probelauf-20261021/`) fand zwei Befunde und eine Reihe von
Verbesserungen. Wunsch: „Behebe die Befunde und die Verbesserungen.“ Nur Oberfläche (`material.js`, `material.css`,
dazu `app.css` für die Bauchbinde und zwei Farbregeln) – keine Schnittstelle, kein Schema, keine Migration.

### Befunde

1. **„neu (Eingangsprüfung)“ ragte aus seiner Kachel** (Tablet quer, Laptop 1280; Firefox auch 1366/1440 und
   Fold zugeklappt): Das Wort „(Eingangsprüfung)“ war breiter als eine von sieben Kacheln. Es trägt jetzt eine weiche
   Trennstelle („Eingangs-/prüfung“), die Kachelbeschriftung bricht notfalls auch im Wort um (`overflow-wrap`).
2. **Tippflächen unter 44 px am Finger.** Lieferung 5 hatte viele Ziele nur mit einem unsichtbaren `::after`
   vergrößert – das zählt weder für die Messung noch für jede Vorlesehilfe als Fläche des Elements. Jetzt hat das
   Bedienelement selbst 44 px, nur bei `(pointer: coarse)`, am Rechner bleibt alles wie es war:
   - Sortierköpfe (`button.mat-sort`, 19 px hoch): `min-height: 44px` mit negativem Rand – die Kopfzeile bleibt so
     niedrig wie bisher;
   - Klappknöpfe der Fälligkeiten (`.mat-ue-klapp`, 32 × 32): 44 × 44, negativer Rand hält Einrückung und Zeilenhöhe;
   - Zähler in den Fälligkeiten (`a.mat-zahl`) und das Datum „nächste Fälligkeit“ (`.mat-ue-tag a`): durchsichtiger
     Rahmen mit `background-clip: padding-box` – die farbige Pille bleibt so groß wie bisher (in der Karte 26 px hoch,
     in der Tabelle 17 px), die Trefferfläche ist 44 px, negative Ränder halten die Zeile;
   - Textknöpfe `.lnk` im Modul und in Dialogen („Probelauf ansehen“): mindestens 44 px hoch;
   - Brotkrumen über dem Ordner („Bestand“): Zeilenhöhe 44 px, jeder Link so hoch wie seine Zeile (bricht als Ganzes
     um – vorher 31 px mit Polster);
   - Suchfeld im Katalog (`#kat-q`, 36–37 px): 44 px;
   - Bauchbinde: kurze Punkte („Wiki“, 40 px breit am Telefon) mindestens 44 px breit (`app.css`, nur direkte
     Punkte der Leiste – im Menü „Mehr“ bleiben sie linksbündig);
   - feste Ordner- und Kategorienleiste: Einträge 44 statt 43 px hoch, Klappknöpfe 44 statt 34 px breit, die
     Überschrift „Ordner“/„Kategorien“ (17 px) als 44 px hohe Fläche.
   Die `::after`-Vergrößerung bleibt nur für Textlinks in Listen (Inventar-Nr., Ordnernamen), die die Messung als
   Links im Text ausnimmt (WCAG 2.5.8); für die Zähler in der Karte deckt sie weiter die ganze Zelle samt
   Beschriftung ab.

### Verbesserungen

- **Kontrast (WCAG AA):** Rot auf dem grauen Hinweiskasten (4,40:1) und auf dem hellroten gewählten Filter „alle“
  (4,22:1) lagen unter 4,5:1. Neues Token `--rot-auf-flaeche` (= `--rot-dunkel`, über 6:1) in `app.css` für Rot als
  Schrift auf hellem Grund: Links in `.notice`, gewählter Reiter `.c-tabs button.sel` (app-weit, auch Kommentare im
  Wiki) und Links in Entwurfszeilen des Lebenslaufs (hellblau, 4,32:1 – beim Nachprüfen gefunden).
- **Legende im Bestand:** Statt „farbig: überfällig, …“ stehen die fünf Zähler selbst in der Legende, jeder mit
  seinem Wort statt der Zahl, in der Reihenfolge wie hinter den Ordnern – auch das Blau für „neu (Eingangsprüfung
  offen)“, das vorher fehlte. Die Farbe ist so nicht das einzige Merkmal.
- **Ordner:**
  - Liegt im Ordner selbst nichts (nach den Zahlen, die die Seite ohnehin hat: `direkt` und `zaehlung`), entfallen
    die Statusfilter und „Zugeordnet an …“; ist ein Filter gesetzt, bleibt die Zeile, damit er sich zurücknehmen lässt.
  - Leerer Ordner mit Artikeln darunter: „Hier liegen keine Artikel direkt – 22 liegen in Unterordnern.“ (bzw. „1 liegt
    in einem Unterordner“), dahinter „Fällige Artikel im ganzen Zweig →“ (Prüfungen, nach dem Ordner gefiltert),
    sofern im Zweig etwas fällig ist. Gezählt werden alle Artikel des Zweigs, die das Konto sieht, ausgesonderte
    eingeschlossen – sie liegen ja dort.
  - Filterknöpfe so breit wie ihr Wort statt gleich breit: „bald fällig“ und „Lebensdauer erreicht“ brechen nicht mehr
    um, die Zeile ist gleich hoch; reicht sie nicht, rutscht der ganze Knopf weiter (alle Filterzeilen im Modul).
    *Korrektur (22.10.2026):* Das stimmte nur am Telefon – mit `flex: 1 1 auto` wuchsen die Knöpfe auf die ganze
    Zeile (am breiten Bildschirm bis 765 px). So breit wie ihr Wort sind sie erst seit der zweiten Nachbesserung.
- **Sehr breite Bildschirme:** Ab 1600 px Fenster wächst der Inhalt bis 2200 px statt bei 1180 px zu enden. Ab 1800 px
  Inhaltsbreite stehen auf der Übersicht „Fälligkeiten je Ordner“ und „Als Nächstes zu prüfen“ nebeneinander (2 : 3),
  „Meine PSA“ in drei Spalten. Fließtext bleibt beim Lesemaß (nächster Punkt). Laptop und kleiner: unverändert.
- **Lesemaß:** Token `--mat-lesemass: 38em` (rund 75 Zeichen) für Hilfetexte, Hinweise, Beschreibungen und kleine
  Absätze (`#mat-inhalt :is(p.help, p.notice, p.mat-text, p.small)`), dazu die Werte der Stammdaten (`.mat-daten dd`) – vorher `80ch`, das in der Hausschrift rund
  100 Zeichen waren. In em, damit kleine und große Schrift gleich viele Zeichen je Zeile haben.
- **Katalogsuche am Telefon:** bis 640 px der kürzere Platzhalter „Hersteller, Modell, Art.-Nr., Norm“ (der volle
  wurde abgeschnitten); der volle Text steht als Beschriftung (`aria-label`, `title`) – das Feld hatte vorher keine.
- **Produktnamen:** Kurze Wörter mit Bindestrich (bis 16 Zeichen, etwa „GS-S“, „HB-7“) stehen als ein Stück
  (`.mat-wort`, `nameHtml`) und brechen nicht mehr am Strich („GS-“ / „S“); längere behalten ihre Umbruchstelle,
  damit nichts aus einer schmalen Spalte ragt. *Korrektur (22.10.2026):* „GS-S“ in der Artikel- und Prüfliste ist
  die Artikelnummer, nicht der Name – sie brach weiter am Strich (rund zehn Stellen ohne `.mat-wort`). Behoben in der
  zweiten Nachbesserung.
- **Schloss der Systemordner:** „🔒 Gesperrt/Ausgesondert“ – das Schloss steht außerhalb der Unterstreichung (eigenes
  Element mit Rand statt Leerzeichen im Link) und grau wie die Klapp-Dreiecke daneben statt bunt; kein neues Zeichen
  (`schloss()` in Leiste, Bestand, Unterordnern, Fälligkeiten und Ordnertitel).
- **Bauchbinde:** Der eigene Name steht so kräftig wie „Profil“ dahinter (vorher normal neben fett).
- **Übersicht am Telefon:** Kacheln mit 0 rücken ans Ende und werden zu einer Zeile („0 gesperrt“, mindestens 44 px
  hoch, weiter antippbar, mit ihrer farbigen Kante) – nur, wo die Kacheln zu zweit stehen (unter 570 px
  Kachelbreite). Beim Platzhalterbestand am iPhone (vier Nullen) steht „Fälligkeiten je Ordner“ damit rund 70 px höher.

### Tests

`tests/test_material_l5.py::test_geraete_nachbesserung` (statisch: Token, Tippflächen ohne `::after`, Lesemaß,
Legende in der Reihenfolge von `zahlen()`, Filter und Leertext im Ordner, `.mat-wort`, Schloss, Katalogsuche,
Nullkacheln, breite Bildschirme). Angepasst: `tests/test_material_beschreibung.py::test_bemerkung_heisst_so` – der
volle Platzhalter der Katalogsuche steht jetzt in der Konstante `KAT_SUCHE` (dort weiter mit „Bemerkung“).

### Im Browser geprüft

`st-geraete` gegen eine Kopie des Platzhalterbestands aus dem Probelauf (lokaler Server ohne Mailserver), dieselben
vier Seiten, alle drei Engines und alle 21 Geräte: `/home/harness/geraete-laeufe/nachbesserung-20261021/`.

| | Probelauf | Nachbesserung |
| --- | --- | --- |
| Aufrufe mit Befund (Chromium / Firefox / WebKit, je 84) | 48 / 50 / 48 | 0 / 0 / 0 |
| T – Tippflächen unter 44 px (Vorkommen) | 926 | 0 |
| U – Text ragt aus dem Kasten | 9 | 0 |
| H, F, K, A, X | 0 | 0 |
| Hinweis Kontrast unter 4,5:1 | 2 Farbpaare (126 Vorkommen) | 0 |
| Hinweis Zeilen über 90 Zeichen | 3 Absätze (53) | 1 (21) – der Ordnerbaum im Bestand, keine Fließtextzeile |

*Korrektur (22.10.2026):* „0 Befunde“ gilt nur für diese vier Seiten. Die unabhängige Prüfung von f085f12 mit 20
Seiten (Prüfdurchgang, Prüfformular, Formular-Editor, Artikel anlegen, Meldungen, tiefere Ordner) fand im Modul weiter
Tippflächen unter 44 px, waagerechten Bildlauf in Firefox und – neu durch diese Nachbesserung – sich überlappende
Sortierköpfe in der engen Tabelle; siehe „Zweite Nachbesserung nach der Geräte-Prüfung“.

Fotos angesehen: iPhone (Übersicht ganz, Bestand mit Legende), Tablet quer (Übersicht, leerer Ordner mit
Unterordnern, Ordner mit Artikeln und Filtern), Laptop 1280 (Firefox), Superwide (Übersicht zweispaltig, Katalog). Dazu
Prüfungen, Artikel, Systemordner und Meldungen in Chromium bei 360, 390, 1180, 1280 und 5120 px: keine Befunde (der
Filterknopf „alle“ war dabei erst 36 px breit – jetzt mindestens 44 px).

### Bitte bestätigen

1. **Breite Bildschirme:** Inhalt bis 2200 px und ab 1800 px Inhaltsbreite die Übersicht zweispaltig (Fälligkeiten
   links, „Als Nächstes zu prüfen“ rechts). Bei 5120 px bleibt rechts und links trotzdem Rand – Tabellen über 4000 px
   wären schwerer zu lesen als mit Rand.
2. **Nullkacheln am Telefon:** ans Ende sortiert und einzeilig, statt sie ganz auszublenden oder zusammenzufassen –
   die Reihenfolge der Kacheln weicht am Telefon damit von der am Rechner ab.
3. **Lesemaß 38em** auch für Hinweiskästen (`p.notice`): Sie enden am Rechner jetzt bei gut 600 px statt über die
   ganze Breite zu gehen.
4. **Dunkles Rot** (`--rot-dunkel`) für Rot als Schrift auf grauem und hellrotem Grund, app-weit (auch der gewählte
   Reiter der Kommentare im Wiki).
5. **Schloss grau** (Graustufenfilter auf dem vorhandenen 🔒) statt bunt; der Name in der Bauchbinde fett wie
   „Profil“ (statt umgekehrt „Profil“ normal).
6. **Ordnerleiste am Finger:** Klappknöpfe 44 px breit – in der schmalen festen Leiste (Tablet quer, 240 px) bricht
   „Lager Musterstadt“ dadurch in zwei Zeilen um.

**Alle sechs Punkte bestätigt am 22.10.2026** – in der Fassung der zweiten Nachbesserung: Breiten 1800/1180 px und
zweispaltig ab 1500 px (Nr. 1), Nullkacheln in allen Breiten hinten statt per CSS `order` (Nr. 2), Ordnerleiste mit
kleinerem Einzug ab Tiefe 3 und Umbruch nur an Wortgrenzen (Nr. 6).

## Beispielbestand (18.10.2026)

Wunsch: ein umfangreicherer Bestand zum Testen auf dev – nur aus dem vorhandenen Katalog, der dabei unverändert bleibt,
damit er später sauber in die Produktion geht. Entschieden: mit Prüfhistorie (die benutzten Formularversionen gelten
danach als „benutzt“, der Bestand lässt sich nicht wieder entfernen – nur über eine zurückgesetzte dev-Datenbank). Nach
der Prüfung nachgetragen und **nicht Teil dieser Entscheidung**: Produkte mit Artikeln lassen sich danach nicht mehr
löschen und ihre Materialart nicht mehr ändern, ihre Kategorien nicht mehr löschen (Zu prüfen).

- **`scripts/material_beispielbestand.py --beispielbestand [--artikel N]`** – nur für dev, eine Datei außerhalb von
  `app/` (nicht im Abbild; im Container per stdin, README „Beispielbestand (nur dev)“), ohne Schalter Hilfe und
  Rückgabewert 2, mit `BASE_URL` der Produktion (`strömis.de`) Abbruch, einmalig (ein abgebrochener Lauf heißt
  beim nächsten „unvollständig“, Rückgabewert 1). Drei Gliederungen „DEMO-OG
  Auental“, „… Bachheim“, „… Flussstadt“ (Lager mit Regalen, GW-Wasserrettung mit zwei Seilrucksäcken, MTW, zwei
  Strömungsrettungsgruppen, persönliche Ordner), Vorgabe 200 Artikel über alle echten Produkte, je Artikel bis zu vier
  zurückdatierte Prüfungen über das aktive Formular des Katalogs im Abstand seines Intervalls und innerhalb seiner
  Lebensdauer – festgeschrieben, jede mit Protokoll; dazu Sperren mit Mangel (DEMO-Platzhalterfoto; fällt er zwischen
  zwei Prüfungen auf, als außerplanmäßige Prüfung wie der Vorschlag der App) und Freiprüfung, Verlust, Aussonderung
  aus der Prüfung und durch den Materialwart. Je Gliederung sechs DEMO-Konten (`@example.invalid`, zufälliges
  Passwort nur in der Ausgabe, nur Modul Material, `recht_material` = 1): Materialwart (verwalten), Prüferin (lesen
  und prüfen, beides dauerhaft), Mitglied (lesen), externer Prüfer (nur prüfen im Lager, 30 Tage – er prüft nur
  heute, die zurückdatierte Geschichte prüft die Prüferin), zwei Einsatzkräfte mit persönlichem Ordner und Zuordnungen (die erste
  liest ihren Ordner, die zweite hat wie die meisten PSA-Nutzer keinen Modulzugang und sieht „nicht freigeschaltet“; der
  Bericht sagt es an beiden Konten); ein heute abgeschlossener Durchgang mit Sammelprotokoll und ein offener (teils
  erledigt, einer in Prüfung, einer ausgenommen). Alle Zustände kommen vor. Keine Rückrufe, keine Meldungen. Alles über
  die Dienste, je Artikel eine Transaktion, Journal unter „Beispielbestand“.
- **Der Katalog bleibt, wie er ist.** Grundlage sind genau die Produkte, die der Katalog-Export mitnimmt (ohne
  DEMO-Kennzeichen, außerhalb von DEMO-Kategorien, mit Prüfintervall); Produkte ohne aktives Formular bekommen Artikel
  ohne Prüfung („neu“), der Bericht nennt sie. Fachliches kommt nur aus dem Katalog: Ja/Nein und Zahlen stehen auf ihrem
  Soll, ein Pflichtpunkt, dessen Wert nur eine echte Prüfung liefert (Messwert, Datum, Foto), auf „nicht zutreffend“
  mit „DEMO – nicht für echte Prüfungen“; erfunden sind nur Bestandsangaben (Ordner und Seriennummern „DEMO-…“,
  Herstell-, Kauf- und Erstgebrauchsdaten, Bemerkung „DEMO – nicht für echte Prüfungen“).
- **DEMO je Artikel statt nur je Produkt** (`bestand.demo_sql`, `ist_demo`, `demo_ordner_sql`, `ordner_ist_demo`): Bis
  hierher hing „DEMO“ an `mat_product.demo` – Protokolle echter Produkte im Beispielbestand wären von echten nicht zu
  unterscheiden gewesen. Jetzt ist ein Artikel DEMO, wenn sein Produkt das Kennzeichen trägt **oder seine Heimat
  (`bestand.heimat`) oder ein Ordner darüber ein DEMO-Ordner ist** – auch ein Ordner, den jemand ohne Kennzeichen in
  einer DEMO-Gliederung anlegt. Eine Regel als SQL-Ausdruck für Listen und Suche, Artikel (`demo` in der Antwort),
  Prüf- und Aussonderungsprotokoll, Lebenslauf, CSV (Artikel und `Verzeichnis.csv`) und Steckbrief; das
  Sammelprotokoll fragt den Ordner des Durchgangs samt Oberordnern. Das Banner an Artikel, Prüfformular und Prüfung
  folgt dem Artikel („Dieser Artikel gehört zu den Demodaten.“). Am Katalog und am Katalog-Export ändert das nichts.
  Weil die festgeschriebenen Protokolle den Stand ihrer Erstellung behalten, lässt sich zwischen DEMO-Gliederungen und
  echtem Bestand nichts verschieben, weder Artikel noch Ordner (409, `bestand.DEMO_GRENZE`) – auch nicht durch die
  Plattform-Verwaltung. In der Produktion gibt es keine DEMO-Ordner; dort greift die Regel nicht.
- Freigaben-Dialog: Freigaben des Beispielbestands stehen als „vergeben von Beispielbestand“ da (`freigaben.SYSTEM`).
- **Test** `tests/test_material_beispielbestand.py`: Testkatalog mit Platzhaltern, Schnappschuss aller Katalogtabellen,
  des Katalog-Exports (Format 2, ohne Zeitstempel, samt Dateien) und der Katalogdateien vor und nach dem Lauf
  (identisch); jeder Zustand, beide Wege der Aussonderung, Protokolle mit Prüfsumme, Durchgänge, Konten und Freigaben;
  DEMO an Artikel, Liste, Prüfung, Protokoll, Sammelprotokoll, Lebenslauf, CSV und Steckbrief – ein echter Artikel
  daneben bleibt ohne; zweiter Lauf ohne Wirkung; ohne Schalter 2, ohne echte Produkte 1. Nach der Prüfung dazu:
  Verschieben über die Grenze der Demodaten (409 in beide Richtungen, Artikel und Ordner), Sicht der beiden
  Einsatzkräfte, externer Prüfer nur heute, Hilfe und Bericht nennen die Folgen für die Katalogpflege.
- **Gemessen** (Sandbox, Platzhalterkatalog mit 16 Produkten in 10 Kategorien, 8 Formularen, zwei Produkte ohne
  Formular): Vorgabe 200 Artikel – 305 Prüf- und Aussonderungsprotokolle, 3 Sammelprotokolle, 2:33 min; 240 Artikel
  mit 385 Protokollen 3:17 min. Die Laufzeit hängt an den Protokollen (gut eine halbe Sekunde je PDF). Zustände bei
  200: 108 einsatzbereit, 16 bald fällig, 19 überfällig, 32 neu, 13 gesperrt (davon 4 verloren gemeldet), 5
  Lebensdauer erreicht, 7 ausgesondert. Katalog-Export vorher und nachher identisch; im Chromium bei 1280 und 390 px
  angesehen (Übersicht, Fälligkeiten, Artikel, Durchgänge, Protokoll mit DEMO-Kopf und -Kasten). Nach der Prüfung
  erneut gemessen: dieselben Mengen und Zustände, 2:30 min, Katalog-Export vorher und nachher identisch.

### Prüfung vor Auslieferung

Eine unabhängige Prüfung (Lauf auf einer Kopie mit Platzhalterkatalog; Katalogpflege, Verschieben und Anmeldung mit den
DEMO-Konten nachgestellt) hat vier Befunde gemeldet. Jeder ist vor der Behebung nachgestellt worden, alle vier sind
behoben; die Tests zu Nr. 2 und 4 scheitern ohne die Änderung. Danach liefen alle Suiten grün.

| # | Befund | Schwere | Umgang |
| --- | --- | --- | --- |
| 1 | Nach dem Lauf lässt sich auf dev kein Produkt mit DEMO-Artikeln mehr löschen und seine Materialart nicht mehr ändern, seine Kategorie nicht mehr löschen (je 409) – genannt waren nur „benutzte“ Formulare und der nicht entfernbare Bestand | mittel | README („Vorher“, Punkt 2), Docstring und Hilfe („Was danach gilt“) und Bericht („Jetzt mit Artikeln: n Produkte …“) nennen die Folge samt Ausweg: vorher pflegen oder später Export → dev zurücksetzen → Import. Vor dem Lauf zu bestätigen (Zu prüfen). Test: Hilfe, Bericht, 409 beim Löschen |
| 2 | „DEMO“ wechselte beim Verschieben: Ein echter Artikel in einer DEMO-Gliederung stand als DEMO da, sein echtes Protokoll in `Verzeichnis.csv` mit DEMO=ja; ein DEMO-Artikel in der echten Gliederung verlor Kennzeichen und Banner, seine DEMO-Protokolle standen mit DEMO=nein im Verzeichnis | mittel | `bestand.artikel_verschieben` und `ordner_verschieben` lehnen das mit 409 ab (`DEMO_GRENZE`), in beide Richtungen und auch für die Plattform-Verwaltung; innerhalb der Demodaten und im echten Bestand unverändert. Test `test_demo_grenze_beim_verschieben` |
| 3 | Die DEMO-Einsatzkräfte hatten keine Freigabe und damit keinen Modulzugang (403), der Bericht führte sie trotzdem wie die übrigen Konten mit Passwort | niedrig | Einsatzkraft 1 liest ihren persönlichen Ordner (mit mindestens einem ihr zugeordneten Artikel), Einsatzkraft 2 bleibt bewusst ohne Zugang wie die meisten PSA-Nutzer und sieht „nicht freigeschaltet“; Bericht und README sagen es an beiden. Test in `test_beispielbestand` |
| 4 | Der externe Prüfer (Prüffreigabe ab heute, 30 Tage) stand auf zurückdatierten Prüfungen bis 2024 | niedrig | Er prüft nur heute (offener Durchgang, heute geprüfte Lagerartikel, Sperre bei Verlust), die zurückdatierte Geschichte prüft allein die Prüferin. Test in `test_beispielbestand` |

### Zu prüfen

- **Vor dem Lauf auf dev bestätigen** (Prüfung Nr. 1, nicht Teil deiner Entscheidung): Jedes Produkt, von dem der
  Beispielbestand Artikel anlegt – bei 200 Artikeln meist alle echten mit Prüfintervall –, lässt sich danach nicht
  mehr löschen und seine Materialart nicht mehr ändern; seine Kategorie lässt sich nicht mehr löschen. Katalogpflege,
  die das braucht, vorher erledigen – oder später Katalog exportieren, dev-Datenbank zurücksetzen, Export importieren.
- Auf dev **vorher den Katalog exportieren** und das ZIP aufheben; dann der Befehl aus der README.
- Danach: Übersicht und Fälligkeiten, ein Protokoll (Kopf und Kasten „DEMO – nicht für echte Prüfungen“), die
  Durchgänge, als DEMO-Materialwart anmelden (Passwort aus der Ausgabe), als Einsatzkraft 1 (nur ihr persönlicher
  Ordner) und als Einsatzkraft 2 („nicht freigeschaltet“); im Katalog sind die benutzten Formulare jetzt nur noch über
  eine neue Version änderbar.

## Katalogdatei (Format 1)

Eine JSON-Datei, UTF-8. Kategorien werden über Namen an ihrer Stelle im Baum gefunden, Produkte über die
Dublette Hersteller + Modell + Artikelnummer; eine Artikelnummer, die schon ein anderes Produkt trägt, ist ein
Fehler. Was vorhanden ist, wird abgeglichen; ein Formular, dessen
Prüfpunkte sich geändert haben, wird eine neue Version. Ein Fehler irgendwo: nichts gespeichert, jeder Fehler
mit seiner Stelle (`produkte[3] (…): …`). `--trocken` prüft nur.

```json
{
  "format": "stroemis-material-katalog",
  "version": 1,
  "kategorien": [
    {"name": "PSA gegen Absturz und Seiltechnik", "unterkategorien": [
      {"name": "Gurte", "norm": "EN 361, EN 12277 oder EN 813", "materialart": "textil", "intervall_monate": 12}
    ]}
  ],
  "produkte": [
    {"kategorie": ["PSA gegen Absturz und Seiltechnik", "Gurte"], "hersteller": "Beispielwerk", "modell": "Beispielgurt",
     "artikelnummer": "BW-1", "norm": "EN 361", "materialart": "textil", "intervall_monate": 12,
     "lebensdauer_jahre": 10, "lebensdauer_quelle": "Gebrauchsanleitung, Kapitel …", "beschreibung": ""}
  ],
  "formulare": [
    {"kategorie": ["PSA gegen Absturz und Seiltechnik", "Gurte"], "titel": "Gurtprüfung", "aktivieren": true,
     "punkte": [
       {"gruppe": "Kennzeichnung", "text": "Beispiel-Prüfpunkt", "art": "yesno", "soll": "ja", "kritisch": true, "pflicht": true},
       {"gruppe": "Bemerkung", "text": "Beispiel-Freitext", "art": "text", "pflicht": false}
     ]},
    {"produkt": {"hersteller": "Beispielwerk", "modell": "Beispielgurt", "artikelnummer": "BW-1"},
     "titel": "Gurtprüfung Beispielgurt", "punkte": [{"text": "…", "art": "yesno", "soll": "nein"}]}
  ]
}
```

| Feld | Bedeutung |
| --- | --- |
| `kategorien[].name`, `unterkategorien` | Name an dieser Stelle; Unterkategorien beliebig tief |
| `norm` | Freitext, z. B. „EN 362 oder EN 12275“ |
| `beschreibung` | die **Bemerkung** des Produkts (so heißt das Feld in der Oberfläche seit dem 18.10.2026; der Schlüssel bleibt, der Export schreibt ihn): kurzer Zusatz hinter dem Modell, etwa die Verschlussart – angezeigt grau hinter dem Modell, ohne Strich („D Classic Screwlock“). Gleichwertig nimmt der Import den Schlüssel `bemerkung` an; stehen beide da, müssen sie gleich sein. Die Oberfläche nimmt höchstens 80 Zeichen in einer Zeile; der Import übernimmt auch längere und mehrzeilige (bis 4000 Zeichen) unverändert und nennt sie im Bericht |
| `materialart` | `textil`, `metall_hardware` oder `sonstiges` (an der Kategorie: Vorgabe für Produkte) |
| `intervall_monate` | Prüfintervall 1–120; am Produkt optional, wenn die Kategorie eins vorgibt |
| `artikel_laenge` (Kategorie) | `true`/`false`: „Artikel haben eine Länge“ – gilt für die Kategorie und alle Unterkategorien (Schritt 20); fehlt der Schlüssel, bleibt es, wie es ist (neu: `false`) |
| `lebensdauer_jahre` | 1–50; Produkt textil: Pflicht; Metall (`metall_hardware`): verboten; sonstiges: nur mit `lebensdauer_quelle`. An der Kategorie nur bei textil, nur als Vorschlag |
| `kategorie` | Pfad als Liste von Namen oder als Text „Ober / Unter“ |
| `formulare[].kategorie` / `.produkt` | generisch je Kategorie oder spezifisch je Produkt (Hersteller, Modell, Artikelnummer) |
| `aktivieren` | Standard `true`: die Version wird aktiv, eine ältere aktive des Ziels inaktiv |
| `punkte[].text` | der Prüfpunkt bzw. die Prüfanweisung, höchstens 1000 Zeichen |
| `punkte[].art` | `yesno`, `text`, `date`, `number`, `photo`, `signature`, `laenge` (Länge in Metern – vorbelegt mit der Artikellänge, kein Sollwert, nie kritisch; Schritt 20) |
| `punkte[].soll` | bei `yesno` Pflicht: `ja` oder `nein` (bei Schadensfragen `nein`); bei `text`/`number` optionaler Hinweis |
| `punkte[].kritisch` | nur bei `yesno`: ein Mangel daran schließt „einsatzbereit“ aus |
| `punkte[].pflicht` | Standard `true` |

Im Container liegt die Datei im Datenordner:
`docker compose exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material import-catalog /data/import/katalog.json --trocken`

## Katalogdatei (Format 2)

Ein ZIP-Archiv – so schreibt es der Katalog-Export – oder, ohne Dateien, eine reine JSON-Datei:

```
katalog.json                          die Katalogdatei, UTF-8
dateien/bilder/<sha256>.<endung>      Originale der Produktbilder
dateien/dokumente/<sha256>.<endung>   Herstellerdokumente (PDF, JPEG, PNG, WebP)
bericht.txt                           was drin ist und was ausgelassen wurde – nur zum Lesen
```

`katalog.json` ist Format 1 mit `"version": 2` und diesen Ergänzungen. Gelesen werden nur die Dateien, auf die
`katalog.json` verweist; ihre Namen sind frei, der Export benennt sie nach ihrer SHA-256. In einer reinen JSON-Datei
ist ein Verweis auf eine Datei (`bild`, `datei`) ein Fehler.

```json
{
  "format": "stroemis-material-katalog",
  "version": 2,
  "quelle": "https://dev.strömis.de",
  "erstellt": "2026-10-17T14:03:00+02:00",
  "kategorien": [
    {"uid": "5edccf185bb2feaa03ca064a23b676d6", "name": "PSA gegen Absturz und Seiltechnik", "norm": "",
     "materialart": null, "intervall_monate": null, "lebensdauer_jahre": null, "position": 0, "artikel_laenge": false,
     "unterkategorien": [
       {"uid": "fa0924f611f67a059a66fa70610d8495", "name": "Gurte", "norm": "EN 361, EN 12277 oder EN 813",
        "materialart": "textil", "intervall_monate": 12, "lebensdauer_jahre": null, "position": 0,
        "artikel_laenge": false,
        "dokumente": [
          {"art": "pflegehinweis", "titel": "Pflegehinweis Gurte", "version": "", "gueltig_ab": "2024-01-01",
           "datei": "dateien/dokumente/3b54….pdf"}
        ]}
     ]}
  ],
  "produkte": [
    {"uid": "517afaa09a333286eef21f40f0ec4021", "kategorie": ["PSA gegen Absturz und Seiltechnik", "Gurte"],
     "kategorie_uid": "fa0924f611f67a059a66fa70610d8495", "hersteller": "Beispielwerk", "modell": "Beispielgurt",
     "artikelnummer": "BW-1", "norm": "EN 361", "materialart": "textil", "intervall_monate": null,
     "lebensdauer_jahre": 10, "lebensdauer_quelle": "Gebrauchsanleitung, Kapitel …", "beschreibung": "",
     "bild": "dateien/bilder/c2f8….jpg",
     "dokumente": [
       {"art": "gebrauchsanleitung", "titel": "Gebrauchsanleitung", "version": "03/2024", "gueltig_ab": "2024-03-01",
        "datei": "dateien/dokumente/bcae….pdf",
        "vorgaenger": [{"sha256": "9f1c…"}, {"url": "https://hersteller.example/anleitung-alt", "version": "2019"}]},
       {"art": "datenblatt", "titel": "Datenblatt", "version": "2", "gueltig_ab": "2025-01-01",
        "url": "https://hersteller.example/datenblatt"}
     ]}
  ],
  "formulare": [
    {"kategorie": ["PSA gegen Absturz und Seiltechnik", "Gurte"], "kategorie_uid": "fa0924f611f67a059a66fa70610d8495",
     "titel": "Gurtprüfung", "aktivieren": true,
     "punkte": [{"gruppe": "Kennzeichnung", "text": "Beispiel-Prüfpunkt", "art": "yesno", "pflicht": true,
                 "soll": "ja", "kritisch": true}]},
    {"produkt": {"uid": "517afaa09a333286eef21f40f0ec4021", "hersteller": "Beispielwerk", "modell": "Beispielgurt",
                 "artikelnummer": "BW-1"},
     "titel": "Gurtprüfung Beispielgurt (Entwurf)", "aktivieren": false,
     "punkte": [{"gruppe": "", "text": "…", "art": "yesno", "pflicht": true, "soll": "nein", "kritisch": false}]}
  ]
}
```

| Feld | Bedeutung |
| --- | --- |
| `uid` (Kategorie, Produkt) | Katalogkennung: 32 Zeichen `0–9a–f`, in der Datei je Art eindeutig. Abgleich zuerst über sie; sonst über Name an der Stelle bzw. Dublette – dann übernimmt der Datensatz sie. Neu Angelegtes bekommt sie. Optional |
| `artikel_laenge` (Kategorie) | `true`/`false` (auch `"ja"`/`"nein"`, 1/0): das Häkchen „Artikel haben eine Länge“ (Schritt 20, 22.10.2026) – es gilt für die Kategorie und alle Unterkategorien. Der Export schreibt es an jede Kategorie; der Import setzt oder nimmt es weg, ein fehlender Schlüssel oder `null` lässt es, wie es ist (neu: `false`). Auch in Format 1 gelesen. Optional |
| `kategorie_uid` (Produkt, generisches Formular) | Kategorie über ihre uid; gibt es sie hier nicht, gilt `kategorie` (Pfad) |
| `produkt.uid` (spezifisches Formular) | Produkt über seine uid; sonst Hersteller + Modell + Artikelnummer |
| `bild` (Produkt) | Pfad im Archiv; Foto (JPEG, PNG, WebP, HEIC, TIFF), höchstens 31 MB (wie beim Hochladen) und 60 Megapixel. Gleiche SHA-256 wie das Original hier: unverändert; sonst ersetzt. Fehlt es, bleibt das Bild hier |
| `dokumente[]` (Kategorie, Produkt) | `art` (`produktbild`, `konformitaetserklaerung`, `gebrauchsanleitung`, `pruefanweisung`, `pflegehinweis`, `datenblatt`, `sonstiges`), `titel`, `version`, `gueltig_ab` (JJJJ-MM-TT) und entweder `datei` (Pfad im Archiv; PDF oder Bild, Inhalt muss zur Endung passen, höchstens 50 MB) oder `url` (`https://…`) |
| `vorgaenger` (Dokument) | Kennungen der früheren Versionen dieses Dokuments, neueste zuerst: je Version `{"sha256": …}` (Datei) oder `{"url": …, "version": …}` (Link). Der Export schreibt sie mit, sobald ein Dokument Vorgänger hat. Optional |
| Abgleich der Dokumente | Je Ziel in drei Schritten: 1. gleiche Datei (SHA-256) bzw. gleicher Link in gleicher Version unter den aktuellen: unverändert – zuerst für alle Einträge des Ziels; 2. ist eins der aktuellen Dokumente hier unter den `vorgaenger`: neue Version davon; 3. sonst gleiche Art und gleicher Titel – nur, wenn genau eins davon bei `gueltig_ab` schon gilt; bei mehreren ein Fehler („Mehrdeutig“), damit keine Versionsketten über Kreuz verknüpft werden; sonst neues Dokument. Eine neue Version gilt nie früher als die vorhandene |
| `titel` (Formular) | Leer heißt: kein Titel vorgegeben – verglichen werden dann nur die Prüfpunkte; eine neue Version erbt den Titel der letzten hier |
| `aktivieren` (Formular) | Der Export schreibt `true` für das aktive Formular eines Ziels, `false` für die neueste Version, wenn keins aktiv ist |
| `quelle`, `erstellt` | woher und wann (nur zur Anzeige) |
| `set` (Produkt) | Seit dem Rückbau der Set-Funktion (Schritt 26): `true` ist ein **Fehler dieses Produkts** („Sets gibt es nicht mehr …“, nichts wird gespeichert), `false` wird übergangen. Der Export schreibt es nie. (Bis Schritt 26: das Häkchen „Set“.) Optional |
| `bestandteile` (Produkt) | Seit Schritt 25 die Bestandteil-Liste eines Produkts – je Position `{bezeichnung, anzahl}` (Bezeichnung eine Zeile, höchstens 120 Zeichen, je Liste eindeutig; Anzahl 1–20, Vorgabe 1), höchstens 30 Positionen; `einzeln: true`, `produkt` und `austausch` außer `nicht_belegt` sind Fehler; `[]` entfernt die Liste, fehlt der Schlüssel, bleibt sie. Eine Liste aus Texten (Recherche-Manifeste) ist ein Hinweis und wird übergangen. Bericht `bestandteillisten`. Vorlage: `docs/material-katalog-bestandteile-vorlage.json`. Auch in Format 1 gelesen. Optional |

Was hier mehr ist als in der Datei, bleibt: Der Import löscht, deaktiviert und zieht nie etwas zurück. Ein Fehler
irgendwo: nichts gespeichert, auch keine Datei abgelegt. Der Probelauf (`--trocken`, in der Oberfläche immer zuerst)
schreibt nichts. Der Export lässt alles mit DEMO-Kennzeichen weg – Kategorien samt Teilbaum, Produkte darin, Formulare
und Dokumente an DEMO-Zielen – und nimmt Bestand, Prüfungen, Meldungen und Rückrufe nie mit.

Reihenfolge: erst die Kategorien, dann die Produkte, dann die Formulare. Scheitert ein Eintrag an einem Namen, einer
Dublette oder einer Artikelnummer, die hier noch ein anderer Eintrag trägt, kommt er nach den übrigen noch einmal dran
(eine Kategorie samt Teilbaum) – so lange, wie sich dabei etwas bewegt, höchstens 50 Runden. So geht die übliche Kette
„altes Modell bekommt einen Zusatz, neues den alten Namen“ in einem Lauf durch; zwei Namen, die die Plätze tauschen,
bleiben ein Fehler. Dass jedes Produkt ein Prüfintervall hat, prüft der Import erst nach den Produkten: Verliert eine
Kategorie ihre Vorgabe, während das Produkt in derselben Datei ein eigenes Intervall bekommt, ist das gültig.

Grenzen beim Lesen eines Archivs: höchstens 20 000 Einträge und 5 MB Inhaltsverzeichnis – beides am Ende-Satz des
Archivs (bei Zip64 an dessen Zip64-Satz) geprüft, bevor das Verzeichnis eingelesen wird –, 3 GB entpackt,
`katalog.json` 5 MB, Packverhältnis eines Eintrags ab 1 MB höchstens 100 : 1; verschlüsselte, beschädigte oder doppelt
benannte Einträge werden abgewiesen. Hochladen und Export: bis 2 GB. Eine Datei über der Grenze des Imports (Bild
31 MB, Dokument 50 MB) lässt schon der Export aus und nennt sie (Vorschau und `bericht.txt`).

**Wiki-Verknüpfungen gehören nicht zum Katalogformat** (Phase 2 · 3): Der Export schreibt die Prüfanleitung eines
Formulars nicht mit, der Import setzt nie eine – eine neue Formularversion aus dem Import erbt aber die Verknüpfung
der letzten Version. Verknüpft wird in der Instanz, in der die Anleitungen im Wiki stehen.

## Schnittstelle (Phase 1 mit den Nachbesserungen, Phase 2 · Lieferung 1 bis 3, Phase 3 · Lieferung 1 mit den Nachbesserungen vom 21.10.2026, Phase 4 · Lieferung 1 und 2)

Seit Phase 2 gilt jedes Recht an einem Ordner (Freigaben je Ordner, vererbt nach unten): „lesen“ heißt Leserecht am
Gegenstand (Artikel und Prüfungen: an der Heimat des Artikels), „Grundrecht“ lesen oder verwalten, „Materialwart“
verwalten dort, „Prüfer“ Häkchen, Urkundennummer und Prüffreigabe dort. Listen über den ganzen Bestand verlangen
Modulzugang und zeigen nur, was das Konto sieht; Fremdes antwortet 404 wie Unbekanntes. „Katalog“ heißt
Material-Verwaltung (Stufe „Verwaltung“ im Modul Material; bis zur Nachbesserung „Modulstufe“: Produktkatalogpfleger
oder Plattform-Verwaltung).

| Methode und Pfad | Recht | Zweck |
| --- | --- | --- |
| `GET /api/material/start` | Modulzugang (Inhalt gefiltert) | Rechte des Kontos, Zählung, Gliederungen, nächste Fälligkeiten; `ordner_uebersicht` (Fälligkeiten je Ordner, Zeilen in Baumreihenfolge mit `tiefe`, `bestand`, `zaehlung`, `naechste`), `rueckrufe` (laufende mit betroffenen Artikeln im Bestand); `erinnerungen` – Laufstand der Erinnerungsmails (Schalter, Sperre, Mailserver, letzter Mail- und Pflegeteil, `veraltet`, `pflege_veraltet`; Zeitpunkte UTC) nur für Material- und Plattform-Verwaltung, sonst `null` (Phase 2 · 2) |
| `GET /api/material/suche?q=` | Modulzugang | Artikel nach Serien-, Inventar-, Herstellernummer im eigenen Bereich; `eindeutig` bei genau einem Treffer; `exakt_lokal` (ein sichtbarer Artikel hat genau diese Seriennummer) und `global_angebot` (zu jeder Anfrage, die für die globale Suche taugt, außer für die Material-Verwaltung; Phase 2) |
| `GET /api/material/faellig?status=&ordner=&zugeordnet=` | Modulzugang; mit `ordner` lesen dort (sonst 404) | fällige Artikel, Standard überfällig + Lebensdauer erreicht + neu + bald fällig; mit `ordner` auch `ordner` = {id, pfad}; `zugeordnet` filtert nach Person (nur mit Grundrecht wirksam, Phase 2) |
| `GET/POST /api/material/kategorien`, `PUT/DELETE …/<id>` | lesen / Katalog | Kategoriebaum; Löschen nur leer und ohne Dokument in einem Prüfprotokoll (409); je Kategorie `items_have_length` (das Häkchen) und `laenge_wirksam` (hier oder an einer Oberkategorie gesetzt) (Schritt 20) |
| `GET/POST /api/material/produkte`, `GET/PUT/DELETE …/<id>` | lesen / Katalog | Produkte mit Suche (Hersteller, Modell, Bemerkung, Artikelnummer, Norm) und Seiten (`q`, `kategorie`, `seite`, `pro_seite`); `description` (in der Oberfläche „Bemerkung“) beim Speichern höchstens 80 Zeichen, eine Zeile (Nachbesserung vom 18.10.2026) |
| `GET /api/material/produkte/artikelnummer?nr=&ausser=` | lesen | Wem gehört diese Artikelnummer schon? (`produkt` oder `null`) |
| `POST /api/material/produkte/<id>/variante` (Felder wie `POST /produkte`, `dokumente`: Kennungen) | Katalog | Kopie als neue Variante; Bild nie, Dokumente nach Wahl |
| `PUT /api/material/produkte/<id>/bestandteile` (`bestandteile`: Liste der Positionen) | Katalog | Bestandteil-Liste als Ganzes ersetzen (nur Bezeichnung und Anzahl) → `produkt`, `geaendert`; Lesefelder `bestandteile` `[{id, position, bezeichnung, anzahl}]`, `stueckliste_grenzen` – Einzelheiten im Abschnitt „Bestandteil-Liste an normalen Produkten“ (Schritt 25) |
| `POST/DELETE /api/material/produkte/<id>/bild` | Katalog | Produktbild |
| `POST /api/material/produkte/<id>/dokumente`, `POST /api/material/dokumente/<id>/version`, `…/zurueckziehen` | Katalog | Herstellerdokumente |
| `GET/POST /api/material/formulare`, `GET/PUT/DELETE …/<id>`, `POST …/<id>/aktivieren`, `…/deaktivieren` | lesen / Katalog | Prüfformulare |
| `GET/POST /api/material/ordner`, `GET/PUT/DELETE …/<id>`, `POST …/<id>/verschieben`, `POST/DELETE …/<id>/foto` | lesen / Materialwart (Löschen: am Oberordner; Gliederung auf oberster Ebene anlegen und löschen: Material-Verwaltung) | Ordnerbaum; über Gliederungsgrenzen verschiebt nur, wer beide Gliederungen verwaltet, und zur Gliederung macht einen Ordner (`PUT` mit `kind: "gliederung"`) nur, wer die bisherige verwaltet (Phase 2) |
| `GET /api/material/artikel/vorschlag` | Modulzugang; mit `folder_id` lesen dort (sonst 404) | Vorschläge (Intervall, nächste Prüfung, Lebensende) vor dem Anlegen |
| `POST /api/material/artikel`, `GET/PUT/DELETE …/<id>`, `POST /api/material/artikel/verschieben` | lesen / Materialwart | Artikel, auch mehrere auf einmal verschieben |
| `POST /api/material/artikel`, `PUT …/<id>` mit `length_m` (Text „57,5“/„57.5“ oder Zahl, eine Nachkommastelle, 0,1–9999,9, `null` leert) | Materialwart | Länge (Schritt 20): nur, wenn die Kategorie des Produkts sie vorsieht – sonst 409 mit Klartext (eine vorhandene Länge bleibt unverändert speicherbar); Antworten tragen `length_m`, `laenge_text` („57,5 m“) und `laenge_moeglich`; Journal „geändert“ mit `length_m` |
| `GET /media/material/<orig\|web\|thumb\|dok\|anhang>/<datei>` | je Datei (Phase 2): Produktbild und Dokument Modulzugang, Ordnerfoto lesen am Ordner, Befundfoto und Anhang lesen am Artikel, Meldungsfoto wie die Meldung; sonst 404 | Fotos, Dokumente, Prüfanhänge; privat, strenge CSP |
| `GET/POST /api/material/kategorien/<id>/dokumente` | lesen / Katalog | Dokumente für alle Produkte einer Kategorie |
| `PUT /api/material/dokumente/<id>` (`title`) | Katalog | Dokument umbenennen (Produkt- oder Kategoriedokument) |
| `POST /api/material/meldungen` (`manufacturer`, `model`, `article_no`, `norm`, `category_id`, `folder_id`, `links`, `note`; `fotos` mehrfach) | Materialwart (am `folder_id`; ohne Ordner: verwalten irgendwo) | Fehlendes Produkt melden |
| `GET /api/material/meldungen?status=offen\|erledigt\|alle&eigene=0\|1`, `GET …/<id>` | Modulzugang (auch für den Melder); je Meldung nur Katalog, der Melder und wer ihren Ordner sieht (sonst 404, Phase 2) | Meldungen; Material-Verwaltung und Lesende standardmäßig alle offenen, Materialwarte die eigenen; `bearbeiten` nur für die Material-Verwaltung |
| `POST /api/material/meldungen/<id>/produkt` (Felder wie `POST /produkte`, dazu `antwort`) | Katalog | Produkt aus der Meldung anlegen und Meldung erledigen |
| `POST /api/material/meldungen/<id>/zuordnen` (`product_id`, `antwort`), `…/ablehnen` (`antwort` Pflicht) | Katalog | vorhandenes Produkt zuordnen bzw. ablehnen |
| `DELETE /api/material/meldungen/<id>` | nur der Melder – auch ohne Modulzugang | eigene Meldung löschen (offen oder erledigt; ein Produkt aus ihr bleibt); wer eine fremde nicht sehen darf, bekommt 404 wie für eine unbekannte (Phase 2) |
| `?sort=<spalte>&richtung=auf\|ab` an `produkte`, `ordner/<id>`, `faellig`, `suche` | – | Sortierung: Katalog `hersteller`, `produkt`, `kategorie`, `materialart`, `intervall`, `lebensdauer`, `bestand`; Artikel `inventar`, `hersteller`, `produkt`, `serie`, `faellig`, `status` |
| `GET/POST /api/material/artikel/<id>/pruefungen` | lesen / Prüfer | Prüfungen eines Artikels; Prüfung beginnen (`art`, `durchgang_id`) – oder den eigenen Entwurf fortsetzen |
| `GET /api/material/pruefungen/<id>`, `PUT …/punkte/<pid>` (Art `laenge`: `wert` wie `length_m`) | Prüfer | Prüfung trägt `laenge` {`wert`, `text`, `moeglich`}; ein Längenpunkt ist mit der Artikellänge vorbelegt (Soll und Wert „57,5“), der Wert wird als „55,0“ gespeichert; ohne vorgesehene Länge „nicht zutreffend“ – ein Wert und die Befunde `ok`/`mangel` sind 409. Festschreiben (`…/abschliessen`) übernimmt einen abweichenden Wert in `mat_item.length_m` – Journal „laenge_geaendert“ am Artikel (`length_m` vorher/nachher, `pruefung`, `art`), Protokoll „57,5 m → 55,0 m“ bzw. „55,0 m (unverändert)“; 409 „Die Länge am Artikel wurde während der Prüfung auf … geändert – bitte den Messwert bestätigen“, wenn sich die Länge seit der Vorbelegung geändert hat (der Punkt trägt danach die neue Länge); eine Berichtigung behält das Soll des Originals und übernimmt nur einen gegenüber dem Original geänderten Messwert; NaN/Unendlich 400 (Schritt 20 mit Nachbesserung) |
| `GET/PUT/DELETE /api/material/pruefungen/<id>` | lesen / Prüfer / Prüfer oder Materialwart | Prüfung lesen; Art und Bemerkung am Entwurf; Entwurf verwerfen bzw. Reservierung aufheben |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>`, `POST/DELETE …/foto` | Prüfer (eigener Entwurf) | Befund, Wert, Bemerkung, Foto je Prüfpunkt |
| `POST /api/material/pruefungen/<id>/anhaenge` (`file` mehrfach, `art`, `titel`, `im_protokoll`), `DELETE …/<aid>` | Prüfer (eigener Entwurf) | Anhänge |
| `POST /api/material/pruefungen/<id>/festschreiben` (`ergebnis`, `next_due_on`, `grund`, `bemerkung`; alter Pfad `…/abschliessen` gilt weiter) | Prüfer (eigener Entwurf, mit Unterschrift) | Abschluss und Festschreiben mit Protokoll |
| `POST /api/material/pruefungen/<id>/berichtigen` (`grund`) | Prüfer (der die Prüfung gemacht hat) | Berichtigung beginnen; liefert den neuen Entwurf |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>` mit `unterschrift` (data:-URL oder `null`) | Prüfer (eigener Entwurf) | Unterschriftsfeld eines Formulars |
| `GET/PUT/DELETE /api/material/unterschrift` (`bild`: data:-URL vom Signatur-Pad) | GET und DELETE angemeldet (eigene Daten, auch ohne Modulzugang); PUT mit Modulzugang nur Prüfer (seit Lieferung 5 schon mit dem Häkchen, ohne Urkundennummer) und wer irgendwo verwaltet (eigenes Konto) | eigene Unterschrift im Profil |
| `PUT /api/material/urkundennummer` (`urkundennummer`; leer entfernt sie) | Häkchen „Prüfer“ (eigenes Konto), sonst 403 | eigene Urkundennummer im Profil; Antwort `urkundennummer`, `pruefen` (darf jetzt prüfen); ungültig 400 (Lieferung 5) |
| `GET /materialablage/pruefung/<id>/pdf`, `GET /materialablage/durchgang/<id>/sammelprotokoll` | lesen | Protokoll als PDF (nur, solange die Datei ihre Prüfsumme hat) |
| `GET /materialablage/pruefen`, `POST /api/material/pruefen` (`datei`) | ohne Anmeldung | Prüfseite: `ergebnis` (unveraendert, veraendert, unbekannt), `protokoll_id`, `art`, `hinweis` – angemeldet mit Zugang dazu `link` |
| `GET /api/material/entwuerfe` | Modulzugang | offene Prüfungen aller Prüfer im eigenen Bereich |
| `POST /api/material/artikel/<id>/sperren` (`grund`: sturz, beschaedigung, verlust, rueckruf; `text`) | Prüfer | Sperre ohne Prüfung |
| `POST /api/material/artikel/<id>/aussondern` (`grund`: lebensdauer, verlust, irreparabel; `datum`, `bemerkung`) | Materialwart (mit Unterschrift) | Aussonderung gesperrter Artikel mit Aussonderungsprotokoll; liefert `aussonderung` (Kennung) |
| `GET/POST /api/material/durchgaenge`, `GET/DELETE …/<id>` | lesen / Materialwart oder Prüfer | Prüfdurchgänge (`?offen=1`); eröffnen (`folder_id`, `titel`); löschen, solange nichts geprüft ist |
| `POST /api/material/durchgaenge/<id>/ausnehmen`, `…/einbeziehen` (`item_id`, `grund`), `…/abschliessen` | Materialwart oder Prüfer | Artikel ausnehmen, wieder einbeziehen, Durchgang abschließen (mit Sammel- und Set-Protokollen; 409 „Während des Festschreibens wurde am Durchgang weitergearbeitet …“, wenn sich dreimal zwischen Rendern und Festschreiben etwas geändert hat, 503 bei gesperrter Datenbank) |
| `POST /api/material/durchgaenge/<id>/abbrechen` | Materialwart oder Prüfer | vorzeitig beenden; `durchgang` ist `null`, wenn er mangels Geprüftem entfernt wurde |
| `GET /materialablage/export/<ordner>.csv` | Grundrecht am Ordner (Phase 2) | Artikel, deren Heimat im Ordner oder darunter liegt (auch von hier gesperrte und ausgesonderte), als CSV für Excel; Spalte „Zugeordnet an“ (Phase 2), hinter „Modell“ „Bemerkung (Produkt)“ (Nachbesserung vom 18.10.2026), hinter „Lebensende“ die Spalte „Länge (m)“ als „57,5“ (Schritt 20) |
| `GET /materialablage/export/<ordner>-protokolle.zip` | Grundrecht am Ordner (Phase 2) | alle Protokolle dieser Artikel, die Sammelprotokolle der Durchgänge und die Set-Protokolle der Sets im Zweig, mit `Verzeichnis.csv` (Spalte „Set“ seit 25.10.2026); Dateiname mit ASCII-Ersatz („ue“) und `filename*` |
| `GET /materialablage/artikel/<id>/lebenslauf.pdf` | Grundrecht an der Heimat (Phase 2) | Lebenslauf als PDF/A-3b, auf Abruf, nicht festgeschrieben |
| `GET /api/material/katalog/export`, `GET …/export/vorschau` | Katalog | Katalog ohne DEMO als ZIP (Format 2) bzw. seine Zahlen vorab |
| `POST /api/material/katalog/import` (`file`: ZIP oder JSON, `trocken`: Vorgabe `1`) | Katalog | Katalogimport im Hintergrund (seit 24.10.2026): **202** `auftrag`, 409 mit dem laufenden, 507 bei zu wenig Platz (Datei + 64 MB); der Bericht (neu/geändert/unverändert je Art, Bilder, Dokumente, Änderungen, Hinweise, Warnungen, Fehler) kommt über `GET …/katalog/import/<kennung>` |
| `GET /api/material/katalog/import/<kennung>`, `POST …/<kennung>/uebernehmen`, `GET …/katalog/import/aktuell` | Katalog (Übernehmen: wer den Probelauf gestartet hat) | Stand und Bericht eines Auftrags (`von`: Name, frisch aus dem Kontoverweis aufgelöst, „(gelöschtes Konto)“ nach dem Löschen); echter Lauf mit der Datei des Probelaufs (202, 507 bei zu wenig Platz; auch mit der Kennung eines abgebrochenen „Übernehmen“, dessen Probelauf seine Datei zurückbekam); laufender oder zuletzt beendeter Auftrag für die Katalogseite – Einzelheiten unter „Katalogimport im Hintergrund“ und seiner Nachbesserung |
| `GET /api/material/produkte/<id>/rueckrufe` | Modulzugang | Rückrufe des Produkts: laufende mit den betroffenen Artikeln, die das Konto sieht, und ihren Zahlen (nicht gefundene Seriennummern nur für die Material-Verwaltung, Phase 2), beendete mit Vermerk |
| `POST /api/material/produkte/<id>/rueckrufe` (`title`, `description`, `url`, `serials`, `mail`) | Katalog | Rückruf anlegen; Antwort mit betroffenen Artikeln, Empfängerzahl, nicht gefundenen Seriennummern (Phase 2: nur, wer alle Bestände sieht – die Material-Verwaltung; ein Konto mit Teilsicht bekäme `betroffen` und `offen` des eigenen Bereichs und `benachrichtigt`) |
| `POST /api/material/rueckrufe/<id>/beenden` (`vermerk` Pflicht) | Katalog | Rückruf beenden |
| `GET /api/material/rueckrufe` | Modulzugang | alle laufenden Rückrufe mit Produkt und den Zahlen des eigenen Bereichs |
| (Artikel, Produkt, Listen) | lesen | neu: `artikel.rueckrufe` (laufende samt Zustand), `produkt.rueckrufe`, je Listenzeile `rueckruf` (Titel eines offenen) |
| `GET /api/material/ordner/<id>/freigaben` | Materialwart am Ordner | Reiter „Freigaben“ in „Ordner bearbeiten“: `ordner`, `anker_wahl` (der Ordner und die Oberordner, die man verwaltet, je mit dem eigenen Ende), `anker_vorgabe`, `direkt`, `geerbt` (ohne Notiz), `unten` (Zeilen je mit `aenderbar`, `entziehbar`, `grundrecht_dort` und `traegt_pruefen`), `kette`, `verlauf`, `laeuft_ab`, `grenzen` (heute, längste Prüffreigabe, Vorgabe für „bis“) (Phase 2) |
| `POST /api/material/ordner/<id>/freigaben` (`user_id`, `grundrecht`: `lesen`\|`verwalten`\|`null`, `grund_bis`, `pruefen`, `pruefen_bis`, `notiz`) | Materialwart am Ordner | Grundrecht und/oder Prüffreigabe in einem Schritt anlegen oder ändern, ganz oder gar nicht → 201 `freigaben`, `liste`; Prüffreigabe ohne Ende (`pruefen`: true, `pruefen_bis` leer) nur mit Grundrecht am Anker oder darüber, sonst 400; 404 „Konto nicht gefunden.“ für unbekannte, deaktivierte und namenlose Konten, 409 ohne Qualifikation, an Systemordnern oder ohne verbleibenden Verwalter (Phase 2) |
| `POST /api/material/ordner/<id>/freigaben/verlaengern` (`bis`) | Materialwart am Ordner | alle befristeten Prüffreigaben im Zweig, die man ändern darf (auch bis zu 90 Tage abgelaufene) → `verlaengert`, `uebersprungen` (Konto, Ordner, Grund) (Phase 2) |
| `PUT /api/material/freigaben/<id>` (`recht`, `bis` – `null` = unbefristet, bei Prüffreigaben nur mit Grundrecht –, `notiz`), `DELETE …/<id>` | Materialwart am Ordner der Freigabe | Freigabe ändern bzw. entziehen; DELETE liefert `offene_entwuerfe` (Phase 2). Ausweiten (anderes Recht als verwalten → lesen, späteres Ende) nur für Konten mit Modulzugang, sonst 409 |
| `GET /api/material/freigaben/meine` | angemeldet, auch ohne Modulzugang | eigene Freigaben (gültige und im letzten Jahr abgelaufene) mit Pfad, `recht`, `bis`, `gueltig`, `wirkt`, `wirkt_nicht` (Grund oder `null`), `grundrecht_dort`, `laeuft_ab_in_tagen` und `verwalter` (bis zu drei Namen) – ohne Notiz; dazu `zugang`, `qualifiziert` (wirkt nur mit Zugang), `alles` (Material-Verwaltung) (Phase 2) |
| `GET /api/material/freigaben?user_id=` | Plattform-Verwaltung | alle Freigaben eines Kontos mit Notiz (Nutzerverwaltung) (Phase 2) |
| `GET /api/material/nutzer?q=&zweck=` (ab 3 Zeichen) | verwalten irgendwo oder Material-Verwaltung | Personensuche: `zweck=freigabe` (Vorgabe) nur Konten mit Zugang zum Modul (Stufe Mitglied oder Verwaltung), `zweck=zuordnung` alle; höchstens 20 aktive Konten mit Namen, je `id`, `name`, `gliederung`, `qualifiziert` (wirkt nur mit Stufe), `grundrecht_ueberall` (Material-Verwaltung) – keine E-Mail, keine Urkundennummer; `mehr` (Phase 2, `zweck` seit der Modulstufe) |
| `POST /api/material/globalsuche` (`q`, `bestaetigt: true`) | Modulzugang | globale Seriennummernsuche nur unter den Artikeln, die das Konto nicht sieht → `treffer` (höchstens 10 Steckbriefe, ohne Kennungen, mit `sperre`), `mehr`, `hinweis`; 400 ohne Bestätigung, unter 4 Zeichen oder bei Inventar- und STR-Nummern, 409 für die Material-Verwaltung (sieht alles); ungebremst, jede Suche im Protokoll (Phase 2) |
| `POST /api/material/globalsuche/qr` (`token`, `bestaetigt: true`) | Modulzugang | Steckbrief nach einem QR-Scan an einem fremden Artikel (ein Treffer, mit `sperre`); `weiter` (Adresse), wenn der Artikel inzwischen sichtbar ist (Phase 2) |
| `GET /api/material/globalsuche/protokoll?seite=` | Plattform-Verwaltung | Protokoll der globalen Suchen, QR-Steckbriefe und fremden Dubletten, neueste zuerst: `eintraege` (Zeit, Name, Art, Anfrage, Treffer, Gliederungen), `gesamt`, `seite`, `pro_seite` (Phase 2) |
| `PUT /api/material/artikel/<id>/zuordnung` (`user_id` oder `null`) | Materialwart am Artikel | Person zuordnen oder Zuordnung lösen → `artikel`; 409 bei ausgesonderten (Phase 2) |
| `POST /api/material/artikel/zuordnen` (`ids` 1–500, `user_id` oder `null`) | Materialwart je Artikel | mehrere auf einmal, ganz oder gar nicht → `geaendert` (Phase 2) |
| `GET /api/material/ordner/<id>/zugeordnete` | Grundrecht am Ordner | Personen mit Zuordnungen im Zweig: `zugeordnete` (`id`, `name`, `anzahl`, `aktiv`) – für den Filter (Phase 2) |
| `GET /api/material/ordner/<id>?zugeordnet=` | lesen; Filter nur mit Grundrecht wirksam | Ordnerinhalt nach zugeordneter Person (Phase 2) |
| `GET /api/admin/users/<id>/material-folgen` | Plattform-Verwaltung | was das Löschen des Kontos im Modul bewirkt: `freigaben`, `zuordnungen`, `entwuerfe`, `pruefungen` (Phase 2); dazu `letzter_materialwart` – die Gliederungen `[{id, name, pfad}]`, deren einziger Materialwart das Konto heute ist (Rückfrage beim Senken, Deaktivieren und Löschen; Entscheidung vom 18.10.2026) |
| `GET /m/<token>` | Modulzugang | sichtbarer Artikel → Weiterleitung; sonst Seite „fremd“ ohne Artikeldaten mit dem Knopf für den Steckbrief (Phase 2) |
| (Ordner, Artikel, Prüfung, Durchgang) | – | neu: `darf` (`lesen`, `grund`, `pruefen`, `verwalten`) für genau dieses Objekt; `artikel.zugeordnet` und `artikel.journal` nur mit Grundrecht (sonst `null`), Listenzeile `zugeordnet_name`; `durchgang` = `{id, titel, ordner, sichtbar}`; Baumknoten `nur_pfad` und `teilweise`; Durchgangszeilen ohne Leserecht `sichtbar: false`, ohne Kennung (Phase 2) |
| `GET /api/material/erinnerungen/probelauf` | Material-Verwaltung (Plattform-Verwaltung eingeschlossen) | Probelauf der Erinnerungsmails für den nächsten Lauf (heute oder, wenn heute schon verschickt wurde, morgen): `stichtag`, `morgen`, `versand`, `gesperrt`, `smtp`, `letzter` (`tag`, `beginn`, `mails`, `fehlgeschlagen`, `fehlgeschlagen_an`, `fehler`), `mails` (`name`, `gliederung`, `betreff`, `text`, `artikel`, `freigaben` als Verwalter, `eigene` – eigene ablaufende Freigaben, Abschnitt „Deine Freigaben“; keine Adressen), `ohne_empfaenger` (`ordner`, `artikel`, `freigaben`), `ausgelassen` (`ordner_aus`: `id`, `pfad`, `artikel`; `demo`, `demo_freigaben`), `fehlerhaft`, `demo`; `mails` je mit `demo`; `?demo=1` bezieht den DEMO-Bestand ein – nur Ansicht, DEMO-Mails gekennzeichnet, gehen nie hinaus; schreibt nichts (Phase 2 · 2) |
| `GET /api/material/ordner/<id>` | lesen | neu: `ordner.reminders_off` (eigener Wert) und `ordner.erinnerungen` = `{aus, eigen, geerbt_von: {id, pfad, sichtbar} \| null}`; Ordnerbaum mit `reminders_off` (Phase 2 · 2) |
| `PUT /api/material/ordner/<id>` mit `reminders_off` (ja/nein) | Materialwart am Ordner | „Erinnerungsmails aus“ für Ordner und Unterordner; fehlt das Feld, bleibt der Wert; anderes als ja/nein → 400; mit Journal (Phase 2 · 2) |
| `flask --app "app:create_app()" material remind [--trocken [--demo]] [--stichtag JJJJ-MM-TT] [--erneut]` | Kommandozeile im Container | Erinnerungslauf: `--trocken` zeigt die Mails des nächsten Laufs mit Adressen und schreibt nichts (auch bei „aus“ oder gesperrt), `--stichtag` und `--demo` (DEMO-Bestand einbeziehen, nur Ansicht) nur mit `--trocken`; ohne `--trocken` ein echter Lauf für heute (nie DEMO), `--erneut` noch einmal am selben Tag (nur, was nicht im Log steht). Exit 0, 1 (Mail gescheitert, Fehler), 2 (aus, gesperrt, kein Mailserver, `--stichtag` oder `--demo` ohne `--trocken`, unlesbares Datum) (Phase 2 · 2) |
| `flask --app "app:create_app()" material dok-zusammenfuehren [--probe]` | Kommandozeile im Container | Herstellerdokumente einmal je Inhalt (Schritt 18): Altbestand unter `media/material/dok` auf Inhaltsnamen bringen, Dubletten zusammenführen, Prüfsummen aus den Dateien nachtragen – läuft beim ersten Start nach dem Update von selbst; hier mit Bericht (Dateien und MB vorher/nachher, frei, fehlende Dateien, Dateien ohne Zeile und davon entfernte Dubletten, entfernte Zwischendateien älter als ein Tag), `--probe` rechnet nur. Exit 0, 1 (Dateien fehlen), 2 (Ordner nicht erreichbar) (22.10.2026) |
| `flask --app "app:create_app()" material dev-zuruecksetzen [--trocken] [--ja-alles-loeschen]` | Kommandozeile im Container, nur dev | Modul Material leeren: erst die ganze Datenbank nach `sicherung-material-<Zeitstempel>/` sichern und `media/material`, `pdf/` dorthin verschieben, dann alle `mat_`-Objekte entfernen und das Schema frisch anlegen (Version 21); Konten, Wiki, Spots, Prüfungen, Einstellungen bleiben, DEMO-Konten werden nur genannt. `--trocken` zeigt nur. Nur mit `STROEMIS_NAME` auf `-dev`, `BASE_URL` (Umgebung und Einstellungen) mit Host `dev.…`, `localhost` oder `127.0.0.1` und `--ja-alles-loeschen`; SIGTERM/SIGHUP brechen sauber ab (Exit 1), Sicherung 0700/0600, ältere Sicherungen werden genannt. Exit 0, 1 (Sicherung oder späterer Schritt gescheitert – nichts geändert), 2 (nicht dev, ohne Schalter) (23.10.2026) |
| `GET /materialablage/ordner/<id>/import` | Materialwart am Ordner (sonst 403-Seite, fremd 404, Systemordner 409) | Seite „Bestandsliste importieren“ mit der Nacharbeit dieses Zielordners (Phase 2 · 3) |
| `POST /api/material/ordner/<id>/import/probelauf` (Formular: `file`, `zuordnung` JSON `{"<Spalte>": feld}`) | Materialwart am Ordner | Probelauf, schreibt nichts (außer einer Protokollzeile, wenn er fremde Dubletten nennt) → Bericht: `datei`, `nacharbeit_csv`, `spalten`, `felder`, `fehlt`, `warnungen`, `schon_importiert`, `sperre_bis` (dieselbe Datei bis dahin gesperrt, ISO in UTC, sonst `null`), `keine_seriennummer` (keine Spalte als Seriennummer zugeordnet), `ohne_seriennummern_bestaetigen` (Übernehmen braucht `ohne_seriennummern`, Entscheidung vom 20.10.2026), `zahlen` (mit `ohne_serie`), `faelligkeit`, `produkte_offen`, `ordner_unbekannt`, `zeilen`, `frist`; 400 unlesbar, 409 Systemordner, 413 zu groß, 429 anderer Import läuft (Phase 2 · 3) |
| `POST /api/material/ordner/<id>/import` (wie der Probelauf, dazu `ohne_seriennummern` ja/nein) | Materialwart am Ordner | Übernehmen in einer Transaktion → 201, Bericht mit Zeilen `angelegt` (`artikel` {id, inventory_no}, vergebene STR-Nummer) und `import` {id, angelegt, im_bestand, nacharbeit, ersetzt}; 409 nichts zu tun, ohne Seriennummernspalte ohne `ohne_seriennummern` = ja („Keine Spalte ist als Seriennummer zugeordnet – bitte bestätigen …“, nichts geschrieben), dieselbe Datei vor weniger als 10 Minuten, Ordnerbaum geändert; anderes als ja/nein → 400 (Phase 2 · 3) |
| `GET /api/material/ordner/<id>/nacharbeit?gruppe=alle\|produkt\|seriennummer\|daten\|ordner\|sonstige&seite=` | Materialwart am Ordner | offene Nacharbeit dieses Ziels: `zahlen` je Gruppe, `gruppen` (Produktangaben mit Vorschlägen, Meldung und `zugeordnet` – Zahl der Zeilen mit Produktwahl), `zeilen` (200 je Seite, mit `gruende`, `werte`, `offen_bis`), `erledigt` (die letzten 100), `frist` (Phase 2 · 3) |
| `POST /api/material/ordner/<id>/nacharbeit/produkt` (`angabe` oder `zeilen` [Nr.] \| `"alle"`, `product_id` oder `null`) | Materialwart am Ordner | Produkt zuordnen bzw. Wahl zurücknehmen → `gesetzt`; fremde Zeile 404, erledigte 409, DEMO-Produkt im echten Ordner 400 (Phase 2 · 3) |
| `POST /api/material/ordner/<id>/nacharbeit/melden` (Felder wie `POST /meldungen` ohne `folder_id`, dazu `angabe`; `fotos` mehrfach) | Materialwart am Ordner | Produkt melden; die Meldung hängt an allen offenen Zeilen der Angabe → 201 `meldung` (Phase 2 · 3) |
| `POST /api/material/ordner/<id>/nacharbeit/pruefen` (`zeilen` [Nr.] \| `"alle"`, `uebernehmen`) | Materialwart am Ordner | erneut prüfen (Bericht, schreibt nichts) bzw. mit `uebernehmen` in einer Transaktion übernehmen → `zahlen`, `faelligkeit`, `zeilen` (mit `id`), `hinweise`; 429 wie oben (Phase 2 · 3) |
| `POST /api/material/ordner/<id>/nacharbeit/verwerfen` (`zeilen` [Nr.] \| `"alle"`) | Materialwart am Ordner | offene Zeilen verwerfen (Werte gelöscht, Journal) → `verworfen` (Phase 2 · 3) |
| `GET /materialablage/ordner/<id>/nacharbeit.csv` | Materialwart am Ordner (Fehler als Seite) | offene Zeilen als CSV mit „Nacharbeit-Nr.“ (`;`, UTF-8 mit BOM, Formelschutz) – korrigiert wieder hochgeladen, erledigt sie die alten Zeilen (Phase 2 · 3) |
| `GET /api/material/wiki/seiten?q=` | Material-Verwaltung mit Stufe Mitglied im Wiki (sonst 403 mit Klartext) | Seitenwahl: lesbare Seiten ohne Papierkorb und Vorlagen, höchstens 30, je `{id, titel, icon, reichweite}`; `lesemodus` (Phase 2 · 3) |
| `PUT /api/material/formulare/<id>/wiki` (`seite`: Kennung oder `null`) | wie die Seitenwahl; auch an benutzten Formularen | Prüfanleitung verknüpfen bzw. entfernen; nicht lesbare, unbekannte oder Papierkorb-Seite 404 „Wiki-Seite nicht gefunden.“; schreibt nur diese Spalte, Journal mit der Seitennummer → `formular` (Phase 2 · 3) |
| (Übersicht, Ordner, Prüfung, Formular) | – | neu: `start.nacharbeit`, `ordner.nacharbeit` (nur mit verwalten), `pruefung.anleitung` (nur Entwürfe), `formular.wiki` und `formular.wiki_aendern` (nur Material-Verwaltung); `DELETE /ordner/<id>` 409 bei offener Nacharbeit (Phase 2 · 3) |
| `GET /materialablage/meine-psa`, `GET /materialablage/meine-psa/<id>` | angemeldet (sonst Anmeldung), aktives Konto mit Namen – auch ohne Modulstufe (sonst 403 „… braucht dein Konto einen Namen“); mit `<id>` nur ein eigener, nicht ausgesonderter Artikel (sonst 404 wie unbekannt) | Seite „Meine PSA“ (Ansicht `meine_psa`); ohne Modulzugang ohne Modulnavigation und Ordnerleiste (Phase 3 · 1) |
| `GET /api/material/meine-psa` | wie oben (401 ohne Anmeldung) | `artikel` (Karten: `id`, `inventory_no`, `serial_no`, `serial_generated`, `produkt` {`manufacturer`, `model`, `description`, `article_no`, `material_kind`, `bild` (Webfassung), `vorschau`}, `status`, `status_text`, `next_due_on`, `retire_by`, `last_inspected_on`, `gesperrt`, `verloren`, `lock_reason`, `notes`, `gliederung`, `demo`, `mangel` {`seit`}, `eigene_maengel`, `artikel_link`, `dokumente`, `rueckruf`, seit Schritt 20 `length_m` und `laenge_text`), `gesamt`, `mails`, `schwelle_tage` (Phase 3 · 1) |
| `PUT /api/material/meine-psa/mails` (`an`: ja/nein) | angemeldet (eigenes Konto) | Erinnerungen „Deine PSA“ an/aus → `{an}`; 400 ohne brauchbares `an` (Phase 3 · 1) |
| `POST /api/material/artikel/<id>/mangel` (Formular: `beschreibung`, `fotos` × 0–3; oder JSON `{beschreibung}`) | die zugeordnete Person (auch ohne Stufe) oder lesen an der Heimat; ohne Stufe und nicht eigen 403, ohne Leserecht mit Stufe 404 | Mangel melden, sperrt sofort → 201 `{mangel, gesperrt, mail}` (`mail` false bei DEMO, dev-Sperre und ohne Mailserver); 400 (Beschreibung, Fotos), 409 (ausgesondert, schon gemeldet, „Gesperrt“ fehlt), 413 (Phase 3 · 1) |
| `GET /m/<token>` | angemeldet | eigene PSA ohne Stufe oder ohne Leserecht → „Meine PSA“ des Artikels; sonst wie bisher (ohne Stufe 403, gleich ob es den Artikel gibt) (Phase 3 · 1) |
| `GET /materialablage` | – | ohne Stufe mit Zuordnung → 302 „Meine PSA“ (Phase 3 · 1) |
| `GET /media/material/<art>/<datei>` | ohne Stufe: Produktbild (`web`, `thumb`) und Herstellerdokumente der Arten aus „Meine PSA“ zu eigenen Artikeln, eigene Mangelfotos (sonst 403); mit Stufe: Mangelfotos für den Melder, Prüfer und Materialwarte des Artikels (seit 21.10.2026 nicht mehr für reine Leser – 404) | Mangelfotos ohne `orig` (Phase 3 · 1) |
| (Übersicht, Artikel, Listen, Prüfung) | – | neu: `start.maengel` (offene, nach denen kein Prüfer geprüft hat, höchstens 50: `id`, `item_id`, `inventory_no`, `produkt`, `created_at`, `kurz`, `fotos`, `melder`), `start.maengel_gesamt`, `start.meine_psa` {`anzahl`, `dringend`} oder `null`; `artikel.maengel` (Meldungen, offene zuerst, `wieder_offen`), `artikel.mangel_nur_gemeldet`, `artikel.mangel_eigen_offen` (Zeitpunkt der eigenen offenen Meldung oder `null`), `artikel.pruefarten.vorschlag` „ausserplanmaessig“ nach einer Meldung; Listenzeile `mangel`; `pruefung.maengel` (offene, im Entwurf). Text (`description`, `kurz`), Fotos (`fotos`) und `melder` nur für Prüfer und Materialwarte des Artikels und die eigene Meldung, sonst `null` bzw. leer mit `inhalt: false` (Phase 3 · 1, geändert 21.10.2026) |
| `POST /api/material/pruefungen/<id>/festschreiben` | wie bisher | neu: `maengel_gesehen` (abgehakte Kennungen); „einsatzbereit“ bei offener, nicht abgehakter Meldung → 409; Berichtigung mit „einsatzbereit“ bei offener Meldung → 409 (Phase 3 · 1) |
| `POST /api/material/artikel/<id>/aussondern`, `DELETE /api/material/artikel/<id>` | wie bisher | Aussondern 409 nach reiner Mangelsperre ohne Prüfung danach; Löschen 409, sobald eine Meldung am Artikel hängt (Phase 3 · 1) |
| `GET /api/material/artikel/<id>`, `PUT /api/material/artikel/<id>` | wie bisher | `stammdaten_fest` (true, sobald eine abgeschlossene Prüfung existiert; ein Entwurf zählt nicht); PUT danach 409, wenn sich `serial_no` oder `manufactured_on` ändern – auch eine STR-Nummer; weggelassen, leere Seriennummer, dieselben Werte (Seriennummer ohne Rücksicht auf Groß/klein) gehen durch (Nachbesserung vom 21.10.2026) |
| `GET /api/admin/users/<id>/material-folgen`, `GET /api/material/erinnerungen/probelauf` | wie bisher | neu: `maengel` (Zahl der Meldungen, die den Namen behalten); `mails[].psa` (Phase 3 · 1) |
| `PUT /api/material/artikel/<id>` | wie bisher | seit den Entscheidungen vom 21.10.2026: bei Metall ein fehlendes `manufactured_on` nachtragen auch nach der ersten Prüfung (200); `artikel.herstellung_nachtragbar`; Text der 409 nennt den Antrag |
| `PUT /api/material/artikel/<id>` (`product_id`) | wie bisher | seit dem Feintuning (23.10.2026): Produkt ändern bis zur ersten abgeschlossenen Prüfung; 409 bei offenem Entwurf und über die DEMO-Grenze; `artikel.produkt_aenderbar`; Journal „produkt_geaendert“ – siehe Abschnitt „Feintuning nach dem Kommentar-Dokument“ |
| `POST /api/material/artikel/<id>/antrag` (`serial_no`, `manufactured_on`, `begruendung` Pflicht; `herstellung_entfernen` → 400 seit 21.10.2026) | Materialwart oder Prüfer am Artikel (fremd 404, nur lesen 403) | Änderung beantragen → 201 `antraege` (je Feld einer: `id`, `feld`, `feld_text`, `alt`, `neu`, `status`, `begruendung`, `antragsteller`, `eigen`, `passt`, …), `artikel`, `mail`; 400 Eingaben, 409 ungeprüft, ausgesondert, schon beantragt, Dublette, Metall-Nachtragen (21.10.2026) |
| `GET /api/material/antraege?status=offen\|erledigt\|alle` | Modulzugang | Material-Verwaltung alle (Vorgabe offen), sonst die eigenen zu lesbaren Artikeln (Vorgabe alle); je Antrag `artikel` (`id`, `inventory_no`, `produkt`, `gliederung`, `pfad`, `lock_state`, `demo`) und `rueckruf` (`{nicht_mehr, neu}` – laufende Rückrufe, aus denen der Artikel mit der neuen Seriennummer fiele bzw. in die er käme; nur offen, sonst `null`); `alle`, `bearbeiten`, `offen`, `meldungen_offen` (21.10.2026) |
| `POST /api/material/antraege/<id>/bestaetigen` (`antwort` freiwillig), `…/ablehnen` (`antwort` Pflicht) | Material-Verwaltung (Plattform-Verwaltung eingeschlossen) | entscheiden → `antrag`; 409 schon entschieden, Stand geändert, ausgesondert (nur ablehnen), Dublette, alter Antrag aufs Entfernen des Herstelldatums (nur ablehnen; `antrag.entfernen`) (21.10.2026) |
| `POST /api/material/antraege/<id>/zurueckziehen` | Modulzugang; nur der Antragsteller, solange er den Artikel liest (sonst 404) | eigenen offenen Antrag zurückziehen → `antrag` (Stand `zurueckgezogen`, keine Mail; Journal `antrag_zurueckgezogen`); 409 schon entschieden oder zurückgezogen; `GET /api/material/antraege?status=erledigt` schließt `zurueckgezogen` ein (21.10.2026) |
| (Artikel, Übersicht, Meldungen, Kontofolgen) | – | neu: `artikel.antraege` (offene; Begründung und Namen nur für Materialwart und Prüfer, sonst `inhalt: false` – ebenso in `artikel.journal` und im Lebenslauf: ohne `begruendung`, `beantragt_von`, `anmerkung`, `ablehnung`, Handelnder „(Person)“), `artikel.darf_antrag`; `start.antraege_offen` und `meldungen.antraege_offen` (nur Material-Verwaltung, sonst `null`); `material-folgen.antraege` (21.10.2026) |
| `GET /materialablage/ordner/<fid>/bericht` | angemeldet, Modulzugang, lesen am Ordner (sonst 404 wie Systemordner), Grundrecht (externer Prüfer 403) – `bericht_zugang` | Seite „Jahresbericht“ (Ansicht `bericht`, Rahmen mit `{"id": fid}`) (Phase 4 · 1) |
| `GET /api/material/ordner/<fid>/bericht?jahr=<1990…2100>&pruefer=<ja\|nein>` | wie die Seite (401 als JSON) | `bericht` {`dokument`, `kopf` (mit `jahre`, `demo`, `pruefer_nennen`), `bestand`, `bewegungen`, `pruefungen`, `durchgaenge`, `pruefer` (nur mit Haken, sonst `null`), `sperren`, `aussonderungen`, `maengel`, `rueckrufe`, `ausblick`, `fuss`}; jede Listenzeile mit `demo`; 400 bei Unsinn in `jahr`/`pruefer`; `Cache-Control: no-store`; INFO-Logzeile ohne Namen, keine Journalzeile (Phase 4 · 1) |
| `GET /materialablage/ordner/<fid>/bericht-<jahr>.pdf`, `…/bericht-<jahr>-mit-pruefern.pdf` | wie die Seite | der Bericht als PDF/A-3b, inline, nicht festgeschrieben, Listen auf 500 Zeilen je Liste und 1 500 im ganzen PDF gekürzt, je Rückruf höchstens 50 betroffene Artikel (offene zuerst); Dateiname `[DEMO-]Jahresbericht_<Ordner>_<Jahr>[-mit-pruefern].pdf`; 400-Seite bei Jahr außerhalb 1990…2100 (Phase 4 · 1) |
| `GET /materialablage/export/<fid>-pruefungen-<jahr>.csv`, `…-pruefungen-<jahr>-mit-pruefern.csv` | wie die Seite | Prüfungen und Aussonderungen des Jahres im Zweig als CSV (`;`, CRLF, BOM, Formelschutz, ohne Kappung), Spalten `bericht.CSV_SPALTEN`; Prüfer und Urkundennummer nur in der Fassung „-mit-pruefern“ (Phase 4 · 1) |
| `GET /api/material/start` | wie bisher | neu: `mailfehler` – `null`, wenn nichts zu zeigen ist, sonst {`offen`, `zeilen` (höchstens 20, neueste zuerst, nur offene: `id`, `created_at` UTC, `art`, `art_text`, `klasse`, `empfaenger` (Name, „(gelöschtes Konto)“), `rolle`, `bezug_art`, `bezug_id`, `folder_id`, `betreff`, `meldung`, `erledigt_at`, `erledigt_von_name`, `bezug` {`text`, `pfad` (Modul-Route oder `null`)}), `kein_mailserver` (nur Verwaltung), `alle` (Verwaltung)}; Sicht: Material-/Plattform-Verwaltung alles, wer verwaltet, die Zeilen der Ordner in seiner Verwalten-Sicht (Einzelmails tragen die Heimat des Artikels, Sammelmails die Gliederung) ohne die Rollen verwaltung/antragsteller/melder; `betreff` und `meldung` ohne Adresse, Mailserver und Anmeldenamen. `erinnerungen.letzter` ohne `fehlgeschlagen_an` (nur noch `fehlgeschlagen`); `erinnerungen.pflege.mailfehler` {`alt`, `erledigt`, `waisen`} (Phase 4 · 1) |
| `GET /api/material/mailfehler` | Modulzugang mit Sicht (sonst 403) | „Weitere anzeigen“: {`offen`, `zeilen` (höchstens `grenze` = 200, neueste zuerst, Felder wie in `/start`), `grenze`} (Phase 4 · 1, Nachbesserung) |
| `POST /api/material/mailfehler/<mfid>/erledigt` | Modulzugang; Zeile in der eigenen Sicht (sonst 404 „Mailfehler nicht gefunden.“) | abhaken → `zeile`; schon erledigt 200 ohne Änderung (idempotent) (Phase 4 · 1) |
| `POST /api/material/mailfehler/alle-erledigt` | Modulzugang mit Sicht (sonst 403) | alle offenen Zeilen der eigenen Sicht abhaken → `anzahl` (Phase 4 · 1) |
| `POST /api/material/artikel/<id>/aussondern` | wie bisher | neu: `datum` vor der letzten abgeschlossenen Prüfung, vor dem Herstelldatum (Monat → erster Tag) oder vor dem Tag der Sperre (jüngster Journaleintrag frei → gesperrt/verloren, Ortszeit) → 409 mit Klartext; Zukunft und vor der Erfassung weiter 400 (C2, Phase 4 · 1 mit Nachbesserung) |
| `POST /api/material/artikel/<id>/aussondern`, `POST …/pruefungen/<id>/festschreiben`, `GET …/artikel/<id>` | wie bisher | seit Schritt 28: Ergebnis `aussondern` → 400, neu `aussondern_empfohlen` (sperrt); Aussondern nur nach einer letzten Prüfung `instandsetzen`/`aussondern_empfohlen` oder bei `verloren`, sonst 409 mit Grund; Artikel trägt `aussonderung_empfohlen` ({pruefung, protokoll_id, datum, pruefer, grund} bzw. in Listen true/false) und für Materialwarte `aussondern` {ok, grund} |
| `GET /api/material/ordner/<fid>?status=aussonderung_empfohlen`, `GET /api/material/start`; `POST/PUT/DELETE …/freigaben…`, `POST …/ordner/<fid>/verschieben`, `PUT/DELETE /api/admin/users/<id>` | wie bisher | A4: Filter und `empfohlen` (Zahl) am Ordner, `aussonderung_empfohlen` [{ordner_id, gliederung, anzahl}] auf der Übersicht; N5: Antworten tragen `mail` (Mail an die Material-Verwaltung zu Anträgen ohne Materialwart) |
