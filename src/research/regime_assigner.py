"""Assign walk-forward regimes from externally auditable config."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any, Sequence

import pandas as pd


class RegimeAssigner:
    """Assign event-driven regimes to walk-forward windows and validate concentration."""

    def __init__(self, regime_cfg: dict[str, Any]):
        self.cfg = dict(regime_cfg or {})
        self.boundaries = dict(self.cfg.get("regime_boundaries") or {})
        self.caps = dict(self.cfg.get("exposure_caps") or {})
        self.priority = [str(label) for label in self.cfg.get("priority_order") or []]
        self.validation = dict(self.cfg.get("validation") or {})
        self._event_windows = self._build_event_windows()

    def _build_event_windows(self) -> list[dict[str, Any]]:
        windows: list[dict[str, Any]] = []
        for boundary in self.boundaries.values():
            label = str(boundary.get("label", "") or "").strip()
            if not label:
                continue
            weeks_before = int(boundary.get("window_weeks_before", 1) or 1)
            weeks_after = int(boundary.get("window_weeks_after", 2) or 2)
            for date_str in boundary.get("event_dates") or []:
                event_date = pd.Timestamp(date_str).normalize()
                windows.append(
                    {
                        "start": event_date - timedelta(weeks=weeks_before),
                        "end": event_date + timedelta(weeks=weeks_after),
                        "label": label,
                        "event_date": event_date,
                    }
                )
        return windows

    def assign_regime(
        self,
        test_start: pd.Timestamp,
        test_end: pd.Timestamp,
        regime_frame: pd.DataFrame | None = None,
    ) -> str:
        start = pd.Timestamp(test_start).normalize()
        end = pd.Timestamp(test_end).normalize()
        frame_label = self._assign_from_regime_frame(start, end, regime_frame=regime_frame)
        if frame_label is not None:
            return frame_label
        midpoint = start + (end - start) / 2
        matched = [window["label"] for window in self._event_windows if window["start"] <= midpoint <= window["end"]]
        if matched:
            for label in self.priority:
                if label in matched:
                    return label
            return matched[0]
        return self._assign_by_conditions(start, end, regime_frame=regime_frame)

    def _assign_from_regime_frame(
        self,
        test_start: pd.Timestamp,
        test_end: pd.Timestamp,
        *,
        regime_frame: pd.DataFrame | None = None,
    ) -> str | None:
        if regime_frame is None or regime_frame.empty:
            return None

        work = regime_frame.copy()
        if "date" not in work.columns:
            return None
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
        subset = work[work["date"].between(test_start, test_end)].copy()
        if subset.empty:
            return None

        for column in ["regime", "plan_regime_label", "plan_regime_id"]:
            if column not in subset.columns:
                continue
            counts = subset[column].astype(str).value_counts()
            if counts.empty:
                continue
            label = str(counts.index[0])
            if column == "plan_regime_id":
                mapping = {
                    "R1": "R1|Low-Vol Bull",
                    "R2": "R2|High-Vol Bull",
                    "R3": "R3|Low-Vol Bear",
                    "R4": "R4|High-Vol Bear",
                    "R5": "R5|Recovery",
                    "R6": "R6|Sideways",
                    "R7": "R7|Rate-Event",
                    "R8": "R8|Election/Binary",
                    "R9": "R9|External Shock",
                }
                return mapping.get(label, label)
            if column == "plan_regime_label" and "|" not in label:
                reverse_mapping = {
                    "Low-Vol Bull": "R1|Low-Vol Bull",
                    "High-Vol Bull": "R2|High-Vol Bull",
                    "Low-Vol Bear": "R3|Low-Vol Bear",
                    "High-Vol Bear": "R4|High-Vol Bear",
                    "Recovery": "R5|Recovery",
                    "Sideways": "R6|Sideways",
                    "Rate-Event": "R7|Rate-Event",
                    "Election/Binary": "R8|Election/Binary",
                    "External Shock": "R9|External Shock",
                }
                return reverse_mapping.get(label, label)
            return label
        return None

    def _assign_by_conditions(
        self,
        test_start: pd.Timestamp,
        test_end: pd.Timestamp,
        *,
        regime_frame: pd.DataFrame | None = None,
    ) -> str:
        frame_label = self._assign_from_regime_frame(test_start, test_end, regime_frame=regime_frame)
        if frame_label is not None:
            return frame_label
        return "R6|Sideways"

    def assign_all_windows(
        self,
        windows: Sequence[dict[str, Any]],
        *,
        regime_frame: pd.DataFrame | None = None,
    ) -> list[str]:
        labels = [
            self.assign_regime(pd.Timestamp(window["test_start"]), pd.Timestamp(window["test_end"]), regime_frame=regime_frame)
            for window in windows
        ]
        self._validate_distribution(labels)
        return labels

    def apply_window_regimes(
        self,
        regime_frame: pd.DataFrame,
        windows: Sequence[dict[str, Any]],
        *,
        labels: Sequence[str] | None = None,
        source_layer: str = "run_config_window_assignment",
    ) -> pd.DataFrame:
        work = regime_frame.copy()
        if work.empty:
            return work
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
        runtime_labels = list(labels or self.assign_all_windows(windows, regime_frame=work))
        for window, label in zip(windows, runtime_labels, strict=False):
            start = pd.Timestamp(window["test_start"]).normalize()
            end = pd.Timestamp(window["test_end"]).normalize()
            mask = work["date"].between(start, end)
            if not mask.any():
                continue
            regime_id, regime_name = (label.split("|", 1) + [label])[:2] if "|" in label else (label, label)
            work.loc[mask, "plan_regime_id"] = regime_id
            work.loc[mask, "plan_regime_label"] = regime_name
            work.loc[mask, "regime"] = label
            work.loc[mask, "source_layer"] = source_layer
            work.loc[mask, "window_id"] = int(window.get("window_id", 0) or 0)
        return work.sort_values("date", kind="mergesort").reset_index(drop=True)

    def _validate_distribution(self, labels: Sequence[str]) -> None:
        counts = Counter(str(label) for label in labels)
        r7_r8_count = counts.get("R7|Rate-Event", 0) + counts.get("R8|Election/Binary", 0)
        max_allowed = int(self.validation.get("max_r7_r8_windows", 6) or 6)
        warn_at = int(self.validation.get("warn_if_r7_r8_exceeds", 4) or 4)
        total = max(1, len(labels))

        if r7_r8_count > max_allowed:
            raise ValueError(
                f"REGIME CONFIG ERROR: {r7_r8_count} windows assigned to R7/R8; "
                f"max allowed is {max_allowed}. Check regime_config.yaml boundaries."
            )
        if r7_r8_count > warn_at:
            print(f"[RegimeAssigner] WARNING: {r7_r8_count} R7/R8 windows exceeds warning threshold {warn_at}")
        print(f"[RegimeAssigner] R7+R8 total: {r7_r8_count} windows ({100.0 * r7_r8_count / total:.0f}%)")

    def get_exposure_cap(self, regime_label: str) -> float:
        return float(self.caps.get(regime_label, self.caps.get("default", 0.40)))


__all__ = ["RegimeAssigner"]
