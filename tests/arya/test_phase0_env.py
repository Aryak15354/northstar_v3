import torch
import torch.nn as nn


class SmokeMHA(nn.Module):
    def __init__(self, d_model=32, n_heads=4):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Linear(d_model * 2, d_model),
        )
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)

    def forward(self, x):
        seq_len = x.size(1)
        mask = torch.triu(torch.ones(seq_len, seq_len, device=x.device) * float("-inf"), diagonal=1)
        attn, _ = self.attn(x, x, x, attn_mask=mask)
        x = self.ln1(x + attn)
        return self.ln2(x + self.ff(x))


def test_phase0_toy_transformer_forward_backward():
    model = SmokeMHA()
    x = torch.randn(2, 8, 32)
    out = model(x)
    assert out.shape == (2, 8, 32)

    loss = out.mean()
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.requires_grad]
    assert grads
    assert all(g is not None for g in grads)

