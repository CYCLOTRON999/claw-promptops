"""Ollama Model Adapter for local model execution via Ollama HTTP API."""

import asyncio
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from app.adapters.base import BaseModelAdapter, GenerationRequest, GenerationResponse, ModelInfo, StreamChunk


class OllamaAdapter(BaseModelAdapter):
    """Adapter for running local models via Ollama's native HTTP REST API."""

    def __init__(self, model_name: str = "llama3", config: Optional[Dict[str, Any]] = None):
        super().__init__(model_name, config)
        self.base_url = (self.config.get("base_url") or "http://localhost:11434").rstrip("/")

    def supports_structured_output(self) -> bool:
        return True

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            name=self.model_name,
            provider="ollama",
            supports_structured=True,
            supports_streaming=True,
            context_window=8192,
            input_price_per_1k=0.0,
            output_price_per_1k=0.0,
            is_mock=False,
            description=f"Local Ollama model backend for {self.model_name}"
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        endpoint = f"{self.base_url}/api/generate"
        timeout_seconds = request.timeout or 30.0

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
            }
        }
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        if request.response_format == "json":
            payload["format"] = "json"

        start_time = time.perf_counter()

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                raise asyncio.TimeoutError(f"Ollama request timed out after {timeout_seconds}s: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"Ollama HTTP error {exc.response.status_code}: {exc.response.text}") from exc
            except httpx.RequestError as exc:
                raise RuntimeError(f"Ollama connection failure: {exc}") from exc

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        raw_text = data.get("response", "")
        input_tokens = data.get("prompt_eval_count", len(request.prompt) // 4)
        output_tokens = data.get("eval_count", len(raw_text) // 4)

        return GenerationResponse(
            text=raw_text,
            structured_output=None,
            model=self.model_name,
            provider="ollama",
            finish_reason="stop" if data.get("done") else "unknown",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=0.0,
            cached=False,
            status="SUCCESS",
            raw_response=response.text
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        endpoint = f"{self.base_url}/api/generate"
        timeout_seconds = request.timeout or 30.0

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": request.prompt,
            "stream": True,
            "options": {
                "temperature": request.temperature,
            }
        }
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens
        if request.response_format == "json":
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                async with client.stream("POST", endpoint, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk_data = json.loads(line)
                        yield StreamChunk(
                            text=chunk_data.get("response", ""),
                            finish_reason="stop" if chunk_data.get("done") else None,
                            input_tokens=chunk_data.get("prompt_eval_count"),
                            output_tokens=chunk_data.get("eval_count")
                        )
            except httpx.TimeoutException as exc:
                raise asyncio.TimeoutError(f"Ollama streaming timed out: {exc}") from exc
            except Exception as exc:
                raise RuntimeError(f"Ollama streaming error: {exc}") from exc
