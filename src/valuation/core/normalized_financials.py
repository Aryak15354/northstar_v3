"""
Financial Normalizer - Handles accounting differences across sectors
Adjusts for revenue recognition, capitalization policies, and reporting standards
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass

from .screener_field_map import (
    REQUIRED_FOR_DCF,
    REQUIRED_FOR_MOAT,
    SCREENER_ALIASES_TO_INTERNAL,
    SCREENER_TO_INTERNAL,
)

logger = logging.getLogger(__name__)


@dataclass
class FinancialAdjustments:
    """Container for financial adjustments"""
    adjusted_revenue: float
    adjusted_ebit: float
    adjusted_ebitda: float
    adjusted_capex: float
    maintenance_capex: float
    growth_capex: float
    adjusted_working_capital: float
    adjustments_made: Dict[str, str]


class FinancialNormalizer:
    """
    Normalizes financial statements across different accounting treatments
    
    Key adjustments:
    1. Revenue recognition differences (SaaS, construction, auto)
    2. R&D capitalization vs expensing
    3. Lease accounting (IFRS 16 impact)
    4. Depreciation policy normalization
    5. Working capital manipulation detection
    """
    
    SCREENER_DATA_PATH = Path("data/raw/vendors/screener/financials")
    SCREENER_METADATA_PATH = Path("data/raw/vendors/screener/metadata")
    REPORTING_LAG_DAYS = 75
    QUARTERLY_REPORTING_LAG_DAYS = 45

    def __init__(self, config: Optional[dict] = None):
        self._config = dict(config or {})
        self.adjustments_log = []
        self.reporting_lag_days = int(
            self._config.get("reporting_lag_days", self.REPORTING_LAG_DAYS) or self.REPORTING_LAG_DAYS
        )
        self.quarterly_reporting_lag_days = int(
            self._config.get("quarterly_reporting_lag_days", self.QUARTERLY_REPORTING_LAG_DAYS)
            or self.QUARTERLY_REPORTING_LAG_DAYS
        )
        self.data_path = Path(
            self._config.get("screener_data_path", self.SCREENER_DATA_PATH)
        )
        self.metadata_path = Path(
            self._config.get("screener_metadata_path", self.SCREENER_METADATA_PATH)
        )
    
    def normalize_financials(
        self,
        ticker: str,
        sector: str,
        revenue: float,
        ebit: float,
        ebitda: float,
        capex: float,
        depreciation: float,
        amortization: float,
        rd_expense: float,
        capitalized_rd: float,
        rd_amortization: float,
        receivables: float,
        inventory: float,
        payables: float,
        deferred_revenue: float,
        lease_liabilities: float,
        gross_ppe: float,
        **kwargs
    ) -> FinancialAdjustments:
        """
        Normalize financial statements with sector-aware adjustments
        """
        adjustments = {}
        
        # 1. Adjust for R&D capitalization
        if capitalized_rd > 0:
            # Expense capitalized R&D, add back amortization
            adjusted_ebit = ebit - capitalized_rd + rd_amortization
            adjustments['rd_adjustment'] = f"Expensed ${capitalized_rd/1e6:.1f}M capitalized R&D"
        else:
            adjusted_ebit = ebit
        
        # 2. Adjust EBITDA for lease accounting (IFRS 16)
        if lease_liabilities > 0:
            # Approximate lease expense from liability
            implied_lease_expense = lease_liabilities * 0.08  # Assume 8% rate
            adjusted_ebitda = ebitda - implied_lease_expense
            adjustments['lease_adjustment'] = f"Adjusted for ${implied_lease_expense/1e6:.1f}M lease expense"
        else:
            adjusted_ebitda = ebitda
        
        # 3. Revenue recognition adjustments
        adjusted_revenue = self._adjust_revenue_recognition(
            revenue, receivables, deferred_revenue, sector, adjustments
        )
        
        # 4. Separate maintenance vs growth capex
        maintenance_capex, growth_capex = self._split_capex(
            capex, depreciation, revenue, sector
        )
        adjustments['capex_split'] = f"Maintenance: ${maintenance_capex/1e6:.1f}M, Growth: ${growth_capex/1e6:.1f}M"
        
        # 5. Normalize depreciation if outlier
        adjusted_capex = self._normalize_depreciation_policy(
            capex, depreciation, gross_ppe, sector, adjustments
        )
        
        # 6. Working capital adjustments
        adjusted_wc = self._calculate_adjusted_working_capital(
            receivables, inventory, payables, revenue, sector, adjustments
        )
        
        return FinancialAdjustments(
            adjusted_revenue=adjusted_revenue,
            adjusted_ebit=adjusted_ebit,
            adjusted_ebitda=adjusted_ebitda,
            adjusted_capex=adjusted_capex,
            maintenance_capex=maintenance_capex,
            growth_capex=growth_capex,
            adjusted_working_capital=adjusted_wc,
            adjustments_made=adjustments
        )
    
    def _adjust_revenue_recognition(
        self,
        revenue: float,
        receivables: float,
        deferred_revenue: float,
        sector: str,
        adjustments: Dict
    ) -> float:
        """
        Adjust revenue for recognition timing differences
        """
        # Check for receivables growing faster than revenue (red flag)
        receivables_days = (receivables / revenue) * 365 if revenue > 0 else 0
        
        # Sector-specific thresholds
        normal_receivables_days = {
            'Technology': 60,
            'Healthcare': 70,
            'Industrials': 75,
            'Consumer': 45,
            'Financials': 30,
        }
        
        threshold = normal_receivables_days.get(sector, 60)
        
        if receivables_days > threshold * 1.5:
            # Potential revenue stuffing - adjust down
            adjustment_factor = threshold / receivables_days
            adjusted_revenue = revenue * adjustment_factor
            adjustments['revenue_quality'] = f"Adjusted for high receivables days ({receivables_days:.0f} vs {threshold})"
            return adjusted_revenue
        
        # Adjust for deferred revenue changes (SaaS, subscriptions)
        if deferred_revenue > revenue * 0.1:  # Material deferred revenue
            # This is actually good - revenue is more predictable
            adjustments['deferred_revenue'] = f"High deferred revenue: ${deferred_revenue/1e6:.1f}M (quality signal)"
        
        return revenue
    
    def _split_capex(
        self,
        capex: float,
        depreciation: float,
        revenue: float,
        sector: str
    ) -> tuple:
        """
        Split capex into maintenance and growth components
        
        Maintenance capex approximation:
        - Asset-heavy: ~100% of depreciation
        - Asset-light: ~70% of depreciation
        """
        if capex <= 0 or depreciation <= 0:
            return 0, capex
        
        # Sector-specific maintenance ratios
        maintenance_ratios = {
            'Utilities': 1.0,
            'Industrials': 0.95,
            'Materials': 0.90,
            'Energy': 0.95,
            'Technology': 0.70,
            'Healthcare': 0.75,
            'Consumer': 0.80,
        }
        
        ratio = maintenance_ratios.get(sector, 0.85)
        maintenance_capex = depreciation * ratio
        growth_capex = max(0, capex - maintenance_capex)
        
        return maintenance_capex, growth_capex
    
    def _normalize_depreciation_policy(
        self,
        capex: float,
        depreciation: float,
        gross_ppe: float,
        sector: str,
        adjustments: Dict
    ) -> float:
        """
        Check if depreciation policy is aggressive or conservative
        """
        if gross_ppe <= 0:
            return capex
        
        depreciation_rate = depreciation / gross_ppe
        
        # Sector-specific normal ranges
        normal_dep_rates = {
            'Technology': (0.15, 0.25),
            'Industrials': (0.08, 0.15),
            'Utilities': (0.04, 0.08),
            'Consumer': (0.10, 0.18),
        }
        
        low, high = normal_dep_rates.get(sector, (0.08, 0.15))
        
        if depreciation_rate < low:
            adjustments['depreciation'] = f"Conservative depreciation ({depreciation_rate:.1%} vs {low:.1%}-{high:.1%})"
        elif depreciation_rate > high:
            adjustments['depreciation'] = f"Aggressive depreciation ({depreciation_rate:.1%} vs {low:.1%}-{high:.1%})"
        
        return capex
    
    def _calculate_adjusted_working_capital(
        self,
        receivables: float,
        inventory: float,
        payables: float,
        revenue: float,
        sector: str,
        adjustments: Dict
    ) -> float:
        """
        Calculate working capital with quality adjustments
        """
        # Basic working capital
        wc = receivables + inventory - payables
        
        # Check for manipulation
        if revenue > 0:
            receivables_days = (receivables / revenue) * 365
            inventory_days = (inventory / revenue) * 365 if inventory > 0 else 0
            payables_days = (payables / revenue) * 365
            
            cash_conversion_cycle = receivables_days + inventory_days - payables_days
            
            # Sector benchmarks
            normal_ccc = {
                'Technology': 30,
                'Consumer': 45,
                'Industrials': 60,
                'Healthcare': 50,
            }
            
            benchmark = normal_ccc.get(sector, 50)
            
            if cash_conversion_cycle > benchmark * 1.5:
                adjustments['working_capital'] = f"High CCC: {cash_conversion_cycle:.0f} days vs {benchmark} benchmark"
            elif cash_conversion_cycle < 0:
                adjustments['working_capital'] = f"Negative CCC: {cash_conversion_cycle:.0f} days (strong position)"
        
        return wc
    
    def normalize_dataframe(self, df: pd.DataFrame, sector_col: str = 'sector') -> pd.DataFrame:
        """
        Normalize an entire dataframe of financial data
        """
        results = []
        
        for idx, row in df.iterrows():
            try:
                adj = self.normalize_financials(
                    ticker=row.get('ticker', ''),
                    sector=row.get(sector_col, 'Unknown'),
                    revenue=row.get('revenue', 0),
                    ebit=row.get('ebit', 0),
                    ebitda=row.get('ebitda', 0),
                    capex=row.get('capex', 0),
                    depreciation=row.get('depreciation', 0),
                    amortization=row.get('amortization', 0),
                    rd_expense=row.get('rd_expense', 0),
                    capitalized_rd=row.get('capitalized_rd', 0),
                    rd_amortization=row.get('rd_amortization', 0),
                    receivables=row.get('receivables', 0),
                    inventory=row.get('inventory', 0),
                    payables=row.get('payables', 0),
                    deferred_revenue=row.get('deferred_revenue', 0),
                    lease_liabilities=row.get('lease_liabilities', 0),
                    gross_ppe=row.get('gross_ppe', 0),
                )
                
                results.append({
                    'ticker': row.get('ticker', ''),
                    'adjusted_revenue': adj.adjusted_revenue,
                    'adjusted_ebit': adj.adjusted_ebit,
                    'adjusted_ebitda': adj.adjusted_ebitda,
                    'adjusted_capex': adj.adjusted_capex,
                    'maintenance_capex': adj.maintenance_capex,
                    'growth_capex': adj.growth_capex,
                    'adjusted_working_capital': adj.adjusted_working_capital,
                    'adjustments_count': len(adj.adjustments_made),
                })
            except Exception as e:
                print(f"Error normalizing {row.get('ticker', 'unknown')}: {e}")
                continue
        
        return pd.DataFrame(results)

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(".NS"):
            return s
        if "." in s:
            s = s.split(".", 1)[0]
        return f"{s}.NS"

    def _ticker_slug(self, ticker: str) -> str:
        base = self._normalize_ticker(ticker).replace(".NS", "")
        return re.sub(r"[^A-Z0-9_&-]+", "", base.upper())

    @staticmethod
    def _kaggle_safe_component(value: str) -> str:
        out: list[str] = []
        for ch in str(value):
            if re.fullmatch(r"[A-Za-z0-9._-]", ch):
                out.append(ch)
            else:
                out.append(f"_x{ord(ch):02x}_")
        return "".join(out)

    def _ticker_slug_candidates(self, ticker: str) -> list[str]:
        raw_slug = self._ticker_slug(ticker)
        safe_slug = self._kaggle_safe_component(raw_slug)
        candidates = [raw_slug]
        if safe_slug != raw_slug:
            candidates.append(safe_slug)
        return candidates

    def _statement_paths(self, ticker: str, frequency: str) -> list[Path]:
        paths: list[Path] = []
        seen: set[Path] = set()
        for slug in self._ticker_slug_candidates(ticker):
            pattern = f"{slug}_{str(frequency).strip().lower()}_*.csv"
            for path in sorted(self.data_path.glob(pattern)):
                if path not in seen:
                    seen.add(path)
                    paths.append(path)
        return paths

    def get_source_paths(self, ticker: str, frequency: str = "annual") -> list[Path]:
        return self._statement_paths(ticker, frequency)

    @staticmethod
    def _period_to_timestamp(period: object) -> pd.Timestamp:
        text = str(period or "").strip()
        if not text:
            return pd.NaT
        text = re.sub(r"\s+\d+\s*m$", "", text, flags=re.IGNORECASE).strip()
        if text.upper() == "TTM":
            return pd.NaT
        parsed = pd.to_datetime(f"1 {text}", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return pd.NaT
        return pd.Timestamp(parsed.year, parsed.month, 1) + pd.offsets.MonthEnd(0)

    @staticmethod
    def _filter_statement_complete_rows(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        core_fields = [c for c in ["revenue", "net_profit", "cash_from_operations", "operating_profit"] if c in df.columns]
        if not core_fields:
            return df
        coverage = df[core_fields].notna().sum(axis=1)
        preferred = df.loc[coverage > 0].copy().reset_index(drop=True)
        if preferred.empty:
            return df
        preferred["_statement_coverage"] = coverage.loc[coverage > 0].to_numpy()
        preferred = preferred.sort_values(["period_end", "_statement_coverage"], kind="mergesort")
        return preferred.drop(columns=["_statement_coverage"], errors="ignore")

    def _load_metadata_key_ratios(self, ticker: str) -> dict[str, float]:
        path = None
        for slug in self._ticker_slug_candidates(ticker):
            candidate = self.metadata_path / f"{slug}_key_ratios.json"
            if candidate.exists():
                path = candidate
                break
        if path is None:
            return {}
        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed reading Screener metadata for %s: %s", ticker, exc)
            return {}
        if not isinstance(payload, dict):
            return {}

        current_price = pd.to_numeric(payload.get("Current Price"), errors="coerce")
        market_cap = pd.to_numeric(payload.get("Market Cap"), errors="coerce")
        face_value = pd.to_numeric(payload.get("Face Value"), errors="coerce")
        shares_outstanding = np.nan
        if pd.notna(market_cap) and pd.notna(current_price) and float(current_price) > 0:
            shares_outstanding = float(market_cap) / float(current_price)

        return {
            "current_price": float(current_price) if pd.notna(current_price) else np.nan,
            "market_cap": float(market_cap) if pd.notna(market_cap) else np.nan,
            "face_value": float(face_value) if pd.notna(face_value) else np.nan,
            "book_value": float(pd.to_numeric(payload.get("Book Value"), errors="coerce")) if pd.notna(pd.to_numeric(payload.get("Book Value"), errors="coerce")) else np.nan,
            "roe_pct": float(pd.to_numeric(payload.get("ROE"), errors="coerce")) if pd.notna(pd.to_numeric(payload.get("ROE"), errors="coerce")) else np.nan,
            "roce_pct": float(pd.to_numeric(payload.get("ROCE"), errors="coerce")) if pd.notna(pd.to_numeric(payload.get("ROCE"), errors="coerce")) else np.nan,
            "shares_outstanding": shares_outstanding,
        }

    def _raw_metric_map(self) -> dict[str, str]:
        mapping = dict(SCREENER_TO_INTERNAL)
        mapping.update(SCREENER_ALIASES_TO_INTERNAL)
        return mapping

    def _load_raw_long(self, ticker: str, frequency: str) -> pd.DataFrame:
        paths = self._statement_paths(ticker, frequency)
        if not paths:
            return pd.DataFrame(columns=["ticker", "metric", "period", "value", "statement"])

        frames: list[pd.DataFrame] = []
        for path in paths:
            try:
                df = pd.read_csv(path)
            except Exception as exc:
                logger.warning("Failed reading Screener raw file %s: %s", path, exc)
                continue
            required = {"ticker", "metric", "period", "value"}
            if not required.issubset(set(df.columns)):
                continue
            work = df[list(required)].copy()
            work["statement"] = path.stem
            work["ticker"] = work["ticker"].map(self._normalize_ticker)
            work["metric"] = work["metric"].astype(str).str.strip()
            work["period"] = work["period"].astype(str).str.strip()
            work["value"] = pd.to_numeric(work["value"], errors="coerce")
            work = work[(work["ticker"] != "") & (work["metric"] != "") & (work["period"] != "")]
            frames.append(work)

        if not frames:
            return pd.DataFrame(columns=["ticker", "metric", "period", "value", "statement"])
        return pd.concat(frames, ignore_index=True)

    def _normalize_loaded_frame(self, raw: pd.DataFrame, frequency: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()

        work = raw.copy()
        work["internal_field"] = work["metric"].map(self._raw_metric_map())
        work = work.dropna(subset=["internal_field"]).copy()
        if work.empty:
            return pd.DataFrame()

        work["period_end"] = work["period"].map(self._period_to_timestamp)
        work = work.dropna(subset=["period_end"]).copy()
        work["frequency"] = str(frequency).strip().lower()

        wide = (
            work.pivot_table(
                index=["ticker", "period_end", "frequency"],
                columns="internal_field",
                values="value",
                aggfunc="last",
            )
            .reset_index()
            .sort_values(["ticker", "period_end"], kind="mergesort")
            .reset_index(drop=True)
        )
        wide.columns.name = None

        lag_days = self.reporting_lag_days if str(frequency).lower() == "annual" else self.quarterly_reporting_lag_days
        wide["available_date"] = pd.to_datetime(wide["period_end"], errors="coerce") + pd.Timedelta(days=int(lag_days))

        # PIT-CRITICAL: the Screener key-ratios JSON is a *current-day* snapshot
        # with no as-of date (Current Price, Market Cap, today's ROE/ROCE/Book
        # Value, implied shares). Broadcasting/backfilling it into every
        # historical period stamps today's price and ratios onto years of
        # history — a direct look-ahead leak into the entire val_* feature family.
        # Attach the snapshot ONLY to the most-recent statement row, and only
        # where that row is missing the field. Historical rows compute their own
        # values from the statements (e.g. ROCE via capital employed) or stay
        # NaN. A present-day valuation query resolves to the global-latest row and
        # still sees the snapshot; a historical as-of query resolves to an older
        # row that never carried it.
        metadata = self._load_metadata_key_ratios(str(wide["ticker"].iloc[0]))
        if metadata and len(wide):
            latest_idx = wide.index[-1]
            for key, value in metadata.items():
                if key not in wide.columns:
                    wide[key] = np.nan
                    wide[key] = pd.to_numeric(wide[key], errors="coerce")
                current_latest = pd.to_numeric(pd.Series([wide.at[latest_idx, key]]), errors="coerce").iloc[0]
                if pd.isna(current_latest):
                    wide.at[latest_idx, key] = value

        if "equity_capital" in wide.columns and "face_value" in wide.columns and "shares_outstanding" in wide.columns:
            implied_shares = pd.to_numeric(wide["equity_capital"], errors="coerce") / pd.to_numeric(
                wide["face_value"], errors="coerce"
            ).replace(0.0, np.nan)
            wide["shares_outstanding"] = pd.to_numeric(wide["shares_outstanding"], errors="coerce").fillna(implied_shares)

        if "operating_profit" in wide.columns:
            wide["ebit"] = pd.to_numeric(wide["operating_profit"], errors="coerce")
            wide["operating_income"] = pd.to_numeric(wide["operating_profit"], errors="coerce")
        if "revenue" in wide.columns and "sales" not in wide.columns:
            wide["sales"] = pd.to_numeric(wide["revenue"], errors="coerce")
        if "revenue" not in wide.columns and "sales" in wide.columns:
            wide["revenue"] = pd.to_numeric(wide["sales"], errors="coerce")
        if "current_ratio" in wide.columns:
            wide["current_ratio"] = pd.to_numeric(wide["current_ratio"], errors="coerce")
        if "debt_to_equity" in wide.columns:
            wide["debt_to_equity"] = pd.to_numeric(wide["debt_to_equity"], errors="coerce")
        if "asset_turnover" in wide.columns:
            wide["asset_turnover"] = pd.to_numeric(wide["asset_turnover"], errors="coerce")

        return wide

    def load(self, ticker: str, as_of_date: datetime, frequency: str = "annual") -> pd.DataFrame:
        """Load PIT-safe normalized Screener statements for a ticker."""
        raw = self._load_raw_long(ticker, frequency)
        normalized = self._normalize_loaded_frame(raw, frequency)
        if normalized.empty:
            return pd.DataFrame()

        cutoff = pd.Timestamp(as_of_date)
        normalized["available_date"] = pd.to_datetime(normalized["available_date"], errors="coerce")
        normalized = normalized[normalized["available_date"] <= cutoff].copy()
        if normalized.empty:
            return pd.DataFrame()

        normalized = normalized.sort_values("period_end", kind="mergesort").set_index("period_end", drop=False)
        return normalized

    def load_latest(self, ticker: str, as_of_date: datetime, frequency: str = "annual") -> dict:
        df = self.load(ticker, as_of_date, frequency=frequency)
        if df.empty:
            return {}
        preferred = self._filter_statement_complete_rows(df)
        latest = preferred.iloc[-1].to_dict()
        latest["ticker"] = self._normalize_ticker(ticker)
        return latest

    def load_history(
        self,
        ticker: str,
        as_of_date: datetime,
        n_periods: int = 5,
        frequency: str = "annual",
    ) -> list[dict]:
        df = self.load(ticker, as_of_date, frequency=frequency)
        if df.empty:
            return []
        preferred = self._filter_statement_complete_rows(df)
        rows = preferred.tail(int(max(1, n_periods))).copy()
        return [row.to_dict() for _, row in rows.iterrows()]

    def get_tickers_needing_refresh(
        self,
        data_path: str | Path | None = None,
        max_staleness_days: int = 7,
    ) -> list[str]:
        base = Path(data_path) if data_path is not None else self.data_path
        if not base.exists():
            return []
        stale: list[str] = []
        now = datetime.utcnow()
        for path in sorted(base.glob("*_annual_pl.csv")):
            age_days = (now - datetime.utcfromtimestamp(path.stat().st_mtime)).days
            if age_days > int(max_staleness_days):
                stale.append(self._normalize_ticker(path.stem.split("_", 1)[0]))
        return stale

    def get_coverage(self, as_of_date: datetime, tickers: list[str]) -> dict:
        coverage: dict[str, dict] = {}
        for ticker in tickers:
            fin = self.load_latest(ticker, as_of_date, frequency="annual")
            missing_dcf = [f for f in REQUIRED_FOR_DCF if fin.get(f) is None or pd.isna(fin.get(f))]
            missing_moat = [f for f in REQUIRED_FOR_MOAT if fin.get(f) is None or pd.isna(fin.get(f))]
            coverage[ticker] = {
                "has_data": bool(fin),
                "dcf_fields_present": len(REQUIRED_FOR_DCF) - len(missing_dcf),
                "dcf_fields_missing": missing_dcf,
                "moat_fields_present": len(REQUIRED_FOR_MOAT) - len(missing_moat),
                "moat_fields_missing": missing_moat,
                "has_cashflow": bool(fin) and fin.get("cash_from_operations") is not None and not pd.isna(fin.get("cash_from_operations")),
            }
        return coverage
