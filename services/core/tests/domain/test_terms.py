from decimal import Decimal

import pytest

from app.domain.terms import PaymentTerms, parse_payment_terms


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # The formats named in the proposal.
        ("2/10 net 30", PaymentTerms(Decimal("0.02"), 10, 30)),
        ("Net 14", PaymentTerms(None, None, 14)),
        ("2% 10 Net 30", PaymentTerms(Decimal("0.02"), 10, 30)),
        ("Due on receipt", PaymentTerms(None, None, 0)),
        # Real-world variations of the discount form.
        ("1/10 net 60", PaymentTerms(Decimal("0.01"), 10, 60)),
        ("2/15 net 45", PaymentTerms(Decimal("0.02"), 15, 45)),
        ("3/10 net 90", PaymentTerms(Decimal("0.03"), 10, 90)),
        ("1.5/10 net 30", PaymentTerms(Decimal("0.015"), 10, 30)),
        ("2 / 10, net 30", PaymentTerms(Decimal("0.02"), 10, 30)),
        ("2/10 Net30", PaymentTerms(Decimal("0.02"), 10, 30)),
        ("2% 10, NET 30 days", PaymentTerms(Decimal("0.02"), 10, 30)),
        # Net-only and immediate terms.
        ("NET 30", PaymentTerms(None, None, 30)),
        ("net 7 days", PaymentTerms(None, None, 7)),
        ("COD", PaymentTerms(None, None, 0)),
        ("Cash on delivery", PaymentTerms(None, None, 0)),
    ],
)
def test_parse_payment_terms(text: str, expected: PaymentTerms) -> None:
    assert parse_payment_terms(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        "Payment terms to be agreed",
        "30",  # a bare number is ambiguous — don't guess
        "2/10",  # discount shorthand with no net period
        "EOM",  # end of month is not a fixed day count
        "net",  # no number at all
    ],
)
def test_unparseable_terms_return_none(text: str | None) -> None:
    assert parse_payment_terms(text) is None


def test_discount_pct_is_a_decimal_ratio() -> None:
    parsed = parse_payment_terms("2/10 net 30")
    assert parsed is not None
    assert isinstance(parsed.discount_pct, Decimal)
    assert parsed.discount_pct == Decimal("0.02")
