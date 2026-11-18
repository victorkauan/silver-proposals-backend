---
status: accepted
date: 2026-11-17
decision-makers: Victor Kauan
---

# Stream AI generation with server-sent events behind a provider interface

## Context and Problem Statement

A proposal is generated from its briefing by a large language model on Amazon Bedrock. A full document takes roughly
30 to 90 seconds. The load balancer closes idle connections after 60 seconds by default, and users should not stare at
a spinner for a minute. Tests and CI must never call the real model. How should the API deliver the result, and how
should the code depend on the model?

## Decision Drivers

- Generation can take longer than the load balancer idle timeout.
- Users should see progress immediately.
- Tests and CI must run without AWS credentials and without cost.
- The model must be replaceable (Claude, GPT, a stronger tier) without code changes.

## Considered Options

- Single JSON response after generation finishes
- Asynchronous job with polling
- Server-sent events (SSE) streaming the text as it is produced

## Decision Outcome

Chosen option: **SSE streaming behind a provider interface**.

- `POST /proposals/{id}/generate` answers `text/event-stream` with `delta` events while the model writes, then `done`
  after the content is saved, or `error` with a stable code. Authorization and validation errors still answer as JSON
  before the stream starts.
- The application depends on an `LLMProvider` protocol (`app/shared/adapters/llm`). `FakeProvider` is the default for
  local development and CI. `BedrockProvider` uses the Converse streaming API. `AI_PROVIDER` and `BEDROCK_MODEL_ID`
  select the provider and the model.
- In AWS, the provider authenticates only through the ECS task role. There are no keys anywhere.

### Consequences

- Good, because bytes keep flowing, so the 60-second idle timeout is never reached, and the first words appear in seconds.
- Good, because CI and local development need no credentials, and swapping models is a configuration change.
- Bad, because the frontend reads the stream with `fetch` instead of a plain JSON call.
- Bad, because the IAM policy needs `bedrock:InvokeModelWithResponseStream`, not only `bedrock:InvokeModel`.

## Pros and Cons of the Options

### Single JSON response

- Good, because it is the simplest client code.
- Bad, because it needs a longer load balancer timeout and shows no progress.

### Asynchronous job with polling

- Good, because it survives disconnections.
- Bad, because it needs a job store, a worker, and polling, which is too much for v1.

### Server-sent events

- Good, because it gives immediate feedback and needs no extra infrastructure.
- Bad, because a dropped connection loses the in-progress text. The previous content stays untouched, and the user can retry.

## More Information

- [Generation reference](../reference/generation.md)
