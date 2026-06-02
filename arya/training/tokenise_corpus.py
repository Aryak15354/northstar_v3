"""Convert cleaned text corpus files into uint16 token binaries."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer
from tqdm import tqdm


def tokenise_to_bin(corpus_dir: str | Path, tokeniser_path: str | Path, output_path: str | Path) -> int:
    corpus_path = Path(corpus_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    tokeniser = Tokenizer.from_file(str(tokeniser_path))
    eos_id = tokeniser.token_to_id("<|eos|>")
    if eos_id is None:
        raise ValueError("Tokeniser is missing <|eos|>.")

    all_ids: list[int] = []
    for file_path in tqdm(sorted(corpus_path.rglob("*.txt")), desc="Tokenising corpus"):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        ids = tokeniser.encode(text).ids
        ids.append(eos_id)
        all_ids.extend(ids)

    if max(all_ids, default=0) > np.iinfo(np.uint16).max:
        raise ValueError("Token IDs exceed uint16. Reduce vocab size or change dtype.")

    arr = np.asarray(all_ids, dtype=np.uint16)
    arr.tofile(output)
    return int(arr.size)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tokenise Arya text corpus to uint16 binary.")
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("tokeniser_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    n_tokens = tokenise_to_bin(args.corpus_dir, args.tokeniser_path, args.output_path)
    print(f"Wrote {n_tokens:,} tokens to {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

