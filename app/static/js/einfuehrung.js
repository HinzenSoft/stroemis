/* Interaktive Einführung je Modul (Wunsch des Nutzers vom 28.10.2026, Entscheidungen vom 03.11.2026; Bauvorlage
   planung/tutorial/entwurf.md, Server app/einfuehrung.py, README „Einführungen (Übungen je Modul)“).

   Läuft auf jeder Seite mit Konto – nach common.js und vor den Skripten der Seite (base.html):
   - Ohne Übung räumt es Übungsreste aus der Ablage dieses Reiters und zeigt auf Seiten eines Moduls das Angebot
     (schwebende Karte unten rechts, am Telefon als Leiste unten; nicht modal, erst nach offenen Dialogen).
   - Im Übungsmodus (?uebung=<teil>, vom Server bestätigt: STROEMIS.einfuehrung.uebung) legt es eine Schicht um alle
     Wege, auf denen die Seite Daten holt oder schreibt (fetch, XMLHttpRequest, sendBeacon, window.open, Datei-Links,
     GET-Formulare, Verlauf): Anfragen an /api/ und /media/ beantwortet die Übungsdatei des Moduls
     (app/static/js/uebung/<modul>.js) aus ihrem Übungsbestand – ans Netz gehen nur der Merker (/api/einfuehrung/…),
     GET /api/me und /static/, mit der Kopfzeile „X-Uebung: 1“; der Server sperrt alles andere ein zweites Mal.
     Dazu die Führung: ein Rahmen um das Ziel, eine Sprechblase daneben (am Telefon als Leiste unten), Schritt für
     Schritt durch die Abläufe des Teils bis zum Dialog „Geschafft“.

   Schnittstelle für die Übungsdateien:
     S.einfuehrung.modul("material", {
       bestand: () => ({ … }),          Übungsbestand (frisch je Ablauf), nur Platzhalter „Übung“, Kennungen ab 900000001
       antworten: [[methode, muster, (treffer, body, z, url) => antwort], …]
                                         methode "GET" … oder "*"; muster RegExp (auf den Pfad) oder genauer Pfad;
                                         antwort: Objekt (JSON 200), {status, error} (Fehler), {datei: "/static/…"}
                                         (Datei), eine Response – auch als Promise. z ist der Übungsbestand; was die
                                         Antwort darin ändert, bleibt bis zum Ende des Ablaufs (sessionStorage).
       dateien: [[RegExp, "/static/uebung/…"], …]   Datei-Adressen (Pfad), die in der Übung eine Übungsdatei öffnen
       teile: { grund: { ablaeufe: [{ titel, start, schritte: [schritt, …] }, …] }, … } });
   Ein Schritt: ziel (Selektor, Funktion → Element, oder null = Blase mittig ohne Rahmen), text (reiner Text), warten
   (fehlt → „Weiter“; {klick: sel} | {wert: [sel, RegExp]} | {anfrage: "METHODE /pfad" oder RegExp} | {da: sel} |
   {bedingung: (z) => bool}), wenn (() => bool: Schritt nur, wenn zutreffend), datei ({input: sel, bild:
   "/static/uebung/…"} – Knopf „Übungsbild nehmen“), probe (nur für den Durchlauftest: {klick: sel} | {tippen: [sel,
   text]} | {datei: true}).
   Testschnittstelle (nur lesend): S.einfuehrung.zustand(), S.einfuehrung.teile(modul). */
(function () {
  const S = window.S;
  const E = (window.STROEMIS && window.STROEMIS.einfuehrung) || null;
  const UEBUNG = E && E.uebung ? E.uebung : null;
  const ZUSTAND = "stroemis-uebung";          // Übungszustand dieses Reiters: {modul, teil, ablauf, schritt, z}
  const RUHE = "stroemis-uebung-ruhe";        // Module, deren Angebot in diesem Reiter schweigt (nach Ende/Unterbrechen)
  const KENNUNG = /\b9[0-3]\d{7}\b/;          // Kennungen des Übungsbestands (Bauvorlage 2.2)
  const echtFetch = window.fetch.bind(window);
  const echtOpen = window.open.bind(window);
  const esc = S.esc;
  const registriert = {};                     // Modul → Übungsdatei

  /* --- Ablage ------------------------------------------------------------------------------------------------------ */
  const sitzung = {
    lesen(k) { try { return JSON.parse(sessionStorage.getItem(k) || "null"); } catch (e) { return null; } },
    schreiben(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* kein Speicher */ } },
    weg(k) { try { sessionStorage.removeItem(k); } catch (e) { /* kein Speicher */ } },
  };
  /* Übungsreste weg: jeder Schlüssel, dessen Name eine Übungs-Kennung trägt (Prüfentwurf, Entwurf der Strömipedia,
     Ansicht der Riegenkarten), die Werte nur bei den Schlüsseln der Riegenkarten („pruef:“, die Stoppuhr nennt ihren
     Lehrgang im Wert) – ein echter Entwurf mit einer neunstelligen Zahl im Text bleibt. Dazu der Übungszustand. */
  function ablageAufraeumen() {
    for (const speicher of [window.localStorage, window.sessionStorage]) {
      try {
        const weg = [];
        for (let i = 0; i < speicher.length; i++) {
          const k = speicher.key(i);
          if (!k) continue;
          if (k === ZUSTAND || KENNUNG.test(k) || (k.startsWith("pruef:") && KENNUNG.test(speicher.getItem(k) || ""))) weg.push(k);
        }
        weg.forEach((k) => speicher.removeItem(k));
      } catch (e) { /* kein Speicher (privater Modus, abgeschaltet) */ }
    }
  }
  const ruhe = () => sitzung.lesen(RUHE) || [];
  function ruhig(modul) { const r = ruhe(); if (!r.includes(modul)) sitzung.schreiben(RUHE, r.concat(modul)); }

  /* Merker auf dem Server (PUT /api/einfuehrung/<modul>/<teil>) – auch wenn die Seite gleich geht (keepalive). */
  async function merken(modul, teil, zustand, ablauf) {
    try {
      await S.api(`/api/einfuehrung/${encodeURIComponent(modul)}/${encodeURIComponent(teil)}`,
        { method: "PUT", body: { zustand, ablauf: ablauf || 0 }, keepalive: true });
      return true;
    } catch (e) {
      return false;
    }
  }

  /* --- Adressen ---------------------------------------------------------------------------------------------------- */
  // Eine Datei statt einer Seite – dieselbe Regel wie der Service Worker (sw.js) und die Sperre des Servers.
  function istDatei(u) {
    if (!u) return false;
    const p = u.pathname;
    return /^\/(api|media)\//.test(p) || /\.[A-Za-z0-9]{1,8}$/.test(p.slice(p.lastIndexOf("/") + 1))
      || /\/(pdf|sammelprotokoll)$/.test(p);
  }
  const adresse = (url) => { try { return new URL(String(url), location.href); } catch (e) { return null; } };

  /* --- Übungsdateien ----------------------------------------------------------------------------------------------- */
  const sicher = (f, ...a) => { try { return f(...a); } catch (e) { return false; } };
  const alsText = (v) => (typeof v === "function" ? "(Funktion)" : v instanceof RegExp ? String(v)
    : Array.isArray(v) ? v.map(alsText) : v);
  function beschreiben(def) {
    const out = {};
    for (const [k, teil] of Object.entries((def && def.teile) || {})) {
      out[k] = { ablaeufe: (teil.ablaeufe || []).map((a) => ({ titel: a.titel, start: a.start || "",
        schritte: (a.schritte || []).map((s) => ({
          ziel: s.ziel === undefined || s.ziel === null ? null : alsText(s.ziel), text: s.text || "",
          warten: s.warten ? Object.fromEntries(Object.entries(s.warten).map(([w, v]) => [w, alsText(v)])) : null,
          wenn: s.wenn ? Boolean(sicher(s.wenn)) : null, datei: s.datei || null, probe: s.probe || null })) })) };
    }
    return out;
  }

  let DEF = null;                 // Übungsdatei des Moduls, in dem geübt wird
  let zustand = null;             // {modul, teil, ablauf, schritt, z}
  let umgeleitet = false;         // die Seite führt gleich zum Start des Ablaufs – keine Führung hier
  const beantwortet = [];         // „METHODE /pfad“ seit dem Laden der Seite
  const unbekannt = [];           // ohne Antwort in der Übungsdatei
  const fuehrung = { bereit: false, geschafft: false, sackgasse: false, ziel: null };

  /* --- Ohne Übung -------------------------------------------------------------------------------------------------- */
  if (!UEBUNG) {
    // Wer aus einer Übung herauskommt (Kopfleiste, Zurück), landet auf einer echten Seite: der Zustand dieses Reiters und
    // die Übungsreste gehen still, der Merker steht schon auf „unterbrochen“.
    if (sitzung.lesen(ZUSTAND)) ablageAufraeumen();
    // Eine Adresse mit „uebung=“, die der Server nicht als Übung zeichnet (Teil gilt nicht für das Konto, Seite ohne
    // Übung): Die Kennung kommt aus der Adresse, bevor die Seite Anfragen stellt – der Server sperrte sie sonst.
    const hier = new URL(location.href);
    if (hier.searchParams.has("uebung") || hier.searchParams.has("ablauf")) {
      hier.searchParams.delete("uebung");
      hier.searchParams.delete("ablauf");
      history.replaceState(history.state, "", hier.pathname + hier.search + hier.hash);
    }
  }

  const rechteck = (el) => {
    if (!el || !el.isConnected || !el.getClientRects().length) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
  };
  window.S.einfuehrung = {
    modul(name, def) {
      registriert[name] = def;
      if (UEBUNG && E && name === E.modul && !DEF) { DEF = def; starten(); }
    },
    zustand() {
      const a = zustand && DEF && DEF.teile && DEF.teile[zustand.teil] ? DEF.teile[zustand.teil].ablaeufe[zustand.ablauf] : null;
      const s = a && a.schritte ? a.schritte[zustand.schritt] : null;
      return { modul: E && E.modul, teil: UEBUNG, ablauf: zustand ? zustand.ablauf : null, schritt: zustand ? zustand.schritt : null,
               schrittzahl: a && a.schritte ? a.schritte.length : 0, ablaeufe: UEBUNG && DEF && DEF.teile && DEF.teile[UEBUNG]
                 ? DEF.teile[UEBUNG].ablaeufe.length : 0,
               ziel: s && s.ziel !== undefined && s.ziel !== null ? alsText(s.ziel) : null, bereit: fuehrung.bereit,
               geschafft: fuehrung.geschafft, sackgasse: fuehrung.sackgasse, umgeleitet,
               unbekannt: unbekannt.slice(), beantwortet: beantwortet.slice(),
               zielRect: rechteck(zielEl), blaseRect: blase && !blase.hidden ? rechteck(blase) : null,
               leiste: Boolean(blase && blase.classList.contains("als-leiste")) };
    },
    teile(modul) { return beschreiben(registriert[modul || (E && E.modul)]); },
  };

  /* ================================================================================================================
     Schicht (nur im Übungsmodus, Bauvorlage 2.3)
     ================================================================================================================ */
  // Was ans Netz darf – mit X-Uebung: 1 (der Server lässt genau das durch).
  const ausnahme = (pfad, methode) => pfad.startsWith("/api/einfuehrung/") || pfad.startsWith("/static/")
    || (pfad === "/api/me" && (methode === "GET" || methode === "HEAD"));
  const antwortJson = (status, daten) => new Response(JSON.stringify(daten === undefined ? {} : daten),
    { status, headers: { "Content-Type": "application/json" } });
  function dateiFuer(u) {
    if (!u || u.origin !== location.origin || !DEF) return null;
    const treffer = (DEF.dateien || []).find(([muster]) => muster.test(u.pathname));
    return treffer ? treffer[1] : null;
  }
  function bodyLesen(body) {
    if (typeof body !== "string") return body;
    try { return JSON.parse(body); } catch (e) { return body; }
  }
  // Eine Anfrage aus der Antworttabelle beantworten – roh (Objekt, {status, error}, {datei}, Response).
  async function beantworten(methode, u, body) {
    const pfad = u.pathname;
    const schluessel = `${methode} ${pfad}`;
    for (const [m, muster, fn] of (DEF && DEF.antworten) || []) {
      if (m !== "*" && m !== methode) continue;
      const treffer = typeof muster === "string" ? (muster === pfad ? [pfad] : null) : pfad.match(muster);
      if (!treffer) continue;
      let r;
      try {
        r = await fn(treffer, bodyLesen(body), zustand ? zustand.z : {}, u);
      } catch (e) {
        console.error("Übung: Antwort auf", schluessel, e);
        r = { status: 500, error: "Die Übung kennt diese Antwort nicht." };
      }
      speichern();
      beantwortet.push(schluessel);
      nachAnfrage(schluessel);
      return r;
    }
    const datei = (methode === "GET" || methode === "HEAD") ? dateiFuer(u) : null;
    if (datei) { beantwortet.push(schluessel); nachAnfrage(schluessel); return { datei }; }
    unbekannt.push(schluessel);
    return { status: 403, error: "In der Übung nicht verfügbar." };
  }
  async function alsAntwort(r, methode) {
    if (r instanceof Response) return r;
    if (r && typeof r === "object" && typeof r.datei === "string" && Object.keys(r).length === 1) {
      if (!r.datei.startsWith("/static/")) return antwortJson(403, { error: "In der Übung nicht verfügbar." });
      if (methode === "HEAD") return new Response(null, { status: 200 });
      return echtFetch(r.datei, { credentials: "same-origin", headers: { "X-Uebung": "1" } });
    }
    if (r && typeof r === "object" && typeof r.status === "number" && typeof r.error === "string") {
      return antwortJson(r.status, { error: r.error });
    }
    return antwortJson(200, r);
  }

  /* XMLHttpRequest der Übung: Uploads (Ankerplätze, Strömipedia, Riegenkarten) und der Katalogimport laufen gegen die
     Antworttabelle, der Fortschritt kommt in vier Stufen bis 100 %. Dateien bleiben im Browser. */
  function feuern(ziel, typ, init) {
    const ev = init ? new ProgressEvent(typ, init) : new Event(typ);
    const h = ziel[`on${typ}`];
    if (typeof h === "function") h.call(ziel, ev);
    ziel.dispatchEvent(ev);
  }
  const pause = (ms) => new Promise((r) => setTimeout(r, ms));
  function groesse(body) {
    if (!body) return 0;
    if (typeof body === "string") return body.length;
    if (body instanceof Blob) return body.size;
    if (body instanceof FormData) {
      let n = 0;
      for (const [, v] of body.entries()) n += v instanceof Blob ? v.size : String(v).length;
      return n;
    }
    return 0;
  }
  class UebungXHR extends EventTarget {
    constructor() {
      super();
      Object.assign(this, { readyState: 0, status: 0, statusText: "", response: null, responseText: "", responseType: "",
        responseURL: "", timeout: 0, withCredentials: false, upload: new EventTarget(), weg: false, typ: null });
    }
    open(methode, url) {
      this.methode = String(methode || "GET").toUpperCase();
      this.url = adresse(url);
      this.zustandSetzen(1);
    }
    setRequestHeader() { /* die Übung braucht keine Kopfzeilen */ }
    overrideMimeType() { /* egal */ }
    getResponseHeader(k) { return String(k).toLowerCase() === "content-type" ? this.typ : null; }
    getAllResponseHeaders() { return this.typ ? `content-type: ${this.typ}\r\n` : ""; }
    zustandSetzen(n) { this.readyState = n; feuern(this, "readystatechange"); }
    abort() {
      if (this.weg) return;
      this.weg = true;
      this.zustandSetzen(4);
      feuern(this, "abort", { lengthComputable: false, loaded: 0, total: 0 });
      feuern(this, "loadend", { lengthComputable: false, loaded: 0, total: 0 });
      this.readyState = 0;
    }
    send(body) { this.lauf(body); }
    async lauf(body) {
      const gesamt = Math.max(1, groesse(body));
      feuern(this, "loadstart", { lengthComputable: false, loaded: 0, total: 0 });
      feuern(this.upload, "loadstart", { lengthComputable: true, loaded: 0, total: gesamt });
      for (const anteil of [0.25, 0.5, 0.75, 1]) {
        await pause(80);
        if (this.weg) return;
        feuern(this.upload, "progress", { lengthComputable: true, loaded: Math.round(gesamt * anteil), total: gesamt });
      }
      feuern(this.upload, "load", { lengthComputable: true, loaded: gesamt, total: gesamt });
      feuern(this.upload, "loadend", { lengthComputable: true, loaded: gesamt, total: gesamt });
      const u = this.url;
      let res;
      if (u && u.origin === location.origin && ausnahme(u.pathname, this.methode)) {
        res = await echtFetch(u.href, { method: this.methode, body, credentials: "same-origin",
          headers: { "X-Uebung": "1", "X-Requested-With": "XMLHttpRequest" } });
      } else if (u && u.origin === location.origin) {
        res = await alsAntwort(await beantworten(this.methode, u, body), this.methode);
      } else {
        res = antwortJson(403, { error: "In der Übung nicht verfügbar." });
      }
      if (this.weg) return;
      const text = await res.text();
      this.status = res.status;
      this.statusText = res.statusText || "";
      this.typ = res.headers.get("Content-Type");
      this.responseURL = u ? u.href : "";
      this.zustandSetzen(2);
      this.zustandSetzen(3);
      if (this.responseType === "json") { try { this.response = JSON.parse(text); } catch (e) { this.response = null; } }
      else if (this.responseType === "blob") this.response = new Blob([text], { type: this.typ || "" });
      else { this.responseText = text; this.response = text; }
      this.zustandSetzen(4);
      feuern(this, "load", { lengthComputable: true, loaded: text.length, total: text.length });
      feuern(this, "loadend", { lengthComputable: true, loaded: text.length, total: text.length });
    }
  }
  Object.assign(UebungXHR, { UNSENT: 0, OPENED: 1, HEADERS_RECEIVED: 2, LOADING: 3, DONE: 4 });

  function schichtEinschalten() {
    window.fetch = async function (eingabe, init) {
      const opt = init || {};
      const anfrage = typeof Request !== "undefined" && eingabe instanceof Request ? eingabe : null;
      const u = adresse(anfrage ? anfrage.url : eingabe);
      const methode = String(opt.method || (anfrage ? anfrage.method : "GET")).toUpperCase();
      if (!u || u.origin !== location.origin) return antwortJson(403, { error: "In der Übung nicht verfügbar." });
      if (ausnahme(u.pathname, methode)) {
        const kopf = new Headers(opt.headers || (anfrage ? anfrage.headers : undefined));
        kopf.set("X-Uebung", "1");
        return echtFetch(eingabe, Object.assign({}, opt, { headers: kopf }));
      }
      await Promise.resolve();
      return alsAntwort(await beantworten(methode, u, opt.body), methode);
    };
    window.XMLHttpRequest = UebungXHR;
    try { Object.defineProperty(navigator, "sendBeacon", { value: () => true, configurable: true }); }
    catch (e) { /* ältere Browser */ }
    window.open = function (url, ...rest) {
      const u = adresse(url || "about:blank");
      if (u && /^https?:$/.test(u.protocol) && u.origin !== location.origin) return echtOpen(url, ...rest);   // fremde Seite
      const datei = dateiFuer(u);
      if (datei) return echtOpen(datei, "_blank", "noopener");
      S.toast(istDatei(u) ? "In der Übung gibt es diese Datei nicht." : "In der Übung nicht verfügbar.");
      return null;
    };
    // Links: Dateien öffnen die Übungsdatei (oder melden, dass es sie nicht gibt); Seiten desselben Moduls behalten die
    // Kennung. Die Kopfleiste führt aus der Übung hinaus, ein neuer Reiter (target) öffnet die echte Seite.
    document.addEventListener("click", (e) => {
      if (e.button !== 0) return;
      const a = e.target.closest && e.target.closest("a[href]");
      if (!a || a.closest("header.bauchbinde, .fuehrung-blase, .einfuehrung-angebot")) return;
      const roh = a.getAttribute("href") || "";
      if (!roh || roh.startsWith("#") || /^(javascript|mailto|tel|blob|data):/i.test(roh)) return;
      const u = adresse(a.href);
      if (!u || u.origin !== location.origin) return;
      if (istDatei(u) || a.hasAttribute("download")) {
        e.preventDefault();
        const datei = dateiFuer(u);
        if (datei) echtOpen(datei, "_blank", "noopener");
        else S.toast("In der Übung gibt es diese Datei nicht.");
        return;
      }
      if (a.target && a.target !== "_self") return;
      const neu = S.ziel(u.href);
      if (neu !== u.href) a.setAttribute("href", neu);
    }, true);
    // GET-Formulare des Moduls (Nummernsuche der Materialablage): die Kennung als verstecktes Feld.
    document.addEventListener("submit", (e) => {
      const f = e.target;
      if (!(f instanceof HTMLFormElement) || (f.getAttribute("method") || "get").toLowerCase() !== "get") return;
      const u = adresse(f.action || location.href);
      if (!u || S.ziel(u.href) === u.href || f.querySelector("input[name=uebung]")) return;
      const feld = document.createElement("input");
      Object.assign(feld, { type: "hidden", name: "uebung", value: UEBUNG });
      f.appendChild(feld);
    }, true);
    // Verlauf: Adressen, die die Seite selbst schreibt (Strömipedia, Filter, Reiter), behalten die Kennung.
    for (const art of ["pushState", "replaceState"]) {
      const vorher = history[art];
      history[art] = function (state, titel, url) {
        return vorher.call(history, state, titel, url === undefined || url === null ? url : S.ziel(String(url)));
      };
    }
    // Seitentitel mit Vorsatz „Übung · “ – auch, wenn die Seite ihn später selbst setzt (S.titel).
    const titelSetzen = () => { if (!document.title.startsWith("Übung · ")) document.title = `Übung · ${document.title}`; };
    const t = document.querySelector("title");
    if (t) new MutationObserver(titelSetzen).observe(t, { childList: true, characterData: true, subtree: true });
    titelSetzen();
  }

  /* ================================================================================================================
     Führung (Bauvorlage 2.7)
     ================================================================================================================ */
  const teilDef = () => (DEF && DEF.teile && DEF.teile[UEBUNG]) || null;
  const ablaufDef = () => { const t = teilDef(); return t && zustand ? t.ablaeufe[zustand.ablauf] || null : null; };
  function speichern() { if (zustand) sitzung.schreiben(ZUSTAND, zustand); }
  function frischerBestand() { return DEF && typeof DEF.bestand === "function" ? JSON.parse(JSON.stringify(DEF.bestand() || {})) : {}; }
  function neuerAblauf(n) {
    ablageAufraeumen();
    zustand = { modul: E.modul, teil: UEBUNG, ablauf: n, schritt: 0, z: frischerBestand() };
    speichern();
    merken(E.modul, UEBUNG, "unterbrochen", n);
  }
  // Steht die Seite schon an der Startadresse des Ablaufs? (Pfad und Abfrage ohne Kennung; der Anker zählt nicht.)
  function ohneKennung(u) {
    const k = new URL(u.href);
    k.searchParams.delete("uebung");
    k.searchParams.delete("ablauf");
    return k.pathname + k.search;
  }
  function zumStart(start, ersetzen) {
    const u = adresse(start || E.start);
    if (!u) return false;
    const hier = new URL(location.href);
    if (ohneKennung(u) === ohneKennung(hier)) {
      if (u.hash !== hier.hash) history.replaceState(history.state, "", S.ziel(u.pathname + hier.search + u.hash));
      return false;
    }
    umgeleitet = true;
    if (ersetzen) location.replace(S.ziel(u.href)); else location.href = S.ziel(u.href);
    return true;
  }

  function starten() {
    const hier = new URL(location.href);
    const param = hier.searchParams.has("ablauf") ? parseInt(hier.searchParams.get("ablauf"), 10) : null;
    const t = teilDef();
    const alt = sitzung.lesen(ZUSTAND);
    if (param !== null) {
      hier.searchParams.delete("ablauf");
      history.replaceState(history.state, "", hier.pathname + hier.search + hier.hash);
    }
    if (!t || !Array.isArray(t.ablaeufe) || !t.ablaeufe.length) {
      zustand = { modul: E.modul, teil: UEBUNG, ablauf: 0, schritt: 0, z: frischerBestand() };
      return;
    }
    if (param !== null || !alt || alt.modul !== E.modul || alt.teil !== UEBUNG || !t.ablaeufe[alt.ablauf]) {
      const n = Math.max(0, Math.min(Number.isFinite(param) ? param : 0, t.ablaeufe.length - 1));
      neuerAblauf(n);
      zumStart(t.ablaeufe[n].start, true);
      return;
    }
    zustand = alt;
  }

  let blase = null;
  let rahmen = null;
  let zielEl = null;
  let laufNr = 0;                       // jede Anzeige eines Schritts; ältere Wartende geben auf
  let aufraeumen = [];                  // Wächter des gezeigten Schritts
  let planung = 0;

  function sichtbar(el) {
    if (!el || !el.isConnected || !el.getClientRects().length) return false;
    if (el.closest(".fuehrung-blase, .fuehrung-rahmen")) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && !el.closest("[hidden], [inert]");
  }
  function zielSuchen(z) {
    if (z === null || z === undefined) return null;
    if (typeof z === "function") { const el = sicher(z); return el instanceof Element && sichtbar(el) ? el : null; }
    try {
      for (const el of document.querySelectorAll(z)) if (sichtbar(el)) return el;
    } catch (e) { /* ungültiger Selektor */ }
    return null;
  }
  // Wartet, bis pruefen() etwas liefert (Änderungen am Dokument, dazu ein Takt für Größen und Stile) – höchstens ms.
  function warteAuf(pruefen, ms) {
    return new Promise((fertig) => {
      const sofort = pruefen();
      if (sofort) { fertig(sofort); return; }
      let aus = null;
      const versuch = () => { const r = pruefen(); if (r) { aus(); fertig(r); } };
      const mo = new MutationObserver(versuch);
      mo.observe(document.documentElement, { childList: true, subtree: true, attributes: true });
      const takt = setInterval(versuch, 250);
      const ende = ms === Infinity ? null : setTimeout(() => { aus(); fertig(null); }, ms);
      aus = () => { mo.disconnect(); clearInterval(takt); if (ende) clearTimeout(ende); };
      aufraeumen.push(aus);
    });
  }

  /* Wohin Blase und Rahmen gehören: in den obersten offenen modalen Dialog (außerhalb wären sie inert), sonst ans Ende
     der Seite. */
  function behaelter() {
    const offen = [...document.querySelectorAll("dialog[open]")].filter((d) => sicher(() => d.matches(":modal")));
    return offen.length ? offen[offen.length - 1] : document.body;
  }
  function einhaengen() {
    const b = behaelter();
    for (const el of [rahmen, blase]) if (el && el.parentElement !== b) b.appendChild(el);
  }
  const schmal = () => window.innerWidth < 600;
  function lage() {
    planung = 0;
    if (!blase) return;
    if (blase.hidden) { rahmen.hidden = true; return; }        // Rückfrage „Übung unterbrechen?“ offen
    einhaengen();
    const wurzel = document.documentElement;
    const leiste = schmal();
    blase.classList.toggle("als-leiste", leiste);
    wurzel.classList.toggle("fuehrung-leiste", leiste);
    if (leiste) wurzel.style.setProperty("--fuehrung-hoehe", `${Math.ceil(blase.offsetHeight)}px`);
    else wurzel.style.removeProperty("--fuehrung-hoehe");
    // Zeichnet die Seite neu, ist das Ziel ein neues Element – dann wieder suchen.
    const s = aktuellerSchritt();
    if (s && s.ziel !== null && s.ziel !== undefined && !sichtbar(zielEl)) {
      const neu = zielSuchen(s.ziel);
      if (neu) zielBeschreiben(neu);
    }
    // Steht die Blase in einem Dialog, das Ziel aber dahinter (inert), bleibt der Dialog ohne Abdunkelung.
    const imDialog = blase.parentElement !== document.body;
    const r = zielEl && sichtbar(zielEl) && (!imDialog || blase.parentElement.contains(zielEl)) ? zielEl.getBoundingClientRect() : null;
    rahmen.hidden = !r;
    if (r) {
      Object.assign(rahmen.style, { left: `${Math.round(r.left - 4)}px`, top: `${Math.round(r.top - 4)}px`,
        width: `${Math.round(r.width + 8)}px`, height: `${Math.round(r.height + 8)}px` });
    }
    if (leiste) { blase.style.left = ""; blase.style.top = ""; return; }
    const vw = wurzel.clientWidth;
    const vh = window.innerHeight;
    const w = blase.offsetWidth;
    const h = blase.offsetHeight;
    let left = (vw - w) / 2;
    let top = (vh - h) / 2;
    // Ohne sichtbares Ziel in einem Dialog: neben den Dialog statt über seinen Inhalt.
    const anker = r || (imDialog ? blase.parentElement.getBoundingClientRect() : null);
    if (anker && !r) {
      top = anker.bottom + 12;
      if (top + h > vh - 8) top = anker.top - 12 - h;
      if (top < 8) top = Math.max(8, vh - h - 8);
    } else if (r) {
      top = r.bottom + 12;                                   // unter dem Ziel …
      if (top + h > vh - 8) top = r.top - 12 - h;            // … sonst darüber …
      if (top < 8) top = Math.max(8, vh - h - 8);            // … sonst unten im Fenster
      left = Math.min(Math.max(8, r.left), vw - w - 8);
    }
    blase.style.left = `${Math.round(Math.max(8, left))}px`;
    blase.style.top = `${Math.round(Math.max(8, top))}px`;
  }
  const lagePlanen = () => { if (!planung) planung = requestAnimationFrame(lage); };

  function aktuellerSchritt() {
    const a = ablaufDef();
    return a && zustand && a.schritte ? a.schritte[zustand.schritt] || null : null;
  }
  // „Schritt n von m“ über den ganzen Teil; Schritte, die gerade nicht zutreffen (wenn), zählen nicht.
  function zaehlung() {
    const t = teilDef();
    let n = 0;
    let m = 0;
    t.ablaeufe.forEach((a, i) => (a.schritte || []).forEach((s, j) => {
      if (s.wenn && !sicher(s.wenn)) return;
      m += 1;
      if (i < zustand.ablauf || (i === zustand.ablauf && j <= zustand.schritt)) n += 1;
    }));
    return { n: Math.max(1, n), m: Math.max(1, m) };
  }

  function zielBeschreiben(el) {
    if (zielEl && zielEl !== el) zielLoesen();
    zielEl = el;
    if (!el) return;
    const alt = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (!alt.includes("fuehrung-text")) {
      el.dataset.fuehrungBeschrieben = "1";
      el.setAttribute("aria-describedby", alt.concat("fuehrung-text").join(" "));
    }
  }
  function zielLoesen() {
    if (!zielEl) return;
    if (zielEl.dataset.fuehrungBeschrieben) {
      const rest = (zielEl.getAttribute("aria-describedby") || "").split(/\s+/).filter((x) => x && x !== "fuehrung-text");
      if (rest.length) zielEl.setAttribute("aria-describedby", rest.join(" ")); else zielEl.removeAttribute("aria-describedby");
      delete zielEl.dataset.fuehrungBeschrieben;
    }
    zielEl = null;
  }

  function blaseBauen() {
    if (blase) return;
    rahmen = document.createElement("div");
    rahmen.className = "fuehrung-rahmen";
    rahmen.hidden = true;
    rahmen.setAttribute("aria-hidden", "true");
    blase = document.createElement("div");
    blase.className = "fuehrung-blase";
    blase.id = "fuehrung-blase";
    blase.setAttribute("role", "dialog");
    blase.setAttribute("aria-modal", "false");
    blase.setAttribute("aria-labelledby", "fuehrung-titel");
    blase.setAttribute("aria-describedby", "fuehrung-text");
    document.body.append(rahmen, blase);
    window.addEventListener("scroll", lagePlanen, { capture: true, passive: true });
    window.addEventListener("resize", lagePlanen);
    if (window.visualViewport) window.visualViewport.addEventListener("resize", lagePlanen);
    new MutationObserver(lagePlanen).observe(document.documentElement,
      { subtree: true, childList: true, attributes: true, attributeFilter: ["open", "class", "hidden", "style"] });
    setInterval(lagePlanen, 400);
  }

  /* Die Blase zeichnen. knoepfe: [{text, klasse, aktion}] rechts, dazu immer „Übung unterbrechen“ als Textknopf. */
  function blaseZeigen(kopf, titel, text, knoepfe) {
    blaseBauen();
    blase.innerHTML = `<p class="fuehrung-kopf">${esc(kopf)}</p>
      <p class="fuehrung-titel" id="fuehrung-titel">${esc(titel)}</p>
      <p class="fuehrung-text" id="fuehrung-text" tabindex="-1">${esc(text)}</p>
      <div class="fuehrung-knoepfe"><button type="button" class="lnk fuehrung-unterbrechen">Übung unterbrechen</button>
        ${knoepfe.map((k, i) => `<button type="button" class="${k.klasse}" data-k="${i}">${esc(k.text)}</button>`).join("")}</div>`;
    blase.querySelector(".fuehrung-unterbrechen").addEventListener("click", () => unterbrechen());
    blase.querySelectorAll("[data-k]").forEach((b) => b.addEventListener("click", () => knoepfe[+b.dataset.k].aktion(b)));
    lage();
  }

  function schrittVerlassen() {
    laufNr += 1;
    aufraeumen.splice(0).forEach((f) => sicher(f));
    zielLoesen();
    fuehrung.bereit = false;
  }

  async function schrittZeigen() {
    schrittVerlassen();
    const lauf = laufNr;
    const a = ablaufDef();
    if (!a) { sackgasse("Diese Übung gibt es hier noch nicht."); return; }
    const liste = a.schritte || [];
    while (zustand.schritt < liste.length && liste[zustand.schritt].wenn && !sicher(liste[zustand.schritt].wenn)) zustand.schritt += 1;
    speichern();
    if (zustand.schritt >= liste.length) { ablaufFertig(); return; }
    const s = liste[zustand.schritt];
    fuehrung.ziel = s.ziel === null || s.ziel === undefined ? null : alsText(s.ziel);
    let el = null;
    if (s.ziel !== null && s.ziel !== undefined) {
      el = await warteAuf(() => zielSuchen(s.ziel), 5000);
      if (lauf !== laufNr) return;
      if (!el) { sackgasse("Hier geht es in der Übung nicht weiter."); return; }
    }
    zielBeschreiben(el);
    const { n, m } = zaehlung();
    const knoepfe = [];
    const vorige = liste.slice(0, zustand.schritt).filter((x) => !x.wenn || sicher(x.wenn));
    if (vorige.length && !vorige[vorige.length - 1].warten) knoepfe.push({ text: "Zurück", klasse: "btn secondary", aktion: zurueck });
    if (s.datei) knoepfe.push({ text: "Übungsbild nehmen", klasse: "btn secondary fuehrung-bild", aktion: () => bildNehmen(s.datei) });
    if (!s.warten) knoepfe.push({ text: "Weiter", klasse: "btn fuehrung-weiter", aktion: () => weiter() });
    blaseZeigen(`Übung · Schritt ${n} von ${m}`, a.titel || "", s.text || "", knoepfe);
    if (el) {
      const r = el.getBoundingClientRect();
      const unten = window.innerHeight - (schmal() ? blase.offsetHeight : 0);
      if (r.top < 0 || r.bottom > unten) el.scrollIntoView({ block: "center", behavior: S.weich() });
    }
    lage();
    wachen(s, lauf);
    // Fokus: ohne Aktion auf „Weiter“, mit Aktion auf das Ziel (wenn fokussierbar), sonst auf den Text.
    const weiterKnopf = blase.querySelector(".fuehrung-weiter");
    if (weiterKnopf) weiterKnopf.focus({ preventScroll: true });
    else if (el && el.matches("a[href], button, input, select, textarea, summary, [tabindex], [contenteditable]") && !el.disabled) el.focus({ preventScroll: true });
    else blase.querySelector(".fuehrung-text").focus({ preventScroll: true });
    fuehrung.bereit = true;
  }

  function wachen(s, lauf) {
    const w = s.warten;
    if (!w) return;
    const fertig = () => { if (lauf === laufNr) weiter(); };
    if (w.klick) {
      const beiKlick = (e) => { if (e.target.closest && e.target.closest(w.klick) && !e.target.closest(".fuehrung-blase")) fertig(); };
      document.addEventListener("click", beiKlick, true);
      aufraeumen.push(() => document.removeEventListener("click", beiKlick, true));
    }
    if (w.wert) {
      const [sel, muster] = w.wert;
      const beiEingabe = (e) => {
        const el = e.target instanceof Element ? (e.target.matches(sel) ? e.target : e.target.closest(sel)) : null;
        if (!el) return;
        const wert = typeof el.value === "string" ? el.value : el.textContent;
        if ((muster instanceof RegExp ? muster : new RegExp(muster)).test(wert || "")) fertig();
      };
      document.addEventListener("input", beiEingabe, true);
      document.addEventListener("change", beiEingabe, true);
      aufraeumen.push(() => { document.removeEventListener("input", beiEingabe, true); document.removeEventListener("change", beiEingabe, true); });
    }
    if (w.anfrage) {
      const passt = (k) => (w.anfrage instanceof RegExp ? w.anfrage.test(k) : k === w.anfrage);
      wartendeAnfrage = (k) => { if (passt(k)) fertig(); };
      aufraeumen.push(() => { wartendeAnfrage = null; });
    }
    if (w.da) warteAuf(() => zielSuchen(w.da), Infinity).then((el) => { if (el) fertig(); });
    if (w.bedingung) warteAuf(() => sicher(w.bedingung, zustand.z), Infinity).then((ok) => { if (ok) fertig(); });
  }
  let wartendeAnfrage = null;
  function nachAnfrage(schluessel) { if (wartendeAnfrage) setTimeout(() => wartendeAnfrage && wartendeAnfrage(schluessel), 0); }

  /* Weiter: Der Schritt zählt sofort weiter (sessionStorage) – führt die Aktion auf eine andere Seite, setzt die neue Seite
     dort fort; sonst zeigt die Blase gleich den nächsten Schritt. */
  function weiter() {
    zustand.schritt += 1;
    speichern();
    schrittVerlassen();
    const lauf = laufNr;
    setTimeout(() => { if (lauf === laufNr) schrittZeigen(); }, 0);
  }
  function zurueck() {
    const liste = ablaufDef().schritte;
    let i = zustand.schritt - 1;
    while (i > 0 && liste[i].wenn && !sicher(liste[i].wenn)) i -= 1;
    zustand.schritt = Math.max(0, i);
    speichern();
    schrittZeigen();
  }

  function sackgasse(text) {
    schrittVerlassen();
    fuehrung.sackgasse = true;
    const a = ablaufDef();
    blaseZeigen("Übung", (a && a.titel) || "Übung", text, [{ text: "Ablauf neu beginnen", klasse: "btn", aktion: neuBeginnen }]);
    blase.querySelector(".btn").focus({ preventScroll: true });
  }
  function neuBeginnen() {
    const t = teilDef();
    const n = zustand ? zustand.ablauf : 0;
    neuerAblauf(n);
    const start = t && t.ablaeufe[n] ? t.ablaeufe[n].start : E.start;
    if (!zumStart(start, false)) location.reload();
  }

  async function bildNehmen(datei) {
    const input = document.querySelector(datei.input);
    if (!input || !String(datei.bild || "").startsWith("/static/uebung/")) return;
    try {
      const res = await echtFetch(datei.bild, { credentials: "same-origin", headers: { "X-Uebung": "1" } });
      const blob = await res.blob();
      const f = new File([blob], datei.bild.split("/").pop(), { type: blob.type || "image/jpeg" });
      const dt = new DataTransfer();
      dt.items.add(f);
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    } catch (e) {
      S.toast("Das Übungsbild ließ sich nicht laden.", true);
    }
  }

  function ablaufFertig() {
    schrittVerlassen();
    const t = teilDef();
    const n = zustand.ablauf + 1;
    if (n < t.ablaeufe.length) {
      neuerAblauf(n);
      if (!zumStart(t.ablaeufe[n].start, false)) schrittZeigen();
      return;
    }
    geschafft();
  }

  function fuehrungWeg() {
    schrittVerlassen();
    for (const el of [blase, rahmen]) if (el) el.remove();
    blase = null;
    rahmen = null;
    document.documentElement.classList.remove("fuehrung-leiste");
    document.documentElement.style.removeProperty("--fuehrung-hoehe");
  }
  /* Raus aus der Übung: Ablage aufräumen, das Angebot schweigt in diesem Reiter, zur Seite ohne Kennung. Schloss gerade
     ein Dialog (Rückfrage, „Geschafft“), nimmt common.js erst seinen Verlaufseintrag zurück (S.dialogVerlauf) – ein
     Seitenwechsel davor würde von diesem Schritt zurück abgebrochen. Also warten, bis der Eintrag weg ist (höchstens 1 s). */
  function verlassen(ziel) {
    ablageAufraeumen();
    sitzung.weg(ZUSTAND);
    ruhig(E.modul);
    umgeleitet = true;
    const ende = Date.now() + 1000;
    const los = () => {
      const st = history.state;
      if (st && typeof st === "object" && typeof st.stroemisOverlay === "number" && Date.now() < ende) { setTimeout(los, 30); return; }
      location.href = ziel || E.start;
    };
    setTimeout(los, 0);
  }
  function unterbrechen() {
    // Der Merker steht schon auf „unterbrochen“ beim laufenden Ablauf (gesetzt beim Start jedes Ablaufs).
    fuehrungWeg();
    verlassen(E.start);
  }

  /* Abschluss (Bauvorlage 2.8): Dialog „Geschafft“, der Merker steht danach auf „erledigt“. */
  async function geschafft() {
    fuehrungWeg();
    fuehrung.geschafft = true;
    await merken(E.modul, UEBUNG, "erledigt", zustand.ablauf);
    const eigen = (E.teile || []).find((x) => x.teil === UEBUNG);
    const naechster = (E.teile || []).find((x) => x.teil !== UEBUNG && (x.zustand === "offen" || x.zustand === "unterbrochen"));
    const anleitung = E.anleitung ? `<p>Alles Weitere steht in der Anleitung in der Strömipedia.</p>
      <p><a href="${esc(E.anleitung)}" target="_blank" rel="noopener">Anleitung in der Strömipedia öffnen</a></p>` : "";
    const knoepfe = naechster
      ? `<button type="button" class="btn secondary" id="fg-spaeter">Später</button>
         <button type="button" class="btn" id="fg-weiter">Weiter mit „${esc(naechster.titel)}“</button>`
      : `<button type="button" class="btn" id="fg-ende">Übung beenden</button>`;
    let wohin = E.start;
    const dlg = S.dialog(`<h2>Geschafft</h2>
      <p>Du hast die Übung „${esc(E.name)} – ${esc(eigen ? eigen.titel : UEBUNG)}“ abgeschlossen. ${esc(E.ist || "")}</p>
      ${anleitung}<div class="dlg-actions">${knoepfe}</div>`, (d, body) => {
      const weiterKnopf = body.querySelector("#fg-weiter");
      if (weiterKnopf) weiterKnopf.addEventListener("click", () => { wohin = naechster.adresse; d.close(); });
      body.querySelectorAll("#fg-spaeter, #fg-ende").forEach((b) => b.addEventListener("click", () => d.close()));
      (weiterKnopf || body.querySelector("#fg-ende")).focus();
    });
    dlg.classList.add("fuehrung-geschafft");
    dlg.addEventListener("close", () => {
      dlg.classList.remove("fuehrung-geschafft");
      verlassen(wohin);
    }, { once: true });
  }

  function fragen() {
    if (!blase) return;
    blase.hidden = true;
    rahmen.hidden = true;
    S.confirm("Übung unterbrechen?", "Unterbrechen", "Weiter üben", { endgueltig: false }).then((ja) => {
      if (ja) { unterbrechen(); return; }
      if (!blase) return;
      blase.hidden = false;
      lage();
      const f = blase.querySelector(".fuehrung-weiter") || blase.querySelector(".fuehrung-text");
      if (f) f.focus({ preventScroll: true });
    });
  }

  if (UEBUNG) {
    schichtEinschalten();
    // Esc (nur ohne offenen Dialog, Menü oder Info – und wenn die Seite die Taste nicht schon behandelt hat) fragt, ob
    // die Übung unterbrochen werden soll. Am window, also nach den Handlern der Seite am document.
    window.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || !blase || blase.hidden) return;
      if (document.querySelector("dialog[open], details.menue[open], .menue-schwebend")) return;
      if ([...document.querySelectorAll(".info-text")].some((t) => !t.hidden)) return;
      e.preventDefault();
      fragen();
    });
    const los = () => {
      if (umgeleitet) return;
      // Der Hinweis „Entwicklungsserver“ (erste Seite nach der Anmeldung auf dev) zuerst – dann die Führung.
      const dev = document.getElementById("dev-hinweis");
      if (dev && dev.open) { dev.addEventListener("close", () => setTimeout(los, 0), { once: true }); return; }
      if (!DEF) {
        zustand = zustand || { modul: E.modul, teil: UEBUNG, ablauf: 0, schritt: 0, z: {} };
        sackgasse("Die Übung ließ sich nicht laden.");
        return;
      }
      schrittZeigen();
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", los, { once: true });
    else setTimeout(los, 0);
  }

  /* ================================================================================================================
     Angebot beim Betreten (Bauvorlage 2.6) – nur auf Seiten eines Moduls ohne Übung
     ================================================================================================================ */
  const liste = (namen) => (namen.length < 2 ? namen.join("") : `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`);
  function angebotText(an) {
    const minuten = an.reduce((n, t) => n + (t.minuten || 0), 0);
    const unterbrochen = an.find((t) => t.zustand === "unterbrochen");
    if (unterbrochen) {
      return { titel: unterbrochen.teil === "grund" ? `Übung ${E.zu} fortsetzen?` : `Übung „${unterbrochen.titel}“ fortsetzen?`,
               text: `Du hast bei „${unterbrochen.ablauf_titel}“ aufgehört (Ablauf ${unterbrochen.ablauf + 1} von ${unterbrochen.ablaeufe}).`,
               knopf: "Übung fortsetzen", start: unterbrochen };
    }
    if (an[0].teil === "grund") {
      const umfang = an.length > 1
        ? `${liste(an.map((t) => (t.teil === "grund" ? "Grundteil" : `Teil „${t.titel}“`)))}, etwa ${minuten} Minuten, jederzeit unterbrechbar.`
        : `Etwa ${minuten} Minuten, jederzeit unterbrechbar.`;
      return { titel: `Kurze Übung ${E.zu}`, text: `Probier die wichtigsten Abläufe an Übungsdaten aus. ${E.bleibt} ${umfang}`,
               knopf: "Übung starten", start: an[0] };
    }
    return { titel: an.length > 1 ? `Neu für dich: Übungen ${liste(an.map((t) => `„${t.titel}“`))}` : `Neu für dich: Übung „${an[0].titel}“`,
             text: `Probier die Abläufe deiner neuen ${an.length > 1 ? "Aufgaben" : "Aufgabe"} an Übungsdaten aus. Etwa ${minuten} Minuten.`,
             knopf: "Übung starten", start: an[0] };
  }
  function angebotZeigen() {
    const an = E.angebot;
    const t = angebotText(an);
    const karte = document.createElement("section");
    karte.className = "einfuehrung-angebot";
    karte.setAttribute("role", "region");
    karte.setAttribute("aria-labelledby", "einf-angebot-titel");
    karte.innerHTML = `<h2 id="einf-angebot-titel">${esc(t.titel)}</h2><p>${esc(t.text)}</p>
      <div class="einf-angebot-knoepfe"><button type="button" class="btn secondary" id="einf-nicht-jetzt">Nicht jetzt</button>
        <button type="button" class="btn" id="einf-starten">${esc(t.knopf)}</button></div>`;
    document.body.appendChild(karte);
    const wurzel = document.documentElement;
    const anpassen = () => {
      if (!karte.isConnected) return;
      const leiste = schmal();
      karte.classList.toggle("als-leiste", leiste);
      wurzel.classList.toggle("fuehrung-leiste", leiste);
      if (leiste) wurzel.style.setProperty("--fuehrung-hoehe", `${Math.ceil(karte.offsetHeight)}px`);
      else wurzel.style.removeProperty("--fuehrung-hoehe");
    };
    const weg = () => {
      karte.remove();
      wurzel.classList.remove("fuehrung-leiste");
      wurzel.style.removeProperty("--fuehrung-hoehe");
      window.removeEventListener("resize", anpassen);
    };
    window.addEventListener("resize", anpassen);
    anpassen();
    karte.querySelector("#einf-nicht-jetzt").addEventListener("click", async (e) => {
      e.currentTarget.disabled = true;
      for (const x of an) await merken(E.modul, x.teil, "abgelehnt", x.ablauf);
      weg();
      S.toast("Die Übung findest du jederzeit im Profil unter „Einführungen“.");
    });
    karte.querySelector("#einf-starten").addEventListener("click", async (e) => {
      const knopf = e.currentTarget;
      knopf.disabled = true;
      const ok = await merken(E.modul, t.start.teil, "unterbrochen", t.start.zustand === "unterbrochen" ? t.start.ablauf : 0);
      if (!ok) { S.fehlschlag(knopf, "Die Übung ließ sich gerade nicht starten. Versuch es gleich noch einmal."); return; }
      sitzung.weg(ZUSTAND);
      location.href = t.start.adresse;
    });
  }
  // Erst, wenn kein Dialog mehr offen ist – auch keiner, der noch kommt (Hinweis „Entwicklungsserver“, Willkommen der
  // Materialablage: beide stehen schon im HTML und öffnen nacheinander).
  function angebotPlanen() {
    const dev = document.getElementById("dev-hinweis");
    const willkommen = document.getElementById("mat-willkommen");
    const wartend = new Set([dev, willkommen].filter((d) => d && (d.open || (d === willkommen && dev && dev.open))));
    wartend.forEach((d) => d.addEventListener("close", () => { wartend.delete(d); pruefen(); }, { once: true }));
    let gezeigt = false;
    let takt = null;
    function pruefen() {
      if (gezeigt) return;
      if (document.querySelector("dialog[open]") || wartend.size) return;
      clearTimeout(takt);
      takt = setTimeout(() => {
        if (gezeigt || document.querySelector("dialog[open]") || wartend.size) return;
        gezeigt = true;
        mo.disconnect();
        angebotZeigen();
      }, 400);
    }
    const mo = new MutationObserver(pruefen);
    mo.observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ["open"], childList: true });
    pruefen();
  }
  if (!UEBUNG && E && Array.isArray(E.angebot) && E.angebot.length && !ruhe().includes(E.modul)) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", angebotPlanen, { once: true });
    else angebotPlanen();
  }
})();
