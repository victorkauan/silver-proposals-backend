import re
import time
from collections.abc import Iterator

from app.shared.adapters.llm.base import GenerationRequest, StreamEvent, TextDelta, Usage

FAKE_PROPOSAL = """# Proposta comercial

> Documento gerado pelo provedor de teste, sem chamada a um modelo real.

## Resumo
Esta proposta apresenta o escopo, o cronograma e as condições para o projeto descrito no briefing.
O objetivo é entregar uma solução simples de manter, com resultados mensuráveis.

## Contexto e objetivos
- Aumentar a presença digital e facilitar o contato com novos clientes.
- Centralizar as informações que hoje estão espalhadas em vários canais.
- Permitir que a equipe do cliente atualize o conteúdo sem depender de terceiros.

## Escopo
### Incluído
- Levantamento de requisitos e alinhamento com a equipe do cliente.
- Design das telas principais, com versão para celular.
- Desenvolvimento, testes e publicação.
- Treinamento de uso para a equipe.

### Fora do escopo
- Integração com sistemas de pagamento.
- Produção de fotos e textos institucionais.

## Cronograma
| Etapa | Duração | Entrega |
|---|---|---|
| Descoberta | 1 semana | Requisitos validados |
| Design | 2 semanas | Telas aprovadas |
| Desenvolvimento | 2 semanas | Versão de homologação |
| Publicação | 1 semana | Projeto no ar |

## Investimento
[A DEFINIR]

## Condições
- Prazo de validade desta proposta: [A DEFINIR].
- Forma de pagamento: [A DEFINIR].

## Próximos passos
1. Revisar esta proposta e enviar ajustes.
2. Confirmar o investimento e a data de início.
3. Agendar a reunião de descoberta.
"""

WORD_BOUNDARY = re.compile(r"(?<=\s)(?=\S)")


class FakeProvider:
    model = "fake"

    def __init__(self, delay_ms: int = 0) -> None:
        self._delay_seconds = delay_ms / 1000

    def stream(self, request: GenerationRequest) -> Iterator[StreamEvent]:
        for word in WORD_BOUNDARY.split(FAKE_PROPOSAL):
            if self._delay_seconds:
                time.sleep(self._delay_seconds)
            yield TextDelta(word)
        yield Usage(input_tokens=len(request.prompt) // 4, output_tokens=len(FAKE_PROPOSAL) // 4)
