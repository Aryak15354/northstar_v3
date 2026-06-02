import json

from arya.dpo.build_dpo_data import build_overconfidence_rejection, write_pairs
from arya.dpo.dataset import DPODataset
from arya.dpo.train_dpo import DPOConfig, train_dpo
from arya.model.config import AryaConfig
from arya.model.transformer import Arya
from arya.sft.build_sft_data import build_nil_example
from arya.sft.dataset import SFTDataset
from arya.sft.train_sft import SFTConfig, train_sft
from arya.tokeniser.train_tokeniser import train_tokeniser


def _tokeniser(tmp_path):
    corpus = tmp_path / "corpus" / "align"
    corpus.mkdir(parents=True)
    corpus.joinpath("sample.txt").write_text(
        (
            "<|system|> <|user|> <|assistant|> <|nil_event|> <|nil_action|> "
            "MONITOR_ONLY REDUCE_GROSS confidence rationale portfolio_action <|eos|> "
        )
        * 30
    )
    return train_tokeniser(tmp_path / "corpus", tmp_path / "tok", vocab_size=512, min_frequency=1, show_progress=False)


def test_sft_and_dpo_training_loops_smoke(tmp_path):
    tok = _tokeniser(tmp_path)
    example = build_nil_example(
        {"headline": "Routine update"},
        "Neutral state.",
        {"portfolio_action": "MONITOR_ONLY", "confidence": 0.4, "rationale": "Routine update."},
    )
    examples_path = tmp_path / "sft.json"
    examples_path.write_text(json.dumps([example]))
    sft_ds = SFTDataset(examples_path, tok, max_len=256)
    model = Arya(AryaConfig.tiny(vocab_size=512))
    logs = train_sft(model, sft_ds, SFTConfig(epochs=1, batch_size=1, grad_accum=1, learning_rate=1e-3))
    assert logs and logs[-1]["loss"] > 0

    pair = build_overconfidence_rejection(example)
    pairs_path = write_pairs([pair], tmp_path / "pairs.json")
    dpo_ds = DPODataset(pairs_path, tok, max_len=256)
    policy = Arya(AryaConfig.tiny(vocab_size=512))
    ref = Arya(AryaConfig.tiny(vocab_size=512))
    dpo_logs = train_dpo(policy, ref, dpo_ds, DPOConfig(epochs=1, batch_size=1, learning_rate=1e-4))
    assert dpo_logs and "reward_margin" in dpo_logs[-1]
