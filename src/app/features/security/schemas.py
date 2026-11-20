import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.features.account.schemas import ConfirmPassword
from app.features.auth.schemas import Password, TwoFactorCode


class TwoFactorStatus(BaseModel):
    enabled: bool
    enabled_at: datetime | None
    recovery_codes_remaining: int


class TwoFactorSetupRequest(BaseModel):
    password: ConfirmPassword


class TwoFactorSetup(BaseModel):
    secret: str
    otpauth_uri: str


class TwoFactorEnableRequest(BaseModel):
    code: TwoFactorCode


class TwoFactorDisableRequest(BaseModel):
    password: ConfirmPassword
    code: TwoFactorCode


class RecoveryCodesRequest(BaseModel):
    password: ConfirmPassword


class RecoveryCodes(BaseModel):
    codes: list[str]


class PasswordChange(BaseModel):
    current_password: ConfirmPassword
    new_password: Password


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    last_active_at: datetime
    expires_at: datetime
    user_agent: str | None
    current: bool


class SessionsRevoked(BaseModel):
    revoked: int
