#!/usr/bin/env python3
"""
🔗 INTEGRATE ALPHA GENERATION INTO V3 SYSTEM
Ensure alpha generation is properly integrated with the main V3 system
"""

import os
import sys

def integrate_alpha_generation():
    """Integrate alpha generation into the main V3 system"""
    
    # Read the main system runner
    main_system_path = 'run_complete_v3_system.py'
    
    if not os.path.exists(main_system_path):
        print("❌ Main system runner not found")
        return False
    
    with open(main_system_path, 'r') as f:
        content = f.read()
    
    # Add alpha generation import and integration
    alpha_integration = '''
    def run_alpha_generation(self):
        """Run alpha generation pipeline"""
        
        if self.verbose:
            print("\\n🧠 Running Alpha Generation Pipeline...")
        
        try:
            # Import alpha engine
            sys.path.append('src')
            from intelligence.institutional_alpha_engine import InstitutionalAlphaEngine
            
            # Initialize engine
            engine = InstitutionalAlphaEngine()
            
            # Generate sample market data for alpha generation
            market_data = {
                'prices': {},
                'volumes': {},
                'fundamentals': {},
                'macro_data': {},
                'sentiment_data': {}
            }
            
            # Sample universe
            universe = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 
                       'ICICIBANK', 'KOTAKBANK', 'BHARTIARTL', 'ITC', 'SBIN']
            
            # Generate alpha positions
            result = engine.generate_alpha_positions(market_data, universe)
            
            self.log_phase('alpha_generation', 'success', 
                          f"Alpha generation completed - {len(result.positions)} positions generated")
            
            # Save alpha results
            os.makedirs('data/alpha', exist_ok=True)
            alpha_results = {
                'timestamp': result.timestamp.isoformat(),
                'positions': result.positions,
                'allocations': result.allocations,
                'regime_state': result.regime_state,
                'health_status': result.health_status,
                'execution_time': result.execution_time
            }
            
            import json
            with open('data/alpha/latest_alpha_results.json', 'w') as f:
                json.dump(alpha_results, f, indent=2)
            
            return True
            
        except Exception as e:
            self.log_phase('alpha_generation', 'failed', f"Alpha generation failed: {e}")
            return False
'''
    
    # Add alpha generation to the phases
    if "'dashboard_launch': {'duration': 0, 'status': 'pending', 'details': []}" in content:
        content = content.replace(
            "'dashboard_launch': {'duration': 0, 'status': 'pending', 'details': []}",
            "'alpha_generation': {'duration': 0, 'status': 'pending', 'details': []},\n            'dashboard_launch': {'duration': 0, 'status': 'pending', 'details': []}"
        )
    
    # Add the alpha generation method to the class
    if "def run_command(self, command, phase, description, timeout=1800, cwd=None):" in content:
        content = content.replace(
            "def run_command(self, command, phase, description, timeout=1800, cwd=None):",
            f"{alpha_integration}\n    def run_command(self, command, phase, description, timeout=1800, cwd=None):"
        )
    
    # Add alpha generation to the full pipeline
    if "def run_full_pipeline(self):" in content:
        # Find the method and add alpha generation call
        lines = content.split('\n')
        new_lines = []
        in_full_pipeline = False
        
        for line in lines:
            new_lines.append(line)
            
            if "def run_full_pipeline(self):" in line:
                in_full_pipeline = True
            
            if in_full_pipeline and "self.run_data_ingestion()" in line:
                # Add alpha generation after data ingestion
                new_lines.append("        ")
                new_lines.append("        # Phase 2: Alpha Generation")
                new_lines.append("        if not self.run_alpha_generation():")
                new_lines.append("            return False")
        
        content = '\n'.join(new_lines)
    
    # Write the updated content
    with open(main_system_path, 'w') as f:
        f.write(content)
    
    print("✅ Alpha generation integrated into main V3 system")
    return True

def main():
    """Main execution"""
    
    print("🔗 INTEGRATING ALPHA GENERATION INTO V3 SYSTEM")
    print("=" * 50)
    
    if integrate_alpha_generation():
        print("\n✅ Integration completed successfully!")
        print("   - Alpha generation is now part of the main pipeline")
        print("   - Results will be saved to data/alpha/")
        print("   - Run 'python run_complete_v3_system.py' to test")
    else:
        print("\n❌ Integration failed")

if __name__ == "__main__":
    main()