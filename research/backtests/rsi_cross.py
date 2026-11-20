"""RSI(14) crossing its 14-day simple moving average (TradingView's default RSI-based MA).
Cross up -> long, cross down -> short, entered at that day's close.
Exit: close reaches the take-profit (+X% for longs, -X% for shorts), or the opposite cross, whichever comes first.
An opposite cross also opens the new position. Flat days earn T-bills. Costs 0.02% per side; short borrow cost ignored.
Daily closes only (no intraday fills), so take-profits fill at the close that crosses the level.
"""
import os, sys, numpy as np, pandas as pd
Q = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(os.path.dirname(os.path.dirname(Q)), "history")
COST = 0.0002
IND = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC", "SMH", "IGV", "GRID", "XBI", "IHI", "IHF",
       "XOP", "AMLP", "XME", "KRE", "ITA", "IYT", "ITB", "XRT"]
P = {s: pd.read_csv(os.path.join(M, f"{s}.csv"), parse_dates=["date"]).set_index("date").loc[:"2026-11-18", "adjclose"] for s in IND + ["SPY", "BIL"]}
def rsi(p, n=14):
    d = p.diff(); au = d.clip(lower=0).ewm(alpha=1/n, adjust=False, min_periods=n).mean(); ad = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + au / ad)
bil = P["BIL"].pct_change()
def rf_for(idx):
    r = bil.reindex(idx).fillna(0.0001)  # about 2.5% a year before BIL data begins
    return r

def simulate(p, tp, sides=("long", "short")):
    r = rsi(p); ma = r.rolling(14).mean()
    up = (r > ma) & (r.shift(1) <= ma.shift(1)); dn = (r < ma) & (r.shift(1) >= ma.shift(1))
    pos = np.zeros(len(p)); entry = None; side = 0; trades = []
    pv = p.values; U = up.values; D = dn.values
    for i in range(len(p)):
        if side != 0:
            chg = pv[i] / entry - 1
            hit = (side == 1 and chg >= tp) or (side == -1 and chg <= -tp)
            flip = (side == 1 and D[i]) or (side == -1 and U[i])
            if hit or flip:
                trades.append((side, side * chg - 2 * COST, "target" if hit else "reverse", p.index[i].year)); side = 0
        if side == 0:
            if U[i] and "long" in sides and not (trades and trades[-1][2] == "target" and False):
                side, entry = 1, pv[i]
            elif D[i] and "short" in sides:
                side, entry = -1, pv[i]
        pos[i] = side
    return pd.Series(pos, index=p.index), trades

def equity(p, pos):
    r = p.pct_change().fillna(0); h = pos.shift(1).fillna(0)
    rf = rf_for(p.index)
    out = h * r + (h == 0) * rf - pos.diff().abs().fillna(0) * COST
    return out

def stats(r):
    eq = (1 + r).cumprod(); y = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / y) - 1; vol = r.std() * np.sqrt(252); sh = (r.mean() * 252 - 0.025) / vol
    return cagr, vol, sh, (eq / eq.cummax() - 1).min()

spy = P["SPY"]; st = spy.index[30]
c, v, s, d = stats(spy.pct_change().fillna(0).loc[st:])
print(f"SPY buy and hold 1993-2026: CAGR {c*100:.1f}%  vol {v*100:.1f}%  maxDD {d*100:.1f}%\n")
for tp in (0.02, 0.03, 0.05):
    for sides, lab in ((("long", "short"), "long and short"), (("long",), "long only")):
        pos, tr = simulate(spy, tp, sides)
        r = equity(spy, pos).loc[st:]
        c, v, s, d = stats(r)
        t = pd.DataFrame(tr, columns=["side", "ret", "how", "year"])
        line = f"SPY, take-profit {tp*100:.0f}%, {lab:15s} CAGR {c*100:5.1f}%  vol {v*100:4.1f}%  maxDD {d*100:6.1f}%  trades {len(t)/33.8:4.1f}/yr  win {np.mean(t.ret>0)*100:3.0f}%  avg {t.ret.mean()*100:+.2f}%"
        print(line)
        if lab == "long and short":
            for sd, nm in ((1, "longs"), (-1, "shorts")):
                x = t[t.side == sd]; print(f"      {nm:6s}: n={len(x)}, win {np.mean(x.ret>0)*100:.0f}%, avg {x.ret.mean()*100:+.2f}%, hit target {np.mean(x.how=='target')*100:.0f}%, avg loser {x.ret[x.ret<=0].mean()*100:+.2f}%")
            for a, b in ((1993, 2009), (2010, 2026)):
                x = t[(t.year >= a) & (t.year <= b)]; print(f"      {a}-{b}: avg trade {x.ret.mean()*100:+.2f}% (n={len(x)}, t={x.ret.mean()/x.ret.std()*np.sqrt(len(x)):.1f})")
    print()

print("Pooled across SPY and 25 sector ETFs, take-profit 3%, average trade by side:")
allt = []
for s_ in ["SPY"] + IND:
    _, tr = simulate(P[s_].dropna(), 0.03); allt += [(s_,) + x for x in tr]
T = pd.DataFrame(allt, columns=["etf", "side", "ret", "how", "year"])
for sd, nm in ((1, "longs"), (-1, "shorts")):
    x = T[T.side == sd]; print(f"  {nm}: n={len(x)}, win {np.mean(x.ret>0)*100:.0f}%, avg {x.ret.mean()*100:+.2f}% (t={x.ret.mean()/x.ret.std()*np.sqrt(len(x)):.1f}), average winner {x.ret[x.ret>0].mean()*100:+.2f}%, average loser {x.ret[x.ret<=0].mean()*100:+.2f}%")
x = T; print(f"  all: avg {x.ret.mean()*100:+.3f}% per trade, t={x.ret.mean()/x.ret.std()*np.sqrt(len(x)):.1f}, n={len(x)}")
