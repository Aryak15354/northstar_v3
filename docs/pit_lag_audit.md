# PIT Lag Audit

Date: 2026-03-09  
Scope: data sources feeding `RegimeEngine` and `FeatureFactory` in Northstar v3.

## Summary

- Two PIT hardening fixes were applied:
1. Daily macro lag in regime-label build changed from `+0` to `+1 day`.
2. Sentiment fallback in feature merge (when `availability_date` is missing) changed from same-day to `date + 1 business day`.
- No other too-short lags were found.
- Conservative lags (slightly long) are intentionally retained.

## Audit Table

| Data source | Actual publication lag (best-known) | Implemented lag | Code location | Status |
|---|---|---|---|---|
| RBI-style daily macro series (`core_macro_*` daily) | Usually same-day or next-day publication for daily market series; conservative PIT should avoid same-day trading use | `+1 day` | `scripts/build_regime_labels.py` (`_sheet_to_lagged_daily`, `_read_csv_macro_file`) | Fixed (was `+0`) |
| RBI-style monthly macro series | Typically multi-day to multi-week lag from month-end | `+30 days` | `scripts/build_regime_labels.py` | OK (conservative) |
| RBI-style quarterly macro series | Typically multi-week lag from quarter-end | `+45 days` | `scripts/build_regime_labels.py` | OK (conservative) |
| CEA daily power | Generally published next day (sometimes 1-2 days) | `+1 day` | `scripts/scrape_cea_power.py`, `src/signals/macro/cea_power.py`, `src/signals/macro/macro_regime.py` | OK |
| GST e-way bill monthly | Usually released in following month; conservative lag preferred | `month_end + 30 days` | `scripts/scrape_gst_ewaybill.py`, `src/signals/macro/gst_ewaybill.py`, `src/signals/macro/macro_regime.py` | OK (conservative) |
| BSE bulk deals | Disclosed after market close on trade date | `+1 business day` | `src/signals/bulk_deals.py` | OK |
| Screener annual fundamentals | Company filing schedules vary; conservative lag preferred | `fiscal_year_end + 60 days` | `scripts/load_screener_to_pipeline.py`, `src/research/feature_factory.py` fallback path | OK (conservative) |
| Screener quarterly fundamentals/shareholding | Quarterly filing cadence; conservative lag | `quarter_end + 45 days` | `scripts/load_screener_to_pipeline.py` | OK (conservative) |
| Promoter pledge | Quarterly filing cadence | `quarter_end + 45 days` | `src/signals/promoter_pledge.py` | OK |
| Credit ratings | Rating action date public on/near action date | `+1 business day` | `src/signals/credit_ratings.py` | OK |
| Earnings announcements | Results announcement date should be tradable next session | `announcement_date + 1 business day`; fallback `fiscal_year_end + 60 days` | `src/signals/earnings_dates.py` | OK |
| Corporate announcements (order/capex/insider etc.) | Exchange disclosure, usable next session | `+1 business day` | `src/signals/order_announcements.py` | OK |
| Sentiment (ticker + market) | News/event on D should affect trading from D+1 | `+1 business day` | `src/signals/sentiment_bridge.py`; fallback handling in `src/research/feature_factory.py` | Fixed fallback |

## Notes

- `RegimeEngine` uses `availability_date` when present (`src/research/regime_engine.py`), which is PIT-safe for macro/sentiment/power/gst feeds.
- Local `data/macro/raw/core_macro_*.csv` files were sampled; they contain measurement period/date columns but no explicit publication timestamp columns. Flat frequency-based lags are the safest available approach without source-level release timestamps.
- `FeatureFactory` macro merge path expects `availability_date` in `macro_regime_features.parquet`. If missing, upstream loaders should be corrected rather than shortening lags.

## External references checked

- RBI release calendar / data release pages: [rbi.org.in](https://www.rbi.org.in/Scripts/releaseCalender.aspx), [dbie.rbi.org.in](https://dbie.rbi.org.in/DBIE/dbie.rbi?site=statistics)
- CEA daily report portal: [cea.nic.in/daily-report](https://cea.nic.in/daily-report/?lang=en)
- GST e-way bill statistics portal: [ewaybillgst.gov.in](https://ewaybillgst.gov.in/Others/EWBMonthStats.aspx)
- BSE bulk deal archive landing page: [bseindia.com Bulk Deal Archive](https://www.bseindia.com/markets/equity/EQReports/BulkDealArchieve.aspx)
