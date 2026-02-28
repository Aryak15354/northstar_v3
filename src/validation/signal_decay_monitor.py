#!/usr/bin/env python3
"""
📉 SIGNAL DECAY MONITOR - PHASE 6: ENHANCEMENT LAYER
Track signal-return correlation over time and detect decay

This implements the signal decay monitoring requirements for Phase 6 (Enhancement)
of the institutional validation framework. It tracks signal-return correlation
over time, computes decay rate, and alerts when decay worsens for 3 months.

CRITICAL PRINCIPLE: Signal Quality Monitoring
- Track signal-return correlation over time
- Compute decay rate for each signal
- Alert when decay worsens for 3 months
- Persist to data/validation/signal_decay.parquet
- Provide early warning of signal degradation

Usage:
    from src.validation.signal_decay_monitor import SignalDecayMonitor
    
    monitor = SignalDecayMonitor()
    monitor.track_signal_decay("momentum", signal_values, returns)
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


class DecayAlertLevel(Enum):
    """Signal decay alert levels"""
    NONE = "none"           # No decay detected
    MILD = "mild"           # Slight decay (1 month)
    MODERATE = "moderate"   # Moderate decay (2 months)
    SEVERE = "severe"       # Severe decay (3+ months)


@dataclass
class SignalDecayRecord:
    """
    Signal decay record for tracking correlation degradation
    
    Complete decay information with statistical measures.
    """
    date: datetime
    signal_name: str
    correlation_current: float  # Current correlation
    correlation_3m_avg: float   # 3-month average
    correlation_6m_avg: float   # 6-month average
    decay_rate: float          # Rate of decay per month
    decay_months: int          # Consecutive months of decay
    alert_level: DecayAlertLevel
    statistical_significance: float  # p-value of decay trend
    observations: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['date'] = result['date'].isoformat()
        result['alert_level'] = result['alert_level'].value
        return result
    
    def validate(self) -> List[str]:
        """Validate decay record"""
        errors = []
        
        if not (-1.0 <= self.correlation_current <= 1.0):
            errors.append(f"Current correlation {self.correlation_current} outside bounds [-1.0, 1.0]")
        
        if not (-1.0 <= self.correlation_3m_avg <= 1.0):
            errors.append(f"3-month correlation {self.correlation_3m_avg} outside bounds [-1.0, 1.0]")
        
        if self.decay_months < 0:
            errors.append("Decay months cannot be negative")
        
        if not (0.0 <= self.statistical_significance <= 1.0):
            errors.append("Statistical significance must be between 0.0 and 1.0")
        
        if self.observations < 10:
            errors.append("Insufficient observations for decay analysis")
        
        return errors
    
    def get_alert_description(self) -> str:
        """Get human-readable alert description"""
        if self.alert_level == DecayAlertLevel.NONE:
            return "No decay detected - signal quality stable"
        elif self.alert_level == DecayAlertLevel.MILD:
            return "Mild decay detected - monitor signal quality"
        elif self.alert_level == DecayAlertLevel.MODERATE:
            return "Moderate decay detected - consider signal adjustment"
        else:
            return "Severe decay detected - signal requires immediate attention"


class SignalDecayMonitor:
    """
    Signal Decay Monitor - Phase 6: Enhancement Layer
    
    Tracks signal-return correlation over time and detects decay patterns.
    Provides early warning when signal quality degrades consistently.
    
    ENFORCES REQUIREMENTS:
    - 18.1-18.8: Signal decay monitoring and alerting
    
    V3 INTEGRATION:
    - Integrates with existing signal systems
    - Provides decay alerts for strategy adjustment
    - Maintains signal quality history
    """
    
    def __init__(self, base_dir: str = "data/validation"):
        """
        Initialize Signal Decay Monitor
        
        Args:
            base_dir: Base directory for decay data
        """
        self.base_dir = base_dir
        self.decay_dir = os.path.join(base_dir, "signal_decay")
        
        # Create directories
        os.makedirs(self.decay_dir, exist_ok=True)
        
        # Configuration
        self.config = {
            'correlation_window': 26,  # Weeks for correlation calculation
            'decay_threshold': -0.05,  # Minimum decay per month to trigger alert
            'alert_months': 3,  # Months of decay to trigger severe alert
            'min_observations': 20,  # Minimum observations for correlation
            'significance_level': 0.05,  # Statistical significance threshold
            'correlation_methods': ['pearson', 'spearman'],  # Correlation methods
            'decay_smoothing': 0.3,  # Exponential smoothing for decay rate
        }
        
        # Signal tracking state
        self.signal_history: Dict[str, List[Dict]] = {}
        self.decay_alerts: Dict[str, DecayAlertLevel] = {}
        
        # Load existing history
        self._load_signal_history()
        
        print("📉 Signal Decay Monitor initialized")
        print(f"   Output: {self.decay_dir}/")
        print(f"   Correlation window: {self.config['correlation_window']} weeks")
        print(f"   Decay threshold: {self.config['decay_threshold']:.3f} per month")
        print(f"   Alert threshold: {self.config['alert_months']} months")
    
    def compute_signal_correlation(self, signal_values: np.ndarray, 
                                 returns: np.ndarray, 
                                 method: str = 'pearson') -> Tuple[float, float]:
        """
        Compute correlation between signal and returns
        
        VALIDATES REQUIREMENTS 18.1, 18.2
        
        Args:
            signal_values: Signal values array
            returns: Return values array
            method: Correlation method ('pearson' or 'spearman')
            
        Returns:
            Tuple of (correlation, p_value)
        """
        
        # Ensure arrays are same length
        min_length = min(len(signal_values), len(returns))
        signal_clean = signal_values[:min_length]
        returns_clean = returns[:min_length]
        
        # Remove NaN values
        valid_mask = ~(np.isnan(signal_clean) | np.isnan(returns_clean))
        
        if valid_mask.sum() < self.config['min_observations']:
            return 0.0, 1.0
        
        signal_valid = signal_clean[valid_mask]
        returns_valid = returns_clean[valid_mask]
        
        try:
            if method == 'pearson':
                correlation, p_value = pearsonr(signal_valid, returns_valid)
            elif method == 'spearman':
                correlation, p_value = spearmanr(signal_valid, returns_valid)
            else:
                raise ValueError(f"Unknown correlation method: {method}")
            
            # Handle NaN results
            if np.isnan(correlation):
                correlation = 0.0
            if np.isnan(p_value):
                p_value = 1.0
            
            return float(correlation), float(p_value)
            
        except Exception as e:
            print(f"⚠️ Error computing correlation: {e}")
            return 0.0, 1.0
    
    def calculate_decay_rate(self, correlations: List[float], 
                           dates: List[datetime]) -> Tuple[float, float]:
        """
        Calculate decay rate from correlation history
        
        VALIDATES REQUIREMENTS 18.3, 18.4
        
        Args:
            correlations: List of correlation values
            dates: List of corresponding dates
            
        Returns:
            Tuple of (decay_rate_per_month, p_value)
        """
        
        if len(correlations) < 3:
            return 0.0, 1.0
        
        try:
            # Convert dates to months since first date
            first_date = min(dates)
            months = [(d - first_date).days / 30.44 for d in dates]  # Average days per month
            
            # Linear regression: correlation = intercept + slope * months
            X = np.array(months).reshape(-1, 1)
            y = np.array(correlations)
            
            # Remove NaN values
            valid_mask = ~(np.isnan(X.flatten()) | np.isnan(y))
            if valid_mask.sum() < 3:
                return 0.0, 1.0
            
            X_clean = X[valid_mask]
            y_clean = y[valid_mask]
            
            # Fit regression
            reg = LinearRegression()
            reg.fit(X_clean, y_clean)
            
            # Calculate statistics
            y_pred = reg.predict(X_clean)
            residuals = y_clean - y_pred
            
            # Standard error and t-statistic for slope
            n = len(X_clean)
            if n <= 2:
                return float(reg.coef_[0]), 1.0
            
            mse = np.sum(residuals**2) / (n - 2)
            x_centered = X_clean - np.mean(X_clean)
            se_slope = np.sqrt(mse / np.sum(x_centered**2))
            
            if se_slope > 0:
                t_stat = reg.coef_[0] / se_slope
                df = n - 2
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))
            else:
                p_value = 1.0
            
            return float(reg.coef_[0]), float(p_value)
            
        except Exception as e:
            print(f"⚠️ Error calculating decay rate: {e}")
            return 0.0, 1.0
    
    def determine_alert_level(self, decay_rate: float, 
                            decay_months: int, 
                            significance: float) -> DecayAlertLevel:
        """
        Determine alert level based on decay characteristics
        
        VALIDATES REQUIREMENTS 18.5, 18.8
        
        Args:
            decay_rate: Rate of decay per month
            decay_months: Consecutive months of decay
            significance: Statistical significance of decay
            
        Returns:
            Alert level
        """
        
        # No alert if decay is not statistically significant
        if significance > self.config['significance_level']:
            return DecayAlertLevel.NONE
        
        # No alert if decay is positive (improving)
        if decay_rate >= 0:
            return DecayAlertLevel.NONE
        
        # No alert if decay is too small
        if decay_rate > self.config['decay_threshold']:
            return DecayAlertLevel.NONE
        
        # Determine severity based on duration and magnitude
        if decay_months >= self.config['alert_months']:
            return DecayAlertLevel.SEVERE
        elif decay_months >= 2:
            return DecayAlertLevel.MODERATE
        elif decay_months >= 1:
            return DecayAlertLevel.MILD
        else:
            return DecayAlertLevel.NONE
    
    def track_signal_decay(self, signal_name: str, 
                          signal_values: np.ndarray, 
                          returns: np.ndarray,
                          date: Optional[datetime] = None) -> SignalDecayRecord:
        """
        Track signal decay for a specific signal
        
        VALIDATES REQUIREMENTS 18.1-18.8
        
        Args:
            signal_name: Name of the signal
            signal_values: Signal values array
            returns: Return values array
            date: Date of measurement (default: now)
            
        Returns:
            Signal decay record
        """
        
        if date is None:
            date = datetime.now()
        
        print(f"📉 Tracking signal decay: {signal_name}")
        
        # Compute current correlation
        correlation, p_value = self.compute_signal_correlation(signal_values, returns)
        
        # Initialize signal history if needed
        if signal_name not in self.signal_history:
            self.signal_history[signal_name] = []
        
        # Add current measurement
        measurement = {
            'date': date,
            'correlation': correlation,
            'p_value': p_value,
            'observations': len(signal_values)
        }
        self.signal_history[signal_name].append(measurement)
        
        # Keep only recent history (last 12 months)
        cutoff_date = date - timedelta(days=365)
        self.signal_history[signal_name] = [
            m for m in self.signal_history[signal_name] 
            if m['date'] >= cutoff_date
        ]
        
        # Calculate historical averages
        recent_correlations = [m['correlation'] for m in self.signal_history[signal_name]]
        recent_dates = [m['date'] for m in self.signal_history[signal_name]]
        
        # 3-month and 6-month averages
        three_months_ago = date - timedelta(days=90)
        six_months_ago = date - timedelta(days=180)
        
        corr_3m = [m['correlation'] for m in self.signal_history[signal_name] if m['date'] >= three_months_ago]
        corr_6m = [m['correlation'] for m in self.signal_history[signal_name] if m['date'] >= six_months_ago]
        
        correlation_3m_avg = np.mean(corr_3m) if corr_3m else correlation
        correlation_6m_avg = np.mean(corr_6m) if corr_6m else correlation
        
        # Calculate decay rate
        decay_rate, decay_significance = self.calculate_decay_rate(recent_correlations, recent_dates)
        
        # Count consecutive months of decay
        decay_months = self._count_decay_months(signal_name, date)
        
        # Determine alert level
        alert_level = self.determine_alert_level(decay_rate, decay_months, decay_significance)
        
        # Create decay record
        decay_record = SignalDecayRecord(
            date=date,
            signal_name=signal_name,
            correlation_current=correlation,
            correlation_3m_avg=correlation_3m_avg,
            correlation_6m_avg=correlation_6m_avg,
            decay_rate=decay_rate,
            decay_months=decay_months,
            alert_level=alert_level,
            statistical_significance=decay_significance,
            observations=len(signal_values)
        )
        
        # Validate record
        validation_errors = decay_record.validate()
        if validation_errors:
            print(f"⚠️ Decay record validation warnings:")
            for error in validation_errors:
                print(f"   {error}")
        
        # Update alert state
        self.decay_alerts[signal_name] = alert_level
        
        # Save decay record
        self._save_decay_record(decay_record)
        
        print(f"   📊 Current correlation: {correlation:.3f}")
        print(f"   📉 Decay rate: {decay_rate:.4f} per month")
        print(f"   ⚠️  Alert level: {alert_level.value}")
        print(f"   📅 Decay months: {decay_months}")
        
        return decay_record
    
    def _count_decay_months(self, signal_name: str, current_date: datetime) -> int:
        """Count consecutive months of decay"""
        
        if signal_name not in self.signal_history:
            return 0
        
        history = self.signal_history[signal_name]
        if len(history) < 2:
            return 0
        
        # Sort by date
        history_sorted = sorted(history, key=lambda x: x['date'])
        
        # Count consecutive months where correlation decreased
        decay_months = 0
        
        for i in range(len(history_sorted) - 1, 0, -1):
            current_corr = history_sorted[i]['correlation']
            previous_corr = history_sorted[i-1]['correlation']
            
            if current_corr < previous_corr:
                decay_months += 1
            else:
                break
        
        return decay_months
    
    def get_decay_alerts(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current decay alerts for all signals
        
        Returns:
            Dictionary of signal alerts
        """
        
        alerts = {}
        
        for signal_name, alert_level in self.decay_alerts.items():
            if alert_level != DecayAlertLevel.NONE:
                # Get latest record for this signal
                if signal_name in self.signal_history and self.signal_history[signal_name]:
                    latest = self.signal_history[signal_name][-1]
                    
                    alerts[signal_name] = {
                        'alert_level': alert_level.value,
                        'correlation_current': latest['correlation'],
                        'last_updated': latest['date'].isoformat(),
                        'description': SignalDecayRecord(
                            date=latest['date'],
                            signal_name=signal_name,
                            correlation_current=latest['correlation'],
                            correlation_3m_avg=0.0,
                            correlation_6m_avg=0.0,
                            decay_rate=0.0,
                            decay_months=0,
                            alert_level=alert_level,
                            statistical_significance=0.0,
                            observations=0
                        ).get_alert_description()
                    }
        
        return alerts
    
    def _save_decay_record(self, decay_record: SignalDecayRecord):
        """
        Save decay record to parquet file
        
        VALIDATES REQUIREMENTS 18.7
        
        Args:
            decay_record: Decay record to save
        """
        
        try:
            # Convert to DataFrame
            record_data = decay_record.to_dict()
            record_df = pd.DataFrame([record_data])
            
            # Append to existing file or create new
            file_path = os.path.join(self.decay_dir, "signal_decay.parquet")
            
            if os.path.exists(file_path):
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, record_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False)
            else:
                # Create new file
                record_df.to_parquet(file_path, index=False)
            
            print(f"   ✅ Decay record saved: {decay_record.signal_name}")
            
        except Exception as e:
            print(f"❌ Failed to save decay record: {e}")
    
    def _load_signal_history(self):
        """Load signal history from file"""
        
        try:
            file_path = os.path.join(self.decay_dir, "signal_decay.parquet")
            
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                
                # Rebuild signal history
                self.signal_history = {}
                self.decay_alerts = {}
                
                for _, row in df.iterrows():
                    signal_name = row['signal_name']
                    
                    if signal_name not in self.signal_history:
                        self.signal_history[signal_name] = []
                    
                    measurement = {
                        'date': pd.to_datetime(row['date']),
                        'correlation': row['correlation_current'],
                        'p_value': row.get('statistical_significance', 0.05),
                        'observations': row['observations']
                    }
                    self.signal_history[signal_name].append(measurement)
                    
                    # Update latest alert level
                    self.decay_alerts[signal_name] = DecayAlertLevel(row['alert_level'])
                
                print(f"✅ Loaded signal history for {len(self.signal_history)} signals")
            
        except Exception as e:
            print(f"⚠️ Failed to load signal history: {e}")
    
    def generate_decay_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive decay report
        
        Returns:
            Decay report summary
        """
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_signals': len(self.signal_history),
            'signals_with_alerts': len([a for a in self.decay_alerts.values() if a != DecayAlertLevel.NONE]),
            'alert_summary': {},
            'signal_details': {}
        }
        
        # Count alerts by level
        for level in DecayAlertLevel:
            count = len([a for a in self.decay_alerts.values() if a == level])
            report['alert_summary'][level.value] = count
        
        # Signal details
        for signal_name, history in self.signal_history.items():
            if history:
                latest = history[-1]
                alert_level = self.decay_alerts.get(signal_name, DecayAlertLevel.NONE)
                
                report['signal_details'][signal_name] = {
                    'current_correlation': latest['correlation'],
                    'alert_level': alert_level.value,
                    'last_updated': latest['date'].isoformat(),
                    'history_length': len(history)
                }
        
        return report


def main():
    """Demonstrate Signal Decay Monitor"""
    
    print("📉 SIGNAL DECAY MONITOR - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize monitor
    monitor = SignalDecayMonitor()
    
    # Create synthetic signal data with decay
    np.random.seed(42)
    n_periods = 50
    
    # Generate returns
    returns = np.random.normal(0, 0.02, n_periods)
    
    # Generate signal with initial correlation that decays over time
    initial_correlation = 0.6
    decay_factor = 0.98  # Slight decay each period
    
    signal_values = []
    for i in range(n_periods):
        # Correlation decays over time
        current_correlation = initial_correlation * (decay_factor ** i)
        
        # Generate signal with target correlation
        noise = np.random.normal(0, 0.01)
        signal_value = current_correlation * returns[i] + noise
        signal_values.append(signal_value)
    
    signal_values = np.array(signal_values)
    
    print(f"📊 Generated synthetic data:")
    print(f"   Periods: {n_periods}")
    print(f"   Initial correlation: {initial_correlation:.3f}")
    print(f"   Decay factor: {decay_factor:.3f}")
    
    # Track signal decay
    decay_record = monitor.track_signal_decay("momentum_signal", signal_values, returns)
    
    print(f"\n📉 Decay Analysis Results:")
    print(f"   Current correlation: {decay_record.correlation_current:.3f}")
    print(f"   3-month average: {decay_record.correlation_3m_avg:.3f}")
    print(f"   Decay rate: {decay_record.decay_rate:.4f} per month")
    print(f"   Alert level: {decay_record.alert_level.value}")
    print(f"   Description: {decay_record.get_alert_description()}")
    
    # Get all alerts
    alerts = monitor.get_decay_alerts()
    print(f"\n⚠️  Active Alerts: {len(alerts)}")
    for signal, alert in alerts.items():
        print(f"   {signal}: {alert['alert_level']} - {alert['description']}")
    
    # Generate report
    report = monitor.generate_decay_report()
    print(f"\n📋 Decay Report Summary:")
    print(f"   Total signals: {report['total_signals']}")
    print(f"   Signals with alerts: {report['signals_with_alerts']}")
    print(f"   Alert breakdown: {report['alert_summary']}")
    
    print("\n✅ Signal Decay Monitor demonstration complete")


if __name__ == "__main__":
    main()