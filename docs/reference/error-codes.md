# Error codes

Every error response has a stable machine-readable `code` and a `message` in Brazilian Portuguese, ready to show to users.
Clients should branch on `code`, never on `message`.

```json
{ "code": "invalid_credentials", "message": "E-mail ou senha inválidos." }
```

| Code | HTTP | Message |
|---|---|---|
| `validation_error` | 422 | Verifique os dados informados. |
| `not_authenticated` | 401 | Faça login para continuar. |
| `invalid_token` | 401 | Sua sessão expirou. Faça login novamente. |
| `invalid_credentials` | 401 | E-mail ou senha inválidos. |
| `invalid_refresh_token` | 401 | Sua sessão expirou. Faça login novamente. |
| `email_taken` | 409 | Já existe uma conta com este e-mail. |
| `rate_limited` | 429 | Muitas tentativas. Aguarde um instante e tente novamente. |
| `forbidden` | 403 | Você não tem permissão para esta ação. |
| `proposal_not_found` | 404 | Proposta não encontrada. |
| `briefing_required` | 422 | Preencha o briefing antes de gerar a proposta. |
| `version_conflict` | 409 | A proposta foi alterada por outra pessoa. Recarregue para ver a versão mais recente. |
| `version_not_found` | 404 | Versão não encontrada. |
| `share_link_not_found` | 404 | Link inválido ou expirado. |
| `invalid_password` | 403 | Senha incorreta. |
| `invalid_challenge` | 401 | A verificação expirou. Entre com seu e-mail e senha novamente. |
| `invalid_two_factor_code` | 401 (login), 400 (account) | Código inválido. Confira o app autenticador e tente de novo. |
| `two_factor_already_enabled` | 409 | A verificação em duas etapas já está ativa. |
| `two_factor_not_enabled` | 409 | A verificação em duas etapas não está ativa. |
| `two_factor_setup_required` | 409 | Comece a configuração do app autenticador novamente. |
| `session_not_found` | 404 | Sessão não encontrada ou já encerrada. |
| `generation_unavailable` | stream `error` | O serviço de IA está ocupado. Tente novamente em instantes. |
| `generation_timeout` | stream `error` | A geração demorou demais. Tente novamente. |
| `generation_failed` | stream `error` | Não foi possível gerar a proposta. Tente novamente. |

`validation_error` also carries `details`, a list of `{ "field": "<name>", "type": "<pydantic error type>" }` entries,
for example `{ "field": "password", "type": "string_too_short" }`. The catalog lives in `src/app/shared/errors.py`.
