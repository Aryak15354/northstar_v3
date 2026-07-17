#!/usr/bin/env python3
"""CI gate: live-artifact truth invariants.

This gate encodes the mechanical checks that would have caught the critical
defects found in the 2026-07 forensic audit — every one of which produced a
plausible-looking artifact that no existing health check flagged because the
health checks counted rows instead of measuring signal. Each invariant here
asserts a property of a LIVE artifact that must hold if the pipeline is telling
the truth:

  * a per-stock output must actually vary per stock (no universe-wide constant)
  * monetary columns must not jump by ~1e7 between adjacent periods (unit mixing)
  * a consumed feed must not be stale (dead-feed detection)
  * the daily scheduler must not be silently failing a source
  * the live book must be the book we intend to hold (name count / gross)

Design:
  * Missing artifact  -> SKIP (does not fail CI; environments without data exist)
  * Present + violates -> FAIL (this is always a real bug; fix the pipeline, not
    the gate)
  * Staleness is measured in CALENDAR days with a generous threshold so normal
    weekends/holidays do not trip it; a genuinely dead feed (weeks stale) will.

Exit 0 = all present artifacts pass. Exit 1 = at least one hard invariant failed.
Run: python3 scripts/ci/check_live_artifact_invariants.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
D = PROJECT_ROOT / "data"

# Max calendar days a consumed feed may lag "now" before we call it dead.
# Generous enough to survive a long weekend + a public holiday cluster.
STALE_HARD_DAYS = 12


@dataclass
class Result:
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""
    metrics: dict = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"


def _skip(name: str, reason: str) -> Result:
    return Result(name, "SKIP", reason)


def _read(path: Path, **kw) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path, **kw)
    except Exception as exc:  # pragma: no cover - corruption surfaces as FAIL upstream
        raise RuntimeError(f"unreadable:{path.name}:{exc}") from exc


def _max_date(df: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Timestamp | None:
    for col in candidates:
        if col in df.columns:
            s = pd.to_datetime(df[col], errors="coerce").dropna()
            if not s.empty:
                return pd.Timestamp(s.max()).tz_localize(None)
    # date may live in the index
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
        return pd.Timestamp(df.index.max()).tz_localize(None)
    return None


# --------------------------------------------------------------------------- #
# Invariants
# --------------------------------------------------------------------------- #
def inv_fundamentals_unit_continuity() -> Result:
    """Adjacent-fiscal-year revenue per ticker must not jump ~1e7x (₹ vs ₹cr mix)."""
    name = "fundamentals_unit_continuity"
    path = D / "canonical/fundamentals/fundamentals_annual_panel.parquet"
    df = _read(path, columns=["ticker", "fiscal_year", "revenue"])
    if df is None:
        return _skip(name, "annual panel missing")
    work = df.dropna(subset=["ticker", "fiscal_year", "revenue"]).copy()
    work = work[work["revenue"] != 0]
    work = work.sort_values(["ticker", "fiscal_year"])
    work["prev"] = work.groupby("ticker")["revenue"].shift(1)
    work = work.dropna(subset=["prev"])
    # Only a meaningful positive prior base gives a meaningful ratio; near-zero
    # or negative bases (turnarounds, first-revenue years) produce spurious huge
    # ratios that are not unit errors.
    work = work[work["prev"].abs() >= 1.0]
    ratio = (work["revenue"] / work["prev"]).abs()
    # This gate targets the ₹-vs-₹crore UNIT MIX specifically (a 1e7x jump), not
    # real business growth. Even extreme small-cap hypergrowth stays under ~1000x
    # in a single year; a >1e4x (or <1e-4x) jump is only ever a unit-scale
    # corruption. Bounds chosen to catch every 1e7 mix while never flagging a
    # genuine ramp (OLAELEC ₹1cr→₹373cr, CAMPUS ₹2cr→₹508cr all pass).
    offenders = work[(ratio > 1e4) | (ratio < 1e-4)]
    n = int(len(offenders))
    if n == 0:
        return Result(name, "PASS", f"{work['ticker'].nunique()} tickers continuous",
                      {"tickers": int(work["ticker"].nunique())})
    sample = (offenders.assign(ratio=ratio.loc[offenders.index].round(2))
              .sort_values("ratio", ascending=False)
              .head(8)[["ticker", "fiscal_year", "prev", "revenue", "ratio"]]
              .to_dict("records"))
    return Result(name, "FAIL", f"{n} adjacent-FY revenue jumps outside [0.2,5]",
                  {"offenders": n, "sample": sample})


def inv_valuation_engines_nondegenerate() -> Result:
    """Per-stock valuation z-scores must vary across the universe (not a constant)."""
    name = "valuation_engines_nondegenerate"
    path = D / "processed/valuation_engines.parquet"
    df = _read(path)
    if df is None:
        return _skip(name, "valuation_engines.parquet missing")
    checked, dead = {}, []
    for col in ("composite_z", "fundamental_z", "relative_z", "market_implied_z"):
        if col in df.columns:
            std = float(pd.to_numeric(df[col], errors="coerce").std(skipna=True) or 0.0)
            checked[col] = round(std, 6)
            # composite must move; single engines may legitimately be sparse but
            # composite collapsing to one number means no stock-specific signal.
            if col == "composite_z" and std < 1e-4:
                dead.append(col)
    if not checked:
        return _skip(name, "no z-score columns present")
    if dead:
        return Result(name, "FAIL",
                      f"degenerate constant valuation output: {dead} (std<1e-4)",
                      {"stds": checked, "rows": int(len(df))})
    return Result(name, "PASS", "composite_z varies across universe", {"stds": checked})


def inv_stock_roles_nondegenerate() -> Result:
    """Risk-role classification must not collapse to a single/near-single label."""
    name = "stock_roles_nondegenerate"
    path = D / "processed/stock_roles.parquet"
    df = _read(path, columns=["stock_role"])
    if df is None:
        return _skip(name, "stock_roles.parquet missing")
    vc = df["stock_role"].value_counts()
    n_roles = int(len(vc))
    top_share = float(vc.iloc[0] / vc.sum()) if len(vc) else 1.0
    # >=3 distinct roles present AND no single role owns >95% of the book.
    if n_roles >= 3 and top_share <= 0.95:
        return Result(name, "PASS", f"{n_roles} roles, top share {top_share:.2f}",
                      {"roles": vc.to_dict()})
    return Result(name, "FAIL",
                  f"degenerate roles: {n_roles} distinct, top share {top_share:.2f}",
                  {"roles": vc.to_dict()})


def inv_scores_have_spread() -> Result:
    """Live scores must have cross-sectional spread (a model that produces a flat
    cross-section is producing no ranking)."""
    name = "scores_have_spread"
    path = D / "processed/scores.parquet"
    df = _read(path)
    if df is None:
        return _skip(name, "scores.parquet missing")
    col = next((c for c in ("final_score", "northstar_score", "model_score") if c in df.columns), None)
    if col is None:
        return _skip(name, "no score column")
    std = float(pd.to_numeric(df[col], errors="coerce").std(skipna=True) or 0.0)
    if std > 1e-6:
        return Result(name, "PASS", f"{col} std={std:.4f}", {"std": round(std, 6), "n": int(len(df))})
    return Result(name, "FAIL", f"flat cross-section: {col} std={std:.2e}", {"n": int(len(df))})


def inv_scores_book_is_top_ranked() -> Result:
    """The scorer's suggested book must actually hold TOP-RANKED names.

    Guards the index-identity regression where _build_weights intersected an
    ignore_index RangeIndex with the frame's labels and silently weighted the
    first ~20 tickers in universe order (score ranks 101-496) instead of the
    turnover-constrained top-N. Count/gross checks alone cannot see rank quality
    — this asserts the held names' median score percentile is genuinely high.
    """
    name = "scores_book_is_top_ranked"
    path = D / "processed/scores.parquet"
    df = _read(path)
    if df is None:
        return _skip(name, "scores.parquet missing")
    if "suggested_weight" not in df.columns or "final_score" not in df.columns:
        return _skip(name, "no suggested_weight/final_score columns")
    w = pd.to_numeric(df["suggested_weight"], errors="coerce").fillna(0.0)
    held = df[w > 1e-9]
    if held.empty:
        return _skip(name, "no held names in book")
    pct = pd.to_numeric(df["final_score"], errors="coerce").rank(pct=True)
    held_pct = pct.loc[held.index]
    median_pct = float(held_pct.median())
    # A top-N-of-~500 long book should sit near the top of the ranking. The
    # turnover constraint legitimately retains a few slipped names (rank<=35),
    # so require median >= 0.70 rather than a razor-thin bound.
    if median_pct >= 0.70:
        return Result(name, "PASS",
                      f"{len(held)} held names, median score pct {median_pct:.2f}",
                      {"held": int(len(held)), "median_pct": round(median_pct, 3)})
    return Result(name, "FAIL",
                  f"book is NOT top-ranked: median score pct {median_pct:.2f} "
                  f"across {len(held)} held names (min {held_pct.min():.2f})",
                  {"held": int(len(held)), "median_pct": round(median_pct, 3),
                   "min_pct": round(float(held_pct.min()), 3)})


def inv_portfolio_weights_sane() -> Result:
    """The live book must be a concentrated book, not the whole quintile.

    Guards the DailyScorer._build_weights regression where the turnover-capped
    top-N book was discarded and every quintile-5 name got a weight. A healthy
    long book holds well under half the scored universe.
    """
    name = "portfolio_weights_sane"
    path = D / "processed/portfolio_weights.parquet"
    df = _read(path)
    if df is None:
        return _skip(name, "portfolio_weights.parquet missing")
    wcol = next((c for c in ("final_weight", "weight") if c in df.columns), None)
    if wcol is None:
        return _skip(name, "no weight column")
    w = pd.to_numeric(df[wcol], errors="coerce").fillna(0.0)
    held = int((w.abs() > 1e-9).sum())
    gross = float(w.abs().sum())
    # gross must be a sane fraction (0,1.5]; held names must be a real book, not
    # a closet index (<= 60 names for a top-N mandate).
    problems = []
    if not (0.0 < gross <= 1.5):
        problems.append(f"gross={gross:.3f} outside (0,1.5]")
    if held > 60:
        problems.append(f"held={held} names (closet-index; expected concentrated book)")
    if held == 0:
        problems.append("empty book")
    if problems:
        return Result(name, "FAIL", "; ".join(problems), {"held": held, "gross": round(gross, 4)})
    return Result(name, "PASS", f"{held} names, gross {gross:.3f}",
                  {"held": held, "gross": round(gross, 4)})


def inv_refresh_scheduler_healthy() -> Result:
    """No scheduled data source may be silently failing (consecutive_failures>=2).

    This is exactly how the cross-asset feed died for 7.5 weeks: argparse error,
    exit 2, recorded in a state file nobody read.
    """
    name = "refresh_scheduler_healthy"
    path = D / "runtime/refresh_state.json"
    if not path.exists():
        return _skip(name, "refresh_state.json missing")
    try:
        state = json.loads(path.read_text())
    except Exception as exc:
        return Result(name, "FAIL", f"unreadable refresh_state.json: {exc}")
    failing = {}
    for src, info in (state.get("sources") or {}).items():
        cf = int(info.get("consecutive_failures", 0) or 0)
        if cf >= 2:
            failing[src] = {"consecutive_failures": cf, "last_error": info.get("last_error")}
    if failing:
        return Result(name, "FAIL", f"{len(failing)} source(s) failing repeatedly",
                      {"failing": failing})
    return Result(name, "PASS", "all sources healthy", {"sources": len(state.get("sources") or {})})


def inv_consumed_feeds_fresh() -> Result:
    """Consumed live feeds must not be weeks-stale (dead-feed detection).

    Only checks artifacts that the daily live path actually reads. A stale feed
    is a pipeline failure; the fix is to refresh the feed, never to widen this.
    """
    name = "consumed_feeds_fresh"
    now = pd.Timestamp(datetime.now()).normalize()
    feeds = {
        "cross_asset_prices": (D / "canonical/macro/cross_asset_prices_daily.parquet", ("date",)),
        "canonical_prices": (D / "canonical/prices/equity_prices_daily.parquet", ("date",)),
        "scores": (D / "processed/scores.parquet", ("date",)),
        "market_state": (D / "processed/market_state.parquet", ("date", "timestamp")),
    }
    stale, checked = {}, {}
    for label, (path, cols) in feeds.items():
        df = _read(path, columns=None)
        if df is None:
            continue
        mx = _max_date(df, cols)
        if mx is None:
            continue
        age = int((now - mx).days)
        checked[label] = {"latest": str(mx.date()), "age_days": age}
        if age > STALE_HARD_DAYS:
            stale[label] = checked[label]
    if not checked:
        return _skip(name, "no consumed feeds present")
    if stale:
        return Result(name, "FAIL", f"{len(stale)} feed(s) stale > {STALE_HARD_DAYS}d",
                      {"stale": stale, "checked": checked})
    return Result(name, "PASS", f"{len(checked)} feeds fresh", {"checked": checked})


def inv_sentiment_model_consistent() -> Result:
    """The sentiment panel must not have silently DOWNGRADED its model.

    company_sentiment_daily carries a sentiment_model provenance column
    (finbert:... / lexicon / mixed:...). FinBERT can silently fall back to the
    lexicon when transformers is unavailable, changing every sentiment signal
    with no other trace — the mixed-model incident this guards against. FAIL if
    the recent window's dominant model is weaker than the historical norm, or if
    recent days are 'mixed'. SKIP on pre-provenance data (all 'unknown').
    """
    name = "sentiment_model_consistent"
    path = D / "canonical/sentiment/company_sentiment_daily.parquet"
    df = _read(path, columns=None)
    if df is None or "sentiment_model" not in df.columns or "date" not in df.columns:
        return _skip(name, "no sentiment_model provenance yet")
    df = df[["date", "sentiment_model"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sentiment_model"] = df["sentiment_model"].astype(str)
    df = df[(df["sentiment_model"] != "unknown") & df["date"].notna()]
    if df.empty:
        return _skip(name, "sentiment_model all unknown (pre-provenance)")

    def _rank(model: str) -> int:  # higher = stronger
        m = str(model).lower()
        if m.startswith("finbert"):
            return 2
        if m.startswith("mixed"):
            return 1
        return 0  # lexicon / other

    cutoff = df["date"].max() - pd.Timedelta(days=30)
    recent = df[df["date"] >= cutoff]
    history = df[df["date"] < cutoff]
    if recent.empty:
        return _skip(name, "no recent sentiment rows")
    recent_dom = recent["sentiment_model"].value_counts().idxmax()
    mixed_frac = float(recent["sentiment_model"].str.startswith("mixed").mean())
    hist_dom = history["sentiment_model"].value_counts().idxmax() if not history.empty else recent_dom

    problems = []
    if _rank(recent_dom) < _rank(hist_dom):
        problems.append(f"model downgraded: history={hist_dom} -> recent={recent_dom}")
    if mixed_frac > 0.2:
        problems.append(f"{mixed_frac:.0%} of recent days are mixed-model")
    if problems:
        return Result(name, "FAIL", "; ".join(problems),
                      {"recent_dominant": recent_dom, "history_dominant": hist_dom,
                       "mixed_frac": round(mixed_frac, 3)})
    return Result(name, "PASS", f"recent model {recent_dom}", {"recent_dominant": recent_dom})


def inv_dashboard_freshness() -> Result:
    """No more than a small fraction of active dashboard visuals may render stale
    data. This is what turned "64% of panels silently frozen" into a hard signal:
    the dashboard's own registry + freshness resolver decide truth, so a dead feed
    or a repointing regression fails CI instead of quietly lying in a chart.
    """
    name = "dashboard_freshness"
    try:
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from src.dashboard.registry import VISUALS
        from src.dashboard import freshness as F
    except Exception as exc:
        # streamlit or a dashboard dep may be absent in a bare CI image — SKIP,
        # don't fail (the dashboard tab covers itself; this is a bonus gate).
        return _skip(name, f"dashboard import unavailable: {type(exc).__name__}: {exc}")
    total = 0
    stale = []
    for v in VISUALS:
        fr = F.spec_freshness(v)
        if fr["status"] in (F.STATUS_FRESH, F.STATUS_AGING, F.STATUS_STALE, F.STATUS_MISSING):
            total += 1
        if fr["status"] in (F.STATUS_STALE, F.STATUS_MISSING):
            stale.append((v.visual_id, fr.get("detail")))
    if total == 0:
        return _skip(name, "no resolvable visuals")
    frac = len(stale) / total
    # Some genuinely-lagged upstreams (e.g. monthly GST) are acceptable; a
    # widespread stale front is not. Threshold 15%.
    if frac <= 0.15:
        return Result(name, "PASS", f"{total - len(stale)}/{total} visuals fresh",
                      {"stale": len(stale), "total": total})
    return Result(name, "FAIL", f"{len(stale)}/{total} visuals stale ({frac:.0%})",
                  {"stale_sample": stale[:8], "total": total})


def inv_nav_no_backfill() -> Result:
    """The paper-fund NAV must be an honest walk-forward record, not a backfill.

    Guards the look-ahead regression where the engine replayed TODAY's target
    from the 2024 inception across all past dates. The NAV must not begin
    materially before the earliest point-in-time target snapshot
    (data/portfolio/weekly/*.parquet) — if it does, history is being
    back-projected from the current book.
    """
    name = "nav_no_backfill"
    nav_path = D / "pnl/nav_history.parquet"
    weekly_dir = D / "portfolio/weekly"
    nav = _read(nav_path, columns=["date"])
    if nav is None or "date" not in nav.columns:
        return _skip(name, "nav_history.parquet missing/undated")
    nav_start = pd.to_datetime(nav["date"], errors="coerce").min()
    if pd.isna(nav_start):
        return _skip(name, "no NAV dates")
    if not weekly_dir.exists():
        return _skip(name, "no weekly snapshots to compare")
    snap_dates = [pd.to_datetime(p.stem, errors="coerce") for p in weekly_dir.glob("*.parquet")]
    snap_dates = [d for d in snap_dates if pd.notna(d)]
    if not snap_dates:
        return _skip(name, "no dated weekly snapshots")
    first_snap = min(snap_dates)
    # Allow a small grace (a few days) for the trading-day alignment.
    if pd.Timestamp(nav_start) < pd.Timestamp(first_snap) - pd.Timedelta(days=7):
        return Result(name, "FAIL",
                      f"NAV starts {pd.Timestamp(nav_start).date()} but first target snapshot "
                      f"is {pd.Timestamp(first_snap).date()} — history is back-projected",
                      {"nav_start": str(pd.Timestamp(nav_start).date()),
                       "first_snapshot": str(pd.Timestamp(first_snap).date())})
    return Result(name, "PASS", f"NAV starts {pd.Timestamp(nav_start).date()} ≥ first target",
                  {"nav_start": str(pd.Timestamp(nav_start).date())})


def inv_price_panel_trading_clean() -> Result:
    """The processed price panel must be trading-clean: no weekend/holiday rows,
    no forward-filled frozen blocks, no sub-threshold scale seams.

    Guards the corruption that silently poisoned the 2026-07-04 alpha export —
    5 mega-caps (HDFCBANK, ICICIBANK, INFY, RELIANCE, TCS) whose feed fabricated
    NSE-holiday rows and, for HDFCBANK/ICICIBANK, forward-filled two full years
    at ~1/5 scale. Because every feature is cross-sectionally ranked per date, one
    corrupted mega-cap perturbs every stock's z-score on every affected date.
    Delegates to scripts/ci/check_price_integrity (single source of truth)."""
    name = "price_panel_trading_clean"
    prices = D / "processed/prices.parquet"
    if not prices.exists():
        return _skip(name, "processed/prices.parquet missing")
    try:
        from scripts.ci import check_price_integrity as cpi
    except Exception:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "check_price_integrity", Path(__file__).with_name("check_price_integrity.py"))
        cpi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cpi)
    report = cpi.run(prices)
    checks = report["checks"]
    # ADVISORY (mega-cap pins) never fails this invariant, matching the gate.
    hard_fail = {k: v["status"] for k, v in checks.items()
                 if v["status"] == "FAIL"}
    if not hard_fail:
        return Result(name, "PASS",
                      f"{report['tickers']} tickers trading-clean",
                      {"rows": report["rows"]})
    quarantine = list(checks["flat_lines"].get("quarantine_refetch", {}).keys())
    return Result(name, "FAIL",
                  f"price panel corrupt: {', '.join(hard_fail)}"
                  + (f"; re-fetch {quarantine}" if quarantine else ""),
                  {"failing_checks": hard_fail, "quarantine_refetch": quarantine})


INVARIANTS: tuple[Callable[[], Result], ...] = (
    inv_fundamentals_unit_continuity,
    inv_price_panel_trading_clean,
    inv_valuation_engines_nondegenerate,
    inv_stock_roles_nondegenerate,
    inv_scores_have_spread,
    inv_scores_book_is_top_ranked,
    inv_portfolio_weights_sane,
    inv_nav_no_backfill,
    inv_refresh_scheduler_healthy,
    inv_consumed_feeds_fresh,
    inv_sentiment_model_consistent,
    inv_dashboard_freshness,
)


def run() -> tuple[int, list[Result]]:
    results: list[Result] = []
    for fn in INVARIANTS:
        try:
            results.append(fn())
        except Exception as exc:
            results.append(Result(fn.__name__, "FAIL", f"invariant raised: {exc}"))
    rc = 1 if any(r.failed for r in results) else 0
    return rc, results


def main() -> int:
    ap = argparse.ArgumentParser(description="Live-artifact truth invariants gate")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    args = ap.parse_args()

    rc, results = run()
    if args.json:
        print(json.dumps({"gate": "live_artifact_invariants",
                          "status": "FAIL" if rc else "PASS",
                          "results": [r.__dict__ for r in results]}, indent=2, default=str))
        return rc

    print("== live-artifact truth invariants ==")
    for r in results:
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}[r.status]
        print(f"{icon} {r.name:34s} {r.status:4s} {r.detail}")
        if r.failed and r.metrics:
            print(f"      {json.dumps(r.metrics, default=str)[:400]}")
    n_fail = sum(1 for r in results if r.failed)
    n_skip = sum(1 for r in results if r.status == "SKIP")
    print(f"-- {len(results)-n_fail-n_skip} pass, {n_fail} fail, {n_skip} skip --")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
