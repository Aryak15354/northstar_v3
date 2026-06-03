"""
Quick test script to validate stock options integration

Tests:
1. Stock loader initialization
2. Instrument key lookup
3. Sector filtering
4. Top liquid stocks
5. Single stock monitoring
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.stock_options_loader import get_stock_loader

def test_stock_loader():
    """Test stock options loader"""
    print("=" * 80)
    print("TEST 1: Stock Options Loader")
    print("=" * 80)
    
    loader = get_stock_loader()
    
    print(f"✓ Loaded {len(loader.get_all_symbols())} stocks with options")
    print(f"✓ Available sectors: {len(loader.get_sectors())}")
    
    # Test single stock lookup
    reliance = loader.get_stock('RELIANCE')
    if reliance:
        print(f"✓ RELIANCE lookup: {reliance.name}")
        print(f"  - ISIN: {reliance.isin}")
        print(f"  - Instrument Key: {reliance.instrument_key}")
        print(f"  - Lot Size: {reliance.lot_size}")
        print(f"  - Sector: {reliance.sector}")
    else:
        print("✗ RELIANCE lookup failed")
        return False
    
    # Test sector filtering
    banking = loader.get_by_sector('Financial Services')
    print(f"✓ Financial Services sector: {len(banking)} stocks")
    
    # Test recommended stocks
    recommended = loader.get_recommended_for_beginners()
    print(f"✓ Recommended stocks: {len(recommended)}")
    
    # Test search
    results = loader.search_stocks('tata')
    print(f"✓ Search 'tata': {len(results)} results")
    
    print("\n✅ Stock loader tests passed\n")
    return True


def test_top_liquid_stocks():
    """Test top liquid stocks list"""
    print("=" * 80)
    print("TEST 2: Top Liquid Stocks")
    print("=" * 80)
    
    loader = get_stock_loader()
    
    top_stocks = ['ITC', 'ONGC', 'SBIN', 'NATIONALUM', 'TCS', 'GAIL', 'HINDZINC', 'VEDL', 
                 'CANBK', 'LICI', 'TATASTEEL', 'COALINDIA', 'HDFCBANK', 'SAIL', 'WIPRO',
                 'BANKINDIA', 'PIIND', 'RELIANCE', 'SUNPHARMA', 'TIINDIA']
    
    print(f"Testing {len(top_stocks)} top liquid stocks...")
    
    missing = []
    for symbol in top_stocks:
        stock = loader.get_stock(symbol)
        if not stock:
            missing.append(symbol)
        else:
            print(f"  ✓ {symbol:15} - {stock.name:40} Lot: {stock.lot_size}")
    
    if missing:
        print(f"\n✗ Missing stocks: {missing}")
        return False
    
    print("\n✅ All top liquid stocks available\n")
    return True


def test_sectors():
    """Test sector coverage"""
    print("=" * 80)
    print("TEST 3: Sector Coverage")
    print("=" * 80)
    
    loader = get_stock_loader()
    sectors = loader.get_sectors()
    
    print(f"Total sectors: {len(sectors)}\n")
    
    for sector in sectors:
        stocks = loader.get_by_sector(sector)
        print(f"  {sector:40} {len(stocks):3} stocks")
    
    print("\n✅ Sector tests passed\n")
    return True


def test_instrument_keys():
    """Test instrument key format"""
    print("=" * 80)
    print("TEST 4: Instrument Key Format")
    print("=" * 80)
    
    loader = get_stock_loader()
    
    # Test a few stocks
    test_stocks = ['RELIANCE', 'TCS', 'HDFCBANK', 'ITC', 'INFY']
    
    for symbol in test_stocks:
        stock = loader.get_stock(symbol)
        if stock:
            # Verify format: NSE_EQ|ISIN
            if stock.instrument_key.startswith('NSE_EQ|INE'):
                print(f"  ✓ {symbol:15} {stock.instrument_key}")
            else:
                print(f"  ✗ {symbol:15} Invalid format: {stock.instrument_key}")
                return False
        else:
            print(f"  ✗ {symbol} not found")
            return False
    
    print("\n✅ Instrument key format tests passed\n")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("STOCK OPTIONS INTEGRATION TEST SUITE")
    print("=" * 80 + "\n")
    
    tests = [
        test_stock_loader,
        test_top_liquid_stocks,
        test_sectors,
        test_instrument_keys
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}\n")
            results.append(False)
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if all(results):
        print("\n🎉 ALL TESTS PASSED - Stock options integration is working!\n")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Please review errors above\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
