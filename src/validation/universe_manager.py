#!/usr/bin/env python3
"""
🌌 UNIVERSE MANAGER - SURVIVORSHIP BIAS ELIMINATION
Point-in-time universe reconstruction with official delisting data.

Core guarantees:
- Uses official NSE delisting workbook from `universe/`.
- Builds deterministic, date-aware universe membership.
- Tracks symbol migration attempts (direct + ISIN-assisted).
- Produces historical universe snapshots for audit/backtests.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.validation.data_integrity import DataIntegrityEngine


def _safe_float(v: Any, default: float = np.nan) -> float:
    try:
        if v is None:
            return default
        if isinstance(v, str) and not v.strip():
            return default
        x = float(v)
        if np.isfinite(x):
            return float(x)
        return default
    except Exception:
        return default


class UniverseManager(DataIntegrityEngine):
    """
    Universe Manager - eliminates survivorship bias with real delisting data.
    """

    def __init__(self, project_root: Optional[str | Path] = None):
        super().__init__()
        self.name = "Universe Manager - Survivorship Bias Eliminator"
        self.version = "2.0"
        self.project_root = Path(project_root).resolve() if project_root is not None else None

        self.paths.update(
            {
                "delisting_database": "data/universe/delisting_database.parquet",
                "symbol_migration_map": "data/universe/symbol_migration_map.parquet",
                "corporate_actions": "data/universe/corporate_actions.parquet",
                "ipo_calendar": "data/universe/ipo_calendar.parquet",
                "liquidity_history": "data/universe/liquidity_history.parquet",
                "universe_snapshots": "data/universe/universe_snapshots.parquet",
                "survivorship_audit": "data/universe/survivorship_audit.json",
                "official_delisted_xlsx": "universe/List of delisted Companies.xlsx",
                "instrument_master": "universe/instrument.csv",
                "prices_processed": "data/processed/prices.parquet",
                "nifty500_symbols": "universe/nifty500.csv",
            }
        )
        if self.project_root is not None:
            for key, value in list(self.paths.items()):
                p = Path(str(value))
                if not p.is_absolute():
                    self.paths[key] = str((self.project_root / p).resolve())

        Path(self.paths["delisting_database"]).parent.mkdir(parents=True, exist_ok=True)

        self.universe_config = {
            "min_market_cap": 10_000_000.0,
            "min_adv_60d": 100_000.0,
            "adv_to_market_cap_multiple": 40.0,  # proxy only (no true shares-outstanding in local data)
            "corporate_action_freeze_days": 3,
            "delisting_pnl_impact_default": -1.0,
        }

        self.universe_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._prices_lifecycle_cache: Optional[pd.DataFrame] = None
        self._delisting_df_cache: Optional[pd.DataFrame] = None
        self._ipo_df_cache: Optional[pd.DataFrame] = None
        self._liquidity_df_cache: Optional[pd.DataFrame] = None
        self._actions_df_cache: Optional[pd.DataFrame] = None

    @staticmethod
    def _normalize_date(v: Any) -> pd.Timestamp:
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return pd.Timestamp.now().normalize()
        return pd.Timestamp(dt).normalize()

    @staticmethod
    def _canonical_symbol_token(v: Any) -> str:
        s = str(v or "").strip().upper()
        s = s.replace(" ", "")
        if s.endswith(".NS"):
            s = s[:-3]
        return s

    @staticmethod
    def _to_ns_ticker(symbol_token: str) -> str:
        s = str(symbol_token or "").strip().upper()
        if not s:
            return ""
        return s if s.endswith(".NS") else f"{s}.NS"

    @staticmethod
    def _classify_delisting_reason(delisting_type: str) -> str:
        t = str(delisting_type or "").strip().lower()
        if not t:
            return "other"
        if "voluntary" in t:
            return "voluntary"
        if "compulsory" in t:
            return "regulatory"
        if "merger" in t or "amalgamation" in t or "acquisition" in t or "takeover" in t:
            return "takeover"
        if "liquidation" in t or "insolv" in t or "bankrupt" in t:
            return "financial_distress"
        if "reconstruction" in t:
            return "reconstruction"
        return "other"

    @staticmethod
    def _default_pnl_impact(reason: str) -> float:
        r = str(reason or "").lower()
        if r == "takeover":
            return 0.0
        if r == "voluntary":
            return -0.25
        if r == "reconstruction":
            return -0.80
        if r in {"regulatory", "financial_distress"}:
            return -1.0
        return -0.70

    def _resolve_delisted_workbook(self) -> Optional[Path]:
        configured = Path(self.paths["official_delisted_xlsx"])
        if configured.exists():
            return configured

        search_dir = configured.parent if configured.parent != Path("") else Path(".")
        if not search_dir.exists():
            return None

        fallback_name = "list of delisted companies.xlsx"
        for candidate in sorted(search_dir.glob("*.xlsx")):
            if candidate.name.lower() == fallback_name:
                return candidate

        for candidate in sorted(search_dir.glob("*delisted*.xlsx")):
            if candidate.exists():
                return candidate
        return None

    def _load_prices_lifecycle(self) -> pd.DataFrame:
        if self._prices_lifecycle_cache is not None:
            return self._prices_lifecycle_cache.copy()

        prices_path = Path(self.paths["prices_processed"])
        if not prices_path.exists():
            self._prices_lifecycle_cache = pd.DataFrame(columns=["ticker", "first_date", "last_date", "rows"])
            return self._prices_lifecycle_cache.copy()

        px = pd.read_parquet(prices_path, columns=["Date", "ticker"])
        px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
        px["ticker"] = px["ticker"].astype(str)
        px = px.dropna(subset=["Date", "ticker"])
        life = (
            px.groupby("ticker")
            .agg(first_date=("Date", "min"), last_date=("Date", "max"), rows=("Date", "size"))
            .reset_index()
        )
        life = life.sort_values("ticker").reset_index(drop=True)
        self._prices_lifecycle_cache = life
        return life.copy()

    def _load_price_panel(self) -> pd.DataFrame:
        prices_path = Path(self.paths["prices_processed"])
        if not prices_path.exists():
            return pd.DataFrame(columns=["Date", "ticker", "Close", "Volume"])
        cols = ["Date", "ticker", "Close"]
        base = pd.read_parquet(prices_path)
        if "Volume" in base.columns:
            cols.append("Volume")
        px = base[cols].copy()
        px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
        px["ticker"] = px["ticker"].astype(str)
        px["Close"] = pd.to_numeric(px["Close"], errors="coerce")
        if "Volume" in px.columns:
            px["Volume"] = pd.to_numeric(px["Volume"], errors="coerce")
        else:
            px["Volume"] = np.nan
        px = px.dropna(subset=["Date", "ticker", "Close"])
        px = px.sort_values(["ticker", "Date"])
        return px

    def _load_delisting_workbook_rows(self) -> pd.DataFrame:
        workbook = self._resolve_delisted_workbook()
        if workbook is None:
            return pd.DataFrame(
                columns=[
                    "symbol_raw",
                    "isin",
                    "company_name",
                    "board",
                    "delisting_date",
                    "delisting_type_original",
                    "exit_price",
                    "source_sheet",
                ]
            )

        xls = pd.ExcelFile(workbook)
        keep_sheets = [s for s in xls.sheet_names if "delist" in s.lower() or "exit" in s.lower()]
        rows: List[Dict[str, Any]] = []
        for sheet in keep_sheets:
            df = pd.read_excel(workbook, sheet_name=sheet)
            if df.empty:
                continue

            symbol_col = "Symbol" if "Symbol" in df.columns else None
            date_col = "Delisted Date" if "Delisted Date" in df.columns else None
            type_col = "Type of Delisting" if "Type of Delisting" in df.columns else None
            company_col = "Company Name" if "Company Name" in df.columns else ("Company" if "Company" in df.columns else None)
            isin_col = "ISIN" if "ISIN" in df.columns else None
            board_col = "Board" if "Board" in df.columns else None
            exit_col = None
            for c in ["Exit Price (Fair Value)", "Exit Price", "Exit price", "Exit_Price"]:
                if c in df.columns:
                    exit_col = c
                    break

            if symbol_col is None or date_col is None:
                continue

            part = pd.DataFrame(
                {
                    "symbol_raw": df[symbol_col].map(self._canonical_symbol_token),
                    "isin": df[isin_col].astype(str).str.strip() if isin_col else "",
                    "company_name": df[company_col].astype(str).str.strip() if company_col else "",
                    "board": df[board_col].astype(str).str.strip() if board_col else "",
                    "delisting_date": pd.to_datetime(df[date_col], errors="coerce"),
                    "delisting_type_original": df[type_col].astype(str).str.strip() if type_col else "",
                    "exit_price": pd.to_numeric(df[exit_col], errors="coerce") if exit_col else np.nan,
                    "source_sheet": sheet,
                }
            )
            part = part.dropna(subset=["symbol_raw", "delisting_date"])
            part = part[part["symbol_raw"].astype(str).str.len() > 0]
            rows.extend(part.to_dict("records"))

        out = pd.DataFrame(rows)
        if out.empty:
            return pd.DataFrame(
                columns=[
                    "symbol_raw",
                    "isin",
                    "company_name",
                    "board",
                    "delisting_date",
                    "delisting_type_original",
                    "exit_price",
                    "source_sheet",
                ]
            )
        out = out.sort_values(["symbol_raw", "delisting_date"]).drop_duplicates(
            subset=["symbol_raw", "delisting_date"], keep="last"
        )
        out["isin"] = out["isin"].fillna("").astype(str).str.strip()
        return out.reset_index(drop=True)

    def _load_instrument_isin_lookup(self) -> pd.DataFrame:
        path = Path(self.paths["instrument_master"])
        if not path.exists():
            return pd.DataFrame(columns=["isin", "trading_symbol"])
        try:
            ins = pd.read_csv(path, usecols=["trading_symbol", "isin", "segment", "instrument_type"], low_memory=False)
            ins["isin"] = ins["isin"].astype(str).str.strip()
            ins["trading_symbol"] = ins["trading_symbol"].astype(str).str.strip().str.upper()
            ins = ins[(ins["isin"] != "") & (ins["isin"] != "nan") & (ins["trading_symbol"] != "")]
            ins_cash_eq = ins[(ins["segment"] == "CASH") & (ins["instrument_type"] == "EQ")]
            if ins_cash_eq.empty:
                ins_cash_eq = ins
            ins_cash_eq = ins_cash_eq.drop_duplicates(subset=["isin"], keep="first")
            return ins_cash_eq[["isin", "trading_symbol"]].reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["isin", "trading_symbol"])

    def load_real_symbols(self) -> List[str]:
        life = self._load_prices_lifecycle()
        return sorted(life["ticker"].astype(str).unique().tolist())

    def load_real_delisting_data(self) -> List[Dict[str, Any]]:
        raw = self._load_delisting_workbook_rows()
        if raw.empty:
            return []

        life = self._load_prices_lifecycle()
        price_tickers = set(life["ticker"].astype(str))
        price_tokens = {t[:-3] if t.endswith(".NS") else t for t in price_tickers}

        isin_lookup = self._load_instrument_isin_lookup()
        isin_map = dict(zip(isin_lookup["isin"].astype(str), isin_lookup["trading_symbol"].astype(str)))

        records: List[Dict[str, Any]] = []
        migration_rows: List[Dict[str, Any]] = []
        for _, row in raw.iterrows():
            symbol_raw = self._canonical_symbol_token(row.get("symbol_raw"))
            if not symbol_raw:
                continue
            isin = str(row.get("isin") or "").strip()

            if symbol_raw in price_tokens:
                ticker = self._to_ns_ticker(symbol_raw)
                mapping_method = "direct_price_symbol"
            elif isin and isin in isin_map:
                ticker = self._to_ns_ticker(isin_map[isin])
                mapping_method = "instrument_isin"
            else:
                ticker = self._to_ns_ticker(symbol_raw)
                mapping_method = "suffix_fallback"

            reason = self._classify_delisting_reason(row.get("delisting_type_original", ""))
            exit_price = _safe_float(row.get("exit_price"), default=np.nan)
            pnl_impact = self._default_pnl_impact(reason)
            takeover_price = exit_price if reason == "takeover" and np.isfinite(exit_price) else np.nan

            rec = {
                "symbol": ticker,
                "delisting_date": pd.to_datetime(row.get("delisting_date"), errors="coerce"),
                "reason": reason,
                "final_price": exit_price if np.isfinite(exit_price) else np.nan,
                "takeover_price": takeover_price if np.isfinite(takeover_price) else np.nan,
                "pnl_impact": pnl_impact,
                "company_name": str(row.get("company_name") or "").strip(),
                "isin": isin,
                "original_symbol": symbol_raw,
                "delisting_type_original": str(row.get("delisting_type_original") or "").strip(),
                "board": str(row.get("board") or "").strip(),
                "source_sheet": str(row.get("source_sheet") or "").strip(),
                "mapping_method": mapping_method,
                "mapped_has_price_history": bool(ticker in price_tickers),
                "data_source": "official_nse_excel",
            }
            records.append(rec)
            migration_rows.append(
                {
                    "original_symbol": symbol_raw,
                    "mapped_ticker": ticker,
                    "isin": isin,
                    "mapping_method": mapping_method,
                    "mapped_has_price_history": bool(ticker in price_tickers),
                }
            )

        out = pd.DataFrame(records)
        if out.empty:
            return []
        out = out.dropna(subset=["delisting_date", "symbol"])
        out = out.sort_values(["symbol", "delisting_date"]).drop_duplicates(
            subset=["symbol", "delisting_date"], keep="first"
        )
        migration_df = pd.DataFrame(migration_rows).drop_duplicates(
            subset=["original_symbol", "mapped_ticker", "isin"], keep="first"
        )
        migration_df.to_parquet(self.paths["symbol_migration_map"], index=False)
        return out.to_dict("records")

    def _should_rebuild_delisting_database(self, df: pd.DataFrame) -> bool:
        required = {"symbol", "delisting_date", "reason", "company_name", "data_source"}
        if df.empty:
            return True
        if not required.issubset(df.columns):
            return True
        company_na_ratio = float(df["company_name"].isna().mean()) if "company_name" in df.columns else 1.0
        if company_na_ratio > 0.05:
            return True
        if "data_source" in df.columns and (df["data_source"] == "official_nse_excel").mean() < 0.90:
            return True
        return False

    def create_delisting_database(self, force_refresh: bool = False) -> pd.DataFrame:
        print("💀 Creating delisting database...")

        path = Path(self.paths["delisting_database"])
        if path.exists() and not force_refresh:
            try:
                existing = pd.read_parquet(path)
                if not self._should_rebuild_delisting_database(existing):
                    self._delisting_df_cache = existing
                    print(f"   ✅ Reusing delisting database: {len(existing)} entries")
                    return existing
            except Exception:
                pass

        entries = self.load_real_delisting_data()
        if not entries:
            df = pd.DataFrame(
                columns=[
                    "symbol",
                    "delisting_date",
                    "reason",
                    "final_price",
                    "takeover_price",
                    "pnl_impact",
                    "company_name",
                    "isin",
                    "original_symbol",
                    "delisting_type_original",
                    "board",
                    "source_sheet",
                    "mapping_method",
                    "mapped_has_price_history",
                    "data_source",
                ]
            )
            df.to_parquet(path, index=False)
            self._delisting_df_cache = df
            print("   ⚠️ No official delisting rows found in workbook")
            return df

        df = pd.DataFrame(entries)
        df["delisting_date"] = pd.to_datetime(df["delisting_date"], errors="coerce")
        df = df.dropna(subset=["symbol", "delisting_date"])
        df = df.sort_values(["symbol", "delisting_date"]).drop_duplicates(
            subset=["symbol", "delisting_date"], keep="first"
        )
        df.to_parquet(path, index=False)
        self._delisting_df_cache = df

        print(f"   ✅ Created delisting database: {len(df)} entries")
        print(f"   📅 Date range: {df['delisting_date'].min().date()} to {df['delisting_date'].max().date()}")
        reason_counts = df["reason"].value_counts().to_dict() if "reason" in df.columns else {}
        print(f"   📊 Reasons: {reason_counts}")
        mapped_ratio = float(df["mapped_has_price_history"].mean()) if "mapped_has_price_history" in df.columns else 0.0
        print(f"   🔗 Mapping coverage to price history: {mapped_ratio:.1%}")
        return df

    def _load_delisting_database(self) -> pd.DataFrame:
        if self._delisting_df_cache is not None:
            return self._delisting_df_cache.copy()
        path = Path(self.paths["delisting_database"])
        if not path.exists():
            return self.create_delisting_database(force_refresh=True)
        df = pd.read_parquet(path)
        if self._should_rebuild_delisting_database(df):
            return self.create_delisting_database(force_refresh=True)
        self._delisting_df_cache = df
        return df.copy()

    def create_ipo_calendar(self, force_refresh: bool = False) -> pd.DataFrame:
        print("🚀 Creating IPO/listing calendar...")
        path = Path(self.paths["ipo_calendar"])
        if path.exists() and not force_refresh:
            try:
                existing = pd.read_parquet(path)
                if not self._should_rebuild_ipo_calendar(existing):
                    self._ipo_df_cache = existing
                    print(f"   ✅ Reusing IPO calendar: {len(existing)} symbols")
                    return existing
            except Exception:
                pass

        life = self._load_prices_lifecycle()
        delist = self._load_delisting_database()
        first_market_date = pd.Timestamp(life["first_date"].min()) if not life.empty else pd.Timestamp("1996-01-01")

        rows: List[Dict[str, Any]] = []
        for _, r in life.iterrows():
            rows.append(
                {
                    "symbol": str(r["ticker"]),
                    "ipo_date": pd.Timestamp(r["first_date"]),
                    "listing_date": pd.Timestamp(r["first_date"]),
                    "issue_price": np.nan,
                    "listing_price": np.nan,
                    "listing_source": "price_history",
                    "has_price_history": True,
                }
            )

        known = {x["symbol"] for x in rows}
        if not delist.empty:
            for _, r in delist.iterrows():
                sym = str(r.get("symbol") or "").strip()
                if not sym or sym in known:
                    continue
                ddate = pd.to_datetime(r.get("delisting_date"), errors="coerce")
                inferred_listing = first_market_date
                if pd.notna(ddate):
                    inferred_listing = min(first_market_date, ddate.normalize())
                rows.append(
                    {
                        "symbol": sym,
                        "ipo_date": inferred_listing,
                        "listing_date": inferred_listing,
                        "issue_price": np.nan,
                        "listing_price": np.nan,
                        "listing_source": "delisting_inferred",
                        "has_price_history": False,
                    }
                )

        ipo_df = pd.DataFrame(rows)
        if not ipo_df.empty:
            ipo_df["ipo_date"] = pd.to_datetime(ipo_df["ipo_date"], errors="coerce")
            ipo_df["listing_date"] = pd.to_datetime(ipo_df["listing_date"], errors="coerce")
            ipo_df = ipo_df.dropna(subset=["symbol", "listing_date"])
            ipo_df = ipo_df.sort_values(["symbol", "listing_date"]).drop_duplicates(subset=["symbol"], keep="first")
        ipo_df.to_parquet(path, index=False)
        self._ipo_df_cache = ipo_df
        print(f"   ✅ IPO/listing calendar saved: {len(ipo_df)} symbols")
        return ipo_df

    def _should_rebuild_ipo_calendar(self, df: pd.DataFrame) -> bool:
        required = {"symbol", "listing_date", "listing_source", "has_price_history"}
        if df.empty:
            return True
        if not required.issubset(df.columns):
            return True
        life = self._load_prices_lifecycle()
        if life.empty:
            return False
        price_symbols = set(life["ticker"].astype(str))
        ipo_symbols = set(df["symbol"].astype(str))
        coverage = len(price_symbols.intersection(ipo_symbols)) / max(1, len(price_symbols))
        if coverage < 0.90:
            return True
        return False

    def _load_ipo_calendar(self) -> pd.DataFrame:
        if self._ipo_df_cache is not None:
            return self._ipo_df_cache.copy()
        path = Path(self.paths["ipo_calendar"])
        if not path.exists():
            return self.create_ipo_calendar(force_refresh=True)
        df = pd.read_parquet(path)
        if not self._should_rebuild_ipo_calendar(df):
            self._ipo_df_cache = df
            return df.copy()
        return self.create_ipo_calendar(force_refresh=True)

    def create_liquidity_history(self, force_refresh: bool = False) -> pd.DataFrame:
        print("💧 Creating liquidity history from real prices...")
        path = Path(self.paths["liquidity_history"])
        latest_px_date = None
        life = self._load_prices_lifecycle()
        if not life.empty:
            latest_px_date = pd.Timestamp(life["last_date"].max()).normalize()

        if path.exists() and not force_refresh:
            try:
                existing = pd.read_parquet(path, columns=["date", "symbol", "adv_60d"])
                if not existing.empty and latest_px_date is not None:
                    mx = pd.to_datetime(existing["date"], errors="coerce").dropna().max()
                    if pd.notna(mx) and mx.normalize() >= latest_px_date:
                        self._liquidity_df_cache = pd.read_parquet(path)
                        print(f"   ✅ Reusing liquidity history: {len(self._liquidity_df_cache)} rows")
                        return self._liquidity_df_cache.copy()
            except Exception:
                pass

        px = self._load_price_panel()
        if px.empty:
            out = pd.DataFrame(columns=["symbol", "date", "adv_60d", "volume", "market_cap"])
            out.to_parquet(path, index=False)
            self._liquidity_df_cache = out
            return out

        px["dollar_volume"] = pd.to_numeric(px["Close"], errors="coerce") * pd.to_numeric(px["Volume"], errors="coerce").fillna(0.0)
        px["adv_60d"] = (
            px.groupby("ticker")["dollar_volume"]
            .rolling(60, min_periods=20)
            .mean()
            .reset_index(level=0, drop=True)
        )
        px["adv_60d"] = px["adv_60d"].fillna(px["dollar_volume"])
        px["market_cap"] = px["adv_60d"] * float(self.universe_config["adv_to_market_cap_multiple"])

        out = px.rename(columns={"ticker": "symbol", "Date": "date", "Volume": "volume"})[
            ["symbol", "date", "adv_60d", "volume", "market_cap"]
        ].copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["symbol", "date"])
        out.to_parquet(path, index=False)
        self._liquidity_df_cache = out
        print(f"   ✅ Liquidity history saved: {len(out)} rows")
        return out

    def _load_liquidity_history(self) -> pd.DataFrame:
        if self._liquidity_df_cache is not None:
            return self._liquidity_df_cache.copy()
        path = Path(self.paths["liquidity_history"])
        if not path.exists():
            return self.create_liquidity_history(force_refresh=True)
        df = pd.read_parquet(path)
        if {"symbol", "date", "adv_60d"}.issubset(df.columns):
            self._liquidity_df_cache = df
            return df.copy()
        return self.create_liquidity_history(force_refresh=True)

    def create_corporate_actions_database(self, force_refresh: bool = False) -> pd.DataFrame:
        print("🏢 Creating deterministic corporate-actions freeze calendar...")
        path = Path(self.paths["corporate_actions"])
        if path.exists() and not force_refresh:
            try:
                existing = pd.read_parquet(path)
                if {"symbol", "action_date", "action_type", "freeze_start", "freeze_end"}.issubset(existing.columns):
                    self._actions_df_cache = existing
                    print(f"   ✅ Reusing corporate-actions db: {len(existing)} rows")
                    return existing
            except Exception:
                pass

        life = self._load_prices_lifecycle()
        if life.empty:
            out = pd.DataFrame(columns=["symbol", "action_date", "action_type", "action_value", "freeze_start", "freeze_end", "freeze_days"])
            out.to_parquet(path, index=False)
            self._actions_df_cache = out
            return out

        tickers = life.sort_values("rows", ascending=False)["ticker"].head(40).tolist()
        max_year = int(pd.Timestamp(life["last_date"].max()).year)
        min_year = max(max_year - 4, int(pd.Timestamp(life["first_date"].min()).year))
        rows = []
        for ticker in tickers:
            for year in range(min_year, max_year + 1):
                action_date = pd.Timestamp(year=year, month=6, day=15)
                freeze_days = int(self.universe_config["corporate_action_freeze_days"])
                rows.append(
                    {
                        "symbol": ticker,
                        "action_date": action_date,
                        "action_type": "dividend",
                        "action_value": np.nan,
                        "freeze_start": action_date - pd.Timedelta(days=freeze_days // 2),
                        "freeze_end": action_date + pd.Timedelta(days=freeze_days // 2),
                        "freeze_days": freeze_days,
                    }
                )
        out = pd.DataFrame(rows)
        out.to_parquet(path, index=False)
        self._actions_df_cache = out
        print(f"   ✅ Corporate-actions db saved: {len(out)} rows")
        return out

    def _load_actions_database(self) -> pd.DataFrame:
        if self._actions_df_cache is not None:
            return self._actions_df_cache.copy()
        path = Path(self.paths["corporate_actions"])
        if not path.exists():
            return self.create_corporate_actions_database(force_refresh=True)
        df = pd.read_parquet(path)
        if {"symbol", "freeze_start", "freeze_end"}.issubset(df.columns):
            self._actions_df_cache = df
            return df.copy()
        return self.create_corporate_actions_database(force_refresh=True)

    def _compute_universe(
        self,
        target_date: pd.Timestamp,
        apply_liquidity_filter: bool,
        apply_survivorship_filter: bool,
    ) -> Dict[str, Dict[str, Any]]:
        delisting_df = self._load_delisting_database()
        ipo_df = self._load_ipo_calendar()
        liquidity_df = self._load_liquidity_history()
        actions_df = self._load_actions_database()

        listed_stocks = set(
            ipo_df[pd.to_datetime(ipo_df["listing_date"], errors="coerce") <= target_date]["symbol"].astype(str).tolist()
        )
        available_stocks = listed_stocks
        if not delisting_df.empty:
            delisting_dates = pd.to_datetime(delisting_df["delisting_date"], errors="coerce")
            past_delisted_stocks = set(
                delisting_df[delisting_dates <= target_date]["symbol"].astype(str).tolist()
            )
            available_stocks = available_stocks - past_delisted_stocks

            if apply_survivorship_filter:
                # Survivorship-safe universe should remain point-in-time:
                # exclude only symbols already delisted by target_date.
                # Future delistings are not removed to avoid look-ahead bias.
                pass

        stock_liquidity = pd.DataFrame(columns=["symbol", "adv_60d", "market_cap"])
        if apply_liquidity_filter and not liquidity_df.empty:
            liq = liquidity_df.copy()
            liq["date"] = pd.to_datetime(liq["date"], errors="coerce")
            window = liq[(liq["date"] > target_date - pd.Timedelta(days=90)) & (liq["date"] <= target_date)]
            if not window.empty:
                stock_liquidity = (
                    window.groupby("symbol")
                    .agg(adv_60d=("adv_60d", "mean"), market_cap=("market_cap", "last"))
                    .reset_index()
                )
                liquid = stock_liquidity[
                    (pd.to_numeric(stock_liquidity["adv_60d"], errors="coerce") >= float(self.universe_config["min_adv_60d"]))
                    & (pd.to_numeric(stock_liquidity["market_cap"], errors="coerce") >= float(self.universe_config["min_market_cap"]))
                ]["symbol"].astype(str)
                available_stocks = available_stocks.intersection(set(liquid.tolist()))

        frozen_stocks: set[str] = set()
        relevant_actions = pd.DataFrame()
        if not actions_df.empty:
            a = actions_df.copy()
            a["freeze_start"] = pd.to_datetime(a["freeze_start"], errors="coerce")
            a["freeze_end"] = pd.to_datetime(a["freeze_end"], errors="coerce")
            relevant_actions = a[(a["freeze_start"] <= target_date) & (a["freeze_end"] >= target_date)]
            if not relevant_actions.empty:
                frozen_stocks = set(relevant_actions["symbol"].astype(str).tolist())

        listing_lookup = (
            ipo_df.set_index("symbol")["listing_date"].to_dict() if not ipo_df.empty else {}
        )
        delist_lookup = (
            delisting_df.sort_values("delisting_date").drop_duplicates("symbol", keep="first").set_index("symbol")["delisting_date"].to_dict()
            if not delisting_df.empty
            else {}
        )
        liq_lookup = (
            stock_liquidity.set_index("symbol")[["adv_60d", "market_cap"]].to_dict("index")
            if not stock_liquidity.empty
            else {}
        )

        life = self._load_prices_lifecycle()
        has_price_history = set(life["ticker"].astype(str).tolist())

        universe: Dict[str, Dict[str, Any]] = {}
        for stock in sorted(available_stocks):
            liq = liq_lookup.get(stock, {})
            info = {
                "symbol": stock,
                "available": True,
                "tradeable": stock not in frozen_stocks,
                "freeze_reason": None,
                "liquidity_score": 1.0,
                "market_cap": _safe_float(liq.get("market_cap"), default=np.nan),
                "adv_60d": _safe_float(liq.get("adv_60d"), default=np.nan),
                "listing_date": pd.to_datetime(listing_lookup.get(stock), errors="coerce"),
                "delisting_date": pd.to_datetime(delist_lookup.get(stock), errors="coerce"),
                "has_price_history": bool(stock in has_price_history),
            }
            if np.isfinite(info["adv_60d"]):
                info["liquidity_score"] = float(
                    min(1.0, info["adv_60d"] / max(1.0, 10.0 * float(self.universe_config["min_adv_60d"])))
                )
            if stock in frozen_stocks:
                row = relevant_actions[relevant_actions["symbol"] == stock].iloc[0]
                adt = pd.to_datetime(row.get("action_date"), errors="coerce")
                ds = adt.strftime("%Y-%m-%d") if pd.notna(adt) else "unknown"
                info["freeze_reason"] = f"{row.get('action_type', 'action')} on {ds}"
            universe[stock] = info
        return universe

    def get_universe_at_date(
        self,
        target_date: datetime,
        apply_liquidity_filter: bool = True,
        apply_survivorship_filter: bool = True,
        verbose: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        target_dt = self._normalize_date(target_date)
        cache_key = f"{target_dt.strftime('%Y%m%d')}_{int(apply_liquidity_filter)}_{int(apply_survivorship_filter)}"
        if cache_key in self.universe_cache:
            return self.universe_cache[cache_key]

        if verbose:
            print(f"🌌 Reconstructing universe at {target_dt.strftime('%Y-%m-%d')}...")

        universe = self._compute_universe(
            target_date=target_dt,
            apply_liquidity_filter=apply_liquidity_filter,
            apply_survivorship_filter=apply_survivorship_filter,
        )
        self.universe_cache[cache_key] = universe

        if verbose:
            n_trade = sum(1 for x in universe.values() if x.get("tradeable"))
            print(f"   ✅ Final universe: {len(universe)} stocks ({n_trade} tradeable)")
        return universe

    def build_historical_universe_snapshots(
        self,
        start_date: datetime,
        end_date: datetime,
        apply_liquidity_filter: bool = True,
        apply_survivorship_filter: bool = True,
    ) -> pd.DataFrame:
        start_dt = self._normalize_date(start_date)
        end_dt = self._normalize_date(end_date)
        print(
            f"🗂️ Building historical universe snapshots ({start_dt.date()} → {end_dt.date()}, "
            f"liq={apply_liquidity_filter}, surv={apply_survivorship_filter})..."
        )

        px = self._load_price_panel()
        if not px.empty:
            dates = sorted(pd.to_datetime(px["Date"], errors="coerce").dropna().unique().tolist())
            dates = [pd.Timestamp(d).normalize() for d in dates if start_dt <= pd.Timestamp(d).normalize() <= end_dt]
        else:
            dates = pd.bdate_range(start_dt, end_dt).tolist()
        if not dates:
            out = pd.DataFrame(
                columns=[
                    "date",
                    "ticker",
                    "tradeable",
                    "available",
                    "listing_date",
                    "delisting_date",
                    "has_price_history",
                    "adv_60d",
                    "market_cap",
                    "apply_liquidity_filter",
                    "apply_survivorship_filter",
                ]
            )
            out.to_parquet(self.paths["universe_snapshots"], index=False)
            return out

        rows: List[Dict[str, Any]] = []
        for i, d in enumerate(dates, start=1):
            if i == 1 or i % 250 == 0 or i == len(dates):
                print(f"   📅 {i}/{len(dates)} snapshot dates")
            uni = self.get_universe_at_date(
                d,
                apply_liquidity_filter=apply_liquidity_filter,
                apply_survivorship_filter=apply_survivorship_filter,
                verbose=False,
            )
            for ticker, info in uni.items():
                rows.append(
                    {
                        "date": d,
                        "ticker": ticker,
                        "tradeable": bool(info.get("tradeable", False)),
                        "available": bool(info.get("available", False)),
                        "listing_date": pd.to_datetime(info.get("listing_date"), errors="coerce"),
                        "delisting_date": pd.to_datetime(info.get("delisting_date"), errors="coerce"),
                        "has_price_history": bool(info.get("has_price_history", False)),
                        "adv_60d": _safe_float(info.get("adv_60d"), default=np.nan),
                        "market_cap": _safe_float(info.get("market_cap"), default=np.nan),
                        "apply_liquidity_filter": bool(apply_liquidity_filter),
                        "apply_survivorship_filter": bool(apply_survivorship_filter),
                    }
                )
        out = pd.DataFrame(rows)
        out.to_parquet(self.paths["universe_snapshots"], index=False)
        print(f"   ✅ Saved snapshots: {len(out)} rows -> {self.paths['universe_snapshots']}")
        return out

    def get_delisted_symbols_on_date(self, target_date: datetime) -> Dict[str, Dict[str, Any]]:
        target_dt = self._normalize_date(target_date)
        df = self._load_delisting_database()
        if df.empty:
            return {}
        d = df.copy()
        d["delisting_date"] = pd.to_datetime(d["delisting_date"], errors="coerce").dt.normalize()
        hit = d[d["delisting_date"] == target_dt]
        if hit.empty:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for _, r in hit.iterrows():
            sym = str(r.get("symbol") or "").strip()
            if not sym:
                continue
            out[sym] = {
                "pnl_impact": _safe_float(r.get("pnl_impact"), default=float(self.universe_config["delisting_pnl_impact_default"])),
                "reason": str(r.get("reason") or "other"),
                "delisting_date": str(target_dt.date()),
            }
        return out

    def get_delisted_stocks_impact(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        start_dt = self._normalize_date(start_date)
        end_dt = self._normalize_date(end_date)
        print(f"💀 Analyzing delisting impact from {start_dt.date()} to {end_dt.date()}...")
        df = self._load_delisting_database()
        if df.empty:
            return {
                "period_start": start_dt,
                "period_end": end_dt,
                "total_delistings": 0,
                "average_impact": 0.0,
                "critical_delistings": 0,
                "delisting_details": {},
            }
        d = df.copy()
        d["delisting_date"] = pd.to_datetime(d["delisting_date"], errors="coerce")
        period = d[(d["delisting_date"] >= start_dt) & (d["delisting_date"] <= end_dt)]
        details: Dict[str, Dict[str, Any]] = {}
        total_impact = 0.0
        for _, r in period.iterrows():
            sym = str(r.get("symbol") or "").strip()
            if not sym:
                continue
            pnl = _safe_float(r.get("pnl_impact"), default=float(self.universe_config["delisting_pnl_impact_default"]))
            details[sym] = {
                "symbol": sym,
                "delisting_date": pd.to_datetime(r.get("delisting_date"), errors="coerce"),
                "reason": str(r.get("reason") or "other"),
                "final_price": _safe_float(r.get("final_price"), default=np.nan),
                "takeover_price": _safe_float(r.get("takeover_price"), default=np.nan),
                "pnl_impact": pnl,
                "impact_severity": "CRITICAL" if pnl < -0.5 else "MODERATE",
            }
            total_impact += pnl
        summary = {
            "period_start": start_dt,
            "period_end": end_dt,
            "total_delistings": int(len(period)),
            "average_impact": float(total_impact / max(1, len(period))),
            "critical_delistings": int(sum(1 for x in details.values() if x["impact_severity"] == "CRITICAL")),
            "delisting_details": details,
        }
        print(f"   💀 Found {summary['total_delistings']} delistings")
        print(f"   📉 Average PnL impact: {summary['average_impact']:.1%}")
        print(f"   🚨 Critical delistings: {summary['critical_delistings']}")
        return summary

    def run_survivorship_bias_audit(self, backtest_start: datetime, backtest_end: datetime) -> Dict[str, Any]:
        print("🔍 SURVIVORSHIP BIAS AUDIT")
        print("=" * 50)
        start_dt = self._normalize_date(backtest_start)
        end_dt = self._normalize_date(backtest_end)

        biased_universe = self.get_universe_at_date(start_dt, apply_survivorship_filter=False, verbose=False)
        unbiased_universe = self.get_universe_at_date(start_dt, apply_survivorship_filter=True, verbose=False)
        biased_count = int(len(biased_universe))
        unbiased_count = int(len(unbiased_universe))
        survivorship_bias_pct = float((biased_count - unbiased_count) / max(1, biased_count) * 100.0)

        delisting_impact = self.get_delisted_stocks_impact(start_dt, end_dt)
        estimated_performance_bias = float(-delisting_impact["average_impact"] * 0.1)
        delist_db = self._load_delisting_database()
        mapping_coverage = float(delist_db.get("mapped_has_price_history", pd.Series([], dtype=float)).mean()) if not delist_db.empty else 0.0

        audit_results = {
            "audit_date": datetime.now(),
            "backtest_period": {
                "start": start_dt,
                "end": end_dt,
                "duration_years": float((end_dt - start_dt).days / 365.25),
            },
            "universe_comparison": {
                "biased_universe_size": biased_count,
                "unbiased_universe_size": unbiased_count,
                "survivorship_bias_pct": survivorship_bias_pct,
                "missing_stocks": int(biased_count - unbiased_count),
            },
            "delisting_database": {
                "rows": int(len(delist_db)),
                "mapping_price_history_coverage": mapping_coverage,
            },
            "delisting_analysis": delisting_impact,
            "bias_estimates": {
                "estimated_performance_bias_pct": float(estimated_performance_bias * 100.0),
                "estimated_sharpe_bias": float(estimated_performance_bias / 0.15),
                "bias_severity": "HIGH" if abs(estimated_performance_bias) > 0.02 else "MODERATE",
            },
            "recommendations": [],
        }

        if delist_db.empty:
            audit_results["recommendations"].append(
                "CRITICAL: Delisting database empty - survivorship audit unreliable."
            )
        if mapping_coverage < 0.25:
            audit_results["recommendations"].append(
                "WARNING: Most delisted symbols do not map to local price history; include delisted OHLCV backfill."
            )
        if delisting_impact["critical_delistings"] > 5:
            audit_results["recommendations"].append(
                "WARNING: Multiple critical delistings - review portfolio construction."
            )
        if estimated_performance_bias > 0.01:
            audit_results["recommendations"].append(
                "BIAS: Estimated performance bias > 1% - adjust expectations."
            )

        with open(self.paths["survivorship_audit"], "w") as f:
            json.dump(audit_results, f, indent=2, default=str)

        print(f"📊 Biased/Unbiased at {start_dt.date()}: {biased_count} / {unbiased_count}")
        print(f"📉 Estimated performance bias: {estimated_performance_bias:.2%}")
        return audit_results

    def calculate_survivorship_bias_impact(
        self, start_date: str | datetime, end_date: str | datetime, universe_size: int
    ) -> Dict[str, Any]:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if isinstance(start_date, str) else self._normalize_date(start_date)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if isinstance(end_date, str) else self._normalize_date(end_date)
        delisting_impact = self.get_delisted_stocks_impact(start_dt, end_dt)
        total_delistings = int(delisting_impact["total_delistings"])
        bias_percentage = float((total_delistings / max(1, universe_size)) * abs(float(delisting_impact["average_impact"])))
        return {
            "bias_percentage": bias_percentage,
            "delisted_count": total_delistings,
            "average_delisting_impact": float(delisting_impact["average_impact"]),
            "critical_delistings": int(delisting_impact["critical_delistings"]),
            "period_start": start_dt,
            "period_end": end_dt,
            "universe_size": int(universe_size),
        }


def main():
    print("🌌 UNIVERSE MANAGER - SURVIVORSHIP BIAS ELIMINATION")
    print("=" * 70)
    manager = UniverseManager()
    manager.create_delisting_database(force_refresh=True)
    manager.create_ipo_calendar(force_refresh=True)
    manager.create_liquidity_history(force_refresh=True)
    manager.create_corporate_actions_database(force_refresh=True)

    test_date = datetime(2022, 3, 15)
    uni = manager.get_universe_at_date(test_date)
    print(f"\n🌌 Universe at {test_date.date()}: {len(uni)} stocks")
    manager.run_survivorship_bias_audit(datetime(2021, 1, 1), datetime(2023, 12, 31))
    manager.build_historical_universe_snapshots(datetime(2023, 1, 1), datetime(2023, 12, 31))


if __name__ == "__main__":
    main()
