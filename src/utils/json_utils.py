"""
JSON Utilities - Robust JSON loading with error handling
"""

import json
import os

def safe_load_json(file_path, default=None):
    """
    Safely load JSON file with comprehensive error handling
    """
    if not os.path.exists(file_path):
        print(f"Warning: JSON file not found: {file_path}")
        return default if default is not None else {}
    
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            
        if not content:
            print(f"Warning: Empty JSON file: {file_path}")
            return default if default is not None else {}
            
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in {file_path}: {e}")
        return default if default is not None else {}
        
    except Exception as e:
        print(f"Warning: Error loading JSON {file_path}: {e}")
        return default if default is not None else {}

def safe_save_json(data, file_path):
    """Safely save JSON file"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Warning: Error saving JSON {file_path}: {e}")
        return False
