import math


def calculator(operation: str, a: float, b: float) -> str:
    """Perform a basic arithmetic calculation.

    Use this tool for ANY math operation — addition, subtraction,
    multiplication, division, exponentiation, or square roots.

    Args:
        operation: The math operation to perform. One of:
            "add", "subtract", "multiply", "divide", "power", "sqrt"
        a: The first number.
        b: The second number. For sqrt, this is ignored — only 'a' is used.

    Returns:
        The result as a string.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return "Error: Inputs must be finite numbers."
    try:
        if not math.isfinite(float(a)) or not math.isfinite(float(b)):
            return "Error: Inputs must be finite numbers."

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "Error: Division by zero."
            result = a / b
        elif operation == "power":
            if abs(b) > 1_000:
                return "Error: Exponent is outside the supported range."
            result = a**b
        elif operation == "sqrt":
            if a < 0:
                return "Error: Square root requires a non-negative number."
            result = math.sqrt(a)
        else:
            return f"Error: Unknown operation '{operation}'."
    except (OverflowError, TypeError, ValueError, ZeroDivisionError) as exc:
        return f"Error: Calculation failed ({exc!s})."

    if isinstance(result, complex) or not math.isfinite(float(result)):
        return "Error: Result is outside the supported numeric range."
    return str(result)
