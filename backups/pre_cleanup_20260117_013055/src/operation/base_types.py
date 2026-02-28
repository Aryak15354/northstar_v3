"""
Base types and data models for the Northstar V3 Comprehensive Operation System.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import numpy as np


class OperationStatus(Enum):
    """Status of an operation."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class LiveOperationStatus(Enum):
    """Live operation status levels."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class MarketDataStatus(Enum):
    """Market data connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class Alert:
    """Alert information."""
    timestamp: datetime
    level: AlertLevel
    component: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


@dataclass
class RiskBreach:
    """Risk limit breach information."""
    timestamp: datetime
    limit_type: str
    limit_value: float
    actual_value: float
    severity: str
    component: str


@dataclass
class SignalExecutionResult:
    """Result of signal execution."""
    signal_id: str
    execution_time: datetime
    status: str  # "executed", "rejected", "error"
    execution_price: Optional[float] = None
    executed_quantity: Optional[int] = None
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None
    risk_compliance: bool = False
    execution_latency_ms: float = 0.0
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    """Result of a system operation."""
    operation_id: str
    operation_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: OperationStatus = OperationStatus.NOT_STARTED
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    validation_results: Dict[str, bool] = field(default_factory=dict)
    alerts_generated: List[Alert] = field(default_factory=list)
    report_path: Optional[str] = None
    diagnostic_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate operation duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class CrisisValidationResult:
    """Result of crisis period validation."""
    crisis_period: str
    start_date: datetime
    end_date: datetime
    total_return: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    var_breach_count: int
    risk_limit_breaches: List[RiskBreach] = field(default_factory=list)
    recovery_time_days: int = 0
    stress_test_passed: bool = False
    additional_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class AlphaValidationResult:
    """Result of alpha validation across market regimes."""
    regime: str
    period_start: datetime
    period_end: datetime
    alpha_generated: float
    information_ratio: float
    hit_rate: float
    signal_quality_score: float
    consistency_score: float
    regime_adaptation_score: float
    validation_passed: bool
    signal_count: int = 0
    additional_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class SystemHealthStatus:
    """Current system health status."""
    timestamp: datetime
    overall_health: HealthStatus
    component_status: Dict[str, str] = field(default_factory=dict)
    performance_score: float = 0.0
    data_quality_score: float = 0.0
    latency_metrics: Dict[str, float] = field(default_factory=dict)
    error_counts: Dict[str, int] = field(default_factory=dict)
    alert_level: AlertLevel = AlertLevel.INFO
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class CrisisPeriod:
    """Definition of a crisis period for testing."""
    name: str
    start_date: datetime
    end_date: datetime
    severity: str
    characteristics: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ValidationScenario:
    """Definition of a validation scenario."""
    name: str
    scenario_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcomes: Dict[str, Any] = field(default_factory=dict)
    timeout_minutes: int = 60


@dataclass
class AlertConfig:
    """Configuration for alert handling."""
    email_recipients: List[str] = field(default_factory=list)
    slack_webhook: Optional[str] = None
    alert_thresholds: Dict[str, float] = field(default_factory=dict)
    escalation_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    output_directory: str = "reports/operation"
    report_formats: List[str] = field(default_factory=lambda: ["html", "pdf", "json"])
    include_charts: bool = True
    chart_style: str = "professional"
    auto_email: bool = False
    email_recipients: List[str] = field(default_factory=list)


@dataclass
class OperationConfig:
    """Main configuration for operation system."""
    crisis_periods: List[CrisisPeriod] = field(default_factory=list)
    validation_scenarios: List[ValidationScenario] = field(default_factory=list)
    performance_thresholds: Dict[str, float] = field(default_factory=dict)
    alert_settings: AlertConfig = field(default_factory=AlertConfig)
    reporting_config: ReportConfig = field(default_factory=ReportConfig)
    
    # System settings
    max_concurrent_operations: int = 3
    operation_timeout_hours: int = 24
    data_retention_days: int = 365
    enable_real_time_monitoring: bool = True
    
    # Performance thresholds
    min_sharpe_ratio: float = 0.5
    max_drawdown_threshold: float = 0.15
    min_information_ratio: float = 0.3
    max_var_breaches: int = 5
    
    # Live operation settings
    max_processing_latency_ms: float = 100.0
    max_execution_latency_ms: float = 500.0
    monitoring_interval_seconds: int = 30
    max_position_size: int = 10000
    restricted_symbols: List[str] = field(default_factory=list)
    allowed_signal_types: List[str] = field(default_factory=lambda: ["buy", "sell", "hold"])
    
    def __post_init__(self):
        """Initialize default crisis periods if none provided."""
        if not self.crisis_periods:
            self.crisis_periods = self._get_default_crisis_periods()
        
        if not self.performance_thresholds:
            self.performance_thresholds = self._get_default_thresholds()
    
    def _get_default_crisis_periods(self) -> List[CrisisPeriod]:
        """Get default crisis periods for testing."""
        return [
            CrisisPeriod(
                name="2008_financial_crisis",
                start_date=datetime(2007, 10, 1),
                end_date=datetime(2009, 3, 31),
                severity="extreme",
                characteristics=["credit_crunch", "liquidity_crisis", "volatility_spike"],
                description="Global financial crisis triggered by subprime mortgage collapse"
            ),
            CrisisPeriod(
                name="2020_covid_crash",
                start_date=datetime(2020, 2, 1),
                end_date=datetime(2020, 5, 31),
                severity="extreme",
                characteristics=["pandemic_shock", "circuit_breakers", "policy_response"],
                description="COVID-19 pandemic market crash and recovery"
            ),
            CrisisPeriod(
                name="2000_dotcom_bubble",
                start_date=datetime(2000, 3, 1),
                end_date=datetime(2002, 10, 31),
                severity="high",
                characteristics=["tech_bubble", "valuation_reset", "recession"],
                description="Dot-com bubble burst and subsequent recession"
            )
        ]
    
    def _get_default_thresholds(self) -> Dict[str, float]:
        """Get default performance thresholds."""
        return {
            "min_sharpe_ratio": self.min_sharpe_ratio,
            "max_drawdown": self.max_drawdown_threshold,
            "min_information_ratio": self.min_information_ratio,
            "max_var_breaches": float(self.max_var_breaches),
            "min_hit_rate": 0.52,
            "min_signal_quality": 0.6,
            "max_latency_ms": 100.0,
            "min_data_quality": 0.95
        }


@dataclass
class BacktestConfig:
    """Configuration for backtesting operations."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1000000.0
    rebalance_frequency: str = "weekly"
    benchmark: str = "NIFTY50"
    risk_free_rate: float = 0.06  # 6% risk-free rate
    validation_metrics: List[str] = field(default_factory=lambda: [
        "total_return", "sharpe_ratio", "max_drawdown", "volatility",
        "information_ratio", "tracking_error", "var_95"
    ])
    
    # Transaction cost settings
    transaction_cost_bps: float = 10.0  # 10 basis points
    market_impact_model: str = "linear"
    
    # Risk settings
    max_position_size: float = 0.05  # 5% max position
    max_sector_exposure: float = 0.20  # 20% max sector
    var_confidence: float = 0.95
    
    def validate(self) -> bool:
        """Validate backtest configuration."""
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        
        if not (0 < self.max_position_size <= 1):
            raise ValueError("Max position size must be between 0 and 1")
        
        return True


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward analysis."""
    training_window: int = 24  # months
    testing_window: int = 6   # months
    step_size: int = 3       # months
    optimization_metric: str = "sharpe_ratio"
    reoptimization_frequency: str = "quarterly"
    minimum_observations: int = 252  # trading days
    
    # Optimization settings
    max_iterations: int = 100
    convergence_tolerance: float = 1e-6
    parameter_bounds: Dict[str, tuple] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate walk-forward configuration."""
        if self.training_window <= 0:
            raise ValueError("Training window must be positive")
        
        if self.testing_window <= 0:
            raise ValueError("Testing window must be positive")
        
        if self.step_size <= 0:
            raise ValueError("Step size must be positive")
        
        if self.minimum_observations <= 0:
            raise ValueError("Minimum observations must be positive")
        
        return True


@dataclass
class PerformanceMetrics:
    """Performance metrics for backtesting and analysis."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    information_ratio: float = 0.0
    alpha: float = 0.0
    beta: float = 1.0
    tracking_error: float = 0.0
    var_breach_count: int = 0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    avg_exposure: float = 0.0
    avg_positions: float = 0.0
    avg_turnover: float = 0.0
    
    # Additional metrics
    sortino_ratio: float = 0.0
    upside_capture: float = 0.0
    downside_capture: float = 0.0
    tail_ratio: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0


@dataclass
class BacktestResult:
    """Result of a backtest execution."""
    engine_name: str
    start_date: datetime
    end_date: datetime
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    information_ratio: float
    alpha: float
    beta: float
    tracking_error: float
    var_breach_count: int
    validation_passed: bool
    performance_data: List[Dict[str, Any]] = field(default_factory=list)
    additional_metrics: Dict[str, float] = field(default_factory=dict)
    
    @property
    def duration_days(self) -> int:
        """Calculate backtest duration in days."""
        return (self.end_date - self.start_date).days
    
    @property
    def calmar_ratio(self) -> float:
        """Calculate Calmar ratio."""
        return self.annualized_return / abs(self.max_drawdown) if self.max_drawdown < 0 else np.inf


@dataclass
class StressTestScenario:
    """Definition of a stress test scenario."""
    name: str
    description: str
    duration_minutes: int
    severity: str  # "low", "medium", "high", "extreme", "critical"
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_impacts: List[str] = field(default_factory=list)
    risk_thresholds: Dict[str, float] = field(default_factory=dict)


@dataclass
class StressTestResult:
    """Result of a stress test execution."""
    test_id: str
    scenario_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    test_passed: bool = False
    duration_seconds: float = 0.0
    scenario_parameters: Dict[str, Any] = field(default_factory=dict)
    expected_impacts: List[str] = field(default_factory=list)
    performance_impact: Dict[str, Any] = field(default_factory=dict)
    system_behavior: Dict[str, Any] = field(default_factory=dict)
    risk_limit_validation: Dict[str, Any] = field(default_factory=dict)
    recovery_required: bool = False
    recovery_procedures_executed: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None
    error_message: Optional[str] = None
    alerts_generated: List[Alert] = field(default_factory=list)


@dataclass
class StressTestConfig:
    """Configuration for stress testing system."""
    # Test execution settings
    max_concurrent_tests: int = 3
    test_timeout_minutes: int = 60
    enable_recovery_procedures: bool = True
    
    # Risk compliance settings
    min_risk_compliance_rate: float = 0.8
    enable_risk_limit_validation: bool = True
    
    # Scenario settings
    default_scenario_duration_minutes: int = 30
    enable_scenario_customization: bool = True
    
    # Reporting settings
    generate_detailed_reports: bool = True
    store_test_history: bool = True
    max_history_entries: int = 1000
    
    # Recovery settings
    enable_automatic_recovery: bool = True
    max_recovery_attempts: int = 3
    recovery_timeout_minutes: int = 10


@dataclass
class WalkForwardResult:
    """Result of walk-forward analysis execution."""
    analysis_id: str
    window_id: str
    training_start: datetime
    training_end: datetime
    testing_start: datetime
    testing_end: datetime
    strategies_analyzed: List[str]
    strategy_results: List[Dict[str, Any]] = field(default_factory=list)
    window_results: List[Dict[str, Any]] = field(default_factory=list)
    degradation_analysis: Dict[str, Any] = field(default_factory=dict)
    evolution_insights: Dict[str, Any] = field(default_factory=dict)
    analysis_duration_seconds: float = 0.0
    analysis_passed: bool = True
    failure_reason: Optional[str] = None


@dataclass
class StrategyEvolutionResult:
    """Result of strategy evolution analysis."""
    strategy_name: str
    analysis_period_start: datetime
    analysis_period_end: datetime
    evolution_detected: bool
    evolution_insights: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    parameter_changes: Dict[str, Any] = field(default_factory=dict)
    performance_trends: Dict[str, Any] = field(default_factory=dict)


class ComponentStatus(Enum):
    """Component status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SystemHealthLevel(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    validation_id: str
    component: str
    status: ComponentStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    execution_time_seconds: float


@dataclass
class ValidationReport:
    """Comprehensive validation report."""
    report_id: str
    timestamp: datetime
    validation_results: List[ValidationResult]
    overall_status: SystemHealthStatus
    summary: Dict[str, Any]


@dataclass
class StrategyDegradation:
    """Strategy degradation analysis result."""
    strategy_name: str
    degradation_detected: bool
    degradation_severity: str
    degradation_start_date: Optional[datetime] = None
    performance_decline_pct: float = 0.0
    statistical_significance: float = 0.0
    recommended_actions: List[str] = field(default_factory=list)
    degradation_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardWindow:
    """Walk-forward analysis window definition."""
    window_id: str
    training_start: datetime
    training_end: datetime
    testing_start: datetime
    testing_end: datetime
    training_observations: int
    testing_observations: int