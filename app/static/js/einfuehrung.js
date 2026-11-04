/* Interaktive Einführung je Modul (Wunsch des Nutzers vom 28.10.2026, Entscheidungen vom 03.11.2026; Bauvorlage
   planung/tutorial/entwurf.md, Server app/einfuehrung.py, README „Einführungen (Übungen je Modul)“).

   Läuft auf jeder Seite mit Konto – nach common.js und vor den Skripten der Seite (base.html):
   - Ohne Übung räumt es Übungsreste aus der Ablage dieses Reiters und zeigt auf Seiten eines Moduls das Angebot
     (schwebende Karte unten rechts, am Telefon als Leiste unten; nicht modal, erst nach offenen Dialogen).
   - Im Übungsmodus (?uebung=<teil>, vom Server bestätigt: STROEMIS.einfuehrung.uebung) legt es eine Schicht um alle
     Wege, auf denen die Seite Daten holt oder schreibt (fetch, XMLHttpRequest, sendBeacon, window.open, Datei-Links,
     GET-Formulare, Verlauf): Anfragen an /api/ und /media/ beantwortet die Übungsdatei des Moduls
     (app/static/js/uebung/<modul>.js) aus ihrem Übungsbestand – ans Netz gehen nur der Merker (/api/einfuehrung/…),
     GET /api/me, Abmelden und /static/, mit der Kopfzeile „X-Uebung: 1“; der Server sperrt alles andere ein zweites Mal.
     localStorage und sessionStorage zeigen auf eine eigene Übungsablage; Seiten eines Moduls ohne Übungszweig (Meine
     PSA, Echtheit prüfen …) melden „In der Übung nicht verfügbar.“ statt zu laden (Sicherheitsprüfung vom 04.11.2026).
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
   {bedingung: (z) => bool}; mehrere Angaben: was zuerst eintritt), wenn (() => bool: Schritt nur, wenn zutreffend), datei ({input: sel, bild:
   "/static/uebung/…"} – Knopf „Übungsbild nehmen“), probe (nur für den Durchlauftest: {klick: sel} | {klick: sel, frei:
   true, sonst: sel} | {tippen: [sel, text]} | {datei: true}). Ein Text darf ein Getter sein (er folgt der Lage), ebenso
   ein Ziel als Funktion. „Tippe“ in Texten sagt die Blase ohne Touch-Zeiger als „Klicke“ (wortlaut).
   Testschnittstelle (nur lesend): S.einfuehrung.zustand(), S.einfuehrung.teile(modul). */
(function () {
  const S = window.S;
  const E = (window.STROEMIS && window.STROEMIS.einfuehrung) || null;
  const UEBUNG = E && E.uebung ? E.uebung : null;
  const ZUSTAND = "stroemis-uebung";          // Übungszustand dieses Reiters: {modul, teil, ablauf, schritt, z}
  const RUHE = "stroemis-uebung-ruhe";        // Module, deren Angebot in diesem Reiter schweigt (nach Ende/Unterbrechen)
  const ABLAGE = "stroemis-uebung-ablage";    // Übungsablage dieses Reiters: {lokal: {…}, sitzung: {…}}
  const echtFetch = window.fetch.bind(window);
  const echtOpen = window.open.bind(window);
  const esc = S.esc;
  const registriert = {};                     // Modul → Übungsdatei

  /* --- Ablage ------------------------------------------------------------------------------------------------------ */
  // Die echte Ablage des Browsers – gefasst, bevor die Übung localStorage und sessionStorage umlegt (ablageUmlegen).
  const echt = { lokal: null, sitzung: null };
  try { echt.lokal = window.localStorage; echt.sitzung = window.sessionStorage; } catch (e) { /* kein Speicher */ }
  const sitzung = {
    lesen(k) { try { return JSON.parse(echt.sitzung.getItem(k) || "null"); } catch (e) { return null; } },
    schreiben(k, v) { try { echt.sitzung.setItem(k, JSON.stringify(v)); } catch (e) { /* kein Speicher */ } },
    weg(k) { try { echt.sitzung.removeItem(k); } catch (e) { /* kein Speicher */ } },
  };
  /* Übungsreste weg: die Übungsablage und der Übungszustand dieses Reiters. Was die Seite in der Übung abgelegt hat
     (Prüfentwurf, Stoppuhr, Entwürfe, zugeklappte Ordner), lag nur dort (ablageUmlegen) – die echte Ablage bleibt. */
  function ablageAufraeumen() {
    sitzung.weg(ABLAGE);
    sitzung.weg(ZUSTAND);
  }

  /* Im Übungsmodus liest und schreibt kein Skript der Seite die echte Ablage (Sicherheitsprüfung vom 04.11.2026):
     localStorage und sessionStorage zeigen vor den Skripten der Seite auf je einen Bereich der Übungsablage – im echten
     sessionStorage unter ABLAGE, damit sie Seitenwechsel innerhalb der Übung übersteht und mit dem Reiter vergeht. Eine
     echte Stoppuhr, zugeklappte Ordner oder ausgeblendete Hinweise bleiben so, wie sie sind; überschreibt die Übung sie,
     dann nur in ihrem Bereich. */
  function ablageBereich(name) {
    const alles = () => { const a = sitzung.lesen(ABLAGE); return a && typeof a === "object" ? a : {}; };
    // Ohne Prototyp: ein Schlüssel „__proto__“ ist dann ein gewöhnlicher Eintrag.
    const lesen = () => { const b = alles()[name]; return Object.assign(Object.create(null), b && typeof b === "object" ? b : {}); };
    const schreiben = (werte) => {
      if (!echt.sitzung) throw new DOMException("Kein Speicher", "SecurityError");
      const a = alles();
      a[name] = werte;
      echt.sitzung.setItem(ABLAGE, JSON.stringify(a));   // voll: QuotaExceededError wie beim echten Speicher
    };
    return {
      get length() { return Object.keys(lesen()).length; },
      key(i) { const k = Object.keys(lesen()); const n = Math.trunc(Number(i)); return n >= 0 && n < k.length ? k[n] : null; },
      getItem(k) { const w = lesen(); return Object.prototype.hasOwnProperty.call(w, String(k)) ? w[String(k)] : null; },
      setItem(k, v) { const w = lesen(); w[String(k)] = String(v); schreiben(w); },
      removeItem(k) { const w = lesen(); delete w[String(k)]; schreiben(w); },
      clear() { schreiben(Object.create(null)); },
    };
  }
  let ablageUmgelegt = false;
  function ablageUmlegen() {
    try {
      for (const [eigenschaft, bereich] of [["localStorage", ablageBereich("lokal")], ["sessionStorage", ablageBereich("sitzung")]]) {
        Object.defineProperty(window, eigenschaft, { configurable: true, enumerable: true, get: () => bereich });
      }
      ablageUmgelegt = window.localStorage !== echt.lokal && window.sessionStorage !== echt.sitzung;
    } catch (e) { ablageUmgelegt = false; }
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
  let seiteGeht = 0;              // seit wann diese Seite verlassen wird (Link, Formular, location …) – bis die neue da ist
  let zurueckSeit = 0;            // ein Schritt zurück im Verlauf läuft (common.js schließt ein Overlay) – bis popstate
  let dialogZuSeit = 0;           // eben hat sich ein Dialog geschlossen – sein Schritt zurück kommt gleich
  let ausDemVerlauf = false;      // die Seite kam per Zurück/Vor – fehlt das Ziel, sagt die Blase, wie es weitergeht

  /* --- Ohne Übung -------------------------------------------------------------------------------------------------- */
  if (!UEBUNG) {
    // Wer aus einer Übung herauskommt (Kopfleiste: Startseite, Profil, andere Module, Meine PSA; Zurück), landet auf
    // einer echten Seite: Zustand und Übungsablage dieses Reiters gehen still, der Merker steht schon auf „unterbrochen“.
    // Nicht auf der Fehlerseite „In der Übung nicht verfügbar“ (E.gesperrt) – „Zurück zur Übung“ macht dort weiter.
    if (!(E && E.gesperrt)) {
      ablageAufraeumen();
      // Auch, wenn der Browser die Seite aus seinem Seitenspeicher zeigt (Zurück aus der Übung).
      window.addEventListener("pageshow", (e) => { if (e.persisted) ablageAufraeumen(); });
    }
    // Eine Adresse mit „uebung=“, die der Server nicht als Übung zeichnet (Teil gilt nicht für das Konto, Fehlerseite):
    // Die Kennung kommt aus der Adresse, bevor die Seite Anfragen stellt – der Server sperrte sie sonst.
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
    // Nur für das Abmelden (common.js, ablageLeeren): die echte Ablage, auch wenn die Übung sie umgelegt hat.
    echteAblage() { return [echt.lokal, echt.sitzung].filter(Boolean); },
  };

  /* ================================================================================================================
     Schicht (nur im Übungsmodus, Bauvorlage 2.3)
     ================================================================================================================ */
  // Was ans Netz darf – mit X-Uebung: 1 (der Server lässt genau das durch). Abmelden ändert nur die Sitzung.
  const ausnahme = (pfad, methode) => pfad.startsWith("/api/einfuehrung/") || pfad.startsWith("/static/")
    || (pfad === "/api/me" && (methode === "GET" || methode === "HEAD")) || (pfad === "/api/auth/logout" && methode === "POST");
  /* Seiten eines Moduls ohne Übungszweig (Meine PSA, Echtheit prüfen, Bericht, Druck …): Die Liste der Seiten mit
     Übungszweig gibt der Server mit (STROEMIS.einfuehrung.seiten, app/einfuehrung.py UEBUNGSSEITEN). Links, Formulare und
     Seitenwechsel dorthin bleiben auf der Seite und melden „In der Übung nicht verfügbar.“. */
  const SEITEN = ((E && E.seiten) || []).map((s) => { try { return new RegExp(s); } catch (e) { return null; } }).filter(Boolean);
  const BEREICHE = (E && E.bereiche) || [];
  const ohneUebung = (u) => Boolean(u && u.origin === location.origin
    && BEREICHE.some((b) => u.pathname === b || u.pathname.startsWith(`${b}/`)) && !SEITEN.some((r) => r.test(u.pathname)));
  const NICHT_HIER = "In der Übung nicht verfügbar.";
  let ausgang = null;                   // Adresse eines Links der Kopfleiste, der gerade aus der Übung hinausführt
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
    // Kennung. Die Kopfleiste führt aus der Übung hinaus – ohne Referer, sonst hielte der Server auch „Meine PSA“ der
    // Kopfleiste für eine Seite aus der Übung; ein neuer Reiter (target) öffnet die echte Seite. Ebenso ein Klick mit
    // Zusatztaste (Strg, Cmd, Umschalt, Alt: neuer Reiter, neues Fenster, Download) wie der Mittelklick: keine Kennung, die
    // Übung in diesem Reiter bleibt, wie sie ist (Befund 1 der Endprüfung).
    const kopfleiste = (el) => Boolean(el && el.closest && el.closest("header.bauchbinde"));
    const zusatztaste = (e) => e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey;
    document.querySelectorAll("header.bauchbinde a[href]").forEach((a) => { a.referrerPolicy = "no-referrer"; });
    document.addEventListener("click", (e) => {
      if (zusatztaste(e)) return;
      const a = e.target.closest && e.target.closest("a[href]");
      if (a && kopfleiste(a)) { ausgang = a.href; a.referrerPolicy = "no-referrer"; return; }
      if (!a || a.closest(".fuehrung-blase, .einfuehrung-angebot")) return;
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
    // Links auf Seiten ohne Übungszweig: erst nach den Handlern der Seite (die einen Link selbst behandeln dürfen), auch mit
    // target – stattdessen der Toast, die Übung läuft weiter.
    window.addEventListener("click", (e) => {
      if (zusatztaste(e) || e.defaultPrevented) return;
      const a = e.target.closest && e.target.closest("a[href]");
      if (!a || kopfleiste(a) || a.closest(".fuehrung-blase, .einfuehrung-angebot") || !ohneUebung(adresse(a.href))) return;
      e.preventDefault();
      S.toast(NICHT_HIER);
    });
    // GET-Formulare des Moduls (Nummernsuche der Materialablage): die Kennung als verstecktes Feld.
    const formZiel = (f, e) => adresse((e && e.submitter && e.submitter.hasAttribute("formaction") && e.submitter.formAction)
      || (f.hasAttribute("action") ? f.action : location.href));
    document.addEventListener("submit", (e) => {
      const f = e.target;
      if (!(f instanceof HTMLFormElement) || (f.getAttribute("method") || "get").toLowerCase() !== "get") return;
      const u = formZiel(f, e);
      if (!u || S.ziel(u.href) === u.href || f.querySelector("input[name=uebung]")) return;
      const feld = document.createElement("input");
      Object.assign(feld, { type: "hidden", name: "uebung", value: UEBUNG });
      f.appendChild(feld);
    }, true);
    // Formulare an Seiten ohne Übungszweig (nach den Handlern der Seite): Toast statt Seitenwechsel.
    window.addEventListener("submit", (e) => {
      const f = e.target;
      if (e.defaultPrevented || !(f instanceof HTMLFormElement) || !ohneUebung(formZiel(f, e))) return;
      e.preventDefault();
      S.toast(NICHT_HIER);
    });
    // Jeder andere Seitenwechsel dorthin (location.href = S.ziel(…), assign, replace, Verlauf) – wo der Browser die
    // Navigation API hat (Chromium, Firefox, Safari 26): anhalten, Toast. Ohne sie antwortet der Server mit der Fehlerseite
    // „In der Übung nicht verfügbar“ und dem Weg zurück. Die Kopfleiste (ausgang) führt hinaus.
    // Ebenso Seitenwechsel auf Dateien (/api/, /media/, Endung – dieselbe Regel wie bei Links), etwa der Export der
    // Strömipedia über location.href: die Übungsdatei aus der Dateitabelle oder der Hinweis, dass es sie nicht gibt. Auch
    // Downloads (ein losgelöster Link mit download – Hinweis 1 der Endprüfung).
    if (window.navigation && typeof window.navigation.addEventListener === "function") {
      window.navigation.addEventListener("navigate", (e) => {
        if (!e.cancelable || e.hashChange || e.navigationType === "reload" || e.navigationType === "traverse") return;
        const u = adresse(e.destination && e.destination.url);
        const download = typeof e.downloadRequest === "string";
        if (u && u.origin === location.origin && (istDatei(u) || download) && !(ausgang && u.href === ausgang)) {
          e.preventDefault();
          const datei = dateiFuer(u);
          if (datei) echtOpen(datei, "_blank", "noopener");
          else S.toast("In der Übung gibt es diese Datei nicht.");
          return;
        }
        if (!ohneUebung(u) || (ausgang && u.href === ausgang)) return;
        e.preventDefault();
        S.toast(NICHT_HIER);
      });
      // Ein Seitenwechsel, den niemand angehalten hat, läuft: Bis die neue Seite da ist, wertet die Führung auf dieser
      // nichts mehr aus (schrittZeigen – kein Überspringen, nichts speichern).
      window.navigation.addEventListener("navigate", (e) => {
        if (!e.defaultPrevented && !e.downloadRequest && !(e.destination && e.destination.sameDocument)) seiteGeht = Date.now();
      });
    }
    window.addEventListener("pagehide", () => { seiteGeht = seiteGeht || Date.now(); });
    window.addEventListener("pageshow", (e) => {
      seiteGeht = 0;
      if (!e.persisted || !DEF) return;
      // Aus dem Seitenspeicher des Browsers zurück (Zurück/Vor): Läuft die Übung nicht mehr, zur echten Seite (Befund B2);
      // sonst den Schritt aus dem Übungszustand neu zeigen – wie nach einem Seitenaufruf aus dem Verlauf.
      const alt = sitzung.lesen(ZUSTAND);
      if (!aktiv(alt)) { zurEchtenSeite(); return; }
      zustand = alt;
      umgeleitet = false;
      ausDemVerlauf = true;
      schrittZeigen();
    });
    // Schließt ein Overlay, nimmt common.js seinen Schritt im Verlauf zurück (S.overlayVerlauf: history.go, dann popstate),
    // und der Browser stellt dabei die Bildlaufhöhe von vorher wieder her. Die Führung wartet das ab (overlaySchliesst).
    for (const art of ["back", "go"]) {
      const vorher = history[art];
      history[art] = function (...a) { zurueckSeit = Date.now(); return vorher.apply(history, a); };
    }
    window.addEventListener("popstate", () => { zurueckSeit = 0; }, true);
    new MutationObserver((liste) => {
      if (liste.some((m) => m.target instanceof HTMLDialogElement && !m.target.open)) dialogZuSeit = Date.now();
    }).observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ["open"] });
    // Ohne Referer erkennt der Server eine Anfrage aus der Übung nicht (Hinweis 1 der Sicherheitsprüfung): Außerhalb der
    // Kopfleiste trägt in der Übung kein Element referrerpolicy oder rel="noreferrer". Bilder, Medien und Rahmen hält
    // zusätzlich die engere CSP der Übungsseite von /api/ und /media/ fern (app/einfuehrung.py, csp_quellen) – für sie
    // käme dieser Beobachter zu spät, für Links (neuer Reiter) nicht.
    const refererBehalten = (wurzel) => {
      if (!(wurzel instanceof Element)) return;
      for (const el of [wurzel, ...wurzel.querySelectorAll("[referrerpolicy], [rel]")]) {
        if (kopfleiste(el)) continue;
        if (el.hasAttribute("referrerpolicy")) el.removeAttribute("referrerpolicy");
        const rel = el.getAttribute("rel");
        if (rel && /(^|\s)noreferrer(\s|$)/i.test(rel)) {
          el.setAttribute("rel", rel.split(/\s+/).filter((t) => t && t.toLowerCase() !== "noreferrer").join(" "));
        }
      }
    };
    new MutationObserver((liste) => liste.forEach((m) => {
      if (m.type === "attributes") refererBehalten(m.target); else m.addedNodes.forEach(refererBehalten);
    })).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["referrerpolicy", "rel"] });
    refererBehalten(document.body);
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
  // Wie diese Seite geladen wurde: "navigate", "reload" oder "back_forward" (Zurück/Vor im Browser).
  function ladeart() {
    try { const n = performance.getEntriesByType("navigation")[0]; return (n && n.type) || "navigate"; } catch (e) { return "navigate"; }
  }
  // Der Ablauf, bei dem der Merker dieses Teils „unterbrochen“ steht (vom Server mit der Seite) – sonst 0.
  function gemerkt() {
    const t = ((E && E.teile) || []).find((x) => x.teil === UEBUNG);
    return t && t.zustand === "unterbrochen" && Number.isInteger(t.ablauf) ? t.ablauf : 0;
  }
  // Der Merker geht nie auf einen kleineren Ablauf zurück (ein zweiter Reiter, Befund 1 der Endprüfung).
  function neuerAblauf(n) {
    ablageAufraeumen();
    zustand = { modul: E.modul, teil: UEBUNG, ablauf: n, schritt: 0, z: frischerBestand() };
    speichern();
    merken(E.modul, UEBUNG, "unterbrochen", Math.max(n, gemerkt()));
  }
  // Steht die Seite schon an der Startadresse des Ablaufs? (Pfad und Abfrage ohne Kennung; der Anker zählt nicht.)
  function ohneKennung(u) {
    const k = new URL(u.href);
    k.searchParams.delete("uebung");
    k.searchParams.delete("ablauf");
    return k.pathname + k.search;
  }
  /* Zur Startadresse eines Ablaufs. frisch: die Seite lädt auf jeden Fall neu – auch bei gleicher Adresse oder nur anderem
     Anker –, damit sie zum frischen Übungsbestand passt (sonst zeigte sie noch, was der vorige Ablauf geändert hat, und
     bliebe im alten Reiter). Ohne frisch (beim Laden der Seite, vor ihren Skripten) genügt an der Startadresse der Anker. */
  function zumStart(start, ersetzen, frisch) {
    const u = adresse(start || E.start);
    if (!u) return false;
    const hier = new URL(location.href);
    if (ohneKennung(u) === ohneKennung(hier)) {
      if (u.hash !== hier.hash) history.replaceState(history.state, "", S.ziel(u.pathname + hier.search + u.hash));
      if (!frisch) return false;
      umgeleitet = true;
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });     // neu geladen von oben, nicht an der alten Stelle
      location.reload();
      return true;
    }
    umgeleitet = true;
    if (ersetzen) location.replace(S.ziel(u.href)); else location.href = S.ziel(u.href);
    return true;
  }
  // Erst, wenn kein Overlay mehr seinen Schritt zurück im Verlauf nimmt (höchstens 1 s) – ein Seitenwechsel davor würde
  // von diesem Schritt abgebrochen.
  function nachDemZurueck(fn) {
    const ende = Date.now() + 1000;
    const los = () => { if (overlaySchliesst() && Date.now() < ende) { setTimeout(los, 30); return; } fn(); };
    setTimeout(los, 0);
  }

  // Läuft in diesem Reiter eine Übung dieses Teils (Übungszustand in der Ablage)?
  const aktiv = (alt) => Boolean(alt && typeof alt === "object" && alt.modul === E.modul && alt.teil === UEBUNG);
  // Raus zur echten Startseite des Moduls, ohne Spur im Verlauf (Zurück nach dem Verlassen der Übung, Befund B2).
  function zurEchtenSeite() {
    umgeleitet = true;
    fuehrungWeg();
    location.replace(E.start);
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
    // Aus dem Verlauf (Zurück/Vor) ohne laufende Übung dieses Teils – nach „Übung unterbrechen“, „Geschafft“ oder dem Weg
    // über die Kopfleiste: keine Übungsseite ohne Führung, sondern die echte Seite (Befund B2).
    if (ladeart() === "back_forward" && !aktiv(alt)) {
      zustand = { modul: E.modul, teil: UEBUNG, ablauf: 0, schritt: 0, z: {} };
      zurEchtenSeite();
      return;
    }
    if (!t || !Array.isArray(t.ablaeufe) || !t.ablaeufe.length) {
      zustand = { modul: E.modul, teil: UEBUNG, ablauf: 0, schritt: 0, z: frischerBestand() };
      return;
    }
    // Ein Reiter ohne Übungszustand (Profil, Angebot, Strg-Klick, Lesezeichen) beginnt beim gemerkten Ablauf.
    if (param !== null || !aktiv(alt) || !t.ablaeufe[alt.ablauf]) {
      const n = Math.max(0, Math.min(Number.isFinite(param) ? param : gemerkt(), t.ablaeufe.length - 1));
      neuerAblauf(n);
      zumStart(t.ablaeufe[n].start, true);
      return;
    }
    // Neu geladen nach einer Eingabe in diesem Ablauf (Text, Suchbegriff): Die Eingabe ist weg – der Ablauf beginnt von vorn,
    // statt einen Schritt zu zeigen, der sie voraussetzt (Verbesserung V9).
    const schritte = t.ablaeufe[alt.ablauf].schritte || [];
    if (ladeart() === "reload" && schritte.slice(0, alt.schritt).some((x) => x && x.warten && x.warten.wert)) {
      neuerAblauf(alt.ablauf);
      zumStart(t.ablaeufe[alt.ablauf].start, true);
      return;
    }
    zustand = alt;
    ausDemVerlauf = ladeart() === "back_forward";
  }

  let blase = null;
  let rahmen = null;
  let ansage = null;                    // Live-Region: der Text des Schritts bei Zielen im Editor (zielBeschreiben)
  let zielEl = null;
  let laufNr = 0;                       // jede Anzeige eines Schritts; ältere Wartende geben auf
  let aufraeumen = [];                  // Wächter des gezeigten Schritts
  let planung = 0;
  let bereitSeit = 0;                   // seit wann der gezeigte Schritt bereit ist
  let nachgeholt = 0;                   // wie oft lage() das Ziel dieses Schritts wieder ins Bild geholt hat
  let selbstGerollt = false;            // in diesem Schritt hast du selbst gerollt – dann holt lage() nichts zurück
  let eingabeSeit = 0;                  // letzte Eingabe (Tippen, Klicken, Taste) außerhalb der Blase

  // Ein Bild weiter (requestAnimationFrame; im verdeckten Reiter nach spätestens 80 ms).
  const bild = () => new Promise((r) => { requestAnimationFrame(() => r()); setTimeout(r, 80); });
  // Ein Overlay schließt gerade: sein Schritt zurück im Verlauf steht aus oder läuft (siehe schichtEinschalten).
  const overlaySchliesst = () => Boolean((zurueckSeit && Date.now() - zurueckSeit < 1500) || (dialogZuSeit && Date.now() - dialogZuSeit < 150));
  const seiteGehtGerade = () => umgeleitet || Boolean(seiteGeht && Date.now() - seiteGeht < 4000);
  function obersterDialog() {
    const offen = [...document.querySelectorAll("dialog[open]")].filter((d) => sicher(() => d.matches(":modal")));
    return offen.length ? offen[offen.length - 1] : null;
  }
  // Sichtbar: mit Fläche, nicht unsichtbar, nicht in [hidden]/[inert] – und bei offenem modalem Dialog nur in ihm (alles
  // dahinter ist für dich gerade nicht erreichbar, auch wenn der Browser es noch zeichnet).
  function sichtbar(el) {
    if (!el || !el.isConnected || !el.getClientRects().length) return false;
    if (el.closest(".fuehrung-blase, .fuehrung-rahmen")) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || el.closest("[hidden], [inert]")) return false;
    const d = obersterDialog();
    return !d || d.contains(el);
  }
  // Läuft eine Animation am Ziel oder einem Vorfahren (Schublade, Seitenleiste gleitet herein)? Endlose zählen nicht.
  function animiert(el) {
    if (typeof document.getAnimations !== "function") return false;
    return document.getAnimations().some((an) => {
      const t = an.effect && an.effect.target;
      if (an.playState !== "running" || !(t instanceof Element) || !t.contains(el)) return false;
      const zeit = typeof an.effect.getComputedTiming === "function" ? an.effect.getComputedTiming() : {};
      return zeit.iterations !== Infinity;
    });
  }

  /* --- Ins Bild holen ---------------------------------------------------------------------------------------------
     Der freie Bereich für ein Ziel: das Fenster, begrenzt von den Rahmen, die es abschneiden (Dialog, Schublade, Liste,
     die in sich rollt), von klebenden oder festen Leisten darüber und darunter (Kopfleiste, Suchzeile, Reiter,
     Abschlussleiste – gesucht mit elementsFromPoint an der waagerechten Mitte des Ziels) und am Telefon von der Leiste der
     Führung. Darin holt insBild das Ziel sofort (ohne weichen Bildlauf) in die Mitte; ist es höher als der Bereich, steht
     sein Anfang oben. */
  const klebt = (n) => { const p = getComputedStyle(n).position; return p === "fixed" || p === "sticky"; };
  function leisteBei(el, x, y) {
    if (y < 0 || y >= window.innerHeight) return null;
    for (const t of document.elementsFromPoint(x, y)) {
      if (t.closest(".fuehrung-blase, .fuehrung-rahmen")) continue;
      for (let n = t; n && n !== document.body && n !== document.documentElement; n = n.parentElement) {
        if (n.contains(el)) return null;                 // das Ziel selbst oder sein Rahmen
        // Eine Leiste ist flach; eine klebende Spalte (Seitenbaum, Gliederung, Seitenleiste) liegt neben dem Ziel.
        if (klebt(n)) return n.getBoundingClientRect().height <= window.innerHeight / 2 ? n : null;
      }
      return null;
    }
    return null;
  }
  function freieFlaeche(el) {
    let oben = 0;
    let unten = window.innerHeight;
    if (blase && !blase.hidden && blase.classList.contains("als-leiste")) unten = Math.min(unten, blase.getBoundingClientRect().top);
    for (let n = el.parentElement; n && n !== document.body && n !== document.documentElement; n = n.parentElement) {
      if (getComputedStyle(n).overflowY === "visible") continue;
      const r = n.getBoundingClientRect();
      oben = Math.max(oben, r.top + n.clientTop);
      unten = Math.min(unten, r.top + n.clientTop + n.clientHeight);
    }
    const r = el.getBoundingClientRect();
    const x = Math.min(Math.max((Math.max(r.left, 0) + Math.min(r.right, window.innerWidth)) / 2, 1), window.innerWidth - 2);
    for (let i = 0; i < 6; i++) {
      const n = leisteBei(el, x, oben + 1);
      const b = n ? n.getBoundingClientRect().bottom : oben;
      if (b <= oben + 0.5) break;
      oben = b;
    }
    for (let i = 0; i < 6; i++) {
      const n = leisteBei(el, x, unten - 2);
      const t = n ? n.getBoundingClientRect().top : unten;
      if (t >= unten - 0.5) break;
      unten = t;
    }
    return { oben, unten: Math.max(unten, oben + 1) };
  }
  /* Das Rechteck des Ziels – bei einem Kombinationsfeld mit aufgeklappter Liste (aria-expanded="true", aria-controls:
     Vorschläge der Suche) samt Liste: Sie gehört ins Bild, und die Blase deckt sie nicht (Telefon quer, Browserprüfung). */
  function zielFlaeche(el) {
    const r = el.getBoundingClientRect();
    const id = el.getAttribute("aria-expanded") === "true" ? el.getAttribute("aria-controls") : "";
    const liste = id ? document.getElementById(id) : null;
    if (!liste || !liste.getClientRects().length || liste.hidden) return r;
    const l = liste.getBoundingClientRect();
    const k = { left: Math.min(r.left, l.left), top: Math.min(r.top, l.top), right: Math.max(r.right, l.right),
                bottom: Math.max(r.bottom, l.bottom) };
    return Object.assign(k, { width: k.right - k.left, height: k.bottom - k.top });
  }
  // Steht das Ziel im freien Bereich? (Höhere Ziele: wenn sie seine Mitte bedecken.)
  function imFreien(el) {
    const f = freieFlaeche(el);
    const r = zielFlaeche(el);
    if (r.height <= f.unten - f.oben + 1) return r.top >= f.oben - 1 && r.bottom <= f.unten + 1;
    const mitte = (f.oben + f.unten) / 2;
    return r.top <= mitte && r.bottom >= mitte;
  }
  // Das Ziel um m Pixel verschieben (positiv: nach unten) – erst mit dem Fenster, dann mit den Rahmen, die in sich rollen.
  function verschieben(el, m) {
    const kette = [null];
    for (let n = el.parentElement; n && n !== document.body && n !== document.documentElement; n = n.parentElement) {
      if (/(auto|scroll|hidden)/.test(getComputedStyle(n).overflowY) && n.scrollHeight > n.clientHeight + 1) kette.splice(1, 0, n);
    }
    for (const c of kette) {
      if (Math.abs(m) < 1) return;
      const vorher = el.getBoundingClientRect().top;
      (c || window).scrollBy({ top: -m, left: 0, behavior: "instant" });
      m -= el.getBoundingClientRect().top - vorher;
    }
  }
  function insBild(el) {
    if (!el || !sichtbar(el)) return;
    for (let i = 0; i < 3 && !imFreien(el); i++) {
      if (i === 0) el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });   // in jedem Rahmen sichtbar
      const f = freieFlaeche(el);
      const r = zielFlaeche(el);
      const frei = f.unten - f.oben;
      verschieben(el, (r.height <= frei ? f.oben + (frei - r.height) / 2 : f.oben) - r.top);
    }
  }
  const lageText = (el) => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round).join(","); };
  /* Vor „bereit“: Webschriften geladen, kein Overlay schließt mehr, keine Animation am Ziel – dann ins Bild holen, und erst
     wenn das Ziel zwei Bilder lang still steht, gilt der Schritt als bereit (höchstens 3 s). Zeichnet die Seite das Ziel
     dabei neu, gilt das neue. */
  async function beruhigen(s, el, lauf) {
    const ende = Date.now() + 3000;
    while (Date.now() < ende) {
      await bild();
      if (lauf !== laufNr) return null;
      if (!sichtbar(el)) {
        el = zielSuchen(s.ziel);
        if (!el) continue;
        zielBeschreiben(el);
      }
      if (overlaySchliesst() || (document.fonts && document.fonts.status !== "loaded") || animiert(el)) continue;
      insBild(el);
      lage();
      // Findet die Blase neben dem Ziel keinen Platz, steht sie jetzt als Leiste unten – das Ziel darüber.
      insBild(el);
      lage();
      const vorher = lageText(el);
      await bild();
      await bild();
      if (lauf !== laufNr) return null;
      if (sichtbar(el) && lageText(el) === vorher && !overlaySchliesst() && !animiert(el)) return el;
    }
    return sichtbar(el) ? el : zielSuchen(s.ziel);
  }
  // Vor dem Auswerten eines Schritts: ein, zwei Bilder für Seitenwechsel, die die Aktion eben geplant hat (Formulare),
  // dann Webschriften und das Zurück eines eben geschlossenen Overlays (höchstens 3 s).
  async function abwarten(lauf) {
    await bild();
    await bild();
    if (document.fonts && document.fonts.ready) await Promise.race([document.fonts.ready, pause(3000)]);
    const ende = Date.now() + 3000;
    while (lauf === laufNr && Date.now() < ende && !seiteGehtGerade()
           && (overlaySchliesst() || (document.fonts && document.fonts.status !== "loaded"))) await pause(30);
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
      const takt = setInterval(versuch, 120);
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
    for (const el of [rahmen, blase, ansage]) if (el && el.parentElement !== b) b.appendChild(el);
  }
  /* Leiste unten statt schwebender Blase: am Telefon hochkant (schmal) und bei geringer Höhe – Telefon quer (Befund B1
     der Browserprüfung vom 04.11.2026) –, dazu in einem Schritt, in dem die Blase neben dem Ziel keinen Platz fand
     (engLeiste, lage). Das Angebot folgt derselben Regel. */
  const schmal = () => window.innerWidth < 600 || window.innerHeight < 520;
  let engLeiste = false;
  // Offene Menüs: schwebende (am Ende der Seite, über allem außer Führung und Dialogen) und aufgeklappte.
  const MENUES = ".menue-schwebend, details[open] > :is(.menue-liste, .mat-menue-liste, .zeilenmenue-liste)";
  const menues = () => [...document.querySelectorAll(MENUES)].filter((m) => m.getClientRects().length && !m.closest("[hidden], [inert]"));
  const ueber = (a, b) => a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1;
  const kasten = (left, top, w, h) => ({ left, top, right: left + w, bottom: top + h });
  // Die Knöpfe eines Dialogs (Abbrechen, Hauptaktion): Die Blase weicht ihnen aus wie Menüs (Befund B3).
  const DIALOGKNOEPFE = ":is(.dlg-actions, .c-actions, .lb-aktionen) :is(button, a[href])";
  // Die Bildschirmsegmente eines faltbaren Geräts (Scharnier, Befund B4) – mit nur einem Segment leer.
  function segmente() {
    const quelle = (window.viewport && window.viewport.segments) || (window.visualViewport && window.visualViewport.segments) || [];
    const liste = [...quelle].map((g) => kasten(g.x !== undefined ? g.x : g.left, g.y !== undefined ? g.y : g.top, g.width, g.height));
    return liste.length > 1 ? liste : [];
  }
  // Einen Platz für die Blase (left, top) in das Segment schieben, in dem seine Mitte liegt.
  function insSegment([x, y], w, h, segs) {
    const mx = x + w / 2;
    const my = y + h / 2;
    const g = segs.find((k) => mx >= k.left && mx < k.right && my >= k.top && my < k.bottom)
      || segs.reduce((a, k) => (Math.hypot(mx - (k.left + k.right) / 2, my - (k.top + k.bottom) / 2)
        < Math.hypot(mx - (a.left + a.right) / 2, my - (a.top + a.bottom) / 2) ? k : a));
    if (g.right - g.left < w + 16 || g.bottom - g.top < h + 16) return [x, y];
    return [Math.min(Math.max(g.left + 8, x), g.right - w - 8), Math.min(Math.max(g.top + 8, y), g.bottom - h - 8)];
  }
  function lage() {
    planung = 0;
    if (!blase) return;
    if (blase.hidden) { rahmen.hidden = true; return; }        // Rückfrage „Übung unterbrechen?“ offen
    einhaengen();
    const wurzel = document.documentElement;
    const leiste = schmal() || engLeiste;
    blase.classList.toggle("als-leiste", leiste);
    wurzel.classList.toggle("fuehrung-leiste", leiste);
    if (leiste) wurzel.style.setProperty("--fuehrung-hoehe", `${Math.ceil(blase.offsetHeight)}px`);
    else wurzel.style.removeProperty("--fuehrung-hoehe");
    // Zeichnet die Seite neu, ist das Ziel ein neues Element – dann wieder suchen. Ein Ziel als Funktion hängt an der
    // Lage (Lupe, bis das Suchfeld offen ist) und wird jedes Mal neu bestimmt; ebenso ein Text als Getter.
    const s = aktuellerSchritt();
    if (s && s.ziel !== null && s.ziel !== undefined && (!sichtbar(zielEl) || typeof s.ziel === "function")) {
      const neu = zielSuchen(s.ziel);
      if (neu && neu !== zielEl) zielBeschreiben(neu);
    }
    const textEl = blase.querySelector(".fuehrung-text");
    if (s && textEl && zustand && blase.dataset.schritt === `${zustand.ablauf}:${zustand.schritt}`
        && textEl.textContent !== wortlaut(s.text || "")) {
      textEl.textContent = wortlaut(s.text || "");
      ansagen(textEl.textContent);
    }
    // Steht die Blase in einem Dialog, das Ziel aber dahinter (inert), bleibt der Dialog ohne Abdunkelung.
    const imDialog = blase.parentElement !== document.body;
    const r = zielEl && sichtbar(zielEl) && (!imDialog || blase.parentElement.contains(zielEl)) ? zielEl.getBoundingClientRect() : null;
    // Rutscht das Ziel kurz nach dem Zeigen unter eine Leiste oder die Blase (das Zurück eines Dialogs stellt die alte
    // Bildlaufhöhe her, Inhalt lädt nach), holt die Führung es noch einmal ins Bild – nicht, wenn du selbst gerollt hast.
    if (r && fuehrung.bereit && !selbstGerollt && nachgeholt < 4 && Date.now() - bereitSeit < 2500 && !overlaySchliesst()
        && !animiert(zielEl) && !imFreien(zielEl)) {
      nachgeholt += 1;
      insBild(zielEl);
      lagePlanen();
      return;
    }
    // Ein offenes Menü (vom Nutzer geöffnet) bleibt frei: Der Rahmen dunkelt ein schwebendes Menü nicht ab, wenn das Ziel
    // nicht darin liegt, und die Blase weicht jedem aus – unter, über, neben das Menü; passt sie nirgends hin (oder steht
    // sie als Leiste unten), liegt sie unter einem schwebenden Menü.
    const offen = menues();
    const zielImMenue = Boolean(zielEl && offen.some((m) => m.contains(zielEl)));
    rahmen.classList.toggle("unter-menue", offen.some((m) => m.matches(".menue-schwebend")) && !zielImMenue);
    const flaechen = offen.map((m) => m.getBoundingClientRect());
    rahmen.hidden = !r;
    if (r) {
      Object.assign(rahmen.style, { left: `${Math.round(r.left - 4)}px`, top: `${Math.round(r.top - 4)}px`,
        width: `${Math.round(r.width + 8)}px`, height: `${Math.round(r.height + 8)}px` });
    }
    if (leiste) {
      // Zwei Segmente nebeneinander (faltbares Gerät quer): die Leiste nur im Segment des Ziels, sonst im rechten – nicht
      // über dem Scharnier.
      const segs = segmente();
      const g = segs.length && segs.every((k) => k.top === segs[0].top)
        ? segs.find((k) => r && (r.left + r.right) / 2 >= k.left && (r.left + r.right) / 2 < k.right) || segs[segs.length - 1] : null;
      blase.style.left = g ? `${Math.round(g.left)}px` : "";
      blase.style.right = g ? `${Math.round(wurzel.clientWidth - g.right)}px` : "";
      blase.style.top = "";
      const b = blase.getBoundingClientRect();
      blase.classList.toggle("unter-menue", flaechen.some((m) => ueber(m, b)));
      return;
    }
    /* Die schwebende Blase: unter, über, rechts oder links neben dem Ziel (ohne Ziel neben dem Dialog bzw. mitten im
       Fenster), dann um den Dialog und um offene Menüs herum. Sie deckt nie das Ziel, die Kopfleiste oder die Leisten
       über dem Ziel und bleibt in einem Bildschirmsegment; Menüs und Knöpfe eines Dialogs meidet sie. Geht das nirgends,
       liegt sie unter einem schwebenden Menü – oder steht für den Rest des Schritts als Leiste unten. */
    const vw = wurzel.clientWidth;
    const vh = window.innerHeight;
    const w = blase.offsetWidth;
    const h = blase.offsetHeight;
    const kopf = document.querySelector("header.bauchbinde");
    const kopfR = kopf && kopf.getClientRects().length ? kopf.getBoundingClientRect() : null;
    const obenFrei = Math.max(r ? freieFlaeche(zielEl).oben : 0, kopfR && kopfR.bottom > 0 ? kopfR.bottom : 0);
    const dialog = imDialog ? blase.parentElement.getBoundingClientRect() : null;
    const knoepfe = imDialog ? [...blase.parentElement.querySelectorAll(DIALOGKNOEPFE)]
      .filter((k) => k.getClientRects().length && !k.closest(".fuehrung-blase") && !(zielEl && (k === zielEl || k.contains(zielEl))))
      .map((k) => k.getBoundingClientRect()) : [];
    const zf = r ? zielFlaeche(zielEl) : null;
    const verboten = [zf && kasten(zf.left - 4, zf.top - 4, zf.width + 8, zf.height + 8), kopfR && kopfR.bottom > 0 && kopfR].filter(Boolean);
    const segs = segmente();
    const quer = (x) => Math.min(Math.max(8, x), vw - w - 8);
    const hoch = (y) => Math.min(Math.max(obenFrei + 8, y), vh - h - 8);
    const um = (k) => [[quer(k.left), k.bottom + 12], [quer(k.left), k.top - 12 - h], [k.right + 12, hoch(k.top)], [k.left - 12 - w, hoch(k.top)]];
    const plaetze = [];
    if (zf) plaetze.push(...um(zf));
    if (dialog) plaetze.push(...um(dialog));
    if (!r && !dialog) plaetze.push([(vw - w) / 2, hoch((vh - h) / 2)]);
    if (!r) plaetze.push([quer((vw - w) / 2), vh - h - 8]);
    for (const m of flaechen) plaetze.push(...um(m));
    const geprueft = plaetze.map((p) => (segs.length ? insSegment(p, w, h, segs) : p)).map(([x, y]) => {
      const k = kasten(x, y, w, h);
      const drin = x >= 8 && y >= obenFrei + 8 - 0.5 && k.right <= vw - 8 && k.bottom <= vh - 8
        && (!segs.length || segs.some((g) => k.left >= g.left && k.right <= g.right && k.top >= g.top && k.bottom <= g.bottom));
      const frei = drin && !verboten.some((v) => ueber(v, k)) && !knoepfe.some((b) => ueber(b, k));
      return { x, y, frei, ohneMenue: frei && !flaechen.some((f) => ueber(f, k)) };
    });
    const wahl = geprueft.find((p) => p.ohneMenue) || geprueft.find((p) => p.frei);
    if (!wahl) {
      engLeiste = true;
      lage();
      return;
    }
    blase.classList.toggle("unter-menue", !wahl.ohneMenue);
    blase.style.right = "";
    blase.style.left = `${Math.round(wahl.x)}px`;
    blase.style.top = `${Math.round(wahl.y)}px`;
  }
  const lagePlanen = () => { if (!planung) planung = requestAnimationFrame(lage); };

  function aktuellerSchritt() {
    const a = ablaufDef();
    return a && zustand && a.schritte ? a.schritte[zustand.schritt] || null : null;
  }
  /* „Schritt n von m“ über den ganzen Teil; Schritte, die nicht zutreffen (wenn), zählen nicht. Welche das sind, hält die
     Führung beim Betreten eines Ablaufs fest (zaehlungFesthalten) – kippt ein „wenn“ durch die Aktion eines Schritts,
     springt m nicht. Zeigt sie einen Schritt, der beim Betreten nicht zutraf, zählt er als nächster. */
  function zaehlungFesthalten() {
    if (zustand.zahl && zustand.zahl.ablauf === zustand.ablauf) return;
    const aus = [];
    teilDef().ablaeufe.forEach((a, i) => (a.schritte || []).forEach((s, j) => { if (s.wenn && !sicher(s.wenn)) aus.push(`${i}:${j}`); }));
    zustand.zahl = { ablauf: zustand.ablauf, aus };
  }
  function zaehlung() {
    const aus = new Set((zustand.zahl && zustand.zahl.aus) || []);
    let n = 0;
    let m = 0;
    teilDef().ablaeufe.forEach((a, i) => (a.schritte || []).forEach((s, j) => {
      if (aus.has(`${i}:${j}`)) return;
      m += 1;
      if (i < zustand.ablauf || (i === zustand.ablauf && j < zustand.schritt)) n += 1;
    }));
    return { n: Math.min(Math.max(1, m), n + 1), m: Math.max(1, m) };
  }

  /* Das Ziel bekommt den Text des Schritts als Beschreibung (aria-describedby). Nicht in einem Editor (contenteditable):
     ProseMirror zeichnet einen Knoten neu, sobald jemand ein Attribut daran setzt – dort genügt die Live-Region der Blase,
     die jeden Schritt ansagt (ansagen). */
  function zielBeschreiben(el) {
    if (zielEl && zielEl !== el) zielLoesen();
    zielEl = el;
    if (!el) return;
    if (el.isContentEditable || el.closest("[contenteditable]:not([contenteditable=false])")) return;
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
    ansage = document.createElement("p");
    ansage.className = "nur-vorlesen fuehrung-ansage";
    ansage.setAttribute("aria-live", "polite");
    document.body.append(rahmen, blase, ansage);
    window.addEventListener("scroll", lagePlanen, { capture: true, passive: true });
    // Rollst du selbst (Rad, Wischen, Tasten zum Rollen), holt lage() das Ziel dieses Schritts nicht zurück.
    const selbst = (e) => {
      if (e.type === "keydown" && (!/^(ArrowUp|ArrowDown|PageUp|PageDown|Home|End| )$/.test(e.key)
          || (e.target instanceof Element && e.target.closest("input, textarea, select, [contenteditable]")))) return;
      selbstGerollt = true;
    };
    for (const art of ["wheel", "touchmove", "keydown"]) window.addEventListener(art, selbst, { capture: true, passive: true });
    const eingabe = (e) => { if (!(e.target instanceof Element && e.target.closest(".fuehrung-blase"))) eingabeSeit = Date.now(); };
    for (const art of ["pointerdown", "keydown"]) window.addEventListener(art, eingabe, { capture: true, passive: true });
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
    delete blase.dataset.schritt;
    ansagen(`${kopf}: ${text}`);
    lage();
  }
  // Jede Schrittänderung in die Live-Region (Verbesserung V3) – kurz geleert, damit auch ein gleicher Text neu ankommt.
  function ansagen(text) {
    if (!ansage) return;
    ansage.textContent = "";
    const el = ansage;
    setTimeout(() => { if (ansage === el) el.textContent = text; }, 120);
  }
  /* Am Rechner klickst du, am Finger tippst du (Verbesserung V5): Die Übungsdateien schreiben „Tippe“ – ohne Touch-Zeiger
     sagt die Blase „Klicke“. */
  function wortlaut(text) {
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) return text;
    return String(text).replace(/\b([Tt])ipp(e|st)?\b/g, (_, t, endung) => `${t === "T" ? "K" : "k"}lick${endung || ""}`);
  }

  function schrittVerlassen() {
    laufNr += 1;
    aufraeumen.splice(0).forEach((f) => sicher(f));
    zielLoesen();
    fuehrung.bereit = false;
    nachgeholt = 0;
    selbstGerollt = false;
    engLeiste = false;
  }
  // Noch einmal, wenn die Seite doch bleibt (ein Seitenwechsel, der abbricht).
  const nochmal = (lauf) => { if (!umgeleitet) setTimeout(() => { if (lauf === laufNr) schrittZeigen(); }, 300); };

  async function schrittZeigen() {
    schrittVerlassen();
    const lauf = laufNr;
    const beginn = Date.now();
    const a = ablaufDef();
    if (!a) { sackgasse("Diese Übung gibt es hier noch nicht."); return; }
    // Läuft ein Seitenwechsel (die Aktion des Schritts führt auf eine andere Seite), wertet die Führung hier nichts mehr aus
    // – kein Überspringen, nichts speichern; die neue Seite zeigt den Schritt.
    if (seiteGehtGerade()) { nochmal(lauf); return; }
    await abwarten(lauf);
    if (lauf !== laufNr) return;
    if (seiteGehtGerade()) { nochmal(lauf); return; }
    const liste = a.schritte || [];
    while (zustand.schritt < liste.length && liste[zustand.schritt].wenn && !sicher(liste[zustand.schritt].wenn)) zustand.schritt += 1;
    zaehlungFesthalten();
    speichern();
    if (zustand.schritt >= liste.length) { ablaufFertig(); return; }
    const s = liste[zustand.schritt];
    fuehrung.ziel = s.ziel === null || s.ziel === undefined ? null : alsText(s.ziel);
    let el = null;
    if (s.ziel !== null && s.ziel !== undefined) {
      el = await warteAuf(() => (overlaySchliesst() || seiteGehtGerade() ? null : zielSuchen(s.ziel)), 5000);
      if (lauf !== laufNr) return;
      if (seiteGehtGerade()) { nochmal(lauf); return; }
      if (!el) { sackgasse(ausDemVerlauf ? ZURUECK_GEGANGEN : NICHT_WEITER); return; }
    }
    zielBeschreiben(el);
    const { n, m } = zaehlung();
    const knoepfe = [];
    const vorige = liste.slice(0, zustand.schritt).filter((x) => !x.wenn || sicher(x.wenn));
    if (vorige.length && !vorige[vorige.length - 1].warten) knoepfe.push({ text: "Zurück", klasse: "btn secondary", aktion: zurueck });
    if (s.datei) knoepfe.push({ text: "Übungsbild nehmen", klasse: "btn secondary fuehrung-bild", aktion: () => bildNehmen(s.datei) });
    // „Weiter“ grau umrandet: Der rote Hauptknopf im Bild gehört der Seite (Knopfsprache, Verbesserung V11).
    if (!s.warten) knoepfe.push({ text: "Weiter", klasse: "btn secondary fuehrung-weiter", aktion: () => weiter() });
    blaseZeigen(`Übung · Schritt ${n} von ${m}`, a.titel || "", wortlaut(s.text || ""), knoepfe);
    blase.dataset.schritt = `${zustand.ablauf}:${zustand.schritt}`;
    wachen(s, lauf);
    // Ins Bild holen und abwarten, bis das Ziel ruht (beruhigen) – erst dann ist der Schritt bereit.
    if (el) {
      el = await beruhigen(s, el, lauf);
      if (lauf !== laufNr) return;
      if (!el) { sackgasse(ausDemVerlauf ? ZURUECK_GEGANGEN : NICHT_WEITER); return; }
      zielBeschreiben(el);
    }
    lage();
    // Fokus: ohne Aktion auf „Weiter“, mit Aktion auf das Ziel (wenn fokussierbar), sonst auf den Text – nicht, wenn du
    // inzwischen selbst etwas tust (ein Menü geöffnet hast: der Fokus woanders schlösse es).
    const ae = document.activeElement;
    const selbstAmWerk = eingabeSeit > beginn || Boolean(ae && ae.closest && ae.closest("details.menue[open], .menue-schwebend"));
    const weiterKnopf = blase.querySelector(".fuehrung-weiter");
    if (selbstAmWerk) { /* Fokus bleibt */ }
    else if (weiterKnopf) weiterKnopf.focus({ preventScroll: true });
    else if (el && el.matches("a[href], button, input, select, textarea, summary, [tabindex], [contenteditable]") && !el.disabled) el.focus({ preventScroll: true });
    else blase.querySelector(".fuehrung-text").focus({ preventScroll: true });
    fuehrung.bereit = true;
    bereitSeit = Date.now();
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

  const NICHT_WEITER = "Hier geht es in der Übung nicht weiter.";
  // Zurück im Browser auf eine Seite eines früheren Schritts (Verbesserung V2): „Vor“ führt zum Schritt zurück.
  const ZURUECK_GEGANGEN = "Du bist im Browser zurückgegangen. Mit „Vor“ geht es beim letzten Schritt weiter – oder beginne den Ablauf neu.";
  function sackgasse(text) {
    schrittVerlassen();
    fuehrung.sackgasse = true;
    const a = ablaufDef();
    blaseZeigen("Übung", (a && a.titel) || "Übung", text, [{ text: "Ablauf neu beginnen", klasse: "btn secondary", aktion: neuBeginnen }]);
    blase.querySelector(".btn").focus({ preventScroll: true });
  }
  function neuBeginnen() {
    const t = teilDef();
    const n = zustand ? zustand.ablauf : 0;
    neuerAblauf(n);
    const start = t && t.ablaeufe[n] ? t.ablaeufe[n].start : E.start;
    umgeleitet = true;
    nachDemZurueck(() => zumStart(start, false, true));
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
      // Jeder Ablauf beginnt frisch: mit frischem Übungsbestand und neu geladener Startseite (auch bei gleicher Adresse).
      neuerAblauf(n);
      umgeleitet = true;
      nachDemZurueck(() => zumStart(t.ablaeufe[n].start, false, true));
      return;
    }
    geschafft();
  }

  function fuehrungWeg() {
    schrittVerlassen();
    for (const el of [blase, rahmen, ansage]) if (el) el.remove();
    blase = null;
    rahmen = null;
    ansage = null;
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
      ? `<button type="button" class="btn secondary" id="fg-spaeter">Nicht jetzt</button>
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
    S.confirm("Übung unterbrechen? Fortsetzen kannst du später im Profil unter „Einführungen“.", "Unterbrechen", "Weiter üben",
      { endgueltig: false }).then((ja) => {
      if (ja) { unterbrechen(); return; }
      if (!blase) return;
      blase.hidden = false;
      lage();
      const f = blase.querySelector(".fuehrung-weiter") || blase.querySelector(".fuehrung-text");
      if (f) f.focus({ preventScroll: true });
    });
  }

  if (UEBUNG) {
    ablageUmlegen();
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
      if (!DEF || !ablageUmgelegt) {
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
      // „Kurz“ nur, wenn sie es ist – mit den Teilen deiner Rollen kann sie länger dauern (Verbesserung V5).
      return { titel: `${minuten <= 5 ? "Kurze Übung" : "Übung"} ${E.zu}`,
               text: `Probier die wichtigsten Abläufe an Übungsdaten aus. ${E.bleibt} ${umfang}`,
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
