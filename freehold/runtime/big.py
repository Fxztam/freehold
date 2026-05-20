from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
import math

from freehold.core.ast import BigFloatValue, BigIntegerValue, SourcePos, VerificationError


def decimal_precision(precision_bits: int) -> int:
    if not isinstance(precision_bits, int) or isinstance(precision_bits, bool) or precision_bits < 1:
        raise VerificationError("Big precision must be a positive Integer")
    return max(1, math.ceil(precision_bits * math.log10(2)) + 8)


def integer(text: str) -> BigIntegerValue:
    try:
        return BigIntegerValue(int(text, 10))
    except ValueError as exc:
        raise VerificationError(f"invalid BigInteger literal: {text}") from exc


def from_integer(value: int) -> BigIntegerValue:
    return BigIntegerValue(value)


def float_from_string(text: str, precision_bits: int) -> BigFloatValue:
    precision = decimal_precision(precision_bits)
    try:
        with localcontext() as ctx:
            ctx.prec = precision
            return BigFloatValue(+Decimal(text), precision_bits)
    except InvalidOperation as exc:
        raise VerificationError(f"invalid BigFloat literal: {text}") from exc


def float_from_integer(value: BigIntegerValue, precision_bits: int) -> BigFloatValue:
    precision = decimal_precision(precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(+Decimal(value.value), precision_bits)


def add_int(left: BigIntegerValue, right: BigIntegerValue) -> BigIntegerValue:
    return BigIntegerValue(left.value + right.value)


def sub_int(left: BigIntegerValue, right: BigIntegerValue) -> BigIntegerValue:
    return BigIntegerValue(left.value - right.value)


def mul_int(left: BigIntegerValue, right: BigIntegerValue) -> BigIntegerValue:
    return BigIntegerValue(left.value * right.value)


def div_int(left: BigIntegerValue, right: BigIntegerValue, pos: SourcePos) -> BigIntegerValue:
    if right.value == 0:
        raise VerificationError(f"{pos.text()}: Big.divInt division by zero")
    sign = -1 if (left.value < 0) != (right.value < 0) else 1
    return BigIntegerValue(sign * (abs(left.value) // abs(right.value)))


def neg_int(value: BigIntegerValue) -> BigIntegerValue:
    return BigIntegerValue(-value.value)


def abs_int(value: BigIntegerValue) -> BigIntegerValue:
    return BigIntegerValue(abs(value.value))


def sign_int(value: BigIntegerValue) -> int:
    return (value.value > 0) - (value.value < 0)


def result_precision(left: BigFloatValue, right: BigFloatValue | None = None) -> int:
    if right is None:
        return left.precision_bits
    return max(left.precision_bits, right.precision_bits)


def with_float(value: Decimal, precision_bits: int) -> BigFloatValue:
    precision = decimal_precision(precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(+value, precision_bits)


def add_float(left: BigFloatValue, right: BigFloatValue) -> BigFloatValue:
    precision_bits = result_precision(left, right)
    precision = decimal_precision(precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(left.value + right.value, precision_bits)


def sub_float(left: BigFloatValue, right: BigFloatValue) -> BigFloatValue:
    precision_bits = result_precision(left, right)
    precision = decimal_precision(precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(left.value - right.value, precision_bits)


def mul_float(left: BigFloatValue, right: BigFloatValue) -> BigFloatValue:
    precision_bits = result_precision(left, right)
    precision = decimal_precision(precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(left.value * right.value, precision_bits)


def div_float(left: BigFloatValue, right: BigFloatValue, pos: SourcePos) -> BigFloatValue:
    if right.value == 0:
        raise VerificationError(f"{pos.text()}: Big.divFloat division by zero")
    precision_bits = result_precision(left, right)
    precision = decimal_precision(precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(left.value / right.value, precision_bits)


def sqrt(value: BigFloatValue, pos: SourcePos) -> BigFloatValue:
    if value.value < 0:
        raise VerificationError(f"{pos.text()}: Big.sqrt domain error")
    precision = decimal_precision(value.precision_bits)
    with localcontext() as ctx:
        ctx.prec = precision
        return BigFloatValue(value.value.sqrt(), value.precision_bits)


def abs_float(value: BigFloatValue) -> BigFloatValue:
    return BigFloatValue(abs(value.value), value.precision_bits)


def sign_float(value: BigFloatValue) -> int:
    return (value.value > 0) - (value.value < 0)


def to_string(value: BigIntegerValue) -> str:
    return str(value.value)


def format_float(value: BigFloatValue, digits: int) -> str:
    if not isinstance(digits, int) or isinstance(digits, bool) or digits < 0:
        raise VerificationError("Big.format digits must be a non-negative Integer")
    return f"{value.value:.{digits}f}"
