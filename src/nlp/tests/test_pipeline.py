from datetime import datetime

from src.nlp.pipeline.news_nlp_pipeline import NewsNLPPipeline


def test_news_nlp_pipeline_processes_single_document() -> None:
    pipeline = NewsNLPPipeline(
        {
            "nlp": {
                "models": {
                    "sentiment": {"allow_remote_download": False},
                    "event_classifier": {"allow_remote_download": False},
                    "ner": {"allow_remote_download": False},
                }
            }
        }
    )

    result = pipeline.process_document(
        "TCS wins large order after strong Q3 results",
        ticker="TCS.NS",
        published_at=datetime(2026, 1, 2, 9, 0),
        source="test",
    )

    assert result is not None
    assert result.resolved_tickers[0] == "TCS"
    assert result.availability_date is not None
    assert result.event is not None
