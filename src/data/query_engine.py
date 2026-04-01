"""Lightweight DuckDB-backed parquet query helper with pandas fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd


def _safe_identifier(name: str) -> str:
    # Conservative identifier quoting for known local schemas.
    return '"' + str(name).replace('"', '""') + '"'


@dataclass
class DuckDBQueryEngine:
    """Query parquet with pushdown filters while keeping API pandas-friendly."""

    memory_limit_mb: int = 1024
    threads: int = 1

    def __post_init__(self) -> None:
        self._duckdb = None
        self._con = None
        try:
            import duckdb as _duckdb  # type: ignore

            self._duckdb = _duckdb
            self._con = _duckdb.connect(database=":memory:")
            self._con.execute(f"PRAGMA threads={max(1, int(self.threads))}")
            self._con.execute(f"PRAGMA memory_limit='{max(256, int(self.memory_limit_mb))}MB'")
        except Exception:
            self._duckdb = None
            self._con = None

    @property
    def available(self) -> bool:
        return self._con is not None

    def _query(self, sql: str, params: Optional[Sequence[Any]] = None) -> pd.DataFrame:
        if self._con is None:
            raise RuntimeError("duckdb_unavailable")
        if params:
            return self._con.execute(sql, list(params)).df()
        return self._con.execute(sql).df()

    def columns(self, path: Path | str) -> List[str]:
        p = str(path)
        if not self.available:
            try:
                return list(pd.read_parquet(p, engine="pyarrow").columns)
            except Exception:
                return []
        try:
            df = self._query("SELECT * FROM read_parquet(?) LIMIT 0", [p])
            return list(df.columns)
        except Exception:
            return []

    def scalar(self, path: Path | str, expression_sql: str) -> Any:
        p = str(path)
        if not self.available:
            return None
        try:
            df = self._query(
                f"SELECT {expression_sql} AS value FROM read_parquet(?)",
                [p],
            )
            if df.empty:
                return None
            return df.iloc[0]["value"]
        except Exception:
            return None

    def read_parquet(
        self,
        path: Path | str,
        *,
        columns: Optional[Iterable[str]] = None,
        date_col: Optional[str] = None,
        start_date: Optional[pd.Timestamp | str] = None,
        end_date: Optional[pd.Timestamp | str] = None,
        equal_filters: Optional[Dict[str, Any]] = None,
        in_filters: Optional[Dict[str, Sequence[Any]]] = None,
        order_by: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        p = str(path)

        if not self.available:
            kwargs: Dict[str, Any] = {}
            if columns:
                kwargs["columns"] = list(columns)
            if in_filters and "ticker" in in_filters:
                vals = list(in_filters.get("ticker") or [])
                if vals:
                    kwargs["filters"] = [("ticker", "in", vals)]
            try:
                out = pd.read_parquet(p, **kwargs)
            except Exception:
                return pd.DataFrame()
            if date_col and date_col in out.columns:
                d = pd.to_datetime(out[date_col], errors="coerce")
                if start_date is not None:
                    out = out.loc[d >= pd.to_datetime(start_date, errors="coerce")]
                if end_date is not None:
                    out = out.loc[d <= pd.to_datetime(end_date, errors="coerce")]
            if equal_filters:
                for k, v in equal_filters.items():
                    if k in out.columns:
                        out = out.loc[out[k] == v]
            if in_filters:
                for k, vals in in_filters.items():
                    if k in out.columns:
                        out = out.loc[out[k].isin(list(vals or []))]
            if order_by:
                valid = [c for c in order_by if c in out.columns]
                if valid:
                    out = out.sort_values(valid)
            if limit is not None and limit > 0 and len(out) > int(limit):
                out = out.head(int(limit))
            return out.reset_index(drop=True)

        select_cols = "*"
        if columns:
            clean = [str(c) for c in columns if str(c)]
            if clean:
                select_cols = ", ".join(_safe_identifier(c) for c in clean)

        clauses: List[str] = []
        params: List[Any] = [p]

        if date_col:
            q_col = _safe_identifier(date_col)
            if start_date is not None:
                clauses.append(f"{q_col} >= ?")
                params.append(pd.Timestamp(start_date).to_pydatetime())
            if end_date is not None:
                clauses.append(f"{q_col} <= ?")
                params.append(pd.Timestamp(end_date).to_pydatetime())

        if equal_filters:
            for key, value in equal_filters.items():
                clauses.append(f"{_safe_identifier(key)} = ?")
                params.append(value)

        if in_filters:
            for key, values in in_filters.items():
                vals = [v for v in list(values or []) if v is not None]
                if not vals:
                    continue
                placeholders = ", ".join(["?"] * len(vals))
                clauses.append(f"{_safe_identifier(key)} IN ({placeholders})")
                params.extend(vals)

        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order_sql = ""
        if order_by:
            clean_order = [str(c) for c in order_by if str(c)]
            if clean_order:
                order_sql = " ORDER BY " + ", ".join(_safe_identifier(c) for c in clean_order)

        limit_sql = ""
        if limit is not None and int(limit) > 0:
            limit_sql = f" LIMIT {int(limit)}"

        sql = f"SELECT {select_cols} FROM read_parquet(?)" + where_sql + order_sql + limit_sql
        try:
            return self._query(sql, params).reset_index(drop=True)
        except Exception:
            return pd.DataFrame()
