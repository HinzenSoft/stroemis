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

  function showErr(msg) { err.textContent = msg; err.classList.remove("hidden"); }
  function busy(form, on) { form.querySelector("button[type=submit]").disabled = on; }

  async function submit(form, path, body, after) {
    err.classList.add("hidden");
    busy(form, true);
    try {
      const data = await S.api(path, { method: "POST", body });
      after(data);
    } catch (e) {
      showErr(e.message);
    } finally {
      busy(form, false);
    }
  }

  const fLogin = document.getElementById("f-login");
  if (fLogin) fLogin.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(fLogin, "/api/auth/login", { email: fLogin.email.value, password: fLogin.password.value },
      () => { location.href = (next.startsWith("/") && !next.startsWith("//")) ? next : "/"; });
  });

  const fReg = document.getElementById("f-register");
  if (fReg) fReg.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(fReg, "/api/auth/register", {
      name: fReg.name.value, gliederung: fReg.gliederung.value, email: fReg.email.value, password: fReg.password.value,
      reason: fReg.reason.value,
    }, (d) => {
      if (d.pending) fReg.innerHTML = `<p class="notice">${S.esc(d.message)}</p>`;
      else location.href = "/";
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
    if (fReset.password.value !== fReset.password2.value) return showErr("Die Passwörter stimmen nicht überein.");
    submit(fReset, "/api/auth/reset", { token, password: fReset.password.value }, () => {
      S.toast("Passwort gespeichert");
      history.replaceState(null, "", location.pathname);
      location.href = "/";
    });
  });
})();


/* Slideshow auf der Anmeldeseite: zufällige Bilder aus den Spots, langsam wandernd und überblendet */
(function () {
  const box = document.getElementById("slideshow");
  if (!box || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const slides = box.querySelectorAll(".slide");
  let images = [], i = 0, active = 0;
  function next() {
    if (!images.length) return;
    const img = new Image();
    img.onload = () => {
      active = 1 - active;
      const el = slides[active];
      el.style.backgroundImage = `url("${img.src}")`;
      el.classList.remove("pan-a", "pan-b");
      void el.offsetWidth; // Animation neu starten
      el.classList.add(i % 2 ? "pan-a" : "pan-b", "show");
      slides[1 - active].classList.remove("show");
      i = (i + 1) % images.length;
    };
    img.src = images[i].url;
  }
  fetch("/api/public/slideshow").then((r) => r.json()).then((d) => {
    images = (d.images || []).sort(() => Math.random() - 0.5);
    if (images.length) { box.classList.add("on"); next(); setInterval(next, 9000); }
  }).catch(() => {});
})();
