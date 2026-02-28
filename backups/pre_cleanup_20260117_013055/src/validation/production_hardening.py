#!/usr/bin/env python3
"""
🧬 PRODUCTION HARDENING ORCHESTRATOR
The master validator that makes Northstar ready for real money

This orchestrates all hardening layers:
1. Data Integrity (Point-in-Time Truth)
2. Portfolio Kill Switches (Survival Layer)  
3. Walk-Forward Validation (Temporal Discipline)
4. Model Fraud Detection (Strategy Honesty)

Usage:
    from src.validation.production_hardening import ProductionHardening
    
    hardening = ProductionHardening()
    hardening.run_complete_hardening()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class ProductionHardening:
    """
    Production Hardening Orchestrator
    
    The master system that validates Northstar is ready for real money.
    Runs all validation layers and produces a production readiness report.
    """
    
    def __init__(self):
        self.name = "Production Hardening Orchestrator"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'hardening_report': 'data/validation/production_hardening_report.json',
            'readiness_certificate': 'data/validation/production_readiness_certificate.json'
        }
        
        # Create validation directory
        os.makedirs('data/validation', exist_ok=True)
        
        # Hardening components
        self.hardening_components = {
            'data_integrity': False,
            'kill_switches': False,
            'walk_forward_validation': False,
            'model_fraud_detection': False
        }
        
        # Execution log
        self.execution_log = []
    
    def log_execution(self, component, status, message="", duration=0):
        """Log hardening component execution"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.execution_log.append(entry)
        
        # Update component status
        if component in self.hardening_components:
            self.hardening_components[component] = (status == 'success')
    
    def run_data_integrity_check(self):
        """Layer 1: Data Integrity Validation"""
        
        print("🧱 LAYER 1: DATA INTEGRITY VALIDATION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            import sys
            import os
            )))
            from src.validation.data_integrity import DataIntegrityEngine
            
            integrity_engine = DataIntegrityEngine()
            is_honest = integrity_engine.run_integrity_check()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if is_honest:
                self.log_execution('data_integrity', 'success', 
                                 "Point-in-time integrity enforced", duration)
                print("✅ Data integrity validation PASSED")
                return True
            else:
                self.log_execution('data_integrity', 'failed', 
                                 "Future data leakage detected", duration)
                print("❌ Data integrity validation FAILED")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('data_integrity', 'failed', str(e), duration)
            print(f"❌ Data integrity validation ERROR: {e}")
            return False
    
    def run_kill_switches_check(self):
        """Layer 2: Portfolio Kill Switches Validation"""
        
        print("\n🛡️ LAYER 2: PORTFOLIO KILL SWITCHES")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            import sys
            import os
            )))
            from src.risk.portfolio_kill_switches import PortfolioKillSwitches
            
            kill_switches = PortfolioKillSwitches()
            is_safe, emergency_actions = kill_switches.check_portfolio_health()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if is_safe:
                self.log_execution('kill_switches', 'success', 
                                 "All kill switches operational", duration)
                print("✅ Kill switches validation PASSED")
                return True
            else:
                self.log_execution('kill_switches', 'failed', 
                                 f"Emergency actions triggered: {len(emergency_actions)}", duration)
                print("❌ Kill switches validation FAILED - Emergency actions taken")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('kill_switches', 'failed', str(e), duration)
            print(f"❌ Kill switches validation ERROR: {e}")
            return False
    
    def run_walk_forward_validation(self):
        """Layer 3: Walk-Forward Temporal Validation"""
        
        print("\n🧪 LAYER 3: WALK-FORWARD VALIDATION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            import sys
            import os
            )))
            from src.validation.walk_forward_engine import WalkForwardEngine
            
            validator = WalkForwardEngine()
            is_valid = validator.run_walk_forward_validation()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if is_valid:
                self.log_execution('walk_forward_validation', 'success', 
                                 "Temporal discipline maintained", duration)
                print("✅ Walk-forward validation PASSED")
                return True
            else:
                self.log_execution('walk_forward_validation', 'failed', 
                                 "Temporal integrity violations", duration)
                print("❌ Walk-forward validation FAILED")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('walk_forward_validation', 'failed', str(e), duration)
            print(f"❌ Walk-forward validation ERROR: {e}")
            return False
    
    def run_model_fraud_detection(self):
        """Layer 4: Model Fraud Detection"""
        
        print("\n🔍 LAYER 4: MODEL FRAUD DETECTION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            # Check strategy correlation matrix for fraud
            fraud_detected = False
            fraud_messages = []
            
            # Load strategy performance for correlation analysis
            perf_file = 'data/processed/performance/master.parquet'
            if os.path.exists(perf_file):
                perf_df = pd.read_parquet(perf_file)
                
                # Filter to only include strategies that still exist
                backtest_dir = 'data/processed/backtests'
                if os.path.exists(backtest_dir):
                    existing_strategies = [f.replace('.parquet', '') for f in os.listdir(backtest_dir) if f.endswith('.parquet')]
                    perf_df = perf_df[perf_df['strategy'].isin(existing_strategies)]
                
                # Create correlation matrix
                strategy_returns = perf_df.pivot(index='date', columns='strategy', values='daily_return')
                
                if len(strategy_returns.columns) > 1:
                    corr_matrix = strategy_returns.corr()
                    
                    # Check for suspiciously high correlations
                    np.fill_diagonal(corr_matrix.values, 0)
                    high_corr_pairs = []
                    
                    for i in range(len(corr_matrix.columns)):
                        for j in range(i+1, len(corr_matrix.columns)):
                            corr_val = abs(corr_matrix.iloc[i, j])
                            if corr_val > 0.85:  # Suspiciously high correlation
                                strategy1 = corr_matrix.columns[i]
                                strategy2 = corr_matrix.columns[j]
                                high_corr_pairs.append((strategy1, strategy2, corr_val))
                    
                    if high_corr_pairs:
                        fraud_detected = True
                        fraud_messages.append(f"High correlations detected: {len(high_corr_pairs)} pairs")
                        
                        for s1, s2, corr in high_corr_pairs[:3]:  # Show top 3
                            fraud_messages.append(f"  {s1} ↔ {s2}: {corr:.1%} correlation")
            
            # Check for impossible Sharpe ratios
            beliefs_file = 'data/processed/strategy_beliefs.parquet'
            if os.path.exists(beliefs_file):
                beliefs_df = pd.read_parquet(beliefs_file)
                
                # Check for suspiciously high skill probabilities
                high_skill = beliefs_df[beliefs_df['skill_prob'] > 0.9]
                if len(high_skill) > 0:
                    fraud_detected = True
                    fraud_messages.append(f"Suspiciously high skill detected: {len(high_skill)} strategies")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if not fraud_detected:
                self.log_execution('model_fraud_detection', 'success', 
                                 "No model fraud detected", duration)
                print("✅ Model fraud detection PASSED")
                return True
            else:
                fraud_summary = "; ".join(fraud_messages)
                self.log_execution('model_fraud_detection', 'failed', 
                                 fraud_summary, duration)
                print("❌ Model fraud detection FAILED")
                for msg in fraud_messages:
                    print(f"   🚨 {msg}")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('model_fraud_detection', 'failed', str(e), duration)
            print(f"❌ Model fraud detection ERROR: {e}")
            return False
    
    def generate_production_readiness_report(self):
        """Generate comprehensive production readiness report"""
        
        print("\n📊 GENERATING PRODUCTION READINESS REPORT")
        print("=" * 50)
        
        # Calculate overall readiness score
        passed_components = sum(1 for status in self.hardening_components.values() if status)
        total_components = len(self.hardening_components)
        readiness_score = passed_components / total_components
        
        # Determine readiness level
        if readiness_score >= 1.0:
            readiness_level = "PRODUCTION READY"
            readiness_color = "🟢"
        elif readiness_score >= 0.75:
            readiness_level = "MOSTLY READY"
            readiness_color = "🟡"
        else:
            readiness_level = "NOT READY"
            readiness_color = "🔴"
        
        # Create detailed report
        report = {
            'timestamp': datetime.now().isoformat(),
            'readiness_score': readiness_score,
            'readiness_level': readiness_level,
            'components': self.hardening_components,
            'execution_log': self.execution_log,
            'total_duration': sum(entry['duration_seconds'] for entry in self.execution_log),
            'recommendations': []
        }
        
        # Add recommendations for failed components
        if not self.hardening_components['data_integrity']:
            report['recommendations'].append("Fix data integrity violations before production")
        
        if not self.hardening_components['kill_switches']:
            report['recommendations'].append("Address portfolio risk violations")
        
        if not self.hardening_components['walk_forward_validation']:
            report['recommendations'].append("Fix temporal discipline violations")
        
        if not self.hardening_components['model_fraud_detection']:
            report['recommendations'].append("Address model fraud concerns")
        
        # Save report
        with open(self.paths['hardening_report'], 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate certificate if ready
        if readiness_score >= 1.0:
            certificate = {
                'certificate_id': f"NORTHSTAR_PROD_CERT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'issued_date': datetime.now().isoformat(),
                'system_name': "Northstar V3 Learning Financial Organism",
                'readiness_score': readiness_score,
                'validation_components': list(self.hardening_components.keys()),
                'certificate_status': "VALID",
                'valid_until': (datetime.now() + pd.Timedelta(days=30)).isoformat(),
                'issuer': "Production Hardening Engine",
                'notes': "System validated for real money deployment"
            }
            
            with open(self.paths['readiness_certificate'], 'w') as f:
                json.dump(certificate, f, indent=2, default=str)
        
        # Print summary
        print(f"   {readiness_color} READINESS LEVEL: {readiness_level}")
        print(f"   📊 Score: {readiness_score:.1%} ({passed_components}/{total_components} components)")
        print(f"   ⏱️ Total validation time: {report['total_duration']:.1f} seconds")
        
        if report['recommendations']:
            print(f"   📋 Recommendations:")
            for rec in report['recommendations']:
                print(f"     • {rec}")
        
        return report
    
    def run_complete_hardening(self):
        """Run complete production hardening validation"""
        
        print("🧬 PRODUCTION HARDENING ORCHESTRATOR")
        print("=" * 70)
        print("Making Northstar ready for real money")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Track overall execution
        system_start = datetime.now()
        
        # Run all hardening layers
        hardening_steps = [
            ('Data Integrity', self.run_data_integrity_check),
            ('Kill Switches', self.run_kill_switches_check),
            ('Walk-Forward Validation', self.run_walk_forward_validation),
            ('Model Fraud Detection', self.run_model_fraud_detection)
        ]
        
        for step_name, step_function in hardening_steps:
            success = step_function()
            if not success:
                print(f"\n⚠️ {step_name} failed - continuing with remaining validations...")
        
        # Generate production readiness report
        report = self.generate_production_readiness_report()
        
        # Calculate overall results
        total_duration = (datetime.now() - system_start).total_seconds()
        readiness_score = report['readiness_score']
        
        # Print final summary
        print(f"\n🧬 PRODUCTION HARDENING COMPLETE")
        print("=" * 70)
        print(f"⏱️  Total Duration: {total_duration:.1f} seconds")
        print(f"📊 Readiness Score: {readiness_score:.1%}")
        print(f"🧬 Component Status:")
        
        for component, status in self.hardening_components.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {component.replace('_', ' ').title()}")
        
        if readiness_score >= 1.0:
            print(f"\n🎉 NORTHSTAR IS PRODUCTION READY!")
            print("   All validation layers passed")
            print("   System is hardened for real money")
            print(f"   Certificate issued: {self.paths['readiness_certificate']}")
        elif readiness_score >= 0.75:
            print(f"\n⚠️ NORTHSTAR IS MOSTLY READY")
            print("   Some validation concerns remain")
            print("   Review recommendations before production")
        else:
            print(f"\n❌ NORTHSTAR IS NOT READY FOR PRODUCTION")
            print("   Critical validation failures detected")
            print("   Address all issues before real money deployment")
        
        return readiness_score >= 1.0

def main():
    """Main execution function"""
    
    hardening = ProductionHardening()
    is_ready = hardening.run_complete_hardening()
    
    return is_ready

if __name__ == "__main__":
    main()