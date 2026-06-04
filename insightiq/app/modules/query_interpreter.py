# Rule-based NLP interpreter: maps plain-English questions to structured QueryObject intents.

from __future__ import annotations

import re
import uuid
from typing import Optional

from rapidfuzz import fuzz, process as fuzz_process

from app.models.schemas import (
    AmbiguityItem,
    DatasetProfile,
    DType,
    ErrorResponse,
    ErrorType,
    FilterCondition,
    QueryIntent,
    QueryObject,
    SemanticTag,
)

# Always escalated to OpenAI even when Tier 1 matches, because they need deeper reasoning.
_TIER2_ESCALATE_INTENTS: frozenset[QueryIntent] = frozenset({
    QueryIntent.business_decision,
    QueryIntent.open_ended_insight,
    QueryIntent.multi_criteria_rank,
})

FUZZY_MATCH_THRESHOLD = 55       # min score to accept a column match per token
AMBIGUITY_SCORE_GAP = 8          # gap between top-2 scores for ONE token → ambiguous
LOW_CONFIDENCE_THRESHOLD = 0.55

_INTENT_PATTERNS: list[tuple[QueryIntent, list[str], float]] = [
    (QueryIntent.missing_data, [
        r"\bmissing\b", r"\bnull\b", r"\bempty\b", r"\bblank\b",
        r"\bgap\b", r"\bno value\b", r"\bincomplete\b", r"\bnot filled\b",
    ], 0.92),

    (QueryIntent.feature_importance, [
        r"what\s+(drives?|affects?|influences?|causes?|determines?)",
        r"most important factor", r"key driver", r"main factor",
        r"what contributes", r"what predicts",
        r"which.*most.*affect",
        r"what\s+influence",
        r"factors?\s+(affecting|influencing|driving)",
        # Additional patterns for "drivers", "predictors", "variables"
        r"\bdrivers?\s+(of|for|behind)\b",
        r"\bkey\s+(factors?|variables?|predictors?)\b",
        r"\bimportant\s+(variables?|features?|factors?)\b",
        r"\bwhat\s+(are\s+the\s+)?(main|key|top|primary)\s+(factors?|predictors?|drivers?|variables?)\b",
        r"\bpredict(s|ing|or)?\b.{0,30}\b(column|variable|target)\b",
        r"\binfluences?\b.{0,30}\b(most|heavily|strongly|significantly)\b",
        r"\bmost\s+(influential|predictive|important)\b",
        r"\bwhat\s+determines?\b",
        r"\bfactors?\b.{0,40}\b(predict|influence|affect|drive)\b",
        r"\bwhich\b.{0,20}\bfactors?\b",
        r"\bpredict(s|ing)?\b.{0,50}\b(visits?|tickets?|score|rate|outcome|amount|churn|default)\b",
    ], 0.88),

    # New: efficiency / ROI queries  — higher confidence than ranking so they win
    (QueryIntent.efficiency_query, [
        r"\beffici",
        r"\broi\b",
        r"\breturn\s+on\b",
        r"\bprofit\s+per\b",                               # "profit per unit/employee"
        r"\bprofit\s+(ratio)\b",                           # "profit ratio"
        r"\bprofit\s+margin\b.{0,20}\b(per|ratio|efficiency|vs|against|return)\b",  # "profit margin vs cost", NOT standalone
        r"\bper\s+(unit|employee|person|item|transaction|sale)\b",  # "revenue per unit", "revenue per employee"
        r"\bcost[\s-]effective",
        r"\bprofitab(le|ility)\b",
        r"\bhigh\w*\s+profit\b.{0,40}\blow\w*\s+cost\b",
        r"\blow\w*\s+cost\b.{0,40}\bhigh\w*\s+profit\b",
        r"\bprofit\s+to\s+cost\b",
        r"\bprofit\s*[/÷]\s*cost\b",
        r"\bbest\s+return\b",
        r"\bvalue\s+for\s+(money|cost)\b",
    ], 0.89),

    # Business decision — Tier-1 hook so Tier-2 has the correct intent framing
    # (business_decision is in _TIER2_ESCALATE_INTENTS so Tier-2 always runs for these)
    (QueryIntent.business_decision, [
        r"\bshould\s+we\b",
        r"\bwhere\s+should\s+we\b",
        r"\bprioritize\b",
        r"\bstrateg(y|ies)?\b",
        r"\bbest\s+strategy\b",
        r"\bwhich\s+(should|would)\b.{0,30}\b(invest|focus|prioritize|choose|expand|grow)\b",
        r"\bexpansion\b",
        r"\bdiscontinue\b",
        r"\bheadcount\b",
        r"\breduc(e|ing)\s+churn\b",
    ], 0.88),

    # New: multi-column combination ranking
    (QueryIntent.combination_ranking, [
        r"\bcombination\b",
        r"\bcombined?\b.{0,20}(highest|most|best|top)\b",
        r"\bpair\w*\b.{0,20}(highest|most|best|top)\b",
        r"\bwhich\b.{0,40}\band\b.{0,40}(generates?|has|gives?|produces?)\b.{0,30}(highest|most|best|top)\b",
        r"\bwhich\b.{0,40}(category|channel|segment|region|type).{0,20}\band\b.{0,40}(category|channel|segment|region|type)\b",
    ], 0.88),

    # Scenario / conditional analysis — must sit BEFORE trend/correlation/ranking
    # so specific "when X is high/low" and "if X increases" patterns win
    (QueryIntent.scenario_analysis, [
        r"\bwhat\s+happens?\b",
        r"\bif\b.{0,40}\b(increase[s]?|decrease[s]?|rises?|falls?|goes?\s+up|goes?\s+down|higher|lower)\b",
        r"\bscenario\b",
        r"\bwhen\b.{0,25}\b(is|are)\b.{0,15}\b(high|low|large|small|above|below)\b",
        r"\bshow\b.{0,30}\bwhen\b",
        r"\bin\s+(high|low)\s+\w+\s+scenarios?\b",
        r"\bin\s+\w+\s+(high|low)\s+scenarios?\b",
    ], 0.87),

    # Threshold / numeric filter — "when X exceeds N", "where X > 200"
    (QueryIntent.threshold_analysis, [
        r"\bexceed[s]?\b",
        r"\bmore\s+than\s+\d+\b",
        r"\bless\s+than\s+\d+\b",
        r"\babove\s+\d",
        r"\bbelow\s+\d",
        r"\bgreater\s+than\s+\d",
        r"\bat\s+least\s+\d",
        r"\bover\s+\d",
        r"\bunder\s+\d",
        r"\bwhen\b.{0,30}\b\d+\b",
    ], 0.87),

    (QueryIntent.trend, [
        r"\btrends?\b", r"\bover time\b", r"\btime series\b",
        r"\bmonthly\b", r"\bweekly\b", r"\byearly\b",
        r"\bby month\b", r"\bby year\b", r"\bby quarter\b",
        r"\bchange[ds]?\s+over\b", r"\bgrow(th)?\b", r"\bdecline\b",
        r"\bprogress\b", r"\btrajectory\b",
        r"\bover\s+the\s+(months?|years?|weeks?|quarters?)\b",
        r"\blately\b",
    ], 0.87),

    (QueryIntent.correlation, [
        r"\bcorrelat", r"\brelationship\b", r"\brelated\b",
        r"\binfluence\b", r"\bassociat\b", r"\blinked\b",
        r"\bconnect\b", r"\bbetween\b.*\band\b",
        r"\baffect\b", r"\bimpact\b.{0,20}\b(on|profit|revenue|sales)\b",
        r"\bdoes\b.{0,30}\baffect\b",
        r"\bis\b.{0,30}\bassociated\b",
        r"\brelated\s+to\b",
        r"\bhow\s+does\b.{0,30}\brelate\b",
        r"\brelate[s]?\s+to\b",
    ], 0.84),

    (QueryIntent.ranking, [
        r"\btop\b", r"\bbottom\b", r"\bbest\b", r"\bworst\b",
        r"\bhighest\b", r"\blowest\b", r"\bmost\b", r"\bleast\b",
        r"\brank\b", r"\blargest\b", r"\bsmallest\b",
        r"which.*highest", r"which.*lowest", r"which.*most",
        r"number one", r"leading",
    ], 0.86),

    (QueryIntent.comparison, [
        r"\bcompar", r"\bversus\b", r"\bvs\b", r"\bdiffer",
        r"\bacross\s+(regions?|groups?|categories?|types?|segments?|countries?|cities?|departments?|channels?|brands?|products?|teams?|divisions?|weather)\b",
        r"\bby\s+(region|product|category|group|type|segment|country|city|department|channel|brand|store|quarter|team|division|weather|condition)\b",
        r"\bbreak.*down\b", r"\bsplit\s+by\b", r"\bgroup\s+by\b",
        r"\bper\s+(region|product|category|group|segment)\b",
        r"\bbroken\s+down\b",
        r"\bshow\b.{3,50}\bby\s+(region|product|category|group|type|segment)\b",
        r"\bhow\s+does\b.{0,30}\bdiffer\b",
        r"\bhow\s+do\b.{0,30}\bcompare\b",
        r"\bvary\s+(by|across)\b",
        r"\bvaries?\s+(by|across)\b",
        r"\bhow\s+does\b.{0,40}\bvary\b",
    ], 0.85),

    (QueryIntent.distribution, [
        r"\bdistribut", r"\bspread\b", r"\brange\b", r"\bhistogram\b",
        r"\bvariance\b", r"\bstandard deviation\b",
        r"\bmedian\b", r"\btypical\b",
        r"\bsummary\b", r"\bstatistics\b",
        r"\bdescribe\b", r"\boverview\b", r"\bprofile\b",
    ], 0.78),

    (QueryIntent.aggregation, [
        r"\btotal\b", r"\bsum\b", r"\bcount\b", r"\bhow many\b",
        r"\baverage\b", r"\bavg\b", r"\bmean\b", r"\boverall\b",
        r"\baggregate\b", r"\bcumulative\b",
        r"^\s*show\b", r"^\s*display\b", r"^\s*view\b", r"^\s*get\b",
        r"\bstats?\b",
    ], 0.76),
]

# Semantic synonym map — user word → SemanticTag(s)
_SEMANTIC_SYNONYMS: dict[str, list[SemanticTag]] = {
    # Quantity synonyms
    "sales": [SemanticTag.quantity],
    "revenue": [SemanticTag.quantity],
    "income": [SemanticTag.quantity],
    "profit": [SemanticTag.quantity],
    "cost": [SemanticTag.quantity],
    "price": [SemanticTag.quantity],
    "amount": [SemanticTag.quantity],
    "value": [SemanticTag.quantity],
    "spend": [SemanticTag.quantity],
    "budget": [SemanticTag.quantity],
    "expense": [SemanticTag.quantity],
    "score": [SemanticTag.quantity],
    "rating": [SemanticTag.quantity],
    "quantity": [SemanticTag.quantity],
    "units": [SemanticTag.quantity],
    "orders": [SemanticTag.quantity],
    "volume": [SemanticTag.quantity],
    "number": [SemanticTag.quantity],
    "total": [SemanticTag.quantity],
    # Domain-agnostic quantity aliases (health, environment, HR)
    "salary": [SemanticTag.quantity],
    "wage": [SemanticTag.quantity],
    "bmi": [SemanticTag.quantity],
    "risk": [SemanticTag.quantity],
    "pollution": [SemanticTag.quantity],
    "temperature": [SemanticTag.quantity],
    "temp": [SemanticTag.quantity],
    "energy": [SemanticTag.quantity],
    "demand": [SemanticTag.quantity],
    "inventory": [SemanticTag.quantity],
    "visits": [SemanticTag.quantity],
    "tickets": [SemanticTag.quantity],
    "margin": [SemanticTag.quantity],
    "consumption": [SemanticTag.quantity],
    "index": [SemanticTag.quantity],
    "reading": [SemanticTag.quantity],
    "satisfaction": [SemanticTag.quantity],
    # Date synonyms
    "date": [SemanticTag.date],
    "time": [SemanticTag.date],
    "month": [SemanticTag.date],
    "year": [SemanticTag.date],
    "week": [SemanticTag.date],
    "day": [SemanticTag.date],
    "quarter": [SemanticTag.date],
    "period": [SemanticTag.date],
    "when": [SemanticTag.date],
    "timestamp": [SemanticTag.date],
    # Category synonyms
    "region": [SemanticTag.category],
    "area": [SemanticTag.category],
    "location": [SemanticTag.category],
    "country": [SemanticTag.category],
    "city": [SemanticTag.category],
    "state": [SemanticTag.category],
    "category": [SemanticTag.category],
    "type": [SemanticTag.category],
    "group": [SemanticTag.category],
    "segment": [SemanticTag.category],
    "product": [SemanticTag.category],
    "brand": [SemanticTag.category],
    "channel": [SemanticTag.category],
    "status": [SemanticTag.category],
    "department": [SemanticTag.category],
    "condition": [SemanticTag.category],
    "weather": [SemanticTag.category],
    "issue": [SemanticTag.category],
}

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "to", "of", "in",
    "on", "at", "by", "for", "with", "about", "and", "but", "or", "so",
    "not", "no", "very", "just", "show", "me", "my", "our", "your",
    "its", "which", "what", "how", "who", "where", "when", "why",
    "all", "each", "every", "any", "most", "more", "make", "find", "get",
    "give", "tell", "want", "see", "look", "check", "please", "i",
    "data", "dataset", "column", "columns", "number", "this", "that",
    "there", "their", "these", "those", "across", "per",
}

_FILTER_PATTERNS = [
    r"where\s+(\w+)\s+(?:is|=|equals?)\s+['\"]?(\w[\w\s]*?)['\"]?(?:\s|$)",
    r"for\s+(\w+)\s+(?:=|equals?)\s+['\"]?(\w[\w\s]*?)['\"]?(?:\s|$)",
    # "in [column] [value]" only when the column term comes first (e.g. "in region West")
    # Deliberately tightened: require the captured col-term to be a plausible short identifier
    # (no spaces, not a digit/operator word) to avoid false matches like "in revenue across orders"
    r"\bin\s+(?:the\s+)?(\w+)\s+['\"]?(\w+)['\"]?(?:\s|$)",
]

# Public entry point — two-tier interpreter

def interpret_query(
    raw_query: str,
    profile: DatasetProfile,
    feedback_hints: Optional[dict] = None,
) -> tuple[Optional[QueryObject], Optional[ErrorResponse]]:
    """
    Interpret a natural-language query against a DatasetProfile.

    Tier 1 (rule-based): always runs first.  Fully deterministic.
    Feedback adaptation: applied after Tier 1 — adjusts intent before Tier 2.
    Tier 2 (OpenAI planner): called only when Tier 1 + adaptation cannot resolve.

    feedback_hints (optional): dict from feedback_store.get_adaptation_hints().
      - avoid_intent     : intent proven unhelpful for a similar past question
      - preferred_intent : intent proven helpful for a similar past question
      - fallback_intent  : deterministic rule-based alternative to avoid_intent

    Returns (QueryObject, None) on success or (None, ErrorResponse) on failure.
    """
    tier1_obj, tier1_err = _interpret_tier1(raw_query, profile)

    # Apply feedback adaptation BETWEEN Tier 1 and Tier 2.
    # Deterministic fallback is tried first; Tier 2 is the last resort.
    if feedback_hints:
        tier1_obj, tier1_err = _apply_feedback_adaptation(
            raw_query, tier1_obj, tier1_err, feedback_hints
        )

    # Decide whether to escalate to Tier 2
    if _should_use_tier2(tier1_obj, tier1_err):
        tier2_obj = _interpret_tier2(raw_query, profile)
        if tier2_obj is not None:
            return tier2_obj, None

    return tier1_obj, tier1_err

# Feedback adaptation helpers (deterministic — no OpenAI involved)

def _rebuild_with_intent(
    obj: QueryObject,
    new_intent_str: str,
    source: str = "",
) -> Optional[QueryObject]:
    """
    Return a shallow copy of *obj* with a substituted intent and operation.
    Returns None if new_intent_str is not a valid QueryIntent enum value.
    """
    try:
        new_intent = QueryIntent(new_intent_str)
    except ValueError:
        return None

    note = (
        f" [Feedback adaptation ({source}): intent switched to '{new_intent_str}']"
        if source else ""
    )
    return QueryObject(
        query_id=obj.query_id,
        raw_query=obj.raw_query,
        intent=new_intent,
        mapped_columns=obj.mapped_columns,
        operation=_build_operation(new_intent),
        filters=obj.filters,
        confidence=obj.confidence,
        ambiguities=obj.ambiguities,
        interpretation_explanation=obj.interpretation_explanation + note,
        is_ambiguous=obj.is_ambiguous,
        is_low_confidence=obj.is_low_confidence,
        parameters=obj.parameters,
        sub_queries=obj.sub_queries,
    )

def _apply_feedback_adaptation(
    raw_query: str,
    tier1_obj: Optional[QueryObject],
    tier1_err: Optional[ErrorResponse],
    feedback_hints: dict,
) -> tuple[Optional[QueryObject], Optional[ErrorResponse]]:
    """
    Apply feedback-guided adaptation after Tier 1, before Tier 2.

    Priority order:
    1. Positive match + current confidence < 0.75 → rebuild with preferred_intent
       (reuses a previously successful interpretation pattern)
    2. Negative match + current intent == avoid_intent:
       a. Deterministic fallback from rule table → rebuild with fallback_intent
       b. No rule match → downgrade confidence to force Tier 2 (last resort)

    Keeps the original result unchanged if no hint applies.
    """
    preferred_intent = feedback_hints.get("preferred_intent")
    avoid_intent = feedback_hints.get("avoid_intent")
    fallback_intent = feedback_hints.get("fallback_intent")

    # Case 1 — Positive feedback: reuse a previously successful intent
    # Only applies when Tier 1 succeeded but with low/medium confidence.
    if (
        preferred_intent
        and tier1_obj is not None
        and tier1_obj.confidence < 0.75
        and tier1_obj.intent.value != preferred_intent
    ):
        rebuilt = _rebuild_with_intent(tier1_obj, preferred_intent, source="positive feedback")
        if rebuilt is not None:
            return rebuilt, None

    # Case 2 — Negative feedback: avoid the previously failed intent
    if (
        avoid_intent
        and tier1_obj is not None
        and tier1_obj.intent.value == avoid_intent
    ):
        # 2a: Try the deterministic fallback heuristic first (no OpenAI needed)
        if fallback_intent and fallback_intent != avoid_intent:
            rebuilt = _rebuild_with_intent(
                tier1_obj, fallback_intent, source="negative feedback — rule fallback"
            )
            if rebuilt is not None:
                return rebuilt, None

        # 2b: No deterministic fallback available → lower confidence so Tier 2 runs.
        # Exception: keep comparison/aggregation/distribution above LOW_CONFIDENCE_THRESHOLD
        # so Tier 2 cannot override them with higher-level intents like business_decision.
        _PROTECTED_TIER1 = frozenset({
            QueryIntent.comparison,
            QueryIntent.aggregation,
            QueryIntent.distribution,
        })
        new_conf = 0.40
        if tier1_obj.intent in _PROTECTED_TIER1:
            new_conf = 0.65  # above 0.6 Tier-2 escalation threshold → prevents unwanted override
        tier1_obj.confidence = new_conf
        tier1_obj.is_low_confidence = (new_conf < LOW_CONFIDENCE_THRESHOLD)

    return tier1_obj, tier1_err

# Tier 1 — deterministic rule-based interpreter (original logic)

def _interpret_tier1(
    raw_query: str,
    profile: DatasetProfile,
) -> tuple[Optional[QueryObject], Optional[ErrorResponse]]:
    """Fully deterministic rule-based interpretation — no feedback, no OpenAI."""
    query_id = str(uuid.uuid4())
    normalised = _normalise(raw_query)

    # Step 1: Detect intent
    intent, intent_conf = _detect_intent(normalised)

    # Step 2: Extract tokens
    tokens = _extract_tokens(normalised)

    # Step 3: Map tokens to columns — PER TOKEN to detect real ambiguity
    mapped, ambiguous_token, ambiguity_items = _map_columns_per_token(tokens, profile)

    # Step 4: Semantic fallback
    if not mapped:
        mapped = _semantic_fallback(tokens, normalised, profile)
        ambiguous_token = None
        ambiguity_items = []

    # Step 4b: Trend/growth intents — auto-inject the best datetime column when
    # the user writes "over time", "by month", etc. without naming the date column.
    # This prevents trend queries from losing their date column mapping entirely.
    _TREND_INTENTS = (
        QueryIntent.trend,
        QueryIntent.period_growth,
        QueryIntent.seasonal_pattern,
    )
    if intent in _TREND_INTENTS and profile.datetime_columns:
        has_dt = any(c in profile.datetime_columns for c in mapped)
        if not has_dt:
            dt_col = profile.datetime_columns[0]
            if dt_col not in mapped:
                mapped = [dt_col] + mapped

    # Step 5: Filter detection
    filter_cond = _detect_filter(normalised, profile, raw_query=raw_query)

    # Step 6: Confidence
    confidence, explanation = _compute_confidence(
        intent, intent_conf, mapped, bool(ambiguous_token), profile
    )

    is_low_conf = confidence < LOW_CONFIDENCE_THRESHOLD

    # ---- Error gates ----

    # Real ambiguity: one token could mean multiple specific columns
    if ambiguous_token and ambiguity_items:
        valid_cols = profile.numeric_columns + profile.categorical_columns + profile.datetime_columns
        return None, ErrorResponse(
            error_id=str(uuid.uuid4()),
            error_type=ErrorType.ambiguity,
            message=(
                f"I'm not sure which column you mean by '{ambiguous_token}'. "
                f"Could you be more specific?"
            ),
            reason=f"Token '{ambiguous_token}' matched multiple columns with similar scores.",
            suggestions=[
                f"Try asking about '{a.candidate_column}' directly"
                for a in ambiguity_items[:3]
            ],
            ambiguity_options=ambiguity_items[:4],
            valid_columns_hint=valid_cols[:8],
        )

    # Mismatch: no columns found and intent needs them
    if not mapped and intent not in (QueryIntent.missing_data, QueryIntent.unknown):
        valid_cols = profile.numeric_columns + profile.categorical_columns + profile.datetime_columns
        term = _best_unmatched_term(tokens)
        return None, ErrorResponse(
            error_id=str(uuid.uuid4()),
            error_type=ErrorType.mismatch,
            message=(
                f"I couldn't find a column matching '{term}' in your dataset. "
                f"Available columns include: {', '.join(valid_cols[:8])}."
            ),
            reason=f"No column in profile matched tokens: {tokens}",
            suggestions=[f"Try asking about '{c}'" for c in valid_cols[:4]],
            valid_columns_hint=valid_cols,
        )

    # Low confidence
    if is_low_conf:
        return None, ErrorResponse(
            error_id=str(uuid.uuid4()),
            error_type=ErrorType.low_confidence,
            message=(
                f"I wasn't confident enough to interpret your question "
                f"(confidence: {confidence:.0%}). Could you rephrase it?"
            ),
            reason=f"Confidence {confidence:.3f} below threshold {LOW_CONFIDENCE_THRESHOLD}",
            suggestions=[
                "Use column names directly, e.g. 'Show revenue by region'",
                "Use keywords like: top, trend, compare, missing, average",
                "Ask about a specific column: 'What is the average revenue?'",
            ],
            valid_columns_hint=(profile.numeric_columns + profile.categorical_columns)[:6],
        )

    # Unsupported: unknown intent with no column context
    if intent == QueryIntent.unknown:
        return None, ErrorResponse(
            error_id=str(uuid.uuid4()),
            error_type=ErrorType.unsupported,
            message=(
                "I'm not sure what kind of analysis you're asking for. "
                "I can help with: trends, comparisons, rankings, "
                "correlations, distributions, and missing data."
            ),
            reason=f"Intent detected as 'unknown' for query: '{raw_query}'",
            suggestions=[
                "Ask about trends: 'Show revenue over time'",
                "Ask about rankings: 'Which region has the highest sales?'",
                "Ask about missing data: 'Which columns have missing values?'",
                "Ask about comparisons: 'Compare profit by product'",
            ],
        )

    operation = _build_operation(intent)

    return QueryObject(
        query_id=query_id,
        raw_query=raw_query,
        intent=intent,
        mapped_columns=mapped,
        operation=operation,
        filters=filter_cond,
        confidence=round(confidence, 4),
        ambiguities=ambiguity_items,
        interpretation_explanation=explanation,
        is_ambiguous=bool(ambiguous_token),
        is_low_confidence=is_low_conf,
    ), None

# Tier 2 — OpenAI planner

def _should_use_tier2(
    tier1_obj: Optional[QueryObject],
    tier1_err: Optional[ErrorResponse],
) -> bool:
    """Return True when Tier 2 should be attempted."""
    if tier1_err is not None:
        # Escalate low-confidence and unsupported errors; pass through ambiguity/mismatch
        return tier1_err.error_type in (ErrorType.low_confidence, ErrorType.unsupported)
    if tier1_obj is not None:
        if tier1_obj.confidence <= 0.6:
            return True
        if tier1_obj.intent == QueryIntent.unknown:
            return True
        if tier1_obj.intent in _TIER2_ESCALATE_INTENTS:
            return True
    return False

def _interpret_tier2(
    raw_query: str,
    profile: DatasetProfile,
) -> Optional[QueryObject]:
    """
    Call the OpenAI planner and, on success, return a QueryObject populated
    with the new advanced intent + parameters.  Returns None on any failure.
    """
    try:
        from app.modules import openai_planner  # late import — avoids startup cost

        column_names = [c.name for c in profile.columns]
        column_types = {c.name: c.dtype.value for c in profile.columns}

        plan = openai_planner.classify_and_plan_query(raw_query, column_names, column_types)

        intent_str = plan.get("intent", "unknown")
        if intent_str == "unknown":
            return None

        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            return None

        params: dict = plan.get("parameters", {}) or {}
        sub_queries: list[str] = plan.get("sub_queries", []) or []
        confidence: float = float(plan.get("confidence", 0.5))

        # Build mapped_columns from common parameter keys
        all_col_names = {c.name for c in profile.columns}
        mapped: list[str] = []
        for key in ("col_a", "col_b", "target_col", "group_col", "date_col",
                    "condition_col", "filter_col", "segment_col",
                    "numerator_col", "denominator_col", "metric_col"):
            val = params.get(key)
            if isinstance(val, str) and val in all_col_names and val not in mapped:
                mapped.append(val)
        for m in (params.get("metrics") or []):
            if isinstance(m, str) and m in all_col_names and m not in mapped:
                mapped.append(m)

        explanation = (
            f"I interpreted your question as a "
            f"'{intent_str.replace('_', ' ')}' query "
            f"(via AI planner, confidence {confidence:.0%})."
        )

        return QueryObject(
            query_id=str(uuid.uuid4()),
            raw_query=raw_query,
            intent=intent,
            mapped_columns=mapped,
            operation=intent_str,
            filters=None,
            confidence=round(min(1.0, max(0.0, confidence)), 4),
            ambiguities=[],
            interpretation_explanation=explanation,
            is_ambiguous=False,
            is_low_confidence=confidence < LOW_CONFIDENCE_THRESHOLD,
            parameters=params,
            sub_queries=sub_queries,
        )
    except Exception:
        return None

# Step 1 — Intent detection

def _detect_intent(normalised: str) -> tuple[QueryIntent, float]:
    best_intent = QueryIntent.unknown
    best_conf = 0.0
    for intent, patterns, base_conf in _INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, normalised):
                if base_conf > best_conf:
                    best_conf = base_conf
                    best_intent = intent
                break
    return best_intent, best_conf

# Step 2 — Token extraction

def _extract_tokens(normalised: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", normalised)
    words = cleaned.split()
    tokens = [w for w in words if w not in _STOP_WORDS and len(w) >= 3]
    # Also add bigrams for compound column names like "units_sold"
    bigrams = [
        f"{words[i]}_{words[i+1]}"
        for i in range(len(words) - 1)
        if words[i] not in _STOP_WORDS and words[i+1] not in _STOP_WORDS
        and len(words[i]) >= 3 and len(words[i+1]) >= 3
    ]
    return list(dict.fromkeys(tokens + bigrams))  # deduplicate, preserve order

# Step 3 — Per-token column mapping (the KEY fix)

def _normalize_token(token: str) -> str:
    """
    Apply the same normalisation as profiler._normalize_column_alias so tokens
    and column aliases are compared on equal footing.
    Strips currency/unit symbols, collapses separators to underscores.
    """
    t = token.lower()
    t = re.sub(r"[$£€%#@!?()[\]{}]", "", t)
    t = re.sub(r"[\s\-./\\]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t

def _map_columns_per_token(
    tokens: list[str],
    profile: DatasetProfile,
) -> tuple[list[str], Optional[str], list[AmbiguityItem]]:
    """
    Map each token independently to the best-matching column.

    Matching runs on *both* the raw column name and its normalized_alias
    so that noisy names like "Revenue($)" or "Avg-Cost" are reachable
    from plain user terms like "revenue" or "average cost".

    Returns:
      mapped          — list of uniquely matched column names (original names)
      ambiguous_token — the token that caused ambiguity (if any)
      ambiguity_items — candidates for the ambiguous token
    """
    # Build two search targets per column: raw name + normalized alias.
    # Both map back to the original column name.
    raw_names = [c.name for c in profile.columns]
    alias_map: dict[str, str] = {}   # alias_key → original_name
    search_pool: list[str] = []

    for col in profile.columns:
        # raw name always included
        search_pool.append(col.name)
        alias_map[col.name] = col.name
        # normalized alias — only add when it differs from the raw name
        alias = col.normalized_alias or _normalize_token(col.name)
        if alias and alias != col.name:
            key = f"__alias__{alias}"   # prefix prevents collision with real col names
            alias_map[key] = col.name
            search_pool.append(key)

    if not search_pool or not tokens:
        return [], None, []

    mapped_cols: list[str] = []
    ambiguous_token: Optional[str] = None
    ambiguity_items: list[AmbiguityItem] = []

    for token in tokens:
        # Also try normalized form of the token against the pool
        norm_token = _normalize_token(token)
        candidates_to_try = list(dict.fromkeys([token, norm_token]))  # deduplicate

        best_matches: dict[str, float] = {}   # original_col_name → best score

        for t in candidates_to_try:
            results = fuzz_process.extract(
                t,
                search_pool,
                scorer=fuzz.token_set_ratio,
                limit=6,
            )
            for key, score, _ in results:
                if score < FUZZY_MATCH_THRESHOLD:
                    continue
                orig = alias_map.get(key, key)
                if score > best_matches.get(orig, 0):
                    best_matches[orig] = score

        good = sorted(best_matches.items(), key=lambda x: -x[1])
        if not good:
            continue

        if len(good) == 1:
            # Clear winner — add it
            col_name = good[0][0]
            if col_name not in mapped_cols:
                mapped_cols.append(col_name)
        else:
            # Multiple candidates — check gap between top two
            top_score = good[0][1]
            second_score = good[1][1]
            gap = top_score - second_score

            if gap > AMBIGUITY_SCORE_GAP:
                # Clear winner despite multiple candidates
                col_name = good[0][0]
                if col_name not in mapped_cols:
                    mapped_cols.append(col_name)
            else:
                # Genuinely ambiguous token — but only flag if top score is HIGH
                # (meaning the system is confident this token IS a column reference,
                # just unsure WHICH one)
                if top_score >= 80 and not ambiguous_token:
                    ambiguous_token = token
                    col_meta_map = {c.name: c for c in profile.columns}
                    ambiguity_items = [
                        AmbiguityItem(
                            candidate_column=col,
                            similarity_score=round(score / 100, 4),
                            display_label=f"{col} ({col_meta_map[col].dtype.value if col in col_meta_map else 'unknown'})",
                        )
                        for col, score in good[:4]
                    ]
                else:
                    # Low-confidence multi-match — just take the best one
                    col_name = good[0][0]
                    if col_name not in mapped_cols:
                        mapped_cols.append(col_name)

    # Post-loop disambiguation: if ANY candidate for the ambiguous token was
    # independently confirmed by another token in the same query, the ambiguity
    # is resolved — clear it so the query can proceed normally WITHOUT adding
    # the spurious top candidate.
    # Example: "customer" is ambiguous (customer_segment vs customer_age), but
    # "segment" independently mapped to customer_segment → ambiguity resolved,
    # do NOT add customer_age just because it scored highest for "customer".
    if ambiguous_token and ambiguity_items:
        any_candidate_mapped = any(
            item.candidate_column in mapped_cols for item in ambiguity_items
        )
        if any_candidate_mapped:
            ambiguous_token = None
            ambiguity_items = []
        else:
            # Still ambiguous — add the top candidate so we have at least one column
            top_candidate = ambiguity_items[0].candidate_column
            if top_candidate not in mapped_cols:
                mapped_cols.append(top_candidate)

    return mapped_cols, ambiguous_token, ambiguity_items

# Step 4 — Semantic fallback

def _semantic_fallback(
    tokens: list[str],
    normalised: str,
    profile: DatasetProfile,
) -> list[str]:
    candidate_tags: list[SemanticTag] = []
    for token in tokens:
        candidate_tags.extend(_SEMANTIC_SYNONYMS.get(token, []))
    for synonym, tags in _SEMANTIC_SYNONYMS.items():
        if re.search(r"\b" + re.escape(synonym) + r"\b", normalised):
            candidate_tags.extend(tags)

    if not candidate_tags:
        return []

    matched = []
    for col in profile.columns:
        if col.semantic_tag in candidate_tags and col.name not in matched:
            matched.append(col.name)
    return matched

# Step 5 — Filter detection

_INVALID_FILTER_VALS: frozenset[str] = frozenset({
    "above", "below", "less", "more", "than", "across", "orders", "dataset",
    "data", "from", "and", "or", "not", "orders", "records", "rows", "items",
    "total", "average", "mean", "count", "sum", "all", "each", "every",
})

def _detect_filter(
    normalised: str,
    profile: DatasetProfile,
    raw_query: str = "",
) -> Optional[FilterCondition]:
    all_col_names = [c.name for c in profile.columns]
    # Use raw query for value extraction to preserve case; normalised for pattern matching
    for pattern in _FILTER_PATTERNS:
        m = re.search(pattern, normalised, re.IGNORECASE)
        if m:
            col_term = m.group(1).strip()
            filter_val = m.group(2).strip()
            # Reject values that are clearly not column values (operators, aggregates, stopwords)
            if filter_val.lower() in _INVALID_FILTER_VALS:
                continue
            # Reject purely numeric filter values (those are thresholds, not category values)
            if re.match(r'^\d+(\.\d+)?%?$', filter_val):
                continue
            # Try to recover original-case value from raw query
            if raw_query:
                raw_m = re.search(pattern, raw_query, re.IGNORECASE)
                if raw_m:
                    filter_val = raw_m.group(2).strip()
            result = fuzz_process.extractOne(
                col_term, all_col_names, scorer=fuzz.token_set_ratio
            )
            if result and result[1] >= FUZZY_MATCH_THRESHOLD:
                return FilterCondition(
                    column=result[0],
                    operator="eq",
                    value=filter_val,
                )
    return None

# Step 6 — Confidence scoring

def _compute_confidence(
    intent: QueryIntent,
    intent_conf: float,
    mapped_cols: list[str],
    is_ambiguous: bool,
    profile: DatasetProfile,
) -> tuple[float, str]:
    base = intent_conf if intent != QueryIntent.unknown else 0.30
    col_bonus = min(0.12, 0.06 * len(mapped_cols)) if mapped_cols else -0.15
    ambiguity_penalty = -0.10 if is_ambiguous else 0.0

    # missing_data doesn't need columns
    if intent == QueryIntent.missing_data:
        col_bonus = 0.08
        ambiguity_penalty = 0.0

    confidence = max(0.0, min(1.0, base + col_bonus + ambiguity_penalty))
    explanation = _build_explanation(intent, mapped_cols)
    return confidence, explanation

def _build_explanation(intent: QueryIntent, mapped_cols: list[str]) -> str:
    intent_labels = {
        QueryIntent.ranking: "find the top/bottom values",
        QueryIntent.trend: "show a trend over time",
        QueryIntent.correlation: "analyse relationships between columns",
        QueryIntent.distribution: "show the distribution and statistics",
        QueryIntent.missing_data: "summarise missing values",
        QueryIntent.aggregation: "compute an aggregate (total, average, count)",
        QueryIntent.comparison: "compare values across groups",
        QueryIntent.feature_importance: "find what most influences a column",
        QueryIntent.unknown: "perform an analysis",
        # Phase 3 advanced intents
        QueryIntent.targeted_correlation: "compute targeted correlation between two specific columns",
        QueryIntent.compound_filter: "filter rows matching two simultaneous conditions",
        QueryIntent.derived_metric: "compute a derived metric and analyse its distribution",
        QueryIntent.period_growth: "analyse period-over-period growth",
        QueryIntent.anomaly_query: "detect anomalous rows",
        QueryIntent.multi_criteria_rank: "rank groups by multiple weighted criteria",
        QueryIntent.business_decision: "produce a ranked business recommendation",
        QueryIntent.scenario_analysis: "compare high vs low condition groups",
        QueryIntent.open_ended_insight: "generate multiple sub-analyses",
        QueryIntent.segment_comparison: "compare two named segments across metrics",
        QueryIntent.threshold_analysis: "filter rows above/below a threshold and summarise",
        QueryIntent.seasonal_pattern: "decompose and analyse seasonal patterns",
        QueryIntent.combination_ranking: "rank combinations of multiple categories by a metric",
        QueryIntent.efficiency_query: "rank groups by efficiency ratio (profit per cost or similar)",
    }
    action = intent_labels.get(intent, "perform an analysis")
    if mapped_cols:
        cols_str = " and ".join(f"'{c}'" for c in mapped_cols[:3])
        return f"I interpreted your question as: {action} for {cols_str}."
    return f"I interpreted your question as: {action}."

# Step 8 — Operation string

def _build_operation(intent: QueryIntent) -> str:
    return {
        QueryIntent.ranking: "groupby_sum_rank",
        QueryIntent.trend: "time_series_aggregate",
        QueryIntent.correlation: "pearson_correlation",
        QueryIntent.distribution: "descriptive_stats",
        QueryIntent.missing_data: "missing_value_count",
        QueryIntent.aggregation: "aggregate_sum_mean",
        QueryIntent.comparison: "groupby_aggregation",
        QueryIntent.feature_importance: "feature_importance",
        QueryIntent.unknown: "unknown",
        # Phase 3 advanced intents
        QueryIntent.targeted_correlation: "targeted_correlation",
        QueryIntent.compound_filter: "compound_filter",
        QueryIntent.derived_metric: "derived_metric",
        QueryIntent.period_growth: "period_growth",
        QueryIntent.anomaly_query: "anomaly_query",
        QueryIntent.multi_criteria_rank: "multi_criteria_rank",
        QueryIntent.business_decision: "business_decision",
        QueryIntent.scenario_analysis: "scenario_analysis",
        QueryIntent.open_ended_insight: "open_ended_insight",
        QueryIntent.segment_comparison: "segment_comparison",
        QueryIntent.threshold_analysis: "threshold_analysis",
        QueryIntent.seasonal_pattern: "seasonal_pattern",
        QueryIntent.combination_ranking: "combination_groupby_rank",
        QueryIntent.efficiency_query: "efficiency_score_rank",
    }.get(intent, "unknown")

# Helpers

def _normalise(query: str) -> str:
    return re.sub(r"\s+", " ", query.lower().strip())

def _best_unmatched_term(tokens: list[str]) -> str:
    candidates = [t for t in tokens if len(t) >= 3 and "_" not in t]
    return candidates[0] if candidates else (tokens[0] if tokens else "that term")
