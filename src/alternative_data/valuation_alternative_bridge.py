"""
ValuationAlternativeBridge — Connects credit and pledges to Valuation Engine.

This bridge translates credit ratings and promoter pledge data into inputs
that the Valuation Engine can consume for forensic analysis and distress detection.

It provides:
1. Credit inputs for valuation adjustments (credit spread, distress flags)
2. Pledge inputs for forensic red flags (margin call risk, governance concerns)
3. Combined distress scores for risk-adjusted valuation

Design principle: This bridge is the ONLY place where alternative data flows into
valuation. It ensures research-to-live consistency by using AlternativeFeatureBlock.
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

logger = logging.getLogger(__name__)


class ValuationAlternativeBridge:
    """
    Bridge between alternative data and Valuation Engine.
    
    Translates credit ratings and promoter pledges into valuation-ready inputs.
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
        valuation_config = config.get('valuation_alternative', {})
        self.credit_weight = valuation_config.get('credit_weight', 0.6)
        self.pledge_weight = valuation_config.get('pledge_weight', 0.4)
        self.distress_threshold = valuation_config.get('distress_threshold', 0.6)
        
        # Credit spread mapping (rating → spread in bps)
        self.credit_spread_map = {
            'AAA': 50, 'AA+': 75, 'AA': 100, 'AA-': 125,
            'A+': 150, 'A': 175, 'A-': 200,
            'BBB+': 250, 'BBB': 300, 'BBB-': 350,
            'BB+': 450, 'BB': 550, 'BB-': 650,
            'B+': 800, 'B': 1000, 'B-': 1200,
            'C': 1500, 'D': 2000
        }
        
        logger.info("ValuationAlternativeBridge initialized")
    
    def get_credit_inputs_for_valuation(
        self,
        as_of_date: datetime,
        tickers: List[str]
    ) -> pd.DataFrame:
        """
        Get credit rating inputs for valuation adjustments.
        
        The Valuation Engine uses these to:
        1. Adjust discount rates based on credit risk
        2. Flag companies in financial distress
        3. Apply forensic scrutiny to deteriorating credits
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of ticker symbols
            
        Returns:
            DataFrame with Ticker as index and columns:
                - credit_rating: Current rating (string)
                - credit_spread_bps: Credit spread in basis points
                - credit_distress_flag: 1.0 if in distress, 0.0 otherwise
                - credit_momentum_90d: Rating momentum (-1 to 1)
                - credit_watch_negative: 1.0 if recent downgrade
                - credit_risk_adjustment: Suggested discount rate adjustment (%)
        """
        try:
            # Get company-level features from feature block
            company_features = self.feature_block.compute_company_level_features(
                as_of_date,
                tickers
            )
            
            if company_features.empty:
                logger.warning("No company features for credit inputs")
                return self._empty_credit_inputs(tickers)
            
            # Load raw credit data for ratings
            credit_df = self.registry.alternative.load_credit_ratings(as_of_date, tickers=tickers)
            
            # Build credit inputs
            credit_inputs = []
            for ticker in tickers:
                if ticker in company_features.index:
                    features = company_features.loc[ticker]
                    
                    # Get current rating
                    ticker_credit = credit_df[credit_df.get('Ticker', pd.Series()) == ticker] if not credit_df.empty else pd.DataFrame()
                    if not ticker_credit.empty and 'CurrentRating' in ticker_credit.columns:
                        current_rating = ticker_credit.iloc[-1]['CurrentRating']
                    else:
                        current_rating = 'BBB'  # Default to investment grade
                    
                    # Map rating to spread
                    credit_spread = self.credit_spread_map.get(current_rating, 300)
                    
                    # Extract features
                    distress_flag = features.get('credit_in_distress', 0.0)
                    momentum = features.get('credit_rating_momentum_90d', 0.0)
                    watch_negative = features.get('credit_watch_negative', 0.0)
                    
                    # Risk adjustment for discount rate
                    # Higher spread → higher discount rate
                    risk_adjustment = (credit_spread - 100) / 100.0  # Normalize around A rating
                    risk_adjustment = float(np.clip(risk_adjustment, 0, 5))  # Cap at +5%
                    
                    credit_inputs.append({
                        'Ticker': ticker,
                        'credit_rating': current_rating,
                        'credit_spread_bps': credit_spread,
                        'credit_distress_flag': distress_flag,
                        'credit_momentum_90d': momentum,
                        'credit_watch_negative': watch_negative,
                        'credit_risk_adjustment': risk_adjustment
                    })
                else:
                    # No coverage
                    credit_inputs.append(self._empty_credit_input_row(ticker))
            
            credit_df_out = pd.DataFrame(credit_inputs).set_index('Ticker')
            
            logger.debug(f"Credit inputs computed for {len(credit_df_out)} tickers")
            return credit_df_out
            
        except Exception as e:
            logger.error(f"Error building credit inputs: {e}")
            return self._empty_credit_inputs(tickers)
    
    def get_pledge_inputs_for_forensics(
        self,
        as_of_date: datetime,
        tickers: List[str]
    ) -> pd.DataFrame:
        """
        Get promoter pledge inputs for forensic analysis.
        
        The Valuation Engine uses these to:
        1. Flag governance red flags (high/increasing pledges)
        2. Assess margin call risk
        3. Apply valuation haircuts to risky companies
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of ticker symbols
            
        Returns:
            DataFrame with Ticker as index and columns:
                - pledge_pct: Current pledge percentage (0-1)
                - pledge_risk_score: Composite risk score (0-1)
                - pledge_margin_call_risk: 1.0 if high risk, 0.0 otherwise
                - pledge_governance_flag: 1.0 if governance concern
                - pledge_increasing_flag: 1.0 if pledge increasing
                - pledge_valuation_haircut: Suggested valuation discount (%)
        """
        try:
            # Get company-level features from feature block
            company_features = self.feature_block.compute_company_level_features(
                as_of_date,
                tickers
            )
            
            if company_features.empty:
                logger.warning("No company features for pledge inputs")
                return self._empty_pledge_inputs(tickers)
            
            # Build pledge inputs
            pledge_inputs = []
            for ticker in tickers:
                if ticker in company_features.index:
                    features = company_features.loc[ticker]
                    
                    # Extract features
                    pledge_pct = features.get('pledge_pct_current', 0.0)
                    risk_score = features.get('pledge_risk_score', 0.0)
                    high_flag = features.get('pledge_high_flag', 0.0)
                    increasing_flag = features.get('pledge_increasing_2q', 0.0)
                    
                    # Margin call risk (high pledge + increasing)
                    margin_call_risk = 1.0 if (pledge_pct > 0.5 and increasing_flag > 0.5) else 0.0
                    
                    # Governance flag (high pledge is a red flag)
                    governance_flag = high_flag
                    
                    # Valuation haircut
                    # Apply discount based on risk score
                    # 0% risk → 0% haircut, 100% risk → 30% haircut
                    valuation_haircut = risk_score * 30.0
                    
                    pledge_inputs.append({
                        'Ticker': ticker,
                        'pledge_pct': pledge_pct,
                        'pledge_risk_score': risk_score,
                        'pledge_margin_call_risk': margin_call_risk,
                        'pledge_governance_flag': governance_flag,
                        'pledge_increasing_flag': increasing_flag,
                        'pledge_valuation_haircut': valuation_haircut
                    })
                else:
                    # No coverage
                    pledge_inputs.append(self._empty_pledge_input_row(ticker))
            
            pledge_df = pd.DataFrame(pledge_inputs).set_index('Ticker')
            
            logger.debug(f"Pledge inputs computed for {len(pledge_df)} tickers")
            return pledge_df
            
        except Exception as e:
            logger.error(f"Error building pledge inputs: {e}")
            return self._empty_pledge_inputs(tickers)
    
    def get_combined_distress_score(
        self,
        as_of_date: datetime,
        tickers: List[str]
    ) -> pd.DataFrame:
        """
        Get combined distress score from credit and pledge data.
        
        This is a composite metric that combines:
        - Credit distress (low rating, negative momentum)
        - Pledge risk (high pledge, increasing trend)
        
        The Valuation Engine uses this as a master red flag for
        companies requiring extra scrutiny or exclusion.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of ticker symbols
            
        Returns:
            DataFrame with Ticker as index and columns:
                - distress_score: Composite score (0-1, higher = more distress)
                - distress_flag: 1.0 if score > threshold
                - distress_source: Primary source of distress
                - recommended_action: "EXCLUDE", "HAIRCUT", or "MONITOR"
        """
        try:
            # Get credit and pledge inputs
            credit_inputs = self.get_credit_inputs_for_valuation(as_of_date, tickers)
            pledge_inputs = self.get_pledge_inputs_for_forensics(as_of_date, tickers)
            
            # Combine into distress scores
            distress_data = []
            for ticker in tickers:
                # Get credit distress
                if ticker in credit_inputs.index:
                    credit_distress = credit_inputs.loc[ticker, 'credit_distress_flag']
                    credit_momentum = credit_inputs.loc[ticker, 'credit_momentum_90d']
                    credit_component = credit_distress * 0.7 + max(0, -credit_momentum) * 0.3
                else:
                    credit_component = 0.0
                
                # Get pledge distress
                if ticker in pledge_inputs.index:
                    pledge_risk = pledge_inputs.loc[ticker, 'pledge_risk_score']
                    pledge_component = pledge_risk
                else:
                    pledge_component = 0.0
                
                # Weighted combination
                distress_score = (
                    self.credit_weight * credit_component +
                    self.pledge_weight * pledge_component
                )
                distress_score = float(np.clip(distress_score, 0, 1))
                
                # Distress flag
                distress_flag = 1.0 if distress_score > self.distress_threshold else 0.0
                
                # Determine primary source
                if credit_component > pledge_component:
                    distress_source = "CREDIT"
                elif pledge_component > 0:
                    distress_source = "PLEDGE"
                else:
                    distress_source = "NONE"
                
                # Recommended action
                if distress_score > 0.8:
                    action = "EXCLUDE"
                elif distress_score > 0.5:
                    action = "HAIRCUT"
                else:
                    action = "MONITOR"
                
                distress_data.append({
                    'Ticker': ticker,
                    'distress_score': distress_score,
                    'distress_flag': distress_flag,
                    'distress_source': distress_source,
                    'recommended_action': action,
                    'credit_component': credit_component,
                    'pledge_component': pledge_component
                })
            
            distress_df = pd.DataFrame(distress_data).set_index('Ticker')
            
            # Log high-distress companies
            high_distress = distress_df[distress_df['distress_flag'] > 0.5]
            if not high_distress.empty:
                logger.warning(
                    f"High distress detected in {len(high_distress)} companies: "
                    f"{high_distress.index.tolist()}"
                )
            
            return distress_df
            
        except Exception as e:
            logger.error(f"Error computing combined distress score: {e}")
            return self._empty_distress_scores(tickers)
    
    def get_valuation_context(
        self,
        as_of_date: datetime,
        tickers: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """
        Get comprehensive valuation context from alternative data.
        
        This is a convenience method that bundles all valuation-relevant
        alternative data into a single dict.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of ticker symbols
            
        Returns:
            Dict with all valuation-relevant alternative data
        """
        try:
            credit_inputs = self.get_credit_inputs_for_valuation(as_of_date, tickers)
            pledge_inputs = self.get_pledge_inputs_for_forensics(as_of_date, tickers)
            distress_scores = self.get_combined_distress_score(as_of_date, tickers)
            
            return {
                'credit_inputs': credit_inputs,
                'pledge_inputs': pledge_inputs,
                'distress_scores': distress_scores,
                'as_of_date': as_of_date
            }
            
        except Exception as e:
            logger.error(f"Error building valuation context: {e}")
            return {
                'credit_inputs': self._empty_credit_inputs(tickers),
                'pledge_inputs': self._empty_pledge_inputs(tickers),
                'distress_scores': self._empty_distress_scores(tickers),
                'as_of_date': as_of_date
            }
    
    def _empty_credit_input_row(self, ticker: str) -> Dict:
        """Return empty credit input row for a ticker."""
        return {
            'Ticker': ticker,
            'credit_rating': 'BBB',
            'credit_spread_bps': 300,
            'credit_distress_flag': 0.0,
            'credit_momentum_90d': 0.0,
            'credit_watch_negative': 0.0,
            'credit_risk_adjustment': 0.0
        }
    
    def _empty_credit_inputs(self, tickers: List[str]) -> pd.DataFrame:
        """Return empty credit inputs DataFrame."""
        rows = [self._empty_credit_input_row(t) for t in tickers]
        return pd.DataFrame(rows).set_index('Ticker')
    
    def _empty_pledge_input_row(self, ticker: str) -> Dict:
        """Return empty pledge input row for a ticker."""
        return {
            'Ticker': ticker,
            'pledge_pct': 0.0,
            'pledge_risk_score': 0.0,
            'pledge_margin_call_risk': 0.0,
            'pledge_governance_flag': 0.0,
            'pledge_increasing_flag': 0.0,
            'pledge_valuation_haircut': 0.0
        }
    
    def _empty_pledge_inputs(self, tickers: List[str]) -> pd.DataFrame:
        """Return empty pledge inputs DataFrame."""
        rows = [self._empty_pledge_input_row(t) for t in tickers]
        return pd.DataFrame(rows).set_index('Ticker')
    
    def _empty_distress_scores(self, tickers: List[str]) -> pd.DataFrame:
        """Return empty distress scores DataFrame."""
        rows = []
        for ticker in tickers:
            rows.append({
                'Ticker': ticker,
                'distress_score': 0.0,
                'distress_flag': 0.0,
                'distress_source': 'NONE',
                'recommended_action': 'MONITOR',
                'credit_component': 0.0,
                'pledge_component': 0.0
            })
        return pd.DataFrame(rows).set_index('Ticker')
