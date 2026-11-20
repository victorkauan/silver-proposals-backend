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
    VERSION_CONFLICT = "version_conflict"
    VERSION_NOT_FOUND = "version_not_found"
    SHARE_LINK_NOT_FOUND = "share_link_not_found"
    INVALID_PASSWORD = "invalid_password"
    INVALID_CHALLENGE = "invalid_challenge"
    INVALID_TWO_FACTOR_CODE = "invalid_two_factor_code"
    TWO_FACTOR_ALREADY_ENABLED = "two_factor_already_enabled"
    TWO_FACTOR_NOT_ENABLED = "two_factor_not_enabled"
    TWO_FACTOR_SETUP_REQUIRED = "two_factor_setup_required"
    SESSION_NOT_FOUND = "session_not_found"


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
    ErrorCode.VERSION_CONFLICT: (
        "A proposta foi alterada por outra pessoa. Recarregue para ver a versão mais recente."
    ),
    ErrorCode.VERSION_NOT_FOUND: "Versão não encontrada.",
    ErrorCode.SHARE_LINK_NOT_FOUND: "Link inválido ou expirado.",
    ErrorCode.INVALID_PASSWORD: "Senha incorreta.",
    ErrorCode.INVALID_CHALLENGE: "A verificação expirou. Entre com seu e-mail e senha novamente.",
    ErrorCode.INVALID_TWO_FACTOR_CODE: (
        "Código inválido. Confira o app autenticador e tente de novo."
    ),
    ErrorCode.TWO_FACTOR_ALREADY_ENABLED: "A verificação em duas etapas já está ativa.",
    ErrorCode.TWO_FACTOR_NOT_ENABLED: "A verificação em duas etapas não está ativa.",
    ErrorCode.TWO_FACTOR_SETUP_REQUIRED: "Comece a configuração do app autenticador novamente.",
    ErrorCode.SESSION_NOT_FOUND: "Sessão não encontrada ou já encerrada.",
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
