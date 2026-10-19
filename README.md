# ⚡ ai-tools: 0-Token Autonomous Engineering & DevOps CLI Suite

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![Zero-Token CLI](https://img.shields.io/badge/Efficiency-0--Token_CLI-orange.svg)](docs/)
[![Architecture: JarvisOS](https://img.shields.io/badge/Ecosystem-JarvisOS-purple.svg)](author/)

> **High-speed, deterministic, 0-token command-line suite for developers and autonomous AI agents.**  
> Parse codebases, audit server ports, scrub credentials, inspect databases, reduce video keyframes, sync cloud drives, and generate API contracts in milliseconds without consuming LLM tokens.

---

## 🌟 Why `ai-tools`?

In modern AI-assisted engineering, agents and developers waste thousands of tokens and wait tens of seconds feeding raw files, logs, and database dumps into cloud LLMs.

`ai-tools` provides a local, deterministic alternative:
- ⚡ **30-50% Analysis Efficiency:** Accelerates codebase AST parsing, port checks, and diagnostic audits by 30-50% compared to prompt-heavy agent workflows.
- 💰 **0 LLM Tokens Spent:** All indexing, parsing, and inspection run locally.
- ⚡ **Microsecond Execution:** Written in Python with optimized standard libraries and AST parsing.
- 🔒 **Zero Secret Leaks:** Built-in pattern scanner redacts credentials before committing or transmitting.
- 🤖 **Agent-First NDJSON Output:** Emits machine-readable JSON checkpoints for seamless integration into autonomous agent swarms.

---

## 🧱 The 12 Production Modules

| Module | Description | Guide |
|:---|:---|:---|
| 🖥️ **`sys`** | Server health (CPU/RAM), storage allocation, port scanner, and Docker audit. | [docs/01_sys.md](docs/01_sys.md) |
| 🧩 **`code`** | Gen2 AST parser (0-dependency) for Python, JS/TS, Go, PHP, and C. Blueprint and API discovery. | [docs/02_code.md](docs/02_code.md) |
| 🔒 **`secure`** | Scans 60+ secret patterns (API keys, bot tokens, private keys) with 60% masked dry-runs and redaction. | [docs/03_secure.md](docs/03_secure.md) |
| 🩺 **`debug`** | Surgical stacktrace locator with contextual source code extraction and instant compiler check. | [docs/04_debug.md](docs/04_debug.md) |
| 📄 **`doc`** | 8-Section API contracts, TypeScript DTOs, Postman generator, and safe GET-only probing sandbox. | [docs/05_doc.md](docs/05_doc.md) |
| 🎬 **`media`** | Video keyframe extraction, audio silence removal & STT, image OCR & dHash, and memory archive tree. | [docs/06_media.md](docs/06_media.md) |
| 📜 **`session`** | AI agent transcript inspector, fast regex querying, and clean Markdown dialog exporter. | [docs/07_session.md](docs/07_session.md) |
| ⚡ **`super_media`** | Perceptual dHash frame reducer (<12% delta), Audio-Visual timeline sync, and 5-tier archive blueprint. | [docs/08_super_media.md](docs/08_super_media.md) |
| 🤖 **`bot`** | Sandboxed Telegram bot command handler manager (add, remove, test, and syntax check). | [docs/09_bot.md](docs/09_bot.md) |
| 📤 **`sender`** | Telegram message dispatcher: formatted Markdown/HTML, documents, photos, and real-time live message updates. | [docs/10_sender.md](docs/10_sender.md) |
| 🗄️ **`db`** | Multi-engine database inspector and query engine (PostgreSQL, MySQL, SQLite, MongoDB, Redis). | [docs/11_db.md](docs/11_db.md) |
| ☁️ **`drive`** | Google Drive 5.00 TB automation (rclone engine, OAuth/Service Account, chunked upload/download/sync). | [docs/12_drive.md](docs/12_drive.md) |

---

## 🚀 Quickstart & Installation

### 1. Clone & Install
```bash
git clone https://github.com/fummatov92/ai-tools.git
cd ai-tools
pip install -r requirements.txt
./install.sh
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your optional configurations
```

### 3. External System Dependencies
To enable full media processing, cloud drive sync, and OCR, install the recommended system CLI tools:
```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y ffmpeg tesseract-ocr rclone sqlite3 nodejs

# macOS (Homebrew)
brew install ffmpeg tesseract rclone sqlite node
```
> See [docs/SYSTEM_DEPENDENCIES.md](docs/SYSTEM_DEPENDENCIES.md) for detailed per-module requirements and Windows/WSL2 setup.

### 4. Verify Capabilities
```bash
ai-tool --describe
```

---

## 💡 Common CLI Examples

```bash
# Get full codebase blueprint without wasting LLM tokens
ai-tool code blueprint /path/to/project

# Check listening ports between 8000 and 9000
ai-tool sys ports --start 8000 --end 9000

# Scan project for accidental secret leaks (Dry-Run)
ai-tool secure scan /path/to/project

# Surgical stacktrace context locator
ai-tool debug trace --log error.log

# Check Google Drive cloud connection and quota
ai-tool drive status

# Inspect SQL dump tables and row counts
ai-tool db inspect backup.sql
```

---

## 🏛️ Origins & Author

`ai-tools` was created by **Fayzillo Ummatov** ([@fummatov92](https://github.com/fummatov92)) as the deterministic utility backbone for **JarvisOS**.

- [Origin Story & Architecture](author/ORIGIN_STORY.md)
- [About the Author](author/ABOUT_AUTHOR.md)
- [Engineering Philosophy & Roadmap](author/PHILOSOPHY_AND_ROADMAP.md)

---

## 📄 License
This project is open-source and released under the [MIT License](LICENSE).
