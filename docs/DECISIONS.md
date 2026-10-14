# Decisions and departures from the handoff spec

The handoff in `docs/handoff/` was written for a paid AWS + n8n + Anthropic stack. Ledgic is an
open-source showcase that must run at (near) zero cost, so these departures are deliberate.

| # | Spec | Ledgic | Why |
|---|------|--------|-----|
| D1 | n8n workflows on AWS ECS | Durable Python orchestrator inside the FastAPI core (`services/core/app/orchestrator`), state in Postgres, `LISTEN/NOTIFY` wakeups | One process on Railway Hobby; workflows are code that can be unit-tested and read on GitHub |
| D2 | Anthropic Claude vision + AWS Textract cross-check | OpenAI `gpt-4.1-mini` structured outputs via the OpenAI Agents SDK; calibration uses the spec's fallback formula | Uses an existing key; no per-page OCR bill |
| D3 | fastembed bge-small (384) | `text-embedding-3-small` truncated to 512 dims | Tiny image on Railway (no torch/onnx); embeddings computed once at seed time |
| D4 | SES email, S3 EDI drop, vendor portal scraping, Slack | Upload + mobile `/capture` intake only; replay injects documents directly | No domain or AWS account needed |
| D5 | QuickBooks Online sandbox | Deterministic mock adapters for QuickBooks and NetSuite (`posting/mock.py`) | No Intuit app review / OAuth for a demo |
| D6 | Pixel visual regression | Playwright smoke + axe at 1280/1600 | Time-boxed build |
| D7 | Terraform, CloudWatch, Secrets Manager | Railway + Vercel + Supabase dashboards; env vars | Free tiers |
| D8 | Contract "Vendor agreement 2026" ends 2026-09-30 | Seed computes a rolling end date (5 months after seed day) | The demo runs after the spec date; the clause 4.2 story must stay true |
| D9 | LLM never writes prose | Added a **resolution agent** that drafts vendor notices / explanations with citations; a guard asserts every money figure equals the deterministic recommendation | Shows tool-using agents while keeping "LLM reads, never decides" |
| D10 | — | **Ask Ledgic** RAG copilot (pgvector + full-text hybrid, RRF) and an **MCP server** exposing Ledgic tools | Portfolio goals: agents, RAG, MCP |
| D11 | Demo viewer is read-only | Viewer + "Try as Elena" (AP manager) sign-in; demo data resets nightly | Lets visitors exercise real decision flows |
| D12 | AI spend cap in provider console | `llm_budget` table: atomic reserve/settle, `LLM_DAILY_CAP_USD` (default $0.50); replay uses recorded outputs ($0); BYOK header | Public demo must not drain the owner's key |
