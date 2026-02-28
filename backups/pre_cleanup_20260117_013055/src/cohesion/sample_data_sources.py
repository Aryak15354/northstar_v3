#!/usr/bin/env python3
"""
📊 SAMPLE DATA SOURCES - FOR TESTING INTEGRATED DATA PIPELINE
Sample implementations of data sources for testing the capital-grade pipeline system

These are concrete implementations of the IDataSource protocol for testing purposes.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.integrated_data_pipeline import IDataSource, ProcessingResult

class MockMarketDataSource(IDataSource):
    """Mock market data source for testing"""
    
    def __init__(self, name: str = "mock_market_data"):
        self.name = name
        self.last_update = datetime.now()
        self.connection_valid = True
    
    def get_name(self) -> str:
        return self.name
    
    def get_data(self, query: Dict[str, Any]) -> ProcessingResult:
        """Generate mock market data"""
        
        try:
            # Generate sample market data
            dates = pd.date_range(
                start=datetime.now() - timedelta(days=30),
                end=datetime.now(),
                freq='D'
            )
            
            symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
            
            data_rows = []
            for date in dates:
                for symbol in symbols:
                    # Generate realistic price data
                    base_price = {'AAPL': 150, 'GOOGL': 2500, 'MSFT': 300, 'TSLA': 200, 'AMZN': 3000}[symbol]
                    price = base_price * (1 + np.random.normal(0, 0.02))  # 2% daily volatility
                    volume = np.random.randint(1000000, 10000000)
                    
                    data_rows.append({
                        'date': date,
                        'symbol': symbol,
                        'price': round(price, 2),
                        'volume': volume,
                        'market_cap': price * 1000000000,  # Mock market cap
                        'sector': self._get_sector(symbol)
                    })
            
            df = pd.DataFrame(data_rows)
            
            return ProcessingResult(
                success=True,
                data=df,
                errors=[],
                warnings=[],
                metadata={
                    'source': self.name,
                    'rows': len(df),
                    'symbols': len(symbols),
                    'date_range': f"{dates[0].date()} to {dates[-1].date()}"
                },
                processing_time=0.1
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                data=None,
                errors=[f"Error generating mock market data: {str(e)}"],
                warnings=[],
                metadata={},
                processing_time=0.0
            )
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for symbol"""
        sector_map = {
            'AAPL': 'Technology',
            'GOOGL': 'Technology', 
            'MSFT': 'Technology',
            'TSLA': 'Automotive',
            'AMZN': 'Consumer Discretionary'
        }
        return sector_map.get(symbol, 'Unknown')
    
    def validate_connection(self) -> bool:
        return self.connection_valid
    
    def get_last_update(self) -> Optional[datetime]:
        return self.last_update

class MockMacroDataSource(IDataSource):
    """Mock macro data source for testing"""
    
    def __init__(self, name: str = "mock_macro_data"):
        self.name = name
        self.last_update = datetime.now()
        self.connection_valid = True
    
    def get_name(self) -> str:
        return self.name
    
    def get_data(self, query: Dict[str, Any]) -> ProcessingResult:
        """Generate mock macro data"""
        
        try:
            # Generate sample macro data
            dates = pd.date_range(
                start=datetime.now() - timedelta(days=365),
                end=datetime.now(),
                freq='M'  # Monthly data
            )
            
            data_rows = []
            for i, date in enumerate(dates):
                # Generate realistic macro indicators
                gdp_growth = 2.5 + np.random.normal(0, 0.5)  # Around 2.5% with noise
                inflation = 3.0 + np.random.normal(0, 0.3)   # Around 3% with noise
                unemployment = 4.0 + np.random.normal(0, 0.2) # Around 4% with noise
                interest_rate = 5.0 + np.random.normal(0, 0.1) # Around 5% with noise
                
                data_rows.append({
                    'date': date,
                    'gdp_growth': round(gdp_growth, 2),
                    'inflation_rate': round(inflation, 2),
                    'unemployment_rate': round(unemployment, 2),
                    'interest_rate': round(interest_rate, 2),
                    'consumer_confidence': round(np.random.uniform(80, 120), 1),
                    'manufacturing_pmi': round(np.random.uniform(45, 55), 1)
                })
            
            df = pd.DataFrame(data_rows)
            
            return ProcessingResult(
                success=True,
                data=df,
                errors=[],
                warnings=[],
                metadata={
                    'source': self.name,
                    'rows': len(df),
                    'indicators': 6,
                    'date_range': f"{dates[0].date()} to {dates[-1].date()}"
                },
                processing_time=0.05
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                data=None,
                errors=[f"Error generating mock macro data: {str(e)}"],
                warnings=[],
                metadata={},
                processing_time=0.0
            )
    
    def validate_connection(self) -> bool:
        return self.connection_valid
    
    def get_last_update(self) -> Optional[datetime]:
        return self.last_update

class MockFundamentalDataSource(IDataSource):
    """Mock fundamental data source for testing"""
    
    def __init__(self, name: str = "mock_fundamental_data"):
        self.name = name
        self.last_update = datetime.now()
        self.connection_valid = True
    
    def get_name(self) -> str:
        return self.name
    
    def get_data(self, query: Dict[str, Any]) -> ProcessingResult:
        """Generate mock fundamental data"""
        
        try:
            symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
            
            data_rows = []
            for symbol in symbols:
                # Generate realistic fundamental metrics
                revenue = np.random.uniform(50e9, 500e9)  # $50B to $500B
                net_income = revenue * np.random.uniform(0.1, 0.3)  # 10-30% margin
                total_assets = revenue * np.random.uniform(1.5, 3.0)
                
                data_rows.append({
                    'symbol': symbol,
                    'report_date': datetime.now() - timedelta(days=30),  # Last quarter
                    'revenue': round(revenue, 0),
                    'net_income': round(net_income, 0),
                    'total_assets': round(total_assets, 0),
                    'pe_ratio': round(np.random.uniform(15, 35), 2),
                    'pb_ratio': round(np.random.uniform(1, 5), 2),
                    'roe': round(np.random.uniform(0.1, 0.25), 3),
                    'debt_to_equity': round(np.random.uniform(0.2, 1.5), 2)
                })
            
            df = pd.DataFrame(data_rows)
            
            return ProcessingResult(
                success=True,
                data=df,
                errors=[],
                warnings=[],
                metadata={
                    'source': self.name,
                    'rows': len(df),
                    'symbols': len(symbols),
                    'metrics': 7
                },
                processing_time=0.08
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                data=None,
                errors=[f"Error generating mock fundamental data: {str(e)}"],
                warnings=[],
                metadata={},
                processing_time=0.0
            )
    
    def validate_connection(self) -> bool:
        return self.connection_valid
    
    def get_last_update(self) -> Optional[datetime]:
        return self.last_update

class FailingDataSource(IDataSource):
    """Data source that fails for testing retry logic"""
    
    def __init__(self, name: str = "failing_data_source", fail_count: int = 2):
        self.name = name
        self.fail_count = fail_count
        self.attempt_count = 0
        self.last_update = datetime.now()
    
    def get_name(self) -> str:
        return self.name
    
    def get_data(self, query: Dict[str, Any]) -> ProcessingResult:
        """Fail for first few attempts, then succeed"""
        
        self.attempt_count += 1
        
        if self.attempt_count <= self.fail_count:
            # Simulate transient failure
            raise Exception(f"Simulated transient failure (attempt {self.attempt_count})")
        
        # Success after retries
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'value': [10, 20, 30],
            'timestamp': [datetime.now()] * 3
        })
        
        return ProcessingResult(
            success=True,
            data=df,
            errors=[],
            warnings=[f"Succeeded after {self.attempt_count} attempts"],
            metadata={'attempts': self.attempt_count},
            processing_time=0.02
        )
    
    def validate_connection(self) -> bool:
        return True
    
    def get_last_update(self) -> Optional[datetime]:
        return self.last_update

class StaleDataSource(IDataSource):
    """Data source with stale data for testing freshness checks"""
    
    def __init__(self, name: str = "stale_data_source", age_hours: int = 48):
        self.name = name
        self.age_hours = age_hours
        self.last_update = datetime.now() - timedelta(hours=age_hours)
    
    def get_name(self) -> str:
        return self.name
    
    def get_data(self, query: Dict[str, Any]) -> ProcessingResult:
        """Return stale data"""
        
        # Create data with old timestamps
        old_date = datetime.now() - timedelta(hours=self.age_hours)
        
        df = pd.DataFrame({
            'date': [old_date] * 5,
            'symbol': ['STALE'] * 5,
            'price': [100.0] * 5,
            'volume': [1000] * 5
        })
        
        return ProcessingResult(
            success=True,
            data=df,
            errors=[],
            warnings=[f"Data is {self.age_hours} hours old"],
            metadata={'data_age_hours': self.age_hours},
            processing_time=0.01
        )
    
    def validate_connection(self) -> bool:
        return True
    
    def get_last_update(self) -> Optional[datetime]:
        return self.last_update

def create_sample_data_sources() -> Dict[str, IDataSource]:
    """Create a set of sample data sources for testing"""
    
    return {
        'market_data': MockMarketDataSource(),
        'macro_data': MockMacroDataSource(),
        'fundamental_data': MockFundamentalDataSource(),
        'failing_source': FailingDataSource(fail_count=2),
        'stale_source': StaleDataSource(age_hours=48)
    }

def main():
    """Test the sample data sources"""
    
    print("📊 TESTING SAMPLE DATA SOURCES")
    print("=" * 40)
    
    sources = create_sample_data_sources()
    
    for name, source in sources.items():
        print(f"\n🔍 Testing {name}...")
        
        try:
            # Test connection
            if source.validate_connection():
                print(f"   ✅ Connection valid")
            else:
                print(f"   ❌ Connection invalid")
                continue
            
            # Test data retrieval
            result = source.get_data({})
            
            if result.success:
                print(f"   ✅ Data retrieved successfully")
                print(f"   📊 Rows: {len(result.data) if result.data is not None else 0}")
                print(f"   ⏱️ Processing time: {result.processing_time:.3f}s")
                
                if result.warnings:
                    print(f"   ⚠️ Warnings: {'; '.join(result.warnings)}")
            else:
                print(f"   ❌ Data retrieval failed: {'; '.join(result.errors)}")
        
        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")
    
    print(f"\n✅ Sample data sources test completed!")
    
    return True

if __name__ == "__main__":
    main()