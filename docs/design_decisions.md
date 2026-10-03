# CLAW PROMPTOPS - Design Decisions & Architectural Rationale

This document explains the foundational engineering and architectural choices made in the design and implementation of CLAW PromptOps. It serves as both an architectural record and an evaluation guide for project reviews.

---

### 1. Why FastAPI?
- **Asynchronous Native Performance:** Built on Starlette and ASGI (`uvicorn`), enabling non-blocking I/O during streaming LLM token chunks, concurrent network requests to external providers, and database operations.
- **Strict Pydantic Integration:** Automatically validates request/response payloads at API boundaries and generates interactive OpenAPI/Swagger documentation (`/docs`) out of the box.
- **Lightweight & Modular:** Avoids heavy monolithic dependencies (like Django) while offering clean dependency injection for database sessions and adapters.

---

### 2. Why SQLite + SQLAlchemy 2.0?
- **Zero-Setup Local Reproducibility:** SQLite requires no external server daemons, credentials, or network configuration. A student or evaluator can clone the repo and immediately inspect persistent run history.
- **SQLAlchemy 2.0 Modern Standards:** Fully typed models (`Mapped`, `mapped_column`) and clean Repository pattern separation. If production scaling is needed, switching to PostgreSQL requires only changing the `DATABASE_URL` connection string without changing application queries.

---

### 3. Why Pydantic v2 & JSON Schema?
- **Rust-Backed Validation Speed:** Pydantic v2 offers an order-of-magnitude performance improvement for parsing and validating JSON structures.
- **Two-Tier Validation:**
  1. *Pydantic Models:* Strong typing for internal Python runtime objects (Requests, Responses, Run records).
  2. *JSON Schema:* Dynamic, user-defined schema specifications loaded from YAML/JSON files, allowing arbitrary structured schemas (e.g. `event_brief`, `content_pack`) without needing custom Python classes for every user-defined task.

---

### 4. Why Provider Adapter Architecture?
- **Decoupling Application from Vendors:** LLM APIs differ in endpoints, headers, payload formats, and streaming implementations (e.g. Ollama vs OpenAI vs Anthropic).
- **Single Generation Pipeline:** Core engineering logic (prompt rendering, routing, parsing, repair loops, retries, metric collection) runs identically regardless of whether the model is local Ollama, cloud-based OpenAI, or an offline Mock.
- **Vendor Lock-in Immunity:** Adding a new provider only requires subclassing `BaseModelAdapter` and implementing `generate()` and `stream()`.

---

### 5. Why a Deterministic MockAdapter?
- **Academic & Evaluation Dependability:** Demonstrations and test suites must not fail due to WiFi dropouts, API rate limits, expired credit cards, or missing Ollama binaries.
- **Controlled Failure Simulation:** A deterministic mock can simulate `MOCK_MALFORMED_JSON`, `MOCK_MISSING_FIELD`, `MOCK_TIMEOUT`, and `MOCK_INTERRUPTED_STREAM` on demand, proving that recovery systems (repair, retry, fallback) work predictably under test.
- **Zero-Cost CI/CD:** Automated regression tests run in seconds without consuming API tokens.

---

### 6. Why Prompt Versioning & Immutability?
- **Engineering Reproducibility:** If prompt `v1.0` is modified in-place, past experiment results become non-reproducible and invalid.
- **Regression Tracking:** Prompt changes (e.g. adding strict instructions or changing few-shot examples) must be measurable. Versioning (`v1.0`, `v1.1`, `v2.0`) allows running A/B experiments to verify whether an updated prompt actually improves schema validity or increases latency/cost.

---

### 7. Why Separate Retry from Repair?
- **Transient vs. Semantic Errors:**
  - **Retry:** Addresses *operational / network / infrastructure* failures (e.g., HTTP 503, connection reset, timeout, interrupted stream). Retrying sends the *exact same prompt* with exponential backoff.
  - **Repair:** Addresses *model reasoning / syntax / schema* failures (e.g., markdown ticks instead of raw JSON, missing mandatory fields, wrong data type). Retrying the exact same prompt often yields the same bad response. Repair builds a *corrective prompt* showing the model its previous erroneous output and specific schema error messages.
- Conflating them wastes tokens and leads to infinite loops.

---

### 8. Why Deterministic & Explainable Model Routing?
- **Auditability:** In enterprise PromptOps, routing to a cheaper model or smaller local model must have a clear business justification (e.g., "Task classified as extraction + low latency required").
- **Predictable Cost Control:** Black-box routing is impossible to debug when output quality degrades or cloud bills spike. Recording `routing_reason` on every run guarantees transparent auditing.

---

### 9. Why Configuration-Aware Caching?
- A cache key must incorporate:
  `Hash(Model + Prompt Name + Prompt Version + Rendered Prompt + Temperature + Max Tokens + Response Format)`
- If prompt version `v1.1` is deployed, queries must never hit cached responses from `v1.0`. Similarly, temperature differences (e.g., 0.0 deterministic vs 0.7 creative) must produce distinct cache entries.

---

### 10. Why at Least 50 Fixed Test Cases?
- **No Dynamic Test Hallucination:** Generating random test cases at runtime makes regression testing unscientific and untrustworthy.
- **Edge Coverage:** A rigorous test suite must include normal inputs, messy inputs, missing information, schema boundary violations, type mismatch traps, and simulated network interruptions. Fixed test cases ensure before-and-after comparability across model and prompt revisions.
