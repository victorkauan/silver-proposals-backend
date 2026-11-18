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
| `generation_unavailable` | stream `error` | O serviço de IA está ocupado. Tente novamente em instantes. |
| `generation_timeout` | stream `error` | A geração demorou demais. Tente novamente. |
| `generation_failed` | stream `error` | Não foi possível gerar a proposta. Tente novamente. |

`validation_error` also carries `details`, a list of `{ "field": "<name>", "type": "<pydantic error type>" }` entries,
for example `{ "field": "password", "type": "string_too_short" }`. The catalog lives in `src/app/shared/errors.py`.
