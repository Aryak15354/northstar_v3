#!/usr/bin/env python3
"""
Weekly Intelligence Report - Human-Readable Intelligence Summary

This module generates the weekly intelligence report that serves as the primary
interface between the Intelligence Observer and human operators.

REPORT PRINCIPLES:
1. Read-only, non-actionable intelligence
2. Historical context and comparative analysis
3. Explicit disclaimers about non-binding nature
4. Structured format for consistent consumption
5. Reflection prompts for human bias checking
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

@dataclass
class WeeklyIntelligenceReport:
    """
    Weekly Intelligence Report Generator
    
    This class generates the weekly intelligence report that provides
    structured, non-actionable intelligence for human consumption.
    """
    
    def __init__(self):
        self.name = "Weekly Intelligence Report Generator"
        self.version = "1.0.0"
        
        # Report configuration
        self.report_config = {
            'max_summary_items': 5,
            'max_scores_displayed': 10,
            'max_alerts_displayed': 5,
            'include_reflection_prompts': True,
            'include_disclaimers': True
        }
        
        print(f"📊 {self.name} v{self.version}")
    
    def generate_report(self, scores: List[Dict[str, Any]], 
                       alerts: List[Dict[str, Any]], 
                       narratives: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate weekly intelligence report
        
        Args:
            scores: List of intelligence scores from the week
            alerts: List of intelligence alerts from the week
            narratives: List of intelligence narratives from the week
            
        Returns:
            Dict containing complete weekly report
        """
        
        report_id = f"WIR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        generation_time = datetime.now()
        
        # Generate report sections
        executive_summary = self._generate_executive_summary(scores, alerts, narratives)
        score_analysis = self._analyze_scores(scores)
        alert_summary = self._summarize_alerts(alerts)
        narrative_insights = self._extract_narrative_insights(narratives)
        reflection_prompts = self._generate_reflection_prompts()
        
        # Compile full report
        report = {
            'report_metadata': {
                'report_id': report_id,
                'report_type': 'weekly_intelligence',
                'generation_time': generation_time.isoformat(),
                'period_start': (generation_time - timedelta(days=7)).isoformat(),
                'period_end': generation_time.isoformat(),
                'observer_version': self.version,
                'guardrail_status': 'active'
            },
            'executive_summary': executive_summary,
            'intelligence_scores': score_analysis,
            'intelligence_alerts': alert_summary,
            'narrative_insights': narrative_insights,
            'reflection_prompts': reflection_prompts,
            'mandatory_disclaimers': self._get_mandatory_disclaimers(),
            'consumption_guidelines': self._get_consumption_guidelines()
        }
        
        return report
    
    def generate_markdown_report(self, scores: List[Dict[str, Any]], 
                                alerts: List[Dict[str, Any]], 
                                narratives: List[Dict[str, Any]]) -> str:
        """Generate markdown version of weekly report"""
        
        report_data = self.generate_report(scores, alerts, narratives)
        
        md = f"# Weekly Intelligence Report\n\n"
        md += f"**Report ID:** {report_data['report_metadata']['report_id']}\n"
        md += f"**Generated:** {report_data['report_metadata']['generation_time']}\n"
        md += f"**Period:** {report_data['report_metadata']['period_start']} to {report_data['report_metadata']['period_end']}\n"
        md += f"**Observer Version:** {report_data['report_metadata']['observer_version']}\n\n"
        
        # Executive Summary
        md += f"## Executive Summary\n\n"
        for item in report_data['executive_summary']:
            md += f"- {item}\n"
        md += "\n"
        
        # Intelligence Scores
        md += f"## Intelligence Scores\n\n"
        for score in report_data['intelligence_scores']['top_scores']:
            md += f"### {score['score_name']}\n"
            md += f"- **Value:** {score['value']:.0f}/100\n"
            md += f"- **Confidence:** {score['confidence']:.1%}\n"
            md += f"- **Interpretation:** {score['interpretation']}\n"
            md += f"- **Historical Context:** {score['historical_context']}\n\n"
        
        # Alerts
        if report_data['intelligence_alerts']['alert_count'] > 0:
            md += f"## Intelligence Alerts\n\n"
            for alert in report_data['intelligence_alerts']['alerts']:
                md += f"### {alert['alert_type'].title()} Alert\n"
                md += f"- **Severity:** {alert['severity']}\n"
                md += f"- **Message:** {alert['message']}\n"
                md += f"- **Recommended Response:** {alert['recommended_response']}\n"
                md += f"- **Explicitly NOT Recommended:** {', '.join(alert['explicitly_not_recommended'][:3])}\n\n"
        
        # Narrative Insights
        if report_data['narrative_insights']['narrative_count'] > 0:
            md += f"## Narrative Insights\n\n"
            for insight in report_data['narrative_insights']['key_insights']:
                md += f"- {insight}\n"
            md += "\n"
        
        # Reflection Prompts
        md += f"## Reflection Prompts\n\n"
        md += f"Please answer these questions after reading this report:\n\n"
        for prompt in report_data['reflection_prompts']:
            md += f"1. {prompt}\n"
        md += "\n"
        
        # Disclaimers
        md += f"## Mandatory Disclaimers\n\n"
        for disclaimer in report_data['mandatory_disclaimers']:
            md += f"**{disclaimer}**\n\n"
        
        return md
    
    def save_report(self, report: Dict[str, Any], output_dir: str = "data/intelligence/observer/reports/weekly/") -> str:
        """Save report to file"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        # JSON version
        json_filename = f"{report['report_metadata']['report_id']}.json"
        json_filepath = os.path.join(output_dir, json_filename)
        
        with open(json_filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Markdown version
        md_filename = f"{report['report_metadata']['report_id']}.md"
        md_filepath = os.path.join(output_dir, md_filename)
        
        # Regenerate markdown from report data
        scores = [report['intelligence_scores']['top_scores']] if report['intelligence_scores']['top_scores'] else []
        alerts = report['intelligence_alerts']['alerts']
        narratives = []  # Would extract from report if available
        
        markdown_content = self.generate_markdown_report(scores, alerts, narratives)
        
        with open(md_filepath, 'w') as f:
            f.write(markdown_content)
        
        print(f"📄 Weekly report saved: {json_filename}")
        return json_filepath
    
    def _generate_executive_summary(self, scores: List[Dict[str, Any]], 
                                   alerts: List[Dict[str, Any]], 
                                   narratives: List[Dict[str, Any]]) -> List[str]:
        """Generate executive summary items"""
        
        summary_items = []
        
        # Analyze scores for summary
        if scores:
            high_scores = [s for s in scores if s.get('value', 0) > 70]
            low_scores = [s for s in scores if s.get('value', 0) < 30]
            
            if high_scores:
                summary_items.append(f"{len(high_scores)} intelligence scores elevated above historical norms")
            
            if low_scores:
                summary_items.append(f"{len(low_scores)} intelligence scores below typical ranges")
        
        # Analyze alerts for summary
        if alerts:
            high_severity_alerts = [a for a in alerts if a.get('severity') == 'high']
            
            if high_severity_alerts:
                summary_items.append(f"{len(high_severity_alerts)} high-severity alerts generated")
            else:
                summary_items.append(f"{len(alerts)} monitoring alerts generated, no high-severity issues")
        else:
            summary_items.append("No intelligence alerts generated during period")
        
        # Add regime and stress summary
        regime_scores = [s for s in scores if 'regime' in s.get('score_name', '').lower()]
        stress_scores = [s for s in scores if 'stress' in s.get('score_name', '').lower()]
        
        if regime_scores:
            avg_regime_score = sum(s.get('value', 0) for s in regime_scores) / len(regime_scores)
            if avg_regime_score > 60:
                summary_items.append("Regime analysis indicates elevated transition probability")
            else:
                summary_items.append("Regime analysis indicates stable market conditions")
        
        if stress_scores:
            avg_stress_score = sum(s.get('value', 0) for s in stress_scores) / len(stress_scores)
            if avg_stress_score > 60:
                summary_items.append("Stress indicators showing elevated clustering")
            else:
                summary_items.append("Stress indicators within normal ranges")
        
        # Ensure we have at least some summary items
        if not summary_items:
            summary_items = [
                "Intelligence analysis completed for weekly period",
                "No significant anomalies detected in market patterns",
                "System behavioral integrity maintained"
            ]
        
        return summary_items[:self.report_config['max_summary_items']]
    
    def _analyze_scores(self, scores: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze intelligence scores for report"""
        
        if not scores:
            return {
                'score_count': 0,
                'top_scores': [],
                'score_distribution': {},
                'average_confidence': 0.0
            }
        
        # Sort scores by value (descending)
        sorted_scores = sorted(scores, key=lambda x: x.get('value', 0), reverse=True)
        top_scores = sorted_scores[:self.report_config['max_scores_displayed']]
        
        # Calculate distribution
        score_ranges = {'high': 0, 'medium': 0, 'low': 0}
        total_confidence = 0
        
        for score in scores:
            value = score.get('value', 0)
            if value >= 70:
                score_ranges['high'] += 1
            elif value >= 40:
                score_ranges['medium'] += 1
            else:
                score_ranges['low'] += 1
            
            total_confidence += score.get('confidence', 0)
        
        # Add historical context to top scores
        for score in top_scores:
            score['historical_context'] = self._get_score_historical_context(score)
        
        return {
            'score_count': len(scores),
            'top_scores': top_scores,
            'score_distribution': score_ranges,
            'average_confidence': total_confidence / len(scores) if scores else 0.0
        }
    
    def _summarize_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize intelligence alerts for report"""
        
        if not alerts:
            return {
                'alert_count': 0,
                'alerts': [],
                'severity_distribution': {},
                'alert_types': {}
            }
        
        # Sort alerts by severity and timestamp
        severity_order = {'high': 3, 'medium': 2, 'low': 1}
        sorted_alerts = sorted(alerts, 
                             key=lambda x: (severity_order.get(x.get('severity', 'low'), 1), 
                                          x.get('timestamp', '')), 
                             reverse=True)
        
        top_alerts = sorted_alerts[:self.report_config['max_alerts_displayed']]
        
        # Calculate distributions
        severity_dist = {}
        alert_types = {}
        
        for alert in alerts:
            severity = alert.get('severity', 'unknown')
            alert_type = alert.get('alert_type', 'unknown')
            
            severity_dist[severity] = severity_dist.get(severity, 0) + 1
            alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
        
        return {
            'alert_count': len(alerts),
            'alerts': top_alerts,
            'severity_distribution': severity_dist,
            'alert_types': alert_types
        }
    
    def _extract_narrative_insights(self, narratives: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract insights from intelligence narratives"""
        
        if not narratives:
            return {
                'narrative_count': 0,
                'key_insights': [],
                'narrative_types': {}
            }
        
        key_insights = []
        narrative_types = {}
        
        for narrative in narratives:
            # Extract key similarities and differences
            similarities = narrative.get('key_similarities', [])
            differences = narrative.get('key_differences', [])
            
            if similarities:
                key_insights.extend(similarities[:2])  # Top 2 similarities
            
            if differences:
                key_insights.append(f"Key difference: {differences[0]}")  # Top difference
            
            # Count narrative types
            narrative_type = narrative.get('narrative_type', 'unknown')
            narrative_types[narrative_type] = narrative_types.get(narrative_type, 0) + 1
        
        return {
            'narrative_count': len(narratives),
            'key_insights': key_insights[:10],  # Limit insights
            'narrative_types': narrative_types
        }
    
    def _generate_reflection_prompts(self) -> List[str]:
        """Generate reflection prompts for human bias checking"""
        
        if not self.report_config['include_reflection_prompts']:
            return []
        
        return [
            "Did this report make me want to take any trading actions?",
            "Did reading this increase my confidence or humility about market conditions?",
            "Can I do nothing after reading this and still feel at peace with my strategy?",
            "Am I using this intelligence to confirm existing biases or challenge them?",
            "Would I make the same decisions if I hadn't read this report?"
        ]
    
    def _get_mandatory_disclaimers(self) -> List[str]:
        """Get mandatory disclaimers for report"""
        
        if not self.report_config['include_disclaimers']:
            return []
        
        return [
            "This report is informational only. No system behavior may be altered as a result of this report.",
            "All intelligence is descriptive and historical. No trading recommendations are provided.",
            "The Observer may increase understanding but may never increase courage. Courage is already encoded in your engines.",
            "Any urge to act based on this intelligence should be delayed 72 hours for emotional decay."
        ]
    
    def _get_consumption_guidelines(self) -> List[str]:
        """Get guidelines for consuming the report"""
        
        return [
            "Read this report only during designated weekly review periods",
            "Never read during live decision windows or market stress periods",
            "Focus on pattern recognition, not action implications",
            "Use intelligence to increase humility, not confidence",
            "Remember: The system trades. Intelligence explains. You observe."
        ]
    
    def _get_score_historical_context(self, score: Dict[str, Any]) -> str:
        """Get historical context description for a score"""
        
        value = score.get('value', 0)
        
        if value >= 80:
            return "Significantly elevated vs historical median"
        elif value >= 60:
            return "Moderately above historical norms"
        elif value >= 40:
            return "Within typical historical range"
        elif value >= 20:
            return "Below historical median"
        else:
            return "Significantly below historical norms"