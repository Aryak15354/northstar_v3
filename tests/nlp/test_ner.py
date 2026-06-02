from __future__ import annotations

from src.nlp.models.india_financial_ner import IndiaFinancialNER


def test_ticker_extraction_from_headline():
    ner = IndiaFinancialNER({})
    entities = ner.extract_entities("HDFCBANK rises 3% after strong quarterly results")
    assert any(entity.canonical_ticker == "HDFCBANK" for entity in entities)


def test_company_name_to_ticker_resolution():
    ner = IndiaFinancialNER({})
    entities = ner.extract_entities("HDFC Bank rises 3%")
    assert any(entity.canonical_ticker == "HDFCBANK" for entity in entities)


def test_company_alias_resolution():
    ner = IndiaFinancialNER({})
    entities = ner.extract_entities("Reliance Industries announces capex")
    assert any(entity.canonical_ticker == "RELIANCE" for entity in entities)


def test_promoter_to_company():
    ner = IndiaFinancialNER({})
    entities = ner.extract_entities("Mukesh Ambani increases stake")
    assert any(entity.canonical_ticker == "RELIANCE" for entity in entities)


def test_multiple_companies_in_one_headline():
    ner = IndiaFinancialNER({})
    entities = ner.extract_entities("TCS wins order from HDFC Bank")
    tickers = {entity.canonical_ticker for entity in entities if entity.canonical_ticker}
    assert {"TCS", "HDFCBANK"}.issubset(tickers)


def test_unknown_company_handled_gracefully():
    ner = IndiaFinancialNER({})
    entities = ner.extract_entities("XYZ Corp announces results")
    assert any(entity.entity_type == "ORG" for entity in entities)
