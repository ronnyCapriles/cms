/* Click-to-copy shortcodes, live markdown preview, and drag-to-reorder for
   inlines with an `order` column. No dependencies: the origin is IPv6 only
   and serves no third-party script. */
(function () {
  "use strict";

  function csrfToken(el) {
    var form = el && el.closest ? el.closest("form") : null;
    var input = form && form.querySelector("input[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      var args = arguments, self = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(self, args); }, wait);
    };
  }

  /* Copy buttons */

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // A plain-HTTP origin blocks the async clipboard.
    return new Promise(function (resolve, reject) {
      var scratch = document.createElement("textarea");
      scratch.value = text;
      scratch.setAttribute("readonly", "");
      scratch.style.position = "fixed";
      scratch.style.opacity = "0";
      document.body.appendChild(scratch);
      scratch.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(scratch);
      if (ok) { resolve(); } else { reject(new Error("copy failed")); }
    });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-cms-copy]");
    if (!button) return;
    event.preventDefault();
    copyText(button.getAttribute("data-cms-copy")).then(function () {
      button.setAttribute("data-copied", "1");
      setTimeout(function () { button.removeAttribute("data-copied"); }, 1400);
    }).catch(function () {
      // Select it instead, so it can still be copied by hand.
      var range = document.createRange();
      range.selectNodeContents(button);
      var selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    });
  });

  /* Markdown preview */

  var PREVIEW_PREF = "cms-admin:markdown-preview";

  function preferenceOn() {
    // A private window throws on access.
    try { return localStorage.getItem(PREVIEW_PREF) !== "0"; }
    catch (e) { return true; }
  }

  function savePreference(on) {
    try { localStorage.setItem(PREVIEW_PREF, on ? "1" : "0"); }
    catch (e) {}
  }

  function buildPreview(textarea) {
    var url = textarea.getAttribute("data-cms-preview-url");
    if (!url) return;

    var pk = textarea.getAttribute("data-cms-preview-pk") || "";

    var wrap = document.createElement("div");
    wrap.className = "cms-md";

    var bar = document.createElement("div");
    bar.className = "cms-md__bar";

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "cms-md__toggle";
    toggle.textContent = "Preview";

    var status = document.createElement("span");
    status.className = "cms-md__status";

    bar.appendChild(toggle);
    bar.appendChild(status);

    var pane = document.createElement("div");
    pane.className = "cms-md__preview";
    pane.setAttribute("aria-live", "polite");

    textarea.parentNode.insertBefore(wrap, textarea);
    wrap.appendChild(bar);
    wrap.appendChild(textarea);
    wrap.appendChild(pane);

    var form = textarea.closest("form");
    var languageSelect = form && form.querySelector("#id_language");
    var lastRendered = null;

    var render = debounce(function () {
      if (!wrap.classList.contains("cms-md--split")) return;

      var text = textarea.value;
      var lang = languageSelect ? languageSelect.value : "";
      var key = lang + "\u0000" + text;
      if (key === lastRendered) return;

      status.textContent = "rendering";
      status.removeAttribute("data-state");

      var body = new URLSearchParams();
      body.set("text", text);
      body.set("lang", lang);
      body.set("pk", pk);

      fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": csrfToken(textarea),
          "X-Requested-With": "XMLHttpRequest"
        },
        body: body.toString()
      }).then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      }).then(function (data) {
        // Rendered by our own code, so it is trusted markup.
        pane.innerHTML = data.html ||
          "<p class=\"cms-empty\">Nothing to preview yet.</p>";
        lastRendered = key;
        status.textContent = "up to date";
      }).catch(function (error) {
        status.textContent = "preview unavailable (" + error.message + ")";
        status.setAttribute("data-state", "error");
      });
    }, 400);

    function setOpen(open, remember) {
      wrap.classList.toggle("cms-md--split", open);
      toggle.setAttribute("aria-pressed", open ? "true" : "false");
      pane.hidden = !open;
      if (remember) savePreference(open);
      if (open) { lastRendered = null; render(); }
      else { status.textContent = ""; }
    }

    toggle.addEventListener("click", function () {
      setOpen(!wrap.classList.contains("cms-md--split"), true);
    });
    textarea.addEventListener("input", render);
    if (languageSelect) languageSelect.addEventListener("change", render);

    setOpen(preferenceOn(), false);
  }

  /* Drag to reorder */

  function orderInput(row) {
    return row.querySelector("input[name$='-order']");
  }

  function rowsOf(tbody) {
    return Array.prototype.filter.call(
      tbody.querySelectorAll("tr.form-row"),
      function (row) { return !row.classList.contains("empty-form"); }
    );
  }

  function renumber(tbody) {
    // Gaps of ten leave room to type a value between two rows.
    rowsOf(tbody).forEach(function (row, index) {
      var input = orderInput(row);
      if (input) input.value = (index + 1) * 10;
    });
  }

  function makeSortable(tbody) {
    var dragging = null;

    function prepare(row) {
      if (row.dataset.cmsSortable === "1") return;
      if (row.classList.contains("empty-form")) return;
      if (!orderInput(row)) return;

      var cell = row.querySelector("td.original") || row.cells[0];
      if (!cell) return;

      var handle = document.createElement("span");
      handle.className = "cms-handle";
      handle.title = "Drag to reorder";
      handle.setAttribute("aria-hidden", "true");
      // Appended, never prepended: the label in td.original is positioned
      // absolutely with no `top`, so anything ahead of it pushes it down.
      cell.appendChild(handle);

      // Only the handle arms the row, so cell text stays selectable.
      handle.addEventListener("mousedown", function () { row.draggable = true; });
      handle.addEventListener("touchstart", function () { row.draggable = true; },
                              { passive: true });
      row.addEventListener("dragend", function () { row.draggable = false; });

      row.dataset.cmsSortable = "1";
    }

    tbody.addEventListener("dragstart", function (event) {
      var row = event.target.closest("tr.form-row");
      if (!row || !row.draggable) return;
      dragging = row;
      row.classList.add("cms-dragging");
      event.dataTransfer.effectAllowed = "move";
      // Firefox will not start a drag with an empty data transfer.
      event.dataTransfer.setData("text/plain", "");
    });

    tbody.addEventListener("dragover", function (event) {
      if (!dragging) return;
      var row = event.target.closest("tr.form-row");
      if (!row || row === dragging || row.classList.contains("empty-form")) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";

      rowsOf(tbody).forEach(function (r) { r.classList.remove("cms-drop-target"); });
      row.classList.add("cms-drop-target");

      var box = row.getBoundingClientRect();
      var below = (event.clientY - box.top) > box.height / 2;
      tbody.insertBefore(dragging, below ? row.nextSibling : row);
    });

    tbody.addEventListener("drop", function (event) {
      if (dragging) event.preventDefault();
    });

    tbody.addEventListener("dragend", function () {
      if (!dragging) return;
      dragging.classList.remove("cms-dragging");
      rowsOf(tbody).forEach(function (r) { r.classList.remove("cms-drop-target"); });
      dragging = null;
      renumber(tbody);
    });

    return function () { rowsOf(tbody).forEach(prepare); };
  }

  var sortables = [];

  function initSortables(root) {
    root.querySelectorAll("fieldset.cms-sortable table tbody").forEach(function (tbody) {
      if (tbody.dataset.cmsSortableInit === "1") return;
      tbody.dataset.cmsSortableInit = "1";
      var prepareAll = makeSortable(tbody);
      prepareAll();
      sortables.push(prepareAll);
    });
  }

  /* Keep a wide inline inside its box */

  function wrapWideTables(root) {
    root.querySelectorAll(".inline-group fieldset.module > table").forEach(function (table) {
      if (table.parentNode.classList.contains("cms-tablewrap")) return;
      var wrap = document.createElement("div");
      wrap.className = "cms-tablewrap";
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  /* Boot */

  function init() {
    document.querySelectorAll("textarea[data-cms-preview-url]").forEach(buildPreview);
    wrapWideTables(document);
    initSortables(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Django fires this natively when "Add another" clones a row.
  document.addEventListener("formset:added", function () {
    sortables.forEach(function (prepareAll) { prepareAll(); });
  });
})();
