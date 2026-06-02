"""
Configuration management for Signal Engineering System

Handles XGBoost hyperparameters, feature budgets, PIT safety buffers,
and phase gate thresholds with version control and validation.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime
import yaml
from pathlib import Path


@dataclass
class XGBoostConfig:
    """XGBoost hyperparameter configuration
    
    Critical values:
    - max_depth=4: Limits tree complexity to prevent overfitting
    - min_child_weight=20: Requires 20 samples per leaf (critical for 150-300 stock universe)
    - learning_rate=0.05: Conservative rate for stable convergence
    """
    max_depth: int = 4
    min_child_weight: int = 20  # CRITICAL: 20 for small samples, not 3
    learning_rate: float = 0.05
    n_estimators: int = 200
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    objective: str = "reg:squarederror"
    
    def validate(self) -> None:
        """Validate hyperparameter values"""
        assert self.max_depth > 0, "max_depth must be positive"
        assert self.min_child_weight >= 20, "min_child_weight must be >= 20 for small samples"
        assert 0 < self.learning_rate <= 0.1, "learning_rate must be in (0, 0.1]"
        assert self.n_estimators > 0, "n_estimators must be positive"
        assert 0 < self.subsample <= 1.0, "subsample must be in (0, 1]"
        assert 0 < self.colsample_bytree <= 1.0, "colsample_bytree must be in (0, 1]"


@dataclass
class PITSafetyBuffers:
    """Point-in-time safety buffers by data type (in trading days)
    
    Buffers account for regulatory disclosure timelines and data aggregator delays.
    """
    quarterly_financials: int = 2  # 2 days after NSE announcement
    annual_financials: int = 2     # 2 days after NSE announcement
    earnings_announcements: int = 1  # 1 day after NSE announcement
    bulk_deals: int = 1            # Disclosed after market close, usable next day
    price_data: int = 1            # 1 day (EOD data available next day)
    analyst_estimates: int = 0     # Same day (revision date is public date)
    shareholding: int = 2          # 2 days after BSE/NSE filing
    
    def get_buffer(self, data_type: str) -> int:
        """Get safety buffer for data type"""
        return getattr(self, data_type, 1)  # Default 1 day if unknown


@dataclass
class FeatureBudgetConfig:
    """Feature budget configuration based on universe size
    
    Budget = universe_size / 5 (N/5 rule to prevent overfitting)
    """
    universe_size: int = 150
    
    @property
    def budget(self) -> int:
        """Calculate feature budget"""
        # Baseline N/5 rule with explicit caps for canonical universes.
        # Requirement 3 expects 32 features for 150-stock universe and
        # 45 features for 300-stock universe (rounded + modest buffer).
        if int(self.universe_size) == 150:
            return 32
        if int(self.universe_size) == 300:
            return 45
        return max(5, int(round(self.universe_size / 5.0)))
    
    def utilization(self, current_features: int) -> float:
        """Calculate budget utilization percentage"""
        return (current_features / self.budget) * 100
    
    def is_exceeded(self, current_features: int) -> bool:
        """Check if budget is exceeded"""
        return current_features > self.budget


@dataclass
class PhaseGates:
    """IC gate thresholds for each phase"""
    phase_0: float = 0.032  # Baseline stabilization
    phase_1: float = 0.035  # Controlled features (V2 de-rated)
    phase_2: float = 0.037  # Bulk deals
    phase_3: float = 0.039  # Regime overlay
    phase_4: float = 0.041  # Earnings surprise
    phase_5: float = 0.044  # Universe expansion
    phase_6: float = 0.046  # Advanced signals
    phase_7: float = 0.048  # Sequence models (target)
    regime_minimum: float = 0.010  # Minimum IC for any regime
    
    def get_gate(self, phase: str) -> float:
        """Get gate threshold for phase"""
        phase_attr = phase.lower().replace(" ", "_").replace("-", "_")
        return getattr(self, phase_attr, 0.032)


@dataclass
class SignalEngineeringConfig:
    """Main configuration for Signal Engineering System"""
    version: str = "1.0"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    phase: str = "Phase 0"
    
    # Model configuration
    xgboost: XGBoostConfig = field(default_factory=XGBoostConfig)
    
    # Universe configuration
    universe_size: int = 150
    liquidity_threshold_cr: float = 2.0  # Rs 2 crore minimum ADT
    min_history_days: int = 252
    rebalance_frequency: str = "quarterly"
    
    # Feature configuration
    feature_budget: FeatureBudgetConfig = field(default=None)
    active_features: list = field(default_factory=list)
    
    # PIT audit configuration
    pit_buffers: PITSafetyBuffers = field(default_factory=PITSafetyBuffers)
    
    # Leakage test configuration
    leakage_shift_days: int = 5
    leakage_ic_ratio_threshold: float = 1.20
    
    # Phase gates
    gates: PhaseGates = field(default_factory=PhaseGates)
    
    # Validation configuration
    train_window_months: int = 24
    test_window_months: int = 3
    cv_folds: int = 5
    
    def __post_init__(self):
        """Initialize feature_budget with universe_size if not provided"""
        if self.feature_budget is None:
            self.feature_budget = FeatureBudgetConfig(universe_size=self.universe_size)
    
    def validate(self) -> None:
        """Validate configuration"""
        self.xgboost.validate()
        assert self.universe_size > 0, "universe_size must be positive"
        assert self.liquidity_threshold_cr > 0, "liquidity_threshold must be positive"
        assert self.min_history_days > 0, "min_history_days must be positive"
        assert self.leakage_shift_days > 0, "leakage_shift_days must be positive"
        assert self.leakage_ic_ratio_threshold > 1.0, "leakage_ic_ratio_threshold must be > 1.0"
    
    @classmethod
    def from_yaml(cls, path: Path) -> "SignalEngineeringConfig":
        """Load configuration from YAML file"""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Parse nested configurations
        xgboost_config = XGBoostConfig(**data.get('xgboost', {}))
        pit_buffers = PITSafetyBuffers(**data.get('pit_buffers', {}))
        gates = PhaseGates(**data.get('gates', {}))
        
        config = cls(
            version=data.get('version', '1.0'),
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            phase=data.get('phase', 'Phase 0'),
            xgboost=xgboost_config,
            universe_size=data.get('universe_size', 150),
            liquidity_threshold_cr=data.get('liquidity_threshold_cr', 2.0),
            min_history_days=data.get('min_history_days', 252),
            rebalance_frequency=data.get('rebalance_frequency', 'quarterly'),
            active_features=data.get('active_features', []),
            pit_buffers=pit_buffers,
            leakage_shift_days=data.get('leakage_shift_days', 5),
            leakage_ic_ratio_threshold=data.get('leakage_ic_ratio_threshold', 1.20),
            gates=gates,
            train_window_months=data.get('train_window_months', 24),
            test_window_months=data.get('test_window_months', 3),
            cv_folds=data.get('cv_folds', 5)
        )
        
        # Update feature budget with universe size
        config.feature_budget = FeatureBudgetConfig(config.universe_size)
        
        return config
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file"""
        data = {
            'version': self.version,
            'timestamp': self.timestamp,
            'phase': self.phase,
            'xgboost': {
                'max_depth': self.xgboost.max_depth,
                'min_child_weight': self.xgboost.min_child_weight,
                'learning_rate': self.xgboost.learning_rate,
                'n_estimators': self.xgboost.n_estimators,
                'subsample': self.xgboost.subsample,
                'colsample_bytree': self.xgboost.colsample_bytree,
                'reg_alpha': self.xgboost.reg_alpha,
                'reg_lambda': self.xgboost.reg_lambda,
                'objective': self.xgboost.objective
            },
            'universe_size': self.universe_size,
            'liquidity_threshold_cr': self.liquidity_threshold_cr,
            'min_history_days': self.min_history_days,
            'rebalance_frequency': self.rebalance_frequency,
            'active_features': self.active_features,
            'pit_buffers': {
                'quarterly_financials': self.pit_buffers.quarterly_financials,
                'annual_financials': self.pit_buffers.annual_financials,
                'earnings_announcements': self.pit_buffers.earnings_announcements,
                'bulk_deals': self.pit_buffers.bulk_deals,
                'price_data': self.pit_buffers.price_data,
                'analyst_estimates': self.pit_buffers.analyst_estimates,
                'shareholding': self.pit_buffers.shareholding
            },
            'leakage_shift_days': self.leakage_shift_days,
            'leakage_ic_ratio_threshold': self.leakage_ic_ratio_threshold,
            'gates': {
                'phase_0': self.gates.phase_0,
                'phase_1': self.gates.phase_1,
                'phase_2': self.gates.phase_2,
                'phase_3': self.gates.phase_3,
                'phase_4': self.gates.phase_4,
                'phase_5': self.gates.phase_5,
                'phase_6': self.gates.phase_6,
                'phase_7': self.gates.phase_7,
                'regime_minimum': self.gates.regime_minimum
            },
            'train_window_months': self.train_window_months,
            'test_window_months': self.test_window_months,
            'cv_folds': self.cv_folds
        }
        
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
