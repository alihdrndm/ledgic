"""Deterministic mock QuickBooks Online and NetSuite adapters (DECISIONS D5).

* Ids are derived from the invoice id, so re-posting the same invoice returns the same Bill id.
* Latency 300–900 ms (deterministic per invoice); `latency=False` skips the sleep (backfill, tests)
  but still reports the modeled latency so durations stay realistic.
* Duplicate copies (invoices with `duplicate_of`) are refused: they can never be paid (01 §3.6).
* `fail=True` simulates an outage (503) — used for failure injection in tests and demos.
"""

from __future__ import annotations

import asyncio
import hashlib

from .base import BillRequest, PostingRefused, PostingResult


def _h(invoice_id: str, salt: str) -> int:
    return int(hashlib.sha256(f"{salt}:{invoice_id}".encode()).hexdigest()[:12], 16)


def modeled_latency_ms(invoice_id: str) -> int:
    return 300 + _h(invoice_id, "latency") % 601


class MockErp:
    def __init__(self, system: str, *, latency: bool = True) -> None:
        if system not in ("quickbooks", "netsuite"):
            raise ValueError(system)
        self.system = system
        self.label = "QuickBooks" if system == "quickbooks" else "NetSuite"
        self.latency = latency

    def external_id(self, invoice_id: str) -> str:
        if self.system == "quickbooks":
            return str(10_000 + _h(invoice_id, "qbo") % 90_000)
        return str(1_000_000 + _h(invoice_id, "ns") % 9_000_000)

    def display_ref(self, external_id: str) -> str:
        noun = "Bill" if self.system == "quickbooks" else "vendorBill"
        return f"{noun} {int(external_id):,}"

    async def create_bill(self, req: BillRequest, *, fail: bool = False) -> PostingResult:
        if req.duplicate_of:
            raise PostingRefused(
                f"invoice {req.invoice_id} is a duplicate of {req.duplicate_of}; payment blocked"
            )
        ms = modeled_latency_ms(req.invoice_id)
        if self.latency:
            await asyncio.sleep(ms / 1000)
        if fail:
            msg = f"{self.label} API 503 Service Unavailable (mock outage)"
            return PostingResult(
                False, self.system, None, None, {"mock": True, "status": 503, "error": msg}, msg, ms
            )
        ext = self.external_id(req.invoice_id)
        body = req.as_json(self.system)
        if self.system == "quickbooks":
            response = {
                "mock": True,
                "Bill": {
                    "Id": ext,
                    "SyncToken": "0",
                    "TotalAmt": body["TotalAmt"],
                    "DocNumber": req.invoice_number,
                },
            }
        else:
            response = {
                "mock": True,
                "id": ext,
                "links": [{"rel": "self", "href": f"/record/v1/vendorBill/{ext}"}],
            }
        return PostingResult(True, self.system, ext, self.display_ref(ext), response, None, ms)


def adapter_for(system: str | None, *, latency: bool = True) -> MockErp:
    """Only mocks ship with Ledgic; real QBO/NetSuite would plug in here (06 §9)."""
    return MockErp(system if system in ("quickbooks", "netsuite") else "quickbooks", latency=latency)
