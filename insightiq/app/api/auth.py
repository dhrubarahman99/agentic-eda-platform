# Authentication endpoints: signup, login, logout, profile management.

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr

from app.utils.auth_store import (
    signup_user,
    login_user,
    logout_user,
    get_user_from_token,
    get_user_id_from_token,
    update_user_credentials,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UpdateCredentialsRequest(BaseModel):
    current_password: str
    name:             Optional[str]     = None
    email:            Optional[EmailStr]= None
    new_password:     Optional[str]     = None

class AuthResponse(BaseModel):
    token:    str
    email:    str
    name:     str
    is_admin: bool = False

class UserResponse(BaseModel):
    email:    str
    name:     str
    is_admin: bool = False

class MessageResponse(BaseModel):
    message: str

@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest):
    if len(body.name.strip()) < 1:
        raise HTTPException(status_code=422, detail="Name is required.")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters.")

    token = signup_user(body.name, body.email, body.password)
    if token is None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    return AuthResponse(token=token, email=body.email.lower(), name=body.name.strip())

@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    result = login_user(body.email, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token, user_info = result
    return AuthResponse(
        token=token,
        email=user_info["email"],
        name=user_info["name"],
        is_admin=user_info.get("is_admin", False),
    )

@router.post("/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    token = _extract_token(authorization)
    if token:
        logout_user(token)
    return {"ok": True}

@router.get("/me", response_model=UserResponse)
async def me(authorization: Optional[str] = Header(default=None)):
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing token.")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    return UserResponse(email=user["email"], name=user["name"], is_admin=user.get("is_admin", False))

@router.patch("/me", response_model=MessageResponse)
async def update_me(
    body: UpdateCredentialsRequest,
    authorization: Optional[str] = Header(default=None),
):
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token.")

    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    name_new = body.name.strip() if body.name else None
    if name_new is not None and len(name_new) < 1:
        raise HTTPException(status_code=422, detail="Name cannot be empty.")

    email_new = str(body.email).strip().lower() if body.email else None

    if body.new_password is not None and len(body.new_password) < 6:
        raise HTTPException(
            status_code=422,
            detail="New password must be at least 6 characters.",
        )

    error = update_user_credentials(
        user_id=user["id"],
        current_password=body.current_password,
        new_name=name_new,
        new_email=email_new,
        new_password=body.new_password,
    )

    if error == "wrong_password":
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if error == "email_taken":
        raise HTTPException(status_code=409, detail="That email address is already in use.")
    if error == "no_change":
        raise HTTPException(status_code=422, detail="No changes were made — the values you entered are the same as your current credentials.")
    if error is not None:
        raise HTTPException(status_code=500, detail="Could not update credentials. Please try again.")

    logout_user(token)

    return MessageResponse(message="Credentials updated successfully. Please log in with your new details.")

def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None
