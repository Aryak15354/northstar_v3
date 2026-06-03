from __future__ import annotations

from src.valuation.core.screener_field_map import (
    INTERNAL_TO_SCREENER,
    REQUIRED_FOR_ACCRUALS,
    REQUIRED_FOR_DCF,
    REQUIRED_FOR_MOAT,
    REQUIRED_FOR_MULTIPLES,
    REQUIRED_FOR_RESIDUAL_INCOME,
    SCREENER_TO_INTERNAL,
)


def test_required_field_sets_are_covered_by_mapping():
    mapped_values = set(SCREENER_TO_INTERNAL.values())
    required = (
        set(REQUIRED_FOR_DCF)
        | set(REQUIRED_FOR_MOAT)
        | set(REQUIRED_FOR_ACCRUALS)
        | set(REQUIRED_FOR_RESIDUAL_INCOME)
        | set(REQUIRED_FOR_MULTIPLES)
    )
    assert required.issubset(mapped_values)


def test_internal_to_screener_is_invertible_for_canonical_map():
    assert len(INTERNAL_TO_SCREENER) == len(set(SCREENER_TO_INTERNAL.values()))
    for screener_name, internal_name in SCREENER_TO_INTERNAL.items():
        assert INTERNAL_TO_SCREENER[internal_name] == screener_name
