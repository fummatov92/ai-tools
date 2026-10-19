# 📄 8-Section API Contracts & Probing (`doc` module)

The `doc` module generates zero-token, production-grade API documentation, TypeScript DTO contracts, and Postman collections.

## Architecture
- **8-Section Standard:** Overview, Authentication, Endpoints, Request DTOs, Response DTOs, Error Codes, cURL Examples, and Mock Sandbox.
- **Safe Probing Sandbox:** Executes safe, read-only GET requests against dev databases to generate realistic response schemas without writing to production.

## Commands

### 1. Generate Contracts
```bash
ai-tool doc generate /path/to/project --export=md,ts,postman
```
Generates:
- `docs/<module>_api_docs.md`
- `types/<module>.d.ts`
- `postman_collection.json`

### 2. Live Safe Probing
```bash
ai-tool doc probe http://127.0.0.1:3000 --whitelist-tables
```
Probes safe endpoints and captures live JSON responses.
