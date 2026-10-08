"""Small Ollama client used by the Phase 1 prototype."""

import json
from dataclasses import dataclass
from urllib import error, request


class OllamaError(RuntimeError):
    """Raised when the local Ollama request cannot be completed."""


@dataclass
class OllamaClient:
    """Client for Ollama's local text generation endpoint."""

    model: str = "gemma4:e4b"
    base_url: str = "http://localhost:11434"
    timeout: float = 120.0

    def generate(self, prompt: str) -> str:
        """Generate a JSON response from Ollama."""

        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            }
        ).encode("utf-8")
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        http_request = request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise OllamaError(
                "Could not connect to Ollama. Start Ollama and verify the model is available."
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama returned an invalid HTTP response.") from exc

        result = body.get("response")
        if not isinstance(result, str) or not result.strip():
            raise OllamaError("Ollama response did not contain generated text.")
        return result
