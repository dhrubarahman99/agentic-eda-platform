# Feedback storage and adaptation hints using RapidFuzz similarity matching against SQLite.

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional, TypedDict

from app.utils.database import DB_PATH, get_db

# Keep for backward compat with the /feedback/stats endpoint
_STORE_PATH = str(DB_PATH)

# Similarity threshold on 0–100 scale (token_set_ratio or difflib×100).
# 65 works well for short analytical questions.
SIMILARITY_THRESHOLD = 65

# Record shape

class FeedbackRecord(TypedDict):
    record_id:    str
    user_id:      Optional[int]
    session_id:   str
    query_id:     str
    question:     str        # ORIGINAL user question (never the assistant's response)
    intent:       str        # intent the system used when answering
    columns_used: list       # column names the system mapped
    plain_summary:str        # first 400 chars of the assistant answer
    feedback:     str        # "positive" | "negative"
    timestamp:    str        # ISO-8601 UTC

# Validation helper

def _is_valid_record(rec: object) -> bool:
    """Return True only for well-formed, non-empty FeedbackRecords."""
    if not isinstance(rec, dict):
        return False
    if rec.get("feedback") not in ("positive", "negative"):
        return False
    if not isinstance(rec.get("question"), str) or not rec["question"].strip():
        return False
    if not isinstance(rec.get("intent"), str) or not rec["intent"].strip():
        return False
    return True

# Similarity engine  (RapidFuzz → difflib fallback, no ML, no embeddings)

def _normalize_query(text: str) -> str:
    """Lowercase and strip punctuation — keeps all content words for better matching."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def compute_similarity(q1: str, q2: str) -> float:
    """
    Token-set ratio similarity, normalised to 0.0–100.0.

    RapidFuzz token_set_ratio handles word-order differences and partial
    overlaps well (e.g. "What affects profit?" ≈ "What drives profit?").
    Falls back to difflib.SequenceMatcher if RapidFuzz is unavailable.
    """
    a = _normalize_query(q1)
    b = _normalize_query(q2)
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz import fuzz
        return float(fuzz.token_set_ratio(a, b))
    except ImportError:
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio() * 100.0

# Fallback intent heuristic  (fully rule-based, deterministic)

# Each entry: (failed_intent, trigger_keywords_in_query, suggested_fallback)
# Matched in order; first match wins.
_INTENT_FALLBACK_RULES: list[tuple[str, list[str], str]] = [
    ("comparison", ["affect", "impact", "influence", "drive", "cause",
                    "increase", "decrease", "change", "leads to"],       "scenario_analysis"),
    ("comparison", ["rank", "top", "best", "highest", "lowest",
                    "most", "least", "leading", "largest", "smallest"],  "ranking"),
    ("comparison", ["trend", "over time", "growth", "monthly",
                    "weekly", "yearly"],                                  "trend"),
    ("comparison", ["correlat", "relationship", "related",
                    "associated", "linked"],                              "correlation"),

    ("aggregation", ["top", "best", "highest", "most", "rank",
                     "leading", "largest"],                               "ranking"),
    ("aggregation", ["trend", "over time", "growth", "monthly",
                     "change", "trajectory"],                             "trend"),
    ("aggregation", ["affect", "impact", "drive", "factor",
                     "influence", "determine"],                           "feature_importance"),

    ("correlation", ["affect", "impact", "drive", "cause", "influence",
                     "determine", "factor", "key", "main"],              "feature_importance"),
    ("correlation", ["scenario", "if", "when", "condition",
                     "high", "low", "threshold"],                        "scenario_analysis"),
    ("correlation", ["anomaly", "outlier", "unusual",
                     "abnormal", "extreme"],                              "anomaly_query"),

    ("ranking",     ["trend", "over time", "growth", "change",
                     "monthly", "yearly"],                                "trend"),
    ("ranking",     ["compare", "vs", "versus", "difference",
                     "across", "between"],                                "comparison"),
    ("ranking",     ["affect", "impact", "drive", "factor"],             "feature_importance"),

    ("trend",       ["rank", "top", "best", "highest", "most",
                     "leading"],                                          "ranking"),
    ("trend",       ["compare", "across", "by", "between",
                     "versus"],                                           "comparison"),
    ("trend",       ["anomaly", "outlier", "unusual",
                     "spike", "drop"],                                    "anomaly_query"),

    ("feature_importance", ["trend", "over time",
                             "growth"],                                   "trend"),
    ("feature_importance", ["anomaly", "outlier",
                             "unusual", "abnormal"],                      "anomaly_query"),
    ("feature_importance", ["compare", "vs",
                             "across", "by region"],                      "comparison"),

    ("distribution", ["rank", "top", "highest",
                      "lowest", "best"],                                  "ranking"),
    ("distribution", ["trend", "over time",
                      "growth"],                                          "trend"),

    ("missing_data", ["rank", "top", "highest"],                         "ranking"),
    ("missing_data", ["correlat", "relationship"],                       "correlation"),
]

def _get_intent_fallback(question: str, failed_intent: str) -> Optional[str]:
    """
    Given a failed intent and the current question, return a better intent
    suggestion using the fallback rule table.  Pure rule-based, deterministic.
    Returns None if no rule matches.
    """
    q_lower = question.lower()
    for rule_intent, keywords, fallback in _INTENT_FALLBACK_RULES:
        if rule_intent != failed_intent:
            continue
        if any(kw in q_lower for kw in keywords):
            return fallback
    return None

# FeedbackStore

class FeedbackStore:
    """
    Thread-safe, SQLite-backed store for user feedback records.

    In-memory list (_records) is used for fast similarity scanning.
    SQLite is the authoritative store — _records is loaded from DB at startup
    and extended synchronously on each add_feedback() call.

    add_feedback(user_id=...)     — persist a new record; user-scoped
    get_adaptation_hints(user_id=...) — similarity search; scoped to user
    list_all()                    — return all records (debug endpoint)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[FeedbackRecord] = []
        self._load()

    # ── Initialisation from DB ───────────────────────────────────────────────

    def _load(self) -> None:
        """Load all feedback records from SQLite into memory."""
        try:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT record_id, user_id, session_id, query_id, question,
                              intent, columns_used, plain_summary, feedback, created_at
                       FROM feedback
                       ORDER BY id ASC"""
                ).fetchall()
            self._records = []
            for row in rows:
                try:
                    columns_used = json.loads(row["columns_used"] or "[]")
                except Exception:
                    columns_used = []
                rec: FeedbackRecord = {
                    "record_id":    row["record_id"],
                    "user_id":      row["user_id"],
                    "session_id":   row["session_id"] or "",
                    "query_id":     row["query_id"] or "",
                    "question":     row["question"],
                    "intent":       row["intent"],
                    "columns_used": columns_used,
                    "plain_summary":row["plain_summary"] or "",
                    "feedback":     row["feedback"],
                    "timestamp":    row["created_at"] or "",
                }
                if _is_valid_record(rec):
                    self._records.append(rec)
        except Exception:
            self._records = []  # DB not ready yet (e.g. before init_db()) — start fresh

    # ── Public API ────────────────────────────────────────────────────────────

    def add_feedback(
        self,
        session_id: str,
        query_id: str,
        question: str,          # must be the ORIGINAL user question
        intent: str,
        columns_used: list,
        plain_summary: str,
        feedback: str,          # "positive" | "negative" only
        user_id: Optional[int] = None,
    ) -> str:
        """
        Persist a feedback record to SQLite and the in-memory list.
        Invalid feedback values are rejected silently (returns "").
        Thread-safe.
        """
        if feedback not in ("positive", "negative"):
            return ""
        question = question.strip()
        if not question:
            return ""

        record: FeedbackRecord = {
            "record_id":    str(uuid.uuid4()),
            "user_id":      user_id,
            "session_id":   str(session_id),
            "query_id":     str(query_id),
            "question":     question,
            "intent":       str(intent).strip(),
            "columns_used": [str(c) for c in columns_used if c],
            "plain_summary":str(plain_summary)[:400],
            "feedback":     feedback,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            # Write to SQLite first
            try:
                with get_db() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO feedback
                           (record_id, user_id, session_id, query_id, question,
                            intent, columns_used, plain_summary, feedback)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            record["record_id"],
                            user_id,
                            record["session_id"],
                            record["query_id"],
                            record["question"],
                            record["intent"],
                            json.dumps(record["columns_used"]),
                            record["plain_summary"],
                            record["feedback"],
                        ),
                    )
            except Exception:
                pass  # never crash the query pipeline over a DB write failure

            # Always update in-memory list (even if DB write failed — stays consistent for session)
            self._records.append(record)

        return record["record_id"]

    def get_adaptation_hints(
        self,
        question: str,
        threshold: float = SIMILARITY_THRESHOLD,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Scan past feedback for questions similar to *question* and return hints.

        When user_id is provided, only that user's own feedback is considered.
        This prevents user A's negative feedback from affecting user B's queries.

        Returned dict keys:
          avoid_intent     (str | None) — intent proven unhelpful for a similar Q
          preferred_intent (str | None) — intent proven helpful for a similar Q
          fallback_intent  (str | None) — deterministic rule-based fallback for avoid_intent
          similarity_note  (str | None) — human-readable trace string

        Algorithm:
          1. Normalise + compute token_set_ratio between question and stored Qs.
          2. Accept candidates with score >= threshold (default 65/100).
          3. Among qualifying negatives → pick highest-similarity as avoid_intent.
          4. Among qualifying positives → pick highest-similarity as preferred_intent.
          5. For avoid_intent → look up deterministic fallback heuristic.
        """
        hints: dict = {
            "avoid_intent":     None,
            "preferred_intent": None,
            "fallback_intent":  None,
            "similarity_note":  None,
        }

        with self._lock:
            # Scope to user's own records if user_id is provided
            if user_id is not None:
                records = [r for r in self._records if r.get("user_id") == user_id]
            else:
                records = list(self._records)

        if not records:
            return hints

        best_negative: Optional[tuple[float, FeedbackRecord]] = None
        best_positive: Optional[tuple[float, FeedbackRecord]] = None

        for rec in records:
            if not _is_valid_record(rec):
                continue
            score = compute_similarity(question, rec["question"])
            if score < threshold:
                continue
            if rec["feedback"] == "negative":
                if best_negative is None or score > best_negative[0]:
                    best_negative = (score, rec)
            elif rec["feedback"] == "positive":
                if best_positive is None or score > best_positive[0]:
                    best_positive = (score, rec)

        notes: list[str] = []

        if best_negative:
            s, rec = best_negative
            hints["avoid_intent"] = rec["intent"]
            hints["fallback_intent"] = _get_intent_fallback(question, rec["intent"])
            fallback_note = (
                f" Fallback intent: '{hints['fallback_intent']}'."
                if hints["fallback_intent"] else ""
            )
            notes.append(
                f"Similar question (similarity {s:.0f}%) was marked unhelpful "
                f"when interpreted as '{rec['intent']}' — avoiding that intent.{fallback_note}"
            )

        if best_positive:
            s, rec = best_positive
            hints["preferred_intent"] = rec["intent"]
            notes.append(
                f"Similar question (similarity {s:.0f}%) was marked helpful "
                f"with intent '{rec['intent']}'."
            )

        if notes:
            hints["similarity_note"] = " ".join(notes)

        return hints

    def list_all(self) -> list:
        """Return a copy of all valid records (debug / GET endpoint)."""
        with self._lock:
            return [r for r in self._records if _is_valid_record(r)]

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

# Singleton — import and use `feedback_store` everywhere
feedback_store = FeedbackStore()
