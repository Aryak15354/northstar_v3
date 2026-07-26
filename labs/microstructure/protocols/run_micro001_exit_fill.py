#!/usr/bin/env python3
"""MICRO-001 -- Realistic exit-fill model for names breaching the universe threshold.

Executes labs/microstructure/protocols/MICRO-001_EXIT_FILL_MODEL.md. Replaces G8-12's crude bound
(0 to -2.29%/yr "depending on whether exits fill cleanly") with a modeled point estimate, using the
real historical daily price/volume path in the run-up window and the same cost model every other lab
uses (src/pnl/indian_cost_model.IndianEquityCostModel).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.pnl.indian_cost_model import IndianEquityCostModel  # noqa: E402
from research_os.experiment_registry import close_experiment  # noqa: E402

CM = IndianEquityCostModel()
OUT = ROOT / "labs/microstructure/results/MICRO-001"
OUT.mkdir(parents=True, exist_ok=True)

MIN_PRICE = 20.0
PARTICIPATION_CAP = 0.05          # Sleeve-1's own documented execution rule, inherited not tuned
MAX_UNWIND_DAYS = 20
UNIVERSE_ADV_FLOOR_CR = 1.0       # panel universe rule: 13-week median traded value >= Rs1cr
DAY20_LIQUIDITY_DISCOUNT = 0.20   # stated explicitly (contract section 4): remainder marked down 20%
                                  # if still unliquidated at day 20 -- a disclosed assumption, not a
                                  # silently-vanishing position
N_BOOTSTRAP = 2000
SEED = 42


def breach_events() -> pd.DataFrame:
    """Every ticker with a documented gap between its last panel-qualifying date and its last usable
    (non-quarantined) date in the merged delisted-price source -- the population G8-12 identified.
    """
    m = pd.read_parquet(ROOT / "data/processed/delisted_prices_merged.parquet",
                        columns=["date", "ticker", "close", "adj_close", "volume",
                                "quarantine_discontinuity"])
    m["date"] = pd.to_datetime(m["date"]).dt.normalize()
    m = m[~m["quarantine_discontinuity"].astype(bool)].copy()
    m["px"] = pd.to_numeric(m["adj_close"], errors="coerce").fillna(
        pd.to_numeric(m["close"], errors="coerce"))
    m = m.dropna(subset=["px"])
    m = m[m["px"] > 0]

    panel = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                            columns=["date", "ticker", "close", "adv_13w", "is_delisted"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel[pd.to_numeric(panel["close"], errors="coerce") >= MIN_PRICE]
    pdel = panel[panel["is_delisted"].astype(bool)]

    last_panel = pdel.groupby("ticker")["date"].max().rename("panel_last")
    last_panel_adv = pdel.sort_values("date").groupby("ticker")["adv_13w"].last().rename("adv_at_breach")
    last_src = m.groupby("ticker")["date"].max().rename("src_last")
    j = pd.concat([last_panel, last_panel_adv, last_src], axis=1).dropna()
    return j.reset_index().rename(columns={"index": "ticker"}), m


def simulate_unwind(daily: pd.DataFrame, breach_date: pd.Timestamp, position_inr: float) -> dict:
    """Unwind `position_inr` starting the trading day AFTER breach, at a 5%-of-volume daily cap.

    Returns realistic weighted-average execution price info and comparison to the clean-fill price
    (the breach-day close itself, zero slippage -- what the panel-based backtest implicitly assumes).
    """
    tail = daily[daily["date"] > breach_date].sort_values("date").head(MAX_UNWIND_DAYS)
    breach_row = daily[daily["date"] <= breach_date].sort_values("date")
    if breach_row.empty or tail.empty:
        return None
    clean_fill_px = float(breach_row["px"].iloc[-1])

    remaining_inr = position_inr
    proceeds = 0.0
    shares_sold_value = 0.0
    days_used = 0
    for _, row in tail.iterrows():
        if remaining_inr <= 0:
            break
        day_traded_value = float(row["px"]) * float(row["volume"])
        if day_traded_value <= 0:
            continue
        sellable_today = min(remaining_inr, PARTICIPATION_CAP * day_traded_value)
        if sellable_today <= 0:
            continue
        adv_for_slippage = day_traded_value            # single-day traded value as the ADV proxy here
        slip_bps = CM.slippage_bps_for(sellable_today, adv_for_slippage)
        exec_px_factor = 1.0 - slip_bps / 1e4           # a sell loses value to slippage
        proceeds += sellable_today * exec_px_factor
        remaining_inr -= sellable_today
        days_used += 1

    unliquidated = remaining_inr
    if unliquidated > 0:
        proceeds += unliquidated * (1.0 - DAY20_LIQUIDITY_DISCOUNT)

    realized_fraction = proceeds / position_inr if position_inr > 0 else np.nan
    clean_fraction = 1.0   # by definition, clean fill realizes 100% of the breach-day mark
    drag = realized_fraction - clean_fraction            # negative => realistic unwind is worse
    return dict(clean_fill_px=clean_fill_px, days_used=days_used,
               unliquidated_frac=unliquidated / position_inr if position_inr > 0 else np.nan,
               realized_fraction=realized_fraction, drag=drag)


def main() -> int:
    print("=" * 100)
    print("MICRO-001 -- REALISTIC EXIT-FILL MODEL")
    print("=" * 100)

    events, m = breach_events()
    print(f"breach-event population: {len(events)} tickers (all non-quarantined, all with a "
          f"post-breach daily tail)\n")

    rows = []
    for _, ev in events.iterrows():
        tk = ev["ticker"]
        daily = m[m.ticker == tk]
        # position sized as if this were one name in an N-name book at the ADV level observed at
        # breach -- position_inr scaled to the SAME participation logic used throughout Gen-8
        # (a name's notional is set relative to its OWN adv at breach, not an arbitrary constant)
        # NOTE (self-caught, disclosed in FINDINGS.md): adv_13w is ALREADY in raw INR (verified:
        # panel-wide min is 1.00e7 = exactly the Rs1cr universe floor) -- the first version of this
        # script multiplied by a further 1e7 as if adv_13w were denominated in crore, inflating every
        # position ~10,000,000x and making the 5%-of-daily-volume cap unable to sell anything
        # meaningful in 20 days for ANY ticker. That produced a suspicious flat -20.0000% drag with
        # ZERO bootstrap variance across all 89 events -- caught by that exact symptom before trusting
        # the VALIDATED verdict it produced, not after.
        adv_inr = float(ev["adv_at_breach"]) if pd.notna(ev["adv_at_breach"]) else np.nan
        if not np.isfinite(adv_inr) or adv_inr <= 0:
            continue
        # a position sized at 10% of the name's own last-qualifying-ADV -- i.e. a position that was
        # legitimately built while the name still cleared the Rs1cr ADV universe floor
        position_inr = 0.10 * adv_inr
        r = simulate_unwind(daily, ev["panel_last"], position_inr)
        if r is None:
            continue
        r["ticker"] = tk
        rows.append(r)

    res = pd.DataFrame(rows)
    print(f"simulated unwinds: {len(res)} of {len(events)} breach events "
          f"({len(events) - len(res)} excluded: no post-breach tail or zero ADV)\n")

    print("--- headline result ---")
    print(f"mean drag   : {res['drag'].mean():+.4%}")
    print(f"median drag : {res['drag'].median():+.4%}")
    print(f"mean days to unwind (of a max {MAX_UNWIND_DAYS}): {res['days_used'].mean():.1f}")
    print(f"mean unliquidated fraction at day {MAX_UNWIND_DAYS}: {res['unliquidated_frac'].mean():.1%}")

    rng = np.random.default_rng(SEED)
    boot_means = np.array([res["drag"].sample(len(res), replace=True, random_state=int(s)).mean()
                          for s in rng.integers(0, 1_000_000, N_BOOTSTRAP)])
    ci_lo, ci_hi = np.percentile(boot_means, [2.5, 97.5])
    print(f"\nbootstrap 95% CI on mean drag ({N_BOOTSTRAP} draws): [{ci_lo:+.4%}, {ci_hi:+.4%}]")

    # ---- annualize: a breach event is a one-time cost realized once per affected position ----
    # G8-12's own per-tier exposure: share of rows drawn from later-truncated names
    tier_exposure = dict(ALL=0.045, FNO_LARGE=0.055, NON_FNO_TAIL=0.025, SMALL_ADV_Q1=0.080)
    mean_drag = float(res["drag"].mean())
    print("\n--- annualized differential drag per tier (mean drag x G8-12's tier exposure share) ---")
    annualized = {}
    for tier, exposure in tier_exposure.items():
        # a position is held ~1 year on average before a breach event might occur (conservative;
        # matches the book's own annual turnover order of magnitude) -- so exposure share directly
        # scales to an annualized drag without a separate holding-period assumption
        drag_pct_yr = mean_drag * exposure * 100
        annualized[tier] = drag_pct_yr
        print(f"  {tier:14s} exposure {exposure:.1%}  ->  modeled drag {drag_pct_yr:+.3f}%/yr")

    differential = annualized["SMALL_ADV_Q1"] - annualized["ALL"]
    print(f"\n  SMALL_ADV_Q1 - ALL differential: {differential:+.3f}%/yr")
    print(f"  G8-12's crude bound was:          0 to -2.29%/yr")

    # ---- gates ----
    direction_supported = mean_drag < 0
    material = abs(differential) > 0.5
    concentration_supported = abs(differential) >= 0 and annualized["SMALL_ADV_Q1"] < annualized["ALL"]
    ci_excludes_zero = ci_hi < 0 or ci_lo > 0

    print("\n--- gates ---")
    print(f"  direction (H-MICRO-001-1, drag < 0)         : {'PASS' if direction_supported else 'FAIL'}")
    print(f"  materiality (|differential| > 0.5%/yr)      : {'PASS' if material else 'FAIL'}")
    print(f"  tier concentration (H-MICRO-001-2)          : {'PASS' if concentration_supported else 'FAIL'}")
    print(f"  bootstrap CI excludes zero                  : {ci_excludes_zero}")

    if not direction_supported:
        verdict = "METHODOLOGICAL_FAILURE"
        outcome = ("Realistic unwind came out BETTER than the clean-fill assumption -- investigate "
                   "before trusting.")
    elif not ci_excludes_zero:
        verdict = "INCONCLUSIVE"
        outcome = (f"Direction is correct (mean drag {mean_drag:+.3%}) but the bootstrap CI "
                   f"[{ci_lo:+.3%}, {ci_hi:+.3%}] includes zero -- n={len(res)} breach events is not "
                   f"enough to distinguish the drag from noise at this resolution.")
    elif material:
        verdict = "VALIDATED"
        outcome = ("The crude 0-to--2.29%/yr bound is replaced with a modeled point estimate: mean "
                   f"per-position drag {mean_drag:+.3%} (95% CI [{ci_lo:+.3%}, {ci_hi:+.3%}]), "
                   f"translating to a SMALL_ADV_Q1-vs-ALL differential of {differential:+.3f}%/yr.")
    else:
        # direction is real and statistically distinguishable from zero (CI excludes zero), but the
        # pre-registered materiality bar (section 7: >0.5%/yr differential) is not cleared -- this is
        # a tested, powered, REJECTED materiality hypothesis, not an "inconclusive" one. Conflating
        # "real but small" with "we couldn't tell" is exactly the distinction verdict_schema.py exists
        # to prevent.
        verdict = "REJECTED"
        outcome = (f"The exit-fill drag is real (mean {mean_drag:+.3%}, 95% CI "
                   f"[{ci_lo:+.3%}, {ci_hi:+.3%}], excludes zero) but the annualized "
                   f"SMALL_ADV_Q1-vs-ALL differential ({differential:+.3f}%/yr) is far below the "
                   f"pre-registered 0.5%/yr materiality bar. The hypothesis that exit-fill realism is "
                   f"a MATERIAL driver of the G8-07/G8-11 tier effect is REJECTED -- this mechanism, "
                   f"while genuine, does not explain a meaningful share of the lead. G8-12's crude "
                   f"bound (0 to -2.29%/yr) is superseded by this far smaller modeled figure.")

    payload = dict(
        experiment="MICRO-001", n_breach_events=len(events), n_simulated=len(res),
        mean_drag=mean_drag, median_drag=float(res["drag"].median()),
        bootstrap_ci95=[float(ci_lo), float(ci_hi)],
        mean_days_to_unwind=float(res["days_used"].mean()),
        mean_unliquidated_frac_at_day20=float(res["unliquidated_frac"].mean()),
        tier_exposure_source="results/gen8/G8-12/g8_12_data.json (rows_from_truncated_names)",
        annualized_drag_by_tier=annualized,
        differential_small_vs_all=float(differential),
        prior_crude_bound="[0, -2.29]%/yr (results/gen8/G8-12)",
        gates=dict(direction=direction_supported, material=material,
                  concentration=concentration_supported, ci_excludes_zero=bool(ci_excludes_zero)),
        verdict=verdict, outcome=outcome,
    )
    (OUT / "micro001_data.json").write_text(json.dumps(payload, indent=2, default=str))
    res.to_csv(OUT / "micro001_breach_events.csv", index=False)

    print("\n" + "=" * 100)
    print(f"VERDICT: {verdict}")
    print(f"OUTCOME: {outcome}")
    print("=" * 100)

    close_experiment("MICRO-001", verdict, "labs/microstructure/results/MICRO-001/FINDINGS.md")
    print(f"\nwrote {OUT / 'micro001_data.json'}; MICRO-001 closed in the master registry as {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
