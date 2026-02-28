#!/usr/bin/env python3
"""
🏦 RISK BUDGET ENFORCER - INSTITUTIONAL VALIDATION LAYER 2
Sector-level risk limit enforcement with proportional scaling

This is the risk budget enforcement system for institutional validation.
It provides automatic sector risk limit enforcement with clear, testable rules.

Key Features:
- Default sector limits (Banks 10%, IT 8%, Metals 6%, Pharma 7%)
- Proportional position scaling when limits exceeded
- Sector risk utilization tracking
- Complete audit trail in risk_budget.parquet
- Integration with existing portfolio systems

Usage:
    from src.validation.risk_budget_enforcer import RiskBudgetEnforcer
    
    enforcer = RiskBudgetEnforcer()
    adjusted_portfolio = enforcer.enforce_risk_budget(portfolio)
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import warnings
warnings.filterwarnings('ignore')


@dataclass
class SectorRiskState:
    """Sector risk state data model"""
    date: datetime
    sector: str
    max_risk: float
    current_risk: float
    utilization: float  # current_risk / max_risk
    positions_count: int
    total_weight: float
    scale_factor: float  # Applied scaling factor
    enforcement_triggered: bool


@dataclass
class RiskBudgetState:
    """Overall risk budget state"""
    date: datetime
    total_sectors: int
    sectors_over_limit: int
    max_utilization: float
    avg_utilization: float
    enforcement_active: bool
    total_scaling_applied: float


class RiskBudgetEnforcer:
    """
    Risk Budget Enforcer - Institutional Validation Layer 2
    
    Enforces sector-level risk limits by scaling positions proportionally
    when sector exposure exceeds defined limits.
    
    Default Sector Limits:
    - Banks: 10%
    - IT: 8% 
    - Metals: 6%
    - Pharma: 7%
    - Others: 5% (default for unlisted sectors)
    
    Enforcement Logic:
    - If sector_risk > sector_limit: scale_factor = sector_limit / sector_risk
    - Apply scale_factor to all positions in that sector
    - Track utilization and log all enforcement actions
    """
    
    def __init__(self, 
                 sector_limits: Optional[Dict[str, float]] = None,
                 default_limit: float = 0.05):
        """
        Initialize risk budget enforcer with sector limits
        
        Args:
            sector_limits: Dictionary of sector -> limit (default uses institutional limits)
            default_limit: Default limit for sectors not explicitly defined (default 5%)
        """
        # Default institutional sector limits
        if sector_limits is None:
            sector_limits = {
                'Banks': 0.10,      # 10%
                'IT': 0.08,         # 8%
                'Metals': 0.06,     # 6%
                'Pharma': 0.07,     # 7%
                'Auto': 0.05,       # 5%
                'FMCG': 0.05,       # 5%
                'Energy': 0.05,     # 5%
                'Telecom': 0.04,    # 4%
                'Realty': 0.03,     # 3%
                'Media': 0.02       # 2%
            }
        
        self.sector_limits = sector_limits
        self.default_limit = default_limit
        
        # File paths
        self.risk_budget_file = 'data/risk/risk_budget.parquet'
        self.risk_budget_state_file = 'data/risk/risk_budget_state.parquet'
        
        # Ensure directory exists
        os.makedirs('data/risk', exist_ok=True)
    
    def get_sector_limit(self, sector: str) -> float:
        """
        Get risk limit for a sector
        
        Args:
            sector: Sector name
            
        Returns:
            Risk limit for the sector
        """
        return self.sector_limits.get(sector, self.default_limit)
    
    def calculate_sector_risks(self, portfolio: Dict[str, Dict]) -> Dict[str, float]:
        """
        Calculate current risk for each sector
        
        Args:
            portfolio: Dictionary of {ticker: {'weight': float, 'sector': str, ...}}
            
        Returns:
            Dictionary of {sector: total_risk}
        """
        sector_risks = {}
        
        for ticker, position in portfolio.items():
            if 'weight' not in position or 'sector' not in position:
                continue
            
            weight = abs(position['weight'])  # Use absolute weight for risk
            sector = position['sector']
            
            if sector not in sector_risks:
                sector_risks[sector] = 0.0
            
            sector_risks[sector] += weight
        
        return sector_risks
    
    def identify_violations(self, sector_risks: Dict[str, float]) -> Dict[str, Tuple[float, float, float]]:
        """
        Identify sectors that exceed their risk limits
        
        Args:
            sector_risks: Dictionary of {sector: current_risk}
            
        Returns:
            Dictionary of {sector: (current_risk, limit, scale_factor)} for violating sectors
        """
        violations = {}
        
        for sector, current_risk in sector_risks.items():
            limit = self.get_sector_limit(sector)
            
            if current_risk > limit:
                scale_factor = limit / current_risk
                violations[sector] = (current_risk, limit, scale_factor)
        
        return violations
    
    def apply_sector_scaling(self, 
                            portfolio: Dict[str, Dict], 
                            violations: Dict[str, Tuple[float, float, float]]) -> Dict[str, Dict]:
        """
        Apply proportional scaling to violating sectors
        
        Args:
            portfolio: Original portfolio
            violations: Dictionary of violating sectors with scale factors
            
        Returns:
            Adjusted portfolio with scaled positions
        """
        adjusted_portfolio = portfolio.copy()
        
        for ticker, position in adjusted_portfolio.items():
            if 'sector' not in position or 'weight' not in position:
                continue
            
            sector = position['sector']
            
            if sector in violations:
                _, _, scale_factor = violations[sector]
                
                # Scale the position weight
                original_weight = position['weight']
                scaled_weight = original_weight * scale_factor
                
                # Update position
                adjusted_portfolio[ticker] = position.copy()
                adjusted_portfolio[ticker]['weight'] = scaled_weight
                adjusted_portfolio[ticker]['original_weight'] = original_weight
                adjusted_portfolio[ticker]['scale_factor'] = scale_factor
                adjusted_portfolio[ticker]['risk_scaled'] = True
            else:
                # Mark as not scaled
                adjusted_portfolio[ticker] = position.copy()
                adjusted_portfolio[ticker]['risk_scaled'] = False
        
        return adjusted_portfolio
    
    def create_sector_risk_states(self, 
                                  portfolio: Dict[str, Dict], 
                                  sector_risks: Dict[str, float],
                                  violations: Dict[str, Tuple[float, float, float]],
                                  date: datetime) -> List[SectorRiskState]:
        """
        Create sector risk state records for logging
        
        Args:
            portfolio: Portfolio data
            sector_risks: Current sector risks
            violations: Violating sectors
            date: Current date
            
        Returns:
            List of SectorRiskState objects
        """
        sector_states = []
        
        # Get all sectors present in portfolio
        all_sectors = set()
        for position in portfolio.values():
            if 'sector' in position:
                all_sectors.add(position['sector'])
        
        for sector in all_sectors:
            current_risk = sector_risks.get(sector, 0.0)
            max_risk = self.get_sector_limit(sector)
            utilization = current_risk / max_risk if max_risk > 0 else 0.0
            
            # Count positions in sector
            positions_count = sum(1 for pos in portfolio.values() 
                                if pos.get('sector') == sector and pos.get('weight', 0) != 0)
            
            # Calculate total weight (sum of absolute weights)
            total_weight = sum(abs(pos.get('weight', 0)) for pos in portfolio.values() 
                             if pos.get('sector') == sector)
            
            # Check if enforcement was triggered
            enforcement_triggered = sector in violations
            scale_factor = violations[sector][2] if enforcement_triggered else 1.0
            
            sector_state = SectorRiskState(
                date=date,
                sector=sector,
                max_risk=max_risk,
                current_risk=current_risk,
                utilization=utilization,
                positions_count=positions_count,
                total_weight=total_weight,
                scale_factor=scale_factor,
                enforcement_triggered=enforcement_triggered
            )
            
            sector_states.append(sector_state)
        
        return sector_states
    
    def create_risk_budget_state(self, 
                                sector_states: List[SectorRiskState],
                                date: datetime) -> RiskBudgetState:
        """
        Create overall risk budget state
        
        Args:
            sector_states: List of sector risk states
            date: Current date
            
        Returns:
            RiskBudgetState object
        """
        if not sector_states:
            return RiskBudgetState(
                date=date,
                total_sectors=0,
                sectors_over_limit=0,
                max_utilization=0.0,
                avg_utilization=0.0,
                enforcement_active=False,
                total_scaling_applied=0.0
            )
        
        total_sectors = len(sector_states)
        sectors_over_limit = sum(1 for s in sector_states if s.enforcement_triggered)
        max_utilization = max(s.utilization for s in sector_states)
        avg_utilization = np.mean([s.utilization for s in sector_states])
        enforcement_active = sectors_over_limit > 0
        
        # Calculate total scaling applied (weighted by sector size)
        total_weight = sum(s.total_weight for s in sector_states)
        if total_weight > 0:
            total_scaling_applied = sum(
                s.total_weight * (1.0 - s.scale_factor) for s in sector_states
            ) / total_weight
        else:
            total_scaling_applied = 0.0
        
        return RiskBudgetState(
            date=date,
            total_sectors=total_sectors,
            sectors_over_limit=sectors_over_limit,
            max_utilization=max_utilization,
            avg_utilization=avg_utilization,
            enforcement_active=enforcement_active,
            total_scaling_applied=total_scaling_applied
        )
    
    def log_risk_budget_state(self, 
                             sector_states: List[SectorRiskState],
                             budget_state: RiskBudgetState) -> None:
        """
        Log risk budget state to parquet files
        
        Args:
            sector_states: List of sector risk states
            budget_state: Overall risk budget state
        """
        # Log sector states
        if sector_states:
            sector_df = pd.DataFrame([asdict(s) for s in sector_states])
            
            if os.path.exists(self.risk_budget_file):
                existing_df = pd.read_parquet(self.risk_budget_file)
                sector_df = pd.concat([existing_df, sector_df], ignore_index=True)
            
            sector_df.to_parquet(self.risk_budget_file, index=False)
        
        # Log overall state
        budget_df = pd.DataFrame([asdict(budget_state)])
        
        if os.path.exists(self.risk_budget_state_file):
            existing_df = pd.read_parquet(self.risk_budget_state_file)
            budget_df = pd.concat([existing_df, budget_df], ignore_index=True)
        
        budget_df.to_parquet(self.risk_budget_state_file, index=False)
    
    def enforce_risk_budget(self, 
                           portfolio: Dict[str, Dict],
                           date: Optional[datetime] = None) -> Tuple[Dict[str, Dict], RiskBudgetState]:
        """
        Main method: Enforce sector risk budget limits
        
        Args:
            portfolio: Dictionary of {ticker: {'weight': float, 'sector': str, ...}}
            date: Date for logging (default: now)
            
        Returns:
            Tuple of (adjusted_portfolio, risk_budget_state)
        """
        if date is None:
            date = datetime.now()
        
        print("🏦 RISK BUDGET ENFORCER - INSTITUTIONAL VALIDATION")
        print("=" * 60)
        
        # Calculate current sector risks
        sector_risks = self.calculate_sector_risks(portfolio)
        
        print(f"📊 Portfolio Analysis:")
        print(f"   Total positions: {len(portfolio)}")
        print(f"   Sectors present: {len(sector_risks)}")
        
        # Identify violations
        violations = self.identify_violations(sector_risks)
        
        if violations:
            print(f"\n🚨 SECTOR LIMIT VIOLATIONS DETECTED:")
            for sector, (current, limit, scale) in violations.items():
                print(f"   {sector}: {current:.1%} > {limit:.1%} (scale to {scale:.3f})")
        else:
            print(f"\n✅ ALL SECTOR LIMITS RESPECTED")
        
        # Apply scaling
        adjusted_portfolio = self.apply_sector_scaling(portfolio, violations)
        
        # Create state records
        sector_states = self.create_sector_risk_states(
            adjusted_portfolio, sector_risks, violations, date
        )
        budget_state = self.create_risk_budget_state(sector_states, date)
        
        # Log states
        self.log_risk_budget_state(sector_states, budget_state)
        
        # Print results
        print(f"\n📈 RISK BUDGET STATE:")
        print(f"   Total sectors: {budget_state.total_sectors}")
        print(f"   Sectors over limit: {budget_state.sectors_over_limit}")
        print(f"   Max utilization: {budget_state.max_utilization:.1%}")
        print(f"   Avg utilization: {budget_state.avg_utilization:.1%}")
        print(f"   Enforcement active: {budget_state.enforcement_active}")
        print(f"   Total scaling applied: {budget_state.total_scaling_applied:.2%}")
        
        print(f"\n💾 Risk budget logged to: {self.risk_budget_file}")
        
        return adjusted_portfolio, budget_state


def main():
    """Main execution function for testing"""
    # Create sample portfolio for testing
    sample_portfolio = {
        'HDFCBANK': {'weight': 0.08, 'sector': 'Banks'},
        'ICICIBANK': {'weight': 0.06, 'sector': 'Banks'},
        'SBIN': {'weight': 0.04, 'sector': 'Banks'},  # Total Banks: 18% > 10% limit
        'TCS': {'weight': 0.05, 'sector': 'IT'},
        'INFY': {'weight': 0.04, 'sector': 'IT'},     # Total IT: 9% > 8% limit
        'TATASTEEL': {'weight': 0.04, 'sector': 'Metals'},
        'HINDALCO': {'weight': 0.03, 'sector': 'Metals'},  # Total Metals: 7% > 6% limit
        'SUNPHARMA': {'weight': 0.03, 'sector': 'Pharma'},
        'DRREDDY': {'weight': 0.02, 'sector': 'Pharma'},   # Total Pharma: 5% < 7% limit
    }
    
    enforcer = RiskBudgetEnforcer()
    adjusted_portfolio, budget_state = enforcer.enforce_risk_budget(sample_portfolio)
    
    return adjusted_portfolio, budget_state


if __name__ == "__main__":
    main()