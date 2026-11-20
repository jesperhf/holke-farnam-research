# Strategy research (November 2026)

Not part of the site. Data: `research/history` (daily ETF prices from Yahoo) and `research/factors` (Kenneth French Data Library).
Scripts expect the CSVs next to them; copy `research/history/*.csv` and `research/factors/*.csv` into one folder with the scripts to rerun.

- `backtest.py`, `robust.py`: industry momentum on 25 sector and industry ETFs, 2005 to 2026
- `ema_test.py`, `ema_abs.py`: 50-day EMA pullback test
- `current.py`: industry labels and EMA distances as of Nov 18, 2026
- `worst_sector.py`: buying the prior year's worst S&P sector each January, 2000 to 2026
- `strategies.py`, `overlap.py`: factor premia before and after publication, trend following since 1927, 49-industry momentum since 1927, multi-asset ETF strategies, volatility targeting, factor ETFs. Output in `strategy_results.txt`.
