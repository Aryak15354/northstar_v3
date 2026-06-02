"""Configuration objects for Arya model variants."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class AryaConfig:
    vocab_size: int = 32_768
    d_model: int = 2048
    n_layers: int = 24
    n_heads: int = 16
    n_kv_heads: int = 4
    d_ff: int = 5632
    max_seq_len: int = 2048
    rope_theta: float = 10_000.0
    rms_eps: float = 1e-6
    dropout: float = 0.0
    tie_weights: bool = True

    def __post_init__(self) -> None:
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads.")
        if self.n_heads % self.n_kv_heads != 0:
            raise ValueError("n_heads must be divisible by n_kv_heads for GQA.")
        if self.vocab_size <= 0:
            raise ValueError("vocab_size must be positive.")
        if self.max_seq_len <= 0:
            raise ValueError("max_seq_len must be positive.")

    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "AryaConfig":
        return cls(**payload)

    @classmethod
    def arya_1b(cls) -> "AryaConfig":
        return cls()

    @classmethod
    def arya_3b(cls) -> "AryaConfig":
        return cls(d_model=2560, n_layers=32, n_heads=20, n_kv_heads=4, d_ff=6912)

    @classmethod
    def tiny(cls, vocab_size: int = 128) -> "AryaConfig":
        """A laptop-safe config for tests and architecture smoke runs."""

        return cls(
            vocab_size=vocab_size,
            d_model=32,
            n_layers=2,
            n_heads=4,
            n_kv_heads=2,
            d_ff=64,
            max_seq_len=64,
            dropout=0.0,
        )

