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
      throw new Error("Keine Verbindung zum Server.");
    }
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname);
      throw new Error("Nicht angemeldet");
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* leer */ }
    if (!res.ok) throw new Error(data.error || ("Fehler " + res.status));
    return data;
  }

  let toastTimer;
  /* Der Toast liegt als Popover in der obersten Ebene des Browsers – über dem Backdrop eines
     modalen Dialogs. Sonst stand „Bitte einen Nutzer wählen“ gedimmt HINTER dem Dialog, aus
     dem die Meldung kam. Ältere Browser ohne Popover zeigen ihn wie bisher. */
  function toast(msg, isError) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "show" + (isError ? " err" : "");
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
    if (onOpen) onOpen(dlg, body);
    if (!dlg.open) dlg.showModal();
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

  return { esc, api, toast, dialog, confirm, fmtDate, fmtCoord, CAT };
})();
