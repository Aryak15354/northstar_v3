"""Regression tests for the Black-Scholes engine and the unified OptionsOrgan."""

import math

import pytest

from src.options.black_scholes import price_and_greeks, atm_iv_estimate
from src.options.options_organ import OptionsOrgan


# ----------------------------- Black-Scholes ----------------------------- #
def test_put_call_parity():
    c = price_and_greeks(option_type="CE", spot=100, strike=100, days_to_expiry=365, iv=0.2, rate=0.065)
    p = price_and_greeks(option_type="PE", spot=100, strike=100, days_to_expiry=365, iv=0.2, rate=0.065)
    # C - P == S - K e^{-rT}
    assert abs((c.price - p.price) - (100 - 100 * math.exp(-0.065))) < 1e-2


def test_greek_signs_and_bounds():
    c = price_and_greeks(option_type="CE", spot=100, strike=100, days_to_expiry=30, iv=0.2, rate=0.065)
    p = price_and_greeks(option_type="PE", spot=100, strike=100, days_to_expiry=30, iv=0.2, rate=0.065)
    assert 0.0 <= c.delta <= 1.0 and -1.0 <= p.delta <= 0.0
    assert c.gamma > 0 and p.gamma > 0          # long options are long gamma
    assert c.vega > 0 and p.vega > 0            # long options are long vega
    assert c.theta < 0 and p.theta < 0          # long options bleed time value


def test_expiry_intrinsic():
    itm = price_and_greeks(option_type="CE", spot=110, strike=100, days_to_expiry=0, iv=0.2)
    assert abs(itm.price - 10.0) < 1e-6
    otm = price_and_greeks(option_type="PE", spot=110, strike=100, days_to_expiry=0, iv=0.2)
    assert otm.price == 0.0


def test_iv_estimate_regime_aware():
    calm = atm_iv_estimate(0.18, "expansion")
    crisis = atm_iv_estimate(0.18, "crisis")
    assert crisis > calm > 0.18   # vol risk premium, higher in stress


# ------------------------------- OptionsOrgan ---------------------------- #
@pytest.fixture()
def organ(tmp_path):
    return OptionsOrgan(report_path=tmp_path / "sugg.json")


def test_hedge_only_for_deteriorating_holdings(organ):
    organ.ingest(
        regime="hostile_bear",
        holdings={
            "BADCO.NS": {"spot": 500, "quantity": 100, "situation_score": -0.6, "realized_vol": 0.3},
            "OKCO.NS": {"spot": 500, "quantity": 100, "situation_score": 0.1, "realized_vol": 0.2},
        },
        candidates={},
    )
    hedges = organ.suggest_hedges()
    hedged = {h.hedges_symbol for h in hedges}
    assert "BADCO.NS" in hedged        # deteriorating -> hedged
    assert "OKCO.NS" not in hedged     # healthy -> not hedged


def test_severe_gets_protective_put_mild_gets_collar(organ):
    organ.ingest(
        regime="bear",
        holdings={
            "SEVERE.NS": {"spot": 800, "quantity": 100, "situation_score": -0.7, "realized_vol": 0.3},
            "MILD.NS": {"spot": 800, "quantity": 100, "situation_score": -0.2, "realized_vol": 0.25},
        },
        candidates={},
    )
    by_sym = {h.hedges_symbol: h for h in organ.suggest_hedges()}
    assert by_sym["SEVERE.NS"].structure == "protective_put"
    assert by_sym["MILD.NS"].structure == "collar"


def test_directional_shorts_and_longs(organ):
    organ.ingest(
        regime="neutral",
        holdings={},
        candidates={
            "BEARSTRONG.NS": {"spot": 1000, "directional_score": -0.6, "realized_vol": 0.3},
            "BULL.NS": {"spot": 1000, "directional_score": 0.5, "realized_vol": 0.2},
            "FLAT.NS": {"spot": 1000, "directional_score": 0.0, "realized_vol": 0.2},
        },
    )
    shorts = {s.underlying: s for s in organ.suggest_shorts()}
    longs = {s.underlying: s for s in organ.suggest_longs()}
    assert shorts["BEARSTRONG.NS"].structure == "bear_put_spread"  # strong -> defined-risk spread
    assert shorts["BEARSTRONG.NS"].net_delta < 0                    # bearish exposure
    assert longs["BULL.NS"].net_delta > 0                           # bullish exposure
    assert "FLAT.NS" not in shorts and "FLAT.NS" not in longs       # neutral -> no directional


def test_spread_max_loss_is_bounded(organ):
    organ.ingest(
        regime="neutral", holdings={},
        candidates={"X.NS": {"spot": 1000, "directional_score": -0.6, "realized_vol": 0.3}},
    )
    s = organ.suggest_shorts()[0]
    assert s.structure == "bear_put_spread"
    assert 0 < s.max_loss < float("inf")            # defined risk
    assert s.max_profit not in (None, float("inf")) # capped upside


def test_full_cycle_and_report(organ, tmp_path):
    organ.ingest(
        regime="range_bound_low_vol", holdings={},
        candidates={"NIFTY": {"spot": 24000, "directional_score": 0.0, "realized_vol": 0.12}},
    )
    sugg = organ.process()
    assert any(s.category == "opportunity" for s in sugg)
    path = organ.write_report()
    assert path.exists()
    g = organ.aggregate_greeks()
    assert set(g) == {"net_delta", "net_theta", "net_vega", "premium_at_risk"}


def test_read_state_is_defensive(tmp_path):
    # A junk state object must never raise; with the v3-artifact fallback
    # disabled it degrades to empty inputs.
    org = OptionsOrgan(
        config={"options_organ": {"use_v3_artifacts": False}},
        report_path=tmp_path / "s.json",
    )

    class Junk:
        pass
    org.read_state(Junk())
    assert org.process() == []


# --------------------------- CandidateBuilder ---------------------------- #
def test_candidate_builder_normalizes_and_feeds_organ(tmp_path):
    """Builder maps raw scorer output -> [-1,1] directional scores and the
    organ consumes them; a bearish name yields a short, a bullish name a long."""
    import pandas as pd, json
    from src.options.candidate_builder import CandidateBuilder
    from src.options.options_organ import OptionsOrgan

    scores = tmp_path / "scores.parquet"
    pd.DataFrame({
        "ticker": ["WEAK.NS", "STRONG.NS", "MID.NS"],
        "northstar_score": [-3.0, 3.0, 0.0],
        "regime": ["neutral"] * 3,
    }).to_parquet(scores)
    sent = tmp_path / "sent.parquet"
    pd.DataFrame({"ticker": [], "sentiment_polarity": [], "sentiment_surprise": [],
                  "availability_date": []}).to_parquet(sent)
    pos = tmp_path / "pos.json"
    pos.write_text(json.dumps({"positions": {}}))

    # Provide prices via a fake read_prices_legacy by monkeypatching module path.
    import src.options.candidate_builder as cb
    fake_prices = pd.DataFrame({
        "ticker": ["WEAK.NS", "STRONG.NS", "MID.NS"] * 10,
        "Date": pd.date_range("2026-01-01", periods=10).tolist() * 3,
        "Close": [100] * 30,
    })
    cb.CandidateBuilder._load_prices = lambda self: fake_prices  # type: ignore

    b = CandidateBuilder(scores_path=scores, sentiment_path=sent, positions_path=pos)
    regime, cands, holds = b.build()
    assert cands["WEAK.NS"]["directional_score"] < -0.2
    assert cands["STRONG.NS"]["directional_score"] > 0.2

    org = OptionsOrgan(report_path=tmp_path / "s.json")
    org.ingest(regime=regime, holdings=holds, candidates=cands)
    cats = {s.underlying: s.category for s in org.process()}
    assert cats.get("WEAK.NS") == "short"
    assert cats.get("STRONG.NS") == "long"


# --------------------------- SuggestionStore ----------------------------- #
def test_history_continuity_and_conviction_boost(tmp_path):
    """A signal seen on prior days is 'continued' with a streak + priority
    boost; a fresh signal is 'new'."""
    from datetime import datetime, timedelta
    from src.options.suggestion_store import SuggestionStore

    store = SuggestionStore(history_dir=tmp_path / "h", history_parquet=tmp_path / "h.parquet")
    cands = {"P.NS": {"spot": 1000, "directional_score": -0.6, "realized_vol": 0.3}}

    for d in (2, 1):  # two prior days
        o = OptionsOrgan(config={"options_organ": {"use_history": False}}, report_path=tmp_path / "l.json")
        o.ingest(regime="neutral", holdings={}, candidates=cands)
        o.process()
        store.record(o.suggestions, "neutral", as_of=datetime.now() - timedelta(days=d))

    today = OptionsOrgan(config={"options_organ": {"use_history": False}}, report_path=tmp_path / "l.json")
    today.ingest(regime="neutral", holdings={},
                 candidates={**cands, "NEW.NS": {"spot": 1000, "directional_score": -0.6, "realized_vol": 0.3}})
    today.process()
    base_priority = {s.underlying: s.priority for s in today.suggestions}
    store.annotate(today.suggestions, as_of=datetime.now())
    by = {s.underlying: s for s in today.suggestions}
    assert by["P.NS"].status == "continued" and by["P.NS"].days_active >= 3
    assert by["P.NS"].priority > base_priority["P.NS"]   # conviction boost
    assert by["NEW.NS"].status == "new" and by["NEW.NS"].days_active == 1

    summ = store.recent_summary(lookback_days=7)
    assert any(p["underlying"] == "P.NS" for p in summ["persistent_names"])
