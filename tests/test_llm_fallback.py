"""Groq: si el modelo configurado ya no existe (404), se elige uno disponible."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402

from app.services.llm_service import GroqLLM  # noqa: E402


class _Resp:
    def __init__(self, status: int, body: dict | None = None, text: str = ""):
        self.status_code = status
        self._body = body or {}
        self.text = text or str(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "https://x"),
                response=httpx.Response(self.status_code))


def test_switches_to_an_available_model_on_404(monkeypatch):
    used: list[str] = []

    def fake_post(url, json, headers, timeout):
        used.append(json["model"])
        if json["model"] == "modelo-retirado":
            return _Resp(404, text='{"error":{"code":"model_not_found"}}')
        return _Resp(200, {"choices": [{"message": {"content": " hola "}}]})

    def fake_get(url, headers, timeout):
        return _Resp(200, {"data": [
            {"id": "whisper-large-v3", "active": True},
            {"id": "llama-3.1-8b-instant", "active": True},
            {"id": "openai/gpt-oss-20b", "active": True},
        ]})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    llm = GroqLLM("clave")
    llm.model = "modelo-retirado"
    assert llm.complete("hola") == "hola"
    assert used == ["modelo-retirado", "llama-3.1-8b-instant"]   # preferido disponible, no whisper
    assert llm.model == "llama-3.1-8b-instant"                    # se recuerda para las siguientes

    used.clear()
    assert llm.complete("otra") == "hola"
    assert used == ["llama-3.1-8b-instant"]                       # ya no vuelve a probar el roto


def test_pick_skips_non_chat_models(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, headers, timeout: _Resp(200, {"data": [
        {"id": "whisper-large-v3-turbo", "active": True},
        {"id": "meta-llama/llama-guard-4-12b", "active": True},
        {"id": "algun-chat-nuevo", "active": True},
    ]}))
    assert GroqLLM("clave")._pick_available_model() == "algun-chat-nuevo"


def test_healthy_model_is_used_as_is(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: (
        calls.append(json["model"]) or _Resp(200, {"choices": [{"message": {"content": "ok"}}]})))
    llm = GroqLLM("clave")
    assert llm.complete("x") == "ok" and calls == [llm.MODEL]
