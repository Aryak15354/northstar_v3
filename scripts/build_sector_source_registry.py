#!/usr/bin/env python3
"""Generate the sector data-source registry (Phase 2 of the acquisition plan).

Produces, from the universe + BSE mapping (both already in-repo and verified):

* ``config/sector_data_sources.yaml``  — per-company discovery routes: normalized
  category, NSE symbol, BSE security code, Screener slug, expected XBRL taxonomy,
  and the supplement documents each category needs (NIM/CASA/Stage-3/EV etc.).
* ``config/document_patterns.yaml``    — filename/subject regexes that classify a
  filing attachment as results / presentation / transcript / Basel / EV / press.
* ``reports/data_acquisition/metric_coverage_matrix.csv`` — company x metric x
  source x status, the living EXP-13 readiness scoreboard (recomputed each run
  from whatever the pipelines have actually landed).

The registry stores *discovery routes*, never per-quarter document URLs (those rot
every quarter). ``ir_url`` is intentionally left for the document-discovery layer to
resolve and verify; NSE/BSE ids here are the stable, verified anchors.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_FILE = PROJECT_ROOT / "universe" / "nifty500.csv"
BSE_MAP_FILE = PROJECT_ROOT / "data" / "raw" / "nifty500_bse_mapping.csv"
REGISTRY_OUT = PROJECT_ROOT / "config" / "sector_data_sources.yaml"
PATTERNS_OUT = PROJECT_ROOT / "config" / "document_patterns.yaml"
COVERAGE_OUT = PROJECT_ROOT / "reports" / "data_acquisition" / "metric_coverage_matrix.csv"
CREDIT_PARQUET = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "credit_quarterly.parquet"
SCREENER_QUARTERLY = PROJECT_ROOT / "data" / "processed" / "screener_fundamentals_quarterly.csv"


# --- category classification ------------------------------------------------

# (keyword in lowercased subsector/name) -> normalized category. Order matters:
# earlier, more specific rules win.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("small finance bank", "sfb"),
    ("public sector bank", "psu_bank"),
    ("private sector bank", "private_bank"),
    ("bank", "bank_generic"),  # refined below by name if not caught above
    ("life insurance", "life_insurer"),
    ("general insurance", "general_insurer"),
    ("insurance", "general_insurer"),
    ("housing finance", "hfc"),
    ("affordable housing", "hfc"),
    ("asset management", "amc"),
    ("wealth management", "amc"),
    ("power exchange", "exchange"),
    ("exchange", "exchange"),
    ("depositor", "depository"),
    ("stockbrok", "broker"),
    ("broking", "broker"),
    ("digital payments", "fintech"),
    ("fintech", "fintech"),
    ("payment", "fintech"),
    ("gold loan", "nbfc"),
    ("vehicle finance", "nbfc"),
    ("consumer finance", "nbfc"),
    ("retail finance", "nbfc"),
    ("power sector lending", "nbfc"),
    ("nbfc", "nbfc"),
    ("finance", "nbfc"),
    ("diversified financial", "diversified_financial"),
]

# PSU bank names (for names where subsector only says "Public Sector Bank")
KNOWN_PSU_BANKS = {
    "SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK", "BANKINDIA", "INDIANB",
    "IOB", "CENTRALBK", "UCOBANK", "MAHABANK", "PSB", "IDBI",
}
KNOWN_PRIVATE_BANKS = {
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "IDFCFIRSTB",
    "FEDERALBNK", "BANDHANBNK", "RBLBANK", "YESBANK", "CUB", "KARURVYSYA",
    "J&KBANK", "SOUTHBANK", "DCBBANK", "TMB",
}

# category -> expected NSE XBRL taxonomy for quarterly results
CATEGORY_TAXONOMY = {
    "private_bank": "banking",
    "psu_bank": "banking",
    "sfb": "banking",
    "nbfc": "nbfc",
    "hfc": "nbfc",
    "amc": "nbfc",
    "life_insurer": "insurance",
    "general_insurer": "insurance",
    "exchange": "generic",
    "depository": "generic",
    "broker": "generic",
    "fintech": "generic",
    "diversified_financial": "generic",
}

# category -> supplement documents (metrics the XBRL/Screener don't fully cover)
CATEGORY_SUPPLEMENTS = {
    "private_bank": ["investor_presentation", "basel_pillar3"],
    "psu_bank": ["investor_presentation", "basel_pillar3"],
    "sfb": ["investor_presentation", "basel_pillar3"],
    "nbfc": ["investor_presentation"],
    "hfc": ["investor_presentation"],
    "amc": ["investor_presentation"],
    "life_insurer": ["public_disclosure", "embedded_value"],
    "general_insurer": ["public_disclosure"],
    "exchange": ["investor_presentation"],
    "depository": ["investor_presentation"],
    "broker": ["investor_presentation"],
    "fintech": ["investor_presentation"],
    "diversified_financial": ["investor_presentation"],
}

# category -> credit/operational metrics we want (for the coverage matrix)
CATEGORY_METRICS = {
    "private_bank": ["gnpa_pct", "nnpa_pct", "net_interest_income", "provisions", "roa", "cet1_ratio", "casa_pct", "nim"],
    "psu_bank": ["gnpa_pct", "nnpa_pct", "net_interest_income", "provisions", "roa", "cet1_ratio", "casa_pct", "nim"],
    "sfb": ["gnpa_pct", "nnpa_pct", "net_interest_income", "provisions", "roa", "cet1_ratio", "nim"],
    "nbfc": ["impairment_financial", "interest_earned", "profit_before_tax", "gnpa_pct", "aum", "stage3_pct"],
    "hfc": ["impairment_financial", "interest_earned", "gnpa_pct", "aum", "stage3_pct"],
    "amc": ["revenue_from_ops", "profit_before_tax", "aum"],
    "life_insurer": ["apes", "embedded_value", "vnb_margin"],
    "general_insurer": ["gross_premium", "combined_ratio"],
    "exchange": ["revenue_from_ops", "profit_before_tax"],
    "depository": ["revenue_from_ops", "profit_before_tax"],
    "broker": ["revenue_from_ops", "profit_before_tax"],
    "fintech": ["revenue_from_ops", "profit_before_tax"],
    "diversified_financial": ["revenue_from_ops", "profit_before_tax"],
}


# Explicit overrides for names whose Subsector is "See Industry Column" or an
# ambiguous holding-company label. These are hand-verified classifications.
SYMBOL_CATEGORY_OVERRIDES = {
    "BSE": "exchange",
    "CAMS": "amc",            # RTA to mutual funds; AUM-linked fee model
    "KFINTECH": "amc",        # RTA / investor-solutions
    "CREDITACC": "nbfc",      # microfinance
    "CGCL": "nbfc",
    "HUDCO": "hfc",
    "IFCI": "nbfc",
    "IREDA": "nbfc",          # renewable-energy lending NBFC
    "JIOFIN": "nbfc",
    "POONAWALLA": "nbfc",
    "SAMMAANCAP": "hfc",      # ex-Indiabulls Housing
    "NIACL": "general_insurer",
    "CRISIL": "diversified_financial",  # rating agency (no XBRL credit metrics)
    "CHOLAHLDNG": "diversified_financial",
    "BAJAJHLDNG": "diversified_financial",
    "MAHSCOOTER": "diversified_financial",
    "TATAINVEST": "diversified_financial",
    "AIIL": "diversified_financial",
    "MFSL": "life_insurer",   # holding co for Max Life
    "JMFINANCIL": "nbfc",
    "MOTILALOFS": "broker",
    "CHOICEIN": "broker",
    "ABCAPITAL": "diversified_financial",
    "BAJAJFINSV": "diversified_financial",
}


def classify(symbol: str, subsector: str, name: str) -> str:
    if symbol in SYMBOL_CATEGORY_OVERRIDES:
        return SYMBOL_CATEGORY_OVERRIDES[symbol]
    text = f"{subsector} {name}".lower()
    cat = None
    for kw, c in CATEGORY_RULES:
        if kw in text:
            cat = c
            break
    if cat == "bank_generic" or (cat is None and "bank" in text):
        if symbol in KNOWN_PSU_BANKS:
            return "psu_bank"
        if symbol in KNOWN_PRIVATE_BANKS:
            return "private_bank"
        return "private_bank"
    if cat is None:
        return "diversified_financial"
    return cat


# --- registry build ---------------------------------------------------------

def build_registry() -> dict:
    uni = pd.read_csv(UNIVERSE_FILE)
    bse = pd.read_csv(BSE_MAP_FILE)
    bse_by_symbol = {
        str(r["Symbol"]).strip().upper(): r["bse_code"]
        for _, r in bse.iterrows()
        if pd.notna(r.get("bse_code"))
    }
    fin = uni[uni["Industry"] == "Financial Services"].copy()

    registry: dict[str, dict] = {}
    for _, row in fin.iterrows():
        symbol = str(row["Symbol"]).strip().upper()
        name = str(row.get("Company Name") or "").strip()
        subsector = str(row.get("Subsector") or "").strip()
        category = classify(symbol, subsector, name)
        bse_code = bse_by_symbol.get(symbol)
        bse_code_int = int(bse_code) if pd.notna(bse_code) else None
        registry[symbol] = {
            "company_name": name,
            "category": category,
            "subsector_raw": subsector,
            "nse": {"symbol": symbol},
            "bse": {"security_code": bse_code_int},
            "screener_slug": symbol,
            "xbrl_taxonomy": CATEGORY_TAXONOMY.get(category, "generic"),
            "supplement_docs": CATEGORY_SUPPLEMENTS.get(category, ["investor_presentation"]),
            "ir_url": None,  # resolved + verified by the document-discovery layer
            "metrics_wanted": CATEGORY_METRICS.get(category, []),
        }
    return registry


DOCUMENT_PATTERNS = {
    "financial_results": {
        "subject": [r"financial result", r"unaudited.*result", r"audited.*result", r"quarterly result"],
        "filename": [r"result", r"outcome.*board"],
    },
    "investor_presentation": {
        "subject": [r"investor present", r"earnings present", r"analyst present", r"investor update"],
        "filename": [r"present", r"investor", r"earnings.?deck"],
    },
    "earnings_transcript": {
        "subject": [r"transcript", r"earnings call", r"conference call", r"concall"],
        "filename": [r"transcript", r"concall", r"call"],
    },
    "basel_pillar3": {
        "subject": [r"basel", r"pillar 3", r"pillar iii", r"capital adequacy"],
        "filename": [r"basel", r"pillar"],
    },
    "embedded_value": {
        "subject": [r"embedded value", r"indian embedded value", r"\biev\b"],
        "filename": [r"embedded", r"iev"],
    },
    "public_disclosure": {
        "subject": [r"public disclosure", r"l-\d+", r"irdai", r"segment reporting"],
        "filename": [r"disclosure", r"public"],
    },
    "press_release": {
        "subject": [r"press release", r"media release", r"news release"],
        "filename": [r"press", r"release", r"media"],
    },
}


# --- coverage matrix --------------------------------------------------------

def _load_credit() -> pd.DataFrame:
    if CREDIT_PARQUET.exists():
        return pd.read_parquet(CREDIT_PARQUET)
    return pd.DataFrame()


def _load_screener() -> pd.DataFrame:
    if SCREENER_QUARTERLY.exists():
        return pd.read_csv(SCREENER_QUARTERLY)
    return pd.DataFrame()


def build_coverage_matrix(registry: dict) -> pd.DataFrame:
    credit = _load_credit()
    screener = _load_screener()
    credit_syms = set(credit["symbol"].unique()) if not credit.empty else set()
    screener_syms = (
        set(screener["ticker"].str.replace(".NS", "", regex=False).str.upper())
        if not screener.empty and "ticker" in screener
        else set()
    )
    # per-symbol non-null metric presence in credit parquet
    credit_metric_cov: dict[str, set] = {}
    if not credit.empty:
        for sym, g in credit.groupby("symbol"):
            present = {c for c in g.columns if g[c].notna().any()}
            credit_metric_cov[sym] = present

    rows = []
    for symbol, meta in registry.items():
        for metric in meta["metrics_wanted"]:
            source = "none"
            status = "MISSING"
            if metric in credit_metric_cov.get(symbol, set()):
                source, status = "nse_xbrl", "AVAILABLE"
            elif metric in {"gnpa_pct", "nnpa_pct"} and symbol in screener_syms:
                source, status = "screener", "AVAILABLE"
            elif metric in {"casa_pct", "nim", "aum", "stage3_pct", "combined_ratio",
                            "embedded_value", "vnb_margin", "apes", "gross_premium"}:
                source, status = meta["supplement_docs"][0], "NEEDS_DOC_EXTRACTION"
            rows.append({
                "symbol": symbol,
                "category": meta["category"],
                "metric": metric,
                "source": source,
                "status": status,
            })
    return pd.DataFrame(rows)


def main() -> int:
    registry = build_registry()
    REGISTRY_OUT.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_OUT.open("w") as fh:
        yaml.safe_dump(
            {"_generated_by": "scripts/build_sector_source_registry.py", "companies": registry},
            fh, sort_keys=True, default_flow_style=False,
        )
    with PATTERNS_OUT.open("w") as fh:
        yaml.safe_dump(DOCUMENT_PATTERNS, fh, sort_keys=True, default_flow_style=False)

    coverage = build_coverage_matrix(registry)
    COVERAGE_OUT.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(COVERAGE_OUT, index=False)

    # summary
    cats = pd.Series([m["category"] for m in registry.values()]).value_counts()
    print(f"[registry] {len(registry)} financial-services companies")
    print("[registry] categories:")
    for c, n in cats.items():
        print(f"    {c:22s} {n}")
    if not coverage.empty:
        avail = coverage[coverage["status"] == "AVAILABLE"]
        print(f"[coverage] {len(avail)}/{len(coverage)} metric-cells AVAILABLE today")
        print(f"[coverage] by status: {coverage['status'].value_counts().to_dict()}")
    print(f"[registry] wrote {REGISTRY_OUT}")
    print(f"[registry] wrote {PATTERNS_OUT}")
    print(f"[registry] wrote {COVERAGE_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
