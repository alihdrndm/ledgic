# Ledgic MCP server

Ledgic exposes its accounts-payable brain over the [Model Context Protocol](https://modelcontextprotocol.io),
so Claude Desktop, Claude Code, Cursor or any MCP client can triage exceptions, explain three-way matches,
cite contract clauses and — with the right token and role — record real decisions.

- **Remote (streamable HTTP):** `https://<core-host>/mcp`, bearer personal access token.
- **Local (stdio):** `uv run --project services/core ledgic-mcp`, token in `LEDGIC_MCP_TOKEN`.
- Code: `services/core/app/mcp/` (`server.py` tools · `service.py` queries · `auth.py` tokens ·
  `http.py` / `stdio.py` transports · `tokens.py` CLI). Built on the official `mcp` Python SDK 2.x (`MCPServer`).

## Tools

| Tool | Scope | What it returns |
|---|---|---|
| `list_exceptions(status='open', type=None, limit=20)` | read | Open (or filtered) exceptions: id, type, invoice, vendor, location, amount at risk, reason, age, payment-blocked flag, the system's recommendation |
| `get_invoice(invoice_number)` | read | Header, lines with GL coding, PO/GRN, match verdict, exceptions + decisions, ERP posting. Number matched ignoring case/punctuation |
| `explain_match(invoice_number)` | read | Per-line tolerance math (invoiced vs expected price and its source — contract clause or PO — delta, allowed), the sentence *"Line 1 is +12.0% against a ±2% limit and $88.00 against a $25 limit — it fails both, so the invoice holds for approval."*, the rule, recommendation and decision |
| `search_contracts(query, k=5, kind=None)` | read | Hybrid (pgvector + full-text, RRF) passages from contracts / AP policy / vendor notes with `title`, `clause_ref`, quote. Degrades to full-text (`mode: text_only`) when embeddings are unavailable |
| `ask_ledgic(question)` | read | Ledgic's own RAG copilot: markdown answer + numbered citations. Cost-capped (daily AI budget → cached / retrieval-only) |
| `get_kpis(period='mtd'\|'qtd'\|'l30')` | read | Volume, touchless rate, cost per invoice, cycle time, money held (variances / duplicates / fraud), decision speed, top catches, ERP sync + today's queue |
| `verify_audit_chain()` | read | Recomputes the org's hash-chained audit log: `ok`, entries, head hash or first broken id |
| `decide_exception(exception_id, action, comment?, pay_amount?, hold_amount?, extra?)` | **decide** | Executes `rpc_decide_exception` as the token's user — same transaction, checks and audit trail as a click in the UI |

**Resources:** `ledgic://policy/ap` (AP policy markdown) · `ledgic://exceptions/open` (JSON snapshot of the queue).
**Prompts:** `triage_exceptions(limit)` (propose — never execute — a decision per open exception, with citations) ·
`explain_invoice(invoice_number)` (vendor-friendly explanation of a hold).

Money is always a decimal string in USD (`"2759.60"`); percentages are fractions (`"0.02"` = 2%).

## Connect

### Public demo (read-only)

The demo deployment publishes a **read-only** token for the *Demo Viewer* user:

```
Authorization: Bearer <MCP_DEMO_TOKEN published in the README>
```

It can read everything a viewer can see in the demo org and nothing else; `decide_exception` is refused (see
[security model](#security-model)).

### Claude Code

```bash
claude mcp add --transport http ledgic https://<core-host>/mcp \
  --header "Authorization: Bearer lgc_pat_..."
```

Local stdio instead:

```bash
claude mcp add ledgic --env LEDGIC_MCP_TOKEN=lgc_pat_... \
  -- uv run --project /path/to/ledgic/services/core ledgic-mcp
```

### Cursor (`~/.cursor/mcp.json` or `.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "ledgic": {
      "url": "https://<core-host>/mcp",
      "headers": { "Authorization": "Bearer lgc_pat_..." }
    }
  }
}
```

Local stdio:

```json
{
  "mcpServers": {
    "ledgic": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/ledgic/services/core", "ledgic-mcp"],
      "env": {
        "LEDGIC_MCP_TOKEN": "lgc_pat_...",
        "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

Local stdio:

```json
{
  "mcpServers": {
    "ledgic": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/ledgic/services/core", "ledgic-mcp"],
      "env": {
        "LEDGIC_MCP_TOKEN": "lgc_pat_...",
        "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
      }
    }
  }
}
```

Remote HTTP with a bearer header (Desktop's connector UI only does OAuth, so bridge with `mcp-remote`):

```json
{
  "mcpServers": {
    "ledgic": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://<core-host>/mcp", "--header", "Authorization:Bearer ${LEDGIC_TOKEN}"],
      "env": { "LEDGIC_TOKEN": "lgc_pat_..." }
    }
  }
}
```

On Windows use the full path to `uv.exe` / `npx.cmd` if Claude Desktop cannot find them.

## Tokens

Personal access tokens look like `lgc_pat_<43 url-safe chars>`. Only the sha256 is stored (`mcp_tokens.token_hash`);
the raw value is printed once.

```bash
cd services/core
uv run python -m app.mcp.tokens create --user <auth-user-uuid> --org <org-uuid> --scopes read --name laptop
uv run python -m app.mcp.tokens create --user <uuid> --org <uuid> --scopes read,decide --name elena-desktop
uv run python -m app.mcp.tokens list [--org <uuid>]
uv run python -m app.mcp.tokens revoke --id <token-id>
uv run python -m app.mcp.tokens demo      # upsert MCP_DEMO_TOKEN for the demo viewer (read-only)
```

- `create` refuses a user who is not a member of the org. `decide` implies `read`.
- **Demo token:** set `MCP_DEMO_TOKEN` (any value starting `lgc_`, 16–256 chars) on the core service. On startup
  (and via `tokens demo`) it is upserted for the demo *viewer* in the demo org with scopes forced to `['read']`,
  so the value is safe to hand out for the hosted demo (it is deliberately not committed). Rotate it by changing the env var.
- `last_used_at` is updated on every authenticated call; revocation takes effect on the next request.

## Security model

1. **Authentication.** HTTP requests go through the SDK's `BearerAuthBackend` + `RequireAuthMiddleware` with a
   Ledgic `TokenVerifier`: no / unknown / revoked token → `401` with `WWW-Authenticate: Bearer`; a token without
   `read` → `403`. stdio resolves `LEDGIC_MCP_TOKEN` at start-up and again on every call.
2. **Scopes are a coarse gate.** `read` tokens can never reach the decision RPC (`decide_exception` needs `decide`).
3. **The database is the authority.** Every tool runs in a transaction *as the token's user*
   (`set local role authenticated` + `request.jwt.claims.sub`), so the same RLS policies,
   `security_invoker` views and `security definer` RPC checks that guard the web app apply here:
   - viewers are read-only (`LEDGIC_FORBIDDEN: Read-only access`) — even with a `decide` token;
   - AP managers decide up to the org's manager limit ($5,000 at risk), controllers above it; not-duplicate and
     new-vendor releases need a controller;
   - segregation of duties: whoever edited an invoice's amounts cannot approve it; whoever created a vendor cannot
     release its hold;
   - comments are mandatory where policy says so.
   Refusals come back as tool errors (`Forbidden: …`, `Not found: …`, `Conflict: …`, `Invalid: …`) — never as a
   partial write. Every decision writes `approvals` + hash-chained `audit_log` rows and resumes the paused
   pipeline run.
4. **Rate limit.** 60 tool calls / minute / token (`rate_limit_hit('mcp:token:<id>')`).
5. **Cost cap.** `ask_ledgic` / `search_contracts` share the global daily AI budget; when it is spent they answer
   from cache or retrieval only.
6. Transport: stateless streamable HTTP with JSON responses (no sticky sessions, survives redeploys). DNS-rebinding
   host checks are off because a browser cannot attach the bearer token.

## Example conversation (Claude Desktop, Elena's `read,decide` token)

> **You:** What's waiting for me in AP?
>
> *Claude calls `list_exceptions`* → 14 open; top: PS-88214 · Protein Supplier · Riverside · price variance ·
> $88.00 at risk · recommendation short-pay $2,759.60 / hold $88.00 (confidence 0.94).
>
> **You:** Why is PS-88214 held?
>
> *Claude calls `explain_match("PS-88214")` and `search_contracts("shrimp 16/20 price Protein Supplier")`*
> "Line 1 (Shrimp 16/20 IQF) is billed at $4.12/lb; the contract price is $3.68/lb (*Protein Supplier
> agreement §4.2*). Line 1 is +12.0% against a ±2% limit and $88.00 against a $25 limit — it fails both, so the
> invoice holds for approval. GRN-RS-4410 shows everything was received. Ledgic recommends paying $2,759.60 and
> holding $88.00."
>
> **You:** Do it.
>
> *Claude calls `decide_exception(exception_id=…, action="short_pay")`* → "Recorded 'short_pay'; it is now
> resolved. The paused pipeline run will resume." The decision shows up in the web app's audit trail, attributed
> to Elena.
>
> With the public demo token the last step instead returns
> `Error executing tool decide_exception: Forbidden: this token lacks the 'decide' scope` — and a viewer token
> that somehow had `decide` would still get `Forbidden: Read-only access` from the database.

## Mounting in core (FastAPI)

```python
from contextlib import asynccontextmanager
from app.mcp.http import http_app, mcp_lifespan

@asynccontextmanager
async def lifespan(app):
    await open_pool()
    async with mcp_lifespan():      # runs the MCP session manager; mints MCP_DEMO_TOKEN
        yield
    await close_pool()

app = FastAPI(lifespan=lifespan)
app.add_route("/mcp", http_app(), methods=["GET", "POST", "DELETE"])
```

Use `add_route`, not `app.mount("/mcp", …)`: a mount 307-redirects `/mcp` → `/mcp/` and MCP clients don't follow
redirects. `CORE_PUBLIC_URL` (optional) sets the issuer URL advertised by the auth settings.

## Tests

```bash
cd services/core
COVERAGE_FILE=.coverage.mcp uv run pytest tests/mcp -q
```

In-memory client (tool/resource/prompt surface, auth failures, scope enforcement), HTTP via the FastAPI mount
(401s, scoped sessions), the real `ledgic-mcp` stdio subprocess, and — once the demo org is seeded — the demo
viewer being refused by `rpc_decide_exception`. DB tests skip with a reason when local Supabase is not running.
