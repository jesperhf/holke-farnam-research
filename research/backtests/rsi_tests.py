"""RSI and EMA rules, daily, close-to-close. Signals use the day's close; the position is entered at that close.
Costs 0.10% per side. When not invested, a stand-alone strategy earns T-bills (BIL from 2007, Fama-French RF before).
Exits fixed in advance: RSI(14) rules exit when RSI(14) rises above 50 or after 20 trading days; Connors RSI(2) exits when the
close is above its 5-day simple average (his published rule) or after 10 days.
"""
import os, numpy as np, pandas as pd
Q = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(os.path.dirname(os.path.dirname(Q)), "history")
COST = 0.001
IND = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC", "SMH", "IGV", "GRID", "XBI", "IHI", "IHF",
       "XOP", "AMLP", "XME", "KRE", "ITA", "IYT", "ITB", "XRT"]
load = lambda s: pd.read_csv(os.path.join(M, f"{s}.csv"), parse_dates=["date"]).set_index("date").loc[:"2026-11-18"]
P = {s: load(s)["adjclose"] for s in IND + ["SPY", "BIL"]}
spy = P["SPY"]; days = spy.index

# daily risk-free: Fama-French monthly RF spread evenly over trading days, BIL total return after 2007
ff = open(os.path.join(Q, "F-F_Research_Data_Factors.csv"), encoding="latin-1").read().splitlines()
h = next(i for i, l in enumerate(ff) if l.startswith(",Mkt-RF"))
rows = [l.split(",") for l in ff[h + 1:] if l[:6].strip().isdigit() and len(l.split(",")[0].strip()) == 6]
rfm = pd.Series({pd.Period(r[0].strip(), "M"): float(r[4]) / 100 for r in rows})
rf_d = pd.Series([rfm.get(d.to_period("M"), np.nan) for d in days], index=days)
cnt = rf_d.groupby(days.to_period("M")).transform("size")
rf_d = (rf_d / cnt).ffill()
bil = P["BIL"].pct_change().reindex(days)
rf_d = bil.where(bil.notna() & (days >= "2007-07-01"), rf_d).fillna(0)

def rsi(p, n):
    d = p.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(); ad = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + au / ad)
ema = lambda p, n: p.ewm(span=n, adjust=False, min_periods=n).mean()

RULES = {
    "Your rule: RSI(14)<30 and below 200-day EMA": dict(entry=lambda p, r14, r2: (r14 < 30) & (p < ema(p, 200)), exit=lambda p, r14, r2: r14 > 50, maxd=20),
    "Trend-aligned: RSI(14)<30 and above 200-day EMA": dict(entry=lambda p, r14, r2: (r14 < 30) & (p > ema(p, 200)), exit=lambda p, r14, r2: r14 > 50, maxd=20),
    "Connors: RSI(2)<10 and above 200-day average": dict(entry=lambda p, r14, r2: (r2 < 10) & (p > p.rolling(200).mean()), exit=lambda p, r14, r2: p > p.rolling(5).mean(), maxd=10),
}

def positions(p, rule):
    r14, r2 = rsi(p, 14), rsi(p, 2)
    en = rule["entry"](p, r14, r2).fillna(False).values; ex = rule["exit"](p, r14, r2).fillna(False).values
    pos = np.zeros(len(p)); held = 0; trades = []
    for i in range(len(p)):
        if held:
            held += 1
            if ex[i] or held > rule["maxd"]:
                trades.append((start_i, i)); held = 0; pos[i] = 0; continue
            pos[i] = 1
        elif en[i]:
            held = 1; start_i = i; pos[i] = 1
    return pd.Series(pos, index=p.index), trades

def stats(r):
    r = r.dropna(); eq = (1 + r).cumprod(); y = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / y) - 1; vol = r.std() * np.sqrt(252)
    ex = r - rf_d.reindex(r.index); sh = ex.mean() / ex.std() * np.sqrt(252)
    return cagr, vol, sh, (eq / eq.cummax() - 1).min()

line = lambda lab, s: print(f"{lab:62s} CAGR {s[0]*100:5.1f}%  vol {s[1]*100:5.1f}%  Sharpe {s[2]:5.2f}  maxDD {s[3]*100:6.1f}%")
sr = spy.pct_change()
st = spy.index[0] + pd.Timedelta(days=300)
print(f"PART 1. SPY alone, {st:%Y} to Nov 2026. In the market only after a signal, T-bills otherwise.")
line("SPY buy and hold", stats(sr.loc[st:]))
trade_rows = []
for lab, rule in RULES.items():
    pos, trades = positions(spy, rule)
    held = pos.shift(1).fillna(0)
    r = held * sr + (1 - held) * rf_d - pos.diff().abs().fillna(0) * COST
    line(lab, stats(r.loc[st:]))
    tr = np.array([spy.iloc[b] / spy.iloc[a] - 1 - 2 * COST for a, b in trades if spy.index[a] >= st])
    yrs = [spy.index[a].year for a, b in trades if spy.index[a] >= st]
    print(f"{'':6s}{len(tr)} trades, {len(tr)/((days[-1]-st).days/365.25):.1f} a year, win rate {np.mean(tr>0)*100:.0f}%, average trade {tr.mean()*100:+.2f}%, time invested {held.loc[st:].mean()*100:.0f}%")
    tr_s = pd.Series(tr, index=yrs)
    if "Connors" in lab:
        print(f"{'':6s}Before 2008 publication: avg trade {tr_s[tr_s.index < 2008].mean()*100:+.2f}% (n={int((tr_s.index<2008).sum())}); 2008 on: {tr_s[tr_s.index >= 2008].mean()*100:+.2f}% (n={int((tr_s.index>=2008).sum())})")

# Event study: forward returns after each entry signal vs all days, SPY and the 25 ETFs pooled
print("\nPART 2. Event study, SPY plus 25 sector and industry ETFs pooled: return over the next 5, 10 and 20 days after an entry signal, minus the average for all days in that ETF")
for lab, rule in RULES.items():
    acc = {5: [], 10: [], 20: []}
    for s in ["SPY"] + IND:
        p = P[s].dropna(); r14, r2 = rsi(p, 14), rsi(p, 2)
        en = rule["entry"](p, r14, r2).fillna(False)
        fire = en & ~en.shift(1, fill_value=False)
        for H in (5, 10, 20):
            f = p.shift(-H) / p - 1; base = f.mean()
            acc[H] += list((f[fire] - base).dropna().values)
    print(f"  {lab:58s} n={len(acc[20]):5d}  " + "  ".join(f"{H}d {np.mean(acc[H])*100:+.2f}% (t={np.mean(acc[H])/np.std(acc[H])*np.sqrt(len(acc[H])):.1f})" for H in (5, 10, 20)))

# Part 3: sleeve that holds SPY by default and rotates up to 5 slots of 20% into ETFs with an open signal
print(f"\nPART 3. Rotation sleeve: hold SPY by default; when an ETF signals, move a 20% slot into it until its exit (max 5 slots). 2000 to Nov 2026.")
st3 = pd.Timestamp("2000-01-01")
for lab, rule in RULES.items():
    pos = pd.DataFrame({s: positions(P[s].dropna(), rule)[0] for s in IND}).reindex(days).fillna(0)
    rets = pd.DataFrame({s: P[s].pct_change() for s in IND}).reindex(days).fillna(0)
    w = pd.DataFrame(0.0, index=days, columns=IND)
    held = []
    for i, d in enumerate(days):
        held = [s for s in held if pos.iloc[i][s] == 1]
        for s in pos.columns[pos.iloc[i].values == 1]:
            if s not in held and len(held) < 5: held.append(s)
        w.iloc[i][held] = 0.2 if held else 0
        for s in held: w.at[d, s] = 0.2
    wl = w.shift(1).fillna(0)
    spy_w = 1 - wl.sum(axis=1)
    r = (wl * rets).sum(axis=1) + spy_w * sr.fillna(0) - w.diff().abs().sum(axis=1).fillna(0) * COST * 2
    line(f"  {lab}", stats(r.loc[st3:]))
    print(f"{'':8s}average weight outside SPY: {wl.loc[st3:].sum(axis=1).mean()*100:.0f}%")
line("  SPY buy and hold, same period", stats(sr.loc[st3:]))
