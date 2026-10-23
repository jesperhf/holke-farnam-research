"""Build the static site into _site/.

  python scripts/build.py              full site for GitHub Pages
  python scripts/build.py --artifact   preview variant (index page as a fragment, no file downloads)

Needs the `markdown` package (pip install markdown).
"""

import datetime as dt
import html
import json
import os
import re
import shutil
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACT = "--artifact" in sys.argv
OUT = os.path.join(ROOT, "_artifact" if ARTIFACT else "_site")
FONTS = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800"
         "&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,650&display=swap")


def load(path, default=None):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


SITE = load("content/site.json")
CALLS = load("content/calls.json", {"calls": []})["calls"]
BOOK = load("content/positions.json", {"snapshot": None, "positions": [], "closed": [], "trades": []})
CYCLE = load("data/cycle.json", {})
PRICES = load("data/prices.json", {"prices": {}})
E = html.escape
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def long_date(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def short_date(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{MONTHS[d.month - 1][:3]} {d.day}, {d.year}"

# ---------------------------------------------------------------- journal

def parse_entry(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    meta, body = {}, raw
    if m:
        body = m.group(2)
        for line in m.group(1).splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            meta[k.strip()] = v
    meta["body"] = body
    meta["file"] = os.path.basename(path)
    upd = os.path.join(ROOT, "content", "updates", meta["slug"] + ".md")
    meta["updates"] = open(upd, encoding="utf-8").read() if os.path.exists(upd) else ""
    return meta


def entries():
    d = os.path.join(ROOT, "content", "journal")
    out = [parse_entry(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(".md")]
    # newest first; same date keeps the later file (series order) first
    def part(e):
        m = re.search(r"part (\d+)", e.get("series", ""))
        return int(m.group(1)) if m else 0
    return sorted(out, key=lambda e: (e["written"], part(e)), reverse=True)


def md(text):
    h = markdown.markdown(text, extensions=["tables", "sane_lists"])
    h = h.replace("<table>", '<div class="table-box"><table>').replace("</table>", "</table></div>")
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', h)
    h = h.replace("<p>{{chart:value-vs-price}}</p>", value_chart())
    h = h.replace("<p>{{diagram:chain}}</p>", chain_diagram())
    return h

# ---------------------------------------------------------------- figures

def pct(v):
    r = round(v)
    return ("+" if r > 0 else "\u2212" if r < 0 else "") + f"{abs(r)}%"


def value_chart():
    rows = sorted(CALLS, key=lambda c: c["base"] / c["price"], reverse=True)
    lo, hi, x0, x1 = -60, 80, 150, 740
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    y0, pitch = 48, 28
    bottom = y0 + pitch * len(rows) - 12
    parts = []
    for t in range(lo, hi + 1, 20):
        parts.append(f'<line class="gridl" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="30" y2="{bottom}"/>'
                     f'<text class="tick" x="{X(t):.1f}" y="22" text-anchor="middle">{pct(t)}</text>')
    parts.append(f'<line class="zero" x1="{X(0):.1f}" x2="{X(0):.1f}" y1="30" y2="{bottom}"/>')
    above = 0
    for i, c in enumerate(rows):
        y = y0 + i * pitch
        base = (c["base"] / c["price"] - 1) * 100
        bull = (c["bull"] / c["price"] - 1) * 100
        above += base < 0
        up = base > 0
        bx, bw = min(X(0), X(base)), abs(X(base) - X(0))
        vx = X(base) + (6 if up else -6)
        parts.append(
            f'<text class="lbl{" strong" if up else ""}" x="0" y="{y + 5}">{E(c["name"])}<title>{E(c["sector"])}</title></text>'
            f'<rect class="bar{" up" if up else ""}" x="{bx:.1f}" y="{y - 8}" width="{bw:.1f}" height="16" rx="2"><title>{E(c["name"])}: base value {pct(base)} vs price, bull {pct(bull)}</title></rect>'
            f'<text class="val" x="{vx:.1f}" y="{y + 5}" text-anchor="{"start" if up else "end"}">{pct(base)}</text>'
            f'<path class="bull" d="M{X(bull):.1f} {y - 7}l7 7l-7 7l-7 -7z"><title>{E(c["name"])}: bull case {pct(bull)} vs price</title></path>')
    h = bottom + 34
    parts.append(f'<rect class="bar" x="{x0}" y="{h - 16}" width="16" height="11" rx="2"/><text class="sub" x="{x0 + 22}" y="{h - 6}">Base-case value vs price</text>'
                 f'<path class="bull" d="M{x0 + 222} {h - 17}l7 7l-7 7l-7 -7z"/><text class="sub" x="{x0 + 236}" y="{h - 6}">Bull-case value vs price</text>')
    svg = (f'<svg class="vchart" viewBox="0 0 760 {h + 6}" role="img" aria-label="Base-case value against share price for twelve AI companies">'
           + "".join(parts) + "</svg>")
    return (f'<figure><h3>{above} of {len(rows)} names trade above my base-case value</h3>'
            f'<div class="wide-fig">{svg}</div><figcaption>My scenario DCFs from the three company work-ups. Prices October 19 to 21, 2026. '
            f'Discount rates 10% to 11.5% (12% to 13% for memory).</figcaption></figure>')


def chain_diagram():
    pairs = [
        ("1. AI capex", "About a third of 2026 US GDP growth (ING); increasingly funded with debt at 5%+ yields",
         "Capex digestion", "Hyperscalers slow orders as returns lag spending, or as credit costs bite"),
        ("2. Supplier earnings", "Micron and Nvidia add 9 of the 29 points of Q3 S&P 500 EPS growth",
         "Supplier earnings fall hardest", "In 2009 TSMC revenue fell 11% and ASML's fell 46%"),
        ("3. Index profits and stock prices", "S&P 500 net margin 14.9% vs a 12.6% five-year average; profit share of GDP highest since the 1940s",
         "Index earnings and prices fall", "Margins mean-revert from a record; a 19x multiple does not cushion an earnings cut"),
        ("4. Wealth effect and top-earner spending", "Top 10% of earners are half of consumer spending; stock gains add about 0.44 pt to GDP (ING)",
         "Wealth effect reverses", "Top-earner spending slows with portfolios, and everyone else is already squeezed"),
        ("5. Labor market, already cooling", "September payrolls +29k; unemployment 4.2%; wages +3.0% vs 3.7% CPI",
         "Contraction", "Firms protect margins with layoffs; a 0.5 pt rise in unemployment triggers the Sahm rule"),
    ]
    cells = ['<div class="colhead">Today: what is holding the economy up</div><div class="colhead then-h">If AI earnings roll over</div>']
    for a, b, c, d in pairs:
        cells.append(f'<div class="box now"><b>{E(a)}</b><span>{E(b)}</span></div><div class="box then"><b>{E(c)}</b><span>{E(d)}</span></div>')
    return (f'<figure><h3>The economy leans on one chain, and it unwinds in the same order</h3>'
            f'<div class="chain">{"".join(cells)}</div><figcaption>Figures from FactSet, BEA, ING, Moody\'s and BLS, as cited below.</figcaption></figure>')

# ---------------------------------------------------------------- layout

NAV = [("index.html", "Home"), ("journal/index.html", "Journal"), ("tracker.html", "Cycle tracker"),
       ("scorecard.html", "Scorecard"), ("positions.html", "Positions"), ("models.html", "Models"), ("about.html", "About")]


def page(path, title, body, current, scripts=(), description=""):
    depth = path.count("/")
    root = "../" * depth
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{root}{href}"{cur if label == current else ""}>{label}</a>' for href, label in NAV)
    full_title = SITE["name"] if title == SITE["name"] else f"{title} · {SITE['name']}"
    head = (f'<title>{E(full_title)}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            f'<meta name="description" content="{E(description or SITE["tagline"])}">\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{FONTS}">\n<link rel="stylesheet" href="{root}assets/site.css">\n'
            + ("" if ARTIFACT else f'<link rel="alternate" type="application/rss+xml" title="{E(SITE["name"])}" href="{root}feed.xml">\n'))
    foot = (f'<footer><div class="wrap"><p><b>{E(SITE["name"])}</b> is the personal investment journal of {E(SITE["author"])}. '
            f'Nothing here is investment advice or a recommendation to buy or sell any security. See the <a href="{root}about.html#disclosures">disclosures</a>.</p>'
            f'<p>Economic data: Federal Reserve Bank of St. Louis (FRED). Company figures as cited in each entry.</p></div></footer>')
    scr = "".join(f'<script src="{root}assets/{s}"></script>' for s in scripts)
    inner = (f'<header class="mast"><div class="wrap"><a class="brand" href="{root}index.html"><b>{E(SITE["name"])}</b><span>{E(SITE["tagline"])}</span></a>'
             f'<nav class="top" aria-label="Site">{nav}</nav></div></header>\n<main class="wrap">{body}</main>\n{foot}\n{scr}')
    if ARTIFACT and path == "index.html":
        # The artifact host wraps the index page in its own document skeleton.
        html_out = head + f'<div data-root="{root}" id="page-root">' + inner + "</div>"
    else:
        html_out = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                    f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n{head}</head>\n'
                    f'<body data-root="{root}">\n{inner}\n</body>\n</html>\n')
    dest = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(html_out)

# ---------------------------------------------------------------- pieces

def pager_link(e, word):
    if not e:
        return ""
    return '<a href="' + e["slug"] + '.html">' + word + ": " + E(e["title"]) + "</a>"


def stance_chip(s):
    s = s or ""
    cls = "pass" if s.lower().startswith("pass") else "watch"
    return f'<span class="chip {cls}">{E(s)}</span>'


def held_at(tickers, when):
    """Positions in these tickers that were open on date `when` (ISO)."""
    want = {t.upper() for t in tickers}
    out = []
    for p in BOOK.get("positions", []) + BOOK.get("closed", []):
        if p["ticker"].upper() not in want:
            continue
        opened, closed = p.get("opened"), p.get("closed")
        if opened and opened[:10] > when[:10]:
            continue
        if closed and closed[:10] <= when[:10]:
            continue
        out.append(p)
    return out


def disclosure_html(e):
    tickers = e.get("tickers") or []
    if not BOOK.get("snapshot"):
        line = '<p class="flag">Position disclosure not yet confirmed by the author.</p>'
    else:
        held = held_at(tickers, e["published"])
        if held:
            line = ("<p>At publication I held: " + ", ".join(E(p["ticker"]) for p in held) +
                    '. Current weights are on the <a href="../positions.html">positions page</a>.</p>')
        else:
            line = "<p>At publication I held no position in any company discussed in this entry.</p>"
    return ('<aside class="disclose"><p><b>Disclosure.</b></p>' + line +
            "<p>This is my personal research journal, not investment advice. Valuations, scenario weights and buy levels are my own estimates. "
            'See the <a href="../about.html#disclosures">full disclosures</a>.</p></aside>')


def fmt_open(v, snap=None):
    if not v:
        return ("Before " + short_date(snap)) if snap else "n/a"
    if len(v) == 7:
        return MONTHS[int(v[5:7]) - 1][:3] + " " + v[:4]
    return short_date(v)


def pos_price(ticker):
    p = PRICES.get("prices", {}).get("pos:" + ticker.upper())
    return (p["price"], p.get("date")) if p else (None, None)


def current_weights():
    """Drift each snapshot weight with its price since the snapshot; cash held constant."""
    rows = BOOK.get("positions", [])
    cash = BOOK.get("cash") or 0.0
    vals = {}
    for p in rows:
        lp, _ = pos_price(p["ticker"])
        drift = (lp / p["snapPrice"]) if (lp and p.get("snapPrice")) else 1.0
        vals[p["ticker"]] = p["weight"] * drift
    total = sum(vals.values()) + cash
    if not total:
        return {}, 0.0
    return {k: v / total * 100 for k, v in vals.items()}, cash / total * 100


def positions_page():
    snap = BOOK.get("snapshot")
    if not snap:
        return ('<section class="page"><div class="sect-head"><h1>Positions</h1></div>'
                '<p class="lede">Every position in my personal brokerage account, shown as a percent of the portfolio. No dollar amounts are published or stored anywhere on this site.</p>'
                '<div class="table-box"><div class="empty">The first portfolio snapshot has not been loaded yet. Once it is, this page lists each position with its weight, '
                "average cost per share, return since purchase, exit levels and a link to the research behind it, plus a dated log of every trade.</div></div></section>")
    w, cash_now = current_weights()
    rows = sorted(BOOK.get("positions", []), key=lambda p: -w.get(p["ticker"], 0))
    top5 = sum(sorted(w.values(), reverse=True)[:5])
    biggest = max(w.values()) if w else 0
    strip = ('<div class="verdict"><div><div class="eyebrow">Snapshot ' + E(long_date(snap)) + '</div>'
             f'<div class="phase-name">{len(rows)} positions</div><p>Weights below are estimated for today: each snapshot weight moves with its share price since the snapshot, and cash is held constant.</p></div>'
             f'<div><div class="metrics"><div><b>{biggest:.1f}%</b><span>Largest position</span></div><div><b>{top5:.0f}%</b><span>Top five combined</span></div>'
             f'<div><b>{cash_now:.1f}%</b><span>Cash</span></div></div></div></div>')
    trs = []
    for p in rows:
        lp, ld = pos_price(p["ticker"])
        ccy = p.get("currency", "USD")
        wt = w.get(p["ticker"], p["weight"])
        ret = f'<span class="{"pos" if lp >= p["avgCost"] else "neg"}">{pct((lp / p["avgCost"] - 1) * 100) if abs(lp / p["avgCost"] - 1) >= 0.005 else "0%"}</span>' if (lp and p.get("avgCost")) else '<span class="muted">n/a</span>'
        plan = []
        flags = []
        if p.get("trimAbove"):
            plan.append("Trim above " + money(p["trimAbove"], ccy))
            if lp and lp >= p["trimAbove"]:
                flags.append('<span class="chip L">At trim level</span>')
        if p.get("exitBelow"):
            plan.append("Exit below " + money(p["exitBelow"], ccy))
            if lp and lp <= p["exitBelow"]:
                flags.append('<span class="chip C">At exit level</span>')
        if p.get("exitPlan"):
            plan.append(E(p["exitPlan"]))
        link = f'<a href="journal/{p["entry"]}.html">Research</a>' if p.get("entry") else '<span class="muted">No entry yet</span>'
        opened = fmt_open(p.get("opened"), snap)
        trs.append(
            f'<tr><td><b>{E(p.get("name") or p["ticker"])}</b><span class="sub">{E(p["ticker"])}</span></td>'
            f'<td class="num"><div class="wbar"><i style="width:{min(wt, 100) / max(biggest, 1) * 100:.1f}%"></i></div>{wt:.1f}%<span class="sub">snapshot {p["weight"]:.1f}%</span></td>'
            f'<td class="num">{money(p["avgCost"], ccy) if p.get("avgCost") else "n/a"}</td>'
            f'<td class="num">{money(lp, ccy) if lp else "n/a"}' + (f'<span class="sub">{E(ld)}</span>' if ld else "") + "</td>"
            f'<td class="num">{ret}</td><td>{opened}</td>'
            f'<td>{"<br>".join(plan) if plan else "<span class=muted>Not set</span>"}{(" " + " ".join(flags)) if flags else ""}</td><td>{link}</td></tr>')
    open_tbl = ('<div class="table-box"><table class="calls positions"><thead><tr><th>Position</th><th class="num">Weight</th><th class="num">Avg cost</th>'
                '<th class="num">Latest</th><th class="num">Return</th><th>Opened</th><th>Exit plan</th><th></th></tr></thead><tbody>' + "".join(trs) + "</tbody></table></div>")
    closed = BOOK.get("closed", [])
    if closed:
        crs = "".join(
            f'<tr><td><b>{E(c.get("name") or c["ticker"])}</b><span class="sub">{E(c["ticker"])}</span></td>'
            f'<td>{fmt_open(c.get("opened"))}</td><td>{short_date(c["closed"])}</td>'
            f'<td class="num">{money(c["avgCost"], c.get("currency", "USD"))}</td><td class="num">{money(c["exitPrice"], c.get("currency", "USD"))}</td>'
            f'<td class="num"><span class="{"pos" if c["exitPrice"] >= c["avgCost"] else "neg"}">{pct((c["exitPrice"] / c["avgCost"] - 1) * 100)}</span></td>'
            f'<td>{E(c.get("note", ""))}</td></tr>' for c in sorted(closed, key=lambda c: c["closed"], reverse=True))
        closed_html = ('<section class="sect"><h2>Closed positions</h2><div class="table-box"><table class="calls"><thead><tr><th>Position</th><th>Opened</th><th>Closed</th>'
                       '<th class="num">Avg cost</th><th class="num">Exit price</th><th class="num">Return</th><th>Why I sold</th></tr></thead><tbody>' + crs + "</tbody></table></div></section>")
    else:
        closed_html = '<section class="sect"><h2>Closed positions</h2><p class="muted" style="font-family:var(--f-ui)">None yet. Every full exit is recorded here with its exit price and return.</p></section>'
    trades = BOOK.get("trades", [])
    if trades:
        trs2 = "".join(
            f'<tr><td class="nowrap">{short_date(t["date"])}</td><td>{E(t["action"])}</td><td><b>{E(t["ticker"])}</b></td>'
            f'<td class="num">{t["from"]:.1f}% → {t["to"]:.1f}%</td><td class="num">{money(t["price"], t.get("currency", "USD")) if t.get("price") else ""}</td><td>{E(t.get("note", ""))}</td></tr>'
            for t in sorted(trades, key=lambda t: t["date"], reverse=True))
        log = ('<section class="sect"><h2>Trade log</h2><div class="table-box"><table class="calls"><thead><tr><th>Date</th><th>Action</th><th>Ticker</th>'
               '<th class="num">Weight</th><th class="num">Price</th><th>Note</th></tr></thead><tbody>' + trs2 + "</tbody></table></div></section>")
    else:
        log = '<section class="sect"><h2>Trade log</h2><p class="muted" style="font-family:var(--f-ui)">Trades after the first snapshot are logged here by date, as weight changes rather than amounts.</p></section>'
    return ('<section class="sect"><div class="sect-head"><h1>Positions</h1><span class="muted" style="font-family:var(--f-ui);font-size:14px">'
            + E(BOOK.get("account", "")) + ' · percentages only</span></div>'
            '<p class="lede">Every position I hold, as a percent of the portfolio, with my average cost, my exit levels and the research behind it. No dollar amounts are published or stored anywhere on this site.</p>'
            + strip + open_tbl + "</section>" + closed_html + log +
            '<div class="notes"><p><b>How to read this.</b> Return is the latest price against my average cost per share, before dividends. Exit levels are set in advance: '
            '"trim above" is where I would reduce the position, "exit below" is where the thesis would be broken. A chip appears when the price reaches either level.</p>'
            "<p>Trades are posted after they are filled, not before.</p></div>")


def latest_price(c):
    p = PRICES.get("prices", {}).get(c["id"])
    return (p["price"], p.get("date")) if p else (None, None)


def money(v, ccy):
    sym = {"USD": "$", "EUR": "€", "KRW": "₩"}[ccy]
    if ccy == "KRW":
        return f"{sym}{v:,.0f}"
    if float(v).is_integer():
        return f"{sym}{v:,.0f}"
    return f"{sym}{v:,.2f}"


def rnd(v, ccy):
    return round(v, -3) if ccy == "KRW" else round(v)


def calls_table(rows, compact=False):
    head = ("<tr><th>Company</th><th>Stance</th><th class=\"num\">Price published</th><th class=\"num\">Buy below</th>"
            + ("" if compact else "<th class=\"num\">Base value</th>")
            + "<th class=\"num\">Latest price</th><th class=\"num\">Change since</th><th class=\"num\">To buy level</th><th>Status</th></tr>")
    body = []
    for c in rows:
        lp, ld = latest_price(c)
        ref = lp if lp is not None else c["price"]
        since = f'<span class="{"pos" if lp >= c["price"] else "neg"}">{(lp / c["price"] - 1) * 100:+.1f}%</span>' if lp is not None else '<span class="muted">n/a</span>'
        gap = (c["buyBelow"] / ref - 1) * 100
        held_now = any(p["ticker"].upper() == c.get("yahoo", "").upper() or p["ticker"].upper() == c["ticker"].split(" ")[0].upper() for p in BOOK.get("positions", []))
        if held_now:
            status = '<span class="chip hit">Held</span>'
        elif c["stance"].lower().startswith("pass"):
            status = '<span class="chip pass">Pass</span>'
        elif lp is not None and lp <= c["buyBelow"]:
            status = '<span class="chip hit">At buy level</span>'
        else:
            status = '<span class="chip watch">Waiting</span>'
        jl = f'journal/{c["entry"]}.html' if not compact or True else ""
        body.append(
            f'<tr><td><a href="{{root}}{jl}">{E(c["name"])}</a><span class="sub">{E(c["ticker"])} · {E(c["sector"])}</span></td>'
            f'<td class="nowrap">{E(c["stance"])}</td>'
            f'<td class="num">{money(c["price"], c["currency"])}<span class="sub">{short_date(c["priceDate"])}</span></td>'
            f'<td class="num">{money(c["buyBelow"], c["currency"])}</td>'
            + ("" if compact else f'<td class="num">{money(rnd(c["base"], c["currency"]), c["currency"])}<span class="sub">bear {money(rnd(c["bear"], c["currency"]), c["currency"])} · bull {money(rnd(c["bull"], c["currency"]), c["currency"])}</span></td>')
            + f'<td class="num">{money(lp, c["currency"]) if lp is not None else "<span class=muted>n/a</span>"}'
            + (f'<span class="sub">{E(ld)}</span>' if ld else "") + "</td>"
            f'<td class="num">{since}</td><td class="num">{pct(gap)}</td><td>{status}</td></tr>')
    return f'<div class="table-box"><table class="calls"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


def cycle_text():
    L = CYCLE.get("latest") or {}
    if L.get("position") is None:
        return "Waiting for data", "M", "The first daily update fills this in."
    pos = L["position"]
    k = "E" if pos < 25 else "M" if pos < 50 else "L" if pos < 74 else "C"
    names = {"E": "Early expansion", "M": "Mid expansion", "L": "Late expansion", "C": "Contraction"}
    short = {"E": "Early", "M": "Mid", "L": "Late", "C": "contraction"}
    lab = names[k]
    for edge in (25, 50, 74):
        if abs(pos - edge) < 4:
            a = "E" if edge - 1 < 25 else "M" if edge - 1 < 50 else "L"
            b = "M" if edge + 1 < 50 else "L" if edge + 1 < 74 else "C"
            lab = "Late expansion, turning" if b == "C" else f"{short[a]} to {short[b].lower()} transition"
    when = ("reading of " + long_date(L["asOf"])) if CYCLE.get("seed") else ("updated " + long_date(CYCLE["generated"]))
    return lab, k, f"Position {round(pos)} of 100 · {L['counts'][k]} of {L['reporting']} indicators agree · {when}"

# ---------------------------------------------------------------- pages

def build():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for d in ("assets", "data"):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(OUT, d))
    if not ARTIFACT:
        shutil.copytree(os.path.join(ROOT, "models"), os.path.join(OUT, "models"))
        open(os.path.join(OUT, ".nojekyll"), "w").close()

    ents = entries()
    latest = next((e for e in ents if e["slug"] == "the-ai-trade-in-a-late-cycle"), ents[0])

    # Journal entries
    for i, e in enumerate(ents):
        newer = ents[i - 1] if i > 0 else None
        older = ents[i + 1] if i + 1 < len(ents) else None
        upd = ""
        if e["updates"].strip():
            upd = '<section class="prose"><h2>Updates</h2>' + md(e["updates"]) + "</section>"
        else:
            upd = ('<section class="prose"><h2>Updates</h2><p class="muted">No updates yet. Later thinking on this entry is added here as dated notes, '
                   "and the entry above stays as written.</p></section>")
        tick = ", ".join(t for t in e.get("tickers", []) if t != "SKH")
        body = (f'<article style="display:grid;gap:34px"><header class="note-head"><div class="eyebrow">{E(e.get("series", "Journal"))}</div>'
                f'<h1>{E(e["title"])}</h1><p class="lede">{E(e["summary"])}</p>'
                f'<div class="meta"><span>Written {long_date(e["written"])}</span><span>Published {long_date(e["published"])}</span>{stance_chip(e.get("stance"))}</div>'
                f'<div class="lock"><span>This entry is locked as written. Prices and figures are as of the dates in the text. Later thinking goes in the updates at the end.</span></div></header>'
                f'<div class="prose">{md(e["body"])}</div>{upd}{disclosure_html(e)}'
                f'<nav class="pager" aria-label="More entries"><span>{pager_link(newer, "Newer")}</span><span>{pager_link(older, "Older")}</span></nav></article>')
        page(f'journal/{e["slug"]}.html', e["title"], body, "Journal", description=e["summary"])

    def entry_list(items, root):
        lis = []
        for e in items:
            lis.append(f'<li><div class="date">{short_date(e["written"])}</div><div><h3><a href="{root}journal/{e["slug"]}.html">{E(e["title"])}</a></h3>'
                       f'<p>{E(e["summary"])}</p><div class="row">{stance_chip(e.get("stance"))}<span>{E(e.get("series", ""))}</span></div></div></li>')
        return f'<ul class="entries">{"".join(lis)}</ul>'

    # Journal index
    page("journal/index.html", "Journal",
         '<section class="sect"><div class="sect-head"><h1>Journal</h1><span class="muted" style="font-family:var(--f-ui);font-size:14px">'
         f'{len(ents)} entries · newest first</span></div><p class="lede">Every entry is dated and kept as written. When my view changes, I add a dated update to the entry instead of editing it.</p>'
         + entry_list(ents, "../") + "</section>", "Journal")

    # Home
    lab, k, meta = cycle_text()
    watch = [c for c in CALLS if not c["stance"].lower().startswith("pass")]
    home = (
        f'<section class="hero"><div class="view"><div class="eyebrow">Current view · {short_date(latest["written"])}</div>'
        f'<h1><a href="journal/{latest["slug"]}.html">{E(latest["title"][0].upper() + latest["title"][1:])}</a></h1>'
        f'<p class="lede">{E(latest["summary"])}</p><div class="meta">{stance_chip(latest.get("stance"))}<a href="journal/{latest["slug"]}.html">Read the entry</a></div></div>'
        f'<a class="gauge" href="tracker.html" aria-label="Open the cycle tracker"><div class="eyebrow">US business cycle, live</div>'
        f'<div class="phase" id="gauge-phase" style="color:var(--{ {"E": "early", "M": "mid", "L": "late", "C": "contr"}[k] })">{E(lab)}</div>'
        f'<svg id="gauge-svg" viewBox="0 0 400 132" role="img" aria-label="Business cycle curve with the current reading marked"></svg>'
        f'<small id="gauge-meta">{E(meta)}</small></a></section>'
        f'<section class="sect"><div class="sect-head"><h2>Watchlist</h2><a href="scorecard.html">All calls and how they are doing</a></div>'
        f'<p class="muted" style="font-family:var(--f-ui);font-size:15px;margin:0">No positions at today\'s prices. These are the levels where my base case earns its required return.</p>'
        + calls_table(watch, compact=True).replace("{root}", "") + "</section>"
        f'<section class="sect"><div class="sect-head"><h2>Journal</h2><a href="journal/index.html">All entries</a></div>{entry_list(ents, "")}</section>')
    page("index.html", SITE["name"], home, "Home", scripts=("tracker.js",), description=latest["summary"])

    # Tracker
    seed_hidden = "" if CYCLE.get("seed") else " hidden"
    tracker = (
        '<section class="sect"><div class="sect-head"><h1>Business cycle tracker</h1><span class="muted" style="font-family:var(--f-ui);font-size:14px">US economy · 11 indicators · FRED data</span></div>'
        f'<div class="banner" id="seed-banner"{seed_hidden}>{E(CYCLE.get("seedNote", ""))}</div>'
        '<div class="verdict"><div><div class="eyebrow" id="v-asof">Reading</div><div class="phase-name" id="v-phase">Loading</div><p id="v-summary">Placing the economy on the cycle.</p></div>'
        '<div><div class="metrics"><div><b id="m-pos">n/a</b><span>Cycle position, 0 to 100</span></div><div><b id="m-conf">n/a</b><span>Indicators agreeing</span></div><div><b id="m-cov">n/a</b><span>Indicators reporting</span></div></div>'
        '<div class="split" id="split" aria-label="Indicator votes by phase"></div><div class="split-key" id="split-key"></div></div></div>'
        '<div class="panel"><div class="panel-head"><h2>Where the cycle stands</h2><small>Hover or tap a phase to read what usually happens in it</small></div>'
        '<div class="svg-box"><svg id="cycle" viewBox="0 0 1000 310" role="img" aria-label="Business cycle curve with the current reading marked"></svg></div></div>'
        '<div class="verdict" id="phase-card"><div><div class="eyebrow" id="pc-eyebrow">Phase guide</div><h3 id="pc-title" style="font-size:24px;margin:4px 0 8px">Select a phase</h3><p id="pc-desc"></p></div>'
        '<div><p><b style="color:var(--ink)">Typical signals.</b> <span id="pc-signals"></span></p><p style="margin-top:8px"><b style="color:var(--ink)">Sectors that have historically led.</b> <span id="pc-sectors"></span></p></div></div>'
        '<div class="panel"><div class="panel-head"><h2>The composite since 1990</h2><small>Monthly position on the cycle, 0 to 100</small></div>'
        '<div class="svg-box"><svg id="history" viewBox="0 0 1000 330" role="img" aria-label="Cycle position by month since 1990 with recessions shaded"></svg></div></div>'
        '<section class="sect"><h2>Readings behind the call</h2><div class="table-box"><table class="readings"><thead><tr><th>Indicator</th><th>Latest</th><th>Context</th><th>Signal</th><th>Rule</th><th>FRED series</th></tr></thead>'
        '<tbody id="rows"><tr><td colspan="6" class="empty">Loading the latest readings.</td></tr></tbody></table></div></section>'
        '<div class="notes"><p><b>How the call is made.</b> Each indicator votes for one phase using the fixed rule beside it. The position is the average of the voted phase centers (early 13, mid 40, late 62, contraction 87). '
        'These rules describe the present; they are not a recession forecast, and the NBER dates turning points only after the fact.</p>'
        '<p><b>How it updates.</b> A scheduled job pulls each series from FRED every morning, recomputes the votes, and republishes this page. The history line uses today\'s revised data aligned to the month measured, so it is cleaner than what was known in real time.</p></div></section>')
    page("tracker.html", "Business cycle tracker", tracker, "Cycle tracker", scripts=("tracker.js",),
         description="A live reading of where the US economy sits in the business cycle, built from 11 FRED indicators.")

    # Scorecard
    pg = PRICES.get("generated")
    sc = (
        '<section class="sect"><div class="sect-head"><h1>Scorecard</h1><span class="muted" style="font-family:var(--f-ui);font-size:14px">'
        + (f"Prices updated {long_date(pg)}" if pg else "Latest prices appear after the first daily update") + "</span></div>"
        '<p class="lede">Every call as first published, next to where the stock trades now. Rows are never edited. When my view on a company changes, I add a new row with a new date.</p>'
        + calls_table(CALLS).replace("{root}", "") +
        '<div class="notes"><p><b>Reading the table.</b> "Buy below" is the price at which my base case earns my required return. "Gap to buy level" is how far the stock would have to fall to reach it. '
        '"Pass" means I would not buy even at the buy level without new information. Base, bear and bull values come from the scenario DCFs on the <a href="models.html">models page</a>.</p>'
        '<p><b>How I grade calls.</b> Over time this page answers two questions: did the stocks I passed on do worse than the ones I wanted, and did buy levels that filled go on to earn the returns my base cases implied.</p>'
        "<p>Latest prices update every morning. SK hynix is in Korean won and Siemens Energy in euros.</p></div></section>")
    page("scorecard.html", "Scorecard", sc, "Scorecard", description="Every published call next to where the stock trades now.")

    # Models
    models = [
        ("Memory_Storage_DCF.xlsx", "Memory and storage", "Micron, SK hynix, Seagate and Western Digital. Five-year scenario DCFs with a terminal value, built for cyclical businesses.", "memory-and-storage"),
        ("Power_ChipEquipment_DCF.xlsx", "Power and chip equipment", "TSMC, ASML, Applied Materials, Vertiv, Siemens Energy and nVent. Ten-year DCFs with a five-year fade to terminal levels.", "power-and-chip-equipment"),
        ("Optical_Networking_DCF.xlsx", "Optical networking", "Coherent and Fabrinet, on the same ten-year framework.", "optical-networking"),
    ]
    cards = []
    for f, t, d, slug in models:
        dl = (f'<span class="dl muted">Download on the published site</span>' if ARTIFACT else f'<a class="dl" href="models/{f}" download>Download {f}</a>')
        cards.append(f'<div class="card"><h3>{E(t)}</h3><p>{E(d)}</p><p><a href="journal/{slug}.html">Read the entry</a></p>{dl}</div>')
    mp = ('<section class="page"><div class="sect-head"><h1>Models</h1></div>'
          '<p class="lede">The Excel workbooks behind the valuations, with live formulas. Blue cells are inputs. Each workbook has a WACC tab with a switch between a CAPM-calculated discount rate and my assumed rate.</p></section>'
          f'<div class="cards">{"".join(cards)}</div>'
          '<div class="notes"><p>These are free cash flow models, not full three-statement builds. Free cash flow is operating income after tax, less net reinvestment and the working capital that growth absorbs. '
          'Every scenario path, margin and discount rate is my own assumption, set out where you can change it.</p></div>')
    page("models.html", "Models", mp, "Models", description="The valuation workbooks behind each journal entry.")

    page("positions.html", "Positions", positions_page(), "Positions",
         description="Every position in my personal account as a percent of the portfolio, with cost basis, exit levels and the research behind it.")

    # About and disclosures
    if not BOOK.get("snapshot"):
        hold_html = '<p class="flag">My current positions have not been listed here yet.</p>'
    else:
        hold_html = (f'<p>Every position in my personal brokerage account is listed on the <a href="positions.html">positions page</a>, '
                     f'as percentages of the portfolio (snapshot of {long_date(BOOK["snapshot"])}, with trades logged since). Each journal entry states which of its companies I held at publication.</p>')
    bio = "".join(f"<p>{E(b)}</p>" for b in SITE["bio"])
    proc = f'<p>{E(SITE["process_note"])}</p>' if SITE.get("process_note") else ""
    about = (f'<section class="page"><div class="sect-head"><h1>About</h1></div>{bio}'
             '<h2>How the journal works</h2><ul>'
             "<li>Every entry is dated and locked as written. Prices, figures and conclusions reflect what I knew on that date.</li>"
             "<li>When my view changes, I add a dated update under the original entry and a new row on the scorecard. I do not rewrite history.</li>"
             "<li>Every valuation states its bear, base and bull cases, and every thesis says what would prove it wrong.</li></ul>"
             f'{proc}<h2 id="disclosures">Disclosures</h2>'
             "<p>This site is my personal research journal. It is not investment advice, not a recommendation to buy or sell any security, and not an offer of any service. "
             "I am not a registered investment adviser. Nothing here takes into account your circumstances, and you should do your own research.</p>"
             "<p>My estimates can be wrong. Prices and figures are as of the dates stated and are not updated in past entries.</p>"
             "<h3>Positions</h3>" + hold_html +
             "<h3>Data</h3><p>Economic data come from the Federal Reserve Bank of St. Louis (FRED). This site uses FRED data but is not endorsed or certified by the Federal Reserve Bank of St. Louis. "
             "Some series are owned by third parties and are subject to their terms. Company figures are cited to their sources in each entry.</p></section>")
    page("about.html", "About", about, "About", description="Who writes this journal, how it works, and disclosures.")

    # RSS
    if not ARTIFACT:
        base = (SITE.get("url") or "").rstrip("/")
        items = "".join(
            f"<item><title>{E(e['title'])}</title><link>{base}/journal/{e['slug']}.html</link><guid>{base}/journal/{e['slug']}.html</guid>"
            f"<pubDate>{dt.datetime.fromisoformat(e['published']).strftime('%a, %d %b %Y 12:00:00 +0000')}</pubDate><description>{E(e['summary'])}</description></item>"
            for e in ents)
        open(os.path.join(OUT, "feed.xml"), "w").write(
            f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{E(SITE["name"])}</title><link>{base}/</link>'
            f"<description>{E(SITE['tagline'])}</description>{items}</channel></rss>")
    print(f"built {len(ents)} entries into {OUT}")


if __name__ == "__main__":
    build()
