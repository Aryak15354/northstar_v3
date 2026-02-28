#!/usr/bin/env python3
"""
🧠 MARKET BRAIN DASHBOARD - NORTHSTAR V3
Advanced real-time dashboard for Market Brain intelligence

This provides:
- Real-time force visualization
- Regime transition tracking
- Survival instinct monitoring
- Performance analytics
- Integration status
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class MarketBrainDashboard:
    """
    Market Brain Dashboard - Real-time Intelligence Display
    
    Provides comprehensive real-time view of:
    - Current market forces and their evolution
    - Pulse intensity trends and patterns
    - Survival instinct status and triggers
    - V3 integration health and impact
    - Performance metrics and alerts
    """
    
    def __init__(self):
        self.name = "Market Brain Dashboard"
        self.version = "1.0"
        
        # Display configuration
        self.config = {
            'force_display_limit': 10,       # Top N forces to show
            'history_days': 7,               # Days of history to analyze
            'trend_periods': 24,             # Periods for trend analysis
            'alert_threshold_hours': 6       # Hours for alert freshness
        }
        
        # Paths
        self.paths = {
            'pulse_state': 'data/processed/pulse_state.json',
            'pulse_history': 'data/processed/pulse_history.parquet',
            'survival_state': 'data/processed/system_stress.json',
            'survival_metrics': 'data/processed/survival_metrics.parquet',
            'market_tensor': 'data/processed/market_tensor.parquet',
            'brain_alerts': 'data/processed/brain_alerts.json',
            'brain_performance': 'data/processed/brain_performance.json'
        }
    
    def display_current_pulse(self):
        """Display current market pulse status"""
        
        print("💓 CURRENT MARKET PULSE")
        print("=" * 50)
        
        try:
            if os.path.exists(self.paths['pulse_state']):
                with open(self.paths['pulse_state'], 'r') as f:
                    pulse_state = json.load(f)
                
                # Basic pulse metrics
                intensity = pulse_state.get('pulse_intensity', 0)
                phase = pulse_state.get('market_phase', 'unknown')
                risk_level = pulse_state.get('risk_level', 'unknown')
                timestamp = pulse_state.get('timestamp', 'unknown')
                
                # Display main metrics
                intensity_bar = self.create_intensity_bar(intensity)
                phase_icon = self.get_phase_icon(phase)
                risk_icon = self.get_risk_icon(risk_level)
                
                print(f"🎯 Intensity: {intensity:.2f} {intensity_bar}")
                print(f"{phase_icon} Phase: {phase.title()}")
                print(f"{risk_icon} Risk Level: {risk_level.title()}")
                print(f"⏰ Updated: {self.format_timestamp(timestamp)}")
                
                # Display dominant forces
                forces = pulse_state.get('dominant_forces', {})
                if forces:
                    print(f"\n⚡ DOMINANT FORCES (Top {min(len(forces), self.config['force_display_limit'])})")
                    print("-" * 30)
                    
                    sorted_forces = sorted(forces.items(), 
                                         key=lambda x: abs(x[1].get('strength', 0)), 
                                         reverse=True)
                    
                    for i, (force_name, force_data) in enumerate(sorted_forces[:self.config['force_display_limit']]):
                        strength = force_data.get('strength', 0)
                        direction = force_data.get('direction', 'neutral')
                        
                        direction_icon = "↑" if direction == 'up' else "↓" if direction == 'down' else "→"
                        strength_bar = self.create_strength_bar(strength)
                        
                        print(f"  {i+1:2d}. {force_name[:25]:25s} {strength:6.2f} {direction_icon} {strength_bar}")
                
                # Display force categories
                self.display_force_categories(forces)
                
            else:
                print("❌ Pulse state not available")
                
        except Exception as e:
            print(f"❌ Error displaying pulse: {e}")
    
    def display_force_categories(self, forces):
        """Display forces grouped by category"""
        
        if not forces:
            return
        
        # Categorize forces
        categories = {
            'Monetary': [],
            'Corporate': [],
            'Sector': [],
            'Flow': [],
            'Structure': [],
            'Other': []
        }
        
        for force_name, force_data in forces.items():
            strength = force_data.get('strength', 0)
            direction = force_data.get('direction', 'neutral')
            
            if 'rbi' in force_name.lower() or 'macro' in force_name.lower():
                categories['Monetary'].append((force_name, strength, direction))
            elif 'corp' in force_name.lower() or 'factor' in force_name.lower():
                categories['Corporate'].append((force_name, strength, direction))
            elif any(sector in force_name.lower() for sector in ['sector', 'industry']):
                categories['Sector'].append((force_name, strength, direction))
            elif 'flow' in force_name.lower():
                categories['Flow'].append((force_name, strength, direction))
            elif any(struct in force_name.lower() for struct in ['nifty', 'breadth', 'volatility']):
                categories['Structure'].append((force_name, strength, direction))
            else:
                categories['Other'].append((force_name, strength, direction))
        
        print(f"\n🏷️ FORCE CATEGORIES")
        print("-" * 30)
        
        for category, force_list in categories.items():
            if force_list:
                avg_strength = np.mean([abs(f[1]) for f in force_list])
                force_count = len(force_list)
                
                category_icon = self.get_category_icon(category)
                print(f"  {category_icon} {category:12s}: {force_count:2d} forces (avg: {avg_strength:.2f})")
    
    def display_pulse_trends(self):
        """Display pulse trends and patterns"""
        
        print(f"\n📈 PULSE TRENDS ({self.config['history_days']} days)")
        print("=" * 50)
        
        try:
            if os.path.exists(self.paths['pulse_history']):
                pulse_df = pd.read_parquet(self.paths['pulse_history'])
                
                if not pulse_df.empty:
                    # Filter to recent history
                    cutoff_date = datetime.now() - timedelta(days=self.config['history_days'])
                    
                    # Ensure index is datetime
                    if not isinstance(pulse_df.index, pd.DatetimeIndex):
                        pulse_df.index = pd.to_datetime(pulse_df.index)
                    
                    recent_df = pulse_df[pulse_df.index >= cutoff_date]
                    
                    if not recent_df.empty:
                        # Intensity trends
                        current_intensity = recent_df['pulse_intensity'].iloc[-1]
                        avg_intensity = recent_df['pulse_intensity'].mean()
                        max_intensity = recent_df['pulse_intensity'].max()
                        min_intensity = recent_df['pulse_intensity'].min()
                        
                        intensity_trend = self.calculate_trend(recent_df['pulse_intensity'])
                        trend_icon = "📈" if intensity_trend > 0.1 else "📉" if intensity_trend < -0.1 else "➡️"
                        
                        print(f"💓 Intensity Metrics:")
                        print(f"   Current: {current_intensity:.2f}")
                        print(f"   Average: {avg_intensity:.2f}")
                        print(f"   Range: {min_intensity:.2f} - {max_intensity:.2f}")
                        print(f"   Trend: {trend_icon} {intensity_trend:+.3f}")
                        
                        # Phase distribution
                        phase_counts = recent_df['market_phase'].value_counts()
                        print(f"\n🎯 Phase Distribution:")
                        for phase, count in phase_counts.items():
                            percentage = count / len(recent_df) * 100
                            phase_icon = self.get_phase_icon(phase)
                            print(f"   {phase_icon} {phase.title():12s}: {count:3d} ({percentage:5.1f}%)")
                        
                        # Risk level distribution
                        if 'risk_level' in recent_df.columns:
                            risk_counts = recent_df['risk_level'].value_counts()
                            print(f"\n⚠️ Risk Distribution:")
                            for risk, count in risk_counts.items():
                                percentage = count / len(recent_df) * 100
                                risk_icon = self.get_risk_icon(risk)
                                print(f"   {risk_icon} {risk.title():12s}: {count:3d} ({percentage:5.1f}%)")
                        
                        # Recent activity
                        recent_24h = recent_df[recent_df.index >= datetime.now() - timedelta(hours=24)]
                        print(f"\n⏰ Recent Activity (24h):")
                        print(f"   Updates: {len(recent_24h)}")
                        print(f"   Avg Intensity: {recent_24h['pulse_intensity'].mean():.2f}")
                        
                        if len(recent_24h) > 1:
                            intensity_volatility = recent_24h['pulse_intensity'].std()
                            print(f"   Volatility: {intensity_volatility:.3f}")
                    
                    else:
                        print("❌ No recent pulse data available")
                else:
                    print("❌ Pulse history is empty")
            else:
                print("❌ Pulse history not available")
                
        except Exception as e:
            print(f"❌ Error displaying trends: {e}")
    
    def display_survival_status(self):
        """Display survival instinct status"""
        
        print(f"\n🛡️ SURVIVAL INSTINCTS")
        print("=" * 50)
        
        try:
            if os.path.exists(self.paths['survival_state']):
                with open(self.paths['survival_state'], 'r') as f:
                    survival_state = json.load(f)
                
                # Main survival metrics
                mode = survival_state.get('survival_mode', 'unknown')
                emergency = survival_state.get('emergency_triggered', False)
                timestamp = survival_state.get('timestamp', 'unknown')
                
                mode_icon = "🚨" if emergency else "✅" if mode == 'normal' else "⚠️"
                emergency_text = " 🚨 EMERGENCY ACTIVE" if emergency else ""
                
                print(f"{mode_icon} Mode: {mode.upper()}{emergency_text}")
                print(f"⏰ Updated: {self.format_timestamp(timestamp)}")
                
                # Assessment details
                assessments = survival_state.get('assessments', {})
                if assessments:
                    print(f"\n🔍 SYSTEM ASSESSMENTS")
                    print("-" * 30)
                    
                    for assessment_name, assessment_data in assessments.items():
                        if isinstance(assessment_data, dict):
                            stress_level = assessment_data.get('stress_level', 'unknown')
                            stress_value = assessment_data.get('stress_value', 0)
                            
                            stress_icon = "🔴" if stress_level == 'high' else "🟡" if stress_level == 'medium' else "🟢"
                            
                            print(f"  {stress_icon} {assessment_name.replace('_', ' ').title():20s}: {stress_level} ({stress_value:.3f})")
                
                # Action parameters
                action_params = survival_state.get('action_parameters', {})
                if action_params:
                    print(f"\n⚙️ ACTION PARAMETERS")
                    print("-" * 30)
                    
                    exposure_mult = action_params.get('exposure_multiplier', 1.0)
                    position_limit = action_params.get('position_size_limit', 1.0)
                    
                    print(f"  📊 Exposure Multiplier: {exposure_mult:.1%}")
                    print(f"  📏 Position Limit: {position_limit:.1%}")
                
                # Recommendations
                recommendations = survival_state.get('recommendations', [])
                if recommendations:
                    print(f"\n💡 RECOMMENDATIONS")
                    print("-" * 30)
                    for i, rec in enumerate(recommendations, 1):
                        print(f"  {i}. {rec}")
                
            else:
                print("❌ Survival state not available")
                
        except Exception as e:
            print(f"❌ Error displaying survival status: {e}")
    
    def display_integration_status(self):
        """Display V3 integration status"""
        
        print(f"\n🔗 V3 INTEGRATION STATUS")
        print("=" * 50)
        
        try:
            import sys
            from src.cohesion.unified_state_manager import UnifiedStateManager
            
            market_engine = UnifiedStateManager()
            market_state = market_engine.compute_market_state()
            
            # Check brain integration
            brain_fields = {
                'pulse_intensity': 'Pulse Intensity',
                'market_phase': 'Market Phase',
                'survival_mode': 'Survival Mode',
                'brain_active': 'Brain Active',
                'regime_similarity': 'Regime Similarity'
            }
            
            print("🧠 BRAIN INTEGRATION FIELDS")
            print("-" * 30)
            
            for field_key, field_name in brain_fields.items():
                if field_key in market_state:
                    value = market_state[field_key]
                    status_icon = "✅"
                    
                    if isinstance(value, bool):
                        display_value = "Yes" if value else "No"
                    elif isinstance(value, (int, float)):
                        display_value = f"{value:.3f}"
                    else:
                        display_value = str(value)
                    
                    print(f"  {status_icon} {field_name:20s}: {display_value}")
                else:
                    print(f"  ❌ {field_name:20s}: Missing")
            
            # Integration impact
            print(f"\n📊 INTEGRATION IMPACT")
            print("-" * 30)
            
            allowed_exposure = market_state.get('allowed_exposure', 0)
            risk_on_prob = market_state.get('risk_on_probability', 0)
            macro_regime = market_state.get('macro_regime', 'unknown')
            
            print(f"  🎯 Allowed Exposure: {allowed_exposure:.1f}%")
            print(f"  📈 Risk-On Probability: {risk_on_prob:.1%}")
            print(f"  🏛️ Macro Regime: {macro_regime}")
            
            # Market breadth from integration
            breadth_pct = market_state.get('breadth_pct', 0)
            participation = market_state.get('participation_score', 0)
            
            print(f"  📊 Market Breadth: {breadth_pct:.0f}%")
            print(f"  🎭 Participation: {participation}")
            
        except Exception as e:
            print(f"❌ Error displaying integration status: {e}")
    
    def display_alerts_and_performance(self):
        """Display active alerts and performance metrics"""
        
        print(f"\n🚨 ALERTS & PERFORMANCE")
        print("=" * 50)
        
        # Display active alerts
        try:
            if os.path.exists(self.paths['brain_alerts']):
                with open(self.paths['brain_alerts'], 'r') as f:
                    alerts = json.load(f)
                
                # Filter recent alerts
                recent_alerts = []
                cutoff_time = datetime.now() - timedelta(hours=self.config['alert_threshold_hours'])
                
                for alert in alerts:
                    try:
                        alert_time = datetime.fromisoformat(alert.get('timestamp', ''))
                        if alert_time >= cutoff_time:
                            recent_alerts.append(alert)
                    except:
                        recent_alerts.append(alert)  # Include if timestamp parsing fails
                
                if recent_alerts:
                    print("🚨 ACTIVE ALERTS")
                    print("-" * 30)
                    
                    for alert in recent_alerts:
                        severity = alert.get('severity', 'unknown')
                        alert_type = alert.get('type', 'unknown')
                        message = alert.get('message', 'No message')
                        
                        severity_icon = "🚨" if severity == 'high' else "⚠️" if severity == 'medium' else "ℹ️"
                        
                        print(f"  {severity_icon} {alert_type}: {message}")
                else:
                    print("✅ No active alerts")
            else:
                print("ℹ️ No alert data available")
        
        except Exception as e:
            print(f"❌ Error displaying alerts: {e}")
        
        # Display performance metrics
        try:
            if os.path.exists(self.paths['brain_performance']):
                with open(self.paths['brain_performance'], 'r') as f:
                    performance = json.load(f)
                
                perf_report = performance.get('performance_report', {})
                health_status = performance.get('health_status', {})
                
                print(f"\n📊 PERFORMANCE METRICS")
                print("-" * 30)
                
                # Overall health
                overall_health = health_status.get('overall_health', 'unknown')
                health_icon = "🟢" if overall_health == 'excellent' else "🟡" if overall_health == 'good' else "🔴"
                print(f"  {health_icon} Overall Health: {overall_health.title()}")
                
                # Component scores
                components = health_status.get('components', {})
                if components:
                    print(f"  📊 Component Scores:")
                    for comp_name, comp_data in components.items():
                        score = comp_data.get('score', 0)
                        status = comp_data.get('status', 'unknown')
                        
                        score_icon = "🟢" if score > 0.8 else "🟡" if score > 0.5 else "🔴"
                        print(f"     {score_icon} {comp_name.title():12s}: {score:.2f} ({status})")
                
                # Performance metrics
                metrics = perf_report.get('metrics', {})
                if metrics:
                    print(f"  ⚡ Recent Activity:")
                    
                    pulse_metrics = metrics.get('pulse', {})
                    if pulse_metrics:
                        updates = pulse_metrics.get('updates_count', 0)
                        avg_intensity = pulse_metrics.get('avg_intensity', 0)
                        print(f"     💓 Pulse Updates: {updates} (avg intensity: {avg_intensity:.2f})")
                    
                    survival_metrics = metrics.get('survival', {})
                    if survival_metrics:
                        avg_stress = survival_metrics.get('avg_stress', 0)
                        emergency_count = survival_metrics.get('emergency_count', 0)
                        print(f"     🛡️ Avg Stress: {avg_stress:.3f} (emergencies: {emergency_count})")
            
        except Exception as e:
            print(f"❌ Error displaying performance: {e}")
    
    def create_intensity_bar(self, intensity, max_width=20):
        """Create visual intensity bar"""
        
        # Normalize intensity to 0-1 scale (assuming max intensity of 5)
        normalized = min(intensity / 5.0, 1.0)
        filled_width = int(normalized * max_width)
        
        bar = "█" * filled_width + "░" * (max_width - filled_width)
        return f"[{bar}]"
    
    def create_strength_bar(self, strength, max_width=10):
        """Create visual strength bar"""
        
        # Normalize strength to 0-1 scale (assuming max strength of 10)
        normalized = min(abs(strength) / 10.0, 1.0)
        filled_width = int(normalized * max_width)
        
        bar = "█" * filled_width + "░" * (max_width - filled_width)
        return f"[{bar}]"
    
    def get_phase_icon(self, phase):
        """Get icon for market phase"""
        
        phase_icons = {
            'expansion': '📈',
            'peak': '🔝',
            'contraction': '📉',
            'trough': '🔻',
            'neutral': '➡️',
            'crisis': '🚨',
            'recovery': '🔄'
        }
        
        return phase_icons.get(phase.lower(), '❓')
    
    def get_risk_icon(self, risk_level):
        """Get icon for risk level"""
        
        risk_icons = {
            'low': '🟢',
            'medium': '🟡',
            'high': '🔴',
            'extreme': '🚨'
        }
        
        return risk_icons.get(risk_level.lower(), '❓')
    
    def get_category_icon(self, category):
        """Get icon for force category"""
        
        category_icons = {
            'Monetary': '💰',
            'Corporate': '🏢',
            'Sector': '🏭',
            'Flow': '💧',
            'Structure': '🏗️',
            'Other': '❓'
        }
        
        return category_icons.get(category, '❓')
    
    def calculate_trend(self, series):
        """Calculate trend direction"""
        
        if len(series) < 2:
            return 0
        
        # Simple linear trend
        x = np.arange(len(series))
        y = series.values
        
        # Calculate slope
        slope = np.polyfit(x, y, 1)[0]
        return slope
    
    def format_timestamp(self, timestamp_str):
        """Format timestamp for display"""
        
        try:
            if timestamp_str and timestamp_str != 'unknown':
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                age = datetime.now() - dt.replace(tzinfo=None)
                
                if age.total_seconds() < 3600:  # Less than 1 hour
                    minutes = int(age.total_seconds() / 60)
                    return f"{minutes}m ago"
                elif age.total_seconds() < 86400:  # Less than 1 day
                    hours = int(age.total_seconds() / 3600)
                    return f"{hours}h ago"
                else:
                    days = int(age.total_seconds() / 86400)
                    return f"{days}d ago"
            else:
                return "Unknown"
        except:
            return "Unknown"
    
    def run_complete_dashboard(self):
        """Run complete Market Brain dashboard"""
        
        print("🧠 MARKET BRAIN INTELLIGENCE DASHBOARD")
        print("=" * 60)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Display all sections
        self.display_current_pulse()
        self.display_pulse_trends()
        self.display_survival_status()
        self.display_integration_status()
        self.display_alerts_and_performance()
        
        print(f"\n🎯 Dashboard refresh completed at {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)

def main():
    """Run Market Brain dashboard"""
    
    dashboard = MarketBrainDashboard()
    dashboard.run_complete_dashboard()
    
    return True

if __name__ == "__main__":
    main()