"""Deterministic derived-view materializer from PRS authoritative state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class RuntimeMaterializer:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def state_json_path(self) -> Path:
        return self.output_dir / "portfolio_state_current.json"

    @property
    def state_parquet_path(self) -> Path:
        return self.output_dir / "portfolio_state_current.parquet"

    @property
    def positions_parquet_path(self) -> Path:
        return self.output_dir / "portfolio_positions_current.parquet"

    @property
    def events_parquet_path(self) -> Path:
        return self.output_dir / "portfolio_ledger_events.parquet"

    @property
    def greeks_parquet_path(self) -> Path:
        return self.output_dir / "portfolio_risk_greeks.parquet"

    @property
    def stress_parquet_path(self) -> Path:
        return self.output_dir / "portfolio_stress_matrix.parquet"

    def materialize_snapshot(self, snapshot: Dict[str, Any]) -> None:
        payload = dict(snapshot)
        self.state_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

        row = {k: v for k, v in payload.items() if k not in {"holdings", "sector_allocation", "regime_context", "hedging_state", "transaction_history"}}
        row["sector_allocation_json"] = json.dumps(payload.get("sector_allocation", {}), sort_keys=True)
        row["regime_context_json"] = json.dumps(payload.get("regime_context", {}), sort_keys=True)
        row["hedging_state_json"] = json.dumps(payload.get("hedging_state", {}), sort_keys=True)
        row["transaction_history_json"] = json.dumps(payload.get("transaction_history", []), sort_keys=True)
        pd.DataFrame([row]).to_parquet(self.state_parquet_path, index=False)

        positions = []
        for symbol, h in sorted(dict(payload.get("holdings", {}) or {}).items()):
            record = {"symbol": symbol}
            record.update(dict(h or {}))
            positions.append(record)
        pd.DataFrame(positions if positions else [{"symbol": ""}]).to_parquet(self.positions_parquet_path, index=False)

        greeks = {
            "timestamp_utc": payload.get("timestamp_utc"),
            "net_delta": payload.get("net_delta", 0.0),
            "net_gamma": payload.get("net_gamma", 0.0),
            "net_vega": payload.get("net_vega", 0.0),
            "net_theta": payload.get("net_theta", 0.0),
            "net_rho": payload.get("net_rho", 0.0),
            "gross_exposure": payload.get("gross_exposure", 0.0),
            "net_exposure": payload.get("net_exposure", 0.0),
            "cash": payload.get("cash", 0.0),
            "state_hash": payload.get("state_hash", ""),
        }
        pd.DataFrame([greeks]).to_parquet(self.greeks_parquet_path, index=False)

    def materialize_events(self, events: List[Dict[str, Any]]) -> None:
        rows: List[Dict[str, Any]] = []
        for ev in sorted(events, key=lambda e: int(e.get("event_id", 0) or 0)):
            row = dict(ev)
            row["payload_json"] = str(row.get("payload_json", "{}"))
            rows.append(row)
        if not rows:
            rows = [{"event_id": 0, "event_type": "", "timestamp_utc": "", "proposal_id": ""}]
        pd.DataFrame(rows).to_parquet(self.events_parquet_path, index=False)

    def materialize_stress(self, records: List[Dict[str, Any]]) -> None:
        rows = [dict(r) for r in records]
        if not rows:
            rows = [{"event_id": 0, "scenario_id": "", "pnl_impact": 0.0, "risk_metric": 0.0}]
        pd.DataFrame(rows).to_parquet(self.stress_parquet_path, index=False)
