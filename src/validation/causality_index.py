#!/usr/bin/env python3
"""
🔗 CAUSALITY INDEX - LAYER 4: LIVE REALITY
Human-readable explanations of allocation changes for institutional validation

This implements the causality index requirements for Layer 4 (Live Reality) of the
institutional validation framework. It provides clear, one-line explanations of
what drove portfolio allocation changes for investor transparency.

CRITICAL PRINCIPLE: Human-Readable Causality
- Identify top 3 drivers of allocation changes each month
- Generate human-readable descriptions (e.g., "Liquidity beta ↑ in banks")
- Rank by magnitude of impact on allocation
- Provide complete causal chain from macro change to allocation change

Usage:
    from src.validation.causality_index import CausalityIndex
    
    causality = CausalityIndex()
    index = causality.generate_monthly_causality_index(
        current_positions, previous_positions, market_conditions
    )
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import warnings

warnings.filterwarnings('ignore')


@dataclass
class CausalityDriver:
    """
    Individual causality driver
    
    Represents one factor that drove allocation changes.
    """
    rank: int  # 1, 2, or 3 (top 3 drivers)
    driver_description: str  # Human-readable description
    impact_magnitude: float  # Magnitude of impact on allocation (0.0 to 1.0)
    affected_sectors: List[str]  # Sectors affected by this driver
    macro_factor: str  # Underlying macro factor
    direction: str  # "increase" or "decrease"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate driver data"""
        errors = []
        
        if not (1 <= self.rank <= 3):
            errors.append(f"Rank {self.rank} outside bounds [1, 3]")
        
        if not (0.0 <= self.impact_magnitude <= 1.0):
            errors.append(f"Impact magnitude {self.impact_magnitude} outside bounds [0.0, 1.0]")
        
        if self.direction not in ['increase', 'decrease']:
            errors.append(f"Invalid direction: {self.direction}")
        
        if not isinstance(self.affected_sectors, list):
            errors.append("Affected sectors must be a list")
        
        return errors


@dataclass
class MonthlyCausalityIndex:
    """
    Monthly causality index
    
    Complete causality explanation for one month's allocation changes.
    """
    date: datetime
    total_allocation_change: float  # Total magnitude of allocation changes
    top_drivers: List[CausalityDriver]  # Top 3 drivers
    regime_context: str  # Market regime context
    summary_explanation: str  # One-line summary
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['top_drivers'] = [driver.to_dict() for driver in self.top_drivers]
        return result
    
    def validate(self) -> List[str]:
        """Validate causality index"""
        errors = []
        
        if len(self.top_drivers) > 3:
            errors.append(f"Too many drivers: {len(self.top_drivers)} (max 3)")
        
        if self.total_allocation_change < 0.0:
            errors.append(f"Total allocation change {self.total_allocation_change} is negative")
        
        # Validate each driver
        for driver in self.top_drivers:
            driver_errors = driver.validate()
            errors.extend([f"Driver {driver.rank}: {error}" for error in driver_errors])
        
        return errors


class CausalityIndex:
    """
    Causality Index - Layer 4: Live Reality
    
    Generates human-readable explanations of allocation changes for
    institutional transparency and investor communication.
    
    ENFORCES REQUIREMENTS:
    - 24.1-24.8: Causality index for human readability
    
    V3 INTEGRATION:
    - Uses UnifiedState for data access (Requirement 14.1)
    - Emits events through EventBus (Requirement 14.2)
    """
    
    def __init__(self,
                 output_dir: str = "data/intelligence",
                 unified_state=None,
                 event_bus=None):
        """
        Initialize Causality Index
        
        Args:
            output_dir: Directory for output files
            unified_state: Optional UnifiedState instance for V3 integration
            event_bus: Optional EventBus instance for V3 integration
        """
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # V3 Integration (optional)
        self.unified_state = unified_state
        self.event_bus = event_bus
        
        # Causality templates for human-readable descriptions
        self.causality_templates = {
            'volatility': {
                'increase': "Market volatility ↑ → {direction} {strategy} exposure in {sectors}",
                'decrease': "Market volatility ↓ → {direction} {strategy} exposure in {sectors}"
            },
            'liquidity': {
                'increase': "Liquidity stress ↑ → {direction} exposure in {sectors}",
                'decrease': "Liquidity conditions ↑ → {direction} exposure in {sectors}"
            },
            'interest_rate': {
                'increase': "Interest rates ↑ → {direction} rate-sensitive {sectors}",
                'decrease': "Interest rates ↓ → {direction} rate-sensitive {sectors}"
            },
            'regime_shift': {
                'increase': "Regime shift to {regime} → {direction} {strategy} allocation",
                'decrease': "Regime shift from {regime} → {direction} {strategy} allocation"
            },
            'momentum': {
                'increase': "Momentum signals ↑ → {direction} momentum exposure in {sectors}",
                'decrease': "Momentum signals ↓ → {direction} momentum exposure in {sectors}"
            },
            'value': {
                'increase': "Value opportunities ↑ → {direction} value exposure in {sectors}",
                'decrease': "Value signals ↓ → {direction} value exposure in {sectors}"
            },
            'quality': {
                'increase': "Quality premium ↑ → {direction} quality exposure in {sectors}",
                'decrease': "Quality signals ↓ → {direction} quality exposure in {sectors}"
            },
            'risk_management': {
                'increase': "Risk controls activated → {direction} overall exposure",
                'decrease': "Risk conditions normalized → {direction} overall exposure"
            }
        }
        
        print("🔗 Causality Index initialized")
        print(f"   Output: {output_dir}/")
        if unified_state:
            print("   ✅ V3 Integration: UnifiedState connected")
        if event_bus:
            print("   ✅ V3 Integration: EventBus connected")
    
    def generate_monthly_causality_index(self,
                                        date: datetime,
                                        current_positions: Dict[str, Dict[str, Any]],
                                        previous_positions: Dict[str, Dict[str, Any]],
                                        market_conditions: Dict[str, float],
                                        regime_info: Optional[Dict[str, Any]] = None) -> MonthlyCausalityIndex:
        """
        Generate monthly causality index
        
        ENFORCES REQUIREMENTS 24.1-24.8: Causality Index for Human Readability
        
        Args:
            date: Month-end date
            current_positions: Current portfolio positions
            previous_positions: Previous month's positions
            market_conditions: Market conditions and changes
            regime_info: Optional regime information
            
        Returns:
            MonthlyCausalityIndex with top 3 drivers
        """
        
        print(f"🔗 Generating causality index for {date.strftime('%Y-%m')}")
        
        # 1. Calculate allocation changes
        allocation_changes = self._calculate_allocation_changes(current_positions, previous_positions)
        
        # 2. Identify potential drivers
        potential_drivers = self._identify_potential_drivers(
            allocation_changes, market_conditions, regime_info
        )
        
        # 3. Rank drivers by impact magnitude
        top_drivers = self._rank_drivers_by_impact(potential_drivers, allocation_changes)
        
        # 4. Generate human-readable descriptions
        causality_drivers = self._generate_driver_descriptions(top_drivers, market_conditions, regime_info)
        
        # 5. Create summary explanation
        summary_explanation = self._generate_summary_explanation(causality_drivers, allocation_changes)
        
        # 6. Create causality index
        causality_index = MonthlyCausalityIndex(
            date=date,
            total_allocation_change=sum(abs(change) for change in allocation_changes.values()),
            top_drivers=causality_drivers[:3],  # Top 3 only
            regime_context=regime_info.get('regime', 'unknown') if regime_info else 'unknown',
            summary_explanation=summary_explanation
        )
        
        # Validate
        validation_errors = causality_index.validate()
        if validation_errors:
            print(f"⚠️ Causality index validation warnings:")
            for error in validation_errors[:3]:  # Show first 3 errors
                print(f"   {error}")
        
        # Persist causality index
        self._persist_causality_index(causality_index)
        
        # V3 Integration: Store in UnifiedState
        self._store_in_unified_state(causality_index)
        
        # V3 Integration: Emit event
        self._emit_causality_event(causality_index)
        
        print(f"✅ Generated causality index: {len(causality_drivers)} drivers identified")
        
        return causality_index
    
    def _calculate_allocation_changes(self,
                                    current_positions: Dict[str, Dict[str, Any]],
                                    previous_positions: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """Calculate allocation changes between periods"""
        
        allocation_changes = {}
        
        # Get all tickers
        all_tickers = set(current_positions.keys()) | set(previous_positions.keys())
        
        for ticker in all_tickers:
            current_weight = current_positions.get(ticker, {}).get('weight', 0.0)
            previous_weight = previous_positions.get(ticker, {}).get('weight', 0.0)
            
            change = current_weight - previous_weight
            
            if abs(change) > 0.001:  # Only track meaningful changes (>0.1%)
                allocation_changes[ticker] = change
        
        return allocation_changes
    
    def _identify_potential_drivers(self,
                                  allocation_changes: Dict[str, float],
                                  market_conditions: Dict[str, float],
                                  regime_info: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify potential drivers of allocation changes"""
        
        potential_drivers = []
        
        # 1. Market volatility driver
        volatility_change = market_conditions.get('volatility_change', 0.0)
        if abs(volatility_change) > 0.02:  # >2% volatility change
            potential_drivers.append({
                'type': 'volatility',
                'magnitude': abs(volatility_change),
                'direction': 'increase' if volatility_change > 0 else 'decrease',
                'affected_changes': self._get_volatility_affected_changes(allocation_changes),
                'macro_factor': 'market_volatility'
            })
        
        # 2. Liquidity stress driver
        liquidity_change = market_conditions.get('liquidity_change', 0.0)
        if abs(liquidity_change) > 0.1:  # >10% liquidity change
            potential_drivers.append({
                'type': 'liquidity',
                'magnitude': abs(liquidity_change),
                'direction': 'increase' if liquidity_change < 0 else 'decrease',  # Inverted: less liquidity = more stress
                'affected_changes': self._get_liquidity_affected_changes(allocation_changes),
                'macro_factor': 'liquidity_conditions'
            })
        
        # 3. Interest rate driver
        rate_change = market_conditions.get('interest_rate_change', 0.0)
        if abs(rate_change) > 0.005:  # >0.5% rate change
            potential_drivers.append({
                'type': 'interest_rate',
                'magnitude': abs(rate_change) * 100,  # Convert to percentage
                'direction': 'increase' if rate_change > 0 else 'decrease',
                'affected_changes': self._get_rate_affected_changes(allocation_changes),
                'macro_factor': 'interest_rates'
            })
        
        # 4. Regime shift driver
        if regime_info and regime_info.get('regime_changed', False):
            potential_drivers.append({
                'type': 'regime_shift',
                'magnitude': 0.5,  # Fixed magnitude for regime shifts
                'direction': 'increase',  # Always considered an increase in regime-appropriate allocation
                'affected_changes': allocation_changes,  # All changes potentially regime-driven
                'macro_factor': 'market_regime',
                'regime': regime_info.get('new_regime', 'unknown')
            })
        
        # 5. Strategy-specific drivers
        strategy_drivers = self._identify_strategy_drivers(allocation_changes, market_conditions)
        potential_drivers.extend(strategy_drivers)
        
        # 6. Risk management driver
        risk_driver = self._identify_risk_management_driver(allocation_changes, market_conditions)
        if risk_driver:
            potential_drivers.append(risk_driver)
        
        return potential_drivers
    
    def _get_volatility_affected_changes(self, allocation_changes: Dict[str, float]) -> Dict[str, float]:
        """Get allocation changes affected by volatility"""
        
        # Assume all changes are potentially volatility-affected
        # In a real system, this would use sector/strategy mappings
        return allocation_changes
    
    def _get_liquidity_affected_changes(self, allocation_changes: Dict[str, float]) -> Dict[str, float]:
        """Get allocation changes affected by liquidity"""
        
        # Focus on larger positions that are more liquidity-sensitive
        return {ticker: change for ticker, change in allocation_changes.items() 
                if abs(change) > 0.02}  # >2% changes
    
    def _get_rate_affected_changes(self, allocation_changes: Dict[str, float]) -> Dict[str, float]:
        """Get allocation changes affected by interest rates"""
        
        # In a real system, this would identify rate-sensitive sectors (banks, REITs, etc.)
        # For now, assume all changes are potentially rate-affected
        return allocation_changes
    
    def _identify_strategy_drivers(self,
                                 allocation_changes: Dict[str, float],
                                 market_conditions: Dict[str, float]) -> List[Dict[str, Any]]:
        """Identify strategy-specific drivers"""
        
        strategy_drivers = []
        
        # Momentum driver
        momentum_signal = market_conditions.get('momentum_strength', 0.0)
        if abs(momentum_signal) > 0.1:
            strategy_drivers.append({
                'type': 'momentum',
                'magnitude': abs(momentum_signal),
                'direction': 'increase' if momentum_signal > 0 else 'decrease',
                'affected_changes': self._get_momentum_affected_changes(allocation_changes),
                'macro_factor': 'momentum_signals'
            })
        
        # Value driver
        value_signal = market_conditions.get('value_opportunity', 0.0)
        if abs(value_signal) > 0.1:
            strategy_drivers.append({
                'type': 'value',
                'magnitude': abs(value_signal),
                'direction': 'increase' if value_signal > 0 else 'decrease',
                'affected_changes': self._get_value_affected_changes(allocation_changes),
                'macro_factor': 'value_signals'
            })
        
        # Quality driver
        quality_signal = market_conditions.get('quality_premium', 0.0)
        if abs(quality_signal) > 0.1:
            strategy_drivers.append({
                'type': 'quality',
                'magnitude': abs(quality_signal),
                'direction': 'increase' if quality_signal > 0 else 'decrease',
                'affected_changes': self._get_quality_affected_changes(allocation_changes),
                'macro_factor': 'quality_signals'
            })
        
        return strategy_drivers
    
    def _get_momentum_affected_changes(self, allocation_changes: Dict[str, float]) -> Dict[str, float]:
        """Get changes affected by momentum signals"""
        
        # In a real system, this would identify momentum-strategy positions
        # For now, assume positions with larger increases are momentum-driven
        return {ticker: change for ticker, change in allocation_changes.items() 
                if change > 0.01}  # Increases >1%
    
    def _get_value_affected_changes(self, allocation_changes: Dict[str, float]) -> Dict[str, float]:
        """Get changes affected by value signals"""
        
        # In a real system, this would identify value-strategy positions
        return {ticker: change for ticker, change in allocation_changes.items() 
                if abs(change) > 0.005}  # Any meaningful change
    
    def _get_quality_affected_changes(self, allocation_changes: Dict[str, float]) -> Dict[str, float]:
        """Get changes affected by quality signals"""
        
        # In a real system, this would identify quality-strategy positions
        return {ticker: change for ticker, change in allocation_changes.items() 
                if change > 0}  # Any increases
    
    def _identify_risk_management_driver(self,
                                       allocation_changes: Dict[str, float],
                                       market_conditions: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Identify risk management driver"""
        
        # Check if overall exposure decreased significantly
        total_change = sum(allocation_changes.values())
        
        if total_change < -0.05:  # >5% decrease in total exposure
            return {
                'type': 'risk_management',
                'magnitude': abs(total_change),
                'direction': 'decrease',
                'affected_changes': {ticker: change for ticker, change in allocation_changes.items() 
                                   if change < 0},  # All decreases
                'macro_factor': 'risk_controls'
            }
        
        return None
    
    def _rank_drivers_by_impact(self,
                               potential_drivers: List[Dict[str, Any]],
                               allocation_changes: Dict[str, float]) -> List[Dict[str, Any]]:
        """Rank drivers by their impact magnitude"""
        
        # Calculate impact score for each driver
        for driver in potential_drivers:
            affected_changes = driver['affected_changes']
            
            # Impact score = magnitude * sum of affected allocation changes
            total_affected_change = sum(abs(change) for change in affected_changes.values())
            impact_score = driver['magnitude'] * total_affected_change
            
            driver['impact_score'] = impact_score
        
        # Sort by impact score (descending)
        ranked_drivers = sorted(potential_drivers, key=lambda x: x['impact_score'], reverse=True)
        
        return ranked_drivers
    
    def _generate_driver_descriptions(self,
                                    top_drivers: List[Dict[str, Any]],
                                    market_conditions: Dict[str, float],
                                    regime_info: Optional[Dict[str, Any]]) -> List[CausalityDriver]:
        """Generate human-readable descriptions for drivers"""
        
        causality_drivers = []
        
        for rank, driver in enumerate(top_drivers[:3], 1):  # Top 3 only
            # Get affected sectors (simplified)
            affected_sectors = self._get_affected_sectors(driver['affected_changes'])
            
            # Generate description using templates
            description = self._generate_driver_description(driver, affected_sectors, regime_info)
            
            # Create CausalityDriver object
            causality_driver = CausalityDriver(
                rank=rank,
                driver_description=description,
                impact_magnitude=min(1.0, driver['impact_score']),  # Cap at 1.0
                affected_sectors=affected_sectors,
                macro_factor=driver['macro_factor'],
                direction=driver['direction']
            )
            
            causality_drivers.append(causality_driver)
        
        return causality_drivers
    
    def _get_affected_sectors(self, affected_changes: Dict[str, float]) -> List[str]:
        """Get sectors affected by changes (simplified)"""
        
        # In a real system, this would map tickers to sectors
        # For now, generate mock sectors based on ticker patterns
        sectors = set()
        
        for ticker in affected_changes.keys():
            if 'BANK' in ticker or ticker.startswith('HDFC') or ticker.startswith('ICICI'):
                sectors.add('Banks')
            elif 'IT' in ticker or ticker.startswith('TCS') or ticker.startswith('INFY'):
                sectors.add('IT')
            elif 'PHARMA' in ticker or 'HEALTH' in ticker:
                sectors.add('Pharma')
            elif 'METAL' in ticker or 'STEEL' in ticker:
                sectors.add('Metals')
            elif 'AUTO' in ticker:
                sectors.add('Auto')
            else:
                # Extract strategy from ticker (our mock tickers are like "MOMENTUM1", "VALUE2")
                if ticker.startswith('MOMENTUM'):
                    sectors.add('Momentum')
                elif ticker.startswith('VALUE'):
                    sectors.add('Value')
                elif ticker.startswith('QUALITY'):
                    sectors.add('Quality')
                elif ticker.startswith('LOW_VOL'):
                    sectors.add('Low Vol')
                else:
                    sectors.add('Diversified')
        
        return list(sectors)[:3]  # Limit to 3 sectors for readability
    
    def _generate_driver_description(self,
                                   driver: Dict[str, Any],
                                   affected_sectors: List[str],
                                   regime_info: Optional[Dict[str, Any]]) -> str:
        """Generate human-readable description for a driver"""
        
        driver_type = driver['type']
        direction = driver['direction']
        
        # Get template
        if driver_type in self.causality_templates:
            template = self.causality_templates[driver_type][direction]
        else:
            # Fallback template
            template = f"{driver_type.replace('_', ' ').title()} {direction} → affected {', '.join(affected_sectors)}"
        
        # Format template
        try:
            # Determine allocation direction
            allocation_direction = "increased" if direction == "increase" else "reduced"
            
            # Format sectors
            sectors_str = ", ".join(affected_sectors) if affected_sectors else "portfolio"
            
            # Special handling for regime shifts
            if driver_type == 'regime_shift' and regime_info:
                regime = regime_info.get('new_regime', 'unknown')
                description = template.format(
                    regime=regime,
                    direction=allocation_direction,
                    strategy=driver_type,
                    sectors=sectors_str
                )
            else:
                description = template.format(
                    direction=allocation_direction,
                    strategy=driver_type,
                    sectors=sectors_str
                )
            
        except KeyError:
            # Fallback if template formatting fails
            description = f"{driver_type.replace('_', ' ').title()} {direction} → {allocation_direction} exposure in {sectors_str}"
        
        return description
    
    def _generate_summary_explanation(self,
                                    causality_drivers: List[CausalityDriver],
                                    allocation_changes: Dict[str, float]) -> str:
        """Generate one-line summary explanation"""
        
        if not causality_drivers:
            return "No significant allocation changes detected"
        
        # Get top driver
        top_driver = causality_drivers[0]
        
        # Calculate total allocation change magnitude
        total_change = sum(abs(change) for change in allocation_changes.values())
        
        # Generate summary
        if total_change > 0.1:  # >10% total change
            summary = f"Major reallocation driven by {top_driver.driver_description.lower()}"
        elif total_change > 0.05:  # >5% total change
            summary = f"Moderate reallocation due to {top_driver.driver_description.lower()}"
        else:
            summary = f"Minor adjustments from {top_driver.driver_description.lower()}"
        
        return summary
    
    def _persist_causality_index(self, causality_index: MonthlyCausalityIndex):
        """Persist causality index to file"""
        
        # Create filename
        date_str = causality_index.date.strftime("%Y%m")
        filename = f"causality_index_{date_str}.json"
        file_path = os.path.join(self.output_dir, filename)
        
        # Convert to dictionary and save
        causality_dict = causality_index.to_dict()
        causality_dict['date'] = causality_dict['date'].isoformat()
        
        with open(file_path, 'w') as f:
            json.dump(causality_dict, f, indent=2, default=str)
        
        print(f"✅ Persisted causality index: {file_path}")
    
    def load_causality_index(self, date: datetime) -> Optional[MonthlyCausalityIndex]:
        """Load causality index from file"""
        
        date_str = date.strftime("%Y%m")
        filename = f"causality_index_{date_str}.json"
        file_path = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Convert back to objects
            data['date'] = datetime.fromisoformat(data['date'])
            
            # Convert drivers
            drivers = []
            for driver_data in data['top_drivers']:
                driver = CausalityDriver(**driver_data)
                drivers.append(driver)
            
            data['top_drivers'] = drivers
            
            return MonthlyCausalityIndex(**data)
            
        except Exception as e:
            print(f"❌ Failed to load causality index: {e}")
            return None
    
    def get_causality_summary(self, 
                             start_date: datetime, 
                             end_date: datetime) -> Dict[str, Any]:
        """Get causality summary for date range"""
        
        summary = {
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'months_analyzed': 0,
            'top_macro_factors': {},
            'most_affected_sectors': {},
            'common_drivers': {},
            'average_allocation_change': 0.0
        }
        
        current_date = start_date.replace(day=28)  # Use month-end approximation
        total_allocation_change = 0.0
        
        while current_date <= end_date:
            causality_index = self.load_causality_index(current_date)
            
            if causality_index:
                summary['months_analyzed'] += 1
                total_allocation_change += causality_index.total_allocation_change
                
                # Track macro factors
                for driver in causality_index.top_drivers:
                    factor = driver.macro_factor
                    summary['top_macro_factors'][factor] = summary['top_macro_factors'].get(factor, 0) + 1
                    
                    # Track affected sectors
                    for sector in driver.affected_sectors:
                        summary['most_affected_sectors'][sector] = summary['most_affected_sectors'].get(sector, 0) + 1
                    
                    # Track driver types
                    driver_type = driver.driver_description.split('→')[0].strip()
                    summary['common_drivers'][driver_type] = summary['common_drivers'].get(driver_type, 0) + 1
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Calculate averages
        if summary['months_analyzed'] > 0:
            summary['average_allocation_change'] = total_allocation_change / summary['months_analyzed']
        
        return summary
    
    # ========================================================================
    # V3 INTEGRATION METHODS
    # ========================================================================
    
    def _store_in_unified_state(self, causality_index: MonthlyCausalityIndex):
        """Store causality index in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "causality_index"
            
            # Store latest causality index
            self.unified_state.set(
                component=component_name,
                key="latest_causality_index",
                value={
                    "date": causality_index.date.isoformat(),
                    "summary": causality_index.summary_explanation,
                    "top_driver": causality_index.top_drivers[0].driver_description if causality_index.top_drivers else "No drivers",
                    "total_change": causality_index.total_allocation_change
                }
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store causality index in UnifiedState: {e}")
    
    def _emit_causality_event(self, causality_index: MonthlyCausalityIndex):
        """Emit causality index event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            self.event_bus.emit(
                event_type="CAUSALITY_INDEX_GENERATED",
                source="causality_index",
                data={
                    "date": causality_index.date.isoformat(),
                    "summary": causality_index.summary_explanation,
                    "drivers_count": len(causality_index.top_drivers),
                    "total_allocation_change": causality_index.total_allocation_change,
                    "regime_context": causality_index.regime_context
                },
                tags=["causality", "allocation", "explanation"],
                priority="INFO"
            )
            
        except Exception as e:
            print(f"⚠️ Failed to emit causality event: {e}")


def main():
    """Demonstrate Causality Index"""
    
    print("🔗 CAUSALITY INDEX - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize causality index
    causality = CausalityIndex(output_dir="data/test_causality")
    
    # Mock current positions
    current_positions = {
        'MOMENTUM1': {'weight': 0.08, 'strategy': 'momentum'},
        'MOMENTUM2': {'weight': 0.06, 'strategy': 'momentum'},
        'VALUE1': {'weight': 0.12, 'strategy': 'value'},
        'VALUE2': {'weight': 0.10, 'strategy': 'value'},
        'QUALITY1': {'weight': 0.07, 'strategy': 'quality'},
        'LOW_VOL1': {'weight': 0.15, 'strategy': 'low_vol'}
    }
    
    # Mock previous positions (with some changes)
    previous_positions = {
        'MOMENTUM1': {'weight': 0.12, 'strategy': 'momentum'},  # Decreased
        'MOMENTUM2': {'weight': 0.10, 'strategy': 'momentum'},  # Decreased
        'VALUE1': {'weight': 0.08, 'strategy': 'value'},       # Increased
        'VALUE2': {'weight': 0.06, 'strategy': 'value'},       # Increased
        'QUALITY1': {'weight': 0.07, 'strategy': 'quality'},   # No change
        'LOW_VOL1': {'weight': 0.10, 'strategy': 'low_vol'}    # Increased
    }
    
    # Mock market conditions
    market_conditions = {
        'volatility_change': 0.05,      # 5% increase in volatility
        'liquidity_change': -0.15,      # 15% decrease in liquidity
        'interest_rate_change': 0.01,   # 1% increase in rates
        'momentum_strength': -0.2,      # Momentum weakening
        'value_opportunity': 0.3,       # Value opportunities increasing
        'quality_premium': 0.0,         # No change in quality
    }
    
    # Mock regime info
    regime_info = {
        'regime': 'late-expansion',
        'regime_changed': True,
        'new_regime': 'late-expansion',
        'previous_regime': 'expansion'
    }
    
    # Generate causality index
    causality_index = causality.generate_monthly_causality_index(
        date=datetime(2024, 1, 31),
        current_positions=current_positions,
        previous_positions=previous_positions,
        market_conditions=market_conditions,
        regime_info=regime_info
    )
    
    # Display results
    print(f"\n📊 CAUSALITY INDEX RESULTS")
    print("=" * 60)
    
    print(f"Date: {causality_index.date.strftime('%Y-%m')}")
    print(f"Total Allocation Change: {causality_index.total_allocation_change:.2%}")
    print(f"Regime Context: {causality_index.regime_context}")
    print(f"Summary: {causality_index.summary_explanation}")
    
    print(f"\n🔗 TOP DRIVERS")
    print("=" * 60)
    
    for driver in causality_index.top_drivers:
        print(f"{driver.rank}. {driver.driver_description}")
        print(f"   Impact: {driver.impact_magnitude:.2%}")
        print(f"   Sectors: {', '.join(driver.affected_sectors)}")
        print(f"   Factor: {driver.macro_factor}")
        print()
    
    # Test loading
    loaded_index = causality.load_causality_index(datetime(2024, 1, 31))
    if loaded_index:
        print(f"✅ Successfully loaded causality index")
        print(f"   Loaded summary: {loaded_index.summary_explanation}")
    
    print("\n✅ Causality Index demonstration complete")


if __name__ == "__main__":
    main()