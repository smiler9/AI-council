from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


SUPPORTED_PROVIDERS = {
    "mock",
    "local_openai_compatible",
    "openai_stub",
    "anthropic_stub",
    "gemini_stub",
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "mock"
    base_url: str = "http://localhost:11434/v1"
    model: str = "qwen3-coder:30b"
    api_key: str = "local"
    timeout_seconds: float = 60.0


def load_llm_config(environ: Mapping[str, str] | None = None) -> LLMConfig:
    values = os.environ if environ is None else environ
    provider = values.get("LLM_PROVIDER", "mock").strip() or "mock"
    if provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(f"Unsupported LLM_PROVIDER '{provider}'. Supported providers: {supported}")

    timeout_raw = values.get("LLM_TIMEOUT_SECONDS", "60").strip() or "60"
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("LLM_TIMEOUT_SECONDS must be a number") from exc

    if timeout_seconds <= 0:
        raise ValueError("LLM_TIMEOUT_SECONDS must be greater than 0")

    return LLMConfig(
        provider=provider,
        base_url=values.get("LLM_BASE_URL", "http://localhost:11434/v1").strip()
        or "http://localhost:11434/v1",
        model=values.get("LLM_MODEL", "qwen3-coder:30b").strip() or "qwen3-coder:30b",
        api_key=values.get("LLM_API_KEY", "local").strip() or "local",
        timeout_seconds=timeout_seconds,
    )
