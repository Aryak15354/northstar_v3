#!/usr/bin/env python3
"""
Observer Audit Log - Complete Audit Trail for Intelligence Observer

This module maintains a comprehensive audit trail of all Observer activities,
ensuring complete transparency and accountability for intelligence operations.

AUDIT PRINCIPLES:
1. Every Observer action is logged
2. All authority checks are recorded
3. Violations are permanently tracked
4. Audit trail is immutable
5. Complete reproducibility enabled
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
import warnings
warnings.filterwarnings('ignore')

@dataclass
class AuditEntry:
    """Single audit log entry"""
    entry_id: str
    timestamp: datetime
    event_type: str
    event_data: Dict[str, Any]
    source: str = "intelligence_observer"
    hash_chain: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'event_data': self.event_data,
            'source': self.source,
            'hash_chain': self.hash_chain
        }
    
    def calculate_hash(self, previous_hash: str = "") -> str:
        """Calculate hash for this entry including chain"""
        content = f"{self.entry_id}{self.timestamp.isoformat()}{self.event_type}{json.dumps(self.event_data, sort_keys=True)}{previous_hash}"
        return hashlib.sha256(content.encode()).hexdigest()

class ObserverAuditLog:
    """
    Observer Audit Log - Immutable Audit Trail
    
    This class maintains a complete, immutable audit trail of all
    Intelligence Observer activities for transparency and accountability.
    """
    
    def __init__(self):
        self.name = "Observer Audit Log"
        self.version = "1.0.0"
        
        # Audit configuration
        self.audit_config = {
            'log_directory': 'data/intelligence/observer/audit/',
            'max_entries_per_file': 1000,
            'retention_days': 365,
            'enable_hash_chain': True,
            'enable_daily_rotation': True
        }
        
        # Create audit directory
        os.makedirs(self.audit_config['log_directory'], exist_ok=True)
        
        # Audit state
        self.current_entries: List[AuditEntry] = []
        self.entry_count = 0
        self.last_hash = ""
        self.current_file_date = datetime.now().date()
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Load existing audit state
        self._load_audit_state()
        
        print(f"📋 {self.name} v{self.version} - Immutable Audit Trail Active")
        print(f"📁 Audit Directory: {self.audit_config['log_directory']}")
        print(f"🔗 Hash Chain: {'Enabled' if self.audit_config['enable_hash_chain'] else 'Disabled'}")
    
    def log_event(self, event_type: str, event_data: Dict[str, Any], 
                  source: str = "intelligence_observer") -> str:
        """
        Log an Observer event to the audit trail
        
        Args:
            event_type: Type of event being logged
            event_data: Event data dictionary
            source: Source of the event
            
        Returns:
            str: Entry ID of the logged event
        """
        
        with self.lock:
            try:
                # Create audit entry
                entry_id = f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                
                entry = AuditEntry(
                    entry_id=entry_id,
                    timestamp=datetime.now(),
                    event_type=event_type,
                    event_data=event_data.copy(),  # Defensive copy
                    source=source
                )
                
                # Calculate hash chain if enabled
                if self.audit_config['enable_hash_chain']:
                    entry.hash_chain = entry.calculate_hash(self.last_hash)
                    self.last_hash = entry.hash_chain
                
                # Add to current entries
                self.current_entries.append(entry)
                self.entry_count += 1
                
                # Check if we need to rotate files
                self._check_file_rotation()
                
                # Persist immediately for critical events
                if event_type in ['authority_violation', 'observer_suspended', 'system_error']:
                    self._persist_current_entries()
                
                return entry_id
                
            except Exception as e:
                print(f"❌ Audit logging error: {e}")
                return ""
    
    def log_authority_violation(self, violation_type: str, violation_data: Dict[str, Any]) -> str:
        """Log authority violation with high priority"""
        
        violation_event = {
            'violation_type': violation_type,
            'violation_data': violation_data,
            'severity': 'HIGH',
            'requires_review': True
        }
        
        return self.log_event('authority_violation', violation_event)
    
    def log_intelligence_output(self, output_type: str, output_data: Dict[str, Any]) -> str:
        """Log intelligence output for reproducibility"""
        
        intelligence_event = {
            'output_type': output_type,
            'output_data': output_data,
            'reproducible': True
        }
        
        return self.log_event('intelligence_output', intelligence_event)
    
    def log_system_interaction(self, interaction_type: str, interaction_data: Dict[str, Any]) -> str:
        """Log system interaction for audit trail"""
        
        interaction_event = {
            'interaction_type': interaction_type,
            'interaction_data': interaction_data,
            'authority_level': 'read_only'
        }
        
        return self.log_event('system_interaction', interaction_event)
    
    def get_audit_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get audit summary for specified period"""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Load recent entries
        recent_entries = self._load_entries_since(cutoff_date)
        
        # Calculate summary statistics
        event_types = {}
        sources = {}
        violations = 0
        
        for entry in recent_entries:
            # Count by event type
            event_types[entry.event_type] = event_types.get(entry.event_type, 0) + 1
            
            # Count by source
            sources[entry.source] = sources.get(entry.source, 0) + 1
            
            # Count violations
            if entry.event_type == 'authority_violation':
                violations += 1
        
        return {
            'period_days': days,
            'total_entries': len(recent_entries),
            'event_types': event_types,
            'sources': sources,
            'authority_violations': violations,
            'audit_integrity': self._verify_audit_integrity(recent_entries),
            'summary_generated': datetime.now().isoformat()
        }
    
    def verify_audit_integrity(self) -> Dict[str, Any]:
        """Verify integrity of audit trail"""
        
        with self.lock:
            try:
                # Load all audit files
                all_entries = self._load_all_entries()
                
                # Verify hash chain if enabled
                hash_chain_valid = True
                if self.audit_config['enable_hash_chain']:
                    hash_chain_valid = self._verify_hash_chain(all_entries)
                
                # Check for gaps in timestamps
                timestamp_gaps = self._check_timestamp_gaps(all_entries)
                
                # Verify file integrity
                file_integrity = self._verify_file_integrity()
                
                return {
                    'total_entries': len(all_entries),
                    'hash_chain_valid': hash_chain_valid,
                    'timestamp_gaps': timestamp_gaps,
                    'file_integrity': file_integrity,
                    'verification_time': datetime.now().isoformat()
                }
                
            except Exception as e:
                return {
                    'error': str(e),
                    'verification_failed': True,
                    'verification_time': datetime.now().isoformat()
                }
    
    def export_audit_trail(self, start_date: datetime, end_date: datetime, 
                          output_path: str) -> bool:
        """Export audit trail for specified period"""
        
        try:
            # Load entries for period
            entries = self._load_entries_between(start_date, end_date)
            
            # Create export data
            export_data = {
                'export_metadata': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_entries': len(entries),
                    'export_time': datetime.now().isoformat(),
                    'observer_version': self.version
                },
                'audit_entries': [entry.to_dict() for entry in entries],
                'integrity_verification': self._verify_audit_integrity(entries)
            }
            
            # Write export file
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            print(f"📤 Audit trail exported: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Audit export error: {e}")
            return False
    
    def _load_audit_state(self):
        """Load existing audit state"""
        
        try:
            # Find most recent audit file
            audit_files = self._get_audit_files()
            
            if audit_files:
                latest_file = max(audit_files)
                latest_entries = self._load_entries_from_file(latest_file)
                
                if latest_entries:
                    # Get last hash for chain continuation
                    if self.audit_config['enable_hash_chain']:
                        self.last_hash = latest_entries[-1].hash_chain or ""
                    
                    # Update entry count
                    self.entry_count = sum(len(self._load_entries_from_file(f)) for f in audit_files)
                    
                    print(f"📋 Loaded audit state: {self.entry_count} total entries")
        
        except Exception as e:
            print(f"⚠️ Error loading audit state: {e}")
    
    def _check_file_rotation(self):
        """Check if audit file rotation is needed"""
        
        current_date = datetime.now().date()
        
        # Daily rotation
        if (self.audit_config['enable_daily_rotation'] and 
            current_date != self.current_file_date):
            self._persist_current_entries()
            self.current_file_date = current_date
        
        # Size-based rotation
        elif len(self.current_entries) >= self.audit_config['max_entries_per_file']:
            self._persist_current_entries()
    
    def _persist_current_entries(self):
        """Persist current entries to file"""
        
        if not self.current_entries:
            return
        
        try:
            # Create filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"observer_audit_{timestamp}.json"
            filepath = os.path.join(self.audit_config['log_directory'], filename)
            
            # Prepare data
            audit_data = {
                'file_metadata': {
                    'creation_time': datetime.now().isoformat(),
                    'entry_count': len(self.current_entries),
                    'observer_version': self.version,
                    'hash_chain_enabled': self.audit_config['enable_hash_chain']
                },
                'entries': [entry.to_dict() for entry in self.current_entries]
            }
            
            # Write file
            with open(filepath, 'w') as f:
                json.dump(audit_data, f, indent=2)
            
            # Clear current entries
            self.current_entries.clear()
            
            print(f"💾 Audit entries persisted: {filename}")
            
        except Exception as e:
            print(f"❌ Error persisting audit entries: {e}")
    
    def _get_audit_files(self) -> List[str]:
        """Get list of audit files"""
        
        audit_dir = Path(self.audit_config['log_directory'])
        
        if not audit_dir.exists():
            return []
        
        return [
            str(f) for f in audit_dir.glob('observer_audit_*.json')
            if f.is_file()
        ]
    
    def _load_entries_from_file(self, filepath: str) -> List[AuditEntry]:
        """Load audit entries from file"""
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            entries = []
            for entry_data in data.get('entries', []):
                entry = AuditEntry(
                    entry_id=entry_data['entry_id'],
                    timestamp=datetime.fromisoformat(entry_data['timestamp']),
                    event_type=entry_data['event_type'],
                    event_data=entry_data['event_data'],
                    source=entry_data.get('source', 'intelligence_observer'),
                    hash_chain=entry_data.get('hash_chain')
                )
                entries.append(entry)
            
            return entries
            
        except Exception as e:
            print(f"⚠️ Error loading audit file {filepath}: {e}")
            return []
    
    def _load_entries_since(self, cutoff_date: datetime) -> List[AuditEntry]:
        """Load audit entries since cutoff date"""
        
        all_entries = []
        
        # Load from files
        for filepath in self._get_audit_files():
            entries = self._load_entries_from_file(filepath)
            all_entries.extend([e for e in entries if e.timestamp >= cutoff_date])
        
        # Add current entries
        all_entries.extend([e for e in self.current_entries if e.timestamp >= cutoff_date])
        
        # Sort by timestamp
        all_entries.sort(key=lambda x: x.timestamp)
        
        return all_entries
    
    def _load_entries_between(self, start_date: datetime, end_date: datetime) -> List[AuditEntry]:
        """Load audit entries between dates"""
        
        all_entries = []
        
        # Load from files
        for filepath in self._get_audit_files():
            entries = self._load_entries_from_file(filepath)
            all_entries.extend([
                e for e in entries 
                if start_date <= e.timestamp <= end_date
            ])
        
        # Add current entries
        all_entries.extend([
            e for e in self.current_entries 
            if start_date <= e.timestamp <= end_date
        ])
        
        # Sort by timestamp
        all_entries.sort(key=lambda x: x.timestamp)
        
        return all_entries
    
    def _load_all_entries(self) -> List[AuditEntry]:
        """Load all audit entries"""
        
        all_entries = []
        
        # Load from files
        for filepath in self._get_audit_files():
            entries = self._load_entries_from_file(filepath)
            all_entries.extend(entries)
        
        # Add current entries
        all_entries.extend(self.current_entries)
        
        # Sort by timestamp
        all_entries.sort(key=lambda x: x.timestamp)
        
        return all_entries
    
    def _verify_hash_chain(self, entries: List[AuditEntry]) -> bool:
        """Verify hash chain integrity"""
        
        if not entries or not self.audit_config['enable_hash_chain']:
            return True
        
        try:
            previous_hash = ""
            
            for entry in entries:
                if entry.hash_chain:
                    expected_hash = entry.calculate_hash(previous_hash)
                    if entry.hash_chain != expected_hash:
                        return False
                    previous_hash = entry.hash_chain
            
            return True
            
        except Exception as e:
            print(f"⚠️ Hash chain verification error: {e}")
            return False
    
    def _check_timestamp_gaps(self, entries: List[AuditEntry]) -> List[Dict[str, Any]]:
        """Check for suspicious gaps in timestamps"""
        
        gaps = []
        
        if len(entries) < 2:
            return gaps
        
        for i in range(1, len(entries)):
            time_diff = entries[i].timestamp - entries[i-1].timestamp
            
            # Flag gaps longer than 24 hours during expected operation
            if time_diff > timedelta(hours=24):
                gaps.append({
                    'start_entry': entries[i-1].entry_id,
                    'end_entry': entries[i].entry_id,
                    'gap_hours': time_diff.total_seconds() / 3600,
                    'start_time': entries[i-1].timestamp.isoformat(),
                    'end_time': entries[i].timestamp.isoformat()
                })
        
        return gaps
    
    def _verify_file_integrity(self) -> Dict[str, Any]:
        """Verify integrity of audit files"""
        
        audit_files = self._get_audit_files()
        
        file_status = {
            'total_files': len(audit_files),
            'readable_files': 0,
            'corrupted_files': [],
            'missing_metadata': []
        }
        
        for filepath in audit_files:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Check for required metadata
                if 'file_metadata' not in data:
                    file_status['missing_metadata'].append(filepath)
                
                # Check entries structure
                if 'entries' in data and isinstance(data['entries'], list):
                    file_status['readable_files'] += 1
                else:
                    file_status['corrupted_files'].append(filepath)
                    
            except Exception as e:
                file_status['corrupted_files'].append(filepath)
        
        return file_status
    
    def _verify_audit_integrity(self, entries: List[AuditEntry]) -> Dict[str, Any]:
        """Verify integrity of audit entries"""
        
        return {
            'hash_chain_valid': self._verify_hash_chain(entries),
            'timestamp_gaps': len(self._check_timestamp_gaps(entries)),
            'entry_count': len(entries)
        }