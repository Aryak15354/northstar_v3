"""
Accounting Distortion Detector
Identifies specific accounting manipulations and distortions
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class DistortionReport:
    """Container for distortion analysis"""
    distortions_found: List[str]
    severity_score: float  # 0-100, higher is worse
    adjusted_metrics: Dict[str, float]
    recommendations: List[str]


class AccountingDistortionDetector:
    """
    Detect specific accounting distortions and manipulations
    
    Focus areas:
    1. Revenue recognition timing
    2. Expense capitalization
    3. Cookie jar reserves
    4. Channel stuffing
    5. Bill-and-hold schemes
    """
    
    def __init__(self):
        self.severity_weights = {
            'critical': 30,
            'high': 20,
            'medium': 10,
            'low': 5
        }
    
    def detect_revenue_distortions(
        self,
        revenue: float,
        revenue_prior: float,
        receivables: float,
        receivables_prior: float,
        deferred_revenue: float,
        deferred_revenue_prior: float,
        cash_from_customers: float
    ) -> Dict[str, any]:
        """
        Detect revenue recognition distortions
        """
        distortions = []
        severity = 0
        
        # 1. Receivables growing faster than revenue
        if revenue_prior > 0 and receivables_prior > 0:
            revenue_growth = (revenue - revenue_prior) / revenue_prior
            receivables_growth = (receivables - receivables_prior) / receivables_prior
            
            if receivables_growth > revenue_growth * 1.5:
                distortions.append({
                    'type': 'Receivables Growth Anomaly',
                    'severity': 'high',
                    'detail': f"Receivables grew {receivables_growth:.1%} vs revenue {revenue_growth:.1%}",
                    'implication': 'Possible channel stuffing or aggressive revenue recognition'
                })
                severity += self.severity_weights['high']
        
        # 2. Deferred revenue declining (SaaS red flag)
        if deferred_revenue_prior > 0:
            deferred_change = (deferred_revenue - deferred_revenue_prior) / deferred_revenue_prior
            if deferred_change < -0.10:  # 10% decline
                distortions.append({
                    'type': 'Deferred Revenue Decline',
                    'severity': 'medium',
                    'detail': f"Deferred revenue declined {deferred_change:.1%}",
                    'implication': 'Possible pull-forward of revenue or customer churn'
                })
                severity += self.severity_weights['medium']
        
        # 3. Cash from customers < Revenue (persistent)
        if cash_from_customers < revenue * 0.85:  # 15% gap
            distortions.append({
                'type': 'Cash Collection Gap',
                'severity': 'high',
                'detail': f"Cash collected {cash_from_customers/1e6:.1f}M vs revenue {revenue/1e6:.1f}M",
                'implication': 'Revenue recognized but not collected'
            })
            severity += self.severity_weights['high']
        
        return {
            'distortions': distortions,
            'severity': min(100, severity)
        }
    
    def detect_expense_capitalization(
        self,
        capex: float,
        capex_prior: float,
        depreciation: float,
        revenue: float,
        revenue_prior: float,
        rd_capitalized: float,
        software_capitalized: float
    ) -> Dict[str, any]:
        """
        Detect aggressive expense capitalization
        """
        distortions = []
        severity = 0
        
        # 1. Capex growing faster than revenue
        if revenue_prior > 0 and capex_prior > 0:
            revenue_growth = (revenue - revenue_prior) / revenue_prior
            capex_growth = (capex - capex_prior) / capex_prior
            
            if capex_growth > revenue_growth * 2 and capex_growth > 0.20:
                distortions.append({
                    'type': 'Aggressive Capex Growth',
                    'severity': 'medium',
                    'detail': f"Capex grew {capex_growth:.1%} vs revenue {revenue_growth:.1%}",
                    'implication': 'Possible expense capitalization to inflate earnings'
                })
                severity += self.severity_weights['medium']
        
        # 2. Capex >> Depreciation (persistent)
        if depreciation > 0:
            capex_to_dep_ratio = capex / depreciation
            if capex_to_dep_ratio > 2.0:
                distortions.append({
                    'type': 'High Capex to Depreciation',
                    'severity': 'low',
                    'detail': f"Capex/Depreciation ratio: {capex_to_dep_ratio:.1f}x",
                    'implication': 'High growth capex or aggressive capitalization'
                })
                severity += self.severity_weights['low']
        
        # 3. R&D capitalization (tech companies)
        if rd_capitalized > 0:
            distortions.append({
                'type': 'R&D Capitalization',
                'severity': 'medium',
                'detail': f"Capitalized R&D: ${rd_capitalized/1e6:.1f}M",
                'implication': 'Earnings inflated by R&D capitalization'
            })
            severity += self.severity_weights['medium']
        
        # 4. Software capitalization
        if software_capitalized > revenue * 0.05:  # > 5% of revenue
            distortions.append({
                'type': 'High Software Capitalization',
                'severity': 'medium',
                'detail': f"Software capex: ${software_capitalized/1e6:.1f}M ({software_capitalized/revenue:.1%} of revenue)",
                'implication': 'Possible aggressive capitalization of development costs'
            })
            severity += self.severity_weights['medium']
        
        return {
            'distortions': distortions,
            'severity': min(100, severity)
        }
    
    def detect_reserve_manipulation(
        self,
        restructuring_charges: float,
        restructuring_charges_prior: float,
        impairment_charges: float,
        warranty_reserves: float,
        warranty_reserves_prior: float,
        bad_debt_expense: float,
        bad_debt_expense_prior: float
    ) -> Dict[str, any]:
        """
        Detect cookie jar reserves and big bath accounting
        """
        distortions = []
        severity = 0
        
        # 1. Frequent restructuring charges (cookie jar)
        if restructuring_charges > 0 and restructuring_charges_prior > 0:
            distortions.append({
                'type': 'Frequent Restructuring',
                'severity': 'high',
                'detail': f"Restructuring charges in multiple periods",
                'implication': 'Possible cookie jar reserves or poor management'
            })
            severity += self.severity_weights['high']
        
        # 2. Large impairment charges (big bath)
        if impairment_charges > 0:
            distortions.append({
                'type': 'Impairment Charges',
                'severity': 'medium',
                'detail': f"Impairment: ${impairment_charges/1e6:.1f}M",
                'implication': 'Possible big bath accounting or poor acquisitions'
            })
            severity += self.severity_weights['medium']
        
        # 3. Warranty reserve changes
        if warranty_reserves_prior > 0:
            reserve_change = (warranty_reserves - warranty_reserves_prior) / warranty_reserves_prior
            if abs(reserve_change) > 0.30:  # 30% change
                distortions.append({
                    'type': 'Warranty Reserve Volatility',
                    'severity': 'low',
                    'detail': f"Warranty reserves changed {reserve_change:.1%}",
                    'implication': 'Possible reserve manipulation'
                })
                severity += self.severity_weights['low']
        
        # 4. Bad debt expense changes
        if bad_debt_expense_prior > 0:
            bad_debt_change = (bad_debt_expense - bad_debt_expense_prior) / bad_debt_expense_prior
            if abs(bad_debt_change) > 0.50:  # 50% change
                distortions.append({
                    'type': 'Bad Debt Expense Volatility',
                    'severity': 'medium',
                    'detail': f"Bad debt expense changed {bad_debt_change:.1%}",
                    'implication': 'Possible earnings management through reserves'
                })
                severity += self.severity_weights['medium']
        
        return {
            'distortions': distortions,
            'severity': min(100, severity)
        }
    
    def detect_working_capital_manipulation(
        self,
        receivables: float,
        receivables_prior: float,
        inventory: float,
        inventory_prior: float,
        payables: float,
        payables_prior: float,
        revenue: float,
        revenue_prior: float,
        cogs: float,
        cogs_prior: float
    ) -> Dict[str, any]:
        """
        Detect working capital manipulation
        """
        distortions = []
        severity = 0
        
        # Calculate days
        if revenue > 0 and revenue_prior > 0:
            receivables_days = (receivables / revenue) * 365
            receivables_days_prior = (receivables_prior / revenue_prior) * 365
            
            if receivables_days > receivables_days_prior * 1.20:  # 20% increase
                distortions.append({
                    'type': 'Rising Receivables Days',
                    'severity': 'high',
                    'detail': f"Receivables days: {receivables_days:.0f} vs {receivables_days_prior:.0f}",
                    'implication': 'Collection issues or channel stuffing'
                })
                severity += self.severity_weights['high']
        
        if cogs > 0 and cogs_prior > 0:
            inventory_days = (inventory / cogs) * 365
            inventory_days_prior = (inventory_prior / cogs_prior) * 365
            
            if inventory_days > inventory_days_prior * 1.25:  # 25% increase
                distortions.append({
                    'type': 'Rising Inventory Days',
                    'severity': 'medium',
                    'detail': f"Inventory days: {inventory_days:.0f} vs {inventory_days_prior:.0f}",
                    'implication': 'Slow-moving inventory or demand issues'
                })
                severity += self.severity_weights['medium']
            
            payables_days = (payables / cogs) * 365
            payables_days_prior = (payables_prior / cogs_prior) * 365
            
            if payables_days > payables_days_prior * 1.30:  # 30% increase
                distortions.append({
                    'type': 'Stretched Payables',
                    'severity': 'medium',
                    'detail': f"Payables days: {payables_days:.0f} vs {payables_days_prior:.0f}",
                    'implication': 'Cash flow pressure or supplier issues'
                })
                severity += self.severity_weights['medium']
        
        return {
            'distortions': distortions,
            'severity': min(100, severity)
        }
    
    def comprehensive_distortion_analysis(
        self,
        # Revenue
        revenue: float,
        revenue_prior: float,
        receivables: float,
        receivables_prior: float,
        deferred_revenue: float = 0,
        deferred_revenue_prior: float = 0,
        cash_from_customers: float = 0,
        
        # Expenses
        capex: float = 0,
        capex_prior: float = 0,
        depreciation: float = 0,
        rd_capitalized: float = 0,
        software_capitalized: float = 0,
        
        # Reserves
        restructuring_charges: float = 0,
        restructuring_charges_prior: float = 0,
        impairment_charges: float = 0,
        warranty_reserves: float = 0,
        warranty_reserves_prior: float = 0,
        bad_debt_expense: float = 0,
        bad_debt_expense_prior: float = 0,
        
        # Working capital
        inventory: float = 0,
        inventory_prior: float = 0,
        payables: float = 0,
        payables_prior: float = 0,
        cogs: float = 0,
        cogs_prior: float = 0,
    ) -> DistortionReport:
        """
        Comprehensive accounting distortion analysis
        """
        all_distortions = []
        total_severity = 0
        
        # 1. Revenue distortions
        revenue_analysis = self.detect_revenue_distortions(
            revenue, revenue_prior, receivables, receivables_prior,
            deferred_revenue, deferred_revenue_prior, cash_from_customers
        )
        all_distortions.extend(revenue_analysis['distortions'])
        total_severity += revenue_analysis['severity']
        
        # 2. Expense capitalization
        expense_analysis = self.detect_expense_capitalization(
            capex, capex_prior, depreciation, revenue, revenue_prior,
            rd_capitalized, software_capitalized
        )
        all_distortions.extend(expense_analysis['distortions'])
        total_severity += expense_analysis['severity']
        
        # 3. Reserve manipulation
        reserve_analysis = self.detect_reserve_manipulation(
            restructuring_charges, restructuring_charges_prior,
            impairment_charges, warranty_reserves, warranty_reserves_prior,
            bad_debt_expense, bad_debt_expense_prior
        )
        all_distortions.extend(reserve_analysis['distortions'])
        total_severity += reserve_analysis['severity']
        
        # 4. Working capital manipulation
        wc_analysis = self.detect_working_capital_manipulation(
            receivables, receivables_prior, inventory, inventory_prior,
            payables, payables_prior, revenue, revenue_prior, cogs, cogs_prior
        )
        all_distortions.extend(wc_analysis['distortions'])
        total_severity += wc_analysis['severity']
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_distortions)
        
        # Adjusted metrics
        adjusted_metrics = {
            'adjusted_revenue': revenue * 0.95 if len([d for d in all_distortions if d['type'] in ['Receivables Growth Anomaly', 'Cash Collection Gap']]) > 0 else revenue,
            'distortion_count': len(all_distortions),
            'critical_count': len([d for d in all_distortions if d['severity'] == 'critical']),
            'high_count': len([d for d in all_distortions if d['severity'] == 'high']),
        }
        
        return DistortionReport(
            distortions_found=[f"{d['type']}: {d['detail']}" for d in all_distortions],
            severity_score=min(100, total_severity),
            adjusted_metrics=adjusted_metrics,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, distortions: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on distortions"""
        recommendations = []
        
        if len(distortions) == 0:
            recommendations.append("No significant accounting distortions detected")
            return recommendations
        
        # Group by severity
        critical = [d for d in distortions if d['severity'] == 'critical']
        high = [d for d in distortions if d['severity'] == 'high']
        
        if len(critical) > 0:
            recommendations.append("CRITICAL: Avoid investment until issues resolved")
        
        if len(high) >= 2:
            recommendations.append("Multiple high-severity issues - significant discount required")
        
        # Specific recommendations
        distortion_types = [d['type'] for d in distortions]
        
        if 'Receivables Growth Anomaly' in distortion_types:
            recommendations.append("Adjust revenue down by 5-10% for quality")
        
        if 'R&D Capitalization' in distortion_types:
            recommendations.append("Expense capitalized R&D to calculate true earnings")
        
        if 'Frequent Restructuring' in distortion_types:
            recommendations.append("Treat restructuring as recurring operating expense")
        
        return recommendations
