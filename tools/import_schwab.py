"""Turn a Schwab positions export (CSV) into content/positions.json.

    python tools/import_schwab.py path/to/Positions.csv [--date 2026-10-23]

Only percentages and per-share prices are written. Quantities, market values
and cost totals are read in memory to compute weights and average cost, then
discarded. Never commit the CSV itself (*.csv is in .gitignore).

Existing details (opened dates, exit levels, research links, closed positions
and the trade log) are kept for tickers already in the file.
"""
import csv
import datetime as dt
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "content", "positions.json")


def num(s):
    s = (s or "").strip().replace("$", "").replace(",", "").replace("%", "")
    if s in ("", "--", "N/A", "n/a"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def find(row, *names):
    for k in row:
        kl = (k or "").lower()
        if any(kl.startswith(n) for n in names):
            return row[k]
    return None


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    snap = args[args.index("--date") + 1] if "--date" in args else None
    text = open(path, encoding="utf-8-sig").read()
    if not snap:
        m = re.search(r"as of .*?(\d{4})/(\d{1,2})/(\d{1,2})", text)
        if m:
            snap = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        else:
            m = re.search(r"as of .*?(\d{1,2})/(\d{1,2})/(\d{4})", text)
            snap = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else dt.date.today().isoformat()
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip('"').lower().startswith("symbol"))
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))

    holdings, cash_val = [], 0.0
    for r in rows:
        sym = (find(r, "symbol") or "").strip()
        mv = num(find(r, "mkt val", "market value"))
        if not sym or mv is None:
            continue
        stype0 = (find(r, "security type", "asset type") or "").strip().lower()
        if sym.lower().startswith("cash") or "money market" in stype0:
            cash_val += mv  # cash and money market funds count as cash
            continue
        if sym.lower().startswith("account total") or sym.lower().startswith("positions total"):
            continue
        qty = num(find(r, "qty", "quantity"))
        cost = num(find(r, "cost basis"))
        price = num(find(r, "price"))
        stype = (find(r, "security type", "asset type") or "").strip()
        avg = (cost / qty) if (cost and qty) else None
        holdings.append({"ticker": sym.upper(), "name": (find(r, "description") or "").strip().title(),
                         "mv": mv, "price": price, "avgCost": round(avg, 4) if avg else None, "type": stype})

    total = sum(h["mv"] for h in holdings) + cash_val
    old = json.load(open(DEST)) if os.path.exists(DEST) else {}
    keep = {p["ticker"]: p for p in old.get("positions", [])}
    out_pos = []
    for h in sorted(holdings, key=lambda h: -h["mv"]):
        p = dict(keep.get(h["ticker"], {}))
        p.update({"ticker": h["ticker"], "weight": round(h["mv"] / total * 100, 2), "snapPrice": h["price"], "avgCost": h["avgCost"]})
        p.setdefault("name", h["name"])
        if h["type"]:
            p.setdefault("type", h["type"])
        out_pos.append(p)
    gone = sorted(set(keep) - {p["ticker"] for p in out_pos})
    book = {
        "note": old.get("note", "Percentages and per-share prices only. Never store dollar amounts or share counts in this file: the repository is public."),
        "account": old.get("account", "Personal brokerage account"),
        "snapshot": snap,
        "cash": round(cash_val / total * 100, 2),
        "positions": out_pos,
        "closed": old.get("closed", []),
        "trades": old.get("trades", []),
    }
    json.dump(book, open(DEST, "w"), indent=1)
    print(f"{len(out_pos)} positions, cash {book['cash']:.1f}%, weights sum {sum(p['weight'] for p in out_pos) + book['cash']:.1f}%")
    if gone:
        print("No longer in the export (record these as closed with an exit price):", ", ".join(gone))


if __name__ == "__main__":
    main()
