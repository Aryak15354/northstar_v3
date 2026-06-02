import torch

from arya.model.config import AryaConfig
from arya.model.transformer import Arya, estimate_transformer_params, initial_loss_baseline


def test_phase3_forward_loss_and_generation_shape():
    torch.manual_seed(7)
    cfg = AryaConfig.tiny(vocab_size=64)
    model = Arya(cfg)
    ids = torch.randint(0, cfg.vocab_size, (2, 8))
    logits = model(ids)
    assert logits.shape == (2, 8, cfg.vocab_size)

    _, loss = model(ids, ids)
    assert loss.item() > 0
    assert not torch.isnan(loss)

    out = model.generate(ids[:, :3], max_new_tokens=5, temperature=0)
    assert out.shape == (2, 8)


def test_phase3_loss_decreases_on_tiny_batch():
    torch.manual_seed(11)
    cfg = AryaConfig.tiny(vocab_size=48)
    model = Arya(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=5e-3)
    ids = torch.randint(0, cfg.vocab_size, (2, 10))

    first = None
    last = None
    for _ in range(20):
        opt.zero_grad()
        _, loss = model(ids, ids)
        loss.backward()
        opt.step()
        if first is None:
            first = loss.item()
        last = loss.item()
    assert last < first


def test_phase3_config_and_parameter_estimates():
    cfg = AryaConfig.tiny(vocab_size=32)
    model = Arya(cfg)
    assert model.parameter_count() > 0
    assert estimate_transformer_params(cfg) > 0
    assert initial_loss_baseline(32) > 3

