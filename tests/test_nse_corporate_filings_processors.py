#!/usr/bin/env python3

from pathlib import Path

import pandas as pd

from scripts.nse_corporate_filings_processors import (
    classify_announcement_category,
    parse_nse_announcements_csv,
    parse_nse_promoter_pledge_csv,
)


def test_parse_nse_promoter_pledge_csv_maps_ticker_and_numeric_fields(tmp_path: Path):
    path = tmp_path / "pledge.csv"
    pd.DataFrame(
        [
            {
                "NAME OF COMPANY": "360 ONE WAM LIMITED",
                "TOTAL PROMOTER HOLDING NO. OF SHARES (A)": 25328244,
                "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM NO. OF SHARES PLEDGED": 5053297,
                "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM TOTAL NO. OF DEMAT SHARES": 405778237,
                "(%) PLEDGE / DEMAT": 1.25,
                "Values(Rs. Cr.)": 601.342,
                "BROADCAST DATE": "18-Mar-2026 16:31:20",
            }
        ]
    ).to_csv(path, index=False)

    parsed = parse_nse_promoter_pledge_csv(path)

    assert len(parsed) == 1
    row = parsed.iloc[0]
    assert row["company_name"] == "360 ONE WAM LIMITED"
    assert row["nse_ticker"] == "360ONE.NS"
    assert row["pledge_pct"] == 1.25
    assert row["source"] == "NSE_PROMOTER_PLEDGE"
    assert str(row["date"]).startswith("2026-03-18")


def test_classify_announcement_category_matches_existing_feature_buckets():
    assert classify_announcement_category("Award of Order / Receipt of Order", "Received contract worth Rs 50 crore") == "Order Win"
    assert classify_announcement_category("Scheme of Arrangement", "Board approved amalgamation") == "Merger"
    assert classify_announcement_category("General Updates", "Capacity expansion at new plant") == "Capacity Expansion"


def test_parse_nse_announcements_csv_standardizes_equity_export(tmp_path: Path):
    path = tmp_path / "announcements.csv"
    pd.DataFrame(
        [
            {
                "SYMBOL": "KPIL",
                "COMPANY NAME": "Kalpataru Projects International Limited",
                "SUBJECT": "Award of Order / Receipt of Order",
                "DETAILS": "Company received an order worth Rs. 120 crore.",
                "BROADCAST DATE/TIME": "18-Mar-2026 19:31:15",
                "RECEIPT": "2026-03-18 19:31:15",
                "DISSEMINATION": "18-Mar-2026 19:31:16",
                "DIFFERENCE": "00:00:01",
                "ATTACHMENT": "https://example.com/a.pdf",
            }
        ]
    ).to_csv(path, index=False)

    parsed = parse_nse_announcements_csv(path)

    assert len(parsed) == 1
    row = parsed.iloc[0]
    assert row["nse_ticker"] == "KPIL.NS"
    assert row["category"] == "Order Win"
    assert row["headline"] == "Award of Order / Receipt of Order"
    assert row["source"] == "NSE_ANNOUNCEMENTS"
