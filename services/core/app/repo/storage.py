"""Supabase Storage via the REST API with the service-role key (bucket `documents`)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

BUCKET = "documents"
_client: httpx.AsyncClient | None = None


def _headers() -> dict[str, str]:
    key = get_settings().supabase_service_role_key
    return {"Authorization": f"Bearer {key}", "apikey": key}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    return _client


def _url(path: str, bucket: str = BUCKET) -> str:
    return f"{get_settings().supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{path.lstrip('/')}"


async def upload_object(
    path: str, content: bytes, mime: str, *, bucket: str = BUCKET, upsert: bool = True
) -> None:
    r = await client().post(
        _url(path, bucket),
        content=content,
        headers={
            **_headers(),
            "Content-Type": mime,
            "x-upsert": "true" if upsert else "false",
            "cache-control": "3600",
        },
    )
    if r.status_code >= 400:
        raise RuntimeError(f"storage upload {path}: {r.status_code} {r.text[:200]}")


async def download_object(path: str, *, bucket: str = BUCKET, max_bytes: int = 10 * 1024 * 1024) -> bytes:
    r = await client().get(_url(path, bucket), headers=_headers())
    if r.status_code == 404 or (r.status_code == 400 and "not found" in r.text.lower()):
        raise FileNotFoundError(path)
    if r.status_code >= 400:
        raise RuntimeError(f"storage download {path}: {r.status_code} {r.text[:200]}")
    if len(r.content) > max_bytes:
        raise ValueError("object larger than 10 MB")
    return r.content


async def delete_objects(paths: list[str], *, bucket: str = BUCKET) -> int:
    if not paths:
        return 0
    deleted = 0
    for i in range(0, len(paths), 500):
        chunk = paths[i : i + 500]
        r = await client().request(
            "DELETE",
            f"{get_settings().supabase_url.rstrip('/')}/storage/v1/object/{bucket}",
            json={"prefixes": chunk},
            headers=_headers(),
        )
        if r.status_code < 400:
            body: Any = r.json()
            deleted += len(body) if isinstance(body, list) else 0
    return deleted


async def storage_available() -> bool:
    s = get_settings()
    if not s.supabase_service_role_key:
        return False
    try:
        r = await client().get(f"{s.supabase_url.rstrip('/')}/storage/v1/bucket/{BUCKET}", headers=_headers())
        return r.status_code < 400
    except httpx.HTTPError:
        return False
