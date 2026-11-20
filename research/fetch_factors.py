"""One-off: download Kenneth French data library files and extra ETF histories for strategy research.
Runs in GitHub Actions. Writes research/factors/*.csv (raw French CSVs unzipped) and research/history/<SYM>.csv."""
import io, json, os, time, urllib.parse, urllib.request, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOUT = os.path.join(ROOT, "research", "factors"); os.makedirs(FOUT, exist_ok=True)
HOUT = os.path.join(ROOT, "research", "history"); os.makedirs(HOUT, exist_ok=True)
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = ["F-F_Research_Data_Factors_CSV.zip", "F-F_Research_Data_5_Factors_2x3_CSV.zip", "F-F_Momentum_Factor_CSV.zip",
         "49_Industry_Portfolios_CSV.zip", "10_Industry_Portfolios_CSV.zip", "F-F_ST_Reversal_Factor_CSV.zip", "F-F_LT_Reversal_Factor_CSV.zip"]
ETFS = ["EFA", "EEM", "TLT", "IEF", "SHY", "BIL", "GLD", "DBC", "VNQ", "IWM", "IWD", "IWF", "MTUM", "QUAL", "USMV", "VLUE", "AGG"]
def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read(); return b if binary else b.decode()
        except Exception as e:
            err = e; time.sleep(3 + 3 * i)
    raise err
report = {}
for f in FILES:
    try:
        z = zipfile.ZipFile(io.BytesIO(get(BASE + f, True)))
        for n in z.namelist():
            open(os.path.join(FOUT, n.replace(".CSV", ".csv")), "wb").write(z.read(n)); report[f] = n
    except Exception as e:
        report[f] = f"error: {e}"
for s in ETFS:
    try:
        js = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?period1=0&period2=9999999999&interval=1d&events=div%2Csplit&includeAdjustedClose=true"))
        r = js["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]; adj = r["indicators"]["adjclose"][0]["adjclose"]
        n = 0
        with open(os.path.join(HOUT, f"{s}.csv"), "w") as fh:
            fh.write("date,open,high,low,close,adjclose,volume\n")
            for t, o, h, l, c, a, v in zip(ts, q["open"], q["high"], q["low"], q["close"], adj, q["volume"]):
                if c is None or a is None: continue
                fh.write(f"{time.strftime('%Y-%m-%d', time.gmtime(t))},{o},{h},{l},{c},{a},{v}\n"); n += 1
        report[s] = n
    except Exception as e:
        report[s] = f"error: {e}"
    time.sleep(0.5)
json.dump(report, open(os.path.join(FOUT, "_report.json"), "w"), indent=1); print(json.dumps(report, indent=1))
