#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 14 - ENHANCED DATA INTEGRITY
Property-based tests for enhanced data integrity and immutability system

Tests the following properties:
- Property 41: Data Hash Consistency
- Property 42: Immutability Enforcement
- Property 43: Corruption Detection Accuracy

Usage:
    python -m pytest tests/validation/test_task14_data_integrity_properties.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
import warnings
warnings.filterwarnings('ignore')

import sys
import os
)))

from src.validation.enhanced_data_integrity_system import EnhancedDataIntegritySystem, IntegrityStatus

class TestTask14DataIntegrityProperties:
    """Property tests for Task 14 - Enhanced Data Integrity"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.integrity_system = EnhancedDataIntegritySystem()
        
    @given(
        data_size=st.integers(min_value=10, max_value=100),
        corruption_probability=st.floats(min_value=0.0, max_value=0.3)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_41_data_hash_consistency(self, data_size, corruption_probability):
        """
        Property 41: Data Hash Consistency
        
        Identical data should always produce identical hashes,
        and any modification should produce different hashes.
        """
        
        # Create test data
        original_data = pd.DataFrame({
            'symbol': ['AAPL'] * data_size,
            'date': pd.date_range('2023-01-01', periods=data_size),
            'close': np.random.uniform(100, 200, data_size),
            'volume': np.random.randint(1000000, 10000000, data_size)
        })
        
        # Calculate original hash
        original_hash = self.integrity_system.calculate_data_hash(original_data)
        
        # Create identical copy
        identical_data = original_data.copy()
        identical_hash = self.integrity_system.calculate_data_hash(identical_data)
        
        # Property: Identical data should have identical hashes
        assert original_hash == identical_hash, "Identical data should produce identical hashes"
        
        # Create modified data
        modified_data = original_data.copy()
        
        # Apply random corruptions
        num_corruptions = max(1, int(len(modified_data) * corruption_probability))
        corruption_indices = np.random.choice(len(modified_data), num_corruptions, replace=False)
        
        for idx in corruption_indices:
            # Randomly modify a value
            if np.random.random() < 0.5:
                modified_data.loc[idx, 'close'] *= 1.1  # 10% change
            else:
                modified_data.loc[idx, 'volume'] += 1000  # Small volume change
        
        modified_hash = self.integrity_system.calculate_data_hash(modified_data)
        
        # Property: Modified data should have different hash
        if num_corruptions > 0:
            assert original_hash != modified_hash, "Modified data should produce different hash"
        
        # Property: Hash should be deterministic
        rehash = self.integrity_system.calculate_data_hash(original_data)
        assert original_hash == rehash, "Hash calculation should be deterministic"
    
    @given(
        data_modifications=st.integers(min_value=1, max_value=5),
        modification_magnitude=st.floats(min_value=0.01, max_value=0.5)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_42_immutability_enforcement(self, data_modifications, modification_magnitude):
        """
        Property 42: Immutability Enforcement
        
        System should detect any unauthorized modifications to data
        and maintain tamper-evident audit trails.
        """
        
        # Create original data
        original_data = pd.DataFrame({
            'symbol': ['MSFT', 'GOOGL', 'AAPL'] * 20,
            'date': pd.date_range('2023-01-01', periods=60),
            'close': np.random.uniform(50, 300, 60),
            'volume': np.random.randint(500000, 20000000, 60)
        })
        
        # Register original data
        source_name = "test_immutability"
        original_hash = self.integrity_system.register_data_hash(source_name, original_data, "CREATE")
        
        # Verify original data validates correctly
        validation_result = self.integrity_system.validate_data_hash(source_name, original_data)
        assert validation_result, "Original data should validate against its hash"
        
        # Apply modifications
        modified_data = original_data.copy()
        
        for _ in range(data_modifications):
            # Random modification
            row_idx = np.random.randint(0, len(modified_data))
            col_name = np.random.choice(['close', 'volume'])
            
            if col_name == 'close':
                # Modify price by percentage
                modified_data.loc[row_idx, col_name] *= (1 + modification_magnitude)
            else:
                # Modify volume by absolute amount
                modified_data.loc[row_idx, col_name] += int(modification_magnitude * 1000000)
        
        # Property: Modified data should fail validation
        modified_validation = self.integrity_system.validate_data_hash(source_name, modified_data)
        assert not modified_validation, "Modified data should fail hash validation"
        
        # Property: Hash registry should maintain history
        assert source_name in self.integrity_system.hash_registry, "Source should be in hash registry"
        assert len(self.integrity_system.hash_registry[source_name]) >= 1, "Hash history should be maintained"
        
        # Property: Original hash should remain unchanged
        latest_entry = self.integrity_system.hash_registry[source_name][-1]
        assert latest_entry['hash'] == original_hash, "Original hash should remain unchanged"
    
    @given(
        corruption_type=st.sampled_from(['outliers', 'negatives', 'duplicates', 'missing']),
        corruption_intensity=st.floats(min_value=0.1, max_value=0.8)
    )
    @settings(max_examples=12, deadline=5000)
    def test_property_43_corruption_detection_accuracy(self, corruption_type, corruption_intensity):
        """
        Property 43: Corruption Detection Accuracy
        
        System should accurately detect different types of data corruption
        and classify them appropriately.
        """
        
        # Create clean baseline data
        clean_data = pd.DataFrame({
            'symbol': ['AAPL'] * 100,
            'date': pd.date_range('2023-01-01', periods=100),
            'open': np.random.uniform(150, 200, 100),
            'high': np.random.uniform(160, 210, 100),
            'low': np.random.uniform(140, 190, 100),
            'close': np.random.uniform(150, 200, 100),
            'volume': np.random.randint(1000000, 5000000, 100)
        })
        
        # Apply specific corruption type
        corrupted_data = clean_data.copy()
        corruption_count = max(1, int(len(corrupted_data) * corruption_intensity))
        
        if corruption_type == 'outliers':
            # Add extreme outliers
            outlier_indices = np.random.choice(len(corrupted_data), corruption_count, replace=False)
            for idx in outlier_indices:
                corrupted_data.loc[idx, 'close'] *= 10  # 10x normal value
                
        elif corruption_type == 'negatives':
            # Add negative prices (impossible)
            negative_indices = np.random.choice(len(corrupted_data), corruption_count, replace=False)
            for idx in negative_indices:
                corrupted_data.loc[idx, 'close'] = -abs(corrupted_data.loc[idx, 'close'])
                
        elif corruption_type == 'duplicates':
            # Add duplicate timestamps
            duplicate_indices = np.random.choice(len(corrupted_data)-1, corruption_count, replace=False)
            for idx in duplicate_indices:
                corrupted_data.loc[idx+1, 'date'] = corrupted_data.loc[idx, 'date']
                
        elif corruption_type == 'missing':
            # Add missing values
            missing_indices = np.random.choice(len(corrupted_data), corruption_count, replace=False)
            for idx in missing_indices:
                corrupted_data.loc[idx, 'close'] = np.nan
        
        # Run corruption detection
        corruption_indicators = self.integrity_system.detect_corruption_indicators(corrupted_data, "test_source")
        
        # Property: Should detect corruption when present
        if corruption_intensity > 0.2:  # Significant corruption
            assert len(corruption_indicators) > 0, f"Should detect {corruption_type} corruption"
            
            # Check for appropriate corruption type detection
            indicator_text = ' '.join(corruption_indicators).lower()
            
            if corruption_type == 'outliers':
                assert 'outlier' in indicator_text, "Should detect outliers"
            elif corruption_type == 'negatives':
                assert 'non-positive' in indicator_text or 'negative' in indicator_text, "Should detect negative values"
            elif corruption_type == 'duplicates':
                # This would be detected in timestamp validation
                pass
            elif corruption_type == 'missing':
                # Missing values affect completeness score
                completeness = self.integrity_system.calculate_completeness_score(corrupted_data)
                assert completeness < 1.0, "Should detect missing values through completeness"
        
        # Property: Clean data should have minimal corruption indicators
        clean_indicators = self.integrity_system.detect_corruption_indicators(clean_data, "clean_source")
        assert len(clean_indicators) <= 1, "Clean data should have minimal corruption indicators"
    
    def test_property_41_data_hash_consistency_deterministic(self):
        """Deterministic test for data hash consistency"""
        
        # Create test data
        data = pd.DataFrame({
            'symbol': ['AAPL', 'GOOGL', 'MSFT'],
            'date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
            'close': [150.0, 2800.0, 250.0],
            'volume': [1000000, 2000000, 1500000]
        })
        
        # Calculate hash multiple times
        hash1 = self.integrity_system.calculate_data_hash(data)
        hash2 = self.integrity_system.calculate_data_hash(data)
        hash3 = self.integrity_system.calculate_data_hash(data)
        
        # Should be identical
        assert hash1 == hash2 == hash3, "Hash should be deterministic"
        
        # Modify data slightly
        modified_data = data.copy()
        modified_data.loc[0, 'close'] = 150.01  # Tiny change
        
        modified_hash = self.integrity_system.calculate_data_hash(modified_data)
        assert hash1 != modified_hash, "Even tiny changes should produce different hash"
    
    def test_property_42_immutability_enforcement_deterministic(self):
        """Deterministic test for immutability enforcement"""
        
        # Create test data
        data = pd.DataFrame({
            'symbol': ['TEST'] * 10,
            'date': pd.date_range('2023-01-01', periods=10),
            'close': [100.0] * 10,
            'volume': [1000000] * 10
        })
        
        # Register data
        source_name = "immutability_test"
        self.integrity_system.register_data_hash(source_name, data, "CREATE")
        
        # Validate original data
        assert self.integrity_system.validate_data_hash(source_name, data), "Original data should validate"
        
        # Modify data
        tampered_data = data.copy()
        tampered_data.loc[0, 'close'] = 101.0
        
        # Should fail validation
        assert not self.integrity_system.validate_data_hash(source_name, tampered_data), "Tampered data should fail validation"
        
        # Original should still validate
        assert self.integrity_system.validate_data_hash(source_name, data), "Original data should still validate"
    
    def test_property_43_corruption_detection_accuracy_deterministic(self):
        """Deterministic test for corruption detection accuracy"""
        
        # Create clean data
        clean_data = pd.DataFrame({
            'symbol': ['AAPL'] * 50,
            'date': pd.date_range('2023-01-01', periods=50),
            'open': np.linspace(100, 200, 50),
            'high': np.linspace(110, 210, 50),
            'low': np.linspace(90, 190, 50),
            'close': np.linspace(100, 200, 50),
            'volume': [1000000] * 50
        })
        
        # Should have minimal corruption indicators
        clean_indicators = self.integrity_system.detect_corruption_indicators(clean_data, "clean")
        assert len(clean_indicators) == 0, "Clean data should have no corruption indicators"
        
        # Create obviously corrupted data
        corrupted_data = clean_data.copy()
        corrupted_data.loc[0, 'close'] = -100  # Negative price
        corrupted_data.loc[1:10, 'volume'] = 999999999  # Extreme outliers
        
        # Should detect corruption
        corruption_indicators = self.integrity_system.detect_corruption_indicators(corrupted_data, "corrupted")
        assert len(corruption_indicators) > 0, "Should detect obvious corruption"
        
        # Check specific corruption types
        indicator_text = ' '.join(corruption_indicators).lower()
        assert 'non-positive' in indicator_text, "Should detect negative prices"
        assert 'outlier' in indicator_text, "Should detect volume outliers"
    
    def test_schema_validation(self):
        """Test schema validation functionality"""
        
        # Valid data
        valid_data = pd.DataFrame({
            'symbol': ['AAPL', 'GOOGL'],
            'date': pd.to_datetime(['2023-01-01', '2023-01-02']),
            'open': [150.0, 2800.0],
            'high': [155.0, 2850.0],
            'low': [148.0, 2780.0],
            'close': [152.0, 2820.0],
            'volume': [1000000, 2000000]
        })
        
        is_valid, issues = self.integrity_system.validate_schema_compliance(valid_data, 'prices')
        assert is_valid, f"Valid data should pass schema validation: {issues}"
        
        # Invalid data - missing required column
        invalid_data = valid_data.drop('volume', axis=1)
        is_valid, issues = self.integrity_system.validate_schema_compliance(invalid_data, 'prices')
        assert not is_valid, "Data missing required column should fail validation"
        assert any('volume' in issue for issue in issues), "Should identify missing volume column"
    
    def test_timestamp_consistency(self):
        """Test timestamp consistency validation"""
        
        # Valid timestamps
        valid_data = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=10),
            'value': range(10)
        })
        
        is_consistent, issues = self.integrity_system.validate_timestamp_consistency(valid_data)
        assert is_consistent, f"Valid timestamps should pass: {issues}"
        
        # Duplicate timestamps
        duplicate_data = valid_data.copy()
        duplicate_data.loc[5, 'date'] = duplicate_data.loc[4, 'date']
        
        is_consistent, issues = self.integrity_system.validate_timestamp_consistency(duplicate_data)
        assert not is_consistent, "Duplicate timestamps should fail validation"
        assert any('duplicate' in issue.lower() for issue in issues), "Should identify duplicates"
    
    def test_completeness_score(self):
        """Test completeness score calculation"""
        
        # Complete data
        complete_data = pd.DataFrame({
            'a': [1, 2, 3, 4, 5],
            'b': [10, 20, 30, 40, 50]
        })
        
        completeness = self.integrity_system.calculate_completeness_score(complete_data)
        assert completeness == 1.0, "Complete data should have 100% completeness"
        
        # Data with missing values
        incomplete_data = complete_data.copy()
        incomplete_data.loc[0, 'a'] = np.nan
        incomplete_data.loc[1, 'b'] = np.nan
        
        completeness = self.integrity_system.calculate_completeness_score(incomplete_data)
        expected_completeness = 1.0 - (2 / 10)  # 2 missing out of 10 total cells
        assert abs(completeness - expected_completeness) < 0.01, f"Expected {expected_completeness}, got {completeness}"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])