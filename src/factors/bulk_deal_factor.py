"""Bulk-deal factor pack."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import logging
import re

import numpy as np
import pandas as pd

from src.core.panel_math import coalesce_rowwise
from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class BulkDealFactor(BaseFactor):
    """Multi-column bulk-deal signal pack with PIT-safe raw event handling."""

    FACTOR_NAME = "bulk_deal"
    FACTOR_FAMILY = "FLOW"
    FEATURE_COLUMNS = [
        'bulk_net_buy_pressure',
        'bulk_net_buy_adv',
        'bulk_deal_momentum_21d',
        'bulk_promoter_buy_flag',
        'bulk_institutional_count',
        'bulk_float_impact',
    ]
    _CATEGORY_KEYWORDS = {
        'Promoter': ['PROMOTER', 'PROMOTER GROUP'],
        'FII': ['FII', 'FPI', 'FOREIGN', 'OVERSEAS', 'OFFSHORE', 'HSBC', 'MORGAN', 'GOLDMAN', 'UBS'],
        'DII': ['MUTUAL FUND', 'MF', 'INSURANCE', 'AMC', 'ASSET MANAGEMENT', 'TRUST', 'BANK'],
        'Corporate': ['CAPITAL', 'INVEST', 'VENTURE', 'PARTNERS', 'HOLDINGS', 'PRIVATE LIMITED', 'LIMITED', 'LLP'],
    }

    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        return pd.Series(dtype=float)

    def get_output_columns(self, include_meta: bool = True) -> list[str]:
        cols: list[str] = []
        for name in self.FEATURE_COLUMNS:
            cols.extend([name, f'{name}_zscore', f'{name}_rank'])
            if include_meta:
                cols.append(f'{name}_available')
        return cols

    def get_feature_names(self, include_raw: bool = False) -> list[str]:
        names: list[str] = []
        for name in self.FEATURE_COLUMNS:
            if include_raw:
                names.append(name)
            names.extend([f'{name}_zscore', f'{name}_rank'])
        return names

    def get_primary_zscore_column(self) -> str:
        return 'bulk_net_buy_pressure_zscore'

    def compute(self, as_of_date: datetime, tickers: list, use_cache: bool = True, winsorize_std: float = 3.0) -> pd.DataFrame:
        lookback_days = int(self._factor_config.get('lookback_days', 63) or 63)
        safety_lag_days = int(self._factor_config.get('safety_lag_days', 1) or 1)
        min_accuracy = float(self._factor_config.get('min_classification_accuracy', 0.90) or 0.90)

        deals = self._registry.alternative.get_bulk_deal_history(
            as_of_date=as_of_date,
            tickers=tickers,
            lookback_days=lookback_days,
            safety_lag_days=safety_lag_days,
            apply_pit_universe_filter=True,
        )
        free_float = self._registry.fundamentals.get_free_float(as_of_date, tickers=tickers)
        market = self._registry.market.load(
            as_of_date=as_of_date,
            tickers=tickers,
            start_date=as_of_date - timedelta(days=40),
            fields=['close', 'volume'],
        )

        market_frame = market.reset_index() if not market.empty else pd.DataFrame()
        if not market_frame.empty:
            market_frame['Date'] = pd.to_datetime(market_frame['Date'], errors='coerce')
            market_frame = market_frame.sort_values(['Ticker', 'Date'], kind='mergesort')
            market_frame['close'] = pd.to_numeric(market_frame.get('close'), errors='coerce')
            market_frame['volume'] = pd.to_numeric(market_frame.get('volume'), errors='coerce')

        entity_table = self._load_entity_table()
        use_identity = float(entity_table.get('validated_accuracy', 0.0) or 0.0) >= min_accuracy

        rows = {ticker: self._compute_ticker_features(ticker, as_of_date, deals.get(ticker, pd.DataFrame()), free_float.get(ticker, {}), market_frame, entity_table, use_identity) for ticker in tickers}
        raw_df = pd.DataFrame.from_dict(rows, orient='index').reindex(tickers)

        result = pd.DataFrame(index=tickers)
        for column in self.FEATURE_COLUMNS:
            raw_series = pd.to_numeric(raw_df.get(column), errors='coerce').reindex(tickers)
            norm_series = raw_series.copy()
            non_null = norm_series.dropna()
            if len(non_null) >= 10:
                mean = float(non_null.mean())
                std = float(non_null.std())
                norm_series = norm_series.clip(lower=mean - winsorize_std * std, upper=mean + winsorize_std * std)
                norm_mean = float(norm_series.dropna().mean())
                norm_std = float(norm_series.dropna().std())
                zscore = (norm_series - norm_mean) / (norm_std + 1e-9)
            else:
                zscore = pd.Series(np.nan, index=tickers)
            result[column] = raw_series
            result[f'{column}_zscore'] = zscore
            result[f'{column}_rank'] = raw_series.rank(pct=True)
            result[f'{column}_available'] = raw_series.notna()

        return result

    def get_coverage(self, as_of_date: datetime, tickers: list) -> dict:
        result = self.compute(as_of_date, tickers, use_cache=False)
        availability_cols = [f'{column}_available' for column in self.FEATURE_COLUMNS if f'{column}_available' in result.columns]
        available = result[availability_cols].any(axis=1).sum() if availability_cols else 0
        return {
            'factor_name': self.FACTOR_NAME,
            'as_of_date': as_of_date,
            'universe_size': len(tickers),
            'tickers_with_data': int(available),
            'coverage_pct': float(available) / len(tickers) if tickers else 0.0,
            'minimum_viable_coverage': self._factor_config.get('min_coverage_pct', 0.20),
        }

    def _compute_ticker_features(
        self,
        ticker: str,
        as_of_date: datetime,
        deals: pd.DataFrame,
        free_float: dict,
        market_frame: pd.DataFrame,
        entity_table: dict,
        use_identity: bool,
    ) -> dict:
        zero = {name: 0.0 for name in self.FEATURE_COLUMNS}
        if deals is None or deals.empty:
            return zero

        work = deals.copy()
        work['date'] = pd.to_datetime(work.get('date'), errors='coerce')
        work['signed_qty'] = pd.to_numeric(work.get('signed_qty'), errors='coerce')
        work['quantity'] = pd.to_numeric(work.get('quantity'), errors='coerce')
        work['price'] = pd.to_numeric(work.get('price'), errors='coerce')
        work['notional'] = pd.to_numeric(work.get('notional'), errors='coerce')
        # N10: per-row fallback to quantity*price where notional is missing.
        work['notional'] = coalesce_rowwise(work['notional'], work['quantity'] * work['price'])
        if use_identity:
            work = self._classify(work, entity_table)

        w5 = work[work['date'] >= pd.Timestamp(as_of_date) - timedelta(days=7)].copy()
        w21 = work[work['date'] >= pd.Timestamp(as_of_date) - timedelta(days=30)].copy()

        adv_21d, latest_close = self._adv_and_close(ticker, market_frame)
        ff_shares = free_float.get('free_float_shares')
        if (ff_shares is None or pd.isna(ff_shares) or float(ff_shares) <= 0.0) and free_float.get('market_cap') and latest_close:
            ff_pct = float(free_float.get('free_float_pct') or 0.0) / 100.0
            if ff_pct > 0 and latest_close > 0:
                ff_shares = (float(free_float.get('market_cap')) / float(latest_close)) * ff_pct

        market_cap = free_float.get('market_cap')
        if (market_cap is None or pd.isna(market_cap) or float(market_cap) <= 0.0) and latest_close and ff_shares and free_float.get('free_float_pct'):
            ff_pct = float(free_float.get('free_float_pct') or 0.0) / 100.0
            if ff_pct > 0:
                market_cap = (float(ff_shares) / ff_pct) * float(latest_close)

        net5 = float(pd.to_numeric(w5.get('signed_qty'), errors='coerce').fillna(0.0).sum()) if not w5.empty else 0.0
        net21 = float(pd.to_numeric(w21.get('signed_qty'), errors='coerce').fillna(0.0).sum()) if not w21.empty else 0.0
        deal_value = float(pd.to_numeric(w5.get('notional'), errors='coerce').fillna(0.0).abs().sum()) if not w5.empty else 0.0

        result = {
            'bulk_net_buy_pressure': net5 / float(ff_shares) if ff_shares and float(ff_shares) > 0 else np.nan,
            'bulk_net_buy_adv': net5 / float(adv_21d) if adv_21d and float(adv_21d) > 0 else np.nan,
            'bulk_deal_momentum_21d': net21 / float(ff_shares) if ff_shares and float(ff_shares) > 0 else np.nan,
            'bulk_float_impact': deal_value / float(market_cap) if market_cap and float(market_cap) > 0 else np.nan,
            'bulk_promoter_buy_flag': 0.0,
            'bulk_institutional_count': 0.0,
        }

        if use_identity and not w5.empty:
            promoter_buy = w5[(w5.get('buyer_category') == 'Promoter') & (pd.to_numeric(w5.get('signed_qty'), errors='coerce') > 0)]
            institutional_buyers = w5[
                (w5.get('buyer_category').isin(['FII', 'DII', 'Corporate']))
                & (pd.to_numeric(w5.get('signed_qty'), errors='coerce') > 0)
            ]
            result['bulk_promoter_buy_flag'] = float(not promoter_buy.empty)
            canonical = institutional_buyers.get('buyer_canonical', pd.Series(dtype=object)).astype(str)
            canonical = canonical[canonical.str.len() > 0]
            result['bulk_institutional_count'] = float(canonical.nunique())

        return result

    @staticmethod
    def _normalize_name(value: object) -> str:
        s = str(value or '').strip().upper()
        s = re.sub(r'[^A-Z0-9 ]+', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    def _load_entity_table(self) -> dict:
        path = Path(self._factor_config.get('entity_table_path', 'data/reference/bulk_deal_entities.csv'))
        if not path.exists():
            return {'seed_names': [], 'seed_categories': {}, 'validated_accuracy': 0.0}
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            logger.warning("Failed reading bulk-deal entity table %s: %s", path, exc)
            return {'seed_names': [], 'seed_categories': {}, 'validated_accuracy': 0.0}
        name_col = next((c for c in ('raw_name_fragment', 'pattern') if c in df.columns), None)
        cat_col = next((c for c in ('category', 'buyer_category') if c in df.columns), None)
        if name_col is None or cat_col is None:
            return {'seed_names': [], 'seed_categories': {}, 'validated_accuracy': 0.0}
        seeds = [self._normalize_name(v) for v in df[name_col].dropna().tolist() if self._normalize_name(v)]
        categories = {self._normalize_name(k): str(v).strip() for k, v in zip(df[name_col], df[cat_col]) if self._normalize_name(k)}
        accuracy = float(pd.to_numeric(df.get('validated_accuracy'), errors='coerce').dropna().iloc[0]) if 'validated_accuracy' in df.columns and pd.to_numeric(df.get('validated_accuracy'), errors='coerce').notna().any() else 0.0
        return {'seed_names': seeds, 'seed_categories': categories, 'validated_accuracy': accuracy}

    def _classify(self, deals: pd.DataFrame, entity_table: dict) -> pd.DataFrame:
        work = deals.copy()
        seeds = entity_table.get('seed_names', [])
        categories = entity_table.get('seed_categories', {})

        def classify_name(name: object) -> tuple[str, str]:
            normalized = self._normalize_name(name)
            if not normalized:
                return 'Unknown', ''
            for seed in seeds:
                if seed and seed in normalized:
                    return categories.get(seed, 'Unknown'), seed
            best_seed = ''
            best_score = 0.0
            try:
                from rapidfuzz import fuzz, process

                if seeds:
                    match = process.extractOne(normalized, seeds, scorer=fuzz.ratio)
                    if match is not None:
                        best_seed = str(match[0])
                        best_score = float(match[1]) / 100.0
            except Exception:
                best_seed = ''
                best_score = 0.0
            if best_seed and best_score >= 0.85:
                return categories.get(best_seed, 'Unknown'), best_seed

            for category, patterns in self._CATEGORY_KEYWORDS.items():
                for pattern in patterns:
                    if pattern in normalized:
                        return category, normalized
            return 'Unknown', normalized

        classified = work.get('client_name', pd.Series('', index=work.index)).map(classify_name)
        work['buyer_category'] = classified.map(lambda x: x[0])
        work['buyer_canonical'] = classified.map(lambda x: x[1])
        return work

    @staticmethod
    def _adv_and_close(ticker: str, market_frame: pd.DataFrame) -> tuple[float | None, float | None]:
        if market_frame.empty:
            return None, None
        work = market_frame[market_frame['Ticker'] == ticker].copy()
        if work.empty:
            return None, None
        work = work.dropna(subset=['Date']).sort_values('Date', kind='mergesort')
        work['notional'] = pd.to_numeric(work.get('close'), errors='coerce') * pd.to_numeric(work.get('volume'), errors='coerce')
        adv = float(work['notional'].tail(21).mean()) if work['notional'].notna().any() else None
        latest_close = float(pd.to_numeric(work['close'], errors='coerce').dropna().iloc[-1]) if pd.to_numeric(work['close'], errors='coerce').notna().any() else None
        return adv, latest_close
