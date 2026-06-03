#!/usr/bin/env python3
"""
Headless dashboard rendering audit for Northstar V3.

What it checks:
- Every render_* method (except top-level page bootstrap methods)
- Exceptions during section rendering
- Flat charts (single-value/near-zero variance traces)
- DataFrame Arrow serialization compatibility

Outputs:
- reports/system/dashboard_render_audit_latest.json
"""

from __future__ import annotations

import inspect
import json
import traceback
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.northstar_v3_ultimate_integrated_dashboard import (
    NorthstarV3UltimateIntegratedDashboard,
    load_core_data,
    load_sentiment_context,
)

try:
    import pyarrow as pa
except Exception:
    pa = None


def _is_flat_trace(values) -> bool | None:
    try:
        arr = pd.to_numeric(pd.Series(values), errors="coerce").dropna().to_numpy(dtype=float)
    except Exception:
        return None
    if arr.size < 5:
        return None
    span = float(np.nanmax(arr) - np.nanmin(arr))
    sd = float(np.nanstd(arr))
    return bool(span <= 1e-9 or sd <= 1e-10)


def main() -> int:
    dashboard = NorthstarV3UltimateIntegratedDashboard()
    data = load_core_data()
    sentiment_ctx = load_sentiment_context()
    try:
        integrated = dashboard._get_integrated_frame(max_rows=2500)
    except Exception:
        integrated = pd.DataFrame()

    original_plotly = st.plotly_chart
    original_dataframe = st.dataframe
    original_error = st.error

    method_ctx = {"name": None}
    results = []
    charts = []
    dataframe_arrow_issues = []
    st_error_calls = []

    def wrapped_plotly(fig, *args, **kwargs):
        flat_flags = []
        for trace in getattr(fig, "data", []):
            flag = _is_flat_trace(getattr(trace, "y", None))
            if flag is not None:
                flat_flags.append(flag)
        charts.append(
            {
                "method": method_ctx["name"],
                "key": kwargs.get("key"),
                "title": str(getattr(getattr(fig, "layout", None), "title", None).text or ""),
                "traces": len(getattr(fig, "data", [])),
                "all_flat": bool(flat_flags and all(flat_flags)),
            }
        )
        return original_plotly(fig, *args, **kwargs)

    def wrapped_dataframe(frame=None, *args, **kwargs):
        if isinstance(frame, pd.DataFrame) and pa is not None:
            try:
                pa.Table.from_pandas(frame)
            except Exception as exc:
                dataframe_arrow_issues.append(
                    {
                        "method": method_ctx["name"],
                        "error": str(exc),
                        "columns": list(frame.columns)[:40],
                    }
                )
        return original_dataframe(frame, *args, **kwargs)

    def wrapped_error(*args, **kwargs):
        st_error_calls.append({"method": method_ctx["name"], "message": str(args[0] if args else "")})
        return original_error(*args, **kwargs)

    st.plotly_chart = wrapped_plotly
    st.dataframe = wrapped_dataframe
    st.error = wrapped_error

    skip = {"render_header", "render_live_refresh_controls", "render"}
    methods = sorted(
        [
            name
            for name in dir(dashboard)
            if name.startswith("render_") and name not in skip and callable(getattr(dashboard, name))
        ]
    )

    for name in methods:
        fn = getattr(dashboard, name)
        sig = inspect.signature(fn)
        kwargs = {}
        supported = True
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            if pname == "data":
                kwargs[pname] = data
            elif pname == "sentiment_ctx":
                kwargs[pname] = sentiment_ctx
            elif pname == "integrated":
                kwargs[pname] = integrated
            elif pname == "live_mode":
                kwargs[pname] = False
            elif pname == "key_prefix":
                kwargs[pname] = f"audit_{name}"
            elif param.default is inspect._empty:
                supported = False
                break
        if not supported:
            results.append({"method": name, "status": "skipped"})
            continue

        method_ctx["name"] = name
        try:
            fn(**kwargs)
            results.append({"method": name, "status": "ok"})
        except Exception as exc:
            results.append(
                {
                    "method": name,
                    "status": "error",
                    "error": str(exc),
                    "trace": traceback.format_exc().splitlines()[-12:],
                }
            )

    summary = {
        "methods_total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "charts_total": len(charts),
        "charts_all_flat": sum(1 for c in charts if c.get("all_flat")),
        "charts_no_key": sum(1 for c in charts if not c.get("key")),
        "dataframe_arrow_issues": len(dataframe_arrow_issues),
        "st_error_calls": len(st_error_calls),
    }

    report = {
        "summary": summary,
        "errors": [r for r in results if r["status"] == "error"],
        "flat_charts": [c for c in charts if c.get("all_flat")],
        "dataframe_arrow_issues": dataframe_arrow_issues,
        "st_errors": st_error_calls,
    }

    out_path = Path("reports/system/dashboard_render_audit_latest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str))

    print(json.dumps(summary, indent=2))
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
