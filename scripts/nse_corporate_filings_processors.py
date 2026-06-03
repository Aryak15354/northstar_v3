#!/usr/bin/env python3
"""Processors for NSE corporate-filings CSV downloads."""

from __future__ import annotations

import difflib
import json
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PLEDGE_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "promoter_pledge"
RAW_ANNOUNCEMENTS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "announcements"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "alternative"
PLEDGE_PROCESSED_PATH = PROCESSED_DIR / "promoter_pledge_all.csv"
ANNOUNCEMENTS_PROCESSED_PATH = PROCESSED_DIR / "announcements_all.csv"
PLEDGE_PROCESSED_PARQUET_PATH = PROCESSED_DIR / "promoter_pledge_all.parquet"
ANNOUNCEMENTS_PROCESSED_PARQUET_PATH = PROCESSED_DIR / "announcements_all.parquet"

for path in (RAW_PLEDGE_DIR, RAW_ANNOUNCEMENTS_DIR, PROCESSED_DIR):
    path.mkdir(parents=True, exist_ok=True)


_COMPANY_STOPWORDS = {
    "LIMITED",
    "LTD",
    "PRIVATE",
    "PVT",
    "PUBLIC",
    "COMPANY",
    "CO",
    "CORPORATION",
    "CORP",
}

_CATEGORY_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "Insider Trading",
        (
            re.compile(r"\binsider\b", re.I),
            re.compile(r"\bsast\b", re.I),
            re.compile(r"\bsubstantial acquisition\b", re.I),
            re.compile(r"\bregulation\s+7\s*\(2\)\b", re.I),
            re.compile(r"\bregulation\s+29\b", re.I),
            re.compile(r"\bregulation\s+31\b", re.I),
        ),
    ),
    (
        "Merger",
        (
            re.compile(r"\bmerger\b", re.I),
            re.compile(r"\bamalgamation\b", re.I),
            re.compile(r"\bdemerger\b", re.I),
            re.compile(r"\bde-merger\b", re.I),
            re.compile(r"\bscheme of arrangement\b", re.I),
        ),
    ),
    (
        "Acquisition",
        (
            re.compile(r"\bacquisition\b", re.I),
            re.compile(r"\bacquire\b", re.I),
            re.compile(r"\btakeover\b", re.I),
            re.compile(r"\bstrategic stake\b", re.I),
            re.compile(r"\binvestment in\b", re.I),
        ),
    ),
    (
        "Capacity Expansion",
        (
            re.compile(r"\bcapacity\b", re.I),
            re.compile(r"\bcapex\b", re.I),
            re.compile(r"\bexpansion\b", re.I),
            re.compile(r"\bgreenfield\b", re.I),
            re.compile(r"\bbrownfield\b", re.I),
            re.compile(r"\bnew plant\b", re.I),
            re.compile(r"\bcommissioning\b", re.I),
            re.compile(r"\bcommercial production\b", re.I),
        ),
    ),
    (
        "Order Win",
        (
            re.compile(r"\border\b", re.I),
            re.compile(r"\bcontract\b", re.I),
            re.compile(r"\bletter of award\b", re.I),
            re.compile(r"\bwork order\b", re.I),
            re.compile(r"\baward of order\b", re.I),
            re.compile(r"\breceipt of order\b", re.I),
        ),
    ),
)


def _normalize_ticker(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text.endswith(".NS"):
        return text
    if "." in text:
        text = text.split(".", 1)[0]
    return f"{text}.NS"


def _normalize_company_name(value: object) -> str:
    text = str(value or "").upper()
    text = text.replace("&", " AND ")
    text = text.replace("'", "")
    replacements = (
        ("PHARMALABS", "PHARMA LABS"),
        ("PHARMACEUTICALS", "PHARMA"),
        ("TECHNOLOGIES", "TECH"),
        ("TECHNOLOGY", "TECH"),
        ("INDUSTRIES", "INDUSTRY"),
        ("SERVICES", "SERVICE"),
        ("LABORATORIES", "LABS"),
        ("LABORATORY", "LABS"),
        ("MOTORS", "MOTOR"),
        ("SYSTEMS", "SYSTEM"),
        ("PRODUCTS", "PRODUCT"),
        ("HOLDINGS", "HOLDING"),
        ("INTERNATIONAL", "INTL"),
        ("LIMITED", "LTD"),
        ("PRIVATE", "PVT"),
    )
    for src, dst in replacements:
        text = re.sub(rf"\b{re.escape(src)}\b", dst, text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    words = [word for word in text.split() if word not in _COMPANY_STOPWORDS]
    return " ".join(words).strip()


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False).str.strip()
    cleaned = cleaned.replace({"": None, "nan": None, "None": None})
    return pd.to_numeric(cleaned, errors="coerce")


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def _company_candidate_rows() -> Iterable[tuple[str, str]]:
    metadata_dir = PROJECT_ROOT / "data" / "raw" / "screener" / "metadata"
    for path in sorted(metadata_dir.glob("*_metadata.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        ticker = _normalize_ticker(payload.get("ticker"))
        company_name = str(payload.get("company_name") or "").strip()
        if ticker and company_name:
            yield company_name, ticker

    for path in (
        PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings" / "tickers_equities.csv",
        PROJECT_ROOT / "universe" / "nifty500.csv",
        PROJECT_ROOT / "universe" / "nifty_500.csv",
    ):
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        company_col = next((col for col in frame.columns if str(col).strip().upper() == "COMPANY NAME"), None)
        symbol_col = next((col for col in frame.columns if str(col).strip().upper() == "SYMBOL"), None)
        if not company_col or not symbol_col:
            continue
        for _, row in frame[[company_col, symbol_col]].dropna().iterrows():
            yield str(row[company_col]).strip(), _normalize_ticker(row[symbol_col])

    instrument_path = PROJECT_ROOT / "universe" / "instrument.csv"
    if instrument_path.exists():
        try:
            frame = pd.read_csv(instrument_path, low_memory=False)
        except Exception:
            frame = pd.DataFrame()
        if not frame.empty:
            frame = frame[(frame.get("exchange") == "NSE") & (frame.get("segment") == "CASH")].copy()
            if "series" in frame.columns:
                frame = frame[frame["series"].fillna("").isin(["EQ", "BE", "BZ", "SM", "ST"])].copy()
            for _, row in frame.iterrows():
                company_name = str(row.get("name") or "").strip()
                trading_symbol = str(row.get("trading_symbol") or "").strip()
                if company_name and trading_symbol:
                    yield company_name, _normalize_ticker(trading_symbol)


@lru_cache(maxsize=1)
def build_company_lookup() -> dict[str, str]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for company_name, ticker in _company_candidate_rows():
        normalized = _normalize_company_name(company_name)
        if normalized and ticker:
            counts[normalized][ticker] += 1
    return {name: counter.most_common(1)[0][0] for name, counter in counts.items() if counter}


def resolve_company_ticker(company_name: object) -> tuple[str | None, str]:
    lookup = build_company_lookup()
    normalized = _normalize_company_name(company_name)
    if not normalized:
        return None, "unmatched"
    if normalized in lookup:
        return lookup[normalized], "exact"

    fuzzy_match = difflib.get_close_matches(normalized, list(lookup.keys()), n=1, cutoff=0.85)
    if fuzzy_match:
        candidate = fuzzy_match[0]
        similarity = difflib.SequenceMatcher(None, normalized, candidate).ratio()
        overlap = _token_overlap(normalized, candidate)
        normalized_tokens = normalized.split()
        candidate_tokens = candidate.split()
        same_lead_token = bool(normalized_tokens and candidate_tokens and normalized_tokens[0] == candidate_tokens[0])
        contains_match = normalized in candidate or candidate in normalized
        if similarity >= 0.97 or (same_lead_token and (contains_match or overlap >= 0.6)):
            return lookup[candidate], f"fuzzy:{similarity:.2f}"

    return None, "unmatched"


def classify_announcement_category(subject: object, details: object) -> str:
    subject_text = str(subject or "").strip()
    full_text = f"{subject_text} {details or ''}".strip()
    for category, patterns in _CATEGORY_PATTERNS:
        if any(pattern.search(full_text) for pattern in patterns):
            return category
    return subject_text or "General"


def parse_nse_promoter_pledge_csv(csv_path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]

    rename_map = {
        "NAME OF COMPANY": "company_name",
        "TOTAL NO. OF ISSUED SHARES A+B+C": "total_issued_shares",
        "TOTAL PROMOTER HOLDING NO. OF SHARES (A)": "total_promoter_shares",
        "TOTAL PROMOTER HOLDING % A /(A+B+C)": "total_promoter_holding_pct",
        "TOTAL PUBLIC HOLDING B": "total_public_holding_shares",
        "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER NO. OF SHARES (X)": "encumbered_last_quarter_shares",
        "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER % OF PROMOTER SHARES (X/A)": "encumbered_last_quarter_promoter_pct",
        "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER % OF TOTAL SHARES [X/(A+B+C)]": "encumbered_last_quarter_total_pct",
        "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER VALUES(RS.CR.)=NO. OF SHARES ENCUMBERED [X] * LAST AVAILABLE CLOSING PRICE OF THE SCRIP": "encumbered_last_quarter_value_cr",
        "DISCLOSURE MADE BY PROMOTERS": "disclosure_made_by_promoters",
        "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM NO. OF SHARES PLEDGED": "shares_pledged",
        "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM TOTAL NO. OF DEMAT SHARES": "total_demat_shares",
        "(%) PLEDGE / DEMAT": "pledge_pct",
        "Values(Rs. Cr.)": "pledge_value_cr",
        "BROADCAST DATE": "broadcast_datetime",
    }
    frame = frame.rename(columns=rename_map)

    numeric_columns = [
        "total_issued_shares",
        "total_promoter_shares",
        "total_promoter_holding_pct",
        "total_public_holding_shares",
        "encumbered_last_quarter_shares",
        "encumbered_last_quarter_promoter_pct",
        "encumbered_last_quarter_total_pct",
        "encumbered_last_quarter_value_cr",
        "shares_pledged",
        "total_demat_shares",
        "pledge_pct",
        "pledge_value_cr",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = _to_numeric(frame[column])

    broadcast = pd.to_datetime(frame.get("broadcast_datetime"), format="%d-%b-%Y %H:%M:%S", errors="coerce")
    if broadcast.isna().all():
        broadcast = pd.to_datetime(frame.get("broadcast_datetime"), errors="coerce", dayfirst=True)
    frame["broadcast_datetime"] = broadcast
    frame["date"] = frame["broadcast_datetime"].dt.normalize()

    resolutions = frame.get("company_name", pd.Series(dtype=object)).apply(resolve_company_ticker)
    frame["nse_ticker"] = resolutions.map(lambda item: item[0] or "")
    frame["ticker_match_status"] = resolutions.map(lambda item: item[1])
    frame["bse_code"] = ""
    frame["source"] = "NSE_PROMOTER_PLEDGE"

    ordered_columns = [
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
    ]
    for column in ordered_columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame[ordered_columns].copy()
    frame = frame.dropna(subset=["date", "company_name"]).drop_duplicates(
        subset=["date", "company_name"], keep="last"
    )
    return frame.sort_values(["date", "company_name"], kind="mergesort").reset_index(drop=True)


def parse_nse_announcements_csv(csv_path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]

    rename_map = {
        "SYMBOL": "symbol",
        "COMPANY NAME": "company_name",
        "SUBJECT": "subject",
        "DETAILS": "details",
        "BROADCAST DATE/TIME": "broadcast_datetime",
        "RECEIPT": "receipt_datetime",
        "DISSEMINATION": "dissemination_datetime",
        "DIFFERENCE": "difference",
        "ATTACHMENT": "attachment",
    }
    frame = frame.rename(columns=rename_map)

    for column in ("broadcast_datetime", "receipt_datetime", "dissemination_datetime"):
        if column in frame.columns:
            parsed = pd.to_datetime(frame[column], format="%d-%b-%Y %H:%M:%S", errors="coerce")
            if parsed.isna().all():
                parsed = pd.to_datetime(frame[column], errors="coerce")
            frame[column] = parsed

    subject_series = frame.get("subject", pd.Series("", index=frame.index)).fillna("").astype(str)
    details_series = frame.get("details", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["date"] = frame["broadcast_datetime"]
    frame["nse_ticker"] = frame.get("symbol", pd.Series("", index=frame.index)).map(_normalize_ticker)
    frame["headline"] = subject_series.str.strip()
    frame["announcement_text"] = details_series.str.strip()
    frame["category"] = [
        classify_announcement_category(subject, details)
        for subject, details in zip(subject_series, details_series, strict=False)
    ]
    frame["bse_code"] = ""
    frame["source"] = "NSE_ANNOUNCEMENTS"

    ordered_columns = [
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
    ]
    for column in ordered_columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame[ordered_columns].copy()
    frame = frame.dropna(subset=["date", "headline"]).drop_duplicates(
        subset=["date", "nse_ticker", "headline", "attachment"], keep="last"
    )
    return frame.sort_values(["date", "nse_ticker", "headline"], kind="mergesort").reset_index(drop=True)


def _load_existing_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def _write_dual_outputs(frame: pd.DataFrame, csv_path: Path, parquet_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(parquet_path, index=False)


def _combine_frames(existing: pd.DataFrame, new_frame: pd.DataFrame, *, dedupe_columns: list[str]) -> pd.DataFrame:
    frames = [frame for frame in (existing, new_frame) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True, sort=False)
    for column in ("date", "broadcast_datetime", "receipt_datetime", "dissemination_datetime"):
        if column in combined.columns:
            combined[column] = pd.to_datetime(combined[column], errors="coerce")

    active_dedupe_columns = [column for column in dedupe_columns if column in combined.columns]
    if active_dedupe_columns:
        combined = combined.drop_duplicates(subset=active_dedupe_columns, keep="last")

    sort_columns = [column for column in ["date", "nse_ticker", "company_name", "headline"] if column in combined.columns]
    if sort_columns:
        combined = combined.sort_values(sort_columns, kind="mergesort")
    return combined.reset_index(drop=True)


def merge_promoter_pledge_history(new_frame: pd.DataFrame) -> pd.DataFrame:
    existing = _load_existing_frame(PLEDGE_PROCESSED_PARQUET_PATH)
    if existing.empty:
        existing = _load_existing_frame(PLEDGE_PROCESSED_PATH)
    combined = _combine_frames(existing, new_frame, dedupe_columns=[])
    if combined.empty:
        _write_dual_outputs(combined, PLEDGE_PROCESSED_PATH, PLEDGE_PROCESSED_PARQUET_PATH)
        return combined

    combined["date"] = pd.to_datetime(combined.get("date"), errors="coerce")
    combined["company_name"] = combined.get("company_name", "").fillna("").astype(str).str.strip()
    combined["nse_ticker"] = combined.get("nse_ticker", "").fillna("").astype(str).str.strip()
    combined["bse_code"] = combined.get("bse_code", "").fillna("").astype(str).str.strip()
    combined["ticker_match_status"] = combined.get("ticker_match_status", "").fillna("").astype(str)
    combined["broadcast_datetime"] = pd.to_datetime(combined.get("broadcast_datetime"), errors="coerce")
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
    _write_dual_outputs(combined, PLEDGE_PROCESSED_PATH, PLEDGE_PROCESSED_PARQUET_PATH)
    return combined


def merge_announcements_history(new_frame: pd.DataFrame) -> pd.DataFrame:
    existing = _load_existing_frame(ANNOUNCEMENTS_PROCESSED_PARQUET_PATH)
    if existing.empty:
        existing = _load_existing_frame(ANNOUNCEMENTS_PROCESSED_PATH)
    combined = _combine_frames(
        existing,
        new_frame,
        dedupe_columns=["date", "nse_ticker", "headline", "attachment"],
    )
    _write_dual_outputs(combined, ANNOUNCEMENTS_PROCESSED_PATH, ANNOUNCEMENTS_PROCESSED_PARQUET_PATH)
    return combined
