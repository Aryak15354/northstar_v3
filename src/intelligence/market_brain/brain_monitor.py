#!/usr/bin/env python3
"""
🧠 MARKET BRAIN MONITOR - NORTHSTAR V3
Advanced monitoring and alerting for Market Brain system

This provides:
- Real-time brain health monitoring
- Force anomaly detection
- Regime change alerts
- Performance tracking
- Integration health checks
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class MarketBrainMonitor:
    """
    Market Brain Monitor - Advanced Health Monitoring
    
    Monitors all aspects of the Market Brain system:
    - Component health and data freshness
    - Force detection accuracy and stability
    - Survival instinct trigger patterns
    - V3 integration consistency
    - Performance metrics and alerts
    """
    
    def __init__(self):
        self.name = "Market Brain Monitor"
        self.version = "1.0"
        
        # Monitoring thresholds
        self.thresholds = {
            'data_freshness_hours': 24,      # Max age for data
            'pulse_intensity_max': 5.0,      # High intensity alert
            'pulse_intensity_min': 0.1,      # Low intensity alert
            'force_stability_window': 5,     # Periods for stability check
            'system_stress_high': 0.8,       # High stress threshold
            'exposure_change_alert': 0.2,    # 20% exposure change alert
            'component_failure_alert': 2     # Max failed components
        }
        
        # Paths
        self.paths = {
            'pulse_history': 'data/processed/pulse_history.parquet',
            'survival_metrics': 'data/processed/survival_metrics.parquet',
            'market_tensor': 'data/processed/market_tensor.parquet',
            'brain_alerts': 'data/processed/brain_alerts.json',
            'brain_performance': 'data/processed/brain_performance.json'
        }
    
    def check_component_health(self):
        """Check health of all Market Brain components"""
        
        print("🔍 CHECKING COMPONENT HEALTH")
        print("-" * 40)
        
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'overall_health': 'unknown',
            'alerts': []
        }
        
        # Check Market Tensor
        tensor_health = self.check_tensor_health()
        health_status['components']['tensor'] = tensor_health
        
        # Check Market Pulse
        pulse_health = self.check_pulse_health()
        health_status['components']['pulse'] = pulse_health
        
        # Check Survival Instincts
        survival_health = self.check_survival_health()
        health_status['components']['survival'] = survival_health
        
        # Check V3 Integration
        integration_health = self.check_integration_health()
        health_status['components']['integration'] = integration_health
        
        # Determine overall health
        component_scores = [comp['score'] for comp in health_status['components'].values()]
        avg_score = np.mean(component_scores)
        
        if avg_score >= 0.9:
            health_status['overall_health'] = 'excellent'
        elif avg_score >= 0.7:
            health_status['overall_health'] = 'good'
        elif avg_score >= 0.5:
            health_status['overall_health'] = 'fair'
        else:
            health_status['overall_health'] = 'poor'
        
        # Generate alerts
        failed_components = [name for name, comp in health_status['components'].items() 
                           if comp['score'] < 0.5]
        
        if len(failed_components) >= self.thresholds['component_failure_alert']:
            health_status['alerts'].append({
                'type': 'component_failure',
                'severity': 'high',
                'message': f"Multiple components failing: {failed_components}",
                'timestamp': datetime.now().isoformat()
            })
        
        print(f"   🎯 Overall Health: {health_status['overall_health'].upper()}")
        
        # Format component scores separately to avoid f-string backslash issue
        component_scores = [f'{name}: {comp["score"]:.2f}' for name, comp in health_status['components'].items()]
        print(f"   📊 Component Scores: {component_scores}")
        
        if health_status['alerts']:
            print(f"   🚨 Active Alerts: {len(health_status['alerts'])}")
        
        return health_status
    
    def check_tensor_health(self):
        """Check Market Tensor component health"""
        
        tensor_health = {
            'score': 0.0,
            'status': 'unknown',
            'issues': [],
            'metrics': {}
        }
        
        try:
            if os.path.exists(self.paths['market_tensor']):
                from .market_tensor import MarketTensorEngine
                tensor_raw = pd.read_parquet(self.paths['market_tensor'])
                tensor_df = MarketTensorEngine.canonicalize_tensor_frame(tensor_raw)
                
                # Check data freshness
                latest_date = tensor_df.index[-1]
                age_hours = (datetime.now() - latest_date).total_seconds() / 3600
                
                tensor_health['metrics']['age_hours'] = age_hours
                tensor_health['metrics']['shape'] = list(tensor_df.shape)
                tensor_health['metrics']['variables'] = len(tensor_df.columns)
                
                # Score based on freshness and completeness
                freshness_score = max(0, 1 - age_hours / (self.thresholds['data_freshness_hours'] * 2))
                completeness_score = min(1.0, len(tensor_df.columns) / 50)  # Expect ~50+ variables
                
                tensor_health['score'] = (freshness_score + completeness_score) / 2
                
                if age_hours > self.thresholds['data_freshness_hours']:
                    tensor_health['issues'].append(f"Data stale ({age_hours:.1f} hours old)")
                
                if len(tensor_df.columns) < 20:
                    tensor_health['issues'].append(f"Low variable count ({len(tensor_df.columns)})")
                
                tensor_health['status'] = 'healthy' if tensor_health['score'] > 0.7 else 'degraded'
                
            else:
                tensor_health['issues'].append("Market tensor file missing")
                tensor_health['status'] = 'failed'
                
        except Exception as e:
            tensor_health['issues'].append(f"Error checking tensor: {e}")
            tensor_health['status'] = 'error'
        
        return tensor_health
    
    def check_pulse_health(self):
        """Check Market Pulse component health"""
        
        pulse_health = {
            'score': 0.0,
            'status': 'unknown',
            'issues': [],
            'metrics': {}
        }
        
        try:
            # Check pulse state
            pulse_state_path = 'data/processed/pulse_state.json'
            if os.path.exists(pulse_state_path):
                with open(pulse_state_path, 'r') as f:
                    pulse_state = json.load(f)
                
                intensity = pulse_state.get('pulse_intensity', 0)
                forces_count = len(pulse_state.get('dominant_forces', {}))
                
                pulse_health['metrics']['intensity'] = intensity
                pulse_health['metrics']['forces_count'] = forces_count
                pulse_health['metrics']['phase'] = pulse_state.get('market_phase', 'unknown')
                
                # Score based on reasonable intensity and force detection
                intensity_score = 1.0 if 0.1 <= intensity <= 3.0 else 0.5
                forces_score = min(1.0, forces_count / 5)  # Expect ~5 forces
                
                pulse_health['score'] = (intensity_score + forces_score) / 2
                
                if intensity > self.thresholds['pulse_intensity_max']:
                    pulse_health['issues'].append(f"Very high pulse intensity ({intensity:.2f})")
                elif intensity < self.thresholds['pulse_intensity_min']:
                    pulse_health['issues'].append(f"Very low pulse intensity ({intensity:.2f})")
                
                if forces_count < 3:
                    pulse_health['issues'].append(f"Low force detection ({forces_count} forces)")
                
                pulse_health['status'] = 'healthy' if pulse_health['score'] > 0.7 else 'degraded'
                
            else:
                pulse_health['issues'].append("Pulse state file missing")
                pulse_health['status'] = 'failed'
                
        except Exception as e:
            pulse_health['issues'].append(f"Error checking pulse: {e}")
            pulse_health['status'] = 'error'
        
        return pulse_health
    
    def check_survival_health(self):
        """Check Survival Instincts component health"""
        
        survival_health = {
            'score': 0.0,
            'status': 'unknown',
            'issues': [],
            'metrics': {}
        }
        
        try:
            # Check survival state
            survival_state_path = 'data/processed/system_stress.json'
            if os.path.exists(survival_state_path):
                with open(survival_state_path, 'r') as f:
                    survival_state = json.load(f)
                
                mode = survival_state.get('survival_mode', 'unknown')
                emergency = survival_state.get('emergency_triggered', False)
                stress_level = survival_state.get('assessments', {}).get('system_stress', {}).get('stress_value', 0)
                
                survival_health['metrics']['mode'] = mode
                survival_health['metrics']['emergency'] = emergency
                survival_health['metrics']['stress_level'] = stress_level
                
                # Score based on normal operation
                mode_score = 1.0 if mode == 'normal' else 0.3
                emergency_score = 1.0 if not emergency else 0.0
                stress_score = max(0, 1 - stress_level)
                
                survival_health['score'] = (mode_score + emergency_score + stress_score) / 3
                
                if emergency:
                    survival_health['issues'].append("Emergency mode triggered")
                
                if stress_level > self.thresholds['system_stress_high']:
                    survival_health['issues'].append(f"High system stress ({stress_level:.3f})")
                
                if mode not in ['normal', 'cautious']:
                    survival_health['issues'].append(f"Unusual survival mode: {mode}")
                
                survival_health['status'] = 'healthy' if survival_health['score'] > 0.7 else 'degraded'
                
            else:
                survival_health['issues'].append("Survival state file missing")
                survival_health['status'] = 'failed'
                
        except Exception as e:
            survival_health['issues'].append(f"Error checking survival: {e}")
            survival_health['status'] = 'error'
        
        return survival_health
    
    def check_integration_health(self):
        """Check V3 Integration health"""
        
        integration_health = {
            'score': 0.0,
            'status': 'unknown',
            'issues': [],
            'metrics': {}
        }
        
        try:
            # Test V3 integration by running market state
            from src.cohesion.unified_state_manager import UnifiedStateManager
            
            market_engine = UnifiedStateManager()
            market_state = market_engine.compute_market_state()
            
            # Check brain integration fields
            brain_fields = ['pulse_intensity', 'market_phase', 'survival_mode', 'brain_active']
            integrated_fields = [field for field in brain_fields if field in market_state]
            
            integration_health['metrics']['integrated_fields'] = len(integrated_fields)
            integration_health['metrics']['total_fields'] = len(brain_fields)
            integration_health['metrics']['brain_active'] = market_state.get('brain_active', False)
            
            # Score based on integration completeness
            integration_score = len(integrated_fields) / len(brain_fields)
            active_score = 1.0 if market_state.get('brain_active', False) else 0.0
            
            integration_health['score'] = (integration_score + active_score) / 2
            
            if len(integrated_fields) < len(brain_fields):
                missing_fields = [f for f in brain_fields if f not in integrated_fields]
                integration_health['issues'].append(f"Missing brain fields: {missing_fields}")
            
            if not market_state.get('brain_active', False):
                integration_health['issues'].append("Brain not active in market state")
            
            integration_health['status'] = 'healthy' if integration_health['score'] > 0.8 else 'degraded'
            
        except Exception as e:
            integration_health['issues'].append(f"Error checking integration: {e}")
            integration_health['status'] = 'error'
        
        return integration_health
    
    def detect_anomalies(self):
        """Detect anomalies in Market Brain behavior"""
        
        print("\n🔍 DETECTING ANOMALIES")
        print("-" * 40)
        
        anomalies = []
        
        try:
            # Check pulse history for anomalies
            if os.path.exists(self.paths['pulse_history']):
                pulse_df = pd.read_parquet(self.paths['pulse_history'])
                
                if len(pulse_df) >= self.thresholds['force_stability_window']:
                    recent_pulses = pulse_df.tail(self.thresholds['force_stability_window'])
                    
                    # Check for sudden intensity spikes
                    intensity_std = recent_pulses['pulse_intensity'].std()
                    if intensity_std > 1.0:
                        anomalies.append({
                            'type': 'pulse_volatility',
                            'severity': 'medium',
                            'message': f"High pulse intensity volatility (std: {intensity_std:.3f})",
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    # Check for phase instability
                    phase_changes = (recent_pulses['market_phase'] != recent_pulses['market_phase'].shift()).sum()
                    if phase_changes > 3:
                        anomalies.append({
                            'type': 'phase_instability',
                            'severity': 'medium',
                            'message': f"Frequent phase changes ({phase_changes} in {len(recent_pulses)} periods)",
                            'timestamp': datetime.now().isoformat()
                        })
            
            # Check survival metrics for anomalies
            if os.path.exists(self.paths['survival_metrics']):
                survival_df = pd.read_parquet(self.paths['survival_metrics'])
                
                if len(survival_df) >= 3:
                    recent_survival = survival_df.tail(3)
                    
                    # Check for emergency triggers
                    emergency_count = recent_survival['emergency_triggered'].sum()
                    if emergency_count > 0:
                        anomalies.append({
                            'type': 'emergency_trigger',
                            'severity': 'high',
                            'message': f"Emergency triggered {emergency_count} times recently",
                            'timestamp': datetime.now().isoformat()
                        })
            
            print(f"   🎯 Anomalies detected: {len(anomalies)}")
            
            for anomaly in anomalies:
                severity_icon = "🚨" if anomaly['severity'] == 'high' else "⚠️"
                print(f"   {severity_icon} {anomaly['type']}: {anomaly['message']}")
            
        except Exception as e:
            print(f"   ❌ Anomaly detection error: {e}")
        
        return anomalies
    
    def generate_performance_report(self):
        """Generate Market Brain performance report"""
        
        print("\n📊 PERFORMANCE REPORT")
        print("-" * 40)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'period': '24h',
            'metrics': {},
            'trends': {},
            'recommendations': []
        }
        
        try:
            # Pulse performance metrics
            if os.path.exists(self.paths['pulse_history']):
                pulse_df = pd.read_parquet(self.paths['pulse_history'])
                
                if not pulse_df.empty:
                    recent_24h = pulse_df[pulse_df.index >= datetime.now() - timedelta(hours=24)]
                    
                    if not recent_24h.empty:
                        report['metrics']['pulse'] = {
                            'avg_intensity': float(recent_24h['pulse_intensity'].mean()),
                            'max_intensity': float(recent_24h['pulse_intensity'].max()),
                            'updates_count': len(recent_24h),
                            'dominant_phase': recent_24h['market_phase'].mode().iloc[0] if not recent_24h['market_phase'].mode().empty else 'unknown'
                        }
                        
                        print(f"   💓 Pulse Updates: {len(recent_24h)}")
                        print(f"   💓 Avg Intensity: {recent_24h['pulse_intensity'].mean():.2f}")
                        print(f"   💓 Dominant Phase: {report['metrics']['pulse']['dominant_phase']}")
            
            # Survival performance metrics
            if os.path.exists(self.paths['survival_metrics']):
                survival_df = pd.read_parquet(self.paths['survival_metrics'])
                
                if not survival_df.empty:
                    recent_24h = survival_df[survival_df.index >= datetime.now() - timedelta(hours=24)]
                    
                    if not recent_24h.empty:
                        report['metrics']['survival'] = {
                            'avg_stress': float(recent_24h['system_stress'].mean()),
                            'max_stress': float(recent_24h['system_stress'].max()),
                            'emergency_count': int(recent_24h['emergency_triggered'].sum()),
                            'mode_changes': int((recent_24h['survival_mode'] != recent_24h['survival_mode'].shift()).sum())
                        }
                        
                        print(f"   🛡️ Avg System Stress: {recent_24h['system_stress'].mean():.3f}")
                        print(f"   🛡️ Emergency Triggers: {int(recent_24h['emergency_triggered'].sum())}")
            
            # Generate recommendations
            if 'pulse' in report['metrics']:
                pulse_metrics = report['metrics']['pulse']
                
                if pulse_metrics['avg_intensity'] < 0.2:
                    report['recommendations'].append("Consider increasing market data frequency - low pulse intensity detected")
                
                if pulse_metrics['updates_count'] < 10:
                    report['recommendations'].append("Increase pulse update frequency for better market sensing")
            
            if 'survival' in report['metrics']:
                survival_metrics = report['metrics']['survival']
                
                if survival_metrics['avg_stress'] > 0.7:
                    report['recommendations'].append("High system stress detected - review risk parameters")
                
                if survival_metrics['emergency_count'] > 0:
                    report['recommendations'].append("Emergency triggers detected - investigate market conditions")
            
            print(f"   🎯 Recommendations: {len(report['recommendations'])}")
            for rec in report['recommendations']:
                print(f"   💡 {rec}")
            
        except Exception as e:
            print(f"   ❌ Performance report error: {e}")
        
        return report
    
    def run_complete_monitoring(self):
        """Run complete Market Brain monitoring suite"""
        
        print("🧠 MARKET BRAIN MONITORING SUITE")
        print("=" * 60)
        
        # Component health check
        health_status = self.check_component_health()
        
        # Anomaly detection
        anomalies = self.detect_anomalies()
        
        # Performance report
        performance_report = self.generate_performance_report()
        
        # Save monitoring results
        monitoring_results = {
            'timestamp': datetime.now().isoformat(),
            'health_status': health_status,
            'anomalies': anomalies,
            'performance_report': performance_report
        }
        
        # Save alerts
        if health_status['alerts'] or anomalies:
            all_alerts = health_status['alerts'] + anomalies
            
            try:
                os.makedirs(os.path.dirname(self.paths['brain_alerts']), exist_ok=True)
                with open(self.paths['brain_alerts'], 'w') as f:
                    json.dump(all_alerts, f, indent=2)
                print(f"\n💾 Saved {len(all_alerts)} alerts to {self.paths['brain_alerts']}")
            except Exception as e:
                print(f"\n❌ Could not save alerts: {e}")
        
        # Save performance data
        try:
            os.makedirs(os.path.dirname(self.paths['brain_performance']), exist_ok=True)
            with open(self.paths['brain_performance'], 'w') as f:
                json.dump(monitoring_results, f, indent=2)
            print(f"💾 Saved monitoring results to {self.paths['brain_performance']}")
        except Exception as e:
            print(f"❌ Could not save performance data: {e}")
        
        # Summary
        print(f"\n🎯 MONITORING SUMMARY")
        print("-" * 40)
        print(f"Overall Health: {health_status['overall_health'].upper()}")
        print(f"Active Alerts: {len(health_status['alerts'] + anomalies)}")
        print(f"Recommendations: {len(performance_report.get('recommendations', []))}")
        
        return monitoring_results

def main():
    """Run Market Brain monitoring"""
    
    monitor = MarketBrainMonitor()
    results = monitor.run_complete_monitoring()
    
    # Return success based on overall health
    overall_health = results['health_status']['overall_health']
    return overall_health in ['excellent', 'good']

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
