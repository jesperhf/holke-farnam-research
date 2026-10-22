// Business cycle tracker: draws the cycle curve, the history line and the
// readings table from data/cycle.json (written daily from FRED).
(function () {
  var PH = {
    E: { name: "Early expansion", short: "Early", c: "var(--early)", t: "var(--early-t)", center: 13, from: 0, to: 25,
      desc: "Output recovers from the trough. Credit loosens, inventories rebuild and profits rebound from a low base.",
      signals: "Fed easing or on hold at low rates; steep yield curve; unemployment high but falling.",
      sectors: "Financials, consumer discretionary, real estate, industrials." },
    M: { name: "Mid expansion", short: "Mid", c: "var(--mid)", t: "var(--mid-t)", center: 40, from: 25, to: 50,
      desc: "The longest phase. Growth is steady, policy moves toward neutral and earnings growth settles.",
      signals: "Moderate GDP growth; stable inflation; Fed near neutral; solid payroll growth.",
      sectors: "Information technology, communication services." },
    L: { name: "Late expansion", short: "Late", c: "var(--late)", t: "var(--late-t)", center: 62, from: 50, to: 74,
      desc: "Capacity runs tight. Inflation pressure builds, policy turns restrictive and growth begins to slow.",
      signals: "Fed hiking; inflation rising; commodity prices up; unemployment near its low; high long rates.",
      sectors: "Energy, materials, health care, consumer staples." },
    C: { name: "Contraction", short: "Contraction", c: "var(--contr)", t: "var(--contr-t)", center: 87, from: 74, to: 100,
      desc: "Output falls and unemployment rises quickly. Earnings decline, credit tightens and the Fed cuts.",
      signals: "Unemployment up 0.5 points from its low; payrolls negative; activity indexes deeply negative.",
      sectors: "Consumer staples, utilities, health care." }
  };
  var ORDER = ["E", "M", "L", "C"];
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, parent) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function txt(node, s) { node.textContent = s; return node; }
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function phaseAt(p) { return p < 25 ? "E" : p < 50 ? "M" : p < 74 ? "L" : "C"; }
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function fmtDate(iso) { var m = /^(\d{4})-(\d{2})-?(\d{2})?/.exec(iso || ""); if (!m) return iso || ""; return MONTHS[+m[2] - 1] + (m[3] ? " " + (+m[3]) + "," : "") + " " + m[1]; }
  function label(pos) {
    var k = phaseAt(pos), edges = [25, 50, 74], near = null;
    for (var i = 0; i < edges.length; i++) if (Math.abs(pos - edges[i]) < 4) near = edges[i];
    if (near === null) return PH[k].name;
    var a = phaseAt(near - 1), b = phaseAt(near + 1);
    return b === "C" ? "Late expansion, turning" : PH[a].short + " to " + PH[b].short.toLowerCase() + " transition";
  }

  // Stylized cycle curve: trough at 0 and 100, peak at 72.
  function curve(svg, opts) {
    var X0 = opts.x0, X1 = opts.x1, YB = opts.yb, AMP = opts.amp;
    var px = function (p) { return X0 + (X1 - X0) * p / 100; };
    var lvl = function (p) { return p <= 72 ? (1 - Math.cos(Math.PI * p / 72)) / 2 : (1 + Math.cos(Math.PI * (p - 72) / 28)) / 2; };
    var py = function (p) { return YB - AMP * lvl(p); };
    return { px: px, py: py, draw: function (bands) {
      var g = el("g", {}, svg);
      if (bands) ORDER.forEach(function (k) {
        var ph = PH[k];
        el("rect", { x: px(ph.from), y: opts.top, width: px(ph.to) - px(ph.from), height: YB - opts.top + 10, fill: ph.t }, g);
        txt(el("text", { x: (px(ph.from) + px(ph.to)) / 2, y: opts.top + 18, "text-anchor": "middle", "font-size": opts.fs, "font-weight": 600, fill: ph.c }, g), opts.small ? ph.short.toUpperCase() : ph.name.toUpperCase());
      });
      el("line", { x1: X0, x2: X1, y1: YB, y2: YB, stroke: "var(--rule)" }, g);
      var d = "";
      for (var i = 0; i <= 200; i++) { var p = i / 2; d += (i ? "L" : "M") + px(p).toFixed(1) + " " + py(p).toFixed(1); }
      el("path", { d: d, fill: "none", stroke: "var(--ink)", "stroke-width": opts.small ? 2 : 2.5, "stroke-linecap": "round" }, g);
      return g;
    } };
  }
  function dot(svg, c, pos, tagText, big) {
    var x = c.px(pos), y = c.py(pos), g = el("g", {}, svg);
    el("circle", { cx: x, cy: y, r: big ? 16 : 11, fill: "var(--ink)", opacity: 0.12 }, g);
    el("circle", { cx: x, cy: y, r: big ? 8.5 : 6, fill: "var(--ink)", stroke: "var(--surface)", "stroke-width": 3 }, g);
    if (tagText) {
      var w = tagText.length * 7.6 + 18, tx = Math.max(10, Math.min(990 - w, x - w / 2)), ty = y - 50 < 50 ? y + 20 : y - 44;
      el("rect", { x: tx, y: ty, width: w, height: 26, rx: 4, fill: "var(--ink)" }, g);
      txt(el("text", { x: tx + 9, y: ty + 17.5, "font-size": 13, "font-weight": 500, fill: "var(--surface)" }, g), tagText);
    }
  }

  function renderGauge(data) {
    var svg = $("gauge-svg"); if (!svg) return;
    var L = data.latest || {};
    if (L.position == null) return;
    var c = curve(svg, { x0: 14, x1: 386, yb: 118, amp: 84, top: 8, fs: 10.5, small: true });
    c.draw(true);
    dot(svg, c, L.position, null, false);
    var k = phaseAt(L.position);
    var ph = $("gauge-phase"); ph.textContent = label(L.position); ph.style.color = PH[k].c;
    $("gauge-meta").textContent = "Position " + Math.round(L.position) + " of 100 · " + L.counts[k] + " of " + L.reporting + " indicators agree · " + (data.seed ? "reading of " + fmtDate(L.asOf) : "updated " + fmtDate((data.generated || "").slice(0, 10)));
  }

  function showPhase(k, current) {
    var card = $("phase-card"); if (!card) return;
    var ph = PH[k];
    card.style.setProperty("--pc", ph.c);
    $("pc-eyebrow").textContent = current ? "Current phase" : "Phase guide";
    $("pc-title").textContent = ph.name; $("pc-title").style.color = ph.c;
    $("pc-desc").textContent = ph.desc; $("pc-signals").textContent = ph.signals; $("pc-sectors").textContent = ph.sectors;
  }

  function renderTracker(data) {
    var svg = $("cycle"); if (!svg) return;
    var L = data.latest || {};
    if (data.seed && $("seed-banner")) { $("seed-banner").hidden = false; $("seed-banner").textContent = data.seedNote || ""; }
    $("v-asof").textContent = data.seed ? "Reading of " + fmtDate(L.asOf) : "Updated " + fmtDate((data.generated || "").slice(0, 10)) + " from FRED";
    if (L.position == null) { $("v-phase").textContent = "Not enough data"; return; }
    var k = phaseAt(L.position);
    var vp = $("v-phase"); vp.textContent = label(L.position); vp.style.color = PH[k].c;
    $("v-summary").textContent = L.reporting + " of " + L.indicators.length + " indicators report. " +
      ORDER.filter(function (q) { return L.counts[q]; }).map(function (q) { return L.counts[q] + " point to " + PH[q].name.toLowerCase(); }).join(", ") + ".";
    $("m-pos").textContent = Math.round(L.position);
    $("m-conf").textContent = L.counts[k] + " of " + L.reporting;
    $("m-cov").textContent = L.reporting + " of " + L.indicators.length;
    var split = $("split"); split.innerHTML = "";
    ORDER.forEach(function (q) { if (!L.counts[q]) return; var i = document.createElement("i"); i.style.width = (100 * L.counts[q] / L.reporting) + "%"; i.style.background = PH[q].c; i.title = PH[q].name + ": " + L.counts[q]; split.appendChild(i); });
    $("split-key").innerHTML = ORDER.map(function (q) { return '<span style="--c:' + PH[q].c + '">' + PH[q].short + " " + (L.counts[q] || 0) + "</span>"; }).join("");

    // Cycle curve with bands that explain each phase.
    var c = curve(svg, { x0: 40, x1: 960, yb: 270, amp: 190, top: 20, fs: 14, small: false });
    var g = c.draw(true);
    Array.prototype.forEach.call(g.querySelectorAll("rect"), function (r, i) {
      r.setAttribute("class", "band"); r.setAttribute("tabindex", "0"); r.setAttribute("role", "button"); r.setAttribute("aria-label", PH[ORDER[i]].name);
      var show = function () { showPhase(ORDER[i], ORDER[i] === k); };
      r.addEventListener("mouseenter", show); r.addEventListener("focus", show); r.addEventListener("click", show);
    });
    g.addEventListener("mouseleave", function () { showPhase(k, true); });
    [[0, "Trough"], [72, "Peak"], [100, "Trough"]].forEach(function (a) {
      el("circle", { cx: c.px(a[0]), cy: c.py(a[0]), r: 3.5, fill: "var(--ink)" }, svg);
      txt(el("text", { x: c.px(a[0]), y: a[0] === 72 ? c.py(a[0]) - 12 : 298, "text-anchor": a[0] === 0 ? "start" : a[0] === 100 ? "end" : "middle", "font-size": 12.5, fill: "var(--muted)" }, svg), a[1]);
    });
    var hist = data.history || [];
    hist.slice(-12, -1).forEach(function (h, i, arr) {
      el("circle", { cx: c.px(h.pos), cy: c.py(h.pos), r: 4.5, fill: "var(--surface)", stroke: "var(--muted)", "stroke-width": 1.5, opacity: 0.45 + 0.5 * (i + 1) / arr.length }, svg);
    });
    dot(svg, c, L.position, (data.seed ? fmtDate(L.asOf) : "Now") + " · " + Math.round(L.position), true);
    showPhase(k, true);

    // Readings table.
    $("rows").innerHTML = L.indicators.map(function (r) {
      var chip = r.vote ? '<span class="chip ' + r.vote + '">' + PH[r.vote].short + "</span>" : '<span class="chip pass">No reading</span>';
      return "<tr><td>" + esc(r.name) + (r.period ? '<span class="sub">' + esc(r.period) + "</span>" : "") + '</td><td class="num">' + esc(r.display || "n/a") +
        '</td><td class="num"><span class="sub" style="font-family:var(--f-data)">' + esc(r.context || "") + "</span></td><td>" + chip + '</td><td class="rule">' + esc(r.rule) +
        '</td><td><a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.series) + "</a></td></tr>";
    }).join("");

    renderHistory(data);
  }

  function renderHistory(data) {
    var svg = $("history"); if (!svg) return;
    var hist = data.history || [];
    if (hist.length < 24) { svg.parentNode.innerHTML = '<div class="empty">The history line appears after the first daily update from FRED. It plots this composite every month since 1990, with US recessions shaded.</div>'; return; }
    var W = 1000, H = 330, x0 = 54, x1 = 980, y0 = 18, y1 = 290;
    var t = function (m) { var p = m.split("-"); return +p[0] + (+p[1] - 1) / 12; };
    var a = t(hist[0].m), b = t(hist[hist.length - 1].m);
    var X = function (m) { return x0 + (t(m) - a) / (b - a) * (x1 - x0); };
    var Y = function (p) { return y1 - p / 100 * (y1 - y0); };
    ORDER.forEach(function (k) {
      el("rect", { x: x0, y: Y(PH[k].to), width: x1 - x0, height: Y(PH[k].from) - Y(PH[k].to), fill: PH[k].t }, svg);
      txt(el("text", { x: x0 - 8, y: (Y(PH[k].from) + Y(PH[k].to)) / 2 + 4, "text-anchor": "end", "font-size": 11, fill: PH[k].c, "font-weight": 600 }, svg), PH[k].short === "Contraction" ? "Contr." : PH[k].short);
    });
    (data.recessions || []).forEach(function (r) {
      var s = r[0], e = r[1] || hist[hist.length - 1].m;
      if (t(e) < a) return;
      var xs = X(t(s) < a ? hist[0].m : s), xe = X(e);
      el("rect", { x: xs, y: y0, width: Math.max(2, xe - xs), height: y1 - y0, fill: "var(--rec)" }, svg);
    });
    for (var yr = Math.ceil(a / 5) * 5; yr <= b; yr += 5) {
      var x = x0 + (yr - a) / (b - a) * (x1 - x0);
      el("line", { x1: x, x2: x, y1: y1, y2: y1 + 5, stroke: "var(--muted)" }, svg);
      txt(el("text", { x: x, y: y1 + 20, "text-anchor": "middle", "font-size": 11.5, fill: "var(--muted)" }, svg), String(yr));
    }
    var d = hist.map(function (h, i) { return (i ? "L" : "M") + X(h.m).toFixed(1) + " " + Y(h.pos).toFixed(1); }).join("");
    el("path", { d: d, fill: "none", stroke: "var(--ink)", "stroke-width": 1.6, "stroke-linejoin": "round" }, svg);
    var last = hist[hist.length - 1];
    el("circle", { cx: X(last.m), cy: Y(last.pos), r: 5, fill: "var(--ink)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
    txt(el("text", { x: x0, y: H - 4, "font-size": 11, fill: "var(--muted)" }, svg), "Shaded columns: US recessions (NBER, via FRED USREC)");
  }

  function load() {
    var base = (document.body && document.body.getAttribute("data-root")) || "";
    fetch(base + "data/cycle.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { renderGauge(data); renderTracker(data); })
      .catch(function () {
        var s = $("v-summary") || $("gauge-meta");
        if (s) s.textContent = "The cycle data file did not load. Refresh the page to try again.";
      });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load); else load();
})();
