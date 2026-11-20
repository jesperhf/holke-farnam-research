"""Strategy research backtests.

Data: Kenneth French Data Library (monthly, July 1926 to September 2026) and daily ETF prices from Yahoo (adjusted).
All returns are total returns. Long-only strategies pay 0.10% per unit of one-way turnover.
"""
import io, os, numpy as np, pandas as pd

Q = os.path.dirname(os.path.abspath(__file__))
M = os.path.join(os.path.dirname(Q), "mom")
COST = 0.001


def french(fn, section=None):
    lines = open(os.path.join(Q, fn), encoding="latin-1").read().splitlines()
    start = 0
    if section:
        start = next(i for i, l in enumerate(lines) if section in l) + 1
    else:
        start = next(i for i, l in enumerate(lines) if l.startswith(","))
    hdr = start if lines[start].startswith(",") else start
    while not lines[hdr].startswith(","):
        hdr += 1
    body = []
    for l in lines[hdr + 1:]:
        if not l.strip() or not l.strip()[0].isdigit():
            break
        body.append(l)
    df = pd.read_csv(io.StringIO("\n".join([lines[hdr]] + body)), index_col=0)
    df.columns = [c.strip() for c in df.columns]
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    df = df.replace([-99.99, -999], np.nan) / 100
    return df


ff3 = french("F-F_Research_Data_Factors.csv")
ff5 = french("F-F_Research_Data_5_Factors_2x3.csv")
mom = french("F-F_Momentum_Factor.csv")
ind = french("49_Industry_Portfolios.csv", "Average Value Weighted Returns -- Monthly")
RF = ff3["RF"]
MKT = ff3["Mkt-RF"] + RF


def stats(r, rf=RF):
    r = r.dropna()
    yrs = len(r) / 12
    eq = (1 + r).cumprod()
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(12)
    ex = (r - rf.reindex(r.index)).dropna()
    sharpe = ex.mean() / ex.std() * np.sqrt(12)
    dd = (eq / eq.cummax() - 1).min()
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd, start=r.index[0].year, end=r.index[-1].year)


def fmt(d, lab):
    return f"{lab:46s} {d['start']}-{d['end']}  CAGR {d['cagr']*100:5.1f}%  vol {d['vol']*100:5.1f}%  Sharpe {d['sharpe']:5.2f}  maxDD {d['maxdd']*100:6.1f}%"


out = []
P = lambda *a: (print(*a), out.append(" ".join(str(x) for x in a)))

# ---------- 1. Factor premia, before and after publication (long-short, gross) ----------
P("1. FACTOR PREMIA (long-short, gross of costs), mean annual return and t-stat, split at the year the factor was published")
fac = pd.DataFrame({"Market (Mkt-RF)": ff3["Mkt-RF"], "Size (SMB)": ff3["SMB"], "Value (HML)": ff3["HML"], "Momentum (UMD)": mom["Mom"],
                    "Profitability (RMW)": ff5["RMW"], "Investment (CMA)": ff5["CMA"]})
pub = {"Market (Mkt-RF)": 1964, "Size (SMB)": 1981, "Value (HML)": 1992, "Momentum (UMD)": 1993, "Profitability (RMW)": 2013, "Investment (CMA)": 2015}
def tstat(x):
    x = x.dropna(); return x.mean() / x.std() * np.sqrt(len(x))
for k, y in pub.items():
    x = fac[k].dropna(); pre = x[x.index.year < y]; post = x[x.index.year >= y]
    P(f"  {k:22s} full {x.index[0].year}-{x.index[-1].year}: {x.mean()*1200:5.1f}%/yr t={tstat(x):4.1f} | before {y}: {pre.mean()*1200:5.1f}% t={tstat(pre):4.1f} | {y} on: {post.mean()*1200:5.1f}% t={tstat(post):4.1f}")
corr = fac[["Value (HML)", "Momentum (UMD)", "Profitability (RMW)"]].dropna().corr()
P(f"  Correlation value vs momentum: {corr.iloc[0,1]:.2f}; value vs profitability: {corr.iloc[0,2]:.2f}; momentum vs profitability: {corr.iloc[1,2]:.2f}")
combo = fac[["Value (HML)", "Momentum (UMD)", "Profitability (RMW)", "Investment (CMA)"]].dropna().mean(axis=1)
for k in ["Value (HML)", "Momentum (UMD)", "Profitability (RMW)"]:
    x = fac[k].loc[combo.index]; P(f"  Sharpe {k:22s} {x.mean()/x.std()*np.sqrt(12):.2f}")
P(f"  Sharpe equal mix of value, momentum, profitability, investment: {combo.mean()/combo.std()*np.sqrt(12):.2f} (1963 on)")
for a, b in ((1963, 1999), (2000, 2026)):
    c = combo[(combo.index.year >= a) & (combo.index.year <= b)]
    P(f"    mix {a}-{b}: {c.mean()*1200:4.1f}%/yr, Sharpe {c.mean()/c.std()*np.sqrt(12):.2f}")
worst = combo.rolling(12).sum().min(); P(f"  Worst 12 months for the mix: {worst*100:.1f}%")
for k in fac:
    x = fac[k].dropna(); r10 = x.rolling(120).sum()
    P(f"  {k:22s} share of rolling 10-year periods with a negative premium: {(r10.dropna() < 0).mean()*100:.0f}%")

# ---------- 2. Trend following on the US stock market (10-month average) ----------
P("\n2. TREND FOLLOWING, US stock market: hold stocks when the market index is above its 10-month average, else T-bills")
idx = (1 + MKT).cumprod()
sig = (idx > idx.rolling(10).mean()).shift(1)  # decide at month-end t-1, earn month t
pos = sig.astype(float)
trade = pos.diff().abs().fillna(0)
tf = pos * MKT + (1 - pos) * RF - trade * COST
tf = tf.dropna().iloc[10:]
bh = MKT.loc[tf.index]
for lab, a, b in (("Full", 1927, 2026), ("Before publication (to 2006)", 1927, 2006), ("Since Faber 2007", 2007, 2026), ("Post-1950", 1950, 2026)):
    sel = (tf.index.year >= a) & (tf.index.year <= b)
    P(fmt(stats(tf[sel]), f"  Trend, {lab}")); P(fmt(stats(bh[sel]), f"  Buy and hold, {lab}"))
P(f"  Months in stocks: {pos.loc[tf.index].mean()*100:.0f}%; switches per year: {trade.loc[tf.index].sum()/len(tf)*12:.1f}")
for a, b, lab in (("1929-09", "1932-06", "1929-32 crash"), ("2000-09", "2002-09", "2000-02 bear"), ("2007-10", "2009-02", "2008 crisis"), ("2020-02", "2020-03", "COVID crash"), ("2022-01", "2022-09", "2022")):
    P(f"    {lab:14s} trend {((1+tf.loc[a:b]).prod()-1)*100:+6.1f}%   buy-and-hold {((1+bh.loc[a:b]).prod()-1)*100:+6.1f}%")
P("    Missed upside, years trend trailed buy-and-hold by 10+ points:", int(((tf.groupby(tf.index.year).apply(lambda x:(1+x).prod()-1) - bh.groupby(bh.index.year).apply(lambda x:(1+x).prod()-1)) < -0.10).sum()))

# ---------- 3. Industry momentum and reversal, 49 industries since 1927 ----------
P("\n3. INDUSTRY MOMENTUM, 49 Fama-French industries (value-weighted), monthly, long-only top or bottom 5")
I = ind.copy()
r12_1 = (1 + I).rolling(11).apply(np.prod, raw=True).shift(1) - 1  # months t-11..t-1, skipping t
res = {}
for lab, asc, look in (("Top 5 by 12-1 momentum", False, r12_1), ("Bottom 5 by 12-1 (reversal)", True, r12_1),
                       ("Top 5 by 1-month return", False, I), ("Bottom 5 by 1-month return", True, I)):
    rets, prev = [], set()
    for t in range(13, len(I) - 1):
        s = look.iloc[t].dropna()
        if len(s) < 20: rets.append(np.nan); continue
        picks = set(s.sort_values(ascending=asc).index[:5])
        turn = len(picks ^ prev) / 5 if prev else 1; prev = picks
        rets.append(I.iloc[t + 1][list(picks)].mean() - COST * turn)
    res[lab] = pd.Series(rets, index=I.index[14:len(I)])
ew = I.mean(axis=1).loc[res["Top 5 by 12-1 momentum"].index]
P(fmt(stats(ew), "  Equal weight, all 49 industries"))
P(fmt(stats(MKT.loc[ew.index]), "  US market"))
for k, v in res.items():
    P(fmt(stats(v), f"  {k}"))
for a, b in ((1927, 1998), (1999, 2026)):
    sel = lambda s: s[(s.index.year >= a) & (s.index.year <= b)]
    x = sel(res["Top 5 by 12-1 momentum"]) - sel(ew)
    P(f"    Top 5 momentum minus equal weight, {a}-{b}: {x.mean()*1200:+.1f}%/yr, t={tstat(x):.1f}")

# ---------- 4. Multi-asset with ETFs, 2005 to 2026 ----------
P("\n4. MULTI-ASSET STRATEGIES WITH ETFs (daily data to Nov 18, 2026; monthly decisions)")
def etf(s):
    return pd.read_csv(os.path.join(M, f"{s}.csv"), parse_dates=["date"]).set_index("date").loc[:"2026-11-18", "adjclose"]
E = pd.DataFrame({s: etf(s) for s in ["SPY", "EFA", "AGG", "IEF", "GLD", "DBC", "VNQ", "BIL", "SHY", "TLT", "EEM"]}).resample("ME").last()
ER = E.pct_change()
cash = ER["BIL"].fillna(ER["SHY"])
start = E.dropna(subset=["SPY", "EFA", "AGG", "GLD", "DBC", "VNQ"]).index[12]
idxs = ER.loc[start:].index
def series(fn):
    out_, prevw = [], pd.Series(dtype=float)
    for i in range(len(idxs) - 1):
        t, n = idxs[i], idxs[i + 1]
        w = fn(t)
        k = w.index.union(prevw.index); turn = (w.reindex(k, fill_value=0) - prevw.reindex(k, fill_value=0)).abs().sum()
        r = sum(wt * (ER.loc[n, a] if a != "CASH" else cash.loc[n]) for a, wt in w.items()) - COST * turn
        out_.append(r); prevw = w
    return pd.Series(out_, index=idxs[1:])
ret12 = E / E.shift(12) - 1
sma10 = E.rolling(10).mean()
def gem(t):  # Antonacci dual momentum
    if ret12.loc[t, "SPY"] > ret12.loc[t, "SHY"]:
        return pd.Series({("SPY" if ret12.loc[t, "SPY"] >= ret12.loc[t, "EFA"] else "EFA"): 1.0})
    return pd.Series({"AGG": 1.0})
def trend5(t):  # equal weight five assets, each only when above its 10-month average
    w = {}
    for a in ["SPY", "EFA", "IEF", "GLD", "DBC"]:
        k = a if E.loc[t, a] > sma10.loc[t, a] else "CASH"; w[k] = w.get(k, 0) + 0.2
    return pd.Series(w)
s6040 = series(lambda t: pd.Series({"SPY": 0.6, "AGG": 0.4}))
P(fmt(stats(ER["SPY"].loc[s6040.index]), "  SPY"))
P(fmt(stats(s6040), "  60% SPY / 40% AGG, monthly rebalance"))
P(fmt(stats(series(gem)), "  Dual momentum (SPY/EFA/AGG)"))
P(fmt(stats(series(lambda t: pd.Series({a: 0.2 for a in ["SPY", "EFA", "IEF", "GLD", "DBC"]}))), "  Equal weight 5 assets, no trend rule"))
P(fmt(stats(series(trend5)), "  Equal weight 5 assets with 10-month trend rule"))

# ---------- 5. Volatility targeting on SPY ----------
P("\n5. VOLATILITY TARGETING, SPY 1993 to 2026: exposure = 15% / last month's realized volatility, capped at 100% (rest in T-bills)")
d = etf("SPY").pct_change().dropna()
rv = d.rolling(21).std() * np.sqrt(252)
me_rv = rv.resample("ME").last()
spym = (1 + d).resample("ME").prod() - 1
w = (0.15 / me_rv).clip(upper=1.0).shift(1)
rfm = RF.reindex(spym.index).ffill()
vt = (w * spym + (1 - w) * rfm - w.diff().abs() * COST).dropna()
P(fmt(stats(spym.loc[vt.index]), "  SPY buy and hold"))
P(fmt(stats(vt), "  SPY volatility-targeted"))
P(f"  Average exposure {w.loc[vt.index].mean()*100:.0f}%")

# ---------- 6. Factor ETFs (real implementation), 2014 to 2026 ----------
P("\n6. LONG-ONLY FACTOR ETFs, Jan 2014 to Nov 2026 (what an investor could actually buy)")
F = pd.DataFrame({s: etf(s) for s in ["SPY", "MTUM", "QUAL", "USMV", "VLUE", "IWD", "IWF", "IWM"]}).resample("ME").last().pct_change().loc["2014-01":]
for s, lab in (("SPY", "S&P 500"), ("MTUM", "Momentum"), ("QUAL", "Quality"), ("USMV", "Minimum volatility"), ("VLUE", "Value"), ("IWD", "Russell 1000 Value"), ("IWF", "Russell 1000 Growth"), ("IWM", "Russell 2000 (small)")):
    P(fmt(stats(F[s]), f"  {lab} ({s})"))

open(os.path.join(Q, "strategy_results.txt"), "w").write("\n".join(out))
