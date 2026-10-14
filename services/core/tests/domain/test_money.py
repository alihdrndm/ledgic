from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.money import (
    D,
    cents,
    conf,
    fmt_conf,
    fmt_money,
    fmt_money_short,
    fmt_pct,
    fmt_pct_limit,
    fmt_qty,
    fmt_unit_price,
)


def test_d_accepts_decimal_int_str() -> None:
    assert D(Decimal("1.5")) == Decimal("1.5")
    assert D(3) == Decimal(3)
    assert D(" $2,759.60 ") == Decimal("2759.60")


@pytest.mark.parametrize("bad", [1.5, True, None, [1]])
def test_d_rejects_float_bool_other(bad: object) -> None:
    with pytest.raises(TypeError):
        D(bad)  # type: ignore[arg-type]


def test_d_rejects_garbage_string() -> None:
    with pytest.raises(ValueError):
        D("abc")


def test_conf_accepts_float() -> None:
    assert conf(0.71) == Decimal("0.71")
    assert conf("0.9") == Decimal("0.9")


def test_cents_half_up() -> None:
    assert cents("2.675") == Decimal("2.68")
    assert cents("2.665") == Decimal("2.67")
    assert cents("-2.675") == Decimal("-2.68")


def test_money_formats() -> None:
    assert fmt_money("2759.6") == "$2,759.60"
    assert fmt_money("-5") == "-$5.00"
    assert fmt_money("88", sign=True) == "+$88.00"
    assert fmt_money("0", sign=True) == "$0.00"
    assert fmt_money_short("25.00") == "$25"
    assert fmt_money_short("25.50") == "$25.50"


def test_pct_formats() -> None:
    assert fmt_pct(Decimal(88) / Decimal(736)) == "+12.0%"
    assert fmt_pct("-0.05") == "-5.0%"
    assert fmt_pct("0") == "0.0%"
    assert fmt_pct_limit("0.02") == "2%"
    assert fmt_pct_limit("0.025") == "2.5%"


def test_qty_unit_conf_formats() -> None:
    assert fmt_qty("12.000") == "12"
    assert fmt_qty("2.50") == "2.5"
    assert fmt_qty("1200") == "1,200"
    assert fmt_unit_price("3.68") == "$3.68"
    assert fmt_unit_price("3.6825") == "$3.6825"
    assert fmt_unit_price("4") == "$4.00"
    assert fmt_conf(0.94) == "0.94"


@given(st.integers(min_value=-(10**9), max_value=10**9), st.integers(min_value=0, max_value=6))
def test_cents_idempotent_and_two_places(n: int, scale: int) -> None:
    v = Decimal(n).scaleb(-scale)
    c = cents(v)
    assert cents(c) == c
    assert c.as_tuple().exponent == -2
    assert abs(c - v) <= Decimal("0.005")
