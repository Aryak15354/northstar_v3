from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from scripts.kaggle.augment_feature_export_dataset import (
    BseClient,
    _extract_pdf_text,
    _bse_document_score,
    _carry_forward_export_support_files,
    _derive_eq_family,
    _derive_revision_family,
    _extract_cg_metrics,
    _extract_fs_metrics,
    _extract_it_metrics,
    _merge_asof_by_ticker,
    _merge_asof_macro,
    _parse_cga_detail_table,
    _pct_change_sparse_observed,
    _repair_quality_proxy_families,
    _repair_revision_factor_family,
    _suppress_middle_outliers,
    compact_bse_cache,
)


def test_derive_eq_family_uses_cash_conversion_fallback_and_cross_sectional_outputs() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05", "2024-01-05", "2024-01-12", "2024-01-12"]),
            "ticker": ["AAA.NS", "BBB.NS", "AAA.NS", "BBB.NS"],
            "net_income": [10.0, 5.0, None, None],
            "operating_cash_flow": [None, None, None, None],
            "cash_conversion": [2.5, 1.2, 2.7, 1.0],
        }
    )

    derived = _derive_eq_family(frame)

    assert derived["earnings_quality_ratio"].notna().all()
    assert derived["earnings_quality_ratio_cs_z"].notna().all()
    assert derived["earnings_quality_ratio_cs_rank"].notna().all()
    assert float(derived.loc[derived["ticker"] == "AAA.NS", "earnings_quality_ratio"].iloc[0]) > float(
        derived.loc[derived["ticker"] == "BBB.NS", "earnings_quality_ratio"].iloc[0]
    )


def test_extract_it_metrics_reads_attrition_headcount_and_tcv() -> None:
    text = """
    Investment in talent continues. Net headcount increased by 5,000 to 337,000 employees.
    LTM voluntary attrition rate stood at 12.8%.
    Large deal TCV was robust at $4.8 bn in Q3 with 57% net new.
    """

    metrics = _extract_it_metrics(text)

    assert metrics["headcount_level"] == 337000.0
    assert metrics["attrition_rate"] == 12.8
    assert metrics["deal_tcv_level_usd_mn"] == 4800.0


def test_derive_eq_family_falls_back_to_valuation_proxy_when_raw_inputs_are_dead() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05", "2024-01-05", "2024-01-12", "2024-01-12"]),
            "ticker": ["AAA.NS", "BBB.NS", "AAA.NS", "BBB.NS"],
            "net_income": [None, None, None, None],
            "operating_cash_flow": [None, None, None, None],
            "cash_conversion": [None, None, None, None],
            "val_earnings_quality_score_zscore": [0.9, -0.2, 0.6, -0.4],
        }
    )

    derived = _derive_eq_family(frame)

    assert derived["earnings_quality_ratio"].nunique(dropna=True) > 1
    assert derived["earnings_quality_ratio_cs_z"].nunique(dropna=True) > 1
    assert derived["earnings_quality_ratio_cs_rank"].abs().max() > 0.0


def test_repair_quality_proxy_families_repairs_dead_accrual_family_from_live_proxy() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05", "2024-01-05", "2024-01-12", "2024-01-12"]),
            "ticker": ["AAA.NS", "BBB.NS", "AAA.NS", "BBB.NS"],
            "accruals_ratio": [0.0, 0.0, 0.0, 0.0],
            "accruals_ratio_cs_z": [0.0, 0.0, 0.0, 0.0],
            "accruals_ratio_cs_rank": [0.0, 0.0, 0.0, 0.0],
            "val_accruals_ratio_zscore": [-0.4, 0.3, -0.2, 0.5],
        }
    )

    repaired = _repair_quality_proxy_families(frame)

    assert repaired["accruals_ratio"].nunique(dropna=True) > 1
    assert repaired["accruals_ratio_cs_z"].nunique(dropna=True) > 1
    assert repaired["accruals_ratio_cs_rank"].abs().max() > 0.0


def test_derive_revision_family_recovers_compendium_revision_columns() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2024-01-05",
                    "2024-01-12",
                    "2024-01-19",
                    "2024-01-26",
                    "2024-02-02",
                    "2024-02-09",
                    "2024-02-16",
                    "2024-02-23",
                ]
            ),
            "ticker": ["AAA.NS"] * 8,
            "eps_sue": [0.1, 0.1, 0.2, 0.2, 0.6, 0.6, 1.1, 1.1],
            "rev_sue": [0.05, 0.05, 0.1, 0.1, 0.3, 0.3, 0.55, 0.55],
        }
    )

    derived = _derive_revision_family(frame)

    assert derived["eps_revision_accel"].notna().sum() > 0
    assert derived["combined_revision_score"].notna().sum() > 0
    assert derived["combined_revision_score_cs_z"].notna().sum() > 0
    assert derived["combined_revision_score_cs_rank"].notna().sum() > 0


def test_repair_revision_factor_family_backfills_missing_revision_columns() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2024-01-05",
                    "2024-01-12",
                    "2024-01-19",
                    "2024-01-26",
                    "2024-02-02",
                    "2024-02-09",
                    "2024-02-16",
                    "2024-02-23",
                ]
            ),
            "ticker": ["AAA.NS"] * 8,
            "eps_sue": [0.1, 0.1, 0.2, 0.2, 0.6, 0.6, 1.1, 1.1],
            "rev_sue": [0.05, 0.05, 0.1, 0.1, 0.3, 0.3, 0.55, 0.55],
            "eps_revision_accel": [0.0] * 8,
            "combined_revision_score": [0.0] * 8,
            "combined_revision_score_cs_z": [0.0] * 8,
            "combined_revision_score_cs_rank": [0.0] * 8,
        }
    )

    repaired = _repair_revision_factor_family(frame)

    assert repaired["eps_revision_accel"].notna().sum() > 0
    assert repaired["combined_revision_score"].notna().sum() > 0
    assert repaired["combined_revision_score_cs_z"].notna().sum() > 0
    assert repaired["combined_revision_score_cs_rank"].notna().sum() > 0


def test_extract_cg_metrics_reads_order_book_value() -> None:
    text = """
    Q3 - All Round Progress
    Order Inflow 17% y-o-y
    Order Backlog ₹ 7,332 crore
    Revenue ₹ 714 bn
    """

    metrics = _extract_cg_metrics(text)

    assert metrics["order_book_level_inr_cr"] == 7_332.0


def test_extract_it_metrics_prefers_total_headcount_over_increment() -> None:
    text = """
    Headcount grew by over 5,000 sequentially we are now over 323,000 employees worldwide.
    Attrition remains low at 13.7%.
    """

    metrics = _extract_it_metrics(text)

    assert metrics["headcount_level"] == 323000.0


def test_extract_fs_metrics_reads_bank_presentation_rows() -> None:
    text = """
    Bank Highlights
    4.54% NIM
    41.3% CASA Ratio
    0.31% Net NPA
    Asset Quality
    GNPA (%) 1.30%
    NNPA (%) 0.31%
    PCR (%) 76%
    Bank's Financial Health Indicators
    CD Ratio 88.6%
    Balance Sheet
    Net Advances 480,673 413,839 462,688 16% 4%
    Deposits 542,638 473,497 528,776
    """

    metrics = _extract_fs_metrics(text)

    assert metrics["nim_level"] == 4.54
    assert metrics["casa_ratio"] == 41.3
    assert metrics["npa_net_4q"] == 0.31
    assert metrics["gnpa_level"] == 1.30
    assert metrics["provision_coverage"] == 76.0
    assert metrics["credit_deposit_ratio"] == 88.6
    assert metrics["loan_growth_yoy"] == 16.0
    assert metrics["advances_level"] == 480673.0
    assert metrics["deposits_level"] == 542638.0


def test_parse_cga_detail_table_extracts_monthly_and_ytd_columns() -> None:
    html = """
    <table>
      <tr><th>Months</th><th>2025-26</th><th>2025-26</th><th>2024-25</th><th>2024-25</th></tr>
      <tr><th>Months</th><th>Monthly</th><th>Year to date</th><th>Monthly</th><th>Year to date</th></tr>
      <tr><td>April</td><td>256829</td><td>256829</td><td>212293</td><td>212293</td></tr>
      <tr><td>May</td><td>450910</td><td>707739</td><td>358465</td><td>570758</td></tr>
      <tr><td>June</td><td>205638</td><td>913377</td><td>258919</td><td>829677</td></tr>
    </table>
    """

    parsed = _parse_cga_detail_table(html)

    assert parsed["month_name"].tolist() == ["April", "May", "June"]
    assert parsed["current_monthly"].tolist() == [256829.0, 450910.0, 205638.0]
    assert parsed["current_ytd"].tolist() == [256829.0, 707739.0, 913377.0]


def test_merge_asof_by_ticker_overlays_existing_column_without_suffix_drift() -> None:
    features = pd.DataFrame(
        {
            "ticker": ["AAA.NS", "AAA.NS"],
            "date": pd.to_datetime(["2024-01-05", "2024-01-12"]),
            "nim_4q_trend": [1.0, 1.0],
        }
    )
    events = pd.DataFrame(
        {
            "ticker": ["AAA.NS"],
            "date": pd.to_datetime(["2024-01-10"]),
            "nim_4q_trend": [2.5],
        }
    )

    merged = _merge_asof_by_ticker(features, events, ["nim_4q_trend"])

    assert "nim_4q_trend__incoming" not in merged.columns
    assert merged["nim_4q_trend"].tolist() == [1.0, 2.5]


def test_merge_asof_macro_overlays_existing_macro_column_without_suffix_drift() -> None:
    features = pd.DataFrame(
        {
            "ticker": ["AAA.NS", "AAA.NS"],
            "date": pd.to_datetime(["2024-01-05", "2024-01-12"]),
            "infra_spending_index": [100.0, 100.0],
        }
    )
    macro = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-10"]),
            "infra_spending_index": [104.0],
        }
    )

    merged = _merge_asof_macro(features, macro, ["infra_spending_index"])

    assert "infra_spending_index__incoming" not in merged.columns
    assert merged["infra_spending_index"].tolist() == [100.0, 104.0]


def test_merge_asof_macro_respects_tolerance_for_stale_points() -> None:
    features = pd.DataFrame(
        {
            "ticker": ["AAA.NS", "AAA.NS"],
            "date": pd.to_datetime(["2024-01-05", "2025-06-01"]),
        }
    )
    macro = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"]),
            "power_sector_capex": [123.0],
        }
    )

    merged = _merge_asof_macro(features, macro, ["power_sector_capex"], tolerance=pd.Timedelta(days=120))

    assert merged["power_sector_capex"].iloc[0] == 123.0
    assert pd.isna(merged["power_sector_capex"].iloc[1])


def test_bse_document_score_prefers_presentation_over_intimation() -> None:
    presentation = {
        "NEWSSUB": "Q4 FY25 Investor Presentation",
        "ATTACHMENTNAME": "InvestorPresentation.pdf",
    }
    intimation = {
        "NEWSSUB": "Analyst / Investor Meet - Intimation",
        "ATTACHMENTNAME": "Notice.pdf",
    }

    assert _bse_document_score(presentation) > _bse_document_score(intimation)


def test_pct_change_sparse_observed_uses_previous_non_null_level() -> None:
    series = pd.Series([100.0, None, 110.0, None, 121.0])

    changes = _pct_change_sparse_observed(series)

    assert pd.isna(changes.iloc[0])
    assert pd.isna(changes.iloc[1])
    assert round(float(changes.iloc[2]), 6) == 0.1
    assert pd.isna(changes.iloc[3])
    assert round(float(changes.iloc[4]), 6) == 0.1


def test_suppress_middle_outliers_drops_one_off_mid_series_spike() -> None:
    series = pd.Series([9500.0, 1766.0, 9400.0])

    filtered = _suppress_middle_outliers(series)

    assert filtered.iloc[0] == 9500.0
    assert pd.isna(filtered.iloc[1])
    assert filtered.iloc[2] == 9400.0


def test_extract_pdf_text_falls_back_when_fitz_fails(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fitz(_payload: bytes) -> str:
        calls.append("fitz")
        raise RuntimeError("bad_pdf")

    def fake_pypdf(_payload: bytes) -> str:
        calls.append("pypdf")
        return "fallback text"

    monkeypatch.setattr(
        "scripts.kaggle.augment_feature_export_dataset._extract_pdf_text_with_fitz",
        fake_fitz,
    )
    monkeypatch.setattr(
        "scripts.kaggle.augment_feature_export_dataset._extract_pdf_text_with_pypdf",
        fake_pypdf,
    )

    text = _extract_pdf_text(b"%PDF-1.4", prefer_pypdf=False)

    assert text == "fallback text"
    assert calls == ["fitz", "pypdf"]


def test_compact_bse_cache_round_trips_loose_files(tmp_path: Path) -> None:
    cache_dir = tmp_path / "bse"
    attachments_dir = cache_dir / "attachments"
    text_dir = cache_dir / "attachment_text"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    announcement_name = "ann_500001_result_20240101_20240131_1.json"
    (cache_dir / announcement_name).write_text(json.dumps({"Table": [{"headline": "hello"}]}), encoding="utf-8")
    pdf_name = "Doc.pdf"
    pdf_payload = b"%PDF-1.4 compact-cache"
    (attachments_dir / pdf_name).write_bytes(pdf_payload)
    (text_dir / f"{pdf_name}.txt").write_text("cached text", encoding="utf-8")

    summary = compact_bse_cache(
        cache_dir,
        max_archive_raw_bytes=1024 * 1024,
        raw_cache_policy="all",
        delete_loose_files=True,
    )

    assert summary["announcement_files_compacted"] == 1
    assert summary["attachment_text_files_compacted"] == 1
    assert summary["attachment_pdf_files_compacted"] == 1
    assert not (cache_dir / announcement_name).exists()
    assert not (attachments_dir / pdf_name).exists()
    assert not (text_dir / f"{pdf_name}.txt").exists()

    client = BseClient(cache_dir, max_archive_raw_bytes=1024 * 1024, raw_cache_policy="all")
    rows = client.fetch_announcements(
        500001,
        "Result",
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-31"),
    )

    assert rows == [{"headline": "hello"}]
    assert client.attachment_bytes({"ATTACHMENTNAME": pdf_name}) == pdf_payload
    assert client.attachment_text({"ATTACHMENTNAME": pdf_name}) == "cached text"


def test_compact_bse_cache_lean_mode_drops_redundant_raw_pdfs(tmp_path: Path) -> None:
    cache_dir = tmp_path / "bse"
    attachments_dir = cache_dir / "attachments"
    text_dir = cache_dir / "attachment_text"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    pdf_name = "Doc.pdf"
    (attachments_dir / pdf_name).write_bytes(b"%PDF-1.4 compact-cache")
    (text_dir / f"{pdf_name}.txt").write_text("cached text", encoding="utf-8")

    summary = compact_bse_cache(
        cache_dir,
        max_archive_raw_bytes=1024 * 1024,
        raw_cache_policy="text_failures_only",
        delete_loose_files=True,
    )

    assert summary["attachment_pdf_files_compacted"] == 1
    assert summary["attachment_pdf_files_retained"] == 0
    assert not (cache_dir / "attachment_archives").exists()

    client = BseClient(cache_dir, max_archive_raw_bytes=1024 * 1024)
    assert client.attachment_text({"ATTACHMENTNAME": pdf_name}) == "cached text"


def test_compact_bse_cache_lean_mode_keeps_raw_when_text_is_empty(tmp_path: Path) -> None:
    cache_dir = tmp_path / "bse"
    attachments_dir = cache_dir / "attachments"
    text_dir = cache_dir / "attachment_text"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    pdf_name = "Unreadable.pdf"
    pdf_payload = b"%PDF-1.4 unreadable"
    (attachments_dir / pdf_name).write_bytes(pdf_payload)
    (text_dir / f"{pdf_name}.txt").write_text("", encoding="utf-8")

    summary = compact_bse_cache(
        cache_dir,
        max_archive_raw_bytes=1024 * 1024,
        raw_cache_policy="text_failures_only",
        delete_loose_files=True,
    )

    assert summary["attachment_pdf_files_compacted"] == 1
    assert summary["attachment_pdf_files_retained"] == 1

    client = BseClient(cache_dir, max_archive_raw_bytes=1024 * 1024)
    assert client.attachment_bytes({"ATTACHMENTNAME": pdf_name}) == pdf_payload


def test_carry_forward_export_support_files_rewrites_manifest_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "source_export"
    output_root = tmp_path / "augmented_export"
    source_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    (source_root / "northstar_walk_forward_splits.json").write_text(
        json.dumps(
            [
                {
                    "window_id": 1,
                    "train_start": "2024-01-05",
                    "train_end": "2024-06-28",
                    "test_start": "2024-07-05",
                    "test_end": "2024-09-27",
                }
            ]
        ),
        encoding="utf-8",
    )
    pd.DataFrame({"date": pd.to_datetime(["2024-01-05"]), "regime": ["R1"]}).to_parquet(
        source_root / "northstar_regime_labels.parquet", index=False
    )
    (source_root / "feature_unit_registry.json").write_text(json.dumps([{"feature": "x"}]), encoding="utf-8")
    (source_root / "plan_signal_audit.json").write_text(json.dumps({"blocking_signals": []}), encoding="utf-8")
    (source_root / "weekly_export_manifest.json").write_text(
        json.dumps(
            {
                "feature_count": 10,
                "features_rows": 2,
                "metadata_rows": 2,
                "ticker_count": 1,
                "date_min": "2024-01-05",
                "date_max": "2024-01-12",
                "n_windows": 1,
                "files": {
                    "features": str(source_root / "northstar_features.parquet"),
                    "metadata": str(source_root / "northstar_metadata.parquet"),
                    "splits": str(source_root / "northstar_walk_forward_splits.json"),
                    "regimes": str(source_root / "northstar_regime_labels.parquet"),
                },
            }
        ),
        encoding="utf-8",
    )
    (source_root / "merged_chunk_export_manifest.json").write_text(
        json.dumps(
            {
                "output_dir": str(source_root),
                "files": {
                    "features": str(source_root / "northstar_features.parquet"),
                    "metadata": str(source_root / "northstar_metadata.parquet"),
                    "splits": str(source_root / "northstar_walk_forward_splits.json"),
                    "regimes": str(source_root / "northstar_regime_labels.parquet"),
                },
            }
        ),
        encoding="utf-8",
    )

    merged = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05", "2024-01-12"]),
            "ticker": ["AAA.NS", "AAA.NS"],
            "target_weekly_return": [0.1, 0.2],
            "feature_x": [1.0, 2.0],
        }
    )
    metadata = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05", "2024-01-12"]),
            "ticker": ["AAA.NS", "AAA.NS"],
        }
    )
    merged.to_parquet(output_root / "northstar_features.parquet", index=False)
    metadata.to_parquet(output_root / "northstar_metadata.parquet", index=False)

    copied = _carry_forward_export_support_files(
        source_export_root=source_root,
        output_root=output_root,
        merged=merged,
        metadata=metadata,
    )

    assert "northstar_walk_forward_splits.json" in copied
    weekly_manifest = json.loads((output_root / "weekly_export_manifest.json").read_text(encoding="utf-8"))
    assert weekly_manifest["files"]["features"] == str(output_root / "northstar_features.parquet")
    assert weekly_manifest["files"]["regimes"] == str(output_root / "northstar_regime_labels.parquet")
    assert weekly_manifest["features_rows"] == 2
