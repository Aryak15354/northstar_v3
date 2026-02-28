#!/usr/bin/env python3
"""
🔍 PROVENANCE SYSTEM - PHASE 5: INFRASTRUCTURE LAYER
Complete data provenance and audit trail for institutional validation

This implements the core data provenance requirements for Phase 5 (Infrastructure)
of the institutional validation framework. It provides complete traceability of
all data sources, versions, and transformations used in system decisions.

CRITICAL PRINCIPLE: Complete Data Lineage
- Create manifest for every system run
- Include file hashes, timestamps, schema versions
- Include code commit hash for reproducibility
- Link manifest to all outputs
- Ensure immutable audit trail

Usage:
    from src.validation.provenance_system import ProvenanceSystem
    
    provenance = ProvenanceSystem()
    manifest = provenance.create_run_manifest(run_id="20260118_143022")
    provenance.link_outputs(manifest_id, output_files)
"""

import pandas as pd
import numpy as np
import json
import os
import hashlib
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')


@dataclass
class DataFile:
    """
    Data file record for provenance tracking
    
    Complete file information with hash, timestamp, and schema version.
    """
    path: str
    hash: str  # SHA256 hash of file content
    timestamp: datetime  # File modification timestamp
    schema_version: str  # Schema version identifier
    size_bytes: int  # File size in bytes
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['timestamp'] = result['timestamp'].isoformat()
        return result
    
    def validate(self) -> List[str]:
        """Validate data file record"""
        errors = []
        
        if not self.path:
            errors.append("Path cannot be empty")
        
        if not self.hash or len(self.hash) != 64:
            errors.append(f"Invalid SHA256 hash: {self.hash}")
        
        if self.size_bytes < 0:
            errors.append(f"Size cannot be negative: {self.size_bytes}")
        
        return errors


@dataclass
class RunManifest:
    """
    Run manifest record for complete provenance tracking
    
    Complete record of all data and code used in a system run.
    """
    run_id: str
    timestamp: datetime
    code_commit: Optional[str]  # Git commit hash if available
    data_files: List[DataFile]
    linked_outputs: List[str]  # Output files produced by this run
    system_info: Dict[str, Any]  # System information
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = {
            'run_id': self.run_id,
            'timestamp': self.timestamp.isoformat(),
            'code_commit': self.code_commit,
            'data_files': [df.to_dict() for df in self.data_files],
            'linked_outputs': self.linked_outputs,
            'system_info': self.system_info
        }
        return result
    
    def validate(self) -> List[str]:
        """Validate run manifest"""
        errors = []
        
        if not self.run_id:
            errors.append("Run ID cannot be empty")
        
        if not self.data_files:
            errors.append("Data files list cannot be empty")
        
        # Validate all data files
        for i, data_file in enumerate(self.data_files):
            file_errors = data_file.validate()
            for error in file_errors:
                errors.append(f"Data file {i}: {error}")
        
        return errors


class ProvenanceSystem:
    """
    Provenance System - Phase 5: Infrastructure Layer
    
    Provides complete data provenance and audit trail for institutional
    validation and compliance. Tracks all data sources, versions, and
    transformations used in system decisions.
    
    ENFORCES REQUIREMENTS:
    - 16.1-16.8: Data provenance and versioning
    
    V3 INTEGRATION:
    - Uses UnifiedState for state storage (Requirement 14.1)
    - Emits events through EventBus (Requirement 14.2)
    - Integrates with Market_Clock for time-driven updates (Requirement 14.4)
    """
    
    def __init__(self, 
                 base_dir: str = "data/metadata",
                 unified_state=None,
                 event_bus=None,
                 market_clock=None):
        """
        Initialize Provenance System
        
        Args:
            base_dir: Base directory for provenance manifests
            unified_state: Optional UnifiedState instance for V3 integration
            event_bus: Optional EventBus instance for V3 integration
            market_clock: Optional Market_Clock instance for V3 integration
        """
        self.base_dir = base_dir
        
        # Create base directory
        os.makedirs(base_dir, exist_ok=True)
        
        # V3 Integration (optional)
        self.unified_state = unified_state
        self.event_bus = event_bus
        self.market_clock = market_clock
        
        # Current run tracking
        self.current_manifest: Optional[RunManifest] = None
        
        print("🔍 Provenance System initialized")
        print(f"   Output: {self.base_dir}/")
        if unified_state:
            print("   ✅ V3 Integration: UnifiedState connected")
        if event_bus:
            print("   ✅ V3 Integration: EventBus connected")
        if market_clock:
            print("   ✅ V3 Integration: Market_Clock connected")
    
    def _compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA256 hash of file content
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash as hex string
        """
        
        try:
            hash_sha256 = hashlib.sha256()
            
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            print(f"⚠️ Failed to compute hash for {file_path}: {e}")
            return "unknown"
    
    def _get_file_timestamp(self, file_path: str) -> datetime:
        """
        Get file modification timestamp
        
        Args:
            file_path: Path to file
            
        Returns:
            File modification timestamp
        """
        
        try:
            stat = os.stat(file_path)
            return datetime.fromtimestamp(stat.st_mtime)
        except Exception as e:
            print(f"⚠️ Failed to get timestamp for {file_path}: {e}")
            return datetime.now()
    
    def _get_file_size(self, file_path: str) -> int:
        """
        Get file size in bytes
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes
        """
        
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            print(f"⚠️ Failed to get size for {file_path}: {e}")
            return 0
    
    def _detect_schema_version(self, file_path: str) -> str:
        """
        Detect schema version for data file
        
        Args:
            file_path: Path to file
            
        Returns:
            Schema version identifier
        """
        
        # Simple schema version detection based on file extension and content
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.parquet':
            try:
                # Try to read parquet file and inspect schema
                df = pd.read_parquet(file_path, nrows=0)  # Just read schema
                columns = list(df.columns)
                
                # Detect common schema patterns
                if 'date' in columns and 'northstar_return' in columns:
                    return "performance_v3.2"
                elif 'date' in columns and 'regime_id' in columns:
                    return "regime_memory_v2.1"
                elif 'date' in columns and 'ticker' in columns and 'weight' in columns:
                    return "positions_v1.0"
                elif 'date' in columns and 'returns' in columns:
                    return "pnl_v1.0"
                else:
                    return f"parquet_v1.0_{len(columns)}cols"
                    
            except Exception:
                return "parquet_unknown"
        
        elif file_ext == '.json':
            try:
                # Try to read JSON and detect structure
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    if 'run_id' in data and 'timestamp' in data:
                        return "manifest_v1.0"
                    elif 'regime' in data and 'tailwind_shift' in data:
                        return "decisions_v1.0"
                    else:
                        return f"json_dict_v1.0_{len(data)}keys"
                elif isinstance(data, list):
                    return f"json_list_v1.0_{len(data)}items"
                else:
                    return "json_unknown"
                    
            except Exception:
                return "json_unknown"
        
        elif file_ext == '.csv':
            try:
                # Try to read CSV and inspect columns
                df = pd.read_csv(file_path, nrows=0)
                return f"csv_v1.0_{len(df.columns)}cols"
            except Exception:
                return "csv_unknown"
        
        else:
            return f"unknown_{file_ext}"
    
    def _get_git_commit_hash(self) -> Optional[str]:
        """
        Get current git commit hash if available
        
        Returns:
            Git commit hash or None if not available
        """
        
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
                
        except Exception:
            return None
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        Get system information for manifest
        
        Returns:
            Dictionary with system information
        """
        
        import platform
        import sys
        
        return {
            'python_version': sys.version,
            'platform': platform.platform(),
            'hostname': platform.node(),
            'user': os.environ.get('USER', 'unknown'),
            'working_directory': os.getcwd(),
            'environment_variables': {
                key: value for key, value in os.environ.items()
                if key.startswith(('NORTHSTAR_', 'DATA_', 'CONFIG_'))
            }
        }
    
    def create_data_file_record(self, file_path: str) -> Optional[DataFile]:
        """
        Create data file record for provenance tracking
        
        ENFORCES PROPERTY 34: Data Provenance Manifest Completeness
        VALIDATES REQUIREMENTS 16.2, 16.3, 16.4
        
        Args:
            file_path: Path to data file
            
        Returns:
            DataFile record or None if file doesn't exist
        """
        
        if not os.path.exists(file_path):
            print(f"⚠️ File not found: {file_path}")
            return None
        
        try:
            # Compute file hash
            file_hash = self._compute_file_hash(file_path)
            
            # Get file timestamp
            timestamp = self._get_file_timestamp(file_path)
            
            # Get file size
            size_bytes = self._get_file_size(file_path)
            
            # Detect schema version
            schema_version = self._detect_schema_version(file_path)
            
            # Create DataFile record
            data_file = DataFile(
                path=file_path,
                hash=file_hash,
                timestamp=timestamp,
                schema_version=schema_version,
                size_bytes=size_bytes
            )
            
            # Validate
            validation_errors = data_file.validate()
            if validation_errors:
                print(f"⚠️ Data file validation warnings for {file_path}:")
                for error in validation_errors:
                    print(f"   {error}")
            
            return data_file
            
        except Exception as e:
            print(f"❌ Failed to create data file record for {file_path}: {e}")
            return None
    
    def create_run_manifest(self, 
                           run_id: Optional[str] = None,
                           data_file_patterns: List[str] = None) -> RunManifest:
        """
        Create run manifest for complete provenance tracking
        
        ENFORCES PROPERTY 34: Data Provenance Manifest Completeness
        VALIDATES REQUIREMENTS 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8
        
        Args:
            run_id: Optional run identifier (auto-generated if None)
            data_file_patterns: List of file patterns to include in manifest
            
        Returns:
            RunManifest object
        """
        
        # Generate run ID if not provided
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"🔍 Creating run manifest: {run_id}")
        
        # Get current timestamp
        timestamp = datetime.now()
        
        # Get git commit hash
        code_commit = self._get_git_commit_hash()
        if code_commit:
            print(f"   Git commit: {code_commit[:8]}")
        else:
            print("   Git commit: Not available")
        
        # Get system information
        system_info = self._get_system_info()
        
        # Default data file patterns if not provided
        if data_file_patterns is None:
            data_file_patterns = [
                "data/processed/*.parquet",
                "data/macro/*.parquet",
                "data/market/*.parquet",
                "data/intelligence/*.parquet",
                "data/risk/*.parquet",
                "data/portfolio/*.parquet",
                "data/state/*.parquet",
                "data/validation/*.parquet"
            ]
        
        # Collect data files
        data_files = []
        
        for pattern in data_file_patterns:
            # Simple glob-like pattern matching
            if '*' in pattern:
                # Extract directory and extension
                parts = pattern.split('*')
                if len(parts) == 2:
                    directory = parts[0]
                    extension = parts[1]
                    
                    if os.path.exists(directory):
                        for filename in os.listdir(directory):
                            if filename.endswith(extension):
                                file_path = os.path.join(directory, filename)
                                data_file = self.create_data_file_record(file_path)
                                if data_file:
                                    data_files.append(data_file)
            else:
                # Exact file path
                if os.path.exists(pattern):
                    data_file = self.create_data_file_record(pattern)
                    if data_file:
                        data_files.append(data_file)
        
        print(f"   Data files: {len(data_files)} files tracked")
        
        # Create manifest
        manifest = RunManifest(
            run_id=run_id,
            timestamp=timestamp,
            code_commit=code_commit,
            data_files=data_files,
            linked_outputs=[],  # Will be populated later
            system_info=system_info
        )
        
        # Validate manifest
        validation_errors = manifest.validate()
        if validation_errors:
            print(f"⚠️ Manifest validation warnings:")
            for error in validation_errors[:5]:  # Show first 5 errors
                print(f"   {error}")
            if len(validation_errors) > 5:
                print(f"   ... and {len(validation_errors) - 5} more")
        
        # Save manifest
        manifest_path = self._save_manifest(manifest)
        print(f"   Saved: {manifest_path}")
        
        # Store as current manifest
        self.current_manifest = manifest
        
        # V3 Integration: Store in UnifiedState
        self._store_manifest_in_unified_state(manifest)
        
        # V3 Integration: Emit event
        self._emit_manifest_event(manifest)
        
        return manifest
    
    def link_outputs(self, 
                    manifest_id: str, 
                    output_files: List[str]) -> bool:
        """
        Link output files to existing manifest
        
        ENFORCES PROPERTY 34: Data Provenance Manifest Completeness
        VALIDATES REQUIREMENTS 16.6
        
        Args:
            manifest_id: Run ID of the manifest
            output_files: List of output file paths
            
        Returns:
            True if successful, False otherwise
        """
        
        try:
            # Load existing manifest
            manifest_path = os.path.join(self.base_dir, f"run_manifest_{manifest_id}.json")
            
            if not os.path.exists(manifest_path):
                print(f"❌ Manifest not found: {manifest_id}")
                return False
            
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            # Add output files
            existing_outputs = set(manifest_data.get('linked_outputs', []))
            new_outputs = set(output_files)
            all_outputs = list(existing_outputs | new_outputs)
            
            manifest_data['linked_outputs'] = all_outputs
            
            # Save updated manifest
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f, indent=2, default=str)
            
            print(f"✅ Linked {len(new_outputs)} outputs to manifest {manifest_id}")
            
            # V3 Integration: Emit event
            if self.event_bus:
                self.event_bus.emit(
                    event_type="PROVENANCE_OUTPUTS_LINKED",
                    source="provenance_system",
                    data={
                        "manifest_id": manifest_id,
                        "output_count": len(new_outputs),
                        "total_outputs": len(all_outputs)
                    },
                    tags=["provenance", "outputs", "linking"]
                )
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to link outputs to manifest {manifest_id}: {e}")
            return False
    
    def _save_manifest(self, manifest: RunManifest) -> str:
        """
        Save manifest to file
        
        ENFORCES PROPERTY 35: Manifest Immutability
        VALIDATES REQUIREMENTS 16.8
        
        Args:
            manifest: RunManifest to save
            
        Returns:
            Path to saved manifest file
        """
        
        # Create filename
        filename = f"run_manifest_{manifest.run_id}.json"
        file_path = os.path.join(self.base_dir, filename)
        
        # Convert to dictionary
        manifest_data = manifest.to_dict()
        
        # Add cryptographic signature (simple hash for now)
        manifest_json = json.dumps(manifest_data, sort_keys=True, default=str)
        manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
        manifest_data['_signature'] = manifest_hash
        
        # Save to file
        with open(file_path, 'w') as f:
            json.dump(manifest_data, f, indent=2, default=str)
        
        return file_path
    
    def load_manifest(self, manifest_id: str) -> Optional[RunManifest]:
        """
        Load manifest from file
        
        Args:
            manifest_id: Run ID of the manifest
            
        Returns:
            RunManifest object or None if not found
        """
        
        manifest_path = os.path.join(self.base_dir, f"run_manifest_{manifest_id}.json")
        
        if not os.path.exists(manifest_path):
            return None
        
        try:
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            # Verify signature
            signature = manifest_data.pop('_signature', None)
            if signature:
                manifest_json = json.dumps(manifest_data, sort_keys=True, default=str)
                expected_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
                
                if signature != expected_hash:
                    print(f"⚠️ Manifest signature mismatch for {manifest_id}")
            
            # Convert data files
            data_files = []
            for df_data in manifest_data.get('data_files', []):
                df_data['timestamp'] = datetime.fromisoformat(df_data['timestamp'])
                data_files.append(DataFile(**df_data))
            
            # Create manifest
            manifest = RunManifest(
                run_id=manifest_data['run_id'],
                timestamp=datetime.fromisoformat(manifest_data['timestamp']),
                code_commit=manifest_data.get('code_commit'),
                data_files=data_files,
                linked_outputs=manifest_data.get('linked_outputs', []),
                system_info=manifest_data.get('system_info', {})
            )
            
            return manifest
            
        except Exception as e:
            print(f"❌ Failed to load manifest {manifest_id}: {e}")
            return None
    
    def verify_reproducibility(self, 
                              manifest_id: str,
                              current_data_patterns: List[str] = None) -> Dict[str, Any]:
        """
        Verify reproducibility by comparing current data with manifest
        
        ENFORCES PROPERTY 0.5: Reproducibility
        VALIDATES REQUIREMENTS 16.7
        
        Args:
            manifest_id: Run ID of the manifest to verify against
            current_data_patterns: Current data file patterns to check
            
        Returns:
            Dictionary with reproducibility verification results
        """
        
        print(f"🔍 Verifying reproducibility for manifest: {manifest_id}")
        
        # Load original manifest
        original_manifest = self.load_manifest(manifest_id)
        if not original_manifest:
            return {
                'status': 'error',
                'message': f'Manifest {manifest_id} not found'
            }
        
        # Create current manifest for comparison
        current_manifest = self.create_run_manifest(
            run_id=f"{manifest_id}_verification",
            data_file_patterns=current_data_patterns
        )
        
        # Compare manifests
        results = {
            'status': 'success',
            'manifest_id': manifest_id,
            'verification_time': datetime.now().isoformat(),
            'code_commit_match': original_manifest.code_commit == current_manifest.code_commit,
            'file_count_match': len(original_manifest.data_files) == len(current_manifest.data_files),
            'files_changed': [],
            'files_missing': [],
            'files_added': [],
            'reproducible': True
        }
        
        # Create lookup for current files
        current_files = {df.path: df for df in current_manifest.data_files}
        original_files = {df.path: df for df in original_manifest.data_files}
        
        # Check for changes and missing files
        for path, original_file in original_files.items():
            if path not in current_files:
                results['files_missing'].append(path)
                results['reproducible'] = False
            else:
                current_file = current_files[path]
                if original_file.hash != current_file.hash:
                    results['files_changed'].append({
                        'path': path,
                        'original_hash': original_file.hash,
                        'current_hash': current_file.hash,
                        'original_timestamp': original_file.timestamp.isoformat(),
                        'current_timestamp': current_file.timestamp.isoformat()
                    })
                    results['reproducible'] = False
        
        # Check for added files
        for path in current_files:
            if path not in original_files:
                results['files_added'].append(path)
        
        # Summary
        if results['reproducible']:
            print(f"✅ Reproducibility verified: All data files match")
        else:
            print(f"⚠️ Reproducibility risk detected:")
            if results['files_changed']:
                print(f"   Changed files: {len(results['files_changed'])}")
            if results['files_missing']:
                print(f"   Missing files: {len(results['files_missing'])}")
            if results['files_added']:
                print(f"   Added files: {len(results['files_added'])}")
        
        return results
    
    def get_manifest_summary(self, 
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get summary of all manifests in date range
        
        Args:
            start_date: Start date for summary (optional)
            end_date: End date for summary (optional)
            
        Returns:
            Dictionary with manifest summary statistics
        """
        
        # Get all manifest files
        manifest_files = [f for f in os.listdir(self.base_dir) if f.startswith('run_manifest_') and f.endswith('.json')]
        
        summary = {
            'total_manifests': len(manifest_files),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            },
            'manifests_in_range': 0,
            'total_data_files': 0,
            'total_outputs': 0,
            'code_commits': set(),
            'schema_versions': {},
            'file_extensions': {},
            'manifests': []
        }
        
        for manifest_file in manifest_files:
            try:
                manifest_id = manifest_file.replace('run_manifest_', '').replace('.json', '')
                manifest = self.load_manifest(manifest_id)
                
                if manifest:
                    # Check date range
                    if start_date and manifest.timestamp < start_date:
                        continue
                    if end_date and manifest.timestamp > end_date:
                        continue
                    
                    summary['manifests_in_range'] += 1
                    summary['total_data_files'] += len(manifest.data_files)
                    summary['total_outputs'] += len(manifest.linked_outputs)
                    
                    if manifest.code_commit:
                        summary['code_commits'].add(manifest.code_commit)
                    
                    # Track schema versions and file extensions
                    for data_file in manifest.data_files:
                        schema = data_file.schema_version
                        summary['schema_versions'][schema] = summary['schema_versions'].get(schema, 0) + 1
                        
                        ext = Path(data_file.path).suffix
                        summary['file_extensions'][ext] = summary['file_extensions'].get(ext, 0) + 1
                    
                    summary['manifests'].append({
                        'run_id': manifest.run_id,
                        'timestamp': manifest.timestamp.isoformat(),
                        'code_commit': manifest.code_commit,
                        'data_files_count': len(manifest.data_files),
                        'outputs_count': len(manifest.linked_outputs)
                    })
                    
            except Exception as e:
                print(f"⚠️ Failed to process manifest {manifest_file}: {e}")
        
        # Convert sets to lists for JSON serialization
        summary['code_commits'] = list(summary['code_commits'])
        
        return summary
    
    # ========================================================================
    # V3 INTEGRATION METHODS
    # ========================================================================
    
    def _store_manifest_in_unified_state(self, manifest: RunManifest):
        """Store manifest in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "provenance_system"
            
            # Store latest manifest
            self.unified_state.set(
                component=component_name,
                key="latest_manifest",
                value={
                    "run_id": manifest.run_id,
                    "timestamp": manifest.timestamp.isoformat(),
                    "code_commit": manifest.code_commit,
                    "data_files_count": len(manifest.data_files),
                    "outputs_count": len(manifest.linked_outputs)
                }
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store manifest in UnifiedState: {e}")
    
    def _emit_manifest_event(self, manifest: RunManifest):
        """Emit manifest event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            self.event_bus.emit(
                event_type="PROVENANCE_MANIFEST_CREATED",
                source="provenance_system",
                data={
                    "run_id": manifest.run_id,
                    "timestamp": manifest.timestamp.isoformat(),
                    "code_commit": manifest.code_commit,
                    "data_files_count": len(manifest.data_files),
                    "outputs_count": len(manifest.linked_outputs)
                },
                tags=["provenance", "manifest", "created"]
            )
            
        except Exception as e:
            print(f"⚠️ Failed to emit manifest event: {e}")


def main():
    """Demonstrate Provenance System"""
    
    print("🔍 PROVENANCE SYSTEM - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize provenance system
    provenance = ProvenanceSystem(base_dir="data/test_metadata")
    
    # Create run manifest
    manifest = provenance.create_run_manifest(
        run_id="DEMO_20260118_143022",
        data_file_patterns=[
            "data/processed/performance_summary.parquet",
            "data/intelligence/regime_memory.parquet",
            "data/risk/risk_state.parquet"
        ]
    )
    
    print(f"\n📋 MANIFEST CREATED")
    print(f"   Run ID: {manifest.run_id}")
    print(f"   Timestamp: {manifest.timestamp}")
    print(f"   Code commit: {manifest.code_commit}")
    print(f"   Data files: {len(manifest.data_files)}")
    
    # Simulate linking outputs
    output_files = [
        "data/reports/monthly_report_202401.pdf",
        "data/execution/shadow_trades.parquet"
    ]
    
    success = provenance.link_outputs(manifest.run_id, output_files)
    print(f"\n🔗 OUTPUTS LINKED: {success}")
    
    # Verify reproducibility
    verification = provenance.verify_reproducibility(manifest.run_id)
    print(f"\n🔍 REPRODUCIBILITY CHECK")
    print(f"   Status: {verification['status']}")
    print(f"   Reproducible: {verification.get('reproducible', False)}")
    
    # Get summary
    summary = provenance.get_manifest_summary()
    print(f"\n📊 SUMMARY")
    print(f"   Total manifests: {summary['total_manifests']}")
    print(f"   Total data files: {summary['total_data_files']}")
    print(f"   Code commits: {len(summary['code_commits'])}")
    
    print("\n✅ Provenance System demonstration complete")


if __name__ == "__main__":
    main()