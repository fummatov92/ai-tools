# 🤖 Dynamic Telegram Bot Handler Management (`bot` module)

The `bot` module manages modular command handlers for Telegram bots, allowing developers to add, remove, and verify handlers dynamically in isolated sandboxes.

## Commands

### 1. List Dynamic Handlers
```bash
ai-tool bot list
```
Displays all active command handlers, file sizes, and modification timestamps.

### 2. Safely Add Handler
```bash
ai-tool bot add stats_cmd --desc "Prints server statistics"
```
Generates a boilerplate handler template in `handlers/stats_cmd.js` with isolated execution boundaries.

### 3. Remove Handler
```bash
ai-tool bot remove stats_cmd
```
Safely deletes handler files while preventing directory traversal attacks.

### 4. Syntax & Integrity Check
```bash
ai-tool bot check
```
Verifies JavaScript/TypeScript syntax for all handler files before loading them into live bot runtimes.
