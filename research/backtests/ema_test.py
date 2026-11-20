exec(open("backtest.py").read().split("res = {}")[0])
import numpy as np, pandas as pd
ema = lambda s, n: s.ewm(span=n, adjust=False, min_periods=n).mean()
H = 20  # trading days forward
fwd = daily.shift(-H) / daily - 1
fspy = fwd["SPY"]
# month-end label carried forward to each day of the next month
lead = ((comp >= 0.8) & (trend == 1)).reindex(daily.index, method="ffill").shift(1)  # use prior month-end label
rows = []
for k in ETFS:
    p = daily[k].dropna()
    e21, e50, e200 = ema(p, 21), ema(p, 50), ema(p, 200)
    uptrend = e50 > e200
    near = (p / e50 - 1).abs() <= 0.01
    was_above = (p / e50 - 1).rolling(20).max().shift(1) >= 0.03
    event = near & was_above & uptrend
    # one event per pullback: first day of each cluster (10-day gap)
    ev_days = event[event].index
    keep, last = [], None
    for d in ev_days:
        if last is None or (d - last).days > 14: keep.append(d)
        last = d
    L = lead[k].reindex(p.index).fillna(False).astype(bool)
    for d in keep:
        if d > pd.Timestamp(CUTOFF) - pd.Timedelta(days=35) or pd.isna(fwd.loc[d, k]): continue
        rows.append(dict(etf=k, date=d, leading=bool(L.loc[d]), rel=fwd.loc[d, k] - fspy.loc[d]))
    # baseline: every day in an uptrend (50>200), relative 20-day return
    base = (fwd[k] - fspy).reindex(p.index)[uptrend & base_ok(p) if False else uptrend].dropna()
    rows.append(dict(etf=k, date=None, leading=None, rel=None, base_mean=base.mean(), base_n=len(base)))
ev = pd.DataFrame([r for r in rows if r["date"] is not None])
bs = pd.DataFrame([r for r in rows if r["date"] is None])
def summ(x, lab):
    t = x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan
    print(f"{lab:58s} n={len(x):4d}  mean {x.mean()*100:+.2f}%  ahead {(x>0).mean()*100:.0f}%  t={t:.2f}")
print(f"20-day return vs SPY after a pullback to the 50-day EMA (within 1%, after being 3%+ above, 50-day EMA above 200-day)")
summ(ev["rel"], "All pullback events")
summ(ev.loc[ev.leading, "rel"], "Pullbacks in industries ranked Leading")
summ(ev.loc[~ev.leading, "rel"], "Pullbacks in other industries")
bm = (bs.base_mean * bs.base_n).sum() / bs.base_n.sum()
print(f"Baseline: average 20-day return vs SPY on any uptrend day: {bm*100:+.2f}%")
ev.to_csv("ema_events.txt", index=False)
