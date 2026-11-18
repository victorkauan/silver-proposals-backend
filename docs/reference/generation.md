# Proposal generation

Design decision: [ADR-0002](../adr/0002-stream-generation-behind-a-provider-interface.md).

## Endpoint

`POST /proposals/{id}/generate`: requires `Authorization: Bearer`, and the caller must be owner or editor. The rate limit
is 10 requests per minute per IP. The proposal's saved `briefing` must not be empty.

Errors before the stream starts are regular JSON responses: `401`, `403 forbidden`, `404 proposal_not_found`,
`422 briefing_required`, `429 rate_limited`.

Otherwise the API answers `200` with `Content-Type: text/event-stream`:

```text
event: delta
data: {"text": "# Proposta comercial\n"}

event: delta
data: {"text": "## Resumo\n"}

event: done
data: {"proposal_id": "<uuid>"}
```

| Event | Data | Meaning |
|---|---|---|
| `delta` | `{"text": "..."}` | Next piece of Markdown. Append it in order. |
| `done` | `{"proposal_id": "..."}` | Generation finished and `content` was saved. |
| `error` | `{"code": "...", "message": "..."}` | Generation stopped. The previous `content` is unchanged. |

| Error code | Cause |
|---|---|
| `generation_unavailable` | Throttling or the service is temporarily unavailable. Retry later. |
| `generation_timeout` | The model took too long. |
| `generation_failed` | Any other provider error, or an empty answer. |

A dropped connection discards the partial text, and the saved content stays as it was.

## Prompt

The system prompt (`src/app/features/generation/system_prompt.md`) asks for a pt-BR Markdown proposal with fixed sections,
`[A DEFINIR]` for missing facts, and no invented values. The title, client, and briefing go in the user message. The
briefing is escaped and wrapped in `<briefing>` tags, and the model is told to treat it as data only. The prompt is never
returned by the API or written to logs.

## Providers

| `AI_PROVIDER` | Use |
|---|---|
| `fake` (default) | Local development and CI. Returns a fixed Markdown document with no network calls. |
| `bedrock` | Amazon Bedrock Converse streaming API, with the model from `BEDROCK_MODEL_ID`. |

Every request sets `maxTokens` (`GENERATION_MAX_TOKENS`, default 4096). Clients use adaptive retries and a read timeout
(`BEDROCK_READ_TIMEOUT_SECONDS`).

### Credentials and permissions

There are no AI keys in code, configuration, or Secrets Manager. Locally, boto3 uses your AWS profile. In AWS it uses
the ECS task role, which needs `bedrock:InvokeModelWithResponseStream` on the inference profile and on the underlying
foundation models.

## Logs

Each generation writes one JSON line: `generation_completed` with `model`, `latency_ms`, `input_tokens`, `output_tokens`,
and `content_chars`, or `generation_failed` with `error_code` and the provider error type. Briefings and generated text
are never logged.
