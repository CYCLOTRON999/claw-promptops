"""JSON extraction and robust text-to-JSON parsing."""

import json
import re
from typing import Any, Dict, Optional, Tuple


class JSONParseError(ValueError):
    """Raised when JSON cannot be parsed from model completion."""
    def __init__(self, message: str, raw_text: str):
        super().__init__(message)
        self.raw_text = raw_text


class JSONParser:
    """Extracts and parses JSON structures from raw model outputs, handling markdown fences and preambles."""

    @staticmethod
    def extract_and_parse(text: str) -> Tuple[Any, Optional[str]]:
        """Attempt to extract and parse JSON from text.

        Returns (parsed_object, extracted_json_string).
        Raises JSONParseError if no valid JSON structure could be decoded.
        """
        if not text or not text.strip():
            raise JSONParseError("Model output is completely empty.", raw_text=text)

        cleaned = text.strip()

        # 1. Direct parse attempt
        try:
            return json.loads(cleaned), cleaned
        except json.JSONDecodeError:
            pass

        # 2. Check for markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return json.loads(candidate), candidate
            except json.JSONDecodeError as exc:
                # If still fails inside fence, record specific error
                raise JSONParseError(f"Malformed JSON inside code block: {exc}", raw_text=text)

        # 3. Find outer outermost curly braces { ... } or brackets [ ... ]
        curly_start = cleaned.find("{")
        curly_end = cleaned.rfind("}")
        if curly_start != -1 and curly_end != -1 and curly_end > curly_start:
            candidate = cleaned[curly_start:curly_end + 1].strip()
            try:
                return json.loads(candidate), candidate
            except json.JSONDecodeError:
                pass

        bracket_start = cleaned.find("[")
        bracket_end = cleaned.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            candidate = cleaned[bracket_start:bracket_end + 1].strip()
            try:
                return json.loads(candidate), candidate
            except json.JSONDecodeError:
                pass

        # 4. If all heuristics fail, raise structured JSONParseError
        raise JSONParseError("Unable to locate or parse valid JSON from model response.", raw_text=text)
