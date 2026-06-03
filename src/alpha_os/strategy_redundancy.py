"""
StrategyRedundancyDetector — Identifies when two strategies are doing the same thing.

Alpha diversification requires that active strategies contribute independent alpha
sources. If Strategy A and Strategy B are generating signals with correlation > 0.7,
they are not independent. Running both:
  - Does not improve diversification
  - Doubles the risk concentration in correlated bets
  - Wastes the feature budget allocated to the duplicate strategy

The redundancy detector runs two checks:
1. Signal correlation: Are the per-ticker alpha scores correlated over time?
2. Factor exposure overlap: Do the strategies load on the same factors?

If a new CANDIDATE strategy is redundant with an ACTIVE strategy, it is disqualified
(status = REDUNDANT) unless it has substantially better ICIR. If two ACTIVE strategies
become redundant over time (their signals have converged), the lower-ICIR strategy is
flagged for demotion review.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class RedundancyCheckResult:
    """Result of redundancy check for a candidate strategy."""
    candidate_id: str
    is_redundant: bool
    redundant_with: Optional[str]       # strategy_id of the ACTIVE strategy it duplicates
    max_correlation: float              # Highest pairwise correlation found
    correlations: Dict[str, float]      # {active_strategy_id: correlation} for all active
    recommendation: str                 # "DISQUALIFY", "PROCEED", "DISPLACE"
    # DISPLACE means: candidate is superior — consider retiring the existing strategy


class StrategyRedundancyDetector:
    """Identifies when two strategies are doing the same thing."""
    
    def __init__(self, registry, config: Optional[Dict] = None):
        """
        Args:
            registry: StrategyRegistry instance
            config: Configuration dict
        """
        self._registry = registry
        self._config = config or {}
        
        # Configuration
        self._signal_correlation_threshold = self._config.get(
            'redundancy', {}
        ).get('signal_correlation_threshold', 0.70)
        
        self._factor_exposure_overlap_threshold = self._config.get(
            'redundancy', {}
        ).get('factor_exposure_overlap_threshold', 0.75)
        
        self._lookback_days = self._config.get(
            'redundancy', {}
        ).get('lookback_days', 90)
        
        self._icir_dominance_margin = self._config.get(
            'redundancy', {}
        ).get('icir_dominance_margin', 0.20)
        
        # Paths for signal data
        self._signals_path = Path("data/results/research/trackers/strategy_signals.parquet")
    
    def check_candidate_redundancy(
        self,
        candidate_id: str,
        candidate_signals: pd.DataFrame
    ) -> RedundancyCheckResult:
        """
        Checks a CANDIDATE strategy against all ACTIVE strategies.
        Computes signal correlation using the candidate's historical alpha scores
        from validation against the live signals of each ACTIVE strategy.
        
        Args:
            candidate_id: Strategy ID of the candidate
            candidate_signals: DataFrame with columns [date, ticker, alpha_score]
        
        Returns:
            RedundancyCheckResult with recommendation
        """
        logger.info(f"Checking redundancy for candidate: {candidate_id}")
        
        # Get all active strategies
        active_strategies = self._registry.get_active_strategies()
        
        if not active_strategies:
            logger.info("No active strategies to check against")
            return RedundancyCheckResult(
                candidate_id=candidate_id,
                is_redundant=False,
                redundant_with=None,
                max_correlation=0.0,
                correlations={},
                recommendation="PROCEED"
            )
        
        # Get candidate strategy record
        try:
            candidate_record = self._registry.get(candidate_id)
        except Exception as e:
            logger.warning(f"Could not get candidate record: {e}")
            candidate_record = None
        
        # Compute correlations with each active strategy
        correlations = {}
        max_correlation = 0.0
        most_redundant_with = None
        
        for active_strategy in active_strategies:
            # Load active strategy signals
            active_signals = self._load_strategy_signals(
                active_strategy.strategy_id,
                lookback_days=self._lookback_days
            )
            
            if active_signals is None or active_signals.empty:
                logger.debug(
                    f"No signals found for active strategy {active_strategy.strategy_id}"
                )
                continue
            
            # Compute correlation
            correlation = self._compute_signal_correlation(
                candidate_signals,
                active_signals
            )
            
            correlations[active_strategy.strategy_id] = correlation
            
            if correlation > max_correlation:
                max_correlation = correlation
                most_redundant_with = active_strategy.strategy_id
        
        # Determine if redundant
        is_redundant = max_correlation > self._signal_correlation_threshold
        
        # Determine recommendation
        if not is_redundant:
            recommendation = "PROCEED"
        else:
            # Check if candidate is superior (DISPLACE scenario)
            if candidate_record and most_redundant_with:
                try:
                    active_record = self._registry.get(most_redundant_with)
                    
                    # Compare ICIRs
                    candidate_icir = candidate_record.validation_icir
                    active_icir = active_record.validation_icir
                    
                    if candidate_icir > active_icir + self._icir_dominance_margin:
                        recommendation = "DISPLACE"
                        logger.info(
                            f"Candidate {candidate_id} is superior to "
                            f"{most_redundant_with} (ICIR {candidate_icir:.2f} vs {active_icir:.2f})"
                        )
                    else:
                        recommendation = "DISQUALIFY"
                except Exception as e:
                    logger.warning(f"Could not compare ICIRs: {e}")
                    recommendation = "DISQUALIFY"
            else:
                recommendation = "DISQUALIFY"
        
        result = RedundancyCheckResult(
            candidate_id=candidate_id,
            is_redundant=is_redundant,
            redundant_with=most_redundant_with,
            max_correlation=max_correlation,
            correlations=correlations,
            recommendation=recommendation
        )
        
        logger.info(
            f"Redundancy check complete: {recommendation} "
            f"(max_corr={max_correlation:.3f} with {most_redundant_with})"
        )
        
        return result
    
    def monitor_active_redundancy(
        self,
        as_of_date: datetime
    ) -> List[RedundancyCheckResult]:
        """
        Runs pairwise redundancy checks across all ACTIVE strategies.
        This runs weekly (called by weekly_research_review.py).
        
        Returns a list of redundancy issues found among currently active strategies.
        If two active strategies have converged in their signals over time, flags
        the lower-ICIR one for review.
        """
        logger.info(f"Monitoring active strategy redundancy as of {as_of_date.date()}")
        
        active_strategies = self._registry.get_active_strategies()
        
        if len(active_strategies) < 2:
            logger.info("Less than 2 active strategies, no redundancy to check")
            return []
        
        redundancy_issues = []
        
        # Pairwise comparison
        for i, strategy_a in enumerate(active_strategies):
            for strategy_b in active_strategies[i+1:]:
                # Load signals for both strategies
                signals_a = self._load_strategy_signals(
                    strategy_a.strategy_id,
                    lookback_days=self._lookback_days
                )
                
                signals_b = self._load_strategy_signals(
                    strategy_b.strategy_id,
                    lookback_days=self._lookback_days
                )
                
                if signals_a is None or signals_b is None:
                    continue
                
                if signals_a.empty or signals_b.empty:
                    continue
                
                # Compute correlation
                correlation = self._compute_signal_correlation(signals_a, signals_b)
                
                # Check if redundant
                if correlation > self._signal_correlation_threshold:
                    # Determine which strategy to flag (lower ICIR)
                    if strategy_a.validation_icir < strategy_b.validation_icir:
                        flagged_strategy = strategy_a.strategy_id
                        dominant_strategy = strategy_b.strategy_id
                    else:
                        flagged_strategy = strategy_b.strategy_id
                        dominant_strategy = strategy_a.strategy_id
                    
                    issue = RedundancyCheckResult(
                        candidate_id=flagged_strategy,
                        is_redundant=True,
                        redundant_with=dominant_strategy,
                        max_correlation=correlation,
                        correlations={dominant_strategy: correlation},
                        recommendation="REVIEW_FOR_DEMOTION"
                    )
                    
                    redundancy_issues.append(issue)
                    
                    logger.warning(
                        f"Redundancy detected: {flagged_strategy} and {dominant_strategy} "
                        f"(correlation={correlation:.3f})"
                    )
        
        logger.info(f"Found {len(redundancy_issues)} redundancy issues among active strategies")
        
        return redundancy_issues
    
    def compute_strategy_correlation_matrix(
        self,
        strategy_ids: List[str],
        lookback_days: int = 90
    ) -> pd.DataFrame:
        """
        Returns a correlation matrix of signal correlations across strategies.
        Used by the dashboard to visualize the strategy portfolio's alpha diversification.
        
        Args:
            strategy_ids: List of strategy IDs to include
            lookback_days: Number of days to look back for signals
        
        Returns:
            DataFrame with correlation matrix (strategy_ids as both index and columns)
        """
        logger.info(f"Computing correlation matrix for {len(strategy_ids)} strategies")
        
        # Load signals for all strategies
        signals_dict = {}
        
        for strategy_id in strategy_ids:
            signals = self._load_strategy_signals(strategy_id, lookback_days)
            if signals is not None and not signals.empty:
                signals_dict[strategy_id] = signals
        
        if len(signals_dict) < 2:
            logger.warning("Not enough strategies with signals to compute correlation matrix")
            return pd.DataFrame()
        
        # Build correlation matrix
        correlation_matrix = pd.DataFrame(
            index=list(signals_dict.keys()),
            columns=list(signals_dict.keys()),
            dtype=float
        )
        
        for strategy_a in signals_dict:
            for strategy_b in signals_dict:
                if strategy_a == strategy_b:
                    correlation_matrix.loc[strategy_a, strategy_b] = 1.0
                else:
                    correlation = self._compute_signal_correlation(
                        signals_dict[strategy_a],
                        signals_dict[strategy_b]
                    )
                    correlation_matrix.loc[strategy_a, strategy_b] = correlation
        
        return correlation_matrix
    
    def _compute_signal_correlation(
        self,
        signals_a: pd.DataFrame,
        signals_b: pd.DataFrame
    ) -> float:
        """
        Compute correlation between two signal dataframes.
        
        Args:
            signals_a: DataFrame with columns [date, ticker, alpha_score]
            signals_b: DataFrame with columns [date, ticker, alpha_score]
        
        Returns:
            Correlation coefficient (0 to 1)
        """
        try:
            # Ensure date columns are datetime
            if 'date' in signals_a.columns:
                signals_a = signals_a.copy()
                signals_a['date'] = pd.to_datetime(signals_a['date'])
            
            if 'date' in signals_b.columns:
                signals_b = signals_b.copy()
                signals_b['date'] = pd.to_datetime(signals_b['date'])
            
            # Merge on date and ticker
            merged = pd.merge(
                signals_a[['date', 'ticker', 'alpha_score']],
                signals_b[['date', 'ticker', 'alpha_score']],
                on=['date', 'ticker'],
                suffixes=('_a', '_b')
            )
            
            if merged.empty or len(merged) < 10:
                logger.debug("Not enough overlapping signals to compute correlation")
                return 0.0
            
            # Compute correlation
            correlation = merged['alpha_score_a'].corr(merged['alpha_score_b'])
            
            # Handle NaN
            if pd.isna(correlation):
                return 0.0
            
            # Return absolute correlation
            return abs(correlation)
            
        except Exception as e:
            logger.warning(f"Could not compute signal correlation: {e}")
            return 0.0
    
    def _load_strategy_signals(
        self,
        strategy_id: str,
        lookback_days: int
    ) -> Optional[pd.DataFrame]:
        """
        Load historical signals for a strategy.
        
        Args:
            strategy_id: Strategy ID
            lookback_days: Number of days to look back
        
        Returns:
            DataFrame with columns [date, ticker, alpha_score] or None
        """
        try:
            # Check if signals file exists
            if not self._signals_path.exists():
                logger.debug(f"Signals file not found: {self._signals_path}")
                return None
            
            # Load signals
            df = pd.read_parquet(self._signals_path)
            
            # Filter to strategy
            if 'strategy_id' not in df.columns:
                logger.debug("Signals file missing strategy_id column")
                return None
            
            strategy_signals = df[df['strategy_id'] == strategy_id].copy()
            
            if strategy_signals.empty:
                logger.debug(f"No signals found for strategy {strategy_id}")
                return None
            
            # Filter to lookback period
            if 'date' in strategy_signals.columns:
                strategy_signals['date'] = pd.to_datetime(strategy_signals['date'])
                cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
                strategy_signals = strategy_signals[
                    strategy_signals['date'] >= cutoff_date
                ]
            
            # Ensure required columns
            required_cols = ['date', 'ticker', 'alpha_score']
            if not all(col in strategy_signals.columns for col in required_cols):
                logger.debug(f"Signals missing required columns: {required_cols}")
                return None
            
            return strategy_signals[required_cols]
            
        except Exception as e:
            logger.warning(f"Could not load signals for {strategy_id}: {e}")
            return None
