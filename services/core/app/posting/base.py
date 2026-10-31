"""ERP posting interface (06 §9): create_bill(invoice, lines, pay, hold, coding) -> PostingResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class BillLine:
    line_no: int
    description: str
    qty: Decimal | None
    unit_price: Decimal | None
    amount: Decimal  # amount payable on this line (expected price for short-pays)
    gl_number: str | None
    gl_name: str | None


@dataclass(frozen=True)
class BillRequest:
    invoice_id: str
    posting_key: str  # idempotency key (RequestId)
    vendor_id: str | None
    vendor_name: str | None
    entity_short_code: str | None
    entity_ref: str | None
    location_code: str | None
    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None
    lines: tuple[BillLine, ...]
    pay_amount: Decimal
    hold_amount: Decimal
    memo: str
    duplicate_of: str | None = None

    def as_json(self, system: str) -> dict[str, Any]:
        """The request body as the real API would receive it (QBO Bill / NetSuite vendorBill shape)."""
        if system == "quickbooks":
            return {
                "RequestId": self.posting_key,
                "VendorRef": {"name": self.vendor_name, "value": self.vendor_id},
                "DocNumber": self.invoice_number,
                "TxnDate": self.invoice_date.isoformat() if self.invoice_date else None,
                "DueDate": self.due_date.isoformat() if self.due_date else None,
                "PrivateNote": self.memo,
                "TotalAmt": f"{self.pay_amount:.2f}",
                "Line": [
                    {
                        "LineNum": ln.line_no,
                        "Description": ln.description,
                        "Amount": f"{ln.amount:.2f}",
                        "DetailType": "AccountBasedExpenseLineDetail",
                        "AccountBasedExpenseLineDetail": {
                            "AccountRef": {"name": f"{ln.gl_number} {ln.gl_name}" if ln.gl_number else None},
                            "ClassRef": {"name": self.location_code},
                        },
                    }
                    for ln in self.lines
                ],
            }
        return {
            "externalId": self.posting_key,
            "entity": {"refName": self.vendor_name},
            "subsidiary": {"refName": self.entity_short_code},
            "location": {"refName": self.location_code},
            "tranId": self.invoice_number,
            "tranDate": self.invoice_date.isoformat() if self.invoice_date else None,
            "dueDate": self.due_date.isoformat() if self.due_date else None,
            "memo": self.memo,
            "userTotal": f"{self.pay_amount:.2f}",
            "expense": {
                "items": [
                    {
                        "line": ln.line_no,
                        "memo": ln.description,
                        "amount": f"{ln.amount:.2f}",
                        "account": {"refName": f"{ln.gl_number} {ln.gl_name}" if ln.gl_number else None},
                        "location": {"refName": self.location_code},
                    }
                    for ln in self.lines
                ]
            },
        }


@dataclass(frozen=True)
class PostingResult:
    ok: bool
    system: str
    external_id: str | None
    display_ref: str | None  # 'Bill 18,240'
    response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: int = 0
    retryable: bool = True


class PostingRefused(Exception):
    """The adapter refuses to post (e.g. the invoice is a duplicate copy). Never retried."""


class PostingValidationError(Exception):
    """The bill cannot be built as a valid ERP document (missing account, lines that miss the total)."""


class ErpAdapter(Protocol):
    system: str
    label: str

    async def create_bill(self, req: BillRequest, *, fail: bool = False) -> PostingResult: ...
