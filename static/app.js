/* Progressive enhancement for the Result Register.
   Every page works without this file: the list is filtered and sorted on the
   server from the query string, and a student link opens a full page with the
   marksheet panel already open. With it, filtering is instant and the panel
   opens beside the list without a page load. */
(function () {
  "use strict";

  // ---------- small shared helpers ----------
  function isTyping(el) {
    return el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
  }

  // Keep --header-h equal to the sticky top bar's real height (it grows when
  // the nav wraps on narrow screens), so the side panel sits just below it.
  var spine = document.querySelector(".spine");
  if (spine) {
    var setHeaderHeight = function () {
      document.documentElement.style.setProperty("--header-h", spine.offsetHeight + "px");
    };
    setHeaderHeight();
    if (window.ResizeObserver) new ResizeObserver(setHeaderHeight).observe(spine);
    else window.addEventListener("resize", setHeaderHeight);
  }

  document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () { select.form.submit(); });
  });

  document.querySelectorAll("[data-print]").forEach(function (btn) {
    btn.addEventListener("click", function () { window.print(); });
  });

  // ---------- upload: example button ----------
  var exampleBtn = document.querySelector("[data-load-example]");
  if (exampleBtn) {
    exampleBtn.addEventListener("click", function () {
      var area = document.getElementById("pasted-json");
      area.value = document.getElementById("example-json").textContent.trim();
      area.focus();
    });
  }

  // ---------- edit: show only the chosen optional subject ----------
  var optionalSelect = document.getElementById("optional-select");
  if (optionalSelect) {
    var syncOptional = function () {
      document.querySelectorAll("[data-optional-row]").forEach(function (row) {
        var on = row.getAttribute("data-optional-row") === optionalSelect.value;
        row.hidden = !on;
        row.querySelectorAll("input").forEach(function (input) { input.disabled = !on; });
      });
    };
    optionalSelect.addEventListener("change", syncOptional);
    syncOptional();
  }

  // ---------- ledger ----------
  var workspace = document.getElementById("workspace");
  if (!workspace) return;

  var form = document.getElementById("list-controls");
  var search = document.getElementById("search-input");
  var tbody = document.querySelector("#roster tbody");
  var rows = Array.prototype.slice.call(tbody.rows);
  var countEl = document.getElementById("list-count");
  var emptyEl = document.getElementById("list-empty");
  var pane = document.getElementById("detail-pane");
  var listPath = form.getAttribute("action");            // /d/<ds>/
  var studentPathRe = /\/s\/([^\/?#]+)\/?$/;
  var defaults = { q: "", sort: "roll", result: "all", cls: "" };
  var requestSeq = 0;

  function readView() {
    return {
      q: search.value.trim(),
      sort: form.elements.sort.value,
      result: form.elements.result.value,
      cls: form.elements.cls.value
    };
  }

  function writeView(view) {
    search.value = view.q;
    ["sort", "result", "cls"].forEach(function (k) {
      var el = form.elements[k];
      el.value = view[k];
      if (el.value !== view[k]) el.value = defaults[k];   // unknown option -> default
    });
  }

  function viewFromSearch(qs) {
    var params = new URLSearchParams(qs);
    var view = {};
    Object.keys(defaults).forEach(function (k) { view[k] = params.get(k) || defaults[k]; });
    return view;
  }

  function queryString(view) {
    var params = new URLSearchParams();
    Object.keys(defaults).forEach(function (k) {
      if (view[k] && view[k] !== defaults[k]) params.set(k, view[k]);
    });
    var s = params.toString();
    return s ? "?" + s : "";
  }

  function rowMatches(row, view) {
    if (view.cls && row.getAttribute("data-class") !== view.cls) return false;
    var letter = row.getAttribute("data-letter");
    var flags = row.getAttribute("data-flags").split(" ").filter(Boolean);
    switch (view.result) {
      case "pass": if (letter === "F") return false; break;
      case "fail": if (letter !== "F") return false; break;
      case "flagged": if (!flags.length) return false; break;
      case "optional": case "practical": case "absent":
        if (flags.indexOf(view.result) === -1) return false; break;
    }
    var hay = row.getAttribute("data-search");
    return view.q.toLowerCase().split(/\s+/).filter(Boolean).every(function (t) { return hay.indexOf(t) !== -1; });
  }

  function applyView(updateUrl) {
    var view = readView();
    var rankAttr = "data-rank-" + view.sort.replace(/_/g, "-");
    rows.sort(function (a, b) { return +a.getAttribute(rankAttr) - +b.getAttribute(rankAttr); });
    var frag = document.createDocumentFragment();
    var shown = 0;
    var qs = queryString(view);
    rows.forEach(function (row) {
      var ok = rowMatches(row, view);
      row.hidden = !ok;
      if (ok) shown++;
      var link = row.querySelector("a.student-link");
      link.setAttribute("href", listPath + "s/" + encodeURIComponent(row.getAttribute("data-id")) + qs);
      frag.appendChild(row);
    });
    tbody.appendChild(frag);
    countEl.textContent = "Showing " + shown + " of " + rows.length + " students";
    emptyEl.hidden = shown !== 0;
    pane.querySelectorAll("[data-close]").forEach(function (a) { a.setAttribute("href", listPath + qs); });
    if (updateUrl) {
      var path = window.location.pathname;
      history.replaceState(history.state, "", path + qs);
    }
  }

  var debounce;
  search.addEventListener("input", function () {
    clearTimeout(debounce);
    debounce = setTimeout(function () { applyView(true); }, 60);
  });
  form.addEventListener("change", function () { applyView(true); });
  form.addEventListener("submit", function (e) { e.preventDefault(); applyView(true); });

  document.getElementById("clear-filters").addEventListener("click", function (e) {
    e.preventDefault();
    writeView(defaults);
    applyView(true);
    search.focus();
  });

  // ---------- detail panel ----------
  function selectRow(id) {
    rows.forEach(function (row) {
      var on = row.getAttribute("data-id") === id;
      row.classList.toggle("is-selected", on);
      if (on) row.setAttribute("aria-current", "true"); else row.removeAttribute("aria-current");
    });
  }

  function selectedRow() {
    return tbody.querySelector("tr.is-selected");
  }

  function showStepButtons() {
    var group = pane.querySelector("[data-step-group]");
    if (group) group.hidden = false;
  }

  function openStudent(href, opts) {
    opts = opts || {};
    var url = new URL(href, window.location.href);
    var match = url.pathname.match(studentPathRe);
    if (!match) return;
    var id = decodeURIComponent(match[1]);
    var seq = ++requestSeq;

    workspace.classList.add("has-panel");
    pane.hidden = false;
    pane.setAttribute("aria-busy", "true");
    selectRow(id);
    if (!opts.keepContent) {
      pane.innerHTML = '<div class="panel-loading" role="status"><span class="spinner" aria-hidden="true"></span>Loading marksheet…</div>';
    } else {
      pane.classList.add("is-refreshing");
    }
    if (opts.push) history.pushState({ student: id }, "", url.pathname + url.search);

    var partial = new URL(url.href);
    partial.searchParams.set("partial", "1");
    fetch(partial.href, { headers: { "X-Requested-With": "fetch" } })
      .then(function (res) {
        if (!res.ok) throw new Error(res.status === 404 ? "This student no longer exists." : "The server answered " + res.status + ".");
        return res.text();
      })
      .then(function (html) {
        if (seq !== requestSeq) return;
        pane.innerHTML = html;
        pane.removeAttribute("aria-busy");
        pane.classList.remove("is-refreshing");
        pane.scrollTop = 0;
        showStepButtons();
        document.title = pane.querySelector("h1").textContent + " · Ledger · Bogura Secondary School";
        if (opts.focus !== false) {
          var title = pane.querySelector("#marksheet-title");
          if (title) title.focus({ preventScroll: true });
        }
        if (window.matchMedia("(max-width: 900px)").matches) workspace.scrollIntoView({ block: "start" });
      })
      .catch(function (err) {
        if (seq !== requestSeq) return;
        pane.removeAttribute("aria-busy");
        pane.classList.remove("is-refreshing");
        pane.innerHTML =
          '<div class="panel-error" role="alert"><p><strong>Couldn\'t load this marksheet.</strong> ' +
          (err && err.message ? err.message : "") + '</p>' +
          '<p><button type="button" class="btn btn-small" data-retry>Try again</button> ' +
          '<a class="btn btn-small" href="' + url.pathname + url.search + '">Open as a full page</a> ' +
          '<a class="btn btn-small" href="' + listPath + queryString(readView()) + '" data-close>Close</a></p></div>';
        pane.querySelector("[data-retry]").addEventListener("click", function () { openStudent(href, {}); });
      });
  }

  function closePanel(opts) {
    opts = opts || {};
    requestSeq++;
    var row = selectedRow();
    workspace.classList.remove("has-panel");
    pane.hidden = true;
    pane.innerHTML = "";
    selectRow(null);
    document.title = "Ledger · Bogura Secondary School";
    if (opts.push) history.pushState({}, "", listPath + queryString(readView()));
    if (row && !row.hidden) {
      var link = row.querySelector("a.student-link");
      link.focus({ preventScroll: true });
      row.scrollIntoView({ block: "nearest" });
    }
  }

  function step(dir) {
    var visible = rows.filter(function (r) { return !r.hidden; });
    if (!visible.length) return;
    var current = selectedRow();
    var i = visible.indexOf(current);
    var next = visible[i === -1 ? 0 : Math.min(visible.length - 1, Math.max(0, i + dir))];
    if (!next || next === current) return;
    next.scrollIntoView({ block: "nearest" });
    openStudent(next.querySelector("a.student-link").href, { push: true, keepContent: true, focus: false });
  }

  function plainClick(e) {
    return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
  }

  tbody.addEventListener("click", function (e) {
    if (!plainClick(e)) return;
    var row = e.target.closest("tr");
    if (!row) return;
    var link = row.querySelector("a.student-link");
    e.preventDefault();
    openStudent(link.href, { push: true });
  });

  pane.addEventListener("click", function (e) {
    if (!plainClick(e)) return;
    var close = e.target.closest("[data-close]");
    if (close) { e.preventDefault(); closePanel({ push: true }); return; }
    var stepBtn = e.target.closest("[data-step]");
    if (stepBtn) step(+stepBtn.getAttribute("data-step"));
  });

  document.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    var typing = isTyping(document.activeElement);
    if (e.key === "/" && !typing) {
      e.preventDefault();
      search.focus();
      search.select();
      return;
    }
    if (e.key === "Escape") {
      if (document.activeElement === search && search.value) { search.value = ""; applyView(true); return; }
      if (workspace.classList.contains("has-panel")) { e.preventDefault(); closePanel({ push: true }); }
      return;
    }
    if (typing || !workspace.classList.contains("has-panel")) return;
    if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); step(1); }
    else if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); step(-1); }
  });

  window.addEventListener("popstate", function () {
    writeView(viewFromSearch(window.location.search));
    applyView(false);
    var match = window.location.pathname.match(studentPathRe);
    if (match) openStudent(window.location.href, { focus: false });
    else if (workspace.classList.contains("has-panel")) closePanel({});
  });

  // Initial state: the server already rendered filters, order and any open panel.
  if (workspace.classList.contains("has-panel")) {
    showStepButtons();
    var sel = selectedRow();
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }
  history.replaceState({}, "", window.location.pathname + window.location.search);
})();
