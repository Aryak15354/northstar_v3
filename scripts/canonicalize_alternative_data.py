#!/usr/bin/env python3
"""Canonicalize alternative datasets onto the live NSE-first surface."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_corporate_filings_processors import (  # noqa: E402
    ANNOUNCEMENTS_PROCESSED_PATH,
    PLEDGE_PROCESSED_PATH,
    PROCESSED_DIR,
    RAW_ANNOUNCEMENTS_DIR,
    RAW_PLEDGE_DIR,
    _normalize_company_name,
    parse_nse_announcements_csv,
    parse_nse_promoter_pledge_csv,
    resolve_company_ticker,
)
from scripts.scrape_nse_credit_ratings_robust import parse_credit_ratings_csv  # noqa: E402


RAW_BULK_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
RAW_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
STATUS_PATH = PROCESSED_DIR / "alternative_canonicalization_status.json"


def _read_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def _write_outputs(
    df: pd.DataFrame,
    *,
    csv_path: Path,
    parquet_path: Path | None = None,
    alias_csv_paths: Iterable[Path] = (),
    alias_parquet_paths: Iterable[Path] = (),
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    if parquet_path is not None:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)
    for alias in alias_csv_paths:
        alias.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(alias, index=False)
    for alias in alias_parquet_paths:
        alias.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(alias, index=False)


def _normalize_ticker(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text or text in {"NAN", "NONE"}:
        return ""
    if text.endswith(".NS"):
        return text
    if "." in text:
        text = text.split(".", 1)[0]
    return f"{text}.NS"


def _load_existing_processed(*candidates: Path) -> pd.DataFrame:
    for candidate in candidates:
        frame = _read_frame(candidate)
        if not frame.empty:
            return frame
    return pd.DataFrame()


def _col(frame: pd.DataFrame, name: str, default="") -> pd.Series:
    if name in frame.columns:
        return frame[name]
    if isinstance(default, pd.Series):
        return default.reindex(frame.index)
    return pd.Series([default] * len(frame), index=frame.index)


def _parse_mixed_datetime(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().any():
        fallback = pd.to_datetime(values, errors="coerce", dayfirst=True)
        parsed = parsed.fillna(fallback)
    future_cutoff = pd.Timestamp.now().normalize() + pd.Timedelta(days=14)
    as_text = values.astype(str).str.strip()
    iso_mask = as_text.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False) & parsed.gt(future_cutoff)
    if bool(iso_mask.any()):
        swapped = as_text.loc[iso_mask].str.replace(
            r"^(\d{4})-(\d{2})-(\d{2})$",
            r"\1-\3-\2",
            regex=True,
        )
        reparsed = pd.to_datetime(swapped, errors="coerce")
        parsed.loc[iso_mask] = reparsed
    return parsed


def _standardize_bulk_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "company_name",
                "client_name",
                "deal_type",
                "quantity",
                "price",
                "remarks",
                "nse_ticker",
                "source",
            ]
        )

    out = frame.copy()
    out.columns = [str(col).strip() for col in out.columns]
    rename_map = {
        "Date": "date",
        "SYMBOL": "symbol",
        "Symbol": "symbol",
        "Security Name": "company_name",
        "SECURITY NAME": "company_name",
        "scrip_name": "company_name",
        "Client Name": "client_name",
        "CLIENT NAME": "client_name",
        "Buy / Sell": "deal_type",
        "BUY / SELL": "deal_type",
        "Quantity Traded": "quantity",
        "QUANTITY TRADED": "quantity",
        "Trade Price / Wght. Avg. Price": "price",
        "TRADE PRICE / WGHT. AVG. PRICE": "price",
        "Remarks": "remarks",
    }
    out = out.rename(columns=rename_map)
    out["date"] = _parse_mixed_datetime(_col(out, "date"))
    out["symbol"] = _col(out, "symbol").astype(str).str.strip().str.upper()
    out["company_name"] = _col(out, "company_name").astype(str).str.strip()
    out["client_name"] = _col(out, "client_name").astype(str).str.strip()
    out["deal_type"] = _col(out, "deal_type").astype(str).str.strip().str.upper()
    out["quantity"] = pd.to_numeric(
        _col(out, "quantity").astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    out["price"] = pd.to_numeric(_col(out, "price"), errors="coerce")
    out["remarks"] = _col(out, "remarks").astype(str).str.strip()
    if "nse_ticker" not in out.columns:
        out["nse_ticker"] = out["symbol"].map(_normalize_ticker)
    else:
        out["nse_ticker"] = out["nse_ticker"].map(_normalize_ticker)
    out["source"] = _col(out, "source", "NSE_MANUAL_DOWNLOAD").fillna("NSE_MANUAL_DOWNLOAD").astype(str)

    keep = [
        "date",
        "symbol",
        "company_name",
        "client_name",
        "deal_type",
        "quantity",
        "price",
        "remarks",
        "nse_ticker",
        "source",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = pd.NA
    out = out[keep].copy()
    out = out.dropna(subset=["date", "symbol"])
    out = out[out["symbol"].astype(str).str.len() > 0]
    return out.reset_index(drop=True)


def canonicalize_bulk_deals() -> dict[str, object]:
    frames: list[pd.DataFrame] = []
    existing = _load_existing_processed(
        PROCESSED_DIR / "bulk_deals_nse_all.csv",
        PROCESSED_DIR / "bulk_deals_nse_all.parquet",
        PROCESSED_DIR / "bulk_deals_all.csv",
    )
    if not existing.empty:
        frames.append(_standardize_bulk_frame(existing))

    for path in sorted(RAW_BULK_DIR.glob("*.csv")):
        if path.name.startswith(".") or path.parent.name.startswith("_"):
            continue
        frame = _standardize_bulk_frame(_read_frame(path))
        if not frame.empty:
            frames.append(frame)

    if not frames:
        empty = _standardize_bulk_frame(pd.DataFrame())
        _write_outputs(
            empty,
            csv_path=PROCESSED_DIR / "bulk_deals_nse_all.csv",
            parquet_path=PROCESSED_DIR / "bulk_deals_nse_all.parquet",
            alias_csv_paths=[PROCESSED_DIR / "bulk_deals_all.csv"],
            alias_parquet_paths=[PROCESSED_DIR / "bulk_deals_all.parquet"],
        )
        return {"rows": 0, "latest_date": None}

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date", "symbol"])
    combined = combined.sort_values(["date", "symbol", "client_name", "deal_type"], kind="mergesort")
    combined = combined.drop_duplicates(
        subset=["date", "symbol", "client_name", "deal_type", "quantity", "price"],
        keep="last",
    ).reset_index(drop=True)
    combined = combined.sort_values("date", ascending=False, kind="mergesort").reset_index(drop=True)

    _write_outputs(
        combined,
        csv_path=PROCESSED_DIR / "bulk_deals_nse_all.csv",
        parquet_path=PROCESSED_DIR / "bulk_deals_nse_all.parquet",
        alias_csv_paths=[PROCESSED_DIR / "bulk_deals_all.csv"],
        alias_parquet_paths=[PROCESSED_DIR / "bulk_deals_all.parquet"],
    )
    recent = combined[combined["date"] >= (pd.Timestamp.now().normalize() - pd.Timedelta(days=90))].copy()
    recent.to_csv(PROCESSED_DIR / "bulk_deals_nse_recent.csv", index=False)
    latest = pd.to_datetime(combined["date"], errors="coerce").max()
    return {"rows": int(len(combined)), "latest_date": latest.isoformat() if pd.notna(latest) else None}


def _garbage_rating_company(value: object) -> bool:
    text = str(value or "").strip().upper()
    if not text or text in {"NAN", "NONE"}:
        return True
    if text.startswith(","):
        return True
    if text in {
        "SUBJECT",
        "CREATE DATE/ TIME",
        "BROADCAST DATE/ TIME",
        "VERIFIED BY",
        "LOCKED BY",
        "STATUS",
        "PLACE",
        "DATE",
        "XBRL FILE NAME",
    }:
        return True
    return False


def _standardize_ratings_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "company_name",
                "nse_ticker",
                "ticker_match_status",
                "agency",
                "new_rating",
                "action_type",
                "outlook",
                "isin",
                "instrument_type",
                "source",
                "processed_date",
            ]
        )

    out = frame.copy()
    out.columns = [str(col).strip() for col in out.columns]
    rename_map = {
        "rating": "new_rating",
        "rating_action": "action_type",
        "Ticker": "nse_ticker",
    }
    out = out.rename(columns=rename_map)

    if "date" not in out.columns or _parse_mixed_datetime(_col(out, "date")).isna().all():
        if "DATE OF CREDIT RATING" in out.columns:
            out["date"] = out["DATE OF CREDIT RATING"]
    out["date"] = _parse_mixed_datetime(_col(out, "date"))

    if "nse_ticker" not in out.columns:
        out["nse_ticker"] = ""
    out["nse_ticker"] = out["nse_ticker"].map(_normalize_ticker)
    out["company_name"] = _col(out, "company_name").astype(str).str.strip()
    out["agency"] = _col(out, "agency").astype(str).str.strip()
    out["new_rating"] = _col(out, "new_rating", _col(out, "rating", "")).astype(str).str.strip()
    out["action_type"] = _col(out, "action_type", _col(out, "rating_action", "")).astype(str).str.strip()
    out["outlook"] = _col(out, "outlook").astype(str).str.strip()
    out["isin"] = _col(out, "isin", _col(out, "ISIN", "")).astype(str).str.strip()
    out["instrument_type"] = _col(out, "instrument_type", "Debt").fillna("Debt").astype(str)
    out["source"] = _col(out, "source", "NSE_CREDIT_RATINGS").fillna("NSE_CREDIT_RATINGS").astype(str)
    out["processed_date"] = pd.to_datetime(_col(out, "processed_date"), errors="coerce")

    missing_ticker_mask = out["nse_ticker"].eq("")
    if bool(missing_ticker_mask.any()):
        resolutions = out.loc[missing_ticker_mask, "company_name"].apply(resolve_company_ticker)
        out.loc[missing_ticker_mask, "nse_ticker"] = resolutions.map(lambda item: _normalize_ticker(item[0]))
        out.loc[missing_ticker_mask, "ticker_match_status"] = resolutions.map(lambda item: item[1])
    else:
        out["ticker_match_status"] = _col(out, "ticker_match_status", "exact")

    keep = [
        "date",
        "company_name",
        "nse_ticker",
        "ticker_match_status",
        "agency",
        "new_rating",
        "action_type",
        "outlook",
        "isin",
        "instrument_type",
        "source",
        "processed_date",
    ]
    for column in keep:
        if column not in out.columns:
            out[column] = pd.NA
    out = out[keep].copy()
    out = out.dropna(subset=["date"]).copy()
    if out.empty:
        return out.reset_index(drop=True)
    garbage_mask = out["company_name"].map(_garbage_rating_company).fillna(True)
    out = out.loc[~garbage_mask].copy()
    if out.empty:
        return pd.DataFrame(columns=keep)
    validity_mask = (
        out["company_name"].astype(str).str.len().gt(1)
        & (
            out["agency"].astype(str).str.len().gt(0)
            | out["new_rating"].astype(str).str.len().gt(0)
            | out["action_type"].astype(str).str.len().gt(0)
        )
    )
    out = out[validity_mask].copy()
    return out.reset_index(drop=True)


def canonicalize_credit_ratings() -> dict[str, object]:
    frames: list[pd.DataFrame] = []
    existing = _load_existing_processed(
        PROCESSED_DIR / "credit_ratings_nse_all.csv",
        PROCESSED_DIR / "credit_ratings_nse_all.parquet",
        PROCESSED_DIR / "credit_ratings_all.csv",
    )
    if not existing.empty:
        frames.append(_standardize_ratings_frame(existing))

    standardized_raw_files = sorted(RAW_RATINGS_DIR.glob("nse_credit_ratings*.csv"))
    for path in standardized_raw_files:
        frame = _standardize_ratings_frame(_read_frame(path))
        if not frame.empty:
            frames.append(frame)

    # Daily scrapes write standardized nse_credit_ratings*.csv files. Raw CF-CRD
    # files are a fallback for manual downloads only; parsing the full raw archive
    # on every canonicalization run is slow and noisy.
    if not standardized_raw_files:
        for path in sorted(RAW_RATINGS_DIR.glob("CF-CRD*.csv")):
            parsed = parse_credit_ratings_csv(path)
            frame = _standardize_ratings_frame(parsed if isinstance(parsed, pd.DataFrame) else pd.DataFrame())
            if not frame.empty:
                frames.append(frame)

    if not frames:
        empty = _standardize_ratings_frame(pd.DataFrame())
        _write_outputs(
            empty,
            csv_path=PROCESSED_DIR / "credit_ratings_nse_all.csv",
            parquet_path=PROCESSED_DIR / "credit_ratings_nse_all.parquet",
            alias_csv_paths=[PROCESSED_DIR / "credit_ratings_all.csv"],
            alias_parquet_paths=[PROCESSED_DIR / "credit_ratings_all.parquet"],
        )
        return {"rows": 0, "latest_date": None, "mapped_tickers": 0}

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined["processed_date"] = pd.to_datetime(combined["processed_date"], errors="coerce")
    combined = combined.dropna(subset=["date"])
    combined = combined.sort_values(
        ["date", "company_name", "agency", "processed_date"],
        kind="mergesort",
    )
    dedupe_cols = ["date", "company_name", "agency", "new_rating", "action_type", "isin"]
    dedupe_cols = [col for col in dedupe_cols if col in combined.columns]
    combined = combined.drop_duplicates(subset=dedupe_cols, keep="last").reset_index(drop=True)
    combined = combined.sort_values("date", ascending=False, kind="mergesort").reset_index(drop=True)

    _write_outputs(
        combined,
        csv_path=PROCESSED_DIR / "credit_ratings_nse_all.csv",
        parquet_path=PROCESSED_DIR / "credit_ratings_nse_all.parquet",
        alias_csv_paths=[PROCESSED_DIR / "credit_ratings_all.csv"],
        alias_parquet_paths=[PROCESSED_DIR / "credit_ratings_all.parquet"],
    )
    latest = pd.to_datetime(combined["date"], errors="coerce").max()
    mapped = int(combined["nse_ticker"].astype(str).str.len().gt(0).sum()) if "nse_ticker" in combined.columns else 0
    return {"rows": int(len(combined)), "latest_date": latest.isoformat() if pd.notna(latest) else None, "mapped_tickers": mapped}


def _standardize_pledge_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[
            "date",
            "broadcast_datetime",
            "company_name",
            "bse_code",
            "nse_ticker",
            "total_issued_shares",
            "total_promoter_shares",
            "total_promoter_holding_pct",
            "total_public_holding_shares",
            "encumbered_last_quarter_shares",
            "encumbered_last_quarter_promoter_pct",
            "encumbered_last_quarter_total_pct",
            "encumbered_last_quarter_value_cr",
            "disclosure_made_by_promoters",
            "shares_pledged",
            "total_demat_shares",
            "pledge_pct",
            "pledge_value_cr",
            "ticker_match_status",
            "source",
        ])

    out = frame.copy()
    out["date"] = pd.to_datetime(_col(out, "date"), errors="coerce")
    out["broadcast_datetime"] = pd.to_datetime(_col(out, "broadcast_datetime"), errors="coerce")
    for column in ["company_name", "bse_code", "nse_ticker", "ticker_match_status", "source"]:
        out[column] = _col(out, column).fillna("").astype(str).str.strip()
    out["nse_ticker"] = out["nse_ticker"].map(_normalize_ticker)
    return out.reset_index(drop=True)


def canonicalize_promoter_pledge() -> dict[str, object]:
    frames: list[pd.DataFrame] = []
    existing = _load_existing_processed(PROCESSED_DIR / "promoter_pledge_all.parquet", PLEDGE_PROCESSED_PATH)
    if not existing.empty:
        frames.append(_standardize_pledge_frame(existing))
    for path in sorted(RAW_PLEDGE_DIR.glob("*.csv")):
        parsed = parse_nse_promoter_pledge_csv(path)
        if not parsed.empty:
            frames.append(_standardize_pledge_frame(parsed))

    if not frames:
        empty = _standardize_pledge_frame(pd.DataFrame())
        _write_outputs(
            empty,
            csv_path=PLEDGE_PROCESSED_PATH,
            parquet_path=PROCESSED_DIR / "promoter_pledge_all.parquet",
        )
        return {"rows": 0, "latest_date": None}

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined["broadcast_datetime"] = pd.to_datetime(combined["broadcast_datetime"], errors="coerce")
    combined = combined.dropna(subset=["date"])
    combined["company_name"] = combined["company_name"].astype(str).str.strip()
    combined["nse_ticker"] = combined["nse_ticker"].astype(str).map(_normalize_ticker)
    combined["bse_code"] = combined["bse_code"].astype(str).str.strip()
    combined["ticker_match_status"] = combined["ticker_match_status"].astype(str)
    combined["_date_key"] = combined["date"].dt.strftime("%Y-%m-%d").fillna("")
    combined["_merge_priority"] = (
        combined["nse_ticker"].str.len().gt(0).astype(int) * 10
        + combined["company_name"].str.len().gt(0).astype(int) * 5
        + combined["broadcast_datetime"].notna().astype(int)
    )
    combined["_dedupe_key"] = combined.apply(
        lambda row: (
            f"{row['_date_key']}|company|{_normalize_company_name(row['company_name'])}"
            if row["company_name"]
            else f"{row['_date_key']}|ticker|{row['nse_ticker']}"
            if row["nse_ticker"]
            else f"{row['_date_key']}|bse|{row['bse_code']}"
        ),
        axis=1,
    )
    combined = combined.sort_values(
        ["_dedupe_key", "_merge_priority", "broadcast_datetime"],
        kind="mergesort",
    ).drop_duplicates(subset=["_dedupe_key"], keep="last")
    combined = combined.drop(columns=["_date_key", "_merge_priority", "_dedupe_key"], errors="ignore")
    combined = combined.sort_values(["date", "nse_ticker", "company_name"], kind="mergesort").reset_index(drop=True)

    _write_outputs(
        combined,
        csv_path=PLEDGE_PROCESSED_PATH,
        parquet_path=PROCESSED_DIR / "promoter_pledge_all.parquet",
    )
    latest = pd.to_datetime(combined["date"], errors="coerce").max()
    return {"rows": int(len(combined)), "latest_date": latest.isoformat() if pd.notna(latest) else None}


def _standardize_announcements_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=[
            "date",
            "broadcast_datetime",
            "receipt_datetime",
            "dissemination_datetime",
            "difference",
            "bse_code",
            "symbol",
            "nse_ticker",
            "company_name",
            "category",
            "headline",
            "announcement_text",
            "subject",
            "attachment",
            "source",
        ])

    out = frame.copy()
    for column in ["date", "broadcast_datetime", "receipt_datetime", "dissemination_datetime"]:
        out[column] = pd.to_datetime(_col(out, column), errors="coerce")
    for column in ["difference", "bse_code", "symbol", "nse_ticker", "company_name", "category", "headline", "announcement_text", "subject", "attachment", "source"]:
        out[column] = _col(out, column).fillna("").astype(str).str.strip()
    out["nse_ticker"] = out["nse_ticker"].map(_normalize_ticker)
    return out.reset_index(drop=True)


def canonicalize_announcements() -> dict[str, object]:
    frames: list[pd.DataFrame] = []
    existing = _load_existing_processed(PROCESSED_DIR / "announcements_all.parquet", ANNOUNCEMENTS_PROCESSED_PATH)
    if not existing.empty:
        frames.append(_standardize_announcements_frame(existing))
    for path in sorted(RAW_ANNOUNCEMENTS_DIR.glob("*.csv")):
        parsed = parse_nse_announcements_csv(path)
        if not parsed.empty:
            frames.append(_standardize_announcements_frame(parsed))

    if not frames:
        empty = _standardize_announcements_frame(pd.DataFrame())
        _write_outputs(
            empty,
            csv_path=ANNOUNCEMENTS_PROCESSED_PATH,
            parquet_path=PROCESSED_DIR / "announcements_all.parquet",
        )
        return {"rows": 0, "latest_date": None}

    combined = pd.concat(frames, ignore_index=True, sort=False)
    for column in ["date", "broadcast_datetime", "receipt_datetime", "dissemination_datetime"]:
        combined[column] = pd.to_datetime(combined[column], errors="coerce")
    combined = combined.dropna(subset=["date"])
    combined = combined.drop_duplicates(
        subset=["date", "nse_ticker", "headline", "attachment"],
        keep="last",
    ).sort_values(["date", "nse_ticker", "headline"], kind="mergesort").reset_index(drop=True)

    _write_outputs(
        combined,
        csv_path=ANNOUNCEMENTS_PROCESSED_PATH,
        parquet_path=PROCESSED_DIR / "announcements_all.parquet",
    )
    latest = pd.to_datetime(combined["date"], errors="coerce").max()
    return {"rows": int(len(combined)), "latest_date": latest.isoformat() if pd.notna(latest) else None}


def run_canonicalization() -> dict[str, dict[str, object]]:
    summary = {
        "bulk_deals": canonicalize_bulk_deals(),
        "credit_ratings": canonicalize_credit_ratings(),
        "promoter_pledge": canonicalize_promoter_pledge(),
        "announcements": canonicalize_announcements(),
    }
    STATUS_PATH.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonicalize alternative datasets onto the live NSE-first surface.")
    parser.parse_args()
    summary = run_canonicalization()
    for family, details in summary.items():
        print(f"[canonicalize:{family}] {json.dumps(details, default=str)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
