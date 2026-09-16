/* Gemeinsamer Markdown-Renderer: Docmost-Callouts (mit Emoji), mehrspaltige Abschnitte, Videos, TOC.
   Wird vom internen Wiki, der Editor-Vorschau und dem öffentlichen Wiki benutzt. */
window.MD = (function () {
  const CALLOUTS = { info: "💡", warning: "⚠️", success: "✅", danger: "⛔", note: "📝", tip: "💡" };
  const VIDEO_RE = /\.(mp4|m4v|mov|webm)(\?.*)?$/i;
  const AUDIO_RE = /\.(mp3|m4a|ogg|oga|wav)(\?.*)?$/i;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* Pastelltöne, aus denen die Hintergrundfarbe eines Callouts gewählt werden kann.
     Gespeichert wird der Name, nicht der Farbwert – so bleibt das Markdown lesbar und es
     kann nichts Fremdes in die Seite geraten. */
  const CALLOUT_FARBEN = { rosa: "#fde8ee", pfirsich: "#fdeee0", sonne: "#fdf6d8", mint: "#e4f5ea",
                           himmel: "#e4f0fa", flieder: "#efe6f7", sand: "#f3ede3", stein: "#f0f0f0" };

  /* Kopfzeile eines Callouts: ":::info", ":::info 🧗", ":::warning ⚠️ farbe:mint" */
  function parseHead(kind, rest) {
    kind = kind.toLowerCase();
    if (!(kind in CALLOUTS)) return null;
    let farbe = "";
    const emoji = String(rest || "").trim().replace(/(?:^|\s)farbe:([a-zäöü]+)\b/i, (t, f) => {
      if (f.toLowerCase() in CALLOUT_FARBEN) { farbe = f.toLowerCase(); return ""; }
      return t;
    }).trim();
    return { kind, emoji: emoji || CALLOUTS[kind], farbe };
  }

  function calloutHtml(kind, emoji, inner, farbe) {
    const f = farbe && farbe in CALLOUT_FARBEN ? ` co-farbe-${farbe}` : "";
    return `<div class="callout callout-${kind}${f}"><span class="callout-emoji" aria-hidden="true">${esc(emoji)}</span><div class="callout-body">${inner}</div></div>`;
  }

  const ALIGNS = new Set(["left", "center", "right", "justify"]);
  // Blöcke ohne eigenen Inhalt – sie werden erst beim Anzeigen gefüllt.
  const MARKERS = ["toc", "unterseiten", "seitenumbruch"];

  /* Einen :::-Block am Anfang von src finden – mit Verschachtelung (Accordion in Callout, Callout in Accordion …).
     Liefert { name, args, inner, raw } oder null. */
  /* Zeilen, die in einem GESCHLOSSENEN Codeblock liegen. Ein nicht geschlossener Fence darf den
     Rest nicht verschlucken – sonst fände der Parser das schließende ":::" nicht mehr und der
     ganze Block fiele als Fließtext heraus. */
  function fenceMask(lines) {
    const mask = new Array(lines.length).fill(false);
    let open = -1;
    let marker = null;
    for (let i = 0; i < lines.length; i++) {
      const m = /^[ \t]{0,3}(`{3,}|~{3,})\s*$/.exec(lines[i]);
      const o = /^[ \t]{0,3}(`{3,}|~{3,})/.exec(lines[i]);
      if (open < 0) {
        if (o) { open = i; marker = o[1][0]; }
        continue;
      }
      // Geschlossen wird nur durch eine Zeile aus demselben Zeichen, mindestens gleich lang.
      if (m && m[1][0] === marker) {
        for (let k = open; k <= i; k++) mask[k] = true;
        open = -1;
        marker = null;
      }
    }
    return mask;                       // ein offen gebliebener Fence bleibt unmarkiert
  }

  /* Einen :::-Block am Anfang von src finden – mit Verschachtelung (Accordion in Callout usw.).
     Bis zu drei führende Leerzeichen sind erlaubt: Docmost-Exporte rücken Blöcke gern ein. */
  function splitFence(src) {
    const head = /^[ \t]{0,3}:::[ \t]*([A-Za-z]+)([^\n]*)\n/.exec(src);
    if (!head) return null;
    const lines = src.split("\n");
    const inCode = fenceMask(lines);
    let depth = 1;
    for (let i = 1; i < lines.length; i++) {
      if (inCode[i]) continue;                       // ":::" im Codebeispiel zählt nicht
      const l = lines[i].replace(/^[ \t]{0,3}/, "");
      if (/^:::[ \t]*[A-Za-z]/.test(l) && !/:::[ \t]*$/.test(l.slice(3))) depth++;
      else if (/^:::[ \t]*$/.test(l)) {
        depth--;
        if (depth === 0) {
          let rawLines = i + 1;
          while (rawLines < lines.length && lines[rawLines].trim() === "") rawLines++;
          const raw = lines.slice(0, rawLines).join("\n") + (rawLines < lines.length ? "\n" : "");
          /* Abgezogen wird der GEMEINSAME Einzug aller nicht leeren Zeilen, höchstens drei
             Zeichen – nicht je Zeile bis zu drei. Sonst verlöre der eingerückte Unterpunkt
             einer Aufzählung seinen Einzug und stünde in der Leseansicht eine Ebene zu hoch,
             während der Editor ihn richtig eingerückt zeigt. */
          const rumpf = lines.slice(1, i);
          const vorn = (x) => /^[ \t]*/.exec(x)[0].length;
          const einzug = rumpf.reduce((n, x) => (x.trim() ? Math.min(n, vorn(x)) : n), 3);
          const inner = rumpf.map((x) => x.slice(Math.min(einzug, vorn(x)))).join("\n");
          return { name: head[1].toLowerCase(), args: (head[2] || "").trim(), inner, raw };
        }
      }
    }
    return null;
  }

  /* Spalten am "|||" trennen – aber weder an einem "|||" im Codeblock noch an einem, das zu
     einem verschachtelten Abschnitt gehört. Der Editor trennt genauso (teileSpalten in
     wiki.js); ohne die Tiefenzählung zerfiele "Spalten in Spalten" in beiden Ansichten
     unterschiedlich. */
  function splitColumns(inner) {
    const lines = inner.split("\n");
    const inCode = fenceMask(lines);
    const cols = [];
    let cur = [];
    let tiefe = 0;
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (!inCode[i]) {
        if (/^:::[ \t]*[A-Za-z]/.test(l) && !/:::[ \t]*$/.test(l.slice(3))) tiefe++;
        else if (/^:::[ \t]*$/.test(l)) { if (tiefe) tiefe--; }
        else if (!tiefe && /^[ \t]*\|\|\|[ \t]*$/.test(l)) { cols.push(cur.join("\n")); cur = []; continue; }
      }
      cur.push(l);
    }
    cols.push(cur.join("\n"));
    return cols;
  }

  const calloutBlock = {
    name: "calloutBlock",
    level: "block",
    start(src) { const m = src.match(/(?:^|\n)[ \t]{0,3}:::/); return m ? m.index + (m[0].startsWith("\n") ? 1 : 0) : undefined; },
    tokenizer(src) {
      const f = splitFence(src);
      if (f) {
        if (f.name === "columns") {
          const cols = splitColumns(f.inner).map((c) => this.lexer.blockTokens(c + "\n", []));
          return { type: "columnsBlock", raw: f.raw, cols };
        }
        if (f.name === "accordion") {
          return { type: "accordionBlock", raw: f.raw, title: f.args || "Details", tokens: this.lexer.blockTokens(f.inner + "\n", []) };
        }
        if (MARKERS.includes(f.name)) {
          return { type: "markerBlock", raw: f.raw, marker: f.name };
        }
        /* Synchronisierte Abschnitte: ":::baustein <kennung>" hält den Inhalt an EINER Stelle,
           ":::einbau <seite>#<kennung>" zeigt ihn anderswo. Der Einbau bleibt hier ein leerer
           Platzhalter – gefüllt wird er in enhance(), wo die Seite nachgeladen werden kann.
           Das hat einen Grund: Über die gewöhnliche Schnittstelle gelten die Leserechte der
           Quellseite von allein. Setzte der Server den Inhalt ein, müsste er dieselbe Prüfung
           ein zweites Mal nachbauen – und genau dort ist sie schon einmal durchgerutscht. */
        if (f.name === "baustein") {
          return { type: "bausteinBlock", raw: f.raw, kennung: f.args.trim(),
                   tokens: this.lexer.blockTokens(f.inner + "\n", []) };
        }
        if (f.name === "einbau") {
          return { type: "einbauBlock", raw: f.raw, ziel: f.args.trim() };
        }
        if (f.name === "align") {
          const mode = ALIGNS.has(f.args.toLowerCase()) ? f.args.toLowerCase() : "center";
          return { type: "alignBlock", raw: f.raw, mode, tokens: this.lexer.blockTokens(f.inner + "\n", []) };
        }
        const head = parseHead(f.name, f.args);
        if (head) return { type: "calloutBlock", raw: f.raw, ...head, tokens: this.lexer.blockTokens(f.inner + "\n", []) };
      }
      const m = /^:::[ \t]*(\w+)[ \t]+(.*?)[ \t]*:::[ \t]*(?:\n+|$)/.exec(src);
      if (m) {
        const head = parseHead(m[1], "");
        if (head) return { type: "calloutBlock", raw: m[0], ...head, inline: true, tokens: this.lexer.inlineTokens(m[2]) };
      }
    },
    renderer(token) {
      if (token.type === "accordionBlock") {
        return `<details class="accordion"><summary>${esc(token.title)}</summary><div class="accordion-body">${this.parser.parse(token.tokens)}</div></details>`;
      }
      if (token.type === "markerBlock") {
        // Platzhalter – gefüllt wird er nach dem Rendern (enhance), wo der Seitenbaum bekannt ist.
        if (token.marker === "seitenumbruch") return '<div class="page-break" aria-hidden="true"></div>';
        return `<div class="md-marker" data-marker="${token.marker}"></div>`;
      }
      if (token.type === "bausteinBlock") {
        return `<section class="baustein" data-baustein="${esc(token.kennung)}">${this.parser.parse(token.tokens)}</section>`;
      }
      if (token.type === "einbauBlock") {
        return `<div class="einbau" data-ziel="${esc(token.ziel)}"></div>`;
      }
      if (token.type === "alignBlock") {
        return `<div class="align-${token.mode}">${this.parser.parse(token.tokens)}</div>`;
      }
      if (token.type === "columnsBlock") {
        return `<div class="columns cols-${token.cols.length}">${token.cols.map((c) => `<div class="col">${this.parser.parse(c)}</div>`).join("")}</div>`;
      }
      const inner = token.inline ? this.parser.parseInline(token.tokens) : this.parser.parse(token.tokens);
      return calloutHtml(token.kind, token.emoji, inner, token.farbe);
    },
  };
  const columnsRenderer = { name: "columnsBlock", level: "block", renderer: calloutBlock.renderer };
  const accordionRenderer = { name: "accordionBlock", level: "block", renderer: calloutBlock.renderer };
  const alignRenderer = { name: "alignBlock", level: "block", renderer: calloutBlock.renderer };
  const markerRenderer = { name: "markerBlock", level: "block", renderer: calloutBlock.renderer };
  const bausteinRenderer = { name: "bausteinBlock", level: "block", renderer: calloutBlock.renderer };
  const einbauRenderer = { name: "einbauBlock", level: "block", renderer: calloutBlock.renderer };

  /* Einzeilige Callouts in Tabellenzellen (:::warning <details>…</details> :::) */
  const calloutInline = {
    name: "calloutInline",
    level: "inline",
    start(src) { const i = src.indexOf(":::"); return i < 0 ? undefined : i; },
    tokenizer(src) {
      const m = /^:::[ \t]*(\w+)[ \t]+([\s\S]*?)[ \t]*:::/.exec(src);
      if (m) {
        const head = parseHead(m[1], "");
        if (head) return { type: "calloutInline", raw: m[0], ...head, tokens: this.lexer.inlineTokens(m[2]) };
      }
    },
    renderer(token) { return calloutHtml(token.kind, token.emoji, this.parser.parseInline(token.tokens), token.farbe); },
  };

  /* Bildbreite steckt als Fragment in der Adresse: ![Alt](bild.jpg#w=60%)
     Der WYSIWYG-Editor schreibt Adressen beim Speichern prozentkodiert zurück ("%" wird "%25").
     Beide Schreibweisen werden gelesen, sonst ginge die Breite beim ersten Speichern verloren. */
  function imageWidth(href) {
    const m = /#w=(\d{1,4})(px|%25|%)?$/.exec(href || "");
    if (!m) return "";
    return m[2] === "%" || m[2] === "%25" ? m[1] + "%" : m[1];
  }

  /* --- Auszeichnungen, die Markdown selbst nicht kennt -----------------------------------
     Unterstreichen, Hervorheben, Hoch- und Tiefstellen gibt es in Docmost, in Markdown aber
     nicht. Gespeichert wird deshalb eine reine Textschreibweise:

         ++unterstrichen++   ==hervorgehoben==   10^3^   H~2~O

     Rohes HTML (<u>, <mark>, <sub>, <sup>) wäre die naheliegende Alternative, überlebt aber
     den WYSIWYG-Editor nicht: er kennt diese Auszeichnungen nicht und wirft sie beim Speichern
     ersatzlos weg. Die Textschreibweise reicht er dagegen unverändert durch (siehe wiki.js,
     widgetRules). Bestehende Seiten mit rohem HTML werden beim Öffnen des Editors einmalig
     umgeschrieben – gerendert wird beides. */
  // Der Inhalt darf keine weitere Auszeichnung enthalten: Toast UI baut daraus ein Widget und
  // schneidet beim ersten verschachtelten Element still ab – aus "==A **b** C==" würde "==A **b**",
  // der Rest wäre beim Speichern verloren. Deshalb sind * _ ` [ ] und die Trennzeichen selbst
  // im Inhalt ausgeschlossen; er darf zudem weder mit Leerzeichen beginnen noch enden.
  const MARKS = [
    { tag: "u",    delim: "++", name: "markUnderline",
      re:     /^\+\+([^\s=+~^*_`[\]\n](?:[^=+~^*_`[\]\n]*[^\s=+~^*_`[\]\n])?)\+\+/,
      widget:  /\+\+([^\s=+~^*_`[\]\n](?:[^=+~^*_`[\]\n]*[^\s=+~^*_`[\]\n])?)\+\+/ },
    { tag: "mark", delim: "==", name: "markHighlight",
      re:     /^==([^\s=+~^*_`[\]\n](?:[^=+~^*_`[\]\n]*[^\s=+~^*_`[\]\n])?)==/,
      widget:  /==([^\s=+~^*_`[\]\n](?:[^=+~^*_`[\]\n]*[^\s=+~^*_`[\]\n])?)==/ },
    { tag: "sup",  delim: "^",  name: "markSup",
      re:     /^\^([^\s=+~^*_`[\]\n]+)\^/,
      widget:  /\^([^\s=+~^*_`[\]\n]+)\^/ },
    // Tiefstellen nutzt eine einzelne Tilde – die doppelte gehört zu ~~durchgestrichen~~.
    { tag: "sub",  delim: "~",  name: "markSub",
      re:     /^~(?!~)([^\s=+~^*_`[\]\n]+)~(?!~)/,
      widget: /(?<!~)~([^\s=+~^*_`[\]\n]+)~(?!~)/ },
  ];

  /* Textfarbe im Fließtext: {{rot:Text}}. Bewusst nur die Farben aus dem Handbuch CD –
     freie Farbwahl widerspricht dem Gestaltungsraster. */
  // Welcher Name welchen Farbwert bekommt, steht im Stylesheet (.tc-rot …); hier zählt nur die Auswahl.
  const COLOR_NAMES = ["rot", "blau", "gruen", "grau", "gelb"];
  const colorMark = {
    name: "colorMark",
    level: "inline",
    start(src) { const i = src.indexOf("{{"); return i < 0 ? undefined : i; },
    tokenizer(src) {
      const m = /^\{\{(rot|blau|gruen|grau|gelb):([^}\n]{1,200})\}\}/.exec(src);
      if (m) return { type: "colorMark", raw: m[0], color: m[1], tokens: this.lexer.inlineTokens(m[2]) };
    },
    renderer(token) {
      return `<span class="tc tc-${token.color}">${this.parser.parseInline(token.tokens)}</span>`;
    },
  };

  /* Statusmarke im Fließtext: {status:offen} */
  const STATUS_COLORS = { offen: "warn", "in pruefung": "warn", "in prüfung": "warn", geprueft: "ok",
                          "geprüft": "ok", freigegeben: "ok", entwurf: "grau", veraltet: "danger" };
  const statusMark = {
    name: "statusMark",
    level: "inline",
    start(src) { const i = src.indexOf("{status:"); return i < 0 ? undefined : i; },
    tokenizer(src) {
      const m = /^\{status:([^}\n]{1,40})\}/.exec(src);
      if (m) return { type: "statusMark", raw: m[0], label: m[1].trim() };
    },
    renderer(token) {
      const cls = STATUS_COLORS[token.label.toLowerCase()] || "grau";
      return `<span class="status-badge status-${cls}">${esc(token.label)}</span>`;
    },
  };

  const markExtensions = MARKS.map((m) => ({
    name: m.name,
    level: "inline",
    start(src) { const i = src.indexOf(m.delim); return i < 0 ? undefined : i; },
    tokenizer(src) {
      const hit = m.re.exec(src);
      if (hit) return { type: m.name, raw: hit[0], tokens: this.lexer.inlineTokens(hit[1]) };
    },
    renderer(token) { return `<${m.tag}>${this.parser.parseInline(token.tokens)}</${m.tag}>`; },
  }));

  /* Zeichen, das im Editorformat für einen harten Zeilenumbruch steht (U+2424, „SYMBOL FOR
     NEWLINE"). Der Editor kennt keinen Umbruchknoten – ohne diesen Umweg verschwände ein mit
     zwei Leerzeichen gesetzter Umbruch beim Öffnen, und die Wörter davor und danach klebten
     aneinander. Im gespeicherten Markdown steht das Zeichen nie. */
  const UMBRUCH = "\u2424";

  /* Regeln für den WYSIWYG-Editor: gleiche Schreibweise, nur ohne Zeilenanker. */
  function widgetRules() {
    const extra = [
      { rule: /\u2424/, toDOM() { return document.createElement("br"); } },
      { rule: /\{\{(rot|blau|gruen|grau|gelb):([^}\n]{1,200})\}\}/,
        toDOM(text) {
          const m = /\{\{(rot|blau|gruen|grau|gelb):([^}\n]{1,200})\}\}/.exec(text);
          const el = document.createElement("span");
          el.className = "tc tc-" + (m ? m[1] : "grau");
          el.textContent = m ? m[2] : text;
          return el;
        } },
      { rule: /\{status:[^}\n]{1,40}\}/,
        toDOM(text) {
          const m = /\{status:([^}\n]{1,40})\}/.exec(text);
          const label = m ? m[1].trim() : text;
          const el = document.createElement("span");
          el.className = "status-badge status-" + (STATUS_COLORS[label.toLowerCase()] || "grau");
          el.textContent = label;
          return el;
        } },
    ];
    return extra.concat(MARKS.map((m) => ({
      rule: m.widget,
      toDOM(text) {
        const hit = m.widget.exec(text);
        const el = document.createElement(m.tag);
        el.textContent = hit ? hit[1] : text;
        return el;
      },
    })));
  }


  const MARK_BY_TAG = { u: "++", mark: "==", sup: "^", sub: "~" };

  /* <u>…</u> und Verwandte (etwa aus einem Docmost-Import) in die Textschreibweise bringen.
     Nur einfache Inhalte werden angefasst; alles Verschachtelte bleibt unverändert stehen. */
  function htmlMarksToSyntax(md) {
    return String(md || "").replace(/<(u|mark|sub|sup)>([\s\S]*?)<\/\1>/gi, (all, tag, inner) => {
      const t = tag.toLowerCase(), d = MARK_BY_TAG[t];
      if (!inner || /[<>\n]/.test(inner) || inner.includes(d)) return all;
      const text = inner.trim();
      if (!text) return all;
      if ((t === "sub" || t === "sup") && /\s/.test(text)) return all;  // dort sind Leerzeichen nicht darstellbar
      return d + text + d;
    });
  }

  /* Auswahl im Editor auszeichnen: liefert die Zeichenfolge oder "" bei unpassendem Text. */
  function wrapMark(tag, text) {
    const d = MARK_BY_TAG[tag];
    const t = String(text || "").trim();
    if (!d || !t || t.includes(d)) return "";
    if ((tag === "sub" || tag === "sup") && /\s/.test(t)) return "";
    return d + t + d;
  }

  /* Anhänge (PDF, Word, Tabellen, ZIP, GPX …) werden als beschriftete Schaltfläche gezeigt. */
  const FILE_RE = /\.(pdf|docx?|odt|rtf|xlsx?|ods|csv|pptx?|odp|txt|zip|gpx|kmz?)$/i;
  const FILE_ICON = {
    pdf: "📕", doc: "📘", docx: "📘", odt: "📘", rtf: "📘",
    xls: "📗", xlsx: "📗", ods: "📗", csv: "📗",
    ppt: "📙", pptx: "📙", odp: "📙",
    txt: "📄", zip: "🗜️", gpx: "🗺️", kml: "🗺️", kmz: "🗺️",
  };

  const renderer = {
    link(href, title, text) {
      const tok = typeof href === "object" ? href : null;
      const url = tok ? tok.href : href;
      const label = tok ? tok.text : text;
      const m = FILE_RE.exec(String(url || "").split("?")[0]);
      // Nur hochgeladene Anhänge bekommen die Schaltfläche, alles andere bleibt ein normaler Link.
      if (!m || !/^\/media\/wiki\//.test(url)) return false;
      const icon = FILE_ICON[m[1].toLowerCase()] || "📄";
      return `<a class="attachment" href="${esc(url)}" target="_blank" rel="noopener">`
        + `<span class="att-icon" aria-hidden="true">${icon}</span>`
        + `<span class="att-name">${esc(label || url)}</span>`
        + `<span class="att-ext">${esc(m[1].toUpperCase())}</span></a>`;
    },
    image(href, title, text) {
      if (typeof href === "object") { const t = href; href = t.href; title = t.title; text = t.text; }
      if (VIDEO_RE.test(href || "")) {
        return `<video controls preload="metadata" src="${esc(href)}"${title ? ` title="${esc(title)}"` : ""}></video>`;
      }
      if (AUDIO_RE.test(href || "")) {
        return `<audio controls preload="metadata" src="${esc(href)}"${title ? ` title="${esc(title)}"` : ""}></audio>`;
      }
      const w = imageWidth(href);
      const img = `<img src="${esc(href)}" alt="${esc(text || "")}"${w ? ` width="${esc(w)}"` : ""} loading="lazy">`;
      // Der Titel eines Bildes ist die Bildunterschrift: ![Alt](bild.jpg "Unterschrift")
      return title ? `<figure>${img}<figcaption>${esc(title)}</figcaption></figure>` : img;
    },
  };

  marked.use({ gfm: true, breaks: false, renderer,
    extensions: [calloutBlock, columnsRenderer, accordionRenderer, alignRenderer, markerRenderer,
                 bausteinRenderer, einbauRenderer, calloutInline,
                 statusMark, colorMark, ...markExtensions] });

  /* Eine Zeile, die nur aus "<br>" besteht, ist eine gesetzte Leerzeile. Markdown liest daraus
     einen HTML-Block – und der zieht den unmittelbar folgenden Absatz mit hinein, der damit
     spurlos verschwindet. Ältere Seiten tragen diese Schreibweise noch (der Editor schreibt
     inzwischen "&nbsp;"), deshalb wird sie hier beim Anzeigen begradigt: ein eigener Absatz,
     mit Leerzeilen ringsum. Im Codeblock bleibt jede Zeile, wie sie ist. */
  /* Zellen einer Markdown-Tabellenzeile – ein escaptes "\\|" trennt nicht. */
  function zellen(zeile) {
    return zeile.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/);
  }
  /* Eine Kopfzeile mit verbundenen Zellen hat weniger Zellen als die Trennzeile darunter
     ("| A | @cols=2:B |" über "| --- | --- | --- |"). GFM verlangt dieselbe Anzahl, sonst ist
     es gar keine Tabelle – marked ließe die Zeilen als Text stehen. Die fehlenden Zellen
     werden deshalb vor dem Rendern ergänzt; in der Anzeige verschwinden sie wieder
     (siehe verbundeneZellen). */
  function tabellenkoepfeFuellen(md) {
    if (md.indexOf("@cols=") < 0 && md.indexOf("@rows=") < 0) return md;
    const zeilen = md.split("\n");
    const maske = fenceMask(zeilen);
    for (let i = 1; i < zeilen.length; i++) {
      if (maske[i] || !/^[ \t]*\|[\s:|-]*\|[ \t]*$/.test(zeilen[i])) continue;   // Trennzeile?
      if (!/-/.test(zeilen[i])) continue;
      const soll = zellen(zeilen[i]).length;
      const kopf = zeilen[i - 1];
      if (!/^[ \t]*\|/.test(kopf)) continue;
      const ist = zellen(kopf).length;
      if (ist >= soll) continue;
      zeilen[i - 1] = kopf.trimEnd().replace(/\|[ \t]*$/, "|") + " |".repeat(soll - ist);
    }
    return zeilen.join("\n");
  }

  function leerzeilenBegradigen(md) {
    const zeilen = String(md).split("\n");
    if (!zeilen.some((z) => /^[ \t]*<br\s*\/?>[ \t]*$/i.test(z))) return md;
    const maske = fenceMask(zeilen);
    const raus = [];
    zeilen.forEach((z, i) => {
      if (!maske[i] && /^[ \t]*<br\s*\/?>[ \t]*$/i.test(z)) {
        if (raus.length && raus[raus.length - 1].trim()) raus.push("");
        raus.push("&nbsp;", "");
        return;
      }
      if (!maske[i] && !z.trim() && raus.length && !raus[raus.length - 1].trim()) return;
      raus.push(z);
    });
    return raus.join("\n");
  }

  /* Was DOMPurify zusätzlich durchlässt und was ausdrücklich nicht. Ein Artikel darf Filme
     zeigen, aber weder Formulare noch Stilblöcke mitbringen: Ein <style> im Text stellte die
     Oberfläche aller Leser um, ein <form> täuschte Eingaben vor. Und ids, die der Rahmen
     selbst benutzt (dlg, toast, article …), dürfen im Inhalt nicht vorkommen – sonst fände
     getElementById das Element im Artikel statt das des Rahmens (DOM-Clobbering). */
  const REINIGUNG = { ADD_TAGS: ["video", "audio", "source"],
                      ADD_ATTR: ["target", "controls", "preload", "playsinline"],
                      FORBID_TAGS: ["style", "form", "textarea", "select", "button", "dialog", "iframe"] };
  const RAHMEN_ID = /^(dlg|toast|toc|comments|article|tree|map|banner|favorites|editor|side|fab|wiki-|pg-|ed-|lb-|al-|up-|au-|sh-|ic-|lk-|be-|ce-|dr-|loc-|imp-|p-|h-|btn-|comment-|search-|seiten-)/;
  /* Aufgabenlisten („* [ ] offen“) brauchen ein <input type=checkbox> – das ist der einzige
     Grund, aus dem hier überhaupt ein Eingabefeld stehen darf. Alles andere fliegt raus, und
     auch die Kästchen bleiben abgeschaltet: Ein Artikel soll nichts entgegennehmen. */
  DOMPurify.addHook("uponSanitizeElement", (node, data) => {
    if (data.tagName !== "input") return;
    if ((node.getAttribute("type") || "").toLowerCase() !== "checkbox") { node.remove(); return; }
    for (const a of [...node.attributes]) {
      if (!["type", "checked", "disabled", "class"].includes(a.name)) node.removeAttribute(a.name);
    }
    node.setAttribute("disabled", "");
  });
  DOMPurify.addHook("uponSanitizeAttribute", (node, data) => {
    if (data.attrName === "id" && (!/^[A-Za-z][\w-]*$/.test(data.attrValue) || RAHMEN_ID.test(data.attrValue))) {
      data.keepAttr = false;
    }
  });

  function render(md) {
    let html;
    try { html = marked.parse(tabellenkoepfeFuellen(leerzeilenBegradigen(md || ""))); } catch (e) { html = `<p class="error">Markdown konnte nicht gerendert werden: ${esc(e.message)}</p>`; }
    return DOMPurify.sanitize(html, REINIGUNG);
  }

  /* Überschriften mit IDs versehen und Gliederung liefern */
  function buildToc(root) {
    const used = new Set();
    const items = [];
    root.querySelectorAll("h1, h2, h3, h4, h5").forEach((h) => {
      // Die id wird immer aus dem Text gebildet – eine mitgebrachte (rohes HTML, Import) käme
      // ungeprüft in ein href und war so ein Weg am Sanitizer vorbei in die Leiste.
      let id = h.textContent.trim().toLowerCase().replace(/[äöüß]/g, (c) => ({ ä: "ae", ö: "oe", ü: "ue", ß: "ss" }[c]))
        .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "abschnitt";
      let n = 2, base = id;
      // Zweimal derselbe Abschnittsname – und: Eine Überschrift „Toc“ oder „Tree“ ergäbe eine
      // Kennung, die es im Rahmen schon gibt (die Leiste, der Seitenbaum). getElementById
      // fände dann das Falsche.
      const fremd = (x) => { const el = document.getElementById(x); return !!el && !root.contains(el); };
      while (used.has(id) || fremd(id)) id = `${base}-${n++}`;
      used.add(id);
      h.id = id;
      items.push({ id, level: +h.tagName[1], text: h.textContent.trim() });
    });
    return items;
  }

  /* Nachbearbeitung des gerenderten Artikels – für internes und öffentliches Wiki gleich:
     breite Tabellen bekommen einen eigenen Scrollbereich (sonst schieben sie die Spalte auf),
     Codeblöcke einen Kopierknopf, Überschriften einen anklickbaren Anker. */
  /* Einen eingebundenen Abschnitt einsetzen. Die Quellseite kommt über o.holeSeite – eine
     Funktion, die der Aufrufer mitbringt (Wiki: die angemeldete Schnittstelle, öffentlicher
     Bereich: die öffentliche). Damit gelten die Leserechte der Quellseite von allein, und der
     Unterschied zwischen "gibt es nicht" und "darfst du nicht lesen" bleibt ungesagt: Sonst
     ließe sich über einen Einbau abfragen, welche Seiten es gibt. */
  const EINBAU_TIEFE = 3;                 // Baustein im Baustein – irgendwo ist Schluss

  function einbauFuellen(wurzel, o, tiefe, speicher) {
    wurzel.querySelectorAll(".einbau[data-ziel]").forEach((el) => {
      if (el.dataset.gefuellt) return;
      el.dataset.gefuellt = "1";
      const teil = String(el.getAttribute("data-ziel") || "").split("#");
      const slug = (teil[0] || "").trim();
      const kennung = (teil[1] || "").trim();
      const sage = (text) => { el.innerHTML = `<div class="einbau-fehlt">${esc(text)}</div>`; };
      if (!slug || !kennung) return sage("Eingebundener Abschnitt ohne Ziel – erwartet wird „seite#abschnitt“.");
      if (tiefe >= EINBAU_TIEFE) return sage("Zu viele ineinander eingebundene Abschnitte.");
      if (typeof o.holeSeite !== "function") return sage(`Eingebundener Abschnitt „${kennung}“ aus „${slug}“.`);
      if (!speicher.has(slug)) speicher.set(slug, Promise.resolve(o.holeSeite(slug)).catch(() => null));
      speicher.get(slug).then((seite) => {
        if (!seite) return sage(`Der eingebundene Abschnitt ist nicht verfügbar: „${slug}“ gibt es nicht oder du darfst die Seite nicht lesen.`);
        const huelle = document.createElement("div");
        huelle.innerHTML = render(seite.content);
        const quelle = [...huelle.querySelectorAll(".baustein")]
          .find((b) => b.getAttribute("data-baustein") === kennung);
        if (!quelle) return sage(`Den Abschnitt „${kennung}“ gibt es auf „${seite.title}“ nicht (mehr).`);
        el.innerHTML = "";
        const inhalt = document.createElement("div");
        inhalt.className = "einbau-inhalt";
        while (quelle.firstChild) inhalt.appendChild(quelle.firstChild);
        el.appendChild(inhalt);
        const fuss = document.createElement("div");
        fuss.className = "einbau-fuss";
        const a = document.createElement("a");
        a.href = (o.prefix || "/wiki/") + seite.slug;
        a.textContent = seite.title;
        fuss.append(document.createTextNode("Aus "), a);
        el.appendChild(fuss);
        einbauFuellen(inhalt, o, tiefe + 1, speicher);   // Baustein im Baustein
      });
    });
  }

  function enhance(root, opts) {
    const o = opts || {};
    einbauFuellen(root, o, 0, new Map());

    // Platzhalter aus :::toc und :::unterseiten füllen
    root.querySelectorAll(".md-marker[data-marker=toc]").forEach((el) => {
      const items = buildToc(root);
      el.innerHTML = items.length
        ? `<div class="inline-toc"><strong>Inhalt</strong>${tocHtml(items)}</div>`
        : '<div class="inline-toc muted small">Noch keine Überschriften.</div>';
    });
    root.querySelectorAll(".md-marker[data-marker=unterseiten]").forEach((el) => {
      const kids = o.children || [];
      el.innerHTML = kids.length
        ? `<div class="children-list"><strong>Unterseiten</strong><ul>${kids.map((k) =>
            `<li><a href="${esc(o.prefix || "/wiki/")}${esc(k.slug)}">${k.icon ? esc(k.icon) + " " : ""}${esc(k.title)}</a></li>`).join("")}</ul></div>`
        : '<div class="muted small">Diese Seite hat keine Unterseiten.</div>';
    });

    // Bildunterschrift: ein kursiver Absatz direkt unter dem Bild wird zur Beschriftung.
    // Diese Schreibweise überlebt den WYSIWYG-Editor, ein Bildtitel ("…") dagegen nicht.
    root.querySelectorAll("p > img:only-child").forEach((img) => {
      const para = img.parentElement;
      const next = para.nextElementSibling;
      if (!next || next.tagName !== "P") return;
      const em = next.firstElementChild;
      if (!em || em.tagName !== "EM" || next.childNodes.length !== 1) return;
      const fig = document.createElement("figure");
      const cap = document.createElement("figcaption");
      cap.textContent = em.textContent;
      para.replaceWith(fig);
      fig.appendChild(img);
      fig.appendChild(cap);
      next.remove();
    });

    // Bilder und Videos im Vollbild ansehen
    root.querySelectorAll("img").forEach((img) => {
      if (img.closest("a")) return;                     // verlinkte Bilder behalten ihren Link
      img.classList.add("zoomable");
      img.addEventListener("click", () => openLightbox(img.getAttribute("src"), img.getAttribute("alt")));
    });

    /* Zusammengefasste Zellen: Der Editor schreibt sie als Vorsatz in die Zelle
       ("@cols=2:Text", "@rows=2:Text"). marked kennt nur gewöhnliche Tabellen und lässt den
       Vorsatz als Text stehen – hier wird daraus das, was er meint. */
    root.querySelectorAll("td, th").forEach((zelle) => {
      let vorsatz = zelle.textContent;
      if (vorsatz.indexOf("@cols=") !== 0 && vorsatz.indexOf("@rows=") !== 0) return;
      let spalten = 1, zeilen = 1, m;
      while ((m = /^@(cols|rows)=(\d{1,3}):/.exec(vorsatz))) {
        if (m[1] === "cols") spalten = Math.min(30, parseInt(m[2], 10) || 1);
        else zeilen = Math.min(100, parseInt(m[2], 10) || 1);
        vorsatz = vorsatz.slice(m[0].length);
        // Aus dem ersten Textknoten nehmen, damit Auszeichnungen in der Zelle bleiben.
        const tw = document.createTreeWalker(zelle, NodeFilter.SHOW_TEXT);
        const tn = tw.nextNode();
        if (tn) tn.nodeValue = tn.nodeValue.slice(m[0].length);
      }
      if (spalten > 1) zelle.colSpan = spalten;
      if (zeilen > 1) zelle.rowSpan = zeilen;
    });

    /* Und die Zellen wieder weg, die nur dastehen, weil GFM jede Zeile gleich lang haben will:
       Was eine verbundene Zelle überdeckt, steht im Markdown gar nicht – marked füllt es auf.
       Gezählt wird wie im Browser: Jede Zelle rückt auf die nächste freie Spalte. */
    root.querySelectorAll("table").forEach((t) => {
      if (!t.querySelector("[colspan], [rowspan]")) return;
      // Spaltenzahl aus der längsten Zeile: Die Kopfzeile trägt die aufgefüllten Zellen
      // (siehe tabellenkoepfeFuellen) und wäre mit ihren Spannen zu breit gerechnet.
      const breite = [...t.rows].reduce((n, r) => Math.max(n, r.cells.length), 0);
      if (!breite) return;
      const belegt = [];
      [...t.rows].forEach((zeile, z) => {
        let spalte = 0;
        [...zeile.cells].forEach((c) => {
          while (belegt[z] && belegt[z][spalte]) spalte += 1;
          if (spalte >= breite) {
            if (!c.textContent.trim()) c.remove();          // Füllzelle
            return;
          }
          const ds = c.colSpan || 1, dz = c.rowSpan || 1;
          for (let i = 0; i < dz; i += 1) {
            belegt[z + i] = belegt[z + i] || [];
            for (let j = 0; j < ds; j += 1) belegt[z + i][spalte + j] = true;
          }
          spalte += ds;
        });
      });
    });

    root.querySelectorAll("table").forEach((t) => {
      if (t.parentElement && t.parentElement.classList.contains("table-scroll")) return;
      const box = document.createElement("div");
      box.className = "table-scroll";
      t.replaceWith(box);
      box.appendChild(t);
    });

    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement && pre.parentElement.classList.contains("code-block")) return;
      const box = document.createElement("div");
      box.className = "code-block";
      pre.replaceWith(box);
      box.appendChild(pre);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "code-copy";
      btn.textContent = "Kopieren";
      btn.title = "Code in die Zwischenablage kopieren";
      btn.addEventListener("click", async () => {
        const code = pre.querySelector("code") || pre;
        try {
          await navigator.clipboard.writeText(code.textContent.replace(/\n$/, ""));
          btn.textContent = "Kopiert";
        } catch (e) {
          btn.textContent = "Nicht möglich";
        }
        setTimeout(() => { btn.textContent = "Kopieren"; }, 1800);
      });
      box.appendChild(btn);
    });

    // Tabellen nach Spalte sortieren – rein in der Ansicht, der Inhalt bleibt unverändert.
    root.querySelectorAll("table").forEach((t) => {
      const head = t.tHead && t.tHead.rows[0];
      const body = t.tBodies[0];
      if (!head || !body || body.rows.length < 2) return;
      // Sind Zellen zusammengefasst, gehört eine Spalte nicht mehr zu genau einer Zelle je
      // Zeile – sortieren würde die Tabelle auseinanderreißen.
      if (t.querySelector("[colspan], [rowspan]")) return;
      Array.from(head.cells).forEach((th, col) => {
        if (th.querySelector(".th-sort")) return;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "th-sort";
        btn.title = "Nach dieser Spalte sortieren";
        btn.textContent = "⇅";
        let dir = 0;
        btn.addEventListener("click", () => {
          dir = dir === 1 ? -1 : 1;
          head.querySelectorAll(".th-sort").forEach((x) => { if (x !== btn) x.textContent = "⇅"; });
          btn.textContent = dir === 1 ? "↑" : "↓";
          const rows = Array.from(body.rows);
          const val = (r) => (r.cells[col] ? r.cells[col].textContent.trim() : "");
          const num = (v) => { const n = parseFloat(v.replace(/\./g, "").replace(",", ".")); return isNaN(n) ? null : n; };
          rows.sort((a, b) => {
            const x = val(a), y = val(b);
            const nx = num(x), ny = num(y);
            if (nx !== null && ny !== null) return (nx - ny) * dir;
            return x.localeCompare(y, "de") * dir;
          });
          rows.forEach((r) => body.appendChild(r));
        });
        th.appendChild(btn);
      });
    });

    root.querySelectorAll("h1[id], h2[id], h3[id], h4[id], h5[id]").forEach((h) => {
      if (h.querySelector(".h-anchor")) return;
      const a = document.createElement("a");
      a.className = "h-anchor";
      a.href = "#" + h.id;
      a.textContent = "#";
      a.setAttribute("aria-label", `Link zum Abschnitt „${h.textContent.trim()}“`);
      // Der Titel erklärt beim Darüberfahren, wozu das Zeichen da ist – sonst liest es sich
      // wie ein Steuerzeichen im Text.
      a.title = "Link zu diesem Abschnitt";
      h.appendChild(a);
    });
  }

  /* Bild im Vollbild – ein einziges Overlay für alle Seiten. */
  function openLightbox(src, alt) {
    if (!src) return;
    const box = document.createElement("div");
    box.className = "md-lightbox";
    box.innerHTML = `<button type="button" class="md-lightbox-close" aria-label="Schließen">×</button>`;
    const img = document.createElement("img");
    img.src = src.replace(/#w=[^#]*$/, "");
    img.alt = alt || "";
    box.appendChild(img);
    const close = () => { box.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    box.addEventListener("click", (e) => { if (e.target !== img) close(); });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(box);
  }

  /* Aktiven Abschnitt im Inhaltsverzeichnis mitführen. */
  function tocScrollspy(root, tocEl) {
    if (!root || !tocEl) return () => {};
    const heads = Array.from(root.querySelectorAll("h1[id], h2[id], h3[id], h4[id], h5[id]"));
    if (!heads.length) return () => {};
    const entziffern = (t) => { try { return decodeURIComponent(t); } catch (e) { return t; } };
    const links = new Map(Array.from(tocEl.querySelectorAll("a[href^='#']"))
      .map((a) => [entziffern(a.getAttribute("href").slice(1)), a]));
    const onScroll = () => {
      // Eine Überschrift in einem zugeklappten Akkordeon wird nicht gezeichnet; ihr Rechteck
      // liegt bei 0 und galt damit immer als „gerade gelesen“.
      const sichtbar = heads.filter((h) => h.getClientRects().length);
      if (!sichtbar.length) return;
      let active = sichtbar[0];
      for (const h of sichtbar) {
        if (h.getBoundingClientRect().top <= 120) active = h; else break;
      }
      links.forEach((a) => a.classList.remove("active"));
      const hit = links.get(active.id);
      if (hit) hit.classList.add("active");
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }

  /* Beim Laden mit #anker: der Artikel steht erst nach dem Rendern, darum hier nachziehen. */
  function scrollToHash(root) {
    const id = decodeURIComponent((location.hash || "").slice(1));
    if (!id) return false;
    const t = root.querySelector(`[id="${CSS.escape(id)}"]`) || document.getElementById(id);
    if (!t) return false;
    t.scrollIntoView({ block: "start" });
    return true;
  }

  function tocHtml(items) {
    if (!items.length) return "";
    const min = Math.min(...items.map((i) => i.level));
    return `<ul class="toc-list">${items.map((i) => `<li class="l${i.level - min}"><a href="#${esc(i.id)}">${esc(i.text)}</a></li>`).join("")}</ul>`;
  }

  /* Alle darstellbaren Unicode-Emojis (aus den Emoji-Blöcken, gefiltert über einen Render-Test).
     Der Test misst nur die Textbreite: ein Zeichen ohne Schriftschnitt bekommt das Ersatzkästchen
     mit immer gleicher Breite. Ein Auslesen der Pixel je Zeichen (getImageData) wäre genauer,
     würde die Oberfläche beim ersten Öffnen aber für Sekunden anhalten. */
  let emojiCache = null;
  function allEmojis() {
    if (emojiCache) return emojiCache;
    const ranges = [[0x1F600, 0x1F64F], [0x1F300, 0x1F5FF], [0x1F680, 0x1F6FF], [0x1F900, 0x1F9FF], [0x1FA70, 0x1FAFF],
                    [0x2600, 0x26FF], [0x2700, 0x27BF], [0x1F1E6, 0x1F1FF], [0x2B00, 0x2BFF], [0x2190, 0x21FF]];
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = "22px serif";
    const w = (ch) => ctx.measureText(ch).width;
    // Zwei nicht belegte Zeichen als Vergleich – beide ergeben das Ersatzkästchen.
    const tofu = [0x1FFFE, 0x0EFFFF].map((cp) => w(String.fromCodePoint(cp)));
    const out = [];
    for (const [a, b] of ranges) {
      for (let cp = a; cp <= b; cp++) {
        const ch = String.fromCodePoint(cp);
        const cw = w(ch);
        if (cw > 0 && !tofu.includes(cw)) out.push(ch);
      }
    }
    emojiCache = out;
    return out;
  }

  /* Gehört dieses <img> zum Artikel? Im Editor stehen Bilder herum, die nicht im Text stehen:
     der Trennstrich von ProseMirror und das Profilbild in der Autorenzeile. Wer sie mitzählt,
     bringt die Zuordnung „n-tes Bild im Text = n-tes <img>“ durcheinander – und dann trifft
     jede Änderung am Bild das falsche oder bricht ab. */
  const istInhaltsbild = (img) => !!img && img.tagName === "IMG"
    && !img.classList.contains("ProseMirror-separator")
    && !(img.closest && img.closest(".ed-nichtinhalt"));

  return { render, buildToc, tocHtml, enhance, scrollToHash, tocScrollspy, istInhaltsbild,
           CALLOUTS, CALLOUT_FARBEN, ALIGNS, MARKERS, COLOR_NAMES, VIDEO_RE, AUDIO_RE, esc, allEmojis,
           fenceMask, imageWidth, widgetRules, htmlMarksToSyntax, wrapMark, UMBRUCH };
})();
