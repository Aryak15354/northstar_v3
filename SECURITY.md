# Security Policy

Northstar V3 is a public, source-available operational workspace. Treat it as sensitive because it contains broker-integration code and operational runbooks even when credentials are absent.

## Supported Surface

Security reports should focus on the current public repository on the `main` branch, especially:

- credential handling
- broker/API integration paths
- CI and release workflows
- files that could expose private account, trading, or market-data artifacts
- unsafe defaults that could affect live execution

Archived status documents are retained for history, but exposed secrets in any file still matter and should be reported.

## Reporting

Please report sensitive issues privately to the repository owner. Do not open public issues or PRs containing real credentials, tokens, private account data, exploitable details, or secret-scanner output with full values.

Include:

- affected file paths and line numbers
- impact summary
- reproduction steps, if safe to share
- whether the issue appears in current files, git history, or both

## Credential Rotation

If a broker key, API secret, OAuth token, private key, Kaggle credential, or cloud credential appears in a public commit, assume it is compromised. Revoke or rotate it at the provider even if the current working tree has been cleaned.

## Public Hygiene Checks

Run this before publishing changes:

```bash
python scripts/ci/check_no_secrets.py
```

The scanner is intentionally lightweight. It is not a substitute for provider-side credential rotation or full history scanning with tools such as `gitleaks`.
