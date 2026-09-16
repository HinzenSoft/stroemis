/* Der Bearbeitungsverlauf des Editors – also das, was "Rückgängig" zurücknimmt.

   Toast UI baut den Editor mit leerem Inhalt auf und füllt ihn danach über setMarkdown
   beziehungsweise setHTML. Beides sind gewöhnliche ProseMirror-Transaktionen, und schon der
   Aufbau selbst ist eine: Der Konstruktor setzt den Anfangswert ein, das ist gemessen genau ein
   Eintrag. Das mitgelieferte prosemirror-history steckt fest in Toast UIs defaultPlugins und
   schrieb sie alle mit – und fasste sie, weil sie dicht aufeinander folgen, sogar zu einem
   einzigen Schritt zusammen. Ein Strg+Z direkt nach dem Öffnen nahm damit das Laden zurück:
   Der Artikel war schlagartig leer, das Feld meldete eine Änderung, und die Autospeicherung
   schrieb den leeren Stand gut eine Sekunde später zur Seite.

   Der Verlauf soll erst mit der ersten eigenen Änderung beginnen. Von den beiden Wegen dorthin
   nehmen wir den über die Transaktion: "addToHistory: false" ist eine von prosemirror-history
   selbst dokumentierte Angabe, die jede Transaktion mitbringen darf. Gesetzt wird sie, indem der
   Versand der Sicht für die Dauer des Öffnens überzogen wird – welche Transaktionen Toast UI
   dabei auslöst, muss uns so nicht bekannt sein.

   Den Historien-Stapel nachträglich zu leeren wäre der andere Weg. Er verlangt aber den nicht
   exportierten Plugin-Schlüssel von prosemirror-history – zu finden nur über eine Regex auf
   String(plugin.key) – und den Nachbau seines Zustands über spec.state.init(), das dabei ohne
   die von ProseMirror vorgesehenen Argumente gerufen werden müsste. Beides bricht mit dem
   nächsten Toast-UI-Bundle, und zwar still: Die Absicherung wäre weg, ohne dass es auffiele.

   Damit auch der Aufbau mit ins Fenster fällt, muss die Sicht schon während des Konstruktors
   greifbar sein – ed.wwEditor.view gibt es da noch nicht. Beides liefert die dokumentierte
   Plugin-Schnittstelle: Toast UI reicht wysiwygPlugins an ProseMirror weiter, und ProseMirror
   legt die Plugin-Sichten beim Bau der EditorView an, also vor dem Einsetzen des Anfangswerts.

   Benutzung:
       editorOptions.plugins = [..., EDVERLAUF.plugin]
       const ed = EDVERLAUF.oeffnen(() => { const e = new toastui.Editor(editorOptions);
                                            e.setMarkdown(text, false); return e; }); */
window.EDVERLAUF = (function () {
  const sichten = new WeakMap();           // Editor -> EditorView, vom Plugin eingetragen
  let laufend = false;                     // offenes Fenster: nichts kommt in den Verlauf
  const zurueck = [];                      // die Überziehungen dieses Fensters

  const sicht = (ed) => {
    const s = sichten.get(ed);
    if (s) return s;
    // Ohne EDVERLAUF.plugin in den Optionen: lieber der Griff ins Innenleben als gar kein
    // Schutz. Der Aufbau bleibt dann allerdings im Verlauf – siehe oben.
    try { return ed.wwEditor.view || null; } catch (e) { return null; }
  };

  const ueberziehen = (view) => {
    // dispatch liegt am Prototyp der Sicht; die eigene Eigenschaft verdeckt sie nur und wird
    // am Ende des Fensters wieder entfernt. War sie ausnahmsweise schon eigen, kommt die alte
    // zurück.
    const eigen = Object.prototype.hasOwnProperty.call(view, "dispatch");
    const original = view.dispatch;
    view.dispatch = (tr) => original.call(view, tr.setMeta("addToHistory", false));
    zurueck.push(() => { if (eigen) view.dispatch = original; else delete view.dispatch; });
  };

  /* Gehört in editorOptions.plugins. Es trägt nichts zum Dokument bei – es hält nur die Sicht
     fest, sobald ProseMirror sie baut, und zieht sie sofort über, wenn gerade ein Fenster
     offen ist. */
  function plugin(ctx) {
    const { Plugin } = ctx.pmState;
    const ed = ctx.instance;
    return {
      wysiwygPlugins: [() => new Plugin({
        view(eigeneSicht) {
          sichten.set(ed, eigeneSicht);
          if (laufend) ueberziehen(eigeneSicht);
          return {};
        },
      })],
    };
  }

  /* fn ausführen, ohne dass etwas davon rückgängig zu machen wäre. Verschachtelt gilt das
     äußere Fenster; geschlossen wird in jedem Fall, auch wenn fn wirft. */
  function ohne(ed, fn) {
    if (laufend) return fn();
    laufend = true;
    const view = ed ? sicht(ed) : null;
    if (view) ueberziehen(view);
    try { return fn(); } finally {
      laufend = false;
      while (zurueck.length) { try { zurueck.pop()(); } catch (e) { /* egal */ } }
    }
  }

  /* Den Editor bauen und füllen – alles darin bleibt außerhalb des Verlaufs. Die Sicht gibt
     es zu Beginn noch nicht; sie meldet sich aus dem Plugin heraus, während fn läuft. */
  function oeffnen(fn) {
    return ohne(null, fn);
  }

  /* Inhalt eines bestehenden Editors vollständig ersetzen, ohne Verlaufseintrag.
     Zu beachten: Der Vorgang kommt nicht in den Verlauf, er räumt ihn aber auch nicht aus.
     Beim Öffnen ist das dasselbe – da ist noch nichts drin. Wird ein Entwurf erst nach den
     ersten eigenen Tastendrücken übernommen, bleiben die im Verlauf; ein Strg+Z danach nimmt
     also sie zurück, nicht das Übernehmen. Leer wird die Seite dabei nie. */
  function laden(ed, md) {
    ohne(ed, () => ed.setMarkdown(md, false));
  }

  /* Wie viele eigene Schritte ließen sich gerade zurücknehmen? Nur für tests/rundlauf.html –
     hier ist der Griff nach dem nicht exportierten Plugin-Schlüssel zu verantworten, im
     Betrieb nicht. Ohne Fund: -1. */
  function tiefe(ed) {
    const view = sicht(ed);
    if (!view) return -1;
    try {
      const pl = view.state.plugins.find((p) => /^history\$/.test(String(p.key || "")));
      return pl ? pl.getState(view.state).done.eventCount : -1;
    } catch (e) { return -1; }
  }

  return { plugin, oeffnen, ohne, laden, tiefe };
})();
