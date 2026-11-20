import os, glob, json
import numpy as np, pandas as pd
D="."; CUTOFF="2026-11-18"
ETFS = ["XLK","XLV","XLF","XLE","XLI","XLY","XLP","XLU","XLB","XLRE","XLC","SMH","IGV","GRID","XBI","IHI","IHF","XOP","AMLP","XME","KRE","ITA","IYT","ITB","XRT"]
NAMES={"XLK":"Technology","XLV":"Health care","XLF":"Financials","XLE":"Energy","XLI":"Industrials","XLY":"Consumer discretionary","XLP":"Consumer staples","XLU":"Utilities","XLB":"Materials","XLRE":"Real estate","XLC":"Communication services","SMH":"Semiconductors","IGV":"Software","GRID":"Power grid infrastructure","XBI":"Biotech","IHI":"Medical devices","IHF":"Health insurers and providers","XOP":"Oil and gas producers","AMLP":"Pipelines (MLPs)","XME":"Metals and mining","KRE":"Regional banks","ITA":"Aerospace and defense","IYT":"Transports","ITB":"Homebuilders","XRT":"Retail"}
syms=[os.path.basename(f)[:-4] for f in glob.glob("*.csv")]
px=pd.DataFrame({s:pd.read_csv(f"{s}.csv",parse_dates=["date"]).set_index("date").loc[:CUTOFF,"adjclose"] for s in syms}).ffill(limit=3)
d=px.index[-1]
def ret(s, a, b=0):
    p=px[s].dropna(); 
    return p.iloc[-1-b*21]/p.iloc[-1-a*21]-1 if len(p)>a*21+1 else np.nan
rows=[]
for k in ETFS:
    r12=ret(k,12,1)-ret("SPY",12,1); r6=ret(k,6)-ret("SPY",6); r3=ret(k,3)-ret("SPY",3)
    rows.append(dict(etf=k,name=NAMES[k],r12_1=r12,r6=r6,r3=r3))
t=pd.DataFrame(rows).set_index("etf")
for c in ("r12_1","r6","r3"): t[c+"_rk"]=t[c].rank(pct=True)
t["score"]=t[["r12_1_rk","r6_rk","r3_rk"]].mean(axis=1)
ema=lambda s,n: s.ewm(span=n,adjust=False,min_periods=n).mean()
def emas(s):
    p=px[s].dropna(); out={}
    for n in (21,50,200): out[f"e{n}"]=p.iloc[-1]/ema(p,n).iloc[-1]-1
    out["stack"]= "21>50>200" if ema(p,21).iloc[-1]>ema(p,50).iloc[-1]>ema(p,200).iloc[-1] else ("below 200" if p.iloc[-1]<ema(p,200).iloc[-1] else "mixed")
    out["above_sma200"]=p.iloc[-1]>p.rolling(200).mean().iloc[-1]
    return out
for k in ETFS:
    for kk,v in emas(k).items(): t.loc[k,kk]=v
def label(r):
    if r.score>=0.8 and r.above_sma200: return "Leading"
    if r.r12_1_rk<0.5 and r.r3_rk>=0.6: return "Turning up"
    if r.r12_1_rk>=0.5 and r.r3_rk<0.4: return "Fading"
    if r.score<0.4: return "Lagging"
    return "Middle"
t["label"]=t.apply(label,axis=1)
t=t.sort_values("score",ascending=False)
pd.set_option("display.width",220)
show=t[["name","label","score","r12_1","r6","r3","e21","e50","e200","stack"]].copy()
for c in ("r12_1","r6","r3","e21","e50","e200"): show[c]=(show[c]*100).round(1)
show["score"]=(show["score"]*100).round(0)
print(f"As of {d:%b %d, %Y} close. Returns relative to SPY, %. EMA columns: price vs EMA, %.")
print(show.to_string())
H=[s for s in syms if s not in ETFS+["SPY","RSP"]]
hr=[]
for s in sorted(H):
    p=px[s].dropna()
    if len(p)<210: hr.append(dict(t=s,note=f"only {len(p)} days of history")); continue
    e=emas(s); hr.append(dict(t=s,price=round(p.iloc[-1],2),e21=round(e["e21"]*100,1),e50=round(e["e50"]*100,1),e200=round(e["e200"]*100,1),stack=e["stack"]))
print("\nHoldings: price vs EMA, %")
print(pd.DataFrame(hr).set_index("t").to_string())
t.to_csv("current_industries.txt"); pd.DataFrame(hr).to_csv("current_holdings_ema.txt",index=False)
