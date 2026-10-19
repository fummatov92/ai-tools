# 🧩 AST Codebase Indexing & Blueprint (`code` module)

The `code` module delivers 0-dependency, high-speed AST indexing for Python, TypeScript/JavaScript, Go, PHP, and C.

## Commands

### 1. Codebase Blueprint
```bash
ai-tool code blueprint /path/to/project
```
Analyzes the entire repository structure, detecting:
- Primary technology stacks and frameworks;
- Total source files, configurations, and documentation counts;
- Core directory hierarchy without printing thousands of unnecessary file lines.

### 2. API Endpoint Discovery
```bash
ai-tool code endpoints /path/to/project
```
Scans controllers and route handlers across NestJS, Express, FastAPI, and Go Gin, outputting:
- HTTP Method (GET, POST, PUT, DELETE, PATCH);
- Exact Route URL;
- Source file, line number, and handler function name.

### 3. Symbol Scope & Ctags Extraction
```bash
ai-tool code symbols /path/to/project
ai-tool code symbols /path/to/file.py
```
Extracts all classes, interfaces, methods, and functions with line spans.
