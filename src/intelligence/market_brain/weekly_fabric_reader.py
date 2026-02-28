#!/usr/bin/env python3
"""
🧬 WEEKLY FABRIC READER - NORTHSTAR V3 MARKET BRAIN
The Intelligence Interface: Reading Causal Relationships for Decision Making

This provides the interface for V3 systems to access weekly causal fabric data:
- Real-time relationship queries for Capital Allocator
- Trend analysis for Narrative Engine
- Anticipatory signals for Intelligence Stack
- Integration with existing V3 workflows

Integration with V3:
- Feeds into Capital Allocator for regime-aware allocation
- Provides narrative context for Narrative Engine
- Supplies anticipatory signals for Intelligence Stack
- Enhances Market Pulse with relationship dynamics
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Import V3 components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.intelligence.market_brain.weekly_relationship_store import WeeklyRelationshipStore

class WeeklyFabricReader:
    """
    Weekly Fabric Reader - Intelligence Interface
    
    Provides high-level access to causal relationship data for:
    - Capital allocation decisions
    - Narrative generation
    - Anticipatory intelligence
    - Market pulse enhancement
    - Regime transition detection
    """
    
    def __init__(self):
        self.name = "Weekly Fabric Reader"
        self.version = "1.0"
        
        # Initialize relationship store
        self.store = WeeklyRelationshipStore()
        
        # Reader configuration
        self.config = {
            'default_lookback_weeks': 8,
            'trend_significance_threshold': 0.15,
            'high_confidence_threshold': 0.7,
            'high_novelty_threshold': 0.7,
            'pressure_aggregation_window': 4,
            'anticipatory_horizon_focus': [4, 12],  # Focus on 1-month and 3-month horizons
            'narrative_relationship_limit': 10,
            'transition_probability_cap': 0.85,
            'min_relationships_for_high_confidence': 25,
        }
        
        # Relationship interpretation mappings
        self.relationship_interpretations = {
            'macro_to_sector': {
                'positive': "Macro tailwinds are strengthening {dst_name} sector performance",
                'negative': "Macro headwinds are pressuring {dst_name} sector returns"
            },
            'fx_to_sector': {
                'positive': "Currency movements are boosting {dst_name} sector competitiveness",
                'negative': "Currency pressures are weighing on {dst_name} sector margins"
            },
            'flows_to_sector': {
                'positive': "Capital flows are driving momentum in {dst_name} sector",
                'negative': "Capital outflows are creating pressure in {dst_name} sector"
            },
            'sector_to_corporate': {
                'positive': "Sector rotation is favoring {dst_name} performance",
                'negative': "Sector rotation is creating headwinds for {dst_name}"
            }
        }

    def _resolve_analysis_window(self, weeks_back: int) -> Tuple[datetime, datetime]:
        """
        Resolve a robust query window.

        If there are no relationships in the most recent `weeks_back` window
        relative to wall-clock time, fall back to the latest available index date.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks_back)

        try:
            index_df = self.store.load_relationship_index()
            if index_df.empty or 'date' not in index_df.columns:
                return start_date, end_date

            latest_date = pd.to_datetime(index_df['date'], errors='coerce').dropna().max()
            if pd.isna(latest_date):
                return start_date, end_date

            latest_dt = latest_date.to_pydatetime()
            if latest_dt < start_date:
                end_date = latest_dt
                start_date = end_date - timedelta(weeks=weeks_back)
        except Exception:
            pass

        return start_date, end_date
    
    def get_current_market_pressure(self, weeks_back: int = 4) -> Dict:
        """Get current market pressure from recent relationships"""
        
        try:
            start_date, end_date = self._resolve_analysis_window(weeks_back)

            # Get recent high-confidence relationships
            recent_relationships = self.store.query_relationships(
                start_date=start_date,
                end_date=end_date,
                min_confidence=self.config['high_confidence_threshold']
            )
            
            if recent_relationships.empty:
                return {'pressure_vectors': {}, 'dominant_forces': [], 'regime_pressure': 'neutral'}
            
            # Calculate pressure vectors by source type
            pressure_vectors = {}
            
            for src_type in recent_relationships['src_type'].unique():
                src_relationships = recent_relationships[recent_relationships['src_type'] == src_type]
                
                # Calculate weighted average pressure
                total_pressure = 0
                total_weight = 0
                
                for _, rel in src_relationships.iterrows():
                    weight = rel['confidence'] * (1 + rel['novelty'])  # Weight by confidence and novelty
                    total_pressure += rel['beta'] * weight
                    total_weight += weight
                
                if total_weight > 0:
                    avg_pressure = total_pressure / total_weight
                    pressure_vectors[src_type] = {
                        'pressure': float(avg_pressure),
                        'strength': float(abs(avg_pressure)),
                        'direction': 'positive' if avg_pressure > 0 else 'negative',
                        'confidence': float(src_relationships['confidence'].mean()),
                        'relationship_count': len(src_relationships)
                    }
            
            # Identify dominant forces
            dominant_forces = sorted(
                pressure_vectors.items(),
                key=lambda x: x[1]['strength'],
                reverse=True
            )[:3]  # Top 3 forces
            
            # Determine overall regime pressure
            total_market_pressure = sum(pv['pressure'] for pv in pressure_vectors.values())
            
            if total_market_pressure > 0.2:
                regime_pressure = 'expansionary'
            elif total_market_pressure < -0.2:
                regime_pressure = 'contractionary'
            else:
                regime_pressure = 'neutral'
            
            return {
                'pressure_vectors': pressure_vectors,
                'dominant_forces': [{'type': k, **v} for k, v in dominant_forces],
                'regime_pressure': regime_pressure,
                'total_pressure': float(total_market_pressure),
                'analysis_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error getting market pressure: {e}")
            return {'pressure_vectors': {}, 'dominant_forces': [], 'regime_pressure': 'neutral'}
    
    def get_emerging_relationships(self, weeks_back: int = 8, min_novelty: float = None) -> List[Dict]:
        """Get emerging relationships that signal structural shifts"""
        
        try:
            if min_novelty is None:
                min_novelty = self.config['high_novelty_threshold']

            start_date, end_date = self._resolve_analysis_window(weeks_back)
            
            # Query recent high-novelty relationships
            recent_relationships = self.store.query_relationships(
                start_date=start_date,
                end_date=end_date,
                min_confidence=0.5  # Lower confidence threshold for emerging relationships
            )
            
            if recent_relationships.empty:
                return []
            
            # Filter for high novelty
            emerging = recent_relationships[recent_relationships['novelty'] >= min_novelty]
            
            if emerging.empty:
                return []
            
            # Sort by novelty and confidence
            emerging = emerging.sort_values(['novelty', 'confidence'], ascending=False)

            # Keep one representative per source-target-horizon to reduce repetitive rows.
            dedupe_cols = [c for c in ['src_name', 'dst_name', 'horizon'] if c in emerging.columns]
            if len(dedupe_cols) == 3:
                emerging = emerging.drop_duplicates(subset=dedupe_cols, keep='first')
            
            # Format for output
            emerging_relationships = []
            
            for _, rel in emerging.head(10).iterrows():  # Top 10 emerging relationships
                relationship = {
                    'source': rel['src_name'],
                    'target': rel['dst_name'],
                    'source_type': rel['src_type'],
                    'target_type': rel['dst_type'],
                    'horizon_weeks': int(rel['horizon']),
                    'strength': float(rel['beta']),
                    'confidence': float(rel['confidence']),
                    'novelty': float(rel['novelty']),
                    'direction': 'positive' if rel['direction'] > 0 else 'negative',
                    'date_detected': rel['date'].isoformat(),
                    'interpretation': self.interpret_relationship(rel),
                    'anticipatory_signal': self.assess_anticipatory_signal(rel)
                }
                emerging_relationships.append(relationship)
            
            return emerging_relationships
            
        except Exception as e:
            print(f"❌ Error getting emerging relationships: {e}")
            return []

    def get_data_freshness(self) -> Dict:
        """Return relationship and tensor freshness details for dashboard diagnostics."""
        freshness = {
            'relationship_latest_date': None,
            'relationship_count': 0,
            'relationship_years': [],
            'tensor_latest_date': None,
            'lag_days': None,
        }

        try:
            index_df = self.store.load_relationship_index()
            if isinstance(index_df, pd.DataFrame) and not index_df.empty:
                dates = pd.to_datetime(index_df.get('date'), errors='coerce').dropna()
                if not dates.empty:
                    freshness['relationship_latest_date'] = dates.max().isoformat()
                freshness['relationship_count'] = int(len(index_df))
                if 'year' in index_df.columns:
                    freshness['relationship_years'] = sorted(index_df['year'].dropna().astype(int).unique().tolist())
        except Exception:
            pass

        try:
            tensor_paths = [
                os.path.join('data', 'processed', 'market_tensor.parquet'),
                os.path.join('data', 'weekly_insights', 'weekly_tensor_store.parquet'),
                os.path.join('data', 'processed', 'market_tensor_latest.parquet'),
            ]
            latest_candidates = []
            for tensor_path in tensor_paths:
                if not os.path.exists(tensor_path):
                    continue
                tensor = pd.read_parquet(tensor_path)
                if isinstance(tensor.index, pd.DatetimeIndex) and len(tensor.index) > 0:
                    latest_candidates.append(pd.to_datetime(tensor.index.max(), errors='coerce'))
                    continue
                if isinstance(tensor, pd.DataFrame) and 'date' in tensor.columns:
                    latest_candidates.append(pd.to_datetime(tensor['date'], errors='coerce').dropna().max())

            latest_candidates = [d for d in latest_candidates if pd.notna(d)]
            if latest_candidates:
                freshness['tensor_latest_date'] = max(latest_candidates).isoformat()
        except Exception:
            pass

        try:
            rel = pd.to_datetime(freshness['relationship_latest_date'], errors='coerce')
            ten = pd.to_datetime(freshness['tensor_latest_date'], errors='coerce')
            if pd.notna(rel) and pd.notna(ten):
                freshness['lag_days'] = int((ten - rel).days)
        except Exception:
            pass

        return freshness
    
    def get_relationship_trends(self, weeks_back: int = None) -> Dict:
        """Get relationship trends for narrative generation"""
        
        try:
            if weeks_back is None:
                weeks_back = self.config['default_lookback_weeks']
            
            # Use resolved window so stale calendars don't produce empty trends.
            start_date, end_date = self._resolve_analysis_window(weeks_back)
            recent_relationships = self.store.query_relationships(
                start_date=start_date,
                end_date=end_date,
                min_confidence=0.6
            )
            if recent_relationships.empty:
                trends = {'rising_edges': [], 'collapsing_edges': [], 'new_relationships': []}
            else:
                trends = self.store.analyze_relationship_trends(recent_relationships)
            
            # Enhance with interpretations
            enhanced_trends = {
                'rising_relationships': [],
                'weakening_relationships': [],
                'new_relationships': [],
                'narrative_summary': ""
            }
            
            # Process rising edges
            for edge in trends.get('rising_edges', [])[:5]:  # Top 5
                enhanced_edge = {
                    **edge,
                    'interpretation': self.interpret_edge_change(edge, 'rising'),
                    'market_implication': self.assess_market_implication(edge, 'rising')
                }
                enhanced_trends['rising_relationships'].append(enhanced_edge)
            
            # Process collapsing edges
            for edge in trends.get('collapsing_edges', [])[:5]:  # Top 5
                enhanced_edge = {
                    **edge,
                    'interpretation': self.interpret_edge_change(edge, 'weakening'),
                    'market_implication': self.assess_market_implication(edge, 'weakening')
                }
                enhanced_trends['weakening_relationships'].append(enhanced_edge)
            
            # Process new relationships
            for rel in trends.get('new_relationships', [])[:5]:  # Top 5
                enhanced_rel = {
                    **rel,
                    'interpretation': self.interpret_new_relationship(rel),
                    'structural_significance': self.assess_structural_significance(rel)
                }
                enhanced_trends['new_relationships'].append(enhanced_rel)
            
            # Generate narrative summary
            enhanced_trends['narrative_summary'] = self.generate_trend_narrative(enhanced_trends)
            
            return enhanced_trends
            
        except Exception as e:
            print(f"❌ Error getting relationship trends: {e}")
            return {'rising_relationships': [], 'weakening_relationships': [], 'new_relationships': [], 'narrative_summary': ""}
    
    def get_anticipatory_signals(self, focus_horizons: List[int] = None) -> Dict:
        """Get anticipatory signals for forward-looking intelligence"""
        
        try:
            if focus_horizons is None:
                focus_horizons = self.config['anticipatory_horizon_focus']

            start_date, end_date = self._resolve_analysis_window(4)
            
            # Get recent high-confidence, high-novelty relationships
            recent_relationships = self.store.query_relationships(
                start_date=start_date,
                end_date=end_date,
                min_confidence=0.6,
                horizons=focus_horizons
            )
            
            if recent_relationships.empty:
                return {'signals': [], 'regime_transition_probability': 0.0, 'key_relationships_to_watch': []}
            
            # Filter for anticipatory signals (high novelty or strong relationships)
            anticipatory_mask = (
                (recent_relationships['novelty'] >= 0.6) |
                (recent_relationships['confidence'] >= 0.8)
            )
            
            anticipatory_relationships = recent_relationships[anticipatory_mask]
            
            signals = []
            
            for _, rel in anticipatory_relationships.iterrows():
                signal = {
                    'signal_type': self.classify_signal_type(rel),
                    'relationship': f"{rel['src_name']} → {rel['dst_name']}",
                    'horizon_weeks': int(rel['horizon']),
                    'signal_strength': float(rel['novelty'] * rel['confidence']),
                    'direction': 'positive' if rel['direction'] > 0 else 'negative',
                    'confidence': float(rel['confidence']),
                    'market_implication': self.assess_anticipatory_implication(rel),
                    'watch_for': self.generate_watch_signals(rel),
                    'date_detected': rel['date'].isoformat()
                }
                signals.append(signal)
            
            # Sort by signal strength
            signals = sorted(signals, key=lambda x: x['signal_strength'], reverse=True)
            
            # Assess regime transition probability
            regime_transition_prob = self.assess_regime_transition_probability(anticipatory_relationships)
            
            # Key relationships to watch
            key_relationships = self.identify_key_relationships_to_watch(anticipatory_relationships)
            
            return {
                'signals': signals[:10],  # Top 10 signals
                'regime_transition_probability': float(regime_transition_prob),
                'key_relationships_to_watch': key_relationships,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error getting anticipatory signals: {e}")
            return {'signals': [], 'regime_transition_probability': 0.0, 'key_relationships_to_watch': []}
    
    def get_capital_allocation_insights(self) -> Dict:
        """Get insights specifically for capital allocation decisions"""
        
        try:
            # Get current pressure and trends
            pressure = self.get_current_market_pressure()
            trends = self.get_relationship_trends(weeks_back=6)
            signals = self.get_anticipatory_signals()
            
            # Calculate strategy fitness multipliers
            strategy_fitness = self.calculate_strategy_fitness(pressure, trends)
            
            # Identify sector rotation signals
            sector_rotation = self.identify_sector_rotation_signals(trends)
            
            # Risk adjustment recommendations
            risk_adjustments = self.recommend_risk_adjustments(pressure, signals)
            
            return {
                'strategy_fitness_multipliers': strategy_fitness,
                'sector_rotation_signals': sector_rotation,
                'risk_adjustments': risk_adjustments,
                'market_pressure_summary': pressure,
                'anticipatory_positioning': self.recommend_anticipatory_positioning(signals),
                'confidence_level': self.calculate_overall_confidence(pressure, trends, signals)
            }
            
        except Exception as e:
            print(f"❌ Error getting capital allocation insights: {e}")
            return {}
    
    def interpret_relationship(self, relationship) -> str:
        """Interpret a single relationship for narrative purposes"""
        
        try:
            src_type = relationship['src_type']
            dst_type = relationship['dst_type']
            direction = 'positive' if relationship['direction'] > 0 else 'negative'
            
            # Create interpretation key
            interp_key = f"{src_type}_to_{dst_type}"
            
            if interp_key in self.relationship_interpretations:
                template = self.relationship_interpretations[interp_key][direction]
                return template.format(
                    src_name=relationship['src_name'],
                    dst_name=relationship['dst_name']
                )
            else:
                # Generic interpretation
                direction_word = "boosting" if direction == 'positive' else "pressuring"
                return f"{relationship['src_name']} is {direction_word} {relationship['dst_name']} performance"
                
        except Exception as e:
            return f"Relationship detected between {relationship.get('src_name', 'unknown')} and {relationship.get('dst_name', 'unknown')}"
    
    def assess_anticipatory_signal(self, relationship) -> str:
        """Assess the anticipatory significance of a relationship"""
        
        try:
            novelty = relationship['novelty']
            confidence = relationship['confidence']
            horizon = relationship['horizon']
            
            if novelty > 0.8 and confidence > 0.7:
                if horizon <= 4:
                    return "Strong near-term structural shift signal"
                else:
                    return "Strong medium-term regime change signal"
            elif novelty > 0.6:
                return "Emerging relationship worth monitoring"
            elif confidence > 0.8:
                return "Established relationship strengthening"
            else:
                return "Weak signal requiring confirmation"
                
        except:
            return "Signal significance unclear"
    
    def interpret_edge_change(self, edge, change_type) -> str:
        """Interpret changes in relationship strength"""
        
        try:
            src_name = edge['src_name']
            dst_name = edge['dst_name']
            change_magnitude = abs(edge['confidence_change'])
            
            if change_type == 'rising':
                if change_magnitude > 0.3:
                    return f"Strong strengthening of {src_name} influence on {dst_name}"
                else:
                    return f"Gradual strengthening of {src_name}-{dst_name} relationship"
            else:  # weakening
                if change_magnitude > 0.3:
                    return f"Sharp weakening of {src_name} influence on {dst_name}"
                else:
                    return f"Gradual weakening of {src_name}-{dst_name} relationship"
                    
        except:
            return "Relationship strength change detected"
    
    def assess_market_implication(self, edge, change_type) -> str:
        """Assess market implications of relationship changes"""
        
        try:
            # This would be enhanced with domain knowledge
            if change_type == 'rising':
                return "Increasing market sensitivity to this factor"
            else:
                return "Decreasing market sensitivity to this factor"
                
        except:
            return "Market implication unclear"
    
    def interpret_new_relationship(self, relationship) -> str:
        """Interpret newly discovered relationships"""
        
        try:
            return f"New causal link discovered: {relationship['src_name']} now influencing {relationship['dst_name']}"
        except:
            return "New relationship discovered"
    
    def assess_structural_significance(self, relationship) -> str:
        """Assess structural significance of new relationships"""
        
        try:
            novelty = relationship['novelty']
            confidence = relationship['confidence']
            
            if novelty > 0.8 and confidence > 0.6:
                return "High structural significance - potential regime shift"
            elif novelty > 0.6:
                return "Moderate structural significance - emerging pattern"
            else:
                return "Low structural significance - requires monitoring"
                
        except:
            return "Structural significance unclear"
    
    def generate_trend_narrative(self, trends) -> str:
        """Generate narrative summary of trends"""
        
        try:
            narrative_parts = []
            
            # Rising relationships
            if trends['rising_relationships']:
                count = len(trends['rising_relationships'])
                narrative_parts.append(f"{count} relationships are strengthening")
            
            # Weakening relationships
            if trends['weakening_relationships']:
                count = len(trends['weakening_relationships'])
                narrative_parts.append(f"{count} relationships are weakening")
            
            # New relationships
            if trends['new_relationships']:
                count = len(trends['new_relationships'])
                narrative_parts.append(f"{count} new relationships have emerged")
            
            if narrative_parts:
                return "Market structure is evolving: " + ", ".join(narrative_parts) + "."
            else:
                return "Market relationships remain stable with no significant structural changes."
                
        except:
            return "Trend analysis completed."
    
    def classify_signal_type(self, relationship) -> str:
        """Classify the type of anticipatory signal"""
        
        try:
            src_type = relationship['src_type']
            novelty = relationship['novelty']
            
            if novelty > 0.8:
                return f"structural_shift_{src_type}"
            elif novelty > 0.6:
                return f"emerging_pattern_{src_type}"
            else:
                return f"strengthening_{src_type}"
                
        except:
            return "unknown_signal"
    
    def assess_anticipatory_implication(self, relationship) -> str:
        """Assess implications of anticipatory signals"""
        
        try:
            # This would be enhanced with domain-specific knowledge
            horizon = relationship['horizon']
            
            if horizon <= 4:
                return "Near-term market positioning opportunity"
            elif horizon <= 12:
                return "Medium-term strategic positioning signal"
            else:
                return "Long-term structural change indicator"
                
        except:
            return "Implication assessment pending"
    
    def generate_watch_signals(self, relationship) -> List[str]:
        """Generate specific things to watch for based on relationship"""
        
        try:
            watch_signals = []
            
            src_name = relationship['src_name']
            dst_name = relationship['dst_name']
            
            watch_signals.append(f"Monitor {src_name} for continued strength")
            watch_signals.append(f"Watch {dst_name} for responsive movements")
            
            if relationship['novelty'] > 0.7:
                watch_signals.append("Confirm relationship persistence over next 2-3 weeks")
            
            return watch_signals
            
        except:
            return ["Monitor relationship development"]
    
    def assess_regime_transition_probability(self, relationships) -> float:
        """Assess probability of regime transition based on relationships"""
        
        try:
            if relationships.empty:
                return 0.0

            rel = relationships.copy()
            novelty = pd.to_numeric(rel.get('novelty', 0.0), errors='coerce').fillna(0.0).clip(0.0, 1.0)
            confidence = pd.to_numeric(rel.get('confidence', 0.0), errors='coerce').fillna(0.0).clip(0.0, 1.0)
            beta = pd.to_numeric(rel.get('beta', 0.0), errors='coerce').fillna(0.0)
            beta_strength = np.tanh(beta.abs())

            per_edge_score = 0.50 * novelty + 0.30 * confidence + 0.20 * beta_strength
            high_novel_share = float((novelty > 0.7).mean())
            edge_score = float(per_edge_score.mean())

            # Confidence in probability should rise with sample size.
            sample_factor = float(np.clip(
                np.log1p(len(rel)) / np.log1p(40.0),
                0.0,
                1.0
            ))

            raw_prob = (0.55 * edge_score + 0.45 * high_novel_share) * sample_factor
            cap = float(self.config.get('transition_probability_cap', 0.85))
            return float(np.clip(raw_prob, 0.0, cap))
            
        except:
            return 0.0
    
    def identify_key_relationships_to_watch(self, relationships) -> List[Dict]:
        """Identify key relationships to monitor"""
        
        try:
            # Sort by combined novelty and confidence
            relationships['watch_score'] = relationships['novelty'] * relationships['confidence']
            top_relationships = relationships.nlargest(5, 'watch_score')
            
            key_relationships = []
            
            for _, rel in top_relationships.iterrows():
                key_rel = {
                    'relationship': f"{rel['src_name']} → {rel['dst_name']}",
                    'watch_score': float(rel['watch_score']),
                    'reason': "High novelty and confidence combination",
                    'horizon_weeks': int(rel['horizon'])
                }
                key_relationships.append(key_rel)
            
            return key_relationships
            
        except:
            return []
    
    def calculate_strategy_fitness(self, pressure, trends) -> Dict:
        """Calculate strategy fitness multipliers based on current conditions"""
        
        try:
            # Start from neutral and apply smooth bounded adjustments.
            fitness_multipliers = {
                'growth_strategies': 1.0,
                'defensive_strategies': 1.0,
                'export_focused': 1.0,
                'import_dependent': 1.0,
                'liquidity_sensitive': 1.0,
                'credit_sensitive': 1.0,
                'cyclicals': 1.0,
                'quality_defensives': 1.0,
            }

            for force_type, force_data in pressure.get('pressure_vectors', {}).items():
                direction = str(force_data.get('direction', 'neutral')).lower()
                pressure_val = float(force_data.get('pressure', 0.0) or 0.0)
                strength = float(force_data.get('strength', abs(pressure_val)) or abs(pressure_val))
                impact = float(min(0.25, abs(pressure_val) * 0.35 + strength * 0.15))
                signed = impact if direction == 'positive' else -impact

                if force_type == 'macro':
                    fitness_multipliers['growth_strategies'] += signed
                    fitness_multipliers['defensive_strategies'] -= 0.6 * signed
                    fitness_multipliers['cyclicals'] += 0.8 * signed
                elif force_type == 'fx':
                    fitness_multipliers['export_focused'] += signed
                    fitness_multipliers['import_dependent'] -= signed
                elif force_type == 'flows':
                    fitness_multipliers['growth_strategies'] += 0.7 * signed
                    fitness_multipliers['quality_defensives'] += -0.5 * signed
                elif force_type == 'credit':
                    fitness_multipliers['credit_sensitive'] -= signed
                    fitness_multipliers['quality_defensives'] += -0.6 * signed
                elif force_type == 'liquidity':
                    fitness_multipliers['liquidity_sensitive'] += signed
                    fitness_multipliers['defensive_strategies'] += -0.4 * signed
                elif force_type == 'sector':
                    fitness_multipliers['cyclicals'] += 0.6 * signed
                    fitness_multipliers['quality_defensives'] += -0.4 * signed
                elif force_type == 'corporate':
                    fitness_multipliers['quality_defensives'] += 0.7 * (-signed)
                    fitness_multipliers['growth_strategies'] += 0.4 * signed

            # Regime-pressure overlay to keep output coherent.
            regime_pressure = str(pressure.get('regime_pressure', 'neutral')).lower()
            if regime_pressure == 'contractionary':
                fitness_multipliers['defensive_strategies'] += 0.08
                fitness_multipliers['quality_defensives'] += 0.08
                fitness_multipliers['growth_strategies'] -= 0.08
                fitness_multipliers['cyclicals'] -= 0.08
            elif regime_pressure == 'expansionary':
                fitness_multipliers['growth_strategies'] += 0.08
                fitness_multipliers['cyclicals'] += 0.08
                fitness_multipliers['defensive_strategies'] -= 0.06

            # Keep multipliers economically meaningful and never zero.
            for key, value in list(fitness_multipliers.items()):
                fitness_multipliers[key] = float(np.clip(value, 0.75, 1.25))

            return fitness_multipliers
            
        except:
            return {}
    
    def identify_sector_rotation_signals(self, trends) -> List[Dict]:
        """Identify sector rotation signals from trends"""
        
        try:
            rotation_signals = []
            
            # Look for sector-related relationship changes
            for rel in trends.get('rising_relationships', []):
                if 'sector' in rel.get('dst_type', ''):
                    rotation_signals.append({
                        'type': 'sector_strengthening',
                        'sector': rel['dst_name'],
                        'driver': rel['src_name'],
                        'strength': rel['confidence_change']
                    })
            
            for rel in trends.get('weakening_relationships', []):
                if 'sector' in rel.get('dst_type', ''):
                    rotation_signals.append({
                        'type': 'sector_weakening',
                        'sector': rel['dst_name'],
                        'driver': rel['src_name'],
                        'strength': abs(rel['confidence_change'])
                    })
            
            return rotation_signals
            
        except:
            return []
    
    def recommend_risk_adjustments(self, pressure, signals) -> Dict:
        """Recommend risk adjustments based on current conditions"""
        
        try:
            adjustments = {
                'overall_risk_level': 'neutral',
                'specific_adjustments': [],
                'rationale': []
            }
            
            # Assess overall market pressure
            total_pressure = pressure.get('total_pressure', 0)
            
            if abs(total_pressure) > 0.3:
                if total_pressure > 0:
                    adjustments['overall_risk_level'] = 'increase'
                    adjustments['rationale'].append("Strong positive market pressure supports higher risk")
                else:
                    adjustments['overall_risk_level'] = 'decrease'
                    adjustments['rationale'].append("Strong negative market pressure suggests risk reduction")
            
            # Check for high regime transition probability
            transition_prob = signals.get('regime_transition_probability', 0)
            
            if transition_prob > 0.6:
                adjustments['specific_adjustments'].append({
                    'type': 'regime_transition_hedge',
                    'action': 'increase_cash_buffer',
                    'magnitude': 'moderate'
                })
                adjustments['rationale'].append("High regime transition probability suggests defensive positioning")
            
            return adjustments
            
        except:
            return {'overall_risk_level': 'neutral', 'specific_adjustments': [], 'rationale': []}
    
    def recommend_anticipatory_positioning(self, signals) -> List[Dict]:
        """Recommend anticipatory positioning based on signals"""
        
        try:
            positioning_recommendations = []
            
            for signal in signals.get('signals', [])[:5]:  # Top 5 signals
                if signal['signal_strength'] > 0.5:
                    recommendation = {
                        'signal': signal['relationship'],
                        'action': 'monitor_and_position' if signal['confidence'] > 0.7 else 'monitor_only',
                        'horizon': f"{signal['horizon_weeks']} weeks",
                        'confidence': signal['confidence'],
                        'rationale': signal['market_implication']
                    }
                    positioning_recommendations.append(recommendation)
            
            return positioning_recommendations
            
        except:
            return []
    
    def calculate_overall_confidence(self, pressure, trends, signals) -> float:
        """Calculate overall confidence in the analysis"""
        
        try:
            confidence_factors = []
            
            # Pressure confidence
            if pressure['pressure_vectors']:
                avg_pressure_confidence = np.mean([
                    pv['confidence'] for pv in pressure['pressure_vectors'].values()
                ])
                confidence_factors.append(avg_pressure_confidence)
            
            # Trend confidence
            all_trend_relationships = (
                trends.get('rising_relationships', []) +
                trends.get('weakening_relationships', []) +
                trends.get('new_relationships', [])
            )
            
            if all_trend_relationships:
                trend_confidences = [
                    rel.get('confidence', rel.get('recent_confidence', 0.5))
                    for rel in all_trend_relationships
                ]
                avg_trend_confidence = np.mean(trend_confidences)
                confidence_factors.append(avg_trend_confidence)
            
            # Signal confidence
            signal_list = signals.get('signals', [])
            if signal_list:
                avg_signal_confidence = np.mean([s['confidence'] for s in signal_list])
                confidence_factors.append(avg_signal_confidence)
            
            relationship_count = 0
            relationship_count += int(sum(
                int(v.get('relationship_count', 0) or 0)
                for v in pressure.get('pressure_vectors', {}).values()
            ))
            relationship_count += int(len(trends.get('rising_relationships', [])))
            relationship_count += int(len(trends.get('weakening_relationships', [])))
            relationship_count += int(len(trends.get('new_relationships', [])))
            relationship_count += int(len(signals.get('signals', [])))

            base_conf = float(np.mean(confidence_factors)) if confidence_factors else 0.45
            sample_conf = float(np.clip(
                np.log1p(max(0, relationship_count)) / np.log1p(40.0),
                0.0,
                1.0
            ))
            overall = 0.70 * base_conf + 0.30 * sample_conf

            # Prevent "always high confidence" when data is sparse.
            min_for_high = int(self.config.get('min_relationships_for_high_confidence', 25))
            if relationship_count < min_for_high:
                overall = min(overall, 0.72)
            if relationship_count < 5:
                overall = min(overall, 0.55)

            return float(np.clip(overall, 0.10, 0.95))
                
        except:
            return 0.5

def main():
    """Test the fabric reader"""
    
    reader = WeeklyFabricReader()
    
    print("🧬 Testing Weekly Fabric Reader...")
    
    # Test market pressure
    pressure = reader.get_current_market_pressure()
    print(f"   Market pressure: {len(pressure['pressure_vectors'])} vectors")
    
    # Test emerging relationships
    emerging = reader.get_emerging_relationships()
    print(f"   Emerging relationships: {len(emerging)}")
    
    # Test trends
    trends = reader.get_relationship_trends()
    print(f"   Relationship trends: {len(trends['rising_relationships'])} rising, {len(trends['weakening_relationships'])} weakening")
    
    # Test anticipatory signals
    signals = reader.get_anticipatory_signals()
    print(f"   Anticipatory signals: {len(signals['signals'])}")
    
    # Test capital allocation insights
    insights = reader.get_capital_allocation_insights()
    print(f"   Capital allocation insights: {len(insights)} categories")
    
    print("✅ Weekly Fabric Reader test completed")
    return True

if __name__ == "__main__":
    main()
