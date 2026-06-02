"""Train Arya's custom BPE tokeniser."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterator

from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
from tokenizers.normalizers import NFC

from arya.tokeniser.constants import SPECIAL_TOKENS, UNK_TOKEN, VOCAB_SIZE


def corpus_iterator(corpus_dir: str | Path, chunk_chars: int = 10_000) -> Iterator[str]:
    """Yield bounded text chunks so tokeniser training stays memory-safe."""

    corpus_path = Path(corpus_dir)
    for file_path in sorted(corpus_path.rglob("*.txt")):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for start in range(0, len(text), chunk_chars):
            chunk = text[start : start + chunk_chars].strip()
            if len(chunk) > 50:
                yield chunk


def build_tokeniser() -> Tokenizer:
    tokeniser = Tokenizer(models.BPE(unk_token=UNK_TOKEN))
    tokeniser.normalizer = NFC()
    tokeniser.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokeniser.decoder = decoders.ByteLevel()
    return tokeniser


def train_tokeniser(
    corpus_dir: str | Path,
    output_dir: str | Path,
    vocab_size: int = VOCAB_SIZE,
    min_frequency: int = 2,
    show_progress: bool = True,
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    tokeniser = build_tokeniser()
    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=SPECIAL_TOKENS,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        min_frequency=min_frequency,
        show_progress=show_progress,
    )
    tokeniser.train_from_iterator(corpus_iterator(corpus_dir), trainer=trainer)

    path = output_path / "arya-tokeniser.json"
    tokeniser.save(str(path))
    return path


def load_tokeniser(path: str | Path) -> Tokenizer:
    return Tokenizer.from_file(str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Arya BPE tokeniser.")
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--vocab-size", type=int, default=VOCAB_SIZE)
    parser.add_argument("--min-frequency", type=int, default=2)
    args = parser.parse_args()

    path = train_tokeniser(
        args.corpus_dir,
        args.output_dir,
        vocab_size=args.vocab_size,
        min_frequency=args.min_frequency,
    )
    tokeniser = load_tokeniser(path)
    print(f"Tokeniser saved to {path}")
    print(f"Vocab size: {tokeniser.get_vocab_size()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
