import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Password = Annotated[str, Field(min_length=8, max_length=128)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class RegisterRequest(BaseModel):
    email: EmailStr
    name: Name
    password: Password
    accept_privacy: Literal[True]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    privacy_up_to_date: bool
    privacy_accepted_at: datetime | None
    two_factor_enabled: bool


TwoFactorCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=6, max_length=20)
]


class TwoFactorLoginRequest(BaseModel):
    challenge_token: Annotated[str, Field(min_length=1, max_length=2048)]
    code: TwoFactorCode


class TwoFactorChallengeResponse(BaseModel):
    two_factor_required: Literal[True] = True
    challenge_token: str
    expires_in: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
