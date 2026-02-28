"""
Accounting Integrity Module for Northstar V2

Enforces canonical equity equation and integrity checks with governance alerts.
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AccountingIntegrityChecker:
    """Enforces accounting integrity and canonical equity equation"""
    
    def __init__(self, tolerance_pct: float = 0.0001):
        """
        Initialize integrity checker
        
        Args:
            tolerance_pct: Tolerance as fraction of net_equity (default 0.0001 = 0.01%)
        """
        self.tolerance_pct = tolerance_pct
        self.min_tolerance_inr = 1.0  # Minimum 1 INR tolerance

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)
    
    def compute_canonical_equity(self, base_capital: float, realized_net_pnl: float, 
                               unrealized_pnl: float) -> float:
        """
        Compute canonical equity equation
        
        net_equity = base_capital + realized_net_pnl + unrealized_pnl
        """
        return base_capital + realized_net_pnl + unrealized_pnl
    
    def compute_tolerance(self, net_equity: float) -> float:
        """Compute tolerance threshold"""
        percentage_tolerance = abs(net_equity) * self.tolerance_pct
        return max(self.min_tolerance_inr, percentage_tolerance)
    
    def validate_equity_integrity(self, runtime_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate equity integrity against canonical equation
        
        Returns integrity report with status and recommendations
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'status': 'unknown',
            'canonical_equity': 0.0,
            'reported_equity': 0.0,
            'difference': 0.0,
            'tolerance': 0.0,
            'within_tolerance': False,
            'governance_alert': False,
            'block_new_risk': False,
            'details': {},
            'recommendations': []
        }
        
        try:
            # Extract components
            base_capital = self._to_float(runtime_state.get('base_capital', 0.0))
            realized_net_pnl = self._to_float(runtime_state.get('realized_net_pnl', 0.0))
            unrealized_pnl = self._to_float(runtime_state.get('unrealized_pnl', 0.0))
            reported_equity = self._to_float(runtime_state.get('net_equity', 0.0))
            
            # Compute canonical equity
            canonical_equity = self.compute_canonical_equity(
                base_capital, realized_net_pnl, unrealized_pnl
            )
            
            # Compute difference and tolerance
            difference = abs(canonical_equity - reported_equity)
            tolerance = self.compute_tolerance(canonical_equity)
            
            # Update report
            report.update({
                'canonical_equity': canonical_equity,
                'reported_equity': reported_equity,
                'difference': difference,
                'tolerance': tolerance,
                'within_tolerance': difference <= tolerance,
                'details': {
                    'base_capital': base_capital,
                    'realized_net_pnl': realized_net_pnl,
                    'unrealized_pnl': unrealized_pnl,
                    'difference_pct': (difference / abs(canonical_equity)) * 100 if canonical_equity != 0 else 0
                }
            })
            
            # Determine status and actions
            if report['within_tolerance']:
                report['status'] = 'healthy'
                logger.info(f"Equity integrity check passed: "
                           f"₹{canonical_equity:,.2f} vs ₹{reported_equity:,.2f} "
                           f"(diff: ₹{difference:.2f}, tolerance: ₹{tolerance:.2f})")
            else:
                report['status'] = 'mismatch'
                report['governance_alert'] = True
                report['block_new_risk'] = True
                
                logger.error(f"Equity integrity VIOLATION: "
                            f"₹{canonical_equity:,.2f} vs ₹{reported_equity:,.2f} "
                            f"(diff: ₹{difference:.2f}, tolerance: ₹{tolerance:.2f})")
                
                # Add recommendations
                report['recommendations'].extend([
                    "Immediate reconciliation required",
                    "Block new risk until resolved",
                    "Trigger governance alert",
                    "Review ledger and position valuations"
                ])
                
                if difference > tolerance * 10:  # Severe mismatch
                    report['recommendations'].append("Consider recovery mode")
        
        except Exception as e:
            report['status'] = 'error'
            report['governance_alert'] = True
            report['block_new_risk'] = True
            report['details']['error'] = str(e)
            logger.error(f"Equity integrity check failed: {e}", exc_info=True)
        
        return report
    
    def compute_dynamic_risk_cap(self, net_equity: float, portfolio_risk_cap_pct: float) -> float:
        """
        Compute dynamic risk cap based on current equity
        
        risk_cap = net_equity * portfolio_risk_cap_pct
        """
        return max(0.0, float(net_equity) * float(portfolio_risk_cap_pct))
    
    def validate_risk_constraints(self, runtime_state: Dict[str, Any], 
                                portfolio_risk_cap_pct: float) -> Dict[str, Any]:
        """Validate risk constraints against dynamic equity"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'net_equity': runtime_state.get('net_equity', 0.0),
            'risk_cap_value': 0.0,
            'current_risk': 0.0,
            'risk_remaining': 0.0,
            'risk_utilization_pct': 0.0,
            'within_limits': True,
            'recommendations': []
        }
        
        try:
            net_equity = self._to_float(runtime_state.get('net_equity', 0.0))
            
            # Compute dynamic risk cap
            risk_cap_value = self.compute_dynamic_risk_cap(net_equity, portfolio_risk_cap_pct)
            
            # Get current risk (sum of max_risk from open positions)
            open_positions = runtime_state.get('open_positions', [])
            if not isinstance(open_positions, list):
                open_positions = []
            current_risk = 0.0
            for pos in open_positions:
                if not isinstance(pos, dict):
                    continue
                # Runtime positions store max_loss; keep max_risk fallback for backward compatibility.
                position_risk = self._to_float(
                    pos.get('max_loss', pos.get('max_risk', 0.0)),
                    default=0.0,
                )
                current_risk += abs(position_risk)
            
            # Compute remaining risk capacity
            risk_remaining = max(0.0, risk_cap_value - current_risk)
            risk_utilization_pct = (
                (current_risk / risk_cap_value * 100.0)
                if risk_cap_value > 0
                else (100.0 if current_risk > 0 else 0.0)
            )
            
            # Update report
            report.update({
                'risk_cap_value': risk_cap_value,
                'current_risk': current_risk,
                'risk_remaining': risk_remaining,
                'risk_utilization_pct': risk_utilization_pct,
                'within_limits': current_risk <= risk_cap_value
            })
            
            # Add recommendations based on utilization
            if risk_utilization_pct > 90:
                report['recommendations'].append("Risk utilization very high (>90%)")
            elif risk_utilization_pct > 75:
                report['recommendations'].append("Risk utilization high (>75%)")
            
            if not report['within_limits']:
                report['recommendations'].extend([
                    "Risk limit exceeded - reduce positions",
                    "Block new risk until within limits"
                ])
            
            logger.info(f"Risk constraint check: "
                       f"₹{current_risk:,.0f} / ₹{risk_cap_value:,.0f} "
                       f"({risk_utilization_pct:.1f}%)")
        
        except Exception as e:
            report['recommendations'].append(f"Risk validation error: {e}")
            logger.error(f"Risk constraint validation failed: {e}")
        
        return report
    
    def update_weekly_anchor(self, runtime_state: Dict[str, Any]) -> Dict[str, Any]:
        """Update weekly equity anchor if needed"""
        current_date = datetime.now().date()
        
        # Check if we need to set/update weekly anchor
        week_start_equity = runtime_state.get('week_start_equity')
        last_anchor_date = runtime_state.get('week_anchor_date')
        
        # Set anchor if missing or if new week started
        needs_update = False
        if week_start_equity is None:
            needs_update = True
            reason = "Initial weekly anchor"
        elif last_anchor_date:
            try:
                last_date = datetime.fromisoformat(last_anchor_date).date()
                current_week = current_date.isocalendar()[:2]
                last_week = last_date.isocalendar()[:2]
                if current_week != last_week:
                    needs_update = True
                    reason = "New ISO week started"
            except Exception:
                needs_update = True
                reason = "Invalid anchor date"
        else:
            needs_update = True
            reason = "Missing anchor date"
        
        if needs_update:
            net_equity = runtime_state.get('net_equity', 0.0)
            runtime_state['week_start_equity'] = net_equity
            runtime_state['week_anchor_date'] = current_date.isoformat()
            
            logger.info(f"Weekly anchor updated: ₹{net_equity:,.2f} ({reason})")
            
            return {
                'updated': True,
                'reason': reason,
                'week_start_equity': net_equity,
                'anchor_date': current_date.isoformat()
            }
        
        return {'updated': False}
    
    def compute_weekly_performance(self, runtime_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compute weekly performance metrics"""
        week_start_equity = runtime_state.get('week_start_equity')
        current_equity = runtime_state.get('net_equity', 0.0)
        
        if week_start_equity is None:
            return {
                'weekly_pnl': 0.0,
                'weekly_return_pct': 0.0,
                'anchor_available': False
            }
        
        weekly_pnl = current_equity - week_start_equity
        weekly_return_pct = (weekly_pnl / week_start_equity * 100) if week_start_equity != 0 else 0.0
        
        return {
            'weekly_pnl': weekly_pnl,
            'weekly_return_pct': weekly_return_pct,
            'week_start_equity': week_start_equity,
            'current_equity': current_equity,
            'anchor_available': True
        }
    
    def generate_integrity_summary(self, runtime_state: Dict[str, Any], 
                                 portfolio_risk_cap_pct: float) -> Dict[str, Any]:
        """Generate comprehensive integrity summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks_performed': [],
            'alerts': [],
            'block_new_risk': False,
            'equity_check': {},
            'risk_check': {},
        }
        
        # Equity integrity check
        equity_check = self.validate_equity_integrity(runtime_state)
        summary['equity_check'] = equity_check
        summary['checks_performed'].append({
            'check': 'equity_integrity',
            'status': equity_check['status'],
            'within_tolerance': equity_check['within_tolerance']
        })
        
        if equity_check['governance_alert']:
            summary['alerts'].append('Equity integrity violation')
            summary['overall_status'] = 'alert'
        
        if equity_check['block_new_risk']:
            summary['block_new_risk'] = True
        
        # Risk constraint check
        risk_check = self.validate_risk_constraints(runtime_state, portfolio_risk_cap_pct)
        summary['risk_check'] = risk_check
        summary['checks_performed'].append({
            'check': 'risk_constraints',
            'within_limits': risk_check['within_limits'],
            'utilization_pct': risk_check['risk_utilization_pct']
        })
        
        if not risk_check['within_limits']:
            summary['alerts'].append('Risk limits exceeded')
            summary['overall_status'] = 'alert'
            summary['block_new_risk'] = True
        
        # Weekly anchor update
        anchor_update = self.update_weekly_anchor(runtime_state)
        if anchor_update['updated']:
            summary['checks_performed'].append({
                'check': 'weekly_anchor_update',
                'updated': True,
                'reason': anchor_update['reason']
            })
        
        return summary
