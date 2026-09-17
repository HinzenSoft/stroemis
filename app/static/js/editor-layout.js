/* Darstellung der Abschnitte im Editor: ausgerichteter Text, Hinweiskiste, einklappbare
   Box und nebeneinanderliegende Spalten. Alles entsteht aus ProseMirror-Dekorationen –
   das Dokument bleibt unberuehrt, das gespeicherte Markdown aendert sich um kein Byte. */
window.EDLAYOUT = (function () {
  const hinweisKopf = window.EDMD.hinweisKopf;
  const MD = window.MD;

  /* --- Echte Darstellung im Editor ---------------------------------------------------
     Die Abschnittsmarken sollen nicht als Beschriftung dastehen, sondern ihre Wirkung
     zeigen: ausgerichteter Text, eine Hinweiskiste, nebeneinanderliegende Spalten.
     Ein umschließendes Element über mehrere Geschwister lässt sich in ProseMirror nicht
     erzeugen – Node-Dekorationen können aber jedem Block eine Klasse und einen Stil
     mitgeben. Das Dokument bleibt unberührt, es ist reine Ansicht; das gespeicherte
     Markdown ändert sich dadurch um kein Byte.
     Außerhalb von Spalten liegt jeder Block in einer eigenen Rasterzeile. Innerhalb eines
     Spaltenabschnitts ginge das nicht: eine Rasterzeile ist über alle Spalten hinweg gleich
     hoch, ein hoher Block links risse rechts eine Lücke. Dort bekommt der ganze Abschnitt
     deshalb EINE Zeile, in der seine Blöcke absolut liegen – die Waagerechte rechnet CSS
     selbst (calc), die Senkrechte misst das Plugin nach jeder Änderung. Damit fließt jede
     Spalte für sich, genau wie in der Leseansicht. */
  const SP_RINNE = 22;                // Rinne zwischen den Spalten – wie in der Leseansicht
  const SP_MINBRUCH = 1 / 8;          // schmaler als ein Achtel: lieber untereinander
  // Auf schmalen Geräten stehen Spalten untereinander – derselbe Umschaltpunkt wie in der
  // Leseansicht (app.css). Ohne das zeigte der Editor auf dem Telefon fünf Spalten zu je
  // 48 Pixeln, während der Artikel daneben sauber gestapelt war.
  const SP_SCHMAL = "(max-width: 640px)";
  const schmalesGeraet = () => typeof matchMedia === "function" && matchMedia(SP_SCHMAL).matches;
  const OEFFNER_ART = ["spalten", "ausrichtung", "hinweis", "akkordeon", "baustein"];
  // Eine Länge aus Prozent und Pixeln – so lassen sich die Spaltenbreiten beliebig tief
  // ineinander rechnen, ohne dass der Ausdruck wächst.
  const laenge = (p, x) => (Math.abs(x) < 0.01 ? `${+p.toFixed(4)}%`
    : `calc(${+p.toFixed(4)}% ${x < 0 ? "-" : "+"} ${Math.abs(+x.toFixed(2))}px)`);
  // Vorsatz für das eigene Stilblatt der Messung – muss die Grundregeln überstimmen.
  const SP_WURZEL = ".wiki-editor .toastui-editor-ww-container .toastui-editor-contents";

  /* Bauplan einer Dokumentfassung: Klassen und Platzierung je Block – und für jeden
     Spaltenabschnitt der Baum, aus dem die Messung die Oberkanten errechnet. Er entsteht
     je Fassung genau einmal; Dekoration und Messung sehen damit immer dasselbe. */
  let planFassung = null, planWert = null, planSchmal = null;
  function spaltenPlan(doc) {
    // Ob Spalten neben- oder untereinander stehen, hängt nicht am Dokument, sondern am
    // Fenster. Beides gehört deshalb in den Schlüssel des Zwischenspeichers: Wird der
    // Bauplan an einem schmalen Fenster gebaut und das Fenster danach breit, ohne dass sich
    // das Dokument ändert, blieben die Spalten sonst gestapelt stehen.
    const schmal = schmalesGeraet();
    if (planFassung === doc && planSchmal === schmal) return planWert;
    const kinder = [];
    doc.forEach((n, off) => {
      const art = n.type.name === "customBlock" ? String(n.attrs.info || "") : "";
      // textContent baut den Text des ganzen Teilbaums neu auf. Gebraucht wird er nur
      // bei zwei Markenarten – sonst kostete das bei jedem Tastendruck unnötig Zeit.
      const brauchtText = art === "ausrichtung" || art === "hinweis";
      kinder.push({ n, von: off, bis: off + n.nodeSize, art, leer: n.content.size === 0,
                    absatz: n.type.name === "paragraph",
                    text: brauchtText ? n.textContent || "" : "" });
    });
    const anz = kinder.length;
    const kl = Array.from({ length: anz }, () => []);
    const stil = Array.from({ length: anz }, () => []);
    const emojiFuer = {};
    const abschnitte = [];             // oberste Spaltenabschnitte, für die gemessen wird
    const wert = { kinder, anz, kl, stil, emojiFuer, abschnitte };
    planFassung = doc; planWert = wert; planSchmal = schmal;
    if (!anz) return wert;

    /* Welche leeren Absätze sind bloße Trennzeichen – und welche sind Inhalt?
       Zwischen zwei Absätzen steht im Markdown eine Leerzeile, und der Editor bildet genau
       sie als leeren Absatz ab; in der Leseansicht steht dort nichts. Jeder WEITERE leere
       Absatz ist dagegen Inhalt: Toast UI schreibt ihn als "<br>", und die Leseansicht zeigt
       ihn als Leerzeile. Von einer Reihe leerer Absätze zwischen zwei Absätzen zählt deshalb
       genau der erste als Trenner – der Rest bleibt stehen, sonst drückte man die
       Eingabetaste und nichts geschähe. Steht vor oder hinter der Reihe kein Absatz (eine
       Marke, eine Tabelle, der Textanfang), ist keiner davon Trenner. */
    /* Bild mit Unterschrift: Die Leseansicht macht aus einem Bildabsatz und dem kursiven
       Absatz darunter EINE Abbildung mit Beschriftung (markdown.js, enhance) – kleinere
       Schrift, engerer Abstand. Im Editor blieben es zwei gewöhnliche Absätze; die Stelle war
       dadurch rund fünfzehn Pixel höher als im Artikel, und alles darunter verschob sich.
       Erkannt wird dieselbe Form: ein Absatz mit nichts als einem Bild, darunter ein Absatz,
       der ganz kursiv ist. */
    const nurBild = (k) => !!k && k.absatz && k.n.childCount === 1 && k.n.firstChild.type.name === "image";
    const ganzKursiv = (k) => {
      if (!k || !k.absatz || !k.n.childCount) return false;
      let kursiv = true;
      k.n.forEach((c) => { if (!c.isText || !c.marks.some((m) => m.type.name === "emph")) kursiv = false; });
      return kursiv;
    };
    /* Ein Bild mitten in einem Absatz: Im Artikel steht jedes Bild als Block auf einer eigenen
       Zeile, im Editor liefe es sonst mitten in der Textzeile mit – der Absatz war dadurch gut
       fünfzig Pixel flacher als im Artikel, und bei mittiger Ausrichtung stand das Bild ein
       Stück neben der Mitte, weil die ganze Zeile mittig gesetzt wurde statt des Bildes. */
    const bildImText = (k) => {
      if (!k || !k.absatz || k.n.childCount < 2) return false;
      let bild = false, anderes = false;
      k.n.forEach((c) => {
        if (c.type.name === "image") bild = true;
        else if (!c.isText || c.text.trim()) anderes = true;
      });
      return bild && anderes;
    };
    const leererAbsatz = (k) => !!k && k.absatz && k.leer;
    const vollerAbsatz = (k) => !!k && k.absatz && !k.leer;
    const fugen = new Set();
    for (let i = 0; i < anz; i++) {
      if (!leererAbsatz(kinder[i]) || leererAbsatz(kinder[i - 1])) continue;   // nur der Reihenanfang
      let j = i;
      while (leererAbsatz(kinder[j + 1])) j++;
      if (vollerAbsatz(kinder[i - 1]) && vollerAbsatz(kinder[j + 1])) fugen.add(i);
    }
    const bildMitUnterschrift = new Set();
    const bildUnterschrift = new Set();
    for (let i = 0; i < anz; i++) {
      if (!nurBild(kinder[i])) continue;
      let j = i + 1;
      while (leererAbsatz(kinder[j])) j++;                 // die Fuge dazwischen überspringen
      if (ganzKursiv(kinder[j])) { bildMitUnterschrift.add(i); bildUnterschrift.add(j); }
    }

    // Sucht zu einer Öffnermarke die zugehörige Schlussmarke und die Trenner darin.
    const struktur = (i) => {
      const trenner = [];
      let tiefe = 1, zu = -1;
      for (let j = i + 1; j < anz; j++) {
        const a = kinder[j].art;
        if (OEFFNER_ART.includes(a)) tiefe++;
        else if (a === "ende") { tiefe--; if (!tiefe) { zu = j; break; } }
        else if ((a === "spalte" || a === "koerper") && tiefe === 1) trenner.push(j);
      }
      return { zu, trenner };
    };

    // Im Fluss eine eigene Rasterzeile, in einer Spalte absolut in der Zeile des Abschnitts.
    const setze = (i, geo, z) => {
      // Eine Leerzeile im Text ist im Editor ein leerer Absatz. In einer Kiste bekäme er
      // sonst denselben Innenabstand wie ein Absatz mit Inhalt und risse sie auseinander.
      if (kinder[i].leer) kl[i].push("ed-leerzeile");
      // Der Trenner zwischen zwei Absätzen wird zugeklappt (siehe app.css) und öffnet sich
      // erst, wenn der Schreibstrich darin steht. Welcher das ist, steht oben in "fugen".
      // Der erste Block einer Kiste oder Spalte trägt deren Symbol und oberen Anschluss –
      // zugeklappt verschwände beides. Er bleibt darum stehen, auch wenn er leer ist.
      if (fugen.has(i) && !kl[i].some((c) => /-erst$/.test(c))) kl[i].push("ed-fuge");
      // Bild und Unterschrift rücken zusammen – wie die Abbildung in der Leseansicht.
      if (bildUnterschrift.has(i)) kl[i].push("ed-unterschrift");
      if (bildMitUnterschrift.has(i)) kl[i].push("ed-bild");
      if (bildImText(kinder[i])) kl[i].push("ed-bild-im-text");
      if (geo.abs) {
        kl[i].push("sp-abs");
        stil[i].push(`--sp-l:${geo.l}`, `--sp-b:${geo.b}`, "grid-column:1/-1", `grid-row:${geo.zeile}`);
      } else {
        stil[i].push("grid-column:1/-1", `grid-row:${z}`);
      }
    };

    /* Legt die Blöcke [von, bis) ab. Im Fluss ist z die nächste freie Rasterzeile und wird
       zurückgegeben; in einer Spalte zählt allein die Reihenfolge, die in geo.liste landet. */
    const lauf = (von, bis, geo, z, erbe) => {
      const stelle = (x, klassen) => {
        kl[x].push(...klassen); setze(x, geo, z);
        if (!geo.abs) z++;
        if (geo.liste) geo.liste.push(x);
      };
      let i = von;
      while (i < bis) {
        const k = kinder[i];
        if (!OEFFNER_ART.includes(k.art)) { stelle(i, erbe); i++; continue; }
        const { zu, trenner } = struktur(i);
        if (zu < 0 || zu >= bis) { stelle(i, erbe); i++; continue; }   // Waise: stehen lassen
        if (k.art === "ausrichtung") {
          const m = (k.text.trim() || "center").toLowerCase();
          stelle(i, [...erbe, "sek-still"]);
          // Die innere Ausrichtung ersetzt die äußere. Würden sich die Klassen stapeln,
          // entschiede die Reihenfolge im CSS statt der Verschachtelung.
          z = lauf(i + 1, zu, geo, z, [...erbe.filter((c) => !/^al-/.test(c)), "al-" + m]);
          stelle(zu, [...erbe, "sek-still"]);
        } else if (k.art === "hinweis") {
          const { kind, emoji, farbe } = hinweisKopf(k.text);
          const farbe1 = farbe ? ["cofarbe-" + farbe] : [];
          stelle(i, [...erbe, "co-marke", "co-" + kind, ...farbe1]);
          // Erster Inhaltsblock trägt das Symbol – wie in der Leseansicht links davor.
          for (let x = i + 1; x < zu; x++) {
            if (kinder[x].art) continue;
            kl[x].push("co-erst", "kasten-erst"); emojiFuer[x] = emoji; break;
          }
          // Ebenso beim Hinweis: die innere Kiste übermalt die äußere, statt ihre
          // Farbe zu erben – sonst gewänne die zuletzt notierte CSS-Regel.
          z = lauf(i + 1, zu, geo, z,
            [...erbe.filter((c) => !/^co(-|$)/.test(c) && !/^cofarbe-/.test(c)), "co", "kasten", "co-" + kind, ...farbe1]);
          stelle(zu, [...erbe, "co-marke", "co-" + kind, "co-schluss", ...farbe1]);
        } else if (k.art === "akkordeon") {
          // Titel (bis zur Trennmarke) und Inhalt sind gewöhnliche Blöcke; die Klassen
          // geben ihnen das Aussehen der aufgeklappten Box aus der Leseansicht.
          const mitte = trenner.find((j) => kinder[j].art === "koerper");
          const trennung = mitte === undefined ? zu : mitte;
          const ohne = erbe.filter((c) => !/^ak(-|$)/.test(c));
          stelle(i, [...erbe, "ak-marke", "ak-auf"]);
          for (let x = i + 1; x < trennung; x++) { if (!kinder[x].art) { kl[x].push("ak-erst"); break; } }
          z = lauf(i + 1, trennung, geo, z, [...ohne, "ak-titel"]);
          if (trennung < zu) {
            stelle(trennung, [...erbe, "ak-marke", "ak-mitte"]);
            for (let x = trennung + 1; x < zu; x++) { if (!kinder[x].art) { kl[x].push("kasten-erst"); break; } }
            z = lauf(trennung + 1, zu, geo, z, [...ohne, "ak", "kasten"]);
          }
          stelle(zu, [...erbe, "ak-marke", "ak-schluss"]);
        } else if (k.art === "baustein") {
          // Ein Baustein ändert am Aussehen nichts – er markiert nur, welcher Teil der Seite
          // anderswo eingebunden wird. Sein Inhalt bleibt gewöhnlicher Text im Fluss. Ohne
          // diesen Zweig fiele er in den letzten und würde als Spaltenabschnitt gesetzt.
          stelle(i, [...erbe, "sek-teil", "sek-teil-auf"]);
          z = lauf(i + 1, zu, geo, z, erbe);
          stelle(zu, [...erbe, "sek-teil"]);
        } else {
          const grenzen = [i, ...trenner.filter((j) => kinder[j].art === "spalte"), zu];
          const n = grenzen.length - 1;
          // Tief verschachtelt bliebe von jeder Spalte nur ein Strich übrig – dann untereinander
          // statt nebeneinander, mit voller Breite. Auf schmalen Geräten gilt das immer.
          const stapeln = schmal || geo.bruch / n < SP_MINBRUCH;
          const zeile = geo.abs ? geo.zeile : z;
          const spalten = [];
          let gemeinsam = null;
          for (let c = 0; c < n; c++) {
            let liste, lP, lX, bP, bX, bruch;
            if (stapeln) {
              if (!gemeinsam) { gemeinsam = []; spalten.push(gemeinsam); }
              liste = gemeinsam;
              lP = geo.lP; lX = geo.lX; bP = geo.bP; bX = geo.bX; bruch = geo.bruch;
            } else {
              liste = []; spalten.push(liste);
              bP = geo.bP / n; bX = (geo.bX - (n - 1) * SP_RINNE) / n;
              lP = geo.lP + c * bP; lX = geo.lX + c * (bX + SP_RINNE);
              bruch = geo.bruch / n;
            }
            const g = { abs: true, zeile, liste, bruch, lP, lX, bP, bX,
                        l: laenge(lP, lX), b: laenge(bP, bX) };
            kl[grenzen[c]].push(...erbe, "sp-kopf");
            setze(grenzen[c], g);
            liste.push(grenzen[c]);
            // Wie in der Leseansicht (.columns .col > :first-child) beginnt die Spalte ohne
            // oberen Rand – auch wenn dort eine Kiste anfängt, deren Marke sonst 1,1em einrückte.
            if (grenzen[c] + 1 < grenzen[c + 1]) kl[grenzen[c] + 1].push("sp-erst");
            lauf(grenzen[c] + 1, grenzen[c + 1], g, 0, erbe);
          }
          if (geo.abs) {
            // Spalten in Spalten: auch die Schlussmarke liegt absolut. Ihre Höhe zählt die
            // Messung über den Knoten mit, den die umgebende Spalte hier bekommt.
            kl[zu].push(...erbe, "sp-fuss");
            setze(zu, geo);
            geo.liste.push({ spalten, zu });
          } else {
            // Die Schlussmarke bleibt im Fluss: sie hält die Zeile auf, in der alle
            // Spaltenblöcke absolut liegen (ihr oberer Rand ist die gemessene Höhe).
            kl[zu].push(...erbe, "sp-fuss");
            setze(zu, geo, z); z++;
            abschnitte.push({ zu, spalten });
          }
        }
        i = zu + 1;
      }
      return z;
    };

    const wurzel = { abs: false, bruch: 1, lP: 0, lX: 0, bP: 100, bX: 0, liste: null };
    // Zeile 2 bleibt der Autorzeile vorbehalten: sie ist ein Widget und bekommt vom
    // Plugin keine Dekoration – ohne reservierte Zeile setzt das Raster sie ans Ende.
    if (kinder[0].n.type.name === "heading") {
      setze(0, wurzel, 1);
      lauf(1, anz, wurzel, 3, []);
    } else {
      lauf(0, anz, wurzel, 1, []);
    }
    return wert;
  }

  /* Alle Blockindizes eines Spaltenbaums – in dieser Reihenfolge wird gemessen. */
  const spaltenIndizes = (liste, raus) => {
    liste.forEach((e) => {
      if (typeof e === "number") raus.push(e);
      else { e.spalten.forEach((sp) => spaltenIndizes(sp, raus)); raus.push(e.zu); }
    });
    return raus;
  };

  /* --- Einzeilige Hinweiskisten in Tabellenzellen ------------------------------------
     ":::warning Kurzer Text :::" steht in einer Zelle als gewöhnlicher Text; die Leseansicht
     macht daraus eine Kiste (markdown.js, calloutInline). Im Editor sah man bisher die rohen
     Marken. Dieselbe Regel wie dort – Art, dann Inhalt, dann Schlussmarke – gibt der Zelle
     hier die Fläche und blendet die beiden Marken aus. Das Dokument bleibt unberührt: Auch
     das Ausblenden ist nur Ansicht, gespeichert wird der Text Zeichen für Zeichen wie bisher. */
  // Dieselbe Regel wie calloutInline in markdown.js: die ERSTE Schlussmarke beendet die
  // Kiste. Gezeichnet wird nur, wenn sie damit die ganze Zelle füllt – steht dahinter noch
  // Text, zöge die Leseansicht ihn aus der Kiste heraus, und der Editor zeigte etwas anderes.
  const ZELL_KASTE = /^(:::[ \t]*([A-Za-z]+)[ \t]+)([\s\S]*?)([ \t]*:::)/;
  const ZELLE = { tableHeadCell: true, tableBodyCell: true };
  const IN_TABELLE = { table: true, tableHead: true, tableBody: true, tableRow: true };

  function zellenKaesten(doc, decos, Decoration) {
    doc.descendants((n, pos) => {
      if (!ZELLE[n.type.name]) return !!IN_TABELLE[n.type.name];
      // Nur die einfache Zelle: ein Absatz, darin ausschließlich Text. Steckt ein Bild oder
      // ein Widget darin, verschöben die Textstellen sich gegen die Dokumentstellen.
      const absatz = n.firstChild;
      if (n.childCount !== 1 || !absatz || absatz.type.name !== "paragraph") return false;
      let nurText = true;
      absatz.forEach((k) => { if (!k.isText) nurText = false; });
      if (!nurText) return false;
      const text = absatz.textContent;
      const m = ZELL_KASTE.exec(text);
      if (!m || m[0].length !== text.length || !(m[2].toLowerCase() in MD.CALLOUTS)) return false;
      const art = m[2].toLowerCase();
      // Die Kiste ist der Absatz in der Zelle – wie in der Leseansicht, wo das Kästchen in
      // der Zelle steht und nicht die Zelle selbst ist. Stellen zählen vom Absatzinhalt an.
      const inhalt = pos + 2;
      decos.push(Decoration.node(pos + 1, pos + 1 + absatz.nodeSize,
                                 { class: "co-zelle coz-" + art, "data-emoji": MD.CALLOUTS[art] }));
      decos.push(Decoration.inline(inhalt, inhalt + m[1].length, { class: "co-zeichen" }));
      const schluss = inhalt + m[1].length + m[3].length;
      decos.push(Decoration.inline(schluss, schluss + m[4].length, { class: "co-zeichen" }));
      return false;
    });
  }

  /* --- Schutz vor versehentlichem Löschen -----------------------------------------------
     Eine Tabelle, ein Spaltenabschnitt, ein Ausrichtungsblock oder eine Hinweiskiste ist mit
     einem einzigen Tastendruck weg, wenn der Schreibstrich unmittelbar davor oder dahinter
     steht. Beim Abschnitt ist es schlimmer als es aussieht: Verschwindet nur eine seiner
     Marken, löst sich beim Speichern der ganze Abschnitt auf – der Inhalt bleibt, der Kasten
     ist fort. Entfernen und Rücktaste lassen diese Blöcke deshalb stehen. Weg kommen sie über
     ihr eigenes Menü ("Tabelle löschen", "Block löschen", "Abschnitt löschen").
     Der Baustein bleibt vorerst außen vor – danach war nicht gefragt. */
  const GESCHUETZT_AUF = ["spalten", "ausrichtung", "hinweis", "akkordeon"];

  function geschuetzteKnoten(doc) {
    const raus = [];
    const stapel = [];
    doc.forEach((n, off) => {
      const art = n.type.name === "customBlock" ? String(n.attrs.info || "") : "";
      const eintrag = (a) => raus.push({ von: off, bis: off + n.nodeSize, art: a });
      if (OEFFNER_ART.includes(art)) {
        stapel.push(art);
        if (GESCHUETZT_AUF.includes(art)) eintrag(art);
      } else if (art === "ende") {
        const auf = stapel.pop();
        if (GESCHUETZT_AUF.includes(auf)) eintrag(auf);
      } else if (art === "spalte") {
        if (stapel[stapel.length - 1] === "spalten") eintrag("spalten");
      } else if (art === "koerper") {
        // Die Trennmarke zwischen Titel und Inhalt der einklappbaren Box: Fehlt sie, wird beim
        // Speichern der ganze Abschnitt zum Titel und die Box steht leer da.
        if (stapel[stapel.length - 1] === "akkordeon") eintrag("akkordeon");
      } else if (n.type.name === "table") {
        eintrag("tabelle");
      }
    });
    return raus;
  }

  /* Meldet die abgewehrte Taste nach außen – die Oberfläche macht daraus einen Hinweis.
     Ohne ihn bliebe die Taste einfach wirkungslos, und das liest sich wie ein Fehler. */
  const meldeSchutz = (art) => {
    try { document.dispatchEvent(new CustomEvent("edlayout:geschuetzt", { detail: { art } })); }
    catch (e) { /* egal */ }
  };

  /* Ersetzt die Auswahl einen geschützten Block ganz? Dann wird die Eingabe verworfen und der
     Grund gemeldet – wie bei Entf und Rücktaste. */
  function auswahlGeschuetzt(sicht) {
    if (sicht.state.selection.empty) return false;
    let art = null;
    try { art = loeschenAbwehren(sicht.state, false); } catch (e) { return false; }
    if (!art) return false;
    meldeSchutz(art);
    return true;
  }

  function loeschenAbwehren(zustand, rueckwaerts) {
    const geschuetzt = geschuetzteKnoten(zustand.doc);
    if (!geschuetzt.length) return null;
    const aus = zustand.selection;
    if (!aus.empty) {
      // Ein Knoten, der ganz in der Auswahl liegt, wäre danach weg.
      const treffer = geschuetzt.find((g) => g.von >= aus.from && g.bis <= aus.to);
      return treffer ? treffer.art : null;
    }
    const $v = aus.$from;
    if ($v.depth < 1) return null;
    // Nur ganz am Rand des obersten Blocks kommt der Nachbar überhaupt in Reichweite. Steht
    // der Strich mitten im Text – oder tiefer, etwa in einer Liste –, trifft die Taste nur
    // den eigenen Block, und ProseMirror hebt ihn heraus, statt den Nachbarn anzufassen.
    if (rueckwaerts) {
      if ($v.pos !== $v.start(1)) return null;
      const ende = $v.before(1);
      const treffer = geschuetzt.find((g) => g.bis === ende);
      return treffer ? treffer.art : null;
    }
    if ($v.pos !== $v.end(1)) return null;
    const anfang = $v.after(1);
    const treffer = geschuetzt.find((g) => g.von === anfang);
    return treffer ? treffer.art : null;
  }

  function layoutPlugin(ctx) {
    const { Plugin } = ctx.pmState;
    const { Decoration, DecorationSet } = ctx.pmView;
    return {
      wysiwygPlugins: [() => new Plugin({
        /* Zwei Absätze trennt im Markdown eine Leerzeile, und der Editor bildet sie als leeren
           Absatz ab. Beim Teilen mit der Eingabetaste entsteht dieser Absatz aber NICHT: Aus
           einem Absatz werden zwei unmittelbar aufeinanderfolgende, und Toast UI schreibt sie
           mit nur einem Zeilenumbruch dazwischen. Markdown liest daraus wieder EINEN Absatz –
           der neue Absatz war nach dem Speichern also wieder weg.
           Die Lücke wird deshalb nach jeder Änderung geschlossen. Nicht im Verlauf: Es ist
           keine Änderung des Nutzers, sondern die Schreibweise, die das Format verlangt. */
        appendTransaction(_vorgaenge, alt, neu) {
          if (alt.doc === neu.doc) return null;
          const luecken = [];
          let vorherAbsatz = false;
          neu.doc.forEach((n, off) => {
            const absatz = n.type.name === "paragraph" && n.content.size > 0;
            if (vorherAbsatz && absatz) luecken.push(off);
            vorherAbsatz = absatz;
          });
          if (!luecken.length) return null;
          const art = neu.schema.nodes.paragraph;
          if (!art) return null;
          const tr = neu.tr;
          // Von hinten nach vorn, damit die vorderen Stellen gültig bleiben.
          luecken.reverse().forEach((stelle) => tr.insert(stelle, art.create()));
          return tr.setMeta("addToHistory", false);
        },
        props: {
          decorations(zustand) {
            const plan = spaltenPlan(zustand.doc);
            if (!plan.anz) return null;
            const misst = plan.abschnitte.length > 0;
            // Der Block, in dem der Schreibstrich steht: seine Fuge bleibt offen. Das hängt
            // allein an der Auswahl, nicht am Dokument – der Bauplan oben wird je Fassung
            // zwischengespeichert und darf davon nichts wissen.
            let offen = -1;
            try {
              const $v = zustand.selection.$from;
              const stelle = $v.depth >= 1 ? $v.before(1) : $v.pos;
              offen = plan.kinder.findIndex((k) => k.von === stelle);
            } catch (e) { /* keine brauchbare Auswahl – dann bleibt alles zu */ }
            const decos = [];
            for (let i = 0; i < plan.anz; i++) {
              const attrs = {};
              const klassen = i === offen ? plan.kl[i].filter((c) => c !== "ed-fuge") : plan.kl[i];
              if (klassen.length) attrs.class = Array.from(new Set(klassen)).join(" ");
              if (plan.stil[i].length) attrs.style = plan.stil[i].join(";");
              if (plan.emojiFuer[i]) attrs["data-emoji"] = plan.emojiFuer[i];
              // Die gemessenen Oberkanten stehen in einem eigenen Stilblatt und finden ihren
              // Block über diese Kennung. Als Attribut setzt ProseMirror sie selbst – ein
              // nachträglich geschriebener style-Wert läse der DOM-Beobachter als Änderung
              // des Dokuments zurück, und das bei jedem Tastendruck.
              if (misst && (plan.kl[i].includes("sp-abs") || plan.kl[i].includes("sp-fuss"))) attrs["data-sp"] = String(i);
              if (attrs.class || attrs.style) decos.push(Decoration.node(plan.kinder[i].von, plan.kinder[i].bis, attrs));
            }
            zellenKaesten(zustand.doc, decos, Decoration);
            return DecorationSet.create(zustand.doc, decos);
          },
          handleKeyDown(sicht, ereignis) {
            if (ereignis.key !== "Backspace" && ereignis.key !== "Delete") return false;
            let art = null;
            try { art = loeschenAbwehren(sicht.state, ereignis.key === "Backspace"); }
            catch (e) { return false; }        // im Zweifel lieber nicht dazwischenfunken
            if (!art) return false;
            meldeSchutz(art);
            return true;                       // die Taste ist verbraucht, nichts geschieht
          },
          /* Dieselbe Wache für alles, was eine AUSWAHL ersetzt: ein getipptes Zeichen, Einfügen,
             Ablegen, Ausschneiden. Sonst genügte Strg+X über eine Tabelle, wo Entf abgewehrt wird. */
          handleTextInput(sicht) { return auswahlGeschuetzt(sicht); },
          handlePaste(sicht) { return auswahlGeschuetzt(sicht); },
          handleDrop(sicht) { return auswahlGeschuetzt(sicht); },
          handleDOMEvents: {
            cut(sicht, ereignis) {
              if (!auswahlGeschuetzt(sicht)) return false;
              ereignis.preventDefault();
              return true;
            },
            /* Tippen über eine Auswahl läuft in Chrome nicht durch handleTextInput, sondern
               ersetzt den Bereich als Ganzes – beforeinput kommt davor und lässt sich abbrechen. */
            beforeinput(sicht, ereignis) {
              if (ereignis.inputType && /^(delete|history)/.test(ereignis.inputType)) return false;   // Entf/Rücktaste macht handleKeyDown
              if (!auswahlGeschuetzt(sicht)) return false;
              ereignis.preventDefault();
              return true;
            },
          },
        },
        /* Die Senkrechte der Spalten: nach jeder Änderung die Höhen lesen, daraus je Spalte
           die Oberkanten aufsummieren und in ein eigenes Stilblatt schreiben. Das läuft
           synchron in derselben Aufgabe wie die Dekoration – vor dem Zeichnen, also ohne
           Flackern, und noch vor ProseMirrors eigenem scrollIntoView. */
        view(sicht) {
          const blatt = document.createElement("style");
          document.head.appendChild(blatt);
          let lebt = true, rahmen = 0, letzte = null, beobachtet = [];
          const beo = typeof ResizeObserver === "function" ? new ResizeObserver(() => plan()) : null;
          function plan() {
            if (!lebt || rahmen) return;
            rahmen = requestAnimationFrame(() => { rahmen = 0; messen(); });
          }
          function messen() {
            if (!lebt) return;
            let p;
            try { p = spaltenPlan(sicht.state.doc); } catch (e) { return; }
            if (!p.abschnitte.length) {
              if (letzte !== "") { blatt.textContent = ""; letzte = ""; }
              if (beo) { beo.disconnect(); beobachtet = []; }
              return;
            }
            const el = {};
            sicht.dom.querySelectorAll(":scope > [data-sp]").forEach((e) => { el[e.getAttribute("data-sp")] = e; });
            const idx = [];
            p.abschnitte.forEach((a) => { a.spalten.forEach((sp) => spaltenIndizes(sp, idx)); idx.push(a.zu); });
            // Erst alles lesen, dann rechnen, dann einmal schreiben – ein Umbruch je Runde.
            const h = {};
            idx.forEach((i) => {
              const e = el[i];
              if (!e) { h[i] = 0; return; }
              const r = e.getBoundingClientRect();
              const c = getComputedStyle(e);
              h[i] = r.height + (parseFloat(c.marginTop) || 0) + (parseFloat(c.marginBottom) || 0);
            });
            const breite = sicht.dom.clientWidth;
            // Wie in der Leseansicht (@media max-width: 640px) stehen die Spalten auf schmalen
            // Bildschirmen untereinander. Maßgeblich ist dieselbe Größe wie dort – die des
            // Fensters, nicht die der Textspalte; sonst stünden sie in den beiden Ansichten
            // unterschiedlich. Gerechnet wird dann einfach hintereinander statt nebeneinander.
            const schmal = window.innerWidth <= 640;
            const sig = breite + "|" + (schmal ? "s" : "b") + "|" + idx.map((i) => h[i].toFixed(2)).join(",");
            if (sig === letzte) return;
            letzte = sig;
            const oben = {};
            const laufY = (liste, y) => {
              for (const e of liste) {
                if (typeof e === "number") { oben[e] = y; y += h[e]; }
                else {
                  let u = y;
                  if (schmal) e.spalten.forEach((sp) => { u = laufY(sp, u); });
                  else e.spalten.forEach((sp) => { u = Math.max(u, laufY(sp, y)); });
                  oben[e.zu] = u; y = u + h[e.zu];
                }
              }
              return y;
            };
            const regeln = [];
            p.abschnitte.forEach((a) => {
              let u = 0;
              if (schmal) a.spalten.forEach((sp) => { u = laufY(sp, u); });
              else a.spalten.forEach((sp) => { u = Math.max(u, laufY(sp, 0)); });
              regeln.push(`${SP_WURZEL} > [data-sp="${a.zu}"]{margin-top:${u.toFixed(2)}px}`);
            });
            const voll = schmal ? ";left:0;width:100%" : "";
            Object.keys(oben).forEach((i) => {
              regeln.push(`${SP_WURZEL} > [data-sp="${i}"]{top:${oben[i].toFixed(2)}px${voll}}`);
            });
            blatt.textContent = regeln.join("\n");
            if (beo) {
              beobachtet.forEach((e) => beo.unobserve(e));
              beobachtet = idx.map((i) => el[i]).filter(Boolean);
              beobachtet.forEach((e) => beo.observe(e));
              beo.observe(sicht.dom);
              beobachtet.push(sicht.dom);
            }
          }
          // Bilder und Schriften ändern die Höhe erst, wenn sie geladen sind.
          const spaet = () => {
            if (!lebt) return;
            sicht.dom.querySelectorAll("img, video").forEach((m) => {
              if (m.dataset.spWartet) return;
              const fertig = m.tagName === "IMG" ? m.complete : m.readyState > 0;
              if (fertig) return;
              m.dataset.spWartet = "1";
              ["load", "loadedmetadata", "error"].forEach((n) => m.addEventListener(n, plan, { once: true }));
            });
          };
          messen(); spaet();
          if (document.fonts && document.fonts.ready) document.fonts.ready.then(plan, () => {});
          /* Ob Spalten nebeneinander oder untereinander stehen, entscheidet die Dekoration –
             und die berechnet ProseMirror nur bei einer Zustandsänderung neu, nicht beim
             Ändern der Fensterbreite. Wer also am Telefon quer dreht oder das Fenster über den
             Umschaltpunkt zieht, behielte sonst das alte Layout. Eine leere Transaktion stößt
             die Neuberechnung an, ohne das Dokument anzufassen: docChanged bleibt falsch, das
             automatische Speichern läuft nicht an. */
          function beiGroessenwechsel() {
            // Verglichen wird mit dem Stand, aus dem der Bauplan gebaut wurde – nicht mit
            // einem eigenen Merker: Beide könnten auseinanderlaufen, wenn der Editor gerade
            // beim Aufbau des Fensters entsteht.
            if (schmalesGeraet() !== planSchmal) {
              try { sicht.dispatch(sicht.state.tr.setMeta("addToHistory", false)); } catch (e) { /* egal */ }
            }
            plan();
          }
          window.addEventListener("resize", beiGroessenwechsel);
          return {
            update() { messen(); spaet(); },
            destroy() {
              lebt = false;
              if (rahmen) cancelAnimationFrame(rahmen);
              if (beo) beo.disconnect();
              window.removeEventListener("resize", beiGroessenwechsel);
              blatt.remove();
            },
          };
        },
      })],
    };
  }


  /* Ein Fehler beim Übersetzen des Toast-UI-Bündels 3.2.2: Die Zellauswahl
     (CellSelection – der Zug über mehrere Zellen) ist nach ES5 übersetzt und ruft ihre
     Oberklasse als "Selection.call(this, …)" auf. Selection selbst liegt im selben Bündel
     aber als ES6-Klasse, und eine Klasse lässt sich ohne "new" nicht aufrufen: Jeder Zug über
     mehrere Zellen endete deshalb in einer Ausnahme, die Auswahl entstand nie – und ohne sie
     gibt es kein Verbinden von Zellen.
     Geflickt wird an der Klasse selbst: Ein eigener Eintrag "call" verdeckt
     Function.prototype.call und baut nach, was der Konstruktor tut (er setzt genau diese drei
     Felder). Im ganzen Bündel gibt es nur diese eine Stelle, die Selection so aufruft; alle
     anderen Auswahlarten sind selbst ES6-Klassen und benutzen "super". */
  function zellenAuswahlReparieren(pmState) {
    const Auswahl = pmState && pmState.Selection;
    if (!Auswahl || Object.prototype.hasOwnProperty.call(Auswahl, "call")) return;
    let gefeilt = false;
    Auswahl.call = function (ziel, anker, kopf, bereiche) {
      ziel.$anchor = anker;
      ziel.$head = kopf;
      ziel.ranges = bereiche || [{ $from: anker.min(kopf), $to: anker.max(kopf) }];
      if (!gefeilt) { gefeilt = true; abbildungAbsichern(Object.getPrototypeOf(ziel), Auswahl); }
      return ziel;
    };
  }

  /* Und noch eine Folge desselben Bauteils: Wird der Text ausgetauscht, während eine Zellauswahl
     steht (Rückgängig, Laden eines Entwurfs, jedes setMd), rechnet Toast UI die alte Auswahl auf
     den neuen Text um – findet die Zelle dort nicht mehr und läuft in eine Ausnahme. Der Editor
     bliebe stehen. Statt dessen wird auf eine gewöhnliche Textauswahl an derselben Stelle
     ausgewichen. */
  function abbildungAbsichern(proto, Auswahl) {
    const original = proto && proto.map;
    if (typeof original !== "function") return;
    proto.map = function (doc, abbildung) {
      try { return original.call(this, doc, abbildung); }
      catch (e) {
        const roh = abbildung.map(this.startCell ? this.startCell.pos : 0);
        return Auswahl.near(doc.resolve(Math.max(0, Math.min(roh, doc.content.size))));
      }
    };
  }

  // Die Reparatur braucht nur das Modul, nicht den Editor: als Erweiterung eingehängt, weil
  // Toast UI dort "pmState" herausgibt – dieselbe Modulinstanz, die der Editor selbst benutzt.
  const zellenAuswahl = ({ pmState }) => { zellenAuswahlReparieren(pmState); return {}; };

  /* --- Die Schilder der Abschnittsmarken sind kein Schreibgrund ------------------------
     Ein Schild ist ein Custom-Block, und sein Text ist das Argument der Marke: bei
     "$$baustein / sicherung" die Kennung. Gerät der Schreibstrich hinein – über die
     Pfeiltasten ist das ein Tastendruck –, schreibt jede Eingabe dort hinein. Aus der Kennung
     wurde dann "Erster Absatz.\n\nZweiter Absatz.sicherung", und beim Speichern zerfiel der
     ganze Abschnitt: Die Marke war nicht mehr als solche zu erkennen, der Rumpf stand als
     roher "$$baustein"-Text im Artikel und das Gegenstück fehlte.
     Statt die Eingabe wortlos zu schlucken, wandert sie dorthin, wo sie hingehört: unmittelbar
     hinter das Schild – bei einer öffnenden Marke ist das der Anfang des Abschnitts. */
  const MARKE_INFO = new Set(["spalten", "spalte", "ausrichtung", "hinweis", "akkordeon",
                              "koerper", "baustein", "einbau", "ende"]);
  const markeUm = ($pos) => {
    for (let d = $pos.depth; d > 0; d--) {
      const knoten = $pos.node(d);
      if (knoten.type.name !== "customBlock") continue;
      return MARKE_INFO.has(String(knoten.attrs.info || "").trim())
        ? { knoten, pos: $pos.before(d) } : null;
    }
    return null;
  };
  /* "scheibe" ist eine ProseMirror-Slice (aus der Zwischenablage), "knoten" ein einzelner
     Knoten (ein getippter Absatz). Die Slice wird über replaceRange eingesetzt: insert() legte
     sie roh an die Stelle, und eine Aufzählung kam dabei als zwei Textzeilen an. */
  const hinterDieMarke = (view, marke, { scheibe, knoten }) => {
    const pos = marke.pos + marke.knoten.nodeSize;
    try {
      const tr = scheibe ? view.state.tr.replaceRange(pos, pos, scheibe)
                         : view.state.tr.insert(pos, knoten);
      const Auswahl = Object.getPrototypeOf(view.state.selection.constructor);
      const ende = Math.min(pos + (scheibe ? scheibe.content.size : knoten.nodeSize), tr.doc.content.size);
      tr.setSelection(Auswahl.near(tr.doc.resolve(ende)));
      view.dispatch(tr.scrollIntoView());
    } catch (e) {
      // Passt der Inhalt dort nicht hinein, bleibt es beim Nichtstun – lieber nichts einfügen
      // als die Marke zerschreiben.
    }
    return true;
  };
  const markenSchuetzen = ({ pmState }) => ({
    wysiwygPlugins: [() => new pmState.Plugin({
      props: {
        handleTextInput(view, von, bis, text) {
          const marke = markeUm(view.state.doc.resolve(von));
          if (!marke) return false;
          const absatz = view.state.schema.nodes.paragraph;
          if (!absatz || !text) return true;
          return hinterDieMarke(view, marke, { knoten: absatz.create(null, view.state.schema.text(text)) });
        },
        handlePaste(view, ereignis, scheibe) {
          const marke = markeUm(view.state.selection.$from);
          if (!marke) return false;
          return hinterDieMarke(view, marke, { scheibe });
        },
      },
    })],
  });

  return { layoutPlugin, zellenAuswahl, markenSchuetzen };
})();
