import math

import pytest

from my_agent.tools.calculator import calculator


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        ("add", 2, 3, "5"),
        ("subtract", 10, 4, "6"),
        ("multiply", 7, 6, "42"),
        ("divide", 9, 4, "2.25"),
        ("power", 2, 10, "1024"),
        ("sqrt", 81, 0, "9.0"),
    ],
)
def test_supported_operations(
    operation: str,
    a: float,
    b: float,
    expected: str,
) -> None:
    assert calculator(operation, a, b) == expected


def test_division_by_zero_is_rejected() -> None:
    assert calculator("divide", 4, 0) == "Error: Division by zero."


def test_negative_square_root_is_rejected() -> None:
    assert calculator("sqrt", -1, 0).startswith("Error:")


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_non_finite_inputs_are_rejected(value: float) -> None:
    assert calculator("add", value, 1).startswith("Error:")


def test_unbounded_exponent_is_rejected() -> None:
    assert calculator("power", 2, 1_001).startswith("Error:")


def test_unknown_operation_is_rejected() -> None:
    assert calculator("modulo", 5, 2).startswith("Error:")
