#!/usr/bin/env python3
"""
Language Guard - Prevents Imperative Language in Observer Outputs

This module implements language filtering to ensure Observer outputs
contain no imperative or command language.
"""

import re
from typing import List, Dict, Any

class LanguageGuard:
    """Prevents imperative language in Observer outputs"""
    
    def __init__(self):
        self.name = "Language Guard"
        self.version = "1.0.0"
        
        self.forbidden_words = [
            'should', 'must', 'will', 'do', 'enter', 'exit',
            'buy', 'sell', 'trade', 'increase', 'reduce'
        ]
        
    def check_language(self, text: str) -> Dict[str, Any]:
        """Check text for forbidden language"""
        
        violations = []
        text_lower = text.lower()
        
        for word in self.forbidden_words:
            if word in text_lower:
                violations.append(word)
        
        return {
            'violations': violations,
            'is_compliant': len(violations) == 0,
            'violation_count': len(violations)
        }