# Changelog: Bereich „Prüfungen“ (Stand 27.09.2026)

Erweiterung von strömis.de um Lehrgänge, Teilnehmende, Voraussetzungen, Prüfungsleistungen, Bewertungen mit
Stoppuhr, Nachprüfungen, Medien und eine Mängelübersicht für Feedbackrunden – nur für Nutzer mit dem neuen
Zusatzrecht „Prüfer“.

## Neue Dateien

| Datei | Inhalt |
|---|---|
| `app/api_pruefungen.py` | Blueprint `/api/pruefungen`: Lehrgänge (Liste mit Suche/Jahr/Fortschritt, Anlegen, Bearbeiten, Löschen, Kopieren), Teilnehmende, Voraussetzungen samt Status und Verlauf, Prüfungsleistungen mit Reihenfolge, Versuche (Bewertung, Bearbeitung mit Verlauf, Nachprüfung, Löschen des letzten Versuchs), Medien-Upload und -Auslieferung, Mängelübersicht, Excel-Import (Vorschau und Übernahme) |
| `app/pruefungen_import.py` | Excel-Erkennung ohne Flask/Datenbank: Kopfzeile finden, Lehrgangsdaten aus den Kopfzeilen lesen, Spalten zuordnen, ja/nein/Datum als „erfüllt“ deuten, Duplikate und Leerzeilen melden |
| `app/templates/pruefungen.html` | Seite für Lehrgangsliste, Lehrgang (Reiter Teilnehmende, Leistungen, Bewertung, Mängel) und Druckansicht |
| `app/static/js/pruefungen.js` | Oberfläche des Bereichs: Dialoge, Bewertungsmatrix, Stoppuhr, Medien-Upload mit Fortschritt, Mängelübersicht, Import-Vorschau |
| `app/static/css/pruefungen.css` | Gestaltung des Bereichs (DLRG-CD, mobil zuerst, Druck) |
| `tests/test_pruefungen.py` | Rauchtests der Abnahmekriterien über die API |
| `tests/test_pruefungen_import.py` | Tests der Excel-Erkennung mit synthetischen Dateien |
| `CHANGELOG-Pruefungen.md` | diese Datei |

## Geänderte Dateien

| Datei | Änderung |
|---|---|
| `app/db.py` | Zehn neue Tabellen (siehe unten); Migration `users.is_pruefer` |
| `app/auth.py` | `is_pruefer()`, Decorator `pruefer_required`, `public_user()` liefert `is_pruefer` |
| `app/api_admin.py` | Nutzer anlegen/bearbeiten nimmt `is_pruefer` an |
| `app/static/js/admin.js` | Checkbox „Prüfer“ im Nutzerdialog, Marke „Prüfer“ in der Rollenspalte |
| `app/templates/base.html` | Reiter „Prüfungen“ (nur mit Flag), `STROEMIS.user.is_pruefer` |
| `app/__init__.py` | Blueprint registriert; Seitenrouten `/pruefungen`, `/pruefungen/<id>`, `/pruefungen/<id>/druck` (403 ohne Flag); geschützte Medienroute `/media/pruefung/<kind>/<datei>`; Upload-Endpunkte in `GROSSE_UPLOADS`; Template-Kontext `is_pruefer` |
| `app/einstellungen.py` | Hilfetext zur Upload-Grenze erwähnt Prüfungsmedien |
| `requirements.txt` | `openpyxl==3.1.5` |
| `README.md` | Funktionsübersicht, Aufbau, Testaufrufe |

## Neue Tabellen

`pruef_lehrgaenge`, `pruef_ausbilder`, `pruef_teilnehmer`, `pruef_voraussetzungen`, `pruef_voraussetzung_status`,
`pruef_voraussetzung_verlauf`, `pruef_leistungen`, `pruef_versuche`, `pruef_versuch_verlauf`, `pruef_medien`.
Alle werden beim Start mit `CREATE TABLE IF NOT EXISTS` angelegt (wie bisher); vorhandene Daten bleiben unberührt.
Neue Spalte: `users.is_pruefer` (additiv, Vorgabe 0).

## Neue Abhängigkeiten

- `openpyxl==3.1.5` (Python, .xlsx lesen). Keine neuen JavaScript-Bibliotheken – Toast UI, marked und DOMPurify liegen
  bereits unter `app/static/vendor/`.
- Dockerfile unverändert: `COPY app ./app` nimmt die neuen Dateien mit, `pip install -r requirements.txt` zieht openpyxl.

## Medien

Bilder und Videos zu Prüfungen liegen unter `<DATA_DIR>/media/pruefungen/{orig,web,thumb}` (Original, Web-Variante,
Thumbnail bzw. Poster-Frame). Videos werden wie in den Alben nach H.264 gewandelt, das Standbild kommt aus ffmpeg oder vom
Browser; ohne ffmpeg bleibt ein Platzhalter mit Play-Dreieck. Ausgeliefert wird ausschließlich über
`/media/pruefung/<kind>/<datei>` – ohne Anmeldung 401, ohne Prüfer-Flag 403, `Cache-Control: private`.

## Getroffene Annahmen

- **Nur das Flag zählt.** Auch ein Administrator sieht den Bereich erst, wenn er sich das Zusatzrecht „Prüfer“ in der
  Nutzerverwaltung gibt. So ist das Abnahmekriterium „Benutzer ohne Rolle Prüfer sehen den Tab nicht“ wörtlich erfüllt
  und der Kreis derer, die Teilnehmerdaten sehen, bleibt bewusst klein.
- **Alle Prüfer sehen alle Lehrgänge.** Es gibt keine Zuordnung von Prüfern zu einzelnen Lehrgängen; ein Prüfer darf jeden
  Lehrgang anlegen, bearbeiten, bewerten und löschen. Für eine Ortsgruppe mit einem festen Prüferkreis ist das der
  gewünschte Ablauf; eine Beschränkung je Lehrgang ließe sich über die Ausbilderliste nachrüsten.
- **Nachvollziehbarkeit übersteht Kontolöschungen.** Zu jeder Bewertung, jedem Haken und jedem Medium wird neben der
  Nutzer-ID der Name als Schnappschuss gespeichert. Wird ein Konto gelöscht, bleibt „abgenommen von M. Müller“ lesbar.
- **Letzter Versuch ist maßgeblich.** Der Zellstatus in der Matrix folgt dem Versuch mit der höchsten Nummer; eine
  Nachprüfung ist nur nach einer mangelhaften Bewertung möglich, beliebig oft hintereinander. Gelöscht werden kann nur der
  jeweils letzte Versuch einer Zelle – so bleibt die Reihenfolge lückenlos.
- **Bearbeiten statt Doppelbewertung.** Gibt es zu einer Zelle schon einen Versuch und der letzte ist bestanden, wird
  keine weitere Bewertung angelegt; die vorhandene lässt sich bearbeiten (mit „bearbeitet von … am …“ und Verlauf).
- **Kopie ohne Nummer.** Beim Kopieren eines Lehrgangs wird die Lehrgangsnummer geleert – sie bezeichnet eine
  Durchführung und wäre in der Kopie falsch. Status der Kopie ist „geplant“.
- **Import stellt zurückgesetzte Haken nicht zurück.** Steht eine Voraussetzung in der Excel auf „nein“, während sie im
  System manuell abgehakt wurde, bleibt der Haken. Die Datei ergänzt, sie löscht nicht.
- **Spalten mit ja/nein gelten als Voraussetzung**, auch verwaltende wie „Kostenübernahme“ oder „Zahlung“; die Vorschau
  erlaubt es, einzelne Spalten auf „ignorieren“ zu setzen. Die Spalte „Alter“ der Beispieldatei enthält Geburtsdaten und
  wird deshalb als Geburtsdatum übernommen. Weitere Spalten (Rolle, Status) landen als „weitere Angaben“ am Teilnehmenden.
- **Zeilen mit einer Rolle außer „Teilnehmender“** (etwa „Lehrgangsleitung“) werden als Ausbilder des Lehrgangs
  übernommen, nicht als Teilnehmende.
- **Import ist zustandslos.** Vorschau und Übernahme bekommen die Datei jeweils erneut geschickt – Gunicorn läuft mit
  mehreren Arbeitsprozessen ohne gemeinsamen Speicher, und die Dateien sind klein.
- **Größenlimit für Videos** ist die vorhandene, in den Einstellungen änderbare Grenze `MAX_UPLOAD_MB` (Vorgabe 5 GB);
  eine zweite Grenze nur für Prüfungsmedien hätte zwei Stellen für dieselbe Frage geschaffen.
- **Testdaten sind erfunden.** Die Beispiel-Excel enthält echte Namen und Geburtsdaten; sie liegt nicht im Projekt. Die
  Tests erzeugen eine strukturgleiche Datei mit erfundenen Namen (Kopfzeile in Zeile 7, verbundene Zellen, Datumstexte,
  ja/nein-Spalten, Leerzeilen, Duplikat). Der Import der echten Datei wurde zusätzlich von Hand geprüft.
- **Eigenes Stylesheet.** Die Gestaltung des Bereichs liegt in `pruefungen.css` und wird nur auf dieser Seite geladen;
  Variablen und Bausteine kommen weiter aus `app.css`.
- **Suche unabhängig von Groß-/Kleinschreibung auch bei Umlauten.** Der Textfilter der Lehrgangsliste läuft in Python
  (casefold), weil SQLite `lower()` nur ASCII kennt und „Köln“ über LIKE nicht durch „köln“ gefunden würde.
- **Eine Bewertung, auf die schon eine Nachprüfung folgt, lässt sich nicht mehr auf „bestanden“ ändern** (409) – sonst
  stünde eine Nachprüfung hinter einer bestandenen Prüfung, ein Zustand, den das Anlegen nie erzeugt.
- **Zeitangaben** werden als Sekunden gespeichert und in „mm:ss“, „m:ss“, „h:mm:ss“ oder als Zahl angenommen; mehr als
  24 Stunden werden abgewiesen. Feldgrenzen: Titel/Ort 200, Nummer 60, Bezeichnungen 300, Kommentar 5000,
  Beschreibung 20000 bzw. 50000 Zeichen.
- **Reihenfolge-Endpunkte übergehen fremde Kennungen** (nur Zeilen des eigenen Lehrgangs werden umsortiert), statt die
  ganze Anfrage abzuweisen.
- **Import: Stammdaten füllen nur leere Felder, „weitere Angaben“ überschreiben.** Vorname, Geburtsdatum, Gliederung,
  E-Mail und Bemerkung eines vorhandenen Teilnehmenden werden nur ergänzt, wenn sie leer sind; die Zusatzspalten
  (etwa Rolle, Status) kommen aus derselben Datei und tragen beim Neuimport den aktuelleren Stand.
- **Import: Stammdaten-Synonyme gelten nur am Anfang eines Spaltentitels.** „Bestätigung Gliederung“ oder ein Titel mit
  „Heimatgliederung“ mitten im Text wird nicht zur Gliederung, sondern bleibt – bei ja/nein-Werten – eine Voraussetzung.
  Excel-Seriennummern werden nur in Geburtsdatum-Spalten als Datum gelesen; „Alter“ mit Zahlen bleibt eine weitere Angabe.
  Zwei Spalten mit derselben Stammdaten-Zuordnung: die erste gewinnt, die zweite wird zur weiteren Angabe und gemeldet.
  Ein Zeitraum mit nur einem Datum setzt von = bis; zweistellige Jahre wie üblich (00–68 → 20xx).
- **Nicht lesbare Excel-Dateien** (kein .xlsx, kein ZIP, kaputte Arbeitsmappe) ergeben 400 mit Klartext; der Grund steht im Log.
- **openpyxl wird erst beim Import geladen**, nicht beim Start jedes Gunicorn-Arbeitsprozesses.

## Durchsicht und Nachbesserungen (27./28.09.2026)

Der Bereich wurde nach dem Bau aus fünf Blickwinkeln geprüft (Rechte und Sicherheit, Korrektheit gegen die
Anforderungen, Frontend, Excel-Import, Datenintegrität); bestätigte Befunde wurden behoben und mit Tests
(`test_nachtraege` in `tests/test_pruefungen.py`) abgesichert:

- **Stoppuhr-Wiederaufnahme:** Nach einem Neuladen der Seite (oder über das Banner „Stoppuhr läuft“) hielt der
  Dialog die laufende Uhr sofort wieder an, weil der erste Takt noch vor dem Öffnen des Dialogs lief – das
  Zeitfeld blieb leer. Behoben; Speichern übernimmt außerdem eine noch laufende Messung ins Zeitfeld, wenn es leer ist.
- **Zeitangaben** werden streng geprüft: nur „mm:ss“, „h:mm:ss“ oder Sekunden, Einzelteile 0–59 – „1:90“, „1:-5“
  oder Python-Schreibweisen wie „1_0:00“ werden mit 400 abgewiesen.
- **Ja/Nein-Felder** (`erfuellt`, `nachpruefung`) nehmen nur echte Wahrheitswerte oder „true/false/1/0/ja/nein“ an;
  der Text „false“ galt vorher als wahr.
- **Gleichzeitiges Arbeiten:** Bearbeiten und Löschen eines Versuchs prüfen „gibt es schon eine Nachprüfung?“ im
  Schreibzugriff selbst; eine zwischenzeitlich geänderte Bewertung wird nicht mehr stumm überschrieben (409 mit
  Hinweis, die Seite neu zu laden). Fremdschlüsselfehler (Person gerade gelöscht) ergeben 409 statt 500 oder einer
  falschen „schon bewertet“-Meldung.
- **Dateien:** Ein Löschfehler bei einer Mediendatei bricht das Aufräumen nicht mehr ab (Protokoll statt 500);
  Fehlermeldungen beim Upload nennen keine Serverpfade mehr; das vom Browser mitgeschickte Standbild zu Videos
  unterliegt derselben Pixelgrenze wie Bilder.
- **Excel-Import:** Die Import-Endpunkte haben eine eigene Anfragegrenze von 25 MB (statt der Filmgrenze); Zeilen ohne
  Nachnamen werden in Vorschau UND Übernahme gleich behandelt (übersprungen, mit Hinweis); eine Datei ohne erkennbare
  Namensspalte liefert eine korrigierbare Vorschau statt eines Fehlers; ein verdrehter Zeitraum wird gedreht, ein
  zum vorhandenen Datum unpassender nicht übernommen; gleichnamige Teilnehmende ohne Geburtsdatum in der Datei
  werden nicht geraten, sondern gemeldet; „Nachname, Vorname“ in einer Spalte wird am Komma getrennt; „TN“ und
  „Teiln.“ gelten als Teilnehmende, unbekannte Rollen bleiben Teilnehmende mit Hinweis, nur bekannte Ausbilderwörter
  (Lehrgangsleitung, Ausbilder, Referent, Prüfer, Dozent, Trainer, Helfer) machen eine Zeile zum Ausbilder; reine
  Datumsspalten mit Titeln wie „Anmeldung“ oder „Stand“ werden keine Voraussetzung; eine titellose
  Voraussetzungsspalte bekommt den Namen „Spalte C“; eine Kopfzeile aus nur „Vorname“ und „Nachname“ wird erkannt.
- **Oberfläche:** Der Jahresfilter der Liste baute die Jahresauswahl aus der bereits gefilterten Antwort neu;
  im Voraussetzungen-Dialog häuften sich Klick-Handler (Doppelaktionen); eine im Bearbeiten-Formular gestartete
  Stoppuhr ist über das Banner wieder erreichbar; „Abbrechen“ im Nachprüfungsformular führt zur Übersicht; im
  Import-Dialog bleiben eigene Eingaben zu Titel/Nummer/Ort/Datum beim Ändern der Zuordnung erhalten, und nach
  einem Vorschaufehler bleibt die Datei gewählt; gerenderte Beschreibungen tragen keine id-Attribute mehr
  (Formularfelder des Dialogs ließen sich sonst durch Markdown überdecken); Touchziele in allen Dialogen ≥ 44 px.
- **Kopie:** Der Vorgabetitel „… (Kopie)“ hält die 200-Zeichen-Grenze ein.

Bewusst nicht geändert (geprüft und verworfen): Zeitfelder mit `inputmode="numeric"` (Sekunden lassen sich auch ohne
Doppelpunkt tippen); die Hintergrund-Videopflege für Bestandsvideos bleibt auf Alben und Wiki beschränkt (Videos zu
Prüfungen werden bereits beim Hochladen gewandelt).

## Zweite Runde (28.09.2026): Rechte, Profilbilder, Lehrgangsergebnis, Umbenennungen, Beispieldaten

**Neu/geändert**

- **Rechte im Bereich.** Zwei Stufen: *Lehrgangsleitung* (im Lehrgang mit Nutzerkonto und einer Funktion, die „Leitung“
  enthält, eingetragen) und *Administration* dürfen Lehrgänge bearbeiten, kopieren und löschen, Teilnehmende anlegen,
  ändern und löschen, Voraussetzungen und Prüfungsleistungen definieren, Versuche löschen, das Lehrgangsergebnis setzen
  und in einen bestehenden Lehrgang importieren. Alle übrigen Prüfenden (Referierende ohne Leitungsfunktion, sonstige
  Prüfer) bewerten, laden Medien hoch, haken Voraussetzungen ab und schreiben Kommentare. Wer einen Lehrgang anlegt (auch
  per Import), wird automatisch als Lehrgangsleitung eingetragen – außer Administratoren.
- **Profilbild je Teilnehmendem** (`POST/DELETE /api/pruefungen/teilnehmer/<id>/bild`, 256×256 wie das Nutzer-Profilbild,
  Ablage unter `media/pruefungen/avatar`, Auslieferung nur an Prüfer über `/media/pruefung/avatar/<datei>`). Wird mit der
  Person bzw. dem Lehrgang gelöscht.
- **Freier Kommentar je Teilnehmendem** (`PUT …/kommentar`, alle Prüfenden) und **Lehrgangsergebnis** der Leitung
  (`PUT …/ergebnis` mit `bestanden`, `nicht_bestanden` oder `null` zum Aufheben; speichert wer/wann). Mit vermerktem
  Ergebnis sind die Prüfungsdaten der Person **eingefroren**: Versuche anlegen/ändern/löschen, Medien, Haken und Kommentar
  antworten mit 409, der Import übergeht die Person. Stammdaten und Profilbild bleiben für die Leitung änderbar.
  Kommentar und Ergebnis (👍/👎) werden in der Bewertungsansicht „je TN“ gepflegt; eingefrorene Personen tragen 🔒
  (auch in der Matrix, die selbst nur die Leistungen zeigt).
- **Begriff „Ausbilder“ → „Referierende“** in allen Oberflächentexten; Funktionen im Dialog: „Lehrgangsleitung“ und
  „Referierende:r“. Die Feldnamen der Schnittstelle (`ausbilder`) bleiben.
- **„Excel importieren“ → „Import“**; der Dialog erklärt den Weg über das ISC (Dokumente → Checkliste Voraussetzungen
  (Excel) → „Allgemeine Lehrgangsinformationen mit ausgeben“).
- **Lehrgangsliste** ohne „Excel importieren“ je Lehrgang; Bearbeiten/Kopieren/Löschen nur für die Leitung.
  **Lehrgangsseite**: rechts nur „Import“ und ganz rechts „Bearbeiten“, kein Kopieren mehr (das bleibt in der Liste).
- **Beispieldaten** (`POST /api/pruefungen/beispieldaten`, nur Administration; Knopf in der Lehrgangsliste;
  `python -m app.beispieldaten`): SR1 mit 14 Voraussetzungen, 9 Leistungen, 8 Personen, Bewertungen, einer Nachprüfung und
  einem Ergebnis; SR2 nach der Checkliste „Beurteilung Strömungsretter 2“ mit 5 Voraussetzungen und 17 Leistungen in der
  Reihenfolge der Checkliste (die doppelten Kriterien „Führungsverhalten“ und „Teamfähigkeit“ sind als „(Seiltechnik)“ und
  „(Wasser)“ unterschieden), 6 Personen, vollständige Bewertungen und Ergebnisse. Alle Personen sind erfunden.
- Neue Spalten `pruef_teilnehmer.bild`, `kommentar`, `ergebnis`, `ergebnis_von`, `ergebnis_von_name`, `ergebnis_am`
  (additiv, per Migration); `LehrgangKurz`/`LehrgangDetail` liefern `darf_leiten`, `ergebnis_bestanden`,
  `ergebnis_nicht_bestanden`; `TN` liefert `bild`, `kommentar`, `ergebnis`, `ergebnis_von_name`, `ergebnis_am`, `eingefroren`.

**Annahmen dieser Runde**

- „Prüfungen löschen“ heißt: Lehrgänge und einzelne Prüfungsversuche löschen – beides nur Leitung/Administration.
- Ein Freitext-Eintrag als Lehrgangsleitung (ohne Nutzerkonto) verleiht keine Rechte; die Leitung muss über ihr Konto
  eingetragen sein.
- Eine Leitung kann sich nicht selbst aussperren: Bearbeitet sie die Liste der Referierenden und fehlt darin, wird sie
  wieder als Lehrgangsleitung eingetragen (Administratoren nicht). Die Leitung wechselt, indem die Administration oder
  die neue Leitung die Liste anpasst.
- Eingefroren sind die Prüfungsdaten (Versuche, Medien, Haken, Kommentar), nicht die Stammdaten – ein Tippfehler im Namen
  soll sich auch nach dem Abschluss korrigieren lassen.
- Das Lehrgangsergebnis ist von den Zellstatus unabhängig: Die Leitung entscheidet, auch wenn Leistungen offen sind.
- Die Spalte „Führung“ der SR2-Checkliste ist in den Beispieldaten nicht als eigenes Feld abgebildet; sie lässt sich als
  Kommentar am Versuch festhalten.

## Nachtrag (28.09.2026): Profilbild vergrößern, Ansicht „je TN“

- Ein Profilbild lässt sich überall antippen und öffnet groß im Leuchtkasten (Name, Gliederung, Geburtsdatum, Ergebnis) –
  auch aus dem Bewertungsdialog heraus, der dabei geöffnet bleibt. Initialen-Kreise sind nicht antippbar.
- In der Bewertungsansicht „je TN“ steht das Profilbild groß im Kopf; jede Leistung zeigt die gebrauchte Zeit neben der
  Sollzeit („⏱ 01:15 von 01:00 – über Sollzeit“) und den Kommentar des letzten Versuchs.
- Die Zellen im Lehrgangsdetail liefern dafür zusätzlich `letzter_kommentar`.

## Nachtrag (28.09.2026): Matrix ohne Zusatzspalten

- Die Spalten „Kommentar“ und „Lehrgang“ sind aus der Matrix entfernt; sie zeigt nur noch die Prüfungsleistungen.
  Kommentar und Lehrgangsergebnis bleiben in der Ansicht „je TN“ (Block über der Leistungsliste) erreichbar.
  Schloss und Dämpfung eingefrorener Personen bleiben in der Matrix erhalten.

## Wiki-Nachträge (28.09.2026)

- **Nutzerverwaltung:** Die Spalte „Inhalte“ zählt jetzt auch die angelegten Artikel („3 Artikel, 2 Alben, 14 Bilder“;
  Seiten im Papierkorb zählen nicht). Schnittstelle: `page_count` in `GET /api/admin/users`.
- **Einklappbare Boxen im Editor:** Sie beginnen zugeklappt – wie im Artikel – und lassen sich über den Pfeil vor dem Titel
  auf- und zuklappen (Klick auf die linken 30 px des Titels; der Titeltext bleibt normal bearbeitbar). Ausgeblendet werden
  nur Körper und Trennmarke in der Ansicht, das Dokument ändert sich nicht. Die Pfeiltasten überspringen einen zugeklappten
  Körper wie im Artikel; landet der Schreibstrich dennoch darin (etwa nach Rückgängig), klappt die Box von selbst auf,
  und beim Zuklappen rückt er ans Ende des Titels. Damit
  steht der Text unter einer Box im Editor auf gleicher Höhe wie in der Leseansicht – vorher lag er um den ganzen
  Boxinhalt tiefer. Alte `$$accordion`-Blöcke aus Browser-Entwürfen werden ebenfalls zugeklappt gezeigt.
- **Profilbilder im Wiki größer:** Autorzeile 32 statt 24 px, Autorentafel 40 statt 30 px – in Lese- und Editoransicht gleich.
- **Anhänge sichtbar:** Sind zu einer Prüfung Bilder oder Videos hinterlegt, zeigen die Bewertungsübersichten (Matrix,
  „je Leistung“, „je TN“) in der Zelle eine Büroklammer, ab zwei Anhängen mit Zähler. Schnittstelle: `medien_anzahl`
  je Zelle im Lehrgangsdetail.
