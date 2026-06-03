#!/usr/bin/env python3
"""Lightweight tracked-file secret scan for public repository hygiene."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


SKIP_SUFFIXES = {
    ".csv",
    ".gz",
    ".h5",
    ".hdf5",
    ".ipynb",
    ".jpg",
    ".jpeg",
    ".parquet",
    ".pdf",
    ".png",
    ".webp",
    ".xlsx",
    ".zip",
}

ALLOWLIST_TOKENS = {
    "",
    "...",
    "<token>",
    "new_token",
    "new_token_here",
    "placeholder",
    "rotate_required",
    "your_6_digit_totp_here",
    "your_access_token",
    "your_access_token_here",
    "your_api_key",
    "your_api_key_here",
    "your_api_secret",
    "your_api_secret_here",
    "your_groww_api_key_here",
    "your_groww_api_secret_here",
    "your_groww_auth_token_here",
    "your_new_token",
    "your_new_token_here",
    "your_token_here",
    "your_upstox_api_key_here",
    "your_upstox_api_secret_here",
}

ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|api[_-]?secret|access[_-]?token|refresh[_-]?token|auth[_-]?token|password|passwd|client[_-]?secret)\b"
    r"\s*[:=]\s*['\"]?([^'\"\s#]+)"
)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")
UPSTOX_KEY_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], text=True)
    return [Path(line) for line in output.splitlines() if line.strip()]


def is_probable_secret(value: str) -> bool:
    token = value.strip().strip("'\"")
    lowered = token.lower()
    if lowered in ALLOWLIST_TOKENS:
        return False
    if token.startswith("${") and token.endswith("}"):
        return False
    if token.startswith("$"):
        return False
    if len(token) < 8:
        return False
    return True


def inspect_file(path: Path) -> list[str]:
    if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        lowered_line = line.lower()
        if PRIVATE_KEY_RE.search(line):
            findings.append(f"{path}:{idx}: private key block")
        if JWT_RE.search(line):
            findings.append(f"{path}:{idx}: JWT-like token")
        for match in ASSIGNMENT_RE.finditer(line):
            value = match.group(1)
            if path.suffix == ".py":
                continue
            if is_probable_secret(value):
                findings.append(f"{path}:{idx}: secret-like assignment")
        if (
            UPSTOX_KEY_RE.search(line)
            and "your_upstox_api_key_here" not in line
            and ("upstox_api_key" in lowered_line or "api key" in lowered_line)
        ):
            findings.append(f"{path}:{idx}: UUID-like broker key")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        findings.extend(inspect_file(path))

    if findings:
        print("Potential secrets found in tracked files:")
        print("\n".join(findings[:200]))
        if len(findings) > 200:
            print(f"... and {len(findings) - 200} more")
        return 1

    print("No obvious secrets found in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
