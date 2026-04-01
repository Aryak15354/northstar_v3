"""Named entity recognition tuned for Indian financial headlines."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.nlp.models.model_registry import NLPModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    text: str
    entity_type: str
    canonical_ticker: str | None = None
    canonical_name: str | None = None
    confidence: float = 0.0
    start_char: int = 0
    end_char: int = 0


class IndiaFinancialNER:
    """Rule-first NER with optional transformer backfill."""

    INDIA_COMPANY_ALIASES = {
        "hdfc bank": "HDFCBANK",
        "hdfcbank": "HDFCBANK",
        "icici bank": "ICICIBANK",
        "icici": "ICICIBANK",
        "sbi": "SBIN",
        "state bank of india": "SBIN",
        "axis bank": "AXISBANK",
        "kotak bank": "KOTAKBANK",
        "kotak": "KOTAKBANK",
        "bajaj finance": "BAJFINANCE",
        "tcs": "TCS",
        "tata consultancy services": "TCS",
        "infosys": "INFY",
        "infy": "INFY",
        "hcl tech": "HCLTECH",
        "hcl technologies": "HCLTECH",
        "wipro": "WIPRO",
        "ltimindtree": "LTIM",
        "lti": "LTIM",
        "reliance": "RELIANCE",
        "reliance industries": "RELIANCE",
        "ril": "RELIANCE",
        "tata motors": "TATAMOTORS",
        "adani": "ADANIENT",
        "adani ports": "ADANIPORTS",
        "adani green": "ADANIGREEN",
        "sun pharma": "SUNPHARMA",
        "dr reddys": "DRREDDY",
        "dr reddy": "DRREDDY",
        "cipla": "CIPLA",
        "divi": "DIVISLAB",
        "maruti": "MARUTI",
        "maruti suzuki": "MARUTI",
        "mahindra": "M&M",
        "m&m": "M&M",
        "bajaj auto": "BAJAJ-AUTO",
        "ongc": "ONGC",
        "bpcl": "BPCL",
        "hpcl": "HPCL",
        "gail": "GAIL",
        "l&t": "LT",
        "larsen and toubro": "LT",
        "ntpc": "NTPC",
        "power grid": "POWERGRID",
    }
    PROMOTER_ALIASES = {
        "mukesh ambani": "RELIANCE",
        "gautam adani": "ADANIENT",
        "narayana murthy": "INFY",
        "n r narayana murthy": "INFY",
        "azim premji": "WIPRO",
        "uday kotak": "KOTAKBANK",
        "deepak parekh": "HDFCBANK",
    }

    def __init__(self, config: dict[str, Any] | None = None, ticker_master_path: str = "data/canonical/reference/ticker_master.parquet") -> None:
        self._config = config or {}
        self._ticker_master_path = Path(ticker_master_path)
        self._ner_pipeline = None
        self._registry = NLPModelRegistry(self._config)
        self._ticker_to_name: dict[str, str] = {}
        self._name_to_ticker: dict[str, str] = {}
        self._alias_map = dict(self.INDIA_COMPANY_ALIASES)
        self._load_ticker_master()

    def extract_entities(self, text: str) -> list[ExtractedEntity]:
        if not text or len(str(text).strip()) < 3:
            return []
        entities = []
        entities.extend(self._rule_based_extraction(str(text)))
        entities.extend(self._regex_company_extraction(str(text), entities))
        try:
            entities.extend(self._model_based_extraction(str(text), entities))
        except Exception as exc:
            logger.debug("Skipping transformer NER path: %s", exc)
        return self._deduplicate_entities(entities)

    def _load_ticker_master(self) -> None:
        if not self._ticker_master_path.exists():
            return
        try:
            master = pd.read_parquet(self._ticker_master_path)
        except Exception as exc:
            logger.warning("Could not read ticker master: %s", exc)
            return
        for _, row in master.iterrows():
            raw_symbol = str(row.get("symbol") or row.get("ticker") or "").strip()
            raw_ticker = str(row.get("ticker") or "").strip()
            symbol = self._normalize_symbol(raw_symbol or raw_ticker)
            company_name = str(row.get("company_name") or row.get("name") or "").strip()
            if symbol:
                self._ticker_to_name[symbol] = company_name or symbol
            if symbol and company_name:
                self._name_to_ticker[self._normalize_company_name(company_name)] = symbol
                self._alias_map.setdefault(self._normalize_company_name(company_name), symbol)

    def _rule_based_extraction(self, text: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        lower = text.lower()

        for match in re.finditer(r"\b[A-Z][A-Z0-9&.-]{1,20}\b", text):
            symbol = self._normalize_symbol(match.group(0))
            if symbol in self._ticker_to_name:
                entities.append(
                    ExtractedEntity(
                        text=match.group(0),
                        entity_type="ORG",
                        canonical_ticker=symbol,
                        canonical_name=self._ticker_to_name.get(symbol, symbol),
                        confidence=0.97,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )

        for alias, ticker in self._alias_map.items():
            pattern = rf"\b{re.escape(alias)}\b"
            for match in re.finditer(pattern, lower):
                entities.append(
                    ExtractedEntity(
                        text=text[match.start() : match.end()],
                        entity_type="ORG",
                        canonical_ticker=ticker,
                        canonical_name=self._ticker_to_name.get(ticker, ticker),
                        confidence=0.92,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )

        for promoter, ticker in self.PROMOTER_ALIASES.items():
            pattern = rf"\b{re.escape(promoter)}\b"
            for match in re.finditer(pattern, lower):
                entities.append(
                    ExtractedEntity(
                        text=text[match.start() : match.end()],
                        entity_type="PERSON",
                        canonical_ticker=ticker,
                        canonical_name=self._ticker_to_name.get(ticker, ticker),
                        confidence=0.91,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )
        return entities

    def _regex_company_extraction(self, text: str, known_entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        taken = {(item.start_char, item.end_char) for item in known_entities}
        entities: list[ExtractedEntity] = []
        for match in re.finditer(r"\b([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3}\s+(?:Ltd|Limited|Bank|Industries|Corp|Corporation))\b", text):
            span = (match.start(), match.end())
            if span in taken:
                continue
            entity_text = match.group(1)
            normalized = self._normalize_company_name(entity_text)
            ticker = self._alias_map.get(normalized) or self._name_to_ticker.get(normalized)
            entities.append(
                ExtractedEntity(
                    text=entity_text,
                    entity_type="ORG",
                    canonical_ticker=ticker,
                    canonical_name=self._ticker_to_name.get(ticker, entity_text) if ticker else None,
                    confidence=0.72 if ticker else 0.55,
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )
        return entities

    def _model_based_extraction(self, text: str, known_entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        if self._ner_pipeline is None:
            self._load_ner_pipeline()
        if self._ner_pipeline is None:
            return []
        covered = {(item.start_char, item.end_char) for item in known_entities}
        entities: list[ExtractedEntity] = []
        for result in self._ner_pipeline(text):
            start = int(result.get("start", 0) or 0)
            end = int(result.get("end", 0) or 0)
            if (start, end) in covered:
                continue
            entity_type = str(result.get("entity_group") or result.get("entity") or "").upper()
            if entity_type not in {"ORG", "PERSON", "GPE", "MONEY", "PERCENT", "DATE"}:
                continue
            entity_text = str(result.get("word") or "").replace("##", "")
            ticker = None
            if entity_type == "ORG":
                normalized = self._normalize_company_name(entity_text)
                ticker = self._alias_map.get(normalized) or self._name_to_ticker.get(normalized)
            elif entity_type == "PERSON":
                ticker = self.PROMOTER_ALIASES.get(entity_text.lower())
            entities.append(
                ExtractedEntity(
                    text=entity_text,
                    entity_type=entity_type,
                    canonical_ticker=ticker,
                    canonical_name=self._ticker_to_name.get(ticker, entity_text) if ticker else None,
                    confidence=float(result.get("score", 0.65)),
                    start_char=start,
                    end_char=end,
                )
            )
        return entities

    def _load_ner_pipeline(self) -> None:
        spec = self._registry.ner_model()
        if spec.source != "local" and not bool(self._config.get("nlp", {}).get("models", {}).get("ner", {}).get("allow_remote_download", False)):
            raise RuntimeError("local NER weights not found")
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("transformers is not installed") from exc
        try:
            import torch
            device = 0 if torch.cuda.is_available() else -1
        except ImportError:
            device = -1
        self._ner_pipeline = pipeline("ner", model=spec.path, aggregation_strategy="simple", device=device)

    def _deduplicate_entities(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        deduped: list[ExtractedEntity] = []
        seen: set[tuple[str, str, int, int]] = set()
        for entity in sorted(entities, key=lambda item: (-float(item.confidence), item.start_char, item.end_char)):
            key = (
                entity.entity_type,
                entity.canonical_ticker or entity.text.lower(),
                int(entity.start_char),
                int(entity.end_char),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return deduped

    @staticmethod
    def _normalize_symbol(value: str) -> str:
        return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()

    @staticmethod
    def _normalize_company_name(name: str) -> str:
        value = str(name or "").lower()
        value = re.sub(r"\b(limited|ltd|inc|corp|corporation|industries|industry|company|co|india|ind)\b", " ", value)
        value = value.replace("&", " and ")
        value = re.sub(r"[^a-z0-9 ]+", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value
