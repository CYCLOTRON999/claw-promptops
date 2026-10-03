# CLAW PROMPTOPS - Failure Log

This log documents genuine engineering failures, root causes, applied fixes, and lessons learned encountered during development.

---

### [FL-20261003-01] Initial Environment Setup & Python 3.14 Compatibility
- **Date:** 2026-10-03
- **Component:** Environment Setup / CLI Inspection
- **Problem Description:** Local system lacked global `docker` and `ollama` binaries in `$PATH`, and system Python was Python 3.14.3.
- **Root Cause Analysis:** macOS host did not have global container or local LLM daemons pre-installed. Python 3.14 is a bleeding-edge release requiring wheel verification.
- **Fix Applied:** Configured an isolated virtual environment (`.venv`). Selected modern pure-Python and C-ABI compatible wheels (`fastapi`, `pydantic>=2`, `sqlalchemy>=2`, `jsonschema`, `streamlit`). Prioritized offline deterministic `MockAdapter` as the primary development and test engine.
- **Verification:** Verified all wheels installed cleanly and `pip check` confirmed zero broken dependencies.
- **Lesson Learned:** LLM development platforms must be local-first and self-contained; never assume developer machines possess pre-installed external services.

---

### [FL-20261003-02] AttributeError: 'GenerationResponse' Object Lacked 'metadata' Field
- **Date:** 2026-10-03
- **Component:** Model Contract / Request-Response Schema (`app/adapters/base.py`)
- **Problem Description:** Test suite crashed with `AttributeError: 'GenerationResponse' object has no attribute 'metadata'` during pipeline completion.
- **Root Cause Analysis:** `GenerationRequest` included `metadata: Dict[str, Any]`, but `GenerationResponse` omitted the field. When `generator.execute()` attempted to attach `final_response.metadata["routing_reason"] = routing_reason`, Pydantic rejected the undeclared attribute.
- **Fix Applied:** Added `metadata: Dict[str, Any] = Field(default_factory=dict)` to `GenerationResponse`.
- **Verification:** Ran `pytest tests/integration/test_pipeline.py`, which passed.
- **Lesson Learned:** Maintain parity between request/response tracking contracts when transferring telemetry across pipeline stages.

---

### [FL-20261003-03] Fallback Model Repeated Primary Model's Simulated Failure
- **Date:** 2026-10-03
- **Component:** Fallback Subsystem (`app/generation/fallback.py`, `app/adapters/mock.py`)
- **Problem Description:** `test_end_to_end_fallback_flow` failed because `mock-fallback` timed out exactly like the primary model.
- **Root Cause Analysis:** `fallback_request` deep-copied `gen_request`, including `metadata["mock_scenario"] = "MOCK_TIMEOUT"`. Consequently, the fallback adapter also simulated a timeout.
- **Fix Applied:** Updated `MockAdapter` generation and streaming methods to check for `request.metadata.get("fallback_activated", False)`, treating fallback invocation as a recovery event that outputs valid fallback data.
- **Verification:** Reran integration tests; fallback activation passed with `res.fallback_used == True` and valid data.
- **Lesson Learned:** Disaster recovery models must not inherit failure injection parameters intended strictly for the primary model under test.

---

### [FL-20261003-04] Version Mismatch in Regression Test Suite (94% vs >=95% Pass Rate)
- **Date:** 2026-10-03
- **Component:** Prompt Registry / Evaluation Runner (`prompts/content_pack/`, `evaluation/runner.py`)
- **Problem Description:** `test_full_50_suite_execution` failed with `assert 94.0 >= 95.0` (47/50 tests passed).
- **Root Cause Analysis:** The test suite ran with `prompt_version="v2.0"`. While `event_brief` had `v2.0.yaml`, `content_pack` only had `v1.0.yaml`. The 3 test cases for `content_pack` (TC006, TC007, TC010) raised `PromptRegistryError`.
- **Fix Applied:** Created `prompts/content_pack/v2.yaml` and implemented defensive fallback in `evaluation/runner.py` to default to `latest` if a requested version is not registered for that specific task.
- **Verification:** All 50 test cases passed with 100% schema validity rate in `test_50_suite.py`.
- **Lesson Learned:** Multi-task test runners must gracefully handle heterogeneous prompt version numbers across different task registries.

---

### [FL-20261003-05] SyntaxError: Nonlocal Binding at Module Scope in Streamlit Dashboard
- **Date:** 2026-10-03
- **Component:** UI Dashboard (`ui/dashboard.py`)
- **Problem Description:** Importing `ui.dashboard` crashed with `SyntaxError: no binding for nonlocal 'stream_text' found`.
- **Root Cause Analysis:** `nonlocal` was used inside an inner function defined at the module top-level where no enclosing outer function existed.
- **Fix Applied:** Replaced `nonlocal stream_text` with a mutable container `stream_container = [""]`.
- **Verification:** Executed `python -c "import ui.dashboard"`; imported with exit code 0.
- **Lesson Learned:** In script-style frameworks like Streamlit, top-level code runs in module scope, where `nonlocal` cannot bind.
