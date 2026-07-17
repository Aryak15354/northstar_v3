from src.nlp.models.india_financial_ner import IndiaFinancialNER


def test_india_financial_ner_extracts_known_company_alias() -> None:
    entities = IndiaFinancialNER().extract_entities("Infosys wins a large cloud migration order")

    tickers = {entity.canonical_ticker for entity in entities}
    assert "INFY" in tickers
