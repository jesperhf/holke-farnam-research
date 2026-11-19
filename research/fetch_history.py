"""One-off: download daily adjusted price history for the industry momentum research.
Runs in GitHub Actions (the research workspace cannot reach Yahoo). Writes research/history/<SYMBOL>.csv."""
import csv, json, os, sys, time, urllib.parse, urllib.request

ETFS = ["SPY", "RSP", "XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
        "SMH", "IGV", "GRID", "XBI", "IHI", "IHF", "XOP", "AMLP", "XME", "KRE", "ITA", "IYT", "ITB", "XRT"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
book = json.load(open(os.path.join(ROOT, "content", "positions.json")))
HOLD = []
for p in book["positions"]:
    if p.get("type", "Equity") == "Equity" or p["ticker"] in ("GLD", "XBI", "VGK"):
        HOLD.append(p.get("yahoo") or p["ticker"].upper().replace(".", "-"))
SYMS = sorted(set(ETFS + HOLD))
OUT = os.path.join(ROOT, "research", "history"); os.makedirs(OUT, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode()
        except Exception as e:
            err = e; time.sleep(2 + 3 * i)
    raise err

report = {}
for s in SYMS:
    try:
        js = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?period1=0&period2=9999999999&interval=1d&events=div%2Csplit&includeAdjustedClose=true"))
        r = js["chart"]["result"][0]
        ts = r["timestamp"]; q = r["indicators"]["quote"][0]; adj = r["indicators"]["adjclose"][0]["adjclose"]
        rows = 0
        with open(os.path.join(OUT, f"{s}.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["date", "open", "high", "low", "close", "adjclose", "volume"])
            for t, o, h, l, c, a, v in zip(ts, q["open"], q["high"], q["low"], q["close"], adj, q["volume"]):
                if c is None or a is None:
                    continue
                w.writerow([time.strftime("%Y-%m-%d", time.gmtime(t)), o, h, l, c, a, v]); rows += 1
        report[s] = rows
    except Exception as e:
        report[s] = f"error: {e}"
    time.sleep(0.5)
json.dump(report, open(os.path.join(OUT, "_report.json"), "w"), indent=1)
print(json.dumps(report, indent=1))
