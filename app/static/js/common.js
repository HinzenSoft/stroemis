/* Gemeinsame Hilfsfunktionen für alle Seiten */
window.S = (function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(path, opts = {}) {
    const init = { method: opts.method || "GET", headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" };
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

  document.addEventListener("click", async (e) => {
    if (e.target.id === "logout") {
      try { await api("/api/auth/logout", { method: "POST", body: {} }); }
      catch (err) { toast("Abmelden hat nicht geklappt: " + err.message, true); return; }
      location.href = "/login";
    }
  });

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
