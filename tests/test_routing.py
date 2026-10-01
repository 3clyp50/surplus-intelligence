import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("surplus_routing", Path(__file__).resolve().parents[1] / "helpers/routing.py")
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class RoutingTests(unittest.TestCase):
    def test_defaults_and_zero_are_distinct(self):
        self.assertEqual(routing.request_options({}, {}, {}), {"extra_body": {}, "extra_headers": {}})
        self.assertEqual(routing.request_options({"min_discount_pct": "0"}, {}, {})["extra_headers"], {"X-Min-Discount": "0"})

    def test_controls_and_precedence(self):
        config = dict(provider="api.openai.com, api.anthropic.com", providers_blocked="openrouter\nvenice",
                      provider_order="api.openai.com", objective="latency", price_tolerance_pct="15",
                      max_latency_ms="4000", min_discount_pct="30")
        model = {"extra_body": {"provider": "api.anthropic.com", "si_route": {"objective": "reliability"}},
                 "extra_headers": {"x-min-discount": "40"}}
        call = {"extra_body": {"si_route": {"price_tolerance_pct": 10}, "metadata": {"test": True}}}
        result = routing.request_options(config, model, call)
        body = result["extra_body"]
        self.assertEqual(body["provider"], ["api.anthropic.com"])
        self.assertEqual(body["providers_blocked"], ["openrouter", "venice"])
        self.assertEqual(body["si_route"], {"objective": "reliability", "price_tolerance_pct": 10, "max_latency_ms": 4000})
        self.assertEqual(result["extra_headers"], {"x-min-discount": "40"})
        self.assertEqual(model["extra_body"]["provider"], "api.anthropic.com")
        self.assertNotIn("max_latency_ms", call["extra_body"]["si_route"])

    def test_alias_replaces_default_allowlist(self):
        result = routing.request_options({"provider": "openai"}, {"extra_body": {"provider_url": "https://api.anthropic.com"}}, {})
        self.assertNotIn("provider", result["extra_body"])
        self.assertIn("provider_url", result["extra_body"])

    def test_invalid_settings_fail_closed(self):
        for config in ({"providers_blocked": {"venice": True}}, {"providers_blocked": ["x"] * 33},
                       {"provider": [None]}, {"min_discount_pct": True}, {"min_discount_pct": "101"},
                       {"min_discount_pct": "2.5"}, {"objective": "fastest"}, {"max_latency_ms": "0"},
                       {"price_tolerance_pct": "nan"}, {"api_key": "not-a-real-key"}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                routing.validate_config(config)

    def test_invalid_request_overrides_fail_closed(self):
        for options in ({"extra_body": []}, {"extra_body": {"providers_blocked": None}},
                        {"extra_body": {"provider": []}}, {"extra_body": {"si_route": None}},
                        {"extra_body": {"provider": "openai", "provider_url": "https://api.openai.com"}},
                        {"extra_headers": {"X-Min-Discount": "-1"}},
                        {"extra_headers": {"Bad": "line\nbreak"}},
                        {"api_base": "https://api.surplusintelligence.ai.evil.test/v1"},
                        {"api_base": "http://api.surplusintelligence.ai/v1"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                routing.request_options({}, {}, options)

    def test_responses_uses_local_history_without_fallback(self):
        result = routing.request_options({}, {"a0_api_mode": "responses", "responses_state": "server"}, {})
        self.assertEqual(result["responses_state"], "local")
        self.assertFalse(result["store"])
        self.assertFalse(result["a0_responses_fallback"])
        self.assertFalse(routing.request_options({}, {"a0_api_mode": "responses_api"}, {})["store"])
        routing.request_options({}, {"api_base": "https://api.surplusintelligence.ai/min30/v1"}, {})


if __name__ == "__main__":
    unittest.main()
