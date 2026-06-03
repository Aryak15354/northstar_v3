#!/usr/bin/env python3
"""
🧠 REGIME MEMORY ENGINE - NORTHSTAR V3 MARKET BRAIN
The Memory System: Learning from Historical Market Patterns

This creates regime fingerprints using temporal autoencoders to compress
market history into learnable patterns. Northstar can then match current
conditions to historical regimes and predict what usually comes next.

Integration with V3:
- Extends existing Memory Engine with regime-specific patterns
- Feeds into Capital Allocator for regime-aware allocation
- Enhances Intelligence Stack with historical context

Output: regime_fingerprints.parquet + regime_clusters.json
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings('ignore')

# Safe TensorFlow import for M1 Macs - avoid Metal GPU crashes
TF_AVAILABLE = False
try:
    # Set environment variables for M1 Mac compatibility
    import os
    os.environ['TF_METAL_DEVICE_PLACEMENT'] = 'false'  # Disable Metal placement
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TF logs
    
    import tensorflow as tf
    from tensorflow.keras import layers, models
    
    # Configure TensorFlow for M1 Mac safety - force CPU-only mode
    tf.config.set_visible_devices([], 'GPU')  # Force CPU-only mode
    tf.get_logger().setLevel('ERROR')
    
    # Test basic functionality without GPU
    tf.constant([1, 2, 3])  # Simple test
    
    TF_AVAILABLE = True
    print("✅ TensorFlow available (CPU-only mode for M1 Mac compatibility)")
except (ImportError, Exception) as e:
    TF_AVAILABLE = False
    print(f"ℹ️ TensorFlow not available ({type(e).__name__}), using PCA for regime compression")

class RegimeMemoryEngine:
    """
    Regime Memory Engine - Market Pattern Recognition
    
    Creates compressed representations of market regimes using:
    - Temporal windows of market tensor data
    - Autoencoder compression (or PCA fallback)
    - Clustering for regime identification
    - Similarity matching for regime prediction
    """
    
    def __init__(self):
        self.name = "Regime Memory Engine"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'market_tensor': 'data/processed/market_tensor.parquet',
            'regime_fingerprints': 'data/processed/regime_fingerprints.parquet',
            'regime_clusters': 'data/processed/regime_clusters.json',
            'regime_model': 'data/models/regime_autoencoder.h5',
            'regime_pca': 'data/models/regime_pca.pkl',
            'regime_scaler': 'data/models/regime_scaler.pkl',
            'regime_metadata': 'data/processed/regime_metadata.json'
        }
        
        # Regime configuration
        self.config = {
            'window_size': 26,          # 6 months of weekly data
            'embedding_dim': 16,        # Compressed regime dimension
            'n_clusters': 8,            # Number of regime clusters
            'min_similarity': 0.7,      # Minimum similarity for regime match
            'overlap_stride': 13,       # Overlap between windows (50%)
            'autoencoder_epochs': 50,   # Training epochs for autoencoder
            'batch_size': 32,           # Batch size for training
            'validation_split': 0.2     # Validation split for training
        }
        
        # Regime interpretations
        self.regime_names = {
            0: 'Crisis',
            1: 'Recovery', 
            2: 'Expansion',
            3: 'Late Expansion',
            4: 'Peak',
            5: 'Slowdown',
            6: 'Tightening',
            7: 'Neutral'
        }
        
        # Model components
        self.scaler = None
        self.autoencoder = None
        self.encoder = None
        self.pca = None
        self.kmeans = None
    
    def load_market_tensor(self):
        """Load market tensor for regime analysis"""
        
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
    
    def create_regime_windows(self, tensor):
        """Create overlapping windows for regime analysis"""
        
        print("🪟 Creating regime windows...")
        
        window_size = self.config['window_size']
        stride = self.config['overlap_stride']
        
        if len(tensor) < window_size:
            print(f"⚠️ Insufficient data: {len(tensor)} < {window_size}")
            return np.array([]), []
        
        windows = []
        window_dates = []
        
        for i in range(0, len(tensor) - window_size + 1, stride):
            window_data = tensor.iloc[i:i + window_size]
            
            # Flatten window into single vector
            window_vector = window_data.values.flatten()
            windows.append(window_vector)
            
            # Store end date of window
            window_dates.append(window_data.index[-1])
        
        windows_array = np.array(windows)
        
        print(f"   📊 Created {len(windows)} windows of size {window_size}")
        print(f"   Vector dimension: {windows_array.shape[1]}")
        
        return windows_array, window_dates
    
    def build_autoencoder(self, input_dim):
        """Build CPU-only autoencoder for M1 Mac safety"""
        
        if not TF_AVAILABLE:
            print("   Using PCA instead of autoencoder")
            return None
        
        try:
            print("🧠 Building CPU-only autoencoder for M1 Mac...")
            
            # Force CPU device context to avoid Metal GPU crashes
            with tf.device('/CPU:0'):
                embedding_dim = self.config['embedding_dim']
                
                # Simpler, more stable architecture
                encoder_input = layers.Input(shape=(input_dim,))
                encoded = layers.Dense(256, activation='relu')(encoder_input)
                encoded = layers.Dropout(0.1)(encoded)
                encoded = layers.Dense(64, activation='relu')(encoded)
                encoded = layers.Dense(embedding_dim, activation='relu', name='embedding')(encoded)
                
                # Decoder
                decoded = layers.Dense(64, activation='relu')(encoded)
                decoded = layers.Dropout(0.1)(decoded)
                decoded = layers.Dense(256, activation='relu')(decoded)
                decoded = layers.Dense(input_dim, activation='linear')(decoded)
                
                # Full autoencoder
                autoencoder = models.Model(encoder_input, decoded)
                autoencoder.compile(
                    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                    loss='mse', 
                    metrics=['mae']
                )
                
                # Encoder only
                encoder = models.Model(encoder_input, encoded)
                
                print(f"   🏗️ CPU Autoencoder: {input_dim} → {embedding_dim} → {input_dim}")
                
                return autoencoder, encoder
                
        except Exception as e:
            print(f"⚠️ Autoencoder creation failed: {e}")
            print("   Falling back to PCA")
            return None
    
    def train_regime_compressor(self, windows):
        """Train autoencoder or PCA for regime compression"""
        
        print("🎓 Training regime compressor...")
        
        # Normalize windows
        self.scaler = StandardScaler()
        windows_scaled = self.scaler.fit_transform(windows)
        
        if TF_AVAILABLE and len(windows) > 20:
            try:
                # Try autoencoder with CPU-only mode for M1 safety
                input_dim = windows.shape[1]
                self.autoencoder, self.encoder = self.build_autoencoder(input_dim)
                
                if self.autoencoder is not None:
                    # Train with CPU-only mode and reduced parameters for stability
                    with tf.device('/CPU:0'):
                        history = self.autoencoder.fit(
                            windows_scaled, windows_scaled,
                            epochs=min(self.config['autoencoder_epochs'], 20),  # Limit epochs
                            batch_size=min(self.config['batch_size'], 16),      # Smaller batches
                            validation_split=self.config['validation_split'],
                            verbose=0,
                            shuffle=True
                        )
                    
                    # Get embeddings with CPU-only mode
                    with tf.device('/CPU:0'):
                        embeddings = self.encoder.predict(windows_scaled, verbose=0)
                    
                    print(f"   ✅ Autoencoder trained (final loss: {history.history['loss'][-1]:.4f})")
                    
                else:
                    raise Exception("Autoencoder creation failed")
                    
            except Exception as e:
                print(f"⚠️ Autoencoder training failed: {e}")
                print("   Falling back to PCA")
                # Fall through to PCA
                self.autoencoder = None
                self.encoder = None
        
        if not TF_AVAILABLE or self.autoencoder is None:
            # Use PCA fallback
            print("   Using PCA for regime compression")
            
            self.pca = PCA(n_components=self.config['embedding_dim'])
            embeddings = self.pca.fit_transform(windows_scaled)
            
            explained_var = self.pca.explained_variance_ratio_.sum()
            print(f"   ✅ PCA trained (explained variance: {explained_var:.3f})")
        
        print(f"   📊 Embeddings shape: {embeddings.shape}")
        return embeddings
    
    def cluster_regimes(self, embeddings):
        """Cluster regime embeddings to identify distinct regimes"""
        
        print("🎯 Clustering regime embeddings...")
        
        n_clusters = min(self.config['n_clusters'], len(embeddings))
        
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = self.kmeans.fit_predict(embeddings)
        
        # Calculate cluster statistics
        cluster_stats = {}
        for i in range(n_clusters):
            cluster_mask = cluster_labels == i
            cluster_embeddings = embeddings[cluster_mask]
            
            cluster_stats[i] = {
                'name': self.regime_names.get(i, f'Regime_{i}'),
                'size': int(cluster_mask.sum()),
                'percentage': float(cluster_mask.mean() * 100),
                'centroid': cluster_embeddings.mean(axis=0).tolist(),
                'std': cluster_embeddings.std(axis=0).tolist()
            }
        
        print(f"   📊 Identified {n_clusters} regime clusters:")
        for i, stats in cluster_stats.items():
            print(f"      {stats['name']}: {stats['size']} periods ({stats['percentage']:.1f}%)")
        
        return cluster_labels, cluster_stats
    
    def build_regime_fingerprints(self):
        """Build complete regime fingerprint system"""
        
        print("🧠 BUILDING REGIME MEMORY SYSTEM")
        print("=" * 60)
        
        # Step 1: Load market tensor
        tensor = self.load_market_tensor()
        
        if tensor.empty:
            print("❌ Cannot build regime memory without market tensor")
            return False
        
        # Step 2: Create regime windows
        windows, window_dates = self.create_regime_windows(tensor)
        
        if len(windows) == 0:
            print("❌ Could not create regime windows")
            return False
        
        # Step 3: Train regime compressor
        embeddings = self.train_regime_compressor(windows)
        
        # Step 4: Cluster regimes
        cluster_labels, cluster_stats = self.cluster_regimes(embeddings)
        
        # Step 5: Create regime fingerprints DataFrame
        regime_fingerprints = pd.DataFrame(
            embeddings,
            index=window_dates,
            columns=[f'regime_factor_{i}' for i in range(embeddings.shape[1])]
        )
        
        # Add cluster labels
        regime_fingerprints['regime_cluster'] = cluster_labels
        regime_fingerprints['regime_name'] = [
            self.regime_names.get(label, f'Regime_{label}') 
            for label in cluster_labels
        ]
        
        # Step 6: Save results
        self.save_regime_memory(regime_fingerprints, cluster_stats, tensor.columns.tolist())
        
        print("\n✅ Regime memory system built successfully!")
        print(f"   Regime periods: {len(regime_fingerprints)}")
        print(f"   Embedding dimension: {embeddings.shape[1]}")
        print(f"   Regime clusters: {len(cluster_stats)}")
        
        return True
    
    def save_regime_memory(self, regime_fingerprints, cluster_stats, tensor_columns):
        """Save regime memory components"""
        
        # Create output directories
        os.makedirs(os.path.dirname(self.paths['regime_fingerprints']), exist_ok=True)
        os.makedirs(os.path.dirname(self.paths['regime_model']), exist_ok=True)
        
        # Save regime fingerprints
        regime_fingerprints.to_parquet(self.paths['regime_fingerprints'])
        print(f"💾 Saved regime fingerprints: {self.paths['regime_fingerprints']}")
        
        # Save cluster information
        cluster_info = {
            'created_at': datetime.now().isoformat(),
            'n_clusters': len(cluster_stats),
            'cluster_stats': cluster_stats,
            'regime_names': self.regime_names
        }
        
        with open(self.paths['regime_clusters'], 'w') as f:
            json.dump(cluster_info, f, indent=2)
        print(f"💾 Saved regime clusters: {self.paths['regime_clusters']}")
        
        # Save models
        if TF_AVAILABLE and self.autoencoder is not None:
            self.autoencoder.save(self.paths['regime_model'])
            print(f"💾 Saved autoencoder model: {self.paths['regime_model']}")
        
        # Save scaler
        import pickle
        with open(self.paths['regime_scaler'], 'wb') as f:
            pickle.dump(self.scaler, f)
        print(f"💾 Saved scaler: {self.paths['regime_scaler']}")

        # Save PCA model for non-TF inference path.
        if self.pca is not None:
            with open(self.paths['regime_pca'], 'wb') as f:
                pickle.dump(self.pca, f)
            print(f"💾 Saved PCA model: {self.paths['regime_pca']}")
        
        # Save metadata
        metadata = {
            'created_at': datetime.now().isoformat(),
            'version': self.version,
            'config': self.config,
            'tensor_columns': tensor_columns,
            'n_regimes': len(regime_fingerprints),
            'embedding_dim': regime_fingerprints.shape[1] - 2,  # Exclude cluster columns
            'date_range': {
                'start': regime_fingerprints.index[0].isoformat(),
                'end': regime_fingerprints.index[-1].isoformat()
            },
            'tensorflow_available': TF_AVAILABLE
        }
        
        with open(self.paths['regime_metadata'], 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"📋 Saved regime metadata: {self.paths['regime_metadata']}")
    
    def load_regime_memory(self):
        """Load existing regime memory system"""
        
        try:
            if os.path.exists(self.paths['regime_fingerprints']):
                fingerprints = pd.read_parquet(self.paths['regime_fingerprints'])
                print(f"📊 Loaded regime fingerprints: {fingerprints.shape}")
                return fingerprints
        except Exception as e:
            print(f"⚠️ Could not load regime fingerprints: {e}")
        
        return pd.DataFrame()
    
    def get_current_regime(self, current_tensor_window):
        """Identify current regime from tensor window"""
        
        try:
            # Load regime system
            fingerprints = self.load_regime_memory()
            if fingerprints.empty:
                return None
            
            # Load scaler
            import pickle
            with open(self.paths['regime_scaler'], 'rb') as f:
                scaler = pickle.load(f)

            # Load PCA model if available (required for non-TF path).
            if self.pca is None and os.path.exists(self.paths['regime_pca']):
                with open(self.paths['regime_pca'], 'rb') as f:
                    self.pca = pickle.load(f)
            
            # Prepare current window
            current_vector = current_tensor_window.values.flatten().reshape(1, -1)
            current_scaled = scaler.transform(current_vector)
            
            # Get embedding
            if TF_AVAILABLE and os.path.exists(self.paths['regime_model']):
                # Use autoencoder
                encoder = tf.keras.models.load_model(self.paths['regime_model'])
                # Extract encoder part
                encoder_layers = [layer for layer in encoder.layers if 'embedding' in layer.name]
                if encoder_layers:
                    current_embedding = encoder_layers[0].output
                else:
                    # Fallback to PCA
                    current_embedding = self.pca.transform(current_scaled)
            else:
                # Use PCA
                if self.pca is None:
                    raise RuntimeError(
                        "PCA model missing for regime inference. "
                        "Rebuild regime memory to generate data/models/regime_pca.pkl."
                    )
                current_embedding = self.pca.transform(current_scaled)
            
            # Find most similar historical regime
            embedding_cols = [col for col in fingerprints.columns if col.startswith('regime_factor_')]
            historical_embeddings = fingerprints[embedding_cols].values
            
            similarities = cosine_similarity(current_embedding, historical_embeddings)[0]
            best_match_idx = np.argmax(similarities)
            best_similarity = similarities[best_match_idx]
            
            if best_similarity >= self.config['min_similarity']:
                matched_regime = fingerprints.iloc[best_match_idx]
                
                return {
                    'regime_cluster': int(matched_regime['regime_cluster']),
                    'regime_name': matched_regime['regime_name'],
                    'similarity': float(best_similarity),
                    'match_date': matched_regime.name.isoformat(),
                    'confidence': 'high' if best_similarity > 0.8 else 'medium'
                }
            else:
                return {
                    'regime_cluster': -1,
                    'regime_name': 'Unknown',
                    'similarity': float(best_similarity),
                    'match_date': None,
                    'confidence': 'low'
                }
        
        except Exception as e:
            print(f"⚠️ Error identifying current regime: {e}")
            return None
    
    def get_regime_transitions(self):
        """Analyze historical regime transitions"""
        
        try:
            fingerprints = self.load_regime_memory()
            if fingerprints.empty:
                return {}
            
            # Calculate transition matrix
            regimes = fingerprints['regime_cluster'].values
            n_clusters = len(set(regimes))
            
            transition_matrix = np.zeros((n_clusters, n_clusters))
            
            for i in range(len(regimes) - 1):
                current_regime = regimes[i]
                next_regime = regimes[i + 1]
                transition_matrix[current_regime, next_regime] += 1
            
            # Normalize to probabilities
            row_sums = transition_matrix.sum(axis=1, keepdims=True)
            transition_probs = np.divide(transition_matrix, row_sums, 
                                       out=np.zeros_like(transition_matrix), 
                                       where=row_sums!=0)
            
            # Convert to interpretable format
            transitions = {}
            for i in range(n_clusters):
                regime_name = self.regime_names.get(i, f'Regime_{i}')
                transitions[regime_name] = {}
                
                for j in range(n_clusters):
                    next_regime_name = self.regime_names.get(j, f'Regime_{j}')
                    transitions[regime_name][next_regime_name] = float(transition_probs[i, j])
            
            return transitions
            
        except Exception as e:
            print(f"⚠️ Error analyzing regime transitions: {e}")
            return {}
    
    def predict_regime_evolution(self, current_regime_cluster, n_steps=4):
        """Predict likely regime evolution"""
        
        try:
            transitions = self.get_regime_transitions()
            if not transitions:
                return []
            
            current_regime_name = self.regime_names.get(current_regime_cluster, f'Regime_{current_regime_cluster}')
            
            if current_regime_name not in transitions:
                return []
            
            evolution = []
            current = current_regime_name
            
            for step in range(n_steps):
                next_regimes = transitions[current]
                
                # Get most likely next regime
                if next_regimes:
                    most_likely = max(next_regimes.items(), key=lambda x: x[1])
                    
                    evolution.append({
                        'step': step + 1,
                        'regime': most_likely[0],
                        'probability': most_likely[1],
                        'from_regime': current
                    })
                    
                    current = most_likely[0]
                else:
                    break
            
            return evolution
            
        except Exception as e:
            print(f"⚠️ Error predicting regime evolution: {e}")
            return []
    
    def get_regime_characteristics(self, regime_cluster):
        """Get characteristics of a specific regime"""
        
        try:
            fingerprints = self.load_regime_memory()
            if fingerprints.empty:
                return {}
            
            regime_data = fingerprints[fingerprints['regime_cluster'] == regime_cluster]
            
            if regime_data.empty:
                return {}
            
            embedding_cols = [col for col in regime_data.columns if col.startswith('regime_factor_')]
            
            characteristics = {
                'regime_name': self.regime_names.get(regime_cluster, f'Regime_{regime_cluster}'),
                'occurrences': len(regime_data),
                'percentage': len(regime_data) / len(fingerprints) * 100,
                'avg_duration': self.calculate_avg_regime_duration(fingerprints, regime_cluster),
                'embedding_stats': {
                    'mean': regime_data[embedding_cols].mean().to_dict(),
                    'std': regime_data[embedding_cols].std().to_dict()
                },
                'recent_occurrences': regime_data.tail(5).index.strftime('%Y-%m-%d').tolist()
            }
            
            return characteristics
            
        except Exception as e:
            print(f"⚠️ Error getting regime characteristics: {e}")
            return {}
    
    def calculate_avg_regime_duration(self, fingerprints, regime_cluster):
        """Calculate average duration of a regime"""
        
        try:
            regimes = fingerprints['regime_cluster'].values
            durations = []
            current_duration = 0
            
            for regime in regimes:
                if regime == regime_cluster:
                    current_duration += 1
                else:
                    if current_duration > 0:
                        durations.append(current_duration)
                        current_duration = 0
            
            # Don't forget the last regime if it ends the series
            if current_duration > 0:
                durations.append(current_duration)
            
            return np.mean(durations) if durations else 0
            
        except:
            return 0

def main():
    """Build regime memory system"""
    
    engine = RegimeMemoryEngine()
    success = engine.build_regime_fingerprints()
    
    if success:
        print(f"\n🎯 Regime memory ready for market pulse!")
        print(f"   Next step: Build market pulse engine")
        return True
    else:
        print("❌ Failed to build regime memory")
        return False

if __name__ == "__main__":
    main()
