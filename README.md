# strömis.de

Übungsobjekte für die seiltechnische Rettung und Übungsgewässer für die Strömungsrettung auf einer Karte katalogisieren (Ankerplätze) – plus ein gemeinsames Wiki (Strömipedia), die Prüfungen der Lehrgänge (Riegenkarten) und Ausrüstungsbestand mit Prüfnachweisen (Materialablage). Ein Docker-Container, Gestaltung nach dem DLRG-Handbuch Corporate Design.

## Was die Anwendung kann

**Module und Adressen** (Umbenennung vom 26.10.2026, Wunsch des Nutzers): Die Module heißen **Strömipedia** (bis dahin „Wiki“), **Ankerplätze** („Spots“, die Karte), **Riegenkarten** („Prüfungen“ – Lehrgänge, Kataloge, Prüfungen abnehmen), **Materialablage** („Material“) und **Leitstelle** („Verwaltung“). Umbenannt sind nur die sichtbaren Namen und die Seitenadressen; die Rollen („Material-Verwaltung“, „Wiki-Verwaltung“, „Plattform-Verwaltung“), die Stufe „Verwaltung“ in jedem Modul, die Begriffe in den Modulen (Album, Lehrgang, Katalog, Prüfer, die Prüfungen der Materialablage) und alle internen Schlüssel (`recht_<modul>`, `auth.MODULE`, Datei- und Endpunktnamen) bleiben. Namen und Adressen stehen an einer Stelle: `app/module.py`.

| Modul | Seiten (neu) | alte Adresse – leitet dauerhaft weiter |
|---|---|---|
| Startseite | `/` (seit dem 02.11.2026 über alle Module, siehe „Startseite“) | – |
| Strömipedia | `/stroemipedia`, `/stroemipedia/<slug>` | `/wiki`, `/wiki/<slug>`, auch `/strömipedia…` |
| Ankerplätze | `/ankerplaetze` | `/karte`, auch `/ankerplätze` |
| Riegenkarten | `/riegenkarten`, `/riegenkarten/kataloge[/<id>]`, `/riegenkarten/<id>[/druck]` | `/pruefungen…` |
| Materialablage | `/materialablage…` (Übersicht, Prüfungen, Bestand, Katalog, Artikel, „Echtheit prüfen“ `/materialablage/pruefen` …) | `/material…` (auch `/material/pruefen` aus gedruckten Protokollen) |
| Leitstelle | `/leitstelle` | `/admin` |

Die Weiterleitung (301, erster `before_request`-Haken, ohne Anmeldung und ohne Datenbankabfrage) gilt für GET und HEAD, behält die Abfrage (`?status=…`, `?freigaben=…`) – den Anker behält der Browser – und führt nur auf einen eigenen Pfad (festes Präfix plus der kodierte Rest, kein Host, kein Schema). Ein Schrägstrich am Ende einer Startseite (`/stroemipedia/`, `/ankerplaetze/`, `/riegenkarten/`, `/materialablage/`, `/leitstelle/`, auch `/wiki/` usw.) führt ebenso per 301 auf die Adresse ohne – nur diese fünf festen Pfade, Unterseiten mit Schrägstrich bleiben 404. `Cache-Control: max-age=86400`: Browser merken sich die 301 einen Tag, nicht unbegrenzt. Unverändert bleiben `/m/<token>` (QR- und NFC-Etiketten), `/api/…`, `/media/…`, `/static/…`, `/oeffentlich/…` und die früheren öffentlichen Adressen `wiki.strömis.de/<slug>` (seit dem 01.11.2026 Einstiege zur Anmeldung, siehe „Freigabe für alle Angemeldeten“). Gespeicherte Links in Wiki-Seiten (`](/wiki/<slug>)`) werden nicht umgeschrieben: Beide Schreibweisen gelten als interner Link (Rückverweise, Klick ohne Neuladen, Umschreiben im öffentlichen Teil); neue Links schreibt der Editor als `/stroemipedia/<slug>`. Festgeschriebene Protokolle bleiben, wie sie sind (sie tragen `strömis.de/material/pruefen`); neue Protokolle und Lebensläufe drucken `strömis.de/materialablage/pruefen` und „Materialablage · …“ im Kopf.

**Als App und Kontakt** (01.11.2026, Wünsche vom 28.10.2026): strömis.de lässt sich als App auf den Startbildschirm
legen (eigenes Fenster ohne Adressleiste, Maskottchen auf Rot als Symbol; ohne Netz nur eine Hinweisseite, nichts
Angemeldetes im Speicher – siehe „Als App installieren (PWA)“). Ganz unten auf jeder Seite stehen klein die
Kontaktadressen „Fragen: verwalter@stroemis.de · Fehler: bugs@stroemis.de“ (einstellbar unter Leitstelle →
Einstellungen, Gruppe „Seite“).

**Ankerplätze (Karte)**
- Bilder erscheinen als Thumbnail-Marker (rote Umrandung = Seiltechnik, blaue = Gewässer). Beim Herauszoomen werden sie zu einem Stapel mit Zähler zusammengefasst; ein Klick zoomt hinein, auf der letzten Stufe fächern sie sich auf.
- Klick auf ein Bild öffnet das Album mit allen Bildern, allgemeinen Infos und dem Ansprechpartner (Name, Gliederung, Telefon, E-Mail, Hinweise). Hat ein Album noch kein Bild mit Position, sagt ein Satz, wie es auf die Karte kommt (Bild mit GPS hochladen oder „Auf Karte platzieren“).
- **Suche und Liste** (Gerätetest 01.11.2026): Das Suchfeld über der Karte („Album suchen: Name oder Ort“) sucht in Titel, Beschreibung und Gliederung des Ansprechpartners der Alben – ein eigenes Ortsfeld hat ein Album nicht, der Ort steht meist im Titel oder in der Beschreibung; Groß/klein, Akzente und ß zählen nicht. Die Karte zeigt dann nur die Bilder der Treffer, die Liste die Treffer selbst; Enter öffnet einen einzelnen Treffer bzw. rückt mehrere ins Bild. „Alben“ schaltet die Liste auf und zu: Ist der eigene Standort bekannt (oder für die Seite schon freigegeben), heißt sie „In der Nähe“ und ist nach Entfernung sortiert (mit „x km entfernt“, Alben ohne Position am Ende), sonst alphabetisch mit „Standort verwenden“. Die Filter Seiltechnik/Gewässer gelten auch für die Liste; alle Alben bleiben in ihr (kein seitenweises Laden). Nach dem Löschen eines Albums steht die frische Liste da.
- **Eigener Standort** („◎“): Die Meldung kommt erst mit der Antwort der Ortung und nennt den Fall – nicht freigegeben, nach 20 Sekunden kein Standort (draußen braucht GPS einen Moment), am Gerät nicht verfügbar. Ist der Standort für die Seite im Browser blockiert, steht sofort ein Hinweis auf die Website-Einstellungen da; kommt gar keine Antwort (der Browser unterdrückt die Rückfrage), meldet sich die Seite nach 30 Sekunden. Solange gesucht wird, blinkt „◎“ blau.
- Jedes Bild hat Titel, Notiz, Objekthöhe, Höhe ü. NN, Aufnahmezeit, Koordinaten und ein Freitextfeld für weitere Infos. Alles ist nachträglich änderbar. Die Herkunft der Position („aus Bild“ oder „manuell“) wechselt in „Bild bearbeiten“ nur, wenn Breite oder Länge im Formular wirklich geändert wurden – wer nur den Titel ändert, behält den Geotag als Herkunft (Entscheidung des Nutzers vom 01.11.2026; der Server prüft es ebenso). Gespeichert werden überhaupt nur die Felder, die im Formular geändert wurden (seit dem 02.11.2026) – „Höhe ü. NN“ (im Feld auf eine Nachkommastelle) und die Aufnahmezeit (im Feld ohne Sekunden) bleiben sonst auf die Stelle genau erhalten.
- **Bilder auf die Karte ziehen** legt ein neues Album an: Ein kurzer Dialog fragt Titel und Art, dann wird hochgeladen. Liegt der Mittelpunkt der Geotags innerhalb von 2 km an einem Album, das man selbst führt, fragt die Anwendung anschließend, ob die Bilder dorthin gehören – dann wandern sie in das vorhandene Album und das neue löst sich wieder auf. Alben anderer in der Nähe werden genannt, aber nicht angeboten. Dateien über der Seitenleiste eines eigenen Albums kommen direkt in dieses Album.
- Beim Hochladen werden Geotag, Höhe und Aufnahmezeit aus den EXIF-Daten gelesen (JPEG, PNG, WebP, TIFF, HEIC/HEIF vom iPhone). Die Dateiauswahl und das Ablegen auf der Karte nehmen genau diese Bildformate und die Videos (MP4, M4V, MOV, WebM) an – die Liste kommt vom Server (`images.MEDIEN_ACCEPT`; GIF, BMP und AVIF lehnt er ab und lassen sich seit dem 01.11.2026 auch nicht mehr wählen). Bilder ohne Geotag werden erkannt; die Anwendung bietet direkt an, sie auf der Karte zu platzieren – per Tipp auf die Karte, über die Album-Position (den Mittelpunkt der Bilder des Albums mit Position; den Knopf „Album-Position übernehmen“ gibt es erst, wenn eines davon eine hat – auch ein eben platziertes), den eigenen Standort oder über eine Adresssuche, die die Karte an die gesuchte Stelle fährt. Die Suche läuft über den eigenen Server (Nominatim), damit die Adresse nicht mit der IP des Mitglieds nach außen geht.
- Kartenansichten (Ebenenwahl oben rechts): Satellit (Esri-Luftbild, Startansicht), Karte (OpenStreetMap) und Gelände (OpenTopoMap), Filter nach Seiltechnik/Gewässer. Über dem Luftbild liegt eine Beschriftungsebene mit Straßen, Orts- und Gewässernamen – sonst sieht man zwar die Kiesbank, weiß aber nicht, an welchem Fluss; sie erscheint nur zum Luftbild und ist über `SAT_LABELS_URL` austauschbar oder abschaltbar. Ist die Seitenleiste offen, rücken Zoom, Ebenenwahl und Rechtehinweise neben sie, statt darunter zu verschwinden.
- Das Deckblatt eines Albums lässt sich festlegen (in der Großansicht eines Bildes „Als Deckblatt“). Es steht in der Albumliste und liegt auf der Karte im Bilderstapel eines Haufens obenauf. Ohne Wahl zeigt das Album sein erstes Bild.
- Ein Bild heißt nach seinem Titel, sonst nach dem Dateinamen – außer der besteht nur aus Ziffern (die Fotoauswahl von Android liefert „48698.jpg“): dann „Bild 3 von 5“ in Großansicht, Bildraster und Rückfrage beim Löschen. Nach dem Hochladen meldet ein Toast „n Bilder hochgeladen“; folgt die Frage nach Bildern ohne Geotag, steht das Ergebnis in ihr.
- Videos (MP4, MOV, WebM) können wie Bilder hochgeladen werden. Was nicht jeder Browser abspielt – vor allem Aufnahmen vom iPhone (.mov mit HEVC) – wird beim Hochladen nach H.264/AAC gewandelt und bekommt ein Vorschaubild aus dem Film; dafür bringt der Container ffmpeg mit – als statisch gebundenes Programm (GPLv3) aus dem Abbild `mwader/static-ffmpeg` von Docker Hub, festgenagelt über dessen Prüfsumme (bis 21.10.2026 von johnvansickle.com, das nicht mehr erreichbar war). Aus der Paketverwaltung kostete dasselbe rund 630 MB statt etwa 260 MB. Das gilt auch für Videos in Artikeln und für den **Bestand**: Nach jedem Start prüft ein Hintergrundlauf alle vorhandenen Videos und wandelt, was nötig ist – Verweise in Seiten, Fassungen und Anhangslisten ziehen mit, und die alte Adresse (`….mov`) führt weiter zum Film. Unter „Nutzer“ steht, solange es läuft, eine Zeile mit dem Stand; `VIDEOPFLEGE=0` schaltet den Lauf ab. Ein Klick auf ein Thumbnail öffnet direkt die Großansicht.

**Startseite** (`/`, Wunsch und Entscheidung des Nutzers vom 02.11.2026 „Start über alle Module“; `app/start.py`, `start.html`, `start.js`)
- Jedes angemeldete Konto mit mindestens einem Modul, „Meine PSA“ oder dem Lesemodus der Strömipedia landet hier – nach der Anmeldung (ein `next` geht vor), über das Logo und als Start der App (`start_url`). Einen Reiter „Start“ gibt es nicht; auf der Startseite ist keiner aktiv, „Strömipedia“ führt nach `/stroemipedia`. Ein Konto ganz ohne Bereich bekommt weiter die Hinweisseite „noch kein Bereich freigeschaltet“ (mit dem Weg ins Profil). Fehlerseiten führen „Zur Startseite“ (unter `/materialablage` mit Modulzugang weiter zur Übersicht der Materialablage).
- Kopf: „Hallo, <Name>“ (ohne Namen „Willkommen“) und das Suchfeld der Strömipedia (mit Stufe oder im Lesemodus) – es öffnet `/stroemipedia?suche=<Begriff>`, dort steht der Begriff im Suchfeld über dem Seitenbaum und die Treffer erscheinen (unter 1024 px im Feld „Artikel suchen“ der Suchzeile, die Trefferliste geht darunter auf).
- **Kacheln** je Modul in der Reihenfolge der Navigation, nur Module, die das Konto nutzt; der Kopf führt ins Modul, jede Zeile mit einer Zahl über 0 auf die passende (möglichst gefilterte) Ansicht, sonst ein ruhiger Satz: **Strömipedia** – lesbare Seiten (im Lesemodus „freigegebene Seiten“), „neu oder geändert seit deinem letzten Besuch“ (ohne eigene Änderungen); **Ankerplätze** – Alben, neue Alben und neue Bilder anderer seit dem letzten Besuch; **Riegenkarten** – laufende Lehrgänge, die das Konto sieht, darin Leistungen ohne Abnahme und offene Mängel (bei genau einem Lehrgang führen die Zeilen hinein); **Materialablage** – mit Bestand dieselben Zahlen wie ihre Übersicht (überfällig, neu/Eingangsprüfung, bald fällig, gemeldete Mängel, zu entscheidende Änderungsanträge), ohne Bestand die eigene PSA (zugeordnet, davon nicht einsatzbereit); ohne Modulzugang mit PSA eine Kachel „Meine PSA“; **Leitstelle** (nur Plattform-Verwaltung) – offene Kontoanfragen. Spalten nach der Inhaltsbreite: 1, ab 560 px 2, ab 1100 px 4 (mit fünf Modulen 5).
- **Zuletzt besucht** (die letzten 8 geöffneten Seiten, Alben, Lehrgänge und Artikel der Materialablage mit Modul und Zeit) und **Neu und geändert** (die letzten 8 Änderungen an Seiten, Alben und Lehrgängen – die Materialablage nicht, ihr Journal wäre nur Rauschen); ab 740 px Inhalt nebeneinander. Gemerkt wird serverseitig je Konto (kein localStorage – Geräte werden geteilt), beim Zeigen neu nach Rechten gefiltert: Gelöschtes und nicht mehr Sichtbares fällt weg.
- Darunter die obersten **Abschnitte der Strömipedia als Karten** (Titel, Zahl der Seiten, drei Unterseiten) und „alle →“.
- „Letzter Besuch“: verglichen wird mit dem vorigen Besuch der Startseite; ein Besuch endet erst nach 30 Minuten ohne Aufruf der Startseite (Neuladen oder Zurückkommen über das Logo zeigt dieselben Zahlen). Merker ohne Schemaschritt in `mat_meta` (`start:besuch:<Konto>`, `start:ziele:<Konto>` mit höchstens 20 Zielen), Seiten der Strömipedia weiter in `wiki_views`; beides geht mit dem Konto. Schnittstelle: `GET /api/start` (alles, nach Rechten gefiltert; ohne Bereich 403), `POST /api/start/besuch` (merkt den Besuch, nur aus eigenem Skript).

**Strömipedia (das Wiki; Docmost-Nachfolger)**
- WYSIWYG-Editor (Toast UI). Markdown-Zeichen wirken beim Tippen **nicht** – `# `, `- `, `> ` oder ` ``` ` am Zeilenanfang bleiben Text; Blöcke kommen aus dem Einfügemenü (`/`), Auszeichnungen aus der Auswahlleiste oder von Tastenkürzeln. Beim Tippen wirken nur `/` (Einfügemenü), `::` (Emoji), die Auszeichnungen ohne Markdown-Entsprechung (`++…++`, `==…==`, `^…^`, `~…~`, `{{farbe:…}}`, `{status:…}`) und die Typografie (`--` → –, `...` → …, deutsche Anführungszeichen); eingefügtes Markdown (Strg+V) kommt fertig gesetzt an (Hilfeseite `docs/Editor - Bedienung und Kuerzel.md`). Eine Quelltextansicht gibt es nicht – gespeichert wird trotzdem Markdown.
- Keine feste Toolbar: `/` öffnet ein Einfügemenü (Überschriften, Listen, Tabelle, Bild, Video, Datei, Audio, HTML-Baustein, Callout, Spalten, Box, Inhaltsverzeichnis, Emoji, Datum …); markierter Text bekommt eine schwebende Leiste mit „Umwandeln in …“ (Überschriften, Listen, Zitat, Code-Block, Callout, Code, Hervorheben, Hoch-/Tiefstellen), Fett/Kursiv/Durchgestrichen/Unterstrichen, Textfarbe, Link, Ausrichtung und Rückgängig/Wiederholen. Klick in Tabellen, auf Bilder, Links oder in einen Abschnitt öffnet ein Kontextmenü wie in Docmost: Zeilen/Spalten, Spaltenausrichtung, Zellen verbinden und wieder teilen (ein Zug über mehrere Zellen, dann *Zellen verbinden*; gespeichert als `@cols=`/`@rows=` vor dem Zelleninhalt, sortiert wird eine solche Tabelle nicht mehr), Bildbreite (Presets, Zahlenwert oder Ziehgriff), Ausrichtung, Alt-Text, Zuschneiden (Rahmen über dem Bild; das Ergebnis ist eine neue Datei, das Original bleibt liegen), Spaltenanzahl, Callout-Art und Emoji, Duplizieren, Löschen. Die Menüs tragen nur Symbole (eigene SVG, keine Icon-Bibliothek); markierter Text blendet das Blockmenü aus und die Formatleiste ein, und umgekehrt. Der Editor zeigt Spalten nebeneinander, Callouts als farbige Kisten – auch die einzeilige Form in einer Tabellenzelle, deren Marken dort ausgeblendet sind –, einklappbare Boxen aufgeklappt und Ausrichtung wirklich ausgerichtet – der Inhalt ist dabei gewöhnlicher Editorinhalt und wird direkt bearbeitet, ohne Dialog. Jede Spalte fließt für sich (gemessenes Layout statt geteilter Rasterzeilen), in Breite und Rinne deckungsgleich mit der Leseansicht. Auch der Zeilenfall stimmt überein: Die Leerzeile, mit der Markdown zwei Absätze trennt, ist im Editor technisch ein leerer Absatz – sie bleibt im Dokument stehen, wird aber zugeklappt. Jede darüber hinaus gesetzte Leerzeile bleibt dagegen sichtbar und wird als `&nbsp;`-Absatz gespeichert; früher schrieb der Editor dafür eine `<br>`-Zeile, und die verschluckte in der Leseansicht den folgenden Absatz. Auf schmalen Bildschirmen stehen Spalten in beiden Ansichten untereinander (ab 640 px). Blöcke lassen sich am Griff links verschieben; an einer Marke wandert der ganze Abschnitt mit. Tabellen, Spalten- und Ausrichtungsabschnitte lassen sich nicht mit Entfernen oder Rücktaste löschen – nur über ihr eigenes Menü; eine halb gelöschte Abschnittsmarke nähme beim Speichern den ganzen Abschnitt mit. Oben rechts schaltet ein Umschalter zwischen Lesen und Bearbeiten, beide in derselben Breite. Bilder per Drag & Drop, Einfügen aus der Zwischenablage sowie Kopieren und Ausschneiden.
- Ein **HTML-Baustein** (`/`-Menü „HTML einbetten“, nur mit Verwaltungsrecht im Wiki) bettet eine selbst hochgeladene, eigenständige HTML-Datei (eigenes Skript, eigenes Stylesheet – etwa eine interaktive Grafik) in den Artikel ein, in Lese- und Bearbeitungsansicht gleich; eingebunden wird sie wie ein Bild (`![Titel](baustein.html)`). Zum Rahmen wird nur eine eigene Datei unter `/media/wiki/`; eine fremde Adresse mit `.html`-Endung bleibt ein Bildverweis. Im Editor hat der Baustein wie ein Bild ein eigenes Menü (Griff oben links im Rahmen oder Klick in den Rahmen): Breite, Höhe, Ausrichtung, Titel, Ersetzen, Duplizieren, Löschen; Griffe rechts, unten und in der Ecke ziehen die Größe. Gespeichert werden die Maße in der Adresse, wie die Bildbreite: `![Titel](baustein.html#w=60%&h=420)`. Ausgeliefert wird sie in einem gesandboxten `<iframe>` (`sandbox="allow-scripts"`, bewusst *ohne* `allow-same-origin`): Das Skript darin läuft, hat aber keinen Zugriff auf Cookies, Sitzung, Speicher oder DOM von strömis.de und kann nicht aus dem Rahmen heraus navigieren – auch auf einer für alle Angemeldeten freigegebenen Seite bleibt das so, denn dort erreicht der Baustein jedes angemeldete Konto, auch ohne Wiki-Stufe. Wer im Wiki kein Verwaltungsrecht hat, bekommt die Datei beim Hochladen abgelehnt.
- Callouts (`info`, `tip`, `warning`, `success`, `danger`, `note`) mit frei wählbarem Emoji und wahlweise einer eigenen Pastellfarbe (`farbe:mint` in der Kopfzeile; acht Töne zur Auswahl) (Auswahl aller darstellbaren Unicode-Emojis oder Eingabe über den System-Emoji-Picker). Abschnitte mit 2 bis 5 Spalten, einklappbare Boxen (Accordions; Titel und Inhalt direkt im Text bearbeitbar – im Editor zugeklappt wie im Artikel, der Pfeil vor dem Titel klappt auf) – beide ineinander verschachtelbar. Ausrichtungsblöcke (`:::align center`). Synchronisierte Abschnitte: `:::baustein <kennung>` hält einen Text an einer Stelle, `:::einbau <seite>#<kennung>` zeigt ihn auf beliebig vielen anderen Seiten – geändert wird nur in der Quelle. Vorhandene Absätze lassen sich nachträglich dazu machen (markieren → „Umwandeln in …“ → „Synchronisierter Abschnitt“), ohne dass sich am Text etwas ändert. Aufgelöst wird beim Anzeigen über die gewöhnliche Schnittstelle, damit die Leserechte der Quellseite von allein gelten; im öffentlichen Bereich erscheint nur, was dort freigegeben ist. Rückverweise zeigen der Quellseite, wer sie einbindet. Gespeichert wird Markdown mit `:::`-Blöcken; bestehende Seiten funktionieren unverändert. Tabellen, Callouts, einklappbare Boxen, Spalten und Ausrichtungsblöcke lassen sich im Editor nicht mit Entfernen oder Rücktaste löschen – nur über ihr Inline-Menü; ein versehentlicher Tastendruck würde sonst eine Marke entfernen und beim Speichern den ganzen Abschnitt auflösen.
- Die Übersicht (`/stroemipedia`) zeigt die obersten Abschnitte als Karten im Raster (seit dem 02.11.2026): Titel, Zahl der Seiten (der Abschnitt und alles darunter), die ersten sechs Unterseiten und „… n weitere“ zum Abschnitt; alles Weitere steht im Seitenbaum. Die Übersicht nutzt die Breite (die Lesebreite gilt nur für Artikel). Die Karten haben eine feste Spaltenbreite – volle Reihen füllen die Breite, eine nicht volle Reihe steht mittig wie auf der Startseite (eine Regel `.wiki-karten` für Übersicht, Lesemodus und Startseite; Spalten nach der Breite der Liste: 2 ab 492 px, 3 ab 744, 4 ab 996, 5 ab 1248). Darunter „zuletzt besucht“ und „zuletzt geändert“. Im Lesemodus stehen die freigegebenen Einstiegsseiten ebenso als Karten (`/api/public/index` liefert dazu `seiten`, `kinder`, `unterseiten`).
- Die erste Überschrift im Text ist zugleich der Seitentitel – wie in Docmost. Wer sie ändert, benennt die Seite um; ein eigenes Titelfeld gibt es nicht mehr. Einsortiert wird eine Seite durch Ziehen im Seitenbaum links (auf eine Seite ziehen macht sie zur Unterseite).
- **Seitenbaum** links (seit dem 28.10.2026 übersichtlicher): vor jedem Titel eine feste Spalte mit einem gezeichneten Winkel als Klappzeichen (nach rechts = zugeklappt, nach unten = offen; Name „<Seite> aufklappen/zuklappen“, `aria-expanded`), Seiten ohne Unterseiten halten die Spalte frei, damit alle Titel einer Ebene bündig stehen. Jede Ebene rückt gleich weit ein, eine dünne Linie unter dem Klappzeichen der Elternseite fasst ihre Unterseiten zusammen; die oberste Ebene steht fett und ohne Einzug. Aktive Seite mit rotem Balken, fett. Am Rechner enden lange Titel mit „…“ (voller Titel im Tooltip), „+“ und „⋯“ erscheinen beim Überfahren oder wenn die Zeile den Tastaturfokus hat. Am Finger (grober Zeiger, Telefon wie Tablet) ist der Baum seit dem 02.11.2026 kompakter: Zeilen 36 px (bewusste Ausnahme von den sonst 44 px am Finger), lange Titel brechen unter ihrer ersten Zeile um (Zeilenhöhe 1,25, 6 px Polster), statt Abstand trennt eine feine Linie jede Zeile, vor jedem weiteren Abschnitt der obersten Ebene eine kräftigere; das Klappzeichen hat 44 × 36 px Tippfläche über einer nur 24 px breiten Spalte, „⋯“ (44 × 36 px) steht nur in der Zeile der geöffneten Seite – für eine andere Seite tippt man sie erst an, mit der Tastatur erscheint es am fokussierten Eintrag; der Ordnerbaum der Materialablage bleibt bei 44 px; die Schublade (unter 1024 px) ist bis 360 px breit, daneben bleibt ein Streifen der Seite, der sie schließt. Im „⋯“ einer Seite: Unterseite anlegen, Merkliste, Symbol, Duplizieren, Als Markdown herunterladen, In den Papierkorb.
- **Vorlagen** (Entscheidung des Nutzers vom 01.11.2026): Eine Seite mit „Als Vorlage anbieten“ (im „⋯“ der Seite) bieten „Neue Seite“, „Unterseite anlegen“, das „+“ im Seitenbaum und „Erste Seite anlegen“ an (die beiden letzten seit dem 02.11.2026) – der Dialog „Neue Seite“ fragt „Beginnen mit“: Leer oder eine der Vorlagen, die das Konto lesen darf (`GET /api/wiki/templates`). Der Inhalt der Vorlage wird ohne ihre Titelzeile in den Editor der neuen Seite **kopiert**; angelegt wird mit „Anlegen“ wie jede neue Seite, danach hängt nichts mehr an der Vorlage (ändern oder löschen wirkt nicht zurück). Bilder und Anhänge wie beim Duplizieren: die neue Seite verweist auf dieselben Dateien. Gibt es keine lesbare Vorlage, öffnet „Neue Seite“ den Editor gleich leer wie bisher. Vorlagen stehen nicht in den Anleitungsverweisen.
- Die Kopfzeile bleibt beim Scrollen stehen und ist wie in Docmost aufgeteilt: links der Pfad zur Seite mit den Symbolen der Ebenen, rechts der Umschalter Lesen/Bearbeiten, Kommentare, Teilen, ein Knopf für das Inhaltsverzeichnis und „⋯“ für alles Weitere (Verlauf, Merkliste, Beobachten, Export, Import aus einem ZIP für die Wiki-Verwaltung, Drucken, Vorlage, Duplizieren, Papierkorb). Sie bleibt eine Zeile (Gerätetest 01.11.2026): Der Pfad nimmt nur, was die Knöpfe übrig lassen, und kürzt sich auf „erste Ebene / … / Seite“, sobald ein Glied sonst abgeschnitten würde; am Finger weichen „Teilen“ und „Inhaltsverzeichnis“ in „⋯“ aus, wenn die Leiste schmaler als 720 px ist. Bei höchstens 500 px Höhe (Telefon quer, Tablet mit Bildschirmtastatur) klebt sie nicht, sondern rollt mit dem Text weg. Unter der Überschrift steht, wer die Seite angelegt hat – ein Klick darauf zeigt Ersteller und Mitwirkende –, daneben ein Knopf, der rechts die Angaben zur Seite aufklappt: Herkunft, Zeitpunkte, Wörter, Zeichen, Lesezeit und die Verweise in beide Richtungen.
- Artikel mittig mit fester Lesebreite; rechts ein automatisches Inhaltsverzeichnis, die Angaben zur Seite und die Kommentare. **Auf dem Telefon** (unter 1180 px) rücken Kommentare und Angaben unter den Artikel, das Inhaltsverzeichnis steht dann in „⋯“ und öffnet als Dialog (ein Tipp auf einen Abschnitt springt dorthin); unter 1024 px (Telefon, Tablet hochkant, Foldable) steht oben im Inhalt eine **Suchzeile** wie in der Materialablage (seit dem 02.11.2026): links „☰“ – der Seitenbaum als Schublade –, daneben das Feld „Artikel suchen“ über die restliche Breite; sie klebt beim Rollen unter der Kopfleiste, die Kopfzeile einer Seite direkt darunter. Gesucht wird wie über dem Baum (ab zwei Zeichen), die Treffer stehen als Liste unter der Zeile über dem Text; Tippen oder Enter öffnet die Seite, Esc, Tippen daneben und Zurück schließen die Liste. In der Schublade steht dann kein zweites Suchfeld; im Editor gibt es die Zeile nicht – dort bleiben „☰“ in seiner Kopfzeile und die Suche in der Schublade. Dieselbe Zeile hat der Lesemodus (seit dem 02.11.2026; gesucht nur in den freigegebenen Seiten). Bis 500 px Höhe und bei offener Tastatur klebt nur die Suchzeile (am oberen Rand). Der Pfad weicht dem Titel. Fingerziele wachsen auf Touch-Geräten, Eingabefelder haben 16 px (kein iOS-Zoom), Dialoge und Leuchtkasten füllen den Bildschirm, die Listen der Leitstelle und der Riegenkarten werden nach der Breite des Inhalts zur Kartenliste. Bei **1024 px** (Tablet quer) ist der Seitenbaum höchstens 260 px breit, das Seitenpolster 24 px, die Albumleiste 340 px. **Faltgeräte** aufgeklappt (Galaxy Fold, Pixel Fold): meldet der Browser zwei Bildschirmhälften (Viewport Segments), liegt die Falz genau auf der Trennlinie – links Seitenbaum, rechts Text; auf der Karte rechts die Albumleiste; zusammengeklappt füllt die Schublade die linke Hälfte. Leitstelle, Riegenkarten und Profil stehen dann ganz in der rechten Hälfte, nichts liegt auf der Falz. Alles davon liegt in Media-Queries – am Rechner ändert sich nichts. Der Editor benutzt dieselbe Spalte: Kopfzeile, Titel, Autorzeile und jeder Block sitzen in beiden Ansichten auf demselben Pixel. Gemessen über ein Dokument mit Spalten, Ausrichtung, Liste, Tabelle und Bild mit Unterschrift bleibt der Unterschied unter zwei Pixeln und summiert sich nicht: Die Abschnittsmarken kosten keine Höhe, Tabellen und Bildunterschriften übernehmen die Maße der Leseansicht.
- Kommentare zu beliebigen Textstellen (Text markieren → „Kommentieren“) oder zur ganzen Seite, mit Antworten und „Erledigt“. Löschen dürfen Kommentator, Seitenersteller und die Wiki-Verwaltung. Bis 1180 px (Kommentare unter dem Artikel) öffnet ein Tipp auf eine markierte Stelle den Kommentar samt Antworten als Dialog über dem Text, statt ans Seitenende zu springen; „Erledigt“, „Wieder öffnen“ und „Löschen“ bestätigen sich mit einer Meldung. Kästchen von Aufgabenlisten sind 24 px groß und tragen den Text ihres Punkts als Namen.
- Bearbeitungsfreigaben: Der Ersteller gibt einzelne Nutzer zum Bearbeiten frei (ohne Löschrecht); die Freigabe gilt auch für Unterseiten. Ohne Freigabe können andere Nutzer lesen und kommentieren.
- Den **Ersteller** einer Seite kann die Wiki-Verwaltung umschreiben (Klick auf „Von …“ unter dem Titel → „Ersteller ändern“). Gebraucht wird das, wenn jemand die Gliederung verlässt. Mit dem Namen wechseln auch seine Rechte: löschen und Bearbeiter freigeben. Zur Wahl stehen nur Konten mit Stufe in der Strömipedia; seit dem 02.11.2026 lehnt auch der Server ein Konto ohne Stufe ab (400). Ebenso „Bearbeiten erlauben“: Ein neu gewähltes Konto ohne Stufe lehnt der Server ab, statt es still zu speichern – wer schon freigegeben ist und die Stufe verloren hat, bleibt stehen, bis man ihn abwählt.
- **Freigabe für alle Angemeldeten** (früher „öffentliche Freigabe“; nur mit Verwaltungsrecht im Wiki, Menü „Teilen“ → „Für alle Angemeldeten freigeben“): einzelne Seiten oder ganze Abschnitte inkl. Unterseiten lesen dann auch angemeldete Konten **ohne** Stufe in der Strömipedia (Lesemodus) – samt der eingebundenen Bilder und Videos; mit Stufe „Mitglied“ liest man ohnehin alle nicht beschränkten Seiten. **Ohne Anmeldung gibt es seit dem 01.11.2026 keine Strömipedia-Inhalte mehr** (Nutzer: „Es gibt kein öffentlich stehendes Wiki ohne Anmeldungen mehr.“): `/api/public/pages|index|search` und Wiki-Anhänge antworten ohne Sitzung 401 (Anhänge leiten zur Anmeldung), `/oeffentlich/…` und die Subdomain `wiki.strömis.de/<slug>` leiten zur Anmeldung auf `BASE_URL` mit Rücksprung nach `/stroemipedia/<slug>` (angemeldet direkt dorthin); alte Bild- und Dateilinks der Subdomain (`wiki.strömis.de/media/wiki/<datei>`) ebenso mit Rücksprung auf die Datei. Wer schon angemeldet ist, springt von `/login?next=…` gleich zum Ziel (nur seiteneigene Ziele, Nachbesserung vom 02.11.2026). Nicht betroffen: die Bilder der Anmeldeseite (`/api/public/slideshow`), die QR-Adressen `/m/…` und „Echtheit prüfen“. Die Vorlage `public.html` und `public.js` bleiben (der Lesemodus nutzt `public.js`). Anhänge über die Freigabe liegen nur noch im eigenen Zwischenspeicher (`private`, ein Tag). Nicht freigegebene Anhänge bleiben geschützt. In einem freigegebenen Abschnitt darf auch Unterseiten nur die Wiki-Verwaltung anlegen oder dorthin verschieben – sonst käme Freigeben durch die Hintertür. Marke am Seitentitel „für alle Angemeldeten“, im Baum 🌐.
- **Lesemodus für Konten ohne Wiki-Zugriff:** Ein angemeldetes Konto mit „kein Zugriff“ in der Strömipedia sieht unter „Strömipedia“ (`/stroemipedia`, `/stroemipedia/<slug>`) genau die Seiten, die für alle Angemeldeten freigegeben sind – auch die Unterseiten freigegebener Abschnitte, mit ihren Bildern und Dateien, Seitenbaum und Suche –, in der eigenen Kopfleiste – unter 1024 px mit derselben Suchzeile „☰“ + „Artikel suchen“ wie die Strömipedia (seit dem 02.11.2026, vorher „☰ Seiten“). Eine Zeile über dem Text sagt: „Du siehst die Seiten der Strömipedia, die für alle Angemeldeten freigegeben sind. Für alle übrigen schaltet dich die Plattform-Verwaltung frei.“ Mehr gibt es nicht: kein Bearbeiten, Anlegen oder Löschen, kein Papierkorb, keine Versionen, Kommentare, Autorenangaben oder beschränkten Seiten und keine eingebundenen Abschnitte aus internen Seiten; ein Link auf eine interne Seite meldet „gibt es nicht, oder sie steht nur in der internen Strömipedia“ – wortgleich für beides. Seiten, die das Konto früher beobachtet hat, melden sich nicht mehr per Mail. Der Lesemodus benutzt den Leser und die Schnittstelle des früheren öffentlichen Teils (`public.js`, `/api/public`, seit dem 01.11.2026 nur mit Anmeldung): Was freigegeben ist, entscheidet weiter eine Stelle (`api_wiki.is_public`), und die internen Schnittstellen antworten diesem Konto wie bisher 403. `tests/test_wiki_lesemodus.py` geht dafür jede Wiki-Route durch.
- Versionsverlauf mit Wiederherstellen (standardmäßig die letzten 100 Fassungen je Seite, `WIKI_MAX_REVISIONS`), Volltextsuche, Export einzelner Seiten oder ganzer Abschnitte als Markdown beziehungsweise ZIP. Im ZIP liegt jede Seite unter genau einem Pfad, ihre Unterseiten im gleichnamigen Ordner; heißen zwei Geschwister gleich, bekommt das zweite `-<slug>` angehängt – samt Ordner für seine Unterseiten; ist auch dieser Name schon vergeben, zählt er weiter (`-<slug>-2` …) –, damit der Import den Baum unverändert wieder aufbaut. Fehlt einer Seite die Titelzeile `# …` (etwa per Schnittstelle angelegt), schreibt der Export sie davor – so behält die Seite beim Import ihren Titel statt des Dateinamens. Die heruntergeladene Datei heißt `<Titel>_<JJJJ-MM-TT>_<HHMM>.md` bzw. `.zip`, und jeder Abruf hat eine eigene Adresse (seit dem 27.10.2026 – sonst bot Chrome auf Android die alte Datei an).
- **Import aus einem ZIP** (Wunsch vom 25.10.2026; nur die Wiki-Verwaltung; seit 28.10.2026 nur noch im Menü „⋯“ neben „Neue Seite“ über dem Seitenbaum (dort auch der Papierkorb) → „Seiten aus ZIP importieren“ – weder im „⋯“ jeder Seite im Baum noch im „⋯“ des Seitenkopfs): Dialog „Seiten importieren“ mit Dateiwahl und „Einsortieren unter“ (eine Seite aus dem Baum oder „– oberste Ebene –“, vorgewählt die oberste Ebene); ein Satz sagt vorher, wenn das Ziel ohne Anmeldung sichtbar oder lesebeschränkt ist – die neuen Seiten erben das, gesetzt wird nichts. Das Ergebnis steht im selben Dialog (Seiten als Links, Hinweise), „Schließen“ öffnet die erste neue Seite. **Aufbau des ZIP** wie beim Export: Jede `*.md`/`*.markdown` (UTF-8, auch mit BOM) ist eine Seite, `A/B.md` eine Unterseite von `A.md`; ein Ordner ohne eigene `.md` wird eine Seite mit seinem Namen; Geschwister in natürlicher Reihenfolge der Dateinamen („2 …“ vor „10 …“) hinter die vorhandenen. **Titel** = erste Zeile `# …` (wie im Editor), sonst der Dateiname – dann steht `# <Titel>` vorn; höchstens 200 Zeichen. **Anhänge** kommen nur mit, wenn eine Seite auf sie verweist (Bilder werden wie beim Hochladen neu geschrieben, ohne Aufnahmeangaben; Dokumente, GIF, SVG und HTML-Bausteine unverändert; jede Datei einmal); **Videos werden übergangen** („Videos einzeln hochladen“), ebenso fremde Dateitypen und unbenutzte Dateien – das Ergebnis nennt sie. **Verweise** außerhalb von Code: `/media/wiki/<datei>` (so schreibt der Export, Eintrag `media/<datei>`) und relative Pfade zeigen danach auf die neue Datei, das Fragment (`#w=…`) bleibt; ein relativer Verweis auf eine andere importierte `.md` wird `/stroemipedia/<neue Adresse>`; `/stroemipedia/…`- und `/wiki/…`-Links, `:::einbau` und fremde Adressen bleiben, was sich nicht auflösen lässt, bleibt stehen und steht als Hinweis da. **Gleicher Titel** unter derselben Seite: Es entsteht trotzdem eine neue Seite mit eigener Adresse, die vorhandene bleibt unberührt (Hinweis im Ergebnis). Alles oder nichts: Scheitert etwas, entsteht keine Seite und keine Datei. Keine Mails an Beobachter. Höchstens 200 MB je ZIP (`WIKI_IMPORT_MB`), 2000 Einträge, 500 Seiten.
- Beim Umbenennen einer Seite ändert sich ihre Adresse, die bisherige bleibt aber gültig – vorhandene Links und Lesezeichen laufen weiter.
- **Es bearbeitet immer nur eine Person.** Wer den Editor öffnet, bekommt den Schreibplatz; alle anderen sehen in der Kopfzeile „✏ Anna bearbeitet“ und einen ausgegrauten Knopf „Bearbeiten“, der sagt, worauf zu warten ist. Entreißen lässt sich der Platz nicht – der Editor speichert von allein, und wer ihn mitten im Satz verlöre, merkte vom Verlust seiner Arbeit nichts. Jeder offene Reiter meldet sich alle 15 Sekunden; bleibt die Meldung aus, wird der Platz nach 45 Sekunden frei, und wer dann zurückkommt, erfährt, dass hier nicht mehr gespeichert wird. **Warten muss trotzdem niemand:** Wer liest, während jemand anderes schreibt, sieht dessen gespeicherte Änderungen von selbst erscheinen – der Herzschlag der Leser läuft solange alle 4 statt alle 15 Sekunden, und weicht die gespeicherte Fassung von der gezeigten ab, wird der Artikel nachgezeichnet. Die Lesestelle bleibt dabei stehen: gemerkt wird der oberste sichtbare Absatz, nicht die Bildlaufhöhe, sonst rutschte man bei jedem oberhalb eingefügten Satz weiter. Unter einer Textauswahl oder einem offenen Dialog wird nicht gezeichnet (Prüfstand: `tests/live_mitlesen.html`). Gespeichert wird nur, wenn die Fassung noch stimmt: Die Prüfung sitzt im Schreibzugriff selbst, zwei gleichzeitige Speichervorgänge können sich also nicht mehr gegenseitig überschreiben.
- Der Editor speichert von allein, kurz nach jeder Änderung – einen Speichern-Knopf gibt es nicht; der Stand steht links in der Kopfzeile: sofort nach der ersten Eingabe „Ungespeichert“, während der Anfrage „Speichert …“, danach „Gespeichert 13:02“ (als Live-Region, die Vorlesehilfe sagt den Wechsel an; Gerätetest 01.11.2026). Hochgeladene Bilder und Dateien melden sich mit „Bild hochgeladen“ bzw. „Datei hochgeladen“; ein rein numerischer Dateiname (Fotoauswahl von Android: „48698.jpg“) wird nicht zum Alternativtext – den trägt man dann am Bild unter „ALT“ ein. Das `/`-Menü öffnet über dem Cursor, wenn darunter (etwa über der Bildschirmtastatur) kein Platz ist, und ist höchstens 40 % des sichtbaren Bereichs hoch; der Cursor bleibt beim Tippen unter den klebenden Leisten sichtbar. Zwischenstände füllen weder den Verlauf noch lösen sie Benachrichtigungen aus: Alle Speichervorgänge einer Bearbeitung – vom Öffnen bis zum Verlassen des Editors – gehören zu einer Fassung; jede neue Bearbeitung legt eine eigene an, auch kurz nach der vorigen. Die Post an Beobachter folgt einer eigenen Regel: Wer dieselbe Seite kurz hintereinander mehrfach bearbeitet, schreibt zwar jedes Mal eine eigene Fassung, löst aber innerhalb von zehn Minuten nur eine Nachricht aus. Einen „Verwerfen“-Knopf gibt es nur noch beim Anlegen einer neuen Seite; bei einer vorhandenen holt der Verlauf ältere Stände zurück. Eine neue Seite wird weiterhin ausdrücklich über „Anlegen“ erzeugt.
- Speichern zwei Leute dieselbe Seite, wird die zweite Änderung nicht stillschweigend überschrieben: Der Server lehnt sie ab, das automatische Speichern hält an und weist auf die zwischenzeitliche Fassung im Verlauf hin.

**Nutzer**
- Anmeldung mit E-Mail und Passwort, Passwort per E-Mail zurücksetzen. Nach zehn Fehlversuchen je Adresse oder je Absender-IP ist eine Viertelstunde Pause – gegen das Durchprobieren von Passwörtern. „Konto anfragen“: Name, Gliederung, E-Mail und Passwort sind Pflicht, eine Begründung ist optional. Die Anfrage geht per E-Mail an die Verwaltung; erst nach Freigabe ist die Anmeldung möglich (der Nutzer wird per Mail informiert). Der allererste Nutzer bekommt überall Verwaltungsrecht.
- Eigenes Zeichen: Liegt `app/static/img/maskottchen.webp` (oder .png/.jpg/.svg) bereit, steht es in Kopfzeile und Anmeldung anstelle des DLRG-Schriftzugs – 44 px in der Leiste, 96 px auf dem Anmeldebildschirm. WebP wird bevorzugt; ein knapp bemessenes Bild (rund 256 px Kantenlänge) reicht dafür und spart gegenüber einer 1024er-PNG-Vorlage rund das Vierzigfache an Übertragung.
- Profil mit Name, Gliederung, Telefon und Profilbild (quadratisch auf 256 px gebracht; es steht an den Autorenangaben der Artikel).
- **Rechte-Matrix statt Rollen:** Jedes Konto trägt je Modul eine Stufe – **kein Zugriff** (0), **Mitglied** (1), **Redakteur** (2, nur in Strömipedia, Ankerplätzen und Riegenkarten) oder **Verwaltung** (3) –, gesetzt unter „Leitstelle → Nutzer“ direkt in der Tabelle oder im Nutzerdialog. Die Module: **Strömipedia** (Mitglied: alle nicht beschränkten Seiten lesen und kommentieren, eigene Kommentare ändern, löschen, erledigen – bearbeiten nur Seiten, für die es selbst freigegeben ist, samt Unterseiten wie ein Redakteur (seit dem 02.11.2026, vorher genau diese Seite), ohne sie zu verschieben, dafür auch Bilder hochladen; Redakteur: dazu eigene Seiten und Unterseiten anlegen (auch unter fremden Seiten außerhalb freigegebener Abschnitte), duplizieren, bearbeiten, verschieben, in den Papierkorb legen und wiederherstellen, Lesen einschränken, Bearbeiter freigeben, Kommentare an eigenen Seiten erledigen und löschen, freigegebene fremde Seiten samt Unterseiten bearbeiten (nicht verschieben – verschieben darf nur, wer die Seite auch in den Papierkorb legen darf), Bilder und Dateien hochladen; Verwaltung: alle Seiten, beschränkte lesen, für alle Angemeldeten freigeben – das darf nur sie –, HTML-Bausteine, ZIP-Import, Ersteller ändern), **Ankerplätze** (Mitglied: Karte, Alben und Bilder ansehen; Redakteur: eigene Alben anlegen – auch per Ablegen auf der Karte –, bearbeiten, löschen, Bilder nur in eigene Alben, ein einzelnes Bild zusätzlich, wer es hochgeladen hat; Verwaltung: alle Alben, auch Bilder in fremde), **Riegenkarten** (Mitglied: nur die Lehrgänge, in denen das Konto als Ausbilder eingetragen ist – dort bewerten, abhaken, Medien, Kommentar; als Leitung eingetragen auch leiten; fremde Lehrgänge samt Teilnehmenden, Bewertungen und Medien sind „nicht gefunden“ (404); Redakteur: dazu Lehrgänge anlegen, kopieren und als neuen Lehrgang importieren (wird Leitung), Kataloge lesen und als Vorlage nutzen, eigene anlegen und pflegen; Verwaltung: alle Lehrgänge und Kataloge), **Materialablage** (Mitglied: das Modul nutzen – Katalog, Suche, Profil –, Bestand nur über Freigaben je Ordner; Verwaltung, die **Material-Verwaltung**: Produktkatalog pflegen, alle Bestände aller Gliederungen, Gliederungen anlegen, jede Freigabe – prüfen nur mit Häkchen „Prüfer“, Urkundennummer und Prüffreigabe; siehe „Materialablage“), **Leitstelle** (nur kein Zugriff oder Verwaltung: Anfragen freigeben, Nutzer anlegen, bearbeiten, deaktivieren, löschen – Inhalte gehen auf den Löschenden über, auch Kataloge der Riegenkarten –, Reset-Mail auslösen (mit Rückfrage), Einstellungen). Verwaltung in der Leitstelle schließt alle Rechte überall ein. Neue Konten (Kontoanfrage und Leitstelle) starten als Mitglied in der Materialablage und sonst ohne Zugriff – in der Strömipedia also im Lesemodus (seit dem 18.10.2026, am 01.11.2026 bestätigt; bis dahin Mitglied in Spots und Wiki, vorhandene Konten behalten ihre Stufen); Redakteure vergibt die Plattform-Verwaltung von Hand; mit der Materialablage braucht ein Konto einen Namen; wem ein Modul fehlt, sieht den Reiter nicht und bekommt auf Adresse und Schnittstelle 403 – auch die Mediendateien des Moduls. Die Oberfläche blendet aus, was die Stufe nicht erlaubt (kein „Neue Seite“, „Album anlegen“, „Lehrgang anlegen“, „Kataloge“ für Mitglieder; Bearbeiten, Kopieren, Löschen nach den Angaben des Servers je Gegenstand), statt 403 zu zeigen. Ausnahme Strömipedia: Ohne Stufe dort bleibt der Reiter und führt in den Lesemodus mit den für alle Angemeldeten freigegebenen Seiten (siehe oben); wer gar kein Modul hat, landet dort statt auf einer Hinweisseite. Niemand kann sich selbst die Verwaltung entziehen. Mehr unter [„Stufe Redakteur“](#stufe-redakteur-01112026).
- **Nutzerliste der Leitstelle** (Gerätetest 01.11.2026): Über der Tabelle sucht ein Feld in Name, E-Mail und Gliederung, daneben filtert „Alle Rollen“ nach Prüfer, deaktivierten Konten, Konten ohne Zugriff oder einer Stufe je Modul („Riegenkarten: Redakteur“); darunter steht „n von m Konten“. Gefiltert wird im Browser, die Liste bleibt vollständig geladen. In der Kartenansicht (unter 760 px Inhalt, also Fenster unter 800 px – Telefon, kleines Tablet hochkant) ist jede Karte zugeklappt – Name als Aufklapper, Gliederung, die Rollen als Marken; Auswahlfelder und Knöpfe erst nach dem Aufklappen, so trifft ein Tipp beim Rollen kein Feld, das sofort speichert. Die Spaltenköpfe der Tabelle brechen an weichen Trennstellen um („Material-/ablage“), statt ineinanderzulaufen. Zwischen 760 und 1 100 px Inhalt (Fold innen, Tablet hochkant) ist die Tabelle 1 100 px breit und rollt in ihrem Rahmen seitwärts, der Name bleibt links stehen – so stehen die Auswahlfelder mit „Verwaltung“ ganz da.
- Beim Umstieg von den früheren Rollen werden sie einmalig übertragen: Administrator → überall Verwaltung, die damalige Rolle „Redakteur“ (bis 16.10.2026 – nicht die heutige Stufe) → Verwaltung in Spots und Wiki, Nutzer → Mitglied in Spots und Wiki, das Prüfer-Häkchen → Mitglied in Prüfungen.

**Anmeldeseite**
- Slideshow mit zufälligen Bildern aus den Ankerplätzen (langsam wandernd, überblendet; abschaltbar mit `LOGIN_SLIDESHOW=false`, respektiert „Bewegung reduzieren“). Die Bilder werden über signierte, 24 h gültige Links ausgeliefert (bleibt ohne Anmeldung). Eine Strömipedia ohne Anmeldung gibt es seit dem 01.11.2026 nicht mehr. Seit dem Gerätetest (01.11.2026) in einer eigenen kleinen Fassung – WebP, längste Kante 1000 px, angelegt beim ersten Abruf unter `media/slide/` (ein Zehntel der Web-Variante) –; geladen werden nur das gezeigte und das nächste Bild, erst wenn die Fläche im Bild ist, und in einem verborgenen Reiter wird nicht weitergeblättert.
- Eine Überschrift erster Ordnung je Seite (Anmelden, Konto anfragen, Passwort zurücksetzen, Neues Passwort setzen); „Passwort anzeigen“ als Häkchen unter dem Passwortfeld (auch „Passwort ändern“ im Profil); Fehlermeldungen werden vorgelesen (`role="alert"`, die Felder verweisen mit `aria-describedby` darauf), nach „falsch“ steht der Fokus im Passwortfeld; die Antworten auf „Link anfordern“ und „Konto anfragen“ sind Live-Regionen. Nach dem Anmelden ersetzt die Zielseite die Anmeldeseite im Verlauf (Zurück führt nicht mehr auf ein leeres Anmeldeformular).

**Riegenkarten** (Modul „pruefungen“; nur mit Zugang zu den Riegenkarten)
- Lehrgänge mit Titel, Nummer, Zeitraum, Ort, Status, Lehrgangsleitung und Referierenden (immer Konten mit Stufe in den Riegenkarten, gesucht über Name oder E-Mail-Adresse – Freitext-Ausbilder gibt es seit dem 01.11.2026 nicht mehr, siehe [„Ausbilder nur mit Konto“](#ausbilder-nur-mit-konto-01112026)). Liste mit Suche, Jahresfilter, Teilnehmerzahl, Fortschritt („18/24 Leistungen abgenommen“) und – unter dem Titel – offenen Mängeln und Teilnehmenden mit offenen Voraussetzungen.
- **Lehrgangsseite** (Gerätetest 01.11.2026): Die Reiter Teilnehmende, Leistungen, Bewertung und Mängel kleben beim Rollen unter der Kopfleiste (rollt die Kopfleiste mit, ganz oben); ein Reiterwechsel weit unten beginnt direkt unter ihnen. Status, Nummer, Datum, Ort, Leitung, Beschreibung und Fortschritt stehen am Telefon (bis 760 px) und bei weniger als 600 px Höhe in der zugeklappten Zeile „Angaben zum Lehrgang“ (Status, Datum und Stand darin auch zugeklappt), sonst offen. „Bearbeiten“ und „Import“ stehen für die Leitung im Menü „Mehr“ neben dem Titel. Ein neu angelegter Lehrgang öffnet bei den Teilnehmenden („Noch niemand eingetragen“ mit dem Weg zum Import).
- Lehrgänge anlegen, kopieren und als neuen Lehrgang importieren darf, wer in den Riegenkarten mindestens **Redakteur** ist. Wer über den Dialog anlegt, steht darin vorbelegt als Leitung; wer eine Liste als neuen Lehrgang importiert, wird Leitung – auch mit Stufe Verwaltung (Entscheidung des Nutzers vom 01.11.2026; vorher trug sich die Verwaltung beim Import nicht ein). Innerhalb eines Lehrgangs zwei Stufen: **Lehrgangsleitung** (wer im Lehrgang mit dem Kennzeichen „Leitung“ eingetragen ist – mehrere Personen je Lehrgang sind möglich) und die Verwaltung der Riegenkarten legen Teilnehmende, Voraussetzungen und Leistungen an, ändern und löschen sie; alle anderen Prüfenden – etwa Referierende – nehmen Prüfungen ab und haken Voraussetzungen ab.
- Je Teilnehmendem ein Profilbild, ein freier Kommentar der Prüfenden und das **Lehrgangsergebnis** der Leitung (bestanden / nicht bestanden). Mit dem Ergebnis sind die Prüfungsdaten der Person eingefroren – keine neuen Versuche, Medien oder Haken, bis die Leitung das Ergebnis aufhebt. Eine Person mit vermerktem Ergebnis lässt sich auch nicht löschen, und Leistungen, Kriterien oder Voraussetzungen, an denen eingefrorene Bewertungen oder Haken hängen, lassen sich weder ändern noch löschen; an einer solchen Leistung lassen sich seit dem 01.11.2026 auch keine Kriterien mehr anlegen oder umsortieren (409 mit Klartext; der Dialog zeigt die Kriterien nur zum Lesen und einen Satz statt „Kriterium anlegen“). Ist das beim Öffnen des Leistungsdialogs schon so, steht seit dem 02.11.2026 alles nur zum Lesen da (Beschreibung als Text), über der Knopfzeile ein Satz, was nicht mehr geht, und „Speichern“ ist ausgegraut (fokussierbar, ein Klick hebt den Satz hervor) – vorher scheiterte „Speichern“ erst mit 409. Den Lehrgang als Ganzes darf die Leitung weiterhin löschen.
- **Diktieren per Mikrofon** an den Kommentarfeldern (Web Speech API des Browsers, Deutsch). Die Erkennung läuft im Browser – Chrome und Safari können das Audio an Google bzw. Apple senden; die Einstellung `SPRACHEINGABE` schaltet den Knopf ab.
- **Prüfungsleistungskataloge**: Vorlagen für die Prüfungsleistungen eines Lehrgangs, unabhängig von einer einzelnen Durchführung. Auch Katalog-Leistungen können eine **Kriterienliste** tragen, als reine Vorlage ohne Bewertungsteil (ein Katalog hat keine Versuche). Sehen und anlegen darf, wer in den Riegenkarten mindestens Redakteur ist (Auswahl beim Anlegen eines Lehrgangs, Knopf „Kataloge“ neben „+ Lehrgang anlegen“); ändern, löschen und die Leistungen samt Kriterien darin pflegen darf der Ersteller eines Katalogs, alle Kataloge die Verwaltung der Riegenkarten. Ein Mitglied sieht keine Kataloge. Die Leistungen eines gewählten Katalogs werden beim Anlegen einmalig samt ihrer Kriterien in den Lehrgang **kopiert** – eine spätere Änderung am Katalog (auch sein Löschen) wirkt sich nie auf einen schon angelegten Lehrgang aus. Individuelle Leistungen lassen sich unabhängig davon jederzeit ergänzen, auch während der Lehrgang läuft.
- **Import** der Teilnehmerliste (.xlsx, etwa die ISC-Checkliste „Voraussetzungen“ mit allgemeinen Lehrgangsinformationen): Die Datei wird vorab gelesen und in einer Vorschau gezeigt – erkannte Spalten, Zuordnung (Stammdaten, Voraussetzung, weitere Angabe, ignorieren) per Auswahl korrigierbar, Warnungen zu Leerzeilen und Duplikaten. Kopfzeilen der Datei (Nummer, Titel, Zeitraum, Ort) füllen leere Lehrgangsfelder; Spalten mit ja/nein werden zu **Voraussetzungen** des Lehrgangs, bereits erfüllte Häkchen werden übernommen und als „importiert“ protokolliert. Ein zweiter Import derselben Liste aktualisiert statt zu verdoppeln. Gleichnamige Teilnehmende werden dabei nie geraten: Passen mehrere Dateizeilen auf eine Person ohne Geburtsdatum im Lehrgang, werden sie als mehrdeutig gemeldet und nicht übernommen. Der Import prüft Dateien vor dem Einlesen: höchstens 500 Archiv-Einträge und 200 MB entpackt, 20 Arbeitsblätter, 20.000 Zeilen × 300 Spalten bzw. 500.000 Felder je Arbeitsmappe (gezählt, bevor die Datei geladen wird – leere Zellen, Zeilen und die ganze Fläche verbundener Zellen, Links und Kommentare zählen mit), 2.000 Datenzeilen je Import und 50 Spalten mit weiteren Angaben (Titel 100, Werte 500 Zeichen); Überschreitungen ergeben eine Meldung mit Hinweis, was zu tun ist.
- **Voraussetzungen** je Teilnehmendem abhaken – unter jedem Haken steht klein, wer ihn wann gesetzt hat; jede Änderung bleibt im Verlauf („Verlauf“ erscheint, sobald es einen Eintrag gibt). Teilnehmende mit offenen Voraussetzungen sind markiert. Am Telefon hat jede Person eine Zeile „Voraussetzungen · 4 von 6 erfüllt“ zum Aufklappen – aufgeklappt, solange etwas offen ist; wer sie auf- oder zuklappt oder darin abhakt, behält den Zustand. Jedes Häkchen meldet „Gespeichert – Name: „Voraussetzung“ erfüllt“; solange die Antwort des Servers fehlt, steht darunter „Wird gespeichert …“ (nach zehn Sekunden „Noch nicht gespeichert – keine Antwort vom Server“). **Ohne Netz** springt der Kasten zurück und die Meldung sagt „Nicht gespeichert – keine Verbindung.“ – es gibt keine Warteschlange; ebenso beim Speichern einer Bewertung und eines Kommentars (die Eingaben bleiben im Dialog stehen) und beim Lehrgangsergebnis (eine Rückfrage ohne Eingaben – nach dem Fehlschlag noch einmal vermerken).
- **Prüfungsleistungen** mit Beschreibung (Editor wie im Wiki: keine feste Toolbar, stattdessen eine schwebende Formatleiste bei Textauswahl für Überschrift/Text, Liste, fett, kursiv, Link), optionalem Zeitansatz und optionaler **Kriterienliste** (einzeln abhakbare Punkte zusätzlich zur Beschreibung); sortierbar. Die Kriterienliste lässt sich schon beim Anlegen einer Leistung mit aufbauen, nicht erst danach – als lokaler Entwurf, bis die Leistung gespeichert wird. Ein Lehrgang lässt sich samt Leistungen, ihren Kriterien und Voraussetzungs-Definitionen **kopieren** – ohne Teilnehmende und Ergebnisse.
- **Prüfungen abnehmen** in einer Matrix Teilnehmende × Leistungen, auf dem Telefon als Liste je Leistung oder je Teilnehmendem. Bei höchstens 500 px Höhe (Telefon quer) ist die Matrix kompakt: ohne Gliederung unter dem Namen und ohne „wer/wann“ in den Zellen, Zeilen 54 statt 91 px (Gerätetest 01.11.2026). Hat eine Leistung eine Kriterienliste, zeigt die Zelle in Matrix und „je Leistung“ „Kriterien erfüllt/gesamt“ (z. B. „Kriterien 1/2“; reicht die Zelle nicht, in einer zweiten Zeile) als schnellen Indikator, ohne sie öffnen zu müssen; in „je Teilnehmende“ steht dort mehr Platz zur Verfügung, deshalb erscheint direkt die volle Kriterienliste mit ✅/❌ je Punkt unter Zeit und Kommentar des letzten Versuchs; dort ist außerdem der Titel jeder Leistung grün (bestanden), rot (mangelhaft) oder unverändert (noch kein Versuch) eingefärbt. Der Bewertungsdialog hat eine **Stoppuhr** (nur bei Zeitansatz; überlebt Neuladen und Bildschirmsperre, weil der Startzeitpunkt im Browser liegt), ein immer manuell befüllbares Zeitfeld, die **Kriterienliste** der Leistung – falls vorhanden – mit einem dreistufigen Haken je Punkt (Antippen wechselt nicht bewertet → ✅ erfüllt → ❌ nicht erfüllt → nicht bewertet), große Knöpfe 👍 bestanden / 👎 mangelhaft, einen Kommentar (Pflicht bei mangelhaft) und Bilder/Videos direkt von der Kamera. Jede Bewertung trägt Prüfer und Zeitpunkt; Änderungen werden als „bearbeitet von … am …“ gekennzeichnet, der alte Stand bleibt im Verlauf.
- **Nachprüfung** als zusätzlicher Versuch; die Erstprüfung bleibt sichtbar, für die Matrix zählt der letzte Versuch.
- **Mängel / Feedback**: alle mangelhaften Leistungen je Teilnehmendem mit Kommentar, Medien, Zeit, Prüfer und Stand der Nachprüfung – filterbar und als Druckansicht für das Feedbackgespräch.
- **Druckansicht „je Teilnehmende“**: In der Bewertungsansicht „je Teilnehmende“ zeigt „Druckansicht“ alle Prüfungsleistungen der gewählten Person auf einer eigenen Seite – mit Profilbild, freiem Kommentar sowie je Leistung Ergebnis, Zeit, Kommentar und den hochgeladenen Bildern/Videos. Drucken oder als PDF speichern. Der Seitentitel (Reiter, Browserverlauf) nennt nur Ansicht und Lehrgang, nicht die Person.
- Lehrgangs-, Katalog- und Leistungslisten: „Öffnen“ bzw. „Bearbeiten“ als Knopf, Seltenes (Bearbeiten, Kopieren, Verschieben, Löschen) im Zeilenmenü „Mehr“; rot ist je Ansicht nur die Hauptaktion („Lehrgang anlegen“, „Bewertung speichern“ …).
- Die Medien liegen in einem eigenen Ordner und werden nur an Konten ausgeliefert, die den Lehrgang sehen (die Verwaltung der Riegenkarten alle).

**Materialablage** (Ausrüstungsbestand und Prüfnachweise; nur mit Zugang zur Materialablage – „Meine PSA“ auch ohne; Stand: Phasen 1 bis 4 freigegeben – zuletzt Jahresbericht und Mailfehler-Protokoll, Änderungsanträge an alle Stammdaten (Schema 23 und 24), Bestandteil-Listen (Schema 25), Rückbau der Set-Funktion mit Set-Protokollen im Prüfdurchgang (Schema 26 und 27), Aussondern nur durch den Materialwart (Schema 28), Anträge ohne Materialwart (Schema 29); die Lieferungen 2 und 2b (Sets mit Komponenten) sind durch den Rückbau ersetzt. Nachbesserung vor dem Merge nach main (26.10.2026, **Schema 30**), Prüfsumme und Kennung für den Lebenslauf (27.10.2026, **Schema 31**), Liste nach dem Merge – Materialablage (27.10.2026, **Schema 32**), Prüfformular eines anderen Produkts übernehmen (04.11.2026, **Schema 35**), Nachbesserung nach der Sicherheitsprüfung (04.11.2026, **Schema 36**), Aufräumen (04.11.2026, **Schema 37**), Formular-Pool je Kategorie (04.11.2026, **Schema 38**; ersetzt „übernehmen“ aus Schema 35/36), Untergruppen in Prüfformularen (04.11.2026, **Schema 39**). Verlauf in `CHANGELOG-Material.md`)
- Verwaltet PSA gegen Absturz und Seiltechnik sowie Wasser-Material (Schwimmwesten, Wasserrettungshelme, Wurfsäcke, Neopren- und Trockenanzüge) aller Gliederungen in einer Instanz. Lampen, Pumpen, Funk, Verbrauchsmaterial, Ausleihe und Fahrzeuginventar gehören bewusst nie hinein – das Modul ersetzt Prüfkarte und Excel-Liste des Materialwarts, kein Lager.
- **Rollen**: Die Stufe in der Materialablage setzt die Plattform-Verwaltung in der Leitstelle wie bei den anderen Modulen. **Mitglied** heißt Zugang zum Modul (Katalog, Suchfeld, Profil, „Meine Freigaben“); Bestand sieht ein Mitglied nur über **Freigaben je Ordner** (siehe unten), die der Verwalter eines Ordners vergibt – getrennt von der Stufe. **Verwaltung** heißt **Material-Verwaltung**: Sie pflegt den Produktkatalog (Kategorien, Produkte, Herstellerdokumente, Prüfformulare, Produktmeldungen, Rückrufe), sieht und verwaltet den ganzen Bestand aller Gliederungen, legt die Gliederungen auf oberster Ebene an und vergibt jede Freigabe; die Plattform-Verwaltung (Verwaltung in der Leitstelle) gehört immer dazu. Änderungsanträge an Stammdaten entscheiden aber nur die Materialwarte des Ordners – auch die Material-Verwaltung nur mit eigener Freigabe „verwalten“ dort oder darüber; sie darf sie sich selbst geben (Freigaben und Journal zeigen es). Eine Gliederung in einem Ordner legt an, wer den Oberordner verwaltet. Ohne Stufe wirken weder Freigaben noch das Häkchen; die eigenen Daten bleiben erreichbar – die hinterlegte Unterschrift lässt sich im Profil entfernen, die eigene Produktmeldung löschen. Dazu das Häkchen **Prüfer** (Sachkundiger) am Konto, plattformweit und von der Plattform-Verwaltung gesetzt; die Urkundennummer trägt der Prüfer selbst im Profil ein (Abschnitt „Urkundennummer und Unterschrift“); bis dahin zeigen Profil, Artikel und Nutzerliste „Urkundennummer fehlt“. **Prüfen** darf nur, wer Stufe, Häkchen, Urkundennummer **und** eine gültige Prüffreigabe für den Ordner hat – auch Materialwarte und die Material-Verwaltung; das Häkchen setzt die Plattform-Verwaltung, die Prüffreigabe der Materialwart. Zum Modul gehört ein Name im Profil: Wer handelt, steht mit Namen im Journal und in den Protokollen – nie nur mit der E-Mail; das Feld „Anmeldung“ eines Prüf- oder Aussonderungsprotokolls nennt zusätzlich die E-Mail-Adresse beim Festschreiben (die „Login-Identität“ der einfachen elektronischen Unterschrift, als Kopie – Entscheidung E1 A vom 26.10.2026); ohne Namen fehlt der Reiter „Materialablage“, und die Startseite zeigt keine Kachel der Materialablage. In der Leitstelle ist die Spalte Materialablage eine Auswahl wie bei den anderen Modulen („–“, „Mitglied“, „Verwaltung“); darunter stehen „Prüfer“, klein „n Freigaben“ und gelb „wirkt nicht – kein Zugang“, wenn Häkchen oder Freigaben ohne Stufe dastehen. Setzt man im Dialog „Bearbeiten“ das Häkchen „Prüfer“, während Materialablage auf „–“ steht, springt die Auswahl auf „Mitglied“ (gespeichert wird mit „Speichern“); unter dem Häkchen steht, dass Prüfen erst mit einer Prüffreigabe am Ordner geht (mit Link zum Bestand) – solange das Konto keine gültige hat (Gerätetest 01.11.2026, M4); der Dialog zeigt auch die Freigaben des Kontos und, eingeklappt, seinen **Verlauf (Materialablage)**: die letzten 50 Einträge des Journals am Konto – Stufe, Häkchen „Prüfer“, Urkundennummer, Unterschrift (nur „hinterlegt“/„–“, ohne Bild) – mit Zeit und Handelndem (Entscheidung E3 A vom 26.10.2026; `GET /api/admin/users/<id>/journal`, nur Plattform-Verwaltung). Ist das Konto heute der einzige Materialwart einer Gliederung, fragt die Leitstelle nach, bevor die Materialablage auf „–“ geht (in der Tabelle wie im Dialog) oder das Konto deaktiviert wird, und der Dialog „Löschen“ nennt es – danach verwaltet dort nur noch die Material-Verwaltung und vergibt Freigaben; „Trotzdem speichern“ speichert. Jede Änderung an Stufe, Häkchen, Urkundennummer, Unterschrift und Freigaben steht im Journal des Moduls.
- **Freigaben je Ordner**: Wer einen Ordner verwaltet, gibt unter Bestand → Ordner → **Bearbeiten** im Reiter **Freigaben** einem Konto – auch aus einer anderen Gliederung – das Recht **lesen** (alles ansehen, CSV und Protokoll-ZIP, Lebenslauf, Journal, zugeordnete Personen; dazu **Mängel melden – das sperrt den Artikel sofort**), **prüfen** (die Prüfsicht: Artikel, Prüfungen samt Protokollen, Durchgänge samt Sammel- und Set-Protokollen und „Alle Protokolle (ZIP)“, dazu prüfen, sperren und Durchgänge führen – kein Export des Ordners (CSV, Protokoll-ZIP), kein Lebenslauf, kein Journal, keine Personen) oder **verwalten** (dazu Ordner und Artikel pflegen, aussondern, Personen zuordnen, Freigaben vergeben). Eine Freigabe gilt im Ordner und in allen Unterordnern; Rechte addieren sich. lesen und verwalten gelten dauerhaft oder bis zu einem Tag. Freigaben gibt es nur an Konten mit Zugang zum Modul (Stufe Mitglied oder Verwaltung). Eine Prüffreigabe wirkt nur bei Konten mit Häkchen und Urkundennummer; befristet (höchstens 24 Monate) ist sie nur für externe Prüfer – wer dort auch lesen oder verwalten hat, prüft dauerhaft, und zwar nur, solange dieses Grundrecht gilt (entzogen oder abgelaufen, wirkt die dauerhafte Prüffreigabe nicht mehr). Der letzte Tag zählt mit: Eine Freigabe „bis 31.12.“ gilt den ganzen 31.12. und endet um 0:00 Uhr deutscher Zeit. Man wählt eine **Rolle** (Karten, beim Anlegen und Ändern dieselben): Führungskraft (lesen), Materialwart (verwalten), Materialwart und Prüfer, Prüfer (lesen und prüfen) oder Externer Prüfer (nur prüfen, mit Enddatum) – seltene Kombinationen unter „Einzeln“ (Grundrecht und Prüffreigabe je mit eigener Gültigkeit). Die **Gültigkeit** ist eine Radiogruppe „dauerhaft / bis [Datum]“ mit immer sichtbarem Datumsfeld; bei einer Rolle gilt sie fürs Grundrecht, das Prüfen von Prüfer und Materialwart und Prüfer ist immer dauerhaft und gilt, solange das Grundrecht gilt – auch wenn der Vergebende selbst nur befristet verwaltet („Prüfen folgt dem Grundrecht“, Entscheidung des Nutzers vom 03.11.2026; der Server erlaubt eine dauerhafte Prüffreigabe von einem befristeten Verwalter, wenn die Person dort in derselben Anfrage ein Grundrecht bekommt oder dort bzw. darüber schon eines hat). „dauerhaft“ fürs Grundrecht gibt es nur, wer selbst dauerhaft verwaltet, sonst endet es spätestens mit der eigenen Verwalterfreigabe; dann ist „bis“ gewählt und das Datumsfeld leer („Du verwaltest hier bis … – länger geht nicht.“), das Datum trägt man selbst ein. Ein Datum ist nirgends vorbelegt außer beim externen Prüfer: Er bekommt nur „bis“ (vorgeschlagen der 31.12. des Folgejahres, höchstens 24 Monate und nicht länger als das eigene Verwalten). Ein Rollenwechsel lässt, was man an der Gültigkeit selbst gesetzt hat. Befristete Prüffreigaben interner Personen aus der Zeit davor bleiben, wie sie sind (der Dialog öffnet sie unter „Einzeln“); auf dauerhaft bringt sie die Rolle „Prüfer“ bzw. „Materialwart und Prüfer“ oder unter „Einzeln“ die Prüffreigabe „dauerhaft“. Rollen, die nicht gehen, sind ausgegraut, der Grund steht als Satz darunter (z. B. Prüfen ohne Qualifikation, eigene Rechte erweitern); „Alle Prüffreigaben verlängern“ verlängert die befristeten eines ganzen Zweigs auf einmal. Die Listen „Hier vergeben“, „Geerbt von oben“ und „In Unterordnern“ zeigen **eine Zeile je Person** (geerbt und in Unterordnern je Person und Ordner) mit ihren Rechten und deren Zustand, z. B. „verwalten (dauerhaft)“ und „prüfen (bis 31.12.2027)“; die Zahl im Kopf zählt diese Zeilen (geerbt und in Unterordnern also Person und Ordner). **„Ändern“** öffnet **„Rechte ändern“** mit denselben Rollenkarten, vorgewählt die Rolle zu den heutigen Rechten (passt keine oder ist ein Recht nicht änderbar: „Einzeln“), dazu Gültigkeit und Notiz (zugeklappt, offen, wenn es eine gibt) – gespeichert in einem Schritt, ganz oder gar nicht (lehnt der Server ein Recht ab, bleibt alles, wie es war, und die Meldung steht an der Gültigkeit bzw. der Rolle); fällt ein Recht weg, fragt der Dialog vorher, ohne Änderung schließt er ohne Anfrage (Wunsch des Nutzers vom 02.11.2026, „Rollen wie beim Anlegen“); **„Entziehen“** nimmt nach einer Rückfrage alle Rechte der Person an diesem Ordner. Wählt man unter „Freigabe anlegen“ jemanden, der am gewählten Ordner schon Rechte hat, steht „… hat hier schon: …“ mit „Rechte ändern“ da (Wunsch des Nutzers vom 02.11.2026). Verlauf, „Meine Freigaben“ und die Leitstelle bleiben je Freigabe. Ein Verwalter vergibt nie länger, als er selbst verwaltet (eine dauerhafte Prüffreigabe gilt ohnehin nur, solange das Grundrecht der Person gilt), ändert fremde Freigaben nur, wenn er sie selbst so hätte vergeben dürfen (eine dauerhafte Prüffreigabe nur, wenn das Grundrecht, das sie trägt, nicht länger läuft als sein eigenes Verwalten), und kann keine Gliederung ohne einen Verwalter lassen, der mindestens so lange bleibt. Die Notiz an einer Freigabe sehen nur die Verwalter des Ordners und die Material-Verwaltung. Auf der Übersicht stehen unter **Meine Freigaben** die eigenen, gelb, was in 30 Tagen abläuft; im Ordnerkopf sieht der Verwalter, wie viele in den nächsten 30 Tagen ablaufen. Abgelaufene bleiben in der Liste stehen, bis jemand sie verlängert oder entfernt; „Meine Freigaben“ nennt bei abgelaufenen das Datum und wer verlängern kann. Ohne Freigabe sieht ein Konto keinen Bestand, und was es nicht sieht, behandelt das Modul, als gäbe es das nicht – auch in Suche, Zählungen, Exporten und Mediendateien. Oberordner ohne eigenes Recht erscheinen im Baum nur als grauer Pfad, „Gesperrt“ und „Ausgesondert“ einer Gliederung, die man nicht ganz sieht, nur mit den eigenen Artikeln. Gesperrte und ausgesonderte Artikel gehören weiter zu ihrem Herkunftsordner – für Rechte, Export und Durchgänge.
- **Verschieben zwischen Gliederungen** darf nur, wer beide Gliederungen verwaltet, oder die Material-Verwaltung. Mit einem Ordner wandern seine Freigaben (was vom alten Oberordner geerbt war, gilt am neuen Ort nicht mehr) und seine gesperrten und ausgesonderten Artikel in die Systemordner der neuen Gliederung. Verlässt ein Artikel den Bereich eines offenen Prüfdurchgangs – auch innerhalb einer Gliederung –, nimmt der Durchgang ihn mit dem Grund „verschoben am …“ aus; das Sammelprotokoll nennt dann keinen Ordner und keinen Prüfer der anderen Gliederung. Einen vorhandenen Ordner zur Gliederung machen ist ebenfalls ein Wechsel für alles darin: Das darf nur, wer die Gliederung darüber verwaltet, oder die Material-Verwaltung (die Plattform-Verwaltung gehört dazu).
- **Katalog**: Kategoriebaum mit Normen und Vorgaben, Produkte (Hersteller, Modell, Bemerkung als kurzer Zusatz von höchstens 80 Zeichen, etwa die Verschlussart – überall grau direkt hinter dem Modell und vor der Artikelnummer, ohne Strich; im Katalogformat heißt der Schlüssel weiter `beschreibung`, der Import nimmt auch `bemerkung` –, Artikelnummer, Norm, Materialart, Prüfintervall, Lebensdauer) mit Dublettenprüfung auf Hersteller + Modell + Artikelnummer (Schreibweise egal, „-“ als Artikelnummer zählt als keine); jede Artikelnummer gibt es zudem je Hersteller nur einmal – bei einem anderen Hersteller ist sie ein anderes Produkt (seit dem 22.10.2026; vorher katalogweit: echte Herstellernummern wie P53 kollidieren zwischen Herstellern). Lebensdauer: Pflicht bei textil, verboten bei Metall, bei „sonstiges“ nur mit Fundstelle der Herstellerangabe. Produktbild über die vorhandene Bildverarbeitung, Herstellerdokumente (PDF/Bild oder Link) mit Version, Gültigkeitsbeginn, neuer Version, Zurückziehen und Umbenennen – ein Protokoll verweist später auf die am Prüftag gültige. Eine Dokumentdatei liegt **einmal je Inhalt** unter `media/material/dok/<SHA-256>.<Endung>` und gehört allen Dokumenten mit diesem Inhalt (Varianten, dieselbe Anleitung an vielen Produkten, Katalogimport); gelöscht wird sie erst, wenn kein Dokument sie mehr nennt – ein Dokument aus einem festgeschriebenen Protokoll nie (Schritt 18, 22.10.2026). Allgemeine Dokumente (Pflegehinweise, Anleitungen) hängen an einer Kategorie und gelten für alle Produkte darin und darunter. Listen mit eigener Herstellerspalte, sortierbar per Klick auf den Spaltenkopf; links der Kategorienbaum als Navigation (unter 1024 px als Schublade; „☰“ dafür steht in der Katalogliste links in der Suchzeile, die beim Scrollen oben stehen bleibt – Wunsch vom 26.10.2026; nach der Wahl einer Kategorie aus der Schublade steht die Liste oben, die Dokumente der Kategorie sind dort zugeklappt, „Löschen“ steht unter „Bearbeiten“; zurück von einer Produktseite kommt die Liste an derselben Stelle wieder, mit Suche, Sortierung und allem Nachgeladenen). Suche serverseitig mit Trigramm-Index und Seiten. Pflegen darf nur die Material-Verwaltung. Ein Produkt bleibt auch mit Artikeln bearbeitbar; jede Änderung steht im Produktjournal, im Journal der Artikel („Produkt geändert“) und – seit dem 24.10.2026 – im Lebenslauf der Artikel (Stammdaten, Bild, Bestandteil-Liste seit dem Anlegen des Artikels; Rückrufe stehen dort in ihrem eigenen Abschnitt). Löschen lässt sich ein Produkt nur ohne Artikel und nur, solange keine Prüfung nach einem seiner Prüfformulare steht (seit 04.11.2026 – auch an Artikeln eines Produkts, das sein Formular übernimmt; sonst bietet die Produktseite „Löschen“ nicht an und die Schnittstelle antwortet „Das Prüfformular dieses Produkts wurde schon für Prüfungen benutzt – es bleibt im Katalog.“), seine Materialart mit Artikeln nicht ändern. **DEMO im Katalog** (Regel des Katalog-Exports, seit 04.11.2026 auch für die Übung der Einführung und „Formular übernehmen“, `katalog.demo_kategorien`/`produkt_ist_demo`/`formular_ist_demo`): DEMO ist eine Kategorie mit DEMO-Kennzeichen samt ihrem ganzen Teilbaum, ein Produkt mit Kennzeichen oder in einer solchen Kategorie, ein Formular mit Kennzeichen oder an einem solchen Ziel – auch wenn die Oberfläche Produkt oder Formular darin ohne Kennzeichen angelegt hat. Fehlt beim Anlegen eines Artikels ein Produkt, meldet der Materialwart es mit Links, Fotos und Bemerkung; die Material-Verwaltung bekommt eine Mail (gibt es keine außer der Plattform-Verwaltung, diese), legt es an (oder ordnet ein vorhandenes zu) oder lehnt mit Begründung ab, und der Melder bekommt Bescheid. Eine Meldung sehen nur die Material-Verwaltung, der Melder und wer ihren Ordner sieht; die Mail nennt nur die Gliederung.
- **Prüfformulare – Formular-Pool je Kategorie** (seit 04.11.2026, **Schema 38**; ersetzt „generisch je Kategorie,
  spezifisch je Produkt, Formular eines anderen Produkts übernehmen“ aus Schema 35/36): Jedes Prüfformular steht im **Pool
  genau einer Kategorie** (seine Heimat), versioniert wie bisher – höchstens eine Version aktiv, eine benutzte Version
  wird nie mehr geändert, Änderungen über „Neue Version“. Es gilt als **Standard** einer Kategorie (auch in
  Unterkategorien ohne eigenen Standard; eine Unterkategorie darf einen Standard aus dem Pool darüber haben) oder ist
  einem **Produkt zugewiesen** (geht dem Standard vor und bleibt, auch wenn sich der Standard ändert). Eine neue aktive
  Version gilt sofort überall, laufende Prüfungen behalten ihre. Zuweisen lässt sich ein Formular nur im Teilbaum seiner
  Heimat (Produkte und Kategorien dort; Trigger als Netz), nur mit aktiver Version; deaktivieren und löschen geht erst,
  wenn es nirgends mehr zugewiesen ist. Ein Formular mit Prüfpunkt „Länge (m)“ nur an Produkte mit Artikellänge. Ohne
  Zuweisung und ohne Standard (auch oben) ist ein Artikel nicht prüfbar – Produkt- und Kategorieseite warnen.
  **Seite „Prüfformulare“** (`/materialablage/katalog/formulare`, Knopf im Katalogkopf; **nur die Material-Verwaltung**):
  der ganze Kategorienbaum, je Kategorie ihr Standard (eigener oder „geerbt von …“) und die Formulare ihres Pools mit
  Version, Status, „Standard für …“, „zugewiesen: …“ und „gilt für n Produkte“ (aufklappbar), Suche nach Formular,
  Kategorie oder Produkt (blendet nur aus), „+ Prüfformular anlegen“ (Kategorie, Titel – Pflicht –, optional „Prüfpunkte
  übernehmen von …“) und je Zeile **„Zuweisen“**: ein Dialog mit Häkchen je Kategorie (als Standard) und je Produkt im
  Teilbaum der Heimat – je Zeile, was dort heute gilt („bisher: „X““ – ein Haken holt die Zuweisung hierher; „gilt über
  Standard …“), Längen-Konflikte ausgegraut mit Grund, Suche über den Produkten, über der Knopfzeile die Zahl der
  Änderungen; am Telefon über die ganze Fläche. Die **Formularseite** (für alle mit Modulzugang lesbar) zeigt „Gilt für“
  (Standard für, zugewiesen, insgesamt n Produkte) mit „Zuweisen“, im Menü „Kopie anlegen“ (neues Formular mit den
  Punkten dieser Version). **Produkt-, Kategorie- und Artikelseite** zeigen nur, welches Formular gilt („dem Produkt
  zugewiesen“ bzw. „Standard der Kategorie „X““, Link zur Version) – Knöpfe dafür gibt es dort nicht mehr. Wird ein
  Produkt in eine andere Kategorie oder eine Kategorie an eine andere Stelle verschoben und läge eine Zuweisung danach
  außerhalb des Pools ihres Formulars, wird sie gelöst – der Dialog sagt es vorher. Journal am Formular, am Produkt und
  an der Kategorie („Prüfformular zugewiesen“, „Standard-Prüfformular gesetzt“, „Zuweisung gelöst“). Datenmodell:
  `mat_formular` (Heimat, uid), `mat_form` = Version mit `formular_id` (Kennungen aus der Zeit davor unverändert),
  `mat_formular_zuweisung` (Kategorie oder Produkt; je Ziel höchstens eine). Die Migration (Schema 38) legt je bisherigem
  Ziel ein Formular an und prüft, dass danach für jedes Produkt dieselbe Version gilt – sonst bricht sie ab und die
  Datenbank bleibt, wie sie war. Migration und Einzelheiten: `CHANGELOG-Material.md`, „Formular-Pool je Kategorie
  (Schema 38)“. Prüfpunkte mit Gruppe, Untergruppe, Art (Ja/Nein, Text, Datum, Zahl, Foto, Unterschrift, Länge), Pflicht und Sollwert. **Untergruppen** (seit 04.11.2026, **Schema 39**): eine Ebene unter der Gruppe (Gruppe › Untergruppe › Prüfpunkte), gemischt erlaubt – in einer Gruppe stehen zuerst die Punkte ohne Untergruppe, danach die Untergruppen als zusammenhängende Blöcke (der Server ordnet so, stabil; bestehende Formulare bleiben unverändert gültig). Gespeichert als Feld `untergruppe` je Punkt (leer = keine; eine Zeile, höchstens 80 Zeichen wie die Gruppe), kopiert in die Befundzeilen der Prüfung – festgeschriebene Protokolle bleiben, wie sie waren (Trigger `mat_result_untergruppe`). Im Editor eine Stufe tiefer als die Gruppe: „+ Untergruppe“ am Ende jeder Gruppe (ohne Untergruppen neben ihrem „+ Prüfpunkt“), eingezogene Zwischenzeile mit Namensfeld (volle Breite, bricht um), Griff ⠿ (zieht die Untergruppe samt Punkten innerhalb der Gruppe und in andere Gruppen, Einfügemarke, Esc) und Knopf „Untergruppe entfernen“ (mit Punkten nach Rückfrage samt Anzahl), darunter ihre Punkte eingezogen und ihr „+ Prüfpunkt“; Punkte zieht man hinein und heraus (über die untere Hälfte des Untergruppenkopfs an ihren Anfang, über die obere ans Ende des Abschnitts davor), „Nach oben/unten“ wechselt auch über Untergruppengrenzen, „In Gruppe verschieben“ nennt die Untergruppen eingerückt. Eine Untergruppe mit Punkten braucht beim Speichern einen Namen, gleiche Namen in einer Gruppe gehen nicht (Fehler am Feld); eine leere fällt beim Speichern weg. Nur-Lese-Ansicht, Prüfung (kleinere Zwischenüberschrift, Karten eingezogen), festgeschriebene Prüfung („Gruppe › Untergruppe“ über dem Punkt) und Prüfprotokoll-PDF (Zwischenzeile in der Spalte „Prüfpunkt“, Punkte eingezogen) zeigen sie; neue Version, „Kopie anlegen“, Berichtigung, Katalog-Export/-Import (Format 3, Feld `untergruppe`; ältere Dateien ohne Feld → leer; eine andere Untergruppe gibt eine neue Version) und die Übung übernehmen sie. **Editor** (seit 04.11.2026): Jede Gruppe steht als eigene Zwischenzeile über ihren Punkten – der Name in voller Breite (bis 80 Zeichen, bricht um), Umbenennen gilt für alle Punkte darunter; Gruppen sind aufeinanderfolgende Punkte mit gleicher Gruppe, Punkte ohne Gruppe ein Block ohne Namen, zwei getrennte Blöcke gleichen Namens bleiben zwei. Je Punktzeile ein Griff ⠿ zum Ziehen (Maus und Finger, auch in eine andere Gruppe, am Rand rollt die Seite, Esc bricht ab) und ein Menü „⋯“ mit „Nach oben“/„Nach unten“ (über die Gruppengrenze als letzter bzw. erster Punkt der Nachbargruppe), „In Gruppe verschieben“ (Dialog mit den Gruppen und „Neue Gruppe“, der Punkt kommt ans Ende) und „Entfernen“ – so geht alles auch per Tastatur; je Gruppe der Knopf „Gruppe entfernen“ (mit Punkten nach Rückfrage samt Anzahl; „Gruppe nach oben“/„nach unten“ im Menü „⋯“ entfiel am 04.11.2026 auf Wunsch des Nutzers – Gruppen verschiebt nur der Griff, per Tastatur nicht). Ganze Gruppen lassen sich auch ziehen (seit 04.11.2026): Griff ⠿ vorn an der Gruppenzeile (nur bei mehr als einer Gruppe; Maus und Finger, am Rand rollt die Seite, Esc bricht ab) – der Block mit seinen Punkten bleibt beim Ziehen stehen, eine blaue Einfügemarke zeigt die Grenze zwischen zwei Gruppen, an die er kommt; nie mitten in eine Gruppe. „+ Prüfpunkt“ am Ende jeder Gruppe, unten „+ Gruppe“ (mit einem leeren Punkt) und „Speichern“; eine leere Gruppe steht bis zum Speichern mit Hinweis da und wird nicht gespeichert. Getipptes (Titel, Gruppennamen, Punkte) bleibt bei jedem Neuzeichnen stehen. Gespeichert wird unverändert die flache Liste mit `gruppe` (seit Schema 39 dazu `untergruppe`) je Punkt (`PUT /api/material/formulare/<id>`). Die Ansicht ohne Bearbeiten zeigt dieselben Zwischenzeilen. **„optional“ statt „Pflicht“** (seit 04.11.2026): Jeder Prüfpunkt ist Pflicht; im Editor setzt man das (normal leere) Häkchen „optional“ nur, wo ein Punkt entfallen darf (etwa Wartung oder Pflege) – gespeichert wird weiter `pflicht` je Punkt (Häkchen = nicht Pflicht), neue Punkte sind Pflicht; ohne Bearbeiten trägt nur ein optionaler Punkt die Marke „optional“ (die Prüfung zeigte schon nur „optional“, Prüfprotokoll und Katalogdatei bleiben). **Absätze im Prüfpunkt** (seit 04.11.2026): Enter fügt im Prüfpunkt einen Zeilenumbruch ein; der Server behält ihn (`\r\n` → `\n`, mehr als eine Leerzeile wird eine, Leerzeilen am Rand fallen weg, je Zeile wie bisher ohne Steuerzeichen und doppelte Leerzeichen; einzeilige Punkte unverändert; höchstens 1000 Zeichen); Formularansicht, Prüfung, Prüfprotokoll-PDF, neue Version und Katalog-Export/-Import übernehmen ihn, Meldungen nennen den Punkt in einer Zeile. Die Markierung „kritisch“ (ein Mangel an diesem Punkt schloss „einsatzbereit“ aus) ist seit dem 03.11.2026 ganz entfernt: kein Häkchen im Formular-Editor, keine Marke in Prüfung und Protokoll, keine Sperre – bei jedem Mangel wählt der Prüfer das Ergebnis selbst. Vorhandene Markierungen bleiben in der Datenbank (Spalte `is_critical`, kein Schemaschritt) und werden nicht mehr gelesen; ein Feld `kritisch` in Formular-Anfragen und Katalogdateien wird ohne Prüfung übergangen, neue Punkte tragen es nicht. **Artikellänge** (seit 22.10.2026): Trägt eine Kategorie das Häkchen „Artikel haben eine Länge“ (es gilt auch für ihre Unterkategorien – etwa Seile und Meterware), bekommen Artikel ihrer Produkte das Feld „Länge (m)“ (eine Nachkommastelle, Komma oder Punkt, Anzeige „57,5 m“ im Steckbrief, in Listen, im Lebenslauf, in „Meine PSA“ und als CSV-Spalte „Länge (m)“; der Bestandsimport liest eine Spalte „Länge“ in Metern – „Länge (cm)“, andere Einheiten und „1.200“ nur als Hinweis und Bemerkung), und ein Prüfpunkt der Art „Länge“ (höchstens einer je Formular) ist in der Prüfung mit der Artikellänge vorbelegt – trägt der Prüfer einen anderen Wert ein, übernimmt das Festschreiben ihn in den Artikel (Journal „Länge geändert“, Protokoll „57,5 m → 55,0 m“). Hat jemand die Länge während der Prüfung geändert, fragt das Festschreiben nach (der Punkt zeigt die neue Länge).
- **Bestand**: Ordnerbaum, oben die Gliederungen, darunter frei verschachtelt Standorte, Fahrzeuge, Sets; hinter jedem Ordner sein Bestand und die Zahlen je Status (erklärt im „i“ an der Überschrift, jede Zahl mit title) – am Telefon nur „überfällig“ und ohne Marken, die unter den Namen rutschen (Ordnerart, „DEMO“ nur am obersten DEMO-Ordner; Gerätetest 01.11.2026). Hat ein Ordner ein Foto, steht es auf seiner Seite links neben Name und Knopfzeile – 96 px, am Telefon 64 px mit der Knopfzeile darunter; Klick oder Tippen zeigt es groß (Wunsch des Nutzers vom 02.11.2026). Jede Gliederung bekommt die Systemordner „Gesperrt“ und „Ausgesondert“ (nicht umbenennbar, verschiebbar, löschbar; nichts kommt von Hand hinein). Artikel bekommen eine plattformweit eineindeutige Inventarnummer (`M-000001`) und – ohne Herstellernummer – eine eindeutige Seriennummer (`STR-000001`); beide werden nie wieder vergeben. Lebensende (nur textil) = Herstellung (Monat genügt) + Lebensdauer; es lässt sich vorziehen – vor der ersten Prüfung direkt (nur nach vorn – zurück erst nach der ersten Prüfung per Antrag), danach per Antrag, der ein vorgezogenes Lebensende auch wieder nach hinten setzen darf, höchstens bis zur Rechnung (genau die Rechnung: nicht mehr von Hand gesetzt, Schritt 24). **Die Stammdaten stehen seit der ersten abgeschlossenen Prüfung fest** (ein Entwurf zählt nicht) – sie stehen im Prüfprotokoll: Produkt, Seriennummer (auch eine STR-Nummer), Herstellung, Kauf, Erstgebrauch, Lebensende (auch vorziehen und zurücksetzen) und das Prüfintervall am Artikel (Wunsch vom 24.10.2026; vorher nur Seriennummer und Herstellung). Direkt ändern Materialwart **und Prüfer** danach nur noch Bemerkung, Länge und die nächste Prüfung (vorziehen) – Prüfer bekommen dafür „Bearbeiten“ mit genau diesen drei Feldern (vor und nach der ersten Prüfung; „Nächste Prüfung“ erst nach ihr – vorher steht „Eingangsprüfung ausstehend“, auch für den Materialwart). **Das Produkt** ändert der Materialwart bis zur ersten Prüfung im Dialog „Bearbeiten“ (Feld „Produkt“ ganz oben mit „anderes Produkt“ und der Produktsuche; ein Hinweis sagt, was der Wechsel nachzieht – Lebensende aus der Lebensdauer des neuen Produkts oder weg, die Länge fällt weg, wenn die Kategorie keine vorsieht, ein kürzeres Prüfintervall rückt die nächste Prüfung vor, Rückrufe gelten nach dem neuen Produkt; Durchgang und Zuordnung bleiben), danach per Antrag; nie mit offener Prüfung oder über die DEMO-Grenze. Nach der ersten Prüfung zeigt der Dialog „Artikel … bearbeiten“ alle freigabepflichtigen Felder oben schreibgeschützt („Seit der ersten Prüfung fest – Teil des Prüfnachweises.“); der Server lehnt eine Änderung mit 409 ab, Datenbank-Trigger fangen den Rest. Ein leeres Feld nachtragen geht dann ebenfalls nur per Antrag (auch das Herstelldatum bei Metall); **entfernen lässt sich ein Herstelldatum nach der ersten Prüfung nie**, auch nicht per Antrag. **Änderungsanträge**: Materialwart oder Prüfer beantragen mit Begründung („Änderung beantragen“ in den Stammdaten oder im Dialog „Bearbeiten“) – alle Felder, die sich ändern sollen, in **einem** Antrag (mit Antrag-Nr.; vorbelegt mit den heutigen Werten, auch „anderes Produkt“ mit seinen Folgen); je Artikel ein offener Antrag. **Entscheiden die Materialwarte des Ordners** – wer eine eigene gültige Freigabe „verwalten“ an der Heimat des Artikels oder darüber hat, auch aus einer anderen Gliederung, auch für den eigenen Antrag; die Material-Verwaltung nur mit so einer Freigabe. Die Liste steht unter **Bestand → „Änderungsanträge“** (Knopf mit Blase: offene, die man entscheidet, ab 100 „99+“; Filter offen | erledigt | alle; die alte Adresse unter Katalog → Meldungen leitet dorthin weiter, „Produktmeldungen“ zeigt nur noch gemeldete fehlende Produkte); jeder sieht dort seine eigenen und die, die er entscheidet, die Übersicht nennt die Zahl, die Artikelseite führt Zuständige mit „Entscheiden“ hin. Bestätigt oder abgelehnt (nur mit Begründung) wird der ganze Antrag; beim Bestätigen prüft der Server den ganzen neuen Stand noch einmal (Herstellung nicht nach Kauf, Seriennummer je Produkt eindeutig …) und verlangt, dass der Artikel noch die alten Werte trägt – sonst nur ablehnen. Danach steht alles sofort am Artikel; Journal und Lebenslauf zeigen einen Eintrag mit alten und neuen Werten, Antragsteller, Bestätiger und Begründung (wer den Artikel nur liest, sieht dort nur Felder, Werte und Zeitpunkt); festgeschriebene Protokolle behalten die alten Werte, ein später festgeschriebenes Sammelprotokoll nennt „vormals … (Änderungsantrag Nr. …)“ bei Seriennummer und Produkt. Fiele der Artikel mit neuer Seriennummer oder anderem Produkt aus einem laufenden Rückruf (oder käme hinein), sagen es Antragsdialog, Karte und Rückfrage, das Journal vermerkt es. Ebenso, wenn ein laufender Rückruf ihn danach weiter trifft und für ihn durch eine Prüfung schon erledigt war: Nach dem Antrag zählt nur eine neue Prüfung, der Rückruf gilt dann wieder als offen – auch bei einem reinen Tippfehler in der Seriennummer (Liste nach dem Merge). Einen offenen Antrag **zieht der Antragsteller selbst zurück** (Rückfrage; Stand „zurückgezogen“, keine Mail). Mails an die zuständigen Materialwarte (ohne den Antragsteller; gibt es gar keinen, an die Material-Verwaltung mit dem Hinweis auf die Freigabe) und an den Antragsteller (nur, solange er den Artikel liest); verliert ein Ordner mit offenem Antrag später seinen letzten Materialwart – Freigabe entzogen, abgelaufen, Konto deaktiviert oder gelöscht, Ordner verschoben –, bekommt die Material-Verwaltung einmal je Wegfall eine Mail mit Ordner und Zahl der Anträge (Schema 29); bei DEMO, auf dev und ohne Mailserver ins Log. Die Trigger lassen nur genau die Änderungen eines bestätigten Antrags zu, und die nur einmal; weitere (Schritt 16) verhindern die Umwege, einen geprüften Artikel zu ersetzen, umzunummerieren, zu löschen oder die Materialart seines Produkts zu ändern. Anträge sind nach der Entscheidung oder dem Zurückziehen unveränderlich und unlöschbar (Trigger, Schritte 17 und 23). Mehrfachauswahl zum Verschieben, Journal mit Vorher/Nachher je Feld an Produkt, Artikel und Ordner. Links steht der Ordnerbaum als Navigation (eigene Ebene markiert; Klappzeichen wie im Seitenbaum der Strömipedia – ein gezeichneter Winkel, nach rechts zu, nach unten offen –, jede Unterebene eingerückt mit Führungslinie; im Katalog ebenso der Kategorienbaum); unter 1024 px Breite klappt er als Schublade hinter „☰ Ordner“ auf (ihr Kopf mit „✕“ bleibt beim Rollen oben stehen), von 1024 bis 1199 px steht er als schmalere Leiste daneben. **Artikelliste des Ordners** (Wünsche vom 25.10.2026; seit 05.11.2026 der ganze Zweig): Ein Ordner zeigt seine eigenen Artikel und die aller Unterordner, die das Konto sieht – zuerst die direkt darin, dann je Unterordner eine Überschrift mit dem Pfad relativ zum Ordner („Zentrallager › Regal 3“, Link auf den Unterordner, mit Zahl) in der Reihenfolge des Baums; leere Unterordner erscheinen nicht, „Gesperrt“ steht als eigene Gruppe da, „Ausgesondert“ nur mit dem Statusfilter „ausgesondert“ (auf seiner eigenen Seite immer). Je Gruppe stehen die ersten 50, darunter „Weitere n anzeigen“ (lädt die nächsten nach); die Spaltenköpfe sortieren innerhalb jeder Gruppe; die Mehrfachauswahl geht über alle Gruppen („alle auswählen“ und das Häkchen einer Überschrift nehmen die angezeigten Artikel). Ein Ordner ohne Unterordner sieht aus wie bisher, der Abschnitt „Unterordner“ bleibt. Vorn die Spalte „Kategorie“ (sortierbar; bis 899 px Inhaltsbreite enge Tabelle, zwischen 900 und 979 px klein über dem Hersteller, als Karte klein über Hersteller und Produkt – so rollt die Liste nie seitwärts), die Filter stehen im **Filtermenü unter dem Baum** – Status (dazu „Aussonderung empfohlen“, wo es so einen Artikel gibt – meist in „Gesperrt“), Kategorie (bei gleichem Namen mit Pfad) und „Zugeordnet an“ (nur mit Grundrecht; zur Wahl stehen alle Personen mit Zuordnungen im Zweig; ohne Zahlen), verknüpft mit „und“ und gültig für den ganzen Zweig; Status und Kategorie zeigen je Eintrag die Zahl im ganzen Zweig mit den übrigen Filtern (Status dazu „ausgesondert“, wo es solche gibt); über der Liste „Gefiltert: … – Filter zurücksetzen“. Als Schublade öffnet der Knopf „Filter (n)“ über der Liste sie gleich bei den Filtern, nach einer Wahl schließt sie. Die Artikelseite zeigt die Norm des Produkts in einer eigenen Zeile der Stammdaten.
- **Prüfintervall**: Herstellerseite (Produkt, sonst Kategorie) und Organisation (Artikel, sonst nächster Ordner bis zur Gliederung) – es gilt das kürzere. Ein Ordner kann verschärfen, nicht verlängern. Wird das wirksame Intervall kürzer, ziehen Fälligkeiten hinter „letzte Prüfung + Intervall“ (ohne Prüfung „heute + Intervall“) auf diese Grenze vor – liegt sie schon zurück, ist der Artikel überfällig (mit Journaleintrag).
- **Status** wird nie gespeichert, sondern abgeleitet: neu (noch keine Prüfung – die Eingangsprüfung steht aus), einsatzbereit, bald fällig (Einstellung `MATERIAL_BALD_FAELLIG_TAGE`, Vorgabe 30), überfällig, gesperrt, Lebensdauer erreicht, ausgesondert. Die **Übersicht** zeigt die Fälligkeiten je Ordner (Gliederungen mit ihren Unterordnern eingerückt: Bestand, überfällig, neu, bald fällig, gesperrt, Lebensdauer erreicht, nächste Fälligkeit; jede Zahl öffnet die gefilterte Liste und springt zu ihr, der gewählte Filter ist als gedrückt markiert), laufende Rückrufe und Prüfdurchgänge und was als Nächstes zu prüfen ist. Gesperrte und Ausgesonderte zählen bei ihrer Gliederung; „fällig“ umfasst auch „Lebensdauer erreicht“.
- **Prüfung** (nur Prüfer mit Urkundennummer und Prüffreigabe für den Ordner): jederzeit aus der Artikelansicht startbar, die erste ist immer die Eingangsprüfung. Formular = die aktive Version des dem Produkt zugewiesenen Formulars, sonst die des Standards seiner Kategorie (oder der nächsten Oberkategorie mit einem; Formular-Pool, Schema 38) – eine Stelle (`katalog.formular_fuer_produkt`) für Prüfung, Produkt- und Artikelseite; das Protokoll nennt „„Titel“, Version n (Prüfformular der Kategorie „Heimat“)“; jeder Befund ist mit „in Ordnung“ vorbelegt, Ja/Nein-Punkte mit ihrem Sollwert. Fürs Telefon gebaut: große Umschalter je Prüfpunkt (mit der Tastatur je Punkt ein Tab-Stopp, Pfeiltasten wählen; Sprunglink „Zum Abschluss“), Kamera-Knopf, feste Leiste unten mit Ergebnis und „Festschreiben“ – höchstens rund ein Fünftel der Höhe, beim Scrollen eingeklappt auf eine Zeile (was noch fehlt bzw. das gewählte Ergebnis und „Zum Abschluss“), voll am Ende des Formulars (Gerätetest 01.11.2026); ein Tipp auf das ausgegraute „Festschreiben“ hebt den Grund hervor und führt zum fehlenden Schritt (Ergebnis, im Dialog der erste nicht abgehakte gemeldete Mangel); Grund bzw. „Nächste Prüfung“ fragt der Dialog „Prüfung festschreiben“ (seit UI/UX vor dem Merge); jede Eingabe wird sofort gespeichert. Jeder Mangel braucht ein Foto und eine Bemerkung; bei einem Mangel wählt der Prüfer das Ergebnis selbst (seit 03.11.2026 ohne Sperre durch „kritische“ Punkte), nur ein erreichtes Lebensende schließt „einsatzbereit“ aus; die nächste Fälligkeit (Prüftag + Intervall) lässt sich nur vorziehen. Anhänge (Prüfkarte, Bericht) als PDF oder Foto; mehrere Fotos eines Scans werden ein PDF. Der offene Entwurf reserviert den Artikel: andere sehen „in Prüfung bei …“, eine liegen gebliebene Reservierung hebt der Materialwart auf. Abschließen heißt **Festschreiben**: Es braucht die im Profil hinterlegte Unterschrift und erzeugt das Prüfprotokoll als PDF (siehe „Nachweis“); danach ist die Prüfung unveränderlich. Unterschriftsfelder eines Formulars füllt man auf dem Signatur-Pad.
- **Sperren und Aussondern**: „instandsetzen“ sperrt und verschiebt nach „Gesperrt“ der Gliederung (Herkunft gemerkt); zurück bringt nur eine Freiprüfung mit „einsatzbereit“. Ohne Prüfung sperrt ein Prüfer (seit 01.11.2026) nur noch auf zwei Wegen mit festem Grund: **„Verlust melden“** im Menü „Mehr“ der Artikelseite (Grund „Verlust“, „Was ist passiert?“ freiwillig; der Artikel ist gesperrt und zählt als verloren – taucht er wieder auf, bringt ihn nur eine Freiprüfung zurück) und **„Sperren (Rückruf)“** im Rückruf-Banner (Dialog „M-… wegen Rückruf sperren“, Knopf „Wegen Rückruf sperren“). Beschädigung und Sturzbelastung meldet man über **„Mangel melden“** (Beschreibung, Fotos, Mail an die Verwalter); der Server lehnt die früheren Sperrgründe „sturz“ und „beschaedigung“ mit Klartext ab, ältere Sperren mit diesen Gründen bleiben in Anzeige, Lebenslauf, Journal und Jahresbericht unverändert lesbar. **Prüfer sondern nicht aus** (Wunsch vom 25.10.2026, Schema 28): Ihr Ergebnis „aussondern empfohlen“ sperrt wie „instandsetzen“; die Empfehlung steht im Prüfprotokoll, am Artikel (Hinweis und Marke „Aussonderung empfohlen“, auch in der Liste „Gesperrt“) und im Dialog „Aussondern“; die Übersicht nennt Materialwarten (und der Material-Verwaltung) die Zahl der Artikel mit Empfehlung, die sie aussondern dürfen, mit Link auf „Gesperrt“ mit gesetztem Filter „Aussonderung empfohlen“. **Aussondern darf nur der Materialwart** (Recht „verwalten“) – und nur, wenn die letzte Prüfung des gesperrten Artikels „instandsetzen“ oder „aussondern empfohlen“ ergab; nach einer Sperre wegen Rückruf (früher auch Sturz oder Beschädigung) oder einer Mangelmeldung also erst nach einer Prüfung, nach „Verlust“ sofort (Grund „Verlust“ vorbelegt). Sonst ist „Aussondern“ ausgegraut und sagt, was fehlt. Jede Aussonderung ist ein eigener Vorgang mit Grund und Datum und eigenem, festgeschriebenem Aussonderungsprotokoll (mit seiner Unterschrift); der Artikel wandert nach „Ausgesondert“ und zählt nirgends mehr als Bestand – er gehört aber weiter zu seinem Herkunftsordner, dessen Verwalter ihn und sein Aussonderungsprotokoll weiter sehen. Prüfungen vor dem 25.10.2026 mit dem Ergebnis „aussondern“ (das damals zugleich aussonderte) heißen jetzt „aussondern (ausgesondert)“.
- **Prüfdurchgang** (Materialwart oder Prüfer eröffnet ihn für einen Ordner): alle Artikel darin und darunter auf einer gemeinsamen Liste (offen, in Prüfung bei …, erledigt, mit Grund ausgenommen) – beim Öffnen mit dem Filter „offen“, solange es Offenes gibt; darüber ein Suchfeld nach Nummer oder Name (Inventar-, Serien-, Herstellernummer, Hersteller, Modell, Kategorie; blendet nur aus, die Liste bleibt vollständig) und am Telefon mit Chrome unter Android „QR-Code scannen“ (ein Foto des Etiketts; steht der Artikel im Durchgang, zeigt die Liste ihn – ohne diese Möglichkeit öffnet die Kamera-App den Artikel über seinen QR-Code direkt); Kopf, Filter und Grund zählen gleich („5 erledigt + 2 ausgenommen = 7 von 16 fertig · 8 offen · 1 in Prüfung“), Ausnehmen und Einbeziehen bestätigt eine Meldung; mehrere Prüfer zugleich, jeder mit eigener Urkundennummer. Abschließen erst, wenn alles geprüft oder ausgenommen ist – dann entsteht das Sammelprotokoll mit allen Artikeln, Ausnahmen, Prüfern samt Urkundennummer und Unterschrift und den Prüfsummen der Einzelprotokolle; „Abbrechen“ beendet ihn vorzeitig (offene Prüfungen laufen einzeln weiter, Ungeprüftes steht darin als „nicht geprüft“, auch im Sammelprotokoll). Seit Schema 27 bekommt beim regulären Abschluss jedes Set darunter dazu sein Set-Protokoll (siehe unten „Set-Protokolle im Prüfdurchgang“). Auf „Prüfungen“ stehen nur die laufenden Durchgänge; das Menü **„Prüfdurchgänge“** bietet „Prüfdurchgang anlegen“ (wer irgendwo verwaltet oder prüft) und **„Abgeschlossene Prüfdurchgänge“** (`/materialablage/durchgaenge`): beendete und abgebrochene je Jahr des Abschlusses (neuestes Jahr offen, ältere zum Aufklappen, je 50 mit „Weitere anzeigen“), filterbar nach Ordner (mit Unterordnern) und Wörtern im Titel, je Zeile Titel, Ordner, eröffnet, abgeschlossen, Stand und Sammelprotokoll (PDF); am Telefon als Karten. Zurück von einem Durchgang steht die Seite wieder so da wie vorher.
- **Nachweis**: Prüfer (und wer aussondert) hinterlegen ihre Unterschrift einmal im Profil (Signatur-Pad). Beim Festschreiben entsteht ein PDF/A-Protokoll (WeasyPrint) – Prüf-, Aussonderungs-, Sammel- oder Set-Protokoll mit Protokoll-ID (`P-`, `A-`, `S-`, `T-2026-000123`); Prüf- und Aussonderungsprotokolle mit Unterschrift, Anmeldung (E-Mail-Adresse beim Festschreiben) und Zeitpunkt; Sammel- und Set-Protokolle mit den Unterschriften der beteiligten Prüfer – wer den Durchgang abschließt, steht mit Name und Zeitpunkt darin und unterschreibt nicht. Das Prüfprotokoll folgt dem Muster der EN-365-Karte mit Befunden, Mangelfotos, Herstellerdokumenten, Anhängen samt Prüfsumme (auf Wunsch hinten angefügt) und QR-Code zur Artikelseite (für die zugeordnete Person „Meine PSA“; neue Protokolle beschriften ihn „Artikel online“, bis 26.10.2026 „Lebenslauf online“). **Seitenaufbau** (seit 27.10.2026, nur neue PDFs): Im Prüfprotokoll beginnt der Abschluss – Ergebnis, Bemerkung, Herstellerdokumente (Art und Version in einer Spalte), Anhänge und Unterschrift – immer auf einer neuen Seite, die Fotos zu den Prüfpunkten folgen als Anlage danach. Das Aussonderungsprotokoll hält Aussonderung, letzte Prüfung und Unterschrift zusammen. In allen Listen bleiben Überschrift, Tabellenkopf und die ersten vier Zeilen zusammen, die letzten drei gehen gemeinsam auf eine neue Seite, kurze Listen (bis etwa eine halbe Seite) werden nicht geteilt. Im Fuß jeder Seite steht „SHA-256 (erste N Bytes): …“: nachrechenbar mit `head -c N datei.pdf | sha256sum` oder auf der öffentlichen Seite „Echtheit prüfen“ `/materialablage/pruefen` (Knopf auf „Prüfungen“, ohne Anmeldung; zeigt nur „unverändert“ oder „verändert“ und die Protokoll-ID – bei einem Lebenslauf dessen Kennung und Stand). Die Dateien liegen schreibgeschützt unter `/data/pdf/<jahr>/`; Datenbank-Trigger weisen jede Änderung an festgeschriebenen Prüfungen und abgeschlossenen Durchgängen ab. Eine Korrektur ist eine **Berichtigung**: ein neuer Entwurf mit allen Befunden, Fotos und Anhängen, demselben Prüftag und Verweis – das Original bleibt mit seinem Protokoll erhalten.
- **Suche** nach Serien-, Inventar- und Herstellernummer mit Teiltreffern (Feld „Inventar-, Serien-, Herstellernr.“ – derselbe Wortlaut in der Suchzeile und in der Modulnavigation, Gerätetest 01.11.2026 –, nicht im Katalog – dort sucht die Suchzeile Produkte, Wunsch vom 26.10.2026; am Telefon und Tablet hochkant – solange die Ordnerleiste eine Schublade ist – steht es auf allen übrigen Seiten wie im Katalog offen als Artikelsuche in einer Suchzeile oben im Inhalt, die beim Scrollen unter der Kopfleiste stehen bleibt, links daneben „☰“ für die Ordner (auf „Bestand“, wo der Baum selbst der Inhalt ist, nur das Feld); keine Lupe mehr – Wünsche vom 28.10.2026; nur in der Prüfung selbst bleibt die Suche am Telefon ausgeblendet); ein eindeutiger Treffer öffnet den Artikel direkt. Jeder Artikel hat eine Adresse `https://strömis.de/m/<token>` für QR-Code, NFC- oder RFID-Tag – sie führt über die Anmeldung zum Artikel (liegt er außerhalb des eigenen Bereichs, nur zu einem Hinweis, siehe „Globale Suche“); ist er ausgesondert, gesperrt oder am Lebensende, steht das sofort groß auf der Seite. Etiketten druckt das Modul nicht: Die Adresse am Artikel kopieren und auf einen Tag schreiben oder mit einem beliebigen Etikettenprogramm als QR-Code drucken. Die Adresse ist dauerhaft – `BASE_URL` danach nicht mehr ändern, und Etiketten von dev.strömis.de nie ans echte Material.
- **Globale Suche**: Unter den eigenen Treffern bieten Trefferseite und Suchvorschläge „Außerhalb deines Bereichs nach der Seriennummer „…“ suchen“ an – zu jeder Anfrage, die dafür taugt, auch neben eigenen Treffern und wenn ein eigener Artikel genau diese Nummer hat; auch Mitgliedern und Prüfern ohne Freigabe, nicht aber der Material-Verwaltung, die ohnehin alles sieht. Nach einer Bestätigung sucht sie nur unter den Artikeln, die man nicht sieht, und zeigt bis zu zehn Steckbriefe direkt unter der eigenen Liste – ab der Trennlinie „Außerhalb deines Bereichs“ (andere Gliederungen; wer nur einen Teil einer Gliederung sieht, auch deren übrige Ordner), jeder gestrichelt umrandet und mit seiner Gliederung als Marke ganz oben: Produkt mit Bild, Inventar- und Seriennummer, Herstellung, Lebensende, ein Wort zum Sperrzustand („gesperrt“, „verloren gemeldet“ oder „ausgesondert“ – ohne Grund und Datum) und „Gehört zu <Gliederung> · <Ordner>“ – keine Prüfungen, Protokolle, Fotos, Bemerkungen oder Personen. Gesucht wird nur nach der ganzen Herstellerseriennummer (ab 4 Zeichen), nie nach den fortlaufenden Inventar- und STR-Nummern. Ein eindeutiger eigener Treffer öffnet wie bisher gleich den Artikel statt der Trefferseite – dann steht das Angebot dort unter dem Kopf des Artikels (und in den Suchvorschlägen). Ein QR-Scan an einem fremden Artikel zeigt „Dieser Artikel gehört nicht zu deinem Bereich.“ und auf Wunsch denselben Steckbrief – samt Sperrwort, damit ein Finder sieht, ob ein fremdes Seil gesperrt, verloren gemeldet oder ausgesondert ist. Gibt es die Seriennummer beim Anlegen für dasselbe Produkt schon in einem fremden Bereich, sagt die Meldung nur das – ohne Inventarnummer und Gliederung – und verweist auf die globale Suche. Alle drei stehen jedes Mal zwölf Monate mit Namen im Protokoll (Leitstelle → Nutzer, „Globale Suchen (Materialablage)“ – nur die Plattform-Verwaltung); eine Grenze, wie oft man suchen darf, gibt es nicht – die Kontrolle ist das Protokoll.
- **Export** (mit lesen oder verwalten am Ordner, beim Lebenslauf am Artikel): je Ordner im Untermenü „Export / Import“ „Artikelliste exportieren (CSV)“ (für Excel: `;`, UTF-8 mit BOM, Status, Fälligkeiten, Lebensende, zugeordnete Person, hinter „Modell“ die Spalte „Bemerkung (Produkt)“ und weiter hinten die „Bemerkung“ des Artikels – samt der von hier gesperrten und ausgesonderten Artikel) und „Protokolle exportieren (ZIP)“ (alle festgeschriebenen Protokolle dieser Artikel, die Sammelprotokolle der Durchgänge und die Set-Protokolle der Sets im Zweig, mit `Verzeichnis.csv` samt Prüfsummen; eine fehlende oder veränderte Datei steht dort mit ihrem Zustand, statt den Export abzubrechen), je Artikel „Lebenslauf (PDF)“: Stammdaten, Zustand, alle Prüfungen chronologisch mit Protokoll-ID und Prüfsumme, Durchgänge, Rückrufe und Ereignisse – auf Abruf gesetzt (ein Festschreiben des Lebenslaufs gibt es nicht, auch nicht bei der Aussonderung). Seit Schema 31 bekommt jeder Abruf eine **Kennung** `L-<Jahr>-<Nr>` (fortlaufend je Jahr; Lücken sind abgebrochene Abrufe) im Kopf und Fuß jeder Seite und unten den **Prüfsummen-Stempel** wie ein Protokoll („Lebenslauf L-2026-000123 · SHA-256 (erste N Bytes): …“). Gespeichert werden nur Kennung, Inventarnummer, Stand und die Prüfsummen (Tabelle `mat_lebenslauf`, unveränderlich) – **nicht, wer abgerufen hat**, nicht der Inhalt, keine Datei. So erkennt die Prüfseite einen ausgegebenen Lebenslauf Byte für Byte wieder („Lebenslauf“, Kennung, Stand; angemeldet mit Leserecht dazu der Link zum Artikel). Nach dem Zurückspielen einer älteren Sicherung kennt sie die seither ausgegebenen Lebensläufe nicht mehr; die **Kennung eines ausgegebenen Lebenslaufs wird nicht noch einmal vergeben** – die zuletzt vergebene steht zusätzlich als leere Datei unter `data/pdf/lebenslauf/` (Name = Kennung, eine je Jahr), und das Zurückspielen ergänzt `pdf/` nur (seit dem 27.10.2026). Eine Anfrage mit HEAD (etwa Vorabladen) bekommt nach der Rechteprüfung nur die Kopfzeilen – ohne Kennung und ohne Eintrag. Je Konto höchstens 60 Lebensläufe in einer Viertelstunde (wie die Bremse der Prüfseite); darüber antwortet der Abruf mit „Bitte in einer Viertelstunde noch einmal“ (429). Jeder Abruf setzt neu: Der Name trägt Datum, Uhrzeit und Kennung (`Lebenslauf_<Inventarnummer>_<JJJJ-MM-TT>_<HHMM>_<Kennung>.pdf`, deutsche Zeit wie „Stand“), und der Knopf hängt beim Antippen einen Zeitstempel an die Adresse (`?stand=…`, der Server übergeht ihn) – so öffnet Chrome auf Android nicht die schon heruntergeladene Datei mit altem Stand. Ebenso Artikelliste, Protokoll-ZIP, Jahresbericht (PDF und Prüfungen-CSV), Nacharbeit-CSV und Katalogdatei; festgeschriebene Protokolle und „Alle Protokolle (ZIP)“ eines Durchgangs behalten ihren Namen.
- **Personenzuordnung**: PSA, die eine Person dauerhaft nutzt, ordnet ein Verwalter ihr zu – in der Artikelansicht („Zugeordnet an“ → „Zuordnen“) oder für mehrere Artikel aus der Ordnerliste; wählbar ist jedes aktive Konto mit Namen, auch ohne Zugang zum Modul. Die Zuordnung sehen nur Konten mit lesen oder verwalten (Spalte „Person“, Filter „Zugeordnet an …“, CSV-Spalte „Zugeordnet an“) – nicht die Prüfsicht, nicht die globale Suche und nie ein Protokoll oder der Lebenslauf. Im Journal steht die Person nur als pseudonymer Verweis. Aussondern löst die Zuordnung; ein deaktiviertes Konto steht mit „(deaktiviert)“ da.
- **Jahresbericht je Zweig** (Phase 4 · Lieferung 1): Im Ordnerkopf unter „Export“ → „Jahresbericht exportieren“ – für einen Ordnerzweig (in der Regel die Gliederung) und ein Kalenderjahr: Bestand zum Stichtag heute (Status, je Kategorie, je Unterordner), Bewegungen, Prüfungen (je Prüfart, je Ergebnis, mit Mangel – die Zahl „mit kritischem Mangel“ und die CSV-Spalte „kritischer Mangel“ sind seit 03.11.2026 entfallen) mit Prüfabdeckung und Liste der nicht geprüften Artikel, Prüfdurchgänge mit Ausnahmen, Sperren und Freiprüfungen, Aussonderungen, Mangelmeldungen, Rückrufe, Ausblick über zwölf Monate – als Seite (mit Sprungmarken zu den Blöcken), PDF/A (nicht festgeschrieben, kein Prüfnachweis; Listen gekürzt – 500 Zeilen je Liste, 1 500 im ganzen PDF, 50 Artikel je Rückruf) und CSV-Prüfungsliste. Namen von Prüfern stehen nur mit dem Haken „Prüfer nennen“ darin (Dateiname „-mit-pruefern“); DEMO-Artikel zählen mit und sind gekennzeichnet. Für Führungskraft und Materialwart (lesen oder verwalten am Zweig) und die Material-Verwaltung.
- **Mailversand im Blick** (Phase 4 · Lieferung 1): Jede Modul-Mail (Erinnerung, Mangel, Änderungsantrag, Produktmeldung, Rückruf), die der Mailserver nicht annimmt, steht im Kasten „Mailversand“ auf der Übersicht – ohne Adressen und ohne Zugangsdaten des Mailservers, mit Empfänger, Rolle, Bezug (Link ins Modul), Betreff und der gereinigten Serverantwort; die letzten 20, „Weitere anzeigen“ für alle offenen (bis 200), „Erledigt“ je Zeile, „Alle erledigt“ mit Rückfrage im Untermenü. Die Material-Verwaltung sieht alles, Materialwarte die Zeilen der Ordner, die sie verwalten (Mangel, Antrag, Produktmeldung: die Heimat des Artikels – auch, wer nur einen Unterordner verwaltet; Erinnerung und Rückruf: je Gliederung). Erinnerungen holt der nächste Lauf nach; sonst gibt es keinen erneuten Versand (Mailtexte werden nicht gespeichert). Ohne Mailserver, unter der Umgebungssperre (dev) und bei DEMO geht nichts hinaus und nichts ins Protokoll. Zeilen bleiben 13 Monate, erledigte 3; mit dem Konto werden sie gelöscht.
- **Meine PSA und Mangelmeldung** (Phase 3 · Lieferung 1): Wem ein Verwalter Ausrüstung zugeordnet hat, sieht sie unter **„Meine PSA“** (`/materialablage/meine-psa`) – jedes aktive Konto mit Namen, **auch ohne Stufe in der Materialablage** (dann ohne Modulnavigation und Ordnerleiste). Je Artikel eine Karte: Status (ein verloren gemeldeter Artikel mit der Marke „verloren“ wie auf der Artikelseite, seit dem 02.11.2026), nächste Prüfung, Lebensende, letzte Prüfung, Gliederung (nur der Name), Bemerkung, Sperrgrund, Produktbild (nur Web- und Vorschaufassung), Serien- und Inventarnummer, Gebrauchsanleitung, Pflegehinweis, Konformitätserklärung und Datenblatt des Herstellers, Titel laufender Rückrufe und die eigenen Meldungen – keine Ordner, keine Protokolle, keine Prüfhistorie, kein Journal. Der Eintrag „Meine PSA“ steht in der Kopfleiste, sobald etwas zugeordnet ist und das Konto nirgends im Bestand lesen darf (ohne Stufe oder Mitglied ohne Freigabe); wer liest, verwaltet oder prüft, findet seine PSA als Kasten unten auf der Übersicht. Der QR-Link `/m/<token>` der eigenen PSA führt ohne Leserecht auf ihre Karte; fremde Artikel antworten ohne Stufe weiter mit „nicht freigeschaltet“. **„Mangel melden“** (grauer Knopf an der Karte und an der Artikelansicht) dürfen die zugeordnete Person und jeder mit lesen, verwalten oder prüfen am Artikel: Beschreibung (Pflicht, bis 2000 Zeichen) und bis zu 3 Fotos (am Telefon Kamera oder Galerie, nacheinander gesammelt; das Original mit Aufnahmeort wird sofort gelöscht, es bleiben Web- und Vorschaufassung ohne EXIF). **Jede Meldung sperrt sofort** (Systemordner „Gesperrt“, Grund „Mangel gemeldet am …“, Journal „Mangel gemeldet“ mit Namen und – im Verlauf am Artikel – der Mangelbeschreibung; beides sehen dort nur Prüfer und Materialwarte und der Melder bei seiner eigenen Meldung, sonst steht „(Person)“ ohne Text) – auch bei offenem Prüfentwurf; alle Texte sagen: beiseitelegen und dem Materialwart geben (wer den Artikel selbst verwaltet, liest nur „beiseitelegen“; am schon gesperrten Artikel heißt der Knopf „Melden“). Die Quittung steht danach oben auf der Seite, ohne Toast daneben. Zurück nur über eine **Freiprüfung**: Mit „einsatzbereit“ hakt der Prüfer im Festschreib-Dialog jede offene Meldung einzeln ab („Gemeldeten Mangel geprüft“), dann ist sie erledigt; „instandsetzen“ lässt sie offen, eine Berichtigung gibt nie frei (und wird die Freiprüfung später zu „instandsetzen“ berichtigt, ist die Meldung wieder offen), und aussondern kann der Materialwart nach einer reinen Mangelsperre erst, wenn ein Prüfer den Artikel seither geprüft hat (der Knopf ist bis dahin ausgegraut). Sichtbar als rotes Banner am Artikel (eine Beschreibung ab 600 Zeichen dort eingeklappt mit „Weiterlesen“; die Fotos stehen seit dem 04.11.2026 als Spalte links neben dem Text, ebenso im Banner der Prüfung und in Meine PSA), Marke „Mangel“ in Listen und Suche, Kasten „Gemeldete Mängel“ oben auf der Übersicht (bis ein Prüfer geprüft hat) und Hinweis in der Prüfung (Prüfart „außerplanmäßig“ vorgeschlagen). **Text, Fotos und den Namen des Melders** sehen nur Prüfer (wirksame Prüffreigabe, auch der externe Prüfer) und Materialwarte des Artikels (verwalten; Material- und Plattform-Verwaltung ebenso) – und der Melder seine eigene Meldung; wer den Artikel nur liest, sieht „Mangel gemeldet am …“ ohne Text, Fotos und Namen (die Foto-Adressen antworten ihm 404), die zugeordnete Person bei fremder Meldung nur den Zeitpunkt (Entscheidung vom 21.10.2026). Dieselbe Regel gilt im **Lebenslauf (PDF)**: Bei „Mangel gemeldet“ stehen für Prüfer, Materialwart und den Melder bei seiner eigenen Meldung der Name und die vollständige Mangelbeschreibung (Zeilenumbrüche bleiben), für alle anderen „(Person)“ ohne Text; Fotos nie (Wunsch vom 26.10.2026). **Mails sofort**: an die Verwalter der Heimat (ohne sie Material-, ohne diese Plattform-Verwaltung) und an jeden Prüfer mit Prüffreigabe dort oder darüber; meldet jemand anderes die PSA einer Person, bekommt sie eine kurze Sperrmitteilung ohne Melder und Text (nicht abbestellbar – sie betrifft ihre Sicherheit). Nie an den Melder, nie an DEMO-Adressen; bei DEMO-Artikeln, auf dev (Umgebungssperre) und ohne Mailserver stehen die Mails nur im Log, und der Dialog sagt „Es ging keine Mail hinaus“. Eine offene Meldung je Konto und Artikel (dann ist „Mangel melden“ ausgegraut), keine Tagesgrenze, kein Zurückziehen. Im **Profil** lassen sich die Erinnerungen „Deine PSA“ abbestellen.
- **Rückrufe**: Die Material-Verwaltung legt am Produkt einen Rückruf an (Titel, was zu tun ist, Link des Herstellers, optional die betroffenen Seriennummern). Er steht am Produkt, als rotes Banner an jedem betroffenen Artikel, in der Prüfung, als Marke in den Listen und auf der Übersicht; eine Mail geht je betroffenem Artikel an die Verwalter seines Bereichs (gibt es keinen, an die Material-Verwaltung – an die Plattform-Verwaltung nur, wenn es keine gibt) und an die Prüfer, die ihn geprüft haben und dort noch prüfen dürfen – jeder bekommt eine Mail mit genau den Artikeln, die er sehen darf. Liste, Zahlen und Produktseite zeigen jedem nur seinen Bereich. Gesperrt wird nicht automatisch: Prüfer sperren mit dem Grund „Rückruf“, und eine Prüfung nach dem Rückruf erledigt ihn für den Artikel ebenso. Kam der Artikel erst durch einen bestätigten Änderungsantrag (andere Seriennummer oder anderes Produkt) in den Rückruf, zählt nur eine Prüfung nach diesem Antrag – eine frühere kannte den Rückruf für ihn nicht (Nachbesserung vor dem Merge, R1). Maßgeblich ist, wann der Prüfentwurf begann, nicht wann er abgeschlossen wurde: Ein Entwurf, der schon offen war, als der Rückruf angelegt oder der Antrag bestätigt wurde, erledigt ihn nicht – der Artikel braucht danach eine neue Prüfung (Runde 2, N-A1). Ohne Mailserver oder unter der Sperre der Entwicklung sagen Rückmeldung und Produktseite, dass keine Mail hinausging („kein Mailserver eingerichtet“ bzw. „in dieser Umgebung sind Mails gesperrt“) – maßgeblich ist der Stand beim Anlegen, nicht der Mailserver von heute (seit Schema 32; ältere Rückrufe tragen keinen Vermerk); gezählt wird der Versuch weiter als gescheitert. Beendet wird er mit Vermerk. Ändern oder löschen lässt sich ein Rückruf nicht (Entscheidung E4 A vom 26.10.2026): Er hat Mails ausgelöst und steht im Lebenslauf; ein Fehler wird mit „Beenden“ (etwa „irrtümlich angelegt – ersetzt durch …“) und einem neuen Rückruf berichtigt. Eine eigene Liste gibt es nicht – die laufenden stehen auf der Übersicht, alle eines Produkts auf der Produktseite.
- **Erinnerungsmails** (Schalter unter „Leitstelle → Einstellungen“, Vorgabe aus – siehe „Erinnerungsmails (Materialablage)“): Jeden Morgen ab 6 Uhr bekommen die Verwalter eines Ordners eine Sammelmail, gruppiert nach Ordnerpfad – Prüfung in 30 und in 7 Tagen fällig, überfällig (einmal je Fälligkeit), Lebensende in 90 Tagen (nur textiles Material) und befristete Freigaben, die in 30 Tagen ablaufen. Jede Stufe kommt je Empfänger nur einmal. Verwaltet an einem Ordner niemand, geht die Mail an die Material-Verwaltung, ohne sie an die Plattform-Verwaltung („kein Materialwart eingetragen“). Wessen befristete Freigabe abläuft, bekommt sie zusätzlich selbst – im Abschnitt „Deine Freigaben“, mit den Namen derer, die verlängern können (wie unter „Meine Freigaben“). Zugeordnete Personen bekommen ihre eigene PSA im Abschnitt „Deine PSA“ (30 Tage vor der Prüfung, überfällig, Lebensende in 90 Tagen; abbestellbar im Profil, siehe „Meine PSA und Mangelmeldung“). Nie für DEMO-Bestand (den der Probelauf auf Wunsch zur Ansicht einbezieht). Im Dialog „Ordner bearbeiten“ lassen sich Erinnerungen je Ordner abschalten (gilt für alle Unterordner). Die Material-Verwaltung sieht unten auf der Übersicht den Stand des letzten Laufs und einen Probelauf (wer bekäme welche Mail – es geht nichts hinaus).
- **Bestandsimport** (wer einen Ordner verwaltet; im Ordnerkopf „Export / Import“ → „Bestandsliste importieren“): Eine vorhandene Bestandsliste kommt als Excel-Arbeitsmappe (.xlsx) oder CSV (UTF-8 oder Windows-1252 wie aus deutschem Excel, Trennzeichen `;`, `,` oder Tab) in den Ordner. **Ablauf**: Datei wählen oder hineinziehen – der **Probelauf** läuft sofort und schreibt nichts; er ordnet die Spalten selbst zu (Hersteller, Modell bzw. Typ bzw. Bezeichnung, Artikelnummer, Seriennummer – auch „Ser.-Nr.“, „Serien-Nummer“, „Fabr.-Nr.“ –, bisherige Inventarnummer, Ordner als Pfad unter dem Zielordner, Herstelldatum, Kaufdatum, Erstgebrauch, zuletzt geprüft, nächste Prüfung, Prüfintervall, Lebensende, Anzahl, Bemerkung – Größe, Farbe, Standort und weitere Spalten als „Titel: Wert“ in die Bemerkung); die Zuordnung lässt sich je Spalte ändern, Personenspalten (Ausgegeben an, Telefon …) lassen sich keinem Feld zuordnen – auch nicht in der Nacharbeits-CSV. Ist keine Spalte als Seriennummer zugeordnet, warnt der Probelauf zuerst (sonst bekäme jede Zeile still eine STR-Nummer) und nennt die nicht zugeordneten Spalten; übernommen wird dann nur mit einem Häkchen „Diese Liste hat keine Seriennummern …“ direkt über dem Knopf – es gilt auch für die Zeilen, die in die Nacharbeit gehen, und jeder neue Probelauf nimmt es zurück. Das **Prüfintervall** zählt in Monaten; „Jahre“ im Spaltentitel („Prüfintervall (Jahre)“, „Intervall in Jahren“) oder am Wert („1 Jahr“, „0,5 Jahre“) gilt, ebenso „jährlich“, „halbjährlich“, „2x jährlich“, „alle 6 Monate“; eine 1 oder 2 ohne Einheit kommt in die Nacharbeit (Monate oder Jahre?), ein kürzeres Intervall als das wirksame wird mit Hinweis am Artikel gespeichert. „1“, „01“, „1,0“ und „1 Stk.“ sind ein Artikel, größere Anzahlen Sammelzeilen. Dann **„Übernehmen: n Artikel anlegen, m Zeilen in die Nacharbeit“** – in einer Transaktion. Die Tabelle „angelegt“ nennt je Zeile die neue Inventarnummer zum Beschriften (alte Nummern stehen nur in der Bemerkung und sind nicht suchbar). Importierte Artikel stehen auf **„neu“**; die Fälligkeit kommt aus „nächste Prüfung“ bzw. „zuletzt geprüft“ + Intervall (höchstens heute + Intervall), ohne beides ist die Eingangsprüfung sofort fällig. Zeilen ohne Herstellerseriennummer bekommen eine Seriennummer vom System (STR-…). Was die Liste sagt, aber nicht übernommen wird (unlesbare Daten, ein Lebensende bei Metall), steht als „… laut Liste: …“ in der Bemerkung. Was schon im Bestand steht (Produkt und Seriennummer), wird übersprungen, nie aktualisiert; dieselbe Datei in denselben Ordner wird 10 Minuten lang abgelehnt – der Probelauf sagt dann, ab wann es wieder geht, und bietet kein „Übernehmen“ an. Stehen Zeilen derselben Datei (gleiche Prüfsumme) noch in der Nacharbeit, ersetzt ein erneutes Hochladen sie über die Zeilennummer, statt sie zu verdoppeln; Zeilen ohne Seriennummer, die damals schon angelegt wurden, entstünden dagegen noch einmal (der Probelauf sagt es). Produkte werden nie geraten: nur gleicher Dublettenschlüssel, gleiche Artikelnummer beim gleichen Hersteller (trägt sie mehr als ein Hersteller und die Liste nennt keinen davon, geht die Zeile in die Nacharbeit) oder Hersteller + Modellname bei genau einem Produkt (ein Grundprodukt mit Varianten „Modell | Zusatz“ ist mehrdeutig, auch ohne Artikelnummern); dieselbe Seriennummer bei zwei Varianten desselben Herstellers in einer Datei geht in die Nacharbeit. Der Import legt keine Produkte und keine Ordner an. **Grenzen**: höchstens 5 MB (xlsx entpackt 10 MB, CSV 10 000 Zeilen), 2000 Datenzeilen, 300 Spalten; je Arbeitsprozess ein Import gleichzeitig. **Nacharbeit**: Was nicht sicher passt (Produkt unbekannt oder mehrdeutig, Seriennummer unbrauchbar oder zu kurz, Pflichtdatum fehlt, Ordner unbekannt, Sammelzeile „Anzahl 10“, Dublette), steht in der Nacharbeit des Zielordners – unten auf derselben Seite, mit Hinweis im Ordnerkopf und auf der Übersicht. Dort ordnet man Produkte je Angabe oder zeilenweise zu (Größen, Varianten), meldet ein fehlendes Produkt (die Material-Verwaltung legt es gleich im Katalog an), prüft erneut und übernimmt oder verwirft. Je Produktangabe eine Karte: „Produkt zuordnen“ – danach öffnet sich gleich die Prüfung dieser Zeilen mit „k Artikel übernehmen“ (rot) oder „Abbrechen“; eine zugeordnete Karte (oder eine eingepflegte Meldung) trägt dafür auch „Übernehmen“ (Wünsche vom 25.10.2026). Die Material-Verwaltung legt ein fehlendes Produkt mit „Im Katalog anlegen“ an (danach dieselbe Prüfung), alle anderen Verwalter melden es mit **„Fehlendes Produkt melden“** – vorbelegt mit Hersteller, Modell, Artikelnummer und einer Bemerkung (Satz zum Import und bis zu fünf Bemerkungen der Zeilen, ohne Serien- und Inventarnummern); Norm und Kategorie kennt der Import nicht. Werte korrigiert man in der CSV (Knopf „Als CSV herunterladen“, Spalte „Nacharbeit-Nr.“ nicht ändern) und lädt sie als neue Liste hoch – die alten Zeilen werden dabei erledigt, auch zweimal hochgeladen entsteht nichts doppelt. **Offene Zeilen verfallen einen Monat nach dem Import** (danach verworfen, Werte gelöscht); eine vorher heruntergeladene CSV prüft solche Zeilen beim Hochladen wie neue – von Hand verworfene bleiben erledigt (Nacharbeit-Nr. leeren, um sie doch zu übernehmen). Gespeichert werden nur zugeordnete Spalten und nur, solange die Zeile offen ist; der Dateiname steht nur am Import und im Ordnerjournal; beim Löschen eines Kontos wird sein Name dort „(gelöschtes Konto)“. Ein Ordner mit offener Nacharbeit lässt sich nicht löschen.
- **Prüfanleitung aus der Strömipedia** (Phase 2 · L3) ist **seit dem 04.11.2026 entfernt** (Wunsch des Nutzers): keine Zeile „Prüfanleitung in der Strömipedia“ am Prüfformular, kein Dialog zur Seitenwahl, keine Einblendung in offenen Prüfungen; `GET /api/material/wiki/seiten` und `PUT /api/material/formulare/<id>/wiki` antworten 404, `formular.wiki`, `formular.wiki_aendern` und `pruefung.anleitung` gibt es nicht mehr, neue Formularversionen erben nichts. Die Spalte `mat_form.wiki_page_id` samt Index entfernt Schritt 37 (siehe „Aufräumen“); alte Journal-Einträge „Prüfanleitung (Strömipedia) geändert“ bleiben lesbar. Für Prüfanweisungen bleiben die Herstellerdokumente am Produkt (Art „Prüfanweisung“).
- **Verweise auf die Anleitung** (Wunsch vom 28.10.2026, Entscheidung „Nur wer lesen darf“): Die Materialablage verlinkt den Strömipedia-Artikel „Materialablage“ und seine Unterseiten – als „Mehr dazu in der Strömipedia“ am Ende von 28 Infos („i“; vier an Seitenüberschriften, drei neu: „Gemeldete Mängel“, „Laufende Prüfdurchgänge“, „Art“ im Ordnerdialog), als **„i“ an der Überschrift** jeder anderen Seite (15 Seiten und die Übersicht „Materialablage“; seit dem 02.11.2026 – Wunsch des Nutzers „Füge die Anleitungen einheitlich in einem i bei der Überschrift hinzu“ – statt des Textlinks „Anleitung“ dahinter und des blauen Hinweiskastens oben auf der Übersicht: ein Satz, worum es geht, und „Anleitung in der Strömipedia öffnen“; hat die Überschrift schon ein „i“, steht der Link dort als „Mehr dazu“), in der Hilfe-Box von „Echtheit prüfen“ und im Dialog **„Willkommen in der Materialablage“** beim allerersten Besuch der Übersicht (je Konto einmal, gemerkt in `mat_meta` als `willkommen:<Konto>`, ohne Schemaschritt; auf dev erst nach dem Hinweis „Entwicklungsserver“). Gefunden wird jede Zielseite zur Laufzeit über ihren **Titel** im Teilbaum unter der Seite „Materialablage“ (mit Unterseiten; nicht über die Adresse, die der ZIP-Import aus dem Titel bildet), ein Anker nur, wenn die Seite die Überschrift hat; sonst führt der Link an den Seitenanfang. **Es zählen nur Seiten, die für alle Angemeldeten freigegeben sind** (selbst oder über einen Abschnitt darüber) – die Wurzel und jede Themenseite, auch für Übersicht und Willkommen (Entscheidung des Nutzers vom 01.11.2026 nach der Sicherheitsprüfung: vorher konnte jeder Redakteur die Verweise mit einer eigenen, neueren Seite „Materialablage“ oder einer Unterseite mit kleiner `position` umlenken; freigeben darf nur die Wiki-Verwaltung, und in einem freigegebenen Abschnitt legt nur sie Seiten an). Der Artikel wird also **erst verlinkt, wenn die Wiki-Verwaltung ihn über „Teilen“ → „Für alle Angemeldeten freigeben“ (samt Unterseiten) freigegeben hat**; mehrere freigegebene Seiten „Materialablage“ mit Unterseiten: die neueste gewinnt. Zusätzlich wird jede Seite mit den Rechten der Strömipedia geprüft (Stufe in der Strömipedia samt Lesebeschränkung, ohne Stufe nur die für alle Angemeldeten freigegebenen Seiten): Was das Konto nicht lesen darf, im Papierkorb liegt oder fehlt, bekommt keinen Link – das „i“ behält seinen Text, das „i“ der Anleitung und das Willkommen entfallen. Die Tabelle Thema → (Seitentitel, Anker) steht nur in `app/material/services/anleitung.py` (`THEMEN`); ändert sich ein Titel oder eine Überschrift im Artikel, verschwindet der Link bzw. sein Anker still – `tests/test_material_anleitung.py` gleicht die Tabelle mit dem Artikel ab, wenn er auf dem Rechner liegt. Alle Links öffnen einen neuen Tab.
  - **Strömipedia, Ankerplätze und Riegenkarten** (seit dem 01.11.2026, Freigabe des Nutzers: `planung/wiki-module/plan_anleitungsverweise.md`): die Anleitung als „i“ an der Überschrift (seit dem 02.11.2026, vorher der Textlink „Anleitung“ im Seitenkopf; `S.anleitung.kopf` in common.js liefert das „i“, das ins Element der Überschrift gehört) und „Mehr dazu in der Strömipedia“ am Ende der vorhandenen „i“ – kein Willkommen, kein Hinweiskasten. „Anleitung zum Editor“ im „⋯“ des Editors bleibt; „Anleitung zur Strömipedia“ im „⋯“ einer Seite ist am 02.11.2026 entfallen (Wunsch des Nutzers – die Anleitung steht im „i“ der Übersicht). Dieselben Regeln wie oben (Titel unter der Wurzel, Anker über die Kennung der Überschrift, **nur für alle Angemeldeten freigegebene Seiten** – die drei Artikel werden erst nach „Teilen“ → „Für alle Angemeldeten freigeben“ samt Unterseiten verlinkt –, nur wer lesen darf, fehlt die Seite, kein Link); die Suche steht allgemein in `app/anleitung.py` (`aufloesen`, eine Wurzel und eine Themen-Tabelle je Modul in `TABELLEN`), die Materialablage nutzt sie mit ihrer eigenen Tabelle unverändert. Die Seiten bekommen die Adressen als `data-anleitung`, die Oberfläche fragt über `S.anleitung` (common.js). Links öffnen einen neuen Tab – außer dem „i“ an der Übersicht der Strömipedia, das in der Strömipedia bleibt. Weil der Artikel „Strömipedia“ selbst in der Strömipedia liegt, zeigt dort kein Link auf die Seite, die gerade offen ist (gelesen oder bearbeitet). `tests/test_module_anleitung.py` gleicht die Tabellen mit den Artikeln unter `/home/harness/wiki-*/artikel` ab, wenn sie auf dem Rechner liegen. **Diese Titel und Überschriften dürfen sich in den Artikeln nicht ändern** (sonst verschwindet der Link bzw. führt an den Seitenanfang):
    - **Strömipedia** (Wurzel „Strömipedia“): Übersicht → „i“ an „Strömipedia“ auf „Strömipedia“; „⋯“ im Editor → „Anleitung zum Editor“ auf „Der Editor“; „i“ Papierkorb → „Papierkorb, Export und Import“ `#papierkorb`; „i“ Bearbeiten erlauben (Teilen) → „Teilen und Freigaben“ `#bearbeiten-erlauben`; „i“ Textfarbe → „Der Editor“ `#auswahlleiste`; „i“ Abschnitt einbinden → „Der Editor“ `#synchronisierte-abschnitte`; „i“ Spalten einfügen → „Der Editor“ `#callouts-spalten-und-boxen`. Ohne Stufe in der Strömipedia (Lesemodus) gibt es dort keinen Link – die Lesemodus-Ansicht hat weder Seitenkopf noch „i“.
    - **Ankerplätze** (Wurzel „Ankerplätze“): Seitenleiste „Alben“ → „i“ am Titel auf „Ankerplätze“; Seitenleiste eines Albums → „Alben“ `#album-in-der-seitenleiste`; „i“ Album im Dialog „Album anlegen“ → „Alben“ `#album-anlegen`, in „Album bearbeiten“ → `#album-bearbeiten`. Die Karte selbst hat keinen Seitenkopf; in der Werkzeugleiste ist am Telefon kein Platz.
    - **Riegenkarten** (Wurzel „Riegenkarten“): Lehrgangsliste → „i“ an „Riegenkarten“ auf „Riegenkarten“; Lehrgangsseite → „i“ am Titel auf „Lehrgänge“ `#die-lehrgangsseite`; Katalogseite → „Prüfungsleistungen und Kataloge“ `#katalogseite`; „i“ an „Prüfungsleistungskataloge“ → dieselbe Seite `#pruefungsleistungskataloge`; „i“ Lehrgangsleitung und Referierende → „Lehrgänge“ `#leitung-und-referierende-eintragen`; „i“ Prüfungsleistungen aus Katalog → „Lehrgänge“ `#pruefungsleistungen-aus-einem-katalog`; „i“ Zeitansatz → „Bewertung“ `#stoppuhr`; „i“ Kriterienliste → „Prüfungsleistungen und Kataloge“ `#kriterienliste`; „i“ Datei (.xlsx) im Import → „Teilnehmerliste importieren“ `#was-der-import-erkennt`; „i“ eingefroren → „Mängel, Druckansichten und Lehrgangsergebnis“ `#eingefroren`. Die Druckansichten bekommen keine Adressen.
- **Austritt und Löschen**: Beim Austritt 1. die PSA zurücknehmen (Zuordnung lösen), 2. das Konto deaktivieren (seine Freigaben wirken dann nicht mehr), 3. nach Klärung offener Prüfungen löschen – der Dialog „Löschen“ nennt vorher, was im Modul folgt. Beim Löschen entfernt die Anwendung Freigaben und Zuordnungen (je mit Journaleintrag), setzt offene Entwürfe auf „(gelöschtes Konto)“ ohne Urkundennummer (die Reservierung hebt der Materialwart auf), nimmt den Namen aus Produktmeldungen und Suchprotokoll und löscht die Zeilen des Kontos im Erinnerungslog und im Mailfehler-Protokoll (Arbeitsdaten, sonst nach 13 Monaten weg). Festgeschriebene Prüfungen, Aussonderungen, Durchgänge, Rückrufe, Mangelmeldungen und das Journal behalten die Namen der Handelnden – Nachweis nach EN 365 (der Dialog „Löschen“ nennt die Zahl der Mangelmeldungen, die den Namen behalten). **Prüfnachweise werden unbefristet aufbewahrt** (Entscheidung des Betreibers vom 18.10.2026): Prüfungen samt Befunden, Befundfotos und Anhängen, Aussonderungen, Prüf-, Aussonderungs- und Sammelprotokolle, Durchgänge mit Geprüftem, das Journal und die Herstellerdokumente, die ein Protokoll nennt, löscht die Anwendung nie – auch nicht nach der Aussonderung oder mit dem Konto des Prüfers; Artikel, Ordner, Durchgänge und Kategorien, an denen ein Nachweis hängt, lassen sich nicht löschen. Verwerfen lassen sich nur offene Entwürfe. Betroffene (wer eine Freigabe hatte, wem etwas zugeordnet war) stehen im Journal nur unter einer Zufallskennung, die mit dem Konto verschwindet. Das ist **Pseudonymisierung, keine Anonymisierung**: Aus dem Zusammenhang (Zeitpunkt, wer gleichzeitig handelte) bleibt ein Rückschluss möglich. Die stündliche Sicherung `~/data.bak` (siehe „Daten und Sicherung“) hält nur den Stand der letzten vollen Stunde – Gelöschtes ist spätestens nach einer Stunde auch dort weg; weitere Kopien (etwa Snapshots des Hosters) halten es bis zu ihrer eigenen Frist. Vorschlag für das Verfahrensverzeichnis der Gliederung (abstimmen und juristisch prüfen lassen): Zweck Prüfnachweis der PSA und Materialverwaltung; Kategorien Konto, Rolle, Urkundennummer, Unterschrift, Zuordnung PSA ↔ Person, Freigaben, Suchprotokoll, Mangelmeldungen (Beschreibung, bis 3 Fotos ohne Ortsangaben, Melder, Zeitpunkt; unbefristet mit dem Artikel) – das Verzeichnis ausgegebener Lebensläufe (Kennung, Inventarnummer, Zeitpunkt, Prüfsummen) enthält keine Personendaten, wer abruft, wird nicht gespeichert –, Mails an Zugeordnete (Erinnerungen „Deine PSA“ abbestellbar, Sperrmitteilung nicht; auch an Konten ohne Modulstufe; Erinnerungslog 13 Monate; Mailfehler-Protokoll: Arbeitsdaten, 13 Monate, mit dem Konto gelöscht); Empfänger Verwalter und Prüfer des Ordners, Material-Verwaltung, Plattform-Verwaltung, die zugeordnete Person (nur ihre eigene PSA); Maßnahmen Pseudonymisierung der Betroffenen im Journal, Löschung des Kontos; Fristen: Suchprotokoll zwölf Monate, Sicherungen mit ihrer Frist (trägt der Betreiber ein), Prüfnachweise unbefristet, auch nach der Aussonderung (Entscheidung des Betreibers vom 18.10.2026 – die Begründung der unbefristeten Speicherung im Verfahrensverzeichnis bitte juristisch prüfen lassen).
- **Aufräumen** (Wunsch vom 04.11.2026; **Schema 37**): Spalten entfernter Funktionen fallen mit `ALTER TABLE … DROP COLUMN` (SQLite ≥ 3.35, kein Neuaufbau einer Tabelle): `mat_form.wiki_page_id` samt `idx_mat_form_wiki` (Prüfanleitung), `mat_product.wiki_page_id` (nie benutzt), `mat_folder.owner_user_id` (nie benutzt), am Artikel `parent_item_id` samt den Wächtern `mat_item_kein_teil*`, `lock_cause`, `set_lock_origin`, `set_pruefen` (Sets, seit Schema 26 leer), an der Produktmeldung `is_set` und `set_teile` (Set-Meldung – die Zeile „Teile laut Meldung“ entfällt), `mat_checklist_item.is_critical` (Marke „kritisch“, entfallen am 03.11.2026) und `users.mat_katalog` (Häkchen „Produktkatalogpfleger“, seit Schritt 10 ungelesen; nicht mehr in `db.MIGRATIONS`). **Bleiben** als Nachweis bzw. weil Schutz-Trigger sie nennen: `mat_product.is_set`, die Set-Spalten der Bestandteil-Liste, `mat_inspection.set_lauf_id` mit `mat_set_lauf` und `mat_set_protokoll_zeile`, `mat_inspection_result.is_critical` (Kopie in festgeschriebenen Befundzeilen); Journal-Beschriftungen alter Einträge ebenso. Das Startprotokoll nennt je Spalte, wie viele Zeilen einen Wert verloren (`grep "Schritt 37"`). Dazu fiel toter Code: `rechte.urkunde_fehlt`, der alte Pfad `POST /api/material/pruefungen/<id>/abschliessen` (heute nur `…/festschreiben`), `GET /api/wiki/watches` (Beobachten selbst bleibt), die unbenutzten Übungsbilder in `app/static/uebung/` und eine CSS-Regel ohne Erzeuger. Rückweg nur über die Sicherung (siehe „Daten und Sicherung“).
- **Sets als Ordner** (Rückbau der Set-Funktion, Wunsch vom 25.10.2026; **Schema 26**): Ein Set ist wieder ein Ordner der Art „Set“ (Rucksack, Kiste, Beutel) im Bestand – kein Katalogprodukt mit Teilen mehr. „Set anlegen“, Set-Artikel mit Teilen, „Set prüfen“, Teile tauschen, entnehmen oder einsetzen, „Stückliste übertragen“ und die Set-Meldung gibt es nicht mehr; „Fehlendes Produkt melden“ meldet nur ein Produkt. Herstellersets stehen als Produkt mit Bestandteil-Liste im Katalog (unten). Die Katalogdatei lehnt `"set": true` als Fehler dieses Produkts ab. Schritt 26 hat den Altbestand auf dev umgestellt: Teile sind eigene Artikel im selben Ordner (Gesperrte bleiben gesperrt, bis ein Prüfer frei prüft), Set-Produkte normale Produkte mit ihren Text-Positionen; festgeschriebene Set-Protokolle bleiben Datei und Prüfsumme. Einzelheiten und Rückweg: `CHANGELOG-Material.md`, „Rückbau der Set-Funktion“.
- **Set-Protokolle im Prüfdurchgang** (Wunsch vom 25.10.2026; **Schema 27**): Schließt man einen Durchgang regulär ab, bekommt jedes Set (Ordner der Art „Set“) unterhalb des Durchgangsordners, in dem mindestens ein Artikel geprüft wurde, zusätzlich zum Sammelprotokoll ein eigenes **Set-Protokoll** (T-<Jahr>-<Nr>) – „wie ein Durchgang nur für dieses Set“: alle Artikel darunter (auch die innerer Sets), Ergebnisübersicht, Prüfer dieses Sets mit Unterschrift, „Teil von Sammelprotokoll S-…“. Nicht beim Abbruch. Im Sammelprotokoll stehen die Artikel eines Sets zusammen unter Zwischenzeilen (je Set von außen nach innen, „(Fortsetzung)“ beim Rückweg in ein äußeres Set, „Außerhalb von Sets“ danach), dahinter das Verzeichnis der Set-Protokolle mit Prüfsumme. Die Durchgangsseite zeigt die Set-Protokolle und „Alle Protokolle (ZIP)“ (Sammelprotokoll, Set-Protokolle, Verzeichnis.csv – den Knopf gibt es nur bei Durchgängen mit Set-Protokollen; sonst genügt „Protokoll (PDF)“ neben der Überschrift „Sammelprotokoll“, die Einzelprotokolle stehen im Protokoll-ZIP des Ordners), die Ordnerseite eines Sets den Abschnitt „Set-Protokolle“ (bzw. „Set- und Sammelprotokolle“). Öffnen darf ein Set-Protokoll, wer den Durchgang sieht oder das Set lesen darf – auch nach dem Verschieben des Sets in eine andere Gliederung (vom Nutzer bestätigt); die Prüfseite erkennt es. Die PDFs entstehen vor dem kurzen Festschreiben ohne Schreibsperre – ein Abschluss mit vielen Sets hält die übrige Plattform nicht auf.
- **Produkte mit Bestandteil-Liste** (Wunsch vom 25.10.2026; **Schema 25**): Herstellersets kommen als normale Produkte mit einer Liste „Bestandteile“ (je Position Bezeichnung und Anzahl, nur Text, ohne Teil-Artikel); pflegen darf sie die Material-Verwaltung. Im Produktdialog hat jedes Produkt die Reiter „Produkt“ und „Bestandteile“; die Produktseite zeigt den Abschnitt „Bestandteile“ („Bestandteile bearbeiten“), die Artikelseite, Meine PSA und das Lebenslauf-PDF die Zeile „Bestandteile“. Jede Prüfung fragt je Position „vorhanden/fehlt“ ab (oder „n. z.“, wenn die Position an diesem Artikel nicht vorkommt – dann ohne Seriennummern) – „fehlt“ ist ein Mangel (Foto und Bemerkung). **Seriennummern der Bestandteile**: am Artikel je Stück freiwillig, beim Anlegen und bis zur ersten Prüfung direkt (Dialog „Bearbeiten“), danach trägt sie der Prüfer in der Prüfung ein (Protokoll „alt → neu“) oder man beantragt sie; die Suche findet den Artikel auch über sie, Rückrufe treffen Bestandteile nicht. Die Katalogdatei kennt `bestandteile` (Bericht „Bestandteil-Listen“; Vorlage `docs/material-katalog-bestandteile-vorlage.json`).
- Katalogimport für die Ergebnisse aus Phase 0: `flask --app "app:create_app()" material import-catalog datei.json` (Format in `CHANGELOG-Material.md`, Vorlage mit Kategorien und Normen in `docs/material-katalog-vorlage.json`). Prüfpunkte im Katalogformat: `gruppe`, `text`, `art`, `pflicht`, `soll`; ein `kritisch` aus älteren Dateien wird seit dem 03.11.2026 ohne Fehler übergangen (nicht gespeichert, auch nicht geprüft), der Export schreibt es nicht mehr. Ein erneuter Import derselben Datei legt keine neue Formularversion an, nur weil ein vorhandenes Formular noch die alte Markierung trägt.
- **Katalog exportieren und importieren**: Katalog → „Katalog exportieren“ (oder `material export-catalog katalog.zip`) – ein ZIP im **Format 3** mit Kategorien, Produkten samt Bild und Herstellerdokumenten und den **aktiven Prüfformularen samt Zuweisungen** (je Formular des Pools mit aktiver Version genau diese, mit uid, Heimat, „standard_fuer“ und „zugewiesen“; auch mit DEMO-Kennzeichen und aktive Platzhalter der Skripte; ohne aktive Version keins), ohne DEMO-Kategorien und -Produkte, ohne Bestand, Prüfungen, Meldungen, Rückrufe und **ohne Journal** (keine Konten, Namen, Bearbeitungszeiten). Der Bericht im ZIP nennt die Formulare und welche hier DEMO bzw. Platzhalter sind. Auf der anderen Anlage Katalog → „Katalog importieren“: erst ein Probelauf mit Bericht (neu, geändert, unverändert, Warnungen zu vorhandenen Artikeln, Zuweisungen gesetzt/gelöst), dann „Übernehmen“ (oder `import-catalog katalog.zip --trocken`, danach ohne `--trocken`). Kategorien, Produkte und Formulare tragen eine dauerhafte Katalogkennung – umbenennen oder verschieben auf dev kommt als Änderung an, nicht als Dublette; ein Formular ohne bekannte Kennung findet der Import über den Titel in derselben Heimat (der Bericht nennt es mit seinen bisherigen Zuweisungen). Der Import **übernimmt nie ein DEMO-Kennzeichen** (auch kein Feld `demo` der Datei), nimmt ein führendes „DEMO“ aus Formulartiteln (groß oder klein geschrieben) und macht jedes Formular der Datei **aktiv** (eine neue Version, wenn Titel oder Prüfpunkte abweichen; ein zweiter Import ändert nichts). Für Zuweisungen ist **die Datei maßgeblich**: Für jedes Formular und jede Kategorie bzw. jedes Produkt der Datei gilt danach genau, was sie sagt – eine Zuweisung hier, die sie nicht nennt, wird gelöst; Zuweisungen zwischen Formularen und Zielen, die es nur hier gibt, bleiben (eine Datei ganz ohne Formulare löst so die Zuweisungen ihrer Kategorien und Produkte – der Bericht warnt und nennt sie). Sonst löscht der Import nichts: `"bestandteile": []` leert eine Bestandteil-Liste, `"artikel_laenge": false` nimmt das Häkchen weg. Ältere Dateien (Format 1/2) kommen weiter herein: ein Formular mit `kategorie` wird deren Standard, eins mit `produkt` kommt in den Pool der Kategorie des Produkts und wird ihm zugewiesen, `formular_von` (Schema 35) wird die Zuweisung an das Formular der Quelle. Ein Formular hier schreibt eine solche Datei nur um, wenn es allein diesem Ziel gilt (beim Produkt auch den Produkten, die es laut derselben Datei übernehmen); gilt es auch anderswo (Standard, weitere Produkte), kommt ein neues in den Pool und das geteilte bleibt unverändert – der Bericht sagt es und nennt bei jeder neuen Version, wofür das Formular bisher galt. Für die Produktion siehe „Inbetriebnahme in der Produktion“: dev exportieren, dort importieren.
- **Katalogimport im Hintergrund** (24.10.2026): Probelauf und Übernehmen laufen als Auftrag auf dem Server. Der Dialog lädt die Datei hoch (mit Fortschritt), zeigt dann Phase und Zahlen („Datei prüfen“, „Probedurchgang“, „Dateien ablegen n von m“, „Datenbank schreiben“) und am Ende den Bericht; „Übernehmen“ nimmt die Datei des Probelaufs (sie liegt eine Stunde bereit, kein zweiter Upload). Der Dialog darf zu – oben auf der Katalogseite steht ein laufender oder am selben Tag beendeter Import mit „Stand ansehen“ bzw. „Bericht ansehen“. Es läuft immer nur ein Katalogimport (ein zweiter Start bekommt die Meldung mit dem laufenden). Endet der Server mitten im Lauf (Neustart, Deploy), zeigt der Auftrag nach spätestens 30 s „abgebrochen“. Die Datenbank schreibt der Import ganz oder gar nicht; schon abgelegte Bilder und Dokumente räumt der Server weg – höchstens die eine Datei, die er im Moment des Abbruchs gerade schrieb, kann unter `media/material` liegen bleiben (mit nichts verknüpft, nie angezeigt; ein Dokument heißt nach seinem Inhalt und wird beim nächsten Lauf wiederverwendet). Brach ein „Übernehmen“ ab, bevor es gespeichert hatte, liegt die Datei des Probelaufs wieder eine Stunde bereit und „Übernehmen“ geht noch einmal; sonst zeigt ein neuer Probelauf mit derselben Datei, ob noch etwas fehlt. Vor dem Hochladen fragt der Dialog, ob schon ein Import läuft, und lädt dann gar nicht erst hoch; nach 100 % steht „Datei wird abgelegt …“, bis der Server antwortet – wer da schließt, bricht nichts mehr ab. Ein neuer Import löscht die Datei eines älteren Probelaufs (dessen „Übernehmen“ ist damit überholt); reicht der Platz auf dem Server nicht für die Datei plus 64 MB Reserve, lehnt er mit 507 und den Zahlen ab. Der Auftrag nennt das Konto, das ihn gestartet hat, nur über den pseudonymen Kontoverweis wie das Journal – nach dem Löschen des Kontos steht dort „(gelöschtes Konto)“, und niemand sonst kann seinen Probelauf übernehmen (Nachbesserung nach der Sicherheitsprüfung, 24.10.2026). Zwischendaten liegen unter `data/katalog-import/` (nur für den Container lesbar, nach 7 Tagen weg). Die Zeitgrenze des Reverse-Proxys gilt für den Import nicht mehr, nur noch für das Hochladen selbst. Die Kommandozeile bleibt synchron.
- **Update auf Schritt 18 (Herstellerdokumente einmal je Inhalt, 22.10.2026)**: Beim ersten Start danach führt die Anwendung die vorhandenen Dokumentdateien unter `media/material/dok` einmal zusammen – jede bekommt den Namen ihrer Prüfsumme (aus der Datei gerechnet, nicht aus der Datenbank), gleiche Inhalte werden eine Datei, die Datenbank bekommt die neuen Namen samt Prüfsumme und Größe; die alten Namen verschwinden erst nach dem Commit; ein Abbruch vor dem Commit lässt beide Namen stehen und der nächste Start holt es nach, ein Abbruch danach lässt die alten Namen als Dateien ohne Zeile zurück, die der nächste Start aufräumt. Das Log sagt dann einmal `Herstellerdokumente einmal je Inhalt (Schritt 18): N Dateien → M, X MB frei; …`. Eine Zeile, deren Datei fehlt, behält ihren Namen und steht als Warnung im Log (`Dokumentdatei fehlt unter media/material/dok: …`). Jeder spätere Start räumt den Ordner unter `media/material/dok` nur noch auf: Dateien ohne Zeile, deren Inhalt unter seinem Inhaltsnamen liegt, und Zwischendateien (Name mit Punkt davor) älter als ein Tag gehen weg (`media/material/dok aufgeräumt: …` als Info); andere Dateien ohne Zeile bleiben liegen und stehen als Warnung im Log (`media/material/dok: n Dateien ohne Zeile (x MB) – sie bleiben liegen …`) – dann nachsehen, was da liegt (22.10.2026). Ist `media/material/dok` beim Start nicht erreichbar, geschieht nichts, die Anwendung startet trotzdem, und das Log warnt (`… nicht erreichbar – die Zusammenführung … wartet auf den nächsten Start`). Von Hand, mit Bericht (Dateien und Bytes vorher/nachher, fehlende Dateien, Dateien ohne Zeile, entfernte Zwischendateien): `docker compose exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material dok-zusammenfuehren --probe` (rechnet nur) bzw. ohne `--probe`. Vorher wie immer die stündliche Sicherung abwarten oder `data/` sichern.
- **Inbetriebnahme in der Produktion**: siehe den eigenen Abschnitt [„Inbetriebnahme in der Produktion (erster Merge dev → main)“](#inbetriebnahme-in-der-produktion-erster-merge-dev--main) – Sicherung, Merge, Kontrolle, Gliederungen und Stufen, Katalog-ZIPs, Erinnerungsmails zuletzt. Wo es schon Gliederungen gibt (dev), hat die Migration aus den Stufen aus Phase 1 Freigaben gemacht (Schritt 8) und danach die Stufen gesetzt (Schritt 10: bisherige Produktkatalogpfleger und die Plattform-Verwaltung werden Material-Verwaltung, wer eine Stufe, eine Freigabe oder das Häkchen „Prüfer“ hat, wird Mitglied); befristete Prüffreigaben externer Prüfer laufen bis zum 31.12. des Folgejahres und kündigen sich per Erinnerungsmail an.

## Schnellstart

```bash
cp .env.example .env        # BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD setzen
mkdir -p data && sudo chown -R 1000:1000 data   # der Datenordner gehört dem Nutzer im Container
docker compose up -d --build
```

Danach läuft die Anwendung auf `http://127.0.0.1:8080`.

> **Beim ersten Ausprobieren ohne HTTPS unbedingt `COOKIE_SECURE=false` in die `.env` schreiben.**
> Sonst markiert die Anwendung das Sitzungscookie als `Secure`, der Browser verwirft es auf einer
> HTTP-Seite – die Anmeldung meldet Erfolg und man landet trotzdem wieder auf der Anmeldeseite.
> Im Protokoll (`docker compose logs`) steht dann ein entsprechender Hinweis. Hinter einem
> Reverse-Proxy mit TLS bleibt `COOKIE_SECURE=true` richtig; der Proxy muss `X-Forwarded-Proto`
> mitschicken (Caddy tut das von sich aus).

Läuft der Container, aber die Seite lädt nicht, hilft `docker compose logs` weiter; `docker compose ps` zeigt außerdem, ob der Healthcheck grün ist.

Beim Bauen lädt der Container die JavaScript-Bibliotheken (Leaflet, Leaflet.markercluster, marked, DOMPurify, Toast UI Editor) in festen Versionen herunter und prüft jede Datei gegen `vendor.sha256`; zur Laufzeit ist außer den Kartenkacheln kein fremder Server nötig. Einzige Ausnahme ist die deutsche Sprachdatei des Editors: sie hat eine eigene Prüfsumme im Dockerfile und darf fehlen – dann läuft der Editor auf Englisch weiter.

## Betrieb hinter strömis.de

Der Container spricht nur HTTP auf Port 8080. TLS und die Umlaut-Domain übernimmt ein Reverse-Proxy, z. B. Caddy:

```
strömis.de, xn--strmis-yxa.de, wiki.strömis.de, wiki.xn--strmis-yxa.de {
    reverse_proxy 127.0.0.1:8080
    request_body {
        max_size 5GB
    }
}
```

Beide Hostnamen zeigen auf denselben Container: Anfragen mit dem Host `wiki.strömis.de` (`PUBLIC_HOST`) landen intern unter `/oeffentlich/…` – seit dem 01.11.2026 (kein Wiki ohne Anmeldung mehr) nur noch eine Weiterleitung zur Anmeldung auf `BASE_URL` mit Rücksprung in die Strömipedia (angemeldet gleich zur Seite); die Sitzung gilt nur auf der Hauptadresse. Alte Links auf die Subdomain bleiben so gültig; wer sie nicht mehr braucht, kann `wiki.*` aus dem Caddy-Block nehmen (dann laufen alte Links ins Leere). Dafür braucht die Subdomain einen DNS-Eintrag und ein Zertifikat (Caddy holt es automatisch).

Uploads bis 5 GB: bei nginx/Traefik `client_max_body_size`/`maxRequestBodyBytes` und die Timeouts entsprechend erhöhen (Gunicorn im Container wartet bis zu 60 Minuten). Der Katalogimport (Materialablage) wartet seit dem 24.10.2026 nicht mehr auf das Ende des Imports: Nach dem Hochladen kommt die Antwort sofort, der Import läuft im Hintergrund – die Antwort-Zeitgrenze des Proxys spielt für ihn keine Rolle mehr, nur die für den Upload. Der Container wertet `X-Forwarded-Proto/For/Host` aus (ProxyFix), damit Links und sichere Cookies stimmen. `docker-compose.yml` veröffentlicht Port 8080 auf allen Schnittstellen, damit auch ein Proxy auf einem anderen Rechner ihn erreicht. Wer den Container direkt erreicht, könnte diese Kopfzeilen selbst setzen und damit die Anmeldebremse je IP umgehen – und Docker öffnet Ports an einer `ufw`-Firewall vorbei. Den Port deshalb in der Firewall des Anbieters nur für den Proxy freigeben; läuft der Proxy auf demselben Host, genügt `"127.0.0.1:8080:8080"` in der Compose-Datei. Der Container läuft ohne Capabilities und ohne Rechtegewinn (`cap_drop`, `no-new-privileges`), und sein Wurzeldateisystem ist schreibgeschützt (`read_only`): Beschreibbar bleiben nur das Datenvolumen `/data` und ein flüchtiges `/tmp` für Gunicorns Prozess-Lebenszeichen, den Schriften-Zwischenspeicher von Fontconfig und die Zwischendateien von WeasyPrint beim Erzeugen eines Protokolls (je Protokoll einige 100 kB, danach gelöscht).

Nach einem Update gilt: Wer die Anwendung im Browser offen hat, lädt die Seite einmal neu. Ein Reiter, der noch die alten Skripte ausführt, spricht sonst weiter mit der alten Schnittstelle – im schlimmsten Fall legt jeder seiner Zwischenstände eine eigene Fassung im Verlauf an.

### Automatisches Deployment

`.github/workflows/deploy.yml` verbindet sich bei jedem Push nach `main` oder `dev` (oder von Hand über „Run
workflow“ in GitHub) per SSH mit dem VPS. `main` geht in die Produktion (Klon unter `DEPLOY_PATH`), `dev` in die
Entwicklungsumgebung (eigener Klon, siehe unten); andere Zweige werden nie ausgerollt. Im jeweiligen Klon führt
er `git pull`, `docker compose up -d --build --remove-orphans` und `docker image prune -f` aus – der Build
läuft also auf dem VPS selbst, ohne Umweg über eine Registry.
Vorher prüft er, dass `data/` dem Nutzer 1000 gehört; sonst bricht er ab, und der laufende
Container bleibt stehen, statt durch einen ersetzt zu werden, der beim Start an fehlenden Schreibrechten stirbt.
Läuft gerade schon ein Deploy (auch der anderen Umgebung), wartet ein zweiter statt parallel zu starten. Die SSH-Action ist auf einen festen
Commit gepinnt (Kommentar `# v1` daneben): Ein wanderndes Tag könnte sonst anderen Code mit dem Deploy-Schlüssel
ausführen; zum Heben den neuen Commit eintragen.

Einmalige Einrichtung:

1. Auf dem eigenen Rechner ein eigenes Schlüsselpaar nur für dieses Deployment erzeugen (nicht den persönlichen
   Schlüssel verwenden): `ssh-keygen -t ed25519 -C "github-actions-deploy" -f deploy_key -N ""`.
2. Den öffentlichen Teil (`deploy_key.pub`) auf dem VPS in `~/.ssh/authorized_keys` des Deploy-Nutzers eintragen.
3. Im GitHub-Repository unter **Settings → Secrets and variables → Actions** anlegen:
   - `DEPLOY_HOST` – Adresse des VPS
   - `DEPLOY_USER` – SSH-Nutzer auf dem VPS
   - `DEPLOY_SSH_KEY` – Inhalt der privaten Schlüsseldatei (`deploy_key`)
   - `DEPLOY_PATH` – absoluter Pfad zum Klon dieses Repositories auf dem VPS (dort liegt `docker-compose.yml`)
   - `DEPLOY_PATH_DEV` – nur nötig, wenn der Klon der Entwicklungsumgebung nicht neben dem der Produktion
     liegt (Vorgabe: `DEPLOY_PATH` mit `-dev` dahinter, siehe „Entwicklungsumgebung“)
   - `DEPLOY_PORT` – nur nötig, wenn SSH dort nicht auf Port 22 läuft
4. Auf dem VPS sicherstellen, dass der Deploy-Nutzer `git pull` im Repository ohne Rückfrage ausführen kann (bei
   einem privaten Repository braucht der VPS selbst einen eigenen, lesenden Zugang zu GitHub – z. B. ein weiteres
   Deploy-Schlüsselpaar, auf GitHub unter **Settings → Deploy keys** des Repositories hinterlegt) und Mitglied
   der Gruppe `docker` ist (`docker compose` ohne `sudo`).

Bis diese Secrets gesetzt sind, schlägt der Workflow beim ersten Lauf fehl – manuelles Deployment per SSH
funktioniert unverändert genauso wie bisher.

### Entwicklungsumgebung (dev.strömis.de)

Der Zweig `dev` läuft genauso wie die Produktion, nur getrennt: eigener Klon auf demselben VPS, eigene `.env`,
eigene Daten, eigener Container `stroemis-dev` auf Port 8008, erreichbar unter `https://dev.strömis.de`
(`dev.xn--strmis-yxa.de`). Jeder Push auf `dev` rollt dort automatisch aus; was sich bewährt hat, kommt per Merge
nach `main` und damit in die Produktion. Die Entwicklung beginnt mit leeren Daten und schickt Mails mit „(DEV)“ im
Absendernamen.

Nach jeder Anmeldung zeigt die Entwicklung einmal den Hinweis „Entwicklungsserver“ (Daten können sich ändern oder
verschwinden, Fehler sind zu erwarten, Rückmeldungen an bugs@stroemis.de) – auf der ersten Seite danach, egal welches
Modul. Erkannt wird die Entwicklung an `STROEMIS_NAME` mit „-dev“ am Ende (setzt `dev-einrichten.sh`; dieselbe Regel wie
die Sperre der Erinnerungsmails); in der Produktion und lokal ohne „-dev“ erscheint er nie.

Einmalige Einrichtung:

1. DNS: `dev.xn--strmis-yxa.de` als A-Eintrag (und AAAA, falls vorhanden) auf den VPS.
2. Auf dem VPS als Deploy-Nutzer das Einrichtungsskript aus dem Zweig `dev` holen und mit dem Ordner der
   Produktion aufrufen (an der Produktion ändert das nichts):

   ```bash
   git -C /pfad/zur/produktion fetch origin dev
   git -C /pfad/zur/produktion show origin/dev:scripts/dev-einrichten.sh > ~/dev-einrichten.sh
   bash ~/dev-einrichten.sh /pfad/zur/produktion
   ```

   Es klont den Zweig `dev` neben die Produktion (Ordnername mit `-dev`), kopiert die `.env` der Produktion und
   stellt sie um (Projekt-, Container- und Abbildname `stroemis-dev`, Port 8008, Adressen auf `dev.strömis.de`,
   eigener Sitzungsschlüssel), legt `data/` für den Nutzer 1000 an (einmal `sudo`), baut
   und startet. Ein anderer Zielordner: als zweites Argument angeben und in GitHub das Secret `DEPLOY_PATH_DEV`
   setzen.
3. Den Reverse-Proxy ergänzen und neu laden, z. B. Caddy:

```
dev.strömis.de, dev.xn--strmis-yxa.de {
    reverse_proxy 127.0.0.1:8008
    request_body {
        max_size 5GB
    }
    header X-Robots-Tag "noindex, nofollow"
}
```

Wie bei der Produktion veröffentlicht Docker den Port auf allen Schnittstellen und an `ufw` vorbei; 8008 also in
der Firewall des Anbieters nur für den Proxy öffnen, oder – läuft der Proxy auf demselben Host – in der `.env`
der Entwicklung `STROEMIS_PORT=127.0.0.1:8008` setzen. Unterscheiden sich Produktion und Entwicklung sonst
noch, dann nur über ihre `.env`; `docker-compose.yml` und das Dockerfile sind für beide dieselben.

`GET /healthz` antwortet ohne Anmeldung mit `{"ok": true}` – darauf setzt der `HEALTHCHECK` des Containers auf (alle 30 s, `docker ps` zeigt den Zustand). Die Daten liegen im Volume unter `/data`: `stroemis.db` (SQLite mit WAL), `media/` (Originale, Web-Größen, Thumbnails, Wiki-Anhänge, Profilbilder), `pdf/` (festgeschriebene Protokolle der Materialablage) und `secret_key`. Für eine Sicherung genügt es, dieses Volume zu kopieren – am besten bei gestopptem Container.

### DEMO-Daten und DEMO-Konten (nur dev)

DEMO-Daten und DEMO-Konten entstehen seit dem 25.10.2026 nur noch über den Beispielbestand (nächster Abschnitt) – das
frühere `scripts/material_demo.py` mit seinem kleinen DEMO-Katalog ist entfernt; der Beispielbestand braucht den
echten Katalog. **So kommen Browserproben an DEMO-Daten** (lokal, eigener Datenordner, nie im Repository):

```bash
export DATA_DIR=/home/…/probe-daten BASE_URL=http://localhost:8080 COOKIE_SECURE=false VIDEOPFLEGE=0
flask --app "app:create_app()" material import-catalog katalog-gesamt-teil01.zip   # ein Teil der Katalogserie
python scripts/material_beispielbestand.py --beispielbestand --artikel 60          # knapp zwei Minuten; 800: rund 30 min
python run.py                                                                      # dann mit den Konten aus der Ausgabe anmelden
```

Die Ausgabe nennt die Konten mit Passwort (`demo-wart-a@example.invalid` Materialwart, `demo-pruefer@…` Prüfer,
`demo-extern@…` externer Prüfer, `demo-mv@…` Material-Verwaltung, `demo-mitglied@…`, `demo-einsatzkraft-01@…` …).
Mails gehen keine hinaus. Für einen zweiten Stand einen neuen Datenordner nehmen – der Beispielbestand läuft je
Datenbank nur einmal.

### Beispielbestand (nur dev)

`scripts/material_beispielbestand.py` legt aus dem **vorhandenen Katalog** den Bestand einer großen Gliederung mit gut
zwei Jahren Geschichte an (Wunsch des Nutzers vom 25.10.2026):

- **Struktur:** „DEMO-Kreisverband Flussland“ mit Zentrallager (Regale Seile, Hardware, PSA, Reserve), fünf Fahrzeugen
  (zwei GW-Wasserrettung, zwei MTW, Mehrzweckboot) mit Seilrucksäcken und Taschen als Ordner der Art „Set“ (die
  Flaschenzugtasche liegt im Seilrucksack 1 – ein Set im Set), drei Strömungsrettungsgruppen und persönlichen Ordnern für
  bis zu 40 DEMO-Einsatzkräfte (je 20 Artikel eine); dazu die kleine „DEMO-OG Nachbarstadt“ (Lager, MTW) für die
  Trennung je Gliederung und die globale Suche (Seriennummer `DEMO-NS-4711`).
- **Artikel:** Vorgabe 800 (`--artikel N`), nur echte Produkte ohne Bestandteil-Liste. Mix nach Kategorien: viele Karabiner und
  Textilmaterial, je Einsatzkraft Gurt, Helm, Karabiner, Schlinge, Abseilgerät (soweit der Katalog sie hat; von Anfang
  an, Ersatz nach einer Aussonderung), Seile mit einer Länge, wenige Rollen, Flaschenzüge und Seilklemmen; je Typ wenige
  Standardprodukte. Den Typ gibt der Name der Kategorie (die unterste zuerst): Abseilgeräte und Abseilachten sind
  Abseilgeräte, Band- und Textilmaterial Schlingen, Seilrollen und Flaschenzüge Rollen – keine Seile. Seriennummern
  `DEMO-FL-0001` …, Ersatz `…-E`.
- **Geschichte („volles Leben“):** Ersterfassung je Bereich kurz vor seiner ersten Jahresprüfung, jährliche
  Prüfdurchgänge je Bereich (abgeschlossen, mit Sammelprotokoll), dazwischen Prüfungen bei kürzerem Intervall und
  außerplanmäßige nach Einsätzen, Mängel mit Sperre und Prüfung nach Reparatur, Aussonderungen (Mangel, Lebensdauer,
  Verlust) mit Nachkauf, Nachkäufe über die Jahre, verloren gemeldete Artikel, Verschiebungen, Zuordnungen (Einsatzkräfte
  scheiden aus, ihre Ausrüstung geht über die Reserve an neue; Ausgeschiedene bekommen danach nichts mehr), Änderungsanträge
  (bestätigt, abgelehnt, zurückgezogen, offen – jeder Zustand kommt vor). Ein Mangel (instandsetzen) wie ein schwerer, der
  zur Aussonderung führt, liegt auf einem Ja/Nein-Prüfpunkt – seit Schema 28 empfiehlt der Prüfer die Aussonderung
  („aussondern empfohlen“, sperrt), der Materialwart sondert danach aus (nach Verlust direkt); beim Lebensende steht
  der Punkt zur Lebensdauer auf „nicht in Ordnung“. Änderungsanträge entscheidet der Materialwart des Ordners. Dafür stellt das Skript die Uhr **seines eigenen Prozesses** zurück und lässt sie
  Tag für Tag laufen, nie über gestern hinaus – Journal, Prüftage, Protokolle und Durchgänge tragen ihr damaliges Datum.
  Bekannte Grenze: Was SQLite selbst stempelt (`applied_at` bestätigter Anträge, Trigger mit `'now'`), trägt den Lauftag.
  Die erste Prüfung im Durchgang heißt auch beim Erstbestand „Eingangsprüfung“ – ohne abgeschlossene Prüfung lässt die
  App keine andere Art zu. Heute: ein offener Durchgang im Zentrallager (teils erledigt, einer in Prüfung beim externen
  Prüfer, einer ausgenommen), im MTW 2 ist die Jahresprüfung ausgefallen (überfällig), die persönliche Ausrüstung ist
  bald fällig. Jeder Zustand kommt vor. Alle Texte (Befunde, Gründe,
  Bemerkungen) sind „DEMO – nicht für echte Prüfungen“, Mängel haben ein DEMO-Platzhalterfoto.
- **Formulare:** Hat eine echte Kategorie kein wirksames aktives Prüfformular, legt das Skript eins an –
  DEMO-gekennzeichnet, aktiv, nicht im Katalog-Export: nach den **Petzl-Prüfberichten**, wo
  `scripts/beispielbestand_petzl_punkte.json` die Kategorie nach ihrem Namen kennt (13 Kategorien – „Textilmaterial“
  auch unter dem älteren Namen „Bandmaterial“ –, Punkte wörtlich mit Gruppe und Soll – das Feld „kritisch“ der Datei
  bleibt seit dem 03.11.2026 ungenutzt; Fundstelle je Punkt in der Datei, Quellen mit Version im Bericht – Petzl, „Überprüfung von PSA – Prüfbericht/Vorgehensweise bei der
  Überprüfung“ je Produktgruppe, z. B. Gurte 110526, Karabiner 260625, Seile 071215; Abseilachten und Kantenschutz mit
  der nächstliegenden Vorlage), sonst ein Platzhalter (Ja/Nein, Text, Zahl, bei Artikellänge „Länge (m)“) an der
  obersten Kategorie ohne Formular. Echte Formulare bleiben unberührt.
- **Konten** (nur Materialablage, Passwörter nur in der Ausgabe; gibt es ein DEMO-Konto mit der Adresse schon, übernimmt
  der Lauf es nur, wenn es aktiv und freigeschaltet ist und die Stufe seiner Rolle hat – unverändert samt Passwort und
  Rollen, Abweichungen nennt der Bericht; eine offene Kontoanfrage oder ein deaktiviertes Konto mit einer dieser Adressen
  lässt ihn vor jedem Schreiben abbrechen – dann unter Leitstelle → Nutzer ablehnen bzw. selbst einstellen):
  `demo-wart-a@example.invalid` (Materialwart Kreisverband), `demo-wart-b@…` (Nachbarstadt), `demo-pruefer@…` und
  `demo-pruefer-2@…` (dauerhaft lesen und prüfen), `demo-pruefer-ns@…`, `demo-extern@…` (prüfen im Zentrallager, 30
  Tage – befristet sind Prüffreigaben nur für Externe), `demo-mitglied@…` (lesen), `demo-mv@…`
  (DEMO-Material-Verwaltung, Stufe Verwaltung) und `demo-einsatzkraft-01@…` … – die erste liest ihren persönlichen
  Ordner, die übrigen haben keinen Modulzugang und sehen „Meine PSA“ (ein gemeinsames Passwort).

Am Katalog ändert das Skript sonst nichts; erfunden sind nur Bestandsangaben, alle mit „DEMO“. Ein Artikel in einer
DEMO-Gliederung gilt überall als DEMO – Oberfläche, Protokolle, Lebenslauf, CSV und Steckbrief –, auch wenn sein
Produkt aus dem echten Katalog stammt; zwischen DEMO-Gliederungen und echtem Bestand lässt sich nichts verschieben (409).
Mails gehen keine hinaus (auch nicht ins Mailprotokoll). Nur auf dev oder lokal: `BASE_URL` muss gesetzt sein (das
Skript belegt sie nicht vor) und in der Umgebung **und** in der Anwendung die Positivliste von `dev-zuruecksetzen`
erfüllen (Host mit „dev.“ davor oder localhost), dazu die dev-Kennung `STROEMIS_NAME` auf `-dev` (wie bei
`dev-zuruecksetzen`) – ohne sie nur, wenn beide Adressen localhost/127.0.0.1 sind und der Lauf außerhalb des
Containers ist (`DATA_DIR` nicht `/data` – im Produktionscontainer ließe sich die Ausnahme sonst mit
`BASE_URL=http://localhost:8080` erzwingen). Sonst legt das Skript nichts an.

Vorher:

1. **Katalog exportieren** (Katalog → „Katalog exportieren“ oder `material export-catalog`) und das ZIP aufheben – damit
   kommt der Katalog nach dem Zurücksetzen von dev wieder hinein (die Produktion bekommt die Import-ZIPs der
   Katalog-Lieferungen, siehe „Inbetriebnahme in der Produktion“). Der Beispielbestand und seine DEMO-Formulare kommen mit keinem Export mit.
2. Wissen, was danach gilt: Jede benutzte **Formularversion ist „benutzt“** und lässt sich nur noch über eine neue
   Version ändern. Jedes Produkt mit Artikeln lässt sich **nicht mehr löschen und seine Materialart nicht mehr
   ändern**; seine Kategorie lässt sich nicht mehr löschen. Der Bestand lässt sich **nicht entfernen** – zurück geht es
   nur, indem man das Modul auf dev zurücksetzt („Materialablage auf dev zurücksetzen“) und den Export importiert.

Auf dem VPS im Klon der Entwicklung (das Abbild enthält `scripts/` nicht – Skript und Petzl-Datei gehen per tar in das
flüchtige `/tmp` des Containers, die App liegt dort unter `/srv`, die Daten unter `/data`):

```bash
tmux new -s beispielbestand          # oder screen – siehe unten
tar c scripts/material_beispielbestand.py scripts/beispielbestand_petzl_punkte.json | docker exec -i stroemis-dev sh -c 'rm -rf /tmp/bb && mkdir /tmp/bb && tar x -C /tmp/bb && echo $$ > /tmp/bb/pid && export VIDEOPFLEGE=0 PYTHONPATH=/srv && exec python /tmp/bb/scripts/material_beispielbestand.py --beispielbestand'
```

Der Lauf dauert bei 800 Artikeln rund **eine halbe Stunde** (gemessen 28 Minuten neben der laufenden Testsuite, unter
Last länger) – jede Prüfung bekommt ihr Protokoll (gut eine halbe Sekunde je PDF), und nach jedem Vorgang lässt er eine
kurze Pause (0,05 s), damit andere Schreiber dazwischenkommen; er zählt je Monat und Durchgang mit, `--artikel N` für
weniger (60 Artikel: knapp zwei Minuten). **dev ist während des Laufs nur
eingeschränkt benutzbar**: Anmelden und Speichern gehen, können aber einige Sekunden warten – am besten laufen lassen,
wenn niemand auf dev arbeitet. Er endet mit einem Bericht: Konten mit Passwörtern, Mengen, Zustände, angelegte Formulare
mit ihren Quellen, Hinweise auf Gescheitertes. Er läuft nur einmal – gibt es die Gliederungen schon, legt er nichts an.
**Nie in der Produktion** (Container `stroemis`).

**Den Befehl in `tmux` oder `screen` starten** und die **Ausgabe mit den Passwörtern sichern** (aus dem Fenster in den
Passwortmanager – sie werden nirgends gespeichert und nicht erneut angezeigt). Strg-C oder eine abgerissene Verbindung
beenden den Lauf **nicht**: `docker exec -i` hat kein Terminal, das Skript im Container läuft weiter bis zum Ende, nur
seine Ausgabe – mit den Passwörtern – ist dann verloren (Passwörter dann unter Leitstelle → Nutzer neu setzen).
Abbrechen geht nur so (der laufende Vorgang rollt samt Protokolldateien zurück):

```bash
docker exec stroemis-dev sh -c 'kill -TERM "$(cat /tmp/bb/pid)"'
```

Nach einem Abbruch bleibt ein Teilbestand, und kein weiterer Lauf vervollständigt ihn: Er meldet „unvollständig“ mit
Rückgabewert 1 und legt nichts an. Neu geht es dann nur, indem man das Modul auf dev zurücksetzt und danach den
Katalog-Export importiert.

### Materialablage auf dev zurücksetzen (nur dev)

`flask material dev-zuruecksetzen` leert die Materialablage auf dev, um es von null an zu testen: Katalog, Ordner und
Gliederungen, Bestand, Prüfungen samt Protokollen, Durchgänge, Importe, Rückrufe, Anträge, Meldungen, Journal,
Erinnerungslog und Mailfehler-Protokoll (alle Tabellen `mat_*` samt Triggern und Volltextindizes) und die Dateien unter
`media/material` und `pdf/`. **Es bleiben** die Konten (samt Modulstufe, Häkchen „Prüfer“, Urkundennummer, Unterschrift
und PSA-Mails), Strömipedia, Ankerplätze, Riegenkarten und die Einstellungen (Leitstelle → Einstellungen). Vorher sichert der
Befehl die ganze Datenbank (Online-Backup, wie die stündliche Sicherung) und **verschiebt** die Medien des Moduls in
einen Sicherungsordner – scheitert die Sicherung, löscht er nichts. Danach legt er das Schema des Moduls frisch an, wie
eine neue Installation (dieselbe Schemaversion wie ein frischer Start, heute 39), und leert `data/katalog-import/` (Aufträge des Katalogimports im
Hintergrund). Läuft gerade ein Katalogimport, bricht er vorher ab (Rückgabewert 1, nichts geändert); während des Laufs
bekommt ein Import-Start „läuft schon“. Wer den Katalog behalten will: vorher Katalog → „Katalog exportieren“, danach
importieren.

Er wirkt nur, wenn `STROEMIS_NAME` auf `-dev` endet (setzt `dev-einrichten.sh`, dieselbe Regel wie die Sperre der
Erinnerungsmails), `BASE_URL` in der `.env` **und** unter Leitstelle → Einstellungen auf eine Adresse der Entwicklung
zeigt – der Host beginnt mit `dev.` (etwa `https://dev.strömis.de`) oder ist `localhost`/`127.0.0.1` – und
`--ja-alles-loeschen` dabeisteht. Jede andere, leere oder unlesbare `BASE_URL` sperrt, auch jede Schreibweise von
`strömis.de` (ohne Schema, mit Leerzeichen, in Punycode, mit zerlegtem „ö“ oder ideographischem Punkt). Sonst
Rückgabewert 2, nichts geändert. In der Produktion (Container `stroemis`) lehnt er also auch mit Schalter ab.

Auf dem VPS im Klon der Entwicklung (`dev-einrichten.sh` legt ihn neben die Produktion, Ordnername mit `-dev`; Container
`stroemis-dev` laut `.env` – `docker compose` erreicht ihn dort über den Dienst `stroemis`):

```bash
cd /pfad/zur/produktion-dev
# 1. Ansehen, was geschähe: Tabellen mit Zeilen, Medien mit Größe, Sicherungsordner, DEMO-Konten – ändert nichts
docker compose exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material dev-zuruecksetzen --trocken
# 2. Sichern und zurücksetzen
docker compose exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material dev-zuruecksetzen --ja-alles-loeschen
# 3. Neu starten
docker compose restart
```

Die Ausgabe nennt den Sicherungsordner (`/data/sicherung-material-JJJJ-MM-TT_hhmmss` im Container, also
`data/sicherung-material-…` im Klon), die Zahl der geleerten Tabellen und Zeilen, die verschobenen Medien und die
DEMO-Konten. Rückgabewert 0 = zurückgesetzt; 1 = die Sicherung oder ein späterer Schritt ist gescheitert – dann ist
nichts geändert (Datenbank unverändert, Medien zurück an ihrem Platz; die Meldung sagt es); 2 = nicht dev oder ohne
Schalter. Der Server darf dabei laufen: Der Befehl hält während Sicherung und Umbau die Schreibsperre der Datenbank
(Schreibzugriffe warten so lange); der Neustart danach räumt auf, was die Arbeitsprozesse noch im Speicher halten.
**Während des Laufs (wenige Sekunden) nicht auf `dev` pushen und den Container nicht neu starten.** Ein `docker compose
stop/restart` oder Deploy (SIGTERM) bricht sauber ab – Datenbank unverändert, Medien zurück, Rückgabewert 1. Nur wenn der
Prozess hart beendet wird (SIGKILL), bleiben die Medien im Sicherungsordner liegen; dessen `LIESMICH.txt` steht dann mit
„LAUF UNVOLLSTÄNDIG“ da und nennt die `mv`-Zeilen, die sie zurückbringen (die Datenbank ist auch dann unverändert).

- **Sicherung löschen**: Die Sicherung ist eine Kopie der **ganzen** Datenbank – alle Konten mit E-Mail,
  Passwort-Hash, Urkundennummer und Unterschrift, dazu Wiki und Prüfungen. Ein Konto, das danach auf dev gelöscht wird,
  bleibt in ihr stehen. Deshalb **löschen, sobald der Neustart und ein erster Test geklappt haben, spätestens nach
  einer Woche**: `rm -rf data/sicherung-material-…` (Befehl und Ordnername stehen in der Ausgabe und in `LIESMICH.txt`;
  ggf. mit `sudo`). Der Ordner ist nur für seinen Besitzer lesbar (0700, Kopie 0600). Jeder Lauf und jeder Probelauf
  nennt die älteren Sicherungen mit Datum und Größe.
- **Platz**: Die Kopie der Datenbank braucht einmal deren Größe (der Probelauf nennt Größe und freien Platz); die Medien
  werden nur umbenannt, nicht kopiert.
- **DEMO-Konten** (`@example.invalid`) löscht der Befehl nicht, er listet sie. Sie haben danach keine Freigaben mehr;
  über die Leitstelle löschen, falls nicht mehr gebraucht. Der Beispielbestand (nach dem Katalog-Import) übernimmt
  vorhandene DEMO-Konten samt Passwort, gibt ihnen ihre Freigaben neu und legt nur fehlende an.
- **Rückweg** (der ganze Stand vor dem Zurücksetzen; was seither auf dev entstand – auch an Konten, Strömipedia,
  Ankerplätzen und Riegenkarten –, geht verloren). Dieselben Zeilen mit dem richtigen Ordnernamen stehen in `LIESMICH.txt` im
  Sicherungsordner. Gehört `data/` nicht deinem Nutzer, `rm`, `cp` und `mv` mit `sudo`:

  ```bash
  cd /pfad/zur/produktion-dev
  S=data/sicherung-material-2026-10-23_174512      # der Ordner aus der Ausgabe
  docker compose stop
  rm -f data/stroemis.db-wal data/stroemis.db-shm
  cp "$S/stroemis.db" data/stroemis.db
  rm -rf data/media/material data/pdf
  mv "$S/media/material" data/media/material
  mv "$S/pdf" data/pdf
  sudo chown -R 1000:1000 data
  docker compose up -d
  ```

  (Lag vor dem Zurücksetzen unter `data/pdf` oder `data/media/material` nichts, fehlt der Ordner auch in der Sicherung –
  dann diese `mv`-Zeile weglassen.)

### Erinnerungsmails (Materialablage)

Die Anwendung verschickt die Erinnerungsmails selbst – ohne Cron und ohne Handgriff auf dem VPS: Jeder
Arbeitsprozess startet mit der ersten Anfrage einen Hintergrundlauf, der alle 15 Minuten aufwacht und **einmal am Tag
ab 6 Uhr deutscher Zeit** arbeitet. Dass zwei Arbeitsprozesse, ein Neustart oder die Kommandozeile nie doppelt mahnen,
regeln Tagesmarken in der Datenbank und das Erinnerungslog – außer, wenn ein Prozess genau zwischen der Annahme einer
Mail und ihrem Vermerk endet (etwa beim Neustart nach einem Deploy kurz nach 6 Uhr); dann kommt diese eine Mail am
nächsten Morgen noch einmal. Ausgefallene Tage holt der nächste Lauf nach (mit der höchsten erreichten Stufe).

- **Einschalten in der Produktion im Browser**: Leitstelle → Einstellungen → Materialablage → „Erinnerungsmails
  verschicken“. Die **Vorgabe ist aus**. Nicht in der `.env` einschalten – die Entwicklung kopiert sie. Nach dem
  Einschalten kommen die ersten Mails binnen 15 Minuten, danach jeden Morgen. Der erste Lauf schickt den Rückstand:
  alles, was schon in einem Fenster liegt, einmal.
- **Aus** heißt: keine Mails, kein Log. Der tägliche Pflegeteil läuft trotzdem – Journaleintrag „Freigabe
  abgelaufen“, Löschen des Erinnerungslogs nach 13 Monaten, Kürzen des Protokolls der globalen Suche und des
  Mailfehler-Protokolls (13 Monate, erledigte Zeilen 3 Monate).
- **Ohne `SMTP_HOST`** wird nichts versucht; die Übersicht sagt dann „kein Mailserver eingerichtet“.
- **Stand und Probelauf**: Materialablage → Übersicht, ganz unten (nur Material- und Plattform-Verwaltung): an/aus/gesperrt,
  letzter Lauf mit Uhrzeit, Zahl der Mails und Fehlschläge, dazu der Textlink „Probelauf ansehen“ – er zeigt je
  Empfänger Betreff und Text des nächsten Laufs (heute, oder morgen, wenn heute schon verschickt wurde) und nennt
  Ordner mit „Erinnerungen aus“. Er verschickt und vermerkt nichts. Steht der Lauf (nach 7 Uhr noch keiner), ist eine
  Mail gescheitert oder gab es einen Fehler, steht das zusätzlich gelb oben auf der Übersicht. Eine gescheiterte Mail
  geht am nächsten Morgen erneut.
- **DEMO-Bestand im Probelauf ansehen** (für dev, wo alles DEMO ist): Hat der Probelauf DEMO ausgelassen, bietet er das
  Kästchen „DEMO-Bestand einbeziehen (nur Ansicht)“. Mit Haken zählen DEMO-Artikel, DEMO-Freigaben und DEMO-Konten
  wie echte; solche Mails tragen die Marke „DEMO“, „DEMO – geht nie hinaus“ und „[DEMO]“ im Betreff. Der echte Lauf
  lässt DEMO immer aus – eine Mail mit DEMO lässt sich weder verschicken noch vermerken.
- **Kommandozeile** (im Container; `VIDEOPFLEGE=0` hält den Videolauf aus dem kurzen Prozess heraus):

  ```bash
  # Probelauf: zeigt die Mails des nächsten Laufs mit Adressen, verschickt und schreibt nichts – geht auch bei „aus“
  docker exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material remind --trocken
  # Probelauf für einen bestimmten Tag (Fälligkeiten dieses Tages, Rechte von heute)
  docker exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material remind --trocken --stichtag 2026-11-01
  # Probelauf mit DEMO-Bestand (nur Ansicht, etwa auf dev) – --demo geht nur zusammen mit --trocken
  docker exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material remind --trocken --demo
  # Echter Lauf jetzt (nur bei eingeschaltetem Versand und mit Mailserver); --erneut schickt am selben Tag noch einmal,
  # was nicht im Log steht
  docker exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material remind
  ```

  Rückgabewert 0 = in Ordnung, 1 = eine Mail ist gescheitert oder ein Fehler steht im Stand, 2 = Versand aus,
  gesperrt, kein Mailserver oder falscher Aufruf (`--stichtag` oder `--demo` ohne `--trocken`, unlesbares Datum). Ein
  Cron auf dem Host ist nicht nötig; einer mit `remind` mahnte trotzdem nicht doppelt.
- **Die Entwicklung bleibt still**: `MATERIAL_ERINNERUNGEN_SPERRE` (nur in der `.env`, kein Wert im Browser übersteuert
  sie) sperrt den Versand. Ohne Eintrag greift sie, wenn `STROEMIS_NAME` auf `-dev` endet – das setzt
  `dev-einrichten.sh`, die bestehende Entwicklung ist also ohne Handgriff gesperrt; künftige Einrichtungen tragen
  `MATERIAL_ERINNERUNGEN_SPERRE=1` zusätzlich ausdrücklich ein. Die Übersicht auf dev zeigt „in dieser Umgebung
  gesperrt“; der Probelauf geht trotzdem, mit dem Kästchen „DEMO-Bestand einbeziehen“ auch für den DEMO-Bestand. Wer
  auf dev bewusst Mails ausprobieren will, setzt `MATERIAL_ERINNERUNGEN_SPERRE=0` (DEMO-Konten bekommen auch dann
  nichts).
- **Datenbank der Produktion auf dev einspielen**: Die Sperre schützt vor Mails. Damit auch die übrigen Einstellungen
  der Produktion (Mailserver, `BASE_URL`) nicht gelten, dort `EINSTELLUNGEN_AUS=1` setzen.
- **Je Ordner abschalten**: Ordner → Bearbeiten → Reiter „Ordner“ → „Erinnerungsmails aus“ (nur wer den Ordner
  verwaltet; gilt für alle Unterordner, steht im Journal). Ablaufende Freigaben melden sich weiter, ebenso „Deine PSA“ an
  die Personen, denen dort etwas zugeordnet ist – dafür zählt nur ihr eigener Haken im Profil (Entscheidung E2 B vom
  26.10.2026; bis dahin fiel der Abschnitt mit dem Ordner weg).

## Konfiguration

Beim ersten Start richtet `.env` die Anlage ein (Vorlage: `.env.example`). Danach lässt sich
fast alles davon **im Browser** ändern: **Leitstelle → Einstellungen**. Jedes Feld zeigt dort,
woher sein geltender Wert kommt – hier gesetzt, aus der `.env` oder eingebaute Vorgabe – und
lässt sich einzeln zurücksetzen.

In der Leitstelle heißt die `.env` „Grundeinstellung auf dem Server“: Die Marke an jedem Feld sagt „hier gesetzt“,
„Grundeinstellung“ (aus der `.env`) oder „Vorgabe“; den Namen der Variablen zeigt ihr Tooltip, die Tabelle unten nennt alle.
Die Felder stehen je Gruppe (Seite, Riegenkarten, Materialablage, E-Mail, Ankerplätze, Grenzen, Sicherheit) in einem
zugeklappten Abschnitt.

Ein im Browser gesetzter Wert hat **Vorrang** vor der `.env`. Andernfalls ließe sich etwas
einstellen, ohne dass es wirkt, und der Grund stünde in einer Datei auf dem Server. Die Werte
liegen in der Datenbank und gelten sofort in allen Arbeitsprozessen; ein Neustart ist für keine
Einstellung nötig.

Nur in der `.env` einstellbar bleiben `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DATA_DIR`,
`VIDEOPFLEGE` und `MATERIAL_ERINNERUNGEN_SPERRE`. Das Mailkennwort wird gespeichert, aber nie wieder ausgeliefert – auch nicht
an die Plattform-Verwaltung.

> **Notausgang:** Hat eine Einstellung die Anwendung unbedienbar gemacht – der klassische Fall
> ist `COOKIE_SECURE` an, während der Zugriff über einfaches HTTP läuft –, käme niemand mehr an
> die Oberfläche, um sie zurückzunehmen. Dafür gibt es `EINSTELLUNGEN_AUS=1`: Damit gilt wieder
> allein die `.env`, die gespeicherten Werte bleiben erhalten.

| Variable | Bedeutung |
| --- | --- |
| `BASE_URL` | Öffentliche Adresse, wird in E-Mail-Links verwendet |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Erstes Konto mit Verwaltungsrecht, wird beim Start angelegt |
| `SECRET_KEY` | Sitzungsschlüssel; leer = wird erzeugt und unter `/data/secret_key` gespeichert |
| `ALLOW_REGISTRATION` | Selbstregistrierung erlauben (`true`/`false`) |
| `COOKIE_SECURE` | Cookies nur über HTTPS (`true` im Produktivbetrieb) |
| `MAX_UPLOAD_MB` | Obergrenze je Hochladevorgang (Standard 5120 = 5 GB) |
| `MAX_REQUEST_MB` | Obergrenze einer gewöhnlichen Anfrage ohne Upload (Standard 1) – begrenzt auch die Länge einer Wiki-Seite. Gilt auch am Datenstrom; Anfragen ohne `Content-Length` (chunked) werden mit 411 abgewiesen |
| `SITE_NAME` | Name der Anwendung in Betreffzeilen und Absendern |
| `PUBLIC_HOST`, `PUBLIC_URL` | Subdomain und Adresse der früheren öffentlichen Strömipedia (seit 01.11.2026 nur Einstieg zur Anmeldung) |
| `KONTAKT_EMAIL` | Kontaktadresse für Fragen und Anliegen (Vorgabe `verwalter@stroemis.de`): im Fuß jeder Seite – angemeldet, Anmeldung, Fehlerseiten – und im Satz vor dem Bestandsimport der Materialablage. Leer gesetzt: Die Angabe entfällt; keine gültige Adresse: Warnung im Log, es gilt die Vorgabe. Auch unter „Leitstelle → Einstellungen“ (Gruppe „Seite“, „Kontaktadresse“) – dort lehnt Speichern eine ungültige Adresse ab |
| `FEHLER_EMAIL` | Adresse für Fehler und Verbesserungsvorschläge (Vorgabe `bugs@stroemis.de`): im Fuß jeder Seite und im Hinweis „Entwicklungsserver“ auf dev (Betreff „strömis.de dev: “). Leer: Die Angabe entfällt, der Hinweis bleibt ohne den Satz. Sonst wie `KONTAKT_EMAIL` („Adresse für Fehlermeldungen“) |
| `ADMIN_NOTIFY_EMAIL` | Empfänger für Kontoanfragen (leer = das dienstälteste Konto mit Plattform-Verwaltung; es geht bewusst genau eine Mail hinaus, damit die Antwortzeit nicht verrät, ob eine Adresse schon ein Konto hat – die übrigen sehen die Anfrage unter „Leitstelle → Nutzer“) |
| `LOGIN_SLIDESHOW` | Slideshow auf der Anmeldeseite (`true`/`false`) |
| `SMTP_*`, `MAIL_FROM` | Mailversand für Passwort-Reset; ohne `SMTP_HOST` steht der Link im Container-Log (`docker compose logs`) |
| `SMTP_ENVELOPE_FROM` | Absender des Umschlags (Return-Path). Leer = die Adresse aus `MAIL_FROM`; gegen sie prüft der Empfänger SPF (siehe „Damit Mails ankommen“) |
| `WIKI_MAX_REVISIONS` | Fassungen je Wiki-Seite im Verlauf (Standard 100, `0` = alle behalten) |
| `WIKI_IMPORT_MB` | Obergrenze eines Wiki-Imports als ZIP (Standard 200) |
| `MAP_CENTER`, `MAP_ZOOM`, `TILE_URL`, `TOPO_URL`, `SAT_URL` | Kartenstart und Kachelquellen; `SAT_URL` ist das Luftbild und die Startansicht (leer = nur Straßenkarte) |
| `SAT_LABELS_URL` | Beschriftungsebenen über dem Luftbild (Straßen, Orts- und Gewässernamen), mehrere durch Komma; leer = keine |
| `TILE_ATTRIBUTION`, `TOPO_ATTRIBUTION`, `SAT_ATTRIBUTION` | Rechtehinweise unter der Karte (leer = Vorgaben von OSM, OpenTopoMap und Esri) |
| `MATERIAL_BALD_FAELLIG_TAGE` | Materialablage: so viele Tage vor der nächsten Prüfung gilt ein Artikel als „bald fällig“ (Standard 30, erlaubt eine ganze Zahl von 0 bis 365; ein anderer Wert in der `.env` – etwa `abc` oder `1000` – gilt nicht: Die App startet trotzdem, schreibt eine Warnung ins Log und nimmt die Vorgabe 30, und die Leitstelle zeigt 30 als Vorgabe. Auch unter „Leitstelle → Einstellungen“ – dort lehnt Speichern andere Werte ab, und ein unbrauchbarer gespeicherter Wert gilt nicht: dann wirkt und erscheint der Wert aus `.env` bzw. Vorgabe, in jedem Arbeitsprozess gleich) |
| `MATERIAL_ERINNERUNGEN` | Materialablage: Erinnerungsmails verschicken (`true`/`false`, Standard `false`). Im Browser einschalten (Leitstelle → Einstellungen), nicht hier – die Entwicklung kopiert die `.env` |
| `MATERIAL_ERINNERUNGEN_SPERRE` | `1` sperrt die Erinnerungsmails hart, `0` hebt die Sperre auf; ohne Eintrag gesperrt, wenn `STROEMIS_NAME` auf `-dev` endet. Nur in der `.env` – kein Wert im Browser übersteuert sie |
| `VIDEOPFLEGE` | `0` schaltet den Hintergrundlauf ab, der nach dem Start Bestandsvideos nach H.264 wandelt (Standard: an) |
| `EINSTELLUNGEN_AUS` | `1` setzt alle im Browser gespeicherten Werte außer Kraft – dann gilt allein diese Datei |
| `GEOCODE_URL` | Adresssuche beim Platzieren von Bildern (leer = abgeschaltet). Die öffentliche Nominatim-Adresse erlaubt eine Anfrage je Sekunde; wer viel sucht, betreibt eine eigene. |

Ohne `ADMIN_EMAIL`/`ADMIN_PASSWORD` bekommt der erste Nutzer, der ein Konto anfragt, sofort überall Verwaltungsrecht. Ohne SMTP werden Kontoanfragen nicht per Mail gemeldet – offene Anfragen stehen aber immer oben unter „Nutzer“.

## Wie die Anwendung abgesichert ist

- **Anmeldung:** Sitzungs-Cookie (HttpOnly, SameSite=Lax, mit `COOKIE_SECURE` nur über HTTPS), Passwörter als Werkzeug-Hash. Schreibende API-Aufrufe verlangen `Sec-Fetch-Site: same-origin` und einen JSON-Body oder `X-Requested-With` – ein Formular von einer fremden Seite erfüllt das nicht.
- **Passwort-Reset:** Der Link trägt den Token hinter `#`. Fragmente schickt der Browser nicht an den Server, der Token steht also weder im Zugriffsprotokoll noch im Referer. Das Protokoll von Gunicorn führt ohnehin nur den Pfad, nicht die Abfrage. Ein Token wird ungültig, sobald das Passwort geändert wurde; gesperrte und noch nicht freigegebene Konten weist der Reset ab.
- **Kontoanfragen** antworten immer gleich, auch wenn es die Adresse schon gibt – von außen ist nicht zu erkennen, wer hier ein Konto hat. Der Inhaber bekommt stattdessen eine Hinweismail.
- **Medien:** Bilder und Videos hinter der Anmeldung werden als `Cache-Control: private` ausgeliefert, landen also in keinem gemeinsamen Zwischenspeicher. Alle Mediendateien bekommen eine eigene, sehr enge CSP – auch ein direkt aufgerufenes SVG kann damit nichts ausführen.
- **Sitzungsschlüssel:** wird beim ersten Start exklusiv angelegt, damit nicht zwei Gunicorn-Worker mit verschiedenen Schlüsseln starten (das äußerte sich sonst in sporadischen Abmeldungen).
- **JavaScript-Bibliotheken** werden beim Bauen gegen `vendor.sha256` geprüft. Nach einem Versionswechsel im Dockerfile die Prüfsummen neu erzeugen (Anleitung steht in der Datei).
- **Wiki-Inhalte** werden im Browser gerendert und mit DOMPurify bereinigt; Seiten liefern eine CSP mit Nonce, kein `unsafe-inline` für Skripte. Das `style`-Attribut wird aus Inhalten entfernt (sonst ließe sich die Oberfläche aller Leser überlagern), ebenso Formulare, Rahmen und ids, die die Oberfläche selbst benutzt. Der Editor bekommt dieselbe Reinigung als Option mit; was er speichert, läuft beim Anzeigen in jedem Fall erneut durch sie – der Schutz der Leser hängt nicht am Editor. Bilder dürfen nur vom eigenen Server und von den eingestellten Kachelservern kommen – ein Bild von einer fremden Adresse meldete dieser sonst jeden Aufruf. Externe Bilder in Seiten bitte hochladen statt verlinken.
- **Editor und Browserspeicher:** Wer den Editor verlässt, während eine Speicherung läuft, verliert nichts – der letzte Stand wird nach deren Antwort nachgesendet, und der Browser-Entwurf bleibt, bis sein Inhalt gesichert ist. Beim Abmelden werden Entwürfe und Prüfungsdaten aus dem Browserspeicher entfernt. Eingebaute Abschnitte und das Live-Nachziehen lesen Seiten mit `?leise=1`, zählen also nicht als Besuch.
- **Anfragegrößen:** Jede Route hat ihre Grenze (1 MB normal, 8 MB Profilbild, 25 MB Excel-Import, 200 MB Wiki-Import `WIKI_IMPORT_MB`, `MAX_UPLOAD_MB` für Filme), und sie gilt am Datenstrom; eine Anfrage ohne `Content-Length` (chunked) wird mit 411 abgewiesen. Zwischendateien großer Uploads und der ZIP-Export liegen unter `/data/tmp`, nicht im Container.
- **Sitzungen** sind an den Passwortstand gebunden: Wer sein Passwort ändert oder zurücksetzt, meldet damit alle anderen Browser ab. „Passwort vergessen“ ist je Absender und je Adresse gebremst, der Versand läuft im Hintergrund (die Antwortzeit verrät nicht, ob es das Konto gibt).
- **Verschieben (Strömipedia):** Elternseite oder Stelle im Baum ändert nur, wer die Seite auch in den Papierkorb legen darf – ihr Ersteller ab Redakteur oder die Wiki-Verwaltung (Entscheidung des Nutzers vom 01.11.2026). Eine Bearbeitungsfreigabe reicht zum Bearbeiten, nicht zum Umhängen: Sonst ließe sich eine fremde Seite unter eine eigene lesebeschränkte hängen und wäre für alle anderen verschwunden. Gilt für `PUT /api/wiki/pages/<id>` (`parent_id`, `position`) und `PUT /api/wiki/reorder` (Einträge, die Elternseite und Stelle behalten, bleiben unberührt); der Seitenbaum lässt nur solche Seiten ziehen und nur dorthin ablegen, wo es der Server annimmt.
- **Abmelden und „Zurück“:** Kommt eine angemeldete Seite aus dem Seitenspeicher des Browsers zurück (bfcache), fragt sie `/api/me` und lädt neu, wenn die Sitzung nicht mehr diesem Konto gehört oder niemand antwortet – nach dem Abmelden zeigt „Zurück“ so die Anmeldung statt der zuletzt gelesenen Seite. Der Speicherstand einer offenen Prüfung (Materialablage, `sessionStorage`) trägt die Kontokennung im Schlüssel.
- **Lesebeschränkte Abschnitte:** Herausverschieben darf nur, wer die Beschränkung aufheben dürfte (Ersteller des Abschnitts oder Wiki-Verwaltung); Fehlermeldungen nennen keine Titel fremder Seiten; unter eine Seite hängen kann nur, wer sie lesen darf. In den Papierkorb legen oder endgültig löschen kann ein Redakteur nur eigene Seiten und nur Teilbäume ohne Seiten anderer Ersteller; ein Mitglied löscht keine Seiten, die Wiki-Verwaltung jede (`can_delete`).
- **Wiki-Import (ZIP):** nur die Wiki-Verwaltung (Mitglied 403, bevor die Datei gelesen wird). Geprüft wird vor dem Entpacken: Zahl der Einträge (höchstens 2000) und Größe des Inhaltsverzeichnisses (512 KB) aus dem Ende-Satz, keine doppelten Namen, nichts verschlüsselt, entpackt höchstens 1 GB, je Eintrag ab 1 MB ein Packverhältnis bis 100:1; gelesen wird nie mehr als die angegebene Größe. Pfade nur relativ – `..`, führender Schrägstrich, Rückstrich, Laufwerk, Steuerzeichen, symbolische Verweise und mehr als 20 Ebenen brechen ab; `__MACOSX/`, versteckte Dateien und `Thumbs.db` werden still übergangen. Seiten je höchstens `MAX_REQUEST_MB` (wie im Editor), zusammen höchstens 64 MB, UTF-8 ohne Nullzeichen. Anhänge gehen durch dieselbe Ablage wie beim Hochladen (Endung, Pixelgrenze, Bilder neu geschrieben); Videos nimmt der Import nicht mit. Geschrieben wird in einer Transaktion; scheitert sie, löscht der Import die schon abgelegten Dateien.
- **HTML-Bausteine** stellt nur die Wiki-Verwaltung ein – die Endung wird dafür genauso bestimmt wie bei der Ablage, auch wenn der Browser statt eines Dateinamens nur einen Inhaltstyp mitschickt.
- **Videos:** ffmpeg arbeitet nur mit lokalen Dateien (`-protocol_whitelist`), entfernt beim Wandeln und beim Umpacken die Begleitangaben (Aufnahmeort vom Telefon) und läuft je Arbeitsprozess nur einmal zugleich. Der ZIP-Export packt jede Datei einmal, auf Platte, bis 2 GB.
- **Aufräumen:** Nach dem Start entfernt der Hintergrundlauf Artikeldateien unter `media/wiki`, die seit einer Woche weder eine Seite noch eine Fassung im Verlauf nennt (Uploads ohne Speichern, alte Zuschnitte, Anhänge endgültig gelöschter Seiten, abgebrochene Umwandlungen).
- **Anmeldeseite:** Die Slideshow zeigt je Tag dieselbe Auswahl, nicht bei jedem Aufruf andere Bilder – sonst ließe sich der Bestand ohne Anmeldung einsammeln.
- **Protokolle (Materialablage):** Festgeschriebene Prüfungen, Aussonderungen und Durchgänge ändert auch die Datenbank nicht mehr (Trigger); die PDF-Dateien liegen schreibgeschützt unter `/data/pdf` und werden nur ausgeliefert, wenn ihre Prüfsumme noch stimmt. WeasyPrint lädt beim Rendern nichts aus dem Netz und keine fremden Dateien – nur die eigenen Schriften; Bilder kommen eingebettet. Die öffentliche Seite „Echtheit prüfen“ `/materialablage/pruefen` speichert nichts, nennt keine Personendaten und ist je Adresse auf 20 Prüfungen in 15 Minuten und 200 MB je Datei gebremst.
- **Trennung je Gliederung (Materialablage):** Rechte am Bestand gibt es für Mitglieder nur über Freigaben je Ordner (alle Bestände sieht nur die Material-Verwaltung); der Server prüft sie bei jeder Anfrage, und ohne Stufe im Modul wirkt keine. `tests/test_material_stufen.py` ruft jede Route des Moduls mit einem Konto auf, das Freigaben, aber keine Stufe hat (403 vor jeder Frage nach dem Gegenstand). Was ein Konto nicht sieht, antwortet wie etwas, das es nicht gibt – 404 mit derselben Meldung, ob die Kennung im Pfad oder im Inhalt der Anfrage steht; 403 nur, wenn man den Gegenstand sieht, die Aktion aber nicht darf. Listen, Zählungen, Suche, Exporte, Rückrufe und Meldungen filtert der Server, nicht die Oberfläche. Mediendateien prüft er je Datei (Ordnerfoto am Ordner, Befundfoto und Prüfanhang am Artikel, Meldungsfoto an der Meldung; Produktbilder und Herstellerdokumente für alle mit Zugang). Die globale Seriennummernsuche, der Steckbrief nach einem QR-Scan und die Meldung „gibt es schon in einem Bereich, den du nicht siehst“ beim Anlegen stehen jedes Mal zwölf Monate mit Namen im Protokoll – ungebremst, die Kontrolle ist dieses Protokoll; gesucht wird nur nach der ganzen Herstellerseriennummer, nach ausdrücklicher Bestätigung und nur unter dem, was man nicht sieht. Die Personensuche für Freigaben und Zuordnung zeigt ab drei Zeichen nur Name, Gliederung und ob jemand Prüfer ist – keine E-Mail. `tests/test_material_trennung.py` ruft jede Route des Moduls mit Kennungen einer fremden Gliederung auf und sucht deren Merkmale in allen Antworten.
- **Export und Katalogaustausch (Materialablage):** Exporte gibt es nur mit lesen oder verwalten am Ordner (Freigaben je Ordner); Werte, die eine Tabellenkalkulation als Formel läse (`=`, `+`, `-`, `@` am Anfang), stehen in der CSV mit vorangestelltem `'`. Das Protokoll-ZIP gibt nur Dateien heraus, deren Prüfsumme noch stimmt, und entsteht als Zwischendatei unter `/data/tmp` (höchstens 2 GB). Den Katalog exportieren und importieren nur die Material-Verwaltung. Der Import liest aus dem ZIP nur die Einträge, auf die `katalog.json` verweist (keine absoluten Pfade, kein `..`, keine doppelten Namen), prüft Zahl, Größe und Packverhältnis der Einträge vor dem Lesen und lässt Bilder und Dokumente durch dieselben Prüfungen wie beim Hochladen (Endung, Inhalt, Größe, Pixel); ein Fehler irgendwo speichert nichts.
- **Übungssperre (Einführung):** Eine Übung läuft ganz im Browser – die Schicht in `einfuehrung.js` beantwortet jede Anfrage der Seite aus dem Übungsbestand. Zweite Absicherung auf dem Server (`einfuehrung.sperre`, erster Schritt von `csrf_guard`): Eine Übungsanfrage – Kopfzeile `X-Uebung: 1` oder ein Referer derselben Herkunft mit `uebung=` im Abfrageteil (so auch Bilder, Beacons, Datei-Links und neue Fenster) – bekommt an `/api/` und `/media/` (auch lesend), mit jeder schreibenden Methode und an jede Datei (Endung, `…/pdf`, `…/sammelprotokoll`) 403 „In der Übung gesperrt – es wird nichts gespeichert.“. Durch gehen nur der Merker (`/api/einfuehrung/…`), `GET /api/me`, Abmelden (`POST /api/auth/logout`, ändert nur die Sitzung), `/static/` und Seitenaufrufe. Seiten gibt es in der Übung nur mit Übungszweig (`einfuehrung.UEBUNGSSEITEN`): Jeder andere Seitenaufruf mit `uebung=` – oder aus einer Übungsseite heraus unter einem Modulpfad (Meine PSA, Echtheit prüfen, Bericht, Bestandsimport, Druck der Riegenkarten …) – bekommt vor der Route die Fehlerseite „In der Übung nicht verfügbar“ (403) mit „Zurück zur Übung“; die Kopfleiste führt ohne Referer hinaus. Eine Übungsseite hat eine engere CSP: Bilder, Medien und Rahmen nur aus `/static/` (dazu `data:`, `blob:`, Kartenkacheln), Verbindungen nur zu den Ausnahmen, `default-src 'none'` (kein Prefetch) mit `manifest-src 'self'`, Worker nur der Service Worker (`worker-src …/sw.js`) – so erreicht auch ein Element mit `referrerpolicy="no-referrer"` `/api/` und `/media/` nicht; dazu `Cache-Control: no-store`. Einzige Ausnahme unter `/media/`: Aus der Übung der Materialablage laden die Produktbilder der Katalogauswahl (`einfuehrung.katalog_bilder`, Web- und Vorschaufassung) – nur mit GET, nur genau diese Dateien, in Sperre und `img-src` der CSP gleich; die Medienroute prüft danach wie immer Anmeldung und Modulzugang. Die Schicht hält auch Downloads (`<a download>`, auch losgelöst) an. Alte Adressen leiten aus der Übung mit der Kennung weiter (`einfuehrung.mit_kennung`, ohne Zwischenspeicher). Eine Übung gilt nur, wenn ihr Teil für das Konto gilt – die Stufe in der Übung ist nie höher als die echte. `tests/test_einfuehrung.py` ruft jede Regel unter `/api/` mit jeder Methode und jede Seitenregel der Module mit `uebung=` auf und prüft, dass sich die Datenbank nicht ändert.

## Damit Mails ankommen

Die Anwendung verschickt nur wenige, dafür wichtige Mails: Passwort-Reset, Kontofreigabe,
Benachrichtigung an Beobachter. Ob sie ankommen, entscheidet nicht die Anwendung, sondern das
DNS der Absenderdomain. Empfänger prüfen drei Dinge:

- **SPF** – ein TXT-Eintrag auf der Domain, der sagt, welche Server für sie versenden dürfen.
  Fehlt er, gilt jede Mail als ungedeckt.
- **DKIM** – eine Signatur, die der versendende Mailserver anbringt. Sie entsteht nur, wenn die
  Mail über genau diesen Server hinausgeht.
- **DMARC** – die Ansage, was bei Misserfolg geschehen soll. `p=reject` heißt: wegwerfen. Es
  genügt, wenn SPF **oder** DKIM passt, aber die geprüfte Domain muss zu der in `MAIL_FROM`
  gehören – dafür sorgt der Umschlagabsender (`SMTP_ENVELOPE_FROM`, leer = wie `MAIL_FROM`).

Die Anwendung tut, was von ihrer Seite möglich ist: `Message-ID` und `Auto-Submitted` in jeder
Mail, der Anzeigename als ein sauber kodiertes Wort, und die Antwort des Mailservers landet im
Log statt im Nichts. **Testmail senden** in der Verwaltung verschickt eine Probemail und
zeigt wörtlich, was der Mailserver dazu sagt – Verbindung, Anmeldung, abgewiesener Empfänger.

### Wenn Mails trotzdem im Spam landen

In der Reihenfolge, in der es sich lohnt:

1. **Die Absenderdomain.** Sie wiegt schwerer als alles andere. Exotische Endungen (`.tech`,
   `.xyz`, `.top`) werden von manchen Empfängern pauschal abgewiesen – die DLRG-Server tun
   genau das (`550 5.7.1 Absender-TLD nicht erlaubt`). Eine `.de`-Domain, die zur Seite gehört,
   löst dieses Problem vollständig und ist durch nichts zu ersetzen.
2. **SPF, DKIM und DMARC vollständig** auf ebendieser Domain. Alle drei, nicht zwei davon.
   Bei DMARC mit `p=none` anfangen und die Berichte lesen, bevor auf `quarantine` oder
   `reject` gestellt wird.
3. **Ausrichtung.** Die Domain im Umschlagabsender muss zu der in `MAIL_FROM` passen, sonst
   scheitert DMARC trotz gültigem SPF. Beides steht unter Leitstelle → Einstellungen → E-Mail.
4. **Rückwärtsauflösung (PTR)** der versendenden IP auf einen Namen der Domain, und dieser
   Name wieder auf die IP. Fehlt sie, stuft fast jeder Empfänger herab.
5. **Ein bedienter Posteingang** hinter der Absenderadresse. `noreply@` ist verbreitet und
   wird trotzdem schlechter bewertet als eine Adresse, an die man antworten kann.
6. **Über einen Versanddienst schicken** (Postmark, Brevo, Mailjet, der Mailserver des
   Hosters), statt selbst zuzustellen. Deren Adressbereiche haben einen Ruf, ein einzelner
   Server hat keinen. Bei den meisten heißt das: `SMTP_ENVELOPE_FROM` auf eine Adresse ihrer
   Domain setzen, `MAIL_FROM` bleibt die eigene.
7. **Aufwärmen.** Eine Domain, die jahrelang nichts verschickt hat und plötzlich Mails an
   dieselbe Empfängerdomain schickt, fällt auf. Erst wenige, dann mehr.

Nicht zielführend: den Text umschreiben, Bilder weglassen oder auf Wörter wie „Passwort“
verzichten. Bei transaktionalen Mails entscheidet fast ausschließlich die Absenderdomain.

## Stufe Redakteur (01.11.2026)

Wunsch des Nutzers (28.10.2026, Entscheidungen vom 28.10. und 01.11.2026): In Strömipedia, Ankerplätzen und
Riegenkarten gibt es zwischen Mitglied und Verwaltung die Stufe **Redakteur** – Mitglieder lesen (und bewerten in den
Riegenkarten dort, wo sie eingetragen sind), Redakteure legen eigene Inhalte an, die Verwaltung darf alles. Was jede
Stufe darf, steht oben unter „Rechte-Matrix statt Rollen“ und in der Leitstelle (Hilfe „Rechte je Modul“, Hinweis am
Auswahlfeld). Kurz die Regeln, die nicht offensichtlich sind:

- **Zahlen:** In allen fünf Spalten `users.recht_*` gilt eine Skala: 0 kein Zugriff, 1 Mitglied, 2 Redakteur,
  3 Verwaltung (`auth.py`: `KEIN_ZUGRIFF … VERWALTUNG`, `STUFEN_JE_MODUL`; Oberfläche `S.STUFE` in `common.js`, Vorlagen
  `stufe`). Materialablage kennt 0/1/3, die Leitstelle 0/3 – die Leitstelle lehnt andere Werte mit 400 ab.
  Verwaltung in der Leitstelle zieht alles auf 3.
- **Migration (Schritt 33 der Materialablage):** hebt in jeder Spalte 2 → 3; 0 und 1 bleiben – bestehende Mitglieder
  bleiben Mitglied, niemand wird von selbst Redakteur. Läuft einmal je Schema-Stand (Versionsvermerk, eine
  Transaktion – bricht er ab, steht alles wie vorher); ein zweiter Start ändert nichts. Kein Journal (gleiche
  Bedeutung, neue Zahl); die Beschriftung der Materialablage zeigt 2 (Einträge vor Schritt 33) und 3 als
  „Verwaltung“. Kataloge der Riegenkarten: `created_by` gab es schon; Kataloge ohne Ersteller (Konto gelöscht) pflegt
  nur die Verwaltung.
- **Strömipedia:** Ersteller- und Freigaberechte wirken ab Redakteur. Eine Bearbeitungsfreigabe erlaubt einem Mitglied
  wie einem Redakteur die Seite samt Unterseiten (seit dem 02.11.2026 auf Wunsch des Nutzers; vorher für Mitglieder
  genau diese Seite) – bearbeiten, mit Bildern, nicht verschieben (Elternseite und Stelle ändert nur, wer die Seite in den Papierkorb legen
  darf; Entscheidung vom 01.11.2026). „Bearbeiten erlauben“ bietet nur Konten mit Strömipedia-Stufe an. In einem für
  alle Angemeldeten freigegebenen Abschnitt zeigt der Baum Redakteuren kein „+“, kein „Unterseite anlegen“ und kein
  „Duplizieren“ (`can_create` je Baumzeile und Seite, `can_duplicate` an der Seite). Wird beim Schreiben die Stufe oder
  die Freigabe entzogen, meldet der Editor die Antwort des Servers einmal und hört auf zu speichern; der Text bleibt
  zum Kopieren stehen – beim Speichern (403) wie beim Herzschlag (`POST /api/wiki/praesenz` liefert dafür
  `darf_schreiben`; seit dem 02.11.2026 meldet er nicht mehr „… bearbeitet jetzt“, sondern „keine Berechtigung mehr“). Lesebeschränkte Seiten gelten für Mitglied und Redakteur gleich. Für alle Angemeldeten freigeben,
  HTML-Bausteine, ZIP-Import und Ersteller ändern: nur die Wiki-Verwaltung.
- **Ankerplätze:** Bilder in fremde Alben nur die Verwaltung.
- **Riegenkarten:** Ohne Verwaltung sieht ein Konto nur Lehrgänge, in denen es mit seinem Konto als Ausbilder steht;
  alles andere (Lehrgang, Teilnehmende, Versuche, Medien unter `/media/pruefung/…`, Druckansicht, Mängel, Import
  in den Lehrgang) antwortet 404 wie „gibt es nicht“. Leitung ist die Rolle je Lehrgang – ein Redakteur kann ein
  Mitglied als Leitung eintragen; es pflegt dann diesen Lehrgang (auch Import hinein), kopiert ihn aber nicht
  (Kopieren und Import als neuer Lehrgang ab Redakteur). Ausbilder sind seit dem 01.11.2026 immer Konten (siehe
  „Ausbilder nur mit Konto“).
- **Inbetriebnahme:** siehe „Inbetriebnahme in der Produktion“, Schritt 7 (Redakteure vergeben, Ausbilder verknüpfen).

**Rückweg** auf einen Stand vor Schritt 33 (älterer Code): Er läse Redakteure (2) als Verwaltung – eine
Rechteausweitung. Vor dem Zurückgehen deshalb an der Datenbank (nach einer Sicherung, mit gestoppter App):

```sql
BEGIN;
UPDATE users SET recht_karte = CASE recht_karte WHEN 3 THEN 2 WHEN 2 THEN 1 ELSE recht_karte END,
                 recht_wiki = CASE recht_wiki WHEN 3 THEN 2 WHEN 2 THEN 1 ELSE recht_wiki END,
                 recht_pruefungen = CASE recht_pruefungen WHEN 3 THEN 2 WHEN 2 THEN 1 ELSE recht_pruefungen END,
                 recht_material = CASE recht_material WHEN 3 THEN 2 ELSE recht_material END,
                 recht_verwaltung = CASE recht_verwaltung WHEN 3 THEN 2 ELSE recht_verwaltung END;
UPDATE mat_meta SET wert = '32' WHERE schluessel = 'schema_version';
COMMIT;
```

Redakteure werden dabei Mitglied (sie behalten ihre Inhalte; der ältere Code lässt Mitglieder wieder anlegen). Die
Indizes `idx_pruef_ausbilder_user`, `idx_pruef_medien_file`, `idx_pruef_tn_bild` dürfen bleiben. Das gilt auch ab
Schritt 34 (siehe unten): Die SQL setzt den Stand auf 32, Schritt 34 braucht keinen eigenen Rückweg.

## Ausbilder nur mit Konto (01.11.2026)

Wunsch des Nutzers (01.11.2026): „Entferne die Freitext-Ausbilder in der Riegenkarte, entweder Personen haben einen
Account und mindestens das Recht Mitglied, oder machen keine Lehrgänge.“ Bestätigt mit „ohne Text in der Beschreibung“.

- **Regel:** Ausbilder (Leitung und Referierende) ist ein aktives Konto mit Stufe in den Riegenkarten (mindestens
  Mitglied; die Plattform-Verwaltung hat sie überall). Funktion (frei) und Kennzeichen „Leitung“ bleiben je Ausbilder;
  wer einen Lehrgang anlegt, wird wie bisher Leitung. Die Namen kommen aus dem Konto (auch nach einer Umbenennung).
- **Lehrgang anlegen/bearbeiten:** je Zeile die Suche nach Name oder E-Mail-Adresse (`GET /api/pruefungen/nutzer?q=`,
  ab 2 Zeichen, höchstens 20 Treffer, nur passende Konten, ohne E-Mail-Adresse in der Antwort; suchen darf, wer
  Lehrgänge anlegt oder einen leitet). Der Name zählt als Teil, die E-Mail-Adresse nur ganz (Groß/klein egal) – als
  Teil ließ sie sich über die Treffer Zeichen für Zeichen erraten (Nachbesserung vom 02.11.2026). Nimmt sich eine
  Leitung im Dialog das Kennzeichen „Leitung“, bleibt sie Leitung in ihrer eigenen Zeile (keine zweite).
  **Kopieren** übernimmt nur Ausbilder mit passendem Konto (aktiv, Stufe); die übrigen nennt die Meldung
  (`ausbilder_nicht_uebernommen`). Der Server lehnt eine Zeile ohne Konto oder mit einem Konto ohne Stufe
  (auch deaktiviert) mit 400 ab – mit Klartext und `zeile`, der Dialog zeigt die Meldung an der Zeile. Ein Konto, das
  schon eingetragen ist und seine Stufe verliert, bleibt eingetragen; Lehrgang und Druckansicht markieren es mit
  „ohne Zugriff“, der Dialog mit „ohne Zugriff – Stufe in der Leitstelle vergeben“ (bzw. „Konto deaktiviert“). Es
  sieht den Lehrgang nicht, bis es die Stufe wieder hat. Ein gelöschtes Konto verschwindet aus allen Lehrgängen (seine
  Bewertungen behalten den Namen).
- **Excel-Import:** Ausbilder aus der Datei (Rolle) werden einem Konto zugeordnet – zuerst über die E-Mail-Adresse der
  Zeile (gehört sie zu einem Konto, entscheidet nur dieses), sonst über den Namen, wenn er unter den passenden Konten
  genau einmal vorkommt („Nachname, Vorname“ wie „Vorname Nachname“, Groß/klein egal). Wer nicht eindeutig passt, wird
  nicht übernommen und steht in Vorschau und Ergebnis unter „Nicht übernommen – kein Konto mit Riegenkarten-Stufe“
  (`ausbilder_nicht_uebernommen`: Name, Funktion). Schon eingetragene Konten kommen nicht doppelt. Die Vorschau nennt
  je Zeile nur den Namen des zugeordneten Kontos und ob es schon eingetragen ist (keine Kennung, keine Adresse).
- **Bestand (Schritt 34 der Materialablage):** Jeder Freitext-Ausbilder wird verknüpft, wenn sein Name eindeutig zu
  einem aktiven Konto mit Stufe passt (Funktion und Leitung bleiben; steht das Konto schon im Lehrgang, wird es eine
  Zeile – Leitung, wenn eine es war). Sonst wird er **entfernt – ohne Text in der Lehrgangsbeschreibung**. Das
  Startprotokoll nennt jede Verknüpfung („Schritt 34 (Riegenkarten): Lehrgang … – Freitext „…“ (Funktion) mit Konto n
  verknüpft“ bzw. „… mit der vorhandenen Zeile von Konto n zusammengelegt“), je Lehrgang die Entfernten („… – Ausbilder
  ohne passendes Konto entfernt: …“) und eine Summenzeile mit verknüpft, zusammengelegt und entfernt getrennt
  (`pruef_ausbilder` nachher = vorher − zusammengelegt − entfernt). Läuft einmal (Versionsvermerk, eine Transaktion); ein zweiter Start ändert
  nichts. Rückweg auf Schritt 33: nichts zu tun – der ältere Stand nimmt Stand 34 als aktuell und liest die
  verknüpften Zeilen wie immer; entfernte Freitext-Ausbilder gibt es nur in der Sicherung vor dem Deploy.
- **Vor dem Merge (Produktion):** Freitext-Ausbilder vorher mit Konten versehen – sonst fallen sie beim ersten Start
  weg (die Sicherung vor dem Merge enthält sie). Was Schritt 34 tun wird, zeigt das Werkzeug
  `scripts/vor_merge_riegenkarten.py` – nur lesend, nur Python, im laufenden Container der Produktion (kein `sqlite3`
  auf dem Rechner nötig, die Datei muss nicht dorthin):
  `git fetch origin && git show origin/dev:scripts/vor_merge_riegenkarten.py | docker exec -i stroemis python - /data/stroemis.db`.
  Teil 1, **Vorschau auf Schritt 34:** je Freitext-Ausbilder „verknüpfen“ bzw. „zusammenlegen“ (mit Konto, Name und
  Gliederung – gegenlesen: eine Verknüpfung über den Namen gibt dem Konto Einsicht in Teilnehmende und Bewertungen des
  Lehrgangs; ein Namensvetter wäre falsch) oder „ENTFERNEN“ mit Grund (mehrdeutig, nur Konten ohne Stufe, kein Konto),
  dazu die Summe und die Zahl der Ausbilder-Zeilen danach. Teil 2, **Bewertet ohne Eintrag:** wer in einem Lehrgang
  bewertet hat, ohne mit seinem Konto als Ausbilder darin zu stehen (und keine Verwaltung der Riegenkarten ist) – diese
  Konten sehen den Lehrgang nach dem Merge nicht mehr, außer Schritt 34 verknüpft sie (steht dabei).
  Für jede Person, die weiter prüfen soll: Konto anlegen (Name genau wie im Lehrgang) und Stufe „Mitglied“ in den
  Riegenkarten geben – dann verknüpft der Schritt sie selbst –, oder vorher im alten Stand den Eintrag auf das Konto
  umstellen (Häkchen „extern“ weg, Konto wählen); wer bewertet hat, ohne eingetragen zu sein, kommt im alten Stand als
  Ausbilder in den Lehrgang. Danach das Werkzeug noch einmal laufen lassen. Nach dem Start steht im Startprotokoll
  (gesichert in Schritt 4 der Inbetriebnahme, `grep "Schritt 34"`), wer verknüpft und wer entfernt wurde.

## Daten und Sicherung

Alles liegt im Volume `/data`: `stroemis.db` (SQLite), `media/orig` (Originale), `media/web` und `media/thumb` (erzeugte Varianten), `media/slide` (Fassungen der Anmeldeseite, entstehen bei Bedarf neu – muss nicht gesichert werden), `media/wiki` (Wiki-Bilder), `media/avatar` (Profilbilder), `media/pruefungen` (Medien zu Prüfungen), `media/material` (Fotos, Herstellerdokumente und Prüfanhänge der Materialablage; Herstellerdokumente unter `media/material/dok/<SHA-256>.<Endung>`, eine Datei je Inhalt), `pdf/` (festgeschriebene Protokolle der Materialablage, schreibgeschützt – unbedingt mitsichern: die Datenbank verweist auf sie, und ihre Prüfsummen lassen sich nicht neu erzeugen), `secret_key`, nur auf dev `sicherung-material-…` (Sicherungen von `material dev-zuruecksetzen`, siehe dort) und `tmp/` (Zwischendateien laufender Uploads und Exporte – muss nicht gesichert werden), `katalog-import/` (Zwischendaten des Katalogimports im Hintergrund, nach 7 Tagen weg – muss nicht gesichert werden). Verwaiste Dateien unter `media/wiki` räumt der Hintergrundlauf nach einer Woche weg (siehe „Wie die Anwendung abgesichert ist“).

**Stündliche Sicherung nach `~/data.bak`** – ein einzelner Cron-Eintrag auf dem VPS. Er gehört in den Cron des
Nutzers, dem `data/` gehört (uid 1000), oder in den von root: Nur die dürfen `secret_key` lesen. Mit `crontab -e`
eintragen und den Pfad anpassen:

```
0 * * * * cd /pfad/zur/produktion && mkdir -p ~/data.bak && docker exec stroemis python -c "import sqlite3; d = sqlite3.connect('/data/tmp/abzug.db'); sqlite3.connect('/data/stroemis.db').backup(d); d.execute('PRAGMA journal_mode=DELETE')" && cp data/tmp/abzug.db ~/data.bak/stroemis.db && rsync -a --delete --exclude=/tmp/ --exclude=/katalog-import/ --exclude='/stroemis.db*' data/ ~/data.bak/
```

Die Datenbank läuft im WAL-Modus; eine bloße Dateikopie kann mitten in einem Schreibvorgang einen unbrauchbaren
Stand erwischen. Deshalb zieht der Eintrag sie zuerst über SQLites Online-Backup im laufenden Container ab und legt
diesen Abzug als `stroemis.db` in die Sicherung, umgestellt auf das gewöhnliche Journal: So entstehen in
`~/data.bak` auch beim Hineinschauen keine WAL-Dateien, die beim Zurückspielen mitkämen. Danach spiegelt `rsync`
alle übrigen Dateien: Es überträgt nur Geändertes, und was in `data/` gelöscht wurde, verschwindet auch aus der
Sicherung. `~/data.bak` hält also immer nur den Stand der letzten vollen Stunde. Auf dem Host braucht es `rsync`.

Zurückspielen (im Ordner der Produktion):

```bash
docker compose down
rsync -a --delete --exclude=/pdf/ ~/data.bak/ data/    # --delete räumt auch alte WAL-Dateien neben der Datenbank weg
if [ -d ~/data.bak/pdf ]; then rsync -a ~/data.bak/pdf/ data/pdf/; fi   # Protokolle nur ergänzen, nie löschen (siehe unten)
sudo chown -R 1000:1000 data
docker compose up -d
```

Ohne `pdf/` in der Sicherung (vor dem ersten festgeschriebenen Protokoll, jede Sicherung von vor dem Merge) fällt die
zweite `rsync`-Zeile weg – sonst endete sie mit Fehler 23 und hielte ein Skript mit `set -e` an.

Festgeschriebene Protokolle der Materialablage (`data/pdf/`) werden beim Zurückspielen nicht gelöscht: Ein
Protokoll, das nach der letzten Sicherung entstand, ist vielleicht schon ausgehändigt. Die Datenbank kennt es nach
dem Zurückspielen nicht mehr; der Start legt es deshalb nach `data/pdf/verwaist/`, und seine Protokoll-ID wird nicht
noch einmal vergeben (ist der zugehörige Entwurf wieder offen, bekommt sein neues Protokoll eine Folgenummer wie
`P-2026-000007-2`). Die Prüfung ist im System neu festzuschreiben. Ebenso vergibt der Lebenslauf keine Kennung zweimal: Die zuletzt vergebene
steht als leere Datei unter `data/pdf/lebenslauf/`, und der Abruf nimmt die höchste Nummer aus Datenbank und Datei.
Maßgeblich für die Echtheit eines Lebenslaufs bleibt seine Prüfsumme; die Seite „Echtheit prüfen“ kennt die nach der Sicherung
ausgegebenen nicht mehr.

**Aufräumen (Schritt 37 der Materialablage, 04.11.2026) – Rückweg nur über die Sicherung:** Der Schritt entfernt
Spalten entfernter Funktionen (siehe „Aufräumen“ oben). Ein älterer Stand ≤ 36 liefe auf der migrierten Datenbank nicht
überall (er schriebe etwa beim Beispielbestand `mat_katalog`, vor dem Entfernen der Prüfanleitung `mat_form.wiki_page_id`)
– zurück also nur mit Code **und** Daten von vorher, wie unter „Zurückspielen“. Verlorene Werte (Markierungen
„kritisch“ an Prüfpunkten, Verknüpfungen Formular → Wiki-Seite) nennt das Startprotokoll je Spalte mit Zahl
(`docker compose logs | grep "Schritt 37"`); die Sicherung vor dem Deploy enthält sie. Mit SQLite < 3.35 bliebe alles
stehen (Meldung im Startprotokoll) – das Abbild `python:3.12-slim` bringt 3.46.

**Von Hand in der Datenbank** (Reparatur mit `sqlite3`, nur bei gestopptem Container und mit eigener Kopie vorher):
immer zuerst `PRAGMA foreign_keys = ON; PRAGMA recursive_triggers = ON;` – so wie die Anwendung jede Verbindung öffnet.
Ohne die beiden greifen Fremdschlüssel und die Lösch-Trigger bei `INSERT OR REPLACE` nicht. Festgeschriebene Nachweise
(Prüfungen samt Befunden und Anhängen, Durchgänge, Set-Protokolle, Journal, Mangelmeldungen, Anträge,
Mailfehler-Zeilen, seit Schema 31 das Verzeichnis ausgegebener Lebensläufe) schützen Trigger gegen Ändern, Löschen,
Ersetzen und – seit Schema 30 – jede Änderung der Kennung
(auch `SET rowid = …`); Kontoverweise darin dürfen nur auf NULL (so setzt sie das Löschen eines Kontos). Seit Schema 32
halten sie auch ohne `recursive_triggers`, wo REPLACE eine Zeile verdrängen würde: `UPDATE OR REPLACE` auf die Kennung
einer Prüfung oder eines Durchgangs (auch aus einem Entwurf oder offenen Durchgang heraus – die Kennungen ändern sich
nie) und REPLACE über Inventarnummer, QR-Kennung oder Produkt + Seriennummer eines geprüften Artikels. Die beiden PRAGMAs
bleiben trotzdem Pflicht.

**Übergang beim ersten Merge nach main (26.10.2026).** Der alte Deploy-Workflow sicherte vor jedem Neustart
(`scripts/sicherung.sh`, auf Wunsch aufs NAS); der neue sichert **nicht mehr** – es gilt allein der Cron-Eintrag oben.
Deshalb vor dem Merge auf dem VPS:

1. Eigene Kopie der Daten, nicht `~/data.bak` (die wird stündlich überschrieben und enthält eine Stunde nach dem Merge
   schon den migrierten Stand): `cd /pfad/zur/produktion && docker compose stop && cp -a data ~/data.vor-merge-$(date +%F) && docker compose start`
   (als Nutzer 1000 oder mit `sudo`; Pause unter einer Minute).
2. Das laufende Abbild als Rückweg aufheben – der Deploy räumt das alte Abbild mit `docker image prune -f` weg, und der
   alte Stand lässt sich heute nicht mehr ohne Weiteres neu bauen: `docker tag stroemis:latest stroemis:vor-merge-5c7e848`.
3. Den alten Cron-Eintrag entfernen: `crontab -l` (und `sudo crontab -l`) – die Zeile mit `# stroemis-sicherung` ruft
   nach dem Merge ein gelöschtes Skript auf (Rückgabewert 127, eine NAS-Sicherung endete still). Stattdessen die Zeile
   oben eintragen; nach dem Merge `sicherung.log` im Ordner der Produktion löschen. Die `BACKUP_*`-Zeilen der `.env`
   liest nichts mehr.

**Rückweg** nach dem Merge – nur mit den Daten von vorher, nie bloß den Code zurück: Der alte Stand liefe zwar auf der
migrierten Datenbank, löschte beim Kontolöschen aber Freigaben der Materialablage ohne Journal. Im Ordner der
Produktion:

```bash
docker compose down
mv data data.nach-merge-$(date +%F-%H%M)            # aufheben: Protokolle (pdf/) und alles seit dem Merge
cp -a ~/data.vor-merge-<Datum> data && sudo chown -R 1000:1000 data
docker tag stroemis:vor-merge-5c7e848 stroemis:latest
docker compose up -d                                 # ohne --build: das alte Abbild, die Compose-Datei bleibt
```

Danach nichts nach main pushen und keinen Deploy für main starten, bis der Fehler behoben ist; nicht per Force-Push
zurückgehen (der Klon auf dem VPS bliebe auf dem neuen Stand). Die Weiterleitungen der alten Adressen (`/wiki` →
`/stroemipedia`, `/karte`, `/admin`, `/material`, `/pruefungen`) hält der Browser einen Tag im Zwischenspeicher – nach
einem Rückweg führen alte Lesezeichen bis zu 24 Stunden ins Leere (hart neu laden hilft). Ein paar Wochen nach einem
gelungenen Merge `docker image rm stroemis:vor-merge-5c7e848` und `~/data.vor-merge-…` löschen.

## Inbetriebnahme in der Produktion (erster Merge dev → main)

Die Produktion (main) hat bis zum Merge keine Materialablage; der erste Start danach legt ihr Schema in einem Lauf an
(Schemaversion 34, unter einer Sekunde) und ändert an Konten, Strömipedia, Ankerplätzen und Riegenkarten nur die
Rechte-Matrix (Schritt 33: Verwaltung 2 → 3, siehe „Stufe Redakteur“) und die Riegenkarten-Ausbilder ohne Konto
(Schritt 34: verknüpfen oder entfernen, siehe „Ausbilder nur mit Konto“ – **vorher** die Freitext-Ausbilder mit
Konten versehen). Es geht keine Mail von selbst hinaus (Erinnerungsmails sind aus). Reihenfolge:

1. **Vorab:** Stand der Produktion ansehen (`git status --short; git log -1 --oneline` im Ordner der Produktion,
   `docker port stroemis`). Läuft der Reverse-Proxy auf demselben Rechner, `STROEMIS_PORT=127.0.0.1:8080` in die `.env`
   der Produktion – sonst veröffentlicht Compose den Port auf allen Schnittstellen. `stat -c %u data` im Ordner der
   Produktion muss `1000` sagen – sonst bricht der neue Deploy vor dem Neustart ab (einmalig
   `sudo chown -R 1000:1000 data`). Offene Kontoanfragen vorher erledigen (sie behalten die alten Vorgaben der Rechte).
   Mindestens 6 GB frei (Katalog unter `media/material` etwa 2 GB, dieselbe Menge in `~/data.bak`). Die Nutzer
   vorab informieren: Die Module heißen jetzt Strömipedia, Ankerplätze, Riegenkarten, Materialablage und Leitstelle,
   die Adressen `/stroemipedia`, `/ankerplaetze`, `/riegenkarten`, `/materialablage`, `/leitstelle` (alte Lesezeichen
   leiten weiter; die Seite nach dem Merge einmal neu laden).
2. **Sicherung:** wie unter „Übergang beim ersten Merge“ (eigene Kopie, Abbild taggen, Cron-Eintrag ersetzen). Die
   Kopie prüfen – **zuerst zählen**, direkt nach dem Kopieren: `find ~/data.vor-merge-<Datum> -type f | wc -l` gleich
   `find data -type f | wc -l`; dann die Unversehrtheit:
   `python3 -c "import sqlite3;print(sqlite3.connect('file:$HOME/data.vor-merge-<Datum>/stroemis.db?mode=ro&immutable=1',uri=True).execute('pragma integrity_check').fetchone())"`
   → `('ok',)`. `immutable=1` legt an der ruhenden Kopie keine `-shm`/`-wal`-Dateien an (mit nur `mode=ro` stünden
   danach zwei Dateien mehr in der Kopie als im Original).
3. **Merge und Deploy:** im Repository (nicht im Ordner der Produktion) den **geprüften Stand** nach main bringen –
   nicht den lokalen Zweig `dev`, der kann hinter `origin/dev` stehen und brächte dann einen älteren Stand in die
   Produktion: `git fetch origin && git checkout main && git merge --ff-only <geprüfter Commit>` (oder
   `git merge --ff-only origin/dev`, wenn `origin/dev` der geprüfte Stand ist). **Vor dem Push** prüfen:
   `git log -1 --oneline` nennt den geprüften Commit, und `grep -n "^SCHEMA_VERSION =" app/material/models.py` sagt
   `SCHEMA_VERSION = 34`. Erst dann `git push origin main`; der Workflow baut und startet neu. Den Lauf beobachten (GitHub → Actions, oder
   `curl -s "https://api.github.com/repos/HinzenSoft/stroemis/actions/runs?branch=main&per_page=1"` → `status`,
   `conclusion`): git pull, Prüfung `data` = uid 1000, Build, Neustart.
4. **Kontrolle:** `docker ps` (healthy), `docker port stroemis` wie unter 1 festgelegt (mit `STROEMIS_PORT` nur
   `127.0.0.1:8080`), `docker compose logs --tail 200` ohne Traceback; Schemaversion und
   Unversehrtheit: `docker exec stroemis python -c "import sqlite3;c=sqlite3.connect('/data/stroemis.db');print(c.execute(\"select wert from mat_meta where schluessel='schema_version'\").fetchone(), c.execute('pragma integrity_check').fetchone())"`
   → `('34',) ('ok',)`. **Startprotokoll sichern**, bevor ein späterer Deploy den Container ersetzt (nur dort stehen
   die Namen aus Schritt 34): `docker compose logs > ~/start-nach-merge-$(date +%F).log`, darin
   `grep "Schritt 34" ~/start-nach-merge-*.log`. Zählung vorher/nachher gegen die Vor-Merge-Kopie über **alle** Tabellen
   der Kopie (neue Tabellen der Materialablage zählen nicht mit):
   `for d in ~/data.vor-merge-<Datum> data; do python3 -c "import sqlite3,sys;c=sqlite3.connect('file:'+sys.argv[1]+'/stroemis.db?mode=ro',uri=True);k=sqlite3.connect('file:'+sys.argv[2]+'/stroemis.db?mode=ro&immutable=1',uri=True);print([(t,c.execute(f'select count(*) from \"{t}\"').fetchone()[0]) for (t,) in k.execute(\"select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name\")])" $d ~/data.vor-merge-<Datum>; done`
   – beide Zeilen gleich bis auf **`pruef_ausbilder`**: Dort ist nachher = vorher − zusammengelegt − entfernt (Zahlen aus
   der Summenzeile von Schritt 34 im Startprotokoll; ohne Freitext-Ausbilder gleich). Dazu
   `find data/media -type f | wc -l` gegen die Kopie (als Nutzer 1000 oder mit `sudo`). Im Browser als
   Plattform-Verwaltung: fünf Module in der Kopfleiste, Leitstelle → Nutzer (Materialablage nur bei der
   Plattform-Verwaltung „Verwaltung“), alte Lesezeichen leiten weiter. Nach der nächsten vollen Stunde:
   `ls -la ~/data.bak` (Zeitstempel dieser Stunde) und `crontab -l` (nur noch die neue Zeile, keine
   `# stroemis-sicherung`).
5. **Materialablage einrichten:** Gibt es noch keine Gliederung, vergibt die Migration keine Freigaben, und nur die
   Plattform-Verwaltung hat das Modul. In Leitstelle → Nutzer der Material-Verwaltung die Stufe „Verwaltung“ und den
   Mitgliedern der Gliederung „Mitglied“ geben (neue Konten haben „Mitglied“ schon), Prüfern dazu das Häkchen
   „Prüfer“; alle brauchen einen Namen. Als Material-Verwaltung unter Materialablage → Bestand „Gliederung anlegen“ –
   danach öffnet sich „Ordner bearbeiten“ im Reiter „Freigaben“ mit der Rolle „Materialwart“: im selben Schritt den
   ersten Materialwart wählen. Ab da verwaltet die Gliederung ihren Ordner selbst (weitere Freigaben, Prüffreigaben);
   die Urkundennummer tragen Prüfer selbst im Profil ein.
6. **Katalog:** die Import-ZIPs der Katalog-Lieferungen direkt in der Produktion einspielen – je Teil erst Probelauf,
   dann „Übernehmen“ (Katalog → „Katalog importieren“ oder `scp` nach `data/import/` und
   `docker exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material import-catalog /data/import/<teil>.zip --trocken`,
   dann ohne `--trocken`); eine Update-Datei erst nach der Serie, auf die sie aufsetzt. Danach `data/import/` leeren.
   **Prüfformulare kommen per Export von dev** (seit dem Formular-Pool, Schema 38; die Entscheidung vom 26.10.2026
   „Formulare kommen nicht per Export“ ist **aufgehoben**): Auf dev Katalog → „Katalog exportieren“, in der
   Produktion Katalog → „Katalog importieren“ (erst Probelauf, dann „Übernehmen“) bzw. `import-catalog` wie oben. Der
   Export bringt je Formular mit aktiver Version genau diese samt Standards und Zuweisungen; der Import macht sie
   aktiv, übernimmt kein DEMO-Kennzeichen und nimmt „DEMO“ vorn aus den Titeln (auch aktive Platzhalter der Skripte
   kommen so mit – vorher auf dev durch echte Formulare ersetzen oder deaktivieren, was nicht in die Produktion
   soll). Für die Zuweisungen ist die Datei maßgeblich. Danach legt die Material-Verwaltung unter Materialablage →
   Katalog → „Prüfformulare“ an und weist zu, was noch fehlt. Ohne Zuweisung und Standard lässt sich ein Artikel nicht
   prüfen (die App sagt es beim Start der Prüfung).
7. **Redakteure vergeben, Riegenkarten-Ausbilder verknüpfen** (Stufe Redakteur, 01.11.2026): Bestehende Mitglieder
   bleiben Mitglied und legen in Strömipedia und Ankerplätzen nichts mehr an und bearbeiten nichts mehr – auch nicht,
   was sie früher selbst angelegt haben. In Leitstelle → Nutzer zeigt die Spalte „Inhalte“, wer Artikel, Alben oder
   Bilder hat: diesen Konten bei Bedarf „Redakteur“ in der Strömipedia bzw. den Ankerplätzen geben. In den
   Riegenkarten sieht ein Mitglied nur noch die Lehrgänge, in denen es **mit seinem Konto** als Ausbilder steht; wer
   Lehrgänge anlegen soll, bekommt „Redakteur“ – wer bisher welche angelegt hat oder Kataloge pflegt, nennt dieselbe
   Spalte („n Lehrgänge“, „n Kataloge“). Ausbilder ohne Konto gibt es nicht mehr: Schritt 34 hat sie verknüpft
   oder entfernt (vorher vorbereitet, siehe „Ausbilder nur mit Konto“ – „Vor dem Merge“); im Startprotokoll
   nachsehen, wer entfernt wurde, und diese Personen bei Bedarf mit Konto und Stufe „Mitglied“ wieder eintragen.
   Verknüpfte Konten ohne Stufe stehen im Lehrgang als „ohne Zugriff“ – ihnen die Stufe geben oder sie austragen.
   Lehrgänge der Verwaltung ohne Ausbilder-Eintrag sieht nur die Verwaltung.
8. **Erinnerungsmails zuletzt:** erst wenn Gliederungen, Freigaben und Bestand stehen – Materialablage → Übersicht →
   „Probelauf ansehen“, dann Leitstelle → Einstellungen → Materialablage → „Erinnerungsmails verschicken“ an. In der
   `.env` der Produktion weder `MATERIAL_ERINNERUNGEN_SPERRE` noch `STROEMIS_NAME=…-dev`.

## Als App installieren (PWA)

Seit dem 01.11.2026 ist strömis.de eine installierbare Web-App (Wunsch des Nutzers vom 28.10.2026; Entscheidungen vom
01.11.2026: Symbol „Maskottchen auf Rot“, ohne Netz nur eine Hinweisseite). Alles dafür steht in `app/pwa.py`:

| Adresse | Inhalt |
| --- | --- |
| `/manifest.webmanifest` | `application/manifest+json`, ohne Anmeldung: Name „strömis.de“, `start_url` und `scope` „/“, `display: standalone`, Farben aus den Tokens (`--rot` als Leiste, `--weiss` als Hintergrund beim Start), Symbole 192/512 als „any“ und „maskable“, Kurzbefehle zu allen fünf Modulen (lange auf das Symbol drücken; wer ein Modul nicht hat, landet auf der Fehlerseite mit seinem Bereich). `no-cache`: Änderungen gelten nach dem Deploy sofort |
| `/sw.js` | der Service Worker (Quelle `app/static/js/sw.js`) mit Versionsstempel; `no-cache`, liegt am Ursprung und gilt damit für „/“ |
| `/offline` | die Hinweisseite „Keine Verbindung – strömis.de braucht das Netz. Versuch es gleich noch einmal.“ – ohne Mittel von außen (Stil, Zeichen als `data:`-Bild, „Erneut versuchen“ als Link auf dieselbe Adresse) |

Jede Seite mit Kopfleiste (auch Anmeldung und Fehlerseiten) verweist auf das Manifest und das Symbol für iPhone/iPad
(`apple-touch-icon`, iOS liest die Manifest-Symbole nicht) und meldet den Worker an (`common.js`, nur über HTTPS oder
localhost). **Was der Worker tut:** nur zweierlei – die Seite installierbar machen und die Hinweisseite zeigen, wenn eine
Seite nicht geladen werden kann (Netz weg). **Zwischengespeichert wird nur `/offline`** – keine Seite, keine Antwort der
Schnittstelle, kein Bild, nichts Angemeldetes. Jede Seite kommt wie ohne Worker vom Server, Fehlerseiten (403, 404, 500,
auch 502 des Proxys während eines Deploys) gehen unverändert durch. Gar nicht angefasst werden: alles außer dem Aufruf
einer Seite per GET (Skripte, Bilder, `fetch`, Formulare, Uploads), `/api/…`, `/media/…`, `/static/…`, die QR-Adressen
`/m/…` und Downloads (Adressen mit Dateiendung wie `…/lebenslauf.pdf`, `…/protokolle.zip`, `…/export/12.csv`, dazu
`…/pdf` und `…/sammelprotokoll`).

**Hinweis „App installieren“:** unauffällig im Profil, Abschnitt „App“ – mit Knopf, wo der Browser die Installation
anbietet (Chrome, Edge, Samsung Internet), mit der Anleitung „Teilen → Zum Home-Bildschirm“ auf iPhone und iPad; nicht,
wenn die Seite schon als App läuft. Chrome am Telefon zeigt keine eigene Leiste mehr; die Installation bleibt auch im
Browsermenü. Auf iPhone/iPad hat die App eine eigene Anmeldung (iOS trennt ihre Cookies von Safari) – einmal anmelden,
dann gilt sie wie im Browser 30 Tage.

**dev und Produktion** sind getrennte Apps (eigener Ursprung). Auf dev (`STROEMIS_NAME` endet auf `-dev`) heißt die App
„strömis.de dev“, und ihre Symbole tragen eine gelbe Marke „dev“. Die frühere öffentliche Strömipedia (`wiki.strömis.de`)
leitet seit dem 01.11.2026 zur Anmeldung (es gibt ohne Anmeldung keine Strömipedia-Seiten mehr); eine eigene
Installation dort ist nicht vorgesehen.

**Symbole** liegen fertig unter `app/static/img/pwa/` (je 192/512 „any“ und „maskable“, 96 für die Kurzbefehle, 180 für
iOS, jeweils auch mit `-dev`). Erzeugt aus `app/static/img/maskottchen.png` mit `python3 scripts/pwa_symbole.py` (Pillow;
Maskottchen auf `--rot`, „maskable“ kleiner mit Schutzrand – alles Wichtige im inneren Kreis von 40 % –, die dev-Marke in
der Hausschrift). Nur nötig, wenn sich das Maskottchen ändert; die Dateien werden eingecheckt.

**Betrieb – Worker-Aktualisierung beim Deploy:** Der Versionsstempel ist eine Prüfsumme über `sw.js`, die Hinweisseite, das Favicon
und das Maskottchen (beim Start berechnet). Ändert sich eins davon, ist `/sw.js` nach dem Deploy ein anderes Byte-Muster:
Der Browser holt den neuen Worker beim nächsten Seitenaufruf, er legt die neue Hinweisseite ab, übernimmt sofort
(`skipWaiting`, `clients.claim` – unbedenklich, weil er nichts außer der Hinweisseite aus einem Speicher liefert) und
räumt den alten Speicher weg. Ändert sich nichts davon, bleibt der installierte Worker; Seiten, Skripte und Stile kommen
ohnehin frisch vom Server. Nichts davon braucht einen Schritt beim Deploy. **Notausgang**, falls der Worker je stören
sollte: `app/static/js/sw.js` durch einen Worker ersetzen, der sich bei `activate` selbst abmeldet
(`self.registration.unregister()`) und keinen `fetch`-Haken hat, und ausrollen – die Browser holen ihn beim nächsten
Aufruf, danach läuft alles wie ohne Worker.

## Einführungen (Übungen je Modul)

Seit dem 03.11.2026 bietet jedes Modul außer der Leitstelle eine kurze Übung an (Wunsch des Nutzers vom 28.10.2026,
Entscheidungen vom 03.11.2026; Bauvorlage `planung/tutorial/entwurf.md`). Freiwillig: Beim Betreten eines Moduls
erscheint ein Angebot – unten rechts als schwebende Karte, am Telefon (unter 600 px Breite oder 520 px Höhe, also auch
quer) als Leiste unten, nicht modal und erst, wenn der Hinweis „Entwicklungsserver“ und das Willkommen der Materialablage
geschlossen sind. „Kurze Übung …“ heißt es nur, wenn die genannte Dauer höchstens 5 Minuten ist. „Nicht jetzt“ gilt für
alle angebotenen Teile, danach nur noch das Profil (Abschnitt „Einführungen“ unter „Passwort ändern“: je Modul eine
Zeile mit den geltenden Teilen als kleine Knöpfe – ✓ erledigt, „· fortsetzen“ mit der Stelle darunter; der Knopf startet,
setzt fort oder zeigt erneut, Dauer und Stand stehen in title und aria-label). Keine
Sperre, keine Weiterleitung; kein Angebot auf der Startseite, im Profil, in der Leitstelle, auf Druck- und Fehlerseiten,
im Lesemodus der Strömipedia und in „Meine PSA“.

**Teile** (`app/einfuehrung.py`, `TEILE`): je Modul ein Grundteil für alle mit Modulzugang und ein Zusatzteil je Rolle –
Materialablage: Grundteil, „Prüfer“ (Häkchen und Urkundennummer), „Materialwart“ (Verwalterfreigabe irgendwo),
„Material-Verwaltung“; Strömipedia: Grundteil, „Redakteur“, „Verwaltung“; Ankerplätze: Grundteil, „Redakteur“;
Riegenkarten: Grundteil, „Leitung“ (Leitung in einem Lehrgang oder Redakteur), „Redakteur“. Die Rollen rechnet der
Server bei jedem Seitenaufruf: Kommt eine Rolle hinzu, wird nur ihr Teil angeboten; fällt sie weg, verschwindet der Teil
aus Angebot und Profil (sein Stand bleibt).

**Übungsmodus:** die gewohnte Seite mit `?uebung=<teil>` (etwa `/materialablage?uebung=grund`) – nur, wenn der Teil für
das Konto gilt, sonst wird der Parameter übergangen. Der Server zeichnet dann nur die Hülle ohne echte Daten mit den
Rechten des Teils (`rechte[modul]` und in der Materialablage `data-darf`; kein Banner, kein Willkommen, kein „Zuletzt
besucht“, keine Suche mit Weiterleitung, kein `_sichtbar` der Riegenkarten); Titel mit dem Vorsatz „Übung · “. Im
Browser legt `app/static/js/einfuehrung.js` vor den Skripten der Seite eine Schicht um `fetch`, `XMLHttpRequest`,
`sendBeacon`, `window.open`, Datei-Links, GET-Formulare und den Verlauf: Anfragen an `/api/` und `/media/` beantwortet die
Übungsdatei des Moduls (`app/static/js/uebung/<modul>.js`) aus ihrem Übungsbestand, Schreibvorgänge spielt sie darin
nach (je Ablauf frisch, im `sessionStorage` des Reiters unter `stroemis-uebung`). `localStorage` und `sessionStorage`
zeigen in der Übung auf eine eigene Übungsablage (`stroemis-uebung-ablage` im `sessionStorage` des Reiters): Kein Skript
der Seite liest oder schreibt die echte Ablage – eine laufende echte Stoppuhr, zugeklappte Ordner oder ein ausgeblendeter
Hinweis bleiben, wie sie sind. Hochgeladene Dateien bleiben im
Browser („Übungsbild nehmen“ setzt ein Bild aus `/static/uebung/` in die Dateiwahl); Dateien öffnen eine Übungsdatei
(`/static/uebung/uebungsdatei.pdf`) oder melden „In der Übung gibt es diese Datei nicht.“. Seitenwechsel behalten die
Kennung (Links und Formulare des Moduls, Verlauf, im Code `S.ziel(adresse)` aus `common.js`); die Kopfleiste und ein neuer
Reiter führen auf die echten Seiten – auch ein Klick mit Strg, Cmd, Umschalt oder Alt wie der Mittelklick: Der Link bekommt
keine Kennung, der neue Reiter (das neue Fenster, der Download) zeigt die echte Seite, die Übung in diesem Reiter läuft
weiter, und ihr Merker bleibt. Öffnet ein Reiter ohne Übungszustand die Übung (Lesezeichen, Link mit Kennung), beginnt er
beim gemerkten Ablauf und setzt den Merker nie auf einen kleineren zurück. Seiten des Moduls ohne Übungszweig (nicht in `STROEMIS.einfuehrung.seiten`, vom
Server aus `UEBUNGSSEITEN`) öffnen sich in der Übung nicht: Links, Formulare und Seitenwechsel per Code (Navigation API)
bleiben auf der Seite mit dem Toast „In der Übung nicht verfügbar.“; ohne Navigation API antwortet der Server mit der
Fehlerseite und „Zurück zur Übung“ (Übungszustand bleibt). Ebenso die alten Adressen der Module (`/material…`, `/wiki/…`,
`/karte`, `/pruefungen…`, Schreibweisen mit Umlaut): Ihre Weiterleitung behält aus der Übung die Kennung (Kennung in der
Adresse oder Referer derselben Übung, `einfuehrung.mit_kennung`; auch `…/katalog/meldungen?bereich=antraege`) und landet
nie auf der echten Seite im selben Reiter. Zurück im Browser nach dem Verlassen der Übung („Übung unterbrechen“,
„Geschafft“, Kopfleiste) zeigt die echte Startseite des Moduls, keine Übungsseite ohne Führung: Übungsseiten kommen mit
`Cache-Control: no-store`, und eine Übungsseite aus dem Verlauf (auch aus dem Seitenspeicher des Browsers, `pageshow`)
ohne laufende Übung dieses Teils geht mit `location.replace` zur Startseite. Abmelden geht auch aus der Übung und leert die echte Ablage
samt Übungszustand. Kartenkacheln laden wie sonst. Zweite Absicherung ist die Sperre auf dem Server
(siehe „Wie die Anwendung abgesichert ist“). Übungs-Kennungen: Materialablage 900000001–900000999, Strömipedia 9100000xx,
Ankerplätze 9200000xx, Riegenkarten 9300000xx – echte Zeilen erreichen sie nie; beim Ende, beim Unterbrechen und auf
jeder echten Seite räumt `einfuehrung.js` die Übungsablage und den Übungszustand weg (beim Abmelden gehen sie ohnehin mit).

**Führung:** ein Rahmen in `--wasser` um das Ziel (die Seite bleibt bedienbar), eine Sprechblase daneben bzw. als Leiste
unten mit „Übung · Schritt n von m“, Ablauftitel, Text, „Zurück“/„Weiter“ (grau umrandet – der rote Hauptknopf im Bild
gehört der Seite) und „Übung unterbrechen“; in einem offenen Dialog wandert sie in den Dialog. Als **Leiste** steht sie
unter 600 px Breite oder 520 px Höhe (Telefon hochkant und quer) und in jedem Schritt, in dem die schwebende Blase neben
dem Ziel keinen Platz findet; ist die Leiste breit (ab 600 px), stehen ihre Knöpfe rechts neben dem Text. Die schwebende
Blase steht unter, über, rechts oder links neben dem Ziel (samt aufgeklappter Liste eines Kombinationsfelds, etwa der
Vorschläge der Suche) und deckt nie das Ziel, die Kopfleiste, die Leisten darüber, offene Menüs oder die Knöpfe des
Dialogs (`.dlg-actions`); auf einem faltbaren Gerät bleibt sie in einem Bildschirmsegment (`viewport.segments`). Jeden
Schritt sagt eine Live-Region an („Übung · Schritt n von m: Text“). „Tippe“ in den Texten der Übungsdateien heißt ohne
Touch-Zeiger „Klicke“. Ein Eingabeschritt geht erst weiter, wenn du fertig bist: nach 1,5 s ohne Tastendruck, beim
Verlassen des Felds, mit Enter oder bei einer Auswahl (seit dem 04.11.2026; vorher schon beim ersten passenden Zeichen). Esc fragt „Übung unterbrechen?“ – mit dem Satz, dass du im Profil unter „Einführungen“ fortsetzen
kannst. Führt eine Aktion auf eine andere Seite, setzt die neue Seite fort (bis 5 s Warten auf das Ziel, sonst „Hier geht
es in der Übung nicht weiter.“ mit „Ablauf neu beginnen“); kommst du per Zurück im Browser auf eine Seite eines früheren
Schritts, sagt die Blase, dass „Vor“ zum Schritt zurückführt oder der Ablauf neu beginnen kann. Nach dem Neuladen setzt
die Führung am gespeicherten Schritt fort – nach einer Eingabe in diesem Ablauf (Text, Suchbegriff, die das Neuladen
löscht) am Anfang des Ablaufs. Am Ende eines Teils der Dialog „Geschafft“ – mit der Anleitung des Moduls in der
Strömipedia, wenn das Konto sie lesen darf, und „Nicht jetzt“/„Weiter mit „…““, wenn ein weiterer Teil offen ist.

Wie die Führung ein Ziel zeigt (seit 04.11.2026, „Führung robust“): Sie holt es **sofort** (ohne weichen Bildlauf) in die
Mitte des freien Bereichs – zwischen festen bzw. klebenden Leisten oben (Kopfleiste, Suchzeile, Reiter; gesucht mit
`elementsFromPoint` an der waagerechten Mitte des Ziels) und unten (Abschlussleiste, am Telefon die Leiste der Führung),
begrenzt von Rahmen, die in sich rollen (Dialog, Schublade); höhere Ziele stehen mit ihrem Anfang oben. „Bereit“ ist ein
Schritt erst, wenn die Webschriften geladen sind (`document.fonts`), kein Overlay mehr seinen Schritt zurück im Verlauf
nimmt (`S.dialogVerlauf`: das Zurück stellt die alte Bildlaufhöhe her), keine Animation am Ziel oder einem Vorfahren
läuft (Schublade) und das Ziel zwei Bilder lang still steht. Rutscht es in den 2,5 s danach doch unter eine Leiste, holt
die Führung es noch einmal ins Bild (nicht, wenn du selbst rollst). Bei offenem modalem Dialog zählen nur Ziele in ihm.
Während ein Seitenwechsel läuft, wertet sie auf der alten Seite nichts aus (kein `wenn`, nichts gespeichert); welche
Schritte nicht zutreffen, hält sie beim Betreten eines Ablaufs fest – „Schritt n von m“ springt nicht. **Jeder Ablauf
beginnt mit frischem Übungsbestand und neu geladener Startseite**, auch bei gleicher Adresse oder nur anderem Anker. Ziele
im Editor (`contenteditable`) bekommen kein `aria-describedby` (ProseMirror zeichnete sonst neu) – den Text sagt eine
Live-Region an. Seitenwechsel auf Dateien (`/api/`, `/media/`, Endung – wie bei Links, etwa der Export der Strömipedia)
hält die Schicht über die Navigation API an: Übungsdatei oder „In der Übung gibt es diese Datei nicht.“. Ein vom Nutzer
geöffnetes Menü bleibt frei (die Blase weicht aus oder liegt unter einem schwebenden Menü, der Rahmen dunkelt es nicht
ab). Klebende Leisten unten (`position: sticky/fixed; bottom: 0`) und fensterhohe Flächen enden über der Leiste der
Führung: unter `html.fuehrung-leiste` mit `bottom: var(--fuehrung-hoehe, 0px)` bzw. abgezogener Höhe (Regel in `app.css`,
Abschnitt „Einführung“; `scroll-padding-bottom` ebenso).

**Übungen je Modul** (Bau 04.11.2026; Übungsdateien `app/static/js/uebung/<modul>.js`, Bilder unter
`app/static/uebung/<modul>/` aus `scripts/uebungsdateien.py`; nur Platzhalter „Übung“, keine erfundenen Fachdaten wie
Intervalle oder Lebensdauern – die Materialablage nimmt Produkte und Prüfformulare, wo es geht, aus dem echten Katalog):
- **Materialablage**: Grundteil (Zurechtfinden, Artikel finden, Mangel melden), „Prüfer“ (Prüfung durchführen),
  „Materialwart“ (Artikel anlegen, Freigabe erteilen, Prüfdurchgang), „Material-Verwaltung“ (Katalog und Prüfformular).
  Übungsbestand: „Übung – Gliederung“ mit Lager und Fahrzeug 1 (und den Systemordnern), drei Übungsartikel (Ü-0001 Gurt,
  Ü-0002 Seil, Ü-0003 Helm), Übungsperson A/B; Kennungen 900000001–900000999. Jeder Seitenwechsel in `material.js`,
  `suche.js`, `global.js`, `freigaben.js` geht über `S.ziel`. Tests `tests/test_einfuehrung_material.py`,
  `tests/test_einfuehrung_katalog.py`.
  **Produkte aus dem Katalog** (seit 04.11.2026, Wunsch „Produkte und Prüfbögen, die im Katalog sind – ohne Echtdaten der
  Artikel“): Eine Übungsseite der Materialablage trägt in `STROEMIS.einfuehrung.katalog` eine feste Auswahl echter
  Katalogprodukte samt geltendem Prüfformular (`einfuehrung.katalog_material`, kein Weg unter `/api/`). Je Rolle ein
  Produkt – Gurt: eine Kategorie im Pfad endet auf „Gurt(e)“, textil; Seil: „Seil(e)“, textil; Helm: „Helm(e)“, sonst
  „Karabiner“ (der Katalog hat keine Helme) –, nicht DEMO, ohne laufenden Rückruf, mit geltendem Formular
  (`katalog.formular_fuer_produkt`, nicht DEMO, mit Prüfpunkten); Produkte mit Bild zuerst, dann die kleinste Kennung.
  DEMO nach der Regel des Katalog-Exports (seit der Nachbesserung vom 04.11.2026): auch ein Produkt oder Formular in einer
  DEMO-Kategorie ohne eigenes Kennzeichen. Die Auswahl liegt je Arbeitsprozess im Zwischenspeicher – neu gerechnet nach
  einer Änderung am Katalog (Zahl und letzte Änderung von Produkten, Formularen, Prüfpunkten, Kategorien, Rückrufen,
  Dokumenten), an einem neuen Tag oder spätestens nach 60 Sekunden (`einfuehrung.KATALOG_FRIST`). Die Bildausnahme der
  Sperre prüft zuerst Methode (GET), Pfad (`/media/material/web|thumb/`), Dateinamen und Anmeldung mit Modulzugang und
  sieht erst dann in die Auswahl – ohne Anmeldung kostet eine Anfrage mit `X-Uebung` nichts mehr.
  Mitgegeben werden nur Katalogfelder: Hersteller, Modell, Beschreibung, Artikelnummer, Norm, Materialart,
  Kategoriepfad (Namen), Prüfintervall und Lebensdauer mit Quelle, Produktbild (Web- und Vorschaufassung), Namen,
  Art, Version, Gültigkeit und Größe der geltenden Herstellerdokumente; vom Formular Titel, Version, Quelle und Prüfpunkte
  (Gruppe, Text mit Absätzen, Art, Soll, optional). Nichts über Artikel, Ordner, Bestand, Personen, Journal, Prüfungen
  oder Meldungen; Kennungen, Artikel (Inventar- und Seriennummern „Ü-…“), Ordner und Personen bleiben Übung, Links führen
  nie auf echte Produktseiten. Herstellerdokumente öffnen in der Übung nicht („In der Übung gibt es diese Datei
  nicht.“). Die Prüfung im Teil „Prüfer“ nutzt die Punkte des echten Formulars, vorbelegt wie echt; was in Pflichtpunkten
  danach noch leer ist, trägt die Übung ein (Text „Übung“, Zahl „1“, Datum heute, Foto und Unterschrift der Übung) – bis
  auf den ersten Zahl- oder Textpunkt, den trägst du ein. Längenpunkte sind „nicht zutreffend“ (Übungsartikel haben keine
  Länge). Der Teil „Material-Verwaltung“ bearbeitet eine Übungskopie des Formulars (neuer Punkt in der ersten Gruppe).
  Die Schritte nennen die Produkte („Such „<Modell>““, „Öffne „<Hersteller Modell>““). Fehlt eine Rolle (kein Katalog,
  kein passendes Produkt), bleibt ihr Platzhalter („Übungsgurt“, „Übungsseil“, „Übungshelm“ vom Hersteller „Übung“ mit
  dem „Übungsformular“ aus drei Platzhalter-Punkten, ohne Intervall und Lebensdauer).
- **Strömipedia**: Grundteil (Lesen, Suchen, Kommentieren, Bearbeiten), „Redakteur“ (Seite anlegen, Bearbeiten erlauben,
  Verlauf), „Verwaltung“ (Für alle Angemeldeten freigeben, Papierkorb) am Übungsabschnitt „Übung: Start“ (Adressen
  `/stroemipedia/uebung-…`, Kennungen 9100000xx). Löschen, Verschieben, Duplizieren, Lesebeschränkung, Hochladen, Import
  und Export gibt es in der Übung nicht. Test `tests/test_einfuehrung_wiki.py`.
- **Ankerplätze**: Grundteil (Karte und Album; Suchen und filtern), „Redakteur“ (Album anlegen; Bilder hochladen mit
  Rückfrage „ohne Geotag“, Adresssuche und Tipp auf die Karte; Bild beschreiben). Drei Übungsalben um den
  Kartenmittelpunkt, die Adresssuche findet nur den „Übungsort“; nicht in der Übung: Löschen, Zusammenlegen, Deckblatt,
  Ziehen und Ablegen. Test `tests/test_einfuehrung_karte.py`.
- **Riegenkarten**: Grundteil (Lehrgang öffnen, Voraussetzung abhaken, Bewerten, Mängel), „Leitung“ (Teilnehmende
  eintragen, Lehrgangsergebnis; beginnt im Übungslehrgang), „Redakteur“ (Lehrgang anlegen). „Übungslehrgang“ mit
  „Teilnehmer Übung 1–3“, Leistungen, Kriterien und Voraussetzungen als Platzhalter, ohne Zeitansatz (keine Stoppuhr);
  Kennungen 9300000xx. Druckansichten, Import, Kopieren, Löschen, Profilbilder, Medien und das Bearbeiten von Katalogen,
  Voraussetzungen und Leistungen gibt es in der Übung nicht. Test `tests/test_einfuehrung_riegen.py`.

**Merker** ohne Schemaschritt in `mat_meta` (Schema bleibt 34): Schlüssel `einfuehrung:<Konto>`, Wert
`{"<modul>:<teil>": {"zustand": "abgelehnt" | "unterbrochen" | "erledigt", "ablauf": n, "am": …}}`; ein unlesbarer Wert
(kein JSON, falsche Typen, tief geschachtelt) gilt als leer. „unterbrochen“ trägt den nächsten unfertigen Ablauf,
fortgesetzt wird an seinem Anfang. Schnittstelle: `PUT /api/einfuehrung/<modul>/<teil>` mit
`{"zustand": "abgelehnt" | "unterbrochen" | "erledigt", "ablauf": n}` (`ablauf` ganzzahlig ab 0, kleiner als die Zahl der
Abläufe, fehlt → 0) → `{"ok": true}`; nur angemeldet (401) und aus eigenem Skript (JSON, wie alle schreibenden
Schnittstellen; fremde Seite 403), 404 unbekannter Teil, 403 wenn der Teil nicht für das Konto gilt, 400 falscher Zustand
oder Ablauf; aus „erledigt“ wird nichts anderes (Antwort trotzdem ok); unter der Schreibsperre, gleichzeitige Aufrufe
verlieren nichts. Lesen tut ihn nur der Server (Angebot, Profil, `STROEMIS.einfuehrung.teile`) – eine Leseschnittstelle
gibt es nicht. Die Übung darf ihn auch aus der Übung heraus schreiben (Ausnahme der Sperre). Kein Journal, keine Mail, keine Anzeige in der Leitstelle. Der
Merker geht mit dem Konto (`api_admin.delete_user`); ein Zurücksetzen der Materialablage auf dev leert `mat_meta` und
damit auch ihn – alle bekommen das Angebot dann wieder. Rückweg: `DELETE FROM mat_meta WHERE schluessel LIKE
'einfuehrung:%'`.

**Übungsdateien** (`app/static/js/uebung/<modul>.js`) registrieren sich mit
`S.einfuehrung.modul(modul, { bestand, antworten, dateien, teile })`:

| Feld | Inhalt |
| --- | --- |
| `bestand` | `() => ({ … })` – Übungsbestand, frisch je Ablauf; nur Platzhalter „Übung“, Kennungen im Bereich des Moduls |
| `antworten` | `[[methode, muster, (treffer, body, z, url) => antwort], …]` – `methode` „GET“ … oder „*“, `muster` RegExp auf den Pfad oder genauer Pfad; Antwort: Objekt (JSON 200), `{status, error}` (Fehler), `{datei: "/static/…"}` (Datei) oder eine `Response`, auch als Promise; was sie in `z` ändert, bleibt bis zum Ende des Ablaufs |
| `dateien` | `[[RegExp, "/static/uebung/…"], …]` – Datei-Adressen, die in der Übung eine Übungsdatei öffnen |
| `teile` | `{ <teil>: { ablaeufe: [{ titel, start, schritte: [schritt, …] }, …] }, … }` – genau die Teile aus `TEILE`, die Titel der Abläufe und die Startadresse des ersten wie dort (`tests/test_einfuehrung.py` vergleicht) |

Ein Schritt: `ziel` (Selektor, Funktion → Element oder `null` = Blase mittig ohne Rahmen), `text` (reiner Text, du, ein
bis zwei Sätze), `warten` (fehlt → Knopf „Weiter“; `{klick: sel}`, `{wert: [sel, RegExp]}`, `{anfrage: "METHODE /pfad"}`
oder RegExp, `{da: sel}`, `{bedingung: (z) => bool}`), `wenn` (`() => bool`, Schritt nur, wenn zutreffend), `datei`
(`{input: sel, bild: "/static/uebung/…"}` – Knopf „Übungsbild nehmen“), `probe` (nur für den Durchlauftest: `{klick: sel}`,
`{klick: sel, frei: true}` – Tipp auf die Mitte der größten freien Stelle, etwa auf die Karte; gibt es keine, mit
`sonst: sel` auf jenes –, `{tippen: [sel, text]}`, `{datei: true}`; ohne probe klickt der Test `warten.klick` bzw.
„Weiter“). Mehrere Angaben in `warten`: was zuerst eintritt. `text` darf ein Getter sein und `ziel` eine Funktion – beide
fragt die Führung immer wieder neu (die Lupe der Materialablage, bis das Suchfeld offen ist). Texte schreiben „Tippe“; am
Rechner sagt die Blase „Klicke“. Ziele sind einfache Selektoren oder
Funktionen, die sagen, wann ein Ziel zur richtigen Seite gehört – Bildlauf, Dialoge, Schriften und Schubladen wartet die
Führung selbst ab. Testschnittstelle
(nur lesend): `S.einfuehrung.zustand()`, `S.einfuehrung.teile(modul)`. Übungsbilder und die Übungsdatei erzeugt
`python3 scripts/uebungsdateien.py` (Pillow; ohne Angabe nur die Übungsdatei, Bilder nur mit `--ziel` in den Ordner
eines Teils, `--von`, `--bis`).

**Nach einer Änderung an der Oberfläche nachziehen:** Wird ein Durchlauftest rot (`tests/test_einfuehrung_browser.py`,
je Modul `tests/test_einfuehrung_<modul>.py`; Befunde nennen Ablauf, Schritt und Ziel), stimmt meist ein Selektor in
`uebung/<modul>.js` nicht mehr, oder die Seite stellt eine neue Anfrage, die die Antworttabelle noch nicht kennt
(„Unbeantwortete Anfragen“). Neue programmatische Seitenwechsel im Modul gehen über `S.ziel(…)`. Bekommt eine Seite einen
Übungszweig, gehört ihr Endpunkt in `UEBUNGSSEITEN` (sonst „In der Übung nicht verfügbar“). Ändern sich Abläufe
(Titel, Startadresse des ersten), gehören sie auch in `TEILE`. Die Browser-Tests laufen mit Chromium über
`/home/harness/devtools/cdp` (Hilfe `tests/einfuehrung_browser.py`); ohne Chromium melden sie „übersprungen“.

## DLRG-Wortmarke einsetzen

Die Kopfzeile ist als rote Bauchbinde mit Wortmarke, Trennstrich und Funktionsbezeichnung aufgebaut. Bis die offizielle Wortmarke vorliegt, steht dort der Schriftzug „DLRG“ in Gelb. Die SVG-Wortmarke aus dem DLRG-Downloadbereich als `app/static/img/dlrg-wortmarke.svg` ablegen und den Container neu bauen – sie wird dann automatisch verwendet.

Die Hausschrift **DLRG Univers 55 Roman** liegt als WOFF2 unter `app/static/fonts/` (Regular, Kursiv, Fett; zusammen rund 74 kB) und wird für die Bauchbinde, die Wortmarke auf der Anmeldeseite und alle Überschriften benutzt – in der Leseansicht und im Editor gleichermaßen. Der übrige Text bleibt beim Systemschnitt.

Farben nach Handbuch CD (Stand 09/2024): Rot `#e30613`, Gelb `#ffed00` (nur für die Wortmarke und als Hinweisfarbe), 80 % Schwarz `#575756` als Textfarbe, Blau `#0069b4` als Kennfarbe für Gewässer. Schrift: Univers, ersatzweise Arial (die Univers ist lizenzpflichtig und wird nicht mitgeliefert – liegt sie auf dem Rechner vor, wird sie verwendet).

## Editor-Syntax (Markdown)

Der Editor arbeitet WYSIWYG; gespeichert wird Markdown, das auch von Hand geschrieben werden kann:

```
:::warning ⚠️
**Große Lastwinkel**

Text …
:::

:::columns
Linke Spalte
|||
Rechte Spalte
:::

:::accordion Titel der einklappbaren Box
Inhalt, der erst nach dem Aufklappen sichtbar ist.
:::

![Video](/media/wiki/abc123.mp4)
```

Nach `:::art` steht optional das Emoji (Standard: 💡 info und tip, ⚠️ warning, ✅ success, ⛔ danger, 📝 note), dahinter wahlweise `farbe:<name>`. Im Editor stehen diese Blöcke so da, wie sie später aussehen; bearbeitet wird direkt im Text, einen Dialog gibt es nicht mehr. Videos sind Bild-Links mit Video-Endung.

## Hilfeseite für den Editor

Unter `docs/` liegt die Seite „Editor: Bedienung und Kürzel“ als Markdown-Datei. Sie erklärt
Kürzel, Einfügemenü, Auswahlleiste, Callouts, Spalten, Tabellen und Medien – und ist zugleich ihr
eigenes Beispiel. In eine frische Installation kommt sie über eine neue Seite, in die der Inhalt
der Datei eingefügt wird.

## Entwicklung ohne Docker

```bash
pip install -r requirements.txt
python run.py                 # http://127.0.0.1:8080, Daten in ./data
python tests/test_smoke.py    # Rauchtest über die API (Login, Upload, EXIF, Rechte, Wiki, Reset)
                              # und Härtungstest (Freigaben, alte Adressen, Anmeldebremse, Grenzen)
python tests/test_wiki_lesemodus.py    # Wiki-Lesemodus: Konto ohne Wiki-Stufe sieht genau die freigegebenen Seiten, ohne Anmeldung nichts (alle Wiki-Routen)
python tests/test_rechte_redakteur.py  # Stufe Redakteur: Mitglied/Redakteur/Verwaltung je Endpunkt, Sichtbarkeit der Riegenkarten, Schritt 33
python tests/test_rechte_ausbilder.py  # Riegenkarten-Ausbilder nur mit Konto: Anlegen/Bearbeiten, Kontosuche, Import-Zuordnung, Schritt 34
python tests/test_pruefungen.py         # Prüfungsbereich (Rechte, Kataloge, Excel-Import, Kopieren, Nachprüfung, Medien)
python tests/test_pruefungen_import.py  # Excel-Erkennung
python tests/test_material_feinschliff.py  # Feinschliff aus den Wiki-Fragen: „Deine PSA“ trotz „Erinnerungsmails aus“ (E2 B), Verlauf des
                                        # Kontos für die Leitstelle (E3 A), „Artikel online“ im Protokoll, Texte (K9, K19, K21, T)
python tests/test_umbenennung.py        # Neue Modulnamen: jede alte Adresse → neue (301, Abfrage, Umlaute, kein offener Sprung), Rechte,
                                        # Kopfleiste und Titel, Mails, neue PDFs mit /materialablage/pruefen, alte PDFs unverändert, Wiki-Links
python tests/test_module_vor_merge.py   # Nachbesserung vor dem Merge (übrige Module): Titel der Anmeldeseiten, Rollennamen in Meldungen, Rechte-Raster, Verlauf, Esc/Fokus, Emoji-Raster
python tests/test_module_nach_merge.py  # Lieferung nach dem Merge (übrige Module): Wiki-Export (Namen bis frei, Titelzeile), Seitentitel ohne Namen,
                                        # Knopfsprache, Sprunglink, Tippflächen und Leitstelle (statisch), Reset-Mail
python tests/test_module_info_i.py      # Info-„i“ app-weit: S.info und Jinja-Makro (Markup, aria, Verhalten, Esc im Dialog), alle 52
                                        # umgestellten Stellen je Modul, was sichtbar bleibt, Marken je Liste, Vorlagen gerendert
python tests/test_module_letzte_offene.py  # Letzte offene Punkte: Datenschutzsätze am „i“ eine Zeile, Baumknöpfe der Strömipedia,
                                        # Blatt-Symbol „Angaben zur Seite“, Abschnittsaktion neben der Überschrift
python tests/test_geraetetest_teil1.py  # Gerätetest Teil 1: Slideshow als WebP, Anmeldeseiten (H1, Meldung, Passwort anzeigen,
                                        # location.replace), Menüs und Zurück, Schubladen inert, Kopfleiste bei wenig Höhe, Toast
python tests/test_module_uiux_verhalten.py  # UI/UX vor dem Merge, Teil U1a: Zurück schließt Overlays, Fehler am Feld, ein
                                        # Menübaustein, Rückfragen, Mehrzahl, Export mit Uhrzeit, Fehlerseiten, Bedienzeichen
python tests/test_wiki_fehlerart.py     # Fehlerart beim Ablegen von Dateien der Strömipedia (Import, Hochladen, Drehen, Zuschneiden)
python tests/test_wiki_geraetetest.py   # Gerätetest 01.11.2026, Teil 2: Speicherstand, „/“-Menü, Artikel-Leiste, Inhaltsverzeichnis in „⋯“,
                                        # Kommentar als Blatt, Aufgabenlisten, Dateinamen, Erfolgsmeldungen (statisch)
python tests/test_module_uiux_u1b.py    # UI/UX vor dem Merge, Teil Aussehen: Kontrast auf hellen Flächen, Tippflächen, Menü, Abschnittskopf,
                                        # Leerzustand, Statusmarken, Reiter, Textknopf, Namen, Tokens, CSS-Hygiene (statisch)
python tests/test_module_uiux_u3.py     # UI/UX vor dem Merge, Teil U3: Hinweis „Entwicklungsserver“ (nur dev, einmal je Anmeldung),
                                        # Anmeldung, Leitstelle, 403-Weg, Strömipedia, Ankerplätze, Riegenkarten (statisch)
python tests/test_module_geraetetest_t5.py  # Gerätetest 01.11.2026, Teil 5: Ankerplätze Suche/Liste „in der Nähe“, Standort,
                                        # Bildnamen, Hochlade-Meldung; Leitstelle Suche/Filter/Karten, Spaltenköpfe, Prüffreigabe-Satz
python tests/test_geraetetest_riegen.py # Gerätetest 01.11.2026, Riegenkarten: Aufklapper „Voraussetzungen“, klebende Reiter, Kopf, ohne Netz,
                                        # Erfolgsmeldungen, Kriterien-Zustand, Überschriften, Fehler am Feld (statisch)
python tests/test_material_uiux_u2.py   # UI/UX vor dem Merge, Teil U2 Materialablage: Ultrawide, ausgegraute Hauptknöpfe mit Grund,
                                        # Abschlussleiste, Mangel je Rolle, Knöpfe, Banner, Journal, „Echtheit prüfen“, Radiogruppe, Fehlerzustand
python tests/test_geraetetest_quer.py  # Gerätetest 01.11.2026, Teil X: :hover nur mit Maus (:active am Finger), Schrift 14/15 px,
                                        # Listen ab 760 px Inhalt als Tabelle, Abschlussleiste ohne Überbreite, Matrix quer (statisch)
python tests/test_material_geraetetest4.py  # Gerätetest 01.11.2026, Teil 4: Suche und QR im Prüfdurchgang, eine Zählweise, eingeklappte
                                        # Abschlussleiste, Sprung zum fehlenden Schritt, Filter mit aria-pressed, Bestandsbaum am Telefon, ein Platzhalter
python tests/test_material.py           # Materialablage (Migration, Rollen, Katalog, Ordner, Artikel, Suche, Journal, Import, Prüfung, Durchgang, Produktmeldungen,
                                        # Festschreiben, Protokolle, Prüfsumme, Prüfseite, Berichtigung) – braucht WeasyPrint samt Pango;
                                        # den Stempel liest pdftotext (poppler-utils), ohne es pypdf
python tests/test_material_ueberblick.py  # Lieferung 4: Zählung je Ordner, Führungskraft nur lesend (alle Routen), /m/<token> ausgesondert
python tests/test_material_export.py     # Lieferung 4: CSV je Ordner, Protokoll-ZIP, Lebenslauf-PDF
python tests/test_material_katalog.py    # Lieferung 4: Katalog-Export und -Import (Rundlauf, ohne DEMO, ZIP-Sicherheit)
python tests/test_material_rueckruf.py   # Lieferung 4: Rückrufe (Rechte, betroffene Artikel, Mail, Sperre, Lebenslauf)
python tests/test_material_l5.py         # Lieferung 5: Mangel mit Bemerkung, Urkundennummer, Oberfläche (Gerüst, CSS, Prüfformular, Ordnerfoto, Suchfeld);
                                        # Phase 2: Oberfläche nach Rechten je Ordner (statisch)
python tests/test_material_profil.py     # Lieferung 5: Urkundennummer im Profil
python tests/test_material_trennung.py   # Phase 2: Trennung je Gliederung (Migration 7 → 8, nichts aus einer fremden Gliederung in irgendeiner Antwort,
                                        # Kennungen im Inhalt, Heimat, Verschieben und Durchgänge, Prüfsicht, Ablauf)
python tests/test_material_freigaben.py  # Phase 2: Freigaben vergeben, ändern, entziehen, verlängern; Übernahme-Schutz; Nutzerverwaltung; Rechte je Person (02.11.2026)
python tests/test_material_globalsuche.py  # Phase 2: globale Seriennummernsuche, QR-Steckbrief, Protokoll (keine Bremse), Sperrwort, nur Fremdes
python tests/test_material_zuordnung.py  # Phase 2: Personenzuordnung, Meldungen je Bereich, Löschkonzept, Prüfnachweise bleiben
python tests/test_material_meine_psa.py  # Phase 3: Meine PSA (auch ohne Modulstufe), Kopfleiste, QR, Medien, Karte, Profil
python tests/test_material_mangel.py    # Phase 3: Mangelmeldung (Sperre, Fotos, Mails, Freiprüfung mit Häkchen, Aussondern, Migration 13, Oberfläche statisch)
python tests/test_material_stammdaten.py  # Stammdaten fest nach der ersten Prüfung (Dienst 409, Trigger, Migration 14, Dialog statisch)
python tests/test_material_antrag.py      # Änderungsanträge: Nachtragen nur per Antrag, Antrag/Bestätigen/Ablehnen, Rechte, Trigger, Mails, Rückruf,
                                         # Löschkonzept, Migration 15 bis 17 (7 → 17 mit MATERIAL_KOPIE_STAND_7), Oberfläche statisch;
                                         # Prüfung: Leser ohne Begründung/Namen, Bescheid nur mit Recht, Trigger 16, Rückruf-Hinweis,
                                         # „vormals“ im Sammelprotokoll (SAMMELPROTOKOLL_ABLAGE=datei.pdf legt es für st-vera ab),
                                         # Nachtragen nach Entfernen per Antrag nur per Antrag (Altfall Stand 16);
                                         # Zurückziehen, Herstelldatum nicht entfernbar, Migration 17 (16 → Ende mit Anträgen)
python tests/test_material_antrag_zustaendig.py  # Anträge an alle Stammdaten: Zuständigkeit je Rolle (E5–E7), ohne Zuständige, Sammelantrag,
                                         # neue Felder und Produkt, Bearbeiten durch Prüfer, Trigger und Migration 22 → 23, Produktjournal
                                         # am Artikel und im Lebenslauf (E8), Seiten, Oberfläche statisch
python tests/test_material_bestandteile.py  # Bestandteil-Liste an Produkten und Seriennummern der Bestandteile: Migration 24 → 25, Trigger,
                                            # Katalog, Prüfzeilen („fehlt“ = Mangel), Nummern (direkt, Prüfung, Antrag, Suche, PSA,
                                            # Lebenslauf), Katalogdatei (F2), Oberfläche statisch
python tests/test_material_ohne_kritisch.py  # „kritisch“ entfernt (03.11.2026): Formular-Editor und Schnittstelle, „einsatzbereit“ trotz alter
                                             # Markierung, Protokoll/Lebenslauf/Jahresbericht/CSV ohne, gespeichertes Protokoll unverändert,
                                             # Katalogimport mit (übergangen, keine neue Version) und Export ohne, Oberfläche statisch
python tests/test_material_formular_editor.py  # Prüfformular-Editor (04.11.2026, Chromium, sonst „übersprungen“): Gruppen als Zwischenzeile,
                                             # Ziehen (Maus/Finger, in andere Gruppe, Bildlauf am Rand, Esc), Menü „⋯“, In Gruppe verschieben,
                                             # Gruppe umbenennen/verschieben/entfernen, Speichern in der Datenbank, Nur-Lese-Ansicht,
                                             # 44 px am Finger gemessen; Absatz per Enter, in der Prüfung, HTML bleibt Text; Häkchen „optional“
python tests/test_material_untergruppen.py   # Untergruppen (Schema 39): Normalisierung und Reihenfolge-Regel, Schnittstelle, neue Version,
                                             # Kopie, Journal, Export/Import rund (auch alte Datei ohne Feld), Prüfung, Berichtigung, PDF,
                                             # festgeschriebenes Protokoll unverändert, Trigger, Migration frisch und 38 → 39 mit Altbestand;
                                             # Browser 1280/360 (anlegen, umbenennen, ziehen, entfernen, Punkte hinein/heraus, Speichern,
                                             # Nur-Lese-Ansicht, Prüfungsansicht, 44 px gemessen) und die Übung mit Untergruppen
python tests/test_material_pruefpunkt_absatz.py  # Absätze im Prüfpunkt (04.11.2026): punkt_text, Speichern, neue Version, Katalog-Export/
                                             # -Import rund, Prüfung, Meldung in einer Zeile, Prüfprotokoll-PDF mit eigenen Zeilen
python tests/test_material_formular_pool.py  # Formular-Pool (Schema 38): Auflösung, Zuweisen (Teilbaum, Standard von oben,
                                             # Z3–Z5, Länge, ohne aktive Version), Verschieben löst (Z6, Vorschau), Löschen,
                                             # Trigger per SQL, Prüfung und Protokoll, Titel/Kopie/Vorlage, Rechte je Rolle,
                                             # alte Routen 404, Zähler katalog_stand, Migration 37 → 38 mit Altbestand, Abbruch,
                                             # frisch, Oberfläche statisch
python tests/test_material_formular_transfer.py  # Katalogaustausch Format 3: Export nur aktive (auch DEMO), ohne Journal;
                                             # Import ohne DEMO, „DEMO“ aus Titeln, aktiv, Datei maßgeblich für Zuweisungen,
                                             # Abgleich uid/Titel, laufende Prüfung, Rundlauf; alte Formate 1/2
python tests/test_material_formular_sicherheit.py  # Formular-Pool nach der Sicherheitsprüfung: Format 1/2 schreibt kein geteiltes
                                             # Formular um (Fälle 1–5), PUT …/zuweisung mit kaputtem Rumpf 400, Hinweise im
                                             # Importbericht (Titel, leere Formularliste), „DEMO“ in jeder Schreibweise, Trigger
python tests/test_material_aufraeumen.py  # Aufräumen (Schema 37): frisch ohne die elf Spalten, 36 → 37 mit Werten in allen
                                             # (übrige Spalten, Kennungen, FK, Volltext, Protokoll gleich; Startprotokoll; zweiter
                                             # Lauf/Start; Schutz), SQLite < 3.35, Schnittstelle je Rolle, alte Wege 404, statisch
python tests/test_einfuehrung.py         # Einführung je Modul: Übungssperre (jede /api/-Regel × Methode), Merker, Angebot je Rolle,
                                        # Übungsseiten ohne echte Daten, Seiten ohne Übungszweig (jede Seitenregel), engere CSP, Abmelden,
                                        # Profil „Einführungen“, Übungsdateien gegen TEILE (statisch)
python tests/test_einfuehrung_browser.py # Einführung im Browser (Chromium, sonst „übersprungen“): Angebot, „Nicht jetzt“, Profil, Gerüst-
                                        # Übung je Modul bis „Geschafft“, Esc, Blase im Dialog, kein /api/ und /media/ im Übungsmodus,
                                        # Übungsablage, Seiten ohne Übungszweig (Toast), ohne Referer (CSP), Abmelden aus der Übung
python tests/test_einfuehrung_material.py # Übungen der Materialablage: S.ziel in den Modulskripten, Platzhalter, alle vier Teile bei
                                          # 1280 (Maus) und 360 (Touch) bis „Geschafft“, Datenbank unverändert
python tests/test_einfuehrung_wiki.py   # Übungen der Strömipedia: drei Teile bei 1280/360, Router mit Kennung, Export als Hinweis (Menü
                                        # frei), echte Seite nicht in der Übung, wiki_*-Tabellen unverändert
python tests/test_einfuehrung_karte.py  # Übungen der Ankerplätze: beide Teile bei 1280/360, echtes Album nicht in der Übung, Datenbank
                                        # und Medienordner unverändert
python tests/test_einfuehrung_riegen.py # Übungen der Riegenkarten: drei Teile bei 1280/360, echter Lehrgang nicht in der Übung, Druck →
                                        # Toast, Stoppuhr-Reste, pruef_*-Tabellen unverändert
python tests/test_material_stufen.py     # Phase 2: Modulstufe (Migration 9 → 10, ohne Stufe wirkt nichts – alle Routen, Material-Verwaltung,
                                        # Personensuche je Zweck, Mails, Profil, Vorgabe neuer Konten)
python tests/test_material_beispielbestand.py  # Beispielbestand: Katalog unverändert bis auf DEMO-Formulare (nicht im Export), Struktur, Geschichte über zwei Jahre,
                                               # alle Zustände, Protokolle, DEMO-Kennzeichnung, Konten, Petzl- und Platzhalter-Formulare, abgebrochener Lauf,
                                               # Sperre (BASE_URL, dev-Kennung), Typ nach Kategorienamen, Mangelpunkte, Uhr, vorhandene Konten, „Neue Version“ bleibt DEMO
python tests/test_material_dev_zuruecksetzen.py  # material dev-zuruecksetzen: Sperren (dev-Kennung, BASE_URL als Positivliste, Schalter), --trocken, Sicherung (0700/0600), Abbruch bei laufendem Katalogimport
                                                 # vollständig, Schema wie neu, übrige Module byteidentisch, Scheitern und SIGTERM/SIGHUP ändern nichts
python scripts/material_beispielbestand.py --beispielbestand  # DEMO-Bestand und DEMO-Konten aus dem vorhandenen Katalog (nur dev/localhost,
                                                              # siehe „Beispielbestand (nur dev)“; die Passwörter stehen nur in der Ausgabe)
flask --app "app:create_app()" material import-catalog katalog.json --trocken   # Katalogdatei prüfen (JSON oder ZIP)
flask --app "app:create_app()" material export-catalog katalog.zip              # Katalog ohne DEMO als ZIP (Format 3)
```

Die JavaScript-Bibliotheken liegen im Arbeitsbaum unter `app/static/vendor/` und werden im Docker-Build noch einmal frisch geladen und gegen `vendor.sha256` geprüft.

WeasyPrint (Protokolle der Materialablage) braucht außerhalb von Docker die Systembibliotheken Pango und HarfBuzz – unter Debian/Ubuntu `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core` (dazu `libharfbuzz-subset0` ab Debian 12 bzw. Ubuntu 24.04 – älteren Systemen fehlt das Paket, WeasyPrint läuft dann ohne), unter macOS `brew install pango`.

`tests/rundlauf.html` prüft die zentrale Invariante des Editors – Markdown öffnen und speichern darf kein Byte ändern – über einen Korpus aus 66 Fällen. Ein zweiter Abschnitt prüft den Rückgängig-Verlauf (ein Strg+Z direkt nach dem Laden darf am Dokument nichts ändern, eigene Änderungen müssen weiterhin rückgängig zu machen sein), gesetzte Leerzeilen, das Auflösen unvollständiger Abschnitte und die Grenzen des Renderers: Aufgabenlisten behalten ihr Kästchen, Formulare und Stilblöcke aus dem Seitentext kommen nicht durch. Ein dritter Abschnitt prüft die zusammengefassten Zellen: dass ein Zug über mehrere Zellen überhaupt eine Zellauswahl ergibt (das Bündel von Toast UI ist an dieser Stelle fehlerhaft übersetzt und wird geflickt), dass Verbinden und Teilen die erwartete Schreibweise ergeben und dass die Leseansicht daraus `colspan` und `rowspan` macht – mit Gegenproben, die ohne die Reparatur beziehungsweise ohne die Nachbearbeitung fehlschlagen müssen. Die Datei lädt die Projektskripte über relative Pfade; ein Doppelklick genügt, ein Server ist nicht nötig.

`tests/gleichstand.html` hält Leseansicht und Editor nebeneinander und misst für 17 Bausteine Schriftgröße, Schnitt, Farbe, Auszeichnung, Ausrichtung und den linken Textanfang – die Probe darauf, dass der Editor zeigt, was der Artikel später zeigt.

`tests/nachgeholtes_speichern.html` prüft, dass das automatische Speichern niemals die falsche Seite trifft: Ein Speichervorgang, der seinen eigenen Editor überlebt, weil die Anfrage hängt und man inzwischen die Seite gewechselt hat, darf den Text der neuen Seite nicht unter der Kennung der alten ablegen. Die Datei fährt das Wiki mit einem nachgestellten Server hoch, der jede Schreibanfrage so lange festhält, bis der Test sie freigibt – der Ablauf hängt damit an keiner Laufzeit. Auch hier genügt ein Doppelklick.

`tests/live_mitlesen.html` prüft das Mitlesen: Sobald jemand anderes schreibt, meldet sich der Leser alle 4 statt alle 15 Sekunden, holt jede neue Fassung und zeichnet den Artikel nach – der oberste sichtbare Absatz bleibt dabei auf ±2 px an seiner Stelle, auch wenn oberhalb ein Absatz eingefügt wurde; unter einer Textauswahl wird nicht gezeichnet, und nach dem Weggang des Schreibers kommt der letzte Stand noch an, danach gilt wieder der lange Takt. Der Lauf dauert rund eine halbe Minute, weil die echten Takte gelten.

`tests/baustein_editor.html` prüft den HTML-Baustein in beiden Ansichten: Im Artikel entsteht aus der Bild-Schreibweise ein gesandboxter Rahmen mit den Maßen aus der Adresse, kein rohes `<iframe>` und keine fremde Adresse kommt durch. Im Editor steckt er in einer Hülle mit Griff, bekommt dasselbe Menü wie ein Bild und wird an drei Griffen gezogen; geprüft wird jeweils, was der Editor danach an den Server schickt (`#w=…&h=…`), und dass die Zuordnung zu einem Bild daneben stimmt. Der Server ist eine Attrappe, ein Doppelklick genügt.

## Aufbau

```
app/
  __init__.py      App-Factory, Seiten-Routen, Weiterleitung der alten Adressen, Medienauslieferung, CSRF-Schutz, Security-Header
  module.py        Sichtbare Modulnamen und Seitenadressen (NAME, PFAD), alte Adressen (ALT, UMLAUT) und ihr Ziel
  start.py         Startseite über alle Module: GET /api/start (Kacheln, Zuletzt besucht, Neu und geändert, Abschnitte),
                   POST /api/start/besuch, Merker in mat_meta (ziel_merken aus den Routen, konto_vergessen)
  auth.py          Login, Registrierung, Reset, Profil (Session-Cookie, Werkzeug-Hashes)
  api_albums.py    Alben, Bilder, Kartendaten
  api_wiki.py      Seiten, Versionen, Suche, Freigaben, Kommentare, API des Lesemodus, Datei-Upload, Export, Import (Route)
  wiki_import.py   Wiki-Import aus einem ZIP (Prüfung, Baum, Anhänge, Verweise, eine Transaktion)
  api_admin.py     Nutzerverwaltung
  api_pruefungen.py  Prüfungen: Lehrgänge, Teilnehmende, Voraussetzungen, Leistungen, Kataloge, Versuche, Medien, Mängel, Import, Rechte
  pruefungen_import.py  Excel-Teilnehmerlisten lesen (Kopfzeile finden, Spalten zuordnen, ja/nein deuten) – ohne Flask
  images.py        EXIF (GPS, Höhe, Zeit), Ausrichtung, Thumbnails, HEIC, Videos nach H.264
  medienpflege.py  Nach dem Start im Hintergrund: Bestandsvideos wandeln, verwaiste Artikeldateien aufräumen (eine Sperre, ein Arbeiter)
  db.py            SQLite-Schema, Migrationen, Transaktionsklammer
  material/        Materialablage, eigenständig: models.py (Tabellen mat_*, Schemaversion in mat_meta),
                   routes.py (Seiten /materialablage…, /m/<token>, Schnittstelle /api/material…, Medien),
                   routes_export.py, routes_katalog.py, routes_rueckruf.py (Export, Katalogaustausch, Rückrufe),
                   routes_freigaben.py, routes_global.py, routes_zuordnung.py (Freigaben, globale Suche, Zuordnung),
                   cli.py (flask material import-catalog, export-catalog), services/ (rechte, katalog, bestand,
                   status, interval, search, nummern, qr, journal, importer, katalog_export, pruefung,
                   durchgang, anhang, protokoll (Festschreiben, Ablage, Prüfseite), pdf (WeasyPrint), stempel
                   (Prüfsumme), unterschrift, ueberblick, export, lebenslauf, beschriftung, rueckruf, meldung,
                   freigaben, globalsuche, globalprotokoll (Protokoll der globalen Suchen), medien (Rechte je Datei),
                   zuordnung, loeschung (Löschkonzept), psa (Meine PSA), mangel (Mangelmeldung), antrag
                   (Änderungsanträge an festen Stammdaten), stueckliste (Bestandteil-Liste eines Produkts),
                   teilnummern (Seriennummern der Bestandteile)),
                   routes_psa.py, routes_antrag.py,
                   templates/ (pdf/: Vorlagen der Protokolle und des Lebenslaufs), static/ (material.js, .css,
                   unterschrift.js für das Signatur-Pad, pruefen.js für die Prüfseite, freigaben.js für den Reiter
                   „Freigaben“, global.js für die globale Suche, profil_psa.js für „Meine PSA“ im Profil)
  mailer.py        SMTP-Versand (ohne SMTP_HOST landet die Mail im Log)
  templates/       Jinja-Seiten; _makros.html mit dem Makro „info“ (dasselbe „i“ wie S.info, für Vorlagen)
  static/css/      app.css – ein Blatt für alle Ansichten; pruefungen.css nur für den Prüfungsbereich
  static/fonts/    DLRG Univers als WOFF2 (Regular, Kursiv, Fett)
  static/img/      Favicon, optional die DLRG-Wortmarke
  static/vendor/   Leaflet, markercluster, marked, DOMPurify, Toast UI, signature_pad (im Docker-Build geladen)
  static/js/       common.js       gemeinsame Helfer (api, esc, dialog, toast, Datum, info – das „i“ hinter einem Begriff;
                                   seit UI/UX vor dem Merge: Zurück schließt Overlays (overlayVerlauf, dialogVerlauf,
                                   klassenVerlauf), Fehler am Feld (feldFehler, fehlschlag), ein Menübaustein (menue,
                                   menueSchwebend), confirm mit { endgueltig: false }, plural, rollen, Bedienzeichen ✕ ↑ ↓;
                                   seit dem Gerätetest 01.11.2026: Zurück und Esc schließen auch Menüs, schubladeZustand
                                   (zugeklappt inert), toast als gemeinsame Rückmeldung, html.tastatur auch auf Android,
                                   „Passwort anzeigen“ über data-pw-zeigen)
                   markdown.js     Renderer: Callouts, Spalten, Boxen, Videos, TOC, Auszeichnungen; Artikelsuche (Suchzeile) für wiki.js und public.js
                   editor-format.js  Markdown <-> Editorformat (reine Funktionen, trägt den Rundlauf)
                   editor-layout.js  Darstellung der Abschnitte im Editor (ProseMirror-Dekorationen)
                   editor-verlauf.js Rückgängig-Verlauf: Laden gehört nicht hinein
                   wiki.js         Editor, Seitenbaum, Kommentare, Teilen, Verlauf
                   public.js       Lesemodus (Konten ohne Stufe im Wiki; bis 01.11.2026 auch das öffentliche Wiki)
                   start.js        Startseite über alle Module (Kacheln, Listen, Karten der Strömipedia)
                   map.js          Karte, Alben, Upload, Lokalisieren, Bild-Detail
                   pruefungen.js   Lehrgänge, Voraussetzungen, Bewertungsmatrix, Stoppuhr, Mängel, Excel-Import
                   admin.js (mit admin_globalsuche.js), auth.js, profile.js
tests/
  test_smoke.py    Rauch-, Härtungs- und Befundtest über die API (der Befundtest stellt die Fixes der Sicherheitsprüfung nach)
  test_wiki_lesemodus.py  Lesemodus des Wikis: Konto ohne Stufe im Wiki gegen jede Wiki-Route der url_map
  test_module_kleinigkeiten.py  Kleinigkeiten aus dem Artikel-Nachzug: Ankersprung (node), Herzschlag, Ersteller und
                   Bearbeiter nur mit Stufe, Leistungsdialog eingefroren, „Bild bearbeiten“ ohne Rundung, Texte
  test_module_startseite.py  Startseite: Route und Navigation, Rechte je Rolle, Zahlen der Materialablage wie die Übersicht,
                   Zuletzt besucht, „neu seit dem letzten Besuch“, Abschnitte als Karten, Suchfeld
  test_pruefungen.py  Prüfungsbereich: Rechte, Kataloge, Import, Kopieren, Pflichtkommentar, Nachprüfung, Medien, Mängel
  test_pruefungen_import.py  Excel-Erkennung mit synthetischen Dateien
  test_material.py Materialablage: Migration, Rollen, Katalog, Ordner, Artikel, Suche, Journal, Status, Import,
                   Prüfung, Sperre und Aussonderung, Anhänge, Prüfdurchgang, Produktmeldungen, Festschreiben,
                   Protokolle mit Prüfsumme, Prüfseite, Berichtigung, Unterschrift
  test_material_ueberblick.py, test_material_export.py, test_material_katalog.py, test_material_rueckruf.py
                   Materialablage, Lieferung 4: Übersicht und Rechte, Export, Katalogaustausch, Rückrufe
  test_material_l5.py, test_material_profil.py
                   Materialablage, Lieferung 5: Feinschliff nach Pilot, Urkundennummer im Profil; dazu die
                   statische Prüfung der Oberfläche nach Rechten je Ordner (Phase 2)
  test_material_trennung.py, test_material_freigaben.py, test_material_globalsuche.py, test_material_zuordnung.py,
  test_material_stufen.py
                   Materialablage, Phase 2: Trennung je Gliederung, Freigaben, globale Suche, Personenzuordnung,
                   Löschkonzept und Modulstufe
  test_material_set_rueckbau.py
                   Materialablage, Rückbau der Set-Funktion (Schritt 26): Migration frisch, 20 → Ende und 25 → 26 mit
                   Set-Altbestand, Trigger, Schnittstelle (entfallene Routen, Katalogdatei, Meldung, CSV), Rechte am
                   Reiter „Bestandteile“, kein Set-Rest im Code
  test_material_setprotokolle.py
                   Materialablage, Set-Protokolle im Prüfdurchgang (Schritt 27): Inhalt je PDF (verschachtelt, gesperrt,
                   aus dem Bereich), Zwischenzeilen und Verzeichnis, Abbruch, Fehler beim Rendern, Trigger, Prüfseite,
                   Nummernschutz, Rechte je Rolle, Ordnerseite, ZIP des Durchgangs und Ordner-Export
  test_material_lebenslauf_summe.py
                   Materialablage, Prüfsumme und Kennung für den Lebenslauf (Schritt 31): Abruf und Verzeichnis, Kennung
                   je Jahr, Prüfseite (unverändert, Stempel fehlt, angehängt, verändert, fremd, falsche Kennung), Trigger,
                   Migration 30 → 31
  test_material_nach_merge.py
                   Materialablage, Liste nach dem Merge (Schritt 32): Lebenslauf-Kennung nach dem Zurückspielen,
                   HEAD und Abrufbremse, Prüfseite, REPLACE ohne recursive_triggers (Trigger, Migration 31 → 32),
                   Rückruf nach Antrag wieder offen, Rückruf-Text nach dem Stand beim Versand
  test_material_reste.py
                   Materialablage, Reste vor dem finalen Test: „Weiterlesen“ im Mangel-Banner, Brotkrumen am Telefon
                   in einer Zeile, „Produktmeldungen“, Ergebnisseite, Fokus im Unterschrift-Dialog
  test_material_dg_archiv.py
                   Materialablage, abgeschlossene Prüfdurchgänge (27.10.2026): Schnittstelle je Jahr mit Filtern und
                   Seiten, Rechte und Gliederungstrennung, Seite und Menü je Rolle, Info-„i“, Namen als Einheit,
                   Knopftexte ohne „…“ in allen Modulen

  test_material_pdf_umbruch.py
                   Materialablage, Seitenumbrüche in den PDF-Protokollen: Verzeichnis und Artikelliste des
                   Sammelprotokolls (Anfang, Ende, kurz), Abschluss des Prüfprotokolls auf neuer Seite,
                   Herstellerdokumente ohne zerhackte Spalten, Tabellenkopf bei langen Bemerkungen
  test_material_produktwechsel.py
                   Materialablage, Feintuning (23.10.2026): Produkt am Artikel ändern – Rechte, Entwurf,
                   DEMO-Grenze, Folgen (Lebensende, Länge, Fälligkeit, Rückrufe, Durchgang, Meine PSA), Journal,
                   Hinweis „anderes Produkt“, Oberfläche statisch
  rundlauf.html    Rundlauf, Rückgängig-Verlauf und verbundene Zellen im Browser prüfen (Datei einfach öffnen)
  gleichstand.html Leseansicht und Editor nebeneinander messen (Datei einfach öffnen)
  nachgeholtes_speichern.html
                   Automatisches Speichern trifft nie die falsche Seite (Datei einfach öffnen)
  live_mitlesen.html
                   Mitlesen bei fremdem Schreiber: kurzer Takt, Nachzeichnen, Lesestelle bleibt
  baustein_editor.html
                   HTML-Baustein: Rahmen im Artikel, Menü und Ziehgriffe im Editor (Datei einfach öffnen)
```

Hinweise: iPhone-Videos im HEVC-Format (.mov) werden beim Hochladen und für den Bestand nach H.264 gewandelt – ohne ffmpeg (etwa in einer Entwicklungsumgebung ohne Container) bleibt es beim Original, das dann nur Safari abspielt. Die Nutzungsbedingungen der OSM-/OpenTopoMap-Kachelserver gelten für kleine Nutzergruppen; bei größerem Aufkommen `TILE_URL` auf einen eigenen oder kommerziellen Kachelserver umstellen.
