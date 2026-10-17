# Changelog: Modul „Material“ (Phase 1, MVP)

Material- und Prüfmanagement für strömis.de nach dem Konzept vom 16.10.2026: Ausrüstungsbestand der
Gliederungen, Prüfnachweise je Ausrüstungsteil, später unveränderliche PDF-Prüfprotokolle. Umgesetzt in vier
Lieferungen; jede ist für sich deploybar.

| Lieferung | Inhalt | Stand |
| --- | --- | --- |
| 1 – Fundament | Schema, Migration, Rollen, Katalog mit Dokumenten und Formularen, Ordnerbaum, Artikel, Suche, Journal | geliefert 16.10.2026, freigegeben 17.10.2026 |
| 2 – Prüfung | Prüfformular, Mangelfoto, Anhänge, Ergebnis, Sperre, Aussonderung, Lebenslauf, Prüfdurchgang; dazu Status „neu“ mit Eingangsprüfung, Prüfen jederzeit, Ordnernavigation | geliefert 17.10.2026, freigegeben 17.10.2026 |
| 3 – Nachweis | Unterschrift, Festschreiben, PDF mit Prüfsumme, Prüfseite; dazu Berichtigung und Unterschriftsfelder | geliefert 17.10.2026, freigegeben 17.10.2026 |
| 4 – Überblick | Übersicht mit Fälligkeiten je Ordner, Führungskraft nur lesend, QR-Adresse mit Status, Export (CSV, Protokoll-ZIP, Lebenslauf-PDF); dazu Katalogaustausch (Katalog und Formulare von dev in die Produktion, ohne Bestand und Prüfungen) und Rückrufe zu Produkten (Hinweis in der Anwendung und per Mail). Kein Etikettenbogen (nicht gewünscht) | geliefert 17.10.2026, freigegeben 17.10.2026 |
| 5 – Feinschliff | Rückmeldungen aus dem Pilotbetrieb: Bedienung am Telefon, auf Foldables und Tablets; Ordnerkopf aufgeräumt | in Arbeit |

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
  für Ansicht und Druck. Bitte bestätigen, dass die Lizenz der DLRG das für PDF-Protokolle abdeckt.
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
  Rückrufs (alle betroffenen Artikel samt Ablage) müssen dann nach Leserecht filtern.
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

## Lieferung 5 – Feinschliff nach Pilot (in Arbeit)

Rückmeldungen aus dem Pilotbetrieb. Lieferung 4 wurde am 17.10.2026 mit „Lieferung 5 starten“ freigegeben.

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
| `materialart` | `textil`, `metall_hardware` oder `sonstiges` (an der Kategorie: Vorgabe für Produkte) |
| `intervall_monate` | Prüfintervall 1–120; am Produkt optional, wenn die Kategorie eins vorgibt |
| `lebensdauer_jahre` | 1–50; Produkt textil: Pflicht; Metall (`metall_hardware`): verboten; sonstiges: nur mit `lebensdauer_quelle`. An der Kategorie nur bei textil, nur als Vorschlag |
| `kategorie` | Pfad als Liste von Namen oder als Text „Ober / Unter“ |
| `formulare[].kategorie` / `.produkt` | generisch je Kategorie oder spezifisch je Produkt (Hersteller, Modell, Artikelnummer) |
| `aktivieren` | Standard `true`: die Version wird aktiv, eine ältere aktive des Ziels inaktiv |
| `punkte[].text` | der Prüfpunkt bzw. die Prüfanweisung, höchstens 1000 Zeichen |
| `punkte[].art` | `yesno`, `text`, `date`, `number`, `photo`, `signature` |
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
     "materialart": null, "intervall_monate": null, "lebensdauer_jahre": null, "position": 0,
     "unterkategorien": [
       {"uid": "fa0924f611f67a059a66fa70610d8495", "name": "Gurte", "norm": "EN 361, EN 12277 oder EN 813",
        "materialart": "textil", "intervall_monate": 12, "lebensdauer_jahre": null, "position": 0,
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
| `kategorie_uid` (Produkt, generisches Formular) | Kategorie über ihre uid; gibt es sie hier nicht, gilt `kategorie` (Pfad) |
| `produkt.uid` (spezifisches Formular) | Produkt über seine uid; sonst Hersteller + Modell + Artikelnummer |
| `bild` (Produkt) | Pfad im Archiv; Foto (JPEG, PNG, WebP, HEIC, TIFF), höchstens 31 MB (wie beim Hochladen) und 60 Megapixel. Gleiche SHA-256 wie das Original hier: unverändert; sonst ersetzt. Fehlt es, bleibt das Bild hier |
| `dokumente[]` (Kategorie, Produkt) | `art` (`produktbild`, `konformitaetserklaerung`, `gebrauchsanleitung`, `pruefanweisung`, `pflegehinweis`, `datenblatt`, `sonstiges`), `titel`, `version`, `gueltig_ab` (JJJJ-MM-TT) und entweder `datei` (Pfad im Archiv; PDF oder Bild, Inhalt muss zur Endung passen, höchstens 50 MB) oder `url` (`https://…`) |
| `vorgaenger` (Dokument) | Kennungen der früheren Versionen dieses Dokuments, neueste zuerst: je Version `{"sha256": …}` (Datei) oder `{"url": …, "version": …}` (Link). Der Export schreibt sie mit, sobald ein Dokument Vorgänger hat. Optional |
| Abgleich der Dokumente | Je Ziel in drei Schritten: 1. gleiche Datei (SHA-256) bzw. gleicher Link in gleicher Version unter den aktuellen: unverändert – zuerst für alle Einträge des Ziels; 2. ist eins der aktuellen Dokumente hier unter den `vorgaenger`: neue Version davon; 3. sonst gleiche Art und gleicher Titel – nur, wenn genau eins davon bei `gueltig_ab` schon gilt; bei mehreren ein Fehler („Mehrdeutig“), damit keine Versionsketten über Kreuz verknüpft werden; sonst neues Dokument. Eine neue Version gilt nie früher als die vorhandene |
| `titel` (Formular) | Leer heißt: kein Titel vorgegeben – verglichen werden dann nur die Prüfpunkte; eine neue Version erbt den Titel der letzten hier |
| `aktivieren` (Formular) | Der Export schreibt `true` für das aktive Formular eines Ziels, `false` für die neueste Version, wenn keins aktiv ist |
| `quelle`, `erstellt` | woher und wann (nur zur Anzeige) |

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

## Schnittstelle (Lieferungen 1 bis 4, mit den Nachbesserungen)

| Methode und Pfad | Recht | Zweck |
| --- | --- | --- |
| `GET /api/material/start` | lesen | Rechte des Kontos, Zählung, Gliederungen, nächste Fälligkeiten; `ordner_uebersicht` (Fälligkeiten je Ordner, Zeilen in Baumreihenfolge mit `tiefe`, `bestand`, `zaehlung`, `naechste`), `rueckrufe` (laufende mit betroffenen Artikeln im Bestand) |
| `GET /api/material/suche?q=` | lesen | Artikel nach Serien-, Inventar-, Herstellernummer; `eindeutig` bei genau einem Treffer |
| `GET /api/material/faellig?status=&ordner=` | lesen | fällige Artikel, Standard überfällig + Lebensdauer erreicht + neu + bald fällig; mit `ordner` auch `ordner` = {id, pfad} |
| `GET/POST /api/material/kategorien`, `PUT/DELETE …/<id>` | lesen / Katalog | Kategoriebaum |
| `GET/POST /api/material/produkte`, `GET/PUT/DELETE …/<id>` | lesen / Katalog | Produkte mit Suche und Seiten (`q`, `kategorie`, `seite`, `pro_seite`) |
| `GET /api/material/produkte/artikelnummer?nr=&ausser=` | lesen | Wem gehört diese Artikelnummer schon? (`produkt` oder `null`) |
| `POST /api/material/produkte/<id>/variante` (Felder wie `POST /produkte`, `dokumente`: Kennungen) | Katalog | Kopie als neue Variante; Bild nie, Dokumente nach Wahl |
| `POST/DELETE /api/material/produkte/<id>/bild` | Katalog | Produktbild |
| `POST /api/material/produkte/<id>/dokumente`, `POST /api/material/dokumente/<id>/version`, `…/zurueckziehen` | Katalog | Herstellerdokumente |
| `GET/POST /api/material/formulare`, `GET/PUT/DELETE …/<id>`, `POST …/<id>/aktivieren`, `…/deaktivieren` | lesen / Katalog | Prüfformulare |
| `GET/POST /api/material/ordner`, `GET/PUT/DELETE …/<id>`, `POST …/<id>/verschieben`, `POST/DELETE …/<id>/foto` | lesen / Materialwart | Ordnerbaum |
| `GET /api/material/artikel/vorschlag` | lesen | Vorschläge (Intervall, nächste Prüfung, Lebensende) vor dem Anlegen |
| `POST /api/material/artikel`, `GET/PUT/DELETE …/<id>`, `POST /api/material/artikel/verschieben` | lesen / Materialwart | Artikel, auch mehrere auf einmal verschieben |
| `GET /media/material/<orig|web|thumb|dok|anhang>/<datei>` | lesen | Fotos, Dokumente, Prüfanhänge; privat, strenge CSP |
| `GET/POST /api/material/kategorien/<id>/dokumente` | lesen / Katalog | Dokumente für alle Produkte einer Kategorie |
| `PUT /api/material/dokumente/<id>` (`title`) | Katalog | Dokument umbenennen (Produkt- oder Kategoriedokument) |
| `POST /api/material/meldungen` (`manufacturer`, `model`, `article_no`, `norm`, `category_id`, `folder_id`, `links`, `note`; `fotos` mehrfach) | Materialwart | Fehlendes Produkt melden |
| `GET /api/material/meldungen?status=offen\|erledigt\|alle&eigene=0\|1`, `GET …/<id>` | lesen | Meldungen; Katalogpfleger und Lesende standardmäßig alle offenen, Materialwarte die eigenen; `bearbeiten` nur für Katalogpfleger |
| `POST /api/material/meldungen/<id>/produkt` (Felder wie `POST /produkte`, dazu `antwort`) | Katalog | Produkt aus der Meldung anlegen und Meldung erledigen |
| `POST /api/material/meldungen/<id>/zuordnen` (`product_id`, `antwort`), `…/ablehnen` (`antwort` Pflicht) | Katalog | vorhandenes Produkt zuordnen bzw. ablehnen |
| `DELETE /api/material/meldungen/<id>` | nur der Melder | eigene Meldung löschen (offen oder erledigt; ein Produkt aus ihr bleibt) |
| `?sort=<spalte>&richtung=auf|ab` an `produkte`, `ordner/<id>`, `faellig`, `suche` | – | Sortierung: Katalog `hersteller`, `produkt`, `kategorie`, `materialart`, `intervall`, `lebensdauer`, `bestand`; Artikel `inventar`, `hersteller`, `produkt`, `serie`, `faellig`, `status` |
| `GET/POST /api/material/artikel/<id>/pruefungen` | lesen / Prüfer | Prüfungen eines Artikels; Prüfung beginnen (`art`, `durchgang_id`) – oder den eigenen Entwurf fortsetzen |
| `GET/PUT/DELETE /api/material/pruefungen/<id>` | lesen / Prüfer / Prüfer oder Materialwart | Prüfung lesen; Art und Bemerkung am Entwurf; Entwurf verwerfen bzw. Reservierung freigeben |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>`, `POST/DELETE …/foto` | Prüfer (eigener Entwurf) | Befund, Wert, Bemerkung, Foto je Prüfpunkt |
| `POST /api/material/pruefungen/<id>/anhaenge` (`file` mehrfach, `art`, `titel`, `im_protokoll`), `DELETE …/<aid>` | Prüfer (eigener Entwurf) | Anhänge |
| `POST /api/material/pruefungen/<id>/festschreiben` (`ergebnis`, `next_due_on`, `grund`, `bemerkung`; alter Pfad `…/abschliessen` gilt weiter) | Prüfer (eigener Entwurf, mit Unterschrift) | Abschluss und Festschreiben mit Protokoll |
| `POST /api/material/pruefungen/<id>/berichtigen` (`grund`) | Prüfer (der die Prüfung gemacht hat) | Berichtigung beginnen; liefert den neuen Entwurf |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>` mit `unterschrift` (data:-URL oder `null`) | Prüfer (eigener Entwurf) | Unterschriftsfeld eines Formulars |
| `GET/PUT/DELETE /api/material/unterschrift` (`bild`: data:-URL vom Signatur-Pad) | lesen; PUT nur Prüfer und Materialwart (eigenes Konto) | eigene Unterschrift im Profil |
| `GET /material/pruefung/<id>/pdf`, `GET /material/durchgang/<id>/sammelprotokoll` | lesen | Protokoll als PDF (nur, solange die Datei ihre Prüfsumme hat) |
| `GET /material/pruefen`, `POST /api/material/pruefen` (`datei`) | ohne Anmeldung | Prüfseite: `ergebnis` (unveraendert, veraendert, unbekannt), `protokoll_id`, `art`, `hinweis` – angemeldet mit Zugang dazu `link` |
| `GET /api/material/entwuerfe` | lesen | offene Prüfungen aller Prüfer |
| `POST /api/material/artikel/<id>/sperren` (`grund`: sturz, beschaedigung, verlust, rueckruf; `text`) | Prüfer | Sperre ohne Prüfung |
| `POST /api/material/artikel/<id>/aussondern` (`grund`: lebensdauer, verlust, irreparabel; `datum`, `bemerkung`) | Materialwart (mit Unterschrift) | Aussonderung gesperrter Artikel mit Aussonderungsprotokoll; liefert `aussonderung` (Kennung) |
| `GET/POST /api/material/durchgaenge`, `GET/DELETE …/<id>` | lesen / Materialwart oder Prüfer | Prüfdurchgänge (`?offen=1`); eröffnen (`folder_id`, `titel`); löschen, solange nichts geprüft ist |
| `POST /api/material/durchgaenge/<id>/ausnehmen`, `…/einbeziehen` (`item_id`, `grund`), `…/abschliessen` | Materialwart oder Prüfer | Artikel ausnehmen, wieder einbeziehen, Durchgang abschließen (mit Sammelprotokoll) |
| `POST /api/material/durchgaenge/<id>/abbrechen` | Materialwart oder Prüfer | vorzeitig beenden; `durchgang` ist `null`, wenn er mangels Geprüftem entfernt wurde |
| `GET /material/export/<ordner>.csv` | lesen | Artikel des Ordners samt Unterordnern (und von hier gesperrte) als CSV für Excel |
| `GET /material/export/<ordner>-protokolle.zip` | lesen | alle Protokolle dieser Artikel und die Sammelprotokolle der Durchgänge im Zweig, mit `Verzeichnis.csv` |
| `GET /material/artikel/<id>/lebenslauf.pdf` | lesen | Lebenslauf als PDF/A-3b, auf Abruf, nicht festgeschrieben |
| `GET /api/material/katalog/export`, `GET …/export/vorschau` | Katalog | Katalog ohne DEMO als ZIP (Format 2) bzw. seine Zahlen vorab |
| `POST /api/material/katalog/import` (`file`: ZIP oder JSON, `trocken`: Vorgabe `1`) | Katalog | Katalogimport; Antwort `bericht` (neu/geändert/unverändert je Art, Bilder, Dokumente, Änderungen, Hinweise, Warnungen, Fehler) |
| `GET /api/material/produkte/<id>/rueckrufe` | lesen | Rückrufe des Produkts: laufende mit betroffenen Artikeln, Zahlen und nicht gefundenen Seriennummern, beendete mit Vermerk |
| `POST /api/material/produkte/<id>/rueckrufe` (`title`, `description`, `url`, `serials`, `mail`) | Katalog | Rückruf anlegen; Antwort mit betroffenen Artikeln, Empfängerzahl, nicht gefundenen Seriennummern |
| `POST /api/material/rueckrufe/<id>/beenden` (`vermerk` Pflicht) | Katalog | Rückruf beenden |
| `GET /api/material/rueckrufe` | lesen | alle laufenden Rückrufe mit Produkt und Zahlen |
| (Artikel, Produkt, Listen) | lesen | neu: `artikel.rueckrufe` (laufende samt Zustand), `produkt.rueckrufe`, je Listenzeile `rueckruf` (Titel eines offenen) |
