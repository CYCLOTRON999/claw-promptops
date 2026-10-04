"""CLAW PROMPTOPS - Enterprise Streamlit Operations & Evaluation Dashboard."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st

# Ensure project root is in sys.path when launched as streamlit run ui/dashboard.py
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Application imports
from app.adapters import list_available_models, get_adapter
from app.cache.cache import default_cache
from app.config import settings
from app.database.database import SessionLocal, init_db
from app.database.repositories import (
    ExperimentRepository,
    FailureRepository,
    RunRepository,
    TestCaseRepository
)
from app.experiments.runner import ExperimentRunner
from app.generation.generator import PromptOpsGenerator
from app.metrics.cost import CostCalculator
from app.prompts.loader import PromptDefinition, PromptVariable
from app.prompts.registry import default_prompt_registry, PromptRegistryError
from app.routing.router import ModelRouter, RoutingCriteria
from app.validation.json_validator import SchemaValidator
from evaluation.runner import EvaluationSuiteRunner

# Page Configuration
st.set_page_config(
    page_title="CLAW PromptOps Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-End Dark Cyberpunk / Navy Theme Styling
st.markdown("""
<style>
    /* Global Background and Typography */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Headers & Accent Gradient */
    h1, h2, h3, h4 {
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }
    
    .claw-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60a5fa 0%, #38bdf8 50%, #93c5fd 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .claw-tagline {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    
    /* Metrics Card */
    .metric-card {
        background-color: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 1.2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        transition: border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #3b82f6;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.3rem;
    }
    
    /* Status Badges */
    .badge-success {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid #059669;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-repaired {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid #d97706;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-failed {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid #dc2626;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    /* Code blocks and JSON boxes */
    .stCodeBlock, div[data-testid="stJson"] {
        border-radius: 8px !important;
        border: 1px solid #1e293b !important;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #080c14;
        border-right: 1px solid #1e293b;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Database & Core Services
init_db()
generator = PromptOpsGenerator()
suite_runner = EvaluationSuiteRunner()
suite_runner.seed_database()
experiment_runner = ExperimentRunner()


def run_async(coro):
    """Run an async coroutine synchronously inside Streamlit event loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# Sidebar Navigation & Platform Header
with st.sidebar:
    st.markdown('<div class="claw-title">⚡ CLAW PROMPTOPS</div>', unsafe_allow_html=True)
    st.caption("Controlled LLM Generation & Evaluation")
    st.markdown("---")

    nav_selection = st.radio(
        "Navigation",
        [
            "Overview",
            "Generate",
            "Prompt Registry",
            "Models",
            "Experiments",
            "Test Suite (50+)",
            "Run History",
            "Failures",
            "Metrics"
        ],
        index=0
    )

    st.markdown("---")
    st.caption("SYSTEM ENVIRONMENT")
    st.markdown(f"**Default Model:** `{settings.default_model}`")
    st.markdown(f"**Cache Active:** `{settings.cache_enabled}`")
    st.markdown(f"**Max Retries:** `{settings.max_retries}`")
    st.markdown(f"**Max Repairs:** `{settings.max_repair_attempts}`")
    st.markdown(f"**Timeout:** `{settings.model_timeout_seconds}s`")


# ==============================================================================
# 1. OVERVIEW PAGE
# ==============================================================================
if nav_selection == "Overview":
    st.markdown('<div class="claw-title">CLAW PromptOps Platform</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="claw-tagline">From messy natural language instructions to reliable, validated structured AI outputs.</div>',
        unsafe_allow_html=True
    )

    # Fetch aggregate verified metrics from SQLite
    db = SessionLocal()
    try:
        metrics = RunRepository.get_aggregate_metrics(db)
        recent_runs = RunRepository.list_runs(db, limit=5)
        recent_failures = FailureRepository.list_failures(db, limit=5)
        recent_experiments = ExperimentRepository.list_experiments(db, limit=3)
    finally:
        db.close()

    # Metric Cards Grid
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metrics['total_runs']}</div>
            <div class="metric-label">Total Runs</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metrics['schema_validity_pct']}%</div>
            <div class="metric-label">Schema Validity</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metrics['avg_latency_ms']:.1f} ms</div>
            <div class="metric-label">Avg Latency</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metrics['repair_rate_pct']}%</div>
            <div class="metric-label">Repair Rate</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{metrics['cache_hit_rate_pct']}%</div>
            <div class="metric-label">Cache Hit Rate</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("###")

    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        st.subheader("System Architecture Lifecycle")
        st.markdown("""
        Every instruction passes through strict PromptOps control stages:
        1. **Classification & Routing:** Explainable routing based on task, latency, and cost constraints.
        2. **Immutable Prompt Registry:** Template rendering with strict variable completeness validation.
        3. **Deterministic Cache:** Parameter-hashed cache preventing duplicate execution costs.
        4. **Resilient Execution:** Bounded exponential backoff retries and automated fallback chains.
        5. **Structured Parsing & Validation:** JSON extraction with Pydantic v2 and JSON Schema checks.
        6. **Automated Repair Loop:** Re-prompts the model with targeted error diagnostics upon schema failure.
        7. **Observability & Audit Trail:** Persistent storage of latency, tokens, cost, and failure logs.
        """)

        st.subheader("Recent Generation Runs")
        if recent_runs:
            for r in recent_runs:
                badge_class = "badge-success" if r.status == "SUCCESS" else ("badge-repaired" if r.status == "REPAIRED" else "badge-failed")
                st.markdown(f"""
                <div style="background:#111827; border:1px solid #1e293b; padding:0.8rem 1rem; border-radius:8px; margin-bottom:0.5rem; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong style="color:#ffffff;">{r.id}</strong> — <span style="color:#94a3b8;">{r.task_type}</span> ({r.model})
                        <div style="font-size:0.8rem; color:#64748b;">{r.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | Latency: {r.latency_ms:.1f}ms | Tokens: {r.total_tokens}</div>
                    </div>
                    <span class="{badge_class}">{r.status}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No runs recorded yet. Navigate to 'Generate' or 'Test Suite' to execute runs.")

    with right_col:
        st.subheader("Recent Outages & Failures")
        if recent_failures:
            for f in recent_failures:
                st.markdown(f"""
                <div style="background:#181014; border:1px solid #7f1d1d; padding:0.8rem 1rem; border-radius:8px; margin-bottom:0.5rem;">
                    <div style="display:flex; justify-content:space-between;">
                        <strong style="color:#f87171;">{f.failure_type}</strong>
                        <span style="font-size:0.75rem; color:#fca5a5;">{f.timestamp.strftime('%H:%M:%S')}</span>
                    </div>
                    <div style="font-size:0.85rem; color:#cbd5e1; margin-top:0.2rem;">{f.error_message[:120]}...</div>
                    <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.3rem;">Run: {f.run_id} | Model: {f.model} | Retries: {f.retry_count} | Repairs: {f.repair_count}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No system failures recorded. Zero active outages.")

        st.subheader("Recent Benchmark Experiments")
        if recent_experiments:
            for exp in recent_experiments:
                st.markdown(f"""
                <div style="background:#111827; border:1px solid #1e293b; padding:0.8rem 1rem; border-radius:8px; margin-bottom:0.5rem;">
                    <strong style="color:#60a5fa;">{exp.name}</strong> ({exp.id})
                    <div style="font-size:0.8rem; color:#94a3b8;">
                        Prompt: {exp.prompt_a_name} ({exp.prompt_a_version} vs {exp.prompt_b_version})<br/>
                        Models: {exp.model_a} vs {exp.model_b}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No experiments executed yet. Navigate to 'Experiments' to run an A/B benchmark.")


# ==============================================================================
# 2. GENERATE PAGE
# ==============================================================================
elif nav_selection == "Generate":
    st.subheader("⚡ Controlled Generation & Reliability Pipeline")
    st.caption("Submit unstructured natural-language requests and inspect full pipeline telemetry.")

    col_config, col_main = st.columns([1, 2])

    with col_config:
        st.markdown("#### Generation Parameters")
        available_prompts = default_prompt_registry.list_prompts()
        selected_prompt_name = st.selectbox("Prompt Template", available_prompts, index=0)

        versions = default_prompt_registry.list_versions(selected_prompt_name)
        selected_version = st.selectbox("Prompt Version", versions, index=len(versions)-1)
        prompt_def = default_prompt_registry.get_prompt(selected_prompt_name, selected_version)

        available_models = [m.name for m in list_available_models()]
        selected_model = st.selectbox("Model Backend", ["auto (Model Router)"] + available_models, index=0)

        col_t, col_m = st.columns(2)
        with col_t:
            temperature = st.slider("Temperature", 0.0, 1.0, float(prompt_def.model_requirements.temperature), 0.05)
        with col_m:
            max_tokens = st.number_input("Max Tokens", 64, 4096, int(prompt_def.model_requirements.max_tokens or 1024), 64)

        structured_output = st.checkbox("Enforce JSON Schema", value=True)
        streaming_enabled = st.checkbox("Enable Live Streaming", value=False)

        st.markdown("---")
        st.markdown("#### Failure Simulation Mode (Demo)")
        failure_scenario = st.selectbox(
            "Inject Failure Scenario",
            [
                "MOCK_VALID (Normal)",
                "MOCK_MALFORMED_JSON (Trigger Repair)",
                "MOCK_MISSING_FIELD (Trigger Repair)",
                "MOCK_WRONG_TYPE (Trigger Repair)",
                "MOCK_TIMEOUT (Trigger Fallback)",
                "MOCK_PROVIDER_ERROR (Trigger Retry)",
                "MOCK_INTERRUPTED_STREAM"
            ],
            index=0
        )

    with col_main:
        st.markdown("#### Messy Natural Language Instruction")
        default_instruction = (
            "Plan a cheap 3-day Delhi trip. Include food, don't put more than four activities per day, "
            "and make sure everything is practical."
        ) if selected_prompt_name == "event_brief" else (
            "Announcing CLAW PromptOps: The enterprise platform for reliable LLM pipelines and automated prompt evaluation."
        )

        user_input = st.text_area(
            "Enter messy instruction...",
            value=default_instruction,
            height=130
        )

        run_btn = st.button("RUN GENERATION PIPELINE", type="primary", use_container_width=True)

        if run_btn:
            # Build variable dictionary
            var_name = prompt_def.variables[0].name if prompt_def.variables else "instruction"
            scenario_code = failure_scenario.split(" ")[0]

            variables = {
                var_name: user_input,
                "instruction": user_input,
                "topic": user_input
            }
            if scenario_code != "MOCK_VALID":
                variables["mock_scenario"] = scenario_code

            resolved_model = None if selected_model.startswith("auto") else selected_model

            # Handle streaming mode
            if streaming_enabled and not scenario_code.startswith("MOCK_"):
                st.markdown("##### Live Token Stream")
                stream_placeholder = st.empty()
                stream_container = [""]
                adapter = get_adapter(resolved_model or settings.default_model)
                rendered = default_prompt_registry.render_prompt(selected_prompt_name, selected_version, variables)

                gen_req = GenerationRequest(
                    task_type=prompt_def.task_type,
                    prompt=rendered,
                    variables=variables,
                    model=adapter.model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

                async def stream_tokens():
                    async for chunk in adapter.stream(gen_req):
                        stream_container[0] += chunk.text
                        stream_placeholder.code(stream_container[0], language="json")

                run_async(stream_tokens())

            # Complete pipeline run
            with st.spinner("Processing through PromptOps pipeline..."):
                response = run_async(generator.execute(
                    task_type=prompt_def.task_type,
                    prompt_name=selected_prompt_name,
                    prompt_version=selected_version,
                    variables=variables,
                    preferred_model=resolved_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    metadata={"mock_scenario": scenario_code} if scenario_code != "MOCK_VALID" else {}
                ))

            # Telemetry Summary Bar
            st.markdown("---")
            st.markdown("#### Pipeline Telemetry & Audit")

            t1, t2, t3, t4, t5, t6 = st.columns(6)
            t1.metric("Status", response.status)
            t2.metric("Model Used", response.model)
            t3.metric("Latency", f"{response.latency_ms:.1f} ms")
            t4.metric("Tokens", f"{response.input_tokens + response.output_tokens}")
            t5.metric("Cost", CostCalculator.format_cost(response.estimated_cost))
            t6.metric("Cache", "HIT" if response.cached else "MISS")

            r1, r2, r3 = st.columns(3)
            r1.metric("Repair Attempts", response.repair_count)
            r2.metric("Network Retries", response.retry_count)
            r3.metric("Fallback Activated", "YES" if response.fallback_used else "NO")

            routing_reason = response.metadata.get("routing_reason", "Standard routing")
            st.info(f"**Routing Explanation:** {routing_reason}")

            # Render Tabs for Output Inspection
            tab_json, tab_raw, tab_rendered = st.tabs(["Structured JSON Output", "Raw Model Output", "Rendered Prompt"])

            with tab_json:
                if response.structured_output:
                    st.json(response.structured_output)
                    st.success("✅ Output strictly conforms to schema specifications.")
                else:
                    st.error(f"❌ Output failed validation: {response.error}")

            with tab_raw:
                st.code(response.text, language="json" if response.structured_output else "text")

            with tab_rendered:
                try:
                    rendered_p = default_prompt_registry.render_prompt(selected_prompt_name, selected_version, variables)
                    st.code(rendered_p, language="markdown")
                except Exception as exc:
                    st.warning(f"Could not render preview: {exc}")


# ==============================================================================
# 3. PROMPT REGISTRY PAGE
# ==============================================================================
elif nav_selection == "Prompt Registry":
    st.subheader("📚 Immutable Prompt Registry")
    st.caption("Version-controlled prompt templates with strict variable validation and change history.")

    prompts = default_prompt_registry.list_prompts()
    selected_prompt = st.selectbox("Select Prompt Template", prompts, index=0)

    versions = default_prompt_registry.list_versions(selected_prompt)
    selected_ver = st.selectbox("Select Version", versions, index=len(versions)-1)

    prompt_def = default_prompt_registry.get_prompt(selected_prompt, selected_ver)

    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.markdown(f"#### Template: `{prompt_def.name}` ({prompt_def.version})")
        st.markdown(f"**Description:** {prompt_def.description}")
        st.markdown(f"**Change Log:** *{prompt_def.change_description}*")
        st.markdown(f"**Output Schema:** `{prompt_def.output_schema or 'None'}`")
        st.code(prompt_def.template, language="markdown")

    with col2:
        st.markdown("#### Variable Specifications")
        for v in prompt_def.variables:
            req_str = "Required" if v.required else "Optional"
            st.markdown(f"- **`{v.name}`** ({req_str}): {v.description}")

        st.markdown("#### Model Requirements")
        st.markdown(f"- **Temperature:** `{prompt_def.model_requirements.temperature}`")
        st.markdown(f"- **Max Tokens:** `{prompt_def.model_requirements.max_tokens}`")
        st.markdown(f"- **Format:** `{prompt_def.model_requirements.response_format}`")

    st.markdown("---")
    st.subheader("Change History (Audit Trail)")
    history = default_prompt_registry.get_change_history(selected_prompt)
    for h in history:
        st.markdown(f"""
        <div style="background:#111827; border:1px solid #1e293b; padding:0.8rem 1rem; border-radius:8px; margin-bottom:0.5rem;">
            <strong style="color:#60a5fa;">Version {h['version']}</strong> — <span style="color:#94a3b8;">Created {h['date']}</span>
            <div style="margin-top:0.2rem; color:#f1f5f9;">{h['description']}</div>
            <div style="font-size:0.8rem; color:#38bdf8; margin-top:0.2rem;">Changes: {h['change_description']}</div>
        </div>
        """, unsafe_allow_html=True)


# ==============================================================================
# 4. MODELS PAGE
# ==============================================================================
elif nav_selection == "Models":
    st.subheader("🤖 Configured Model Backends & Pricing Profiles")
    st.caption("Decoupled model adapter capability profiles and cost rates.")

    models = list_available_models()
    for m in models:
        with st.expander(f"{'⚡ [MOCK]' if m.is_mock else '🌐'} {m.name} ({m.provider})", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Provider:** `{m.provider}`")
            c2.markdown(f"**Structured Output:** `{'Supported' if m.supports_structured else 'No'}`")
            c3.markdown(f"**Streaming:** `{'Supported' if m.supports_streaming else 'No'}`")
            c4.markdown(f"**Context Window:** `{m.context_window} tokens`")

            p1, p2 = st.columns(2)
            p1.markdown(f"**Input Price (per 1K):** `{CostCalculator.format_cost(m.input_price_per_1k)}`")
            p2.markdown(f"**Output Price (per 1K):** `{CostCalculator.format_cost(m.output_price_per_1k)}`")

            st.caption(m.description)


# ==============================================================================
# 5. EXPERIMENTS PAGE
# ==============================================================================
elif nav_selection == "Experiments":
    st.subheader("🧪 Side-by-Side Prompt & Model A/B Benchmarks")
    st.caption("Measure and compare prompt versions (v1 vs v2) and models on identical test cases.")

    col_setup, col_preview = st.columns([1, 1.2])

    with col_setup:
        exp_name = st.text_input("Experiment Name", value="Event Brief: Baseline v1.0 vs Hardened v2.0")
        prompt_name = st.selectbox("Prompt to Benchmark", default_prompt_registry.list_prompts(), index=0)

        versions = default_prompt_registry.list_versions(prompt_name)
        v_a = st.selectbox("Variant A Version", versions, index=0)
        v_b = st.selectbox("Variant B Version", versions, index=min(1, len(versions)-1))

        models = [m.name for m in list_available_models()]
        m_a = st.selectbox("Variant A Model", models, index=0)
        m_b = st.selectbox("Variant B Model", models, index=0)

        run_exp_btn = st.button("RUN BENCHMARK EXPERIMENT", type="primary", use_container_width=True)

    if run_exp_btn:
        with st.spinner("Executing identical 50-case benchmark on both variants..."):
            report = run_async(experiment_runner.run_comparison(
                name=exp_name,
                prompt_name=prompt_name,
                prompt_version_a=v_a,
                prompt_version_b=v_b,
                model_a=m_a,
                model_b=m_b
            ))

        st.success(f"Benchmark '{report.name}' completed! Experiment ID: `{report.experiment_id}`")

        # Side-by-Side Comparison Table
        st.markdown("### Measured Comparison Results")

        comp_data = {
            "Metric": [
                "Total Runs",
                "Schema Validity",
                "Instruction Following",
                "Average Latency",
                "Average Tokens",
                "Total Cost",
                "Repair Rate",
                "Failure Rate"
            ],
            f"Variant A ({v_a})": [
                report.variant_a.total_runs,
                f"{report.variant_a.schema_validity_pct}%",
                f"{report.variant_a.instruction_following_pct}%",
                f"{report.variant_a.avg_latency_ms:.1f} ms",
                f"{report.variant_a.avg_tokens:.1f}",
                CostCalculator.format_cost(report.variant_a.total_cost_usd),
                f"{report.variant_a.repair_rate_pct}%",
                f"{report.variant_a.failure_rate_pct}%"
            ],
            f"Variant B ({v_b})": [
                report.variant_b.total_runs,
                f"{report.variant_b.schema_validity_pct}%",
                f"{report.variant_b.instruction_following_pct}%",
                f"{report.variant_b.avg_latency_ms:.1f} ms",
                f"{report.variant_b.avg_tokens:.1f}",
                CostCalculator.format_cost(report.variant_b.total_cost_usd),
                f"{report.variant_b.repair_rate_pct}%",
                f"{report.variant_b.failure_rate_pct}%"
            ],
            "Delta (B - A)": [
                "-",
                f"{report.deltas['validity_delta_pct']:+}%",
                f"{report.deltas['instruction_score_delta_pct']:+}%",
                f"{report.deltas['latency_delta_ms']:+} ms",
                f"{report.deltas['tokens_delta']:+}",
                f"${report.deltas['cost_delta_usd']:+.6f}",
                f"{report.deltas['repair_rate_delta_pct']:+}%",
                f"{report.deltas['failure_rate_delta_pct']:+}%"
            ]
        }
        st.dataframe(comp_data, use_container_width=True)


# ==============================================================================
# 6. TEST SUITE (50+) PAGE
# ==============================================================================
elif nav_selection == "Test Suite (50+)":
    st.subheader("🛡️ 50+ Fixed Test Regression Suite")
    st.caption("Deterministic regression test cases covering normal, malformed, missing, type, timeout, and stream failure cases.")

    test_cases = suite_runner.load_test_cases()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        run_all_btn = st.button("RUN ALL 50 TESTS", type="primary", use_container_width=True)
    with c2:
        filter_cat = st.selectbox("Filter Category", ["All"] + sorted(list(set(tc["category"] for tc in test_cases))))

    if run_all_btn:
        with st.spinner("Running all 50 regression tests through pipeline..."):
            suite_res = run_async(suite_runner.run_suite(model="mock-deterministic", prompt_version="v2.0"))

        st.success(f"Execution Complete: {suite_res['passed']}/{suite_res['total_tests']} tests passed ({suite_res['pass_rate_pct']}%)")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Schema Validity", f"{suite_res['schema_validity_pct']}%")
        m2.metric("Avg Latency", f"{suite_res['avg_latency_ms']:.1f} ms")
        m3.metric("Repairs Needed", f"{suite_res['repair_rate_pct']}%")
        m4.metric("Fallbacks Used", f"{suite_res['fallback_rate_pct']}%")

    # Display Test Cases Table
    st.markdown("### Test Cases Inventory")
    filtered = [tc for tc in test_cases if filter_cat == "All" or tc["category"] == filter_cat]

    for tc in filtered:
        with st.expander(f"`{tc['id']}` [{tc['category'].upper()}] - {tc['description']}"):
            st.markdown(f"**Input:** `{tc['input_text']}`")
            st.markdown(f"**Expected Schema:** `{tc.get('expected_schema')}`")
            st.json(tc.get("expected", {}))


# ==============================================================================
# 7. RUN HISTORY PAGE
# ==============================================================================
elif nav_selection == "Run History":
    st.subheader("📜 Persistent Run Audit History")
    st.caption("Every generation is preserved with full reproducible parameters, latency, and token metrics.")

    db = SessionLocal()
    try:
        runs = RunRepository.list_runs(db, limit=50)
    finally:
        db.close()

    if runs:
        run_table = []
        for r in runs:
            run_table.append({
                "Run ID": r.id,
                "Timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Task": r.task_type,
                "Model": r.model,
                "Version": r.prompt_version,
                "Status": r.status,
                "Latency (ms)": round(r.latency_ms, 1),
                "Tokens": r.total_tokens,
                "Cost": CostCalculator.format_cost(r.estimated_cost),
                "Repairs": r.repair_count,
                "Retries": r.retry_count,
                "Fallback": "Yes" if r.fallback_used else "No"
            })
        st.dataframe(run_table, use_container_width=True)
    else:
        st.info("No runs recorded in SQLite database yet.")


# ==============================================================================
# 8. FAILURES PAGE
# ==============================================================================
elif nav_selection == "Failures":
    st.subheader("⚠️ Diagnostic Failure Log")
    st.caption("Deep diagnostic tracking for validation errors, timeouts, provider failures, and streaming drops.")

    db = SessionLocal()
    try:
        failures = FailureRepository.list_failures(db, limit=50)
    finally:
        db.close()

    if failures:
        for f in failures:
            with st.expander(f"🔴 [{f.failure_type}] Run {f.run_id} ({f.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"):
                st.markdown(f"**Error Message:** `{f.error_message}`")
                st.markdown(f"**Model:** `{f.model}` | **Prompt Version:** `{f.prompt_version}`")
                st.markdown(f"**Retries Attempted:** `{f.retry_count}` | **Repairs Attempted:** `{f.repair_count}` | **Fallback Used:** `{'Yes' if f.fallback_used else 'No'}`")
                if f.raw_payload:
                    st.code(f.raw_payload, language="text")
    else:
        st.success("No failure records logged in database.")


# ==============================================================================
# 9. METRICS PAGE
# ==============================================================================
elif nav_selection == "Metrics":
    st.subheader("📊 Verifiable Aggregate System Metrics")
    st.caption("Formulas and definitions documented in docs/evaluation.md. All metrics derived from stored run data.")

    db = SessionLocal()
    try:
        metrics = RunRepository.get_aggregate_metrics(db)
    finally:
        db.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Executions", metrics["total_runs"])
    c2.metric("Schema Validity", f"{metrics['schema_validity_pct']}%")
    c3.metric("Average Latency", f"{metrics['avg_latency_ms']} ms")
    c4.metric("Average Tokens", f"{metrics['avg_tokens']}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total Cost (USD)", f"${metrics['total_cost_usd']:.6f}")
    c6.metric("Repair Rate", f"{metrics['repair_rate_pct']}%")
    c7.metric("Failure Rate", f"{metrics['failure_rate_pct']}%")
    c8.metric("Cache Hit Rate", f"{metrics['cache_hit_rate_pct']}%")
