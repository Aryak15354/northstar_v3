#!/usr/bin/env python3
"""
Output Sanitizer - Ensures Observer Outputs Contain No Decision Commands

This module sanitizes all Intelligence Observer outputs to ensure they contain
no imperative language, trading recommendations, or decision commands.

SANITIZATION PRINCIPLES:
1. Remove all imperative verbs (do, enter, exit, buy, sell)
2. Block modal certainty (will, must, should)
3. Rewrite or block forbidden content
4. Inject mandatory disclaimers
5. Ensure all language is descriptive only
"""

import re
import json
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class SanitizationLevel(Enum):
    """Levels of output sanitization"""
    STRICT = "strict"      # Maximum sanitization
    STANDARD = "standard"  # Standard sanitization
    PERMISSIVE = "permissive"  # Minimal sanitization

@dataclass
class SanitizationResult:
    """Result of output sanitization"""
    original_content: str
    sanitized_content: str
    violations_found: List[str]
    sanitization_applied: bool
    blocked_content: bool
    
class OutputSanitizer:
    """
    Output Sanitizer - Ensures Observer Outputs Are Authority-Safe
    
    This class sanitizes all Intelligence Observer outputs to ensure they
    contain no decision commands or imperative language.
    """
    
    def __init__(self, sanitization_level: SanitizationLevel = SanitizationLevel.STANDARD):
        self.name = "Intelligence Observer Output Sanitizer"
        self.version = "1.0.0"
        self.sanitization_level = sanitization_level
        
        # Forbidden words and phrases by category
        self.forbidden_patterns = {
            'imperative_verbs': [
                r'\b(do|enter|exit|buy|sell|trade|execute|place|cancel)\b',
                r'\b(increase|reduce|modify|change|adjust|override)\b',
                r'\b(activate|deactivate|switch|force|trigger)\b',
                r'\b(rebalance|hedge|cover|close|open)\b'
            ],
            'modal_certainty': [
                r'\b(will|must|should|shall|need to|have to)\b',
                r'\b(definitely|certainly|absolutely|guaranteed)\b',
                r'\b(always|never|impossible|inevitable)\b'
            ],
            'trading_recommendations': [
                r'\b(recommend|suggest|advise|propose)\b.*\b(position|trade|exposure)\b',
                r'\b(go long|go short|take profit|stop loss)\b',
                r'\b(bullish|bearish|overweight|underweight)\b.*\b(recommendation|advice)\b'
            ],
            'urgency_language': [
                r'\b(urgent|immediate|now|quickly|asap)\b',
                r'\b(emergency|critical|must act)\b',
                r'\b(time sensitive|act fast)\b'
            ]
        }
        
        # Replacement patterns for sanitization
        self.replacement_patterns = {
            'imperative_to_descriptive': {
                r'\bdo\b': 'historically done',
                r'\benter\b': 'historically entered',
                r'\bexit\b': 'historically exited',
                r'\bincrease\b': 'historically increased',
                r'\breduce\b': 'historically reduced',
                r'\bactivate\b': 'historically activated',
                r'\bswitch\b': 'historically switched'
            },
            'certainty_to_probability': {
                r'\bwill\b': 'may',
                r'\bmust\b': 'typically',
                r'\bshould\b': 'historically',
                r'\bdefinitely\b': 'likely',
                r'\bcertainly\b': 'probably',
                r'\balways\b': 'typically',
                r'\bnever\b': 'rarely'
            }
        }
        
        # Mandatory disclaimers
        self.mandatory_disclaimers = [
            "This analysis is descriptive only and does not imply system action.",
            "No trading recommendations are provided.",
            "Historical patterns do not guarantee future outcomes."
        ]
        
        # Sanitization statistics
        self.sanitization_stats = {
            'total_processed': 0,
            'violations_found': 0,
            'content_blocked': 0,
            'content_sanitized': 0
        }
        
        print(f"🧹 {self.name} v{self.version}")
        print(f"🔒 Sanitization Level: {sanitization_level.value}")
    
    def sanitize_text(self, text: str, context: str = "") -> SanitizationResult:
        """
        Sanitize text content for authority compliance
        
        Args:
            text: Text content to sanitize
            context: Context for sanitization (e.g., 'score_interpretation')
            
        Returns:
            SanitizationResult with sanitized content and violation details
        """
        
        self.sanitization_stats['total_processed'] += 1
        
        original_text = text
        violations_found = []
        sanitized_text = text
        blocked = False
        
        # Check for violations
        for category, patterns in self.forbidden_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    violations_found.extend([f"{category}: {match}" for match in matches])
        
        # Apply sanitization based on level
        if violations_found:
            self.sanitization_stats['violations_found'] += 1
            
            if self.sanitization_level == SanitizationLevel.STRICT:
                # Strict mode: Block content with violations
                if any('imperative_verbs' in v or 'trading_recommendations' in v for v in violations_found):
                    blocked = True
                    sanitized_text = "[CONTENT BLOCKED: Contains forbidden imperative language]"
                    self.sanitization_stats['content_blocked'] += 1
                else:
                    sanitized_text = self._apply_sanitization_replacements(sanitized_text)
                    self.sanitization_stats['content_sanitized'] += 1
            
            elif self.sanitization_level == SanitizationLevel.STANDARD:
                # Standard mode: Apply replacements
                sanitized_text = self._apply_sanitization_replacements(sanitized_text)
                self.sanitization_stats['content_sanitized'] += 1
            
            # Permissive mode: Log violations but allow content
        
        # Add disclaimers if content was modified
        if sanitized_text != original_text and not blocked:
            sanitized_text = self._add_disclaimers(sanitized_text, context)
        
        return SanitizationResult(
            original_content=original_text,
            sanitized_content=sanitized_text,
            violations_found=violations_found,
            sanitization_applied=sanitized_text != original_text,
            blocked_content=blocked
        )
    
    def sanitize_intelligence_score(self, score_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize intelligence score dictionary"""
        
        sanitized_score = score_dict.copy()
        
        # Sanitize interpretation
        if 'interpretation' in sanitized_score:
            result = self.sanitize_text(sanitized_score['interpretation'], 'score_interpretation')
            sanitized_score['interpretation'] = result.sanitized_content
            
            if result.violations_found:
                sanitized_score['sanitization_applied'] = True
                sanitized_score['original_interpretation'] = result.original_content
        
        # Sanitize calculation method
        if 'calculation_method' in sanitized_score:
            result = self.sanitize_text(sanitized_score['calculation_method'], 'calculation_method')
            sanitized_score['calculation_method'] = result.sanitized_content
        
        # Ensure forbidden actions are present
        if 'forbidden_actions' not in sanitized_score or not sanitized_score['forbidden_actions']:
            sanitized_score['forbidden_actions'] = [
                "change_exposure",
                "switch_engine",
                "modify_thresholds",
                "override_risk_limits"
            ]
        
        return sanitized_score
    
    def sanitize_intelligence_alert(self, alert_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize intelligence alert dictionary"""
        
        sanitized_alert = alert_dict.copy()
        
        # Sanitize message
        if 'message' in sanitized_alert:
            result = self.sanitize_text(sanitized_alert['message'], 'alert_message')
            sanitized_alert['message'] = result.sanitized_content
            
            if result.blocked_content:
                # If message is blocked, replace with safe alternative
                sanitized_alert['message'] = "Market conditions warrant increased monitoring attention."
        
        # Sanitize recommended response
        if 'recommended_response' in sanitized_alert:
            result = self.sanitize_text(sanitized_alert['recommended_response'], 'recommended_response')
            sanitized_alert['recommended_response'] = result.sanitized_content
            
            # Ensure response is non-binding
            if not sanitized_alert['recommended_response'].startswith('Consider'):
                sanitized_alert['recommended_response'] = f"Consider {sanitized_alert['recommended_response'].lower()}"
        
        # Ensure explicitly_not_recommended is present
        if 'explicitly_not_recommended' not in sanitized_alert or not sanitized_alert['explicitly_not_recommended']:
            sanitized_alert['explicitly_not_recommended'] = [
                "reduce_exposure",
                "activate_crisis_engine",
                "override_system",
                "force_rebalance"
            ]
        
        return sanitized_alert
    
    def sanitize_intelligence_narrative(self, narrative_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize intelligence narrative dictionary"""
        
        sanitized_narrative = narrative_dict.copy()
        
        # Sanitize summary
        if 'summary' in sanitized_narrative:
            result = self.sanitize_text(sanitized_narrative['summary'], 'narrative_summary')
            sanitized_narrative['summary'] = result.sanitized_content
        
        # Sanitize engine behavior note
        if 'engine_behavior_note' in sanitized_narrative:
            result = self.sanitize_text(sanitized_narrative['engine_behavior_note'], 'engine_behavior')
            sanitized_narrative['engine_behavior_note'] = result.sanitized_content
            
            # Ensure historical framing
            if sanitized_narrative['engine_behavior_note'] and not any(
                word in sanitized_narrative['engine_behavior_note'].lower() 
                for word in ['historically', 'previously', 'typically', 'in the past']
            ):
                sanitized_narrative['engine_behavior_note'] = f"Historically, {sanitized_narrative['engine_behavior_note'].lower()}"
        
        # Ensure disclaimer is present
        if 'explicit_disclaimer' not in sanitized_narrative or not sanitized_narrative['explicit_disclaimer']:
            sanitized_narrative['explicit_disclaimer'] = "This narrative is descriptive only and does not imply system action."
        
        return sanitized_narrative
    
    def _apply_sanitization_replacements(self, text: str) -> str:
        """Apply sanitization replacement patterns"""
        
        sanitized = text
        
        # Apply imperative to descriptive replacements
        for pattern, replacement in self.replacement_patterns['imperative_to_descriptive'].items():
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Apply certainty to probability replacements
        for pattern, replacement in self.replacement_patterns['certainty_to_probability'].items():
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def _add_disclaimers(self, text: str, context: str) -> str:
        """Add mandatory disclaimers to sanitized content"""
        
        # Choose appropriate disclaimer based on context
        if context in ['score_interpretation', 'alert_message']:
            disclaimer = self.mandatory_disclaimers[0]  # Descriptive only
        elif context in ['recommended_response']:
            disclaimer = self.mandatory_disclaimers[1]  # No recommendations
        else:
            disclaimer = self.mandatory_disclaimers[2]  # Historical patterns
        
        return f"{text} [{disclaimer}]"
    
    def validate_output_compliance(self, output: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Validate that output complies with authority boundaries"""
        
        compliance_result = {
            'compliant': True,
            'violations': [],
            'sanitization_required': False,
            'blocked_content': False
        }
        
        if isinstance(output, str):
            result = self.sanitize_text(output)
            if result.violations_found:
                compliance_result['compliant'] = False
                compliance_result['violations'] = result.violations_found
                compliance_result['sanitization_required'] = True
                compliance_result['blocked_content'] = result.blocked_content
        
        elif isinstance(output, dict):
            # Check dictionary for forbidden keys
            forbidden_keys = {
                'trade_signal', 'position_change', 'exposure_change',
                'engine_override', 'risk_override', 'execution_command'
            }
            
            for key in output.keys():
                if key in forbidden_keys:
                    compliance_result['compliant'] = False
                    compliance_result['violations'].append(f"Forbidden key: {key}")
            
            # Recursively check string values
            for key, value in output.items():
                if isinstance(value, str):
                    result = self.sanitize_text(value)
                    if result.violations_found:
                        compliance_result['compliant'] = False
                        compliance_result['violations'].extend([f"{key}: {v}" for v in result.violations_found])
        
        return compliance_result
    
    def get_sanitization_stats(self) -> Dict[str, Any]:
        """Get sanitization statistics"""
        
        return {
            'sanitization_level': self.sanitization_level.value,
            'statistics': self.sanitization_stats.copy(),
            'violation_rate': (
                self.sanitization_stats['violations_found'] / 
                max(1, self.sanitization_stats['total_processed'])
            ),
            'block_rate': (
                self.sanitization_stats['content_blocked'] / 
                max(1, self.sanitization_stats['total_processed'])
            )
        }
    
    def reset_stats(self):
        """Reset sanitization statistics"""
        
        self.sanitization_stats = {
            'total_processed': 0,
            'violations_found': 0,
            'content_blocked': 0,
            'content_sanitized': 0
        }

# Global sanitizer instance
_output_sanitizer = None

def get_output_sanitizer() -> OutputSanitizer:
    """Get global output sanitizer instance"""
    global _output_sanitizer
    
    if _output_sanitizer is None:
        _output_sanitizer = OutputSanitizer()
    
    return _output_sanitizer

def sanitize_observer_output(output: Union[Dict[str, Any], str]) -> Union[Dict[str, Any], str]:
    """Sanitize observer output using global sanitizer"""
    
    sanitizer = get_output_sanitizer()
    
    if isinstance(output, dict):
        # Determine output type and sanitize accordingly
        if 'score_name' in output:
            return sanitizer.sanitize_intelligence_score(output)
        elif 'alert_type' in output:
            return sanitizer.sanitize_intelligence_alert(output)
        elif 'narrative_type' in output:
            return sanitizer.sanitize_intelligence_narrative(output)
        else:
            # Generic dictionary sanitization
            sanitized = {}
            for key, value in output.items():
                if isinstance(value, str):
                    result = sanitizer.sanitize_text(value)
                    sanitized[key] = result.sanitized_content
                else:
                    sanitized[key] = value
            return sanitized
    
    elif isinstance(output, str):
        result = sanitizer.sanitize_text(output)
        return result.sanitized_content
    
    return output