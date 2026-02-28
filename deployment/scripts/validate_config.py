#!/usr/bin/env python3
"""
Configuration Validation Tool
Validates configuration completeness and consistency
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Configuration validation result"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    score: float

class ConfigurationValidator:
    """Validates Northstar V3 configuration"""
    
    def __init__(self):
        self.required_sections = [
            'market_config',
            'risk_config', 
            'data_config',
            'intelligence_config',
            'portfolio_config'
        ]
        
        self.required_market_params = [
            'market_name',
            'currency',
            'trading_hours',
            'settlement_days',
            'min_trade_size'
        ]
        
        self.required_risk_params = [
            'max_individual_weight',
            'max_sector_weight',
            'max_portfolio_volatility',
            'min_cash_buffer',
            'stop_loss_threshold'
        ]
    
    def validate_configuration(self, config_path: str) -> ValidationResult:
        """Validate configuration file"""
        
        errors = []
        warnings = []
        
        try:
            # Load configuration
            if config_path.endswith('.json'):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            elif config_path.endswith('.yaml') or config_path.endswith('.yml'):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
            else:
                errors.append(f"Unsupported config format: {config_path}")
                return ValidationResult(False, errors, warnings, 0.0)
            
            # Validate required sections
            for section in self.required_sections:
                if section not in config:
                    errors.append(f"Missing required section: {section}")
            
            # Validate market configuration
            if 'market_config' in config:
                market_config = config['market_config']
                for param in self.required_market_params:
                    if param not in market_config:
                        errors.append(f"Missing market parameter: {param}")
            
            # Validate risk configuration
            if 'risk_config' in config:
                risk_config = config['risk_config']
                for param in self.required_risk_params:
                    if param not in risk_config:
                        errors.append(f"Missing risk parameter: {param}")
                
                # Validate risk parameter ranges
                if 'max_individual_weight' in risk_config:
                    weight = risk_config['max_individual_weight']
                    if not (0.01 <= weight <= 0.20):
                        warnings.append(f"max_individual_weight {weight} outside recommended range [0.01, 0.20]")
            
            # Calculate validation score
            total_checks = len(self.required_sections) + len(self.required_market_params) + len(self.required_risk_params)
            failed_checks = len(errors)
            score = max(0.0, (total_checks - failed_checks) / total_checks)
            
            is_valid = len(errors) == 0
            
            return ValidationResult(is_valid, errors, warnings, score)
            
        except Exception as e:
            errors.append(f"Configuration validation failed: {str(e)}")
            return ValidationResult(False, errors, warnings, 0.0)
    
    def generate_template_config(self, environment: str = "production") -> Dict[str, Any]:
        """Generate template configuration for environment"""
        
        template = {
            "environment": environment,
            "market_config": {
                "market_name": "NSE",
                "currency": "INR",
                "trading_hours": {
                    "start": "09:15",
                    "end": "15:30",
                    "timezone": "Asia/Kolkata"
                },
                "settlement_days": 2,
                "min_trade_size": 1000
            },
            "risk_config": {
                "max_individual_weight": 0.05,
                "max_sector_weight": 0.25,
                "max_portfolio_volatility": 0.20,
                "min_cash_buffer": 0.05,
                "stop_loss_threshold": -0.10,
                "max_drawdown": -0.15
            },
            "data_config": {
                "data_sources": ["NSE", "BSE", "RBI"],
                "update_frequency": "daily",
                "lookback_days": 252,
                "min_history_days": 60
            },
            "intelligence_config": {
                "enable_momentum": True,
                "enable_mean_reversion": True,
                "enable_regime_detection": True,
                "signal_decay_days": 30,
                "min_signal_strength": 0.3
            },
            "portfolio_config": {
                "rebalance_frequency": "weekly",
                "max_positions": 20,
                "min_positions": 5,
                "transaction_cost": 0.001
            }
        }
        
        # Environment-specific adjustments
        if environment == "development":
            template["risk_config"]["max_individual_weight"] = 0.10
            template["data_config"]["lookback_days"] = 60
        elif environment == "testing":
            template["risk_config"]["max_individual_weight"] = 0.08
            template["data_config"]["lookback_days"] = 120
        
        return template

def main():
    """Configuration validation tool main function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Northstar V3 Configuration Validator")
    parser.add_argument("--config", help="Configuration file to validate")
    parser.add_argument("--generate", help="Generate template config for environment")
    parser.add_argument("--output", help="Output file for generated config")
    
    args = parser.parse_args()
    
    validator = ConfigurationValidator()
    
    if args.generate:
        print(f"Generating template configuration for {args.generate}")
        template = validator.generate_template_config(args.generate)
        
        output_file = args.output or f"config_{args.generate}.yaml"
        with open(output_file, 'w') as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)
        
        print(f"✅ Template configuration saved to {output_file}")
    
    if args.config:
        print(f"Validating configuration: {args.config}")
        result = validator.validate_configuration(args.config)
        
        print(f"\nValidation Result: {'✅ VALID' if result.is_valid else '❌ INVALID'}")
        print(f"Score: {result.score:.2%}")
        
        if result.errors:
            print("\n❌ Errors:")
            for error in result.errors:
                print(f"  - {error}")
        
        if result.warnings:
            print("\n⚠️ Warnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

if __name__ == "__main__":
    main()
