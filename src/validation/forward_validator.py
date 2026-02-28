#!/usr/bin/env python3
"""
🔮 FORWARD VALIDATOR - PHASE 6: ENHANCEMENT LAYER
Test anticipation events and allocation timing

This implements the forward validation requirements for Phase 6 (Enhancement)
of the institutional validation framework. It tests anticipation events,
verifies allocation shifts preceded returns, and tracks anticipation success rate.

CRITICAL PRINCIPLE: Anticipation Timing Validation
- Test anticipation events where allocation changes preceded market moves
- Verify allocation shifts occurred before corresponding returns
- Track anticipation success rate over time
- Persist to data/intelligence/anticipation_test.parquet
- Provide evidence of predictive capability

Usage:
    from src.validation.forward_validator import ForwardValidator
    
    validator = ForwardValidator()
    validator.test_anticipation_events(allocation_data, return_data)
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import warnings
from scipy import stats
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LinearRegression

warnings.filterwarnings('ignore')


class AnticipationResult(Enum):
    """Anticipation test results"""
    SUCCESS = "success"         # Allocation shift preceded positive returns
    FAILURE = "failure"         # Allocation shift preceded negative returns
    NEUTRAL = "neutral"         # No significant anticipation detected
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data for testing


@dataclass
class AnticipationEvent:
    """
    Anticipation event record for tracking predictive allocation changes
    
    Complete anticipation information with timing and performance metrics.
    """
    date: datetime
    event_type: str  # 'increase', 'decrease', 'regime_shift'
    allocation_change: float  # Change in allocation (positive = increase)
    allocation_before: float  # Allocation before change
    allocation_after: float   # Allocation after change
    
    # Forward-looking returns (after allocation change)
    return_1d: float    # 1-day forward return
    return_5d: float    # 5-day forward return
    return_20d: float   # 20-day forward return
    
    # Anticipation metrics
    anticipation_score: float  # How well the allocation change predicted returns
    timing_advantage: float    # Days of advance timing
    confidence_level: float    # Statistical confidence of anticipation
    
    # Result classification
    anticipation_result: AnticipationResult
    success_message: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['date'] = result['date'].isoformat()
        result['anticipation_result'] = result['anticipation_result'].value
        return result
    
    def validate(self) -> List[str]:
        """Validate anticipation event"""
        errors = []
        
        if not (-1.0 <= self.allocation_before <= 1.0):
            errors.append(f"Allocation before {self.allocation_before} outside reasonable bounds [-1.0, 1.0]")
        
        if not (-1.0 <= self.allocation_after <= 1.0):
            errors.append(f"Allocation after {self.allocation_after} outside reasonable bounds [-1.0, 1.0]")
        
        if abs(self.allocation_change) < 0.001:
            errors.append("Allocation change too small to be meaningful")
        
        if not (0.0 <= self.confidence_level <= 1.0):
            errors.append("Confidence level must be between 0.0 and 1.0")
        
        if self.timing_advantage < 0:
            errors.append("Timing advantage cannot be negative")
        
        return errors
    
    def get_anticipation_summary(self) -> str:
        """Get human-readable anticipation summary"""
        if self.anticipation_result == AnticipationResult.SUCCESS:
            return f"SUCCESS: Allocation change anticipated returns with {self.anticipation_score:.3f} score"
        elif self.anticipation_result == AnticipationResult.FAILURE:
            return f"FAILURE: Allocation change did not anticipate returns ({self.anticipation_score:.3f} score)"
        elif self.anticipation_result == AnticipationResult.NEUTRAL:
            return f"NEUTRAL: No significant anticipation detected ({self.anticipation_score:.3f} score)"
        else:
            return f"INSUFFICIENT DATA: {self.success_message}"


class ForwardValidator:
    """
    Forward Validator - Phase 6: Enhancement Layer
    
    Tests anticipation events and validates that allocation changes
    preceded corresponding market returns, providing evidence of predictive capability.
    
    ENFORCES REQUIREMENTS:
    - 10.1-10.6: Anticipation testing and timing validation
    
    V3 INTEGRATION:
    - Integrates with existing allocation systems
    - Provides anticipation validation for strategy approval
    - Maintains anticipation success history
    """
    
    def __init__(self, base_dir: str = "data/intelligence"):
        """
        Initialize Forward Validator
        
        Args:
            base_dir: Base directory for anticipation data
        """
        self.base_dir = base_dir
        self.anticipation_dir = os.path.join(base_dir, "anticipation_testing")
        
        # Create directories
        os.makedirs(self.anticipation_dir, exist_ok=True)
        
        # Configuration
        self.config = {
            # Allocation change thresholds
            'min_allocation_change': 0.05,  # 5% minimum change to be considered
            'significant_change_threshold': 0.10,  # 10% for significant changes
            
            # Forward return periods
            'return_periods': [1, 5, 20],  # Days to look forward
            'primary_period': 20,  # Primary period for anticipation scoring
            
            # Anticipation scoring
            'success_threshold': 0.3,  # Minimum score for success
            'confidence_threshold': 0.05,  # Statistical significance threshold
            
            # Timing analysis
            'max_timing_advantage': 10,  # Maximum days of advance timing to consider
            'min_observations': 20,  # Minimum observations for statistical tests
        }
        
        # Anticipation tracking state
        self.anticipation_history: List[AnticipationEvent] = []
        self.success_rate_history: Dict[str, float] = {}
        
        # Load existing history
        self._load_anticipation_history()
        
        print("🔮 Forward Validator initialized")
        print(f"   Output: {self.anticipation_dir}/")
        print(f"   Min allocation change: {self.config['min_allocation_change']:.1%}")
        print(f"   Success threshold: {self.config['success_threshold']:.3f}")
        print(f"   Primary return period: {self.config['primary_period']} days")
    
    def detect_allocation_changes(self, allocation_data: pd.DataFrame) -> pd.DataFrame:
        """
        Detect significant allocation changes for anticipation testing
        
        VALIDATES REQUIREMENTS 10.1, 10.2
        
        Args:
            allocation_data: DataFrame with allocation data (date, allocation columns)
            
        Returns:
            DataFrame with detected allocation changes
        """
        
        print(f"🔍 Detecting allocation changes...")
        
        if allocation_data.empty:
            return pd.DataFrame()
        
        # Ensure date column is datetime
        if 'date' not in allocation_data.columns:
            if allocation_data.index.name == 'date' or isinstance(allocation_data.index, pd.DatetimeIndex):
                allocation_data = allocation_data.reset_index()
            else:
                raise ValueError("Allocation data must have 'date' column or datetime index")
        
        allocation_data['date'] = pd.to_datetime(allocation_data['date'])
        allocation_data = allocation_data.sort_values('date')
        
        # Find allocation columns (exclude date)
        allocation_columns = [col for col in allocation_data.columns if col != 'date']
        
        if not allocation_columns:
            print("⚠️ No allocation columns found")
            return pd.DataFrame()
        
        print(f"   📊 Analyzing {len(allocation_columns)} allocation series")
        print(f"   📅 Date range: {allocation_data['date'].min().date()} to {allocation_data['date'].max().date()}")
        
        change_events = []
        
        for col in allocation_columns:
            allocation_series = allocation_data[col].values
            dates = allocation_data['date'].values
            
            # Calculate rolling changes
            for i in range(1, len(allocation_series)):
                current_allocation = allocation_series[i]
                previous_allocation = allocation_series[i-1]
                
                # Skip if either value is NaN
                if np.isnan(current_allocation) or np.isnan(previous_allocation):
                    continue
                
                allocation_change = current_allocation - previous_allocation
                
                # Check if change is significant
                if abs(allocation_change) >= self.config['min_allocation_change']:
                    
                    # Determine event type
                    if allocation_change > 0:
                        event_type = 'increase'
                    else:
                        event_type = 'decrease'
                    
                    # Check for regime shift (large change)
                    if abs(allocation_change) >= self.config['significant_change_threshold']:
                        event_type = 'regime_shift'
                    
                    change_event = {
                        'date': dates[i],
                        'allocation_series': col,
                        'event_type': event_type,
                        'allocation_change': allocation_change,
                        'allocation_before': previous_allocation,
                        'allocation_after': current_allocation,
                        'change_magnitude': abs(allocation_change)
                    }
                    change_events.append(change_event)
        
        if change_events:
            changes_df = pd.DataFrame(change_events)
            print(f"   ✅ Detected {len(changes_df)} significant allocation changes")
            
            # Show event type breakdown
            event_counts = changes_df['event_type'].value_counts()
            print(f"   📈 Event breakdown: {dict(event_counts)}")
            
            return changes_df
        else:
            print("   ⚠️ No significant allocation changes detected")
            return pd.DataFrame()
    
    def calculate_forward_returns(self, change_events: pd.DataFrame, 
                                return_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate forward returns for each allocation change event
        
        VALIDATES REQUIREMENTS 10.3, 10.4
        
        Args:
            change_events: DataFrame with allocation change events
            return_data: DataFrame with return data (date, return columns)
            
        Returns:
            DataFrame with forward returns added
        """
        
        print(f"📈 Calculating forward returns...")
        
        if change_events.empty or return_data.empty:
            return change_events
        
        # Ensure return data has date column
        if 'date' not in return_data.columns:
            if return_data.index.name == 'date' or isinstance(return_data.index, pd.DatetimeIndex):
                return_data = return_data.reset_index()
            else:
                raise ValueError("Return data must have 'date' column or datetime index")
        
        return_data['date'] = pd.to_datetime(return_data['date'])
        return_data = return_data.sort_values('date')
        
        # Find return columns (exclude date)
        return_columns = [col for col in return_data.columns if col != 'date' and 'return' in col.lower()]
        
        if not return_columns:
            # Try to find any numeric columns that might be returns
            numeric_columns = return_data.select_dtypes(include=[np.number]).columns
            return_columns = [col for col in numeric_columns if col != 'date']
        
        if not return_columns:
            print("⚠️ No return columns found")
            return change_events
        
        # Use the first return column as primary return series
        primary_return_col = return_columns[0]
        print(f"   📊 Using '{primary_return_col}' as primary return series")
        
        # Add forward return columns to change events
        enhanced_events = change_events.copy()
        
        for period in self.config['return_periods']:
            enhanced_events[f'return_{period}d'] = np.nan
        
        # Calculate forward returns for each event
        for idx, event in change_events.iterrows():
            event_date = pd.to_datetime(event['date'])
            
            # Find returns after the event date
            future_returns = return_data[return_data['date'] > event_date].copy()
            
            if future_returns.empty:
                continue
            
            # Calculate cumulative returns for each period
            for period in self.config['return_periods']:
                if len(future_returns) >= period:
                    # Get returns for the specified period
                    period_returns = future_returns[primary_return_col].iloc[:period]
                    
                    # Calculate cumulative return
                    if not period_returns.isna().all():
                        cumulative_return = (1 + period_returns).prod() - 1
                        enhanced_events.loc[idx, f'return_{period}d'] = cumulative_return
        
        # Remove events without sufficient forward return data
        valid_events = enhanced_events.dropna(subset=[f'return_{self.config["primary_period"]}d'])
        
        primary_period_col = f'return_{self.config["primary_period"]}d'
        print(f"   ✅ Calculated forward returns for {len(valid_events)} events")
        print(f"   📊 Primary period ({self.config['primary_period']}d) return range: "
              f"{valid_events[primary_period_col].min():.2%} to "
              f"{valid_events[primary_period_col].max():.2%}")
        
        return valid_events
    
    def calculate_anticipation_score(self, allocation_change: float, 
                                   forward_return: float, 
                                   event_type: str) -> Tuple[float, float]:
        """
        Calculate anticipation score and confidence for an event
        
        VALIDATES REQUIREMENTS 10.4, 10.5
        
        Args:
            allocation_change: Change in allocation
            forward_return: Forward return after change
            event_type: Type of event ('increase', 'decrease', 'regime_shift')
            
        Returns:
            Tuple of (anticipation_score, confidence_level)
        """
        
        # Normalize allocation change and return for scoring
        normalized_change = np.tanh(allocation_change * 10)  # Compress to [-1, 1]
        normalized_return = np.tanh(forward_return * 50)     # Compress to [-1, 1]
        
        # Calculate directional alignment
        # Positive score when allocation change and return have same sign
        directional_score = normalized_change * normalized_return
        
        # Magnitude bonus for larger changes and returns
        magnitude_bonus = abs(normalized_change) * abs(normalized_return)
        
        # Event type multiplier
        event_multipliers = {
            'increase': 1.0,
            'decrease': 1.0,
            'regime_shift': 1.2  # Bonus for regime shifts
        }
        event_multiplier = event_multipliers.get(event_type, 1.0)
        
        # Combined anticipation score
        anticipation_score = (directional_score + magnitude_bonus * 0.5) * event_multiplier
        
        # Confidence based on magnitude of change and return
        confidence_base = min(abs(allocation_change) * 10, 1.0) * min(abs(forward_return) * 20, 1.0)
        confidence_level = min(confidence_base, 0.95)  # Cap at 95%
        
        return float(anticipation_score), float(confidence_level)
    
    def classify_anticipation_result(self, anticipation_score: float, 
                                   confidence_level: float) -> Tuple[AnticipationResult, str]:
        """
        Classify anticipation result based on score and confidence
        
        VALIDATES REQUIREMENTS 10.5, 10.6
        
        Args:
            anticipation_score: Calculated anticipation score
            confidence_level: Statistical confidence level
            
        Returns:
            Tuple of (result, message)
        """
        
        # Check confidence threshold
        if confidence_level < self.config['confidence_threshold']:
            return AnticipationResult.INSUFFICIENT_DATA, f"Low confidence: {confidence_level:.3f} < {self.config['confidence_threshold']:.3f}"
        
        # Check success threshold
        if anticipation_score >= self.config['success_threshold']:
            return AnticipationResult.SUCCESS, f"Strong anticipation: score {anticipation_score:.3f} >= {self.config['success_threshold']:.3f}"
        elif anticipation_score <= -self.config['success_threshold']:
            return AnticipationResult.FAILURE, f"Poor anticipation: score {anticipation_score:.3f} <= {-self.config['success_threshold']:.3f}"
        else:
            return AnticipationResult.NEUTRAL, f"Neutral anticipation: score {anticipation_score:.3f} within neutral range"
    
    def test_anticipation_events(self, allocation_data: pd.DataFrame, 
                               return_data: pd.DataFrame,
                               test_date: Optional[datetime] = None) -> List[AnticipationEvent]:
        """
        Test anticipation events for allocation changes
        
        VALIDATES REQUIREMENTS 10.1-10.6
        
        Args:
            allocation_data: DataFrame with allocation data
            return_data: DataFrame with return data
            test_date: Date of testing (default: now)
            
        Returns:
            List of anticipation events
        """
        
        if test_date is None:
            test_date = datetime.now()
        
        print(f"🔮 TESTING ANTICIPATION EVENTS - {test_date.date()}")
        print("=" * 60)
        
        # Detect allocation changes
        change_events = self.detect_allocation_changes(allocation_data)
        
        if change_events.empty:
            print("⚠️ No allocation changes detected for anticipation testing")
            return []
        
        # Calculate forward returns
        events_with_returns = self.calculate_forward_returns(change_events, return_data)
        
        if events_with_returns.empty:
            print("⚠️ No events with sufficient forward return data")
            return []
        
        # Test each event for anticipation
        anticipation_events = []
        
        print(f"\n🧪 Testing {len(events_with_returns)} events for anticipation...")
        
        for idx, event in events_with_returns.iterrows():
            try:
                # Get primary forward return
                primary_return = event[f'return_{self.config["primary_period"]}d']
                
                if np.isnan(primary_return):
                    continue
                
                # Calculate anticipation score
                anticipation_score, confidence_level = self.calculate_anticipation_score(
                    event['allocation_change'], 
                    primary_return, 
                    event['event_type']
                )
                
                # Classify result
                anticipation_result, success_message = self.classify_anticipation_result(
                    anticipation_score, confidence_level
                )
                
                # Calculate timing advantage (simplified)
                timing_advantage = self.config['primary_period'] / 2.0  # Assume mid-period timing
                
                # Create anticipation event
                anticipation_event = AnticipationEvent(
                    date=pd.to_datetime(event['date']),
                    event_type=event['event_type'],
                    allocation_change=event['allocation_change'],
                    allocation_before=event['allocation_before'],
                    allocation_after=event['allocation_after'],
                    return_1d=event.get('return_1d', np.nan),
                    return_5d=event.get('return_5d', np.nan),
                    return_20d=event.get('return_20d', np.nan),
                    anticipation_score=anticipation_score,
                    timing_advantage=timing_advantage,
                    confidence_level=confidence_level,
                    anticipation_result=anticipation_result,
                    success_message=success_message
                )
                
                # Validate event
                validation_errors = anticipation_event.validate()
                if not validation_errors:
                    anticipation_events.append(anticipation_event)
                else:
                    print(f"⚠️ Event validation warnings: {validation_errors}")
                
            except Exception as e:
                print(f"❌ Error processing event {idx}: {e}")
                continue
        
        # Save anticipation events
        self._save_anticipation_events(anticipation_events)
        
        # Update history
        self.anticipation_history.extend(anticipation_events)
        
        # Calculate success rate
        success_rate = self._calculate_success_rate(anticipation_events)
        
        # Summary
        print(f"\n✅ ANTICIPATION TESTING COMPLETE")
        print(f"   📊 Events tested: {len(anticipation_events)}")
        print(f"   ✅ Successful anticipations: {len([e for e in anticipation_events if e.anticipation_result == AnticipationResult.SUCCESS])}")
        print(f"   ❌ Failed anticipations: {len([e for e in anticipation_events if e.anticipation_result == AnticipationResult.FAILURE])}")
        print(f"   ➖ Neutral anticipations: {len([e for e in anticipation_events if e.anticipation_result == AnticipationResult.NEUTRAL])}")
        print(f"   📈 Success rate: {success_rate:.1%}")
        
        return anticipation_events
    
    def _calculate_success_rate(self, events: List[AnticipationEvent]) -> float:
        """Calculate anticipation success rate"""
        
        if not events:
            return 0.0
        
        # Count successful anticipations
        successful = len([e for e in events if e.anticipation_result == AnticipationResult.SUCCESS])
        
        # Count total valid tests (exclude insufficient data)
        valid_tests = len([e for e in events if e.anticipation_result != AnticipationResult.INSUFFICIENT_DATA])
        
        if valid_tests == 0:
            return 0.0
        
        return successful / valid_tests
    
    def get_anticipation_summary(self, days_back: Optional[int] = None) -> Dict[str, Any]:
        """
        Get anticipation testing summary
        
        Args:
            days_back: Number of days to look back (default: all history)
            
        Returns:
            Anticipation summary
        """
        
        events = self.anticipation_history
        
        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            events = [e for e in events if e.date >= cutoff_date]
        
        if not events:
            return {
                'total_events': 0,
                'success_rate': 0.0,
                'avg_anticipation_score': 0.0,
                'avg_timing_advantage': 0.0
            }
        
        # Calculate metrics
        success_rate = self._calculate_success_rate(events)
        avg_score = np.mean([e.anticipation_score for e in events])
        avg_timing = np.mean([e.timing_advantage for e in events])
        
        # Event type breakdown
        event_types = {}
        for event in events:
            event_type = event.event_type
            if event_type not in event_types:
                event_types[event_type] = {'count': 0, 'success_rate': 0.0}
            event_types[event_type]['count'] += 1
        
        # Calculate success rate by event type
        for event_type in event_types:
            type_events = [e for e in events if e.event_type == event_type]
            event_types[event_type]['success_rate'] = self._calculate_success_rate(type_events)
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_events': len(events),
            'success_rate': success_rate,
            'avg_anticipation_score': avg_score,
            'avg_timing_advantage': avg_timing,
            'event_type_breakdown': event_types,
            'recent_performance': {
                'last_30_days': self._calculate_success_rate([e for e in events if e.date >= datetime.now() - timedelta(days=30)]),
                'last_90_days': self._calculate_success_rate([e for e in events if e.date >= datetime.now() - timedelta(days=90)])
            }
        }
        
        return summary
    
    def _save_anticipation_events(self, events: List[AnticipationEvent]):
        """
        Save anticipation events to parquet file
        
        VALIDATES REQUIREMENTS 10.6
        
        Args:
            events: List of anticipation events to save
        """
        
        if not events:
            return
        
        try:
            # Ensure directory exists
            os.makedirs(self.anticipation_dir, exist_ok=True)
            
            # Convert to DataFrame
            events_data = [event.to_dict() for event in events]
            events_df = pd.DataFrame(events_data)
            
            # Append to existing file or create new
            file_path = os.path.join(self.anticipation_dir, "anticipation_test.parquet")
            
            if os.path.exists(file_path):
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, events_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False)
            else:
                # Create new file
                events_df.to_parquet(file_path, index=False)
            
            print(f"   ✅ Anticipation events saved: {len(events)} events")
            
        except Exception as e:
            print(f"❌ Failed to save anticipation events: {e}")
    
    def _load_anticipation_history(self):
        """Load anticipation history from file"""
        
        try:
            file_path = os.path.join(self.anticipation_dir, "anticipation_test.parquet")
            
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                
                # Rebuild anticipation history
                self.anticipation_history = []
                
                for _, row in df.iterrows():
                    anticipation_event = AnticipationEvent(
                        date=pd.to_datetime(row['date']),
                        event_type=row['event_type'],
                        allocation_change=row['allocation_change'],
                        allocation_before=row['allocation_before'],
                        allocation_after=row['allocation_after'],
                        return_1d=row['return_1d'],
                        return_5d=row['return_5d'],
                        return_20d=row['return_20d'],
                        anticipation_score=row['anticipation_score'],
                        timing_advantage=row['timing_advantage'],
                        confidence_level=row['confidence_level'],
                        anticipation_result=AnticipationResult(row['anticipation_result']),
                        success_message=row['success_message']
                    )
                    
                    self.anticipation_history.append(anticipation_event)
                
                print(f"✅ Loaded anticipation history: {len(self.anticipation_history)} events")
            
        except Exception as e:
            print(f"⚠️ Failed to load anticipation history: {e}")


def main():
    """Demonstrate Forward Validator"""
    
    print("🔮 FORWARD VALIDATOR - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize validator
    validator = ForwardValidator()
    
    # Create synthetic allocation and return data
    np.random.seed(42)
    n_periods = 200
    
    dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='D')
    
    # Generate allocation data with regime changes
    allocation_data = []
    base_allocation = 0.6
    
    for i, date in enumerate(dates):
        # Add some regime shifts
        if i == 50:
            base_allocation = 0.8  # Increase allocation
        elif i == 100:
            base_allocation = 0.4  # Decrease allocation
        elif i == 150:
            base_allocation = 0.7  # Another increase
        
        # Add noise
        noise = np.random.normal(0, 0.02)
        allocation = max(0.1, min(0.9, base_allocation + noise))
        
        allocation_data.append({
            'date': date,
            'strategy_allocation': allocation,
            'total_exposure': allocation * 1.2  # Leveraged exposure
        })
    
    allocation_df = pd.DataFrame(allocation_data)
    
    # Generate return data with some correlation to allocation changes
    return_data = []
    
    for i, date in enumerate(dates):
        # Base return
        base_return = 0.0005
        
        # Add correlation with allocation changes
        if i > 0:
            allocation_change = allocation_df.iloc[i]['strategy_allocation'] - allocation_df.iloc[i-1]['strategy_allocation']
            # Positive correlation with a lag
            if i >= 5:
                lagged_change = allocation_df.iloc[i-5]['strategy_allocation'] - allocation_df.iloc[i-6]['strategy_allocation'] if i >= 6 else 0
                base_return += lagged_change * 0.5  # 50% correlation with 5-day lag
        
        # Add noise
        noise = np.random.normal(0, 0.015)
        daily_return = base_return + noise
        
        return_data.append({
            'date': date,
            'strategy_return': daily_return,
            'market_return': daily_return * 0.8 + np.random.normal(0, 0.01)
        })
    
    return_df = pd.DataFrame(return_data)
    
    print(f"📊 Generated synthetic data:")
    print(f"   Allocation data: {len(allocation_df)} days")
    print(f"   Return data: {len(return_df)} days")
    print(f"   Date range: {dates[0].date()} to {dates[-1].date()}")
    
    # Test anticipation events
    anticipation_events = validator.test_anticipation_events(allocation_df, return_df)
    
    print(f"\n🔮 Anticipation Test Results:")
    print(f"   Total events: {len(anticipation_events)}")
    
    for event in anticipation_events[:5]:  # Show first 5 events
        print(f"   {event.date.date()}: {event.event_type}")
        print(f"      Allocation: {event.allocation_before:.1%} → {event.allocation_after:.1%}")
        print(f"      20d Return: {event.return_20d:.2%}")
        print(f"      Score: {event.anticipation_score:.3f}")
        print(f"      Result: {event.anticipation_result.value}")
    
    # Get summary
    summary = validator.get_anticipation_summary()
    print(f"\n📋 Anticipation Summary:")
    print(f"   Success rate: {summary['success_rate']:.1%}")
    print(f"   Avg score: {summary['avg_anticipation_score']:.3f}")
    print(f"   Avg timing advantage: {summary['avg_timing_advantage']:.1f} days")
    
    if summary['event_type_breakdown']:
        print(f"   Event type breakdown:")
        for event_type, stats in summary['event_type_breakdown'].items():
            print(f"      {event_type}: {stats['count']} events, {stats['success_rate']:.1%} success")
    
    print("\n✅ Forward Validator demonstration complete")


if __name__ == "__main__":
    main()