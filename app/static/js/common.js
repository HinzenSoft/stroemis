/* Gemeinsame Hilfsfunktionen für alle Seiten */
window.S = (function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(path, opts = {}) {
    const init = { method: opts.method || "GET", headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" };
    // keepalive: Die Anfrage kommt auch an, wenn die Seite gerade geht (Neuladen, Zurück) – etwa Getipptes im Prüfformular.
    if (opts.keepalive) init.keepalive = true;
    if (opts.body instanceof FormData) {
      init.body = opts.body;
    } else if (opts.body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body);
    }
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      // Kein Serverstatus: Das Netz war weg, der Server nicht erreichbar oder die Anfrage
      // abgebrochen. Das ist etwas anderes als "gibt es nicht" – wer beides gleich behandelt,
      // behauptet bei jedem Wacklen, der Inhalt existiere nicht.
      const netz = new Error("Keine Verbindung zum Server.");
      netz.status = 0;
      throw netz;
    }
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname);
      throw new Error("Nicht angemeldet");
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* leer */ }
    if (!res.ok) {
      // Der Status gehört an den Fehler: Nur damit lässt sich später "gibt es nicht" (404/403)
      // von "gerade nicht erreichbar" (0, 5xx) unterscheiden.
      const err = new Error(data.error || ("Fehler " + res.status));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  let toastTimer;
  /* Ist ein Dialog offen, erscheint die Meldung bei IHM statt am unteren Fensterrand: Auf einem
     großen, hohen Bildschirm sitzt ein mittig geöffneter Dialog oft weit über dem unteren Rand –
     eine Fehlermeldung dort ("Bitte einen Titel angeben") blieb unbemerkt, während der Blick noch
     auf dem Formular lag. Ist über dem Dialog Platz, schwebt die Meldung wie eine Fahne darüber;
     füllt der Dialog fast den Bildschirm (Telefon), rutscht sie stattdessen in seinen oberen Rand.
     Berechnet wird das bei jedem Aufruf neu – der Dialog bewegt sich während der kurzen Anzeigezeit
     ohnehin nicht. */
  function toastPositionieren(el) {
    const offene = document.querySelectorAll("dialog[open]");
    const dlg = offene[offene.length - 1];   // zuletzt geöffnet liegt oben (z. B. eine Rückfrage)
    if (!dlg) { el.classList.remove("bei-dialog", "bei-dialog-innen"); return; }
    const r = dlg.getBoundingClientRect();
    el.style.setProperty("--toast-x", Math.round(r.left + r.width / 2) + "px");
    el.classList.add("bei-dialog");
    if (r.top > 64) {
      el.style.setProperty("--toast-y", Math.round(r.top - 10) + "px");
      el.classList.remove("bei-dialog-innen");
    } else {
      el.style.setProperty("--toast-y", Math.round(r.top + 10) + "px");
      el.classList.add("bei-dialog-innen");
    }
  }

  /* Der Toast liegt als Popover in der obersten Ebene des Browsers – über dem Backdrop eines
     modalen Dialogs. Sonst stand „Bitte einen Nutzer wählen“ gedimmt HINTER dem Dialog, aus
     dem die Meldung kam. Ältere Browser ohne Popover zeigen ihn wie bisher. */
  function toast(msg, isError) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "show" + (isError ? " err" : "");
    // Ein Fehler unterbricht sofort (assertive), eine Bestätigung wartet, bis eine Sprechpause ist.
    el.setAttribute("role", isError ? "alert" : "status");
    el.setAttribute("aria-live", isError ? "assertive" : "polite");
    toastPositionieren(el);
    try { if (!el.hasAttribute("popover")) el.setAttribute("popover", "manual"); el.showPopover(); } catch (e) { /* kein Popover */ }
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.className = "";
      try { el.hidePopover(); } catch (e) { /* egal */ }
    }, isError ? 5000 : 2800);
  }

  /* --- Zurück schließt Overlays (UI/UX vor dem Merge, A1) ---------------------------------------------------------
     Die Zurück-Taste oder -Geste (Android, Wischen am iPhone) verließ die Seite, auch wenn nur ein Dialog, eine
     Schublade oder eine Großansicht offen war – ein halb ausgefülltes Formular war damit weg. Jetzt legt jedes Overlay
     beim Öffnen einen eigenen Verlaufseintrag an (dieselbe Adresse, im Zustand die Tiefe unter OV); Zurück schließt das
     oberste Overlay statt die Seite zu verlassen. Schließt es auf anderem Weg (Knopf, Esc, daneben), nimmt es seinen
     Eintrag wieder heraus – kein doppeltes Zurück, und „Vor“ führt nicht in einen Zustand, den es nicht mehr gibt (ein
     solcher toter Eintrag wird sofort wieder verlassen).
     Ein Dialog wird dabei wie mit Esc geschlossen (Ereignis „cancel“): Wer Esc abfängt – ungespeicherte Freigaben,
     laufendes Hochladen, Unterschrift unterwegs –, hält auch Zurück auf; der Eintrag kommt dann wieder hinzu.
     Verträglich mit der eigenen Adressführung der Seiten: history.pushState/replaceState sind hier umhüllt. Schreibt
     eine Seite ihre Adresse um, während ein Overlay offen ist (Filter, #album=…), gilt die neue Adresse auch nach dem
     Schließen; wechselt die Strömipedia die Seite aus der offenen Schublade heraus, nimmt die neue Seite den Eintrag des
     Overlays ein, statt darüber zu liegen. Schritte zurück, die nur Overlays betreffen, sieht der Code der Seite nicht
     (popstate wird angehalten) – der Editor der Strömipedia fragte sonst „Änderungen verwerfen?“.
     Geht die Seite gerade (beforeunload: Speichern, dann location.href), unterbleibt der Schritt zurück: Chromium
     bräche damit den Seitenwechsel ab. Der Eintrag bleibt dann tot stehen und wird beim nächsten Zurück übersprungen. */
  const OV = "stroemisOverlay";
  const ovStapel = [];                 // offene Overlays mit eigenem Eintrag, unterstes zuerst: { tiefe, schliessen, offen }
  const ovNachher = [];                // geöffnet, während ein Schritt zurück lief – ihr Eintrag kommt danach
  let ovWarten = false;                // ein eigener Schritt zurück läuft, sein popstate steht aus
  let ovImZurueck = false;             // Overlays schließen gerade wegen Zurück
  let ovPlan = null;                   // geplanter Schritt zurück (setTimeout)
  let ovSeiteGeht = 0;                 // Zeitpunkt von beforeunload
  let ovVerborgen = false;             // zwischen pagehide und pageshow (bfcache)
  let ovSeite = null;                  // { state, url }: was die Seite in die Adresse schrieb, während ein Overlay offen war
  let ovAktuell = 0;                   // Tiefe des Eintrags, auf dem wir stehen
  let ovGesehen = location.href;       // die Adresse, die der Code der Seite zuletzt kannte
  const ovPush = history.pushState.bind(history);
  const ovReplace = history.replaceState.bind(history);
  const ovTiefe = (st) => (st && typeof st === "object" && typeof st[OV] === "number" ? st[OV] : 0);
  const ovMit = (st, d) => (d ? Object.assign({}, st && typeof st === "object" ? st : null, { [OV]: d }) : ovOhne(st));
  function ovOhne(st) {
    if (!st || typeof st !== "object" || !(OV in st)) return st;
    const rest = Object.assign({}, st);
    delete rest[OV];
    return Object.keys(rest).length ? rest : null;
  }
  const ovOben = () => (ovStapel.length ? ovStapel[ovStapel.length - 1].tiefe : 0);
  // Ein frisch geladenes Dokument hat kein offenes Overlay – stand der Eintrag auf einem (Zurück von einer anderen Seite
  // ohne bfcache), gilt er als gewöhnlicher Eintrag der Seite.
  if (ovTiefe(history.state)) ovReplace(ovOhne(history.state), "");

  function ovEintragen(o) {
    const d = ovTiefe(history.state);
    const k = ovOben();
    o.tiefe = k + 1;
    // Steht oben noch ein toter Eintrag (Overlay zu, Eintrag geblieben), nimmt das neue Overlay ihn ein.
    if (d > k) ovReplace(ovMit(history.state, o.tiefe), "");
    else ovPush(ovMit(history.state, o.tiefe), "", location.href);
    ovAktuell = o.tiefe;
    ovStapel.push(o);
  }
  function ovNachtragen() { ovNachher.splice(0).forEach((o) => { if (o.offen) ovEintragen(o); }); }
  function ovZurueck() {
    if (ovPlan || ovVerborgen) return;
    ovPlan = setTimeout(() => {
      ovPlan = null;
      if (ovVerborgen || ovWarten || ovImZurueck) return;
      if (ovSeiteGeht && Date.now() - ovSeiteGeht < 3000) return;
      const n = ovTiefe(history.state) - ovOben();
      if (n <= 0) return;
      ovWarten = true;
      history.go(-n);
    }, 0);
  }
  // Die Adresse, die die Seite während des Overlays gesetzt hat, gilt auch für den Eintrag darunter.
  function ovSeiteSetzen(d) {
    if (!ovSeite) return;
    ovReplace(ovMit(ovSeite.state, d), "", ovSeite.url);
    if (!d) ovSeite = null;
  }

  /* Ein Overlay anmelden: schliessen() schließt es wegen Zurück (false = bleibt offen). Zurück kommt { zu }, das der
     Aufrufer beim Schließen auf anderem Weg ruft (mehrfach unschädlich). */
  function overlayVerlauf(schliessen) {
    const o = { tiefe: 0, schliessen, offen: true };
    if (ovWarten || ovImZurueck) ovNachher.push(o);
    else ovEintragen(o);
    return {
      zu() {
        if (!o.offen) return;
        o.offen = false;
        const i = ovNachher.indexOf(o);
        if (i >= 0) { ovNachher.splice(i, 1); return; }
        const j = ovStapel.indexOf(o);
        if (j < 0) return;                       // von einer neuen Seite abgelöst
        ovStapel.splice(j, 1);
        ovZurueck();
      },
    };
  }

  /* Ein <dialog> anmelden (nach showModal). Ein Folgedialog im selben Element (S.dialog bei offenem #dlg) behält den
     Eintrag; erst das endgültige Schließen nimmt ihn heraus. */
  const dlgVerlauf = new WeakMap();
  function dialogVerlauf(dlg) {
    if (!dlg || dlgVerlauf.has(dlg)) return;
    const h = overlayVerlauf(() => {
      const ev = new Event("cancel", { cancelable: true });
      dlg.dispatchEvent(ev);
      if (ev.defaultPrevented) return false;
      dlgVerlauf.delete(dlg);
      dlg.close();
      return true;
    });
    dlgVerlauf.set(dlg, h);
    const zu = () => {
      if (dlg.open) return;                      // gleich wieder geöffnet (Folgedialog)
      dlg.removeEventListener("close", zu);
      if (dlgVerlauf.get(dlg) === h) dlgVerlauf.delete(dlg);
      h.zu();
    };
    dlg.addEventListener("close", zu);
  }

  /* Ein Overlay, das eine Klasse öffnet (Schubladen, Seitenleiste der Karte): offen, solange el die Klasse trägt und
     gilt() stimmt (etwa: die Leiste ist gerade eine Schublade). schliessen() schließt es so, wie es die Seite selbst tut. */
  function klassenVerlauf(el, klasse, schliessen, gilt) {
    if (!el) return;
    let h = null;
    const pruefen = () => {
      const auf = el.classList.contains(klasse) && (!gilt || gilt());
      if (auf && !h) {
        const neu = overlayVerlauf(() => { if (h === neu) h = null; schliessen(); return !el.classList.contains(klasse); });
        h = neu;
      } else if (!auf && h) {
        const alt = h;
        h = null;
        alt.zu();
      }
    };
    new MutationObserver(pruefen).observe(el, { attributes: true, attributeFilter: ["class"] });
    pruefen();
  }

  window.addEventListener("popstate", (e) => {
    const d = ovTiefe(e.state);
    const vorher = ovAktuell;
    ovAktuell = d;
    // Den Code der Seite (Strömipedia, öffentliche Seiten) geht der Schritt nur an, wenn sich die Adresse wirklich ändert.
    const durchlassen = () => {
      if (location.href === ovGesehen) e.stopImmediatePropagation();
      else ovGesehen = location.href;
    };
    if (ovWarten) {                                   // unser eigener Schritt zurück
      if (d > ovOben()) { e.stopImmediatePropagation(); history.go(-(d - ovOben())); return; }   // noch nicht unten
      ovWarten = false;
      ovSeiteSetzen(d);
      durchlassen();
      ovNachtragen();
      return;
    }
    const k = ovOben();
    if (d > k) {                                      // toter Eintrag (Vor, oder Zurück auf ein schon geschlossenes Overlay)
      e.stopImmediatePropagation();
      ovWarten = true;
      history.go(-(d - k));
      return;
    }
    if (d === k) {
      // Nur ein toter Eintrag lag dazwischen (Overlay zu, während die Seite schon ging): weiter zurück, als wäre er nicht da.
      if (vorher > d) { e.stopImmediatePropagation(); history.back(); return; }
      durchlassen();
      return;
    }
    // Zurück: die Overlays über d schließen, das oberste zuerst; ein Dialog kann es ablehnen (cancel wie Esc).
    ovSeiteSetzen(d);
    durchlassen();
    ovImZurueck = true;
    const bleiben = [];
    try {
      while (ovStapel.length && ovOben() > d) {
        const o = ovStapel.pop();
        if (o.schliessen() === false) { bleiben.push(o); break; }
        o.offen = false;
      }
    } finally {
      ovImZurueck = false;
    }
    // Abgelehnt: das Overlay (und was darunter über d lag) bekommt seinen Eintrag zurück.
    const wieder = ovStapel.filter((o) => o.tiefe > d).concat(bleiben);
    ovStapel.splice(ovStapel.length - (wieder.length - bleiben.length), wieder.length - bleiben.length);
    wieder.forEach(ovEintragen);
    ovNachtragen();
  });
  window.addEventListener("hashchange", () => { ovGesehen = location.href; });
  window.addEventListener("beforeunload", () => { ovSeiteGeht = Date.now(); });
  window.addEventListener("pagehide", () => { ovVerborgen = true; });
  window.addEventListener("pageshow", (e) => {
    ovVerborgen = false;
    ovSeiteGeht = 0;
    if (!e.persisted) return;
    ovAktuell = ovTiefe(history.state);
    ovGesehen = location.href;
    // Aus dem bfcache zurück: Was beim Verlassen schloss (Schubladen), hat seinen Eintrag noch – den verlassen wir.
    const n = ovTiefe(history.state) - ovOben();
    if (n > 0) { ovWarten = true; history.go(-n); }
  });
  history.pushState = function (state, titel, url) {
    if (ovTiefe(history.state)) {
      // Seitenwechsel aus einem offenen Overlay heraus: Die neue Seite nimmt dessen Eintrag ein; die offenen Overlays
      // schließen danach ohne eigenen Schritt zurück.
      ovStapel.splice(0);
      ovNachher.splice(0);
      ovSeite = null;
      ovReplace(ovOhne(state), titel, url);
    } else {
      ovPush(state, titel, url);
    }
    ovAktuell = 0;
    ovGesehen = location.href;
  };
  history.replaceState = function (state, titel, url) {
    const d = ovTiefe(history.state);
    if (d) {
      ovReplace(ovMit(ovOhne(state), d), titel, url);
      ovSeite = { state: ovOhne(state), url: location.href };
    } else {
      ovReplace(state, titel, url);
    }
    ovGesehen = location.href;
  };

  /* Dialog mit HTML-Inhalt. onOpen erhält das Dialog-Element. */
  function dialog(html, onOpen) {
    const dlg = document.getElementById("dlg");
    const body = document.getElementById("dlg-body");
    body.innerHTML = html;
    body.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dlg.close()));
    // Der Titel benennt den Dialog – so sagt die Vorlesehilfe beim Öffnen, worum es geht.
    const titel = body.querySelector("h2");
    if (titel) { titel.id = titel.id || "dlg-titel"; dlg.setAttribute("aria-labelledby", titel.id); }
    else dlg.removeAttribute("aria-labelledby");
    // showModal() setzt den Fokus selbst aufs erste Bedienelement – auf dem Telefon meist ein Textfeld, und dann ging
    // sofort die Bildschirmtastatur auf und verdeckte den halben Dialog. Am Touchgerät bekommt deshalb der Titel den
    // Fokus (autofocus; ein autofocus am <dialog> selbst übergeht Chromium); die Tastatur kommt erst, wenn man ins
    // Feld tippt. Mit Maus und Tastatur bleibt es beim ersten Feld. Wer ein Feld ausdrücklich mit autofocus versieht
    // (Kommentar und Antwort im Wiki: Der Dialog ist nur zum Schreiben da), behält es – auch am Touchgerät.
    if (titel && window.matchMedia("(pointer: coarse)").matches && !body.querySelector("[autofocus]")) {
      titel.tabIndex = -1; titel.autofocus = true;
    }
    // Erst öffnen, dann onOpen: Ein geschlossener Dialog ist display:none – focus() und
    // scrollIntoView() darin liefen ins Leere, und der Fokus landete auf dem ersten Element.
    if (!dlg.open) dlg.showModal();
    dialogVerlauf(dlg);
    // Rollt der Inhalt (lange Dialoge wie „Nutzer bearbeiten“), zählt Chromium den rollenden Körper selbst als erstes
    // Bedienelement und setzt den Fokus dorthin statt aufs erste Feld – dann eben von Hand aufs erste Feld.
    // Ebenso, wenn es das „i“ hinter dem Titel oder einem Feld traf: Der Fokus gehört aufs erste Bedienelement, und die
    // Info soll nicht beim Öffnen von selbst aufgehen.
    const ae = document.activeElement;
    if (ae === body || (ae && ae.closest && body.contains(ae) && ae.closest(".info"))) {
      const erstes = [...body.querySelectorAll("input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), a[href], summary")]
        .find((el) => !el.closest(".info"));
      if (erstes) erstes.focus();
    }
    if (onOpen) onOpen(dlg, body);
    return dlg;
  }

  /* Rückfrage in einem eigenen Dialog – so bleibt ein bereits offener Dialog (z. B. der Versionsverlauf) darunter stehen,
     statt mit geschlossen zu werden. neinLabel: wenn „Abbrechen“ missverständlich wäre (die Hauptaktion heißt selbst
     „… abbrechen“). Der Titel ist die Frage selbst („Ordner „X“ löschen?“, UI/UX vor dem Merge A4) – aus dem Text
     genommen, der Rest steht darunter; opt.titel setzt ihn ausdrücklich, opt.html ersetzt den Text darunter (fertiges
     HTML, Eingaben mit esc). Endgültiges (Vorgabe) bestätigt der rote Rahmenknopf „btn danger“; opt.endgueltig: false
     für Rückfragen, bei denen nichts verloren geht („Senden“, „Wiederherstellen“, „Zuordnen“, „Entziehen“) – dann ist
     die Hauptaktion der gewöhnliche rote Knopf. opt.fokus: "nein" setzt den Fokus ausdrücklich auf „Abbrechen“ (sonst
     nimmt der Browser das erste Bedienelement – ebenfalls „Abbrechen“). */
  function frageTeilen(text) {
    const t = String(text || "").trim();
    const ende = t.indexOf("?");
    if (ende < 0) return { titel: t || "Bist du sicher?", rest: "" };
    const satz = t.lastIndexOf(". ", ende);
    const anfang = satz < 0 ? 0 : satz + 2;
    return { titel: t.slice(anfang, ende + 1), rest: `${t.slice(0, anfang)}${t.slice(ende + 1)}`.trim() };
  }
  function confirm(text, okLabel, neinLabel, opt = {}) {
    return new Promise((resolve) => {
      const teile = frageTeilen(text);
      const titel = opt.titel || teile.titel;
      const unten = opt.html !== undefined ? opt.html : (opt.titel ? (text ? `<p>${esc(text)}</p>` : "") : (teile.rest ? `<p>${esc(teile.rest)}</p>` : ""));
      const dlg = document.createElement("dialog");
      dlg.setAttribute("aria-labelledby", "c-titel");
      dlg.innerHTML = `<div class="dlg-body"><h2 id="c-titel">${esc(titel)}</h2>${unten}
        <div class="dlg-actions"><button class="btn secondary" id="c-no" type="button">${esc(neinLabel || "Abbrechen")}</button>
        <button class="${opt.endgueltig === false ? "btn" : "btn danger"}" id="c-ok" type="button">${esc(okLabel || "Löschen")}</button></div></div>`;
      document.body.appendChild(dlg);
      const done = (v) => { resolve(v); dlg.close(); };
      dlg.querySelector("#c-ok").onclick = () => done(true);
      dlg.querySelector("#c-no").onclick = () => done(false);
      dlg.addEventListener("close", () => { resolve(false); dlg.remove(); });
      dlg.showModal();
      dialogVerlauf(dlg);
      if (opt.fokus === "nein") dlg.querySelector("#c-no").focus();
    });
  }

  function fmtDate(iso, withTime) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const o = { day: "2-digit", month: "2-digit", year: "numeric" };
    if (withTime) { o.hour = "2-digit"; o.minute = "2-digit"; }
    return d.toLocaleString("de-DE", o);
  }

  function fmtCoord(lat, lon) {
    if (lat == null || lon == null) return "";
    return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  }

  const CAT = { seil: "Seiltechnik", wasser: "Übungsgewässer", sonstiges: "Sonstiges" };

  /* Was beim Abmelden aus dem Browser verschwindet: Entwürfe, die Stoppuhr einer Prüfung –
     alles, was Inhalt trägt. Am gemeinsamen Rechner fände sonst die nächste Person den
     ungespeicherten Text ihres Vorgängers im Entwurfsbalken. Einstellungen ohne Inhalt
     (Breite der Seitenleiste, zugeklapptes Verzeichnis) bleiben; sie verraten nichts. Die
     Ansichtswahl der Prüfungsseite teilt den Vorsatz „pruef:“ und geht mit – ein Klick stellt
     sie wieder her. */
  const BLEIBT = new Set(["stroemis-sidebar", "stroemis-toc-aus"]);
  function ablageLeeren() {
    for (const speicher of [window.localStorage, window.sessionStorage]) {
      try {
        const weg = [];
        for (let i = 0; i < speicher.length; i++) {
          const k = speicher.key(i);
          if (k && /^(stroemis-|pruef:)/.test(k) && !BLEIBT.has(k)) weg.push(k);
        }
        weg.forEach((k) => speicher.removeItem(k));
      } catch (e) { /* kein Speicher (privater Modus, abgeschaltet) – dann gibt es auch nichts zu löschen */ }
    }
  }

  document.addEventListener("click", async (e) => {
    /* Nur der Knopf in der Hauptnavigation (base.html) meldet ab. Geprüft wurde vorher allein
       die id – und ein <span id="logout"> im Artikel warf damit jeden hinaus, der es anklickte.
       Die Reinigung (markdown.js, RAHMEN_ID) lässt die id im Inhalt inzwischen nicht mehr zu;
       das hier ist der zweite Riegel. */
    const knopf = e.target.closest && e.target.closest("button#logout, a#logout");
    if (!knopf || !knopf.closest("header nav")) return;
    try { await api("/api/auth/logout", { method: "POST", body: {} }); }
    catch (err) { toast("Abmelden hat nicht geklappt: " + err.message, true); return; }
    ablageLeeren();
    location.href = "/login";
  });

  /* Hauptnavigation, die nicht in die Bauchbinde passt (Telefon, Tablet hochkant, Konten mit allen Modulen): Vorher
     rollte die Leiste unsichtbar seitlich, und „Profil“ und „Abmelden“ lagen ohne jeden Hinweis hinter dem Rand.
     Jetzt weicht Schritt für Schritt, was entbehrlich ist – erst der eigene Name, dann der Schriftzug neben dem
     Zeichen. Reicht das nicht, wandern die hinteren Punkte (zuerst Abmelden, dann Profil, dann die Module von rechts)
     in das Menü „Mehr“ am rechten Rand („Priority+“); der gerade aktive Punkt bleibt immer stehen. Neu geordnet
     wird bei jeder Breitenänderung und wenn die Hausschrift nachgeladen ist. Ohne Skript rollt die Leiste wie bisher. */
  (function kopfleiste() {
    const kopf = document.querySelector("header.bauchbinde");
    const nav = kopf && kopf.querySelector("nav.nav");
    const mehr = nav && nav.querySelector(".nav-mehr");
    if (!mehr) return;
    const knopf = mehr.querySelector(".nav-mehr-knopf");
    const liste = mehr.querySelector(".nav-mehr-liste");
    const punkte = Array.from(nav.children).filter((el) => el !== mehr);
    // Ohne Spielraum: Schon ein überstehendes Pixel (gerundete Breiten) schickt den hintersten Punkt ins Menü – sonst
    // lief er bei 375 px 1 px über den Rand (Browserprüfung der Umbenennung, B2). Den Abstand zum Fensterrand hält
    // der rechte Rand der Bauchbinde (app.css, mindestens 8 px).
    const zuBreit = () => nav.scrollWidth > nav.clientWidth;
    const zu = () => { liste.hidden = true; knopf.setAttribute("aria-expanded", "false"); };
    let breite = -1;
    function anordnen() {
      zu();
      punkte.forEach((p) => nav.insertBefore(p, mehr));
      kopf.classList.remove("nav-eng", "nav-enger");
      mehr.hidden = true;
      nav.scrollLeft = 0;
      if (!zuBreit()) return;
      kopf.classList.add("nav-eng");                 // ohne den eigenen Namen
      if (!zuBreit()) return;
      kopf.classList.add("nav-enger");               // ohne den Schriftzug neben dem Zeichen
      if (!zuBreit()) return;
      mehr.hidden = false;
      for (let i = punkte.length - 1; i >= 0 && zuBreit(); i--) {
        if (!punkte[i].classList.contains("active")) liste.prepend(punkte[i]);
      }
    }
    knopf.addEventListener("click", () => {
      const auf = liste.hidden;
      liste.hidden = !auf;
      knopf.setAttribute("aria-expanded", String(auf));
    });
    document.addEventListener("click", (e) => { if (!liste.hidden && !mehr.contains(e.target)) zu(); });
    // Schon beim Aufsetzen daneben schließen, nicht erst beim Tippen: Ein Wisch oder Zug auf der Karte erzeugt kein
    // „click“, und das Menü stand dann weiter über der Seite. Ebenso, sobald die Seite rollt.
    document.addEventListener("pointerdown", (e) => { if (!liste.hidden && !mehr.contains(e.target)) zu(); }, true);
    window.addEventListener("scroll", () => { if (!liste.hidden) zu(); }, { passive: true });
    // Wer mit der Tastatur aus dem Menü herausgeht, lässt es nicht offen stehen.
    mehr.addEventListener("focusout", (e) => { if (e.relatedTarget && !mehr.contains(e.relatedTarget)) zu(); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || liste.hidden) return;
      zu();
      if (mehr.contains(document.activeElement)) knopf.focus();
    });
    // Nur die Breite zählt: Die Höhe ändert sich am Telefon schon beim Rollen (Adressleiste) und mit der Tastatur.
    const pruefen = () => { const b = kopf.clientWidth; if (b !== breite) { breite = b; anordnen(); } };
    if (window.ResizeObserver) new ResizeObserver(pruefen).observe(kopf);
    else window.addEventListener("resize", pruefen);
    pruefen();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(anordnen);
  })();

  /* Sichtbarer Ausschnitt: Auf dem iPhone nimmt die Tastatur die halbe Höhe, aber 100dvh weiß davon
     nichts. Ein Dialog blieb deshalb bildschirmhoch, sein Inhalt hatte nichts zu rollen, und iOS
     schob stattdessen den ganzen Ausschnitt hin und her – „Scrollen geht nicht mehr“. Die beiden
     Variablen tragen Höhe und Versatz des tatsächlich sichtbaren Bereichs, die Klasse „tastatur“
     sagt, dass er deutlich kleiner ist als das Fenster; app.css begrenzt offene Dialoge damit.
     Android (interactive-widget=resizes-content) verkleinert das Fenster selbst – dort greift nichts. */
  (function sichtbarerAusschnitt() {
    const vv = window.visualViewport;
    if (!vv) return;
    const root = document.documentElement;
    let tick = null, warTastatur = false;
    const setzen = () => {
      tick = null;
      root.style.setProperty("--vv-h", Math.round(vv.height) + "px");
      root.style.setProperty("--vv-top", Math.round(vv.offsetTop) + "px");
      // Beim Hineinzoomen schrumpft der Ausschnitt ebenfalls – das ist keine Tastatur.
      const tastatur = vv.scale <= 1.01 && vv.height < window.innerHeight - 100;
      root.classList.toggle("tastatur", tastatur);
      // Gerade aufgegangen: Das Feld mit dem Fokus in den nun kleineren Dialog holen – iOS hat es
      // vorher nur im großen Ausschnitt sichtbar gemacht.
      if (tastatur && !warTastatur) {
        const ae = document.activeElement;
        if (ae && ae.closest && ae.closest("dialog[open]") && (ae.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName))) {
          try { ae.scrollIntoView({ block: "center", inline: "nearest" }); } catch (e) { /* egal */ }
        }
      }
      warTastatur = tastatur;
    };
    const planen = () => { if (tick == null) tick = requestAnimationFrame(setzen); };
    vv.addEventListener("resize", planen);
    vv.addEventListener("scroll", planen);
    window.addEventListener("resize", planen);
    setzen();
  })();

  /* --- Menüs: ein Baustein für alle Module (UI/UX vor dem Merge, A3/D1) --------------------------------------------
     Vorher gab es drei Bauarten mit je eigener Logik (details.mat-menue der Materialablage, details.zeilenmenue der
     Leitstelle und Riegenkarten, die schwebenden Menüs der Strömipedia). Jetzt eine: S.menue() zeichnet
       <details class="menue"><summary class="btn secondary small" aria-haspopup="menu">Mehr</summary>
         <div class="menue-liste" role="menu"> Einträge: <a role="menuitem"> oder <button role="menuitem"> </div></details>
     und das Verhalten hier gilt für jedes details.menue und jedes schwebende Menü (S.menueSchwebend): Nur eins ist
     offen; ein Klick daneben oder auf einen Eintrag schließt, ebenso Esc (Fokus zurück auf den Menüknopf – in einem
     Dialog schließt Esc nur das Menü) und Tab hinaus (focusout); ↑/↓, Pos1/Ende wandern durch die Einträge, ↓ auf dem
     Menüknopf öffnet. Mit der Tastatur geöffnet, steht der Fokus gleich auf dem ersten Eintrag. Die Liste bleibt im
     Bild: waagerecht rückt sie ein (auf einem Doppelbildschirm in die eigene Hälfte), senkrecht öffnet sie nach oben,
     wenn unten der Platz fehlt, sonst rollt sie in sich. Das Aussehen kommt von der Klasse „menue“ (app.css); bis zur
     Zusammenführung tragen die Menüs zusätzlich ihre bisherige Klasse (art: "mat-menue" bzw. "zeilenmenue").
     Bleibt nur EIN Eintrag, zeichnet S.menue einen grauen Knopf statt eines Menüs (Nutzer 27.10.2026). */
  const MENUE_EINTRAG = "a[href], button:not([disabled])";
  const menueOffen = () => [...document.querySelectorAll("details.menue[open], .menue-schwebend")];
  const menueListe = (m) => (m.matches(".menue-schwebend") ? m : m.querySelector(":scope > .menue-liste"));
  const menueEintraege = (m) => {
    const l = menueListe(m);
    return l ? [...l.querySelectorAll(MENUE_EINTRAG)].filter((x) => x.getClientRects().length) : [];
  };
  const menueSchwebendZu = new WeakMap();      // schwebendes Menü → schließen(fokusZurueck)
  function menueZu(m, fokus) {
    if (m.matches(".menue-schwebend")) { const zu = menueSchwebendZu.get(m); if (zu) zu(fokus); return; }
    m.open = false;
    if (fokus) m.querySelector("summary").focus();
  }
  // Die Grenzen des Bilds: das Fenster unter der Kopfleiste – auf einem Doppelbildschirm die Hälfte, in der der Knopf steht.
  function menueRahmen(knopf) {
    let links = 0;
    let rechts = document.documentElement.clientWidth;
    const haelften = window.viewport && window.viewport.segments;
    if (haelften && haelften.length > 1) {
      const h = Array.from(haelften).find((x) => knopf.left >= x.x - 1 && knopf.left < x.x + x.width);
      if (h) { links = h.x; rechts = Math.min(rechts, h.x + h.width); }
    }
    const kopf = document.querySelector("header.bauchbinde");
    const oben = Math.max(0, kopf ? kopf.getBoundingClientRect().bottom : 0);
    return { links: links + 8, rechts: rechts - 8, oben: oben + 8, unten: (window.visualViewport ? window.visualViewport.height : window.innerHeight) - 8 };
  }
  function menueAusrichten(m) {
    const liste = menueListe(m);
    if (!liste) return;
    liste.style.left = ""; liste.style.right = ""; liste.style.top = ""; liste.style.bottom = "";
    liste.style.maxHeight = ""; liste.style.overflowY = "";
    const knopf = m.getBoundingClientRect();
    const r = menueRahmen(knopf);
    const breite = liste.offsetWidth;
    const links = Math.max(r.links, Math.min(knopf.right - breite, r.rechts - breite));
    liste.style.right = "auto";
    liste.style.left = `${Math.round(links - knopf.left)}px`;
    const hoehe = liste.offsetHeight;
    const unten = r.unten - knopf.bottom - 6;
    const oben = knopf.top - r.oben - 6;
    if (hoehe <= unten) return;
    if (hoehe <= oben || oben > unten) { liste.style.top = "auto"; liste.style.bottom = "calc(100% + 6px)"; }
    if (hoehe > Math.max(oben, unten)) { liste.style.maxHeight = `${Math.max(120, Math.floor(Math.max(oben, unten)))}px`; liste.style.overflowY = "auto"; }
  }
  function menueRollen(m) {
    const liste = menueListe(m);
    if (!liste) return;
    liste.setAttribute("role", "menu");
    liste.querySelectorAll(MENUE_EINTRAG).forEach((x) => x.setAttribute("role", "menuitem"));
  }
  let menueTaste = null;                     // der Menüknopf, der gerade per Tastatur geöffnet wird
  document.addEventListener("toggle", (e) => {
    const m = e.target;
    if (!(m instanceof HTMLDetailsElement) || !m.classList.contains("menue") || !m.open) return;
    menueOffen().forEach((x) => { if (x !== m && !x.contains(m)) menueZu(x, false); });
    menueRollen(m);
    menueAusrichten(m);
    if (menueTaste === m) { menueTaste = null; const erste = menueEintraege(m)[0]; if (erste) erste.focus(); }
  }, true);
  document.addEventListener("click", (e) => {
    menueOffen().forEach((m) => {
      // (Der Klick, der ein schwebendes Menü eben geöffnet hat, kommt danach hier an – an seinem Knopf bleibt es offen.)
      const daneben = !m.contains(e.target) && !(m.menueAnker && m.menueAnker.contains(e.target));
      if (daneben || e.target.closest(".menue-liste a, .menue-liste button, .menue-schwebend a, .menue-schwebend button")) menueZu(m, false);
    });
  });
  // Schwebende Menüs schließen schon beim Aufsetzen daneben; ein Tipp auf ihren Knopf schließt nur (öffnet nicht neu).
  document.addEventListener("pointerdown", (e) => {
    document.querySelectorAll(".menue-schwebend").forEach((m) => {
      if (m.contains(e.target)) return;
      const anker = m.menueAnker;
      if (anker && anker.contains(e.target)) anker.menueGeradeZu = Date.now();
      menueZu(m, false);
    });
  }, true);
  document.addEventListener("focusout", (e) => {
    const m = e.target.closest && e.target.closest("details.menue[open], .menue-schwebend");
    if (m && e.relatedTarget && !m.contains(e.relatedTarget)) menueZu(m, false);
  });
  document.addEventListener("keydown", (e) => {
    const ae = document.activeElement;
    const knopf = ae && ae.matches && ae.matches("details.menue > summary") ? ae : null;
    if (knopf && (e.key === "Enter" || e.key === " ")) { menueTaste = knopf.parentElement; return; }
    if (knopf && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      const m = knopf.parentElement;
      if (!m.open) { menueTaste = null; m.open = true; }
      const liste = menueEintraege(m);
      if (liste.length) liste[e.key === "ArrowDown" ? 0 : liste.length - 1].focus();
      return;
    }
    const offen = menueOffen();
    if (!offen.length) return;
    if (e.key === "Escape") {
      const m = offen.find((x) => x.contains(ae)) || offen.find((x) => x.menueAnker && x.menueAnker === ae) || offen[offen.length - 1];
      menueZu(m, true);
      e.preventDefault();
      if (m.closest("dialog") || (m.menueAnker && m.menueAnker.closest("dialog"))) e.stopPropagation();
      return;
    }
    const m = offen.find((x) => menueListe(x) && menueListe(x).contains(ae));
    if (!m) return;
    // Tab aus einem schwebenden Menü: zurück auf seinen Knopf, von dort geht Tab weiter.
    if (e.key === "Tab" && m.matches(".menue-schwebend")) { menueZu(m, true); return; }
    const liste = menueEintraege(m);
    const at = liste.indexOf(ae);
    const ziel = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: liste.length - 1 }[e.key];
    if (ziel === undefined) return;
    e.preventDefault();
    if (liste.length) liste[(ziel + liste.length) % liste.length].focus();
  });
  window.addEventListener("resize", () => document.querySelectorAll("details.menue[open]").forEach(menueAusrichten));

  /* Markup eines Menüs. opt: { text: Beschriftung des Knopfs (Vorgabe „Mehr“), klein: false für einen normal großen
     Knopf, art: bisherige Klasse ("mat-menue" | "zeilenmenue"), links: Einträge als <a> (Aussehen der Materialablage),
     eintraege: [{ text, satz?, href?, attrs?, kurz? }] } – attrs ist fertiges Attribut-HTML (data-act …), satz eine kurze
     Erklärung unter dem Eintrag (höchstens eine Zeile am Telefon), href ein Ziel (sonst ein Knopf bzw. href="#").
     Leere Einträge (false, null) fallen weg; { trenner: true } zieht einen Strich vor die folgenden. Bleibt ein Eintrag,
     wird es ein Knopf mit dessen Text. */
  function menue(opt) {
    const roh = (opt.eintraege || []).filter(Boolean);
    // Ein Strich nur zwischen Einträgen (fällt am Anfang, am Ende und doppelt weg).
    const alle = roh.filter((x, i) => !x.trenner || (roh.slice(0, i).some((y) => !y.trenner) && roh.slice(i + 1).some((y) => !y.trenner)
      && !(roh[i + 1] && roh[i + 1].trenner)));
    const eintraege = alle.filter((x) => !x.trenner);
    if (!eintraege.length) return "";
    const klein = opt.klein === false ? "" : " small";
    const attrs = (x) => (x.attrs ? ` ${x.attrs}` : "");
    if (eintraege.length === 1) {
      const x = eintraege[0];
      // kurz: ein kürzerer Knopftext, wo die Spalte schmal ist (der volle Text bleibt der Name fürs Vorlesen).
      const name = x.kurz ? ` aria-label="${esc(x.text)}"` : "";
      return x.href ? `<a class="btn secondary${klein}" href="${esc(x.href)}"${name}${attrs(x)}>${esc(x.kurz || x.text)}</a>`
        : `<button type="button" class="btn secondary${klein}"${name}${attrs(x)}>${esc(x.kurz || x.text)}</button>`;
    }
    const art = opt.art ? ` ${opt.art}` : "";
    const eintrag = (x) => {
      if (x.trenner) return `<hr class="menue-trenner${opt.art ? ` ${opt.art}-trenner` : ""}">`;
      const inhalt = opt.links ? `<strong>${esc(x.text)}</strong>${x.satz ? `<span>${esc(x.satz)}</span>` : ""}` : esc(x.text);
      return x.href || opt.links ? `<a href="${esc(x.href || "#")}" role="menuitem"${attrs(x)}>${inhalt}</a>`
        : `<button type="button" role="menuitem"${attrs(x)}>${inhalt}</button>`;
    };
    return `<details class="menue${art}"><summary class="btn secondary${klein}" aria-haspopup="menu">${esc(opt.text || "Mehr")}</summary>`
      + `<div class="menue-liste${opt.art ? ` ${opt.art}-liste` : ""}" role="menu">${alle.map(eintrag).join("")}</div></details>`;
  }

  /* Ein schwebendes Menü an einem Knopf (Strömipedia: „⋯“ am Seitenbaum, an der Baumzeile, im Seitenkopf): box ist ein
     fertiges Element mit Knöpfen; es kommt ans Ende der Seite (sonst schnitte die rollende Seitenleiste es ab), steht
     unter dem Knopf und im Bild, bekommt den Fokus auf den ersten Eintrag und dasselbe Verhalten wie jedes Menü.
     Zurück kommt schliessen(fokusZurueck). */
  function menueSchwebend(anker, box) {
    if (anker.menueGeradeZu && Date.now() - anker.menueGeradeZu < 800) { anker.menueGeradeZu = 0; return () => {}; }
    box.classList.add("menue", "menue-schwebend");
    box.menueAnker = anker;
    document.body.appendChild(box);
    menueOffen().forEach((x) => { if (x !== box) menueZu(x, false); });
    menueRollen(box);
    const a = anker.getBoundingClientRect();
    const r = menueRahmen(a);
    box.style.left = `${Math.max(r.links, Math.min(r.rechts - box.offsetWidth, a.left))}px`;
    // Unter dem Knopf, wenn es dort passt, sonst darüber; passt es nirgends (Telefon quer), dort, wo mehr Platz ist,
    // und die Liste rollt in sich.
    const unten = r.unten - a.bottom - 4;
    const oben = a.top - r.oben - 4;
    const hoehe = box.offsetHeight;
    const hoch = hoehe > unten && oben > unten;
    if (hoehe > Math.max(unten, oben)) { box.style.maxHeight = `${Math.max(120, Math.floor(Math.max(unten, oben)))}px`; box.style.overflowY = "auto"; }
    box.style.top = `${window.scrollY + (hoch ? Math.max(r.oben, a.top - 4 - box.offsetHeight) : a.bottom + 4)}px`;
    const schliessen = (fokus) => {
      if (!box.isConnected) return;
      box.remove();
      if (fokus !== false && anker && anker.focus) anker.focus();
    };
    menueSchwebendZu.set(box, schliessen);
    setTimeout(() => { const erste = menueEintraege(box)[0]; if (erste) erste.focus(); }, 0);
    return schliessen;
  }

  /* Info zu einem Begriff (designsprache „Info-Symbol „i““; seit 27.10.2026 app-weit, vorher infoKnopf in material.js):
     ein gekringeltes „i“ hinter dem Begriff statt eines Erklärsatzes darunter. Ein Knopf (aria-label „Info zu …“,
     aria-expanded, aria-describedby auf die Info); die Info (role="tooltip", darf Links enthalten – html ist fertiges
     HTML ohne Eingaben) erscheint beim Darüberfahren mit der Maus, bei Tastaturfokus und beim Antippen; Esc, ein Tipp
     daneben oder der Fokus woanders schließt. Aussehen in app.css (.info), dasselbe Markup erzeugt das Jinja-Makro
     „info“ (templates/_makros.html). */
  let infoZahl = 0;
  function info(thema, html) {
    const id = `info-${++infoZahl}`;
    return `<span class="info"><button type="button" class="info-knopf" aria-label="Info zu ${esc(thema)}" aria-expanded="false"
      aria-controls="${id}" aria-describedby="${id}"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="8.6"
      fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="10" cy="6.1" r="1.25" fill="currentColor"/><path d="M10 9v5.6" stroke="currentColor"
      stroke-width="2" stroke-linecap="round"/></svg></button><span class="info-text" role="tooltip" id="${id}" hidden>${html}</span></span>`;
  }

  /* Verhalten der Info-Symbole, einmal je Seite für alle (auch später gezeichnete): offen, solange die Maus über „i“
     oder Info steht, der Fokus darin ist oder sie angetippt wurde (fest – bis zum nächsten Tipp auf „i“, daneben oder
     Esc). Die Info steht unter dem „i“ und rückt ins Bild – in einem Dialog in dessen Inhalt, der sie sonst abschnitte. */
  const infoTeil = (w, sel) => (w ? w.querySelector(sel) : null);
  const infoOffen = (w) => { const t = infoTeil(w, ".info-text"); return Boolean(t && !t.hidden); };
  function infoZeigen(w, an, fest) {
    const k = infoTeil(w, ".info-knopf");
    const t = infoTeil(w, ".info-text");
    if (!k || !t) return;
    w.classList.toggle("fest", Boolean(an && (fest || w.classList.contains("fest"))));
    if (!an) w.classList.remove("fest");
    k.setAttribute("aria-expanded", String(an));
    t.hidden = !an;
    if (!an) return;
    const rahmen = w.closest("dialog .dlg-body, dialog");
    const r0 = rahmen ? rahmen.getBoundingClientRect() : null;
    const links = (r0 ? r0.left : 0) + 8;
    const rechts = (r0 ? r0.left + rahmen.clientWidth : document.documentElement.clientWidth) - 8;
    t.style.maxWidth = r0 ? `${Math.max(160, Math.min(320, Math.floor(rechts - links)))}px` : "";
    t.style.left = "0px";
    const r = t.getBoundingClientRect();
    const verschub = r.right > rechts ? rechts - r.right : 0;
    t.style.left = `${Math.round(Math.max(verschub, links - r.left))}px`;
  }
  const infoAlleZu = (ausser) => document.querySelectorAll(".info").forEach((w) => { if (w !== ausser && infoOffen(w)) infoZeigen(w, false); });
  document.addEventListener("click", (e) => {
    const k = e.target.closest && e.target.closest(".info-knopf");
    const w = e.target.closest && e.target.closest(".info");
    infoAlleZu(w);
    // Ein Tipp in die Info (nicht auf einen Link darin) wirkt nicht auf das, worin das „i“ steht – ein Haken in einem
    // <label> kippte sonst, ein <summary> klappte auf oder zu.
    if (!k && w && e.target.closest(".info-text") && !e.target.closest("a[href]")) e.preventDefault();
    if (!k || !w) return;
    e.preventDefault();
    // Mit der Maus ist die Info beim Klick schon offen (Darüberfahren): Der Klick hält sie fest, ein zweiter schließt.
    infoZeigen(w, !(infoOffen(w) && w.classList.contains("fest")), true);
  });
  document.addEventListener("pointerover", (e) => {
    if (e.pointerType !== "mouse") return;
    const w = e.target.closest && e.target.closest(".info");
    if (w && !infoOffen(w)) { infoAlleZu(w); infoZeigen(w, true); }
  });
  document.addEventListener("pointerout", (e) => {
    if (e.pointerType !== "mouse") return;
    const w = e.target.closest && e.target.closest(".info");
    if (!w || w.contains(e.relatedTarget) || w.classList.contains("fest") || w.contains(document.activeElement)) return;
    infoZeigen(w, false);
  });
  document.addEventListener("focusin", (e) => {
    const w = e.target.closest && e.target.closest(".info");
    infoAlleZu(w);
    // Nach Esc kommt der Fokus auf das „i“ zurück – ohne die Info gleich wieder zu öffnen.
    if (w && w.dataset.esc) { delete w.dataset.esc; return; }
    if (w && e.target.matches(".info-knopf:focus-visible")) infoZeigen(w, true);
  });
  document.addEventListener("focusout", (e) => {
    const w = e.target.closest && e.target.closest(".info");
    if (w && !w.contains(e.relatedTarget) && !w.classList.contains("fest") && !w.matches(":hover")) infoZeigen(w, false);
  });
  /* Esc schließt zuerst eine offene Info – und nur sie: Ein Dialog, in dem sie steht, bleibt offen (darum in der
     Erfassungsphase, vor den Esc-Regeln der Dialoge und Menüs). */
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const w = [...document.querySelectorAll(".info")].find(infoOffen);
    if (!w) return;
    infoZeigen(w, false);
    if (w.closest("dialog")) { e.preventDefault(); e.stopPropagation(); }
    const k = infoTeil(w, ".info-knopf");
    if (w.contains(document.activeElement) && document.activeElement !== k) {
      w.dataset.esc = "1";
      k.focus();
    }
  }, true);

  /* --- Fehler am Feld (UI/UX vor dem Merge, A2) ----------------------------------------------------------------
     Vorher meldete fast jeder Dialog einen Fehler nur als Toast; der Fokus fiel dabei auf die Seite (BODY), weil der
     ausgegraute Knopf ihn verlor, und das Feld blieb unmarkiert. Wie „Mangel melden“ jetzt überall:
     feldFehler(feld, text) – das Feld trägt aria-invalid, darunter steht der Satz (mit aria-describedby verknüpft), der
     Fokus geht aufs Feld; die nächste Eingabe nimmt beides wieder weg.
     fehlschlag(knopf, fehler, feld) – für das catch nach einer Anfrage: gibt den Knopf frei und meldet am Feld, wenn
     eins betroffen ist. feld ist das Feld selbst oder ein Bereich (Dialog): Dann sucht die Hilfe das Feld, das die
     Meldung des Servers nennt („„Titel“ fehlt.“ → das Feld mit der Beschriftung „Titel“). Ohne Feld: Toast und der Fokus
     zurück auf den Knopf (nie auf BODY). */
  let fehlerZahl = 0;
  const beschriftung = (l) => {
    const k = l.cloneNode(true);
    k.querySelectorAll(".info, .info-text, input, select, textarea, button").forEach((x) => x.remove());
    return k.textContent.replace(/\s+/g, " ").replace(/[*:]\s*$/, "").trim();
  };
  function feldZuName(bereich, name) {
    if (!bereich || !name) return null;
    const n = name.trim().toLowerCase();
    for (const l of bereich.querySelectorAll("label")) {
      const t = beschriftung(l).toLowerCase();
      if (l.control && (t === n || t.startsWith(`${n} (`) || t.startsWith(`${n} –`))) return l.control;
    }
    return [...bereich.querySelectorAll("input, select, textarea")].find((f) => (f.getAttribute("aria-label") || "").toLowerCase() === n) || null;
  }
  function feldOk(feld) {
    feld.removeAttribute("aria-invalid");
    feld.classList.remove("ungueltig");
    const p = feld.id ? document.getElementById(`${feld.id}-fehler`) : null;
    if (p) p.hidden = true;
  }
  function feldFehler(feld, text) {
    if (!feld) return;
    if (!feld.id) feld.id = `feld-${++fehlerZahl}`;
    let p = document.getElementById(`${feld.id}-fehler`);
    if (!p) {
      p = document.createElement("p");
      p.id = `${feld.id}-fehler`;
      p.className = "error feld-fehler";
      // Hinter dem Feld – bei Feldern mit Knopf daneben (Suche mit Trefferliste, Datum) hinter dieser Gruppe.
      // Ein Knopf einer Auswahlliste (Radio): hinter der Liste.
      const gruppe = (feld.type === "radio" && feld.closest(".user-pick, .mat-wahl, [role=radiogroup], fieldset"))
        || feld.closest(".feld-gruppe, .mat-produktwahl, .em-row") || feld;
      gruppe.insertAdjacentElement("afterend", p);
    }
    p.textContent = text;
    p.hidden = false;
    const beschr = (feld.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (!beschr.includes(p.id)) feld.setAttribute("aria-describedby", [...beschr, p.id].join(" "));
    feld.setAttribute("aria-invalid", "true");
    feld.classList.add("ungueltig");
    if (!feld.dataset.fehlerWeg) {
      feld.dataset.fehlerWeg = "1";
      const weg = () => feldOk(feld);
      feld.addEventListener("input", weg);
      feld.addEventListener("change", weg);
    }
    feld.focus();
    return false;
  }
  function fehlschlag(knopf, fehler, feld) {
    const text = fehler && typeof fehler === "object" ? fehler.message : String(fehler || "");
    if (knopf) knopf.disabled = false;
    const el = feld instanceof Element ? feld : null;
    let ziel = el && el.matches("input, select, textarea") ? el : null;
    if (!ziel && el) {
      const m = text.match(/^„([^“]+)“/);
      ziel = m ? feldZuName(el, m[1]) : null;
    }
    if (ziel) { feldFehler(ziel, text); return; }
    toast(text, true);
    const ae = document.activeElement;
    if (knopf && knopf.isConnected && (!ae || ae === document.body || ae.tagName === "DIALOG" || ae === knopf)) knopf.focus();
  }

  /* --- Kleinere gemeinsame Hilfen ---------------------------------------------------------------------------------
     plural: „1 Bild“, „3 Bilder“ (A11; vorher eigene Kopien in Materialablage, Riegenkarten, Freigaben, Leitstelle).
     rollen: weiches Rollen nur, wenn „Bewegung reduzieren“ nicht gewählt ist (A15) – sonst springt die Ansicht.
     schliessenKnopf, reihenfolgeKnoepfe, entfernenKnopf: dieselben Bedienzeichen in allen Modulen (D3, Zeichen der
     Materialablage, Nutzer V13) – ✕ zum Schließen und Entfernen, ↑/↓ für die Reihenfolge, jeweils mit Namen fürs Vorlesen.
     attrs ist fertiges Attribut-HTML, klasse die Knopfklasse. */
  const plural = (n, eins, viele) => `${n} ${n === 1 ? eins : viele}`;
  const bewegungAus = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function rollen(el, opt = {}) {
    if (!el) return;
    el.scrollIntoView(Object.assign({}, opt, { behavior: bewegungAus() ? "auto" : "smooth" }));
  }
  const weich = () => (bewegungAus() ? "auto" : "smooth");
  const schliessenKnopf = (attrs = "", klasse = "schliessen") =>
    `<button type="button" class="${klasse}" aria-label="Schließen" title="Schließen"${attrs ? ` ${attrs}` : ""}>✕</button>`;
  // name: der ganze Name fürs Vorlesen („Kriterium entfernen“, „Voraussetzung löschen“).
  const entfernenKnopf = (attrs = "", name = "Entfernen", klasse = "btn secondary small") =>
    `<button type="button" class="${klasse} zeichenknopf" aria-label="${esc(name)}" title="${esc(name)}"${attrs ? ` ${attrs}` : ""}>✕</button>`;
  // i: Platz (ab 0), n: Anzahl; hoch/runter: Attribut-HTML der beiden Knöpfe; name: was verschoben wird („Position 2“).
  const reihenfolgeKnoepfe = (i, n, hoch, runter, name = "", klasse = "btn secondary small") =>
    `<button type="button" class="${klasse} zeichenknopf" ${hoch} aria-label="${esc(name ? `${name} nach oben` : "Nach oben")}" title="Nach oben"${i <= 0 ? " disabled" : ""}>↑</button>`
    + `<button type="button" class="${klasse} zeichenknopf" ${runter} aria-label="${esc(name ? `${name} nach unten` : "Nach unten")}" title="Nach unten"${i >= n - 1 ? " disabled" : ""}>↓</button>`;

  /* Seitentitel im Reiter des Browsers und im Verlauf: das Gezeigte vorn, dann das Modul, dann die Seite –
     „M-000123 – Materialablage – strömis.de“ (Browserprüfung vor dem Merge, V2). teile: Texte (leere fallen weg),
     modul: Schlüssel aus app/module.py („material“ …) oder leer. Kein HTML: document.title zeigt Text, wie er ist. */
  function titel(teile, modul) {
    const name = modul ? ((window.STROEMIS && STROEMIS.module && STROEMIS.module.name) || {})[modul] : "";
    document.title = [...[].concat(teile || []), name, "strömis.de"].map((t) => String(t || "").trim()).filter(Boolean).join(" – ");
  }

  return { esc, api, toast, dialog, confirm, fmtDate, fmtCoord, CAT, titel, info, overlayVerlauf, dialogVerlauf, klassenVerlauf,
           feldFehler, feldOk, fehlschlag, menue, menueSchwebend, plural, rollen, weich, schliessenKnopf, entfernenKnopf,
           reihenfolgeKnoepfe };
})();
