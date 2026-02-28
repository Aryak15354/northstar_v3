"""
Strategy Lab for Northstar V2 Research

Strategy analysis and optimization with governance controls.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StrategyLab:
    """Strategy research and analysis module"""
    
    def __init__(self):
        self.analysis_cache = {}
    
    def run_analysis(self, market_data: Dict[str, Any], 
                    system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run strategy analysis"""
        analysis_start = datetime.now()
        
        results = {
            'module': 'strategy_lab',
            'timestamp': analysis_start.isoformat(),
            'outputs': [],
            'metrics': {},
            'recommendations': []
        }
        
        try:
            # Analyze current strategy performance
            strategy_performance = self._analyze_strategy_performance(system_state)
            results['outputs'].append({
                'type': 'strategy_performance_analysis',
                'data': strategy_performance,
                'actionable': False,  # Analysis only, not actionable
                'generated_at': datetime.now().isoformat()
            })
            
            # Generate strategy recommendations
            recommendations = self._generate_strategy_recommendations(
                market_data, system_state, strategy_performance
            )
            results['outputs'].append({
                'type': 'strategy_recommendations',
                'data': recommendations,
                'actionable': True,  # Recommendations are actionable
                'generated_at': datetime.now().isoformat()
            })
            
            # Parameter sensitivity analysis
            if system_state.get('current_mode') == 'normal_operation':
                param_analysis = self._parameter_sensitivity_analysis(system_state)
                results['outputs'].append({
                    'type': 'parameter_sensitivity',
                    'data': param_analysis,
                    'actionable': False,  # Analysis only
                    'generated_at': datetime.now().isoformat()
                })
            
            results['metrics']['analysis_duration_seconds'] = (
                datetime.now() - analysis_start
            ).total_seconds()
            
        except Exception as e:
            logger.error(f"Strategy lab analysis failed: {e}")
            results['error'] = str(e)
        
        return results
    
    def _analyze_strategy_performance(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance of current strategies"""
        open_positions = system_state.get('open_positions', [])
        def _pnl(pos: Dict[str, Any]) -> float:
            return float(
                pos.get('current_pnl', pos.get('unrealized_pnl', pos.get('realized_pnl', 0.0)))
                or 0.0
            )

        def _risk(pos: Dict[str, Any]) -> float:
            return float(
                pos.get('max_risk', pos.get('max_loss', pos.get('risk', 0.0)))
                or 0.0
            )
        
        # Group positions by strategy type
        strategy_groups = {}
        for position in open_positions:
            strategy_type = position.get('strategy_type', 'unknown')
            if strategy_type not in strategy_groups:
                strategy_groups[strategy_type] = []
            strategy_groups[strategy_type].append(position)
        
        # Analyze each strategy type
        performance_analysis = {
            'total_positions': len(open_positions),
            'strategy_breakdown': {},
            'overall_metrics': {
                'total_pnl': sum(_pnl(pos) for pos in open_positions),
                'total_risk': sum(_risk(pos) for pos in open_positions),
                'avg_pnl_per_position': 0
            }
        }
        
        if open_positions:
            performance_analysis['overall_metrics']['avg_pnl_per_position'] = (
                performance_analysis['overall_metrics']['total_pnl'] / len(open_positions)
            )
        
        # Analyze each strategy type
        for strategy_type, positions in strategy_groups.items():
            strategy_pnl = sum(_pnl(pos) for pos in positions)
            strategy_risk = sum(_risk(pos) for pos in positions)
            
            performance_analysis['strategy_breakdown'][strategy_type] = {
                'position_count': len(positions),
                'total_pnl': strategy_pnl,
                'total_risk': strategy_risk,
                'avg_pnl_per_position': strategy_pnl / len(positions) if positions else 0,
                'risk_adjusted_return': strategy_pnl / strategy_risk if strategy_risk > 0 else 0,
                'allocation_pct': len(positions) / len(open_positions) * 100 if open_positions else 0
            }
        
        return performance_analysis
    
    def _generate_strategy_recommendations(self, market_data: Dict[str, Any],
                                         system_state: Dict[str, Any],
                                         performance_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate strategy recommendations based on analysis"""
        recommendations = {
            'timestamp': datetime.now().isoformat(),
            'market_regime': system_state.get('current_regime', 'unknown'),
            'recommendations': [],
            'risk_adjustments': [],
            'allocation_suggestions': []
        }
        
        # Analyze market conditions from real feed only.
        vix_raw = market_data.get('vix_level')
        rv_raw = market_data.get('realized_vol')
        try:
            vix_level = float(vix_raw) if vix_raw is not None else None
        except Exception:
            vix_level = None
        try:
            realized_vol = float(rv_raw) if rv_raw is not None else None
        except Exception:
            realized_vol = None
        recommendations['data_quality'] = {
            'vix_level_available': bool(vix_level is not None),
            'realized_vol_available': bool(realized_vol is not None),
        }

        # Generate regime-based recommendations
        if vix_level is None:
            recommendations['recommendations'].append({
                'type': 'data_guard',
                'recommendation': 'Skipped volatility-regime recommendation due to missing VIX input',
                'confidence': 'high',
                'rationale': 'Real-time VIX level is unavailable; no synthetic proxy used'
            })
        elif vix_level > 25:  # High volatility environment
            recommendations['recommendations'].append({
                'type': 'regime_adjustment',
                'recommendation': 'Favor long volatility strategies in high VIX environment',
                'confidence': 'medium',
                'rationale': f'VIX at {vix_level} suggests elevated volatility premium'
            })
        elif vix_level < 12:  # Low volatility environment
            recommendations['recommendations'].append({
                'type': 'regime_adjustment',
                'recommendation': 'Consider short volatility strategies in low VIX environment',
                'confidence': 'medium',
                'rationale': f'VIX at {vix_level} suggests compressed volatility premium'
            })
        
        # Analyze strategy performance and suggest adjustments
        strategy_breakdown = performance_analysis.get('strategy_breakdown', {})
        
        for strategy_type, metrics in strategy_breakdown.items():
            risk_adjusted_return = metrics.get('risk_adjusted_return', 0)
            
            if risk_adjusted_return < -0.1:  # Poor performing strategy
                recommendations['risk_adjustments'].append({
                    'strategy_type': strategy_type,
                    'action': 'reduce_allocation',
                    'current_allocation_pct': metrics.get('allocation_pct', 0),
                    'suggested_reduction': '25%',
                    'rationale': f'Poor risk-adjusted return: {risk_adjusted_return:.3f}'
                })
            elif risk_adjusted_return > 0.2:  # Well performing strategy
                recommendations['allocation_suggestions'].append({
                    'strategy_type': strategy_type,
                    'action': 'consider_increase',
                    'current_allocation_pct': metrics.get('allocation_pct', 0),
                    'rationale': f'Strong risk-adjusted return: {risk_adjusted_return:.3f}'
                })
        
        return recommendations
    
    def _parameter_sensitivity_analysis(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Return strict status until real sensitivity engine is enabled."""
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'skipped_no_real_sensitivity_engine',
            'reason': 'No synthetic/placeholder sensitivity analysis allowed',
            'parameters_analyzed': [],
            'sensitivity_results': {},
            'recommendations': [],
        }
