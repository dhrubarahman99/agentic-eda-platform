# Optional OpenAI layer that rewrites plain_summary and key_takeaway; never modifies computed values.

from __future__ import annotations

import json
import os
import re
from typing import Optional

from app.models.schemas import InsightResult, QueryResult

# Configuration — read from environment (.env is loaded by main.py on startup)

def _get_api_key() -> str:
    """Read the OpenAI API key from the environment at call time (not import time).
    This ensures .env values loaded by load_dotenv() in main.py are available."""
    return os.environ.get("OPENAI_API_KEY", "").strip()

def _is_enabled() -> bool:
    """Check the LLM_ENHANCEMENT_ENABLED toggle.
    Defaults to True. Set LLM_ENHANCEMENT_ENABLED=false to disable."""
    val = os.environ.get("LLM_ENHANCEMENT_ENABLED", "true").strip().lower()
    return val not in ("false", "0", "no", "off")

# Constants

MODEL = "gpt-4o-mini"
MAX_TOKENS = 600
TIMEOUT_SECONDS = 10.0
MAX_SUMMARY_INPUT_CHARS = 600

_SYSTEM_PROMPT = """You are a sharp data analyst writing insight descriptions for a business dashboard. Your audience is intelligent but not a data scientist — think a product manager, operations lead, or business analyst who understands business context well.

STRICT RULES:
1. You receive a plain_summary and key_takeaway computed by an analytics engine.
2. You may improve the phrasing and clarity of plain_summary and key_takeaway.
3. You must write a subtitle: 2-3 sentences that go beyond restating the finding. Interpret what the pattern likely means, what it implies for decisions or operations, and what a smart analyst would flag as the next question to answer. Draw only from facts and numbers already in the input — do not invent new claims.
4. NEVER invent, change, or add any numbers, percentages, or column names not in the original input.
5. NEVER mention algorithms, models, p-values, R-squared, or any statistical method names.
6. The subtitle should be analytical in tone — confident, specific, and action-oriented. Avoid filler phrases like "this is important" or "it is worth noting".
7. Keep plain_summary under 60 words.
8. Keep key_takeaway under 25 words.
9. Keep subtitle between 50–80 words. Use 2-3 focused sentences. Each sentence should add new information or a new angle — no padding.
10. Respond ONLY with JSON, no markdown:
{"plain_summary": "...", "key_takeaway": "...", "subtitle": "..."}"""

# Public entry points

def enhance_insight(insight: InsightResult) -> InsightResult:
    """
    Attempt to improve the phrasing of an InsightResult's text fields.
    Silent fallback on any failure. Original text preserved if LLM is
    disabled, key is missing, or the call fails.
    """
    try:
        enhanced_summary, enhanced_takeaway, enhanced_subtitle = _call_llm(
            insight_type=insight.insight_type.value,
            columns=insight.columns_used,
            plain_summary=insight.plain_summary,
            key_takeaway=insight.key_takeaway,
        )
        if enhanced_summary:
            insight.plain_summary = enhanced_summary
        if enhanced_takeaway:
            insight.key_takeaway = enhanced_takeaway
        if enhanced_subtitle:
            insight.subtitle = enhanced_subtitle
    except Exception:
        pass
    return insight

def enhance_query_result(result: QueryResult) -> QueryResult:
    """
    Attempt to improve the phrasing of a QueryResult's text fields.
    Only enhances successful results. Silent fallback on any failure.
    """
    if result.status.value != "success":
        return result
    if not result.plain_summary:
        return result

    try:
        enhanced_summary, enhanced_takeaway, _ = _call_llm(
            insight_type="query_answer",
            columns=(
                result.interpretation.mapped_columns
                if result.interpretation else []
            ),
            plain_summary=result.plain_summary,
            key_takeaway=result.key_takeaway or "",
        )
        if enhanced_summary:
            result.plain_summary = enhanced_summary
        if enhanced_takeaway and result.key_takeaway:
            result.key_takeaway = enhanced_takeaway
    except Exception:
        pass
    return result

def enhance_insights_batch(insights: list[InsightResult]) -> list[InsightResult]:
    """Enhance a list of InsightResults independently. Failure on one does not affect others."""
    for insight in insights:
        enhance_insight(insight)
    return insights

# Core LLM call

def _call_llm(
    insight_type: str,
    columns: list[str],
    plain_summary: str,
    key_takeaway: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Call OpenAI to improve phrasing.
    Returns (None, None) on any failure — caller always handles fallback.

    Checks (in order):
      1. LLM_ENHANCEMENT_ENABLED toggle
      2. OPENAI_API_KEY presence
      3. Actual API call
      4. Response parsing and hallucination guard
    """
    # ---- Toggle check ----
    if not _is_enabled():
        return None, None, None

    # ---- API key check ----
    api_key = _get_api_key()
    if not api_key:
        return None, None, None

    # ---- Prepare inputs ----
    plain_summary = plain_summary[:MAX_SUMMARY_INPUT_CHARS]
    key_takeaway = (key_takeaway or "")[:200]
    cols_str = (
        ", ".join(f"'{c}'" for c in columns[:5])
        if columns else "unspecified columns"
    )

    user_message = (
        f"Insight type: {insight_type}\n"
        f"Columns involved: {cols_str}\n\n"
        f"plain_summary to improve:\n{plain_summary}\n\n"
        f"key_takeaway to improve:\n{key_takeaway}\n\n"
        "Return only the JSON object with improved phrasing."
    )

    # ---- API call ----
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=TIMEOUT_SECONDS)

        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0.3,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            response_format={"type": "json_object"},
        )

        raw_text = _extract_text(response)
        if not raw_text:
            return None, None, None

        return _parse_and_validate(raw_text, plain_summary, key_takeaway)

    except Exception:
        return None, None, None

def _extract_text(response) -> Optional[str]:
    try:
        return response.choices[0].message.content.strip()
    except Exception:
        return None

def _parse_and_validate(
    raw_text: str,
    original_summary: str,
    original_takeaway: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse JSON and run hallucination guard on numbers."""
    clean = re.sub(r"```(?:json)?", "", raw_text).strip().strip("`").strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]+\}", clean, re.DOTALL)
        if not match:
            return None, None, None
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError:
            return None, None, None

    enhanced_summary = parsed.get("plain_summary", "").strip()
    enhanced_takeaway = parsed.get("key_takeaway", "").strip()
    enhanced_subtitle = parsed.get("subtitle", "").strip()

    # Hallucination guard — numbers invented by LLM are rejected
    original_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", original_summary))
    if original_numbers:
        all_original = original_numbers | set(
            re.findall(r"\d+(?:[.,]\d+)?", original_takeaway)
        )
        enhanced_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", enhanced_summary))
        if enhanced_numbers - all_original:
            return None, None, None
        subtitle_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", enhanced_subtitle))
        if subtitle_numbers - all_original:
            enhanced_subtitle = ""

    if enhanced_summary and len(enhanced_summary) < 10:
        enhanced_summary = None
    if enhanced_takeaway and len(enhanced_takeaway) < 5:
        enhanced_takeaway = None
    if enhanced_subtitle and len(enhanced_subtitle) < 10:
        enhanced_subtitle = None

    return enhanced_summary or None, enhanced_takeaway or None, enhanced_subtitle or None

# Status check (used by GET /api/llm/status)

def is_llm_available() -> tuple[bool, str]:
    """
    Returns (available: bool, reason: str).
    Checks toggle first, then API key, then network reachability.
    """
    if not _is_enabled():
        return False, (
            "LLM enhancement is disabled. "
            "Set LLM_ENHANCEMENT_ENABLED=true in your .env file to enable it."
        )

    api_key = _get_api_key()
    if not api_key:
        return False, (
            "OPENAI_API_KEY is not set. "
            "Add OPENAI_API_KEY=sk-... to your .env file."
        )

    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            client.get("https://api.openai.com", timeout=5.0)
        return True, "OpenAI LLM enhancement layer is available and enabled."
    except Exception as e:
        return False, f"OpenAI endpoint unreachable: {str(e)[:100]}"