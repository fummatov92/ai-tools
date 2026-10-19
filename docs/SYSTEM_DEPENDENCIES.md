# 🛠️ System Requirements & External CLI Dependencies

To achieve **0-Token, ultra-fast performance**, `ai-tools` delegates heavy multimedia, cloud synchronization, and database operations to well-established, battle-tested system CLI binaries rather than cloud APIs.

---

## 📦 Required External Tools by Module

| Binary | Used in Modules | Primary Purpose | Optional / Required |
|:---|:---|:---|:---|
| **`ffmpeg`** | `media`, `super_media` | Video frame extraction, keyframe detection, and audio track separation. | Required for Video/Audio |
| **`ffprobe`** | `media`, `super_media` | Media stream metadata, duration, codec, and bitrate analysis. | Required for Video/Audio |
| **`tesseract`** | `media` | Optical Character Recognition (OCR) to extract text from images. | Optional (only for OCR) |
| **`rclone`** | `drive` | Google Drive 5.00 TB cloud storage management, upload, download, and sync. | Required for `drive` module |
| **`sqlite3`** | `db`, `secure` | Local database queries, backup parsing, and audit log indexing. | Recommended |
| **`node`** / **`tsc`** | `debug`, `bot` | Syntax verification for JavaScript/TypeScript and bot handler check. | Optional (for TS/JS checks) |

---

## 📥 Installation Commands by Operating System

### 1. Ubuntu / Debian (Recommended)
```bash
sudo apt update
sudo apt install -y \
  ffmpeg \
  tesseract-ocr \
  tesseract-ocr-eng \
  rclone \
  sqlite3 \
  nodejs
```

### 2. macOS (Homebrew)
```bash
brew update
brew install ffmpeg tesseract rclone sqlite node
```

### 3. Fedora / RHEL / CentOS
```bash
sudo dnf install -y \
  ffmpeg \
  tesseract \
  rclone \
  sqlite \
  nodejs
```

### 4. Windows
For Windows environments, running under **WSL2 (Windows Subsystem for Linux)** with Ubuntu is strongly recommended for native performance:
```bash
wsl --install -d Ubuntu
```

---

## 🛡️ Graceful Degradation & Safe Fallback
If an external tool is missing on your system:
- Core modules (`code`, `secure`, `sys`, `session`, `doc`, `sender`) continue to function 100% independently without any external binary dependencies.
- If a command requiring an external binary is invoked (e.g. `ai-tool media video` without `ffmpeg` or `ai-tool drive status` without `rclone`), the CLI prints a clear, friendly error specifying the exact package to install:
```json
{
  "success": false,
  "error": "rclone vositasi tizimda topilmadi. O'rnatish: curl https://rclone.org/install.sh | sudo bash"
}
```
