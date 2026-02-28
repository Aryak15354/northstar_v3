"""
M1 Mac Safe Regime Memory Engine
Handles TensorFlow Metal GPU issues on Apple Silicon
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import pickle
import json
from pathlib import Path

warnings.filterwarnings('ignore')

# Safe TensorFlow import for M1 Macs
TF_AVAILABLE = False
try:
    # Set environment variables for M1 Mac compatibility
    os.environ['TF_METAL_DEVICE_PLACEMENT'] = 'false'  # Disable Metal placement
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TF logs
    
    import tensorflow as tf
    
    # Configure TensorFlow for M1 Mac safety
    tf.config.set_visible_devices([], 'GPU')  # Force CPU-only mode
    tf.get_logger().setLevel('ERROR')
    
    # Test basic functionality without GPU
    test_tensor = tf.constant([1, 2, 3])
    
    TF_AVAILABLE = True
    print("✅ TensorFlow available (CPU-only mode for M1 Mac compatibility)")
    
except (ImportError, Exception) as e:
    TF_AVAILABLE = False
    print(f"ℹ️ TensorFlow not available ({type(e).__name__}), using PCA for regime compression")

class M1SafeRegimeMemoryEngine:
    """
    M1 Mac Safe Regime Memory Engine
    
    Uses CPU-only TensorFlow or falls back to PCA to avoid Metal GPU crashes
    """
    
    def __init__(self):
        self.name = "M1 Safe Regime Memory Engine"
        self.version = "1.0"
        
        # Ensure data directories exist
        os.makedirs('data/processed', exist_ok=True)
        os.makedirs('data/models', exist_ok=True)
        
        # Data paths
        self.paths = {
            'market_tensor': 'data/processed/market_tensor.parquet',
            'regime_fingerprints': 'data/processed/regime_fingerprints.parquet',
            'regime_clusters': 'data/processed/regime_clusters.json',
            'regime_model': 'data/models/regime_autoencoder.h5',
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
            'autoencoder_epochs': 20,   # Reduced epochs for stability
            'batch_size': 16,           # Smaller batch size for M1
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
        self.use_pca = not TF_AVAILABLE  # Default to PCA if TF not available
    
    def load_market_tensor(self):
        """Load market tensor data"""
        try:
            if os.path.exists(self.paths['market_tensor']):
                tensor_data = pd.read_parquet(self.paths['market_tensor'])
                from src.intelligence.market_brain.market_tensor import MarketTensorEngine
                tensor_data = MarketTensorEngine.canonicalize_tensor_frame(tensor_data)
                print(f"📊 Loaded market tensor: {tensor_data.shape}")
                return tensor_data
            else:
                print("⚠️ Market tensor not found, creating synthetic data")
                return self.create_synthetic_tensor()
        except Exception as e:
            print(f"⚠️ Error loading market tensor: {e}")
            return self.create_synthetic_tensor()
    
    def create_synthetic_tensor(self):
        """Create synthetic market tensor for testing"""
        dates = pd.date_range('2020-01-01', periods=200, freq='W')
        n_features = 30
        
        # Create synthetic market data with regime-like patterns
        data = []
        for i, date in enumerate(dates):
            # Create different regimes based on time
            if i < 50:  # Crisis regime
                regime_data = np.random.normal(-0.5, 2.0, n_features)
            elif i < 100:  # Recovery regime
                regime_data = np.random.normal(0.2, 1.5, n_features)
            elif i < 150:  # Expansion regime
                regime_data = np.random.normal(1.0, 1.0, n_features)
            else:  # Neutral regime
                regime_data = np.random.normal(0.0, 1.2, n_features)
            
            data.append(regime_data)
        
        tensor_data = pd.DataFrame(
            data,
            index=dates,
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        
        # Save synthetic data
        tensor_data.to_parquet(self.paths['market_tensor'])
        print(f"📊 Created synthetic market tensor: {tensor_data.shape}")
        return tensor_data
    
    def create_temporal_windows(self, tensor_data):
        """Create temporal windows from market tensor"""
        print("🪟 Creating temporal windows...")
        
        window_size = self.config['window_size']
        stride = self.config['overlap_stride']
        
        windows = []
        window_dates = []
        
        for i in range(0, len(tensor_data) - window_size + 1, stride):
            window = tensor_data.iloc[i:i + window_size]
            
            # Flatten window to 1D
            window_flat = window.values.flatten()
            windows.append(window_flat)
            window_dates.append(window.index[-1])  # Use end date of window
        
        windows_array = np.array(windows)
        print(f"   Created {len(windows)} windows of shape {windows_array.shape}")
        
        return windows_array, window_dates
    
    def build_safe_autoencoder(self, input_dim):
        """Build CPU-only autoencoder for M1 Mac safety"""
        if not TF_AVAILABLE:
            print("   Using PCA instead of autoencoder")
            return None, None
        
        try:
            print("🧠 Building CPU-only autoencoder for M1 Mac...")
            
            # Force CPU device context
            with tf.device('/CPU:0'):
                from tensorflow.keras import layers, models
                
                embedding_dim = self.config['embedding_dim']
                
                # Simpler architecture for stability
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
                
                # Models
                autoencoder = models.Model(encoder_input, decoded)
                autoencoder.compile(
                    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                    loss='mse',
                    metrics=['mae']
                )
                
                encoder = models.Model(encoder_input, encoded)
                
                print(f"   🏗️ CPU Autoencoder: {input_dim} → {embedding_dim} → {input_dim}")
                return autoencoder, encoder
                
        except Exception as e:
            print(f"⚠️ Autoencoder creation failed: {e}")
            print("   Falling back to PCA")
            self.use_pca = True
            return None, None
    
    def train_regime_compressor(self, windows):
        """Train autoencoder or PCA for regime compression"""
        print("🎓 Training regime compressor...")
        
        # Normalize windows
        self.scaler = StandardScaler()
        windows_scaled = self.scaler.fit_transform(windows)
        
        if not self.use_pca and TF_AVAILABLE and len(windows) > 20:
            try:
                # Try autoencoder with CPU-only mode
                input_dim = windows.shape[1]
                self.autoencoder, self.encoder = self.build_safe_autoencoder(input_dim)
                
                if self.autoencoder is not None:
                    # Train with reduced parameters for stability
                    with tf.device('/CPU:0'):
                        history = self.autoencoder.fit(
                            windows_scaled, windows_scaled,
                            epochs=self.config['autoencoder_epochs'],
                            batch_size=self.config['batch_size'],
                            validation_split=self.config['validation_split'],
                            verbose=0,
                            shuffle=True
                        )
                    
                    print(f"   ✅ Autoencoder trained (final loss: {history.history['loss'][-1]:.4f})")
                    
                    # Get embeddings
                    embeddings = self.encoder.predict(windows_scaled, verbose=0)
                    
                else:
                    raise Exception("Autoencoder creation failed")
                    
            except Exception as e:
                print(f"⚠️ Autoencoder training failed: {e}")
                print("   Falling back to PCA")
                self.use_pca = True
        
        if self.use_pca or not TF_AVAILABLE:
            # Use PCA fallback
            print("   Using PCA for regime compression")
            self.pca = PCA(n_components=self.config['embedding_dim'])
            embeddings = self.pca.fit_transform(windows_scaled)
            print(f"   ✅ PCA trained (explained variance: {self.pca.explained_variance_ratio_.sum():.3f})")
        
        return embeddings
    
    def cluster_regimes(self, embeddings):
        """Cluster regime embeddings"""
        print("🎯 Clustering regimes...")
        
        self.kmeans = KMeans(
            n_clusters=self.config['n_clusters'],
            random_state=42,
            n_init=10
        )
        
        regime_labels = self.kmeans.fit_predict(embeddings)
        
        print(f"   ✅ Identified {len(np.unique(regime_labels))} regime clusters")
        
        return regime_labels
    
    def build_regime_memory(self):
        """Build complete regime memory system"""
        print("🧠 Building M1 Safe Regime Memory...")
        print("=" * 50)
        
        try:
            # Load market tensor
            tensor_data = self.load_market_tensor()
            
            # Create temporal windows
            windows, window_dates = self.create_temporal_windows(tensor_data)
            
            # Train compressor
            embeddings = self.train_regime_compressor(windows)
            
            # Cluster regimes
            regime_labels = self.cluster_regimes(embeddings)
            
            # Create regime fingerprints
            regime_fingerprints = pd.DataFrame(
                embeddings,
                index=pd.to_datetime(window_dates),
                columns=[f'dim_{i}' for i in range(embeddings.shape[1])]
            )
            regime_fingerprints['regime'] = regime_labels
            regime_fingerprints['regime_name'] = [
                self.regime_names.get(label, f'Regime_{label}') 
                for label in regime_labels
            ]
            
            # Save results
            self.save_regime_memory(regime_fingerprints, embeddings, regime_labels)
            
            # Generate summary
            summary = self.generate_summary(regime_fingerprints)
            
            print("✅ M1 Safe Regime Memory built successfully!")
            return summary
            
        except Exception as e:
            print(f"❌ Regime memory building failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_regime_memory(self, regime_fingerprints, embeddings, regime_labels):
        """Save regime memory components"""
        print("💾 Saving regime memory...")
        
        # Save fingerprints
        regime_fingerprints.to_parquet(self.paths['regime_fingerprints'])
        
        # Save models
        if self.scaler:
            with open(self.paths['regime_scaler'], 'wb') as f:
                pickle.dump(self.scaler, f)
        
        # Save autoencoder if available
        if self.autoencoder and not self.use_pca:
            try:
                self.autoencoder.save(self.paths['regime_model'])
            except Exception as e:
                print(f"⚠️ Could not save autoencoder: {e}")
        
        # Save PCA if used
        if self.pca:
            pca_path = self.paths['regime_model'].replace('.h5', '_pca.pkl')
            with open(pca_path, 'wb') as f:
                pickle.dump(self.pca, f)
        
        # Save cluster info
        cluster_info = {
            'n_clusters': self.config['n_clusters'],
            'regime_names': self.regime_names,
            'cluster_centers': self.kmeans.cluster_centers_.tolist(),
            'use_pca': self.use_pca,
            'tensorflow_available': TF_AVAILABLE
        }
        
        with open(self.paths['regime_clusters'], 'w') as f:
            json.dump(cluster_info, f, indent=2)
        
        print("   ✅ All components saved")
    
    def generate_summary(self, regime_fingerprints):
        """Generate regime memory summary"""
        regime_counts = regime_fingerprints['regime'].value_counts().sort_index()
        
        summary = {
            'status': 'SUCCESS',
            'method': 'PCA' if self.use_pca else 'Autoencoder',
            'total_windows': len(regime_fingerprints),
            'embedding_dimension': self.config['embedding_dim'],
            'n_clusters': self.config['n_clusters'],
            'regime_distribution': regime_counts.to_dict(),
            'date_range': {
                'start': regime_fingerprints.index[0].isoformat(),
                'end': regime_fingerprints.index[-1].isoformat()
            },
            'tensorflow_available': TF_AVAILABLE,
            'cpu_only_mode': True,
            'm1_safe': True
        }
        
        return summary

def test_m1_safe_regime_memory():
    """Test the M1 safe regime memory engine"""
    print("🧪 Testing M1 Safe Regime Memory Engine...")
    
    engine = M1SafeRegimeMemoryEngine()
    result = engine.build_regime_memory()
    
    if result:
        print("\n📊 REGIME MEMORY SUMMARY:")
        print("=" * 40)
        for key, value in result.items():
            print(f"{key}: {value}")
        return True
    else:
        print("❌ Test failed")
        return False

if __name__ == "__main__":
    test_m1_safe_regime_memory()
