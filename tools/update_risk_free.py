"""Reset the 10-year Treasury (risk-free) rate in every holdings workbook and refresh the Positions page.

Usage:
    python tools/update_risk_free.py 0.0495 2026-11-04 [--force] [--dry-run]

What it does, for each workbook in models/holdings/ that has a WACC tab:
  1. Sets the risk-free input (WACC!B7) to the new rate and dates the note.
  2. Moves every assumed discount rate (assumed WACC, row 26; banks' assumed cost of equity,
     row 38) by the same amount, so each stock keeps its premium over Treasuries.
  3. Recalculates the workbook with LibreOffice (the xlsx skill's recalc.py).
Then it rereads the recalculated values and updates content/positions.json:
  target (base value), trimAbove (bull value), exitBelow (halfway, bear to base), requiredReturn,
  using the same rounding as the published levels. TMC uses its own risk rate and is skipped.

Changes smaller than 0.10 percentage points are ignored unless --force is given, to avoid
moving public levels for noise. Prints old and new values for every holding.
"""
import glob
import json
import os
import subprocess
import sys

from openpyxl import load_workbook

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECALC = "/mnt/skills/public/xlsx/scripts/recalc.py"
THRESHOLD = 0.0010


def rnd(v):
    if v < 10:
        return round(v * 4) / 4
    if v < 100:
        return round(v)
    return round(v / 5) * 5


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force, dry = "--force" in sys.argv, "--dry-run" in sys.argv
    if len(args) != 2:
        sys.exit(__doc__)
    rf_new, date = float(args[0]), args[1]
    if not 0.0 < rf_new < 0.15:
        sys.exit("Risk-free rate looks wrong; pass it as a decimal, e.g. 0.0495")
    books = sorted(glob.glob(os.path.join(ROOT, "models", "holdings", "*_Valuation.xlsx")))
    first = load_workbook(books[0])
    rf_old = first["WACC"]["B7"].value
    delta = rf_new - rf_old
    print(f"Risk-free in models: {rf_old:.4%}  new: {rf_new:.4%}  change: {delta * 100:+.2f} pp")
    if abs(delta) < THRESHOLD and not force:
        print(f"Change below {THRESHOLD:.2%}; nothing updated.")
        return
    if dry:
        print("Dry run; nothing written.")
        return
    if not os.path.exists(RECALC):
        sys.exit(f"Recalc script not found at {RECALC}; cannot recalculate workbooks.")
    for path in books:
        wb = load_workbook(path)
        if "WACC" not in wb.sheetnames:
            continue
        w = wb["WACC"]
        w["B7"] = rf_new
        w["C7"] = f"10-year Treasury yield at the close on {date}; assumed rates below move with it"
        for row in (26, 38):
            for col in range(2, 8):
                c = w.cell(row, col)
                if isinstance(c.value, (int, float)) and w.cell(row, 1).value and "ssumed" in str(w.cell(row, 1).value):
                    c.value = round(c.value + delta, 6)
        s = wb["Summary"]
        for row in s.iter_rows():
            for c in row:
                if isinstance(c.value, str) and "5.31% risk-free" in c.value:
                    c.value = c.value.replace("5.31% risk-free", f"{rf_new:.2%} risk-free")
        wb.save(path)
        out = subprocess.run([sys.executable, RECALC, path, "90"], capture_output=True, text=True)
        res = json.loads(out.stdout[out.stdout.index("{"):])
        if res.get("total_errors"):
            sys.exit(f"Recalc errors in {os.path.basename(path)}: {res.get('error_summary')}")
    pos_path = os.path.join(ROOT, "content", "positions.json")
    book = json.load(open(pos_path))
    print(f"{'Ticker':6s} {'rate':>13s} {'base':>15s} {'trim':>13s} {'exit':>13s}")
    for p in book["positions"]:
        t = p["ticker"]
        f = os.path.join(ROOT, "models", "holdings", f"{t}_Valuation.xlsx")
        if t == "TMC" or not os.path.exists(f):
            continue
        wb = load_workbook(f, data_only=True)
        s = wb["Summary"]
        bear, base, bull = (s.cell(5, c).value for c in (5, 6, 7))
        rate = wb[t]["B8" if t in ("JPM", "BAC") else "B10"].value
        new = dict(target=rnd(base), trimAbove=rnd(bull), exitBelow=rnd((bear + base) / 2), requiredReturn=round(rate, 4))
        print(f"{t:6s} {p.get('requiredReturn', 0):.2%}->{rate:.2%} {p.get('target')}->{new['target']:<8} "
              f"{p.get('trimAbove')}->{new['trimAbove']:<6} {p.get('exitBelow')}->{new['exitBelow']}")
        p.update(new)
    book["riskFree"] = {"rate": rf_new, "date": date}
    json.dump(book, open(pos_path, "w"), indent=2, ensure_ascii=False)
    print("Updated content/positions.json. Rebuild with python scripts/build.py and commit.")


if __name__ == "__main__":
    main()
