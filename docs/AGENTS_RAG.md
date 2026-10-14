# Agents and RAG

Ledgic follows one rule for AI: **the LLM reads, it never decides.** Models turn pixels into fields, and
they turn deterministic facts into prose with citations. Every money figure, verdict and recommendation
comes from `services/core/app/domain/` (pure `Decimal` code). Every permission check lives in the database.

All model calls go through one gateway (`app/ai/gateway.py`), and every agent has a $0 fallback path.

## 1. LLM gateway

`LlmGateway.metered(...)` wraps every OpenAI call:

```
estimate tokens → llm_budget_reserve(est_usd, cap) → call → llm_budget_settle(reservation, actual_usd) → cost_ledger row
```

- **Modes:** `LLM_MODE=fixture` (default) never builds an OpenAI client, so nothing can touch the network.
  `LLM_MODE=live` calls OpenAI when a key is available.
- **Budget:** `LLM_DAILY_CAP_USD` (default 0.50, UTC day). `llm_budget_reserve` is a single conditional
  `update … where spent + reserved + est <= cap`, so concurrent callers can't overshoot. It returns `null`
  when over budget, and the gateway raises `BudgetExceeded`. Missing or failing budget RPC → refused (fail closed).
  Stale reservations (> 10 min) are released by pg_cron or the scheduler.
- **Prices:** `PRICE_TABLE` per 1M tokens. Unknown models are priced at the most expensive row.
- **BYOK:** an `X-OpenAI-Key` header is used for that request only. It is never logged or stored and
  skips the owner's budget. The call is still written to `cost_ledger` with `meta.billing = 'byok'`.

## 2. Agents

All three agents use the OpenAI Agents SDK (`app/ai/runtime.py` builds the `RunConfig`: temperature 0,
max tokens, workflow name, metering hooks).

### 2.1 Extraction agent: `app/ai/extraction.py`

| | |
|---|---|
| **Input** | Page images. PDFs are rendered with pypdfium2 at 150 dpi; images and pages are downscaled to 1600 px on the long side. Max 3 pages. |
| **Model** | `gpt-4.1-mini` vision, prompt `app/ai/prompts/p-1.md` (`PROMPT_VERSION = "p-1"`) |
| **Output** | Strict `ExtractionResult` (`app/ai/schemas.py`), identical to `contracts/extraction.schema.json`: header fields and line items, each `{value, confidence, bbox}` |
| **Tools** | None. A single structured-output call. |
| **Guards** | Budget reservation sized from page count. Raw confidences are then **calibrated** by deterministic code (`domain/gate.calibrate_fallback`: the spec's fallback formula, since there is no second OCR reading) and scored with a weighted geometric mean (`doc_confidence`). The **gate** (document ≥ 0.90, every required field ≥ 0.75) decides whether a person must review. |
| **Modes** (`invoices.extraction_mode`) | `live` (uploads under budget or BYOK), `simulated` (replay and backfill documents carry the corpus's pre-computed read), `recorded` (hero documents use `tools/corpus/fixtures/heroes/<invoice>.json`). If no live call is possible for an upload, the run parks in extraction review with empty fields ("AI budget reached — enter fields manually"). |

The hero fixtures are produced by `tools/corpus/fixtures/heroes/generate_heroes.py` from the corpus layout
and the authored hero confidences. They stand in for a recorded model response so the demo replays at $0.

### 2.2 Resolution agent: `app/ai/resolution.py`

Drafts a **vendor notice** or an **internal explanation** for an exception (`POST /v1/exceptions/{id}/draft`;
the orchestrator also drafts in the background via `orchestrator/drafts.py`).

| | |
|---|---|
| **Input** | `DraftFacts` gathered deterministically: the exception, the recommendation (pay / hold), match lines with expected vs invoiced price and the price source (contract clause or PO), vendor, PO/GRN, prior short-pays, and the relevant contract chunks |
| **Tools** (`RESOLUTION_TOOLS`) | `search_kb` (contract-clause RAG), `vendor_history`, `get_po_grn` |
| **Output** | `body_md` with `[n]` citations, stored in `exception_drafts` with `mode`, `model`, `prompt_version` (`r-1`), `cost_usd` and the guard result |
| **Guards** | **Money guard.** A regex extracts every money figure in the draft (`$1,234.56`, `USD 88`, `88.00 dollars`). Each must equal a figure in `facts.allowed_figures()` (recommendation pay/hold, invoice and PO amounts, line amounts and unit prices, prior short-pays). Any other figure → the LLM draft is rejected, `guard.rejected` lists the offending figures, and the stored draft falls back to the recorded hero draft or the deterministic template. ≤ 900 output tokens, ≤ 6 tool calls. |
| **Fallback** | Fixture mode, no key, budget spent or any error → `recorded` mode (hero draft such as `PS-88214.draft.json` if it passes the guard, else `domain/templates`). |

### 2.3 Ask Ledgic copilot: `app/ai/copilot.py`

Answers questions about contracts, policy, vendors and the live AP queue. It is used by the web panel
(`/api/copilot` → `POST /v1/copilot/ask`, SSE) and by the MCP `ask_ledgic` tool.

| | |
|---|---|
| **Input** | A question (≤ 500 chars) and an optional `{invoice_id, exception_id}` context |
| **Tools** (`COPILOT_TOOLS`) | `search_kb`, `get_invoice`, `get_exception`, `vendor_history`, `get_po_grn`, `get_kpis`. All read-only, each in a `READ ONLY` transaction scoped to the org taken from the run context (`AgentCtx`), so the model can never choose another org. |
| **Output** | `answer_md` with numbered citations `{n, chunk_id, document_id, title, kind, clause_ref, quote}`, `mode` (`cached`, `live` or `retrieval_only`), `tool_calls`, `cost_usd`. Streamed as `status` / `token` / `citation` / `done` SSE events. |
| **Guards** | ≤ 6 tool calls (after that a tool returns "answer now"), ≤ 1.5k output tokens. The model cites chunk refs (`K1`, `K2`, …) that are rewritten to `[1]`, `[2]` and checked against chunks actually retrieved in this run. |
| **Order of service** | 1. `copilot_cache` (org, sha256 of the normalized question) → `cached`. Entries naming an invoice are skipped once its exceptions or decisions changed. Questions about "right now" are never cached. 2. Live agent → `live`. 3. Budget spent, fixture mode or error → `retrieval_only`: a deterministic answer from the top chunks (verbatim quotes) plus the deterministic exception facts. No prose is generated, so nothing can be invented. |

The suggested questions in the web panel ("Why is PS-88214 on hold?", "What does clause 4.2 of the Protein
Supplier agreement say about shrimp?", …) are precomputed into the cache by `python -m app.ai.seed_kb`.

### 2.4 MCP

The MCP server reuses the same read-only data tools (`app/ai/tools.py`) and the copilot. See [MCP.md](MCP.md).

## 3. RAG

### 3.1 Corpus

Markdown under `tools/corpus/kb/`:

| Folder | Kind | Examples |
|---|---|---|
| `contracts/` | `contract` | `protein-supplier-agreement-2026.md` (clause 4.2: Shrimp 16/20 IQF at $3.68/lb), produce and broadline agreements |
| `policies/` | `policy` | `ap-policy.md` (tolerance, approval limits, fraud release), `month-end-close.md` |
| `vendor-notes/` | `vendor_note` | one note per demo vendor |

Front matter (`title`, `kind`, `vendor`, `contract`) links documents to `vendors` and `contracts`.
Contract placeholders (effective dates) are filled from the `contracts` table at index time, so the
rolling contract end date (DECISIONS D8) stays consistent between the database and the text.

### 3.2 Chunking: `app/ai/rag/chunker.py`

- One chunk per heading section, with `heading_path` (`Protein Supplier — Vendor agreement 2026 > 4. Pricing > 4.2 Pricing: Shrimp 16/20 IQF`).
- Sections longer than 1,400 characters are split on paragraph boundaries.
- **Clause references** are parsed from numbered headings: `## 4.2 Pricing` → `4.2`, `### Section 7.1 — Term` → `7.1`,
  `## Schedule A` → `Sched. A`. A chunk inherits the nearest numbered ancestor's clause ref. This is what lets
  an answer cite *§4.2* instead of a whole document.

### 3.3 Indexing: `app/ai/rag/index.py`, `embed.py`

- `kb_documents` (one per file) and `kb_chunks` (`content`, `heading_path`, `clause_ref`,
  `embedding vector(512)`, generated `tsv`). Indexes: HNSW (`vector_cosine_ops`) on `embedding`, GIN on `tsv`.
- Live embeddings: `text-embedding-3-small` truncated to 512 dimensions (DECISIONS D3), batched by 96,
  metered by the gateway. Indexing happens once, at seed time.
- Offline (fixture mode, CI or no budget): a deterministic **hashed bag-of-words** pseudo-embedding
  (`hash-bow-512`). It is lexical, not semantic. With it, quality relies mostly on the full-text arm.
  `retrieve.py` probes which scheme an org's index uses and embeds queries the same way.

### 3.4 Retrieval: `app/ai/rag/retrieve.py` + `kb_search` (SQL)

1. **Clause pinning.** If the question names a clause (`clause 4.2`, `§4.2`, `section 4.2`), chunks with
   that `clause_ref` are pinned first (contracts before other kinds).
2. **Hybrid search in SQL.** `public.kb_search(org, embedding, text, k, kinds)`
   (`20261014000003_rpc.sql`, `security invoker`):
   - vector arm: top 40 by cosine distance (`<=>`);
   - text arm: top 40 by `ts_rank_cd` over `websearch_to_tsquery`. The query is OR-ed
     (`shrimp or price or contract`) so partial matches rank instead of requiring every word;
   - **reciprocal-rank fusion**: `score = 1/(60 + vector_rank) + 1/(60 + text_rank)`, full outer join so a
     chunk found by only one arm still counts.
3. **Rerank.** BM25 over the candidate pool (the section heading counts twice, which rewards short, precise
   clauses), fused by reciprocal rank with the pool order, plus a small bonus for the document kind the
   question names ("contract", "policy", …).
4. **Degradation.** No query embedding (budget spent, `LlmUnavailable`) or RPC missing → full-text-only SQL
   over the same chunks. The MCP `search_contracts` tool reports this as `mode: text_only`.

### 3.5 Citations

Each tool result registers its chunks in `AgentCtx` under refs `K1…Kn`. `finalize_citations` renumbers the
refs the answer actually used into `[1]…[n]` and attaches `{title, kind, clause_ref, quote}`. Refs the tools never returned are dropped, so a citation
cannot point at a passage the agent did not retrieve. The quote is a snippet of the passage around the
query terms, so a reader can check the claim without opening the document.

## 4. Fixture vs live

| | `LLM_MODE=fixture` (default, CI, demo replay) | `LLM_MODE=live` |
|---|---|---|
| Extraction | `simulated` (corpus) or `recorded` (heroes) | `live` for uploads, falls back as above |
| Embeddings | `hash-bow-512` | `text-embedding-3-small` @ 512 |
| Copilot | `cached` → `retrieval_only` | `cached` → `live` → `retrieval_only` |
| Drafts | `recorded` (hero draft or template) | `live` if the money guard passes, else `recorded` |
| Cost | $0 | ≤ `LLM_DAILY_CAP_USD`/day, or the visitor's key |

## 5. Evaluation

| What | How | Where |
|---|---|---|
| Hero numbers | Exact assertions: 736.00 / 824.00 / 88.00 / 14.72 / +12.0 % / 2,759.60 / 0.94; PR-2214 field 0.71 and document 0.88 → review; PR-2201 ≥ 0.90 → held; NV-0001 0.90 → controller; BD-104882 touchless | `tests/domain/test_heroes.py`, `tests/integration/test_scenarios.py` |
| Copilot grounding | Retrieval-only and live answers cite clause 4.2 for the shrimp question; a KB query is steered to the clause on the exception; citations are renumbered correctly | `tests/ai/test_copilot.py` |
| Money guard | Drafts with an invented figure are rejected and replaced by the template; valid drafts pass | `tests/ai/test_resolution.py` |
| Extraction schema | The pydantic model produces exactly `contracts/extraction.schema.json`; normalization and coercion | `tests/ai/test_extraction.py` |
| RAG | Clause-ref detection, section paths, front matter, long-section splits, every KB file parses, deterministic hash embeddings, full-text retrieval finds clause 4.2; data tools, recorded drafts and suggested-question precompute against a real database | `tests/ai/test_rag.py`, `tests/ai/test_db_integration.py` |
| Budget | Price math, reserve → call → settle → ledger, refusal spends nothing, failed calls settle or release, BYOK skips the budget and is never logged, fixture mode refuses clients, embeddings are metered | `tests/ai/test_gateway.py` |
| MCP permissions | A viewer token is refused by `decide_exception` (scope check and, independently, the DB role check) | `tests/mcp/` |
| Extraction accuracy KPI | Weekly `eval_runs` (12 weeks seeded): a stratified sample of each week's corpus, field-level comparison against ground-truth labels with the spec's normalization (money to cents, ISO dates, alphanumeric invoice numbers, fuzzy ≥ 90 for descriptions). The pre-human reads are **simulated** from the corpus with calibrated error rates (a field reported at 0.95 is wrong 5 % of the time), not live model output. The Operations screen reads this through `v_eval_weekly`. | `app/demo/seed.py` (`eval_rows`) |

Run the AI tests with `cd services/core && uv run pytest tests/ai -q`.
