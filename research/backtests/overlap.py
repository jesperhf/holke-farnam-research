exec(open("strategies.py").read().split("# ---------- 4.")[0].replace("P(", "(lambda *a: None)("))
import numpy as np
top = res["Top 5 by 12-1 momentum"]; ewi = I.mean(axis=1).loc[top.index]
for a, b in ((2005, 2026), (2007, 2026), (2013, 2026), (2018, 2026)):
    sel = (top.index.year >= a) & (top.index.year <= b)
    x = top[sel] - ewi[sel]; y = top[sel] - MKT.loc[top.index][sel]
    print(f"{a}-{b}: top5 {stats(top[sel])['cagr']*100:5.1f}% | EW {stats(ewi[sel])['cagr']*100:5.1f}% | market {stats(MKT.loc[top.index][sel])['cagr']*100:5.1f}% | vs EW {x.mean()*1200:+.1f}%/yr t={tstat(x):.1f} | vs market {y.mean()*1200:+.1f}%/yr t={tstat(y):.1f}")
# robustness: top 3 / 10, and 6-month lookback, full and post-1999
r6 = (1 + I).rolling(6).apply(np.prod, raw=True) - 1
def run(look, n):
    rets, prev = [], set()
    for t in range(13, len(I) - 1):
        s = look.iloc[t].dropna(); picks = set(s.sort_values(ascending=False).index[:n])
        turn = len(picks ^ prev) / n if prev else 1; prev = picks
        rets.append(I.iloc[t + 1][list(picks)].mean() - COST * turn)
    return pd.Series(rets, index=I.index[14:len(I)])
for lab, look, n in (("12-1, top 3", r12_1, 3), ("12-1, top 10", r12_1, 10), ("6-month, top 5", r6, 5)):
    s = run(look, n); e = I.mean(axis=1).loc[s.index]
    for a in (1927, 1999):
        sel = s.index.year >= a; x = s[sel] - e[sel]
        print(f"{lab:16s} from {a}: CAGR {stats(s[sel])['cagr']*100:5.1f}% vs EW {stats(e[sel])['cagr']*100:5.1f}%  excess {x.mean()*1200:+.1f}%/yr t={tstat(x):.1f}")
