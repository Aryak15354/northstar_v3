from arya.tokeniser.constants import SPECIAL_TOKENS
from arya.tokeniser.train_tokeniser import load_tokeniser, train_tokeniser


def _write_fixture_corpus(path):
    corpus = path / "corpus" / "finance"
    corpus.mkdir(parents=True)
    corpus.joinpath("sample.txt").write_text(
        (
            "RBI MPC raises repo rate while NIFTY and BANKNIFTY react. "
            "SEBI filing says EBITDA and PAT grew in crore and lakh terms. "
            "<|nil_event|> <|nil_action|> <|assistant|> "
        )
        * 20
    )
    return corpus.parent


def test_phase2_train_tiny_tokeniser_special_tokens_and_roundtrip(tmp_path):
    corpus_dir = _write_fixture_corpus(tmp_path)
    tokeniser_path = train_tokeniser(
        corpus_dir,
        tmp_path / "tok",
        vocab_size=512,
        min_frequency=1,
        show_progress=False,
    )
    tokeniser = load_tokeniser(tokeniser_path)
    vocab = tokeniser.get_vocab()
    assert vocab["<|pad|>"] == 0
    for token in SPECIAL_TOKENS:
        assert token in vocab

    sample = "RBI MPC raises repo rate by 25 basis points."
    assert tokeniser.decode(tokeniser.encode(sample).ids) == sample
