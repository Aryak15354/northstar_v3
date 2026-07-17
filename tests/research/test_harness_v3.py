"""D-06 acceptance tests for harness_v3 (Master Plan v3.0 Part I)."""

import math

import numpy as np
import pandas as pd
import pytest

from scripts.kaggle.plan_2026_05_18_production.harness_v3 import (
    LOCKBOX_START,
    LeakTripwire,
    LockboxViolation,
    assert_lockbox,
    benjamini_hochberg,
    block_bootstrap_ci,
    cpcv_splits,
    dedupe_clusters,
    deflated_sharpe_ratio,
    derive_forward_targets,
    derive_target_flavors,
    enforce_lockbox,
    hac_tstat,
    ic_summary,
    per_date_spearman_ic,
    probability_of_backtest_overfitting,
    walk_forward_splits,
)


# --- lockbox -----------------------------------------------------------------

def test_lockbox_refuses_config_without_lockbox():
    with pytest.raises(LockboxViolation):
        assert_lockbox({})


def test_lockbox_filters_and_raises_on_survival():
    cfg = {"lockbox_start": str(LOCKBOX_START.date())}
    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-05", "2025-08-01"]), "x": [1, 2]})
    out = enforce_lockbox(df, cfg)
    assert len(out) == 1 and out["date"].max() < LOCKBOX_START
    # FINAL-02 unlock keeps rows
    out2 = enforce_lockbox(df, {**cfg, "final_02_unlock": True})
    assert len(out2) == 2


# --- per-date spearman -------------------------------------------------------

def test_ic_nan_below_min_pairs_never_zero():
    dates = pd.Series(pd.to_datetime(["2024-01-05"] * 10 + ["2024-01-12"] * 40))
    sig = pd.Series(np.random.default_rng(0).normal(size=50))
    tgt = pd.Series(np.random.default_rng(1).normal(size=50))
    ic = per_date_spearman_ic(sig, tgt, dates, min_pairs=30)
    assert pd.isna(ic.iloc[0])          # 10 pairs < 30 -> NaN, not 0
    assert np.isfinite(ic.iloc[1])


def test_ic_perfect_monotone_is_one():
    dates = pd.Series(pd.to_datetime(["2024-01-05"] * 40))
    sig = pd.Series(np.arange(40, dtype=float))
    ic = per_date_spearman_ic(sig, sig * 2 + 1, dates)
    assert ic.iloc[0] == pytest.approx(1.0, abs=1e-9)


def test_ic_date_constant_series_raises():
    dates = pd.Series(pd.to_datetime(["2024-01-05"] * 40 + ["2024-01-12"] * 40))
    sig = pd.Series([5.0] * 40 + [7.0] * 40)  # constant per date = macro series
    tgt = pd.Series(np.random.default_rng(2).normal(size=80))
    with pytest.raises(ValueError):
        per_date_spearman_ic(sig, tgt, dates)


def test_tripwire_halts_on_too_good_ic():
    ics = pd.Series(0.5, index=pd.date_range("2020-01-03", periods=60, freq="W-FRI"))
    with pytest.raises(LeakTripwire):
        ic_summary(ics, h_weeks=4)


# --- HAC t-stat (vs statsmodels reference) -----------------------------------

def test_hac_tstat_matches_statsmodels():
    rng = np.random.default_rng(7)
    x = rng.normal(0.02, 0.05, size=200)
    lag = 3
    try:
        import statsmodels.api as sm
        ols = sm.OLS(x, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
        ref_t = float(ols.tvalues[0])
    except ImportError:
        pytest.skip("statsmodels not installed")
    ours = hac_tstat(x, lag=lag)
    assert ours == pytest.approx(ref_t, rel=0.02)


# --- block bootstrap coverage on synthetic AR(1) ------------------------------

def test_block_bootstrap_covers_ar1_mean():
    rng = np.random.default_rng(11)
    hits = 0
    trials = 30
    for t in range(trials):
        e = rng.normal(size=300)
        x = np.zeros(300)
        for i in range(1, 300):
            x[i] = 0.5 * x[i - 1] + e[i]
        x = x + 0.0  # true mean 0
        lo, hi = block_bootstrap_ci(x, block_len=26, n_boot=400, seed=t)
        if lo <= 0.0 <= hi:
            hits += 1
    assert hits / trials >= 0.80  # ~95% nominal; loose gate for 400 resamples


# --- splitters ----------------------------------------------------------------

def _weekly_dates(n=200, start="2019-01-04"):
    return list(pd.date_range(start, periods=n, freq="W-FRI"))


def test_walk_forward_no_overlap_and_purge():
    ds = _weekly_dates(220)
    splits = walk_forward_splits(ds, first_train_end="2022-01-07", test_weeks=26,
                                 step_weeks=26, purge_weeks=4)
    assert len(splits) >= 2
    for s in splits:
        assert max(s.train_dates) < min(s.test_dates)
        gap_weeks = (min(s.test_dates) - max(s.train_dates)).days / 7
        assert gap_weeks >= 4 + 1 - 1e-9  # purge respected


def test_cpcv_no_leakage_and_combo_count():
    ds = _weekly_dates(160)
    splits = cpcv_splits(ds, n_groups=8, n_test_groups=2, max_combos=16,
                         purge_weeks=4, embargo_weeks=4)
    assert 1 <= len(splits) <= 16
    for s in splits:
        train = set(s.train_dates)
        test = set(s.test_dates)
        assert not (train & test)
        # purge: no train date within 4 weeks before or after a test date
        for td in test:
            for k in range(-4, 5):
                assert (td + pd.Timedelta(weeks=k)) not in train or k == 0 and False


# --- PBO ----------------------------------------------------------------------

def test_pbo_high_for_pure_noise_low_for_dominant_config():
    rng = np.random.default_rng(3)
    noise = pd.DataFrame(rng.normal(0, 0.02, size=(32, 10)))
    pbo_noise = probability_of_backtest_overfitting(noise, n_partitions=16)
    dominant = noise.copy()
    dominant[0] = dominant[0] + 0.05  # config 0 genuinely better everywhere
    pbo_dom = probability_of_backtest_overfitting(dominant, n_partitions=16)
    assert pbo_noise > 0.3
    assert pbo_dom < 0.15


# --- DSR ----------------------------------------------------------------------

def test_dsr_orders_real_vs_noise():
    rng = np.random.default_rng(5)
    real = rng.normal(0.006, 0.02, size=260)     # strong genuine edge (SR~2.2 ann)
    junk = rng.normal(0.0, 0.02, size=260)
    dsr_real = deflated_sharpe_ratio(real, n_trials=50)
    dsr_junk = deflated_sharpe_ratio(junk, n_trials=50)
    assert dsr_real > 0.9
    assert dsr_junk < 0.5
    assert dsr_junk < dsr_real


# --- FDR + dedupe ---------------------------------------------------------------

def test_bh_fdr_reference_vector():
    # Benjamini & Hochberg (1995) worked example: 15 p-values, q=0.05 -> 4 rejections
    p = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
         0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.000]
    passed = benjamini_hochberg(p, q=0.05)
    assert passed[:4] == [True, True, True, True]
    assert sum(passed) == 4


def test_dedupe_correlated_trio_one_representative():
    rng = np.random.default_rng(9)
    base = rng.normal(size=300)
    df = pd.DataFrame({
        "a": base,
        "b": base + rng.normal(0, 0.01, 300),   # near-duplicate of a
        "c": base * -1 + rng.normal(0, 0.01, 300),  # |rho|>0.9 negative — same cluster
        "d": rng.normal(size=300),               # independent
    })
    cov = pd.Series({"a": 0.9, "b": 0.99, "c": 0.5, "d": 0.8})
    rep = dedupe_clusters(df, threshold=0.90, coverage=cov)
    assert rep["a"] == rep["b"] == rep["c"] == "b"  # highest coverage wins
    assert rep["d"] == "d"


# --- targets --------------------------------------------------------------------

def test_forward_targets_log_return_and_nan_tail():
    dates = pd.date_range("2024-01-05", periods=6, freq="W-FRI")
    df = pd.DataFrame({
        "date": list(dates) * 1,
        "ticker": ["A.NS"] * 6,
        "close": [100, 110, 121, 133.1, 146.41, 161.051],
    })
    out = derive_forward_targets(df, horizons_w=(1, 4))
    t1 = out["target_1w"].iloc[0]
    assert t1 == pytest.approx(math.log(110 / 100))
    assert pd.isna(out["target_1w"].iloc[-1])       # no future close -> NaN
    assert pd.isna(out["target_4w"].iloc[3])


def test_target_flavors_per_date_winsor_and_sector():
    dates = pd.to_datetime(["2024-01-05"] * 40)
    rng = np.random.default_rng(13)
    df = pd.DataFrame({
        "date": dates,
        "ticker": [f"T{i}.NS" for i in range(40)],
        "sector": ["FIN"] * 20 + ["IT"] * 20,
        "target_4w": rng.normal(0, 0.02, 40),
    })
    df.loc[0, "target_4w"] = 5.0  # absurd outlier
    out = derive_target_flavors(df, horizon_w=4)
    assert abs(out["tgt_z_4w"].iloc[0]) <= 3.0 + 1e-9   # winsorized per date
    sec_mean = out.groupby("sector")["tgt_sec_4w"].mean()
    assert abs(sec_mean.loc["IT"]) < 1e-9               # sector-demeaned


# --- panel_math group helpers: MultiIndex composite keys (regression) ---
# 2026-07-17: feature_factory._add_structural_alpha_features passes a
# MultiIndex(date, sector); pd.Series(MultiIndex) raises NotImplementedError on
# pandas 2.x, so every *_sector_z column died at build time. The playbook wrote
# that call but nothing ever executed it -- only a Kaggle smoke run caught it.

def test_group_zscore_accepts_multiindex_and_groups_by_tuple():
    import pandas as pd
    import numpy as np
    from src.core.panel_math import group_zscore

    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"] * 4 + ["2024-01-02"] * 4),
        "sector": ["IT", "IT", "BANK", "BANK"] * 2,
        "roe": [10.0, 20.0, 5.0, 15.0, 1.0, 3.0, 100.0, 100.0],
    })
    mi = pd.MultiIndex.from_arrays([df["date"], df["sector"]])
    z = group_zscore(df["roe"], mi)

    expected = (10 - 15) / np.std([10, 20], ddof=1)
    assert abs(z.iloc[0] - expected) < 1e-9      # within date x sector, not sector
    assert abs(z.iloc[1] + expected) < 1e-9
    assert z.iloc[6] == 0.0 and z.iloc[7] == 0.0  # degenerate group -> 0.0

    missing = df.copy()
    missing.loc[0, "roe"] = np.nan
    z2 = group_zscore(missing["roe"], pd.MultiIndex.from_arrays([missing["date"], missing["sector"]]))
    assert pd.isna(z2.iloc[0])                    # missing stays NaN, never 0


def test_group_rank_centered_accepts_multiindex():
    import pandas as pd
    from src.core.panel_math import group_rank_centered

    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"] * 4 + ["2024-01-02"] * 4),
        "sector": ["IT", "IT", "BANK", "BANK"] * 2,
        "roe": [10.0, 20.0, 5.0, 15.0, 1.0, 3.0, 100.0, 100.0],
    })
    mi = pd.MultiIndex.from_arrays([df["date"], df["sector"]])
    r = group_rank_centered(df["roe"], mi)
    # grouped by sector alone, roe=10 would rank 3/4 -> 0.25; 0.0 proves date x sector
    assert abs(r.iloc[0] - 0.0) < 1e-9
    assert abs(r.iloc[1] - 0.5) < 1e-9


def test_group_helpers_series_and_arraylike_unchanged():
    import pandas as pd
    from src.core.panel_math import group_zscore, group_rank_centered

    df = pd.DataFrame({"sector": ["IT", "IT", "BANK", "BANK"], "roe": [10.0, 20.0, 5.0, 15.0]})
    assert group_zscore(df["roe"], df["sector"]).equals(group_zscore(df["roe"], df["sector"].values))
    assert group_rank_centered(df["roe"], df["sector"]).equals(
        group_rank_centered(df["roe"], df["sector"].values)
    )


# --- PIT lag registry completeness (regression) ---
# 2026-07-17: feature_pit_enforce=True (playbook E.3) made an unmatched feature a
# HARD build failure. recent_downgrade_flag / watch_negative_flag are the ratings
# family but don't start with "rating_", so they matched no pattern and killed the
# build 8 minutes in -- one name revealed per run. Both catalogs must stay in sync.

def _pit_match(base, rules):
    import re
    for rule in rules:
        pattern = str(rule["pattern"])
        if pattern.startswith("re:"):
            if re.match(pattern[3:], base):
                return rule["lag"]
        elif pattern == base or base.startswith(pattern):
            return rule["lag"]
    return None


def test_rating_family_flags_have_pit_lags_in_both_catalogs():
    from src.research.feature_pit_rules import default_feature_pit_lags
    from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import (
        _weekly_feature_pit_lag_rules,
    )

    flags = [
        "recent_downgrade_flag",
        "recent_upgrade_flag",
        "watch_negative_flag",
        "investment_grade_flag",
    ]
    for rules in (default_feature_pit_lags(), _weekly_feature_pit_lag_rules()):
        for flag in flags:
            assert _pit_match(flag, rules) == "bulk", f"{flag} has no PIT lag rule"
        assert _pit_match("rating_numeric", rules) == "bulk"   # no regression


def test_alternative_feature_builder_groups_all_have_pit_lags():
    """Every feature AlternativeFeatureBuilder emits must resolve to a PIT lag.

    Catches the whole family at once instead of one name per 8-minute build.
    """
    from src.research.feature_pit_rules import default_feature_pit_lags
    from src.signals.feature_builder import AlternativeFeatureBuilder

    rules = default_feature_pit_lags()
    unmatched = [
        name
        for names in AlternativeFeatureBuilder.FEATURE_GROUPS.values()
        for name in names
        if _pit_match(str(name), rules) is None
    ]
    assert not unmatched, f"features with no PIT lag rule: {unmatched}"
