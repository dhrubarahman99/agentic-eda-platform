# Two-layer session store: in-memory DataFrames + SQLite metadata persistence.

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import pandas as pd

from app.models.schemas import DatasetProfile

class SessionStore:
    """Dict-backed in-memory session registry with SQLite persistence."""

    def __init__(self) -> None:
        self._frames:    dict[str, pd.DataFrame]   = {}
        self._profiles:  dict[str, DatasetProfile] = {}
        self._filenames: dict[str, str]             = {}

    # Write — in-memory only (called from upload.py directly)

    def create_session(
        self,
        df: pd.DataFrame,
        profile: DatasetProfile,
        filename: str,
    ) -> str:
        """Store a DataFrame + profile in memory and return the session_id."""
        session_id = str(uuid.uuid4())
        self._frames[session_id]    = df
        self._profiles[session_id]  = profile
        self._filenames[session_id] = filename
        return session_id

    # Read — in-memory first, SQLite fallback where appropriate

    def get_frame(self, session_id: str) -> Optional[pd.DataFrame]:
        return self._frames.get(session_id)

    def get_profile(self, session_id: str) -> Optional[DatasetProfile]:
        """Return the profile from memory, or restore it from the DB if needed."""
        profile = self._profiles.get(session_id)
        if profile is not None:
            return profile
        return self._restore_profile_from_db(session_id)

    def get_filename(self, session_id: str) -> Optional[str]:
        filename = self._filenames.get(session_id)
        if filename is not None:
            return filename
        # DB fallback
        try:
            from app.utils.database import get_db
            with get_db() as conn:
                row = conn.execute(
                    "SELECT filename FROM dataset_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            if row:
                return row["filename"]
        except Exception:
            pass
        return None

    def exists(self, session_id: str) -> bool:
        """True if the session is in memory OR recorded in SQLite."""
        if session_id in self._frames:
            return True
        try:
            from app.utils.database import get_db
            with get_db() as conn:
                row = conn.execute(
                    "SELECT 1 FROM dataset_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            return row is not None
        except Exception:
            return False

    # Housekeeping

    def delete_session(self, session_id: str) -> None:
        """Remove from both memory and SQLite."""
        self._frames.pop(session_id, None)
        self._profiles.pop(session_id, None)
        self._filenames.pop(session_id, None)
        try:
            from app.utils.database import get_db
            with get_db() as conn:
                conn.execute(
                    "DELETE FROM dataset_sessions WHERE session_id = ?",
                    (session_id,),
                )
        except Exception:
            pass

    def list_sessions(self) -> list[str]:
        """Return all session IDs currently held in memory."""
        return list(self._frames.keys())

    # SQLite persistence helpers (called from API layer after upload / analysis)

    def save_session_to_db(
        self,
        session_id: str,
        filename: str,
        profile: DatasetProfile,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Persist session metadata and the DatasetProfile JSON to SQLite.
        Called from upload.py immediately after a successful upload.
        Best-effort: silently no-ops on any DB failure.
        """
        try:
            from app.utils.database import get_db
            profile_json = profile.model_dump_json()
            with get_db() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO dataset_sessions
                       (session_id, user_id, filename, row_count, col_count,
                        quality_status, potential_target, profile_json,
                        created_at, last_accessed)
                       VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                    (
                        session_id,
                        user_id,
                        filename,
                        profile.shape.get("rows", 0),
                        profile.shape.get("cols", 0),
                        profile.data_quality.overall.value,
                        profile.potential_target,
                        profile_json,
                    ),
                )
        except Exception:
            pass  # never block the upload flow

    def save_analysis_to_db(
        self,
        session_id: str,
        insights: list,
        prep_report_summary: str,
    ) -> None:
        """
        Persist analysis results (insight metadata + preprocessing summary) to SQLite.
        Called from analysis.py after a successful run.
        Best-effort: silently no-ops on any DB failure.
        """
        try:
            from app.utils.database import get_db
            has_ml = any(
                getattr(i, "source_module", "") == "ml_module"
                for i in insights
            )
            # Slim JSON — only what the Sessions sidebar needs
            insights_data: list[dict[str, Any]] = [
                {
                    "rank":             i.rank,
                    "insight_id":       i.insight_id,
                    "type":             i.insight_type.value,
                    "source_module":    i.source_module,
                    "columns_used":     i.columns_used,
                    "plain_summary":    i.plain_summary,
                    "key_takeaway":     i.key_takeaway,
                    "impact_score":     round(i.impact_score, 4),
                    "confidence_score": round(i.confidence_score, 4),
                    "composite_score":  round(i.composite_score, 4),
                }
                for i in insights
            ]
            with get_db() as conn:
                conn.execute(
                    """UPDATE dataset_sessions SET
                           has_analysis     = 1,
                           total_insights   = ?,
                           has_ml_insights  = ?,
                           insights_json    = ?,
                           prep_report_json = ?,
                           last_accessed    = datetime('now')
                       WHERE session_id = ?""",
                    (
                        len(insights),
                        1 if has_ml else 0,
                        json.dumps(insights_data),
                        prep_report_summary,
                        session_id,
                    ),
                )
        except Exception:
            pass  # never block the analysis response

    def touch_session(self, session_id: str) -> None:
        """Bump last_accessed to now (call on any read that uses a session)."""
        try:
            from app.utils.database import get_db
            with get_db() as conn:
                conn.execute(
                    "UPDATE dataset_sessions SET last_accessed = datetime('now') WHERE session_id = ?",
                    (session_id,),
                )
        except Exception:
            pass

    def list_db_sessions(self, user_id: Optional[int] = None) -> list[dict]:
        """
        Return session metadata rows from SQLite, ordered by most recently
        accessed.  Optionally scoped to a specific user.
        Returns [] on any DB error so the Sessions sidebar degrades gracefully.
        """
        try:
            from app.utils.database import get_db
            with get_db() as conn:
                if user_id is not None:
                    rows = conn.execute(
                        """SELECT session_id, filename, row_count, col_count,
                                  quality_status, has_analysis, has_ml_insights,
                                  total_insights, potential_target
                           FROM dataset_sessions
                           WHERE user_id = ?
                           ORDER BY last_accessed DESC""",
                        (user_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT session_id, filename, row_count, col_count,
                                  quality_status, has_analysis, has_ml_insights,
                                  total_insights, potential_target
                           FROM dataset_sessions
                           ORDER BY last_accessed DESC""",
                    ).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

    # Private — DB fallback for profile restoration

    def _restore_profile_from_db(self, session_id: str) -> Optional[DatasetProfile]:
        """
        Reconstruct a DatasetProfile from the stored JSON blob.
        Also warms the in-memory caches so subsequent calls are instant.
        """
        try:
            from app.utils.database import get_db
            with get_db() as conn:
                row = conn.execute(
                    "SELECT profile_json, filename FROM dataset_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            if row and row["profile_json"]:
                profile = DatasetProfile.model_validate_json(row["profile_json"])
                # Warm in-memory cache
                self._profiles[session_id] = profile
                if row["filename"]:
                    self._filenames[session_id] = row["filename"]
                return profile
        except Exception:
            pass
        return None

# Singleton — imported by all modules that need session data
session_store = SessionStore()
