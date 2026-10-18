/* Öffentliches Wiki: freigegebene Seiten lesen – ohne Login (public.html) und im Lesemodus für angemeldete Konten
   ohne Stufe im Wiki (wiki_lesemodus.html). Beide lesen nur über /api/public: Was zu sehen ist, entscheidet der
   Server an einer Stelle (api_wiki.is_public), nicht dieses Skript. */
(function () {
  const esc = MD.esc;
  const $ = (s) => document.querySelector(s);
  const shell = $(".wiki-shell"), treeEl = $("#tree"), content = $("#wiki-content"), tocEl = $("#toc"), side = $("#wiki-side");
  const lesemodus = shell.dataset.modus === "lesemodus";
  /* Seiten liegen unter prefix + slug, die Übersicht unter start. Im Lesemodus sind das /wiki/… und /wiki – eine
     Adresse /wiki/ gibt es dort nicht, ein Neuladen der Übersicht endete sonst auf der 404-Seite. */
  const prefix = shell.dataset.prefix || (location.pathname.startsWith("/oeffentlich") ? "/oeffentlich/" : "/");
  const start = shell.dataset.start || prefix;
  const adresse = (slug) => (slug ? prefix + slug : start);
  const slugAusPfad = () => (location.pathname.startsWith(prefix) ? location.pathname.slice(prefix.length) : "");
  let stopSpy = null;

  async function get(path) {
    let r;
    // Der Status gehört an den Fehler – sonst ist "gibt es nicht" von "gerade nicht
    // erreichbar" nicht zu unterscheiden (siehe einbauFuellen in markdown.js).
    try { r = await fetch(path, { credentials: "same-origin" }); }
    catch (e) { const netz = new Error("Keine Verbindung zum Server."); netz.status = 0; throw netz; }
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { const err = new Error(d.error || "Fehler " + r.status); err.status = r.status; throw err; }
    return d;
  }

  /* Eigene Adressen, die keine Wiki-Seite sind: Anhänge, statische Dateien, API. */
  const isFile = (href) => /^\/(api|media|static)\//.test(href);
  /* Fremd ist, was einen anderen Ursprung hat – ganz, nicht als Vorsatz: Mit startsWith galt
     "https://stroemis.de.evil.example/" als eigene Adresse. Lässt sich die Adresse nicht
     deuten, zählt sie als fremd. */
  const istFremd = (href) => { try { return new URL(href, location.href).origin !== location.origin; } catch (e) { return true; } };

  function wire(root) {
    root.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (/^https?:\/\//i.test(href) && istFremd(href)) { a.target = "_blank"; a.rel = "noopener"; }
      else if ((href.startsWith(prefix) || href === start) && !isFile(href)) a.addEventListener("click", (e) => { e.preventDefault(); navigate(href === start ? "" : href.slice(prefix.length)); });
    });
  }

  function navigate(ziel, push = true) {
    side.classList.remove("open");        // auf dem Telefon liegt die Seitenleiste über dem Text
    // Ein Link mit Sprungmarke (…/seite#abschnitt): Die Marke gehört in die Adresse, nicht in den Seitennamen –
    // sonst fragte der Leser nach „seite#abschnitt“ und meldete eine vorhandene Seite als nicht gefunden.
    const slug = ziel.split("#")[0];
    if (push) history.pushState({ slug }, "", adresse(slug) + ziel.slice(slug.length));
    show(slug);
  }
  window.addEventListener("popstate", () => show(slugAusPfad()));

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
    catch (e) {
      /* Im Lesemodus sagt die Meldung, wo die Seite sonst sein könnte – für „gibt es nicht“ und „nicht öffentlich“
         wortgleich, wie die Schnittstelle selbst: Sonst ließe sich abfragen, welche internen Seiten es gibt. */
      const text = lesemodus && e.status === 404 ? "Diese Seite gibt es nicht, oder sie steht nur im internen Wiki." : e.message;
      content.innerHTML = `<div class="empty"><strong>Seite nicht gefunden</strong>${esc(text)}<div class="btn-row" style="justify-content:center;margin-top:12px"><a class="btn secondary small" href="${start}">Zur Übersicht</a></div></div>`;
      wire(content);
      // Das Inhaltsverzeichnis gehörte der vorigen Seite – seine Sprungziele gibt es hier nicht.
      tocEl.innerHTML = "";
      if (stopSpy) { stopSpy(); stopSpy = null; }
      // Direkt aufgerufen stand der Baum sonst leer da: dann die Einstiegsseiten wie auf der Übersicht. Nach dem
      // Laden noch einmal nachsehen – ist inzwischen eine andere Seite offen, hat sie ihren eigenen Baum gezeichnet.
      if (lesemodus && !treeEl.children.length) {
        const pages = await einstiegsseiten();
        if (!treeEl.children.length) indexBaum(pages);
      }
      return;
    }
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
    const verzeichnisZeichnen = (liste) => {
      tocEl.innerHTML = liste.length ? `<div class="rail-title">Inhalt</div>${MD.tocHtml(liste)}` : "";
      if (stopSpy) stopSpy();
      stopSpy = MD.tocScrollspy(art, tocEl);
    };
    MD.enhance(art, { children: (d.tree || []).filter((t) => t.parent_id === p.id), prefix,
                      holeSeite: (slug) => get(`/api/public/pages/${encodeURIComponent(slug)}`).then((r) => r.page),
                      /* Eingebundener Text trifft erst nach dem Zeichnen ein. Ohne dieselbe
                         Behandlung führten seine internen Links auf /wiki/… und damit zur
                         Anmeldung, und seine Überschriften fehlten im Verzeichnis. */
                      nachInhalt: (el) => {
                        el.querySelectorAll('a[href^="/wiki/"]').forEach((a) =>
                          a.setAttribute("href", prefix + a.getAttribute("href").slice(6)));
                        wire(el);
                        verzeichnisZeichnen(MD.buildToc(art));
                      } });
    verzeichnisZeichnen(items);
    if (!MD.scrollToHash(content)) window.scrollTo(0, 0);
  }

  async function einstiegsseiten() {
    try { return (await get("/api/public/index")).pages; } catch (e) { return []; }
  }

  function indexBaum(pages) {
    treeEl.innerHTML = pages.length ? `<ul>${pages.map((p) => `<li class="leaf"><div class="row"><span class="tg"></span><a href="${prefix}${esc(p.slug)}">${esc(p.title)}</a></div></li>`).join("")}</ul>` : "";
    wire(treeEl);
  }

  async function home() {
    document.title = "Wiki – strömis.de";
    const pages = await einstiegsseiten();
    indexBaum(pages);
    tocEl.innerHTML = "";
    // Im Lesemodus steht der Hinweis auf die Freischaltung schon über dem Text (wiki_lesemodus.html), und angemeldet
    // ist das Konto bereits – deshalb dort ohne „anmelden“ und mit eigenem Text, wenn nichts freigegeben ist.
    const titel = lesemodus ? "Wiki" : "Öffentliches Wiki";
    const einleitung = lesemodus
      ? "Freigegebene Inhalte aus der Strömungsrettung."
      : `Freigegebene Inhalte aus der Strömungsrettung. Für alles Weitere: <a href="${STROEMIS.baseUrl}/login">anmelden</a>.`;
    const leer = lesemodus ? "Derzeit sind keine Seiten öffentlich freigegeben." : "Derzeit sind keine Seiten freigegeben.";
    content.innerHTML = `<div class="wiki-head"><nav class="krumen" aria-label="Pfad"><span class="krume" aria-current="page">${titel}</span></nav></div>
      <h1 class="seitentitel">${titel}</h1>
      <p class="help">${einleitung}</p>
      <div class="wiki-content">${pages.length ? `<ul>${pages.map((p) => `<li><a href="${prefix}${esc(p.slug)}">${esc(p.title)}</a>${p.public_children ? ' <span class="muted small">(mit Unterseiten)</span>' : ""}</li>`).join("")}</ul>` : `<p class="muted">${leer}</p>`}</div>`;
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
  show(shell.dataset.slug || slugAusPfad());
})();
