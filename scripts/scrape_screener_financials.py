#!/usr/bin/env python3
"""Comprehensive one-shot Screener.in company page scraper.

This script scrapes all major sections on:
  https://www.screener.in/company/TICKER/consolidated/
with fallback to:
  https://www.screener.in/company/TICKER/
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

DEFAULT_OUTPUT_DIR = Path("data/raw/vendors/screener")
LOG_COLUMNS = [
    "ticker",
    "url_used",
    "status",
    "sections_scraped",
    "rows_scraped_total",
    "error_message",
    "timestamp",
    "duration_seconds",
]

SECTION_NAMES = {
    "A": "key_ratios",
    "B": "quarterly_results",
    "C": "annual_profit_loss",
    "D": "annual_balance_sheet",
    "E": "annual_cash_flow",
    "F": "annual_ratios",
    "G": "shareholding_pattern",
    "H": "peers_comparison",
    "I": "company_metadata",
    "J": "pros_cons",
}

KEY_RATIO_LABELS = {
    "marketcap": "Market Cap",
    "currentprice": "Current Price",
    "highlow": "High / Low",
    "stockpe": "Stock P/E",
    "bookvalue": "Book Value",
    "dividendyield": "Dividend Yield",
    "roce": "ROCE",
    "roe": "ROE",
    "facevalue": "Face Value",
}

TABLE_SECTION_SPECS = {
    "quarterly_pl": {
        "ids": ["quarters", "quarterly-results", "quarterly"],
        "headings": ["quarterly results", "quarterly"],
    },
    "annual_pl": {
        "ids": ["profit-loss", "profitandloss", "profit_loss"],
        "headings": ["profit & loss", "profit and loss", "annual results"],
    },
    "annual_bs": {
        "ids": ["balance-sheet", "balancesheet"],
        "headings": ["balance sheet"],
    },
    "annual_cf": {
        "ids": ["cash-flow", "cashflow"],
        "headings": ["cash flow"],
    },
    "annual_ratios": {
        "ids": ["ratios", "financial-ratios"],
        "headings": ["ratios"],
    },
    "shareholding": {
        "ids": ["shareholding", "share-holding"],
        "headings": ["shareholding pattern", "shareholding"],
    },
    "peers": {
        "ids": ["peers", "peers-table"],
        "headings": ["peer comparison", "peers"],
    },
}


@dataclass
class ScrapeResult:
    ticker: str
    url_used: str
    status: str
    sections_scraped: list[str]
    rows_scraped_total: int
    error_message: str
    duration_seconds: float


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_ticker(raw: str) -> str:
    s = _clean_text(raw).upper()
    if not s:
        return ""
    if "." in s:
        base, suffix = s.split(".", 1)
        if suffix == "NS":
            return f"{base}.NS"
        return f"{base}.NS"
    return f"{s}.NS"


def _ticker_to_slug(ticker: str) -> str:
    base = _normalize_ticker(ticker).replace(".NS", "")
    return re.sub(r"[^A-Z0-9_&-]+", "", base)


def _ticker_for_url(ticker: str) -> str:
    return _ticker_to_slug(ticker)


def _norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(text).lower())


def clean_numeric(value: Any) -> float:
    s = _clean_text(value)
    if not s:
        return float("nan")
    if s.lower() in {"-", "--", "—", "na", "n/a", "nan", "none"}:
        return float("nan")

    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()

    s = s.replace(",", "")
    s = s.replace("₹", "")
    s = s.replace("Rs.", "")
    s = s.replace("Cr.", "")
    s = s.replace("Cr", "")
    s = s.replace("%", "")
    s = s.replace("x", "")
    s = s.replace("X", "")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9.\-]", "", s)

    if s in {"", "-", ".", "-.", ".-"}:
        return float("nan")
    try:
        out = float(s)
    except ValueError:
        return float("nan")
    if neg:
        out = -abs(out)
    return float(out)


def _parse_high_low(value: str) -> dict[str, Any]:
    raw = _clean_text(value)
    nums = re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", raw)
    parsed = [clean_numeric(x) for x in nums[:2]]
    out: dict[str, Any] = {"raw": raw}
    if parsed:
        out["high"] = parsed[0]
    if len(parsed) > 1:
        out["low"] = parsed[1]
    return out


def _find_table_by_spec(soup: BeautifulSoup, spec: dict[str, list[str]]) -> Optional[Tag]:
    for section_id in spec["ids"]:
        by_id = soup.find(id=section_id)
        if isinstance(by_id, Tag):
            table = by_id.find("table")
            if isinstance(table, Tag):
                return table

    lowered_ids = set(spec["ids"])
    for node in soup.find_all(["section", "div", "article"]):
        node_id = _clean_text(node.get("id", "")).lower()
        if any(cand in node_id for cand in lowered_ids):
            table = node.find("table")
            if isinstance(table, Tag):
                return table

    heading_needles = [x.lower() for x in spec["headings"]]
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        htxt = _clean_text(heading.get_text(" ", strip=True)).lower()
        if not any(needle in htxt for needle in heading_needles):
            continue
        parent = heading.find_parent(["section", "div", "article"])
        if isinstance(parent, Tag):
            table = parent.find("table")
            if isinstance(table, Tag):
                return table
        sib = heading.find_next("table")
        if isinstance(sib, Tag):
            return sib
    return None


def _extract_headers_and_rows(table: Tag) -> tuple[list[str], list[Tag]]:
    header_cells: list[str] = []
    row_nodes: list[Tag] = []

    thead = table.find("thead")
    if isinstance(thead, Tag):
        trs = thead.find_all("tr")
        if trs:
            header_cells = [_clean_text(x.get_text(" ", strip=True)) for x in trs[-1].find_all(["th", "td"])]

    tbody = table.find("tbody")
    if isinstance(tbody, Tag):
        row_nodes = [r for r in tbody.find_all("tr") if isinstance(r, Tag)]
    else:
        row_nodes = [r for r in table.find_all("tr") if isinstance(r, Tag)]

    if not header_cells and row_nodes:
        first_cells = row_nodes[0].find_all(["th", "td"])
        header_cells = [_clean_text(x.get_text(" ", strip=True)) for x in first_cells]
        row_nodes = row_nodes[1:]
    return header_cells, row_nodes


def _table_to_long_rows(table: Optional[Tag], ticker: str) -> list[dict[str, Any]]:
    if not isinstance(table, Tag):
        return []
    headers, row_nodes = _extract_headers_and_rows(table)
    if len(headers) < 2:
        return []
    periods = [_clean_text(x) for x in headers[1:]]

    out: list[dict[str, Any]] = []
    for row in row_nodes:
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        metric = _clean_text(cells[0].get_text(" ", strip=True))
        metric = re.sub(r"\s*\+\s*$", "", metric).strip()
        if not metric:
            continue

        values = [_clean_text(c.get_text(" ", strip=True)) for c in cells[1:]]
        if len(values) < len(periods):
            values += [""] * (len(periods) - len(values))
        for period, val in zip(periods, values):
            if not period:
                continue
            out.append(
                {
                    "ticker": ticker,
                    "metric": metric,
                    "period": period,
                    "value": float(clean_numeric(val)),
                }
            )
    return out


def _extract_key_ratios(soup: BeautifulSoup) -> dict[str, Any]:
    items: dict[str, Any] = {}
    nodes = soup.select("ul#top-ratios li, div#top-ratios li, ul.company-ratios li")
    if not nodes:
        nodes = soup.find_all("li")
    for li in nodes:
        if not isinstance(li, Tag):
            continue
        name_node = li.select_one(".name")
        value_node = li.select_one(".value")
        if not isinstance(name_node, Tag) or not isinstance(value_node, Tag):
            spans = li.find_all("span")
            if len(spans) < 2:
                continue
            name_text = _clean_text(spans[0].get_text(" ", strip=True))
            value_text = _clean_text(spans[-1].get_text(" ", strip=True))
        else:
            name_text = _clean_text(name_node.get_text(" ", strip=True))
            value_text = _clean_text(value_node.get_text(" ", strip=True))
        if not name_text:
            continue
        nk = _norm_key(name_text)
        if nk not in KEY_RATIO_LABELS:
            continue
        canon = KEY_RATIO_LABELS[nk]
        if canon == "High / Low":
            items[canon] = _parse_high_low(value_text)
        else:
            val = clean_numeric(value_text)
            items[canon] = val if pd.notna(val) else value_text
    return items


def _extract_about_text(soup: BeautifulSoup) -> str:
    for css in ["section#about p", "div#about p", "[id*=about] p"]:
        node = soup.select_one(css)
        if isinstance(node, Tag):
            txt = _clean_text(node.get_text(" ", strip=True))
            if txt:
                return txt
    for heading in soup.find_all(["h2", "h3", "h4", "div", "span"]):
        htxt = _clean_text(heading.get_text(" ", strip=True)).lower()
        if htxt != "about":
            continue
        parent = heading.find_parent(["section", "div", "article"])
        if not isinstance(parent, Tag):
            continue
        p = parent.find("p")
        if isinstance(p, Tag):
            txt = _clean_text(p.get_text(" ", strip=True))
            if txt:
                return txt
    return ""


def _extract_metadata(soup: BeautifulSoup, ticker: str, url_used: str) -> dict[str, Any]:
    company_name = ""
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        company_name = _clean_text(h1.get_text(" ", strip=True))

    page_text = _clean_text(soup.get_text(" ", strip=True))
    bse_match = re.search(r"\bBSE\s*[:\-]?\s*([0-9]{3,6})\b", page_text, flags=re.IGNORECASE)
    nse_match = re.search(r"\bNSE\s*[:\-]?\s*([A-Z0-9&\-._]{2,24})\b", page_text, flags=re.IGNORECASE)

    bse_code = bse_match.group(1) if bse_match else ""
    nse_code = nse_match.group(1) if nse_match else ""

    industry = ""
    sector = ""
    for item in soup.select("li, tr"):
        if not isinstance(item, Tag):
            continue
        name_node = item.select_one(".name")
        value_node = item.select_one(".value")
        if not isinstance(name_node, Tag) or not isinstance(value_node, Tag):
            continue
        key = _norm_key(name_node.get_text(" ", strip=True))
        val = _clean_text(value_node.get_text(" ", strip=True))
        if key == "industry" and val:
            industry = val
        elif key == "sector" and val:
            sector = val

    website = ""
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = _clean_text(a.get("href", ""))
        txt = _clean_text(a.get_text(" ", strip=True)).lower()
        if "website" in txt and href.startswith("http"):
            website = href
            break
    if not website:
        for a in soup.find_all("a", href=True):
            href = _clean_text(a.get("href", ""))
            if not href.startswith("http"):
                continue
            if "screener.in" in href or "bseindia" in href or "nseindia" in href:
                continue
            website = href
            break

    return {
        "ticker": ticker,
        "company_name": company_name,
        "bse_code": bse_code,
        "nse_code": nse_code,
        "industry": industry,
        "sector": sector,
        "about_text": _extract_about_text(soup),
        "website": website,
        "url_used": url_used,
        "scraped_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _dedupe_keep_order(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        v = _clean_text(raw)
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        out.append(v)
        seen.add(key)
    return out


def _extract_pros_cons(soup: BeautifulSoup) -> dict[str, list[str]]:
    pros: list[str] = []
    cons: list[str] = []

    for li in soup.select(".pros li, [id*=pros] li"):
        if isinstance(li, Tag):
            pros.append(_clean_text(li.get_text(" ", strip=True)))
    for li in soup.select(".cons li, [id*=cons] li"):
        if isinstance(li, Tag):
            cons.append(_clean_text(li.get_text(" ", strip=True)))

    for heading in soup.find_all(["h2", "h3", "h4", "div", "span"]):
        txt = _clean_text(heading.get_text(" ", strip=True)).lower()
        if txt not in {"pros", "cons"}:
            continue
        parent = heading.find_parent(["section", "div", "article"])
        if not isinstance(parent, Tag):
            continue
        ul = parent.find("ul")
        if not isinstance(ul, Tag):
            continue
        bullets = [_clean_text(li.get_text(" ", strip=True)) for li in ul.find_all("li")]
        if txt == "pros":
            pros.extend(bullets)
        else:
            cons.extend(bullets)
    return {"pros": _dedupe_keep_order(pros), "cons": _dedupe_keep_order(cons)}


def _extract_peers(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table = _find_table_by_spec(soup, TABLE_SECTION_SPECS["peers"])
    if not isinstance(table, Tag):
        return []
    headers, row_nodes = _extract_headers_and_rows(table)
    if len(headers) < 2:
        return []
    headers = [_clean_text(x) if _clean_text(x) else f"col_{i}" for i, x in enumerate(headers)]

    peers: list[dict[str, Any]] = []
    for row in row_nodes:
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        values = [_clean_text(c.get_text(" ", strip=True)) for c in cells]
        if len(values) < len(headers):
            values += [""] * (len(headers) - len(values))

        row_obj: dict[str, Any] = {}
        for key, val in zip(headers, values):
            if key.lower() in {"name", "company", "peer", "s.no", "s.no.", "serial"}:
                row_obj[key] = val
                continue
            nval = clean_numeric(val)
            row_obj[key] = nval if pd.notna(nval) else val

        # If serial number is first and name is second, normalize an explicit Name key.
        if "Name" not in row_obj and len(values) >= 2 and headers[0].lower() in {"s.no", "s.no.", "serial", "col_0"}:
            row_obj["Name"] = values[1]
        peers.append(row_obj)
    return peers


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _write_long_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        pd.DataFrame(columns=["ticker", "metric", "period", "value"]).to_csv(path, index=False)
        return 0
    df = pd.DataFrame(rows, columns=["ticker", "metric", "period", "value"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce").astype(float)
    df.to_csv(path, index=False)
    return int(len(df))


def _expected_resume_files(output_dir: Path, ticker_slug: str) -> list[Path]:
    return [
        output_dir / "metadata" / f"{ticker_slug}_metadata.json",
        output_dir / "financials" / f"{ticker_slug}_quarterly_pl.csv",
        output_dir / "financials" / f"{ticker_slug}_annual_pl.csv",
        output_dir / "financials" / f"{ticker_slug}_annual_bs.csv",
        output_dir / "financials" / f"{ticker_slug}_annual_cf.csv",
        output_dir / "financials" / f"{ticker_slug}_annual_ratios.csv",
        output_dir / "shareholding" / f"{ticker_slug}_shareholding.csv",
    ]


def _all_resume_files_exist(output_dir: Path, ticker_slug: str) -> bool:
    return all(p.exists() for p in _expected_resume_files(output_dir, ticker_slug))


def _resume_files_are_fresh(output_dir: Path, ticker_slug: str, max_age_days: int) -> bool:
    """True only if every core file exists AND is newer than max_age_days.

    Existence alone is NOT sufficient: quarterly fundamentals gain a new column
    every quarter, so a file scraped last quarter is stale even though it exists.
    Skipping on existence alone is the "resume == complete" bug that resume-skipped
    all 2,495 tickers on the June run while the real data was from March.
    A non-positive max_age_days disables the freshness gate (existence-only resume).
    """
    files = _expected_resume_files(output_dir, ticker_slug)
    if not all(p.exists() for p in files):
        return False
    if max_age_days <= 0:
        return True
    cutoff = time.time() - (max_age_days * 86400)
    return all(p.stat().st_mtime >= cutoff for p in files)


def _load_tickers(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"ticker file not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        if df.empty:
            return []
        candidates = ["ticker", "Ticker", "symbol", "Symbol", "nse_ticker", "NSE"]
        col = next((c for c in candidates if c in df.columns), None)
        if col is None:
            col = df.columns[0]
        raw = [str(x) for x in df[col].dropna().tolist()]
    else:
        raw = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]

    out: list[str] = []
    seen: set[str] = set()
    for tk in raw:
        ntk = _normalize_ticker(tk)
        if not ntk:
            continue
        if ntk in seen:
            continue
        seen.add(ntk)
        out.append(ntk)
    return out


def _fetch_company_page(session: requests.Session, ticker: str, timeout: int = 30) -> tuple[str, str]:
    slug = _ticker_for_url(ticker)
    consolidated_url = f"https://www.screener.in/company/{slug}/consolidated/"
    standalone_url = f"https://www.screener.in/company/{slug}/"

    r = session.get(consolidated_url, timeout=timeout, allow_redirects=True)
    if r.status_code == 200:
        return consolidated_url, r.text
    if r.status_code == 404:
        r2 = session.get(standalone_url, timeout=timeout, allow_redirects=True)
        if r2.status_code == 200:
            return standalone_url, r2.text
        if r2.status_code == 404:
            raise FileNotFoundError(f"404 not found for consolidated and standalone ({ticker})")
        raise RuntimeError(f"standalone request failed with status {r2.status_code}")
    raise RuntimeError(f"consolidated request failed with status {r.status_code}")


def _quarterly_npa_is_blank(rows: list[dict[str, Any]]) -> bool:
    """True if bank asset-quality rows exist but every value is NaN.

    Banks disclose Gross/Net NPA on their STANDALONE statements; the consolidated
    Screener page carries the NPA row labels with empty cells. Detecting that lets
    us fall back to the standalone page instead of silently storing all-NaN NPA
    (the B3 defect that left 75 of 95 financials without GNPA).
    """
    npa_vals = [r["value"] for r in rows if "npa" in str(r.get("metric", "")).lower()]
    if not npa_vals:
        return False
    return all(pd.isna(v) for v in npa_vals)


def scrape_ticker(session: requests.Session, ticker: str, output_dir: Path) -> ScrapeResult:
    started = time.time()
    ticker_slug = _ticker_to_slug(ticker)
    sections: list[str] = []
    rows_total = 0
    url_used = ""

    try:
        url_used, html = _fetch_company_page(session, ticker)
        soup = BeautifulSoup(html, "html.parser")

        # Bank asset-quality (Gross/Net NPA) is disclosed standalone. If the fetched
        # (consolidated) page has NPA rows that are entirely blank, re-fetch the
        # standalone page so those metrics are captured instead of stored as NaN.
        _probe = _table_to_long_rows(
            _find_table_by_spec(soup, TABLE_SECTION_SPECS["quarterly_pl"]), ticker
        )
        if _quarterly_npa_is_blank(_probe) and url_used.endswith("/consolidated/"):
            standalone_url = url_used.replace("/consolidated/", "/")
            try:
                r_sa = session.get(standalone_url, timeout=30, allow_redirects=True)
                if r_sa.status_code == 200:
                    sa_soup = BeautifulSoup(r_sa.text, "html.parser")
                    sa_probe = _table_to_long_rows(
                        _find_table_by_spec(sa_soup, TABLE_SECTION_SPECS["quarterly_pl"]), ticker
                    )
                    if not _quarterly_npa_is_blank(sa_probe):
                        soup = sa_soup
                        url_used = standalone_url
                        sections.append("standalone_fallback_for_npa")
            except Exception:
                pass

        # Section I
        metadata = _extract_metadata(soup, ticker, url_used)
        if metadata.get("company_name") or metadata.get("about_text"):
            sections.append("I_company_metadata")

        # Section A
        key_ratios = _extract_key_ratios(soup)
        if key_ratios:
            sections.append("A_key_ratios")
            rows_total += len(key_ratios)

        # Sections B-G
        quarterly_rows = _table_to_long_rows(_find_table_by_spec(soup, TABLE_SECTION_SPECS["quarterly_pl"]), ticker)
        annual_pl_rows = _table_to_long_rows(_find_table_by_spec(soup, TABLE_SECTION_SPECS["annual_pl"]), ticker)
        annual_bs_rows = _table_to_long_rows(_find_table_by_spec(soup, TABLE_SECTION_SPECS["annual_bs"]), ticker)
        annual_cf_rows = _table_to_long_rows(_find_table_by_spec(soup, TABLE_SECTION_SPECS["annual_cf"]), ticker)
        annual_ratios_rows = _table_to_long_rows(_find_table_by_spec(soup, TABLE_SECTION_SPECS["annual_ratios"]), ticker)
        shareholding_rows = _table_to_long_rows(_find_table_by_spec(soup, TABLE_SECTION_SPECS["shareholding"]), ticker)

        if quarterly_rows:
            sections.append("B_quarterly_results")
            rows_total += len(quarterly_rows)
        if annual_pl_rows:
            sections.append("C_annual_profit_loss")
            rows_total += len(annual_pl_rows)
        if annual_bs_rows:
            sections.append("D_annual_balance_sheet")
            rows_total += len(annual_bs_rows)
        if annual_cf_rows:
            sections.append("E_annual_cash_flow")
            rows_total += len(annual_cf_rows)
        if annual_ratios_rows:
            sections.append("F_annual_ratios")
            rows_total += len(annual_ratios_rows)
        if shareholding_rows:
            sections.append("G_shareholding_pattern")
            rows_total += len(shareholding_rows)

        # Section H
        peers = _extract_peers(soup)
        if peers:
            sections.append("H_peers_comparison")
            rows_total += len(peers)

        # Section J
        pros_cons = _extract_pros_cons(soup)
        if pros_cons.get("pros") or pros_cons.get("cons"):
            sections.append("J_pros_cons")
            rows_total += len(pros_cons.get("pros", [])) + len(pros_cons.get("cons", []))

        # Writes
        _write_json(output_dir / "metadata" / f"{ticker_slug}_metadata.json", metadata)
        _write_json(output_dir / "metadata" / f"{ticker_slug}_key_ratios.json", key_ratios)
        _write_json(output_dir / "metadata" / f"{ticker_slug}_peers.json", peers)
        _write_json(output_dir / "metadata" / f"{ticker_slug}_pros_cons.json", pros_cons)

        _write_long_csv(output_dir / "financials" / f"{ticker_slug}_quarterly_pl.csv", quarterly_rows)
        _write_long_csv(output_dir / "financials" / f"{ticker_slug}_annual_pl.csv", annual_pl_rows)
        _write_long_csv(output_dir / "financials" / f"{ticker_slug}_annual_bs.csv", annual_bs_rows)
        _write_long_csv(output_dir / "financials" / f"{ticker_slug}_annual_cf.csv", annual_cf_rows)
        _write_long_csv(output_dir / "financials" / f"{ticker_slug}_annual_ratios.csv", annual_ratios_rows)
        _write_long_csv(output_dir / "shareholding" / f"{ticker_slug}_shareholding.csv", shareholding_rows)

        core_files_exist = _all_resume_files_exist(output_dir, ticker_slug)
        status = "success" if core_files_exist else "partial"
        if status == "partial" and not sections:
            status = "failed"

        return ScrapeResult(
            ticker=ticker,
            url_used=url_used,
            status=status,
            sections_scraped=sections,
            rows_scraped_total=rows_total,
            error_message="",
            duration_seconds=time.time() - started,
        )
    except FileNotFoundError as exc:
        return ScrapeResult(
            ticker=ticker,
            url_used=url_used,
            status="not_found",
            sections_scraped=sections,
            rows_scraped_total=rows_total,
            error_message=str(exc),
            duration_seconds=time.time() - started,
        )
    except Exception as exc:  # noqa: BLE001
        return ScrapeResult(
            ticker=ticker,
            url_used=url_used,
            status="failed",
            sections_scraped=sections,
            rows_scraped_total=rows_total,
            error_message=str(exc),
            duration_seconds=time.time() - started,
        )


def _append_log(output_dir: Path, rows: list[ScrapeResult]) -> None:
    log_path = output_dir / "scrape_log.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if write_header:
            writer.writeheader()
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        for r in rows:
            writer.writerow(
                {
                    "ticker": r.ticker,
                    "url_used": r.url_used,
                    "status": r.status,
                    "sections_scraped": ",".join(r.sections_scraped),
                    "rows_scraped_total": int(r.rows_scraped_total),
                    "error_message": r.error_message,
                    "timestamp": ts,
                    "duration_seconds": round(float(r.duration_seconds), 3),
                }
            )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scrape comprehensive Screener.in company fundamentals.")
    p.add_argument(
        "--ticker-file",
        type=str,
        default="universe/nifty500.csv",
        help="Ticker source file (one ticker per line OR CSV with ticker/symbol column).",
    )
    p.add_argument("--max-tickers", type=int, default=0, help="Limit to first N tickers (0 = all).")
    p.add_argument("--resume", action="store_true", help="Skip tickers that already have all required core files AND are fresh (see --max-age-days).")
    p.add_argument(
        "--max-age-days",
        type=int,
        default=45,
        help="Under --resume, only skip a ticker whose core files are newer than this many days "
        "(quarterly cadence ~90d; 45 forces a re-scrape well within each quarter). 0 = existence-only (legacy).",
    )
    p.add_argument("--delay-min", type=float, default=4.0, help="Minimum delay between companies (seconds).")
    p.add_argument("--delay-max", type=float, default=8.0, help="Maximum delay between companies (seconds).")
    p.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory root.")
    return p


def _summary(results: list[ScrapeResult], elapsed_seconds: float) -> None:
    attempted = len(results)
    succeeded = sum(1 for r in results if r.status in {"success", "skipped_resume"})
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    not_found = sum(1 for r in results if r.status == "not_found")
    avg = (elapsed_seconds / attempted) if attempted else 0.0
    failed_tk = [r.ticker for r in results if r.status == "failed"]
    partial_tk = [r.ticker for r in results if r.status == "partial"]

    print("=== Screener Scrape Summary ===")
    print(f"Total tickers attempted: {attempted}")
    print(f"Succeeded (all files): {succeeded}")
    print(f"Partial (some files): {partial}")
    print(f"Failed: {failed}")
    print(f"Not found (404): {not_found}")
    print(f"Total time: {elapsed_seconds / 60.0:.2f} minutes")
    print(f"Average time per ticker: {avg:.2f} seconds")
    print()
    print(f"Failed tickers: {failed_tk}")
    print(f"Partial tickers: {partial_tk}")


def main() -> int:
    args = _build_parser().parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tickers = _load_tickers(Path(args.ticker_file))
    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[: int(args.max_tickers)]
    if not tickers:
        print("No tickers found.")
        return 0

    if float(args.delay_min) <= 0 or float(args.delay_max) <= 0:
        raise ValueError("delay range must be > 0")
    if float(args.delay_min) > float(args.delay_max):
        raise ValueError("delay_min cannot be greater than delay_max")

    session = requests.Session()
    session.headers.update(HEADERS)

    run_started = time.time()
    all_results: list[ScrapeResult] = []

    for idx, ticker in enumerate(tickers):
        ticker_slug = _ticker_to_slug(ticker)
        if bool(args.resume) and _resume_files_are_fresh(out_dir, ticker_slug, int(args.max_age_days)):
            result = ScrapeResult(
                ticker=ticker,
                url_used="",
                status="skipped_resume",
                sections_scraped=["resume_skip"],
                rows_scraped_total=0,
                error_message="",
                duration_seconds=0.0,
            )
            all_results.append(result)
        else:
            result = scrape_ticker(session=session, ticker=ticker, output_dir=out_dir)
            all_results.append(result)

        print(
            f"[{idx + 1}/{len(tickers)}] {ticker} status={result.status} rows={result.rows_scraped_total}",
            flush=True,
        )

        # Strictly enforce delay between companies (no parallel/no exceptions).
        if idx < len(tickers) - 1:
            delay = random.uniform(float(args.delay_min), float(args.delay_max))
            time.sleep(delay)

    _append_log(out_dir, all_results)
    _summary(all_results, elapsed_seconds=time.time() - run_started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
