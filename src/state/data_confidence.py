#!/usr/bin/env python3
"""
📊 DATA CONFIDENCE ENGINE - PREVENT FAKE PRECISION
Track data quality and coverage to ensure honest precision

This engine tracks:
- Data coverage (% of universe with data)
- Data freshness (days since last update)
- Data completeness (missing fields)
- Overall system confidence

Key Principle: HONEST PRECISION
- Never show false precision with missing data
- Confidence multiplies all scores
- Low confidence = lower conviction

Usage:
    from src.state.data_confidence import DataConfidenceEngine
    
    engine = DataConfidenceEngine()
    confidence = engine.compute_confidence()
    
    # Apply to scores
    final_score = raw_score * confidence['overall']
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

class DataConfidenceEngine:
    """
    Data Confidence Tracker - Prevent Fake Precision
    
    Tracks data quality across all system components
    to ensure we never show false precision
    """
    
    def __init__(self):
        self.data_paths = {
            'fundamentals': 'data/processed/fundamentals.parquet',
            'valuation': 'data/processed/valuation.parquet',
            'technicals': 'data/processed/technicals.parquet',
            'macro': 'data/macro/factors/macro_score.parquet',
            'prices': 'data/processed/prices.parquet',
            'scores': 'data/processed/scores.parquet'
        }
        
        self.output_path = 'data/processed/data_confidence.parquet'
        
        # Confidence thresholds
        self.thresholds = {
            'coverage_min': 0.6,      # 60% minimum coverage
            'freshness_days': 30,     # 30 days maximum staleness
            'completeness_min': 0.7   # 70% minimum completeness
        }
    
    def safe_read_parquet(self, path):
        """Safely read parquet with error handling"""
        try:
            if os.path.exists(path):
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
        except Exception as e:
            print(f"⚠️ Error reading {path}: {e}")
        return pd.DataFrame()
    
    def compute_coverage_confidence(self, df, name):
        """Compute coverage confidence for a dataset"""
        if df.empty:
            return {
                'coverage_pct': 0.0,
                'coverage_confidence': 0.0,
                'record_count': 0
            }
        
        # Basic coverage metrics
        total_records = len(df)
        non_null_records = len(df.dropna(how='all'))
        coverage_pct = non_null_records / total_records if total_records > 0 else 0
        
        # Coverage confidence (sigmoid function)
        coverage_confidence = 1 / (1 + np.exp(-10 * (coverage_pct - 0.5)))
        
        return {
            'coverage_pct': coverage_pct,
            'coverage_confidence': coverage_confidence,
            'record_count': total_records
        }
    
    def compute_freshness_confidence(self, df, name):
        """Compute freshness confidence based on data age"""
        if df.empty:
            return {
                'staleness_days': 999,
                'freshness_confidence': 0.0
            }
        
        # Try to find date column
        date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        
        if date_cols:
            try:
                latest_date = pd.to_datetime(df[date_cols[0]]).max()
                staleness_days = (datetime.now() - latest_date).days
            except:
                staleness_days = 30  # Default assumption
        else:
            # Use file modification time as fallback
            try:
                file_path = self.data_paths.get(name, '')
                if os.path.exists(file_path):
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    staleness_days = (datetime.now() - mod_time).days
                else:
                    staleness_days = 999
            except:
                staleness_days = 999
        
        # Freshness confidence (exponential decay)
        freshness_confidence = np.exp(-staleness_days / 30.0)  # 30-day half-life
        
        return {
            'staleness_days': staleness_days,
            'freshness_confidence': freshness_confidence
        }
    
    def compute_completeness_confidence(self, df, name):
        """Compute completeness confidence based on missing fields"""
        if df.empty:
            return {
                'completeness_pct': 0.0,
                'completeness_confidence': 0.0
            }
        
        # Calculate completeness across all fields
        total_cells = df.size
        non_null_cells = df.count().sum()
        completeness_pct = non_null_cells / total_cells if total_cells > 0 else 0
        
        # Completeness confidence
        completeness_confidence = max(0, min(1, completeness_pct))
        
        return {
            'completeness_pct': completeness_pct,
            'completeness_confidence': completeness_confidence
        }
    
    def compute_dataset_confidence(self, name):
        """Compute overall confidence for a single dataset"""
        df = self.safe_read_parquet(self.data_paths.get(name, ''))
        
        # Compute individual confidence metrics
        coverage = self.compute_coverage_confidence(df, name)
        freshness = self.compute_freshness_confidence(df, name)
        completeness = self.compute_completeness_confidence(df, name)
        
        # Overall dataset confidence (geometric mean)
        individual_confidences = [
            coverage['coverage_confidence'],
            freshness['freshness_confidence'],
            completeness['completeness_confidence']
        ]
        
        # Geometric mean (more conservative than arithmetic mean)
        dataset_confidence = np.prod(individual_confidences) ** (1/len(individual_confidences))
        
        return {
            'dataset': name,
            'coverage_pct': coverage['coverage_pct'],
            'staleness_days': freshness['staleness_days'],
            'completeness_pct': completeness['completeness_pct'],
            'coverage_confidence': coverage['coverage_confidence'],
            'freshness_confidence': freshness['freshness_confidence'],
            'completeness_confidence': completeness['completeness_confidence'],
            'dataset_confidence': dataset_confidence,
            'record_count': coverage['record_count']
        }
    
    def compute_system_confidence(self):
        """Compute overall system confidence"""
        
        print("📊 Computing Data Confidence...")
        
        # Compute confidence for each dataset
        dataset_confidences = []
        
        for name in self.data_paths.keys():
            confidence = self.compute_dataset_confidence(name)
            dataset_confidences.append(confidence)
            
            print(f"   {name:12}: {confidence['dataset_confidence']:.1%} "
                  f"(coverage: {confidence['coverage_pct']:.1%}, "
                  f"age: {confidence['staleness_days']}d, "
                  f"complete: {confidence['completeness_pct']:.1%})")
        
        # Overall system confidence (minimum of critical datasets)
        critical_datasets = ['fundamentals', 'valuation', 'macro', 'prices']
        critical_confidences = [
            c['dataset_confidence'] for c in dataset_confidences 
            if c['dataset'] in critical_datasets
        ]
        
        if critical_confidences:
            # Use minimum of critical datasets (weakest link)
            system_confidence = min(critical_confidences)
        else:
            system_confidence = 0.3  # Default low confidence
        
        # Create summary
        confidence_summary = {
            'timestamp': datetime.now(),
            'system_confidence': system_confidence,
            'datasets': dataset_confidences,
            'critical_confidence': system_confidence,
            'data_quality_grade': self.get_confidence_grade(system_confidence)
        }
        
        return confidence_summary
    
    def get_confidence_grade(self, confidence):
        """Convert confidence to letter grade"""
        if confidence >= 0.8:
            return 'A'
        elif confidence >= 0.6:
            return 'B'
        elif confidence >= 0.4:
            return 'C'
        elif confidence >= 0.2:
            return 'D'
        else:
            return 'F'
    
    def save_confidence_metrics(self, confidence_summary):
        """Save confidence metrics to parquet"""
        
        # Create DataFrame from dataset confidences
        datasets_df = pd.DataFrame(confidence_summary['datasets'])
        datasets_df['timestamp'] = confidence_summary['timestamp']
        datasets_df['system_confidence'] = confidence_summary['system_confidence']
        
        # Create directory if needed
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        # Save to parquet
        datasets_df.to_parquet(self.output_path, index=False)
        
        print(f"💾 Data confidence saved to: {self.output_path}")
        
        return self.output_path
    
    def run(self):
        """Main execution - compute and save data confidence"""
        
        print("📊 DATA CONFIDENCE ENGINE - PREVENT FAKE PRECISION")
        print("=" * 60)
        
        # Compute system confidence
        confidence_summary = self.compute_system_confidence()
        
        # Save metrics
        output_path = self.save_confidence_metrics(confidence_summary)
        
        # Print summary
        print(f"\n📊 DATA CONFIDENCE SUMMARY")
        print("-" * 40)
        print(f"System Confidence: {confidence_summary['system_confidence']:.1%}")
        print(f"Data Quality Grade: {confidence_summary['data_quality_grade']}")
        print(f"Critical Datasets: {len([d for d in confidence_summary['datasets'] if d['dataset_confidence'] > 0.6])}/{len(confidence_summary['datasets'])}")
        
        # Warnings for low confidence
        if confidence_summary['system_confidence'] < 0.6:
            print(f"\n⚠️ LOW SYSTEM CONFIDENCE: {confidence_summary['system_confidence']:.1%}")
            print("   Scores will be penalized for data quality issues")
            
            # Identify problem datasets
            problem_datasets = [
                d for d in confidence_summary['datasets'] 
                if d['dataset_confidence'] < 0.6
            ]
            
            for dataset in problem_datasets:
                print(f"   📉 {dataset['dataset']}: {dataset['dataset_confidence']:.1%}")
                if dataset['staleness_days'] > 30:
                    print(f"      - Stale data ({dataset['staleness_days']} days old)")
                if dataset['coverage_pct'] < 0.6:
                    print(f"      - Low coverage ({dataset['coverage_pct']:.1%})")
                if dataset['completeness_pct'] < 0.7:
                    print(f"      - Incomplete data ({dataset['completeness_pct']:.1%})")
        else:
            print(f"\n✅ GOOD SYSTEM CONFIDENCE: {confidence_summary['system_confidence']:.1%}")
        
        print(f"\n✅ Data Confidence Engine operational")
        print(f"📁 Output: {output_path}")
        
        return confidence_summary

# =========================== UTILITY FUNCTIONS ===========================

def load_latest_confidence():
    """Load latest data confidence metrics"""
    
    confidence_path = 'data/processed/data_confidence.parquet'
    
    try:
        if os.path.exists(confidence_path):
            df = pd.read_parquet(confidence_path)
            if not df.empty:
                # Get latest timestamp
                latest_time = df['timestamp'].max()
                latest_df = df[df['timestamp'] == latest_time]
                
                # Return system confidence
                system_confidence = latest_df['system_confidence'].iloc[0]
                
                print(f"📖 Loaded data confidence: {system_confidence:.1%}")
                return system_confidence
    except Exception as e:
        print(f"⚠️ Error loading data confidence: {e}")
    
    # Return default confidence
    print("⚠️ Using default data confidence: 50%")
    return 0.5

def apply_confidence_penalty(scores, confidence=None):
    """Apply confidence penalty to scores"""
    
    if confidence is None:
        confidence = load_latest_confidence()
    
    # Apply confidence multiplier
    adjusted_scores = scores * confidence
    
    print(f"📊 Applied {confidence:.1%} confidence penalty to scores")
    
    return adjusted_scores

# =========================== MAIN EXECUTION ===========================

def main():
    """Main execution"""
    engine = DataConfidenceEngine()
    confidence = engine.run()
    return confidence

if __name__ == "__main__":
    main()