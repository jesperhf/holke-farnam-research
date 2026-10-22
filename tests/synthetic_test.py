import sys, os, math, random, datetime as dt, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import update_data as U
random.seed(1)
def months(a, b):
    y, m = a
    while (y, m) <= b:
        yield dt.date(y, m, 1)
        m += 1
        if m == 13: y, m = y + 1, 1
end = (2026, 10)
def mk(fn, freq="m", start=(1985,1)):
    out=[]
    if freq=="m":
        for d in months(start, end): out.append((d, fn(d)))
    elif freq=="q":
        for d in months(start, end):
            if d.month in (1,4,7,10): out.append((d, fn(d)))
    elif freq in ("d","w"):
        d=dt.date(*start,1); step=1 if freq=="d" else 7
        while d<=dt.date(2026,10,17):
            out.append((d, fn(d))); d+=dt.timedelta(days=step)
    return out
t=lambda d:(d.year-1985)+d.month/12
cyc=lambda d: math.sin(t(d)/8*2*math.pi)
raw={
 "UNRATE": mk(lambda d:5.5-1.5*cyc(d)),
 "PAYEMS": mk(lambda d:100000+t(d)*1500+200*cyc(d)),
 "ICSA": mk(lambda d:300000-60000*cyc(d)+random.uniform(-5000,5000),"w"),
 "CFNAIMA3": mk(lambda d:0.5*cyc(d)),
 "CPIAUCSL": mk(lambda d:100*1.025**t(d)),
 "CPILFESL": mk(lambda d:100*1.022**t(d)),
 "DFEDTAR": [(d,v) for d,v in mk(lambda d:round(3+2*cyc(d),2),"d") if d<dt.date(2008,12,16)],
 "DFEDTARU": [(d,v) for d,v in mk(lambda d:round(3+2*cyc(d),2),"d") if d>=dt.date(2008,12,16)],
 "T10Y3M": mk(lambda d:1-1.2*cyc(d),"d"),
 "A191RL1Q225SBEA": mk(lambda d:2+2*cyc(d),"q"),
 "DFII10": mk(lambda d:1.5+cyc(d),"d",(2003,1)),
 "DGS10": mk(lambda d:4+cyc(d),"d"),
 "DCOILBRENTEU": mk(lambda d:60+20*cyc(d),"d",(1987,5)),
 "CP": mk(lambda d:1000*1.05**t(d)*(1+0.1*cyc(d)),"q"),
 "SAHMREALTIME": mk(lambda d:max(0,-cyc(d))),
 "USREC": mk(lambda d:1 if cyc(d)<-0.9 else 0),
}
c=U.build_cycle(raw)
print(json.dumps(c["latest"],indent=1)[:2500]); print(len(c["history"]), c["history"][:2], c["history"][-2:], c["recessions"][:3])
