"""Run from the A0 root using its framework Python. No network or real API key."""
import asyncio
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import httpx
from openai import AsyncOpenAI
import models
from helpers import plugins
from helpers.providers import get_provider_config, reload_providers
from usr.plugins.surplus_intelligence.helpers.routing import BASE_URL, prepare_call


class FrameworkTests(unittest.TestCase):
    def test_unrelated_provider_is_untouched(self):
        data = {"args": (SimpleNamespace(a0_model_conf=SimpleNamespace(provider="openai"), kwargs={}),), "kwargs": {}}
        with patch.object(plugins, "get_plugin_config", side_effect=AssertionError("Unrelated config read")):
            prepare_call(data)
        self.assertEqual(data["kwargs"], {})

    def test_missing_surplus_key_cannot_borrow_openai_key(self):
        with patch.object(models, "get_api_key_raw", side_effect=lambda provider: "other-provider-key" if provider == "openai" else "None"):
            mc = models.ModelConfig(type=models.ModelType.CHAT, provider="surplus", name="gpt-4.1-mini")
            model = models.get_chat_model("surplus", mc.name, model_config=mc)
            with self.assertRaisesRegex(ValueError, "Surplus API key"):
                prepare_call({"args": (model,), "kwargs": {}})

    def test_provider_registration(self):
        reload_providers()
        provider = get_provider_config("chat", "surplus")
        self.assertEqual(provider["litellm_provider"], "openai")
        self.assertEqual(provider["kwargs"]["api_base"], BASE_URL)
        self.assertIsNone(get_provider_config("embedding", "surplus"))

    def test_wire(self):
        for mode in ("chat", "responses"):
            for method in ("unified_call", "unified_turn"):
                for stream in (False, True):
                    with self.subTest(mode=mode, method=method, stream=stream):
                        asyncio.run(self.check_wire(mode, method, stream))

    async def check_wire(self, mode, method, stream):
        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            self.assertEqual(request.url.host, "api.surplusintelligence.ai")
            self.assertEqual(request.url.path, "/v1/responses" if mode == "responses" else "/v1/chat/completions")
            self.assertEqual(body["provider"], ["api.openai.com"])
            self.assertEqual(body["providers_blocked"], ["venice"])
            self.assertEqual(body["si_route"]["objective"], "latency")
            self.assertEqual(request.headers["X-Min-Discount"], "30")
            if mode == "chat":
                reply = {"id": "test", "object": "chat.completion", "created": 1, "model": "gpt-4.1-mini",
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]}
                events = [{"id": "test", "object": "chat.completion.chunk", "created": 1, "model": "gpt-4.1-mini",
                           "choices": [{"index": 0, "delta": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]}]
            else:
                self.assertFalse(body["store"])
                self.assertNotIn("previous_response_id", body)
                reply = {"id": "resp_test", "object": "response", "created_at": 1, "status": "completed", "model": "gpt-4.1-mini",
                         "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
                                     "content": [{"type": "output_text", "text": "OK", "annotations": []}]}]}
                events = [{"type": "response.created", "response": {**reply, "status": "in_progress", "output": []}, "sequence_number": 0},
                          {"type": "response.output_text.delta", "item_id": "msg_test", "output_index": 0, "content_index": 0, "delta": "OK", "sequence_number": 1},
                          {"type": "response.completed", "response": reply, "sequence_number": 2}]
            if body.get("stream"):
                content = "".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n"
                return httpx.Response(200, text=content, headers={"Content-Type": "text/event-stream"}, request=request)
            return httpx.Response(200, json=reply, request=request)

        async def send(_client, request, **kwargs):
            return respond(request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(api_key="test-only", base_url=BASE_URL, http_client=http, max_retries=0)
            config = {"provider": "api.openai.com", "providers_blocked": "venice", "objective": "latency", "min_discount_pct": "30"}
            original = plugins.get_plugin_config

            def plugin_config(name, *args, **kwargs):
                return config if name == "surplus_intelligence" else original(name, *args, **kwargs)

            async def chunk(*args):
                pass

            mc = models.ModelConfig(type=models.ModelType.CHAT, provider="surplus", name="gpt-4.1-mini")
            model = models.get_chat_model("surplus", mc.name, model_config=mc, api_key="test-only", client=client, a0_api_mode=mode, a0_retry_attempts=0)
            # Responses uses LiteLLM's own HTTP client, not the SDK client above.
            # Intercept the shared HTTP boundary so no test can reach the network.
            with patch.object(plugins, "get_plugin_config", side_effect=plugin_config), patch.object(httpx.AsyncClient, "send", send):
                result = await getattr(model, method)(user_message="Return OK.", response_callback=chunk if stream else None)
            self.assertEqual(len(requests), 1)
            self.assertIn("OK", str(result))


if __name__ == "__main__":
    unittest.main()
