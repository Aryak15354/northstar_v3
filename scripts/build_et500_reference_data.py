#!/usr/bin/env python3
"""Build ET500 reference artifacts used by the research pipeline.

Outputs:
- data/reference/et500_name_to_ticker.csv
- data/reference/et500_pit_membership.csv
"""

from __future__ import annotations

import argparse
import difflib
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


STOPWORDS = {
    "LTD",
    "LIMITED",
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "INC",
    "PVT",
    "PRIVATE",
    "PUBLIC",
    "PLC",
    "LLP",
    "THE",
    "OF",
    "AND",
}


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _norm_company_basic(value: object) -> str:
    s = str(value or "").upper().replace("&", " AND ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return " ".join(s.split())


def _norm_company_stripped(value: object) -> str:
    tokens = [t for t in _norm_company_basic(value).split() if t not in STOPWORDS]
    return " ".join(tokens)


def _token_f1(a: str, b: str) -> float:
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    if inter == 0:
        return 0.0
    return (2.0 * inter) / float(len(sa) + len(sb))


def _similarity(a: str, b: str) -> tuple[float, float, float]:
    token_score = _token_f1(a, b)
    seq_score = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    contain_score = 0.0
    if a and b and (a in b or b in a):
        contain_score = min(len(a), len(b)) / max(len(a), len(b))
    return max(token_score, seq_score, contain_score), token_score, seq_score


def _fuzzy_match_ok(query: str, alias: str, score: float, token_score: float, seq_score: float) -> bool:
    long_tokens = [t for t in query.split() if len(t) >= 3]
    if len(long_tokens) < 2:
        return False
    if token_score < 0.55:
        return False
    if seq_score < 0.82 and score < 0.94:
        return False
    if min(len(query), len(alias)) < 10 and score < 0.95:
        return False
    return True


def _to_float(series: pd.Series) -> pd.Series:
    as_text = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip()
    )
    as_text = as_text.replace({"": np.nan, "nan": np.nan, "NaN": np.nan, "None": np.nan, "-": np.nan})
    return pd.to_numeric(as_text, errors="coerce").astype(float)


def build_reference_files(
    *,
    et500_csv: Path,
    prices_parquet: Path,
    nifty500_csv: Path,
    instrument_csv: Path,
    mapping_out_csv: Path,
    membership_out_csv: Path,
) -> tuple[int, int]:
    if not et500_csv.exists():
        raise FileNotFoundError(f"ET500 CSV not found: {et500_csv}")
    if not prices_parquet.exists():
        raise FileNotFoundError(f"Prices parquet not found: {prices_parquet}")
    if not nifty500_csv.exists():
        raise FileNotFoundError(f"Nifty500 CSV not found: {nifty500_csv}")
    if not instrument_csv.exists():
        raise FileNotFoundError(f"Instrument CSV not found: {instrument_csv}")

    et_df = pd.read_csv(et500_csv)
    et_df["COMPANY NAME"] = et_df["COMPANY NAME"].astype(str).str.strip()
    company_name_counts = et_df["COMPANY NAME"].value_counts().to_dict()
    unique_company_names = sorted(set(et_df["COMPANY NAME"].tolist()))

    prices = pd.read_parquet(prices_parquet, columns=["ticker"])
    universe_tickers = {_normalize_ticker(x) for x in prices["ticker"].astype(str).tolist()}
    universe_tickers.discard("")

    alias_basic_by_ticker: dict[str, set[str]] = defaultdict(set)
    alias_stripped_by_ticker: dict[str, set[str]] = defaultdict(set)

    def add_alias(ticker: str, company_name: object) -> None:
        if ticker not in universe_tickers:
            return
        basic = _norm_company_basic(company_name)
        stripped = _norm_company_stripped(company_name)
        if basic:
            alias_basic_by_ticker[ticker].add(basic)
        if stripped:
            alias_stripped_by_ticker[ticker].add(stripped)

    nifty_df = pd.read_csv(nifty500_csv)
    for _, row in nifty_df.iterrows():
        ticker = _normalize_ticker(row.get("Symbol", ""))
        add_alias(ticker, row.get("Company Name", ""))

    instrument_df = pd.read_csv(
        instrument_csv,
        usecols=["exchange", "trading_symbol", "name", "instrument_type", "series"],
        low_memory=False,
    )
    instrument_df = instrument_df[
        (instrument_df["exchange"].astype(str).str.upper() == "NSE")
        & (instrument_df["instrument_type"].astype(str).str.upper() == "EQ")
        & (instrument_df["series"].astype(str).str.upper() == "EQ")
    ]
    for row in instrument_df.itertuples(index=False):
        ticker = _normalize_ticker(getattr(row, "trading_symbol", ""))
        add_alias(ticker, getattr(row, "name", ""))

    basic_to_tickers: dict[str, set[str]] = defaultdict(set)
    stripped_to_tickers: dict[str, set[str]] = defaultdict(set)
    stripped_candidates: list[tuple[str, str]] = []
    for ticker, aliases in alias_basic_by_ticker.items():
        for alias in aliases:
            basic_to_tickers[alias].add(ticker)
    for ticker, aliases in alias_stripped_by_ticker.items():
        for alias in aliases:
            stripped_to_tickers[alias].add(ticker)
            stripped_candidates.append((alias, ticker))

    mapping_rows: list[dict[str, object]] = []
    for company_name in unique_company_names:
        basic_name = _norm_company_basic(company_name)
        stripped_name = _norm_company_stripped(company_name)

        ticker = "UNMATCHED"
        method = "unmatched"
        score = np.nan

        exact_basic_hits = basic_to_tickers.get(basic_name, set())
        if len(exact_basic_hits) == 1:
            ticker = next(iter(exact_basic_hits))
            method = "exact_basic"
            score = 1.0
        else:
            exact_stripped_hits = stripped_to_tickers.get(stripped_name, set())
            if len(exact_stripped_hits) == 1 and len([t for t in stripped_name.split() if len(t) >= 3]) >= 2:
                ticker = next(iter(exact_stripped_hits))
                method = "exact_stripped"
                score = 1.0

        if ticker == "UNMATCHED":
            scored: list[tuple[float, float, float, str, str]] = []
            for alias, candidate_ticker in stripped_candidates:
                sim, token_sim, seq_sim = _similarity(stripped_name, alias)
                if sim < 0.82:
                    continue
                scored.append((sim, token_sim, seq_sim, candidate_ticker, alias))
            scored.sort(key=lambda x: x[0], reverse=True)
            if scored:
                best_score = scored[0][0]
                top_tied = [x for x in scored if abs(x[0] - best_score) < 1e-9]
                top_tickers = {x[3] for x in top_tied}
                second_best = max((x[0] for x in scored if x[3] not in top_tickers), default=0.0)
                best = top_tied[0]
                if (
                    best_score >= 0.93
                    and (best_score - second_best) >= 0.03
                    and len(top_tickers) == 1
                    and _fuzzy_match_ok(stripped_name, best[4], best_score, best[1], best[2])
                ):
                    ticker = best[3]
                    method = "fuzzy"
                    score = best_score

        mapping_rows.append(
            {
                "company_name": company_name,
                "nse_ticker": ticker,
                "match_method": method,
                "match_score": score,
            }
        )

    mapping_df = pd.DataFrame(mapping_rows)

    # Keep one company name per ticker for a strict one-to-one mapping table.
    matched = mapping_df[mapping_df["nse_ticker"] != "UNMATCHED"].copy()
    if not matched.empty:
        matched["company_row_count"] = matched["company_name"].map(lambda x: int(company_name_counts.get(x, 0)))
        matched = matched.sort_values(
            ["nse_ticker", "company_row_count", "match_score", "company_name"],
            ascending=[True, False, False, True],
            kind="mergesort",
        )
        keep_company_by_ticker = matched.drop_duplicates(subset=["nse_ticker"], keep="first")[
            ["nse_ticker", "company_name"]
        ]
        keep_pairs = {
            (str(row.company_name), str(row.nse_ticker))
            for row in keep_company_by_ticker.itertuples(index=False)
        }
        demote_mask = mapping_df["nse_ticker"].ne("UNMATCHED") & ~mapping_df.apply(
            lambda r: (str(r["company_name"]), str(r["nse_ticker"])) in keep_pairs,
            axis=1,
        )
        if bool(demote_mask.any()):
            mapping_df.loc[demote_mask, "nse_ticker"] = "UNMATCHED"
            mapping_df.loc[demote_mask, "match_method"] = "duplicate_ticker_demoted"
            mapping_df.loc[demote_mask, "match_score"] = np.nan

    mapping_out = mapping_df[["company_name", "nse_ticker"]].sort_values("company_name").reset_index(drop=True)
    mapping_out_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping_out.to_csv(mapping_out_csv, index=False)

    map_dict = dict(zip(mapping_out["company_name"], mapping_out["nse_ticker"]))
    et_work = et_df.copy()
    et_work["nse_ticker"] = et_work["COMPANY NAME"].map(map_dict).fillna("UNMATCHED")
    et_work = et_work[et_work["nse_ticker"] != "UNMATCHED"].copy()

    revenue_col = next((c for c in et_df.columns if c.strip().startswith("Revenue")), "Revenue")
    membership = pd.DataFrame(
        {
            "year": pd.to_numeric(et_work["Year"], errors="coerce"),
            "nse_ticker": et_work["nse_ticker"].map(_normalize_ticker),
            "rank": _to_float(et_work["RANK"]),
            "prev_rank": _to_float(et_work["PREVIOUS YEAR RANK"]),
            "revenue_cr": _to_float(et_work[revenue_col]),
            "revenue_change_pct": _to_float(et_work["Revenue change"]),
            "pat_cr": _to_float(et_work["PAT in crores"]),
            "pat_change_pct": _to_float(et_work["PAT change"]),
            "market_cap_cr": _to_float(et_work["Market Cap in crores"]),
        }
    )
    membership = membership.dropna(subset=["year", "nse_ticker"])
    membership["year"] = membership["year"].astype(int)
    membership = membership.sort_values(["year", "rank", "nse_ticker"], kind="mergesort")
    membership = membership.drop_duplicates(subset=["year", "nse_ticker"], keep="first")
    membership = membership[
        [
            "year",
            "nse_ticker",
            "rank",
            "prev_rank",
            "revenue_cr",
            "revenue_change_pct",
            "pat_cr",
            "pat_change_pct",
            "market_cap_cr",
        ]
    ].reset_index(drop=True)
    membership_out_csv.parent.mkdir(parents=True, exist_ok=True)
    membership.to_csv(membership_out_csv, index=False)

    matched_count = int((mapping_out["nse_ticker"] != "UNMATCHED").sum())
    unmatched_count = int((mapping_out["nse_ticker"] == "UNMATCHED").sum())
    print(
        f"[et500-mapping] matched={matched_count} unmatched={unmatched_count} total={len(mapping_out)} "
        f"membership_rows={len(membership)}"
    )
    return matched_count, unmatched_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ET500 name/ticker mapping and PIT membership files.")
    parser.add_argument(
        "--et500-csv",
        type=Path,
        default=Path("universe/Economic times Top 500 companies since 2009 - 2009-2021.csv"),
    )
    parser.add_argument("--prices-parquet", type=Path, default=Path("data/processed/prices.parquet"))
    parser.add_argument("--nifty500-csv", type=Path, default=Path("universe/nifty500.csv"))
    parser.add_argument("--instrument-csv", type=Path, default=Path("universe/instrument.csv"))
    parser.add_argument(
        "--mapping-out",
        type=Path,
        default=Path("data/reference/et500_name_to_ticker.csv"),
    )
    parser.add_argument(
        "--membership-out",
        type=Path,
        default=Path("data/reference/et500_pit_membership.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_reference_files(
        et500_csv=args.et500_csv,
        prices_parquet=args.prices_parquet,
        nifty500_csv=args.nifty500_csv,
        instrument_csv=args.instrument_csv,
        mapping_out_csv=args.mapping_out,
        membership_out_csv=args.membership_out,
    )


if __name__ == "__main__":
    main()
