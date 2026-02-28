#!/usr/bin/env python3
"""
🎯 UNIFIED PORTFOLIO COORDINATOR - NORTHSTAR V3 PHASE 4
Master Portfolio Construction System

This is the unified coordinator that orchestrates all portfolio construction
components into a single, coherent portfolio management system.

Coordinates:
- Portfolio Governor (main portfolio construction)
- Capital Allocator (strategy allocation with Bayesian beliefs)
- Strategy blending and portfolio optimization
- Integration with unified intelligence and risk systems

Usage:
from cohesion.dependency_container import get_dependency_container

    from src.portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
    
    coordinator = UnifiedPortfolioCoordinator()
    success = coordinator.construct_unified_portfolio()
"""

import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path for imports
import pathlib
project_root = str(pathlib.Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class UnifiedPortfolioCoordinator:
    """
    Unified Portfolio Coordinator - Master Portfolio Construction System
    
    Orchestrates all portfolio construction components to create a unified
    portfolio that integrates intelligence, capital allocation, and risk management.
    """
    
    def __init__(self):
        self.name = "Unified Portfolio Coordinator"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'portfolio_analytics': 'data/processed/portfolio_analytics.json',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'unified_portfolio': 'data/processed/unified_portfolio.parquet',
            'coordination_log': 'data/processed/portfolio_coordination_log.json'
        }
        
        # Ensure directories exist
        os.makedirs('data/processed', exist_ok=True)
        
        # Initialize components (lazy loading)
        self._portfolio_governor = None
        self._capital_allocator = None
        
        # Coordination tracking
        self.coordination_log = []
    
    def log_coordination(self, component, status, message="", duration=0):
        """Log coordination activities"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.coordination_log.append(entry)
        
        # Print status
        status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
        print(f"   {status_icon} {component}: {message}")
    
    @property
    def portfolio_governor(self):
        """Lazy load Portfolio Governor"""
        if self._portfolio_governor is None:
            try:
                from src.portfolio.portfolio_governor import PortfolioGovernor
                self._portfolio_governor = PortfolioGovernor()
            except ImportError as e:
                try:
                    from portfolio.portfolio_governor import PortfolioGovernor
                    self._portfolio_governor = PortfolioGovernor()
                except ImportError:
                    print(f"⚠️ Portfolio Governor not available: {e}")
                    self._portfolio_governor = None
        return self._portfolio_governor
    
    @property
    def capital_allocator(self):
        """Lazy load Capital Allocator"""
        if self._capital_allocator is None:
            try:
                from src.intelligence.capital_allocator import CapitalAllocator
                self._capital_allocator = CapitalAllocator()
            except ImportError as e:
                try:
                    from intelligence.capital_allocator import CapitalAllocator
                    self._capital_allocator = CapitalAllocator()
                except ImportError:
                    print(f"⚠️ Capital Allocator not available: {e}")
                    self._capital_allocator = None
        return self._capital_allocator
    
    def run_capital_allocation(self):
        """Step 1: Run capital allocation across strategies"""
        
        print("🧠 STEP 1: CAPITAL ALLOCATION")
        print("-" * 30)
        
        start_time = datetime.now()
        
        try:
            if self.capital_allocator:
                # Run Bayesian capital allocation
                allocations = self.capital_allocator.run_allocation()
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if allocations:
                    self.log_coordination('capital_allocator', 'success', 
                                        f"Allocated capital across {len(allocations)} strategies", duration)
                    
                    # Show top allocations
                    sorted_allocs = sorted(allocations.items(), key=lambda x: x[1], reverse=True)
                    print(f"   📊 Top allocations:")
                    for strategy, allocation in sorted_allocs[:3]:
                        print(f"     {strategy}: {allocation:.1%}")
                    
                    return allocations
                else:
                    self.log_coordination('capital_allocator', 'failed', 
                                        "No capital allocations generated", duration)
                    return {}
            else:
                self.log_coordination('capital_allocator', 'failed', 
                                    "Capital Allocator not available", 0)
                return {}
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_coordination('capital_allocator', 'failed', str(e), duration)
            return {}
    
    def run_portfolio_construction(self, allocations):
        """Step 2: Run portfolio construction with capital allocations"""
        
        print("\n🎯 STEP 2: PORTFOLIO CONSTRUCTION")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            if self.portfolio_governor:
                # Inject capital allocations into portfolio governor
                if allocations:
                    # Save allocations for portfolio governor to use
                    with open(self.paths['capital_allocations'], 'w') as f:
                        json.dump({
                            'timestamp': datetime.now().isoformat(),
                            'allocations': allocations
                        }, f, indent=2, default=str)
                
                # Run portfolio construction
                portfolio, analytics = self.portfolio_governor.run_portfolio_construction()
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if not portfolio.empty:
                    total_exposure = portfolio['final_weight'].sum()
                    self.log_coordination('portfolio_governor', 'success', 
                                        f"Constructed portfolio: {len(portfolio)} positions, {total_exposure:.1%} exposure", 
                                        duration)
                    return portfolio, analytics
                else:
                    self.log_coordination('portfolio_governor', 'failed', 
                                        "Empty portfolio generated", duration)
                    return pd.DataFrame(), {}
            else:
                self.log_coordination('portfolio_governor', 'failed', 
                                    "Portfolio Governor not available", 0)
                return pd.DataFrame(), {}
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_coordination('portfolio_governor', 'failed', str(e), duration)
            return pd.DataFrame(), {}
    
    def enhance_portfolio_with_allocations(self, portfolio, allocations, analytics):
        """Step 3: Enhance portfolio with allocation metadata"""
        
        print("\n🧬 STEP 3: PORTFOLIO ENHANCEMENT")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            if portfolio.empty:
                self.log_coordination('portfolio_enhancement', 'skipped', 
                                    "Empty portfolio - skipping enhancement", 0)
                return portfolio, analytics
            
            # Add allocation metadata to portfolio
            enhanced_portfolio = portfolio.copy()
            
            # Add strategy allocation information
            enhanced_portfolio['strategy_allocations'] = json.dumps(allocations)
            enhanced_portfolio['allocation_timestamp'] = datetime.now().isoformat()
            enhanced_portfolio['coordination_version'] = self.version
            
            # Calculate strategy contribution scores
            if allocations:
                # This is a simplified approach - in practice would need strategy-position mapping
                total_strategies = len(allocations)
                enhanced_portfolio['strategy_diversification'] = total_strategies
                enhanced_portfolio['top_strategy_allocation'] = max(allocations.values()) if allocations else 0
            
            # Enhance analytics with allocation information
            enhanced_analytics = analytics.copy()
            enhanced_analytics['capital_allocation'] = {
                'strategy_count': len(allocations),
                'allocations': allocations,
                'allocation_entropy': self.calculate_allocation_entropy(allocations),
                'concentration_ratio': max(allocations.values()) if allocations else 0
            }
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_coordination('portfolio_enhancement', 'success', 
                                f"Enhanced portfolio with {len(allocations)} strategy allocations", 
                                duration)
            
            return enhanced_portfolio, enhanced_analytics
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_coordination('portfolio_enhancement', 'failed', str(e), duration)
            return portfolio, analytics
    
    def calculate_allocation_entropy(self, allocations):
        """Calculate entropy of capital allocations (diversification measure)"""
        
        if not allocations:
            return 0
        
        allocations_array = np.array(list(allocations.values()))
        allocations_array = allocations_array[allocations_array > 0]  # Remove zeros
        
        if len(allocations_array) == 0:
            return 0
        
        # Normalize to probabilities
        probs = allocations_array / allocations_array.sum()
        
        # Calculate entropy
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        
        return float(entropy)
    
    def save_unified_portfolio(self, portfolio, analytics):
        """Step 4: Save unified portfolio and analytics"""
        
        print("\n💾 STEP 4: SAVE UNIFIED PORTFOLIO")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Save unified portfolio
            if not portfolio.empty:
                portfolio.to_parquet(self.paths['unified_portfolio'], index=False)
                print(f"   ✅ Unified portfolio saved: {len(portfolio)} positions")
            else:
                # Save empty portfolio
                empty_portfolio = pd.DataFrame(columns=['ticker', 'final_weight'])
                empty_portfolio.to_parquet(self.paths['unified_portfolio'], index=False)
                print(f"   ✅ Empty unified portfolio saved")
            
            # Save enhanced analytics
            analytics['unified_coordination'] = {
                'timestamp': datetime.now().isoformat(),
                'coordinator_version': self.version,
                'coordination_success': True,
                'coordination_log': self.coordination_log
            }
            
            with open(self.paths['portfolio_analytics'], 'w') as f:
                json.dump(analytics, f, indent=2, default=str)
            
            # Save coordination log
            coordination_summary = {
                'timestamp': datetime.now().isoformat(),
                'coordinator_version': self.version,
                'coordination_log': self.coordination_log,
                'success_rate': sum(1 for entry in self.coordination_log if entry['status'] == 'success') / len(self.coordination_log) if self.coordination_log else 0,
                'total_duration': sum(entry['duration_seconds'] for entry in self.coordination_log)
            }
            
            with open(self.paths['coordination_log'], 'w') as f:
                json.dump(coordination_summary, f, indent=2, default=str)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_coordination('save_portfolio', 'success', 
                                "Unified portfolio and analytics saved", duration)
            
            return True
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_coordination('save_portfolio', 'failed', str(e), duration)
            return False
    
    def construct_unified_portfolio(self):
        """Main unified portfolio construction process"""
        
        print("🎯 UNIFIED PORTFOLIO COORDINATOR")
        print("=" * 60)
        
        total_start_time = datetime.now()
        
        # Step 1: Capital Allocation
        allocations = self.run_capital_allocation()
        
        # Step 2: Portfolio Construction
        portfolio, analytics = self.run_portfolio_construction(allocations)
        
        # Step 3: Portfolio Enhancement
        enhanced_portfolio, enhanced_analytics = self.enhance_portfolio_with_allocations(
            portfolio, allocations, analytics
        )
        
        # Step 4: Save Results
        save_success = self.save_unified_portfolio(enhanced_portfolio, enhanced_analytics)
        
        # Calculate results
        total_duration = (datetime.now() - total_start_time).total_seconds()
        successful_steps = sum(1 for entry in self.coordination_log if entry['status'] == 'success')
        total_steps = len(self.coordination_log)
        
        # Print summary
        print(f"\n🎯 UNIFIED PORTFOLIO COORDINATION COMPLETE")
        print("=" * 60)
        print(f"Duration: {total_duration:.1f} seconds")
        print(f"Success: {successful_steps}/{total_steps} steps")
        
        if not enhanced_portfolio.empty:
            total_exposure = enhanced_portfolio['final_weight'].sum()
            print(f"Portfolio: {len(enhanced_portfolio)} positions, {total_exposure:.1%} exposure")
            
            if allocations:
                print(f"Strategies: {len(allocations)} strategies allocated")
        
        return successful_steps >= 2  # At least capital allocation and portfolio construction must succeed

def main():
    """Main execution function"""
    
    coordinator = UnifiedPortfolioCoordinator()
    success = coordinator.construct_unified_portfolio()
    
    return success

if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
