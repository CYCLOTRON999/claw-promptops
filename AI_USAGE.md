# CLAW PROMPTOPS - AI Usage & Engineering Attribution

This document records the exact usage of AI engineering assistance during the design, development, and testing of CLAW PromptOps, adhering to academic honesty and engineering integrity standards.

---

## 1. AI Tools Utilized
- **Assistant:** Google Antigravity Agentic IDE (DeepMind Gemini 3.8 Flash model)
- **Role:** Senior Software Architect, Python Engineer, Testing Engineer, and Technical Mentor

---

## 2. Areas of Assistance
- **Architecture Specification & Design:** Structuring the modular directory hierarchy, decoupling the provider adapters, and establishing the validation-repair-retry-fallback pipeline.
- **Boilerplate & Test Generation:** Writing comprehensive test cases (including the 50 fixed evaluation scenarios), Pydantic schemas, and SQLAlchemy model declarations.
- **Documentation & Diagrams:** Drafting Mermaid workflow diagrams, architectural rationale in `docs/design_decisions.md`, and API contracts.

---

## 3. Human Review & Verification Methodology
- **Zero-Tolerance for Fabricated Metrics:** All metrics (latency, token count, cost, validity rates) must strictly compute from actual execution runs stored in SQLite. No synthetic randomizers are permitted in production code paths.
- **Automated Verification:** Every generated component is paired with unit, integration, and regression tests executed via `pytest`. Code is not considered complete until all tests pass in the local `.venv`.
- **Offline Reliability:** Verified that the test suite runs with network interfaces disabled or without external API keys via the deterministic `MockAdapter`.

---

## 4. Known Limitations
- Real Ollama inference requires an Ollama daemon running locally at `http://localhost:11434` with desired models pulled (e.g. `llama3` or `mistral`).
- Live OpenAI inference requires setting `OPENAI_API_KEY` in `.env`.
- Streamlit UI runs locally and connects to either the FastAPI backend or directly to the application services.
