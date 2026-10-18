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
    if (onOpen) onOpen(dlg, body);
    return dlg;
  }

  /* Rückfrage in einem eigenen Dialog – so bleibt ein bereits offener Dialog
     (z. B. der Versionsverlauf) darunter stehen, statt mit geschlossen zu werden. */
  function confirm(text, okLabel) {
    return new Promise((resolve) => {
      const dlg = document.createElement("dialog");
      dlg.innerHTML = `<div class="dlg-body"><h2>Bist du sicher?</h2><p>${esc(text)}</p>
        <div class="dlg-actions"><button class="btn secondary" id="c-no" type="button">Abbrechen</button>
        <button class="btn danger" id="c-ok" type="button">${esc(okLabel || "Löschen")}</button></div></div>`;
      document.body.appendChild(dlg);
      const done = (v) => { resolve(v); dlg.close(); };
      dlg.querySelector("#c-ok").onclick = () => done(true);
      dlg.querySelector("#c-no").onclick = () => done(false);
      dlg.addEventListener("close", () => { resolve(false); dlg.remove(); });
      dlg.showModal();
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
    const zuBreit = () => nav.scrollWidth > nav.clientWidth + 1;
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

  return { esc, api, toast, dialog, confirm, fmtDate, fmtCoord, CAT };
})();
