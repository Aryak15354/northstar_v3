#!/usr/bin/env python3
"""
🧬 WEEKLY RELATIONSHIP STORE - NORTHSTAR V3 MARKET BRAIN
The Memory Vault: Efficient Storage and Retrieval of Causal Relationships

This manages the storage, indexing, and retrieval of weekly causal relationships:
- Efficient parquet storage with compression
- Fast querying by date, relationship type, strength
- Relationship evolution tracking
- Integration with existing V3 data systems

Integration with V3:
- Stores relationships discovered by Weekly Fabric Builder
- Provides fast access for Capital Allocator
- Feeds into Narrative Engine for storytelling
- Supports Anticipatory Intelligence queries
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class WeeklyRelationshipStore:
    """
    Weekly Relationship Storage and Retrieval System
    
    Manages the complete lifecycle of relationship data:
    - Storage: Efficient parquet files with metadata
    - Indexing: Fast lookup by various criteria
    - Querying: Flexible relationship retrieval
    - Evolution: Track how relationships change over time
    - Integration: Connect with existing V3 systems
    """
    
    def __init__(self):
        self.name = "Weekly Relationship Store"
        self.version = "1.0"
        
        # Storage paths
        self.paths = {
            'base_dir': 'data/weekly_insights',
            'relationship_index': 'data/weekly_insights/relationship_index.parquet',
            'evolution_tracking': 'data/weekly_insights/relationship_evolution.parquet',
            'metadata': 'data/weekly_insights/store_metadata.json',
            'summary_stats': 'data/weekly_insights/summary_statistics.json'
        }
        
        # Storage configuration
        self.config = {
            'compression': 'snappy',
            'index_update_frequency': 'weekly',
            'max_memory_cache': 1000,  # Max relationships to cache in memory
            'evolution_window': 52,    # Weeks to track evolution
            'summary_update_threshold': 100  # New relationships before summary update
        }
        
        # Relationship schema
        self.relationship_schema = {
            'date': 'datetime64[ns]',
            'year': 'int16',
            'week': 'int8',
            'src_type': 'category',
            'src_name': 'string',
            'dst_type': 'category',
            'dst_name': 'string',
            'horizon': 'int8',
            'beta': 'float32',
            'information_gain': 'float32',
            'confidence': 'float32',
            'direction': 'int8',
            'regime_context': 'category',
            'novelty': 'float32',
            'stability': 'float32'
        }
        
        # In-memory cache
        self._relationship_cache = {}
        self._index_cache = None
        self._last_cache_update = None
    
    def ensure_directories(self):
        """Ensure all required directories exist"""
        
        try:
            base_path = Path(self.paths['base_dir'])
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Create year directories if they don't exist
            current_year = datetime.now().year
            for year in range(2000, current_year + 2):
                year_path = base_path / str(year)
                year_path.mkdir(exist_ok=True)
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating directories: {e}")
            return False
    
    def save_weekly_relationships(self, relationships, year, week):
        """Save weekly relationships with optimized storage"""
        
        try:
            if not relationships:
                return False
            
            self.ensure_directories()
            
            # Convert to DataFrame with proper schema
            df = pd.DataFrame(relationships)
            
            # Apply schema types
            for col, dtype in self.relationship_schema.items():
                if col in df.columns:
                    try:
                        if dtype == 'category':
                            df[col] = df[col].astype('category')
                        elif dtype == 'datetime64[ns]':
                            df[col] = pd.to_datetime(df[col])
                        else:
                            df[col] = df[col].astype(dtype)
                    except Exception as e:
                        print(f"⚠️ Warning: Could not convert {col} to {dtype}: {e}")
            
            # Save to parquet with compression
            week_file = os.path.join(
                self.paths['base_dir'], 
                str(year), 
                f'week_{week:02d}.parquet'
            )
            
            df.to_parquet(
                week_file, 
                compression=self.config['compression'],
                index=False
            )
            
            # Update index
            self.update_relationship_index(df, year, week)
            
            # Clear cache to force refresh
            self._relationship_cache.clear()
            self._index_cache = None
            
            print(f"   💾 Saved {len(relationships)} relationships: week_{week:02d}.parquet")
            return True
            
        except Exception as e:
            print(f"❌ Error saving relationships: {e}")
            return False
    
    def update_relationship_index(self, new_relationships, year, week):
        """Update the master relationship index"""
        
        try:
            # Load existing index
            if os.path.exists(self.paths['relationship_index']):
                index_df = pd.read_parquet(self.paths['relationship_index'])
            else:
                index_df = pd.DataFrame()
            
            # Create index entries for new relationships
            index_entries = []
            
            for _, rel in new_relationships.iterrows():
                index_entry = {
                    'year': year,
                    'week': week,
                    'date': rel['date'],
                    'src_type': rel['src_type'],
                    'src_name': rel['src_name'],
                    'dst_type': rel['dst_type'],
                    'dst_name': rel['dst_name'],
                    'horizon': rel['horizon'],
                    'confidence': rel['confidence'],
                    'novelty': rel['novelty'],
                    'file_path': f'{year}/week_{week:02d}.parquet'
                }
                index_entries.append(index_entry)
            
            # Add new entries to index
            if index_entries:
                new_index_df = pd.DataFrame(index_entries)
                
                if not index_df.empty:
                    # Remove existing entries for this year/week to avoid duplicates
                    mask = ~((index_df['year'] == year) & (index_df['week'] == week))
                    index_df = index_df[mask]
                    
                    # Combine with new entries
                    index_df = pd.concat([index_df, new_index_df], ignore_index=True)
                else:
                    index_df = new_index_df
                
                # Sort by date
                index_df = index_df.sort_values(['year', 'week']).reset_index(drop=True)
                
                # Save updated index
                index_df.to_parquet(
                    self.paths['relationship_index'],
                    compression=self.config['compression'],
                    index=False
                )
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error updating relationship index: {e}")
            return False
    
    def load_relationship_index(self):
        """Load and cache the relationship index"""
        
        try:
            if (self._index_cache is not None and 
                self._last_cache_update is not None and
                (datetime.now() - self._last_cache_update).seconds < 300):  # 5 minute cache
                return self._index_cache
            
            if os.path.exists(self.paths['relationship_index']):
                self._index_cache = pd.read_parquet(self.paths['relationship_index'])
                self._last_cache_update = datetime.now()
                return self._index_cache
            else:
                return pd.DataFrame()
                
        except Exception as e:
            print(f"⚠️ Error loading relationship index: {e}")
            return pd.DataFrame()
    
    def query_relationships(self, 
                          start_date=None, 
                          end_date=None,
                          src_types=None,
                          dst_types=None,
                          min_confidence=None,
                          horizons=None,
                          limit=None):
        """Query relationships with flexible filtering"""
        
        try:
            # Load index
            index_df = self.load_relationship_index()
            
            if index_df.empty:
                return pd.DataFrame()
            
            # Apply filters
            mask = pd.Series(True, index=index_df.index)
            
            if start_date:
                mask &= index_df['date'] >= pd.to_datetime(start_date)
            
            if end_date:
                mask &= index_df['date'] <= pd.to_datetime(end_date)
            
            if src_types:
                if isinstance(src_types, str):
                    src_types = [src_types]
                mask &= index_df['src_type'].isin(src_types)
            
            if dst_types:
                if isinstance(dst_types, str):
                    dst_types = [dst_types]
                mask &= index_df['dst_type'].isin(dst_types)
            
            if min_confidence:
                mask &= index_df['confidence'] >= min_confidence
            
            if horizons:
                if isinstance(horizons, int):
                    horizons = [horizons]
                mask &= index_df['horizon'].isin(horizons)
            
            # Apply mask
            filtered_index = index_df[mask]
            
            if filtered_index.empty:
                return pd.DataFrame()
            
            # Apply limit
            if limit:
                filtered_index = filtered_index.head(limit)
            
            # Load actual relationship data
            relationships = []
            
            for file_path in filtered_index['file_path'].unique():
                try:
                    full_path = os.path.join(self.paths['base_dir'], file_path)
                    
                    if os.path.exists(full_path):
                        # Check cache first
                        if file_path in self._relationship_cache:
                            file_relationships = self._relationship_cache[file_path]
                        else:
                            file_relationships = pd.read_parquet(full_path)
                            
                            # Cache if not too many cached files
                            if len(self._relationship_cache) < self.config['max_memory_cache']:
                                self._relationship_cache[file_path] = file_relationships
                        
                        relationships.append(file_relationships)
                        
                except Exception as e:
                    print(f"⚠️ Error loading {file_path}: {e}")
                    continue
            
            if relationships:
                combined_df = pd.concat(relationships, ignore_index=True)
                
                # Apply the same filters to the detailed data
                detail_mask = pd.Series(True, index=combined_df.index)
                
                if start_date:
                    detail_mask &= combined_df['date'] >= pd.to_datetime(start_date)
                
                if end_date:
                    detail_mask &= combined_df['date'] <= pd.to_datetime(end_date)
                
                if src_types:
                    detail_mask &= combined_df['src_type'].isin(src_types)
                
                if dst_types:
                    detail_mask &= combined_df['dst_type'].isin(dst_types)
                
                if min_confidence:
                    detail_mask &= combined_df['confidence'] >= min_confidence
                
                if horizons:
                    detail_mask &= combined_df['horizon'].isin(horizons)
                
                result = combined_df[detail_mask]
                
                if limit:
                    result = result.head(limit)
                
                return result.sort_values('date')
            else:
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error querying relationships: {e}")
            return pd.DataFrame()
    
    def get_recent_trends(self, weeks=8, min_confidence=0.6):
        """Get recent relationship trends for narrative generation"""
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(weeks=weeks)
            
            # Query recent relationships
            recent_relationships = self.query_relationships(
                start_date=start_date,
                end_date=end_date,
                min_confidence=min_confidence
            )
            
            if recent_relationships.empty:
                return {'rising_edges': [], 'collapsing_edges': [], 'new_relationships': []}
            
            # Analyze trends
            trends = self.analyze_relationship_trends(recent_relationships)
            
            return trends
            
        except Exception as e:
            print(f"❌ Error getting recent trends: {e}")
            return {'rising_edges': [], 'collapsing_edges': [], 'new_relationships': []}
    
    def analyze_relationship_trends(self, relationships):
        """Analyze trends in relationship strength over time"""
        
        try:
            trends = {
                'rising_edges': [],
                'collapsing_edges': [],
                'new_relationships': []
            }
            
            # Group by relationship pair
            relationship_groups = relationships.groupby(['src_name', 'dst_name', 'horizon'])
            
            for (src_name, dst_name, horizon), group in relationship_groups:
                if len(group) < 2:
                    continue
                
                # Sort by date
                group_sorted = group.sort_values('date')
                
                # Calculate trend
                recent_confidence = group_sorted['confidence'].iloc[-1]
                older_confidence = group_sorted['confidence'].iloc[0]
                
                confidence_change = recent_confidence - older_confidence
                
                # Check for novelty (new relationships)
                if group_sorted['novelty'].iloc[-1] > 0.7:
                    trends['new_relationships'].append({
                        'src_name': src_name,
                        'dst_name': dst_name,
                        'horizon': horizon,
                        'confidence': recent_confidence,
                        'novelty': group_sorted['novelty'].iloc[-1],
                        'beta': group_sorted['beta'].iloc[-1]
                    })
                
                # Check for rising/collapsing edges
                if abs(confidence_change) > 0.1:  # Significant change
                    edge_info = {
                        'src_name': src_name,
                        'dst_name': dst_name,
                        'horizon': horizon,
                        'confidence_change': confidence_change,
                        'recent_confidence': recent_confidence,
                        'recent_beta': group_sorted['beta'].iloc[-1]
                    }
                    
                    if confidence_change > 0:
                        trends['rising_edges'].append(edge_info)
                    else:
                        trends['collapsing_edges'].append(edge_info)
            
            # Sort by magnitude of change
            trends['rising_edges'] = sorted(
                trends['rising_edges'], 
                key=lambda x: x['confidence_change'], 
                reverse=True
            )
            
            trends['collapsing_edges'] = sorted(
                trends['collapsing_edges'], 
                key=lambda x: abs(x['confidence_change']), 
                reverse=True
            )
            
            trends['new_relationships'] = sorted(
                trends['new_relationships'], 
                key=lambda x: x['novelty'], 
                reverse=True
            )
            
            return trends
            
        except Exception as e:
            print(f"❌ Error analyzing relationship trends: {e}")
            return {'rising_edges': [], 'collapsing_edges': [], 'new_relationships': []}
    
    def get_relationship_evolution(self, src_name, dst_name, horizon, weeks_back=52):
        """Track how a specific relationship has evolved over time"""
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(weeks=weeks_back)
            
            # Query specific relationship
            relationships = self.query_relationships(
                start_date=start_date,
                end_date=end_date
            )
            
            if relationships.empty:
                return pd.DataFrame()
            
            # Filter for specific relationship
            mask = ((relationships['src_name'] == src_name) & 
                   (relationships['dst_name'] == dst_name) & 
                   (relationships['horizon'] == horizon))
            
            evolution = relationships[mask].sort_values('date')
            
            return evolution
            
        except Exception as e:
            print(f"❌ Error getting relationship evolution: {e}")
            return pd.DataFrame()
    
    def get_summary_statistics(self):
        """Get summary statistics about stored relationships"""
        
        try:
            index_df = self.load_relationship_index()
            
            if index_df.empty:
                return {}
            
            stats = {
                'total_relationships': len(index_df),
                'date_range': {
                    'start': index_df['date'].min().isoformat(),
                    'end': index_df['date'].max().isoformat()
                },
                'years_covered': sorted(index_df['year'].unique().tolist()),
                'relationship_types': {
                    'by_src_type': index_df['src_type'].value_counts().to_dict(),
                    'by_dst_type': index_df['dst_type'].value_counts().to_dict(),
                    'by_horizon': index_df['horizon'].value_counts().to_dict()
                },
                'confidence_distribution': {
                    'mean': float(index_df['confidence'].mean()),
                    'std': float(index_df['confidence'].std()),
                    'min': float(index_df['confidence'].min()),
                    'max': float(index_df['confidence'].max())
                },
                'novelty_distribution': {
                    'mean': float(index_df['novelty'].mean()),
                    'std': float(index_df['novelty'].std()),
                    'high_novelty_count': int((index_df['novelty'] > 0.7).sum())
                }
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting summary statistics: {e}")
            return {}
    
    def cleanup_old_cache(self):
        """Clean up old cached data"""
        
        try:
            # Clear memory cache if it's getting too large
            if len(self._relationship_cache) > self.config['max_memory_cache']:
                # Keep only the most recently accessed files
                # For simplicity, just clear the cache
                self._relationship_cache.clear()
                print("   🧹 Cleared relationship cache")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error cleaning up cache: {e}")
            return False
    
    def export_relationships_for_integration(self, start_date=None, end_date=None):
        """Export relationships in format suitable for V3 integration"""
        
        try:
            # Query all relationships in date range
            relationships = self.query_relationships(
                start_date=start_date,
                end_date=end_date
            )
            
            if relationships.empty:
                return {}
            
            # Format for integration with existing V3 systems
            integration_data = {
                'causal_edges': [],
                'pressure_map': {},
                'regime_relationships': {},
                'anticipatory_signals': []
            }
            
            # Process relationships
            for _, rel in relationships.iterrows():
                # Causal edges for graph analysis
                edge = {
                    'source': rel['src_name'],
                    'target': rel['dst_name'],
                    'weight': float(rel['beta']),
                    'confidence': float(rel['confidence']),
                    'horizon': int(rel['horizon']),
                    'date': rel['date'].isoformat()
                }
                integration_data['causal_edges'].append(edge)
                
                # Pressure map for capital allocation
                pressure_key = f"{rel['src_type']}_{rel['dst_type']}"
                if pressure_key not in integration_data['pressure_map']:
                    integration_data['pressure_map'][pressure_key] = []
                
                integration_data['pressure_map'][pressure_key].append({
                    'pressure': float(rel['beta']),
                    'confidence': float(rel['confidence']),
                    'date': rel['date'].isoformat()
                })
                
                # Anticipatory signals (high novelty relationships)
                if rel['novelty'] > 0.7:
                    signal = {
                        'relationship': f"{rel['src_name']} → {rel['dst_name']}",
                        'signal_strength': float(rel['novelty']),
                        'confidence': float(rel['confidence']),
                        'horizon_weeks': int(rel['horizon']),
                        'date': rel['date'].isoformat()
                    }
                    integration_data['anticipatory_signals'].append(signal)
            
            return integration_data
            
        except Exception as e:
            print(f"❌ Error exporting relationships for integration: {e}")
            return {}

def main():
    """Test the relationship store"""
    
    store = WeeklyRelationshipStore()
    
    # Test data
    test_relationships = [
        {
            'date': datetime.now(),
            'year': 2024,
            'week': 1,
            'src_type': 'macro',
            'src_name': 'repo_rate',
            'dst_type': 'sector',
            'dst_name': 'banking',
            'horizon': 4,
            'beta': 0.35,
            'information_gain': 0.25,
            'confidence': 0.75,
            'direction': 1,
            'regime_context': 'expansion',
            'novelty': 0.8,
            'stability': 0.7
        }
    ]
    
    # Test save
    success = store.save_weekly_relationships(test_relationships, 2024, 1)
    
    if success:
        print("✅ Relationship store test passed")
        
        # Test query
        results = store.query_relationships(min_confidence=0.5)
        print(f"   Found {len(results)} relationships")
        
        # Test summary
        stats = store.get_summary_statistics()
        print(f"   Total relationships in store: {stats.get('total_relationships', 0)}")
        
        return True
    else:
        print("❌ Relationship store test failed")
        return False

if __name__ == "__main__":
    main()