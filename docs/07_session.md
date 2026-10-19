# 📜 AI Session & Transcript Intelligence (`session` module)

The `session` module analyzes, queries, and sanitizes Google Antigravity and AI Agent transcripts directly from JSONL files.

## Commands

### 1. List Sessions
```bash
ai-tool session list
```
Lists recent sessions with conversation IDs, titles, step counts, and timestamps.

### 2. Inspect Session Details
```bash
ai-tool session inspect <session-id>
```
Breaks down token usage, tools executed, and user prompts.

### 3. Query Keyword Across Transcripts
```bash
ai-tool session query <session-id> "keyword"
```
Blazing-fast search across multi-megabyte JSONL transcript files without loading them into memory.

### 4. Export Clean Markdown
```bash
ai-tool session export <session-id> --output session_summary.md
```
Exports human-readable dialogs with secrets automatically redacted.
