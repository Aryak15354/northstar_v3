#!/usr/bin/env python3
"""
📊 OUT-OF-SAMPLE VALIDATOR - PHASE 6: ENHANCEMENT LAYER
Validate strategy performance across different time periods

This implements the out-of-sample validation requirements for Phase 6 (Enhancement)
of the institutional validation framework. It splits data into train/validate/test
periods and ensures test performance meets minimum thresholds.

CRITICAL PRINCIPLE: Temporal Validation Integrity
- Split data into train (2008-2018), validate (2019-2021), test (2022-2025)
- Compute Sharpe ratio for each period independently
- Require test Sharpe ≥ 70% of train Sharpe (degradation tolerance)
- Persist to data/validation/oos_results.parquet
- Provide robust evidence of strategy generalization

Usage:
    from src.validation.oos_validator import OOSValidator
    
    validator = OOSValidator()
    validator.validate_strategy_oos("momentum_strategy", strategy_returns)
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

warnings.filterwarnings('ignore')


class OOSResult(Enum):
    """Out-of-sample validation results"""
    PASS = "pass"           # Test performance meets threshold
    FAIL = "fail"           # Test performance below threshold
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data for validation
    ERROR = "error"         # Validation error occurred


@dataclass
class OOSValidationRecord:
    """
    Out-of-sample validation record for strategy performance
    
    Complete OOS validation information with period-specific metrics.
    """
    date: datetime
    strategy_name: str
    
    # Training period (2008-2018)
    train_start: datetime
    train_end: datetime
    train_sharpe: float
    train_return_annual: float
    train_volatility_annual: float
    train_observations: int
    
    # Validation period (2019-2021)
    validate_start: datetime
    validate_end: datetime
    validate_sharpe: float
    validate_return_annual: float
    validate_volatility_annual: float
    validate_observations: int
    
    # Test period (2022-2025)
    test_start: datetime
    test_end: datetime
    test_sharpe: float
    test_return_annual: float
    test_volatility_annual: float
    test_observations: int
    
    # Validation results
    sharpe_degradation: float  # (test_sharpe / train_sharpe) - 1
    degradation_threshold: float  # Minimum acceptable ratio (0.7)
    oos_result: OOSResult
    validation_message: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        # Convert datetime fields to ISO format
        datetime_fields = ['date', 'train_start', 'train_end', 'validate_start', 
                          'validate_end', 'test_start', 'test_end']
        for field in datetime_fields:
            if field in result:
                result[field] = result[field].isoformat()
        result['oos_result'] = result['oos_result'].value
        return result
    
    def validate(self) -> List[str]:
        """Validate OOS record"""
        errors = []
        
        # Check Sharpe ratios are finite
        if not np.isfinite(self.train_sharpe):
            errors.append("Training Sharpe ratio must be finite")
        
        if not np.isfinite(self.test_sharpe):
            errors.append("Test Sharpe ratio must be finite")
        
        # Check observation counts
        if self.train_observations < 50:
            errors.append("Insufficient training observations (need ≥50)")
        
        if self.test_observations < 20:
            errors.append("Insufficient test observations (need ≥20)")
        
        # Check period ordering
        if self.train_end >= self.validate_start:
            errors.append("Training period must end before validation period")
        
        if self.validate_end >= self.test_start:
            errors.append("Validation period must end before test period")
        
        # Check degradation calculation
        if self.train_sharpe != 0:
            expected_degradation = (self.test_sharpe / self.train_sharpe) - 1
            if abs(self.sharpe_degradation - expected_degradation) > 1e-6:
                errors.append("Sharpe degradation calculation incorrect")
        
        return errors
    
    def get_validation_summary(self) -> str:
        """Get human-readable validation summary"""
        if self.oos_result == OOSResult.PASS:
            return f"PASS: Test Sharpe ({self.test_sharpe:.3f}) meets threshold ({self.degradation_threshold:.1%} of train Sharpe {self.train_sharpe:.3f})"
        elif self.oos_result == OOSResult.FAIL:
            return f"FAIL: Test Sharpe ({self.test_sharpe:.3f}) below threshold ({self.degradation_threshold:.1%} of train Sharpe {self.train_sharpe:.3f})"
        elif self.oos_result == OOSResult.INSUFFICIENT_DATA:
            return "INSUFFICIENT DATA: Not enough observations for reliable validation"
        else:
            return f"ERROR: {self.validation_message}"


class OOSValidator:
    """
    Out-of-Sample Validator - Phase 6: Enhancement Layer
    
    Validates strategy performance across different time periods to ensure
    robustness and generalization capability.
    
    ENFORCES REQUIREMENTS:
    - 20.1-20.8: Out-of-sample validation with temporal splits
    
    V3 INTEGRATION:
    - Integrates with existing strategy performance systems
    - Provides OOS validation for strategy approval
    - Maintains temporal validation history
    """
    
    def __init__(self, base_dir: str = "data/validation"):
        """
        Initialize OOS Validator
        
        Args:
            base_dir: Base directory for validation data
        """
        self.base_dir = base_dir
        self.oos_dir = os.path.join(base_dir, "oos_validation")
        
        # Create directories
        os.makedirs(self.oos_dir, exist_ok=True)
        
        # Configuration
        self.config = {
            # Period definitions
            'train_start': datetime(2008, 1, 1),
            'train_end': datetime(2018, 12, 31),
            'validate_start': datetime(2019, 1, 1),
            'validate_end': datetime(2021, 12, 31),
            'test_start': datetime(2022, 1, 1),
            'test_end': datetime(2025, 12, 31),
            
            # Validation thresholds
            'degradation_threshold': 0.7,  # Test Sharpe ≥ 70% of train Sharpe
            'min_train_observations': 50,  # Minimum training observations
            'min_test_observations': 20,   # Minimum test observations
            'min_sharpe_threshold': 0.1,   # Minimum Sharpe for meaningful comparison
            
            # Risk-free rate (annualized)
            'risk_free_rate': 0.06,  # 6% annual risk-free rate
            
            # Calculation parameters
            'trading_days_per_year': 252,
            'weeks_per_year': 52,
        }
        
        # Validation state
        self.validation_history: Dict[str, List[OOSValidationRecord]] = {}
        
        # Load existing history
        self._load_validation_history()
        
        print("📊 OOS Validator initialized")
        print(f"   Output: {self.oos_dir}/")
        print(f"   Training period: {self.config['train_start'].year}-{self.config['train_end'].year}")
        print(f"   Validation period: {self.config['validate_start'].year}-{self.config['validate_end'].year}")
        print(f"   Test period: {self.config['test_start'].year}-{self.config['test_end'].year}")
        print(f"   Degradation threshold: {self.config['degradation_threshold']:.1%}")
    
    def split_data_by_periods(self, returns: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Split return series into train/validate/test periods
        
        VALIDATES REQUIREMENTS 20.1, 20.2
        
        Args:
            returns: Time series of returns with datetime index
            
        Returns:
            Tuple of (train_returns, validate_returns, test_returns)
        """
        
        print(f"📅 Splitting data into temporal periods...")
        
        # Ensure datetime index
        if not isinstance(returns.index, pd.DatetimeIndex):
            print("⚠️ Converting index to datetime")
            returns.index = pd.to_datetime(returns.index)
        
        # Split into periods
        train_mask = (returns.index >= self.config['train_start']) & (returns.index <= self.config['train_end'])
        validate_mask = (returns.index >= self.config['validate_start']) & (returns.index <= self.config['validate_end'])
        test_mask = (returns.index >= self.config['test_start']) & (returns.index <= self.config['test_end'])
        
        train_returns = returns[train_mask]
        validate_returns = returns[validate_mask]
        test_returns = returns[test_mask]
        
        print(f"   📈 Training: {len(train_returns)} observations ({train_returns.index.min().date()} to {train_returns.index.max().date()})")
        print(f"   📊 Validation: {len(validate_returns)} observations ({validate_returns.index.min().date()} to {validate_returns.index.max().date()})")
        print(f"   🧪 Test: {len(test_returns)} observations ({test_returns.index.min().date()} to {test_returns.index.max().date()})")
        
        return train_returns, validate_returns, test_returns
    
    def calculate_period_metrics(self, returns: pd.Series, period_name: str) -> Dict[str, float]:
        """
        Calculate performance metrics for a specific period
        
        VALIDATES REQUIREMENTS 20.3, 20.4
        
        Args:
            returns: Return series for the period
            period_name: Name of the period (for logging)
            
        Returns:
            Dictionary with performance metrics
        """
        
        if len(returns) == 0:
            return {
                'sharpe_ratio': 0.0,
                'annual_return': 0.0,
                'annual_volatility': 0.0,
                'observations': 0
            }
        
        # Remove NaN values
        clean_returns = returns.dropna()
        
        if len(clean_returns) < 5:  # Need minimum observations
            return {
                'sharpe_ratio': 0.0,
                'annual_return': 0.0,
                'annual_volatility': 0.0,
                'observations': len(clean_returns)
            }
        
        # Determine frequency for annualization
        if len(clean_returns) > 1:
            avg_days_between = (clean_returns.index[-1] - clean_returns.index[0]).days / (len(clean_returns) - 1)
            
            if avg_days_between <= 2:  # Daily data
                periods_per_year = self.config['trading_days_per_year']
            elif avg_days_between <= 8:  # Weekly data
                periods_per_year = self.config['weeks_per_year']
            else:  # Monthly or other
                periods_per_year = 12
        else:
            periods_per_year = self.config['trading_days_per_year']
        
        # Calculate metrics
        mean_return = clean_returns.mean()
        volatility = clean_returns.std()
        
        # Annualize
        annual_return = mean_return * periods_per_year
        annual_volatility = volatility * np.sqrt(periods_per_year)
        
        # Calculate Sharpe ratio
        if annual_volatility > 0:
            excess_return = annual_return - self.config['risk_free_rate']
            sharpe_ratio = excess_return / annual_volatility
        else:
            sharpe_ratio = 0.0
        
        metrics = {
            'sharpe_ratio': float(sharpe_ratio),
            'annual_return': float(annual_return),
            'annual_volatility': float(annual_volatility),
            'observations': len(clean_returns)
        }
        
        print(f"   📊 {period_name} metrics:")
        print(f"      Sharpe ratio: {metrics['sharpe_ratio']:.3f}")
        print(f"      Annual return: {metrics['annual_return']:.1%}")
        print(f"      Annual volatility: {metrics['annual_volatility']:.1%}")
        print(f"      Observations: {metrics['observations']}")
        
        return metrics
    
    def validate_oos_performance(self, train_metrics: Dict[str, float], 
                               test_metrics: Dict[str, float]) -> Tuple[OOSResult, str]:
        """
        Validate out-of-sample performance against thresholds
        
        VALIDATES REQUIREMENTS 20.5, 20.6
        
        Args:
            train_metrics: Training period metrics
            test_metrics: Test period metrics
            
        Returns:
            Tuple of (validation_result, message)
        """
        
        print(f"🧪 Validating OOS performance...")
        
        # Check data sufficiency
        if train_metrics['observations'] < self.config['min_train_observations']:
            return OOSResult.INSUFFICIENT_DATA, f"Insufficient training data: {train_metrics['observations']} < {self.config['min_train_observations']}"
        
        if test_metrics['observations'] < self.config['min_test_observations']:
            return OOSResult.INSUFFICIENT_DATA, f"Insufficient test data: {test_metrics['observations']} < {self.config['min_test_observations']}"
        
        # Check if training Sharpe is meaningful
        if abs(train_metrics['sharpe_ratio']) < self.config['min_sharpe_threshold']:
            return OOSResult.INSUFFICIENT_DATA, f"Training Sharpe too low for meaningful comparison: {train_metrics['sharpe_ratio']:.3f}"
        
        # Calculate degradation
        if train_metrics['sharpe_ratio'] != 0:
            sharpe_ratio = test_metrics['sharpe_ratio'] / train_metrics['sharpe_ratio']
        else:
            return OOSResult.ERROR, "Training Sharpe ratio is zero"
        
        # Check threshold
        threshold = self.config['degradation_threshold']
        
        if sharpe_ratio >= threshold:
            message = f"PASS: Test Sharpe ratio {sharpe_ratio:.3f} ≥ threshold {threshold:.3f}"
            result = OOSResult.PASS
        else:
            message = f"FAIL: Test Sharpe ratio {sharpe_ratio:.3f} < threshold {threshold:.3f}"
            result = OOSResult.FAIL
        
        print(f"   📊 Train Sharpe: {train_metrics['sharpe_ratio']:.3f}")
        print(f"   🧪 Test Sharpe: {test_metrics['sharpe_ratio']:.3f}")
        print(f"   📈 Ratio: {sharpe_ratio:.3f}")
        print(f"   🎯 Threshold: {threshold:.3f}")
        print(f"   ✅ Result: {result.value.upper()}")
        
        return result, message
    
    def validate_strategy_oos(self, strategy_name: str, 
                            returns: pd.Series,
                            validation_date: Optional[datetime] = None) -> OOSValidationRecord:
        """
        Validate strategy out-of-sample performance
        
        VALIDATES REQUIREMENTS 20.1-20.8
        
        Args:
            strategy_name: Name of the strategy
            returns: Time series of strategy returns
            validation_date: Date of validation (default: now)
            
        Returns:
            OOS validation record
        """
        
        if validation_date is None:
            validation_date = datetime.now()
        
        print(f"📊 VALIDATING OOS PERFORMANCE: {strategy_name}")
        print("=" * 60)
        
        try:
            # Split data into periods
            train_returns, validate_returns, test_returns = self.split_data_by_periods(returns)
            
            # Calculate metrics for each period
            train_metrics = self.calculate_period_metrics(train_returns, "Training")
            validate_metrics = self.calculate_period_metrics(validate_returns, "Validation")
            test_metrics = self.calculate_period_metrics(test_returns, "Test")
            
            # Validate OOS performance
            oos_result, validation_message = self.validate_oos_performance(train_metrics, test_metrics)
            
            # Calculate degradation
            if train_metrics['sharpe_ratio'] != 0:
                sharpe_degradation = (test_metrics['sharpe_ratio'] / train_metrics['sharpe_ratio']) - 1
            else:
                sharpe_degradation = -1.0  # Complete degradation if train Sharpe is 0
            
            # Create validation record
            validation_record = OOSValidationRecord(
                date=validation_date,
                strategy_name=strategy_name,
                
                # Training period
                train_start=self.config['train_start'],
                train_end=self.config['train_end'],
                train_sharpe=train_metrics['sharpe_ratio'],
                train_return_annual=train_metrics['annual_return'],
                train_volatility_annual=train_metrics['annual_volatility'],
                train_observations=train_metrics['observations'],
                
                # Validation period
                validate_start=self.config['validate_start'],
                validate_end=self.config['validate_end'],
                validate_sharpe=validate_metrics['sharpe_ratio'],
                validate_return_annual=validate_metrics['annual_return'],
                validate_volatility_annual=validate_metrics['annual_volatility'],
                validate_observations=validate_metrics['observations'],
                
                # Test period
                test_start=self.config['test_start'],
                test_end=self.config['test_end'],
                test_sharpe=test_metrics['sharpe_ratio'],
                test_return_annual=test_metrics['annual_return'],
                test_volatility_annual=test_metrics['annual_volatility'],
                test_observations=test_metrics['observations'],
                
                # Validation results
                sharpe_degradation=sharpe_degradation,
                degradation_threshold=self.config['degradation_threshold'],
                oos_result=oos_result,
                validation_message=validation_message
            )
            
            # Validate record
            validation_errors = validation_record.validate()
            if validation_errors:
                print(f"⚠️ Validation record warnings:")
                for error in validation_errors:
                    print(f"   {error}")
            
            # Save validation record
            self._save_validation_record(validation_record)
            
            # Update history
            if strategy_name not in self.validation_history:
                self.validation_history[strategy_name] = []
            self.validation_history[strategy_name].append(validation_record)
            
            print(f"✅ OOS VALIDATION COMPLETE: {strategy_name}")
            print(f"   📊 Result: {oos_result.value.upper()}")
            print(f"   📈 Sharpe degradation: {sharpe_degradation:.1%}")
            print(f"   💬 Message: {validation_message}")
            
            return validation_record
            
        except Exception as e:
            print(f"❌ OOS validation error: {e}")
            
            # Create error record
            error_record = OOSValidationRecord(
                date=validation_date,
                strategy_name=strategy_name,
                train_start=self.config['train_start'],
                train_end=self.config['train_end'],
                train_sharpe=0.0,
                train_return_annual=0.0,
                train_volatility_annual=0.0,
                train_observations=0,
                validate_start=self.config['validate_start'],
                validate_end=self.config['validate_end'],
                validate_sharpe=0.0,
                validate_return_annual=0.0,
                validate_volatility_annual=0.0,
                validate_observations=0,
                test_start=self.config['test_start'],
                test_end=self.config['test_end'],
                test_sharpe=0.0,
                test_return_annual=0.0,
                test_volatility_annual=0.0,
                test_observations=0,
                sharpe_degradation=0.0,
                degradation_threshold=self.config['degradation_threshold'],
                oos_result=OOSResult.ERROR,
                validation_message=str(e)
            )
            
            return error_record
    
    def get_validation_summary(self, strategy_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get validation summary for strategies
        
        Args:
            strategy_name: Specific strategy name (default: all strategies)
            
        Returns:
            Validation summary
        """
        
        if strategy_name:
            strategies = [strategy_name] if strategy_name in self.validation_history else []
        else:
            strategies = list(self.validation_history.keys())
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_strategies': len(strategies),
            'validation_results': {},
            'summary_stats': {
                'pass_count': 0,
                'fail_count': 0,
                'insufficient_data_count': 0,
                'error_count': 0
            }
        }
        
        for strategy in strategies:
            if self.validation_history[strategy]:
                latest_validation = self.validation_history[strategy][-1]
                
                summary['validation_results'][strategy] = {
                    'result': latest_validation.oos_result.value,
                    'train_sharpe': latest_validation.train_sharpe,
                    'test_sharpe': latest_validation.test_sharpe,
                    'sharpe_degradation': latest_validation.sharpe_degradation,
                    'last_validated': latest_validation.date.isoformat(),
                    'message': latest_validation.validation_message
                }
                
                # Update summary stats
                result = latest_validation.oos_result
                if result == OOSResult.PASS:
                    summary['summary_stats']['pass_count'] += 1
                elif result == OOSResult.FAIL:
                    summary['summary_stats']['fail_count'] += 1
                elif result == OOSResult.INSUFFICIENT_DATA:
                    summary['summary_stats']['insufficient_data_count'] += 1
                else:
                    summary['summary_stats']['error_count'] += 1
        
        return summary
    
    def _save_validation_record(self, validation_record: OOSValidationRecord):
        """
        Save validation record to parquet file
        
        VALIDATES REQUIREMENTS 20.7
        
        Args:
            validation_record: Validation record to save
        """
        
        try:
            # Convert to DataFrame
            record_data = validation_record.to_dict()
            record_df = pd.DataFrame([record_data])
            
            # Append to existing file or create new
            file_path = os.path.join(self.oos_dir, "oos_results.parquet")
            
            if os.path.exists(file_path):
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, record_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False)
            else:
                # Create new file
                record_df.to_parquet(file_path, index=False)
            
            print(f"   ✅ Validation record saved: {validation_record.strategy_name}")
            
        except Exception as e:
            print(f"❌ Failed to save validation record: {e}")
    
    def _load_validation_history(self):
        """Load validation history from file"""
        
        try:
            file_path = os.path.join(self.oos_dir, "oos_results.parquet")
            
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                
                # Rebuild validation history
                self.validation_history = {}
                
                for _, row in df.iterrows():
                    strategy_name = row['strategy_name']
                    
                    if strategy_name not in self.validation_history:
                        self.validation_history[strategy_name] = []
                    
                    # Reconstruct validation record
                    validation_record = OOSValidationRecord(
                        date=pd.to_datetime(row['date']),
                        strategy_name=strategy_name,
                        train_start=pd.to_datetime(row['train_start']),
                        train_end=pd.to_datetime(row['train_end']),
                        train_sharpe=row['train_sharpe'],
                        train_return_annual=row['train_return_annual'],
                        train_volatility_annual=row['train_volatility_annual'],
                        train_observations=row['train_observations'],
                        validate_start=pd.to_datetime(row['validate_start']),
                        validate_end=pd.to_datetime(row['validate_end']),
                        validate_sharpe=row['validate_sharpe'],
                        validate_return_annual=row['validate_return_annual'],
                        validate_volatility_annual=row['validate_volatility_annual'],
                        validate_observations=row['validate_observations'],
                        test_start=pd.to_datetime(row['test_start']),
                        test_end=pd.to_datetime(row['test_end']),
                        test_sharpe=row['test_sharpe'],
                        test_return_annual=row['test_return_annual'],
                        test_volatility_annual=row['test_volatility_annual'],
                        test_observations=row['test_observations'],
                        sharpe_degradation=row['sharpe_degradation'],
                        degradation_threshold=row['degradation_threshold'],
                        oos_result=OOSResult(row['oos_result']),
                        validation_message=row['validation_message']
                    )
                    
                    self.validation_history[strategy_name].append(validation_record)
                
                print(f"✅ Loaded validation history for {len(self.validation_history)} strategies")
            
        except Exception as e:
            print(f"⚠️ Failed to load validation history: {e}")


def main():
    """Demonstrate OOS Validator"""
    
    print("📊 OOS VALIDATOR - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize validator
    validator = OOSValidator()
    
    # Create synthetic strategy returns spanning multiple periods
    np.random.seed(42)
    
    # Generate returns from 2008 to 2025
    start_date = datetime(2008, 1, 1)
    end_date = datetime(2025, 12, 31)
    dates = pd.date_range(start=start_date, end=end_date, freq='W')
    
    # Create strategy with different performance in different periods
    returns_data = []
    
    for date in dates:
        if date.year <= 2018:
            # Training period: Good performance
            base_return = 0.002  # 0.2% weekly
            volatility = 0.015
        elif date.year <= 2021:
            # Validation period: Moderate performance
            base_return = 0.0015  # 0.15% weekly
            volatility = 0.018
        else:
            # Test period: Degraded but acceptable performance
            base_return = 0.0012  # 0.12% weekly (60% of training)
            volatility = 0.020
        
        # Add market noise
        market_noise = np.random.normal(0, 0.01)
        strategy_return = base_return + np.random.normal(0, volatility) + market_noise
        returns_data.append(strategy_return)
    
    strategy_returns = pd.Series(returns_data, index=dates, name="demo_strategy")
    
    print(f"📊 Generated synthetic strategy returns:")
    print(f"   Date range: {dates[0].date()} to {dates[-1].date()}")
    print(f"   Total observations: {len(strategy_returns)}")
    print(f"   Training period performance: Higher")
    print(f"   Test period performance: Degraded but acceptable")
    
    # Validate OOS performance
    validation_record = validator.validate_strategy_oos("demo_strategy", strategy_returns)
    
    print(f"\n📊 OOS Validation Results:")
    print(f"   Strategy: {validation_record.strategy_name}")
    print(f"   Result: {validation_record.oos_result.value.upper()}")
    print(f"   Training Sharpe: {validation_record.train_sharpe:.3f}")
    print(f"   Test Sharpe: {validation_record.test_sharpe:.3f}")
    print(f"   Degradation: {validation_record.sharpe_degradation:.1%}")
    print(f"   Threshold: {validation_record.degradation_threshold:.1%}")
    print(f"   Summary: {validation_record.get_validation_summary()}")
    
    # Get validation summary
    summary = validator.get_validation_summary()
    print(f"\n📋 Validation Summary:")
    print(f"   Total strategies: {summary['total_strategies']}")
    print(f"   Pass count: {summary['summary_stats']['pass_count']}")
    print(f"   Fail count: {summary['summary_stats']['fail_count']}")
    print(f"   Insufficient data: {summary['summary_stats']['insufficient_data_count']}")
    print(f"   Errors: {summary['summary_stats']['error_count']}")
    
    print("\n✅ OOS Validator demonstration complete")


if __name__ == "__main__":
    main()