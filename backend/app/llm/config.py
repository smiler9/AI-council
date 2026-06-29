from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


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
    max_tokens: int = 1200


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

    max_tokens_raw = values.get("LLM_MAX_TOKENS", "1200").strip() or "1200"
    try:
        max_tokens = int(max_tokens_raw)
    except ValueError as exc:
        raise ValueError("LLM_MAX_TOKENS must be an integer") from exc

    if max_tokens <= 0:
        raise ValueError("LLM_MAX_TOKENS must be greater than 0")

    base_url = values.get("LLM_BASE_URL", "http://localhost:11434/v1").strip()
    if not base_url:
        base_url = "http://localhost:11434/v1"
    if provider == "local_openai_compatible":
        _validate_local_base_url(base_url)

    return LLMConfig(
        provider=provider,
        base_url=base_url,
        model=values.get("LLM_MODEL", "qwen3-coder:30b").strip() or "qwen3-coder:30b",
        api_key=values.get("LLM_API_KEY", "local").strip() or "local",
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
    )


def _validate_local_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LLM_BASE_URL must be an http(s) URL for local_openai_compatible")
