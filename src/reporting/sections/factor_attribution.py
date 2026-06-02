"""Weekly factor attribution section."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd

from src.reporting.common import (
    PROJECT_ROOT,
    SectionResult,
    factor_columns,
    latest_research_factor_frame,
    num_text,
    read_json_candidates,
    read_parquet_candidates,
    render_note,
    trailing_factor_ics,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import (
    HTMLRenderer,
    render_bar_chart_horizontal,
    render_chart_block,
    render_metric_grid,
    render_table,
)


SECTION_NAME = "factor_attribution"
SECTION_TITLE = "Factor Attribution Report"


FACTOR_PATTERNS = {
    "bab": ("bab_", "beta"),
    "amihud": ("amihud", "liquidity"),
    "piotroski": ("piotroski",),
    "max_lottery": ("max_lottery", "lottery"),
    "earnings_quality": ("earnings_quality", "accrual", "roe", "margin", "quality"),
}


def _aggregate_importance(feature_importance: dict[str, float]) -> dict[str, float]:
    buckets = {key: 0.0 for key in FACTOR_PATTERNS}
    for feature, value in feature_importance.items():
        lowered = feature.lower()
        matched = False
        for family, patterns in FACTOR_PATTERNS.items():
            if any(pattern in lowered for pattern in patterns):
                buckets[family] += float(value)
                matched = True
                break
        if not matched:
            continue
    return buckets


def build_section(report_date: date) -> SectionResult:
    try:
        scores = read_parquet_candidates(["data/processed/scores.parquet"])
        current_regime = str(scores.iloc[0].get("regime", "")) if not scores.empty else ""
        registry = read_json_candidates(["models/regime_models/regime_model_registry.json"])
        models = registry.get("models", {})
        if not isinstance(models, dict) or not models:
            raise KeyError("Regime model registry is empty")

        current_model = models.get(current_regime) or next(iter(models.values()))
        current_importance = _aggregate_importance(current_model.get("feature_importance", {}))
        avg_importance = pd.DataFrame([_aggregate_importance(model.get("feature_importance", {})) for model in models.values()]).mean().to_dict()

        chart = render_bar_chart_horizontal(
            list(current_importance.keys()),
            [round(current_importance[key] * 100.0, 3) for key in current_importance],
            width=560,
            height=180,
            color_fn=lambda value: "#388bfd",
        )

        research = latest_research_factor_frame(report_date)
        target_col = "forward_return_5d__realized" if research["forward_return_5d__realized"].notna().any() else "forward_return_5d"
        ic_rows = []
        for factor_name, candidates in factor_columns().items():
            factor_col = next((col for col in candidates if col in research.columns), None)
            if factor_col is None:
                continue
            ic_4w, ic_12w = trailing_factor_ics(research, factor_col, target_col)
            ic_rows.append(
                {
                    "Factor": factor_name,
                    "Current Regime Weight": f"{current_importance.get(factor_name, 0.0) * 100.0:.2f}",
                    "All-Regime Avg": f"{avg_importance.get(factor_name, 0.0) * 100.0:.2f}",
                    "IC 4W": num_text(ic_4w, digits=3, signed=True),
                    "IC 12W": num_text(ic_12w, digits=3, signed=True),
                    "Trend": "STRENGTHENING" if (ic_4w or -999.0) > (ic_12w or -999.0) else "DECAYING",
                }
            )

        top_contributors = scores.nlargest(3, "final_score")[["ticker", "final_score", "model_score", "sector"]].copy()
        top_contributors["Final Score"] = top_contributors["final_score"].map(lambda x: f"{float(x):.4f}")
        top_contributors["Model Score"] = top_contributors["model_score"].map(lambda x: f"{float(x):.4f}")
        top_contributors = top_contributors.drop(columns=["final_score", "model_score"]).rename(columns={"ticker": "Ticker", "sector": "Sector"})

        metrics = render_metric_grid(
            [
                ("Current regime", current_model.get("regime", current_regime or "unknown"), "Live scoring regime"),
                ("Backend", str(current_model.get("backend", "unknown")), None),
                ("Feature count", str(len(current_model.get("feature_cols", []) or [])), None),
                ("Train IC", num_text(current_model.get("train_ic"), digits=3), "Model registry"),
            ]
        )
        body = metrics + render_chart_block("Mean feature-family importance in current regime model", chart)
        body += render_table(pd.DataFrame(ic_rows))
        body += "<h3>Top score contributors this week</h3>" + render_table(top_contributors)
        body += render_note("When a dedicated SHAP parquet is absent, this section falls back to live regime-model feature importance aggregated into the core factor families.")
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="ok",
            badge="OK",
            summary=f"Factor attribution is anchored to the {current_model.get('regime', current_regime or 'unknown')} regime model.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
