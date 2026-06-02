"""Shared helpers for Northstar reporting."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_LOG_PATH = PROJECT_ROOT / "logs" / "reporting.log"


def get_logger() -> logging.Logger:
    """Return the canonical reporting logger with file output."""
    logger = logging.getLogger("northstar.reporting")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    REPORT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(REPORT_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


LOGGER = get_logger()


@dataclass(slots=True)
class SectionResult:
    """Render-ready section payload."""

    name: str
    title: str
    body_html: str
    status: str = "ok"
    badge: str = "OK"
    summary: str | None = None
    warnings: list[str] | None = None


def status_badge(status: str) -> str:
    normalized = (status or "").strip().lower()
    mapping = {
        "ok": "OK",
        "healthy": "HEALTHY",
        "warn": "ALERT",
        "amber": "ALERT",
        "critical": "CRITICAL",
        "fail": "CRITICAL",
        "unavailable": "DATA UNAVAILABLE",
    }
    return mapping.get(normalized, status.upper() if status else "OK")


def unavailable_section(title: str, reason: str, *, name: str | None = None) -> SectionResult:
    LOGGER.warning("%s unavailable: %s", title, reason)
    safe_reason = html_escape(reason)
    return SectionResult(
        name=name or slugify(title),
        title=title,
        status="unavailable",
        badge="DATA UNAVAILABLE",
        summary=reason,
        body_html=(
            "<div class='unavailable-block'>"
            f"<p>{safe_reason}</p>"
            "</div>"
        ),
        warnings=[reason],
    )


def html_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def slugify(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_"}:
            out.append("_")
    return "".join(out).strip("_") or "section"


def existing_path(candidates: Sequence[str | Path]) -> Path:
    for candidate in candidates:
        path = candidate if isinstance(candidate, Path) else PROJECT_ROOT / candidate
        if path.exists():
            return path
    raise FileNotFoundError(f"No existing file found among: {list(candidates)}")


def maybe_path(candidates: Sequence[str | Path]) -> Path | None:
    try:
        return existing_path(candidates)
    except FileNotFoundError:
        return None


def read_parquet_candidates(candidates: Sequence[str | Path], columns: Sequence[str] | None = None) -> pd.DataFrame:
    path = existing_path(candidates)
    return pd.read_parquet(path, columns=list(columns) if columns else None)


def read_csv_candidates(candidates: Sequence[str | Path], **kwargs: Any) -> pd.DataFrame:
    path = existing_path(candidates)
    return pd.read_csv(path, **kwargs)


def read_json_candidates(candidates: Sequence[str | Path]) -> dict[str, Any]:
    path = existing_path(candidates)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise KeyError(f"JSON payload at {path} is not a dict")
    return payload


def read_text_candidates(candidates: Sequence[str | Path]) -> str:
    path = existing_path(candidates)
    return path.read_text(encoding="utf-8", errors="ignore")


def normalize_datetime_frame(df: pd.DataFrame, *, date_candidates: Sequence[str] = ("date", "Date", "timestamp")) -> pd.DataFrame:
    work = df.copy()
    if not any(col in work.columns for col in date_candidates):
        if work.index.name and "date" in str(work.index.name).lower():
            work = work.reset_index()
        elif isinstance(work.index, pd.DatetimeIndex):
            work = work.reset_index().rename(columns={"index": "date"})
    for candidate in date_candidates:
        if candidate in work.columns:
            work["date"] = pd.to_datetime(work[candidate], errors="coerce")
            break
    if "date" not in work.columns:
        raise KeyError("No date-like column available")
    work = work.dropna(subset=["date"]).sort_values("date", kind="mergesort")
    return work


def select_as_of(df: pd.DataFrame, report_date: date | datetime, *, date_col: str = "date") -> pd.DataFrame:
    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    cutoff = pd.Timestamp(report_date)
    if isinstance(report_date, date) and not isinstance(report_date, datetime):
        cutoff = cutoff + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return work.loc[work[date_col] <= cutoff].copy()


def latest_value_on_or_before(series: pd.Series, dates: pd.Series, cutoff: pd.Timestamp) -> float | None:
    work = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce"), "value": pd.to_numeric(series, errors="coerce")})
    work = work.dropna(subset=["date", "value"]).sort_values("date")
    work = work.loc[work["date"] <= cutoff]
    if work.empty:
        return None
    return float(work.iloc[-1]["value"])


def find_series_change(work: pd.DataFrame, value_col: str, anchor: pd.Timestamp, lag_days: int) -> tuple[float | None, float | None]:
    frame = work[["date", value_col]].copy()
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    frame = frame.dropna().sort_values("date")
    latest = latest_value_on_or_before(frame[value_col], frame["date"], anchor)
    previous = latest_value_on_or_before(frame[value_col], frame["date"], anchor - pd.Timedelta(days=lag_days))
    if previous is None and len(frame) >= 2:
        prior_frame = frame.loc[frame["date"] < anchor]
        if not prior_frame.empty:
            previous = float(prior_frame.iloc[-1][value_col])
    if latest is None or previous is None:
        return latest, None
    return latest, float(latest - previous)


def rolling_signal_flag(series: pd.Series) -> str:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 8:
        return "N/A"
    delta = clean.diff().dropna()
    if len(delta) < 8:
        return "N/A"
    latest = float(delta.iloc[-1])
    trailing = delta.tail(90)
    std = float(trailing.std(ddof=0) or 0.0)
    if std <= 0.0:
        return "NEUTRAL"
    z = (latest - float(trailing.mean())) / std
    if z > 1.0:
        return "ALERT"
    if z < -1.0:
        return "ALERT"
    return "NORMAL"


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        out = float(value)
        if np.isnan(out) or np.isinf(out):
            return default
        return out
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def pct_text(value: float | None, *, digits: int = 1, scale: float = 100.0, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value) * scale
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.{digits}f}%"


def num_text(value: float | None, *, digits: int = 2, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.{digits}f}"


def money_text(value: float | None, *, digits: int = 0, prefix: str = "Rs ") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{prefix}{float(value):,.{digits}f}"


def bps_text(value: float | None, *, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f} bps"


def parse_iso_datetime(value: Any) -> datetime | None:
    if value in (None, "", "None"):
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).to_pydatetime()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def age_hours(value: Any) -> float | None:
    dt_value = parse_iso_datetime(value)
    if dt_value is None:
        return None
    return max((now_utc() - dt_value).total_seconds() / 3600.0, 0.0)


def normalize_ticker(symbol: Any) -> str:
    value = str(symbol or "").strip().upper()
    for suffix in (".NS", ".BO"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value


def latest_research_snapshot_path(report_date: date | datetime | None = None) -> Path:
    snapshot_dir = PROJECT_ROOT / "data" / "results" / "research" / "snapshots"
    candidates = sorted(snapshot_dir.rglob("research_snapshot_*.parquet"))
    if not candidates:
        raise FileNotFoundError("No research snapshots available")
    if report_date is None:
        return candidates[-1]
    cutoff = pd.Timestamp(report_date).date()
    eligible = []
    for path in candidates:
        stamp = path.stem.rsplit("_", 1)[-1]
        try:
            file_date = datetime.strptime(stamp, "%Y%m%d").date()
        except ValueError:
            continue
        if file_date <= cutoff:
            eligible.append(path)
    return eligible[-1] if eligible else candidates[-1]


def latest_run_report_path(report_date: date | datetime | None = None) -> Path:
    run_root = PROJECT_ROOT / "data" / "operations" / "complete_v3_runs"
    reports = sorted(run_root.glob("*/run_report.json"))
    if not reports:
        raise FileNotFoundError("No complete_v3 run reports found")
    if report_date is None:
        return reports[-1]
    cutoff = pd.Timestamp(report_date).date()
    eligible = []
    for path in reports:
        try:
            dt = datetime.strptime(path.parent.name.split("_")[0], "%Y%m%d").date()
        except ValueError:
            continue
        if dt <= cutoff:
            eligible.append(path)
    return eligible[-1] if eligible else reports[-1]


def load_current_positions_frame() -> pd.DataFrame:
    current_positions_path = maybe_path(["data/portfolio/current_positions.json"])
    if current_positions_path is None:
        raise FileNotFoundError("Current positions payload missing")

    payload = json.loads(current_positions_path.read_text(encoding="utf-8"))
    raw_positions = payload.get("positions") or {}
    if isinstance(raw_positions, dict):
        rows = []
        for key, value in raw_positions.items():
            if not isinstance(value, dict):
                continue
            row = {"ticker": key}
            row.update(value)
            rows.append(row)
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(raw_positions)
    if df.empty:
        return df
    df["ticker"] = df.get("ticker", df.get("symbol", "")).astype(str)
    df["ticker_base"] = df["ticker"].map(normalize_ticker)
    numeric_cols = ["quantity", "avg_price", "current_price", "market_value", "unrealized_pnl", "weight"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_sector_mapping() -> pd.DataFrame:
    df = read_csv_candidates(["data/metadata/ticker_sector_mapping.csv"])
    df["ticker_base"] = df["ticker"].map(normalize_ticker)
    return df


def cross_sectional_ic(df: pd.DataFrame, factor_col: str, target_col: str, *, date_col: str = "date") -> pd.Series:
    work = df[[date_col, factor_col, target_col]].copy()
    work[factor_col] = pd.to_numeric(work[factor_col], errors="coerce")
    work[target_col] = pd.to_numeric(work[target_col], errors="coerce")
    work = work.dropna()
    if work.empty:
        return pd.Series(dtype=float)

    def _corr(group: pd.DataFrame) -> float:
        if group[factor_col].nunique() < 3 or group[target_col].nunique() < 3:
            return np.nan
        return group[factor_col].corr(group[target_col], method="spearman")

    series = work.groupby(date_col, sort=True).apply(_corr)
    series.index = pd.to_datetime(series.index, errors="coerce")
    return series.dropna().sort_index()


def trailing_factor_ics(df: pd.DataFrame, factor_col: str, target_col: str) -> tuple[float | None, float | None]:
    daily_ic = cross_sectional_ic(df, factor_col, target_col)
    if daily_ic.empty:
        return None, None
    ic_4w = safe_float(daily_ic.tail(20).mean())
    ic_12w = safe_float(daily_ic.tail(60).mean())
    return ic_4w, ic_12w


def factor_columns() -> dict[str, list[str]]:
    return {
        "bab": ["bab_beta", "bab_beta_signal"],
        "amihud": ["amihud_illiquidity", "amihud_liquidity_rank"],
        "piotroski": ["piotroski_f_score_norm", "piotroski_f_score"],
        "max_lottery": ["max_lottery_21d", "max_lottery_5d", "max_lottery_top5_21d"],
        "earnings_quality": ["earnings_quality_score", "accruals_ratio", "accruals_volatility"],
    }


def latest_research_factor_frame(
    report_date: date | datetime,
    extra_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    cols = {
        "date",
        "ticker_x",
        "ticker",
        "sector",
        "forward_return_5d__realized",
        "forward_return_5d",
        "ret_1d",
        "sentiment_5d_mean",
        "sentiment_21d_mean",
    }
    for candidates in factor_columns().values():
        cols.update(candidates)
    if extra_columns:
        cols.update(extra_columns)

    path = latest_research_snapshot_path(report_date)
    df = pd.read_parquet(path, columns=[col for col in cols if col])
    df = normalize_datetime_frame(df)
    df = select_as_of(df, report_date)
    if "ticker_x" in df.columns:
        df["ticker"] = df["ticker_x"].astype(str)
    elif "ticker" not in df.columns:
        raise KeyError("Research snapshot missing ticker column")
    df["ticker_base"] = df["ticker"].map(normalize_ticker)
    return df


def render_note(text: str) -> str:
    return f"<p class='section-note'>{html_escape(text)}</p>"
