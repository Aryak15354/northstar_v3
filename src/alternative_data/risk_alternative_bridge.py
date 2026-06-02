"""
RiskAlternativeBridge — Connects alternative data to Risk Management System.

This bridge translates alternative data signals into risk management inputs
for portfolio construction and position sizing. It provides:

1. Portfolio-level alternative risk metrics (exposure to distressed companies)
2. New position risk checks (pre-trade validation)
3. Systemic risk signals (market-wide stress indicators)

Design principle: This bridge is the ONLY place where alternative data flows into
risk management. It ensures research-to-live consistency by using AlternativeFeatureBlock.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from src.ingestion.ingestion_registry import IngestionRegistry
from src.alternative_data.alternative_feature_block import AlternativeFeatureBlock
from src.alternative_data.alternative_state import (
    AlternativeDataState,
    EconomicActivityRegime,
    SmartMoneySignal
)

logger = logging.getLogger(__name__)


class RiskAlternativeBridge:
    """
    Bridge between alternative data and Risk Management System.
    
    Translates alternative data signals into risk-ready inputs for
    portfolio construction and position management.
    """
    
    def __init__(self, registry: IngestionRegistry, config: dict):
        """
        Initialize bridge with registry and configuration.
        
        Args:
            registry: IngestionRegistry for data access
            config: Configuration dict
        """
        self.registry = registry
        self.config = config
        self.feature_block = AlternativeFeatureBlock(registry, config)
        
        # Configuration
        risk_config = config.get('risk_alternative', {})
        self.max_distress_exposure = risk_config.get('max_distress_exposure', 0.15)
        self.max_high_pledge_exposure = risk_config.get('max_high_pledge_exposure', 0.20)
        self.systemic_stress_threshold = risk_config.get('systemic_stress_threshold', 0.6)
        self.position_size_limit_distress = risk_config.get('position_size_limit_distress', 0.02)
        
        logger.info("RiskAlternativeBridge initialized")
    
    def get_portfolio_alternative_risk(
        self,
        as_of_date: datetime,
        current_positions: pd.DataFrame
    ) -> Dict[str, any]:
        """
        Get portfolio-level alternative risk metrics.
        
        The Risk Management System uses these to:
        1. Monitor exposure to distressed companies
        2. Track concentration in high-pledge names
        3. Assess portfolio vulnerability to credit/governance shocks
        
        Args:
            as_of_date: Point-in-time date
            current_positions: DataFrame with Ticker and Weight columns
            
        Returns:
            Dict with:
                - distress_exposure: % of portfolio in distressed companies
                - high_pledge_exposure: % of portfolio in high-pledge companies
                - credit_downgrade_exposure: % exposed to negative credit momentum
                - smart_money_alignment: Alignment with institutional flows (-1 to 1)
                - risk_level: "LOW", "MEDIUM", "HIGH", or "CRITICAL"
                - warnings: List of warning messages
                - recommendations: List of recommended actions
        """
        try:
            if current_positions.empty:
                logger.warning("No current positions for portfolio risk assessment")
                return self._empty_portfolio_risk()
            
            tickers = current_positions['Ticker'].tolist()
            weights = current_positions.set_index('Ticker')['Weight']
            
            # Get company-level features
            company_features = self.feature_block.compute_company_level_features(
                as_of_date,
                tickers
            )
            
            if company_features.empty:
                logger.warning("No company features for portfolio risk")
                return self._empty_portfolio_risk()
            
            # Calculate exposures
            distress_exposure = 0.0
            high_pledge_exposure = 0.0
            downgrade_exposure = 0.0
            smart_money_misalignment = 0.0
            
            for ticker in tickers:
                if ticker not in company_features.index:
                    continue
                
                weight = weights.get(ticker, 0.0)
                features = company_features.loc[ticker]
                
                # Distress exposure
                if features.get('credit_in_distress', 0.0) > 0.5:
                    distress_exposure += weight
                
                # High pledge exposure
                if features.get('pledge_high_flag', 0.0) > 0.5:
                    high_pledge_exposure += weight
                
                # Downgrade exposure
                if features.get('credit_watch_negative', 0.0) > 0.5:
                    downgrade_exposure += weight
                
                # Smart money misalignment (holding distribution names)
                if features.get('bulk_distribution_flag', 0.0) > 0.5:
                    smart_money_misalignment += weight
            
            # Smart money alignment (positive = aligned with accumulation)
            smart_money_alignment = -smart_money_misalignment
            
            # Determine risk level
            risk_level, warnings, recommendations = self._assess_portfolio_risk_level(
                distress_exposure,
                high_pledge_exposure,
                downgrade_exposure,
                smart_money_misalignment
            )
            
            portfolio_risk = {
                'distress_exposure': float(distress_exposure),
                'high_pledge_exposure': float(high_pledge_exposure),
                'credit_downgrade_exposure': float(downgrade_exposure),
                'smart_money_alignment': float(smart_money_alignment),
                'risk_level': risk_level,
                'warnings': warnings,
                'recommendations': recommendations,
                'as_of_date': as_of_date
            }
            
            logger.info(
                f"Portfolio risk: {risk_level} "
                f"(distress={distress_exposure:.1%}, pledge={high_pledge_exposure:.1%})"
            )
            
            return portfolio_risk
            
        except Exception as e:
            logger.error(f"Error computing portfolio alternative risk: {e}")
            return self._empty_portfolio_risk()
    
    def get_new_position_risk_check(
        self,
        as_of_date: datetime,
        ticker: str,
        proposed_weight: float,
        current_positions: Optional[pd.DataFrame] = None
    ) -> Dict[str, any]:
        """
        Pre-trade risk check for new position using alternative data.
        
        The Risk Management System uses this to validate new positions
        before execution. It can PASS, WARN, or BLOCK trades.
        
        Args:
            as_of_date: Point-in-time date
            ticker: Ticker symbol for new position
            proposed_weight: Proposed portfolio weight (0-1)
            current_positions: Optional current portfolio positions
            
        Returns:
            Dict with:
                - status: "PASS", "WARN", or "BLOCK"
                - risk_score: Composite risk score (0-1)
                - flags: List of risk flags raised
                - max_allowed_weight: Maximum allowed weight for this ticker
                - recommended_weight: Recommended weight (may be < proposed)
                - rationale: Human-readable explanation
        """
        try:
            # Get company-level features
            company_features = self.feature_block.compute_company_level_features(
                as_of_date,
                [ticker]
            )
            
            if company_features.empty or ticker not in company_features.index:
                logger.warning(f"No features for {ticker}, allowing with caution")
                return {
                    'status': 'WARN',
                    'risk_score': 0.5,
                    'flags': ['NO_ALTERNATIVE_DATA'],
                    'max_allowed_weight': proposed_weight,
                    'recommended_weight': proposed_weight * 0.8,
                    'rationale': 'No alternative data coverage - proceed with caution'
                }
            
            features = company_features.loc[ticker]
            
            # Collect risk flags
            flags = []
            risk_components = []
            
            # Credit risk
            if features.get('credit_in_distress', 0.0) > 0.5:
                flags.append('CREDIT_DISTRESS')
                risk_components.append(0.8)
            elif features.get('credit_watch_negative', 0.0) > 0.5:
                flags.append('CREDIT_WATCH_NEGATIVE')
                risk_components.append(0.4)
            
            # Pledge risk
            pledge_risk = features.get('pledge_risk_score', 0.0)
            if pledge_risk > 0.7:
                flags.append('HIGH_PLEDGE_RISK')
                risk_components.append(0.7)
            elif pledge_risk > 0.4:
                flags.append('ELEVATED_PLEDGE')
                risk_components.append(0.3)
            
            # Smart money distribution
            if features.get('bulk_distribution_flag', 0.0) > 0.5:
                flags.append('INSTITUTIONAL_SELLING')
                risk_components.append(0.3)
            
            # Compute composite risk score
            if risk_components:
                risk_score = float(np.mean(risk_components))
            else:
                risk_score = 0.0
            
            # Determine status and limits
            if risk_score > 0.7:
                status = 'BLOCK'
                max_allowed_weight = 0.0
                recommended_weight = 0.0
                rationale = f"High alternative risk (score={risk_score:.2f}). Flags: {', '.join(flags)}"
            elif risk_score > 0.4:
                status = 'WARN'
                max_allowed_weight = self.position_size_limit_distress
                recommended_weight = min(proposed_weight, max_allowed_weight)
                rationale = f"Elevated alternative risk (score={risk_score:.2f}). Limit position size. Flags: {', '.join(flags)}"
            else:
                status = 'PASS'
                max_allowed_weight = proposed_weight
                recommended_weight = proposed_weight
                rationale = f"Alternative risk acceptable (score={risk_score:.2f})"
            
            # Check portfolio-level constraints if current positions provided
            if current_positions is not None and not current_positions.empty:
                portfolio_check = self._check_portfolio_constraints(
                    as_of_date,
                    ticker,
                    proposed_weight,
                    current_positions,
                    features
                )
                
                if portfolio_check['constraint_violated']:
                    status = 'BLOCK'
                    flags.extend(portfolio_check['violated_constraints'])
                    rationale += f" Portfolio constraint violated: {portfolio_check['reason']}"
            
            result = {
                'status': status,
                'risk_score': risk_score,
                'flags': flags,
                'max_allowed_weight': float(max_allowed_weight),
                'recommended_weight': float(recommended_weight),
                'rationale': rationale,
                'ticker': ticker,
                'proposed_weight': proposed_weight
            }
            
            if status == 'BLOCK':
                logger.warning(f"Position BLOCKED: {ticker} - {rationale}")
            elif status == 'WARN':
                logger.info(f"Position WARNING: {ticker} - {rationale}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in position risk check for {ticker}: {e}")
            return {
                'status': 'WARN',
                'risk_score': 0.5,
                'flags': ['ERROR'],
                'max_allowed_weight': proposed_weight * 0.5,
                'recommended_weight': proposed_weight * 0.5,
                'rationale': f'Error in risk check: {e}'
            }
    
    def get_systemic_risk_signals(self, as_of_date: datetime) -> Dict[str, any]:
        """
        Get market-wide systemic risk signals from alternative data.
        
        The Risk Management System uses these to:
        1. Adjust overall portfolio risk exposure
        2. Trigger defensive positioning in stress periods
        3. Identify regime shifts requiring portfolio rebalancing
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            Dict with:
                - systemic_stress_level: 0-1 (higher = more stress)
                - economic_activity_regime: Regime classification
                - credit_market_stress: Credit market stress indicator
                - pledge_systemic_risk: Systemic pledge risk flag
                - smart_money_signal: Institutional flow signal
                - risk_regime: "NORMAL", "ELEVATED", or "CRISIS"
                - recommended_portfolio_adjustment: Suggested action
        """
        try:
            # Get market-level features
            market_features = self.feature_block.compute_market_level_features(as_of_date)
            
            if market_features.empty:
                logger.warning("No market features for systemic risk")
                return self._empty_systemic_risk()
            
            # Extract key indicators
            gst_regime = market_features['gst_regime_numeric'].iloc[0]
            credit_stress = market_features['credit_market_stress_flag'].iloc[0]
            pledge_systemic = market_features['pledge_systemic_risk'].iloc[0]
            bulk_signal = market_features['bulk_market_signal_numeric'].iloc[0]
            credit_momentum = market_features['credit_market_net_momentum'].iloc[0]
            
            # Compute systemic stress level
            stress_components = []
            
            # Economic contraction
            if gst_regime <= -1:
                stress_components.append(0.4)
            
            # Credit market stress
            if credit_stress > 0.5:
                stress_components.append(0.6)
            
            # Negative credit momentum
            if credit_momentum < -0.3:
                stress_components.append(0.3)
            
            # Systemic pledge risk
            if pledge_systemic > 0.5:
                stress_components.append(0.5)
            
            # Institutional distribution
            if bulk_signal <= -1:
                stress_components.append(0.4)
            
            # Aggregate stress level
            if stress_components:
                systemic_stress = float(np.mean(stress_components))
            else:
                systemic_stress = 0.0
            
            # Classify risk regime
            if systemic_stress > 0.7:
                risk_regime = "CRISIS"
                adjustment = "REDUCE_RISK_SIGNIFICANTLY"
            elif systemic_stress > 0.4:
                risk_regime = "ELEVATED"
                adjustment = "REDUCE_RISK_MODERATELY"
            else:
                risk_regime = "NORMAL"
                adjustment = "MAINTAIN_CURRENT_RISK"
            
            # Map economic regime
            if gst_regime >= 1:
                econ_regime = "EXPANSION"
            elif gst_regime <= -1:
                econ_regime = "CONTRACTION"
            else:
                econ_regime = "NEUTRAL"
            
            # Map smart money signal
            if bulk_signal >= 1:
                smart_money = "ACCUMULATION"
            elif bulk_signal <= -1:
                smart_money = "DISTRIBUTION"
            else:
                smart_money = "NEUTRAL"
            
            systemic_risk = {
                'systemic_stress_level': systemic_stress,
                'economic_activity_regime': econ_regime,
                'credit_market_stress': float(credit_stress),
                'pledge_systemic_risk': float(pledge_systemic),
                'smart_money_signal': smart_money,
                'risk_regime': risk_regime,
                'recommended_portfolio_adjustment': adjustment,
                'stress_components': stress_components,
                'as_of_date': as_of_date
            }
            
            logger.info(
                f"Systemic risk: {risk_regime} "
                f"(stress={systemic_stress:.2f}, regime={econ_regime})"
            )
            
            return systemic_risk
            
        except Exception as e:
            logger.error(f"Error computing systemic risk signals: {e}")
            return self._empty_systemic_risk()
    
    def _assess_portfolio_risk_level(
        self,
        distress_exposure: float,
        high_pledge_exposure: float,
        downgrade_exposure: float,
        smart_money_misalignment: float
    ) -> Tuple[str, List[str], List[str]]:
        """
        Assess overall portfolio risk level and generate warnings/recommendations.
        
        Returns:
            Tuple of (risk_level, warnings, recommendations)
        """
        warnings = []
        recommendations = []
        
        # Check distress exposure
        if distress_exposure > self.max_distress_exposure * 1.5:
            warnings.append(f"CRITICAL: Distress exposure {distress_exposure:.1%} exceeds limit")
            recommendations.append("URGENT: Reduce distressed positions immediately")
        elif distress_exposure > self.max_distress_exposure:
            warnings.append(f"HIGH: Distress exposure {distress_exposure:.1%} above target")
            recommendations.append("Reduce exposure to distressed companies")
        
        # Check pledge exposure
        if high_pledge_exposure > self.max_high_pledge_exposure * 1.5:
            warnings.append(f"CRITICAL: High-pledge exposure {high_pledge_exposure:.1%} exceeds limit")
            recommendations.append("URGENT: Reduce high-pledge positions")
        elif high_pledge_exposure > self.max_high_pledge_exposure:
            warnings.append(f"HIGH: High-pledge exposure {high_pledge_exposure:.1%} above target")
            recommendations.append("Reduce exposure to high-pledge companies")
        
        # Check downgrade exposure
        if downgrade_exposure > 0.25:
            warnings.append(f"Elevated downgrade risk: {downgrade_exposure:.1%} of portfolio")
            recommendations.append("Monitor credit-watch positions closely")
        
        # Check smart money misalignment
        if smart_money_misalignment > 0.30:
            warnings.append(f"High institutional selling in portfolio: {smart_money_misalignment:.1%}")
            recommendations.append("Review positions facing institutional distribution")
        
        # Determine overall risk level
        if len([w for w in warnings if 'CRITICAL' in w]) > 0:
            risk_level = "CRITICAL"
        elif len([w for w in warnings if 'HIGH' in w]) > 0:
            risk_level = "HIGH"
        elif len(warnings) > 0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return risk_level, warnings, recommendations
    
    def _check_portfolio_constraints(
        self,
        as_of_date: datetime,
        ticker: str,
        proposed_weight: float,
        current_positions: pd.DataFrame,
        ticker_features: pd.Series
    ) -> Dict[str, any]:
        """
        Check if adding this position would violate portfolio-level constraints.
        
        Returns:
            Dict with constraint_violated flag and details
        """
        # Calculate what portfolio would look like with new position
        tickers = current_positions['Ticker'].tolist() + [ticker]
        
        # Get features for all positions
        all_features = self.feature_block.compute_company_level_features(
            as_of_date,
            tickers
        )
        
        if all_features.empty:
            return {'constraint_violated': False, 'violated_constraints': [], 'reason': ''}
        
        # Calculate new exposures
        new_distress_exposure = 0.0
        new_pledge_exposure = 0.0
        
        for t in current_positions['Ticker']:
            if t in all_features.index:
                weight = current_positions[current_positions['Ticker'] == t]['Weight'].iloc[0]
                features = all_features.loc[t]
                
                if features.get('credit_in_distress', 0.0) > 0.5:
                    new_distress_exposure += weight
                if features.get('pledge_high_flag', 0.0) > 0.5:
                    new_pledge_exposure += weight
        
        # Add proposed position
        if ticker_features.get('credit_in_distress', 0.0) > 0.5:
            new_distress_exposure += proposed_weight
        if ticker_features.get('pledge_high_flag', 0.0) > 0.5:
            new_pledge_exposure += proposed_weight
        
        # Check constraints
        violated = []
        reason = ""
        
        if new_distress_exposure > self.max_distress_exposure:
            violated.append('MAX_DISTRESS_EXPOSURE')
            reason = f"Would exceed max distress exposure ({new_distress_exposure:.1%} > {self.max_distress_exposure:.1%})"
        
        if new_pledge_exposure > self.max_high_pledge_exposure:
            violated.append('MAX_PLEDGE_EXPOSURE')
            reason += f" Would exceed max pledge exposure ({new_pledge_exposure:.1%} > {self.max_high_pledge_exposure:.1%})"
        
        return {
            'constraint_violated': len(violated) > 0,
            'violated_constraints': violated,
            'reason': reason.strip()
        }
    
    def _empty_portfolio_risk(self) -> Dict[str, any]:
        """Return empty portfolio risk when data unavailable."""
        return {
            'distress_exposure': 0.0,
            'high_pledge_exposure': 0.0,
            'credit_downgrade_exposure': 0.0,
            'smart_money_alignment': 0.0,
            'risk_level': 'UNKNOWN',
            'warnings': ['NO_DATA'],
            'recommendations': ['Unable to assess alternative risk - data unavailable']
        }
    
    def _empty_systemic_risk(self) -> Dict[str, any]:
        """Return empty systemic risk when data unavailable."""
        return {
            'systemic_stress_level': 0.0,
            'economic_activity_regime': 'UNKNOWN',
            'credit_market_stress': 0.0,
            'pledge_systemic_risk': 0.0,
            'smart_money_signal': 'UNKNOWN',
            'risk_regime': 'UNKNOWN',
            'recommended_portfolio_adjustment': 'MAINTAIN_CURRENT_RISK',
            'stress_components': []
        }
