"""Operator CLI for the Arya production pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arya.data.corpus_builder import build_clean_corpus, split_corpus
from arya.data.corpus_stats import CorpusHealthGate
from arya.data.scrapers import NSEFilingScraper, NewsScraper, RBIScraper, SEBIScraper, WikipediaScraper
from arya.eval.gates import benchmark_gate, corpus_gate, pretraining_log_gate, tokeniser_gate
from arya.tokeniser.train_tokeniser import train_tokeniser
from arya.training.tokenise_corpus import tokenise_to_bin


def main() -> int:
    parser = argparse.ArgumentParser(description="Arya production pipeline CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect")
    collect_sub = collect.add_subparsers(dest="source", required=True)

    nse = collect_sub.add_parser("nse")
    nse.add_argument("output_dir", type=Path)
    nse.add_argument("--from-date", required=True)
    nse.add_argument("--to-date", required=True)
    nse.add_argument("--index", default="equities")
    nse.add_argument("--download-attachments", action="store_true")
    nse.add_argument("--max-attachments", type=int)
    nse.add_argument("--progress-every", type=int, default=250)

    rbi = collect_sub.add_parser("rbi")
    rbi.add_argument("output_dir", type=Path)
    rbi.add_argument("--limit", type=int, default=50)
    rbi.add_argument("--include-notifications", action="store_true")

    sebi = collect_sub.add_parser("sebi")
    sebi.add_argument("output_dir", type=Path)
    sebi.add_argument("--limit", type=int, default=100)
    sebi.add_argument("--no-fetch-articles", action="store_true")

    news = collect_sub.add_parser("news")
    news.add_argument("output_dir", type=Path)
    news.add_argument("--per-feed-limit", type=int, default=50)
    news.add_argument("--fetch-articles", action="store_true")

    wiki = collect_sub.add_parser("wikipedia")
    wiki.add_argument("output_dir", type=Path)
    wiki.add_argument("--limit", type=int)

    clean = sub.add_parser("clean-corpus")
    clean.add_argument("raw_root", type=Path)
    clean.add_argument("clean_root", type=Path)
    clean.add_argument("--min-words", type=int, default=50)

    split = sub.add_parser("split-corpus")
    split.add_argument("clean_root", type=Path)
    split.add_argument("split_root", type=Path)
    split.add_argument("--val-fraction", type=float, default=0.01)

    tok = sub.add_parser("train-tokeniser")
    tok.add_argument("corpus_dir", type=Path)
    tok.add_argument("output_dir", type=Path)
    tok.add_argument("--vocab-size", type=int, default=32_768)
    tok.add_argument("--min-frequency", type=int, default=2)

    tokbin = sub.add_parser("tokenise")
    tokbin.add_argument("corpus_dir", type=Path)
    tokbin.add_argument("tokeniser_path", type=Path)
    tokbin.add_argument("output_path", type=Path)

    gate = sub.add_parser("gate")
    gate_sub = gate.add_subparsers(dest="gate", required=True)
    gate_corpus = gate_sub.add_parser("corpus")
    gate_corpus.add_argument("corpus_dir", type=Path)
    gate_corpus.add_argument("--min-tokens", type=int, default=CorpusHealthGate.min_est_tokens)
    gate_corpus.add_argument("--min-avg-doc-words", type=int, default=CorpusHealthGate.min_avg_doc_words)

    gate_tok = gate_sub.add_parser("tokeniser")
    gate_tok.add_argument("tokeniser_path", type=Path)
    gate_tok.add_argument("--vocab-size", type=int, default=32_768)

    gate_pre = gate_sub.add_parser("pretraining-log")
    gate_pre.add_argument("log_path", type=Path)
    gate_pre.add_argument("--max-ppl", type=float, default=25.0)

    gate_bench = gate_sub.add_parser("benchmark")
    gate_bench.add_argument("report_path", type=Path)

    args = parser.parse_args()
    if args.command == "collect":
        return _collect(args)
    if args.command == "clean-corpus":
        result = build_clean_corpus(args.raw_root, args.clean_root, min_words=args.min_words)
        print(json.dumps(result.__dict__, indent=2, sort_keys=True))
        return 0
    if args.command == "split-corpus":
        print(json.dumps(split_corpus(args.clean_root, args.split_root, args.val_fraction), indent=2))
        return 0
    if args.command == "train-tokeniser":
        path = train_tokeniser(args.corpus_dir, args.output_dir, args.vocab_size, args.min_frequency)
        print(path)
        return 0
    if args.command == "tokenise":
        n_tokens = tokenise_to_bin(args.corpus_dir, args.tokeniser_path, args.output_path)
        print(json.dumps({"tokens": n_tokens, "output_path": str(args.output_path)}, indent=2))
        return 0
    if args.command == "gate":
        return _gate(args)
    raise AssertionError(args.command)


def _collect(args) -> int:
    if args.source == "nse":
        count = NSEFilingScraper(args.output_dir).collect_range(
            args.from_date,
            args.to_date,
            index=args.index,
            download_attachments=args.download_attachments,
            max_attachments=args.max_attachments,
            progress_every=args.progress_every,
        )
    elif args.source == "rbi":
        count = RBIScraper(args.output_dir).collect_press_releases(limit=args.limit)
        if args.include_notifications:
            count += RBIScraper(args.output_dir).collect_notifications(limit=args.limit)
    elif args.source == "sebi":
        count = SEBIScraper(args.output_dir, fetch_articles=not args.no_fetch_articles).collect_rss(limit=args.limit)
    elif args.source == "news":
        count = NewsScraper(args.output_dir, fetch_articles=args.fetch_articles).collect(per_feed_limit=args.per_feed_limit)
    elif args.source == "wikipedia":
        count = WikipediaScraper(args.output_dir).collect(limit=args.limit)
    else:
        raise AssertionError(args.source)
    print(json.dumps({"source": args.source, "written": count}, indent=2, sort_keys=True))
    return 0


def _gate(args) -> int:
    if args.gate == "corpus":
        result = corpus_gate(
            args.corpus_dir,
            CorpusHealthGate(min_est_tokens=args.min_tokens, min_avg_doc_words=args.min_avg_doc_words),
        )
    elif args.gate == "tokeniser":
        result = tokeniser_gate(args.tokeniser_path, vocab_size=args.vocab_size)
    elif args.gate == "pretraining-log":
        result = pretraining_log_gate(args.log_path, max_ppl=args.max_ppl)
    elif args.gate == "benchmark":
        result = benchmark_gate(args.report_path)
    else:
        raise AssertionError(args.gate)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
