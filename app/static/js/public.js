/* Öffentliche Strömipedia: freigegebene Seiten lesen – ohne Login (public.html) und im Lesemodus für angemeldete Konten
   ohne Stufe im Wiki (wiki_lesemodus.html). Beide lesen nur über /api/public: Was zu sehen ist, entscheidet der
   Server an einer Stelle (api_wiki.is_public), nicht dieses Skript. */
(function () {
  const esc = MD.esc;
  const $ = (s) => document.querySelector(s);
  const shell = $(".wiki-shell"), treeEl = $("#tree"), content = $("#wiki-content"), tocEl = $("#toc"), side = $("#wiki-side");
  // Zurück schließt die offene Schublade (UI/UX vor dem Merge, A1) – im Lesemodus mit common.js, die öffentliche Seite hat es nicht.
  if (window.S && S.klassenVerlauf && side) {
    S.klassenVerlauf(side, "open", () => side.classList.remove("open"), () => getComputedStyle(side).position === "fixed");
    // Zugeklappt inert und aria-hidden, „☰“ mit aria-expanded (Gerätetest B14).
    if (S.schubladeZustand) S.schubladeZustand(side, "#wiki-menu");
  } else if (side && $("#wiki-menu")) {
    // public.html ohne common.js: „☰“ trägt seit der Suchzeile (02.11.2026) aria-expanded – es folgt der Schublade.
    new MutationObserver(() => $("#wiki-menu").setAttribute("aria-expanded", String(side.classList.contains("open"))))
      .observe(side, { attributes: true, attributeFilter: ["class"] });
  }
  const lesemodus = shell.dataset.modus === "lesemodus";
  /* Seiten liegen unter prefix + slug, die Übersicht unter start. Im Lesemodus sind das /stroemipedia/… und
     /stroemipedia – eine Adresse /stroemipedia/ gibt es dort nicht, ein Neuladen der Übersicht endete sonst auf der 404-Seite. */
  const prefix = shell.dataset.prefix || (location.pathname.startsWith("/oeffentlich") ? "/oeffentlich/" : "/");
  const start = shell.dataset.start || prefix;
  const adresse = (slug) => (slug ? prefix + slug : start);
  /* Gespeicherte interne Links: /wiki/<slug> (vor der Umbenennung vom 26.10.2026, Inhalte werden nicht umgeschrieben)
     und /stroemipedia/<slug> – beide auf das Präfix dieses Lesers umbiegen. */
  const internUmbiegen = (el) => el.querySelectorAll('a[href^="/stroemipedia/"], a[href^="/wiki/"]').forEach((a) =>
    a.setAttribute("href", prefix + a.getAttribute("href").replace(/^\/(?:stroemipedia|wiki)\//, "")));
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
  /* Ein Schritt im Verlauf zeigt eine andere Seite – die Trefferliste der Suchzeile gehört nicht dazu. (Im Lesemodus
     schließt Zurück sie schon vorher als eigener Schritt, S.klassenVerlauf; public.html hat common.js nicht.) */
  window.addEventListener("popstate", () => {
    if (zeilenSuche) zeilenSuche.schliessen();
    show(slugAusPfad());
  });

  /* Klappzeichen wie im Seitenbaum der internen Strömipedia (wiki.js): ein gezeichneter Winkel, hier immer aufgeklappt
     (nach unten gedreht, app.css) – der öffentliche Baum klappt nicht. */
  const KLAPPZEICHEN = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6 3.5L10.5 8 6 12.5"/></svg>';
  function tree(rows, current) {
    const kids = (pid) => rows.filter((r) => (r.parent_id || null) === pid);
    const branch = (pid) => {
      const k = kids(pid);
      return k.length ? `<ul>${k.map((r) => `<li class="${kids(r.id).length ? "" : "leaf"}"><div class="row"><span class="tg">${kids(r.id).length ? KLAPPZEICHEN : ""}</span><a href="${prefix}${esc(r.slug)}" class="${r.slug === current ? "active" : ""}"><span class="baum-titel">${esc(r.title)}</span></a></div>${branch(r.id)}</li>`).join("")}</ul>` : "";
    };
    // Die Wurzel des freigegebenen Abschnitts hat parent_id null
    treeEl.innerHTML = branch(null);
    wire(treeEl);
  }

  async function show(slug) {
    if (!slug) return home();
    shell.classList.remove("uebersicht");
    let d;
    try { d = await get(`/api/public/pages/${encodeURIComponent(slug)}`); }
    catch (e) {
      /* Im Lesemodus sagt die Meldung, wo die Seite sonst sein könnte – für „gibt es nicht“ und „nicht öffentlich“
         wortgleich, wie die Schnittstelle selbst: Sonst ließe sich abfragen, welche internen Seiten es gibt. */
      const text = lesemodus && e.status === 404 ? "Diese Seite gibt es nicht, oder sie steht nur in der internen Strömipedia." : e.message;
      content.innerHTML = `<div class="wiki-head"><h1>Seite nicht gefunden</h1></div><p class="leerzustand">${esc(text)}</p>
        <div class="btn-row"><a class="btn secondary small" href="${start}">Zur Übersicht</a></div>`;
      wire(content);
      // Das Inhaltsverzeichnis gehörte der vorigen Seite – seine Sprungziele gibt es hier nicht. Ebenso ihr Titel im
      // Reiter (und im Verlauf) und ihre Markierung im Baum: Sonst stand dort weiter die Seite, die man verlassen hat.
      tocEl.innerHTML = "";
      if (stopSpy) { stopSpy(); stopSpy = null; }
      document.title = "Seite nicht gefunden – Strömipedia – strömis.de";
      treeEl.querySelectorAll("a.active").forEach((a) => a.classList.remove("active"));
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
    document.title = `${p.title} – Strömipedia – strömis.de`;
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
    // Links auf interne Seiten auf den öffentlichen Bereich umbiegen
    internUmbiegen(art);
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
                      // leise: Die Quellseite eines eingebauten Abschnitts ist kein Besuch („Zuletzt besucht“ der Startseite).
                      holeSeite: (slug) => get(`/api/public/pages/${encodeURIComponent(slug)}?leise=1`).then((r) => r.page),
                      /* Eingebundener Text trifft erst nach dem Zeichnen ein. Ohne dieselbe
                         Behandlung führten seine internen Links auf /stroemipedia/… und damit zur
                         Anmeldung, und seine Überschriften fehlten im Verzeichnis. */
                      nachInhalt: (el) => {
                        internUmbiegen(el);
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
    treeEl.innerHTML = pages.length ? `<ul>${pages.map((p) => `<li class="leaf"><div class="row"><span class="tg"></span><a href="${prefix}${esc(p.slug)}"><span class="baum-titel">${esc(p.title)}</span></a></div></li>`).join("")}</ul>` : "";
    wire(treeEl);
  }

  async function home() {
    document.title = "Strömipedia – strömis.de";
    const pages = await einstiegsseiten();
    indexBaum(pages);
    tocEl.innerHTML = "";
    // Im Lesemodus steht der Hinweis auf die Freischaltung schon über dem Text (wiki_lesemodus.html), und angemeldet
    // ist das Konto bereits – deshalb dort ohne „anmelden“ und mit eigenem Text, wenn nichts freigegeben ist.
    // Im Lesemodus heißt die Seite nicht noch einmal „Strömipedia“ – das stehen schon Reiter und Hinweis darüber (UI/UX vor
    // dem Merge C5: vorher dreimal untereinander); die Pfadzeile mit nur dem Seitennamen fällt auf der Übersicht weg.
    const titel = lesemodus ? "Freigegebene Seiten" : "Öffentliche Strömipedia";
    const einleitung = lesemodus
      ? "Freigegebene Inhalte aus der Strömungsrettung."
      : `Freigegebene Inhalte aus der Strömungsrettung. Für alles Weitere: <a href="${STROEMIS.baseUrl}/login">anmelden</a>.`;
    const leer = lesemodus ? "Derzeit sind keine Seiten für alle Angemeldeten freigegeben." : "Derzeit sind keine Seiten freigegeben.";
    /* Die Einstiegsseiten als Karten wie auf der Übersicht der Strömipedia (wiki.js) und der Startseite: Titel, Zahl der
       Seiten, die ersten Unterseiten (/api/public/index, api_wiki.abschnitte) – vorher eine Liste. */
    // Mit dem Symbol der Seite wie auf der Startseite und der Übersicht der Strömipedia (wiki.js).
    const seite = (s) => `<a href="${prefix}${esc(s.slug)}">${s.icon ? esc(s.icon) + " " : ""}${esc(s.title)}</a>`;
    const karte = (p) => {
      const mehr = (p.kinder || 0) - (p.unterseiten || []).length;
      return `<li class="wiki-karte"><h2>${seite(p)}</h2>
        <p class="wiki-karte-zahl">${p.seiten === 1 ? "1 Seite" : `${Number(p.seiten)} Seiten`}</p>
        ${(p.unterseiten || []).length ? `<ul>${p.unterseiten.map((u) => `<li>${seite(u)}</li>`).join("")}${mehr > 0
          ? `<li class="wiki-karte-mehr"><a href="${prefix}${esc(p.slug)}">… ${mehr} weitere<span class="nur-vorlesen"> ${mehr === 1 ? "Unterseite" : "Unterseiten"} von ${esc(p.title)}</span></a></li>` : ""}</ul>` : ""}</li>`;
    };
    if (lesemodus) shell.classList.add("uebersicht");
    content.innerHTML = `<h1 class="seitentitel">${titel}</h1>
      <p class="help">${einleitung}</p>
      ${pages.length ? `<ul class="wiki-karten">${pages.map(karte).join("")}</ul>` : `<p class="muted">${leer}</p>`}`;
    wire(content);
  }

  /* Artikel suchen – im Feld über dem Seitenbaum und unter 1024 px in der Suchzeile oben im Inhalt (wiki_lesemodus.html,
     public.html; wie in der Strömipedia seit dem 02.11.2026, für den Lesemodus vom Nutzer am selben Tag bestätigt).
     Dieselbe Logik wie dort (MD.sucheVerdrahten, MD.suchzeileEinrichten in markdown.js), nur über /api/public/search:
     Gefunden werden ausschließlich freigegebene Seiten. */
  const searchInput = $("#wiki-search"), searchResults = $("#search-results");
  const artikelsuche = {
    suchen: async (q) => (await get(`/api/public/search?q=${encodeURIComponent(q)}`)).results,
    adresse: (slug) => prefix + slug,
    oeffnen: (href) => navigate(href.slice(prefix.length)),      // navigate schließt auch die Schublade
    // Im Lesemodus mit der Meldung aus common.js; public.html lädt common.js nicht – dort bleibt es still wie bisher.
    fehler: (text) => { if (window.S && S.toast) S.toast(text, true); },
  };
  MD.sucheVerdrahten(searchInput, searchResults, artikelsuche);
  const suchzeile = $("#wiki-suchzeile");
  const zeilenSuche = suchzeile && MD.sucheVerdrahten($("#zeilen-suche"), $("#zeilen-treffer"), { ...artikelsuche, zeile: suchzeile });
  const zeileSteht = MD.suchzeileEinrichten(shell, suchzeile, zeilenSuche, searchInput);

  $("#wiki-menu").addEventListener("click", () => side.classList.toggle("open"));
  // Tippen daneben oder Escape schließt die Schublade – wie im angemeldeten Wiki.
  document.addEventListener("pointerdown", (e) => {
    if (side.classList.contains("open") && !side.contains(e.target) && !e.target.closest("#wiki-menu")) side.classList.remove("open");
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") side.classList.remove("open"); });
  /* Suchfeld der Startseite: /stroemipedia?suche=<Begriff> – wie in wiki.js (sucheAusAdresse): unter 1024 px ins Feld
     der Suchzeile, deren Liste dann aufgeht (bis zum 02.11.2026 öffnete sich dafür die Schublade). */
  function sucheAusAdresse() {
    const q = new URLSearchParams(location.search).get("suche");
    if (q === null || !searchInput) return;
    history.replaceState(history.state, "", location.pathname + location.hash);
    if (!q.trim()) return;
    if (zeileSteht()) {
      zeilenSuche.feld.value = q.trim();
      zeilenSuche.feld.dispatchEvent(new Event("input"));
      return;
    }
    searchInput.value = q.trim();
    if (getComputedStyle(side).position === "fixed") side.classList.add("open");
    searchInput.dispatchEvent(new Event("input"));
  }
  Promise.resolve(show(shell.dataset.slug || slugAusPfad())).then(sucheAusAdresse);
})();
