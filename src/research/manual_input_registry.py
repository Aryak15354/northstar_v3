"""Normalize weekly manual research inputs into canonical Northstar datasets."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def _snake_case(value: Any) -> str:
    text = _clean_text(value)
    text = text.replace("%", " pct ")
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_").lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except Exception:
        return str(path)


def _normalize_cells(values: Iterable[Any]) -> set[str]:
    return {_clean_text(v).upper() for v in values if _clean_text(v)}


def detect_header_row(raw: pd.DataFrame, required_columns: Iterable[str], *, scan_rows: int = 12) -> int:
    required = {_clean_text(c).upper() for c in required_columns if _clean_text(c)}
    best_row = 0
    best_score = -1
    for idx in range(min(len(raw), scan_rows)):
        row_tokens = _normalize_cells(raw.iloc[idx].tolist())
        score = len(required & row_tokens)
        if score > best_score:
            best_row = idx
            best_score = score
        if required and required.issubset(row_tokens):
            return idx
    return best_row


def _drop_empty_edges(df: pd.DataFrame) -> pd.DataFrame:
    out = df.dropna(axis=0, how="all").dropna(axis=1, how="all").copy()
    unnamed = [c for c in out.columns if _snake_case(c).startswith("unnamed")]
    if unnamed:
        out = out.drop(columns=unnamed, errors="ignore")
    return out


def load_excel_sheet(
    path: Path,
    sheet_name: str,
    *,
    required_columns: Iterable[str],
    filter_col: str | None = None,
    filter_regex: str | None = None,
) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    raw = raw.dropna(axis=1, how="all")
    header_row = detect_header_row(raw, required_columns)
    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    df = _drop_empty_edges(df)
    rename_map = {col: _snake_case(col) for col in df.columns}
    df = df.rename(columns=rename_map)
    df = df.loc[:, [c for c in df.columns if c]]
    if filter_col and filter_col in df.columns:
        values = df[filter_col].map(_clean_text)
        if filter_regex:
            mask = values.str.fullmatch(filter_regex, na=False)
        else:
            mask = values.astype(bool)
        df = df.loc[mask].copy()
    return df.reset_index(drop=True)


def _coerce_date_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.normalize()
    return out


def coerce_numeric_like_columns(
    df: pd.DataFrame,
    *,
    exclude: Iterable[str] = (),
    min_ratio: float = 0.75,
) -> pd.DataFrame:
    out = df.copy()
    exclude_set = {str(c) for c in exclude}
    for col in out.columns:
        if col in exclude_set:
            continue
        series = out[col]
        if pd.api.types.is_numeric_dtype(series):
            continue
        text = series.map(_clean_text)
        non_empty = text[text != ""]
        if non_empty.empty:
            continue
        numeric = pd.to_numeric(non_empty.str.replace(",", "", regex=False), errors="coerce")
        ratio = float(numeric.notna().mean())
        if ratio >= min_ratio:
            out[col] = pd.to_numeric(text.str.replace(",", "", regex=False), errors="coerce")
    return out


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    for para in root.findall(".//w:p", DOCX_NS):
        runs = [node.text for node in para.findall(".//w:t", DOCX_NS) if node.text]
        line = "".join(runs).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _write_frame_bundle(df: pd.DataFrame, stem: Path) -> dict[str, Any]:
    stem.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(stem.with_suffix(".csv"), index=False)
    df.to_parquet(stem.with_suffix(".parquet"), index=False)
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "csv_path": _rel(stem.with_suffix(".csv")),
        "parquet_path": _rel(stem.with_suffix(".parquet")),
    }


def _normalize_major_regimes(path: Path) -> dict[str, pd.DataFrame]:
    major = load_excel_sheet(
        path,
        "NSE_Regime_Events",
        required_columns=["EVENT_ID", "EVENT_NAME", "REGIME_TYPE", "START_DATE", "END_DATE"],
        filter_col="event_id",
        filter_regex=r"E\d{3}",
    )
    major = _coerce_date_columns(major, ["start_date", "end_date"])
    major = coerce_numeric_like_columns(
        major,
        exclude={
            "event_id",
            "event_name",
            "regime_type",
            "crisis_label",
            "trigger_category",
            "primary_trigger",
            "secondary_triggers",
            "sectors_worst_hit",
            "sectors_least_hit",
            "global_context",
            "key_macro_indicators",
            "observed_market_behavior",
            "regime_characteristics",
            "model_collapse_risk",
            "backtest_use_case",
            "data_quality_notes",
            "sources",
        },
    )

    codebook = load_excel_sheet(
        path,
        "Codebook",
        required_columns=["FIELD", "ALLOWED_VALUES / DESCRIPTION", "PYTHON_DTYPE", "NORTHSTAR_USE"],
        filter_col="field",
    )
    summary = load_excel_sheet(
        path,
        "Regime_Summary",
        required_columns=["REGIME_TYPE", "COUNT", "AVG_DRAWDOWN_PCT", "AVG_DURATION_DAYS"],
        filter_col="regime_type",
    )
    summary = coerce_numeric_like_columns(summary, exclude={"regime_type", "model_collapse_risk_dominant", "backtest_priority"})
    return {
        "major_events": major,
        "major_codebook": codebook,
        "major_summary": summary,
    }


def _normalize_subtle_periods(path: Path) -> dict[str, pd.DataFrame]:
    subtle = load_excel_sheet(
        path,
        "SUBTLE_Regime_Periods",
        required_columns=["PERIOD_ID", "PERIOD_NAME", "START_DATE", "END_DATE", "LINKED_MAJOR_EVENTS"],
        filter_col="period_id",
        filter_regex=r"S\d{3}",
    )
    subtle = _coerce_date_columns(subtle, ["start_date", "end_date"])
    subtle = coerce_numeric_like_columns(
        subtle,
        exclude={
            "period_id",
            "period_name",
            "primary_style",
            "breadth_trend",
            "index_trend",
            "liquidity_regime",
            "macro_signal",
            "flow_regime",
            "sector_leadership",
            "sector_laggards",
            "global_linkage",
            "behavioral_sentiment",
            "linked_major_events",
            "encoding_notes",
            "northstar_use_case",
        },
    )

    codebook = load_excel_sheet(
        path,
        "Codebook",
        required_columns=["FIELD", "ALLOWED_VALUES / DESCRIPTION", "PYTHON_DTYPE", "NORTHSTAR_USE"],
        filter_col="field",
    )
    timeline = load_excel_sheet(
        path,
        "Period_Timeline",
        required_columns=["ID", "NAME", "START", "END", "TYPE"],
        filter_col="id",
        filter_regex=r"[ES]\d{3}",
    )
    timeline = _coerce_date_columns(timeline, ["start", "end"])
    timeline = coerce_numeric_like_columns(timeline, exclude={"id", "name", "type", "series", "factor_signal"})
    ml_guide = load_excel_sheet(
        path,
        "ML_Feature_Guide",
        required_columns=["FEATURE_CATEGORY", "FEATURE_NAME", "ENCODING", "DERIVATION / NOTES"],
        filter_col="feature_name",
    )
    return {
        "subtle_periods": subtle,
        "subtle_codebook": codebook,
        "timeline": timeline,
        "ml_feature_guide": ml_guide,
    }


def _rename_universe_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "Company Name": "company_name",
        "NSE Symbol": "symbol",
        "Symbol": "symbol",
        "ISIN": "isin",
        "ISIN Code": "isin",
        "Industry": "broad_sector",
        "NIFTY500 Broad Sector": "broad_sector",
        "Subsector": "subsector",
        "HQ City": "hq_city",
        "Conglomerate / Group": "conglomerate_group",
        "Intl Brand / MNC": "international_brand_mnc_subsidiary",
        "International Brand / MNC Subsidiary": "international_brand_mnc_subsidiary",
        "Commodity Sensitivities": "commodity_sensitivities",
        "Sector & Macro Sensitivities": "sector_macro_sensitivities",
        "Key Interconnections & Peers": "key_interconnections_peers",
        "Data Enrichment Status": "data_enrichment_status",
    }
    out = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}).copy()
    for col in out.columns:
        if out[col].dtype == object or str(out[col].dtype).startswith("string"):
            out[col] = out[col].map(_clean_text)
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].str.upper()
        out["ticker"] = out["symbol"].where(out["symbol"] == "", out["symbol"] + ".NS")
    if "series" not in out.columns:
        out["series"] = "EQ"
    return out


def merge_universe_sources(csv_df: pd.DataFrame, workbook_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    csv_norm = _rename_universe_columns(csv_df)
    workbook_norm = _rename_universe_columns(workbook_df)
    csv_norm["source_csv"] = True
    workbook_norm["source_workbook"] = True
    merged = workbook_norm.merge(csv_norm, on="symbol", how="outer", suffixes=("_workbook", "_csv"))

    def pick(column: str, suffix: str) -> pd.Series:
        direct = merged.get(column)
        if direct is not None:
            return direct
        with_suffix = merged.get(f"{column}_{suffix}")
        if with_suffix is not None:
            return with_suffix
        return pd.Series("", index=merged.index, dtype="object")

    out = pd.DataFrame()
    out["symbol"] = merged.get("symbol", "").map(_clean_text).str.upper()
    for col in [
        "company_name",
        "isin",
        "broad_sector",
        "subsector",
        "hq_city",
        "conglomerate_group",
        "international_brand_mnc_subsidiary",
        "commodity_sensitivities",
        "sector_macro_sensitivities",
        "key_interconnections_peers",
        "data_enrichment_status",
        "series",
        "ticker",
    ]:
        left = pick(col, "csv")
        right = pick(col, "workbook")
        out[col] = left.where(left.map(_clean_text) != "", right)
        out[col] = out[col].map(_clean_text)

    out["ticker"] = out["ticker"].where(out["ticker"] != "", out["symbol"].where(out["symbol"] == "", out["symbol"] + ".NS"))
    out["series"] = out["series"].where(out["series"] != "", "EQ")
    out = out[out["symbol"] != ""].copy()
    out = out.sort_values("symbol", kind="mergesort").drop_duplicates("symbol", keep="last").reset_index(drop=True)

    workbook_symbols = set(workbook_norm["symbol"].dropna().astype(str))
    csv_symbols = set(csv_norm["symbol"].dropna().astype(str))
    comparison = {
        "rows_merged": int(len(out)),
        "rows_workbook": int(len(workbook_norm)),
        "rows_csv": int(len(csv_norm)),
        "workbook_only_symbols": sorted(workbook_symbols - csv_symbols),
        "csv_only_symbols": sorted(csv_symbols - workbook_symbols),
    }
    return out, comparison


def _prepare_auxiliary_sheet(
    path: Path,
    sheet_name: str,
    *,
    required_columns: Iterable[str],
    filter_column: str | None = None,
) -> pd.DataFrame:
    df = load_excel_sheet(path, sheet_name, required_columns=required_columns, filter_col=filter_column)
    return coerce_numeric_like_columns(df, exclude={filter_column} if filter_column else ())


def build_legacy_universe(universe_df: pd.DataFrame) -> pd.DataFrame:
    legacy = pd.DataFrame(
        {
            "Company Name": universe_df["company_name"],
            "Industry": universe_df["broad_sector"],
            "Symbol": universe_df["symbol"],
            "Series": universe_df["series"].where(universe_df["series"] != "", "EQ"),
            "ISIN Code": universe_df["isin"],
            "Subsector": universe_df.get("subsector", ""),
            "HQ City": universe_df.get("hq_city", ""),
            "Conglomerate / Group": universe_df.get("conglomerate_group", ""),
            "International Brand / MNC Subsidiary": universe_df.get("international_brand_mnc_subsidiary", ""),
            "Commodity Sensitivities": universe_df.get("commodity_sensitivities", ""),
            "Sector & Macro Sensitivities": universe_df.get("sector_macro_sensitivities", ""),
            "Key Interconnections & Peers": universe_df.get("key_interconnections_peers", ""),
            "Data Enrichment Status": universe_df.get("data_enrichment_status", ""),
        }
    )
    return legacy.sort_values("Symbol", kind="mergesort").reset_index(drop=True)


def build_news_master(legacy_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "name": legacy_df["Company Name"],
            "industry": legacy_df["Industry"],
            "symbol": legacy_df["Symbol"],
            "series": legacy_df["Series"],
            "isin_code": legacy_df["ISIN Code"],
        }
    )


def prepare_research_inputs(
    *,
    major_regime_xlsx: Path,
    subtle_regime_xlsx: Path,
    universe_master_xlsx: Path,
    universe_master_csv: Path,
    weekly_sprint_docx: Path,
    research_plan_docx: Path,
    raw_destination_root: Path,
    canonical_reference_root: Path,
    legacy_universe_path: Path,
    news_master_path: Path,
) -> dict[str, Any]:
    raw_destination_root.mkdir(parents=True, exist_ok=True)
    canonical_reference_root.mkdir(parents=True, exist_ok=True)

    sources = {
        "major_regime_xlsx": major_regime_xlsx,
        "subtle_regime_xlsx": subtle_regime_xlsx,
        "universe_master_xlsx": universe_master_xlsx,
        "universe_master_csv": universe_master_csv,
        "weekly_sprint_docx": weekly_sprint_docx,
        "research_plan_docx": research_plan_docx,
    }
    source_manifest: dict[str, Any] = {}
    for key, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(f"missing_source:{src}")
        dest = raw_destination_root / src.name
        shutil.copy2(src, dest)
        source_manifest[key] = {
            "source_path": str(src),
            "stored_path": _rel(dest),
            "sha256": _sha256(dest),
            "size_bytes": int(dest.stat().st_size),
        }

    sprint_text = extract_docx_text(raw_destination_root / weekly_sprint_docx.name)
    plan_text = extract_docx_text(raw_destination_root / research_plan_docx.name)
    sprint_text_path = raw_destination_root / f"{weekly_sprint_docx.stem}.txt"
    plan_text_path = raw_destination_root / f"{research_plan_docx.stem}.txt"
    sprint_text_path.write_text(sprint_text, encoding="utf-8")
    plan_text_path.write_text(plan_text, encoding="utf-8")

    major_outputs = _normalize_major_regimes(major_regime_xlsx)
    subtle_outputs = _normalize_subtle_periods(subtle_regime_xlsx)

    workbook_master = pd.read_excel(universe_master_xlsx, sheet_name="🏢 Universe Master")
    csv_master = pd.read_csv(universe_master_csv, low_memory=False)
    enriched_universe, universe_comparison = merge_universe_sources(csv_master, workbook_master)

    sector_breakdown = _prepare_auxiliary_sheet(
        universe_master_xlsx,
        "🏭 Sector Breakdown",
        required_columns=["Broad Sector", "# Companies", "% of Universe"],
        filter_column="broad_sector",
    )
    conglomerates_map = _prepare_auxiliary_sheet(
        universe_master_xlsx,
        "🏛 Conglomerates Map",
        required_columns=["Conglomerate / Group", "Company Name", "NSE Symbol"],
        filter_column="company_name",
    )
    mnc_brands = _prepare_auxiliary_sheet(
        universe_master_xlsx,
        "🌍 MNC & Intl Brands",
        required_columns=["Company Name", "NSE Symbol", "Conglomerate / Parent"],
        filter_column="company_name",
    )
    commodity_lens = _prepare_auxiliary_sheet(
        universe_master_xlsx,
        "⚡ Commodity Lens",
        required_columns=["Commodity / Input", "Listed Companies with Direct Exposure"],
        filter_column="commodity_input",
    )
    interconnections = _prepare_auxiliary_sheet(
        universe_master_xlsx,
        "🔗 Interconnections",
        required_columns=["Interconnection Theme", "Details of Key Linkages (Listed Companies)"],
        filter_column="interconnection_theme",
    )

    outputs: dict[str, Any] = {}
    outputs["major_events"] = _write_frame_bundle(
        major_outputs["major_events"],
        canonical_reference_root / "regimes/nse_regime_events_major",
    )
    outputs["major_codebook"] = _write_frame_bundle(
        major_outputs["major_codebook"],
        canonical_reference_root / "regimes/nse_regime_events_codebook",
    )
    outputs["major_summary"] = _write_frame_bundle(
        major_outputs["major_summary"],
        canonical_reference_root / "regimes/nse_regime_summary",
    )
    outputs["subtle_periods"] = _write_frame_bundle(
        subtle_outputs["subtle_periods"],
        canonical_reference_root / "regimes/nse_regime_periods_subtle",
    )
    outputs["subtle_codebook"] = _write_frame_bundle(
        subtle_outputs["subtle_codebook"],
        canonical_reference_root / "regimes/nse_regime_periods_codebook",
    )
    outputs["timeline"] = _write_frame_bundle(
        subtle_outputs["timeline"],
        canonical_reference_root / "regimes/nse_regime_timeline",
    )
    outputs["ml_feature_guide"] = _write_frame_bundle(
        subtle_outputs["ml_feature_guide"],
        canonical_reference_root / "regimes/nse_regime_ml_feature_guide",
    )
    outputs["universe_enriched"] = _write_frame_bundle(
        enriched_universe,
        canonical_reference_root / "universe/nifty500_universe_enriched",
    )
    outputs["sector_breakdown"] = _write_frame_bundle(
        sector_breakdown,
        canonical_reference_root / "universe/nifty500_sector_breakdown",
    )
    outputs["conglomerates_map"] = _write_frame_bundle(
        conglomerates_map,
        canonical_reference_root / "universe/nifty500_conglomerates_map",
    )
    outputs["mnc_brands"] = _write_frame_bundle(
        mnc_brands,
        canonical_reference_root / "universe/nifty500_mnc_brands",
    )
    outputs["commodity_lens"] = _write_frame_bundle(
        commodity_lens,
        canonical_reference_root / "universe/nifty500_commodity_lens",
    )
    outputs["interconnections"] = _write_frame_bundle(
        interconnections,
        canonical_reference_root / "universe/nifty500_interconnections",
    )

    legacy_universe = build_legacy_universe(enriched_universe)
    legacy_universe_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_universe.to_csv(legacy_universe_path, index=False)

    news_master = build_news_master(legacy_universe)
    news_master_path.parent.mkdir(parents=True, exist_ok=True)
    news_master.to_csv(news_master_path, index=False)

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "raw_destination_root": _rel(raw_destination_root),
        "canonical_reference_root": _rel(canonical_reference_root),
        "sources": source_manifest,
        "documents": {
            "weekly_sprint_text_path": _rel(sprint_text_path),
            "research_plan_text_path": _rel(plan_text_path),
        },
        "outputs": outputs,
        "legacy_universe_path": _rel(legacy_universe_path),
        "news_master_path": _rel(news_master_path),
        "universe_source_comparison": universe_comparison,
    }

    source_manifest_path = raw_destination_root / "source_manifest.json"
    source_manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    canonical_manifest_path = canonical_reference_root / "research_inputs_manifest.json"
    canonical_manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest
