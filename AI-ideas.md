# AI Ideas and Archived Implementation Notes

> Historical record only. Local-LLM/AI functionality has been removed from the application; this document does not describe supported runtime features.

## Current status

The local-LLM implementation, UI actions, and workers are absent from the application. Legacy `llm` and `ai_enabled` values may remain in `profiles.json`; no current code reads or acts on them.

## Prompt history

- **[2026-09-01]** "thinking about this code, what options could be taken to use pingone MCP and other ai abilities to make it better"
- **[2026-09-01]** "build all of this"
- **[2026-09-01]** "use pingone helix make sure all AI is optional and that existing core functionality works"
- **[2026-09-01]** "update based on the following. Identify and document gaps for further research" [Helix MCP integration guide provided]
- **[2026-09-01]** "what am I still missing"
- **[2026-09-02]** "create a checklist I can print and work against"
- **[2026-09-02]** "checklist of dependencies I need to supply"
- **[2026-09-02]** "update to remove helix references instead include the option to work with a local LLM. Provide configuration options to connect with the LLM and interface (e.g., LM Studio) of the users choice. All AI functionality must be optional in nature. Ask for requirements as needed"
- **[2026-09-02]** "steps to clean up requirements, verify compliation, and update historical log entry for helix removal"
- **[2026-09-02]** "remove, rebuild requirements.txt if needed"
- **[2026-09-02]** "update historical log"
- **[2026-09-02]** "what remains to be tested or worked on"
- **[2026-09-02]** "do these"

## Development history

## 2026-09-03b - Enforced AI Is Always Optional And Local-Only

### Summary

- Audited the optional local LLM integration to guarantee two invariants in code, not just docs: (1) AI is never active unless explicitly enabled per profile, and (2) it can never talk to anything but a local/private address.
- Off-by-default was already true (`self.ai_enabled = False`, gated by `_build_llm_client()`); added active enforcement for local-only, since the base URL was previously a free-text field a user could point at any public/cloud endpoint by mistake.

### Changes

- `api/llm_client.py` — new `is_local_base_url()` resolves the configured host and requires every address to be loopback, RFC1918 private, or link-local (accepts `localhost`, `127.0.0.1`, `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`, IPv6 `::1`/`fc00::/7`). New `LLMNotLocalError`. `LLMClient.__init__()` now calls this check unconditionally, so every code path that builds a client (main window, both dialogs) is covered by a single choke point.
- `ui/dialogs.py` — `LLMConnectionDialog.accept()` overridden to block saving a non-local base URL; `_test_connection()`/`_fetch_models()` already surface exceptions generically, so they now report the same rejection instead of a raw connection error.
- `ui/main_window.py` — `toggle_ai_enabled()` re-checks `is_local_base_url()` before allowing "Enable AI Features" to turn on (checkbox reverted otherwise); `_build_llm_client()` catches `LLMNotLocalError` alongside `LLMNotConfiguredError`.
- `README.md` — documented the enforced restriction and clarified the existing Ollama `-cloud` caveat (a local base URL can still proxy to a hosted model; that can't be detected from the URL alone).

### Known limitation (documented, not solved)

- Ollama tags ending in `-cloud` (and similar proxy setups) are reachable at a local base URL but forward the request to a hosted model. This can't be distinguished by URL/DNS inspection alone, so it remains a documented caveat rather than a blocked case.

### Verification performed

- `python -m py_compile` clean across `workers.py`, `ui/main_window.py`, `ui/dialogs.py`, `api/client.py`, `api/llm_client.py`, `app.py`.
- Manual check of `is_local_base_url()` against `localhost`, `127.0.0.1`, `192.168.1.50`, `10.0.0.5`, `::1` (all `True`) and `api.openai.com`, `example.com`, empty string (all `False`).

## 2026-09-03 - Defaulted Local LLM Integration To LM Studio + ministral-3-8b-instruct-2512

### Summary

- Set LM Studio (`openai_compatible` provider) with model `ministral-3-8b-instruct-2512` as the out-of-the-box preset for the optional local LLM integration, so a new profile's "Configure Local LLM..." dialog opens with sane defaults instead of blank fields.
- AI remains fully optional and off by default; this only changes what's prefilled when the user opens the config dialog.

### Changes

- `api/llm_client.py` — added `DEFAULT_MODEL = "ministral-3-8b-instruct-2512"`; `LLMConfig.model` and `LLMConfig.from_dict()` now default to it instead of `""`; updated the `openai_compatible` provider hint to mention loading this model in LM Studio.
- `ui/dialogs.py` — `LLMConnectionDialog` now prefills the model combo with `DEFAULT_MODEL` (mirroring the existing base-URL prefill behavior) when no model is already configured.
- `INSTALL.md` — documented that LM Studio + `ministral-3-8b-instruct-2512` is the default preset, with the steps to install LM Studio, download the model, and start its local server.

### No new Python dependencies

- Still uses only `httpx` over HTTP to LM Studio's OpenAI-compatible endpoint; no package changes to `requirements.txt`.

### Missing/external requirements (not Python packages, cannot be installed via pip)

- **LM Studio desktop app** must be installed separately (https://lmstudio.ai/) — not a PyPI dependency.
- **`ministral-3-8b-instruct-2512` model file** must be downloaded inside LM Studio before use; the app has no way to fetch or verify model weights.
- **LM Studio local server** must be started manually (Developer tab -> Start Server) and the model loaded/active; the app only calls the HTTP endpoint and cannot start LM Studio itself.
- If LM Studio's default port (`1234`) is already in use, the base URL in "Configure Local LLM..." must be updated to match.

### Verification performed

- `python -m py_compile` clean across `workers.py`, `ui/main_window.py`, `ui/dialogs.py`, `api/client.py`, `api/llm_client.py`, `app.py`.

## 2026-09-02 - Replaced Helix/MCP Integration With Optional Local LLM Support

### Summary

- Removed the prior PingOne Helix MCP integration entirely (`api/helix_client.py`, `HELIX_SETUP_CHECKLIST.md`, `HelixListToolsWorker`, `HelixCallToolWorker`, `HelixConnectionDialog`, `HelixAssistantDialog`, the `mcp` dependency, and all Helix wiring in `ui/main_window.py`).
- Replaced it with an optional, off-by-default **local LLM** integration using a pluggable provider model.

### New/changed files

- `api/llm_client.py` — `ProviderSpec`/`PROVIDERS` registry (`openai_compatible` for LM Studio/vLLM/LocalAI/llama.cpp/Jan, and `ollama` native), `LLMConfig`, `LLMClient` (`chat`, `chat_json`, `list_models`), keyring-backed optional API key (service `pingone_usermanager_llm`), redaction helpers, and a tolerant JSON extractor for model responses.
- `workers.py` — `LLMChatWorker`, `LLMModelListWorker` (same `QRunnable`/`WorkerSignals` pattern as existing workers).
- `ui/dialogs.py` — `LLMConnectionDialog` (provider dropdown, base URL, model fetch, temperature/max tokens/timeout, redaction toggle, Test Connection), `AIAssistantDialog` (chat panel), `AIReviewDialog` (read-only findings), `AIBulkActionDialog` (NL -> JSON plan -> local match -> preview -> confirm). `AttributeMappingDialog` gained an optional "Suggest Mappings (AI)" button.
- `ui/main_window.py` — "AI (Optional)" menu (Enable AI Features, Configure Local LLM, AI Assistant, Natural-Language Bulk Action), per-profile persistence (`cfg[profile]['llm']` + `cfg[profile]['ai_enabled']`), "Explain (AI)" button in the log viewer, optional AI data-quality review before bulk import, plus new `_delete_users_by_ids()` and `_run_bulk_update()` helpers reused by the NL bulk action flow.
- `requirements.txt` — removed `mcp`; no new dependency added (the LLM client uses `httpx`, already required).

### Design decisions

- **No new dependency**: all providers are reached over plain HTTP via `httpx`, so enabling AI never requires installing anything extra.
- **Optionality**: every AI entry point calls `_build_llm_client()`, which returns `None` when AI is disabled or unconfigured. `_build_llm_client(silent=True)` is used where an AI affordance should simply not appear (mapping-suggestion button, import review) rather than raise a dialog.
- **Safety**: the natural-language bulk action never lets the model execute anything. The model only emits a JSON filter/action plan; matching is resolved locally against `users_cache`, the operator sees the exact affected rows, and a second explicit confirmation is required before reusing the existing bulk delete/update workers.
- **Redaction**: outbound prompts are scrubbed of emails/UUIDs/phone numbers when `redact_pii` is on (default). Credential-like values (`client_secret`, `api_key`, `authorization`, `bearer`, `password`, tokens) are redacted unconditionally regardless of that setting.

### Cleanup performed during removal

- Deleted `api/helix_client.py` and `HELIX_SETUP_CHECKLIST.md`.
- Removed the `mcp` pin from `requirements.txt`; no replacement dependency was needed since `api/llm_client.py` uses `httpx` (already required).
- Uninstalled `mcp` from the venv along with its 17 orphaned transitive dependencies (`mcp-types`, `httpx2`, `httpcore2`, `httpx-sse`, `sse-starlette`, `starlette`, `uvicorn`, `PyJWT`, `python-multipart`, `opentelemetry-api`, `pydantic`, `pydantic-settings`, `pydantic_core`, `annotated-types`, `typing-inspection`, `python-dotenv`, `click`). Packages shared with real dependencies (`anyio`, `h11`, `httpcore`, `certifi`, `idna`, and the `jsonschema` stack) were deliberately kept. `pip check` reports no broken requirements afterward.
- **Caught during cleanup**: `jsonschema` is used by `api/client.py::local_validate_user()` for optional local schema validation against `user_schema.json`, but it was never declared in `requirements.txt` — it happened to be installed only as an `mcp` transitive dependency. Removing `mcp` would have silently turned local validation into a no-op on a fresh install. `jsonschema` is now explicitly declared as an optional dependency.
- Audited every third-party import across the codebase against `requirements.txt`. The only undeclared import is `pymysql` in `test_connection.py`, a standalone legacy diagnostic script; the app itself is JDBC-only, so `pymysql` is intentionally excluded and a comment now records that decision.
- Deleted the stale `api/__pycache__/helix_client.cpython-314.pyc`, which kept the removed module importable even after the source file was deleted.

### Verification performed

- `python -m py_compile` clean across `workers.py`, `ui/main_window.py`, `ui/dialogs.py`, `api/client.py`, `api/llm_client.py`, `api/db_utils.py`, `api/ldap_utils.py`, `tps_tracker.py`, `app.py`.
- **Clean-install verification**: built a throwaway venv, installed only from `requirements.txt`, ran `pip check` (no broken requirements), and confirmed every app module imports successfully. This proves the dependency list is complete and self-sufficient.
- Import test of `MainWindow`, the new workers, and all new dialogs succeeds.
- Confirmed zero remaining `Helix`/`mcp` references in Python sources.
- Provider URL/payload construction unit-checked for both `openai_compatible` and `ollama` shapes.
- **Mock-server round trip**: stood up a local HTTP server implementing both the OpenAI-compatible (`/v1/models`, `/v1/chat/completions`) and Ollama (`/api/tags`, `/api/chat`) contracts, and confirmed `list_models()` and `chat()` parse each provider's response correctly.
- Redaction helpers and `parse_json_response()` (fenced JSON and JSON embedded in prose) verified.
- `AIBulkActionDialog._field_value()`/`_matches()` unit-tested across all five filter operators, dotted field paths, missing fields, and ANDed filter combinations, since that logic gates destructive operations.
- **Headless Qt runtime tests** (`QT_QPA_PLATFORM=offscreen`): dialogs actually constructed and driven, not just imported. Verified provider switching updates the default URL, config round-trips through `LLMConfig`, the bulk-action preview populates correctly, Apply is enabled only for `update`/`delete` plans (not `select`), a malformed non-dict plan is handled without crashing or enabling Apply, and the AI mapping button is shown only when an LLM client is supplied.
- **AI mapping suggestion end-to-end** against a mock LLM returning fenced JSON: valid targets applied, targets not in the known attribute list correctly rejected, and pre-existing mappings left untouched.
- Not yet exercised against a real LM Studio/Ollama instance (none running in this session); the mock server validates wire format but not real model behavior.

### Live testing against LM Studio (google/gemma-4-31b) - 2026-09-02

First real-model run. Three genuine defects surfaced that mock testing could not have caught:

1. **Reasoning models returned "empty response"** - Gemma-4-31B emits hidden chain-of-thought in a separate `reasoning_content` field. On harder prompts it consumed the entire token budget on reasoning (`finish_reason: length`, `reasoning_tokens: 697` of 700) and returned empty `content`. The old code silently produced `""` and then raised a misleading "The model returned an empty response."
   - **Fix**: `_parse_response()` now inspects `finish_reason`, `reasoning_content`, and `usage.completion_tokens_details.reasoning_tokens`, and raises an actionable error naming the model, the exhausted budget, and a concrete suggested value (double the current setting). Default `max_tokens` raised 1024 -> 4096.
2. **Default timeout far too low** - one bulk-plan request took **515 seconds** to complete successfully. The previous 120s default would have failed it as a timeout.
   - **Fix**: `DEFAULT_TIMEOUT` raised 120 -> 300 s, and timeout exceptions now produce a specific message telling the user to raise 'Request Timeout' rather than a generic connection error.
3. **Model invented a non-existent PingOne field** - for "disable everyone in the Contractors population" the model returned `"updates": {"status": "disabled"}`. PingOne has no `status` field (it is `enabled`). `AIBulkActionDialog` previously passed `updates` straight through to the PATCH payload with no validation, so a confirmed plan could have issued a malformed write.
   - **Fix**: added `ALLOWED_UPDATE_FIELDS` plus `_validate_updates()`. Any update key outside the known-attribute set (union the profile's visible columns, excluding `id`) blocks the Apply button and explains why. Verified against the exact plan the real model produced.

Correct behavior confirmed in the same run: model listing, plain chat, mapping suggestions (5/6 columns mapped correctly, unmappable column correctly omitted, all targets valid), filter generation, and local matching (`population.name == Contractors` correctly resolved to the expected users).

**Full end-to-end run through the real Qt worker/dialog layer** (not just direct async calls) also passed: `LLMModelListWorker`, assistant chat, "Explain (AI)" on a 401/`invalid_client` log excerpt (correctly diagnosed bad client credentials), data-quality review, `AttributeMappingDialog._ai_suggest_mappings` (4/4 correct, unmappable column left unset), and `AIBulkActionDialog._generate_plan` (correct plan, correct local match, boolean coercion applied).

4. **Redaction silently defeated part of the data-quality review** - the review prompt asked the model to find "malformed email domains", but with `redact_pii` on (the default) every address is replaced with `[EMAIL]` before sending. The model dutifully reported findings about `[EMAIL]` placeholders and could not possibly detect the planted typo `jdoe@exmaple.cmo`.
   - **Fix**: the prompt is now built from the redaction setting - email/format checks are only requested when redaction is off, and when it is on the model is told the placeholders are not real values. Verified live: with redaction on the output is clean (duplicate username + casing only); with redaction off the same data correctly yields "Malformed email domain: jdoe@exmaple.cmo".

### Gaps / Follow-up Research Needed

1. **Live model validation** — the wire format for both providers is covered by a mock server, but no real LM Studio/Ollama instance was available to confirm actual model behavior (response quality, streaming absence, timeout characteristics under real inference load). Smoke-test against at least one real server before relying on the AI features.
2. **Small-model JSON reliability** — `AIBulkActionDialog` and the mapping suggester require valid JSON. `parse_json_response()` tolerates code fences and surrounding prose, but small quantized models may still produce unusable output. Consider constrained/grammar-based decoding (LM Studio structured output, Ollama `format: json`) if this proves flaky in practice.
3. **No streaming** — responses are requested with `stream: false`, so long generations block until complete (the worker keeps the UI responsive, but there is no token-by-token feedback). Streaming would need a different worker signal design.
4. **Redaction is regex-based** — `redact_text()` catches emails, UUIDs, phone numbers, and common credential keys, but is not a comprehensive PII detector. Names, addresses, and employee IDs still pass through. Review before pointing AI features at sensitive production data.
5. **Bulk-action filter vocabulary is limited** — supported ops are `equals`, `contains`, `startswith`, `empty`, `not_empty`, ANDed together. No OR/negation/numeric/date comparisons. Extend `_matches()` if richer selection is needed.
6. **Single-turn chat** — `AIAssistantDialog` sends each prompt independently; there is no conversation history sent back to the model, so follow-up questions lack context. Adding history requires managing context-window limits.
7. **Import review is bounded** — the AI data-quality pass only examines the first 50 staged rows to stay within typical local context windows, so issues later in a large file are not seen.

## Past issue record

## 2026-09-02 - AI Bulk Action Could Emit an Invented PingOne Field

- **Date**: 2026-09-02
- **Issue**: Asked to "disable everyone in the Contractors population", the local model returned `"updates": {"status": "disabled"}`. PingOne has no `status` attribute (the correct field is `enabled`). `AIBulkActionDialog` passed the model's `updates` dict straight into the bulk-update payload, so a user who confirmed the plan would have issued a malformed write against every matched user.
- **Root Cause**: The preview/confirmation step validated *which users* were affected but never validated *what fields* would be written. Language models routinely produce plausible-but-wrong field names.
- **Solution**: Added `ALLOWED_UPDATE_FIELDS` and `_validate_updates()` to `AIBulkActionDialog`. Update keys outside the known PingOne attribute set (plus the profile's visible columns, excluding `id`) now block the Apply button with an explanation.
- **Files Affected**: `ui/dialogs.py`
- **Prevention**: When an AI proposes a mutation, validate both the *scope* (which records) and the *payload* (which fields/values). Human confirmation is not sufficient - an operator cannot be expected to know that `status` is not a real PingOne field.

## 2026-09-02 - Reasoning Models Return Empty Content and Are Very Slow

- **Date**: 2026-09-02
- **Issue**: Against LM Studio running `google/gemma-4-31b`, AI calls failed with a misleading "The model returned an empty response." One request that did succeed took 515 seconds, well past the 120-second default timeout.
- **Root Cause**: Reasoning models emit hidden chain-of-thought into a separate `reasoning_content` field. On harder prompts the entire `max_tokens` budget was consumed by reasoning (`finish_reason: length`), leaving `content` empty. The parser returned `""` without inspecting `finish_reason`, and the defaults (1024 tokens, 120 s) were tuned for fast non-reasoning models.
- **Solution**: `_parse_response()` now inspects `finish_reason`, `reasoning_content`, and reasoning token usage and raises actionable errors; `max_tokens` default 1024 -> 4096; `DEFAULT_TIMEOUT` 120 -> 300 s; timeouts get a dedicated message.
- **Files Affected**: `api/llm_client.py`, `ui/dialogs.py`
- **Prevention**: Never treat an empty completion as simply "empty" - inspect `finish_reason` and provider-specific fields first, and surface the remedy in the error text. Assume local models may be an order of magnitude slower than hosted ones when choosing defaults.

## 2026-09-02 - Undeclared `jsonschema` Dependency Masked by a Transitive Install

- **Date**: 2026-09-02
- **Issue**: `jsonschema` is used by `api/client.py::local_validate_user()` for optional local validation, but it was never listed in `requirements.txt`. It only worked because another package pulled it in transitively. Removing that package would have silently reduced local validation to a no-op on any fresh install - with no error, since the import is wrapped in `try/except`.
- **Root Cause**: An optional feature guarded by `try: import X / except: return` will never fail loudly, so a missing declaration is invisible until someone builds a clean environment.
- **Solution**: Declared `jsonschema` explicitly in `requirements.txt`, and verified completeness by installing into a throwaway venv from `requirements.txt` alone and importing every module.
- **Files Affected**: `requirements.txt`, `api/client.py` (usage only)
- **Prevention**: When adding or removing dependencies, audit *all* third-party imports against `requirements.txt` - including ones inside `try/except` blocks. Validate with a clean-venv install rather than trusting the working environment.

## 2026-09-02 - Stale `.pyc` Kept a Deleted Module Importable

- **Date**: 2026-09-02
- **Issue**: After deleting `api/helix_client.py`, `import api.helix_client` still succeeded because `api/__pycache__/helix_client.cpython-314.pyc` remained on disk.
- **Root Cause**: Python can import from a leftover bytecode cache when the corresponding source file is gone.
- **Solution**: Deleted the orphaned `.pyc` and confirmed the import then raises `ModuleNotFoundError`.
- **Files Affected**: `api/__pycache__/`
- **Prevention**: After deleting a module, remove its `__pycache__` entry and assert the import fails. A grep of source files alone is not sufficient proof of removal.

---
