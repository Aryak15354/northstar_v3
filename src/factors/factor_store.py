"""
FactorStore — historical factor score persistence and batch computation.

Each factor is stored in a wide parquet file with one row per (date, ticker):
    date, ticker, {factor}_raw, {factor}_zscore, {factor}_rank, {factor}_available,
    universe_size, computed_at
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FactorStore:
    """Manage persistence and batch computation of canonical factor scores."""

    def __init__(self, factor_registry, config: dict):
        self._registry = factor_registry
        self._config = config
        store_cfg = (config or {}).get('factors', {}).get('store', {}) or {}
        self._base_path = Path(store_cfg.get('base_path', 'data/factors'))
        self._base_path.mkdir(parents=True, exist_ok=True)

    def compute_history(
        self,
        start_date: datetime,
        end_date: datetime,
        tickers: list,
        frequency: str = 'weekly',
        skip_existing: bool = True,
        factors: Optional[list] = None,
    ) -> dict:
        if frequency == 'daily':
            schedule = pd.date_range(start_date, end_date, freq='B')
        elif frequency == 'monthly':
            schedule = pd.date_range(start_date, end_date, freq='M')
        else:
            schedule = pd.date_range(start_date, end_date, freq='W-FRI')

        dates = [d.to_pydatetime() for d in schedule]
        if skip_existing:
            missing = set(self.get_missing_dates(start_date, end_date, frequency=frequency))
            dates = [d for d in dates if d in missing]

        selected = list(factors or self._registry.get_enabled_factors())
        summary = {
            'dates_to_compute': len(dates),
            'factors_to_compute': len(selected),
            'dates_computed': 0,
            'errors': [],
        }

        for idx, as_of_date in enumerate(dates, start=1):
            try:
                logger.info("Computing factor history for %s (%d/%d)", as_of_date.date(), idx, len(dates))
                result = self._registry.compute_all(as_of_date, tickers, use_cache=True)
                self._save_factor_data(as_of_date, result, selected)
                summary['dates_computed'] += 1
            except Exception as exc:
                msg = f"{as_of_date.date()}: {exc}"
                logger.error("Factor history compute failed: %s", msg)
                summary['errors'].append(msg)

        return summary

    def _save_factor_data(self, as_of_date: datetime, result: pd.DataFrame, factors: list) -> None:
        computed_at = pd.Timestamp.utcnow()
        for factor in list(factors or []):
            factor_obj = self._registry._factors.get(factor)
            if factor_obj is not None and hasattr(factor_obj, 'get_output_columns'):
                cols = [c for c in factor_obj.get_output_columns(include_meta=True) if c in result.columns]
            else:
                cols = [c for c in result.columns if c.startswith(f"{factor}_")]
            if not cols:
                continue

            frame = result[cols].copy()
            for col in cols:
                if str(col).endswith('_available') and col in frame.columns:
                    frame[col] = frame[col].fillna(False).astype(bool)
            frame['date'] = pd.Timestamp(as_of_date)
            frame['ticker'] = frame.index.astype(str)
            frame['universe_size'] = int(len(result))
            frame['computed_at'] = computed_at
            frame = frame.reset_index(drop=True)

            file_path = self._base_path / f"{factor}_scores.parquet"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if file_path.exists():
                existing = pd.read_parquet(file_path)
                existing = self._normalize_factor_frame(existing, factor, factor_obj, cols)
                mask = pd.to_datetime(existing['date'], errors='coerce') != pd.Timestamp(as_of_date)
                combined = pd.concat([existing[mask], frame], ignore_index=True)
            else:
                combined = frame

            temp_path = file_path.with_name(f"{file_path.stem}.tmp.parquet")
            combined.to_parquet(temp_path, index=False)
            temp_path.rename(file_path)

    def load_factor_features(
        self,
        start_date: datetime,
        end_date: datetime,
        tickers: list,
        factor_names: Optional[list] = None,
    ) -> pd.DataFrame:
        selected = list(factor_names or self._registry.get_enabled_factors())
        frames = []

        for factor in selected:
            file_path = self._base_path / f"{factor}_scores.parquet"
            if not file_path.exists():
                logger.warning("Factor file missing: %s", file_path)
                continue
            try:
                df = pd.read_parquet(file_path)
            except Exception as exc:
                logger.warning("Failed loading factor file %s: %s", file_path, exc)
                continue
            factor_obj = self._registry._factors.get(factor)
            df = self._normalize_factor_frame(df, factor, factor_obj)

            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df[
                (df['date'] >= pd.Timestamp(start_date))
                & (df['date'] <= pd.Timestamp(end_date))
                & (df['ticker'].astype(str).isin([str(t) for t in tickers]))
            ].copy()
            if df.empty:
                continue
            if factor_obj is not None and hasattr(factor_obj, 'get_output_columns'):
                prefixed = [c for c in factor_obj.get_output_columns(include_meta=True) if c in df.columns]
            else:
                prefixed = [c for c in df.columns if c.startswith(f"{factor}_")]
            keep = ['date', 'ticker'] + prefixed
            frames.append(df[keep].set_index(['date', 'ticker']).sort_index())

        if not frames:
            return pd.DataFrame(index=pd.MultiIndex.from_arrays([[], []], names=['date', 'ticker']))

        merged = pd.concat(frames, axis=1)
        merged = merged.loc[:, ~merged.columns.duplicated()]
        return merged.sort_index()

    def get_missing_dates(
        self,
        start_date: datetime,
        end_date: datetime,
        frequency: str = 'weekly',
    ) -> list[datetime]:
        if frequency == 'daily':
            full = pd.date_range(start_date, end_date, freq='B')
        elif frequency == 'monthly':
            full = pd.date_range(start_date, end_date, freq='M')
        else:
            full = pd.date_range(start_date, end_date, freq='W-FRI')

        expected = {d.to_pydatetime() for d in full}
        seen = set()
        for factor in self._registry.get_enabled_factors():
            file_path = self._base_path / f"{factor}_scores.parquet"
            if not file_path.exists():
                continue
            try:
                df = pd.read_parquet(file_path, columns=['date'])
                dates = pd.to_datetime(df['date'], errors='coerce').dropna().dt.normalize()
                seen.update(d.to_pydatetime() for d in dates.unique())
            except Exception:
                continue
        return sorted(expected - seen)

    def get_store_status(self) -> dict:
        status = {
            'factors': {},
            'total_dates': 0,
            'total_tickers': 0,
            'date_range': None,
        }
        all_dates = set()
        all_tickers = set()

        for factor in self._registry.get_enabled_factors():
            file_path = self._base_path / f"{factor}_scores.parquet"
            if not file_path.exists():
                status['factors'][factor] = {'exists': False}
                continue
            try:
                df = pd.read_parquet(file_path)
            except Exception as exc:
                status['factors'][factor] = {'exists': False, 'error': str(exc)}
                continue
            factor_obj = self._registry._factors.get(factor)
            df = self._normalize_factor_frame(df, factor, factor_obj)

            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            dates = df['date'].dropna()
            tickers = df['ticker'].astype(str).dropna()
            all_dates.update(dates.dt.normalize().unique())
            all_tickers.update(tickers.unique())
            availability_cols = [col for col in df.columns if str(col).endswith('_available')]
            coverage_pct = float(df[availability_cols].any(axis=1).mean()) if availability_cols and len(df) > 0 else None
            status['factors'][factor] = {
                'exists': True,
                'num_dates': int(dates.dt.normalize().nunique()),
                'num_tickers': int(tickers.nunique()),
                'date_range': (
                    str(dates.min().date()) if not dates.empty else None,
                    str(dates.max().date()) if not dates.empty else None,
                ),
                'coverage_pct': coverage_pct,
            }

        if all_dates:
            normalized_dates = pd.to_datetime(sorted(all_dates))
            status['total_dates'] = int(len(normalized_dates))
            status['date_range'] = (
                str(normalized_dates.min().date()),
                str(normalized_dates.max().date()),
            )
        if all_tickers:
            status['total_tickers'] = int(len(all_tickers))
        return status

    def _normalize_factor_frame(
        self,
        df: pd.DataFrame,
        factor: str,
        factor_obj=None,
        explicit_cols: Optional[list] = None,
    ) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        if explicit_cols is not None:
            expected_cols = list(explicit_cols)
        elif factor_obj is not None and hasattr(factor_obj, 'get_output_columns'):
            expected_cols = [c for c in factor_obj.get_output_columns(include_meta=True)]
        else:
            expected_cols = [c for c in df.columns if c.startswith(f"{factor}_")]

        work = df.copy()
        if {'metric', 'value'}.issubset(set(work.columns)):
            work['date'] = pd.to_datetime(work['date'], errors='coerce')
            pivot = (
                work[['date', 'ticker', 'metric', 'value']]
                .dropna(subset=['date', 'ticker', 'metric'])
                .pivot_table(index=['date', 'ticker'], columns='metric', values='value', aggfunc='last')
                .reset_index()
            )
            work = pivot

        if 'date' in work.columns:
            work['date'] = pd.to_datetime(work['date'], errors='coerce')
        if 'ticker' in work.columns:
            work['ticker'] = work['ticker'].astype(str)

        for col in expected_cols:
            if col not in work.columns:
                work[col] = False if str(col).endswith('_available') else np.nan
            elif str(col).endswith('_available'):
                work[col] = work[col].fillna(False).astype(bool)

        if 'universe_size' not in work.columns:
            work['universe_size'] = np.nan
        if 'computed_at' not in work.columns:
            work['computed_at'] = pd.NaT

        keep = ['date', 'ticker'] + expected_cols + ['universe_size', 'computed_at']
        keep = [col for col in keep if col in work.columns]
        return work[keep].copy()
