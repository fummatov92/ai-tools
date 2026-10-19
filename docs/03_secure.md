# 🔒 Secret Scanning & Sanitization (`secure` module)

The `secure` module protects repositories from accidental secret leaks by detecting 60+ patterns of credentials, API tokens, passwords, and private keys.

## Features
- **Dry-Run Safe Mode:** `ai-tool secure scan` scans without altering any file.
- **60% Masking:** Discovered secrets are masked by 60% in generated reports so that developers can identify the secret without exposing it.
- **Automated Backups:** When `redact` is executed, original files are backed up automatically to `scanning_docs/backups/`.

## Commands

### 1. Scan for Secrets (Dry-Run)
```bash
ai-tool secure scan /path/to/project
```
Outputs findings count and generates a detailed audit report in `scanning_docs/reports/scan_report.json`.

### 2. Redact Secrets (Execute)
```bash
ai-tool secure redact /path/to/project
```
Replaces discovered secrets with `[REDACTED_PASSWORD]`, `[REDACTED_TOKEN]`, `[REDACTED_PRIVATE_KEY]`.
