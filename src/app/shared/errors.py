from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    NOT_AUTHENTICATED = "not_authenticated"
    INVALID_TOKEN = "invalid_token"
    INVALID_CREDENTIALS = "invalid_credentials"
    INVALID_REFRESH_TOKEN = "invalid_refresh_token"
    EMAIL_TAKEN = "email_taken"
    RATE_LIMITED = "rate_limited"
    FORBIDDEN = "forbidden"
    PROPOSAL_NOT_FOUND = "proposal_not_found"
    BRIEFING_REQUIRED = "briefing_required"
    GENERATION_UNAVAILABLE = "generation_unavailable"
    GENERATION_TIMEOUT = "generation_timeout"
    GENERATION_FAILED = "generation_failed"


MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "Verifique os dados informados.",
    ErrorCode.NOT_AUTHENTICATED: "Faça login para continuar.",
    ErrorCode.INVALID_TOKEN: "Sua sessão expirou. Faça login novamente.",
    ErrorCode.INVALID_CREDENTIALS: "E-mail ou senha inválidos.",
    ErrorCode.INVALID_REFRESH_TOKEN: "Sua sessão expirou. Faça login novamente.",
    ErrorCode.EMAIL_TAKEN: "Já existe uma conta com este e-mail.",
    ErrorCode.RATE_LIMITED: "Muitas tentativas. Aguarde um instante e tente novamente.",
    ErrorCode.FORBIDDEN: "Você não tem permissão para esta ação.",
    ErrorCode.PROPOSAL_NOT_FOUND: "Proposta não encontrada.",
    ErrorCode.BRIEFING_REQUIRED: "Preencha o briefing antes de gerar a proposta.",
    ErrorCode.GENERATION_UNAVAILABLE: "O serviço de IA está ocupado. Tente novamente em instantes.",
    ErrorCode.GENERATION_TIMEOUT: "A geração demorou demais. Tente novamente.",
    ErrorCode.GENERATION_FAILED: "Não foi possível gerar a proposta. Tente novamente.",
}


class AppError(Exception):
    def __init__(
        self, code: ErrorCode, status_code: int, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.status_code = status_code
        self.headers = headers


def error_body(code: ErrorCode, **extra: Any) -> dict[str, Any]:
    return {"code": code.value, "message": MESSAGES[code], **extra}


async def handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(
        content=error_body(exc.code), status_code=exc.status_code, headers=exc.headers
    )


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    details = [
        {"field": ".".join(str(part) for part in error["loc"][1:]), "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        content=error_body(ErrorCode.VALIDATION_ERROR, details=details),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
