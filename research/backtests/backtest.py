"""Industry momentum backtest on sector and industry ETFs.

Monthly rebalance at month-end closes (adjusted for dividends and splits).
Signals, all measured relative to SPY:
  m12_1: return from 12 months ago to 1 month ago
  m6:    6-month return
  m3:    3-month return
Composite = average percentile rank of the three across the ETFs available that month.
Trend filter: month-end price above its 200-day simple average.
"""
import glob, os, json
import numpy as np
import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
CUTOFF = "2026-11-18"  # last full session; today's row is intraday
ETFS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
        "SMH", "IGV", "GRID", "XBI", "IHI", "IHF", "XOP", "AMLP", "XME", "KRE", "ITA", "IYT", "ITB", "XRT"]
COST = 0.001  # 10 bp per side on traded weight


def load(sym):
    df = pd.read_csv(os.path.join(D, f"{sym}.csv"), parse_dates=["date"]).set_index("date")
    return df.loc[:CUTOFF, "adjclose"].astype(float)


px = pd.DataFrame({s: load(s) for s in ETFS + ["SPY", "RSP"]})
daily = px.ffill(limit=3)
sma200 = daily.rolling(200, min_periods=200).mean()
me = daily.resample("ME").last()
me_sma = sma200.resample("ME").last()
avail = me[ETFS].notna() & me[ETFS].shift(13).notna()

rel = lambda a, b: a - b
r12_1 = me.shift(1) / me.shift(12) - 1
r6 = me / me.shift(6) - 1
r3 = me / me.shift(3) - 1
sig = {}
for name, r in (("m12_1", r12_1), ("m6", r6), ("m3", r3)):
    sig[name] = r[ETFS].sub(r["SPY"], axis=0).where(avail)
ranks = {k: v.rank(axis=1, pct=True) for k, v in sig.items()}
comp = (ranks["m12_1"] + ranks["m6"] + ranks["m3"]) / 3
trend = (me[ETFS] > me_sma[ETFS]).where(avail)
fwd1 = (me.shift(-1) / me - 1)

start = avail.sum(axis=1)
first = start[start >= 12].index[0]
months = [m for m in comp.index if m >= first and m < me.index[-1]]


def stats(r, label):
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(12)
    dd = (eq / eq.cummax() - 1).min()
    return dict(label=label, cagr=cagr, vol=vol, ratio=cagr / vol if vol else np.nan, maxdd=dd, months=len(r))


def run(score, top=5, trend_filter=False, fill="SPY"):
    rets, w_prev, turn = [], pd.Series(dtype=float), []
    for m in months:
        s = score.loc[m].dropna()
        if len(s) < top:
            rets.append(np.nan); continue
        picks = list(s.sort_values(ascending=False).index[:top])
        w = pd.Series(1 / top, index=picks)
        if trend_filter:
            ok = [p for p in picks if trend.loc[m, p] == 1]
            w = pd.Series(1 / top, index=ok)
            if len(ok) < top:
                w[fill] = w.get(fill, 0) + (top - len(ok)) / top
        allk = w.index.union(w_prev.index)
        t = (w.reindex(allk, fill_value=0) - w_prev.reindex(allk, fill_value=0)).abs().sum()
        turn.append(t)
        r = sum(wt * fwd1.loc[m, k] for k, wt in w.items()) - COST * t
        rets.append(r); w_prev = w
    out = pd.Series(rets, index=[m + pd.offsets.MonthEnd(1) for m in months])
    return out, float(np.mean(turn))


res = {}
spy = pd.Series([fwd1.loc[m, "SPY"] for m in months], index=[m + pd.offsets.MonthEnd(1) for m in months])
ew = pd.Series([fwd1.loc[m, [k for k in ETFS if avail.loc[m, k]]].mean() for m in months], index=spy.index)
rows = [stats(spy, "SPY"), stats(ew, "Equal weight, all ETFs available")]
for top in (3, 5, 7):
    r, t = run(comp, top); rows.append(stats(r, f"Composite, top {top}") | dict(turnover=t)); res[f"comp{top}"] = r
r, t = run(comp, 5, True); rows.append(stats(r, "Composite, top 5, trend filter") | dict(turnover=t)); res["comp5tf"] = r
for k in ("m12_1", "m6", "m3"):
    r, t = run(ranks[k], 5); rows.append(stats(r, f"{k} only, top 5") | dict(turnover=t)); res[k] = r
# bottom 5 as a check that the ranking carries information
r, _ = run(-comp, 5); rows.append(stats(r, "Composite, bottom 5")); res["bottom5"] = r

tab = pd.DataFrame(rows).set_index("label")
pd.set_option("display.width", 200)
print(f"Backtest {months[0]:%b %Y} to {months[-1] + pd.offsets.MonthEnd(1):%b %Y}, monthly rebalance, 10 bp per side")
print((tab[["cagr", "vol", "ratio", "maxdd"]] * [100, 100, 1, 100]).round(2).to_string())
print("turnover (avg one-way per month):", {k: round(v, 2) for k, v in tab.get("turnover", pd.Series()).dropna().items()})

# Sub-periods: excess over SPY, annualized
def excess(r, a, b):
    x = (r - spy).loc[a:b].dropna()
    return x.mean() * 12, (x > 0).mean(), len(x)
print("\nTop 5 composite minus SPY, by period (annualized mean excess, % of months ahead):")
for a, b in (("2007", "2012"), ("2013", "2019"), ("2020", "2026")):
    m_, h, n = excess(res["comp5"], a, b)
    m2, h2, _ = excess(res["comp5tf"], a, b)
    print(f"  {a}-{b}: plain {m_*100:+.1f}%/yr ({h*100:.0f}% of months)  trend-filtered {m2*100:+.1f}%/yr ({h2*100:.0f}%)  n={n}")

# Reversal episodes: relative return of top 5 vs SPY
print("\nReversal episodes, top 5 composite minus SPY (cumulative):")
for a, b, lab in (("2009-03", "2009-06", "Mar-Jun 2009 rebound"), ("2020-03", "2020-06", "Mar-Jun 2020 rebound"),
                  ("2022-01", "2022-06", "H1 2022 rate shock"), ("2026-10", "2026-11", "Oct-Nov 2026 AI whipsaw")):
    x = res["comp5"].loc[a:b]; y = spy.loc[a:b]
    print(f"  {lab}: strategy {((1+x).prod()-1)*100:+.1f}%  SPY {((1+y).prod()-1)*100:+.1f}%  n={len(x)}")

# Label test: forward 1- and 3-month returns relative to SPY by label
fwd3 = me.shift(-3) / me - 1
lab_rows = []
for m in months[:-3]:
    s12 = ranks["m12_1"].loc[m]; s3 = ranks["m3"].loc[m]; c = comp.loc[m]; tr = trend.loc[m]
    for k in c.dropna().index:
        if c[k] >= 0.8 and tr[k] == 1: L = "Leading"
        elif s12[k] < 0.5 and s3[k] >= 0.6: L = "Turning up"
        elif s12[k] >= 0.5 and s3[k] < 0.4: L = "Fading"
        elif c[k] < 0.4: L = "Lagging"
        else: L = "Middle"
        lab_rows.append(dict(label=L, f1=fwd1.loc[m, k] - fwd1.loc[m, "SPY"], f3=fwd3.loc[m, k] - fwd3.loc[m, "SPY"]))
lt = pd.DataFrame(lab_rows).groupby("label").agg(n=("f1", "size"), f1=("f1", "mean"), f3=("f3", "mean"),
                                                   hit3=("f3", lambda x: (x > 0).mean()))
print("\nForward return vs SPY by label (mean, % of cases ahead over 3 months):")
print((lt * [1, 100, 100, 100]).round(2).to_string())

out = dict(table=tab.reset_index().to_dict("records"), labels=lt.reset_index().to_dict("records"),
           start=str(months[0].date()), end=str(months[-1].date()))
json.dump(out, open(os.path.join(D, "backtest_results.json"), "w"), default=float, indent=1)
for k, v in res.items():
    v.to_csv(os.path.join(D, f"bt_{k}.txt"))
spy.to_csv(os.path.join(D, "bt_spy.txt"))
