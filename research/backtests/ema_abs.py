exec(open("backtest.py").read().split("res = {}")[0])
import numpy as np, pandas as pd
ema = lambda s, n: s.ewm(span=n, adjust=False, min_periods=n).mean()
ev = pd.read_csv("ema_events.txt", parse_dates=["date"])
H=20; fwd = daily.shift(-H)/daily-1
a = np.array([fwd.loc[d,k] for k,d in zip(ev.etf, ev.date)])
base=[]
for k in ETFS:
    p=daily[k].dropna(); up=(ema(p,50)>ema(p,200)); f=fwd[k].reindex(p.index)[up].dropna(); base.append(f)
b=pd.concat(base)
print(f"Absolute 20-day return after pullback events: mean {a.mean()*100:+.2f}%, up {np.mean(a>0)*100:.0f}% (n={len(a)})")
print(f"Absolute 20-day return on any uptrend day:     mean {b.mean()*100:+.2f}%, up {(b>0).mean()*100:.0f}% (n={len(b)})")
# did the 50-day EMA 'hold'? share of events where price did not close more than 3% below the 50-day EMA within 20 days
held=[]
for k,d in zip(ev.etf, ev.date):
    p=daily[k].dropna(); e=ema(p,50); i=p.index.get_loc(d); w=(p.iloc[i+1:i+21]/e.iloc[i+1:i+21]-1)
    held.append((w>-0.03).all())
print(f"Events where price never closed 3%+ below the 50-day EMA over the next 20 days: {np.mean(held)*100:.0f}%")
