"""ERP posting adapters. Ledgic ships deterministic mocks for QuickBooks Online and NetSuite (D5)."""

from .base import (
    BillLine,
    BillRequest,
    ErpAdapter,
    PostingRefused,
    PostingResult,
    PostingValidationError,
)
from .mock import MockErp, adapter_for, modeled_latency_ms

__all__ = [
    "BillLine",
    "BillRequest",
    "ErpAdapter",
    "MockErp",
    "PostingRefused",
    "PostingResult",
    "PostingValidationError",
    "adapter_for",
    "modeled_latency_ms",
]
