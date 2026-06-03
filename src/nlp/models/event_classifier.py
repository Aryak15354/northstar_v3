"""Event-type classification for Indian financial headlines."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.nlp.models.model_registry import NLPModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class EventClassification:
    event_type: str
    confidence: float
    is_company_event: bool
    is_macro_event: bool
    expected_direction: str
    materiality: str
    pit_lag_days: int
    rule_based: bool


RULE_PATTERNS = [
    (r"\b(rbi|reserve bank|central bank).{0,40}\b(keeps?|holds?|unchanged|pause|status quo)\b.{0,20}\b(repo|rate|policy)\b", "neutral_corporate", "neutral", "medium", 0),
    (r"\b(rbi|reserve bank|central bank).{0,40}\b(raises?|raised|hikes?|hiked|tightens?|tightened|hawkish)\b.{0,40}\b(repo|interest|rate|policy)\b", "macro_rate_hike", "negative", "high", 0),
    (r"\b(repo|interest) rate\b.{0,15}\b(raised|hiked|increased)\b", "macro_rate_hike", "negative", "high", 0),
    (r"\b(rbi|reserve bank|central bank).{0,40}\b(cuts?|cut|reduces?|reduced|lowers?|lowered|eases?|eased|dovish)\b.{0,40}\b(repo|interest|rate|policy)\b", "macro_rate_cut", "positive", "high", 0),
    (r"\b(repo|interest) rate\b.{0,15}\b(cut|reduced|lowered)\b", "macro_rate_cut", "positive", "high", 0),
    (r"\b(q[1-4]|quarterly|annual|fy\d{2}|results?)\b.{0,30}\b(beat|beats|beating|surges?|rises?|jumps?|record|strong)\b", "earnings_beat", "positive", "high", 0),
    (r"\b(net profit|profit|pat|revenue|sales)\b.{0,20}\b(beat|beats|surges?|rises?|grows?|jumps?)\b", "earnings_beat", "positive", "high", 0),
    (r"\b(net profit|profit|pat|revenue|sales)\b.{0,20}\b(miss|misses|falls?|drops?|declines?|down)\b", "earnings_miss", "negative", "high", 0),
    (r"\b(appoints?|names?)\b.{0,25}\b(ceo|md|chairman|cfo)\b", "management_change_positive", "positive", "medium", 0),
    (r"\b(ceo|md|chairman|cfo)\b.{0,25}\b(resigns?|quits?|steps down|arrested|removed|exits?)\b", "management_change_negative", "negative", "medium", 0),
    (r"\b(fraud|scam|embezzlement|accounting irregularit|financial irregularit)\w*", "fraud_allegation", "negative", "high", 0),
    (r"\b(sebi|rbi|ed|cbi)\b.{0,30}\b(probe|probes|investigation|notice|order|action)\b", "regulatory_action_negative", "negative", "high", 0),
    (r"\b(sebi|rbi|government|licen[cs]e)\b.{0,30}\b(approves?|approved|clears?|cleared|grants?|granted)\b", "regulatory_action_positive", "positive", "medium", 0),
    (r"\b(acquires?|acquisition|merger|takeover|buys?\s+stake)\b", "merger_acquisition", "unknown", "high", 0),
    (r"\b(restructuring|debt recast|debt restructuring|refinancing)\b", "debt_restructuring", "unknown", "medium", 1),
    (r"\bpromoter\b.{0,20}\bpledge\b.{0,20}\b(increase|increases|up|rises?)\b", "promoter_pledge_increase", "negative", "medium", 2),
    (r"\bpromoter\b.{0,20}\bpledge\b.{0,20}\b(decrease|decreases|reduced|falls?|down)\b", "promoter_pledge_decrease", "positive", "low", 2),
    (r"\b(wins?|bags?|secures?)\b.{0,50}\b(order|contract|deal)\b", "order_win", "positive", "medium", 0),
    (r"\b(loses?|loss of)\b.{0,30}\b(order|contract|deal)\b", "order_loss", "negative", "medium", 0),
    (r"\b(capex|capital expenditure|expansion)\b.{0,30}\b(plan|plans|announce|announces|invest|investment)\b", "capex_announcement", "positive", "medium", 0),
    (r"\b(dividend)\b.{0,20}\b(announce|announces|declares?|declared|payout)\b", "dividend_announcement", "positive", "low", 0),
    (r"\b(buyback|share repurchase)\b", "buyback_announcement", "positive", "medium", 0),
    (r"\b(cpi|inflation)\b.{0,20}\b(rises?|higher|hotter|accelerates?|above)\b", "macro_inflation_high", "negative", "medium", 0),
    (r"\b(cpi|inflation)\b.{0,20}\b(falls?|cools?|lower|below|softens?)\b", "macro_inflation_low", "positive", "medium", 0),
    (
        r"\b(fii|fpi|foreign investor)s?\b.{0,40}\b("
        r"outflow|sell|selling|sells?|withdraw|withdrawal|net sellers?|"
        r"pull|pulls?|dump|dumping"
        r")\b",
        "macro_fii_outflow",
        "negative",
        "high",
        0,
    ),
    (
        r"\b(fii|fpi|foreign investor)s?\b.{0,40}\b("
        r"inflow|buy|buying|buys?|purchase|purchases?|net buyers?|"
        r"add|adds?|accumulate|accumulation"
        r")\b",
        "macro_fii_inflow",
        "positive",
        "high",
        0,
    ),
    (r"\b(crude|oil|brent|wti)\b.{0,30}\b(spike|spikes|spiked|surge|surges|jump|jumps|higher)\b", "macro_crude_spike", "negative", "high", 0),
    (r"\b(hormuz|strait|tanker route|shipping lane|blockade|missile|airstrike|war|military action|pipeline)\b", "macro_geopolitical", "negative", "high", 0),
]
COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), event_type, direction, materiality, lag)
    for pattern, event_type, direction, materiality, lag in RULE_PATTERNS
]


class EventClassifier:
    """Rule-first event classifier with optional model fallback."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._registry = NLPModelRegistry(self._config)
        self._model_pipeline = None

    def classify(self, text: str) -> EventClassification:
        if not text or len(str(text).strip()) < 3:
            return self._neutral_result(0.0)
        headline = str(text).strip()
        rule_result = self._rule_based_classify(headline)
        if rule_result is not None and rule_result.confidence >= 0.85:
            return rule_result
        try:
            model_result = self._model_classify(headline)
        except Exception as exc:
            logger.debug("Event model fallback engaged: %s", exc)
            model_result = self._heuristic_model_classify(headline)

        if rule_result is None:
            return model_result
        return model_result if model_result.confidence > rule_result.confidence else rule_result

    def _rule_based_classify(self, text: str) -> EventClassification | None:
        for pattern, event_type, direction, materiality, lag in COMPILED_PATTERNS:
            if not pattern.search(text):
                continue
            is_macro = event_type.startswith("macro_")
            return EventClassification(
                event_type=event_type,
                confidence=0.88 if event_type != "neutral_corporate" else 0.86,
                is_company_event=not is_macro,
                is_macro_event=is_macro,
                expected_direction=direction,
                materiality=materiality,
                pit_lag_days=lag,
                rule_based=True,
            )
        return None

    def _model_classify(self, text: str) -> EventClassification:
        if self._model_pipeline is None:
            self._load_model_pipeline()
        if self._model_pipeline is None:
            return self._heuristic_model_classify(text)
        result = self._model_pipeline(text, truncation=True, max_length=256)
        top = result[0] if isinstance(result, list) else result
        label = str(top.get("label", "unknown")).strip()
        confidence = float(top.get("score", 0.55))
        return self._metadata(label, confidence, rule_based=False)

    def _heuristic_model_classify(self, text: str) -> EventClassification:
        normalized = text.lower()
        if any(token in normalized for token in ("quarter", "q1", "q2", "q3", "q4", "result")) and any(
            token in normalized for token in ("beat", "beats", "record", "strong")
        ):
            return self._metadata("earnings_beat", 0.74, rule_based=False)
        if any(token in normalized for token in ("quarter", "q1", "q2", "q3", "q4", "result")) and any(
            token in normalized for token in ("miss", "weak", "fall", "drop")
        ):
            return self._metadata("earnings_miss", 0.74, rule_based=False)
        if "tightens monetary policy" in normalized or "hawkish stance" in normalized:
            return self._metadata("macro_rate_hike", 0.72, rule_based=False)
        if "eases monetary policy" in normalized or "dovish stance" in normalized:
            return self._metadata("macro_rate_cut", 0.72, rule_based=False)
        if any(token in normalized for token in ("order", "contract")) and any(token in normalized for token in ("wins", "bags", "secures")):
            return self._metadata("order_win", 0.68, rule_based=False)
        if any(token in normalized for token in ("fraud", "irregularit", "probe")):
            return self._metadata("fraud_allegation", 0.70, rule_based=False)
        if any(token in normalized for token in ("blockade", "tanker", "shipping lane", "strait")):
            return self._metadata("macro_geopolitical", 0.69, rule_based=False)
        return self._neutral_result(0.5, rule_based=False)

    def _load_model_pipeline(self) -> None:
        spec = self._registry.event_model()
        if spec.name == "zero_shot" and not bool(self._config.get("nlp", {}).get("models", {}).get("event_classifier", {}).get("allow_remote_download", False)):
            raise RuntimeError("local event-classifier weights not found")
        if spec.name == "zero_shot":
            self._model_pipeline = _ZeroShotWrapper()
            return
        try:
            from transformers import pipeline
            import torch
            device = 0 if torch.cuda.is_available() else -1
        except ImportError as exc:
            raise RuntimeError("transformers/torch not installed") from exc
        self._model_pipeline = pipeline("text-classification", model=spec.path, top_k=1, device=device)

    def _metadata(self, label: str, confidence: float, *, rule_based: bool) -> EventClassification:
        direction_map = {
            "earnings_beat": "positive",
            "earnings_miss": "negative",
            "management_change_positive": "positive",
            "management_change_negative": "negative",
            "fraud_allegation": "negative",
            "regulatory_action_negative": "negative",
            "regulatory_action_positive": "positive",
            "order_win": "positive",
            "order_loss": "negative",
            "capex_announcement": "positive",
            "dividend_announcement": "positive",
            "buyback_announcement": "positive",
            "macro_rate_hike": "negative",
            "macro_rate_cut": "positive",
            "macro_inflation_high": "negative",
            "macro_inflation_low": "positive",
            "macro_geopolitical": "negative",
            "macro_crude_spike": "negative",
            "macro_fii_outflow": "negative",
            "macro_fii_inflow": "positive",
            "neutral_corporate": "neutral",
            "unknown": "unknown",
        }
        materiality_map = {
            "earnings_beat": "high",
            "earnings_miss": "high",
            "fraud_allegation": "high",
            "macro_rate_hike": "high",
            "macro_rate_cut": "high",
            "macro_geopolitical": "high",
            "macro_crude_spike": "high",
            "macro_fii_outflow": "high",
            "macro_fii_inflow": "high",
            "order_win": "medium",
            "order_loss": "medium",
            "management_change_positive": "medium",
            "management_change_negative": "medium",
        }
        lag_map = {
            "promoter_pledge_increase": 2,
            "promoter_pledge_decrease": 2,
        }
        is_macro = label.startswith("macro_")
        return EventClassification(
            event_type=label,
            confidence=float(confidence),
            is_company_event=not is_macro,
            is_macro_event=is_macro,
            expected_direction=direction_map.get(label, "unknown"),
            materiality=materiality_map.get(label, "low"),
            pit_lag_days=int(lag_map.get(label, 0)),
            rule_based=rule_based,
        )

    def _neutral_result(self, confidence: float, *, rule_based: bool = True) -> EventClassification:
        return EventClassification(
            event_type="neutral_corporate",
            confidence=float(confidence),
            is_company_event=True,
            is_macro_event=False,
            expected_direction="neutral",
            materiality="low",
            pit_lag_days=0,
            rule_based=rule_based,
        )


class _ZeroShotWrapper:
    """Uses zero-shot classification when no fine-tuned event model is available."""

    LABEL_MAP = {
        "earnings beat": "earnings_beat",
        "earnings miss": "earnings_miss",
        "order win": "order_win",
        "fraud allegation": "fraud_allegation",
        "management change": "management_change_negative",
        "merger acquisition": "merger_acquisition",
        "rate hike": "macro_rate_hike",
        "rate cut": "macro_rate_cut",
        "crude oil spike": "macro_crude_spike",
        "geopolitical risk": "macro_geopolitical",
        "fii selling": "macro_fii_outflow",
    }

    def __init__(self) -> None:
        try:
            from transformers import pipeline
            import torch
            device = 0 if torch.cuda.is_available() else -1
        except ImportError as exc:
            raise RuntimeError("transformers/torch not installed") from exc
        self._pipe = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=device)
        self._labels = list(self.LABEL_MAP)

    def __call__(self, text: str, **_: Any) -> list[dict[str, Any]]:
        result = self._pipe(text, self._labels)
        label = self.LABEL_MAP.get(result["labels"][0], "unknown")
        return [{"label": label, "score": float(result["scores"][0])}]
