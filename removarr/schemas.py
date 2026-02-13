from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional

class AccountCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    plex_token: str = Field(..., min_length=10)

class AccountOut(BaseModel):
    id: int
    label: str
    auth_method: str
    status: str
    last_check_at: Optional[str] = None
    last_ok_at: Optional[str] = None
    last_error: Optional[str] = None

class WebhookResult(BaseModel):
    removed: int
    scanned_accounts: int
    details: list[str] = []

class SetupAdmin(BaseModel):
    username: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=8, max_length=256)

class LoginReq(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=256)

class OAuthStartReq(BaseModel):
    label: Optional[str] = Field(None, max_length=200)

class OAuthStartRes(BaseModel):
    flow_id: str
    url: str

class OAuthStatusRes(BaseModel):
    flow_id: str
    status: str  # pending|ok|expired|error
    message: Optional[str] = None
    account_id: Optional[int] = None
    label: Optional[str] = None
