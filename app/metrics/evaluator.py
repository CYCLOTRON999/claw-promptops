"""Instruction-following and semantic constraint evaluation framework."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationReport(BaseModel):
    """Detailed score and checklist of instruction-following adherence."""
    passed: bool
    score: float = Field(..., ge=0.0, le=1.0, description="Fraction of checks passed (0.0 to 1.0)")
    total_checks: int
    passed_checks: int
    details: List[str] = Field(default_factory=list)


class InstructionEvaluator:
    """Evaluates whether generated outputs adhered to test case instruction constraints."""

    @classmethod
    def evaluate(
        cls,
        output_dict: Optional[Dict[str, Any]],
        raw_text: str,
        expected: Dict[str, Any]
    ) -> EvaluationReport:
        """Run deterministic checks against expected properties."""
        details: List[str] = []
        total_checks = 0
        passed_checks = 0

        # Check 1: Valid JSON requirement
        if "valid_json" in expected:
            total_checks += 1
            if expected["valid_json"]:
                if output_dict is not None and isinstance(output_dict, dict):
                    passed_checks += 1
                    details.append("PASS: Valid JSON object produced")
                else:
                    details.append("FAIL: Expected valid JSON object but was None or invalid")
            else:
                if output_dict is None:
                    passed_checks += 1
                    details.append("PASS: Expected non-JSON or failure, correctly caught")
                else:
                    details.append("FAIL: Expected invalid output, but output was valid JSON")

        # If output_dict is None, remaining structured checks fail
        if output_dict is None or not isinstance(output_dict, dict):
            # Check remaining text-based expectations
            if "forbidden_content" in expected:
                for forbidden in expected["forbidden_content"]:
                    total_checks += 1
                    if forbidden.lower() not in raw_text.lower():
                        passed_checks += 1
                        details.append(f"PASS: Forbidden content '{forbidden}' not found in raw text")
                    else:
                        details.append(f"FAIL: Forbidden content '{forbidden}' found in raw text")

            score = (passed_checks / total_checks) if total_checks > 0 else 0.0
            return EvaluationReport(
                passed=(passed_checks == total_checks and total_checks > 0),
                score=round(score, 4),
                total_checks=total_checks,
                passed_checks=passed_checks,
                details=details
            )

        # Check 2: Required field presence
        if "required_fields" in expected:
            for field in expected["required_fields"]:
                total_checks += 1
                if field in output_dict and output_dict[field] is not None:
                    passed_checks += 1
                    details.append(f"PASS: Required field '{field}' is present")
                else:
                    details.append(f"FAIL: Required field '{field}' is missing or null")

        # Check 3: Forbidden content
        if "forbidden_content" in expected:
            for forbidden in expected["forbidden_content"]:
                total_checks += 1
                text_to_check = (raw_text + " " + str(output_dict)).lower()
                if forbidden.lower() not in text_to_check:
                    passed_checks += 1
                    details.append(f"PASS: Forbidden content '{forbidden}' absent")
                else:
                    details.append(f"FAIL: Forbidden content '{forbidden}' detected in output")

        # Check 4: Required keywords
        if "required_keywords" in expected:
            for kw in expected["required_keywords"]:
                total_checks += 1
                text_to_check = (raw_text + " " + str(output_dict)).lower()
                if kw.lower() in text_to_check:
                    passed_checks += 1
                    details.append(f"PASS: Required keyword '{kw}' found")
                else:
                    details.append(f"FAIL: Required keyword '{kw}' not found")

        # Check 5: Max array items (e.g. "don't put more than 4 activities per day")
        if "max_items" in expected:
            for field_name, max_limit in expected["max_items"].items():
                total_checks += 1
                field_val = output_dict.get(field_name)
                if isinstance(field_val, list):
                    if len(field_val) <= max_limit:
                        passed_checks += 1
                        details.append(f"PASS: Array '{field_name}' length {len(field_val)} <= {max_limit}")
                    else:
                        details.append(f"FAIL: Array '{field_name}' length {len(field_val)} exceeds limit {max_limit}")
                else:
                    # If field is not a list, check passes if not applicable or fails
                    passed_checks += 1
                    details.append(f"PASS: Field '{field_name}' does not exceed list constraint")

        # Check 6: Type constraints
        if "type_constraints" in expected:
            for field_name, expected_type in expected["type_constraints"].items():
                total_checks += 1
                val = output_dict.get(field_name)
                type_ok = False
                if expected_type == "string" and isinstance(val, str):
                    type_ok = True
                elif expected_type == "integer" and isinstance(val, int):
                    type_ok = True
                elif expected_type == "array" and isinstance(val, list):
                    type_ok = True
                elif expected_type == "object" and isinstance(val, dict):
                    type_ok = True

                if type_ok:
                    passed_checks += 1
                    details.append(f"PASS: Field '{field_name}' is of type {expected_type}")
                else:
                    details.append(f"FAIL: Field '{field_name}' expected {expected_type}, got {type(val).__name__}")

        total_checks = max(total_checks, 1)
        score = passed_checks / total_checks
        is_passed = (passed_checks == total_checks)

        return EvaluationReport(
            passed=is_passed,
            score=round(score, 4),
            total_checks=total_checks,
            passed_checks=passed_checks,
            details=details
        )
