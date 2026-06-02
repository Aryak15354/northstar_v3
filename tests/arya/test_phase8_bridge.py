import importlib

from arya.inference.quantise import save_arya_checkpoint
from arya.model.config import AryaConfig
from arya.model.transformer import Arya
from arya.tokeniser.train_tokeniser import train_tokeniser


def test_phase8_bridge_loads_env_configured_tiny_runtime(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus" / "bridge"
    corpus.mkdir(parents=True)
    corpus.joinpath("sample.txt").write_text(
        ("<|system|> <|user|> <|assistant|> <|eos|> bridge runtime text " * 20)
    )
    tokeniser_path = train_tokeniser(
        tmp_path / "corpus",
        tmp_path / "tok",
        vocab_size=512,
        min_frequency=1,
        show_progress=False,
    )
    checkpoint_path = tmp_path / "arya-tiny.pt"
    save_arya_checkpoint(Arya(AryaConfig.tiny(vocab_size=512)), checkpoint_path)

    monkeypatch.setenv("ARYA_CHECKPOINT_PATH", str(checkpoint_path))
    monkeypatch.setenv("ARYA_TOKENISER_PATH", str(tokeniser_path))
    monkeypatch.setenv("ARYA_DEVICE", "cpu")

    bridge = importlib.import_module("arya.northstar_bridge")
    bridge.get_arya_runtime.cache_clear()
    runtime = bridge.get_arya_runtime()
    assert hasattr(runtime, "complete")
