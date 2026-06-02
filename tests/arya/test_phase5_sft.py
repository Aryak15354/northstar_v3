import json

from arya.sft.build_sft_data import build_nil_example
from arya.sft.dataset import SFTDataset
from arya.tokeniser.train_tokeniser import train_tokeniser


def test_phase5_sft_dataset_masks_prompt_tokens(tmp_path):
    corpus = tmp_path / "corpus" / "sft"
    corpus.mkdir(parents=True)
    corpus.joinpath("sample.txt").write_text(
        (
            "<|system|> system <|user|> user <|assistant|> "
            "<|nil_event|> <|nil_action|> MONITOR_ONLY confidence rationale <|eos|> "
        )
        * 20
    )
    tokeniser_path = train_tokeniser(
        tmp_path / "corpus",
        tmp_path / "tok",
        vocab_size=512,
        min_frequency=1,
        show_progress=False,
    )
    example = build_nil_example(
        {"headline": "Routine NSE circular"},
        "Regime neutral, exposure moderate.",
        {"portfolio_action": "MONITOR_ONLY", "confidence": 0.4},
    )
    examples_path = tmp_path / "examples.json"
    examples_path.write_text(json.dumps([example]))

    ds = SFTDataset(examples_path, tokeniser_path, max_len=256)
    input_ids, target = ds[0]
    assistant_id = ds.assistant_id
    assistant_pos = (input_ids == assistant_id).nonzero(as_tuple=True)[0][-1].item()

    assert all(value.item() == -100 for value in target[: assistant_pos + 1])
    assert (target[assistant_pos + 1 :] != -100).any()
