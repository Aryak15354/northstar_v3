"""
MacroAlternativeBridge — Connects GST and power to Macro Transmission Engine.

This bridge translates alternative economic activity data (GST, power consumption)
into inputs that the Macro Transmission Engine can consume. It provides:
1. Kalman observation vectors for state estimation
2. Macro forecast inputs for regime-conditional forecasting
3. Sector-level macro sensitivities based on economic activity

Design principle: This bridge is the ONLY place where alternative data flows into
macro forecasting. It ensures research-to-live consistency by using AlternativeFeatureBlock.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd
import numpy as np

# lazy under TYPE_CHECKING to break the ingestion<->core<->alternative_data cycle
if TYPE_CHECKING:
    from src.ingestion.ingestion_registry import IngestionRegistry
from src.alternative_data.alternative_feature_block import AlternativeFeatureBlock
from src.alternative_data.alternative_state import (
    AlternativeDataState,
    EconomicActivityRegime
)

logger = logging.getLogger(__name__)


class MacroAlternativeBridge:
    """
    Bridge between alternative data and Macro Transmission Engine.
    
    Translates GST and power consumption signals into macro-ready inputs.
    """
    
    def __init__(self, registry: "IngestionRegistry", config: dict):
        """
        Initialize bridge with registry and configuration.
        
        Args:
            registry: "IngestionRegistry" for data access
            config: Configuration dict
        """
        self.registry = registry
        self.config = config
        self.feature_block = AlternativeFeatureBlock(registry, config)
        
        # Configuration
        macro_config = config.get('macro_alternative', {})
        self.gst_weight = macro_config.get('gst_weight', 0.6)
        self.power_weight = macro_config.get('power_weight', 0.4)
        self.forecast_confidence_base = macro_config.get('forecast_confidence_base', 0.7)
        
        logger.info("MacroAlternativeBridge initialized")
    
    def get_kalman_observation_vector(self, as_of_date: datetime) -> Dict[str, float]:
        """
        Get observation vector for Kalman filter state estimation.
        
        The Kalman filter in macro_transmission_engine uses this to update
        its belief about the current economic state. These observations
        complement traditional macro indicators (GDP, inflation, etc.).
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            Dict with:
                - gst_yoy_growth_zscore: Z-scored GST year-over-year growth
                - power_yoy_growth_zscore: Z-scored power consumption growth
                - composite_activity_score: Weighted composite (-1 to 1)
        """
        try:
            # Get market-level features from feature block
            market_features = self.feature_block.compute_market_level_features(as_of_date)
            
            if market_features.empty:
                logger.warning("No market features available for Kalman observation")
                return self._empty_kalman_observation()
            
            # Extract GST and power features
            gst_yoy = market_features['gst_yoy_growth'].iloc[0]
            power_yoy = market_features['power_yoy_growth'].iloc[0]
            gst_regime = market_features['gst_regime_numeric'].iloc[0]
            power_proxy = market_features['power_industrial_proxy'].iloc[0]
            
            # Composite activity score (weighted combination)
            composite_score = (
                self.gst_weight * gst_yoy +
                self.power_weight * power_yoy
            )
            
            # Clip to reasonable range
            composite_score = float(np.clip(composite_score, -3, 3))
            
            observation = {
                'gst_yoy_growth_zscore': float(gst_yoy),
                'power_yoy_growth_zscore': float(power_yoy),
                'composite_activity_score': composite_score,
                'gst_regime_numeric': float(gst_regime),
                'power_industrial_proxy': float(power_proxy)
            }
            
            logger.debug(f"Kalman observation: composite={composite_score:.3f}")
            return observation
            
        except Exception as e:
            logger.error(f"Error building Kalman observation: {e}")
            return self._empty_kalman_observation()
    
    def get_macro_forecast_inputs(
        self,
        as_of_date: datetime,
        forecast_horizon_months: int = 3
    ) -> Dict[str, float]:
        """
        Get inputs for macro forecasting with regime conditioning.
        
        The Bayesian VAR forecaster uses these to condition forecasts on
        current economic activity regime. This allows regime-dependent
        forecast adjustments.
        
        Args:
            as_of_date: Point-in-time date
            forecast_horizon_months: Forecast horizon in months
            
        Returns:
            Dict with:
                - current_activity_regime: Numeric regime code (-2 to 2)
                - activity_momentum: Rate of change in activity (z-score)
                - leading_indicator_signal: Forward-looking signal
                - forecast_confidence_modifier: Adjustment to forecast uncertainty
        """
        try:
            # Get market-level features
            market_features = self.feature_block.compute_market_level_features(as_of_date)
            
            if market_features.empty:
                logger.warning("No market features for macro forecast inputs")
                return self._empty_forecast_inputs()
            
            # Extract regime and momentum
            gst_regime = market_features['gst_regime_numeric'].iloc[0]
            gst_trend_accel = market_features['gst_trend_accel'].iloc[0]
            power_mom = market_features['power_mom_change'].iloc[0]
            
            # Activity momentum (composite of GST acceleration and power momentum)
            activity_momentum = (
                0.6 * gst_trend_accel +
                0.4 * power_mom
            )
            
            # Leading indicator signal (power leads GST by ~1 month)
            leading_signal = power_mom
            
            # Forecast confidence modifier
            # Higher confidence when regime is clear and stable
            regime_clarity = abs(gst_regime)  # 0 = neutral, 2 = clear regime
            confidence_modifier = self.forecast_confidence_base + (0.15 * regime_clarity / 2.0)
            confidence_modifier = float(np.clip(confidence_modifier, 0.5, 1.0))
            
            forecast_inputs = {
                'current_activity_regime': float(gst_regime),
                'activity_momentum': float(activity_momentum),
                'leading_indicator_signal': float(leading_signal),
                'forecast_confidence_modifier': confidence_modifier,
                'forecast_horizon_months': forecast_horizon_months
            }
            
            logger.debug(
                f"Macro forecast inputs: regime={gst_regime:.1f}, "
                f"momentum={activity_momentum:.3f}"
            )
            return forecast_inputs
            
        except Exception as e:
            logger.error(f"Error building macro forecast inputs: {e}")
            return self._empty_forecast_inputs()
    
    def get_sector_macro_sensitivities(self, as_of_date: datetime) -> pd.DataFrame:
        """
        Get sector-level macro sensitivities based on economic activity.
        
        Different sectors have different sensitivities to economic activity:
        - Cyclicals (auto, capital goods) are highly sensitive
        - Defensives (pharma, FMCG) are less sensitive
        - Financials are moderately sensitive
        
        This returns a DataFrame that macro_alpha_adjuster.py can use to
        adjust sector exposures based on current activity regime.
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            DataFrame with sector as index and columns:
                - gst_sensitivity: Sensitivity to GST growth (-1 to 1)
                - power_sensitivity: Sensitivity to power consumption
                - activity_beta: Overall economic activity beta
                - regime_adjustment: Suggested weight adjustment
        """
        try:
            # Get current activity regime
            market_features = self.feature_block.compute_market_level_features(as_of_date)
            
            if market_features.empty:
                logger.warning("No market features for sector sensitivities")
                return self._empty_sector_sensitivities()
            
            gst_regime = market_features['gst_regime_numeric'].iloc[0]
            composite_activity = market_features['gst_yoy_growth'].iloc[0]
            
            # Define sector sensitivities (calibrated from historical analysis)
            sector_params = {
                'AUTO': {'gst': 1.2, 'power': 0.9, 'beta': 1.3},
                'CAPITAL_GOODS': {'gst': 1.1, 'power': 1.0, 'beta': 1.2},
                'METALS': {'gst': 0.9, 'power': 1.1, 'beta': 1.1},
                'REALTY': {'gst': 1.0, 'power': 0.7, 'beta': 1.0},
                'BANKS': {'gst': 0.8, 'power': 0.6, 'beta': 0.9},
                'FINANCIAL_SERVICES': {'gst': 0.7, 'power': 0.5, 'beta': 0.8},
                'IT': {'gst': 0.3, 'power': 0.2, 'beta': 0.4},
                'PHARMA': {'gst': 0.2, 'power': 0.3, 'beta': 0.3},
                'FMCG': {'gst': 0.4, 'power': 0.4, 'beta': 0.5},
                'CONSUMER_DURABLES': {'gst': 0.9, 'power': 0.8, 'beta': 1.0},
                'TELECOM': {'gst': 0.5, 'power': 0.6, 'beta': 0.6},
                'ENERGY': {'gst': 0.6, 'power': 0.9, 'beta': 0.7},
                'UTILITIES': {'gst': 0.4, 'power': 0.8, 'beta': 0.5}
            }
            
            # Build DataFrame
            sector_data = []
            for sector, params in sector_params.items():
                # Regime adjustment: overweight cyclicals in expansion, underweight in contraction
                if gst_regime >= 1:  # Expansion/Recovering
                    regime_adj = params['beta'] * 0.1  # Overweight high-beta sectors
                elif gst_regime <= -1:  # Contraction/Slowing
                    regime_adj = -params['beta'] * 0.1  # Underweight high-beta sectors
                else:  # Neutral
                    regime_adj = 0.0
                
                sector_data.append({
                    'Sector': sector,
                    'gst_sensitivity': params['gst'],
                    'power_sensitivity': params['power'],
                    'activity_beta': params['beta'],
                    'regime_adjustment': regime_adj,
                    'current_regime': gst_regime
                })
            
            sector_df = pd.DataFrame(sector_data).set_index('Sector')
            
            logger.debug(f"Sector sensitivities computed for {len(sector_df)} sectors")
            return sector_df
            
        except Exception as e:
            logger.error(f"Error computing sector sensitivities: {e}")
            return self._empty_sector_sensitivities()
    
    def get_activity_regime_context(self, as_of_date: datetime) -> Dict[str, any]:
        """
        Get comprehensive activity regime context for macro engine.
        
        This is a convenience method that bundles all macro-relevant
        alternative data into a single dict.
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            Dict with all macro-relevant alternative data
        """
        try:
            kalman_obs = self.get_kalman_observation_vector(as_of_date)
            forecast_inputs = self.get_macro_forecast_inputs(as_of_date)
            sector_sens = self.get_sector_macro_sensitivities(as_of_date)
            
            return {
                'kalman_observation': kalman_obs,
                'forecast_inputs': forecast_inputs,
                'sector_sensitivities': sector_sens,
                'as_of_date': as_of_date
            }
            
        except Exception as e:
            logger.error(f"Error building activity regime context: {e}")
            return {
                'kalman_observation': self._empty_kalman_observation(),
                'forecast_inputs': self._empty_forecast_inputs(),
                'sector_sensitivities': self._empty_sector_sensitivities(),
                'as_of_date': as_of_date
            }
    
    def _empty_kalman_observation(self) -> Dict[str, float]:
        """Return neutral observation when data unavailable."""
        return {
            'gst_yoy_growth_zscore': 0.0,
            'power_yoy_growth_zscore': 0.0,
            'composite_activity_score': 0.0,
            'gst_regime_numeric': 0.0,
            'power_industrial_proxy': 0.0
        }
    
    def _empty_forecast_inputs(self) -> Dict[str, float]:
        """Return neutral forecast inputs when data unavailable."""
        return {
            'current_activity_regime': 0.0,
            'activity_momentum': 0.0,
            'leading_indicator_signal': 0.0,
            'forecast_confidence_modifier': 0.5,
            'forecast_horizon_months': 3
        }
    
    def _empty_sector_sensitivities(self) -> pd.DataFrame:
        """Return empty sector sensitivities DataFrame."""
        return pd.DataFrame(columns=[
            'gst_sensitivity',
            'power_sensitivity',
            'activity_beta',
            'regime_adjustment',
            'current_regime'
        ])
