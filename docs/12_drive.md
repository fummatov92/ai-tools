# ☁️ Google Drive Cloud Automation & Sync (`drive` module)

The `drive` module integrates high-performance cloud storage (Google Drive 5.00 TB) into server environments using automated rclone engines, OAuth tokens, and Service Accounts.

## Features
- **0-Token Cloud Operations:** Upload, download, list, quota, and link generation from terminal.
- **Chunked Resumable Transfers:** Reliable large file transfers (e.g. 100MB to 50GB backups).
- **Two-Way / One-Way Sync:** Keeps local folders and remote Google Drive folders in sync.

## Commands

### 1. Check Connection & Storage Quota
```bash
ai-tool drive status
ai-tool drive quota
```
Outputs total allocated storage, used space, free space, and active connection status.

### 2. List Files & Folders
```bash
ai-tool drive ls
ai-tool drive ls --path "Backups"
```

### 3. Upload File or Directory
```bash
ai-tool drive upload /path/to/archive.zip --remote-path "Backups/"
```

### 4. Download File or Directory
```bash
ai-tool drive download "Backups/archive.zip" --local-path ./downloaded.zip
```

### 5. Generate Shareable Link
```bash
ai-tool drive link "Backups/archive.zip"
```
