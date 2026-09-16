/* Wiki: Seitenbaum, Ansicht mit Inhaltsverzeichnis und Kommentaren, WYSIWYG-Editor (Toast UI),
   Bearbeitungsfreigaben, öffentliche Freigabe, Versionen, Suche, Import */
(function () {
  const { esc, api, toast, dialog, fmtDate } = S;
  const $ = (sel, root) => (root || document).querySelector(sel);
  /* Beim Wechsel zwischen Lesen und Bearbeiten gemerkte Bildlaufhöhe: beide Ansichten setzen
     jeden Block auf dieselbe Höhe, die Stelle im Text bleibt damit unter dem Zeiger stehen.
     Ohne das Merken sprang der Editor ans Dokumentende, sobald er den Fokus bekam. */
  let modusScroll = null;
  const modusScrollMerken = () => { modusScroll = window.scrollY; };
  const modusScrollAnwenden = () => {
    if (modusScroll === null) return false;
    const y = modusScroll;
    modusScroll = null;
    /* Der Editor baut seinen Inhalt erst nach und nach auf: Bilder werden neu geladen, die
       Spalten messen ihre Höhen. Solange der Text kürzer ist als die gemerkte Stelle, kappt
       der Browser das Scrollen auf das Dokumentende – man landet unten statt dort, wo man
       gelesen hat. Die Stelle wird deshalb nachgehalten, bis sie wirklich erreicht ist:
       höchstens zwei Sekunden lang, und nur solange niemand selbst scrollt. */
    const ende = Date.now() + 2000;
    let lauf = 0, eigener = false;
    const merke = () => { eigener = true; };
    const ereignisse = ["wheel", "touchmove", "keydown", "mousedown"];
    ereignisse.forEach((n) => window.addEventListener(n, merke, { passive: true }));
    const aufraeumen = () => {
      if (lauf) cancelAnimationFrame(lauf);
      lauf = 0;
      ereignisse.forEach((n) => window.removeEventListener(n, merke));
    };
    const halten = () => {
      lauf = 0;
      if (eigener) return aufraeumen();
      if (Math.round(window.scrollY) !== Math.round(y)) window.scrollTo(0, y);
      if (Math.round(window.scrollY) === Math.round(y) || Date.now() > ende) return aufraeumen();
      lauf = requestAnimationFrame(halten);
    };
    window.scrollTo(0, y);
    lauf = requestAnimationFrame(halten);
    return true;
  };

  const shell = $(".wiki-shell");
  const side = $("#wiki-side");
  /* Unter 1180 px hat das Raster keine dritte Spalte mehr. Die rechte Spur (Kommentare, Angaben
     zur Seite) wandert dann in die Textspalte unter den Artikel, statt zu verschwinden – auf
     Telefon und Tablet waren Kommentare sonst gar nicht zu lesen. Das Element bleibt dasselbe
     (tocEl/commentsEl zeigen weiter darauf), nur sein Platz im Baum ändert sich. */
  const schmalesRaster = window.matchMedia("(max-width: 1180px)");
  const spurVersetzen = () => {
    const rail = $("#wiki-rail"), main = $("#wiki-main"), shell = $(".wiki-shell");
    if (!rail || !main || !shell) return;
    if (schmalesRaster.matches) { if (rail.parentElement !== main) main.appendChild(rail); }
    else if (rail.parentElement !== shell) shell.appendChild(rail);
  };
  schmalesRaster.addEventListener("change", spurVersetzen);
  spurVersetzen();
  const treeEl = $("#tree");
  const content = $("#wiki-content");
  const tocEl = $("#toc");
  const commentsEl = $("#comments");
  const fab = $("#comment-fab");
  const searchInput = $("#wiki-search");
  const searchResults = $("#search-results");

  const state = { pages: [], byId: new Map(), current: null, comments: [], editor: null, dirty: false,
                  collapsed: new Set(), users: null, commentFilter: "open", spy: null, autosave: null,
                  praesenz: null, pulsLauf: 0, pulsToken: 0, ladeLauf: 0, schreibrecht: false,
                  editorSeite: null, editorNeu: false, editorKonflikt: false };

  /* --- Wer ist gerade an der Seite? --------------------------------------------------------
     Der Editor speichert selbstständig; zwei Leute gleichzeitig an einer Seite hieße deshalb,
     dass einer seine Arbeit verliert, ohne es zu merken. Jeder Reiter meldet daher alle paar
     Sekunden, woran er ist. Genau einer bekommt das Schreibrecht, die anderen sehen, wer es hat.
     Die Kennung hält im sessionStorage: Neuladen ist derselbe Reiter, ein zweiter Reiter ein
     anderer – sonst nähme sich der Nutzer beim Neuladen selbst das Schreibrecht weg. */
  const PULS_MS = 15000;
  /* Solange jemand anderes schreibt, laufen die Leser im kurzen Takt: Der Schreiber speichert
     ohnehin 1,2 s nach jeder Änderung, und was er speichert, erscheint bei den Lesern von
     selbst (siehe artikelNachziehen). Vier Sekunden: kurz genug, um zuzusehen, lang genug,
     dass ein Verein mit ein paar Mitlesern die Datenbank nicht mit Herzschlägen beschäftigt. */
  const LIVE_MS = 4000;
  const REITER = (() => {
    try {
      const vorhanden = sessionStorage.getItem("stroemis-reiter");
      if (vorhanden) return vorhanden;
      const neu = bearbeitungsKennzeichen();
      sessionStorage.setItem("stroemis-reiter", neu);
      return neu;
    } catch (e) { return bearbeitungsKennzeichen(); }
  })();
  // Welche Endungen als Film und Ton gelten, entscheidet der Renderer – hier dieselbe Liste.
  const { VIDEO_RE, AUDIO_RE } = MD;
  // Jede Zeile, die im Editorformat einen Block eröffnet. Blockmenü und Ziehgriff bilden
  // damit Text und Editor aufeinander ab – beide müssen dieselbe Liste sehen.
  const MARKEN_RE = window.EDMD.MARKEN_RE;
  // Zeichenfolge, die kurz an der Cursorstelle steht, damit sich der gemeinte Block im
  // Markdown wiederfinden lässt. Sie verschwindet noch vor dem Zurückschreiben.
  const AUSRICHT_MARKE = "zzausrichtungsstellezz";
  // Zweite Marke für das Ende einer Auswahl über mehrere Absätze. Sie darf die erste nicht
  // enthalten, sonst fände die Suche nach der einen auch die andere.
  const AUSRICHT_ENDE = "zzausrichtungsendemarkezz";

  /* Kopfzeile wie in Docmost: links der Pfad, rechts Umschalter, Teilen, Kommentare, das
     Inhaltsverzeichnis und ein Menü für alles Weitere. Der Knopf blendet nur die Gliederung
     aus – die rechte Spur behält ihre Breite, damit sich der Text beim Umschalten nicht
     verschiebt. */
  const TOC_AUS = "stroemis-toc-aus";
  const tocKnopf = () =>
    '<button class="btn ghost small kopfknopf" id="pg-toc" title="Inhaltsverzeichnis ein- oder ausblenden" aria-label="Inhaltsverzeichnis">☰</button>';
  const tocStandAnwenden = () => {
    let aus = false;
    try { aus = localStorage.getItem(TOC_AUS) === "1"; } catch (e) { /* egal */ }
    document.body.classList.toggle("toc-aus", aus);
    const k = $("#pg-toc");
    if (k) k.setAttribute("aria-pressed", aus ? "false" : "true");
  };
  const tocKnopfVerdrahten = () => {
    const k = $("#pg-toc");
    if (!k) return;
    tocStandAnwenden();
    k.onclick = () => {
      const aus = !document.body.classList.contains("toc-aus");
      try { localStorage.setItem(TOC_AUS, aus ? "1" : "0"); } catch (e) { /* egal */ }
      tocStandAnwenden();
    };
  };

  /* ======================================================================
     Baum
     ====================================================================== */
  async function loadTree() {
    // Der Baum trägt die ganze Navigation. Bricht der Abruf ab, bleibt der letzte Stand stehen
    // statt zu verschwinden – und der Fehler wird gesagt, statt in einer stillen Ablehnung zu enden.
    let d;
    try { d = await api("/api/wiki/tree"); } catch (e) { toast("Der Seitenbaum ließ sich nicht laden: " + e.message, true); return; }
    state.pages = d.pages;
    state.byId = new Map(d.pages.map((p) => [p.id, p]));
    renderTree();
  }
  const children = (pid) => state.pages.filter((p) => (p.parent_id || null) === (pid || null));

  function ancestors(page) {
    const out = [];
    let p = page && page.parent_id ? state.byId.get(page.parent_id) : null;
    while (p) { out.unshift(p); p = p.parent_id ? state.byId.get(p.parent_id) : null; }
    return out;
  }

  function branch(pid, depth) {
    const kids = children(pid);
    if (!kids.length) return "";
    const path = new Set(ancestors(state.current).map((p) => p.id));
    return `<ul>${kids.map((p) => {
      const sub = branch(p.id, depth + 1);
      const collapsed = sub && !path.has(p.id) && (state.collapsed.has(p.id) || (depth >= 1 && !state.collapsed.has(-p.id)));
      return `<li class="${sub ? "" : "leaf"}${collapsed ? " collapsed" : ""}" data-id="${p.id}" data-slug="${esc(p.slug)}">
        <div class="row" draggable="true">
          <button class="tg" type="button" aria-label="Auf- oder zuklappen"></button>
          <a href="/wiki/${esc(p.slug)}" title="${esc(p.title)}" class="${state.current && state.current.id === p.id ? "active" : ""}">${p.icon ? `<span class="tree-icon" aria-hidden="true">${esc(p.icon)}</span>` : ""}${esc(p.title)}${p.is_public ? ' <span class="pub" title="öffentlich freigegeben">🌐</span>' : ""}${p.favorite ? ' <span class="fav" title="auf der Merkliste">★</span>' : ""}</a>
          <button class="row-add" type="button" title="Unterseite anlegen" aria-label="Unterseite anlegen">+</button>
          <button class="row-menu" type="button" title="Mehr" aria-label="Weitere Aktionen">⋯</button>
        </div>${sub}</li>`;
    }).join("")}</ul>`;
  }

  function renderTree() {
    treeEl.innerHTML = branch(null, 0) || '<li class="muted small" style="padding:6px">Noch keine Seiten.</li>';
    treeEl.querySelectorAll(".tg").forEach((b) => b.addEventListener("click", () => {
      const li = b.closest("li"), id = +li.dataset.id;
      li.classList.toggle("collapsed");
      if (li.classList.contains("collapsed")) { state.collapsed.add(id); state.collapsed.delete(-id); }
      else { state.collapsed.delete(id); state.collapsed.add(-id); }
    }));
    treeEl.querySelectorAll("a").forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault();
      side.classList.remove("open");
      navigate(a.getAttribute("href").slice(6));
    }));
    treeEl.querySelectorAll(".row-add").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = +b.closest("li").dataset.id;
      if (leaveEditor()) openEditor({ parent_id: id });
    }));
    treeEl.querySelectorAll(".row-menu").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      treeRowMenu(b, state.byId.get(+b.closest("li").dataset.id));
    }));
    wireTreeDrag();
    renderFavorites();
  }

  /* Pfeiltasten, Pos1/Ende und Escape in einem aufgeklappten Menü. */
  function wireMenuKeys(box, close) {
    const items = () => Array.from(box.querySelectorAll("button:not([disabled])"));
    const focusAt = (i) => { const list = items(); if (list.length) list[(i + list.length) % list.length].focus(); };
    box.setAttribute("role", "menu");
    items().forEach((b) => b.setAttribute("role", "menuitem"));
    setTimeout(() => focusAt(0), 0);
    box.addEventListener("keydown", (e) => {
      const list = items();
      const at = list.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); focusAt(at + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); focusAt(at - 1); }
      else if (e.key === "Home") { e.preventDefault(); focusAt(0); }
      else if (e.key === "End") { e.preventDefault(); focusAt(list.length - 1); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "Tab") { close(); }
    });
  }

  /* Kontextmenü an der Baumzeile – dieselben Aktionen wie im Seitenkopf. */
  function treeRowMenu(anchor, page) {
    if (!page) return;
    const box = document.createElement("div");
    box.className = "tree-menu";
    box.innerHTML = `
      <button type="button" data-a="child">Unterseite anlegen</button>
      <button type="button" data-a="fav">${page.favorite ? "Von der Merkliste nehmen" : "Zur Merkliste"}</button>
      <button type="button" data-a="icon">Symbol ändern …</button>
      <button type="button" data-a="dup">Duplizieren</button>
      <button type="button" data-a="export">Als Markdown herunterladen</button>
      <button type="button" data-a="del" class="danger">In den Papierkorb</button>`;
    document.body.appendChild(box);
    const r = anchor.getBoundingClientRect();
    box.style.left = `${Math.min(window.innerWidth - box.offsetWidth - 8, r.left)}px`;
    box.style.top = `${window.scrollY + r.bottom + 4}px`;
    const close = () => { box.remove(); document.removeEventListener("pointerdown", onDoc, true); if (anchor && anchor.focus) anchor.focus(); };
    const onDoc = (e) => { if (!box.contains(e.target)) close(); };
    setTimeout(() => document.addEventListener("pointerdown", onDoc, true), 0);
    wireMenuKeys(box, close);
    box.addEventListener("click", async (e) => {
      const b = e.target.closest("button[data-a]");
      if (!b) return;
      const a = b.dataset.a;
      close();
      if (a === "child") { if (leaveEditor()) openEditor({ parent_id: page.id }); return; }
      if (a === "fav") return toggleFavorite(page.id, !page.favorite);
      if (a === "icon") return iconDialog(page.id, page.icon || "");
      if (a === "export") { window.location.href = `/api/wiki/pages/${page.id}/export`; return; }
      if (a === "dup") {
        try { const r2 = await api(`/api/wiki/pages/${page.id}/duplicate`, { method: "POST", body: {} });
          toast("Seite dupliziert"); await loadTree(); navigate(r2.page.slug); }
        catch (err) { toast(err.message, true); }
        return;
      }
      if (a === "del") {
        if (!(await S.confirm(`Seite „${page.title}“ mit allen Unterseiten in den Papierkorb legen?`, "In den Papierkorb"))) return;
        try { await api(`/api/wiki/pages/${page.id}`, { method: "DELETE" }); toast("In den Papierkorb gelegt");
          await loadTree(); navigate(""); }
        catch (err) { toast(err.message, true); }
      }
    });
  }

  /* Seiten im Baum per Ziehen umsortieren: auf eine Zeile = darunter einsortieren,
     auf die Lücke zwischen zwei Zeilen = daneben. */
  function wireTreeDrag() {
    let dragId = null;
    treeEl.querySelectorAll(".row").forEach((row) => {
      const li = row.closest("li");
      row.addEventListener("dragstart", (e) => {
        dragId = +li.dataset.id;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(dragId));
        row.classList.add("dragging");
      });
      row.addEventListener("dragend", () => { dragId = null; clearDropMarks(); row.classList.remove("dragging"); });
      row.addEventListener("dragover", (e) => {
        if (!dragId || dragId === +li.dataset.id) return;
        e.preventDefault();
        const r = row.getBoundingClientRect();
        const zone = (e.clientY - r.top) / r.height;
        clearDropMarks();
        row.classList.add(zone < 0.25 ? "drop-before" : zone > 0.75 ? "drop-after" : "drop-into");
      });
      row.addEventListener("drop", async (e) => {
        e.preventDefault();
        const target = state.byId.get(+li.dataset.id);
        const moved = state.byId.get(dragId);
        const mode = row.classList.contains("drop-before") ? "before"
          : row.classList.contains("drop-after") ? "after" : "into";
        clearDropMarks();
        if (!moved || !target || moved.id === target.id) return;
        const parentId = mode === "into" ? target.id : (target.parent_id || null);
        const siblings = children(parentId).filter((x) => x.id !== moved.id);
        let index = siblings.length;
        if (mode !== "into") {
          const at = siblings.findIndex((x) => x.id === target.id);
          index = at < 0 ? siblings.length : (mode === "before" ? at : at + 1);
        }
        siblings.splice(index, 0, moved);
        const items = siblings.map((x, i) => ({ id: x.id, parent_id: parentId, position: i }));
        try {
          await api("/api/wiki/reorder", { method: "PUT", body: { items } });
          await loadTree();
          toast("Verschoben");
        } catch (err) { toast(err.message, true); await loadTree(); }
      });
    });
  }
  function clearDropMarks() {
    treeEl.querySelectorAll(".drop-before, .drop-after, .drop-into")
      .forEach((x) => x.classList.remove("drop-before", "drop-after", "drop-into"));
  }

  async function toggleFavorite(pid, on) {
    try {
      await api(`/api/wiki/pages/${pid}/favorite`, { method: "PUT", body: { favorite: !!on } });
      await loadTree();
      if (state.current && state.current.id === pid) { state.current.favorite = !!on; await renderPage(); }
      toast(on ? "Zur Merkliste hinzugefügt" : "Von der Merkliste genommen");
    } catch (e) { toast(e.message, true); }
  }

  /* Merkliste über dem Seitenbaum */
  async function renderFavorites() {
    const box = $("#favorites");
    if (!box) return;
    const favs = state.pages.filter((p) => p.favorite);
    box.innerHTML = favs.length
      ? `<div class="side-title">Merkliste</div><ul class="fav-list">${favs.map((p) =>
          `<li><a href="/wiki/${esc(p.slug)}">${p.icon ? `<span class="tree-icon">${esc(p.icon)}</span>` : "★ "}${esc(p.title)}</a></li>`).join("")}</ul>`
      : "";
    box.querySelectorAll("a").forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault(); side.classList.remove("open"); navigate(a.getAttribute("href").slice(6));
    }));
  }

  /* Emoji für die Seite wählen */
  function iconDialog(pid, current) {
    dialog(`<h2>Symbol der Seite</h2>
      <div class="em-row"><input type="text" id="em-input" maxlength="8" autocomplete="off"><span class="help">Emoji eintippen oder unten wählen</span></div>
      <div class="em-grid" id="em-grid"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
      <button class="btn ghost" id="ic-clear" type="button">Entfernen</button>
      <button class="btn" id="ic-ok" type="button">Übernehmen</button></div>`,
      (dlg, body) => {
        dlg.classList.add("wide");
        dlg.addEventListener("close", () => dlg.classList.remove("wide"), { once: true });
        const getEmoji = emojiPicker(body, current || "📄");
        const save = async (icon) => {
          try {
            await api(`/api/wiki/pages/${pid}/icon`, { method: "PUT", body: { icon } });
            dlg.close(); await loadTree();
            if (state.current && state.current.id === pid) { state.current.icon = icon; await renderPage(); }
          } catch (e) { toast(e.message, true); }
        };
        body.querySelector("#ic-ok").onclick = () => save(getEmoji());
        body.querySelector("#ic-clear").onclick = () => save("");
      });
  }

  /* ======================================================================
     Navigation
     ====================================================================== */
  function slugFromPath() { return decodeURIComponent(location.pathname.replace(/^\/(wiki\/?)?/, "")); }

  function navigate(ziel, push = true) {
    // "seite#abschnitt" oder "seite?x": Nur der Slug sucht die Seite, der Anker springt danach.
    const [ohneHash, hash = ""] = String(ziel || "").split("#");
    const slug = ohneHash.split("?")[0];
    if (!leaveEditor()) return;
    if (push) history.pushState({ slug }, "", (slug ? `/wiki/${slug}` : "/wiki") + (hash ? `#${hash}` : ""));
    show(slug);
  }
  window.addEventListener("popstate", () => {
    // Nur der Anker hat gewechselt (Klick auf „#“ neben einer Überschrift, Eintrag im
    // Inline-Inhaltsverzeichnis): Dann wird gescrollt, nicht die ganze Seite neu geholt.
    if (state.current && !state.editor && slugFromPath() === state.current.slug) { MD.scrollToHash(content); return; }
    if (leaveEditor()) return show(slugFromPath());
    // Der Nutzer bleibt im Editor – dann muss auch die Adresse wieder auf die Seite zeigen,
    // die er bearbeitet, sonst zeigen Adresszeile und Ansicht auf Verschiedenes.
    if (state.current) history.pushState({ slug: state.current.slug }, "", `/wiki/${state.current.slug}`);
  });

  /* --- Anwesenheit und Schreibrecht --------------------------------------------------------- */
  async function praesenzPuls(extra = {}) {
    clearTimeout(state.pulsLauf);
    const p = state.current;
    if (!p || !p.id) return null;
    // Nur der Editor DIESER Seite meldet „schreiben“. Eine neue, noch nicht angelegte Seite hat
    // keine Kennung – ihr Editor darf nicht die zuvor gelesene Seite für alle sperren.
    const wunsch = state.editor && state.editorSeite === p.id ? "schreiben" : "lesen";
    const lauf = ++state.pulsToken;
    let d = null;
    try {
      d = await api("/api/wiki/praesenz", { method: "POST",
        body: { reiter: REITER, page_id: p.id, modus: wunsch, ...extra } });
    } catch (e) { /* Netz weg oder Seite fort – der nächste Herzschlag versucht es erneut */ }
    // Ist inzwischen ein neuer Puls gestartet (Seitenwechsel, Editor auf), führt der die
    // Schleife – sonst liefen zwei Herzschläge nebeneinander, und die Antwort der vorigen
    // Seite färbte den Bearbeiten-Knopf der neuen.
    if (lauf !== state.pulsToken) return null;
    const takt = !state.editor && d && d.schreiber ? LIVE_MS : PULS_MS;
    state.pulsLauf = setTimeout(() => praesenzPuls(), takt);
    if (!d || state.current !== p) return null;
    state.praesenz = d;
    praesenzAnzeigen();
    if (wunsch === "schreiben" && d.modus !== "schreiben" && state.schreibrecht) {
      state.schreibrecht = false;
      schreibrechtVerloren(d);
    } else if (d.modus === "schreiben") {
      state.schreibrecht = true;
    }
    // Die Antwort nennt die gespeicherte Fassung. Ist sie neuer als die gezeigte, wird der
    // Artikel nachgezogen – auch im langen Takt: So kommt der letzte Stand noch an, wenn der
    // fremde Editor schon wieder zu ist.
    if (wunsch === "lesen" && state.current === p && d.version != null && p.version != null
        && d.version !== p.version) artikelNachziehen(p);
    return d;
  }

  /* --- Live mitlesen ---------------------------------------------------------------------
     Es schreibt immer nur eine Person, aber die anderen müssen nicht warten, bis sie fertig
     ist. Neu gezeichnet wird nur der Artikel; Kopfzeile, Verzeichnis und Kommentaranker
     werden nachgeführt. Die Lesestelle bleibt stehen (lesestelleMerken). */
  async function artikelNachziehen(p) {
    if (state.editor || state.zieht) return;
    // Nicht unter einer Auswahl oder einem offenen Dialog wegzeichnen: Wer gerade eine
    // Textstelle zum Kommentieren markiert, verlöre sie. Der nächste Herzschlag kommt wieder.
    const dlg = document.getElementById("dlg");
    const sel = window.getSelection();
    const art = $("#article");
    if ((dlg && dlg.open) || (sel && !sel.isCollapsed && art && art.contains(sel.anchorNode))) return;
    state.zieht = true;
    try {
      const d = await api(`/api/wiki/pages/${encodeURIComponent(p.slug)}`);
      if (state.current !== p || state.editor || !d.page || d.page.version === p.version) return;
      const neu = d.page;
      const kopfNeu = neu.title !== p.title || neu.icon !== p.icon || neu.slug !== p.slug;
      const stelle = lesestelleMerken();
      Object.assign(p, neu);               // p ist state.current – an Ort und Stelle nachführen
      if (kopfNeu) {
        // Umbenannt oder neues Symbol: Kopf, Titel und Baum müssen mit – das ist selten,
        // dafür darf die Seite einmal ganz neu entstehen.
        document.title = `${p.title} – Wiki – strömis.de`;
        history.replaceState({ slug: p.slug }, "", `/wiki/${p.slug}`);
        await loadTree();
        await renderPage();
      } else {
        artikelZeichnen(p);
        anchorComments();
      }
      lesestelleAnwenden(stelle);
    } catch (e) { /* Netz weg – der nächste Herzschlag versucht es erneut */
    } finally { state.zieht = false; }
  }

  /* Die Lesestelle über ein Neuzeichnen hinweg halten. Gemerkt wird nicht die Bildlaufhöhe,
     sondern der oberste sichtbare Block mit seinem Text und seinem Abstand zum oberen Rand:
     Wächst der Text oberhalb, bliebe die Höhe gleich, der Leser aber rutschte auf einen
     anderen Absatz. Nach dem Zeichnen wird derselbe Block wieder an dieselbe Stelle geholt –
     gesucht über den Text, damit ein oberhalb eingefügter Absatz die Zählung nicht verschiebt. */
  function lesestelleMerken() {
    const art = $("#article");
    if (!art || window.scrollY < 4) return null;    // ganz oben bleibt ganz oben
    const bloecke = Array.from(art.children);
    const i = bloecke.findIndex((b) => b.getBoundingClientRect().bottom > 0);
    if (i < 0) return null;
    return { i, text: bloecke[i].textContent, oben: bloecke[i].getBoundingClientRect().top };
  }
  function lesestelleAnwenden(stelle) {
    if (!stelle) return;
    const art = $("#article");
    if (!art) return;
    const bloecke = Array.from(art.children);
    const gleich = bloecke.map((b, i) => [b, i]).filter(([b]) => b.textContent === stelle.text)
      .sort((a, b) => Math.abs(a[1] - stelle.i) - Math.abs(b[1] - stelle.i));
    const ziel = gleich.length ? gleich[0][0] : bloecke[Math.min(stelle.i, bloecke.length - 1)];
    if (!ziel) return;
    const setzen = () => window.scrollBy(0, ziel.getBoundingClientRect().top - stelle.oben);
    setzen();
    // Bilder, die erst noch laden, schieben den Text darunter nach – nachhalten, solange
    // der Leser nicht selbst gescrollt hat.
    let ruhe = window.scrollY;
    art.querySelectorAll("img").forEach((img) => {
      if (img.complete) return;
      img.addEventListener("load", () => { if (window.scrollY === ruhe) { setzen(); ruhe = window.scrollY; } },
                           { once: true });
    });
  }

  /* Beim Schließen des Reiters bleibt keine Zeit für eine Antwort; sendBeacon schickt trotzdem.
     Der JSON-Inhaltstyp genügt dem CSRF-Schutz, ein eigener Kopf ginge hier gar nicht. */
  function praesenzAbmelden() {
    try {
      navigator.sendBeacon("/api/wiki/praesenz",
        new Blob([JSON.stringify({ reiter: REITER, weg: true })], { type: "application/json" }));
    } catch (e) { /* egal */ }
  }
  window.addEventListener("pagehide", praesenzAbmelden);

  function praesenzAnzeigen() {
    const reihe = $(".wiki-head .btn-row");
    if (!reihe) return;
    const d = state.praesenz;
    const schreiber = d && d.schreiber ? d.schreiber : null;
    let feld = $("#pg-praesenz");
    if (!schreiber) {
      if (feld) feld.remove();
    } else {
      if (!feld) {
        feld = document.createElement("span");
        feld.id = "pg-praesenz";
        feld.className = "praesenz";
        reihe.insertBefore(feld, reihe.firstChild);
      }
      feld.textContent = `✏ ${schreiber.name} bearbeitet`;
      feld.title = `${schreiber.name} hat diese Seite gerade im Editor offen. Was gespeichert wird, `
        + "erscheint hier von selbst.";
    }
    bearbeitenKnopfStand(schreiber);
  }

  /* Solange jemand anders schreibt, ist der Knopf gar nicht erst zu drücken. Vorher stand dahinter
     ein Dialog mit „Nur lesen“ und „Trotzdem übernehmen“ – der bot eine Wahl an, die es nicht
     geben darf: Der Editor speichert von allein, der Übernommene verliert seine Arbeit
     unbemerkt. Bleibt als einzige Antwort „warten“, und die sagt der Knopf selbst. */
  function bearbeitenKnopfStand(schreiber) {
    const ed = $("#pg-edit");
    if (!ed) return;
    ed.disabled = !!schreiber;
    ed.title = schreiber
      ? `${schreiber.name} bearbeitet diese Seite gerade. Sobald die Seite frei ist, lässt sich `
        + "hier wieder bearbeiten."
      : "";
  }

  /* Den Schreibplatz verliert nur, wessen Reiter sich lange genug nicht gemeldet hat – Rechner
     im Schlaf, Netz weg, Reiter eingefroren. Dann gilt er als fort, und der Nächste rückt nach. */
  function schreibrechtVerloren(d) {
    const wer = d && d.schreiber ? d.schreiber.name : "Jemand anderes";
    state.editorGesperrt = true;
    toast(`Die Verbindung war zu lange unterbrochen – inzwischen bearbeitet ${wer} die Seite. `
      + "Hier wird nichts mehr gespeichert. Kopiere deine letzten Änderungen, bevor du die Seite "
      + "verlässt.", true);
    const st = $("#ed-status");
    if (st) { st.textContent = `${wer} bearbeitet jetzt – nicht mehr gespeichert`; st.classList.add("warn"); }
  }

  async function schreibrechtHolen(p) {
    try {
      return await api("/api/wiki/praesenz", { method: "POST",
        body: { reiter: REITER, page_id: p.id, modus: "schreiben" } });
    } catch (e) { toast(e.message, true); return null; }
  }

  /* Der Weg in den Editor führt über das Schreibrecht. Der Knopf ist ausgegraut, solange ihn
     jemand anderes hat – hierher kommt man dann nur noch im Wettlauf: Der Knopf wird alle paar
     Sekunden nachgeführt, jemand kann in der Lücke davor angefangen haben. Dann bleibt es beim
     Lesen, und der Hinweis sagt, worauf zu warten ist. */
  async function bearbeitenStarten(p) {
    const d = await schreibrechtHolen(p);
    if (d && d.modus === "schreiben") {
      state.schreibrecht = true;
      state.editorGesperrt = false;
      modusScrollMerken();
      return openEditor(p);
    }
    if (d) { state.praesenz = d; praesenzAnzeigen(); }
    const wer = d && d.schreiber ? d.schreiber.name : "Jemand anderes";
    const seit = d && d.schreiber && d.schreiber.seit ? ` (seit ${fmtDate(d.schreiber.seit, true)})` : "";
    toast(`${wer} bearbeitet diese Seite gerade${seit} – solange geht nur Lesen.`, true);
    return null;
  }

  async function show(slug) {
    hideFab();
    if (!slug) return showHome();
    // Zwei schnelle Klicks: Die Antwort der ZULETZT gewählten Seite gehört auf den Schirm,
    // auch wenn die der ersten später eintrifft.
    const lauf = ++state.ladeLauf;
    let d;
    try { d = await api(`/api/wiki/pages/${encodeURIComponent(slug)}`); }
    catch (e) {
      if (lauf !== state.ladeLauf) return;
      state.current = null;
      if (state.spy) { try { state.spy(); } catch (e) { /* egal */ } state.spy = null; }
      seitenInfoSchliessen();
      content.innerHTML = `<div class="empty"><strong>Seite nicht gefunden</strong>${esc(e.message)}<div class="btn-row" style="justify-content:center;margin-top:12px"><a class="btn secondary small" href="/wiki" id="home-link">Zur Übersicht</a></div></div>`;
      $("#home-link").onclick = (ev) => { ev.preventDefault(); navigate(""); };
      renderTree(); renderRail([]);
      return;
    }
    if (lauf !== state.ladeLauf) return;
    state.current = d.page;
    // Die Anwesenheit galt der vorigen Seite. Stehen lassen hieße, den Bearbeiten-Knopf hier
    // nach einem fremden Schreiber zu graufärben, der ganz woanders sitzt.
    state.praesenz = null;
    if (d.page.slug !== slug) history.replaceState({ slug: d.page.slug }, "", `/wiki/${d.page.slug}`);
    document.title = `${d.page.title} – Wiki – strömis.de`;
    renderTree();
    await renderPage();
    // Anmelden, wer hier gerade liest – und erfahren, ob jemand anders die Seite bearbeitet.
    praesenzPuls();
    // Mit #abschnitt in der Adresse dorthin springen, sonst an den Anfang – es sei denn, wir
    // kommen gerade aus dem Editor: dann bleibt die Stelle im Text stehen.
    if (!modusScrollAnwenden() && !MD.scrollToHash(content)) window.scrollTo(0, 0);
  }

  function showHome() {
    // Ohne Seite gibt es keinen Herzschlag mehr – der Reiter meldet sich ab, sonst hielte ein
    // Schreiber, der zur Übersicht wechselt, seine Seite noch 45 s lang für alle gesperrt.
    clearTimeout(state.pulsLauf);
    state.pulsToken++;
    praesenzAbmelden();
    state.current = null;
    state.comments = [];
    // Der Scrollspy hing noch am Fenster und suchte Überschriften eines Artikels, den es nicht
    // mehr gibt; die Angabenleiste zeigte die Zahlen der zuletzt gelesenen Seite.
    if (state.spy) { try { state.spy(); } catch (e) { /* egal */ } state.spy = null; }
    seitenInfoSchliessen();
    document.title = "Wiki – strömis.de";
    renderTree();
    renderRail([]);
    const roots = children(null);
    if (!roots.length) {
      content.innerHTML = `<div class="empty"><strong>Das Wiki ist noch leer</strong>Lege die erste Seite an.
        <div class="btn-row" style="justify-content:center;margin-top:14px"><button class="btn" id="h-new">Erste Seite anlegen</button></div></div>`;
      $("#h-new").onclick = () => openEditor({ parent_id: null });
      return;
    }
    /* Die Übersicht zeigt jeden Abschnitt mit allem, was darunter liegt – nicht nur die erste
       Ebene. Tiefer als drei Stufen wird nicht mehr aufgefächert: Dort steht stattdessen, wie
       viele Seiten noch folgen, und der Weg dorthin führt über den Abschnitt selbst. */
    const HOME_TIEFE = 3;
    const zaehleUnter = (pid) => children(pid).reduce((n, k) => n + 1 + zaehleUnter(k.id), 0);
    const eintrag = (p) => `<a href="/wiki/${esc(p.slug)}">${p.icon ? esc(p.icon) + " " : ""}${esc(p.title)}</a>`;
    const zweig = (pid, tiefe) => {
      const kids = children(pid);
      if (!kids.length) return "";
      if (tiefe >= HOME_TIEFE) {
        const n = kids.reduce((sum, k) => sum + 1 + zaehleUnter(k.id), 0);
        return `<ul class="home-tiefer"><li class="muted">… ${n} weitere ${n === 1 ? "Seite" : "Seiten"}</li></ul>`;
      }
      return `<ul>${kids.map((k) => `<li>${eintrag(k)}${zweig(k.id, tiefe + 1)}</li>`).join("")}</ul>`;
    };
    content.innerHTML = `<div class="wiki-head"><h1>Wiki</h1></div>
      <div class="wiki-meta">${state.pages.length} Seiten · Wissen für die Strömungsrettung und seiltechnische Rettung</div>
      <div class="wiki-content home-baum">${roots.map((r) =>
        `<h2>${eintrag(r)}</h2>${zweig(r.id, 1)}`).join("")}</div>
      <div class="home-cols" id="home-recent"></div>`;
    wireLinks(content);
    loadRecent();
  }

  async function loadRecent() {
    const box = $("#home-recent");
    if (!box) return;
    let d;
    try { d = await api("/api/wiki/recent"); } catch (e) { return; }
    const list = (rows, meta) => rows.length
      ? `<ul>${rows.map((r) => `<li><a href="/wiki/${esc(r.slug)}">${r.icon ? esc(r.icon) + " " : ""}${esc(r.title)}</a>`
        + `<span class="muted small"> · ${fmtDate(meta(r), true)}</span></li>`).join("")}</ul>`
      : '<p class="muted small">Noch nichts.</p>';
    box.innerHTML = `
      <div><div class="side-title">Zuletzt besucht</div>${list(d.seen, (r) => r.seen_at)}</div>
      <div><div class="side-title">Zuletzt geändert</div>${list(d.changed, (r) => r.updated_at)}</div>`;
    wireLinks(box);
  }

  /* Papierkorb: wiederherstellen oder endgültig entfernen */
  async function trashDialog() {
    let d;
    try { d = await api("/api/wiki/trash"); } catch (e) { return toast(e.message, true); }
    const rows = d.pages;
    dialog(`<h2>Papierkorb</h2>
      ${rows.length ? `<p class="help">Wiederhergestellte Seiten kommen an ihren alten Platz zurück; ist die
      übergeordnete Seite noch gelöscht, landen sie auf der obersten Ebene.</p>
      <ul class="trash-list">${rows.map((r) => `<li data-id="${r.id}">
        <div><strong>${r.icon ? esc(r.icon) + " " : ""}${esc(r.title)}</strong>
          <span class="muted small">${r.children ? `· ${r.children} Unterseite${r.children > 1 ? "n" : ""} ` : ""}· gelöscht ${fmtDate(r.deleted_at, true)}${r.created_by_name ? " · " + esc(r.created_by_name) : ""}</span></div>
        <div class="btn-row">${r.can_restore
          ? '<button class="btn secondary small" data-a="restore">Wiederherstellen</button><button class="btn danger small" data-a="purge">Endgültig löschen</button>'
          : '<span class="muted small">nur Ersteller oder Admin</span>'}</div>
      </li>`).join("")}</ul>`
      : '<p class="muted">Der Papierkorb ist leer.</p>'}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`,
      (dlg, body) => {
        body.querySelectorAll("[data-a]").forEach((b) => b.onclick = async () => {
          const li = b.closest("li");
          const id = +li.dataset.id;
          const title = li.querySelector("strong").textContent;
          try {
            if (b.dataset.a === "restore") {
              await api(`/api/wiki/pages/${id}/restore`, { method: "POST", body: {} });
              toast("Wiederhergestellt");
            } else {
              if (!(await S.confirm(`„${title}“ und alle Unterseiten endgültig löschen? Das lässt sich nicht rückgängig machen.`,
                                    "Endgültig löschen"))) return;
              await api(`/api/wiki/trash/${id}`, { method: "DELETE" });
              toast("Endgültig gelöscht");
            }
            dlg.close();
            await loadTree();
            trashDialog();
          } catch (e) { toast(e.message, true); }
        });
      });
  }

  function wireLinks(root) {
    root.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (/^https?:\/\//i.test(href) && !href.startsWith(location.origin)) { a.target = "_blank"; a.rel = "noopener"; }
      else if (href.startsWith("/wiki/")) a.addEventListener("click", (e) => { e.preventDefault(); navigate(href.slice(6)); });
      else if (href.startsWith("#") && href.length > 1) a.addEventListener("click", (e) => {
        const ziel = document.getElementById(decodeURIComponent(href.slice(1)));
        if (!ziel) return;
        e.preventDefault();
        ziel.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(history.state, "", href);
      });
    });
  }

  /* ======================================================================
     Seitenansicht: Artikel, Inhaltsverzeichnis, Kommentare
     ====================================================================== */
  function renderBody(p) {
    return MD.render(p.content);
  }

  /* Brotkrumen oben links – wie in Docmost mit dem Symbol der jeweiligen Seite.
     Sie stehen in beiden Ansichten an derselben Stelle, damit beim Umschalten nichts springt. */
  function krumenPfad(crumbs, p, neu) {
    const glied = (c, aktiv) => aktiv
      ? `<span class="krume" aria-current="page">${c.icon ? `<span class="krume-icon">${esc(c.icon)}</span>` : ""}${esc(c.title)}</span>`
      : `<a class="krume" href="/wiki/${esc(c.slug)}">${c.icon ? `<span class="krume-icon">${esc(c.icon)}</span>` : ""}${esc(c.title)}</a>`;
    const kette = [...crumbs.map((c) => glied(c, false)),
                   glied({ icon: p.icon, title: neu ? "Neue Seite" : (p.title || "Ohne Titel"), slug: p.slug }, true)];
    return `<nav class="krumen" aria-label="Pfad">${kette.join('<span class="krume-sep" aria-hidden="true">/</span>')}</nav>`;
  }

  /* Autorzeile unter der Überschrift, samt Knopf für die Angaben zur Seite. */
  const initialen = (name) => String(name || "?").trim().split(/\s+/).slice(0, 2).map((t) => t[0] || "").join("").toUpperCase() || "?";
  /* Der Kreis vor einem Namen: das hochgeladene Profilbild, sonst die Initialen. Die Adresse kommt
     vom Server und zeigt stets nach /media/avatar/ – fremde Ziele haben hier nichts zu suchen. */
  const bildAdresse = (u) => {
    const a = String((u && (u.avatar || u.created_by_avatar)) || "");
    return a.startsWith("/media/avatar/") ? a : "";
  };
  const avatarInhalt = (u, name) => {
    const a = bildAdresse(u);
    return a ? `<img src="${esc(a)}" alt="" loading="lazy">` : esc(initialen(name));
  };
  /* Wer an einer Seite geschrieben hat – aufgeklappt am Autorennamen, wie in Docmost. */
  let autorZu = null;
  async function autorTafel(p, anker) {
    if (autorZu) { autorZu(); return; }
    const box = document.createElement("div");
    box.className = "autor-tafel";
    box.innerHTML = '<div class="muted small">wird geladen …</div>';
    document.body.appendChild(box);
    const stelle = () => {
      const r = anker.getBoundingClientRect();
      box.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - box.offsetWidth - 8, r.left))}px`;
      box.style.top = `${window.scrollY + r.bottom + 6}px`;
    };
    stelle();
    const zu = () => {
      box.remove();
      document.removeEventListener("pointerdown", aussen, true);
      window.removeEventListener("resize", stelle);
      autorZu = null;
      if (anker.focus) anker.focus();
    };
    const aussen = (e) => { if (!box.contains(e.target) && e.target !== anker) zu(); };
    setTimeout(() => document.addEventListener("pointerdown", aussen, true), 0);
    window.addEventListener("resize", stelle);
    box.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); zu(); } });
    autorZu = zu;
    const person = (u, rolle) => `<div class="autor-person">
        <span class="avatar${rolle ? "" : " mit"}" aria-hidden="true">${avatarInhalt(u, u.name || u.email)}</span>
        <span class="autor-text"><span class="autor-nam">${esc(u.name || u.email || "unbekannt")}</span>${
          rolle ? `<span class="autor-rolle">${esc(rolle)}</span>` : ""}</span>
      </div>`;
    try {
      const r = await api(`/api/wiki/pages/${p.id}/contributors`);
      const mit = r.contributors || [];
      // Umschreiben darf nur die Administration – am Ersteller hängen Rechte, nicht bloß ein Name.
      const darfWechseln = !!(STROEMIS.user && STROEMIS.user.role === "admin");
      box.innerHTML = (r.owner ? person(r.owner, "Ersteller") : "")
        + (darfWechseln ? '<button class="lnk autor-wechsel" id="au-wechsel" type="button">Ersteller ändern …</button>' : "")
        + (mit.length ? `<div class="autor-trenner"></div><div class="autor-titel">Mitwirkende</div>`
                        + mit.map((u) => person(u, "")).join("") : "");
      const w = box.querySelector("#au-wechsel");
      if (w) w.onclick = () => { zu(); erstellerDialog(p, r.owner); };
      stelle();
    } catch (e) {
      box.innerHTML = `<div class="muted small">${esc(e.message)}</div>`;
    }
  }

  /* Ersteller umschreiben. Gebraucht wird das nach einem Import – dort trägt jede Seite den
     Namen dessen, der die Ausfuhr eingespielt hat – und wenn jemand die Gliederung verlässt.
     Der Dialog sagt, dass die Rechte mitgehen: Wer hier steht, darf die Seite löschen und
     Bearbeiter freigeben. */
  async function erstellerDialog(p, bisher) {
    if (!state.users) { try { state.users = (await api("/api/wiki/users")).users; } catch (e) { state.users = []; } }
    const liste = state.users.map((u) => `
        <label class="inline"><input type="radio" name="au-wahl" value="${u.id}"${u.id === p.created_by ? " checked" : ""}> ${esc(u.name || "Unbenannt")} <span class="muted small">${esc(u.gliederung || "")}</span></label>`).join("");
    dialog(`<h2>Ersteller ändern</h2>
      <p class="help">Der Name steht als „Von …“ unter dem Titel. Mit ihm wechseln auch seine Rechte an
        dieser Seite: löschen und Bearbeiter freigeben.${bisher ? ` Bisher: <strong>${esc(bisher.name || "unbekannt")}</strong>.` : ""}</p>
      <input type="search" id="au-filter" placeholder="Nutzer suchen …">
      <div class="user-pick" id="au-users">${liste || '<div class="muted small">Keine Nutzer gefunden.</div>'}</div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="au-ok" type="button">Übernehmen</button></div>`,
      (dlg, body) => {
        const filter = body.querySelector("#au-filter");
        filter.addEventListener("input", () => {
          const q = filter.value.toLowerCase();
          body.querySelectorAll("#au-users label").forEach((l) => l.classList.toggle("hidden", !!q && !l.textContent.toLowerCase().includes(q)));
        });
        body.querySelector("#au-ok").onclick = async () => {
          const wahl = body.querySelector('input[name="au-wahl"]:checked');
          if (!wahl) { toast("Bitte einen Nutzer wählen.", true); return; }
          try {
            const r = await api(`/api/wiki/pages/${p.id}/creator`, { method: "PUT", body: { user_id: +wahl.value } });
            Object.assign(p, r.page);
            if (state.current && state.current.id === p.id) Object.assign(state.current, r.page);
            dlg.close();
            toast("Ersteller geändert");
            await loadTree();                 // der Baum führt den Namen mit
            await renderPage();
          } catch (e) { toast(e.message, true); }
        };
      });
  }

  function autorZeile(p) {
    return `<div class="autorzeile">
      <button type="button" class="autor-knopf" aria-haspopup="dialog" title="Wer an dieser Seite geschrieben hat">
        <span class="avatar" aria-hidden="true">${avatarInhalt(p, p.created_by_name)}</span>
        <span class="autorname">Von ${esc(p.created_by_name || "unbekannt")}</span>
      </button>
      <button type="button" class="rundknopf" id="pg-info" title="Angaben zur Seite" aria-label="Angaben zur Seite">i</button>
      ${p.read_restricted ? '<span class="rundknopf still" title="Nur für freigegebene Nutzer lesbar" aria-label="Nur für freigegebene Nutzer lesbar">🔒</span>' : ""}
    </div>`;
  }

  async function renderPage() {
    // Bei offenem Editor (Merkliste, Symbol, Ersteller aus dem Editor heraus geändert) bleibt der
    // Editor stehen – nur der Baum wird nachgeführt. Sonst stünde die Leseansicht über einem
    // Editor, der weiter speichert.
    if (state.editor) { renderTree(); return; }
    seitenInfoSchliessen();
    const p = state.current;
    const crumbs = ancestors(p);
    const kids = children(p.id);
    const pubBadge = p.effective_public ? '<span class="badge pubbadge" title="Ohne Anmeldung erreichbar">🌐 öffentlich</span>' : "";
    content.innerHTML = `
      <div class="wiki-head">
        <button class="btn ghost small kopfknopf baum-knopf" id="pg-baum" type="button" title="Seiten" aria-label="Seitenbaum öffnen">☰</button>
        ${krumenPfad(crumbs, p)}
        <div class="btn-row">
          ${p.can_edit ? `<div class="mode-toggle" role="group" aria-label="Ansicht wechseln">
            <button type="button" id="pg-edit" data-mode="bearbeiten" aria-pressed="false">Bearbeiten</button>
            <button type="button" class="on" data-mode="lesen" aria-pressed="true">Lesen</button>
          </div>` : ""}
          <button class="btn ghost small kopfknopf" id="pg-comment" title="Kommentieren – Text markieren oder allgemein zur Seite" aria-label="Kommentieren">💬</button>
          ${p.can_share || p.can_publish ? `<button class="btn ghost small kopfknopf" id="pg-share" title="Teilen" aria-label="Teilen">${I.teilen}</button>` : ""}
          ${tocKnopf()}
          <button class="btn ghost small kopfknopf" id="pg-more" title="Weitere Aktionen" aria-label="Weitere Aktionen">⋯</button>
        </div>
      </div>
      <h1 class="seitentitel"><button class="page-icon" id="pg-icon" type="button" title="Symbol der Seite ändern">${p.icon ? esc(p.icon) : "＋"}</button>${esc(p.title)} ${pubBadge}</h1>
      ${autorZeile(p)}
      <article class="wiki-content" id="article"></article>
      ${kids.length ? `<div class="children-list"><strong>Unterseiten</strong><ul>${kids.map((k) => `<li><a href="/wiki/${esc(k.slug)}">${k.icon ? esc(k.icon) + " " : ""}${esc(k.title)}</a></li>`).join("")}</ul></div>` : ""}
      <div id="pg-backlinks"></div>
      <div id="pg-attachments"></div>`;

    artikelZeichnen(p);
    wireLinks(content);

    const ed = $("#pg-edit"); if (ed) ed.onclick = () => bearbeitenStarten(p);
    // Der Kopf ist neu – Anwesenheitsmarke und Knopfstand kommen aus dem letzten Herzschlag.
    praesenzAnzeigen();
    const info = $("#pg-info"); if (info) info.onclick = () => seitenInfo(p, info);
    const autorKnopf = content.querySelector(".autor-knopf");
    if (autorKnopf && p.id) autorKnopf.onclick = () => autorTafel(p, autorKnopf);
    $("#pg-comment").onclick = () => commentDialog("");
    $("#pg-icon").onclick = () => iconDialog(p.id, p.icon || "");
    tocKnopfVerdrahten();
    const baum = $("#pg-baum"); if (baum) baum.onclick = () => side.classList.toggle("open");
    $("#pg-more").onclick = (e) => pageMenu(e.currentTarget, p);
    const sh = $("#pg-share"); if (sh) sh.onclick = () => shareDialog(p);
    loadBacklinks(p);
    loadAttachments(p);
    await loadComments();
  }

  /* Den Artikel in den stehenden Rahmen zeichnen – beim Aufbau der Seite wie beim Nachziehen
     aus dem Herzschlag. Verzeichnis und Scrollspy hängen am Artikel und entstehen mit ihm. */
  function artikelZeichnen(p) {
    const art = $("#article");
    art.innerHTML = renderBody(p);
    const first = art.firstElementChild;
    if (first && first.tagName === "H1" && first.textContent.trim().toLowerCase() === p.title.trim().toLowerCase()) first.remove();
    wireLinks(art);
    renderRail(MD.buildToc(art));
    // Eingebundene Abschnitte holen sich ihre Quellseite über die gewöhnliche Schnittstelle –
    // damit gelten deren Leserechte, ohne dass sie hier ein zweites Mal geprüft werden müssten.
    MD.enhance(art, { children: children(p.id),
                      holeSeite: (slug) => api(`/api/wiki/pages/${encodeURIComponent(slug)}`).then((d) => d.page) });
    if (state.spy) state.spy();
    state.spy = MD.tocScrollspy(art, tocEl);
  }

  /* Löschen legt in den Papierkorb – von dort wiederherstellbar. */
  async function trashPage(p) {
    const n = children(p.id).length;
    if (!(await S.confirm(
      `Seite „${p.title}“ in den Papierkorb legen?${n ? ` ${n} Unterseite${n > 1 ? "n kommen" : " kommt"} mit.` : ""}`,
      "In den Papierkorb"))) return;
    try {
      await api(`/api/wiki/pages/${p.id}`, { method: "DELETE" });
      toast("In den Papierkorb gelegt");
      await loadTree();
      navigate(p.parent_id && state.byId.get(p.parent_id) ? state.byId.get(p.parent_id).slug : "");
    } catch (e) { toast(e.message, true); }
  }

  /* „⋯“ im Seitenkopf: Export, Duplizieren, Vorlage, Papierkorb */
  function pageMenu(anchor, p) {
    const box = document.createElement("div");
    box.className = "tree-menu";
    box.innerHTML = `
      <button type="button" data-a="history">Verlauf …</button>
      <button type="button" data-a="fav">${p.favorite ? "Von der Merkliste nehmen" : "Zur Merkliste"}</button>
      <button type="button" data-a="watch">${p.watch ? "Nicht mehr beobachten" : "Bei Änderungen benachrichtigen"}</button>
      <button type="button" data-a="export">Als Markdown herunterladen</button>
      <button type="button" data-a="exportzip">Abschnitt als ZIP herunterladen</button>
      <button type="button" data-a="print">Drucken / als PDF sichern</button>
      ${p.can_edit ? `<button type="button" data-a="template">${p.is_template ? "Nicht mehr als Vorlage" : "Als Vorlage anbieten"}</button>` : ""}
      <button type="button" data-a="dup">Duplizieren</button>
      ${p.can_delete ? '<button type="button" data-a="del" class="danger">In den Papierkorb</button>' : ""}`;
    document.body.appendChild(box);
    const r = anchor.getBoundingClientRect();
    box.style.left = `${Math.max(8, Math.min(window.innerWidth - box.offsetWidth - 8, r.left))}px`;
    box.style.top = `${window.scrollY + r.bottom + 4}px`;
    const close = () => { box.remove(); document.removeEventListener("pointerdown", onDoc, true); if (anchor && anchor.focus) anchor.focus(); };
    const onDoc = (e) => { if (!box.contains(e.target)) close(); };
    setTimeout(() => document.addEventListener("pointerdown", onDoc, true), 0);
    wireMenuKeys(box, close);
    box.addEventListener("click", async (e) => {
      const b = e.target.closest("button[data-a]");
      if (!b) return;
      const a = b.dataset.a;
      close();
      if (a === "history") return showHistory(p);
      if (a === "fav") return toggleFavorite(p.id, !p.favorite);
      if (a === "watch") {
        try {
          const r = await api(`/api/wiki/pages/${p.id}/watch`, { method: "PUT", body: { watch: !p.watch } });
          p.watch = r.watch;
          toast(r.watch ? "Du wirst bei Änderungen benachrichtigt." : "Beobachtung beendet.");
          await renderPage();
        } catch (err) { toast(err.message, true); }
        return;
      }
      if (a === "export") { window.location.href = `/api/wiki/pages/${p.id}/export`; return; }
      if (a === "exportzip") { window.location.href = `/api/wiki/pages/${p.id}/export?children=1`; return; }
      if (a === "print") { window.print(); return; }
      if (a === "del") return trashPage(p);
      try {
        if (a === "template") {
          const r2 = await api(`/api/wiki/pages/${p.id}/options`, { method: "PUT", body: { is_template: !p.is_template } });
          Object.assign(p, r2.page);
          await loadTree();
          await renderPage();
        } else if (a === "dup") {
          const r2 = await api(`/api/wiki/pages/${p.id}/duplicate`, { method: "POST", body: {} });
          toast("Seite dupliziert");
          await loadTree();
          navigate(r2.page.slug);
        }
      } catch (err) { toast(err.message, true); }
    });
  }

  async function loadBacklinks(p) {
    const box = $("#pg-backlinks");
    if (!box || !p.backlink_count) return;
    try {
      const d = await api(`/api/wiki/pages/${p.id}/backlinks`);
      if (!d.pages.length || state.current !== p) return;   // inzwischen weitergeblättert
      box.innerHTML = `<div class="children-list"><strong>Was hierher verweist</strong><ul>${d.pages.map((k) =>
        `<li><a href="/wiki/${esc(k.slug)}">${k.icon ? esc(k.icon) + " " : ""}${esc(k.title)}</a></li>`).join("")}</ul></div>`;
      wireLinks(box);
    } catch (e) { /* Rückverweise sind Beiwerk */ }
  }

  async function loadAttachments(p) {
    const box = $("#pg-attachments");
    if (!box) return;
    try {
      const d = await api(`/api/wiki/pages/${p.id}/attachments`);
      // Nach Endung filtern, nicht nach der Datenbankspalte: importierte Anhänge haben keine.
      const DOC = /\.(pdf|docx?|odt|rtf|xlsx?|ods|csv|pptx?|odp|txt|zip|gpx|kmz?)$/i;
      const files = d.files.filter((f) => f.kind === "file" || DOC.test(f.file));
      if (!files.length || state.current !== p) return;     // inzwischen weitergeblättert
      const kb = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " kB");
      box.innerHTML = `<div class="children-list"><strong>Anhänge dieser Seite</strong><ul>${files.map((f) =>
        `<li><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.original_name || f.file)}</a>`
        + `${f.size ? ` <span class="muted small">${kb(f.size)}</span>` : ""}</li>`).join("")}</ul></div>`;
    } catch (e) { /* Anhangsliste ist Beiwerk */ }
  }

  function renderRail(tocItems) {
    tocEl.innerHTML = tocItems.length ? `<div class="rail-title">Inhalt</div>${MD.tocHtml(tocItems)}` : "";
    tocEl.querySelectorAll("a").forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault();
      const t = document.getElementById(a.getAttribute("href").slice(1));
      if (t) { t.scrollIntoView({ behavior: "smooth", block: "start" }); history.replaceState(null, "", a.getAttribute("href")); }
    }));
    if (!state.current) commentsEl.innerHTML = "";
  }

  /* Inhaltsverzeichnis aus den Überschriften des Editors. Die Sprungziele stehen als
     Elementverweise in einer Liste, nicht als id im Dokument: eine id am Knoten wäre eine
     DOM-Änderung, die ProseMirror als Bearbeitung deuten würde. */
  let editorSprungziele = [];
  function renderEditorRail() {
    const el = document.querySelector(".toastui-editor-ww-container .ProseMirror");
    if (!el) return;
    const kinder = Array.from(el.children);
    const items = [];
    editorSprungziele = [];
    kinder.forEach((h, i) => {
      if (!/^H[1-5]$/.test(h.tagName)) return;
      if (i === 0) return;                       // die erste Überschrift ist der Seitentitel
      const text = h.textContent.trim();
      if (!text) return;
      items.push({ id: `ed-toc-${editorSprungziele.length}`, level: +h.tagName[1], text });
      editorSprungziele.push(h);
    });
    tocEl.innerHTML = items.length ? `<div class="rail-title">Inhalt</div>${MD.tocHtml(items)}` : "";
    tocEl.querySelectorAll("a").forEach((a, i) => a.addEventListener("click", (e) => {
      e.preventDefault();
      const ziel = editorSprungziele[i];
      if (ziel) ziel.scrollIntoView({ behavior: "smooth", block: "start" });
    }));
  }

  /* --- Angaben zur Seite: rechte Leiste mit Herkunft, Umfang und Verweisen -----
     Die Zahlen zu Wörtern und Zeichen entstehen aus dem gerenderten Artikel, nicht aus
     dem Markdown – gezählt wird, was auch dasteht. */
  let infoOffen = false;
  /* Beim Seitenwechsel und beim Öffnen des Editors zuklappen – sonst stünden dort die
     Angaben der vorher besuchten Seite, ohne dass es jemand merkt. */
  function seitenInfoSchliessen() {
    infoOffen = false;
    const box = $("#seiten-info");
    if (box) { box.classList.add("hidden"); box.innerHTML = ""; }
  }
  async function seitenInfo(p, knopf) {
    const box = $("#seiten-info");
    if (!box) return;
    infoOffen = !infoOffen;
    if (knopf) knopf.classList.toggle("on", infoOffen);
    if (!infoOffen) { box.classList.add("hidden"); box.innerHTML = ""; return; }
    // Beim Lesen steht der Artikel im DOM, beim Bearbeiten im Editor – sonst zählte die
    // Angabe im Editor immer null.
    const quelle = $("#article") || document.querySelector(".toastui-editor-ww-container .ProseMirror");
    // Gezählt wird der Artikel, nicht die Bedienung: „Kopieren“ am Codeblock, das „#“ hinter
    // jeder Überschrift und die Sortierpfeile der Tabellen sind kein Text der Seite.
    let text = "";
    if (quelle) {
      const abschrift = quelle.cloneNode(true);
      abschrift.querySelectorAll(".code-copy, .h-anchor, .th-sort, .cbadge, .ed-nichtinhalt").forEach((el) => el.remove());
      text = abschrift.textContent.replace(/\s+/g, " ").trim();
    }
    const woerter = text ? text.split(" ").length : 0;
    const zeilen = [
      ["Angelegt von", esc(p.created_by_name || "unbekannt")],
      ["Zuletzt geändert von", esc(p.updated_by_name || p.created_by_name || "unbekannt")],
      ["Angelegt", esc(fmtDate(p.created_at, true))],
      ["Zuletzt geändert", esc(fmtDate(p.updated_at, true))],
      ["Wörter", String(woerter)],
      ["Zeichen", String(text.length)],
      ["Lesezeit", (() => { const m = Math.max(1, Math.round(woerter / 200)); return `etwa ${m} ${m === 1 ? "Minute" : "Minuten"}`; })()],
      ["Kommentare", String(p.comment_count || 0)],
    ];
    if (schmalesRaster.matches) setTimeout(() => box.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    box.innerHTML = `<div class="rail-title">Angaben zur Seite</div>
      <dl class="info-liste">${zeilen.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      <div class="info-verweise" id="info-verweise"><span class="muted small">Verweise werden geladen …</span></div>`;
    box.classList.remove("hidden");
    try {
      const d = await api(`/api/wiki/pages/${p.id}/backlinks`);
      const liste = (titel, seiten) => `<div class="rail-title">${titel} (${seiten.length})</div>` + (seiten.length
        ? `<ul class="info-links">${seiten.map((q) => `<li><a href="/wiki/${esc(q.slug)}">${q.icon ? esc(q.icon) + " " : ""}${esc(q.title)}</a></li>`).join("")}</ul>`
        : '<p class="muted small">keine</p>');
      const ziel = $("#info-verweise");
      if (!ziel) return;
      ziel.innerHTML = liste("Verweise hierher", d.pages || []) + liste("Verweise von hier", d.outgoing || []);
      wireLinks(ziel);
    } catch (e) {
      const ziel = $("#info-verweise");
      if (ziel) ziel.innerHTML = '<p class="muted small">Verweise ließen sich nicht laden.</p>';
    }
  }

  /* --- Kommentare ----------------------------------------------------------- */
  async function loadComments() {
    const p = state.current;
    if (!p) return;
    let geladen;
    try { geladen = (await api(`/api/wiki/pages/${p.id}/comments`)).comments; }
    catch (e) { geladen = []; }
    // Während der Anfrage kann der Nutzer längst auf einer anderen Seite sein.
    if (!state.current || state.current.id !== p.id) return;
    state.comments = geladen;
    renderComments();
    anchorComments();
  }

  function renderComments() {
    const list = state.comments;
    const tops = list.filter((c) => !c.parent_id);
    const replies = (id) => list.filter((c) => c.parent_id === id);
    const one = (c, isReply) => `
      <div class="comment${c.resolved ? " resolved" : ""}${isReply ? " reply" : ""}" data-cid="${c.id}">
        <div class="c-head"><strong>${esc(c.user_name || "Unbekannt")}</strong> <span class="muted small">${fmtDate(c.created_at, true)}</span></div>
        ${c.quote && !isReply ? `<blockquote class="c-quote" title="Zur Textstelle springen">${esc(c.quote)}</blockquote>` : ""}
        <div class="c-body">${esc(c.body)}</div>
        <div class="c-actions">
          ${!isReply ? `<button class="lnk" data-reply="${c.id}">Antworten</button>` : ""}
          ${c.can_edit ? `<button class="lnk" data-edit="${c.id}">Bearbeiten</button>` : ""}
          ${!isReply && c.can_delete ? `<button class="lnk" data-resolve="${c.id}">${c.resolved ? "Wieder öffnen" : "Erledigt"}</button>` : ""}
          ${c.can_delete ? `<button class="lnk" data-del="${c.id}">Löschen</button>` : ""}
        </div>
        ${!isReply ? replies(c.id).map((r) => one(r, true)).join("") : ""}
      </div>`;
    const open = tops.filter((c) => !c.resolved);
    const doneList = tops.filter((c) => c.resolved);
    const shown = state.commentFilter === "done" ? doneList : open;
    commentsEl.innerHTML = `<div class="rail-title">Kommentare</div>
      <div class="c-tabs">
        <button type="button" class="${state.commentFilter === "done" ? "" : "sel"}" data-tab="open">Offen (${open.length})</button>
        <button type="button" class="${state.commentFilter === "done" ? "sel" : ""}" data-tab="done">Erledigt (${doneList.length})</button>
      </div>
      ${shown.length ? shown.map((c) => one(c, false)).join("")
        : `<div class="muted small">${state.commentFilter === "done" ? "Nichts erledigt." : "Noch keine offenen Kommentare. Text im Artikel markieren, um eine Stelle zu kommentieren."}</div>`}`;
    commentsEl.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => {
      state.commentFilter = b.dataset.tab;
      renderComments();
    });
    commentsEl.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => {
      const c = state.comments.find((x) => x.id === +b.dataset.edit);
      if (!c) return;
      dialog(`<h2>Kommentar bearbeiten</h2>
        <label for="ce-text">Text</label><textarea id="ce-text">${esc(c.body)}</textarea>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="ce-ok" type="button">Speichern</button></div>`,
        (dlg, body) => {
          body.querySelector("#ce-ok").onclick = async () => {
            const txt = body.querySelector("#ce-text").value.trim();
            if (!txt) return toast("Der Kommentar ist leer.", true);
            try {
              await api(`/api/wiki/comments/${c.id}`, { method: "PUT", body: { body: txt } });
              dlg.close(); await loadComments(); toast("Kommentar geändert");
            } catch (e) { toast(e.message, true); }
          };
        });
    });
    commentsEl.querySelectorAll("[data-reply]").forEach((b) => b.onclick = () => commentDialog("", +b.dataset.reply));
    commentsEl.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => {
      if (!(await S.confirm("Kommentar löschen?"))) return;
      try { await api(`/api/wiki/comments/${b.dataset.del}`, { method: "DELETE" }); await loadComments(); } catch (e) { toast(e.message, true); }
    });
    commentsEl.querySelectorAll("[data-resolve]").forEach((b) => b.onclick = async () => {
      const c = state.comments.find((x) => x.id === +b.dataset.resolve);
      try { await api(`/api/wiki/comments/${c.id}`, { method: "PUT", body: { resolved: !c.resolved } }); await loadComments(); } catch (e) { toast(e.message, true); }
    });
    commentsEl.querySelectorAll(".c-quote").forEach((q) => q.onclick = () => {
      const cid = q.closest(".comment").dataset.cid;
      const m = content.querySelector(`mark.cq[data-cid="${cid}"], .cbadge[data-cid="${cid}"]`);
      if (m) { m.scrollIntoView({ behavior: "smooth", block: "center" }); m.classList.add("flash"); setTimeout(() => m.classList.remove("flash"), 2000); }
      else toast("Die Textstelle wurde im Artikel nicht mehr gefunden.");
    });
  }

  /* Zitierte Textstellen im Artikel markieren */
  function anchorComments() {
    const art = $("#article");
    if (!art) return;                       // im Editor gibt es keinen Artikel zum Markieren
    art.querySelectorAll("mark.cq").forEach((m) => m.replaceWith(...m.childNodes));
    art.querySelectorAll(".cbadge").forEach((b) => b.remove());
    art.normalize();
    for (const c of state.comments.filter((x) => !x.parent_id && x.quote && !x.resolved)) {
      const hit = findText(art, c.quote, c.quote_before, c.quote_after);
      if (!hit) continue;
      const range = document.createRange();
      range.setStart(hit.startNode, hit.startOffset);
      range.setEnd(hit.endNode, hit.endOffset);
      const mark = document.createElement("mark");
      mark.className = "cq"; mark.dataset.cid = c.id; mark.title = `Kommentar von ${c.user_name || ""}`;
      try { range.surroundContents(mark); }
      catch (e) { // Auswahl reicht über mehrere Elemente: nur ein Hinweis am Anfang
        const badge = document.createElement("span");
        badge.className = "cbadge"; badge.dataset.cid = c.id; badge.textContent = "💬"; badge.title = mark.title;
        range.collapse(true); range.insertNode(badge);
      }
    }
    art.querySelectorAll("mark.cq, .cbadge").forEach((m) => m.addEventListener("click", () => {
      const el = commentsEl.querySelector(`.comment[data-cid="${m.dataset.cid}"]`);
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 2000); }
    }));
  }

  /* Text im Artikel finden (Whitespace-tolerant) und auf Textknoten abbilden */
  function findText(root, needle, before, after) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let text = "";
    for (let n = walker.nextNode(); n; n = walker.nextNode()) { nodes.push({ node: n, start: text.length }); text += n.nodeValue; }
    const q = needle.replace(/\s+/g, " ").trim();
    if (!q || !nodes.length) return null;
    const map = []; let hay = ""; let lastWs = false;
    for (let i = 0; i < text.length; i++) {
      const ws = /\s/.test(text[i]);
      if (ws && lastWs) continue;
      hay += ws ? " " : text[i]; map.push(i); lastWs = ws;
    }
    // Bei mehreren Fundstellen die nehmen, deren Umfeld am besten passt.
    const norm = (t) => String(t || "").replace(/\s+/g, " ").trim();
    const pre = norm(before), post = norm(after);
    const spots = [];
    for (let at = hay.indexOf(q); at >= 0; at = hay.indexOf(q, at + 1)) spots.push(at);
    if (!spots.length) return null;
    let idx = spots[0];
    if (spots.length > 1 && (pre || post)) {
      let best = -1;
      for (const at of spots) {
        // pre/post sind getrimmt – die Fenster müssen es auch sein, sonst scheitert der
        // Vergleich an jedem Wortzwischenraum, und immer die erste Fundstelle gewinnt.
        const b = hay.slice(Math.max(0, at - pre.length - 1), at).trimEnd();
        const a = hay.slice(at + q.length, at + q.length + post.length + 1).trimStart();
        const score = (pre && b.endsWith(pre.slice(-Math.min(pre.length, b.length))) ? pre.length : 0)
          + (post && a.startsWith(post.slice(0, Math.min(post.length, a.length))) ? post.length : 0);
        if (score > best) { best = score; idx = at; }
      }
    }
    const s = map[idx], e = map[idx + q.length - 1] + 1;
    const locate = (pos, isEnd) => {
      for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        if (isEnd ? pos > n.start : pos >= n.start) return { node: n.node, offset: Math.min(pos - n.start, n.node.nodeValue.length) };
      }
      return { node: nodes[0].node, offset: 0 };
    };
    const a = locate(s, false), b = locate(e, true);
    return { startNode: a.node, startOffset: a.offset, endNode: b.node, endOffset: b.offset };
  }

  /* Schwebender Knopf bei Textauswahl im Artikel */
  function hideFab() { fab.classList.add("hidden"); }
  document.addEventListener("selectionchange", () => {
    const sel = document.getSelection();
    const art = $("#article");
    if (!art || !state.current || !sel || sel.isCollapsed || !sel.rangeCount) return hideFab();
    const range = sel.getRangeAt(0);
    if (!art.contains(range.commonAncestorContainer)) return hideFab();
    const txt = sel.toString().trim();
    if (txt.length < 2) return hideFab();
    const r = range.getBoundingClientRect();
    const grob = window.matchMedia("(pointer: coarse)").matches;
    fab.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - 170, r.left + r.width / 2 - 80))}px`;
    // Auf dem Telefon liegt über der Auswahl das Systemmenü (Kopieren …) – der Knopf geht darunter.
    fab.style.top = `${window.scrollY + (grob ? r.bottom + 12 : r.top - 40)}px`;
    // Gespeichert wird höchstens ein halbes Tausend Zeichen – das Umfeld muss sich auf genau
    // diesen Ausschnitt beziehen, sonst sucht das Wiederfinden später mit einem „danach“,
    // das im Text gar nicht an dieser Stelle steht.
    const zitat = txt.slice(0, 500);
    fab.dataset.quote = zitat;
    try {
      const all = art.textContent;
      const pre = document.createRange();
      pre.setStart(art, 0);
      pre.setEnd(range.startContainer, range.startOffset);
      // Der Zitattext ist getrimmt; die Auswahl darf mit Leerraum beginnen. Um genau diese
      // Zeichen liegt der Anfang des Zitats weiter hinten als der Anfang der Auswahl.
      const roh = sel.toString();
      const at = pre.toString().length + (roh.length - roh.trimStart().length);
      fab.dataset.qbefore = all.slice(Math.max(0, at - 60), at);
      fab.dataset.qafter = all.slice(at + zitat.length, at + zitat.length + 60);
    } catch (e) { fab.dataset.qbefore = ""; fab.dataset.qafter = ""; }
    fab.classList.remove("hidden");
  });
  fab.addEventListener("mousedown", (e) => e.preventDefault());
  // iOS hebt die Auswahl beim Tippen auf – noch vor dem click; touchend kommt davor.
  fab.addEventListener("touchend", (e) => { e.preventDefault(); fab.click(); }, { passive: false });
  fab.addEventListener("click", () => {
    const q = fab.dataset.quote;
    const ctx = { before: fab.dataset.qbefore || "", after: fab.dataset.qafter || "" };
    hideFab();
    commentDialog(q, null, ctx);
  });

  function commentDialog(quote, parentId, ctx) {
    const p = state.current;
    dialog(`<h2>${parentId ? "Antwort" : "Kommentar"} zu „${esc(p.title)}“</h2>
      ${quote ? `<blockquote class="c-quote">${esc(quote)}</blockquote>` : (parentId ? "" : '<p class="help">Ohne markierte Textstelle gilt der Kommentar für die ganze Seite. Um eine Stelle zu kommentieren: Text im Artikel markieren und auf „Kommentieren“ tippen.</p>')}
      <label for="c-text">Kommentar</label><textarea id="c-text" autofocus></textarea>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="c-save" type="button">Speichern</button></div>`,
      (dlg, body) => {
        body.querySelector("#c-save").onclick = async () => {
          const text = body.querySelector("#c-text").value.trim();
          if (!text) return toast("Der Kommentar ist leer.", true);
          try {
            await api(`/api/wiki/pages/${p.id}/comments`, { method: "POST", body: {
              body: text, quote: quote || "", parent_id: parentId || null,
              quote_before: (ctx && ctx.before) || "", quote_after: (ctx && ctx.after) || "" } });
            dlg.close(); toast("Kommentar gespeichert"); await loadComments();
          } catch (e) { toast(e.message, true); }
        };
      });
  }

  /* --- Teilen: Bearbeiter und öffentliche Freigabe ------------------------------ */
  async function shareDialog(p) {
    if (!state.users) { try { state.users = (await api("/api/wiki/users")).users; } catch (e) { state.users = []; } }
    const editorIds = new Set((p.editors || []).map((u) => u.id));
    const publicLink = `${STROEMIS.publicUrl}/${p.slug}`;
    dialog(`<h2>Teilen: ${esc(p.title)}</h2>
      ${p.can_share ? `<h3>Bearbeiten erlauben</h3>
      <p class="help">Freigegebene Nutzer dürfen diese Seite und ihre Unterseiten bearbeiten, aber nicht löschen.</p>
      <input type="search" id="sh-filter" placeholder="Nutzer suchen …">
      <div class="user-pick" id="sh-users">${state.users.filter((u) => u.id !== p.created_by).map((u) => `
        <label class="inline"><input type="checkbox" value="${u.id}" ${editorIds.has(u.id) ? "checked" : ""}> ${esc(u.name || "Unbenannt")} <span class="muted small">${esc(u.gliederung || "")}</span></label>`).join("") || '<div class="muted small">Keine weiteren Nutzer.</div>'}</div>` : ""}
      ${p.can_share ? `<h3 style="margin-top:18px">Lesen einschränken</h3>
      <p class="help">Normalerweise darf jeder Angemeldete jede Seite lesen. Eingeschränkt sehen die Seite
      und ihre Unterseiten nur noch du, die Administration und die oben freigegebenen Nutzer.</p>
      <label class="inline"><input type="checkbox" id="sh-restrict" ${p.read_restricted ? "checked" : ""}
        ${p.effective_public ? "disabled" : ""}> Nur für freigegebene Nutzer lesbar</label>
      ${p.effective_public ? '<div class="help">Nicht möglich, solange die Seite öffentlich freigegeben ist.</div>' : ""}` : ""}
      ${p.can_publish ? `<h3 style="margin-top:18px">Öffentlich freigeben</h3>
      <p class="help">Öffentliche Seiten sind ohne Anmeldung über den Link unten erreichbar – samt ihrer Bilder und Videos.</p>
      <label class="inline"><input type="checkbox" id="sh-public" ${p.is_public ? "checked" : ""}> Diese Seite öffentlich zeigen</label>
      <label class="inline"><input type="checkbox" id="sh-children" ${p.public_children ? "checked" : ""} ${p.is_public ? "" : "disabled"}> … einschließlich aller Unterseiten (ganzer Abschnitt)</label>
      <div class="share-link ${p.is_public ? "" : "hidden"}" id="sh-link"><input type="text" readonly value="${esc(publicLink)}" id="sh-url"><button class="btn secondary small" id="sh-copy" type="button">Kopieren</button></div>`
      : (p.effective_public ? `<p class="notice">Diese Seite ist über einen freigegebenen Abschnitt öffentlich: <a href="${esc(publicLink)}" target="_blank" rel="noopener">${esc(publicLink)}</a></p>` : "")}
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button><button class="btn" id="sh-save" type="button">Speichern</button></div>`,
      (dlg, body) => {
        const filter = body.querySelector("#sh-filter");
        if (filter) filter.addEventListener("input", () => {
          const q = filter.value.toLowerCase();
          body.querySelectorAll("#sh-users label").forEach((l) => l.classList.toggle("hidden", !!q && !l.textContent.toLowerCase().includes(q)));
        });
        const pub = body.querySelector("#sh-public");
        if (pub) pub.addEventListener("change", () => {
          body.querySelector("#sh-children").disabled = !pub.checked;
          body.querySelector("#sh-link").classList.toggle("hidden", !pub.checked);
        });
        const copy = body.querySelector("#sh-copy");
        if (copy) copy.onclick = async () => { try { await navigator.clipboard.writeText(body.querySelector("#sh-url").value); toast("Link kopiert"); } catch (e) { body.querySelector("#sh-url").select(); } };
        body.querySelector("#sh-save").onclick = async () => {
          try {
            if (p.can_share) {
              const ids = Array.from(body.querySelectorAll("#sh-users input:checked")).map((i) => +i.value);
              const r = await api(`/api/wiki/pages/${p.id}/editors`, { method: "PUT", body: { user_ids: ids } });
              p.editors = r.editors;
            }
            const restrict = body.querySelector("#sh-restrict");
            if (restrict && !restrict.disabled && !!p.read_restricted !== restrict.checked) {
              const r = await api(`/api/wiki/pages/${p.id}/restrict`, { method: "PUT", body: { read_restricted: restrict.checked } });
              Object.assign(p, r.page);
            }
            if (p.can_publish && pub) {
              const r = await api(`/api/wiki/pages/${p.id}/share`, { method: "PUT", body: { is_public: pub.checked, public_children: body.querySelector("#sh-children").checked } });
              Object.assign(p, r.page);
            }
            dlg.close(); toast("Freigaben gespeichert");
            await loadTree(); show(p.slug);
          } catch (e) { toast(e.message, true); }
        };
      });
  }

  /* ======================================================================
     Editor (Toast UI, WYSIWYG) – Callouts, Spalten und Videos als Blöcke
     ====================================================================== */

  /* Gespeichert wird Docmost-Markdown (:::info …). Im Editor erscheinen die Blöcke als Toast-UI-Custom-Blocks
     ($$callout / $$columns): gerendert, mit Stift-Symbol zum Bearbeiten. */
  /* Nur die äußersten :::-Blöcke werden zu Editor-Blöcken ($$…$$); verschachtelte Blöcke bleiben als :::-Text
     im Block stehen und werden dort vom Renderer dargestellt (Accordion im Callout, Callout im Accordion usw.). */
  /* Die reinen Umwandlungen zwischen Markdown und Editorformat stehen in
     editor-format.js, die Darstellung der Abschnitte in editor-layout.js. */
  const { toEditorMd, fromEditorMd, SNIPPETS, hinweisKopf, hinweisZeile, hinweisMd,
          bausteinMd, einbauMd, HINWEIS_NAME, ABSCHNITT_AUF } = window.EDMD;
  const layoutPlugin = window.EDLAYOUT.layoutPlugin;
  const zellenAuswahl = window.EDLAYOUT.zellenAuswahl;

  /* Toast UI 3.2.2 hat einen Fehler im Konverter für Tabellenzellen: er entscheidet über
     "steckt in der Zelle Fließtext, der in einen Absatz gehört?" mit node.literal.match(...).
     Widget-Knoten (unsere ++unterstrichen++, ==hervorgehoben==, {status:…}, {{rot:…}}) haben
     literal === null – steht so eine Auszeichnung am Anfang oder Ende einer Zelle, stürzt der
     Editor beim Laden ab und die Seite fällt stumm auf das Markdown-Textfeld zurück.
     Der Konverter liegt als eigene Eigenschaft an der Instanz und wird deshalb hier ersetzt,
     statt das Vendor-Bundle anzufassen. Der Ersatz macht dasselbe wie das Original, entscheidet
     die Frage aber am Knotentyp: alles, was kein Blockknoten ist, ist Fließtext.
     Der Sonderfall htmlInline bleibt wie im Original – dort baut Toast UI den Block selbst. */
  const BLOCKKNOTEN = ["document", "paragraph", "heading", "blockQuote", "bulletList", "orderedList",
                       "item", "codeBlock", "htmlBlock", "thematicBreak", "table", "tableHead",
                       "tableBody", "tableRow", "tableCell", "customBlock", "frontMatter", "refDef"];
  const HTML_TAG = /^<\/?([a-zA-Z][a-zA-Z0-9-]*)/;
  function zellenKonverterReparieren(ed) {
    let konv;
    try { konv = ed.convertor.toWwConvertors; } catch (e) { return; }
    if (!konv || typeof konv.tableCell !== "function") return;
    const original = konv.tableCell;
    konv.tableCell = function (state, node, ctx) {
      try {
        if (node.ignored) return;
        const fliesstext = (n) => {
          if (!n) return false;
          if (n.type === "htmlInline") {
            const m = HTML_TAG.exec(n.literal || "");
            if (!m) return false;
            const tag = m[1].toLowerCase();
            return !!(state.schema.marks[tag] || state.schema.nodes[tag]);
          }
          return !BLOCKKNOTEN.includes(n.type);
        };
        if (ctx.entering) {
          const nodes = state.schema.nodes;
          const rumpf = node.parent.parent;                       // tableHead oder tableBody
          const ziel = rumpf.type === "tableHead" ? nodes.tableHeadCell : nodes.tableBodyCell;
          const ausrichtung = (rumpf.parent.columns[node.startIdx] || {}).align;
          const attrs = Object.assign({}, node.attrs);
          if (ausrichtung) attrs.align = ausrichtung;
          state.openNode(ziel, attrs);
          if (fliesstext(node.firstChild)) state.openNode(nodes.paragraph);
        } else {
          if (fliesstext(node.lastChild)) state.closeNode();
          state.closeNode();
        }
      } catch (e) {
        // Sollte Toast UI die Schnittstelle ändern, lieber das Original nehmen als gar nichts.
        return original.call(this, state, node, ctx);
      }
    };
  }

  const ALIGN_NAME = { left: "links", center: "mittig", right: "rechts", justify: "Blocksatz" };
  const sektionsMarke = (art, text) => [
    { type: "openTag", tagName: "div", outerNewLine: true,
      classNames: ["sek-marke", `sek-${art}`, "ed-marker"] },
    { type: "html", content: `<span>${MD.esc(text)}</span>` },
    { type: "closeTag", tagName: "div", outerNewLine: true },
  ];
  /* Renderer für die Custom-Blocks innerhalb des Editors (Vorschau und WYSIWYG) */
  const customHTMLRenderer = {
    callout(node) {
      const lit = (node.literal || "").split("\n");
      const head = (lit[0] || "").trim().split(/\s+/);
      const kind = head[0] && head[0].toLowerCase() in MD.CALLOUTS ? head[0].toLowerCase() : "info";
      const emoji = head.slice(1).join(" ") || MD.CALLOUTS[kind];
      const body = lit.slice(1).join("\n");
      return [
        { type: "openTag", tagName: "div", outerNewLine: true, classNames: ["callout", `callout-${kind}`] },
        { type: "html", content: `<span class="callout-emoji" aria-hidden="true">${MD.esc(emoji)}</span><div class="callout-body">${MD.render(body)}</div>` },
        { type: "closeTag", tagName: "div", outerNewLine: true },
      ];
    },
    accordion(node) {
      const lit = (node.literal || "").split("\n");
      const title = (lit[0] || "Details").trim();
      return [
        { type: "openTag", tagName: "details", attributes: { class: "accordion", open: "true" }, outerNewLine: true },
        { type: "html", content: `<summary>${MD.esc(title)}</summary><div class="accordion-body">${MD.render(lit.slice(1).join("\n"))}</div>` },
        { type: "closeTag", tagName: "details", outerNewLine: true },
      ];
    },
    align(node) {
      const lit = (node.literal || "").split("\n");
      const mode = MD.ALIGNS.has((lit[0] || "").trim().toLowerCase()) ? lit[0].trim().toLowerCase() : "center";
      return [
        { type: "openTag", tagName: "div", outerNewLine: true, classNames: [`align-${mode}`] },
        { type: "html", content: MD.render(lit.slice(1).join("\n")) },
        { type: "closeTag", tagName: "div", outerNewLine: true },
      ];
    },
    /* Marken der Spalten- und Ausrichtungsabschnitte: eine schmale Zeile, die zeigt, wo der
       Abschnitt anfaengt, wo die naechste Spalte beginnt und wo er endet. Der Inhalt dazwischen
       ist gewoehnlicher Editorinhalt und damit direkt bearbeitbar. */
    /* Die Marken sind nur noch Anfasser: der Abschnitt selbst zeigt im Editor, was er ist –
       eine Hinweiskiste, nebeneinanderliegende Spalten, ausgerichteter Text. */
    hinweis(node) {
      const { kind, emoji } = hinweisKopf(node.literal);
      return sektionsMarke("hinweis", `${emoji} ${HINWEIS_NAME[kind]}`);
    },
    akkordeon() { return sektionsMarke("akkordeon", "Einklappbare Box"); },
    koerper() { return sektionsMarke("koerper", "Inhalt"); },
    spalten() { return sektionsMarke("spalten", "Spalte 1"); },
    spalte() { return sektionsMarke("spalte", "Spalte"); },
    ende() { return sektionsMarke("ende", "Ende"); },
    ausrichtung(node) {
      const mode = MD.ALIGNS.has((node.literal || "").trim().toLowerCase()) ? node.literal.trim().toLowerCase() : "center";
      return sektionsMarke("ausrichtung", ALIGN_NAME[mode]);
    },
    /* Synchronisierte Abschnitte: Der Baustein ist ein gewöhnlicher Abschnitt mit Marke – sein
       Inhalt wird hier bearbeitet. Der Einbau zeigt fremden Text; er ist deshalb kein Inhalt,
       sondern ein Schild mit Herkunft. Geändert wird dort, wo der Baustein steht. */
    baustein(node) {
      return sektionsMarke("baustein", `Baustein „${(node.literal || "").trim() || "abschnitt"}“`);
    },
    einbau(node) {
      const ziel = (node.literal || "").trim();
      const teil = ziel.split("#");
      const wo = (teil[0] || "").trim(), was = (teil[1] || "").trim();
      const text = wo && was ? `Abschnitt „${was}“ aus „${wo}“` : "Einbau ohne Ziel";
      return [{ type: "openTag", tagName: "div", outerNewLine: true, classNames: ["ed-einbau", "ed-marker"] },
              { type: "html", content: `<strong>${MD.esc(text)}</strong>`
                + `<div class="muted small">Der Text steht auf der anderen Seite und wird dort geändert.</div>` },
              { type: "closeTag", tagName: "div", outerNewLine: true }];
    },
    toc() {
      return [{ type: "openTag", tagName: "div", outerNewLine: true, classNames: ["inline-toc", "ed-marker"] },
              { type: "html", content: "<strong>Inhalt</strong><div class=\"muted small\">Die Gliederung erscheint in der Ansicht.</div>" },
              { type: "closeTag", tagName: "div", outerNewLine: true }];
    },
    unterseiten() {
      return [{ type: "openTag", tagName: "div", outerNewLine: true, classNames: ["children-list", "ed-marker"] },
              { type: "html", content: "<strong>Unterseiten</strong><div class=\"muted small\">Die Liste erscheint in der Ansicht.</div>" },
              { type: "closeTag", tagName: "div", outerNewLine: true }];
    },
    seitenumbruch() {
      return [{ type: "openTag", tagName: "div", outerNewLine: true, classNames: ["page-break", "ed-marker"] },
              { type: "html", content: "<span class=\"muted small\">Seitenumbruch beim Drucken</span>" },
              { type: "closeTag", tagName: "div", outerNewLine: true }];
    },
    columns(node) {
      const cols = (node.literal || "").split(/\n[ \t]*\|\|\|[ \t]*\n/);
      return [
        { type: "openTag", tagName: "div", outerNewLine: true, classNames: ["columns", `cols-${cols.length}`] },
        { type: "html", content: cols.map((c) => `<div class="col">${MD.render(c)}</div>`).join("") },
        { type: "closeTag", tagName: "div", outerNewLine: true },
      ];
    },
    image(node, context) {
      const url = node.destination || "";
      if (VIDEO_RE.test(url)) {
        return [
          { type: "openTag", tagName: "video", attributes: { src: url, controls: "true", preload: "metadata" }, outerNewLine: true },
          { type: "closeTag", tagName: "video", outerNewLine: true },
        ];
      }
      if (AUDIO_RE.test(url)) {
        return [
          { type: "openTag", tagName: "audio", attributes: { src: url, controls: "true", preload: "metadata" }, outerNewLine: true },
          { type: "closeTag", tagName: "audio", outerNewLine: true },
        ];
      }
      const w = MD.imageWidth(url);
      if (w) {
        return [{ type: "openTag", tagName: "img", selfClose: true, attributes: { src: url, alt: node.firstChild ? node.firstChild.literal || "" : "", width: w } }];
      }
      return context.origin();
    },
  };

  /* Link einfügen oder ändern: Adresse, Beschriftung und eine Suche über die vorhandenen Seiten.
     Ersetzt das frühere window.prompt und ist zugleich der Weg zu internen Verlinkungen. */
  function linkDialog(initial, onSave) {
    const cur = initial || {};
    dialog(`<h2>${cur.url ? "Link bearbeiten" : "Link einfügen"}</h2>
      <label for="lk-text">Beschriftung</label>
      <input type="text" id="lk-text" value="${esc(cur.text || "")}" placeholder="Angezeigter Text">
      <label for="lk-url">Adresse</label>
      <input type="text" id="lk-url" value="${esc(cur.url || "")}" placeholder="https://… oder /wiki/seite">
      <label for="lk-search">… oder auf eine Seite im Wiki verlinken</label>
      <input type="search" id="lk-search" placeholder="Seitentitel suchen …" autocomplete="off">
      <ul class="link-pages" id="lk-pages"></ul>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
      <button class="btn" id="lk-ok" type="button">Übernehmen</button></div>`,
      (dlg, body) => {
        const urlEl = body.querySelector("#lk-url");
        const textEl = body.querySelector("#lk-text");
        const list = body.querySelector("#lk-pages");
        const search = body.querySelector("#lk-search");
        const renderPages = () => {
          const q = search.value.trim().toLowerCase();
          const hits = state.pages.filter((p) => !q || p.title.toLowerCase().includes(q)).slice(0, 8);
          list.innerHTML = hits.length
            ? hits.map((p) => `<li><button type="button" data-slug="${esc(p.slug)}" data-title="${esc(p.title)}">${esc(p.title)}</button></li>`).join("")
            : '<li class="muted small">Keine passende Seite.</li>';
          list.querySelectorAll("button[data-slug]").forEach((b) => b.onclick = () => {
            urlEl.value = "/wiki/" + b.dataset.slug;
            if (!textEl.value.trim()) textEl.value = b.dataset.title;
            list.querySelectorAll("button").forEach((x) => x.classList.toggle("sel", x === b));
          });
        };
        search.addEventListener("input", renderPages);
        renderPages();
        body.querySelector("#lk-ok").onclick = () => {
          const url = urlEl.value.trim();
          if (!url) return toast("Bitte eine Adresse angeben.", true);
          dlg.close();
          onSave({ url, text: textEl.value.trim() || url });
        };
      });
  }

  /* --- Schwebende Formatleiste bei Textauswahl und "/"-Einfügemenü im WYSIWYG-Modus ------------------- */
  /* Symbolalphabet der schwebenden Leisten.
     Warum eigene SVG statt Unicode: von den Zeichen, die hier gebraucht werden, liegt in der
     Hausschrift (Univers, ersatzweise Arial) praktisch nur ≡. ☰ ▤ ⧉ ⤒ ⤓ ⤫ ⇤ ⇥ ✕ ✎ ⟲ ⟳ ↗ kommen
     aus zufälligen Ersatzschriften, drei davon aus Serifenschriften – daher die uneinheitlichen
     Strichstärken und Grundlinien. Ein 16er-Raster in currentColor löst das: die Symbole nehmen
     Größe und Farbe des Knopfes an, auch beim Überfahren, im aktiven Zustand und in Rot.
     Keine Bibliothek, kein externer Abruf – Inline-SVG ist Markup und verträgt sich mit der CSP. */
  const ico = (d) => `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">${d}</svg>`;
  const I = {
    linksb:    ico('<path d="M3 3h10M3 6h6M3 9h10M3 12h6"/>'),
    mittig:    ico('<path d="M3 3h10M5 6h6M3 9h10M5 12h6"/>'),
    rechtsb:   ico('<path d="M3 3h10M7 6h6M3 9h10M7 12h6"/>'),
    blocksatz: ico('<path d="M3 3h10M3 6h10M3 9h10M3 12h10"/>'),
    zeileAuf:  ico('<rect x="2.5" y="6.5" width="11" height="7" rx="1"/><path d="M2.5 10h11M8 1.5v3.5M6.25 3.25L8 1.5l1.75 1.75"/>'),
    zeileAb:   ico('<rect x="2.5" y="2.5" width="11" height="7" rx="1"/><path d="M2.5 6h11M8 14.5V11M6.25 12.75L8 14.5l1.75-1.75"/>'),
    zeileWeg:  ico('<rect x="2.5" y="2.5" width="11" height="11" rx="1"/><path d="M2.5 6.2h11M2.5 9.8h11M5.6 6.9l4.8 2.2M10.4 6.9l-4.8 2.2"/>'),
    spalteLi:  ico('<rect x="6.5" y="2.5" width="7" height="11" rx="1"/><path d="M10 2.5v11M1.5 8h3.5M3.25 6.25L1.5 8l1.75 1.75"/>'),
    spalteRe:  ico('<rect x="2.5" y="2.5" width="7" height="11" rx="1"/><path d="M6 2.5v11M14.5 8H11M12.75 6.25L14.5 8l-1.75 1.75"/>'),
    spalteWeg: ico('<rect x="2.5" y="2.5" width="11" height="11" rx="1"/><path d="M6.2 2.5v11M9.8 2.5v11M6.9 5.6l2.2 4.8M9.1 5.6l-2.2 4.8"/>'),
    verbinden: ico('<rect x="2.5" y="3.5" width="11" height="9" rx="1"/><path d="M8 3.5v2M8 10.5v2" stroke-dasharray="1.5 1.5"/><path d="M5 8h6M9.2 6.5L11 8l-1.8 1.5M6.8 6.5L5 8l1.8 1.5"/>'),
    teilen2: ico('<rect x="2.5" y="3.5" width="11" height="9" rx="1"/><path d="M8 3.5v9"/><path d="M4.4 8h2.2M6.1 6.8L4.4 8l1.7 1.2M11.6 8H9.4M9.9 6.8L11.6 8 9.9 9.2"/>'),
    stift:     ico('<path d="M11.2 2.3l2.5 2.5-8 8-3.2 0.7 0.7-3.2z"/>'),
    duplizieren: ico('<rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 5.5v-2a1 1 0 00-1-1h-6a1 1 0 00-1 1v6a1 1 0 001 1h2"/>'),
    ersetzen:  ico('<path d="M2.5 5.5h9M9 3l2.5 2.5L9 8M13.5 10.5h-9M7 8l-2.5 2.5L7 13"/>'),
    zuschneiden: ico('<path d="M4.5 1.5v10h10M1.5 4.5h10v10"/>'),
    drehLinks: ico('<path d="M3.2 7.5a5 5 0 105-5H2.5M5 5.5l-2.5-3 2.5-2.5" transform="translate(0 2)"/>'),
    drehRechts: ico('<path d="M12.8 7.5a5 5 0 11-5-5h5.7M11 5.5l2.5-3-2.5-2.5" transform="translate(0 2)"/>'),
    herunter:  ico('<path d="M8 2.5v8M4.5 7L8 10.5 11.5 7M2.5 13.5h11"/>'),
    papierkorb: ico('<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 9h5.6l.7-9M6.7 7v4M9.3 7v4"/>'),
    kette:     ico('<path d="M6.5 9.5l3-3M7.5 4.5l1-1a2.8 2.8 0 014 4l-1 1M8.5 11.5l-1 1a2.8 2.8 0 01-4-4l1-1"/>'),
    ketteWeg:  ico('<path d="M7.5 4.5l1-1a2.8 2.8 0 014 4l-1 1M8.5 11.5l-1 1a2.8 2.8 0 01-4-4l1-1M11.7 11.7l1.8 1.8M4.3 4.3L2.5 2.5"/>'),
    extern:    ico('<path d="M9.5 2.5h4v4M13.5 2.5L7.5 8.5M11.5 9.5V13H3V4.5h3.5"/>'),
    teilen:    ico('<circle cx="11.8" cy="3.7" r="1.9"/><circle cx="11.8" cy="12.3" r="1.9"/>'
                 + '<circle cx="4.2" cy="8" r="1.9"/><path d="M5.85 7.07l4.3-2.44M5.85 8.93l4.3 2.44"/>'),
    zurueck:   ico('<path d="M3 8h7a3.5 3.5 0 010 7H7M6 5L3 8l3 3"/>'),
    vor:       ico('<path d="M13 8H6a3.5 3.5 0 000 7h3M10 5l3 3-3 3"/>'),
    farbe:     ico('<path d="M3.5 11L8 2.5 12.5 11M5.3 8.2h5.4"/><rect class="voll" x="3" y="12.8" width="10" height="2.2" rx=".6"/>'),
    breite:    ico('<path d="M2.5 3.5v9M13.5 3.5v9M4.5 8h7M6 6l-2 2 2 2M10 6l2 2-2 2"/>'),
    original:  ico('<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>'),
    aufloesen: ico('<path d="M2.5 5V2.5H5M11 2.5h2.5V5M13.5 11v2.5H11M5 13.5H2.5V11"/><path d="M3.5 8h9" stroke-dasharray="2 2"/>'),
    spalten:   ico('<rect x="2.5" y="3" width="11" height="10" rx="1"/><path d="M8 3v10"/>'),
    akkordeon: ico('<rect x="2.5" y="3" width="11" height="10" rx="1"/><path d="M2.5 6.5h11"/><path d="M5 4.75l1.2 1L5 6.75" fill="none"/>'),
    emoji:     ico('<circle cx="8" cy="8" r="5.8"/><circle class="voll" cx="6" cy="6.6" r=".9"/><circle class="voll" cx="10" cy="6.6" r=".9"/><path d="M5.4 9.6a3.1 3.1 0 005.2 0"/>'),
    farbtopf:  ico('<path d="M6.5 2.5l6 6-5 5a1.4 1.4 0 01-2 0l-4-4a1.4 1.4 0 010-2z"/><path d="M13.5 11.5s1.5 1.7 1.5 2.6a1.5 1.5 0 01-3 0c0-.9 1.5-2.6 1.5-2.6z" class="voll"/>'),
    griff:     ico('<circle class="voll" cx="6" cy="4" r="1.1"/><circle class="voll" cx="10" cy="4" r="1.1"/><circle class="voll" cx="6" cy="8" r="1.1"/><circle class="voll" cx="10" cy="8" r="1.1"/><circle class="voll" cx="6" cy="12" r="1.1"/><circle class="voll" cx="10" cy="12" r="1.1"/>'),
  };
  const AUSRICHTUNGEN = [["left", I.linksb, "Links"], ["center", I.mittig, "Mittig"],
                         ["right", I.rechtsb, "Rechts"], ["justify", I.blocksatz, "Blocksatz"]];
  // "tip" trägt dasselbe Symbol wie "info" – als Vorgabe wäre es eine zweite gleiche Glühbirne.
  // Im Speicherformat bleibt es gültig, nur die Auswahl zeigt es nicht mehr.
  const KINDS = ["info", "warning", "success", "danger", "note"];

  /* Pastellfarbe für die Hinweiskiste – ein Popover mit fester Auswahl, kein freier Farbwert.
     So bleibt das gespeicherte Markdown lesbar und es kann nichts Fremdes hineingeraten. */
  const farbPopover = (anker, aktuell, aufWahl) => {
    const box = document.createElement("div");
    box.className = "ed-farben";
    const felder = Object.entries(MD.CALLOUT_FARBEN).map(([name, wert]) =>
      `<button type="button" class="farbe${name === aktuell ? " on" : ""}" data-f="${esc(name)}" title="${esc(name)}"
        aria-label="${esc(name)}" style="background:${wert}"></button>`).join("");
    box.innerHTML = `${felder}<button type="button" class="farbe leer${aktuell ? "" : " on"}" data-f=""
      title="Farbe der Hinweisart" aria-label="Farbe der Hinweisart">✕</button>`;
    document.body.appendChild(box);
    const r = anker.getBoundingClientRect();
    const w = box.offsetWidth, h = box.offsetHeight;
    const unten = window.innerHeight - r.bottom > h + 16;
    box.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - w - 8, r.left))}px`;
    box.style.top = `${window.scrollY + (unten ? r.bottom + 6 : r.top - h - 6)}px`;
    const zu = () => { box.remove(); document.removeEventListener("pointerdown", aussen, true); farbZu = null; };
    const aussen = (e) => { if (!box.contains(e.target)) zu(); };
    setTimeout(() => document.addEventListener("pointerdown", aussen, true), 0);
    box.addEventListener("mousedown", (e) => e.preventDefault());
    box.addEventListener("click", (e) => { const b = e.target.closest("[data-f]"); if (!b) return; zu(); aufWahl(b.dataset.f); });
    box.addEventListener("keydown", (e) => { if (e.key === "Escape" || e.key === "Tab") { e.preventDefault(); zu(); } });
    farbZu = zu;
    return zu;
  };
  let farbZu = null;

  /* Emoji-Auswahl als Popover am Knopf – kein Dialog, damit die Auswahl im Text stehen bleibt
     und der Hinweis daneben sichtbar bleibt. Das Raster wird einmal gebaut und wiederverwendet. */
  let emojiGitter = null;
  let emojiZu = null;
  const emojiPopover = (anker, initial, aufWahl) => {
    if (emojiZu) emojiZu();
    const box = document.createElement("div");
    box.className = "ed-emoji";
    if (!emojiGitter) {
      emojiGitter = MD.allEmojis().map((e) => `<button type="button" class="em" data-e="${esc(e)}">${e}</button>`).join("");
    }
    box.innerHTML = `<div class="em-row"><input type="text" class="em-inp" maxlength="8" autocomplete="off" value="${esc(initial || "")}" aria-label="Emoji eintippen">
      <span class="help">eintippen oder unten wählen</span></div><div class="em-grid">${emojiGitter}</div>`;
    document.body.appendChild(box);
    const r = anker.getBoundingClientRect();
    const w = box.offsetWidth, h = box.offsetHeight;
    const untenPlatz = window.innerHeight - r.bottom > h + 16;
    box.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - w - 8, r.left))}px`;
    box.style.top = `${window.scrollY + (untenPlatz ? r.bottom + 6 : r.top - h - 6)}px`;
    const zu = () => { box.remove(); document.removeEventListener("pointerdown", aussen, true); emojiZu = null; };
    const aussen = (e) => { if (!box.contains(e.target)) zu(); };
    setTimeout(() => document.addEventListener("pointerdown", aussen, true), 0);
    // Der Editor darf den Fokus nicht verlieren – nur das Eingabefeld bekommt ihn.
    box.addEventListener("mousedown", (e) => { if (e.target.tagName !== "INPUT") e.preventDefault(); });
    const inp = box.querySelector(".em-inp"), grid = box.querySelector(".em-grid");
    const nimm = (v) => { const e = Array.from(String(v || "").trim()).slice(0, 4).join(""); if (e) { zu(); aufWahl(e); } };
    grid.addEventListener("click", (e) => { const b = e.target.closest(".em"); if (b) nimm(b.dataset.e); });
    box.addEventListener("keydown", (e) => {
      if (e.key === "Escape" || e.key === "Tab") { e.preventDefault(); return zu(); }
      if (e.key === "Enter") { e.preventDefault(); return nimm(document.activeElement === inp ? inp.value : document.activeElement.dataset.e); }
      const liste = Array.from(grid.querySelectorAll(".em"));
      const spalten = Math.max(1, Math.floor(grid.clientWidth / 36));
      const at = liste.indexOf(document.activeElement);
      const d = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: spalten, ArrowUp: -spalten }[e.key];
      if (!d) return;
      e.preventDefault();
      const n = at < 0 ? 0 : Math.max(0, Math.min(liste.length - 1, at + d));
      if (liste[n]) { liste[n].focus(); liste[n].scrollIntoView({ block: "nearest" }); }
    });
    inp.focus(); inp.select();
    emojiZu = zu;
    return zu;
  };

  function setupInlineTools(insert, calloutMenu, columnsMenu) {
    const ed = state.editor;
    const root = $("#editor");
    const bubble = document.createElement("div");
    bubble.className = "ed-bubble hidden";
    bubble.innerHTML = `
      <select class="ed-style" title="Absatz umwandeln">
        <optgroup label="Text">
          <option value="">Umwandeln in …</option>
          <option value="p">Text</option>
          <option value="h1">Überschrift 1</option>
          <option value="h2">Überschrift 2</option>
          <option value="h3">Überschrift 3</option>
          <option value="h4">Überschrift 4</option>
          <option value="h5">Überschrift 5</option>
        </optgroup>
        <optgroup label="Listen">
          <option value="ul">Aufzählung</option>
          <option value="ol">Nummerierte Liste</option>
          <option value="task">Aufgabenliste</option>
        </optgroup>
        <optgroup label="Blöcke">
          <option value="quote">Zitat</option>
          <option value="codeblock">Code-Block</option>
          <option value="callout">Callout</option>
        </optgroup>
        <optgroup label="Auszeichnung">
          <option value="code">Code</option>
          <option value="mark">Hervorheben</option>
          <option value="sup">Hochgestellt</option>
          <option value="sub">Tiefgestellt</option>
        </optgroup>
      </select>
      <span class="sep"></span>
      <button type="button" data-cmd="bold" title="Fett" aria-label="Fett"><b>B</b></button>
      <button type="button" data-cmd="italic" title="Kursiv" aria-label="Kursiv"><i>I</i></button>
      <button type="button" data-cmd="strike" title="Durchgestrichen" aria-label="Durchgestrichen"><s>S</s></button>
      <button type="button" data-mark="u" title="Unterstrichen" aria-label="Unterstrichen"><u>U</u></button>
      <button type="button" data-act="color" title="Textfarbe" aria-label="Textfarbe">${I.farbe}</button>
      <button type="button" data-act="link" title="Link" aria-label="Link einfügen">${I.kette}</button>
      <span class="sep"></span>
      <select class="ed-align" title="Ausrichtung" aria-label="Ausrichtung">
        <option value="">—</option>
        <option value="left">⯇</option>
        <option value="center">≡</option>
        <option value="right">⯈</option>
        <option value="justify">▤</option>
      </select>
      <span class="sep"></span>
      <button type="button" data-cmd="undo" title="Rückgängig (Strg+Z)" aria-label="Rückgängig">${I.zurueck}</button>
      <button type="button" data-cmd="redo" title="Wiederholen (Strg+Umschalt+Z)" aria-label="Wiederholen">${I.vor}</button>`;
    bubble.setAttribute("role", "toolbar");
    bubble.setAttribute("aria-label", "Textformat");
    document.body.appendChild(bubble);
    const pm = () => root.querySelector(".toastui-editor-ww-container .ProseMirror");
    const hideBubble = () => bubble.classList.add("hidden");
    bubble.addEventListener("mousedown", (e) => { if (e.target.tagName !== "SELECT") e.preventDefault(); });
    bubble.querySelectorAll("[data-cmd]").forEach((b) => b.onclick = () => { ed.exec(b.dataset.cmd); state.dirty = true; });
    bubble.querySelector(".ed-style").onchange = (e) => {
      const v = e.target.value;
      e.target.value = "";
      if (!v) return;
      hideBubble();
      // h1 bis h5: Die Auswahl bietet fünf Stufen an, das Inhaltsverzeichnis führt fünf –
      // eine Regel bis h4 ließ „Überschrift 5“ wirkungslos im Menü stehen.
      if (/^h[1-5]$/.test(v)) ed.exec("heading", { level: +v[1] });
      else if (v === "p") ed.exec("heading", { level: 0 });
      else if (v === "ul") ed.exec("bulletList");
      else if (v === "ol") ed.exec("orderedList");
      else if (v === "task") ed.exec("taskList");
      else if (v === "quote") ed.exec("blockQuote");
      else if (v === "codeblock") ed.exec("codeBlock");
      else if (v === "code") ed.exec("code");
      else if (v === "callout") return calloutMenu();
      else if (["mark", "sup", "sub"].includes(v)) return applyMark(v);
      state.dirty = true;
    };
    bubble.querySelector("[data-act=color]").onclick = () => {
      const text = ed.getSelectedText().trim();
      if (!text) return toast("Bitte zuerst Text markieren.", true);
      const NAMES = { rot: "Rot", blau: "Blau (Gewässer)", gruen: "Grün", grau: "Grau", gelb: "Gelb hinterlegt" };
      hideBubble();
      dialog(`<h2>Textfarbe</h2>
        <p class="help">Nach dem Handbuch CD sind nur die Hausfarben vorgesehen – Rot als Auszeichnung,
        Blau als Kennfarbe für Gewässer, Gelb als Hinweis.</p>
        <div class="callout-pick">${MD.COLOR_NAMES.map((c) =>
          `<button type="button" class="btn secondary" data-c="${c}"><span class="tc tc-${c}">${esc(NAMES[c] || c)}</span></button>`).join("")}
          <button type="button" class="btn ghost" data-c="">Farbe entfernen</button></div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button></div>`,
        (dlg, body) => body.querySelectorAll("[data-c]").forEach((b2) => b2.onclick = () => {
          const c = b2.dataset.c;
          dlg.close();
          const inner = text.replace(/^\{\{(?:rot|blau|gruen|grau|gelb):([\s\S]*)\}\}$/, "$1");
          ed.replaceSelection(c ? `{{${c}:${inner}}}` : inner);
          state.dirty = true;
        }));
    };
    bubble.querySelectorAll("[data-mark]").forEach((b) => b.onclick = () => {
      const tag = b.dataset.mark;
      const wrapped = MD.wrapMark(tag, ed.getSelectedText());
      if (!wrapped) {
        return toast(tag === "sub" || tag === "sup"
          ? "Hoch- und Tiefstellen geht nur für zusammenhängende Zeichen ohne Leerzeichen."
          : "Dieser Text lässt sich so nicht auszeichnen.", true);
      }
      ed.replaceSelection(wrapped);
      state.dirty = true;
      hideBubble();
    });
    bubble.querySelector("[data-act=link]").onclick = () => {
      const text = ed.getSelectedText();
      let range = null;
      try { range = ed.getSelection(); } catch (e) { /* im Markdown-Modus egal */ }
      hideBubble();
      linkDialog({ text }, ({ url, text: label }) => {
        // Der Dialog nimmt den Fokus – die Auswahl vorher merken und wiederherstellen.
        if (range) { try { ed.setSelection(range[0], range[1]); } catch (e) { /* egal */ } }
        ed.exec("addLink", { linkUrl: url, linkText: label });
        state.dirty = true;
      });
    };
    bubble.querySelector(".ed-align").onchange = (e) => {
      const mode = e.target.value;
      e.target.value = "";
      if (mode) applyAlign(mode);
    };
    const applyAlign = (mode) => {
      // Markdown kennt keine Ausrichtung. Der Bereich wird deshalb in zwei Marken eingefasst –
      // steht er schon zwischen solchen, ändert sich nur die Richtung, und dieselbe Richtung
      // noch einmal hebt sie wieder auf. Der Inhalt selbst bleibt unangetastet und damit
      // auch der Cursor darin.
      hideBubble();
      /* Welcher Block gemeint ist, entscheidet eine Marke an der Cursorstelle – nicht das
         Abzählen der Blöcke. Das Zählen ging schief, sobald Editor und Text einen Block
         unterschiedlich schneiden (ein Bild mit Unterschrift, ein weicher Umbruch), und dann
         verweigerte die Ausrichtung den Dienst. Die Marke trifft die Stelle immer.
         Bei einer Auswahl über mehrere Absätze wird auch das Ende markiert: Sonst richtete
         sich nur der oberste Absatz aus, und der Rest blieb stehen, wie er war. Zuerst das
         Ende einsetzen – eine Einfügung am Anfang verschöbe die Stelle dahinter. */
      let md, marken = false;
      try {
        const wahl = ed.getSelection();
        const von = Math.min(wahl[0], wahl[1]), bis = Math.max(wahl[0], wahl[1]);
        if (bis > von) { ed.setSelection(bis, bis); ed.replaceSelection(AUSRICHT_ENDE); }
        ed.setSelection(von, von);                 // Auswahl nicht überschreiben
        ed.replaceSelection(AUSRICHT_MARKE);
        marken = true;
        md = ed.getMarkdown();
      } catch (e) {
        md = ed.getMarkdown();
      }
      let zeilen = md.split("\n");
      const markeZeile = zeilen.findIndex((z) => z.includes(AUSRICHT_MARKE));
      const endeZeile = zeilen.findIndex((z) => z.includes(AUSRICHT_ENDE));
      // Endet die Auswahl genau am Anfang des nächsten Absatzes, gehört der nicht mehr dazu.
      const amBlockanfang = endeZeile > markeZeile
        && zeilen[endeZeile].trimStart().startsWith(AUSRICHT_ENDE);
      // Die Marken kommen in jedem Fall wieder heraus – auch wenn gleich abgebrochen wird.
      // Sonst stünde „zzausrichtungsstellezz“ im Artikel.
      zeilen = zeilen.map((z) => z.split(AUSRICHT_MARKE).join("").split(AUSRICHT_ENDE).join(""));
      md = zeilen.join("\n");
      const nicht = (text) => {
        if (marken) setMd(md);                     // aufgeräumter Stand zurück in den Editor
        toast(text || "Der Abschnitt lässt sich hier nicht zuordnen – bitte in den Absatz "
                    + "klicken, der ausgerichtet werden soll.", true);
      };
      if (markeZeile < 0) return nicht();
      const erg = EDMD.ausrichten(md, { markeZeile, endeZeile, amBlockanfang, mode });
      if (erg.fehler !== undefined) return nicht(erg.fehler || undefined);
      setMd(erg.md);
      state.dirty = true;
    };

    /* Der Zug über mehrere Zellen ist flüchtig. ProseMirror liest seine Auswahl neu aus dem
       Dokument, sobald sich darin etwas rührt – und dann ist aus der Zellauswahl eine gewöhnliche
       Textauswahl über dieselben Zellen geworden. Der Knopf „Zellen verbinden“ käme damit nie zum
       Zug. Der gezogene Bereich wird deshalb gemerkt und vor dem Verbinden wiederhergestellt.
       Die Klasse der Zellauswahl gibt Toast UI nicht heraus; sie wird beim ersten Zug von der
       Auswahl selbst abgenommen. */
    const wwSicht = () => { try { return ed.wwEditor.view; } catch (e) { return null; } };
    const ZELLE = /^table(Head|Body)Cell$/;
    let ZellAuswahl = null;
    let zellBereich = null;                      // { von, bis }: Positionen vor den Eckzellen
    const zellBereichMerken = () => {
      const sicht = wwSicht();
      const s = sicht && sicht.state.selection;
      if (!s || !s.startCell || !s.endCell) return;
      ZellAuswahl = s.constructor;
      zellBereich = { von: s.startCell.pos, bis: s.endCell.pos };
    };
    const istZelle = (doc, pos) => {
      const n = pos >= 0 && pos < doc.content.size ? doc.nodeAt(pos) : null;
      return !!(n && ZELLE.test(n.type.name));
    };
    /* Stellt den gemerkten Bereich wieder her und sagt, ob danach mehr als eine Zelle der
       übergebenen Tabelle ausgewählt ist – nur dann gibt es etwas zu verbinden. Der gemerkte
       Bereich muss noch in genau dieser Tabelle liegen: Sonst verbände der Knopf nach einer
       Änderung woanders zwei Zellen, die niemand markiert hat. */
    const zellBereichHerstellen = (tabelle) => {
      const sicht = wwSicht();
      if (!sicht) return false;
      const s = sicht.state.selection;
      if (s && s.startCell && s.endCell) return s.startCell.pos !== s.endCell.pos;
      if (!ZellAuswahl || !zellBereich || zellBereich.von === zellBereich.bis) return false;
      const doc = sicht.state.doc;
      if (!istZelle(doc, zellBereich.von) || !istZelle(doc, zellBereich.bis)) return false;
      const dom = (pos) => { try { const d = sicht.nodeDOM(pos); return d && d.nodeType === 1 ? d : null; } catch (e) { return null; } };
      const a = dom(zellBereich.von), b = dom(zellBereich.bis);
      if (!a || !b || a.closest("table") !== tabelle || b.closest("table") !== tabelle) return false;
      try {
        sicht.dispatch(sicht.state.tr.setSelection(
          new ZellAuswahl(doc.resolve(zellBereich.von), doc.resolve(zellBereich.bis))));
        return true;
      } catch (e) { return false; }
    };
    const zelleUm = (knoten) => {
      const e = knoten && (knoten.nodeType === 1 ? knoten : knoten.parentElement);
      return e ? e.closest("td, th") : null;
    };

    const onSelection = () => {
      const el = pm();
      const sel = document.getSelection();
      if (!el || !sel || sel.isCollapsed || !sel.rangeCount || !el.contains(sel.anchorNode)) return hideBubble();
      /* Eine über mehrere Zellen gezogene Auswahl ist Tabellensache, nicht Textsache: Hier gehört
         weder die Textleiste hin noch das Wegblenden des Tabellenmenüs. Geprüft wird beides – die
         Markierung des Editors und, falls die schon zerfallen ist, die Auswahl im Dokument. */
      if (el.querySelector("td.toastui-editor-cell-selected, th.toastui-editor-cell-selected")) {
        zellBereichMerken();
        return hideBubble();
      }
      const vonZelle = zelleUm(sel.anchorNode), bisZelle = zelleUm(sel.focusNode);
      if (vonZelle && bisZelle && vonZelle !== bisZelle) return hideBubble();
      const r = sel.getRangeAt(0).getBoundingClientRect();
      if (!r.width && !r.height) return hideBubble();
      hideCtx();                                   // sobald Text markiert ist, weicht das Blockmenü
      bubble.classList.remove("hidden");
      markActive();
      const w = bubble.offsetWidth;
      bubble.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
      bubble.style.top = `${window.scrollY + r.top - bubble.offsetHeight - 8}px`;
    };
    /* Zeigt an, welche Auszeichnung an der Auswahl schon anliegt. */
    function markActive() {
      const sel = document.getSelection();
      const node = sel && sel.anchorNode;
      const el = node && (node.nodeType === 1 ? node : node.parentElement);
      const has = (q) => !!(el && el.closest(q));
      const map = { bold: "strong, b", italic: "em, i", strike: "del, s" };
      bubble.querySelectorAll("[data-cmd]").forEach((b) => {
        const q = map[b.dataset.cmd];
        b.classList.toggle("on", !!q && has(q));
      });
      bubble.querySelectorAll("[data-mark]").forEach((b) => {
        const tag = { u: "u", mark: "mark", sup: "sup", sub: "sub" }[b.dataset.mark];
        b.classList.toggle("on", has(`.tui-widget ${tag}`));
      });
      // Die Auswahlfelder sind Befehlslisten, kein Zustand – sie stehen immer auf der Kopfzeile.
      bubble.querySelector(".ed-style").value = "";
      const al = el && el.closest(".align-left, .align-center, .align-right, .align-justify");
      bubble.querySelector(".ed-align").value = al ? al.className.replace("align-", "") : "";
    }
    document.addEventListener("selectionchange", onSelection);

    /* "/"-Menü */
    const items = [
      { t: "Text", d: "Normaler Absatz", run: () => ed.exec("heading", { level: 0 }) },
      { t: "Überschrift 1", d: "Große Abschnittsüberschrift", run: () => ed.exec("heading", { level: 1 }) },
      { t: "Überschrift 2", d: "Mittlere Überschrift", run: () => ed.exec("heading", { level: 2 }) },
      { t: "Überschrift 3", d: "Kleine Überschrift", run: () => ed.exec("heading", { level: 3 }) },
      { t: "Überschrift 4", d: "Kleine Zwischenüberschrift", k: "h4", run: () => ed.exec("heading", { level: 4 }) },
      { t: "Überschrift 5", d: "Kleinste Überschrift", k: "h5", run: () => ed.exec("heading", { level: 5 }) },
      { t: "Aufzählung", d: "Einfache Liste", run: () => ed.exec("bulletList") },
      { t: "Nummerierte Liste", d: "Liste mit Nummern", run: () => ed.exec("orderedList") },
      { t: "Aufgabenliste", d: "Liste mit Häkchen", run: () => ed.exec("taskList") },
      { t: "Zitat", d: "Eingerückter Block, z. B. Voraussetzungen", run: () => ed.exec("blockQuote") },
      { t: "Tabelle", d: "Größe wählen, später erweiterbar", k: "raster", run: () => {
        dialog(`<h2>Tabelle einfügen</h2>
          <div class="field-row">
            <div><label for="tb-rows">Zeilen (mit Kopfzeile)</label><input type="number" id="tb-rows" min="2" max="30" value="3"></div>
            <div><label for="tb-cols">Spalten</label><input type="number" id="tb-cols" min="1" max="12" value="3"></div>
          </div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
          <button class="btn" id="tb-ok" type="button">Einfügen</button></div>`,
          (dlg, body) => { body.querySelector("#tb-ok").onclick = () => {
            const rows = Math.min(30, Math.max(2, +body.querySelector("#tb-rows").value || 3));
            const cols = Math.min(12, Math.max(1, +body.querySelector("#tb-cols").value || 3));
            dlg.close();
            ed.exec("addTable", { rowCount: rows, columnCount: cols });
            state.dirty = true;
          }; });
      } },
      { t: "Bild", d: "Bild hochladen", run: () => pickImage((url, alt) => { ed.exec("addImage", { imageUrl: url, altText: alt }); state.dirty = true; }) },
      { t: "Video", d: "Video hochladen (MP4, MOV, WebM)", run: () => pickFile("video/*,.mp4,.m4v,.mov,.webm", (url, name, kind) => {
        if (kind !== "video") return toast("Das ist kein Video – für Bilder bitte „Bild“ verwenden.", true);
        insert(`![${name || "Video"}](${url})\n`);
      }) },
      { t: "Audio", d: "Tonaufnahme einbetten (MP3, M4A, OGG, WAV)", k: "ton sprache", run: () => pickFile(".mp3,.m4a,.ogg,.oga,.wav,audio/*", (url, name, kind) => {
        if (kind !== "file") return toast("Das ist keine Audiodatei.", true);
        insert(`![${name || "Aufnahme"}](${url})\n`);
      }) },
      { t: "Datei", d: "Anhang verlinken (PDF, Word, Excel, ZIP, GPX …)", run: () => pickFile(".pdf,.doc,.docx,.odt,.rtf,.xls,.xlsx,.ods,.csv,.ppt,.pptx,.odp,.txt,.zip,.gpx,.kml,.kmz", (url, name, kind, filename) => {
        if (kind !== "file") return toast("Für Bilder und Videos bitte „Bild“ oder „Video“ verwenden.", true);
        insert(`[${filename || name}](${url})\n`);
      }) },
      { t: "Code-Block", d: "Vorformatierter Text", run: () => ed.exec("codeBlock") },
      { t: "Trennlinie", d: "Waagerechte Linie", run: () => ed.exec("hr") },
      { t: "Callout", d: "Info, Warnung, Erfolg, Gefahr, Hinweis – mit Emoji", run: calloutMenu },
      { t: "Spalten", d: "Abschnitt mit zwei bis fünf Spalten", run: columnsMenu },
      { t: "Einklappbare Box", d: "Inhalt erst nach dem Aufklappen sichtbar", run: () => insert(SNIPPETS.accordion) },
      { t: "Typische Fehler", d: "Tabelle im Stil des Wikis", k: "vorlage tabelle", run: () => insert(SNIPPETS.fehler) },
      { t: "Inhaltsverzeichnis", d: "Gliederung an dieser Stelle im Text", k: "toc gliederung",
        run: () => insert("$$toc\n$$\n") },
      { t: "Unterseiten", d: "Liste der Unterseiten an dieser Stelle", k: "kinder navigation",
        run: () => insert("$$unterseiten\n$$\n") },
      { t: "Synchronisierter Abschnitt", d: "Teil dieser Seite, der auch anderswo erscheinen kann",
        k: "baustein wiederverwenden", run: () => bausteinDialog() },
      { t: "Abschnitt einbinden", d: "Synchronisierten Abschnitt einer anderen Seite anzeigen",
        k: "einbau baustein uebernehmen", run: () => einbauDialog() },
      { t: "Emoji", d: "Emoji auswählen und einfügen", k: "symbol smiley", run: () => emojiInsertDialog() },
      { t: "Datum", d: "Heutiges Datum einfügen", k: "zeit heute",
        run: () => ed.replaceSelection(new Date().toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })) },
      { t: "Seitenumbruch", d: "Beim Drucken hier umbrechen", k: "druck pdf",
        run: () => insert("$$seitenumbruch\n$$\n") },
      { t: "Statusmarke", d: "Farbige Marke, z. B. „in Prüfung“", k: "badge label",
        run: () => ed.replaceSelection("{status:offen}") },
    ];
    /* --- Synchronisierte Abschnitte -----------------------------------------------------
       Der Baustein bekommt eine Kennung, unter der ihn andere Seiten ansprechen. Sie steht
       im gespeicherten Text und soll deshalb schlicht bleiben: Kleinbuchstaben, Ziffern,
       Striche. Ein Titel voller Umlaute und Leerzeichen wäre in ":::einbau seite#kennung"
       nicht wiederzuerkennen. */
    const alsKennung = (roh) => String(roh || "").toLowerCase().trim()
      .replace(/[äöüß]/g, (c) => ({ "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss" }[c]))
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48);

    // Alle Bausteine einer Seite – gelesen wird der gespeicherte Text, nicht die Anzeige.
    const bausteineVon = (inhalt) => {
      const raus = [];
      String(inhalt || "").split("\n").forEach((z) => {
        const m = /^:::[ \t]*baustein[ \t]+(\S.*?)[ \t]*$/.exec(z);
        if (m) raus.push(m[1]);
      });
      return raus;
    };

    function bausteinDialog() {
      dialog(`<h2>Synchronisierter Abschnitt</h2>
        <p class="help">Dieser Teil der Seite lässt sich auf anderen Seiten einbinden. Geändert
          wird er immer hier – überall sonst erscheint der geänderte Text mit.</p>
        <label for="bs-name">Kennung</label>
        <input type="text" id="bs-name" placeholder="z. B. sicherung-am-ufer" autocomplete="off">
        <p class="help" id="bs-vorschau"></p>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="bs-ok" type="button">Einfügen</button></div>`,
        (dlg, body) => {
          const feld = body.querySelector("#bs-name");
          const vor = body.querySelector("#bs-vorschau");
          const zeigen = () => {
            const k = alsKennung(feld.value);
            vor.textContent = k ? `Wird angesprochen als: ${state.current.slug}#${k}` : "";
          };
          feld.addEventListener("input", zeigen);
          body.querySelector("#bs-ok").onclick = () => {
            const k = alsKennung(feld.value);
            if (!k) return toast("Bitte eine Kennung angeben.", true);
            dlg.close();
            insert(bausteinMd(k));
          };
        });
    }

    function einbauDialog() {
      dialog(`<h2>Abschnitt einbinden</h2>
        <p class="help">Zeigt einen synchronisierten Abschnitt einer anderen Seite. Der Text wird
          dort gepflegt und erscheint hier immer in seinem neuesten Stand.</p>
        <label for="eb-search">Seite suchen</label>
        <input type="search" id="eb-search" placeholder="Seitentitel …" autocomplete="off">
        <ul class="link-pages" id="eb-pages"></ul>
        <label for="eb-teile">Abschnitt</label>
        <ul class="link-pages" id="eb-teile"></ul>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="eb-ok" type="button">Einfügen</button></div>`,
        (dlg, body) => {
          const suche = body.querySelector("#eb-search");
          const seiten = body.querySelector("#eb-pages");
          const teile = body.querySelector("#eb-teile");
          let gewaehlt = null, kennung = null;
          const zeigeTeile = (liste) => {
            kennung = null;
            teile.innerHTML = liste.length
              ? liste.map((k) => `<li><button type="button" data-k="${esc(k)}">${esc(k)}</button></li>`).join("")
              : '<li class="muted small">Auf dieser Seite gibt es keinen synchronisierten Abschnitt.</li>';
            teile.querySelectorAll("button[data-k]").forEach((b) => b.onclick = () => {
              kennung = b.dataset.k;
              teile.querySelectorAll("button").forEach((x) => x.classList.toggle("sel", x === b));
            });
          };
          const zeigeSeiten = () => {
            const q = suche.value.trim().toLowerCase();
            const treffer = state.pages.filter((p) => !q || p.title.toLowerCase().includes(q)).slice(0, 8);
            seiten.innerHTML = treffer.length
              ? treffer.map((p) => `<li><button type="button" data-slug="${esc(p.slug)}">${esc(p.title)}</button></li>`).join("")
              : '<li class="muted small">Keine passende Seite.</li>';
            seiten.querySelectorAll("button[data-slug]").forEach((b) => b.onclick = async () => {
              gewaehlt = b.dataset.slug;
              seiten.querySelectorAll("button").forEach((x) => x.classList.toggle("sel", x === b));
              teile.innerHTML = '<li class="muted small">Wird gelesen …</li>';
              try {
                const d = await api(`/api/wiki/pages/${encodeURIComponent(gewaehlt)}`);
                zeigeTeile(bausteineVon(d.page.content));
              } catch (e) {
                teile.innerHTML = '<li class="muted small">Die Seite lässt sich nicht lesen.</li>';
              }
            });
          };
          suche.addEventListener("input", zeigeSeiten);
          zeigeSeiten();
          zeigeTeile([]);
          body.querySelector("#eb-ok").onclick = () => {
            if (!gewaehlt) return toast("Bitte zuerst eine Seite wählen.", true);
            if (!kennung) return toast("Bitte einen Abschnitt wählen.", true);
            dlg.close();
            insert(einbauMd(gewaehlt, kennung));
          };
        });
    }

    const menu = document.createElement("div");
    menu.className = "ed-slash hidden";
    document.body.appendChild(menu);
    let slash = null; // { query, sel }
    const closeSlash = () => { slash = null; menu.classList.add("hidden"); };
    const renderSlash = () => {
      const q = slash.query.toLowerCase();
      const list = items.filter((it) => !q || it.t.toLowerCase().includes(q) || it.d.toLowerCase().includes(q)
        || (it.k || "").includes(q));
      if (!list.length) return closeSlash();
      slash.list = list; slash.index = Math.min(slash.index || 0, list.length - 1);
      menu.innerHTML = `<div class="ed-slash-title">Einfügen${q ? ` – „${esc(slash.query)}“` : ""}</div>` +
        list.map((it, i) => `<button type="button" class="${i === slash.index ? "sel" : ""}" data-i="${i}"><strong>${esc(it.t)}</strong><span>${esc(it.d)}</span></button>`).join("");
      menu.querySelectorAll("button").forEach((b) => { b.onmousedown = (e) => e.preventDefault(); b.onclick = () => pick(+b.dataset.i); });
      menu.classList.remove("hidden");
      const sel = document.getSelection();
      let r = sel && sel.rangeCount ? sel.getRangeAt(0).getBoundingClientRect() : null;
      if (!r || (!r.width && !r.height)) { const n = sel && sel.anchorNode; const el = n && (n.nodeType === 1 ? n : n.parentElement); r = el ? el.getBoundingClientRect() : { left: 100, bottom: 100 }; }
      menu.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - 320, r.left))}px`;
      menu.style.top = `${window.scrollY + r.bottom + 6}px`;
    };
    const pick = (i) => {
      const it = slash.list[i];
      const len = slash.query.length + 1;
      closeSlash();
      // "/" und Suchtext wieder entfernen, dann den Befehl ausführen
      try { const [from, to] = ed.getSelection(); ed.setSelection(from - len, to); ed.replaceSelection(""); } catch (e) { /* egal */ }
      it.run();
      state.dirty = true;
      const el = pm(); if (el) el.focus();
    };
    root.addEventListener("keydown", (e) => {
      if (!ed.isWysiwygMode()) return;
      if (slash) {
        if (e.key === "Escape") { e.preventDefault(); return closeSlash(); }
        if (e.key === "ArrowDown") { e.preventDefault(); slash.index = (slash.index + 1) % slash.list.length; return renderSlash(); }
        if (e.key === "ArrowUp") { e.preventDefault(); slash.index = (slash.index - 1 + slash.list.length) % slash.list.length; return renderSlash(); }
        if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); return pick(slash.index); }
        if (e.key === "Backspace") { if (!slash.query) return closeSlash(); slash.query = slash.query.slice(0, -1); return setTimeout(renderSlash, 0); }
        // Leertaste vor der Zeichenprüfung: sonst landet sie im Suchtext und das Menü
        // schließt sich erst über den leeren Trefferfilter.
        if (e.key === " ") return closeSlash();
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) { slash.query += e.key; return setTimeout(renderSlash, 0); }
        return;
      }
      const mod = e.ctrlKey || e.metaKey;
      if (mod && !e.altKey) {
        const k = e.key.toLowerCase();
        // Strg+U legt in Toast UI sonst eine Aufzählung an – hier unterstreicht es.
        if (k === "u") { e.preventDefault(); return applyMark("u"); }
        if (k === "h" && e.shiftKey) { e.preventDefault(); return applyMark("mark"); }
        if (k === "k") { e.preventDefault(); return openLinkDialogForSelection(); }
        if (k === "\\") { e.preventDefault(); return clearFormatting(); }
        if (k === "f" && e.shiftKey) { e.preventDefault(); return findReplaceDialog(); }
        // Ausweg, wenn sich ein Block nicht eindeutig zuordnen lässt – die Meldungen
        // verweisen auf genau dieses Kürzel.
        if (k === "c" && e.shiftKey) { e.preventDefault(); if (state.editorCopyMd) state.editorCopyMd(); return; }
      }
      // Emoji-Auswahl über „::“ – ein einzelner Doppelpunkt am Wortanfang kam zu oft vor
      // („:::warning“ in einer Tabellenzelle, „: Anmerkung“) und riss den Dialog auf.
      if (e.key === ":" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const sel = document.getSelection();
        const before = sel && sel.anchorNode && sel.anchorNode.nodeType === 3
          ? sel.anchorNode.nodeValue.slice(0, sel.anchorOffset) : "";
        if (/(^|\s):$/.test(before)) { e.preventDefault(); setTimeout(() => emojiInsertDialog(true), 0); }
      }
      if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
        const sel = document.getSelection();
        const before = sel && sel.anchorNode && sel.anchorNode.nodeType === 3 ? sel.anchorNode.nodeValue.slice(0, sel.anchorOffset) : "";
        if (before && !/\s$/.test(before)) return; // mitten im Wort (z. B. URL) kein Menü
        slash = { query: "", index: 0 };
        setTimeout(renderSlash, 0);
      }
    }, true);
    root.addEventListener("mousedown", () => { if (slash) closeSlash(); });

    /* --- Auszeichnen, Link, Formatierung entfernen, Suchen/Ersetzen, Emoji ------------ */
    const applyMark = (tag) => {
      const wrapped = MD.wrapMark(tag, ed.getSelectedText());
      if (!wrapped) {
        return toast(tag === "sub" || tag === "sup"
          ? "Hoch- und Tiefstellen geht nur für zusammenhängende Zeichen ohne Leerzeichen."
          : "Bitte zuerst Text markieren.", true);
      }
      ed.replaceSelection(wrapped);
      state.dirty = true;
      hideBubble();
    };

    const openLinkDialogForSelection = () => {
      const text = ed.getSelectedText();
      let range = null;
      try { range = ed.getSelection(); } catch (e) { /* egal */ }
      hideBubble();
      linkDialog({ text }, ({ url, text: label }) => {
        if (range) { try { ed.setSelection(range[0], range[1]); } catch (e) { /* egal */ } }
        ed.exec("addLink", { linkUrl: url, linkText: label });
        state.dirty = true;
      });
    };

    /* Alles Inline-Format der Auswahl entfernen – auch die eigenen Auszeichnungen. */
    const clearFormatting = () => {
      const sel = ed.getSelectedText();
      if (!sel) return toast("Bitte zuerst Text markieren.", true);
      const plain = sel
        .replace(/\$\$widget\d+ ([\s\S]*?)\$\$/g, "$1")
        .replace(/\*\*([\s\S]*?)\*\*/g, "$1").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1$2")
        .replace(/~~([\s\S]*?)~~/g, "$1").replace(/`([^`\n]+)`/g, "$1")
        .replace(/\+\+([^+\n]+)\+\+/g, "$1").replace(/==([^=\n]+)==/g, "$1")
        .replace(/\^([^^\s]+)\^/g, "$1").replace(/(?<!~)~([^~\s]+)~(?!~)/g, "$1")
        .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
      ed.replaceSelection(plain);
      state.dirty = true;
      hideBubble();
    };

    /* Der Editorkopf liegt in einer anderen Kapsel als diese Werkzeuge – er erreicht sie über
       den Zustand, genau wie das Kopieren als Markdown. */
    state.editorSuchen = () => findReplaceDialog();
    state.editorKlartext = () => clearFormatting();
    /* Suchen und Ersetzen im geöffneten Dokument (arbeitet auf dem Markdown). */
    const findReplaceDialog = () => {
      dialog(`<h2>Suchen und Ersetzen</h2>
        <label for="fr-find">Suchen</label><input type="text" id="fr-find" autocomplete="off">
        <label for="fr-repl">Ersetzen durch</label><input type="text" id="fr-repl" autocomplete="off">
        <label class="inline"><input type="checkbox" id="fr-case"> Groß-/Kleinschreibung beachten</label>
        <div class="help" id="fr-count"></div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button>
        <button class="btn" id="fr-go" type="button">Alle ersetzen</button></div>`,
        (dlg, body) => {
          const find = body.querySelector("#fr-find");
          const count = body.querySelector("#fr-count");
          const rx = () => {
            const t = find.value;
            if (!t) return null;
            return new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
                              body.querySelector("#fr-case").checked ? "g" : "gi");
          };
          /* Ersetzt wird nur im Fließtext: nicht in Abschnittsmarken ($$spalten …, sonst zerfiele
             der Abschnitt), nicht in Codeblöcken, nicht in Link- und Bildadressen. Der Ersatztext
             wird wörtlich eingesetzt – „$1“ oder „$$“ sind keine Muster. */
          const ersetzeGeschuetzt = (md, r, ersatz) => {
            const zeilen = md.split("\n");
            const zaun = MD.fenceMask(zeilen);
            let inMarke = false, n = 0;
            const neu = zeilen.map((z, i) => {
              if (zaun[i]) return z;
              if (!inMarke && MARKEN_RE.test(z)) { inMarke = true; return z; }
              if (inMarke) { if (/^\$\$[ \t]*$/.test(z)) inMarke = false; return z; }
              return z.split(/(\]\([^)]*\))/).map((t, k) => (k % 2 ? t : t.replace(r, () => { n++; return ersatz; }))).join("");
            });
            return { text: neu.join("\n"), n };
          };
          const update = () => {
            const r = rx();
            const n = r ? ersetzeGeschuetzt(ed.getMarkdown(), r, "").n : 0;
            count.textContent = r ? `${n} Fundstelle${n === 1 ? "" : "n"}` : "";
          };
          find.addEventListener("input", update);
          body.querySelector("#fr-case").addEventListener("change", update);
          body.querySelector("#fr-go").onclick = () => {
            const r = rx();
            if (!r) return toast("Bitte einen Suchbegriff angeben.", true);
            const md = ed.getMarkdown();
            const ersatz = body.querySelector("#fr-repl").value;
            const { text, n } = ersetzeGeschuetzt(md, r, ersatz);
            if (!n) return toast("Keine Fundstelle.", true);
            // Erst den Dialog schließen: sein Schließen holt den Fokus zurück und würde ihn
            // dem Editor sonst gleich wieder wegnehmen – der Cursor landete im Nichts.
            dlg.close();
            setMd(text);
            // Das Schließen eines <dialog> gibt den Fokus erst im nächsten Durchlauf zurück –
            // deshalb den Editor danach noch einmal holen, sonst tippt man ins Leere.
            setTimeout(() => { try { ed.getCurrentModeEditor().view.focus(); } catch (e) { /* egal */ } }, 0);
            toast(`${n} Stelle${n === 1 ? "" : "n"} ersetzt`);
          };
        });
    };

    /* Emoji mitten im Text einfügen */
    const emojiInsertDialog = (doppelpunktWeg = false) => {
      dialog(`<h2>Emoji einfügen</h2>
        <div class="em-row"><input type="text" id="em-input" maxlength="8" autocomplete="off"><span class="help">eintippen oder unten wählen</span></div>
        <div class="em-grid" id="em-grid"></div>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
        <button class="btn" id="em-ok" type="button">Einfügen</button></div>`,
        (dlg, body) => {
          dlg.classList.add("wide");
          dlg.addEventListener("close", () => dlg.classList.remove("wide"), { once: true });
          const getEmoji = emojiPicker(body, "💡");
          body.querySelector("#em-ok").onclick = () => {
            const e = getEmoji();
            dlg.close();
            if (doppelpunktWeg) {
              // Der erste der beiden Doppelpunkte steht noch im Text – er gehört zum Kürzel.
              try { const v = ed.getCurrentModeEditor().view; const von = v.state.selection.from; v.dispatch(v.state.tr.delete(von - 1, von)); } catch (err) { /* egal */ }
            }
            ed.replaceSelection(e);
            state.dirty = true;
          };
        });
    };

    /* Typografische Ersetzungen beim Tippen: -- wird –, ... wird …, "x" bekommt deutsche
       Anführungszeichen. Nur im Fließtext, nicht in Code-Blöcken. */
    root.addEventListener("keyup", (e) => {
      if (!ed.isWysiwygMode() || e.ctrlKey || e.metaKey || e.altKey) return;
      if (!/^[-." ]$/.test(e.key)) return;
      const sel = document.getSelection();
      const node = sel && sel.anchorNode;
      if (!node || node.nodeType !== 3) return;
      if (node.parentElement && node.parentElement.closest("pre, code")) return;
      const before = node.nodeValue.slice(0, sel.anchorOffset);
      let cut = 0, put = "";
      // Nicht in einer Zeile, die nur aus Strichen besteht: „---“ soll eine Trennlinie werden,
      // und die zweite Taste darf die dritte nicht unmöglich machen.
      if (/--$/.test(before) && !/---$/.test(before) && !/^\s*-+$/.test(before)) { cut = 2; put = "–"; }
      else if (/\.\.\.$/.test(before)) { cut = 3; put = "…"; }
      else if (/(^|[\s(\[])"$/.test(before)) { cut = 1; put = "„"; }
      else if (/[^\s(\[]"$/.test(before)) { cut = 1; put = "“"; }
      if (!cut) return;
      const start = sel.anchorOffset - cut;
      node.nodeValue = node.nodeValue.slice(0, start) + put + node.nodeValue.slice(sel.anchorOffset);
      const r = document.createRange();
      r.setStart(node, start + put.length); r.collapse(true);
      sel.removeAllRanges(); sel.addRange(r);
      state.dirty = true;
    });

    /* --- Eingefügten Markdown-Text als Rich Text übernehmen ---------------------------
       Toast UI fügt Text roh ein; wer aus Docmost oder einer Datei kopiert, hätte sonst
       "## Titel" als Fließtext im Artikel stehen. */
    const MD_HINT = /(^|\n)\s{0,3}(#{1,6}\s|[-*+]\s|\d+\.\s|>\s|```|\|.*\|)|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)/;
    /* Liegt in der Auswahl eine Tabelle oder eine Abschnittsmarke, würde das Einfügen sie mit
       ersetzen – dieselbe Wache wie beim Löschen, nur vor unseren eigenen Einfügewegen. */
    const auswahlSchuetzen = (e) => {
      const sel = document.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount || !pm() || !pm().contains(sel.anchorNode)) return false;
      const inhalt = sel.getRangeAt(0).cloneContents();
      if (!inhalt.querySelector("table, .sek-marke, .toastui-editor-custom-block")) return false;
      e.preventDefault(); e.stopImmediatePropagation();
      toast("Die Auswahl enthält eine Tabelle oder einen Abschnitt – erst die Auswahl verkleinern, dann einfügen.", true);
      return true;
    };
    root.addEventListener("paste", (e) => {
      if (!ed.isWysiwygMode()) return;
      if (auswahlSchuetzen(e)) return;
      const cb = e.clipboardData;
      if (!cb) return;
      // Dateien haben Vorrang – die erledigt der Upload-Zweig weiter unten.
      if (cb.files && cb.files.length) return;
      const text = cb.getData("text/plain") || "";
      const html = cb.getData("text/html") || "";
      if (html || !text || !MD_HINT.test(text)) return;   // echtes HTML kann Toast UI selbst
      if (/^!\[[^\]]*\]\([^)\s]+\)$/.test(text.trim())) return;   // reines Bild: siehe Bild-Zweig
      e.preventDefault();
      e.stopPropagation();
      // Eingefügtes Markdown an der Cursorstelle in den Text einsetzen und neu parsen lassen.
      e.stopImmediatePropagation();
      insertMarkdownAtCursor(text);
      state.dirty = true;
    }, true);

    /* --- Bilder kopieren, ausschneiden und einfügen -----------------------------------
       Toast UI macht den Bildknoten unselektierbar (schema: selectable:false) und seine NodeView
       verschluckt jedes Ereignis (stopEvent liefert immer true). ProseMirror sieht copy/cut auf
       einem Bild deshalb nie. Wir behandeln beides selbst, bevor es dorthin gelangt: das zuletzt
       angeklickte Bild gilt als Auswahl (dasselbe Bild, das auch das Bildmenü geöffnet hat). */
    let lastImage = null;
    root.addEventListener("click", (e) => {
      const img = e.target && e.target.closest ? e.target.closest("img") : null;
      lastImage = img && pm() && pm().contains(img) ? img : null;
    }, true);

    const imageMarkdownOf = (img) => {
      const occ = imageOccurrences(ed.getMarkdown())[contentImages().indexOf(img)];
      return occ ? { md: `![${occ.alt}](${occ.url})` } : null;
    };

    const imgClip = (e) => {
      const sel = document.getSelection();
      // Nur eingreifen, wenn wirklich ein Bild gemeint ist und keine Textauswahl besteht.
      if (!lastImage || !pm() || !pm().contains(lastImage)) return;
      if (sel && !sel.isCollapsed && sel.toString().trim()) return;
      const info = imageMarkdownOf(lastImage);
      if (!info) return;
      e.preventDefault();
      e.stopPropagation();
      if (e.clipboardData) {
        e.clipboardData.setData("text/plain", info.md);
        e.clipboardData.setData("text/html", `<img src="${lastImage.getAttribute("src")}" alt="${lastImage.getAttribute("alt") || ""}">`);
      }
      if (e.type === "cut") {
        const img = lastImage;
        lastImage = null;
        rewriteImage(img, () => null);
        toast("Bild ausgeschnitten");
      } else {
        toast("Bild kopiert");
      }
    };
    root.addEventListener("copy", imgClip, true);
    root.addEventListener("cut", imgClip, true);

    /* Eingefügtes Bild: aus der Zwischenablage (Screenshot) oder als kopiertes Bild aus dem
       Artikel. Toast UIs eigener Weg greift nur bei Dateien; ein <img> im HTML der Zwischenablage
       oder unser eigenes ![…](…) landen sonst als Text im Absatz. */
    root.addEventListener("paste", (e) => {
      const cb = e.clipboardData;
      if (!cb) return;
      if (cb.files && cb.files.length) return;              // Dateien macht addImageBlobHook
      const html = cb.getData("text/html") || "";
      const text = cb.getData("text/plain") || "";
      const ausHtml = /<img\b[^>]*\bsrc=["']([^"']+)["']/i.exec(html);
      const ausText = /^!\[([^\]]*)\]\(([^)\s]+)\)$/.exec(text.trim());
      if (!ausHtml && !ausText) return;
      const url = ausText ? ausText[2] : ausHtml[1];
      if (!/^\/media\/wiki\//.test(url)) return;            // fremde Adressen nicht einbetten
      const alt = ausText ? ausText[1] : "";
      e.preventDefault();
      e.stopImmediatePropagation();          // sonst fügt der Markdown-Zweig dasselbe Bild erneut ein
      insertMarkdownAtCursor(`![${alt}](${url})`);
      state.dirty = true;
    }, true);

    /* Mehrere Dateien auf einmal einfügen oder ablegen */
    const uploadMany = async (files) => {
      const list = Array.from(files);
      if (!list.length) return;
      const status = $("#ed-status");
      let done = 0;
      for (const f of list) {
        if (status) status.textContent = `Lade ${f.name} hoch (${done + 1}/${list.length}) …`;
        try {
          const r = await uploadFile(f);
          if (r.kind === "image") insert(`![${f.name.replace(/\.[^.]+$/, "")}](${r.url})\n`);
          else if (r.kind === "video") insert(`![${f.name.replace(/\.[^.]+$/, "")}](${r.url})\n`);
          else insert(`[${f.name}](${r.url})\n`);
          done++;
        } catch (err) { toast(`${f.name}: ${err.message}`, true); }
      }
      if (status) status.textContent = done ? `${done} Datei${done === 1 ? "" : "en"} eingefügt` : "";
      setTimeout(() => { if (status) status.textContent = ""; }, 2500);
    };
    root.addEventListener("paste", (e) => {
      const f = e.clipboardData && e.clipboardData.files;
      if (f && f.length > 1) { e.preventDefault(); e.stopPropagation(); uploadMany(f); }
    }, true);
    root.addEventListener("drop", (e) => {
      const f = e.dataTransfer && e.dataTransfer.files;
      if (f && f.length > 1) { e.preventDefault(); e.stopPropagation(); uploadMany(f); }
    }, true);

    /* Klick unter den letzten Block hängt einen Absatz an – sonst kommt man am Ende
       eines Callouts oder einer Tabelle nicht mehr weiter. */
    root.addEventListener("mousedown", (e) => {
      if (!ed.isWysiwygMode()) return;
      const el = pm();
      if (!el || e.target !== el) return;
      const last = el.lastElementChild;
      if (!last) return;
      if (e.clientY <= last.getBoundingClientRect().bottom) return;
      const md = ed.getMarkdown();
      if (/\n\n$/.test(md)) return;
      setMd(md + "\n\n");
      state.dirty = true;
    });

    /* ---- Kontextmenüs beim Klick in Tabellen, auf Blöcke (Spalten, Callout, Box, Ausrichtung) und Bilder ---- */
    const ctx = document.createElement("div");
    ctx.className = "ed-ctx hidden";
    document.body.appendChild(ctx);
    ctx.addEventListener("mousedown", (e) => e.preventDefault());
    const frame = document.createElement("div"); frame.className = "ed-resize-frame hidden"; document.body.appendChild(frame);
    const handle = document.createElement("div"); handle.className = "ed-resize hidden"; handle.title = "Ziehen zum Skalieren"; handle.setAttribute("role", "button"); handle.setAttribute("aria-label", "Bildbreite ändern"); document.body.appendChild(handle);
    let ctxTarget = null;
    const hideCtx = () => { if (emojiZu) emojiZu(); if (farbZu) farbZu(); ctx.classList.add("hidden"); frame.classList.add("hidden"); handle.classList.add("hidden"); if (ctxTarget && ctxTarget.classList) ctxTarget.classList.remove("ed-selected"); ctxTarget = null; };
    const placeCtx = (el, html, wire, name) => {
      hideBubble();                                  // Block- und Textleiste schließen sich aus
      ctx.innerHTML = html;
      ctx.setAttribute("role", "toolbar");
      ctx.setAttribute("aria-label", name || "Werkzeuge");
      // Ohne Beschriftung braucht der Zustand eine Ansage – die Klasse allein hört niemand.
      ctx.querySelectorAll("button").forEach((b) => {
        if (b.hasAttribute("data-act")) return;
        b.setAttribute("aria-pressed", b.classList.contains("on") ? "true" : "false");
      });
      ctx.classList.remove("hidden");
      if (wire) wire(ctx);
      const r = el.getBoundingClientRect();
      const w = ctx.offsetWidth;
      ctx.style.left = `${window.scrollX + Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
      ctx.style.top = `${window.scrollY + r.bottom + 8}px`;
    };
    /* Die Knöpfe tragen nur noch Symbole – der title ist damit zugleich ihr zugänglicher Name. */
    const btn = (attr, val, title, label, cls) =>
      `<button type="button" ${attr}="${esc(String(val))}" title="${esc(title)}" aria-label="${esc(title)}" class="${cls || ""}">${
        // Eigene Symbole sind fertiges SVG, alles andere kann aus dem Dokument stammen
        // (etwa das Emoji eines Hinweises) und muss entschärft werden.
        typeof label === "string" && label.startsWith("<svg") ? label : esc(String(label))}</button>`;

    /* Der Text zerfällt in oberste Blöcke: Absatz, Liste, Tabelle, Codeblock, $$-Block, :::-Block.
       Über die Reihenfolge lassen sie sich den obersten Elementen im Editor zuordnen. */
    // Die Zerlegung in oberste Blöcke steht in EDMD – sie ist reine Textarbeit und wird
    // dort auch geprüft (tests/rundlauf.html).
    const topLevelBlocks = EDMD.topLevelBlocks;

    /* Die obersten Elemente, die im Markdown auch wirklich einen Block ergeben.
       Ein leerer Absatz steht im Editor für eine Leerzeile und zählt deshalb nicht mit. */
    const hasMedia = (el) => !!el.querySelector("img, video, audio, table, hr") || el.tagName === "HR";
    const blockEls = () => {
      const el = pm();
      if (!el) return [];
      return Array.from(el.children)
        .filter((c) => !c.classList.contains("ed-nichtinhalt"))
        .filter((c) => c.textContent.trim() || hasMedia(c));
    };

    /* Auf welchen dieser Blöcke zeigt ein Element (oder der Cursor)? */
    const topElFor = (node) => {
      const el = pm();
      if (!el || !node) return null;
      let cur = node.nodeType === 1 ? node : node.parentElement;
      while (cur && cur.parentElement !== el) cur = cur.parentElement;
      return cur && el.contains(cur) ? cur : null;
    };
    const indexOfTop = (topEl) => blockEls().indexOf(topEl);
    const currentTopIndex = () => {
      const sel = document.getSelection();
      return sel && sel.anchorNode ? indexOfTop(topElFor(sel.anchorNode)) : -1;
    };

    /* Text an der Cursorstelle als eigener Block einsetzen.
       Statt DOM und Markdown über Zählungen aufeinander abzubilden (was an leeren Absätzen und
       Sonderblöcken scheitert), wird an der Cursorstelle eine Marke gesetzt, das Markdown geholt
       und die Marke durch den neuen Block ersetzt. Das trifft die Stelle immer. */
    const INSERT_TOKEN = "zzeinfuegestellezz";
    /* Höchstens eine Leerzeile am Stück – aber nur außerhalb von Codeblöcken. */
    const entleere = EDMD.entleere;
    const insertMarkdownAtCursor = (text) => {
      const body = String(text || "").replace(/\n+$/, "");
      if (!body) return;
      let md;
      // Ist ein ganzer Block ausgewählt (Callout, Spalten, Bild …), würde replaceSelection ihn
      // ersetzen statt die Marke einzusetzen – solche Blöcke sind atomar. Dann ohne Marke arbeiten.
      const atomAusgewaehlt = (() => {
        const sel = document.getSelection();
        if (!sel || !sel.anchorNode) return false;
        const top = topElFor(sel.anchorNode);
        return !!(top && (top.classList.contains("toastui-editor-custom-block") || top.querySelector("img, video, audio")));
      })();
      // Auf welchem Block steht der Cursor? Gebraucht, wenn die Marke nicht in den Text kommt:
      // Auf einem Schild (Einbau, Abschnittsmarke, Bild) gibt es keine Textstelle, in die sich
      // eine Marke setzen ließe. Dann kommt der neue Block direkt HINTER dieses Schild – nicht
      // ans Dokumentende, wo ihn niemand sucht. Beim Einbau heißt das: auf DIESER Seite, unter
      // dem eingebundenen Abschnitt; der eingebundene Text selbst gehört zur Quellseite.
      const blockIdx = currentTopIndex();
      const aufEinbau = (() => {
        const sel = document.getSelection();
        const top = sel && sel.anchorNode ? topElFor(sel.anchorNode) : null;
        return !!(top && top.querySelector(".ed-einbau"));
      })();
      try {
        if (!atomAusgewaehlt) ed.replaceSelection(INSERT_TOKEN);
        md = ed.getMarkdown();
      } catch (e) {
        md = ed.getMarkdown();
      }
      const idx = md.split("\n").findIndex((l) => l.includes(INSERT_TOKEN));
      if (idx < 0) {
        const rein = md.replace(new RegExp(INSERT_TOKEN, "g"), "");
        const { lines: zl, blocks: zb } = topLevelBlocks(rein);
        const ziel = blockIdx >= 0 ? zb[blockIdx] : null;
        if (ziel) {
          setMd(entleere([...zl.slice(0, ziel.end), "", ...body.split("\n"), "", ...zl.slice(ziel.end)]).join("\n"));
          if (aufEinbau) toast("Der eingebundene Abschnitt wird auf seiner Quellseite geändert – der Text steht jetzt darunter.");
        } else {                                       // gar kein Block unter dem Cursor: ans Ende
          setMd(rein.replace(/\n+$/, "") + "\n\n" + body + "\n");
        }
        return;
      }
      const lines = md.split("\n");
      const rest = lines[idx].split(INSERT_TOKEN).join("");
      // Steht der Cursor ganz vorn in der Zeile, will man den Block DAVOR haben – wer am
      // Zeilenanfang einfügt, meint „vor diesem Absatz“, nicht „dahinter“.
      const vorn = lines[idx].startsWith(INSERT_TOKEN) && rest.trim();
      // Innerhalb einer Tabelle, eines Codeblocks oder eines :::-Blocks darf nicht getrennt
      // werden – der neue Block kommt dann hinter die ganze Struktur.
      const { blocks } = topLevelBlocks(lines.join("\n"));
      const umgebend = blocks.find((x) => idx >= x.start && idx < x.end);
      const mehrzeilig = umgebend && umgebend.end - umgebend.start > 1;
      let out;
      if (mehrzeilig) {
        lines[idx] = rest;
        out = [...lines.slice(0, umgebend.end), "", ...body.split("\n"), "", ...lines.slice(umgebend.end)];
      } else if (vorn) {
        out = [...lines.slice(0, idx), "", ...body.split("\n"), "", rest, ...lines.slice(idx + 1)];
      } else {
        const behalten = rest.trim() ? [rest] : [];    // leere Zeile weicht dem neuen Block
        out = [...lines.slice(0, idx), ...behalten, "", ...body.split("\n"), "", ...lines.slice(idx + 1)];
      }
      // Nur die selbst erzeugten Leerzeilen um die Einfügestelle glätten – ein globaler
      // Kollaps würde Leerzeilen in Codeblöcken zusammenziehen.
      setMd(entleere(out).join("\n").replace(/^\n+/, ""));
    };
    state.insertBlock = insertMarkdownAtCursor;

    /* --- Ziehgriff: oberste Blöcke im Editor umsortieren --------------------------------
       Der Griff erscheint links neben dem Block, unter dem die Maus steht. Verschoben wird
       im Markdown (die Blockgrenzen kennt topLevelBlocks), nicht im Editor-Baum. */
    const grip = document.createElement("div");
    grip.className = "ed-grip hidden";
    grip.title = "Ziehen zum Verschieben";
    grip.innerHTML = I.griff;
    grip.setAttribute("role", "button");
    grip.setAttribute("aria-label", "Block verschieben");
    document.body.appendChild(grip);
    let dragFrom = -1;

    const placeGrip = (el, index) => {
      const r = el.getBoundingClientRect();
      // Der Griff steht links neben dem Block. In einem Spaltenabschnitt ist das die linke
      // Kante DER SPALTE – ohne diese Rechnung landete er mitten in der Nachbarspalte.
      grip.style.left = `${r.left - 22}px`;
      grip.style.top = `${window.scrollY + r.top + 2}px`;
      if (!r.width || !r.height) return hideGrip();
      grip.classList.remove("hidden");
      grip.dataset.index = String(index);      // am Element ablesbar – erleichtert Tests
    };
    const hideGrip = () => { grip.classList.add("hidden"); grip.dataset.index = "-1"; };

    root.addEventListener("mousemove", (e) => {
      if (!ed.isWysiwygMode() || dragFrom >= 0) return;
      const el = pm();
      if (!el) return hideGrip();
      const cur = topElFor(e.target);
      const idx = cur ? indexOfTop(cur) : -1;
      if (idx < 0) return hideGrip();
      placeGrip(cur, idx);
    });
    root.addEventListener("mouseleave", (e) => { if (!grip.contains(e.relatedTarget)) hideGrip(); });

    const clearBlockDrop = () => {
      blockEls().forEach((c) => c.classList.remove("blk-before", "blk-after"));
    };

    /* Ziehen mit der Maus statt über HTML5-Drag&Drop: ProseMirror greift beim nativen Ziehen
       selbst ein, und der Ablauf lässt sich so auch prüfen. */
    grip.draggable = false;
    grip.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const from = parseInt(grip.dataset.index || "-1", 10);
      if (from < 0) return;
      dragFrom = from;
      grip.classList.add("dragging");
      let target = -1, before = false;

      const move = (ev) => {
        const cur = topElFor(document.elementFromPoint(ev.clientX, ev.clientY));
        clearBlockDrop();
        target = cur ? indexOfTop(cur) : -1;
        if (target < 0) return;
        const r = cur.getBoundingClientRect();
        before = ev.clientY < r.top + r.height / 2;
        cur.classList.add(before ? "blk-before" : "blk-after");
      };
      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        grip.classList.remove("dragging");
        clearBlockDrop();
        const to = target;
        dragFrom = -1;
        hideGrip();
        if (to < 0 || to === from) return;
        moveBlock(from, to, before);
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });

    /* Marken bilden einen Abschnitt. Wer eine davon zieht, meint den ganzen Abschnitt –
       sonst bliebe der Inhalt ohne Anfang oder Ende zurück. */
    const sektionsBereich = (lines, blocks, index) => {
      const art = (j) => (lines[blocks[j].start] || "").trim();
      const auf = (x) => ABSCHNITT_AUF.has(x);
      const a = art(index);
      if (!auf(a) && a !== "$$spalte" && a !== "$$koerper" && a !== "$$ende") return null;
      let start = auf(a) ? index : -1;
      if (start < 0) {
        let t = 0;
        for (let j = index - 1; j >= 0; j--) {
          const k = art(j);
          if (k === "$$ende") t++;
          else if (auf(k)) { if (!t) { start = j; break; } t--; }
        }
      }
      if (start < 0) return null;
      let ende = -1, t = 1;
      for (let j = start + 1; j < blocks.length; j++) {
        const k = art(j);
        if (auf(k)) t++;
        else if (k === "$$ende") { t--; if (!t) { ende = j; break; } }
      }
      return ende < 0 ? null : { start, ende };
    };

    /* Einen obersten Block im Markdown an eine andere Stelle setzen. */
    const moveBlock = (from, to, before) => {
      const md = ed.getMarkdown();
      const { lines, blocks } = topLevelBlocks(md);
      if (blocks.length !== blockEls().length || !blocks[from] || !blocks[to]) {
        return toast("Die Blöcke lassen sich hier nicht eindeutig zuordnen – "
                     + "bitte mit Strg+Umschalt+C den Markdown-Text kopieren und dort von Hand umstellen.", true);
      }
      const ber = sektionsBereich(lines, blocks, from);
      const von = ber ? ber.start : from, bis = ber ? ber.ende : from;
      if (to >= von && to <= bis) return;                  // Ziel liegt im Abschnitt selbst
      const anzahl = bis - von + 1;
      const parts = blocks.map((b) => lines.slice(b.start, b.end));
      const moved = parts.splice(von, anzahl);
      let target = to > bis ? to - anzahl : to;
      if (!before) target += 1;
      target = Math.max(0, Math.min(parts.length, target));
      parts.splice(target, 0, ...moved);
      setMd(parts.map((x) => x.join("\n")).join("\n\n"));
      state.dirty = true;
      toast("Block verschoben");
    };

    editorCleanupPush(() => grip.remove());

    /* Markdown-Umschreibung: die äußeren $$-Blöcke des Editorformats in Dokumentreihenfolge */
    const outerBlocks = () => {
      const md = ed.getMarkdown();
      const lines = md.split("\n");
      const blocks = []; let cur = null;
      const zaun = MD.fenceMask(lines);
      for (let i = 0; i < lines.length; i++) {
        if (zaun[i]) continue;                       // "$$" im Codebeispiel ist kein Block
        const l = lines[i];
        const m = !cur && MARKEN_RE.exec(l);
        if (m) cur = { start: i, kind: m[1] };
        else if (cur && /^\$\$[ \t]*$/.test(l)) { cur.end = i + 1; cur.lines = lines.slice(cur.start, cur.end); blocks.push(cur); cur = null; }
      }
      return { lines, blocks };
    };
    /* Toast UIs setMarkdown ersetzt den kompletten Dokumentinhalt in einer einzigen
       ProseMirror-Transaktion. Jede Cursorposition innerhalb des ersetzten Bereichs bildet
       ProseMirror dabei auf dessen Ende ab – daher sprang der Cursor nach jeder Operation ans
       Dokumentende. Deshalb bauen wir die beiden Schritte selbst nach (Markdown-Modell füllen,
       daraus das WYSIWYG-Modell erzeugen), vergleichen alte und neue Blöcke und tauschen nur
       den wirklich geänderten Mittelteil. Die Selektion führt ProseMirror dann über tr.mapping
       von allein korrekt mit, und das DOM bleibt außerhalb der Änderung unangetastet – kein
       Neuaufbau der Bilder, kein Scrollsprung.
       Optional nimmt setMd eine Zielposition entgegen – dort landet der Cursor stattdessen. */
    const wwView = () => { try { return ed.wwEditor.view; } catch (e) { return null; } };

    const setzeAuswahl = (a, b) => {
      const view = wwView();
      if (!view) return;
      const max = view.state.doc.content.size;
      const von = Math.max(1, Math.min(a, max));
      const bis = Math.max(von, Math.min(b == null ? a : b, max));
      try { ed.setSelection(von, bis); } catch (e) { /* egal */ }
    };

    /* Toast UI rendert im WYSIWYG kein width-Attribut an Bildern – die gespeicherte Breite
       steckt in der Adresse (#w=…) und wird nur beim Anzeigen des Artikels ausgewertet. Ohne
       diesen Durchlauf zeigt der Editor jedes Bild in voller Breite; der Ziehgriff misst dann
       etwas anderes, als er zurückschreibt, und das Bild schrumpft bei jedem Anfassen.
       Der Durchlauf setzt nur style-Eigenschaften innerhalb einer NodeView ohne contentDOM –
       ProseMirror liest das nicht in das Dokument zurück, das Markdown bleibt unberührt. */
    const bildBreitenAnwenden = () => {
      const el = pm();
      if (!el) return;
      el.querySelectorAll("img, video").forEach((im) => {
        if (im.classList.contains("ProseMirror-separator") || im.closest(".ed-nichtinhalt")) return;
        const w = MD.imageWidth(im.getAttribute("src") || "");
        im.style.width = w ? (/%$/.test(w) ? w : `${w}px`) : "";
        im.style.height = w ? "auto" : "";
      });
    };

    const setMdVoll = (md, ziel) => {
      let pos = null;
      try { pos = ed.getSelection(); } catch (e) { /* egal */ }
      ed.setMarkdown(md, false);
      const wunsch = typeof ziel === "number" ? [ziel, ziel] : pos;
      if (wunsch) setzeAuswahl(wunsch[0], wunsch[1]);
    };

    const setMd = (md, ziel) => {
      const y = window.scrollY;
      const view = wwView();
      let neu = null;
      if (view && ed.isWysiwygMode()) {
        try {
          ed.mdEditor.setMarkdown(md, false);              // füllt toastMark neu
          neu = ed.convertor.toWysiwygModel(ed.toastMark.getRootNode());
        } catch (e) { neu = null; }
      }
      if (!neu || !neu.content || !neu.content.childCount) {
        setMdVoll(md, ziel);
      } else {
        const alt = view.state.doc.content, inhalt = neu.content;
        let k = 0;                                         // gleiche Blöcke am Anfang
        while (k < alt.childCount && k < inhalt.childCount && alt.child(k).eq(inhalt.child(k))) k++;
        let s = 0;                                         // gleiche Blöcke am Ende
        while (s < alt.childCount - k && s < inhalt.childCount - k
               && alt.child(alt.childCount - 1 - s).eq(inhalt.child(inhalt.childCount - 1 - s))) s++;
        if (k < alt.childCount || k < inhalt.childCount) {
          let von = 0;
          for (let i = 0; i < k; i++) von += alt.child(i).nodeSize;
          let bis = alt.size;
          for (let i = 0; i < s; i++) bis -= alt.child(alt.childCount - 1 - i).nodeSize;
          const mitte = [];
          for (let i = k; i < inhalt.childCount - s; i++) mitte.push(inhalt.child(i));
          const $f = view.state.selection.$from;
          const vorher = view.state.selection.from;
          // Den Knoten unter dem Cursor merken: wird ein Block nur umschlossen oder verschoben,
          // steht er hinterher unverändert an anderer Stelle – dann zieht der Cursor mit.
          const altKnoten = $f.depth > 0 ? $f.node(1) : null;
          const altOffset = $f.depth > 0 ? vorher - $f.before(1) : 0;
          view.dispatch(view.state.tr.replaceWith(von, bis, mitte));
          if (typeof ziel === "number") setzeAuswahl(ziel);
          else if (vorher > von && vorher < bis) {
            // Lag der Cursor mitten im getauschten Bereich, hat ProseMirror ihn an dessen Ende
            // geschoben. Erst den unveränderten Knoten suchen, sonst den Abstand beibehalten.
            let stelle = -1, lauf = von;
            for (const kn of mitte) {
              if (altKnoten && kn.eq(altKnoten)) { stelle = lauf; break; }
              lauf += kn.nodeSize;
            }
            const laenge = mitte.reduce((n, kn) => n + kn.nodeSize, 0);
            setzeAuswahl(stelle >= 0 ? stelle + altOffset : Math.min(vorher, von + Math.max(0, laenge - 1)));
          }
        } else if (typeof ziel === "number") setzeAuswahl(ziel);
      }
      bildBreitenAnwenden();
      window.scrollTo(0, y);
      try { ed.getCurrentModeEditor().view.focus(); } catch (e) { /* egal */ }
    };

    const rewriteBlock = (index, text) => {
      const { lines, blocks } = outerBlocks();
      const b = blocks[index];
      if (!b) return toast("Block nicht gefunden – bitte mit Strg+Umschalt+C den Markdown-Text "
                           + "kopieren und dort von Hand ändern.", true);
      const mid = text == null ? [] : text.replace(/\n$/, "").split("\n");
      setMd([...lines.slice(0, b.start), ...mid, ...lines.slice(b.end)].join("\n"));
      state.dirty = true;
      hideCtx();
    };
    /* Jeder $$-Block von Toast UI hat im Editor genau ein Wurzelelement. Damit stimmt die
       Reihenfolge der Elemente im Editor mit der Reihenfolge der Bloecke im Markdown ueberein –
       darauf beruht die Zuordnung im Blockmenue. */
    const BLOCK_SEL = ".toastui-editor-custom-block";
    const blockRoots = () => Array.from(pm() ? pm().querySelectorAll(BLOCK_SEL) : []).filter((el) => !(el.parentElement && el.parentElement.closest(BLOCK_SEL)));

    const blockEditDialog = (index) => {
      const { blocks } = outerBlocks();
      const b = blocks[index];
      if (!b) return;
      const body = b.lines.slice(1, -1);
      hideCtx();
      if (b.kind === "columns") {
        const cols = body.join("\n").split(/\n[ \t]*\|\|\|[ \t]*\n/);
        dialog(`<h2>Spalten bearbeiten</h2><div class="block-edit"><div class="cols">${cols.map((c, i) => `<div><label>Spalte ${i + 1}</label><textarea data-col="${i}">${esc(c)}</textarea></div>`).join("")}</div>
          <div class="btn-row" style="margin-top:10px"><button class="btn secondary small" id="be-add" type="button">+ Spalte</button><button class="btn secondary small" id="be-del" type="button">– letzte Spalte</button></div></div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="be-ok" type="button">Übernehmen</button></div>`,
          (dlg, box) => {
            dlg.classList.add("wide"); dlg.addEventListener("close", () => dlg.classList.remove("wide"), { once: true });
            const grid = box.querySelector(".cols");
            box.querySelector("#be-add").onclick = () => { if (grid.children.length >= 5) return; const n = grid.children.length; grid.insertAdjacentHTML("beforeend", `<div><label>Spalte ${n + 1}</label><textarea data-col="${n}">Spalte ${n + 1}</textarea></div>`); };
            box.querySelector("#be-del").onclick = () => { if (grid.children.length > 2) grid.lastElementChild.remove(); };
            box.querySelector("#be-ok").onclick = () => { const vals = Array.from(box.querySelectorAll("textarea")).map((t) => t.value); dlg.close(); rewriteBlock(index, "$$columns\n" + vals.join("\n|||\n") + "\n$$"); };
          });
      } else if (b.kind === "callout") {
        const head = body[0].trim().split(/\s+/); let kind = head[0] in MD.CALLOUTS ? head[0] : "info";
        dialog(`<h2>Callout bearbeiten</h2><div class="block-edit">
          <div class="callout-pick" id="ck">${["info", "tip", "warning", "success", "danger", "note"].map((k) => `<button type="button" class="btn ${k === kind ? "" : "secondary"}" data-k="${k}">${MD.CALLOUTS[k]} ${k}</button>`).join("")}</div>
          <label for="em-input">Emoji</label><div class="em-row"><input type="text" id="em-input" maxlength="8" autocomplete="off"><span class="help">eintippen oder unten wählen</span></div><div class="em-grid" id="em-grid"></div>
          <label>Inhalt (Markdown)</label><textarea id="be-body">${esc(body.slice(1).join("\n"))}</textarea></div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="be-ok" type="button">Übernehmen</button></div>`,
          (dlg, box) => {
            dlg.classList.add("wide"); dlg.addEventListener("close", () => dlg.classList.remove("wide"), { once: true });
            const getEmoji = emojiPicker(box, head.slice(1).join(" ") || MD.CALLOUTS[kind]);
            box.querySelectorAll("#ck [data-k]").forEach((x) => x.onclick = () => { kind = x.dataset.k; box.querySelectorAll("#ck .btn").forEach((y) => y.classList.toggle("secondary", y !== x)); });
            box.querySelector("#be-ok").onclick = () => { const e = getEmoji(); const txt = box.querySelector("#be-body").value; dlg.close(); rewriteBlock(index, `$$callout\n${kind} ${e}\n${txt}\n$$`); };
          });
      } else {
        dialog(`<h2>Ausrichtung bearbeiten</h2><div class="block-edit"><label>Inhalt (Markdown)</label><textarea id="be-body">${esc(body.slice(1).join("\n"))}</textarea></div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="be-ok" type="button">Übernehmen</button></div>`,
          (dlg, box) => { box.querySelector("#be-ok").onclick = () => { const txt = box.querySelector("#be-body").value; dlg.close(); rewriteBlock(index, `$$align\n${body[0]}\n${txt}\n$$`); }; });
      }
    };

    /* Marken gehören zu einem Abschnitt: die öffnende Marke, beliebig viele Spaltenmarken und
       die schließende. Wer eine davon anfasst, meint immer den ganzen Abschnitt. */
    const MARKEN = ["spalten", "spalte", "ausrichtung", "hinweis", "akkordeon", "koerper", "baustein", "ende"];
    // Dieselbe Liste wie EDMD.ABSCHNITT_AUF – ohne den Baustein bekam dessen Schlussmarke das
    // Menü eines losen Blocks („löschen“, „duplizieren“) statt das des Abschnitts.
    const istOeffner = (k) => k === "spalten" || k === "ausrichtung" || k === "hinweis" || k === "akkordeon" || k === "baustein";
    const sektion = (blocks, index) => {
      const b = blocks[index];
      if (!b || !MARKEN.includes(b.kind)) return null;
      let auf = istOeffner(b.kind) ? index : -1;
      if (auf < 0) {                                  // zur öffnenden Marke zurückgehen
        // Rückwärts zählt jede geschlossene Sektion mit; die erste öffnende Marke auf
        // Tiefe null gehört zu dieser Marke.
        let tiefe = 0;
        for (let j = index - 1; j >= 0; j--) {
          const k = blocks[j].kind;
          if (k === "ende") tiefe++;
          else if (istOeffner(k)) { if (!tiefe) { auf = j; break; } tiefe--; }
        }
      }
      if (auf < 0) return null;
      let zu = -1, tiefe = 1;
      const spalten = [];
      for (let j = auf + 1; j < blocks.length; j++) {
        const k = blocks[j].kind;
        if (istOeffner(k)) tiefe++;
        else if (k === "ende") { tiefe--; if (!tiefe) { zu = j; break; } }
        else if (k === "spalte" && tiefe === 1) spalten.push(j);
      }
      const kindAuf = blocks[auf].kind;
      const art = kindAuf === "spalten" ? "columns" : kindAuf === "hinweis" ? "hinweis"
        : kindAuf === "akkordeon" ? "akkordeon" : "align";
      return { art, auf, zu, spalten: art === "columns" ? spalten : [] };
    };

    /* Mehrere Blöcke in einem Rutsch ersetzen – von hinten nach vorn, damit die vorher
       ermittelten Zeilennummern gültig bleiben. text === null löscht den Block. */
    const rewriteBloecke = (aenderungen) => {
      const { lines, blocks } = outerBlocks();
      let out = lines.slice();
      aenderungen.slice().sort((a, b) => b.index - a.index).forEach(({ index, text }) => {
        const b = blocks[index];
        if (!b) return;
        const mid = text == null ? [] : String(text).replace(/\n$/, "").split("\n");
        out = [...out.slice(0, b.start), ...mid, ...out.slice(b.end)];
      });
      setMd(entleere(out).join("\n"));
      state.dirty = true;
      hideCtx();
    };

    /* Zu einem gewöhnlichen Block: die Marke, die den ihn umgebenden Abschnitt eröffnet. */
    const MARKE_SEL = ".sek-spalten, .sek-ausrichtung, .sek-hinweis, .sek-akkordeon, .sek-baustein";
    const umgebenderAbschnitt = (top) => {
      const el = pm();
      if (!el || !top) return null;
      const kinder = Array.from(el.children);
      const i = kinder.indexOf(top);
      if (i < 0) return null;
      let tiefe = 0;
      for (let j = i; j >= 0; j--) {
        const c = kinder[j];
        if (!c.querySelector) continue;
        if (j !== i && c.querySelector(".sek-ende")) { tiefe++; continue; }
        if (c.querySelector(MARKE_SEL)) { if (!tiefe) return c; tiefe--; }
      }
      return null;
    };

    const blockMenu = (el) => {
      const wurzeln = blockRoots();
      const index = wurzeln.indexOf(el);
      if (index < 0) return hideCtx();
      const { lines, blocks } = outerBlocks();
      // Nur handeln, wenn Editor und Text gleich viele Blöcke sehen – sonst zeigte das Menü
      // auf einen anderen Block, als der Nutzer angeklickt hat.
      if (blocks.length !== wurzeln.length) {
        hideCtx();
        return toast("Die Blöcke lassen sich hier nicht eindeutig zuordnen – bitte mit "
                     + "Strg+Umschalt+C den Markdown-Text kopieren und dort von Hand ändern.", true);
      }
      const b = blocks[index];
      if (!b) return hideCtx();

      const sek = sektion(blocks, index);
      if (sek) {
        let html;
        const hw = sek.art === "hinweis" ? hinweisKopf(blocks[sek.auf].lines[1]) : null;
        if (sek.art === "columns") {
          const n = sek.spalten.length + 1;
          html = `<span class="lbl" title="Spalten">${I.spalten}</span>${[2, 3, 4, 5].map((k) => btn("data-cols", k, `${k} Spalten`, k, "num" + (k === n ? " on" : ""))).join("")}<span class="sep"></span>`;
        } else if (hw) {
          html = KINDS.map((k) => btn("data-kind", k, HINWEIS_NAME[k], MD.CALLOUTS[k], k === hw.kind ? "on" : "")).join("")
               + btn("data-act", "emoji", "Anderes Emoji wählen", I.emoji)
               + btn("data-act", "farbe", "Hintergrundfarbe wählen", I.farbtopf, hw.farbe ? "on" : "")
               + `<span class="sep"></span>`;
        } else if (sek.art === "akkordeon") {
          html = `<span class="lbl" title="Einklappbare Box">${I.akkordeon}</span><span class="sep"></span>`;
        } else {
          const mode = (blocks[sek.auf].lines[1] || "").trim();
          html = AUSRICHTUNGEN.map(([m, sym, t]) => btn("data-mode", m, t, sym, m === mode ? "on" : "")).join("")
               + `<span class="sep"></span>`;
        }
        html += btn("data-act", "loesen", "Abschnitt auflösen, Inhalt behalten", I.aufloesen)
              + btn("data-act", "weg", "Abschnitt samt Inhalt löschen", I.papierkorb, "danger");
        return placeCtx(el, html, (box) => {
          const kopfNeu = (kind, emoji, farbe) =>
            rewriteBloecke([{ index: sek.auf, text: `$$hinweis\n${hinweisZeile(kind, emoji, farbe)}\n$$` }]);
          box.querySelectorAll("[data-kind]").forEach((x) => x.onclick = () => {
            // Ein selbst gewähltes Emoji bleibt erhalten, das vorgegebene wandert mit der Art mit.
            const e = (!hw.emoji || hw.emoji === MD.CALLOUTS[hw.kind]) ? MD.CALLOUTS[x.dataset.kind] : hw.emoji;
            kopfNeu(x.dataset.kind, e, hw.farbe);
          });
          const emKnopf = box.querySelector("[data-act=emoji]");
          if (emKnopf) emKnopf.onclick = () => emojiPopover(emKnopf, hw.emoji, (neu) => kopfNeu(hw.kind, neu, hw.farbe));
          const farbKnopf = box.querySelector("[data-act=farbe]");
          if (farbKnopf) farbKnopf.onclick = () => farbPopover(farbKnopf, hw.farbe, (neu) => kopfNeu(hw.kind, hw.emoji, neu));
          box.querySelectorAll("[data-cols]").forEach((x) => x.onclick = () => {
            const k = +x.dataset.cols, n = sek.spalten.length + 1;
            if (k === n) return hideCtx();
            if (k > n) {
              const zu = sek.zu < 0 ? null : sek.zu;
              const neueMarken = Array.from({ length: k - n }, () => "$$spalte\n$$").join("\n\n");
              if (zu === null) return hideCtx();
              rewriteBloecke([{ index: zu, text: `${neueMarken}\n\n$$ende\n$$` }]);
            } else {
              rewriteBloecke(sek.spalten.slice(k - 1).map((i) => ({ index: i, text: null })));
            }
          });
          box.querySelectorAll("[data-mode]").forEach((x) => x.onclick = () =>
            rewriteBloecke([{ index: sek.auf, text: `$$ausrichtung\n${x.dataset.mode}\n$$` }]));
          box.querySelector("[data-act=loesen]").onclick = () =>
            rewriteBloecke([sek.auf, ...sek.spalten, ...(sek.zu < 0 ? [] : [sek.zu])].map((i) => ({ index: i, text: null })));
          box.querySelector("[data-act=weg]").onclick = () => {
            if (sek.zu < 0) {
              // Ohne Schlussmarke ist nicht zu erkennen, wo der Abschnitt endet – dann nur die
              // Marken entfernen, statt womöglich den halben Artikel zu löschen.
              toast("Dem Abschnitt fehlt die Schlussmarke – nur die Marken wurden entfernt.", true);
              return rewriteBloecke([sek.auf, ...sek.spalten].map((i) => ({ index: i, text: null })));
            }
            const von = blocks[sek.auf].start;
            const bis = blocks[sek.zu].end;
            setMd(entleere([...lines.slice(0, von), ...lines.slice(bis)]).join("\n"));
            state.dirty = true; hideCtx();
          };
        }, sek.art === "hinweis" ? "Hinweis" : sek.art === "columns" ? "Spalten"
           : sek.art === "akkordeon" ? "Einklappbare Box" : "Ausrichtung");
      }

      // Geschlossene Blöcke: die einklappbare Box – und Altbestand aus Browser-Entwürfen,
      // die noch $$callout/$$columns/$$align enthalten können.
      let html = "";
      if (b.kind === "columns") {
        const n = b.lines.slice(1, -1).join("\n").split(/\n[ \t]*\|\|\|[ \t]*\n/).length;
        html = `<span class="lbl" title="Spalten">${I.spalten}</span>${[2, 3, 4, 5].map((k) => btn("data-cols", k, `${k} Spalten`, k, "num" + (k === n ? " on" : ""))).join("")}<span class="sep"></span>`;
      } else if (b.kind === "callout") {
        const kind = b.lines[1].trim().split(/\s+/)[0];
        html = KINDS.map((k) => btn("data-kind", k, HINWEIS_NAME[k], MD.CALLOUTS[k], k === kind ? "on" : "")).join("") + `<span class="sep"></span>`;
      } else if (b.kind === "align") {
        const mode = b.lines[1].trim();
        html = AUSRICHTUNGEN.map(([m, sym, t]) => btn("data-mode", m, t, sym, m === mode ? "on" : "")).join("") + `<span class="sep"></span>`;
      }
      const bearbeitbar = ["columns", "callout", "align"].includes(b.kind);
      html += (bearbeitbar ? btn("data-act", "edit", "Inhalt bearbeiten", I.stift) : "")
            + btn("data-act", "dup", "Duplizieren", I.duplizieren) + btn("data-act", "del", "Block löschen", I.papierkorb, "danger");
      // Ohne Maus gibt es keinen Ziehgriff – dann verschieben zwei Knöpfe den Block.
      if (window.matchMedia("(max-width: 760px), (pointer: coarse)").matches) {
        html += `<span class="sep"></span>${btn("data-move", -1, "Nach oben", "↑", "num")}${btn("data-move", 1, "Nach unten", "↓", "num")}`;
      }
      placeCtx(el, html, (box) => {
        box.querySelectorAll("[data-cols]").forEach((x) => x.onclick = () => {
          const cols = b.lines.slice(1, -1).join("\n").split(/\n[ \t]*\|\|\|[ \t]*\n/); const k = +x.dataset.cols;
          while (cols.length < k) cols.push(`Spalte ${cols.length + 1}`);
          rewriteBlock(index, "$$columns\n" + cols.slice(0, k).join("\n|||\n") + "\n$$");
        });
        box.querySelectorAll("[data-kind]").forEach((x) => x.onclick = () => {
          const head = b.lines[1].trim().split(/\s+/); const old = head[0];
          const emoji = head.slice(1).join(" ");
          const e = (!emoji || emoji === MD.CALLOUTS[old]) ? MD.CALLOUTS[x.dataset.kind] : emoji;
          rewriteBlock(index, [`$$callout`, `${x.dataset.kind} ${e}`, ...b.lines.slice(2)].join("\n"));
        });
        box.querySelectorAll("[data-mode]").forEach((x) => x.onclick = () => rewriteBlock(index, ["$$align", x.dataset.mode, ...b.lines.slice(2)].join("\n")));
        const edit = box.querySelector("[data-act=edit]");
        if (edit) edit.onclick = () => blockEditDialog(index);
        box.querySelector("[data-act=dup]").onclick = () => rewriteBlock(index, b.lines.join("\n") + "\n\n" + b.lines.join("\n"));
        box.querySelector("[data-act=del]").onclick = () => rewriteBlock(index, null);
        box.querySelectorAll("[data-move]").forEach((x) => x.onclick = () => {
          const schritt = +x.dataset.move, ziel = index + schritt;
          if (ziel < 0 || ziel >= blocks.length) return;
          hideCtx();
          moveBlock(index, ziel, schritt < 0);
        });
      }, "Block");
    };

    const tableMenu = (cell) => {
      const table = cell.closest("table");
      const html = `${btn("data-cmd", "addRowToUp", "Zeile oberhalb einfügen", I.zeileAuf)}${btn("data-cmd", "addRowToDown", "Zeile unterhalb einfügen", I.zeileAb)}${btn("data-cmd", "removeRow", "Zeile löschen", I.zeileWeg)}<span class="sep"></span>
        ${btn("data-cmd", "addColumnToLeft", "Spalte links einfügen", I.spalteLi)}${btn("data-cmd", "addColumnToRight", "Spalte rechts einfügen", I.spalteRe)}${btn("data-cmd", "removeColumn", "Spalte löschen", I.spalteWeg)}<span class="sep"></span>
        ${btn("data-align", "left", "Spalte linksbündig", I.linksb)}${btn("data-align", "center", "Spalte zentriert", I.mittig)}${btn("data-align", "right", "Spalte rechtsbündig", I.rechtsb)}<span class="sep"></span>
        ${btn("data-cmd", "mergeCells", "Zellen verbinden", I.verbinden)}${btn("data-cmd", "splitCells", "Zellen wieder teilen", I.teilen2)}<span class="sep"></span>
        ${btn("data-cmd", "removeTable", "Tabelle löschen", I.papierkorb, "danger")}`;
      placeCtx(table, html, (box) => {
        box.querySelectorAll("[data-cmd]").forEach((x) => x.onclick = () => {
          /* Verbinden braucht mehrere markierte Zellen, teilen eine verbundene. Ohne das täte
             der Befehl nichts – und ein Knopf, der wortlos nichts tut, sieht nach einem Fehler
             aus. Vor dem Verbinden wird der zuletzt gezogene Zellbereich wiederhergestellt: Der
             Klick auf diesen Knopf selbst kann die Auswahl schon haben zerfallen lassen. */
          if (x.dataset.cmd === "mergeCells" && !zellBereichHerstellen(table)) {
            return toast("Bitte zuerst mehrere Zellen markieren: in eine Zelle klicken und mit "
                         + "gedrückter Maustaste über die anderen ziehen.", true);
          }
          if (x.dataset.cmd === "splitCells") {
            const verbunden = (c) => c.colSpan > 1 || c.rowSpan > 1;
            const markiert = [...table.querySelectorAll("td.toastui-editor-cell-selected, th.toastui-editor-cell-selected")];
            if (!(markiert.length ? markiert : [cell]).some(verbunden)) {
              return toast("Diese Zelle ist nicht verbunden.", true);
            }
          }
          ed.exec(x.dataset.cmd);
          state.dirty = true;
          if (x.dataset.cmd === "removeTable") hideCtx();
        });
        box.querySelectorAll("[data-align]").forEach((x) => x.onclick = () => { ed.exec("alignColumn", { align: x.dataset.align }); state.dirty = true; });
      }, "Tabelle");
    };

    /* Bilder: n-tes Bild im Markdown = n-tes <img> im Editor */
    /* Nur echte Bilder: ![…](film.mp4) und ![…](ton.mp3) stehen zwar auch als Bild-Syntax im
       Markdown, werden aber als <video>/<audio> gerendert. Zählte man sie mit, verschöbe sich die
       Zuordnung n-tes <img> ↔ n-te Fundstelle, und das Bildmenü träfe das falsche Bild. */
    const NICHT_BILD = /\.(mp4|m4v|mov|webm|mp3|m4a|ogg|oga|wav)(\?[^)]*)?(#[^)]*)?$/i;
    /* Bild-Schreibweisen im Text finden – aber nur echte. Ein Beispiel in einem Codeblock oder
       in `Code` ist keine Fundstelle; zählte man es mit, änderte oder löschte das Bildmenü die
       Zeile im Codebeispiel statt des angeklickten Bildes.
       Der Alternativtext darf escapte Klammern enthalten: Dateien heißen durchaus "Foto [1].jpg",
       und Toast UI schreibt sie als "\[1\]" zurück. */
    const codeMaske = (md) => {
      const zeilen = md.split("\n");
      const zaun = MD.fenceMask(zeilen);
      return zeilen.map((z, i) => {
        if (zaun[i]) return " ".repeat(z.length);
        // Inline-Code Zeichen für Zeichen ausblenden, Länge und damit alle Positionen erhalten.
        let out = "", n = 0;
        for (let k = 0; k < z.length; k++) {
          if (z[k] === "`") { let c = 0; while (z[k + c] === "`") c++; n = n ? 0 : c; out += " ".repeat(c); k += c - 1; continue; }
          out += n ? " " : z[k];
        }
        return out;
      }).join("\n");
    };
    const imageOccurrences = (md) => {
      const re = /!\[((?:\\.|[^\]\\])*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
      const maskiert = codeMaske(md);
      const out = [];
      let m;
      while ((m = re.exec(maskiert))) {
        if (NICHT_BILD.test(m[2])) continue;
        // Text aus dem Original nehmen – die Maske dient nur dem Finden.
        out.push({ start: m.index, end: m.index + m[0].length,
                   alt: md.slice(m.index + 2, m.index + 2 + m[1].length), url: m[2] });
      }
      return out;
    };
    /* ProseMirror setzt eigene <img class="ProseMirror-separator"> in den Baum. Zählte man sie
       mit, zeigte das Bildmenü ab dem zweiten Bild auf die falsche Fundstelle im Markdown. */
    // Nur die Bilder des Artikels – die Regel dafür steht in MD.istInhaltsbild.
    const contentImages = () => Array.from(pm().querySelectorAll("img")).filter(MD.istInhaltsbild);

    const rewriteImage = (img, fn) => {
      const bilder = contentImages();
      const index = bilder.indexOf(img);
      const md = ed.getMarkdown();
      const stellen = imageOccurrences(md);
      // Stimmen die Zahlen nicht überein, ist die Zuordnung nicht sicher – dann lieber nichts
      // ändern, als das falsche Bild zu treffen.
      if (stellen.length !== bilder.length) {
        return toast("Die Bilder lassen sich hier nicht eindeutig zuordnen – bitte mit "
                     + "Strg+Umschalt+C den Markdown-Text kopieren und dort von Hand ändern.", true);
      }
      const occ = stellen[index];
      if (!occ) return toast("Bild im Text nicht gefunden.", true);
      const base = occ.url.replace(/#w=[^#]*$/, "");
      const replacement = fn({ alt: occ.alt, url: base, width: MD.imageWidth(occ.url) });
      setMd(md.slice(0, occ.start) + (replacement == null ? "" : replacement) + md.slice(occ.end));
      state.dirty = true;
      hideCtx();
    };
    const imgMd = (alt, url, width) =>
      `![${String(alt || "").replace(/([\[\]])/g, "\\$1")}](${url}${width ? "#w=" + width : ""})`;

    /* Links: n-ter Link im Markdown = n-ter <a> im Editor. Bilder (![…]) sind ausgenommen. */
    const linkOccurrences = (md) => {
      // Der Linktext darf ein vollständiges Bild enthalten: „[![alt](bild.png)](ziel)“ ist ein
      // Link auf „ziel“ – ohne diesen Zweig las die Zählung daraus einen Link namens „![alt“
      // mit der Adresse des Bildes und schrieb beim Ändern am falschen Ort.
      const re = /(^|[^!])\[((?:!\[[^\]]*\]\([^)\s]+(?:\s+"[^"]*")?\)|[^\]])*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
      const out = [];
      let m;
      while ((m = re.exec(md))) out.push({ start: m.index + m[1].length, end: m.index + m[0].length, text: m[2], url: m[3] });
      return out;
    };
    const linkMenu = (a) => {
      a.classList.add("ed-selected");
      const links = Array.from(pm().querySelectorAll("a[href]"));
      const index = links.indexOf(a);
      const href = a.getAttribute("href") || "";
      const rewrite = (fn) => {
        const md = ed.getMarkdown();
        const list = linkOccurrences(md);
        // Automatisch erkannte Adressen stehen ohne […](…) im Text – dann passt die Zählung nicht.
        if (list.length !== links.length || !list[index]) {
          return toast("Dieser Link lässt sich nicht eindeutig zuordnen – bitte mit Strg+Umschalt+C den Markdown-Text kopieren und dort von Hand ändern.", true);
        }
        const o = list[index];
        const rep = fn(o);
        setMd(md.slice(0, o.start) + (rep == null ? "" : rep) + md.slice(o.end));
        state.dirty = true;
        hideCtx();
      };
      const shown = href.length > 44 ? href.slice(0, 42) + "…" : href;
      const html = `<span class="lbl" title="Link">${I.kette}</span><span class="ed-link-url" title="${esc(href)}">${esc(shown)}</span><span class="sep"></span>
        ${btn("data-act", "edit", "Link bearbeiten", I.stift)}<span class="sep"></span>
        ${btn("data-act", "copy", "Adresse kopieren", I.duplizieren)}${btn("data-act", "open", "In neuem Tab öffnen", I.extern)}<span class="sep"></span>
        ${btn("data-act", "unlink", "Link entfernen, Text behalten", I.ketteWeg, "danger")}`;
      placeCtx(a, html, (box) => {
        box.querySelector("[data-act=edit]").onclick = () => {
          const cur = { url: href, text: a.textContent };
          hideCtx();
          linkDialog(cur, ({ url, text }) => rewrite(() => `[${text}](${url})`));
        };
        box.querySelector("[data-act=open]").onclick = () => { window.open(href, "_blank", "noopener"); hideCtx(); };
        box.querySelector("[data-act=copy]").onclick = async () => {
          try { await navigator.clipboard.writeText(new URL(href, location.origin).href); toast("Adresse kopiert"); }
          catch (e) { toast("Kopieren war nicht möglich.", true); }
          hideCtx();
        };
        box.querySelector("[data-act=unlink]").onclick = () => rewrite((o) => o.text);
      }, "Link");
    };
    /* Ein Klick auf ein Bild wählte es aus, ließ den Schreibstrich aber stehen, wo er vorher
       war – meist am Anfang der Überschrift. Wer neben dem Bild weiterschreiben wollte, fand
       keine Stelle dafür: In einer Spalte füllt das Bild die ganze Breite, rechts daneben ist
       nichts mehr zum Anklicken. Nach dem Klick steht der Strich deshalb hinter dem Bild.
       Der Weg führt über die Auswahl im Dokument; ProseMirror übernimmt sie von dort. */
    const strichHinterBild = (img) => {
      try {
        const bereich = document.createRange();
        bereich.setStartAfter(img);
        bereich.collapse(true);
        const aus = window.getSelection();
        aus.removeAllRanges();
        aus.addRange(bereich);
      } catch (e) { /* kein Platz dahinter – dann bleibt der Strich, wo er war */ }
    };
    /* --- Zuschneiden --------------------------------------------------------------------
       Über dem Bild liegt ein Rahmen, den man verschieben und an den vier Ecken ziehen kann;
       alles außerhalb wird abgedunkelt. Was zählt, sind vier Anteile zwischen 0 und 1 – so
       ist der Ausschnitt unabhängig davon, wie groß das Bild gerade dargestellt wird. Der
       Server legt daraus eine NEUE Datei an und lässt das Ausgangsbild liegen: Ein Zuschnitt
       lässt sich damit zurücknehmen, und ein Bild, das an zwei Stellen steht, verliert nicht
       an beiden seine Ränder. */
    let cropZu = null;
    const cropSchliessen = () => { if (cropZu) cropZu(); };
    const cropStart = (img) => {
      cropSchliessen();                              // nie zwei Rahmen gleichzeitig
      hideCtx();
      // Ein Bild, das noch lädt, hat noch keine Maße – darüber ließe sich kein Rahmen legen.
      // Dann wartet er auf das erste Bild, statt wortlos nicht zu erscheinen.
      if (!img.getBoundingClientRect().width) {
        if (img.isConnected) img.addEventListener("load", () => cropStart(img), { once: true });
        return;
      }
      const huelle = document.createElement("div");
      huelle.className = "ed-crop";
      const rahmen = document.createElement("div");
      rahmen.className = "ed-crop-rahmen";
      ["lo", "ro", "lu", "ru"].forEach((ecke) => {
        const e = document.createElement("div");
        e.className = "ed-crop-ecke ecke-" + ecke;
        e.dataset.ecke = ecke;
        rahmen.appendChild(e);
      });
      const leiste = document.createElement("div");
      leiste.className = "ed-crop-leiste";
      leiste.innerHTML = `<span class="hinweis">Rahmen ziehen, dann übernehmen</span>
        <button type="button" class="btn secondary" data-crop="weg">Abbrechen</button>
        <button type="button" class="btn" data-crop="ok">Zuschneiden</button>`;
      huelle.appendChild(rahmen);
      document.body.appendChild(huelle);
      document.body.appendChild(leiste);

      // Anteile des Ausschnitts am Bild – Anfang ist das ganze Bild.
      let a = { x: 0, y: 0, b: 1, h: 1 };
      const MIN = 0.05;                              // kleiner als ein Zwanzigstel wird nichts
      const klemm = (v, min, max) => Math.max(min, Math.min(max, v));

      const stelle = () => {
        const r = img.getBoundingClientRect();
        // Ist das Bild aus dem Text verschwunden, hat der Rahmen nichts mehr zu umfassen.
        // Eine vorübergehende Größe null (etwa während der Editor neu aufbaut) reicht nicht.
        if (!img.isConnected) return cropWeg();
        if (!r.width || !r.height) return;
        huelle.style.left = `${window.scrollX + r.left}px`;
        huelle.style.top = `${window.scrollY + r.top}px`;
        huelle.style.width = `${r.width}px`;
        huelle.style.height = `${r.height}px`;
        rahmen.style.left = `${a.x * r.width}px`;
        rahmen.style.top = `${a.y * r.height}px`;
        rahmen.style.width = `${a.b * r.width}px`;
        rahmen.style.height = `${a.h * r.height}px`;
        leiste.style.left = `${window.scrollX + Math.max(8, r.left)}px`;
        leiste.style.top = `${window.scrollY + r.bottom + 8}px`;
      };

      // Ziehen: an einer Ecke wandert die Ecke, sonst der ganze Rahmen.
      const ziehen = (ev) => {
        if (ev.button != null && ev.button !== 0) return;
        const ecke = ev.target.dataset ? ev.target.dataset.ecke : null;
        if (!ecke && ev.target !== rahmen) return;
        ev.preventDefault();
        const r = img.getBoundingClientRect();
        const start = { mx: ev.clientX, my: ev.clientY, ...a };
        const bewegt = (e2) => {
          const dx = (e2.clientX - start.mx) / r.width;
          const dy = (e2.clientY - start.my) / r.height;
          if (!ecke) {
            a.x = klemm(start.x + dx, 0, 1 - start.b);
            a.y = klemm(start.y + dy, 0, 1 - start.h);
          } else {
            const links = ecke === "lo" || ecke === "lu";
            const oben = ecke === "lo" || ecke === "ro";
            if (links) {
              const x = klemm(start.x + dx, 0, start.x + start.b - MIN);
              a.b = start.x + start.b - x; a.x = x;
            } else {
              a.b = klemm(start.b + dx, MIN, 1 - start.x);
            }
            if (oben) {
              const y = klemm(start.y + dy, 0, start.y + start.h - MIN);
              a.h = start.y + start.h - y; a.y = y;
            } else {
              a.h = klemm(start.h + dy, MIN, 1 - start.y);
            }
          }
          stelle();
        };
        const fertig = () => {
          document.removeEventListener("pointermove", bewegt);
          document.removeEventListener("pointerup", fertig);
        };
        document.addEventListener("pointermove", bewegt);
        document.addEventListener("pointerup", fertig);
      };
      rahmen.addEventListener("pointerdown", ziehen);

      const taste = (e) => {
        if (e.key === "Escape") { e.preventDefault(); cropWeg(); }
        else if (e.key === "Enter") { e.preventDefault(); uebernehmen(); }
      };
      function cropWeg() {
        huelle.remove(); leiste.remove();
        window.removeEventListener("scroll", stelle, true);
        window.removeEventListener("resize", stelle);
        document.removeEventListener("keydown", taste, true);
        cropZu = null;
      }
      const uebernehmen = async () => {
        if (a.x <= 0.001 && a.y <= 0.001 && a.b >= 0.999 && a.h >= 0.999) return cropWeg();
        const quelle = (img.getAttribute("src") || "").replace(/#.*$/, "");
        const knopf = leiste.querySelector("[data-crop=ok]");
        knopf.disabled = true; knopf.textContent = "Schneidet …";
        try {
          const d = await api("/api/wiki/files/zuschnitt",
            { method: "POST", body: { file: quelle, x: a.x, y: a.y, w: a.b, h: a.h } });
          cropWeg();
          rewriteImage(img, (o) => imgMd(o.alt, d.url, o.width));
        } catch (e) {
          knopf.disabled = false; knopf.textContent = "Zuschneiden";
          toast(e.message || "Das Bild ließ sich nicht zuschneiden.", true);
        }
      };
      leiste.querySelector("[data-crop=weg]").onclick = cropWeg;
      leiste.querySelector("[data-crop=ok]").onclick = uebernehmen;
      window.addEventListener("scroll", stelle, true);
      window.addEventListener("resize", stelle);
      document.addEventListener("keydown", taste, true);
      cropZu = cropWeg;
      stelle();
    };

    /* Bild drehen. Wie beim Zuschneiden macht das der Server und legt eine neue Datei an; der
       Text bekommt nur die neue Adresse. Solange die Antwort unterwegs ist, steht das Bild
       schon gekippt da – bei einem großen Bild dauert das sonst spürbar lange, ohne dass sich
       etwas rührt. Schlägt es fehl, wird die Vorschau zurückgenommen. */
    const drehen = async (img, grad) => {
      if (img.dataset.dreht) return;
      const quelle = (img.getAttribute("src") || "").replace(/#.*$/, "");
      img.dataset.dreht = "1";
      const vorher = img.style.transform;
      img.style.transform = `rotate(${grad === 90 ? 90 : -90}deg)`;
      hideCtx();
      try {
        const d = await api("/api/wiki/files/drehung", { method: "POST", body: { file: quelle, grad } });
        img.style.transform = vorher;
        delete img.dataset.dreht;
        rewriteImage(img, (o) => imgMd(o.alt, d.url, o.width));
      } catch (e) {
        img.style.transform = vorher;
        delete img.dataset.dreht;
        toast(e.message || "Das Bild ließ sich nicht drehen.", true);
      }
    };

    const imageMenu = (img) => {
      img.classList.add("ed-selected");
      strichHinterBild(img);
      const cur = MD.imageWidth(img.getAttribute("src")) || "";
      const html = `<span class="lbl" title="Bildbreite">${I.breite}</span>${["25%", "50%", "75%", "100%"].map((w) =>
          btn("data-w", w, `Breite ${parseInt(w, 10)} % der Textbreite`, parseInt(w, 10), "num" + (cur === w ? " on" : ""))).join("")}${
          btn("data-w", "", "Originalgröße", I.original, cur ? "" : "on")}${btn("data-act", "exact", "Breite genau angeben", "…", "num")}<span class="sep"></span>
        ${btn("data-al", "left", "Bild links", I.linksb)}${btn("data-al", "center", "Bild mittig", I.mittig)}${btn("data-al", "right", "Bild rechts", I.rechtsb)}<span class="sep"></span>
        ${btn("data-act", "alt", "Alternativtext", "ALT", "abbr")}<span class="sep"></span>
        ${btn("data-act", "rotl", "Nach links drehen", I.drehLinks)}${btn("data-act", "rotr", "Nach rechts drehen", I.drehRechts)}${btn("data-act", "crop", "Bild zuschneiden", I.zuschneiden)}${btn("data-act", "dup", "Bild duplizieren", I.duplizieren)}${btn("data-act", "replace", "Bild ersetzen", I.ersetzen)}${btn("data-act", "download", "Original öffnen", I.herunter)}<span class="sep"></span>
        ${btn("data-act", "del", "Bild löschen", I.papierkorb, "danger")}`;
      placeCtx(img, html, (box) => {
        box.querySelectorAll("[data-w]").forEach((x) => x.onclick = () => rewriteImage(img, (o) => imgMd(o.alt, o.url, x.dataset.w)));
        box.querySelectorAll("[data-al]").forEach((x) => x.onclick = () => {
          // Steht das Bild schon in einem Ausrichtungsabschnitt, wird dessen Richtung geändert –
          // sonst schachtelte jeder Klick einen weiteren Abschnitt darum.
          const top = topElFor(img);
          const auf = umgebenderAbschnitt(top);
          if (auf && auf.querySelector(".sek-ausrichtung")) {
            const index = blockRoots().indexOf(auf);
            if (index >= 0) return rewriteBloecke([{ index, text: `$$ausrichtung\n${x.dataset.al}\n$$` }]);
          }
          /* Eine Bildunterschrift gehört zum Bild: Im Artikel werden Bild und kursiver Absatz
             darunter zu einer Abbildung zusammengefasst. Bliebe die Unterschrift außerhalb des
             Ausrichtungsabschnitts, stünde sie im Artikel als gewöhnlicher Absatz da – die
             Abbildung wäre auseinandergerissen. Deshalb wandert sie mit. */
          // Nachbarschaft über blockEls, nicht über nextElementSibling: Zwischen zwei Blöcken
          // steht im Editor eine Fuge (ein leerer Absatz zum Anklicken), die kein Block ist.
          const els = blockEls();
          const i = top ? els.indexOf(top) : -1;
          const unten = i >= 0 ? els[i + 1] : null;
          if (unten && unten.classList.contains("ed-unterschrift")) {
            const md = ed.getMarkdown();
            const { lines, blocks } = topLevelBlocks(md);
            if (blocks.length === els.length && blocks[i] && blocks[i + 1]) {
              const erg = EDMD.ausrichten(md, { markeZeile: blocks[i].start, endeZeile: blocks[i + 1].start,
                                                amBlockanfang: false, mode: x.dataset.al });
              if (erg.md !== undefined) {
                setMd(erg.md);
                state.dirty = true;
                hideCtx();
                return;
              }
            }
          }
          rewriteImage(img, (o) => `\n$$ausrichtung\n${x.dataset.al}\n$$\n\n${imgMd(o.alt, o.url, o.width)}\n\n$$ende\n$$\n`);
        });
        box.querySelector("[data-act=alt]").onclick = () => {
          const cur = img.getAttribute("alt") || "";
          hideCtx();
          dialog(`<h2>Bildbeschreibung</h2>
            <p class="help">Der Alternativtext wird vorgelesen, wenn das Bild nicht angezeigt werden kann.</p>
            <label for="alt-text">Alternativtext</label><input type="text" id="alt-text" value="${esc(cur)}">
            <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
            <button class="btn" id="alt-ok" type="button">Übernehmen</button></div>`,
            (dlg, body) => { body.querySelector("#alt-ok").onclick = () => {
              const a = body.querySelector("#alt-text").value;
              dlg.close();
              rewriteImage(img, (o) => imgMd(a, o.url, o.width));
            }; });
        };
        box.querySelector("[data-act=exact]").onclick = () => {
          const cur = MD.imageWidth(img.getAttribute("src")) || "";
          hideCtx();
          dialog(`<h2>Bildbreite</h2>
            <p class="help">Prozent der Textbreite (z. B. <code>60%</code>) oder Bildpunkte (z. B. <code>420</code>).</p>
            <label for="iw-val">Breite</label><input type="text" id="iw-val" value="${esc(cur)}" placeholder="60% oder 420">
            <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button>
            <button class="btn" id="iw-ok" type="button">Übernehmen</button></div>`,
            (dlg, body) => { body.querySelector("#iw-ok").onclick = () => {
              const raw = body.querySelector("#iw-val").value.trim().replace(",", ".");
              const m = /^(\d{1,4})\s*(%|px)?$/.exec(raw);
              if (raw && !m) return toast("Bitte eine Zahl angeben, wahlweise mit % dahinter.", true);
              dlg.close();
              const w = !raw ? "" : (m[2] === "%" ? m[1] + "%" : m[1]);
              rewriteImage(img, (o) => imgMd(o.alt, o.url, w));
            }; });
        };
        box.querySelectorAll("[data-act=rotl], [data-act=rotr]").forEach((x) => x.onclick = () => drehen(img, x.dataset.act === "rotr" ? 90 : 270));
        box.querySelector("[data-act=crop]").onclick = () => cropStart(img);
        box.querySelector("[data-act=dup]").onclick = () => rewriteImage(img, (o) => imgMd(o.alt, o.url, o.width) + "\n\n" + imgMd(o.alt, o.url, o.width));
        box.querySelector("[data-act=replace]").onclick = () => pickImage((url) => rewriteImage(img, (o) => imgMd(o.alt, url, o.width)));
        box.querySelector("[data-act=download]").onclick = () => window.open(img.getAttribute("src").replace(/#w=.*$/, ""), "_blank", "noopener");
        box.querySelector("[data-act=del]").onclick = () => rewriteImage(img, () => null);
      }, "Bild");
      // Griff zum Skalieren am rechten Rand
      const r = img.getBoundingClientRect();
      frame.classList.remove("hidden"); handle.classList.remove("hidden");
      frame.style.left = `${window.scrollX + r.left}px`; frame.style.top = `${window.scrollY + r.top}px`; frame.style.width = `${r.width}px`; frame.style.height = `${r.height}px`;
      handle.style.left = `${window.scrollX + r.right - 7}px`; handle.style.top = `${window.scrollY + r.top + r.height / 2 - 22}px`;
      handle.onmousedown = handle.ontouchstart = (e) => {
        e.preventDefault();
        // Bezugsgröße ist der Textbereich, in dem das Bild steht – genau darauf bezieht der
        // Browser später width="…%". Die Breite des Editors wäre größer, dadurch käme jedes Mal
        // ein zu kleiner Prozentwert heraus und das Bild schrumpfte bei jedem Anfassen.
        // Der Wrapper <span class="image-link"> verlinkter Bilder ist inline und hätte
        // clientWidth 0 – deshalb den nächsten Block-Vorfahren suchen.
        let host = img.parentElement;
        while (host && host !== pm() && /^inline/.test(getComputedStyle(host).display)) host = host.parentElement;
        host = host || pm();
        const cs = getComputedStyle(host);
        const bezug = Math.max(1, host.clientWidth
          - parseFloat(cs.paddingLeft || 0) - parseFloat(cs.paddingRight || 0));
        // Ausgangsbreite erst jetzt messen: zwischen Menüaufbau und Anfassen kann sich das
        // Bild verschoben oder neu aufgebaut haben.
        const jetzt = img.getBoundingClientRect();
        const startX = (e.touches ? e.touches[0] : e).clientX;
        const startW = jetzt.width;
        let w = startW;
        const move = (ev) => {
          const x = (ev.touches ? ev.touches[0] : ev).clientX;
          if (Math.abs(x - startX) > 2) bewegt = true;
          w = Math.max(40, Math.min(bezug, startW + (x - startX)));
          frame.style.width = `${w}px`;
          handle.style.left = `${window.scrollX + jetzt.left + w - 7}px`;
          img.style.width = `${w}px`;
        };
        let bewegt = false;
        const up = () => {
          document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up);
          document.removeEventListener("touchmove", move); document.removeEventListener("touchend", up);
          if (!bewegt) return;                       // bloßes Anfassen ändert nichts
          const pct = Math.max(5, Math.min(100, Math.round((w / bezug) * 100)));
          rewriteImage(img, (o) => imgMd(o.alt, o.url, pct >= 98 ? "100%" : `${pct}%`));
        };
        document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
        document.addEventListener("touchmove", move, { passive: false }); document.addEventListener("touchend", up);
      };
    };

    root.addEventListener("click", (e) => {
      if (!ed.isWysiwygMode()) return hideCtx();
      const el = pm(); if (!el || !el.contains(e.target)) return hideCtx();
      /* Zieht man über mehrere Zellen, endet der Klick auf der Zeile oder der Tabelle, nicht auf
         einer Zelle – "closest(td, th)" ginge leer aus und das Tabellenmenü bliebe zu. Ein
         weiterer Klick auf eine Zelle würde die Auswahl wieder auflösen, und das Verbinden wäre
         dann nicht mehr erreichbar. Steht also eine Zellauswahl, gilt der Klick ihr. Das muss vor
         die Prüfung auf Textauswahl: Zu einer Zellauswahl gehört im Browser auch eine
         Textauswahl über dieselben Zellen. */
      const gewaehlt = el.querySelector("td.toastui-editor-cell-selected, th.toastui-editor-cell-selected");
      if (gewaehlt) { hideCtx(); ctxTarget = gewaehlt; return tableMenu(gewaehlt); }
      // Ein Klick ohne Zellauswahl heißt: Der Zug von vorhin ist erledigt. Was danach kommt,
      // meint ihn nicht mehr.
      zellBereich = null;
      // Nach dem Ziehen einer Textauswahl feuert ebenfalls ein Klick – der darf das
      // Blockmenü nicht über die gerade erschienene Textleiste legen.
      const sel = document.getSelection();
      if (sel && !sel.isCollapsed && sel.rangeCount && el.contains(sel.anchorNode) && String(sel).trim()) return hideCtx();
      hideCtx();
      const img = e.target.closest("img");
      // Nur Artikelbilder bekommen ein Menü: Ein Klick auf das Profilbild in der Autorenzeile
      // soll keine Bildleiste aufziehen, deren Knöpfe auf nichts im Text zeigen.
      if (img && MD.istInhaltsbild(img)) { ctxTarget = img; return imageMenu(img); }
      // Links vor Tabelle und Block prüfen: sonst wäre ein Link in einer Zelle nicht erreichbar.
      const link = e.target.closest("a[href]");
      if (link) { ctxTarget = link; return linkMenu(link); }
      const cell = e.target.closest("td, th");
      if (cell && cell.closest("table")) { ctxTarget = cell; return tableMenu(cell); }
      const block = e.target.closest(BLOCK_SEL);
      if (block) { const roots = blockRoots(); const rootEl = roots.find((r) => r === block || r.contains(block)); if (rootEl) { ctxTarget = rootEl; return blockMenu(rootEl); } }
      // Ein Klick mitten in eine Hinweiskiste oder einen Spaltenabschnitt meint den Abschnitt –
      // sonst käme man an sein Menü nur über die schmale Marke.
      const auf = umgebenderAbschnitt(topElFor(e.target));
      if (auf) { ctxTarget = auf; return blockMenu(auf); }
    });
    const onEscape = (e) => { if (e.key === "Escape") hideCtx(); };
    document.addEventListener("keydown", onEscape);

    /* Entfernen und Rücktaste lassen Tabellen, Hinweiskisten, Spalten- und Ausrichtungs-
       abschnitte stehen (siehe editor-layout.js). Ohne Rückmeldung sähe die wirkungslose
       Taste nach einem Fehler aus. Gedrückt gehaltene Taste soll aber nicht dauernd melden. */
    let schutzZuletzt = 0;
    const SCHUTZ_NAME = { tabelle: "Die Tabelle", ausrichtung: "Der Ausrichtungsblock",
                          hinweis: "Die Hinweiskiste", akkordeon: "Die einklappbare Box",
                          spalten: "Der Spaltenabschnitt" };
    const onSchutz = (e) => {
      const jetzt = Date.now();
      if (jetzt - schutzZuletzt < 2500) return;
      schutzZuletzt = jetzt;
      const was = SCHUTZ_NAME[e.detail && e.detail.art] || "Der Abschnitt";
      toast(`${was} lässt sich nicht mit der Taste löschen. Klicke hinein – im Menü steht `
            + "der Knopf dafür.");
    };
    document.addEventListener("edlayout:geschuetzt", onSchutz);

    /* ProseMirror baut Bildknoten bei jeder Änderung neu auf und verliert dabei die Breite,
       die nur in der Adresse steht. Deshalb nach jeder Änderung einmal nachziehen –
       gebündelt im nächsten Bildaufbau, damit schnelles Tippen nichts kostet. */
    let breitenLauf = 0;
    ed.on("change", () => {
      if (breitenLauf) return;
      breitenLauf = requestAnimationFrame(() => { breitenLauf = 0; bildBreitenAnwenden(); });
    });
    bildBreitenAnwenden();

    // Aufräumen, wenn der Editor geschlossen wird – sonst bleibt bei jedem Öffnen ein Zuhörer zurück
    const origDestroy = ed.destroy.bind(ed);
    ed.destroy = () => {
      document.removeEventListener("selectionchange", onSelection);
      document.removeEventListener("keydown", onEscape);
      document.removeEventListener("edlayout:geschuetzt", onSchutz);
      if (breitenLauf) cancelAnimationFrame(breitenLauf);
      if (emojiZu) emojiZu();
      if (farbZu) farbZu();
      cropSchliessen();                              // sonst bliebe der Rahmen über der Seite liegen
      bubble.remove(); menu.remove(); ctx.remove(); frame.remove(); handle.remove();
      origDestroy();
    };
  }

  /* Emoji-Auswahl in Dialogen: liefert eine Funktion, die das gewählte Emoji zurückgibt */
  const emojiPicker = (body, initial) => {
    // Grid aller darstellbaren Unicode-Emojis plus Eingabefeld (dort auch der System-Emoji-Picker: Win+. / Ctrl+Cmd+Leertaste)
    const grid = body.querySelector("#em-grid");
    const input = body.querySelector("#em-input");
    input.value = initial;
    const list = MD.allEmojis();
    grid.innerHTML = list.map((e) => `<button type="button" class="em" data-e="${MD.esc(e)}">${e}</button>`).join("");
    grid.addEventListener("click", (e) => {
      const b = e.target.closest(".em");
      if (!b) return;
      input.value = b.dataset.e;
      grid.querySelectorAll(".em.sel").forEach((x) => x.classList.remove("sel"));
      b.classList.add("sel");
    });
    return () => Array.from(input.value.trim()).slice(0, 4).join("") || initial;
  };

  /* Bild wählen und hochladen; ruft cb(url, alt) */
  /* Datei wählen und hochladen; ruft cb(url, nameOhneEndung, kind, dateiname) */
  function pickFile(accept, cb) {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = accept;
    inp.onchange = async () => {
      const f = inp.files[0]; if (!f) return;
      const status = $("#ed-status");
      const show = (pct) => { if (status) status.textContent = `Lade ${f.name} hoch … ${pct}%`; };
      show(0);
      try {
        const r = await uploadFile(f, show);
        cb(r.url, f.name.replace(/\.[^.]+$/, ""), r.kind, f.name);
      } catch (e) { toast(e.message, true); }
      if (status) status.textContent = "";
    };
    inp.click();
  }

  function pickImage(cb) {
    pickFile("image/*,.heic,.heif", cb);
  }

  function leaveEditor() {
    /* Der Editor schreibt selbstständig. Wer ihn über einen anderen Weg verlässt (Seitenbaum,
       ein Link im Text), soll deshalb nicht gefragt werden – der letzte Stand geht noch los,
       bevor der Editor abgeräumt wird. Die Anwendung wechselt die Seite ohne Neuladen, die
       Anfrage läuft also zu Ende. Nur eine neue, noch nicht angelegte Seite fragt nach. */
    // Zwei Fälle, in denen der Abschluss NICHT speichern kann, und die deshalb fragen müssen:
    // die neue Seite, die noch nirgends steht, und der Konflikt, nach dem nichts mehr
    // angenommen wird. Früher lief beides stumm in den Abschluss – und der Text war weg.
    if (state.editor && state.dirty && (state.editorNeu || state.editorKonflikt) && !state.speichert) {
      const frage = state.editorNeu
        ? "Die neue Seite ist noch nicht angelegt. Eingaben verwerfen?"
        : "Die letzten Änderungen wurden nicht gespeichert (die Seite wurde inzwischen von jemand "
          + "anderem geändert). Trotzdem verlassen? Ein Entwurf bleibt in diesem Browser.";
      if (!window.confirm(frage)) return false;
    } else if (state.editor && state.editorAbschluss && state.dirty) { try { state.editorAbschluss(); } catch (e) { /* egal */ } }
    else if (state.editor && state.dirty && !state.speichert
             && !window.confirm("Ungespeicherte Änderungen verwerfen?")) return false;
    // Was auch immer gerade noch unterwegs ist: der letzte Stand liegt als Entwurf im Browser.
    if (state.editor && state.saveDraft) { try { state.saveDraft(); } catch (e) { /* egal */ } }
    destroyEditor();
    return true;
  }
  function destroyEditor() {
    editorCleanup.forEach((fn) => { try { fn(); } catch (e) { /* egal */ } });
    editorCleanup = [];
    if (state.editor && state.editor.destroy) { try { state.editor.destroy(); } catch (e) { /* egal */ } }
    state.editor = null;
    state.editorSeite = null;
    state.editorNeu = false;
    state.editorKonflikt = false;
    // Zeiger auf den zerstörten Editor löschen: ein Upload, der jetzt noch fertig wird,
    // würde sonst in einen abgeräumten Editor schreiben wollen und stumm verlorengehen.
    state.insertBlock = null;
    state.editorCopyMd = null;
    state.editorSuchen = null;
    state.editorKlartext = null;
    state.dropDraft = null;
    // Ein Speichervorgang, der den Editor überlebt, setzt diese Marke nicht mehr zurück –
    // sonst griffe er in die inzwischen offene Seite. Also hier: ohne Editor speichert niemand.
    state.speichert = false;
    // Der Schreibplatz wird frei, sobald der Editor zu ist – der nächste Herzschlag meldet
    // diesen Reiter wieder als Leser, und andere können sofort bearbeiten.
    state.schreibrecht = false;
    state.editorGesperrt = false;
    if (state.spy) { try { state.spy(); } catch (e) { /* egal */ } state.spy = null; }
    state.dirty = false;
    document.body.classList.remove("editing");
  }
  window.addEventListener("beforeunload", (e) => {
    if (!state.editor || !state.dirty) return;
    // Erst sichern, dann fragen – sonst wäre alles seit der letzten automatischen Sicherung weg.
    if (state.saveDraft) { try { state.saveDraft(); } catch (err) { /* egal */ } }
    e.preventDefault(); e.returnValue = "";
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden" && state.saveDraft) { try { state.saveDraft(); } catch (e) { /* egal */ } }
  });

  function uploadFile(file, onProgress) {
    // XHR statt fetch: nur damit lässt sich der Fortschritt anzeigen.
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append("file", file, file.name || "datei");
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/wiki/files");
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      if (onProgress) {
        xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
      }
      xhr.onload = () => {
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch (e) { /* leer */ }
        if (xhr.status >= 400) reject(new Error(d.error || `Fehler ${xhr.status}`));
        else resolve(d);
      };
      xhr.onerror = () => reject(new Error("Keine Verbindung zum Server."));
      xhr.send(fd);
    });
  }

  let editorCleanup = [];
  const editorCleanupPush = (fn) => editorCleanup.push(fn);

  /* Nach so langer Pause gilt die Bearbeitung als beendet: Was danach kommt, bekommt ein neues
     Kennzeichen und damit eine eigene Fassung. Ohne das schriebe ein Reiter, der tagelang offen
     liegt, alles in eine einzige Fassung – und die Beobachter hörten nach der ersten Nachricht
     nie wieder etwas. Derselbe Abstand wie die Ruhezeit der Benachrichtigung (MELDUNG_RUHE_SEK
     in api_wiki.py): so gehört zu jeder Fassung wieder höchstens eine Nachricht. */
  const SITZUNG_PAUSE_MS = 10 * 60 * 1000;

  /* Kennzeichen einer Bearbeitung. Es hält, solange der Editor offen ist und zügig
     weitergeschrieben wird, und sagt dem Server, welche Speichervorgänge zusammengehören.
     Zufall aus dem Browser, mit Rückfall auf Zeit und Math.random – crypto fehlt nur in sehr
     alten Umgebungen, und ein doppeltes Kennzeichen wäre auch dort harmlos: es müsste dieselbe
     Person, dieselbe Seite und die unmittelbar davorliegende Fassung treffen. */
  function bearbeitungsKennzeichen() {
    try {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {
      return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
    }
  }

  function openEditor(p) {
    if (state.spy) { try { state.spy(); } catch (e) { /* egal */ } state.spy = null; }
    const isNew = !p.id;
    editorCleanup.forEach((fn) => { try { fn(); } catch (e) { /* egal */ } });
    editorCleanup = [];
    destroyEditor();
    /* Alles, was dieser Aufruf an Zeitgebern und Rückrufen hinterlässt, gehört zu genau dieser
       Seite. Ein nachlaufender Rückruf darf aber nicht mehr in den Editor greifen, der inzwischen
       in state.editor steht – das wäre der Editor der nächsten Seite. Deshalb zwei Merkmale:
       "lebt" sagt, ob dieser Aufruf noch der aktuelle ist (das Abräumen setzt es auf false), und
       "meinEditor" ist der eigene Editor, an dem allein gelesen und geschrieben wird. Wer nach dem
       Abräumen noch aufwacht, sieht beides und bricht ab. */
    let lebt = true;
    let meinEditor = null;
    editorCleanup.push(() => { lebt = false; });
    hideFab();
    document.body.classList.add("editing");
    state.editorSeite = isNew ? null : p.id;
    state.editorNeu = !!isNew;
    state.editorKonflikt = false;
    renderRail([]);
    // Kommentare bleiben beim Bearbeiten sichtbar – Anmerkungen liest man am besten,
    // während man den Text überarbeitet. Antworten geht weiterhin.
    if (!isNew && p.id) { state.current = state.current || p; loadComments(); }
    else commentsEl.innerHTML = "";
    const crumbs = isNew ? [] : ancestors(p);
    content.innerHTML = `
      <div class="wiki-head editing-head">
        <button class="btn ghost small kopfknopf baum-knopf" id="pg-baum" type="button" title="Seiten" aria-label="Seitenbaum öffnen">☰</button>
        ${krumenPfad(crumbs, p, isNew)}
        <div class="btn-row">
          <span class="muted small" id="ed-status"></span>
          ${isNew ? "" : `<div class="mode-toggle" role="group" aria-label="Ansicht wechseln">
            <button type="button" class="on" data-mode="bearbeiten" aria-pressed="true">Bearbeiten</button>
            <button type="button" id="ed-read" data-mode="lesen" aria-pressed="false">Lesen</button>
          </div>`}
          ${isNew ? '<button class="btn ghost small" id="ed-cancel">Verwerfen</button>'
                  + '<button class="btn small" id="ed-save">Anlegen</button>' : ""}
          <button class="btn ghost small kopfknopf" id="ed-more" type="button" title="Weitere Werkzeuge" aria-label="Weitere Werkzeuge">⋯</button>
          ${tocKnopf()}
        </div>
      </div>
      <div class="wiki-editor">
        <div id="editor"></div>
        <textarea id="ed-fallback" class="plain hidden"></textarea>
      </div>`;
    wireLinks(content);          // die Brotkrumen im Editorkopf bleiben Anwendungslinks
    // Die erste Überschrift IST der Seitentitel – wie in Docmost. Fehlt sie, wird sie ergänzt.
    const titelZeile = (md) => {
      const m = /^[ \t]*#[ \t]+(.+?)[ \t]*#*[ \t]*$/.exec((md || "").split("\n")[0] || "");
      if (!m) return null;
      // Der Seitentitel ist reiner Text – Auszeichnungen der Überschrift gehören nicht hinein.
      const roh = m[1].trim()
        .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
        .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
        .replace(/`([^`]*)`/g, "$1")
        .replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, "$1$2")
        .replace(/\*([^*]+)\*|_([^_]+)_/g, "$1$2")
        .replace(/~~([^~]+)~~|\+\+([^+]+)\+\+|==([^=]+)==/g, "$1$2$3");
      return roh.trim() || null;
    };
    const mitTitel = (md, titel) => {
      const roh = (md || "").replace(/^\n+/, "");
      return titelZeile(roh) ? roh : `# ${titel || "Neue Seite"}\n\n${roh}`;
    };
    const initial = mitTitel(toEditorMd(p.content || ""), p.title);

    if (window.toastui && toastui.Editor) {
      // Blöcke werden im Markdown hinter dem Block eingesetzt, in dem der Cursor steht.
      // Der frühere Weg über einen kurzen Wechsel in den Markdown-Modus setzte sie ans
      // Dokumentende, weil dessen Cursor nicht mitläuft – deshalb "kam nichts an".
      const insert = (text) => {
        // Ein Upload überlebt den Seitenwechsel – sein Ergebnis darf dann nicht im Editor der
        // NÄCHSTEN Seite landen und dort gespeichert werden.
        if (!lebt || state.editor !== meinEditor) {
          toast("Die Datei ist hochgeladen, aber dieser Editor ist inzwischen zu – bitte auf der Seite erneut einfügen.", true);
          return;
        }
        if (state.insertBlock) state.insertBlock(text);
        state.dirty = true;
      };
      const calloutMenu = () => {
        const kinds = ["info", "tip", "warning", "success", "danger", "note"];
        let kind = "info";
        dialog(`<h2>Callout einfügen</h2>
          <div class="callout-pick" id="ck">${kinds.map((k) => `<button type="button" class="btn ${k === kind ? "" : "secondary"}" data-k="${k}">${MD.CALLOUTS[k]} ${k}</button>`).join("")}</div>
          <label for="em-input">Emoji oben links</label>
          <div class="em-row"><input type="text" id="em-input" maxlength="8" autocomplete="off"><span class="help">Beliebiges Emoji eintippen oder unten wählen</span></div>
          <div class="em-grid" id="em-grid"></div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button><button class="btn" id="ck-ok" type="button">Einfügen</button></div>`,
          (dlg, body) => {
            dlg.classList.add("wide");
            dlg.addEventListener("close", () => dlg.classList.remove("wide"), { once: true });
            const getEmoji = emojiPicker(body, MD.CALLOUTS[kind]);
            body.querySelectorAll("#ck [data-k]").forEach((b) => b.onclick = () => {
              kind = b.dataset.k;
              body.querySelectorAll("#ck .btn").forEach((x) => x.classList.toggle("secondary", x !== b));
              body.querySelector("#em-input").value = MD.CALLOUTS[kind];
            });
            body.querySelector("#ck-ok").onclick = () => {
              const emoji = getEmoji();
              // Ist Text markiert, wird er der Rumpf – sonst löschte das Einfügen ihn.
              const markiert = (() => { try { return (state.editor.getSelectedText() || "").trim(); } catch (e) { return ""; } })();
              dlg.close();
              const inner = markiert || (kind === "note"
                ? "### Hinweise\n\n- Die Erprobung steht noch aus." : "**Titel**\n\nText");
              insert(hinweisMd(kind, emoji, inner));
            };
          });
      };
      const columnsMenu = () => {
        dialog(`<h2>Spalten einfügen</h2><p class="help">Die Spalten stehen im Editor wie im Artikel nebeneinander; Anfang, Trenner und Ende sind schmale Marken. Auf schmalen Bildschirmen stehen sie untereinander.</p>
          <div class="callout-pick">${[2, 3, 4, 5].map((n) => `<button type="button" class="btn secondary" data-n="${n}">${n} Spalten</button>`).join("")}</div>
          <div class="dlg-actions"><button class="btn secondary" data-close type="button">Abbrechen</button></div>`,
          (dlg, body) => body.querySelectorAll("[data-n]").forEach((b) => b.onclick = () => {
            dlg.close();
            const n = +b.dataset.n;
            insert("$$spalten\n$$\n\n" + Array.from({ length: n }, (_, i) => `Spalte ${i + 1}`).join("\n\n$$spalte\n$$\n\n") + "\n\n$$ende\n$$\n");
          }));
      };
      /* Die Autorzeile steht im Editor an derselben Stelle wie in der Ansicht: direkt unter
         der Überschrift. Weil die Überschrift hier der erste Block des Dokuments ist, geht das
         nur als Widget-Dekoration – ein Stück DOM, das ProseMirror an einer Position einhängt,
         ohne dass es zum Dokument gehört. Es ist damit weder auswählbar noch speicherbar.
         Wichtig: blockEls() muss es überspringen, sonst verschöben sich alle Blocknummern. */
      /* bau muss dieselbe Funktion bleiben: ProseMirror vergleicht Widgets über die Gleichheit
         von toDOM. Eine bei jedem Aufruf neu erzeugte Funktion gälte als immer verändert und
         würde die Autorzeile bei jedem Tastendruck neu aufbauen. */
      const autorBau = () => {
        const el = document.createElement("div");
        el.className = "autorzeile ed-nichtinhalt";
        el.contentEditable = "false";
        el.innerHTML = autorZeile(p).replace(/^<div class="autorzeile">|<\/div>$/g, "");
        el.addEventListener("mousedown", (e) => e.preventDefault());
        const knopf = el.querySelector("#pg-info");
        if (knopf) { knopf.removeAttribute("id"); knopf.onclick = () => seitenInfo(p, knopf); }
        const autorKnopf = el.querySelector(".autor-knopf");
        if (autorKnopf && p.id) autorKnopf.onclick = () => autorTafel(p, autorKnopf);
        return el;
      };
      const autorWidget = ({ pmState, pmView }) => ({
        wysiwygPlugins: [() => new pmState.Plugin({
          props: {
            decorations(zustand) {
              const doc = zustand.doc;
              if (!doc.childCount || doc.child(0).type.name !== "heading") return null;
              return pmView.DecorationSet.create(doc, [pmView.Decoration.widget(doc.child(0).nodeSize, autorBau, { side: -1 })]);
            },
          },
        })],
      });

      /* Toast UI baut im WYSIWYG für jeden Bildknoten ein <img> – auch für ![](film.mp4).
         Das ergab ein kaputtes Bild statt eines Abspielers, und weil das <img> mitgezählt
         wurde, traf das Bildmenü nach einer Tonaufnahme die falsche Fundstelle. Eine eigene
         NodeView macht daraus <video> bzw. <audio>; gewöhnliche Bilder bleiben <img>. */
      const medienNodeView = () => ({
        wysiwygNodeViews: {
          image: (node) => {
            const url = String(node.attrs.imageUrl || "");
            const film = VIDEO_RE.test(url), ton = AUDIO_RE.test(url);
            const el = document.createElement(film ? "video" : ton ? "audio" : "img");
            el.setAttribute("src", url);
            if (film || ton) { el.setAttribute("controls", "true"); el.setAttribute("preload", "metadata"); }
            else {
              el.setAttribute("alt", node.attrs.altText || "");
              const w = MD.imageWidth(url);
              if (w) { el.style.width = /%$/.test(w) ? w : `${w}px`; el.style.height = "auto"; }
            }
            return { dom: el, ignoreMutation: () => true };
          },
        },
      });

      const editorOptions = {
        el: $("#editor"),
        // EDVERLAUF.plugin trägt nichts zum Dokument bei: Es gibt die ProseMirror-Sicht schon
        // während des Aufbaus heraus, damit auch der aus dem Rückgängig-Verlauf bleibt.
        /* Die Erweiterung für zusammengefasste Zellen kommt vom Hersteller (siehe Dockerfile).
           Sie bringt die Befehle mergeCells/splitCells mit und liest und schreibt die
           Schreibweise "@cols=2:"/"@rows=2:" im Markdown. Fehlt sie – etwa weil die Datei
           nicht geladen wurde –, läuft der Editor ohne sie weiter; verbundene Zellen wären
           dann nur nicht mehr verbindbar. */
        plugins: [autorWidget, layoutPlugin, medienNodeView, EDVERLAUF.plugin, zellenAuswahl,
                  ...(toastui.Editor.plugin && toastui.Editor.plugin.tableMergedCell
                      ? [toastui.Editor.plugin.tableMergedCell] : [])],
        initialEditType: "wysiwyg",
        hideModeSwitch: true,        // es gibt nur noch die WYSIWYG-Ansicht
        height: "auto",
        minHeight: "480px",
        initialValue: "",            // erst nach der Konverter-Reparatur unten gesetzt
        // Ohne dies setzt Toast UI den Cursor beim Öffnen ans Ende des Textes; der Browser
        // scrollt ihm hinterher und man landet unten statt an der gelesenen Stelle.
        autofocus: false,
        language: "de-DE",
        usageStatistics: false,
        placeholder: isNew
          ? (p.parent_id
            ? "Worum geht es auf dieser Unterseite? Leitabsatz, dann Aufbau und Typische Fehler …"
            : "Leitabsatz, Voraussetzungen, Aufbau, Typische Fehler, Quellen …")
          : "Text bearbeiten – „/“ öffnet das Einfügemenü.",
        customHTMLRenderer,
        // ++unterstrichen++, ==hervorgehoben==, ^hoch^ und ~tief~ als Widgets: der Editor zeigt sie
        // ausgezeichnet an und gibt den Quelltext unverändert zurück (siehe markdown.js).
        widgetRules: MD.widgetRules(),
        hooks: {
          addImageBlobHook: async (blob, callback) => {
            try {
              const file = blob instanceof File ? blob : new File([blob], "bild.png", { type: blob.type });
              const r = await uploadFile(file);
              callback(r.url, r.kind === "video" ? "Video" : (file.name || "Bild"));
            } catch (e) { toast(e.message, true); }
          },
        },
        toolbarItems: [],
      };
      /* Aufbauen und füllen in einem Zug innerhalb von EDVERLAUF.oeffnen: Sonst landen beide
         Schritte im Rückgängig-Verlauf – ein Strg+Z direkt nach dem Öffnen leerte den Artikel,
         und die Autospeicherung schrieb den leeren Stand zur Seite (siehe editor-verlauf.js).
         Der Konverter muss dazwischen repariert sein, bevor Markdown umgewandelt wird; deshalb
         ist initialValue leer und der Text kommt erst hier. */
      const bauen = () => EDVERLAUF.oeffnen(() => {
        const ed = new toastui.Editor(editorOptions);
        zellenKonverterReparieren(ed);
        try { ed.setMarkdown(initial, false); } catch (e) { /* bleibt leer */ }
        return ed;
      });
      try { state.editor = bauen(); }
      catch (e) { delete editorOptions.language; state.editor = bauen(); }
      meinEditor = state.editor;
      meinEditor.on("change", () => { state.dirty = true; });
      // Das Inhaltsverzeichnis steht auch beim Bearbeiten rechts – gebündelt nachgezogen,
      // damit schnelles Tippen nichts kostet.
      let tocLauf = 0;
      meinEditor.on("change", () => {
        if (tocLauf) return;
        tocLauf = setTimeout(() => { tocLauf = 0; if (lebt) renderEditorRail(); }, 400);
      });
      editorCleanup.push(() => { if (tocLauf) clearTimeout(tocLauf); });
      setTimeout(() => { if (lebt) renderEditorRail(); }, 0);
      setupInlineTools(insert, calloutMenu, columnsMenu);
      // Zurück an die Stelle, an der gerade gelesen wurde (siehe modusScrollMerken).
      modusScrollAnwenden();

      // "Als Markdown kopieren" ist über das Seitenmenü erreichbar, Suchen und Ersetzen
      // über Strg+Umschalt+F – der Editorkopf bleibt frei.
      state.editorCopyMd = async () => {
        try {
          await navigator.clipboard.writeText(fromEditorMd(meinEditor.getMarkdown()));
          toast("Artikel als Markdown kopiert");
        } catch (e) { toast("Kopieren war nicht möglich.", true); }
      };
    } else {
      const ta = $("#ed-fallback");
      ta.classList.remove("hidden"); ta.value = p.content || "";
      ta.addEventListener("input", () => { state.dirty = true; });
      state.editor = { getMarkdown: () => ta.value, destroy: null };
      meinEditor = state.editor;
      toast("Die Editor-Bibliothek ließ sich nicht laden – der Text steht als Markdown in einem einfachen Textfeld.", true);
    }


    /* Entwurf im Browser sichern: nach einem Absturz oder versehentlichem Schließen
       ist die Arbeit nicht weg. Der Entwurf verschwindet beim Speichern. */
    const draftKey = p.id ? `stroemis-entwurf-${p.id}` : `stroemis-entwurf-neu-${p.parent_id || 0}`;
    const readDraft = () => { try { return JSON.parse(localStorage.getItem(draftKey) || "null"); } catch (e) { return null; } };
    const dropDraft = () => { try { localStorage.removeItem(draftKey); } catch (e) { /* egal */ } };
    const saveDraft = () => {
      // draftKey gehört zu dieser Seite: schreibt hier ein nachlaufender Takt den Text aus
      // state.editor hinein, liegt unter dieser Seite der Entwurf einer anderen.
      if (!lebt || state.editor !== meinEditor || !state.dirty) return;
      try {
        localStorage.setItem(draftKey, JSON.stringify({
          md: meinEditor.getMarkdown(), at: new Date().toISOString(), version: p.version ?? null,
        }));
        const st = $("#ed-status");
        if (st && !st.textContent) {
          st.textContent = "Entwurf gesichert";
          setTimeout(() => { if (st.textContent === "Entwurf gesichert") st.textContent = ""; }, 1800);
        }
      } catch (e) { /* voller Speicher: dann eben nicht */ }
    };
    if (state.autosave) clearInterval(state.autosave);
    const entwurfsTakt = setInterval(saveDraft, 20000);
    state.autosave = entwurfsTakt;

    const draft = readDraft();
    // Ein Entwurf trägt die Fassung, auf der er beruht. Liegt die Seite inzwischen in einer
    // neueren vor, darf er nicht still übernommen werden – er überschriebe, was jemand anders
    // seither geschrieben hat, und die Uhrzeit allein sieht das nicht (der Entwurfstakt läuft
    // nach einem Konflikt weiter und ist damit jünger als die fremde Änderung).
    const veraltet = !!(draft && draft.version != null && p.version != null && draft.version < p.version);
    if (draft && !veraltet && draft.at && p.updated_at && Date.parse(draft.at) < Date.parse(p.updated_at)) {
      // Zwischenzeitlich hat jemand (womöglich man selbst in einem anderen Reiter) gespeichert.
      dropDraft();
    } else if (draft && draft.md && draft.md !== initial) {
      const when = fmtDate(draft.at, true);
      toast(`Es liegt ein Entwurf von ${when} vor.`);
      const bar = document.createElement("div");
      bar.className = "notice";
      bar.innerHTML = veraltet
        ? `Entwurf von ${esc(when)} gefunden – er beruht auf einer älteren Fassung, seither hat jemand
           anderes gespeichert. Er wird nicht von selbst übernommen.
        <div class="btn-row" style="margin-top:8px">
          <button class="btn secondary small" id="dr-drop" type="button">Verwerfen</button>
          <button class="btn small" id="dr-show" type="button">Entwurf anzeigen</button>
        </div>`
        : `Ungespeicherter Entwurf von ${esc(when)} gefunden.
        <div class="btn-row" style="margin-top:8px">
          <button class="btn secondary small" id="dr-drop" type="button">Verwerfen</button>
          <button class="btn small" id="dr-use" type="button">Entwurf übernehmen</button>
        </div>`;
      $(".wiki-editor").prepend(bar);
      const zeigen = bar.querySelector("#dr-show");
      if (zeigen) zeigen.onclick = () => dialog(`<h2>Entwurf vom ${esc(when)}</h2>
        <p class="help">Zum Übernehmen die passenden Stellen kopieren und in den Text einfügen.</p>
        <textarea readonly style="min-height:260px;font-family:ui-monospace,monospace">${esc(draft.md)}</textarea>
        <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`);
      const uebernehmen = bar.querySelector("#dr-use");
      if (uebernehmen) uebernehmen.onclick = () => {
        // Auch hier ein Vollersatz: Ein Strg+Z danach nähme nicht den letzten Satz zurück,
        // sondern den ganzen Entwurf – ohne dass man es kommen sieht.
        try { EDVERLAUF.laden(meinEditor, draft.md); } catch (e) { /* egal */ }
        state.dirty = true;
        bar.remove();
      };
      bar.querySelector("#dr-drop").onclick = () => { dropDraft(); bar.remove(); };
    }

    /* Wortzahl und Lesezeit */
    const stats = document.createElement("div");
    stats.className = "help ed-stats";
    $(".wiki-editor").appendChild(stats);
    const updateStats = () => {
      if (!lebt || state.editor !== meinEditor) return;
      let md = "";
      try { md = meinEditor.getMarkdown() || ""; } catch (e) { return; }
      const words = (md.replace(/[#*_`>|\-]+/g, " ").match(/\S+/g) || []).length;
      const min = Math.max(1, Math.round(words / 200));
      stats.textContent = `${words} Wörter · ${md.length} Zeichen · ungefähr ${min} Minute${min === 1 ? "" : "n"} Lesezeit`;
    };
    updateStats();
    const statsTimer = setInterval(updateStats, 4000);
    editorCleanup.push(() => {
      clearInterval(statsTimer);
      clearInterval(entwurfsTakt);
      if (state.autosave === entwurfsTakt) state.autosave = null;
    });
    state.dropDraft = dropDraft;
    state.saveDraft = saveDraft;
    editorCleanup.push(() => { state.saveDraft = null; });

    /* Automatisch speichern – einen Knopf dafür gibt es nicht mehr. Nach jeder Änderung
       wird kurz abgewartet und dann geschrieben; der Stand steht links in der Kopfzeile.
       Jedes Speichern trägt das Kennzeichen dieser Bearbeitung: alle Zwischenstände landen
       damit in derselben Fassung des Verlaufs, und die Beobachter bekommen eine
       Benachrichtigung je Bearbeitung statt je Tastendruck (siehe _revision in api_wiki.py).
       Der Stand von vor dieser Bearbeitung bleibt im Verlauf stehen – auch wenn dieselbe
       Person die Seite kurz darauf noch einmal öffnet. */
    let sitzung = bearbeitungsKennzeichen();
    let letzterSchreib = 0;
    let sicherLauf = 0, sichertGerade = false, wiederholen = false, konflikt = false;
    let leerGemeldet = false;          // der Hinweis kommt einmal je Bearbeitung, nicht je Lauf
    // Der Stand, wie er in der Datenbank steht – nicht die Editorfassung mit den $$-Marken.
    const urText = String(p.content || "");
    let gesichert = urText;
    const stand = (text, warnung) => {
      const st = $("#ed-status");
      if (!st) return;
      st.textContent = text;
      st.classList.toggle("warn", !!warnung);
    };
    const jetztSichern = async () => {
      /* Der Text kommt aus dem EIGENEN Editor und geht an die EIGENE Seite p – beides muss
         zusammenpassen. Wurde der Editor inzwischen abgeräumt, zeigt state.editor auf den der
         nächsten Seite; ein hier nachlaufender Lauf schriebe deren Text unter der ID dieser
         Seite fort, und weil er dasselbe Sitzungskennzeichen trägt, überschriebe er im Verlauf
         auch noch die eigene Fassung. Dann wäre der Text dieser Seite spurlos weg. */
      if (!lebt || state.editor !== meinEditor) return false;
      // Hat jemand anders die Bearbeitung übernommen, schreibt dieser Reiter nicht mehr –
      // sonst überschriebe er die Arbeit des neuen Schreibers.
      if (isNew || konflikt || state.editorGesperrt) return false;
      if (sichertGerade) { wiederholen = true; return false; }
      const md = fromEditorMd(meinEditor.getMarkdown());
      if (md === gesichert) { state.dirty = false; return true; }
      /* Ein leerer Editor bei einer Seite, die eben noch Text hatte, ist fast immer ein Unfall:
         ein Strg+Z zu viel, ein verrutschtes Alles-Markieren, ein Editor, der beim Öffnen
         stolpert. Weil von allein geschrieben wird, wäre der Artikel fort, bevor jemand
         hinsieht – also hier nicht speichern, sondern in der Kopfzeile stehen lassen. Der Text
         steht dabei noch im Editor, Strg+Y holt ihn zurück.
         Absichtliches Leeren bleibt möglich: Die erste Überschrift IST der Seitentitel und
         bleibt ohnehin stehen; alles darunter lässt sich löschen und wird gespeichert. Ganz weg
         kommt eine Seite über Löschen, nicht über einen leeren Text. */
      if (!md.trim() && gesichert.trim()) {
        stand("Nicht gespeichert – der Artikel wäre leer", true);
        if (!leerGemeldet) {
          leerGemeldet = true;
          toast("Der Artikel ist gerade leer und wird so nicht gespeichert. Die Überschrift ist "
                + "zugleich der Seitentitel – sie muss stehen bleiben.", true);
        }
        return false;
      }
      const titel = titelZeile(md) || (p.title || "").trim();
      if (!titel) { stand("Überschrift fehlt", true); return false; }
      // Wer lange nichts geschrieben hat, beginnt mit dem nächsten Stand eine neue Bearbeitung.
      const jetzt = Date.now();
      if (letzterSchreib && jetzt - letzterSchreib > SITZUNG_PAUSE_MS) sitzung = bearbeitungsKennzeichen();
      letzterSchreib = jetzt;
      sichertGerade = true;
      state.speichert = true;
      stand("Speichert …");
      try {
        const r = await api(`/api/wiki/pages/${p.id}`, { method: "PUT", body: {
          title: titel, content: md, format: "markdown", base_version: p.version, sitzung } });
        p.version = r.page.version;
        p.title = r.page.title;
        p.slug = r.page.slug;
        gesichert = md;
        // Der eigene Entwurf, nicht state.dropDraft: das zeigt nach einem Seitenwechsel schon
        // auf den Entwurf der nächsten Seite.
        dropDraft();
        await loadTree();
        // Während der Anfrage kann der Editor geschlossen worden sein. Geschrieben ist dann
        // zwar richtig, aber Statuszeile und Adresszeile gehören jetzt einer anderen Seite.
        if (!lebt || state.editor !== meinEditor) return true;
        state.dirty = false;
        stand(EDMD.repariert() ? "Gespeichert – unvollständige Marken entfernt" : "Gespeichert", EDMD.repariert());
        // Ändert die Überschrift den Titel, ändert sich auch die Adresse – ohne Seitenwechsel.
        if (location.pathname !== `/wiki/${r.page.slug}`) history.replaceState(null, "", `/wiki/${r.page.slug}`);
        return true;
      } catch (e) {
        // Hat jemand anders gespeichert, hilft nur neu laden – sonst liefe das automatische
        // Speichern in eine Schleife aus Fehlermeldungen.
        konflikt = /inzwischen/i.test(e.message || "");
        if (!lebt || state.editor !== meinEditor) return false;
        state.editorKonflikt = konflikt;
        stand(konflikt ? "Nicht gespeichert – die Seite wurde zwischenzeitlich geändert" : "Nicht gespeichert", true);
        if (konflikt) toast(e.message, true);
        return false;
      } finally {
        sichertGerade = false;
        /* Der Nachschlag entsteht ERST hier – also lange nachdem editorCleanup seinen
           clearTimeout gemacht hat. Ohne diese Prüfung wäre er der Zeitgeber, den niemand mehr
           abräumt, und genau er hat die fremde Seite überschrieben. */
        const nachschlag = wiederholen;
        wiederholen = false;
        if (lebt && state.editor === meinEditor) {
          state.speichert = false;
          if (nachschlag) spaeterSichern(300);
        }
      }
    };
    const spaeterSichern = (verzoegerung = 1200) => {
      if (!lebt || isNew || konflikt) return;
      clearTimeout(sicherLauf);
      sicherLauf = setTimeout(() => { sicherLauf = 0; if (lebt) jetztSichern(); }, verzoegerung);
    };
    meinEditor.on("change", () => spaeterSichern());
    editorCleanup.push(() => clearTimeout(sicherLauf));
    // Beim Verlassen geht der letzte Stand noch los; er landet in derselben Fassung wie die
    // Zwischenstände, weil er dasselbe Kennzeichen trägt.
    const abschliessen = async () => {
      clearTimeout(sicherLauf);
      if (!lebt || isNew || konflikt) return true;
      // Wer nur hineingesehen hat, ändert nichts – auch nicht die Schreibweise des Markdowns.
      if (!state.dirty) return true;
      return jetztSichern();
    };
    state.editorAbschluss = abschliessen;
    if (!isNew) praesenzPuls();          // sofort als Schreiber melden, nicht erst beim nächsten Takt
    editorCleanup.push(() => { state.editorAbschluss = null; });

    // Der Umschalter oben rechts ist der kurze Weg zurück in die Ansicht.
    tocKnopfVerdrahten();
    const baum = $("#pg-baum"); if (baum) baum.onclick = () => side.classList.toggle("open");
    /* Suchen/Ersetzen, Formatierung entfernen und „als Markdown kopieren“ gab es nur über
       Tastenkürzel – auf einem Tablet also gar nicht. Dasselbe Menü wie in der Leseansicht,
       mit den Werkzeugen des Editors. */
    const mehr = $("#ed-more");
    if (mehr) mehr.onclick = () => {
      const box = document.createElement("div");
      box.className = "tree-menu";
      box.innerHTML = `
        <button type="button" data-a="suchen">Suchen und ersetzen … <span class="muted small">Strg+Umschalt+F</span></button>
        <button type="button" data-a="klar">Formatierung entfernen <span class="muted small">Strg+\\</span></button>
        <button type="button" data-a="kopieren">Als Markdown kopieren <span class="muted small">Strg+Umschalt+C</span></button>
        ${isNew ? "" : '<button type="button" data-a="verlauf">Verlauf …</button>'}`;
      document.body.appendChild(box);
      const r = mehr.getBoundingClientRect();
      box.style.left = `${Math.max(8, Math.min(window.innerWidth - box.offsetWidth - 8, r.left))}px`;
      box.style.top = `${window.scrollY + r.bottom + 4}px`;
      const zu = () => { box.remove(); document.removeEventListener("pointerdown", aussen, true); mehr.focus(); };
      const aussen = (e) => { if (!box.contains(e.target)) zu(); };
      setTimeout(() => document.addEventListener("pointerdown", aussen, true), 0);
      wireMenuKeys(box, zu);
      box.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-a]");
        if (!b) return;
        zu();
        if (b.dataset.a === "suchen" && state.editorSuchen) state.editorSuchen();
        else if (b.dataset.a === "klar" && state.editorKlartext) state.editorKlartext();
        else if (b.dataset.a === "kopieren" && state.editorCopyMd) state.editorCopyMd();
        else if (b.dataset.a === "verlauf") showHistory(p);
      });
    };
    const leseKnopf = $("#ed-read");
    if (leseKnopf) leseKnopf.onclick = async () => {
      if (isNew && state.dirty) return $("#ed-save").click();
      await abschliessen();
      modusScrollMerken();
      if (leaveEditor()) show(p.slug);
    };
    /* "Verwerfen" gibt es nur bei einer neuen Seite: die steht noch nirgends und wird
       ausdrücklich angelegt. Eine vorhandene Seite schreibt der Editor von allein – dort
       gäbe es nichts zu verwerfen; ältere Stände holt der Verlauf zurück. */
    const abbrechen = $("#ed-cancel");
    if (abbrechen) abbrechen.onclick = () => {
      clearTimeout(sicherLauf);
      state.dirty = false;
      if (!leaveEditor()) return;
      dropDraft();
      state.dropDraft = null;
      show(p.parent_id && state.byId.get(p.parent_id) ? state.byId.get(p.parent_id).slug : slugFromPath());
    };
    // Nur noch für eine neue Seite: sie wird ausdrücklich angelegt, danach schreibt der
    // Editor von allein.
    let speichertGerade = false;
    const anlegenKnopf = $("#ed-save");
    if (anlegenKnopf) anlegenKnopf.onclick = async () => {
      if (speichertGerade) return;                 // Doppelklick legte die Seite sonst zweimal an
      const md = fromEditorMd(meinEditor.getMarkdown());
      const titel = titelZeile(md) || (p.title || "").trim();
      const body = { title: titel, content: md, format: "markdown" };
      if (isNew) body.parent_id = p.parent_id || null;
      // Stand, auf dem diese Fassung beruht – der Server lehnt ab, wenn inzwischen jemand anders gespeichert hat
      if (!isNew) body.base_version = p.version;
      if (!body.title) return toast("Die erste Zeile ist der Seitentitel – bitte eine Überschrift setzen.", true);
      $("#ed-status").textContent = "Speichern …";
      speichertGerade = true;
      state.speichert = true;
      const warHier = state.current ? state.current.id : null;
      const knopf = $("#ed-save");
      if (knopf) knopf.disabled = true;
      try {
        const r = isNew ? await api("/api/wiki/pages", { method: "POST", body })
                        : await api(`/api/wiki/pages/${p.id}`, { method: "PUT", body });
        state.dirty = false;
        if (state.dropDraft) { state.dropDraft(); state.dropDraft = null; }
        destroyEditor();
        // Fehlt einem Abschnitt eine Marke, verschwindet er beim Speichern – das darf nicht
        // stillschweigend passieren, deshalb geht der Hinweis der Erfolgsmeldung vor.
        toast(EDMD.repariert()
          ? "Gespeichert. Ein Spalten- oder Ausrichtungsabschnitt war unvollständig – die Marken "
            + "wurden entfernt, der Inhalt bleibt erhalten."
          : (isNew ? "Seite angelegt" : "Gespeichert"), EDMD.repariert());
        await loadTree();
        // Ist der Nutzer während des Speicherns weitergegangen, bleibt er dort.
        if (!state.current || state.current.id === warHier || state.current.id === r.page.id) navigate(r.page.slug);
      } catch (e) {
        const st = $("#ed-status"); if (st) st.textContent = "";
        toast(e.message, true);
      } finally {
        speichertGerade = false;
        state.speichert = false;
        const k = $("#ed-save"); if (k) k.disabled = false;
      }
    };
  }

  /* ======================================================================
     Verlauf, Suche, Import
     ====================================================================== */
  async function showHistory(p) {
    let revs;
    try { revs = (await api(`/api/wiki/pages/${p.id}/revisions`)).revisions; } catch (e) { return toast(e.message, true); }
    dialog(`<h2>Verlauf: ${esc(p.title)}</h2>
      <ul class="rev-list" style="list-style:none;padding:0;margin:10px 0">${revs.map((r, i) => `
        <li><span>${fmtDate(r.created_at, true)}</span><span class="muted small">${esc(r.user_name || "")} · ${(r.size / 1000).toFixed(1)} kB${i === 0 ? " · aktuell" : ""}</span>
          <span class="btn-row" style="margin-left:auto"><button class="btn ghost small" data-view="${r.id}">Ansehen</button>${i < revs.length - 1 ? `<button class="btn ghost small" data-diff="${i}">Änderungen</button>` : ""}${i > 0 && p.can_edit ? `<button class="btn secondary small" data-restore="${r.id}">Wiederherstellen</button>` : ""}</span></li>`).join("")}</ul>
      <div id="rev-view"></div>
      <div class="dlg-actions"><button class="btn secondary" data-close type="button">Schließen</button></div>`,
      (dlg, body) => {
        dlg.classList.add("wide");
        dlg.addEventListener("close", () => dlg.classList.remove("wide"), { once: true });
        body.querySelectorAll("[data-view]").forEach((b) => b.onclick = async () => {
          try {
            const r = (await api(`/api/wiki/revisions/${b.dataset.view}`)).revision;
            body.querySelector("#rev-view").innerHTML = `<h3>${esc(r.title)} <span class="muted small">(${fmtDate(r.created_at, true)})</span></h3><div class="wiki-content boxed">${renderBody(r)}</div>`;
          } catch (e) { toast(e.message, true); }
        });
        body.querySelectorAll("[data-diff]").forEach((b) => b.onclick = async () => {
          /* Der Knopf steht an der Fassung, die er zeigt: Verglichen wird sie mit der
             Fassung davor. Vorher griff er eine Zeile zu weit nach oben – an der neuesten
             Fassung lief er damit ins Leere („Cannot read properties of undefined“), und an
             allen anderen zeigte er die Änderungen der Fassung darüber. */
          const i = +b.dataset.diff;
          const newer = revs[i], older = revs[i + 1];
          try {
            const [a, bb] = await Promise.all([
              api(`/api/wiki/revisions/${older.id}`), api(`/api/wiki/revisions/${newer.id}`)]);
            body.querySelector("#rev-view").innerHTML =
              `<h3>Änderungen <span class="muted small">${fmtDate(older.created_at, true)} → ${fmtDate(newer.created_at, true)}</span></h3>`
              + `<div class="diff boxed">${wordDiff(a.revision.content, bb.revision.content)}</div>`;
          } catch (e) { toast(e.message, true); }
        });
        body.querySelectorAll("[data-restore]").forEach((b) => b.onclick = async () => {
          if (!(await S.confirm("Diese Version wiederherstellen? Die aktuelle Fassung bleibt im Verlauf erhalten.", "Wiederherstellen"))) return;
          try {
            const r = await api(`/api/wiki/revisions/${b.dataset.restore}/restore`, { method: "POST", body: {} });
            dlg.close(); toast("Version wiederhergestellt"); await loadTree(); navigate(r.page.slug);
          } catch (e) { toast(e.message, true); }
        });
      });
  }

  /* Einfacher Wortvergleich zweier Fassungen: gemeinsame Teilfolge über die Wörter.
     Reicht für „was hat sich geändert“ und kommt ohne zusätzliche Bibliothek aus. */
  function wordDiff(oldText, newText) {
    const split = (t) => String(t || "").split(/(\s+)/);
    const a = split(oldText), b = split(newText);
    const n = a.length, m = b.length;
    // Bei sehr langen Texten nur die Zeilen vergleichen, sonst wird die Tabelle zu groß.
    if (n * m > 4000000) {
      const la = String(oldText || "").split("\n"), lb = String(newText || "").split("\n");
      const setA = new Set(la);
      return lb.map((l) => setA.has(l) ? esc(l) : `<ins>${esc(l)}</ins>`).join("<br>");
    }
    const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const out = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { out.push(esc(a[i])); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push(`<del>${esc(a[i])}</del>`); i++; }
      else { out.push(`<ins>${esc(b[j])}</ins>`); j++; }
    }
    while (i < n) out.push(`<del>${esc(a[i++])}</del>`);
    while (j < m) out.push(`<ins>${esc(b[j++])}</ins>`);
    return out.join("");
  }

  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) { searchResults.classList.add("hidden"); searchResults.innerHTML = ""; return; }
    searchTimer = setTimeout(async () => {
      try {
        const d = await api(`/api/wiki/search?q=${encodeURIComponent(q)}`);
        if (searchInput.value.trim() !== q) return;     // inzwischen weitergetippt oder geleert
        searchResults.classList.remove("hidden");
        searchResults.innerHTML = d.results.length
          ? d.results.map((r) => `<li><a href="/wiki/${esc(r.slug)}">${esc(r.title)}</a>${r.snippet ? `<div class="snip">${esc(r.snippet)}</div>` : ""}</li>`).join("")
          : '<li class="muted">Keine Treffer.</li>';
        searchResults.querySelectorAll("a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); side.classList.remove("open"); navigate(a.getAttribute("href").slice(6)); }));
      } catch (e) { toast(e.message, true); }
    }, 250);
  });

  /* ======================================================================
     Start
     ====================================================================== */
  $("#btn-new-page").addEventListener("click", () => { side.classList.remove("open"); if (leaveEditor()) openEditor({ parent_id: state.current ? state.current.id : null }); });
  $("#btn-trash").addEventListener("click", trashDialog);

  /* Sidebar-Breite ziehen und merken */
  (function () {
    const shellEl = $(".wiki-shell");
    let w = 0;
    try { w = parseInt(localStorage.getItem("stroemis-sidebar") || "", 10) || 0; } catch (e) { /* egal */ }
    if (w >= 180 && w <= 560) shellEl.style.setProperty("--side-w", w + "px");
    const grip = document.createElement("div");
    grip.className = "side-grip";
    grip.title = "Breite ziehen";
    side.appendChild(grip);
    grip.addEventListener("mousedown", (e) => {
      e.preventDefault();
      grip.classList.add("dragging");
      const move = (ev) => {
        const next = Math.max(180, Math.min(560, ev.clientX - side.getBoundingClientRect().left));
        shellEl.style.setProperty("--side-w", next + "px");
      };
      const up = () => {
        grip.classList.remove("dragging");
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        try { localStorage.setItem("stroemis-sidebar", parseInt(getComputedStyle(shellEl).getPropertyValue("--side-w"), 10)); }
        catch (e) { /* egal */ }
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });
  })();
  $("#wiki-menu").addEventListener("click", () => side.classList.toggle("open"));
  document.addEventListener("pointerdown", (e) => {
    if (side.classList.contains("open") && !side.contains(e.target) && e.target.id !== "wiki-menu"
        && !e.target.closest("#pg-baum")) side.classList.remove("open");
  }, true);

  loadTree().then(() => show(shell.dataset.slug || slugFromPath())).catch((e) => toast(e.message, true));
})();
