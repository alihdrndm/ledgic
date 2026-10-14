"""The Ledgic MCP server (mcp 2.x `MCPServer`, formerly FastMCP).

Tools are thin wrappers over `app.mcp.service`: resolve the caller's token, check its scope, rate-limit,
then run the query as that user so the database enforces RLS, role limits and segregation of duties.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Any, Literal

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from pydantic import Field

from . import service
from .auth import require

INSTRUCTIONS = """\
Ledgic is an accounts-payable automation system: invoices arrive (email, photo, portal, EDI), are extracted
by an AI agent, three-way matched against purchase orders and goods receipts, and anything outside policy
becomes an *exception* that a person decides (short-pay, approve, dispute, reject, ...).

How to use these tools well:
- Start with `list_exceptions` to see what needs a decision, `get_kpis` for how AP is performing.
- `get_invoice` and `explain_match` take the human invoice number (e.g. "PS-88214"). `explain_match`
  returns the exact tolerance math per line plus the system's recommendation — quote its sentences
  rather than recomputing.
- `search_contracts` finds contract clauses / AP policy passages with citations (clause_ref); cite them.
- `ask_ledgic` runs Ledgic's own RAG copilot for open questions (slower, cost-capped).
- `decide_exception` records a real decision. Only call it when the user explicitly asks you to decide,
  and confirm the action and amounts first. The database enforces roles, approval limits and segregation
  of duties; a refusal comes back as "Forbidden: ..." — relay it, do not retry with other actions.
- Money values are decimal strings in USD ("2759.60"); percentages are fractions ("0.02" = 2%).
"""

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

ExceptionType = Literal[
    "extraction_review",
    "price_variance",
    "qty_mismatch",
    "no_po",
    "unmatched_line",
    "duplicate",
    "new_vendor_screen",
    "posting_failed",
]
DecisionAction = Literal[
    "short_pay",
    "approve_as_is",
    "dispute",
    "reject_invoice",
    "link_po",
    "approve_without_po",
    "merge",
    "reject_copy",
    "not_duplicate",
    "request_w9",
    "release_hold",
    "retry_posting",
]


async def _read_ctx():
    ctx = await require("read")
    await service.rate_limit(ctx)
    return ctx


def build_server(
    token_verifier: TokenVerifier | None = None, *, issuer_url: str = "http://localhost:8000"
) -> MCPServer:
    """Build the server. Pass a `token_verifier` for HTTP (bearer auth enforced by the SDK middleware);
    leave it None for stdio / in-memory use, where the token comes from `auth.use_local_token`."""
    auth = (
        AuthSettings(issuer_url=issuer_url, resource_server_url=None, required_scopes=["read"])
        if token_verifier is not None
        else None
    )
    mcp = MCPServer(
        "ledgic",
        title="Ledgic AP automation",
        description="Accounts-payable exceptions, three-way match, contracts RAG and DB-enforced approvals.",
        instructions=INSTRUCTIONS,
        website_url="https://github.com/alihdrndm/ledgic",
        version="0.1.0",
        token_verifier=token_verifier,
        auth=auth,
    )

    # ---- tools -------------------------------------------------------------------------------

    @mcp.tool(title="List AP exceptions", annotations=READ_ONLY)
    async def list_exceptions(
        status: Annotated[
            Literal["open", "all", "resolved", "awaiting_vendor", "disputed", "escalated"],
            Field(description="'open' = everything not yet resolved (default); 'all' includes resolved."),
        ] = "open",
        type: Annotated[
            ExceptionType | None,
            Field(description="Only this exception type, e.g. 'price_variance' or 'duplicate'."),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Max rows (1-100).")] = 20,
    ) -> dict[str, Any]:
        """List accounts-payable exceptions waiting for a person: price variances, quantity mismatches,
        missing POs, suspected duplicates, new-vendor fraud screens, failed ERP postings.

        Each row has the exception_id (needed for decide_exception), invoice_number, vendor, location,
        amount_at_risk (USD decimal string), reason, age, whether payment is blocked, and the system's
        recommendation (action + pay/hold amounts + confidence). Risk holds (duplicates, vendor screens)
        sort first, then oldest first."""
        ctx = await _read_ctx()
        return await service.list_exceptions(ctx, status=status, type=type, limit=limit)

    @mcp.tool(title="Get invoice", annotations=READ_ONLY)
    async def get_invoice(
        invoice_number: Annotated[
            str, Field(description="Vendor invoice number, e.g. 'PS-88214' (or invoice UUID).")
        ],
    ) -> dict[str, Any]:
        """Everything about one invoice: header (vendor, location, dates, totals, PO/GRN), extracted lines
        with GL coding, the three-way-match verdict, its exceptions with recommendations and decisions,
        and the ERP posting. Invoice numbers are matched ignoring punctuation and case; if several invoices
        share the number (e.g. a suspected duplicate) the newest is returned and the others are listed."""
        ctx = await _read_ctx()
        return await service.get_invoice(ctx, invoice_number)

    @mcp.tool(title="Explain three-way match", annotations=READ_ONLY)
    async def explain_match(
        invoice_number: Annotated[str, Field(description="Vendor invoice number, e.g. 'PS-88214'.")],
    ) -> dict[str, Any]:
        """Explain why an invoice did or did not pass three-way match (invoice vs PO vs goods receipt).

        Per line: invoiced qty/price/amount, PO and received quantities, the expected unit price and its
        source (contract clause or PO), delta, allowed tolerance and a plain-English sentence such as
        "Line 1 is +12.0% against a ±2% limit and $88.00 against a $25 limit — it fails both, so the invoice
        holds for approval." Also returns the tolerance rule, the recommended action (e.g. short-pay with
        pay/hold amounts) and any decision already taken. Prefer quoting these sentences verbatim."""
        ctx = await _read_ctx()
        return await service.explain_match(ctx, invoice_number)

    @mcp.tool(title="Search contracts & policy", annotations=READ_ONLY)
    async def search_contracts(
        query: Annotated[
            str, Field(description="What to look for, e.g. 'shrimp price per lb Protein Supplier'.")
        ],
        k: Annotated[int, Field(ge=1, le=20, description="Number of passages (1-20).")] = 5,
        kind: Annotated[
            Literal["contract", "policy", "vendor_note"] | None,
            Field(description="Restrict to one document kind; default searches all."),
        ] = None,
    ) -> dict[str, Any]:
        """Search Ledgic's knowledge base — vendor contracts, the AP policy and vendor notes — with hybrid
        (vector + full-text) retrieval. Returns numbered passages with title, clause_ref (e.g. "4.2") and a
        quote. Cite results as "<title> §<clause_ref>". Falls back to keyword search if embeddings are
        unavailable (mode = text_only)."""
        ctx = await _read_ctx()
        return await service.search_contracts(ctx, query, k=k, kind=kind)

    @mcp.tool(
        title="Ask Ledgic copilot", annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False)
    )
    async def ask_ledgic(
        question: Annotated[
            str,
            Field(max_length=500, description="A question about invoices, vendors, contracts or AP policy."),
        ],
    ) -> dict[str, Any]:
        """Ask Ledgic's own copilot agent (RAG over contracts/policy plus read-only tools over invoices and
        KPIs). Returns a markdown answer with numbered citations. It is cost-capped: when the daily AI
        budget is spent it answers from cached or retrieval-only results (see `mode`). Prefer the specific
        tools when you already know what to fetch."""
        ctx = await _read_ctx()
        return await service.ask_ledgic(ctx, question)

    @mcp.tool(title="AP KPIs", annotations=READ_ONLY)
    async def get_kpis(
        period: Annotated[
            Literal["mtd", "qtd", "l30"],
            Field(description="'mtd' month-to-date (default), 'qtd' quarter-to-date, 'l30' last 30 days."),
        ] = "mtd",
    ) -> dict[str, Any]:
        """Operations KPIs for the period: invoice volume, touchless rate, cost per invoice (LLM/OCR/infra/
        human), median cycle time, money held (variances, duplicates, fraud), short-pays accepted, decision
        speed, audit coverage, top catches and ERP sync health — plus today's queue counts."""
        ctx = await _read_ctx()
        return await service.get_kpis(ctx, period)

    @mcp.tool(title="Verify audit chain", annotations=READ_ONLY)
    async def verify_audit_chain() -> dict[str, Any]:
        """Recompute the organization's hash-chained audit log and report whether it is intact
        (ok, number of entries, head hash, or the first broken entry id)."""
        ctx = await _read_ctx()
        return await service.verify_audit_chain(ctx)

    @mcp.tool(
        title="Decide an exception",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
        ),
    )
    async def decide_exception(
        exception_id: Annotated[str, Field(description="exception_id from list_exceptions / get_invoice.")],
        action: Annotated[
            DecisionAction, Field(description="The decision. Allowed actions depend on the exception type.")
        ],
        comment: Annotated[
            str | None,
            Field(
                description="Required for approve_as_is, approve_without_po, not_duplicate, "
                "dispute, release_hold."
            ),
        ] = None,
        pay_amount: Annotated[
            Decimal | None,
            Field(description="short_pay only: amount to pay now (USD). Omit to use the recommendation."),
        ] = None,
        hold_amount: Annotated[
            Decimal | None,
            Field(
                description="short_pay only: amount to hold back; pay + hold must equal the invoice total."
            ),
        ] = None,
        extra: Annotated[
            dict[str, Any] | None,
            Field(
                description='Action-specific fields: link_po → {"po_id": uuid}; '
                'merge → {"keep_invoice_id": uuid}; '
                'release_hold → {"verified_by_phone": true}.'
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Record a decision on an exception, exactly as if the token's user clicked it in the Ledgic UI.

        Actions by type: price_variance / qty_mismatch / unmatched_line → short_pay, approve_as_is, dispute,
        reject_invoice; no_po → link_po, approve_without_po, reject_invoice; duplicate → merge, reject_copy,
        not_duplicate; new_vendor_screen → request_w9, release_hold, reject_invoice; posting_failed →
        retry_posting, reject_invoice.

        Requires a token with the 'decide' scope. The database then enforces the user's role (viewers are
        read-only; AP managers up to $5,000 at risk; controllers above), segregation of duties and comment
        rules, writes the approval and audit rows, and resumes the paused pipeline run. Ask the user to
        confirm before calling."""
        ctx = await require("decide")
        await service.rate_limit(ctx)
        return await service.decide_exception(
            ctx,
            exception_id,
            action,
            comment=comment,
            pay_amount=pay_amount,
            hold_amount=hold_amount,
            extra=extra,
        )

    # ---- resources ---------------------------------------------------------------------------

    @mcp.resource(
        "ledgic://policy/ap",
        name="ap-policy",
        title="AP policy",
        description="The organization's accounts-payable policy: tolerances, approval limits, SoD.",
        mime_type="text/markdown",
    )
    def ap_policy() -> str:
        return service.read_ap_policy()

    @mcp.resource(
        "ledgic://exceptions/open",
        name="open-exceptions",
        title="Open exceptions",
        description="Snapshot of the open exception queue (same data as list_exceptions).",
        mime_type="application/json",
    )
    async def open_exceptions() -> str:
        ctx = await _read_ctx()
        data = await service.list_exceptions(ctx, status="open", limit=50)
        return json.dumps(data, indent=1)

    # ---- prompts -----------------------------------------------------------------------------

    @mcp.prompt(title="Triage AP exceptions")
    def triage_exceptions(limit: str = "10") -> str:
        """Walk the open exception queue and propose a decision for each, citing policy."""
        return (
            f"Use the Ledgic tools to triage up to {limit} open AP exceptions.\n"
            "1. Call list_exceptions (status 'open').\n"
            "2. For each price/quantity exception call explain_match on its invoice; "
            "for duplicates and vendor "
            "screens call get_invoice.\n"
            "3. Where a contract price is involved, call search_contracts and cite the clause.\n"
            "4. Produce a table: invoice, vendor, amount at risk, recommended action "
            "(pay/hold amounts), one-line "
            "reason with citation, and who must approve (AP manager ≤ $5,000 at risk, controller above).\n"
            "Do NOT call decide_exception — this is a proposal for a human."
        )

    @mcp.prompt(title="Explain an invoice hold")
    def explain_invoice(invoice_number: str) -> str:
        """Explain to a vendor-facing colleague why an invoice is held and what will be paid."""
        return (
            f"Explain why invoice {invoice_number} is held. Call explain_match and get_invoice, then "
            "search_contracts for the governing clause. Write 3-5 plain sentences: what was billed, what the "
            "contract/PO says (with clause reference), the tolerance result, "
            "and what Ledgic recommends paying "
            "and holding. Use the exact money figures from the tools."
        )

    return mcp
