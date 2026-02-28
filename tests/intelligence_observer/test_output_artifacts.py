#!/usr/bin/env python3
"""
Output Artifacts Tests

Tests the Intelligence Observer output artifacts (scores, alerts, narratives)
to ensure they:
1. Have proper structure and validation
2. Contain no decision-influencing content
3. Are properly sanitized
4. Include required disclaimers
5. Maintain audit trail integrity
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.intelligence_observer.output_artifacts.intelligence_score import IntelligenceScore
from src.intelligence_observer.output_artifacts.intelligence_alert import IntelligenceAlert
from src.intelligence_observer.output_artifacts.intelligence_narrative import IntelligenceNarrative
from src.intelligence_observer.output_artifacts.output_sanitizer import OutputSanitizer

class TestIntelligenceScore:
    """Test Intelligence Score functionality"""
    
    def test_score_creation_valid(self):
        """Test creating valid intelligence score"""
        score = IntelligenceScore(
            score_name="Regime Similarity Index",
            value=67.5,
            confidence=0.82,
            interpretation="Current conditions resemble historically volatile periods",
            historical_percentile=75.0,
            context_data={'regime': 'neutral', 'volatility': 0.18}
        )
        
        assert score.score_name == "Regime Similarity Index"
        assert score.value == 67.5
        assert score.confidence == 0.82
        assert score.directionality == "neutral"  # Should default to neutral
        assert score.historical_percentile == 75.0
        assert len(score.forbidden_actions) > 0
        assert isinstance(score.timestamp, datetime)
    
    def test_score_validation_value_bounds(self):
        """Test score value validation"""
        # Test value too low
        with pytest.raises(ValueError, match="Score value must be between 0 and 100"):
            IntelligenceScore(
                score_name="Test Score",
                value=-5.0,  # Invalid
                confidence=0.8,
                interpretation="Test interpretation"
            )
        
        # Test value too high
        with pytest.raises(ValueError, match="Score value must be between 0 and 100"):
            IntelligenceScore(
                score_name="Test Score",
                value=150.0,  # Invalid
                confidence=0.8,
                interpretation="Test interpretation"
            )
    
    def test_score_validation_confidence_bounds(self):
        """Test confidence validation"""
        # Test confidence too low
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            IntelligenceScore(
                score_name="Test Score",
                value=50.0,
                confidence=-0.1,  # Invalid
                interpretation="Test interpretation"
            )
        
        # Test confidence too high
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            IntelligenceScore(
                score_name="Test Score",
                value=50.0,
                confidence=1.5,  # Invalid
                interpretation="Test interpretation"
            )
    
    def test_score_forbidden_directionality(self):
        """Test that non-neutral directionality is rejected"""
        with pytest.raises(ValueError, match="Observer scores must have neutral directionality"):
            IntelligenceScore(
                score_name="Test Score",
                value=50.0,
                confidence=0.8,
                interpretation="Test interpretation",
                directionality="bullish"  # Forbidden
            )
    
    def test_score_forbidden_interpretation(self):
        """Test that forbidden interpretation language is rejected"""
        forbidden_interpretations = [
            "System should buy more stocks",
            "Must increase position size",
            "Recommend selling immediately",
            "Enter long positions now"
        ]
        
        for interpretation in forbidden_interpretations:
            with pytest.raises(ValueError, match="contains forbidden language"):
                IntelligenceScore(
                    score_name="Test Score",
                    value=50.0,
                    confidence=0.8,
                    interpretation=interpretation
                )
    
    def test_score_to_dict(self):
        """Test score serialization to dictionary"""
        score = IntelligenceScore(
            score_name="Test Score",
            value=67.5,
            confidence=0.82,
            interpretation="Test interpretation",
            historical_percentile=75.0
        )
        
        score_dict = score.to_dict()
        
        required_fields = [
            'score_id', 'score_name', 'value', 'confidence', 'interpretation',
            'directionality', 'historical_percentile', 'forbidden_actions',
            'timestamp', 'disclaimer'
        ]
        
        for field in required_fields:
            assert field in score_dict
        
        assert score_dict['value'] == 67.5
        assert score_dict['confidence'] == 0.82
        assert score_dict['directionality'] == "neutral"
    
    def test_score_disclaimer_inclusion(self):
        """Test that disclaimer is always included"""
        score = IntelligenceScore(
            score_name="Test Score",
            value=50.0,
            confidence=0.8,
            interpretation="Test interpretation"
        )
        
        assert len(score.disclaimer) > 0
        assert "observation" in score.disclaimer.lower()
        assert "decision" in score.disclaimer.lower()

class TestIntelligenceAlert:
    """Test Intelligence Alert functionality"""
    
    def test_alert_creation_valid(self):
        """Test creating valid intelligence alert"""
        alert = IntelligenceAlert(
            alert_type="monitoring",
            severity="medium",
            message="Regime transition probability elevated above historical baseline",
            confidence=0.75,
            context_data={'transition_prob': 0.65}
        )
        
        assert alert.alert_type == "monitoring"
        assert alert.severity == "medium"
        assert alert.confidence == 0.75
        assert len(alert.non_recommended_actions) > 0
        assert isinstance(alert.timestamp, datetime)
    
    def test_alert_severity_validation(self):
        """Test alert severity validation"""
        valid_severities = ['low', 'medium', 'high']
        
        for severity in valid_severities:
            alert = IntelligenceAlert(
                alert_type="monitoring",
                severity=severity,
                message="Test message",
                confidence=0.8
            )
            assert alert.severity == severity
        
        # Test invalid severity
        with pytest.raises(ValueError, match="Severity must be one of"):
            IntelligenceAlert(
                alert_type="monitoring",
                severity="critical",  # Invalid
                message="Test message",
                confidence=0.8
            )
    
    def test_alert_forbidden_message_content(self):
        """Test that forbidden message content is rejected"""
        forbidden_messages = [
            "System should trade immediately",
            "Must buy this opportunity",
            "Increase position size now",
            "Activate crisis engine"
        ]
        
        for message in forbidden_messages:
            with pytest.raises(ValueError, match="contains forbidden language"):
                IntelligenceAlert(
                    alert_type="monitoring",
                    severity="medium",
                    message=message,
                    confidence=0.8
                )
    
    def test_alert_rate_limiting(self):
        """Test alert rate limiting functionality"""
        # Create multiple alerts of same type
        alert1 = IntelligenceAlert(
            alert_type="stress_monitoring",
            severity="medium",
            message="First alert",
            confidence=0.8
        )
        
        # Second alert of same type should be rate limited
        alert2 = IntelligenceAlert(
            alert_type="stress_monitoring",
            severity="medium", 
            message="Second alert",
            confidence=0.8
        )
        
        # Check that rate limiting is considered
        assert hasattr(alert1, 'cooldown_period')
        assert hasattr(alert2, 'cooldown_period')
    
    def test_alert_to_dict(self):
        """Test alert serialization to dictionary"""
        alert = IntelligenceAlert(
            alert_type="monitoring",
            severity="medium",
            message="Test alert message",
            confidence=0.75
        )
        
        alert_dict = alert.to_dict()
        
        required_fields = [
            'alert_id', 'alert_type', 'severity', 'message', 'confidence',
            'non_recommended_actions', 'timestamp', 'disclaimer'
        ]
        
        for field in required_fields:
            assert field in alert_dict
        
        assert alert_dict['severity'] == "medium"
        assert alert_dict['confidence'] == 0.75
    
    def test_alert_non_recommended_actions(self):
        """Test that non-recommended actions are properly populated"""
        alert = IntelligenceAlert(
            alert_type="monitoring",
            severity="high",
            message="High stress conditions detected",
            confidence=0.85
        )
        
        assert len(alert.non_recommended_actions) > 0
        
        # Should contain typical trading actions that are NOT recommended
        non_rec_text = ' '.join(alert.non_recommended_actions).lower()
        assert any(word in non_rec_text for word in ['trade', 'position', 'exposure'])

class TestIntelligenceNarrative:
    """Test Intelligence Narrative functionality"""
    
    def test_narrative_creation_valid(self):
        """Test creating valid intelligence narrative"""
        narrative = IntelligenceNarrative(
            title="Current Market Regime Analysis",
            content="Current market conditions exhibit characteristics similar to historical periods of elevated uncertainty. Volatility patterns suggest regime transition probability has increased.",
            narrative_type="regime_analysis",
            confidence=0.78,
            context_data={'regime': 'transitional', 'confidence': 0.78}
        )
        
        assert narrative.title == "Current Market Regime Analysis"
        assert len(narrative.content) > 0
        assert narrative.narrative_type == "regime_analysis"
        assert narrative.confidence == 0.78
        assert isinstance(narrative.timestamp, datetime)
    
    def test_narrative_forbidden_content(self):
        """Test that forbidden content is rejected"""
        forbidden_contents = [
            "The system should increase exposure immediately",
            "We must buy this opportunity",
            "Recommend switching to crisis engine",
            "Portfolio should be rebalanced now"
        ]
        
        for content in forbidden_contents:
            with pytest.raises(ValueError, match="contains forbidden language"):
                IntelligenceNarrative(
                    title="Test Narrative",
                    content=content,
                    narrative_type="test",
                    confidence=0.8
                )
    
    def test_narrative_descriptive_language_requirement(self):
        """Test that narratives use descriptive language"""
        valid_narrative = IntelligenceNarrative(
            title="Market Condition Assessment",
            content="Current conditions resemble historical patterns observed during market transitions. Volatility indicators suggest elevated uncertainty levels.",
            narrative_type="assessment",
            confidence=0.8
        )
        
        # Should contain descriptive words
        content_lower = valid_narrative.content.lower()
        descriptive_words = ['resemble', 'observed', 'suggest', 'indicate', 'appear']
        assert any(word in content_lower for word in descriptive_words)
    
    def test_narrative_differences_requirement(self):
        """Test that narratives include differences, not just similarities"""
        # This would be enforced by the sanitizer in practice
        narrative = IntelligenceNarrative(
            title="Regime Comparison",
            content="Current conditions resemble 2018 Q4 in volatility patterns but differ in credit market behavior and correlation structures.",
            narrative_type="comparison",
            confidence=0.8
        )
        
        content_lower = narrative.content.lower()
        # Should mention both similarities and differences
        assert 'resemble' in content_lower or 'similar' in content_lower
        assert 'differ' in content_lower or 'unlike' in content_lower or 'contrast' in content_lower
    
    def test_narrative_to_dict(self):
        """Test narrative serialization to dictionary"""
        narrative = IntelligenceNarrative(
            title="Test Narrative",
            content="Test content with descriptive language",
            narrative_type="test",
            confidence=0.8
        )
        
        narrative_dict = narrative.to_dict()
        
        required_fields = [
            'narrative_id', 'title', 'content', 'narrative_type', 'confidence',
            'timestamp', 'disclaimer'
        ]
        
        for field in required_fields:
            assert field in narrative_dict
        
        assert narrative_dict['title'] == "Test Narrative"
        assert narrative_dict['confidence'] == 0.8
    
    def test_narrative_disclaimer_inclusion(self):
        """Test that disclaimer is always included"""
        narrative = IntelligenceNarrative(
            title="Test Narrative",
            content="Test content",
            narrative_type="test",
            confidence=0.8
        )
        
        assert len(narrative.disclaimer) > 0
        assert "observation" in narrative.disclaimer.lower()
        assert "recommendation" in narrative.disclaimer.lower()

class TestOutputSanitizer:
    """Test Output Sanitizer functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.sanitizer = OutputSanitizer()
    
    def test_sanitizer_initialization(self):
        """Test sanitizer initializes correctly"""
        assert self.sanitizer.name == "Intelligence Observer Output Sanitizer"
        assert self.sanitizer.version == "1.0.0"
        assert len(self.sanitizer.forbidden_verbs) > 0
        assert len(self.sanitizer.forbidden_modal_verbs) > 0
        assert len(self.sanitizer.forbidden_phrases) > 0
    
    def test_imperative_verb_removal(self):
        """Test removal of imperative verbs"""
        test_cases = [
            ("System should buy more stocks", "System observes increased opportunity in stocks"),
            ("Must sell immediately", "Conditions suggest elevated risk"),
            ("Enter long positions", "Historical patterns indicate long bias"),
            ("Exit all positions", "Conditions resemble historical exit periods")
        ]
        
        for original, expected_pattern in test_cases:
            sanitized = self.sanitizer.sanitize_text(original)
            
            # Should not contain original imperative verbs
            forbidden_verbs = ['buy', 'sell', 'enter', 'exit', 'must', 'should']
            sanitized_lower = sanitized.lower()
            
            for verb in forbidden_verbs:
                if verb in original.lower():
                    assert verb not in sanitized_lower or sanitized != original
    
    def test_modal_certainty_removal(self):
        """Test removal of modal certainty language"""
        test_cases = [
            "Market will crash tomorrow",
            "Volatility must increase",
            "System should definitely trade",
            "Portfolio will outperform"
        ]
        
        for text in test_cases:
            sanitized = self.sanitizer.sanitize_text(text)
            
            # Should not contain modal certainty
            modal_verbs = ['will', 'must', 'should', 'definitely']
            sanitized_lower = sanitized.lower()
            
            for modal in modal_verbs:
                if modal in text.lower():
                    # Either removed or text changed significantly
                    assert modal not in sanitized_lower or len(sanitized) != len(text)
    
    def test_forbidden_phrase_replacement(self):
        """Test replacement of forbidden phrases"""
        forbidden_phrases = [
            "trade signal",
            "position change", 
            "engine override",
            "risk override",
            "execution command"
        ]
        
        for phrase in forbidden_phrases:
            test_text = f"Analysis indicates {phrase} is active"
            sanitized = self.sanitizer.sanitize_text(test_text)
            
            # Forbidden phrase should be replaced or removed
            assert phrase not in sanitized.lower()
    
    def test_disclaimer_injection(self):
        """Test that disclaimers are properly injected"""
        original_text = "Current market conditions suggest elevated volatility"
        
        sanitized = self.sanitizer.sanitize_text(original_text, inject_disclaimer=True)
        
        # Should contain disclaimer
        assert len(sanitized) > len(original_text)
        assert "observation" in sanitized.lower() or "analysis" in sanitized.lower()
    
    def test_compliance_validation(self):
        """Test compliance validation"""
        # Valid text
        valid_text = "Current conditions resemble historical patterns of elevated uncertainty"
        is_compliant, issues = self.sanitizer.validate_compliance(valid_text)
        assert is_compliant
        assert len(issues) == 0
        
        # Invalid text
        invalid_text = "System should buy stocks immediately"
        is_compliant, issues = self.sanitizer.validate_compliance(invalid_text)
        assert not is_compliant
        assert len(issues) > 0
    
    def test_sanitize_intelligence_score(self):
        """Test sanitizing intelligence score output"""
        score_data = {
            'score_name': 'Test Score',
            'value': 75.0,
            'interpretation': 'System should trade more aggressively',  # Forbidden
            'confidence': 0.8
        }
        
        sanitized_data = self.sanitizer.sanitize_intelligence_score(score_data)
        
        # Interpretation should be sanitized
        assert 'should trade' not in sanitized_data['interpretation'].lower()
        assert sanitized_data['value'] == 75.0  # Other fields unchanged
    
    def test_sanitize_intelligence_alert(self):
        """Test sanitizing intelligence alert output"""
        alert_data = {
            'alert_type': 'monitoring',
            'severity': 'high',
            'message': 'Must increase position size immediately',  # Forbidden
            'confidence': 0.85
        }
        
        sanitized_data = self.sanitizer.sanitize_intelligence_alert(alert_data)
        
        # Message should be sanitized
        assert 'must increase' not in sanitized_data['message'].lower()
        assert sanitized_data['severity'] == 'high'  # Other fields unchanged
    
    def test_sanitize_intelligence_narrative(self):
        """Test sanitizing intelligence narrative output"""
        narrative_data = {
            'title': 'Market Analysis',
            'content': 'Current conditions suggest we should enter long positions immediately',  # Forbidden
            'narrative_type': 'analysis',
            'confidence': 0.8
        }
        
        sanitized_data = self.sanitizer.sanitize_intelligence_narrative(narrative_data)
        
        # Content should be sanitized
        assert 'should enter' not in sanitized_data['content'].lower()
        assert sanitized_data['title'] == 'Market Analysis'  # Other fields unchanged
    
    def test_descriptive_language_conversion(self):
        """Test conversion to descriptive language"""
        imperative_texts = [
            "Buy technology stocks",
            "Sell energy positions", 
            "Increase exposure to growth",
            "Reduce risk immediately"
        ]
        
        for text in imperative_texts:
            sanitized = self.sanitizer.sanitize_text(text)
            
            # Should be converted to descriptive language
            descriptive_words = ['resemble', 'suggest', 'indicate', 'observe', 'pattern', 'condition']
            sanitized_lower = sanitized.lower()
            
            # Should contain at least one descriptive word
            assert any(word in sanitized_lower for word in descriptive_words)
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        # Empty text
        assert self.sanitizer.sanitize_text("") == ""
        
        # None input
        assert self.sanitizer.sanitize_text(None) == ""
        
        # Very long text
        long_text = "This is a very long text. " * 1000
        sanitized_long = self.sanitizer.sanitize_text(long_text)
        assert isinstance(sanitized_long, str)
        
        # Text with special characters
        special_text = "Market conditions suggest 50% probability of volatility increase!"
        sanitized_special = self.sanitizer.sanitize_text(special_text)
        assert isinstance(sanitized_special, str)

class TestOutputArtifactIntegration:
    """Test integration between output artifacts"""
    
    def test_consistent_disclaimer_format(self):
        """Test that all artifacts have consistent disclaimer format"""
        score = IntelligenceScore(
            score_name="Test Score",
            value=50.0,
            confidence=0.8,
            interpretation="Test interpretation"
        )
        
        alert = IntelligenceAlert(
            alert_type="monitoring",
            severity="medium",
            message="Test alert message",
            confidence=0.8
        )
        
        narrative = IntelligenceNarrative(
            title="Test Narrative",
            content="Test narrative content",
            narrative_type="test",
            confidence=0.8
        )
        
        # All should have disclaimers
        assert len(score.disclaimer) > 0
        assert len(alert.disclaimer) > 0
        assert len(narrative.disclaimer) > 0
        
        # Disclaimers should contain key phrases
        for artifact in [score, alert, narrative]:
            disclaimer_lower = artifact.disclaimer.lower()
            assert "observation" in disclaimer_lower or "analysis" in disclaimer_lower
    
    def test_consistent_timestamp_format(self):
        """Test that all artifacts have consistent timestamp format"""
        artifacts = [
            IntelligenceScore("Test", 50.0, 0.8, "Test"),
            IntelligenceAlert("monitoring", "medium", "Test", 0.8),
            IntelligenceNarrative("Test", "Test content", "test", 0.8)
        ]
        
        for artifact in artifacts:
            assert isinstance(artifact.timestamp, datetime)
            
            # Should be serializable to ISO format
            timestamp_str = artifact.timestamp.isoformat()
            assert isinstance(timestamp_str, str)
            assert len(timestamp_str) > 0
    
    def test_consistent_id_generation(self):
        """Test that all artifacts generate unique IDs"""
        artifacts = [
            IntelligenceScore("Test", 50.0, 0.8, "Test"),
            IntelligenceAlert("monitoring", "medium", "Test", 0.8),
            IntelligenceNarrative("Test", "Test content", "test", 0.8)
        ]
        
        ids = []
        for artifact in artifacts:
            if hasattr(artifact, 'score_id'):
                ids.append(artifact.score_id)
            elif hasattr(artifact, 'alert_id'):
                ids.append(artifact.alert_id)
            elif hasattr(artifact, 'narrative_id'):
                ids.append(artifact.narrative_id)
        
        # All IDs should be unique
        assert len(ids) == len(set(ids))
        
        # All IDs should be non-empty strings
        for id_val in ids:
            assert isinstance(id_val, str)
            assert len(id_val) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])