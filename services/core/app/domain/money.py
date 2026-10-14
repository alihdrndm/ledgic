"""Decimal helpers and display formatting. Money is always Decimal, never float."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0")

Numberish = Decimal | int | str


def D(value: Numberish) -> Decimal:
    """Coerce to Decimal. Floats are rejected so binary rounding can never leak into money."""
    if isinstance(value, bool):
        raise TypeError("bool is not a number")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError("float is not allowed for money; pass a str or Decimal")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.strip().replace(",", "").replace("$", ""))
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal: {value!r}") from exc
    raise TypeError(f"cannot convert {type(value).__name__} to Decimal")


def conf(value: Numberish | float) -> Decimal:
    """Coerce a confidence (0-1) to Decimal. Floats are accepted here (they are not money)."""
    if isinstance(value, float):
        return Decimal(repr(value))
    return D(value)


def quantize(value: Numberish, places: int) -> Decimal:
    return D(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def cents(value: Numberish) -> Decimal:
    """Round to cents, half up."""
    return quantize(value, 2)


def fmt_money(value: Numberish, *, sign: bool = False) -> str:
    """'$2,759.60'; negatives '-$5.00'; sign=True adds '+' to positives ('+$88.00')."""
    v = cents(value)
    body = f"${abs(v):,.2f}"
    if v < 0:
        return "-" + body
    if sign and v > 0:
        return "+" + body
    return body


def fmt_money_short(value: Numberish) -> str:
    """'$25' for whole dollars, else '$25.50' (used for policy limits)."""
    v = cents(value)
    if v == v.to_integral_value():
        return f"${int(v):,}"
    return fmt_money(v)


def fmt_unit_price(value: Numberish) -> str:
    """Unit prices: at least 2 decimals, up to 4 ('$3.68', '$3.6825')."""
    v = D(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    exp = v.normalize().as_tuple().exponent
    places = min(4, max(2, -exp)) if isinstance(exp, int) else 2
    return f"${v:,.{places}f}"


def fmt_pct(ratio: Numberish, places: int = 1) -> str:
    """Ratio -> signed percent with one decimal: Decimal('0.11957') -> '+12.0%'."""
    p = quantize(D(ratio) * 100, places)
    if p == 0:
        return f"{abs(p):.{places}f}%"
    return f"{'+' if p > 0 else '-'}{abs(p):.{places}f}%"


def fmt_pct_limit(ratio: Numberish) -> str:
    """Policy percentage without trailing zeros: Decimal('0.02') -> '2%', '0.025' -> '2.5%'."""
    p = (D(ratio) * 100).normalize()
    return f"{p:f}%"


def fmt_qty(value: Numberish) -> str:
    """Quantities without trailing zeros: '12.000' -> '12', '2.50' -> '2.5'."""
    v = D(value).normalize()
    if v == v.to_integral_value():
        return f"{int(v):,}"
    return f"{v:f}"


def fmt_conf(value: Numberish | float, places: int = 2) -> str:
    """Confidence display: 0.94 -> '0.94'."""
    return f"{quantize(conf(value), places):.{places}f}"
