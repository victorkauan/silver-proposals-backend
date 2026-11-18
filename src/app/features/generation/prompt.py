from pathlib import Path

from app.shared.adapters.llm.base import GenerationRequest

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text(encoding="utf-8").strip()


def _as_data(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


def build_request(
    title: str, client_name: str, briefing: str, max_tokens: int
) -> GenerationRequest:
    prompt = (
        f"Proposta: {_as_data(title)}\n"
        f"Cliente: {_as_data(client_name)}\n\n"
        f"<briefing>\n{_as_data(briefing)}\n</briefing>"
    )
    return GenerationRequest(system=SYSTEM_PROMPT, prompt=prompt, max_tokens=max_tokens)
