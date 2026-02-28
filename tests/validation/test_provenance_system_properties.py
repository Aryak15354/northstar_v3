#!/usr/bin/env python3
"""
Property-Based Tests for Provenance System

Tests the correctness properties of the data provenance and audit trail system
for institutional validation.

# Feature: institutional-validation-layers, Property 34: Data Provenance Manifest Completeness
# Feature: institutional-validation-layers, Property 35: Manifest Immutability
"""

import pytest
import pandas as pd
import numpy as np
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any

# Import the system under test
from src.validation.provenance_system import ProvenanceSystem, DataFile, RunManifest


class TestProvenanceSystemProperties:
    """Property-based tests for Provenance System"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_data_dir = os.path.join(self.temp_dir, "data")
        os.makedirs(self.test_data_dir, exist_ok=True)
        
        # Create test provenance system
        self.provenance = ProvenanceSystem(
            base_dir=os.path.join(self.temp_dir, "metadata")
        )
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_data_file(self, filename: str, content: Any) -> str:
        """Create a test data file"""
        file_path = os.path.join(self.test_data_dir, filename)
        
        if filename.endswith('.parquet'):
            # Create DataFrame and save as parquet
            if isinstance(content, dict):
                df = pd.DataFrame([content])
            else:
                df = pd.DataFrame(content)
            df.to_parquet(file_path, index=False)
        elif filename.endswith('.json'):
            # Save as JSON
            with open(file_path, 'w') as f:
                json.dump(content, f)
        elif filename.endswith('.csv'):
            # Create DataFrame and save as CSV
            if isinstance(content, dict):
                df = pd.DataFrame([content])
            else:
                df = pd.DataFrame(content)
            df.to_csv(file_path, index=False)
        
        return file_path
    
    # ========================================================================
    # PROPERTY 34: Data Provenance Manifest Completeness
    # ========================================================================
    
    @given(
        run_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        file_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_34_manifest_completeness(self, run_id: str, file_count: int):
        """
        Property 34: Data Provenance Manifest Completeness
        
        For any system run, the manifest must include hash, timestamp, 
        and schema version for all input files used.
        
        Validates: Requirements 16.2, 16.3, 16.4
        """
        
        # Create test data files
        test_files = []
        for i in range(file_count):
            filename = f"test_data_{i}.parquet"
            content = {
                'date': [datetime.now()],
                'value': [np.random.random()],
                'category': [f'cat_{i}']
            }
            file_path = self._create_test_data_file(filename, content)
            test_files.append(file_path)
        
        # Create manifest
        manifest = self.provenance.create_run_manifest(
            run_id=run_id,
            data_file_patterns=test_files
        )
        
        # PROPERTY: Manifest must be complete
        assert manifest is not None
        assert manifest.run_id == run_id
        assert manifest.timestamp is not None
        assert isinstance(manifest.data_files, list)
        assert len(manifest.data_files) == file_count
        
        # PROPERTY: Each data file must have required fields
        for data_file in manifest.data_files:
            assert data_file.path is not None and data_file.path != ""
            assert data_file.hash is not None and len(data_file.hash) == 64  # SHA256
            assert data_file.timestamp is not None
            assert data_file.schema_version is not None and data_file.schema_version != ""
            assert data_file.size_bytes >= 0
        
        # PROPERTY: All input files must be tracked
        tracked_paths = {df.path for df in manifest.data_files}
        expected_paths = set(test_files)
        assert tracked_paths == expected_paths
    
    @given(
        file_content_1=st.text(min_size=1, max_size=100),
        file_content_2=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_34_hash_uniqueness(self, file_content_1: str, file_content_2: str):
        """
        Property 34: Hash Uniqueness
        
        Different file contents must produce different hashes.
        """
        
        assume(file_content_1 != file_content_2)
        
        # Create two different files
        file1_path = self._create_test_data_file("file1.json", {"content": file_content_1})
        file2_path = self._create_test_data_file("file2.json", {"content": file_content_2})
        
        # Create data file records
        data_file_1 = self.provenance.create_data_file_record(file1_path)
        data_file_2 = self.provenance.create_data_file_record(file2_path)
        
        # PROPERTY: Different content must have different hashes
        assert data_file_1 is not None
        assert data_file_2 is not None
        assert data_file_1.hash != data_file_2.hash
    
    @given(
        file_content=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_34_hash_consistency(self, file_content: str):
        """
        Property 34: Hash Consistency
        
        Same file content must always produce the same hash.
        """
        
        # Create file
        file_path = self._create_test_data_file("test.json", {"content": file_content})
        
        # Create data file record twice
        data_file_1 = self.provenance.create_data_file_record(file_path)
        data_file_2 = self.provenance.create_data_file_record(file_path)
        
        # PROPERTY: Same content must have same hash
        assert data_file_1 is not None
        assert data_file_2 is not None
        assert data_file_1.hash == data_file_2.hash
    
    # ========================================================================
    # PROPERTY 35: Manifest Immutability
    # ========================================================================
    
    @given(
        run_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')))
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_35_manifest_immutability(self, run_id: str):
        """
        Property 35: Manifest Immutability
        
        For any manifest file created, it must be cryptographically signed 
        and immutable after creation.
        
        Validates: Requirements 16.8
        """
        
        # Create test data file
        file_path = self._create_test_data_file("test.parquet", {
            'date': [datetime.now()],
            'value': [1.0]
        })
        
        # Create manifest
        manifest = self.provenance.create_run_manifest(
            run_id=run_id,
            data_file_patterns=[file_path]
        )
        
        # Load manifest from file
        loaded_manifest = self.provenance.load_manifest(run_id)
        
        # PROPERTY: Loaded manifest must match original
        assert loaded_manifest is not None
        assert loaded_manifest.run_id == manifest.run_id
        assert loaded_manifest.timestamp == manifest.timestamp
        assert loaded_manifest.code_commit == manifest.code_commit
        assert len(loaded_manifest.data_files) == len(manifest.data_files)
        
        # PROPERTY: Data files must match exactly
        for orig_df, loaded_df in zip(manifest.data_files, loaded_manifest.data_files):
            assert orig_df.path == loaded_df.path
            assert orig_df.hash == loaded_df.hash
            assert orig_df.timestamp == loaded_df.timestamp
            assert orig_df.schema_version == loaded_df.schema_version
            assert orig_df.size_bytes == loaded_df.size_bytes
    
    @given(
        run_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        output_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_34_output_linking(self, run_id: str, output_count: int):
        """
        Property 34: Output Linking Completeness
        
        All output files must be properly linked to the manifest.
        
        Validates: Requirements 16.6
        """
        
        # Create test data file
        file_path = self._create_test_data_file("input.parquet", {
            'date': [datetime.now()],
            'value': [1.0]
        })
        
        # Create manifest
        manifest = self.provenance.create_run_manifest(
            run_id=run_id,
            data_file_patterns=[file_path]
        )
        
        # Create output files
        output_files = []
        for i in range(output_count):
            output_path = f"output_{i}.parquet"
            output_files.append(output_path)
        
        # Link outputs
        success = self.provenance.link_outputs(run_id, output_files)
        
        # PROPERTY: Linking must succeed
        assert success is True
        
        # PROPERTY: All outputs must be linked
        loaded_manifest = self.provenance.load_manifest(run_id)
        assert loaded_manifest is not None
        assert len(loaded_manifest.linked_outputs) == output_count
        
        # PROPERTY: All output files must be present
        linked_set = set(loaded_manifest.linked_outputs)
        expected_set = set(output_files)
        assert linked_set == expected_set
    
    # ========================================================================
    # REPRODUCIBILITY PROPERTIES
    # ========================================================================
    
    @given(
        run_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        file_content=st.text(min_size=1, max_size=100)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_reproducibility_verification(self, run_id: str, file_content: str):
        """
        Property: Reproducibility Verification
        
        If data hasn't changed, reproducibility verification must pass.
        If data has changed, it must be detected.
        
        Validates: Requirements 16.7
        """
        
        # Create test data file
        file_path = self._create_test_data_file("test.json", {"content": file_content})
        
        # Create original manifest
        original_manifest = self.provenance.create_run_manifest(
            run_id=run_id,
            data_file_patterns=[file_path]
        )
        
        # Verify reproducibility (should pass - no changes)
        verification = self.provenance.verify_reproducibility(run_id, [file_path])
        
        # PROPERTY: Unchanged data must be reproducible
        assert verification['status'] == 'success'
        assert verification['reproducible'] is True
        assert len(verification['files_changed']) == 0
        assert len(verification['files_missing']) == 0
        
        # Modify the file
        modified_content = file_content + "_modified"
        self._create_test_data_file("test.json", {"content": modified_content})
        
        # Verify reproducibility again (should fail - data changed)
        verification2 = self.provenance.verify_reproducibility(run_id, [file_path])
        
        # PROPERTY: Changed data must be detected
        assert verification2['reproducible'] is False
        assert len(verification2['files_changed']) > 0
    
    # ========================================================================
    # SCHEMA VALIDATION PROPERTIES
    # ========================================================================
    
    @given(
        columns=st.lists(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            min_size=1, max_size=10, unique=True
        ),
        rows=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_schema_detection(self, columns: List[str], rows: int):
        """
        Property: Schema Detection Accuracy
        
        Schema version detection must be consistent and meaningful.
        """
        
        # Create DataFrame with random data
        data = {}
        for col in columns:
            data[col] = np.random.random(rows)
        
        # Create parquet file
        file_path = self._create_test_data_file("schema_test.parquet", data)
        
        # Create data file record
        data_file = self.provenance.create_data_file_record(file_path)
        
        # PROPERTY: Schema version must be detected
        assert data_file is not None
        assert data_file.schema_version is not None
        assert data_file.schema_version != ""
        
        # PROPERTY: Schema version must be consistent
        data_file_2 = self.provenance.create_data_file_record(file_path)
        assert data_file_2.schema_version == data_file.schema_version
    
    # ========================================================================
    # ERROR HANDLING PROPERTIES
    # ========================================================================
    
    def test_property_nonexistent_file_handling(self):
        """
        Property: Nonexistent File Handling
        
        System must gracefully handle nonexistent files.
        """
        
        nonexistent_path = "/path/that/does/not/exist.parquet"
        
        # PROPERTY: Nonexistent file must return None
        data_file = self.provenance.create_data_file_record(nonexistent_path)
        assert data_file is None
    
    def test_property_invalid_manifest_id(self):
        """
        Property: Invalid Manifest ID Handling
        
        System must gracefully handle invalid manifest IDs.
        """
        
        invalid_id = "NONEXISTENT_MANIFEST_ID"
        
        # PROPERTY: Invalid manifest ID must return None
        manifest = self.provenance.load_manifest(invalid_id)
        assert manifest is None
        
        # PROPERTY: Linking to invalid manifest must fail
        success = self.provenance.link_outputs(invalid_id, ["output.parquet"])
        assert success is False
    
    # ========================================================================
    # INTEGRATION PROPERTIES
    # ========================================================================
    
    @given(
        manifest_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=10, deadline=10000)
    def test_property_manifest_summary_accuracy(self, manifest_count: int):
        """
        Property: Manifest Summary Accuracy
        
        Summary statistics must accurately reflect all manifests.
        """
        
        created_manifests = []
        
        # Create multiple manifests
        for i in range(manifest_count):
            run_id = f"TEST_{i:03d}"
            
            # Create test data file
            file_path = self._create_test_data_file(f"data_{i}.parquet", {
                'date': [datetime.now()],
                'value': [i]
            })
            
            # Create manifest
            manifest = self.provenance.create_run_manifest(
                run_id=run_id,
                data_file_patterns=[file_path]
            )
            created_manifests.append(manifest)
        
        # Get summary
        summary = self.provenance.get_manifest_summary()
        
        # PROPERTY: Summary must reflect all created manifests
        assert summary['total_manifests'] >= manifest_count
        assert summary['manifests_in_range'] >= manifest_count
        assert summary['total_data_files'] >= manifest_count
        
        # PROPERTY: All created manifests must be in summary
        summary_run_ids = {m['run_id'] for m in summary['manifests']}
        created_run_ids = {m.run_id for m in created_manifests}
        assert created_run_ids.issubset(summary_run_ids)


def test_data_file_validation():
    """Test DataFile validation"""
    
    # Valid data file
    valid_file = DataFile(
        path="test.parquet",
        hash="a" * 64,  # Valid SHA256 length
        timestamp=datetime.now(),
        schema_version="v1.0",
        size_bytes=1000
    )
    
    errors = valid_file.validate()
    assert len(errors) == 0
    
    # Invalid data file - bad hash
    invalid_file = DataFile(
        path="test.parquet",
        hash="invalid_hash",  # Invalid SHA256
        timestamp=datetime.now(),
        schema_version="v1.0",
        size_bytes=1000
    )
    
    errors = invalid_file.validate()
    assert len(errors) > 0
    assert any("Invalid SHA256 hash" in error for error in errors)


def test_run_manifest_validation():
    """Test RunManifest validation"""
    
    # Valid manifest
    valid_manifest = RunManifest(
        run_id="TEST_001",
        timestamp=datetime.now(),
        code_commit="abc123",
        data_files=[
            DataFile(
                path="test.parquet",
                hash="a" * 64,
                timestamp=datetime.now(),
                schema_version="v1.0",
                size_bytes=1000
            )
        ],
        linked_outputs=["output.parquet"],
        system_info={"python": "3.8"}
    )
    
    errors = valid_manifest.validate()
    assert len(errors) == 0
    
    # Invalid manifest - empty run_id
    invalid_manifest = RunManifest(
        run_id="",  # Empty run_id
        timestamp=datetime.now(),
        code_commit="abc123",
        data_files=[],  # Empty data files
        linked_outputs=[],
        system_info={}
    )
    
    errors = invalid_manifest.validate()
    assert len(errors) > 0
    assert any("Run ID cannot be empty" in error for error in errors)
    assert any("Data files list cannot be empty" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])