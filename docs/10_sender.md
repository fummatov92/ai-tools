# 📤 Telegram Dispatch & Live Status (`sender` module)

The `sender` module enables command-line scripts and autonomous agents to send formatted messages, files, photos, and real-time live message updates to Telegram chats.

## Commands

### 1. Send Formatted Message
```bash
ai-tool sender msg "🚀 Build completed successfully!" --chat-id 123456789
```

### 2. Send Document / Archive
```bash
ai-tool sender doc /path/to/archive.zip --chat-id 123456789
```

### 3. Send Photo
```bash
ai-tool sender photo /path/to/chart.png --chat-id 123456789
```

### 4. Real-Time Live Message Update
```bash
ai-tool sender live 123456789 3694 "⏳ Step 3/5: Compiling assets..."
```
Edits an existing Telegram message in place, preventing chat flooding and providing a live progress bar.
