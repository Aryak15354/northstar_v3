import torch

from arya.inference.runtime import AryaRuntime
from arya.tokeniser.train_tokeniser import load_tokeniser, train_tokeniser


class AppendModel:
    def __init__(self, append_ids):
        self.append_ids = append_ids

    def to(self, device):
        return self

    def eval(self):
        return self

    def generate(self, input_ids, max_new_tokens=512, temperature=0.2, eos_token_id=None):
        append = self.append_ids[:max_new_tokens]
        tensor = torch.tensor([append], dtype=torch.long, device=input_ids.device)
        return torch.cat([input_ids, tensor], dim=1)


def test_phase7_runtime_complete_and_cache(tmp_path):
    corpus = tmp_path / "corpus" / "rt"
    corpus.mkdir(parents=True)
    corpus.joinpath("sample.txt").write_text(
        ("<|system|> <|user|> <|assistant|> <|eos|> NIFTY OK response " * 20)
    )
    tokeniser_path = train_tokeniser(
        tmp_path / "corpus",
        tmp_path / "tok",
        vocab_size=512,
        min_frequency=1,
        show_progress=False,
    )
    tokeniser = load_tokeniser(tokeniser_path)
    append_ids = tokeniser.encode("NIFTY OK").ids
    runtime = AryaRuntime(AppendModel(append_ids), tokeniser_path, device="cpu")

    first = runtime.complete("System", "User", max_tokens=len(append_ids))
    second = runtime.complete("System", "User", max_tokens=len(append_ids))

    assert "NIFTY" in first.content
    assert first.cached is False
    assert second.cached is True
    assert runtime.session_calls == 1
