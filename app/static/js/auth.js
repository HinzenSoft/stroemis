(function () {
  const shell = document.querySelector(".login-form");
  const next = shell.dataset.next || "/";
  const err = document.getElementById("err");

  /* Der Reset-Token steht ausschließlich im Fragment (#token=…) und erreicht den Server nicht –
     als Abfrage (?token=…) landete er im Zugriffsprotokoll und im Referer. */
  function resetToken() {
    // Der Token bleibt im Fragment stehen, bis das Passwort gesetzt ist: Nach einem Fehlversuch
    // oder Neuladen wäre er sonst weg, und die Seite meldete „der Link fehlt“.
    return new URLSearchParams(location.hash.slice(1)).get("token") || "";
  }
  const token = shell.dataset.mode === "reset" ? resetToken() : "";

  /* Fehlermeldung (Gerätetest B7): #err ist role="alert" und steht immer im Dokument – leer nimmt sie keinen Platz ein
     (app.css). So sagt die Vorlesehilfe den Satz an, sobald er erscheint; die Felder verweisen mit aria-describedby
     darauf (login.html). Der Fokus ging mit dem gesperrten Knopf verloren – er kommt aufs Feld, das man jetzt braucht
     (beim Anmelden das Passwort, markiert zum Neutippen), sonst zurück auf den Knopf. */
  function showErr(msg, feld) {
    err.textContent = msg;
    const form = err.closest("form");
    const knopf = form && form.querySelector("button[type=submit]");
    const ae = document.activeElement;
    if (feld) { feld.focus(); if (feld.select) feld.select(); }
    else if (knopf && (!ae || ae === document.body || ae === knopf)) knopf.focus();
  }
  // Nach einer erfolgreichen Kontoanfrage ersetzt die Antwort das Formular samt Knopf – dann gibt es nichts zu entsperren.
  function busy(form, on) { const k = form.querySelector("button[type=submit]"); if (k) k.disabled = on; }

  async function submit(form, path, body, after, feld) {
    err.textContent = "";
    busy(form, true);
    let fehler = null;
    try {
      const data = await S.api(path, { method: "POST", body });
      after(data);
    } catch (e) {
      fehler = e;
    } finally {
      busy(form, false);
    }
    // Erst nach dem Entsperren: Ein gesperrter Knopf nimmt keinen Fokus an.
    if (fehler) showErr(fehler.message, feld);
  }
  // Nach dem Anmelden ersetzt die Zielseite die Anmeldeseite im Verlauf (Gerätetest B15): Zurück führte sonst wieder auf
  // ein leeres Anmeldeformular, obwohl die Sitzung steht.
  const ziel = (adresse) => location.replace(adresse);

  const fLogin = document.getElementById("f-login");
  if (fLogin) fLogin.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(fLogin, "/api/auth/login", { email: fLogin.email.value, password: fLogin.password.value },
      () => { ziel((next.startsWith("/") && !next.startsWith("//")) ? next : "/"); }, fLogin.password);
  });

  const fReg = document.getElementById("f-register");
  if (fReg) fReg.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(fReg, "/api/auth/register", {
      name: fReg.name.value, gliederung: fReg.gliederung.value, email: fReg.email.value, password: fReg.password.value,
      reason: fReg.reason.value,
    }, (d) => {
      if (d.pending) {
        fReg.innerHTML = `<p class="notice">${S.esc(d.message)}</p>`;
        // Die Antwort sagt schon, dass man im Spam-Ordner nachsehen soll – der Satz darunter fiele doppelt.
        const spam = document.getElementById("reg-spam");
        if (spam) spam.hidden = true;
      }
      else ziel("/");
    });
  });

  const fForgot = document.getElementById("f-forgot");
  if (fForgot) fForgot.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(fForgot, "/api/auth/forgot", { email: fForgot.email.value }, (d) => {
      fForgot.innerHTML = `<p class="notice">${S.esc(d.message)}</p>`;
    });
  });

  const fReset = document.getElementById("f-reset");
  const noToken = document.getElementById("no-token");
  if (fReset) (token ? fReset : noToken).classList.remove("hidden");
  if (fReset) fReset.addEventListener("submit", (e) => {
    e.preventDefault();
    if (fReset.password.value !== fReset.password2.value) return showErr("Die Passwörter stimmen nicht überein.", fReset.password2);
    submit(fReset, "/api/auth/reset", { token, password: fReset.password.value }, () => {
      S.toast("Passwort gespeichert");
      history.replaceState(null, "", location.pathname);
      ziel("/");
    });
  });
})();


/* Slideshow auf der Anmeldeseite: zufällige Bilder aus den Spots, langsam wandernd und überblendet.
   Datenmenge (Gerätetest 01.11.2026, B1): Geladen wird nur das gezeigte und das nächste Bild – das nächste erst, wenn
   das gezeigte steht –, in der kleinen WebP-Fassung des Servers (/media/slide/…). Los geht es erst, wenn die Fläche im
   Bild ist (am Telefon steht sie unter dem Formular), und in einem verborgenen Reiter wird nicht weitergeblättert. */
(function () {
  const box = document.getElementById("slideshow");
  if (!box || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const slides = box.querySelectorAll(".slide");
  let images = [], i = 0, active = 0, vorrat = null;
  function laden(n) {
    const img = new Image();
    img.decoding = "async";
    img.src = images[n].url;
    return { n, img };
  }
  function zeigen(img, n) {
    active = 1 - active;
    const el = slides[active];
    el.style.backgroundImage = `url("${img.src}")`;
    el.classList.remove("pan-a", "pan-b");
    void el.offsetWidth; // Animation neu starten
    el.classList.add(n % 2 ? "pan-a" : "pan-b", "show");
    slides[1 - active].classList.remove("show");
  }
  function next() {
    if (!images.length || document.hidden) return;
    const n = i;
    const { img } = vorrat && vorrat.n === n ? vorrat : laden(n);
    vorrat = null;
    i = (n + 1) % images.length;
    const fertig = () => {
      zeigen(img, n);
      if (images.length > 1) vorrat = laden(i);        // das nächste – mehr nicht
    };
    if (img.complete && img.naturalWidth) fertig();
    else { img.onload = fertig; img.onerror = () => { /* fehlt: beim nächsten Takt das folgende */ }; }
  }
  function starten() {
    fetch("/api/public/slideshow").then((r) => r.json()).then((d) => {
      images = (d.images || []).sort(() => Math.random() - 0.5);
      if (images.length) { box.classList.add("on"); next(); setInterval(next, 9000); }
    }).catch(() => {});
  }
  if (!window.IntersectionObserver) { starten(); return; }
  const beobachter = new IntersectionObserver((eintraege) => {
    if (!eintraege.some((e) => e.isIntersecting)) return;
    beobachter.disconnect();
    starten();
  });
  beobachter.observe(box);
})();
