"""Feature-family mapping for the research alpha factory."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Mapping, Sequence, Tuple


# Ordered from most specific to most general to reduce ambiguous matches.
DEFAULT_FAMILY_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "shareholder_yield",
        (
            r"share(s|_outstanding)?",
            r"buyback",
            r"dividend",
            r"payout",
            r"net_payout",
        ),
    ),
    (
        "leverage",
        (
            r"debt",
            r"leverage",
            r"interest_coverage",
            r"\bnet_debt\b",
        ),
    ),
    (
        "quality",
        (
            r"\broe\b",
            r"\broa\b",
            r"ni_margin",
            r"gross_margin",
            r"op(erating)?_margin",
            r"accrual",
            r"operating_income",
            r"net_income",
        ),
    ),
    (
        "value",
        (
            r"\bpe\b",
            r"\bpb\b",
            r"book",
            r"earnings[_-]?yield",
            r"ebitda",
            r"fcf",
            r"posterior_gap",
            r"mispricing",
            r"value",
        ),
    ),
    (
        "growth",
        (
            r"growth",
            r"revenue",
            r"eps",
            r"accel",
        ),
    ),
    (
        "momentum",
        (
            r"\bmom",
            r"\bret_[0-9]+d",
            r"trend",
            r"price_to_sma",
            r"breakout",
        ),
    ),
    (
        "volatility",
        (
            r"\bvol",
            r"variance",
            r"drawdown",
            r"stress",
            r"risk",
        ),
    ),
    (
        "liquidity",
        (
            r"liquidity",
            r"volume",
            r"turnover",
            r"\badv\b",
            r"spread",
        ),
    ),
    (
        "profitability_stability",
        (
            r"stability",
            r"stdmargin",
            r"posterior_variance",
            r"consistency",
        ),
    ),
    (
        "operating_efficiency",
        (
            r"asset_turnover",
            r"inventory",
            r"working_cap",
            r"fcf_to_ocf",
            r"operating_cash_flow",
            r"efficiency",
        ),
    ),
    (
        "macro_conditioned",
        (
            r"^macro_",
            r"^mkt_sent_",
            r"^sent_",
            r"regime",
            r"market_phase",
            r"narrative",
            r"coherence",
            r"liquidity_state",
        ),
    ),
)

_CS_SUFFIX_RE = re.compile(r"(_cs_(z|rank))$", re.IGNORECASE)


def _canonical_feature_name(name: str) -> str:
    cleaned = str(name or "").strip().lower()
    return _CS_SUFFIX_RE.sub("", cleaned)


def infer_family(
    feature_name: str,
    *,
    family_rules: Sequence[Tuple[str, Sequence[str]]] | None = None,
    fallback: str = "other",
) -> str:
    """Infer a factor family for a single feature name."""
    rules = family_rules if family_rules is not None else DEFAULT_FAMILY_RULES
    name = _canonical_feature_name(feature_name)
    if not name:
        return str(fallback)

    for family, patterns in rules:
        for pattern in patterns:
            if re.search(str(pattern), name):
                return str(family)
    return str(fallback)


def build_feature_family_map(
    feature_names: Iterable[str],
    *,
    family_rules: Sequence[Tuple[str, Sequence[str]]] | None = None,
    manual_map: Mapping[str, str] | None = None,
    fallback: str = "other",
) -> Dict[str, str]:
    """Build deterministic feature->family mapping with optional manual overrides."""
    out: Dict[str, str] = {}
    manual = {str(k): str(v) for k, v in (manual_map or {}).items()}
    manual_lower = {_canonical_feature_name(k): str(v) for k, v in manual.items()}

    for feature in feature_names:
        fname = str(feature)
        if fname in manual:
            out[fname] = manual[fname]
            continue

        canonical = _canonical_feature_name(fname)
        if canonical in manual_lower:
            out[fname] = manual_lower[canonical]
            continue

        out[fname] = infer_family(
            fname,
            family_rules=family_rules,
            fallback=fallback,
        )
    return out
