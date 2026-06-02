#!/usr/bin/env python3
"""
Download Indian News Sentiment dataset from Hugging Face
Dataset: harixn/indian_news_sentiment
"""

import os
from pathlib import Path
from datasets import load_dataset

def download_dataset():
    """Download and save the Indian News Sentiment dataset"""
    
    # Create data directory if it doesn't exist
    data_dir = Path("data/raw/news")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print("Downloading Indian News Sentiment dataset from Hugging Face...")
    print("Dataset: harixn/indian_news_sentiment")
    
    try:
        # Load the dataset
        ds = load_dataset("harixn/indian_news_sentiment")
        
        print(f"\nDataset loaded successfully!")
        print(f"Available splits: {list(ds.keys())}")
        
        # Save to disk in different formats
        for split_name, split_data in ds.items():
            print(f"\nProcessing split: {split_name}")
            print(f"Number of rows: {len(split_data)}")
            
            # Save as CSV
            csv_path = data_dir / f"harixn_indian_news_sentiment_{split_name}.csv"
            split_data.to_csv(str(csv_path))
            print(f"Saved CSV: {csv_path}")
            
            # Save as JSON
            json_path = data_dir / f"harixn_indian_news_sentiment_{split_name}.json"
            split_data.to_json(str(json_path))
            print(f"Saved JSON: {json_path}")
            
            # Save as Parquet (efficient format)
            parquet_path = data_dir / f"harixn_indian_news_sentiment_{split_name}.parquet"
            split_data.to_parquet(str(parquet_path))
            print(f"Saved Parquet: {parquet_path}")
        
        # Print dataset info
        print("\n" + "="*60)
        print("Dataset Information:")
        print("="*60)
        for split_name, split_data in ds.items():
            print(f"\nSplit: {split_name}")
            print(f"Columns: {split_data.column_names}")
            print(f"Features: {split_data.features}")
            if len(split_data) > 0:
                print(f"\nSample row:")
                print(split_data[0])
        
        print("\n" + "="*60)
        print(f"Dataset downloaded successfully to: {data_dir}")
        print("="*60)
        
        return ds
        
    except Exception as e:
        print(f"\nError downloading dataset: {e}")
        print("\nNote: This dataset may require authentication.")
        print("If you see an authentication error, run:")
        print("  huggingface-cli login")
        raise

if __name__ == "__main__":
    download_dataset()
