/*
 * ComplianceIQ marketing site — minimal vanilla JS.
 * Responsibilities:
 *   1. Wire off-site CTAs to their configured destinations:
 *        [data-app-link]    -> COMPLIANCEIQ_APP_URL  (deployed app / sign in)
 *        [data-repo-link]   -> COMPLIANCEIQ_REPO_URL (public GitHub repo)
 *        [data-repo-deploy] -> repo + deployment guide (infra deployment)
 *   2. Mobile nav toggle (accessible: aria-expanded + Escape + outside click).
 *   3. Current year in the footer.
 * Written in a functional, side-effect-isolated style. No dependencies.
 */
(function () {
  "use strict";

  var DEFAULT_APP_URL = "https://app.example.com";
  var DEFAULT_REPO_URL = "https://github.com/warrendt/compliance-iq";
  var DEPLOY_PATH = "/blob/main/app/DEPLOYMENT.md";

  // --- 1. Link wiring -----------------------------------------------------
  var trimSlash = function (s) { return s.replace(/\/+$/, ""); };
  var appUrl = (window.COMPLIANCEIQ_APP_URL || DEFAULT_APP_URL).trim();
  var repoUrl = trimSlash((window.COMPLIANCEIQ_REPO_URL || DEFAULT_REPO_URL).trim());

  var wire = function (selector, href, external) {
    Array.prototype.forEach.call(
      document.querySelectorAll(selector),
      function (el) {
        el.setAttribute("href", href);
        el.setAttribute("rel", external ? "noopener noreferrer" : "noopener");
        if (external) el.setAttribute("target", "_blank");
      }
    );
  };

  wire("[data-app-link]", appUrl, false);          // sign in / start mapping
  wire("[data-repo-link]", repoUrl, true);         // resources -> repo
  wire("[data-repo-deploy]", repoUrl + DEPLOY_PATH, true); // get started -> deploy guide

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
