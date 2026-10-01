# Surplus Intelligence for Agent Zero

Adds **Surplus Intelligence** to Agent Zero's Main, Utility, and Vision model selectors, with a live model catalog, native API-key storage, and Surplus routing controls. No core patches, proxy server, or extra dependencies.

## Install

In Agent Zero, open **Plugins → Install from Git** and enter `https://github.com/3clyp50/surplus-intelligence`, or upload a ZIP containing these files at its root. The runtime plugin ID is `surplus_intelligence`; the repository name is `surplus-intelligence`.

Requires Agent Zero's current plugin system, plugin-defined model providers, and the `models.LiteLLMChatWrapper.unified_call` / `unified_turn` extension points. Older builds without those hooks are not supported.

## Connect

1. Open **Model Configuration** and select **Surplus Intelligence** for the model slot you want to use.
2. Enter your Surplus inference API key in the native provider key field. This uses Agent Zero's shared key store, not this plugin's config or source files. `API_KEY_SURPLUS` and `SURPLUS_API_KEY` are also recognized by Agent Zero's existing environment loader.
3. Choose a model from the catalog or enter its exact ID. Set its context window, vision capability, output limit, and reasoning parameters according to that model's capabilities.
4. Save the model preset. Installing this plugin does **not** change existing models, presets, API keys, or embedding configuration.
5. Open this plugin's **Config** to set optional global routing defaults.

Catalog discovery is not an authentication test or a guarantee that sellers are currently available. Only text/chat models belong in these slots; a model appearing in a catalog does not prove compatibility with Agent Zero's agent/tool protocol.

## Routing

| Setting | Surplus field | Meaning |
| --- | --- | --- |
| Allowed providers | `provider` | Only these providers may serve the request. |
| Blocked providers | `providers_blocked` | Exclude providers; blocks win over allows. |
| Preferred order | `provider_order` | Try listed providers first; other eligible providers remain available. |
| Priority | `si_route.objective` | Price, latency, reliability, or price without cache affinity. |
| Price tolerance | `si_route.price_tolerance_pct` | Ranking band above the cheapest eligible offer; **not a cost cap**. |
| Observed latency limit | `si_route.max_latency_ms` | Filter by observed p50; unknown-latency offers remain eligible. Not a request deadline. |
| Minimum discount | `X-Min-Discount` | Estimated marketplace discount against external list price, 0–100. |

Provider lists accept names, hosts, or URLs, separated by commas or newlines (up to 32 entries). The plugin does not widen the route or retry with weaker restrictions when sellers are unavailable. Agent Zero and Surplus can perform their own normal retries; their charges and limits still apply.

Blank settings omit the corresponding field. A blank discount adds no floor; `0` still excludes offers above reference price. Surplus uses the strictest API-key, URL, or request discount floor. Buyer-owned priority/fallback providers are outside that discount guarantee. Actual realized discounts can differ from estimates.

Defaults apply globally, including utility and vision calls through Agent Zero's unified model interfaces. They are **defaults, not administrator-enforced policy**: per-model options override them, and per-call options override both. `si_route` merges by field. Use API-key restrictions for controls that callers must not override. Surplus's key-scoped blocklist and per-request blocklist have different coverage; see its documentation.

### Per-model overrides

In a model's **Additional Parameters**, use JSON-valued entries:

```text
extra_body={"provider":"api.openai.com","providers_blocked":["openrouter"],"si_route":{"objective":"reliability"}}
extra_headers={"X-Min-Discount":"30"}
max_tokens=2048
```

`provider_url` and `provider_base_url` aliases are supported through `extra_body`; use only one allow-list spelling per request. An explicit empty allow-list is rejected. A per-model pin replaces the global allow-list, not the global blocklist. An explicit `providers_blocked: []` clears the plugin's default blocklist for that model, but does not override key-scoped restrictions.

Standard generation settings belong in Model Configuration, not a second plugin-level copy. The plugin does not force reasoning effort, temperature, retries, or output limits across dissimilar models. It preserves unrelated model/request parameters and never logs prompts or credentials.

### Responses (opt-in)

Chat Completions is the default. To use Responses, add:

```text
a0_api_mode=responses
reasoning={"effort":"high"}
max_output_tokens=2048
```

Choose an effort supported by your model and route; `max` is not universally supported. Agent Zero owns history, tool projection, and transport handling. This plugin requests **local Responses history**, `store: false`, and no automatic Responses-to-Chat fallback. Surplus may itself bridge sellers to a different wire. Hosted tools and server-side `previous_response_id` persistence are not promised.

`X-SI-Adapted-Params` means Surplus changed or could not carry a parameter. Neither an effort echo nor an absent adaptation header proves upstream preservation. This plugin does not add a telemetry or spending dashboard; use Surplus's request logs for settled cost and routing evidence.

## Privacy, costs, and removal

Using this provider sends selected chat context, tool results, and any supplied media to Surplus and the selected upstream provider. Use only data you are authorized to share. Configure key-level spending limits in Surplus; routing preferences are not spending limits. Surplus credits and service terms are separate from this plugin's license.

The API base must remain on `https://api.surplusintelligence.ai/v1`, optionally with a `/minN` prefix. Provider host pins choose an upstream **through Surplus**; they do not change the client API endpoint.

Disable or uninstall from Plugins. Provider registration and routing extensions disappear with the plugin. No dependencies, services, or external files are installed, so no lifecycle setup/cleanup is required. Plugin routing config is removed with its directory. Existing model presets and the shared API key are deliberately preserved: switch affected presets to another provider, and remove or revoke the Surplus key separately if desired. Already-running requests are not cancelled by uninstall.

Not included: embeddings, media-generation tools, wallet/key administration, raw LangChain `invoke`/`stream` integration outside A0's unified model interfaces, or undocumented cache-routing options.

## Verification

Dependency-free routing checks from the repository root:

```bash
python3 -m unittest discover -s tests -p test_routing.py -v
```

With the plugin installed, run from Agent Zero's root using its **framework Python**:

```bash
python -m unittest discover -s usr/plugins/surplus_intelligence/tests -v
```

The framework tests intercept HTTP with synthetic credentials. They exercise actual LiteLLM serialization for Chat and Responses, streaming and non-streaming, through both unified call paths. They do not spend credits or prove current seller availability.

Verified on 2026-10-01 against Agent Zero `60c940fd03fdaf60993b70070e6ca7142718200b`:

- 10 tests passed, including eight transport combinations and the missing-key guard.
- Native provider registration, live catalog discovery, settings save/reopen, disable/re-enable, and ZIP removal/reinstall passed on the running instance.
- One small real Chat request using `gpt-5.6-luna`, pinned to `api.openai.com`, returned the expected text. An earlier request for an unlisted older model returned 404; catalog presence and seller availability must always be checked separately.
- Responses is verified with mocked HTTP, not a paid upstream call. A complete autonomous agent/tool loop and every catalog model have not been tested.

## References

Surplus contracts checked on 2026-10-01:

- [Routing controls](https://www.surplusintelligence.ai/docs/marketplace/routing-controls)
- [Minimum-discount routing](https://www.surplusintelligence.ai/docs/marketplace/minimum-discount-routing)
- [Chat Completions](https://www.surplusintelligence.ai/docs/api-reference/chat-completions)
- [Reasoning controls](https://www.surplusintelligence.ai/docs/reference/reasoning)

Independent community integration; not an official Surplus or Agent Zero product. Code is MIT-licensed. The supplied thumbnail is separate brand artwork and is not covered by the code license.
