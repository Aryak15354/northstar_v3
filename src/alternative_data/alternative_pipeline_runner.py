"""
AlternativePipelineRunner — Orchestrates the daily alternative data pipeline.

The runner is responsible for:
1. Checking if alternative data sources are fresh (idempotent)
2. Computing alternative data state from all 5 sources
3. Updating AlternativeDataState in UnifiedState
4. Emitting pipeline completion events
5. Logging structured completion records

This runner is designed to be called from the pre-market sequence at 06:00 IST,
AFTER sentiment pipeline and BEFORE market data update, so alternative data is
ready when the intelligence stack activates at 09:00.

It is safe to call multiple times — if data is already fresh, it logs
"already fresh" and exits without reprocessing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd

from src.alternative_data.alt_data_keys import (
    BULK_ACCUMULATION_BREADTH,
    BULK_DISTRIBUTION_BREADTH,
    BULK_NET_FLOW,
    BULK_SIGNAL_NUMERIC,
    CREDIT_NET_MOMENTUM,
    CREDIT_STRESS_FLAG,
    CREDIT_UPGRADE_RATIO,
    POWER_DEVIATION_SEASONAL,
    POWER_INDUSTRIAL_PROXY,
    POWER_YOY_GROWTH,
)
from src.ingestion.ingestion_registry import IngestionRegistry
from src.alternative_data.alternative_state import (
    AlternativeDataState,
    GSTSignalState,
    PowerSignalState,
    CreditSignalState,
    SmartMoneyState,
    PromoterRiskState,
    EconomicActivityRegime,
    SmartMoneySignal
)
from src.alternative_data.alternative_feature_block import AlternativeFeatureBlock

logger = logging.getLogger(__name__)


def _numeric_to_smart_money_signal(signal_numeric: int | float) -> SmartMoneySignal:
    """Map feature block smart-money numeric output (-2..2) to enum."""
    numeric = int(pd.to_numeric(signal_numeric, errors="coerce") or 0)
    if numeric >= 2:
        return SmartMoneySignal.STRONG_ACCUMULATION
    if numeric >= 1:
        return SmartMoneySignal.MILD_ACCUMULATION
    if numeric == 0:
        return SmartMoneySignal.NEUTRAL
    if numeric >= -1:
        return SmartMoneySignal.MILD_DISTRIBUTION
    return SmartMoneySignal.STRONG_DISTRIBUTION


@dataclass
class AlternativePipelineResult:
    """Result of alternative data pipeline execution"""
    status: str  # 'SUCCESS', 'ALREADY_FRESH', 'PARTIAL', 'FAILED'
    sources_processed: Dict[str, bool]  # source_name -> success
    run_duration_seconds: float
    errors: List[str]
    as_of_date: datetime


class AlternativePipelineRunner:
    """Orchestrates the daily alternative data pipeline"""
    
    def __init__(self, config: dict, event_bus=None):
        """
        Initialize the pipeline runner.
        
        Args:
            config: System configuration dict
            event_bus: Optional event bus for emitting events
        """
        self.config = config
        self.event_bus = event_bus
        
        # Initialize registry
        self.registry = IngestionRegistry(config)
        
        # Initialize feature block
        self.feature_block = AlternativeFeatureBlock(self.registry, config)
        
        # Get freshness thresholds from config
        alt_config = config.get('alternative_data', {})
        self.freshness_thresholds = alt_config.get('freshness_thresholds', {
            'bulk_deals_max_age_days': 2,
            'power_data_max_age_days': 5,
            'power_data_max_age_business_days': 5,
            'credit_ratings_max_age_days': 7,
            'gst_data_max_age_months': 1.5,
            'gst_data_max_age_days': 45,
            'gst_release_grace_days': 10,
            'promoter_pledges_max_age_days': 100
        })
        
        # Track last processed state for idempotency
        self._last_processed_state = None
        self._last_processed_date = None

    @staticmethod
    def _latest_valid_timestamp(df: pd.DataFrame, candidates: list[str]) -> Optional[pd.Timestamp]:
        for column in candidates:
            if column not in df.columns:
                continue
            values = pd.to_datetime(df[column], errors='coerce')
            if values.notna().any():
                return pd.Timestamp(values.max())
        return None

    def _collect_source_details(self, as_of_date: datetime) -> Dict[str, Dict[str, Any]]:
        """Load per-source health once so state freshness matches loader freshness."""
        details: Dict[str, Dict[str, Any]] = {}

        loader_map = {
            'gst': lambda: self.registry.alternative.load_gst(as_of_date),
            'power': lambda: self.registry.alternative.load_power_consumption(as_of_date),
            'credit': lambda: self.registry.alternative.load_credit_ratings(as_of_date),
            'bulk': lambda: self.registry.alternative.load_bulk_deals(as_of_date),
            'pledge': lambda: self.registry.alternative.load_promoter_pledges(as_of_date),
        }

        for source, loader in loader_map.items():
            try:
                df = loader()
                latest_date: Optional[pd.Timestamp] = None
                if source == 'gst' and not df.empty:
                    latest_date = pd.Timestamp(df.index.max())
                elif source == 'power':
                    latest_date = self._latest_valid_timestamp(df, ['availability_date', 'AvailabilityDate', 'date', 'Date'])
                elif source == 'credit':
                    latest_date = self._latest_valid_timestamp(
                        df.reset_index() if isinstance(df.index, pd.MultiIndex) else df,
                        ['ActionDate', 'DATE OF CREDIT RATING', 'DATE', 'Date', 'date', 'processed_date'],
                    )
                elif source == 'bulk':
                    latest_date = self._latest_valid_timestamp(
                        df.reset_index() if isinstance(df.index, pd.MultiIndex) else df,
                        ['latest_trade_date', 'TradeDate', 'Date', 'date'],
                    )
                elif source == 'pledge':
                    latest_date = self._latest_valid_timestamp(
                        df.reset_index() if isinstance(df.index, pd.MultiIndex) else df,
                        ['AvailabilityDate', 'QuarterEnd', 'Date', 'date'],
                    )

                details[source] = {
                    'df': df,
                    'latest_date': latest_date.to_pydatetime() if latest_date is not None else None,
                    'is_fresh': self.is_source_fresh(source, as_of_date),
                }
            except Exception as exc:
                logger.warning("Could not load source detail for %s: %s", source, exc)
                details[source] = {'df': pd.DataFrame(), 'latest_date': None, 'is_fresh': False}

        return details

    @staticmethod
    def _entity_count(df: pd.DataFrame, candidates: List[str]) -> int:
        if df.empty:
            return 0
        work = df.reset_index() if isinstance(df.index, pd.MultiIndex) else df
        for column in candidates:
            if column in work.columns:
                return int(work[column].dropna().astype(str).nunique())
        return 0

    @staticmethod
    def _business_days_old(as_of_date: datetime, latest_date: pd.Timestamp) -> int:
        as_of_day = pd.Timestamp(as_of_date).normalize()
        latest_day = pd.Timestamp(latest_date).normalize()
        if as_of_day <= latest_day:
            return 0
        return int(len(pd.bdate_range(latest_day + pd.Timedelta(days=1), as_of_day)))

    def _latest_gst_observation(self, df: pd.DataFrame) -> Optional[pd.Timestamp]:
        if df.empty:
            return None
        if df.index.name == 'MonthEnd' or isinstance(df.index, pd.DatetimeIndex):
            return pd.Timestamp(df.index.max())
        date_col = next((c for c in ['MonthEnd', 'date', 'Date'] if c in df.columns), None)
        if not date_col:
            return None
        values = pd.to_datetime(df[date_col], errors='coerce')
        return pd.Timestamp(values.max()) if values.notna().any() else None

    @staticmethod
    def _contains_distress_rating(value: Any) -> bool:
        text = str(value or "").upper()
        distress_tokens = [' BB', 'BB+', 'BB-', ' B', 'B+', 'B-', 'CCC', 'CC', 'C', 'D', 'SUB-INVESTMENT']
        return any(token in f" {text}" for token in distress_tokens)
    
    def is_source_fresh(self, source: str, as_of_date: datetime) -> bool:
        """
        Check whether a specific alternative data source is fresh.
        
        Args:
            source: Source name ('gst', 'power', 'credit', 'bulk', 'pledge')
            as_of_date: Date to check against
            
        Returns:
            True if fresh, False if stale or missing
        """
        try:
            if source == 'gst':
                df = self.registry.alternative.load_gst(as_of_date)
                if df.empty:
                    return False
                latest_date = self._latest_gst_observation(df)
                if latest_date is None:
                    return False
                latest_availability = self._latest_valid_timestamp(
                    df.reset_index() if isinstance(df.index, pd.MultiIndex) else df,
                    ['availability_date', 'AvailabilityDate', 'available_at'],
                )
                if latest_availability is not None:
                    age_days = (pd.Timestamp(as_of_date).normalize() - latest_availability.normalize()).days
                    if age_days <= int(self.freshness_thresholds.get('gst_data_max_age_days', 45)):
                        return True
                    publication_lag_days = max((latest_availability.normalize() - latest_date.normalize()).days, 0)
                    next_period_end = (latest_date.normalize() + pd.offsets.MonthEnd(1)).normalize()
                    next_expected_release = next_period_end + pd.Timedelta(days=publication_lag_days)
                    grace_days = int(self.freshness_thresholds.get('gst_release_grace_days', 10))
                    return pd.Timestamp(as_of_date).normalize() <= next_expected_release + pd.Timedelta(days=grace_days)
                months_old = (as_of_date.year - latest_date.year) * 12 + (as_of_date.month - latest_date.month)
                return months_old <= self.freshness_thresholds['gst_data_max_age_months']
            
            elif source == 'power':
                df = self.registry.alternative.load_power_consumption(as_of_date)
                if df.empty:
                    return False
                latest_date = self._latest_valid_timestamp(df, ['availability_date', 'AvailabilityDate', 'date', 'Date'])
                if latest_date is None:
                    return False
                business_days_old = self._business_days_old(as_of_date, latest_date)
                threshold = int(
                    self.freshness_thresholds.get(
                        'power_data_max_age_business_days',
                        self.freshness_thresholds.get('power_data_max_age_days', 5),
                    )
                )
                return business_days_old <= threshold
            
            elif source == 'credit':
                df = self.registry.alternative.load_credit_ratings(as_of_date)
                if df.empty:
                    return False
                latest_date = self._latest_valid_timestamp(
                    df,
                    ['ActionDate', 'DATE OF CREDIT RATING', 'DATE', 'Date', 'date', 'processed_date'],
                )
                if latest_date is None:
                    return False
                days_old = (as_of_date.date() - latest_date.date()).days
                return days_old <= self.freshness_thresholds['credit_ratings_max_age_days']
            
            elif source == 'bulk':
                df = self.registry.alternative.load_bulk_deals(as_of_date)
                if df.empty:
                    return False
                latest_date = self._latest_valid_timestamp(df, ['latest_trade_date', 'TradeDate', 'Date', 'date'])
                if latest_date is None:
                    return False
                days_old = (as_of_date.date() - latest_date.date()).days
                return days_old <= self.freshness_thresholds['bulk_deals_max_age_days']
            
            elif source == 'pledge':
                df = self.registry.alternative.load_promoter_pledges(as_of_date)
                if df.empty:
                    return False
                latest_date = self._latest_valid_timestamp(df, ['AvailabilityDate', 'QuarterEnd', 'Date', 'date'])
                if latest_date is None:
                    return False
                days_old = (as_of_date.date() - latest_date.date()).days
                return days_old <= self.freshness_thresholds['promoter_pledges_max_age_days']
            
            else:
                logger.warning(f"Unknown source: {source}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking freshness for {source}: {e}")
            return False
    
    def run(self, as_of_date: datetime, force: bool = False) -> AlternativePipelineResult:
        """
        Run the alternative data pipeline.
        
        Args:
            as_of_date: Date to process alternative data for
            force: If True, run even if data is fresh
            
        Returns:
            AlternativePipelineResult with status and metrics
        """
        start_time = pd.Timestamp.now()
        errors = []
        sources_processed = {}
        
        try:
            # Check if we've already processed this exact date (idempotency)
            if not force and self._last_processed_date == as_of_date:
                logger.info(f"Alternative data already processed for {as_of_date.date()}")
                return AlternativePipelineResult(
                    status='ALREADY_FRESH',
                    sources_processed=sources_processed,
                    run_duration_seconds=0.0,
                    errors=[],
                    as_of_date=as_of_date
                )
            
            # Check freshness of all sources
            sources = ['gst', 'power', 'credit', 'bulk', 'pledge']
            all_fresh = True
            
            for source in sources:
                is_fresh = self.is_source_fresh(source, as_of_date)
                sources_processed[source] = is_fresh
                if not is_fresh:
                    all_fresh = False
                    logger.warning(f"Source {source} is stale for {as_of_date.date()}")
            
            logger.info(f"Running alternative data pipeline for {as_of_date.date()}")
            
            # Compute alternative state
            alternative_state = self.compute_alternative_state(as_of_date)
            
            # Cache the processed state for idempotency
            self._last_processed_state = alternative_state
            self._last_processed_date = as_of_date
            
            # Log state summary
            logger.info(f"Alternative state computed: "
                       f"GST regime={alternative_state.gst.regime.name}, "
                       f"Smart money={alternative_state.smart_money.market_signal.name}, "
                       f"Systemic risk={alternative_state.promoter_risk.systemic_pledge_risk}")
            
            duration = (pd.Timestamp.now() - start_time).total_seconds()
            
            # Emit event if event bus available
            if self.event_bus:
                try:
                    self.event_bus.emit('ALTERNATIVE_DATA_PIPELINE_COMPLETE', {
                        'sources_processed': sources_processed,
                        'gst_regime': alternative_state.gst.regime.name,
                        'smart_money_signal': alternative_state.smart_money.market_signal.name,
                        'systemic_risk': alternative_state.promoter_risk.systemic_pledge_risk,
                        'pipeline_duration_seconds': duration,
                        'as_of_date': as_of_date.isoformat()
                    })
                except Exception as e:
                    logger.warning(f"Could not emit event: {e}")
            
            logger.info(f"Alternative data pipeline completed in {duration:.2f}s")
            
            return AlternativePipelineResult(
                status='SUCCESS',
                sources_processed=sources_processed,
                run_duration_seconds=duration,
                errors=errors,
                as_of_date=as_of_date
            )
            
        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            
            return AlternativePipelineResult(
                status='FAILED',
                sources_processed=sources_processed,
                run_duration_seconds=(pd.Timestamp.now() - start_time).total_seconds(),
                errors=errors,
                as_of_date=as_of_date
            )
    
    def compute_alternative_state(self, as_of_date: datetime) -> AlternativeDataState:
        """
        Compute the complete alternative data state for a given date.
        
        Args:
            as_of_date: Date to compute state for
            
        Returns:
            AlternativeDataState with all signal states populated
        """
        try:
            source_details = self._collect_source_details(as_of_date)

            # Compute market-level features
            market_features = self.feature_block.compute_market_level_features(as_of_date)
            
            if market_features.empty:
                logger.warning("No market features computed, returning empty state")
                return self._empty_alternative_state(as_of_date)
            
            # Extract features from DataFrame (single row)
            features = market_features.iloc[0].to_dict()
            
            # Build GST signal state
            gst_signal = self._build_gst_signal(features, as_of_date, source_details.get('gst', {}))
            
            # Build power signal state
            power_signal = self._build_power_signal(features, as_of_date, source_details.get('power', {}))
            
            # Build credit signal state
            credit_signal = self._build_credit_signal(features, as_of_date, source_details.get('credit', {}))
            
            # Build smart money state
            smart_money = self._build_smart_money_state(features, as_of_date, source_details.get('bulk', {}))
            
            # Build promoter risk state
            promoter_risk = self._build_promoter_risk_state(features, as_of_date, source_details.get('pledge', {}))
            
            # Combine into alternative data state
            # Determine composite economic activity regime
            gst_regime_score = self._regime_to_score(gst_signal.regime)
            power_regime_score = self._regime_to_score(power_signal.regime)
            composite_score = (gst_regime_score + power_regime_score) / 2.0
            
            if not (gst_signal.is_fresh or power_signal.is_fresh):
                economic_regime = EconomicActivityRegime.UNAVAILABLE
            elif composite_score <= 0.5:
                economic_regime = EconomicActivityRegime.CONTRACTION
            elif composite_score <= 1.5:
                economic_regime = EconomicActivityRegime.SLOWING
            elif composite_score <= 2.5:
                economic_regime = EconomicActivityRegime.NEUTRAL
            elif composite_score <= 3.5:
                economic_regime = EconomicActivityRegime.RECOVERING
            else:
                economic_regime = EconomicActivityRegime.EXPANSION
            
            return AlternativeDataState(
                gst=gst_signal,
                power=power_signal,
                credit=credit_signal,
                smart_money=smart_money,
                promoter_risk=promoter_risk,
                economic_activity_regime=economic_regime,
                any_source_fresh=any(bool(detail.get('is_fresh')) for detail in source_details.values()),
                all_sources_fresh=bool(source_details) and all(bool(detail.get('is_fresh')) for detail in source_details.values()),
                last_updated=as_of_date
            )
            
        except Exception as e:
            logger.error(f"Error computing alternative state: {e}", exc_info=True)
            return self._empty_alternative_state(as_of_date)
    
    def _build_gst_signal(self, features: Dict[str, float], as_of_date: datetime, detail: Dict[str, Any]) -> GSTSignalState:
        """Build GST signal state from features"""
        if not bool(detail.get('is_fresh')):
            return GSTSignalState(last_data_month=detail.get('latest_date'), is_fresh=False)

        regime_numeric = features.get('gst_regime_numeric', 2.0)
        
        # Map numeric regime to enum
        if regime_numeric <= 0:
            regime = EconomicActivityRegime.CONTRACTION
        elif regime_numeric <= 1:
            regime = EconomicActivityRegime.SLOWING
        elif regime_numeric <= 2:
            regime = EconomicActivityRegime.NEUTRAL
        elif regime_numeric <= 3:
            regime = EconomicActivityRegime.RECOVERING
        else:
            regime = EconomicActivityRegime.EXPANSION
        
        # Determine trend direction
        trend_accel = features.get('gst_trend_accel', 0.0)
        if trend_accel > 0.5:
            trend_direction = "ACCELERATING"
        elif trend_accel < -0.5:
            trend_direction = "DECELERATING"
        else:
            trend_direction = "STABLE"
        
        return GSTSignalState(
            regime=regime,
            mom_growth_pct=features.get('gst_mom_growth', 0.0),
            yoy_growth_pct=features.get('gst_yoy_growth', 0.0),
            deviation_from_trend=features.get('gst_deviation_from_trend', 0.0),
            trend_direction=trend_direction,
            last_data_month=detail.get('latest_date'),
            is_fresh=True
        )
    
    def _build_power_signal(self, features: Dict[str, float], as_of_date: datetime, detail: Dict[str, Any]) -> PowerSignalState:
        """Build power signal state from features"""
        if not bool(detail.get('is_fresh')):
            return PowerSignalState(last_data_date=detail.get('latest_date'), is_fresh=False)

        # Determine regime from industrial proxy
        industrial_proxy = features.get(POWER_INDUSTRIAL_PROXY, 0.0)
        if industrial_proxy < -1.0:
            regime = EconomicActivityRegime.CONTRACTION
        elif industrial_proxy < -0.5:
            regime = EconomicActivityRegime.SLOWING
        elif industrial_proxy < 0.5:
            regime = EconomicActivityRegime.NEUTRAL
        elif industrial_proxy < 1.0:
            regime = EconomicActivityRegime.RECOVERING
        else:
            regime = EconomicActivityRegime.EXPANSION
        
        return PowerSignalState(
            regime=regime,
            yoy_growth_pct=features.get(POWER_YOY_GROWTH, 0.0),
            deviation_from_seasonal=features.get(POWER_DEVIATION_SEASONAL, 0.0),
            industrial_proxy_score=industrial_proxy * 50 + 50,  # Convert to 0-100 scale
            last_data_date=detail.get('latest_date'),
            is_fresh=True
        )
    
    def _build_credit_signal(self, features: Dict[str, float], as_of_date: datetime, detail: Dict[str, Any]) -> CreditSignalState:
        """Build credit signal state from features"""
        credit_df = detail.get('df', pd.DataFrame())
        credit_work = credit_df.reset_index() if isinstance(getattr(credit_df, 'index', None), pd.MultiIndex) else credit_df

        distressed_count = 0
        recent_downgrades = 0
        if not credit_work.empty:
            rating_col = next((c for c in ['CurrentRating', 'rating', 'CREDIT RATING'] if c in credit_work.columns), None)
            action_col = next((c for c in ['ActionType', 'rating_action', 'RATING ACTION'] if c in credit_work.columns), None)
            date_col = next((c for c in ['ActionDate', 'DATE OF CREDIT RATING', 'date'] if c in credit_work.columns), None)
            entity_col = next((c for c in ['Ticker', 'CompanyName', 'company_name'] if c in credit_work.columns), None)

            if rating_col and entity_col:
                distress_mask = credit_work[rating_col].apply(self._contains_distress_rating)
                distressed_count = int(credit_work.loc[distress_mask, entity_col].dropna().astype(str).nunique())

            if action_col and date_col:
                action_dates = pd.to_datetime(credit_work[date_col], errors='coerce')
                recent_window = action_dates >= (pd.Timestamp(as_of_date) - pd.Timedelta(days=30))
                downgrade_mask = credit_work[action_col].astype(str).str.upper().str.contains('DOWNGRADE', na=False)
                recent_downgrades = int((recent_window & downgrade_mask).sum())

        return CreditSignalState(
            market_upgrade_ratio=features.get(CREDIT_UPGRADE_RATIO, 0.0),
            net_credit_momentum=features.get(CREDIT_NET_MOMENTUM, 0.0),
            distressed_company_count=distressed_count,
            recent_downgrade_count=recent_downgrades,
            high_yield_stress_flag=features.get(CREDIT_STRESS_FLAG, 0.0) > 0.5,
            last_data_date=detail.get('latest_date'),
            is_fresh=bool(detail.get('is_fresh'))
        )
    
    def _build_smart_money_state(self, features: Dict[str, float], as_of_date: datetime, detail: Dict[str, Any]) -> SmartMoneyState:
        """Build smart money state from features"""
        bulk_df = detail.get('df', pd.DataFrame())
        if not bool(detail.get('is_fresh')):
            return SmartMoneyState(
                market_signal=SmartMoneySignal.UNAVAILABLE,
                last_data_date=detail.get('latest_date'),
                is_fresh=False,
            )

        signal_numeric = features.get(BULK_SIGNAL_NUMERIC, 0.0)
        signal = _numeric_to_smart_money_signal(signal_numeric)
        
        high_buys = 0
        high_sells = 0
        if not bulk_df.empty:
            bulk_work = bulk_df.reset_index() if isinstance(getattr(bulk_df, 'index', None), pd.MultiIndex) else bulk_df
            if 'institutional_accumulation' in bulk_work.columns:
                high_buys = int(bulk_work['institutional_accumulation'].fillna(False).sum())
            if 'net_buy_pressure' in bulk_work.columns:
                high_sells = int((pd.to_numeric(bulk_work['net_buy_pressure'], errors='coerce') < 0).sum())

        return SmartMoneyState(
            market_signal=signal,
            net_institutional_flow_score=features.get(BULK_NET_FLOW, 0.0),
            accumulation_breadth=features.get(BULK_ACCUMULATION_BREADTH, 0.0),
            distribution_breadth=features.get(BULK_DISTRIBUTION_BREADTH, 0.0),
            high_conviction_buys=high_buys,
            high_conviction_sells=high_sells,
            last_data_date=detail.get('latest_date'),
            is_fresh=True
        )
    
    def _build_promoter_risk_state(self, features: Dict[str, float], as_of_date: datetime, detail: Dict[str, Any]) -> PromoterRiskState:
        """Build promoter risk state from features"""
        pledge_df = detail.get('df', pd.DataFrame())
        pledge_work = pledge_df.reset_index() if isinstance(getattr(pledge_df, 'index', None), pd.MultiIndex) else pledge_df
        high_pledge_count = int(pledge_work.get('high_pledge_flag', pd.Series(dtype=bool)).fillna(False).sum()) if not pledge_work.empty else 0
        increasing_count = int(pledge_work.get('pledge_increasing', pd.Series(dtype=bool)).fillna(False).sum()) if not pledge_work.empty else 0

        return PromoterRiskState(
            market_avg_pledge_pct=features.get('pledge_market_avg', 0.0),
            high_pledge_company_count=high_pledge_count,
            pledge_increasing_count=increasing_count,
            systemic_pledge_risk=features.get('pledge_systemic_risk', 0.0) > 0.5,
            last_data_quarter=detail.get('latest_date'),
            is_fresh=bool(detail.get('is_fresh'))
        )
    
    
    def _regime_to_score(self, regime: EconomicActivityRegime) -> float:
        """Convert regime enum to numeric score for averaging"""
        mapping = {
            EconomicActivityRegime.CONTRACTION: 0.0,
            EconomicActivityRegime.SLOWING: 1.0,
            EconomicActivityRegime.NEUTRAL: 2.0,
            EconomicActivityRegime.RECOVERING: 3.0,
            EconomicActivityRegime.EXPANSION: 4.0,
            EconomicActivityRegime.UNAVAILABLE: 2.0  # Neutral default
        }
        return mapping.get(regime, 2.0)
    
    def _empty_alternative_state(self, as_of_date: datetime) -> AlternativeDataState:
        """Return empty alternative state when data unavailable"""
        return AlternativeDataState(
            gst=GSTSignalState(
                regime=EconomicActivityRegime.UNAVAILABLE,
                mom_growth_pct=0.0,
                yoy_growth_pct=0.0,
                deviation_from_trend=0.0,
                trend_direction="UNKNOWN",
                last_data_month=None,
                is_fresh=False
            ),
            power=PowerSignalState(
                regime=EconomicActivityRegime.UNAVAILABLE,
                yoy_growth_pct=0.0,
                deviation_from_seasonal=0.0,
                industrial_proxy_score=0.0,
                last_data_date=None,
                is_fresh=False
            ),
            credit=CreditSignalState(
                market_upgrade_ratio=0.0,
                net_credit_momentum=0.0,
                distressed_company_count=0,
                recent_downgrade_count=0,
                high_yield_stress_flag=False,
                last_data_date=None,
                is_fresh=False
            ),
            smart_money=SmartMoneyState(
                market_signal=SmartMoneySignal.UNAVAILABLE,
                net_institutional_flow_score=0.0,
                accumulation_breadth=0.0,
                distribution_breadth=0.0,
                high_conviction_buys=0,
                high_conviction_sells=0,
                last_data_date=None,
                is_fresh=False
            ),
            promoter_risk=PromoterRiskState(
                market_avg_pledge_pct=0.0,
                high_pledge_company_count=0,
                pledge_increasing_count=0,
                systemic_pledge_risk=False,
                last_data_quarter=None,
                is_fresh=False
            ),
            economic_activity_regime=EconomicActivityRegime.UNAVAILABLE,
            any_source_fresh=False,
            all_sources_fresh=False,
            last_updated=as_of_date
        )
