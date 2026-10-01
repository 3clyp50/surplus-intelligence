# Surplus Intelligence plugin

## Purpose and ownership

This standalone community repository contains the Agent Zero plugin `surplus_intelligence`. Runtime files live at the repository root; install under `usr/plugins/surplus_intelligence`, never under bundled `plugins/`.

## Contracts

- Keep provider registration in `conf/model_providers.yaml`, settings defaults in `default_config.yaml`, validation in `hooks.py`, and routing in `helpers/routing.py`.
- Reuse Agent Zero's model configuration, API-key store, transport, history, and settings UI. No core patches, proxy, background service, or new dependencies.
- Both unified model call paths must apply routing. Do not mutate shared wrapper kwargs or another provider's requests.
- Invalid blocks must fail closed. Distinguish absent discount from zero; describe routing controls as defaults, not spending or security enforcement.
- Never persist keys in this repository or plugin config. Never send an unrelated provider's fallback key to Surplus.
- Keep custom imports under `usr.plugins.surplus_intelligence`. Do not use symlink imports or `sys.path` modifications.
- New lifecycle setup or cleanup, if ever required, belongs in root `hooks.py`, not `execute.py`.
- `webui/thumbnail.webp` is supplied artwork: retain 256×256 dimensions and less than 20,000 bytes. Do not include it under the code's MIT copyright grant.
- No commits, push, GitHub publication, or Plugin Index submission without user authorization. Stage only source, never runtime state or credentials.

## Verification

Run the dependency-free tests with `python3 -m unittest discover -s tests -p test_routing.py -v`.
Run the complete suite from an Agent Zero checkout using its framework Python: `python -m unittest discover -s usr/plugins/surplus_intelligence/tests -v`.
The framework test intercepts HTTP below LiteLLM; preserve that boundary so tests never spend credits.
For settings changes, verify the actual installation, save/reopen, desktop and narrow layouts, and restore only test-created settings. Distinguish mocked transport verification from real paid inference.

## Child DOX Index

No child documents; this file owns the complete plugin. Update README alongside behavior changes.
