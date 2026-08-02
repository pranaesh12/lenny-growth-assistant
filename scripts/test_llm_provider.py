"""
CLI script: test the configured LLM provider end-to-end.

Usage:
    python scripts/test_llm_provider.py

Loads Settings, instantiates the configured provider via LLMManager,
runs a health check, sends a simple test prompt, and prints the
result — provider, model, latency, response content, and token usage.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.llm.exceptions import LLMError  # noqa: E402
from app.llm.manager import LLMManager  # noqa: E402
from app.llm.schemas import LLMRequest  # noqa: E402
from app.utils.logger import get_logger, log_exception  # noqa: E402

log = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    print(f"Configured provider: {settings.DEFAULT_PROVIDER.value}\n")

    try:
        manager = LLMManager(settings=settings)
    except LLMError as exc:
        print(f"Failed to initialize provider: {exc}")
        log_exception("LLM provider initialization failed")
        sys.exit(1)

    print("Running health check...")
    try:
        manager.health_check()
        print("Health check passed.\n")
    except LLMError as exc:
        print(f"Health check FAILED: {exc}")
        log_exception("LLM health check failed")
        sys.exit(1)

    print("Sending test prompt...")
    request = LLMRequest(prompt="Reply with exactly: Hello from Lenny.", max_tokens=50)

    start_time = time.perf_counter()
    try:
        response = manager.generate(request)
    except LLMError as exc:
        print(f"Generation FAILED: {exc}")
        log_exception("LLM generation failed")
        sys.exit(1)
    elapsed = time.perf_counter() - start_time

    print("\n--- Result ---")
    print(f"Provider:        {response.provider}")
    print(f"Model:           {response.model}")
    print(f"Latency:         {response.latency_ms:.1f} ms (wall clock: {elapsed * 1000:.1f} ms)")
    print(f"Response:        {response.content}")
    print(f"Prompt tokens:   {response.prompt_tokens}")
    print(f"Completion tok.: {response.completion_tokens}")
    print(f"Total tokens:    {response.total_tokens}")
    print(f"Finish reason:   {response.finish_reason}")


if __name__ == "__main__":
    main()