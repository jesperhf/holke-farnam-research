"""Candidate rulebooks for a hands-off ETF sleeve. Rules come from the literature (10-month trend, 12-1 momentum);
nothing below is tuned to this data. Selection criterion fixed before running: highest Sharpe with max drawdown no worse than -25%.

Monthly decisions at month-end close, trades at that close, 0.10% cost per unit of one-way turnover.
Cash = BIL (1-3 month T-bills), SHY before BIL existed.
"""
import os, numpy as np, pandas as pd
M = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history")
COST = 0.001
IND = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC", "SMH", "IGV", "GRID", "XBI", "IHI", "IHF",
       "XOP", "AMLP", "XME", "KRE", "ITA", "IYT", "ITB", "XRT"]
ALL = IND + ["SPY", "EFA", "IEF", "GLD", "DBC", "BIL", "SHY", "AGG"]
px = pd.DataFrame({s: pd.read_csv(os.path.join(M, f"{s}.csv"), parse_dates=["date"]).set_index("date").loc[:"2026-11-18", "adjclose"] for s in ALL})
me = px.resample("ME").last()
R = me.pct_change()
cash_r = R["BIL"].fillna(R["SHY"])
sma10 = me.rolling(10).mean()
up = me > sma10
r12_1 = me.shift(1) / me.shift(12) - 1
avail = me[IND].notna() & me[IND].shift(13).notna()

def defensive():  # intermediate Treasuries when they are in an uptrend, else T-bills
    return lambda t: {"IEF": 1.0} if up.loc[t, "IEF"] else {"CASH": 1.0}

def A(t):  # US stock trend
    return {"SPY": 1.0} if up.loc[t, "SPY"] else defensive()(t)

def B(t):  # trend switch, industry momentum inside equity mode
    if not up.loc[t, "SPY"]:
        return defensive()(t)
    s = (r12_1.loc[t, IND] - r12_1.loc[t, "SPY"]).where(avail.loc[t]).dropna()
    picks = list(s.sort_values(ascending=False).index[:5])
    w = {"SPY": 0.5}
    for p in picks: w[p] = w.get(p, 0) + 0.1
    return w

def C(t):  # five-asset trend
    w = {}
    for a in ["SPY", "EFA", "IEF", "GLD", "DBC"]:
        k = a if up.loc[t, a] else "CASH"; w[k] = w.get(k, 0) + 0.2
    return w

def run(fn, start):
    idx = [t for t in me.index if t >= start]
    out, prev = [], {}
    for i in range(len(idx) - 1):
        t, n = idx[i], idx[i + 1]
        w = fn(t)
        keys = set(w) | set(prev)
        turn = sum(abs(w.get(k, 0) - prev.get(k, 0)) for k in keys)
        r = sum(wt * (cash_r.loc[n] if a == "CASH" else R.loc[n, a]) for a, wt in w.items()) - COST * turn
        out.append((n, r, turn)); prev = w
    s = pd.DataFrame(out, columns=["date", "r", "turn"]).set_index("date")
    return s["r"], s["turn"].mean() * 12

def stats(r):
    eq = (1 + r).cumprod(); y = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / y) - 1; vol = r.std() * np.sqrt(12)
    ex = r - cash_r.reindex(r.index); sh = ex.mean() / ex.std() * np.sqrt(12)
    dd = (eq / eq.cummax() - 1).min()
    yr = (1 + r).groupby(r.index.year).prod() - 1
    return cagr, vol, sh, dd, yr

start = pd.Timestamp("2006-12-31")
rows = {}
spy = R["SPY"].loc[start + pd.offsets.MonthEnd(1):]
b6040 = run(lambda t: {"SPY": 0.6, "AGG": 0.4}, start)[0]
for lab, fn in (("A. US stock trend (SPY or Treasuries/T-bills)", A), ("B. Trend switch + industry momentum tilt", B), ("C. Five-asset trend", C)):
    r, turn = run(fn, start); rows[lab] = (r, turn)
print("Jan 2007 to Nov 2026, monthly, after 0.10% costs")
print(f"{'':48s} {'CAGR':>6s} {'Vol':>6s} {'Sharpe':>7s} {'MaxDD':>7s} {'Turnover/yr':>12s}")
for lab, r in (("SPY", spy), ("60/40 SPY/AGG", b6040)):
    c, v, s, d, _ = stats(r.dropna()); print(f"{lab:48s} {c*100:6.1f} {v*100:6.1f} {s:7.2f} {d*100:7.1f}")
for lab, (r, turn) in rows.items():
    c, v, s, d, _ = stats(r.dropna()); print(f"{lab:48s} {c*100:6.1f} {v*100:6.1f} {s:7.2f} {d*100:7.1f} {turn*100:11.0f}%")
print("\nCalendar-year returns:")
yrs = pd.DataFrame({"SPY": stats(spy)[4], **{k[:2]: stats(v[0])[4] for k, v in rows.items()}})
print((yrs * 100).round(1).to_string())
for lab, (r, _) in rows.items():
    x = (r - spy.reindex(r.index)).dropna()
    print(f"{lab[:2]} years ahead of SPY: {(yrs[lab[:2]] > yrs['SPY']).sum()} of {len(yrs)}")
# current signal (as of Nov 18 close, a mid-month check)
t = me.index[-1]
print(f"\nSignals as of {t:%b %d, %Y}: SPY above 10-month avg: {bool(up.loc[t,'SPY'])}, IEF: {bool(up.loc[t,'IEF'])}, EFA: {bool(up.loc[t,'EFA'])}, GLD: {bool(up.loc[t,'GLD'])}, DBC: {bool(up.loc[t,'DBC'])}")
print("B would hold:", B(t)); print("C would hold:", C(t))
