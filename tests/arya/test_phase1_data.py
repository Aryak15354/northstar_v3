import json

from arya.data.cleaner import FinancialTextCleaner
from arya.data.corpus_stats import CorpusHealthGate, analyse_corpus, validate_corpus_health
from arya.data.northstar_exporter import NorthstarCorpusExporter
from arya.data.scrapers.nse_filing_scraper import NSEFilingScraper


def test_phase1_cleaner_removes_noise_and_duplicates():
    cleaner = FinancialTextCleaner(min_words=5)
    raw = "<html><body>RBI policy text with 1,000 crore liquidity support for banks.</body></html>"
    cleaned = cleaner.clean(raw)
    assert cleaned is not None
    assert "<html>" not in cleaned
    assert "1000 crore" in cleaned
    assert cleaner.clean(raw) is None


def test_phase1_corpus_stats_and_health_gate(tmp_path):
    rbi = tmp_path / "corpus" / "rbi"
    northstar = tmp_path / "corpus" / "northstar_corpus"
    filings = tmp_path / "corpus" / "filings"
    rbi.mkdir(parents=True)
    northstar.mkdir(parents=True)
    filings.mkdir(parents=True)
    text = "RBI market policy and liquidity text " * 30
    (rbi / "a.txt").write_text(text)
    (northstar / "b.txt").write_text("Northstar state regime portfolio risk " * 30)
    (filings / "c.txt").write_text("Company filing results shareholder EBITDA " * 30)

    stats = analyse_corpus(tmp_path / "corpus")
    gate = CorpusHealthGate(min_est_tokens=10, min_avg_doc_words=10, max_source_fraction=0.67)
    assert validate_corpus_health(stats, gate) == []


def test_phase1_northstar_exporter_exports_state(tmp_path):
    root = tmp_path / "northstar"
    root.mkdir()
    state = {
        "regime_state": {"current_regime": "EXPANSION", "caution_score": 0.2},
        "portfolio": {"gross_equity_exposure": 0.7},
        "market_state": {"india_vix": 13.5},
    }
    (root / "unified_state_sample.json").write_text(json.dumps(state))

    exporter = NorthstarCorpusExporter(root, tmp_path / "out")
    count = exporter.export_unified_states()
    exported_files = list((tmp_path / "out" / "northstar_corpus").glob("*.txt"))
    assert count == 1
    assert exported_files
    assert "EXPANSION" in exported_files[0].read_text()
    assert (tmp_path / "out" / "manifest.jsonl").exists()


def test_phase1_nse_scraper_normalises_dates(tmp_path):
    scraper = NSEFilingScraper(tmp_path, delay_sec=0)
    assert scraper._normalise_date("2026-04-29") == "29-04-2026"
    assert scraper._normalise_date("29-04-2026") == "29-04-2026"
