"""Cliente Ollama local con fallback automatico entre modelos.

Expone tres metodos de alto nivel:

- complete(prompt, system=...) -> str
- complete_json(prompt, schema_hint=...) -> dict/list
- stream(prompt) -> iterador de tokens

El servicio intenta primero el modelo configurado (p.ej. llama3:8b) y
si no esta instalado prueba mistral:7b y qwen2.5:7b-instruct. Asi evitamos
que el pipeline se rompa porque el usuario no haya descargado un modelo
concreto todavia.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator

import httpx
from loguru import logger

from app.core.config import settings


class OllamaLLM:
    def __init__(self) -> None:
        self.host = settings.ollama_host.rstrip("/")
        self.primary = settings.ollama_model
        self.fallbacks = settings.ollama_fallback_models
        self.timeout = settings.ollama_timeout
        self._usable_model: str | None = None

    # --- internal ---
    def _available_models(self) -> list[str]:
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=10.0)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"No se pudo listar modelos de Ollama: {e}")
            return []

    def _choose_model(self) -> str:
        if self._usable_model:
            return self._usable_model
        available = self._available_models()
        for candidate in [self.primary, *self.fallbacks]:
            if any(candidate.split(":")[0] in m for m in available):
                self._usable_model = next(m for m in available if candidate.split(":")[0] in m)
                logger.info(f"Modelo Ollama seleccionado: {self._usable_model}")
                return self._usable_model
        # ultimo recurso: devolvemos el primario y dejamos que Ollama avise
        logger.warning(f"Ningun modelo instalado coincide con la configuracion; usando {self.primary}")
        self._usable_model = self.primary
        return self.primary

    # --- public API ---
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        model = self._choose_model()
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        try:
            r = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Fallo LLM ({model}): {e}")
            return ""

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        model = self._choose_model()
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system
        with httpx.stream("POST", f"{self.host}/api/generate", json=payload, timeout=self.timeout) as r:
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

    def complete_json(self, prompt: str, system: str | None = None) -> Any:
        """Fuerza al modelo a devolver JSON valido y lo parsea."""
        guard = (
            "Responde UNICAMENTE con JSON valido, sin texto adicional, sin markdown, "
            "sin comentarios. Si no tienes datos, responde con [] o {}."
        )
        sys = f"{system}\n\n{guard}" if system else guard
        raw = self.complete(prompt, system=sys, temperature=0.0)
        return _safe_json_loads(raw)


def _safe_json_loads(text: str) -> Any:
    """Extrae el primer bloque JSON del texto y lo parsea con tolerancia."""
    if not text:
        return {}
    # Quitar fences markdown ```json ... ```
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    # Buscar el primer objeto/array
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        return {}
    candidate = match.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # intento de reparacion basico: coma colgante
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return {}


llm = OllamaLLM()
