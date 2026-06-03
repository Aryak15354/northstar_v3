"""
Sector Mapper - Maps companies to valuation frameworks
Different sectors require different valuation approaches
"""

import pandas as pd
from typing import Dict, List, Optional
from enum import Enum


class SectorCategory(Enum):
    """Primary sector categories for valuation"""
    FINANCIALS = "financials"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    CONSUMER = "consumer"
    INDUSTRIALS = "industrials"
    MATERIALS = "materials"
    ENERGY = "energy"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    TELECOM = "telecom"


class ValuationFramework(Enum):
    """Valuation framework types"""
    FINANCIAL = "financial"  # P/B, ROE-based
    GROWTH = "growth"  # Revenue multiple, growth-adjusted
    ASSET = "asset"  # Asset-based, replacement cost
    CYCLICAL = "cyclical"  # Mid-cycle earnings
    UTILITY = "utility"  # Regulated, yield-based
    STANDARD = "standard"  # Standard DCF/multiples


class SectorMapper:
    """
    Maps companies to appropriate valuation frameworks based on sector
    """
    
    def __init__(self):
        self.sector_mapping = self._initialize_sector_mapping()
        self.framework_mapping = self._initialize_framework_mapping()
        self.sector_characteristics = self._initialize_characteristics()
    
    def _initialize_sector_mapping(self) -> Dict[str, SectorCategory]:
        """Map industry names to sector categories"""
        return {
            # Financials
            'Banks': SectorCategory.FINANCIALS,
            'Insurance': SectorCategory.FINANCIALS,
            'Financial Services': SectorCategory.FINANCIALS,
            'Asset Management': SectorCategory.FINANCIALS,
            'NBFC': SectorCategory.FINANCIALS,
            
            # Technology
            'Information Technology': SectorCategory.TECHNOLOGY,
            'Software': SectorCategory.TECHNOLOGY,
            'IT Services': SectorCategory.TECHNOLOGY,
            'Semiconductors': SectorCategory.TECHNOLOGY,
            'Internet': SectorCategory.TECHNOLOGY,
            
            # Healthcare
            'Pharmaceuticals': SectorCategory.HEALTHCARE,
            'Healthcare': SectorCategory.HEALTHCARE,
            'Biotechnology': SectorCategory.HEALTHCARE,
            'Medical Devices': SectorCategory.HEALTHCARE,
            'Hospitals': SectorCategory.HEALTHCARE,
            
            # Consumer
            'Consumer Goods': SectorCategory.CONSUMER,
            'FMCG': SectorCategory.CONSUMER,
            'Retail': SectorCategory.CONSUMER,
            'Automobiles': SectorCategory.CONSUMER,
            'Consumer Durables': SectorCategory.CONSUMER,
            
            # Industrials
            'Capital Goods': SectorCategory.INDUSTRIALS,
            'Engineering': SectorCategory.INDUSTRIALS,
            'Construction': SectorCategory.INDUSTRIALS,
            'Aerospace': SectorCategory.INDUSTRIALS,
            'Defense': SectorCategory.INDUSTRIALS,
            
            # Materials
            'Metals': SectorCategory.MATERIALS,
            'Mining': SectorCategory.MATERIALS,
            'Chemicals': SectorCategory.MATERIALS,
            'Cement': SectorCategory.MATERIALS,
            'Steel': SectorCategory.MATERIALS,
            
            # Energy
            'Oil & Gas': SectorCategory.ENERGY,
            'Energy': SectorCategory.ENERGY,
            'Power': SectorCategory.ENERGY,
            
            # Utilities
            'Utilities': SectorCategory.UTILITIES,
            'Electric Utilities': SectorCategory.UTILITIES,
            'Water Utilities': SectorCategory.UTILITIES,
            
            # Real Estate
            'Real Estate': SectorCategory.REAL_ESTATE,
            'REITs': SectorCategory.REAL_ESTATE,
            
            # Telecom
            'Telecommunications': SectorCategory.TELECOM,
            'Telecom': SectorCategory.TELECOM,
        }
    
    def _initialize_framework_mapping(self) -> Dict[SectorCategory, ValuationFramework]:
        """Map sectors to valuation frameworks"""
        return {
            SectorCategory.FINANCIALS: ValuationFramework.FINANCIAL,
            SectorCategory.TECHNOLOGY: ValuationFramework.GROWTH,
            SectorCategory.HEALTHCARE: ValuationFramework.GROWTH,
            SectorCategory.CONSUMER: ValuationFramework.STANDARD,
            SectorCategory.INDUSTRIALS: ValuationFramework.CYCLICAL,
            SectorCategory.MATERIALS: ValuationFramework.CYCLICAL,
            SectorCategory.ENERGY: ValuationFramework.CYCLICAL,
            SectorCategory.UTILITIES: ValuationFramework.UTILITY,
            SectorCategory.REAL_ESTATE: ValuationFramework.ASSET,
            SectorCategory.TELECOM: ValuationFramework.UTILITY,
        }
    
    def _initialize_characteristics(self) -> Dict[SectorCategory, Dict]:
        """Define sector-specific characteristics for valuation"""
        return {
            SectorCategory.FINANCIALS: {
                'primary_metrics': ['P/B', 'ROE', 'NIM', 'GNPA'],
                'ignore_metrics': ['EV/EBITDA', 'EV/EBIT'],
                'key_drivers': ['loan_growth', 'credit_quality', 'nim_stability'],
                'typical_roe': 0.15,
                'typical_pb': 2.0,
                'cyclical': True,
            },
            SectorCategory.TECHNOLOGY: {
                'primary_metrics': ['P/S', 'EV/Revenue', 'Rule_of_40', 'FCF_Margin'],
                'ignore_metrics': ['P/B'],
                'key_drivers': ['revenue_growth', 'gross_margin', 'rd_efficiency'],
                'typical_growth': 0.20,
                'typical_margin': 0.70,
                'cyclical': False,
            },
            SectorCategory.HEALTHCARE: {
                'primary_metrics': ['EV/EBITDA', 'P/E', 'Pipeline_Value'],
                'ignore_metrics': [],
                'key_drivers': ['pipeline_strength', 'regulatory_risk', 'patent_expiry'],
                'typical_margin': 0.20,
                'cyclical': False,
            },
            SectorCategory.CONSUMER: {
                'primary_metrics': ['P/E', 'EV/EBITDA', 'ROIC'],
                'ignore_metrics': [],
                'key_drivers': ['brand_power', 'pricing_power', 'distribution'],
                'typical_roic': 0.20,
                'typical_margin': 0.15,
                'cyclical': False,
            },
            SectorCategory.INDUSTRIALS: {
                'primary_metrics': ['EV/EBIT_mid', 'P/B', 'ROIC'],
                'ignore_metrics': [],
                'key_drivers': ['order_book', 'capacity_utilization', 'debt_cycle'],
                'typical_roic': 0.12,
                'cyclical': True,
            },
            SectorCategory.MATERIALS: {
                'primary_metrics': ['EV/EBITDA_mid', 'P/B', 'EV/Ton'],
                'ignore_metrics': [],
                'key_drivers': ['commodity_prices', 'capacity', 'cost_position'],
                'typical_margin': 0.15,
                'cyclical': True,
            },
            SectorCategory.ENERGY: {
                'primary_metrics': ['EV/EBITDA', 'P/CF', 'EV/Reserves'],
                'ignore_metrics': [],
                'key_drivers': ['oil_price', 'reserves', 'production_cost'],
                'typical_margin': 0.10,
                'cyclical': True,
            },
            SectorCategory.UTILITIES: {
                'primary_metrics': ['P/B', 'Dividend_Yield', 'ROE'],
                'ignore_metrics': [],
                'key_drivers': ['regulatory_return', 'rate_base_growth', 'stability'],
                'typical_roe': 0.12,
                'typical_yield': 0.04,
                'cyclical': False,
            },
            SectorCategory.REAL_ESTATE: {
                'primary_metrics': ['P/NAV', 'Cap_Rate', 'FFO_Multiple'],
                'ignore_metrics': ['P/E'],
                'key_drivers': ['occupancy', 'rental_growth', 'asset_quality'],
                'typical_cap_rate': 0.07,
                'cyclical': True,
            },
            SectorCategory.TELECOM: {
                'primary_metrics': ['EV/EBITDA', 'EV/Subscriber', 'FCF_Yield'],
                'ignore_metrics': [],
                'key_drivers': ['arpu', 'subscriber_growth', 'spectrum_cost'],
                'typical_margin': 0.35,
                'cyclical': False,
            },
        }
    
    def map_sector(self, industry: str) -> SectorCategory:
        """Map industry string to sector category"""
        # Direct mapping
        if industry in self.sector_mapping:
            return self.sector_mapping[industry]
        
        # Fuzzy matching
        industry_lower = industry.lower()
        for key, sector in self.sector_mapping.items():
            if key.lower() in industry_lower or industry_lower in key.lower():
                return sector
        
        # Default to standard
        return SectorCategory.CONSUMER  # Most common default
    
    def get_valuation_framework(self, sector: SectorCategory) -> ValuationFramework:
        """Get appropriate valuation framework for sector"""
        return self.framework_mapping.get(sector, ValuationFramework.STANDARD)
    
    def get_sector_characteristics(self, sector: SectorCategory) -> Dict:
        """Get sector-specific characteristics"""
        return self.sector_characteristics.get(sector, {})
    
    def get_primary_metrics(self, sector: SectorCategory) -> List[str]:
        """Get primary valuation metrics for sector"""
        chars = self.get_sector_characteristics(sector)
        return chars.get('primary_metrics', ['P/E', 'EV/EBITDA'])
    
    def should_use_mid_cycle(self, sector: SectorCategory) -> bool:
        """Check if sector requires mid-cycle earnings"""
        chars = self.get_sector_characteristics(sector)
        return chars.get('cyclical', False)
    
    def map_dataframe(self, df: pd.DataFrame, industry_col: str = 'Industry') -> pd.DataFrame:
        """Add sector mapping to dataframe"""
        df = df.copy()
        
        df['sector_category'] = df[industry_col].apply(
            lambda x: self.map_sector(x).value if pd.notna(x) else 'unknown'
        )
        
        df['valuation_framework'] = df['sector_category'].apply(
            lambda x: self.get_valuation_framework(SectorCategory(x)).value 
            if x != 'unknown' else 'standard'
        )
        
        df['is_cyclical'] = df['sector_category'].apply(
            lambda x: self.should_use_mid_cycle(SectorCategory(x)) 
            if x != 'unknown' else False
        )
        
        return df
