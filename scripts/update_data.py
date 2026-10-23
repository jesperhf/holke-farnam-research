"""Refresh the site's data files.

Writes:
  data/cycle.json   business cycle reading, built from public FRED series
  data/prices.json  latest share prices for the scorecard (best effort)

Runs daily in GitHub Actions. Uses only the Python standard library.
FRED: if the FRED_API_KEY environment variable is set, the official API is
used; otherwise the public CSV download (no key needed).
"""

import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "holke-farnam-research-site/1.0 (+github actions)"}

# ---------------------------------------------------------------- fetching

def http_get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # network hiccups: retry with backoff
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed: {url}: {last}")


def fred(series_id):
    """Return a sorted list of (date, value) with missing values dropped."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    out = []
    if key:
        q = urllib.parse.urlencode({"series_id": series_id, "api_key": key, "file_type": "json"})
        js = json.loads(http_get("https://api.stlouisfed.org/fred/series/observations?" + q))
        for o in js.get("observations", []):
            if o.get("value") not in (".", "", None):
                out.append((dt.date.fromisoformat(o["date"]), float(o["value"])))
    else:
        text = http_get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + series_id)
        rows = csv.reader(io.StringIO(text))
        next(rows, None)
        for row in rows:
            if len(row) < 2 or row[1] in (".", ""):
                continue
            try:
                out.append((dt.date.fromisoformat(row[0]), float(row[1])))
            except ValueError:
                continue
    out.sort()
    if not out:
        raise RuntimeError(f"no observations for {series_id}")
    return out

# ---------------------------------------------------------------- series helpers

def month_key(d):
    return (d.year, d.month)


def monthly(obs, how="last"):
    """Collapse daily/weekly observations to calendar months: {(y, m): value}."""
    buckets = {}
    for d, v in obs:
        buckets.setdefault(month_key(d), []).append(v)
    if how == "mean":
        return {k: sum(v) / len(v) for k, v in buckets.items()}
    return {k: v[-1] for k, v in buckets.items()}


def shift(ym, n):
    y, m = ym
    t = y * 12 + (m - 1) + n
    return (t // 12, t % 12 + 1)


def ym_str(ym):
    return f"{ym[0]:04d}-{ym[1]:02d}"


def quarterly_available(obs, lag_months=1):
    """Quarterly obs are dated at quarter start; treat each as known from the
    month after the quarter ends (approximate first release)."""
    avail = {}
    for d, v in obs:
        avail[shift((d.year, d.month), 2 + lag_months)] = v
    return avail


def asof(series, ym):
    """Latest value at or before month ym in a {(y, m): v} dict."""
    best = None
    for k in series:
        if k <= ym and (best is None or k > best):
            best = k
    return (series[best], best) if best is not None else (None, None)


class Lookup:
    """Fast as-of lookups on a monthly dict."""

    def __init__(self, series):
        self.keys = sorted(series)
        self.s = series

    def at(self, ym):
        import bisect
        i = bisect.bisect_right(self.keys, ym) - 1
        if i < 0:
            return None
        return self.s[self.keys[i]]

    def window(self, ym, n):
        """Values for the n months ending at ym (only months that exist)."""
        vals = []
        for k in range(n):
            v = self.s.get(shift(ym, -k))
            if v is not None:
                vals.append(v)
        return vals

    def last_key(self):
        return self.keys[-1]

# ---------------------------------------------------------------- phases

PHASES = {
    "E": {"name": "Early expansion", "center": 13},
    "M": {"name": "Mid expansion", "center": 40},
    "L": {"name": "Late expansion", "center": 62},
    "C": {"name": "Contraction", "center": 87},
}


def phase_of(pos):
    return "E" if pos < 25 else "M" if pos < 50 else "L" if pos < 74 else "C"

# ---------------------------------------------------------------- indicators
# Each indicator takes the loaded series and a month, and returns
# (value, context_text, vote) or None when it has no reading that month.

INDICATORS = [
    {"id": "ur", "name": "Unemployment rate", "series": "UNRATE",
     "rule": "Up 0.5 pt or more from its 12-month low: Contraction. Up 0.2 pt: Late. Falling from 5% or above: Early. Otherwise Mid."},
    {"id": "payrolls", "name": "Payroll growth, 3-month average", "series": "PAYEMS",
     "rule": "Below 0: Contraction. Below +75k a month: Late. Below +250k: Mid. Otherwise Early."},
    {"id": "claims", "name": "Initial jobless claims, 4-week average", "series": "ICSA",
     "rule": "30% or more above its 52-week low: Contraction. 15% above: Late. Otherwise Mid."},
    {"id": "cfnai", "name": "Chicago Fed National Activity Index, 3-month average", "series": "CFNAIMA3",
     "rule": "At or below -0.70: Contraction. Below -0.35: Late. Above +0.20 within a year of a reading at or below -0.70: Early. Otherwise Mid."},
    {"id": "cpi", "name": "CPI inflation, year over year", "series": "CPIAUCSL",
     "rule": "3% or above and higher than 3 months earlier: Late. 2.5% or below and falling: Early. Otherwise Mid."},
    {"id": "fed", "name": "Fed funds target, upper bound", "series": "DFEDTARU",
     "rule": "Higher than 3 months earlier: Late. Lower: Early. Unchanged: Mid."},
    {"id": "curve", "name": "Yield curve, 10-year minus 3-month", "series": "T10Y3M",
     "rule": "Inverted: Late. Positive but inverted at some point in the past 6 months: Contraction. Above +150 bp: Early. Otherwise Mid."},
    {"id": "gdp", "name": "Real GDP growth, annualized", "series": "A191RL1Q225SBEA",
     "rule": "Below 0: Contraction. Below 1%: Late. Below 3%: Mid. Otherwise Early."},
    {"id": "realyield", "name": "10-year real yield (TIPS)", "series": "DFII10",
     "rule": "2.5% or above: Late. 0.5% or below: Early. Otherwise Mid."},
    {"id": "oil", "name": "Brent crude, change over 12 months", "series": "DCOILBRENTEU",
     "rule": "Up 40% or more: Late. Down 30% or more: Contraction. Otherwise Mid."},
    {"id": "profits", "name": "Corporate profits after tax, year over year", "series": "CP",
     "rule": "Below 0: Contraction. Below 5%: Late. Otherwise Mid."},
]

SERIES_IDS = ["UNRATE", "PAYEMS", "ICSA", "CFNAIMA3", "CPIAUCSL", "CPILFESL", "DFEDTARU", "DFEDTAR",
              "T10Y3M", "A191RL1Q225SBEA", "DFII10", "DGS10", "DCOILBRENTEU", "CP", "SAHMREALTIME", "USREC"]


def fmt_pct(v, d=1):
    return f"{v:.{d}f}%"


def signed(v, d=0, unit=""):
    return f"{'+' if v >= 0 else ''}{v:,.{d}f}{unit}"


def build_lookups(raw):
    L = {}
    L["UNRATE"] = Lookup(monthly(raw["UNRATE"]))
    pay = monthly(raw["PAYEMS"])
    chg = {k: pay[k] - pay[shift(k, -1)] for k in pay if shift(k, -1) in pay}
    L["PAYCHG"] = Lookup(chg)
    icsa = raw["ICSA"]
    avg4 = []
    for i in range(3, len(icsa)):
        avg4.append((icsa[i][0], sum(v for _, v in icsa[i - 3:i + 1]) / 4))
    L["ICSA4_obs"] = avg4
    L["ICSA4"] = Lookup(monthly(avg4))
    L["CFNAIMA3"] = Lookup(monthly(raw["CFNAIMA3"]))
    cpi = monthly(raw["CPIAUCSL"])
    L["CPIYY"] = Lookup({k: (cpi[k] / cpi[shift(k, -12)] - 1) * 100 for k in cpi if shift(k, -12) in cpi})
    core = monthly(raw["CPILFESL"])
    L["COREYY"] = Lookup({k: (core[k] / core[shift(k, -12)] - 1) * 100 for k in core if shift(k, -12) in core})
    fed = monthly(raw["DFEDTAR"])
    fed.update(monthly(raw["DFEDTARU"]))
    L["FED"] = Lookup(fed)
    L["CURVE"] = Lookup(monthly(raw["T10Y3M"], "mean"))
    L["GDP"] = Lookup(quarterly_available(raw["A191RL1Q225SBEA"]))
    L["REAL"] = Lookup(monthly(raw["DFII10"], "mean"))
    L["DGS10"] = Lookup(monthly(raw["DGS10"], "mean"))
    oil = monthly(raw["DCOILBRENTEU"], "mean")
    L["OIL"] = Lookup(oil)
    L["OILYY"] = Lookup({k: (oil[k] / oil[shift(k, -12)] - 1) * 100 for k in oil if shift(k, -12) in oil})
    cp = raw["CP"]
    cpyy = []
    for i in range(4, len(cp)):
        cpyy.append((cp[i][0], (cp[i][1] / cp[i - 4][1] - 1) * 100))
    L["CPYY"] = Lookup(quarterly_available(cpyy))
    L["SAHM"] = Lookup(monthly(raw["SAHMREALTIME"]))
    return L


def evaluate(ind_id, L, ym, latest=False):
    """Return dict(value, display, context, vote) or None."""
    if ind_id == "ur":
        v = L["UNRATE"].s.get(ym)
        if v is None:
            return None
        win = L["UNRATE"].window(ym, 12)
        low = min(win)
        prior = L["UNRATE"].s.get(shift(ym, -1))
        d = v - low
        vote = "C" if d >= 0.5 else "L" if d >= 0.2 else "E" if (prior is not None and v < prior and v >= 5) else "M"
        sahm = L["SAHM"].s.get(ym)
        ctx = f"12-month low {low:.1f}%" + (f" · Sahm rule {sahm:.2f}" if sahm is not None else "")
        return {"value": v, "display": fmt_pct(v), "context": ctx, "vote": vote}
    if ind_id == "payrolls":
        win = L["PAYCHG"].window(ym, 3)
        if len(win) < 3 or L["PAYCHG"].s.get(ym) is None:
            return None
        avg = sum(win) / 3
        last = L["PAYCHG"].s[ym]
        vote = "C" if avg < 0 else "L" if avg < 75 else "M" if avg < 250 else "E"
        return {"value": avg, "display": signed(avg, 0, "k"), "context": f"latest month {signed(last, 0, 'k')}", "vote": vote}
    if ind_id == "claims":
        v = L["ICSA4"].s.get(ym)
        if v is None:
            return None
        win = L["ICSA4"].window(ym, 12)
        low = min(win)
        up = (v / low - 1) * 100
        vote = "C" if up >= 30 else "L" if up >= 15 else "M"
        return {"value": v, "display": f"{v / 1000:,.0f}k", "context": f"{up:.0f}% above 52-week low of {low / 1000:,.0f}k", "vote": vote}
    if ind_id == "cfnai":
        v = L["CFNAIMA3"].s.get(ym)
        if v is None:
            return None
        recent_low = min(L["CFNAIMA3"].window(ym, 12))
        vote = "C" if v <= -0.70 else "L" if v < -0.35 else "E" if (v > 0.20 and recent_low <= -0.70) else "M"
        return {"value": v, "display": f"{v:+.2f}", "context": f"12-month low {recent_low:+.2f}", "vote": vote}
    if ind_id == "cpi":
        v = L["CPIYY"].s.get(ym)
        if v is None:
            return None
        p3 = L["CPIYY"].s.get(shift(ym, -3))
        core = L["COREYY"].s.get(ym)
        up = p3 is not None and v > p3
        down = p3 is not None and v < p3
        vote = "L" if (v >= 3 and up) else "E" if (v <= 2.5 and down) else "M"
        ctx = (f"3 months earlier {p3:.1f}%" if p3 is not None else "") + (f" · core {core:.1f}%" if core is not None else "")
        return {"value": v, "display": fmt_pct(v), "context": ctx, "vote": vote}
    if ind_id == "fed":
        v = L["FED"].at(ym) if not latest else L["FED"].at(ym)
        p = L["FED"].at(shift(ym, -3))
        if v is None or p is None:
            return None
        vote = "L" if v > p + 0.01 else "E" if v < p - 0.01 else "M"
        return {"value": v, "display": fmt_pct(v, 2), "context": f"3 months earlier {p:.2f}%", "vote": vote}
    if ind_id == "curve":
        v = L["CURVE"].s.get(ym)
        if v is None:
            return None
        prev = [L["CURVE"].s.get(shift(ym, -k)) for k in range(1, 7)]
        was_inv = any(x is not None and x < 0 for x in prev)
        vote = "L" if v < 0 else "C" if was_inv else "E" if v >= 1.5 else "M"
        p1 = prev[0]
        return {"value": v, "display": signed(v * 100, 0, " bp"),
                "context": (f"prior month {signed(p1 * 100, 0, ' bp')}" if p1 is not None else ""), "vote": vote}
    if ind_id == "gdp":
        v = L["GDP"].at(ym)
        if v is None:
            return None
        vote = "C" if v < 0 else "L" if v < 1 else "M" if v < 3 else "E"
        return {"value": v, "display": fmt_pct(v), "context": "latest quarter", "vote": vote}
    if ind_id == "realyield":
        v = L["REAL"].s.get(ym)
        if v is None:
            return None
        n = L["DGS10"].s.get(ym)
        vote = "L" if v >= 2.5 else "E" if v <= 0.5 else "M"
        return {"value": v, "display": fmt_pct(v, 2), "context": (f"nominal 10-year {n:.2f}%" if n is not None else ""), "vote": vote}
    if ind_id == "oil":
        v = L["OILYY"].s.get(ym)
        lvl = L["OIL"].s.get(ym)
        if v is None:
            return None
        vote = "L" if v >= 40 else "C" if v <= -30 else "M"
        return {"value": v, "display": signed(v, 0, "%"), "context": (f"monthly average ${lvl:,.0f}" if lvl else ""), "vote": vote}
    if ind_id == "profits":
        v = L["CPYY"].at(ym)
        if v is None:
            return None
        vote = "C" if v < 0 else "L" if v < 5 else "M"
        return {"value": v, "display": signed(v, 1, "%"), "context": "latest quarter", "vote": vote}
    return None


def score(readings):
    votes = [r["vote"] for r in readings if r and r.get("vote")]
    if not votes:
        return None
    counts = {k: votes.count(k) for k in PHASES}
    pos = sum(PHASES[v]["center"] for v in votes) / len(votes)
    return {"position": round(pos, 1), "phase": phase_of(pos), "counts": counts, "reporting": len(votes)}


def recessions(usrec):
    spans, start = [], None
    for d, v in usrec:
        if v >= 1 and start is None:
            start = d
        if v < 1 and start is not None:
            spans.append([start.isoformat()[:7], d.isoformat()[:7]])
            start = None
    if start is not None:
        spans.append([start.isoformat()[:7], None])
    return spans


def latest_period(ind, L):
    """Label for the period of the latest reading."""
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    key = {"ur": "UNRATE", "payrolls": "PAYCHG", "claims": "ICSA4", "cfnai": "CFNAIMA3", "cpi": "CPIYY", "fed": "FED",
           "curve": "CURVE", "gdp": None, "realyield": "REAL", "oil": "OILYY", "profits": None}[ind]
    if key is None:
        return None
    y, m = L[key].last_key()
    return f"{months[m - 1]} {y}"


def build_cycle(raw):
    L = build_lookups(raw)
    today = dt.date.today()
    end = (today.year, today.month)
    start = (1990, 1)

    # Latest reading: each indicator at its own most recent month.
    latest = []
    for ind in INDICATORS:
        key = {"ur": "UNRATE", "payrolls": "PAYCHG", "claims": "ICSA4", "cfnai": "CFNAIMA3", "cpi": "CPIYY", "fed": "FED",
               "curve": "CURVE", "gdp": "GDP", "realyield": "REAL", "oil": "OILYY", "profits": "CPYY"}[ind["id"]]
        ym = L[key].last_key()
        r = evaluate(ind["id"], L, ym, latest=True)
        if ind["id"] in ("gdp", "profits"):
            # quarterly: label by the quarter measured
            obs = raw["A191RL1Q225SBEA"] if ind["id"] == "gdp" else raw["CP"]
            q = obs[-1][0]
            period = f"Q{(q.month - 1) // 3 + 1} {q.year}"
        elif ind["id"] == "claims":
            period = "week of " + L["ICSA4_obs"][-1][0].strftime("%b %-d, %Y")
        elif ind["id"] in ("curve", "realyield", "oil"):
            period = latest_period(ind["id"], L) + " average"
        else:
            period = latest_period(ind["id"], L)
        item = {"id": ind["id"], "name": ind["name"], "series": ind["series"], "rule": ind["rule"],
                "url": "https://fred.stlouisfed.org/series/" + ind["series"], "period": period}
        if r:
            item.update(r)
        latest.append(item)
    sc = score(latest)

    # History: monthly composite from 1990.
    hist = []
    ym = start
    while ym <= end:
        rs = [evaluate(ind["id"], L, ym) for ind in INDICATORS]
        s = score(rs)
        if s and s["reporting"] >= 6:
            hist.append({"m": ym_str(ym), "pos": s["position"], "n": s["reporting"]})
        ym = shift(ym, 1)

    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "seed": False,
        "source": "Federal Reserve Bank of St. Louis (FRED)",
        "latest": dict(sc or {}, indicators=latest, asOf=today.isoformat()),
        "history": hist,
        "recessions": recessions(raw["USREC"]),
    }

# ---------------------------------------------------------------- prices

BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
              "Accept": "application/json,text/csv,*/*"}


def get_text(url):
    req = urllib.request.Request(url, headers=BROWSER_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def yahoo_price(symbol):
    js = json.loads(get_text(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"))
    meta = js["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    ts = meta.get("regularMarketTime")
    if price is None:
        raise RuntimeError("no regularMarketPrice")
    date = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat() if ts else None
    return {"price": float(price), "date": date, "source": "Yahoo Finance"}


def stooq_price(symbol):
    text = get_text(f"https://stooq.com/q/l/?s={urllib.parse.quote(symbol)}&f=sd2c&h&e=csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise RuntimeError("empty response: " + text[:80].replace("\n", " "))
    r = rows[0]
    close = r.get("Close")
    if close in (None, "", "N/D"):
        raise RuntimeError("no close: " + text[:80].replace("\n", " "))
    return {"price": float(close), "date": r.get("Date"), "source": "Stooq"}


def update_prices():
    calls = json.load(open(os.path.join(ROOT, "content", "calls.json")))
    out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "prices": {}, "errors": {}}
    try:  # keep prices entered by hand (marked "manual": true)
        old = json.load(open(os.path.join(DATA, "prices.json")))
        out["prices"].update({k: v for k, v in old.get("prices", {}).items() if v.get("manual")})
    except Exception:
        pass
    for c in calls["calls"]:
        if c["id"] in out["prices"]:
            continue
        errs = []
        for fn, sym in ((yahoo_price, c.get("yahoo")), (stooq_price, c.get("stooq"))):
            if not sym:
                continue
            try:
                out["prices"][c["id"]] = fn(sym)
                break
            except Exception as e:
                errs.append(f"{fn.__name__}({sym}): {type(e).__name__}: {str(e)[:120]}")
        if c["id"] not in out["prices"] and errs:
            out["errors"][c["id"]] = errs
    # open positions, keyed "pos:TICKER"
    try:
        book = json.load(open(os.path.join(ROOT, "content", "positions.json")))
    except Exception:
        book = {"positions": []}
    for p in book.get("positions", []):
        key = "pos:" + p["ticker"].upper()
        if key in out["prices"]:
            continue
        sym = p.get("yahoo") or p["ticker"].upper().replace(".", "-").replace("/", "-")
        try:
            out["prices"][key] = yahoo_price(sym)
        except Exception as e:
            out["errors"][key] = [f"yahoo_price({sym}): {type(e).__name__}: {str(e)[:120]}"]
    return out

# ---------------------------------------------------------------- main

def main():
    os.makedirs(DATA, exist_ok=True)
    ok = True
    try:
        raw = {s: fred(s) for s in SERIES_IDS}
        cycle = build_cycle(raw)
        json.dump(cycle, open(os.path.join(DATA, "cycle.json"), "w"), indent=1)
        print("cycle:", cycle["latest"].get("position"), cycle["latest"].get("phase"), len(cycle["history"]), "months")
    except Exception as e:
        ok = False
        print(f"cycle update failed, keeping the previous file: {e}", file=sys.stderr)
    try:
        prices = update_prices()
        # always written, so failures are visible in the repository
        json.dump(prices, open(os.path.join(DATA, "prices.json"), "w"), indent=1)
        print("prices:", len(prices["prices"]), "errors:", json.dumps(prices["errors"]))
    except Exception as e:
        print(f"price update failed, keeping the previous file: {e}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
