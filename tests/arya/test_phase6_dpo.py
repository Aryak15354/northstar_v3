import torch
import torch.nn as nn

from arya.dpo.loss import dpo_loss


class BiasLanguageModel(nn.Module):
    def __init__(self, vocab_size=8):
        super().__init__()
        self.bias = nn.Parameter(torch.zeros(vocab_size))

    def forward(self, ids):
        batch, seq_len = ids.shape
        return self.bias.view(1, 1, -1).expand(batch, seq_len, -1)


def test_phase6_dpo_loss_is_finite_and_backprops():
    policy = BiasLanguageModel()
    reference = BiasLanguageModel()
    chosen = torch.tensor([[1, 2, 3, 4]])
    rejected = torch.tensor([[1, 5, 6, 4]])
    mask = torch.ones_like(chosen)

    loss, margin = dpo_loss(policy, reference, chosen, mask, rejected, mask, beta=0.1)
    assert loss.item() > 0
    assert isinstance(margin, float)
    loss.backward()
    assert policy.bias.grad is not None
    assert reference.bias.grad is None

