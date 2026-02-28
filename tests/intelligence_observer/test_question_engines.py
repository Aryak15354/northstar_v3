#!/usr/bin/env python3
"""
Question Engines Tests

Tests all Intelligence Observer question engines to ensure they:
1. Generate valid intelligence scores and narratives
2. Respect authority boundaries (no decision recommendations)
3. Handle various market conditions correctly
4. Provide meaningful confidence levels
5. Generate appropriate alerts when needed
"""

import pytest
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.intelligence_observer.observer_core.observer_context import ObserverSnapshot
from src.intelligence_observer.question_engines.regime_intelligence import RegimeIntelligenceEngine
from src.intelligence_observer.question_engines.stress_intelligence import StressIntelligenceEngine
from src.intelligence_observer.question_engines.engine_diagnostics import EngineDiagnosticsEngine
from src.intelligence_observer.question_engines.portfolio_structure_intelligence import PortfolioStructureIntelligenceEngine
from src.intelligence_observer.question_engines.meta_integrity_intelligence import MetaIntegrityIntelligenceEngine
from src.intelligence_observer.output_artifacts.intelligence_score import IntelligenceScore
from src.intelligence_observer.output_artifacts.intelligence_alert import IntelligenceAlert
from src.intelligence_observer.output_artifacts.intelligence_narrative import IntelligenceNarrative

class TestRegimeIntelligenceEngine:
    """Test Regime Intelligence Engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.engine = RegimeIntelligenceEngine()
        self.sample_snapshot = self._create_sample_snapshot()
    
    def _create_sample_snapshot(self):
        """Create sample snapshot for testing"""
        # Create sample market data
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        market_data = pd.DataFrame({
            'date': dates,
            'volatility': np.random.normal(0.15, 0.05, 252),
            'correlation': np.random.normal(0.45, 0.15, 252),
            'breadth': np.random.normal(55, 15, 252),
            'regime': np.random.choice(['supportive', 'neutral', 'hostile'], 252)
        })
        
        return ObserverSnapshot(
            snapshot_id="test_regime_001",
            timestamp=datetime.now(),
            data={'market_state': market_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
    
    def test_engine_initialization(self):
        """Test engine initializes correctly"""
        assert self.engine.name == "Regime Intelligence Engine"
        assert self.engine.version == "1.0.0"
        assert len(self.engine.authorized_questions) > 0
        
        # Check authorized questions
        expected_questions = [
            "regime_similarity_analysis",
            "regime_stability_assessment", 
            "regime_transition_probability"
        ]
        
        for question in expected_questions:
            assert question in self.engine.authorized_questions
    
    def test_regime_similarity_analysis(self):
        """Test regime similarity analysis"""
        score, narrative = self.engine.analyze_regime_similarity(self.sample_snapshot)
        
        # Validate score
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert score.directionality == "neutral"
        assert "regime" in score.score_name.lower()
        
        # Validate narrative
        assert isinstance(narrative, IntelligenceNarrative)
        assert len(narrative.title) > 0
        assert len(narrative.content) > 0
        assert narrative.narrative_type == "regime_analysis"
        
        # Check that output contains no decision language
        combined_text = f"{narrative.title} {narrative.content}".lower()
        forbidden_words = ['should', 'must', 'buy', 'sell', 'enter', 'exit']
        for word in forbidden_words:
            assert word not in combined_text, f"Forbidden word '{word}' found in output"
    
    def test_regime_stability_assessment(self):
        """Test regime stability assessment"""
        score = self.engine.analyze_regime_stability(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert score.directionality == "neutral"
        assert "stability" in score.score_name.lower()
        
        # Check interpretation is descriptive, not prescriptive
        assert "probability" in score.interpretation.lower() or "likelihood" in score.interpretation.lower()
    
    def test_regime_transition_probability(self):
        """Test regime transition probability analysis"""
        score = self.engine.analyze_regime_transition_probability(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert score.directionality == "neutral"
        assert "transition" in score.score_name.lower()
    
    def test_invalid_snapshot_handling(self):
        """Test handling of invalid snapshots"""
        # Test with None snapshot
        with pytest.raises(ValueError, match="Snapshot cannot be None"):
            self.engine.analyze_regime_similarity(None)
        
        # Test with snapshot missing required data
        empty_snapshot = ObserverSnapshot(
            snapshot_id="empty_001",
            timestamp=datetime.now(),
            data={},  # Missing market_state
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        with pytest.raises(ValueError, match="market_state"):
            self.engine.analyze_regime_similarity(empty_snapshot)
    
    def test_low_quality_data_handling(self):
        """Test handling of low quality data"""
        # Create snapshot with low quality data
        low_quality_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),  # Very short history
            'volatility': [np.nan] * 5 + [0.1] * 5,  # Missing values
            'correlation': [0.5] * 10
        })
        
        low_quality_snapshot = ObserverSnapshot(
            snapshot_id="low_quality_001",
            timestamp=datetime.now(),
            data={'market_state': low_quality_data},
            data_quality_score=0.3,  # Low quality
            completeness_score=0.5,
            staleness_hours=2.0
        )
        
        score, narrative = self.engine.analyze_regime_similarity(low_quality_snapshot)
        
        # Should still produce output but with lower confidence
        assert score.confidence < 0.7  # Lower confidence due to data quality
        assert "limited" in narrative.content.lower() or "insufficient" in narrative.content.lower()

class TestStressIntelligenceEngine:
    """Test Stress Intelligence Engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.engine = StressIntelligenceEngine()
        self.sample_snapshot = self._create_sample_snapshot()
    
    def _create_sample_snapshot(self):
        """Create sample snapshot with stress indicators"""
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        
        # Create stress indicators
        market_data = pd.DataFrame({
            'date': dates,
            'vix': np.random.normal(20, 8, 252),
            'credit_spreads': np.random.normal(150, 50, 252),
            'correlation': np.random.normal(0.45, 0.20, 252),
            'volatility': np.random.normal(0.15, 0.08, 252),
            'market_stress': np.random.normal(0.25, 0.15, 252)
        })
        
        return ObserverSnapshot(
            snapshot_id="test_stress_001",
            timestamp=datetime.now(),
            data={'market_state': market_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
    
    def test_stress_clustering_analysis(self):
        """Test stress signal clustering analysis"""
        score, alert = self.engine.analyze_stress_clustering(self.sample_snapshot)
        
        # Validate score
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert score.directionality == "neutral"
        assert "stress" in score.score_name.lower()
        
        # Alert may or may not be present
        if alert:
            assert isinstance(alert, IntelligenceAlert)
            assert alert.severity in ['low', 'medium', 'high']
            assert len(alert.message) > 0
            
            # Check that alert contains no action recommendations
            forbidden_phrases = ['should trade', 'must buy', 'increase position']
            for phrase in forbidden_phrases:
                assert phrase not in alert.message.lower()
    
    def test_false_calm_detection(self):
        """Test false calm detection analysis"""
        score, alert = self.engine.analyze_false_calm_detection(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "calm" in score.score_name.lower() or "compression" in score.score_name.lower()
        
        # Check interpretation is observational
        assert any(word in score.interpretation.lower() 
                  for word in ['observed', 'detected', 'indicates', 'suggests'])
    
    def test_crisis_engine_readiness(self):
        """Test crisis engine readiness analysis"""
        score = self.engine.analyze_crisis_engine_readiness(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "readiness" in score.score_name.lower() or "preparedness" in score.score_name.lower()
    
    def test_high_stress_scenario(self):
        """Test analysis during high stress conditions"""
        # Create high stress data
        high_stress_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=50),
            'vix': [35] * 50,  # High VIX
            'credit_spreads': [300] * 50,  # Wide spreads
            'correlation': [0.85] * 50,  # High correlation
            'volatility': [0.35] * 50,  # High volatility
            'market_stress': [0.75] * 50  # High stress
        })
        
        high_stress_snapshot = ObserverSnapshot(
            snapshot_id="high_stress_001",
            timestamp=datetime.now(),
            data={'market_state': high_stress_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        score, alert = self.engine.analyze_stress_clustering(high_stress_snapshot)
        
        # Should detect high stress
        assert score.value > 60  # High stress score
        
        # Should generate alert
        assert alert is not None
        assert alert.severity in ['medium', 'high']

class TestEngineDiagnosticsEngine:
    """Test Engine Diagnostics Engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.engine = EngineDiagnosticsEngine()
        self.sample_snapshot = self._create_sample_snapshot()
    
    def _create_sample_snapshot(self):
        """Create sample snapshot with engine performance data"""
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        
        # Create engine performance data
        engine_data = pd.DataFrame({
            'date': dates,
            'trend_engine_performance': np.random.normal(0.02, 0.15, 252),
            'crisis_engine_performance': np.random.normal(0.05, 0.25, 252),
            'trend_engine_active': np.random.choice([True, False], 252),
            'crisis_engine_active': np.random.choice([True, False], 252),
            'engine_correlation': np.random.normal(0.1, 0.3, 252)
        })
        
        return ObserverSnapshot(
            snapshot_id="test_diagnostics_001",
            timestamp=datetime.now(),
            data={'engine_performance': engine_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
    
    def test_trend_engine_performance_analysis(self):
        """Test trend engine performance analysis"""
        score = self.engine.analyze_trend_engine_performance(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "trend" in score.score_name.lower()
        assert "performance" in score.score_name.lower()
    
    def test_crisis_engine_convexity_integrity(self):
        """Test crisis engine convexity integrity analysis"""
        score = self.engine.analyze_crisis_engine_convexity_integrity(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "crisis" in score.score_name.lower()
        assert "convexity" in score.score_name.lower() or "integrity" in score.score_name.lower()
    
    def test_engine_interaction_review(self):
        """Test engine interaction review"""
        score = self.engine.analyze_engine_interaction_review(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "interaction" in score.score_name.lower() or "independence" in score.score_name.lower()

class TestPortfolioStructureIntelligenceEngine:
    """Test Portfolio Structure Intelligence Engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.engine = PortfolioStructureIntelligenceEngine()
        self.sample_snapshot = self._create_sample_snapshot()
    
    def _create_sample_snapshot(self):
        """Create sample snapshot with portfolio structure data"""
        # Create historical portfolio data (not current positions)
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        
        portfolio_data = pd.DataFrame({
            'date': dates,
            'sector_concentration': np.random.normal(0.25, 0.10, 252),
            'position_concentration': np.random.normal(0.15, 0.08, 252),
            'liquidity_score': np.random.normal(0.75, 0.15, 252),
            'correlation_risk': np.random.normal(0.45, 0.20, 252)
        })
        
        return ObserverSnapshot(
            snapshot_id="test_portfolio_001",
            timestamp=datetime.now(),
            data={'portfolio_structure': portfolio_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
    
    def test_concentration_risk_analysis(self):
        """Test concentration risk analysis"""
        score = self.engine.analyze_concentration_risk(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "concentration" in score.score_name.lower()
        
        # Should be observational, not prescriptive
        assert any(word in score.interpretation.lower() 
                  for word in ['observed', 'detected', 'historical', 'pattern'])
    
    def test_liquidity_fragility_assessment(self):
        """Test liquidity fragility assessment"""
        score = self.engine.analyze_liquidity_fragility(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "liquidity" in score.score_name.lower()

class TestMetaIntegrityIntelligenceEngine:
    """Test Meta-Integrity Intelligence Engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.engine = MetaIntegrityIntelligenceEngine()
        self.sample_snapshot = self._create_sample_snapshot()
    
    def _create_sample_snapshot(self):
        """Create sample snapshot with system integrity data"""
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        
        integrity_data = pd.DataFrame({
            'date': dates,
            'system_performance': np.random.normal(0.85, 0.10, 252),
            'behavioral_consistency': np.random.normal(0.90, 0.08, 252),
            'parameter_drift': np.random.normal(0.02, 0.05, 252),
            'decision_quality': np.random.normal(0.75, 0.15, 252)
        })
        
        return ObserverSnapshot(
            snapshot_id="test_integrity_001",
            timestamp=datetime.now(),
            data={'system_integrity': integrity_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
    
    def test_behavioral_drift_detection(self):
        """Test behavioral drift detection"""
        score = self.engine.analyze_behavioral_drift_detection(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "drift" in score.score_name.lower() or "behavioral" in score.score_name.lower()
    
    def test_preparedness_assessment(self):
        """Test preparedness assessment"""
        score = self.engine.analyze_preparedness_assessment(self.sample_snapshot)
        
        assert isinstance(score, IntelligenceScore)
        assert 0 <= score.value <= 100
        assert 0 <= score.confidence <= 1
        assert "preparedness" in score.score_name.lower() or "readiness" in score.score_name.lower()

class TestQuestionEngineIntegration:
    """Test integration between question engines"""
    
    def setup_method(self):
        """Setup for integration tests"""
        self.regime_engine = RegimeIntelligenceEngine()
        self.stress_engine = StressIntelligenceEngine()
        self.diagnostics_engine = EngineDiagnosticsEngine()
        
        # Create comprehensive snapshot
        self.comprehensive_snapshot = self._create_comprehensive_snapshot()
    
    def _create_comprehensive_snapshot(self):
        """Create comprehensive snapshot with all data types"""
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        
        # Market state data
        market_data = pd.DataFrame({
            'date': dates,
            'volatility': np.random.normal(0.15, 0.05, 252),
            'correlation': np.random.normal(0.45, 0.15, 252),
            'vix': np.random.normal(20, 8, 252),
            'regime': np.random.choice(['supportive', 'neutral', 'hostile'], 252)
        })
        
        # Engine performance data
        engine_data = pd.DataFrame({
            'date': dates,
            'trend_engine_performance': np.random.normal(0.02, 0.15, 252),
            'crisis_engine_performance': np.random.normal(0.05, 0.25, 252)
        })
        
        return ObserverSnapshot(
            snapshot_id="comprehensive_001",
            timestamp=datetime.now(),
            data={
                'market_state': market_data,
                'engine_performance': engine_data
            },
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
    
    def test_multi_engine_analysis(self):
        """Test running multiple engines on same snapshot"""
        # Run regime analysis
        regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(
            self.comprehensive_snapshot
        )
        
        # Run stress analysis
        stress_score, stress_alert = self.stress_engine.analyze_stress_clustering(
            self.comprehensive_snapshot
        )
        
        # Run diagnostics analysis
        diagnostics_score = self.diagnostics_engine.analyze_trend_engine_performance(
            self.comprehensive_snapshot
        )
        
        # All should succeed
        assert isinstance(regime_score, IntelligenceScore)
        assert isinstance(stress_score, IntelligenceScore)
        assert isinstance(diagnostics_score, IntelligenceScore)
        
        # All should have different focus areas
        assert regime_score.score_name != stress_score.score_name
        assert stress_score.score_name != diagnostics_score.score_name
    
    def test_consistent_output_format(self):
        """Test that all engines produce consistent output formats"""
        engines_and_methods = [
            (self.regime_engine, 'analyze_regime_similarity'),
            (self.stress_engine, 'analyze_stress_clustering'),
            (self.diagnostics_engine, 'analyze_trend_engine_performance')
        ]
        
        for engine, method_name in engines_and_methods:
            method = getattr(engine, method_name)
            result = method(self.comprehensive_snapshot)
            
            # Handle different return types (some return tuples)
            if isinstance(result, tuple):
                score = result[0]
            else:
                score = result
            
            # All scores should have consistent structure
            assert hasattr(score, 'value')
            assert hasattr(score, 'confidence')
            assert hasattr(score, 'score_name')
            assert hasattr(score, 'interpretation')
            assert hasattr(score, 'directionality')
            
            # All should be neutral directionality (no bias)
            assert score.directionality == "neutral"
    
    def test_authority_compliance_across_engines(self):
        """Test that all engines comply with authority boundaries"""
        engines = [
            self.regime_engine,
            self.stress_engine,
            self.diagnostics_engine
        ]
        
        for engine in engines:
            # Check that engine has no forbidden methods
            forbidden_methods = [
                'set_exposure', 'modify_position', 'activate_engine',
                'override_risk', 'force_trade', 'place_order'
            ]
            
            for method in forbidden_methods:
                assert not hasattr(engine, method), f"Engine {engine.name} has forbidden method {method}"
            
            # Check that authorized questions are read-only
            for question in engine.authorized_questions:
                assert 'analyze' in question or 'assess' in question or 'detect' in question

if __name__ == "__main__":
    pytest.main([__file__, "-v"])