# strömis.de

Übungsobjekte für die seiltechnische Rettung und Übungsgewässer für die Strömungsrettung auf einer Karte katalogisieren – plus ein gemeinsames Wiki. Ein Docker-Container, Gestaltung nach dem DLRG-Handbuch Corporate Design.

## Was die Anwendung kann

**Spots (Karte)**
- Bilder erscheinen als Thumbnail-Marker (rote Umrandung = Seiltechnik, blaue = Gewässer). Beim Herauszoomen werden sie zu einem Stapel mit Zähler zusammengefasst; ein Klick zoomt hinein, auf der letzten Stufe fächern sie sich auf.
- Klick auf ein Bild öffnet das Album mit allen Bildern, allgemeinen Infos und dem Ansprechpartner (Name, Gliederung, Telefon, E-Mail, Hinweise).
- Jedes Bild hat Titel, Notiz, Objekthöhe, Höhe ü. NN, Aufnahmezeit, Koordinaten und ein Freitextfeld für weitere Infos. Alles ist nachträglich änderbar.
- **Bilder auf die Karte ziehen** legt ein neues Album an: Ein kurzer Dialog fragt Titel und Art, dann wird hochgeladen. Liegt der Mittelpunkt der Geotags innerhalb von 2 km an einem Album, das man selbst führt, fragt die Anwendung anschließend, ob die Bilder dorthin gehören – dann wandern sie in das vorhandene Album und das neue löst sich wieder auf. Alben anderer in der Nähe werden genannt, aber nicht angeboten. Dateien über der Seitenleiste eines eigenen Albums kommen direkt in dieses Album.
- Beim Hochladen werden Geotag, Höhe und Aufnahmezeit aus den EXIF-Daten gelesen (JPEG, PNG, WebP, TIFF, HEIC/HEIF vom iPhone). Bilder ohne Geotag werden erkannt; die Anwendung bietet direkt an, sie auf der Karte zu platzieren – per Tipp auf die Karte, über die Album-Position, den eigenen Standort oder über eine Adresssuche, die die Karte an die gesuchte Stelle fährt. Die Suche läuft über den eigenen Server (Nominatim), damit die Adresse nicht mit der IP des Mitglieds nach außen geht.
- Kartenansichten (Ebenenwahl oben rechts): Satellit (Esri-Luftbild, Startansicht), Karte (OpenStreetMap) und Gelände (OpenTopoMap), Filter nach Seiltechnik/Gewässer. Über dem Luftbild liegt eine Beschriftungsebene mit Straßen, Orts- und Gewässernamen – sonst sieht man zwar die Kiesbank, weiß aber nicht, an welchem Fluss; sie erscheint nur zum Luftbild und ist über `SAT_LABELS_URL` austauschbar oder abschaltbar. Ist die Seitenleiste offen, rücken Zoom, Ebenenwahl und Rechtehinweise neben sie, statt darunter zu verschwinden.
- Das Deckblatt eines Albums lässt sich festlegen (in der Großansicht eines Bildes „Als Deckblatt“). Es steht in der Albumliste und liegt auf der Karte im Bilderstapel eines Haufens obenauf. Ohne Wahl zeigt das Album sein erstes Bild.
- Videos (MP4, MOV, WebM) können wie Bilder hochgeladen werden. Was nicht jeder Browser abspielt – vor allem Aufnahmen vom iPhone (.mov mit HEVC) – wird beim Hochladen nach H.264/AAC gewandelt und bekommt ein Vorschaubild aus dem Film; dafür bringt der Container ffmpeg mit – als statisch gebundenes Programm (GPLv3) aus dem Abbild `mwader/static-ffmpeg` von Docker Hub, festgenagelt über dessen Prüfsumme (bis 21.10.2026 von johnvansickle.com, das nicht mehr erreichbar war). Aus der Paketverwaltung kostete dasselbe rund 630 MB statt etwa 260 MB. Das gilt auch für Videos in Artikeln und für den **Bestand**: Nach jedem Start prüft ein Hintergrundlauf alle vorhandenen Videos und wandelt, was nötig ist – Verweise in Seiten, Fassungen und Anhangslisten ziehen mit, und die alte Adresse (`….mov`) führt weiter zum Film. Unter „Nutzer“ steht, solange es läuft, eine Zeile mit dem Stand; `VIDEOPFLEGE=0` schaltet den Lauf ab. Ein Klick auf ein Thumbnail öffnet direkt die Großansicht.

**Wiki (Startseite, Docmost-Nachfolger)**
- WYSIWYG-Editor (Toast UI) mit Markdown-Kürzeln direkt im Text (`# `, `- `, `> `, ` ``` `). Eine Quelltextansicht gibt es nicht – gespeichert wird trotzdem Markdown.
- Keine feste Toolbar: `/` öffnet ein Einfügemenü (Überschriften, Listen, Tabelle, Bild, Video, Datei, Audio, HTML-Baustein, Callout, Spalten, Box, Inhaltsverzeichnis, Emoji, Datum …); markierter Text bekommt eine schwebende Leiste mit „Umwandeln in …“ (Überschriften, Listen, Zitat, Code-Block, Callout, Code, Hervorheben, Hoch-/Tiefstellen), Fett/Kursiv/Durchgestrichen/Unterstrichen, Textfarbe, Link, Ausrichtung und Rückgängig/Wiederholen. Klick in Tabellen, auf Bilder, Links oder in einen Abschnitt öffnet ein Kontextmenü wie in Docmost: Zeilen/Spalten, Spaltenausrichtung, Zellen verbinden und wieder teilen (ein Zug über mehrere Zellen, dann *Zellen verbinden*; gespeichert als `@cols=`/`@rows=` vor dem Zelleninhalt, sortiert wird eine solche Tabelle nicht mehr), Bildbreite (Presets, Zahlenwert oder Ziehgriff), Ausrichtung, Alt-Text, Zuschneiden (Rahmen über dem Bild; das Ergebnis ist eine neue Datei, das Original bleibt liegen), Spaltenanzahl, Callout-Art und Emoji, Duplizieren, Löschen. Die Menüs tragen nur Symbole (eigene SVG, keine Icon-Bibliothek); markierter Text blendet das Blockmenü aus und die Formatleiste ein, und umgekehrt. Der Editor zeigt Spalten nebeneinander, Callouts als farbige Kisten – auch die einzeilige Form in einer Tabellenzelle, deren Marken dort ausgeblendet sind –, einklappbare Boxen aufgeklappt und Ausrichtung wirklich ausgerichtet – der Inhalt ist dabei gewöhnlicher Editorinhalt und wird direkt bearbeitet, ohne Dialog. Jede Spalte fließt für sich (gemessenes Layout statt geteilter Rasterzeilen), in Breite und Rinne deckungsgleich mit der Leseansicht. Auch der Zeilenfall stimmt überein: Die Leerzeile, mit der Markdown zwei Absätze trennt, ist im Editor technisch ein leerer Absatz – sie bleibt im Dokument stehen, wird aber zugeklappt. Jede darüber hinaus gesetzte Leerzeile bleibt dagegen sichtbar und wird als `&nbsp;`-Absatz gespeichert; früher schrieb der Editor dafür eine `<br>`-Zeile, und die verschluckte in der Leseansicht den folgenden Absatz. Auf schmalen Bildschirmen stehen Spalten in beiden Ansichten untereinander (ab 640 px). Blöcke lassen sich am Griff links verschieben; an einer Marke wandert der ganze Abschnitt mit. Tabellen, Spalten- und Ausrichtungsabschnitte lassen sich nicht mit Entfernen oder Rücktaste löschen – nur über ihr eigenes Menü; eine halb gelöschte Abschnittsmarke nähme beim Speichern den ganzen Abschnitt mit. Oben rechts schaltet ein Umschalter zwischen Lesen und Bearbeiten, beide in derselben Breite. Bilder per Drag & Drop, Einfügen aus der Zwischenablage sowie Kopieren und Ausschneiden.
- Ein **HTML-Baustein** (`/`-Menü „HTML einbetten“, nur mit Verwaltungsrecht im Wiki) bettet eine selbst hochgeladene, eigenständige HTML-Datei (eigenes Skript, eigenes Stylesheet – etwa eine interaktive Grafik) in den Artikel ein, in Lese- und Bearbeitungsansicht gleich; eingebunden wird sie wie ein Bild (`![Titel](baustein.html)`). Zum Rahmen wird nur eine eigene Datei unter `/media/wiki/`; eine fremde Adresse mit `.html`-Endung bleibt ein Bildverweis. Im Editor hat der Baustein wie ein Bild ein eigenes Menü (Griff oben links im Rahmen oder Klick in den Rahmen): Breite, Höhe, Ausrichtung, Titel, Ersetzen, Duplizieren, Löschen; Griffe rechts, unten und in der Ecke ziehen die Größe. Gespeichert werden die Maße in der Adresse, wie die Bildbreite: `![Titel](baustein.html#w=60%&h=420)`. Ausgeliefert wird sie in einem gesandboxten `<iframe>` (`sandbox="allow-scripts"`, bewusst *ohne* `allow-same-origin`): Das Skript darin läuft, hat aber keinen Zugriff auf Cookies, Sitzung, Speicher oder DOM von strömis.de und kann nicht aus dem Rahmen heraus navigieren – auch auf einer öffentlich freigegebenen Seite bleibt das so, denn dort erreicht der Baustein jeden Besucher ohne Anmeldung. Wer im Wiki kein Verwaltungsrecht hat, bekommt die Datei beim Hochladen abgelehnt.
- Callouts (`info`, `tip`, `warning`, `success`, `danger`, `note`) mit frei wählbarem Emoji und wahlweise einer eigenen Pastellfarbe (`farbe:mint` in der Kopfzeile; acht Töne zur Auswahl) (Auswahl aller darstellbaren Unicode-Emojis oder Eingabe über den System-Emoji-Picker). Abschnitte mit 2 bis 5 Spalten, einklappbare Boxen (Accordions; Titel und Inhalt direkt im Text bearbeitbar – im Editor zugeklappt wie im Artikel, der Pfeil vor dem Titel klappt auf) – beide ineinander verschachtelbar. Ausrichtungsblöcke (`:::align center`). Synchronisierte Abschnitte: `:::baustein <kennung>` hält einen Text an einer Stelle, `:::einbau <seite>#<kennung>` zeigt ihn auf beliebig vielen anderen Seiten – geändert wird nur in der Quelle. Vorhandene Absätze lassen sich nachträglich dazu machen (markieren → „Umwandeln in …“ → „Synchronisierter Abschnitt“), ohne dass sich am Text etwas ändert. Aufgelöst wird beim Anzeigen über die gewöhnliche Schnittstelle, damit die Leserechte der Quellseite von allein gelten; im öffentlichen Bereich erscheint nur, was dort freigegeben ist. Rückverweise zeigen der Quellseite, wer sie einbindet. Gespeichert wird Markdown mit `:::`-Blöcken; bestehende Seiten funktionieren unverändert. Tabellen, Callouts, einklappbare Boxen, Spalten und Ausrichtungsblöcke lassen sich im Editor nicht mit Entfernen oder Rücktaste löschen – nur über ihr Inline-Menü; ein versehentlicher Tastendruck würde sonst eine Marke entfernen und beim Speichern den ganzen Abschnitt auflösen.
- Die Übersicht (`/wiki`) listet jeden Abschnitt mit allem, was darunter liegt – verschachtelt bis zur dritten Ebene; tiefer steht, wie viele Seiten noch folgen. Darunter „zuletzt besucht“ und „zuletzt geändert“.
- Die erste Überschrift im Text ist zugleich der Seitentitel – wie in Docmost. Wer sie ändert, benennt die Seite um; ein eigenes Titelfeld gibt es nicht mehr. Einsortiert wird eine Seite durch Ziehen im Seitenbaum links (auf eine Seite ziehen macht sie zur Unterseite).
- Die Kopfzeile bleibt beim Scrollen stehen und ist wie in Docmost aufgeteilt: links der Pfad zur Seite mit den Symbolen der Ebenen, rechts der Umschalter Lesen/Bearbeiten, Kommentare, Teilen, ein Knopf für das Inhaltsverzeichnis und „⋯“ für alles Weitere (Verlauf, Merkliste, Beobachten, Export, Import aus einem ZIP für die Wiki-Verwaltung, Drucken, Vorlage, Duplizieren, Papierkorb). Unter der Überschrift steht, wer die Seite angelegt hat – ein Klick darauf zeigt Ersteller und Mitwirkende –, daneben ein Knopf, der rechts die Angaben zur Seite aufklappt: Herkunft, Zeitpunkte, Wörter, Zeichen, Lesezeit und die Verweise in beide Richtungen.
- Artikel mittig mit fester Lesebreite; rechts ein automatisches Inhaltsverzeichnis, die Angaben zur Seite und die Kommentare. **Auf dem Telefon** (unter 1180 px) rücken Kommentare und Angaben unter den Artikel, das Inhaltsverzeichnis entfällt; unter 800 px sitzt der Seitenbaum als Schublade hinter „☰“ in der Kopfzeile, der Pfad weicht dem Titel. Fingerziele wachsen auf Touch-Geräten, Eingabefelder haben 16 px (kein iOS-Zoom), Dialoge und Leuchtkasten füllen den Bildschirm, die Nutzerverwaltung wird zur Kartenliste. Auf **Tablets** (801–1024 px) ist der Seitenbaum höchstens 260 px breit, das Seitenpolster 24 px, die Albumleiste 340 px. **Faltgeräte** aufgeklappt (Galaxy Fold, Pixel Fold): meldet der Browser zwei Bildschirmhälften (Viewport Segments), liegt die Falz genau auf der Trennlinie – links Seitenbaum, rechts Text; auf der Karte rechts die Albumleiste; zusammengeklappt füllt die Schublade die linke Hälfte. Alles davon liegt in Media-Queries – am Rechner ändert sich nichts. Der Editor benutzt dieselbe Spalte: Kopfzeile, Titel, Autorzeile und jeder Block sitzen in beiden Ansichten auf demselben Pixel. Gemessen über ein Dokument mit Spalten, Ausrichtung, Liste, Tabelle und Bild mit Unterschrift bleibt der Unterschied unter zwei Pixeln und summiert sich nicht: Die Abschnittsmarken kosten keine Höhe, Tabellen und Bildunterschriften übernehmen die Maße der Leseansicht.
- Kommentare zu beliebigen Textstellen (Text markieren → „Kommentieren“) oder zur ganzen Seite, mit Antworten und „Erledigt“. Löschen dürfen Kommentator, Seitenersteller und Admin.
- Bearbeitungsfreigaben: Der Ersteller gibt einzelne Nutzer zum Bearbeiten frei (ohne Löschrecht); die Freigabe gilt auch für Unterseiten. Ohne Freigabe können andere Nutzer lesen und kommentieren.
- Den **Ersteller** einer Seite kann die Administration umschreiben (Klick auf „Von …“ unter dem Titel → „Ersteller ändern“). Gebraucht wird das, wenn jemand die Gliederung verlässt. Mit dem Namen wechseln auch seine Rechte: löschen und Bearbeiter freigeben.
- Öffentliche Freigabe (nur mit Verwaltungsrecht im Wiki, Menü „Teilen“): einzelne Seiten oder ganze Abschnitte inkl. Unterseiten sind dann ohne Login unter `wiki.strömis.de/<slug>` erreichbar – samt der eingebundenen Bilder und Videos. Nicht freigegebene Anhänge bleiben geschützt. In einem freigegebenen Abschnitt darf auch Unterseiten nur die Wiki-Verwaltung anlegen oder dorthin verschieben – sonst käme Veröffentlichen durch die Hintertür.
- **Lesemodus für Konten ohne Wiki-Zugriff:** Ein angemeldetes Konto mit „kein Zugriff“ im Wiki sieht unter „Wiki“ (`/wiki`, `/wiki/<slug>`) genau die Seiten, die der öffentliche Teil ohne Anmeldung zeigt – auch die Unterseiten freigegebener Abschnitte, mit ihren Bildern und Dateien, Seitenbaum und Suche –, nur eben in der eigenen Kopfleiste. Eine Zeile über dem Text sagt: „Du siehst die öffentlichen Seiten des Wikis. Für das interne Wiki schaltet dich die Verwaltung frei.“ Mehr gibt es nicht: kein Bearbeiten, Anlegen oder Löschen, kein Papierkorb, keine Versionen, Kommentare, Autorenangaben oder beschränkten Seiten und keine eingebundenen Abschnitte aus internen Seiten; ein Link auf eine interne Seite meldet „gibt es nicht, oder sie steht nur im internen Wiki“ – wortgleich für beides. Seiten, die das Konto früher beobachtet hat, melden sich nicht mehr per Mail. Der Lesemodus benutzt denselben Leser und dieselbe Schnittstelle wie der öffentliche Teil (`public.js`, `/api/public`): Was öffentlich ist, entscheidet weiter eine Stelle, und die internen Schnittstellen antworten diesem Konto wie bisher 403. `tests/test_wiki_lesemodus.py` geht dafür jede Wiki-Route durch.
- Versionsverlauf mit Wiederherstellen (standardmäßig die letzten 100 Fassungen je Seite, `WIKI_MAX_REVISIONS`), Volltextsuche, Export einzelner Seiten oder ganzer Abschnitte als Markdown beziehungsweise ZIP.
- **Import aus einem ZIP** (Wunsch vom 25.10.2026; nur die Wiki-Verwaltung, Menü „⋯“ → „Seiten aus ZIP importieren …“): Dialog „Seiten importieren“ mit Dateiwahl und „Einsortieren unter“ (eine Seite aus dem Baum oder „– oberste Ebene –“, vorgewählt die offene Seite); ein Satz sagt vorher, wenn das Ziel ohne Anmeldung sichtbar oder lesebeschränkt ist – die neuen Seiten erben das, gesetzt wird nichts. Das Ergebnis steht im selben Dialog (Seiten als Links, Hinweise), „Schließen“ öffnet die erste neue Seite. **Aufbau des ZIP** wie beim Export: Jede `*.md`/`*.markdown` (UTF-8, auch mit BOM) ist eine Seite, `A/B.md` eine Unterseite von `A.md`; ein Ordner ohne eigene `.md` wird eine Seite mit seinem Namen; Geschwister in natürlicher Reihenfolge der Dateinamen („2 …“ vor „10 …“) hinter die vorhandenen. **Titel** = erste Zeile `# …` (wie im Editor), sonst der Dateiname – dann steht `# <Titel>` vorn; höchstens 200 Zeichen. **Anhänge** kommen nur mit, wenn eine Seite auf sie verweist (Bilder werden wie beim Hochladen neu geschrieben, ohne Aufnahmeangaben; Dokumente, GIF, SVG und HTML-Bausteine unverändert; jede Datei einmal); **Videos werden übergangen** („Videos einzeln hochladen“), ebenso fremde Dateitypen und unbenutzte Dateien – das Ergebnis nennt sie. **Verweise** außerhalb von Code: `/media/wiki/<datei>` (so schreibt der Export, Eintrag `media/<datei>`) und relative Pfade zeigen danach auf die neue Datei, das Fragment (`#w=…`) bleibt; ein relativer Verweis auf eine andere importierte `.md` wird `/wiki/<neue Adresse>`; `/wiki/…`-Links, `:::einbau` und fremde Adressen bleiben, was sich nicht auflösen lässt, bleibt stehen und steht als Hinweis da. **Gleicher Titel** unter derselben Seite: Es entsteht trotzdem eine neue Seite mit eigener Adresse, die vorhandene bleibt unberührt (Hinweis im Ergebnis). Alles oder nichts: Scheitert etwas, entsteht keine Seite und keine Datei. Keine Mails an Beobachter. Höchstens 200 MB je ZIP (`WIKI_IMPORT_MB`), 2000 Einträge, 500 Seiten.
- Beim Umbenennen einer Seite ändert sich ihre Adresse, die bisherige bleibt aber gültig – vorhandene Links und Lesezeichen laufen weiter.
- **Es bearbeitet immer nur eine Person.** Wer den Editor öffnet, bekommt den Schreibplatz; alle anderen sehen in der Kopfzeile „✏ Anna bearbeitet“ und einen ausgegrauten Knopf „Bearbeiten“, der sagt, worauf zu warten ist. Entreißen lässt sich der Platz nicht – der Editor speichert von allein, und wer ihn mitten im Satz verlöre, merkte vom Verlust seiner Arbeit nichts. Jeder offene Reiter meldet sich alle 15 Sekunden; bleibt die Meldung aus, wird der Platz nach 45 Sekunden frei, und wer dann zurückkommt, erfährt, dass hier nicht mehr gespeichert wird. **Warten muss trotzdem niemand:** Wer liest, während jemand anderes schreibt, sieht dessen gespeicherte Änderungen von selbst erscheinen – der Herzschlag der Leser läuft solange alle 4 statt alle 15 Sekunden, und weicht die gespeicherte Fassung von der gezeigten ab, wird der Artikel nachgezeichnet. Die Lesestelle bleibt dabei stehen: gemerkt wird der oberste sichtbare Absatz, nicht die Bildlaufhöhe, sonst rutschte man bei jedem oberhalb eingefügten Satz weiter. Unter einer Textauswahl oder einem offenen Dialog wird nicht gezeichnet (Prüfstand: `tests/live_mitlesen.html`). Gespeichert wird nur, wenn die Fassung noch stimmt: Die Prüfung sitzt im Schreibzugriff selbst, zwei gleichzeitige Speichervorgänge können sich also nicht mehr gegenseitig überschreiben.
- Der Editor speichert von allein, kurz nach jeder Änderung – einen Speichern-Knopf gibt es nicht; der Stand steht links in der Kopfzeile. Zwischenstände füllen weder den Verlauf noch lösen sie Benachrichtigungen aus: Alle Speichervorgänge einer Bearbeitung – vom Öffnen bis zum Verlassen des Editors – gehören zu einer Fassung; jede neue Bearbeitung legt eine eigene an, auch kurz nach der vorigen. Die Post an Beobachter folgt einer eigenen Regel: Wer dieselbe Seite kurz hintereinander mehrfach bearbeitet, schreibt zwar jedes Mal eine eigene Fassung, löst aber innerhalb von zehn Minuten nur eine Nachricht aus. Einen „Verwerfen“-Knopf gibt es nur noch beim Anlegen einer neuen Seite; bei einer vorhandenen holt der Verlauf ältere Stände zurück. Eine neue Seite wird weiterhin ausdrücklich über „Anlegen“ erzeugt.
- Speichern zwei Leute dieselbe Seite, wird die zweite Änderung nicht stillschweigend überschrieben: Der Server lehnt sie ab, das automatische Speichern hält an und weist auf die zwischenzeitliche Fassung im Verlauf hin.

**Nutzer**
- Anmeldung mit E-Mail und Passwort, Passwort per E-Mail zurücksetzen. Nach zehn Fehlversuchen je Adresse oder je Absender-IP ist eine Viertelstunde Pause – gegen das Durchprobieren von Passwörtern. „Konto anfragen“: Name, Gliederung, E-Mail und Passwort sind Pflicht, eine Begründung ist optional. Die Anfrage geht per E-Mail an die Verwaltung; erst nach Freigabe ist die Anmeldung möglich (der Nutzer wird per Mail informiert). Der allererste Nutzer bekommt überall Verwaltungsrecht.
- Eigenes Zeichen: Liegt `app/static/img/maskottchen.webp` (oder .png/.jpg/.svg) bereit, steht es in Kopfzeile und Anmeldung anstelle des DLRG-Schriftzugs – 44 px in der Leiste, 96 px auf dem Anmeldebildschirm. WebP wird bevorzugt; ein knapp bemessenes Bild (rund 256 px Kantenlänge) reicht dafür und spart gegenüber einer 1024er-PNG-Vorlage rund das Vierzigfache an Übertragung.
- Profil mit Name, Gliederung, Telefon und Profilbild (quadratisch auf 256 px gebracht; es steht an den Autorenangaben der Artikel).
- **Rechte-Matrix statt Rollen:** Jedes Konto trägt je Modul eine Stufe – **kein Zugriff**, **Mitglied** oder **Verwaltung** –, gesetzt unter „Verwaltung → Nutzer“ direkt in der Tabelle oder im Nutzerdialog. Die Module: **Spots** (Mitglied: eigene Alben anlegen und bearbeiten, ein einzelnes Bild zusätzlich, wer es hochgeladen hat; Verwaltung: alle Alben), **Wiki** (Mitglied: eigene und freigegebene Seiten schreiben, alle nicht beschränkten lesen; Verwaltung: alle Seiten bearbeiten und in den Papierkorb legen, beschränkte lesen, veröffentlichen, HTML-Bausteine einstellen, Ersteller ändern), **Prüfungen** (Mitglied: Prüfungen abnehmen; Verwaltung: Kataloge pflegen und jeden Lehrgang leiten), **Material** (Mitglied: das Modul nutzen – Katalog, Suche, Profil –, Bestand nur über Freigaben je Ordner; Verwaltung, die **Material-Verwaltung**: Produktkatalog pflegen, alle Bestände aller Gliederungen, Gliederungen anlegen, jede Freigabe – prüfen nur mit Häkchen „Prüfer“, Urkundennummer und Prüffreigabe; siehe „Material“), **Verwaltung** (nur kein Zugriff oder Verwaltung: Anfragen freigeben, Nutzer anlegen, bearbeiten, deaktivieren, löschen – Inhalte gehen auf den Löschenden über –, Reset-Mail auslösen, Einstellungen). Verwaltung im Modul Verwaltung schließt alle Rechte überall ein. Neue Konten (Kontoanfrage und Nutzerverwaltung) starten als Mitglied im Modul Material und sonst ohne Zugriff – im Wiki also im Lesemodus (seit dem 18.10.2026; bis dahin Mitglied in Spots und Wiki, vorhandene Konten behalten ihre Stufen); mit Material braucht ein Konto einen Namen; wem ein Modul fehlt, sieht den Reiter nicht und bekommt auf Adresse und Schnittstelle 403 – auch die Mediendateien des Moduls. Ausnahme Wiki: Ohne Stufe dort bleibt der Reiter und führt in den Lesemodus mit den öffentlichen Seiten (siehe oben); wer gar kein Modul hat, landet dort statt auf einer Hinweisseite. Niemand kann sich selbst die Verwaltung entziehen.
- Beim Umstieg von den früheren Rollen werden sie einmalig übertragen: Administrator → überall Verwaltung, Redakteur → Verwaltung in Spots und Wiki, Nutzer → Mitglied in Spots und Wiki, das Prüfer-Häkchen → Mitglied in Prüfungen.

**Anmeldeseite**
- Slideshow mit zufälligen Bildern aus den Spots (langsam wandernd, überblendet; abschaltbar mit `LOGIN_SLIDESHOW=false`, respektiert „Bewegung reduzieren“). Die Bilder werden über signierte, 24 h gültige Links ausgeliefert. Link zum öffentlichen Wiki.

**Prüfungen** (nur mit Zugang zum Modul Prüfungen)
- Lehrgänge mit Titel, Nummer, Zeitraum, Ort, Status, Lehrgangsleitung und Referierenden (aus den Nutzern gewählt oder als Freitext für Externe). Liste mit Suche, Jahresfilter, Teilnehmerzahl, Fortschritt („18/24 Leistungen abgenommen“) und offenen Mängeln.
- Zwei Stufen innerhalb des Bereichs: **Lehrgangsleitung** (wer im Lehrgang mit dem Kennzeichen „Leitung“ eingetragen ist – mehrere Personen je Lehrgang sind möglich) und Administration legen Lehrgänge, Teilnehmende, Voraussetzungen und Leistungen an, ändern und löschen sie; alle anderen Prüfenden – etwa Referierende – nehmen Prüfungen ab und haken Voraussetzungen ab. Wer einen Lehrgang anlegt, wird automatisch seine Leitung.
- Je Teilnehmendem ein Profilbild, ein freier Kommentar der Prüfenden und das **Lehrgangsergebnis** der Leitung (bestanden / nicht bestanden). Mit dem Ergebnis sind die Prüfungsdaten der Person eingefroren – keine neuen Versuche, Medien oder Haken, bis die Leitung das Ergebnis aufhebt. Eine Person mit vermerktem Ergebnis lässt sich auch nicht löschen, und Leistungen, Kriterien oder Voraussetzungen, an denen eingefrorene Bewertungen oder Haken hängen, lassen sich weder ändern noch löschen; den Lehrgang als Ganzes darf die Leitung weiterhin löschen.
- **Diktieren per Mikrofon** an den Kommentarfeldern (Web Speech API des Browsers, Deutsch). Die Erkennung läuft im Browser – Chrome und Safari können das Audio an Google bzw. Apple senden; die Einstellung `SPRACHEINGABE` schaltet den Knopf ab.
- **Prüfungsleistungskataloge**: Vorlagen für die Prüfungsleistungen eines Lehrgangs, unabhängig von einer einzelnen Durchführung. Auch Katalog-Leistungen können eine **Kriterienliste** tragen, als reine Vorlage ohne Bewertungsteil (ein Katalog hat keine Versuche). Lesen darf jede:r Prüfer:in (Auswahl beim Anlegen eines Lehrgangs, Knopf „Kataloge“ neben „+ Lehrgang anlegen“); anlegen, ändern, löschen und die Leistungen samt Kriterien darin pflegen darf nur, wer im Modul Prüfungen die Stufe Verwaltung hat. Die Leistungen eines gewählten Katalogs werden beim Anlegen einmalig samt ihrer Kriterien in den Lehrgang **kopiert** – eine spätere Änderung am Katalog (auch sein Löschen) wirkt sich nie auf einen schon angelegten Lehrgang aus. Individuelle Leistungen lassen sich unabhängig davon jederzeit ergänzen, auch während der Lehrgang läuft.
- **Import** der Teilnehmerliste (.xlsx, etwa die ISC-Checkliste „Voraussetzungen“ mit allgemeinen Lehrgangsinformationen): Die Datei wird vorab gelesen und in einer Vorschau gezeigt – erkannte Spalten, Zuordnung (Stammdaten, Voraussetzung, weitere Angabe, ignorieren) per Auswahl korrigierbar, Warnungen zu Leerzeilen und Duplikaten. Kopfzeilen der Datei (Nummer, Titel, Zeitraum, Ort) füllen leere Lehrgangsfelder; Spalten mit ja/nein werden zu **Voraussetzungen** des Lehrgangs, bereits erfüllte Häkchen werden übernommen und als „importiert“ protokolliert. Ein zweiter Import derselben Liste aktualisiert statt zu verdoppeln. Gleichnamige Teilnehmende werden dabei nie geraten: Passen mehrere Dateizeilen auf eine Person ohne Geburtsdatum im Lehrgang, werden sie als mehrdeutig gemeldet und nicht übernommen. Der Import prüft Dateien vor dem Einlesen: höchstens 500 Archiv-Einträge und 200 MB entpackt, 20 Arbeitsblätter, 20.000 Zeilen × 300 Spalten bzw. 500.000 Felder je Arbeitsmappe (gezählt, bevor die Datei geladen wird – leere Zellen, Zeilen und die ganze Fläche verbundener Zellen, Links und Kommentare zählen mit), 2.000 Datenzeilen je Import und 50 Spalten mit weiteren Angaben (Titel 100, Werte 500 Zeichen); Überschreitungen ergeben eine Meldung mit Hinweis, was zu tun ist.
- **Voraussetzungen** je Teilnehmendem abhaken – unter jedem Haken steht klein, wer ihn wann gesetzt hat; jede Änderung bleibt im Verlauf. Teilnehmende mit offenen Voraussetzungen sind markiert.
- **Prüfungsleistungen** mit Beschreibung (Editor wie im Wiki: keine feste Toolbar, stattdessen eine schwebende Formatleiste bei Textauswahl für Überschrift/Text, Liste, fett, kursiv, Link), optionalem Zeitansatz und optionaler **Kriterienliste** (einzeln abhakbare Punkte zusätzlich zur Beschreibung); sortierbar. Die Kriterienliste lässt sich schon beim Anlegen einer Leistung mit aufbauen, nicht erst danach – als lokaler Entwurf, bis die Leistung gespeichert wird. Ein Lehrgang lässt sich samt Leistungen, ihren Kriterien und Voraussetzungs-Definitionen **kopieren** – ohne Teilnehmende und Ergebnisse.
- **Prüfungen abnehmen** in einer Matrix Teilnehmende × Leistungen, auf dem Telefon als Liste je Leistung oder je Teilnehmendem. Hat eine Leistung eine Kriterienliste, zeigt die Zelle in Matrix und „je Leistung“ „📋 erfüllt/gesamt“ (z. B. „📋 1/2“) als schnellen Indikator, ohne sie öffnen zu müssen; in „je TN“ steht dort mehr Platz zur Verfügung, deshalb erscheint direkt die volle Kriterienliste mit ✅/❌ je Punkt unter Zeit und Kommentar des letzten Versuchs; dort ist außerdem der Titel jeder Leistung grün (bestanden), rot (mangelhaft) oder unverändert (noch kein Versuch) eingefärbt. Der Bewertungsdialog hat eine **Stoppuhr** (nur bei Zeitansatz; überlebt Neuladen und Bildschirmsperre, weil der Startzeitpunkt im Browser liegt), ein immer manuell befüllbares Zeitfeld, die **Kriterienliste** der Leistung – falls vorhanden – mit einem dreistufigen Haken je Punkt (Antippen wechselt nicht bewertet → ✅ erfüllt → ❌ nicht erfüllt → nicht bewertet), große Knöpfe 👍 bestanden / 👎 mangelhaft, einen Kommentar (Pflicht bei mangelhaft) und Bilder/Videos direkt von der Kamera. Jede Bewertung trägt Prüfer und Zeitpunkt; Änderungen werden als „bearbeitet von … am …“ gekennzeichnet, der alte Stand bleibt im Verlauf.
- **Nachprüfung** als zusätzlicher Versuch; die Erstprüfung bleibt sichtbar, für die Matrix zählt der letzte Versuch.
- **Mängel / Feedback**: alle mangelhaften Leistungen je Teilnehmendem mit Kommentar, Medien, Zeit, Prüfer und Stand der Nachprüfung – filterbar und als Druckansicht für das Feedbackgespräch.
- **Druckansicht „je TN“**: In der Bewertungsansicht „je Teilnehmendem“ zeigt „🖨 Druckansicht“ alle Prüfungsleistungen der gewählten Person auf einer eigenen Seite – mit Profilbild, freiem Kommentar sowie je Leistung Ergebnis, Zeit, Kommentar und den hochgeladenen Bildern/Videos. Drucken oder als PDF speichern.
- Die Medien liegen in einem eigenen Ordner und werden nur an Prüfer ausgeliefert.

**Material** (Ausrüstungsbestand und Prüfnachweise; nur mit Zugang zum Modul Material – „Meine PSA“ auch ohne; Stand: Phase 4, Lieferung 1 (Jahresbericht, Mailfehler-Protokoll) – wartet auf Freigabe; Lieferung 2 und 2b (Sets mit Komponenten) – durch den Rückbau der Set-Funktion (25.10.2026, Schema 26) ersetzt; Feintuning nach dem Kommentar-Dokument (23.10.2026); Änderungsanträge an alle Stammdaten, Freigabe durch die zuständigen Materialwarte (24.10.2026, Schema 23; Lebensende auch nach hinten 25.10.2026, Schema 24) – wartet auf Freigabe; Wünsche vom 25.10.2026 (Norm-Zeile, Nacharbeit, Filter im Bestand, Wiki-Import) – wartet auf Freigabe; Bestandteil-Liste an normalen Produkten mit Seriennummern der Bestandteile (25.10.2026, Schema 25) – wartet auf Freigabe; Rückbau der Set-Funktion und Set-Protokolle im Prüfdurchgang (25.10.2026, Schema 26 und 27) – wartet auf Freigabe; siehe `CHANGELOG-Material.md`)
- Verwaltet PSA gegen Absturz und Seiltechnik sowie Wasser-Material (Schwimmwesten, Wasserrettungshelme, Wurfsäcke, Neopren- und Trockenanzüge) aller Gliederungen in einer Instanz. Lampen, Pumpen, Funk, Verbrauchsmaterial, Ausleihe und Fahrzeuginventar gehören bewusst nie hinein – das Modul ersetzt Prüfkarte und Excel-Liste des Materialwarts, kein Lager.
- **Rollen**: Die Stufe im Modul Material setzt die Plattform-Verwaltung in der Nutzerverwaltung wie bei den anderen Modulen. **Mitglied** heißt Zugang zum Modul (Katalog, Suchfeld, Profil, „Meine Freigaben“); Bestand sieht ein Mitglied nur über **Freigaben je Ordner** (siehe unten), die der Verwalter eines Ordners vergibt – getrennt von der Stufe. **Verwaltung** heißt **Material-Verwaltung**: Sie pflegt den Produktkatalog (Kategorien, Produkte, Herstellerdokumente, Prüfformulare, Produktmeldungen, Rückrufe), sieht und verwaltet den ganzen Bestand aller Gliederungen, legt die Gliederungen auf oberster Ebene an und vergibt jede Freigabe; die Plattform-Verwaltung (Verwaltung im Modul Verwaltung) gehört immer dazu. Änderungsanträge an Stammdaten entscheiden aber nur die Materialwarte des Ordners – auch die Material-Verwaltung nur mit eigener Freigabe „verwalten“ dort oder darüber; sie darf sie sich selbst geben (Freigaben und Journal zeigen es). Eine Gliederung in einem Ordner legt an, wer den Oberordner verwaltet. Ohne Stufe wirken weder Freigaben noch das Häkchen; die eigenen Daten bleiben erreichbar – die hinterlegte Unterschrift lässt sich im Profil entfernen, die eigene Produktmeldung löschen. Dazu das Häkchen **Prüfer** (Sachkundiger) am Konto, plattformweit und von der Plattform-Verwaltung gesetzt; die Urkundennummer trägt der Prüfer selbst im Profil ein (Abschnitt „Urkundennummer und Unterschrift“); bis dahin zeigen Profil, Artikel und Nutzerliste „Urkundennummer fehlt“. **Prüfen** darf nur, wer Stufe, Häkchen, Urkundennummer **und** eine gültige Prüffreigabe für den Ordner hat – auch Materialwarte und die Material-Verwaltung; das Häkchen setzt die Plattform-Verwaltung, die Prüffreigabe der Materialwart. Zum Modul gehört ein Name im Profil: Wer handelt, steht mit Namen im Journal und in den Protokollen, nie mit der E-Mail; ohne Namen fehlt der Reiter „Material“, und die Startseite führt ins Wiki. In der Nutzerverwaltung ist die Spalte Material eine Auswahl wie bei den anderen Modulen („–“, „Mitglied“, „Verwaltung“); darunter stehen „Prüfer“, klein „n Freigaben“ und gelb „wirkt nicht – kein Zugang“, wenn Häkchen oder Freigaben ohne Stufe dastehen. Setzt man im Dialog „Bearbeiten“ das Häkchen „Prüfer“, während Material auf „–“ steht, springt die Auswahl auf „Mitglied“ (gespeichert wird mit „Speichern“); der Dialog zeigt auch die Freigaben des Kontos. Ist das Konto heute der einzige Materialwart einer Gliederung, fragt die Nutzerverwaltung nach, bevor Material auf „–“ geht (in der Tabelle wie im Dialog) oder das Konto deaktiviert wird, und der Dialog „Löschen“ nennt es – danach verwaltet dort nur noch die Material-Verwaltung und vergibt Freigaben; „Trotzdem speichern“ speichert. Jede Änderung an Stufe, Häkchen, Urkundennummer und Freigaben steht im Journal des Moduls.
- **Freigaben je Ordner**: Wer einen Ordner verwaltet, gibt unter Bestand → Ordner → **Bearbeiten** im Reiter **Freigaben** einem Konto – auch aus einer anderen Gliederung – das Recht **lesen** (alles ansehen, CSV und Protokoll-ZIP, Lebenslauf, Journal, zugeordnete Personen; dazu **Mängel melden – das sperrt den Artikel sofort**), **prüfen** (die Prüfsicht: Artikel, Prüfungen und Durchgänge, dazu prüfen, sperren und Durchgänge führen – kein Export, kein Journal, keine Personen) oder **verwalten** (dazu Ordner und Artikel pflegen, aussondern, Personen zuordnen, Freigaben vergeben). Eine Freigabe gilt im Ordner und in allen Unterordnern; Rechte addieren sich. lesen und verwalten gelten dauerhaft oder bis zu einem Tag. Freigaben gibt es nur an Konten mit Zugang zum Modul (Stufe Mitglied oder Verwaltung). Eine Prüffreigabe wirkt nur bei Konten mit Häkchen und Urkundennummer; befristet (höchstens 24 Monate) ist sie nur für externe Prüfer – wer dort auch lesen oder verwalten hat, prüft dauerhaft, und zwar nur, solange dieses Grundrecht gilt (entzogen oder abgelaufen, wirkt die dauerhafte Prüffreigabe nicht mehr). Der letzte Tag zählt mit: Eine Freigabe „bis 31.12.“ gilt den ganzen 31.12. und endet um 0:00 Uhr deutscher Zeit. Vorlagen legen das Übliche in einem Schritt an – Führungskraft (lesen), Materialwart (verwalten), Prüfer (lesen und prüfen, dauerhaft), Materialwart und Prüfer, Externer Prüfer (nur prüfen, mit Enddatum) oder Einzeln; „bis“ steht auf dem 31.12. des Folgejahres, und „Alle Prüffreigaben verlängern bis …“ verlängert die befristeten eines ganzen Zweigs auf einmal. Ein Verwalter vergibt nie länger, als er selbst verwaltet, ändert fremde Freigaben nur, wenn er sie selbst so hätte vergeben dürfen, und kann keine Gliederung ohne einen Verwalter lassen, der mindestens so lange bleibt. Die Notiz an einer Freigabe sehen nur die Verwalter des Ordners und die Material-Verwaltung. Auf der Übersicht stehen unter **Meine Freigaben** die eigenen, gelb, was in 30 Tagen abläuft; im Ordnerkopf sieht der Verwalter, wie viele in den nächsten 30 Tagen ablaufen. Abgelaufene bleiben in der Liste stehen, bis jemand sie verlängert oder entfernt; „Meine Freigaben“ nennt bei abgelaufenen das Datum und wer verlängern kann. Ohne Freigabe sieht ein Konto keinen Bestand, und was es nicht sieht, behandelt das Modul, als gäbe es das nicht – auch in Suche, Zählungen, Exporten und Mediendateien. Oberordner ohne eigenes Recht erscheinen im Baum nur als grauer Pfad, „Gesperrt“ und „Ausgesondert“ einer Gliederung, die man nicht ganz sieht, nur mit den eigenen Artikeln. Gesperrte und ausgesonderte Artikel gehören weiter zu ihrem Herkunftsordner – für Rechte, Export und Durchgänge.
- **Verschieben zwischen Gliederungen** darf nur, wer beide Gliederungen verwaltet, oder die Material-Verwaltung. Mit einem Ordner wandern seine Freigaben (was vom alten Oberordner geerbt war, gilt am neuen Ort nicht mehr) und seine gesperrten und ausgesonderten Artikel in die Systemordner der neuen Gliederung. Verlässt ein Artikel den Bereich eines offenen Prüfdurchgangs – auch innerhalb einer Gliederung –, nimmt der Durchgang ihn mit dem Grund „verschoben am …“ aus; das Sammelprotokoll nennt dann keinen Ordner und keinen Prüfer der anderen Gliederung. Einen vorhandenen Ordner zur Gliederung machen ist ebenfalls ein Wechsel für alles darin: Das darf nur, wer die Gliederung darüber verwaltet, oder die Plattform-Verwaltung.
- **Katalog**: Kategoriebaum mit Normen und Vorgaben, Produkte (Hersteller, Modell, Bemerkung als kurzer Zusatz von höchstens 80 Zeichen, etwa die Verschlussart – überall grau direkt hinter dem Modell und vor der Artikelnummer, ohne Strich; im Katalogformat heißt der Schlüssel weiter `beschreibung`, der Import nimmt auch `bemerkung` –, Artikelnummer, Norm, Materialart, Prüfintervall, Lebensdauer) mit Dublettenprüfung auf Hersteller + Modell + Artikelnummer (Schreibweise egal, „-“ als Artikelnummer zählt als keine); jede Artikelnummer gibt es zudem je Hersteller nur einmal – bei einem anderen Hersteller ist sie ein anderes Produkt (seit dem 22.10.2026; vorher katalogweit: echte Herstellernummern wie P53 kollidieren zwischen Herstellern). Lebensdauer: Pflicht bei textil, verboten bei Metall, bei „sonstiges“ nur mit Fundstelle der Herstellerangabe. Produktbild über die vorhandene Bildverarbeitung, Herstellerdokumente (PDF/Bild oder Link) mit Version, Gültigkeitsbeginn, neuer Version, Zurückziehen und Umbenennen – ein Protokoll verweist später auf die am Prüftag gültige. Eine Dokumentdatei liegt **einmal je Inhalt** unter `media/material/dok/<SHA-256>.<Endung>` und gehört allen Dokumenten mit diesem Inhalt (Varianten, dieselbe Anleitung an vielen Produkten, Katalogimport); gelöscht wird sie erst, wenn kein Dokument sie mehr nennt – ein Dokument aus einem festgeschriebenen Protokoll nie (Schritt 18, 22.10.2026). Allgemeine Dokumente (Pflegehinweise, Anleitungen) hängen an einer Kategorie und gelten für alle Produkte darin und darunter. Listen mit eigener Herstellerspalte, sortierbar per Klick auf den Spaltenkopf; links der Kategorienbaum als Navigation. Suche serverseitig mit Trigramm-Index und Seiten. Pflegen darf nur die Material-Verwaltung. Ein Produkt bleibt auch mit Artikeln bearbeitbar; jede Änderung steht im Produktjournal, im Journal der Artikel („Produkt geändert“) und – seit dem 24.10.2026 – im Lebenslauf der Artikel (Stammdaten, Bild, Bestandteil-Liste seit dem Anlegen des Artikels; Rückrufe stehen dort in ihrem eigenen Abschnitt). Löschen lässt sich ein Produkt nur ohne Artikel, seine Materialart mit Artikeln nicht ändern. Fehlt beim Anlegen eines Artikels ein Produkt, meldet der Materialwart es mit Links, Fotos und Bemerkung; die Material-Verwaltung bekommt eine Mail (gibt es keine außer der Plattform-Verwaltung, diese), legt es an (oder ordnet ein vorhandenes zu) oder lehnt mit Begründung ab, und der Melder bekommt Bescheid. Eine Meldung sehen nur die Material-Verwaltung, der Melder und wer ihren Ordner sieht; die Mail nennt nur die Gliederung.
- **Prüfformulare**: je Kategorie ein generisches, je Produkt optional ein spezifisches, das es ersetzt; versioniert, höchstens eine Version aktiv, eine benutzte Version wird nie mehr geändert. Prüfpunkte mit Gruppe, Art (Ja/Nein, Text, Datum, Zahl, Foto, Unterschrift, Länge), Pflicht, Sollwert und „kritisch“. **Artikellänge** (seit 22.10.2026): Trägt eine Kategorie das Häkchen „Artikel haben eine Länge“ (es gilt auch für ihre Unterkategorien – etwa Seile und Meterware), bekommen Artikel ihrer Produkte das Feld „Länge (m)“ (eine Nachkommastelle, Komma oder Punkt, Anzeige „57,5 m“ im Steckbrief, in Listen, im Lebenslauf, in „Meine PSA“ und als CSV-Spalte „Länge (m)“; der Bestandsimport liest eine Spalte „Länge“ in Metern – „Länge (cm)“, andere Einheiten und „1.200“ nur als Hinweis und Bemerkung), und ein Prüfpunkt der Art „Länge“ (höchstens einer je Formular) ist in der Prüfung mit der Artikellänge vorbelegt – trägt der Prüfer einen anderen Wert ein, übernimmt das Festschreiben ihn in den Artikel (Journal „Länge geändert“, Protokoll „57,5 m → 55,0 m“). Hat jemand die Länge während der Prüfung geändert, fragt das Festschreiben nach (der Punkt zeigt die neue Länge).
- **Bestand**: Ordnerbaum, oben die Gliederungen, darunter frei verschachtelt Standorte, Fahrzeuge, Sets. Jede Gliederung bekommt die Systemordner „Gesperrt“ und „Ausgesondert“ (nicht umbenennbar, verschiebbar, löschbar; nichts kommt von Hand hinein). Artikel bekommen eine plattformweit eineindeutige Inventarnummer (`M-000001`) und – ohne Herstellernummer – eine eindeutige Seriennummer (`STR-000001`); beide werden nie wieder vergeben. Lebensende (nur textil) = Herstellung (Monat genügt) + Lebensdauer; es lässt sich vorziehen – vor der ersten Prüfung direkt, danach per Antrag, der ein vorgezogenes Lebensende auch wieder nach hinten setzen darf, höchstens bis zur Rechnung (genau die Rechnung: nicht mehr von Hand gesetzt, Schritt 24). **Die Stammdaten stehen seit der ersten abgeschlossenen Prüfung fest** (ein Entwurf zählt nicht) – sie stehen im Prüfprotokoll: Produkt, Seriennummer (auch eine STR-Nummer), Herstellung, Kauf, Erstgebrauch, Lebensende (auch vorziehen und zurücksetzen) und das Prüfintervall am Artikel (Wunsch vom 24.10.2026; vorher nur Seriennummer und Herstellung). Direkt ändern Materialwart **und Prüfer** danach nur noch Bemerkung, Länge und die nächste Prüfung (vorziehen) – Prüfer bekommen dafür „Bearbeiten“ mit genau diesen drei Feldern (vor und nach der ersten Prüfung). **Das Produkt** ändert der Materialwart bis zur ersten Prüfung im Dialog „Bearbeiten“ (Feld „Produkt“ ganz oben mit „anderes Produkt“ und der Produktsuche; ein Hinweis sagt, was der Wechsel nachzieht – Lebensende aus der Lebensdauer des neuen Produkts oder weg, die Länge fällt weg, wenn die Kategorie keine vorsieht, ein kürzeres Prüfintervall rückt die nächste Prüfung vor, Rückrufe gelten nach dem neuen Produkt; Durchgang und Zuordnung bleiben), danach per Antrag; nie mit offener Prüfung oder über die DEMO-Grenze. Nach der ersten Prüfung zeigt der Dialog „Artikel … bearbeiten“ alle freigabepflichtigen Felder oben schreibgeschützt („Seit der ersten Prüfung fest – Teil des Prüfnachweises.“); der Server lehnt eine Änderung mit 409 ab, Datenbank-Trigger fangen den Rest. Ein leeres Feld nachtragen geht dann ebenfalls nur per Antrag (auch das Herstelldatum bei Metall); **entfernen lässt sich ein Herstelldatum nach der ersten Prüfung nie**, auch nicht per Antrag. **Änderungsanträge**: Materialwart oder Prüfer beantragen mit Begründung („Änderung beantragen …“ in den Stammdaten oder im Dialog „Bearbeiten“) – alle Felder, die sich ändern sollen, in **einem** Antrag (mit Antrag-Nr.; vorbelegt mit den heutigen Werten, auch „anderes Produkt“ mit seinen Folgen); je Artikel ein offener Antrag. **Entscheiden die Materialwarte des Ordners** – wer eine eigene gültige Freigabe „verwalten“ an der Heimat des Artikels oder darüber hat, auch aus einer anderen Gliederung, auch für den eigenen Antrag; die Material-Verwaltung nur mit so einer Freigabe. Die Liste steht unter **Bestand → „Änderungsanträge“** (Knopf mit Blase: offene, die man entscheidet, ab 100 „99+“; Filter offen | erledigt | alle; die alte Adresse unter Katalog → Meldungen leitet dorthin weiter, „Produktmeldungen“ zeigt nur noch gemeldete fehlende Produkte); jeder sieht dort seine eigenen und die, die er entscheidet, die Übersicht nennt die Zahl, die Artikelseite führt Zuständige mit „Entscheiden …“ hin. Bestätigt oder abgelehnt (nur mit Begründung) wird der ganze Antrag; beim Bestätigen prüft der Server den ganzen neuen Stand noch einmal (Herstellung nicht nach Kauf, Seriennummer je Produkt eindeutig …) und verlangt, dass der Artikel noch die alten Werte trägt – sonst nur ablehnen. Danach steht alles sofort am Artikel; Journal und Lebenslauf zeigen einen Eintrag mit alten und neuen Werten, Antragsteller, Bestätiger und Begründung (wer den Artikel nur liest, sieht dort nur Felder, Werte und Zeitpunkt); festgeschriebene Protokolle behalten die alten Werte, ein später festgeschriebenes Sammelprotokoll nennt „vormals … (Änderungsantrag Nr. …)“ bei Seriennummer und Produkt. Fiele der Artikel mit neuer Seriennummer oder anderem Produkt aus einem laufenden Rückruf (oder käme hinein), sagen es Antragsdialog, Karte und Rückfrage, das Journal vermerkt es. Einen offenen Antrag **zieht der Antragsteller selbst zurück** (Rückfrage; Stand „zurückgezogen“, keine Mail). Mails an die zuständigen Materialwarte (ohne den Antragsteller; gibt es gar keinen, an die Material-Verwaltung mit dem Hinweis auf die Freigabe) und an den Antragsteller (nur, solange er den Artikel liest); verliert ein Ordner mit offenem Antrag später seinen letzten Materialwart – Freigabe entzogen, abgelaufen, Konto deaktiviert oder gelöscht, Ordner verschoben –, bekommt die Material-Verwaltung einmal je Wegfall eine Mail mit Ordner und Zahl der Anträge (Schema 29); bei DEMO, auf dev und ohne Mailserver ins Log. Die Trigger lassen nur genau die Änderungen eines bestätigten Antrags zu, und die nur einmal; weitere (Schritt 16) verhindern die Umwege, einen geprüften Artikel zu ersetzen, umzunummerieren, zu löschen oder die Materialart seines Produkts zu ändern. Anträge sind nach der Entscheidung oder dem Zurückziehen unveränderlich und unlöschbar (Trigger, Schritte 17 und 23). Mehrfachauswahl zum Verschieben, Journal mit Vorher/Nachher je Feld an Produkt, Artikel und Ordner. Links steht der Ordnerbaum als Navigation (eigene Ebene markiert); unter 1024 px Breite klappt er als Schublade hinter „☰ Ordner“ auf (ihr Kopf mit „✕“ bleibt beim Rollen oben stehen), von 1024 bis 1199 px steht er als schmalere Leiste daneben. **Artikelliste des Ordners** (Wünsche vom 25.10.2026): vorn die Spalte „Kategorie“ (sortierbar; bis 899 px Inhaltsbreite enge Tabelle, zwischen 900 und 979 px klein über dem Hersteller, als Karte klein über Hersteller und Produkt – so rollt die Liste nie seitwärts), die Filter stehen im **Filtermenü unter dem Baum** – Status (dazu „Aussonderung empfohlen“, wo es so einen Artikel gibt – meist in „Gesperrt“), Kategorie (bei gleichem Namen mit Pfad) und „Zugeordnet an“ (nur mit Grundrecht), verknüpft mit „und“, je Eintrag die Zahl mit den übrigen Filtern; über der Liste „Gefiltert: … – Filter zurücksetzen“. Als Schublade öffnet der Knopf „Filter (n)“ über der Liste sie gleich bei den Filtern, nach einer Wahl schließt sie. Die Artikelseite zeigt die Norm des Produkts in einer eigenen Zeile der Stammdaten.
- **Prüfintervall**: Herstellerseite (Produkt, sonst Kategorie) und Organisation (Artikel, sonst nächster Ordner bis zur Gliederung) – es gilt das kürzere. Ein Ordner kann verschärfen, nicht verlängern. Wird das wirksame Intervall kürzer, ziehen Fälligkeiten hinter „heute + Intervall“ auf diese Grenze vor (mit Journaleintrag).
- **Status** wird nie gespeichert, sondern abgeleitet: neu (noch keine Prüfung – die Eingangsprüfung steht aus), einsatzbereit, bald fällig (Einstellung `MATERIAL_BALD_FAELLIG_TAGE`, Vorgabe 30), überfällig, gesperrt, Lebensdauer erreicht, ausgesondert. Die **Übersicht** zeigt die Fälligkeiten je Ordner (Gliederungen mit ihren Unterordnern eingerückt: Bestand, überfällig, neu, bald fällig, gesperrt, Lebensdauer erreicht, nächste Fälligkeit; jede Zahl öffnet die gefilterte Liste), laufende Rückrufe und Prüfdurchgänge und was als Nächstes zu prüfen ist. Gesperrte und Ausgesonderte zählen bei ihrer Gliederung; „fällig“ umfasst auch „Lebensdauer erreicht“.
- **Prüfung** (nur Prüfer mit Urkundennummer und Prüffreigabe für den Ordner): jederzeit aus der Artikelansicht startbar, die erste ist immer die Eingangsprüfung. Formular = aktives spezifisches des Produkts, sonst aktives generisches der Kategorie; jeder Befund ist mit „in Ordnung“ vorbelegt, Ja/Nein-Punkte mit ihrem Sollwert. Fürs Telefon gebaut: große Umschalter je Prüfpunkt, Kamera-Knopf, feste Leiste unten mit Ergebnis und Abschluss; jede Eingabe wird sofort gespeichert. Jeder Mangel braucht ein Foto, ein kritischer Mangel oder ein erreichtes Lebensende schließt „einsatzbereit“ aus, die nächste Fälligkeit (Prüftag + Intervall) lässt sich nur vorziehen. Anhänge (Prüfkarte, Bericht) als PDF oder Foto; mehrere Fotos eines Scans werden ein PDF. Der offene Entwurf reserviert den Artikel: andere sehen „in Prüfung bei …“, eine liegen gebliebene Reservierung hebt der Materialwart auf. Abschließen heißt **Festschreiben**: Es braucht die im Profil hinterlegte Unterschrift und erzeugt das Prüfprotokoll als PDF (siehe „Nachweis“); danach ist die Prüfung unveränderlich. Unterschriftsfelder eines Formulars füllt man auf dem Signatur-Pad.
- **Sperren und Aussondern**: „instandsetzen“ sperrt und verschiebt nach „Gesperrt“ der Gliederung (Herkunft gemerkt); zurück bringt nur eine Freiprüfung mit „einsatzbereit“. Ein Prüfer kann auch ohne Prüfung sperren (Sturzbelastung, Beschädigung, Verlust, Rückruf). **Prüfer sondern nicht aus** (Wunsch vom 25.10.2026, Schema 28): Ihr Ergebnis „aussondern empfohlen“ sperrt wie „instandsetzen“; die Empfehlung steht im Prüfprotokoll, am Artikel (Hinweis und Marke „Aussonderung empfohlen“, auch in der Liste „Gesperrt“) und im Dialog „Aussondern“; die Übersicht nennt Materialwarten (und der Material-Verwaltung) die Zahl der Artikel mit Empfehlung, die sie aussondern dürfen, mit Link auf „Gesperrt“ mit gesetztem Filter „Aussonderung empfohlen“. **Aussondern darf nur der Materialwart** (Recht „verwalten“) – und nur, wenn die letzte Prüfung des gesperrten Artikels „instandsetzen“ oder „aussondern empfohlen“ ergab; nach einer Sperre wegen Sturz, Beschädigung, Rückruf oder einer Mangelmeldung also erst nach einer Prüfung, nach „Verlust“ sofort. Sonst ist „Aussondern“ ausgegraut und sagt, was fehlt. Jede Aussonderung ist ein eigener Vorgang mit Grund und Datum und eigenem, festgeschriebenem Aussonderungsprotokoll (mit seiner Unterschrift); der Artikel wandert nach „Ausgesondert“ und zählt nirgends mehr als Bestand – er gehört aber weiter zu seinem Herkunftsordner, dessen Verwalter ihn und sein Aussonderungsprotokoll weiter sehen. Prüfungen vor dem 25.10.2026 mit dem Ergebnis „aussondern“ (das damals zugleich aussonderte) heißen jetzt „aussondern (ausgesondert)“.
- **Prüfdurchgang** (Materialwart oder Prüfer eröffnet ihn für einen Ordner): alle Artikel darin und darunter auf einer gemeinsamen Liste (offen, in Prüfung bei …, erledigt, mit Grund ausgenommen); mehrere Prüfer zugleich, jeder mit eigener Urkundennummer. Abschließen erst, wenn alles geprüft oder ausgenommen ist – dann entsteht das Sammelprotokoll mit allen Artikeln, Ausnahmen, Prüfern samt Urkundennummer und Unterschrift und den Prüfsummen der Einzelprotokolle; „Abbrechen“ beendet ihn vorzeitig (offene Prüfungen laufen einzeln weiter, Ungeprüftes steht darin als „nicht geprüft“, auch im Sammelprotokoll). Seit Schema 27 bekommt beim regulären Abschluss jedes Set darunter dazu sein Set-Protokoll (siehe unten „Set-Protokolle im Prüfdurchgang“).
- **Nachweis**: Prüfer (und wer aussondert) hinterlegen ihre Unterschrift einmal im Profil (Signatur-Pad). Beim Festschreiben entsteht ein PDF/A-Protokoll (WeasyPrint) – Prüf-, Aussonderungs-, Sammel- oder Set-Protokoll mit Protokoll-ID (`P-`, `A-`, `S-`, `T-2026-000123`), Unterschrift, Anmeldung und Zeitpunkt, beim Prüfprotokoll nach dem Muster der EN-365-Karte mit Befunden, Mangelfotos, Herstellerdokumenten, Anhängen samt Prüfsumme (auf Wunsch hinten angefügt) und QR-Code zum Lebenslauf. Im Fuß jeder Seite steht „SHA-256 (erste N Bytes): …“: nachrechenbar mit `head -c N datei.pdf | sha256sum` oder auf der öffentlichen Prüfseite `/material/pruefen` (ohne Anmeldung; zeigt nur „unverändert“ oder „verändert“ und die Protokoll-ID). Die Dateien liegen schreibgeschützt unter `/data/pdf/<jahr>/`; Datenbank-Trigger weisen jede Änderung an festgeschriebenen Prüfungen und abgeschlossenen Durchgängen ab. Eine Korrektur ist eine **Berichtigung**: ein neuer Entwurf mit allen Befunden, Fotos und Anhängen, demselben Prüftag und Verweis – das Original bleibt mit seinem Protokoll erhalten.
- **Suche** nach Serien-, Inventar- und Herstellernummer mit Teiltreffern; ein eindeutiger Treffer öffnet den Artikel direkt. Jeder Artikel hat eine Adresse `https://strömis.de/m/<token>` für QR-Code, NFC- oder RFID-Tag – sie führt über die Anmeldung zum Artikel (liegt er außerhalb des eigenen Bereichs, nur zu einem Hinweis, siehe „Globale Suche“); ist er ausgesondert, gesperrt oder am Lebensende, steht das sofort groß auf der Seite. Etiketten druckt das Modul nicht: Die Adresse am Artikel kopieren und auf einen Tag schreiben oder mit einem beliebigen Etikettenprogramm als QR-Code drucken. Die Adresse ist dauerhaft – `BASE_URL` danach nicht mehr ändern, und Etiketten von dev.strömis.de nie ans echte Material.
- **Globale Suche**: Unter den eigenen Treffern bieten Trefferseite und Suchvorschläge „Außerhalb deines Bereichs nach der Seriennummer „…“ suchen“ an – zu jeder Anfrage, die dafür taugt, auch neben eigenen Treffern und wenn ein eigener Artikel genau diese Nummer hat; auch Mitgliedern und Prüfern ohne Freigabe, nicht aber der Material-Verwaltung, die ohnehin alles sieht. Nach einer Bestätigung sucht sie nur unter den Artikeln, die man nicht sieht, und zeigt bis zu zehn Steckbriefe direkt unter der eigenen Liste – ab der Trennlinie „Außerhalb deines Bereichs“ (andere Gliederungen; wer nur einen Teil einer Gliederung sieht, auch deren übrige Ordner), jeder gestrichelt umrandet und mit seiner Gliederung als Marke ganz oben: Produkt mit Bild, Inventar- und Seriennummer, Herstellung, Lebensende, ein Wort zum Sperrzustand („gesperrt“, „verloren gemeldet“ oder „ausgesondert“ – ohne Grund und Datum) und „Gehört zu <Gliederung> · <Ordner>“ – keine Prüfungen, Protokolle, Fotos, Bemerkungen oder Personen. Gesucht wird nur nach der ganzen Herstellerseriennummer (ab 4 Zeichen), nie nach den fortlaufenden Inventar- und STR-Nummern. Ein eindeutiger eigener Treffer öffnet wie bisher gleich den Artikel statt der Trefferseite – dann steht das Angebot dort unter dem Kopf des Artikels (und in den Suchvorschlägen). Ein QR-Scan an einem fremden Artikel zeigt „Dieser Artikel gehört nicht zu deinem Bereich.“ und auf Wunsch denselben Steckbrief – samt Sperrwort, damit ein Finder sieht, ob ein fremdes Seil gesperrt, verloren gemeldet oder ausgesondert ist. Gibt es die Seriennummer beim Anlegen für dasselbe Produkt schon in einem fremden Bereich, sagt die Meldung nur das – ohne Inventarnummer und Gliederung – und verweist auf die globale Suche. Alle drei stehen jedes Mal zwölf Monate mit Namen im Protokoll (Verwaltung → Nutzer, „Globale Suchen (Modul Material)“ – nur die Plattform-Verwaltung); eine Grenze, wie oft man suchen darf, gibt es nicht – die Kontrolle ist das Protokoll.
- **Export** (mit lesen oder verwalten am Ordner, beim Lebenslauf am Artikel): je Ordner im Untermenü „Export / Import“ „Artikelliste exportieren (CSV)“ (für Excel: `;`, UTF-8 mit BOM, Status, Fälligkeiten, Lebensende, zugeordnete Person, hinter „Modell“ die Spalte „Bemerkung (Produkt)“ und weiter hinten die „Bemerkung“ des Artikels – samt der von hier gesperrten und ausgesonderten Artikel) und „Protokolle exportieren (ZIP)“ (alle festgeschriebenen Protokolle dieser Artikel, die Sammelprotokolle der Durchgänge und die Set-Protokolle der Sets im Zweig, mit `Verzeichnis.csv` samt Prüfsummen; eine fehlende oder veränderte Datei steht dort mit ihrem Zustand, statt den Export abzubrechen), je Artikel „Lebenslauf (PDF)“: Stammdaten, Zustand, alle Prüfungen chronologisch mit Protokoll-ID und Prüfsumme, Durchgänge, Rückrufe und Ereignisse – auf Abruf gesetzt, nicht festgeschrieben.
- **Personenzuordnung**: PSA, die eine Person dauerhaft nutzt, ordnet ein Verwalter ihr zu – in der Artikelansicht („Zugeordnet an“ → „Zuordnen …“) oder für mehrere Artikel aus der Ordnerliste; wählbar ist jedes aktive Konto mit Namen, auch ohne Zugang zum Modul. Die Zuordnung sehen nur Konten mit lesen oder verwalten (Spalte „Person“, Filter „Zugeordnet an …“, CSV-Spalte „Zugeordnet an“) – nicht die Prüfsicht, nicht die globale Suche und nie ein Protokoll oder der Lebenslauf. Im Journal steht die Person nur als pseudonymer Verweis. Aussondern löst die Zuordnung; ein deaktiviertes Konto steht mit „(deaktiviert)“ da.
- **Jahresbericht je Zweig** (Phase 4 · Lieferung 1): Im Ordnerkopf unter „Export“ → „Jahresbericht exportieren“ – für einen Ordnerzweig (in der Regel die Gliederung) und ein Kalenderjahr: Bestand zum Stichtag heute (Status, je Kategorie, je Unterordner), Bewegungen, Prüfungen mit Prüfabdeckung und Liste der nicht geprüften Artikel, Prüfdurchgänge mit Ausnahmen, Sperren und Freigaben, Aussonderungen, Mangelmeldungen, Rückrufe, Ausblick über zwölf Monate – als Seite (mit Sprungmarken zu den Blöcken), PDF/A (nicht festgeschrieben, kein Prüfnachweis; Listen gekürzt – 500 Zeilen je Liste, 1 500 im ganzen PDF, 50 Artikel je Rückruf) und CSV-Prüfungsliste. Namen von Prüfern stehen nur mit dem Haken „Prüfer nennen“ darin (Dateiname „-mit-pruefern“); DEMO-Artikel zählen mit und sind gekennzeichnet. Für Führungskraft und Materialwart (lesen oder verwalten am Zweig) und die Material-Verwaltung.
- **Mailversand im Blick** (Phase 4 · Lieferung 1): Jede Modul-Mail (Erinnerung, Mangel, Änderungsantrag, Produktmeldung, Rückruf), die der Mailserver nicht annimmt, steht im Kasten „Mailversand“ auf der Übersicht – ohne Adressen und ohne Zugangsdaten des Mailservers, mit Empfänger, Rolle, Bezug (Link ins Modul), Betreff und der gereinigten Serverantwort; die letzten 20, „Weitere anzeigen“ für alle offenen (bis 200), „Erledigt“ je Zeile, „Alle erledigt“ mit Rückfrage im Untermenü. Die Material-Verwaltung sieht alles, Materialwarte die Zeilen der Ordner, die sie verwalten (Mangel, Antrag, Produktmeldung: die Heimat des Artikels – auch, wer nur einen Unterordner verwaltet; Erinnerung und Rückruf: je Gliederung). Erinnerungen holt der nächste Lauf nach; sonst gibt es keinen erneuten Versand (Mailtexte werden nicht gespeichert). Ohne Mailserver, unter der Umgebungssperre (dev) und bei DEMO geht nichts hinaus und nichts ins Protokoll. Zeilen bleiben 13 Monate, erledigte 3; mit dem Konto werden sie gelöscht.
- **Meine PSA und Mangelmeldung** (Phase 3 · Lieferung 1): Wem ein Verwalter Ausrüstung zugeordnet hat, sieht sie unter **„Meine PSA“** (`/material/meine-psa`) – jedes aktive Konto mit Namen, **auch ohne Stufe im Modul Material** (dann ohne Modulnavigation und Ordnerleiste). Je Artikel eine Karte: Status, nächste Prüfung, Lebensende, letzte Prüfung, Gliederung (nur der Name), Bemerkung, Sperrgrund, Produktbild (nur Web- und Vorschaufassung), Serien- und Inventarnummer, Gebrauchsanleitung, Pflegehinweis, Konformitätserklärung und Datenblatt des Herstellers, Titel laufender Rückrufe und die eigenen Meldungen – keine Ordner, keine Protokolle, keine Prüfhistorie, kein Journal. Der Eintrag „Meine PSA“ steht in der Kopfleiste, sobald etwas zugeordnet ist und das Konto nirgends im Bestand lesen darf (ohne Stufe oder Mitglied ohne Freigabe); wer liest, verwaltet oder prüft, findet seine PSA als Kasten unten auf der Übersicht. Der QR-Link `/m/<token>` der eigenen PSA führt ohne Leserecht auf ihre Karte; fremde Artikel antworten ohne Stufe weiter mit „nicht freigeschaltet“. **„Mangel melden …“** (grauer Knopf an der Karte und an der Artikelansicht) dürfen die zugeordnete Person und jeder mit lesen, verwalten oder prüfen am Artikel: Beschreibung (Pflicht, bis 2000 Zeichen) und bis zu 3 Fotos (am Telefon Kamera oder Galerie, nacheinander gesammelt; das Original mit Aufnahmeort wird sofort gelöscht, es bleiben Web- und Vorschaufassung ohne EXIF). **Jede Meldung sperrt sofort** (Systemordner „Gesperrt“, Grund „Mangel gemeldet am …“, Journal „Mangel gemeldet“ mit Namen – den sehen dort nur Prüfer und Materialwarte, sonst steht „(Person)“) – auch bei offenem Prüfentwurf; alle Texte sagen: beiseitelegen und dem Materialwart geben. Zurück nur über eine **Freiprüfung**: Mit „einsatzbereit“ hakt der Prüfer im Festschreib-Dialog jede offene Meldung einzeln ab („Gemeldeten Mangel geprüft“), dann ist sie erledigt; „instandsetzen“ lässt sie offen, eine Berichtigung gibt nie frei (und wird die Freiprüfung später zu „instandsetzen“ berichtigt, ist die Meldung wieder offen), und aussondern kann der Materialwart nach einer reinen Mangelsperre erst, wenn ein Prüfer den Artikel seither geprüft hat (der Knopf ist bis dahin ausgegraut). Sichtbar als rotes Banner am Artikel, Marke „Mangel“ in Listen und Suche, Kasten „Gemeldete Mängel“ oben auf der Übersicht (bis ein Prüfer geprüft hat) und Hinweis in der Prüfung (Prüfart „außerplanmäßig“ vorgeschlagen). **Text, Fotos und den Namen des Melders** sehen nur Prüfer (wirksame Prüffreigabe, auch der externe Prüfer) und Materialwarte des Artikels (verwalten; Material- und Plattform-Verwaltung ebenso) – und der Melder seine eigene Meldung; wer den Artikel nur liest, sieht „Mangel gemeldet am …“ ohne Text, Fotos und Namen (die Foto-Adressen antworten ihm 404), die zugeordnete Person bei fremder Meldung nur den Zeitpunkt (Entscheidung vom 21.10.2026). **Mails sofort**: an die Verwalter der Heimat (ohne sie Material-, ohne diese Plattform-Verwaltung) und an jeden Prüfer mit Prüffreigabe dort oder darüber; meldet jemand anderes die PSA einer Person, bekommt sie eine kurze Sperrmitteilung ohne Melder und Text (nicht abbestellbar – sie betrifft ihre Sicherheit). Nie an den Melder, nie an DEMO-Adressen; bei DEMO-Artikeln, auf dev (Umgebungssperre) und ohne Mailserver stehen die Mails nur im Log, und der Dialog sagt „Es ging keine Mail hinaus“. Eine offene Meldung je Konto und Artikel (dann ist „Mangel melden …“ ausgegraut), keine Tagesgrenze, kein Zurückziehen. Im **Profil** lassen sich die Erinnerungen „Deine PSA“ abbestellen.
- **Rückrufe**: Die Material-Verwaltung legt am Produkt einen Rückruf an (Titel, was zu tun ist, Link des Herstellers, optional die betroffenen Seriennummern). Er steht am Produkt, als rotes Banner an jedem betroffenen Artikel, in der Prüfung, als Marke in den Listen und auf der Übersicht; eine Mail geht je betroffenem Artikel an die Verwalter seines Bereichs (gibt es keinen, an die Material-Verwaltung – an die Plattform-Verwaltung nur, wenn es keine gibt) und an die Prüfer, die ihn geprüft haben und dort noch prüfen dürfen – jeder bekommt eine Mail mit genau den Artikeln, die er sehen darf. Liste, Zahlen und Produktseite zeigen jedem nur seinen Bereich. Gesperrt wird nicht automatisch: Prüfer sperren mit dem Grund „Rückruf“, und eine Prüfung nach dem Rückruf erledigt ihn für den Artikel ebenso. Beendet wird er mit Vermerk.
- **Erinnerungsmails** (Schalter unter „Verwaltung → Einstellungen“, Vorgabe aus – siehe „Erinnerungsmails (Modul Material)“): Jeden Morgen ab 6 Uhr bekommen die Verwalter eines Ordners eine Sammelmail, gruppiert nach Ordnerpfad – Prüfung in 30 und in 7 Tagen fällig, überfällig (einmal je Fälligkeit), Lebensende in 90 Tagen (nur textiles Material) und befristete Freigaben, die in 30 Tagen ablaufen. Jede Stufe kommt je Empfänger nur einmal. Verwaltet an einem Ordner niemand, geht die Mail an die Material-Verwaltung, ohne sie an die Plattform-Verwaltung („kein Materialwart eingetragen“). Wessen befristete Freigabe abläuft, bekommt sie zusätzlich selbst – im Abschnitt „Deine Freigaben“, mit den Namen derer, die verlängern können (wie unter „Meine Freigaben“). Zugeordnete Personen bekommen ihre eigene PSA im Abschnitt „Deine PSA“ (30 Tage vor der Prüfung, überfällig, Lebensende in 90 Tagen; abbestellbar im Profil, siehe „Meine PSA und Mangelmeldung“). Nie für DEMO-Bestand (den der Probelauf auf Wunsch zur Ansicht einbezieht). Im Dialog „Ordner bearbeiten“ lassen sich Erinnerungen je Ordner abschalten (gilt für alle Unterordner). Die Material-Verwaltung sieht unten auf der Übersicht den Stand des letzten Laufs und einen Probelauf (wer bekäme welche Mail – es geht nichts hinaus).
- **Bestandsimport** (wer einen Ordner verwaltet; im Ordnerkopf „Export / Import“ → „Bestandsliste importieren“): Eine vorhandene Bestandsliste kommt als Excel-Arbeitsmappe (.xlsx) oder CSV (UTF-8 oder Windows-1252 wie aus deutschem Excel, Trennzeichen `;`, `,` oder Tab) in den Ordner. **Ablauf**: Datei wählen oder hineinziehen – der **Probelauf** läuft sofort und schreibt nichts; er ordnet die Spalten selbst zu (Hersteller, Modell bzw. Typ bzw. Bezeichnung, Artikelnummer, Seriennummer – auch „Ser.-Nr.“, „Serien-Nummer“, „Fabr.-Nr.“ –, bisherige Inventarnummer, Ordner als Pfad unter dem Zielordner, Herstelldatum, Kaufdatum, Erstgebrauch, zuletzt geprüft, nächste Prüfung, Prüfintervall, Lebensende, Anzahl, Bemerkung – Größe, Farbe, Standort und weitere Spalten als „Titel: Wert“ in die Bemerkung); die Zuordnung lässt sich je Spalte ändern, Personenspalten (Ausgegeben an, Telefon …) lassen sich keinem Feld zuordnen – auch nicht in der Nacharbeits-CSV. Ist keine Spalte als Seriennummer zugeordnet, warnt der Probelauf zuerst (sonst bekäme jede Zeile still eine STR-Nummer) und nennt die nicht zugeordneten Spalten; übernommen wird dann nur mit einem Häkchen „Diese Liste hat keine Seriennummern …“ direkt über dem Knopf – es gilt auch für die Zeilen, die in die Nacharbeit gehen, und jeder neue Probelauf nimmt es zurück. Das **Prüfintervall** zählt in Monaten; „Jahre“ im Spaltentitel („Prüfintervall (Jahre)“, „Intervall in Jahren“) oder am Wert („1 Jahr“, „0,5 Jahre“) gilt, ebenso „jährlich“, „halbjährlich“, „2x jährlich“, „alle 6 Monate“; eine 1 oder 2 ohne Einheit kommt in die Nacharbeit (Monate oder Jahre?), ein kürzeres Intervall als das wirksame wird mit Hinweis am Artikel gespeichert. „1“, „01“, „1,0“ und „1 Stk.“ sind ein Artikel, größere Anzahlen Sammelzeilen. Dann **„Übernehmen: n Artikel anlegen, m Zeilen in die Nacharbeit“** – in einer Transaktion. Die Tabelle „angelegt“ nennt je Zeile die neue Inventarnummer zum Beschriften (alte Nummern stehen nur in der Bemerkung und sind nicht suchbar). Importierte Artikel stehen auf **„neu“**; die Fälligkeit kommt aus „nächste Prüfung“ bzw. „zuletzt geprüft“ + Intervall (höchstens heute + Intervall), ohne beides ist die Eingangsprüfung sofort fällig. Zeilen ohne Herstellerseriennummer bekommen eine Seriennummer vom System (STR-…). Was die Liste sagt, aber nicht übernommen wird (unlesbare Daten, ein Lebensende bei Metall), steht als „… laut Liste: …“ in der Bemerkung. Was schon im Bestand steht (Produkt und Seriennummer), wird übersprungen, nie aktualisiert; dieselbe Datei in denselben Ordner wird 10 Minuten lang abgelehnt – der Probelauf sagt dann, ab wann es wieder geht, und bietet kein „Übernehmen“ an. Stehen Zeilen derselben Datei (gleiche Prüfsumme) noch in der Nacharbeit, ersetzt ein erneutes Hochladen sie über die Zeilennummer, statt sie zu verdoppeln; Zeilen ohne Seriennummer, die damals schon angelegt wurden, entstünden dagegen noch einmal (der Probelauf sagt es). Produkte werden nie geraten: nur gleicher Dublettenschlüssel, gleiche Artikelnummer beim gleichen Hersteller (trägt sie mehr als ein Hersteller und die Liste nennt keinen davon, geht die Zeile in die Nacharbeit) oder Hersteller + Modellname bei genau einem Produkt (ein Grundprodukt mit Varianten „Modell | Zusatz“ ist mehrdeutig, auch ohne Artikelnummern); dieselbe Seriennummer bei zwei Varianten desselben Herstellers in einer Datei geht in die Nacharbeit. Der Import legt keine Produkte und keine Ordner an. **Grenzen**: höchstens 5 MB (xlsx entpackt 10 MB, CSV 10 000 Zeilen), 2000 Datenzeilen, 300 Spalten; je Arbeitsprozess ein Import gleichzeitig. **Nacharbeit**: Was nicht sicher passt (Produkt unbekannt oder mehrdeutig, Seriennummer unbrauchbar oder zu kurz, Pflichtdatum fehlt, Ordner unbekannt, Sammelzeile „Anzahl 10“, Dublette), steht in der Nacharbeit des Zielordners – unten auf derselben Seite, mit Hinweis im Ordnerkopf und auf der Übersicht. Dort ordnet man Produkte je Angabe oder zeilenweise zu (Größen, Varianten), meldet ein fehlendes Produkt (die Material-Verwaltung legt es gleich im Katalog an), prüft erneut und übernimmt oder verwirft. Je Produktangabe eine Karte: „Produkt zuordnen …“ – danach öffnet sich gleich die Prüfung dieser Zeilen mit „k Artikel übernehmen“ (rot) oder „Abbrechen“; eine zugeordnete Karte (oder eine eingepflegte Meldung) trägt dafür auch „Übernehmen …“ (Wünsche vom 25.10.2026). Die Material-Verwaltung legt ein fehlendes Produkt mit „Im Katalog anlegen …“ an (danach dieselbe Prüfung), alle anderen Verwalter melden es mit **„Fehlendes Produkt melden …“** – vorbelegt mit Hersteller, Modell, Artikelnummer und einer Bemerkung (Satz zum Import und bis zu fünf Bemerkungen der Zeilen, ohne Serien- und Inventarnummern); Norm und Kategorie kennt der Import nicht. Werte korrigiert man in der CSV („Mehr → Als CSV herunterladen“, Spalte „Nacharbeit-Nr.“ nicht ändern) und lädt sie als neue Liste hoch – die alten Zeilen werden dabei erledigt, auch zweimal hochgeladen entsteht nichts doppelt. **Offene Zeilen verfallen einen Monat nach dem Import** (danach verworfen, Werte gelöscht); eine vorher heruntergeladene CSV prüft solche Zeilen beim Hochladen wie neue – von Hand verworfene bleiben erledigt (Nacharbeit-Nr. leeren, um sie doch zu übernehmen). Gespeichert werden nur zugeordnete Spalten und nur, solange die Zeile offen ist; der Dateiname steht nur am Import und im Ordnerjournal; beim Löschen eines Kontos wird sein Name dort „(gelöschtes Konto)“. Ein Ordner mit offener Nacharbeit lässt sich nicht löschen.
- **Prüfanleitung aus dem Wiki**: An jeder Formularversion kann die Material-Verwaltung eine Wiki-Seite als Prüfanleitung verknüpfen (Formular → „Prüfanleitung im Wiki“ → „Ändern …“) – nur mit mindestens Stufe Mitglied im Wiki; ohne sie sieht sie die Verknüpfung und den Hinweis darauf. Auch an benutzten Versionen (die Verknüpfung gehört nicht zum Prüfinhalt); neue Versionen erben sie, der Katalogaustausch nimmt sie nicht mit. In **offenen Prüfungen** steht im Kopf „Prüfanleitung aus dem Wiki“ zum Aufklappen: eingeblendet wird der Abschnitt unter der ersten Überschrift „Prüfung“ der Seite (bis zur nächsten gleich hohen Überschrift), darunter der Link zur ganzen Seite; ohne solchen Abschnitt nur der Link. **Wer sieht was**: jeder nur, was er im Wiki lesen darf – mit Wiki-Stufe nach den Rechten des Wikis, ohne Wiki-Stufe (das sind alle neuen Konten) nur öffentliche Seiten; wer die Seite nicht lesen darf, sieht nur „Zu diesem Formular gibt es eine Prüfanleitung im Wiki, die du nicht lesen darfst.“, nie den Titel. Anleitungen für alle Prüfer gehören deshalb in den öffentlichen Teil des Wikis. Der eingeblendete Abschnitt ist streng gereinigt und abgeschirmt (er kann die Prüfung nicht verändern). Festgehalten wird die Anleitung nirgends – nicht im Protokoll, nicht im PDF; an abgeschlossenen Prüfungen erscheint sie nicht.
- **Austritt und Löschen**: Beim Austritt 1. die PSA zurücknehmen (Zuordnung lösen), 2. das Konto deaktivieren (seine Freigaben wirken dann nicht mehr), 3. nach Klärung offener Prüfungen löschen – der Dialog „Löschen“ nennt vorher, was im Modul folgt. Beim Löschen entfernt die Anwendung Freigaben und Zuordnungen (je mit Journaleintrag), setzt offene Entwürfe auf „(gelöschtes Konto)“ ohne Urkundennummer (die Reservierung hebt der Materialwart auf), nimmt den Namen aus Produktmeldungen und Suchprotokoll und löscht die Zeilen des Kontos im Erinnerungslog und im Mailfehler-Protokoll (Arbeitsdaten, sonst nach 13 Monaten weg). Festgeschriebene Prüfungen, Aussonderungen, Durchgänge, Rückrufe, Mangelmeldungen und das Journal behalten die Namen der Handelnden – Nachweis nach EN 365 (der Dialog „Löschen“ nennt die Zahl der Mangelmeldungen, die den Namen behalten). **Prüfnachweise werden unbefristet aufbewahrt** (Entscheidung des Betreibers vom 18.10.2026): Prüfungen samt Befunden, Befundfotos und Anhängen, Aussonderungen, Prüf-, Aussonderungs- und Sammelprotokolle, Durchgänge mit Geprüftem, das Journal und die Herstellerdokumente, die ein Protokoll nennt, löscht die Anwendung nie – auch nicht nach der Aussonderung oder mit dem Konto des Prüfers; Artikel, Ordner, Durchgänge und Kategorien, an denen ein Nachweis hängt, lassen sich nicht löschen. Verwerfen lassen sich nur offene Entwürfe. Betroffene (wer eine Freigabe hatte, wem etwas zugeordnet war) stehen im Journal nur unter einer Zufallskennung, die mit dem Konto verschwindet. Das ist **Pseudonymisierung, keine Anonymisierung**: Aus dem Zusammenhang (Zeitpunkt, wer gleichzeitig handelte) bleibt ein Rückschluss möglich. Die stündliche Sicherung `~/data.bak` (siehe „Daten und Sicherung“) hält nur den Stand der letzten vollen Stunde – Gelöschtes ist spätestens nach einer Stunde auch dort weg; weitere Kopien (etwa Snapshots des Hosters) halten es bis zu ihrer eigenen Frist. Vorschlag für das Verfahrensverzeichnis der Gliederung (abstimmen und juristisch prüfen lassen): Zweck Prüfnachweis der PSA und Materialverwaltung; Kategorien Konto, Rolle, Urkundennummer, Unterschrift, Zuordnung PSA ↔ Person, Freigaben, Suchprotokoll, Mangelmeldungen (Beschreibung, bis 3 Fotos ohne Ortsangaben, Melder, Zeitpunkt; unbefristet mit dem Artikel), Mails an Zugeordnete (Erinnerungen „Deine PSA“ abbestellbar, Sperrmitteilung nicht; auch an Konten ohne Modulstufe; Erinnerungslog 13 Monate; Mailfehler-Protokoll: Arbeitsdaten, 13 Monate, mit dem Konto gelöscht); Empfänger Verwalter und Prüfer des Ordners, Material-Verwaltung, Plattform-Verwaltung, die zugeordnete Person (nur ihre eigene PSA); Maßnahmen Pseudonymisierung der Betroffenen im Journal, Löschung des Kontos; Fristen: Suchprotokoll zwölf Monate, Sicherungen mit ihrer Frist (trägt der Betreiber ein), Prüfnachweise unbefristet, auch nach der Aussonderung (Entscheidung des Betreibers vom 18.10.2026 – die Begründung der unbefristeten Speicherung im Verfahrensverzeichnis bitte juristisch prüfen lassen).
- **Sets als Ordner** (Rückbau der Set-Funktion, Wunsch vom 25.10.2026, gebaut – wartet auf Prüfung und Freigabe; **Schema 26**): Ein Set ist wieder ein Ordner der Art „Set“ (Rucksack, Kiste, Beutel) im Bestand – kein Katalogprodukt mit Teilen mehr. „Set anlegen“, Set-Artikel mit Teilen, „Set prüfen“, Teile tauschen, entnehmen oder einsetzen, „Stückliste übertragen“ und die Set-Meldung gibt es nicht mehr; „Fehlendes Produkt melden“ meldet nur ein Produkt. Herstellersets stehen als Produkt mit Bestandteil-Liste im Katalog (unten). Die Katalogdatei lehnt `"set": true` als Fehler dieses Produkts ab. Schritt 26 hat den Altbestand auf dev umgestellt: Teile sind eigene Artikel im selben Ordner (Gesperrte bleiben gesperrt, bis ein Prüfer frei prüft), Set-Produkte normale Produkte mit ihren Text-Positionen; festgeschriebene Set-Protokolle bleiben Datei und Prüfsumme. Einzelheiten und Rückweg: `CHANGELOG-Material.md`, „Rückbau der Set-Funktion“.
- **Set-Protokolle im Prüfdurchgang** (Wunsch vom 25.10.2026, gebaut – wartet auf Prüfung und Freigabe; **Schema 27**): Schließt man einen Durchgang regulär ab, bekommt jedes Set (Ordner der Art „Set“) unterhalb des Durchgangsordners, in dem mindestens ein Artikel geprüft wurde, zusätzlich zum Sammelprotokoll ein eigenes **Set-Protokoll** (T-<Jahr>-<Nr>) – „wie ein Durchgang nur für dieses Set“: alle Artikel darunter (auch die innerer Sets), Ergebnisübersicht, Prüfer dieses Sets mit Unterschrift, „Teil von Sammelprotokoll S-…“. Nicht beim Abbruch. Im Sammelprotokoll stehen die Artikel eines Sets zusammen unter Zwischenzeilen (je Set von außen nach innen, „(Fortsetzung)“ beim Rückweg in ein äußeres Set, „Außerhalb von Sets“ danach), dahinter das Verzeichnis der Set-Protokolle mit Prüfsumme. Die Durchgangsseite zeigt die Set-Protokolle und „Alle Protokolle (ZIP)“ (Sammelprotokoll, Set-Protokolle, Verzeichnis.csv), die Ordnerseite eines Sets den Abschnitt „Set-Protokolle“ (bzw. „Set- und Sammelprotokolle“). Öffnen darf ein Set-Protokoll, wer den Durchgang sieht oder das Set lesen darf – auch nach dem Verschieben des Sets in eine andere Gliederung (vom Nutzer bestätigt); die Prüfseite erkennt es. Die PDFs entstehen vor dem kurzen Festschreiben ohne Schreibsperre – ein Abschluss mit vielen Sets hält die übrige Plattform nicht auf.
- **Produkte mit Bestandteil-Liste** (Wunsch vom 25.10.2026, gebaut – wartet auf Prüfung und Freigabe; **Schema 25**): Herstellersets kommen als normale Produkte mit einer Liste „Bestandteile“ (je Position Bezeichnung und Anzahl, nur Text, ohne Teil-Artikel); pflegen darf sie die Material-Verwaltung. Im Produktdialog hat jedes Produkt die Reiter „Produkt“ und „Bestandteile“; die Produktseite zeigt den Abschnitt „Bestandteile“ („Bestandteile bearbeiten“), die Artikelseite, Meine PSA und das Lebenslauf-PDF die Zeile „Bestandteile“. Jede Prüfung fragt je Position „vorhanden/fehlt“ ab – „fehlt“ ist ein Mangel (Foto und Bemerkung). **Seriennummern der Bestandteile**: am Artikel je Stück freiwillig, beim Anlegen und bis zur ersten Prüfung direkt (Dialog „Bearbeiten“), danach trägt sie der Prüfer in der Prüfung ein (Protokoll „alt → neu“) oder man beantragt sie; die Suche findet den Artikel auch über sie, Rückrufe treffen Bestandteile nicht. Die Katalogdatei kennt `bestandteile` (Bericht „Bestandteil-Listen“; Vorlage `docs/material-katalog-bestandteile-vorlage.json`).
- Katalogimport für die Ergebnisse aus Phase 0: `flask --app "app:create_app()" material import-catalog datei.json` (Format in `CHANGELOG-Material.md`, Vorlage mit Kategorien und Normen in `docs/material-katalog-vorlage.json`).
- **Katalog von dev in die Produktion**: Auf dev Katalog → „Katalog exportieren“ (oder `material export-catalog katalog.zip`) – ein ZIP mit Kategorien, Produkten samt Bild und Herstellerdokumenten und den Prüfformularen, ohne DEMO-Einträge, ohne Bestand, Prüfungen, Meldungen und Rückrufe. In der Produktion Katalog → „Katalog importieren“: erst ein Probelauf mit Bericht (neu, geändert, unverändert, Warnungen zu vorhandenen Artikeln), dann „Übernehmen“ (oder `import-catalog katalog.zip --trocken`, danach ohne `--trocken`). Kategorien und Produkte tragen eine dauerhafte Katalogkennung – umbenennen oder verschieben auf dev kommt als Änderung an, nicht als Dublette. Der Import löscht und deaktiviert nie etwas.
- **Katalogimport im Hintergrund** (24.10.2026): Probelauf und Übernehmen laufen als Auftrag auf dem Server. Der Dialog lädt die Datei hoch (mit Fortschritt), zeigt dann Phase und Zahlen („Datei prüfen“, „Probedurchgang“, „Dateien ablegen n von m“, „Datenbank schreiben“) und am Ende den Bericht; „Übernehmen“ nimmt die Datei des Probelaufs (sie liegt eine Stunde bereit, kein zweiter Upload). Der Dialog darf zu – oben auf der Katalogseite steht ein laufender oder am selben Tag beendeter Import mit „Stand ansehen“ bzw. „Bericht ansehen“. Es läuft immer nur ein Katalogimport (ein zweiter Start bekommt die Meldung mit dem laufenden). Endet der Server mitten im Lauf (Neustart, Deploy), zeigt der Auftrag nach spätestens 30 s „abgebrochen“. Die Datenbank schreibt der Import ganz oder gar nicht; schon abgelegte Bilder und Dokumente räumt der Server weg – höchstens die eine Datei, die er im Moment des Abbruchs gerade schrieb, kann unter `media/material` liegen bleiben (mit nichts verknüpft, nie angezeigt; ein Dokument heißt nach seinem Inhalt und wird beim nächsten Lauf wiederverwendet). Brach ein „Übernehmen“ ab, bevor es gespeichert hatte, liegt die Datei des Probelaufs wieder eine Stunde bereit und „Übernehmen“ geht noch einmal; sonst zeigt ein neuer Probelauf mit derselben Datei, ob noch etwas fehlt. Vor dem Hochladen fragt der Dialog, ob schon ein Import läuft, und lädt dann gar nicht erst hoch; nach 100 % steht „Datei wird abgelegt …“, bis der Server antwortet – wer da schließt, bricht nichts mehr ab. Ein neuer Import löscht die Datei eines älteren Probelaufs (dessen „Übernehmen“ ist damit überholt); reicht der Platz auf dem Server nicht für die Datei plus 64 MB Reserve, lehnt er mit 507 und den Zahlen ab. Der Auftrag nennt das Konto, das ihn gestartet hat, nur über den pseudonymen Kontoverweis wie das Journal – nach dem Löschen des Kontos steht dort „(gelöschtes Konto)“, und niemand sonst kann seinen Probelauf übernehmen (Nachbesserung nach der Sicherheitsprüfung, 24.10.2026). Zwischendaten liegen unter `data/katalog-import/` (nur für den Container lesbar, nach 7 Tagen weg). Die Zeitgrenze des Reverse-Proxys gilt für den Import nicht mehr, nur noch für das Hochladen selbst. Die Kommandozeile bleibt synchron.
- **Update auf Schritt 18 (Herstellerdokumente einmal je Inhalt, 22.10.2026)**: Beim ersten Start danach führt die Anwendung die vorhandenen Dokumentdateien unter `media/material/dok` einmal zusammen – jede bekommt den Namen ihrer Prüfsumme (aus der Datei gerechnet, nicht aus der Datenbank), gleiche Inhalte werden eine Datei, die Datenbank bekommt die neuen Namen samt Prüfsumme und Größe; die alten Namen verschwinden erst nach dem Commit; ein Abbruch vor dem Commit lässt beide Namen stehen und der nächste Start holt es nach, ein Abbruch danach lässt die alten Namen als Dateien ohne Zeile zurück, die der nächste Start aufräumt. Das Log sagt dann einmal `Herstellerdokumente einmal je Inhalt (Schritt 18): N Dateien → M, X MB frei; …`. Eine Zeile, deren Datei fehlt, behält ihren Namen und steht als Warnung im Log (`Dokumentdatei fehlt unter media/material/dok: …`). Jeder spätere Start räumt den Ordner unter `media/material/dok` nur noch auf: Dateien ohne Zeile, deren Inhalt unter seinem Inhaltsnamen liegt, und Zwischendateien (Name mit Punkt davor) älter als ein Tag gehen weg (`media/material/dok aufgeräumt: …` als Info); andere Dateien ohne Zeile bleiben liegen und stehen als Warnung im Log (`media/material/dok: n Dateien ohne Zeile (x MB) – sie bleiben liegen …`) – dann nachsehen, was da liegt (22.10.2026). Ist `media/material/dok` beim Start nicht erreichbar, geschieht nichts, die Anwendung startet trotzdem, und das Log warnt (`… nicht erreichbar – die Zusammenführung … wartet auf den nächsten Start`). Von Hand, mit Bericht (Dateien und Bytes vorher/nachher, fehlende Dateien, Dateien ohne Zeile, entfernte Zwischendateien): `docker compose exec -e VIDEOPFLEGE=0 stroemis flask --app "app:create_app()" material dok-zusammenfuehren --probe` (rechnet nur) bzw. ohne `--probe`. Vorher wie immer die stündliche Sicherung abwarten oder `data/` sichern.
- **Inbetriebnahme in der Produktion** (nach dem Update auf Phase 2): Gibt es noch keine Gliederung, vergibt die Migration keine Freigaben, und nur die Plattform-Verwaltung hat das Modul. 1. In der Nutzerverwaltung der Material-Verwaltung die Stufe „Verwaltung“ und den Mitgliedern der Gliederung „Mitglied“ geben (neue Konten haben „Mitglied“ schon), Prüfern dazu das Häkchen „Prüfer“; alle brauchen einen Namen. 2. Als Material-Verwaltung unter Material → Bestand „Gliederung anlegen“ wählen – danach öffnet sich „Ordner bearbeiten“ im Reiter „Freigaben“ mit der Vorlage „Materialwart“: im selben Schritt den ersten Materialwart wählen (die Personensuche findet nur Konten mit Stufe Mitglied oder Verwaltung). 3. Ab da verwaltet die Gliederung ihren Ordner selbst: Der Materialwart vergibt die weiteren Freigaben, Prüfern die Prüffreigabe (Vorlage „Prüfer“ oder „Materialwart und Prüfer“); die Urkundennummer tragen Prüfer selbst im Profil ein. Wo es schon Gliederungen gibt (etwa auf dev), macht die Migration aus den bisherigen Stufen Freigaben an jeder Gliederung und gibt jedem Konto mit Häkchen „Prüfer“ eine Prüffreigabe – dauerhaft, wo es dort auch lesen oder verwalten hat oder Plattform-Verwaltung ist, sonst (externe Prüfer ohne Stufe) bis zum 31.12. des Folgejahres; diese rechtzeitig mit „Alle Prüffreigaben verlängern“ verlängern, Ablaufmails kommen erst mit Lieferung 2. Schritt 10 der Migration setzt danach die Stufen: bisherige Produktkatalogpfleger und die Plattform-Verwaltung werden Material-Verwaltung (und sehen damit alle Bestände), wer eine Stufe aus Phase 1, eine Freigabe oder das Häkchen „Prüfer“ hat, wird Mitglied.

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

Beide Hostnamen zeigen auf denselben Container: Anfragen mit dem Host `wiki.strömis.de` (`PUBLIC_HOST`) landen automatisch im öffentlichen Bereich (intern `/oeffentlich/…`), alles andere bleibt die interne Plattform. Dafür braucht die Subdomain einen DNS-Eintrag und ein Zertifikat (Caddy holt es automatisch).

Uploads bis 5 GB: bei nginx/Traefik `client_max_body_size`/`maxRequestBodyBytes` und die Timeouts entsprechend erhöhen (Gunicorn im Container wartet bis zu 60 Minuten). Der Katalogimport (Modul Material) wartet seit dem 24.10.2026 nicht mehr auf das Ende des Imports: Nach dem Hochladen kommt die Antwort sofort, der Import läuft im Hintergrund – die Antwort-Zeitgrenze des Proxys spielt für ihn keine Rolle mehr, nur die für den Upload. Der Container wertet `X-Forwarded-Proto/For/Host` aus (ProxyFix), damit Links und sichere Cookies stimmen. `docker-compose.yml` veröffentlicht Port 8080 auf allen Schnittstellen, damit auch ein Proxy auf einem anderen Rechner ihn erreicht. Wer den Container direkt erreicht, könnte diese Kopfzeilen selbst setzen und damit die Anmeldebremse je IP umgehen – und Docker öffnet Ports an einer `ufw`-Firewall vorbei. Den Port deshalb in der Firewall des Anbieters nur für den Proxy freigeben; läuft der Proxy auf demselben Host, genügt `"127.0.0.1:8080:8080"` in der Compose-Datei. Der Container läuft ohne Capabilities und ohne Rechtegewinn (`cap_drop`, `no-new-privileges`), und sein Wurzeldateisystem ist schreibgeschützt (`read_only`): Beschreibbar bleiben nur das Datenvolumen `/data` und ein flüchtiges `/tmp` für Gunicorns Prozess-Lebenszeichen, den Schriften-Zwischenspeicher von Fontconfig und die Zwischendateien von WeasyPrint beim Erzeugen eines Protokolls (je Protokoll einige 100 kB, danach gelöscht).

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

`GET /healthz` antwortet ohne Anmeldung mit `{"ok": true}` – darauf setzt der `HEALTHCHECK` des Containers auf (alle 30 s, `docker ps` zeigt den Zustand). Die Daten liegen im Volume unter `/data`: `stroemis.db` (SQLite mit WAL), `media/` (Originale, Web-Größen, Thumbnails, Wiki-Anhänge, Profilbilder), `pdf/` (festgeschriebene Protokolle des Moduls Material) und `secret_key`. Für eine Sicherung genügt es, dieses Volume zu kopieren – am besten bei gestopptem Container.

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
  (bestätigt, abgelehnt, zurückgezogen, offen – jeder Zustand kommt vor). Ein gewöhnlicher Mangel (instandsetzen) liegt nur
  auf einem nicht kritischen Prüfpunkt, ein kritischer führt zur Aussonderung – seit Schema 28 empfiehlt der Prüfer
  sie („aussondern empfohlen“, sperrt), der Materialwart sondert danach aus (nach Verlust direkt); beim Lebensende steht
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
  auch unter dem älteren Namen „Bandmaterial“ –, Punkte wörtlich mit Gruppe, Soll und „kritisch“; Fundstelle je Punkt
  in der Datei, Quellen mit Version im Bericht – Petzl, „Überprüfung von PSA – Prüfbericht/Vorgehensweise bei der
  Überprüfung“ je Produktgruppe, z. B. Gurte 110526, Karabiner 260625, Seile 071215; Abseilachten und Kantenschutz mit
  der nächstliegenden Vorlage), sonst ein Platzhalter (Ja/Nein, Text, Zahl, bei Artikellänge „Länge (m)“) an der
  obersten Kategorie ohne Formular. Echte Formulare bleiben unberührt.
- **Konten** (nur Modul Material, Passwörter nur in der Ausgabe; gibt es ein DEMO-Konto mit der Adresse schon, übernimmt
  der Lauf es nur, wenn es aktiv und freigeschaltet ist und die Stufe seiner Rolle hat – unverändert samt Passwort und
  Rollen, Abweichungen nennt der Bericht; eine offene Kontoanfrage oder ein deaktiviertes Konto mit einer dieser Adressen
  lässt ihn vor jedem Schreiben abbrechen – dann unter Verwaltung → Konten ablehnen bzw. selbst einstellen):
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

1. **Katalog exportieren** (Katalog → „Katalog exportieren“ oder `material export-catalog`) und das ZIP aufheben – er
   ist es, der später in die Produktion geht. Der Beispielbestand und seine DEMO-Formulare kommen mit keinem Export mit.
2. Wissen, was danach gilt: Jede benutzte **Formularversion ist „benutzt“** und lässt sich nur noch über eine neue
   Version ändern. Jedes Produkt mit Artikeln lässt sich **nicht mehr löschen und seine Materialart nicht mehr
   ändern**; seine Kategorie lässt sich nicht mehr löschen. Der Bestand lässt sich **nicht entfernen** – zurück geht es
   nur, indem man das Modul auf dev zurücksetzt („Modul Material auf dev zurücksetzen“) und den Export importiert.

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
seine Ausgabe – mit den Passwörtern – ist dann verloren (Passwörter dann unter Verwaltung → Konten neu setzen).
Abbrechen geht nur so (der laufende Vorgang rollt samt Protokolldateien zurück):

```bash
docker exec stroemis-dev sh -c 'kill -TERM "$(cat /tmp/bb/pid)"'
```

Nach einem Abbruch bleibt ein Teilbestand, und kein weiterer Lauf vervollständigt ihn: Er meldet „unvollständig“ mit
Rückgabewert 1 und legt nichts an. Neu geht es dann nur, indem man das Modul auf dev zurücksetzt und danach den
Katalog-Export importiert.

### Modul Material auf dev zurücksetzen (nur dev)

`flask material dev-zuruecksetzen` leert das Modul Material auf dev, um es von null an zu testen: Katalog, Ordner und
Gliederungen, Bestand, Prüfungen samt Protokollen, Durchgänge, Importe, Rückrufe, Anträge, Meldungen, Journal,
Erinnerungslog und Mailfehler-Protokoll (alle Tabellen `mat_*` samt Triggern und Volltextindizes) und die Dateien unter
`media/material` und `pdf/`. **Es bleiben** die Konten (samt Modulstufe, Häkchen „Prüfer“, Urkundennummer, Unterschrift
und PSA-Mails), Wiki, Spots, das Prüfungen-Modul und die Einstellungen (Verwaltung → Einstellungen). Vorher sichert der
Befehl die ganze Datenbank (Online-Backup, wie die stündliche Sicherung) und **verschiebt** die Medien des Moduls in
einen Sicherungsordner – scheitert die Sicherung, löscht er nichts. Danach legt er das Schema des Moduls frisch an, wie
eine neue Installation (Schemaversion 21), und leert `data/katalog-import/` (Aufträge des Katalogimports im
Hintergrund). Läuft gerade ein Katalogimport, bricht er vorher ab (Rückgabewert 1, nichts geändert); während des Laufs
bekommt ein Import-Start „läuft schon“. Wer den Katalog behalten will: vorher Katalog → „Katalog exportieren“, danach
importieren.

Er wirkt nur, wenn `STROEMIS_NAME` auf `-dev` endet (setzt `dev-einrichten.sh`, dieselbe Regel wie die Sperre der
Erinnerungsmails), `BASE_URL` in der `.env` **und** unter Verwaltung → Einstellungen auf eine Adresse der Entwicklung
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
  bleibt in ihr stehen. Deshalb **löschen, sobald der Neustart und ein erster Test geklappt haben, spätestens vor
  Lieferung 3**: `rm -rf data/sicherung-material-…` (Befehl und Ordnername stehen in der Ausgabe und in `LIESMICH.txt`;
  ggf. mit `sudo`). Der Ordner ist nur für seinen Besitzer lesbar (0700, Kopie 0600). Jeder Lauf und jeder Probelauf
  nennt die älteren Sicherungen mit Datum und Größe.
- **Platz**: Die Kopie der Datenbank braucht einmal deren Größe (der Probelauf nennt Größe und freien Platz); die Medien
  werden nur umbenannt, nicht kopiert.
- **DEMO-Konten** (`@example.invalid`) löscht der Befehl nicht, er listet sie. Sie haben danach keine Freigaben mehr;
  über die Nutzerverwaltung löschen, falls nicht mehr gebraucht. Der Beispielbestand (nach dem Katalog-Import) übernimmt
  vorhandene DEMO-Konten samt Passwort, gibt ihnen ihre Freigaben neu und legt nur fehlende an.
- **Rückweg** (der ganze Stand vor dem Zurücksetzen; was seither auf dev entstand – auch an Konten, Wiki, Spots und
  Prüfungen –, geht verloren). Dieselben Zeilen mit dem richtigen Ordnernamen stehen in `LIESMICH.txt` im
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

### Erinnerungsmails (Modul Material)

Die Anwendung verschickt die Erinnerungsmails selbst – ohne Cron und ohne Handgriff auf dem VPS: Jeder
Arbeitsprozess startet mit der ersten Anfrage einen Hintergrundlauf, der alle 15 Minuten aufwacht und **einmal am Tag
ab 6 Uhr deutscher Zeit** arbeitet. Dass zwei Arbeitsprozesse, ein Neustart oder die Kommandozeile nie doppelt mahnen,
regeln Tagesmarken in der Datenbank und das Erinnerungslog – außer, wenn ein Prozess genau zwischen der Annahme einer
Mail und ihrem Vermerk endet (etwa beim Neustart nach einem Deploy kurz nach 6 Uhr); dann kommt diese eine Mail am
nächsten Morgen noch einmal. Ausgefallene Tage holt der nächste Lauf nach (mit der höchsten erreichten Stufe).

- **Einschalten in der Produktion im Browser**: Verwaltung → Einstellungen → Material → „Erinnerungsmails
  verschicken“. Die **Vorgabe ist aus**. Nicht in der `.env` einschalten – die Entwicklung kopiert sie. Nach dem
  Einschalten kommen die ersten Mails binnen 15 Minuten, danach jeden Morgen. Der erste Lauf schickt den Rückstand:
  alles, was schon in einem Fenster liegt, einmal.
- **Aus** heißt: keine Mails, kein Log. Der tägliche Pflegeteil läuft trotzdem – Journaleintrag „Freigabe
  abgelaufen“, Löschen des Erinnerungslogs nach 13 Monaten, Kürzen des Protokolls der globalen Suche und des
  Mailfehler-Protokolls (13 Monate, erledigte Zeilen 3 Monate).
- **Ohne `SMTP_HOST`** wird nichts versucht; die Übersicht sagt dann „kein Mailserver eingerichtet“.
- **Stand und Probelauf**: Material → Übersicht, ganz unten (nur Material- und Plattform-Verwaltung): an/aus/gesperrt,
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
  verwaltet; gilt für alle Unterordner, steht im Journal). Ablaufende Freigaben melden sich weiter.

## Konfiguration

Beim ersten Start richtet `.env` die Anlage ein (Vorlage: `.env.example`). Danach lässt sich
fast alles davon **im Browser** ändern: **Verwaltung → Einstellungen**. Jedes Feld zeigt dort,
woher sein geltender Wert kommt – hier gesetzt, aus der `.env` oder eingebaute Vorgabe – und
lässt sich einzeln zurücksetzen.

Ein im Browser gesetzter Wert hat **Vorrang** vor der `.env`. Andernfalls ließe sich etwas
einstellen, ohne dass es wirkt, und der Grund stünde in einer Datei auf dem Server. Die Werte
liegen in der Datenbank und gelten sofort in allen Arbeitsprozessen; ein Neustart ist für keine
Einstellung nötig.

Nur in der `.env` einstellbar bleiben `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DATA_DIR`,
`VIDEOPFLEGE` und `MATERIAL_ERINNERUNGEN_SPERRE`. Das Mailkennwort wird gespeichert, aber nie wieder ausgeliefert – auch nicht
an Administratoren.

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
| `PUBLIC_HOST`, `PUBLIC_URL` | Subdomain und Adresse des öffentlichen Wikis |
| `ADMIN_NOTIFY_EMAIL` | Empfänger für Kontoanfragen (leer = der dienstälteste Administrator; es geht bewusst genau eine Mail hinaus, damit die Antwortzeit nicht verrät, ob eine Adresse schon ein Konto hat – die übrigen Admins sehen die Anfrage unter „Nutzer“) |
| `LOGIN_SLIDESHOW` | Slideshow auf der Anmeldeseite (`true`/`false`) |
| `SMTP_*`, `MAIL_FROM` | Mailversand für Passwort-Reset; ohne `SMTP_HOST` steht der Link im Container-Log (`docker compose logs`) |
| `SMTP_ENVELOPE_FROM` | Absender des Umschlags (Return-Path). Leer = die Adresse aus `MAIL_FROM`; gegen sie prüft der Empfänger SPF (siehe „Damit Mails ankommen“) |
| `WIKI_MAX_REVISIONS` | Fassungen je Wiki-Seite im Verlauf (Standard 100, `0` = alle behalten) |
| `WIKI_IMPORT_MB` | Obergrenze eines Wiki-Imports als ZIP (Standard 200) |
| `MAP_CENTER`, `MAP_ZOOM`, `TILE_URL`, `TOPO_URL`, `SAT_URL` | Kartenstart und Kachelquellen; `SAT_URL` ist das Luftbild und die Startansicht (leer = nur Straßenkarte) |
| `SAT_LABELS_URL` | Beschriftungsebenen über dem Luftbild (Straßen, Orts- und Gewässernamen), mehrere durch Komma; leer = keine |
| `TILE_ATTRIBUTION`, `TOPO_ATTRIBUTION`, `SAT_ATTRIBUTION` | Rechtehinweise unter der Karte (leer = Vorgaben von OSM, OpenTopoMap und Esri) |
| `MATERIAL_BALD_FAELLIG_TAGE` | Modul Material: so viele Tage vor der nächsten Prüfung gilt ein Artikel als „bald fällig“ (Standard 30; auch unter „Verwaltung → Einstellungen“) |
| `MATERIAL_ERINNERUNGEN` | Modul Material: Erinnerungsmails verschicken (`true`/`false`, Standard `false`). Im Browser einschalten (Verwaltung → Einstellungen), nicht hier – die Entwicklung kopiert die `.env` |
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
- **Lesebeschränkte Abschnitte:** Herausverschieben darf nur, wer die Beschränkung aufheben dürfte (Ersteller des Abschnitts oder Wiki-Verwaltung); Fehlermeldungen nennen keine Titel fremder Seiten; unter eine Seite hängen kann nur, wer sie lesen darf. In den Papierkorb oder endgültig löschen kann ein Mitglied nur Teilbäume ohne Seiten anderer Ersteller (Wiki-Verwaltung ausgenommen).
- **Wiki-Import (ZIP):** nur die Wiki-Verwaltung (Mitglied 403, bevor die Datei gelesen wird). Geprüft wird vor dem Entpacken: Zahl der Einträge (höchstens 2000) und Größe des Inhaltsverzeichnisses (512 KB) aus dem Ende-Satz, keine doppelten Namen, nichts verschlüsselt, entpackt höchstens 1 GB, je Eintrag ab 1 MB ein Packverhältnis bis 100:1; gelesen wird nie mehr als die angegebene Größe. Pfade nur relativ – `..`, führender Schrägstrich, Rückstrich, Laufwerk, Steuerzeichen, symbolische Verweise und mehr als 20 Ebenen brechen ab; `__MACOSX/`, versteckte Dateien und `Thumbs.db` werden still übergangen. Seiten je höchstens `MAX_REQUEST_MB` (wie im Editor), zusammen höchstens 64 MB, UTF-8 ohne Nullzeichen. Anhänge gehen durch dieselbe Ablage wie beim Hochladen (Endung, Pixelgrenze, Bilder neu geschrieben); Videos nimmt der Import nicht mit. Geschrieben wird in einer Transaktion; scheitert sie, löscht der Import die schon abgelegten Dateien.
- **HTML-Bausteine** stellt nur die Wiki-Verwaltung ein – die Endung wird dafür genauso bestimmt wie bei der Ablage, auch wenn der Browser statt eines Dateinamens nur einen Inhaltstyp mitschickt.
- **Videos:** ffmpeg arbeitet nur mit lokalen Dateien (`-protocol_whitelist`), entfernt beim Wandeln und beim Umpacken die Begleitangaben (Aufnahmeort vom Telefon) und läuft je Arbeitsprozess nur einmal zugleich. Der ZIP-Export packt jede Datei einmal, auf Platte, bis 2 GB.
- **Aufräumen:** Nach dem Start entfernt der Hintergrundlauf Artikeldateien unter `media/wiki`, die seit einer Woche weder eine Seite noch eine Fassung im Verlauf nennt (Uploads ohne Speichern, alte Zuschnitte, Anhänge endgültig gelöschter Seiten, abgebrochene Umwandlungen).
- **Anmeldeseite:** Die Slideshow zeigt je Tag dieselbe Auswahl, nicht bei jedem Aufruf andere Bilder – sonst ließe sich der Bestand ohne Anmeldung einsammeln.
- **Protokolle (Modul Material):** Festgeschriebene Prüfungen, Aussonderungen und Durchgänge ändert auch die Datenbank nicht mehr (Trigger); die PDF-Dateien liegen schreibgeschützt unter `/data/pdf` und werden nur ausgeliefert, wenn ihre Prüfsumme noch stimmt. WeasyPrint lädt beim Rendern nichts aus dem Netz und keine fremden Dateien – nur die eigenen Schriften; Bilder kommen eingebettet. Die öffentliche Prüfseite `/material/pruefen` speichert nichts, nennt keine Personendaten und ist je Adresse auf 20 Prüfungen in 15 Minuten und 200 MB je Datei gebremst.
- **Trennung je Gliederung (Modul Material):** Rechte am Bestand gibt es für Mitglieder nur über Freigaben je Ordner (alle Bestände sieht nur die Material-Verwaltung); der Server prüft sie bei jeder Anfrage, und ohne Stufe im Modul wirkt keine. `tests/test_material_stufen.py` ruft jede Route des Moduls mit einem Konto auf, das Freigaben, aber keine Stufe hat (403 vor jeder Frage nach dem Gegenstand). Was ein Konto nicht sieht, antwortet wie etwas, das es nicht gibt – 404 mit derselben Meldung, ob die Kennung im Pfad oder im Inhalt der Anfrage steht; 403 nur, wenn man den Gegenstand sieht, die Aktion aber nicht darf. Listen, Zählungen, Suche, Exporte, Rückrufe und Meldungen filtert der Server, nicht die Oberfläche. Mediendateien prüft er je Datei (Ordnerfoto am Ordner, Befundfoto und Prüfanhang am Artikel, Meldungsfoto an der Meldung; Produktbilder und Herstellerdokumente für alle mit Zugang). Die globale Seriennummernsuche, der Steckbrief nach einem QR-Scan und die Meldung „gibt es schon in einem Bereich, den du nicht siehst“ beim Anlegen stehen jedes Mal zwölf Monate mit Namen im Protokoll – ungebremst, die Kontrolle ist dieses Protokoll; gesucht wird nur nach der ganzen Herstellerseriennummer, nach ausdrücklicher Bestätigung und nur unter dem, was man nicht sieht. Die Personensuche für Freigaben und Zuordnung zeigt ab drei Zeichen nur Name, Gliederung und ob jemand Prüfer ist – keine E-Mail. `tests/test_material_trennung.py` ruft jede Route des Moduls mit Kennungen einer fremden Gliederung auf und sucht deren Merkmale in allen Antworten.
- **Export und Katalogaustausch (Modul Material):** Exporte gibt es nur mit lesen oder verwalten am Ordner (Freigaben je Ordner); Werte, die eine Tabellenkalkulation als Formel läse (`=`, `+`, `-`, `@` am Anfang), stehen in der CSV mit vorangestelltem `'`. Das Protokoll-ZIP gibt nur Dateien heraus, deren Prüfsumme noch stimmt, und entsteht als Zwischendatei unter `/data/tmp` (höchstens 2 GB). Den Katalog exportieren und importieren nur die Material-Verwaltung. Der Import liest aus dem ZIP nur die Einträge, auf die `katalog.json` verweist (keine absoluten Pfade, kein `..`, keine doppelten Namen), prüft Zahl, Größe und Packverhältnis der Einträge vor dem Lesen und lässt Bilder und Dokumente durch dieselben Prüfungen wie beim Hochladen (Endung, Inhalt, Größe, Pixel); ein Fehler irgendwo speichert nichts.

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
   scheitert DMARC trotz gültigem SPF. Beides steht unter Verwaltung → Einstellungen → E-Mail.
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

## Daten und Sicherung

Alles liegt im Volume `/data`: `stroemis.db` (SQLite), `media/orig` (Originale), `media/web` und `media/thumb` (erzeugte Varianten), `media/wiki` (Wiki-Bilder), `media/avatar` (Profilbilder), `media/pruefungen` (Medien zu Prüfungen), `media/material` (Fotos, Herstellerdokumente und Prüfanhänge des Moduls Material; Herstellerdokumente unter `media/material/dok/<SHA-256>.<Endung>`, eine Datei je Inhalt), `pdf/` (festgeschriebene Protokolle des Moduls Material, schreibgeschützt – unbedingt mitsichern: die Datenbank verweist auf sie, und ihre Prüfsummen lassen sich nicht neu erzeugen), `secret_key`, nur auf dev `sicherung-material-…` (Sicherungen von `material dev-zuruecksetzen`, siehe dort) und `tmp/` (Zwischendateien laufender Uploads und Exporte – muss nicht gesichert werden). Verwaiste Dateien unter `media/wiki` räumt der Hintergrundlauf nach einer Woche weg (siehe „Wie die Anwendung abgesichert ist“).

**Stündliche Sicherung nach `~/data.bak`** – ein einzelner Cron-Eintrag auf dem VPS. Er gehört in den Cron des
Nutzers, dem `data/` gehört (uid 1000), oder in den von root: Nur die dürfen `secret_key` lesen. Mit `crontab -e`
eintragen und den Pfad anpassen:

```
0 * * * * cd /pfad/zur/produktion && mkdir -p ~/data.bak && docker exec stroemis python -c "import sqlite3; d = sqlite3.connect('/data/tmp/abzug.db'); sqlite3.connect('/data/stroemis.db').backup(d); d.execute('PRAGMA journal_mode=DELETE')" && cp data/tmp/abzug.db ~/data.bak/stroemis.db && rsync -a --delete --exclude=/tmp/ --exclude='/stroemis.db*' data/ ~/data.bak/
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
rsync -a ~/data.bak/pdf/ data/pdf/                     # Protokolle nur ergänzen, nie löschen (siehe unten)
sudo chown -R 1000:1000 data
docker compose up -d
```

Festgeschriebene Protokolle des Moduls Material (`data/pdf/`) werden beim Zurückspielen nicht gelöscht: Ein
Protokoll, das nach der letzten Sicherung entstand, ist vielleicht schon ausgehändigt. Die Datenbank kennt es nach
dem Zurückspielen nicht mehr; der Start legt es deshalb nach `data/pdf/verwaist/`, und seine Protokoll-ID wird nicht
noch einmal vergeben (ist der zugehörige Entwurf wieder offen, bekommt sein neues Protokoll eine Folgenummer wie
`P-2026-000007-2`). Die Prüfung ist im System neu festzuschreiben.

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
python tests/test_wiki_lesemodus.py    # Wiki-Lesemodus: Konto ohne Wiki-Stufe sieht genau die öffentlichen Seiten (alle Wiki-Routen)
python tests/test_pruefungen.py         # Prüfungsbereich (Rechte, Kataloge, Excel-Import, Kopieren, Nachprüfung, Medien)
python tests/test_pruefungen_import.py  # Excel-Erkennung
python tests/test_material.py           # Modul Material (Migration, Rollen, Katalog, Ordner, Artikel, Suche, Journal, Import, Prüfung, Durchgang, Produktmeldungen,
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
python tests/test_material_freigaben.py  # Phase 2: Freigaben vergeben, ändern, entziehen, verlängern; Übernahme-Schutz; Nutzerverwaltung
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
flask --app "app:create_app()" material export-catalog katalog.zip              # Katalog ohne DEMO als ZIP (Format 2)
```

Die JavaScript-Bibliotheken liegen im Arbeitsbaum unter `app/static/vendor/` und werden im Docker-Build noch einmal frisch geladen und gegen `vendor.sha256` geprüft.

WeasyPrint (Protokolle des Moduls Material) braucht außerhalb von Docker die Systembibliotheken Pango und HarfBuzz – unter Debian/Ubuntu `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core` (dazu `libharfbuzz-subset0` ab Debian 12 bzw. Ubuntu 24.04 – älteren Systemen fehlt das Paket, WeasyPrint läuft dann ohne), unter macOS `brew install pango`.

`tests/rundlauf.html` prüft die zentrale Invariante des Editors – Markdown öffnen und speichern darf kein Byte ändern – über einen Korpus aus 66 Fällen. Ein zweiter Abschnitt prüft den Rückgängig-Verlauf (ein Strg+Z direkt nach dem Laden darf am Dokument nichts ändern, eigene Änderungen müssen weiterhin rückgängig zu machen sein), gesetzte Leerzeilen, das Auflösen unvollständiger Abschnitte und die Grenzen des Renderers: Aufgabenlisten behalten ihr Kästchen, Formulare und Stilblöcke aus dem Seitentext kommen nicht durch. Ein dritter Abschnitt prüft die zusammengefassten Zellen: dass ein Zug über mehrere Zellen überhaupt eine Zellauswahl ergibt (das Bündel von Toast UI ist an dieser Stelle fehlerhaft übersetzt und wird geflickt), dass Verbinden und Teilen die erwartete Schreibweise ergeben und dass die Leseansicht daraus `colspan` und `rowspan` macht – mit Gegenproben, die ohne die Reparatur beziehungsweise ohne die Nachbearbeitung fehlschlagen müssen. Die Datei lädt die Projektskripte über relative Pfade; ein Doppelklick genügt, ein Server ist nicht nötig.

`tests/gleichstand.html` hält Leseansicht und Editor nebeneinander und misst für 17 Bausteine Schriftgröße, Schnitt, Farbe, Auszeichnung, Ausrichtung und den linken Textanfang – die Probe darauf, dass der Editor zeigt, was der Artikel später zeigt.

`tests/nachgeholtes_speichern.html` prüft, dass das automatische Speichern niemals die falsche Seite trifft: Ein Speichervorgang, der seinen eigenen Editor überlebt, weil die Anfrage hängt und man inzwischen die Seite gewechselt hat, darf den Text der neuen Seite nicht unter der Kennung der alten ablegen. Die Datei fährt das Wiki mit einem nachgestellten Server hoch, der jede Schreibanfrage so lange festhält, bis der Test sie freigibt – der Ablauf hängt damit an keiner Laufzeit. Auch hier genügt ein Doppelklick.

`tests/live_mitlesen.html` prüft das Mitlesen: Sobald jemand anderes schreibt, meldet sich der Leser alle 4 statt alle 15 Sekunden, holt jede neue Fassung und zeichnet den Artikel nach – der oberste sichtbare Absatz bleibt dabei auf ±2 px an seiner Stelle, auch wenn oberhalb ein Absatz eingefügt wurde; unter einer Textauswahl wird nicht gezeichnet, und nach dem Weggang des Schreibers kommt der letzte Stand noch an, danach gilt wieder der lange Takt. Der Lauf dauert rund eine halbe Minute, weil die echten Takte gelten.

`tests/baustein_editor.html` prüft den HTML-Baustein in beiden Ansichten: Im Artikel entsteht aus der Bild-Schreibweise ein gesandboxter Rahmen mit den Maßen aus der Adresse, kein rohes `<iframe>` und keine fremde Adresse kommt durch. Im Editor steckt er in einer Hülle mit Griff, bekommt dasselbe Menü wie ein Bild und wird an drei Griffen gezogen; geprüft wird jeweils, was der Editor danach an den Server schickt (`#w=…&h=…`), und dass die Zuordnung zu einem Bild daneben stimmt. Der Server ist eine Attrappe, ein Doppelklick genügt.

## Aufbau

```
app/
  __init__.py      App-Factory, Seiten-Routen, Medienauslieferung, CSRF-Schutz, Security-Header
  auth.py          Login, Registrierung, Reset, Profil (Session-Cookie, Werkzeug-Hashes)
  api_albums.py    Alben, Bilder, Kartendaten
  api_wiki.py      Seiten, Versionen, Suche, Freigaben, Kommentare, öffentliche API, Datei-Upload, Export, Import (Route)
  wiki_import.py   Wiki-Import aus einem ZIP (Prüfung, Baum, Anhänge, Verweise, eine Transaktion)
  api_admin.py     Nutzerverwaltung
  api_pruefungen.py  Prüfungen: Lehrgänge, Teilnehmende, Voraussetzungen, Leistungen, Kataloge, Versuche, Medien, Mängel, Import, Rechte
  pruefungen_import.py  Excel-Teilnehmerlisten lesen (Kopfzeile finden, Spalten zuordnen, ja/nein deuten) – ohne Flask
  images.py        EXIF (GPS, Höhe, Zeit), Ausrichtung, Thumbnails, HEIC, Videos nach H.264
  medienpflege.py  Nach dem Start im Hintergrund: Bestandsvideos wandeln, verwaiste Artikeldateien aufräumen (eine Sperre, ein Arbeiter)
  db.py            SQLite-Schema, Migrationen, Transaktionsklammer
  material/        Modul Material, eigenständig: models.py (Tabellen mat_*, Schemaversion in mat_meta),
                   routes.py (Seiten /material…, /m/<token>, Schnittstelle /api/material…, Medien),
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
  templates/       Jinja-Seiten
  static/css/      app.css – ein Blatt für alle Ansichten; pruefungen.css nur für den Prüfungsbereich
  static/fonts/    DLRG Univers als WOFF2 (Regular, Kursiv, Fett)
  static/img/      Favicon, optional die DLRG-Wortmarke
  static/vendor/   Leaflet, markercluster, marked, DOMPurify, Toast UI, signature_pad (im Docker-Build geladen)
  static/js/       common.js       gemeinsame Helfer (api, esc, dialog, toast, Datum)
                   markdown.js     Renderer: Callouts, Spalten, Boxen, Videos, TOC, Auszeichnungen
                   editor-format.js  Markdown <-> Editorformat (reine Funktionen, trägt den Rundlauf)
                   editor-layout.js  Darstellung der Abschnitte im Editor (ProseMirror-Dekorationen)
                   editor-verlauf.js Rückgängig-Verlauf: Laden gehört nicht hinein
                   wiki.js         Editor, Seitenbaum, Kommentare, Teilen, Verlauf
                   public.js       öffentliches Wiki und Lesemodus (Konten ohne Stufe im Wiki)
                   map.js          Karte, Alben, Upload, Lokalisieren, Bild-Detail
                   pruefungen.js   Lehrgänge, Voraussetzungen, Bewertungsmatrix, Stoppuhr, Mängel, Excel-Import
                   admin.js (mit admin_globalsuche.js), auth.js, profile.js
tests/
  test_smoke.py    Rauch-, Härtungs- und Befundtest über die API (der Befundtest stellt die Fixes der Sicherheitsprüfung nach)
  test_wiki_lesemodus.py  Lesemodus des Wikis: Konto ohne Stufe im Wiki gegen jede Wiki-Route der url_map
  test_pruefungen.py  Prüfungsbereich: Rechte, Kataloge, Import, Kopieren, Pflichtkommentar, Nachprüfung, Medien, Mängel
  test_pruefungen_import.py  Excel-Erkennung mit synthetischen Dateien
  test_material.py Modul Material: Migration, Rollen, Katalog, Ordner, Artikel, Suche, Journal, Status, Import,
                   Prüfung, Sperre und Aussonderung, Anhänge, Prüfdurchgang, Produktmeldungen, Festschreiben,
                   Protokolle mit Prüfsumme, Prüfseite, Berichtigung, Unterschrift
  test_material_ueberblick.py, test_material_export.py, test_material_katalog.py, test_material_rueckruf.py
                   Modul Material, Lieferung 4: Übersicht und Rechte, Export, Katalogaustausch, Rückrufe
  test_material_l5.py, test_material_profil.py
                   Modul Material, Lieferung 5: Feinschliff nach Pilot, Urkundennummer im Profil; dazu die
                   statische Prüfung der Oberfläche nach Rechten je Ordner (Phase 2)
  test_material_trennung.py, test_material_freigaben.py, test_material_globalsuche.py, test_material_zuordnung.py,
  test_material_stufen.py
                   Modul Material, Phase 2: Trennung je Gliederung, Freigaben, globale Suche, Personenzuordnung,
                   Löschkonzept und Modulstufe
  test_material_set_rueckbau.py
                   Modul Material, Rückbau der Set-Funktion (Schritt 26): Migration frisch, 20 → Ende und 25 → 26 mit
                   Set-Altbestand, Trigger, Schnittstelle (entfallene Routen, Katalogdatei, Meldung, CSV), Rechte am
                   Reiter „Bestandteile“, kein Set-Rest im Code
  test_material_setprotokolle.py
                   Modul Material, Set-Protokolle im Prüfdurchgang (Schritt 27): Inhalt je PDF (verschachtelt, gesperrt,
                   aus dem Bereich), Zwischenzeilen und Verzeichnis, Abbruch, Fehler beim Rendern, Trigger, Prüfseite,
                   Nummernschutz, Rechte je Rolle, Ordnerseite, ZIP des Durchgangs und Ordner-Export
  test_material_produktwechsel.py
                   Modul Material, Feintuning (23.10.2026): Produkt am Artikel ändern – Rechte, Entwurf,
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
