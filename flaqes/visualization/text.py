"""
Text visualization utilities for the CLI.

This module helps render ASCII charts and improved formatted output for reports.
"""

def sparkline(numbers: list[int | float]) -> str:
    """
    Generate a unicode sparkline for a list of numbers.
    e.g., [1, 2, 3, 4, 5] ->  ▂▃▄▅
    """
    if not numbers:
        return ""
    
    chars = " ▂▃▄▅▆▇█"
    min_val = min(numbers)
    max_val = max(numbers)
    span = max_val - min_val
    
    if span == 0:
        return chars[len(chars) // 2] * len(numbers)
        
    result = []
    for n in numbers:
        # Normalize to 0..len(chars)
        idx = int((n - min_val) / span * (len(chars) - 1))
        result.append(chars[idx])
        
    return "".join(result)

def format_trend(current: int | float, previous: int | float) -> str:
    """
    Format a trend with an arrow and change.
    e.g. "10 (↑ 2)" or "5 (↓ 1)"
    """
    diff = current - previous
    if diff > 0:
        return f"{current} (↑ {diff})"
    elif diff < 0:
        return f"{current} (↓ {abs(diff)})"
    else:
        return f"{current} (-)"
