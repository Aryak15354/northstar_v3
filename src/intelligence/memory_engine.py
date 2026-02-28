#!/usr/bin/env python3
"""
🧠 MEMORY & LEARNING ENGINE - INSTITUTIONAL GRADE INTELLIGENCE
Real Intelligence System for Northstar V3

This is the difference between "a clever rules engine" and "a real intelligence system."

Memory: Remember what worked and what didn't
Learning: Adapt weights based on historical performance  
Self-correction: Update behavior based on reality

Creates:
- Trade experience database
- Conditional probability learning
- Dynamic weight adaptation
- Self-critic feedback loops

This is how BlackRock, Bridgewater, AQR actually build intelligence.

Usage:
    try:
    from intelligence.memory_engine import MemoryEngine
except ImportError:
    from MemoryEngine import MemoryEngine
    
    memory = MemoryEngine()
    memory.record_trade_outcome(...)
    performance = memory.analyze_signal_performance()
    new_weights = memory.get_adaptive_weights()
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sqlite3
import json
import warnings
warnings.filterwarnings('ignore')

# =========================== MEMORY ENGINE CORE ===========================

class MemoryEngine:
    """
    Memory & Learning Engine
    
    Remembers every decision, learns from outcomes, adapts behavior.
    This is what transforms Northstar from rules-based to intelligence-based.
    """
    
    def __init__(self, db_path='data/intelligence/memory.db'):
        self.db_path = db_path
        self.ensure_database_exists()
        
        # Learning parameters
        self.learning_rate = 0.1
        self.min_samples_for_learning = 10
        self.lookback_periods = 252  # 1 year of trading days
        
        # Performance tracking
        self.performance_metrics = [
            'total_return', 'win_rate', 'avg_win', 'avg_loss', 
            'max_drawdown', 'sharpe_ratio', 'hit_rate'
        ]
        
        # Signal types to track
        self.signal_types = [
            'valuation', 'momentum', 'macro', 'quality', 'flows',
            'technicals', 'earnings', 'narrative'
        ]
    
    def ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        
        # Create directory
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Create database and tables
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Trade outcomes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    ticker TEXT,
                    entry_date DATE,
                    exit_date DATE,
                    entry_price REAL,
                    exit_price REAL,
                    position_size REAL,
                    return_pct REAL,
                    max_drawdown REAL,
                    hold_days INTEGER,
                    regime TEXT,
                    macro_state TEXT,
                    valuation_score REAL,
                    momentum_score REAL,
                    macro_score REAL,
                    quality_score REAL,
                    flows_score REAL,
                    technicals_score REAL,
                    earnings_score REAL,
                    narrative_score REAL,
                    northstar_score REAL,
                    conviction REAL,
                    outcome TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Signal performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signal_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_type TEXT,
                    signal_value REAL,
                    regime TEXT,
                    outcome_return REAL,
                    outcome_category TEXT,
                    date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Weight adaptations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weight_adaptations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    regime TEXT,
                    signal_type TEXT,
                    old_weight REAL,
                    new_weight REAL,
                    performance_reason TEXT,
                    adaptation_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Model performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version TEXT,
                    regime TEXT,
                    period_start DATE,
                    period_end DATE,
                    total_trades INTEGER,
                    win_rate REAL,
                    avg_return REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    performance_grade TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def record_trade_outcome(self, trade_data):
        """
        Record a completed trade outcome for learning
        
        This is the core memory function - every trade teaches the system
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert trade outcome
            cursor.execute('''
                INSERT OR REPLACE INTO trade_outcomes (
                    trade_id, ticker, entry_date, exit_date, entry_price, exit_price,
                    position_size, return_pct, max_drawdown, hold_days, regime, macro_state,
                    valuation_score, momentum_score, macro_score, quality_score, flows_score,
                    technicals_score, earnings_score, narrative_score, northstar_score,
                    conviction, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('trade_id'),
                trade_data.get('ticker'),
                trade_data.get('entry_date'),
                trade_data.get('exit_date'),
                trade_data.get('entry_price'),
                trade_data.get('exit_price'),
                trade_data.get('position_size'),
                trade_data.get('return_pct'),
                trade_data.get('max_drawdown'),
                trade_data.get('hold_days'),
                trade_data.get('regime'),
                trade_data.get('macro_state'),
                trade_data.get('valuation_score'),
                trade_data.get('momentum_score'),
                trade_data.get('macro_score'),
                trade_data.get('quality_score'),
                trade_data.get('flows_score'),
                trade_data.get('technicals_score'),
                trade_data.get('earnings_score'),
                trade_data.get('narrative_score'),
                trade_data.get('northstar_score'),
                trade_data.get('conviction'),
                trade_data.get('outcome')
            ))
            
            # Record individual signal performances
            for signal_type in self.signal_types:
                signal_value = trade_data.get(f'{signal_type}_score')
                if signal_value is not None:
                    cursor.execute('''
                        INSERT INTO signal_performance (
                            signal_type, signal_value, regime, outcome_return, 
                            outcome_category, date
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        signal_type,
                        signal_value,
                        trade_data.get('regime'),
                        trade_data.get('return_pct'),
                        'win' if trade_data.get('return_pct', 0) > 0 else 'loss',
                        trade_data.get('exit_date')
                    ))
            
            conn.commit()
        
        print(f"📝 Recorded trade outcome: {trade_data.get('ticker')} "
              f"({trade_data.get('return_pct', 0):.1f}% return)")
    
    def analyze_signal_performance(self, regime=None, lookback_days=252):
        """
        Analyze which signals made money and which ones hurt us
        
        This is the learning function - what actually works?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            # Build query
            query = '''
                SELECT signal_type, signal_value, regime, outcome_return, outcome_category
                FROM signal_performance 
                WHERE date >= date('now', '-{} days')
            '''.format(lookback_days)
            
            if regime:
                query += f" AND regime = '{regime}'"
            
            df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return {}
        
        # Analyze performance by signal type
        performance_analysis = {}
        
        for signal_type in df['signal_type'].unique():
            signal_df = df[df['signal_type'] == signal_type]
            
            if len(signal_df) < self.min_samples_for_learning:
                continue
            
            # Calculate performance metrics
            analysis = {
                'total_trades': len(signal_df),
                'win_rate': (signal_df['outcome_category'] == 'win').mean(),
                'avg_return': signal_df['outcome_return'].mean(),
                'avg_win': signal_df[signal_df['outcome_category'] == 'win']['outcome_return'].mean(),
                'avg_loss': signal_df[signal_df['outcome_category'] == 'loss']['outcome_return'].mean(),
                'total_return': signal_df['outcome_return'].sum(),
                'sharpe_ratio': self.calculate_sharpe_ratio(signal_df['outcome_return']),
                'hit_rate_by_signal_strength': self.analyze_signal_strength_performance(signal_df)
            }
            
            # Performance grade
            if analysis['win_rate'] > 0.6 and analysis['avg_return'] > 2:
                grade = 'A'
            elif analysis['win_rate'] > 0.5 and analysis['avg_return'] > 0:
                grade = 'B'
            elif analysis['win_rate'] > 0.4:
                grade = 'C'
            else:
                grade = 'D'
            
            analysis['performance_grade'] = grade
            performance_analysis[signal_type] = analysis
        
        return performance_analysis
    
    def calculate_sharpe_ratio(self, returns, risk_free_rate=0.05):
        """Calculate Sharpe ratio for return series"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        
        if excess_returns.std() == 0:
            return 0.0
        
        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)
    
    def analyze_signal_strength_performance(self, signal_df):
        """Analyze performance by signal strength buckets"""
        
        if len(signal_df) < 10:
            return {}
        
        # Create signal strength buckets
        signal_df = signal_df.copy()
        signal_df['signal_bucket'] = pd.cut(
            signal_df['signal_value'], 
            bins=[-np.inf, -1, -0.5, 0.5, 1, np.inf],
            labels=['very_negative', 'negative', 'neutral', 'positive', 'very_positive']
        )
        
        bucket_performance = {}
        for bucket in signal_df['signal_bucket'].unique():
            if pd.isna(bucket):
                continue
            
            bucket_df = signal_df[signal_df['signal_bucket'] == bucket]
            bucket_performance[str(bucket)] = {
                'count': len(bucket_df),
                'win_rate': (bucket_df['outcome_category'] == 'win').mean(),
                'avg_return': bucket_df['outcome_return'].mean()
            }
        
        return bucket_performance
    
    def get_adaptive_weights(self, regime=None):
        """
        Get adaptive weights based on historical performance
        
        This is where learning translates to action - update the weights!
        """
        
        # Analyze recent performance
        performance = self.analyze_signal_performance(regime)
        
        if not performance:
            # Return default weights if no performance data
            return self.get_default_weights(regime)
        
        # Calculate adaptive weights based on performance
        adaptive_weights = {}
        total_performance_score = 0
        
        for signal_type, perf in performance.items():
            # Performance score combines win rate and average return
            win_rate_score = perf['win_rate'] * 2 - 1  # Convert 0-1 to -1 to +1
            return_score = np.tanh(perf['avg_return'] / 5)  # Normalize returns
            
            performance_score = 0.6 * win_rate_score + 0.4 * return_score
            adaptive_weights[signal_type] = max(0.05, performance_score)  # Minimum 5% weight
            total_performance_score += adaptive_weights[signal_type]
        
        # Normalize weights to sum to 1
        if total_performance_score > 0:
            for signal_type in adaptive_weights:
                adaptive_weights[signal_type] /= total_performance_score
        
        # Blend with default weights for stability
        default_weights = self.get_default_weights(regime)
        blended_weights = {}
        
        for signal_type in default_weights:
            adaptive_weight = adaptive_weights.get(signal_type, default_weights[signal_type])
            # 70% adaptive, 30% default for stability
            blended_weights[signal_type] = (
                0.7 * adaptive_weight + 0.3 * default_weights[signal_type]
            )
        
        # Record weight adaptation
        self.record_weight_adaptation(regime, default_weights, blended_weights, performance)
        
        return blended_weights
    
    def get_default_weights(self, regime=None):
        """Get default weights by regime"""
        
        if regime == 'bull':
            return {
                'valuation': 0.15,
                'momentum': 0.35,
                'macro': 0.20,
                'quality': 0.10,
                'flows': 0.10,
                'technicals': 0.05,
                'earnings': 0.05
            }
        elif regime == 'bear':
            return {
                'valuation': 0.35,
                'momentum': 0.15,
                'macro': 0.25,
                'quality': 0.15,
                'flows': 0.05,
                'technicals': 0.03,
                'earnings': 0.02
            }
        else:  # neutral
            return {
                'valuation': 0.25,
                'momentum': 0.25,
                'macro': 0.20,
                'quality': 0.15,
                'flows': 0.08,
                'technicals': 0.04,
                'earnings': 0.03
            }
    
    def record_weight_adaptation(self, regime, old_weights, new_weights, performance_reason):
        """Record weight adaptations for audit trail"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for signal_type in new_weights:
                old_weight = old_weights.get(signal_type, 0)
                new_weight = new_weights[signal_type]
                
                if abs(new_weight - old_weight) > 0.01:  # Only record significant changes
                    perf_summary = performance_reason.get(signal_type, {})
                    reason = f"Win rate: {perf_summary.get('win_rate', 0):.2f}, Avg return: {perf_summary.get('avg_return', 0):.2f}%"
                    
                    cursor.execute('''
                        INSERT INTO weight_adaptations (
                            regime, signal_type, old_weight, new_weight, 
                            performance_reason, adaptation_date
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        regime, signal_type, old_weight, new_weight, 
                        reason, datetime.now().date()
                    ))
            
            conn.commit()
    
    def calculate_conditional_probabilities(self, regime=None):
        """
        Calculate conditional probabilities for different scenarios
        
        P(win | valuation high, momentum low, macro tightening)
        """
        
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT valuation_score, momentum_score, macro_score, quality_score,
                       return_pct, regime, outcome
                FROM trade_outcomes 
                WHERE entry_date >= date('now', '-{} days')
            '''.format(self.lookback_periods)
            
            if regime:
                query += f" AND regime = '{regime}'"
            
            df = pd.read_sql_query(query, conn)
        
        if df.empty or len(df) < 20:
            return {}
        
        # Create signal buckets
        for col in ['valuation_score', 'momentum_score', 'macro_score', 'quality_score']:
            if col in df.columns:
                df[f'{col}_bucket'] = pd.cut(
                    df[col], 
                    bins=[-np.inf, -0.5, 0.5, np.inf],
                    labels=['low', 'medium', 'high']
                )
        
        # Calculate conditional probabilities
        conditional_probs = {}
        
        # Example: P(win | valuation=high, momentum=low)
        for val_bucket in ['low', 'medium', 'high']:
            for mom_bucket in ['low', 'medium', 'high']:
                condition = (
                    (df['valuation_score_bucket'] == val_bucket) & 
                    (df['momentum_score_bucket'] == mom_bucket)
                )
                
                subset = df[condition]
                if len(subset) >= 5:  # Minimum sample size
                    win_rate = (subset['return_pct'] > 0).mean()
                    avg_return = subset['return_pct'].mean()
                    
                    conditional_probs[f'val_{val_bucket}_mom_{mom_bucket}'] = {
                        'win_probability': win_rate,
                        'expected_return': avg_return,
                        'sample_size': len(subset)
                    }
        
        return conditional_probs
    
    def run_self_critic(self):
        """
        Self-critic analysis: What did we do wrong? What can we improve?
        
        This is the self-correction mechanism
        """
        
        print("🔍 Running self-critic analysis...")
        
        # Analyze recent performance
        recent_performance = self.analyze_signal_performance(lookback_days=60)
        
        critique = {
            'timestamp': datetime.now(),
            'analysis_period': '60 days',
            'findings': [],
            'recommendations': []
        }
        
        # Critique 1: Which signals are failing?
        failing_signals = []
        for signal_type, perf in recent_performance.items():
            if perf['win_rate'] < 0.4 or perf['avg_return'] < -1:
                failing_signals.append({
                    'signal': signal_type,
                    'win_rate': perf['win_rate'],
                    'avg_return': perf['avg_return'],
                    'grade': perf['performance_grade']
                })
        
        if failing_signals:
            critique['findings'].append({
                'type': 'failing_signals',
                'description': f"Found {len(failing_signals)} underperforming signals",
                'details': failing_signals
            })
            critique['recommendations'].append(
                f"Reduce weights for: {', '.join([s['signal'] for s in failing_signals])}"
            )
        
        # Critique 2: Are we over-betting in any regime?
        regime_performance = {}
        for regime in ['bull', 'bear', 'neutral']:
            regime_perf = self.analyze_signal_performance(regime=regime, lookback_days=120)
            if regime_perf:
                avg_performance = np.mean([p['avg_return'] for p in regime_perf.values()])
                regime_performance[regime] = avg_performance
        
        worst_regime = min(regime_performance.items(), key=lambda x: x[1]) if regime_performance else None
        if worst_regime and worst_regime[1] < -2:
            critique['findings'].append({
                'type': 'regime_weakness',
                'description': f"Poor performance in {worst_regime[0]} regime",
                'avg_return': worst_regime[1]
            })
            critique['recommendations'].append(
                f"Reduce exposure limits in {worst_regime[0]} markets"
            )
        
        # Critique 3: Position sizing issues?
        with sqlite3.connect(self.db_path) as conn:
            size_analysis = pd.read_sql_query('''
                SELECT position_size, return_pct, max_drawdown
                FROM trade_outcomes 
                WHERE entry_date >= date('now', '-90 days')
            ''', conn)
        
        if not size_analysis.empty:
            # Check if large positions are causing problems
            large_positions = size_analysis[size_analysis['position_size'] > size_analysis['position_size'].quantile(0.8)]
            if not large_positions.empty and large_positions['return_pct'].mean() < -2:
                critique['findings'].append({
                    'type': 'position_sizing',
                    'description': 'Large positions underperforming',
                    'large_pos_return': large_positions['return_pct'].mean()
                })
                critique['recommendations'].append("Implement tighter position size limits")
        
        # Critique 4: Are we holding too long/short?
        with sqlite3.connect(self.db_path) as conn:
            hold_analysis = pd.read_sql_query('''
                SELECT hold_days, return_pct
                FROM trade_outcomes 
                WHERE entry_date >= date('now', '-90 days')
            ''', conn)
        
        if not hold_analysis.empty and len(hold_analysis) > 10:
            # Optimal holding period analysis
            hold_analysis['hold_bucket'] = pd.cut(
                hold_analysis['hold_days'],
                bins=[0, 5, 15, 30, 60, np.inf],
                labels=['very_short', 'short', 'medium', 'long', 'very_long']
            )
            
            bucket_returns = hold_analysis.groupby('hold_bucket')['return_pct'].mean()
            best_bucket = bucket_returns.idxmax()
            worst_bucket = bucket_returns.idxmin()
            
            if bucket_returns[worst_bucket] < -2:
                critique['findings'].append({
                    'type': 'holding_period',
                    'description': f'{worst_bucket} holding periods underperforming',
                    'worst_return': bucket_returns[worst_bucket],
                    'best_bucket': best_bucket
                })
                critique['recommendations'].append(
                    f"Avoid {worst_bucket} holding periods, favor {best_bucket}"
                )
        
        # Save critique
        self.save_critique(critique)
        
        return critique
    
    def save_critique(self, critique):
        """Save self-critique for historical analysis"""
        
        critique_path = 'data/intelligence/critiques.json'
        os.makedirs(os.path.dirname(critique_path), exist_ok=True)
        
        # Load existing critiques
        critiques = []
        if os.path.exists(critique_path):
            try:
                with open(critique_path, 'r') as f:
                    critiques = json.load(f)
            except:
                critiques = []
        
        # Add new critique
        critique['timestamp'] = critique['timestamp'].isoformat()
        critiques.append(critique)
        
        # Keep only last 50 critiques
        critiques = critiques[-50:]
        
        # Save
        with open(critique_path, 'w') as f:
            json.dump(critiques, f, indent=2)
    
    def get_learning_summary(self):
        """Get summary of what the system has learned"""
        
        with sqlite3.connect(self.db_path) as conn:
            # Total trades
            total_trades = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM trade_outcomes", conn
            ).iloc[0]['count']
            
            # Recent performance
            recent_perf = pd.read_sql_query('''
                SELECT AVG(return_pct) as avg_return, 
                       AVG(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END) as win_rate
                FROM trade_outcomes 
                WHERE entry_date >= date('now', '-90 days')
            ''', conn)
            
            # Weight adaptations
            adaptations = pd.read_sql_query('''
                SELECT COUNT(*) as count FROM weight_adaptations 
                WHERE adaptation_date >= date('now', '-30 days')
            ''', conn).iloc[0]['count']
        
        return {
            'total_trades_recorded': total_trades,
            'recent_avg_return': recent_perf.iloc[0]['avg_return'] if not recent_perf.empty else 0,
            'recent_win_rate': recent_perf.iloc[0]['win_rate'] if not recent_perf.empty else 0,
            'recent_adaptations': adaptations,
            'learning_status': 'active' if total_trades > 50 else 'building_experience'
        }

# =========================== LEARNING COORDINATOR ===========================

class LearningCoordinator:
    """
    Coordinates all learning activities across the system
    
    This is the meta-intelligence that manages the learning process
    """
    
    def __init__(self):
        self.memory_engine = MemoryEngine()
        self.learning_schedule = {
            'daily': ['record_new_trades', 'update_recent_performance'],
            'weekly': ['run_self_critic', 'update_adaptive_weights'],
            'monthly': ['full_performance_review', 'model_retraining']
        }
    
    def run_daily_learning(self):
        """Daily learning routine"""
        print("📚 Running daily learning routine...")
        
        # Update performance metrics
        performance = self.memory_engine.analyze_signal_performance(lookback_days=30)
        
        # Check for any immediate issues
        issues = []
        for signal_type, perf in performance.items():
            if perf['win_rate'] < 0.3:
                issues.append(f"{signal_type} win rate critically low: {perf['win_rate']:.2f}")
        
        if issues:
            print("⚠️ Performance issues detected:")
            for issue in issues:
                print(f"  - {issue}")
        
        return {
            'performance_update': performance,
            'issues_detected': issues,
            'status': 'completed'
        }
    
    def run_weekly_learning(self):
        """Weekly learning routine"""
        print("🧠 Running weekly learning routine...")
        
        # Run self-critic
        critique = self.memory_engine.run_self_critic()
        
        # Update adaptive weights
        adaptive_weights = {}
        for regime in ['bull', 'bear', 'neutral']:
            adaptive_weights[regime] = self.memory_engine.get_adaptive_weights(regime)
        
        return {
            'self_critique': critique,
            'adaptive_weights': adaptive_weights,
            'status': 'completed'
        }
    
    def run_monthly_learning(self):
        """Monthly comprehensive learning review"""
        print("🎓 Running monthly learning review...")
        
        # Full performance analysis
        full_performance = {}
        for regime in ['bull', 'bear', 'neutral']:
            full_performance[regime] = self.memory_engine.analyze_signal_performance(
                regime=regime, lookback_days=252
            )
        
        # Conditional probabilities
        conditional_probs = {}
        for regime in ['bull', 'bear', 'neutral']:
            conditional_probs[regime] = self.memory_engine.calculate_conditional_probabilities(regime)
        
        # Learning summary
        learning_summary = self.memory_engine.get_learning_summary()
        
        return {
            'full_performance': full_performance,
            'conditional_probabilities': conditional_probs,
            'learning_summary': learning_summary,
            'status': 'completed'
        }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate memory and learning system"""
    
    print("🧠 MEMORY & LEARNING ENGINE - INSTITUTIONAL GRADE INTELLIGENCE")
    print("=" * 70)
    
    # Initialize memory engine
    memory = MemoryEngine()
    coordinator = LearningCoordinator()
    
    # Example: Record a trade outcome
    print("\n📝 Example: Recording Trade Outcome")
    print("-" * 40)
    
    example_trade = {
        'trade_id': 'RELIANCE_20241229_001',
        'ticker': 'RELIANCE',
        'entry_date': '2024-12-20',
        'exit_date': '2024-12-29',
        'entry_price': 1250.0,
        'exit_price': 1280.0,
        'position_size': 0.05,  # 5% position
        'return_pct': 2.4,
        'max_drawdown': -1.2,
        'hold_days': 9,
        'regime': 'neutral',
        'macro_state': 'late_expansion',
        'valuation_score': -0.8,  # Undervalued
        'momentum_score': 0.5,    # Positive momentum
        'macro_score': 0.2,       # Slightly positive macro
        'quality_score': 0.9,     # High quality
        'flows_score': -0.3,      # Negative flows
        'technicals_score': 0.4,  # Positive technicals
        'earnings_score': 0.6,    # Good earnings
        'narrative_score': 0.1,   # Neutral narrative
        'northstar_score': 75,    # Overall score
        'conviction': 0.7,        # 70% conviction
        'outcome': 'win'
    }
    
    memory.record_trade_outcome(example_trade)
    
    # Analyze signal performance
    print("\n📊 Signal Performance Analysis")
    print("-" * 40)
    
    performance = memory.analyze_signal_performance(lookback_days=90)
    
    if performance:
        for signal_type, perf in performance.items():
            print(f"{signal_type.title()}: Win Rate={perf['win_rate']:.2f}, "
                  f"Avg Return={perf['avg_return']:.2f}%, Grade={perf['performance_grade']}")
    else:
        print("Insufficient data for performance analysis (need more trades)")
    
    # Get adaptive weights
    print("\n⚖️ Adaptive Weights by Regime")
    print("-" * 40)
    
    for regime in ['bull', 'bear', 'neutral']:
        weights = memory.get_adaptive_weights(regime)
        print(f"\n{regime.upper()} Market:")
        for signal_type, weight in weights.items():
            print(f"  {signal_type}: {weight:.3f}")
    
    # Run self-critic
    print("\n🔍 Self-Critic Analysis")
    print("-" * 40)
    
    critique = memory.run_self_critic()
    
    print(f"Analysis Period: {critique['analysis_period']}")
    print(f"Findings: {len(critique['findings'])}")
    print(f"Recommendations: {len(critique['recommendations'])}")
    
    if critique['recommendations']:
        print("\nKey Recommendations:")
        for rec in critique['recommendations'][:3]:
            print(f"  • {rec}")
    
    # Learning summary
    print("\n🎓 Learning Summary")
    print("-" * 40)
    
    summary = memory.get_learning_summary()
    print(f"Total Trades Recorded: {summary['total_trades_recorded']}")
    recent_win_rate = summary.get('recent_win_rate', 0) or 0
    recent_avg_return = summary.get('recent_avg_return', 0) or 0
    print(f"Recent Win Rate: {recent_win_rate:.2%}")
    print(f"Recent Avg Return: {recent_avg_return:.2f}%")
    print(f"Learning Status: {summary['learning_status']}")
    
    print("\n✅ Memory & Learning engine operational")
    print("💡 Key insight: System learns from every trade and adapts behavior")
    print("🧠 This is how Northstar evolves from rules-based to intelligence-based")

if __name__ == "__main__":
    main()