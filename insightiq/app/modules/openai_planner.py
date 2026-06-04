# OpenAI wrapper: classifies advanced query intents and generates plain-English result explanations.

from __future__ import annotations

import json
import os
from typing import Any

# Constants

MODEL = "gpt-4o-mini"
TIMEOUT_SECONDS = 10.0

VALID_INTENTS: frozenset[str] = frozenset({
    "targeted_correlation",
    "compound_filter",
    "derived_metric",
    "period_growth",
    "anomaly_query",
    "multi_criteria_rank",
    "business_decision",
    "scenario_analysis",
    "open_ended_insight",
    "segment_comparison",
    "threshold_analysis",
    "seasonal_pattern",
    "unknown",
})

_FALLBACK = {"intent": "unknown", "confidence": 0.0, "parameters": {}, "sub_queries": []}

_PLAN_PROMPT_TEMPLATE = """\
You are a data analytics query planner.
Given a user question and available dataset columns, classify the query intent and extract structured parameters.

Available columns:
{cols_desc}

User question: "{question}"

Return ONLY a JSON object with these exact keys:
{{
  "intent": "<one of the intents listed below>",
  "parameters": {{<intent-specific params>}},
  "confidence": <float 0.0–1.0>,
  "sub_queries": [<list of sub-question strings — only for open_ended_insight, else []>]
}}

Allowed intents and their typical parameters:
- targeted_correlation  → {{"col_a": "...", "col_b": "..."}}
- compound_filter       → {{"conditions": [{{"col": "...", "word": "high|low|very high|..."}}]}}
- derived_metric        → {{"numerator_col": "...", "denominator_col": "...", "derived_name": "..."}}
- period_growth         → {{"date_col": "...", "metric_col": "..."}}
- anomaly_query         → {{"columns": ["...", ...]}}
- multi_criteria_rank   → {{"group_col": "...", "metrics": ["...", ...], "weights": [<floats>], "n_top": 5}}
- business_decision     → {{"group_col": "...", "metrics": ["...", ...]}}
- scenario_analysis     → {{"condition_col": "...", "threshold_word": "high|low|...", "target_col": "..."}}
- open_ended_insight    → {{"sub_queries": ["...", ...]}}
- segment_comparison    → {{"segment_col": "...", "segment_a": "...", "segment_b": "...", "metrics": ["..."]}}
- threshold_analysis    → {{"filter_col": "...", "threshold_word": "high|low|...", "target_col": "..."}}
- seasonal_pattern      → {{"date_col": "...", "target_col": "..."}}
- unknown               → {{}}
"""

_EXPLAIN_PROMPT_TEMPLATE = """\
You are a business analytics communicator.

A user asked: "{question}"

The analytics engine computed this result (intent type: {intent}):
{result_json}

Write 2–3 plain-English sentences that explain what this means in business terms.
Rules:
- Do NOT mention algorithms, models, or technical methods.
- Do NOT invent any numbers not present in the data above.
- Write for a non-technical small-business reader.

Return ONLY a JSON object: {{"explanation": "..."}}
"""

# Environment helpers (match llm_enhancer.py contract)

def _get_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()

def _is_enabled() -> bool:
    val = os.environ.get("LLM_ENHANCEMENT_ENABLED", "true").strip().lower()
    return val not in ("false", "0", "no", "off")

# Public API

def classify_and_plan_query(
    question: str,
    column_names: list[str],
    column_types: dict[str, str],
) -> dict[str, Any]:
    """
    Use gpt-4o-mini to classify a question and extract structured parameters.

    Parameters
    ----------
    question     : raw user question
    column_names : list of column names in the dataset
    column_types : {col_name: dtype_string} mapping

    Returns
    -------
    dict with keys: intent, parameters, confidence, sub_queries
    On any failure returns the safe fallback dict (intent="unknown").
    """
    if not _is_enabled() or not _get_api_key():
        return dict(_FALLBACK)

    cols_desc = "\n".join(
        f"  - {name} ({column_types.get(name, 'unknown')})"
        for name in column_names
    )
    prompt = _PLAN_PROMPT_TEMPLATE.format(cols_desc=cols_desc, question=question)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=_get_api_key(), timeout=TIMEOUT_SECONDS)
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=500,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        parsed: dict[str, Any] = json.loads(raw)
    except Exception:
        return dict(_FALLBACK)

    intent = parsed.get("intent", "unknown")
    if intent not in VALID_INTENTS:
        intent = "unknown"

    # Move sub_queries from parameters to top level if planner put them there
    parameters: dict[str, Any] = parsed.get("parameters", {}) or {}
    sub_queries: list[str] = parsed.get("sub_queries", []) or parameters.pop("sub_queries", [])
    if not isinstance(sub_queries, list):
        sub_queries = []

    return {
        "intent": intent,
        "confidence": float(max(0.0, min(1.0, parsed.get("confidence", 0.5)))),
        "parameters": parameters,
        "sub_queries": sub_queries,
    }

def explain_result(
    question: str,
    result_data: dict[str, Any],
    intent: str,
) -> str:
    """
    Ask gpt-4o-mini to write a plain-English business explanation of a
    pre-computed result dict (never raw rows — only aggregated numbers /
    column names / labels).

    Parameters
    ----------
    question    : original user question
    result_data : pre-computed result dict (numbers, labels, aggregates)
    intent      : intent string for context

    Returns
    -------
    Explanation string.  On any failure returns a deterministic fallback
    built from result_data — never raises.
    """
    if not _is_enabled() or not _get_api_key():
        return _build_fallback(result_data)

    # Truncate large result blobs — never send raw rows
    result_json = json.dumps(result_data, indent=2, default=str)[:1_500]

    prompt = _EXPLAIN_PROMPT_TEMPLATE.format(
        question=question,
        intent=intent,
        result_json=result_json,
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=_get_api_key(), timeout=TIMEOUT_SECONDS)
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=200,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        explanation = parsed.get("explanation", "").strip()
        if len(explanation) > 10:
            return explanation
    except Exception:
        pass

    return _build_fallback(result_data)

# Internal helpers

def _build_fallback(result_data: dict[str, Any]) -> str:
    if not result_data:
        return "The analysis completed successfully."
    keys = [str(k) for k in list(result_data.keys())[:3]]
    return f"Analysis result contains: {', '.join(keys)}."
