"""Surplus request defaults, shared by A0's main and utility call paths."""

from copy import deepcopy
import math
import re

BASE_URL = "https://api.surplusintelligence.ai/v1"
OBJECTIVES = {"price", "latency", "reliability", "price_without_cache"}
ROUTING_LISTS = ("provider", "providers_blocked", "provider_order")
ALLOW_ALIASES = ("provider", "provider_url", "provider_base_url")
CONFIG_KEYS = {*ROUTING_LISTS, "objective", "price_tolerance_pct", "max_latency_ms", "min_discount_pct"}


def provider_list(value, field):
    if isinstance(value, str):
        value = [item.strip() for item in re.split(r"[,\n]", value) if item.strip()]
    if not isinstance(value, list) or len(value) > 32 or any(
        not isinstance(item, str) or not item.strip() or len(item) > 256
        or any(ord(char) < 32 for char in item) for item in value
    ):
        raise ValueError(f"{field}: use at most 32 provider names or hosts, separated by commas or lines.")
    return list(dict.fromkeys(item.strip() for item in value))


def number(value, field, *, integer=False, maximum=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field}: enter a non-negative number.") from None
    if isinstance(value, bool) or not math.isfinite(result) or result < 0 or (
        integer and not result.is_integer()
    ) or (maximum is not None and result > maximum):
        raise ValueError(f"{field}: invalid number or out of range.")
    return int(result) if integer else result


def config_defaults(config):
    if not isinstance(config, dict) or set(config) - CONFIG_KEYS:
        raise ValueError("Surplus settings contain unknown fields; credentials belong in Model Configuration.")
    body, route, headers = {}, {}, {}
    for field in ROUTING_LISTS:
        items = provider_list(config.get(field, ""), field)
        if items:
            body[field] = items
    objective = config.get("objective", "")
    if objective not in (None, ""):
        if not isinstance(objective, str) or objective not in OBJECTIVES:
            raise ValueError("objective: choose a listed routing priority.")
        route["objective"] = objective
    for field in ("price_tolerance_pct", "max_latency_ms"):
        value = config.get(field, "")
        if value not in (None, ""):
            route[field] = number(value, field, integer=field == "max_latency_ms")
            if field == "max_latency_ms" and route[field] == 0:
                raise ValueError("max_latency_ms: enter a positive number or leave blank.")
    discount = config.get("min_discount_pct", "")
    if discount not in (None, ""):
        headers["X-Min-Discount"] = str(number(discount, "min_discount_pct", integer=True, maximum=100))
    if route:
        body["si_route"] = route
    return body, headers


def validate_config(config):
    config_defaults(config)


def request_options(config, model_options, call_options):
    """Merge defaults < model options < call options without mutating shared state."""
    body, headers = config_defaults(config)
    effective = {**model_options, **call_options}
    for base in (effective.get("api_base", BASE_URL), effective.get("base_url", BASE_URL)):
        if not isinstance(base, str) or not re.fullmatch(
            r"https://api\.surplusintelligence\.ai/(?:min(?:100|[1-9]?\d)/)?v1/?", base
        ):
            raise ValueError("Surplus API base must use https://api.surplusintelligence.ai/v1 (optional /minN prefix).")

    for options in (model_options, call_options):
        extra = options.get("extra_body", {})
        if not isinstance(extra, dict):
            raise ValueError("Surplus extra_body must be a JSON object.")
        extra = deepcopy(extra)
        # A per-model host pin replaces the global allow-list, regardless of spelling.
        if any(key in extra for key in ALLOW_ALIASES):
            for key in ALLOW_ALIASES:
                body.pop(key, None)
        if "si_route" in extra:
            route = extra.pop("si_route")
            if not isinstance(route, dict):
                raise ValueError("si_route must be a JSON object.")
            body["si_route"] = {**body.get("si_route", {}), **route}
        body.update(extra)
        incoming_headers = options.get("extra_headers", {})
        if not isinstance(incoming_headers, dict):
            raise ValueError("Surplus extra_headers must be a JSON object.")
        for key, value in incoming_headers.items():
            if not isinstance(key, str) or not isinstance(value, str) or any(
                c in key + value for c in "\r\n"
            ):
                raise ValueError("Surplus extra_headers must contain single-line strings.")
            for old in list(headers):
                if old.lower() == key.lower():
                    del headers[old]
            headers[key] = value

    if sum(key in body for key in ALLOW_ALIASES) > 1:
        raise ValueError("Use only one of provider, provider_url, or provider_base_url.")
    for field in ROUTING_LISTS:
        if field in body:
            body[field] = provider_list(body[field], field)
            if field == "provider" and not body[field]:
                raise ValueError("An explicit provider allow-list must not be empty.")
    for alias in ALLOW_ALIASES[1:]:
        if alias in body and (not isinstance(body[alias], str) or not body[alias].strip()):
            raise ValueError(f"{alias} must be a non-empty string.")
    route = body.get("si_route", {})
    if "objective" in route and (not isinstance(route["objective"], str) or route["objective"] not in OBJECTIVES):
        raise ValueError("si_route.objective: invalid routing priority.")
    for field in ("price_tolerance_pct", "max_latency_ms"):
        if field in route:
            route[field] = number(route[field], field, integer=field == "max_latency_ms")
            if field == "max_latency_ms" and route[field] == 0:
                raise ValueError("max_latency_ms must be positive.")
    for key, value in headers.items():
        if key.lower() == "x-min-discount":
            headers[key] = str(number(value, "X-Min-Discount", integer=True, maximum=100))
    result = {"extra_body": body, "extra_headers": headers}
    # Surplus does not promise server-side previous_response_id persistence.
    if str(effective.get("a0_api_mode", "")).strip().lower() in {"response", "responses", "responses_api"}:
        result.update(responses_state="local", store=False, a0_responses_fallback=False)
    return result


def prepare_call(data):
    from helpers.plugins import get_plugin_config
    from models import get_api_key_raw

    args = data.get("args", ())
    call_options = data.get("kwargs", {})
    model = args[0] if args else call_options.get("self")
    options = getattr(model, "kwargs", {})
    provider = getattr(getattr(model, "a0_model_conf", None), "provider", None)
    if isinstance(provider, str):
        provider = provider.lower()
    if provider != "surplus" and not (
        provider is None and options.get("api_base") == BASE_URL
    ):
        return
    key = call_options.get("api_key", options.get("api_key"))
    surplus_keys = {k.strip() for k in get_api_key_raw("surplus").split(",")}
    openai_keys = {k.strip() for k in get_api_key_raw("openai").split(",")}
    explicit_key = call_options.get("api_key") or getattr(getattr(model, "a0_model_conf", None), "api_key", None)
    # Core's OpenAI-compatible fallback must not send another provider's key here.
    if not key or key in {"None", "NA"} or (key in openai_keys and key not in surplus_keys and not explicit_key):
        raise ValueError("Configure the Surplus API key in Model Configuration before using this provider.")
    config = get_plugin_config("surplus_intelligence")
    data["kwargs"] = {
        **call_options,
        **request_options({} if config is None else config, options, call_options),
    }
