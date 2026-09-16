/* Markdown <-> Editorformat.
   Gespeichert wird Docmost-Markdown (":::info", ":::columns" mit "|||", ":::accordion",
   ":::align", ":::toc", ":::unterseiten", ":::seitenumbruch"). Im Editor werden daraus
   Marken-Abschnitte ($$hinweis / $$spalten / $$spalte / $$ausrichtung / $$akkordeon /
   $$koerper / $$ende); der Inhalt dazwischen bleibt gewoehnlicher, direkt bearbeitbarer Text.
   Diese Datei enthaelt nur reine Funktionen ueber Zeichenketten – kein DOM, kein Editor.
   Sie traegt die zentrale Invariante des Projekts: oeffnen und speichern aendert kein Byte. */
window.EDMD = (function () {
  const MD = window.MD;

  const HINWEIS_NAME = { info: "Hinweis", tip: "Tipp", warning: "Achtung",
                         success: "Vorteil", danger: "Gefahr", note: "Notiz" };
  function hinweisKopf(literal) {
    const kopf = String(literal || "").trim().split(/\s+/);
    const kind = kopf[0] && kopf[0].toLowerCase() in MD.CALLOUTS ? kopf[0].toLowerCase() : "info";
    let farbe = "";
    const rest = kopf.slice(1).filter((t) => {
      const m = /^farbe:([a-zäöü]+)$/i.exec(t);
      if (m && m[1].toLowerCase() in MD.CALLOUT_FARBEN) { farbe = m[1].toLowerCase(); return false; }
      return true;
    });
    return { kind, emoji: rest.join(" ") || MD.CALLOUTS[kind], farbe };
  }
  // Kopfzeile eines Hinweises zusammensetzen – Art, Emoji und (falls gewählt) Farbe.
  // Als Funktionsdeklaration, weil SNIPPETS weiter oben schon darauf zugreift.
  function hinweisZeile(kind, emoji, farbe) {
    return `${kind} ${emoji || MD.CALLOUTS[kind]}${farbe ? " farbe:" + farbe : ""}`.trim();
  }

  const isFenceOpen = (l) => /^:::[ \t]*[A-Za-z]/.test(l) && !/:::[ \t]*$/.test(l.slice(3));
  const isFenceClose = (l) => /^:::[ \t]*$/.test(l);
  // Trennzeile zwischen zwei Spalten.
  const TRENNER = /^[ \t]*\|\|\|[ \t]*$/;

  /* Spalten und Ausrichtung erscheinen im Editor nicht als geschlossener Block, sondern als
     schmale Marken; der Inhalt dazwischen bleibt ein ganz normaler Absatz, eine Liste, ein Bild
     und ist damit direkt bearbeitbar. Ein Custom-Block von Toast UI nimmt ausschliesslich Text
     auf und ist atomar – dort kann der Cursor gar nicht stehen, deshalb der Umweg.
       :::columns  <->  $$spalten     |||  <->  $$spalte     :::  <->  $$ende
       :::align X  <->  $$ausrichtung mit X in der ersten Zeile                                */
  const teileSpalten = (body) => {
    const teile = [[]];
    const maske = MD.fenceMask(body);
    let tiefe = 0;
    body.forEach((l, i) => {
      if (maske[i]) { teile[teile.length - 1].push(l); return; }   // im Codeblock trennt nichts
      if (isFenceOpen(l)) tiefe++;
      else if (isFenceClose(l) && tiefe) tiefe--;
      else if (!tiefe && TRENNER.test(l)) { teile.push([]); return; }
      teile[teile.length - 1].push(l);
    });
    return teile;
  };

  // Marken, die einen Abschnitt eröffnen – Spalten, Ausrichtung, Hinweis. "$$ende" schließt alle.
  const ABSCHNITT_AUF = new Set(["$$spalten", "$$ausrichtung", "$$hinweis", "$$akkordeon", "$$baustein"]);

  function wandleBloecke(lines) {
    const out = [];
    // Zeilen in geschlossenen Codeblöcken sind Text, keine Blockgrenzen – dieselbe Maske,
    // mit der auch die Leseansicht arbeitet.
    const maske = MD.fenceMask(lines);
    // Eine Marke braucht Leerzeilen um sich herum, sonst zieht der Markdown-Parser sie in den
    // vorhergehenden Absatz. Auf dem Rueckweg fallen sie wieder weg.
    const marke = (...zeilen) => {
      while (out.length && !out[out.length - 1].trim()) out.pop();
      if (out.length) out.push("");
      out.push(...zeilen, "$$", "");
    };
    let zaun = null;                                 // offener Codeblock
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const f = /^\s{0,3}(`{3,}|~{3,})/.exec(line);
      if (f) { zaun = zaun && line.trim().startsWith(zaun) ? null : (zaun || f[1]); out.push(line); continue; }
      if (zaun) { out.push(line); continue; }        // ":::" im Codeblock ist Text, kein Block
      const m = isFenceOpen(line) && /^:::[ \t]*([A-Za-z]+)([^\n]*)$/.exec(line);
      if (!m) { out.push(line); continue; }
      const name = m[1].toLowerCase(), args = (m[2] || "").trim();
      let depth = 1, end = -1;                       // Ende des Blocks suchen, Verschachtelung mitzaehlen
      for (let j = i + 1; j < lines.length; j++) {
        if (maske[j]) continue;                      // ":::" im Codebeispiel schließt nichts
        if (isFenceOpen(lines[j])) depth++;
        else if (isFenceClose(lines[j])) { depth--; if (!depth) { end = j; break; } }
      }
      // Ohne Abschluss zeigt auch die Leseansicht die Zeile als Text – dann hier ebenso,
      // sonst verschluckt der Editor den ganzen Rest des Artikels.
      if (end < 0) { out.push(line); continue; }
      const body = lines.slice(i + 1, end);
      if (name === "columns") {
        marke("$$spalten");
        teileSpalten(body).forEach((teil, k) => { if (k) marke("$$spalte"); out.push(...wandleBloecke(teil)); });
        marke("$$ende");
        i = end; continue;
      }
      /* Synchronisierte Abschnitte. Der Baustein hält den Inhalt und verhält sich wie jeder
         andere Abschnitt; der Einbau hat keinen eigenen Inhalt, nur ein Ziel – er wird deshalb
         zu einer einzelnen Marke ohne "$$ende". Steht im Rumpf doch etwas, bleibt die Zeile
         :::-Text, sonst ginge dieser Inhalt beim Speichern verloren. */
      if (name === "baustein") {
        marke("$$baustein", args.trim() || "abschnitt");
        out.push(...wandleBloecke(body));
        marke("$$ende");
        i = end; continue;
      }
      if (name === "einbau" && !body.some((l) => l.trim())) {
        marke("$$einbau", args.trim());
        i = end; continue;
      }
      if (name === "align") {
        marke("$$ausrichtung", MD.ALIGNS.has(args.toLowerCase()) ? args.toLowerCase() : "center");
        out.push(...wandleBloecke(body));
        marke("$$ende");
        i = end; continue;
      }
      if (name in MD.CALLOUTS && !body.some((l) => l.trim().startsWith("$$"))) {
        marke("$$hinweis", `${name} ${args || MD.CALLOUTS[name]}`.trim());
        out.push(...wandleBloecke(body));            // Rekursion: Spalten und Boxen im Hinweis
        marke("$$ende");
        i = end; continue;
      }
      /* Die einklappbare Box wird wie der Hinweis zu Marken: der Titel steht als
         gewoehnlicher Absatz zwischen "$$akkordeon" und "$$koerper", der Inhalt dahinter.
         Beides ist damit unmittelbar im Text bearbeitbar – kein Dialog mehr. */
      if (name === "accordion" && !body.some((l) => l.trim().startsWith("$$"))) {
        marke("$$akkordeon");
        out.push((args || "Details").trim());
        marke("$$koerper");
        out.push(...wandleBloecke(body));
        marke("$$ende");
        i = end; continue;
      }
      const head = MD.MARKERS.includes(name) ? [`$$${name}`] : null;
      // Steht im Block selbst eine Zeile mit "$$" (etwa LaTeX), wuerde das Zurueckwandeln ihn an der
      // falschen Stelle schliessen. Solche Bloecke bleiben :::-Text: der Renderer zeigt sie weiterhin,
      // nur das Stift-Symbol im Editor entfaellt. Besser als ein zerschossener Inhalt.
      if (!head || body.some((l) => l.trim().startsWith("$$"))) out.push(...lines.slice(i, end + 1));
      else out.push(...head, ...body, "$$");
      i = end;
    }
    return out;
  }

  /* Ein Absatz, dessen Quelle über mehrere Zeilen läuft, ist in Markdown EIN Absatz: Der
     einzelne Zeilenumbruch zählt wie ein Leerzeichen, und die Leseansicht setzt ihn auch so.
     Toast UI macht daraus je Zeile einen eigenen Absatz. Der Editor zeigte dadurch mehr
     Absätze als der Artikel, mit Abstand dazwischen, und beim Speichern wurden echte Absätze
     daraus – aus einem Absatz wurden drei, ohne dass jemand etwas geschrieben hätte.
     Deshalb werden die Zeilen eines Absatzes hier zusammengezogen. Nicht angetastet werden
     Codeblöcke, Listen, Zitate, Tabellen, Überschriften, Marken und HTML – und ein harter
     Umbruch (zwei Leerzeichen oder ein Rückstrich am Zeilenende) bleibt ebenfalls stehen. */
  // Beliebig eingerückt: Ein Listenpunkt der zweiten Ebene steht vier Leerzeichen tief und
  // ist trotzdem ein Blockanfang – ohne das zöge die Zeile zum Punkt darüber.
  const BLOCKZEILE = /^[ \t]*(?:[-*+][ \t]|\d+[.)][ \t]|>|#{1,6}[ \t]|\||:::|\$\$|<|={3,}[ \t]*$|-{3,}[ \t]*$|_{3,}[ \t]*$|`{3,}|~{3,})/;
  function absaetzeZusammenziehen(lines) {
    const zaun = MD.fenceMask(lines);
    const out = [];
    const her = [];                                    // Herkunftszeile je Ausgabezeile
    lines.forEach((z, i) => {
      const vorher = out.length ? out[out.length - 1] : null;
      const vorherZaun = out.length ? zaun[her[her.length - 1]] : true;
      // Ein Zitat über mehrere Zeilen ist ebenfalls EIN Absatz: „> eins“ und „> zwei“
      // gehören zusammen. Eine leere Zitatzeile („>“) trennt dagegen zwei Absätze.
      const zitatFort = /^[ \t]*>[ \t]*\S/.test(z) && /^[ \t]*>[ \t]*\S/.test(vorher || "");
      const anhaengen = vorher !== null && z.trim() && vorher.trim()
        && !zaun[i] && !vorherZaun
        && (zitatFort || (!BLOCKZEILE.test(z) && !BLOCKZEILE.test(vorher)));
      if (!anhaengen) { out.push(z); her.push(i); return; }
      // Harter Umbruch (zwei Leerzeichen oder Rückstrich am Zeilenende): Er bleibt erhalten,
      // aber als Zeichen im selben Absatz – der Editor zeigt dafür einen Umbruch (siehe
      // MD.UMBRUCH). Ohne das ginge er beim Öffnen verloren und die Wörter klebten zusammen.
      const hart = /(?: {2,}|\\)$/.test(vorher);
      // Beim Zitat fällt das „>“ der Folgezeile weg – die Zeile hängt sich an die erste an.
      const rumpf = zitatFort ? z.replace(/^[ \t]*>[ \t]?/, "").trim() : z.trim();
      out[out.length - 1] = vorher.replace(/(?: +|\\)$/, "") + (hart ? MD.UMBRUCH : " ") + rumpf;
    });
    return out;
  }

  function toEditorMd(md) {
    // <u>/<mark>/<sub>/<sup> aus Importen in die Textschreibweise bringen: als rohes HTML
    // würde der Editor sie beim Speichern verwerfen (siehe markdown.js).
    // Bildtitel als Unterschrift überlebt den Editor nicht – in die kursive Zeile darunter umschreiben.
    const roh = String(md || "").replace(/\r\n/g, "\n").split("\n");
    const zaun = MD.fenceMask(roh);
    // Zeilenweise und zaunbewusst: ein HTML- oder Bildbeispiel im Codeblock darf nicht
    // umgeschrieben werden, sonst zerstört schon das Öffnen des Editors das Beispiel.
    const vorbereitet = roh.map((z, i) => (zaun[i] ? z
      : MD.htmlMarksToSyntax(z).replace(/^(!\[[^\]]*\]\([^)\s]+)\s+"([^"]+)"\)\s*$/, "$1)\n\n*$2*")))
      .join("\n");
    // Marken enden immer mit einer Leerzeile. Steht ein Abschnitt am Textende, würde daraus
    // ein leerer Absatz – und der käme beim Speichern als "<br>" zurück.
    return wandleBloecke(absaetzeZusammenziehen(vorbereitet.split("\n"))).join("\n").replace(/\n+$/, "");
  }

  /* Aufraeumen der Marken-Abschnitte: Leerzeilen, die nur die Marken im Editor umgeben haben,
     verschwinden wieder; eine Waise (|||, ::: ohne offenen Abschnitt) wird verworfen. Damit
     bleibt das gespeicherte Markdown auch dann gueltig, wenn jemand eine Marke geloescht hat. */
  function ordneMarken(lines) {
    const out = [];
    const letzte = () => (out.length ? out[out.length - 1] : null);
    const leerWeg = () => { while (out.length && !out[out.length - 1].trim()) out.pop(); };
    let zaun = null;                                   // offener Codeblock
    let tiefe = 0;                                     // offene :::-Abschnitte
    for (const l of lines) {
      const f = /^\s{0,3}(`{3,}|~{3,})/.exec(l);
      if (f) { zaun = zaun && l.trim().startsWith(zaun) ? null : (zaun || f[1]); out.push(l); continue; }
      if (zaun) { out.push(l); continue; }             // im Codeblock bleibt jede Zeile, wie sie ist
      if (isFenceOpen(l)) {
        const vorher = letzte();
        leerWeg();
        // Vom vorhergehenden Inhalt trennt eine Leerzeile – nicht aber von einer Marke,
        // die unmittelbar davor steht: dort beginnt der Abschnitt ohne Zwischenraum.
        if (out.length && !isFenceOpen(vorher || "") && !TRENNER.test(vorher || "")) out.push("");
        tiefe++;
        out.push(l);
        continue;
      }
      // Trenner und Abschluss nur zurechtrücken, solange wirklich ein Abschnitt offen ist –
      // sonst ist "|||" oder ":::" gewöhnlicher Text und behält seine Leerzeilen.
      if (tiefe && (TRENNER.test(l) || isFenceClose(l))) {
        if (isFenceClose(l)) tiefe--;
        leerWeg(); out.push(l); continue;
      }
      const vor = letzte();
      // Ein Absatz aus einem geschützten Leerzeichen ist eine GESETZTE Leerzeile (siehe unten,
      // LEERZEILE) – trim() hielte ihn für leer und würfe ihn als „doppelt“ weg: Die Leerzeile
      // überlebte das Öffnen, aber nicht das erste Speichern danach.
      if (!l.replace(/\u00a0/g, "x").trim()) {
        // Keine Leerzeile unmittelbar nach einer öffnenden Marke und keine doppelten.
        if (vor === null || !vor.trim() || isFenceOpen(vor) || (tiefe && TRENNER.test(vor))) continue;
        out.push(l); continue;
      }
      if (vor !== null && isFenceClose(vor)) out.push("");   // nach dem Abschluss trennen
      out.push(l);
    }
    return out;
  }

  // Meldet, ob beim letzten Rückwandeln unvollständige Abschnitte begradigt wurden – dann
  // hat jemand eine Marke gelöscht, und der Abschnitt verschwindet beim Speichern.
  let markenRepariert = false;
  /* Der Titel einer einklappbaren Box steht im Editor als gewöhnlicher Absatz zwischen
     "$$akkordeon" und "$$koerper". Gespeichert gehört er in die Kopfzeile ":::accordion …",
     denn nur dort liest ihn die Leseansicht. Mehrere Zeilen werden zu einer zusammengezogen;
     eine Abschnittszeile hat im Titel nichts verloren und fliegt heraus. */
  const titelUebernehmen = (out, eintrag) => {
    if (!eintrag || eintrag.pos == null) return;
    const roh = out.splice(eintrag.pos + 1).map((z) => z.trim()).filter(Boolean);
    const titel = roh.filter((z) => !/^(:::|\|\|\|)/.test(z));
    if (titel.length !== 1 || titel.length !== roh.length) markenRepariert = true;
    // Ohne Titel bleibt die Kopfzeile leer: „:::accordion“ und „:::accordion Details“ sind zwei
    // verschiedene Texte, und das Speichern soll keinen Titel erfinden, den niemand geschrieben hat.
    out[eintrag.pos] = `:::accordion ${titel.join(" ")}`.trimEnd();
    eintrag.pos = null;
  };
  /* Ein "|" in einer Tabellenzelle muss escaped sein, sonst zerlegt der Tabellenparser die
     Zeile – auch innerhalb von `Code`. Toast UI escapt es außerhalb von Code korrekt, innerhalb
     aber nicht; ohne diese Nachbesserung verlöre die Zelle beim nächsten Öffnen ihren Inhalt. */
  const TABELLENZEILE = /^[ \t]{0,3}\|/;
  function pipesInCodeSchuetzen(zeile) {
    if (!TABELLENZEILE.test(zeile) || zeile.indexOf("`") < 0) return zeile;
    let out = "", i = 0, zaun = 0;
    while (i < zeile.length) {
      const c = zeile[i];
      // Außerhalb von Code schützt ein Rückstrich das nächste Zeichen; INNERHALB nicht –
      // sonst schlucken wir dort den schließenden Backtick und escapen ab da alles doppelt.
      if (c === "\\" && !zaun && i + 1 < zeile.length) { out += c + zeile[i + 1]; i += 2; continue; }
      if (c === "`") {
        let n = 0; while (zeile[i + n] === "`") n++;
        if (!zaun) zaun = n; else if (n === zaun) zaun = 0;
        out += "`".repeat(n); i += n; continue;
      }
      if (c === "|" && zaun) { out += "\\|"; i++; continue; }
      out += c; i++;
    }
    return out;
  }

  function fromEditorMd(md) {
    markenRepariert = false;
    // Ausgezeichnete Stellen gibt der Editor als "$$widgetN ++text++$$" zurück – Klammer weg.
    let src = String(md || "").replace(/\$\$widget\d+ ([\s\S]*?)\$\$/g, "$1");
    // Der harte Umbruch kommt als Zeichen zurück und wird wieder zu zwei Leerzeichen und
    // einem Zeilenumbruch – der Schreibweise, die auch die Leseansicht liest.
    src = src.split(MD.UMBRUCH).join("  \n");
    // Adressen kommen prozentkodiert zurück; die Bildbreite ![x](a.jpg#w=50%) darf das nicht verlieren.
    src = src.replace(/(#w=\d{1,4})%25/g, "$1%");
    const lines = src.replace(/\r\n/g, "\n").split("\n");
    const out = []; let open = false;
    const stapel = [];                               // offene Marken-Abschnitte
    let zaun = null;                                 // offener Codeblock
    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];
      let m;
      const f = /^\s{0,3}(`{3,}|~{3,})/.exec(line);
      if (!open && f) { zaun = zaun && line.trim().startsWith(zaun) ? null : (zaun || f[1]); out.push(line); continue; }
      if (zaun) { out.push(line); continue; }
      /* Zusammengefasste Zellen schreibt Toast UI als "@cols=2:"/"@rows=2:" vor den Inhalt – beim
         Verbinden auch dann, wenn die Zelle gar nicht über mehrere Spalten oder Zeilen geht. Ein
         "@rows=1:" liest der Editor beim nächsten Öffnen nicht mehr zurück und schriebe es auch
         nicht wieder: Ohne dieses Wegräumen wäre schon Öffnen und Speichern eine Änderung, und
         das Wiki legte eine Fassung an, in der nichts steht. */
      if (line.startsWith("|")) {
        line = line.replace(/(\|[ \t]*)((?:@(?:cols|rows)=\d+:)+)/g,
                            (ganz, strich, praefix) => strich + praefix.replace(/@(?:cols|rows)=1:/g, ""));
      }
      if (!open && (m = /^\$\$(spalten|spalte|ausrichtung|hinweis|akkordeon|koerper|baustein|einbau|ende)[ \t]*$/.exec(line))) {
        const art = m[1];
        // Vorbedingung statt Nachbesserung: ohne das schließende "$$" ist das kein Block,
        // sondern gewöhnlicher Text, den jemand genau so getippt hat.
        const rumpfZeilen = ["ausrichtung", "hinweis", "baustein", "einbau"].includes(art) ? 1 : 0;
        if (!/^\$\$[ \t]*$/.test(lines[i + 1 + rumpfZeilen] || "")) { out.push(line); continue; }
        let arg = "";
        if (rumpfZeilen) { arg = (lines[i + 1] || "").trim(); i++; }
        i++;                                              // das schließende "$$" der Marke
        const oben = stapel[stapel.length - 1] || null;
        if (art === "spalten") { out.push(":::columns"); stapel.push({ art: "columns", start: out.length - 1, trenner: [] }); }
        else if (art === "akkordeon") {
          // Der Titel folgt erst; die Kopfzeile wird bei "$$koerper" nachgetragen.
          out.push(":::accordion Details");
          stapel.push({ art: "accordion", pos: out.length - 1, start: out.length - 1 });
        } else if (art === "ausrichtung") { out.push(`:::align ${MD.ALIGNS.has(arg.toLowerCase()) ? arg.toLowerCase() : "center"}`); stapel.push({ art: "align", start: out.length - 1 }); }
        else if (art === "hinweis") {
          const kopf = arg.split(/\s+/);
          const ck = (kopf[0] || "info").toLowerCase();
          const emoji = kopf.slice(1).join(" ");
          out.push(`:::${ck in MD.CALLOUTS ? ck : "info"}${emoji ? " " + emoji : ""}`);
          stapel.push({ art: "callout", start: out.length - 1 });
        } else if (art === "baustein") { out.push(`:::baustein ${arg || "abschnitt"}`); stapel.push({ art: "baustein", start: out.length - 1 }); }
        else if (art === "einbau") { out.push(`:::einbau ${arg}`.trimEnd(), ":::"); }
        else if (art === "spalte") { if (oben && oben.art === "columns") { out.push("|||"); oben.trenner.push(out.length - 1); } else markenRepariert = true; }
        else if (art === "koerper") { if (oben && oben.art === "accordion") titelUebernehmen(out, oben); else markenRepariert = true; }
        else if (stapel.length) {
          const zu = stapel.pop();
          // Fehlt die Trennmarke, ist der ganze Abschnitt Titel – dann bleibt die Box leer.
          if (zu.pos != null) { titelUebernehmen(out, zu); markenRepariert = true; }
          out.push(":::");
        }
        else markenRepariert = true;                 // Abschluss ohne Anfang
        continue;
      }
      // Ältere Entwürfe aus dem Browserspeicher können noch die geschlossene Form enthalten.
      if (!open && (m = /^\$\$(callout|columns|accordion|align|toc|unterseiten|seitenumbruch)[ \t]*$/.exec(line))) {
        const kind = m[1];
        if (MD.MARKERS.includes(kind)) out.push(":::" + kind);
        else if (kind === "columns") out.push(":::columns");
        else {
          const arg = (lines[i + 1] || "").trim(); i++;
          if (kind === "callout") {
            const head = arg.split(/\s+/);
            const ck = (head[0] || "info").toLowerCase();
            const emoji = head.slice(1).join(" ");
            out.push(`:::${ck in MD.CALLOUTS ? ck : "info"}${emoji ? " " + emoji : ""}`);
          } else if (kind === "accordion") out.push(`:::accordion ${arg || "Details"}`);
          else out.push(`:::align ${MD.ALIGNS.has(arg.toLowerCase()) ? arg.toLowerCase() : "center"}`);
        }
        open = true; continue;
      }
      if (open && /^\$\$[ \t]*$/.test(line)) { out.push(":::"); open = false; continue; }
      out.push(line);
    }
    /* Fehlt die Schlussmarke, wird der Abschnitt AUFGELÖST: Öffnungszeile und Spaltentrenner
       fallen weg, der Inhalt bleibt gewöhnlicher Text – genau das sagen Editor und Statuszeile
       („Marken entfernt, Inhalt bleibt“). Früher wurde er stattdessen bis zum Dokumentende
       geschlossen und zog alles Folgende mit in den Hinweis, die Spalten oder den Baustein.
       Von oben nach unten abbauen: Der zuletzt geöffnete Abschnitt liegt am weitesten hinten,
       sein Herausnehmen verschiebt die Zeilen der früheren nicht. */
    while (stapel.length) {
      const zu = stapel.pop();
      // „start“ ist die Öffnungszeile; „pos“ bleibt dem Akkordeon vorbehalten (Titelübernahme
      // bei fehlender Trennmarke) – beides zu vermischen ließ jede Schlussmarke ein Akkordeon sehen.
      for (const t of (zu.trenner || []).slice().reverse()) out.splice(t, 1);
      if (zu.start != null) out.splice(zu.start, 1);
      markenRepariert = true;
    }
    if (open) out.push(":::");
    // Steht am Textende ein $$-Block, hängt Toast UI einen leeren Absatz an; der käme als
    // "<br>" zurück und stünde beim nächsten Öffnen als Text da.
    /* Eine Leerzeile, die jemand mit der Eingabetaste gesetzt hat, schreibt Toast UI als
       einzelne "<br>"-Zeile. Markdown liest daraus einen HTML-Block – und der verschluckt den
       Absatz, der unmittelbar darauf folgt: Er verschwand in der Leseansicht spurlos. Ein
       Absatz mit geschütztem Leerzeichen leistet dasselbe und bleibt ein Absatz. Er überlebt
       auch den Weg zurück in den Editor, wo er als sichtbare Leerzeile steht. */
    let imZaun = null;
    const LEERZEILE = /^[ \t]*(?:<br\s*\/?>|\u00a0|&nbsp;)[ \t]*$/i;
    const fertig = [];
    // Zuerst das Ende beschneiden: Toast UI hängt hinter einem Block am Textende von sich aus
    // einen leeren Absatz an. Der ist keine gesetzte Leerzeile und darf nicht zu einer werden.
    const roh = ordneMarken(out);
    while (roh.length && /^[ \t]*(?:<br\s*\/?>|\u00a0)?[ \t]*$/i.test(roh[roh.length - 1])) roh.pop();
    roh.forEach((zeile) => {
      const f = /^\s{0,3}(`{3,}|~{3,})/.exec(zeile);
      if (f) { imZaun = imZaun && zeile.trim().startsWith(imZaun) ? null : (imZaun || f[1]); fertig.push(zeile); return; }
      if (imZaun) { fertig.push(zeile); return; }
      if (LEERZEILE.test(zeile)) {
        // Ein eigener Absatz – ohne die Leerzeilen ringsum zöge Markdown ihn mit dem
        // Nachbarn zu einem einzigen zusammen.
        if (fertig.length && fertig[fertig.length - 1].trim()) fertig.push("");
        fertig.push("&nbsp;", "");
        return;
      }
      if (!zeile.trim() && fertig.length && !fertig[fertig.length - 1].trim()) return;  // keine doppelten
      fertig.push(pipesInCodeSchuetzen(zeile));
    });
    while (fertig.length && !fertig[fertig.length - 1].trim()) fertig.pop();
    return fertig.join("\n");
  }

  /* Ein Hinweis wird als Markenpaar eingefügt – der Inhalt dazwischen ist gewöhnlicher
     Editorinhalt und wird direkt im Text bearbeitet, ohne Umweg über einen Dialog. */
  const hinweisMd = (kind, emoji, inhalt, farbe) =>
    `$$hinweis\n${hinweisZeile(kind, emoji, farbe)}\n$$\n\n${inhalt}\n\n$$ende\n$$\n`;
  /* Einklappbare Box: Titel und Inhalt stehen zwischen den Marken und sind gewöhnlicher Text. */
  const akkordeonMd = (titel, inhalt) =>
    `$$akkordeon\n$$\n\n${titel}\n\n$$koerper\n$$\n\n${inhalt}\n\n$$ende\n$$\n`;
  const SNIPPETS = {
    accordion: akkordeonMd("Titel der Box", "Inhalt, der erst nach dem Aufklappen sichtbar ist."),
    // Ohne <details>: rohes HTML in einer Tabellenzelle verwirft der WYSIWYG-Editor beim
    // Speichern. Für ausklappbare Inhalte gibt es die einklappbare Box ($$accordion).
    fehler: "## Typische Fehler\n\n| Fehler | Fehlerbild |\n| --- | --- |\n| **Fehlername** – Erklärung des Fehlers und seiner Folgen. |     |\n",
  };

  // Ein synchronisierter Abschnitt und sein Einbau – in der Marken-Schreibweise des Editors.
  const bausteinMd = (kennung) =>
    `$$baustein\n${(kennung || "abschnitt").trim()}\n$$\n\nInhalt, der auch auf anderen Seiten erscheinen soll.\n\n$$ende\n$$\n`;
  const einbauMd = (slug, kennung) => `$$einbau\n${slug}#${kennung}\n$$\n`;


  /* --- Zerlegung in oberste Blöcke -----------------------------------------------------
     Reine Textarbeit, aber die Grundlage für alles, was einen Block im Editor einer Stelle im
     Markdown zuordnet: Blockmenü, Ziehgriff, Ausrichtung. Deshalb steht sie hier und nicht im
     Editor – hier ist sie prüfbar. */
  const MARKEN_RE = /^\$\$(callout|columns|accordion|align|toc|unterseiten|seitenumbruch|spalten|spalte|ausrichtung|hinweis|akkordeon|koerper|baustein|einbau|ende)[ \t]*$/;
  // Zeilenanfänge, bei denen mehrere Zeilen zu EINEM Block im Editor gehören.
  const MEHRZEILIG = /^\s{0,3}(?:[-*+][ \t]|\d+[.)][ \t]|>|\||#{1,6}[ \t])/;
  /* Eine Zeile aus nichts als "<br>" ist im Editor ein leerer Absatz und zählt dort nicht
     als Block (blockEls lässt ihn weg). Toast UI hängt genau so eine Zeile an, sobald der
     Text mit einem $$-Block endet – ohne diese Gleichstellung zählte der Text einen Block
     mehr als der Editor, und Ausrichtung, Blockmenü und Ziehgriff verweigerten in jedem
     Artikel den Dienst, der mit Spalten, Hinweis oder Box aufhört.
     Nur am Blockanfang: mitten in einer Aufzählung trennt Toast UI zwei Absätze desselben
     Punktes ebenfalls mit einer solchen Zeile – dort gehört sie zum laufenden Block. */
  const LEERZEILE = (l) => !l.trim() || /^\s*<br\s*\/?>\s*$/i.test(l);
  const topLevelBlocks = (md) => {
    const lines = md.split("\n");
    const blocks = [];
    let i = 0;
    while (i < lines.length) {
      if (LEERZEILE(lines[i])) { i++; continue; }
      const start = i;
      let end;
      const fence = /^\s{0,3}(`{3,}|~{3,})/.exec(lines[i]);
      if (fence) {
        end = i + 1;
        while (end < lines.length && !lines[end].trim().startsWith(fence[1])) end++;
        if (end < lines.length) end++;
      } else if (MARKEN_RE.test(lines[i])) {
        end = i + 1;
        while (end < lines.length && !/^\$\$[ \t]*$/.test(lines[end])) end++;
        if (end < lines.length) end++;
      } else if (/^:::[ \t]*[A-Za-z]/.test(lines[i]) && !/:::[ \t]*$/.test(lines[i].slice(3))) {
        end = i + 1;
        while (end < lines.length && !/^:::[ \t]*$/.test(lines[end])) end++;
        if (end < lines.length) end++;
      } else {
        end = i;
        while (end < lines.length && lines[end].trim()) end++;
        /* Der Editor schreibt zwei aufeinanderfolgende Absätze mit nur EINEM Zeilenumbruch
           dazwischen (ein Enter statt zwei). Ohne diese Unterscheidung zählte das hier als
           ein Block, im Editor stünden aber zwei – ab da wäre jede Zuordnung um eins
           verschoben, und Ausrichtung, Blockmenü und Ziehgriff träfen den falschen Block.
           Listen, Tabellen, Zitate und Überschriften bleiben zusammen; ein harter Umbruch
           (Rückstrich oder zwei Leerzeichen am Zeilenende) auch. */
        if (!MEHRZEILIG.test(lines[i])) {
          let z = i;
          // Nur ein harter Umbruch hält die nächste Zeile beim selben Absatz.
          while (z < end - 1 && /(\\|\s\s)$/.test(lines[z])) z++;
          end = z + 1;
        }
      }
      blocks.push({ start, end });
      i = end;
    }
    return { lines, blocks };
  };

  const entleere = (lines) => {
    const out = [];
    let inFence = null;
    for (const l of lines) {
      const f = /^\s{0,3}(`{3,}|~{3,})/.exec(l);
      if (f) { inFence = inFence && l.trim().startsWith(inFence) ? null : (inFence || f[1]); out.push(l); continue; }
      if (inFence) { out.push(l); continue; }
      if (!l.trim() && out.length && !out[out.length - 1].trim()) continue;
      out.push(l);
    }
    return out;
  };

  /* --- Ausrichtung ---------------------------------------------------------------------
     Der Bereich zwischen zwei Marken bekommt einen $$ausrichtung-Abschnitt. Die Stellen der
     Marken stehen schon fest (der Editor hat sie gesetzt und wieder entfernt); hier ist nur
     noch Text zu bewegen. Liefert { md } oder { fehler }. */
  function ausrichten(md, { markeZeile, endeZeile, amBlockanfang, mode }) {
    const ueber = "Die Auswahl reicht über einen Abschnitt hinaus. Bitte innerhalb eines "
                + "Abschnitts auswählen.";
    const { lines, blocks } = topLevelBlocks(md);
    const blockZu = (z) => blocks.findIndex((b) => z >= b.start && z < b.end);
    const idxVon = blockZu(markeZeile);
    let idxBis = endeZeile >= 0 ? blockZu(endeZeile) : idxVon;
    if (idxBis < 0) idxBis = idxVon;
    // Endet die Auswahl genau am Anfang des nächsten Absatzes, gehört der nicht mehr dazu.
    if (amBlockanfang && idxBis > idxVon) idxBis--;
    if (idxVon < 0 || idxBis < idxVon) return { fehler: "" };
    const art = (j) => (lines[blocks[j].start] || "").trim();
    // Umgebenden Ausrichtungsabschnitt suchen; jede andere Abschnittsmarke beendet die Suche.
    const umschliessend = (ab) => {
      let tiefe = 0;
      for (let j = ab; j >= 0; j--) {
        const a = art(j);
        if (a === "$$ende") tiefe++;
        else if (ABSCHNITT_AUF.has(a)) {
          if (!tiefe) return a === "$$ausrichtung" ? j : -1;
          tiefe--;
        }
      }
      return -1;
    };
    const aufVon = umschliessend(idxVon), aufBis = umschliessend(idxBis);
    // Anfang und Ende stecken in verschiedenen Abschnitten: Das ließe sich nur einfassen,
    // indem einer davon zerschnitten wird – dann lieber gar nichts.
    if (aufVon !== aufBis) return { fehler: ueber };
    const auf = aufVon;
    let zu = -1;
    if (auf >= 0) {
      let t = 1;
      for (let j = auf + 1; j < blocks.length; j++) {
        const a = art(j);
        if (ABSCHNITT_AUF.has(a)) t++;
        else if (a === "$$ende") { t--; if (!t) { zu = j; break; } }
      }
    }
    let out;
    if (auf >= 0 && zu >= 0) {
      const alt = (lines[blocks[auf].start + 1] || "").trim();
      out = alt === mode                                        // gleiche Richtung: Marken weg
        ? [...lines.slice(0, blocks[auf].start), ...lines.slice(blocks[auf].end, blocks[zu].start), ...lines.slice(blocks[zu].end)]
        : [...lines.slice(0, blocks[auf].start), "$$ausrichtung", mode, "$$", ...lines.slice(blocks[auf].end)];
    } else {
      // Der ausgewählte Bereich als Ganzes. Was darin schon einzeln ausgerichtet ist, verliert
      // seine Marken – sonst behielte ein Absatz mittendrin seine alte Richtung, obwohl er
      // mit ausgewählt war.
      let t = 0;
      const weg = new Set(), stapel = [];
      for (let j = idxVon; j <= idxBis; j++) {
        const a = art(j);
        if (ABSCHNITT_AUF.has(a)) { t++; stapel.push({ j, a }); }
        else if (a === "$$ende") {
          t--;
          if (t < 0) break;
          const offen = stapel.pop();
          if (offen && offen.a === "$$ausrichtung") {
            for (const k of [offen.j, j]) for (let z = blocks[k].start; z < blocks[k].end; z++) weg.add(z);
          }
        }
      }
      if (t !== 0) return { fehler: ueber };
      const mitte = [];
      for (let z = blocks[idxVon].start; z < blocks[idxBis].end; z++) if (!weg.has(z)) mitte.push(lines[z]);
      out = [...lines.slice(0, blocks[idxVon].start), "$$ausrichtung", mode, "$$", "",
             ...mitte, "", "$$ende", "$$", ...lines.slice(blocks[idxBis].end)];
    }
    return { md: entleere(out).join("\n") };
  }

  return { toEditorMd, fromEditorMd, repariert: () => markenRepariert, topLevelBlocks, entleere,
           MARKEN_RE, ausrichten,
           SNIPPETS, hinweisMd, akkordeonMd, bausteinMd, einbauMd, hinweisKopf, hinweisZeile,
           HINWEIS_NAME, ABSCHNITT_AUF };
})();
