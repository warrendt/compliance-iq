/*
 * ComplianceIQ — article page behaviour (/ksa). Vanilla JS, no dependencies.
 *   1. Reading progress bar
 *   2. Table-of-contents scrollspy (highlights the current section)
 *   3. Click-to-zoom figures in an accessible <dialog>
 *   4. Copy buttons on code blocks
 */
(function () {
  "use strict";

  // --- 1. Progress -----------------------------------------------------
  var bar = document.getElementById("progressBar");
  var article = document.getElementById("article");
  var onScroll = function () {
    if (!bar || !article) return;
    var rect = article.getBoundingClientRect();
    var total = article.offsetHeight - window.innerHeight;
    var done = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
    bar.style.width = (total > 0 ? (done / total) * 100 : 0) + "%";
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();

  // --- 2. Scrollspy ----------------------------------------------------
  var links = Array.prototype.slice.call(document.querySelectorAll(".a-toc a[href^='#']"));
  var byId = {};
  links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
  var headings = Array.prototype.slice.call(document.querySelectorAll(".a-body h2[id], .a-body h3[id]"))
    .filter(function (h) { return byId[h.id]; });

  var setActive = function (id) {
    links.forEach(function (a) { a.classList.remove("is-active"); });
    Array.prototype.forEach.call(document.querySelectorAll(".a-toc li.is-open"), function (li) { li.classList.remove("is-open"); });
    var link = byId[id];
    if (!link) return;
    link.classList.add("is-active");
    var li = link.closest(".a-toc ol > li");
    if (li) li.classList.add("is-open");
  };

  if ("IntersectionObserver" in window && headings.length) {
    var current = null;
    var io = new IntersectionObserver(function () {
      var offset = 120;
      var active = headings[0];
      headings.forEach(function (h) { if (h.getBoundingClientRect().top - offset <= 0) active = h; });
      if (active && active.id !== current) { current = active.id; setActive(current); }
    }, { rootMargin: "0px 0px -60% 0px", threshold: [0, 1] });
    headings.forEach(function (h) { io.observe(h); });
    window.addEventListener("scroll", function () {
      var offset = 120;
      var active = headings[0];
      headings.forEach(function (h) { if (h.getBoundingClientRect().top - offset <= 0) active = h; });
      if (active && active.id !== current) { current = active.id; setActive(current); }
    }, { passive: true });
  }

  // --- 3. Lightbox -----------------------------------------------------
  var dialog = document.getElementById("lightbox");
  var dImg = document.getElementById("lightboxImg");
  var dCap = document.getElementById("lightboxCap");
  if (dialog && typeof dialog.showModal === "function") {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".zoom");
      if (!btn) return;
      var img = btn.querySelector("img");
      if (!img) return;
      dImg.src = img.currentSrc || img.src;
      dImg.alt = img.alt;
      var fig = btn.closest("figure");
      var cap = fig && fig.querySelector("figcaption");
      dCap.textContent = cap ? cap.textContent : img.alt;
      dialog.showModal();
    });
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog || e.target.closest(".lightbox__close")) dialog.close();
    });
  } else {
    // No <dialog> support: open the image directly.
    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".zoom");
      var img = btn && btn.querySelector("img");
      if (img) window.location.href = img.src;
    });
  }

  // --- 4. Copy code ----------------------------------------------------
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".code__copy");
    if (!btn) return;
    var code = btn.closest(".code").querySelector("code");
    var done = function () {
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = "Copy"; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code.textContent).then(done, function () {});
    }
  });
})();
