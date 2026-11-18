from collections.abc import Iterator

from app.shared.adapters.llm.base import GenerationRequest, StreamEvent, TextDelta, Usage

FAKE_PROPOSAL = """# Proposta comercial

## Resumo
Proposta gerada pelo provedor de teste, sem chamada a um modelo real.

## Escopo
- Levantamento de requisitos
- Desenvolvimento
- Entrega e acompanhamento

## Investimento
[A DEFINIR]
"""


class FakeProvider:
    model = "fake"

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        for line in FAKE_PROPOSAL.splitlines(keepends=True):
            yield TextDelta(line)
        yield Usage(input_tokens=len(request.prompt) // 4, output_tokens=len(FAKE_PROPOSAL) // 4)
