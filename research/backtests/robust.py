exec(open("backtest.py").read().split("res = {}")[0])
import numpy as np, pandas as pd
spy = pd.Series([fwd1.loc[m, "SPY"] for m in months], index=[m + pd.offsets.MonthEnd(1) for m in months])
ew = pd.Series([fwd1.loc[m, [k for k in ETFS if avail.loc[m, k]]].mean() for m in months], index=spy.index)
rows=[stats(spy,"SPY"), stats(ew,"Equal weight, all")]
# (a) avoid list: equal weight excluding bottom 5 by composite
r=[]
for m in months:
    s=comp.loc[m].dropna(); keep=[k for k in s.index if k not in set(s.sort_values().index[:5])]
    r.append(fwd1.loc[m,keep].mean()-COST*0.15)
rows.append(stats(pd.Series(r,index=spy.index),"Equal weight minus bottom 5"))
# (b) 11 sector SPDRs only, 12-1 momentum, top 3
SEC=["XLK","XLV","XLF","XLE","XLI","XLY","XLP","XLU","XLB","XLRE","XLC"]
rk=sig["m12_1"][SEC].rank(axis=1,pct=True)
r=[]; prev=set()
for m in months:
    s=rk.loc[m].dropna()
    if len(s)<6: r.append(np.nan); continue
    p=set(s.sort_values(ascending=False).index[:3]); t=len(p^prev)/3; prev=p
    r.append(fwd1.loc[m,list(p)].mean()-COST*t)
rows.append(stats(pd.Series(r,index=spy.index),"Sectors only, 12-1, top 3"))
# (c) quarterly rebalance, composite top 5
r=[]; picks=None
for i,m in enumerate(months):
    if i%3==0:
        s=comp.loc[m].dropna(); picks=list(s.sort_values(ascending=False).index[:5]); c=COST*0.6
    else: c=0
    r.append(fwd1.loc[m,picks].mean()-c)
rows.append(stats(pd.Series(r,index=spy.index),"Composite top 5, quarterly"))
# (d) top 5 composite vs equal-weight universe excess, and t-stat of Leading label 3m
t=pd.DataFrame(rows).set_index("label")
print((t[["cagr","vol","ratio","maxdd"]]*[100,100,1,100]).round(2).to_string())
top5=pd.read_csv("bt_comp5.txt",index_col=0,parse_dates=True).iloc[:,0]
bot5=pd.read_csv("bt_bottom5.txt",index_col=0,parse_dates=True).iloc[:,0]
x=(top5-ew).dropna(); print("\ntop5 minus equal weight: %+.2f%%/yr, t=%.2f" % (x.mean()*1200, x.mean()/x.std()*np.sqrt(len(x))))
x=(top5-bot5).dropna(); print("top5 minus bottom5:      %+.2f%%/yr, t=%.2f" % (x.mean()*1200, x.mean()/x.std()*np.sqrt(len(x))))
x=(top5-spy).dropna(); print("top5 minus SPY:          %+.2f%%/yr, t=%.2f" % (x.mean()*1200, x.mean()/x.std()*np.sqrt(len(x))))
