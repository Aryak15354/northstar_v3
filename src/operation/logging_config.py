"""
Logging configuration for the Northstar V3 Operation System.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


def setup_operation_logging(
    log_level: str = "INFO",
    log_dir: str = "logs/operation",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up comprehensive logging for operation system.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        max_bytes: Maximum size of each log file
        backup_count: Number of backup log files to keep
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("northstar_operation")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # File handler for all logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "operation.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Separate file handler for errors
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "operation_errors.log",
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # Daily file handler for operation tracking
    daily_handler = logging.handlers.TimedRotatingFileHandler(
        log_path / "operation_daily.log",
        when='midnight',
        interval=1,
        backupCount=30  # Keep 30 days
    )
    daily_handler.setLevel(logging.INFO)
    daily_handler.setFormatter(detailed_formatter)
    logger.addHandler(daily_handler)
    
    logger.info("Operation logging system initialized")
    return logger


def get_operation_logger() -> logging.Logger:
    """Get the operation logger instance."""
    return logging.getLogger("northstar_operation")


class OperationLogFilter(logging.Filter):
    """Custom log filter for operation-specific logging."""
    
    def __init__(self, operation_id: str = None):
        super().__init__()
        self.operation_id = operation_id
    
    def filter(self, record):
        """Add operation ID to log records."""
        if self.operation_id:
            record.operation_id = self.operation_id
        return True


class PerformanceLogger:
    """Logger for performance metrics and timing."""
    
    def __init__(self):
        self.logger = logging.getLogger("northstar_operation.performance")
        
        # Create performance-specific handler
        log_path = Path("logs/operation")
        log_path.mkdir(parents=True, exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            log_path / "performance.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - PERF - %(message)s'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_operation_timing(self, operation_type: str, duration_seconds: float, **kwargs):
        """Log operation timing information."""
        details = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(f"{operation_type} completed in {duration_seconds:.2f}s - {details}")
    
    def log_performance_metric(self, metric_name: str, value: float, **context):
        """Log performance metric."""
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        self.logger.info(f"METRIC: {metric_name}={value:.4f} - {context_str}")


class AlertLogger:
    """Logger for system alerts and notifications."""
    
    def __init__(self):
        self.logger = logging.getLogger("northstar_operation.alerts")
        
        # Create alert-specific handler
        log_path = Path("logs/operation")
        log_path.mkdir(parents=True, exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            log_path / "alerts.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=10
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - ALERT - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_alert(self, level: str, component: str, message: str, **details):
        """Log system alert."""
        details_str = ", ".join(f"{k}={v}" for k, v in details.items())
        log_message = f"[{component}] {message} - {details_str}"
        
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, log_message)