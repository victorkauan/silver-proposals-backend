---
status: accepted
date: 2026-11-22
decision-makers: Victor Kauan
---

# Use DeepInfra while the Bedrock quotas are zero

## Context and Problem Statement

The deployment moved to a new AWS project account. In that account, every Amazon Nova quota on Bedrock is 0 in the
US regions, including the tokens-per-day quota, which cannot be raised in Service Quotas. Every generation fails with
`ThrottlingException`. A quota increase was requested from AWS Support, but there is no date for an answer, and
generation is the product's core feature.

## Considered Options

- Wait for AWS Support, with generation unavailable.
- Call Bedrock from another AWS account.
- Add a second provider behind the existing provider interface ([ADR-0002](0002-stream-generation-behind-a-provider-interface.md))
  and switch to it with `AI_PROVIDER`.

## Decision Outcome

Chosen option: a `deepinfra` provider. It calls DeepInfra's OpenAI-compatible chat completions API with streaming,
using `zai-org/GLM-5.3-Flash`. The Bedrock provider stays in the code; switching back is a configuration change.

The model was chosen on 2026-11-22 by generating the same proposal (the production system prompt and one sample
briefing) with three fast DeepInfra models:

| Model | First text | Whole proposal | Followed the rules |
|---|---|---|---|
| `zai-org/GLM-5.3-Flash` | 3.5 s | 5.4 s | Yes: unknown items marked `[A DEFINIR]` |
| `meta-llama/Llama-4-Scout-17B-16E-Instruct` | 2.9 s | 8.8 s | No: invented a week-by-week schedule |
| `Qwen/Qwen3.8-Flash` | 31.2 s | 34.5 s | Yes, but it reasons before writing |

Larger models were too slow on DeepInfra's shared capacity for a streamed draft: `Qwen/Qwen3-235B-A22B-Instruct-2507`
took 25.6 s before its first token and wrote about 6 tokens per second.

### Consequences

- Good, because generation works again without waiting for AWS, and the rest of the generation flow is unchanged.
- Good, because the provider uses only the standard library, with no new dependency.
- Bad, because it needs an API key. The key lives in AWS Secrets Manager and reaches the task as `DEEPINFRA_API_KEY`;
  it is never in code or in Terraform state.
- Bad, because briefings now go to a third party outside AWS. The privacy notice names DeepInfra while this provider is
  active, and its version changed so that users accept it again.
- Bad, because calls to DeepInfra are not traced as AWS spans; the generation log line still records the model, latency,
  and tokens.
