"""Response envelope `{ok, data | error}` and error mapping (contracts/core-api.md)."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.repo.sql import dumps

log = logging.getLogger("ledgic.api")

STATUS = {
    "UNAUTHENTICATED": 401,
    "INVALID_SIGNATURE": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "INVALID": 422,
    "RATE_LIMITED": 429,
    "BUDGET_EXHAUSTED": 429,
    "LLM_RATE_LIMITED": 502,
    "LLM_BAD_OUTPUT": 502,
    "DB_UNAVAILABLE": 503,
    "INTERNAL": 500,
}
RETRYABLE = {"RATE_LIMITED", "LLM_RATE_LIMITED", "LLM_BAD_OUTPUT", "DB_UNAVAILABLE"}


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status or STATUS.get(code, 500)


class EnvelopeResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return dumps(content).encode("utf-8")


def ok(data: Any, status: int = 200) -> EnvelopeResponse:
    return EnvelopeResponse({"ok": True, "data": data}, status_code=status)


def err(code: str, message: str, status: int | None = None) -> EnvelopeResponse:
    return EnvelopeResponse(
        {"ok": False, "error": {"code": code, "message": message, "retryable": code in RETRYABLE}},
        status_code=status or STATUS.get(code, 500),
    )


def map_db_error(e: psycopg.Error) -> ApiError | None:
    """`LEDGIC_<CODE>: message` raised by RPCs → API error (rpc.md error convention)."""
    msg = (getattr(e.diag, "message_primary", None) or str(e)).strip()
    if msg.startswith("LEDGIC_"):
        code, _, text = msg.partition(":")
        code = code.removeprefix("LEDGIC_")
        return ApiError(code if code in STATUS else "INVALID", text.strip() or msg)
    return None


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError) -> JSONResponse:
        return err(e.code, e.message, e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0] if e.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        return err("INVALID", f"{loc}: {first.get('msg', 'invalid request')}".strip(": "))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "INVALID",
            409: "CONFLICT",
            429: "RATE_LIMITED",
        }.get(e.status_code, "INTERNAL")
        return err(code, str(e.detail), e.status_code)

    @app.exception_handler(psycopg.OperationalError)
    async def _db_down(_: Request, e: psycopg.OperationalError) -> JSONResponse:
        log.warning("db unavailable: %s", e)
        return err("DB_UNAVAILABLE", "Database unavailable")

    @app.exception_handler(psycopg.Error)
    async def _db(_: Request, e: psycopg.Error) -> JSONResponse:
        mapped = map_db_error(e)
        if mapped:
            return err(mapped.code, mapped.message, mapped.status)
        log.exception("db error")
        return err("INTERNAL", "Database error")

    @app.exception_handler(Exception)
    async def _any(_: Request, e: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return err("INTERNAL", "Internal error")


def money(v: Decimal | None) -> str | None:
    return None if v is None else f"{v:.2f}"


def as_json(obj: Any) -> Any:
    return json.loads(dumps(obj))
