"""Intraday quotes for the AI valuation revisit. Runs in GitHub Actions; writes research/quotes.json."""
import json, os, time, urllib.parse, urllib.request
SYMS = ["NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "AMAT", "VRT", "NVT", "FN", "COHR", "STX", "WDC", "000660.KS", "ENR.DE",
        "CLS", "GOOG", "NOW", "CRWV", "NBIS", "MSFT", "META", "AMZN", "ORCL", "ANET", "SPY", "QQQ", "SMH", "^GSPC", "^IXIC", "ANT",
        "MO", "KO", "JCPI", "UNH", "LNG", "EPD", "HYBL", "VGK", "BAC", "JPM", "XBI", "FSLR", "TMC", "MDT", "UBER", "ABT", "SPCX"]
out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "quotes": {}}
for s in SYMS:
    try:
        req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?range=1y&interval=1d",
                                     headers={"User-Agent": "Mozilla/5.0 (research script)"})
        m = json.loads(urllib.request.urlopen(req, timeout=30).read())["chart"]["result"][0]
        meta = m["meta"]; closes = [c for c in m["indicators"]["quote"][0]["close"] if c is not None]
        out["quotes"][s] = dict(price=meta.get("regularMarketPrice"), prev=meta.get("chartPreviousClose"), time=meta.get("regularMarketTime"),
                               high52=max(closes) if closes else None, low52=min(closes) if closes else None,
                               ytd_start=None, currency=meta.get("currency"))
        ts = m["timestamp"]; q = m["indicators"]["quote"][0]["close"]
        y = [c for t, c in zip(ts, q) if c is not None and time.gmtime(t).tm_year == 2025]
        out["quotes"][s]["close_2025"] = y[-1] if y else None
    except Exception as e:
        out["quotes"][s] = {"error": str(e)}
    try:
        req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?range=1d&interval=1m&includePrePost=true",
                                     headers={"User-Agent": "Mozilla/5.0 (research script)"})
        m = json.loads(urllib.request.urlopen(req, timeout=30).read())["chart"]["result"][0]
        pts = [(t, c) for t, c in zip(m.get("timestamp", []), m["indicators"]["quote"][0]["close"]) if c is not None]
        if pts:
            out["quotes"][s]["last_extended"] = pts[-1][1]; out["quotes"][s]["last_extended_time"] = pts[-1][0]
    except Exception as e:
        out["quotes"][s]["ext_error"] = str(e)
    time.sleep(0.5)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "quotes.json"), "w"), indent=1)
