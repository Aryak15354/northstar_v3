#!/usr/bin/env python3
"""
Black Swan Snapshot Script for Northstar V2

Captures comprehensive system state during extreme market events.
"""

import sys
import os
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.options.clock_guard import ClockGuard
from src.options.state_recovery import StateRecoveryManager
from src.options.accounting_integrity import AccountingIntegrityChecker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BlackSwanSnapshotTaker:
    """Captures comprehensive system state during black swan events"""
    
    def __init__(self):
        self.snapshot_time = datetime.now()
        self.clock_guard = ClockGuard()
        self.recovery_manager = StateRecoveryManager(PROJECT_ROOT / "data/options/live")
        self.integrity_checker = AccountingIntegrityChecker()
        
        # Output directory
        self.output_dir = PROJECT_ROOT / "data/options/live/black_swan_snapshots"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def take_immediate_snapshot(self) -> Dict[str, Any]:
        """Take immediate snapshot for first response"""
        logger.info("🚨 TAKING IMMEDIATE BLACK SWAN SNAPSHOT")
        logger.info("=" * 60)
        
        snapshot = {
            'snapshot_type': 'immediate',
            'timestamp': self.snapshot_time.isoformat(),
            'event_detected_at': self.snapshot_time.isoformat(),
            'sections': {}
        }
        
        # Critical immediate checks
        snapshot['sections']['system_mode'] = self.capture_system_mode()
        snapshot['sections']['position_exposure'] = self.capture_position_exposure()
        snapshot['sections']['market_conditions'] = self.capture_market_conditions()
        snapshot['sections']['system_status'] = self.capture_system_status()
        snapshot['sections']['immediate_risks'] = self.assess_immediate_risks()
        
        return snapshot
    
    def take_comprehensive_snapshot(self) -> Dict[str, Any]:
        """Take comprehensive snapshot for detailed analysis"""
        logger.info("📊 TAKING COMPREHENSIVE BLACK SWAN SNAPSHOT")
        logger.info("=" * 60)
        
        snapshot = {
            'snapshot_type': 'comprehensive',
            'timestamp': self.snapshot_time.isoformat(),
            'event_detected_at': self.snapshot_time.isoformat(),
            'sections': {}
        }
        
        # All sections for comprehensive analysis
        snapshot['sections']['system_mode'] = self.capture_system_mode()
        snapshot['sections']['position_exposure'] = self.capture_position_exposure()
        snapshot['sections']['market_conditions'] = self.capture_market_conditions()
        snapshot['sections']['system_status'] = self.capture_system_status()
        snapshot['sections']['governance_state'] = self.capture_governance_state()
        snapshot['sections']['risk_metrics'] = self.capture_risk_metrics()
        snapshot['sections']['performance_impact'] = self.capture_performance_impact()
        snapshot['sections']['liquidity_assessment'] = self.capture_liquidity_assessment()
        snapshot['sections']['correlation_analysis'] = self.capture_correlation_analysis()
        snapshot['sections']['system_resources'] = self.capture_system_resources()
        snapshot['sections']['recent_events'] = self.capture_recent_events()
        
        return snapshot
    
    def capture_system_mode(self) -> Dict[str, Any]:
        """Capture current system mode and constraints"""
        mode_info = {
            'current_mode': 'unknown',
            'mode_entered_at': None,
            'constraints_active': {},
            'auto_responses_triggered': []
        }
        
        try:
            runtime_file = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
            if runtime_file.exists():
                with open(runtime_file, 'r') as f:
                    runtime_state = json.load(f)
                
                mode_info.update({
                    'current_mode': runtime_state.get('current_mode', 'unknown'),
                    'mode_entered_at': runtime_state.get('mode_entered_at'),
                    'constraints_active': runtime_state.get('mode_constraints', runtime_state.get('constraints_active', {})),
                    'block_new_risk': runtime_state.get('block_new_risk', False),
                    'last_governance_check': runtime_state.get('last_governance_check')
                })
            
        except Exception as e:
            mode_info['error'] = str(e)
        
        return mode_info
    
    def capture_position_exposure(self) -> Dict[str, Any]:
        """Capture current position exposure and risk"""
        exposure_info = {
            'total_positions': 0,
            'total_risk': 0.0,
            'total_pnl': 0.0,
            'short_vol_exposure': 0.0,
            'long_vol_exposure': 0.0,
            'position_breakdown': {},
            'high_risk_positions': []
        }
        
        try:
            runtime_file = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
            if runtime_file.exists():
                with open(runtime_file, 'r') as f:
                    runtime_state = json.load(f)
                
                open_positions = runtime_state.get('open_positions', [])
                exposure_info['total_positions'] = len(open_positions)
                
                # Analyze positions
                for position in open_positions:
                    position_risk = float(position.get('max_loss', position.get('max_risk', 0.0)) or 0.0)
                    position_pnl = float(position.get('unrealized_pnl', position.get('current_pnl', 0.0)) or 0.0)
                    strategy_type = position.get('strategy_type', 'unknown')
                    underlying = position.get('underlying', 'unknown')
                    
                    exposure_info['total_risk'] += position_risk
                    exposure_info['total_pnl'] += position_pnl
                    
                    # Categorize by strategy type
                    if strategy_type not in exposure_info['position_breakdown']:
                        exposure_info['position_breakdown'][strategy_type] = {
                            'count': 0,
                            'total_risk': 0.0,
                            'total_pnl': 0.0
                        }
                    
                    exposure_info['position_breakdown'][strategy_type]['count'] += 1
                    exposure_info['position_breakdown'][strategy_type]['total_risk'] += position_risk
                    exposure_info['position_breakdown'][strategy_type]['total_pnl'] += position_pnl
                    
                    # Identify short/long vol exposure
                    if 'short' in strategy_type.lower() or 'sell' in strategy_type.lower():
                        exposure_info['short_vol_exposure'] += position_risk
                    elif 'long' in strategy_type.lower() or 'buy' in strategy_type.lower():
                        exposure_info['long_vol_exposure'] += position_risk
                    
                    # Flag high-risk positions
                    if position_risk > 10000 or position_pnl < -5000:  # Thresholds
                        exposure_info['high_risk_positions'].append({
                            'position_id': position.get('position_id'),
                            'underlying': underlying,
                            'strategy_type': strategy_type,
                            'risk': position_risk,
                            'pnl': position_pnl
                        })
            
        except Exception as e:
            exposure_info['error'] = str(e)
        
        return exposure_info
    
    def capture_market_conditions(self) -> Dict[str, Any]:
        """Capture current market conditions"""
        market_info = {
            'vix_level': None,
            'market_prices': {},
            'volatility_metrics': {},
            'correlation_metrics': {},
            'market_status': 'unknown'
        }
        
        try:
            # Get market time info
            market_time_info = self.clock_guard.get_market_time_info()
            market_info['market_status'] = market_time_info.get('market_status', 'unknown')
            market_info['current_time_ist'] = market_time_info.get('current_time')
            
            # Load latest market data
            market_data_file = PROJECT_ROOT / "data/options/live/market_data_latest.json"
            if market_data_file.exists():
                with open(market_data_file, 'r') as f:
                    market_data = json.load(f)
                
                market_info.update({
                    'vix_level': market_data.get('vix_level'),
                    'market_prices': {
                        'NIFTY': market_data.get('NIFTY_price'),
                        'BANKNIFTY': market_data.get('BANKNIFTY_price'),
                        'FINNIFTY': market_data.get('FINNIFTY_price')
                    },
                    'volatility_metrics': {
                        'realized_vol': market_data.get('realized_vol'),
                        'vol_of_vol': market_data.get('vol_of_vol')
                    },
                    'correlation_metrics': {
                        'implied_corr': market_data.get('implied_corr'),
                        'realized_corr': market_data.get('realized_corr')
                    }
                })
            
        except Exception as e:
            market_info['error'] = str(e)
        
        return market_info
    
    def capture_system_status(self) -> Dict[str, Any]:
        """Capture system operational status"""
        system_info = {
            'daemon_running': False,
            'live_engine_running': False,
            'heartbeat_status': 'unknown',
            'process_locks': {},
            'resource_usage': {}
        }
        
        try:
            # Check daemon status
            daemon_status_file = PROJECT_ROOT / "data/options/live/northstar_daemon_status.json"
            if daemon_status_file.exists():
                with open(daemon_status_file, 'r') as f:
                    daemon_status = json.load(f)
                
                system_info.update({
                    'daemon_running': True,
                    'daemon_pid': daemon_status.get('daemon_pid'),
                    'daemon_uptime_seconds': daemon_status.get('uptime_seconds'),
                    'resource_usage': daemon_status.get('resource_usage', {})
                })
                
                # Check process status
                processes = daemon_status.get('processes', {})
                system_info['live_engine_running'] = processes.get('live_engine', {}).get('running', False)
            
            # Check heartbeat
            heartbeat_file = PROJECT_ROOT / "data/options/live/live_engine_heartbeat.json"
            if heartbeat_file.exists():
                with open(heartbeat_file, 'r') as f:
                    heartbeat = json.load(f)
                
                last_heartbeat = datetime.fromisoformat(heartbeat['timestamp'])
                now_ref = datetime.now(last_heartbeat.tzinfo) if last_heartbeat.tzinfo else datetime.now()
                age_minutes = (now_ref - last_heartbeat).total_seconds() / 60
                
                system_info['heartbeat_status'] = 'fresh' if age_minutes < 10 else 'stale'
                system_info['heartbeat_age_minutes'] = age_minutes
            
        except Exception as e:
            system_info['error'] = str(e)
        
        return system_info
    
    def assess_immediate_risks(self) -> Dict[str, Any]:
        """Assess immediate risks requiring attention"""
        risk_assessment = {
            'critical_risks': [],
            'high_risks': [],
            'medium_risks': [],
            'overall_risk_level': 'unknown'
        }
        
        try:
            # Load current state for analysis
            runtime_file = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
            if runtime_file.exists():
                with open(runtime_file, 'r') as f:
                    runtime_state = json.load(f)
                
                # Check for critical risks
                current_mode = runtime_state.get('current_mode', 'normal_operation')
                if current_mode == 'survival_core':
                    risk_assessment['critical_risks'].append({
                        'risk': 'System in Survival Core mode',
                        'impact': 'High',
                        'action_required': 'Immediate position review'
                    })
                
                # Check position concentration
                open_positions = runtime_state.get('open_positions', [])
                total_risk = sum(float(pos.get('max_loss', pos.get('max_risk', 0.0)) or 0.0) for pos in open_positions)
                net_equity = runtime_state.get('net_equity', 100000)
                
                if total_risk > net_equity * 0.5:  # >50% of equity at risk
                    risk_assessment['high_risks'].append({
                        'risk': 'High position concentration',
                        'impact': f'Risk: ₹{total_risk:,.0f} ({total_risk/net_equity*100:.1f}% of equity)',
                        'action_required': 'Consider position reduction'
                    })
                
                # Check for large unrealized losses
                unrealized_pnl = runtime_state.get('unrealized_pnl', 0)
                if unrealized_pnl < -net_equity * 0.05:  # >5% unrealized loss
                    risk_assessment['high_risks'].append({
                        'risk': 'Large unrealized losses',
                        'impact': f'Unrealized P&L: ₹{unrealized_pnl:,.0f}',
                        'action_required': 'Review position exits'
                    })
            
            # Determine overall risk level
            if risk_assessment['critical_risks']:
                risk_assessment['overall_risk_level'] = 'critical'
            elif risk_assessment['high_risks']:
                risk_assessment['overall_risk_level'] = 'high'
            elif risk_assessment['medium_risks']:
                risk_assessment['overall_risk_level'] = 'medium'
            else:
                risk_assessment['overall_risk_level'] = 'low'
            
        except Exception as e:
            risk_assessment['error'] = str(e)
        
        return risk_assessment
    
    def capture_governance_state(self) -> Dict[str, Any]:
        """Capture governance events and state"""
        governance_info = {
            'recent_events': [],
            'unresolved_events': [],
            'mode_transitions_today': [],
            'alert_count_24h': 0
        }
        
        try:
            events_file = PROJECT_ROOT / "data/options/live/governance_events.parquet"
            if events_file.exists():
                df = pd.read_parquet(events_file)
                
                # Recent events (last 4 hours)
                cutoff_time = self.snapshot_time - pd.Timedelta(hours=4)
                recent_events = df[pd.to_datetime(df['timestamp']) >= cutoff_time]
                
                governance_info['recent_events'] = recent_events[
                    ['timestamp', 'event_type', 'severity', 'details']
                ].to_dict('records')
                
                # Unresolved events
                unresolved = df[df['resolved_at'].isna()]
                governance_info['unresolved_events'] = unresolved[
                    ['timestamp', 'event_type', 'severity']
                ].to_dict('records')
                
                # Mode transitions today
                today_start = self.snapshot_time.replace(hour=0, minute=0, second=0, microsecond=0)
                today_events = df[pd.to_datetime(df['timestamp']) >= today_start]
                mode_transitions = today_events[today_events['event_type'] == 'mode_transition']
                
                governance_info['mode_transitions_today'] = mode_transitions[
                    ['timestamp', 'mode_before', 'mode_after']
                ].to_dict('records')
                
                # Alert count (24h)
                alert_cutoff = self.snapshot_time - pd.Timedelta(hours=24)
                alerts_24h = df[
                    (pd.to_datetime(df['timestamp']) >= alert_cutoff) &
                    (df['severity'].isin(['warning', 'error', 'critical']))
                ]
                governance_info['alert_count_24h'] = len(alerts_24h)
            
        except Exception as e:
            governance_info['error'] = str(e)
        
        return governance_info
    
    def capture_risk_metrics(self) -> Dict[str, Any]:
        """Capture detailed risk metrics"""
        # Placeholder - would implement detailed risk calculations
        return {
            'var_95': 0.0,
            'cvar_95': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'beta_to_market': 0.0,
            'correlation_breakdown': False
        }
    
    def capture_performance_impact(self) -> Dict[str, Any]:
        """Capture performance impact of the event"""
        # Placeholder - would calculate performance impact
        return {
            'pnl_impact_estimate': 0.0,
            'worst_case_scenario': 0.0,
            'time_to_recovery_estimate': 'unknown'
        }
    
    def capture_liquidity_assessment(self) -> Dict[str, Any]:
        """Assess position liquidity"""
        # Placeholder - would assess bid-ask spreads and market depth
        return {
            'liquid_positions': 0,
            'illiquid_positions': 0,
            'avg_bid_ask_spread': 0.0,
            'exit_difficulty_score': 'medium'
        }
    
    def capture_correlation_analysis(self) -> Dict[str, Any]:
        """Analyze correlation breakdown"""
        # Placeholder - would analyze correlation changes
        return {
            'correlation_breakdown_detected': False,
            'correlation_change_magnitude': 0.0,
            'affected_strategies': []
        }
    
    def capture_system_resources(self) -> Dict[str, Any]:
        """Capture system resource usage"""
        import psutil
        
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    
    def capture_recent_events(self) -> Dict[str, Any]:
        """Capture recent system events"""
        # Placeholder - would capture recent log events
        return {
            'error_count_1h': 0,
            'warning_count_1h': 0,
            'restart_count_24h': 0,
            'last_error_message': None
        }
    
    def save_snapshot(self, snapshot: Dict[str, Any], snapshot_type: str = "comprehensive"):
        """Save snapshot to file"""
        timestamp = self.snapshot_time.strftime('%Y%m%d_%H%M%S')
        filename = f"black_swan_snapshot_{snapshot_type}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(snapshot, f, indent=2, default=str)
        
        logger.info(f"Black swan snapshot saved: {filepath}")
        return filepath
    
    def print_snapshot_summary(self, snapshot: Dict[str, Any]):
        """Print snapshot summary"""
        logger.info("=" * 60)
        logger.info("BLACK SWAN SNAPSHOT SUMMARY")
        logger.info("=" * 60)
        
        # System mode
        mode_info = snapshot['sections']['system_mode']
        logger.info(f"🔧 SYSTEM MODE: {mode_info.get('current_mode', 'unknown').upper()}")
        
        # Position exposure
        exposure = snapshot['sections']['position_exposure']
        logger.info(f"💰 EXPOSURE:")
        logger.info(f"   Total Positions: {exposure.get('total_positions', 0)}")
        logger.info(f"   Total Risk: ₹{exposure.get('total_risk', 0):,.0f}")
        logger.info(f"   Total P&L: ₹{exposure.get('total_pnl', 0):,.0f}")
        logger.info(f"   Short Vol Exposure: ₹{exposure.get('short_vol_exposure', 0):,.0f}")
        
        # Market conditions
        market = snapshot['sections']['market_conditions']
        logger.info(f"📈 MARKET:")
        logger.info(f"   VIX Level: {market.get('vix_level', 'N/A')}")
        logger.info(f"   Market Status: {market.get('market_status', 'unknown')}")
        
        # Immediate risks
        risks = snapshot['sections']['immediate_risks']
        logger.info(f"⚠️  RISKS:")
        logger.info(f"   Overall Risk Level: {risks.get('overall_risk_level', 'unknown').upper()}")
        logger.info(f"   Critical Risks: {len(risks.get('critical_risks', []))}")
        logger.info(f"   High Risks: {len(risks.get('high_risks', []))}")
        
        # Print critical risks
        for risk in risks.get('critical_risks', []):
            logger.error(f"   🚨 {risk['risk']}: {risk['action_required']}")
        
        logger.info("=" * 60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Black Swan Snapshot Tool")
    parser.add_argument("--immediate", action="store_true",
                       help="Take immediate snapshot for first response")
    parser.add_argument("--comprehensive", action="store_true",
                       help="Take comprehensive snapshot for detailed analysis")
    parser.add_argument("--output-dir", type=Path,
                       help="Override output directory")
    
    args = parser.parse_args()
    
    # Default to comprehensive if no type specified
    if not args.immediate and not args.comprehensive:
        args.comprehensive = True
    
    snapshot_taker = BlackSwanSnapshotTaker()
    
    if args.output_dir:
        snapshot_taker.output_dir = args.output_dir
        snapshot_taker.output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if args.immediate:
            snapshot = snapshot_taker.take_immediate_snapshot()
            filepath = snapshot_taker.save_snapshot(snapshot, "immediate")
            snapshot_taker.print_snapshot_summary(snapshot)
        
        if args.comprehensive:
            snapshot = snapshot_taker.take_comprehensive_snapshot()
            filepath = snapshot_taker.save_snapshot(snapshot, "comprehensive")
            snapshot_taker.print_snapshot_summary(snapshot)
        
        return 0
        
    except Exception as e:
        logger.error(f"Snapshot failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
