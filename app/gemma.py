"""Small Ollama client used by the Phase 1 prototype."""

import json
import os
from dataclasses import dataclass
from urllib import error, parse, request


class OllamaError(RuntimeError):
    """Raised when the local Ollama request cannot be completed."""


class GeminiError(RuntimeError):
    """Raised when the hosted Gemini API request cannot be completed."""


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


@dataclass
class GeminiClient:
    """Client for hosted Gemma through Google's Gemini API."""

    api_key: str
    model: str = "gemma-4-26b-a4b-it"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    timeout: float = 120.0

    @classmethod
    def from_environment(cls, model: str | None = None) -> "GeminiClient":
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is not set.")
        return cls(api_key=api_key, model=model or cls.model)

    def generate(self, prompt: str) -> str:
        """Generate a JSON response from hosted Gemma."""

        response_schema = {
            "type": "object",
            "required": ["issue_summary", "relevant_files", "implementation_plan", "tests", "risks"],
            "properties": {
                "issue_summary": {"type": "string"},
                "relevant_files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["path", "reason"],
                        "properties": {
                            "path": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                    },
                },
                "implementation_plan": {"type": "array", "items": {"type": "string"}},
                "tests": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
            },
        }
        payload = json.dumps(
            {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": response_schema,
                    "temperature": 0.2,
                    "thinkingConfig": {"thinkingLevel": "minimal"},
                },
            }
        ).encode("utf-8")
        endpoint = (
            f"{self.base_url.rstrip('/')}/models/{parse.quote(self.model, safe='')}"
            f":generateContent?key={parse.quote(self.api_key)}"
        )
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
            raise GeminiError(f"Gemini API returned HTTP {exc.code}: {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise GeminiError("Could not connect to the Gemini API.") from exc
        except json.JSONDecodeError as exc:
            raise GeminiError("Gemini API returned invalid JSON.") from exc

        try:
            result = body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiError("Gemini API response did not contain generated text.") from exc
        if not isinstance(result, str) or not result.strip():
            raise GeminiError("Gemini API returned empty generated text.")
        return result
