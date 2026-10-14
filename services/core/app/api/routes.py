"""/v1 endpoints: ingest, runs, copilot, exception drafts (contracts/core-api.md)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db.pool import connection
from app.repo import journal
from app.repo import runs as runs_repo
from app.repo.sql import exists_fn, val

from .auth import Principal, byok, client_ip, require_role, user_only, user_or_service
from .envelope import ApiError, as_json, ok

log = logging.getLogger("ledgic.api")
router = APIRouter(prefix="/v1")

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 3
UPLOADS_PER_DAY = 10
BYOK_TTL_S = 900


# ------------------------------------------------------------------------------------------- ingest


class IngestBody(BaseModel):
    org_id: str
    channel: Literal["upload", "photo", "email", "portal", "edi"] = "upload"
    storage_path: str
    original_filename: str | None = None
    source_meta: dict[str, Any] = Field(default_factory=dict)
    extraction_mode: Literal["live", "recorded", "simulated"] | None = None


def sniff_mime(blob: bytes, name: str | None) -> str:
    if blob[:5] == b"%PDF-":
        return "application/pdf"
    if blob[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "image/webp"
    raise ApiError(
        "INVALID", f"Unsupported file type{f' ({name})' if name else ''}: upload a PDF, JPEG or PNG"
    )


def pdf_pages(blob: bytes) -> int:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(blob)
    except Exception as e:
        raise ApiError("INVALID", "The PDF could not be read") from e
    try:
        return len(pdf)
    finally:
        pdf.close()


def phash_of(blob: bytes, mime: str) -> str | None:
    try:
        from app.demo.corpus.photo import phash_hex

        return phash_hex(blob, mime)
    except Exception:
        try:
            import imagehash
            from PIL import Image

            if mime.startswith("image/"):
                return str(imagehash.phash(Image.open(io.BytesIO(blob))))
        except Exception:
            return None
    return None


def _remember_key(request: Request, run_id: str, key: str) -> None:
    keys: dict[str, str] = request.app.state.byok_keys
    keys[run_id] = key
    asyncio.get_running_loop().call_later(BYOK_TTL_S, keys.pop, run_id, None)


@router.post("/documents/ingest", status_code=201)
async def ingest(body: IngestBody, request: Request, p: Principal = Depends(user_or_service)) -> Any:
    await require_role(p, body.org_id, "ap_clerk")
    prefix = f"org/{body.org_id}/"
    if not body.storage_path.startswith(prefix) or ".." in body.storage_path:
        raise ApiError("INVALID", "storage_path must be under the organization's prefix")
    if not p.is_service:
        async with connection() as conn:
            if await exists_fn(conn, "rate_limit_hit") and await val(
                conn,
                "select public.rate_limit_hit(%s, %s, %s) as over",
                (f"upload:ip:{client_ip(request)}", UPLOADS_PER_DAY, 86400),
            ):
                raise ApiError("RATE_LIMITED", "Upload limit reached for today (10 per day)")
    from app.repo.storage import download_object

    try:
        blob = await download_object(body.storage_path, max_bytes=MAX_BYTES)
    except FileNotFoundError as e:
        raise ApiError("NOT_FOUND", "Uploaded file not found in storage") from e
    except ValueError as e:
        raise ApiError("INVALID", "File is larger than 10 MB") from e
    mime = sniff_mime(blob, body.original_filename)
    pages = pdf_pages(blob) if mime == "application/pdf" else 1
    if pages > MAX_PAGES:
        raise ApiError("INVALID", f"Documents are limited to {MAX_PAGES} pages")
    sha = hashlib.sha256(blob).hexdigest()
    phash = await asyncio.to_thread(phash_of, blob, mime)
    mode = body.extraction_mode or (
        "live" if not p.is_service else body.source_meta.get("extraction_mode", "live")
    )
    if mode != "live":
        mode = "live"  # uploads have no fixture: simulated/recorded only exist for planned demo documents
    meta = {**body.source_meta, "extraction_mode": mode}
    if p.user_id:
        meta.setdefault("uploaded_by", p.user_id)
    now = datetime.now(UTC)
    async with connection() as conn, conn.transaction():
        existing = await runs_repo.find_document_by_sha(conn, body.org_id, sha)
        if existing is not None:
            run = await runs_repo.latest_run_for_document(conn, str(existing["id"]))
            if run is not None:
                await journal.emit_event(
                    conn,
                    org_id=body.org_id,
                    run_id=str(run["id"]),
                    stage="intake",
                    status="skipped",
                    at=now,
                    summary="Re-delivery ignored — same SHA-256",
                    sub=f"{body.channel} · {body.original_filename or body.storage_path}",
                    detail={"redelivered": True, "storage_path": body.storage_path, "actor_id": p.user_id},
                )
            await journal.write_audit(
                conn,
                org_id=body.org_id,
                actor_type="user" if p.user_id else "system",
                actor_id=p.user_id,
                action="document.redelivered",
                entity_type="document",
                entity_id=str(existing["id"]),
                after={"sha256": sha, "storage_path": body.storage_path},
            )
            return ok(
                {"document_id": str(existing["id"]), "run_id": None, "run_number": None, "redelivered": True},
                201,
            )
        doc = await runs_repo.insert_document(
            conn,
            org_id=body.org_id,
            channel=body.channel,
            storage_path=body.storage_path,
            sha256=sha,
            mime=mime,
            received_at=now,
            page_count=pages,
            phash=phash,
            original_filename=body.original_filename,
            source_meta=meta,
        )
        assert doc is not None
        run = await runs_repo.create_run(
            conn,
            org_id=body.org_id,
            document_id=str(doc["id"]),
            started_at=now,
            context={"extraction_mode": mode},
            workflow_version=request.app.state.settings.orchestrator_version,
        )
    if (k := byok(request)) is not None:
        _remember_key(request, str(run["id"]), k)
    worker = getattr(request.app.state, "worker", None)
    if worker is not None:
        worker.wake()
    return ok(
        {
            "document_id": str(doc["id"]),
            "run_id": str(run["id"]),
            "run_number": int(run["run_number"]),
            "redelivered": False,
        },
        201,
    )


# ------------------------------------------------------------------------------------------- runs


async def _run_for(p: Principal, run_id: str) -> dict[str, Any]:
    async with connection() as conn:
        try:
            run = await runs_repo.get_run(conn, run_id)
        except Exception as e:
            raise ApiError("NOT_FOUND", "Run not found") from e
    if run is None:
        raise ApiError("NOT_FOUND", "Run not found")
    await require_role(p, str(run["org_id"]), "viewer")
    return run


RUN_FIELDS = (
    "id",
    "run_number",
    "org_id",
    "document_id",
    "invoice_id",
    "status",
    "current_stage",
    "next_stage",
    "attempt",
    "next_attempt_at",
    "wait_exception_id",
    "last_error",
    "workflow_version",
    "started_at",
    "finished_at",
)


@router.post("/runs/{run_id}/wake", status_code=202)
async def wake(run_id: str, request: Request, p: Principal = Depends(user_or_service)) -> Any:
    run = await _run_for(p, run_id)
    async with connection() as conn:
        await runs_repo.notify_run(conn, run_id)
    worker = getattr(request.app.state, "worker", None)
    if worker is not None:
        worker.wake()
    return ok({"run_id": run_id, "status": run["status"], "queued": run["status"] == "running"}, 202)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, p: Principal = Depends(user_or_service)) -> Any:
    run = await _run_for(p, run_id)
    async with connection() as conn:
        events = await runs_repo.run_events(conn, run_id)
    return ok({"run": as_json({k: run.get(k) for k in RUN_FIELDS}), "events": as_json(events)})


# ------------------------------------------------------------------------------------------- copilot


class AskBody(BaseModel):
    org_id: str
    question: str = Field(min_length=1, max_length=500)
    context: dict[str, Any] | None = None
    stream: bool = False


@router.post("/copilot/ask")
async def copilot_ask(body: AskBody, request: Request, p: Principal = Depends(user_only)) -> Any:
    await require_role(p, body.org_id, "viewer")
    if not p.is_service:
        async with connection() as conn:
            if await exists_fn(conn, "rate_limit_hit") and await val(
                conn,
                "select public.rate_limit_hit(%s, %s, %s) as over",
                (f"copilot:user:{p.user_id}", 60, 3600),
            ):
                raise ApiError("RATE_LIMITED", "Too many questions — try again in a while")
    from app.ai import ask, sse, stream_ask

    key = byok(request)
    wants_sse = body.stream or "text/event-stream" in (request.headers.get("accept") or "")
    if wants_sse:

        async def gen():  # type: ignore[no-untyped-def]
            try:
                async for ev in stream_ask(body.org_id, body.question, body.context, key):
                    yield sse(ev)
            except Exception as e:
                log.warning("copilot stream failed: %s", type(e).__name__)
                yield sse(
                    {
                        "event": "error",
                        "data": {"code": "INTERNAL", "message": "Copilot failed", "retryable": True},
                    }
                )

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    ans = await ask(body.org_id, body.question, body.context, key)
    return ok(as_json(ans.to_dict()))


# ------------------------------------------------------------------------------------------- drafts


class DraftBody(BaseModel):
    kind: Literal["vendor_notice", "explanation"] = "vendor_notice"
    regenerate: bool = False


@router.post("/exceptions/{exception_id}/draft")
async def exception_draft(
    exception_id: str, body: DraftBody, request: Request, p: Principal = Depends(user_or_service)
) -> Any:
    async with connection() as conn:
        try:
            org = await val(conn, "select org_id::text from exceptions where id = %s", (exception_id,))
        except Exception:
            org = None
    if org is None:
        raise ApiError("NOT_FOUND", "Exception not found")
    await require_role(p, org, "ap_clerk")
    from app.ai import draft_for_exception

    d = await draft_for_exception(exception_id, byok(request), kind=body.kind, regenerate=body.regenerate)
    return ok(as_json(d.to_dict()))
