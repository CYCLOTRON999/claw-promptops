# CLAW PROMPTOPS - Metrics & Evaluation Framework Specification

This document provides formal definitions and mathematical formulations for all metrics calculated, tracked, and displayed within CLAW PromptOps.

---

## 1. Schema Validity Rate
- **Definition:** The percentage of runs that produced structured output strictly conforming to the required schema (JSON Schema + Pydantic validation).
- **Formula:**
  $$\text{Schema Validity Rate (\%)} = \left(\frac{N_{\text{valid}}}{N_{\text{total}}}\right) \times 100$$
- **Note:** Responses that initially failed validation but succeeded after automated repair are counted in `N_repaired` and included in `N_valid`.

---

## 2. Instruction-Following Rate
- **Definition:** The percentage of deterministic constraints (e.g. required fields, forbidden keywords, maximum item bounds, type conformity) satisfied across evaluated test cases.
- **Formula:**
  $$\text{Instruction-Following Rate (\%)} = \left(\frac{\sum \text{Passed Checks}}{\sum \text{Total Checks}}\right) \times 100$$

---

## 3. Average Latency (Roundtrip)
- **Definition:** Mean end-to-end response time in milliseconds across all runs (including retry and repair attempts).
- **Formula:**
  $$\overline{L} = \frac{\sum_{i=1}^{N} \text{latency\_ms}_i}{N}$$

---

## 4. Token Consumption Metrics
- **Input Tokens ($T_{\text{in}}$):** Number of prompt tokens processed by the model adapter.
- **Output Tokens ($T_{\text{out}}$):** Number of completion tokens generated.
- **Total Tokens:** $T_{\text{total}} = T_{\text{in}} + T_{\text{out}}$
- **Average Tokens per Run:** $\overline{T} = \frac{\sum T_{\text{total}}}{N}$

---

## 5. Estimated Cost Calculation
- **Definition:** Estimated USD cost calculated from model-specific pricing per 1,000 tokens.
- **Formula:**
  $$\text{Cost} = \left(\frac{T_{\text{in}}}{1000} \times P_{\text{in}}\right) + \left(\frac{T_{\text{out}}}{1000} \times P_{\text{out}}\right)$$
  Where $P_{\text{in}}$ and $P_{\text{out}}$ are the configured input and output prices per 1,000 tokens.
- **Rule:** If pricing is not explicitly configured for a model, the system displays `"Cost unavailable"` rather than synthesizing a dummy number.

---

## 6. Repair Rate
- **Definition:** The proportion of total runs where the initial model output violated validation rules and required automated prompt repair.
- **Formula:**
  $$\text{Repair Rate (\%)} = \left(\frac{N_{\text{repaired}}}{N_{\text{total}}}\right) \times 100$$

---

## 7. Retry Rate & Fallback Rate
- **Retry Rate:**
  $$\text{Retry Rate (\%)} = \left(\frac{N_{\text{retried}}}{N_{\text{total}}}\right) \times 100$$
- **Fallback Rate:**
  $$\text{Fallback Rate (\%)} = \left(\frac{N_{\text{fallback}}}{N_{\text{total}}}\right) \times 100$$

---

## 8. Failure Rate
- **Definition:** Proportion of runs that failed permanently (exhausted all retries, all fallbacks, or all repair attempts).
- **Formula:**
  $$\text{Failure Rate (\%)} = \left(\frac{N_{\text{failed}}}{N_{\text{total}}}\right) \times 100$$

---

## 9. Cache Hit Rate
- **Definition:** Percentage of generation requests served immediately from the configuration-aware cache without invoking model adapters.
- **Formula:**
  $$\text{Cache Hit Rate (\%)} = \left(\frac{C_{\text{hits}}}{C_{\text{hits}} + C_{\text{misses}}}\right) \times 100$$
