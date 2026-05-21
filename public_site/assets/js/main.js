/* ============================================================
   ClarityOS public site — main.js
   ------------------------------------------------------------
   Vanilla JS only. No frameworks, no bundlers, no external
   dependencies. Loaded with `defer` so it runs after the DOM
   is parsed.

   Responsibilities:
     1. Mobile nav toggle (open/close primary nav).
     2. Close primary nav on outside click + Escape.
     3. Static contact form: prevent submission, surface a
        non-functional status note. Comet wires the real
        backend.
   ============================================================ */
(function () {
  "use strict";

  // ----------------------------------------------------------
  // Nav toggle
  // ----------------------------------------------------------
  var toggle = document.querySelector(".nav-toggle");
  var navList = document.getElementById("primary-nav");

  if (toggle && navList) {
    toggle.addEventListener("click", function () {
      var open = navList.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    // Close on Escape.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && navList.classList.contains("is-open")) {
        navList.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });

    // Close on outside click.
    document.addEventListener("click", function (e) {
      if (!navList.classList.contains("is-open")) return;
      var t = e.target;
      if (t === toggle || toggle.contains(t)) return;
      if (navList.contains(t)) return;
      navList.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    });
  }

  // ----------------------------------------------------------
  // Contact form (static — Comet wires the real handler)
  // ----------------------------------------------------------
  var form = document.querySelector(".contact-form[data-static='true']");
  if (form) {
    var status = form.querySelector("[data-role='contact-status']");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!status) return;
      status.textContent =
        "Form not wired. Please email hello@example.com with the same content.";
      status.classList.add("is-ok");
    });
  }
})();
