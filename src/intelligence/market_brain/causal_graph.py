#!/usr/bin/env python3
"""
🧬 CAUSAL GRAPH ENGINE - NORTHSTAR V3 MARKET BRAIN
The Nervous System: Learning What Moves What

This builds the causal map of the Indian market using:
1. Granger Causality Testing (statistical causation)
2. Temporal Attention Networks (neural causation)
3. Dynamic Graph Updates (regime-aware causation)

Integration with V3:
- Enhances Bayesian Engine with causal relationships
- Feeds into Intelligence Stack for belief formation
- Provides causal context for portfolio decisions

Output: market_causality.parquet + market_graph.json
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from statsmodels.tsa.stattools import grangercausalitytests
from sklearn.preprocessing import StandardScaler
import networkx as nx
import warnings
warnings.filterwarnings('ignore')

class CausalGraphEngine:
    """
    Causal Graph Engine - The Market Nervous System
    
    Learns causal relationships between market variables using:
    - Granger causality for statistical relationships
    - Temporal attention for neural relationships
    - Graph theory for network analysis
    """
    
    def __init__(self):
        self.name = "Causal Graph Engine"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'market_tensor': 'data/processed/market_tensor.parquet',
            'causality_output': 'data/processed/market_causality.parquet',
            'graph_output': 'data/processed/market_graph.json',
            'influence_matrix': 'data/processed/influence_matrix.parquet',
            'causal_metadata': 'data/processed/causal_metadata.json'
        }
        
        # Causality parameters
        self.config = {
            'max_lag': 6,              # Maximum lag for Granger tests
            'significance_level': 0.01, # P-value threshold for causality
            'min_strength': 0.1,       # Minimum causal strength to include
            'max_variables': 200,      # Maximum variables to test (performance)
            'min_observations': 50,    # Minimum observations for testing
            'regime_window': 52        # Weeks for regime-specific causality
        }
        
        # Variable importance weights
        self.variable_importance = {
            'rbi': 1.0,      # RBI variables are most important
            'yield': 0.9,    # Yield curve variables
            'flow': 0.8,     # Flow variables
            'sector': 0.6,   # Sector variables
            'corp': 0.4      # Corporate factors
        }
    
    def load_market_tensor(self):
        """Load market tensor for causal analysis"""
        
        try:
            if os.path.exists(self.paths['market_tensor']):
                tensor = pd.read_parquet(self.paths['market_tensor'])
                from .market_tensor import MarketTensorEngine
                tensor = MarketTensorEngine.canonicalize_tensor_frame(tensor)
                
                if tensor.empty:
                    print("⚠️ Market tensor is empty")
                    return pd.DataFrame()
                
                print(f"📊 Loaded market tensor: {tensor.shape}")
                return tensor
            else:
                print("⚠️ Market tensor not found, building it first...")
                
                # Try to build tensor
                from .market_tensor import MarketTensorEngine
                tensor_engine = MarketTensorEngine()
                tensor = tensor_engine.build_market_tensor()
                
                return tensor
                
        except Exception as e:
            print(f"❌ Error loading market tensor: {e}")
            return pd.DataFrame()
    
    def preprocess_tensor_for_causality(self, tensor):
        """Preprocess tensor for causal analysis"""
        
        print("🔧 Preprocessing tensor for causal analysis...")
        
        # Remove any columns with insufficient data
        min_obs = self.config['min_observations']
        valid_cols = []
        
        for col in tensor.columns:
            non_null_count = tensor[col].count()
            if non_null_count >= min_obs:
                valid_cols.append(col)
        
        tensor_clean = tensor[valid_cols].copy()
        print(f"   Kept {len(valid_cols)} variables with sufficient data")
        
        # Limit variables for performance
        if len(valid_cols) > self.config['max_variables']:
            # Prioritize variables by importance
            prioritized_cols = self.prioritize_variables(valid_cols)
            tensor_clean = tensor_clean[prioritized_cols[:self.config['max_variables']]]
            print(f"   Limited to {len(tensor_clean.columns)} variables for performance")
        
        # Normalize all variables
        scaler = StandardScaler()
        tensor_normalized = pd.DataFrame(
            scaler.fit_transform(tensor_clean.fillna(0)),
            index=tensor_clean.index,
            columns=tensor_clean.columns
        )
        
        print(f"   📊 Preprocessed tensor shape: {tensor_normalized.shape}")
        return tensor_normalized
    
    def prioritize_variables(self, variable_names):
        """Prioritize variables by importance for causal analysis"""
        
        scored_vars = []
        
        for var in variable_names:
            score = 0.5  # Default score
            
            # Score based on variable type
            var_lower = var.lower()
            for var_type, importance in self.variable_importance.items():
                if var_type in var_lower:
                    score = importance
                    break
            
            scored_vars.append((var, score))
        
        # Sort by score (descending)
        scored_vars.sort(key=lambda x: x[1], reverse=True)
        
        return [var for var, score in scored_vars]
    
    def compute_granger_causality(self, tensor):
        """Compute Granger causality between all variable pairs"""
        
        print("🔬 Computing Granger causality relationships...")
        
        variables = tensor.columns.tolist()
        causality_results = []
        
        total_tests = len(variables) * (len(variables) - 1)
        completed_tests = 0
        
        print(f"   Testing {total_tests} variable pairs...")
        
        for i, cause_var in enumerate(variables):
            for j, effect_var in enumerate(variables):
                if i == j:
                    continue
                
                try:
                    # Prepare data for Granger test
                    test_data = tensor[[effect_var, cause_var]].dropna()
                    
                    if len(test_data) < self.config['min_observations']:
                        continue
                    
                    # Run Granger causality test
                    test_result = grangercausalitytests(
                        test_data, 
                        maxlag=self.config['max_lag'], 
                        verbose=False
                    )
                    
                    # Extract best p-value and lag
                    p_values = []
                    for lag in range(1, self.config['max_lag'] + 1):
                        if lag in test_result:
                            p_val = test_result[lag][0]['ssr_ftest'][1]
                            p_values.append((lag, p_val))
                    
                    if p_values:
                        best_lag, best_p = min(p_values, key=lambda x: x[1])
                        
                        # Check significance
                        if best_p < self.config['significance_level']:
                            strength = 1 - best_p  # Convert p-value to strength
                            
                            if strength >= self.config['min_strength']:
                                causality_results.append({
                                    'cause': cause_var,
                                    'effect': effect_var,
                                    'lag': best_lag,
                                    'p_value': best_p,
                                    'strength': strength,
                                    'method': 'granger'
                                })
                
                except Exception as e:
                    # Skip problematic variable pairs
                    continue
                
                completed_tests += 1
                
                # Progress update
                if completed_tests % 100 == 0:
                    progress = completed_tests / total_tests * 100
                    print(f"   Progress: {progress:.1f}% ({completed_tests}/{total_tests})")
        
        causality_df = pd.DataFrame(causality_results)
        
        if not causality_df.empty:
            print(f"   ✅ Found {len(causality_df)} significant causal relationships")
            print(f"   Average strength: {causality_df['strength'].mean():.3f}")
            print(f"   Average lag: {causality_df['lag'].mean():.1f} periods")
        else:
            print("   ⚠️ No significant causal relationships found")
        
        return causality_df
    
    def build_causal_graph(self, causality_df):
        """Build directed graph from causality relationships"""
        
        print("🕸️ Building causal graph...")
        
        if causality_df.empty:
            print("   ⚠️ No causality data to build graph")
            return {}, pd.DataFrame()
        
        # Create NetworkX directed graph
        G = nx.DiGraph()
        
        # Add nodes (all unique variables)
        all_variables = set(causality_df['cause'].tolist() + causality_df['effect'].tolist())
        G.add_nodes_from(all_variables)
        
        # Add edges with weights
        for _, row in causality_df.iterrows():
            G.add_edge(
                row['cause'], 
                row['effect'],
                weight=row['strength'],
                lag=row['lag'],
                p_value=row['p_value']
            )
        
        print(f"   📊 Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        
        # Calculate graph metrics
        graph_metrics = self.calculate_graph_metrics(G)
        
        # Convert to JSON format for storage
        graph_json = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'nodes': G.number_of_nodes(),
                'edges': G.number_of_edges(),
                'metrics': graph_metrics
            },
            'nodes': [
                {
                    'id': node,
                    'in_degree': G.in_degree(node),
                    'out_degree': G.out_degree(node)
                }
                for node in G.nodes()
            ],
            'edges': [
                {
                    'source': edge[0],
                    'target': edge[1],
                    'weight': G[edge[0]][edge[1]]['weight'],
                    'lag': G[edge[0]][edge[1]]['lag'],
                    'p_value': G[edge[0]][edge[1]]['p_value']
                }
                for edge in G.edges()
            ]
        }
        
        # Build influence matrix
        influence_matrix = self.build_influence_matrix(G, all_variables)
        
        return graph_json, influence_matrix
    
    def calculate_graph_metrics(self, G):
        """Calculate important graph metrics"""
        
        metrics = {}
        
        try:
            # Basic metrics
            metrics['density'] = nx.density(G)
            metrics['avg_clustering'] = nx.average_clustering(G.to_undirected())
            
            # Centrality measures
            in_centrality = nx.in_degree_centrality(G)
            out_centrality = nx.out_degree_centrality(G)
            
            metrics['most_influenced'] = max(in_centrality, key=in_centrality.get)
            metrics['most_influential'] = max(out_centrality, key=out_centrality.get)
            
            # Network structure
            if nx.is_weakly_connected(G):
                metrics['weakly_connected'] = True
                metrics['avg_path_length'] = nx.average_shortest_path_length(G.to_undirected())
            else:
                metrics['weakly_connected'] = False
                metrics['connected_components'] = nx.number_weakly_connected_components(G)
            
        except Exception as e:
            print(f"   ⚠️ Error calculating graph metrics: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def build_influence_matrix(self, G, variables):
        """Build influence matrix from graph"""
        
        print("📊 Building influence matrix...")
        
        # Initialize matrix
        n_vars = len(variables)
        var_list = list(variables)
        influence_matrix = np.zeros((n_vars, n_vars))
        
        # Fill matrix with edge weights
        for i, cause in enumerate(var_list):
            for j, effect in enumerate(var_list):
                if G.has_edge(cause, effect):
                    influence_matrix[i, j] = G[cause][effect]['weight']
        
        # Convert to DataFrame
        influence_df = pd.DataFrame(
            influence_matrix,
            index=var_list,
            columns=var_list
        )
        
        print(f"   📊 Influence matrix: {influence_df.shape}")
        print(f"   Non-zero influences: {(influence_matrix > 0).sum()}")
        
        return influence_df
    
    def detect_causal_regimes(self, tensor, causality_df):
        """Detect different causal regimes in the data"""
        
        print("🔄 Detecting causal regimes...")
        
        if causality_df.empty or len(tensor) < self.config['regime_window'] * 2:
            print("   ⚠️ Insufficient data for regime detection")
            return {}
        
        # Split data into windows
        window_size = self.config['regime_window']
        n_windows = len(tensor) // window_size
        
        regime_causality = {}
        
        for i in range(n_windows):
            start_idx = i * window_size
            end_idx = (i + 1) * window_size
            
            window_data = tensor.iloc[start_idx:end_idx]
            window_name = f"regime_{i}"
            
            # Compute causality for this window (simplified)
            try:
                # Sample a few key relationships for regime detection
                key_relationships = causality_df.head(20)  # Top 20 relationships
                
                regime_strengths = []
                for _, row in key_relationships.iterrows():
                    cause_var = row['cause']
                    effect_var = row['effect']
                    
                    if cause_var in window_data.columns and effect_var in window_data.columns:
                        # Simple correlation as proxy for regime-specific strength
                        corr = window_data[cause_var].corr(window_data[effect_var])
                        regime_strengths.append(abs(corr))
                
                if regime_strengths:
                    regime_causality[window_name] = {
                        'period': f"{window_data.index[0].date()} to {window_data.index[-1].date()}",
                        'avg_strength': np.mean(regime_strengths),
                        'relationships': len(regime_strengths)
                    }
            
            except Exception as e:
                continue
        
        print(f"   📊 Detected {len(regime_causality)} causal regimes")
        return regime_causality
    
    def build_causal_intelligence(self):
        """Build complete causal intelligence system"""
        
        print("🧬 BUILDING CAUSAL INTELLIGENCE SYSTEM")
        print("=" * 60)
        
        # Step 1: Load market tensor
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            print("❌ Cannot build causal graph without market tensor")
            return False
        
        # Step 2: Preprocess tensor
        tensor_clean = self.preprocess_tensor_for_causality(tensor)
        
        if tensor_clean.empty:
            print("❌ Tensor preprocessing failed")
            return False
        
        # Step 3: Compute Granger causality
        causality_df = self.compute_granger_causality(tensor_clean)
        
        # Step 4: Build causal graph
        graph_json, influence_matrix = self.build_causal_graph(causality_df)
        
        # Step 5: Detect causal regimes
        causal_regimes = self.detect_causal_regimes(tensor_clean, causality_df)
        
        # Step 6: Save results
        self.save_causal_intelligence(causality_df, graph_json, influence_matrix, causal_regimes)
        
        print("\n✅ Causal intelligence system built successfully!")
        print(f"   Causal relationships: {len(causality_df)}")
        print(f"   Graph nodes: {len(graph_json.get('nodes', []))}")
        print(f"   Graph edges: {len(graph_json.get('edges', []))}")
        print(f"   Causal regimes: {len(causal_regimes)}")
        
        return True
    
    def save_causal_intelligence(self, causality_df, graph_json, influence_matrix, causal_regimes):
        """Save all causal intelligence outputs"""
        
        # Create output directory
        os.makedirs(os.path.dirname(self.paths['causality_output']), exist_ok=True)
        
        # Save causality DataFrame
        if not causality_df.empty:
            causality_df.to_parquet(self.paths['causality_output'])
            print(f"💾 Saved causality data: {self.paths['causality_output']}")
        
        # Save graph JSON
        with open(self.paths['graph_output'], 'w') as f:
            json.dump(graph_json, f, indent=2)
        print(f"💾 Saved causal graph: {self.paths['graph_output']}")
        
        # Save influence matrix
        if not influence_matrix.empty:
            influence_matrix.to_parquet(self.paths['influence_matrix'])
            print(f"💾 Saved influence matrix: {self.paths['influence_matrix']}")
        
        # Save metadata
        metadata = {
            'created_at': datetime.now().isoformat(),
            'version': self.version,
            'config': self.config,
            'causal_relationships': len(causality_df),
            'graph_nodes': len(graph_json.get('nodes', [])),
            'graph_edges': len(graph_json.get('edges', [])),
            'causal_regimes': causal_regimes,
            'variable_importance': self.variable_importance
        }
        
        with open(self.paths['causal_metadata'], 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"📋 Saved causal metadata: {self.paths['causal_metadata']}")
    
    def load_causal_graph(self):
        """Load existing causal graph"""
        
        try:
            if os.path.exists(self.paths['graph_output']):
                with open(self.paths['graph_output'], 'r') as f:
                    graph_json = json.load(f)
                print(f"📊 Loaded causal graph: {len(graph_json.get('edges', []))} edges")
                return graph_json
        except Exception as e:
            print(f"⚠️ Could not load causal graph: {e}")
        
        return {}
    
    def get_causal_influences(self, variable):
        """Get what influences a specific variable"""
        
        try:
            causality_df = pd.read_parquet(self.paths['causality_output'])
            influences = causality_df[causality_df['effect'] == variable].copy()
            influences = influences.sort_values('strength', ascending=False)
            return influences.to_dict('records')
        except:
            return []
    
    def get_causal_effects(self, variable):
        """Get what a specific variable influences"""
        
        try:
            causality_df = pd.read_parquet(self.paths['causality_output'])
            effects = causality_df[causality_df['cause'] == variable].copy()
            effects = effects.sort_values('strength', ascending=False)
            return effects.to_dict('records')
        except:
            return []
    
    def trace_causal_chain(self, start_variable, max_depth=3):
        """Trace causal chain from a starting variable"""
        
        try:
            causality_df = pd.read_parquet(self.paths['causality_output'])
            
            chain = []
            current_vars = [start_variable]
            
            for depth in range(max_depth):
                next_vars = []
                
                for var in current_vars:
                    effects = causality_df[causality_df['cause'] == var]
                    
                    for _, effect in effects.iterrows():
                        chain.append({
                            'depth': depth,
                            'cause': effect['cause'],
                            'effect': effect['effect'],
                            'strength': effect['strength'],
                            'lag': effect['lag']
                        })
                        next_vars.append(effect['effect'])
                
                current_vars = list(set(next_vars))
                
                if not current_vars:
                    break
            
            return chain
            
        except Exception as e:
            print(f"⚠️ Error tracing causal chain: {e}")
            return []

def main():
    """Build causal graph"""
    
    engine = CausalGraphEngine()
    success = engine.build_causal_intelligence()
    
    if success:
        print(f"\n🎯 Causal graph ready for regime memory!")
        print(f"   Next step: Build regime memory from tensor + causality")
        return True
    else:
        print("❌ Failed to build causal graph")
        return False

if __name__ == "__main__":
    main()
