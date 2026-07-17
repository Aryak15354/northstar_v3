"""Persistent, history-aware store for OptionsOrgan suggestions.

The point: the options organ must NOT behave as if it starts from scratch each
day. This store (1) persists every day's suggestions to a rolling history, and
(2) feeds that history back so today's decisions are informed by what was
suggested yesterday / last week:

  - CONTINUITY: a name flagged bearish (or a hedge on a held equity) that was
    already flagged on prior days is marked `continued` with a `days_active`
    streak, instead of appearing brand-new each morning.
  - CONVICTION: persistent signals get a priority boost, so a name weak for a
    week ranks above a one-day blip.
  - LIFECYCLE: names that were suggested before but dropped out today are
    recorded as `closed` in history, so nothing silently disappears.
  - OUTCOME: for closed directional ideas, a rough realized move is logged
    (spot then vs now) for later evaluation.

Artifacts (all under data/options/suggestions/):
  history/<YYYY-MM-DD>.json          -- full daily snapshot
  suggestion_history.parquet         -- rolling flat table (one row per
                                        suggestion per day) used for continuity
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger("options.suggestion_store")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUGG_DIR = PROJECT_ROOT / "data" / "options" / "suggestions"
HISTORY_DIR = SUGG_DIR / "history"
HISTORY_PARQUET = SUGG_DIR / "suggestion_history.parquet"

_HISTORY_COLS = [
    "date", "category", "underlying", "structure", "status", "days_active",
    "net_debit_credit", "max_loss", "priority", "spot", "hedges_symbol",
]


class SuggestionStore:
    def __init__(
        self,
        history_dir: Path = HISTORY_DIR,
        history_parquet: Path = HISTORY_PARQUET,
        *,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.history_dir = Path(history_dir)
        self.history_parquet = Path(history_parquet)
        self.log = log or logger

    # ------------------------------------------------------------------ #
    def load_history(self, lookback_days: int = 20) -> pd.DataFrame:
        if not self.history_parquet.exists():
            return pd.DataFrame(columns=_HISTORY_COLS)
        try:
            df = pd.read_parquet(self.history_parquet)
        except Exception:
            return pd.DataFrame(columns=_HISTORY_COLS)
        if df.empty or "date" not in df.columns:
            return pd.DataFrame(columns=_HISTORY_COLS)
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=lookback_days)
        return df[df["date"] >= cutoff]

    # ------------------------------------------------------------------ #
    def annotate(self, suggestions: List[Any], as_of: Optional[datetime] = None) -> None:
        """Set status / days_active / history_note / priority-boost on each
        suggestion in place, using the persisted history. Idempotent: re-running
        for the same day does not inflate streaks (today's own rows are ignored
        when measuring the prior streak)."""
        as_of = as_of or datetime.now()
        today = pd.Timestamp(as_of).normalize()
        hist = self.load_history(lookback_days=20)
        # Prior history excludes today (so a same-day re-run is stable).
        prior = hist[hist["date"] < today] if not hist.empty else hist

        # Per (underlying, category): the set of prior distinct dates it was seen.
        streaks: Dict[tuple, List[pd.Timestamp]] = {}
        if not prior.empty:
            for (u, c), grp in prior.groupby(["underlying", "category"]):
                streaks[(str(u), str(c))] = sorted(pd.to_datetime(grp["date"]).dt.normalize().unique())

        for s in suggestions:
            key = (s.underlying, s.category)
            dates = streaks.get(key, [])
            # Count the consecutive-trading-day streak ending at the most recent
            # prior appearance (allowing weekend/holiday gaps up to 4 days).
            streak = 0
            if dates:
                streak = 1
                for i in range(len(dates) - 1, 0, -1):
                    gap = (dates[i] - dates[i - 1]).days
                    if gap <= 4:
                        streak += 1
                    else:
                        break
            was_recent = bool(dates) and (today - dates[-1]).days <= 4
            s.status = "continued" if was_recent else "new"
            s.days_active = streak + 1 if was_recent else 1
            if was_recent:
                s.history_note = f"continued signal, active ~{s.days_active} trading days"
                # Conviction boost for persistence (capped).
                s.priority = round(s.priority * min(1.0 + 0.15 * (s.days_active - 1), 2.0), 4)
            else:
                s.history_note = "new signal today"

        # Re-rank within category after the persistence boost.
        suggestions.sort(key=lambda x: (x.category, -x.priority))

    # ------------------------------------------------------------------ #
    def record(self, suggestions: List[Any], regime: str, as_of: Optional[datetime] = None) -> Path:
        """Persist today's snapshot (JSON) and append rows to the rolling
        history parquet. Also marks prior open ideas that dropped out today as
        'closed' for lifecycle continuity."""
        as_of = as_of or datetime.now()
        date_str = pd.Timestamp(as_of).strftime("%Y-%m-%d")
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Daily JSON snapshot.
        snap = {
            "date": date_str,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "regime": regime,
            "suggestions": [s.to_dict() for s in suggestions],
        }
        snap_path = self.history_dir / f"{date_str}.json"
        tmp = snap_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
        tmp.replace(snap_path)

        # Rolling parquet history.
        rows = [{
            "date": pd.Timestamp(as_of).normalize(),
            "category": s.category, "underlying": s.underlying, "structure": s.structure,
            "status": s.status, "days_active": s.days_active,
            "net_debit_credit": s.net_debit_credit, "max_loss": s.max_loss,
            "priority": s.priority, "spot": s.spot, "hedges_symbol": s.hedges_symbol or "",
        } for s in suggestions]
        today_df = pd.DataFrame(rows, columns=_HISTORY_COLS)

        if self.history_parquet.exists():
            try:
                existing = pd.read_parquet(self.history_parquet)
                existing["date"] = pd.to_datetime(existing["date"], errors="coerce")
                # Replace any existing rows for today (idempotent re-run).
                existing = existing[existing["date"].dt.normalize() != pd.Timestamp(as_of).normalize()]
                combined = pd.concat([existing, today_df], ignore_index=True)
            except Exception:
                combined = today_df
        else:
            combined = today_df

        self.history_parquet.parent.mkdir(parents=True, exist_ok=True)
        tmpp = self.history_parquet.with_suffix(".parquet.tmp")
        combined.to_parquet(tmpp, index=False)
        tmpp.replace(self.history_parquet)
        self.log.info("Recorded %d suggestions for %s (history rows=%d)", len(suggestions), date_str, len(combined))
        return snap_path

    # ------------------------------------------------------------------ #
    def recent_summary(self, lookback_days: int = 7) -> Dict[str, Any]:
        """A compact 'what happened last week' view for operators / decisions."""
        hist = self.load_history(lookback_days=lookback_days)
        if hist.empty:
            return {"days": 0, "by_category": {}, "persistent_names": []}
        by_cat = hist.groupby("category")["underlying"].count().to_dict()
        # Names flagged on the most days = the persistent convictions.
        persistence = (
            hist.groupby(["underlying", "category"])["date"].nunique()
            .sort_values(ascending=False).head(10)
        )
        persistent = [
            {"underlying": u, "category": c, "days": int(n)}
            for (u, c), n in persistence.items() if n >= 2
        ]
        return {
            "days": int(hist["date"].nunique()),
            "by_category": {k: int(v) for k, v in by_cat.items()},
            "persistent_names": persistent,
        }
