import numpy as np, pandas as pd
SEC = {"XLK":"Technology","XLV":"Health care","XLF":"Financials","XLE":"Energy","XLI":"Industrials","XLY":"Consumer discretionary",
       "XLP":"Consumer staples","XLU":"Utilities","XLB":"Materials","XLRE":"Real estate","XLC":"Communication services"}
CUT = "2026-11-18"
px = pd.DataFrame({s: pd.read_csv(f"{s}.csv", parse_dates=["date"]).set_index("date").loc[:CUT, "adjclose"] for s in list(SEC) + ["SPY"]})
ye = px.resample("YE").last()
ye = ye[ye.index.year < 2026]
ye.loc[px.index[-1]] = px.iloc[-1]          # 2026 year to date
yr = ye.pct_change()                         # calendar-year total return (2026 = YTD)
yr.index = yr.index.year
rows = []
for y in range(2000, 2027):
    prev = yr.loc[y - 1, list(SEC)].dropna()
    cur = yr.loc[y]
    elig = [s for s in prev.index if not np.isnan(cur[s])]
    prev = prev[elig]
    worst = prev.idxmin(); best = prev.idxmax()
    w2 = list(prev.sort_values().index[:2]); w3 = list(prev.sort_values().index[:3])
    rows.append(dict(year=y, worst=worst, worst_prev=prev.min(), worst_ret=cur[worst], w2=cur[w2].mean(), w3=cur[w3].mean(),
                     best=best, best_ret=cur[best], ew=cur[elig].mean(), spy=cur["SPY"], n=len(elig)))
t = pd.DataFrame(rows).set_index("year")
full = t.loc[:2025]
def summ(col):
    r = full[col]; g = (1 + r).prod() ** (1 / len(r)) - 1
    ex = r - full["spy"]; tt = ex.mean() / ex.std() * np.sqrt(len(ex))
    eq = (1 + r).cumprod(); dd = (eq / eq.cummax() - 1).min()
    return g, r.std(), (ex > 0).mean(), ex.mean(), tt, r.min(), dd
print("2000 to 2025 (26 full years), annual rebalance on Jan 1, total returns")
print(f"{'Strategy':38s} {'CAGR':>6s} {'Vol':>6s} {'Beat SPY':>9s} {'Avg excess':>11s} {'t':>5s} {'Worst yr':>9s} {'MaxDD*':>7s}")
for col, lab in (("spy","SPY"),("ew","Equal weight, all sectors"),("worst_ret","Worst prior-year sector"),("w2","Worst 2 sectors"),("w3","Worst 3 sectors"),("best_ret","Best prior-year sector")):
    g, v, h, ex, tt, mn, dd = summ(col)
    print(f"{lab:38s} {g*100:6.1f} {v*100:6.1f} {h*100:8.0f}% {ex*100:+10.1f}% {tt:5.2f} {mn*100:8.1f}% {dd*100:6.1f}%")
print("*MaxDD on year-end values only")
print("\nYear by year (worst sector = prior year's worst):")
for y, r in t.iterrows():
    tag = " (YTD to Nov 18)" if y == 2026 else ""
    print(f"{y}{tag:16s} {SEC[r.worst]:24s} prior {r.worst_prev*100:+6.1f}%  then {r.worst_ret*100:+6.1f}%  SPY {r.spy*100:+6.1f}%  {'beat' if r.worst_ret>r.spy else 'lagged'}")
for a, b in ((2000, 2008), (2009, 2017), (2018, 2025)):
    s = full.loc[a:b]; ex = (s.worst_ret - s.spy)
    print(f"{a}-{b}: worst sector minus SPY avg {ex.mean()*100:+.1f}%/yr, beat SPY {int((ex>0).sum())} of {len(ex)}")
t.to_csv("worst_sector_years.txt")
eq = (1 + full[["spy","ew","worst_ret","best_ret"]]).cumprod() * 100
print("\nGrowth of 100:"); print(eq.round(0).to_string())
