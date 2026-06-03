"""
Single source of truth for alternative data feature key names.

Both alternative_feature_block.py and alternative_pipeline_runner.py import
from here. Never use bare string literals for these keys.
"""

# Credit market keys
CREDIT_UPGRADE_RATIO = "credit_upgrade_ratio"
CREDIT_NET_MOMENTUM = "credit_net_momentum"
CREDIT_STRESS_FLAG = "credit_stress_flag"

# Bulk deal / smart money keys
BULK_NET_FLOW = "bulk_net_flow"
BULK_BREADTH = "bulk_breadth"
BULK_SIGNAL_NUMERIC = "bulk_signal_numeric"
BULK_ACCUMULATION_BREADTH = "bulk_accumulation_breadth"
BULK_DISTRIBUTION_BREADTH = "bulk_distribution_breadth"
BULK_NET_BREADTH = "bulk_net_breadth"

# Power keys
POWER_DEVIATION_SEASONAL = "power_deviation_seasonal"
POWER_YOY_GROWTH = "power_yoy_growth"
POWER_INDUSTRIAL_PROXY = "power_industrial_proxy"

# GST keys
GST_YOY_GROWTH = "gst_yoy_growth"
GST_DEVIATION = "gst_deviation"
GST_TREND_ACCEL = "gst_trend_accel"
GST_REGIME_NUMERIC = "gst_regime_numeric"

# Promoter pledge keys
PLEDGE_MARKET_AVG = "pledge_market_avg"
PLEDGE_TREND = "pledge_trend"
PLEDGE_SYSTEMIC_RISK = "pledge_systemic_risk"
