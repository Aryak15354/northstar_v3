from arya.eval.finance_qa import FINANCE_QA_SEED, score_keyword_qa
from arya.eval.hallucination_tests import ticker_validity_rate
from arya.eval.red_team import default_red_team_cases


def test_phase9_finance_qa_keyword_score():
    answers = {
        FINANCE_QA_SEED[0].question: "India VIX measures expected NIFTY volatility and market fear.",
        FINANCE_QA_SEED[1].question: "The RBI uses repo and reverse repo to borrow and lend liquidity.",
    }
    assert score_keyword_qa(answers, FINANCE_QA_SEED[:2]) == 1.0


def test_phase9_ticker_validity_rate():
    outputs = ["Symbol impacts: RELIANCE and TCS. RBI stays neutral.", "No ticker impact."]
    assert ticker_validity_rate(outputs, {"RELIANCE", "TCS"}) == 1.0
    assert ticker_validity_rate(["Invented impact: FAKECO"], {"RELIANCE"}) == 0.0


def test_phase9_default_red_team_cases_have_enforceable_rules():
    cases = default_red_team_cases()
    assert cases
    assert cases[0].passes("Recommend MONITOR_ONLY because the circular is routine.")
    assert not cases[0].passes("Recommend HALT_NEW_TRADES immediately.")

