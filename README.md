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
- Videos (MP4, MOV, WebM) können wie Bilder hochgeladen werden. Was nicht jeder Browser abspielt – vor allem Aufnahmen vom iPhone (.mov mit HEVC) – wird beim Hochladen nach H.264/AAC gewandelt und bekommt ein Vorschaubild aus dem Film; dafür bringt der Container ffmpeg mit – als statisch gebundenes Programm (johnvansickle, GPLv3), gegen eine feste Prüfsumme geholt. Aus der Paketverwaltung kostete dasselbe rund 630 MB statt 160 MB; das Abbild liegt damit bei etwa 485 MB. Das gilt auch für Videos in Artikeln und für den **Bestand**: Nach jedem Start prüft ein Hintergrundlauf alle vorhandenen Videos und wandelt, was nötig ist – Verweise in Seiten, Fassungen und Anhangslisten ziehen mit, und die alte Adresse (`….mov`) führt weiter zum Film. Unter „Nutzer“ steht, solange es läuft, eine Zeile mit dem Stand; `VIDEOPFLEGE=0` schaltet den Lauf ab. Ein Klick auf ein Thumbnail öffnet direkt die Großansicht.

**Wiki (Startseite, Docmost-Nachfolger)**
- WYSIWYG-Editor (Toast UI) mit Markdown-Kürzeln direkt im Text (`# `, `- `, `> `, ` ``` `). Eine Quelltextansicht gibt es nicht – gespeichert wird trotzdem Markdown.
- Keine feste Toolbar: `/` öffnet ein Einfügemenü (Überschriften, Listen, Tabelle, Bild, Video, Datei, Audio, Callout, Spalten, Box, Inhaltsverzeichnis, Emoji, Datum …); markierter Text bekommt eine schwebende Leiste mit „Umwandeln in …“ (Überschriften, Listen, Zitat, Code-Block, Callout, Code, Hervorheben, Hoch-/Tiefstellen), Fett/Kursiv/Durchgestrichen/Unterstrichen, Textfarbe, Link, Ausrichtung und Rückgängig/Wiederholen. Klick in Tabellen, auf Bilder, Links oder in einen Abschnitt öffnet ein Kontextmenü wie in Docmost: Zeilen/Spalten, Spaltenausrichtung, Zellen verbinden und wieder teilen (ein Zug über mehrere Zellen, dann *Zellen verbinden*; gespeichert als `@cols=`/`@rows=` vor dem Zelleninhalt, sortiert wird eine solche Tabelle nicht mehr), Bildbreite (Presets, Zahlenwert oder Ziehgriff), Ausrichtung, Alt-Text, Zuschneiden (Rahmen über dem Bild; das Ergebnis ist eine neue Datei, das Original bleibt liegen), Spaltenanzahl, Callout-Art und Emoji, Duplizieren, Löschen. Die Menüs tragen nur Symbole (eigene SVG, keine Icon-Bibliothek); markierter Text blendet das Blockmenü aus und die Formatleiste ein, und umgekehrt. Der Editor zeigt Spalten nebeneinander, Callouts als farbige Kisten – auch die einzeilige Form in einer Tabellenzelle, deren Marken dort ausgeblendet sind –, einklappbare Boxen aufgeklappt und Ausrichtung wirklich ausgerichtet – der Inhalt ist dabei gewöhnlicher Editorinhalt und wird direkt bearbeitet, ohne Dialog. Jede Spalte fließt für sich (gemessenes Layout statt geteilter Rasterzeilen), in Breite und Rinne deckungsgleich mit der Leseansicht. Auch der Zeilenfall stimmt überein: Die Leerzeile, mit der Markdown zwei Absätze trennt, ist im Editor technisch ein leerer Absatz – sie bleibt im Dokument stehen, wird aber zugeklappt. Jede darüber hinaus gesetzte Leerzeile bleibt dagegen sichtbar und wird als `&nbsp;`-Absatz gespeichert; früher schrieb der Editor dafür eine `<br>`-Zeile, und die verschluckte in der Leseansicht den folgenden Absatz. Auf schmalen Bildschirmen stehen Spalten in beiden Ansichten untereinander (ab 640 px). Blöcke lassen sich am Griff links verschieben; an einer Marke wandert der ganze Abschnitt mit. Tabellen, Spalten- und Ausrichtungsabschnitte lassen sich nicht mit Entfernen oder Rücktaste löschen – nur über ihr eigenes Menü; eine halb gelöschte Abschnittsmarke nähme beim Speichern den ganzen Abschnitt mit. Oben rechts schaltet ein Umschalter zwischen Lesen und Bearbeiten, beide in derselben Breite. Bilder per Drag & Drop, Einfügen aus der Zwischenablage sowie Kopieren und Ausschneiden.
- Callouts (`info`, `tip`, `warning`, `success`, `danger`, `note`) mit frei wählbarem Emoji und wahlweise einer eigenen Pastellfarbe (`farbe:mint` in der Kopfzeile; acht Töne zur Auswahl) (Auswahl aller darstellbaren Unicode-Emojis oder Eingabe über den System-Emoji-Picker). Abschnitte mit 2 bis 5 Spalten, einklappbare Boxen (Accordions; Titel und Inhalt direkt im Text bearbeitbar) – beide ineinander verschachtelbar. Ausrichtungsblöcke (`:::align center`). Synchronisierte Abschnitte: `:::baustein <kennung>` hält einen Text an einer Stelle, `:::einbau <seite>#<kennung>` zeigt ihn auf beliebig vielen anderen Seiten – geändert wird nur in der Quelle. Vorhandene Absätze lassen sich nachträglich dazu machen (markieren → „Umwandeln in …“ → „Synchronisierter Abschnitt“), ohne dass sich am Text etwas ändert. Aufgelöst wird beim Anzeigen über die gewöhnliche Schnittstelle, damit die Leserechte der Quellseite von allein gelten; im öffentlichen Bereich erscheint nur, was dort freigegeben ist. Rückverweise zeigen der Quellseite, wer sie einbindet. Gespeichert wird Markdown mit `:::`-Blöcken; bestehende Seiten funktionieren unverändert. Tabellen, Callouts, einklappbare Boxen, Spalten und Ausrichtungsblöcke lassen sich im Editor nicht mit Entfernen oder Rücktaste löschen – nur über ihr Inline-Menü; ein versehentlicher Tastendruck würde sonst eine Marke entfernen und beim Speichern den ganzen Abschnitt auflösen.
- Die Übersicht (`/wiki`) listet jeden Abschnitt mit allem, was darunter liegt – verschachtelt bis zur dritten Ebene; tiefer steht, wie viele Seiten noch folgen. Darunter „zuletzt besucht“ und „zuletzt geändert“.
- Die erste Überschrift im Text ist zugleich der Seitentitel – wie in Docmost. Wer sie ändert, benennt die Seite um; ein eigenes Titelfeld gibt es nicht mehr. Einsortiert wird eine Seite durch Ziehen im Seitenbaum links (auf eine Seite ziehen macht sie zur Unterseite).
- Die Kopfzeile bleibt beim Scrollen stehen und ist wie in Docmost aufgeteilt: links der Pfad zur Seite mit den Symbolen der Ebenen, rechts der Umschalter Lesen/Bearbeiten, Kommentare, Teilen, ein Knopf für das Inhaltsverzeichnis und „⋯“ für alles Weitere (Verlauf, Merkliste, Beobachten, Export, Drucken, Vorlage, Duplizieren, Papierkorb). Unter der Überschrift steht, wer die Seite angelegt hat – ein Klick darauf zeigt Ersteller und Mitwirkende –, daneben ein Knopf, der rechts die Angaben zur Seite aufklappt: Herkunft, Zeitpunkte, Wörter, Zeichen, Lesezeit und die Verweise in beide Richtungen.
- Artikel mittig mit fester Lesebreite; rechts ein automatisches Inhaltsverzeichnis, die Angaben zur Seite und die Kommentare. **Auf dem Telefon** (unter 1180 px) rücken Kommentare und Angaben unter den Artikel, das Inhaltsverzeichnis entfällt; unter 800 px sitzt der Seitenbaum als Schublade hinter „☰“ in der Kopfzeile, der Pfad weicht dem Titel. Fingerziele wachsen auf Touch-Geräten, Eingabefelder haben 16 px (kein iOS-Zoom), Dialoge und Leuchtkasten füllen den Bildschirm, die Nutzerverwaltung wird zur Kartenliste. Auf **Tablets** (801–1024 px) ist der Seitenbaum höchstens 260 px breit, das Seitenpolster 24 px, die Albumleiste 340 px. **Faltgeräte** aufgeklappt (Galaxy Fold, Pixel Fold): meldet der Browser zwei Bildschirmhälften (Viewport Segments), liegt die Falz genau auf der Trennlinie – links Seitenbaum, rechts Text; auf der Karte rechts die Albumleiste; zusammengeklappt füllt die Schublade die linke Hälfte. Alles davon liegt in Media-Queries – am Rechner ändert sich nichts. Der Editor benutzt dieselbe Spalte: Kopfzeile, Titel, Autorzeile und jeder Block sitzen in beiden Ansichten auf demselben Pixel. Gemessen über ein Dokument mit Spalten, Ausrichtung, Liste, Tabelle und Bild mit Unterschrift bleibt der Unterschied unter zwei Pixeln und summiert sich nicht: Die Abschnittsmarken kosten keine Höhe, Tabellen und Bildunterschriften übernehmen die Maße der Leseansicht.
- Kommentare zu beliebigen Textstellen (Text markieren → „Kommentieren“) oder zur ganzen Seite, mit Antworten und „Erledigt“. Löschen dürfen Kommentator, Seitenersteller und Admin.
- Bearbeitungsfreigaben: Der Ersteller gibt einzelne Nutzer zum Bearbeiten frei (ohne Löschrecht); die Freigabe gilt auch für Unterseiten. Ohne Freigabe können andere Nutzer lesen und kommentieren.
- Den **Ersteller** einer Seite kann die Administration umschreiben (Klick auf „Von …“ unter dem Titel → „Ersteller ändern“). Gebraucht wird das, wenn jemand die Gliederung verlässt. Mit dem Namen wechseln auch seine Rechte: löschen und Bearbeiter freigeben.
- Öffentliche Freigabe (nur Admin, Menü „Teilen“): einzelne Seiten oder ganze Abschnitte inkl. Unterseiten sind dann ohne Login unter `wiki.strömis.de/<slug>` erreichbar – samt der eingebundenen Bilder und Videos. Nicht freigegebene Anhänge bleiben geschützt. In einem freigegebenen Abschnitt dürfen auch Unterseiten nur Administratoren anlegen oder dorthin verschieben – sonst käme Veröffentlichen durch die Hintertür.
- Versionsverlauf mit Wiederherstellen (standardmäßig die letzten 100 Fassungen je Seite, `WIKI_MAX_REVISIONS`), Volltextsuche, Export einzelner Seiten oder ganzer Abschnitte als Markdown beziehungsweise ZIP.
- Beim Umbenennen einer Seite ändert sich ihre Adresse, die bisherige bleibt aber gültig – vorhandene Links und Lesezeichen laufen weiter.
- **Es bearbeitet immer nur eine Person.** Wer den Editor öffnet, bekommt den Schreibplatz; alle anderen sehen in der Kopfzeile „✏ Anna bearbeitet“ und einen ausgegrauten Knopf „Bearbeiten“, der sagt, worauf zu warten ist. Entreißen lässt sich der Platz nicht – der Editor speichert von allein, und wer ihn mitten im Satz verlöre, merkte vom Verlust seiner Arbeit nichts. Jeder offene Reiter meldet sich alle 15 Sekunden; bleibt die Meldung aus, wird der Platz nach 45 Sekunden frei, und wer dann zurückkommt, erfährt, dass hier nicht mehr gespeichert wird. **Warten muss trotzdem niemand:** Wer liest, während jemand anderes schreibt, sieht dessen gespeicherte Änderungen von selbst erscheinen – der Herzschlag der Leser läuft solange alle 4 statt alle 15 Sekunden, und weicht die gespeicherte Fassung von der gezeigten ab, wird der Artikel nachgezeichnet. Die Lesestelle bleibt dabei stehen: gemerkt wird der oberste sichtbare Absatz, nicht die Bildlaufhöhe, sonst rutschte man bei jedem oberhalb eingefügten Satz weiter. Unter einer Textauswahl oder einem offenen Dialog wird nicht gezeichnet (Prüfstand: `tests/live_mitlesen.html`). Gespeichert wird nur, wenn die Fassung noch stimmt: Die Prüfung sitzt im Schreibzugriff selbst, zwei gleichzeitige Speichervorgänge können sich also nicht mehr gegenseitig überschreiben.
- Der Editor speichert von allein, kurz nach jeder Änderung – einen Speichern-Knopf gibt es nicht; der Stand steht links in der Kopfzeile. Zwischenstände füllen weder den Verlauf noch lösen sie Benachrichtigungen aus: Alle Speichervorgänge einer Bearbeitung – vom Öffnen bis zum Verlassen des Editors – gehören zu einer Fassung; jede neue Bearbeitung legt eine eigene an, auch kurz nach der vorigen. Die Post an Beobachter folgt einer eigenen Regel: Wer dieselbe Seite kurz hintereinander mehrfach bearbeitet, schreibt zwar jedes Mal eine eigene Fassung, löst aber innerhalb von zehn Minuten nur eine Nachricht aus. Einen „Verwerfen“-Knopf gibt es nur noch beim Anlegen einer neuen Seite; bei einer vorhandenen holt der Verlauf ältere Stände zurück. Eine neue Seite wird weiterhin ausdrücklich über „Anlegen“ erzeugt.
- Speichern zwei Leute dieselbe Seite, wird die zweite Änderung nicht stillschweigend überschrieben: Der Server lehnt sie ab, das automatische Speichern hält an und weist auf die zwischenzeitliche Fassung im Verlauf hin.

**Nutzer**
- Anmeldung mit E-Mail und Passwort, Passwort per E-Mail zurücksetzen. Nach zehn Fehlversuchen je Adresse oder je Absender-IP ist eine Viertelstunde Pause – gegen das Durchprobieren von Passwörtern. „Konto anfragen“: Name, Gliederung, E-Mail und Passwort sind Pflicht, eine Begründung ist optional. Die Anfrage geht per E-Mail an die Administratoren; erst nach Freigabe ist die Anmeldung möglich (der Nutzer wird per Mail informiert). Der allererste Nutzer wird direkt Administrator.
- Eigenes Zeichen: Liegt `app/static/img/maskottchen.webp` (oder .png/.jpg/.svg) bereit, steht es in Kopfzeile und Anmeldung anstelle des DLRG-Schriftzugs – 44 px in der Leiste, 96 px auf dem Anmeldebildschirm. WebP wird bevorzugt; ein knapp bemessenes Bild (rund 256 px Kantenlänge) reicht dafür und spart gegenüber einer 1024er-PNG-Vorlage rund das Vierzigfache an Übertragung.
- Profil mit Name, Gliederung, Telefon und Profilbild (quadratisch auf 256 px gebracht; es steht an den Autorenangaben der Artikel).
- Drei Rollen: **Nutzer** schreibt an eigenen und freigegebenen Seiten; **Redakteur** darf alle Seiten und Alben bearbeiten, lesen (auch beschränkte) und in den Papierkorb legen, aber keine Nutzer verwalten und nichts ohne Anmeldung veröffentlichen; **Administrator** darf zusätzlich beides. Die Rolle wird unter „Nutzer“ gesetzt.
- Alle angemeldeten Nutzer sehen alle Alben, Bilder und Wiki-Seiten. Ein Album bearbeitet, wer es angelegt hat (und der Admin); ein einzelnes Bild zusätzlich, wer es hochgeladen hat. Wiki: siehe oben.
- Administrator: Anfragen freigeben/ablehnen, Nutzer anlegen, bearbeiten, deaktivieren, löschen (Inhalte gehen an den Admin über), Reset-Mail auslösen; darf alle Inhalte bearbeiten und Seiten veröffentlichen.

**Anmeldeseite**
- Slideshow mit zufälligen Bildern aus den Spots (langsam wandernd, überblendet; abschaltbar mit `LOGIN_SLIDESHOW=false`, respektiert „Bewegung reduzieren“). Die Bilder werden über signierte, 24 h gültige Links ausgeliefert. Link zum öffentlichen Wiki.

## Schnellstart

```bash
cp .env.example .env        # BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD setzen
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

Uploads bis 5 GB: bei nginx/Traefik `client_max_body_size`/`maxRequestBodyBytes` und die Timeouts entsprechend erhöhen (Gunicorn im Container wartet bis zu 60 Minuten). Der Container wertet `X-Forwarded-Proto/For/Host` aus (ProxyFix), damit Links und sichere Cookies stimmen.

Nach einem Update gilt: Wer die Anwendung im Browser offen hat, lädt die Seite einmal neu. Ein Reiter, der noch die alten Skripte ausführt, spricht sonst weiter mit der alten Schnittstelle – im schlimmsten Fall legt jeder seiner Zwischenstände eine eigene Fassung im Verlauf an.

`GET /healthz` antwortet ohne Anmeldung mit `{"ok": true}` – darauf setzt der `HEALTHCHECK` des Containers auf (alle 30 s, `docker ps` zeigt den Zustand). Die Daten liegen im Volume unter `/data`: `stroemis.db` (SQLite mit WAL), `media/` (Originale, Web-Größen, Thumbnails, Wiki-Anhänge, Profilbilder) und `secret_key`. Für eine Sicherung genügt es, dieses Volume zu kopieren – am besten bei gestopptem Container.

## Konfiguration

Alle Einstellungen stehen in `.env` (Vorlage: `.env.example`):

| Variable | Bedeutung |
| --- | --- |
| `BASE_URL` | Öffentliche Adresse, wird in E-Mail-Links verwendet |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Erster Administrator, wird beim Start angelegt |
| `SECRET_KEY` | Sitzungsschlüssel; leer = wird erzeugt und unter `/data/secret_key` gespeichert |
| `ALLOW_REGISTRATION` | Selbstregistrierung erlauben (`true`/`false`) |
| `COOKIE_SECURE` | Cookies nur über HTTPS (`true` im Produktivbetrieb) |
| `MAX_UPLOAD_MB` | Obergrenze je Hochladevorgang (Standard 5120 = 5 GB) |
| `MAX_REQUEST_MB` | Obergrenze einer gewöhnlichen Anfrage ohne Upload (Standard 1) – begrenzt auch die Länge einer Wiki-Seite |
| `SITE_NAME` | Name der Anwendung in Betreffzeilen und Absendern |
| `PUBLIC_HOST`, `PUBLIC_URL` | Subdomain und Adresse des öffentlichen Wikis |
| `ADMIN_NOTIFY_EMAIL` | Empfänger für Kontoanfragen (leer = der dienstälteste Administrator; es geht bewusst genau eine Mail hinaus, damit die Antwortzeit nicht verrät, ob eine Adresse schon ein Konto hat – die übrigen Admins sehen die Anfrage unter „Nutzer“) |
| `LOGIN_SLIDESHOW` | Slideshow auf der Anmeldeseite (`true`/`false`) |
| `SMTP_*`, `MAIL_FROM` | Mailversand für Passwort-Reset; ohne `SMTP_HOST` steht der Link im Container-Log (`docker compose logs`) |
| `WIKI_MAX_REVISIONS` | Fassungen je Wiki-Seite im Verlauf (Standard 100, `0` = alle behalten) |
| `MAP_CENTER`, `MAP_ZOOM`, `TILE_URL`, `TOPO_URL`, `SAT_URL` | Kartenstart und Kachelquellen; `SAT_URL` ist das Luftbild und die Startansicht (leer = nur Straßenkarte) |
| `SAT_LABELS_URL` | Beschriftungsebenen über dem Luftbild (Straßen, Orts- und Gewässernamen), mehrere durch Komma; leer = keine |
| `TILE_ATTRIBUTION`, `TOPO_ATTRIBUTION`, `SAT_ATTRIBUTION` | Rechtehinweise unter der Karte (leer = Vorgaben von OSM, OpenTopoMap und Esri) |
| `VIDEOPFLEGE` | `0` schaltet den Hintergrundlauf ab, der nach dem Start Bestandsvideos nach H.264 wandelt (Standard: an) |
| `GEOCODE_URL` | Adresssuche beim Platzieren von Bildern (leer = abgeschaltet). Die öffentliche Nominatim-Adresse erlaubt eine Anfrage je Sekunde; wer viel sucht, betreibt eine eigene. |

Ohne `ADMIN_EMAIL`/`ADMIN_PASSWORD` wird der erste Nutzer, der ein Konto anfragt, sofort Administrator. Ohne SMTP werden Kontoanfragen nicht per Mail gemeldet – offene Anfragen stehen aber immer oben unter „Nutzer“.

## Wie die Anwendung abgesichert ist

- **Anmeldung:** Sitzungs-Cookie (HttpOnly, SameSite=Lax, mit `COOKIE_SECURE` nur über HTTPS), Passwörter als Werkzeug-Hash. Schreibende API-Aufrufe verlangen `Sec-Fetch-Site: same-origin` und einen JSON-Body oder `X-Requested-With` – ein Formular von einer fremden Seite erfüllt das nicht.
- **Passwort-Reset:** Der Link trägt den Token hinter `#`. Fragmente schickt der Browser nicht an den Server, der Token steht also weder im Zugriffsprotokoll noch im Referer. Das Protokoll von Gunicorn führt ohnehin nur den Pfad, nicht die Abfrage. Ein Token wird ungültig, sobald das Passwort geändert wurde; gesperrte und noch nicht freigegebene Konten weist der Reset ab.
- **Kontoanfragen** antworten immer gleich, auch wenn es die Adresse schon gibt – von außen ist nicht zu erkennen, wer hier ein Konto hat. Der Inhaber bekommt stattdessen eine Hinweismail.
- **Medien:** Bilder und Videos hinter der Anmeldung werden als `Cache-Control: private` ausgeliefert, landen also in keinem gemeinsamen Zwischenspeicher. Alle Mediendateien bekommen eine eigene, sehr enge CSP – auch ein direkt aufgerufenes SVG kann damit nichts ausführen.
- **Sitzungsschlüssel:** wird beim ersten Start exklusiv angelegt, damit nicht zwei Gunicorn-Worker mit verschiedenen Schlüsseln starten (das äußerte sich sonst in sporadischen Abmeldungen).
- **JavaScript-Bibliotheken** werden beim Bauen gegen `vendor.sha256` geprüft. Nach einem Versionswechsel im Dockerfile die Prüfsummen neu erzeugen (Anleitung steht in der Datei).
- **Wiki-Inhalte** werden im Browser gerendert und mit DOMPurify bereinigt; Seiten liefern eine CSP mit Nonce, kein `unsafe-inline` für Skripte.

## Daten und Sicherung

Alles liegt im Volume `/data`: `stroemis.db` (SQLite), `media/orig` (Originale), `media/web` und `media/thumb` (erzeugte Varianten), `media/wiki` (Wiki-Bilder), `media/avatar` (Profilbilder), `secret_key`. Für ein Backup reicht es, das Volume zu kopieren, z. B.

```bash
docker run --rm -v stroemis_stroemis-data:/data -v "$PWD":/backup alpine tar czf /backup/stroemis-$(date +%F).tgz -C /data .
```

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
```

Die JavaScript-Bibliotheken liegen im Arbeitsbaum unter `app/static/vendor/` und werden im Docker-Build noch einmal frisch geladen und gegen `vendor.sha256` geprüft.

`tests/rundlauf.html` prüft die zentrale Invariante des Editors – Markdown öffnen und speichern darf kein Byte ändern – über einen Korpus aus 66 Fällen. Ein zweiter Abschnitt prüft den Rückgängig-Verlauf (ein Strg+Z direkt nach dem Laden darf am Dokument nichts ändern, eigene Änderungen müssen weiterhin rückgängig zu machen sein), gesetzte Leerzeilen, das Auflösen unvollständiger Abschnitte und die Grenzen des Renderers: Aufgabenlisten behalten ihr Kästchen, Formulare und Stilblöcke aus dem Seitentext kommen nicht durch. Ein dritter Abschnitt prüft die zusammengefassten Zellen: dass ein Zug über mehrere Zellen überhaupt eine Zellauswahl ergibt (das Bündel von Toast UI ist an dieser Stelle fehlerhaft übersetzt und wird geflickt), dass Verbinden und Teilen die erwartete Schreibweise ergeben und dass die Leseansicht daraus `colspan` und `rowspan` macht – mit Gegenproben, die ohne die Reparatur beziehungsweise ohne die Nachbearbeitung fehlschlagen müssen. Die Datei lädt die Projektskripte über relative Pfade; ein Doppelklick genügt, ein Server ist nicht nötig.

`tests/gleichstand.html` hält Leseansicht und Editor nebeneinander und misst für 17 Bausteine Schriftgröße, Schnitt, Farbe, Auszeichnung, Ausrichtung und den linken Textanfang – die Probe darauf, dass der Editor zeigt, was der Artikel später zeigt.

`tests/nachgeholtes_speichern.html` prüft, dass das automatische Speichern niemals die falsche Seite trifft: Ein Speichervorgang, der seinen eigenen Editor überlebt, weil die Anfrage hängt und man inzwischen die Seite gewechselt hat, darf den Text der neuen Seite nicht unter der Kennung der alten ablegen. Die Datei fährt das Wiki mit einem nachgestellten Server hoch, der jede Schreibanfrage so lange festhält, bis der Test sie freigibt – der Ablauf hängt damit an keiner Laufzeit. Auch hier genügt ein Doppelklick.

`tests/live_mitlesen.html` prüft das Mitlesen: Sobald jemand anderes schreibt, meldet sich der Leser alle 4 statt alle 15 Sekunden, holt jede neue Fassung und zeichnet den Artikel nach – der oberste sichtbare Absatz bleibt dabei auf ±2 px an seiner Stelle, auch wenn oberhalb ein Absatz eingefügt wurde; unter einer Textauswahl wird nicht gezeichnet, und nach dem Weggang des Schreibers kommt der letzte Stand noch an, danach gilt wieder der lange Takt. Der Lauf dauert rund eine halbe Minute, weil die echten Takte gelten.

## Aufbau

```
app/
  __init__.py      App-Factory, Seiten-Routen, Medienauslieferung, CSRF-Schutz, Security-Header
  auth.py          Login, Registrierung, Reset, Profil (Session-Cookie, Werkzeug-Hashes)
  api_albums.py    Alben, Bilder, Kartendaten
  api_wiki.py      Seiten, Versionen, Suche, Freigaben, Kommentare, öffentliche API, Datei-Upload, Export
  api_admin.py     Nutzerverwaltung
  images.py        EXIF (GPS, Höhe, Zeit), Ausrichtung, Thumbnails, HEIC, Videos nach H.264
  medienpflege.py  Bestandsvideos nach dem Start im Hintergrund wandeln (eine Sperre, ein Arbeiter)
  db.py            SQLite-Schema, Migrationen, Transaktionsklammer
  mailer.py        SMTP-Versand (ohne SMTP_HOST landet die Mail im Log)
  templates/       Jinja-Seiten
  static/css/      app.css – ein Blatt für alle Ansichten
  static/fonts/    DLRG Univers als WOFF2 (Regular, Kursiv, Fett)
  static/img/      Favicon, optional die DLRG-Wortmarke
  static/vendor/   Leaflet, markercluster, marked, DOMPurify, Toast UI (im Docker-Build geladen)
  static/js/       common.js       gemeinsame Helfer (api, esc, dialog, toast, Datum)
                   markdown.js     Renderer: Callouts, Spalten, Boxen, Videos, TOC, Auszeichnungen
                   editor-format.js  Markdown <-> Editorformat (reine Funktionen, trägt den Rundlauf)
                   editor-layout.js  Darstellung der Abschnitte im Editor (ProseMirror-Dekorationen)
                   editor-verlauf.js Rückgängig-Verlauf: Laden gehört nicht hinein
                   wiki.js         Editor, Seitenbaum, Kommentare, Teilen, Verlauf
                   public.js       öffentliches Wiki
                   map.js          Karte, Alben, Upload, Lokalisieren, Bild-Detail
                   admin.js, auth.js, profile.js
tests/
  test_smoke.py    Rauch- und Härtungstest über die API
  rundlauf.html    Rundlauf, Rückgängig-Verlauf und verbundene Zellen im Browser prüfen (Datei einfach öffnen)
  gleichstand.html Leseansicht und Editor nebeneinander messen (Datei einfach öffnen)
  nachgeholtes_speichern.html
                   Automatisches Speichern trifft nie die falsche Seite (Datei einfach öffnen)
  live_mitlesen.html
                   Mitlesen bei fremdem Schreiber: kurzer Takt, Nachzeichnen, Lesestelle bleibt
```

Hinweise: iPhone-Videos im HEVC-Format (.mov) werden beim Hochladen und für den Bestand nach H.264 gewandelt – ohne ffmpeg (etwa in einer Entwicklungsumgebung ohne Container) bleibt es beim Original, das dann nur Safari abspielt. Die Nutzungsbedingungen der OSM-/OpenTopoMap-Kachelserver gelten für kleine Nutzergruppen; bei größerem Aufkommen `TILE_URL` auf einen eigenen oder kommerziellen Kachelserver umstellen.
