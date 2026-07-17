"""
Factor Registry — Single entry point for all factor signal computation.

STATUS (I.10): currently DORMANT. It is only constructed when
``use_academic_factors`` (or ``factors.enabled``) is True, which is False in both
Kaggle build configs. The ACTIVE producer of piotroski_fscore / bab_signal /
amihud_illiquidity / max_ret_20d / earnings_quality_ratio (and their cs_z/cs_rank
variants) is ``src/factors/gap9_academic_factors.py``. Two parallel
implementations of the same signals are a drift risk — a decision on whether to
retire this registry or promote it over Gap9 is pending (do not activate both).

The registry:
1. Knows about all five factor classes
2. Instantiates them with the correct registry and config
3. Provides a single compute_all() method that returns the full
   factor feature matrix for a given date and universe
4. Tracks which factors are enabled/disabled in config
5. Reports coverage diagnostics for all factors
"""

from datetime import datetime
import pandas as pd
import numpy as np
import logging

from .bab_factor import BABFactor
from .amihud_factor import AmihudFactor
from .piotroski_factor import PiotroskiFactor
from .max_factor import MAXFactor
from .earnings_quality_factor import EarningsQualityFactor
from .operating_profitability_factor import OperatingProfitabilityFactor
from .earnings_surprise_factor import EarningsSurpriseFactor
from .promoter_pledge_factor import PromoterPledgeFactor
from .bulk_deal_factor import BulkDealFactor
from .ivol_factor import IVOLFactor

logger = logging.getLogger(__name__)


class FactorRegistry:
    """Registry for all factor signal computation."""
    
    FACTOR_CLASSES = {
        'bab': BABFactor,
        'amihud': AmihudFactor,
        'piotroski': PiotroskiFactor,
        'max': MAXFactor,
        'earnings_quality': EarningsQualityFactor,
        'operating_profitability': OperatingProfitabilityFactor,
        'earnings_surprise': EarningsSurpriseFactor,
        'promoter_pledge': PromoterPledgeFactor,
        'bulk_deal': BulkDealFactor,
        'ivol': IVOLFactor,
    }
    
    def __init__(self, registry, config: dict):
        """
        Parameters
        ----------
        registry : IngestionRegistry
            The unified data access layer from Gap 1.
        config : dict
            Full system config.
        """
        self._registry = registry
        self._config = config
        self._enabled = config.get('factors', {}).get('enabled_factors', list(self.FACTOR_CLASSES.keys()))
        
        # Instantiate all enabled factor objects
        self._factors = {}
        for name, cls in self.FACTOR_CLASSES.items():
            if name in self._enabled:
                try:
                    self._factors[name] = cls(registry, config)
                    logger.info(f"Initialized factor: {name}")
                except Exception as e:
                    logger.warning(f"Failed to initialize factor {name}: {e}")
    
    def compute_all(
        self,
        as_of_date: datetime,
        tickers: list,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Compute all enabled factors and return a merged feature DataFrame.
        
        Returns a DataFrame indexed by ticker with columns:
        - {factor_name}_raw
        - {factor_name}_zscore    ← PRIMARY: use this in FeatureFactory
        - {factor_name}_rank      ← SECONDARY: use for robustness checks
        - {factor_name}_available ← DIAGNOSTIC: coverage indicator
        
        Factors that fail computation return NaN columns rather than crashing.
        """
        all_results = []
        
        for name, factor in self._factors.items():
            try:
                result = factor.compute(as_of_date, tickers, use_cache=use_cache)
                all_results.append(result)
                availability_cols = [col for col in result.columns if isinstance(col, str) and col.endswith('_available')]
                if availability_cols:
                    available_count = int(result[availability_cols].any(axis=1).sum())
                    logger.debug(
                        "Computed factor %s for %s: %s/%s tickers",
                        name,
                        as_of_date.date(),
                        available_count,
                        len(tickers),
                    )
            except Exception as e:
                logger.warning(f"Factor {name} failed for {as_of_date}: {e}")
                # Return NaN DataFrame for this factor — don't crash the pipeline
                if hasattr(factor, 'get_output_columns'):
                    columns = factor.get_output_columns(include_meta=True)
                    nan_payload = {}
                    for col in columns:
                        nan_payload[col] = False if str(col).endswith('_available') else np.nan
                    nan_result = pd.DataFrame(nan_payload, index=tickers)
                else:
                    nan_result = pd.DataFrame(
                        {
                            f'{name}_raw': np.nan,
                            f'{name}_zscore': np.nan,
                            f'{name}_rank': np.nan,
                            f'{name}_available': False,
                        },
                        index=tickers
                    )
                all_results.append(nan_result)
        
        if not all_results:
            return pd.DataFrame(index=tickers)
        
        return pd.concat(all_results, axis=1)
    
    def get_coverage_report(
        self,
        as_of_date: datetime,
        tickers: list
    ) -> dict:
        """
        Returns coverage diagnostics for all factors on a given date.
        """
        return {
            name: factor.get_coverage(as_of_date, tickers)
            for name, factor in self._factors.items()
        }
    
    def get_feature_names(self, include_raw: bool = False) -> list:
        """
        Returns the list of feature column names that compute_all() produces.
        """
        names = []
        for factor_name, factor in self._factors.items():
            if hasattr(factor, 'get_feature_names'):
                names.extend(factor.get_feature_names(include_raw=include_raw))
            else:
                if include_raw:
                    names.append(f'{factor_name}_raw')
                names.append(f'{factor_name}_zscore')
                names.append(f'{factor_name}_rank')
        return names
    
    def get_enabled_factors(self) -> list:
        """Returns list of enabled factor names."""
        return list(self._factors.keys())
