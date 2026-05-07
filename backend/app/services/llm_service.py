"""Cliente LLM con soporte para Groq (cloud, gratis) y Ollama (local).

Prioridad de uso:
1. Groq API — si GROQ_API_KEY está configurada (gratis, Llama 3.3 70B).
2. Ollama  — si está corriendo localmente.

Groq es API-compatible con OpenAI. Free tier: 30 req/min, 14 400 req/día.
Modelos gratuitos: llama-3.3-70b-versatile, mistral-saba-24b, gemma2-9b-it.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Iterator

import httpx
from loguru import logger

from app.core.config import settings


# ── Groq client ──────────────────────────────────────────────────────
class GroqLLM:
    BASE = "https://api.groq.com/openai/v1"
    MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def complete(self, prompt: str, system: str | None = None,
                 temperature: float = 0.2, max_tokens: int = 2048) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.MODEL, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens}
        for attempt in range(4):
            try:
                r = httpx.post(f"{self.BASE}/chat/completions",
                               json=payload, headers=self.headers, timeout=120)
                if r.status_code == 429:
                    wait = 2 ** attempt * 3  # 3, 6, 12, 24 s
                    logger.warning(f"Groq 429 rate limit — reintentando en {wait}s (intento {attempt+1}/4)")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError:
                raise
            except Exception as e:
                logger.error(f"Groq error: {e}")
                return ""
        logger.error("Groq: máximo de reintentos alcanzado (429)")
        return ""

    def complete_json(self, prompt: str, system: str | None = None) -> Any:
        guard = ("Respond ONLY with valid JSON. No markdown, no commentary.")
        sys = f"{system}\n\n{guard}" if system else guard
        raw = self.complete(prompt, system=sys, temperature=0.0)
        return _safe_json_loads(raw)

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.MODEL, "messages": messages, "stream": True}
        with httpx.stream("POST", f"{self.BASE}/chat/completions",
                          json=payload, headers=self.headers, timeout=120) as r:
            for line in r.iter_lines():
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        token = chunk["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except Exception:
                        continue


# ── Ollama client ─────────────────────────────────────────────────────
class OllamaLLM:
    def __init__(self) -> None:
        self.host = settings.ollama_host.rstrip("/")
        self.primary = settings.ollama_model
        self.fallbacks = settings.ollama_fallback_models
        self.timeout = settings.ollama_timeout
        self._usable: str | None = None

    def _available_models(self) -> list[str]:
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=8.0)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def _choose_model(self) -> str:
        if self._usable:
            return self._usable
        available = self._available_models()
        for candidate in [self.primary, *self.fallbacks]:
            base = candidate.split(":")[0]
            match = next((m for m in available if base in m), None)
            if match:
                self._usable = match
                logger.info(f"Ollama modelo seleccionado: {match}")
                return match
        logger.warning(f"Usando modelo por defecto: {self.primary}")
        self._usable = self.primary
        return self.primary

    def complete(self, prompt: str, system: str | None = None,
                 temperature: float = 0.2, max_tokens: int = 2048) -> str:
        model = self._choose_model()
        payload: dict[str, Any] = {
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        try:
            r = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama error ({model}): {e}")
            return ""

    def complete_json(self, prompt: str, system: str | None = None) -> Any:
        guard = ("Responde ÚNICAMENTE con JSON válido, sin texto adicional.")
        sys = f"{system}\n\n{guard}" if system else guard
        raw = self.complete(prompt, system=sys, temperature=0.0)
        return _safe_json_loads(raw)

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        model = self._choose_model()
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system
        with httpx.stream("POST", f"{self.host}/api/generate",
                          json=payload, timeout=self.timeout) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("response", "")
                if token:
                    yield token
                if data.get("done"):
                    break


# ── Unified facade ────────────────────────────────────────────────────
class LLMFacade:
    """Usa Groq si hay API key, si no intenta Ollama."""

    def __init__(self) -> None:
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            self._backend: GroqLLM | OllamaLLM = GroqLLM(groq_key)
            logger.info("LLM backend: Groq API")
        else:
            self._backend = OllamaLLM()
            logger.info("LLM backend: Ollama (local)")

    def complete(self, prompt: str, system: str | None = None,
                 temperature: float = 0.2, max_tokens: int = 2048) -> str:
        return self._backend.complete(prompt, system=system,
                                      temperature=temperature, max_tokens=max_tokens)

    def complete_json(self, prompt: str, system: str | None = None) -> Any:
        return self._backend.complete_json(prompt, system=system)

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        return self._backend.stream(prompt, system=system)


# ── helpers ───────────────────────────────────────────────────────────
def _safe_json_loads(text: str) -> Any:
    if not text:
        return {}
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        return {}
    candidate = match.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return {}


llm = LLMFacade()
