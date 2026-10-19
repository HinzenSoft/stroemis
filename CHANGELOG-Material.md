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
  gehören zur Geschichte des Artikels. Bitte bestätigen.
- **Telefon und Tablet**: Reiter „Freigaben“ in „Ordner bearbeiten“ (Vorlagen, Karten, Verlängern) und Zuordnen
  (Personensuche, Sammelaktion) auf dem Telefon durchgehen. Am Tablet hochkant und quer (bis etwa 920 px) sind die
  Freigabenlisten jetzt Karten – im Browser nachgemessen, auf einem echten Gerät noch nicht gesehen.
- **Erledigte Zeilen und neue Durchgänge**: Eine schon erledigte Zeile eines offenen Durchgangs sperrt keinen neuen
  mehr (Prüfung vor Auslieferung, Nr. 4) – das gilt auch innerhalb einer Gliederung: Sind alle Artikel eines
  Unterordners im laufenden Durchgang schon geprüft, lässt sich dort ein eigener eröffnen. Bitte bestätigen.
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
- **Protokollinhalt nach EN 365** (aus Lieferung 3): Die zugeordnete Person kommt bewusst nicht ins Protokoll – mit
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
  Plattform-Verwaltung war, sieht weiter alle Bestände, bis jemand Material einzeln senkt. Bitte bestätigen.
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
  DEMO-Konten (Adresse `….invalid`). Jeder bekommt nur, was er sieht. Zugeordnete Personen, Prüfer und der Inhaber
  einer ablaufenden Freigabe bekommen nichts. Bei einer Freigabe werden die offenen Prüfungen des Inhabers im Zweig
  genannt – bei befristetem lesen oder verwalten die, deren dauerhafte Prüffreigabe an diesem Grundrecht hängt.
- **Mail**: eine je Empfänger und Tag, Artikel und Freigaben zusammen, gruppiert nach Ordnerpfad, in der Gruppe nach
  Dringlichkeit. Jede Gruppe steht mit Pfad, Zahl und Link zum Ordner da (Links aus `BASE_URL`). Höchstens 100
  Artikel- und 50 Freigabezeilen je Mail, der Rest einer Gruppe als „… und n weitere in diesem Ordner“. Die Einleitung
  sagt in einem Satz, dass nur Neues drinsteht, mit dem Link auf alles Fällige. Die Fußzeile nennt den Weg zum
  Abschalten, wenn die Mail Artikel nennt; eine Mail nur mit Freigaben sagt, dass die sich immer melden. Keine
  Adressen anderer Personen.
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
    Prüfungen des Inhabers im Zweig werden genannt.

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

### Verfahrensverzeichnis (Ergänzung)

Zweck „Erinnerung an Prüffristen und ablaufende Freigaben“. Empfänger: Verwalter des Ordners (auch Material- oder
Plattform-Verwaltung, wenn dort eingetragen); ohne Verwalter die Material-Verwaltung, ohne sie die
Plattform-Verwaltung. Inhalt: Artikel und Freigaben, die der Empfänger in der Anwendung ohnehin sieht, bei Freigaben
der Name des Inhabers, nie eine Adresse. Erinnerungslog: Artikel bzw. Freigabe, Stufe, Datum, pseudonymer
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

### Zu prüfen

**Bitte bestätigen** (Vorgaben 1–11 oben sind gebaut wie formuliert; dazu die Folgen, die beim Bau festgelegt wurden):

1. **Schalter in der Vorgabe aus**, eingeschaltet wird in der Produktion **im Browser** (nicht in der `.env`, weil
   dev sie kopiert). Danach kommen die ersten Mails binnen 15 Minuten, dann jeden Morgen ab 6 Uhr.
2. **Ab 6:00 Uhr deutscher Zeit**, fest, einmal am Tag; ausgefallene Tage holt der nächste Lauf mit der höchsten
   erreichten Stufe nach.
3. **Der erste Lauf nach dem Einschalten schickt den Rückstand**: jeden schon überfälligen Artikel einmal, alles im
   7- und 30-Tage-Fenster und alles, was in 90 Tagen das Lebensende erreicht – höchstens 100 Zeilen je Mail, der Rest
   einer Gruppe als „… und n weitere“, gilt ebenfalls als gemahnt. Einen „stillen Start“, der den Bestand nur
   vermerkt, gibt es nicht.
4. **Überfällig nur einmal je Fälligkeitsdatum**; erneut frühestens nach 13 Monaten, wenn die Log-Zeile verfallen ist.
5. **Stufen 30/7 fest, Lebensende 90 Tage, Freigaben 30 Tage.** Weitere Stufen bräuchten einen Neuaufbau der Tabelle.
6. **Artikel ohne Fälligkeitsdatum bekommen keine Mail**; „neu“ wird nach dem Datum gemahnt, mit „Eingangsprüfung
   offen“.
7. **Wer neu Empfänger wird** (neuer Materialwart, Artikel verschoben), bekommt am nächsten Morgen einmal alles, was
   dort schon in einem Fenster liegt – das Log gilt je Empfänger.
8. **Empfänger auch Material- und Plattform-Verwaltung, wenn am Ordner eingetragen** (anders als bei Rückruf und
   Meldung), sonst Material-Verwaltung, sonst Plattform-Verwaltung, gekennzeichnet. Eine Plattform-Verwaltung ohne
   Namen bekommt nichts; ihre Artikel stehen im Probelauf unter „Ohne Empfänger“.
9. **Kein Link je Artikel**, ein Link je Ordner – die Mail bleibt lesbar. Die Stufenregeln stehen in der Hilfe der
   Einstellung, nicht in der Mail.
10. **Bei eingeschaltetem Versand ohne `SMTP_HOST`** wird nichts versucht (Hinweis auf der Übersicht).
11. **„Erinnerungsmails aus“ hält Freigabe-Ablaufmails nicht an** – Freigaben sind Rechte, keine Prüffristen.
12. **Laufstand unten als Textlink**, Handlungsbedarf oben gelb; der Probelauf zeigt nach dem Morgenlauf den Lauf von
    morgen.
13. **Ablaufmail ohne den Inhaber**, der die eigene Freigabe nicht verlängern kann; ist er der einzige Verwalter, geht
    sie an die Material-Verwaltung („nur der Inhaber selbst verwaltet hier“, mit „Verlängern“). Freigaben, die kürzer
    als 30 Tage laufen, melden sich am nächsten Morgen. Offene Prüfungen nennt die Mail auch beim Ablauf eines
    befristeten lesen oder verwalten, an dem eine dauerhafte Prüffreigabe hängt.
14. **„Freigabe abgelaufen“**: Der erste Lauf trägt alle früher abgelaufenen Freigaben ins Journal nach (heutiges
    Datum, echtes Enddatum), auch bei ausgeschaltetem Versand.
15. **DEMO-Konten erkennt man an der Adresse `….invalid`** – neu; die Skripte vergeben nur solche.
16. **Kommandozeile**: `--stichtag` nur mit `--trocken`, `--erneut` für einen zweiten Mailteil am selben Tag; Exit 1
    bei Fehlschlag oder Fehler, 2 bei aus, gesperrt, ohne Mailserver oder falschem Aufruf.
17. **Sperre `MATERIAL_ERINNERUNGEN_SPERRE`** nur in der Umgebung; ohne Eintrag an, wenn `STROEMIS_NAME` auf `-dev`
    endet. Einen Notschalter nur für den Thread gibt es nicht.
18. **Einmaligkeit mit einer Lücke**: Endet ein Prozess genau zwischen der Annahme einer Mail und ihrem Vermerk (etwa
    beim Deploy-Neustart kurz nach 6 Uhr), kommt diese eine Mail am nächsten Morgen noch einmal. Umgekehrt (erst
    vermerken, dann senden) ginge bei einem Abbruch eine Mahnung verloren – das schien schlechter.
19. **DEMO im Probelauf nur zur Ansicht** (Nachtrag): Das Kästchen erscheint nur, wenn DEMO ausgelassen wurde. Mit
    Haken zählen auch DEMO-Konten als Empfänger und im Rückfall – eine DEMO-Material-Verwaltung bekommt dann auch die
    echten Gruppen „kein Materialwart eingetragen“ (gekennzeichnet). Der echte Lauf bleibt ohne DEMO.

**Nach dem Deploy**:

- **Auf dev**: Material → Übersicht (als Material- oder Plattform-Verwaltung) zeigt ganz unten „Erinnerungsmails: in
  dieser Umgebung gesperrt“. „Probelauf ansehen“: ohne Haken nichts aus DEMO – DEMO wird absichtlich nie gemahnt;
  „Ausgelassen: n DEMO-Artikel; n DEMO-Freigaben“. Dann das Kästchen **„DEMO-Bestand einbeziehen (nur Ansicht)“**
  anhaken: Die Mails an die DEMO-Materialwarte und die DEMO-Material-Verwaltung erscheinen mit Marke „DEMO“ –
  aufklappen und Betreff und Text ansehen. Hinaus gehen sie nie (auf dev sperrt ohnehin die Sperre). Gelb oben „Der
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

## Schnittstelle (Phase 1 mit den Nachbesserungen, Phase 2 · Lieferung 1 und 2)

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
| `GET/POST /api/material/kategorien`, `PUT/DELETE …/<id>` | lesen / Katalog | Kategoriebaum; Löschen nur leer und ohne Dokument in einem Prüfprotokoll (409) |
| `GET/POST /api/material/produkte`, `GET/PUT/DELETE …/<id>` | lesen / Katalog | Produkte mit Suche (Hersteller, Modell, Bemerkung, Artikelnummer, Norm) und Seiten (`q`, `kategorie`, `seite`, `pro_seite`); `description` (in der Oberfläche „Bemerkung“) beim Speichern höchstens 80 Zeichen, eine Zeile (Nachbesserung vom 18.10.2026) |
| `GET /api/material/produkte/artikelnummer?nr=&ausser=` | lesen | Wem gehört diese Artikelnummer schon? (`produkt` oder `null`) |
| `POST /api/material/produkte/<id>/variante` (Felder wie `POST /produkte`, `dokumente`: Kennungen) | Katalog | Kopie als neue Variante; Bild nie, Dokumente nach Wahl |
| `POST/DELETE /api/material/produkte/<id>/bild` | Katalog | Produktbild |
| `POST /api/material/produkte/<id>/dokumente`, `POST /api/material/dokumente/<id>/version`, `…/zurueckziehen` | Katalog | Herstellerdokumente |
| `GET/POST /api/material/formulare`, `GET/PUT/DELETE …/<id>`, `POST …/<id>/aktivieren`, `…/deaktivieren` | lesen / Katalog | Prüfformulare |
| `GET/POST /api/material/ordner`, `GET/PUT/DELETE …/<id>`, `POST …/<id>/verschieben`, `POST/DELETE …/<id>/foto` | lesen / Materialwart (Löschen: am Oberordner; Gliederung auf oberster Ebene anlegen und löschen: Material-Verwaltung) | Ordnerbaum; über Gliederungsgrenzen verschiebt nur, wer beide Gliederungen verwaltet, und zur Gliederung macht einen Ordner (`PUT` mit `kind: "gliederung"`) nur, wer die bisherige verwaltet (Phase 2) |
| `GET /api/material/artikel/vorschlag` | Modulzugang; mit `folder_id` lesen dort (sonst 404) | Vorschläge (Intervall, nächste Prüfung, Lebensende) vor dem Anlegen |
| `POST /api/material/artikel`, `GET/PUT/DELETE …/<id>`, `POST /api/material/artikel/verschieben` | lesen / Materialwart | Artikel, auch mehrere auf einmal verschieben |
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
| `GET/PUT/DELETE /api/material/pruefungen/<id>` | lesen / Prüfer / Prüfer oder Materialwart | Prüfung lesen; Art und Bemerkung am Entwurf; Entwurf verwerfen bzw. Reservierung freigeben |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>`, `POST/DELETE …/foto` | Prüfer (eigener Entwurf) | Befund, Wert, Bemerkung, Foto je Prüfpunkt |
| `POST /api/material/pruefungen/<id>/anhaenge` (`file` mehrfach, `art`, `titel`, `im_protokoll`), `DELETE …/<aid>` | Prüfer (eigener Entwurf) | Anhänge |
| `POST /api/material/pruefungen/<id>/festschreiben` (`ergebnis`, `next_due_on`, `grund`, `bemerkung`; alter Pfad `…/abschliessen` gilt weiter) | Prüfer (eigener Entwurf, mit Unterschrift) | Abschluss und Festschreiben mit Protokoll |
| `POST /api/material/pruefungen/<id>/berichtigen` (`grund`) | Prüfer (der die Prüfung gemacht hat) | Berichtigung beginnen; liefert den neuen Entwurf |
| `PUT /api/material/pruefungen/<id>/punkte/<pid>` mit `unterschrift` (data:-URL oder `null`) | Prüfer (eigener Entwurf) | Unterschriftsfeld eines Formulars |
| `GET/PUT/DELETE /api/material/unterschrift` (`bild`: data:-URL vom Signatur-Pad) | GET und DELETE angemeldet (eigene Daten, auch ohne Modulzugang); PUT mit Modulzugang nur Prüfer (seit Lieferung 5 schon mit dem Häkchen, ohne Urkundennummer) und wer irgendwo verwaltet (eigenes Konto) | eigene Unterschrift im Profil |
| `PUT /api/material/urkundennummer` (`urkundennummer`; leer entfernt sie) | Häkchen „Prüfer“ (eigenes Konto), sonst 403 | eigene Urkundennummer im Profil; Antwort `urkundennummer`, `pruefen` (darf jetzt prüfen); ungültig 400 (Lieferung 5) |
| `GET /material/pruefung/<id>/pdf`, `GET /material/durchgang/<id>/sammelprotokoll` | lesen | Protokoll als PDF (nur, solange die Datei ihre Prüfsumme hat) |
| `GET /material/pruefen`, `POST /api/material/pruefen` (`datei`) | ohne Anmeldung | Prüfseite: `ergebnis` (unveraendert, veraendert, unbekannt), `protokoll_id`, `art`, `hinweis` – angemeldet mit Zugang dazu `link` |
| `GET /api/material/entwuerfe` | Modulzugang | offene Prüfungen aller Prüfer im eigenen Bereich |
| `POST /api/material/artikel/<id>/sperren` (`grund`: sturz, beschaedigung, verlust, rueckruf; `text`) | Prüfer | Sperre ohne Prüfung |
| `POST /api/material/artikel/<id>/aussondern` (`grund`: lebensdauer, verlust, irreparabel; `datum`, `bemerkung`) | Materialwart (mit Unterschrift) | Aussonderung gesperrter Artikel mit Aussonderungsprotokoll; liefert `aussonderung` (Kennung) |
| `GET/POST /api/material/durchgaenge`, `GET/DELETE …/<id>` | lesen / Materialwart oder Prüfer | Prüfdurchgänge (`?offen=1`); eröffnen (`folder_id`, `titel`); löschen, solange nichts geprüft ist |
| `POST /api/material/durchgaenge/<id>/ausnehmen`, `…/einbeziehen` (`item_id`, `grund`), `…/abschliessen` | Materialwart oder Prüfer | Artikel ausnehmen, wieder einbeziehen, Durchgang abschließen (mit Sammelprotokoll) |
| `POST /api/material/durchgaenge/<id>/abbrechen` | Materialwart oder Prüfer | vorzeitig beenden; `durchgang` ist `null`, wenn er mangels Geprüftem entfernt wurde |
| `GET /material/export/<ordner>.csv` | Grundrecht am Ordner (Phase 2) | Artikel, deren Heimat im Ordner oder darunter liegt (auch von hier gesperrte und ausgesonderte), als CSV für Excel; Spalte „Zugeordnet an“ (Phase 2), hinter „Modell“ „Bemerkung (Produkt)“ (Nachbesserung vom 18.10.2026) |
| `GET /material/export/<ordner>-protokolle.zip` | Grundrecht am Ordner (Phase 2) | alle Protokolle dieser Artikel und die Sammelprotokolle der Durchgänge im Zweig, mit `Verzeichnis.csv` |
| `GET /material/artikel/<id>/lebenslauf.pdf` | Grundrecht an der Heimat (Phase 2) | Lebenslauf als PDF/A-3b, auf Abruf, nicht festgeschrieben |
| `GET /api/material/katalog/export`, `GET …/export/vorschau` | Katalog | Katalog ohne DEMO als ZIP (Format 2) bzw. seine Zahlen vorab |
| `POST /api/material/katalog/import` (`file`: ZIP oder JSON, `trocken`: Vorgabe `1`) | Katalog | Katalogimport; Antwort `bericht` (neu/geändert/unverändert je Art, Bilder, Dokumente, Änderungen, Hinweise, Warnungen, Fehler) |
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
| `GET /api/material/erinnerungen/probelauf` | Material-Verwaltung (Plattform-Verwaltung eingeschlossen) | Probelauf der Erinnerungsmails für den nächsten Lauf (heute oder, wenn heute schon verschickt wurde, morgen): `stichtag`, `morgen`, `versand`, `gesperrt`, `smtp`, `letzter` (`tag`, `beginn`, `mails`, `fehlgeschlagen`, `fehlgeschlagen_an`, `fehler`), `mails` (`name`, `gliederung`, `betreff`, `text`, `artikel`, `freigaben` – keine Adressen), `ohne_empfaenger` (`ordner`, `artikel`, `freigaben`), `ausgelassen` (`ordner_aus`: `id`, `pfad`, `artikel`; `demo`, `demo_freigaben`), `fehlerhaft`, `demo`; `mails` je mit `demo`; `?demo=1` bezieht den DEMO-Bestand ein – nur Ansicht, DEMO-Mails gekennzeichnet, gehen nie hinaus; schreibt nichts (Phase 2 · 2) |
| `GET /api/material/ordner/<id>` | lesen | neu: `ordner.reminders_off` (eigener Wert) und `ordner.erinnerungen` = `{aus, eigen, geerbt_von: {id, pfad, sichtbar} \| null}`; Ordnerbaum mit `reminders_off` (Phase 2 · 2) |
| `PUT /api/material/ordner/<id>` mit `reminders_off` (ja/nein) | Materialwart am Ordner | „Erinnerungsmails aus“ für Ordner und Unterordner; fehlt das Feld, bleibt der Wert; anderes als ja/nein → 400; mit Journal (Phase 2 · 2) |
| `flask --app "app:create_app()" material remind [--trocken [--demo]] [--stichtag JJJJ-MM-TT] [--erneut]` | Kommandozeile im Container | Erinnerungslauf: `--trocken` zeigt die Mails des nächsten Laufs mit Adressen und schreibt nichts (auch bei „aus“ oder gesperrt), `--stichtag` und `--demo` (DEMO-Bestand einbeziehen, nur Ansicht) nur mit `--trocken`; ohne `--trocken` ein echter Lauf für heute (nie DEMO), `--erneut` noch einmal am selben Tag (nur, was nicht im Log steht). Exit 0, 1 (Mail gescheitert, Fehler), 2 (aus, gesperrt, kein Mailserver, `--stichtag` oder `--demo` ohne `--trocken`, unlesbares Datum) (Phase 2 · 2) |
