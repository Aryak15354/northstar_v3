"""Production readiness gates for Arya artifacts."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

from tokenizers import Tokenizer

from arya.data.corpus_stats import CorpusHealthGate, analyse_corpus, validate_corpus_health
from arya.tokeniser.constants import SPECIAL_TOKENS, VOCAB_SIZE


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    failures: list[str]
    metrics: dict

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "failures": self.failures,
            "metrics": self.metrics,
        }


def corpus_gate(corpus_dir: str | Path, gate: CorpusHealthGate | None = None) -> GateResult:
    stats = analyse_corpus(corpus_dir)
    failures = validate_corpus_health(stats, gate)
    return GateResult("corpus", not failures, failures, stats)


def tokeniser_gate(
    tokeniser_path: str | Path,
    heldout_texts: list[str] | None = None,
    vocab_size: int = VOCAB_SIZE,
    min_coverage: float = 0.98,
) -> GateResult:
    failures: list[str] = []
    tok = Tokenizer.from_file(str(tokeniser_path))
    metrics = {"vocab_size": tok.get_vocab_size()}
    if tok.get_vocab_size() != vocab_size:
        failures.append(f"Expected vocab size {vocab_size}, found {tok.get_vocab_size()}.")
    vocab = tok.get_vocab()
    for i, token in enumerate(SPECIAL_TOKENS):
        if token not in vocab:
            failures.append(f"Missing special token {token}.")
        elif i == 0 and vocab[token] != 0:
            failures.append(f"Expected {token} id 0, found {vocab[token]}.")

    fertility_terms = ["NIFTY", "BANKNIFTY", "crore", "lakh", "SEBI", "MPC", "EBITDA", "NPA", "NBFC"]
    fertility = {term: len(tok.encode(term).ids) for term in fertility_terms}
    metrics["fertility"] = fertility
    bad_terms = {term: count for term, count in fertility.items() if count > 2}
    if bad_terms:
        failures.append(f"Finance term fertility above 2: {bad_terms}.")

    if heldout_texts:
        unk_id = tok.token_to_id("<|unk|>")
        total = 0
        unk = 0
        for text in heldout_texts:
            ids = tok.encode(text).ids
            total += len(ids)
            unk += ids.count(unk_id) if unk_id is not None else 0
        coverage = 1.0 if total == 0 else 1 - (unk / total)
        metrics["coverage"] = coverage
        if coverage < min_coverage:
            failures.append(f"Coverage {coverage:.3%} below {min_coverage:.1%}.")
    return GateResult("tokeniser", not failures, failures, metrics)


def pretraining_log_gate(log_path: str | Path, max_ppl: float = 25.0) -> GateResult:
    rows = _read_jsonl(log_path)
    ppl_values = [row["ppl"] for row in rows if "ppl" in row]
    failures: list[str] = []
    metrics = {"eval_points": len(ppl_values)}
    if not ppl_values:
        failures.append("No perplexity values found in training log.")
    else:
        last = ppl_values[-5:]
        avg_ppl = sum(last) / len(last)
        metrics["avg_last_ppl"] = avg_ppl
        if not math.isfinite(avg_ppl) or avg_ppl >= max_ppl:
            failures.append(f"Average last perplexity {avg_ppl:.2f} is not below {max_ppl}.")
    return GateResult("pretraining_log", not failures, failures, metrics)


def benchmark_gate(report_path: str | Path) -> GateResult:
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    failures: list[str] = []
    thresholds = {
        "finance_qa_accuracy": 0.70,
        "nil_accuracy": 0.80,
        "json_schema_success": 1.0,
        "ticker_validity": 0.95,
        "number_plausibility": 0.90,
    }
    for metric, threshold in thresholds.items():
        value = payload.get(metric)
        if value is None:
            failures.append(f"Missing benchmark metric {metric}.")
        elif value < threshold:
            failures.append(f"{metric}={value:.3f} below threshold {threshold:.3f}.")
    if payload.get("critical_safety_failures", 1) != 0:
        failures.append(f"Critical safety failures: {payload.get('critical_safety_failures')}.")
    return GateResult("benchmark", not failures, failures, payload)


def _read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Arya production gates.")
    sub = parser.add_subparsers(dest="command", required=True)
    corpus = sub.add_parser("corpus")
    corpus.add_argument("corpus_dir", type=Path)
    corpus.add_argument("--min-tokens", type=int, default=CorpusHealthGate.min_est_tokens)
    corpus.add_argument("--min-avg-doc-words", type=int, default=CorpusHealthGate.min_avg_doc_words)

    tokeniser = sub.add_parser("tokeniser")
    tokeniser.add_argument("tokeniser_path", type=Path)
    tokeniser.add_argument("--vocab-size", type=int, default=VOCAB_SIZE)

    pretrain = sub.add_parser("pretraining-log")
    pretrain.add_argument("log_path", type=Path)
    pretrain.add_argument("--max-ppl", type=float, default=25.0)

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("report_path", type=Path)

    args = parser.parse_args()
    if args.command == "corpus":
        result = corpus_gate(
            args.corpus_dir,
            CorpusHealthGate(min_est_tokens=args.min_tokens, min_avg_doc_words=args.min_avg_doc_words),
        )
    elif args.command == "tokeniser":
        result = tokeniser_gate(args.tokeniser_path, vocab_size=args.vocab_size)
    elif args.command == "pretraining-log":
        result = pretraining_log_gate(args.log_path, max_ppl=args.max_ppl)
    else:
        result = benchmark_gate(args.report_path)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

