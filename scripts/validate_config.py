#!/usr/bin/env python3
"""
Configuration Validation Script

Validates configuration files for correctness.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
import argparse
from pathlib import Path


def validate_config(config_path):
    """Validate configuration file"""
    print(f"Validating: {config_path}")
    
    if not Path(config_path).exists():
        print(f"❌ File not found: {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check required sections
        required_sections = [
            'position_limits',
            'greeks_limits',
            'risk_thresholds'
        ]
        
        for section in required_sections:
            if section not in config:
                print(f"❌ Missing required section: {section}")
                return False
            print(f"✅ Found section: {section}")
        
        # Validate position limits
        pos_limits = config['position_limits']
        if 'per_underlying' not in pos_limits or 'total' not in pos_limits:
            print("❌ Invalid position_limits structure")
            return False
        
        # Validate Greeks limits
        greeks_limits = config['greeks_limits']
        required_greeks = ['delta', 'gamma', 'vega', 'theta']
        for greek in required_greeks:
            if greek not in greeks_limits:
                print(f"❌ Missing Greek limit: {greek}")
                return False
        
        # Validate risk thresholds
        risk_thresh = config['risk_thresholds']
        if 'var_95' not in risk_thresh:
            print("❌ Missing var_95 threshold")
            return False
        
        print("✅ Configuration is valid")
        return True
        
    except yaml.YAMLError as e:
        print(f"❌ YAML parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Validate configuration file')
    parser.add_argument('config_file', help='Path to configuration file')
    args = parser.parse_args()
    
    success = validate_config(args.config_file)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
