/*
 * ComplianceIQ marketing site — minimal vanilla JS.
 * Responsibilities:
 *   1. Wire every [data-app-link] CTA to the configured app URL.
 *   2. Mobile nav toggle (accessible: aria-expanded + Escape + outside click).
 *   3. Current year in the footer.
 * Written in a functional, side-effect-isolated style. No dependencies.
 */
(function () {
  "use strict";

  var DEFAULT_APP_URL = "https://app.example.com";

  // --- 1. App-link wiring -------------------------------------------------
  var appUrl = (window.COMPLIANCEIQ_APP_URL || DEFAULT_APP_URL).trim();
  Array.prototype.forEach.call(
    document.querySelectorAll("[data-app-link]"),
    function (el) {
      el.setAttribute("href", appUrl);
      el.setAttribute("rel", "noopener");
    }
  );

  // --- 2. Mobile nav ------------------------------------------------------
  var toggle = document.getElementById("navToggle");
  var menu = document.getElementById("navMenu");

  var setMenu = function (open) {
    if (!toggle || !menu) return;
    toggle.setAttribute("aria-expanded", String(open));
    menu.classList.toggle("is-open", open);
    document.body.classList.toggle("nav-open", open);
  };

  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      setMenu(toggle.getAttribute("aria-expanded") !== "true");
    });

    // Close after choosing a link (single-page anchors).
    menu.addEventListener("click", function (e) {
      if (e.target.closest("a")) setMenu(false);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setMenu(false);
    });

    document.addEventListener("click", function (e) {
      if (
        menu.classList.contains("is-open") &&
        !menu.contains(e.target) &&
        !toggle.contains(e.target)
      ) {
        setMenu(false);
      }
    });
  }

  // --- 3. Footer year -----------------------------------------------------
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
})();
