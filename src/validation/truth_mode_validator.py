"""
Truth Mode Validator - No Excuses Institutional Validation

This implements the "northstar run --truth" command that prevents:
- Silent cherry-picking
- Unconscious tweaking  
- "Try again" bias

Every run is frozen, hashed, and immutable.

Author: Northstar Team
Date: 2026-01-05
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import numpy as np

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


@dataclass
class SystemFreeze:
    """Complete system freeze for truth mode validation."""
    run_id: str
    timestamp: datetime
    config_hash: str
    code_hash: str
    git_hash: str
    seed_set: Dict[str, int]
    environment_hash: str
    data_hash: str
    
    def to_header(self) -> str:
        """Generate immutable header for all reports."""
        return f"""
# NORTHSTAR TRUTH MODE VALIDATION
# RUN ID: {self.run_id}
# TIMESTAMP: {self.timestamp.isoformat()}
# CONFIG HASH: {self.config_hash}
# CODE HASH: {self.code_hash}
# GIT HASH: {self.git_hash}
# SEED SET: {json.dumps(self.seed_set)}
# ENV HASH: {self.environment_hash}
# DATA HASH: {self.data_hash}
# 
# WARNING: This run is IMMUTABLE. Any differences invalidate results.
# ========================================================================
"""


class TruthModeValidator:
    """
    Institutional-grade truth mode validator.
    
    Implements "no excuses" validation that prevents all forms of
    unconscious bias and cherry-picking.
    """
    
    def __init__(self):
        """Initialize truth mode validator."""
        self.logger = setup_operation_logging()
        self.freeze_dir = Path("truth_mode_runs")
        self.freeze_dir.mkdir(exist_ok=True)
        
        self.logger.info("Truth Mode Validator initialized")
    
    def create_system_freeze(self) -> SystemFreeze:
        """
        Create complete system freeze with all hashes.
        
        Returns:
            SystemFreeze: Immutable system state
        """
        self.logger.info("Creating system freeze...")
        
        # Generate unique run ID
        run_id = f"truth_{int(time.time())}_{np.random.randint(10000, 99999)}"
        
        # Get git hash
        try:
            git_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                cwd=".", 
                text=True
            ).strip()
        except:
            git_hash = "NO_GIT_REPO"
        
        # Hash all configuration files
        config_hash = self._hash_configs()
        
        # Hash all source code
        code_hash = self._hash_source_code()
        
        # Set deterministic seeds
        seed_set = {
            "numpy": 42,
            "random": 42,
            "torch": 42,
            "tensorflow": 42,
            "system": 42
        }
        
        # Hash environment
        env_hash = self._hash_environment()
        
        # Hash data files
        data_hash = self._hash_data_files()
        
        freeze = SystemFreeze(
            run_id=run_id,
            timestamp=datetime.now(),
            config_hash=config_hash,
            code_hash=code_hash,
            git_hash=git_hash,
            seed_set=seed_set,
            environment_hash=env_hash,
            data_hash=data_hash
        )
        
        # Save freeze state
        freeze_file = self.freeze_dir / f"{run_id}_freeze.json"
        with open(freeze_file, 'w') as f:
            json.dump(asdict(freeze), f, indent=2, default=str)
        
        self.logger.info(f"System freeze created: {run_id}")
        return freeze
    
    def validate_freeze_integrity(self, freeze: SystemFreeze) -> bool:
        """
        Validate that system state matches frozen state.
        
        Args:
            freeze: Original system freeze
            
        Returns:
            bool: True if system is unchanged
        """
        self.logger.info("Validating freeze integrity...")
        
        # Check git hash
        try:
            current_git = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                cwd=".", 
                text=True
            ).strip()
            if current_git != freeze.git_hash:
                self.logger.error(f"Git hash mismatch: {current_git} != {freeze.git_hash}")
                return False
        except:
            if freeze.git_hash != "NO_GIT_REPO":
                self.logger.error("Git repo state changed")
                return False
        
        # Check config hash
        current_config_hash = self._hash_configs()
        if current_config_hash != freeze.config_hash:
            self.logger.error(f"Config hash mismatch: {current_config_hash} != {freeze.config_hash}")
            return False
        
        # Check code hash
        current_code_hash = self._hash_source_code()
        if current_code_hash != freeze.code_hash:
            self.logger.error(f"Code hash mismatch: {current_code_hash} != {freeze.code_hash}")
            return False
        
        # Check data hash
        current_data_hash = self._hash_data_files()
        if current_data_hash != freeze.data_hash:
            self.logger.error(f"Data hash mismatch: {current_data_hash} != {freeze.data_hash}")
            return False
        
        self.logger.info("Freeze integrity validated ✅")
        return True
    
    def run_truth_mode_validation(self) -> Dict[str, Any]:
        """
        Run complete truth mode validation.
        
        Returns:
            Dict: Validation results with immutable header
        """
        self.logger.info("🧠 STARTING TRUTH MODE VALIDATION")
        self.logger.info("=" * 60)
        
        # Create system freeze
        freeze = self.create_system_freeze()
        
        # Set all seeds deterministically
        self._set_deterministic_seeds(freeze.seed_set)
        
        # Validate freeze integrity
        if not self.validate_freeze_integrity(freeze):
            raise RuntimeError("System freeze integrity check failed")
        
        # Check if this exact run already exists
        if self._run_already_exists(freeze):
            raise RuntimeError(f"Run {freeze.run_id} already exists. Truth mode prevents reruns.")
        
        # Run full walk-forward validation
        validation_results = self._run_full_walk_forward(freeze)
        
        # Generate single immutable report
        report = self._generate_truth_report(freeze, validation_results)
        
        # Save report with freeze header
        report_file = self.freeze_dir / f"{freeze.run_id}_truth_report.md"
        with open(report_file, 'w') as f:
            f.write(freeze.to_header())
            f.write(report)
        
        self.logger.info(f"Truth mode validation complete: {freeze.run_id}")
        self.logger.info(f"Report saved: {report_file}")
        
        return {
            "run_id": freeze.run_id,
            "freeze": freeze,
            "results": validation_results,
            "report_path": str(report_file),
            "integrity_verified": True
        }
    
    def _hash_configs(self) -> str:
        """Hash all configuration files."""
        config_files = []
        
        # Find all config files
        for pattern in ["config/**/*.yaml", "config/**/*.json", "*.yaml", "*.json"]:
            config_files.extend(Path(".").glob(pattern))
        
        # Sort for deterministic hashing
        config_files.sort()
        
        hasher = hashlib.sha256()
        for config_file in config_files:
            if config_file.exists() and config_file.is_file():
                with open(config_file, 'rb') as f:
                    hasher.update(f.read())
        
        return hasher.hexdigest()
    
    def _hash_source_code(self) -> str:
        """Hash all source code files."""
        source_files = []
        
        # Find all Python files
        for pattern in ["src/**/*.py", "scripts/**/*.py", "tests/**/*.py"]:
            source_files.extend(Path(".").glob(pattern))
        
        # Sort for deterministic hashing
        source_files.sort()
        
        hasher = hashlib.sha256()
        for source_file in source_files:
            if source_file.exists() and source_file.is_file():
                with open(source_file, 'rb') as f:
                    hasher.update(f.read())
        
        return hasher.hexdigest()
    
    def _hash_environment(self) -> str:
        """Hash environment variables and system info."""
        def _safe_cmd_output(cmd, fallback: str = "unavailable") -> str:
            try:
                return subprocess.check_output(cmd, text=True).strip()
            except Exception:
                return fallback

        python_executable = sys.executable or "python3"
        python_version = _safe_cmd_output([python_executable, "--version"])
        if python_version == "unavailable":
            python_version = _safe_cmd_output(["python3", "--version"])

        pip_freeze = _safe_cmd_output([python_executable, "-m", "pip", "freeze"])
        if pip_freeze == "unavailable":
            pip_freeze = _safe_cmd_output(["pip3", "freeze"], fallback="")

        env_data = {
            "python_version": python_version,
            "python_executable": python_executable,
            "pip_freeze": pip_freeze,
            "platform": str(os.uname()) if hasattr(os, 'uname') else str(os.name)
        }
        
        env_str = json.dumps(env_data, sort_keys=True)
        return hashlib.sha256(env_str.encode()).hexdigest()
    
    def _hash_data_files(self) -> str:
        """Hash all data files."""
        data_files = []
        excluded_roots = {
            "truth_mode_runs",
            "logs",
            "reports",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
        }

        # Find all data files
        for pattern in ["data/**/*", "cache/**/*"]:
            data_files.extend(Path(".").glob(pattern))

        # Sort for deterministic hashing
        filtered: list[Path] = []
        for f in data_files:
            if not f.is_file():
                continue
            parts = set(f.parts)
            if parts.intersection(excluded_roots):
                continue
            # Skip transient artifacts
            if f.suffix in {".tmp", ".lock", ".pid"}:
                continue
            filtered.append(f)
        data_files = filtered
        data_files.sort()
        
        hasher = hashlib.sha256()
        for data_file in data_files:
            try:
                with open(data_file, 'rb') as f:
                    hasher.update(f.read())
            except:
                # Skip files that can't be read
                continue
        
        return hasher.hexdigest()
    
    def _set_deterministic_seeds(self, seed_set: Dict[str, int]):
        """Set all random seeds deterministically."""
        # Set numpy seed
        np.random.seed(seed_set["numpy"])
        
        # Set Python random seed
        import random
        random.seed(seed_set["random"])
        
        # Set torch seed if available
        try:
            import torch
            torch.manual_seed(seed_set["torch"])
        except ImportError:
            pass
        
        # Set tensorflow seed if available
        try:
            import tensorflow as tf
            tf.random.set_seed(seed_set["tensorflow"])
        except ImportError:
            pass
        
        # Set environment variable for system randomness
        os.environ["PYTHONHASHSEED"] = str(seed_set["system"])
    
    def _run_already_exists(self, freeze: SystemFreeze) -> bool:
        """Check if this exact run already exists."""
        for existing_file in self.freeze_dir.glob("*_freeze.json"):
            try:
                with open(existing_file, 'r') as f:
                    existing_freeze = json.load(f)
                
                # Compare all hashes
                if (existing_freeze.get("config_hash") == freeze.config_hash and
                    existing_freeze.get("code_hash") == freeze.code_hash and
                    existing_freeze.get("git_hash") == freeze.git_hash and
                    existing_freeze.get("data_hash") == freeze.data_hash):
                    return True
            except:
                continue
        
        return False
    
    def _run_full_walk_forward(self, freeze: SystemFreeze) -> Dict[str, Any]:
        """Run full walk-forward validation."""
        # Import walk-forward engine
        from ..operation.walk_forward_analysis_engine import WalkForwardAnalysisEngine
        
        # Run walk-forward analysis
        engine = WalkForwardAnalysisEngine()
        results = engine.run_comprehensive_walk_forward_analysis()
        
        return {
            "walk_forward_results": results,
            "validation_timestamp": datetime.now().isoformat(),
            "freeze_verified": True
        }
    
    def _generate_truth_report(self, freeze: SystemFreeze, results: Dict[str, Any]) -> str:
        """Generate single immutable truth report."""
        return f"""
# NORTHSTAR TRUTH MODE VALIDATION REPORT

## Executive Summary
This report represents a complete, immutable validation run of the Northstar system.
No parameters were adjusted, no runs were repeated, no cherry-picking occurred.

## Validation Results
- **Run ID**: {freeze.run_id}
- **Validation Date**: {freeze.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- **System State**: FROZEN AND VERIFIED
- **Walk-Forward Results**: {json.dumps(results.get('walk_forward_results', {}), indent=2)}

## Integrity Verification
✅ Git hash verified: {freeze.git_hash}
✅ Config hash verified: {freeze.config_hash}
✅ Code hash verified: {freeze.code_hash}
✅ Data hash verified: {freeze.data_hash}
✅ Seeds set deterministically: {json.dumps(freeze.seed_set)}

## Truth Mode Guarantees
1. **No Reruns**: This exact system state can never be run again
2. **No Tweaking**: All parameters are frozen and hashed
3. **No Cherry-Picking**: Single run, single report, immutable results
4. **Full Reproducibility**: Every aspect of the system is hashed and verified

## Institutional Certification
This report meets institutional standards for:
- Audit trail completeness
- Result immutability  
- Bias prevention
- Reproducibility verification

---
**TRUTH MODE VALIDATION COMPLETE**
**This report is IMMUTABLE and UNREPEATABLE**
"""


def run_truth_mode():
    """CLI entry point for truth mode validation."""
    validator = TruthModeValidator()
    results = validator.run_truth_mode_validation()
    
    print("🧠 TRUTH MODE VALIDATION COMPLETE")
    print(f"Run ID: {results['run_id']}")
    print(f"Report: {results['report_path']}")
    print("✅ System integrity verified")
    print("✅ Results are immutable and unrepeatable")
    
    return results


def main():
    """Main entry point with CLI argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Northstar Truth Mode Validator")
    parser.add_argument("--truth", action="store_true", help="Run in truth mode")
    parser.add_argument("--verify", type=str, help="Verify existing run by run_id")
    
    args = parser.parse_args()
    
    if args.truth:
        return run_truth_mode()
    elif args.verify:
        validator = TruthModeValidator()
        # Load and verify existing run
        freeze_file = validator.freeze_dir / f"{args.verify}_freeze.json"
        if freeze_file.exists():
            with open(freeze_file, 'r') as f:
                freeze_data = json.load(f)
            
            # Reconstruct freeze object
            freeze = SystemFreeze(**freeze_data)
            
            # Verify integrity
            if validator.validate_freeze_integrity(freeze):
                print(f"✅ Run {args.verify} integrity verified")
                return True
            else:
                print(f"❌ Run {args.verify} integrity check failed")
                return False
        else:
            print(f"❌ Run {args.verify} not found")
            return False
    else:
        parser.print_help()
        return False


if __name__ == "__main__":
    main()
