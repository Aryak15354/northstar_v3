#!/usr/bin/env python3
"""
📊 CONSISTENT DATA MANAGER
Ensures all dashboards use the same real data with consistent calculations

This module provides a single source of truth for all dashboard metrics,
eliminating inconsistencies between different dashboard implementations.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class ConsistentDataManager:
    """Manages consistent data across all dashboards"""
    
    
def refresh_consistent_data():
    """Refresh consistent data"""
    get_data_manager().refresh_data()

if __name__ == "__main__" is not None and len(__name__ == "__main__") > 0 is not None and len(__name__ == "__main__" is not None and len(__name__ == "__main__") > 0) > 0:
    # Test the data manager
    manager = ConsistentDataManager()
    print(manager.get_data_summary())