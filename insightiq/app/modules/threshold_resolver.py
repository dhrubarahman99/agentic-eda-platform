# Converts vague language ("top performers", "high values") to percentile-based numeric cutoffs.

from __future__ import annotations

import re

import pandas as pd

# Word → (method, param) mapping

_WORD_MAP: dict[str, tuple[str, float | None]] = {
    "high":     ("percentile", 0.75),
    "highest":  ("percentile", 0.75),
    "large":    ("percentile", 0.75),
    "low":      ("percentile", 0.25),
    "lowest":   ("percentile", 0.25),
    "small":    ("percentile", 0.25),
    "very high": ("percentile", 0.90),
    "extreme":   ("percentile", 0.90),
    "very low":  ("percentile", 0.10),
    "unusual":   ("iqr",        None),
    "abnormal":  ("iqr",        None),
    "outlier":   ("iqr",        None),
    "average":   ("percentile", 0.50),
    "typical":   ("percentile", 0.50),
    "threshold": ("percentile", 0.75),
}

# Comparison-word pattern used by extract_numeric_threshold
_CMP_PATTERN = re.compile(
    r"(?:exceeds?|above|over|greater\s+than|more\s+than"
    r"|below|under|less\s+than|at\s+least|at\s+most)\s+"
    r"(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Public API

def resolve_threshold(word: str, series: pd.Series) -> float:
    """
    Convert a vague word/phrase to a numeric cutoff derived from *series*.

    Supported words
    ---------------
    high / highest / large      → 75th percentile
    low / lowest / small        → 25th percentile
    very high / extreme         → 90th percentile
    very low                    → 10th percentile
    unusual / abnormal / outlier → Q3 + 1.5 × IQR
    average / typical           → median (50th percentile)
    threshold (generic)         → 75th percentile (default)

    Parameters
    ----------
    word   : vague description string (may be multi-word, e.g. "very high")
    series : pandas Series of numeric data to derive the cutoff from

    Returns
    -------
    float cutoff value
    """
    key = word.lower().strip()
    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if numeric.empty:
        return 0.0

    entry = _WORD_MAP.get(key)
    if entry is None:
        # Default: 75th percentile
        return float(numeric.quantile(0.75))

    method, param = entry

    if method == "percentile":
        return float(numeric.quantile(param))

    # method == "iqr"
    q1 = float(numeric.quantile(0.25))
    q3 = float(numeric.quantile(0.75))
    iqr = q3 - q1
    return float(q3 + 1.5 * iqr)

def extract_numeric_threshold(query: str) -> float | None:
    """
    Scan *query* for an explicit numeric threshold preceded by a comparison
    word (e.g. "price exceeds 100", "above 50.5").

    Returns the numeric value as float, or None if nothing is found.
    """
    match = _CMP_PATTERN.search(query)
    if match:
        return float(match.group(1))
    return None
