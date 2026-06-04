# CSV upload, session creation, and dataset profiling.

import uuid
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from app.models.schemas import (
    DatasetProfile,
    ErrorResponse,
    ErrorType,
    UploadResponse,
)
from app.modules.file_handler import validate_and_parse
from app.modules.profiler import profile_dataset
from app.utils.auth_store import get_user_id_from_token
from app.utils.session_store import session_store

router = APIRouter()

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a CSV file and receive a full dataset profile",
    tags=["Upload"],
)
async def upload_csv(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
) -> UploadResponse:
    raw_bytes    = await file.read()
    filename     = file.filename or "upload.csv"
    content_type = file.content_type or "text/csv"

    try:
        df = validate_and_parse(filename, content_type, raw_bytes)
    except ValueError as exc:
        error_id = str(uuid.uuid4())
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(
                error_id=error_id,
                error_type=ErrorType.upload_error,
                message=str(exc),
                reason=str(exc),
                suggestions=[
                    "Ensure the file is a comma-separated .csv file.",
                    "Check that the file is under 10 MB.",
                    "Make sure the file has at least two columns and one data row.",
                ],
            ).model_dump(),
        )

    session_id = str(uuid.uuid4())
    profile    = profile_dataset(df, session_id)

    session_store._frames[session_id]    = df
    session_store._profiles[session_id]  = profile
    session_store._filenames[session_id] = filename

    user_id = get_user_id_from_token(authorization)

    session_store.save_session_to_db(
        session_id=session_id,
        filename=filename,
        profile=profile,
        user_id=user_id,
    )

    return UploadResponse(
        session_id=session_id,
        filename=filename,
        profile=profile,
    )

@router.get(
    "/session/{session_id}",
    response_model=DatasetProfile,
    summary="Retrieve the profile for an existing session",
    tags=["Session"],
)
async def get_session(session_id: str) -> DatasetProfile:
    profile = session_store.get_profile(session_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. "
                   "Please upload a CSV file first.",
        )
    return profile

@router.delete(
    "/session/{session_id}",
    summary="Delete a session and its stored data",
    tags=["Session"],
)
async def delete_session(session_id: str) -> dict:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )
    session_store.delete_session(session_id)
    return {"message": f"Session '{session_id}' deleted successfully."}
