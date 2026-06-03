#!/usr/bin/env python3
"""
Artifact Hashing - Ensures Integrity of Intelligence Artifacts

This module provides hashing and integrity verification for all
Intelligence Observer artifacts.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any

class ArtifactHashing:
    """Provides hashing and integrity verification for intelligence artifacts"""
    
    def __init__(self):
        self.name = "Artifact Hashing"
        self.version = "1.0.0"
    
    def hash_artifact(self, artifact: Dict[str, Any]) -> str:
        """Generate hash for intelligence artifact"""
        
        # Create deterministic JSON representation
        artifact_json = json.dumps(artifact, sort_keys=True)
        
        # Generate SHA-256 hash
        return hashlib.sha256(artifact_json.encode()).hexdigest()
    
    def verify_artifact_integrity(self, artifact: Dict[str, Any], expected_hash: str) -> bool:
        """Verify artifact integrity against expected hash"""
        
        actual_hash = self.hash_artifact(artifact)
        return actual_hash == expected_hash