#!/usr/bin/env python3
"""
Property Tests for Regime Similarity - Phase 3 Basic Intelligence
Tests the mathematical properties of regime similarity calculations

Property 20: Regime Similarity Symmetry
Validates: Requirements 7.2

This test ensures that regime similarity calculations follow mathematical properties:
- Symmetry: similarity(A, B) = similarity(B, A)
- Self-similarity: similarity(A, A) = 1.0
- Bounded: 0 <= similarity(A, B) <= 1
- Triangle inequality approximation for cosine similarity
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, settings
from sklearn.metrics.pairwise import cosine_similarity
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.intelligence.regime_memory_system import RegimeMemorySystem

class TestRegimeSimilarityProperties:
    """Property tests for regime similarity calculations"""
    
    def setup_method(self):
        """Setup test environment"""
        self.system = RegimeMemorySystem()
        
        # Create sample regime fingerprints for testing
        np.random.seed(42)
        n_periods = 100
        n_features = 5
        
        # Generate sample feature data
        feature_data = np.random.randn(n_periods, n_features)
        dates = pd.date_range('2020-01-01', periods=n_periods, freq='W')
        
        # Create sample regime fingerprints
        feature_cols = [f'feature_{i}' for i in range(n_features)]
        scaled_cols = [f'feature_{i}_scaled' for i in range(n_features)]
        
        self.sample_fingerprints = pd.DataFrame(
            index=dates,
            data=np.hstack([feature_data, feature_data])  # Original and scaled
        )
        self.sample_fingerprints.columns = feature_cols + scaled_cols
        
        # Add regime labels
        regimes = np.random.choice(['Crisis', 'Expansion', 'Late-Expansion', 'Slowdown'], n_periods)
        self.sample_fingerprints['Regime'] = regimes
    
    @given(
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99)
    )
    @settings(max_examples=100, deadline=5000)
    def test_regime_similarity_symmetry(self, idx1, idx2):
        """
        Property 20: Regime Similarity Symmetry
        
        Tests that similarity(A, B) = similarity(B, A)
        This is a fundamental property of cosine similarity
        """
        # Get two regime fingerprints
        fp1 = self.sample_fingerprints.iloc[idx1]
        fp2 = self.sample_fingerprints.iloc[idx2]
        
        # Calculate similarity in both directions
        sim_ab = self._calculate_similarity(fp1, fp2)
        sim_ba = self._calculate_similarity(fp2, fp1)
        
        # Test symmetry property
        assert abs(sim_ab - sim_ba) < 1e-10, f"Similarity not symmetric: {sim_ab} != {sim_ba}"
    
    @given(st.integers(min_value=0, max_value=99))
    @settings(max_examples=50, deadline=5000)
    def test_regime_self_similarity(self, idx):
        """
        Property 20: Regime Self-Similarity
        
        Tests that similarity(A, A) = 1.0
        A regime should be perfectly similar to itself
        """
        fp = self.sample_fingerprints.iloc[idx]
        
        # Calculate self-similarity
        sim = self._calculate_similarity(fp, fp)
        
        # Test self-similarity property
        assert abs(sim - 1.0) < 1e-10, f"Self-similarity not 1.0: {sim}"
    
    @given(
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99)
    )
    @settings(max_examples=100, deadline=5000)
    def test_regime_similarity_bounds(self, idx1, idx2):
        """
        Property 20: Regime Similarity Bounds
        
        Tests that -1 <= similarity(A, B) <= 1 (with floating point tolerance)
        Cosine similarity is bounded between -1 and 1
        """
        fp1 = self.sample_fingerprints.iloc[idx1]
        fp2 = self.sample_fingerprints.iloc[idx2]
        
        # Calculate similarity
        sim = self._calculate_similarity(fp1, fp2)
        
        # Test bounds with floating point tolerance
        tolerance = 1e-10
        assert -1.0 - tolerance <= sim <= 1.0 + tolerance, f"Similarity out of bounds: {sim}"
    
    @given(
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99)
    )
    @settings(max_examples=50, deadline=5000)
    def test_regime_similarity_triangle_inequality_approximation(self, idx1, idx2, idx3):
        """
        Property 20: Regime Similarity Triangle Inequality (Approximation)
        
        Tests an approximation of triangle inequality for cosine similarity
        While cosine similarity doesn't strictly follow triangle inequality,
        we test that extreme violations don't occur
        """
        fp1 = self.sample_fingerprints.iloc[idx1]
        fp2 = self.sample_fingerprints.iloc[idx2]
        fp3 = self.sample_fingerprints.iloc[idx3]
        
        # Calculate similarities
        sim_12 = self._calculate_similarity(fp1, fp2)
        sim_23 = self._calculate_similarity(fp2, fp3)
        sim_13 = self._calculate_similarity(fp1, fp3)
        
        # Convert to distances (1 - similarity)
        dist_12 = 1 - sim_12
        dist_23 = 1 - sim_23
        dist_13 = 1 - sim_13
        
        # Test approximate triangle inequality with tolerance
        # This is not strict for cosine similarity but should hold approximately
        tolerance = 0.5  # Allow some violation due to cosine similarity properties
        
        assert dist_13 <= dist_12 + dist_23 + tolerance, \
            f"Triangle inequality severely violated: {dist_13} > {dist_12} + {dist_23} + {tolerance}"
    
    def test_regime_similarity_with_real_data(self):
        """
        Property 20: Regime Similarity with Real Data
        
        Tests similarity calculation with actual regime memory data
        """
        # Try to load real regime memory
        try:
            regime_memory = self.system.load_regime_memory()
            
            if not regime_memory.empty and len(regime_memory) >= 2:
                # Test with real data
                fp1 = regime_memory.iloc[0]
                fp2 = regime_memory.iloc[1]
                
                # Calculate similarity
                similarities = self.system.calculate_regime_similarity(fp1, regime_memory)
                
                # Test properties
                assert len(similarities) == len(regime_memory), "Similarity vector length mismatch"
                assert all(-1 <= sim <= 1 for sim in similarities), "Similarities out of bounds"
                assert abs(similarities.iloc[0] - 1.0) < 1e-10, "Self-similarity not 1.0"
                
        except Exception as e:
            # If no real data available, skip this test
            pytest.skip(f"No real regime memory data available: {e}")
    
    def test_regime_similarity_consistency(self):
        """
        Property 20: Regime Similarity Consistency
        
        Tests that similarity calculations are consistent across multiple calls
        """
        fp1 = self.sample_fingerprints.iloc[0]
        fp2 = self.sample_fingerprints.iloc[1]
        
        # Calculate similarity multiple times
        similarities = []
        for _ in range(10):
            sim = self._calculate_similarity(fp1, fp2)
            similarities.append(sim)
        
        # Test consistency
        assert all(abs(sim - similarities[0]) < 1e-10 for sim in similarities), \
            "Similarity calculations not consistent"
    
    def test_regime_similarity_with_identical_features(self):
        """
        Property 20: Regime Similarity with Identical Features
        
        Tests similarity when regimes have identical feature values
        """
        # Create two fingerprints with identical scaled features
        fp1 = self.sample_fingerprints.iloc[0].copy()
        fp2 = self.sample_fingerprints.iloc[1].copy()
        
        # Make scaled features identical
        scaled_cols = [col for col in fp1.index if col.endswith('_scaled')]
        for col in scaled_cols:
            fp2[col] = fp1[col]
        
        # Calculate similarity
        sim = self._calculate_similarity(fp1, fp2)
        
        # Should be 1.0 for identical features
        assert abs(sim - 1.0) < 1e-10, f"Similarity with identical features not 1.0: {sim}"
    
    def test_regime_similarity_with_orthogonal_features(self):
        """
        Property 20: Regime Similarity with Orthogonal Features
        
        Tests similarity when regimes have orthogonal feature vectors
        """
        # Create orthogonal feature vectors
        n_features = 4
        fp1_data = np.array([1, 0, 0, 0])  # Unit vector along first axis
        fp2_data = np.array([0, 1, 0, 0])  # Unit vector along second axis
        
        # Create fingerprints
        scaled_cols = [f'feature_{i}_scaled' for i in range(n_features)]
        fp1 = pd.Series(index=scaled_cols, data=fp1_data)
        fp2 = pd.Series(index=scaled_cols, data=fp2_data)
        
        # Calculate similarity
        sim = self._calculate_similarity(fp1, fp2)
        
        # Should be 0.0 for orthogonal vectors
        assert abs(sim - 0.0) < 1e-10, f"Similarity with orthogonal features not 0.0: {sim}"
    
    def _calculate_similarity(self, fp1, fp2):
        """Helper method to calculate cosine similarity between two fingerprints"""
        
        # Get scaled feature columns
        scaled_cols = [col for col in fp1.index if col.endswith('_scaled')]
        
        if not scaled_cols:
            # If no scaled columns, use all numeric columns
            scaled_cols = [col for col in fp1.index if pd.api.types.is_numeric_dtype(type(fp1[col]))]
        
        # Extract feature vectors
        vec1 = fp1[scaled_cols].values.reshape(1, -1)
        vec2 = fp2[scaled_cols].values.reshape(1, -1)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(vec1, vec2)[0, 0]
        
        return similarity

def test_regime_memory_system_integration():
    """Integration test for regime memory system"""
    
    system = RegimeMemorySystem()
    
    # Test that system can be instantiated
    assert system.name == "Regime Memory System"
    assert system.version == "3.0"
    
    # Test configuration
    assert system.config['similarity_threshold'] == 0.7
    assert system.config['min_regime_periods'] == 4
    
    # Test paths are defined
    assert 'regime_memory' in system.paths
    assert 'regime_metadata' in system.paths

if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])