import json

from arya.data.corpus_stats import CorpusHealthGate
from arya.data.corpus_builder import build_clean_corpus, split_corpus
from arya.data.provenance import ManifestWriter, write_text_document
from arya.data.scrapers.news_scraper import NewsScraper
from arya.data.scrapers.rbi_scraper import RBIScraper
from arya.data.scrapers.sebi_scraper import SEBIScraper
from arya.data.scrapers.wikipedia_scraper import WikipediaScraper
from arya.eval.gates import benchmark_gate, corpus_gate, pretraining_log_gate


RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Market update</title><link>https://example.com/a</link><description>RBI and SEBI market article with enough finance words for a useful corpus document.</description><pubDate>Wed, 29 Apr 2026 10:00:00 GMT</pubDate></item>
</channel></rss>
"""


class FakeClient:
    def __init__(self, text="", payload=None):
        self.text = text
        self.payload = payload or {}

    def get_text(self, url, **kwargs):
        return self.text

    def get_json(self, url, **kwargs):
        return self.payload


def test_provenance_manifest_and_clean_split(tmp_path):
    raw = tmp_path / "raw"
    write_text_document(raw, "rbi", "RBI doc", "RBI monetary liquidity policy corpus sentence " * 20, url="https://rbi.example/doc")
    write_text_document(raw, "northstar_corpus", "State doc", "Northstar regime portfolio state corpus sentence " * 20, url="file://state")
    write_text_document(raw, "filings", "Filing doc", "NSE company filing EBITDA shareholder corpus sentence " * 20, url="https://nse.example/doc")

    docs = ManifestWriter(raw / "manifest.jsonl").read_all()
    assert len(docs) == 3
    assert docs[0].sha256

    result = build_clean_corpus(raw, tmp_path / "clean", min_words=10)
    assert result.written_docs == 3
    counts = split_corpus(tmp_path / "clean", tmp_path / "split", val_fraction=0.5)
    assert counts["train"] + counts["val"] == 3


def test_sebi_and_news_collectors_from_rss_fixture(tmp_path):
    sebi = SEBIScraper(tmp_path / "sebi", client=FakeClient(RSS_FIXTURE), fetch_articles=False)
    news = NewsScraper(
        tmp_path / "news",
        feeds={"fixture": "https://example.com/rss"},
        client=FakeClient(RSS_FIXTURE),
        fetch_articles=False,
    )
    assert sebi.collect_rss(limit=1) == 1
    assert news.collect(per_feed_limit=1) == 1
    assert len(list((tmp_path / "sebi" / "sebi").glob("*.txt"))) == 1
    assert len(list((tmp_path / "news" / "news").glob("*.txt"))) == 1


def test_rbi_press_release_link_parser(tmp_path):
    html = """
    <html><body>
      <a href="BS_PressReleaseDisplay.aspx?prid=123">Money Market Operations</a>
      <a href="BS_PressReleaseDisplay.aspx?prid=123">Duplicate</a>
    </body></html>
    """
    scraper = RBIScraper(tmp_path)
    links = scraper.press_release_links(html)
    assert links == [("Money Market Operations", "https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=123")]


def test_rbi_notification_link_parser(tmp_path):
    html = """
    <html><body>
      <a href="NotificationUser.aspx?Id=123">Circular on banks</a>
      <a href="NotificationUser.aspx?Id=123">Duplicate</a>
    </body></html>
    """
    scraper = RBIScraper(tmp_path)
    links = scraper.notification_links(html)
    assert links == [("Circular on banks", "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=123")]


def test_wikipedia_collector_with_fake_api(tmp_path):
    payload = {
        "query": {
            "pages": {
                "1": {
                    "title": "Reserve Bank of India",
                    "extract": "Reserve Bank of India central bank monetary policy finance " * 20,
                    "fullurl": "https://en.wikipedia.org/wiki/Reserve_Bank_of_India",
                    "pageid": 1,
                }
            }
        }
    }
    scraper = WikipediaScraper(tmp_path, topics=["Reserve Bank of India"], client=FakeClient(payload=payload))
    assert scraper.collect() == 1
    assert len(list((tmp_path / "wikipedia").glob("*.txt"))) == 1


def test_production_gate_helpers(tmp_path):
    corpus = tmp_path / "corpus"
    for source in ("rbi", "northstar_corpus", "filings"):
        source_dir = corpus / source
        source_dir.mkdir(parents=True)
        (source_dir / "doc.txt").write_text("finance market corpus word " * 30)
    result = corpus_gate(
        corpus,
        gate=CorpusHealthGate(min_est_tokens=1, min_avg_doc_words=1, max_source_fraction=0.67),
    )
    assert result.passed

    log = tmp_path / "log.jsonl"
    log.write_text('{"ppl": 20.0}\n{"ppl": 18.0}\n')
    assert pretraining_log_gate(log).passed

    report = tmp_path / "bench.json"
    report.write_text(
        json.dumps(
            {
                "finance_qa_accuracy": 0.8,
                "nil_accuracy": 0.85,
                "json_schema_success": 1.0,
                "ticker_validity": 0.99,
                "number_plausibility": 0.95,
                "critical_safety_failures": 0,
            }
        )
    )
    assert benchmark_gate(report).passed
