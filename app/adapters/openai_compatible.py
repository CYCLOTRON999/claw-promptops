"""OpenAI-compatible Model Adapter for cloud models and compatible local gateways (vLLM, Ollama-OpenAI)."""

import asyncio
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from app.adapters.base import BaseModelAdapter, GenerationRequest, GenerationResponse, ModelInfo, StreamChunk
from app.config import settings


class OpenAICompatibleAdapter(BaseModelAdapter):
    """Adapter for any model endpoint adhering to the OpenAI /chat/completions specification."""

    def __init__(self, model_name: str = "gpt-4o-mini", config: Optional[Dict[str, Any]] = None):
        super().__init__(model_name, config)
        self.base_url = (self.config.get("base_url") or settings.openai_base_url).rstrip("/")
        self.api_key = self.config.get("api_key") or settings.openai_api_key

    def supports_structured_output(self) -> bool:
        return True

    def get_model_info(self) -> ModelInfo:
        pricing = settings.get_pricing_for_model(self.model_name)
        input_price = pricing["input_price_per_1k"] if pricing else None
        output_price = pricing["output_price_per_1k"] if pricing else None

        return ModelInfo(
            name=self.model_name,
            provider="openai_compatible",
            supports_structured=True,
            supports_streaming=True,
            context_window=128000,
            input_price_per_1k=input_price,
            output_price_per_1k=output_price,
            is_mock=False,
            description=f"OpenAI-compatible completion endpoint for {self.model_name}"
        )

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        endpoint = f"{self.base_url}/chat/completions"
        timeout_seconds = request.timeout or 30.0

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": request.prompt}
            ],
            "temperature": request.temperature,
            "stream": False
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                response = await client.post(endpoint, json=payload, headers=self._build_headers())
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                raise asyncio.TimeoutError(f"OpenAI request timed out after {timeout_seconds}s: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"OpenAI HTTP error {exc.response.status_code}: {exc.response.text}") from exc
            except httpx.RequestError as exc:
                raise RuntimeError(f"OpenAI connection error: {exc}") from exc

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        raw_text = message.get("content", "")
        finish_reason = choice.get("finish_reason", "stop")

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", len(request.prompt) // 4)
        output_tokens = usage.get("completion_tokens", len(raw_text) // 4)

        # Cost calculation
        pricing = settings.get_pricing_for_model(self.model_name)
        estimated_cost = None
        if pricing:
            in_cost = (input_tokens / 1000.0) * pricing.get("input_price_per_1k", 0.0)
            out_cost = (output_tokens / 1000.0) * pricing.get("output_price_per_1k", 0.0)
            estimated_cost = round(in_cost + out_cost, 6)

        return GenerationResponse(
            text=raw_text,
            structured_output=None,
            model=self.model_name,
            provider="openai_compatible",
            finish_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            cached=False,
            status="SUCCESS",
            raw_response=response.text
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamChunk]:
        endpoint = f"{self.base_url}/chat/completions"
        timeout_seconds = request.timeout or 30.0

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "stream": True
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                async with client.stream("POST", endpoint, json=payload, headers=self._build_headers()) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        chunk_json = json.loads(data_str)
                        choices = chunk_json.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content_piece = delta.get("content", "")
                        finish_reason = choices[0].get("finish_reason")
                        if content_piece or finish_reason:
                            yield StreamChunk(
                                text=content_piece,
                                finish_reason=finish_reason
                            )
            except httpx.TimeoutException as exc:
                raise asyncio.TimeoutError(f"OpenAI streaming timed out: {exc}") from exc
            except Exception as exc:
                raise RuntimeError(f"OpenAI streaming error: {exc}") from exc
