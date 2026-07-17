"""Shared cross-sectional / identifier helpers. Single source of truth.

Do NOT copy these functions into other modules; import them. Historically the
project maintained 4-5 independent copies of ``group_zscore`` /
``group_rank_centered`` / ``normalize_ticker``, some patched and some not, which
reintroduced the exact "missing history reads as a hard zero" and
"NaN ticker becomes NAN.NS" bugs each time one copy was fixed in isolation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _coerce_groups(groups, index: pd.Index) -> pd.Series:
    """Normalize any group specifier to a Series aligned on ``index``.

    Callers legitimately pass a MultiIndex for composite keys (e.g. date x
    sector). ``pd.Series(MultiIndex)`` raises NotImplementedError on pandas 2.x,
    so factorize the tuples to integer codes instead: same grouping, faster, and
    a NaN-bearing tuple stays its own group exactly as tuple-grouping would.
    """
    if isinstance(groups, pd.MultiIndex):
        return pd.Series(pd.factorize(groups)[0], index=index)
    if isinstance(groups, pd.Series):
        return groups if groups.index.equals(index) else groups.set_axis(index)
    return pd.Series(np.asarray(groups), index=index)


def group_zscore(values: pd.Series, groups: pd.Series, clip_abs: float = 6.0) -> pd.Series:
    """Cross-sectional z-score within each group.

    A present-but-degenerate group (std == 0) collapses to 0.0; a genuinely
    missing input stays NaN. This distinction is the whole point of the helper:
    an unconditional ``fillna(0.0)`` would turn sparse-history factors into a
    hard-coded zero signal instead of leaving them missing.

    ``groups`` accepts a Series, array-like, or MultiIndex (composite key).
    """
    v = pd.to_numeric(values, errors="coerce")
    g = _coerce_groups(groups, v.index)
    mu = v.groupby(g, sort=False).transform("mean")
    sd = v.groupby(g, sort=False).transform("std").replace(0.0, np.nan)
    z = ((v - mu) / (sd + 1e-12)).replace([np.inf, -np.inf], np.nan)
    present = v.notna()
    z = z.mask(present & z.isna(), 0.0)   # present but degenerate group -> 0
    z = z.mask(~present, np.nan)          # genuinely missing -> stays NaN
    return z.clip(-float(clip_abs), float(clip_abs)).astype(float)


def group_rank_centered(values: pd.Series, groups: pd.Series) -> pd.Series:
    """Percentile rank within each group, centered on zero (range [-0.5, 0.5]).

    Present-but-degenerate groups map to 0.0 (the centered midpoint); genuinely
    missing inputs stay NaN.

    ``groups`` accepts a Series, array-like, or MultiIndex (composite key).
    """
    v = pd.to_numeric(values, errors="coerce")
    g = _coerce_groups(groups, v.index)
    r = v.groupby(g, sort=False).rank(method="average", pct=True)
    present = v.notna()
    r = r.mask(present & r.isna(), 0.5)
    r = r.mask(~present, np.nan)
    return r.sub(0.5).astype(float)


def normalize_ticker(value: object) -> str:
    """Normalize a ticker to the ``SYMBOL.NS`` form, returning "" for missing.

    ``str(value or "")`` is unsafe here: ``float('nan')`` is truthy, so it would
    short-circuit to ``nan`` and produce a fabricated ``"NAN.NS"`` ticker for
    what should have been recognized as missing input.
    """
    try:
        if value is None or pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(value).strip().upper()
    if not s or s == "NAN":
        return ""
    if s.endswith((".NS", ".BO")):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def sector_string(series: pd.Series, fill: str = "UNKNOWN") -> pd.Series:
    """Return a string sector series with real NaN filled by ``fill``.

    ``astype(str).fillna(fill)`` is a trap: ``astype(str)`` converts real NaN to
    the literal string ``"nan"`` first, so the subsequent ``fillna`` never fires.
    ``astype("string")`` (nullable) preserves real nulls so ``fillna`` works.
    """
    return series.astype("string").fillna(fill).astype("string")


def coalesce_rowwise(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    """Per-row coalesce: take ``primary`` where present, else ``fallback``.

    Use this instead of ``if primary.isna().all(): primary = fallback`` — the
    whole-column guard never fires when even one row of ``primary`` is present,
    so per-row gaps that the fallback could fill are left missing.
    """
    p = pd.to_numeric(primary, errors="coerce")
    f = pd.to_numeric(fallback, errors="coerce")
    return p.where(p.notna(), f)
