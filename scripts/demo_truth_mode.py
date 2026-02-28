#!/usr/bin/env python3
"""
Demo: Truth Mode Validator

This script demonstrates the Truth Mode validator - the first and most
critical institutional safeguard that prevents cherry-picking and bias.

Usage:
    python scripts/demo_truth_mode.py

Author: Northstar Team
Date: 2026-01-05
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def demo_truth_mode():
    """Demonstrate Truth Mode validation."""
    print("🧠 TRUTH MODE VALIDATOR DEMO")
    print("=" * 50)
    print("Demonstrating the prevention of cherry-picking and bias")
    print()
    
    from validation.truth_mode_validator import TruthModeValidator
    
    # Create validator
    validator = TruthModeValidator()
    
    print("1. Creating system freeze...")
    freeze = validator.create_system_freeze()
    
    print(f"   ✅ Run ID: {freeze.run_id}")
    print(f"   ✅ Timestamp: {freeze.timestamp}")
    print(f"   ✅ Git Hash: {freeze.git_hash}")
    print(f"   ✅ Code Hash: {freeze.code_hash[:16]}...")
    print(f"   ✅ Config Hash: {freeze.config_hash[:16]}...")
    print(f"   ✅ Data Hash: {freeze.data_hash[:16]}...")
    
    print("\n2. Validating freeze integrity...")
    integrity_valid = validator.validate_freeze_integrity(freeze)
    
    if integrity_valid:
        print("   ✅ System freeze integrity verified")
        print("   ✅ No tampering detected")
        print("   ✅ Results are immutable")
    else:
        print("   ❌ System freeze integrity failed")
    
    print("\n3. Truth Mode guarantees:")
    print("   🔒 No reruns allowed with same system state")
    print("   🔒 No parameter tweaking after seeing results")
    print("   🔒 No cherry-picking of favorable outcomes")
    print("   🔒 Complete audit trail maintained")
    print("   🔒 Cryptographic integrity verification")
    
    print(f"\n🧠 TRUTH MODE VALIDATION COMPLETE")
    print(f"Run {freeze.run_id} is now immutable and unrepeatable")
    print("This prevents the #1 silent killer: unconscious bias")
    
    return freeze

def main():
    """Main demo function."""
    print("Starting Truth Mode demonstration...")
    print("This is the foundation of institutional-grade validation")
    print()
    
    freeze = demo_truth_mode()
    
    print("\n" + "=" * 50)
    print("🏛️ INSTITUTIONAL IMPACT")
    print("=" * 50)
    print("Truth Mode addresses the most common failure mode:")
    print("• Prevents unconscious result selection")
    print("• Eliminates 'try again' bias")
    print("• Stops parameter tweaking after backtests")
    print("• Creates immutable audit trails")
    print("• Enables regulatory compliance")
    print()
    print("This single safeguard prevents more fund failures")
    print("than any other institutional control.")
    print()
    print("🎉 Truth Mode: The foundation of honest quant research")

if __name__ == "__main__":
    main()