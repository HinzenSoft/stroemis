/* Öffentliches Wiki (ohne Login): freigegebene Seiten lesen */
(function () {
  const esc = MD.esc;
  const $ = (s) => document.querySelector(s);
  const shell = $(".wiki-shell"), treeEl = $("#tree"), content = $("#wiki-content"), tocEl = $("#toc"), side = $("#wiki-side");
  const prefix = location.pathname.startsWith("/oeffentlich") ? "/oeffentlich/" : "/";
  let stopSpy = null;

  async function get(path) {
    const r = await fetch(path, { credentials: "same-origin" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "Fehler " + r.status);
    return d;
  }

  /* Eigene Adressen, die keine Wiki-Seite sind: Anhänge, statische Dateien, API. */
  const isFile = (href) => /^\/(api|media|static)\//.test(href);

  function wire(root) {
    root.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (/^https?:\/\//i.test(href) && !href.startsWith(location.origin)) { a.target = "_blank"; a.rel = "noopener"; }
      else if (href.startsWith(prefix) && !isFile(href)) a.addEventListener("click", (e) => { e.preventDefault(); navigate(href.slice(prefix.length)); });
    });
  }

  function navigate(slug, push = true) {
    side.classList.remove("open");        // auf dem Telefon liegt die Seitenleiste über dem Text
    if (push) history.pushState({ slug }, "", prefix + slug);
    show(slug);
  }
  window.addEventListener("popstate", () => show(location.pathname.slice(prefix.length)));

  function tree(rows, current) {
    const kids = (pid) => rows.filter((r) => (r.parent_id || null) === pid);
    const branch = (pid) => {
      const k = kids(pid);
      return k.length ? `<ul>${k.map((r) => `<li class="${kids(r.id).length ? "" : "leaf"}"><div class="row"><span class="tg"></span><a href="${prefix}${esc(r.slug)}" class="${r.slug === current ? "active" : ""}">${esc(r.title)}</a></div>${branch(r.id)}</li>`).join("")}</ul>` : "";
    };
    // Die Wurzel des freigegebenen Abschnitts hat parent_id null
    treeEl.innerHTML = branch(null);
    wire(treeEl);
  }

  async function show(slug) {
    if (!slug) return home();
    let d;
    try { d = await get(`/api/public/pages/${encodeURIComponent(slug)}`); }
    catch (e) { content.innerHTML = `<div class="empty"><strong>Seite nicht gefunden</strong>${esc(e.message)}<div class="btn-row" style="justify-content:center;margin-top:12px"><a class="btn secondary small" href="${prefix}">Zur Übersicht</a></div></div>`; wire(content); return; }
    const p = d.page;
    if (p.slug !== slug) history.replaceState({ slug: p.slug }, "", prefix + p.slug);
    document.title = `${p.title} – Wiki – strömis.de`;
    tree(d.tree, p.slug);
    const html = MD.render(p.content);
    // Derselbe Aufbau wie im angemeldeten Wiki: klebende Pfadzeile, Titel, Autorzeile –
    // vorher stand der Titel in der klebenden Leiste und darunter zwei dicke Linien.
    content.innerHTML = `<div class="wiki-head"><nav class="krumen" aria-label="Pfad"><span class="krume" aria-current="page">${esc(p.title)}</span></nav></div>
      <h1 class="seitentitel">${esc(p.title)}</h1>
      <div class="autorzeile"><span class="autorname">Stand ${new Date(p.updated_at).toLocaleDateString("de-DE")}</span></div>
      <article class="wiki-content" id="article">${html}</article>`;
    const art = $("#article");
    const first = art.firstElementChild;
    if (first && first.tagName === "H1" && first.textContent.trim().toLowerCase() === p.title.trim().toLowerCase()) first.remove();
    // Links auf interne Wiki-Seiten auf den öffentlichen Bereich umbiegen
    art.querySelectorAll('a[href^="/wiki/"]').forEach((a) => a.setAttribute("href", prefix + a.getAttribute("href").slice(6)));
    wire(content);
    const items = MD.buildToc(art);
    // Eingebundene Abschnitte nur aus dem öffentlichen Bestand: Ist die Quellseite nicht
    // freigegeben, antwortet die Schnittstelle gar nicht erst mit ihr.
    MD.enhance(art, { children: (d.tree || []).filter((t) => t.parent_id === p.id), prefix,
                      holeSeite: (slug) => get(`/api/public/pages/${encodeURIComponent(slug)}`).then((r) => r.page) });
    tocEl.innerHTML = items.length ? `<div class="rail-title">Inhalt</div>${MD.tocHtml(items)}` : "";
    if (stopSpy) stopSpy();
    stopSpy = MD.tocScrollspy(art, tocEl);
    if (!MD.scrollToHash(content)) window.scrollTo(0, 0);
  }

  async function home() {
    document.title = "Wiki – strömis.de";
    let pages = [];
    try { pages = (await get("/api/public/index")).pages; } catch (e) { /* leer */ }
    treeEl.innerHTML = pages.length ? `<ul>${pages.map((p) => `<li class="leaf"><div class="row"><span class="tg"></span><a href="${prefix}${esc(p.slug)}">${esc(p.title)}</a></div></li>`).join("")}</ul>` : "";
    tocEl.innerHTML = "";
    content.innerHTML = `<div class="wiki-head"><nav class="krumen" aria-label="Pfad"><span class="krume" aria-current="page">Öffentliches Wiki</span></nav></div>
      <h1 class="seitentitel">Öffentliches Wiki</h1>
      <p class="help">Freigegebene Inhalte aus der Strömungsrettung. Für alles Weitere: <a href="${STROEMIS.baseUrl}/login">anmelden</a>.</p>
      <div class="wiki-content">${pages.length ? `<ul>${pages.map((p) => `<li><a href="${prefix}${esc(p.slug)}">${esc(p.title)}</a>${p.public_children ? ' <span class="muted small">(mit Unterseiten)</span>' : ""}</li>`).join("")}</ul>` : '<p class="muted">Derzeit sind keine Seiten freigegeben.</p>'}</div>`;
    wire(content);
  }

  /* Suche im öffentlichen Bereich */
  const searchInput = $("#wiki-search"), searchResults = $("#search-results");
  let searchTimer;
  if (searchInput) searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) { searchResults.classList.add("hidden"); searchResults.innerHTML = ""; return; }
    searchTimer = setTimeout(async () => {
      let d;
      try { d = await get(`/api/public/search?q=${encodeURIComponent(q)}`); } catch (e) { return; }
      searchResults.classList.remove("hidden");
      searchResults.innerHTML = d.results.length
        ? d.results.map((r) => `<li><a href="${prefix}${esc(r.slug)}">${esc(r.title)}</a>${r.snippet ? `<div class="snip">${esc(r.snippet)}</div>` : ""}</li>`).join("")
        : '<li class="muted">Keine Treffer.</li>';
      searchResults.querySelectorAll("a").forEach((a) => a.addEventListener("click", (e) => {
        e.preventDefault(); side.classList.remove("open");
        searchResults.classList.add("hidden"); searchInput.value = "";
        navigate(a.getAttribute("href").slice(prefix.length));
      }));
    }, 250);
  });

  $("#wiki-menu").addEventListener("click", () => side.classList.toggle("open"));
  // Tippen daneben oder Escape schließt die Schublade – wie im angemeldeten Wiki.
  document.addEventListener("pointerdown", (e) => {
    if (side.classList.contains("open") && !side.contains(e.target) && e.target.id !== "wiki-menu") side.classList.remove("open");
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") side.classList.remove("open"); });
  show(shell.dataset.slug || location.pathname.slice(prefix.length));
})();
