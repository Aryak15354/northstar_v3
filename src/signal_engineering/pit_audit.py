"""
Point-in-Time (PIT) Audit Framework

Ensures no future information leaks into historical analysis through rigorous
timestamp management, safety buffers, and audit logging.

Key components:
- PITTimestampManager: Applies safety buffers and validates timestamps
- PITAuditEntry: Data model for audit log entries
- PITAuditLog: Database for tracking all PIT validations
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
import numpy as np
from pathlib import Path
import json

from .config import PITSafetyBuffers


@dataclass
class PITAuditEntry:
    """Audit log entry for PIT validation
    
    Tracks all information needed to verify PIT compliance for a feature.
    """
    feature_name: str
    data_source: str
    timestamp_field: str
    public_availability_date: str
    regulatory_reference: str
    safety_buffer_days: int
    leakage_test_ic_ratio: float
    pit_validated: bool
    validation_date: datetime
    validator: str = "PITTimestampManager"
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'feature_name': self.feature_name,
            'data_source': self.data_source,
            'timestamp_field': self.timestamp_field,
            'public_availability_date': self.public_availability_date,
            'regulatory_reference': self.regulatory_reference,
            'safety_buffer_days': self.safety_buffer_days,
            'leakage_test_ic_ratio': self.leakage_test_ic_ratio,
            'pit_validated': self.pit_validated,
            'validation_date': self.validation_date.isoformat(),
            'validator': self.validator,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PITAuditEntry":
        """Create from dictionary"""
        data['validation_date'] = datetime.fromisoformat(data['validation_date'])
        return cls(**data)


class PITTimestampManager:
    """Manages point-in-time timestamp validation and safety buffer application
    
    Ensures all feature timestamps respect regulatory disclosure timelines
    and data aggregator delays.
    """
    
    def __init__(self, safety_buffers: Optional[PITSafetyBuffers] = None):
        """Initialize with safety buffer configuration
        
        Args:
            safety_buffers: Configuration for safety buffers by data type
        """
        self.safety_buffers = safety_buffers or PITSafetyBuffers()
        self.trading_calendar = None  # Will be loaded from NSE calendar
    
    def apply_safety_buffer(
        self, 
        data: pd.DataFrame, 
        data_type: str,
        timestamp_col: str = 'date'
    ) -> pd.DataFrame:
        """Apply safety buffer to timestamps based on data type
        
        Args:
            data: DataFrame with timestamp column
            data_type: Type of data (e.g., 'quarterly_financials', 'bulk_deals')
            timestamp_col: Name of timestamp column
            
        Returns:
            DataFrame with adjusted timestamps
            
        Raises:
            ValueError: If timestamp column not found or contains future dates
        """
        if timestamp_col not in data.columns:
            raise ValueError(f"Timestamp column '{timestamp_col}' not found in data")
        
        # Get safety buffer for data type
        buffer_days = self.safety_buffers.get_buffer(data_type)
        
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(data[timestamp_col]):
            data[timestamp_col] = pd.to_datetime(data[timestamp_col])
        
        # Apply buffer (shift timestamps forward)
        data = data.copy()
        data[timestamp_col] = data[timestamp_col] + pd.Timedelta(days=buffer_days)
        
        # Validate no future timestamps
        if not self.validate_timestamps(data, timestamp_col):
            raise ValueError(f"Data contains future timestamps after applying {buffer_days}-day buffer")
        
        return data
    
    def validate_timestamps(
        self, 
        data: pd.DataFrame, 
        timestamp_col: str = 'date'
    ) -> bool:
        """Validate that all timestamps are in the past
        
        Args:
            data: DataFrame with timestamp column
            timestamp_col: Name of timestamp column
            
        Returns:
            True if all timestamps are in the past, False otherwise
        """
        if timestamp_col not in data.columns:
            return False
        
        # Convert to datetime if needed
        timestamps = pd.to_datetime(data[timestamp_col])
        
        # Check all timestamps are in the past
        now = pd.Timestamp.now()
        return (timestamps <= now).all()
    
    def align_to_trading_calendar(
        self, 
        data: pd.DataFrame,
        timestamp_col: str = 'date'
    ) -> pd.DataFrame:
        """Align timestamps to NSE trading calendar
        
        Shifts timestamps to next trading day if they fall on non-trading days.
        
        Args:
            data: DataFrame with timestamp column
            timestamp_col: Name of timestamp column
            
        Returns:
            DataFrame with aligned timestamps
        """
        # TODO: Load NSE trading calendar
        # For now, just ensure timestamps are business days
        data = data.copy()
        
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(data[timestamp_col]):
            data[timestamp_col] = pd.to_datetime(data[timestamp_col])
        
        # Shift to next business day if weekend
        # This is a simplified version - full implementation would use NSE calendar
        data[timestamp_col] = data[timestamp_col].apply(
            lambda x: x + pd.offsets.BDay(0) if pd.notnull(x) else x
        )
        
        return data
    
    def get_effective_date(
        self,
        announcement_date: pd.Timestamp,
        data_type: str
    ) -> pd.Timestamp:
        """Get effective date after applying safety buffer
        
        Args:
            announcement_date: Original announcement/filing date
            data_type: Type of data for buffer lookup
            
        Returns:
            Effective date after buffer application
        """
        buffer_days = self.safety_buffers.get_buffer(data_type)
        effective_date = announcement_date + pd.Timedelta(days=buffer_days)
        
        # Align to trading calendar
        effective_date = effective_date + pd.offsets.BDay(0)
        
        return effective_date


class PITAuditLog:
    """Database for PIT audit entries
    
    Maintains complete audit trail of all PIT validations.
    """
    
    def __init__(self, log_path: Optional[Path] = None):
        """Initialize audit log
        
        Args:
            log_path: Path to JSON file for persistent storage
        """
        self.log_path = log_path or Path("data/pit_audit_log.json")
        self.entries: List[PITAuditEntry] = []
        
        # Load existing entries if file exists
        if self.log_path.exists():
            self.load()
    
    def add_entry(self, entry: PITAuditEntry) -> None:
        """Add audit entry to log
        
        Args:
            entry: PITAuditEntry to add
        """
        self.entries.append(entry)
        self.save()
    
    def get_entry(self, feature_name: str) -> Optional[PITAuditEntry]:
        """Get audit entry for feature
        
        Args:
            feature_name: Name of feature
            
        Returns:
            PITAuditEntry if found, None otherwise
        """
        for entry in self.entries:
            if entry.feature_name == feature_name:
                return entry
        return None
    
    def get_all_entries(self) -> List[PITAuditEntry]:
        """Get all audit entries
        
        Returns:
            List of all PITAuditEntry objects
        """
        return self.entries
    
    def get_validated_features(self) -> List[str]:
        """Get list of validated feature names
        
        Returns:
            List of feature names that passed PIT validation
        """
        return [
            entry.feature_name 
            for entry in self.entries 
            if entry.pit_validated
        ]
    
    def get_failed_features(self) -> List[str]:
        """Get list of features that failed PIT validation
        
        Returns:
            List of feature names that failed PIT validation
        """
        return [
            entry.feature_name 
            for entry in self.entries 
            if not entry.pit_validated
        ]
    
    def save(self) -> None:
        """Save audit log to file"""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'entries': [entry.to_dict() for entry in self.entries],
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.log_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self) -> None:
        """Load audit log from file"""
        if not self.log_path.exists():
            return
        
        with open(self.log_path, 'r') as f:
            data = json.load(f)
        
        self.entries = [
            PITAuditEntry.from_dict(entry_data) 
            for entry_data in data.get('entries', [])
        ]
    
    def generate_report(self) -> Dict:
        """Generate summary report of audit log
        
        Returns:
            Dictionary with audit statistics
        """
        total = len(self.entries)
        validated = len(self.get_validated_features())
        failed = len(self.get_failed_features())
        
        return {
            'total_features': total,
            'validated_features': validated,
            'failed_features': failed,
            'validation_rate': validated / total if total > 0 else 0.0,
            'last_updated': datetime.now().isoformat()
        }


def create_pit_audit_entry(
    feature_name: str,
    data_source: str,
    data_type: str,
    leakage_ic_ratio: float,
    safety_buffers: Optional[PITSafetyBuffers] = None
) -> PITAuditEntry:
    """Helper function to create PIT audit entry
    
    Args:
        feature_name: Name of feature
        data_source: Source of data (e.g., 'Screener', 'NSE')
        data_type: Type of data for buffer lookup
        leakage_ic_ratio: IC ratio from leakage test
        safety_buffers: Safety buffer configuration
        
    Returns:
        PITAuditEntry with validation results
    """
    buffers = safety_buffers or PITSafetyBuffers()
    buffer_days = buffers.get_buffer(data_type)
    
    # Determine if validated (IC ratio < 1.20)
    pit_validated = leakage_ic_ratio < 1.20
    
    # Map data types to regulatory references
    regulatory_refs = {
        'quarterly_financials': 'SEBI LODR Regulation 33 - Quarterly Results',
        'annual_financials': 'SEBI LODR Regulation 33 - Annual Results',
        'earnings_announcements': 'SEBI LODR Regulation 30 - Material Events',
        'bulk_deals': 'SEBI LODR Regulation 29 - Bulk Deals',
        'shareholding': 'SEBI LODR Regulation 31 - Shareholding Pattern',
        'price_data': 'NSE/BSE EOD Data',
        'analyst_estimates': 'Third-party data provider'
    }
    
    return PITAuditEntry(
        feature_name=feature_name,
        data_source=data_source,
        timestamp_field='date',
        public_availability_date=f'{data_type} announcement date',
        regulatory_reference=regulatory_refs.get(data_type, 'Unknown'),
        safety_buffer_days=buffer_days,
        leakage_test_ic_ratio=leakage_ic_ratio,
        pit_validated=pit_validated,
        validation_date=datetime.now(),
        notes=f'Leakage IC ratio: {leakage_ic_ratio:.4f}'
    )
