# Changelog: Modul „Material“ (Phase 1, MVP)

Material- und Prüfmanagement für strömis.de nach dem Konzept vom 16.10.2026: Ausrüstungsbestand der
Gliederungen, Prüfnachweise je Ausrüstungsteil, später unveränderliche PDF-Prüfprotokolle. Umgesetzt in vier
Lieferungen; jede ist für sich deploybar.

| Lieferung | Inhalt | Stand |
| --- | --- | --- |
| 1 – Fundament | Schema, Migration, Rollen, Katalog mit Dokumenten und Formularen, Ordnerbaum, Artikel, Suche, Journal | geliefert 16.10.2026, freigegeben 17.10.2026 |
| 2 – Prüfung | Prüfformular, Mangelfoto, Anhänge, Ergebnis, Sperre, Aussonderung, Lebenslauf, Prüfdurchgang; dazu Status „neu“ mit Eingangsprüfung, Prüfen jederzeit, Ordnernavigation | geliefert 17.10.2026 |
| 3 – Nachweis | Unterschrift, Festschreiben, PDF mit Prüfsumme, Prüfseite | offen |
| 4 – Überblick | Dashboard, QR-Etiketten, Export | offen |

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

## Schnittstelle (Lieferungen 1 und 2, mit den Nachbesserungen)

| Methode und Pfad | Recht | Zweck |
| --- | --- | --- |
| `GET /api/material/start` | lesen | Rechte des Kontos, Zählung, Gliederungen, nächste Fälligkeiten |
| `GET /api/material/suche?q=` | lesen | Artikel nach Serien-, Inventar-, Herstellernummer; `eindeutig` bei genau einem Treffer |
| `GET /api/material/faellig?status=&ordner=` | lesen | fällige Artikel, Standard überfällig + neu + bald fällig |
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
| `GET /api/material/meldungen?status=offen\|erledigt\|alle&eigene=1`, `GET …/<id>` | Katalog / Materialwart (eigene) | Meldungen; Katalogpfleger alle (Standard offen), sonst die eigenen |
| `POST /api/material/meldungen/<id>/produkt` (Felder wie `POST /produkte`, dazu `antwort`) | Katalog | Produkt aus der Meldung anlegen und Meldung erledigen |
| `POST /api/material/meldungen/<id>/zuordnen` (`product_id`, `antwort`), `…/ablehnen` (`antwort` Pflicht) | Katalog | vorhandenes Produkt zuordnen bzw. ablehnen |
| `DELETE /api/material/meldungen/<id>` | nur der Melder | eigene Meldung löschen (offen oder erledigt; ein Produkt aus ihr bleibt) |
| `?sort=<spalte>&richtung=auf|ab` an `produkte`, `ordner/<id>`, `faellig`, `suche` | – | Sortierung: Katalog `hersteller`, `produkt`, `kategorie`, `materialart`, `intervall`, `lebensdauer`, `bestand`; Artikel `inventar`, `hersteller`, `produkt`, `serie`, `faellig`, `status` |
| `GET/POST /api/material/artikel/<id>/pruefungen` | lesen / Prüfer | Prüfungen eines Artikels; Prüfung beginnen (`art`, `durchgang_id`) – oder den eigenen Entwurf fortsetzen |
| `GET/PUT/DELETE /api/material/pruefungen/<id>` | lesen / Prüfer / Prüfer oder Materialwart | Prüfung lesen; Art und Bemerkung am Entwurf; Entwurf verwerfen bzw. Reservierung freigeben |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>`, `POST/DELETE …/foto` | Prüfer (eigener Entwurf) | Befund, Wert, Bemerkung, Foto je Prüfpunkt |
| `POST /api/material/pruefungen/<id>/anhaenge` (`file` mehrfach, `art`, `titel`, `im_protokoll`), `DELETE …/<aid>` | Prüfer (eigener Entwurf) | Anhänge |
| `POST /api/material/pruefungen/<id>/abschliessen` (`ergebnis`, `next_due_on`, `grund`, `bemerkung`) | Prüfer (eigener Entwurf) | Abschluss |
| `GET /api/material/entwuerfe` | lesen | offene Prüfungen aller Prüfer |
| `POST /api/material/artikel/<id>/sperren` (`grund`: sturz, beschaedigung, verlust; `text`) | Prüfer | Sperre ohne Prüfung |
| `POST /api/material/artikel/<id>/aussondern` (`grund`: lebensdauer, verlust, irreparabel; `datum`, `bemerkung`) | Materialwart | Aussonderung gesperrter Artikel |
| `GET/POST /api/material/durchgaenge`, `GET/DELETE …/<id>` | lesen / Materialwart oder Prüfer | Prüfdurchgänge (`?offen=1`); eröffnen (`folder_id`, `titel`); löschen, solange nichts geprüft ist |
| `POST /api/material/durchgaenge/<id>/ausnehmen`, `…/einbeziehen` (`item_id`, `grund`), `…/abschliessen` | Materialwart oder Prüfer | Artikel ausnehmen, wieder einbeziehen, Durchgang abschließen |
| `POST /api/material/durchgaenge/<id>/abbrechen` | Materialwart oder Prüfer | vorzeitig beenden; `durchgang` ist `null`, wenn er mangels Geprüftem entfernt wurde |
