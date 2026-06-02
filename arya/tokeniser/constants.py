"""Tokeniser constants shared across Arya phases."""

VOCAB_SIZE = 32_768

SPECIAL_TOKENS = [
    "<|pad|>",
    "<|unk|>",
    "<|bos|>",
    "<|eos|>",
    "<|nil_event|>",
    "<|nil_action|>",
    "<|brief|>",
    "<|research|>",
    "<|options|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
]

PAD_TOKEN = "<|pad|>"
UNK_TOKEN = "<|unk|>"
BOS_TOKEN = "<|bos|>"
EOS_TOKEN = "<|eos|>"
ASSISTANT_TOKEN = "<|assistant|>"

