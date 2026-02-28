#!/usr/bin/env python3
"""
🔄 REDUNDANCY MONITOR - PHASE 6: ENHANCEMENT LAYER
Monitor strategy redundancy and correlation patterns

This implements the redundancy monitoring requirements for Phase 6 (Enhancement)
of the institutional validation framework. It computes rolling correlation between
all strategy pairs and flags redundancy when correlation > 0.85 for 6 months.

CRITICAL PRINCIPLE: Strategy Independence Monitoring
- Compute rolling correlation between all strategy pairs
- Flag redundancy when correlation > 0.85 for 6 months
- Recommend capital reallocation to reduce redundancy
- Persist to data/intelligence/strategy_correlation.parquet
- Provide early warning of strategy convergence

Usage:
    from src.validation.redundancy_monitor import RedundancyMonitor
    
    monitor = RedundancyMonitor()
    monitor.analyze_strategy_redundancy(strategy_returns)
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
from sklearn.preprocessing import StandardScaler
from itertools import combinations

warnings.filterwarnings('ignore')


class RedundancyLevel(Enum):
    """Strategy redundancy levels"""
    LOW = "low"           # Correlation < 0.5
    MODERATE = "moderate" # Correlation 0.5-0.7
    HIGH = "high"         # Correlation 0.7-0.85
    CRITICAL = "critical" # Correlation > 0.85


@dataclass
class RedundancyRecord:
    """
    Strategy redundancy record for tracking correlation patterns
    
    Complete redundancy information with statistical measures.
    """
    date: datetime
    strategy_a: str
    strategy_b: str
    correlation_current: float  # Current correlation
    correlation_6m_avg: float   # 6-month average
    correlation_12m_avg: float  # 12-month average
    redundancy_level: RedundancyLevel
    months_above_threshold: int  # Consecutive months > 0.85
    statistical_significance: float  # p-value of correlation
    observations: int
    recommended_action: str  # Reallocation recommendation
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['date'] = result['date'].isoformat()
        result['redundancy_level'] = result['redundancy_level'].value
        return result
    
    def validate(self) -> List[str]:
        """Validate redundancy record"""
        errors = []
        
        if not (-1.0 <= self.correlation_current <= 1.0):
            errors.append(f"Current correlation {self.correlation_current} outside bounds [-1.0, 1.0]")
        
        if not (-1.0 <= self.correlation_6m_avg <= 1.0):
            errors.append(f"6-month correlation {self.correlation_6m_avg} outside bounds [-1.0, 1.0]")
        
        if self.months_above_threshold < 0:
            errors.append("Months above threshold cannot be negative")
        
        if not (0.0 <= self.statistical_significance <= 1.0):
            errors.append("Statistical significance must be between 0.0 and 1.0")
        
        if self.observations < 10:
            errors.append("Insufficient observations for redundancy analysis")
        
        return errors
    
    def get_redundancy_description(self) -> str:
        """Get human-readable redundancy description"""
        if self.redundancy_level == RedundancyLevel.LOW:
            return "Low redundancy - strategies are sufficiently independent"
        elif self.redundancy_level == RedundancyLevel.MODERATE:
            return "Moderate redundancy - monitor for increasing correlation"
        elif self.redundancy_level == RedundancyLevel.HIGH:
            return "High redundancy - consider reducing allocation overlap"
        else:
            return "Critical redundancy - immediate reallocation recommended"


class RedundancyMonitor:
    """
    Redundancy Monitor - Phase 6: Enhancement Layer
    
    Monitors strategy redundancy through rolling correlation analysis.
    Provides early warning when strategies become too correlated.
    
    ENFORCES REQUIREMENTS:
    - 19.1-19.8: Strategy redundancy monitoring and alerting
    
    V3 INTEGRATION:
    - Integrates with existing strategy systems
    - Provides redundancy alerts for capital allocation
    - Maintains strategy correlation history
    """
    
    def __init__(self, base_dir: str = "data/intelligence"):
        """
        Initialize Redundancy Monitor
        
        Args:
            base_dir: Base directory for redundancy data
        """
        self.base_dir = base_dir
        self.redundancy_dir = os.path.join(base_dir, "strategy_redundancy")
        
        # Create directories
        os.makedirs(self.redundancy_dir, exist_ok=True)
        
        # Configuration
        self.config = {
            'correlation_window': 26,  # Weeks for correlation calculation
            'redundancy_threshold': 0.85,  # Correlation threshold for redundancy
            'alert_months': 6,  # Months above threshold to trigger alert
            'min_observations': 20,  # Minimum observations for correlation
            'significance_level': 0.05,  # Statistical significance threshold
            'correlation_methods': ['pearson', 'spearman'],  # Correlation methods
            'reallocation_threshold': 0.9,  # Threshold for reallocation recommendation
        }
        
        # Strategy tracking state
        self.correlation_history: Dict[str, List[Dict]] = {}
        self.redundancy_alerts: Dict[str, RedundancyLevel] = {}
        
        # Load existing history
        self._load_correlation_history()
        
        print("🔄 Redundancy Monitor initialized")
        print(f"   Output: {self.redundancy_dir}/")
        print(f"   Correlation window: {self.config['correlation_window']} weeks")
        print(f"   Redundancy threshold: {self.config['redundancy_threshold']:.3f}")
        print(f"   Alert threshold: {self.config['alert_months']} months")
    
    def compute_strategy_correlations(self, strategy_returns: pd.DataFrame, 
                                    method: str = 'pearson') -> pd.DataFrame:
        """
        Compute pairwise correlations between all strategies
        
        VALIDATES REQUIREMENTS 19.1, 19.2
        
        Args:
            strategy_returns: DataFrame with strategy returns (columns = strategies)
            method: Correlation method ('pearson' or 'spearman')
            
        Returns:
            DataFrame with pairwise correlations
        """
        
        print(f"📊 Computing strategy correlations using {method} method...")
        
        # Ensure sufficient data
        if len(strategy_returns) < self.config['min_observations']:
            print(f"⚠️ Insufficient data: {len(strategy_returns)} observations (need {self.config['min_observations']})")
            return pd.DataFrame()
        
        # Remove strategies with insufficient data
        valid_strategies = []
        for strategy in strategy_returns.columns:
            valid_data = strategy_returns[strategy].dropna()
            if len(valid_data) >= self.config['min_observations']:
                valid_strategies.append(strategy)
        
        if len(valid_strategies) < 2:
            print("⚠️ Need at least 2 valid strategies for correlation analysis")
            return pd.DataFrame()
        
        strategy_returns_clean = strategy_returns[valid_strategies]
        
        print(f"   📈 Analyzing {len(valid_strategies)} strategies")
        print(f"   📅 Time period: {len(strategy_returns_clean)} observations")
        
        correlation_records = []
        
        # Compute all pairwise correlations
        for strategy_a, strategy_b in combinations(valid_strategies, 2):
            returns_a = strategy_returns_clean[strategy_a].values
            returns_b = strategy_returns_clean[strategy_b].values
            
            # Remove NaN pairs
            valid_mask = ~(np.isnan(returns_a) | np.isnan(returns_b))
            
            if valid_mask.sum() < self.config['min_observations']:
                continue
            
            returns_a_clean = returns_a[valid_mask]
            returns_b_clean = returns_b[valid_mask]
            
            try:
                if method == 'pearson':
                    correlation, p_value = pearsonr(returns_a_clean, returns_b_clean)
                elif method == 'spearman':
                    correlation, p_value = spearmanr(returns_a_clean, returns_b_clean)
                else:
                    raise ValueError(f"Unknown correlation method: {method}")
                
                # Handle NaN results
                if np.isnan(correlation):
                    correlation = 0.0
                if np.isnan(p_value):
                    p_value = 1.0
                
                correlation_record = {
                    'strategy_a': strategy_a,
                    'strategy_b': strategy_b,
                    'correlation': float(correlation),
                    'p_value': float(p_value),
                    'observations': int(valid_mask.sum()),
                    'method': method
                }
                correlation_records.append(correlation_record)
                
            except Exception as e:
                print(f"⚠️ Error computing correlation for {strategy_a}-{strategy_b}: {e}")
                continue
        
        if correlation_records:
            correlations_df = pd.DataFrame(correlation_records)
            print(f"   ✅ Computed {len(correlation_records)} strategy correlations")
            return correlations_df
        else:
            print("   ⚠️ No valid correlations computed")
            return pd.DataFrame()
    
    def detect_redundancy_patterns(self, correlations_df: pd.DataFrame, 
                                 date: Optional[datetime] = None) -> List[RedundancyRecord]:
        """
        Detect redundancy patterns from correlation data
        
        VALIDATES REQUIREMENTS 19.2, 19.3
        
        Args:
            correlations_df: DataFrame with strategy correlations
            date: Date of analysis (default: now)
            
        Returns:
            List of redundancy records
        """
        
        if date is None:
            date = datetime.now()
        
        print(f"🔍 Detecting redundancy patterns for {date.date()}...")
        
        if correlations_df.empty:
            return []
        
        redundancy_records = []
        
        for _, row in correlations_df.iterrows():
            strategy_a = row['strategy_a']
            strategy_b = row['strategy_b']
            current_correlation = row['correlation']
            p_value = row['p_value']
            observations = row['observations']
            
            # Create strategy pair key
            pair_key = f"{min(strategy_a, strategy_b)}_{max(strategy_a, strategy_b)}"
            
            # Update correlation history
            if pair_key not in self.correlation_history:
                self.correlation_history[pair_key] = []
            
            measurement = {
                'date': date,
                'correlation': current_correlation,
                'p_value': p_value,
                'observations': observations
            }
            self.correlation_history[pair_key].append(measurement)
            
            # Keep only recent history (last 12 months)
            cutoff_date = date - timedelta(days=365)
            self.correlation_history[pair_key] = [
                m for m in self.correlation_history[pair_key] 
                if m['date'] >= cutoff_date
            ]
            
            # Calculate historical averages
            recent_correlations = [m['correlation'] for m in self.correlation_history[pair_key]]
            
            # 6-month and 12-month averages
            six_months_ago = date - timedelta(days=180)
            twelve_months_ago = date - timedelta(days=365)
            
            corr_6m = [m['correlation'] for m in self.correlation_history[pair_key] if m['date'] >= six_months_ago]
            corr_12m = [m['correlation'] for m in self.correlation_history[pair_key] if m['date'] >= twelve_months_ago]
            
            correlation_6m_avg = np.mean(corr_6m) if corr_6m else current_correlation
            correlation_12m_avg = np.mean(corr_12m) if corr_12m else current_correlation
            
            # Count months above threshold
            months_above_threshold = self._count_months_above_threshold(pair_key, date)
            
            # Determine redundancy level
            redundancy_level = self._determine_redundancy_level(current_correlation, months_above_threshold)
            
            # Generate recommendation
            recommended_action = self._generate_reallocation_recommendation(
                strategy_a, strategy_b, current_correlation, redundancy_level
            )
            
            # Create redundancy record
            redundancy_record = RedundancyRecord(
                date=date,
                strategy_a=strategy_a,
                strategy_b=strategy_b,
                correlation_current=current_correlation,
                correlation_6m_avg=correlation_6m_avg,
                correlation_12m_avg=correlation_12m_avg,
                redundancy_level=redundancy_level,
                months_above_threshold=months_above_threshold,
                statistical_significance=p_value,
                observations=observations,
                recommended_action=recommended_action
            )
            
            # Validate record
            validation_errors = redundancy_record.validate()
            if not validation_errors:
                redundancy_records.append(redundancy_record)
                
                # Update alert state
                if redundancy_level in [RedundancyLevel.HIGH, RedundancyLevel.CRITICAL]:
                    self.redundancy_alerts[pair_key] = redundancy_level
                elif pair_key in self.redundancy_alerts:
                    del self.redundancy_alerts[pair_key]
            else:
                print(f"⚠️ Redundancy record validation warnings for {pair_key}:")
                for error in validation_errors:
                    print(f"   {error}")
        
        print(f"   📊 Analyzed {len(correlations_df)} strategy pairs")
        print(f"   🔍 Found {len(redundancy_records)} redundancy patterns")
        
        # Show redundancy summary
        if redundancy_records:
            redundancy_counts = {}
            for record in redundancy_records:
                level = record.redundancy_level.value
                redundancy_counts[level] = redundancy_counts.get(level, 0) + 1
            
            print(f"   📈 Redundancy breakdown: {redundancy_counts}")
        
        return redundancy_records
    
    def _count_months_above_threshold(self, pair_key: str, current_date: datetime) -> int:
        """Count consecutive months above redundancy threshold"""
        
        if pair_key not in self.correlation_history:
            return 0
        
        history = self.correlation_history[pair_key]
        if len(history) < 2:
            return 0
        
        # Sort by date
        history_sorted = sorted(history, key=lambda x: x['date'])
        
        # Count consecutive months above threshold (working backwards)
        months_above = 0
        
        for i in range(len(history_sorted) - 1, -1, -1):
            correlation = history_sorted[i]['correlation']
            
            if abs(correlation) >= self.config['redundancy_threshold']:
                months_above += 1
            else:
                break
        
        return months_above
    
    def _determine_redundancy_level(self, correlation: float, months_above_threshold: int) -> RedundancyLevel:
        """Determine redundancy level based on correlation and duration"""
        
        abs_correlation = abs(correlation)
        
        # Critical: High correlation for extended period
        if abs_correlation >= self.config['redundancy_threshold'] and months_above_threshold >= self.config['alert_months']:
            return RedundancyLevel.CRITICAL
        
        # High: Above threshold but not for long enough
        elif abs_correlation >= self.config['redundancy_threshold']:
            return RedundancyLevel.HIGH
        
        # Moderate: Concerning but not critical
        elif abs_correlation >= 0.7:
            return RedundancyLevel.MODERATE
        
        # Low: Acceptable level
        else:
            return RedundancyLevel.LOW
    
    def _generate_reallocation_recommendation(self, strategy_a: str, strategy_b: str, 
                                           correlation: float, redundancy_level: RedundancyLevel) -> str:
        """Generate capital reallocation recommendation"""
        
        abs_correlation = abs(correlation)
        
        if redundancy_level == RedundancyLevel.CRITICAL:
            if abs_correlation >= self.config['reallocation_threshold']:
                return f"URGENT: Reduce allocation to either {strategy_a} or {strategy_b} by 50%"
            else:
                return f"HIGH PRIORITY: Reduce allocation overlap between {strategy_a} and {strategy_b}"
        
        elif redundancy_level == RedundancyLevel.HIGH:
            return f"MODERATE: Monitor {strategy_a}-{strategy_b} correlation and consider rebalancing"
        
        elif redundancy_level == RedundancyLevel.MODERATE:
            return f"LOW: Continue monitoring {strategy_a}-{strategy_b} for increasing correlation"
        
        else:
            return "No action required - strategies maintain healthy independence"
    
    def analyze_strategy_redundancy(self, strategy_returns: pd.DataFrame, 
                                  date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Analyze strategy redundancy for given returns
        
        VALIDATES REQUIREMENTS 19.1-19.8
        
        Args:
            strategy_returns: DataFrame with strategy returns
            date: Date of analysis (default: now)
            
        Returns:
            Redundancy analysis results
        """
        
        if date is None:
            date = datetime.now()
        
        print(f"🔄 ANALYZING STRATEGY REDUNDANCY - {date.date()}")
        print("=" * 60)
        
        # Compute correlations
        correlations_df = self.compute_strategy_correlations(strategy_returns)
        
        if correlations_df.empty:
            return {
                'status': 'insufficient_data',
                'date': date.isoformat(),
                'strategies_analyzed': 0,
                'redundancy_records': []
            }
        
        # Detect redundancy patterns
        redundancy_records = self.detect_redundancy_patterns(correlations_df, date)
        
        # Save results
        self._save_redundancy_records(redundancy_records)
        
        # Generate summary
        analysis_summary = {
            'status': 'success',
            'date': date.isoformat(),
            'strategies_analyzed': len(strategy_returns.columns),
            'strategy_pairs_analyzed': len(correlations_df),
            'redundancy_records': len(redundancy_records),
            'critical_redundancies': len([r for r in redundancy_records if r.redundancy_level == RedundancyLevel.CRITICAL]),
            'high_redundancies': len([r for r in redundancy_records if r.redundancy_level == RedundancyLevel.HIGH]),
            'recommendations': [r.recommended_action for r in redundancy_records if r.redundancy_level in [RedundancyLevel.HIGH, RedundancyLevel.CRITICAL]],
            'top_redundant_pairs': [
                {
                    'strategy_a': r.strategy_a,
                    'strategy_b': r.strategy_b,
                    'correlation': r.correlation_current,
                    'level': r.redundancy_level.value
                }
                for r in sorted(redundancy_records, key=lambda x: abs(x.correlation_current), reverse=True)[:5]
            ]
        }
        
        print(f"✅ REDUNDANCY ANALYSIS COMPLETE")
        print(f"   📊 Strategy pairs analyzed: {analysis_summary['strategy_pairs_analyzed']}")
        print(f"   🔍 Redundancy records: {analysis_summary['redundancy_records']}")
        print(f"   ⚠️  Critical redundancies: {analysis_summary['critical_redundancies']}")
        print(f"   📈 High redundancies: {analysis_summary['high_redundancies']}")
        
        return analysis_summary
    
    def get_redundancy_alerts(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current redundancy alerts for all strategy pairs
        
        Returns:
            Dictionary of redundancy alerts
        """
        
        alerts = {}
        
        for pair_key, redundancy_level in self.redundancy_alerts.items():
            if redundancy_level in [RedundancyLevel.HIGH, RedundancyLevel.CRITICAL]:
                # Parse pair key
                strategies = pair_key.split('_')
                strategy_a, strategy_b = strategies[0], strategies[1]
                
                # Get latest correlation
                if pair_key in self.correlation_history and self.correlation_history[pair_key]:
                    latest = self.correlation_history[pair_key][-1]
                    
                    alerts[pair_key] = {
                        'strategy_a': strategy_a,
                        'strategy_b': strategy_b,
                        'redundancy_level': redundancy_level.value,
                        'correlation_current': latest['correlation'],
                        'last_updated': latest['date'].isoformat(),
                        'description': RedundancyRecord(
                            date=latest['date'],
                            strategy_a=strategy_a,
                            strategy_b=strategy_b,
                            correlation_current=latest['correlation'],
                            correlation_6m_avg=0.0,
                            correlation_12m_avg=0.0,
                            redundancy_level=redundancy_level,
                            months_above_threshold=0,
                            statistical_significance=0.0,
                            observations=0,
                            recommended_action=""
                        ).get_redundancy_description()
                    }
        
        return alerts
    
    def _save_redundancy_records(self, redundancy_records: List[RedundancyRecord]):
        """
        Save redundancy records to parquet file
        
        VALIDATES REQUIREMENTS 19.4
        
        Args:
            redundancy_records: List of redundancy records to save
        """
        
        if not redundancy_records:
            return
        
        try:
            # Convert to DataFrame
            records_data = [record.to_dict() for record in redundancy_records]
            records_df = pd.DataFrame(records_data)
            
            # Append to existing file or create new
            file_path = os.path.join(self.redundancy_dir, "strategy_correlation.parquet")
            
            if os.path.exists(file_path):
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, records_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False)
            else:
                # Create new file
                records_df.to_parquet(file_path, index=False)
            
            print(f"   ✅ Redundancy records saved: {len(redundancy_records)} records")
            
        except Exception as e:
            print(f"❌ Failed to save redundancy records: {e}")
    
    def _load_correlation_history(self):
        """Load correlation history from file"""
        
        try:
            file_path = os.path.join(self.redundancy_dir, "strategy_correlation.parquet")
            
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                
                # Rebuild correlation history
                self.correlation_history = {}
                self.redundancy_alerts = {}
                
                for _, row in df.iterrows():
                    strategy_a = row['strategy_a']
                    strategy_b = row['strategy_b']
                    pair_key = f"{min(strategy_a, strategy_b)}_{max(strategy_a, strategy_b)}"
                    
                    if pair_key not in self.correlation_history:
                        self.correlation_history[pair_key] = []
                    
                    measurement = {
                        'date': pd.to_datetime(row['date']),
                        'correlation': row['correlation_current'],
                        'p_value': row.get('statistical_significance', 0.05),
                        'observations': row['observations']
                    }
                    self.correlation_history[pair_key].append(measurement)
                    
                    # Update latest alert level
                    redundancy_level = RedundancyLevel(row['redundancy_level'])
                    if redundancy_level in [RedundancyLevel.HIGH, RedundancyLevel.CRITICAL]:
                        self.redundancy_alerts[pair_key] = redundancy_level
                
                print(f"✅ Loaded correlation history for {len(self.correlation_history)} strategy pairs")
            
        except Exception as e:
            print(f"⚠️ Failed to load correlation history: {e}")
    
    def generate_redundancy_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive redundancy report
        
        Returns:
            Redundancy report summary
        """
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_strategy_pairs': len(self.correlation_history),
            'pairs_with_alerts': len(self.redundancy_alerts),
            'alert_summary': {},
            'pair_details': {}
        }
        
        # Count alerts by level
        for level in RedundancyLevel:
            count = len([a for a in self.redundancy_alerts.values() if a == level])
            report['alert_summary'][level.value] = count
        
        # Pair details
        for pair_key, history in self.correlation_history.items():
            if history:
                latest = history[-1]
                alert_level = self.redundancy_alerts.get(pair_key, RedundancyLevel.LOW)
                
                strategies = pair_key.split('_')
                
                report['pair_details'][pair_key] = {
                    'strategy_a': strategies[0],
                    'strategy_b': strategies[1],
                    'current_correlation': latest['correlation'],
                    'redundancy_level': alert_level.value,
                    'last_updated': latest['date'].isoformat(),
                    'history_length': len(history)
                }
        
        return report


def main():
    """Demonstrate Redundancy Monitor"""
    
    print("🔄 REDUNDANCY MONITOR - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize monitor
    monitor = RedundancyMonitor()
    
    # Create synthetic strategy returns with known correlations
    np.random.seed(42)
    n_periods = 100
    n_strategies = 5
    
    # Generate base returns
    market_factor = np.random.normal(0, 0.02, n_periods)
    
    strategy_returns = pd.DataFrame()
    
    for i in range(n_strategies):
        strategy_name = f"Strategy_{i+1}"
        
        # Create strategies with varying correlation to market
        market_beta = 0.3 + (i * 0.2)  # Betas from 0.3 to 1.1
        idiosyncratic = np.random.normal(0, 0.015, n_periods)
        
        # Add some cross-strategy correlation for demonstration
        if i > 0:
            prev_strategy = strategy_returns.iloc[:, -1]
            cross_correlation = 0.1 + (i * 0.15)  # Increasing correlation
            cross_component = cross_correlation * prev_strategy
        else:
            cross_component = 0
        
        strategy_return = market_beta * market_factor + idiosyncratic + cross_component
        strategy_returns[strategy_name] = strategy_return
    
    # Add dates
    dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='W')
    strategy_returns.index = dates
    
    print(f"📊 Generated synthetic data:")
    print(f"   Strategies: {n_strategies}")
    print(f"   Periods: {n_periods}")
    print(f"   Date range: {dates[0].date()} to {dates[-1].date()}")
    
    # Analyze redundancy
    analysis_result = monitor.analyze_strategy_redundancy(strategy_returns)
    
    print(f"\n🔍 Redundancy Analysis Results:")
    print(f"   Status: {analysis_result['status']}")
    print(f"   Strategy pairs analyzed: {analysis_result['strategy_pairs_analyzed']}")
    print(f"   Redundancy records: {analysis_result['redundancy_records']}")
    print(f"   Critical redundancies: {analysis_result['critical_redundancies']}")
    print(f"   High redundancies: {analysis_result['high_redundancies']}")
    
    # Show top redundant pairs
    if analysis_result['top_redundant_pairs']:
        print(f"\n📈 Top Redundant Pairs:")
        for pair in analysis_result['top_redundant_pairs'][:3]:
            print(f"   {pair['strategy_a']} - {pair['strategy_b']}: {pair['correlation']:.3f} ({pair['level']})")
    
    # Show recommendations
    if analysis_result['recommendations']:
        print(f"\n💡 Recommendations:")
        for rec in analysis_result['recommendations'][:3]:
            print(f"   {rec}")
    
    # Get alerts
    alerts = monitor.get_redundancy_alerts()
    print(f"\n⚠️  Active Alerts: {len(alerts)}")
    for pair_key, alert in alerts.items():
        print(f"   {alert['strategy_a']}-{alert['strategy_b']}: {alert['redundancy_level']} ({alert['correlation_current']:.3f})")
    
    # Generate report
    report = monitor.generate_redundancy_report()
    print(f"\n📋 Redundancy Report Summary:")
    print(f"   Total strategy pairs: {report['total_strategy_pairs']}")
    print(f"   Pairs with alerts: {report['pairs_with_alerts']}")
    print(f"   Alert breakdown: {report['alert_summary']}")
    
    print("\n✅ Redundancy Monitor demonstration complete")


if __name__ == "__main__":
    main()