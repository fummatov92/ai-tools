# 🩺 Surgical Debugging & Stacktrace Analysis (`debug` module)

The `debug` module parses error stacktraces and runs instant compiler/syntax verification across projects.

## Commands

### 1. Stacktrace Surgical Locator
```bash
ai-tool debug trace "Traceback (most recent call last): File 'server.py', line 45..."
ai-tool debug trace --log /path/to/error.log
```
Parses traceback logs, locates the problematic source file and exact line number, and extracts the surrounding code context (+/- 10 lines) with syntax highlighting.

### 2. Fast Syntax & Type Verification
```bash
ai-tool debug check /path/to/project
```
Runs local TypeScript (`tsc --noEmit`), Python (`py_compile`), or Go compiler checks, surfacing errors in milliseconds without running long test suites.
