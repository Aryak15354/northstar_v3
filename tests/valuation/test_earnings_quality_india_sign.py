from __future__ import annotations

from src.valuation.forensic import earnings_quality as eq


def test_india_accrual_sign_high_accruals_score_higher() -> None:
    original = eq.INDIA_ACCRUAL_SIGN_POSITIVE
    try:
        eq.INDIA_ACCRUAL_SIGN_POSITIVE = True
        high = eq._compute_accrual_quality_score(0.12)
        low = eq._compute_accrual_quality_score(0.01)
        assert high > low
    finally:
        eq.INDIA_ACCRUAL_SIGN_POSITIVE = original


def test_india_accrual_not_a_red_flag() -> None:
    original = eq.INDIA_ACCRUAL_SIGN_POSITIVE
    try:
        eq.INDIA_ACCRUAL_SIGN_POSITIVE = True
        analyzer = eq.EarningsQualityAnalyzer()
        red_flags = analyzer.detect_red_flags(
            accrual_ratio=0.15,
            cash_conversion=1.0,
            beneish={},
            earnings_volatility=0.1,
        )
        assert not any("High accruals" in flag for flag in red_flags)
    finally:
        eq.INDIA_ACCRUAL_SIGN_POSITIVE = original
