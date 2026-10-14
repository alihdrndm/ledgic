"""01 Intake: the document is stored and hashed (re-deliveries never get here — see /v1/documents/ingest)."""

from __future__ import annotations

from app.repo import journal
from app.repo import runs as runs_repo
from app.repo.sql import val

from ..context import RunRow, StageContext
from ..stages import Stage
from ..transitions import FatalStageError, Transition
from .common import channel_label, plural


async def handle(ctx: StageContext, run: RunRow) -> Transition:
    doc = await runs_repo.get_document(ctx.conn, run.document_id)
    if doc is None:
        raise FatalStageError(f"document {run.document_id} not found")
    meta = doc.get("source_meta") or {}
    pages = int(doc.get("page_count") or 1)
    label = channel_label(doc["channel"], doc.get("mime"))
    summary = f"Received — {label}" + ("" if doc["channel"] == "edi" else f", {plural(pages, 'page')}")
    ch = doc["channel"]
    if ch == "email":
        where = meta.get("inbox") or "ap@northside.ledgic.dev"
    elif ch == "photo":
        loc = None
        if meta.get("location_id"):
            loc = await val(ctx.conn, "select name from locations where id = %s", (meta["location_id"],))
        where = f"Dock capture · {loc}" if loc else "Dock capture"
    elif ch == "portal":
        where = "Supplier portal"
    elif ch == "edi":
        where = "EDI interchange"
    else:
        where = "Uploaded in Ledgic"
    await journal.write_audit(
        ctx.conn,
        org_id=run.org_id,
        actor_type="core",
        actor_id="intake",
        action="document.received",
        entity_type="document",
        entity_id=run.document_id,
        after={"channel": ch, "sha256": doc["sha256"], "pages": pages, "mime": doc["mime"]},
        at=ctx.now(),
    )
    return Transition.advance(
        Stage.EXTRACTION,
        summary,
        f"{where} · SHA-256 stored",
        detail={"channel": ch, "pages": pages, "sha256": doc["sha256"], "mime": doc["mime"]},
    )
