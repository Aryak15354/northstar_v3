"""Tests for the NSE XBRL fetcher, credit loader, and document extractor."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.xbrl_results_fetcher import _derive, _taxonomy_from_url
from src.ingestion.credit_loader import CreditLoader
from src.ingestion.document_extractor import extract_from_text

CREDIT_PARQUET = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "credit_quarterly.parquet"


def test_taxonomy_from_url():
    assert _taxonomy_from_url("x/BANKING_1_2.xml") == "banking"
    assert _taxonomy_from_url("x/NBFC_INDAS_1.xml") == "nbfc"
    assert _taxonomy_from_url("x/INDAS_1.xml") == "generic"
    assert _taxonomy_from_url("x/INS_1.xml") == "insurance"


def test_derive_nii_and_pcr():
    row = _derive({
        "interest_earned": 100.0, "interest_expended": 60.0,
        "gross_npa": 10.0, "net_npa": 4.0, "provisions": 8.0,
    })
    assert row["net_interest_income"] == 40.0
    assert row["provision_coverage_ratio"] == pytest.approx(0.6)
    assert row["credit_cost_to_nii"] == pytest.approx(0.2)


def test_extract_it_metrics_from_press_release_text():
    text = (
        "Order Book of $8.1 billion, Book to Bill ratio of 1.1. "
        "LTM IT Services attrition rate at 13.3%. "
        "TCS' workforce stood at 603,305 as at the end of the quarter."
    )
    ex = extract_from_text(text, "TCS", "press_release", "sample.pdf")
    metrics = {e.metric: e.value for e in ex}
    assert metrics.get("attrition_pct") == 13.3
    assert metrics.get("tcv_usd_bn") == 8.1
    assert metrics.get("headcount") == 603305.0


def test_extract_bank_metrics_from_presentation_text():
    text = "NIM at 3.6% for the quarter. CASA ratio of 42.5%. PCR at 71%."
    ex = extract_from_text(text, "HDFCBANK", "investor_presentation", "deck.pdf")
    metrics = {e.metric: e.value for e in ex}
    assert metrics.get("nim_pct") == 3.6
    assert metrics.get("casa_pct") == 42.5
    assert metrics.get("pcr_pct") == 71.0


@pytest.mark.skipif(not CREDIT_PARQUET.exists(), reason="credit parquet not built")
def test_credit_loader_pit_hides_future_filings():
    cl = CreditLoader()
    # A filing broadcast after the as-of date must not appear.
    df = cl.load(as_of_date=datetime(2025, 1, 1), tickers=["HDFCBANK"])
    if df.empty:
        pytest.skip("HDFCBANK not in dataset")
    assert (df["availability_date"] <= pd.Timestamp("2025-01-01")).all()


@pytest.mark.skipif(not CREDIT_PARQUET.exists(), reason="credit parquet not built")
def test_credit_parquet_pit_integrity():
    df = pd.read_parquet(CREDIT_PARQUET)
    period_end = pd.to_datetime(df["period_end"])
    avail = pd.to_datetime(df["availability_date"])
    # availability (broadcast) must never precede the period it reports
    assert (avail >= period_end).all()
    # no future availability dates
    assert (avail <= pd.Timestamp.now().normalize()).all()
